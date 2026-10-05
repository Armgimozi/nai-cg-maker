package kr.augsky.armor;

import com.destroystokyo.paper.event.player.PlayerArmorChangeEvent;
import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.augment.AugmentDef;
import kr.augsky.util.Fx;
import kr.augsky.util.P;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.EquipmentSlotGroup;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.components.EquippableComponent;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import java.util.logging.Logger;

/**
 * 갑옷 세트 (armor.yml). 투구는 3D 모델을 머리에 씌우고, 나머지는 장비 텍스처(equipment/<세트>)로 입힌다.
 * 같은 세트를 2개/4개 입으면 세트 효과가 증강 수치에 더해진다.
 */
public final class ArmorService implements Listener {
    public enum Slot {
        HELMET("helmet", "투구", EquipmentSlot.HEAD, EquipmentSlotGroup.HEAD, Material.NETHERITE_HELMET),
        CHESTPLATE("chestplate", "갑옷", EquipmentSlot.CHEST, EquipmentSlotGroup.CHEST, Material.NETHERITE_CHESTPLATE),
        LEGGINGS("leggings", "각반", EquipmentSlot.LEGS, EquipmentSlotGroup.LEGS, Material.NETHERITE_LEGGINGS),
        BOOTS("boots", "신발", EquipmentSlot.FEET, EquipmentSlotGroup.FEET, Material.NETHERITE_BOOTS);

        public final String id, korean;
        public final EquipmentSlot slot;
        public final EquipmentSlotGroup group;
        public final Material shell;

        Slot(String id, String korean, EquipmentSlot slot, EquipmentSlotGroup group, Material shell) {
            this.id = id;
            this.korean = korean;
            this.slot = slot;
            this.group = group;
            this.shell = shell;
        }

        public static Slot parse(String s) {
            if (s == null) return null;
            for (Slot sl : values()) if (sl.id.equalsIgnoreCase(s) || sl.korean.equals(s)) return sl;
            return null;
        }
    }

    public record Piece(double armor, double toughness, double knockback) {}

    public record SetDef(String id, String name, String color, String source, Map<Slot, Piece> pieces,
                         Map<Integer, List<AugmentDef.Effect>> bonus, Map<Integer, String> bonusDesc,
                         String aura, P recipe) {
        public String colored(String text) {
            return "<" + color + ">" + text + "</" + color + ">";
        }
    }

    private final AugSky plugin;
    private final Logger log;
    private final Map<String, SetDef> sets = new LinkedHashMap<>();
    private final Set<UUID> pending = new HashSet<>();
    /** 지난번에 입고 있던 세트별 부위 수 (세트 효과가 새로 켜졌는지 알리려고) */
    private final Map<UUID, Map<String, Integer>> lastWorn = new HashMap<>();
    private int tick;

    public ArmorService(AugSky plugin) {
        this.plugin = plugin;
        this.log = plugin.getLogger();
        Bukkit.getScheduler().runTaskTimer(plugin, this::auraTick, 40, 5);
    }

    // ------------------------------------------------------------------ 불러오기

    public void load(YamlConfiguration y) {
        sets.clear();
        for (String id : y.getKeys(false)) {
            ConfigurationSection s = y.getConfigurationSection(id);
            if (s == null) continue;
            P p = new P(toMap(s));
            Map<Slot, Piece> pieces = new LinkedHashMap<>();
            P ps = p.sub("pieces");
            for (Slot sl : Slot.values()) {
                List<Double> v = ps == null ? List.of() : ps.doubles(sl.id);
                pieces.put(sl, new Piece(v.size() > 0 ? v.get(0) : 0, v.size() > 1 ? v.get(1) : 0, v.size() > 2 ? v.get(2) : 0));
            }
            Map<Integer, List<AugmentDef.Effect>> bonus = new LinkedHashMap<>();
            Map<Integer, String> desc = new LinkedHashMap<>();
            P b = p.sub("bonus");
            P bd = p.sub("bonus_desc");
            if (b != null) {
                for (String k : b.m.keySet()) {
                    int n;
                    try {
                        n = Integer.parseInt(k);
                    } catch (NumberFormatException e) {
                        continue;
                    }
                    List<AugmentDef.Effect> effs = new ArrayList<>();
                    for (Map<?, ?> em : b.maps(k)) {
                        P ep = new P(em);
                        effs.add(new AugmentDef.Effect(ep.s("type", ""), ep));
                    }
                    bonus.put(n, effs);
                    desc.put(n, bd == null ? "" : bd.s(k, ""));
                }
            }
            sets.put(id, new SetDef(id, p.s("name", id), p.s("color", "#ffffff"), p.s("source", ""), pieces, bonus, desc,
                    p.s("aura", null), p.sub("recipe")));
        }
        log.info("갑옷 " + sets.size() + "세트 불러옴");
    }

