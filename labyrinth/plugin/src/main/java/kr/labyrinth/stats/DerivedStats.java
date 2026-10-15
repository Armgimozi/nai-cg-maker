package kr.labyrinth.stats;

import java.util.Map;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;

/**
 * 파생 능력치 (StatCalculator 결과, 불변). 비율 값은 0~1 (0.15 = 15%).
 *
 * @param stats          최종 스탯 6종 (직업 기본 + 분배 + 장비/칭호/버프)
 * @param weaponDamage   무기 한 방 피해 W (굴림값 × 강화). 맨손이면 3
 * @param attackPower    공격력 = W × 손에 든 무기 피해 종류의 배율 (물리 1 + 0.01 STR · 마법 1 + 0.01 INT) — 툴팁·/스탯 의 '공격력'
 * @param attackSpeed    공격 속도 합계 (민첩 몫 ≤ 0.45, 합계 ≤ 0.75)
 * @param damageMult     주는 피해 배율 가산 (버프 damage_mult, weaken 음수)
 * @param damageTaken    받는 피해 배율 가산 (vulnerable)
 * @param debuffReduction 해로운 효과 지속시간 감소 (WIS, stun 제외)
 * @param physicalPower  물리 배율 1 + 0.01 × STR
 * @param magicPower     마법 배율 1 + 0.01 × INT
 * @param weapon         손에 든 무기의 공격 방식 (간격·방식·피해 종류, 맨손 = {@link WeaponAttack#UNARMED})
 * @param weaponMidDamage 스킬 위력 기준 = 무기 피해 가운데값 × 강화 배율
 * @param skillPower     스킬 위력 (직업 스킬·무기 스킬·지속 피해의 기준)
 * @param attackInterval 실제 공격 주기(초) — 근접·시전 = 간격 ÷ (1 + 공속), 활 = 당김 + 0.15 (하한 적용)
 * @param magicDamage    마법 피해 가산 (사제 은총 등, 마법 종류 피해에만)
 */
public record DerivedStats(
        Map<Stat, Integer> stats,
        double weaponDamage,
        double attackPower,
        double maxHp,
        double maxMp,
        double defense,
        double critChance,
        double critDamage,
        double attackSpeed,
        double moveSpeed,
        double cooldownReduction,
        double skillDamage,
        double manaRegen,
        double hpRegen,
        double healPower,
        double lifesteal,
        double damageReduction,
        double evasion,
        double blockChance,
        double goldBonus,
        double xpBonus,
        double craftDiscount,
        double debuffReduction,
        double knockbackResistance,
        double damageMult,
        double damageTaken,
        double physicalPower,
        double magicPower,
        WeaponAttack weapon,
        double weaponMidDamage,
        double skillPower,
        double attackInterval,
        double magicDamage) {

    public int stat(Stat s) { return stats.getOrDefault(s, 0); }

    /** 피해 종류의 스탯 배율 (고정 = 1, 혼합 = 두 배율의 평균). */
    public double power(DamageKind kind) {
        if (kind == null) return physicalPower;
        return switch (kind) {
            case PHYSICAL -> physicalPower;
            case MAGIC -> magicPower;
            case HYBRID -> (physicalPower + magicPower) / 2.0;
            case FIXED -> 1.0;
        };
    }

    /** 손에 든 무기의 기본 피해 종류. */
    public DamageKind weaponKind() { return weapon == null ? DamageKind.PHYSICAL : weapon.kind(); }

    /** 툴팁 간격 (민첩 전). */
    public double weaponInterval() { return weapon == null ? WeaponAttack.UNARMED.interval() : weapon.interval(); }

    /** 지금 실제 초당 공격 횟수. */
    public double attacksPerSecond() { return attackInterval > 0 ? 1.0 / attackInterval : 0; }
}
