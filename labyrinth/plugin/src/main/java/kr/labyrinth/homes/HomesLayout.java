package kr.labyrinth.homes;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 배포 월드의 "등불 골목" 집 구역 설계 (0.3.7, 10채) — 순수 자료. 소유: 묶음 A.
 * <p>
 * 좌표는 배포 월드 좌표다 (시드 24680, 마을 중심 (-136, 16), 마을 회전 반시계 90°). 실제 집터는 구역 기계가 계획해 구역 기록
 * {@code plots:} 에 남긴 값이 정답이고 (회전·here 자리·계획기가 고른 바닥), 이것은 그 설계값·시험 기준이다.
 * 원본: {@code design036/plots/plots_spec.json} 에서 옛 3번(마을이 다듬은 칸 위, review R1)·옛 9번(광장에서 가장 멂)을 빼고 1..10 으로
 * 다시 번호를 매긴 것 (pl37/work/plots10_spec.json, {@link Spec#oldId}).
 */
public final class HomesLayout {

    private HomesLayout() {}

    /** 상자 [x0, z0, x1, z1] (양 끝 포함). */
    public record Box(String name, int x0, int z0, int x1, int z1) {
        public boolean contains(int x, int z) { return x >= x0 && x <= x1 && z >= z0 && z <= z1; }
    }

    /**
     * 집터 하나 (설계).
     *
     * @param floorY 설계 바닥 높이 (계획기가 ±1 안에서 고름 — 3번은 마을이 다듬은 칸 높이 68 그대로)
     * @param front  대문 쪽 ("N" = 북쪽 거리로 나감, "S" = 남쪽)
     */
    public record Spec(int id, int oldId, int x0, int z0, int x1, int z1, int floorY, String front, int gateX, int gateZ, int signX,
                       double homeX, double homeZ, float homeYaw) {
        public boolean contains(int x, int z) { return x >= x0 && x <= x1 && z >= z0 && z <= z1; }

        /** 대문 바깥 (거리 쪽) 칸. */
        public int[] gateOutside() { return new int[] {gateX, gateZ + ("S".equals(front) ? 1 : -1)}; }
    }

    /** 집 수. */
    public static final int COUNT = 10;
    /** 집터 한 변. */
    public static final int SIZE = 14;
    /** 마을 길 1 의 첫 칸 (이음 칸이 붙는 곳). */
    public static final int[][] JUNCTION = {{-137, 26}, {-137, 27}};

    public static final List<Spec> PLOTS = List.of(
            // 등불길 북쪽 (대문 남쪽, z 62)
            new Spec(1, 1, -178, 48, -165, 61, 73, "S", -172, 62, -170, -171.5, 63.5, 180f),
            new Spec(2, 2, -163, 48, -150, 61, 72, "S", -157, 62, -155, -156.5, 63.5, 180f),
            new Spec(3, 4, -129, 48, -116, 61, 68, "S", -123, 62, -121, -122.5, 63.5, 180f),
            // 등불길 남쪽 (대문 북쪽, z 68)
            new Spec(4, 5, -178, 69, -165, 82, 75, "N", -172, 68, -170, -171.5, 67.5, 0f),
            new Spec(5, 6, -163, 69, -150, 82, 71, "N", -157, 68, -155, -156.5, 67.5, 0f),
            new Spec(6, 7, -144, 69, -131, 82, 67, "N", -138, 68, -136, -137.5, 67.5, 0f),
            new Spec(7, 8, -129, 69, -116, 82, 66, "N", -123, 68, -121, -122.5, 67.5, 0f),
            // 우물길 북쪽 (대문 남쪽, z 98)
            new Spec(8, 10, -163, 84, -150, 97, 70, "S", -157, 98, -155, -156.5, 99.5, 180f),
            new Spec(9, 11, -144, 84, -131, 97, 67, "S", -138, 98, -136, -137.5, 99.5, 180f),
            new Spec(10, 12, -129, 84, -116, 97, 66, "S", -123, 98, -121, -122.5, 99.5, 180f));

    /** 걸어 다니는 공용 칸 (구역 보호 상자 — 길·골목). */
    public static final List<Box> PUBLIC = List.of(
            new Box("이음 칸", -145, 26, -138, 27),
            new Box("골목", -145, 28, -144, 46),
            new Box("받는 칸", -148, 47, -144, 47),
            new Box("가운데 골목", -148, 47, -146, 98),
            new Box("등불길", -179, 63, -115, 67),
            new Box("우물길", -164, 99, -115, 103));

    /** 골목 마당 (옛 3번 자리) — 땅 그대로, 장식만 (마을이 다듬은 칸 z 47..49 를 피해 z 52 이후). 집터 아님. */
    public static final Box YARD = new Box("골목 마당", -144, 48, -131, 61);

    /** 구역 상자 (설계 district_box). */
    public static final Box DISTRICT = new Box("등불 골목", -179, 47, -115, 103);

    public static Spec plot(int id) {
        for (Spec s : PLOTS) if (s.id() == id) return s;
        return null;
    }

    /** 집터 열인가. */
    public static Spec plotAt(int x, int z) {
        for (Spec s : PLOTS) if (s.contains(x, z)) return s;
        return null;
    }

    /** 공용 칸인가. */
    public static boolean isPublic(int x, int z) {
        for (Box b : PUBLIC) if (b.contains(x, z)) return true;
        return false;
    }

    /** 공용 칸 전부 (xz 키 = {@link #key}). */
    public static Set<Long> publicCells() {
        Set<Long> out = new HashSet<>();
        for (Box b : PUBLIC) for (int z = b.z0(); z <= b.z1(); z++) for (int x = b.x0(); x <= b.x1(); x++) out.add(key(x, z));
        return out;
    }

    /** 집터 둘레 한 칸 (울타리·생울타리 줄 — 구역 보호 상자 = zone 0). */
    public static Set<Long> ringCells(Spec s) {
        Set<Long> out = new HashSet<>();
        for (int x = s.x0() - 1; x <= s.x1() + 1; x++) {
            out.add(key(x, s.z0() - 1));
            out.add(key(x, s.z1() + 1));
        }
        for (int z = s.z0(); z <= s.z1(); z++) {
            out.add(key(s.x0() - 1, z));
            out.add(key(s.x1() + 1, z));
        }
        return out;
    }

    /** 설계값 집터 모양 (높이 창 = 바닥 − below .. 바닥 + above · 표지판 높이·집 가기 칸 높이는 모름). */
    public static List<PlotGeom> geoms(int below, int above) {
        List<PlotGeom> out = new ArrayList<>();
        for (Spec s : PLOTS) {
            out.add(new PlotGeom(String.valueOf(s.id()), s.id(), s.x0(), s.z0(), s.x1(), s.z1(), s.floorY(), s.floorY() - below, s.floorY() + above,
                    s.front(), s.gateX(), s.gateZ(), s.signX(), Integer.MIN_VALUE, s.gateZ(), s.homeX(), Double.NaN, s.homeZ(), s.homeYaw(), false));
        }
        return out;
    }

    public static long key(int x, int z) { return ((long) x << 32) ^ (z & 0xffffffffL); }
}
