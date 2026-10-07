package kr.souls.item;

import io.papermc.paper.datacomponent.DataComponentTypes;
import kr.souls.Souls;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.player.PlayerItemConsumeEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.inventory.ItemStack;

/**
 * 주손 막기가 왼손 방패를 가리지 않게 (2.3 의 3). 주손 무기에 막기 성분이 있으면 우클릭이 그것을 먼저 쓰므로, 왼손에 막는 것
 * (방패, 쳐내기 단검, 시험 막기 도구) 이 있을 때는 주손 무기에서 막기 성분을 떼고, 왼손이 비면 다시 붙인다.
 * 슬롯 바꾸기, 손 바꾸기 (F), 인벤토리 닫기, 접속 때 다음 틱에 다시 계산한다. 활의 당기기 성분 (CONSUMABLE) 은 끝까지
 * 당겨도 아이템이 줄지 않게 먹기를 취소한다 (활 쏘기는 M1).
 */
@SuppressWarnings("UnstableApiUsage")
public final class WeaponGuard implements Listener {
    private final Souls plugin;

    public WeaponGuard(Souls plugin) {
        this.plugin = plugin;
    }

    /** 지금 든 것에 맞춰 주손 무기의 막기 성분을 붙이거나 뗀다. 바뀌었으면 true. */
    public boolean refresh(Player p) {
        ItemStack main = p.getInventory().getItemInMainHand();
        Weapons.Def d = plugin.weapons().of(main);
        if (d == null || !Weapons.GUARD.equals(d.use())) return false;
        ItemStack off = p.getInventory().getItemInOffHand();
        boolean offBlocks = !off.isEmpty() && off.hasData(DataComponentTypes.BLOCKS_ATTACKS);
        boolean has = main.hasData(DataComponentTypes.BLOCKS_ATTACKS);
        if (offBlocks == !has) return false;
        if (offBlocks) {
            main.unsetData(DataComponentTypes.BLOCKS_ATTACKS);
            main.unsetData(DataComponentTypes.USE_EFFECTS);
        } else {
            main.setData(DataComponentTypes.BLOCKS_ATTACKS, ItemFactory.guardComponent());
            main.setData(DataComponentTypes.USE_EFFECTS, ItemFactory.guardUse((float) d.walk()));
        }
        p.getInventory().setItemInMainHand(main);
        return true;
    }

    private void later(Player p) {
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline()) refresh(p);
        });
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHeld(PlayerItemHeldEvent e) {
        later(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        later(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onClose(InventoryCloseEvent e) {
        if (e.getPlayer() instanceof Player p) later(p);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        later(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onConsume(PlayerItemConsumeEvent e) {
        if (plugin.weapons().of(e.getItem()) != null) e.setCancelled(true);
    }
}
