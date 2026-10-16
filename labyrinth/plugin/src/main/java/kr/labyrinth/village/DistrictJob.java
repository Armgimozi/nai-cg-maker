package kr.labyrinth.village;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.ChunkSnapshot;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Enemy;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Tameable;
import org.bukkit.util.BoundingBox;

/**
 * 구역 짓기·미리 보기·되돌리기 (0.3.6.1 광산 마을, CONTRACT §2.13). 틱 분할 (VillageJob — 한 번에 하나).
 * <p>
 * 짓기 순서: 자리 후보마다 [펼치기 → 청크 불러오기·지형 조사(비동기 스냅샷) → 마스크 계획 → 지문·비자연 검사 → 엔티티 검사]
 * → 처음 통과한 자리에서 [나무 계산 → <b>바꿀 수 있는 모든 칸의 원래 블록을 백업 파일에 먼저</b> → 기록 state: building (보호 켬)
 * → 사람 내보내기 → 나무 → 지형 → 조각 → 길 → 표지판 → 바뀐 칸만 백업(DIFF) → state: built · NPC]. 모두 막히면 블록 0칸 바꿈.
 * <p>
 * 되돌리기(remove) = 백업에서 지금 블록이 우리가 놓은 것인 칸만 되돌림. 짓다가 꺼졌으면(building) 시작할 때 백업(BEFORE)으로 통째로
 * 되돌린 뒤 처음부터 (recover).
 */
final class DistrictJob extends VillageJob {

    enum Mode { BUILD, PREVIEW, REMOVE, RECOVER }

    /** 자리 요청: site = 배치의 자리, 또는 here (jx, jz 에서 dir 쪽으로). */
    record SiteReq(String id, DistrictLayout.Site site, int jx, int jz, Dir dir) {
        static SiteReq of(DistrictLayout.Site s) { return new SiteReq(s.id(), s, 0, 0, null); }

        static SiteReq here(int jx, int jz, Dir dir) { return new SiteReq("here", null, jx, jz, dir); }

        String label() { return site != null ? id : "here (" + jx + ", " + jz + ") " + dir.key(); }
    }

    private enum Step {
        RESTORE_LOAD, RESTORE_PUMP, RESTORE, NEXT_SITE, SCAN, PLAN, CHECK, ENTITIES, TREES, BACKUP_READ, BACKUP_SAVE,
        CLEAR, TERRAIN, PIECES, PATHS, POST, DIFF_READ, DIFF_SAVE, FINISH
    }

    private final DistrictService svc;
    private final DistrictLibrary.Entry entry;
    private final DistrictLayout L;
    private final Mode mode;
    private final boolean auto;
    private final World world;
    private final List<SiteReq> sites;
    private boolean buildAfterRecover;

    private Step step;
    private int siteIdx = -1;
    private SiteReq site;
    private DistrictLayout.Placement placement;
    private Planner planner;
    private FrozenCells frozen;
    private TerrainGrid grid;
    private Scan.Snapshots snaps;
    private Scan.ChunkPump pump;
    private final AtomicInteger pending = new AtomicInteger();
    private Future<Plan> planFuture;
    private Future<DistrictCheck.Result> checkFuture;
    private Future<Trees.Result> treeFuture;
    private Future<?> ioFuture;
    private Plan plan;
    private DistrictCheck.Result check;
    private PlanWriter writer;
    private List<long[]> clear = List.of(), regrass = List.of();
    private long[] cells;
    private final List<DistrictBackup.Entry> before = new ArrayList<>();
    private final List<DistrictBackup.Entry> diff = new ArrayList<>();
    private DistrictBackup backup;
    private DistrictMeta meta;
    private final List<Entity> moveOut = new ArrayList<>();
    private int cursor, cursor2;
    private int restored, restoreSame, restoreSkipped, restoreErrors;
    private final Set<Long> restoreSeen = new HashSet<>();
    private final Map<String, List<String>> blocked = new LinkedHashMap<>();
    private final List<String> previews = new ArrayList<>();
    private long writeStarted;

