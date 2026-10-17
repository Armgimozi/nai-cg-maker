package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.core.DeathPenaltyRules.Box;
import org.junit.jupiter.api.Test;

/** 0.3.6.2 죽음 페널티 — 장비는 가방에 있어도 안전 · 셜커 상자·꾸러미 규칙. */
class DeathPenaltyGearTest {

    /** 가짜 물건: type = 미궁 아이템 종류 (바닐라면 null), inner = 담긴 것 (담는 물건이 아니면 null). */
    record Item(String id, ItemType type, int count, List<Item> inner) {
        static Item lab(String id, ItemType type, int count) { return new Item(id, type, count, null); }
        static Item vanilla(String id, int count) { return new Item(id, null, count, null); }
        static Item box(String id, Item... in) { return new Item(id, null, 1, new ArrayList<>(Arrays.asList(in))); }
    }

    /** 런타임 DeathPenalty.Stacks 와 같은 판정: keep = alwaysSafe(type, id, 무한 화살 아님, safe_items). */
    static final class Fake implements Box<Item> {
        final Set<String> safe;

        Fake(Set<String> safe) { this.safe = safe; }

        @Override public boolean empty(Item s) { return s == null || s.count() <= 0; }
        @Override public boolean keep(Item s) { return DeathPenaltyRules.alwaysSafe(s.type(), s.id(), false, safe); }
        @Override public List<Item> contents(Item s) { return s.inner() == null ? null : new ArrayList<>(s.inner()); }
        @Override public Item withContents(Item s, List<Item> c) { return new Item(s.id(), s.type(), s.count(), new ArrayList<>(c)); }
    }

    static final Fake BOX = new Fake(Set.of());

    static final Item SWORD = Item.lab("corridor_longsword", ItemType.WEAPON, 1);
    static final Item BOW = Item.lab("hunter_bow", ItemType.WEAPON, 1);
    static final Item HELM = Item.lab("guard_helm", ItemType.ARMOR, 1);
    static final Item SHIELD = Item.lab("oak_buckler", ItemType.ARMOR, 1); // 방패 = armor offhand
    static final Item RING = Item.lab("copper_ring", ItemType.ACCESSORY, 1);
    static final Item KEY = Item.lab("vault_key", ItemType.KEY, 1);
    static final Item PICK = Item.lab("iron_pickaxe", ItemType.TOOL, 1);
    static final Item INGOT = Item.lab("iron_ingot", ItemType.MATERIAL, 13);
    static final Item POTION = Item.lab("minor_healing_potion", ItemType.CONSUMABLE, 5);
    static final Item STONE = Item.lab("lesser_enhance_stone", ItemType.MATERIAL, 4);
    static final Item PRINT = Item.lab("blueprint", ItemType.BLUEPRINT, 1);
    static final Item BREAD = Item.vanilla("bread", 5);

    static boolean[] eligible(Item[] bag) {
        boolean[] e = new boolean[bag.length];
        for (int i = 0; i < bag.length; i++) e[i] = DeathPenaltyRules.losable(bag[i], BOX);
        return e;
    }

    // ── 장비 ─────────────────────────────────────────────────────────────