    private static Map<String, Object> toMap(ConfigurationSection s) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (String k : s.getKeys(false)) {
            Object v = s.get(k);
            m.put(k, v instanceof ConfigurationSection cs ? toMap(cs) : v);
        }
        return m;
    }

    public Map<String, SetDef> all() {
        return sets;
    }

    public SetDef get(String id) {
        return id == null ? null : sets.get(id);
    }

    // ------------------------------------------------------------------ 아이템

    public ItemStack create(String setId, Slot slot) {
        SetDef s = get(setId);
        if (s == null || slot == null) return null;
        Piece pc = s.pieces().get(slot);
        ItemStack it = new ItemStack(slot.shell);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(Text.mm("<!i>" + s.colored(s.name() + " " + slot.korean)));
        meta.lore(Text.mm(lore(s, slot)));
        boolean models = plugin.getConfig().getBoolean("resource-pack.custom-models", true);
        if (models) meta.setItemModel(new NamespacedKey(Keys.NS, "armor/" + s.id() + "_" + slot.id));
        EquippableComponent eq = meta.getEquippable();
        eq.setSlot(slot.slot);
        // 투구는 장비 텍스처 대신 3D 아이템 모델을 머리에 씌운다
        if (models && slot != Slot.HELMET) eq.setModel(new NamespacedKey(Keys.NS, s.id()));
        else if (!models) eq.setModel(NamespacedKey.minecraft("netherite"));
        eq.setDispensable(true);
        eq.setSwappable(true);
        eq.setDamageOnHurt(false);
        meta.setEquippable(eq);
        meta.setUnbreakable(true);
        String base = "armor_" + slot.id;
        meta.addAttributeModifier(Attribute.ARMOR, new AttributeModifier(Keys.of(base + "_armor"), pc.armor(),
                AttributeModifier.Operation.ADD_NUMBER, slot.group));
        if (pc.toughness() > 0) meta.addAttributeModifier(Attribute.ARMOR_TOUGHNESS, new AttributeModifier(
                Keys.of(base + "_toughness"), pc.toughness(), AttributeModifier.Operation.ADD_NUMBER, slot.group));
        if (pc.knockback() > 0) meta.addAttributeModifier(Attribute.KNOCKBACK_RESISTANCE, new AttributeModifier(
                Keys.of(base + "_knockback"), pc.knockback(), AttributeModifier.Operation.ADD_NUMBER, slot.group));
        meta.addItemFlags(ItemFlag.HIDE_ATTRIBUTES, ItemFlag.HIDE_UNBREAKABLE, ItemFlag.HIDE_ADDITIONAL_TOOLTIP, ItemFlag.HIDE_ARMOR_TRIM);
        var pdc = meta.getPersistentDataContainer();
        pdc.set(Keys.ARMOR, PersistentDataType.STRING, s.id());
        pdc.set(Keys.ARMOR_SLOT, PersistentDataType.STRING, slot.id);
        it.setItemMeta(meta);
        return it;
    }

    /** "armor:세트" (무작위 부위) 또는 "armor:세트:부위". */
    public ItemStack spec(String val) {
        String[] parts = val.split(":");
        Slot sl = parts.length > 1 ? Slot.parse(parts[1]) : Slot.values()[ThreadLocalRandom.current().nextInt(4)];
        return create(parts[0], sl);
    }

    public List<String> lore(SetDef s, Slot slot) {
        Piece pc = s.pieces().get(slot);
        List<String> l = new ArrayList<>();
        l.add("<gray>" + s.name() + " 세트 <dark_gray>· " + slot.korean);
        String stat = "<white>🛡 방어력 <#9ad8ff>" + Text.num(pc.armor());
        if (pc.toughness() > 0) stat += "   <white>방어 강도 <#9ad8ff>" + Text.num(pc.toughness());
        l.add(stat);
        if (pc.knockback() > 0) l.add("<white>밀치기 저항 <#9ad8ff>" + Text.pct(pc.knockback()));
        for (Map.Entry<Integer, String> en : s.bonusDesc().entrySet()) {
            l.add("");
            l.add("<#ffcc55>[" + en.getKey() + "세트] <gray>" + en.getValue());
        }
        if (!s.source().isEmpty()) {
            l.add("");
            l.add("<#8a8a9a>▸ " + s.source());
        }
        return l;
    }

    public static String setOf(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return null;
        return it.getItemMeta().getPersistentDataContainer().get(Keys.ARMOR, PersistentDataType.STRING);
    }

    public static Slot slotOf(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return null;
        return Slot.parse(it.getItemMeta().getPersistentDataContainer().get(Keys.ARMOR_SLOT, PersistentDataType.STRING));
    }

    // ------------------------------------------------------------------ 세트 효과

    /** 입고 있는 세트별 부위 수. */
    public Map<String, Integer> worn(Player p) {
        Map<String, Integer> n = new HashMap<>();
        for (Slot sl : Slot.values()) {
            ItemStack it = p.getInventory().getItem(sl.slot);
            String s = setOf(it);
            if (s != null && slotOf(it) == sl) n.merge(s, 1, Integer::sum);
        }
        return n;
    }

    /** 세트 효과 (증강 수치에 더해진다). */
    public List<AugmentDef.Effect> bonusEffects(Player p) {
        List<AugmentDef.Effect> out = new ArrayList<>();
        for (Map.Entry<String, Integer> en : worn(p).entrySet()) {
            SetDef s = get(en.getKey());
            if (s == null) continue;
            for (Map.Entry<Integer, List<AugmentDef.Effect>> b : s.bonus().entrySet()) {
                if (en.getValue() >= b.getKey()) out.addAll(b.getValue());
            }
        }
        return out;
    }

    @EventHandler
    public void onArmorChange(PlayerArmorChangeEvent e) {
        Player p = e.getPlayer();
        if (!pending.add(p.getUniqueId())) return;
        Bukkit.getScheduler().runTask(plugin, () -> {
            pending.remove(p.getUniqueId());
            if (!p.isOnline()) return;
            plugin.augments().refresh(p);
            Map<String, Integer> now = worn(p);
            // 이벤트가 올 때는 이미 새 갑옷이 들어가 있으므로, 지난번 기록과 비교한다
            Map<String, Integer> before = lastWorn.getOrDefault(p.getUniqueId(), Map.of());
            lastWorn.put(p.getUniqueId(), now);
            for (Map.Entry<String, Integer> en : now.entrySet()) {
                SetDef s = get(en.getKey());
                if (s == null) continue;
                int was = before.getOrDefault(en.getKey(), 0);
                for (Map.Entry<Integer, String> b : s.bonusDesc().entrySet()) {
                    if (en.getValue() >= b.getKey() && was < b.getKey()) {
                        p.sendActionBar(Text.mm(s.colored("✦ " + s.name() + " " + b.getKey() + "세트") + " <gray>" + b.getValue()));
                        Fx.sound(p.getLocation(), "item.armor.equip_netherite", 1f, 1.3f);
                    }
                }
            }
        });
    }

    @EventHandler
    public void onJoin(org.bukkit.event.player.PlayerJoinEvent e) {
        lastWorn.put(e.getPlayer().getUniqueId(), worn(e.getPlayer()));
    }

    @EventHandler
    public void onQuit(org.bukkit.event.player.PlayerQuitEvent e) {
        lastWorn.remove(e.getPlayer().getUniqueId());
        pending.remove(e.getPlayer().getUniqueId());
    }

    // ------------------------------------------------------------------ 입자

    private void auraTick() {
        tick++;
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.getGameMode() == GameMode.SPECTATOR || p.isInvisible()) continue;
            for (Map.Entry<String, Integer> en : worn(p).entrySet()) {
                if (en.getValue() < 4) continue;
                SetDef s = get(en.getKey());
                if (s == null || s.aura() == null) continue;
                Location at = p.getLocation();
                if (s.aura().equals("PRISM")) {
                    // 발밑에 도는 무지개 고리
                    for (int i = 0; i < 3; i++) {
                        double a = (tick * 0.35) + i * (Math.PI * 2 / 3);
                        float h = (float) ((tick * 0.02 + i / 3.0) % 1.0);
                        java.awt.Color c = java.awt.Color.getHSBColor(h, 0.55f, 1f);
                        at.getWorld().spawnParticle(Particle.DUST, at.clone().add(Math.cos(a) * 0.8, 0.15, Math.sin(a) * 0.8), 1,
                                0, 0, 0, 0, new Particle.DustOptions(Color.fromRGB(c.getRed(), c.getGreen(), c.getBlue()), 1.1f));
                    }
                    continue;
                }
                String[] specs = s.aura().split("\\|");
                for (String spec : specs) {
                    Fx.Spec fx = Fx.parse(spec);
                    if (fx == null) continue;
                    if (fx.particle() == Particle.LAVA && ThreadLocalRandom.current().nextInt(6) != 0) continue;
                    fx.spawn(at.clone().add(0, 1.0, 0), 1, 0.35, 0.55, 0.35, 0.01);
                }
            }
        }
    }

    public List<String> describe(String setId) {
        SetDef s = get(setId);
        List<String> out = new ArrayList<>();
        if (s == null) return out;
        for (Map.Entry<Integer, String> en : s.bonusDesc().entrySet()) out.add("<#ffcc55>[" + en.getKey() + "세트] <gray>" + en.getValue());
        return out;
    }
}