    private DistrictJob(VillageModule module, CommandSender sender, DistrictService svc, DistrictLibrary.Entry entry, Mode mode, boolean auto,
                        List<SiteReq> sites) {
        super(module, sender, switch (mode) {
            case BUILD -> "광산 마을 짓기";
            case PREVIEW -> "광산 마을 미리 보기";
            case REMOVE -> "광산 마을 되돌리기";
            case RECOVER -> "광산 마을 되돌린 뒤 다시 짓기";
        });
        this.svc = svc;
        this.entry = entry;
        this.L = entry.layout();
        this.mode = mode;
        this.auto = auto;
        this.world = svc.world();
        this.sites = sites;
    }

    /** 시작할 때 저절로 (config 자리 차례). */
    static DistrictJob auto(VillageModule m, DistrictService svc, DistrictLibrary.Entry e, List<String> siteIds) {
        return new DistrictJob(m, Bukkit.getConsoleSender(), svc, e, Mode.BUILD, true, configSites(e, siteIds));
    }

    /** 짓다가 꺼진 구역: 백업으로 되돌린 뒤 (thenBuild 면) 저절로 다시. */
    static DistrictJob recover(VillageModule m, DistrictService svc, DistrictLibrary.Entry e, boolean thenBuild) {
        DistrictJob j = new DistrictJob(m, Bukkit.getConsoleSender(), svc, e, Mode.RECOVER, true,
                configSites(e, m.districtConfig().sites()));
        j.buildAfterRecover = thenBuild;
        return j;
    }

    static DistrictJob command(VillageModule m, CommandSender s, DistrictService svc, DistrictLibrary.Entry e, Mode mode, List<SiteReq> sites) {
        return new DistrictJob(m, s, svc, e, mode, false, sites);
    }

    static List<SiteReq> configSites(DistrictLibrary.Entry e, List<String> ids) {
        List<SiteReq> out = new ArrayList<>();
        for (String id : ids) {
            DistrictLayout.Site s = e.layout().site(id);
            if (s != null) out.add(SiteReq.of(s));
            else Log.warn("[광산 마을] config mine.district.sites 의 '" + id + "' 는 없는 자리입니다 (" + String.join("·", e.layout().siteIds()) + ")");
        }
        if (out.isEmpty()) for (DistrictLayout.Site s : e.layout().sites) out.add(SiteReq.of(s));
        return out;
    }

    @Override
    protected int blocksPerTick() { return Math.max(200, module.districtConfig().blocksPerTick()); }

    @Override
    protected void begin() {
        if (mode == Mode.REMOVE || mode == Mode.RECOVER) {
            File bf = DistrictService.backupFile(world, L.id);
            say("<#c9a2ff>" + title + "</#c9a2ff> <gray>— 백업 " + bf.getName());
            step = Step.RESTORE_LOAD;
            ioFuture = async().submit(() -> {
                backup = DistrictBackup.load(bf);
                return null;
            });
            return;
        }
        say("<#c9a2ff>" + title + " 시작</#c9a2ff> <gray>— 자리 " + String.join(" → ", sites.stream().map(SiteReq::label).toList())
                + (mode == Mode.PREVIEW ? " · 블록을 바꾸지 않습니다" : ""));
        step = Step.NEXT_SITE;
    }

    @Override
    protected String status() {
        return switch (step) {
            case RESTORE_LOAD -> "백업 읽는 중";
            case RESTORE_PUMP, SCAN -> "청크 " + (pump == null ? 0 : pump.done) + "/" + (pump == null ? 0 : pump.total);
            case RESTORE -> "되돌리기 " + pct(backup == null || backup.entries.isEmpty() ? 1 : (double) cursor / backup.entries.size());
            case NEXT_SITE, PLAN -> "계획 세우는 중 (" + (site == null ? "-" : site.label()) + ")";
            case CHECK, ENTITIES -> "자리 살펴보는 중 (" + site.label() + ")";
            case TREES -> "나무 찾는 중";
            case BACKUP_READ -> "백업 " + pct(cells == null || cells.length == 0 ? 1 : (double) cursor / cells.length);
            case BACKUP_SAVE, DIFF_SAVE -> "백업 저장";
            case CLEAR -> "나무 치우기 " + pct(clear.isEmpty() ? 1 : (double) cursor / (clear.size() + regrass.size()));
            case TERRAIN -> "지형 다듬기 " + pct((double) cursor / ((long) plan.gn * plan.gn));
            case PIECES -> "건물 " + (cursor + 1) + "/" + plan.pieces.size();
            case PATHS -> "길 " + (cursor + 1) + "/" + plan.paths.size();
            case POST, FINISH -> "마무리";
            case DIFF_READ -> "바뀐 칸 기록 " + pct(before.isEmpty() ? 1 : (double) cursor / before.size());
        };
    }

