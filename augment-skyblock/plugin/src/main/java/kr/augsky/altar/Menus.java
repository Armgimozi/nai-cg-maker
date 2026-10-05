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
    public enum Kind { ALTAR, CHOICE, MINE, CODEX, WEAPONS }

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

    public void openAltar(Player p, Tier tier) {
        PlayerData d = aug().data(p);
        if (d.hasOffer()) {
            if (d.offerTier != tier) {
                p.sendMessage(Text.mm("<gray>먼저 고르지 않은 " + d.offerTier.label() + " <gray>선택지를 마저 고르세요."));
            }
            openChoice(p);
            return;
        }
        Holder h = new Holder(Kind.ALTAR, tier, 0);
        Inventory inv = create(h, 27, tier.wrap("✦ " + tier.korean + " 제단 ✦"));
        AugmentService.Cost cost = aug().cost(p, tier);
        boolean can = aug().canPay(p, cost);
        int owned = d.owned(tier, aug().registry());
        int total = aug().registry().ofTier(tier).size();

        inv.setItem(4, Items.icon(Material.NETHER_STAR, tier.wrap(tier.korean + " 제단"), List.of(
                "<gray>제물을 바치면 " + tier.wrap(tier.korean) + " <gray>증강 " + aug().choiceCount(p) + "개 중 하나를 고릅니다.",
                "<gray>보유한 " + tier.korean + " 증강: <white>" + owned + " <dark_gray>/ 전체 " + total + "종",
                "",
                "<dark_gray>증강을 많이 가질수록 제물이 늘어납니다.")));

        List<String> costLore = new ArrayList<>();
        costLore.add("<gray>필요한 제물:");
        if (cost.shards() > 0) costLore.add(line(p, "shard", cost.shards(), "증강 파편"));
        if (cost.crystals() > 0) costLore.add(line(p, "prism_crystal", cost.crystals(), "프리즘 결정"));
        for (Map.Entry<Material, Integer> en : cost.items().entrySet()) {
            int have = Items.count(p, it -> it.getType() == en.getKey() && !Items.isCustom(it));
            costLore.add((have >= en.getValue() ? "<#7cff8c>✔ " : "<#ff7070>✘ ") + "<white>" + korean(en.getKey())
                    + " <gray>×" + en.getValue() + " <dark_gray>(보유 " + have + ")");
        }
        if (cost.free()) costLore.add("<#7cff8c>무료");
        costLore.add("");
        costLore.add(can ? "<#ffcc55>▶ 클릭해서 바치기" : "<#ff7070>제물이 부족합니다");
        inv.setItem(11, Items.icon(Material.AMETHYST_CLUSTER, "<white>제물 바치기", costLore));
        h.slotIds.add("offer");

        boolean ticket = aug().hasTicket(p, tier);
        inv.setItem(15, Items.icon(ticket ? Material.PAPER : Material.GRAY_DYE,
                ticket ? tier.wrap(tier.korean + " 증강권 사용") : "<gray>" + tier.korean + " 증강권 없음",
                List.of("<gray>증강권 한 장으로 제물 없이 고릅니다.", "", ticket ? "<#ffcc55>▶ 클릭해서 사용" : "<dark_gray>보스나 시작 보급에서 얻습니다.")));
        inv.setItem(22, Items.icon(Material.BOOK, "<white>내 증강 보기", List.of("<gray>지금까지 얻은 증강 목록")));
        fill(inv, tier.pane);
        p.openInventory(inv);
    }

    private String line(Player p, String itemId, int need, String name) {
        int have = Items.count(p, it -> itemId.equals(Items.tag(it, kr.augsky.Keys.ITEM)));
        return (have >= need ? "<#7cff8c>✔ " : "<#ff7070>✘ ") + "<white>" + name + " <gray>×" + need + " <dark_gray>(보유 " + have + ")";
    }

    private static String korean(Material m) {
        return switch (m) {
            case GOLD_INGOT -> "금 주괴";
            case GOLD_BLOCK -> "금 블록";
            case IRON_INGOT -> "철 주괴";
            case DIAMOND -> "다이아몬드";
            case EMERALD -> "에메랄드";
            case LAPIS_LAZULI -> "청금석";
            case REDSTONE -> "레드스톤";
            case AMETHYST_SHARD -> "자수정 조각";
            default -> m.name().toLowerCase();
        };
    }

    // ------------------------------------------------------------------ 선택

    public void openChoice(Player p) {
        PlayerData d = aug().data(p);
        if (!d.hasOffer()) {
            p.sendMessage(Text.mm("<gray>고를 증강이 없습니다. 제단에 제물을 바치세요."));
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
        inv.setItem(22, Items.icon(d.rerolls > 0 ? Material.ENDER_EYE : Material.GRAY_DYE,
                d.rerolls > 0 ? "<#9ad8ff>다시 뽑기" : "<gray>다시 뽑기 없음",
                List.of("<gray>남은 횟수: <white>" + d.rerolls, "", d.rerolls > 0 ? "<#ffcc55>▶ 클릭" : "<dark_gray>이번에는 다시 뽑을 수 없습니다")));
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

    // ------------------------------------------------------------------ 클릭

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Holder h)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p)) return;
        if (e.getClickedInventory() == null || e.getClickedInventory() != e.getView().getTopInventory()) return;
        int slot = e.getSlot();
        switch (h.kind) {
            case ALTAR -> {
                if (slot == 11) {
                    if (aug().roll(p, h.tier, 1, List.of()).isEmpty()) {
                        p.sendMessage(Text.mm("<gray>더 얻을 수 있는 " + h.tier.korean + " 증강이 없습니다."));
                        return;
                    }
                    AugmentService.Cost cost = aug().cost(p, h.tier);
                    if (!aug().pay(p, cost)) {
                        p.sendMessage(Text.mm("<#ff7070>제물이 부족합니다."));
                        kr.augsky.util.Fx.sound(p.getLocation(), "entity.villager.no", 1, 1);
                        return;
                    }
                    begin(p, h.tier);
                } else if (slot == 15) {
                    if (!aug().hasTicket(p, h.tier)) return;
                    if (aug().roll(p, h.tier, 1, List.of()).isEmpty()) {
                        p.sendMessage(Text.mm("<gray>더 얻을 수 있는 " + h.tier.korean + " 증강이 없습니다."));
                        return;
                    }
                    aug().useTicket(p, h.tier);
                    begin(p, h.tier);
                } else if (slot == 22) {
                    openMine(p);
                }
            }
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
                if (slot == 22 && aug().reroll(p)) openChoice(p);
            }
            case MINE -> {
                if (slot == 53) openCodex(p, Tier.SILVER);
            }
            case CODEX -> {
                if (slot == 45) openCodex(p, Tier.SILVER);
                if (slot == 46) openCodex(p, Tier.GOLD);
                if (slot == 47) openCodex(p, Tier.PRISM);
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

    private void begin(Player p, Tier tier) {
        if (!aug().startOffer(p, tier)) {
            p.sendMessage(Text.mm("<gray>더 얻을 수 있는 " + tier.korean + " 증강이 없습니다. 제물은 돌려드립니다."));
            refund(p, tier);
            p.closeInventory();
            return;
        }
        kr.augsky.util.Fx.sound(p.getLocation(), "block.beacon.activate", 1f, 1.4f);
        p.getWorld().spawnParticle(org.bukkit.Particle.ENCHANT, p.getLocation().add(0, 1.5, 0), 80, 0.8, 0.8, 0.8, 1);
        openChoice(p);
    }

    private void refund(Player p, Tier tier) {
        AugmentService.Cost c = aug().cost(p, tier);
        if (c.shards() > 0) Items.give(p, plugin.items().create("shard", c.shards()));
        if (c.crystals() > 0) Items.give(p, plugin.items().create("prism_crystal", c.crystals()));
        for (Map.Entry<Material, Integer> en : c.items().entrySet()) Items.give(p, new ItemStack(en.getKey(), en.getValue()));
    }

    @EventHandler
    public void onDrag(InventoryDragEvent e) {
        if (e.getInventory().getHolder() instanceof Holder) e.setCancelled(true);
    }
}
