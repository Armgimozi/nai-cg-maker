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
    void difficultyFloorRampInterpolatesHpDamageTelegraphOnly() {
        Difficulty nm = Difficulty.NIGHTMARE.withRamp(Difficulty.Ramp.NIGHTMARE);
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
        // 어려움: 1층 1.2/1.15/0.95 → 4층부터 1.5/1.4/0.85
        Difficulty hard = Difficulty.HARD.withRamp(Difficulty.Ramp.HARD);
        assertRamp(hard.atFloor(1), 1.2, 1.15, 0.95);
        assertRamp(hard.atFloor(2), 1.3, 1.15 + 0.25 / 3, 0.95 - 0.1 / 3);
        assertRamp(hard.atFloor(4), 1.5, 1.4, 0.85);
        // 램프 없는 난이도·상수는 모든 층 같은 값
        assertSame(Difficulty.NORMAL, Difficulty.NORMAL.atFloor(1));
        assertEquals(1.0, Difficulty.NIGHTMARE.rampProgress(1), 1e-9);
        assertEquals(1.0, new Difficulty.Ramp(3, 3, 1, 1, 1).progress(1), 1e-9, "full ≤ from = 램프 없음");
    }

    private static void assertRamp(Difficulty d, double hp, double damage, double telegraph) {
        assertEquals(hp, d.hp(), 1e-9, "hp");
        assertEquals(damage, d.damage(), 1e-9, "damage");
        assertEquals(telegraph, d.telegraph(), 1e-9, "telegraph");
    }

    @Test
    void instanceContextAppliesFloorRampAndSoloOnce() {
        Difficulty nm = Difficulty.NIGHTMARE.withRamp(Difficulty.Ramp.NIGHTMARE);
        InstanceContext solo1 = InstanceContext.adhoc(1, 1, nm, PartyScaling.DEFAULT);
        assertEquals(1.8 * 0.85, solo1.hpMultiplier(), 1e-9);
        assertEquals(1.6 * 0.85, solo1.damageMultiplier(), 1e-9);
        assertEquals(1.8, solo1.dropMultiplier(), 1e-9);
        assertEquals(1.7, solo1.xpMultiplier(), 1e-9);
        assertEquals(0.85, solo1.windup(1.0), 1e-9);
        assertEquals(0.0, solo1.rampProgress(), 1e-9);
        assertNull(solo1.difficulty().ramp());
        // 6층 이상은 지금과 같은 값 (솔로 ×0.85 만)
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
        assertEquals(1.5 * (1 + 0.6 * 3), ctx.hpMultiplier(), 1e-9);
        assertEquals(1.4 * (1 + 0.08 * 3), ctx.damageMultiplier(), 1e-9);
        assertEquals(1.3 * (1 + 0.05 * 3), ctx.dropMultiplier(), 1e-9);
        assertEquals(1.3, ctx.xpMultiplier(), 1e-9);
        assertEquals(0.85, ctx.windup(1.0), 1e-9);
        // 최소 0.5초 보장
        assertEquals(0.5, InstanceContext.adhoc(1, 1, Difficulty.NIGHTMARE, PartyScaling.DEFAULT).windup(0.6), 1e-9);
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
                  hard: {name: "어려움", hp: 1.6, damage: 1.4, drop: 1.3, xp: 1.3, telegraph: 0.85}
                party: {max_size: 10, hp_per_member: 0.5, dmg_per_member: 0.1}
                """);
        Settings s = new Settings(y);
        assertFalse(s.isDifficultySet());
        assertEquals("normal", s.difficulty().id());
        assertEquals(1.6, s.difficulty("hard").hp(), 1e-9);
        assertEquals(0.6, s.difficulty("easy").damage(), 1e-9); // 기본 프리셋 유지
        assertEquals(10, s.party().maxSize());
        assertEquals(0.5, s.party().hpPerMember(), 1e-9);
        // 예전 config.yml (ramp·solo 키 없음) 도 코드 기본값으로 켜진다
        assertEquals(1.2, s.difficulty("hard").atFloor(1).hp(), 1e-9);
        assertEquals(1.6, s.difficulty("hard").atFloor(4).hp(), 1e-9);
        assertEquals(1.8, s.difficulty("nightmare").atFloor(1).hp(), 1e-9);
        assertNull(s.difficulty("easy").ramp());
        assertNull(s.difficulty("normal").ramp());
        assertEquals(0.85, s.party().hp(1), 1e-9);
        assertEquals(0.85, s.party().damage(1), 1e-9);

        y.set("difficulty", "nightmare");
        Settings s2 = new Settings(y);
        assertTrue(s2.isDifficultySet());
        assertEquals(2.4, s2.difficulty().hp(), 1e-9);
        y.set("difficulty", "bogus");
        assertFalse(new Settings(y).isDifficultySet());
    }

    @Test
    void settingsRampKeysDefaultsAndDisable() throws Exception {
        // 키가 없거나 비어 있으면 코드 기본값, 끄기는 enabled: false (또는 false), 일부만 쓰면 나머지는 기본값
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
        assertEquals(Difficulty.Ramp.HARD, s.difficulty("hard").ramp());
        assertNull(s.difficulty("nightmare").ramp());
        assertEquals(2.4, s.difficulty("nightmare").atFloor(1).hp(), 1e-9);
        Difficulty insane = s.difficulty("insane");
        assertEquals(new Difficulty.Ramp(1, 5, 2.0, 2.5, 0.6), insane.ramp());
        assertEquals(2.5, insane.atFloor(3).hp(), 1e-9);
        assertEquals(2.5, insane.atFloor(1).damage(), 1e-9);
        assertNull(s.difficulty("brutal").ramp(), "full_floor ≤ from_floor = 램프 없음");
        assertEquals(1.0, s.party().hp(1), 1e-9);
        assertEquals(1.5, s.party().damage(1), 1e-9, "0.1~1.5 로 자름");

        // 일부 키만: 빠진 값은 기본 램프 값. hp 를 기본보다 낮춘 서버는 시작 값이 원래 값을 넘지 않게
        YamlConfiguration y2 = new YamlConfiguration();
        y2.loadFromString("""
                difficulties:
                  nightmare: {hp: 2.4, damage: 2.0, telegraph: 0.7, ramp: {full_floor: 8}}
                  hard: {hp: 1.1, damage: 1.4, telegraph: 0.85}
                """);
        Settings s2 = new Settings(y2);
        assertEquals(new Difficulty.Ramp(1, 8, 1.8, 1.6, 0.85), s2.difficulty("nightmare").ramp());
        assertEquals(1.1, s2.difficulty("hard").atFloor(1).hp(), 1e-9);
        assertEquals(1.15, s2.difficulty("hard").atFloor(1).damage(), 1e-9);

        assertNull(new Settings(yaml("difficulties: {nightmare: {ramp: false}}")).difficulty("nightmare").ramp());

        // difficulties 섹션 자체가 없어도 어려움·악몽 램프는 켜진다
        Settings bare = new Settings(new YamlConfiguration());
        assertEquals(Difficulty.Ramp.NIGHTMARE, bare.difficulty("nightmare").ramp());
        assertEquals(Difficulty.Ramp.HARD, bare.difficulty("hard").ramp());
        assertEquals(0.85, bare.party().hp(1), 1e-9);
    }

    @Test
    void existingServerConfigWithJarDefaultsKeepsNewBehaviour() throws Exception {
        // 기존 서버: plugins/Labyrinth/config.yml 은 덮어쓰지 않으므로 새 키가 없다. JavaPlugin.getConfig() 처럼 jar 값을 defaults 로 건다
        // (Bukkit 은 이때 빠진 섹션을 '빈 섹션'으로 돌려준다 → 코드 기본값으로 켜져야 한다).
        YamlConfiguration jar = new YamlConfiguration();
        jar.load(new java.io.File("src/main/resources/config.yml"));
        YamlConfiguration old = yaml("""
                difficulty: nightmare
                difficulties:
                  easy:      {name: "쉬움",   hp: 0.7, damage: 0.6, drop: 0.8, xp: 0.8, telegraph: 1.3}
                  normal:    {name: "보통",   hp: 1.0, damage: 1.0, drop: 1.0, xp: 1.0, telegraph: 1.0}
                  hard:      {name: "어려움", hp: 1.5, damage: 1.4, drop: 1.3, xp: 1.3, telegraph: 0.85}
                  nightmare: {name: "악몽",   hp: 2.4, damage: 2.0, drop: 1.8, xp: 1.7, telegraph: 0.7}
                party:
                  max_size: 10
                  hp_per_member: 0.6
                  dmg_per_member: 0.08
                  reward_per_member: 0.05
                  invite_timeout: 60
                """);
        old.setDefaults(jar);
        Settings s = new Settings(old);
        assertEquals(Difficulty.Ramp.NIGHTMARE, s.difficulty().ramp());
        assertEquals(Difficulty.Ramp.HARD, s.difficulty("hard").ramp());
        assertEquals(0.85, s.party().hp(1), 1e-9);
        assertEquals(0.85, s.party().damage(1), 1e-9);
        assertEquals(Settings.DEFAULT_STARTER_KIT, s.starterKit());
        InstanceContext ctx = InstanceContext.adhoc(1, 1, s.difficulty(), s.party());
        assertEquals(1.8 * 0.85, ctx.hpMultiplier(), 1e-9);
        assertEquals(1.6 * 0.85, ctx.damageMultiplier(), 1e-9);

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
        assertEquals(1.0, so.party().hp(1), 1e-9);
        assertTrue(so.starterKit().isEmpty());
    }

    @Test
    void settingsStarterKitDefaultsAndDisable() throws Exception {
        // 키가 없으면 코드 기본값 (수련생 4종 + 하급 치유 물약 5)
        List<Settings.KitItem> def = new Settings(new YamlConfiguration()).starterKit();
        assertEquals(Settings.DEFAULT_STARTER_KIT, def);
        assertEquals(5, def.size());
        assertEquals(new Settings.KitItem("minor_healing_potion", 5), def.get(4));
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
        assertEquals(10, s.party().maxSize());
        // jar 값 = 코드 기본값 (기존 서버에 키가 없을 때와 같은 동작)
        assertEquals(Difficulty.Ramp.HARD, s.difficulty("hard").ramp());
        assertEquals(Difficulty.Ramp.NIGHTMARE, s.difficulty("nightmare").ramp());
        assertNull(s.difficulty("normal").ramp());
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
