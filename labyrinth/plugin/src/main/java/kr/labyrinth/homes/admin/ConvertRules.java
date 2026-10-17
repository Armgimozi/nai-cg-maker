package kr.labyrinth.homes.admin;

/**
 * {@code /labadmin plot convert} 상자 검사 (0.3.7, plan §11) — 순수. 소유: 묶음 B.
 * 가로·세로 ≤ 32, 높이 ≤ 48. 높이를 안 주면 땅 최저 −8 ~ 땅 최고 +24.
 */
public final class ConvertRules {

    private ConvertRules() {}

    public static final int MAX_XZ = 32;
    public static final int MAX_HEIGHT = 48;
    public static final int BELOW = 8;
    public static final int ABOVE = 24;

    /** 정리된 상자 (양 끝 포함) 또는 글. */
    public record Box(int x0, int z0, int x1, int z1, int y0, int y1, String error) {
        public boolean ok() { return error == null; }

        public int floorY() { return Math.min(y1, y0 + BELOW); }
    }

    /**
     * @param y1 y2 null 이면 groundMin − 8 ~ groundMax + 24
     */
    public static Box check(int ax, int az, int bx, int bz, Integer y1, Integer y2, int groundMin, int groundMax, int worldMin, int worldMax) {
        int x0 = Math.min(ax, bx), x1 = Math.max(ax, bx), z0 = Math.min(az, bz), z1 = Math.max(az, bz);
        int lo, hi;
        if (y1 != null && y2 != null) {
            lo = Math.min(y1, y2);
            hi = Math.max(y1, y2);
        } else {
            lo = groundMin - BELOW;
            hi = groundMax + ABOVE;
        }
        lo = Math.max(worldMin, lo);
        hi = Math.min(worldMax, hi);
        String err = null;
        if (x1 - x0 + 1 > MAX_XZ || z1 - z0 + 1 > MAX_XZ) err = "가로·세로는 " + MAX_XZ + "칸까지입니다 (지금 " + (x1 - x0 + 1) + "×" + (z1 - z0 + 1) + ").";
        else if (hi - lo + 1 > MAX_HEIGHT) {
            err = "높이는 " + MAX_HEIGHT + "칸까지입니다 (지금 " + lo + "~" + hi + ", " + (hi - lo + 1) + "칸)."
                    + (y1 == null ? " 높이 y1 y2 를 직접 주세요." : "");
        } else if (hi < lo) err = "높이가 틀렸습니다.";
        return new Box(x0, z0, x1, z1, lo, hi, err);
    }
}
