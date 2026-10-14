package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

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
        assertEquals(1.0, ps.hp(1), 1e-9);
        assertEquals(1.0 + 0.6 * 4, ps.hp(5), 1e-9);
        assertEquals(1.0 + 0.08 * 9, ps.damage(10), 1e-9);
        assertEquals(1.0 + 0.05 * 2, ps.reward(3), 1e-9);
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

        y.set("difficulty", "nightmare");
        Settings s2 = new Settings(y);
        assertTrue(s2.isDifficultySet());
        assertEquals(2.4, s2.difficulty().hp(), 1e-9);
        y.set("difficulty", "bogus");
        assertFalse(new Settings(y).isDifficultySet());
    }

    @Test
    void bundledConfigParses() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.load(new java.io.File("src/main/resources/config.yml"));
        Settings s = new Settings(y);
        assertEquals(4, s.difficulties().size());
        assertEquals(10, s.party().maxSize());
        assertEquals(50, s.level().max());
        assertEquals(5, s.level().pointsPerLevel());
        assertTrue(s.pack().port() > 0);
        assertEquals("labyrinth_world", s.worldName());
    }
}
