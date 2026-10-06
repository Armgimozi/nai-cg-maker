package kr.augsky.weapon;

import kr.augsky.AugSky;
import kr.augsky.Keys;
import kr.augsky.item.Gear;
import kr.augsky.skill.HitEffects;
import kr.augsky.skill.SkillDef;
import kr.augsky.util.P;
import kr.augsky.util.Text;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Tag;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.inventory.EquipmentSlotGroup;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.components.ToolComponent;
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
    private static final List<Attribute> STAT_ATTRS = List.of(Attribute.ATTACK_DAMAGE, Attribute.ATTACK_SPEED, Attribute.ENTITY_INTERACTION_RANGE,
            Attribute.BLOCK_BREAK_SPEED);
    /** 성급함 한 단계가 채굴 속도에 곱하는 몫 (바닐라 성급함: 단계마다 ×(1 + 0.2)). */
    private static final double HASTE_STEP = 0.2;

    private final AugSky plugin;
    private final Map<String, WeaponDef> weapons = new LinkedHashMap<>();
    private final Map<String, Integer> sigs = new HashMap<>();
    private final Map<String, Gear.Repair> repairs = new HashMap<>();

    public WeaponRegistry(AugSky plugin) {
        this.plugin = plugin;
    }

    public void load(YamlConfiguration yml) {
        weapons.clear();
        sigs.clear();
        repairs.clear();
        for (String id : yml.getKeys(false)) {
            ConfigurationSection sec = yml.getConfigurationSection(id);
            if (sec == null) continue;
            P p = P.of(sec);
            String type = p.s("type", "sword");
            P mining = p.sub("mining");
            String tier = mining == null ? "iron" : mining.s("tier", "iron").toLowerCase(java.util.Locale.ROOT);
            if (tierTag(tier) == null) {
                plugin.getLogger().warning("곡괭이 " + id + " 의 채굴 등급 " + tier + " 을 알 수 없어 iron 으로 씁니다");
                tier = "iron";
            }
            // 활은 바닐라 활을 껍데기로 써야 당겨 쏠 수 있다. 곡괭이는 등급에 맞는 바닐라 곡괭이
            // (리소스팩을 꺼도 모양과 마법 부여가 등급에 맞는다)
            String shell = switch (type) {
                case "bow" -> "BOW";
                case "pickaxe" -> switch (tier) {
                    case "wood", "wooden" -> "WOODEN_PICKAXE";
                    case "gold", "golden" -> "GOLDEN_PICKAXE";
                    default -> tier.toUpperCase(java.util.Locale.ROOT) + "_PICKAXE";
                };
                default -> "NETHERITE_SWORD";
            };
            Material mat = Material.matchMaterial(p.s("material", shell));
            if (mat == null) mat = Material.NETHERITE_SWORD;
            P passive = p.sub("passive");
            P perks = p.sub("perks");
            String pool = p.s("pool", "basic");
            String element = p.s("element", "iron");
            double speed = p.d("speed", "pickaxe".equals(type) ? 1.2 : 1.6);
            String skill3 = p.s("skill3", null);
            // 활은 우클릭이 활시위라 조작이 두 개뿐이다
            if (skill3 != null && "bow".equals(type)) {
                plugin.getLogger().warning("무기 " + id + " 는 활이라 skill3 을 쓸 수 없어 무시합니다");
                skill3 = null;
            }
            WeaponDef def = new WeaponDef(
                    id,
                    p.s("name", id),
                    pool,
                    p.s("source", null),
                    type,
                    element,
                    p.d("damage", 6),
                    speed,
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
                    p.b("droppable", true),
                    tier,
                    mining == null ? 1 : mining.d("speed", 6),
                    Gear.weaponDurability(pool, type, speed, p.i("durability", 0)),
                    Gear.weaponRepair(pool, element, p.s("repair", null)),
                    perks != null && perks.b("auto_smelt", false),
                    perks == null ? 0 : Math.max(0, perks.i("haste", 0))
            );
            Gear.Repair rep = Gear.Repair.parse(def.repair());
            if (rep == null || (rep.item() != null && plugin.items().def(rep.item()) == null))
                plugin.getLogger().warning("무기 " + id + " 의 수리 재료 " + def.repair() + " 를 알 수 없습니다 (모루에서 같은 무기로만 고칠 수 있다)");
            repairs.put(id, rep);
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
        gear(meta, w);
        addStats(meta, w);
        UseCooldownComponent uc = meta.getUseCooldown();
        uc.setCooldownSeconds(0.05f);
        uc.setCooldownGroup(Keys.of("w_" + w.id()));
        meta.setUseCooldown(uc);
        meta.addItemFlags(ItemFlag.HIDE_ATTRIBUTES, ItemFlag.HIDE_ADDITIONAL_TOOLTIP);
        meta.getPersistentDataContainer().set(Keys.WEAPON, PersistentDataType.STRING, w.id());
        meta.getPersistentDataContainer().set(SIG, PersistentDataType.INTEGER, sig(w));
        it.setItemMeta(meta);
        Gear.applyRepairable(it, repair(w), plugin.items());
        return it;
    }

    /**
     * 내구도, 반짝임, 곡괭이 채굴 규칙. 만들 때와 다시 쓸 때 같이 쓴다.
     * 예전 형식(부서지지 않음)이었으면 활에 숨겨 붙였던 무한과 마법 숨김도 걷어 낸다. 예전 형식이었으면 true.
     */
    private boolean gear(ItemMeta meta, WeaponDef w) {
        boolean old = Gear.applyDurability(meta, w.durability());
        if (old) {
            // 예전 활은 화살이 줄지 않게 무한 I 을 숨겨 붙였다. 수선과 같이 못 쓰고 마법 부여대도 막으므로 뗀다
            if (w.isBow() && meta.getEnchantLevel(Enchantment.INFINITY) == 1) meta.removeEnchant(Enchantment.INFINITY);
            meta.removeItemFlags(ItemFlag.HIDE_ENCHANTS);
        }
        // 반짝임이 3D 모델을 가리므로 마법을 붙여도 반짝이지 않게 한다 (마법은 설명에 보인다)
        meta.setEnchantmentGlintOverride(false);
        if (w.isPickaxe()) {
            meta.setTool(tool(meta, w));
            // 철·다이아몬드 곡괭이 껍데기는 용암에 타 버린다. 다른 근접 무기·갑옷(네더라이트 껍데기)처럼 불에 타지 않게
            meta.setDamageResistant(org.bukkit.tag.DamageTypeTags.IS_FIRE);
        }
        return old;
    }

    /** 곡괭이 채굴 규칙: 등급보다 높은 블록은 캐도 안 떨어지고, 곡괭이 블록은 정한 속도로 캔다 (바닐라 곡괭이와 같은 순서). */
    private static ToolComponent tool(ItemMeta meta, WeaponDef w) {
        ToolComponent t = meta.getTool();
        t.setRules(new ArrayList<>());
        t.setDefaultMiningSpeed(1f);
        t.setDamagePerBlock(1);
        t.addRule(tierTag(w.miningTier()), null, false);
        t.addRule(Tag.MINEABLE_PICKAXE, (float) w.miningSpeed(), true);
        return t;
    }

    private static Tag<Material> tierTag(String tier) {
        return switch (tier) {
            case "wood", "wooden" -> Tag.INCORRECT_FOR_WOODEN_TOOL;
            case "stone" -> Tag.INCORRECT_FOR_STONE_TOOL;
            case "iron" -> Tag.INCORRECT_FOR_IRON_TOOL;
            case "gold", "golden" -> Tag.INCORRECT_FOR_GOLD_TOOL;
            case "diamond" -> Tag.INCORRECT_FOR_DIAMOND_TOOL;
            case "netherite" -> Tag.INCORRECT_FOR_NETHERITE_TOOL;
            default -> null;
        };
    }

    private static String tierName(String tier) {
        return switch (tier) {
            case "wood", "wooden" -> "나무";
            case "stone" -> "돌";
            case "iron" -> "철";
            case "gold", "golden" -> "금";
            case "diamond" -> "다이아몬드";
            case "netherite" -> "네더라이트";
            default -> tier;
        };
    }

    public Gear.Repair repair(WeaponDef w) {
        return repairs.get(w.id());
    }

    /**
     * 이미 만들어진 무기 아이템의 설명과 공격력·속도·거리, 최대 내구도·수리 재료를 지금 정의로 다시 쓴다.
     * 둘 다 만들 때 아이템에 박히므로, 판이 바뀌거나 리로드한 뒤에도 옛 조작법·옛 스킬·옛 공격력이 남기 때문이다.
     * 부서지지 않던 예전 무기는 내구도가 꽉 찬 채로 바뀐다.
     * 이름(모루로 바꿨을 수 있다)·마법 부여·태그·닳은 정도는 그대로 둔다. 다시 썼으면 true.
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
        gear(meta, w);
        // 우리 키의 수식어만 빼고 다시 단다 (다른 수식어는 건드리지 않는다)
        for (Attribute a : STAT_ATTRS) {
            var mods = meta.getAttributeModifiers(a);
            if (mods == null) continue;
            for (AttributeModifier m : List.copyOf(mods)) {
                String k = m.getKey().getKey();
                if (m.getKey().getNamespace().equals(Keys.NS)
                        && (k.equals("weapon_damage") || k.equals("weapon_speed") || k.equals("weapon_reach") || k.equals("weapon_haste")))
                    meta.removeAttributeModifier(a, m);
            }
        }
        addStats(meta, w);
        pdc.set(SIG, PersistentDataType.INTEGER, sig);
        it.setItemMeta(meta);
        Gear.applyRepairable(it, repair(w), plugin.items());
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
        // 곡괭이 성급함: 바닐라 성급함 N 은 채굴 속도에 ×(1 + 0.2N) 을 따로 곱한다. 같은 몫을 따로 곱하는 수식어(MULTIPLY_SCALAR_1)로 달아서
        // 효과 칸에 안 보이고, 손을 바꾸면 바로 풀리고, 증강의 성급함·채굴 속도와는 서로 곱해진다
        if (w.haste() > 0) {
            meta.addAttributeModifier(Attribute.BLOCK_BREAK_SPEED, new AttributeModifier(
                    Keys.of("weapon_haste"), HASTE_STEP * w.haste(), AttributeModifier.Operation.MULTIPLY_SCALAR_1, EquipmentSlotGroup.MAINHAND));
        }
    }

    /** 설명(스킬 이름·조작·패시브 포함)과 수치의 지문. 리로드 때 스킬을 무기보다 먼저 불러오므로 무기를 불러올 때만 비우면 된다. */
    private int sig(WeaponDef w) {
        return sigs.computeIfAbsent(w.id(), k -> (String.join("\n", lore(w)) + "|" + w.isBow() + "|" + w.damage() + "|" + w.speed() + "|" + w.reach()
                + "|g" + Gear.FORMAT + "|" + w.durability() + "|" + w.repair() + "|" + w.miningTier() + "|" + w.miningSpeed()
                + "|" + w.autoSmelt() + "|" + w.haste() + "|" + w.infiniteArrows()).hashCode());
    }

    public List<String> lore(WeaponDef w) {
        List<String> l = new ArrayList<>();
        l.add("<gray>" + WeaponDef.typeName(w.type()) + " <dark_gray>· " + Element.wrap(w.element(), Element.korean(w.element())));
        if (w.isBow()) {
            l.add("<white>🏹 화살 피해 <#ff6b6b>" + Text.num(w.damage()) + " <dark_gray>(끝까지 당겼을 때)");
            if (w.infiniteArrows()) l.add("<dark_gray>화살 1개만 있으면 줄지 않는다");
        } else {
            if (w.isPickaxe()) l.add("<white>⛏ 채굴 등급 <#9ad8ff>" + tierName(w.miningTier())
                    + " <dark_gray>· <white>채굴 속도 <#ffd84d>" + Text.num(w.miningSpeed()));
            l.add("<white>⚔ 공격력 <#ff6b6b>" + Text.num(w.damage()) + "</#ff6b6b>   <white>⚡ 공격 속도 <#ffd84d>" + Text.num(w.speed()));
        }
        if (w.reach() != 0) l.add("<white>➶ 공격 거리 <#7cd4ff>+" + Text.num(w.reach()));
        if (w.skillPower() != 1.0) l.add("<white>✧ 스킬 위력 <#c9a0ff>×" + Text.num(w.skillPower()));
        l.add(Gear.loreLine(w.durability(), repair(w), plugin.items()));
        for (int slot = 1; slot <= 3; slot++) addSkill(l, w.inputLabel(slot), w.skillOf(slot));
        if (w.passiveDesc() != null) {
            l.add("");
            l.add("<#7cffc4>[패시브] <gray>" + w.passiveDesc());
        }
        if (w.autoSmelt() || w.haste() > 0) l.add("");
        if (w.autoSmelt())
            l.add("<#7cffc4>[패시브] <gray>캐낸 광석이 곧바로 제련된다 <dark_gray>(제련 증강이 있으면 경험치 두 배)");
        if (w.haste() > 0)
            l.add("<#7cffc4>[패시브] <gray>들고 있는 동안 채굴 속도 +" + Math.round(HASTE_STEP * 100 * w.haste()) + "% <dark_gray>(성급함 "
                    + roman(w.haste()) + "만큼, 성급함 증강과 겹친다)");
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

    private static String roman(int n) {
        return switch (n) {
            case 1 -> "I";
            case 2 -> "II";
            case 3 -> "III";
            case 4 -> "IV";
            default -> Integer.toString(n);
        };
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
