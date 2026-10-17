package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.homes.HomesLayout;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import org.junit.jupiter.api.Test;

/**
 * 집 고르기 지도 (0.3.7, plan §1.2): 윗줄 1 2 [마당] 3 · 가운데 4 5 6 7 · 아랫줄 [들판] 8 9 10, 가운데 세로줄 = 골목.
 * 칸 ↔ 번지가 서로 맞고, 표지판 글·들어설 때 글·조사가 맞다.
 */
class ClaimMapTest {

    @Test
    void designLayoutSlots() {
        Map<String, Integer> m = ClaimMap.DESIGN;
        assertEquals(10, m.size());
        // 줄 1 (z 48): 1 · 2 · 마당 · 3
        assertEquals(1 * 9 + 2, m.get("1"));
        assertEquals(1 * 9 + 3, m.get("2"));
        assertEquals(1 * 9 + 5, ClaimMap.yardSlot());
        assertEquals(1 * 9 + 6, m.get("3"));
        // 줄 3 (z 69): 4 5 | 6 7
        assertEquals(3 * 9 + 2, m.get("4"));
        assertEquals(3 * 9 + 3, m.get("5"));
        assertEquals(3 * 9 + 5, m.get("6"));
        assertEquals(3 * 9 + 6, m.get("7"));
        // 줄 4 (z 84): 들판 · 8 | 9 10
        assertEquals(List.of(4 * 9 + 2), ClaimMap.emptyCells());
        assertEquals(4 * 9 + 3, m.get("8"));
        assertEquals(4 * 9 + 5, m.get("9"));
        assertEquals(4 * 9 + 6, m.get("10"));
    }

    @Test
    void slotsAreDistinctAndInverse() {
        Set<Integer> seen = new HashSet<>();
        for (Map.Entry<String, Integer> e : ClaimMap.DESIGN.entrySet()) {
            assertTrue(seen.add(e.getValue()), "겹친 칸 " + e);
            assertEquals(e.getKey(), ClaimMap.plotAt(e.getValue()));
            int col = e.getValue() % 9;
            assertFalse(col == ClaimMap.ALLEY_COL, "골목 칸에 집터가 없음");
            assertTrue(e.getValue() / 9 != ClaimMap.LANTERN_ROW && e.getValue() / 9 != ClaimMap.WELL_ROW, "거리 줄에 집터가 없음");
        }
        assertNull(ClaimMap.plotAt(0));
        for (int s : ClaimMap.EXTRA_SLOTS) assertFalse(seen.contains(s), "convert 집터 칸이 겹치지 않음");
        assertTrue(ClaimMap.yardSlot() > 0 && !seen.contains(ClaimMap.yardSlot()));
    }

    @Test
    void westToEastAndNorthToSouth() {
        // 지도 칸 순서가 실제 배치와 같음 (서 → 동 = 왼쪽 → 오른쪽, 북 → 남 = 위 → 아래)
        for (HomesLayout.Spec a : HomesLayout.PLOTS) for (HomesLayout.Spec b : HomesLayout.PLOTS) {
            int sa = ClaimMap.DESIGN.get(String.valueOf(a.id())), sb = ClaimMap.DESIGN.get(String.valueOf(b.id()));
            if (a.x0() < b.x0()) assertTrue(sa % 9 < sb % 9, a.id() + " < " + b.id());
            if (a.z0() < b.z0()) assertTrue(sa / 9 < sb / 9, a.id() + " ^ " + b.id());
        }
    }

    @Test
    void signAndEnterTexts() {
        PlotGeom g = HomesLayout.geoms(6, 24).get(2);
        assertEquals("3번지", g.label());
        assertEquals(List.of("<b>[3번지]</b>", "비어 있음", "", "<gray>/미궁 집</gray>"), PlotSigns.lines(g, PlotInfo.empty(g, true)));
        PlotInfo owned = new PlotInfo(g, java.util.UUID.randomUUID(), "하린", "하린의 집", List.of(), List.of(), true, 1, 1);
        assertEquals(List.of("<b>[3번지]</b>", "하린", "", "<gray>/미궁 집</gray>"), PlotSigns.lines(g, owned), "기본 이름은 줄을 비움");
        PlotInfo named = new PlotInfo(g, java.util.UUID.randomUUID(), "하린", "등불 아래 작은 집", List.of(), List.of(), true, 1, 1);
        assertEquals("등불 아래 작은 집", PlotSigns.lines(g, named).get(2));
        assertTrue(PlotSigns.enterLine(g, owned).contains("3번지") && PlotSigns.enterLine(g, owned).contains("하린의 집"));
        assertTrue(PlotSigns.enterLine(g, PlotInfo.empty(g, true)).contains("빈 집"));
        assertEquals("1234567890ab", PlotSigns.cut("1234567890abcdef", 12));
    }

    @Test
    void koreanParticles() {
        assertEquals("3번지를", PlayUi.object("3번지"));
        assertEquals("10번지를", PlayUi.object("10번지"));
        assertEquals("c1을", PlayUi.object("c1"));
        assertEquals("c2를", PlayUi.object("c2"));
        assertEquals("집을", PlayUi.object("집"));
        assertEquals("24시간", PlayUi.duration(1440));
        assertEquals("1시간 30분", PlayUi.duration(90));
        assertEquals("10분", PlayUi.duration(10));
        assertEquals("바로", PlayUi.duration(0));
    }
}