    @Override
    protected boolean tick(Budget b) throws Exception {
        switch (step) {
            case RESTORE_LOAD -> {
                if (!ioFuture.isDone()) return false;
                try {
                    ioFuture.get();
                } catch (java.util.concurrent.ExecutionException ex) {
                    Text.error(sender, "백업을 읽지 못했습니다: " + Text.escape(String.valueOf(ex.getCause())) + " — 아무것도 바꾸지 않았습니다");
                    Log.error("[광산 마을] 백업 읽기 실패", ex.getCause());
                    return true;
                }
                int[] bb = backup.bounds();
                if (bb == null) {
                    step = Step.RESTORE;
                    return false;
                }
                // 되돌리는 동안 그 자리 사람은 광장으로
                DistrictMeta d = svc.get(L.id);
                if (d != null) for (Player p : world.getPlayers()) if (insideBox(p.getLocation(), bb, 2)) svc.evict(p, d);
                pump = new Scan.ChunkPump(world, module.plugin(), false, true, 12, c -> { }).area(bb[0], bb[1], bb[2], bb[3]);
                step = Step.RESTORE_PUMP;
            }
            case RESTORE_PUMP -> {
                pump.pump();
                if (pump.finished()) {
                    step = Step.RESTORE;
                    cursor = 0;
                }
            }
            case RESTORE -> {
                if (restore(b)) return afterRestore();
            }
            case NEXT_SITE -> {
                releasePump();
                siteIdx++;
                if (siteIdx >= sites.size()) return allBlocked();
                startSite(sites.get(siteIdx));
            }
            case SCAN -> {
                pump.pump();
                if (pump.finished() && pending.get() == 0) {
                    step = Step.PLAN;
                    planFuture = async().submit(() -> planner.plan(grid, placement.ox(), placement.oz(), 0, true));
                }
            }
            case PLAN -> {
                if (!planFuture.isDone()) return false;
                plan = planFuture.get();
                if (plan == null || !plan.ok()) {
                    block("계획: " + (plan == null ? "계획 없음" : Planner.label(plan.fail) + " — " + plan.reason));
                    return false;
                }
                writer = new PlanWriter(world, plan, grid, placement.layout().pathStyles, L.foundationMix);
                step = Step.CHECK;
                DistrictFingerprint.World fpw = entry.fp() == null ? null : entry.fp().forBuild(svc.villageBuildId());
                int under = entry.fp() == null ? 10 : entry.fp().under, above = entry.fp() == null ? 30 : entry.fp().above;
                DistrictCheck.Live live = live();
                List<int[]> cols = regionColumns();
                checkFuture = async().submit(() -> DistrictCheck.check(fpw, under, above, live, cols, 20));
            }
            case CHECK -> {
                if (!checkFuture.isDone()) return false;
                check = checkFuture.get();
                if (!check.ok()) {
                    List<String> why = new ArrayList<>();
                    for (DistrictCheck.Problem p : check.problems()) why.add(p.line());
                    block(why);
                    return false;
                }
                step = Step.ENTITIES;
            }
            case ENTITIES -> {
                List<String> why = entities();
                if (!why.isEmpty()) {
                    block(why);
                    return false;
                }
                if (mode == Mode.PREVIEW) {
                    previews.add(site.label() + ": <#7fe07f>지을 수 있음</#7fe07f> — " + summary());
                    report();
                    return true;
                }
                step = Step.TREES;
                treeFuture = async().submit(() -> Trees.analyze(snaps, grid, plan.cx, plan.cz, planner.reach(), writer::tidy));
            }
            case TREES -> {
                if (!treeFuture.isDone()) return false;
                Trees.Result t = treeFuture.get();
                clear = new ArrayList<>();
                for (long[] c : t.remove()) if (!frozen.untouchable((int) c[0], (int) c[2])) clear.add(c);
                regrass = new ArrayList<>();
                for (long[] c : t.regrass()) if (!frozen.untouchable((int) c[0], (int) c[2])) regrass.add(c);
                snaps = null;
                cells = backupCells();
                cursor = 0;
                step = Step.BACKUP_READ;
                say("<gray>  " + site.label() + ": 통과 — " + summary() + " · 나무 원목 " + t.logs() + " · 백업할 칸 " + cells.length);
            }
            case BACKUP_READ -> {
                int minY = world.getMinHeight(), maxY = world.getMaxHeight() - 1;
                while (cursor < cells.length && b.timeLeft()) {
                    long k = cells[cursor++];
                    int x = Trees.ux(k), y = Trees.uy(k), z = Trees.uz(k);
                    if (y < minY || y > maxY) continue;
                    before.add(new DistrictBackup.Entry(x, y, z, world.getBlockAt(x, y, z).getBlockData().getAsString(), null));
                }
                if (cursor >= cells.length) {
                    DistrictBackup bk = new DistrictBackup(L.id, DistrictBackup.Phase.BEFORE, before);
                    File bf = DistrictService.backupFile(world, L.id);
                    ioFuture = async().submit(() -> {
                        bk.save(bf);
                        return null;
                    });
                    step = Step.BACKUP_SAVE;
                }
            }
            case BACKUP_SAVE -> {
                if (!ioFuture.isDone()) return false;
                try {
                    ioFuture.get();
                } catch (java.util.concurrent.ExecutionException ex) {
                    Text.error(sender, "백업을 쓰지 못해 짓지 않았습니다: " + Text.escape(String.valueOf(ex.getCause())) + " (아무것도 바꾸지 않았습니다)");
                    Log.error("[광산 마을] 백업 저장 실패 — 짓지 않음", ex.getCause());
                    return true;
                }
                startWriting();
                step = Step.CLEAR;
                cursor = 0;
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
                    if (blk.getRelative(0, 1, 0).getType().isAir()) writer.set(blk, "minecraft:grass_block[snowy=false]", b);
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
                step = Step.DIFF_READ;
                cursor = 0;
            }
            case DIFF_READ -> {
                while (cursor < before.size() && b.timeLeft()) {
                    DistrictBackup.Entry e = before.get(cursor++);
                    String now = world.getBlockAt(e.x(), e.y(), e.z()).getBlockData().getAsString();
                    if (!now.equals(e.before())) diff.add(new DistrictBackup.Entry(e.x(), e.y(), e.z(), e.before(), now));
                }
                if (cursor >= before.size()) {
                    DistrictBackup bk = new DistrictBackup(L.id, DistrictBackup.Phase.DIFF, diff);
                    File bf = DistrictService.backupFile(world, L.id);
                    ioFuture = async().submit(() -> {
                        bk.save(bf);
                        return null;
                    });
                    step = Step.DIFF_SAVE;
                }
            }
            case DIFF_SAVE -> {
                if (!ioFuture.isDone()) return false;
                try {
                    ioFuture.get();
                } catch (java.util.concurrent.ExecutionException ex) {
                    // 짓기 전 백업(BEFORE)이 그대로 남아 있으니 되돌리기는 된다 — 지은 것은 그대로 둔다
                    Log.error("[광산 마을] 바뀐 칸 백업 저장 실패 (짓기 전 백업으로 되돌릴 수 있음)", ex.getCause());
                }
                step = Step.FINISH;
            }
            case FINISH -> {
                finishBuild();
                return true;
            }
        }
        return false;
    }

