package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Future;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.block.data.Openable;
import org.bukkit.block.data.type.Slab;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Entity;

/**
 * {@code /labadmin village selftest} (VILLAGE.md §0 짓고 나서 검사 · §4.4). 메타데이터를 다시 읽어:
 * 조각 칸이 청사진대로인지(mismatched, '.' 칸 공기 = interior), 조각·길 겹침(overlaps), 다듬은 땅의 뜬 블록·얇은 껍질(floating),
 * 남은 나무 조각(원목·떠 있는 잎 = tree_remnants), 정문 앞 걸어 들어가기(blocked_doors), 길 칸 높이 차(path_steps),
 * NPC 자리, 우클릭 칸·스폰·입구, 회전 규칙 대조(rot_mismatch). 결과 한 줄은 서버 로그에도 남는다.
 */
final class VillageSelfTest extends VillageJob {

    private final World world;
    private VillageMeta meta;
    private final VillageLibrary lib;
    private final List<Plan.Placed> pieces = new ArrayList<>();
    private final List<Plan.PathPlan> paths = new ArrayList<>();
    private final Map<String, BlockData> expected = new HashMap<>();
    private final List<String> samples = new ArrayList<>();
    private int exceptions, rotMismatch;
    private Scan.ChunkPump pump;
    private Scan.Snapshots snaps;
    private Future<Map<String, Integer>> future;
    private Map<String, Integer> counts;
    private int waitTicks;
    private int cx, cz, reach;

    VillageSelfTest(VillageModule module, CommandSender sender, World world) {
        super(module, sender, "마을 자가 진단");
        this.world = world;
        this.lib = module.library();
    }

    private void sample(String s) {
        synchronized (samples) {
            if (samples.size() < 14) samples.add(s);
        }
    }

    private void error(String where, Throwable t) {
        exceptions++;
        sample("예외 " + where + ": " + t);
        Log.error("[마을 자가 진단] " + where + " 예외", t);
    }

    @Override
    protected void begin() {
        try {
            meta = VillageMeta.load(VillageService.metaFile(world));
        } catch (Exception e) {
            error("메타데이터", e);
            return;
        }
        cx = meta.center[0];
        cz = meta.center[2];
        reach = meta.terrain != null ? (meta.terrain.n() - 3) / 2 : meta.radius + meta.blend;
        for (VillageMeta.PieceRec r : meta.pieces) {
            Plan.Placed pl = Markers.placed(r, lib.layout, lib.pieces);
            if (pl == null) {
                exceptions++;
                sample("청사진 없음: " + r.piece());
                continue;
            }
            pieces.add(pl);
            Map<String, String> seen = new HashMap<>();
            for (Map.Entry<Integer, String> e : pl.bp.palette.entrySet()) {
                try {
                    BlockData d = Bukkit.createBlockData(e.getValue()).clone();
                    d.rotate(Rot.of(pl.turns));
                    expected.put(pl.index() + ":" + e.getKey(), d);
                    String key = e.getValue() + "@" + pl.turns;
                    if (seen.put(key, "") == null) {
                        BlockData pure = Bukkit.createBlockData(Rot.rotateState(e.getValue(), pl.turns));
                        if (!pure.getAsString().equals(d.getAsString())) {
                            rotMismatch++;
                            sample("회전 대조: " + e.getValue() + " ×" + pl.turns + " → " + d.getAsString() + " / 문자열 " + pure.getAsString());
                        }
                    }
                } catch (Throwable t) {
                    error("팔레트 " + pl.bp.id + " '" + new String(Character.toChars(e.getKey())) + "'", t);
                }
            }
        }
        for (VillageMeta.PathRec r : meta.paths) paths.add(Markers.path(r));
        snaps = new Scan.Snapshots(world);
        int r = reach + 16;
        pump = new Scan.ChunkPump(world, module.plugin(), false, false, 16, snaps::add).area(cx - r, cz - r, cx + r, cz + r);
        say("<#c9a2ff>마을 자가 진단 시작</#c9a2ff> <gray>— 조각 " + pieces.size() + " · 길 " + paths.size() + " · 청크 " + pump.total);
    }

    @Override
    protected String status() {
        if (meta == null) return null;
        if (future == null) return "청크 " + pump.done + "/" + pump.total;
        return counts == null ? "검사 중" : "NPC 확인";
    }

