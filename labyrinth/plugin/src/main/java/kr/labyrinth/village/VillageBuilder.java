package kr.labyrinth.village;

import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.command.CommandSender;

/**
 * {@code /labadmin village build [here | <x> <z>] [north|east|south|west] [force]} (VILLAGE.md §4.1) — 개발용.
 * 위치를 안 주면 월드 스폰 둘레 64칸 안에서, 방향을 안 주면 그 자리 4방향 중에서 계획기가 지형을 가장 적게 바꾸는 쪽을 고른다.
 * 순서: 지형 조사 → 계획(겹침·물·구조물·동굴·한도 검사, 하나라도 걸리면 짓지 않음) → 청크 고정 → 나무 치우기 →
 * 지형 다듬기 → 조각 → 길 → 표지판·깃발 → 메타데이터·월드 스폰·NPC·입구. 전부 틱 분할.
 */
final class VillageBuilder extends VillageJob {

    static final int SEARCH = 64;

    private enum Step { WIPE_LOAD, WIPE, SCAN, PLAN, LOAD, TREES, CLEAR, TERRAIN, PIECES, PATHS, POST, META }

    private final World world;
    private final Integer fx, fz, fixedTurns;
    private final boolean force;
    private final VillageLibrary lib;
    private final VillageMeta old;

    private Step step;
    private Scan.ChunkPump pump;
    private Scan.ChunkPump keep;
    private TerrainGrid grid;
    private final AtomicInteger pending = new AtomicInteger();
    private Future<Plan> planFuture;
    private Plan plan;
    private Scan.Snapshots snaps;
    private Future<Trees.Result> treeFuture;
    private List<long[]> clear = List.of();
    private List<long[]> regrass = List.of();
    private int cursor, cursor2, cursor3;
    private int ox, oz;
    private PlanWriter writer;
    private String planNote = "";

    VillageBuilder(VillageModule module, CommandSender sender, World world, Integer x, Integer z, Integer turns, boolean force, VillageMeta old) {
        super(module, sender, "마을 짓기");
        this.world = world;
        this.fx = x;
        this.fz = z;
        this.fixedTurns = turns;
        this.force = force;
        this.lib = module.library();
        this.old = old;
    }

    @Override
    protected void begin() {
        writer = new PlanWriter(world, null, null, lib.layout.pathStyles, null);
        Location sp = world.getSpawnLocation();
        if (fx != null) {
            ox = fx;
            oz = fz;
        } else {
            ox = sp.getBlockX();
            oz = sp.getBlockZ();
        }
        say("<#c9a2ff>마을 짓기 시작</#c9a2ff> <gray>— " + (fx != null ? "자리 (" + ox + ", " + oz + ")"
                : fixedTurns != null ? "월드 스폰 (" + ox + ", " + oz + ")" : "월드 스폰 (" + ox + ", " + oz + ") 둘레 " + SEARCH + "칸에서 자리 찾기")
                + " · 방향 " + (fixedTurns == null ? "자동(4방향 비교)" : Dir.NORTH.rotate(fixedTurns).key())
                + (force && old != null ? " · <#ff9a4d>force: 예전 마을을 지우고 다시</#ff9a4d>" : ""));
        if (force && old != null) {
            step = Step.WIPE_LOAD;
            int[] b = bounds(old.protect);
            pump = new Scan.ChunkPump(world, module.plugin(), true, true, 12, c -> { }).area(b[0], b[1], b[2], b[3]);
        } else {
            startScan();
        }
    }

    private static int[] bounds(List<VillageMeta.Box> boxes) {
        int x0 = Integer.MAX_VALUE, z0 = Integer.MAX_VALUE, x1 = Integer.MIN_VALUE, z1 = Integer.MIN_VALUE;
        for (VillageMeta.Box b : boxes) {
            x0 = Math.min(x0, b.x0());
            z0 = Math.min(z0, b.z0());
            x1 = Math.max(x1, b.x1());
            z1 = Math.max(z1, b.z1());
        }
        return new int[] {x0, z0, x1, z1};
    }

    private void startScan() {
        step = Step.SCAN;
        int r = lib.planner.scanReach() + (fx == null && fixedTurns == null ? SEARCH : 0);
        grid = TerrainGrid.around(ox, oz, r);
        int minY = world.getMinHeight(), maxY = world.getMaxHeight() - 1;
        pump = new Scan.ChunkPump(world, module.plugin(), true, false, 12, chunk -> {
            var snap = chunk.getChunkSnapshot(true, true, false, false);
            pending.incrementAndGet();
            async().execute(() -> {
                try {
                    Scan.columns(snap, grid, minY, maxY);
                } finally {
                    pending.decrementAndGet();
                }
            });
        }).area(ox - r, oz - r, ox + r, oz + r);
    }

