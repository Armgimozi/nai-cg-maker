package kr.augsky.altar;

import kr.augsky.AugSky;
import kr.augsky.augment.AugmentDef;
import kr.augsky.augment.AugmentService;
import kr.augsky.augment.PlayerData;
import kr.augsky.augment.Tier;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import kr.augsky.weapon.Element;
import kr.augsky.weapon.WeaponDef;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** 제단 화면, 증강 선택 화면, 내 증강/도감 화면, 무기 도감. 모두 클릭만 받고 아이템은 못 꺼낸다. */
public final class Menus implements Listener {
    public enum Kind { CHOICE, MINE, CODEX, WEAPONS, ARMOR }

    public static final class Holder implements InventoryHolder {
        final Kind kind;
        final Tier tier;
        int page;
        Inventory inv;
        final List<String> slotIds = new ArrayList<>();

        Holder(Kind kind, Tier tier, int page) {
            this.kind = kind;
            this.tier = tier;
            this.page = page;
        }

        @Override
        public Inventory getInventory() {
            return inv;
        }
    }

    private static final int[][] CHOICE_SLOTS = {
            {}, {13}, {11, 15}, {11, 13, 15}, {10, 12, 14, 16}, {9, 11, 13, 15, 17}
    };

    private final AugSky plugin;

    public Menus(AugSky plugin) {
        this.plugin = plugin;
    }

    private AugmentService aug() {
        return plugin.augments();
    }

    private static Inventory create(Holder h, int size, String title) {
        Inventory inv = Bukkit.createInventory(h, size, Text.mm(title));
        h.inv = inv;
        return inv;
    }

    private static void fill(Inventory inv, Material pane) {
        ItemStack filler = Items.icon(pane, " ", List.of());
        for (int i = 0; i < inv.getSize(); i++) if (inv.getItem(i) == null) inv.setItem(i, filler);
    }

    // ------------------------------------------------------------------ 제단

    /**
     * 제단(또는 증강권)에서 증강 선택지를 받는다. 제물은 없다.
     * altarId 가 있으면 그 제단은 힘을 다한다(일회용 설정에 따라).
     */
    public boolean claim(Player p, Tier tier, java.util.UUID altarId) {
        if (!aug().startOffer(p, tier)) {
            p.sendMessage(Text.mm("<gray>더 얻을 수 있는 " + tier.korean + " 증강이 없습니다."));
            return false;
        }
        if (altarId != null) plugin.altars().consume(altarId, p);
        kr.augsky.util.Fx.sound(p.getLocation(), "block.beacon.activate", 1f, 1.4f);
        p.getWorld().spawnParticle(org.bukkit.Particle.ENCHANT, p.getLocation().add(0, 1.5, 0), 80, 0.8, 0.8, 0.8, 1);
        openChoice(p);
        return true;
    }

    // ------------------------------------------------------------------ 선택

    public void openChoice(Player p) {
        PlayerData d = aug().data(p);
        if (!d.hasOffer()) {
            p.sendMessage(Text.mm("<gray>고를 증강이 없습니다. 아직 쓰지 않은 제단을 찾아 우클릭하세요. <white>/증강 제단"));
            return;
        }
        Tier tier = d.offerTier;
        Holder h = new Holder(Kind.CHOICE, tier, 0);
        Inventory inv = create(h, 27, tier.wrap("✦ " + tier.korean + " 증강 선택 ✦"));
        int[] slots = CHOICE_SLOTS[Math.min(5, d.offer.size())];
        for (int i = 0; i < d.offer.size() && i < slots.length; i++) {
            AugmentDef def = aug().registry().get(d.offer.get(i));
            if (def == null) continue;
            inv.setItem(slots[i], card(def, d.stacks(def.id()), true));
        }
        int shardCost = aug().rerollShards();
        int shards = Items.count(p, it -> "shard".equals(Items.tag(it, kr.augsky.Keys.ITEM)));
        if (d.rerolls > 0) {
            inv.setItem(22, Items.icon(Material.ENDER_EYE, "<#9ad8ff>다시 뽑기 <gray>(무료)",
                    List.of("<gray>남은 무료 횟수: <white>" + d.rerolls, "", "<#ffcc55>▶ 클릭")));
        } else if (shardCost > 0) {
            boolean can = shards >= shardCost;
            inv.setItem(22, Items.icon(can ? Material.ENDER_EYE : Material.GRAY_DYE,
                    can ? "<#9ad8ff>다시 뽑기 <gray>(증강 파편 " + shardCost + "개)" : "<gray>다시 뽑기 <dark_gray>(증강 파편 " + shardCost + "개)",
                    List.of("<gray>무료 횟수를 다 썼습니다.", "<gray>증강 파편 " + shardCost + "개로 한 번 더 뽑습니다. <dark_gray>(보유 " + shards + ")",
                            "", can ? "<#ffcc55>▶ 클릭" : "<#ff7070>증강 파편이 부족합니다")));
        } else {
            inv.setItem(22, Items.icon(Material.GRAY_DYE, "<gray>다시 뽑기 없음", List.of("<dark_gray>이번에는 다시 뽑을 수 없습니다")));
        }
        inv.setItem(4, Items.icon(Material.NETHER_STAR, tier.wrap("하나를 고르세요"),
                List.of("<gray>창을 닫아도 선택지는 남아 있습니다.", "<gray>다시 열기: <white>/증강 선택")));
        fill(inv, tier.pane);
        p.openInventory(inv);
    }

