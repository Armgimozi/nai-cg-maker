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

    /**
     * 제련소 GUI (0.3.6, Q3): recipes.yml {@code station: smelter} — 탭 제련(광석 ×2 → 주괴, ×1·×8·전부) · 새기기(보석 + 정수 → 강화석 2) ·
     * 곡괭이(앞 곡괭이를 재료로 다시 벼림). 구역 제련공 NPC·interact smelter·광산 관리소가 연다. 레벨 조건 없음.
     */
    default void openSmelter(Player player) {
        kr.labyrinth.core.Log.notImplemented("CraftingService.openSmelter");
        kr.labyrinth.core.Text.error(player, "제련소가 아직 문을 열지 않았습니다.");
    }

    /**
     * 광부 상점 (0.3.6, Q3): 첫 구리 곡괭이 무료 1번 (ext mine.free_pickaxe) · 이후 구리 곡괭이 50G · 광석·주괴·보석 팔기 (SellMenu 그대로).
     * 광산 관리소({@code mine.MineApi#openOffice})의 곡괭이·팔기 탭이 이것을 쓴다.
     */
    default void openMineShop(Player player) {
        kr.labyrinth.core.Log.notImplemented("CraftingService.openMineShop");
        kr.labyrinth.core.Text.error(player, "광부 상점이 아직 문을 열지 않았습니다.");
    }
}