    @Override
    protected String status() {
        return switch (step) {
            case WIPE_LOAD, SCAN, LOAD -> label() + " 청크 " + pump.done + "/" + pump.total;
            case WIPE -> "예전 마을 지우기 " + cursor + "/" + old.protect.size();
            case PLAN -> "계획 세우는 중 (" + elapsedSec() + "초)";
            case TREES -> "나무 찾는 중";
            case CLEAR -> "나무 치우기 " + pct(clear.isEmpty() ? 1 : (double) cursor / clear.size());
            case TERRAIN -> "지형 다듬기 " + pct((double) cursor / (plan.gn * plan.gn));
            case PIECES -> "조각 짓기 " + (cursor + 1) + "/" + plan.pieces.size();
            case PATHS -> "길 " + (cursor + 1) + "/" + plan.paths.size();
            case POST, META -> "마무리";
        };
    }

    private String label() {
        return switch (step) {
            case WIPE_LOAD -> "예전 마을 불러오기";
            case SCAN -> "지형 조사";
            default -> "청크 고정";
        };
    }

    @Override
    protected boolean tick(Budget b) throws Exception {
        switch (step) {
            case WIPE_LOAD -> {
                pump.pump();
                if (pump.finished()) {
                    keep = pump;
                    step = Step.WIPE;
                    cursor = 0;
                    cursor2 = 0;
                }
            }
            case WIPE -> {
                if (wipe(b)) {
                    say("<gray>  예전 마을 자리를 원래 높이의 땅으로 되돌렸습니다");
                    startScan();
                }
            }
            case SCAN -> {
                pump.pump();
                if (pump.finished() && pending.get() == 0) {
                    step = Step.PLAN;
                    say("<gray>  지형 조사 완료: 청크 " + pump.done + "개" + (pump.failed > 0 ? " (실패 " + pump.failed + ")" : "") + " · 계획 세우는 중");
                    planFuture = async().submit(this::makePlan);
                }
            }
            case PLAN -> {
                if (!planFuture.isDone()) return false;
                plan = planFuture.get();
                if (plan == null || !plan.ok()) {
                    Text.error(sender, "여기에는 마을을 지을 수 없습니다 — " + Text.escape(plan == null ? "계획 없음" : Planner.label(plan.fail) + ": " + plan.reason));
                    if (!planNote.isEmpty()) Text.send(sender, "<gray>  " + Text.escape(planNote));
                    Text.send(sender, "<gray>  다른 자리는 <white>/labadmin village survey</white> 로 찾으세요. "
                            + (keep != null ? "<#ff9a4d>(force: 예전 마을은 이미 지운 상태)" : "(아무것도 바꾸지 않았습니다)"));
                    Log.info("[마을] 짓기 거절: " + (plan == null ? "-" : plan.reason));
                    return true;
                }
                PlanWriter w0 = writer;
                writer = new PlanWriter(world, plan, grid, lib.layout.pathStyles, null);
                writer.changed = w0.changed;
                writer.errors = w0.errors;
                say("<#7fe07f>  계획: " + Text.escape(plan.summary()) + "</#7fe07f>");
                if (!planNote.isEmpty()) say("<gray>  " + Text.escape(planNote));
                step = Step.LOAD;
                int r = lib.planner.scanReach();
                snaps = new Scan.Snapshots(world);
                pump = new Scan.ChunkPump(world, module.plugin(), true, true, 12, snaps::add)
                        .area(plan.cx - r, plan.cz - r, plan.cx + r, plan.cz + r);
            }
            case LOAD -> {
                pump.pump();
                if (pump.finished()) {
                    step = Step.TREES;
                    treeFuture = async().submit(() -> Trees.analyze(snaps, grid, plan.cx, plan.cz, lib.planner.reach(), this::tidy));
                }
            }
            case TREES -> {
                if (!treeFuture.isDone()) return false;
                Trees.Result t = treeFuture.get();
                snaps = null;
                clear = new ArrayList<>(t.remove());
                regrass = t.regrass();
                cursor = 0;
                step = Step.CLEAR;
                say("<gray>  나무: 원목 " + t.logs() + " · 잎 " + t.leaves() + " · 붙은 것 " + t.parts() + (t.capped() ? " <#ff9a4d>(상한 도달)" : ""));
            }
            case CLEAR -> {
                BlockData air = writer.data("minecraft:air");
                while (cursor < clear.size() && b.more()) {
                    long[] p = clear.get(cursor++);
                    Block blk = world.getBlockAt((int) p[0], (int) p[1], (int) p[2]);
                    if (!blk.getType().isAir()) {
                        blk.setBlockData(air, false);
                        b.use(1);
                    }
                }
                while (cursor >= clear.size() && cursor - clear.size() < regrass.size() && b.more()) {
                    long[] p = regrass.get(cursor++ - clear.size());
                    Block blk = world.getBlockAt((int) p[0], (int) p[1], (int) p[2]);
                    if (blk.getRelative(0, 1, 0).getType().isAir()) set(blk, "minecraft:grass_block[snowy=false]", b);
                }
                if (cursor >= clear.size() + regrass.size()) {
                    step = Step.TERRAIN;
                    cursor = 0;
                }
            }
            case TERRAIN -> {
                int n = plan.gn * plan.gn;
                while (cursor < n && b.more()) writer.terrainColumn(cursor++, b);
                if (cursor >= n) {
                    say("<gray>  지형 다듬기 완료 (깎기 " + plan.cut + " · 메우기 " + plan.fill + " · 바꾼 블록 " + writer.changed + ")");
                    step = Step.PIECES;
                    cursor = 0;
                    cursor2 = 0;
                }
            }
            case PIECES -> {
                while (cursor < plan.pieces.size() && b.more()) {
                    Plan.Placed pl = plan.pieces.get(cursor);
                    int total = pl.bp.w * pl.bp.h * pl.bp.d;
                    while (cursor2 < total && b.more()) writer.pieceCell(pl, cursor2++, b);
                    if (cursor2 >= total) {
                        cursor++;
                        cursor2 = 0;
                    }
                }
                if (cursor >= plan.pieces.size()) {
                    step = Step.PATHS;
                    cursor = 0;
                    cursor2 = 0;
                }
            }
            case PATHS -> {
                while (cursor < plan.paths.size() && b.more()) {
                    Plan.PathPlan pp = plan.paths.get(cursor);
                    while (cursor2 < pp.cells.size() && b.more()) writer.pathCell(pp, pp.cells.get(cursor2++), b);
                    if (cursor2 >= pp.cells.size()) {
                        cursor++;
                        cursor2 = 0;
                    }
                }
                if (cursor >= plan.paths.size()) step = Step.POST;
            }
            case POST -> {
                int[] sb = writer.post();
                say("<gray>  표지판 " + sb[0] + " · 깃발 " + sb[1] + (writer.errors > 0 ? " <#ff9a4d>· 문제 " + writer.errors + "건 (서버 로그)" : ""));
                step = Step.META;
            }
            case META -> {
                finishMeta();
                return true;
            }
        }
        return false;
    }

