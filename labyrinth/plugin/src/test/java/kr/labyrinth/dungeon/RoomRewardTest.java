package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.stats.XpCurve;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/**
 * 전투방 보상 규칙 (dungeon.yml): 솔로·2인 몹 수(party_mob_count) + 웨이브별 보상 보정(party_mob_reward),
 * 정리 회복(room_clear_heal), 층 첫 돌파 보너스(first_clear_bonus). 키가 없는 예전 dungeon.yml 도 새 기본값으로 켜진다.
 */
class RoomRewardTest {

    private static final double EPS = 1e-9;

    private static DungeonConfig parse(String yaml) throws InvalidConfigurationException {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(yaml);
        return DungeonConfig.of(y);
    }

    @Test
    void missingKeysUseCodeDefaults() throws InvalidConfigurationException {
        // 예전 서버 파일: 새 키가 하나도 없다 (jar 기본값을 setDefaults 로 붙인 경우와 안 붙인 경우 모두)
        YamlConfiguration old = new YamlConfiguration();
        old.loadFromString("version: 1\nmob_count_per_member: 0.15\nrest_heal: 0.5\n");
        YamlConfiguration withJar = new YamlConfiguration();
        withJar.loadFromString("version: 1\nmob_count_per_member: 0.15\nrest_heal: 0.5\n");
        withJar.setDefaults(YamlConfiguration.loadConfiguration(new File("src/main/resources/dungeon.yml")));
        for (DungeonConfig c : new DungeonConfig[] {DungeonConfig.of(old), DungeonConfig.of(withJar), DungeonConfig.defaults()}) {
            assertEquals(0.7, c.mobCountMult(1), EPS);
            assertEquals(0.9, c.mobCountMult(2), EPS);
            assertEquals(1.0, c.mobCountMult(3), EPS);
            assertEquals(1.0, c.mobCountMult(10), EPS);
            assertTrue(c.partyMobReward());
            assertEquals(0.15, c.roomClearHeal(), EPS);
            assertEquals(0.4, c.firstClearBonus(), EPS);
        }
        // 빈 묶음도 기본값
        assertEquals(0.7, parse("party_mob_count: {}\n").mobCountMult(1), EPS);
        assertEquals(0.9, parse("party_mob_count:\n  enabled: true\n").mobCountMult(2), EPS);
    }

    @Test
    void bundledFileMatchesCodeDefaults() {
        DungeonConfig jar = DungeonConfig.of(YamlConfiguration.loadConfiguration(new File("src/main/resources/dungeon.yml")));
        DungeonConfig code = DungeonConfig.defaults();
        assertEquals(code.partyMobCount(), jar.partyMobCount());
        assertEquals(code.partyMobReward(), jar.partyMobReward());
        assertEquals(code.roomClearHeal(), jar.roomClearHeal(), EPS);
        assertEquals(code.firstClearBonus(), jar.firstClearBonus(), EPS);
    }

    @Test
    void explicitSettingsAndDisable() throws InvalidConfigurationException {
        DungeonConfig off = parse("party_mob_count:\n  enabled: false\n  1: 0.7\nroom_clear_heal: 0\nfirst_clear_bonus: 0\n");
        for (int n = 1; n <= 10; n++) assertEquals(1.0, off.mobCountMult(n), EPS);
        assertEquals(1.0, parse("party_mob_count: false\n").mobCountMult(1), EPS);
        assertEquals(0, off.roomClearHeal(), EPS);
        assertEquals(0, off.firstClearXp(XpCurve.DEFAULT, new IntRange(5, 10)));

        DungeonConfig one = parse("party_mob_count: {1: 1.0}\n");
        assertEquals(1.0, one.mobCountMult(1), EPS);
        assertEquals(1.0, one.mobCountMult(2), EPS, "적힌 인원만 바뀌고 나머지는 1.0");

        DungeonConfig clamp = parse("party_mob_count: {1: 0.01, 2: 9}\nroom_clear_heal: 3\n");
        assertEquals(0.1, clamp.mobCountMult(1), EPS);
        assertEquals(1.5, clamp.mobCountMult(2), EPS);
        assertEquals(1.0, clamp.roomClearHeal(), EPS);
    }

