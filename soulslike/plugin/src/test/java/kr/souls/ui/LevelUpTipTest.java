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
        assertEquals("122.4% → 122.6%", LevelUpDialog.step("122%", "122%", "122.4%", "122.6%"));
        assertEquals("95", LevelUpDialog.step("95", "95", "95.0", "95.0"));
        assertEquals("–", LevelUpDialog.step("–", "–", "–", "–"));
    }

    /** 속도는 기준 100% (표는 정수, 설명 칸은 한 자리 더): "0%" "+0.5%" 같은 계산기 꼴이 아니다 (DECISIONS 2026-10-10). */
    @Test
    void finePercent() {
        assertEquals("100.0%", StatRows.pct1(0));
        assertEquals("122.4%", StatRows.pct1(0.224));
        assertEquals("105.0%", StatRows.pct1(0.05));
        assertEquals("97.0%", StatRows.pct1(-0.03));
    }

    @Test
    void tablePercentIsBase100() {
        assertEquals("100%", StatRows.pct(0));
        assertEquals("100%", StatRows.pct(0.004));
        assertEquals("103%", StatRows.pct(0.03));
        assertEquals("85%", StatRows.pct(-0.15));
    }
}