    // ── 계획 ─────────────────────────────────────────────────────────────

    private Plan makePlan() {
        Planner pl = lib.planner;
        if (fx == null && fixedTurns == null) {
            Planner.SurveyResult r = pl.survey(grid, ox, oz, SEARCH, 4, 1, null, () -> cancelled);
            if (r.best().isEmpty()) {
                planNote = "스폰 둘레 " + r.centers() + "곳 × 4방향 모두 탈락: " + rejects(r.rejects());
                Plan p = pl.plan(grid, ox, oz, 0, false);
                if (p.ok()) {
                    p.fail = Planner.Fail.OVERLAP;
                    p.reason = "알 수 없는 이유";
                }
                return p;
            }
            Plan best = r.best().get(0);
            planNote = "스폰 둘레 " + r.centers() + "곳 × 4방향 비교 → 가장 덜 바꾸는 자리";
            return best;
        }
        if (fixedTurns != null) return pl.plan(grid, ox, oz, fixedTurns, true);
        Planner.Ctx ctx = pl.context(grid, ox, oz);
        Plan best = null;
        StringBuilder sb = new StringBuilder();
        for (int t = 0; t < 4; t++) {
            Plan p = pl.plan(ctx, t, true);
            sb.append(Dir.NORTH.rotate(t).key()).append(": ").append(p.ok() ? "깎기+메우기 " + (p.cut + p.fill) : Planner.label(p.fail)).append("  ");
            if (p.ok() && (best == null || p.score() < best.score())) best = p;
            if (best == null && t == 3) best = pl.plan(ctx, 0, true);
        }
        planNote = "4방향: " + sb.toString().trim();
        return best;
    }

    static String rejects(Map<Planner.Fail, Integer> rj) {
        StringBuilder sb = new StringBuilder();
        rj.forEach((k, v) -> sb.append(Planner.label(k)).append(' ').append(v).append(" · "));
        return sb.length() == 0 ? "-" : sb.substring(0, sb.length() - 3);
    }

