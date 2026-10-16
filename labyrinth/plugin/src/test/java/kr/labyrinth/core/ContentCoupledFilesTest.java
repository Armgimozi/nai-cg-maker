package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * jar 만 바꾸는 판올림에서 직접 고친 content 파일 하나만 옛 판으로 남고 나머지가 새 판이 되면(서로 아이템 id 를 주고받음),
 * 켤 때 [중요] 줄로 크게 알린다 — 특히 items.yml 이 옛 판이면 새 장비 몇 개가 빠지는지.
 */
class ContentCoupledFilesTest {

    @Test
    void oldItemsWithNewLootIsLoud() {
        List<String> w = ContentLoader.coupledWarnings(List.of("items.yml"), List.of("loot.yml", "recipes.yml", "enhance.yml", "mobs.yml"), 114);
        String all = String.join("\n", w);
        assertTrue(all.contains("[중요] content/items.yml 이 옛 판이라 새 장비 114개가 빠집니다"), all);
        assertTrue(all.contains("loot.yml·recipes.yml·enhance.yml") && !all.contains("mobs.yml"), all);
        assertTrue(all.contains("/labadmin reload"), all);
    }

    @Test
    void itemsCountUnknownOrZeroStillWarns() {
        String zero = String.join("\n", ContentLoader.coupledWarnings(List.of("items.yml"), List.of("loot.yml"), 0));
        assertTrue(zero.contains("[중요] content/items.yml 이 옛 판이라 새 판에서 바뀐 장비 값이 빠질 수 있습니다"), zero);
        String unknown = String.join("\n", ContentLoader.coupledWarnings(List.of("items.yml"), List.of("loot.yml"), -1));
        assertTrue(unknown.contains("새 장비가 빠질 수 있습니다"), unknown);
    }

    @Test
    void otherOldCoupledFileAlsoWarns() {
        String all = String.join("\n", ContentLoader.coupledWarnings(List.of("loot.yml"), List.of("items.yml"), -1));
        assertTrue(all.contains("[중요] content/loot.yml 이(가) 옛 판이고 items.yml"), all);
    }

    @Test
    void quietWhenNotMixed() {
        assertEquals(List.of(), ContentLoader.coupledWarnings(List.of(), List.of("items.yml", "loot.yml"), -1), "모두 새 판");
        assertEquals(List.of(), ContentLoader.coupledWarnings(List.of("items.yml", "loot.yml", "recipes.yml", "enhance.yml", "npcs.yml"),
                List.of("mobs.yml"), 5), "서로 기대는 파일이 모두 옛 판이면 서로는 맞다");
        assertEquals(List.of(), ContentLoader.coupledWarnings(List.of("titles.yml"), List.of("items.yml"), -1), "따로 노는 파일");
    }

    @Test
    void countsItemsOnlyInTheNewFile() throws Exception {
        byte[] bundled = Files.readAllBytes(Path.of("src/main/resources/content/items.yml"));
        String old = "version: 1\nitems:\n  rusty_sword:\n    name: \"녹슨 검\"\n  foo_old:\n    name: x\n";
        int n = ContentLoader.missingItemIds(bundled, old.getBytes(StandardCharsets.UTF_8));
        int total = org.bukkit.configuration.file.YamlConfiguration.loadConfiguration(
                Path.of("src/main/resources/content/items.yml").toFile()).getConfigurationSection("items").getKeys(false).size();
        boolean hasRusty = new String(bundled, StandardCharsets.UTF_8).contains("\n  rusty_sword:");
        assertEquals(total - (hasRusty ? 1 : 0), n);
        assertEquals(0, ContentLoader.missingItemIds(bundled, bundled));
        assertEquals(-1, ContentLoader.missingItemIds("nope: [".getBytes(StandardCharsets.UTF_8), bundled));
    }
}
