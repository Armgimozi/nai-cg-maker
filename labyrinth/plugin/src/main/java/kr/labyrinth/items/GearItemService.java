package kr.labyrinth.items;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.Consumable;
import io.papermc.paper.datacomponent.item.Equippable;
import io.papermc.paper.datacomponent.item.ItemAttributeModifiers;
import io.papermc.paper.datacomponent.item.ItemEnchantments;
import io.papermc.paper.datacomponent.item.ItemLore;
import io.papermc.paper.datacomponent.item.TooltipDisplay;
import io.papermc.paper.datacomponent.item.UseCooldown;
import io.papermc.paper.datacomponent.item.consumable.ItemUseAnimation;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemSetDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.event.ItemObtainEvent;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

/**
 * 실제 ItemService (items 담당). 정의 → ItemStack:
 * <ul>
 *   <li>ITEM_MODEL = labyrinth:&lt;id&gt; (CustomModelData 안 씀), 이름 = 희귀도 색, 툴팁 = {@link ItemTooltip}</li>
 *   <li>굴림 스탯 PDC({@code Keys.ITEM_SEED/ITEM_ROLLS/ITEM_VERSION}) — 드롭·제작·보상 순간 굴린다</li>
 *   <li>방어구: EQUIPPABLE(slot) + assetId labyrinth:&lt;set&gt;. <b>투구는 assetId 없이</b> → 3D 아이템 모델이 머리에 렌더링</li>
 *   <li>바닐라 속성 수정치 비움(공격력·공속은 StatService), 활은 BOW + 무한(숨김) + 파괴 불가</li>
 *   <li>물약류: CONSUMABLE(마시기 0.8초) + USE_COOLDOWN(cooldown_group 공유, 클라이언트 쿨다운 표시)</li>
 *   <li>최대 개수: 재료 64 · 소모품 16 · 장비·열쇠 1 (GDD §11.6)</li>
 * </ul>
 */
public final class GearItemService implements ItemService {

    public static final int ITEM_VERSION = 1;
    /** 소모품 중 바닐라 '마시기' 로 처리하는 action. 나머지(return/stat_reset/revive)는 우클릭으로 직접 처리. */
    public static final Set<String> DRINK_ACTIONS = Set.of("heal", "mana", "restore", "cleanse", "buff");

    private final Services services;

    public GearItemService(Services services) { this.services = services; }

    @Override
    public ItemStack create(String id) {
        return create(id, ThreadLocalRandom.current().nextLong());
    }

    @Override
    public ItemStack create(String id, long seed) {
        ItemDef def = services.content().item(id);
        return def == null ? null : build(def, seed, 1);
    }

    @Override
    public ItemStack create(String id, int amount) {
        ItemDef def = services.content().item(id);
        if (def == null) return null;
        return build(def, ThreadLocalRandom.current().nextLong(), def.isGear() ? 1 : amount);
    }

    public static int maxStack(ItemDef def) {
        return switch (def.type()) {
            case MATERIAL -> 64;
            case CONSUMABLE -> 16;
            default -> 1;
        };
    }

    static boolean isBow(ItemDef def) { return def.isWeapon() && "bow".equals(def.weaponType()); }