    // ── 예전 마을 지우기 (force) ─────────────────────────────────────────

    private boolean wipe(Budget b) {
        while (cursor < old.protect.size() && b.more()) {
            VillageMeta.Box bx = old.protect.get(cursor);
            int w = bx.x1() - bx.x0() + 1, d = bx.z1() - bx.z0() + 1;
            int cols = w * d;
            while (cursor2 < cols && b.more()) {
                int x = bx.x0() + cursor2 % w, z = bx.z0() + cursor2 / w;
                cursor2++;
                int t = old.terrain != null && old.terrain.in(x, z) ? old.terrain.height(x, z) : bx.y0() + 2;
                for (int y = bx.y0(); y <= bx.y1(); y++) {
                    String want = y > t ? "minecraft:air" : y == t ? "minecraft:grass_block" : y >= t - 3 ? "minecraft:dirt" : "minecraft:stone";
                    set(world.getBlockAt(x, y, z), want, b);
                }
            }
            if (cursor2 >= cols) {
                cursor++;
                cursor2 = 0;
            }
        }
        if (cursor < old.protect.size()) return false;
        // 상자 밖 옹벽·기초 블록도 자연 블록으로 (다시 조사할 때 '사람이 지은 블록'으로 걸리지 않게)
        VillageMeta.TerrainRec tr = old.terrain;
        if (tr == null) return true;
        int n = tr.n() * tr.n();
        while (cursor3 < n && b.more()) {
            int x = tr.x0() + cursor3 % tr.n(), z = tr.z0() + cursor3 / tr.n();
            cursor3++;
            int t = tr.height(x, z);
            for (int y = t - 6; y <= t + 3; y++) {
                Block blk = world.getBlockAt(x, y, z);
                if (Scan.kind(blk.getType()) != Nature.Kind.UNNATURAL) continue;
                set(blk, y > t ? "minecraft:air" : y == t ? "minecraft:grass_block" : y >= t - 3 ? "minecraft:dirt" : "minecraft:stone", b);
            }
        }
        return cursor3 >= n;
    }

    // ── 칸 일은 PlanWriter (구역 짓기와 같이 씀) ─────────────────────────

    private void set(Block blk, String state, Budget b) { writer.set(blk, state, b); }

    /** 마을이 손대는 칸인가 (나무 치우기 범위) — PlanWriter#tidy. */
    boolean tidy(int x, int z) { return writer.tidy(x, z); }

    // ── 메타데이터 ───────────────────────────────────────────────────────

    /** 발 칸 보정 (PlanWriter#standable). */
    static VillageMeta.Pos standable(World w, VillageMeta.Pos p) { return PlanWriter.standable(w, p); }

    private void finishMeta() throws Exception {
        VillageMeta m = Markers.meta(plan, lib.layout);
        m.buildId = UUID.randomUUID().toString();
        m.builtAt = java.time.Instant.now().toString();
        m.pluginVersion = module.plugin().getPluginMeta().getVersion();
        if (m.spawn != null) m.spawn = standable(world, m.spawn);
        if (m.entrance != null) m.entrance = standable(world, m.entrance);
        m.npcs.replaceAll((k, v) -> standable(world, v));
        File f = VillageService.metaFile(world);
        m.save(f);
        if (m.spawn != null) {
            world.setSpawnLocation(new Location(world, m.spawn.x(), m.spawn.y(), m.spawn.z(), m.spawn.yaw(), 0f));
        }
        try {
            world.setGameRule(org.bukkit.GameRules.RESPAWN_RADIUS, 0);
        } catch (Throwable t) {
            Log.warn("[마을] 스폰 반경 게임룰(respawn_radius)을 바꾸지 못했습니다: " + t.getMessage());
        }
        VillageService svc = module.service();
        svc.load();
        svc.applyIfNew(true);
        say("<#7fe07f><b>마을을 지었습니다</b></#7fe07f> <gray>(" + elapsedSec() + "초 · 조각 " + plan.pieces.size() + " · 길 칸 "
                + plan.paths.stream().mapToInt(p -> p.cells.size()).sum() + " · 바꾼 블록 " + writer.changed
                + (writer.errors > 0 ? " · <#ff9a4d>문제 " + writer.errors + "건</#ff9a4d>" : "") + ")");
        say("<gray>  메타데이터: <white>" + Text.escape(f.getPath()) + "</white> · 스폰 = 광장 · 확인: <white>/labadmin village selftest</white>");
        Log.info("[마을] 짓기 완료: " + plan.summary());
    }

    @Override
    protected void cleanup() {
        if (keep != null) keep.release();
        if (pump != null) pump.release();
        snaps = null;
    }
}
