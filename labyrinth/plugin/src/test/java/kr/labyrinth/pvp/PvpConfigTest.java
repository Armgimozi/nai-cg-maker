package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** config.yml {@code pvp:} 읽기 · 범위 자르기 · 0.3.4 값 옮기기 (pvp_spec §12·§13). */
class PvpConfigTest {

    static PvpConfig read(String yaml, List<String> notes) throws InvalidConfigurationException {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(yaml);
        return PvpConfig.from(y.getConfigurationSection("pvp"), notes);
    }

    static PvpConfig read(String yaml) throws InvalidConfigurationException { return read(yaml, null); }

    @Test
    void defaults() {
        PvpConfig d = PvpConfig.DEFAULT;
        assertEquals(1.0, d.damageMultiplier(), 1e-9);
        assertEquals(1.0, d.maxHitRatio(), 1e-9, "한 방 상한 없음");
        assertEquals(0.0, d.defenseWeight(), 1e-9);
        assertEquals(0.6, d.critDamageScale(), 1e-9);
        assertEquals(0.40, d.resilience().cap(), 1e-9);
        assertEquals(0.9, d.classDamage().of("hunter", 35), 1e-9);
        assertEquals(1.2, d.classDamage().of("arcanist", 20), 1e-9);
        assertEquals(1.2, d.classDamage().of("shadow", 50), 1e-9);
        assertEquals(1.0, d.classDamage().of("guardian", 50), 1e-9, "적지 않은 직업 = 1");
        assertEquals(1.0, d.classDamage().of(null, 50), 1e-9);
        assertEquals(0.6, d.healing(), 1e-9);
        assertEquals(0.5, d.lifesteal(), 1e-9);
        assertEquals(0.8, d.shield(), 1e-9);
        assertEquals(1.0, d.cc().maxSeconds().get("stun"), 1e-9);
        assertEquals(1.5, d.cc().maxSeconds().get("frozen"), 1e-9);
        assertEquals(List.of(1.0, 0.5, 0.25, 0.0), d.cc().steps());
        assertTrue(d.cc().isControl("stun") && d.cc().isControl("frozen"));
        assertFalse(d.cc().isControl("root"));
        assertEquals(PvpConfig.DEFAULT, PvpConfig.from(null), "pvp 블록이 없으면 기본값");
    }

    @Test
    void bundledConfigEqualsDefaultsAndSpec() throws IOException {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        List<String> notes = new ArrayList<>();
        assertEquals(PvpConfig.DEFAULT, PvpConfig.from(y.getConfigurationSection("pvp"), notes),
                "jar config.yml = PvpConfig.DEFAULT (키가 빠진 설정도 같은 값)");
        assertTrue(notes.isEmpty(), "새 판 설정은 옮기지 않음: " + notes);
        // 명세(pvp_spec.json config.pvp)와 같은 숫자
        JsonObject spec = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/pvp_spec.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("config").getAsJsonObject("pvp");
        PvpConfig d = PvpConfig.DEFAULT;
        assertEquals(spec.get("damage_multiplier").getAsDouble(), d.damageMultiplier(), 1e-9);
        assertEquals(spec.getAsJsonObject("level_curve").get("exponent").getAsDouble(), d.levelCurve().exponent(), 1e-9);
        assertEquals(spec.getAsJsonObject("buffer_hp").get("per_level_low").getAsDouble(), d.bufferHp().perLevelLow(), 1e-9);
        assertEquals(spec.getAsJsonObject("resilience").get("per_level").getAsDouble(), d.resilience().perLevel(), 1e-9);
        assertEquals(spec.get("crit_damage_scale").getAsDouble(), d.critDamageScale(), 1e-9);
        assertEquals(spec.get("potion").getAsDouble(), d.potion(), 1e-9);
        assertEquals(spec.getAsJsonObject("long_fight").get("per_second").getAsDouble(), d.longFight().perSecond(), 1e-9);
        JsonObject cc = spec.getAsJsonObject("cc");
        for (var e : cc.getAsJsonObject("duration").entrySet()) {
            assertEquals(e.getValue().getAsDouble(), d.cc().duration().get(e.getKey()), 1e-9, "cc.duration." + e.getKey());
        }
        for (var e : cc.getAsJsonObject("max_seconds").entrySet()) {
            assertEquals(e.getValue().getAsDouble(), d.cc().maxSeconds().get(e.getKey()), 1e-9, "cc.max_seconds." + e.getKey());
        }
        assertEquals(cc.get("control_immunity").getAsDouble(), d.cc().controlImmunity(), 1e-9);
        assertEquals(cc.get("min_seconds").getAsDouble(), d.cc().minSeconds(), 1e-9);
        for (var e : spec.getAsJsonObject("class_damage").entrySet()) {
            assertEquals(e.getValue().getAsDouble(), d.classDamage().of(e.getKey(), 35), 1e-9, "class_damage." + e.getKey());
        }
    }

    /** 0.3.4 config.yml 그대로 (새 키 없음): 0.7 → 1.0, 0.35 → 1.0. */
    @Test
    void migratesUntouched034Values() throws InvalidConfigurationException {
        List<String> notes = new ArrayList<>();
        PvpConfig c = read("pvp:\n  enabled: true\n  damage_multiplier: 0.7\n  max_hit_ratio: 0.35\n  safe_zone_margin: 8\n", notes);
        assertEquals(1.0, c.damageMultiplier(), 1e-9);
        assertEquals(1.0, c.maxHitRatio(), 1e-9);
        assertEquals(2, notes.size(), "옮긴 것 한 줄씩: " + notes);
        assertTrue(notes.get(0).contains("0.7 → 1"), notes.get(0));
    }

