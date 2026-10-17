package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.bukkit.Material;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 관리인 자재 목록 (0.3.7, review R5 · R16): 387가지 · 돌 도끼 없음 · 금지 0 (금속·녹이면 조각이 나오는 도구·갑옷·무기·폭발물·레드스톤 장치 …) ·
 * 도구는 건축 도구 허용 목록만 · 블록 id 는 blockdata.json 에 · 값 규칙 (기본 블록 0.25~1G, 원목 ≥ 판자 4, 계단 ≥ 1.5배, 반블록 ≥ 0.5배) ·
 * 값 배율 0.1 아래 자름 · 환불.
 */
class HousingCatalogTest {

    static HousingCatalog cat;
    static List<HousingCatalog.Entry> all = new ArrayList<>();
    static Map<String, HousingCatalog.Entry> byId = new HashMap<>();
    /** 블록이 아닌데 파는 것 (생성기 ITEMS 와 같음). */
    static final Set<String> ITEMS = Set.of("item_frame", "painting", "armor_stand", "water_bucket", "wheat_seeds", "carrot", "potato",
            "beetroot_seeds", "pumpkin_seeds", "melon_seeds", "sweet_berries", "bone_meal", "wooden_hoe", "stone_hoe", "stone_shovel",
            "stone_pickaxe", "shears", "flint_and_steel");

    @BeforeAll
    static void load() throws Exception {
        cat = HousingCatalog.parse(Files.readString(Path.of("src/main/resources/content/housing.yml")), id -> Material.matchMaterial(id) != null);
        for (HousingCatalog.Tab t : cat.tabs()) for (HousingCatalog.Entry e : t.items()) {
            all.add(e);
            byId.put(e.id(), e);
        }
    }

    @Test
    void sizeAndTabs() {
        assertTrue(cat.problems().isEmpty(), () -> String.join("\n", cat.problems()));
        assertEquals(387, cat.size(), "설계 386 − 돌 도끼 (R5) + 흑요석·부싯돌 (0.3.7 fix, 네더 차원문)");
        assertEquals(387, cat.declared());
        assertEquals(9, cat.tabs().size());
        assertEquals(0, cat.banned());
        assertEquals(0, cat.unknown());
        for (HousingCatalog.Tab t : cat.tabs()) assertFalse(t.items().isEmpty(), t.id());
        assertEquals(387, byId.size(), "id 가 겹치지 않음");
    }

    @Test
    void stoneAxeIsGoneAndToolsAreAllowListed() {
        assertNull(cat.find("stone_axe"), "돌 도끼는 무기 (R5)");
        assertEquals("무기", HousingCatalog.banReason("stone_axe"));
        assertEquals("무기", HousingCatalog.banReason("wooden_axe"));
        for (String t : HousingCatalog.TOOLS) {
            assertNotNull(cat.find(t), t);
            assertNull(HousingCatalog.banReason(t), t);
        }
        for (HousingCatalog.Entry e : all) {
            String i = e.id();
            boolean tool = i.endsWith("_pickaxe") || i.endsWith("_shovel") || i.endsWith("_hoe") || i.endsWith("_axe") || i.equals("shears");
            if (tool) assertTrue(HousingCatalog.TOOLS.contains(i), "도구는 허용 목록만: " + i);
        }
    }

    @Test
    void nothingBannedIsSold() {
        for (HousingCatalog.Entry e : all) {
            assertNull(HousingCatalog.banReason(e.id()), e.id());
            assertFalse(HousingCatalog.smeltsToNuggets(e.id()), "녹이면 조각이 나오는 것은 팔지 않음: " + e.id());
            assertFalse(e.id().contains("copper") || e.id().contains("gold") || e.id().contains("diamond") || e.id().contains("emerald")
                    || e.id().contains("netherite"), e.id());
        }
    }

    @Test
    void banRuleCatchesTheForbiddenList() {
        for (String id : List.of("iron_pickaxe", "iron_shovel", "golden_helmet", "chainmail_boots", "iron_horse_armor", "golden_horse_armor",
                "copper_chestplate", "copper_axe", "iron_spear")) {
            assertTrue(HousingCatalog.smeltsToNuggets(id), id);
            assertEquals("녹이면 조각이 나옴", HousingCatalog.banReason(id), id);
        }
        for (String id : List.of("iron_ingot", "iron_nugget", "raw_iron", "iron_ore", "deepslate_iron_ore", "iron_block", "gold_ingot", "gold_nugget",
                "raw_gold", "gold_block", "copper_ingot", "raw_copper", "copper_block", "cut_copper", "copper_lantern", "diamond", "diamond_block",
                "emerald", "emerald_ore", "netherite_scrap", "netherite_ingot", "ancient_debris",
                "wooden_sword", "stone_sword", "bow", "crossbow", "arrow", "trident", "mace", "leather_helmet", "turtle_helmet",
                "tnt", "tnt_minecart", "fire_charge", "lava_bucket",
                "piston", "sticky_piston", "dispenser", "dropper", "crafter", "observer", "rail", "powered_rail", "minecart",
                "redstone", "redstone_torch", "repeater", "comparator", "ender_pearl", "ender_chest", "shulker_box", "white_shulker_box",
                "beacon", "spawner", "cow_spawn_egg", "egg", "command_block", "lapis_lazuli", "lapis_block", "quartz", "quartz_block",
                "crying_obsidian", "anvil", "enchanting_table", "brewing_stand", "fishing_rod", "brush", "cod_bucket")) {
            assertNotNull(HousingCatalog.banReason(id), "팔면 안 됨: " + id);
        }
        // 쇠가 들어 있어도 되돌릴 길이 없는 것은 괜찮다 (R5)
        for (String id : List.of("iron_bars", "iron_chain", "lantern", "hopper", "cauldron", "water_bucket", "shears", "smithing_table",
                "stonecutter", "redstone_lamp", "obsidian", "flint_and_steel")) { // 흑요석·부싯돌 = 네더 차원문 (0.3.7 fix)
            assertNull(HousingCatalog.banReason(id), id);
            assertNotNull(cat.find(id), "목록에 있음: " + id);
        }
    }

