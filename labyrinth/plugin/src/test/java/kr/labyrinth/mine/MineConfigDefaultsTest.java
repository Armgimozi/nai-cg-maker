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
 * config.yml {@code mine:} 손잡이 = 계약 mine.json {@code config_defaults} (§0 뒤: 기력 {@code stamina}·매크로 알림 {@code alert_per_hour} 없음,
 * 광맥 공유 {@code regen_players_cap: 4} 더함). 키가 없으면 코드 기본값.
 */
class MineConfigDefaultsTest {

    /** 계약 config_defaults 에서 주인 늦은 결정(§0)으로 빠진 키. */
    static final List<String> REMOVED = List.of("stamina", "alert_per_hour");

    static Map<String, Object> contractDefaults() {
        Map<String, Object> m = new LinkedHashMap<>(MineTestData.mineJson().sub("config_defaults").sub("mine").asMap());
        for (String k : REMOVED) m.remove(k);
        m.put("regen_players_cap", MineNames.REGEN_PLAYERS_CAP);
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
                  regen_players_cap: 0
                  gem_chance: 5
                  rich: {chance: -1, multiplier: 100}
                  lift_seconds: -3
                  teleport_command: false
                  world: ''
                """);
        MineConfig c = MineConfig.fromRoot(y);
        assertEquals(List.of(1, 1440, 9, 10, 10, 10), c.regenMinutes());
        assertEquals(1, c.regenPlayersCap());
        assertEquals(1.0, c.gemChance());
        assertEquals(0.0, c.richChance());
        assertEquals(10, c.richMultiplier());
        assertEquals(0.0, c.liftSeconds());
        assertEquals(MineConfig.Teleport.OFF, c.teleportCommand());
        assertEquals(MineNames.WORLD, c.world());
        assertEquals(60.0, c.regenSeconds(1));
        assertEquals(600.0, c.regenSeconds(99), "범위 밖 층 = 마지막 층");
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
