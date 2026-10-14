package kr.labyrinth.stats;

import java.util.Collections;
import java.util.EnumMap;
import java.util.Map;
import kr.labyrinth.content.ClassDef;

/**
 * 스탯 → 파생 능력치 순수 계산 (GDD §3, §11.7 상한). Bukkit 의존 없음 — 단위 테스트 대상.
 */
public final class StatCalculator {

    /** 맨손/무기 없음 기본 무기 피해. */
    public static final double UNARMED_DAMAGE = 3.0;
    public static final double BASE_HP_NO_CLASS = 100.0;
    public static final double BASE_MP_NO_CLASS = 50.0;

    // 상한 (GDD §11.7)
    public static final double CAP_CRIT = 0.75;
    public static final double CAP_ATTACK_SPEED = 0.60;
    public static final double CAP_MOVE_SPEED = 0.30;
    public static final double CAP_CDR = 0.40;
    public static final double CAP_CDR_INT = 0.20;
    public static final double CAP_LIFESTEAL = 0.25;
    public static final double CAP_DR = 0.50;
    public static final double CAP_EVASION = 0.40;
    public static final double CAP_BLOCK = 0.40;
    public static final double CAP_CRAFT = 0.30;
    public static final double CAP_DEBUFF = 0.30;

    private StatCalculator() {}

    /**
     * 직업별 주스탯 혼합 (GDD §3). 수호기사 STR0.6+VIT0.4, 광전사 STR, 사냥꾼 DEX, 비전술사 INT,
     * 사제 INT0.5+WIS0.5, 그림자 DEX0.7+LUK0.3. 모르는 직업은 primary_stat 100%, 직업 없음은 STR.
     */
    public static double primaryMix(ClassDef cls, Map<Stat, Integer> s) {
        if (cls == null) return s.getOrDefault(Stat.STR, 0);
        return switch (cls.id()) {
            case "guardian" -> 0.6 * s.getOrDefault(Stat.STR, 0) + 0.4 * s.getOrDefault(Stat.VIT, 0);
            case "berserker" -> s.getOrDefault(Stat.STR, 0);
            case "hunter" -> s.getOrDefault(Stat.DEX, 0);
            case "arcanist" -> s.getOrDefault(Stat.INT, 0);
            case "priest" -> 0.5 * s.getOrDefault(Stat.INT, 0) + 0.5 * s.getOrDefault(Stat.WIS, 0);
            case "shadow" -> 0.7 * s.getOrDefault(Stat.DEX, 0) + 0.3 * s.getOrDefault(Stat.LUK, 0);
            default -> s.getOrDefault(cls.primaryStat(), 0);
        };
    }

    /**
     * @param cls        직업 (null = 직업 없음)
     * @param level      레벨 (1~)
     * @param allocated  분배한 스탯 포인트
     * @param bonus      장비 + 세트 + 칭호 + 버프 합 (StatBlock 키 규칙)
     * @param baseCrit   기본 치명타 확률 (config, 0.05)
     * @param baseCritDamage 기본 치명타 피해 배율 (config, 1.5)
     */
    public static DerivedStats compute(ClassDef cls, int level, Map<Stat, Integer> allocated, StatBlock bonus,
                                       double baseCrit, double baseCritDamage) {
        int lv = Math.max(1, level);
        Map<Stat, Integer> s = new EnumMap<>(Stat.class);
        for (Stat st : Stat.values()) {
            int v = (cls == null ? 0 : cls.baseStat(st)) + allocated.getOrDefault(st, 0) + (int) Math.round(bonus.get(st));
            s.put(st, Math.max(0, v));
        }
        int str = s.get(Stat.STR), dex = s.get(Stat.DEX), intel = s.get(Stat.INT);
        int vit = s.get(Stat.VIT), wis = s.get(Stat.WIS), luk = s.get(Stat.LUK);

        double weapon = bonus.get("damage");
        if (weapon <= 0) weapon = UNARMED_DAMAGE;
        double attackPower = weapon * (1.0 + 0.02 * primaryMix(cls, s));

        double baseHp = cls == null ? BASE_HP_NO_CLASS : cls.baseHp();
        double baseMp = cls == null ? BASE_MP_NO_CLASS : cls.baseMp();
        double hpPer = cls == null ? 8 : cls.hpPerLevel();
        double mpPer = cls == null ? 2 : cls.mpPerLevel();
        double maxHp = Math.max(1, baseHp + hpPer * (lv - 1) + vit * 8.0 + bonus.get("hp"));
        double maxMp = Math.max(0, baseMp + mpPer * (lv - 1) + intel * 3.0 + wis * 2.0 + bonus.get("mp"));

        double defense = Math.max(0, vit * 0.5 + bonus.get("defense"));
        double crit = clamp(baseCrit + dex * 0.0015 + luk * 0.0025 + bonus.get("crit_chance"), 0, CAP_CRIT);
        double critDmg = Math.max(1.0, baseCritDamage + bonus.get("crit_damage"));
        double atkSpeed = clamp(dex * 0.004 + bonus.get("attack_speed"), -0.5, CAP_ATTACK_SPEED);
        double moveSpeed = clamp(bonus.get("move_speed"), -0.6, CAP_MOVE_SPEED);
        double cdr = clamp(Math.min(CAP_CDR_INT, intel * 0.002) + bonus.get("cooldown_reduction"), 0, CAP_CDR);
        double skillDmg = bonus.get("skill_damage");
        double manaRegen = Math.max(0, (cls == null ? 1.0 : cls.manaRegen()) + wis * 0.05 + bonus.get("mana_regen"));
        double hpRegen = Math.max(0, bonus.get("hp_regen"));
        double healPower = Math.max(0, wis * 1.5 + bonus.get("heal_power"));
        double lifesteal = clamp(bonus.get("lifesteal"), 0, CAP_LIFESTEAL);
        double dr = clamp(bonus.get("damage_reduction"), 0, CAP_DR);
        double evasion = clamp(bonus.get("evasion"), 0, CAP_EVASION);
        double block = clamp(bonus.get("block_chance"), 0, CAP_BLOCK);
        double gold = Math.max(-0.9, luk * 0.005 + bonus.get("gold_bonus"));
        double xp = Math.max(-0.9, bonus.get("xp_bonus"));
        double craft = clamp(bonus.get("craft_discount"), 0, CAP_CRAFT);
        double debuff = clamp(wis * 0.005, 0, CAP_DEBUFF);
        double kb = clamp(str * 0.003, 0, 0.5);
        double dmgMult = Math.max(-0.9, bonus.get("damage_mult"));
        double dmgTaken = Math.max(-0.9, bonus.get("damage_taken"));

        return new DerivedStats(Collections.unmodifiableMap(s), weapon, attackPower, maxHp, maxMp, defense, crit,
                critDmg, atkSpeed, moveSpeed, cdr, skillDmg, manaRegen, hpRegen, healPower, lifesteal, dr, evasion,
                block, gold, xp, craft, debuff, kb, dmgMult, dmgTaken);
    }

    static double clamp(double v, double min, double max) {
        return Math.max(min, Math.min(max, v));
    }
}
