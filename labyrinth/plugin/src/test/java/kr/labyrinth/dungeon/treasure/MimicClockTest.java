package kr.labyrinth.dungeon.treasure;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/**
 * 미믹이 달아날 시간 (0.3.6 리뷰): 근처에 사람이 있을 때만 흐른다 — 상자를 열고 멀리 가서 기다리기만 해서는 한 단계 좋은 상자를
 * 공짜로 받을 수 없다. 맞으면 적어도 12초로 늘고, 렉으로 한꺼번에 줄지 않는다.
 */
class MimicClockTest {

    static final long LOCK = 30_000, ENGAGED = 12_000;

    /** 2틱(100ms)마다 부른다. @return 다 될 때까지 흐른 시간(ms), 안 되면 -1 */
    private static long run(MimicClock c, long from, long until, boolean near) {
        for (long t = from; t <= until; t += 100) if (c.tick(t, near, false)) return t - from;
        return -1;
    }

    @Test
    void waitingFarAwayNeverRunsOut() {
        MimicClock c = new MimicClock(LOCK, ENGAGED);
        assertEquals(-1, run(c, 0, 10 * 60_000, false), "10분을 멀리서 기다려도 달아나지 않음");
        assertEquals(LOCK, c.remaining());
    }

    @Test
    void runsOutAfterLockSecondsNearby() {
        MimicClock c = new MimicClock(LOCK, ENGAGED);
        long took = run(c, 0, 60_000, true);
        assertTrue(took >= LOCK - 100 && took <= LOCK + 100, "근처에 있으면 30초 " + took);
    }

    @Test
    void onlyTimeNearbyCounts() {
        MimicClock c = new MimicClock(LOCK, ENGAGED);
        assertFalse(c.tick(0, true, false));
        run(c, 100, 20_000, true);                       // 20초 근처
        assertEquals(-1, run(c, 20_100, 80_000, false)); // 1분 멀리
        long took = run(c, 80_100, 120_000, true);       // 다시 근처 → 남은 10초
        assertTrue(took >= 9_800 && took <= 10_200, "남은 시간 " + took);
    }

    @Test
    void hitsExtendToEngagedAndLagIsCapped() {
        MimicClock c = new MimicClock(LOCK, ENGAGED);
        c.tick(0, true, false);
        run(c, 100, 28_000, true);
        assertTrue(c.remaining() < 3_000);
        assertFalse(c.tick(28_100, true, true), "맞으면 늘어남");
        assertEquals(ENGAGED, c.remaining(), 200);
        // 렉 (10초 멈춤) → 한 번에 MAX_STEP 만큼만
        long before = c.remaining();
        c.tick(38_100, true, false);
        assertEquals(before - MimicClock.MAX_STEP_MS, c.remaining());
    }
}
