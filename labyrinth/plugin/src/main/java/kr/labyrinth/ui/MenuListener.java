package kr.labyrinth.ui;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.core.Log;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryAction;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.inventory.Inventory;

/** {@link Menu} 클릭 보호 + 버튼 디스패치. 연타 방지 120ms. */
public final class MenuListener implements Listener {

    private static final long CLICK_GAP_MS = 120;
    private final Map<UUID, Long> lastClick = new ConcurrentHashMap<>();

    @EventHandler(priority = EventPriority.LOWEST)
    public void onClick(InventoryClickEvent e) {
        Inventory top = e.getView().getTopInventory();
        if (!(top.getHolder(false) instanceof Menu menu)) return;
        if (!(e.getWhoClicked() instanceof Player player)) {
            e.setCancelled(true);
            return;
        }
        boolean topClick = e.getClickedInventory() != null && e.getClickedInventory().equals(top);
        if (!topClick && menu.allowBottomClicks() && e.getAction() != InventoryAction.MOVE_TO_OTHER_INVENTORY
                && e.getAction() != InventoryAction.COLLECT_TO_CURSOR) {
            e.setCancelled(true);
            safe(() -> menu.onBottomClick(new ClickContext(player, menu, e.getSlot(), e.getClick(), e)));
            return;
        }
        e.setCancelled(true);
        if (!topClick) return;
        Button b = menu.button(e.getRawSlot());
        if (b == null || b.action() == null) return;
        long now = System.currentTimeMillis();
        Long last = lastClick.put(player.getUniqueId(), now);
        if (last != null && now - last < CLICK_GAP_MS) return;
        safe(() -> b.action().accept(new ClickContext(player, menu, e.getRawSlot(), e.getClick(), e)));
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onDrag(InventoryDragEvent e) {
        Inventory top = e.getView().getTopInventory();
        if (!(top.getHolder(false) instanceof Menu)) return;
        for (int raw : e.getRawSlots()) {
            if (raw < top.getSize()) {
                e.setCancelled(true);
                return;
            }
        }
    }

    @EventHandler
    public void onClose(InventoryCloseEvent e) {
        if (e.getInventory().getHolder(false) instanceof Menu menu && e.getPlayer() instanceof Player p) {
            safe(() -> menu.onClose(p));
        }
    }

    private static void safe(Runnable r) {
        try {
            r.run();
        } catch (Throwable t) {
            Log.error("메뉴 처리 중 오류", t);
        }
    }
}
