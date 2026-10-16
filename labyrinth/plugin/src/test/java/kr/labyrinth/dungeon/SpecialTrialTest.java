package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.SplittableRandom;
import java.util.TreeSet;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.dungeon.rooms.SpecialTrial;
import kr.labyrinth.dungeon.rooms.SpecialTrial.Condition;
import kr.labyrinth.dungeon.rooms.SpecialTrial.Counters;
import kr.labyrinth.items.GearItemService;
import kr.labyrinth.items.loot.LootRoller;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 특별 시련 (GDD §10.1, gear_spec §6) — 순수 규칙: 굴림(시드 고정·확률·확정 카운터), 층마다 그 기믹이 쓸 수 있는 조건만,
 * 조건 4종 판정, 보상(조건이 깨져도 평소 상자는 그대로), dungeon.yml 기본값, 특별 상자 표, 확정 카운터 저장.
 */
class SpecialTrialTest {

    private static final DungeonConfig.Special CFG = DungeonConfig.Special.DEFAULT;
    private static final SpecialTrial.Rule RULE = new SpecialTrial.Rule(List.of(Condition.FLAWLESS, Condition.SWIFT), 60);
    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    // ── 굴림 ──────────────────────────────────────────────────────────────

    @Test
    void sameSeedSameTrial() {
        for (long seed = 0; seed < 500; seed++) {
            SpecialTrial a = SpecialTrial.pick(seed * 7919L, RULE, CFG, 0);
            SpecialTrial b = SpecialTrial.pick(seed * 7919L, RULE, CFG, 0);
            assertEquals(a, b, "seed " + seed);
        }
        assertEquals(SpecialTrial.seed(42L, 3), SpecialTrial.seed(42L, 3));
        assertFalse(SpecialTrial.seed(42L, 3) == SpecialTrial.seed(42L, 4), "방 번호가 달라도 같은 시드");
    }

    @Test
    void chanceHoldsOverTenThousandVisits() {
        int hit = 0;
        Map<Condition, Integer> conds = new HashMap<>();
        for (int i = 0; i < 10_000; i++) {
            SpecialTrial t = SpecialTrial.pick(SpecialTrial.seed(0x9E3779B97F4A7C15L * (i + 1), 5), RULE, CFG, 0);
            if (t == null) continue;
            hit++;
            conds.merge(t.condition(), 1, Integer::sum);
        }
        assertEquals(CFG.chance(), hit / 10_000.0, 0.02, "특별 시련 비율");
        // 후보 둘이 고르게
        assertEquals(0.5, conds.getOrDefault(Condition.FLAWLESS, 0) / (double) hit, 0.05);
    }

    @Test
    void pityForcesTheNextVisit() {
        for (long s = 0; s < 1000; s++) assertNotNull(SpecialTrial.pick(s, RULE, CFG, CFG.pityVisits()), "확정인데 안 나옴");
        int below = 0;
        for (long s = 0; s < 1000; s++) if (SpecialTrial.pick(s, RULE, CFG, CFG.pityVisits() - 1) != null) below++;
        assertTrue(below < 1000, "확정 전인데 늘 나옴");
        assertTrue(SpecialTrial.pityForced(3, 3));
        assertFalse(SpecialTrial.pityForced(2, 3));
        assertFalse(SpecialTrial.pityForced(99, 0), "pity_visits 0 = 끔");
        assertEquals(4, SpecialTrial.partyMiss(List.of(0, 4, 2)), "파티원 중 가장 큰 값");
        assertEquals(0, SpecialTrial.partyMiss(List.of()));
    }

    /** 30% + 3번 연속 못 보면 확정 → 실제로는 방문의 약 39.5%. */
    @Test
    void effectiveRateWithPityIsAboutThirtyNinePercent() {
        int miss = 0, special = 0, visits = 100_000;
        SplittableRandom seeds = new SplittableRandom(7);
        for (int v = 0; v < visits; v++) {
            SpecialTrial t = SpecialTrial.pick(seeds.nextLong(), RULE, CFG, miss);
            if (t != null) {
                special++;
                miss = 0;
            } else {
                miss++;
            }
        }
        assertEquals(0.395, special / (double) visits, 0.01);
    }