    @Override
    protected boolean tick(Budget b) throws Exception {
        if (meta == null) {
            report(Map.of(), 0, 0, 0, 0, false, false);
            return true;
        }
        if (future == null) {
            pump.pump();
            if (!pump.finished()) return false;
            future = async().submit(this::analyze);
            return false;
        }
        if (counts == null) {
            if (!future.isDone()) return false;
            counts = future.get();
            snaps = null;
        }
        // NPC 는 NpcService 가 청크 로드 뒤 몇 틱 안에 세운다 → 최대 3초 기다림
        int[] npc = npcs();
        if (npc[0] < npc[1] && waitTicks++ < 60) return false;
        int[] inter = interacts();
        report(counts, npc[0], npc[1], inter[0], inter[1], spawnOk(), entranceOk());
        return true;
    }

    // ── 비동기 검사 (스냅샷) ─────────────────────────────────────────────

    private Map<String, Integer> analyze() {
        Map<String, Integer> c = new HashMap<>();
        int[] ck = new int[3];
        try {
            pieceCells(ck);
        } catch (Throwable t) {
            error("조각 칸", t);
        }
        c.put("checked", ck[0]);
        c.put("mismatched", ck[1]);
        c.put("interior", ck[2]);
        try {
            List<String> ov = Planner.overlaps(pieces, paths);
            for (String s : ov) sample(s);
            c.put("overlaps", ov.size());
        } catch (Throwable t) {
            error("겹침", t);
        }
        Set<Long> foot = new HashSet<>(), pathCols = new HashSet<>();
        for (Plan.Placed pl : pieces) {
            for (int rz = 0; rz < pl.d2; rz++) for (int rx = 0; rx < pl.w2; rx++) {
                if (pl.occupies(pl.x0 + rx, pl.z0 + rz)) foot.add(PathRaster.key(pl.x0 + rx, pl.z0 + rz));
            }
        }
        Map<Long, Integer> pathH = new HashMap<>();
        for (Plan.PathPlan pp : paths) for (int[] cell : pp.cells) {
            pathCols.add(PathRaster.key(cell[0], cell[1]));
            pathH.putIfAbsent(PathRaster.key(cell[0], cell[1]), cell[2]);
        }
        try {
            c.put("floating", floating(foot, pathCols));
        } catch (Throwable t) {
            error("뜬 지형", t);
        }
        try {
            c.put("tree_remnants", trees(foot));
        } catch (Throwable t) {
            error("나무", t);
        }
        try {
            c.put("blocked_doors", doors());
        } catch (Throwable t) {
            error("정문", t);
        }
        try {
            c.put("path_steps", pathSteps(pathH));
        } catch (Throwable t) {
            error("길", t);
        }
        return c;
    }

    private void pieceCells(int[] ck) {
        for (Plan.Placed pl : pieces) {
            Blueprint bp = pl.bp;
            for (int y = 0; y < bp.h; y++) {
                for (int z = 0; z < bp.d; z++) {
                    for (int x = 0; x < bp.w; x++) {
                        int cp = bp.cell(x, y, z);
                        if (cp == Blueprint.KEEP) continue;
                        int[] w = pl.world(x, z);
                        int wy = pl.worldY(y);
                        BlockData actual = snaps.data(w[0], wy, w[1]);
                        if (actual == null) continue;
                        ck[0]++;
                        if (cp == Blueprint.AIR) {
                            if (!actual.getMaterial().isAir()) {
                                ck[1]++;
                                ck[2]++;
                                sample(bp.id + " 실내 '.' 칸에 " + actual.getAsString() + " (" + w[0] + " " + wy + " " + w[1] + ")");
                            }
                            continue;
                        }
                        BlockData exp = expected.get(pl.index() + ":" + cp);
                        if (exp == null) continue;
                        if (!exp.matches(actual)) {
                            ck[1]++;
                            sample(bp.id + " (" + w[0] + " " + wy + " " + w[1] + ") 기대 " + exp.getAsString() + " / 실제 " + actual.getAsString());
                        }
                    }
                }
            }
        }
    }

    private static boolean emptyish(Material m) {
        if (m == null) return false;
        Nature.Kind k = Scan.kind(m);
        return k == Nature.Kind.AIR || k == Nature.Kind.LIQUID;
    }

