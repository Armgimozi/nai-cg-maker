package kr.labyrinth.items;

import kr.labyrinth.core.ArmorLooks;

/**
 * 천 4부위 — 마나 보호막 (look_spec §1.3, 순수 — 단위 테스트 대상). 받는 최종 피해(방어·감소·막기·보호막·무적 뒤)의
 * {@code absorb} 를 MP 가 대신 받는다 (MP 1 = 피해 {@code damage_per_mp}). MP 가 최대의 {@code off_below} 아래면 쉬고,
 * 경계 바로 위면 경계까지 남은 MP 만큼만 막는다 — 스킬 쓸 MP 를 남긴다. 지속 피해·고정 피해에도 든다.
 */
public final class ManaShield {

    /** @param hpDamage HP 로 받을 피해 · @param mpCost 쓸 MP · absorbed = 막은 피해 */
    public record Split(double hpDamage, double mpCost, double absorbed) {}

    private ManaShield() {}

    public static Split split(double damage, double mp, double maxMp, ArmorLooks.ManaShield cfg) {
        if (!(damage > 0) || cfg == null || !(cfg.absorb() > 0) || !(maxMp > 0)) return new Split(Math.max(0, damage), 0, 0);
        double floor = cfg.offBelow() * maxMp;
        double spare = mp - floor;
        if (!(spare > 0)) return new Split(damage, 0, 0);
        double absorbed = damage * cfg.absorb();
        double cost = absorbed / cfg.damagePerMp();
        if (cost > spare) {
            cost = spare;
            absorbed = cost * cfg.damagePerMp();
        }
        return new Split(damage - absorbed, cost, absorbed);
    }
}
