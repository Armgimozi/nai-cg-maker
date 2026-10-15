package kr.labyrinth.classes;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.core.Settings;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 시작 꾸러미: 넉넉한 기본값, 예전 판 목록 자동 갱신, 이미 받은 사람에게는 차이만. */
class StarterKitTest {

    @Test
    void defaultsAreGenerous() {
        Settings s = new Settings(new YamlConfiguration());
        assertEquals(Settings.DEFAULT_STARTER_KIT, s.starterKit());
        assertEquals(300, s.starterGold());
        Map<String, Integer> all = StarterKit.owed(s.starterKit(), s.starterGold(), Map.of());
        assertEquals(10, all.get("minor_healing_potion"));
        assertEquals(5, all.get("minor_mana_potion"));
        assertEquals(2, all.get("return_scroll"));
        assertEquals(16, all.get("minecraft:bread"));
        assertEquals(300, all.get(StarterKit.GOLD));
    }

    @Test
    void bundledConfigMatchesCodeDefaults() {
        Settings s = new Settings(YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml")));
        assertEquals(Settings.DEFAULT_STARTER_KIT, s.starterKit());
        assertEquals(Settings.DEFAULT_STARTER_GOLD, s.starterGold());
    }

    @Test
    void legacyConfigListIsUpgraded() {
        // 0.3.2 가 서버에 복사해 둔 그대로의 목록 (골드 키 없음) → 새 기본값 + 골드 300
        YamlConfiguration y = new YamlConfiguration();
        y.set("starter_kit.enabled", true);
        y.set("starter_kit.items", List.of(Map.of("item", "novice_cap", "amount", 1), Map.of("item", "novice_tunic", "amount", 1),
                Map.of("item", "novice_trousers", "amount", 1), Map.of("item", "novice_boots", "amount", 1),
                Map.of("item", "minor_healing_potion", "amount", 5)));
        Settings s = new Settings(y);
        assertEquals(Settings.DEFAULT_STARTER_KIT, s.starterKit());
        assertEquals(300, s.starterGold());
        // 직접 고친 목록은 그대로
        y.set("starter_kit.items", List.of(Map.of("item", "minor_healing_potion", "amount", 3)));
        assertEquals(List.of(new Settings.KitItem("minor_healing_potion", 3)), new Settings(y).starterKit());
        y.set("starter_kit.enabled", false);
        assertTrue(new Settings(y).starterKit().isEmpty());
        assertEquals(0, new Settings(y).starterGold());
    }

    @Test
    void oldKitHoldersGetOnlyTheDifference() {
        Map<String, Object> ext = new HashMap<>();
        ext.put(StarterKit.LEGACY_FLAG, true);
        Map<String, Integer> got = StarterKit.received(ext);
        assertEquals(5, got.get("minor_healing_potion"));
        assertEquals(1, got.get("novice_cap"));
        Map<String, Integer> owed = StarterKit.owed(Settings.DEFAULT_STARTER_KIT, 300, got);
        assertEquals(5, owed.get("minor_healing_potion"));
        assertEquals(5, owed.get("minor_mana_potion"));
        assertEquals(300, owed.get(StarterKit.GOLD));
        assertTrue(!owed.containsKey("novice_cap"), "방어구는 다시 주지 않음");
        // 기록하면 더 줄 것이 없다
        ext.put(StarterKit.GOT, StarterKit.record(got, owed));
        assertTrue(StarterKit.owed(Settings.DEFAULT_STARTER_KIT, 300, StarterKit.received(ext)).isEmpty());
    }

    @Test
    void recordSurvivesOddIdsAndBrokenLines() {
        Map<String, Object> ext = new HashMap<>();
        ext.put(StarterKit.GOT, List.of("minecraft:bread*16", "$gold*300", "broken", "x*notanumber"));
        Map<String, Integer> got = StarterKit.received(ext);
        assertEquals(16, got.get("minecraft:bread"));
        assertEquals(300, got.get(StarterKit.GOLD));
        assertEquals(2, got.size());
    }
}