    /** 다듬은(바뀐) 칸: 맨 윗블록이 있고 그 아래 두 칸이 비지 않았는지, 위 12칸 안에 지형 덩어리가 떠 있지 않은지. */
    private int floating(Set<Long> foot, Set<Long> pathCols) {
        VillageMeta.TerrainRec tr = meta.terrain;
        if (tr == null) return 0;
        int bad = 0;
        for (int z = tr.z0(); z < tr.z0() + tr.n(); z++) {
            for (int x = tr.x0(); x < tr.x0() + tr.n(); x++) {
                if (!tr.changed(x, z) || Math.hypot(x - cx, z - cz) > reach) continue;
                long k = PathRaster.key(x, z);
                if (foot.contains(k)) continue;
                int t = tr.height(x, z);
                Material top = snaps.type(x, t, z);
                if (top == null) continue;
                boolean b = emptyish(top) && !pathCols.contains(k) || emptyish(snaps.type(x, t - 1, z)) || emptyish(snaps.type(x, t - 2, z));
                for (int y = t + 1; y <= t + 12 && !b; y++) {
                    Material m = snaps.type(x, y, z);
                    if (m != null && Scan.kind(m) == Nature.Kind.GROUND) b = true;
                }
                if (b) {
                    bad++;
                    sample("뜬 지형/빈 땅 (" + x + " " + t + " " + z + ") 맨 위 " + top);
                }
            }
        }
        return bad;
    }

    /** 영역 안 자연 원목(조각 발자국 밖) + 원목 없이 떠 있는 자연 잎. */
    private int trees(Set<Long> foot) {
        int logs = 0;
        int minT = Integer.MAX_VALUE, maxT = Integer.MIN_VALUE;
        VillageMeta.TerrainRec tr = meta.terrain;
        for (int z = cz - reach; z <= cz + reach; z++) {
            for (int x = cx - reach; x <= cx + reach; x++) {
                if (Math.hypot(x - cx, z - cz) > reach || foot.contains(PathRaster.key(x, z)) || !snaps.has(x, z)) continue;
                int t = tr != null && tr.in(x, z) ? tr.height(x, z) : snaps.minY;
                minT = Math.min(minT, t);
                maxT = Math.max(maxT, t);
                // 마을이 손댄 열만 (고정 칸 둘레 2칸 + 바뀐 칸) — 그대로인 땅의 나무는 일부러 남김 (VillageBuilder#tidy 와 같은 규칙)
                boolean affected = tr != null && tr.in(x, z) && tr.changed(x, z) || nearFixed(x, z);
                if (!affected) continue;
                int top = snaps.highest(x, z);
                for (int y = t - 1; y <= top; y++) {
                    Material m = snaps.type(x, y, z);
                    if (m != null && Scan.kind(m) == Nature.Kind.LOG && !inPieceBox(x, y, z)) {
                        logs++;
                        sample("남은 원목 " + m + " (" + x + " " + y + " " + z + ")");
                    }
                }
            }
        }
        if (minT == Integer.MAX_VALUE) return logs;
        int r = reach + 8;
        Set<Long> orphan = Trees.orphanLeaves(snaps, cx - r, minT - 4, cz - r, cx + r, maxT + 40, cz + r, Set.of());
        int leaves = 0;
        for (long k : orphan) {
            int x = Trees.ux(k), z = Trees.uz(k);
            if (Math.hypot(x - cx, z - cz) > r) continue;
            leaves++;
            if (leaves <= 3) sample("원목 없는 잎 (" + x + " " + Trees.uy(k) + " " + z + ")");
        }
        return logs + leaves;
    }

    private Set<Long> fixedCols;

    /** 조각 발자국+둘레 1칸, 정문 앞 칸, 길 칸 = 계획기의 고정 칸 (추가 단 제외). 그 둘레 2칸 안인가. */
    private boolean nearFixed(int x, int z) {
        if (fixedCols == null) {
            Set<Long> f = new HashSet<>();
            for (Plan.Placed pl : pieces) {
                for (int rz = -1; rz <= pl.d2; rz++) {
                    for (int rx = -1; rx <= pl.w2; rx++) {
                        int wx = pl.x0 + rx, wz = pl.z0 + rz;
                        boolean near = false;
                        for (int qz = -1; qz <= 1 && !near; qz++) for (int qx = -1; qx <= 1 && !near; qx++) near = pl.occupies(wx + qx, wz + qz);
                        if (near) f.add(PathRaster.key(wx, wz));
                    }
                }
                int[] d = pl.doorFront();
                f.add(PathRaster.key(d[0], d[1]));
            }
            for (Plan.PathPlan pp : paths) for (int[] c : pp.cells) f.add(PathRaster.key(c[0], c[1]));
            fixedCols = f;
        }
        for (int dz = -2; dz <= 2; dz++) for (int dx = -2; dx <= 2; dx++) if (fixedCols.contains(PathRaster.key(x + dx, z + dz))) return true;
        return false;
    }

