package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.function.Predicate;
import kr.labyrinth.content.Params;
import kr.labyrinth.items.ItemMigration036;
import org.junit.jupiter.api.Test;

/** 옛 광물 재료 바꾸기 (계약 §2.10 · R §2-7) — 가짜 아이템으로: 1:1 · 겹쳐짐 · 셜커·꾸러미(안의 안) · 모르는 id · 새 id 없음 · 두 번. */
class ItemMigration036Test {

    /** 가짜 아이템: id(null = 바닐라) · 개수 · 안에 든 것(null = 보관함 아님). */
    record Fake(String id, int amount, List<Fake> contents) {
        static Fake of(String id, int n) { return new Fake(id, n, null); }
    }

    static final ItemMigration036.Access<Fake> ACCESS = new ItemMigration036.Access<>() {
        @Override public String itemId(Fake s) { return s.id(); }
        @Override public int amount(Fake s) { return s.amount(); }
        @Override public List<Fake> contents(Fake s) { return s.contents(); }
        @Override public Fake withContents(Fake s, List<Fake> c) { return new Fake(s.id(), s.amount(), new ArrayList<>(c)); }
        @Override public Fake fresh(String id, int amount) { return Fake.of(id, amount); }   // = ItemService 로 새로 만든 것
    };

    static final Set<String> NEW = Set.of("iron_ore", "gold_ore", "orichalcum_ore", "ember_soul", "resonant_sinew", "clock_oil", "cinder_scale");
    static final Predicate<String> ALL = NEW::contains;

    @Test
    void mapMatchesTheContract() {
        Params conv = Mat036.json("materials.json").sub("conversion");
        Params map = conv.sub("map");
        assertEquals(map.keys().size(), ItemMigration036.MAP.size());
        for (String k : map.keys()) assertEquals(map.str(k), ItemMigration036.MAP.get(k), k);
        Params pre = conv.sub("pre_release");
        for (String k : pre.keys()) assertEquals(pre.str(k), ItemMigration036.PRE_RELEASE.get(k), k);
        for (String to : ItemMigration036.MAP.values()) assertTrue(Mat036.content().item(to) != null, to + " 는 content 에 있어야 함");
    }

    @Test
    void oneToOneKeepsAmountAndMergesWithFreshItems() {
        Fake a = ItemMigration036.convert(Fake.of("slag_ingot", 17), ACCESS, ALL);
        Fake b = ItemMigration036.convert(Fake.of("rime_crystal", 5), ACCESS, ALL);
        assertEquals(Fake.of("gold_ore", 17), a);
        assertEquals(Fake.of("gold_ore", 5), b);
        // 같은 새 id 끼리, 그리고 원래 있던 광석과 똑같은 모양 (isSimilar → 겹쳐짐)
        assertEquals(ACCESS.fresh("gold_ore", 1).id(), a.id());
        assertEquals(new Fake(a.id(), 1, a.contents()), new Fake(b.id(), 1, b.contents()));
        assertEquals(Fake.of("ember_soul", 3), ItemMigration036.convert(Fake.of("ember_shard", 3), ACCESS, ALL));
        assertEquals(Fake.of("cinder_scale", 2), ItemMigration036.convert(Fake.of("cinder_hide", 2), ACCESS, ALL), "배포 전 잿불 가죽");
    }

    @Test
    void unknownAndVanillaItemsAreUntouched() {
        Fake moss = Fake.of("moss_fiber", 9);
        assertSame(moss, ItemMigration036.convert(moss, ACCESS, ALL));
        Fake vanilla = Fake.of(null, 64);
        assertSame(vanilla, ItemMigration036.convert(vanilla, ACCESS, ALL));
        Fake weird = Fake.of("something_else", 1);
        assertSame(weird, ItemMigration036.convert(weird, ACCESS, ALL));
        assertNull(ItemMigration036.convert(null, ACCESS, ALL));
    }

    @Test
    void shulkersAndBundlesAreConvertedInside() {
        Fake bundle = new Fake(null, 1, List.of(Fake.of("mainspring", 4), Fake.of("moss_fiber", 2)));
        Fake shulker = new Fake(null, 1, Arrays.asList(Fake.of("rusted_iron", 30), null, bundle, Fake.of("prism_dust", 1)));
        Fake out = ItemMigration036.convert(shulker, ACCESS, ALL);
        assertEquals(Fake.of("iron_ore", 30), out.contents().get(0));
        assertNull(out.contents().get(1));
        assertEquals(List.of(Fake.of("clock_oil", 4), Fake.of("moss_fiber", 2)), out.contents().get(2).contents());
        assertEquals(Fake.of("resonant_sinew", 1), out.contents().get(3));
        Fake clean = new Fake(null, 1, List.of(Fake.of("moss_fiber", 2)));
        assertSame(clean, ItemMigration036.convert(clean, ACCESS, ALL), "바꿀 것이 없으면 그대로");
    }

    @Test
    void missingNewIdsMeansNoChange() {
        Predicate<String> none = id -> false;
        Fake old = Fake.of("brass_gear", 3);
        assertSame(old, ItemMigration036.convert(old, ACCESS, none));
        assertEquals(List.of("iron_ore", "gold_ore", "ember_soul", "resonant_sinew", "orichalcum_ore", "clock_oil", "cinder_scale"),
                ItemMigration036.missingTargets(none));
        assertEquals(List.of(), ItemMigration036.missingTargets(ALL));
        // 하나만 없으면 그것만 그대로
        Predicate<String> noGold = id -> ALL.test(id) && !id.equals("gold_ore");
        assertEquals("slag_ingot", ItemMigration036.convert(Fake.of("slag_ingot", 1), ACCESS, noGold).id());
        assertEquals("iron_ore", ItemMigration036.convert(Fake.of("rusted_iron", 1), ACCESS, noGold).id());
    }

    @Test
    void twiceIsTheSameAsOnce() {
        Fake[] slots = {Fake.of("rusted_iron", 8), Fake.of("amethyst_shard", 2), null, Fake.of("spider_silk", 3)};
        int n = ItemMigration036.convertAll(slots, ACCESS, ALL);
        assertEquals(2, n);
        List<Fake> once = new ArrayList<>(Arrays.asList(slots));
        assertEquals(0, ItemMigration036.convertAll(slots, ACCESS, ALL));
        assertEquals(once, Arrays.asList(slots));
    }
}
