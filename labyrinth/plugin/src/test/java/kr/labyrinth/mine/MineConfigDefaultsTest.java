package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/**
 * config.yml {@code mine:} 손잡이 = 계약 mine.json {@code config_defaults} (§0 뒤: 기력 {@code stamina}·매크로 알림 {@code alert_per_hour} 없음).
 * 0.3.7: 광맥은 층마다 정해진 분 뒤 다시 참 (사람 수와 관계 없음) — {@code regen_players_cap} 없음, 0.3.6.1 기본 목록은 새 기본으로 읽음.
 * 키가 없으면 코드 기본값.
 */
class MineConfigDefaultsTest {

    /** 계약 config_defaults 에서 주인 늦은 결정(§0)으로 빠진 키. */
    static final List<String> REMOVED = List.of("stamina", "alert_per_hour");

    static Map<String, Object> contractDefaults() {
        Map<String, Object> m = new LinkedHashMap<>(MineTestData.mineJson().sub("config_defaults").sub("mine").asMap());
        for (String k : REMOVED) m.remove(k);
        return m;
    }

    /** 숫자 모양(정수/실수)만 다른 것을 같게 본다. */
    static Object norm(Object o) {
        if (o instanceof Number n) return n.doubleValue();
        if (o instanceof Map<?, ?> m) {
            Map<String, Object> out = new LinkedHashMap<>();
            for (var e : m.entrySet()) out.put(String.valueOf(e.getKey()), norm(e.getValue()));
            return out;
        }
        if (o instanceof List<?> l) return l.stream().map(MineConfigDefaultsTest::norm).toList();
        return o;
    }

    @Test
    void codeDefaultsEqualContract() {
        assertEquals(norm(contractDefaults()), norm(MineConfig.DEFAULT.toMap()));
    }

    @Test
    void shippedConfigEqualsDefaults() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertTrue(y.isConfigurationSection("mine"));
        assertEquals(MineConfig.DEFAULT, MineConfig.fromRoot(y));
        for (String k : REMOVED) assertFalse(y.contains("mine." + k), "config.yml mine." + k + " 없음 (계약 §0)");
        assertFalse(y.contains("mine.regen_players_cap"), "config.yml mine.regen_players_cap 없음 (0.3.7)");
        assertTrue(MineConfig.legacyNotes(y.getConfigurationSection("mine")).isEmpty());
    }

    @Test
    void defaultsAreFixedThreeMinutes() {
        assertEquals(List.of(3, 3, 3, 3, 3, 3), MineConfig.DEFAULT.regenMinutes());
        assertEquals(30, MineConfig.DEFAULT.gemNodeRegenMinutes());
        assertEquals(180.0, MineConfig.DEFAULT.regenSeconds(1));
        assertEquals(1800.0, MineConfig.DEFAULT.gemRegenSeconds());
        assertFalse(MineConfig.DEFAULT.toMap().containsKey("regen_players_cap"), "toMap 에 사람 수 손잡이 없음");
    }

    @Test
    void ownerConfigFrom0361() throws Exception {
        // 0.3.6·0.3.6.1 로 깐 서버의 config.yml 그대로: 옛 기본 목록 → 새 기본 · regen_players_cap 은 무시 + 안내 한 줄
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("mine:\n  regen_minutes: [8, 9, 9, 10, 10, 10]\n  gem_node_regen_minutes: 30\n  regen_players_cap: 4\n");
        MineConfig c = MineConfig.fromRoot(y);
        assertEquals(MineConfig.DEFAULT_REGEN, c.regenMinutes());
        assertEquals(MineConfig.DEFAULT, c);
        assertEquals(List.of(MineConfig.LEGACY_CAP_NOTE), MineConfig.legacyNotes(y.getConfigurationSection("mine")));
        // 주인이 고친 목록은 그대로
        y = new YamlConfiguration();
        y.loadFromString("mine:\n  regen_minutes: [8, 9, 9, 10, 10, 11]\n");
        assertEquals(List.of(8, 9, 9, 10, 10, 11), MineConfig.fromRoot(y).regenMinutes());
        assertTrue(MineConfig.legacyNotes(y.getConfigurationSection("mine")).isEmpty());
        assertTrue(MineConfig.legacyNotes(null).isEmpty());
    }

    @Test
    void missingSectionUsesDefaults() {
        assertEquals(MineConfig.DEFAULT, MineConfig.fromRoot(new YamlConfiguration()));
        assertEquals(MineConfig.DEFAULT, MineConfig.fromRoot(null));
        YamlConfiguration off = new YamlConfiguration();
        off.set("mine", false);
        assertFalse(MineConfig.fromRoot(off).enabled());
    }

    @Test
    void badValuesClamped() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("""
                mine:
                  regen_minutes: [0, 99999, x]
                  gem_chance: 5
                  rich: {chance: -1, multiplier: 100}
                  lift_seconds: -3
                  teleport_command: false
                  world: ''
                """);
        MineConfig c = MineConfig.fromRoot(y);
        assertEquals(List.of(1, 1440, 3, 3, 3, 3), c.regenMinutes());
        assertEquals(1.0, c.gemChance());
        assertEquals(0.0, c.richChance());
        assertEquals(10, c.richMultiplier());
        assertEquals(0.0, c.liftSeconds());
        assertEquals(MineConfig.Teleport.OFF, c.teleportCommand());
        assertEquals(MineNames.WORLD, c.world());
        assertEquals(60.0, c.regenSeconds(1));
        assertEquals(180.0, c.regenSeconds(99), "범위 밖 층 = 마지막 층");
    }

    @Test
    void singleNumberRegenAndTeleport() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("mine:\n  regen_minutes: 5\n  teleport_command: auto\n");
        MineConfig c = MineConfig.fromRoot(y);
        assertEquals(List.of(5, 5, 5, 5, 5, 5), c.regenMinutes());
        assertTrue(c.teleportAllowed(true));
        assertFalse(c.teleportAllowed(false), "auto = village.teleport_command 를 따름");
        y.loadFromString("mine:\n  teleport_command: true\n");
        assertTrue(MineConfig.fromRoot(y).teleportAllowed(false));
    }
}