    private ItemStack card(AugmentDef def, int stacks, boolean choosing) {
        List<Component> lore = new ArrayList<>();
        lore.add(Text.mm(def.tier().label() + (def.maxStacks() > 1 ? " <dark_gray>· 최대 " + def.maxStacks() + "중첩" : "")));
        lore.add(Component.empty());
        for (String s : def.description()) lore.add(Text.mm("<gray>" + s));
        if (stacks > 0) {
            lore.add(Component.empty());
            lore.add(Text.mm("<#7cd4ff>보유 중: " + stacks + "중첩"));
        }
        if (choosing) {
            lore.add(Component.empty());
            lore.add(Text.mm("<#ffcc55>▶ 클릭해서 획득"));
        }
        return Items.icon(def.icon(), Text.mm(def.tier().wrap(def.name())), lore, def.tier() == Tier.PRISM);
    }

    // ------------------------------------------------------------------ 내 증강 / 도감

    public void openMine(Player p) {
        PlayerData d = aug().data(p);
        Holder h = new Holder(Kind.MINE, null, 0);
        Inventory inv = create(h, 54, "<#ffcc55>내 증강 <dark_gray>(" + d.total() + ")");
        int i = 0;
        for (Tier t : Tier.values()) {
            for (Map.Entry<String, Integer> en : d.augments.entrySet()) {
                AugmentDef def = aug().registry().get(en.getKey());
                if (def == null || def.tier() != t || i >= 45) continue;
                inv.setItem(i++, card(def, en.getValue(), false));
            }
        }
        if (d.soul > 0) {
            inv.setItem(49, Items.icon(Material.WITHER_ROSE, "<#c86bff>영혼 수확", List.of("<gray>모은 최대 체력: <white>+" + Text.num(d.soul))));
        }
        inv.setItem(53, Items.icon(Material.KNOWLEDGE_BOOK, "<white>증강 도감", List.of("<gray>모든 증강 보기")));
        h.slotIds.add("codex");
        p.openInventory(inv);
    }

    public void openCodex(Player p, Tier tier) {
        PlayerData d = aug().data(p);
        Holder h = new Holder(Kind.CODEX, tier, 0);
        List<AugmentDef> list = aug().registry().ofTier(tier);
        Inventory inv = create(h, 54, tier.wrap("증강 도감 · " + tier.korean) + " <dark_gray>(" + list.size() + ")");
        int i = 0;
        for (AugmentDef def : list) {
            if (i >= 45) break;
            inv.setItem(i++, card(def, d.stacks(def.id()), false));
        }
        inv.setItem(45, Items.icon(Material.LIGHT_GRAY_DYE, Tier.SILVER.wrap("실버"), List.of()));
        inv.setItem(46, Items.icon(Material.YELLOW_DYE, Tier.GOLD.wrap("골드"), List.of()));
        inv.setItem(47, Items.icon(Material.MAGENTA_DYE, Tier.PRISM.wrap("프리즘"), List.of()));
        p.openInventory(inv);
    }

