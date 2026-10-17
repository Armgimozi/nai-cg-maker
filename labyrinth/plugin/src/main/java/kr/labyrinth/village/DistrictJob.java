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
 * 구역 짓기·미리 보기·되돌리기 (0.3.6.1 광산 마을 · 0.3.7 집 구역, CONTRACT §2.13). 틱 분할 (VillageJob — 한 번에 하나).
 * 글·설정은 구역마다 (이름 = 청사진 name, 설정 = mine.district · homes.district).
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
    /** 계획에서 뽑은 기록(보호 상자·자리·우클릭) — 경계 검사·짓기 직전 보호·기록 파일이 같이 쓴다. */
    private VillageMeta pmeta;
    /** 블록을 쓰는 중 (state building 을 쓴 뒤 ~ built 를 쓰기 전) · 되돌리는 중 · 다 끝남. */
    private volatile boolean writing, restoring;
    private boolean done;
    /** 짓기 직전 그 자리가 바뀌어 다시 살펴본 횟수. */
    private int rescans;
    private int treeOutside;
    /** 막힌 자리 가운데 경계가 아닌 이유(사람 손)로 막힌 것이 있나. */
    private boolean anyNonBorder;
    private DistrictFingerprint.World fpw;
    private int fpUnder = 10, fpAbove = 30;

    static final int MIN_BLOCKS_PER_TICK = 200;
    /** 나무 치우기: 원목이 검사한 영역에서 이보다 멀리 이어지면 막음 (원목 건물·사람이 키운 나무일 수 있다). */
    static final int LOG_REACH = 6;
    /** 영역에서 이보다 먼 잎·붙은 것은 치우지 않는다 (남는 원목이 없으면 저절로 떨어진다). */
    static final int LEAF_REACH = 6;

    private DistrictJob(VillageModule module, CommandSender sender, DistrictService svc, DistrictLibrary.Entry entry, Mode mode, boolean auto,
                        List<SiteReq> sites) {
        super(module, sender, entry.layout().name + switch (mode) {
            case BUILD -> " 짓기";
            case PREVIEW -> " 미리 보기";
            case REMOVE -> " 되돌리기";
            case RECOVER -> " 되돌린 뒤 다시 짓기";
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
                configSites(e, m.districtConfig(e.id()).sites()));
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
            else Log.warn("[" + e.layout().name + "] config " + e.id() + ".district.sites 의 '" + id + "' 는 없는 자리입니다 (" + String.join("·", e.layout().siteIds()) + ")");
        }
        if (out.isEmpty()) for (DistrictLayout.Site s : e.layout().sites) out.add(SiteReq.of(s));
        return out;
    }

    static int blocksPerTick(int configured) { return Math.max(MIN_BLOCKS_PER_TICK, configured); }

    @Override
    protected int blocksPerTick() { return blocksPerTick(module.districtConfig(L.id).blocksPerTick()); }

    private String tag() { return "[" + L.name + "]"; }

    /** 이 구역의 블록을 지금 쓰거나 되돌리는 중인가 (짓는 동안 사람 밀어내기). */
    boolean busy(String id) { return L.id.equals(id) && (writing || restoring); }

    boolean restoring() { return restoring; }

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
                    String why = ex.getCause() instanceof java.nio.file.NoSuchFileException ? "백업 파일이 없습니다" : "백업을 읽지 못했습니다: " + ex.getCause();
                    Text.error(sender, Text.escape(why) + " — 아무것도 바꾸지 않았습니다. 블록을 그대로 두고 기록만 지우려면 <white>/labadmin village district remove "
                            + L.id + " force</white>");
                    Log.error(tag() + " 백업 읽기 실패 (" + why + ")", ex.getCause() instanceof java.nio.file.NoSuchFileException ? null : ex.getCause());
                    if (mode == Mode.RECOVER) {
                        svc.writeBlocked(L.id, DistrictService.Blocked.BACKUP, List.of("짓다가 멈춘 " + L.name + " 기록(state: building)이 있는데 " + why
                                + " — 반쯤 지은 블록을 되돌리지 못했습니다. 그 자리는 보호만 켜져 있습니다 (놓기·부수기 막힘)."), List.of());
                    }
                    return true;
                }
                int[] bb = backup.bounds();
                if (bb == null) {
                    step = Step.RESTORE;
                    return false;
                }
                // 되돌리는 동안 그 자리 사람은 광장으로
                DistrictMeta d = svc.get(L.id);
                restoring = true;
                if (d != null) for (Player p : world.getPlayers()) if (insideBox(p.getLocation(), bb, 2)) svc.evict(p, d, true);
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
                pmeta = Markers.meta(plan, placement.layout());
                String border = svc.outsideBorder(pmeta);
                if (border != null) {
                    blockBorder(border);
                    return false;
                }
                step = Step.CHECK;
                fpw = entry.fp() == null ? null : entry.fp().forBuild(svc.villageBuildId());
                fpUnder = entry.fp() == null ? 10 : entry.fp().under;
                fpAbove = entry.fp() == null ? 30 : entry.fp().above;
                DistrictFingerprint.World fw = fpw;
                int under = fpUnder, above = fpAbove;
                DistrictCheck.Live live = live();
                List<int[]> cols = regionColumns();
                List<int[]> joins = junctionCells();
                checkFuture = async().submit(() -> {
                    DistrictCheck.Result r = DistrictCheck.check(fw, under, above, live, cols, 20);
                    List<DistrictCheck.Problem> j = DistrictCheck.junction(fw, under, above, live, joins, 10);
                    if (j.isEmpty()) return r;
                    List<DistrictCheck.Problem> all = new ArrayList<>(r.problems());
                    all.addAll(j);
                    return new DistrictCheck.Result(r.checked() + joins.size(), r.same(), r.allowed(), r.uncovered(), all);
                });
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
                // 지금부터 블록을 쓰기 시작할 때까지 그 자리 놓기·부수기를 막는다 (기록 파일 없이 — 몇 초)
                int[] pb = DistrictService.bounds(pmeta.protect, 2);
                if (pb != null) svc.setPending(new VillageMeta.Box(pb[0], world.getMinHeight(), pb[1], pb[2], world.getMaxHeight(), pb[3]));
                step = Step.TREES;
                treeFuture = async().submit(() -> Trees.analyze(snaps, grid, plan.cx, plan.cz, planner.reach(), writer::tidy));
            }
            case TREES -> {
                if (!treeFuture.isDone()) return false;
                Trees.Result t = treeFuture.get();
                if (!treeClear(t)) return false;
                cells = backupCells();
                cursor = 0;
                step = Step.BACKUP_READ;
                say("<gray>  " + site.label() + ": 통과 — " + summary() + " · 나무 원목 " + t.logs() + (treeOutside > 0 ? " (영역 밖 열 " + treeOutside + " 살핌)" : "")
                        + " · 백업할 칸 " + cells.length);
            }
            case BACKUP_READ -> {
                int minY = world.getMinHeight(), maxY = world.getMaxHeight() - 1;
                while (cursor < cells.length && b.timeLeft()) {
                    long k = cells[cursor++];
                    int x = Trees.ux(k), y = Trees.uy(k), z = Trees.uz(k);
                    if (y < minY || y > maxY) continue;
                    BlockData now = world.getBlockAt(x, y, z).getBlockData();
                    // 살펴본 뒤(스냅샷) 사람 손으로 바뀐 칸 → 처음부터 다시 살펴봄
                    Material then = snaps == null ? null : snaps.type(x, y, z);
                    if (then != null && then != now.getMaterial() && handChange(then, now.getMaterial())) {
                        rescan(Scan.id(then) + " → " + Scan.id(now.getMaterial()) + " (" + x + " " + y + " " + z + ")");
                        return false;
                    }
                    before.add(new DistrictBackup.Entry(x, y, z, now.getAsString(), null));
                }
                if (cursor >= cells.length) {
                    snaps = null;
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
                    Log.error(tag() + " 백업 저장 실패 — 짓지 않음", ex.getCause());
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
                    Log.error(tag() + " 바뀐 칸 백업 저장 실패 (짓기 전 백업으로 되돌릴 수 있음)", ex.getCause());
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

    private void blockBorder(String why) {
        boolean keep = anyNonBorder;
        block(List.of(why));
        anyNonBorder = keep;
    }

    private void block(List<String> why) {
        anyNonBorder = true;
        if (svc.pending() != null) svc.setPending(null);
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
        String where = String.join(" · ", blocked.keySet());
        DistrictService.Blocked reason = anyNonBorder ? DistrictService.Blocked.PLAYER_MADE : DistrictService.Blocked.BORDER;
        String head = reason == DistrictService.Blocked.BORDER ? "모든 자리 (" + where + ") 가 월드 경계 밖이라 블록을 하나도 바꾸지 않았습니다."
                : "모든 자리 (" + where + ") 에 사람이 만든 것으로 보이는 것이 있거나 지을 수 없어 블록을 하나도 바꾸지 않았습니다.";
        svc.writeBlocked(L.id, reason, List.of(head), lines);
        Text.send(sender, "<#ff9a4d><b>" + Text.escape(tag()) + " 짓지 않았습니다</b></#ff9a4d> <gray>— " + Text.escape(head));
        Text.send(sender, "<gray>  자세히: plugins/Labyrinth/village/" + svc.blockedFile(L.id).getName() + " · " + DistrictService.hint(L.id));
        if (!(sender instanceof org.bukkit.command.ConsoleCommandSender)) Log.info(tag() + " 짓지 않았습니다 — " + head);
        return true;
    }

    private void report() {
        Text.send(sender, "<#e8c58a><b>" + Text.escape(L.name) + " 미리 보기</b></#e8c58a> <gray>(" + elapsedSec() + "초 · 블록을 바꾸지 않았습니다)");
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

    /** 큰길과 만나는 얼린 칸(마을이 다듬은 칸) 위 구역 길 칸 [x, z, y] — 겉 블록을 깔고 위 두 칸을 치우는 칸. */
    private List<int[]> junctionCells() {
        List<int[]> out = new ArrayList<>();
        Set<Long> seen = new HashSet<>();
        for (Plan.PathPlan pp : plan.paths) {
            for (int[] c : pp.cells) {
                if (!plan.isFrozen(c[0], c[1]) || frozen.untouchable(c[0], c[1])) continue;
                if (seen.add(PathRaster.key(c[0], c[1]))) out.add(new int[] {c[0], c[1], c[2]});
            }
        }
        return out;
    }

    /** 검사한 열(영역 안, 얼린 칸 아님)까지의 체비셰프 거리 (0 = 그 열, cap 넘으면 cap + 1). */
    private int regionDistance(int x, int z, int cap) {
        for (int r = 0; r <= cap; r++) {
            for (int dz = -r; dz <= r; dz++) {
                for (int dx = -r; dx <= r; dx++) {
                    if (Math.max(Math.abs(dx), Math.abs(dz)) != r) continue;
                    int qx = x + dx, qz = z + dz;
                    if (plan.inGrid(qx, qz) && plan.inRegion(qx, qz) && !plan.isFrozen(qx, qz)) return r;
                }
            }
        }
        return cap + 1;
    }

    /**
     * 나무 치우기 칸 고르기 (0.3.6.1 리뷰): 마을 길·보호 칸은 빼고, 검사한 영역 밖으로 뻗은 부분은 —
     * 원목이 {@link #LOG_REACH} 칸 넘게 이어지면 막음 (원목 건물·사람이 키운 나무일 수 있다), 그 안이면 그 열들도 지문·비자연 검사,
     * 영역에서 먼 잎·붙은 것은 남김 (원목이 없으면 저절로 떨어진다). @return 계속하면 true (막았으면 false)
     */
    private boolean treeClear(Trees.Result t) {
        clear = new ArrayList<>();
        regrass = new ArrayList<>();
        Map<Long, int[]> outside = new LinkedHashMap<>();
        for (long[] c : t.remove()) {
            int x = (int) c[0], y = (int) c[1], z = (int) c[2];
            if (frozen.untouchable(x, z)) continue;
            int d = regionDistance(x, z, Math.max(LOG_REACH, LEAF_REACH));
            if (d > 0) {
                Material m = snaps.type(x, y, z);
                boolean log = m != null && Scan.kind(m) == Nature.Kind.LOG;
                if (log && d > LOG_REACH) {
                    block("나무 치우기: 원목이 지을 자리에서 " + LOG_REACH + "칸 넘게 이어짐 — 원목 건물·사람이 키운 나무일 수 있어 짓지 않습니다 ("
                            + (m == null ? "?" : Scan.id(m)) + " " + x + " " + y + " " + z + ")");
                    return false;
                }
                if (!log && d > LEAF_REACH) continue;
                outside.putIfAbsent(PathRaster.key(x, z), new int[] {x, z});
            }
            clear.add(c);
        }
        for (long[] c : t.regrass()) {
            int x = (int) c[0], z = (int) c[2];
            if (frozen.untouchable(x, z)) continue;
            if (regionDistance(x, z, LOG_REACH) > LOG_REACH) continue;
            regrass.add(c);
        }
        if (!outside.isEmpty()) {
            DistrictCheck.Result r = DistrictCheck.check(fpw, fpUnder, fpAbove, live(), outside.values(), 20);
            if (!r.ok()) {
                List<String> why = new ArrayList<>();
                for (DistrictCheck.Problem p : r.problems()) why.add("나무 치우기 (영역 밖): " + p.line());
                block(why);
                return false;
            }
        }
        treeOutside = outside.size();
        return true;
    }

    /** 살펴본 뒤 바뀐 칸이 사람 손인가 (자연 변화 = 잔디↔흙·잎 떨어짐·물 흐름·식물 — 비자연 블록이나 새 원목이 끼면 사람 손). */
    static boolean handChange(Material then, Material now) {
        Nature.Kind a = Scan.kind(then), b = Scan.kind(now);
        return a == Nature.Kind.UNNATURAL || b == Nature.Kind.UNNATURAL || (b == Nature.Kind.LOG && a != Nature.Kind.LOG);
    }

    /** 짓기 직전 그 자리가 바뀜 → 처음부터 다시 살펴봄 (두 번까지, 그다음은 막음). */
    private void rescan(String what) {
        before.clear();
        cursor = 0;
        if (++rescans > 2) {
            block("짓기 직전에 그 자리 블록이 바뀌었습니다 — " + what);
            return;
        }
        say("<gray>  " + site.label() + ": 살펴본 뒤 블록이 바뀌어 다시 살펴봅니다 — " + Text.escape(what));
        if (svc.pending() != null) svc.setPending(null);
        releasePump();
        startSite(site);
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
        meta.meta = pmeta != null ? pmeta : Markers.meta(plan, placement.layout());
        int[] hh = module.homesHeight();
        meta.plots = new ArrayList<>(Markers.plots(plan, hh[0], hh[1])); // 0.3.7 집 구역만 (집터 바닥 조각이 없으면 빈 목록)
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
        writing = true;
        svc.load(false); // 보호 상자 켬 (짓는 동안 놓기·부수기 취소)
        svc.setPending(null); // 잠깐 보호 → 기록의 보호 상자로
        int[] bb = DistrictService.bounds(meta.meta.protect, 2);
        int moved = 0;
        for (Player p : world.getPlayers()) {
            if (bb != null && insideBox(p.getLocation(), bb, 0)) {
                svc.evict(p, meta, false);
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
        meta.plots.replaceAll(r -> {
            VillageMeta.Pos h = PlanWriter.standable(world, new VillageMeta.Pos(r.homeX(), r.homeY(), r.homeZ(), r.homeYaw()));
            return new DistrictMeta.PlotRec(r.id(), r.x0(), r.z0(), r.x1(), r.z1(), r.floor(), r.y0(), r.y1(), r.front(), r.gateX(), r.gateY(), r.gateZ(),
                    r.signX(), r.signY(), r.signZ(), r.homeX(), h.y(), r.homeZ(), r.homeYaw());
        });
        flush("짓기");
        meta.state = DistrictMeta.State.BUILT;
        meta.save(DistrictService.metaFile(world, L.id));
        writing = false;
        done = true;
        svc.load(true);
        int npcs = svc.applyNpcs(true, L.id);
        svc.clearBlocked(L.id);
        long secs = (System.currentTimeMillis() - writeStarted + 999) / 1000;
        String line = tag() + " 지었습니다 — 자리 " + site.label() + " · " + elapsedSec() + "초 (블록 쓰기 " + secs + "초) · 바꾼 블록 " + diff.size()
                + " · NPC " + npcs + "/" + meta.meta.npcs.size() + (meta.plots.isEmpty() ? "" : " · 집터 " + meta.plots.size())
                + (writer.errors > 0 ? " · 문제 " + writer.errors + "건" : "");
        Text.send(sender, "<#7fe07f><b>" + Text.escape(line) + "</b></#7fe07f>");
        if (!(sender instanceof org.bukkit.command.ConsoleCommandSender)) Log.info(line);
        Text.send(sender, "<gray>  되돌리기: <white>/labadmin village district remove " + L.id + "</white> (백업 " + DistrictMeta.backupName(L.id)
                + ") · 확인: <white>/labadmin village selftest</white>");
        String news = builtNews();
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.getWorld().equals(world)) Text.send(p, "<#e8c58a>" + Text.escape(tag()) + "</#e8c58a> <gray>" + news);
        }
    }

    /** 지은 뒤 모두에게 한 줄. */
    private String builtNews() {
        if ("homes".equals(L.id)) return "마을 남쪽에 등불 골목이 생겼습니다. 골목의 관리인에게 집을 받을 수 있습니다.";
        String where = site.site() == null ? "마을 옆에" : site.id().equals("east") ? "마을 큰길 끝에" : "마을 큰길 끝에서 갈라진 길 끝에";
        if ("mine".equals(L.id)) return where + " 광산 마을이 생겼습니다. 승강장에서 광산으로 내려갈 수 있습니다.";
        return where + " " + L.name + DistrictService.subjectParticle(L.name) + " 생겼습니다.";
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
        flush("되돌리기"); // 되돌린 블록을 디스크에 먼저 — 기록이 블록보다 앞서지 않게
        restoring = false;
        if (mode == Mode.REMOVE) {
            done = true;
            if (d != null) {
                svc.removeNpcs(d);
                d.state = DistrictMeta.State.REMOVED;
                d.save(DistrictService.metaFile(world, L.id));
            }
            svc.load(true);
            if ("homes".equals(L.id)) svc.removedHomes();
            Text.send(sender, "<#7fe07f><b>" + Text.escape(L.name) + DistrictService.objectParticle(L.name) + " 지웠습니다</b></#7fe07f> <gray>(" + counts + " · "
                    + elapsedSec() + "초)");
            Text.send(sender, "<gray>  기록은 state: removed 로 남아 저절로 다시 짓지 않습니다. 다시 지으려면 <white>/labadmin village district build " + L.id + "</white>");
            Log.info(tag() + " 지웠습니다 — " + counts);
            return true;
        }
        // RECOVER: 기록·백업을 버리고 처음부터
        if (d != null) svc.removeNpcs(d);
        File mf = DistrictService.metaFile(world, L.id), bf = DistrictService.backupFile(world, L.id);
        if (mf.isFile() && !mf.delete()) Log.warn(tag() + " " + mf + " 를 지우지 못했습니다");
        if (bf.isFile() && !bf.delete()) Log.warn(tag() + " " + bf + " 를 지우지 못했습니다");
        svc.load(true);
        Log.info(tag() + " 짓다가 멈춘 것을 되돌렸습니다 — " + counts);
        if (!buildAfterRecover) return true;
        backup = null;
        before.clear();
        restoreSeen.clear();
        say("<gray>  처음부터 다시 짓습니다");
        siteIdx = -1;
        step = Step.NEXT_SITE;
        return false;
    }

    /** 바꾼 블록을 디스크에 (청크 저장이 끝날 때까지 기다림 — 기록 파일을 블록보다 먼저 쓰지 않게, 0.3.6.1 리뷰). */
    private void flush(String what) {
        long t0 = System.currentTimeMillis();
        try {
            world.save(true);
            say("<gray>  월드 저장 (" + what + ", " + (System.currentTimeMillis() - t0) + "ms)");
        } catch (Throwable t) {
            Log.error(tag() + " 월드 저장 실패 (" + what + ") — 다음 자동 저장 때 저장됩니다", t);
        }
    }

    private void releasePump() {
        if (pump != null) pump.release();
        pump = null;
    }

    @Override
    protected void cleanup() {
        releasePump();
        snaps = null;
        if (svc.pending() != null) svc.setPending(null);
        boolean live = module.plugin().isEnabled();
        if (writing && !done) {
            // 짓다가 멈춤 (취소·오류): 반쯤 지은 채 두지 않고 곧바로 백업으로 되돌린다. 서버를 끄는 중이면 다음 시작 때 (state building).
            writing = false;
            if (!live) return;
            Text.send(sender, "<#ff9a4d>" + Text.escape(tag()) + " 짓기가 멈췄습니다 — 백업으로 되돌립니다</#ff9a4d>");
            Log.warn(tag() + " 짓기가 멈췄습니다 — 백업으로 되돌립니다");
            Bukkit.getScheduler().runTaskLater(module.plugin(), () -> {
                if (VillageJob.running() != null) {
                    Log.warn(tag() + " 다른 마을 작업 중이라 되돌리지 못했습니다 — 다음 시작 때 되돌립니다 (state building)");
                    return;
                }
                DistrictJob.recover(module, svc, entry, false).start();
            }, 1L);
            return;
        }
        if (restoring && !done && mode == Mode.REMOVE && live) {
            Text.send(sender, "<#ff9a4d>" + Text.escape(tag()) + " 되돌리기를 멈췄습니다</#ff9a4d> <gray>— 다시 <white>/labadmin village district remove " + L.id
                    + "</white> 하면 이어서 됩니다");
        }
        restoring = false;
    }
}
