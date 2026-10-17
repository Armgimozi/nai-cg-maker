package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineKind;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.mine.MineNames;
import kr.labyrinth.mine.TierRule;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.1 주인 결정 "철 곡괭이로 업글하려면 철 주괴가 필요한게 정상 아닐까": 곡괭이 레시피는 그 곡괭이 제 금속 주괴 + 같은 등급 보석 +
 * 앞 곡괭이 + 정수 + 골드. 그 주괴의 광석과 보석은 앞 곡괭이로 (한 단계 위라 느리게) 캘 수 있어야 사다리가 막히지 않는다.
 * 0.3.7: 은·금·미스릴·오리하르콘 곡괭이는 그 층 정예 재료 3개가 더 든다 (4·7·9·10층 rare — 레벨 조건이 아닌 미궁 진행 문). 철 곡괭이는 그대로.
 */
class PickaxeRecipeIngotTest {

    static final Set<String> ESSENCES = Set.of("dim_essence", "labyrinth_essence", "radiant_essence");
    /** 곡괭이 → 정예 재료 문 (id, 나오는 층). 철 곡괭이는 없음. */
    static final Map<String, Object[]> GATE = Map.of("silver_pickaxe", new Object[] {"verdigris_plate", 4},
            "gold_pickaxe", new Object[] {"tuning_fork_core", 7}, "mithril_pickaxe", new Object[] {"regulator_pendulum", 9},
            "orichalcum_pickaxe", new Object[] {"gatekeeper_rune", 10});

    @Test
    void eachPickaxeUsesItsOwnMetalAndGem() {
        Content c = Mat036.content();
        int prevIngots = 0;
        long prevGold = 0;
        for (int t = 2; t <= 6; t++) {
            String metal = Mat036.METALS.get(t - 1);
            String id = metal + "_pickaxe";
            RecipeDef r = c.recipes().get(id);
            assertNotNull(r, id);
            assertEquals(MineNames.STATION_SMELTER, r.station(), id);
            Object[] gate = GATE.get(id);
            assertEquals(gate == null ? 4 : 5, r.materials().size(), id + " 재료 = 앞 곡괭이 · 주괴 · 보석 · 정수 (+ 정예 재료) (+ 골드)");
            if (gate != null) {
                ItemDef g = c.item((String) gate[0]);
                assertNotNull(g, id + " 정예 재료");
                assertEquals(3, r.materials().get(g.id()), id + " 정예 재료 3개");
                assertEquals(kr.labyrinth.content.Rarity.RARE, g.rarity(), g.id() + " rare");
                assertEquals((int) gate[1], g.floor(), g.id() + " 층");
            }
            String prevPick = Mat036.METALS.get(t - 2) + "_pickaxe";
            assertEquals(1, r.materials().get(prevPick), id + " 앞 곡괭이 1");
            int ingots = 0, gems = 0, ess = 0;
            for (var e : r.materials().entrySet()) {
                ItemDef d = c.item(e.getKey());
                assertNotNull(d, e.getKey());
                if (d.mineKind() == MineKind.INGOT) {
                    assertEquals(metal + "_ingot", d.id(), id + " 는 제 금속 주괴만 (앞 금속 주괴 아님)");
                    ingots = e.getValue();
                } else if (d.mineKind() == MineKind.GEM) {
                    assertEquals(Mat036.GEMS.get(t - 1), d.id(), id + " 는 같은 등급 보석");
                    gems = e.getValue();
                } else if (ESSENCES.contains(d.id())) {
                    ess = e.getValue();
                } else if (gate != null && gate[0].equals(d.id())) {
                    assertEquals(3, e.getValue(), id + " 정예 재료");
                } else {
                    assertEquals(prevPick, d.id(), id + " 모르는 재료 " + d.id());
                }
            }
            assertTrue(ingots >= 10 && gems >= 2 && ess >= 2, id + " 개수 " + ingots + "/" + gems + "/" + ess);
            if (t < 6) assertTrue(ingots >= prevIngots, id + " 주괴 개수가 앞 곡괭이보다 적지 않다");
            // 경제 검토 (0.3.6.1): 미스릴 곡괭이가 이미 오리하르콘·용혈석을 캐므로 오리하르콘 곡괭이는 더 여는 것 없는 마지막 곡괭이 —
            // 재료를 줄였다 (주괴 24 → 12, 10단계 한 벌 주괴 28 의 절반 아래). 골드는 사다리대로 오른다.
            else assertTrue(ingots <= 14 && gems <= 2, id + " 는 가장 빠를 뿐이라 재료가 적다: " + ingots + "/" + gems);
            prevIngots = ingots;
            assertTrue(r.gold() > prevGold, id + " 골드가 앞 곡괭이보다 많다");
            prevGold = r.gold();
            // 앞 곡괭이로 그 주괴의 광석과 보석을 캘 수 있다 (한 단계 위, 느리게)
            ItemDef prev = c.item(prevPick);
            var ore = c.mine().ores().get(metal + "_ore");
            var gem = c.mine().gems().get(Mat036.GEMS.get(t - 1));
            assertEquals(TierRule.Verdict.OK, TierRule.check(prev.tool(), ore.tier()), prevPick + " 로 " + ore.id());
            assertEquals(TierRule.Verdict.OK, TierRule.check(prev.tool(), gem.tier()), prevPick + " 로 " + gem.id());
            assertTrue(TierRule.slow(prev.tool(), ore.tier()) && TierRule.slow(prev.tool(), gem.tier()), "한 단계 위라 느림");
        }
        assertEquals(12, c.recipes().get("iron_pickaxe").materials().get("iron_ingot"), "첫 철 곡괭이 = 철 주괴 12 (표 D)");
    }
}