    @Test
    void offOrEmptyNeverPicks() {
        DungeonConfig.Special off = CFG.disabled();
        for (long s = 0; s < 200; s++) {
            assertNull(SpecialTrial.pick(s, RULE, off, 10));
            assertNull(SpecialTrial.pick(s, new SpecialTrial.Rule(List.of(), 0), CFG, 10));
        }
        assertNotNull(SpecialTrial.forced(1, RULE, off), "자가 진단 확정은 끔과 무관");
        assertNull(SpecialTrial.forced(1, new SpecialTrial.Rule(List.of(), 0), CFG));
    }

    // ── 층 규칙 ───────────────────────────────────────────────────────────

    /** gear_spec §6.3 기본표: 층 → 조건 후보 · 서두름 초. */
    private static final Map<Integer, List<Condition>> TABLE = Map.of(
            1, List.of(Condition.FLAWLESS, Condition.SWIFT), 2, List.of(Condition.UNSCATHED, Condition.ABSTAIN),
            3, List.of(Condition.ABSTAIN, Condition.SWIFT), 4, List.of(Condition.SWIFT, Condition.UNSCATHED),
            5, List.of(Condition.SWIFT, Condition.ABSTAIN), 6, List.of(Condition.SWIFT, Condition.UNSCATHED),
            7, List.of(Condition.FLAWLESS, Condition.UNSCATHED), 8, List.of(Condition.FLAWLESS, Condition.SWIFT),
            9, List.of(Condition.FLAWLESS, Condition.UNSCATHED), 10, List.of(Condition.UNSCATHED, Condition.ABSTAIN));
    private static final Map<Integer, Integer> SWIFT_SECONDS = Map.of(1, 60, 3, 90, 4, 42, 5, 70, 6, 84, 8, 126);
    /** 기믹의 제한 시간 (각 구현의 timeLimit(), floors.yml params 기준). */
    private static final Map<String, Integer> LIMITS = Map.of("lever_sequence", 0, "torch_relay", 120, "spore_purge", 180,
            "valve_flow", 60, "forge_bellows", 150, "lights_out", 120, "resonance_tune", 0, "book_cipher", 180,
            "gear_timing", 180, "void_trial", 0);

    @Test
    void everyFloorUsesOnlyConditionsItsGimmickSupports() {
        assertEquals(10, content.maxFloor());
        for (FloorDef f : content.floors().values()) {
            String g = f.gimmick();
            SpecialTrial.Rule rule = SpecialTrial.rule(g, f.specialTrial(), LIMITS.getOrDefault(g, 0), CFG);
            assertFalse(rule.isEmpty(), f.number() + "층 조건 후보 없음");
            for (Condition c : rule.conditions()) assertTrue(SpecialTrial.supports(g, c), f.number() + "층 " + g + " 이 " + c + " 를 못 씀");
            assertEquals(TABLE.get(f.number()), rule.conditions(), f.number() + "층 조건 후보 (gear_spec §6.3)");
            if (rule.conditions().contains(Condition.SWIFT)) {
                assertEquals(SWIFT_SECONDS.get(f.number()), rule.seconds(), f.number() + "층 서두름 초");
                assertTrue(rule.seconds() >= CFG.swiftMinSeconds());
                int limit = LIMITS.getOrDefault(g, 0);
                assertTrue(limit == 0 || rule.seconds() < limit, f.number() + "층 서두름 초가 제한 시간 이상");
            } else {
                assertFalse(SWIFT_SECONDS.containsKey(f.number()));
            }
        }
    }

    /** 무결을 쓰는 기믹 = 실수 자리에서 noteMistake() 를 부르는 기믹 (코드와 목록이 어긋나지 않게). */
    @Test
    void flawlessGimmicksAreExactlyThoseThatNoteMistakes() throws IOException {
        Path rooms = Path.of("src/main/java/kr/labyrinth/dungeon/rooms");
        String create = Files.readString(rooms.resolve("GimmickRoom.java"));
        Matcher m = Pattern.compile("case \"([a-z_]+)\" -> new (\\w+)\\(").matcher(create);
        Set<String> noting = new TreeSet<>();
        int n = 0;
        while (m.find()) {
            n++;
            String src = Files.readString(rooms.resolve("gimmicks").resolve(m.group(2) + ".java"));
            if (src.contains("noteMistake();")) noting.add(m.group(1));
        }
        assertEquals(10, n, "기믹 10종");
        assertEquals(new TreeSet<>(SpecialTrial.FLAWLESS_GIMMICKS), noting);
    }