    @Test
    void soloBattleWaveKeepsRoomReward() {
        DungeonConfig c = DungeonConfig.defaults();
        // 솔로 1층 mob_density 3/4/5 → 2/3/4, 한 마리당 3/2 · 4/3 · 5/4
        int[][] solo = {{3, 2}, {4, 3}, {5, 4}};
        for (int[] s : solo) {
            DungeonConfig.Wave w = c.battleWave(s[0], 1);
            assertEquals(s[1], w.count(), "굴림 " + s[0]);
            assertEquals((double) s[0] / s[1], w.rewardMult(), EPS);
        }
        // 방 하나 보상(마리 수 × 배율) = 배율 없이 나왔을 수 — 모든 인원·굴림에서
        for (int n = 1; n <= 10; n++) {
            for (int base = 1; base <= 14; base++) {
                DungeonConfig.Wave w = c.battleWave(base, n);
                int full = (int) Math.max(1, Math.min(c.maxMobsPerRoom(), Math.round(base * (1 + c.mobCountPerMember() * (n - 1)))));
                assertTrue(w.count() >= 1 && w.count() <= c.maxMobsPerRoom());
                assertEquals(full, w.count() * w.rewardMult(), 1e-6, "n=" + n + " base=" + base);
                if (n >= 3) {
                    assertEquals(full, w.count(), "3인 이상은 몹 수 그대로");
                    assertEquals(1.0, w.rewardMult(), EPS);
                }
            }
        }
    }

    @Test
    void eliteEscortScalesWithPartySize() {
        DungeonConfig c = DungeonConfig.defaults();
        // 솔로 호위 2~3 → 1~2 (2→1 은 한 마리당 ×2, 3→2 는 ×1.5)
        assertEquals(1, c.eliteEscort(2, 1).count());
        assertEquals(2.0, c.eliteEscort(2, 1).rewardMult(), EPS);
        assertEquals(2, c.eliteEscort(3, 1).count());
        assertEquals(1.5, c.eliteEscort(3, 1).rewardMult(), EPS);
        // 2인 ×0.9 는 반올림으로 그대로, 파티는 변화 없음
        for (int n = 2; n <= 10; n++) {
            for (int base = 2; base <= 3; base++) {
                assertEquals(base, c.eliteEscort(base, n).count(), "n=" + n);
                assertEquals(1.0, c.eliteEscort(base, n).rewardMult(), EPS);
            }
        }
    }

    @Test
    void rewardCompensationCanBeTurnedOff() throws InvalidConfigurationException {
        DungeonConfig c = parse("party_mob_reward: false\n");
        assertFalse(c.partyMobReward());
        assertEquals(2, c.battleWave(3, 1).count(), "몹 수는 줄고");
        assertEquals(1.0, c.battleWave(3, 1).rewardMult(), EPS, "보상 보정은 없다");
        assertEquals(1.0, c.eliteEscort(2, 1).rewardMult(), EPS);
    }

    @Test
    void roomCapIsAppliedBeforeRatio() throws InvalidConfigurationException {
        // 상한에 걸리면 줄인 수와 원래 수가 같아질 수 있다 → 보정 1
        DungeonConfig c = parse("max_mobs_per_room: 3\n");
        DungeonConfig.Wave w = c.battleWave(5, 1);
        assertEquals(3, w.count());
        assertEquals(1.0, w.rewardMult(), EPS);
    }

    @Test
    void firstClearBonusIsLevelBandXp() {
        DungeonConfig c = DungeonConfig.defaults();
        XpCurve curve = XpCurve.DEFAULT;
        // 2층 level_range [5, 10]: 5→10 필요 경험치 합 4,887 × 0.4
        long band = curve.totalTo(10) - curve.totalTo(5);
        assertEquals(4887, band);
        assertEquals(Math.round(4887 * 0.4), c.firstClearXp(curve, new IntRange(5, 10)));
        assertEquals(Math.round((curve.totalTo(5) - curve.totalTo(1)) * 0.4), c.firstClearXp(curve, new IntRange(1, 5)));
        assertEquals(0, c.firstClearXp(curve, new IntRange(5, 5)));
        assertEquals(0, c.firstClearXp(null, new IntRange(5, 10)));
    }
}
