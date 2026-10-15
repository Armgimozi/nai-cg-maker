package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.LinkedHashMap;
import java.util.Map;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.items.CraftingService.Result;
import kr.labyrinth.items.crafting.RecipeCheck;
import org.junit.jupiter.api.Test;

/** 대장장이 조건 확인 순서(재료 → 골드, 레벨 제한 없음)·할인 상한 (GDD §11.11). */
class RecipeCheckTest {

    private static RecipeDef recipe() {
        Map<String, Integer> mats = new LinkedHashMap<>();
        mats.put("moss_fiber", 6);
        mats.put("beetle_shell", 4);
        return new RecipeDef("corridor_longsword", "corridor_longsword", "weapon", "blacksmith", mats, 1000, 5, 1);
    }

    @Test
    void okWhenEverythingIsThere() {
        assertEquals(Result.OK, RecipeCheck.check(recipe(), 5, 1000, 0, id -> 99));
    }

    @Test
    void noCraftingLevelGate() {
        // recipes.yml level_req 는 더 이상 보지 않는다 — 장비는 입을 때 요구 능력치로 가린다
        assertEquals(Result.OK, RecipeCheck.check(recipe(), 1, 1000, 0, id -> 99));
        assertEquals(Result.OK, RecipeCheck.check(recipe(), 1000, 0, id -> 99));
        assertEquals(Result.MISSING_MATERIALS, RecipeCheck.check(recipe(), 1, 0, 0, id -> 0));
    }

    @Test
    void checksMaterialsThenGold() {
        assertEquals(Result.MISSING_MATERIALS, RecipeCheck.check(recipe(), 10, 0, 0, id -> id.equals("moss_fiber") ? 6 : 3));
        assertEquals(Result.NOT_ENOUGH_GOLD, RecipeCheck.check(recipe(), 10, 999, 0, id -> 10));
    }

    @Test
    void discountLowersGoldAndIsCapped() {
        assertEquals(900, RecipeCheck.goldCost(recipe(), 0.10));
        assertEquals(700, RecipeCheck.goldCost(recipe(), 0.95), "할인은 최대 30%");
        assertEquals(1000, RecipeCheck.goldCost(recipe(), -1));
        assertEquals(Result.OK, RecipeCheck.check(recipe(), 10, 900, 0.10, id -> 10));
    }

    @Test
    void unknownRecipe() {
        assertEquals(Result.UNKNOWN_RECIPE, RecipeCheck.check(null, 10, 0, 0, id -> 0));
    }
}