    @Test
    void swiftSecondsFollowOverrideTableLimitAndMinimum() {
        Params over = Params.of(Map.of("conditions", List.of("swift"), "seconds", 10));
        assertEquals(CFG.swiftMinSeconds(), SpecialTrial.rule("lever_sequence", over, 0, CFG).seconds(), "최소 초");
        assertEquals(59, SpecialTrial.rule("lights_out", Params.EMPTY, 60, CFG).seconds(), "제한 시간보다 짧게");
        Params swift = Params.of(Map.of("conditions", List.of("swift")));
        assertEquals(70, SpecialTrial.rule("new_gimmick", swift, 100, CFG).seconds(), "표 없음 → 제한 × 0.7");
        assertEquals(CFG.swiftDefaultSeconds(), SpecialTrial.rule("new_gimmick", swift, 0, CFG).seconds(), "표·제한 없음 → 기본 초");
        assertEquals(100, SpecialTrial.rule("lever_sequence", Params.of(Map.of("seconds", 100)), 0, CFG).seconds(), "seconds 만 덮어씀");
        assertTrue(SpecialTrial.rule("new_gimmick", Params.EMPTY, 0, CFG).isEmpty(), "모르는 기믹은 기본표 없음");
    }

    @Test
    void overrideReplacesDefaultsAndDropsUnsupported() {
        Params o = Params.of(Map.of("conditions", List.of("flawless", "abstain", "abstain", "nope")));
        assertEquals(List.of(Condition.ABSTAIN), SpecialTrial.rule("torch_relay", o, 120, CFG).conditions());
        assertTrue(SpecialTrial.rule("lever_sequence", Params.of(Map.of("conditions", List.of())), 0, CFG).isEmpty(), "빈 목록 = 끔");
        assertTrue(SpecialTrial.rule("lever_sequence", Params.of(Map.of("enabled", false)), 0, CFG).isEmpty(), "enabled: false = 끔");
        assertFalse(SpecialTrial.supports("void_trial", Condition.SWIFT));
        assertFalse(SpecialTrial.supports("torch_relay", Condition.SWIFT));
        assertFalse(SpecialTrial.supports("spore_purge", Condition.UNSCATHED));
        assertTrue(SpecialTrial.supports("spore_purge", Condition.ABSTAIN));
        assertEquals(Condition.UNSCATHED, Condition.parse(" Unscathed "));
        assertNull(Condition.parse("perfect"));
    }

    @Test
    void floorsYmlOverrideTyposAreReported() {
        Map<String, Object> floor = new LinkedHashMap<>();
        floor.put("gimmick", "torch_relay");
        floor.put("special_trial", Map.of("conditions", List.of("swfit", "flawless", "abstain")));
        Map<String, Map<String, Object>> files = new HashMap<>();
        files.put("floors.yml", Map.of("floors", Map.of(1, floor)));
        ContentParser parser = new ContentParser();
        parser.parse(files);
        List<String> mine = new ArrayList<>();
        for (String p : parser.problems()) if (p.startsWith("floors.yml")) mine.add(p);
        assertEquals(2, mine.size(), "모르는 조건 1 + 그 기믹이 못 쓰는 조건 1: " + mine);
        assertTrue(mine.get(0).contains("swfit"));
        assertTrue(mine.get(1).contains("flawless"));
    }

    // ── 판정 ──────────────────────────────────────────────────────────────

