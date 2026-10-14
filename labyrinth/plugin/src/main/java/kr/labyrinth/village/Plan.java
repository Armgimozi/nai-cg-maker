package kr.labyrinth.village;

import java.util.ArrayList;
import java.util.List;

/**
 * 계획기 결과 하나 (자리 + 방향). 조각마다 실제 자리(slack 조정 후)·단 높이 P, 길 칸·높이, 목표 높이장, 깎기/메우기 양.
 * survey 와 build 가 같은 {@link Planner} 결과를 쓴다.
 */
public final class Plan {

    /** 놓인 조각. 회전 후 발자국 상자 왼쪽-북쪽 모서리 (x0, z0), 크기 w2 × d2, 단 높이 floor(= P). */
    public static final class Placed {
        public final Layout.Entry entry;
        public final Blueprint bp;
        /** 마을 회전 + 조각 정면 회전 (시계 방향 90° 단위). */
        public final int turns;
        public final int w2, d2;
        public int x0, z0;
        public int dx, dz;
        public int floor;
        final boolean[] occ;

        public Placed(Layout.Entry entry, Blueprint bp, int turns, int x0, int z0) {
            this.entry = entry;
            this.bp = bp;
            this.turns = Math.floorMod(turns, 4);
            int[] dm = Rot.dims(bp.w, bp.d, this.turns);
            this.w2 = dm[0];
            this.d2 = dm[1];
            this.x0 = x0;
            this.z0 = z0;
            this.occ = new boolean[w2 * d2];
            for (int z = 0; z < bp.d; z++) {
                for (int x = 0; x < bp.w; x++) {
                    if (!bp.occupied(x, z)) continue;
                    int[] r = Rot.inBox(x, z, bp.w, bp.d, this.turns);
                    occ[r[1] * w2 + r[0]] = true;
                }
            }
        }

        public int index() { return entry.index(); }

        /** 정방향 조각 (x, z) → 월드 (x, z). 상자 밖 좌표(정문 앞 칸 등)도 같은 공식. */
        public int[] world(int x, int z) {
            int[] r = Rot.inBox(x, z, bp.w, bp.d, turns);
            return new int[] {x0 + r[0], z0 + r[1]};
        }

        /** 조각 layer y → 월드 Y (§2.3: P + (y − floor_y)). */
        public int worldY(int y) { return floor + (y - bp.floorY); }

        public boolean occupies(int wx, int wz) {
            int lx = wx - x0, lz = wz - z0;
            return lx >= 0 && lz >= 0 && lx < w2 && lz < d2 && occ[lz * w2 + lx];
        }

        /** 조각 정면이 바라보는 월드 방향. */
        public Dir front() { return Dir.NORTH.rotate(turns); }

        public int[] anchor() { return world(bp.anchorX, bp.anchorZ); }

        /** 정문 바로 앞 바깥 칸: anchor 에서 정면(정방향 −z)으로 가다 발자국을 벗어난 첫 칸 (VILLAGE.md §3). */
        public int[] doorFront() { return world(bp.anchorX, doorZ(bp)); }

        static int doorZ(Blueprint bp) {
            int z = bp.anchorZ;
            while (z >= 0 && bp.occupied(bp.anchorX, z)) z--;
            return z;
        }

        public int minY() { return worldY(0); }

        public int maxY() { return worldY(bp.h - 1); }

        public int occupiedCount() {
            int n = 0;
            for (boolean b : occ) if (b) n++;
            return n;
        }
    }

    /** 길 하나: 월드 꺾은선(붙은 조각을 따라 옮긴 뒤), 붙은 조각 index(없으면 −1), 칸(x, z, y — 조각 발자국 안은 뺌). */
    public static final class PathPlan {
        public final Layout.PathDef def;
        public final List<int[]> points;
        public int attachA = -1, attachB = -1;
        public final List<int[]> cells = new ArrayList<>();

        public PathPlan(Layout.PathDef def, List<int[]> points) {
            this.def = def;
            this.points = points;
        }

        public boolean attached(int piece) { return piece >= 0 && (attachA == piece || attachB == piece); }
    }

    public final int cx, cz, turns;
    /** 계획기 안쪽 반경 R · 혼합 띠 B. */
    public int inner, blend;
    public Planner.Fail fail = Planner.Fail.NONE;
    public String reason = "";
    public int h0;
    public final List<Placed> pieces = new ArrayList<>();
    public final List<PathPlan> paths = new ArrayList<>();

    /** 영역 격자 (정사각형, 한 변 gn = 2·reach + 1, 왼쪽-북쪽 = (gx0, gz0)). */
    public int gx0, gz0, gn;
    public int[] ground;
    public int[] fixedH;
    /** 칸마다 고정 출처: 0 없음, 1 추가 단, 2 조각 여유 칸, 3 길, 4 정문 앞, 5 조각 발자국. */
    public byte[] fixedSrc;
    /** full 계획일 때만. */
    public HeightField.Result field;

    public long padCost, cut, fill, caveFill;
    public int logs;
    public String biome = "?";
    public int steepPaths;

    public Plan(int cx, int cz, int turns) {
        this.cx = cx;
        this.cz = cz;
        this.turns = Math.floorMod(turns, 4);
    }

    public boolean ok() { return fail == Planner.Fail.NONE; }

    /** 점수 (작을수록 좋음): full 이면 깎기 + 메우기 + 동굴 메우기, 아니면 고정 칸 변화량. */
    public double score() { return field != null ? cut + fill + caveFill : padCost + caveFill; }

    /** 마을 정면(게이트) 방향 = 정방향 북쪽을 turns 만큼. */
    public Dir front() { return Dir.NORTH.rotate(turns); }

    public boolean inGrid(int x, int z) {
        int lx = x - gx0, lz = z - gz0;
        return lx >= 0 && lz >= 0 && lx < gn && lz < gn;
    }

    public int idx(int x, int z) { return (z - gz0) * gn + (x - gx0); }

    /** 목표 높이 (full 계획). 격자 밖이면 NONE. */
    public int target(int x, int z) {
        if (field == null || !inGrid(x, z)) return HeightField.NONE;
        return field.target()[idx(x, z)];
    }

    public Placed piece(int index) {
        for (Placed p : pieces) if (p.index() == index) return p;
        return null;
    }

    public String summary() {
        return "중심 (" + cx + ", " + cz + ") 정면 " + front().key() + " · H0 " + h0 + (field != null ? " · 깎기 " + cut + " 메우기 " + fill : " · 단 변화 " + padCost)
                + " · 동굴 메움 " + caveFill + " · 원목 " + logs + " · " + biome;
    }
}
