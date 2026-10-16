package kr.labyrinth.combat;

/**
 * 0.3.5 전투 모델의 순수 공식 (Bukkit 무관, 단위 테스트 대상). combat_spec §3 · review2 C1.
 * <pre>
 * 물리 배율 = 1 + 0.01 × STR      마법 배율 = 1 + 0.01 × INT      혼합 = 1 + 0.01 × (STR + INT) / 2
 * 공격 속도 AS = min(0.45, 0.005 × DEX) + 장비·버프,  −50% ~ +75%
 * 실제 간격 = max(0.25, interval ÷ (1 + AS))        활: 당김 = max(0.25, (interval − 0.15) ÷ (1 + AS)), 한 발 주기 = 당김 + 0.15
 * K(방식, 간격) = 근접 1.47 − 0.143 × max(0, 1/간격 − 1.5) · 원거리 1.413 · 시전 1.22
 * 스킬 위력 SP = (W 가운데값 ÷ interval) ÷ K × skill_power_mult × (1 + 0.5 × max(0, AS))
 * 활 세기 = (x² + 2x) ÷ 3, x = 당긴 시간 ÷ 끝까지 당기는 시간 (최대 1)
 * </pre>
 */
public final class CombatMath {

    public static final double STR_POWER = 0.01;
    public static final double INT_POWER = 0.01;
    /** 민첩 1점 = 공격 속도 +0.5%. 민첩 몫은 {@link #DEX_SPEED_CAP} 까지. */
    public static final double DEX_SPEED = 0.005;
    public static final double DEX_SPEED_CAP = 0.45;
    /** 공격 속도 합계 상한 (민첩 몫 + 장비·겉모습·버프). */
    public static final double CAP_ATTACK_SPEED = 0.75;
    public static final double MIN_ATTACK_SPEED = -0.5;
    public static final double DEX_CRIT = 0.0025;
    public static final double LUK_CRIT = 0.0025;
    public static final double DEX_EVASION = 0.001;
    /** 민첩·공속을 다 쌓아도 이보다 빠르지 않다 (초). config combat.attack_interval_min. */
    public static final double MIN_INTERVAL = 0.25;
    /** 활: 놓고 다시 메기는 시간 (초). */
    public static final double BOW_NOCK = 0.15;
    /** 스킬 위력에 드는 공격 속도 몫. */
    public static final double SP_SPEED_SHARE = 0.5;

    private CombatMath() {}

    /** 피해 종류의 스탯 배율. FIXED 는 1. */
    public static double power(DamageKind kind, int str, int intel) {
        if (kind == null) kind = DamageKind.PHYSICAL;
        return switch (kind) {
            case PHYSICAL -> 1.0 + STR_POWER * Math.max(0, str);
            case MAGIC -> 1.0 + INT_POWER * Math.max(0, intel);
            case HYBRID -> 1.0 + 0.5 * (STR_POWER * Math.max(0, str) + INT_POWER * Math.max(0, intel));
            case FIXED -> 1.0;
        };
    }

    /** 민첩 몫 (상한 0.45). */
    public static double dexAttackSpeed(int dex) {
        return Math.min(DEX_SPEED_CAP, DEX_SPEED * Math.max(0, dex));
    }

    /** 공격 속도 합계 = 민첩 몫 + 장비·겉모습·버프, −0.5 ~ +0.75. */
    public static double attackSpeed(int dex, double extra) {
        return clamp(dexAttackSpeed(dex) + extra, MIN_ATTACK_SPEED, CAP_ATTACK_SPEED);
    }

    /** 같은 단계 무기 1 의 '설계 초당 피해' 기울기. */
    public static double k(WeaponAttack.Style style, double interval) {
        if (style == null) style = WeaponAttack.Style.MELEE;
        return switch (style) {
            case RANGED -> 1.413;
            case CASTER -> 1.22;
            case MELEE -> 1.47 - 0.143 * Math.max(0, 1.0 / Math.max(0.05, interval) - 1.5);
        };
    }

