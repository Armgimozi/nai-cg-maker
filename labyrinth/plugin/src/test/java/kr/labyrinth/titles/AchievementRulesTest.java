package kr.labyrinth.titles;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.AchievementDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Rarity;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.ui.HudBars;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** 업적 조건 판정(AchievementRules) + 이벤트 → 카운터 갱신(TitleCounters) + HUD 막대 계산. */
class AchievementRulesTest {

    /** 테스트용 카운터 저장소. */
    static final class MapStore implements TitleCounters.Store {
        final Map<String, Long> m = new HashMap<>();
        int level = 1;

        @Override public long get(String key) { return "level".equals(key) ? level : m.getOrDefault(key, 0L); }
        @Override public void set(String key, long value) { m.put(key, value); }
    }

    MapStore s;

    @BeforeEach
    void setUp() { s = new MapStore(); }

    static AchievementDef def(String id, String type, Map<String, Object> cond) {
        Map<String, Object> c = new LinkedHashMap<>(cond);
        c.put("type", type);
        return new AchievementDef(id, id, "", "clear", type, Params.of(c), "<white>" + id, Map.of(), false, false, 0, Map.of());
    }

    boolean met(AchievementDef d) { return AchievementRules.met(d, s::get); }

    @Test
    void clearCountsAndSolo() {
        AchievementDef clear3 = def("c3", "CLEAR", Map.of("floor", 3, "count", 2));
        AchievementDef solo3 = def("s3", "SOLO_CLEAR", Map.of("floor", 3));
        TitleCounters.onClear(s, 3, 4, 1, 900, "normal", 0);
        assertFalse(met(clear3));
        assertFalse(met(solo3));
        TitleCounters.onClear(s, 3, 1, 0, 800, "normal", 0);
        assertTrue(met(clear3));
        assertTrue(met(solo3));
        // 다른 층은 영향 없음
        assertFalse(met(def("c4", "CLEAR", Map.of("floor", 4))));
    }

    @Test
    void externalClearCounterIsRespected() {
        TitleCounters.onClear(s, 2, 3, 0, 500, "easy", 5);
        assertTrue(met(def("c2x5", "CLEAR", Map.of("floor", 2, "count", 5))));
    }

    @Test
    void noDeathNeedsPartyMinimum() {
        AchievementDef nd = def("nd", "NO_DEATH_CLEAR", Map.of("floor", 5, "party_min", 3));
        TitleCounters.onClear(s, 5, 2, 0, 600, "normal", 0);
        assertFalse(met(nd), "2인 무사망은 3인 조건 불충족");
        TitleCounters.onClear(s, 5, 4, 2, 600, "normal", 0);
        assertFalse(met(nd), "사망이 있으면 기록 안 됨");
        TitleCounters.onClear(s, 5, 3, 0, 600, "normal", 0);
        assertTrue(met(nd));
    }

    @Test
    void difficultyIsAtLeast() {
        AchievementDef hard = def("h", "DIFFICULTY_CLEAR", Map.of("floor", 1, "difficulty", "hard"));
        TitleCounters.onClear(s, 1, 1, 0, 100, "normal", 0);
        assertFalse(met(hard));
        TitleCounters.onClear(s, 1, 1, 0, 100, "nightmare", 0);
        assertTrue(met(hard), "악몽 클리어는 어려움 이상 조건 만족");
        TitleCounters.onClear(s, 1, 1, 0, 100, "easy", 0);
        assertTrue(met(hard), "더 낮은 난이도로 다시 깨도 최고 기록 유지");
    }

    @Test
    void speedKeepsBestTime() {
        AchievementDef sp = def("sp", "SPEED_CLEAR", Map.of("floor", 2, "seconds", 600));
        TitleCounters.onClear(s, 2, 2, 0, 700.2, "normal", 0);
        assertFalse(met(sp));
        TitleCounters.onClear(s, 2, 2, 0, 599.4, "normal", 0);
        assertTrue(met(sp));
        TitleCounters.onClear(s, 2, 2, 0, 1200, "normal", 0);
        assertEquals(600L, s.get("titles.best_time.2"), "느린 기록이 최단 기록을 덮지 않음");
        assertTrue(met(sp));
    }

    @Test
    void firstClearOnlyWithRecordFlag() {
        AchievementDef fc = def("fc", "FIRST_CLEAR", Map.of("floor", 1));
        TitleCounters.onClear(s, 1, 3, 0, 300, "normal", 0);
        assertFalse(met(fc), "기록 claim 없이 클리어만으로는 최초 돌파 아님");
        s.set("titles.first_clear.1", 1);
        assertTrue(met(fc));
    }

    @Test
    void killsByMobRankAndTotal() {
        AchievementDef any = def("k", "KILL", Map.of("count", 3));
        AchievementDef elite = def("ke", "KILL", Map.of("count", 2, "rank", "elite"));
        AchievementDef mob = def("km", "KILL", Map.of("count", 2, "mob", "moss_crawler"));
        TitleCounters.onKill(s, "moss_crawler", "normal", false);
        TitleCounters.onKill(s, "alpha", "elite", false);
        assertFalse(met(any));
        TitleCounters.onKill(s, "alpha", "elite", false);
        assertTrue(met(any));
        assertTrue(met(elite));
        assertFalse(met(mob));
        TitleCounters.onKill(s, "moss_crawler", null, false);
        assertTrue(met(mob));
        assertEquals(2L, s.get("titles.kill_rank.normal"), "rank 없음 = normal");
    }

