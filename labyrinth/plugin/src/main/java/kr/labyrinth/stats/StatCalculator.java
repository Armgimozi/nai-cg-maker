package kr.labyrinth.stats;

import java.util.Collections;
import java.util.EnumMap;
import java.util.Map;
import kr.labyrinth.combat.CombatMath;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.core.ArmorLooks;

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
    /** 공격 속도 합계 상한 +75% (그중 민첩 몫 {@link #CAP_DEX_ATTACK_SPEED}, 간격 하한 0.25초). */
    public static final double CAP_ATTACK_SPEED = CombatMath.CAP_ATTACK_SPEED;
    public static final double CAP_DEX_ATTACK_SPEED = CombatMath.DEX_SPEED_CAP;
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
     * 0.3.4 판 (무기 정보 없음): 손에 든 무기 = 맨손 방식(근접 0.625초·물리), 스킬 위력 기준 = 무기 피해.
     * @param cls        직업 (null = 직업 없음)
     * @param level      레벨 (1~)
     * @param allocated  분배한 스탯 포인트
     * @param bonus      장비 + 세트 + 칭호 + 버프 합 (StatBlock 키 규칙)
     * @param baseCrit   기본 치명타 확률 (config, 0.05)
     * @param baseCritDamage 기본 치명타 피해 배율 (config, 1.5)
     */
    public static DerivedStats compute(ClassDef cls, int level, Map<Stat, Integer> allocated, StatBlock bonus,
                                       double baseCrit, double baseCritDamage) {
        return compute(cls, level, allocated, bonus, baseCrit, baseCritDamage, WeaponAttack.UNARMED, Double.NaN,
                CombatMath.MIN_INTERVAL);
    }

    /**
     * 파생 능력치 (0.3.5 전투 모델, combat_spec §3).
     * <ul>
     *   <li>공격력 = 무기 한 방 W × 무기 피해 종류의 배율 (물리 1 + 0.01 STR, 마법 1 + 0.01 INT). 민첩은 공격력을 올리지 않는다.</li>
     *   <li>민첩: 공격 속도 +0.5%/점(민첩 몫 최대 +45%, 합계 최대 +75%) · 치명 +0.25%p · 회피 +0.1%p.</li>
     *   <li>스킬 위력 = (W 가운데값 ÷ 간격) ÷ K × skill_power_mult × (1 + 0.5 × 공속) — {@link CombatMath#skillPower}.</li>
     * </ul>
     * @param attack      손에 든 무기의 공격 방식 (맨손 {@link WeaponAttack#UNARMED})
     * @param midDamage   스킬 위력 기준 = 무기 피해 범위 가운데값 × 강화 배율 (NaN·0 이하 = 무기 피해 W)
     * @param minInterval 간격 하한 (config combat.attack_interval_min, 0.25초)
     */
    public static DerivedStats compute(ClassDef cls, int level, Map<Stat, Integer> allocated, StatBlock bonus,
                                       double baseCrit, double baseCritDamage, WeaponAttack attack, double midDamage,
                                       double minInterval) {
        return compute(cls, level, allocated, bonus, baseCrit, baseCritDamage, attack, midDamage, minInterval, ArmorLooks.OFF);
    }

    /**
     * 파생 능력치 + 방어구 겉모습 (look_spec §1.2). bonus 의 {@code look.*}·{@code look_body.*} 수({@link ArmorLookMath})로
     * 숨은 효과를 더하고(더하는 키는 장비 스탯처럼, 상한 그대로), 방어·최대 HP·MP 재생에 곱하고, 재사용 대기 배율·4부위 효과를 정한다.
     * 밀려남 저항 = clamp(min(0.5, 0.003 × 힘) + 버팀, 0, 0.85).
     * @param looks 겉모습 설정 (null·꺼짐 = 효과 없음, 수만 셈)
     */
    public static DerivedStats compute(ClassDef cls, int level, Map<Stat, Integer> allocated, StatBlock bonusIn,
                                       double baseCrit, double baseCritDamage, WeaponAttack attack, double midDamage,
                                       double minInterval, ArmorLooks looks) {
        ArmorLookMath.Result look = ArmorLookMath.compute(bonusIn, looks);
        StatBlock bonus = bonusIn;
        if (!look.additive().isEmpty()) bonus = new StatBlock().addAll(bonusIn).addAll(look.additive());
        int lv = Math.max(1, level);
        Map<Stat, Integer> s = new EnumMap<>(Stat.class);
        for (Stat st : Stat.values()) {
            int v = (cls == null ? 0 : cls.baseStat(st)) + allocated.getOrDefault(st, 0) + (int) Math.round(bonus.get(st));
            s.put(st, Math.max(0, v));
        }
        int str = s.get(Stat.STR), dex = s.get(Stat.DEX), intel = s.get(Stat.INT);
        int vit = s.get(Stat.VIT), wis = s.get(Stat.WIS), luk = s.get(Stat.LUK);
        WeaponAttack wa = attack == null ? WeaponAttack.UNARMED : attack;

        double weapon = bonus.get("damage");
        if (weapon <= 0) weapon = UNARMED_DAMAGE;
        double mid = Double.isNaN(midDamage) || midDamage <= 0 ? weapon : midDamage;
        double physical = CombatMath.power(DamageKind.PHYSICAL, str, intel);
        double magic = CombatMath.power(DamageKind.MAGIC, str, intel);
        double attackPower = weapon * CombatMath.power(wa.kind(), str, intel);

        double baseHp = cls == null ? BASE_HP_NO_CLASS : cls.baseHp();
        double baseMp = cls == null ? BASE_MP_NO_CLASS : cls.baseMp();
        double hpPer = cls == null ? 8 : cls.hpPerLevel();
        double mpPer = cls == null ? 2 : cls.mpPerLevel();
        double maxHp = Math.max(1, (baseHp + hpPer * (lv - 1) + vit * 8.0 + bonus.get("hp")) * look.hpMult());
        double maxMp = Math.max(0, baseMp + mpPer * (lv - 1) + intel * 3.0 + wis * 2.0 + bonus.get("mp"));

        double defense = Math.max(0, vit * 0.5 + bonus.get("defense")) * look.defenseMult();
        double crit = clamp(baseCrit + dex * CombatMath.DEX_CRIT + luk * CombatMath.LUK_CRIT + bonus.get("crit_chance"), 0, CAP_CRIT);
        double critDmg = Math.max(1.0, baseCritDamage + bonus.get("crit_damage"));
        double atkSpeed = CombatMath.attackSpeed(dex, bonus.get("attack_speed"));
        double moveSpeed = clamp(bonus.get("move_speed"), -0.6, CAP_MOVE_SPEED);
        double cdr = clamp(Math.min(CAP_CDR_INT, intel * 0.002) + bonus.get("cooldown_reduction"), 0, CAP_CDR);
        double skillDmg = bonus.get("skill_damage");
        double manaRegen = Math.max(0, (cls == null ? 1.0 : cls.manaRegen()) + wis * 0.05 + bonus.get("mana_regen")) * look.manaRegenMult();
        double hpRegen = Math.max(0, bonus.get("hp_regen"));
        double healPower = Math.max(0, wis * 1.5 + bonus.get("heal_power"));
        double lifesteal = clamp(bonus.get("lifesteal"), 0, CAP_LIFESTEAL);
        double dr = clamp(bonus.get("damage_reduction"), 0, CAP_DR);
        double evasion = clamp(dex * CombatMath.DEX_EVASION + bonus.get("evasion"), 0, CAP_EVASION);
        double block = clamp(bonus.get("block_chance"), 0, CAP_BLOCK);
        double gold = Math.max(-0.9, luk * 0.005 + bonus.get("gold_bonus"));
        double xp = Math.max(-0.9, bonus.get("xp_bonus"));
        double craft = clamp(bonus.get("craft_discount"), 0, CAP_CRAFT);
        double debuff = clamp(wis * 0.005, 0, CAP_DEBUFF);
        double kb = ArmorLookMath.knockbackResistance(str, look.knockbackResist());
        double dmgMult = Math.max(-0.9, bonus.get("damage_mult"));
        double dmgTaken = Math.max(-0.9, bonus.get("damage_taken"));
        double magicDmg = Math.max(-0.9, bonus.get("magic_damage"));
        double skillPower = CombatMath.skillPower(mid, wa, atkSpeed);
        double cycle = CombatMath.cycle(wa, atkSpeed, Math.max(0.05, minInterval));

        return new DerivedStats(Collections.unmodifiableMap(s), weapon, attackPower, maxHp, maxMp, defense, crit,
                critDmg, atkSpeed, moveSpeed, cdr, skillDmg, manaRegen, hpRegen, healPower, lifesteal, dr, evasion,
                block, gold, xp, craft, debuff, kb, dmgMult, dmgTaken, physical, magic, wa, mid, skillPower, cycle, magicDmg,
                look.counts(), look.body(), look.full(), look.cooldownMult(), look.ccResist());
    }

    static double clamp(double v, double min, double max) {
        return Math.max(min, Math.min(max, v));
    }
}