    @Test
    void idsAreKnownBlocksOrListedItems() throws Exception {
        JsonObject blocks = JsonParser.parseString(Files.readString(Path.of("../tools/village/blockdata.json"))).getAsJsonObject()
                .getAsJsonObject("blocks");
        for (HousingCatalog.Entry e : all) {
            assertTrue(blocks.has(e.id()) || ITEMS.contains(e.id()), "blockdata.json 에 없는 블록: " + e.id());
            assertNotNull(Material.matchMaterial(e.id()), "Material 이 모름: " + e.id());
        }
    }

    @Test
    void priceRules() {
        for (HousingCatalog.Entry e : all) {
            assertTrue(e.bundle() >= 1 && e.bundle() <= 64, e.id());
            assertTrue(e.price() >= 1, e.id());
            if (e.tab().equals("basic") || e.tab().equals("color")) {
                assertTrue(e.unit() >= 0.25 - 1e-9 && e.unit() <= 1 + 1e-9, "한 칸 0.25~1G: " + e.id() + " " + e.unit());
            }
            String i = e.id();
            if (i.endsWith("_log") && !i.startsWith("stripped_")) {
                HousingCatalog.Entry planks = byId.get(i.substring(0, i.length() - 4) + "_planks");
                assertNotNull(planks, i);
                assertTrue(e.unit() + 1e-9 >= 4 * planks.unit(), "원목 ≥ 판자 4개: " + i);
            }
            HousingCatalog.Entry base = base(i);
            if (i.endsWith("_stairs") && base != null) assertTrue(e.unit() + 1e-9 >= 1.5 * base.unit(), "계단 ≥ 1.5배: " + i);
            if (i.endsWith("_slab") && base != null) assertTrue(e.unit() + 1e-9 >= 0.5 * base.unit(), "반블록 ≥ 0.5배: " + i);
        }
        // 낱개 값 (설계)
        assertEquals(5, byId.get("chest").price());
        assertEquals(40, byId.get("hopper").price());
        assertEquals(30, byId.get("water_bucket").price());
        assertEquals(20, byId.get("red_bed").price());
    }

    @Test
    void multiplierAndRefund() {
        HousingCatalog.Entry dirt = byId.get("dirt");
        assertEquals(16, HousingCatalog.price(dirt, 1.0));
        assertEquals(32, HousingCatalog.price(dirt, 2.0));
        assertEquals(2, HousingCatalog.price(dirt, 0.0), "배율 0.1 아래는 0.1 (R16)");
        assertEquals(1, HousingCatalog.price(byId.get("short_grass"), 0.1), "최소 1G");
        assertEquals(0, HousingCatalog.refund(80, 5, 16, 80));
        assertEquals(80, HousingCatalog.refund(80, 5, 16, 0));
        assertEquals(40, HousingCatalog.refund(80, 5, 16, 40));
        assertEquals(15, HousingCatalog.refund(16, 1, 64, 1), "준 몫은 올림해 받음 — 돌려주는 값이 낸 값을 넘지 않음");
    }

    @Test
    void notesNoLongerMentionDroppedFeatures() {
        for (HousingCatalog.Entry e : all) {
            assertFalse(e.note().contains("상자 수 한도"), e.id() + ": " + e.note());
            assertFalse(e.note().contains("화덕"), e.id() + ": " + e.note());
        }
    }

    @Test
    void generatorDataMatches() throws Exception {
        JsonObject data = JsonParser.parseString(Files.readString(Path.of("../tools/data/037/housing_catalog.json"))).getAsJsonObject();
        assertEquals(387, data.get("count").getAsInt());
        assertEquals(387, data.getAsJsonArray("catalog").size());
    }

    @Test
    void bannedLinesInTheFileAreSkipped() {
        String y = "version: 1\ncount: 3\ntabs:\n  - id: x\n    name: 시험\n    icon: chest\n    items:\n"
                + "      - {id: dirt, bundle: 64, price: 16}\n      - {id: tnt, bundle: 1, price: 5}\n      - {id: not_a_block, bundle: 1, price: 1}\n";
        HousingCatalog c = HousingCatalog.parse(y, id -> Material.matchMaterial(id) != null);
        assertEquals(1, c.size());
        assertEquals(1, c.banned());
        assertEquals(1, c.unknown());
        assertEquals(2, c.problems().size());
    }

    static HousingCatalog.Entry base(String i) {
        for (String suf : new String[] {"_stairs", "_slab", "_wall"}) {
            if (!i.endsWith(suf)) continue;
            String stem = i.substring(0, i.length() - suf.length());
            for (String c : new String[] {stem + "_planks", stem, stem + "s", stem.replace("brick", "bricks"), stem.replace("tile", "tiles")}) {
                if (byId.containsKey(c)) return byId.get(c);
            }
        }
        return null;
    }
}
