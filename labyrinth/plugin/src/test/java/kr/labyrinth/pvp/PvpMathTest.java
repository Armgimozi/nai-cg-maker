package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** PvP 숫자 (pvp_spec §3 표·§4·§5·§8) — 순수. */
class PvpMathTest {

    static final PvpConfig C = PvpConfig.DEFAULT;

    @Test
    void levelCurve() {
        for (int l = 1; l <= 20; l++) assertEquals(2.0, PvpMath.levelMult(C, l), 1e-9, "Lv" + l);
        assertEquals(1.18, PvpMath.levelMult(C, 25), 0.005);
        assertEquals(0.77, PvpMath.levelMult(C, 30), 0.005);
        assertEquals(0.537, PvpMath.levelMult(C, 35), 0.001);
        assertEquals(0.39, PvpMath.levelMult(C, 40), 0.005);
        assertEquals(0.232, PvpMath.levelMult(C, 50), 0.001);
        assertEquals(2.0 * 0.5, PvpMath.levelMult(C.withDamage(0.5, 1.0), 10), 1e-9, "damage_multiplier 를 곱한다");
    }

    @Test
    void bufferHp() {
        assertEquals(42, PvpMath.bufferHp(C, 1), 1e-9);
        assertEquals(210, PvpMath.bufferHp(C, 5), 1e-9);
        assertEquals(420, PvpMath.bufferHp(C, 10), 1e-9);
        assertEquals(840, PvpMath.bufferHp(C, 20), 1e-9);
        assertEquals(900, PvpMath.bufferHp(C, 25), 1e-9);
        assertEquals(1020, PvpMath.bufferHp(C, 35), 1e-9);
        assertEquals(1200, PvpMath.bufferHp(C, 50), 1e-9);
    }

    @Test
    void poolFactor() {
        assertEquals(662.0 / 1502.0, PvpMath.poolFactor(C, 662, 20), 1e-9);
        assertEquals(3107.0 / 4307.0, PvpMath.poolFactor(C, 3107, 50), 1e-9);
        assertEquals(1.0, PvpMath.poolFactor(C, 0, 50), 1e-9, "HP 를 모르면 1");
        // HP 700 대 2,600 → PvP 체력 차이 3.7배 → 2배 쯤 (§3)
        double small = 700 + PvpMath.bufferHp(C, 50), big = 2600 + PvpMath.bufferHp(C, 50);
        assertTrue(big / small < 2.1);
    }

    @Test
    void resilience() {
        assertEquals(0.19, PvpMath.resilience(C, 0, 360, 50), 0.001, "S=360, Lv50");
        assertEquals(0.4 * 57 / (57 + 160.0), PvpMath.resilience(C, 20, 37, 20), 1e-9);
        assertEquals(0.105, PvpMath.resilience(C, 20, 37, 20), 0.001, "§3 표 Lv20 광전사 유리 10.5%");
        assertEquals(0.0, PvpMath.resilience(C, 0, 0, 30), 1e-9);
        assertTrue(PvpMath.resilience(C, 100000, 100000, 1) < 0.40 + 1e-9, "최대 40%");
    }

    @Test
    void crit() {
        assertEquals(1.9, PvpMath.critMultiplier(C, 2.5), 1e-9);
        assertEquals(1.3, PvpMath.critMultiplier(C, 1.5), 1e-9);
        assertEquals(1.6, PvpMath.critMultiplier(C, 2.0), 1e-9);
        assertEquals(2.14, PvpMath.critMultiplier(C, 2.9), 1e-9);
    }

    @Test
    void longFight() {
        assertEquals(1.0, PvpMath.longFight(C, 0), 1e-9);
        assertEquals(1.0, PvpMath.longFight(C, 20), 1e-9);
        assertEquals(0.75, PvpMath.longFight(C, 30), 1e-9);
        assertEquals(0.5, PvpMath.longFight(C, 40), 1e-9);
        assertEquals(0.1, PvpMath.longFight(C, 60), 1e-9);
        assertEquals(0.1, PvpMath.longFight(C, 600), 1e-9, "최소 10%");
    }

    @Test
    void flatHeal() {
        assertEquals(100 * 662.0 / 1502.0, PvpMath.flatHeal(C, 100, 662, 20), 1e-9);
    }

    /** 두 사람 중 높은 레벨을 쓴다 — 고레벨이 저레벨을 칠 때도, 저레벨이 고레벨을 칠 때도 같은 기준 배율. */
    @Test
    void higherLevelIsUsed() {
        assertEquals(50, PvpMath.level(20, 50));
        assertEquals(50, PvpMath.level(50, 20));
        PvpMath.Target low = new PvpMath.Target(20, 662, 20, 37);
        double up = PvpMath.damageFactor(C, 50, low, 1, 1, false);
        double expected = PvpMath.levelMult(C, 50) * (1 - PvpMath.resilience(C, 20, 37, 20)) * 662 / (662 + PvpMath.bufferHp(C, 50));
        assertEquals(expected, up, 1e-9);
        assertTrue(up < PvpMath.damageFactor(C, 20, low, 1, 1, false), "고레벨이 칠 때 배율이 더 낮다");
    }

    /** §3 표: 실제 HP 로 받는 배율 = m × HP비 × (1 − R) (피해 감소 전). */
    @Test
    void spec_table_examples() {
        // Lv35 광전사·수비: HP 2130, S 280, 강인함 20.0%
        PvpMath.Target guard = new PvpMath.Target(35, 2130, 0, 280);
        assertEquals(0.200, PvpMath.resilience(C, 0, 280, 35), 0.001);
        double f = PvpMath.damageFactor(C, 35, guard, 1, 1, false);
        assertEquals(0.537 * 2130 / 3150.0 * 0.8, f, 0.002);
        // Lv50 비전술사·유리: HP 682 S 77 → 6.5%
        assertEquals(0.065, PvpMath.resilience(C, 0, 77, 50), 0.001);
    }

    @Test
    void percentDamageSkipsCurveAndBuffer() {
        PvpMath.Target t = new PvpMath.Target(50, 2000, 0, 0);
        assertEquals(0.5, PvpMath.damageFactor(C, 50, t, 1, 0.5, true), 1e-9, "최대 HP 비율 피해는 스킬·직업·강인함만");
    }

    @Test
    void skillMultRange() {
        assertEquals(1.0, PvpMath.clampSkill(Double.NaN), 1e-9);
        assertEquals(1.0, PvpMath.clampSkill(0), 1e-9);
        assertEquals(0.1, PvpMath.clampSkill(0.05), 1e-9);
        assertEquals(1.0, PvpMath.clampSkill(3), 1e-9);
        assertEquals(0.3, PvpMath.clampSkill(0.3), 1e-9);
    }
}
