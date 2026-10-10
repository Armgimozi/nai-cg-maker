package kr.souls;

import kr.souls.progression.StatCurves;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 능력치 곡선 (DESIGN 5.2): 사이는 직선, 양 끝 밖은 끝 값, 그리고 설계 표의 눈금. */
class StatCurvesTest {
    private final StatCurves c = StatCurves.defaults();

    @Test
    void curveInterpolatesAndClamps() {
        StatCurves.Curve k = StatCurves.Curve.of(10, 0, 20, 10);
        assertEquals(0, k.at(1), 1e-9);
        assertEquals(5, k.at(15), 1e-9);
        assertEquals(10, k.at(99), 1e-9);
    }

    @Test
    void designAnchors() {
        assertEquals(400, c.maxHealth.at(10), 1e-9);
        assertEquals(1500, c.maxHealth.at(99), 1e-9);
        assertEquals(100, c.maxStamina.at(10), 1e-9);
        assertEquals(60, c.maxMana.at(10), 1e-9);
        assertEquals(40, c.equipLoad.at(10), 1e-9);
        assertEquals(0, c.moveSpeed.at(10), 1e-9);
        assertEquals(0, c.statusResist.at(10), 1e-9);
        assertEquals(99, c.max);
    }

    /** 검토 dex-too-weak·slow-stats-feel-dead: 민첩의 첫 열 점 (10 → 20) 이 이동 속도 +5%, 공격 속도 +10% 를 준다 (앞쪽을 올린 판). */
    @Test
    void dexterityIsFrontLoaded() {
        assertEquals(0.05, c.moveSpeed.at(20), 1e-9);
        assertEquals(0.13, c.moveSpeed.at(99), 1e-9);
        assertEquals(0.10, c.attackSpeed.at(20), 1e-9);
        double first = c.moveSpeed.at(20) - c.moveSpeed.at(10);
        double late = c.moveSpeed.at(99) - c.moveSpeed.at(60);
        assertTrue(first > late, "앞쪽 열 점이 뒤쪽 39 점보다 많이 준다");
    }

    /** 검토 slow-stats-feel-dead: 근력·지능 보정과 기력 회복의 10 → 40 이 가팔라졌다 (한 점에 보정 약 +0.02, 회복 +1.5%). 상한은 그대로. */
    @Test
    void earlyPointsCount() {
        assertEquals(0.13, c.scaling.at(10), 1e-9);
        assertEquals(0.35, c.scaling.at(20), 1e-9);
        assertEquals(0.52, c.scaling.at(30), 1e-9);
        assertEquals(0.68, c.scaling.at(40), 1e-9);
        assertEquals(1.0, c.scaling.at(99), 1e-9);
        assertEquals(1.15, c.regenScale.at(20), 1e-9);
        assertEquals(1.30, c.regenScale.at(40), 1e-9);
        assertEquals(1.40, c.regenScale.at(99), 1e-9);
        // 10 → 11 의 한 점도 눈에 보인다: 이동 속도 +0.5%, 회복 +1.5%
        assertEquals(0.005, c.moveSpeed.at(11), 1e-9);
        assertEquals(1.015, c.regenScale.at(11), 1e-9);
    }

    /** 모든 곡선은 줄지 않는다 (능력치를 올려 손해 보는 일이 없다). */
    @Test
    void curvesNeverDecrease() {
        StatCurves.Curve[] all = {c.scaling, c.maxHealth, c.vigorDefense, c.maxMana, c.magicDefense, c.maxStamina, c.regenScale, c.equipLoad,
                c.moveSpeed, c.attackSpeed, c.statusResist};
        for (StatCurves.Curve k : all) {
            for (int x = 1; x < 99; x++) assertTrue(k.at(x + 1) >= k.at(x) - 1e-9, "곡선이 " + x + " 에서 준다: " + k.points());
        }
        for (int x = 1; x < 99; x++) assertTrue(c.memorySlots.at(x + 1) >= c.memorySlots.at(x));
    }

    /** 무른 상한: 40 이후의 한 점은 10..20 의 한 점보다 적게 준다 (최대 HP, 스태미나, 마나). */
    @Test
    void softCaps() {
        for (StatCurves.Curve k : new StatCurves.Curve[] {c.maxHealth, c.maxStamina, c.maxMana}) {
            double early = (k.at(20) - k.at(10)) / 10;
            double late = (k.at(99) - k.at(60)) / 39;
            assertTrue(late < early / 2, "무른 상한: " + k.points());
        }
    }
}
