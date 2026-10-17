package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.rules.PlotRules.Act;
import kr.labyrinth.homes.rules.PlotRules.Verdict;
import kr.labyrinth.homes.rules.PlotRules.Where;
import kr.labyrinth.village.VillageService;
import org.bukkit.Material;
import org.junit.jupiter.api.Test;

/** 권한 표 (plan §9) 그대로 · 남의 집은 기본 막음 + 허용 목록 (R4) · deny_use (R21) · 26.3 블록. */
class PlotRulesTest {

    private static final List<String> DENY_USE = HomesConfig.DEFAULT.denyUse();
    private static final List<String> DENY_PLACE = HomesConfig.DEFAULT.denyPlace();

    @Test
    void planTableHolds() {
        for (PlotRules.Case c : PlotRules.table()) {
            assertEquals(c.expect(), PlotRules.decide(c.act(), c.where(), c.bypass(), c.grace()), c.toString());
        }
        int[] r = PlotRules.selfCheck();
        assertEquals(r[1], r[0]);
        assertTrue(r[1] >= 50, "표가 충분히 큼: " + r[1]);
    }

    @Test
    void everyCombinationDecides() {
        for (Act a : Act.values()) for (Where w : Where.values()) for (boolean b : new boolean[] {false, true}) for (boolean g : new boolean[] {false, true}) {
            assertNotNull(PlotRules.decide(a, w, b, g));
        }
    }

    @Test
    void creativeAdminBypassesAllButTrample() {
        for (Act a : Act.values()) for (Where w : Where.values()) {
            Verdict v = PlotRules.decide(a, w, true, false);
            if (a == Act.TRAMPLE) assertEquals(w == Where.WILD_OPEN ? Verdict.PASS : Verdict.DENY, v);
            else assertEquals(Verdict.ALLOW, v, a + " @ " + w);
        }
    }

    @Test
    void strangersCanOnlyStepOnPlatesAndUseEnderChests() {
        for (Act a : Act.values()) {
            Verdict v = PlotRules.decide(a, Where.STRANGER, false, false);
            boolean allowed = a == Act.PRESSURE || a == Act.ENDER_CHEST;
            assertEquals(allowed ? Verdict.ALLOW : Verdict.DENY, v, a.toString());
        }
    }

    @Test
    void guestsGetDoorsWorkstationsBell() {
        for (Act a : Act.values()) {
            Verdict v = PlotRules.decide(a, Where.GUEST, false, false);
            boolean allowed = a == Act.PRESSURE || a == Act.ENDER_CHEST || a == Act.DOOR || a == Act.WORKSTATION;
            assertEquals(allowed ? Verdict.ALLOW : Verdict.DENY, v, a.toString());
        }
        assertEquals(Act.WORKSTATION, PlotRules.blockUse("bell", false));
        for (String s : List.of("crafting_table", "stonecutter", "loom", "cartography_table", "smithing_table", "grindstone")) {
            assertEquals(Act.WORKSTATION, PlotRules.blockUse(s, false), s);
        }
    }

    @Test
    void ownPlotAllowsAllButBannedThings() {
        for (Act a : Act.values()) {
            Verdict v = PlotRules.decide(a, Where.OWN, false, false);
            boolean denied = a == Act.PLACE_BANNED || a == Act.USE_BANNED || a == Act.PRIME || a == Act.TRAMPLE || a == Act.FIRE;
            assertEquals(denied ? Verdict.DENY : Verdict.ALLOW, v, a.toString());
        }
    }

    @Test
    void protectedBoxesLeaveVillageHandlersAlone() {
        // 마을 핸들러가 있는 것은 PASS (마을 글 한 번) · 없는 것은 우리가 막음 (R4)
        for (Act a : List.of(Act.BREAK, Act.PLACE, Act.BUCKET, Act.HANGING, Act.TOOL, Act.IGNITE, Act.CONTAINER, Act.OTHER_USE, Act.DOOR, Act.BED)) {
            assertEquals(Verdict.PASS, PlotRules.decide(a, Where.PROTECTED, false, false), a.toString());
        }
        for (Act a : List.of(Act.ARMOR_STAND, Act.VEHICLE, Act.SIGN, Act.ENTITY_GRAB, Act.PRIME)) {
            assertEquals(Verdict.DENY, PlotRules.decide(a, Where.PROTECTED, false, false), a.toString());
        }
    }

