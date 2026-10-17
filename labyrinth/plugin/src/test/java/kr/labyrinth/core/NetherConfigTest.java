package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/**
 * config wild.nether (0.3.7, 서버장 결정 "네더 막아"): 안전한 기본값 = 막음. 서버장의 예전 config (키 없음) · wild: false · 잘못된 값 → 막음.
 * true 일 때만 열림. jar 의 config.yml 에 키와 안내 글이 있음.
 */
class NetherConfigTest {

    static final File BUNDLED = new File("src/main/resources/config.yml");

    static boolean open(String yaml) { return new Settings(WildConfigTest.yaml(yaml)).netherOpen(); }

    @Test
    void safeDefaultIsBlocked() {
        assertFalse(new Settings(new YamlConfiguration()).netherOpen(), "키 없음 = 막음");
        assertFalse(open("wild:\n  border: true\n"), "wild 는 있는데 nether 가 없음 (0.3.5.1 ~ 0.3.6 서버장 config)");
        assertFalse(open("wild: false\n"), "wild: false 여도 네더는 막힘");
        assertFalse(open("wild:\n  nether: false\n"));
        assertTrue(open("wild:\n  nether: true\n"), "true 면 다시 열림");
        assertTrue(open("wild:\n  border: false\n  spawns: none\n  nether: true\n"), "야생 막기를 다 끄고 네더만 열기");
    }

    @Test
    void ownersOldConfigWithJarDefaultsIsBlocked() {
        // plugin.getConfig() 모양: 서버장 파일 (wild 없음) + jar config 기본값
        YamlConfiguration file = WildConfigTest.yaml("village:\n  teleport_command: true\n");
        file.setDefaults(YamlConfiguration.loadConfiguration(BUNDLED));
        assertFalse(new Settings(file).netherOpen());
        assertFalse(file.saveToString().contains("nether"), "읽기만으로 키가 생기지 않음");
        // 서버장 파일에 wild 섹션이 있고 nether 만 없음
        YamlConfiguration file2 = WildConfigTest.yaml("wild:\n  border_margin: 40\n");
        file2.setDefaults(YamlConfiguration.loadConfiguration(BUNDLED));
        assertFalse(new Settings(file2).netherOpen());
        file2.set("wild.nether", true);
        assertTrue(new Settings(file2).netherOpen());
    }

    @Test
    void oddValuesAreBlockedWithAWarning() {
        assertTrue(open("wild:\n  nether: yes\n"), "YAML 의 yes 는 true (Bukkit 그대로)");
        for (String v : List.of("\"true\"", "1", "열림", "open")) {
            Settings s = new Settings(WildConfigTest.yaml("wild:\n  nether: " + v + "\n"));
            assertFalse(s.netherOpen(), v);
            assertEquals(1, s.wildWarnings().size(), v);
            assertTrue(s.wildWarnings().get(0).contains("wild.nether"), v);
        }
        List<String> warn = new ArrayList<>();
        assertFalse(Settings.netherOpen(null, warn));
        assertFalse(Settings.netherOpen(Boolean.FALSE, warn));
        assertTrue(warn.isEmpty());
    }

    @Test
    void bundledConfigHasTheSwitchAndTheHint() throws Exception {
        Settings s = new Settings(YamlConfiguration.loadConfiguration(BUNDLED));
        assertFalse(s.netherOpen(), "jar 기본값 = 막음");
        assertTrue(s.wildWarnings().isEmpty());
        String text = Files.readString(BUNDLED.toPath(), StandardCharsets.UTF_8);
        assertTrue(text.contains("nether: false"), "wild 아래 nether: false");
        assertTrue(text.contains("true 로 바꾸면 네더 차원문을 다시 쓸 수 있습니다"), "서버장이 보는 안내 글");
        assertFalse(text.contains("네더 차원문용 흑요석"), "자재에서 흑요석·부싯돌을 뺐다");
        assertFalse(text.contains("통째로 끄려면 wild: false (바닐라 그대로)"), "wild: false 여도 네더는 막힌 채 — 예전 글은 틀림");
        assertTrue(text.contains("wild: false = 경계·스폰만 바닐라 (네더는 막힌 채)"));
        assertTrue(text.contains("border: false · spawns: none · nether: true"), "네더까지 여는 법");
    }

    @Test
    void openingTheNetherFromWildFalseKeepsBorderAndSpawnsOff() {
        // 예전에 wild: false 였던 서버장이 config.yml 글대로 세 줄을 적음 → 경계·스폰은 여전히 바닐라, 네더만 열림
        Settings s = new Settings(WildConfigTest.yaml("wild:\n  border: false\n  spawns: none\n  nether: true\n"));
        assertTrue(s.netherOpen());
        assertFalse(s.wild().border());
        assertEquals(Settings.Wild.Spawns.NONE, s.wild().spawns());
        // nether: true 한 줄만 적으면 경계·스폰 막기가 기본값으로 다시 켜진다 (그래서 글이 세 줄을 말함)
        Settings one = new Settings(WildConfigTest.yaml("wild:\n  nether: true\n"));
        assertTrue(one.wild().border());
        assertEquals(Settings.Wild.Spawns.ALL, one.wild().spawns());
    }
}
