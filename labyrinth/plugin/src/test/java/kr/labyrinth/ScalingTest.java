package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.PartyScaling;
import kr.labyrinth.core.Settings;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

class ScalingTest {

    @Test
    void partyScalingMatchesGdd() {
        PartyScaling ps = PartyScaling.DEFAULT;
        // 솔로 보정: 혼자일 때만 HP·피해 ×0.85, 보상은 그대로
        assertEquals(0.85, ps.hp(1), 1e-9);
        assertEquals(0.85, ps.damage(1), 1e-9);
        assertEquals(1.0, ps.reward(1), 1e-9);
        assertEquals(0.85, ps.hp(0), 1e-9);
        assertEquals(1.0 + 0.6, ps.hp(2), 1e-9);
        assertEquals(1.0 + 0.6 * 4, ps.hp(5), 1e-9);
        assertEquals(1.0 + 0.08 * 9, ps.damage(10), 1e-9);
        assertEquals(1.0 + 0.05 * 2, ps.reward(3), 1e-9);
        // 4인자 = 솔로 보정 없음
        PartyScaling plain = new PartyScaling(10, 0.6, 0.08, 0.05);
        assertEquals(1.0, plain.hp(1), 1e-9);
        assertEquals(1.0, plain.damage(1), 1e-9);
    }

    @Test
    void difficultiesAreOneSetForAllFloors() {
        // 0.3.3: 난이도마다 배율 한 벌 — 1층부터 마지막 층까지 같은 값, 보스 기믹 진행도도 1
        assertRamp(Difficulty.HARD, 1.45, 1.3, 0.9); // 0.3.5: 어려움 HP 1.4 → 1.45
        assertRamp(Difficulty.NIGHTMARE, 1.8, 1.6, 0.85);
        // 0.3.5.2: 보상은 난이도와 상관없이 1.0
        for (Difficulty d : List.of(Difficulty.EASY, Difficulty.NORMAL, Difficulty.HARD, Difficulty.NIGHTMARE)) {
            assertEquals(1.0, d.drop(), 1e-9, d.id());
            assertEquals(1.0, d.xp(), 1e-9, d.id());
        }
        for (Difficulty d : List.of(Difficulty.EASY, Difficulty.NORMAL, Difficulty.HARD, Difficulty.NIGHTMARE)) {
            assertNull(d.ramp(), d.id());
            assertSame(d, d.atFloor(1));
            assertSame(d, d.atFloor(10));
            assertEquals(1.0, d.rampProgress(1), 1e-9);
            assertFalse(d.rampsAtFloor1());
            assertSame(d, Difficulty.defaultFor(d.id()));
        }
        assertNull(Difficulty.defaultFor("insane"));
        assertNull(Difficulty.Ramp.legacy032("normal"));
        // 보통 < 어려움 < 악몽 (HP·피해는 커지고 경고 시간은 짧아진다)
        assertTrue(Difficulty.NORMAL.hp() < Difficulty.HARD.hp() && Difficulty.HARD.hp() < Difficulty.NIGHTMARE.hp());
        assertTrue(Difficulty.NORMAL.damage() < Difficulty.HARD.damage() && Difficulty.HARD.damage() < Difficulty.NIGHTMARE.damage());
        assertTrue(Difficulty.NORMAL.telegraph() > Difficulty.HARD.telegraph() && Difficulty.HARD.telegraph() > Difficulty.NIGHTMARE.telegraph());
    }

