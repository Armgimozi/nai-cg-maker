package kr.labyrinth.pvp;

/**
 * PvP 숫자 (pvp_spec §3·§4·§5·§8) — 순수 함수, 모든 값은 {@link PvpConfig} 에서. 단위 테스트 대상.
 * <pre>
 * L          = max(공격자 레벨, 대상 레벨)
 * m(L)       = base × min(1, (ref ÷ L)^exponent) × damage_multiplier          {@link #levelMult}
 * B(L)       = low × min(L, knee) + high × max(0, L − knee)                    {@link #bufferHp}
 * R          = cap × S ÷ (S + perLevel × L_대상),  S = 대상 VIT + 대상 방어      {@link #resilience}
 * PvP 원피해 = 원피해 × m(L) × 직업 보정 × 스킬 pvp_mult × (1 − R) × H ÷ (H + B) {@link #damageFactor}
 * 치명 피해  = 1 + (치명 피해 − 1) × crit_damage_scale                          {@link #critMultiplier}
 * 긴 싸움    = max(floor, 1 − perSecond × max(0, t − start))                    {@link #longFight}
 * </pre>
 */
public final class PvpMath {

    private PvpMath() {}

    /** 두 사람 중 높은 레벨 (1 이상). */
    public static int level(int attackerLevel, int targetLevel) { return Math.max(1, Math.max(attackerLevel, targetLevel)); }

    /** 기준 배율 m(L) (damage_multiplier 포함). */
    public static double levelMult(PvpConfig c, int level) {
        PvpConfig.LevelCurve lc = c.levelCurve();
        int l = Math.max(1, level);
        double curve = Math.min(1.0, Math.pow((double) lc.refLevel() / l, lc.exponent()));
        return lc.base() * curve * c.damageMultiplier();
    }

    /** PvP 완충 체력 B(L). */
    public static double bufferHp(PvpConfig c, int level) {
        PvpConfig.BufferHp b = c.bufferHp();
        int l = Math.max(1, level);
        return b.perLevelLow() * Math.min(l, b.kneeLevel()) + b.perLevelHigh() * Math.max(0, l - b.kneeLevel());
    }

    /** H ÷ (H + B(L)) — 실제로 깎이는 HP 비율. HP 를 모르면 1. */
    public static double poolFactor(PvpConfig c, double maxHp, int level) {
        if (maxHp <= 0) return 1.0;
        return maxHp / (maxHp + bufferHp(c, level));
    }

    /** 강인함 R (0 ~ cap). */
    public static double resilience(PvpConfig c, double vit, double defense, int targetLevel) {
        double s = Math.max(0, vit) + Math.max(0, defense);
        if (s <= 0) return 0;
        PvpConfig.Resilience r = c.resilience();
        return r.cap() * s / (s + r.perLevel() * Math.max(1, targetLevel));
    }

    /** 플레이어에게 들어가는 치명 피해 배율 (추가 피해만 × crit_damage_scale). */
    public static double critMultiplier(PvpConfig c, double critDamage) {
        return 1.0 + Math.max(0, critDamage - 1.0) * c.critDamageScale();
    }

    /** 긴 싸움 배율 — seconds = 이번 PvP 전투가 이어진 시간. */
    public static double longFight(PvpConfig c, double seconds) {
        PvpConfig.LongFight lf = c.longFight();
        return Math.max(lf.floor(), Math.min(1.0, 1.0 - lf.perSecond() * Math.max(0, seconds - lf.start())));
    }

    /** 고정량 회복(치유력·흡혈·재생) → × H ÷ (H + B) (flat_heal_by_pool 이 꺼져 있으면 그대로). level = 회복받는 사람. */
    public static double flatHeal(PvpConfig c, double amount, double maxHp, int level) {
        return c.flatHealByPool() ? amount * poolFactor(c, maxHp, level) : amount;
    }

    /** 피해 한 건의 대상 쪽 정보. */
    public record Target(int level, double maxHp, double vit, double defense) {}

    /**
     * 플레이어 → 다른 파티 플레이어 원피해에 곱하는 값.
     * @param attackerLevel 공격자 레벨
     * @param classMult     직업 보정 (공격자, {@link PvpConfig.ClassDamage#of})
     * @param skillMult     스킬 pvp_mult (기본 공격·지속 피해 = 1)
     * @param percent       최대 HP 비율 피해 — 이미 상대 HP 기준이라 레벨 곡선·완충을 곱하지 않는다
     */
    public static double damageFactor(PvpConfig c, int attackerLevel, Target t, double classMult, double skillMult, boolean percent) {
        double r = 1.0 - resilience(c, t.vit(), t.defense(), t.level());
        double f = classMult * clampSkill(skillMult) * r;
        if (percent) return f * c.damageMultiplier();
        int l = level(attackerLevel, t.level());
        return f * levelMult(c, l) * poolFactor(c, t.maxHp(), l);
    }

    /** 스킬 pvp_mult 범위 (0.1 ~ 1.0, 값이 없으면 1). */
    public static double clampSkill(double v) {
        if (Double.isNaN(v) || v <= 0) return 1.0;
        return Math.max(0.1, Math.min(1.0, v));
    }
}
