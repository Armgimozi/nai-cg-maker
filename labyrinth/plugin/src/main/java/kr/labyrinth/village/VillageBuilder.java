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
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.DyeColor;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Banner;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Sign;
import org.bukkit.block.banner.Pattern;
import org.bukkit.block.banner.PatternType;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.type.Slab;
import org.bukkit.block.sign.Side;
import org.bukkit.block.sign.SignSide;
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
    private int cursor, cursor2, cursor3;
    private int ox, oz;
    private final Map<String, BlockData> dataCache = new HashMap<>();
    private final Map<String, BlockData> pieceCache = new HashMap<>();
    private int changed, errors;
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
                    Text.send(sender, "<gray>  다른 자리는 <white>/labadmin village survey</white> 로 찾으세요. (아무것도 바꾸지 않았습니다)");
                    Log.info("[마을] 짓기 거절: " + (plan == null ? "-" : plan.reason));
                    return true;
                }
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
                    treeFuture = async().submit(() -> Trees.analyze(snaps, grid, plan.cx, plan.cz, lib.planner.reach()));
                }
            }
            case TREES -> {
                if (!treeFuture.isDone()) return false;
                Trees.Result t = treeFuture.get();
                snaps = null;
                clear = t.remove();
                cursor = 0;
                step = Step.CLEAR;
                say("<gray>  나무: 원목 " + t.logs() + " · 잎 " + t.leaves() + " · 붙은 것 " + t.parts() + (t.capped() ? " <#ff9a4d>(상한 도달)" : ""));
            }
            case CLEAR -> {
                BlockData air = Material.AIR.createBlockData();
                while (cursor < clear.size() && b.more()) {
                    long[] p = clear.get(cursor++);
                    Block blk = world.getBlockAt((int) p[0], (int) p[1], (int) p[2]);
                    if (!blk.getType().isAir()) {
                        blk.setBlockData(air, false);
                        b.use(1);
                    }
                }
                if (cursor >= clear.size()) {
                    step = Step.TERRAIN;
                    cursor = 0;
                }
            }
            case TERRAIN -> {
                int n = plan.gn * plan.gn;
                while (cursor < n && b.more()) terrainColumn(cursor++, b);
                if (cursor >= n) {
                    say("<gray>  지형 다듬기 완료 (깎기 " + plan.cut + " · 메우기 " + plan.fill + " · 바꾼 블록 " + changed + ")");
                    step = Step.PIECES;
                    cursor = 0;
                    cursor2 = 0;
                }
            }
            case PIECES -> {
                while (cursor < plan.pieces.size() && b.more()) {
                    Plan.Placed pl = plan.pieces.get(cursor);
                    int total = pl.bp.w * pl.bp.h * pl.bp.d;
                    while (cursor2 < total && b.more()) pieceCell(pl, cursor2++, b);
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
                    while (cursor2 < pp.cells.size() && b.more()) pathCell(pp, pp.cells.get(cursor2++), b);
                    if (cursor2 >= pp.cells.size()) {
                        cursor++;
                        cursor2 = 0;
                    }
                }
                if (cursor >= plan.paths.size()) step = Step.POST;
            }
            case POST -> {
                post();
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
                    Block blk = world.getBlockAt(x, y, z);
                    if (!blk.getBlockData().getAsString().equals(want)) {
                        blk.setBlockData(data(want), false);
                        b.use(1);
                    }
                }
            }
            if (cursor2 >= cols) {
                cursor++;
                cursor2 = 0;
            }
        }
        return cursor >= old.protect.size();
    }

    // ── 지형 ─────────────────────────────────────────────────────────────

    BlockData data(String state) {
        return dataCache.computeIfAbsent(state, s -> {
            try {
                return Bukkit.createBlockData(s);
            } catch (IllegalArgumentException e) {
                errors++;
                Log.warn("[마을] 블록 문자열 오류: " + s);
                return Material.STONE.createBlockData();
            }
        });
    }

    private void set(Block blk, String state, Budget b) {
        BlockData d = data(state);
        if (blk.getBlockData().matches(d)) return;
        blk.setBlockData(d, false);
        b.use(1);
        changed++;
    }

    /** 옹벽·기초 블록: 그 칸을 덮는 조각의 foundation_mix (+ 아래쪽은 이끼 섞기), 없으면 첫 조각(광장) 것. */
    private String foundation(int x, int y, int z) {
        Blueprint src = plan.pieces.get(0).bp;
        for (Plan.Placed pl : plan.pieces) {
            if (x >= pl.x0 - 1 && x <= pl.x0 + pl.w2 && z >= pl.z0 - 1 && z <= pl.z0 + pl.d2) {
                src = pl.bp;
                break;
            }
        }
        long h = Blueprint.hash(x, y, z);
        String f = src.foundationAt(h);
        if (Math.floorMod(h >>> 7, 5) == 0) {
            String id = Nature.key(f);
            String mossy = id.equals("cobblestone") ? "mossy_cobblestone" : id.endsWith("stone_bricks") && !id.startsWith("mossy") ? "mossy_stone_bricks" : null;
            if (mossy != null) return "minecraft:" + mossy;
        }
        return f;
    }

    private boolean replaceableTerrain(Material m) {
        Nature.Kind k = Scan.kind(m);
        return k == Nature.Kind.AIR || k == Nature.Kind.PLANT || k == Nature.Kind.GROUND || k == Nature.Kind.LEAVES
                || k == Nature.Kind.LOG || k == Nature.Kind.TREE_PART;
    }

    private void terrainColumn(int i, Budget b) {
        int lx = i % plan.gn, lz = i / plan.gn;
        int x = plan.gx0 + lx, z = plan.gz0 + lz;
        double dist = Math.hypot(x - plan.cx, z - plan.cz);
        int reach = lib.planner.reach();
        if (dist > reach || !grid.has(x, z)) return;
        int g = plan.ground[i], t = plan.field.target()[i];
        boolean inR = dist <= lib.planner.inner;
        boolean colChanged = t != g;
        byte src = plan.fixedSrc[i];
        int exposed = plan.field.exposed()[i];
        String surf = grid.surface(x, z);
        String top = Nature.topFor(surf), sub = Nature.subsurface(surf);
        if (!colChanged && !inR && exposed == 0) return;
        // 1. 목표보다 위: 공기 (식물·눈 포함, 위로 뻗은 자연 지형 덩어리까지)
        int clearTop = Math.max(g, t) + 2;
        for (int y = t + 1; y <= clearTop + 14; y++) {
            Block blk = world.getBlockAt(x, y, z);
            Material m = blk.getType();
            if (m.isAir()) {
                if (y > clearTop) break;
                continue;
            }
            Nature.Kind k = Scan.kind(m);
            boolean go = y <= g ? replaceableTerrain(m) : (k == Nature.Kind.PLANT || k == Nature.Kind.GROUND || k == Nature.Kind.LIQUID);
            if (!go) {
                if (y > clearTop) break;
                continue;
            }
            blk.setBlockData(data("minecraft:air"), false);
            b.use(1);
            changed++;
        }
        boolean footprint = src == 5;
        if (colChanged || exposed > 0) {
            // 2. 깎은 칸: 새 맨 윗블록 + 그 아래 두 칸 / 메운 칸: 원래 땅 위로 목표까지 (묻힌 잔디는 흙으로)
            //    옹벽 칸: 드러난 높이만큼 기초 블록(foundation_mix + 이끼)
            int lo = t < g ? t - 2 : t > g ? g : t;
            if (exposed > 0) lo = Math.min(lo, t - exposed + 1);
            for (int y = lo; y <= t; y++) {
                String want = exposed > 0 && y > t - exposed ? foundation(x, y, z) : y == t ? top : sub;
                Block blk = world.getBlockAt(x, y, z);
                if (!replaceableTerrain(blk.getType())) continue;
                set(blk, want, b);
            }
        } else if (!footprint) {
            return; // R 안 그대로인 칸: 식물만 지움
        }
        // 3. 바뀐 칸 바로 아래 빈칸 막기 (얇은 껍질 위에 서지 않게), 발자국은 6칸까지 기초로 (§0 동굴)
        int depth = footprint ? Planner.CAVE_DEPTH : 3;
        for (int k = 1; k <= depth; k++) {
            Block blk = world.getBlockAt(x, t - k, z);
            Nature.Kind kk = Scan.kind(blk.getType());
            if (kk == Nature.Kind.AIR || kk == Nature.Kind.LIQUID) set(blk, footprint ? foundation(x, t - k, z) : sub, b);
        }
        // 4. 띠의 눈 덮인 칸은 눈 한 겹 되살림 (R 안은 지움 — §4.1 2번)
        if (!inR && src == 0 && grid.flag(x, z, Terrain.SNOW) && exposed == 0) {
            Block above = world.getBlockAt(x, t + 1, z);
            if (above.getType().isAir()) set(above, "minecraft:snow[layers=1]", b);
        }
    }

    // ── 조각 ─────────────────────────────────────────────────────────────

    /** 회전한 팔레트 블록 (BlockData#rotate). */
    BlockData pieceData(Plan.Placed pl, int cp) {
        String key = pl.index() + ":" + cp;
        return pieceCache.computeIfAbsent(key, k -> {
            String st = pl.bp.state(cp);
            BlockData d = data(st).clone();
            d.rotate(Rot.of(pl.turns));
            return d;
        });
    }

    private void pieceCell(Plan.Placed pl, int k, Budget b) {
        Blueprint bp = pl.bp;
        int x = k % bp.w, z = (k / bp.w) % bp.d, y = k / (bp.w * bp.d);
        int cp = bp.cell(x, y, z);
        if (cp == Blueprint.KEEP) return;
        int[] w = pl.world(x, z);
        Block blk = world.getBlockAt(w[0], pl.worldY(y), w[1]);
        if (cp == Blueprint.AIR) {
            if (!blk.getType().isAir()) {
                blk.setBlockData(data("minecraft:air"), false);
                b.use(1);
            }
            return;
        }
        blk.setBlockData(pieceData(pl, cp), false);
        b.use(1);
    }

    // ── 길 ───────────────────────────────────────────────────────────────

    /** 길 블록의 반블록 (돌 벽돌 → 돌 벽돌 반블록 …), 없으면 null. */
    static String slabOf(String block) {
        String id = Nature.key(block).replace("cracked_", "");
        String slab;
        if (id.endsWith("bricks")) slab = id.substring(0, id.length() - 1) + "_slab";
        else if (id.endsWith("tiles")) slab = id.substring(0, id.length() - 1) + "_slab";
        else if (id.endsWith("planks")) slab = id.replace("_planks", "_slab");
        else slab = id + "_slab";
        Material m = Material.matchMaterial("minecraft:" + slab);
        return m != null && m.isBlock() && m.createBlockData() instanceof Slab ? "minecraft:" + slab + "[type=bottom,waterlogged=false]" : null;
    }

    private void pathCell(Plan.PathPlan pp, int[] c, Budget b) {
        int x = c[0], z = c[1], y = c[2];
        List<Blueprint.Weighted> style = lib.layout.pathStyles.getOrDefault(pp.def.style(), List.of());
        String block = Blueprint.pick(style, Blueprint.hash(x, 0, z), "minecraft:dirt_path");
        set(world.getBlockAt(x, y, z), block, b);
        for (int dy = 1; dy <= 2; dy++) {
            Block above = world.getBlockAt(x, y + dy, z);
            Nature.Kind k = Scan.kind(above.getType());
            if (k == Nature.Kind.PLANT || k == Nature.Kind.GROUND) set(above, "minecraft:air", b);
        }
        // 이웃 길이 1 높으면 반블록으로 반 칸 계단
        boolean higher = false;
        for (int[] d : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) {
            int h = pathHeight(x + d[0], z + d[1]);
            if (h == y + 1) higher = true;
        }
        if (higher) {
            String slab = slabOf(block);
            if (slab == null && !style.isEmpty()) slab = slabOf(style.get(0).block());
            if (slab != null) set(world.getBlockAt(x, y + 1, z), slab, b);
        }
    }

    private Map<Long, Integer> pathIndex;

    private int pathHeight(int x, int z) {
        if (pathIndex == null) {
            pathIndex = new HashMap<>();
            for (Plan.PathPlan pp : plan.paths) for (int[] c : pp.cells) pathIndex.putIfAbsent(PathRaster.key(c[0], c[1]), c[2]);
        }
        return pathIndex.getOrDefault(PathRaster.key(x, z), Integer.MIN_VALUE);
    }

    // ── 표지판·깃발 ──────────────────────────────────────────────────────

    private void post() {
        int signs = 0, banners = 0;
        for (Markers.Placed mk : Markers.all(plan)) {
            int[] w = mk.first();
            if (w == null) continue;
            Block blk = world.getBlockAt(w[0], w[1], w[2]);
            try {
                if (mk.marker().type().equals("sign")) {
                    BlockState st = blk.getState();
                    if (!(st instanceof Sign sign)) {
                        Log.warn("[마을] 표지판 마커 자리에 표지판이 없음: " + mk.piece().bp.id + " " + blk.getType());
                        errors++;
                        continue;
                    }
                    writeSide(sign.getSide(Side.FRONT), mk.marker().lines(), mk.marker().glow());
                    if (!mk.marker().back().isEmpty()) writeSide(sign.getSide(Side.BACK), mk.marker().back(), mk.marker().glow());
                    sign.setWaxed(true);
                    sign.update(true, false);
                    signs++;
                } else if (mk.marker().type().equals("banner")) {
                    BlockState st = blk.getState();
                    if (!(st instanceof Banner banner)) {
                        Log.warn("[마을] 깃발 마커 자리에 깃발이 없음: " + mk.piece().bp.id + " " + blk.getType());
                        errors++;
                        continue;
                    }
                    List<Pattern> pats = new ArrayList<>();
                    var reg = io.papermc.paper.registry.RegistryAccess.registryAccess().getRegistry(io.papermc.paper.registry.RegistryKey.BANNER_PATTERN);
                    for (String[] p : mk.marker().patterns()) {
                        PatternType type = reg.get(Key.key(p[0].contains(":") ? p[0] : "minecraft:" + p[0]));
                        DyeColor color;
                        try {
                            color = DyeColor.valueOf(p[1].toUpperCase(java.util.Locale.ROOT));
                        } catch (IllegalArgumentException e) {
                            color = null;
                        }
                        if (type == null || color == null) {
                            Log.warn("[마을] 깃발 무늬 오류: " + p[0] + " " + p[1]);
                            errors++;
                            continue;
                        }
                        pats.add(new Pattern(color, type));
                    }
                    banner.setPatterns(pats);
                    banner.update(true, false);
                    banners++;
                }
            } catch (Throwable t) {
                errors++;
                Log.error("[마을] 후처리 오류 (" + mk.marker().type() + ")", t);
            }
        }
        say("<gray>  표지판 " + signs + " · 깃발 " + banners + (errors > 0 ? " <#ff9a4d>· 문제 " + errors + "건 (서버 로그)" : ""));
    }

    private static void writeSide(SignSide side, List<String> lines, boolean glow) {
        for (int i = 0; i < 4; i++) side.line(i, Text.mm(i < lines.size() ? lines.get(i) : ""));
        side.setGlowingText(glow);
    }

    // ── 메타데이터 ───────────────────────────────────────────────────────

    /** 발 칸 보정: 발·머리 칸이 막혔으면 위로, 발밑이 비었으면 아래로 (최대 3칸). */
    static VillageMeta.Pos standable(World w, VillageMeta.Pos p) {
        int x = (int) Math.floor(p.x()), z = (int) Math.floor(p.z()), y = (int) Math.floor(p.y());
        for (int i = 0; i < 4; i++) {
            Block feet = w.getBlockAt(x, y, z);
            if (!feet.isPassable() || !feet.getRelative(0, 1, 0).isPassable()) {
                y++;
                continue;
            }
            if (feet.getRelative(0, -1, 0).isPassable() && i < 3) {
                y--;
                continue;
            }
            break;
        }
        return new VillageMeta.Pos(p.x(), y, p.z(), p.yaw());
    }

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
                + plan.paths.stream().mapToInt(p -> p.cells.size()).sum() + " · 바꾼 블록 " + changed
                + (errors > 0 ? " · <#ff9a4d>문제 " + errors + "건</#ff9a4d>" : "") + ")");
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