    @Test
    void handWrittenFloorRampInterpolatesHpDamageTelegraphOnly() {
        // 관리자가 직접 적은 층 램프는 계속 따른다 (예: 0.3.2 의 악몽 값 2.4/2.0/0.7 + 1→6층 램프)
        Difficulty nm = Difficulty.LEGACY_NIGHTMARE_032.withRamp(Difficulty.Ramp.LEGACY_NIGHTMARE_032);
        // 1층 1.8/1.6/0.85 → 3층 2.04/1.76/0.79 → 6층부터 원래 2.4/2.0/0.7
        assertRamp(nm.atFloor(1), 1.8, 1.6, 0.85);
        assertRamp(nm.atFloor(2), 1.92, 1.68, 0.82);
        assertRamp(nm.atFloor(3), 2.04, 1.76, 0.79);
        assertRamp(nm.atFloor(5), 2.28, 1.92, 0.73);
        assertRamp(nm.atFloor(6), 2.4, 2.0, 0.7);
        assertRamp(nm.atFloor(10), 2.4, 2.0, 0.7);
        assertRamp(nm.atFloor(0), 1.8, 1.6, 0.85);
        // 보상(drop·xp)·id·이름은 1층부터 그대로
        assertEquals(1.8, nm.atFloor(1).drop(), 1e-9);
        assertEquals(1.7, nm.atFloor(1).xp(), 1e-9);
        assertEquals("nightmare", nm.atFloor(1).id());
        assertEquals("악몽", nm.atFloor(1).name());
        // 진행도 (보스 기믹 배율용)
        assertEquals(0.0, nm.rampProgress(1), 1e-9);
        assertEquals(0.4, nm.rampProgress(3), 1e-9);
        assertEquals(0.6, nm.rampProgress(4), 1e-9);
        assertEquals(1.0, nm.rampProgress(9), 1e-9);
        // 실효값에는 램프가 없다 → 두 번 적용되지 않음
        assertNull(nm.atFloor(1).ramp());
        assertRamp(nm.atFloor(1).atFloor(6), 1.8, 1.6, 0.85);
        assertEquals(1.0, nm.atFloor(1).rampProgress(1), 1e-9);
        // 새 어려움 값 위에 직접 적은 1→4층 램프
        Difficulty hard = Difficulty.HARD.withRamp(new Difficulty.Ramp(1, 4, 1.1, 1.0, 1.0));
        assertRamp(hard.atFloor(1), 1.1, 1.0, 1.0);
        assertRamp(hard.atFloor(2), 1.1 + 0.35 / 3, 1.1, 1.0 - 0.1 / 3);
        assertRamp(hard.atFloor(4), 1.45, 1.3, 0.9);
        assertTrue(hard.rampsAtFloor1());
        assertEquals(1.0, new Difficulty.Ramp(3, 3, 1, 1, 1).progress(1), 1e-9, "full ≤ from = 램프 없음");
    }

    private static void assertRamp(Difficulty d, double hp, double damage, double telegraph) {
        assertEquals(hp, d.hp(), 1e-9, "hp");
        assertEquals(damage, d.damage(), 1e-9, "damage");
        assertEquals(telegraph, d.telegraph(), 1e-9, "telegraph");
    }

    @Test
    void instanceContextUsesOneSetOnEveryFloor() {
        // 기본: 1층·6층·10층 모두 악몽 1.8/1.6 × 솔로 0.85, 보스 기믹 진행도 1
        for (int floor : new int[] {1, 3, 6, 10}) {
            InstanceContext solo = InstanceContext.adhoc(floor, 1, Difficulty.NIGHTMARE, PartyScaling.DEFAULT);
            assertEquals(1.8 * 0.85, solo.hpMultiplier(), 1e-9, "층 " + floor);
            assertEquals(1.6 * 0.85, solo.damageMultiplier(), 1e-9);
            assertEquals(1.0, solo.dropMultiplier(), 1e-9);   // 0.3.5.2: 보상은 난이도와 상관없이 1.0
            assertEquals(1.0, solo.xpMultiplier(), 1e-9);
            assertEquals(0.85, solo.windup(1.0), 1e-9);
            assertEquals(1.0, solo.rampProgress(), 1e-9);
            assertSame(Difficulty.NIGHTMARE, solo.difficulty());
        }
        InstanceContext party = InstanceContext.adhoc(6, 4, Difficulty.HARD, PartyScaling.DEFAULT);
        assertEquals(1.45 * (1 + 0.6 * 3), party.hpMultiplier(), 1e-9);
        assertEquals(1.3 * (1 + 0.08 * 3), party.damageMultiplier(), 1e-9);
        assertEquals(1.0, party.rampProgress(), 1e-9);
    }

