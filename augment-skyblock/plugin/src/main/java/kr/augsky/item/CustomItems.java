package kr.augsky.item;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.util.P;
import kr.augsky.util.Text;
import kr.augsky.weapon.WeaponDef;
import net.kyori.adventure.text.Component;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.BookMeta;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** items.yml 의 재료 아이템(파편, 결정, 증강권, 정수, 소환석)과 "아이템 문자열" 해석. */
public final class CustomItems {
    public record Def(String id, String name, Material material, List<String> lore, boolean glint, P raw) {}

    private final AugSky plugin;
    private final Map<String, Def> defs = new LinkedHashMap<>();

    public CustomItems(AugSky plugin) {
        this.plugin = plugin;
    }

    public void load(YamlConfiguration yml) {
        defs.clear();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            P p = P.of(sec);
            Material m = Material.matchMaterial(p.s("material", "PAPER"));
            if (m == null) m = Material.PAPER;
            defs.put(id, new Def(id, p.s("name", id), m, p.strings("lore"), p.b("glint", false), p));
        }
        plugin.getLogger().info("재료 아이템 " + defs.size() + "종 불러옴");
    }

    public Def def(String id) {
        return defs.get(id);
    }

    public Map<String, Def> all() {
        return defs;
    }

    public ItemStack create(String id, int amount) {
        Def d = defs.get(id);
        if (d == null) return null;
        ItemStack it = new ItemStack(d.material(), Math.max(1, amount));
        ItemMeta meta = it.getItemMeta();
        meta.displayName(Text.mm(d.name()));
        if (!d.lore().isEmpty()) meta.lore(Text.mm(d.lore()));
        if (plugin.getConfig().getBoolean("resource-pack.custom-models", true)) {
            meta.setItemModel(new NamespacedKey(Keys.NS, id));
        }
        if (d.glint()) meta.setEnchantmentGlintOverride(true);
        meta.addItemFlags(ItemFlag.HIDE_ADDITIONAL_TOOLTIP);
        meta.getPersistentDataContainer().set(Keys.ITEM, PersistentDataType.STRING, id);
        it.setItemMeta(meta);
        return it;
    }

    /**
     * 아이템 문자열: "shard", "item:shard", "weapon:flame_sword", "pool:frost"(그 pool 의 무작위 무기),
     * "armor:frost"(서리 세트의 무작위 부위), "armor:frost:helmet", "book:mending"(마법이 부여된 책, "book:power:3" 처럼 단계), "IRON_INGOT".
     * 몬스터 드롭, 시작 보급, 조합법, 스킬 연출 아이템에서 같이 쓴다.
     */
    public ItemStack spec(String spec, int amount) {
        if (spec == null || spec.isBlank()) return null;
        String s = spec.trim();
        int colon = s.indexOf(':');
        String kind = colon < 0 ? "" : s.substring(0, colon).toLowerCase(Locale.ROOT);
        String val = colon < 0 ? s : s.substring(colon + 1);
        switch (kind) {
            case "item":
                return create(val, amount);
            case "book":
                return book(val, true);
            case "weapon":
                return plugin.weapons().create(val);
            case "armor":
                return plugin.armor().spec(val);
            case "pool": {
                WeaponDef w = val.equals("any") ? plugin.weapons().randomCommon() : plugin.weapons().random(val);
                return w == null ? null : plugin.weapons().create(w);
            }
            case "minecraft":
            case "":
                if (defs.containsKey(val)) return create(val, amount);
                Material m = Material.matchMaterial(val);
                if (m == null || m.isAir()) {
                    plugin.getLogger().warning("알 수 없는 아이템: " + spec);
                    return null;
                }
                return new ItemStack(m, Math.max(1, Math.min(amount, m.getMaxStackSize())));
            default:
                if (defs.containsKey(s)) return create(s, amount);
                plugin.getLogger().warning("알 수 없는 아이템: " + spec);
                return null;
        }
    }

    /**
     * 바닐라 마법이 부여된 책 ("mending", "power:3". 단계를 안 적으면 최고 단계).
     * 커스텀 표시(PDC)를 붙이지 않아야 모루가 보통 책으로 받는다. named 면 보상 알림에 보이도록 마법 이름을 이름에 넣는다.
     */
    public ItemStack book(String spec, boolean named) {
        String[] parts = spec.split(":");
        // 손으로 고친 yml 의 잘못된 이름("silk touch", 한글)에 예외를 던지면 보스 보상이 통째로 끊긴다. 경고만 남기고 건너뛴다
        NamespacedKey key = parts.length == 0 ? null : NamespacedKey.fromString(parts[0].trim().toLowerCase(Locale.ROOT));
        org.bukkit.enchantments.Enchantment ench = key == null ? null : io.papermc.paper.registry.RegistryAccess.registryAccess()
                .getRegistry(io.papermc.paper.registry.RegistryKey.ENCHANTMENT).get(key);
        if (ench == null) {
            plugin.getLogger().warning("알 수 없는 마법: " + spec);
            return null;
        }
        int level = ench.getMaxLevel();
        if (parts.length > 1) {
            try {
                level = Math.max(1, Integer.parseInt(parts[1].trim()));
            } catch (NumberFormatException ignored) {
                // 단계를 못 읽으면 최고 단계
            }
        }
        ItemStack it = new ItemStack(Material.ENCHANTED_BOOK);
        int lv = level;
        it.editMeta(org.bukkit.inventory.meta.EnchantmentStorageMeta.class, m -> {
            m.addStoredEnchant(ench, lv, true);
            if (named) {
                var gray = net.kyori.adventure.text.format.NamedTextColor.GRAY;
                m.displayName(Text.mm("<yellow>마법이 부여된 책 ").append(Component.text("(", gray))
                        .append(ench.displayName(lv).color(gray)).append(Component.text(")", gray)));
            }
        });
        return it;
    }

    public String idOf(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return null;
        return it.getItemMeta().getPersistentDataContainer().get(Keys.ITEM, PersistentDataType.STRING);
    }

    public ItemStack guideBook() {
        ItemStack book = new ItemStack(Material.WRITTEN_BOOK);
        BookMeta meta = (BookMeta) book.getItemMeta();
        meta.title(Component.text("증강 스카이블럭 안내서"));
        meta.author(Component.text("하늘의 제단지기"));
        List<Component> pages = new ArrayList<>();
        for (String page : plugin.getConfig().getStringList("guide-book")) pages.add(Text.mm(page.replace("\\n", "\n")));
        if (pages.isEmpty()) pages.add(Text.mm("<b>증강 스카이블럭</b>\n\n제단을 찾아 증강을 모으세요."));
        meta.pages(pages);
        meta.getPersistentDataContainer().set(Keys.ITEM, PersistentDataType.STRING, "guide_book");
        book.setItemMeta(meta);
        return book;
    }
}
