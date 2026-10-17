package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.List;
import java.util.Set;
import java.util.SplittableRandom;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import kr.labyrinth.core.DeathPenaltyRules.GoldLoss;
import kr.labyrinth.core.DeathPenaltyRules.Lost;
import kr.labyrinth.core.DeathPenaltyRules.Where;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 0.3.6.2 죽음 페널티 — 골드 5~25% (최대 15,000G) · config · 안내 · 콘솔 줄. */
class DeathPenaltyGoldTest {

    private static Config read(String yaml) {
        return new Settings(WildConfigTest.yaml(yaml)).deathPenalty();
    }

    // ── 셈 ───────────────────────────────────────────────────────────────

    @Test
    void percentOfCarriedGoldRoundedDown() {
        assertEquals(500, DeathPenaltyRules.goldLost(10_000, 5, 15_000));
        assertEquals(2_500, DeathPenaltyRules.goldLost(10_000, 25, 15_000));
        assertEquals(1_234, DeathPenaltyRules.goldLost(10_000, 12.345, 15_000), "내림");
        assertEquals(49, DeathPenaltyRules.goldLost(999, 5, 15_000), "49.95 → 49");
        assertEquals(29, DeathPenaltyRules.goldLost(100, 29, 0), "부동소수 오차로 28 이 되지 않게");
        assertEquals(0, DeathPenaltyRules.goldLost(19, 5, 15_000), "0.95 → 0");
        assertEquals(0, DeathPenaltyRules.goldLost(1, 25, 15_000));
    }

    @Test
    void capAt15000() {
        assertEquals(15_000, DeathPenaltyRules.goldLost(100_000, 25, 15_000), "25% = 25,000 → 15,000");
        assertEquals(15_000, DeathPenaltyRules.goldLost(1_000_000_000L, 5, 15_000));
        assertEquals(15_000, DeathPenaltyRules.goldLost(60_000, 25, 15_000), "딱 상한");
        assertEquals(14_999, DeathPenaltyRules.goldLost(59_996, 25, 15_000));
        assertEquals(250_000, DeathPenaltyRules.goldLost(1_000_000, 25, 0), "0 = 상한 없음");
    }

    @Test
    void zeroOrNegativeGoldLosesNothing() {
        assertEquals(0, DeathPenaltyRules.goldLost(0, 25, 15_000));
        assertEquals(0, DeathPenaltyRules.goldLost(-50, 25, 15_000));
        assertEquals(0, DeathPenaltyRules.goldLost(10_000, 0, 15_000), "0%");
        assertEquals(0, DeathPenaltyRules.goldLost(10_000, Double.NaN, 15_000));
        assertEquals(0, DeathPenaltyRules.goldLost(0, GoldLoss.DEFAULT, new SplittableRandom(1)));
        assertEquals(10_000, DeathPenaltyRules.goldLost(10_000, 400, 0), "100% 를 넘지 않음 — 0 아래로 안 감");
    }

    @Test
    void rolledPercentIsUniformBetweenMinAndMax() {
        int[] buckets = new int[4]; // 5~10, 10~15, 15~20, 20~25
        double sum = 0;
        int n = 40_000;
        SplittableRandom rng = new SplittableRandom(7);
        for (int i = 0; i < n; i++) {
            double p = DeathPenaltyRules.rollPercent(GoldLoss.DEFAULT, rng);
            assertTrue(p >= 5 && p < 25, "5 ~ 25: " + p);
            sum += p;
            buckets[(int) ((p - 5) / 5)]++;
        }
        assertEquals(15, sum / n, 0.15, "평균 15%");
        for (int b : buckets) assertEquals(n / 4.0, b, n * 0.02, "고르게");
        assertEquals(10, DeathPenaltyRules.rollPercent(new GoldLoss(true, 10, 10, 15_000), rng), "같으면 그 값");
    }

    @Test
    void rolledLossStaysInBounds() {
        for (long seed = 0; seed < 5_000; seed++) {
            long lose = DeathPenaltyRules.goldLost(10_000, GoldLoss.DEFAULT, new SplittableRandom(seed));
            assertTrue(lose >= 500 && lose <= 2_500, "10,000G 의 5~25%: " + lose);
            long rich = DeathPenaltyRules.goldLost(1_000_000, GoldLoss.DEFAULT, new SplittableRandom(seed));
            assertEquals(15_000, rich, "부자는 늘 상한");
        }
        assertEquals(0, DeathPenaltyRules.goldLost(10_000, GoldLoss.OFF, new SplittableRandom(1)), "꺼짐");
        assertEquals(0, DeathPenaltyRules.goldLost(10_000, null, new SplittableRandom(1)));
    }

