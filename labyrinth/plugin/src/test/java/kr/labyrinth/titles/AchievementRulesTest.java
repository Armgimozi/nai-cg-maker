package kr.labyrinth.titles;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.ui.HudBars;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * 칭호 (0.3.4 — 칭호마다 서버에서 단 한 명, 조건은 주인이 생기기 전까지 비밀): 사건 판정(qualifies) · 카운터 · 받을 사람 순서 ·
 * 플레이어 문구의 비밀 규칙 · 0.3.4 초기화 · 기본 titles.yml · HUD 막대 계산.
 */
class AchievementRulesTest {

    /** 테스트용 카운터 저장소. */
    static final class MapStore implements TitleCounters.Store {
        final Map<String, Long> m = new HashMap<>();
        int level = 1;

        @Override public long get(String key) { return "level".equals(key) ? level : m.getOrDefault(key, 0L); }
        @Override public void set(String key, long value) { m.put(key, value); }
    }

    static Content content;
    MapStore s;

    @BeforeAll
    static void load() { content = ContentLoader.load(Path.of("src/main/resources/content")).content(); }

    @BeforeEach
    void setUp() { s = new MapStore(); }

    static AchievementDef def(String id, String type, Map<String, Object> cond) {
        Map<String, Object> c = new LinkedHashMap<>(cond);
        c.put("type", type);
        return new AchievementDef(id, id, "", "title", type, Params.of(c), "<white>" + id, Map.of(), true, false, 0, Map.of());
    }

    boolean q(AchievementDef d, TitleTrigger t) { return AchievementRules.qualifies(d, t, s::get); }

    /** 돌파 사건 (카운터도 함께 올림 — 서비스와 같은 순서). */
    TitleTrigger clear(int floor, int party, int deaths, double secs, String diff) {
        TitleCounters.onClear(s, floor, party, deaths, secs, diff, 0);
        return TitleTrigger.clear(floor, party, deaths, secs, diff, false);
    }

    // ── 사건 판정 ─────────────────────────────────────────────────────────

    @Test
    void clearFamilyUsesTheEventItself() {
        AchievementDef solo5 = def("s5", "SOLO_CLEAR", Map.of("floor", 5));
        AchievementDef nd6 = def("nd", "NO_DEATH_CLEAR", Map.of("floor", 6, "party_min", 3));
        AchievementDef night = def("n10", "DIFFICULTY_CLEAR", Map.of("floor", 10, "difficulty", "nightmare"));
        AchievementDef speed = def("sp", "SPEED_CLEAR", Map.of("floor", 7, "seconds", 900));
        assertFalse(q(solo5, clear(5, 2, 0, 600, "normal")), "2인 돌파는 혼자가 아님");
        assertTrue(q(solo5, clear(5, 1, 3, 600, "normal")));
        assertFalse(q(solo5, clear(4, 1, 0, 600, "normal")), "다른 층");
        // 예전에 혼자 깬 기록(카운터)이 있어도 이번 돌파가 혼자가 아니면 아님 — 판정은 사건으로
        assertFalse(q(solo5, clear(5, 3, 0, 600, "normal")));
        assertFalse(q(nd6, clear(6, 2, 0, 600, "normal")), "3인 이상");
        assertFalse(q(nd6, clear(6, 4, 1, 600, "normal")), "쓰러진 사람이 있음");
        assertTrue(q(nd6, clear(6, 3, 0, 600, "normal")));
        assertFalse(q(night, clear(10, 1, 0, 600, "hard")));
        assertTrue(q(night, clear(10, 1, 0, 600, "nightmare")));
        assertFalse(q(speed, clear(7, 2, 0, 900.4, "normal")), "올림해서 901초");
        assertTrue(q(speed, clear(7, 2, 0, 899.6, "normal")));
        // 다른 사건으로는 절대 안 됨
        assertFalse(q(solo5, TitleTrigger.kill("floor05_anvil_king", null, true)));
        assertFalse(q(solo5, TitleTrigger.level(1, 50)));
    }