    /** 고친 값: 배율 v → v ÷ 0.7 (0.5 → 0.714), 상한 0.5 는 그대로 (일부러 상한을 원하는 서버). */
    @Test
    void migratesEdited034Values() throws InvalidConfigurationException {
        List<String> notes = new ArrayList<>();
        PvpConfig c = read("pvp:\n  damage_multiplier: 0.5\n  max_hit_ratio: 0.5\n", notes);
        assertEquals(0.5 / 0.7, c.damageMultiplier(), 1e-9);
        assertEquals(0.5, c.maxHitRatio(), 1e-9);
        assertTrue(notes.get(0).contains("0.5 → 0.71"), notes.get(0));
        assertEquals(1, notes.size());
        PvpConfig one = read("pvp:\n  damage_multiplier: 1.0\n");
        assertEquals(1.0 / 0.7, one.damageMultiplier(), 1e-9, "0.3.4 의 1.0 → 1.43");
    }

    /** 새 판 키가 하나라도 있으면 옮기지 않는다 (다시 읽어도 두 번 나누지 않음). */
    @Test
    void newFormatIsNotMigrated() throws InvalidConfigurationException {
        List<String> notes = new ArrayList<>();
        PvpConfig c = read("pvp:\n  damage_multiplier: 0.7\n  max_hit_ratio: 0.35\n  crit_damage_scale: 0.6\n", notes);
        assertEquals(0.7, c.damageMultiplier(), 1e-9);
        assertEquals(0.35, c.maxHitRatio(), 1e-9);
        assertTrue(notes.isEmpty());
        assertEquals(c, read("pvp:\n  damage_multiplier: 0.7\n  max_hit_ratio: 0.35\n  crit_damage_scale: 0.6\n"), "같은 결과");
    }

    @Test
    void missingKeysAreDefaults() throws InvalidConfigurationException {
        PvpConfig c = read("pvp:\n  enabled: true\n");
        assertEquals(PvpConfig.DEFAULT, c);
        PvpConfig partial = read("pvp:\n  resilience: {cap: 0.35}\n");
        assertEquals(0.35, partial.resilience().cap(), 1e-9);
        assertEquals(8, partial.resilience().perLevel(), 1e-9, "적지 않은 하위 키 = 기본값");
        assertEquals(PvpConfig.DEFAULT.cc(), partial.cc());
        assertEquals(PvpConfig.DEFAULT.classDamage(), partial.classDamage());
    }

    @Test
    void clamps() throws InvalidConfigurationException {
        PvpConfig c = read("pvp:\n  damage_multiplier: 9\n  max_hit_ratio: 0\n  resilience: {cap: 2, per_level: -1}\n"
                + "  crit_damage_scale: 3\n  healing: -1\n  safe_zone_margin: -3\n"
                + "  cc:\n    duration: {stun: 5}\n    slow_max_potency: 2\n    diminishing: {steps: [2, -1]}\n");
        assertEquals(5.0, c.damageMultiplier(), 1e-9);
        assertEquals(0.05, c.maxHitRatio(), 1e-9);
        assertEquals(0.9, c.resilience().cap(), 1e-9);
        assertEquals(0.1, c.resilience().perLevel(), 1e-9);
        assertEquals(1.0, c.critDamageScale(), 1e-9);
        assertEquals(0.0, c.healing(), 1e-9);
        assertEquals(0, c.safeZoneMargin());
        assertEquals(2.0, c.cc().duration().get("stun"), 1e-9);
        assertEquals(0.8, c.cc().duration().get("root"), 1e-9, "적지 않은 종류 = 기본값");
        assertEquals(0.95, c.cc().slowMaxPotency(), 1e-9);
        assertEquals(List.of(1.0, 0.0), c.cc().steps());
    }

    /** review2 F1: 직업 보정을 레벨대마다 (Lv20·35·50) 따로. */
    @Test
    void classDamageByLevelBand() throws InvalidConfigurationException {
        PvpConfig c = read("pvp:\n  class_damage:\n    hunter: 0.9\n    arcanist: {low: 1.2, mid: 1.1, high: 1.3}\n"
                + "    shadow: {all: 1.15, high: 1.25}\n  class_damage_levels: {mid: 30, high: 45}\n");
        assertEquals(0.9, c.classDamage().of("hunter", 50), 1e-9);
        assertEquals(1.2, c.classDamage().of("arcanist", 29), 1e-9);
        assertEquals(1.1, c.classDamage().of("arcanist", 30), 1e-9);
        assertEquals(1.1, c.classDamage().of("arcanist", 44), 1e-9);
        assertEquals(1.3, c.classDamage().of("arcanist", 45), 1e-9);
        assertEquals(1.15, c.classDamage().of("shadow", 20), 1e-9);
        assertEquals(1.25, c.classDamage().of("shadow", 50), 1e-9);
        assertEquals(1.0, c.classDamage().of("guardian", 50), 1e-9, "목록에 없는 직업 = 1 (기본 목록을 섞지 않음)");
        PvpConfig d = PvpConfig.DEFAULT;
        assertEquals(28, d.classDamage().midFrom());
        assertEquals(43, d.classDamage().highFrom());
    }
}
