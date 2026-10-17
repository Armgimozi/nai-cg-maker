package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class ExplorationMapItemTest {

    @Test
    void fitKeepsWholeFloorAndBossDoorInside() {
        for (int n = 3; n <= 14; n++) {
            ExplorationMapItem.Fit f = ExplorationMapItem.Fit.of(n);
            assertTrue(f.k() >= 1);
            assertTrue(f.left(0) >= 0 && f.left(n - 1) + f.cell() <= 128, "가로 n=" + n);
            assertTrue(f.top(0) >= 0 && f.top(n - 1) + f.cell() + 2 * f.k() + f.k() / 2 <= 128, "세로 n=" + n);
        }
        assertEquals(6, ExplorationMapItem.Fit.of(4).k()); // 작은 층은 크게
    }

    @Test
    void emptyFloorIsPlainPaper() {
        int[] px = ExplorationMapItem.pixels(null);
        assertEquals(128 * 128, px.length);
        for (int c : px) assertEquals(ExplorationMapItem.PARCHMENT, c);
    }

    @Test
    void roomsHaveInkEdgesAndPassagesBetweenThem() {
        // 2×2: 0 = 시작(파랑) 1 = 아직 안 가 본 곳, 0→1 동쪽 통로 암시, 0→2 남쪽 지나간 통로, 2 = 전투
        int[] fill = {0x3355cc, -2, 0xd9472b, -1};
        byte[] east = {1, 0, 0, 0}, south = {2, 0, 0, 0};
        ExplorationMap.Shape sh = new ExplorationMap.Shape(2, fill, east, south, 2, 0, 0.5, 0.5, 0f, List.of(), List.of());
        int[] px = ExplorationMapItem.pixels(sh);
        ExplorationMapItem.Fit f = ExplorationMapItem.Fit.of(2);
        int cs = f.cell();
        int cx = f.left(0) + cs / 2, cy = f.top(0) + cs / 2;
        assertEquals(0x3355cc, px[cy * 128 + cx]);
        assertEquals(ExplorationMapItem.INK, px[f.top(0) * 128 + cx], "방 테두리");
        assertEquals(ExplorationMapItem.HINT_INK, px[cy * 128 + f.left(0) + cs + f.k() / 2], "동쪽 통로 암시");
        assertEquals(ExplorationMapItem.PASS, px[(f.top(0) + cs + f.k() / 2) * 128 + cx], "남쪽 지나간 통로");
        assertEquals(ExplorationMapItem.PARCHMENT, px[(f.top(0) + cs / 2) * 128 + f.left(1) + cs / 2], "안 가 본 곳 안쪽은 종이");
        assertEquals(ExplorationMapItem.INK, px[f.top(1) * 128 + cx]);
        assertEquals(ExplorationMapItem.PARCHMENT, px[(f.top(1) + cs / 2) * 128 + f.left(1) + cs / 2], "안 보이는 곳");
        int doorY = f.top(1) + cs + f.k() + 1;
        assertEquals(ExplorationMapItem.DOOR, px[doorY * 128 + f.left(0) + cs / 2], "수호자의 문");
    }

    @Test
    void arrowPointsWhereThePlayerLooks() {
        assertEquals(0, ExplorationMapItem.direction(180f));  // 북쪽 = 위
        assertEquals(4, ExplorationMapItem.direction(-90f));  // 동쪽 = 오른쪽
        assertEquals(8, ExplorationMapItem.direction(0f));    // 남쪽 = 아래
        assertEquals(12, ExplorationMapItem.direction(90f));  // 서쪽 = 왼쪽
        assertEquals(-128, ExplorationMapItem.cursorCoord(0));
        assertEquals(127, ExplorationMapItem.cursorCoord(127.9));
    }
}
