package kr.labyrinth.dungeon.traps;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.MazePlan;
import kr.labyrinth.dungeon.treasure.TreasurePlan;

/**
 * 함정 배치 (순수 로직 — Bukkit 무관, 단위 테스트 대상, GDD §5.5). 같은 층·같은 시드 → 같은 결과.
 * <ul>
 *   <li>후보 = {@link FloorLayout#hallTiles()} (복도 평평한 바닥만 — 방·문 2칸 이내·계단·비밀방·보스 복도는 이미 빠짐).
 *       시작방 바로 옆 셀(거리 &lt; 2)·상자 둘레 2칸·금고 안과 문 둘레·금 간 벽 둘레는 뺀다 → 시작·휴식·보스·기믹방 안에는 함정이 없다.</li>
 *   <li>개수 = 복도 셀 수 × {@code density}. 가중 무작위(막다른 길 셀 ×3, 갈림길 셀 ×2.5, 상자·막다른 길 앞 복도 ×4)로 고르고,
 *       함정끼리 {@code spacing} 칸 이상 띄운다. 종류는 층 {@code types} 를 돌아가며 — 모양이 안 맞으면 다음 종류.</li>
 *   <li>모양: 복도를 가로지르는 한 줄(좁은 쪽 축, 최대 3칸). 벽 발사구 함정은 양 끝이 벽, 구덩이는 두 줄 + 높이 0 + 주변에 도랑·계단 없음.</li>
 * </ul>
 */
public final class TrapPlanner {

    private TrapPlanner() {}

    public static List<TrapSpot> plan(FloorLayout l, TrapSettings s, TreasurePlan t, long seed) {
        if (s.density() <= 0 || s.types().isEmpty()) return List.of();
        SplittableRandom rng = new SplittableRandom(seed ^ 0x7A3B9C1DL);
        MazePlan plan = l.plan();
        int[] hallArr = l.hallTiles();
        Set<Integer> hall = new HashSet<>(hallArr.length * 2);
        for (int h : hallArr) hall.add(h);

        Set<Integer> blocked = new HashSet<>();
        Set<Integer> hot = new HashSet<>();
        for (TreasurePlan.Chest c : t.chests()) {
            around(blocked, c.x(), c.z(), 2);
            if (c.source() != TreasurePlan.Source.SECRET && c.source() != TreasurePlan.Source.VAULT) approach(hot, c.x(), c.z(), c.dirX(), c.dirZ(), 3, 7);
        }
        for (FloorLayout.DeadEnd de : l.deadEnds()) {
            if (!de.minor()) approach(hot, de.tipX(), de.tipZ(), de.dirX(), de.dirZ(), 3, 7);
        }
        TreasurePlan.Vault v = t.vault();
        if (v != null) {
            for (int z = v.minZ() - 1; z <= v.maxZ() + 1; z++) for (int x = v.minX() - 1; x <= v.maxX() + 1; x++) blocked.add(FloorLayout.pack(x, z));
            for (int d : v.door()) around(blocked, FloorLayout.unpackX(d), FloorLayout.unpackZ(d), 2);
            approach(hot, v.doorX(), v.doorZ(), v.dirX(), v.dirZ(), 3, 7);
        }
        for (FloorLayout.SecretRoom sr : l.secretRooms()) {
            for (int w : sr.wall()) around(blocked, FloorLayout.unpackX(w), FloorLayout.unpackZ(w), 1);
        }

        int hallCells = 0;
        for (int c = 0; c < plan.cellCount(); c++) if (plan.used(c) && !plan.type(c).isRoom()) hallCells++;
        int target = (int) Math.round(s.density() * hallCells);
        if (target <= 0) return List.of();

        // 가중 무작위 순서 (Efraimidis–Spirakis: key = u^(1/w), 큰 것부터)
        List<double[]> cands = new ArrayList<>();
        for (int p : hallArr) {
            if (blocked.contains(p)) continue;
            int x = FloorLayout.unpackX(p), z = FloorLayout.unpackZ(p);
            if (l.kind(x, z) != FloorLayout.FLOOR) continue;
            int cell = l.cellAt(x, z);
            if (cell < 0 || plan.distance(cell) < 2) continue;
            double w = 1;
            int deg = Integer.bitCount(plan.exits(cell));
            if (deg <= 1) w *= 3;
            else if (deg >= 3) w *= 2.5;
            if (hot.contains(p)) w *= 4;
            cands.add(new double[] {Math.pow(rng.nextDouble(), 1.0 / w), p});
        }
        cands.sort((a, b) -> Double.compare(b[0], a[0]));

        List<TrapSpot> out = new ArrayList<>();
        Set<Integer> used = new HashSet<>();
        List<TrapType> types = s.types();
        int cursor = rng.nextInt(types.size());
        for (double[] c : cands) {
            if (out.size() >= target) break;
            int p = (int) c[1];
            int x = FloorLayout.unpackX(p), z = FloorLayout.unpackZ(p);
            if (tooClose(out, x, z, s.spacing())) continue;
            for (int k = 0; k < types.size(); k++) {
                TrapType type = types.get((cursor + k) % types.size());
                TrapSpot spot = fit(l, hall, blocked, used, type, x, z, out.size(), rng);
                if (spot == null) continue;
                out.add(spot);
                for (int tile : spot.tiles()) used.add(tile);
                cursor = (cursor + k + 1) % types.size();
                break;
            }
        }
        return out;
    }

    /** 함정 칸 전부 (packed). */
    public static Set<Integer> tiles(List<TrapSpot> spots) {
        Set<Integer> out = new HashSet<>();
        for (TrapSpot s : spots) for (int t : s.tiles()) out.add(t);
        return out;
    }

