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
        for (double hardness : new double[] {0.3, 0.5, 0.75, 3.0, 4.5, 30.0}) {
            for (double secs = 1.0; secs <= 7.0; secs += 0.05) {
                float speed = MineMath.toolSpeed(hardness, secs);
                int ticks = MineMath.ticks(hardness, speed);
                int want = (int) Math.ceil(secs * 20 - 1e-6);
                assertTrue(Math.abs(ticks - want) <= 1, hardness + " · " + secs + "초 → " + ticks + "틱 (원함 " + want + ")");
                assertTrue(ticks >= 20, "1초보다 빠르지 않음");
            }
        }
        assertEquals(0f, MineMath.toolSpeed(0, 2.0));
        assertEquals(0, MineMath.ticks(0, 5));
    }

    @Test
    void neverFasterThanOneSecond() {
        float s = MineMath.toolSpeed(3.0, 0.2);
        assertEquals(MineMath.toolSpeed(3.0, 1.0), s);
        assertTrue(MineMath.ticks(3.0, s) >= 20);
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
        assertEquals(21, checked, "표 §3.4 의 칸 수");
    }

    @Test
    void betterPickaxeIsFasterOnEveryOre() {
        MineDef mine = MineTestData.mine();
        ToolSpec prev = null;
        for (ToolSpec t : MineTestData.pickaxes().values()) {
            if (prev != null) {
                for (MineDef.Node n : mine.ores().values()) {
                    if (!prev.canMine(n.tier())) continue;
                    assertTrue(MineMath.seconds(n, t) < MineMath.seconds(n, prev), t.tier() + " vs " + prev.tier() + " · " + n.id());
                }
                for (MineDef.Node n : mine.gems().values()) {
                    if (!prev.canMine(n.tier())) continue;
                    assertTrue(MineMath.seconds(n, t) < MineMath.seconds(n, prev), "보석 " + n.id());
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

    @Test
    void regrowFactorByPlayers() {
        assertEquals(1, MineMath.regrowFactor(0, 4), "아무도 없어도 한 사람 빠르기");
        assertEquals(1, MineMath.regrowFactor(1, 4));
        assertEquals(3, MineMath.regrowFactor(3, 4));
        assertEquals(4, MineMath.regrowFactor(4, 4));
        assertEquals(4, MineMath.regrowFactor(12, 4));
        assertEquals(1, MineMath.regrowFactor(5, 1));
        assertEquals(1, MineMath.regrowFactor(5, 0), "cap 0 = 1 로 읽음");
    }
}
