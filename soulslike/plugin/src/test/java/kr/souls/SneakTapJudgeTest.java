package kr.souls;

import kr.souls.input.SneakTap;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 웅크리기 짧게 누르기의 판정 (DESIGN 2.1, 3.3), 가짜 시계로. */
class SneakTapJudgeTest {
    @Test
    void shortTapRolls() {
        SneakTap.Judge j = new SneakTap.Judge();
        j.press(100, null);
        SneakTap.Decision d = j.release(104, 5, false, false);
        assertTrue(d.roll());
        assertNull(d.why());
        assertEquals(4, d.held());
    }

    @Test
    void edgeOfWindow() {
        SneakTap.Judge j = new SneakTap.Judge();
        j.press(0, null);
        assertTrue(j.release(5, 5, false, false).roll());
        j.press(10, null);
        SneakTap.Decision d = j.release(16, 5, false, false);
        assertFalse(d.roll());
        assertEquals("hold", d.why());
    }

    @Test
    void comboCancelsRoll() {
        SneakTap.Judge j = new SneakTap.Judge();
        j.press(0, null);
        j.combo("attack");
        j.combo("use");
        SneakTap.Decision d = j.release(2, 5, false, false);
        assertFalse(d.roll());
        assertEquals("attack", d.why(), "처음 조합 입력만 적는다");
    }

    @Test
    void blockedScreenDialog() {
        SneakTap.Judge j = new SneakTap.Judge();
        j.press(0, "dead");
        assertEquals("dead", j.release(1, 5, false, false).why());
        j.press(0, null);
        assertEquals("screen", j.release(1, 5, true, false).why());
        j.press(0, null);
        assertEquals("dialog", j.release(1, 5, false, true).why());
    }

    @Test
    void releaseWithoutPressIsNothing() {
        SneakTap.Judge j = new SneakTap.Judge();
        SneakTap.Decision d = j.release(10, 5, false, false);
        assertFalse(d.roll());
        assertNull(d.why());
        j.combo("attack");
        j.press(20, null);
        assertTrue(j.release(21, 5, false, false).roll(), "누르기 전의 조합 입력은 남지 않는다");
    }
}
