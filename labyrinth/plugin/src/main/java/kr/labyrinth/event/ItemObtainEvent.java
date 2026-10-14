package kr.labyrinth.event;

import kr.labyrinth.content.ItemDef;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;
import org.bukkit.inventory.ItemStack;

/**
 * 플레이어가 미궁 아이템을 얻었을 때 (루팅·제작·보상·상점·관리자 지급). ItemService/LootService/CraftingService 가 발생.
 * 칭호 OBTAIN_RARITY 판정, 전설/신화 방송의 입력.
 *
 * @param source drop | elite | boss | chest | craft | reward | shop | admin
 */
public final class ItemObtainEvent extends Event {
    private static final HandlerList HANDLERS = new HandlerList();
    private final Player player;
    private final ItemDef def;
    private final ItemStack stack;
    private final String source;

    public ItemObtainEvent(Player player, ItemDef def, ItemStack stack, String source) {
        this.player = player;
        this.def = def;
        this.stack = stack;
        this.source = source;
    }

    public Player player() { return player; }
    public ItemDef def() { return def; }
    public ItemStack stack() { return stack; }
    public String source() { return source; }

    @Override
    public HandlerList getHandlers() { return HANDLERS; }
    public static HandlerList getHandlerList() { return HANDLERS; }
}