    @Test
    void lockedWildKeepsLegacyUse() {
        for (Act a : List.of(Act.CONTAINER, Act.DOOR, Act.OTHER_USE, Act.BED, Act.ENDER_CHEST, Act.WORKSTATION, Act.PRESSURE)) {
            assertEquals(Verdict.ALLOW, PlotRules.decide(a, Where.WILD_LOCKED, false, false), "옛 건물 " + a);
        }
        for (Act a : List.of(Act.BREAK, Act.PLACE, Act.BUCKET, Act.TOOL, Act.HANGING, Act.ARMOR_STAND, Act.VEHICLE, Act.SIGN, Act.FIRE, Act.IGNITE)) {
            assertEquals(Verdict.DENY, PlotRules.decide(a, Where.WILD_LOCKED, false, false), a.toString());
        }
        assertEquals(Verdict.ALLOW, PlotRules.decide(Act.BREAK, Where.WILD_LOCKED, false, true), "이사 기간 사람 블록");
        assertEquals(Verdict.DENY, PlotRules.decide(Act.PLACE, Where.WILD_LOCKED, false, true), "이사 기간에도 놓기는 막힘");
        assertEquals(Verdict.PASS, PlotRules.decide(Act.ANIMAL, Where.WILD_LOCKED, false, false), "들판 동물 그대로");
    }

    @Test
    void openWildIsVanillaExceptPrimeAndTrample() {
        for (Act a : Act.values()) {
            Verdict v = PlotRules.decide(a, Where.WILD_OPEN, false, false);
            assertEquals(a == Act.PRIME ? Verdict.DENY : Verdict.PASS, v, a.toString());
        }
    }

    @Test
    void blockUseDefaultsToDeny() {
        // R4: 화분·가마솥·퇴비통·모닥불·케이크·초·소리 블록·중계기·비교기·벌통·조각상·버튼·레버 = 그 밖 우클릭 → 손님 막힘
        for (String s : List.of("potted_poppy", "flower_pot", "cauldron", "water_cauldron", "composter", "campfire", "cake", "candle", "note_block",
                "repeater", "comparator", "beehive", "copper_golem_statue", "oxidized_copper_golem_statue", "stone_button", "lever", "daylight_detector",
                "oak_sign", "anvil", "enchanting_table", "beacon", "conduit", "dragon_egg", "redstone_wire")) {
            Act a = PlotRules.blockUse(s, false);
            assertEquals(Act.OTHER_USE, a, s);
            assertEquals(Verdict.DENY, PlotRules.decide(a, Where.GUEST, false, false), s);
        }
        // 상자류는 BlockState instanceof InventoryHolder 로 (선반·구리 상자·제작기·발사기 포함)
        for (String s : List.of("oak_shelf", "pale_oak_shelf", "copper_chest", "waxed_oxidized_copper_chest", "crafter", "dispenser", "barrel",
                "decorated_pot", "chiseled_bookshelf", "lectern", "jukebox", "hopper", "brewing_stand", "blast_furnace")) {
            assertEquals(Act.CONTAINER, PlotRules.blockUse(s, true), s);
        }
        assertEquals(Act.ENDER_CHEST, PlotRules.blockUse("ender_chest", false));
        assertEquals(Act.PRIME, PlotRules.blockUse("respawn_anchor", false));
        for (String s : List.of("oak_door", "iron_trapdoor", "spruce_fence_gate", "copper_door", "bamboo_trapdoor")) assertEquals(Act.DOOR, PlotRules.blockUse(s, false), s);
        assertEquals(Act.BED, PlotRules.blockUse("red_bed", false));
    }

