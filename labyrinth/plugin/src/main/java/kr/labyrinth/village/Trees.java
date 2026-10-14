package kr.labyrinth.village;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.bukkit.Material;

/**
 * 나무 치우기 계산 (VILLAGE.md §4.1 2번) — 비동기 스레드에서 스냅샷만 읽는다.
 * <ol>
 *   <li>씨앗: 마을 영역(R+B) 안 원목 + 영역 안 잎에서 잎을 따라 7칸 안에 닿는 원목 (= 영역에 걸친 나무).</li>
 *   <li>씨앗에서 원목끼리(26방향) 이어진 덩어리째 — 영역 밖으로 뻗은 부분 포함 (상한 있음).</li>
 *   <li>잎: 둘레 상자 안 자연 잎 중 남는 원목에서 잎을 따라 6칸 안에 닿지 않는 것 (바닐라 잎 거리 규칙) — 반쯤 잘린 잎 덩어리를 남기지 않는다.</li>
 *   <li>덩굴·코코아·벌집·창백한 이끼 같은 붙은 것, 지운 잎 위 눈 한 겹.</li>
 * </ol>
 */
final class Trees {

    static final int LOG_CAP = 80_000;

    record Result(List<long[]> remove, int logs, int leaves, int parts, boolean capped) {}

    private Trees() {}

    static long pack(int x, int y, int z) {
        return ((long) (x & 0x3FFFFFF) << 38) | ((long) (z & 0x3FFFFFF) << 12) | (y & 0xFFF);
    }

    static int ux(long k) { return (int) (k >> 38) << 6 >> 6; }

    static int uz(long k) { return (int) ((k >> 12) & 0x3FFFFFF) << 6 >> 6; }

    static int uy(long k) { return (int) (k & 0xFFF) << 20 >> 20; }

