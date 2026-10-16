package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** 판금 4부위 버팀 (look_spec §1.3): 기절·속박·빙결 시간과 밀려나는 세기 — 보스가 한 것은 그대로. */
class CrowdControlTest {

    static final double EPS = 1e-9;

    @Test
    void durationShrinksExceptFromBoss() {
        assertEquals(2.4, CrowdControl.duration(4.0, 0.40, false), EPS);
        assertEquals(4.0, CrowdControl.duration(4.0, 0.40, true), EPS, "보스가 건 것은 그대로");
        assertEquals(4.0, CrowdControl.duration(4.0, 0, false), EPS);
        assertTrue(CrowdControl.HARD.containsAll(java.util.Set.of("stun", "root", "frozen")));
        assertEquals(3, CrowdControl.HARD.size(), "둔화·침묵 등은 버팀이 안 줄인다");
    }

    @Test
    void knockbackShrinksExceptFromBoss() {
        assertEquals(0.4, CrowdControl.knockback(1.0, 0.60, false), EPS);
        assertEquals(1.0, CrowdControl.knockback(1.0, 0.60, true), EPS, "보스가 민 것은 그대로");
        assertEquals(0.0, CrowdControl.knockback(1.0, 1.0, false), EPS, "넉백 면역");
        assertEquals(1.0, CrowdControl.knockback(1.0, 0, false), EPS);
    }
}