    /**
     * 스킬 위력 = (한 방 가운데값 ÷ 간격) ÷ K × skill_power_mult × (1 + 0.5 × 공속). 간격은 툴팁 값(민첩 전).
     * 같은 단계면 무거운 무기와 가벼운 무기의 스킬 위력이 같다.
     */
    public static double skillPower(double midDamage, WeaponAttack attack, double attackSpeed) {
        WeaponAttack a = attack == null ? WeaponAttack.UNARMED : attack;
        double base = Math.max(0, midDamage) / a.interval() / k(a.style(), a.interval());
        return base * a.skillPowerMult() * (1.0 + SP_SPEED_SHARE * Math.max(0, attackSpeed));
    }

    /** 근접·시전의 실제 간격 (초). */
    public static double meleeInterval(double interval, double attackSpeed, double min) {
        return Math.max(min, interval / (1.0 + Math.max(MIN_ATTACK_SPEED, attackSpeed)));
    }

    /** 활을 끝까지 당기는 시간 (초) = max(하한, (한 발 주기 − 0.15) ÷ (1 + 공속)). */
    public static double bowDraw(double interval, double attackSpeed, double min) {
        return Math.max(min, Math.max(0.05, interval - BOW_NOCK) / (1.0 + Math.max(MIN_ATTACK_SPEED, attackSpeed)));
    }

    /** 실제 공격 주기 (초): 근접·시전 = 간격, 활 = 당김 + 0.15. */
    public static double cycle(WeaponAttack attack, double attackSpeed, double min) {
        WeaponAttack a = attack == null ? WeaponAttack.UNARMED : attack;
        return a.ranged() ? bowDraw(a.interval(), attackSpeed, min) + BOW_NOCK : meleeInterval(a.interval(), attackSpeed, min);
    }

    /** 활 세기 (바닐라 곡선): x = 당긴 시간 ÷ 끝까지 당기는 시간. 0~1. */
    public static double bowForce(double drawnSeconds, double fullDrawSeconds) {
        double x = fullDrawSeconds <= 0 ? 1.0 : clamp(drawnSeconds / fullDrawSeconds, 0, 1);
        return (x * x + 2 * x) / 3.0;
    }

    /**
     * 화살에 무기 고유 효과가 붙는 가장 낮은 세기 (0.3.6.1 안전 검토 1). 끝까지(거의) 당긴 화살만 기본 공격 고유 효과(휩쓸기·연타·방패 강타·
     * 가속·흡혈 등)를 켠다. 고유 효과의 덧 피해는 세기와 상관없이 무기 한 방 기준이라, 3틱만 당겨 놓는 화살(세기 0.1, 0.2초마다 한 발)을
     * 연달아 쏘면 끝까지 당길 때보다 고유 효과가 몇 배로 켜졌다. 0.9 = 끝까지 당기는 시간의 약 92% — 그보다 덜 당긴 화살은 고유 효과 없음.
     * 이 세기 그대로 연달아 쏴도 고유 효과가 켜지는 빠르기는 끝까지 당길 때의 (당김 + 0.15) ÷ (0.924 × 당김 + 0.15) < 1.09배뿐이다.
     */
    public static final double ARROW_UNIQUE_MIN_FORCE = 0.9;

    /** 이 세기의 화살이 무기 고유 효과를 켜는가 ({@link #ARROW_UNIQUE_MIN_FORCE}). */
    public static boolean arrowProcsUnique(double force) { return force >= ARROW_UNIQUE_MIN_FORCE - 1e-9; }

    /** 바닐라 활 세기(20틱 기준)를 당긴 틱 수로 되돌림 — 서버가 당긴 시간을 못 읽을 때만. */
    public static double ticksFromVanillaForce(double force) {
        double f = clamp(force, 0, 1);
        return 20.0 * (-1.0 + Math.sqrt(1.0 + 3.0 * f));
    }

    static double clamp(double v, double lo, double hi) { return Math.max(lo, Math.min(hi, v)); }
}
