package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.ui.menus.CodexMenu;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6 통합 접착 (lead): 툴팁 획득처 '광산'·'제련소' · 곡괭이 줄 · 도감 광산·제련소 묶음 (층 번호 없음) ·
 * 광산 메뉴 칸 = glyphs.yml menus.* · 제련소 탭 이름.
 */
class Glue036Test {

    static final Pattern LABEL = Pattern.compile("(Lv\\s*\\d|레벨|\\d+\\s*층|층\\s*\\d|지하\\s*\\d|단계|티어|tier\\s*\\d)", Pattern.CASE_INSENSITIVE);

    @Test
    void tooltipSourceLineNamesMineAndSmelter() {
        Content c = Mat036.content();
        String ore = Text.strip(ItemTooltip.sourceLine(c, c.item("copper_ore")));
        assertTrue(ore.contains("광산"), ore);
        assertFalse(ore.contains("mine"), ore);
        String ingot = Text.strip(ItemTooltip.sourceLine(c, c.item("copper_ingot")));
        assertTrue(ingot.contains("제련소"), ingot);
        assertFalse(ingot.contains("smelt"), ingot);
    }

    @Test
    void pickaxeTooltipHasToolLinesWithoutLevelLabels() {
        Content c = Mat036.content();
        for (String metal : Mat036.METALS) {
            ItemDef d = c.item(metal + "_pickaxe");
            List<String> lines = ItemTooltip.toolLines(c, d).stream().map(Text::strip).toList();
            assertFalse(lines.isEmpty(), metal);
            assertTrue(lines.get(0).contains("구리"), lines.toString());
            for (String l : lines) assertFalse(LABEL.matcher(l).find(), metal + ": " + l);
        }
        String copper = String.join(" ", ItemTooltip.toolLines(c, c.item("copper_pickaxe")).stream().map(Text::strip).toList());
        assertTrue(copper.contains("구리·철") && copper.contains("철 광석 4초 (느림)"), "구리 곡괭이로 철을 느리게 (0.3.6.1): " + copper);
        assertFalse(copper.contains("은"), "구리 곡괭이로 은은 못 캔다: " + copper);
        String ori = String.join(" ", ItemTooltip.toolLines(c, c.item("orichalcum_pickaxe")).stream().map(Text::strip).toList());
        assertTrue(ori.contains("오리하르콘"), ori);
    }

    @Test
    void codexHasMineAndSmelterGroupsWithoutFloorNumbers() {
        Content c = Mat036.content();
        Map<String, List<String>> src = CodexMenu.buildSources(c);
        for (String metal : Mat036.METALS) {
            List<String> ore = src.getOrDefault(metal + "_ore", List.of()).stream().map(Text::strip).toList();
            assertTrue(ore.stream().anyMatch(l -> l.startsWith("광산") && l.contains("많이 나는 곳")), metal + "_ore: " + ore);
            for (String l : ore) assertFalse(LABEL.matcher(l).find(), metal + "_ore: " + l);
            List<String> ingot = src.getOrDefault(metal + "_ingot", List.of()).stream().map(Text::strip).toList();
            assertTrue(ingot.stream().anyMatch(l -> l.startsWith("제련소")), metal + "_ingot: " + ingot);
            assertFalse(ingot.stream().anyMatch(l -> l.startsWith("대장간")), metal + "_ingot: " + ingot);
        }
        for (String gem : Mat036.GEMS) {
            List<String> g = src.getOrDefault(gem, List.of()).stream().map(Text::strip).toList();
            assertTrue(g.stream().anyMatch(l -> l.startsWith("광산")), gem + ": " + g);
        }
    }

    @Test
    void mineMenuSlotsFollowGlyphs() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/content/glyphs.yml"));
        assertEquals(List.of(4, 13, 22, 31, 40, 49), y.getIntegerList("menus.mine_lift.slots.levels"));
        assertEquals(List.of(2, 4, 6), y.getIntegerList("menus.smelter.slots.tabs"));
        assertEquals(List.of("smelt", "carve", "pickaxe"), y.getStringList("menus.smelter.slots.tab_order"));
        assertEquals(List.of(1, 2, 3, 5, 6, 7), y.getIntegerList("menus.mine_office.slots.tabs"));
        assertEquals("gui_setup_village", y.getString("menus.setup_village.glyph"));
        assertEquals(40, y.getInt("menus.setup_village.slots.entrance"));
        assertTrue(y.isConfigurationSection("glyphs.gui_setup_village"));
    }
}