    @Test
    void clearCountsAndOptionalFilters() {
        AchievementDef c3 = def("c3", "CLEAR", Map.of("floor", 3, "count", 2));
        assertFalse(q(c3, clear(3, 4, 1, 900, "normal")));
        assertTrue(q(c3, clear(3, 4, 1, 900, "normal")));
        AchievementDef mix = def("mx", "CLEAR", Map.of("floor", 8, "solo", true, "no_death", true, "difficulty", "hard"));
        assertFalse(q(mix, clear(8, 1, 0, 100, "normal")));
        assertFalse(q(mix, clear(8, 1, 1, 100, "hard")));
        assertTrue(q(mix, clear(8, 1, 0, 100, "hard")));
        assertEquals("서버 최초로 혼자서 아무도 쓰러지지 않고 '어려움' 이상 난이도로 지하 8층 돌파",
                AchievementRules.conditionText(mix, null));
    }

    @Test
    void firstClearNeedsTheRecordSettingClear() {
        AchievementDef fc = def("fc", "FIRST_CLEAR", Map.of("floor", 1));
        assertFalse(q(fc, TitleTrigger.clear(1, 3, 0, 300, "normal", false)));
        assertTrue(q(fc, TitleTrigger.clear(1, 3, 0, 300, "normal", true)));
    }

    @Test
    void killsMatchTheKilledMobAndCount() {
        AchievementDef elite = def("ke", "KILL", Map.of("count", 2, "rank", "elite"));
        AchievementDef mob = def("km", "KILL", Map.of("count", 1, "mob", "moss_crawler"));
        AchievementDef list = def("kd", "KILL", Map.of("count", 2, "mobs", List.of("moss_drakeling", "void_drake")));
        TitleCounters.onKill(s, "alpha", "elite", false);
        assertFalse(q(elite, TitleTrigger.kill("alpha", "elite", false)));
        TitleCounters.onKill(s, "alpha", "elite", false);
        assertTrue(q(elite, TitleTrigger.kill("alpha", "elite", false)));
        assertFalse(q(elite, TitleTrigger.kill("moss_crawler", "normal", false)), "이미 300을 넘었어도 정예를 잡는 순간에만");
        assertFalse(q(mob, TitleTrigger.kill("alpha", "elite", false)));
        TitleCounters.onKill(s, "moss_crawler", null, false);
        assertTrue(q(mob, TitleTrigger.kill("moss_crawler", null, false)));
        TitleCounters.onKill(s, "moss_drakeling", "normal", false);
        TitleCounters.onKill(s, "void_drake", "normal", false);
        assertTrue(q(list, TitleTrigger.kill("void_drake", "normal", false)));
        assertFalse(q(list, TitleTrigger.kill("void_drake", null, true)), "보스 처치는 몹 처치가 아님");
    }

    @Test
    void bossKillMatchesBoss() {
        AchievementDef b4 = def("b4", "BOSS_KILL", Map.of("boss", "floor04_floodwarden"));
        TitleCounters.onKill(s, "floor03_mycelium_king", null, true);
        assertFalse(q(b4, TitleTrigger.kill("floor03_mycelium_king", null, true)));
        TitleCounters.onKill(s, "floor04_floodwarden", null, true);
        assertTrue(q(b4, TitleTrigger.kill("floor04_floodwarden", null, true)));
        assertEquals(0L, s.get("titles.kills"), "보스는 몹 처치 수에 안 셈");
    }

    @Test
    void levelOnlyWhenCrossing() {
        AchievementDef lv = def("lv", "LEVEL", Map.of("level", 40));
        assertFalse(q(lv, TitleTrigger.level(38, 39)));
        assertTrue(q(lv, TitleTrigger.level(39, 40)));
        assertFalse(q(lv, TitleTrigger.level(44, 45)), "이미 넘은 사람은 레벨업으로 받지 않음");
    }

    @Test
    void obtainCraftEnhanceTreasure() {
        AchievementDef myth = def("m", "OBTAIN_RARITY", Map.of("rarity", "mythic"));
        TitleCounters.onObtain(s, Rarity.LEGENDARY, 1);
        assertFalse(q(myth, TitleTrigger.obtain(Rarity.LEGENDARY)));
        TitleCounters.onObtain(s, Rarity.MYTHIC, 1);
        assertTrue(q(myth, TitleTrigger.obtain(Rarity.MYTHIC)));

        AchievementDef leg = def("cl", "CRAFT", Map.of("rarity", "legendary"));
        TitleCounters.onCraft(s, Rarity.EPIC);
        assertFalse(q(leg, TitleTrigger.craft(Rarity.EPIC)));
        TitleCounters.onCraft(s, Rarity.MYTHIC);
        assertTrue(q(leg, TitleTrigger.craft(Rarity.MYTHIC)), "전설 이상");

        AchievementDef e10 = def("e10", "ENHANCE", Map.of("level", 10));
        assertFalse(q(e10, TitleTrigger.enhance(9)));
        assertTrue(q(e10, TitleTrigger.enhance(10)));
        TitleCounters.onEnhance(s, false, 7);
        assertEquals(0, s.get(AchievementRules.P + "enhance_best"), "실패는 세지 않음");

        AchievementDef mimic = def("mi", "TREASURE", Map.of("kind", "mimic"));
        assertFalse(q(mimic, TitleTrigger.treasure("mimic")), "카운터가 먼저 올라야 함");
        s.add("titles.treasure.mimic", 1);
        assertTrue(q(mimic, TitleTrigger.treasure("mimic")));
        assertFalse(q(mimic, TitleTrigger.treasure("vault")));
    }

