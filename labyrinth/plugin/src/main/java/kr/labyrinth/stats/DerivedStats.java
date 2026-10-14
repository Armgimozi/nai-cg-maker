package kr.labyrinth.stats;

import java.util.Map;

/**
 * 파생 능력치 (StatCalculator 결과, 불변). 비율 값은 0~1 (0.15 = 15%).
 *
 * @param stats          최종 스탯 6종 (직업 기본 + 분배 + 장비/칭호/버프)
 * @param weaponDamage   무기 피해(굴림값). 맨손이면 기본값
 * @param attackPower    공격력 = 무기 피해 × (1 + 0.02 × 주스탯혼합)
 * @param damageMult     주는 피해 배율 가산 (버프 damage_mult, weaken 음수)
 * @param damageTaken    받는 피해 배율 가산 (vulnerable)
 * @param debuffReduction 해로운 효과 지속시간 감소 (WIS, stun 제외)
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
        double damageTaken) {

    public int stat(Stat s) { return stats.getOrDefault(s, 0); }
}