    private static final int[][] N6 = {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}};

    private static boolean log(Scan.Snapshots s, int x, int y, int z) {
        Material m = s.type(x, y, z);
        return m != null && Scan.kind(m) == Nature.Kind.LOG;
    }

    private static boolean leaf(Scan.Snapshots s, int x, int y, int z) {
        Material m = s.type(x, y, z);
        return m != null && Scan.kind(m) == Nature.Kind.LEAVES && Scan.naturalLeaves(s.data(x, y, z));
    }

    static Result analyze(Scan.Snapshots s, TerrainGrid grid, int cx, int cz, int reach) {
        Set<Long> seeds = new HashSet<>();
        List<long[]> regionLeaves = new ArrayList<>();
        int minX = Integer.MAX_VALUE, minZ = Integer.MAX_VALUE, minY = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE, maxZ = Integer.MIN_VALUE, maxY = Integer.MIN_VALUE;
        for (int z = cz - reach; z <= cz + reach; z++) {
            for (int x = cx - reach; x <= cx + reach; x++) {
                if (Math.hypot(x - cx, z - cz) > reach || !grid.has(x, z) || !grid.flag(x, z, Terrain.TREE)) continue;
                int g = grid.ground(x, z), top = s.highest(x, z);
                for (int y = g + 1; y <= top; y++) {
                    if (log(s, x, y, z)) seeds.add(pack(x, y, z));
                    else if (leaf(s, x, y, z)) regionLeaves.add(new long[] {x, y, z});
                }
            }
        }
        // 영역 안 잎 → 잎 따라 7칸 안 원목도 씨앗
        Map<Long, Integer> depth = new HashMap<>();
        ArrayDeque<long[]> q = new ArrayDeque<>();
        for (long[] l : regionLeaves) {
            depth.put(pack((int) l[0], (int) l[1], (int) l[2]), 0);
            q.add(l);
        }
        while (!q.isEmpty()) {
            long[] c = q.poll();
            int d = depth.get(pack((int) c[0], (int) c[1], (int) c[2]));
            for (int[] n : N6) {
                int x = (int) c[0] + n[0], y = (int) c[1] + n[1], z = (int) c[2] + n[2];
                if (log(s, x, y, z)) seeds.add(pack(x, y, z));
                else if (d < 7 && leaf(s, x, y, z)) {
                    long k = pack(x, y, z);
                    if (!depth.containsKey(k)) {
                        depth.put(k, d + 1);
                        q.add(new long[] {x, y, z});
                    }
                }
            }
        }
        // 원목 덩어리 (26방향)
        Set<Long> logs = new HashSet<>();
        ArrayDeque<Long> lq = new ArrayDeque<>(seeds);
        logs.addAll(seeds);
        boolean capped = false;
        while (!lq.isEmpty()) {
            long k = lq.poll();
            int x0 = ux(k), y0 = uy(k), z0 = uz(k);
            minX = Math.min(minX, x0);
            maxX = Math.max(maxX, x0);
            minY = Math.min(minY, y0);
            maxY = Math.max(maxY, y0);
            minZ = Math.min(minZ, z0);
            maxZ = Math.max(maxZ, z0);
            if (logs.size() >= LOG_CAP) {
                capped = true;
                continue;
            }
            for (int dy = -1; dy <= 1; dy++) {
                for (int dz = -1; dz <= 1; dz++) {
                    for (int dx = -1; dx <= 1; dx++) {
                        if (dx == 0 && dy == 0 && dz == 0) continue;
                        int x = x0 + dx, y = y0 + dy, z = z0 + dz;
                        long nk = pack(x, y, z);
                        if (!logs.contains(nk) && log(s, x, y, z)) {
                            logs.add(nk);
                            lq.add(nk);
                        }
                    }
                }
            }
        }
        for (long[] l : regionLeaves) {
            minX = Math.min(minX, (int) l[0]);
            maxX = Math.max(maxX, (int) l[0]);
            minY = Math.min(minY, (int) l[1]);
            maxY = Math.max(maxY, (int) l[1]);
            minZ = Math.min(minZ, (int) l[2]);
            maxZ = Math.max(maxZ, (int) l[2]);
        }
        List<long[]> remove = new ArrayList<>();
        for (long k : logs) remove.add(new long[] {ux(k), uy(k), uz(k)});
        if (logs.isEmpty() && regionLeaves.isEmpty()) return new Result(remove, 0, 0, 0, false);
        // 잎: 남는 원목에서 6칸 안에 닿지 않는 자연 잎 (둘레 상자 +8)
        Set<Long> orphan = orphanLeaves(s, minX - 8, minY - 8, minZ - 8, maxX + 8, maxY + 8, maxZ + 8, logs);
        int leaves = 0;
        Set<Long> gone = new HashSet<>(logs);
        for (long k : orphan) {
            remove.add(new long[] {ux(k), uy(k), uz(k)});
            gone.add(k);
            leaves++;
        }
        // 붙은 것: 덩굴(이어진 줄 전체)·코코아·벌집·이끼·송진, 지운 잎 위 눈 한 겹
        int parts = 0;
        ArrayDeque<long[]> pq = new ArrayDeque<>();
        Set<Long> partSet = new HashSet<>();
        for (long k : gone) {
            int x0 = ux(k), y0 = uy(k), z0 = uz(k);
            for (int[] n : N6) {
                int x = x0 + n[0], y = y0 + n[1], z = z0 + n[2];
                Material m = s.type(x, y, z);
                if (m == null) continue;
                boolean part = Scan.kind(m) == Nature.Kind.TREE_PART || (m == Material.SNOW && n[1] == 1);
                long nk = pack(x, y, z);
                if (part && !gone.contains(nk) && partSet.add(nk)) pq.add(new long[] {x, y, z});
            }
        }
        while (!pq.isEmpty()) {
            long[] c = pq.poll();
            remove.add(c);
            parts++;
            Material self = s.type((int) c[0], (int) c[1], (int) c[2]);
            if (self != Material.VINE && self != Material.PALE_HANGING_MOSS) continue;
            for (int[] n : N6) {
                int x = (int) c[0] + n[0], y = (int) c[1] + n[1], z = (int) c[2] + n[2];
                if (s.type(x, y, z) == self && partSet.add(pack(x, y, z))) pq.add(new long[] {x, y, z});
            }
        }
        return new Result(remove, logs.size(), leaves, parts, capped);
    }

    /**
     * 상자 안 자연 잎 중 (removed 를 뺀) 원목에서 잎을 따라 6칸 안에 닿지 않는 것.
     * removed 가 비어 있으면 = 지금 떠 있는 잎 덩어리 (자가 진단).
     */
    static Set<Long> orphanLeaves(Scan.Snapshots s, int x0, int y0, int z0, int x1, int y1, int z1, Set<Long> removed) {
        y0 = Math.max(y0, s.minY);
        y1 = Math.min(y1, s.maxY);
        Set<Long> all = new HashSet<>();
        Map<Long, Integer> dist = new HashMap<>();
        ArrayDeque<long[]> q = new ArrayDeque<>();
        for (int x = x0; x <= x1; x++) {
            for (int z = z0; z <= z1; z++) {
                if (!s.has(x, z)) continue;
                int top = Math.min(y1, s.highest(x, z));
                for (int y = y0; y <= top; y++) {
                    Material m = s.type(x, y, z);
                    if (m == null) continue;
                    Nature.Kind k = Scan.kind(m);
                    if (k == Nature.Kind.LEAVES && Scan.naturalLeaves(s.data(x, y, z))) all.add(pack(x, y, z));
                    else if (k == Nature.Kind.LOG && !removed.contains(pack(x, y, z))) q.add(new long[] {x, y, z, 0});
                }
            }
        }
        // 상자 밖에서 들어오는 지지(상자 가장자리 바깥 원목)는 상자 둘레 6칸 안 잎만 해당 → 가장자리 잎은 지지된 것으로 본다
        while (!q.isEmpty()) {
            long[] c = q.poll();
            int d = (int) c[3];
            if (d >= 6) continue;
            for (int[] n : N6) {
                int x = (int) c[0] + n[0], y = (int) c[1] + n[1], z = (int) c[2] + n[2];
                long k = pack(x, y, z);
                if (!all.contains(k) || dist.containsKey(k)) continue;
                dist.put(k, d + 1);
                q.add(new long[] {x, y, z, d + 1});
            }
        }
        Set<Long> out = new HashSet<>();
        for (long k : all) {
            if (dist.containsKey(k)) continue;
            int x = ux(k), z = uz(k);
            boolean edge = x - x0 < 6 || x1 - x < 6 || z - z0 < 6 || z1 - z < 6;
            if (edge && !removedNear(removed, k)) continue; // 상자 밖 원목이 지지할 수 있음
            out.add(k);
        }
        return out;
    }

    /** 상자 가장자리 잎이라도 지운 원목 가까이(7칸)면 고아로 본다. */
    private static boolean removedNear(Set<Long> removed, long k) {
        if (removed.isEmpty()) return false;
        int x = ux(k), y = uy(k), z = uz(k);
        for (int dy = -7; dy <= 7; dy++) {
            for (int dz = -7; dz <= 7; dz++) {
                for (int dx = -7; dx <= 7; dx++) {
                    if (Math.abs(dx) + Math.abs(dy) + Math.abs(dz) > 7) continue;
                    if (removed.contains(pack(x + dx, y + dy, z + dz))) return true;
                }
            }
        }
        return false;
    }
}
