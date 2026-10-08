package kr.souls.item;

import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.BlocksAttacks;
import io.papermc.paper.datacomponent.item.Consumable;
import io.papermc.paper.datacomponent.item.DamageResistant;
import io.papermc.paper.datacomponent.item.ItemAttributeModifiers;
import io.papermc.paper.datacomponent.item.ItemLore;
import io.papermc.paper.datacomponent.item.SwingAnimation;
import io.papermc.paper.datacomponent.item.UseEffects;
import io.papermc.paper.datacomponent.item.blocksattacks.DamageReduction;
import io.papermc.paper.datacomponent.item.blocksattacks.ItemDamageFunction;
import io.papermc.paper.datacomponent.item.consumable.ItemUseAnimation;
import io.papermc.paper.registry.keys.tags.DamageTypeTagKeys;
import kr.souls.Keys;
import kr.souls.Lang;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeModifier;
import org.bukkit.inventory.EquipmentSlotGroup;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 데이터 성분을 붙이는 곳은 여기 한 곳이다 (9.8). 데이터 성분 API 는 1.21.11 에서도 실험 기능이라
 * Paper 빌드를 132 로 고정하고, 바뀌면 이 파일만 고친다.
 * M0 에는 막기 성분 서버 시험용 도구와 휘두름 시험 도구만 있다. 둘 다 맞춤 모형 souls:test_guard (팩의 items/test_guard.json:
 * 평소 모형과 막는 모형을 using_item 으로 가른다, 10.6) 를 쓴다. 이것이 M0 의 items 아틀라스 점검이다 (13.4 의 6).
 * 이름과 설명은 번역 열쇠다 (Lang.c, Lang.lines). 아이템에 글이 아니라 열쇠가 적히므로 누가 들어도 그 사람의 언어로 보인다.
 */
@SuppressWarnings("UnstableApiUsage")
public final class ItemFactory {
    /** 시험용 막기 도구의 껍데기. 검 태그가 없고 우클릭 동작이 없는 바닐라 아이템 (9.8 후보). */
    public static final Material SHELL = Material.FLINT;
    /** 시험 도구의 맞춤 모형 (팩 assets/souls/items/test_guard.json) */
    public static final Key TEST_MODEL = Key.key(Keys.NS, "test_guard");
    /** 바닐라 무기가 공격 속도에 쓰는 수정자 열쇠 (같은 열쇠라야 설명 칸에 "공격 속도" 로 묶여 보인다) */
    private static final NamespacedKey BASE_ATTACK_SPEED = NamespacedKey.minecraft("base_attack_speed");
    /** 플레이어의 기본 공격 속도 */
    private static final double PLAYER_ATTACK_SPEED = 4.0;

    /** 막기 시험의 세 가지 판. */
    public enum GuardTest {
        /** 설계 기본: 빈 감소표 + #bypasses_shield. generic 피해가 그대로 들어와야 한다 */
        EMPTY,
        /** 대조군: 바닐라 방패처럼 다 막는 감소표, 우회 없음. 피해가 0 이어야 한다 (시험이 막기를 알아보는지) */
        CONTROL,
        /** 다 막는 감소표 + #bypasses_shield. 우회가 먹으면 피해가 그대로 들어온다 */
        BYPASS,
        /** 막기 성분을 뗀 같은 도구. 왼손에 방패가 있으면 같은 우클릭으로 왼손 방패를 든다 (13.4 의 7) */
        STRIP;

        public static GuardTest parse(String s) {
            try {
                return valueOf(s.toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return null;
            }
        }
    }

    private ItemFactory() {}

    /**
     * 막기 성분 (3.4). 막기 계산은 모두 플러그인이 한다. 바닐라 성분은 막는 자세, using_item 모델, 걸음 느려짐에만 쓴다.
     * 감소표는 늘 비워 둔다 (비어 있지 않으면 바닐라가 피해를 한 번 더 깎고, 내구도를 깎고, 막은 사람을 민다).
     * bypassedBy 는 #minecraft:bypasses_shield (generic 이 들어 있다), disableCooldownScale 은 0.
     */
    public static BlocksAttacks.Builder guardComponent() {
        return BlocksAttacks.blocksAttacks()
                .blockDelaySeconds(0f)
                .disableCooldownScale(0f)
                .bypassedBy(DamageTypeTagKeys.BYPASSES_SHIELD);
    }

    /** 막는 동안 걸음 배율 (2.3.9). 달리기는 없다. */
    public static UseEffects.Builder guardUse(float speed) {
        return UseEffects.useEffects().canSprint(false).interactVibrations(false).speedMultiplier(speed);
    }

