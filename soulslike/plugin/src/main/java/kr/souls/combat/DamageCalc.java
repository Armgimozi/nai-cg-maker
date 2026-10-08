package kr.souls.combat;

import kr.souls.progression.StatCurves;

/**
 * 피해 계산 (3.7). 순수 함수만 둔다 (13.1 의 DamageCalcTest).
 * <ul>
 *   <li>공격력 AR = 기본 × (1 + 근력 등급 × 곡선(근력)). 피해를 올리는 능력치는 근력 하나다. 왼손이 비면 양손 잡기로 근력을 1.5 배로
 *       셈한다 (99 까지, 2.1). 필요 근력이 모자라면 −40% (stats.unfit-penalty).</li>
 *   <li>술 세기 = 100 × (1 + 지능 등급 × 곡선(지능)). 필요 지능 미달이면 −40%. 술 (M5) 이 쓰는 값이고 지금은 창의 숫자다.</li>
 *   <li>공격 속도 배율 a = 1 + 민첩 속도(민첩) × 속도 계수[무기의 민첩 보정], 필요 민첩 미달이면 × (1 − unfit-speed) (3.6).</li>
 *   <li>방어력 = 20 + 0.4 × 레벨 + 체력 방어(체력), 마법 저항 = 20 + 0.4 × 레벨 + 정신 저항(정신).
 *       받는 피해 = 원피해² / (원피해 + 방어력) (원피해 = 방어력이면 절반).</li>
 * </ul>
 */
public final class DamageCalc {
    /** 계산에 쓰는 무기 값 (item.Weapons.Def 에서 떼어 온 것. 등급이 없으면 null, 필요 능력치가 없으면 0). */
    public record Arms(int attack, String strGrade, String dexGrade, String intGrade, int needStr, int needDex, int needInt) {
        public static final Arms BARE = new Arms(0, null, null, null, 0, 0, 0);
    }

    /** 술 세기의 바탕 (촉매 +0) */
    public static final double SPELL_BASE = 100;

    private DamageCalc() {}

    /** 양손으로 잡았을 때 근력 (1.5 배, 99 까지). */
    public static int twoHandStr(int str, boolean twoHanded) {
        return twoHanded ? Math.min(99, (int) Math.floor(str * 1.5)) : str;
    }

    public static double ar(StatCurves c, Arms w, int str, boolean twoHanded) {
        if (w == null || w.attack() <= 0) return 0;
        int s = twoHandStr(str, twoHanded);
        double ar = w.attack() * (1 + c.grade(w.strGrade()) * c.scaling.at(s));
        if (w.needStr() > 0 && s < w.needStr()) ar *= 1 - c.unfitPenalty;
        return ar;
    }

    public static double spellPower(StatCurves c, Arms w, int intel) {
        if (w == null || w.intGrade() == null) return 0;
        double sp = SPELL_BASE * (1 + c.grade(w.intGrade()) * c.scaling.at(intel));
        if (w.needInt() > 0 && intel < w.needInt()) sp *= 1 - c.unfitPenalty;
        return sp;
    }

    /** 공격 속도 배율 a (1 이면 그대로, 1.09 면 9% 빠르다). 무기의 민첩 보정이 없으면 1 (필요 민첩 미달은 그래도 깎는다). */
    public static double attackSpeed(StatCurves c, Arms w, int dex) {
        if (w == null) return 1;
        double a = 1 + c.attackSpeed.at(dex) * c.speedGrade(w.dexGrade());
        if (w.needDex() > 0 && dex < w.needDex()) a *= 1 - c.unfitSpeed;
        return a;
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
