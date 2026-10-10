package kr.souls.ui;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 레벨 올리기 "+" 단추의 설명 칸 (5.9, 검토 softcap-dead-points): 무른 상한 위의 한 점이 반올림한 값을 바꾸지 못하면 한 자리 더
 * 보인다 ("공격력 95 → 95" 가 아니라 "95.3 → 95.6"). 보이는 값이 바뀌면 그대로, 정말 그대로면 하나.
 */
class LevelUpTipTest {
    @Test
    void stepShowsOneMoreDigitOnlyWhenRoundingHidesTheGain() {
        assertEquals("72 → 73", LevelUpDialog.step("72", "73", "72.4", "73.1"));
        assertEquals("95.3 → 95.6", LevelUpDialog.step("95", "95", "95.3", "95.6"));
        assertEquals("+22.4% → +22.6%", LevelUpDialog.step("+22%", "+22%", "+22.4%", "+22.6%"));
        assertEquals("95", LevelUpDialog.step("95", "95", "95.0", "95.0"));
        assertEquals("–", LevelUpDialog.step("–", "–", "–", "–"));
    }

    @Test
    void finePercent() {
        assertEquals("0%", StatRows.pct1(0));
        assertEquals("+22.4%", StatRows.pct1(0.224));
        assertEquals("+5.0%", StatRows.pct1(0.05));
        assertEquals("-3.0%", StatRows.pct1(-0.03));
    }
}
