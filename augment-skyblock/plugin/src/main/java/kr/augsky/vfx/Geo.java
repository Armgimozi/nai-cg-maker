package kr.augsky.vfx;

/**
 * 팩 이펙트 모델의 모양 정보 (pack/vfx_assets.py 와 맞춘다). 디스플레이 로컬 좌표: +Y 위, +Z 앞, +X 왼쪽.
 * 모델이 아이템 디스플레이의 180도 회전을 이미 반영했으므로 FLIP 을 곱하지 않는다.
 * flat: y=0 평면 반지름 1.5 (slash 는 앞쪽 반원만). cut: z -1.5~1.5 엇갈린 두 판, 폭 0.5.
 * beam·rift: z 0~1, 단면 폭 1 → scale (폭, 폭, 길이). pillar·bolt·flame: 세로 빌보드 x ±0.5, y 0~1 → scale (폭, 높이, 1).
 * billboard: star 2칸, spark·orb·void_orb 1칸, sun·moon 3칸. ring_wall: 반지름 1.5 높이 1. dome: 반지름·높이 1.5.
 */
public record Geo(boolean flat, boolean billboard, boolean vertical, Sprite.End end, int thin) {
    public static final double FLAT_HALF = 1.5;
    public static final double BEAM_HALF_W = 0.5;
    public static final double STAR_HALF = 1.0;
    public static final double ORB_HALF = 0.5;
    public static final double SUN_HALF = 1.5;

    static final Geo FLAT = new Geo(true, false, false, Sprite.End.FADE, 0);
    static final Geo FLAT_SLASH = new Geo(true, false, false, Sprite.End.SLASH, 0);
    static final Geo CUT = new Geo(false, false, false, Sprite.End.THIN, Sprite.AX_X | Sprite.AX_Y);
    static final Geo BEAM = new Geo(false, false, false, Sprite.End.THIN, Sprite.AX_X | Sprite.AX_Y);
    static final Geo COLUMN = new Geo(false, false, true, Sprite.End.THIN, Sprite.AX_X | Sprite.AX_Z);
    static final Geo STAR = new Geo(false, true, false, Sprite.End.FADE, 0);
    static final Geo ORB = new Geo(false, true, false, Sprite.End.SHRINK, 0);
    static final Geo WALL = new Geo(false, false, false, Sprite.End.FADE, 0);
    static final Geo PLAIN = new Geo(false, false, false, Sprite.End.FADE, 0);

    public static Geo of(String model) {
        if (model == null) return PLAIN;
        String m = Models.base(model);
        if (m.startsWith("slash")) return FLAT_SLASH;
        if (m.startsWith("cut")) return CUT;
        if (m.startsWith("ring_wall") || m.startsWith("dome") || m.startsWith("wave")) return WALL;
        if (m.startsWith("ring") || m.startsWith("shock") || m.startsWith("circle") || m.startsWith("swirl")
                || m.startsWith("warn_line") || m.startsWith("warn") || m.startsWith("crack")) return FLAT;
        if (m.startsWith("beam") || m.startsWith("rift")) return BEAM;
        if (m.startsWith("pillar") || m.startsWith("bolt") || m.startsWith("flame")) return COLUMN;
        if (m.startsWith("star")) return STAR;
        if (m.startsWith("spark") || m.startsWith("orb") || m.startsWith("void_orb") || m.startsWith("sun")
                || m.startsWith("moon")) return ORB;
        return PLAIN;
    }
}
