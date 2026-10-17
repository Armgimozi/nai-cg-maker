package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** 이사 기간 (plan §10): 처음 켜진 날부터 n일 · 다시 켜도 다시 세지 않음 · 0 = 없음 · 관리자 날수 · 하루 한 번 안내. */
class GraceRuleTest {

    private static final long D = Grace.DAY_MS;
    private static final long T0 = 1_760_000_000_000L;

    @Test
    void fourteenDaysFromFirstLock() {
        Grace g = new Grace(14, T0);
        assertTrue(g.active(T0));
        assertEquals(14, g.daysLeft(T0));
        assertEquals(14, g.daysLeft(T0 + 1), "올림");
        assertEquals(13, g.daysLeft(T0 + D));
        assertEquals(1, g.daysLeft(T0 + 14 * D - 1));
        assertFalse(g.active(T0 + 14 * D), "14일 뒤 끝");
        assertEquals(0, g.daysLeft(T0 + 20 * D));
    }

    @Test
    void notStartedOrZero() {
        assertFalse(new Grace(14, 0).active(T0), "잠금이 켜진 적 없음");
        assertFalse(new Grace(0, T0).active(T0), "0일 = 이사 기간 없음");
        assertEquals(0, new Grace(0, T0).daysLeft(T0));
        assertEquals(0, new Grace(-5, -1).days());
    }

    @Test
    void startsOnlyOnce() {
        assertTrue(Grace.shouldStart(true, 0));
        assertFalse(Grace.shouldStart(true, T0), "다시 켜도 다시 세지 않음");
        assertFalse(Grace.shouldStart(false, 0), "꺼져 있으면 시작 안 함");
    }

    @Test
    void adminOverride() {
        assertEquals(14, Grace.effectiveDays(null, 14));
        assertEquals(3, Grace.effectiveDays(3, 14));
        assertEquals(0, Grace.effectiveDays(0, 14), "관리자가 0일로");
        assertEquals(14, Grace.effectiveDays(-1, 14));
    }

    @Test
    void noticeOncePerDay() {
        long today = Grace.day(T0);
        assertTrue(Grace.noticeDue(-1, today));
        assertFalse(Grace.noticeDue(today, today));
        assertTrue(Grace.noticeDue(today - 1, today));
        assertEquals(today + 1, Grace.day(T0 + D));
    }
}