    @Test
    void instanceContextAppliesHandWrittenRampAndSoloOnce() {
        Difficulty nm = Difficulty.LEGACY_NIGHTMARE_032.withRamp(Difficulty.Ramp.LEGACY_NIGHTMARE_032);
        InstanceContext solo1 = InstanceContext.adhoc(1, 1, nm, PartyScaling.DEFAULT);
        assertEquals(1.8 * 0.85, solo1.hpMultiplier(), 1e-9);
        assertEquals(1.6 * 0.85, solo1.damageMultiplier(), 1e-9);
        assertEquals(1.8, solo1.dropMultiplier(), 1e-9);
        assertEquals(1.7, solo1.xpMultiplier(), 1e-9);
        assertEquals(0.85, solo1.windup(1.0), 1e-9);
        assertEquals(0.0, solo1.rampProgress(), 1e-9);
        assertNull(solo1.difficulty().ramp());
        // 6층 이상은 원래 값 (솔로 ×0.85 만)
        InstanceContext solo6 = InstanceContext.adhoc(6, 1, nm, PartyScaling.DEFAULT);
        assertEquals(2.4 * 0.85, solo6.hpMultiplier(), 1e-9);
        assertEquals(1.0, solo6.rampProgress(), 1e-9);
        // 4인 파티 3층
        InstanceContext party3 = InstanceContext.adhoc(3, 4, nm, PartyScaling.DEFAULT);
        assertEquals(2.04 * (1 + 0.6 * 3), party3.hpMultiplier(), 1e-9);
        assertEquals(1.76 * (1 + 0.08 * 3), party3.damageMultiplier(), 1e-9);
        // 대체 보스: 이미 층 값인 난이도를 감싸도 다시 램프하지 않고, 진행도는 원래 ctx 것을 이어받는다
        Difficulty d = solo1.difficulty();
        Difficulty boosted = new Difficulty(d.id(), d.name(), d.hp() * 3, d.damage() * 1.5, d.drop(), d.xp(), d.telegraph());
        InstanceContext bossCtx = new InstanceContext(solo1.id(), solo1.floor(), solo1.members(), boosted, solo1.rampProgress(),
                solo1.scaling(), null, solo1.startedAt());
        assertEquals(1.8 * 3 * 0.85, bossCtx.hpMultiplier(), 1e-9);
        assertEquals(0.0, bossCtx.rampProgress(), 1e-9);
    }

    @Test
    void instanceMultipliersCombineDifficultyAndParty() {
        InstanceContext ctx = InstanceContext.adhoc(3, 4, Difficulty.HARD, PartyScaling.DEFAULT);
        assertEquals(4, ctx.partySize());
        assertEquals(1.45 * (1 + 0.6 * 3), ctx.hpMultiplier(), 1e-9);
        assertEquals(1.3 * (1 + 0.08 * 3), ctx.damageMultiplier(), 1e-9);
        assertEquals(1.0 * (1 + 0.05 * 3), ctx.dropMultiplier(), 1e-9);   // 난이도 보상 1.0 × 인원
        assertEquals(1.0, ctx.xpMultiplier(), 1e-9);
        assertEquals(0.9, ctx.windup(1.0), 1e-9);
        // 최소 0.5초 보장
        assertEquals(0.5, InstanceContext.adhoc(1, 1, Difficulty.NIGHTMARE, PartyScaling.DEFAULT).windup(0.5), 1e-9);
    }

    @Test
    void gddPerMemberParamRules() {
        Params p = Params.of(Map.of("count_base", 2, "count_per_member", 0.5, "pillars", 4, "pillars_per_members", 3,
                "solo_time", 25, "time", 20, "p2_damage", 1.8, "damage", 1.2));
        assertEquals(2, p.scaled("count", 1, 0), 1e-9);
        assertEquals(2 + Math.floor(4 * 0.5), p.scaled("count", 5, 0), 1e-9);
        assertEquals(4 + 2, p.scaled("pillars", 7, 0), 1e-9);
        assertEquals(25, p.scaled("time", 1, 0), 1e-9);
        assertEquals(20, p.scaled("time", 3, 0), 1e-9);
        assertEquals(1.2, p.phased("damage", 1, 0), 1e-9);
        assertEquals(1.8, p.phased("damage", 3, 0), 1e-9);
    }

    @Test
    void settingsReadDifficultyPresetsAndParty() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("""
                difficulty: ""
                difficulties:
                  hard: {name: "어려움", hp: 1.6, damage: 1.35, drop: 1.3, xp: 1.3, telegraph: 0.8}
                party: {max_size: 8, hp_per_member: 0.5, dmg_per_member: 0.1}
                """);
        Settings s = new Settings(y);
        assertFalse(s.isDifficultySet());
        assertEquals("normal", s.difficulty().id());
        // 직접 고친 값 그대로 — drop·xp 1.3 은 예전 jar 기본값이라 1.0 으로 올라감 (0.3.5.2)
        assertEquals(new Difficulty("hard", "어려움", 1.6, 1.35, 1.0, 1.0, 0.8), s.difficulty("hard"));
        assertEquals(1.5, new Settings(yaml("difficulties: {hard: {drop: 1.5, xp: 1.2}}")).difficulty("hard").drop(), 1e-9, "다른 값은 그대로");
        assertEquals(0.6, s.difficulty("easy").damage(), 1e-9); // 기본 프리셋 유지
        assertEquals(8, s.party().maxSize()); // 직접 고친 값 그대로
        assertEquals(0.5, s.party().hpPerMember(), 1e-9);
        // 층 램프 없음 — 모든 층 같은 값, 적지 않은 악몽은 코드 기본값
        assertEquals(1.6, s.difficulty("hard").atFloor(1).hp(), 1e-9);
        assertEquals(1.6, s.difficulty("hard").atFloor(10).hp(), 1e-9);
        assertEquals(Difficulty.NIGHTMARE, s.difficulty("nightmare"));
        for (Difficulty d : s.difficulties().values()) assertNull(d.ramp(), d.id());
        assertEquals(0.85, s.party().hp(1), 1e-9);
        assertEquals(0.85, s.party().damage(1), 1e-9);

