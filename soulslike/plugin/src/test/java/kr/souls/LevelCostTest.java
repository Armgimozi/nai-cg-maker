package kr.souls;

import kr.souls.progression.LevelCost;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 레벨 비용 (DESIGN 5.3): 11 까지 300 + 20L, 그 뒤 다크 소울 꼴의 3차식 × 0.6. */
class LevelCostTest {
    private final LevelCost cost = LevelCost.defaults();

    @Test
    void flatPart() {
        assertEquals(320, cost.next(1));
        assertEquals(480, cost.next(9));
        assertEquals(520, cost.next(11));
        assertEquals(480 + 500 + 520, cost.sum(9, 3));
        assertEquals(0, cost.sum(9, 0));
    }

    @Test
    void cubicPart() {
        // x = 13: 0.02·2197 + 3.06·169 + 105.6·13 − 895 = 1038.88, × 0.6 = 623.3
        assertEquals(623, cost.next(12));
        assertTrue(cost.next(12) > cost.next(11), "11 → 12 에서 이어진다");
    }

    @Test
    void neverDecreases() {
        for (int lv = 1; lv < 712; lv++) assertTrue(cost.next(lv + 1) >= cost.next(lv), "레벨 " + lv);
    }
}
