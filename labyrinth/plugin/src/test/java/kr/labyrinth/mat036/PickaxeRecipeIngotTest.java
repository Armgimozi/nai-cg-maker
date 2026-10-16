package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

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
 */
class PickaxeRecipeIngotTest {

    static final Set<String> ESSENCES = Set.of("dim_essence", "labyrinth_essence", "radiant_essence");

    @Test
    void eachPickaxeUsesItsOwnMetalAndGem() {
        Content c = Mat036.content();
        int prevIngots = 0;
        for (int t = 2; t <= 6; t++) {
            String metal = Mat036.METALS.get(t - 1);
            String id = metal + "_pickaxe";
            RecipeDef r = c.recipes().get(id);
            assertNotNull(r, id);
            assertEquals(MineNames.STATION_SMELTER, r.station(), id);
            assertEquals(4, r.materials().size(), id + " 재료 = 앞 곡괭이 · 주괴 · 보석 · 정수 (+ 골드)");
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
                } else {
                    assertEquals(prevPick, d.id(), id + " 모르는 재료 " + d.id());
                }
            }
            assertTrue(ingots >= 10 && gems >= 2 && ess >= 2, id + " 개수 " + ingots + "/" + gems + "/" + ess);
            assertTrue(ingots >= prevIngots, id + " 주괴 개수가 앞 곡괭이보다 적지 않다");
            prevIngots = ingots;
            assertTrue(r.gold() > 0, id + " 골드");
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
