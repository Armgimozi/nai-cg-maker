package kr.labyrinth.items;

import com.destroystokyo.paper.event.inventory.PrepareResultEvent;
import io.papermc.paper.event.player.PlayerTradeEvent;
import kr.labyrinth.Services;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.CrafterCraftEvent;
import org.bukkit.event.enchantment.PrepareItemEnchantEvent;
import org.bukkit.event.inventory.FurnaceBurnEvent;
import org.bukkit.event.inventory.FurnaceStartSmeltEvent;
import org.bukkit.event.inventory.PrepareItemCraftEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.MerchantRecipe;

/**
 * 미궁 아이템이 바닐라 제작·화로·모루·숫돌·대장장이 작업대·지도 제작대·마법 부여·주민 거래 재료로 쓰이지 않게 막는다
 * (기반 재질이 종이/활이라 그냥 두면 책·지도 재료가 되거나 거래로 사라질 수 있음).
 */
final class ItemGuardListener implements Listener {

    private final Services services;

    ItemGuardListener(Services services) { this.services = services; }

    private boolean lab(ItemStack s) { return s != null && !s.isEmpty() && services.items().isLabyrinthItem(s); }

    private boolean anyLab(ItemStack[] items) {
        if (items == null) return false;
        for (ItemStack s : items) if (lab(s)) return true;
        return false;
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onCraft(PrepareItemCraftEvent e) {
        if (anyLab(e.getInventory().getMatrix())) e.getInventory().setResult(null);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onCrafter(CrafterCraftEvent e) {
        if (e.getBlock().getState() instanceof org.bukkit.inventory.InventoryHolder h && anyLab(h.getInventory().getContents())) {
            e.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onPrepareResult(PrepareResultEvent e) {
        if (anyLab(e.getInventory().getContents())) e.setResult(null);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onEnchant(PrepareItemEnchantEvent e) {
        if (lab(e.getItem())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onBurn(FurnaceBurnEvent e) {
        if (lab(e.getFuel())) e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onSmelt(FurnaceStartSmeltEvent e) {
        if (lab(e.getSource())) e.setTotalCookTime(Integer.MAX_VALUE);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onTrade(PlayerTradeEvent e) {
        MerchantRecipe r = e.getTrade();
        for (ItemStack ing : r.getIngredients()) {
            if (lab(ing)) {
                e.setCancelled(true);
                return;
            }
        }
        if (e.getPlayer().getOpenInventory().getTopInventory() != null
                && anyLab(e.getPlayer().getOpenInventory().getTopInventory().getContents())) {
            e.setCancelled(true);
        }
    }
}
