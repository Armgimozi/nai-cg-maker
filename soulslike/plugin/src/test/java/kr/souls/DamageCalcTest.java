package kr.souls;

import kr.souls.combat.DamageCalc;
import kr.souls.progression.StatCurves;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 피해 셈 (DESIGN 3.7, 3.4, 5.2). 장비에는 보정·요구 능력치가 없다 (DECISIONS 2026-10-10). */
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
    void attackRating() {
        DamageCalc.Arms w = new DamageCalc.Arms(100, 0);
        assertEquals(100 * (1 + c.strAttack.at(16)), DamageCalc.ar(c, w, 16, false), 1e-9);
        assertTrue(DamageCalc.ar(c, w, 16, false) > 100);
        assertTrue(DamageCalc.ar(c, w, 12, true) > DamageCalc.ar(c, w, 12, false), "양손은 근력 1.5 배");
        assertEquals(DamageCalc.ar(c, w, 18, false), DamageCalc.ar(c, w, 12, true), 1e-9, "양손 근력 12 = 한손 근력 18");
        assertEquals(0, DamageCalc.ar(c, DamageCalc.Arms.BARE, 40, false), 1e-9);
    }

    /** 옛 판의 보정 C 와 같은 몫으로 맞췄다: 직검 (62) 은 근력 10 → 68, 13 → 72, 20 → 79, 30 → 88, 40 → 95, 60 → 102, 99 → 112 (옛 C: 40 → 96). */
    @Test
    void calibratedLikeOldGradeC() {
        DamageCalc.Arms sword = new DamageCalc.Arms(62, 0);
        int[] str = {10, 13, 20, 30, 40, 60, 99};
        int[] ar = {68, 72, 79, 88, 95, 102, 112};
        for (int i = 0; i < str.length; i++) assertEquals(ar[i], Math.round(DamageCalc.ar(c, sword, str[i], false)), "근력 " + str[i]);
        // 옛 곡선 (보정 1.0 기준) × 옛 C 0.8 과 0.01 안에서 같다
        double[] oldCurve = {0.13, 0.35, 0.52, 0.68, 0.80, 1.0};
        int[] at = {10, 20, 30, 40, 60, 99};
        for (int i = 0; i < at.length; i++) assertEquals(0.8 * oldCurve[i], c.strAttack.at(at[i]), 0.0101, "근력 " + at[i]);
    }

    /**
     * 장비에는 보정이 없다: 같은 근력은 어느 무기에나 같은 비율을 더한다 (단검 48 과 대검 92 가 근력 10 → 30 에서 똑같이 몇 % 오른다).
     * 요구 능력치도 없다: 근력 1 로 대검을 들어도 깎이지 않는다 (공격력 = 그 무기의 공격력 × (1 + 근력 몫(1)) = 92).
     */
    @Test
    void sameStrengthSamePercentForEveryWeapon() {
        DamageCalc.Arms dagger = new DamageCalc.Arms(48, 0), greatsword = new DamageCalc.Arms(92, 0);
        double gainDagger = DamageCalc.ar(c, dagger, 30, false) / DamageCalc.ar(c, dagger, 10, false);
        double gainGreat = DamageCalc.ar(c, greatsword, 30, false) / DamageCalc.ar(c, greatsword, 10, false);
        assertEquals(gainDagger, gainGreat, 1e-12, "같은 근력, 같은 비율");
        for (int s = 1; s <= 99; s++) {
            assertEquals(DamageCalc.ar(c, dagger, s, false) / 48, DamageCalc.ar(c, greatsword, s, false) / 92, 1e-12, "근력 " + s);
        }
        assertEquals(92 * (1 + c.strAttack.at(1)), DamageCalc.ar(c, greatsword, 1, false), 1e-9, "근력 1 도 깎이지 않는다 (요구 능력치 없음)");
        assertEquals(92, DamageCalc.ar(c, greatsword, 1, false), 1e-9);
        for (int s = 1; s < 99; s++) assertTrue(DamageCalc.ar(c, greatsword, s + 1, false) >= DamageCalc.ar(c, greatsword, s, false), "근력 " + s);
    }

    @Test
    void spellPower() {
        DamageCalc.Arms pot = new DamageCalc.Arms(0, 100), other = new DamageCalc.Arms(0, 80);
        assertEquals(100 * (1 + c.intSpell.at(16)), DamageCalc.spellPower(c, pot, 16), 1e-9);
        assertEquals(121, Math.round(DamageCalc.spellPower(c, pot, 16)), "마법사 (지능 16) 의 쇠단지: 옛 판과 같다");
        assertEquals(100, DamageCalc.spellPower(c, pot, 1), 1e-9, "지능 1 도 깎이지 않는다 (요구 능력치 없음)");
        assertEquals(DamageCalc.spellPower(c, pot, 30) / 100, DamageCalc.spellPower(c, other, 30) / 80, 1e-12, "모든 촉매에 같은 비율");
        assertEquals(0, DamageCalc.spellPower(c, DamageCalc.Arms.BARE, 40), 1e-9);
    }

    /** 공격 속도는 민첩 하나로 (무기마다의 계수가 없다): 1 + 민첩 속도(민첩). */
    @Test
    void attackSpeedIsDexOnly() {
        assertEquals(1.0, DamageCalc.attackSpeed(c, 10), 1e-9);
        assertEquals(1.10, DamageCalc.attackSpeed(c, 20), 1e-9);
        assertEquals(1.22, DamageCalc.attackSpeed(c, 40), 1e-9);
        assertEquals(1.30, DamageCalc.attackSpeed(c, 99), 1e-9);
        assertEquals(1.0, DamageCalc.attackSpeed(c, 1), 1e-9, "민첩이 낮아도 느려지지 않는다 (요구 능력치 없음)");
    }

    /** 막기 (3.4): 물리는 막기 %, 불·술은 그 절반 (non-physical 0.5), 스태미나는 × (1 − 0.8 × (막기/100)²), 최소 4. */
    @Test
    void guard() {
        assertEquals(40, DamageCalc.guarded(100, 60, true, 0.5), 1e-9);
        assertEquals(70, DamageCalc.guarded(100, 60, false, 0.5), 1e-9);
        assertEquals(0, DamageCalc.guarded(100, 100, true, 0.5), 1e-9);
        assertEquals(50, DamageCalc.guarded(100, 100, false, 0.5), 1e-9);
        assertEquals(100, DamageCalc.guarded(100, 0, true, 0.5), 1e-9);
        assertEquals(0, DamageCalc.guarded(100, 140, true, 0.5), 1e-9, "100 이 위 끝");
        // 옛 표의 안정성과 거의 같다: 막기 50 (양손 무기, 옛 안정성 20) → ×0.80, 65 (대검 양손, 옛 35) → ×0.66, 100 (대방패, 옛 80) → ×0.20
        assertEquals(40, DamageCalc.guardStamina(50, 50, 0.8, 4), 1e-9);
        assertEquals(50 * (1 - 0.8 * 0.65 * 0.65), DamageCalc.guardStamina(50, 65, 0.8, 4), 1e-9);
        assertEquals(10, DamageCalc.guardStamina(50, 100, 0.8, 4), 1e-9);
        assertEquals(4, DamageCalc.guardStamina(10, 100, 0.8, 4), 1e-9, "최소 4");
        assertTrue(DamageCalc.guardStamina(50, 90, 0.8, 4) < DamageCalc.guardStamina(50, 70, 0.8, 4), "막기가 높으면 스태미나를 덜 쓴다");
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
