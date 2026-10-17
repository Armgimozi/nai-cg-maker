package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.ToolSpec;
import org.junit.jupiter.api.Test;

/** 캐는 초 ↔ Tool speed (계약 §2.3·§3.4). */
class MineMathTest {

    @Test
    void speedTicksRoundTrip() {
        for (double hardness : new double[] {0.3, 0.5, 0.75, 1.0, 1.5, 3.0, 4.5, 30.0}) {
            for (double secs = 0.5; secs <= 11.0; secs += 0.05) {
                float speed = MineMath.toolSpeed(hardness, secs);
                int ticks = MineMath.ticks(hardness, speed);
                int want = (int) Math.ceil(secs * 20 - 1e-6);
                assertTrue(Math.abs(ticks - want) <= 1, hardness + " · " + secs + "초 → " + ticks + "틱 (원함 " + want + ")");
                assertTrue(ticks >= 10, "0.5초보다 빠르지 않음");
            }
        }
        assertEquals(0f, MineMath.toolSpeed(0, 2.0));
        assertEquals(0, MineMath.ticks(0, 5));
    }

    @Test
    void neverFasterThanHalfSecond() {
        assertEquals(0.5, MineMath.MIN_SECONDS, 1e-12, "0.3.7: 바닥 0.5초");
        float s = MineMath.toolSpeed(3.0, 0.2);
        assertEquals(MineMath.toolSpeed(3.0, 0.5), s);
        assertEquals(10, MineMath.ticks(3.0, s));
    }

    @Test
    void clientBreakTimeMatchesServerForEveryPair() {
        // 곡괭이 6 × 캘 수 있는 광석·보석 (52쌍): 바닐라 진행(speed ÷ 단단함 ÷ 30 을 틱마다 float 로 더함)으로 부서지는 틱이
        // ⌈20 · max(0.5, 초)⌉ 와 1틱 안에서 같다 — 클라이언트 금 가는 그림이 서버 시간과 맞는다. 바닥 쌍은 10틱
        MineDef mine = MineTestData.mine();
        int pairs = 0, floored = 0;
        for (ToolSpec t : MineTestData.pickaxes().values()) {
            for (MineDef.Node n : StretchRuleTest.allNodes(mine)) {
                if (!t.canMine(n.tier())) continue;
                double s = MineMath.seconds(n, t);
                double h = MineTestData.hardness(n.block());
                int ticks = MineMath.ticks(h, MineMath.toolSpeed(h, s));
                int want = (int) Math.ceil(20 * Math.max(MineMath.MIN_SECONDS, s) - 1e-6);
                assertTrue(Math.abs(ticks - want) <= 1, t.tier() + " × " + n.id() + ": " + ticks + "틱 vs " + want);
                if (t.seconds(n.baseSeconds(), n.tier()) < MineMath.MIN_SECONDS) {
                    assertEquals(10, ticks, t.tier() + " × " + n.id() + " 바닥");
                    floored++;
                }
                pairs++;
            }
        }
        assertEquals(52, pairs, "광석 26 + 보석 노드 26");
        assertTrue(floored >= 3, "바닥 쌍 (미스릴→구리 · 오리하르콘→구리·철 …)");
    }

    @Test
    void secondsTableEqualsContract() {
        MineDef mine = MineTestData.mine();
        Params pk = MineTestData.mineJson().sub("pickaxes");
        int checked = 0;
        for (Map.Entry<String, ToolSpec> e : MineTestData.pickaxes().entrySet()) {
            Params want = pk.sub(e.getKey()).sub("seconds");
            for (MineDef.Node ore : mine.ores().values()) {
                double got = MineMath.seconds(ore, e.getValue());
                if (want.has(ore.id())) {
                    assertEquals(want.dbl(ore.id(), 0), got, 0.01, e.getKey() + " × " + ore.id());
                    checked++;
                } else {
                    assertEquals(Double.POSITIVE_INFINITY, got, e.getKey() + " 는 " + ore.id() + " 을 못 캠");
                }
            }
        }
        assertEquals(26, checked, "표 §3.4 의 칸 수 (0.3.6.1: 한 단계 위 5칸 더)");
    }

    @Test
    void betterPickaxeIsFasterOnEveryOre() {
        MineDef mine = MineTestData.mine();
        ToolSpec prev = null;
        for (ToolSpec t : MineTestData.pickaxes().values()) {
            if (prev != null) {
                for (MineDef.Node n : mine.ores().values()) {
                    if (!prev.canMine(n.tier())) continue;
                    double a = MineMath.seconds(n, t), b = MineMath.seconds(n, prev);
                    assertTrue(a < b || a == MineMath.MIN_SECONDS, t.tier() + " vs " + prev.tier() + " · " + n.id() + " (바닥이면 같아도 됨)");
                }
                for (MineDef.Node n : mine.gems().values()) {
                    if (!prev.canMine(n.tier())) continue;
                    double a = MineMath.seconds(n, t), b = MineMath.seconds(n, prev);
                    assertTrue(a < b || a == MineMath.MIN_SECONDS, "보석 " + n.id());
                }
            }
            prev = t;
        }
    }

    @Test
    void gemNodesAreSlowerThanSameTierOre() {
        MineDef mine = MineTestData.mine();
        for (MineDef.Node g : mine.gems().values()) {
            for (MineDef.Node o : mine.ores().values()) {
                if (o.tier() == g.tier()) assertEquals(o.baseSeconds() * 1.5, g.baseSeconds(), 1e-9, g.id());
            }
        }
    }

    @Test
    void bonusYield() {
        assertEquals(2, MineMath.baseYield(false, 0.1, 0.05));
        assertEquals(1, MineMath.baseYield(false, 0.1, 0.5));
        assertEquals(1, MineMath.baseYield(false, 0.0, 0.0));
        assertEquals(1, MineMath.baseYield(true, 1.0, 0.0), "보석 노드는 덤 없음");
    }
}