    // ── 언제 ─────────────────────────────────────────────────────────────

    @Test
    void onlyOnDungeonKnockDown() {
        assertTrue(DeathPenaltyRules.plan(Config.DEFAULT, Where.DUNGEON_RUN, false).loseGold());
        assertFalse(DeathPenaltyRules.plan(Config.DEFAULT, Where.OUTSIDE, false).loseGold(), "마을·야생·광산·PvP");
        assertFalse(DeathPenaltyRules.plan(Config.DEFAULT, Where.LABYRINTH_WORLD, false).loseGold(), "관전 중 /kill");
        assertFalse(DeathPenaltyRules.plan(Config.DEFAULT, Where.DUNGEON_RUN, true).loseGold(), "관리자 시험 입장");
        assertFalse(DeathPenaltyRules.plan(Config.OFF, Where.DUNGEON_RUN, false).loseGold());
        Config itemsOff = new Config(true, false, 2, 3, Set.of());
        assertTrue(DeathPenaltyRules.plan(itemsOff, Where.DUNGEON_RUN, false).loseGold(), "물건을 꺼도 골드는 따로");
    }

    // ── config ───────────────────────────────────────────────────────────

    @Test
    void defaultsWhenKeyMissing() {
        assertEquals(new GoldLoss(true, 5, 25, 15_000), GoldLoss.DEFAULT);
        assertEquals(GoldLoss.DEFAULT, Config.DEFAULT.gold());
        assertEquals(GoldLoss.DEFAULT, new Settings(new YamlConfiguration()).deathPenalty().gold(), "config 없음");
        // 0.3.6.1 서버 config.yml (penalty 블록에 gold_loss 가 없음) — jar 만 바꾸면 켜진다
        Config old = read("death:\n  keep_inventory: true\n  keep_level: true\n  penalty:\n    xp_progress_reset: true\n"
                + "    combat_exit_seconds: 5\n    dungeon_item_loss:\n      enabled: true\n      slots_min: 2\n      slots_max: 3\n"
                + "      safe_items: []\n");
        assertEquals(Config.DEFAULT, old);
        assertEquals(GoldLoss.DEFAULT, read("death:\n  keep_inventory: true\n").gold(), "0.3.6 config");
        assertEquals(GoldLoss.DEFAULT, read("death:\n  penalty:\n    gold_loss: true\n").gold());
    }

    @Test
    void bundledConfigHasTheGoldBlock() {
        YamlConfiguration jar = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertTrue(jar.isConfigurationSection("death.penalty.gold_loss"));
        assertEquals(GoldLoss.DEFAULT, new Settings(jar).deathPenalty().gold());
    }

    @Test
    void offSwitches() {
        GoldLoss off = read("death:\n  penalty:\n    gold_loss: false\n").gold();
        assertFalse(off.on());
        assertFalse(DeathPenaltyRules.plan(read("death:\n  penalty:\n    gold_loss: false\n"), Where.DUNGEON_RUN, false).loseGold());
        assertFalse(read("death:\n  penalty:\n    gold_loss:\n      enabled: false\n").gold().on());
        assertFalse(read("death:\n  penalty: false\n").gold().on(), "penalty: false = 모두");
        assertFalse(read("death:\n  penalty:\n    gold_loss:\n      max_percent: 0\n").gold().on(), "0% = 끔");
        // jar config 처럼 min_percent: 5 가 적혀 있어도 max_percent: 0 이면 끔 (5% 로 끌어올리지 않음)
        GoldLoss zero = read("death:\n  penalty:\n    gold_loss:\n      enabled: true\n      min_percent: 5\n      max_percent: 0\n"
                + "      max: 15000\n").gold();
        assertFalse(zero.on(), "min 5 · max 0 = 끔");
        assertFalse(DeathPenaltyRules.plan(read("death:\n  penalty:\n    gold_loss:\n      min_percent: 5\n      max_percent: 0\n"),
                Where.DUNGEON_RUN, false).loseGold());
        assertEquals(0, DeathPenaltyRules.goldLost(100_000, zero, new SplittableRandom(3)));
        assertFalse(read("death:\n  penalty:\n    gold_loss:\n      min_percent: 5\n      max_percent: -3\n").gold().on(), "음수도 끔");
        assertTrue(read("death:\n  penalty:\n    gold_loss:\n      min_percent: 0\n      max_percent: 1\n").gold().on(), "1% 는 켜짐");
        // 골드를 꺼도 나머지는 그대로
        Config c = read("death:\n  penalty:\n    gold_loss: false\n");
        assertTrue(c.xpProgressReset() && c.itemLoss());
    }