    @Test
    void unknownTypeNeverQualifies() {
        AchievementDef x = def("x", "SOMETHING_NEW", Map.of());
        assertFalse(q(x, TitleTrigger.kill("a", "normal", false)));
        assertFalse(AchievementRules.met(x, s::get));
    }

    // ── 받을 사람 ─────────────────────────────────────────────────────────

    @Test
    void partyAwardGoesToTopDamageThenLastHitThenOrder() {
        UUID a = UUID.randomUUID(), b = UUID.randomUUID(), c = UUID.randomUUID();
        assertEquals(List.of(b, c, a), AwardOrder.rank(List.of(a, b, c), Map.of(a, 10.0, b, 500.0, c, 120.0), a));
        assertEquals(List.of(c, b, a), AwardOrder.rank(List.of(a, b, c), Map.of(b, 300.0, c, 300.0), c), "같으면 막타");
        assertEquals(List.of(a, b, c), AwardOrder.rank(List.of(a, b, c), Map.of(), null), "기록 없음 → 파티 순서");
        assertEquals(List.of(c, a, b), AwardOrder.rank(List.of(a, b, c), Map.of(), c), "기록 없음 → 막타 먼저");
        assertEquals(List.of(a, b), AwardOrder.rank(List.of(a, b, a), Map.of(), null), "중복 없음");
    }

    // ── 비밀 규칙 (플레이어가 보는 문구) ──────────────────────────────────

    @Test
    void conditionHiddenUntilClaimedThenRevealed() {
        assertEquals(12, content.achievements().size(), "칭호 12개");
        TitleView.Owner owner = new TitleView.Owner("모험가", 1_700_000_000_000L);
        for (AchievementDef a : content.achievements().values()) {
            String cond = AchievementRules.conditionText(a, content);
            String body = AchievementRules.conditionBody(a, content);
            assertFalse(cond.isEmpty(), a.id() + ": 조건 설명 없음");
            // 주인 없음 → 어디에도 조건이 없다
            String hidden = String.join("\n", TitleView.lore(a, null, false, false, content))
                    + "\n" + TitleView.listLine(a, null, false, content);
            assertFalse(hidden.contains(body), a.id() + " 주인 없는데 조건이 보임: " + hidden);
            assertTrue(hidden.contains("???"), a.id());
            assertTrue(hidden.contains("아직 주인이 없습니다"), a.id());
            // 칭호 이름·설명 자체도 조건을 말하지 않는다 (층·보스·몬스터·강화 단계·숫자)
            String visible = a.name() + " " + a.description() + " " + kr.labyrinth.core.Text.strip(a.title());
            for (String bad : List.of("지하", "층", "보스", "혼자", "홀로", "강화", "미믹", "제작", "처치", "악몽", "+")) {
                assertFalse(visible.contains(bad), a.id() + " 이름·설명이 조건을 암시: " + bad);
            }
            assertFalse(visible.matches(".*\\d.*"), a.id() + " 이름·설명에 숫자");
            // 주인 있음 → 메뉴·목록·방송·주인 알림에 조건이 보인다
            String shown = String.join("\n", TitleView.lore(a, owner, false, false, content));
            assertTrue(shown.contains(cond), a.id() + " 주인이 있는데 조건이 안 보임");
            assertTrue(shown.contains("주인: <#ffd36b>모험가"), a.id());
            assertTrue(TitleView.listLine(a, owner, false, content).contains(cond), a.id());
            assertTrue(TitleView.broadcast(a, "모험가", content).contains(cond), a.id());
            assertTrue(TitleView.broadcast(a, "모험가", content).contains("의 주인이 되었습니다"), a.id());
            assertTrue(TitleView.ownerMessage(a, content, "").contains(cond), a.id());
        }
        // 안내 문구에도 조건이 없다
        String sum = String.join("\n", TitleView.summary(12, 0, 0)) + TitleMigration.NOTICE;
        for (AchievementDef a : content.achievements().values()) {
            assertFalse(sum.contains(AchievementRules.conditionBody(a, content)), a.id());
        }
    }

