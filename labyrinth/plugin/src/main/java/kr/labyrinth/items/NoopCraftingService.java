package kr.labyrinth.items;

import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.entity.Player;

/** 안전한 기본 구현: 제작 불가 안내. */
public class NoopCraftingService implements CraftingService {
    @Override
    public Result check(Player player, RecipeDef recipe) { return Result.NOT_AVAILABLE; }

    @Override
    public Result craft(Player player, String recipeId) {
        Log.notImplemented("CraftingService.craft");
        return Result.NOT_AVAILABLE;
    }

    @Override
    public void openBlacksmith(Player player) {
        Log.notImplemented("CraftingService.openBlacksmith");
        Text.error(player, "대장간이 아직 문을 열지 않았습니다.");
    }
}
