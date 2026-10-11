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
        StatCurves.Curve[] ca = {a.strAttack, a.intSpell, a.maxHealth, a.vigorDefense, a.maxMana, a.magicDefense, a.maxStamina, a.regenScale,
                a.equipLoad, a.moveSpeed, a.attackSpeed, a.statusResist};
        StatCurves.Curve[] cb = {b.strAttack, b.intSpell, b.maxHealth, b.vigorDefense, b.maxMana, b.magicDefense, b.maxStamina, b.regenScale,
                b.equipLoad, b.moveSpeed, b.attackSpeed, b.statusResist};
        for (int i = 0; i < ca.length; i++) {
            for (int x = 1; x <= 99; x++) assertEquals(cb[i].at(x), ca[i].at(x), 1e-9, "곡선 " + i + " 의 " + x);
        }
        for (int x = 1; x <= 99; x++) assertEquals(b.memorySlots.at(x), a.memorySlots.at(x));
    }

    /** 옛 판의 보정·요구 능력치 열쇠는 config.yml 에 없다 (장비에는 보정이 없다, DECISIONS 2026-10-10). */
    @Test
    void noGradeOrUnfitKeys() {
        var y = TestFiles.yaml("config.yml");
        for (String k : new String[] {"stats.grades", "stats.speed-grades", "stats.scaling-curve", "stats.unfit-penalty", "stats.unfit-speed"}) {
            assertFalse(y.contains(k), k);
        }
        assertTrue(y.contains("stats.strength.attack") && y.contains("stats.intelligence.spell-power") && y.contains("stats.dexterity.attack-speed"));
    }

    /** 막기 (3.4) 와 패링 (3.5) 의 기본: 불·술은 막기의 절반, 스태미나 0.8, 양손 막기 50 (대검 65), 패링 창은 분류마다. */
    @Test
    void guardAndParryDefaults() {
        assertEquals(0.5, cfg.guard.nonPhysical(), 1e-9);
        assertEquals(0.8, cfg.guard.staminaScale(), 1e-9);
        assertEquals(4, cfg.guard.staminaMin(), 1e-9);
        assertEquals(50, cfg.guard.twoHanded("straight_sword"));
        assertEquals(65, cfg.guard.twoHanded("greatsword"));
        Config.ParryCfg p = cfg.parry;
        assertEquals(9, p.window("parrying_dagger"));
        assertEquals(7, p.window("small_shield"));
        assertEquals(5, p.window("medium_shield"));
        assertEquals(0, p.window("greatshield"), "대방패는 패링하지 못한다");
        assertEquals(4, p.window("dagger"));
        assertEquals(0, p.window("greatsword"));
        assertEquals(0, p.window("halberd"));
        assertEquals(0, p.window("catalyst_kiln"));
        assertEquals(0, p.empty(), "빈 왼손은 패링하지 못한다 (기본)");
        assertEquals(2, p.min());
        assertEquals(12, p.lockMiss());
        assertEquals(6, p.lockHit());
        // 코드의 기본값 (config.yml 이 없을 때) 도 같다
        Config bare = new Config(new org.bukkit.configuration.file.YamlConfiguration());
        assertEquals(p.windows(), bare.parry.windows());
        assertEquals(cfg.guard, bare.guard);
    }

    /**
     * 예전 판 (커밋 3e894c0, 장비에 보정 등급이 있던 판) 의 config.yml 을 그대로 둔 서버 (saveDefaultConfig 는 있는 파일을 다시 쓰지
     * 않는다). JavaPlugin.reloadConfig 처럼 jar 의 config.yml 을 기본값으로 붙여 읽는다. combat.parry·combat.guard 절이 없는 파일에서
     * Bukkit 은 빈 절을 만들어 돌려주는데, 그때 코드의 표를 지우면 패링이 죽는다 (검토 old-config-parry-windows-empty).
     */
    @Test
    void oldConfigKeepsBuiltInTables() {
        var old = org.bukkit.configuration.file.YamlConfiguration.loadConfiguration(new java.io.File("src/test/resources/legacy/config-3e894c0.yml"));
        assertFalse(old.getKeys(true).contains("combat.parry"), "고정한 예전 파일에는 패링 절이 없다");
        old.setDefaults(TestFiles.yaml("config.yml"));
        Config c = new Config(old);
        assertEquals(7, c.parry.window("small_shield"));
        assertEquals(9, c.parry.window("parrying_dagger"));
        assertEquals(5, c.parry.window("medium_shield"));
        assertEquals(4, c.parry.window("dagger"));
        assertEquals(65, c.guard.twoHanded("greatsword"));
        assertEquals(50, c.guard.twoHanded("straight_sword"));
        assertEquals(cfg.parry, c.parry);
        assertEquals(cfg.guard, c.guard);
        // 민첩의 공격 속도: 이름이 같은 열쇠의 예전 값 (B 기준 표) 은 지금 판의 기본과 같다. 근력은 지금 판의 곡선 (예전 파일에 없다)
        assertEquals(0.30, c.stats.attackSpeed.at(99), 1e-9);
        assertEquals(0.10, c.stats.attackSpeed.at(20), 1e-9);
        assertEquals(0.28, c.stats.strAttack.at(20), 1e-9);
        assertEquals(0.28, c.stats.intSpell.at(20), 1e-9);
        for (int x = 1; x <= 99; x++) assertEquals(cfg.stats.attackSpeed.at(x), c.stats.attackSpeed.at(x), 1e-9, "민첩 " + x);
        // 읽지 않은 예전 열쇠는 알린다 (Souls 가 서버 기록에)
        assertEquals(Config.LEGACY_STATS, c.legacy);
        assertTrue(cfg.legacy.isEmpty(), "지금 판의 config.yml 에는 예전 열쇠가 없다");
        // M1 P1a: 적을 치는 다리와 바닐라 공격 대기의 한 주기 (MoveRunner 가 알린다)
        assertEquals(Config.LEGACY_PVE, c.legacyPve);
        assertTrue(cfg.legacyPve.isEmpty(), "지금 판의 config.yml 에는 pve 절이 없다");
        // 예전 파일에 없는 M1 절은 jar 기본값 (빈 절이 아니다)
        assertEquals(cfg.tuning.moves, c.tuning.moves);
        assertEquals(cfg.tuning.input, c.tuning.input);
    }

    /** M1 P1a: combat.input·combat.moves 의 기본값 (3.6). 코드의 기본값 (빈 설정) 도 같다. */
    @Test
    void moveDefaults() {
        var in = cfg.tuning.input;
        assertEquals(6, in.buffer());
        assertEquals(6, in.acceptBefore());
        assertEquals(1, in.fakeSwingWindow());
        assertEquals(2, in.echoWindow());
        var m = cfg.tuning.moves;
        assertEquals(java.util.List.of(100.0, 105.0, 115.0), m.light());
        assertEquals(115, m.lightMv(5), 1e-9, "목록보다 긴 단은 마지막 값");
        assertEquals(160, m.heavy(), 1e-9);
        assertEquals(115, m.running(), 1e-9);
        assertEquals(110, m.roll(), 1e-9);
        assertEquals(1.15, m.costRunning(), 1e-9);
        assertEquals(0.5, m.slowStartup(), 1e-9);
        assertEquals(0.5, m.slowActive(), 1e-9);
        assertEquals(0.25, m.slowRecovery(), 1e-9);
        assertEquals(10, m.minCycle());
        assertEquals(2, m.minStartup());
        assertEquals(4, m.minRecovery());
        assertEquals(0.4, m.cancelAt(), 1e-9);
        assertEquals(1.2, m.vertical(), 1e-9);
        assertEquals(-1, m.rollFrom());
        assertEquals(6, m.rollTo());
        assertEquals(java.util.List.of(10, 20, 30, 40, 60, 99), m.swingTiers());
        assertTrue(m.attackSpeed() >= 4, "서버가 휘두른 뒤 주무기가 내려가지 않게 4 이상 (S3)");
        assertEquals(4, m.comboGrace());
        Config bare = new Config(new org.bukkit.configuration.file.YamlConfiguration());
        assertEquals(m, bare.tuning.moves, "jar 의 config.yml 과 코드의 기본값이 같다");
        assertEquals(in, bare.tuning.input);
        assertFalse(TestFiles.yaml("config.yml").contains("pve"), "pve 절은 없앴다");
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
