package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import kr.labyrinth.core.Settings;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 시작 꾸러미 (계약 §2.6): 새 기본값에 구리 곡괭이 · 0.3.5.1 기본 목록을 그대로 둔 서버도 새 기본값으로 · 직접 고친 목록은 그대로. */
class StarterKit0351Test {

    static Settings settings(String text) throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        return new Settings(y);
    }

    @Test
    void legacy0351ListBecomesTheNewDefault() throws Exception {
        Settings s = settings("""
                starter_kit:
                  enabled: true
                  gold: 100
                  items:
                    - {item: novice_cap, amount: 1}
                    - {item: novice_tunic, amount: 1}
                    - {item: novice_trousers, amount: 1}
                    - {item: novice_boots, amount: 1}
                    - {item: minor_healing_potion, amount: 10}
                    - {item: minor_mana_potion, amount: 5}
                    - {item: return_scroll, amount: 2}
                """);
        assertEquals(Settings.DEFAULT_STARTER_KIT, s.starterKit());
        assertTrue(s.starterKit().contains(new Settings.KitItem("copper_pickaxe", 1)));
        assertEquals(Settings.LEGACY_STARTER_KIT_0351.size() + 1, Settings.DEFAULT_STARTER_KIT.size());
    }

    @Test
    void customListIsKept() throws Exception {
        Settings s = settings("""
                starter_kit:
                  items:
                    - {item: novice_cap, amount: 1}
                    - {item: return_scroll, amount: 5}
                """);
        assertEquals(2, s.starterKit().size());
    }

    @Test
    void jarConfigIsTheNewDefault() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertEquals(Settings.DEFAULT_STARTER_KIT, new Settings(y).starterKit());
        assertNotNull(Mat036.content().item("copper_pickaxe"));
        for (Settings.KitItem k : Settings.DEFAULT_STARTER_KIT) assertNotNull(Mat036.content().item(k.item()), k.item());
    }
}