    /** 메타데이터 보호 상자(조각 상자 +1, 길) 안 — 조각이 일부러 놓은 원목은 나무 조각이 아니다. */
    private boolean inPieceBox(int x, int y, int z) {
        for (VillageMeta.Box b : meta.protect) if (b.contains(x, y, z)) return true;
        return false;
    }

    private boolean passable(int x, int y, int z) {
        Material m = snaps.type(x, y, z);
        if (m == null || m.isAir() || !m.isSolid()) return true;
        BlockData d = snaps.data(x, y, z);
        return d instanceof Openable || (d instanceof Slab s && s.getType() == Slab.Type.BOTTOM);
    }

    private boolean solid(int x, int y, int z) {
        Material m = snaps.type(x, y, z);
        return m != null && !m.isAir() && (m.isSolid() || Scan.kind(m) == Nature.Kind.GROUND) && !(snaps.data(x, y, z) instanceof Openable);
    }

    /** 정문 앞 바깥 칸 땅높이가 조각 바닥과 ±1 이고 그 위 두 칸·안쪽 두 칸이 트였는가. */
    private int doors() {
        int bad = 0;
        for (Plan.Placed pl : pieces) {
            if (!pl.bp.door) continue;
            int[] f = pl.doorFront(), a = pl.anchor();
            int p = pl.floor, oy = Integer.MIN_VALUE;
            for (int y = p + 3; y >= p - 4; y--) {
                if (solid(f[0], y, f[1])) {
                    oy = y;
                    break;
                }
            }
            boolean ok = oy != Integer.MIN_VALUE && Math.abs(oy - p) <= 1 && passable(f[0], oy + 1, f[1]) && passable(f[0], oy + 2, f[1])
                    && passable(a[0], p + 1, a[1]) && passable(a[0], p + 2, a[1]);
            if (!ok) {
                bad++;
                sample(pl.bp.id + " 정문 막힘: 앞 칸 (" + f[0] + ", " + f[1] + ") 땅 " + (oy == Integer.MIN_VALUE ? "없음" : oy) + " / 바닥 " + p);
            }
        }
        return bad;
    }

    /** 길 칸 이웃 걸음 높이 차 (반블록은 0.5). */
    private int pathSteps(Map<Long, Integer> pathH) {
        int bad = 0;
        for (Map.Entry<Long, Integer> e : pathH.entrySet()) {
            long k = e.getKey();
            int x = (int) (k >> 32), z = (int) k;
            double s = surface(x, e.getValue(), z);
            for (int[] d : new int[][] {{1, 0}, {0, 1}}) {
                Integer h = pathH.get(PathRaster.key(x + d[0], z + d[1]));
                if (h == null) continue;
                if (Math.abs(surface(x + d[0], h, z + d[1]) - s) > 1.0) {
                    bad++;
                    sample("길 높이 차 (" + x + ", " + z + ")");
                }
            }
        }
        return bad;
    }

    private double surface(int x, int y, int z) {
        BlockData up = snaps.data(x, y + 1, z);
        return y + 1 + (up instanceof Slab s && s.getType() == Slab.Type.BOTTOM ? 0.5 : 0);
    }

    // ── 메인 스레드 검사 ─────────────────────────────────────────────────

    private int[] npcs() {
        int ok = 0;
        var svc = module.services().npcs();
        Map<String, Location> placed = svc instanceof kr.labyrinth.mobs.npc.NpcServiceImpl impl ? impl.placed() : Map.of();
        for (Map.Entry<String, VillageMeta.Pos> e : meta.npcs.entrySet()) {
            try {
                Location want = new Location(world, e.getValue().x(), e.getValue().y(), e.getValue().z());
                Location at = placed.get(e.getKey());
                if (at == null || at.getWorld() == null || !at.getWorld().equals(world) || at.distanceSquared(want) > 1.0) continue;
                world.getChunkAt(want.getBlockX() >> 4, want.getBlockZ() >> 4);
                boolean live = false;
                for (Entity en : world.getNearbyEntities(want, 1.5, 2.5, 1.5)) {
                    if (svc.npcIdOf(en).map(e.getKey()::equals).orElse(false)) live = true;
                }
                if (live) ok++;
            } catch (Throwable t) {
                error("NPC " + e.getKey(), t);
            }
        }
        return new int[] {ok, meta.npcs.size()};
    }