    // ── 자리 ─────────────────────────────────────────────────────────────

    private void startSite(SiteReq r) {
        site = r;
        VillageMeta v = module.service().meta();
        Map<String, List<Blueprint.Weighted>> styles = module.library() != null && module.library().ok() ? module.library().layout.pathStyles : Map.of();
        if (r.site() != null) {
            int turns = Rot.turns(org.bukkit.block.structure.StructureRotation.valueOf(v.rotation));
            placement = L.place(r.site(), v.center[0], v.center[2], turns, styles, entry.pieces());
        } else {
            placement = L.placeHere(r.jx(), r.jz(), r.dir(), styles, entry.pieces());
        }
        frozen = FrozenCells.of(v, svc.othersBuilt(L.id));
        Planner.Mask mask = new Planner.Mask(L.r, L.b, frozen, L.maxFill, L.foundationDepth, L.smallWater);
        planner = new Planner(placement.layout(), entry.pieces(), mask);
        int reach = planner.scanReach();
        grid = TerrainGrid.around(placement.ox(), placement.oz(), reach);
        snaps = new Scan.Snapshots(world);
        int minY = world.getMinHeight(), maxY = world.getMaxHeight() - 1;
        Scan.Snapshots sn = snaps;
        TerrainGrid g = grid;
        pump = new Scan.ChunkPump(world, module.plugin(), true, true, 12, chunk -> {
            ChunkSnapshot snap = chunk.getChunkSnapshot(true, true, false, false);
            sn.map.put(Scan.key(chunk.getX(), chunk.getZ()), snap);
            pending.incrementAndGet();
            async().execute(() -> {
                try {
                    Scan.columns(snap, g, minY, maxY);
                } finally {
                    pending.decrementAndGet();
                }
            });
        }).area(placement.ox() - reach, placement.oz() - reach, placement.ox() + reach, placement.oz() + reach);
        step = Step.SCAN;
    }

