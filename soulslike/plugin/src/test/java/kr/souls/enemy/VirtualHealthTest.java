package kr.souls.enemy;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * M1 P1b: 가상 체력 (enemy/VirtualHealth, DESIGN 6.1). 최대치 = enemies.yml hp × 난이도 enemy-health (생길 때 한 번), 깎이면 0 에서 멈추고,
 * regen-after 틱이 지나면 다 찬다 (경계는 가짜 시계로 정확히, M1_PLAN 0.11).
 */
class VirtualHealthTest {
    private static final double EPS = 1e-9;

    @Test
    void maxIsBaseTimesDifficulty() {
        assertEquals(1000, VirtualHealth.maxFor(1000, 1.0), EPS);
        assertEquals(1300, VirtualHealth.maxFor(1000, 1.3), EPS, "어려움 (enemy-health 1.3)");
        assertEquals(800, VirtualHealth.maxFor(1000, 0.8), EPS);
        assertEquals(1000, VirtualHealth.maxFor(1000, Double.NaN), EPS, "틀린 배율은 1");
        assertEquals(1000, VirtualHealth.maxFor(1000, 0), EPS);
        assertEquals(1000, VirtualHealth.maxFor(1000, -2), EPS);
        assertEquals(1, VirtualHealth.maxFor(0, 1), EPS, "1 밑으로 내려가지 않는다");
        assertEquals(1, VirtualHealth.maxFor(0.2, 0.5), EPS);
        VirtualHealth v = new VirtualHealth(VirtualHealth.maxFor(1000, 1.3), 0);
        assertEquals(1300, v.max(), EPS);
        assertEquals(1300, v.hp(0), EPS, "생기면 가득");
    }

    @Test
    void hurtClampsAtZeroAndIgnoresBadAmounts() {
        VirtualHealth v = new VirtualHealth(100, 0);
        assertEquals(100 - 83.33, v.hurt(83.33, 10), EPS);
        assertEquals(100 - 83.33, v.hurt(0, 11), EPS, "0 은 깎지 않는다");
        assertEquals(100 - 83.33, v.hurt(-5, 11), EPS);
        assertEquals(100 - 83.33, v.hurt(Double.NaN, 11), EPS);
        assertEquals(10, v.lastHurt(), "깎지 않은 한 대는 시계를 건드리지 않는다");
        assertFalse(v.dead());
        assertEquals(0, v.hurt(1e300, 12), EPS);
        assertTrue(v.dead());
        assertEquals(0, v.hurt(5, 13), EPS, "쓰러진 뒤에는 그대로");
    }

    @Test
    void regenExactlyAfterTheWindow() {
        VirtualHealth v = new VirtualHealth(1000, 60);
        v.hurt(300, 100);
        assertEquals(700, v.hp(100), EPS);
        assertEquals(700, v.hp(159), EPS, "59틱 뒤는 아직");
        assertEquals(1000, v.hp(160), EPS, "60틱 뒤 다 찬다");
        // 맞을 때마다 다시 센다
        v.hurt(100, 200);
        v.hurt(100, 250);
        assertEquals(800, v.hp(309), EPS, "마지막 한 대 (250) 에서 59틱");
        assertEquals(1000, v.hp(310), EPS);
        // 차오르기 전에 맞으면 남은 체력에서 깎는다 (먼저 찼으면 찬 값에서)
        v.hurt(500, 400);
        assertEquals(500, v.hurt(0.0, 459), EPS);
        assertEquals(900, v.hurt(100, 460), EPS, "460 에 다 찬 뒤 깎인다");
    }

    @Test
    void noRegenWhenOffOrDead() {
        VirtualHealth off = new VirtualHealth(100, 0);
        off.hurt(40, 0);
        assertEquals(60, off.hp(1_000_000), EPS, "regen-after 0 은 차지 않는다");
        VirtualHealth dead = new VirtualHealth(100, 60);
        dead.hurt(100, 0);
        assertEquals(0, dead.hp(1_000), EPS, "쓰러진 적은 차지 않는다");
        assertTrue(dead.dead());
        dead.fill();
        assertEquals(100, dead.hp(1_001), EPS);
    }

    @Test
    void badMax() {
        assertEquals(1, new VirtualHealth(Double.NaN, 0).max(), EPS);
        assertEquals(1, new VirtualHealth(-3, 0).max(), EPS);
        assertEquals(0, new VirtualHealth(10, -4).regenAfter());
    }
}
