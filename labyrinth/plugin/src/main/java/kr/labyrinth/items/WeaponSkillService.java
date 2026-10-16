package kr.labyrinth.items;

import org.bukkit.entity.Player;

/**
 * 무기 스킬 (items.yml weapon_skills, 구현 = GDD §17 의 17종, items/weaponskills/*). 소유: items 담당.
 * 구현이 직접 PlayerInteract/PlayerAnimation 이벤트를 듣고 {@link #handle} 로 처리한다.
 * 기본 구현 {@link NoopWeaponSkillService}.
 */
public interface WeaponSkillService {

    enum Input { LEFT, RIGHT, SNEAK_LEFT, SNEAK_RIGHT }

    /**
     * 손에 든 무기의 해당 입력 스킬을 시전. 마나·쿨다운·침묵 확인 포함.
     * @return 스킬이 있어서 입력을 소비했으면 true (true 면 호출자는 바닐라 동작을 취소)
     */
    boolean handle(Player player, Input input);

    /** 남은 재사용 대기(초). 없으면 0. */
    double cooldownRemaining(Player player, String itemId, Input input);

    /** 그 무기(itemId)의 무기 스킬 재사용 대기를 모두 seconds 만큼 줄인다 (고유 효과 마력 흡수). */
    default void reduceCooldowns(Player player, String itemId, double seconds) {}
}
