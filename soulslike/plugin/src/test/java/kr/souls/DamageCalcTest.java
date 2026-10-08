package kr.souls;

import kr.souls.combat.DamageCalc;
import kr.souls.progression.StatCurves;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 피해 셈 (DESIGN 3.7, 5.2). */
class DamageCalcTest {
    private final StatCurves c = StatCurves.defaults();

    @Test
    void reduce() {
        assertEquals(0, DamageCalc.reduce(0, 50), 1e-9);
        assertEquals(50, DamageCalc.reduce(100, 100), 1e-9);
        assertEquals(100, DamageCalc.reduce(100, 0), 1e-9);
        assertTrue(DamageCalc.reduce(200, 50) / 200 > DamageCalc.reduce(20, 50) / 20, "큰 한 대는 덜 깎인다");
    }

    @Test
    void twoHandStrength() {
        assertEquals(16, DamageCalc.twoHandStr(16, false));
        assertEquals(24, DamageCalc.twoHandStr(16, true));
        assertEquals(99, DamageCalc.twoHandStr(70, true));
    }

    @Test
    void attackRatingAndUnfitPenalty() {
        DamageCalc.Arms w = new DamageCalc.Arms(100, "C", null, null, 16, 0, 0);
        double fit = DamageCalc.ar(c, w, 16, false);
        double unfit = DamageCalc.ar(c, w, 15, false);
        assertTrue(fit > 100);
        assertTrue(unfit < fit * 0.7, "필요 근력 미달은 크게 깎인다");
        assertTrue(DamageCalc.ar(c, w, 12, true) > DamageCalc.ar(c, w, 12, false), "양손은 근력 1.5 배");
        assertEquals(0, DamageCalc.ar(c, DamageCalc.Arms.BARE, 40, false), 1e-9);
    }

    @Test
    void spellPower() {
        DamageCalc.Arms pot = new DamageCalc.Arms(0, null, "D", "C", 0, 0, 12);
        assertTrue(DamageCalc.spellPower(c, pot, 16) > DamageCalc.SPELL_BASE);
        assertTrue(DamageCalc.spellPower(c, pot, 11) < DamageCalc.SPELL_BASE, "필요 지능 미달");
        assertEquals(0, DamageCalc.spellPower(c, DamageCalc.Arms.BARE, 40), 1e-9);
    }

    @Test
    void defenseGrowsWithLevelAndVigor() {
        assertEquals(20 + 0.4 * 1 + c.vigorDefense.at(10), DamageCalc.defense(c, 1, 10), 1e-9);
        assertTrue(DamageCalc.defense(c, 50, 30) > DamageCalc.defense(c, 50, 10));
        assertTrue(DamageCalc.magicRes(c, 50, 30) > DamageCalc.magicRes(c, 50, 10));
    }

    @Test
    void pvpMeleeCooldown() {
        assertEquals(100, DamageCalc.pvpMelee(100, 1, 1), 1e-9);
        assertEquals(20, DamageCalc.pvpMelee(100, 0, 1), 1e-9);
        assertEquals(50, DamageCalc.pvpMelee(100, 1, 0.5), 1e-9);
        assertEquals(100, DamageCalc.pvpMelee(100, 7, 1), 1e-9);
    }
}
