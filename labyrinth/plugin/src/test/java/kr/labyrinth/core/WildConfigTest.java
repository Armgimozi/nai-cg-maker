package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.core.Settings.Wild;
import kr.labyrinth.core.Settings.Wild.Spawns;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** config wild (0.3.5.1): 기본값 · 빠진 키 · 끄기 · 잘못된 값 경고 · jar 의 config.yml 과 코드 기본값이 같은가. */
class WildConfigTest {

    static YamlConfiguration yaml(String s) {
        YamlConfiguration y = new YamlConfiguration();
        try {
            y.loadFromString(s);
        } catch (InvalidConfigurationException e) {
            throw new IllegalStateException(e);
        }
        return y;
    }

    @Test
    void missingSectionMeansDefaultsOn() {
        // 예전 서버 config (wild 없음) 도 켜진다 — 서버 주인은 jar 만 바꾼다
        Settings s = new Settings(new YamlConfiguration());
        assertEquals(Wild.DEFAULT, s.wild());
        assertTrue(s.wild().border());
        assertEquals(30, s.wild().borderMargin());
        assertEquals(Spawns.ALL, s.wild().spawns());
        assertTrue(s.wildWarnings().isEmpty());
    }

    @Test
    void bundledConfigMatchesCodeDefaults() {
        Settings s = new Settings(YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml")));
        assertEquals(Wild.DEFAULT, s.wild());
        assertTrue(s.wildWarnings().isEmpty());
        YamlConfiguration raw = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertFalse(raw.contains("wild.nether_end"), "네더·엔드는 막지 않는다 (키 없음)");
        assertTrue(raw.getBoolean("village.block_mob_spawns"), "예전 마을 둘레 막기 키는 그대로");
    }

    @Test
    void readingDefaultsDoesNotWriteAnEmptySection() {
        // 서버 config 에 wild 가 없고 jar config 가 기본값일 때 (plugin.getConfig() 와 같은 모양) — 읽기만으로 'wild: {}' 가 생기면 안 됨
        YamlConfiguration file = yaml("village:\n  teleport_command: true\n");
        file.setDefaults(YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml")));
        Settings s = new Settings(file);
        assertEquals(Wild.DEFAULT, s.wild());
        assertFalse(file.contains("wild", true), "빈 wild 섹션이 생김");
        assertFalse(file.saveToString().contains("wild"));
        // 기본값 섹션을 쓰되, 파일에 적힌 값이 이긴다
        file.set("wild.spawns", "monsters");
        assertEquals(new Wild(true, 30, Spawns.MONSTERS), new Settings(file).wild());
    }

    @Test
    void partialKeysFallBackToDefaults() {
        Wild w = new Settings(yaml("wild:\n  spawns: monsters\n")).wild();
        assertEquals(new Wild(true, 30, Spawns.MONSTERS), w);
        assertEquals(new Wild(false, 30, Spawns.ALL), new Settings(yaml("wild:\n  border: false\n")).wild());
        assertEquals(new Wild(true, 12, Spawns.ALL), new Settings(yaml("wild:\n  border_margin: 12\n")).wild());
    }

    @Test
    void wildFalseTurnsEverythingOff() {
        Wild w = new Settings(yaml("wild: false\n")).wild();
        assertEquals(Wild.OFF, w);
        assertFalse(w.border());
        assertEquals(Spawns.NONE, w.spawns());
    }

    @Test
    void spawnValuesAndWarnings() {
        assertEquals(Spawns.NONE, new Settings(yaml("wild:\n  spawns: none\n")).wild().spawns());
        assertEquals(Spawns.NONE, new Settings(yaml("wild:\n  spawns: false\n")).wild().spawns(), "spawns: false = none");
        assertEquals(Spawns.ALL, new Settings(yaml("wild:\n  spawns: true\n")).wild().spawns());
        assertEquals(Spawns.MONSTERS, new Settings(yaml("wild:\n  spawns: Hostile\n")).wild().spawns());
        assertEquals(Spawns.ALL, new Settings(yaml("wild:\n  spawns: 전부\n")).wild().spawns());
        Settings bad = new Settings(yaml("wild:\n  spawns: animals\n"));
        assertEquals(Spawns.ALL, bad.wild().spawns(), "모르는 값 = 기본값");
        assertEquals(1, bad.wildWarnings().size());
        assertTrue(bad.wildWarnings().get(0).contains("animals"));
        assertNull(Spawns.parse(null));
        assertEquals("monsters", Spawns.MONSTERS.id());
    }

    @Test
    void marginIsClampedWithAWarning() {
        List<String> warn = new ArrayList<>();
        Wild w = Settings.wild(yaml("border_margin: 5000\n"), warn);
        assertEquals(Wild.MAX_MARGIN, w.borderMargin());
        assertEquals(1, warn.size());
        warn.clear();
        assertEquals(0, Settings.wild(yaml("border_margin: -3\n"), warn).borderMargin());
        assertEquals(1, warn.size());
        warn.clear();
        assertEquals(0, Settings.wild(yaml("border_margin: 0\n"), warn).borderMargin());
        assertTrue(warn.isEmpty());
    }
}