    private static void around(Set<Integer> set, int x, int z, int r) {
        for (int dz = -r; dz <= r; dz++) for (int dx = -r; dx <= r; dx++) set.add(FloorLayout.pack(x + dx, z + dz));
    }

    /** 끝 칸에서 복도 쪽으로 from..to 칸, 폭 ±1. */
    private static void approach(Set<Integer> set, int x, int z, int dx, int dz, int from, int to) {
        int px = dz != 0 ? 1 : 0, pz = dx != 0 ? 1 : 0;
        for (int k = from; k <= to; k++) {
            for (int w = -1; w <= 1; w++) set.add(FloorLayout.pack(x + k * dx + w * px, z + k * dz + w * pz));
        }
    }

    private static boolean tooClose(List<TrapSpot> out, int x, int z, int spacing) {
        for (TrapSpot s : out) if (Math.max(Math.abs(s.x() - x), Math.abs(s.z() - z)) < spacing) return true;
        return false;
    }

    /** (x,z) 를 지나는 dx,dz 축 위로 같은 높이 걸을 수 있는 칸 수 (양쪽 최대 9). */
    static int run(FloorLayout l, int x, int z, int dx, int dz, int e) {
        int n = 1;
        for (int s = -1; s <= 1; s += 2) {
            for (int k = 1; k <= 9; k++) {
                int nx = x + s * k * dx, nz = z + s * k * dz;
                if (!l.walkable(nx, nz) || l.elevation(nx, nz) != e) break;
                n++;
            }
        }
        return n;
    }

    private static boolean ok(FloorLayout l, Set<Integer> hall, Set<Integer> blocked, Set<Integer> used, int x, int z, int e) {
        int p = FloorLayout.pack(x, z);
        return hall.contains(p) && !blocked.contains(p) && !used.contains(p) && l.kind(x, z) == FloorLayout.FLOOR && l.elevation(x, z) == e;
    }

    /** 이 종류가 (x,z) 에 맞으면 자리, 아니면 null. */
    static TrapSpot fit(FloorLayout l, Set<Integer> hall, Set<Integer> blocked, Set<Integer> used, TrapType type, int x, int z,
                        int index, SplittableRandom rng) {
        int e = l.elevation(x, z);
        int rx = run(l, x, z, 1, 0, e), rz = run(l, x, z, 0, 1, e);
        boolean crossIsX = rx < rz || (rx == rz && rng.nextBoolean());
        int cx = crossIsX ? 1 : 0, cz = crossIsX ? 0 : 1;
        int ax = 1 - cx, az = 1 - cz;
        int lo = 0, hi = 0;
        while (lo > -2 && l.walkable(x + (lo - 1) * cx, z + (lo - 1) * cz) && l.elevation(x + (lo - 1) * cx, z + (lo - 1) * cz) == e) lo--;
        while (hi < 2 && l.walkable(x + (hi + 1) * cx, z + (hi + 1) * cz) && l.elevation(x + (hi + 1) * cx, z + (hi + 1) * cz) == e) hi++;
        if (hi - lo + 1 > 3) {
            lo = Math.max(lo, -1);
            hi = Math.min(hi, 1);
        }
        boolean fullWidth = !l.open(x + (lo - 1) * cx, z + (lo - 1) * cz) && !l.open(x + (hi + 1) * cx, z + (hi + 1) * cz);
        List<Integer> tiles = new ArrayList<>();
        for (int k = lo; k <= hi; k++) {
            int tx = x + k * cx, tz = z + k * cz;
            if (!ok(l, hall, blocked, used, tx, tz, e)) return null;
            tiles.add(FloorLayout.pack(tx, tz));
        }
        int[] walls = new int[0];
        switch (type.shape()) {
            case WALL -> {
                if (!fullWidth) return null;
                walls = new int[] {FloorLayout.pack(x + (lo - 1) * cx, z + (lo - 1) * cz), FloorLayout.pack(x + (hi + 1) * cx, z + (hi + 1) * cz)};
            }
            case SAW -> {
                if (!fullWidth || hi - lo + 1 < 2) return null;
            }
            case PIT -> {
                if (!fullWidth || e != 0) return null;
                int sgn = rng.nextBoolean() ? 1 : -1;
                List<Integer> second = new ArrayList<>();
                for (int k = lo; k <= hi; k++) {
                    int tx = x + k * cx + sgn * ax, tz = z + k * cz + sgn * az;
                    if (!ok(l, hall, blocked, used, tx, tz, 0)) return null;
                    second.add(FloorLayout.pack(tx, tz));
                }
                // 두 번째 줄도 같은 폭이어야 (옆으로 비켜 갈 틈 없음)
                if (l.open(x + (lo - 1) * cx + sgn * ax, z + (lo - 1) * cz + sgn * az)
                        || l.open(x + (hi + 1) * cx + sgn * ax, z + (hi + 1) * cz + sgn * az)) return null;
                tiles.addAll(second);
                for (int t : tiles) {
                    int tx = FloorLayout.unpackX(t), tz = FloorLayout.unpackZ(t);
                    for (int dz = -1; dz <= 1; dz++) {
                        for (int dx = -1; dx <= 1; dx++) {
                            byte k = l.kind(tx + dx, tz + dz);
                            if (k == FloorLayout.GUTTER || k == FloorLayout.STAIR || k == FloorLayout.DOOR || k == FloorLayout.SECRET) return null;
                            if (k != FloorLayout.VOID && l.elevation(tx + dx, tz + dz) != 0) return null;
                        }
                    }
                }
                if (sgn < 0) {
                    ax = -ax;
                    az = -az;
                }
            }
            default -> { }
        }
        int[] arr = tiles.stream().mapToInt(Integer::intValue).toArray();
        return new TrapSpot(index, type, x, z, arr, ax, az, cx, cz, walls, e, rng.nextInt(80));
    }
}
