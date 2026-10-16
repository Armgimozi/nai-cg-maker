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
import kr.labyrinth.items.enhance.EnhanceRules;
import kr.labyrinth.items.enhance.Enhancement;
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
 *   <li>강화 단계 PDC({@code Keys.ITEM_ENHANCE}, {@link Enhancement}) — 이름 "+7"·툴팁·광택은 {@link #render}, 스탯 배율은 {@link #rolledStats}</li>
 *   <li>방어구: EQUIPPABLE(slot) + assetId labyrinth:&lt;set&gt;. <b>투구는 assetId 없이</b> → 3D 아이템 모델이 머리에 렌더링</li>
 *   <li>바닐라 속성 수정치 비움(공격력·공속은 StatService), 활은 BOW + 무한(숨김) + 파괴 불가</li>
 *   <li>물약류: CONSUMABLE(마시기 0.8초) + USE_COOLDOWN(cooldown_group 공유, 클라이언트 쿨다운 표시)</li>
 *   <li>최대 개수: 재료 64 · 소모품 16 · 장비·열쇠 1 (GDD §11.6)</li>
 * </ul>
 */
public final class GearItemService implements ItemService {

    /** 아이템 데이터 버전: 1 = 굴림, 2 = 강화 단계(Keys.ITEM_ENHANCE) 추가. 1 이하 아이템은 강화 0 으로 읽는다. */
    public static final int ITEM_VERSION = Enhancement.ITEM_VERSION;
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
            case CONSUMABLE, BLUEPRINT -> 16;
            default -> 1;
        };
    }

    /** 활 = 공격 방식이 원거리인 무기 (바닐라 BOW 로 만들어 당겨 쏜다). */
    static boolean isBow(ItemDef def) { return def.isWeapon() && kr.labyrinth.combat.WeaponAttack.of(def).ranged(); }

    /** 정의 → 아이템. 장비면 seed 로 스탯을 굴린다. */
    public ItemStack build(ItemDef def, long seed, int amount) {
        int max = maxStack(def);
        ItemStack s = ItemStack.of(isBow(def) ? Material.BOW : Material.PAPER, Math.max(1, Math.min(max, amount)));
        s.setData(DataComponentTypes.MAX_STACK_SIZE, max);
        s.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, def.id()));
        // 등급별 툴팁 테두리 (리소스팩 labyrinth:tooltip/<등급>_background·_frame)
        s.setData(DataComponentTypes.TOOLTIP_STYLE, Key.key(Keys.NS, def.rarity().id()));

        Map<String, Double> rolls = def.isGear() ? ItemRolls.roll(def, seed) : null;

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
                pdc.set(Keys.ITEM_COMBAT_VER, PersistentDataType.INTEGER, ItemMigration035.VERSION);
            }
        });
        render(s, def);
        return s;
    }

    /**
     * 이름·툴팁·광택을 PDC(굴림값·강화 단계)에서 다시 그린다 — 생성 직후, 강화 직후, 설정이 바뀐 뒤 강화 창에서 고를 때.
     * 이름 = 강화 접두어("+7 ") + 희귀도 색(+7 부터 금빛 그라데이션), +7 부터 인챈트 광택.
     */
    public void render(ItemStack s, ItemDef def) {
        if (def.type().isBlueprint()) { // 0.3.6 Q6: 도안 이름·설명은 PDC 의 레시피에서 (items/blueprint)
            kr.labyrinth.items.blueprint.BlueprintItems.render(s, services.content());
            return;
        }
        int lv = def.isGear() ? Enhancement.level(s) : 0;
        EnhanceRules er = Enhancement.rules();
        boolean enh = lv > 0 && EnhanceRules.enhanceable(def);
        if (enh) {
            String[] col = er.nameColor(def.rarity(), lv);
            s.setData(DataComponentTypes.ITEM_NAME, Text.item(er.namePrefix(lv) + col[0] + def.name() + col[1]));
        } else {
            s.setData(DataComponentTypes.ITEM_NAME, Text.item("<" + def.rarity().color() + ">" + def.name()));
        }
        Map<String, Double> base = def.isGear() ? baseRolls(s, def) : null;
        Map<String, Double> bonus = enh ? er.bonus(def, base, lv) : Map.of();
        List<String> enhLines = def.isGear() ? Enhancement.tooltip(services.content(), def, lv) : List.of();
        List<String> lore = ItemTooltip.lines(services.content(), def, base, bonus, enhLines);
        s.setData(DataComponentTypes.LORE, ItemLore.lore(Text.itemLines(lore)));
        if (enh && er.shines(lv)) s.setData(DataComponentTypes.ENCHANTMENT_GLINT_OVERRIDE, true);
        else if (isBow(def)) s.setData(DataComponentTypes.ENCHANTMENT_GLINT_OVERRIDE, false);
        else s.resetData(DataComponentTypes.ENCHANTMENT_GLINT_OVERRIDE);
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
        // 장착 소리 = 그 부위의 겉모습 (세트 없는 투구·평상복도 — 평상복은 세트 텍스처의 look 으로)
        kr.labyrinth.content.ArmorLook l = def.armorLook();
        if (l == null || !l.real()) {
            ItemSetDef set = def.setBonus() == null ? null : services.content().sets().get(def.setBonus());
            l = set == null ? null : kr.labyrinth.content.ArmorLook.byId(set.look());
        }
        String sound = l == kr.labyrinth.content.ArmorLook.HEAVY ? "item.armor.equip_iron"
                : l == kr.labyrinth.content.ArmorLook.CLOTH ? "item.armor.equip_generic" : "item.armor.equip_leather";
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

    /** 0.3.5 굴림 옮기기를 PDC 에 써 넣고(옮길 것이 있으면) 이름·툴팁을 다시 그린다 — 접속·상자 열기·줍기·손 바꿈 때 불린다. */
    @Override
    public void refresh(ItemStack stack) {
        defOf(stack).ifPresent(def -> {
            migrate(stack, def);
            render(stack, def);
        });
    }

    /** 깃발이 35 보다 낮은 장비의 굴림을 0.3.5 범위로 옮겨 PDC 에 쓴다 (ItemMigration035). @return 바꿨으면 true */
    static boolean migrate(ItemStack stack, ItemDef def) {
        if (stack == null || def == null || !def.isGear()) return false;
        var pdc = stack.getPersistentDataContainer();
        Integer ver = pdc.get(Keys.ITEM_COMBAT_VER, PersistentDataType.INTEGER);
        if (!ItemMigration035.needed(def, ver == null ? 0 : ver)) return false;
        String enc = pdc.get(Keys.ITEM_ROLLS, PersistentDataType.STRING);
        Map<String, Double> rolls = enc == null ? Map.of() : ItemRolls.decode(enc);
        stack.editPersistentDataContainer(w -> {
            if (!rolls.isEmpty()) w.set(Keys.ITEM_ROLLS, PersistentDataType.STRING, ItemRolls.encode(ItemMigration035.migrate(def, rolls)));
            w.set(Keys.ITEM_COMBAT_VER, PersistentDataType.INTEGER, ItemMigration035.VERSION);
        });
        return true;
    }

    /** 굴림값 × 강화 배율 (GDD §11.13 — 무기 피해, 방어구·방패 방어·HP). */
    @Override
    public Map<String, Double> rolledStats(ItemStack stack) {
        Optional<ItemDef> def = defOf(stack);
        if (def.isEmpty() || !def.get().isGear()) return Map.of();
        Map<String, Double> base = baseRolls(stack, def.get());
        int lv = Enhancement.level(stack);
        return lv > 0 ? Enhancement.rules().apply(def.get(), base, lv) : base;
    }

    @Override
    public double midDamage(ItemStack stack) {
        Optional<ItemDef> def = defOf(stack);
        if (def.isEmpty() || !def.get().isWeapon()) return 0;
        kr.labyrinth.content.Range r = def.get().stats().get("damage");
        if (r == null) return 0;
        Map<String, Double> mid = Map.of("damage", r.lerp(0.5));
        int lv = Enhancement.level(stack);
        Map<String, Double> m = lv > 0 ? Enhancement.rules().apply(def.get(), mid, lv) : mid;
        return m.getOrDefault("damage", 0.0);
    }

    /**
     * 강화 전 굴림값 (PDC 굴림 → 시드 재현 → 범위 중간값 순). PDC 굴림이 0.3.5 전 것(깃발 &lt; 35)이면 같은 위치로 옮긴 값을 돌려준다
     * ({@link ItemMigration035}, PDC 는 {@link #refresh} 때 고쳐 쓴다).
     */
    public static Map<String, Double> baseRolls(ItemStack stack, ItemDef def) {
        var pdc = stack.getPersistentDataContainer();
        String enc = pdc.get(Keys.ITEM_ROLLS, PersistentDataType.STRING);
        if (enc != null) {
            Map<String, Double> m = ItemRolls.decode(enc);
            if (!m.isEmpty()) {
                Integer ver = pdc.get(Keys.ITEM_COMBAT_VER, PersistentDataType.INTEGER);
                return ItemMigration035.needed(def, ver == null ? 0 : ver) ? ItemMigration035.migrate(def, m) : m;
            }
        }
        Long seed = pdc.get(Keys.ITEM_SEED, PersistentDataType.LONG);
        return seed != null ? ItemRolls.roll(def, seed) : ItemRolls.midpoint(def);
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