    @Test
    void readableConditionText() {
        AchievementDef solo = def("s", "SOLO_CLEAR", Map.of("floor", 5));
        assertEquals("서버 최초로 혼자서 지하 5층 돌파", AchievementRules.conditionText(solo, null));
        assertEquals("서버 최초로 지하 7층을 15분 안에 돌파",
                AchievementRules.conditionText(def("sp", "SPEED_CLEAR", Map.of("floor", 7, "seconds", 900)), null));
        assertEquals("서버 최초로 3명 이상 파티로 아무도 쓰러지지 않고 지하 6층 돌파",
                AchievementRules.conditionText(def("n", "NO_DEATH_CLEAR", Map.of("floor", 6, "party_min", 3)), null));
        assertEquals("서버 최초로 '악몽' 난이도로 지하 10층 돌파",
                AchievementRules.conditionText(def("d", "DIFFICULTY_CLEAR", Map.of("floor", 10, "difficulty", "nightmare")), null));
        assertEquals("서버 최초로 장비를 +10 까지 강화",
                AchievementRules.conditionText(def("e", "ENHANCE", Map.of("level", 10)), null));
        assertEquals("서버 최초로 정예 몬스터 300마리 처치",
                AchievementRules.conditionText(def("k", "KILL", Map.of("count", 300, "rank", "elite")), null));
        assertEquals("서버 최초로 미믹 길들이기",
                AchievementRules.conditionText(def("m", "TREASURE", Map.of("kind", "mimic")), null));
        String boss = AchievementRules.conditionText(def("b", "BOSS_KILL", Map.of("boss", "floor04_floodwarden")), content);
        assertTrue(boss.startsWith("서버 최초로 지하 4층 보스 ") && boss.endsWith(" 처치"), boss);
        assertFalse(boss.contains("<"), "MiniMessage 기호 없음: " + boss);
    }

    // ── 0.3.4 초기화 · 주인 대조 ─────────────────────────────────────────

    @Test
    void migrationRevokesOldTitlesAndClearsEquippedOnce() {
        PlayerData d = new PlayerData(UUID.randomUUID(), "고참");
        d.grantAchievement("first_clear_floor_1");
        d.grantAchievement("kill_100");
        d.equippedTitle("first_clear_floor_1");
        d.counter("titles.kills", 150);
        d.gold(1234);
        Set<String> valid = content.achievements().keySet();
        TitleMigration.Result r = TitleMigration.reset034(d, valid);
        assertTrue(r.ran());
        assertTrue(r.announce(), "예전에 하던 사람은 안내를 받는다");
        assertEquals(Set.of("first_clear_floor_1", "kill_100"), new HashSet<>(r.revoked()));
        assertTrue(d.achievements().isEmpty());
        assertNull(d.equippedTitle(), "없어진 칭호의 보너스가 남지 않게 해제");
        assertTrue(r.clearedEquipped());
        assertEquals(150, d.counter("titles.kills"), "카운터는 그대로");
        assertEquals(1234, d.gold(), "받은 골드는 그대로");
        // 두 번째 접속: 아무 일도 없음 (새로 얻은 칭호도 지우지 않음)
        String id = valid.iterator().next();
        d.grantAchievement(id);
        TitleMigration.Result again = TitleMigration.reset034(d, valid);
        assertFalse(again.ran());
        assertTrue(d.hasAchievement(id));
        // 새 플레이어: 표시만, 안내 없음
        TitleMigration.Result fresh = TitleMigration.reset034(new PlayerData(UUID.randomUUID(), "새내기"), valid);
        assertTrue(fresh.ran());
        assertFalse(fresh.announce());
    }

