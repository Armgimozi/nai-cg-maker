package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.util.Map;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;
import org.junit.jupiter.api.Test;

/** 단단함 규칙 (주인 결정 2 + 0.3.6.1): 광석·보석 tier ≤ 곡괭이 tier + 1 만 (한 단계 위는 느림), 레벨 조건 없음, 못 캐면 액션바 한 줄. */
class TierRuleTest {

    @Test
    void onlyTierAtMostPickaxe() {
        MineDef mine = MineTestData.mine();
        for (ToolSpec t : MineTestData.pickaxes().values()) {
            for (MineDef.Node n : mine.ores().values()) {
                TierRule.Verdict v = TierRule.check(t, n.tier());
                assertEquals(n.tier() <= t.tier() + 1 ? TierRule.Verdict.OK : TierRule.Verdict.TOO_WEAK, v, t.tier() + " · " + n.id());
                assertEquals(n.tier() == t.tier() + 1, TierRule.slow(t, n.tier()), t.tier() + " · " + n.id() + " 느림");
            }
            for (MineDef.Node g : mine.gems().values()) {
                assertEquals(g.tier() <= t.tier() + 1 ? TierRule.Verdict.OK : TierRule.Verdict.TOO_WEAK, TierRule.check(t, g.tier()), g.id());
                assertEquals(g.tier() == t.tier() + 1, TierRule.slow(t, g.tier()), g.id() + " 느림");
            }
        }
    }

    @Test
    void contractMinesListMatches() {
        var pk = MineTestData.mineJson().sub("pickaxes");
        MineDef mine = MineTestData.mine();
        for (var e : MineTestData.pickaxes().entrySet()) {
            var mines = new java.util.HashSet<>(pk.sub(e.getKey()).strings("mines"));
            for (MineDef.Node n : mine.ores().values()) assertEquals(mines.contains(n.id()), e.getValue().canMine(n.tier()), e.getKey() + " " + n.id());
            for (MineDef.Node n : mine.gems().values()) assertEquals(mines.contains(n.id()), e.getValue().canMine(n.tier()), e.getKey() + " " + n.id());
        }
    }

    @Test
    void messages() {
        ToolSpec copper = new ToolSpec(ToolSpec.PICKAXE, 1, Map.of(1, 1.0), 0);
        assertEquals("곡괭이가 약해 캘 수 없습니다", TierRule.message(TierRule.check(copper, 3)), "두 단계 위는 그대로 못 캠");
        assertNull(TierRule.message(TierRule.check(copper, 2)), "구리 곡괭이로 철 (주인 결정)");
        assertEquals(MineNames.TOO_WEAK, TierRule.message(TierRule.Verdict.TOO_WEAK));
        assertNull(TierRule.message(TierRule.check(copper, 1)));
        assertEquals(TierRule.Verdict.NO_PICKAXE, TierRule.check(null, 1));
        assertEquals(TierRule.Verdict.NO_PICKAXE, TierRule.check(new ToolSpec("axe", 6, Map.of(), 0), 1));
        assertEquals(MineNames.NEED_PICKAXE, TierRule.message(TierRule.Verdict.NO_PICKAXE));
    }

    @Test
    void noLevelGateAnywhere() {
        var pk = MineTestData.mineJson().sub("pickaxes");
        for (String id : pk.keys()) assertNull(pk.sub(id).get("level_req"), id + " level_req");
        for (MineDef.Level l : MineTestData.mine().levels()) {
            assertEquals(null, MineTestData.mineJson().maps("levels").get(l.n() - 1).get("level_req"), l.id());
        }
    }
}