    @Test
    void shelvesAndCopperChestsExistIn263() {
        int shelves = 0, copperChests = 0;
        for (Material m : Material.values()) {
            if (m.name().startsWith("LEGACY_")) continue;
            if (m.name().endsWith("_SHELF") && !m.name().equals("BOOKSHELF")) shelves++;
            if (m.name().endsWith("COPPER_CHEST")) copperChests++;
        }
        assertTrue(shelves >= 13, "선반 13종 이상: " + shelves);
        assertEquals(8, copperChests, "구리 상자 8종");
    }

    @Test
    void physicalSteps() {
        assertEquals(Act.TRAMPLE, PlotRules.physical("farmland"));
        assertEquals(Act.TRAMPLE, PlotRules.physical("TURTLE_EGG"));
        assertEquals(Act.PRESSURE, PlotRules.physical("oak_pressure_plate"));
        assertEquals(Act.PRESSURE, PlotRules.physical("tripwire"));
    }

    @Test
    void itemUse() {
        // R21: 용암 양동이·화염구는 쓰기에서 막음 (deny_place 가 아님)
        assertEquals(Act.USE_BANNED, item(Material.LAVA_BUCKET, "stone"));
        assertEquals(Act.USE_BANNED, item(Material.FIRE_CHARGE, "campfire"));
        assertEquals(Act.IGNITE, item(Material.FLINT_AND_STEEL, "campfire"));
        assertEquals(Act.IGNITE, item(Material.FLINT_AND_STEEL, "white_candle"));
        assertEquals(Act.IGNITE, item(Material.FLINT_AND_STEEL, "candle_cake"));
        assertEquals(Act.FIRE, item(Material.FLINT_AND_STEEL, "obsidian"), "네더를 막으면 (0.3.7 기본) 흑요석에 불 = FIRE");
        assertEquals(Act.IGNITE, PlotRules.itemUse("FLINT_AND_STEEL", "obsidian", true, DENY_USE, DENY_PLACE, true), "wild.nether: true 면 차원문 틀");
        assertEquals(Act.IGNITE, PlotRules.itemUse("FLINT_AND_STEEL", "campfire", true, DENY_USE, DENY_PLACE, true));
        assertEquals(Act.FIRE, PlotRules.itemUse("FLINT_AND_STEEL", "oak_planks", true, DENY_USE, DENY_PLACE, true));
        assertFalse(PlotRules.ignitable("crying_obsidian", true), "우는 흑요석은 틀이 아님");
        assertEquals(Act.FIRE, item(Material.FLINT_AND_STEEL, "oak_planks"));
        assertEquals(Act.PLACE_BANNED, item(Material.TNT_MINECART, "rail"));
        assertEquals(Act.PLACE_BANNED, item(Material.END_CRYSTAL, "obsidian"));
        assertEquals(Act.ARMOR_STAND, item(Material.ARMOR_STAND, "stone"));
        assertEquals(Act.HANGING, item(Material.LEAD, "oak_fence"), "끈 매듭");
        assertNull(item(Material.LEAD, "stone"));
        assertNull(item(Material.MILK_BUCKET, "stone"), "우유 마시기는 그대로");
        assertEquals(Act.TOOL, item(Material.POTION, "dirt"), "물병 → 진흙");
        assertNull(item(Material.POTION, "stone"), "물약 마시기는 그대로");
        assertEquals(Act.TOOL, item(Material.BONE_MEAL, "grass_block"));
        assertEquals(Act.TOOL, item(Material.STONE_HOE, "dirt"));
        assertEquals(Act.TOOL, item(Material.WATER_BUCKET, "stone"));
        assertEquals(Act.TOOL, item(Material.HONEYCOMB, "oak_sign"));
        assertNull(item(Material.OAK_PLANKS, "stone"), "블록 놓기는 BlockPlaceEvent 가 봄");
        assertNull(item(Material.BREAD, "stone"));
    }

    private static Act item(Material m, String clicked) {
        return PlotRules.itemUse(m.name(), clicked, VillageService.changesBlocks(m), DENY_USE, DENY_PLACE, false); // 네더 막음 (기본)
    }

    @Test
    void keyStripsNamespaceAndState() {
        assertEquals("oak_door", PlotRules.key("minecraft:OAK_DOOR[half=upper]"));
        assertEquals("", PlotRules.key(null));
    }
}
