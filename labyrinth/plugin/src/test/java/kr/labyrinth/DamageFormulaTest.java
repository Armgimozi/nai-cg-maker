package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.random.RandomGenerator;
import kr.labyrinth.combat.DamageFormula;
import org.junit.jupiter.api.Test;

class DamageFormulaTest {

    /** 항상 같은 값을 내는 난수 (판정 고정). */
    private static RandomGenerator fixed(double v) {
        return new RandomGenerator() {
            @Override
            public long nextLong() { return 0; }

            @Override
            public double nextDouble() { return v; }
        };
    }

    private static DamageFormula.Input in(double amount, double crit, double evasion, double defense, double dr,
                                          double block, boolean skill, double skillDmg) {
        return new DamageFormula.Input(amount, skill, 0, skillDmg, crit, 1.5, true, evasion, true, defense, false, dr, 0,
                block, true);
    }

    @Test
    void defenseFormula() {
        assertEquals(1.0, DamageFormula.defenseFactor(0), 1e-9);
        assertEquals(0.5, DamageFormula.defenseFactor(100), 1e-9);
        assertEquals(1.0, DamageFormula.defenseFactor(-50), 1e-9);
        var out = DamageFormula.compute(in(100, 0, 0, 100, 0, 0, false, 0), fixed(0.99));
        assertEquals(50, out.damage(), 1e-9);
    }

    @Test
    void critMultipliesBeforeDefense() {
        var out = DamageFormula.compute(in(100, 0.5, 0, 0, 0, 0, false, 0), fixed(0.1));
        assertTrue(out.crit());
        assertEquals(150, out.damage(), 1e-9);
        var noCrit = DamageFormula.compute(in(100, 0.5, 0, 0, 0, 0, false, 0), fixed(0.9));
        assertFalse(noCrit.crit());
        assertEquals(100, noCrit.damage(), 1e-9);
    }

    /** PvP (pvp_spec §3·§5): 방어 × defenseScale(0) = 방어 무시와 같고, 치명 추가 피해 × 0.6 → 2.5 가 1.9. */
    @Test
    void pvpDefenseAndCritScales() {
        double defense = 120;
        var scaled = DamageFormula.compute(in(100, 0, 0, defense * 0.0, 0, 0, false, 0), fixed(0.99));
        var ignored = DamageFormula.compute(new DamageFormula.Input(100, false, 0, 0, 0, 1.5, true, 0, true, defense, true, 0, 0,
                0, true), fixed(0.99));
        assertEquals(ignored.damage(), scaled.damage(), 1e-9, "defenseScale 0 = 방어 무시");
        assertEquals(1.9, DamageFormula.scaledCritDamage(2.5, 0.6), 1e-9);
        assertEquals(2.5, DamageFormula.scaledCritDamage(2.5, 1.0), 1e-9, "기본 1 = 그대로");
        assertEquals(1.0, DamageFormula.scaledCritDamage(0.8, 0.6), 1e-9, "1 아래는 1");
        var crit = DamageFormula.compute(new DamageFormula.Input(100, false, 0, 0, 1.0, DamageFormula.scaledCritDamage(2.5, 0.6),
                true, 0, true, 0, false, 0, 0, 0, true), fixed(0.0));
        assertTrue(crit.crit());
        assertEquals(190, crit.damage(), 1e-9);
    }

    @Test
    void evasionNegatesDamage() {
        var out = DamageFormula.compute(in(100, 0, 0.3, 0, 0, 0, false, 0), fixed(0.1));
        assertTrue(out.evaded());
        assertEquals(0, out.damage(), 1e-9);
    }

    @Test
    void reductionTakenSkillAndBlock() {
        // 스킬 +20%, 방어 25 → ×0.8, 피해감소 10%, 막기(×0.4)
        var input = new DamageFormula.Input(100, true, 0.1, 0.2, 0, 1.5, true, 0, true, 25, false, 0.1, 0.5, 0.4, true);
        var out = DamageFormula.compute(input, fixed(0.0));
        double expected = 100 * 1.1 * 1.2 * 0.8 * 0.9 * 1.5 * 0.4;
        assertTrue(out.blocked());
        assertEquals(expected, out.damage(), 1e-9);
    }

    @Test
    void trueDamageIgnoresDefense() {
        var input = new DamageFormula.Input(80, false, 0, 0, 0, 1.5, false, 0.9, false, 500, true, 0, 0, 0.9, false);
        var out = DamageFormula.compute(input, fixed(0.0));
        assertFalse(out.evaded());
        assertFalse(out.blocked());
        assertEquals(80, out.damage(), 1e-9);
    }
}
