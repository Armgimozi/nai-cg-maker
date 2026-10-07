package kr.souls.util;

import kr.souls.Keys;
import kr.souls.Lang;
import net.kyori.adventure.text.Component;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;

import java.util.HashMap;
import java.util.List;

public final class Items {
    private Items() {}

    /** 창의 그림 칸 같은 아이템. 이름과 설명은 lang 열쇠 (loreKey 는 목록 열쇠, 없으면 null). */
    public static ItemStack icon(Material m, String nameKey, String loreKey) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(Lang.c(nameKey));
        if (loreKey != null) meta.lore(Lang.lines(loreKey));
        meta.addItemFlags(ItemFlag.values());
        it.setItemMeta(meta);
        return it;
    }

    public static ItemStack icon(Material m, Component name, List<Component> lore, boolean glint) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(name);
        if (lore != null && !lore.isEmpty()) meta.lore(lore);
        meta.addItemFlags(ItemFlag.values());
        if (glint) meta.setEnchantmentGlintOverride(true);
        it.setItemMeta(meta);
        return it;
    }

    public static String tag(ItemStack it, NamespacedKey key) {
        if (it == null || it.getType() == Material.AIR || !it.hasItemMeta()) return null;
        return it.getItemMeta().getPersistentDataContainer().get(key, PersistentDataType.STRING);
    }

    public static boolean isCustom(ItemStack it) {
        return tag(it, Keys.ITEM) != null || tag(it, Keys.WEAPON) != null || tag(it, Keys.ARMOR) != null;
    }

    /** 인벤토리에 넣고, 넘치면 발밑에 떨어뜨린다. */
    public static void give(Player p, ItemStack item) {
        if (item == null || item.getType() == Material.AIR) return;
        HashMap<Integer, ItemStack> left = p.getInventory().addItem(item);
        for (ItemStack rest : left.values()) {
            Location l = p.getLocation();
            Item drop = p.getWorld().dropItem(l, rest);
            drop.setPickupDelay(0);
            drop.setOwner(p.getUniqueId());
        }
    }

    /** 인벤토리에서 조건에 맞는 아이템 개수를 센다. */
    public static int count(Player p, java.util.function.Predicate<ItemStack> match) {
        int n = 0;
        for (ItemStack it : p.getInventory().getStorageContents()) {
            if (it != null && match.test(it)) n += it.getAmount();
        }
        ItemStack off = p.getInventory().getItemInOffHand();
        if (off != null && match.test(off)) n += off.getAmount();
        return n;
    }

    /** 조건에 맞는 아이템을 amount 개 제거한다. 모자라면 아무것도 지우지 않고 false. */
    public static boolean take(Player p, java.util.function.Predicate<ItemStack> match, int amount) {
        if (amount <= 0) return true;
        if (count(p, match) < amount) return false;
        int need = amount;
        ItemStack[] contents = p.getInventory().getStorageContents();
        for (int i = 0; i < contents.length && need > 0; i++) {
            ItemStack it = contents[i];
            if (it == null || !match.test(it)) continue;
            int use = Math.min(need, it.getAmount());
            it.setAmount(it.getAmount() - use);
            need -= use;
            contents[i] = it.getAmount() <= 0 ? null : it;
        }
        p.getInventory().setStorageContents(contents);
        if (need > 0) {
            ItemStack off = p.getInventory().getItemInOffHand();
            if (off != null && match.test(off)) {
                int use = Math.min(need, off.getAmount());
                off.setAmount(off.getAmount() - use);
                p.getInventory().setItemInOffHand(off.getAmount() <= 0 ? null : off);
            }
        }
        return true;
    }
}
