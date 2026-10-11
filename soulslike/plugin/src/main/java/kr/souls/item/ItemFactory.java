package kr.souls.item;

import io.papermc.paper.datacomponent.DataComponentType;
import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.BannerPatternLayers;
import io.papermc.paper.datacomponent.item.BlocksAttacks;
import io.papermc.paper.datacomponent.item.DamageResistant;
import io.papermc.paper.datacomponent.item.ItemAttributeModifiers;
import io.papermc.paper.datacomponent.item.ItemEnchantments;
import io.papermc.paper.datacomponent.item.ItemLore;
import io.papermc.paper.datacomponent.item.SwingAnimation;
import io.papermc.paper.datacomponent.item.UseEffects;
import io.papermc.paper.datacomponent.item.blocksattacks.DamageReduction;
import io.papermc.paper.datacomponent.item.blocksattacks.ItemDamageFunction;
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
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

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

    /** 활의 껍데기: 바닐라 활 (당기기·쏘기·화살 쓰기가 바닐라 그대로, 3.6 의 "바닐라 당기기". 피해 바꾸기·화살 돌려주기는 M1) */
    public static final Material BOW_SHELL = Material.BOW;
    /**
     * 방패 (use: block) 의 껍데기: 바닐라 방패 (DECISIONS 2026-10-11 "방패는 바닐라 방패"). 1인칭 막기에서 바닐라는 방패가 아닌 막는
     * 아이템에만 칼 막기 몸짓 (Rx −102.25 …) 을 더 건다. 껍데기가 방패라야 모형의 shield_blocking 자세가 바닐라 방패와 똑같이 보인다
     * (pack/weapons/SPEC.md 1.3). 막기 계산은 그대로 플러그인이 한다 (빈 막기 성분, guardComponent).
     */
    public static final Material SHIELD_SHELL = Material.SHIELD;
    /**
     * 창·미늘창 (분류 spear, halberd) 의 껍데기: 바닐라 창 (DECISIONS 2026-10-11 "창·미늘창은 바닐라 창처럼 쥔다"). 1.21.11 클라이언트는
     * 아이템 태그 #minecraft:spears 인 것을 3인칭에서 팔을 들어 앞으로 겨누는 자세 (ArmPose.SPEAR) 로 든다. 손에 든 모형의 자세
     * (팩 item/spear_in_hand 합성, pack/weapons/SPEC.md 1.3) 는 그 팔 자세에 맞춘 것이라 껍데기가 창이어야 바닐라 창과 같다.
     * 돌창: 화로에 녹지 않고 땔감이 아니다. 바닐라 창의 성분 (찌르기·돌진·사거리·내구도·공격 속성 …) 은 모두 떼어 부싯돌 껍데기와
     * 같은 성분만 남긴다 ({@link #asFlint}). 휘두르기·막기·피해는 그대로 플러그인이 한다.
     */
    public static final Material SPEAR_SHELL = Material.STONE_SPEAR;
    /** 무기 설명 칸 그림 souls:tooltip/weapon_background·_frame (이름 밑 금실, pack/gui_skin.py) */
    private static final Key WEAPON_TOOLTIP = Key.key(Keys.NS, "weapon");

    /**
     * 무기·방패·활·촉매 아이템 (9.8). 검 태그 없는 껍데기에 모형 souls:&lt;id&gt; (팩 pack/weapons, 손에 든 3D 모형과 16 픽셀 그림),
     * 이름 weapon.&lt;id&gt;.name (제목 글꼴), 설명 칸 = 분류 줄, 수치 한 줄 (StatTable: 제 값과 무게), 실선, weapon.&lt;id&gt;.lore (9.7). 모두
     * 번역 열쇠라 보는 사람의 언어로 보인다. 설명 칸 그림은 무기 칸 (tooltip_style souls:weapon: 이름 밑 금실, pack/gui_skin.py). 막는 것 (무기 guard, 방패 block) 은 빈 막기 성분과 걸음 배율 (2.3.9).
     * 촉매와 패링 단검 (use: none) 은 막지 않는다 (패링 단검: 우클릭은 왼손 공격 M1, F 는 패링).
     * 활 (use: bow) 은 바닐라 활 껍데기라 화살이 있으면 바닐라처럼 당겨 쏜다 (검토 archer-thief-promises: 궁수가 활을 쏠 수 있게. 모형의
     * 당긴 모습은 using_item·use_duration 이라 껍데기와 상관없다). 방패 (use: block) 는 바닐라 방패 껍데기 (SHIELD_SHELL). 바닐라 방패의
     * equippable (왼손, 우클릭으로 바꿔 끼지 않음) 은 남겨 둔다: 인벤토리에서 웅크리고 누르면 바닐라 방패처럼 빈 왼손 칸으로 간다.
     * 닳지 않고 마법부여·수리를 받지 않는다. 불에 타지 않는다. 묶음은 하나.
     */
    public static ItemStack weapon(Weapons.Def d) {
        boolean bow = Weapons.BOW.equals(d.use());
        boolean shield = Weapons.BLOCK.equals(d.use());
        boolean spear = SPEAR_CLASSES.contains(d.cls());
        ItemStack it = ItemStack.of(bow ? BOW_SHELL : shield ? SHIELD_SHELL : spear ? SPEAR_SHELL : SHELL);
        if (spear) asFlint(it);
        if (bow || shield) {
            it.unsetData(DataComponentTypes.MAX_DAMAGE);
            it.unsetData(DataComponentTypes.DAMAGE);
            it.unsetData(DataComponentTypes.ENCHANTABLE);
            it.unsetData(DataComponentTypes.REPAIRABLE);
        }
        it.setData(DataComponentTypes.ITEM_MODEL, Key.key(Keys.NS, d.id()));
        it.setData(DataComponentTypes.ITEM_NAME, Lang.c("weapon." + d.id() + ".name")); // lang-dyn: weapon.*.name
        List<Component> lore = new ArrayList<>();
        lore.add(Lang.c("weapon.class." + d.cls())); // lang-dyn: weapon.class.*
        lore.addAll(StatTable.lines(d));
        lore.add(StatTable.rule(d));
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
            case Weapons.BOW -> it.setData(DataComponentTypes.USE_EFFECTS, guardUse((float) d.walk()));
            default -> {
                // 촉매: 술법 (CONSUMABLE 의 몸짓·시간) 은 M5 에 붙인다 (3.12.4). 패링 단검: 왼손 공격은 M1
            }
        }
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.WEAPON, PersistentDataType.STRING, d.id()));
        return it;
    }

    /** 바닐라 창 껍데기 (SPEAR_SHELL) 로 만드는 분류 (weapons.yml class) */
    public static final Set<String> SPEAR_CLASSES = Set.of("spear", "halberd");

    /**
     * 성분을 부싯돌 (SHELL) 의 기본 성분과 똑같이 맞춘다: 부싯돌에 없는 성분은 떼고, 둘 다 있는 성분은 부싯돌 값으로. 바닐라 창 껍데기가
     * 아이템 종류 (태그 #minecraft:spears, 팔 자세) 말고는 부싯돌 무기와 똑같이 쓰이게 (뗀다: kinetic_weapon, piercing_weapon,
     * attack_range, minimum_attack_charge, damage_type, weapon, max_damage, damage, enchantable, repairable, use_effects,
     * 부싯돌 값으로: attribute_modifiers (창의 공격력·공격 속도), swing_animation (창의 찌르기 stab)).
     */
    static void asFlint(ItemStack it) {
        ItemStack flint = ItemStack.of(SHELL);
        for (DataComponentType t : Set.copyOf(it.getDataTypes())) {
            if (!flint.hasData(t)) it.unsetData(t);
        }
        for (DataComponentType t : flint.getDataTypes()) {
            if (t instanceof DataComponentType.Valued<?> v) copyData(flint, it, v);
            else if (t instanceof DataComponentType.NonValued n && !it.hasData(n)) it.setData(n);
        }
    }

    private static <T> void copyData(ItemStack from, ItemStack to, DataComponentType.Valued<T> t) {
        T v = from.getData(t);
        if (v != null && !v.equals(to.getData(t))) to.setData(t, v);
    }

    /**
     * 궁수의 시작 화살 (바닐라 화살 n 개). souls 표시 souls:item=arrows 를 붙여 출신 지우기·다시 고르기가 거둔다 (쏘아 주운 화살도
     * 표시가 남아 함께 묶인다). 화살 아이템은 M1 의 화살 돌려주기와 함께 다시 본다.
     */
    public static ItemStack arrows(int n) {
        ItemStack it = ItemStack.of(Material.ARROW, Math.max(1, Math.min(64, n)));
        it.editPersistentDataContainer(pdc -> pdc.set(Keys.ITEM, PersistentDataType.STRING, "arrows"));
        return it;
    }

    /**
     * 예전 판의 souls 무기를 지금 판으로 다시 만든 것, 지금 판 그대로면 null: 껍데기가 바뀌었거나 (활: 부싯돌 → 바닐라 활, 방패: 부싯돌 →
     * 바닐라 방패, 창·미늘창: 부싯돌 → 바닐라 돌창, 2026-10-11), 설명 칸이
     * 지금 판과 다르거나 (2026-10-10: 보정·요구 능력치 줄을 없애고 수치를 한 줄로, 방패는 막기 하나. weapons.yml 을 고치고 다시 읽은 값,
     * 언어 파일의 대체 글이 바뀐 것도), 쓰는 몸짓이 바뀐 것 (패링 단검·촉매는 막지 않는다), 우리가 붙이지 않은 것이 붙은 것
     * ({@link #foreign}: 마법부여, 방패의 깃발 색·무늬, 지금 판과 다른 성분 종류). 주손 무기의 막기 성분은 견주지 않는다
     * (WeaponGuard 가 든 손을 보고 맞춘다).
     */
    public static ItemStack refreshed(ItemStack it, Weapons weapons) {
        Weapons.Def d = it == null || it.isEmpty() ? null : weapons.of(it);
        if (d == null) return null;
        ItemStack fresh = weapon(d);
        if (it.getType() == fresh.getType() && sameLore(it, fresh) && !staleUse(it, d) && !foreign(it, fresh)) return null;
        return fresh;
    }

    /**
     * 우리가 붙이지 않은 것이 붙었다 (검토 P0-5): 마법부여 (돌창 껍데기는 #minecraft:spears 라 모루가 화염·밀치기·약탈·날카로움·돌진
     * 책을 붙일 수 있다. 플러그인 피해 셈 밖에서 불·밀치기·떨굼이 돈다), 방패의 깃발 바탕색·무늬 (제작대에서 깃발을 붙이면 이름이 바닐라
     * "빨간 방패" 가 된다), 지금 판과 다른 성분 종류 (예전 판의 껍데기에 남은 성분, 마인크래프트 판이 바뀌어 껍데기에 새로 생긴 성분).
     * 모루·제작대 길은 {@link WeaponRefresh} 가 막지만, 다른 세계·예전 판에서 붙은 것은 여기서 고친다.
     */
    static boolean foreign(ItemStack it, ItemStack fresh) {
        ItemEnchantments en = it.getData(DataComponentTypes.ENCHANTMENTS);
        if (en != null && !en.enchantments().isEmpty()) return true;
        if (it.hasData(DataComponentTypes.BASE_COLOR)) return true;
        BannerPatternLayers bp = it.getData(DataComponentTypes.BANNER_PATTERNS);
        if (bp != null && !bp.patterns().isEmpty()) return true;
        // 플러그인이 든 손을 보고 붙였다 뗐다 하는 성분 (WeaponGuard 의 막기·걸음 배율, 구르기 깃발) 은 빼고 견준다.
        // (상수로 두지 않는다: DataComponentTypes 는 서버 등록부에서 읽어 JUnit 이 ItemFactory 를 실을 때 없다)
        List<DataComponentType> live = List.of(DataComponentTypes.BLOCKS_ATTACKS, DataComponentTypes.USE_EFFECTS, DataComponentTypes.CUSTOM_MODEL_DATA);
        Set<DataComponentType> a = new HashSet<>(it.getDataTypes()), b = new HashSet<>(fresh.getDataTypes());
        live.forEach(a::remove);
        live.forEach(b::remove);
        return !a.equals(b);
    }

    /**
     * 인벤토리 (플레이어의 것이면 단축 슬롯·가방·갑옷·왼손, 상자·엔더 상자 …) 의 예전 판 souls 무기를 같은 칸에서 지금 판으로 바꾼다
     * (item/WeaponRefresh: 접속, 줍기, 상자 열기, /souls reload). 바꾼 수.
     */
    public static int refreshWeapons(org.bukkit.inventory.Inventory inv, Weapons weapons) {
        int n = 0;
        ItemStack[] all = inv.getContents();
        for (int i = 0; i < all.length; i++) {
            ItemStack fresh = refreshed(all[i], weapons);
            if (fresh == null) continue;
            inv.setItem(i, fresh);
            n++;
        }
        return n;
    }

    private static boolean sameLore(ItemStack a, ItemStack b) {
        ItemLore la = a.getData(DataComponentTypes.LORE), lb = b.getData(DataComponentTypes.LORE);
        return la == null ? lb == null : lb != null && la.lines().equals(lb.lines());
    }

    /** 막기 성분이 있으면 안 되는 것 (방패도 막는 무기도 아닌 것: 촉매, 패링 단검) 에 막기 성분이 남았다. */
    private static boolean staleUse(ItemStack it, Weapons.Def d) {
        return Weapons.NONE.equals(d.use()) && it.hasData(DataComponentTypes.BLOCKS_ATTACKS);
    }

    /** 이 아이템이 시험 막기 도구인가. */
    public static boolean isTestGuard(ItemStack it) {
        String id = kr.souls.util.Items.tag(it, Keys.ITEM);
        return id != null && id.startsWith("test_guard_");
    }
}
