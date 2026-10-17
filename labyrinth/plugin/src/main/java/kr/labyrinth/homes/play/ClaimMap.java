package kr.labyrinth.homes.play;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import kr.labyrinth.homes.HomesLayout;

/**
 * 집 고르기 지도 (0.3.7, plan §1.2·§8) — 순수. 실제 배치 4×3 을 6줄 상자 메뉴 칸으로.
 * <pre>
 *   줄 0          [마을 ↑ 골목]
 *   줄 1   1  2  | 마당  3        (등불길 북쪽)
 *   줄 2   ───── 등불길 ─────     (관리인 노점 = 골목 칸)
 *   줄 3   4  5  |  6    7        (등불길 남쪽)
 *   줄 4   ·  8  |  9   10        (우물길 북쪽 · 옛 9번 자리는 들판)
 *   줄 5   ───── 우물길 ─────
 * </pre>
 * 가로 칸 = 설계 집터 x0 차례 (서 → 동) → 상자 칸 2·3·5·6, 가운데 4 = 골목. 세로 = z0 차례 (북 → 남) → 줄 1·3·4.
 * 번호는 자리(south_west · here)와 상관없이 같으므로 설계 배치({@link HomesLayout})로 정한다.
 */
public final class ClaimMap {

    private ClaimMap() {}

    public static final int[] COL_SLOTS = {2, 3, 5, 6};
    public static final int[] ROW_SLOTS = {1, 3, 4};
    public static final int ALLEY_COL = 4;
    /** 거리 줄 (등불길 · 우물길). */
    public static final int LANTERN_ROW = 2;
    public static final int WELL_ROW = 5;
    /** 설계 배치에 없는 집터 (관리자 convert c1 …) 를 놓을 칸 — 양쪽 가장자리. */
    public static final int[] EXTRA_SLOTS = {9, 18, 27, 36, 17, 26, 35, 44};

    /** 설계 배치의 번지 → 칸. */
    public static final Map<String, Integer> DESIGN = of(HomesLayout.PLOTS);

    /** 집터 설계 목록 → 번지 → 칸 (가로 4·세로 3 을 넘으면 넘는 것은 빠짐). */
    public static Map<String, Integer> of(List<HomesLayout.Spec> plots) {
        TreeSet<Integer> xs = new TreeSet<>(), zs = new TreeSet<>();
        for (HomesLayout.Spec s : plots) {
            xs.add(s.x0());
            zs.add(s.z0());
        }
        List<Integer> xl = new ArrayList<>(xs), zl = new ArrayList<>(zs);
        Map<String, Integer> out = new LinkedHashMap<>();
        for (HomesLayout.Spec s : plots) {
            int c = xl.indexOf(s.x0()), r = zl.indexOf(s.z0());
            if (c < 0 || c >= COL_SLOTS.length || r < 0 || r >= ROW_SLOTS.length) continue;
            out.put(String.valueOf(s.id()), ROW_SLOTS[r] * 9 + COL_SLOTS[c]);
        }
        return out;
    }

    /** 골목 마당 (옛 3번 자리) 칸. */
    public static int yardSlot() {
        TreeSet<Integer> xs = new TreeSet<>(), zs = new TreeSet<>();
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            xs.add(s.x0());
            zs.add(s.z0());
        }
        int c = new ArrayList<>(xs).indexOf(HomesLayout.YARD.x0()), r = new ArrayList<>(zs).indexOf(HomesLayout.YARD.z0());
        return c < 0 || r < 0 ? -1 : ROW_SLOTS[r] * 9 + COL_SLOTS[c];
    }

    /** 그 칸의 번지 (설계 배치, 없으면 null). */
    public static String plotAt(int slot) {
        for (Map.Entry<String, Integer> e : DESIGN.entrySet()) if (e.getValue() == slot) return e.getKey();
        return null;
    }

    /** 집터도 마당도 아닌 빈 칸 (가로 4 × 세로 3 중 남는 칸 — 옛 9번 자리 들판). */
    public static List<Integer> emptyCells() {
        List<Integer> out = new ArrayList<>();
        int yard = yardSlot();
        for (int r : ROW_SLOTS) for (int c : COL_SLOTS) {
            int s = r * 9 + c;
            if (s != yard && !DESIGN.containsValue(s)) out.add(s);
        }
        return out;
    }
}
