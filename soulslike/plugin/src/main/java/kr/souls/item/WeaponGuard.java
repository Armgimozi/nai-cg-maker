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
 * 주손 막기가 왼손을 가리지 않게 (2.3 의 3). 주손 무기에 막기 성분이 있으면 우클릭이 그것을 먼저 쓰므로, 왼손에 무엇이든 있을 때는
 * (방패, 패링 단검, 왼손 무기, 촉매: 우클릭은 왼손에 든 것을 쓴다, DECISIONS 2026-10-10) 주손 무기에서 막기 성분을 떼고, 왼손이
 * 비면 (양손 잡기: 주무기로 막는다) 다시 붙인다. 왼손에 든 막는 무기 (단검·직검·도끼 …, use: guard) 도 막지 않는다: 왼손 무기의
 * 우클릭은 왼손 공격 (M1) 이라 패링 단검처럼 막기 성분을 뗀다 (검토 offhand-guard-weapons-still-block). 주손으로 돌아오면 위 규칙대로
 * 다시 붙는다.
 * 슬롯 바꾸기, 손 바꾸기 (F), 인벤토리 닫기, 접속 때 다음 틱에 다시 계산한다. 활의 당기기 성분 (CONSUMABLE) 은 끝까지
 * 당겨도 아이템이 줄지 않게 먹기를 취소한다 (활 쏘기는 M1).
 */
@SuppressWarnings("UnstableApiUsage")
public final class WeaponGuard implements Listener {
    private final Souls plugin;

    public WeaponGuard(Souls plugin) {
        this.plugin = plugin;
    }

    /** 지금 든 것에 맞춰 주손 무기의 막기 성분을 붙이거나 떼고, 왼손에 든 막는 무기의 막기 성분을 뗀다. 바뀌었으면 true. */
    public boolean refresh(Player p) {
        boolean changed = false;
        ItemStack off = p.getInventory().getItemInOffHand();
        Weapons.Def od = plugin.weapons().of(off);
        if (od != null && Weapons.GUARD.equals(od.use()) && off.hasData(DataComponentTypes.BLOCKS_ATTACKS)) {
            off.unsetData(DataComponentTypes.BLOCKS_ATTACKS);
            off.unsetData(DataComponentTypes.USE_EFFECTS);
            p.getInventory().setItemInOffHand(off);
            changed = true;
        }
        ItemStack main = p.getInventory().getItemInMainHand();
        Weapons.Def d = plugin.weapons().of(main);
        if (d == null || !Weapons.GUARD.equals(d.use())) return changed;
        boolean offHeld = !p.getInventory().getItemInOffHand().isEmpty();
        boolean has = main.hasData(DataComponentTypes.BLOCKS_ATTACKS);
        if (offHeld == !has) return changed;
        if (offHeld) {
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
