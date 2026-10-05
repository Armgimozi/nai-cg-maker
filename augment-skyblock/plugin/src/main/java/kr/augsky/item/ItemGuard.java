package kr.augsky.item;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.util.Items;
import org.bukkit.Keyed;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.inventory.FurnaceBurnEvent;
import org.bukkit.event.inventory.FurnaceSmeltEvent;
import org.bukkit.event.inventory.PrepareAnvilEvent;
import org.bukkit.event.inventory.PrepareItemCraftEvent;
import org.bukkit.event.inventory.PrepareSmithingEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.Recipe;

import java.util.ArrayList;
import java.util.List;

/** 바닐라 아이템을 껍데기로 쓰는 커스텀 아이템이 원래 용도(조합 재료, 설치, 연료 등)로 새지 않게 막는다. */
public final class ItemGuard implements Listener {
    private final AugSky plugin;

    public ItemGuard(AugSky plugin) {
        this.plugin = plugin;
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onCraft(PrepareItemCraftEvent e) {
        if (e.getRecipe() != null && !allowed(e.getRecipe(), e.getInventory().getMatrix())) e.getInventory().setResult(null);
    }

    /** 크래프터 블록은 PrepareItemCraftEvent 를 거치지 않으므로 따로 막는다. */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onCrafter(org.bukkit.event.block.CrafterCraftEvent e) {
        if (!(e.getBlock().getState(false) instanceof org.bukkit.block.Crafter c)) return;
        if (!allowed(e.getRecipe(), c.getInventory().getContents())) e.setCancelled(true);
    }

    /**
     * 이 재료로 이 조합을 해도 되는지.
     * - 바닐라 조합에는 커스텀 아이템을 넣을 수 없다.
     * - 무기/갑옷을 강화하는 조합은 정해진 무기, 정해진 세트의 같은 부위 갑옷만 받는다
     *   (조합법은 껍데기 재료로만 등록되어 있어서, 같은 껍데기의 다른 아이템이 들어갈 수 있다).
     */
    private boolean allowed(Recipe r, ItemStack[] matrix) {
        NamespacedKey key = r instanceof Keyed k ? k.getKey() : null;
        boolean ours = key != null && key.getNamespace().equals(Keys.NS);
        if (!ours) {
            for (ItemStack it : matrix) if (Items.isCustom(it)) return false;
            return true;
        }
        List<String> armorOk = plugin.recipes().armorInputs(key);
        if (armorOk != null) {
            for (ItemStack it : matrix) {
                if (it == null || !isArmorShell(it.getType())) continue;
                String set = kr.augsky.armor.ArmorService.setOf(it);
                var sl = kr.augsky.armor.ArmorService.slotOf(it);
                if (set == null || sl == null || !armorOk.contains(set + ":" + sl.id)) return false;
            }
        }
        List<String> need = plugin.recipes().weaponInputs(key);
        if (need != null) {
            List<String> have = new ArrayList<>();
            for (ItemStack it : matrix) {
                String w = Items.tag(it, Keys.WEAPON);
                if (w != null) have.add(w);
            }
            for (String n : need) if (!have.remove(n)) return false;
        }
        return true;
    }

    private static boolean isArmorShell(org.bukkit.Material m) {
        return switch (m) {
            case NETHERITE_HELMET, NETHERITE_CHESTPLATE, NETHERITE_LEGGINGS, NETHERITE_BOOTS -> true;
            default -> false;
        };
    }

    @EventHandler(ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent e) {
        if (Items.isCustom(e.getItemInHand())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onSmelt(FurnaceSmeltEvent e) {
        if (Items.isCustom(e.getSource())) e.setCancelled(true);
    }

    @EventHandler(ignoreCancelled = true)
    public void onBurn(FurnaceBurnEvent e) {
        if (Items.isCustom(e.getFuel())) e.setCancelled(true);
    }

    @EventHandler
    public void onAnvil(PrepareAnvilEvent e) {
        ItemStack a = e.getInventory().getFirstItem();
        ItemStack b = e.getInventory().getSecondItem();
        if (Items.tag(a, Keys.ITEM) != null || Items.tag(b, Keys.ITEM) != null) {
            e.setResult(null);
            return;
        }
        String wa = Items.tag(a, Keys.WEAPON), wb = Items.tag(b, Keys.WEAPON);
        if (wb != null && !wb.equals(wa)) e.setResult(null);
        if (wa == null && wb != null) e.setResult(null);
    }

    @EventHandler
    public void onSmith(PrepareSmithingEvent e) {
        for (ItemStack it : e.getInventory().getContents()) {
            if (Items.isCustom(it)) {
                e.setResult(null);
                return;
            }
        }
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        p.discoverRecipes(plugin.recipes().keys());
    }
}
