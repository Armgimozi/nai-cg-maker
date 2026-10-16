package kr.labyrinth.pvp;

import kr.labyrinth.combat.HealKind;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * PvP 전투 상태를 다른 모듈(회복·보호막·상태이상)이 묻는 창구 ({@link TargetFilter#pvp()}). pvp 모듈이 꺼져 있으면 {@link #NONE}
 * — 모두 그대로(배율 1, 시간 그대로).
 */
public interface PvpState {

    PvpState NONE = new PvpState() {};

    /** 다른 파티 플레이어와 피해를 주고받은 지 combat_seconds 안인가. */
    default boolean inCombat(Player p) { return false; }

    /** 받는 회복 배율 (PvP 전투 중: healing·potion·lifesteal × 긴 싸움). */
    default double healFactor(Player p, HealKind kind) { return 1.0; }

    /** 고정량 회복(치유력·흡혈·재생)의 추가 배율 = HP ÷ (HP + 완충) (PvP 전투 중일 때만). */
    default double flatHealFactor(Player p) { return 1.0; }

    /** 새로 얻는 보호막 배율 (PvP 전투 중: shield × 긴 싸움). */
    default double shieldFactor(Player p) { return 1.0; }

    /**
     * 플레이어에게 거는 상태이상 시간 (정신·판금 감소를 거친 값). source 가 다른 파티 플레이어면 PvP 배율 → 상한 → 줄어듦 → 면역.
     * @return 걸 시간(초). 0 = 걸지 않음
     */
    default double ccSeconds(Player target, LivingEntity source, String effectId, double seconds) { return seconds; }

    /** 플레이어에게 거는 상태이상 세기 (둔화 상한). */
    default double ccPotency(Player target, LivingEntity source, String effectId, double potency) { return potency; }

    /** 플레이어의 행동 불가(기절·빙결)가 끝났다 → 잠깐 면역. */
    default void onControlEnd(Player target) {}
}