    public void openWeapons(Player p, int page) {
        Holder h = new Holder(Kind.WEAPONS, null, page);
        List<WeaponDef> all = new ArrayList<>(plugin.weapons().all().values());
        int pages = Math.max(1, (all.size() + 44) / 45);
        page = Math.max(0, Math.min(page, pages - 1));
        h.page = page;
        Inventory inv = create(h, 54, "<#ffcc55>무기 도감 <dark_gray>(" + all.size() + "종) " + (page + 1) + "/" + pages);
        for (int i = 0; i < 45 && page * 45 + i < all.size(); i++) {
            WeaponDef w = all.get(page * 45 + i);
            inv.setItem(i, plugin.weapons().create(w));
            h.slotIds.add(w.id());
        }
        if (page > 0) inv.setItem(45, Items.icon(Material.ARROW, "<white>이전", List.of()));
        if (page < pages - 1) inv.setItem(53, Items.icon(Material.ARROW, "<white>다음", List.of()));
        List<String> info = new ArrayList<>();
        java.util.Map<String, Long> byPool = new java.util.LinkedHashMap<>();
        for (WeaponDef w : all) byPool.merge(w.pool(), 1L, Long::sum);
        for (var en : byPool.entrySet()) info.add("<white>" + Element.poolName(en.getKey()) + " <gray>" + en.getValue() + "종");
        info.add("");
        info.add("<gray>만드는 법은 레시피 책(작업대)에서 볼 수 있어요.");
        if (p.hasPermission("augsky.admin")) info.add("<#ffcc55>관리자: 클릭하면 받습니다");
        inv.setItem(49, Items.icon(Material.BOOK, "<white>무기를 얻는 곳", info));
        p.openInventory(inv);
    }

    /** 갑옷 도감: 세트마다 한 줄(세로)로 투구, 갑옷, 각반, 신발, 세트 효과. */
    public void openArmor(Player p) {
        Holder h = new Holder(Kind.ARMOR, null, 0);
        var sets = new ArrayList<>(plugin.armor().all().values());
        Inventory inv = create(h, 54, "<#ffcc55>갑옷 도감 <dark_gray>(" + sets.size() + "세트)");
        var slots = kr.augsky.armor.ArmorService.Slot.values();
        for (int c = 0; c < 9 && c < sets.size(); c++) {
            var s = sets.get(c);
            for (int r = 0; r < 4; r++) {
                inv.setItem(r * 9 + c, plugin.armor().create(s.id(), slots[r]));
            }
            List<String> info = new ArrayList<>(plugin.armor().describe(s.id()));
            info.add("");
            info.add("<#8a8a9a>▸ " + s.source());
            if (p.hasPermission("augsky.admin")) info.add("<#ffcc55>관리자: 클릭하면 한 벌 받습니다");
            inv.setItem(4 * 9 + c, Items.icon(Material.BOOK, s.colored(s.name() + " 세트"), info));
            h.slotIds.add(s.id());
        }
        fill(inv, Material.BLACK_STAINED_GLASS_PANE);
        p.openInventory(inv);
    }

    // ------------------------------------------------------------------ 클릭

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Holder h)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p)) return;
        if (e.getClickedInventory() == null || e.getClickedInventory() != e.getView().getTopInventory()) return;
        int slot = e.getSlot();
        switch (h.kind) {
            case CHOICE -> {
                PlayerData d = aug().data(p);
                if (!d.hasOffer()) {
                    p.closeInventory();
                    return;
                }
                int[] slots = CHOICE_SLOTS[Math.min(5, d.offer.size())];
                for (int i = 0; i < slots.length; i++) {
                    if (slots[i] == slot) {
                        p.closeInventory();
                        aug().pick(p, i);
                        return;
                    }
                }
                if (slot == 22) {
                    if (aug().reroll(p)) openChoice(p);
                    else kr.augsky.util.Fx.sound(p.getLocation(), "entity.villager.no", 1, 1);
                }
            }
            case MINE -> {
                if (slot == 53) openCodex(p, Tier.SILVER);
            }
            case CODEX -> {
                if (slot == 45) openCodex(p, Tier.SILVER);
                if (slot == 46) openCodex(p, Tier.GOLD);
                if (slot == 47) openCodex(p, Tier.PRISM);
            }
            case ARMOR -> {
                if (!p.hasPermission("augsky.admin")) return;
                int c = slot % 9, r = slot / 9;
                if (c >= h.slotIds.size() || r > 4) return;
                var slots = kr.augsky.armor.ArmorService.Slot.values();
                if (r < 4) Items.give(p, plugin.armor().create(h.slotIds.get(c), slots[r]));
                else for (var sl : slots) Items.give(p, plugin.armor().create(h.slotIds.get(c), sl));
            }
            case WEAPONS -> {
                if (slot == 45) openWeapons(p, h.page - 1);
                else if (slot == 53) openWeapons(p, h.page + 1);
                else if (slot < 45 && slot < h.slotIds.size() && p.hasPermission("augsky.admin")) {
                    Items.give(p, plugin.weapons().create(h.slotIds.get(slot)));
                }
            }
        }
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        if (e.getInventory().getHolder() instanceof Holder) e.setCancelled(true);
    }
}