    @Test
    void syncFollowsTheOwnerRecord() {
        UUID me = UUID.randomUUID();
        UUID other = UUID.randomUUID();
        PlayerData d = new PlayerData(me, "나");
        d.grantAchievement("a");
        d.grantAchievement("b");
        d.equippedTitle("b");
        Map<String, List<UUID>> owners = Map.of("a", List.of(me), "b", List.of(other), "c", List.of(me));
        TitleMigration.Sync sync = TitleMigration.sync(d, List.of("a", "b", "c", "d"), owners);
        assertEquals(List.of("c"), sync.restored(), "주인 기록이 있으면 되돌림");
        assertEquals(List.of("b"), sync.revoked(), "다른 사람이 주인이면 회수");
        assertTrue(sync.clearedEquipped());
        assertTrue(d.hasAchievement("a") && d.hasAchievement("c") && !d.hasAchievement("b"));
        assertFalse(TitleMigration.sync(d, List.of("a", "b", "c", "d"), owners).changed(), "두 번째는 그대로");
    }

    // ── 기본 titles.yml ───────────────────────────────────────────────────

    @Test
    void bundledTitlesAreFewNewAndValid() {
        Set<String> known = Set.of("FIRST_CLEAR", "CLEAR", "SOLO_CLEAR", "NO_DEATH_CLEAR", "DIFFICULTY_CLEAR", "SPEED_CLEAR",
                "KILL", "BOSS_KILL", "LEVEL", "OBTAIN_RARITY", "CRAFT", "ENHANCE", "TREASURE");
        // 예전 판의 칭호 id (새 id 와 겹치면 예전 기록·데이터가 새 칭호로 오해됨)
        Set<String> old = Set.of("first_clear_floor_1", "first_clear_floor_10", "clear_floor_1", "clear_floor_10", "solo_floor_5",
                "solo_floor_10", "no_death_floor_5", "hard_floor_10", "nightmare_floor_10", "speed_floor_5", "kill_1000", "kill_5000",
                "kill_elite_50", "boss_kill_10", "level_50", "first_vault", "mimic_tamer", "obtain_mythic", "craft_100",
                "craft_legendary", "enhance_7", "first_enhance_10");
        int n = content.achievements().size();
        assertTrue(n >= 11 && n <= 13, "칭호 11~13개: " + n);
        Set<String> names = new HashSet<>();
        for (AchievementDef a : content.achievements().values()) {
            assertFalse(old.contains(a.id()), a.id() + " 는 예전 id");
            assertTrue(known.contains(a.conditionType()), a.id() + ": 알 수 없는 조건 " + a.conditionType());
            assertTrue(a.broadcast(), a.id() + " 방송");
            assertTrue(names.add(a.name()), "이름 중복 " + a.name());
            assertFalse(a.description().isBlank(), a.id() + " lore");
            // 칭호 보너스는 체감되게 (0.3.5: 주 능력치 +8~20 · 골드/경험치 +15~20%), 그래도 한 칭호가 판을 깨지 않게 위 한계
            assertTrue(a.bonus().size() >= 1 && a.bonus().size() <= 2, a.id() + " 보너스 1~2개");
            a.bonus().forEach((k, v) -> assertTrue(k.endsWith("_bonus") ? v >= 0.10 - 1e-9 && v <= 0.25 + 1e-9 : v >= 4 && v <= 20,
                    a.id() + " 보너스 범위 밖: " + k + "=" + v));
            assertTrue(a.rewardGold() <= 5000, a.id() + " 골드 보상");
            // 아무 일도 안 한 새 플레이어는 어떤 사건으로도 받지 못한다 (돌파 조건은 돌파해야만)
            MapStore fresh = new MapStore();
            assertFalse(AchievementRules.qualifies(a, TitleTrigger.kill("nothing", "normal", false), fresh::get), a.id());
            assertFalse(AchievementRules.qualifies(a, TitleTrigger.level(1, 2), fresh::get), a.id());
        }
    }

    @Test
    void hudBarCells() {
        assertEquals(0, HudBars.filledCells(0, 10));
        assertEquals(1, HudBars.filledCells(0.01, 10), "조금이라도 남으면 1칸");
        assertEquals(9, HudBars.filledCells(0.99, 10), "가득 차지 않으면 최대 9칸");
        assertEquals(10, HudBars.filledCells(1.0, 10));
        assertEquals(5, HudBars.filledCells(0.5, 10));
        assertEquals("▮▮▮▯▯", HudBars.textBar(0.6, 5, "▮", "▯"));
        assertEquals(0, HudBars.frameIndex(Double.NaN, 20));
        assertEquals(20, HudBars.frameIndex(1.0, 20));
        assertEquals(1, HudBars.halfCells(0.001, 10));
        assertEquals(19, HudBars.halfCells(0.999, 10));
    }
}