    /** 정의 → 아이템. 장비면 seed 로 스탯을 굴린다. */
    public ItemStack build(ItemDef def, long seed, int amount) {
        int max = maxStack(def);
        ItemStack s = ItemStack.of(isBow(def) ? Material.BOW : Material.PAPER, Math.max(1, Math.min(max, amount)));
        s.setData(DataComponentTypes.MAX_STACK_SIZE, max);
        s.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, def.id()));
        s.setData(DataComponentTypes.ITEM_NAME, Text.item("<" + def.rarity().color() + ">" + def.name()));

        Map<String, Double> rolls = def.isGear() ? ItemRolls.roll(def, seed) : null;
        List<String> lore = ItemTooltip.lines(services.content(), def, rolls);
        s.setData(DataComponentTypes.LORE, ItemLore.lore(Text.itemLines(lore)));

        TooltipDisplay.Builder tip = TooltipDisplay.tooltipDisplay();
        if (def.isGear()) {
            s.setData(DataComponentTypes.ATTRIBUTE_MODIFIERS, ItemAttributeModifiers.itemAttributes().build());
            tip.addHiddenComponents(DataComponentTypes.ATTRIBUTE_MODIFIERS);
        }
        if (isBow(def)) {
            s.setData(DataComponentTypes.UNBREAKABLE);
            s.setData(DataComponentTypes.ENCHANTMENTS, ItemEnchantments.itemEnchantments(Map.of(Enchantment.INFINITY, 1)));
            s.setData(DataComponentTypes.ENCHANTMENT_GLINT_OVERRIDE, false);
            tip.addHiddenComponents(DataComponentTypes.ENCHANTMENTS, DataComponentTypes.UNBREAKABLE);
        }
        if (def.type() == ItemType.ARMOR) applyEquippable(s, def);
        if (def.type() == ItemType.CONSUMABLE) applyConsumable(s, def);
        s.setData(DataComponentTypes.TOOLTIP_DISPLAY, tip.build());

        s.editPersistentDataContainer(pdc -> {
            pdc.set(Keys.ITEM_ID, PersistentDataType.STRING, def.id());
            if (rolls != null) {
                pdc.set(Keys.ITEM_SEED, PersistentDataType.LONG, seed);
                pdc.set(Keys.ITEM_ROLLS, PersistentDataType.STRING, ItemRolls.encode(rolls));
                pdc.set(Keys.ITEM_VERSION, PersistentDataType.INTEGER, ITEM_VERSION);
            }
        });
        return s;
    }

    private void applyEquippable(ItemStack s, ItemDef def) {
        EquipmentSlot slot = switch (def.armorSlot() == null ? "" : def.armorSlot()) {
            case "head" -> EquipmentSlot.HEAD;
            case "chest" -> EquipmentSlot.CHEST;
            case "legs" -> EquipmentSlot.LEGS;
            case "feet" -> EquipmentSlot.FEET;
            default -> null; // 방패(offhand)는 보조손에 직접 놓는다
        };
        if (slot == null) return;
        ItemSetDef set = def.setBonus() == null ? null : services.content().sets().get(def.setBonus());
        String look = set == null ? "light" : set.look();
        String sound = switch (look) {
            case "heavy" -> "item.armor.equip_iron";
            case "cloth" -> "item.armor.equip_generic";
            default -> "item.armor.equip_leather";
        };
        Equippable.Builder eb = Equippable.equippable(slot)
                .equipSound(Key.key("minecraft", sound))
                .damageOnHurt(false)
                .dispensable(false);
        // 투구: assetId 를 넣지 않아야 3D 아이템 모델이 머리에 그대로 렌더링된다 (ARCHITECTURE §2)
        if (slot != EquipmentSlot.HEAD && def.armorSet() != null && !def.armorSet().isBlank()) {
            eb.assetId(Key.key(Keys.NS, def.armorSet()));
        }
        s.setData(DataComponentTypes.EQUIPPABLE, eb.build());
    }

    private void applyConsumable(ItemStack s, ItemDef def) {
        Params use = def.use();
        if (use == null || use.isEmpty()) return;
        String action = use.str("action", "");
        double cd = use.dbl("cooldown", 0);
        String group = use.str("cooldown_group", def.id());
        if (DRINK_ACTIONS.contains(action)) {
            s.setData(DataComponentTypes.CONSUMABLE, Consumable.consumable()
                    .consumeSeconds(0.8f)
                    .animation(ItemUseAnimation.DRINK)
                    .sound(Key.key("minecraft", "entity.generic.drink"))
                    .hasConsumeParticles(false)
                    .build());
        }
        if (cd > 0) {
            s.setData(DataComponentTypes.USE_COOLDOWN, UseCooldown.useCooldown((float) cd)
                    .cooldownGroup(cooldownGroupKey(group)).build());
        }
    }

    /** 소모품 쿨다운 그룹 키 (클라이언트 쿨다운 표시 공유). */
    public static Key cooldownGroupKey(String group) {
        return Key.key(Keys.NS, "cd_" + group.toLowerCase(java.util.Locale.ROOT).replaceAll("[^a-z0-9_./-]", "_"));
    }

    @Override
    public Optional<ItemDef> defOf(ItemStack stack) {
        if (stack == null || stack.isEmpty()) return Optional.empty();
        String id = stack.getPersistentDataContainer().get(Keys.ITEM_ID, PersistentDataType.STRING);
        return Optional.ofNullable(services.content().item(id));
    }

    @Override
    public Map<String, Double> rolledStats(ItemStack stack) {
        Optional<ItemDef> def = defOf(stack);
        if (def.isEmpty() || !def.get().isGear()) return Map.of();
        var pdc = stack.getPersistentDataContainer();
        String enc = pdc.get(Keys.ITEM_ROLLS, PersistentDataType.STRING);
        if (enc != null) {
            Map<String, Double> m = ItemRolls.decode(enc);
            if (!m.isEmpty()) return m;
        }
        Long seed = pdc.get(Keys.ITEM_SEED, PersistentDataType.LONG);
        return seed != null ? ItemRolls.roll(def.get(), seed) : ItemRolls.midpoint(def.get());
    }

    @Override
    public int give(Player player, String id, int amount, String source) {
        ItemDef def = services.content().item(id);
        if (def == null || amount <= 0 || player == null) return 0;
        int given = 0;
        int max = maxStack(def);
        while (given < amount) {
            int n = def.isGear() ? 1 : Math.min(max, amount - given);
            ItemStack s = create(id, n);
            if (s == null) break;
            deliver(player, s);
            Bukkit.getPluginManager().callEvent(new ItemObtainEvent(player, def, s, source));
            given += n;
        }
        return given;
    }

    /** 인벤토리에 넣고, 넘치면 발밑에 주인만 줍게 떨군다. */
    public static void deliver(Player player, ItemStack s) {
        player.getInventory().addItem(s).values().forEach(left -> player.getWorld().dropItem(player.getLocation(), left, it -> {
            it.setOwner(player.getUniqueId());
            it.setPickupDelay(10);
        }));
    }
}