    private void block(String why) { block(List.of(why)); }

    private void block(List<String> why) {
        blocked.put(site.label(), new ArrayList<>(why));
        String first = why.isEmpty() ? "-" : why.get(0);
        say("<gray>  " + Text.escape(site.label()) + ": <#ff9a4d>막힘</#ff9a4d> — " + Text.escape(first) + (why.size() > 1 ? " 외 " + (why.size() - 1) + "건" : ""));
        if (mode == Mode.PREVIEW) previews.add(site.label() + ": <#ff9a4d>막힘</#ff9a4d> — " + Text.escape(String.join(" · ", why.subList(0, Math.min(5, why.size())))));
        step = Step.NEXT_SITE;
    }

    private boolean allBlocked() {
        if (mode == Mode.PREVIEW) {
            report();
            return true;
        }
        List<String> lines = new ArrayList<>();
        for (Map.Entry<String, List<String>> e : blocked.entrySet()) for (String w : e.getValue()) if (lines.size() < 40) lines.add("[" + e.getKey() + "] " + w);
        String head = "모든 자리 (" + String.join(" · ", blocked.keySet()) + ") 에 사람이 만든 것으로 보이는 것이 있어 블록을 하나도 바꾸지 않았습니다.";
        svc.writeBlocked(L.id, List.of(head), lines);
        Text.send(sender, "<#ff9a4d><b>[광산 마을] 짓지 않았습니다</b></#ff9a4d> <gray>— " + Text.escape(head));
        Text.send(sender, "<gray>  자세히: plugins/Labyrinth/village/" + svc.blockedFile(L.id).getName() + " · 광산은 /미궁 광산 으로 그대로 됩니다");
        if (!(sender instanceof org.bukkit.command.ConsoleCommandSender)) Log.info("[광산 마을] 짓지 않았습니다 — " + head);
        return true;
    }

    private void report() {
        Text.send(sender, "<#e8c58a><b>광산 마을 미리 보기</b></#e8c58a> <gray>(" + elapsedSec() + "초 · 블록을 바꾸지 않았습니다)");
        for (String p : previews) Text.send(sender, "<gray>  " + p);
        if (!sites.isEmpty() && entry.fp() != null && entry.fp().forBuild(svc.villageBuildId()) == null) {
            Text.send(sender, "<gray>  이 월드는 서버팩 월드가 아니어서 지문 없이 '사람이 놓은 블록'만 살폈습니다 — 짓기 전에 그 자리를 직접 둘러보세요.");
        }
    }

    private String summary() {
        int pathCells = plan.paths.stream().mapToInt(p -> p.cells.size()).sum();
        return "깎기 " + plan.cut + " · 메우기 " + plan.fill + " · 조각 " + plan.pieces.size() + " · 길 칸 " + pathCells + " · 마을 길 이음 " + plan.junctions
                + (check == null ? "" : " · 지문 같음 " + check.same() + " · 허용 " + check.allowed() + " · 지문 없음 " + check.uncovered())
                + (plan.skipped.isEmpty() ? "" : " · 장식 생략 " + plan.skipped.size());
    }

