package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class ExplorationMapItemTest {

    @Test
    void fitKeepsWholeGridInside() {
        for (int n = 3; n <= 12; n++) {
            ExplorationMapItem.Fit f = ExplorationMapItem.Fit.of(2 * n, 2 * n - 1);
            assertTrue(f.px() >= 1);
            assertTrue(f.offX() >= 1 && f.offX() + f.px() * (2 * n - 1) <= 127, "가로 n=" + n);
            assertTrue(f.offY() >= 1 && f.offY() + f.px() * 2 * n <= 127, "세로 n=" + n);
        }
        assertEquals(6, ExplorationMapItem.Fit.of(18, 17).px());
    }

    @Test
    void emptyGridIsParchment() {
        int[] px = ExplorationMapItem.pixels(null);
        assertEquals(128 * 128, px.length);
        for (int c : px) assertEquals(ExplorationMapItem.PARCHMENT, c);
    }

    @Test
    void cellsAreDrawnInTheirColour() {
        int[][] g = {{0xffffff, 0x16131b}, {0x5ef2ff, 0xff2a2a}};
        int[] px = ExplorationMapItem.pixels(g);
        ExplorationMapItem.Fit f = ExplorationMapItem.Fit.of(2, 2);
        int cx = f.offX() + f.px() / 2, cy = f.offY() + f.px() / 2;
        assertEquals(0xffffff, px[cy * 128 + cx]);
        assertEquals(0xff2a2a, px[(cy + f.px()) * 128 + cx + f.px()]);
        assertEquals(ExplorationMapItem.FRAME, px[(f.offY() - 1) * 128 + cx]);
    }
}
