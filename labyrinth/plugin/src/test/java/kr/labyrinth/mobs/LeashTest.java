package kr.labyrinth.mobs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/**
 * 부드러운 줄 (미믹, 0.3.6 리뷰): 줄 밖의 대상은 줄 끝까지만 쫓아가 버티고(순간이동으로 튕겨 돌아오지 않음), 밀려나면 걸어서 돌아오고,
 * 도약은 줄 끝 근처 대상에게만.
 */
class LeashTest {

    static final double R = 8;

    @Test
    void chasesInsideHoldsAtTheEdgeReturnsWhenPushedOut() {
        // 대상이 줄 안 → 어디에 있든 쫓는다 (밀려나 있어도 대상 쪽으로)
        for (double own : new double[] {0, 4, 7.5, 9, 11}) assertEquals(Leash.Move.CHASE, Leash.decide(own, 6, R), "own " + own);
        // 대상이 줄 밖 (원거리 공격수가 10~14칸) → 줄 끝 가까이까지 가고, 거기서 멈춰 버틴다
        for (double t : new double[] {9, 12, 14, 30}) {
            assertEquals(Leash.Move.CHASE, Leash.decide(2, t, R), "가운데에서는 다가감 " + t);
            assertEquals(Leash.Move.HOLD, Leash.decide(R - 0.5, t, R), "줄 끝에서 버팀 " + t);
            assertEquals(Leash.Move.HOLD, Leash.decide(R + 0.3, t, R), "살짝 넘으면 버팀 " + t);
            assertEquals(Leash.Move.RETURN, Leash.decide(R + 1, t, R), "밀려나면 돌아옴 " + t);
        }
        // 버티는 띠 안에서 다시 다가가지 않는다 (줄 끝에서 들락날락 없음)
        assertEquals(Leash.Move.HOLD, Leash.decide(R - Leash.HOLD_BAND, 20, R));
        assertEquals(Leash.Move.CHASE, Leash.decide(R - Leash.HOLD_BAND - 0.01, 20, R));
    }

    @Test
    void lungesOnlyAtTargetsNearTheEdge() {
        assertTrue(Leash.canLunge(5, R));
        assertTrue(Leash.canLunge(R + Leash.LUNGE_MARGIN, R), "줄 끝에서 한 번 덮칠 수 있음");
        assertFalse(Leash.canLunge(R + Leash.LUNGE_MARGIN + 0.1, R), "멀리 있는 대상에게 도약해 줄을 벗어나지 않음");
    }
}
