package kr.labyrinth.homes.rules;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 옛 건물 조사 묶기 (0.3.7, plan §10 · review R14) — 순수. 소유: 묶음 B.
 * 사람이 놓은 블록이 있는 열 (x, z, 개수, 대표 높이) 을 가로·세로 dist 칸 안끼리 한 무리로 묶고 큰 것부터 돌려준다.
 */
public final class LegacyClusters {

    private LegacyClusters() {}

    /** 열 하나: 사람 블록 count 개, 처음 본 높이 y. */
    public record Column(int x, int z, int count, int y) {}

    /** 무리: 상자 · 블록 수 · 열 수 · 가운데 높이. */
    public record Cluster(int x0, int z0, int x1, int z1, int blocks, int columns, int y) {
        public int cx() { return (x0 + x1) / 2; }

        public int cz() { return (z0 + z1) / 2; }
    }

    public static List<Cluster> cluster(List<Column> cols, int dist, int limit) {
        int n = cols.size();
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        int cell = Math.max(1, dist);
        Map<Long, List<Integer>> grid = new HashMap<>();
        for (int i = 0; i < n; i++) {
            Column c = cols.get(i);
            grid.computeIfAbsent(key(Math.floorDiv(c.x(), cell), Math.floorDiv(c.z(), cell)), k -> new ArrayList<>()).add(i);
        }
        for (int i = 0; i < n; i++) {
            Column c = cols.get(i);
            int gx = Math.floorDiv(c.x(), cell), gz = Math.floorDiv(c.z(), cell);
            for (int dx = -1; dx <= 1; dx++) for (int dz = -1; dz <= 1; dz++) {
                List<Integer> l = grid.get(key(gx + dx, gz + dz));
                if (l == null) continue;
                for (int j : l) {
                    if (j <= i) continue;
                    Column o = cols.get(j);
                    if (Math.abs(o.x() - c.x()) <= dist && Math.abs(o.z() - c.z()) <= dist) union(parent, i, j);
                }
            }
        }
        Map<Integer, int[]> acc = new HashMap<>(); // root → x0 z0 x1 z1 blocks columns ysum
        for (int i = 0; i < n; i++) {
            Column c = cols.get(i);
            int r = find(parent, i);
            int[] a = acc.computeIfAbsent(r, k -> new int[] {Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE, 0, 0, 0});
            a[0] = Math.min(a[0], c.x());
            a[1] = Math.min(a[1], c.z());
            a[2] = Math.max(a[2], c.x());
            a[3] = Math.max(a[3], c.z());
            a[4] += c.count();
            a[5]++;
            a[6] += c.y();
        }
        List<Cluster> out = new ArrayList<>();
        for (int[] a : acc.values()) out.add(new Cluster(a[0], a[1], a[2], a[3], a[4], a[5], a[5] == 0 ? 0 : a[6] / a[5]));
        out.sort(Comparator.comparingInt(Cluster::blocks).reversed().thenComparingInt(Cluster::x0).thenComparingInt(Cluster::z0));
        return limit > 0 && out.size() > limit ? new ArrayList<>(out.subList(0, limit)) : out;
    }

    private static long key(int a, int b) { return ((long) a << 32) ^ (b & 0xffffffffL); }

    private static int find(int[] p, int i) {
        while (p[i] != i) {
            p[i] = p[p[i]];
            i = p[i];
        }
        return i;
    }

    private static void union(int[] p, int a, int b) {
        int ra = find(p, a), rb = find(p, b);
        if (ra != rb) p[Math.max(ra, rb)] = Math.min(ra, rb);
    }
}
