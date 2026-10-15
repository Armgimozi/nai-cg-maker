package kr.labyrinth.items.crafting;

import java.util.Map;
import java.util.function.ToIntFunction;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.items.CraftingService;

/**
 * 레시피 조건 확인 — 순수 로직 (GDD §11.11, 단위 테스트 대상). 순서: 재료 → 골드.
 * 제작에는 레벨 제한이 없다 (recipes.yml level_req 는 읽기만 하고 보지 않는다 — 장비는 착용 때 요구 능력치로 가린다).
 */
public final class RecipeCheck {

    /** craft_discount 상한 (GDD §11.7). */
    public static final double MAX_DISCOUNT = 0.30;

    private RecipeCheck() {}

    /** 할인 적용 골드 (반올림, 0 이상). */
    public static long goldCost(RecipeDef r, double craftDiscount) {
        double d = Math.max(0, Math.min(MAX_DISCOUNT, craftDiscount));
        return Math.max(0, Math.round(r.gold() * (1.0 - d)));
    }

    /** @param level 판정에 쓰지 않음 — 호출부 호환용 (제작 레벨 제한 없음) */
    public static CraftingService.Result check(RecipeDef r, int level, long gold, double craftDiscount,
                                               ToIntFunction<String> countOf) {
        return check(r, gold, craftDiscount, countOf);
    }

    /**
     * @param countOf 재료 id → 보유 개수
     */
    public static CraftingService.Result check(RecipeDef r, long gold, double craftDiscount, ToIntFunction<String> countOf) {
        if (r == null) return CraftingService.Result.UNKNOWN_RECIPE;
        for (Map.Entry<String, Integer> m : r.materials().entrySet()) {
            if (countOf.applyAsInt(m.getKey()) < m.getValue()) return CraftingService.Result.MISSING_MATERIALS;
        }
        if (gold < goldCost(r, craftDiscount)) return CraftingService.Result.NOT_ENOUGH_GOLD;
        return CraftingService.Result.OK;
    }
}