    // ── 검사 재료 ─────────────────────────────────────────────────────────

    private DistrictCheck.Live live() {
        TerrainGrid g = grid;
        Scan.Snapshots s = snaps;
        return new DistrictCheck.Live() {
            @Override
            public boolean has(int x, int z) { return g.has(x, z); }

            @Override
            public int ground(int x, int z) { return g.ground(x, z); }

            @Override
            public String block(int x, int y, int z) {
                Material m = s.type(x, y, z);
                return m == null ? "void" : Scan.id(m);
            }

            @Override
            public int flags(int x, int z) { return g.flags(x, z); }

            @Override
            public String note(int x, int z) { return g.note(x, z); }
        };
    }

    /** 계획이 손댈 수 있는 열 (영역 안, 얼린 칸 아님). */
    private List<int[]> regionColumns() {
        List<int[]> out = new ArrayList<>();
        for (int lz = 0; lz < plan.gn; lz++) {
            for (int lx = 0; lx < plan.gn; lx++) {
                int x = plan.gx0 + lx, z = plan.gz0 + lz;
                if (plan.inRegion(x, z) && !plan.isFrozen(x, z)) out.add(new int[] {x, z});
            }
        }
        return out;
    }

    /** 엔티티 검사 (메인 스레드): 사람 손 엔티티 → 막음. 조각 상자 안의 그냥 동물은 밖으로, 적대 몹은 치운다 (짓기 시작할 때). */
    private List<String> entities() {
        List<String> out = new ArrayList<>();
        moveOut.clear();
        int x0 = plan.gx0, z0 = plan.gz0, x1 = plan.gx0 + plan.gn, z1 = plan.gz0 + plan.gn;
        BoundingBox box = new BoundingBox(x0, world.getMinHeight(), z0, x1, world.getMaxHeight(), z1);
        for (Entity en : world.getNearbyEntities(box)) {
            if (en instanceof Player) continue;
            Location l = en.getLocation();
            int bx = l.getBlockX(), bz = l.getBlockZ();
            if (!plan.inRegion(bx, bz) || plan.isFrozen(bx, bz)) continue;
            boolean tagged = WildService.pluginTagged(en) || module.services().npcs().npcIdOf(en).isPresent();
            boolean named = en.customName() != null;
            boolean tamed = en instanceof Tameable t && t.isTamed();
            boolean leashed = en instanceof LivingEntity le && le.isLeashed();
            String why = DistrictCheck.entityBlocks(en.getType().name(), named && en instanceof LivingEntity, tamed, leashed, tagged);
            if (why != null) {
                if (out.size() < 20) out.add(why + " (" + bx + " " + l.getBlockY() + " " + bz + ")");
                continue;
            }
            if (tagged || !(en instanceof LivingEntity)) continue;
            if (inPiece(bx, bz, 2)) moveOut.add(en);
        }
        return out;
    }

    private boolean inPiece(int x, int z, int pad) {
        for (Plan.Placed pl : plan.pieces) {
            if (x >= pl.x0 - pad && x < pl.x0 + pl.w2 + pad && z >= pl.z0 - pad && z < pl.z0 + pl.d2 + pad) return true;
        }
        return false;
    }

    /** 바꿀 수 있는 모든 칸 (지형·조각·길 + 나무), 겹치지 않게. */
    private long[] backupCells() {
        List<Long> list = new ArrayList<>(1 << 16);
        writer.positions(list::add);
        for (long[] c : clear) list.add(Trees.pack((int) c[0], (int) c[1], (int) c[2]));
        for (long[] c : regrass) list.add(Trees.pack((int) c[0], (int) c[1], (int) c[2]));
        long[] a = new long[list.size()];
        for (int i = 0; i < a.length; i++) a[i] = list.get(i);
        Arrays.sort(a);
        int n = 0;
        for (int i = 0; i < a.length; i++) if (i == 0 || a[i] != a[i - 1]) a[n++] = a[i];
        return Arrays.copyOf(a, n);
    }

    // ── 짓기 ─────────────────────────────────────────────────────────────

