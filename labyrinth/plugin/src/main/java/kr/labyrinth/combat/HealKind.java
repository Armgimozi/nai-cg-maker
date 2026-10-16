package kr.labyrinth.combat;

/**
 * 회복의 출처 (pvp_spec §8) — PvP 전투 중 회복 배율을 고르는 데 쓴다. 몹과 싸울 때는 모두 그대로.
 * <ul>
 *   <li>{@link #SKILL} 치유 스킬 (직업·무기 스킬 heal·mend·sanctuary)</li>
 *   <li>{@link #POTION} 치유 물약·재생의 비약 (healing × potion)</li>
 *   <li>{@link #LIFESTEAL} 플레이어를 때려 얻은 흡혈 (healing 대신 lifesteal)</li>
 *   <li>{@link #REGEN} HP 재생 (장비 hp_regen)</li>
 *   <li>{@link #OTHER} 그 밖 (옛 {@code heal(target, amount, show)})</li>
 * </ul>
 */
public enum HealKind { SKILL, POTION, LIFESTEAL, REGEN, OTHER }
