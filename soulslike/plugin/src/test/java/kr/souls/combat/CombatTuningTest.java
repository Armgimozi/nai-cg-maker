package kr.souls.combat;

import kr.souls.Config;
import kr.souls.TestFiles;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** M1 P1-0: CombatTuning 의 틀과 읽는 도우미 (M1_PLAN 0.4). 묶음의 레코드는 이 도우미로 읽고 jar 기본값으로 떨어진다. */
class CombatTuningTest {
    private static YamlConfiguration y(String text) {
        YamlConfiguration c = new YamlConfiguration();
        try {
            c.loadFromString(text);
        } catch (InvalidConfigurationException e) {
            throw new AssertionError(e);
        }
        return c;
    }

    @Test
    void configHasOneTuningField() {
        Config cfg = new Config(TestFiles.yaml("config.yml"));
        assertNotNull(cfg.tuning);
        assertNotNull(cfg.tuning.section("bow"), "없는 절도 빈 절 (null 이 아니다)");
        assertNotNull(new Config(new YamlConfiguration()).tuning, "빈 설정");
        assertNotNull(CombatTuning.read(null).section("x"));
    }

    @Test
    void scalars() {
        YamlConfiguration c = y("a: 7\nb: 2.6\nc: nope\nd: true\nbig: 99999999999\n");
        assertEquals(7, CombatTuning.i(c, "a", 1, 0, 100));
        assertEquals(3, CombatTuning.i(c, "b", 1, 0, 100), "실수는 반올림");
        assertEquals(1, CombatTuning.i(c, "c", 1, 0, 100), "글은 기본값");
        assertEquals(1, CombatTuning.i(c, "missing", 1, 0, 100));
        assertEquals(100, CombatTuning.i(c, "big", 1, 0, 100), "자른다");
        assertEquals(5, CombatTuning.i(null, "a", 5, 0, 10));
        assertEquals(2.6, CombatTuning.d(c, "b", 1, 0, 10), 1e-12);
        assertEquals(7.0, CombatTuning.d(c, "a", 1, 0, 10), 1e-12, "정수도 실수로");
        assertEquals(0.5, CombatTuning.d(c, "c", 0.5, 0, 1), 1e-12);
        assertEquals(1.0, CombatTuning.d(c, "a", 0.5, 0, 1), 1e-12, "자른다");
        assertTrue(CombatTuning.b(c, "d", false));
        assertFalse(CombatTuning.b(c, "a", false), "참거짓이 아니면 기본값");
    }

    @Test
    void tablesTreatEmptySectionAsMissing() {
        Map<String, Integer> def = Map.of("dagger", 4);
        assertEquals(def, CombatTuning.ints(y("t: {}\n"), "t", def, 0, 40), "예전 config.yml 의 빈 절은 기본 표");
        assertEquals(def, CombatTuning.ints(y("x: 1\n"), "t", def, 0, 40));
        Map<String, Integer> got = CombatTuning.ints(y("t: {greatsword: 2, small_shield: 80, bad: x}\n"), "t", def, 0, 40);
        assertEquals(Map.of("greatsword", 2, "small_shield", 40), got, "적은 값만, 자르고, 글은 버린다");
        Map<String, Double> dd = CombatTuning.doubles(y("t: {dagger: 1.3, x: .nan}\n"), "t", Map.of("default", 1.0), 0, 5);
        assertEquals(Map.of("dagger", 1.3), dd);
    }

    @Test
    void lists() {
        List<Double> def = List.of(100.0, 105.0, 115.0);
        assertEquals(List.of(100.0, 110.0), CombatTuning.list(y("m: [100, 110]\n"), "m", def));
        assertEquals(def, CombatTuning.list(y("m: [100, x]\n"), "m", def), "수가 아닌 것이 섞이면 기본값");
        assertEquals(def, CombatTuning.list(y("m: []\n"), "m", def));
        assertEquals(def, CombatTuning.list(y("q: 1\n"), "m", def));
    }

    /** jar 의 config.yml 이 M1 묶음 줄을 넣은 뒤에도 그대로 읽힌다 (combat 의 절은 그대로 넷). */
    @Test
    void jarConfigStillHasCombatSections() {
        YamlConfiguration c = TestFiles.yaml("config.yml");
        for (String k : List.of("stamina", "guard", "parry", "roll")) assertTrue(c.isConfigurationSection("combat." + k), k);
    }
}