    /** 백업이 디스크에 있다 → 기록 state: building (보호 켬) → 사람·동물 내보내기. */
    private void startWriting() throws Exception {
        writeStarted = System.currentTimeMillis();
        VillageMeta v = module.service().meta();
        meta = new DistrictMeta();
        meta.id = L.id;
        meta.name = L.name;
        meta.state = DistrictMeta.State.BUILDING;
        meta.site = site.label();
        meta.villageBuildId = v.buildId;
        meta.backup = DistrictMeta.backupName(L.id);
        meta.safeMargin = L.safeMargin;
        meta.meta = Markers.meta(plan, placement.layout());
        meta.meta.name = L.name;
        meta.meta.buildId = UUID.randomUUID().toString();
        meta.meta.builtAt = java.time.Instant.now().toString();
        meta.meta.pluginVersion = module.plugin().getPluginMeta().getVersion();
        VillageMeta.TerrainRec tr = meta.meta.terrain;
        if (tr != null) {
            for (int z = tr.z0(); z < tr.z0() + tr.n(); z++) {
                for (int x = tr.x0(); x < tr.x0() + tr.n(); x++) {
                    if (plan.inRegion(x, z) && !plan.isFrozen(x, z)) meta.region.set((z - tr.z0()) * tr.n() + (x - tr.x0()));
                }
            }
        }
        meta.save(DistrictService.metaFile(world, L.id));
        svc.load(false); // 보호 상자 켬 (짓는 동안 놓기·부수기 취소)
        int[] bb = DistrictService.bounds(meta.meta.protect, 2);
        int moved = 0;
        for (Player p : world.getPlayers()) {
            if (bb != null && insideBox(p.getLocation(), bb, 0)) {
                svc.evict(p, meta);
                moved++;
            }
        }
        int animals = 0, hostiles = 0;
        for (Entity en : moveOut) {
            if (!en.isValid()) continue;
            if (en instanceof Enemy) {
                en.remove();
                hostiles++;
                continue;
            }
            Location out = outside(en.getLocation());
            if (out != null) {
                en.teleport(out);
                animals++;
            }
        }
        say("<gray>  짓기 시작 (백업 " + before.size() + "칸 저장 · 기록 state: building)" + (moved > 0 ? " · 광장으로 옮긴 사람 " + moved : "")
                + (animals > 0 ? " · 옮긴 동물 " + animals : "") + (hostiles > 0 ? " · 치운 몹 " + hostiles : ""));
    }

    /** 조각 상자 밖으로: 그 자리에서 가까운 영역 가장자리 쪽 땅 위. */
    private Location outside(Location from) {
        int x = from.getBlockX(), z = from.getBlockZ();
        for (int r = 3; r <= 24; r++) {
            for (int[] d : new int[][] {{r, 0}, {-r, 0}, {0, r}, {0, -r}}) {
                int qx = x + d[0], qz = z + d[1];
                if (!grid.has(qx, qz) || inPiece(qx, qz, 2) || !plan.inGrid(qx, qz)) continue;
                if (plan.isFrozen(qx, qz)) continue;
                int t = plan.target(qx, qz);
                if (t == HeightField.NONE) t = grid.ground(qx, qz);
                return new Location(world, qx + 0.5, t + 1, qz + 0.5, from.getYaw(), 0f);
            }
        }
        return null;
    }

    private static boolean insideBox(Location l, int[] b, int pad) {
        return l.getX() >= b[0] - pad && l.getX() <= b[2] + 1 + pad && l.getZ() >= b[1] - pad && l.getZ() <= b[3] + 1 + pad;
    }

