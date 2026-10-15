package kr.labyrinth.event;

import kr.labyrinth.content.ItemDef;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;
import org.bukkit.inventory.ItemStack;

/**
 * 대장장이 강화 한 번이 끝난 뒤 items(강화)가 발생 (GDD §11.13). 칭호 ENHANCE 판정의 입력.
 * outcome = success | fail | downgrade | protected, from/to = 강화 전/후 단계.
 */
public final class EnhanceEvent extends Event {
    private static final HandlerList HANDLERS = new HandlerList();
    private final Player player;
    private final ItemDef def;
    private final ItemStack item;
    private final int from;
    private final int to;
    private final String outcome;

    public EnhanceEvent(Player player, ItemDef def, ItemStack item, int from, int to, String outcome) {
        this.player = player;
        this.def = def;
        this.item = item;
        this.from = from;
        this.to = to;
        this.outcome = outcome;
    }

    public Player player() { return player; }
    public ItemDef def() { return def; }
    /** 강화 뒤 아이템 (사본). */
    public ItemStack item() { return item; }
    public int from() { return from; }
    public int to() { return to; }
    public String outcome() { return outcome; }
    public boolean success() { return "success".equals(outcome); }

    @Override
    public HandlerList getHandlers() { return HANDLERS; }
    public static HandlerList getHandlerList() { return HANDLERS; }
}
