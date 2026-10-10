package kr.souls.combat;

import kr.souls.progression.StatCurves;

/**
 * 피해 계산 (3.7, 3.4). 순수 함수만 둔다 (13.1 의 DamageCalcTest).
 * 장비에는 능력치 보정도 요구 능력치도 없다 (DECISIONS 2026-10-10): 능력치는 모든 장비에 같은 곡선으로 듣는다.
 * <ul>
 *   <li>공격력 AR = 무기의 공격력 × (1 + 근력 몫(근력)) (stats.strength.attack). 피해를 올리는 능력치는 근력 하나다. 왼손이 비면
 *       양손 잡기로 근력을 1.5 배로 셈한다 (99 까지, 2.1: 장비의 보정이 아니라 잡는 자세다).</li>
 *   <li>술법 세기 = 촉매의 술법 세기 × (1 + 지력 몫(지력)) (stats.intelligence.spell-power). 술법 (M5) 이 쓰는 값이고 지금은 창의 숫자다.</li>
 *   <li>공격 속도 배율 a = 1 + 민첩 속도(민첩) (stats.dexterity.attack-speed). 모든 무기에 같다 (3.6).</li>
 *   <li>막기 (3.4): 방패의 막기 g 는 막는 물리 피해 % 다. 불·술은 g × non-physical. 막다가 맞으면 쓰는 스태미나는
 *       그 공격의 스태미나 피해 × (1 − stamina-scale × (g/100)²), 최소 stamina-min (combat.guard).</li>
 *   <li>방어력 = 20 + 0.4 × 레벨 + 생명력 방어(생명력), 마법 저항 = 20 + 0.4 × 레벨 + 정신력 저항(정신력).
 *       받는 피해 = 원피해² / (원피해 + 방어력) (원피해 = 방어력이면 절반).</li>
 * </ul>
 */
public final class DamageCalc {
    /** 계산에 쓰는 장비 값 (item.Weapons.Def 에서 떼어 온 것): 공격력 (근접 무기·활·패링 단검), 술법 세기 (촉매). */
    public record Arms(int attack, int spell) {
        public static final Arms BARE = new Arms(0, 0);
    }

    /** 양손 잡기의 근력 배율 (2.1) */
    public static final double TWO_HAND_STR = 1.5;

    private DamageCalc() {}

    /** 양손으로 잡았을 때 근력 (1.5 배, 99 까지). */
    public static int twoHandStr(int str, boolean twoHanded) {
        return twoHanded ? Math.min(99, (int) Math.floor(str * TWO_HAND_STR)) : str;
    }

    /** 근력의 공격력 몫 (0.28 = +28%). 모든 무기에 같다. */
    public static double strBonus(StatCurves c, int str) {
        return c.strAttack.at(str);
    }

    public static double ar(StatCurves c, Arms w, int str, boolean twoHanded) {
        if (w == null || w.attack() <= 0) return 0;
        return w.attack() * (1 + strBonus(c, twoHandStr(str, twoHanded)));
    }

    public static double spellPower(StatCurves c, Arms w, int intel) {
        if (w == null || w.spell() <= 0) return 0;
        return w.spell() * (1 + c.intSpell.at(intel));
    }

    /** 공격 속도 배율 a (1 이면 그대로, 1.08 이면 8% 빠르다). 무기와 상관없이 민첩 하나로. */
    public static double attackSpeed(StatCurves c, int dex) {
        return 1 + c.attackSpeed.at(dex);
    }

    /**
     * 막는 동안 막는 몫 (0..1): 물리는 막기/100, 불·술 (물리가 아닌 것) 은 막기/100 × nonPhysical.
     * @param guard 막기 (방패의 guard, 양손 막기는 combat.guard.two-handed)
     */
    public static double guardStop(int guard, boolean physical, double nonPhysical) {
        double g = Math.max(0, Math.min(100, guard)) / 100.0;
        return Math.max(0, Math.min(1, physical ? g : g * nonPhysical));
    }

    /** 막았을 때 들어오는 피해: 원피해 × (1 − 막는 몫). 그다음은 방어력 (reduce) 을 지난다. */
    public static double guarded(double raw, int guard, boolean physical, double nonPhysical) {
        return Math.max(0, raw) * (1 - guardStop(guard, physical, nonPhysical));
    }

    /**
     * 막다가 맞으면 쓰는 스태미나 (3.2, 3.4): 공격의 스태미나 피해 × (1 − scale × (막기/100)²), 최소 min. 스태미나가 이만큼 없으면
     * 막기가 깨진다. 보기 (scale 0.8): 막기 50 → ×0.80, 60 → ×0.71, 70 → ×0.61, 90 → ×0.35, 100 → ×0.20.
     */
    public static double guardStamina(double staminaDamage, int guard, double scale, double min) {
        double g = Math.max(0, Math.min(100, guard)) / 100.0;
        return Math.max(min, Math.max(0, staminaDamage) * Math.max(0, 1 - scale * g * g));
    }

    public static double defense(StatCurves c, int level, int vig) {
        return c.defenseBase + c.defensePerLevel * level + c.vigorDefense.at(vig);
    }

    public static double magicRes(StatCurves c, int level, int mnd) {
        return c.defenseBase + c.defensePerLevel * level + c.magicDefense.at(mnd);
    }

    /** 방어로 줄인 피해: raw² / (raw + def). raw 가 0 이하면 0. */
    public static double reduce(double raw, double def) {
        if (raw <= 0) return 0;
        return raw * raw / (raw + Math.max(0, def));
    }

    /**
     * PvP 의 바닐라 근접 한 대 (M1 의 동작 실행기 전, 5.7): AR × (0.2 + 0.8 × 회복²) × pvp.damage-scale. 회복은 바닐라 공격 대기
     * (0..1, 휘두르기 직전의 값). 방어력은 그 뒤 피해 고리에서 줄인다.
     */
    public static double pvpMelee(double ar, double cooldown, double scale) {
        double cd = Math.max(0, Math.min(1, cooldown));
        return ar * (0.2 + 0.8 * cd * cd) * scale;
    }
}