        y.set("difficulty", "nightmare");
        Settings s2 = new Settings(y);
        assertTrue(s2.isDifficultySet());
        assertEquals(1.8, s2.difficulty().hp(), 1e-9);
        y.set("difficulty", "bogus");
        assertFalse(new Settings(y).isDifficultySet());
    }

    @Test
    void settingsRampKeysOnlyWhenHandWritten() throws Exception {
        // 램프는 직접 적었을 때만: 비어 있으면 없음, 끄기는 enabled: false (또는 false), 일부만 쓰면 나머지는 0.3.2 기본 램프 값
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("""
                difficulties:
                  hard: {hp: 1.5, damage: 1.4, ramp: {}}
                  nightmare: {hp: 2.4, damage: 2.0, telegraph: 0.7, ramp: {enabled: false}}
                  insane: {name: "광기", hp: 3.0, damage: 2.5, drop: 2.0, xp: 2.0, telegraph: 0.6,
                           ramp: {full_floor: 5, start: {hp: 2.0}}}
                  brutal: {hp: 2.0, ramp: {from_floor: 4, full_floor: 4}}
                party: {solo_hp: 1.0, solo_damage: 9}
                """);
        Settings s = new Settings(y);
        // 빈 ramp = 없음, 0.3.2 값(1.5/1.4)은 새 기본값으로
        assertEquals(Difficulty.HARD, s.difficulty("hard"));
        // ramp 를 직접 끈 난이도는 적힌 숫자를 1층부터 그대로 (예전 값 승격 없음)
        assertNull(s.difficulty("nightmare").ramp());
        assertEquals(2.4, s.difficulty("nightmare").atFloor(1).hp(), 1e-9);
        assertEquals(0.7, s.difficulty("nightmare").atFloor(1).telegraph(), 1e-9);
        Difficulty insane = s.difficulty("insane");
        assertEquals(new Difficulty.Ramp(1, 5, 2.0, 2.5, 0.6), insane.ramp());
        assertEquals(2.5, insane.atFloor(3).hp(), 1e-9);
        assertEquals(2.5, insane.atFloor(1).damage(), 1e-9);
        assertTrue(insane.rampsAtFloor1());
        assertNull(s.difficulty("brutal").ramp(), "full_floor ≤ from_floor = 램프 없음");
        assertEquals(1.0, s.party().hp(1), 1e-9);
        assertEquals(1.5, s.party().damage(1), 1e-9, "0.1~1.5 로 자름");

        // 직접 고친 램프(full_floor 8)는 계속 따른다 — 빠진 시작 값은 0.3.2 기본 램프 값, 숫자는 적힌 그대로
        YamlConfiguration y2 = new YamlConfiguration();
        y2.loadFromString("""
                difficulties:
                  nightmare: {hp: 2.4, damage: 2.0, telegraph: 0.7, ramp: {full_floor: 8}}
                  hard: {hp: 1.1, damage: 1.4, telegraph: 0.85, ramp: {full_floor: 4, start: {hp: 1.0}}}
                """);
        Settings s2 = new Settings(y2);
        Difficulty nm = s2.difficulty("nightmare");
        assertEquals(new Difficulty.Ramp(1, 8, 1.8, 1.6, 0.85), nm.ramp());
        assertEquals(1.8, nm.atFloor(1).hp(), 1e-9);
        assertEquals(2.4, nm.atFloor(8).hp(), 1e-9);
        // hp 를 낮춘 서버: 빠진 시작 값이 원래 값보다 세지 않게 (damage 1.15 ≤ 1.4, telegraph 0.95 ≥ 0.85)
        Difficulty hard = s2.difficulty("hard");
        assertEquals(new Difficulty.Ramp(1, 4, 1.0, 1.15, 0.95), hard.ramp());
        assertEquals(1.1, hard.atFloor(4).hp(), 1e-9);
        assertEquals(1.4, hard.atFloor(4).damage(), 1e-9);

        assertNull(new Settings(yaml("difficulties: {nightmare: {ramp: false}}")).difficulty("nightmare").ramp());

        // difficulties 섹션 자체가 없으면 코드 기본값 (램프 없음)
        Settings bare = new Settings(new YamlConfiguration());
        assertEquals(Difficulty.NIGHTMARE, bare.difficulty("nightmare"));
        assertEquals(Difficulty.HARD, bare.difficulty("hard"));
        assertEquals(0.85, bare.party().hp(1), 1e-9);
    }

    /** 0.3.2 jar 의 config.yml 이 그대로 적어 둔 난이도 묶음 (기존 서버 plugins/Labyrinth/config.yml). */
    private static final String CONFIG_032 = """
            difficulty: nightmare
            difficulties:
              easy:      {name: "쉬움",   hp: 0.7, damage: 0.6, drop: 0.8, xp: 0.8, telegraph: 1.3}
              normal:    {name: "보통",   hp: 1.0, damage: 1.0, drop: 1.0, xp: 1.0, telegraph: 1.0}
              hard:      {name: "어려움", hp: 1.5, damage: 1.4, drop: 1.3, xp: 1.3, telegraph: 0.85,
                          ramp: {from_floor: 1, full_floor: 4, start: {hp: 1.2, damage: 1.15, telegraph: 0.95}}}
              nightmare: {name: "악몽",   hp: 2.4, damage: 2.0, drop: 1.8, xp: 1.7, telegraph: 0.7,
                          ramp: {from_floor: 1, full_floor: 6, start: {hp: 1.8, damage: 1.6, telegraph: 0.85}}}
            """;

    /** 0.3.4 jar 의 config.yml 이 적어 둔 어려움 (HP 1.4). */
    private static final String CONFIG_034 = """
            difficulties:
              hard:      {name: "어려움", hp: 1.4, damage: 1.3, drop: 1.3, xp: 1.3, telegraph: 0.9}
              nightmare: {name: "악몽",   hp: 1.8, damage: 1.6, drop: 1.8, xp: 1.7, telegraph: 0.85}
            """;

    @Test
    void legacy034HardHpUpgradesTo145EditedValuesKept() throws Exception {
        // 0.3.5: 손대지 않은 0.3.4 어려움 HP 1.4 → 1.45 (combat_spec §10.1, 0.3.2 승격과 같은 방식)
        Settings s = new Settings(yaml(CONFIG_034));
        assertEquals(Difficulty.HARD, s.difficulty("hard"));
        assertEquals(1.45, s.difficulty("hard").hp(), 1e-9);
        assertEquals(Difficulty.NIGHTMARE, s.difficulty("nightmare"));
        assertEquals(Difficulty.LEGACY_HARD_034, Difficulty.legacy034("hard"));
        assertNull(Difficulty.legacy034("nightmare"));
        // 직접 고친 값은 키마다 그대로 (HP 만 고친 서버는 HP 만, 피해를 고친 서버는 HP 만 새 값)
        Settings edited = new Settings(yaml("""
                difficulties:
                  hard: {hp: 1.6, damage: 1.3, drop: 1.3, xp: 1.3, telegraph: 0.9}
                """));
        assertEquals(1.6, edited.difficulty("hard").hp(), 1e-9);
        Settings dmgEdited = new Settings(yaml("""
                difficulties:
                  hard: {hp: 1.4, damage: 1.5, drop: 1.3, xp: 1.3, telegraph: 0.9}
                """));
        assertEquals(1.45, dmgEdited.difficulty("hard").hp(), 1e-9);
        assertEquals(1.5, dmgEdited.difficulty("hard").damage(), 1e-9);
        // 0.3.2 값(1.5/1.4/0.85)을 둔 서버도 곧바로 새 값
        Settings v032 = new Settings(yaml("""
                difficulties:
                  hard: {hp: 1.5, damage: 1.4, telegraph: 0.85}
                """));
        assertEquals(Difficulty.HARD, v032.difficulty("hard"));
        // 직접 적은 램프가 있으면 숫자를 적힌 그대로 (승격 없음)
        Settings ramped = new Settings(yaml("""
                difficulties:
                  hard: {hp: 1.4, damage: 1.3, telegraph: 0.9, ramp: {from_floor: 1, full_floor: 4, start: {hp: 1.1}}}
                """));
        assertEquals(1.4, ramped.difficulty("hard").hp(), 1e-9);
    }

    @Test
    void combatKeysDefaultAndRead() throws Exception {
        Settings bare = new Settings(yaml("difficulty: normal"));
        Settings.Combat c = bare.combat();
        assertEquals(Settings.Combat.DEFAULT, c);
        assertEquals(0.25, c.attackIntervalMin(), 1e-9);
        assertEquals(0.35, c.earlyClickBuffer(), 1e-9);
        assertTrue(c.earlyClickSound());
        assertEquals(50, c.clickToleranceMs());
        assertEquals(1.2, c.jumpCrit(), 1e-9);
        assertTrue(c.bowFullDrawCue());
        assertEquals(1.6, bare.unarmedAttackSpeed(), 1e-9);
        assertTrue(bare.ignoredWeaponSpeedKeys().isEmpty());
        Settings custom = new Settings(yaml("""
                combat: {early_click_buffer: 0, early_click_sound: false, attack_interval_min: 0.3}
                weapon_attack_speed: {none: 2.0, sword_shield: 1.5, greatsword: 0.95}
                """));
        assertEquals(0.0, custom.combat().earlyClickBuffer(), 1e-9, "0 = 기억창 끔");
        assertFalse(custom.combat().earlyClickSound());
        assertEquals(0.3, custom.combat().attackIntervalMin(), 1e-9);
        assertEquals(2.0, custom.unarmedAttackSpeed(), 1e-9);
        assertEquals(List.of("sword_shield", "greatsword"), custom.ignoredWeaponSpeedKeys(), "예전 종류 키는 읽지 않음");
        // jar 의 config.yml = 코드 기본값
        YamlConfiguration jar = new YamlConfiguration();
        jar.load(new java.io.File("src/main/resources/config.yml"));
        Settings js = new Settings(jar);
        assertEquals(Settings.Combat.DEFAULT, js.combat());
        assertTrue(js.ignoredWeaponSpeedKeys().isEmpty());
        assertEquals(Difficulty.HARD, js.difficulty("hard"));
    }

    @Test
    void legacy032DifficultyValuesUpgradeToUnifiedDefaults() throws Exception {
        // 0.3.2 묶음을 그대로 둔 서버 = 손대지 않은 값 → 램프 없이 새 기본값 한 벌
        Settings s = new Settings(yaml(CONFIG_032));
        assertEquals(Difficulty.HARD, s.difficulty("hard"));
        assertEquals(Difficulty.NIGHTMARE, s.difficulty());
        assertEquals(Difficulty.EASY, s.difficulty("easy"));
        assertEquals(Difficulty.NORMAL, s.difficulty("normal"));
        for (int floor : new int[] {1, 6, 10}) {
            InstanceContext ctx = InstanceContext.adhoc(floor, 1, s.difficulty(), s.party());
            assertEquals(1.8 * 0.85, ctx.hpMultiplier(), 1e-9);
            assertEquals(1.6 * 0.85, ctx.damageMultiplier(), 1e-9);
            assertEquals(1.0, ctx.rampProgress(), 1e-9);
        }
        // 0.3.2 의 기본 램프를 하위 키 일부만 적었거나({} 포함) 빠진 키가 있어도 같은 램프면 통합
        Settings partial = new Settings(yaml("""
                difficulties:
                  nightmare: {hp: 2.4, damage: 2.0, telegraph: 0.7, ramp: {from_floor: 1, full_floor: 6, start: {hp: 1.8, damage: 1.6}}}
                  hard: {hp: 1.5, damage: 1.4, telegraph: 0.85, ramp: {}}
                """));
        assertEquals(Difficulty.NIGHTMARE, partial.difficulty("nightmare"));
        assertEquals(Difficulty.HARD, partial.difficulty("hard"));
        // 0.3.2 의 램프 이전 판(램프 키 없음)도 같은 값이면 새 기본값
        assertEquals(Difficulty.NIGHTMARE, new Settings(yaml(
                "difficulties: {nightmare: {name: \"악몽\", hp: 2.4, damage: 2.0, drop: 1.8, xp: 1.7, telegraph: 0.7}}"))
                .difficulty("nightmare"));
        // 키마다: 예전 값과 같은 키만 새 값 — hp 만 고친 악몽은 hp 그대로, damage·telegraph 는 새 기본값
        Difficulty mixed = new Settings(yaml("""
                difficulties:
                  nightmare: {name: "지옥", hp: 3.0, damage: 2.0, drop: 2.5, xp: 1.7, telegraph: 0.7,
                              ramp: {from_floor: 1, full_floor: 6, start: {hp: 1.8, damage: 1.6, telegraph: 0.85}}}
                """)).difficulty("nightmare");
        assertEquals(new Difficulty("nightmare", "지옥", 3.0, 1.6, 2.5, 1.0, 0.85), mixed); // xp 1.7 = 예전 기본값 → 1.0
        // 직접 고친 램프(시작 hp 1.5)는 따르고 숫자도 적힌 그대로
        Difficulty hand = new Settings(yaml("""
                difficulties:
                  nightmare: {hp: 2.4, damage: 2.0, telegraph: 0.7, ramp: {from_floor: 1, full_floor: 6, start: {hp: 1.5, damage: 1.6, telegraph: 0.85}}}
                """)).difficulty("nightmare");
        assertEquals(new Difficulty.Ramp(1, 6, 1.5, 1.6, 0.85), hand.ramp());
        assertEquals(1.5, hand.atFloor(1).hp(), 1e-9);
        assertEquals(2.4, hand.atFloor(6).hp(), 1e-9);
        // 예전 값을 일부러 쓰려면 ramp: false
        Difficulty kept = new Settings(yaml("difficulties: {nightmare: {hp: 2.4, damage: 2.0, telegraph: 0.7, ramp: false}}"))
                .difficulty("nightmare");
        assertEquals(2.4, kept.hp(), 1e-9);
        assertEquals(2.0, kept.damage(), 1e-9);
        assertEquals(0.7, kept.telegraph(), 1e-9);
        assertNull(kept.ramp());
        // 0.3.2 예전 값은 어려움·악몽만 — 쉬움·보통·사용자 난이도는 그대로
        assertEquals(1.5, new Settings(yaml("difficulties: {normal: {hp: 1.5}}")).difficulty("normal").hp(), 1e-9);
        assertEquals(2.4, new Settings(yaml("difficulties: {insane: {hp: 2.4, damage: 2.0}}")).difficulty("insane").hp(), 1e-9);
    }

    @Test
    void existingServerConfigWithJarDefaultsKeepsNewBehaviour() throws Exception {
        // 기존 서버: plugins/Labyrinth/config.yml 은 덮어쓰지 않으므로 새 키가 없다. JavaPlugin.getConfig() 처럼 jar 값을 defaults 로 건다
        // (Bukkit 은 이때 빠진 섹션을 '빈 섹션'으로 돌려준다 → 코드 기본값으로 켜져야 한다).
        YamlConfiguration jar = new YamlConfiguration();
        jar.load(new java.io.File("src/main/resources/config.yml"));
        YamlConfiguration old = yaml(CONFIG_032 + """
                party:
                  max_size: 10
                  hp_per_member: 0.6
                  dmg_per_member: 0.08
                  reward_per_member: 0.05
                  invite_timeout: 60
                """);
        old.setDefaults(jar);
        Settings s = new Settings(old);
        assertEquals(Difficulty.NIGHTMARE, s.difficulty());
        assertEquals(Difficulty.HARD, s.difficulty("hard"));
        assertEquals(0.85, s.party().hp(1), 1e-9);
        assertEquals(0.85, s.party().damage(1), 1e-9);
        assertEquals(Settings.DEFAULT_STARTER_KIT, s.starterKit());
        InstanceContext ctx = InstanceContext.adhoc(1, 1, s.difficulty(), s.party());
        assertEquals(1.8 * 0.85, ctx.hpMultiplier(), 1e-9);
        assertEquals(1.6 * 0.85, ctx.damageMultiplier(), 1e-9);
        assertEquals(ctx.hpMultiplier(), InstanceContext.adhoc(6, 1, s.difficulty(), s.party()).hpMultiplier(), 1e-9);

        // difficulties 를 아예 안 적은 서버도 jar 기본값 = 코드 기본값
        YamlConfiguration none = yaml("difficulty: hard");
        none.setDefaults(jar);
        assertEquals(Difficulty.HARD, new Settings(none).difficulty());

        // 끄기는 명시적으로
        YamlConfiguration off = yaml("""
                difficulties:
                  nightmare: {hp: 2.4, damage: 2.0, telegraph: 0.7, ramp: {enabled: false}}
                party: {solo_hp: 1.0, solo_damage: 1.0}
                starter_kit: {enabled: false}
                """);
        off.setDefaults(jar);
        Settings so = new Settings(off);
        assertNull(so.difficulty("nightmare").ramp());
        assertEquals(2.4, so.difficulty("nightmare").hp(), 1e-9);
        assertEquals(1.0, so.party().hp(1), 1e-9);
        assertTrue(so.starterKit().isEmpty());
    }

    @Test
    void settingsStarterKitDefaultsAndDisable() throws Exception {
        // 키가 없으면 코드 기본값 (수련생 4종 + 하급 치유 물약 10 · 마나 물약 5 · 귀환 주문서 2)
        List<Settings.KitItem> def = new Settings(new YamlConfiguration()).starterKit();
        assertEquals(Settings.DEFAULT_STARTER_KIT, def);
        assertEquals(7, def.size());
        assertEquals(new Settings.KitItem("minor_healing_potion", 10), def.get(4));
        assertEquals(List.of("novice_cap", "novice_tunic", "novice_trousers", "novice_boots"),
                def.subList(0, 4).stream().map(Settings.KitItem::item).toList());

        assertEquals(Settings.DEFAULT_STARTER_KIT, new Settings(yaml("starter_kit: {}")).starterKit(), "빈 섹션 = 기본값");
        assertTrue(new Settings(yaml("starter_kit: {enabled: false}")).starterKit().isEmpty());
        assertTrue(new Settings(yaml("starter_kit: false")).starterKit().isEmpty());
        assertEquals(Settings.DEFAULT_STARTER_KIT, new Settings(yaml("starter_kit: {enabled: true, items: []}")).starterKit(),
                "목록이 비면 기본값");
        Settings custom = new Settings(yaml("""
                starter_kit:
                  items:
                    - {item: bread, amount: 3}
                    - {item: " ", amount: 1}
                    - {item: torch}
                    - {item: stone, amount: 0}
                    - {item: arrow, amount: 200}
                """));
        assertEquals(List.of(new Settings.KitItem("bread", 3), new Settings.KitItem("torch", 1), new Settings.KitItem("arrow", 64)),
                custom.starterKit());
    }

    @Test
    void partyMaxSizeLegacyDefaultBecomesFive() throws Exception {
        // 0.3.5 까지 config.yml 에 적혀 있던 max_size: 10 은 손대지 않은 값 → 5 명
        assertEquals(5, new Settings(yaml("party: {max_size: 10}")).party().maxSize());
        assertEquals(5, new Settings(new YamlConfiguration()).party().maxSize(), "키 없음 = 5");
        assertEquals(3, new Settings(yaml("party: {max_size: 3}")).party().maxSize(), "직접 고친 값");
        assertEquals(1, new Settings(yaml("party: {max_size: 0}")).party().maxSize(), "최소 1");
    }

    private static YamlConfiguration yaml(String text) throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        return y;
    }

    @Test
    void bundledConfigParses() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.load(new java.io.File("src/main/resources/config.yml"));
        Settings s = new Settings(y);
        assertEquals(4, s.difficulties().size());
        assertEquals(Settings.DEFAULT_PARTY_MAX, s.party().maxSize());
        // jar 값 = 코드 기본값 (기존 서버에 키가 없을 때와 같은 동작), 층 램프 없음
        for (String id : List.of("easy", "normal", "hard", "nightmare")) {
            assertEquals(Difficulty.defaultFor(id), s.difficulty(id), id);
        }
        assertEquals(PartyScaling.DEFAULT, s.party());
        assertEquals(Settings.DEFAULT_STARTER_KIT, s.starterKit());
        assertEquals(50, s.level().max());
        assertEquals(5, s.level().pointsPerLevel());
        assertEquals(5, s.level().startPoints());
        assertTrue(s.pack().port() > 0);
        assertEquals("labyrinth_world", s.worldName());
    }

    @Test
    void levelOneStartsWithStatPoints() {
        Settings.Level lv = new Settings(new YamlConfiguration()).level();
        assertEquals(5, lv.startPoints());
        // Lv.1 부터 분배할 포인트가 있고, 레벨업마다 5 씩 더해진다
        assertEquals(5, lv.totalPointsAt(1));
        assertEquals(10, lv.totalPointsAt(2));
        assertEquals(250, lv.totalPointsAt(50));
        assertEquals(5, lv.totalPointsAt(0));
        // 한 번만: 이미 받은 만큼은 다시 주지 않고, 설정을 올리면 차이만, 내려도 거두지 않음
        assertEquals(5, lv.startPointsOwed(0));
        assertEquals(0, lv.startPointsOwed(5));
        assertEquals(2, lv.startPointsOwed(3));
        assertEquals(0, lv.startPointsOwed(8));

        YamlConfiguration y = new YamlConfiguration();
        y.set("level.start_points", 0);
        Settings.Level none = new Settings(y).level();
        assertEquals(0, none.startPointsOwed(0));
        assertEquals(5, none.totalPointsAt(2));
        y.set("level.start_points", -3);
        assertEquals(0, new Settings(y).level().startPoints());
    }
}