    private int[] interacts() {
        int ok = 0;
        for (String k : meta.interact.keySet()) {
            String[] a = k.split(",");
            try {
                Block b = world.getBlockAt(Integer.parseInt(a[0]), Integer.parseInt(a[1]), Integer.parseInt(a[2]));
                if (!b.getType().isAir()) ok++;
                else sample("우클릭 칸이 공기: " + k + " (" + meta.interact.get(k) + ")");
            } catch (Throwable t) {
                error("우클릭 칸 " + k, t);
            }
        }
        return new int[] {ok, meta.interact.size()};
    }

    private boolean standOk(VillageMeta.Pos p) {
        if (p == null) return false;
        Block feet = world.getBlockAt((int) Math.floor(p.x()), (int) Math.floor(p.y()), (int) Math.floor(p.z()));
        return feet.isPassable() && feet.getRelative(0, 1, 0).isPassable() && !feet.getRelative(0, -1, 0).isPassable();
    }

    private boolean spawnOk() {
        if (!standOk(meta.spawn)) {
            sample("스폰 자리에 설 수 없음");
            return false;
        }
        Location s = world.getSpawnLocation();
        boolean same = Math.abs(s.getBlockX() - Math.floor(meta.spawn.x())) <= 1 && Math.abs(s.getBlockZ() - Math.floor(meta.spawn.z())) <= 1;
        if (!same) sample("월드 스폰이 광장 스폰 마커와 다름: " + s.getBlockX() + " " + s.getBlockZ());
        return same;
    }

    private boolean entranceOk() {
        if (!standOk(meta.entrance)) {
            sample("입구 자리에 설 수 없음");
            return false;
        }
        Settings.Entrance e = module.services().settings().entrance();
        boolean same = e.isSet() && e.world().equals(world.getName()) && Math.abs(e.x() - meta.entrance.x()) < 0.6
                && Math.abs(e.z() - meta.entrance.z()) < 0.6 && Math.abs(e.y() - meta.entrance.y()) < 1.1;
        if (!same) sample("config entrance 가 마을 게이트와 다름 (village apply)");
        return same;
    }

    private void report(Map<String, Integer> c, int npcOk, int npcTotal, int interOk, int interTotal, boolean spawn, boolean entrance) {
        String line = "[마을 자가 진단] 결과: 예외 " + exceptions
                + " · checked=" + c.getOrDefault("checked", 0)
                + " mismatched=" + c.getOrDefault("mismatched", -1)
                + " · overlaps=" + c.getOrDefault("overlaps", -1)
                + " · floating=" + c.getOrDefault("floating", -1)
                + " · tree_remnants=" + c.getOrDefault("tree_remnants", -1)
                + " · blocked_doors=" + c.getOrDefault("blocked_doors", -1)
                + " · npcs=" + npcOk + "/" + npcTotal
                + " · interior=" + c.getOrDefault("interior", -1)
                + " · path_steps=" + c.getOrDefault("path_steps", -1)
                + " · interact=" + interOk + "/" + interTotal
                + " · spawn=" + (spawn ? "ok" : "bad")
                + " · entrance=" + (entrance ? "ok" : "bad")
                + " · rot_mismatch=" + rotMismatch;
        boolean pass = exceptions == 0 && c.getOrDefault("mismatched", 1) == 0 && c.getOrDefault("overlaps", 1) == 0
                && c.getOrDefault("floating", 1) == 0 && c.getOrDefault("tree_remnants", 1) == 0 && c.getOrDefault("blocked_doors", 1) == 0
                && npcOk == npcTotal && c.getOrDefault("path_steps", 1) == 0 && interOk == interTotal && spawn && entrance;
        Text.send(sender, (pass ? "<#7fe07f><b>마을 자가 진단 통과</b></#7fe07f>" : "<#ff6b6b><b>마을 자가 진단: 문제 있음</b></#ff6b6b>")
                + " <gray>(" + elapsedSec() + "초)");
        Text.send(sender, "<gray>" + Text.escape(line));
        synchronized (samples) {
            for (String s : samples) Text.send(sender, "<dark_gray>   - " + Text.escape(s.length() > 200 ? s.substring(0, 200) + "…" : s));
        }
        Log.info(line);
    }
}