    @Test
    void valuesAreClamped() {
        GoldLoss g = read("death:\n  penalty:\n    gold_loss:\n      min_percent: -5\n      max_percent: 150\n      max: -100\n").gold();
        assertEquals(0, g.minPercent());
        assertEquals(100, g.maxPercent());
        assertEquals(0, g.max(), "음수 상한 → 0 (상한 없음)");
        g = read("death:\n  penalty:\n    gold_loss:\n      min_percent: 30\n      max_percent: 10\n").gold();
        assertEquals(30, g.minPercent());
        assertEquals(30, g.maxPercent(), "max < min → min");
        g = read("death:\n  penalty:\n    gold_loss:\n      max_percent: 3\n").gold();
        assertEquals(3, g.minPercent(), "max_percent 만 적으면 min 도 그 아래로");
        assertEquals(3, g.maxPercent());
        g = read("death:\n  penalty:\n    gold_loss:\n      max_percent: 40\n").gold();
        assertEquals(5, g.minPercent(), "올리기만 하면 min 은 기본 5");
        assertEquals(40, g.maxPercent());
        g = read("death:\n  penalty:\n    gold_loss:\n      max: 5000\n").gold();
        assertEquals(new GoldLoss(true, 5, 25, 5_000), g, "빠진 키는 기본값");
        assertEquals(new GoldLoss(true, 0, 0, 0), new GoldLoss(true, Double.NaN, Double.NEGATIVE_INFINITY, 0));
    }

    // ── 글 ───────────────────────────────────────────────────────────────

    @Test
    void chatLines() {
        List<String> l = DeathPenaltyRules.lines(List.of(new Lost("철 주괴", 13)), 1_234, 120);
        assertEquals(List.of("죽어서 잃었습니다: 철 주괴 ×13", "골드를 잃었습니다: 1,234G", "이번 레벨 경험치가 처음으로 돌아갔습니다. (-120 XP)"),
                l.stream().map(Text::strip).toList());
        assertEquals(List.of("골드를 잃었습니다: 15,000G"),
                DeathPenaltyRules.lines(List.of(), 15_000, 0).stream().map(Text::strip).toList(), "골드만");
        assertTrue(DeathPenaltyRules.lines(List.of(), 0, 0).isEmpty(), "0G = 말 없음");
        assertEquals(1, DeathPenaltyRules.lines(List.of(), 120).size(), "미궁 밖 = 경험치 줄만");
    }

    @Test
    void goldTextForms() {
        assertEquals("골드 5~25%(최대 15,000G)", DeathPenaltyRules.goldText(GoldLoss.DEFAULT));
        assertEquals("골드 10%", DeathPenaltyRules.goldText(new GoldLoss(true, 10, 10, 0)), "같은 비율 · 상한 없음");
        assertEquals("골드 2.5~7.5%(최대 500G)", DeathPenaltyRules.goldText(new GoldLoss(true, 2.5, 7.5, 500)));
    }

    @Test
    void consoleLineHasGoldBeforeChange() {
        assertEquals("[죽음 페널티] Steve (미궁) 잃은 물건 iron_ingot×13 (철 주괴) · 골드 -1234 (보유 8000 → 6766) · 경험치 -120",
                DeathPenalty.logLine("Steve", "미궁", List.of("iron_ingot×13 (철 주괴)"), 120, 1_234, 8_000));
        assertEquals("[죽음 페널티] Steve (미궁) · 골드 -500 (보유 10000 → 9500)",
                DeathPenalty.logLine("Steve", "미궁", List.of(), 0, 500, 10_000), "장비만 있고 경험치 0");
        assertEquals("[죽음 페널티] Alex (world) · 경험치 -50", DeathPenalty.logLine("Alex", "world", List.of(), 50, 0, 3_000));
        assertNull(DeathPenalty.logLine("Alex", "미궁", List.of(), 0, 0, 0), "잃은 것 없음 = 줄 없음");
    }

    @Test
    void noticeShowsAgainForPlayersWhoSawTheOldRules() {
        assertFalse(DeathPenalty.noticeSeen(null), "처음");
        assertFalse(DeathPenalty.noticeSeen(true), "0.3.6.1 안내만 봄 → 한 번 더");
        assertTrue(DeathPenalty.noticeSeen(DeathPenalty.NOTICE_VERSION));
        assertTrue(DeathPenalty.noticeSeen(2L), "YAML 에서 long 으로 와도");
        assertFalse(DeathPenalty.noticeSeen(1));
    }
}