    public static ItemStack testGuard(GuardTest kind) {
        ItemStack it = ItemStack.of(SHELL);
        BlocksAttacks.Builder ba = switch (kind) {
            case STRIP -> null;
            case EMPTY -> guardComponent();
            case CONTROL -> BlocksAttacks.blocksAttacks().blockDelaySeconds(0f).disableCooldownScale(0f)
                    .addDamageReduction(DamageReduction.damageReduction().base(0f).factor(1f).horizontalBlockingAngle(90f).build())
                    .itemDamage(ItemDamageFunction.itemDamageFunction().threshold(1f).base(0f).factor(1f).build());
            case BYPASS -> guardComponent()
                    .addDamageReduction(DamageReduction.damageReduction().base(0f).factor(1f).horizontalBlockingAngle(90f).build())
                    .itemDamage(ItemDamageFunction.itemDamageFunction().threshold(1f).base(0f).factor(1f).build());
        };
        if (ba != null) {
            it.setData(DataComponentTypes.BLOCKS_ATTACKS, ba);
            it.setData(DataComponentTypes.USE_EFFECTS, guardUse(0.55f));
        }
        // 내구도가 깎이는지 보려고 붙인다. 깎이는 아이템은 묶음이 될 수 없다
        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        it.setData(DataComponentTypes.MAX_DAMAGE, 100);
        it.setData(DataComponentTypes.DAMAGE, 0);
        it.setData(DataComponentTypes.ITEM_MODEL, TEST_MODEL);
        it.setData(DataComponentTypes.ITEM_NAME, Lang.c("test.guard", "kind", kind.name().toLowerCase(Locale.ROOT)));
        it.setData(DataComponentTypes.LORE, ItemLore.lore(Lang.lines("test.guard-lore")));
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.ITEM, PersistentDataType.STRING, "test_guard_" + kind.name().toLowerCase(Locale.ROOT)));
        return it;
    }

    /**
     * 휘두름 시험 도구 (13.4 의 8). swing_animation 길이(틱)가 팔을 휘두르는 시간을 늘이고,
     * attack_speed 를 기본(4)보다 낮추면 조준점 밑에 회복 표시기가 그려진다. 막기 성분은 없다.
     */
    public static ItemStack testSwing(int ticks, double attackSpeed) {
        ItemStack it = ItemStack.of(SHELL);
        it.setData(DataComponentTypes.SWING_ANIMATION, SwingAnimation.swingAnimation().type(SwingAnimation.Animation.WHACK).duration(ticks).build());
        it.setData(DataComponentTypes.ATTRIBUTE_MODIFIERS, ItemAttributeModifiers.itemAttributes()
                .addModifier(Attribute.ATTACK_SPEED, new AttributeModifier(BASE_ATTACK_SPEED, attackSpeed - PLAYER_ATTACK_SPEED,
                        AttributeModifier.Operation.ADD_NUMBER, EquipmentSlotGroup.MAINHAND))
                .build());
        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        it.setData(DataComponentTypes.ITEM_MODEL, TEST_MODEL);
        it.setData(DataComponentTypes.ITEM_NAME, Lang.c("test.swing", "ticks", String.valueOf(ticks)));
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.ITEM, PersistentDataType.STRING, "test_swing"));
        return it;
    }

    /** 활 당기기: 끝까지 당겨도 먹기가 끝나지 않을 만큼 (바닐라 활의 사용 시간 72000 틱과 같다). 먹기는 WeaponGuard 가 취소한다 */
    private static final float BOW_HOLD_SECONDS = 3600f;
    /** 무기 설명 칸 그림 souls:tooltip/weapon_background·_frame (이름 밑 금실, pack/gui_skin.py) */
    private static final Key WEAPON_TOOLTIP = Key.key(Keys.NS, "weapon");

    /**
     * 무기·방패·활·촉매 아이템 (9.8). 검 태그 없는 껍데기에 모형 souls:&lt;id&gt; (팩 pack/weapons, 손에 든 3D 모형과 16 픽셀 그림),
     * 이름 weapon.&lt;id&gt;.name (제목 글꼴), 설명 칸 = 분류 줄, 수치 표 (StatTable, 두 열), 실선, weapon.&lt;id&gt;.lore (9.7). 모두
     * 번역 열쇠라 보는 사람의 언어로 보인다. 설명 칸 그림은 무기 칸 (tooltip_style souls:weapon: 이름 밑 금실, pack/gui_skin.py). 막는 것 (무기 guard, 방패 block) 은 빈 막기 성분과 걸음 배율 (2.3.9), 활은 당기기 몸짓 (CONSUMABLE bow, 쏘기는 M1).
     * 불에 타지 않는다. 묶음은 하나.
     */
    public static ItemStack weapon(Weapons.Def d) {
        ItemStack it = ItemStack.of(SHELL);
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, d.id()));
        it.setData(DataComponentTypes.ITEM_NAME, Lang.c("weapon." + d.id() + ".name")); // lang-dyn: weapon.*.name
        List<Component> lore = new ArrayList<>();
        lore.add(Lang.c("weapon.class." + d.cls())); // lang-dyn: weapon.class.*
        lore.addAll(StatTable.lines(d));
        lore.add(StatTable.rule());
        lore.addAll(Lang.lines("weapon." + d.id() + ".lore")); // lang-dyn: weapon.*.lore
        it.setData(DataComponentTypes.LORE, ItemLore.lore(lore));
        it.setData(DataComponentTypes.TOOLTIP_STYLE, WEAPON_TOOLTIP);
        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);
        it.setData(DataComponentTypes.DAMAGE_RESISTANT, DamageResistant.damageResistant(DamageTypeTagKeys.IS_FIRE));
        switch (d.use()) {
            case Weapons.GUARD, Weapons.BLOCK -> {
                it.setData(DataComponentTypes.BLOCKS_ATTACKS, guardComponent());
                it.setData(DataComponentTypes.USE_EFFECTS, guardUse((float) d.walk()));
            }
            case Weapons.BOW -> {
                it.setData(DataComponentTypes.CONSUMABLE, Consumable.consumable().consumeSeconds(BOW_HOLD_SECONDS)
                        .animation(ItemUseAnimation.BOW).hasConsumeParticles(false).build());
                it.setData(DataComponentTypes.USE_EFFECTS, guardUse((float) d.walk()));
            }
            default -> {
                // 촉매: 술 (CONSUMABLE 의 몸짓·시간) 은 M5 에 붙인다 (3.12.4)
            }
        }
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.WEAPON, PersistentDataType.STRING, d.id()));
        return it;
    }

    /** 이 아이템이 시험 막기 도구인가. */
    public static boolean isTestGuard(ItemStack it) {
        String id = kr.souls.util.Items.tag(it, Keys.ITEM);
        return id != null && id.startsWith("test_guard_");
    }
}
