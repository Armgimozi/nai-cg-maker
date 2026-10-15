package kr.labyrinth.items;

import java.util.Map;
import java.util.Optional;
import kr.labyrinth.content.ItemDef;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * 아이템 정의 → ItemStack (ITEM_MODEL = labyrinth:&lt;id&gt;, EQUIPPABLE, 툴팁 lore, 굴림 스탯 PDC) 과 그 역방향.
 * 소유: items 담당. 기본 구현 {@link BasicItemService} (이름·모델·id 만 붙인 최소 아이템).
 * <p>
 * 장비 스탯은 구현이 {@code services.stats().addContributor(...)} 로 StatService 에 보탠다
 * (착용 방어구·보조손 방패·손에 든 무기·장신구 2칸·세트 효과). 바닐라 속성 수정치는 붙이지 않는다
 * (ATTRIBUTE_MODIFIERS 비우기 — 공격속도·이동속도는 StatService 가 기본값으로 관리).
 * PDC 키는 {@code core.Keys.ITEM_*}.
 */
public interface ItemService {

    /** 새로 굴린 아이템 1개. 정의가 없으면 null. */
    ItemStack create(String id);

    /** 시드로 굴림을 재현한 아이템. */
    ItemStack create(String id, long seed);

    /** amount 개 (스택 가능한 재료·소모품). 장비는 1개씩 따로 만들 것. */
    ItemStack create(String id, int amount);

    /** 미궁 아이템이면 정의. */
    Optional<ItemDef> defOf(ItemStack stack);

    /** 굴린 스탯 (키 = GDD §11.7, 강화 단계 배율 포함 — GDD §11.13). 굴림이 없으면 빈 맵. */
    Map<String, Double> rolledStats(ItemStack stack);

    /**
     * 스킬 위력 기준 무기 피해 = 그 무기 피해 범위의 가운데값 × 강화 배율 (combat_spec §3 'W 가운데값').
     * 굴림 운이 스킬 위력을 흔들지 않는다. 기본 구현은 굴린 피해 그대로.
     */
    default double midDamage(ItemStack stack) {
        return rolledStats(stack).getOrDefault("damage", 0.0);
    }

    /** 이름·툴팁을 아이템 PDC(굴림값·강화 단계)에서 다시 그린다. 기본 구현은 아무것도 안 한다. */
    default void refresh(ItemStack stack) {}

    /**
     * 지급 (인벤토리가 차면 발밑에 떨굼, 주인만 줍게). {@code event.ItemObtainEvent} 발생.
     * @param source drop | elite | boss | chest | craft | reward | shop | admin
     * @return 지급한 개수
     */
    int give(Player player, String id, int amount, String source);

    default boolean isLabyrinthItem(ItemStack stack) { return defOf(stack).isPresent(); }

    /** 미궁 무기(type: weapon)인가 — 직업 스킬 키(F/Q) 가로채기 판단에 쓴다. */
    default boolean isLabyrinthWeapon(ItemStack stack) {
        return defOf(stack).map(ItemDef::isWeapon).orElse(false);
    }

    /** 주 손 무기 정의 (없으면 null). */
    default ItemDef heldWeapon(Player player) {
        return defOf(player.getInventory().getItemInMainHand()).filter(ItemDef::isWeapon).orElse(null);
    }
}
