package kr.labyrinth.combat;

import java.util.random.RandomGenerator;

/**
 * 피해 공식 (GDD §3, §11.2, §11.7) — 순수 함수. 단위 테스트 대상.
 * <ol>
 *   <li>원피해 × (1 + 주는 피해 버프) × (스킬이면 1 + skill_damage)</li>
 *   <li>회피 판정 (회피 가능할 때) → 0</li>
 *   <li>치명타 판정 → × 치명타 피해</li>
 *   <li>방어: × 100 / (100 + 방어)  (TRUE/방어 무시 제외)</li>
 *   <li>× (1 − 피해 감소) × (1 + 받는 피해 증가)</li>
 *   <li>막기(정면·막기 가능) → × 0.4</li>
 * </ol>
 */
public final class DamageFormula {

    public static final double BLOCK_FACTOR = 0.4;

    private DamageFormula() {}

    /** 계산 입력 (공격자/대상 능력치 요약). */
    public record Input(double amount, boolean skill, double attackerDamageMult, double attackerSkillDamage,
                        double critChance, double critDamage, boolean canCrit,
                        double evasion, boolean canEvade,
                        double defense, boolean ignoreDefense,
                        double damageReduction, double damageTaken,
                        double blockChance, boolean canBlock) {}

    public record Output(double damage, boolean crit, boolean evaded, boolean blocked) {}

    public static double defenseFactor(double defense) {
        return 100.0 / (100.0 + Math.max(0, defense));
    }

    /** 치명 피해 배율의 '추가' 몫만 scale 배 (PvP crit_damage_scale: 2.5, 0.6 → 1.9). */
    public static double scaledCritDamage(double critDamage, double scale) {
        return 1.0 + Math.max(0, critDamage - 1.0) * Math.max(0, scale);
    }

    public static Output compute(Input in, RandomGenerator rng) {
        double dmg = Math.max(0, in.amount());
        dmg *= Math.max(0.1, 1.0 + in.attackerDamageMult());
        if (in.skill()) dmg *= Math.max(0.1, 1.0 + in.attackerSkillDamage());

        if (in.canEvade() && in.evasion() > 0 && rng.nextDouble() < in.evasion()) {
            return new Output(0, false, true, false);
        }
        boolean crit = in.canCrit() && in.critChance() > 0 && rng.nextDouble() < in.critChance();
        if (crit) dmg *= Math.max(1.0, in.critDamage());
        if (!in.ignoreDefense()) dmg *= defenseFactor(in.defense());
        dmg *= 1.0 - Math.max(0, Math.min(0.9, in.damageReduction()));
        dmg *= Math.max(0.1, 1.0 + in.damageTaken());
        boolean blocked = in.canBlock() && in.blockChance() > 0 && rng.nextDouble() < in.blockChance();
        if (blocked) dmg *= BLOCK_FACTOR;
        return new Output(Math.max(0, dmg), crit, false, blocked);
    }
}
