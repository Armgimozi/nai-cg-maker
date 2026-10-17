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
 * 광맥 공유 {@code regen_players_cap: 4} 더함) + 0.3.7 광산 PvP {@code pvp}. 키가 없으면 코드 기본값.
 */
class MineConfigDefaultsTest {

    /** 계약 config_defaults 에서 주인 늦은 결정(§0)으로 빠진 키. */
    static final List<String> REMOVED = List.of("stamina", "alert_per_hour");

    /** 0.3.7 더함 (주인 결정 "광산 PVP 키자" — 0.3.6 계약 파일은 역사라 고치지 않고 여기서 더한다). */
    static final Map<String, Object> PVP_037 = Map.of("enabled", true, "penalty", true, "safe_margin", 3);

    static Map<String, Object> contractDefaults() {
        Map<String, Object> m = new LinkedHashMap<>(MineTestData.mineJson().sub("config_defaults").sub("mine").asMap());
        for (String k : REMOVED) m.remove(k);
        m.put("regen_players_cap", MineNames.REGEN_PLAYERS_CAP);
        m.put("pvp", PVP_037);
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
    void minePvpDefaultsOnAndSwitches() throws Exception {
        assertEquals(new MineConfig.Pvp(true, true, 3), MineConfig.DEFAULT.pvp());
        YamlConfiguration jar = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertTrue(jar.isConfigurationSection("mine.pvp"), "배포 config.yml 에 mine.pvp 가 있음");
        assertEquals(MineConfig.DEFAULT_PVP, MineConfig.fromRoot(jar).pvp());
        // 0.3.6.1 서버 config (mine: 는 있지만 pvp 키가 없음) — jar 만 바꾸면 켜진 채로 시작 (파일은 고쳐 쓰지 않음)
        YamlConfiguration old = new YamlConfiguration();
        old.loadFromString("mine:\n  enabled: true\n  safe: true\n  lift_seconds: 2.0\n");
        assertEquals(MineConfig.DEFAULT_PVP, MineConfig.fromRoot(old).pvp());
        assertFalse(old.contains("mine.pvp"), "읽기만 해도 키가 생기지 않음");
        YamlConfiguration off = new YamlConfiguration();
        off.loadFromString("mine:\n  pvp: false\n");
        assertEquals(new MineConfig.Pvp(false, true, 3), MineConfig.fromRoot(off).pvp(), "pvp: false = enabled false");
        off.loadFromString("mine:\n  pvp: {enabled: false}\n");
        assertFalse(MineConfig.fromRoot(off).pvp().enabled());
        off.loadFromString("mine:\n  pvp: {penalty: false}\n");
        assertEquals(new MineConfig.Pvp(true, false, 3), MineConfig.fromRoot(off).pvp(), "잃는 것만 끔 = 경험치만");
        off.loadFromString("mine:\n  pvp: {safe_margin: 99}\n");
        assertEquals(16, MineConfig.fromRoot(off).pvp().safeMargin(), "둘레는 0 ~ 16");
        off.loadFromString("mine:\n  pvp: {safe_margin: -2}\n");
        assertEquals(0, MineConfig.fromRoot(off).pvp().safeMargin());
        YamlConfiguration whole = new YamlConfiguration();
        whole.set("mine", false);
        assertEquals(MineConfig.DEFAULT_PVP, MineConfig.fromRoot(whole).pvp(), "mine: false 는 광산 전체를 끔 (pvp 값은 기본)");
        assertFalse(MineConfig.fromRoot(whole).enabled());
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
