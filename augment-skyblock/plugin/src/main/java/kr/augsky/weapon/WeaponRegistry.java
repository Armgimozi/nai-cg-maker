package kr.augsky.weapon;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.skill.HitEffects;
import kr.augsky.skill.SkillDef;
import kr.augsky.util.P;
import kr.augsky.util.Text;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.EquipmentSlotGroup;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.components.UseCooldownComponent;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

public final class WeaponRegistry {
    /** 아이템을 만들 때 쓴 설명·수치의 지문. 지금 정의와 다르면 refresh 가 다시 쓴다. */
    private static final NamespacedKey SIG = Keys.of("weapon_sig");
    private static final List<Attribute> STAT_ATTRS = List.of(Attribute.ATTACK_DAMAGE, Attribute.ATTACK_SPEED, Attribute.ENTITY_INTERACTION_RANGE);

    private final AugSky plugin;
    private final Map<String, WeaponDef> weapons = new LinkedHashMap<>();
    private final Map<String, Integer> sigs = new HashMap<>();

    public WeaponRegistry(AugSky plugin) {
        this.plugin = plugin;
    }

    public void load(YamlConfiguration yml) {
        weapons.clear();
        sigs.clear();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            P p = P.of(sec);
            // 활은 바닐라 활을 껍데기로 써야 당겨 쏠 수 있다
            Material mat = Material.matchMaterial(p.s("material", "bow".equals(p.s("type", "")) ? "BOW" : "NETHERITE_SWORD"));
            if (mat == null) mat = Material.NETHERITE_SWORD;
            P passive = p.sub("passive");
            String type = p.s("type", "sword");
            String skill3 = p.s("skill3", null);
            // 활은 우클릭이 활시위라 조작이 두 개뿐이다
            if (skill3 != null && "bow".equals(type)) {
                plugin.getLogger().warning("무기 " + id + " 는 활이라 skill3 을 쓸 수 없어 무시합니다");
                skill3 = null;
            }
            WeaponDef def = new WeaponDef(
                    id,
                    p.s("name", id),
                    p.s("pool", "basic"),
                    p.s("source", null),
                    type,
                    p.s("element", "iron"),
                    p.d("damage", 6),
                    p.d("speed", 1.6),
                    p.d("reach", 0),
                    p.d("skill_power", 1.0),
                    mat,
                    p.s("skill", null),
                    p.s("skill2", null),
                    skill3,
                    passive == null ? 0 : passive.d("chance", 0.2),
                    passive == null ? null : passive.s("description", null),
                    passive == null ? List.of() : HitEffects.parseList(passive.maps("effects")),
                    p.strings("lore"),
                    p.sub("recipe"),
                    p.b("droppable", true)
            );
            for (int slot = 1; slot <= 3; slot++) {
                String sid = def.skillOf(slot);
                if (sid != null && plugin.skills().get(sid) == null)
                    plugin.getLogger().warning("무기 " + id + " 의 스킬 " + sid + " 이 skills.yml 에 없습니다");
            }
            weapons.put(id, def);
        }
        plugin.getLogger().info("무기 " + weapons.size() + "종 불러옴");
    }

    public WeaponDef get(String id) {
        return id == null ? null : weapons.get(id);
    }

    public Map<String, WeaponDef> all() {
        return weapons;
    }

    public WeaponDef of(ItemStack it) {
        if (it == null || !it.hasItemMeta()) return null;
        String id = it.getItemMeta().getPersistentDataContainer().get(Keys.WEAPON, PersistentDataType.STRING);
        return get(id);
    }

    /** 같은 pool(얻는 곳) 의 무기 중 하나. */
    public WeaponDef random(String pool) {
        List<WeaponDef> list = new ArrayList<>();
        for (WeaponDef w : weapons.values()) if (w.pool().equals(pool) && w.droppable()) list.add(w);
        if (list.isEmpty()) return null;
        return list.get(ThreadLocalRandom.current().nextInt(list.size()));
    }

    /** 보스/프리즘 무기를 뺀 아무 무기 하나 ('보물 사냥꾼' 증강 등). */
    public WeaponDef randomCommon() {
        List<WeaponDef> list = new ArrayList<>();
        for (WeaponDef w : weapons.values()) {
            if (!w.droppable() || w.pool().equals("boss") || w.pool().equals("prism")) continue;
            list.add(w);
        }
        if (list.isEmpty()) return null;
        return list.get(ThreadLocalRandom.current().nextInt(list.size()));
    }

    public String displayName(WeaponDef w) {
        return Element.wrap(w.element(), w.name());
    }

    public ItemStack create(String id) {
        WeaponDef w = get(id);
        return w == null ? null : create(w);
    }

    public ItemStack create(WeaponDef w) {
        ItemStack it = new ItemStack(w.material());
        ItemMeta meta = it.getItemMeta();
        meta.displayName(Text.mm(displayName(w)));
        meta.lore(Text.mm(lore(w)));
        if (plugin.getConfig().getBoolean("resource-pack.custom-models", true)) {
            meta.setItemModel(new NamespacedKey(Keys.NS, w.id()));
        }
        meta.setUnbreakable(true);
        if (w.isBow()) {
            // 화살 하나만 있으면 줄지 않게 (무한). 반짝임은 모델을 가리므로 끈다
            meta.addEnchant(org.bukkit.enchantments.Enchantment.INFINITY, 1, true);
            meta.setEnchantmentGlintOverride(false);
            meta.addItemFlags(ItemFlag.HIDE_ENCHANTS);
        }
        addStats(meta, w);
        UseCooldownComponent uc = meta.getUseCooldown();
        uc.setCooldownSeconds(0.05f);
        uc.setCooldownGroup(Keys.of("w_" + w.id()));
        meta.setUseCooldown(uc);
        meta.addItemFlags(ItemFlag.HIDE_ATTRIBUTES, ItemFlag.HIDE_UNBREAKABLE, ItemFlag.HIDE_ADDITIONAL_TOOLTIP);
        meta.getPersistentDataContainer().set(Keys.WEAPON, PersistentDataType.STRING, w.id());
        meta.getPersistentDataContainer().set(SIG, PersistentDataType.INTEGER, sig(w));
        it.setItemMeta(meta);
        return it;
    }

    /**
     * 이미 만들어진 무기 아이템의 설명과 공격력·속도·거리를 지금 정의로 다시 쓴다.
     * 둘 다 만들 때 아이템에 박히므로, 판이 바뀌거나 리로드한 뒤에도 옛 조작법·옛 스킬·옛 공격력이 남기 때문이다.
     * 이름(모루로 바꿨을 수 있다)·마법 부여·태그는 그대로 둔다. 다시 썼으면 true.
     */
    public boolean refresh(ItemStack it) {
        if (it == null || it.isEmpty() || !it.hasItemMeta()) return false;
        ItemMeta meta = it.getItemMeta();
        var pdc = meta.getPersistentDataContainer();
        WeaponDef w = get(pdc.get(Keys.WEAPON, PersistentDataType.STRING));
        if (w == null) return false;
        int sig = sig(w);
        Integer had = pdc.get(SIG, PersistentDataType.INTEGER);
        if (had != null && had == sig) return false;
        meta.lore(Text.mm(lore(w)));
        // 우리 키의 수식어만 빼고 다시 단다 (다른 수식어는 건드리지 않는다)
        for (Attribute a : STAT_ATTRS) {
            var mods = meta.getAttributeModifiers(a);
            if (mods == null) continue;
            for (AttributeModifier m : List.copyOf(mods)) {
                String k = m.getKey().getKey();
                if (m.getKey().getNamespace().equals(Keys.NS) && (k.equals("weapon_damage") || k.equals("weapon_speed") || k.equals("weapon_reach")))
                    meta.removeAttributeModifier(a, m);
            }
        }
        addStats(meta, w);
        pdc.set(SIG, PersistentDataType.INTEGER, sig);
        it.setItemMeta(meta);
        return true;
    }

    private void addStats(ItemMeta meta, WeaponDef w) {
        meta.addAttributeModifier(Attribute.ATTACK_DAMAGE, new AttributeModifier(
                Keys.of("weapon_damage"), w.isBow() ? 1 : w.damage() - 1, AttributeModifier.Operation.ADD_NUMBER, EquipmentSlotGroup.MAINHAND));
        meta.addAttributeModifier(Attribute.ATTACK_SPEED, new AttributeModifier(
                Keys.of("weapon_speed"), w.speed() - 4, AttributeModifier.Operation.ADD_NUMBER, EquipmentSlotGroup.MAINHAND));
        if (w.reach() != 0) {
            meta.addAttributeModifier(Attribute.ENTITY_INTERACTION_RANGE, new AttributeModifier(
                    Keys.of("weapon_reach"), w.reach(), AttributeModifier.Operation.ADD_NUMBER, EquipmentSlotGroup.MAINHAND));
        }
    }

    /** 설명(스킬 이름·조작·패시브 포함)과 수치의 지문. 리로드 때 스킬을 무기보다 먼저 불러오므로 무기를 불러올 때만 비우면 된다. */
    private int sig(WeaponDef w) {
        return sigs.computeIfAbsent(w.id(), k -> (String.join("\n", lore(w)) + "|" + w.isBow() + "|" + w.damage() + "|" + w.speed() + "|" + w.reach()).hashCode());
    }

    public List<String> lore(WeaponDef w) {
        List<String> l = new ArrayList<>();
        l.add("<gray>" + WeaponDef.typeName(w.type()) + " <dark_gray>· " + Element.wrap(w.element(), Element.korean(w.element())));
        if (w.isBow()) {
            l.add("<white>🏹 화살 피해 <#ff6b6b>" + Text.num(w.damage()) + " <dark_gray>(끝까지 당겼을 때)");
            l.add("<dark_gray>화살 1개만 있으면 줄지 않는다");
        } else {
            l.add("<white>⚔ 공격력 <#ff6b6b>" + Text.num(w.damage()) + "</#ff6b6b>   <white>⚡ 공격 속도 <#ffd84d>" + Text.num(w.speed()));
        }
        if (w.reach() != 0) l.add("<white>➶ 공격 거리 <#7cd4ff>+" + Text.num(w.reach()));
        if (w.skillPower() != 1.0) l.add("<white>✧ 스킬 위력 <#c9a0ff>×" + Text.num(w.skillPower()));
        for (int slot = 1; slot <= 3; slot++) addSkill(l, w.inputLabel(slot), w.skillOf(slot));
        if (w.passiveDesc() != null) {
            l.add("");
            l.add("<#7cffc4>[패시브] <gray>" + w.passiveDesc());
        }
        if (!w.lore().isEmpty()) {
            l.add("");
            for (String s : w.lore()) l.add("<dark_gray><i>" + s);
        }
        String src = w.source() != null ? w.source() : Element.poolSource(w.pool());
        if (!src.isEmpty()) {
            l.add("");
            l.add("<#8a8a9a>▸ " + src);
        }
        return l;
    }

    private void addSkill(List<String> l, String label, String skillId) {
        if (label == null || skillId == null) return;
        SkillDef s = plugin.skills().get(skillId);
        if (s == null) return;
        l.add("");
        l.add("<#ffcc55>[" + label + "] <white>" + s.name() + " <dark_gray>(재사용 " + Text.num(s.cooldown()) + "초)");
        for (String d : s.description()) l.add("  <gray>" + d);
    }
}
