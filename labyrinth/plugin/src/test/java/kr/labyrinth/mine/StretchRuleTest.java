package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 주인 결정 "구리 곡괭이로 철을 캘 수 있고 철 괭이로 은을 캐는 식": 곡괭이 tier t 는 tier ≤ t + 1 광석·보석을 캔다.
 * 한 단계 위는 그 광석 제 곡괭이 빠르기 × 0.6 (계약 rules.stretch_factor) 로 느리고, 두 단계 위는 그대로 "곡괭이가 약해 캘 수 없습니다".
 */
class StretchRuleTest {

    static List<ToolSpec> ladder() { return new ArrayList<>(MineTestData.pickaxes().values()); }

    @Test
    void reachIsOneTierAboveAndNoMore() {
        for (ToolSpec t : ladder()) {
            assertEquals(Math.min(6, t.tier() + 1), t.maxHardness(), "tier " + t.tier());
            for (int h = 1; h <= 6; h++) {
                TierRule.Verdict v = TierRule.check(t, h);
                if (h <= t.tier()) assertTrue(v == TierRule.Verdict.OK && !TierRule.slow(t, h), t.tier() + "→" + h + " 제 등급 이하");
                else if (h == t.tier() + 1) assertTrue(v == TierRule.Verdict.OK && TierRule.slow(t, h), t.tier() + "→" + h + " 한 단계 위는 느리게");
                else assertEquals(MineNames.TOO_WEAK, TierRule.message(v), t.tier() + "→" + h + " 두 단계 위는 못 캠");
            }
        }
        ToolSpec copper = MineTestData.pickaxes().get("copper_pickaxe");
        MineDef mine = MineTestData.mine();
        assertNull(TierRule.message(TierRule.check(copper, mine.ores().get("iron_ore").tier())), "구리 곡괭이로 철");
        assertNull(TierRule.message(TierRule.check(copper, mine.gems().get("garnet").tier())), "구리 곡괭이로 석류석");
        assertEquals(MineNames.TOO_WEAK, TierRule.message(TierRule.check(copper, mine.ores().get("silver_ore").tier())), "구리 곡괭이로 은은 못 캠");
        ToolSpec iron = MineTestData.pickaxes().get("iron_pickaxe");
        assertNull(TierRule.message(TierRule.check(iron, mine.ores().get("silver_ore").tier())), "철 곡괭이로 은");
        assertNull(TierRule.message(TierRule.check(iron, mine.gems().get("moonstone").tier())), "철 곡괭이로 월장석");
        assertEquals(MineNames.TOO_WEAK, TierRule.message(TierRule.check(iron, mine.ores().get("gold_ore").tier())));
        ToolSpec ori = MineTestData.pickaxes().get("orichalcum_pickaxe");
        for (MineDef.Node n : mine.ores().values()) assertFalse(TierRule.slow(ori, n.tier()), "오리하르콘 곡괭이는 다 제 빠르기");
    }

    @Test
    void oneTierAboveIsSlowerByTheContractFactor() {
        double factor = MineTestData.mineJson().sub("rules").dbl("stretch_factor", -1);
        assertEquals(0.6, factor, 1e-9);
        assertTrue(factor >= 0.55 && factor <= 0.7, "주인 결정의 '눈에 띄게 느림' 폭");
        List<ToolSpec> l = ladder();
        MineDef mine = MineTestData.mine();
        for (int i = 0; i + 1 < l.size(); i++) {
            ToolSpec low = l.get(i), own = l.get(i + 1);
            int h = own.tier();
            assertEquals(own.speedFor(h) * factor, low.speedFor(h), 1e-3, low.tier() + " 곡괭이로 " + h + " = 제 곡괭이 × " + factor);
            for (MineDef.Node n : mine.ores().values()) {
                if (n.tier() != h) continue;
                double slow = MineMath.seconds(n, low), fast = MineMath.seconds(n, own);
                assertEquals(fast / factor, slow, 1e-6, n.id());
                assertTrue(slow >= fast * 1.5, n.id() + " 는 한 단계 아래 곡괭이로 눈에 띄게 느림 (" + slow + " vs " + fast + ")");
                assertTrue(slow > MineMath.seconds(n, l.get(Math.min(l.size() - 1, i + 2))), "위 곡괭이일수록 빠름");
            }
        }
        // 구리 곡괭이로 철 광석: 2.9 ÷ (1.2 × 0.6) ≈ 4.0초 · 철 곡괭이 2.4초
        MineDef.Node ironOre = mine.ores().get("iron_ore");
        assertEquals(4.03, MineMath.seconds(ironOre, l.get(0)), 0.01);
        assertEquals(2.42, MineMath.seconds(ironOre, l.get(1)), 0.01);
    }

    @Test
    void pickaxeComponentsIncludeTheSlowBlocksOnly() {
        MineDef mine = MineTestData.mine();
        for (ToolSpec t : ladder()) {
            PickaxePlan plan = PickaxePlan.of(t, mine, MineTestData::hardness);
            for (MineDef.Node n : allNodes(mine)) {
                boolean want = n.tier() <= t.tier() + 1;
                assertEquals(want, plan.canBreak().contains(n.block()), t.tier() + " CAN_BREAK " + n.id());
            }
            for (PickaxePlan.Rule r : plan.rules()) {
                MineDef.Node n = mine.node(r.node());
                if (n.tier() > t.tier()) {
                    PickaxePlan.Rule same = plan.rules().stream().filter(x -> mine.node(x.node()).tier() == t.tier() && mine.node(x.node()).isOre() == n.isOre())
                            .findFirst().orElseThrow();
                    assertTrue(r.seconds() > same.seconds(), n.id() + " 는 제 등급보다 오래 걸림");
                }
            }
        }
    }

    @Test
    void fallbackWhenItemsYmlHasNoSlowSpeed() {
        ToolSpec old = new ToolSpec(ToolSpec.PICKAXE, 2, Map.of(1, 1.2, 2, 1.2), 0.02);   // 0.3.6 items.yml (한 단계 위 줄 없음)
        assertTrue(old.canMine(3));
        assertEquals(1.2 * ToolSpec.STRETCH_FALLBACK, old.speedFor(3), 1e-9);
        assertFalse(old.canMine(4));
        assertEquals(0, new ToolSpec(ToolSpec.PICKAXE, 0, Map.of(), 0).maxHardness(), "tier 0 은 아무것도 못 캠");
    }

    static List<MineDef.Node> allNodes(MineDef m) {
        List<MineDef.Node> out = new ArrayList<>(m.ores().values());
        out.addAll(m.gems().values());
        return out;
    }
}
