package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.stats.XpCurve;
import org.junit.jupiter.api.Test;

class XpCurveTest {

    private final XpCurve curve = XpCurve.DEFAULT;

    @Test
    void matchesGddTable() {
        // GDD §16.1: L1→2: 100, L10: 1,652, L25: 6,959, L40: 14,694, L49: 20,308
        assertEquals(100, curve.xpToNext(1));
        assertEquals(1652, curve.xpToNext(10));
        assertEquals(6959, curve.xpToNext(25));
        assertEquals(14694, curve.xpToNext(40));
        assertEquals(20308, curve.xpToNext(49));
        assertEquals(0, curve.xpToNext(50));
    }

    @Test
    void totalToMaxIsAbout395k() {
        long total = curve.totalTo(50);
        assertTrue(total > 380_000 && total < 410_000, "누적 " + total);
    }

    @Test
    void applyLevelsUpAcrossMultipleLevels() {
        assertArrayEquals(new long[] {1, 99}, curve.apply(1, 0, 99));
        assertArrayEquals(new long[] {2, 0}, curve.apply(1, 0, 100));
        long need12 = curve.xpToNext(1) + curve.xpToNext(2);
        assertArrayEquals(new long[] {3, 5}, curve.apply(1, 0, need12 + 5));
    }

    @Test
    void capsAtMaxLevel() {
        assertArrayEquals(new long[] {50, 0}, curve.apply(49, 0, 10_000_000));
        assertArrayEquals(new long[] {50, 0}, curve.apply(50, 0, 500));
    }
}