    @Test
    void gearTypesAreAlwaysSafe() {
        Set<String> none = Set.of();
        assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.WEAPON, "corridor_longsword", false, none), "무기");
        assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.ARMOR, "guard_helm", false, none), "방어구");
        assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.ARMOR, "oak_buckler", false, none), "방패 (armor offhand)");
        assertTrue(DeathPenaltyRules.alwaysSafe(ItemType.ACCESSORY, "copper_ring", false, none), "장신구");
        for (ItemType t : ItemType.values()) {
            if (t.isGear()) assertTrue(DeathPenaltyRules.alwaysSafe(t, "x", false, none), t.id());
        }
        // 장비가 아닌 것은 그대로 잃을 수 있다
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.MATERIAL, "iron_ingot", false, none));
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.CONSUMABLE, "minor_healing_potion", false, none));
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.MATERIAL, "lesser_enhance_stone", false, none), "강화석");
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.BLUEPRINT, "blueprint", false, none), "도안");
        assertFalse(DeathPenaltyRules.alwaysSafe(ItemType.MATERIAL, "broken_sword", false, none), "이름이 칼이어도 미궁 재료는 재료");
    }

    @Test
    void vanillaGearIsSafeVanillaToolsAreNot() {
        for (String id : List.of("wooden_sword", "diamond_sword", "netherite_axe", "iron_spear", "trident", "mace", "bow", "crossbow",
                "leather_helmet", "iron_chestplate", "golden_leggings", "netherite_boots", "turtle_helmet", "chainmail_helmet",
                "shield", "elytra", "minecraft:diamond_sword", "DIAMOND_SWORD")) {
            assertTrue(DeathPenaltyRules.vanillaGear(id), id);
            assertTrue(DeathPenaltyRules.alwaysSafe(null, id, false, Set.of()), id);
        }
        for (String id : List.of("diamond_pickaxe", "iron_shovel", "wooden_hoe", "fishing_rod", "bowl", "stick", "arrow",
                "leather_horse_armor", "wolf_armor", "carved_pumpkin", "totem_of_undying", "shulker_box", "bundle", "")) {
            assertFalse(DeathPenaltyRules.vanillaGear(id), id);
        }
        assertFalse(DeathPenaltyRules.vanillaGear(null));
    }

    @Test
    void gearInTheBagIsNeverPicked() {
        // 단축 칸·가방에 장비 9개 + 보통 물건 3칸, 손에 든 칸은 0 (빈 칸)
        Item[] bag = new Item[DeathPenaltyRules.STORAGE_SLOTS];
        Item[] gear = {SWORD, BOW, HELM, SHIELD, RING, SWORD, HELM, RING, BOW};
        int[] gearSlots = {1, 2, 5, 9, 14, 20, 27, 31, 35};
        for (int i = 0; i < gear.length; i++) bag[gearSlots[i]] = gear[i];
        bag[3] = INGOT;
        bag[22] = POTION;
        bag[33] = BREAD;
        boolean[] e = eligible(bag);
        for (int s : gearSlots) assertFalse(e[s], "장비 칸 " + s);
        for (long seed = 0; seed < 3000; seed++) {
            int[] got = DeathPenaltyRules.pickSlots(e, 0, 2, 3, new SplittableRandom(seed));
            assertTrue(got.length == 2 || got.length == 3);
            for (int g : got) {
                assertTrue(g == 3 || g == 22 || g == 33, "보통 물건 칸만: " + g);
                assertNull(DeathPenaltyRules.strip(bag[g], BOX, new ArrayList<>()), "보통 물건은 통째로");
            }
        }
    }

    @Test
    void onlyGearMeansNothingLost() {
        Item[] bag = new Item[DeathPenaltyRules.STORAGE_SLOTS];
        bag[0] = SWORD; // 손에 든 칸
        bag[4] = BOW;
        bag[10] = HELM;
        bag[11] = SHIELD;
        bag[12] = RING;
        bag[13] = KEY;
        bag[14] = PICK;
        bag[15] = Item.box("shulker_box", SWORD, HELM, RING); // 장비만 든 상자
        bag[16] = Item.box("shulker_box");                    // 빈 상자
        bag[17] = Item.vanilla("diamond_sword", 1);
        bag[18] = Item.vanilla("elytra", 1);
        for (long seed = 0; seed < 200; seed++) {
            assertEquals(0, DeathPenaltyRules.pickSlots(eligible(bag), 0, 2, 3, new SplittableRandom(seed)).length);
        }
    }

    @Test
    void gearDoesNotShieldOtherItems() {
        // 장비가 많아도 남은 보통 물건 하나는 반드시 뽑힌다 (장비는 후보를 채우지 않는다)
        Item[] bag = new Item[DeathPenaltyRules.STORAGE_SLOTS];
        for (int i = 1; i < 35; i++) bag[i] = SWORD;
        bag[35] = INGOT;
        for (long seed = 0; seed < 100; seed++) {
            assertEquals(35, DeathPenaltyRules.pickSlots(eligible(bag), 0, 2, 3, new SplittableRandom(seed))[0]);
        }
    }

    // ── 셜커 상자·꾸러미 ─────────────────────────────────────────────────

    @Test
    void shulkerWithMixedContentsLosesOnlyNonGear() {
        Item box = Item.box("shulker_box", SWORD, INGOT, null, BREAD, HELM, KEY, PRINT, RING);
        assertTrue(DeathPenaltyRules.losable(box, BOX));
        List<Item> lost = new ArrayList<>();
        Item after = DeathPenaltyRules.strip(box, BOX, lost);
        assertNotNull(after, "상자는 남는다");
        assertEquals("shulker_box", after.id());
        assertEquals(List.of(INGOT, BREAD, PRINT), lost, "장비 아닌 것만");
        assertEquals(Arrays.asList(SWORD, null, null, null, HELM, KEY, null, RING), after.inner(), "장비·열쇠는 제자리, 지운 자리는 빈 칸");
        assertFalse(DeathPenaltyRules.losable(after, BOX), "남은 상자에는 잃을 것이 없다");
        assertSame(after, DeathPenaltyRules.strip(after, BOX, lost), "다시 뽑아도 그대로");
    }

    @Test
    void shulkerWithOnlyStuffLosesAllButKeepsTheBox() {
        Item box = Item.box("red_shulker_box", INGOT, POTION, STONE);
        List<Item> lost = new ArrayList<>();
        Item after = DeathPenaltyRules.strip(box, BOX, lost);
        assertEquals(List.of(INGOT, POTION, STONE), lost);
        assertNotNull(after);
        assertEquals(Arrays.asList(null, null, null), after.inner());
    }

    @Test
    void emptyOrGearOnlyBoxesAreNotCandidates() {
        assertFalse(DeathPenaltyRules.losable(Item.box("shulker_box"), BOX), "빈 상자");
        assertFalse(DeathPenaltyRules.losable(Item.box("shulker_box", null, null), BOX), "빈 칸만");
        assertFalse(DeathPenaltyRules.losable(Item.box("shulker_box", SWORD, SHIELD, RING, KEY, PICK), BOX), "안전한 것만");
        assertFalse(DeathPenaltyRules.losable(Item.box("bundle", SWORD), BOX), "장비 하나 든 꾸러미");
        assertTrue(DeathPenaltyRules.losable(Item.box("bundle", BREAD), BOX));
        assertFalse(DeathPenaltyRules.losable(null, BOX));
    }

    @Test
    void bundleInsideShulkerFollowsTheSameRule() {
        Item bundle = Item.box("bundle", BREAD, POTION);
        Item gearBundle = Item.box("bundle", BOW);
        Item box = Item.box("shulker_box", bundle, gearBundle, INGOT, SWORD);
        List<Item> lost = new ArrayList<>();
        Item after = DeathPenaltyRules.strip(box, BOX, lost);
        assertEquals(List.of(BREAD, POTION, INGOT), lost);
        assertEquals(4, after.inner().size());
        assertEquals("bundle", after.inner().get(0).id(), "속 꾸러미도 남는다");
        assertEquals(Arrays.asList(null, null), after.inner().get(0).inner());
        assertSame(gearBundle, after.inner().get(1), "장비 꾸러미는 그대로");
        assertNull(after.inner().get(2));
        assertSame(SWORD, after.inner().get(3));
    }

    @Test
    void safeItemsListWorksInsideBoxes() {
        Fake withSafe = new Fake(Set.of("bread"));
        Item box = Item.box("shulker_box", BREAD, INGOT);
        List<Item> lost = new ArrayList<>();
        Item after = DeathPenaltyRules.strip(box, withSafe, lost);
        assertEquals(List.of(INGOT), lost);
        assertEquals(Arrays.asList(BREAD, null), after.inner());
        // safe_items 에 상자 자체를 적으면 안에 든 것까지 통째로 안전
        Fake boxSafe = new Fake(Set.of("shulker_box"));
        assertFalse(DeathPenaltyRules.losable(box, boxSafe));
    }

    @Test
    void ordinaryStackIsLostWhole() {
        List<Item> lost = new ArrayList<>();
        assertNull(DeathPenaltyRules.strip(INGOT, BOX, lost));
        assertEquals(List.of(INGOT), lost);
        lost.clear();
        assertSame(SWORD, DeathPenaltyRules.strip(SWORD, BOX, lost), "장비는 뽑혀도(규칙 밖) 그대로");
        assertTrue(lost.isEmpty());
    }

    @Test
    void absurdNestingStopsSafely() {
        Item deep = BREAD;
        for (int i = 0; i < 20; i++) deep = Item.box("bundle", deep);
        assertFalse(DeathPenaltyRules.losable(deep, BOX), "너무 깊으면 건드리지 않음");
        Item shallow = Item.box("bundle", Item.box("bundle", BREAD));
        assertTrue(DeathPenaltyRules.losable(shallow, BOX));
    }

    @Test
    void boxLossesAreGroupedInChat() {
        List<String> l = DeathPenaltyRules.lines(List.of(new DeathPenaltyRules.Lost("철 주괴", 13),
                new DeathPenaltyRules.Lost("빵", 5, "셜커 상자"), new DeathPenaltyRules.Lost("돌", 64, "셜커 상자"),
                new DeathPenaltyRules.Lost("빵", 2, "셜커 상자")), 0, 0);
        assertEquals(1, l.size());
        assertEquals("죽어서 잃었습니다: 철 주괴 ×13 · 셜커 상자 속: 빵 ×7, 돌 ×64", Text.strip(l.get(0)));
        assertEquals("죽어서 잃었습니다: 셜커 상자 속: 빵 ×5",
                Text.strip(DeathPenaltyRules.lines(List.of(new DeathPenaltyRules.Lost("빵", 5, "셜커 상자")), 0, 0).get(0)), "상자만");
    }
}