    @Test
    void keptJudgesEachCondition() {
        SpecialTrial swift = SpecialTrial.of(Condition.SWIFT, RULE, CFG);
        Counters c = new Counters();
        c.elapsed(60);
        assertTrue(swift.kept(c, 1), "딱 그 초는 지킴");
        c.elapsed(60.5);
        assertFalse(swift.kept(c, 1));

        SpecialTrial un = SpecialTrial.of(Condition.UNSCATHED, RULE, CFG);
        assertEquals(2, un.allowedHits(1));
        assertEquals(4, un.allowedHits(3), "파티원 1명당 +1");
        Counters h = new Counters();
        assertFalse(h.hurt(0.029, un.minDamage()), "최대 HP 3% 미만은 안 셈");
        assertTrue(h.hurt(0.03, un.minDamage()), "3% 는 셈");
        assertTrue(h.hurt(0.5, un.minDamage()));
        assertTrue(un.kept(h, 1), "2번까지 지킴");
        h.hurt(0.1, un.minDamage());
        assertFalse(un.kept(h, 1), "3번 = 깨짐 (솔로)");
        assertTrue(un.kept(h, 2), "2인이면 3번까지");

        SpecialTrial ab = SpecialTrial.of(Condition.ABSTAIN, RULE, CFG);
        Counters a = new Counters();
        assertTrue(ab.kept(a, 1));
        a.consume(false);
        assertFalse(ab.kept(a, 1), "주문서도 셈");
        SpecialTrial potionsOnly = new SpecialTrial(Condition.ABSTAIN, 0, 2, 1, 0.03, true, false);
        assertTrue(potionsOnly.kept(a, 1), "scrolls: false 면 주문서는 안 셈");
        a.consume(true);
        assertFalse(potionsOnly.kept(a, 1));

        SpecialTrial fl = SpecialTrial.of(Condition.FLAWLESS, RULE, CFG);
        Counters f = new Counters();
        assertTrue(fl.kept(f, 4));
        f.mistake();
        assertFalse(fl.kept(f, 4));
        f.reset();
        assertTrue(fl.kept(f, 4), "도전마다 새로");
    }

    @Test
    void potionsAreTheDrinkActions() {
        assertEquals(GearItemService.DRINK_ACTIONS, SpecialTrial.POTION_ACTIONS);
        assertTrue(SpecialTrial.isPotion("heal"));
        assertFalse(SpecialTrial.isPotion("return"));
        assertFalse(SpecialTrial.isPotion("revive"));
        assertFalse(SpecialTrial.isPotion(null));
    }

    @Test
    void dotTicksAreNotHits() {
        assertFalse(SpecialTrial.countsAsHit("effect:venom"));
        assertFalse(SpecialTrial.countsAsHit("effect:bleed"));
        assertTrue(SpecialTrial.countsAsHit("effect:damage"), "즉시 피해 효과는 셈");
        assertTrue(SpecialTrial.countsAsHit("resonance_discord"));
        assertTrue(SpecialTrial.countsAsHit(null), "몹 평타");
    }

    // ── 보상 ──────────────────────────────────────────────────────────────

    @Test
    void brokenConditionStillGivesTheNormalChestOnly() {
        SpecialTrial fl = SpecialTrial.of(Condition.FLAWLESS, RULE, CFG);
        Counters clean = new Counters();
        SpecialTrial.Reward normal = SpecialTrial.reward(3, null, false, clean, 1, CFG.xpBonus());
        assertEquals(List.of("gimmick_floor_3"), normal.tables());
        assertEquals(1.0, normal.xpMult(), 1e-12);
        assertFalse(normal.special());

        SpecialTrial.Reward kept = SpecialTrial.reward(3, fl, false, clean, 1, CFG.xpBonus());
        assertEquals(List.of("gimmick_floor_3", "special_trial_f03"), kept.tables(), "평소 상자에 더해 하나 더");
        assertEquals(1.5, kept.xpMult(), 1e-12, "경험치 ×1.5");
        assertTrue(kept.special());

        assertEquals(List.of("gimmick_floor_3"), SpecialTrial.reward(3, fl, true, clean, 1, CFG.xpBonus()).tables(), "깨짐 표시");
        Counters dirty = new Counters();
        dirty.mistake();
        SpecialTrial.Reward broken = SpecialTrial.reward(3, fl, false, dirty, 1, CFG.xpBonus());
        assertEquals(List.of("gimmick_floor_3"), broken.tables(), "어김 → 평소 상자만");
        assertEquals(1.0, broken.xpMult(), 1e-12);
        assertEquals("special_trial_f10", SpecialTrial.table(10));
    }

