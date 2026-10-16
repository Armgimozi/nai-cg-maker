package kr.labyrinth.content;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** 0.3.6 뼈대: ItemType.TOOL · ToolSpec (tier 규칙·속도) · items.yml mine_level/mine_kind/tool 읽기. */
class ToolSpecTest {

    @Test
    void tierRuleAndSpeed() {
        ToolSpec t = ToolSpec.parse(Params.of(Map.of("kind", "pickaxe", "tier", 3, "speed", Map.of("1", 1.4, "2", 1.4, "3", 1.4), "bonus", 0.04)));
        assertNotNull(t);
        assertTrue(t.isPickaxe());
        assertTrue(t.canMine(1) && t.canMine(3));
        assertFalse(t.canMine(4), "광석 tier > 곡괭이 tier 면 못 캠");
        assertFalse(t.canMine(0));
        assertEquals(0.0, t.speedFor(4));
        assertEquals(2.5 / 1.4, t.seconds(2.5, 1), 1e-9);
        assertTrue(Double.isInfinite(t.seconds(3.7, 4)));
        assertEquals(0.04, t.bonus(), 1e-9);
    }

    @Test
    void scalarSpeedAndLegacyMineTier() {
        ToolSpec t = ToolSpec.parse(Params.of(Map.of("mine_tier", 2, "speed", 1.25)));
        assertEquals(2, t.tier());
        assertEquals(1.25, t.speedFor(1), 1e-9);
        assertEquals(1.25, t.speedFor(2), 1e-9);
        assertNull(ToolSpec.parse(Params.EMPTY));
        assertEquals(1.0, ToolSpec.parse(Params.of(Map.of("tier", 1))).speedFor(1), 1e-9, "표에 없으면 1");
    }

    @Test
    void itemsYmlToolAndMineFields() {
        Map<String, Object> items = new LinkedHashMap<>();
        items.put("copper_pickaxe", Map.of("name", "구리 곡괭이", "type", "tool", "rarity", "common",
                "tool", Map.of("kind", "pickaxe", "tier", 1, "speed", Map.of("1", 1.0), "bonus", 0.0)));
        items.put("copper_ore", Map.of("name", "구리 광석", "type", "material", "rarity", "common", "mine_level", 1, "mine_kind", "ore"));
        items.put("broken_tool", Map.of("name", "x", "type", "tool"));
        items.put("bad_kind", Map.of("name", "y", "type", "material", "mine_kind", "rock"));
        ContentParser p = new ContentParser();
        Content c = p.parse(Map.of("items.yml", Map.of("items", items)));
        ItemDef pick = c.item("copper_pickaxe");
        assertEquals(ItemType.TOOL, pick.type());
        assertFalse(pick.isGear(), "도구는 장비가 아님");
        assertTrue(pick.isTool());
        assertEquals(1, pick.tool().tier());
        ItemDef ore = c.item("copper_ore");
        assertEquals(1, ore.mineLevel());
        assertEquals(MineKind.ORE, ore.mineKind());
        assertTrue(ore.isMineMaterial());
        assertNull(ore.tool());
        List<String> probs = p.problems();
        assertTrue(probs.stream().anyMatch(s -> s.contains("broken_tool") && s.contains("tool")), probs::toString);
        assertTrue(probs.stream().anyMatch(s -> s.contains("bad_kind") && s.contains("mine_kind")), probs::toString);
        assertTrue(c.mine().isEmpty(), "mine.yml 이 없으면 광산 없음");
    }
}
