package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.UUID;
import kr.labyrinth.core.DeathPenaltyRules;
import org.junit.jupiter.api.Test;

/** 0.3.7 광산 PvP '싸우는 중' 시계 ({@link MineCombat}): 10초 안에 때렸거나 맞았으면 싸우는 중 — 미궁 퇴장 시전과 같은 10초. */
class MineCombatTest {

    private static final UUID ANN = new UUID(1, 1);
    private static final UUID BOB = new UUID(2, 2);
    private static final UUID CAT = new UUID(3, 3);

    @Test
    void markCountsForBothSides() {
        MineCombat c = new MineCombat();
        c.mark(ANN, BOB, 1_000);
        assertEquals(0, c.since(ANN, 1_000), "때린 쪽도 싸우는 중");
        assertEquals(500, c.since(BOB, 1_500), "맞은 쪽");
        assertEquals(-1, c.since(CAT, 1_500), "곁에 있던 사람은 아님");
        assertEquals(-1, c.lastHurt(BOB), "피했으면(피해 0) 맞은 시각은 없음 — 시전을 끊지 않음");
    }

    @Test
    void hurtIsOnlyTheVictimAndAlsoCountsAsCombat() {
        MineCombat c = new MineCombat();
        c.hurt(BOB, 2_000);
        assertEquals(2_000, c.lastHurt(BOB));
        assertEquals(0, c.since(BOB, 2_000));
        assertEquals(-1, c.lastHurt(ANN));
        assertEquals(-1, c.since(ANN, 2_000));
        c.mark(ANN, BOB, 3_000);
        assertEquals(2_000, c.lastHurt(BOB), "mark 는 맞은 시각을 바꾸지 않음");
        c.hurt(BOB, 3_000);
        assertTrue(c.lastHurt(BOB) > 2_000, "시전 시작(2초) 뒤에 맞음 → 끊김");
    }

    @Test
    void tenSecondWindow() {
        MineCombat c = new MineCombat();
        c.mark(ANN, BOB, 0);
        assertTrue(DeathPenaltyRules.inCombat(c.since(BOB, 9_990)), "9.99초");
        assertFalse(DeathPenaltyRules.inCombat(c.since(BOB, 10_000)), "10초 = 끝");
        assertFalse(DeathPenaltyRules.inCombat(c.since(CAT, 0)), "기록 없음");
        c.mark(BOB, CAT, 9_000);
        assertTrue(DeathPenaltyRules.inCombat(c.since(BOB, 18_000)), "다시 때리면 새로 10초");
    }

    @Test
    void forgetAndClear() {
        MineCombat c = new MineCombat();
        c.mark(ANN, BOB, 0);
        c.hurt(BOB, 0);
        c.forget(BOB);
        assertEquals(-1, c.since(BOB, 1));
        assertEquals(-1, c.lastHurt(BOB));
        assertEquals(1, c.since(ANN, 1), "다른 사람 기록은 남음");
        c.forget(null);
        c.clear();
        assertEquals(-1, c.since(ANN, 1));
        c.mark(null, null, 5);
        c.hurt(null, 5);
        assertEquals(-1, c.since(null, 5));
        assertEquals(-1, c.lastHurt(null));
    }

    @Test
    void clockGoingBackwardsIsNotCombat() {
        MineCombat c = new MineCombat();
        c.mark(ANN, BOB, 50_000);
        long since = c.since(BOB, 40_000);
        assertTrue(since < 0);
        assertFalse(DeathPenaltyRules.inCombat(since), "시계가 뒤로 가면 싸우는 중이 아닌 것으로");
    }
}
