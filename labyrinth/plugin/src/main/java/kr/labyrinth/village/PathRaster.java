package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 길 꺾은선 → 칸 (VILLAGE.md §3 paths). 폭 w: 홀수면 점이 칸 가운데, 짝수면 칸 모서리를 지나는 중심선에서
 * 거리 w/2 안의 칸. 칸마다 중심선을 따라간 거리 t(0..길이)를 함께 준다 — 높이 보간용.
 */
public final class PathRaster {

    /** 칸 하나: 월드 (x, z) + 중심선 위 거리 t. */
    public record Cell(int x, int z, double t) {}

    private PathRaster() {}

    /** points: 월드 좌표 [x, z] 들. @return 칸 목록 (t 순) — 같은 칸은 한 번만. */
    public static List<Cell> cells(List<int[]> points, int width) {
        double off = width % 2 == 1 ? 0.5 : 0.0;
        int n = points.size();
        double[] px = new double[n], pz = new double[n], cum = new double[n];
        for (int i = 0; i < n; i++) {
            px[i] = points.get(i)[0] + off;
            pz[i] = points.get(i)[1] + off;
            if (i > 0) cum[i] = cum[i - 1] + Math.hypot(px[i] - px[i - 1], pz[i] - pz[i - 1]);
        }
        double half = width / 2.0 - 0.01;
        int minX = Integer.MAX_VALUE, minZ = Integer.MAX_VALUE, maxX = Integer.MIN_VALUE, maxZ = Integer.MIN_VALUE;
        for (int[] p : points) {
            minX = Math.min(minX, p[0]);
            maxX = Math.max(maxX, p[0]);
            minZ = Math.min(minZ, p[1]);
            maxZ = Math.max(maxZ, p[1]);
        }
        int pad = width / 2 + 2;
        Map<Long, Cell> out = new LinkedHashMap<>();
        for (int z = minZ - pad; z <= maxZ + pad; z++) {
            for (int x = minX - pad; x <= maxX + pad; x++) {
                double cx = x + 0.5, cz = z + 0.5;
                double best = Double.MAX_VALUE, bestT = 0;
                for (int i = 1; i < n; i++) {
                    double ax = px[i - 1], az = pz[i - 1], bx = px[i], bz = pz[i];
                    double dx = bx - ax, dz = bz - az;
                    double len2 = dx * dx + dz * dz;
                    double u = len2 <= 1e-9 ? 0 : ((cx - ax) * dx + (cz - az) * dz) / len2;
                    u = Math.max(0, Math.min(1, u));
                    double qx = ax + u * dx, qz = az + u * dz;
                    double dist = Math.hypot(cx - qx, cz - qz);
                    if (dist < best - 1e-9) {
                        best = dist;
                        bestT = cum[i - 1] + u * Math.sqrt(len2);
                    }
                }
                if (best <= half) out.put(key(x, z), new Cell(x, z, bestT));
            }
        }
        List<Cell> list = new ArrayList<>(out.values());
        list.sort((a, b) -> Double.compare(a.t(), b.t()));
        return list;
    }

    /** 꺾은선 길이. */
    public static double length(List<int[]> points) {
        double l = 0;
        for (int i = 1; i < points.size(); i++) {
            l += Math.hypot(points.get(i)[0] - points.get(i - 1)[0], points.get(i)[1] - points.get(i - 1)[1]);
        }
        return l;
    }

    public static long key(int x, int z) { return ((long) x << 32) ^ (z & 0xffffffffL); }
}
