package kr.augsky.item;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Keyed;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.inventory.FurnaceBurnEvent;
import org.bukkit.event.inventory.FurnaceSmeltEvent;
import org.bukkit.event.inventory.PrepareAnvilEvent;
import org.bukkit.event.inventory.PrepareGrindstoneEvent;
import org.bukkit.event.inventory.PrepareItemCraftEvent;
import org.bukkit.event.inventory.PrepareSmithingEvent;
import org.bukkit.event.player.PlayerItemDamageEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerRecipeDiscoverEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.Recipe;
import org.bukkit.inventory.meta.Damageable;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 바닐라 아이템을 껍데기로 쓰는 커스텀 아이템이 원래 용도(조합 재료, 설치, 연료 등)로 새지 않게 막는다.
 * 장비의 모루·숫돌 규칙과 강화 조합의 마법 부여 옮기기, 내구도 경고도 여기서 한다.
 */
public final class ItemGuard implements Listener {
    private final AugSky plugin;

    public ItemGuard(AugSky plugin) {
        this.plugin = plugin;
        // 수선·무한 마법서를 숨겨 둔 상자 (AugSky 를 건드리지 않으려고 여기서 등록한다)
        Bukkit.getPluginManager().registerEvents(new kr.augsky.map.TreasureBooks(plugin), plugin);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onCraft(PrepareItemCraftEvent e) {
        var inv = e.getInventory();
        // 바닐라 '수리' 조합(같은 도구 둘)은 껍데기만 남은 바닐라 아이템을 만든다
        if (e.isRepair()) {
            for (ItemStack it : inv.getMatrix()) {
                if (Items.isCustom(it)) {
                    inv.setResult(null);
                    return;
                }
            }
        }
        if (e.getRecipe() == null) return;
        if (!allowed(e.getRecipe(), inv.getMatrix())) {
            inv.setResult(null);
            return;
        }
        ItemStack carried = carryEnchants(inv.getResult(), inv.getMatrix());
        if (carried != null) inv.setResult(carried);
    }

    /**
     * 강화 조합: 재료로 넣은 장비의 마법 부여를 결과로 옮긴다 (수선을 붙인 무기·곡괭이·갑옷을 강화해도 잃지 않게).
     * 같은 종류끼리만 강화하므로 거의 다 옮겨지지만, 결과에 붙을 수 없거나 서로 겹칠 수 없는 마법은 뺀다.
     * 내구도와 모루 누적 비용은 옮기지 않는다 (새 아이템). 옮길 게 없으면 null.
     */
    private ItemStack carryEnchants(ItemStack result, ItemStack[] matrix) {
        if (Gear.id(result) == null) return null;
        boolean noInfinity = arrowsFree(result);
        Map<Enchantment, Integer> want = new LinkedHashMap<>();
        for (ItemStack it : matrix) {
            if (Gear.id(it) == null) continue;
            for (Map.Entry<Enchantment, Integer> en : it.getEnchantments().entrySet()) want.merge(en.getKey(), en.getValue(), Math::max);
        }
        if (want.isEmpty()) return null;
        ItemStack out = result.clone();
        ItemMeta meta = out.getItemMeta();
        for (Map.Entry<Enchantment, Integer> en : want.entrySet()) {
            Enchantment ench = en.getKey();
            if (!ench.canEnchantItem(out) || (noInfinity && ench.equals(Enchantment.INFINITY))) continue;
            boolean clash = false;
            for (Enchantment have : meta.getEnchants().keySet()) if (have.conflictsWith(ench)) clash = true;
            if (!clash) meta.addEnchant(ench, en.getValue(), true);
        }
        out.setItemMeta(meta);
        return out;
    }

    /** 크래프터 블록은 PrepareItemCraftEvent 를 거치지 않으므로 따로 막고, 강화할 때 마법 부여도 여기서 옮긴다. */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onCrafter(org.bukkit.event.block.CrafterCraftEvent e) {
        if (!(e.getBlock().getState(false) instanceof org.bukkit.block.Crafter c)) return;
        ItemStack[] matrix = c.getInventory().getContents();
        if (!allowed(e.getRecipe(), matrix)) {
            e.setCancelled(true);
            return;
        }
        ItemStack carried = carryEnchants(e.getResult(), matrix);
        if (carried != null) e.setResult(carried);
    }

    /** 화살이 줄지 않는 활(보스·프리즘)인지. 무한은 이 활에 아무 쓸모가 없고 수선만 막으므로 붙지 않게 한다. */
    private boolean arrowsFree(ItemStack it) {
        kr.augsky.weapon.WeaponDef w = plugin.weapons().of(it);
        return w != null && w.infiniteArrows();
    }

    /** 마법 부여대: 화살이 줄지 않는 활에는 무한을 빼고 붙인다. 무한만 나왔으면 아무것도 붙지 않고 경험치·청금석도 들지 않는다 (바닐라 처리). */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onEnchant(org.bukkit.event.enchantment.EnchantItemEvent e) {
        if (!arrowsFree(e.getItem()) || e.getEnchantsToAdd().remove(Enchantment.INFINITY) == null) return;
        if (e.getEnchantsToAdd().isEmpty())
            e.getEnchanter().sendActionBar(Text.mm("<gray>이 활은 이미 화살이 줄지 않아 무한을 붙일 수 없다"));
    }

    /**
     * 이 재료로 이 조합을 해도 되는지.
     * - 바닐라 조합에는 커스텀 아이템을 넣을 수 없다.
     * - 무기/갑옷을 강화하는 조합은 정해진 무기, 정해진 세트의 같은 부위 갑옷만 받는다
     *   (숨은 조합법은 껍데기 재료로 등록되어 있어서 같은 껍데기의 다른 아이템이 들어갈 수 있다).
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
        // 철 곡괭이 껍데기 등은 바닐라 제련법(쇳조각)이 있어서, 굽기는 onSmelt 가 막아도 연료만 계속 탄다
        else if (e.getBlock().getState(false) instanceof org.bukkit.block.Furnace f && Items.isCustom(f.getInventory().getSmelting()))
            e.setCancelled(true);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onAnvil(PrepareAnvilEvent e) {
        if (!anvilOk(e.getInventory().getFirstItem(), e.getInventory().getSecondItem())) e.setResult(null);
        // 화살이 줄지 않는 활에 무한 마법서: 쓸모없이 수선만 막는다
        ItemStack r = e.getResult();
        if (r != null && r.containsEnchantment(Enchantment.INFINITY) && arrowsFree(r)) e.setResult(null);
    }

    /**
     * 모루에 이 둘을 올려도 되는지. 장비(무기·곡괭이·갑옷)는 이름 바꾸기, 바닐라 마법이 부여된 책,
     * 같은 장비끼리 합치기, 그 장비의 수리 재료로 고치기만 된다.
     * 같은 껍데기(네더라이트 검 등)의 다른 장비나 바닐라 아이템, 껍데기 기본 수리 재료(네더라이트 주괴)는 막는다.
     */
    private boolean anvilOk(ItemStack a, ItemStack b) {
        if (a == null || a.isEmpty()) return true;
        boolean noB = b == null || b.isEmpty();
        // 재료 아이템(파편, 정수, 결정, 증강권)은 이름을 바꾸거나 합칠 수 없다
        if (Items.tag(a, Keys.ITEM) != null) return false;
        String ga = Gear.id(a);
        if (ga == null) return noB || !Items.isCustom(b);
        if (noB) return true;
        if (b.getType() == Material.ENCHANTED_BOOK && !Items.isCustom(b)) return true;
        String gb = Gear.id(b);
        if (gb != null) return gb.equals(ga);
        Gear.Repair r = repairOf(a);
        return r != null && r.matches(b);
    }

    private Gear.Repair repairOf(ItemStack it) {
        kr.augsky.weapon.WeaponDef w = plugin.weapons().of(it);
        if (w != null) return plugin.weapons().repair(w);
        return plugin.armor().repair(kr.augsky.armor.ArmorService.setOf(it));
    }

    /** 숫돌에 둘을 올리면 바닐라는 같은 껍데기면 합쳐 버린다. 장비는 같은 장비끼리만 (하나만 올려 마법을 지우는 건 그대로). */
    @EventHandler(priority = EventPriority.HIGHEST)
    public void onGrind(PrepareGrindstoneEvent e) {
        ItemStack a = e.getInventory().getUpperItem(), b = e.getInventory().getLowerItem();
        if (a == null || a.isEmpty() || b == null || b.isEmpty()) return;
        String ga = Gear.id(a), gb = Gear.id(b);
        if (ga == null && gb == null) return;
        if (ga == null || !ga.equals(gb)) e.setResult(null);
    }

    /** 장비 내구도가 10%, 3% 아래로 떨어질 때 한 번씩 알린다 (갑옷은 내구도 막대가 인벤토리에서만 보인다). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onWear(PlayerItemDamageEvent e) {
        ItemStack it = e.getItem();
        if (Gear.id(it) == null || !(it.getItemMeta() instanceof Damageable dm) || !dm.hasMaxDamage()) return;
        int max = dm.getMaxDamage();
        int before = max - dm.getDamage(), after = before - e.getDamage();
        if (after <= 0) return; // 부서지는 건 바닐라가 알린다
        for (double f : new double[]{0.03, 0.10}) {
            int t = (int) Math.ceil(max * f);
            if (before <= t || after > t) continue;
            Player p = e.getPlayer();
            p.sendMessage(Text.mm("<#ff7070>⚠ ").append(it.effectiveName())
                    .append(Text.mm(" <gray>내구도 <#ff7070>" + after + "<gray>/" + max
                            + " <dark_gray>· 모루에서 수리 재료나 같은 아이템으로 고칠 수 있다")));
            p.playSound(p.getLocation(), "minecraft:block.anvil.land", 0.35f, 1.6f);
            break;
        }
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

    /** 숨은 조합법은 레시피 책에 넣지 않는다 (바닐라는 방금 쓴 조합법을 책에 넣어서 네더라이트 검 모양이 보이게 된다). */
    @EventHandler(ignoreCancelled = true)
    public void onDiscover(PlayerRecipeDiscoverEvent e) {
        if (plugin.recipes().isHidden(e.getRecipe())) e.setCancelled(true);
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        p.discoverRecipes(plugin.recipes().keys());
    }
}
