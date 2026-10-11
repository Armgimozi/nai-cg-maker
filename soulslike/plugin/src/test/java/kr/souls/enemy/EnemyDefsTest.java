package kr.souls.enemy;

import kr.souls.Content;
import kr.souls.TestFiles;
import kr.souls.combat.Hit;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * M1 P1b: enemies.yml 읽기 (enemy/EnemyDefs). 파일은 Content.merge 로 열쇠마다 jar 위에 겹치고 (R20), 그 위에서 틀린 값은 같은 id 의 jar
 * 값으로, jar 에도 없으면 기본값으로 물러선다. 사용자가 새로 쓴 id 는 빠진 열쇠를 기본값으로.
 */
class EnemyDefsTest {
    private static YamlConfiguration y(String text) {
        YamlConfiguration c = new YamlConfiguration();
        try {
            c.loadFromString(text);
        } catch (InvalidConfigurationException e) {
            throw new AssertionError(e);
        }
        return c;
    }

    private static final double EPS = 1e-9;

    @Test
    void shippedDummy() {
        YamlConfiguration jar = TestFiles.yaml("content/enemies.yml");
        List<String> warns = new ArrayList<>();
        Map<String, EnemyDefs.Def> m = EnemyDefs.parse(jar, jar, warns::add);
        EnemyDefs.Def d = m.get("dummy");
        assertEquals("zombie", d.body());
        assertEquals(1000, d.hp(), EPS);
        assertEquals(20, d.def(), EPS);
        assertEquals(0, d.poise(), EPS);
        assertEquals("none", d.ai());
        assertTrue(d.brainless());
        assertEquals(60, d.regenAfter());
        assertEquals(60, d.respawn());
        assertEquals(EnemyDefs.Material.STRAW, d.material());
        assertTrue(d.absorb().isEmpty() && d.weak().isEmpty());
        assertEquals(0, d.absorbOf(Hit.Type.SLASH), EPS);
        assertEquals(1, d.weakOf(Hit.Type.FIRE), EPS);
        assertTrue(warns.isEmpty(), "jar 사본은 경고 없이 읽힌다: " + warns);
        // 보이는 이름은 없다 (이야기 보류, 시험 적은 [시험용] lang 열쇠로만)
        for (String id : jar.getKeys(false)) {
            for (String k : jar.getConfigurationSection(id).getKeys(false)) assertFalse(k.equals("name") || k.equals("display"), id + "." + k);
        }
    }

    @Test
    void userValuesWinPerKeyAndJarFillsTheRest() {
        YamlConfiguration jar = y("dummy: {body: zombie, hp: 1000, def: 20, ai: none, regen-after: 60, respawn: 60, material: straw}");
        YamlConfiguration user = y("dummy: {hp: 2500, respawn: 10}");
        YamlConfiguration merged = Content.merge(jar, user).yml();
        EnemyDefs.Def d = EnemyDefs.parse(merged, jar, null).get("dummy");
        assertEquals(2500, d.hp(), EPS, "사용자가 맞춘 값");
        assertEquals(10, d.respawn());
        assertEquals(20, d.def(), EPS, "사용자 파일에 없는 열쇠는 jar 값");
        assertEquals(60, d.regenAfter());
        assertEquals(EnemyDefs.Material.STRAW, d.material());
    }

    @Test
    void badValuesFallBackToJarThenDefault() {
        YamlConfiguration jar = y("dummy: {body: zombie, hp: 1000, def: 20, regen-after: 60, material: straw, absorb: {slash: 0.2}}");
        YamlConfiguration user = y("""
                dummy: {hp: -5, def: lots, regen-after: 2.5e9, material: glass, body: 7, absorb: {slash: 3, bogus: 0.1, fire: 0.5}}
                """);
        YamlConfiguration merged = Content.merge(jar, user).yml();
        List<String> warns = new ArrayList<>();
        EnemyDefs.Def d = EnemyDefs.parse(merged, jar, warns::add).get("dummy");
        assertEquals(1000, d.hp(), EPS, "음수 hp → jar");
        assertEquals(20, d.def(), EPS, "글 def → jar");
        assertEquals(60, d.regenAfter(), "범위 밖 → jar");
        assertEquals(EnemyDefs.Material.STRAW, d.material(), "모르는 재질 → jar");
        assertEquals("zombie", d.body(), "글이 아닌 body → jar");
        assertEquals(0.2, d.absorbOf(Hit.Type.SLASH), EPS, "범위 밖 흡수율 칸만 jar");
        assertEquals(0.5, d.absorbOf(Hit.Type.FIRE), EPS, "맞는 칸은 사용자 값");
        assertEquals(0, d.absorbOf(Hit.Type.MAGIC), EPS);
        assertTrue(warns.size() >= 7, "틀린 값마다 알린다: " + warns);
    }

    @Test
    void userOnlyIdGetsDefaults() {
        YamlConfiguration jar = y("dummy: {body: zombie, hp: 1000}");
        YamlConfiguration user = y("""
                practice: {hp: 300, ai: none, weak: {strike: 1.5}}
                broken: 12
                """);
        YamlConfiguration merged = Content.merge(jar, user).yml();
        List<String> warns = new ArrayList<>();
        Map<String, EnemyDefs.Def> m = EnemyDefs.parse(merged, jar, warns::add);
        EnemyDefs.Def p = m.get("practice");
        assertEquals(EnemyDefs.BODY, p.body());
        assertEquals(300, p.hp(), EPS);
        assertEquals(EnemyDefs.DEF, p.def(), EPS);
        assertEquals(EnemyDefs.POISE, p.poise(), EPS);
        assertEquals(EnemyDefs.REGEN_AFTER, p.regenAfter());
        assertEquals(EnemyDefs.RESPAWN, p.respawn());
        assertEquals(EnemyDefs.MATERIAL, p.material());
        assertEquals(1.5, p.weakOf(Hit.Type.STRIKE), EPS);
        assertEquals(1, p.weakOf(Hit.Type.SLASH), EPS);
        assertNull(m.get("broken"), "절이 아닌 id 는 건너뛴다");
        assertTrue(warns.stream().anyMatch(w -> w.contains("broken")), warns.toString());
        assertEquals(1000, m.get("dummy").hp(), EPS, "jar 의 id 는 그대로 남는다");
    }

    @Test
    void emptyOrMissingFile() {
        assertTrue(EnemyDefs.parse(null, null, null).isEmpty());
        assertTrue(EnemyDefs.parse(new YamlConfiguration(), null, null).isEmpty());
        EnemyDefs defs = new EnemyDefs();
        assertNull(defs.get("dummy"));
        defs.load(y("dummy: {hp: 50}"), null, null);
        assertEquals(50, defs.get("dummy").hp(), EPS);
        assertEquals(EnemyDefs.AI, defs.get("dummy").ai(), "jar 없이 빠진 열쇠는 기본값");
    }
}
