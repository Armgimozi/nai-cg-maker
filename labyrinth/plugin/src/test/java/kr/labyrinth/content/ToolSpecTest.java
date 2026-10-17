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
        assertTrue(t.canMine(4), "0.3.6.1: 한 단계 위까지 캔다");
        assertTrue(t.isSlow(4) && !t.isSlow(3), "한 단계 위만 느림");
        assertFalse(t.canMine(5), "두 단계 위는 못 캠");
        assertFalse(t.canMine(0));
        assertEquals(4, t.maxHardness());
        assertEquals(1.4 * ToolSpec.STRETCH_FALLBACK, t.speedFor(4), 1e-9, "표에 없으면 제 등급 × 0.5");
        assertEquals(0.0, t.speedFor(5));
        assertEquals(2.5 / 1.4, t.seconds(2.5, 1), 1e-9);
        assertTrue(Double.isInfinite(t.seconds(4.1, 5)));
        assertEquals(0.04, t.bonus(), 1e-9);
    }

    @Test
    void missingStretchSpeedUsesNextPickaxe() {
        // 경제 검토 (0.3.6.1): 손으로 고친 items.yml 에 한 단계 위 칸이 없으면, 제 곡괭이 × 0.5 (0.50) 이 아니라
        // 생성기·계약처럼 그 광석 제 곡괭이(철) 빠르기 × 0.5 (0.8) — 구리 곡괭이로 철 광석 3.6초 ÷ 0.8 = 4.5초 (0.3.7)
        Map<String, Object> items = new LinkedHashMap<>();
        items.put("copper_pickaxe", Map.of("name", "구리 곡괭이", "type", "tool", "rarity", "common",
                "tool", Map.of("kind", "pickaxe", "tier", 1, "speed", Map.of("1", 1.0), "bonus", 0.0)));
        items.put("iron_pickaxe", Map.of("name", "철 곡괭이", "type", "tool", "rarity", "common",
                "tool", Map.of("kind", "pickaxe", "tier", 2, "speed", Map.of("1", 1.6, "2", 1.6, "3", 1.25), "bonus", 0.02)));
        Content c = new ContentParser().parse(Map.of("items.yml", Map.of("items", items)));
        ToolSpec copper = c.item("copper_pickaxe").tool();
        assertEquals(0.8, copper.speedFor(2), 1e-9, "다음 곡괭이 빠르기 1.6 × 0.5");
        assertEquals(3.6 / 0.8, copper.seconds(3.6, 2), 1e-9);
        assertEquals(4.5, copper.seconds(3.6, 2), 1e-9);
        assertEquals(1.25, c.item("iron_pickaxe").tool().speedFor(3), 1e-9, "적힌 값은 그대로");
        assertEquals(Map.of(1, 1.0, 2, 1.6), ToolSpec.ownSpeeds(List.of(copper, c.item("iron_pickaxe").tool())));
        ToolSpec lone = ToolSpec.parse(Params.of(Map.of("tier", 3, "speed", Map.of("1", 1.4, "2", 1.4, "3", 1.4))));
        assertTrue(lone.withStretch(Map.of()) == lone, "다음 곡괭이를 모르면 그대로");
        assertTrue(copper.withStretch(Map.of(2, 5.0)) == copper, "이미 있으면 그대로");
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