    @Test
    void bossKillsDoNotCountAsMobKills() {
        AchievementDef b = def("b", "BOSS_KILL", Map.of("count", 1, "boss", "floor01_moss_warden"));
        AchievementDef anyBoss = def("ab", "BOSS_KILL", Map.of("count", 2));
        TitleCounters.onKill(s, "floor01_moss_warden", null, true);
        assertTrue(met(b));
        assertFalse(met(anyBoss));
        assertEquals(0L, s.get("titles.kills"));
        TitleCounters.onKill(s, "floor02_silk_queen", null, true);
        assertTrue(met(anyBoss));
    }

    @Test
    void levelUsesLookup() {
        AchievementDef lv = def("lv", "LEVEL", Map.of("level", 20));
        s.level = 19;
        assertFalse(met(lv));
        s.level = 20;
        assertTrue(met(lv));
    }

    @Test
    void obtainRarityIsExact() {
        AchievementDef leg = def("l", "OBTAIN_RARITY", Map.of("rarity", "legendary", "count", 2));
        TitleCounters.onObtain(s, Rarity.MYTHIC, 1);
        TitleCounters.onObtain(s, Rarity.LEGENDARY, 1);
        assertFalse(met(leg), "신화는 전설 개수에 안 셈 (정확히 일치)");
        TitleCounters.onObtain(s, Rarity.LEGENDARY, 1);
        assertTrue(met(leg));
    }

    @Test
    void craftCountsRarityAndAbove() {
        AchievementDef any = def("cr", "CRAFT", Map.of("count", 3));
        AchievementDef epic = def("ce", "CRAFT", Map.of("count", 2, "rarity", "epic"));
        TitleCounters.onCraft(s, Rarity.LEGENDARY);
        TitleCounters.onCraft(s, Rarity.RARE);
        assertFalse(met(any));
        assertFalse(met(epic));
        TitleCounters.onCraft(s, Rarity.EPIC);
        assertTrue(met(any));
        assertTrue(met(epic), "전설 1 + 영웅 1 = 영웅 이상 2");
    }

    @Test
    void pvpWinsStreakRating() {
        AchievementDef first = def("pf", "PVP_FIRST_WIN", Map.of());
        AchievementDef wins = def("pw", "PVP_WIN", Map.of("count", 2));
        AchievementDef streak = def("ps", "PVP_STREAK", Map.of("count", 2));
        AchievementDef rating = def("pr", "PVP_RATING", Map.of("min", 1150));
        TitleCounters.onPvp(s, false, 0, 990);
        assertFalse(met(first));
        TitleCounters.onPvp(s, true, null, 1030);
        assertTrue(met(first));
        assertFalse(met(streak));
        TitleCounters.onPvp(s, true, null, 1160);
        assertTrue(met(wins));
        assertTrue(met(streak), "연승은 이벤트가 안 주면 자체 계산");
        assertTrue(met(rating));
        TitleCounters.onPvp(s, false, 0, 1100);
        assertEquals(0L, s.get("titles.pvp_streak"));
        assertTrue(met(streak), "최고 연승은 유지");
        assertTrue(met(rating), "최고 레이팅 기준");
    }

    @Test
    void serverFirstRequiresClaimFlag() {
        AchievementDef sf = def("pvp_server_first_win", "PVP_FIRST_WIN", Map.of("server_first", true));
        TitleCounters.onPvp(s, true, 1, 1016);
        assertTrue(AchievementRules.baseMet(sf.conditionType(), sf.condition(), s::get), "자격은 있음");
        assertFalse(met(sf), "서버 기록 claim 전에는 미달성");
        s.set("titles.server_first.pvp_server_first_win", 1);
        assertTrue(met(sf));
    }

    @Test
    void unknownTypeIsNeverMet() {
        assertFalse(met(def("x", "SOMETHING_NEW", Map.of())));
    }

    @Test
    void progressIsClampedAndTyped() {
        AchievementDef k = def("k", "KILL", Map.of("count", 100));
        for (int i = 0; i < 150; i++) TitleCounters.onKill(s, "m", "normal", false);
        assertArrayEquals(new long[] {100, 100}, AchievementRules.progress(k, s::get));
        AchievementDef fc = def("fc", "FIRST_CLEAR", Map.of("floor", 9));
        assertArrayEquals(new long[] {0, 1}, AchievementRules.progress(fc, s::get));
    }

    @Test
    void everyBundledAchievementTypeIsKnown() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        Set<String> known = Set.of("FIRST_CLEAR", "CLEAR", "SOLO_CLEAR", "NO_DEATH_CLEAR", "DIFFICULTY_CLEAR", "SPEED_CLEAR",
                "KILL", "BOSS_KILL", "LEVEL", "OBTAIN_RARITY", "CRAFT", "PVP_FIRST_WIN", "PVP_WIN", "PVP_STREAK", "PVP_RATING");
        assertFalse(c.achievements().isEmpty());
        for (AchievementDef a : c.achievements().values()) {
            assertTrue(known.contains(a.conditionType()), () -> a.id() + ": 알 수 없는 조건 " + a.conditionType());
            assertFalse(AchievementRules.conditionText(a).isEmpty(), () -> a.id() + ": 조건 설명 없음");
            // 아무 기록도 없는 새 플레이어는 어떤 업적도 달성하지 않는다
            MapStore fresh = new MapStore();
            assertFalse(AchievementRules.met(a, fresh::get), () -> a.id() + " 가 빈 상태에서 달성됨");
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
