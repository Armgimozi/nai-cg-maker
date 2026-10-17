package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import kr.labyrinth.homes.HomesLayout;
import kr.labyrinth.homes.PlotGeom;
import org.junit.jupiter.api.Test;

/** 집터 색인 (0.3.7): 무작위 10만 점 = 전수 · 청크 경계 · 높이 창 · convert 집터. */
class PlotIndexTest {

    private static List<PlotGeom> layout() {
        List<PlotGeom> all = new ArrayList<>(HomesLayout.geoms(6, 24));
        all.add(new PlotStore.Custom("c1", 1, -100, -100, -69, -69, 60, 107, 68, Double.NaN, Double.NaN, Double.NaN, 0f).geom());
        all.add(new PlotStore.Custom("c2", 2, 15, 15, 17, 17, 0, 10, 2, Double.NaN, Double.NaN, Double.NaN, 0f).geom()); // 청크 0/1 경계
        return all;
    }

    private static PlotGeom brute(List<PlotGeom> all, int x, int y, int z) {
        for (PlotGeom p : all) if (p.contains(x, y, z)) return p;
        return null;
    }

    @Test
    void randomPointsMatchBruteForce() {
        List<PlotGeom> all = layout();
        PlotIndex idx = new PlotIndex(all);
        Random r = new Random(370);
        int hits = 0;
        for (int i = 0; i < 100_000; i++) {
            int x = -200 + r.nextInt(240), z = -120 + r.nextInt(240), y = 50 + r.nextInt(70);
            PlotGeom want = brute(all, x, y, z);
            assertSame(want, idx.at(x, y, z), "(" + x + ", " + y + ", " + z + ")");
            if (want != null) hits++;
        }
        assertTrue(hits > 1000, "점이 집터에 충분히 떨어져야 시험이 뜻이 있음: " + hits);
    }

    @Test
    void heightWindowAndColumns() {
        PlotIndex idx = new PlotIndex(HomesLayout.geoms(6, 24));
        PlotGeom p3 = idx.byId("3");
        assertNotNull(p3);
        assertEquals(68, p3.floorY());
        assertEquals(62, p3.yMin());
        assertEquals(92, p3.yMax());
        int x = -120, z = 50;
        assertSame(p3, idx.at(x, 62, z), "바닥 −6 은 창 안");
        assertNull(idx.at(x, 61, z), "바닥 −7 은 그 밖");
        assertSame(p3, idx.at(x, 92, z), "바닥 +24 는 창 안");
        assertNull(idx.at(x, 93, z), "바닥 +25 는 그 밖");
        assertSame(p3, idx.column(x, z), "열은 높이 무관");
        assertNull(idx.at(-130, 70, 50), "3번 서쪽 울타리 줄 (x −130) 은 집터 아님");
        assertNull(idx.column(-147, 70), "가운데 골목");
    }

    @Test
    void chunkEdges() {
        PlotIndex idx = new PlotIndex(layout());
        PlotGeom c2 = idx.byId("c2");
        // c2 = x 15..17 · z 15..17 (청크 0 과 1 에 걸침)
        assertSame(c2, idx.at(15, 5, 15));
        assertSame(c2, idx.at(16, 5, 16));
        assertSame(c2, idx.at(17, 5, 17));
        assertNull(idx.at(14, 5, 15));
        assertNull(idx.at(18, 5, 17));
        assertTrue(idx.chunkHasPlot(0, 0) && idx.chunkHasPlot(1, 1) && idx.chunkHasPlot(0, 1) && idx.chunkHasPlot(1, 0));
        assertFalse(idx.chunkHasPlot(2, 2));
        // 음수 좌표 청크 (−1 >> 4 = −1)
        PlotGeom p1 = idx.byId("1");
        assertSame(p1, idx.at(-178, 70, 48));
        assertSame(p1, idx.at(-165, 70, 61));
        assertTrue(idx.near(-176, 50));
    }

    @Test
    void customPlotsAndOrder() {
        PlotIndex idx = new PlotIndex(layout());
        assertEquals(12, idx.size());
        assertEquals("1", idx.all().get(0).id());
        assertEquals("10", idx.all().get(9).id());
        assertEquals("c1", idx.all().get(10).id(), "convert 집터는 구역 집터 뒤 (key 100 + n)");
        assertSame(idx.byId("C1"), idx.byId("c1"), "대소문자 무관");
        assertEquals(101, idx.byId("c1").key());
        assertTrue(idx.byId("c1").custom());
        assertSame(idx.byId("c1"), idx.byKey(101));
        assertNotNull(idx.overlapping(-90, -90, -80, -80, 60, 70), "convert 겹침 검사");
        assertNull(idx.overlapping(-90, -90, -80, -80, 108, 120), "높이가 안 겹치면 됨");
    }

    @Test
    void duplicatesIgnored() {
        List<PlotGeom> all = new ArrayList<>(HomesLayout.geoms(6, 24));
        all.add(HomesLayout.geoms(6, 24).get(0));
        PlotIndex idx = new PlotIndex(all);
        assertEquals(10, idx.size());
        assertTrue(PlotIndex.EMPTY.isEmpty());
        assertNull(PlotIndex.EMPTY.at(0, 64, 0));
    }
}