    private void finishBuild() throws Exception {
        meta.meta.npcs.replaceAll((k, p) -> PlanWriter.standable(world, p));
        meta.meta.points.replaceAll((k, p) -> PlanWriter.standable(world, p));
        meta.state = DistrictMeta.State.BUILT;
        meta.save(DistrictService.metaFile(world, L.id));
        svc.load(true);
        int npcs = svc.applyNpcs(true);
        svc.clearBlocked(L.id);
        long secs = (System.currentTimeMillis() - writeStarted + 999) / 1000;
        String line = "[광산 마을] 지었습니다 — 자리 " + site.label() + " · " + elapsedSec() + "초 (블록 쓰기 " + secs + "초) · 바꾼 블록 " + diff.size()
                + " · NPC " + npcs + "/" + meta.meta.npcs.size() + (writer.errors > 0 ? " · 문제 " + writer.errors + "건" : "");
        Text.send(sender, "<#7fe07f><b>" + Text.escape(line) + "</b></#7fe07f>");
        if (!(sender instanceof org.bukkit.command.ConsoleCommandSender)) Log.info(line);
        Text.send(sender, "<gray>  되돌리기: <white>/labadmin village district remove " + L.id + "</white> (백업 " + DistrictMeta.backupName(L.id)
                + ") · 확인: <white>/labadmin village selftest</white>");
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.getWorld().equals(world)) Text.send(p, "<#e8c58a>[광산 마을]</#e8c58a> <gray>마을 큰길 동쪽 끝에 광산 마을이 생겼습니다. 승강장에서 광산으로 내려갈 수 있습니다.");
        }
    }

    // ── 되돌리기 ─────────────────────────────────────────────────────────

    /** @return 다 되돌렸으면 true */
    private boolean restore(Budget b) {
        if (backup == null) return true;
        Map<String, BlockData> cache = new java.util.HashMap<>();
        while (cursor < backup.entries.size() && b.more()) {
            DistrictBackup.Entry e = backup.entries.get(cursor++);
            if (!restoreSeen.add(e.key())) continue;
            Block blk = world.getBlockAt(e.x(), e.y(), e.z());
            String now = blk.getBlockData().getAsString();
            switch (backup.decide(e, now)) {
                case SAME -> restoreSame++;
                case SKIP -> restoreSkipped++;
                case APPLY -> {
                    try {
                        BlockData d = cache.computeIfAbsent(e.before(), Bukkit::createBlockData);
                        blk.setBlockData(d, false);
                        b.use(1);
                        restored++;
                    } catch (IllegalArgumentException ex) {
                        restoreErrors++;
                    }
                }
            }
        }
        return cursor >= backup.entries.size();
    }

    private boolean afterRestore() throws Exception {
        releasePump();
        DistrictMeta d = svc.get(L.id);
        String counts = "되돌린 블록 " + restored + " · 이미 같던 칸 " + restoreSame + (restoreSkipped > 0 ? " · 그 뒤 바뀌어 그대로 둔 칸 " + restoreSkipped : "")
                + (restoreErrors > 0 ? " · 오류 " + restoreErrors : "");
        if (mode == Mode.REMOVE) {
            if (d != null) {
                svc.removeNpcs(d);
                d.state = DistrictMeta.State.REMOVED;
                d.save(DistrictService.metaFile(world, L.id));
            }
            svc.load(true);
            Text.send(sender, "<#7fe07f><b>광산 마을을 지웠습니다</b></#7fe07f> <gray>(" + counts + " · " + elapsedSec() + "초)");
            Text.send(sender, "<gray>  기록은 state: removed 로 남아 저절로 다시 짓지 않습니다. 다시 지으려면 <white>/labadmin village district build " + L.id + "</white>");
            Log.info("[광산 마을] 지웠습니다 — " + counts);
            return true;
        }
        // RECOVER: 기록·백업을 버리고 처음부터
        if (d != null) svc.removeNpcs(d);
        File mf = DistrictService.metaFile(world, L.id), bf = DistrictService.backupFile(world, L.id);
        if (mf.isFile() && !mf.delete()) Log.warn("[광산 마을] " + mf + " 를 지우지 못했습니다");
        if (bf.isFile() && !bf.delete()) Log.warn("[광산 마을] " + bf + " 를 지우지 못했습니다");
        svc.load(true);
        Log.info("[광산 마을] 짓다가 멈춘 것을 되돌렸습니다 — " + counts);
        if (!buildAfterRecover) return true;
        backup = null;
        before.clear();
        restoreSeen.clear();
        say("<gray>  처음부터 다시 짓습니다");
        siteIdx = -1;
        step = Step.NEXT_SITE;
        return false;
    }

    private void releasePump() {
        if (pump != null) pump.release();
        pump = null;
    }

    @Override
    protected void cleanup() {
        releasePump();
        snaps = null;
    }
}
