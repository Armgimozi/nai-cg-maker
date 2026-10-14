package kr.labyrinth.event;

import kr.labyrinth.content.RecipeDef;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;
import org.bukkit.inventory.ItemStack;

/** 대장장이 제작 성공 후 CraftingService 가 발생. 칭호 CRAFT 판정의 입력. */
public final class CraftEvent extends Event {
    private static final HandlerList HANDLERS = new HandlerList();
    private final Player player;
    private final RecipeDef recipe;
    private final ItemStack result;

    public CraftEvent(Player player, RecipeDef recipe, ItemStack result) {
        this.player = player;
        this.recipe = recipe;
        this.result = result;
    }

    public Player player() { return player; }
    public RecipeDef recipe() { return recipe; }
    public ItemStack result() { return result; }

    @Override
    public HandlerList getHandlers() { return HANDLERS; }
    public static HandlerList getHandlerList() { return HANDLERS; }
}
