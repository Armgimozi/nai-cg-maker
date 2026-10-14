package kr.labyrinth.items;

import java.util.Collection;
import java.util.List;
import kr.labyrinth.core.Log;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/** 안전한 기본 구현: 드롭 없음. */
public class NoopLootService implements LootService {
    @Override
    public List<ItemStack> roll(String tableId, Player looter, InstanceContext ctx) {
        Log.notImplemented("LootService.roll");
        return List.of();
    }

    @Override
    public void drop(String tableId, Collection<Player> looters, Location location, InstanceContext ctx, String source) {
        Log.notImplemented("LootService.drop");
    }
}
