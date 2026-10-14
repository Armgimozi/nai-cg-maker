package kr.labyrinth.items;

import kr.labyrinth.content.RecipeDef;
import org.bukkit.entity.Player;

/**
 * 대장장이 제작 (recipes.yml, GDD §11.11). 소유: items 담당. 기본 구현 {@link NoopCraftingService}.
 * 성공 시 {@code event.CraftEvent} + {@code ItemObtainEvent(source=craft)}.
 */
public interface CraftingService {

    enum Result { OK, UNKNOWN_RECIPE, LEVEL_TOO_LOW, MISSING_MATERIALS, NOT_ENOUGH_GOLD, INVENTORY_FULL, NOT_AVAILABLE }

    /** 재료·골드·레벨 확인 (소모하지 않음). */
    Result check(Player player, RecipeDef recipe);

    /** 제작 시도 (확인 → 재료·골드 소모 → 결과 지급). */
    Result craft(Player player, String recipeId);

    /** 대장장이 GUI 열기 (NPC 우클릭·명령). */
    void openBlacksmith(Player player);
}