    @Test
    void specialChestTableExistsAndGivesSomethingOnEveryFloor() {
        LootRoller roller = new LootRoller(content, new SplittableRandom(11));
        for (int f = 1; f <= content.maxFloor(); f++) {
            String t = SpecialTrial.table(f);
            assertNotNull(content.lootTable(t), "loot.yml 에 " + t + " 없음");
            for (int i = 0; i < 20; i++) {
                assertFalse(roller.roll(t, new LootRoller.Request("normal", 1.0, 0, null)).isEmpty(), t + " 이 빈 상자");
            }
        }
    }

    // ── 문구 ──────────────────────────────────────────────────────────────

    @Test
    void linesSayOnlyWhatNotToDo() {
        SpecialTrial un = SpecialTrial.of(Condition.UNSCATHED, RULE, CFG);
        assertTrue(un.line(1).contains("2번"), un.line(1));
        assertTrue(un.line(3).contains("4번"), "파티 인원만큼 늘어난 횟수: " + un.line(3));
        assertTrue(SpecialTrial.of(Condition.SWIFT, RULE, CFG).line(1).contains("60초"));
        for (Condition c : Condition.values()) {
            SpecialTrial t = SpecialTrial.of(c, RULE, CFG);
            assertTrue(t.line(1).length() <= 40, t.line(1));
            assertTrue(t.shortLine(1).length() <= 20, t.shortLine(1));
            assertTrue(t.status(new Counters(), 1, 10, true).endsWith("깨짐"));
            assertEquals(0f, t.progress(new Counters(), 1, 0, true));
        }
        assertEquals("서두름 · 남은 31초", SpecialTrial.of(Condition.SWIFT, RULE, CFG).status(new Counters(), 1, 29.2, false));
        assertEquals("무상 · 상처 0/2", un.status(new Counters(), 1, 0, false));
    }

    // ── 설정 · 저장 ──────────────────────────────────────────────────────

    private static DungeonConfig parse(String yaml) throws InvalidConfigurationException {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(yaml);
        return DungeonConfig.of(y);
    }

    @Test
    void bundledDungeonYmlMatchesCodeDefaults() throws InvalidConfigurationException {
        DungeonConfig jar = DungeonConfig.of(YamlConfiguration.loadConfiguration(new File("src/main/resources/dungeon.yml")));
        assertEquals(DungeonConfig.Special.DEFAULT, jar.specialTrial());
        assertEquals(DungeonConfig.Special.DEFAULT, DungeonConfig.defaults().specialTrial());
        assertEquals(DungeonConfig.Special.DEFAULT, parse("version: 1\nrest_heal: 0.5\n").specialTrial(), "예전 파일 = 새 기본값");
        assertFalse(parse("special_trial: false\n").specialTrial().enabled());
        assertFalse(parse("special_trial:\n  enabled: false\n").specialTrial().enabled());
        DungeonConfig.Special odd = parse("special_trial:\n  chance: 1.7\n  pity_visits: -2\n  conditions:\n    unscathed: {hits: 5}\n").specialTrial();
        assertEquals(1.0, odd.chance(), 1e-12);
        assertEquals(0, odd.pityVisits());
        assertEquals(5, odd.unscathedHits());
        assertEquals(1, odd.unscathedPerMember(), "빠진 하위 키 = 기본값");
    }

    @Test
    void pityCounterIsSavedPerFloor() throws Exception {
        UUID u = new UUID(1, 2);
        PlayerData d = new PlayerData(u, "tester");
        assertEquals(0, d.specialMiss(4));
        d.specialMiss(4, 2);
        d.specialMiss(7, 1);
        PlayerData back = PlayerData.fromYaml(u, "tester", d.toYaml());
        assertEquals(2, back.specialMiss(4));
        assertEquals(1, back.specialMiss(7));
        assertEquals(0, back.specialMiss(5));
        back.specialMiss(4, -3);
        assertEquals(0, back.specialMiss(4), "음수 없음");
    }
}
