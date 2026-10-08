package kr.souls;

import kr.souls.progression.StatCurves;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 기본 config.yml 이 설계 문서의 표 (StatCurves.defaults, 5.7 난이도) 와 같다. */
class ConfigDefaultsTest {
    private final Config cfg = new Config(TestFiles.yaml("config.yml"));

    @Test
    void controlsDefaultToSneak() {
        assertEquals("sneak", cfg.controls.rollKey());
        assertTrue(cfg.controls.sneakRolls());
        assertFalse(cfg.controls.fRolls());
        assertEquals(5, cfg.controls.tapMaxTicks());
    }

    @Test
    void fourDifficulties() {
        assertEquals("normal", cfg.difficultyDefault);
        assertEquals(java.util.Set.of("easy", "normal", "hard", "very_hard"), cfg.difficulties.keySet());
        Config.Difficulty e = cfg.difficulty("easy"), n = cfg.difficulty("normal"), h = cfg.difficulty("hard"), v = cfg.difficulty("very_hard");
        assertTrue(e.enemyDamage() < n.enemyDamage() && n.enemyDamage() < h.enemyDamage() && h.enemyDamage() < v.enemyDamage());
        assertEquals(1.0, n.enemyDamage(), 1e-9);
        assertTrue(e.estusStart() >= n.estusStart() && n.estusStart() >= v.estusStart());
        for (Config.Difficulty d : cfg.difficulties.values()) assertEquals(1.0, d.souls(), 1e-9, "소울 배율은 모두 1 (검토)");
        assertEquals(n, cfg.difficulty("nonsense"), "모르는 이름은 기본");
    }

    @Test
    void pvpOffByDefault() {
        assertFalse(cfg.pvp.def());
        assertTrue(cfg.pvp.keepSouls());
    }

    @Test
    void statCurvesMatchDesignDefaults() {
        StatCurves a = cfg.stats, b = StatCurves.defaults();
        assertEquals(b.max, a.max);
        StatCurves.Curve[] ca = {a.scaling, a.maxHealth, a.vigorDefense, a.maxMana, a.magicDefense, a.maxStamina, a.regenScale, a.equipLoad,
                a.moveSpeed, a.attackSpeed, a.statusResist};
        StatCurves.Curve[] cb = {b.scaling, b.maxHealth, b.vigorDefense, b.maxMana, b.magicDefense, b.maxStamina, b.regenScale, b.equipLoad,
                b.moveSpeed, b.attackSpeed, b.statusResist};
        for (int i = 0; i < ca.length; i++) {
            for (int x = 1; x <= 99; x++) assertEquals(cb[i].at(x), ca[i].at(x), 1e-9, "곡선 " + i + " 의 " + x);
        }
        for (int x = 1; x <= 99; x++) assertEquals(b.memorySlots.at(x), a.memorySlots.at(x));
        for (String g : new String[] {"E", "D", "C", "B", "A", "S"}) {
            assertEquals(b.grade(g), a.grade(g), 1e-9);
            assertEquals(b.speedGrade(g), a.speedGrade(g), 1e-9);
        }
    }

    @Test
    void levelCostMatchesDefaults() {
        var d = kr.souls.progression.LevelCost.defaults();
        for (int lv = 1; lv <= 712; lv += 7) assertEquals(d.next(lv), cfg.levelCost.next(lv), "레벨 " + lv);
    }

    @Test
    void loadTiersMatchDefaults() {
        var d = kr.souls.progression.LoadTiers.defaults();
        assertEquals(d.all(), cfg.load.all());
        assertEquals("auto", cfg.roll.load());
    }
}
