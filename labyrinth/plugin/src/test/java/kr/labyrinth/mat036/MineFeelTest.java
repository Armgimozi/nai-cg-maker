package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;
import kr.labyrinth.mine.MineMath;
import org.junit.jupiter.api.Test;

/**
 * 0.3.7 주인: "그리고 철 캐는 속도랑 구리 캐는 속도랑 별로 차이가 없어 보이는데" — jar 의 content (mine.yml + items.yml tool) 로
 * 캐는 맛을 본다 (계약 검사 check_contract 와 같은 것을 서버가 실제로 읽는 값으로).
 * <ol>
 *   <li>같은 곡괭이로 한 등급 위 광석은 1.35배 이상 오래 (구리 ↔ 철이 눈에 띔)</li>
 *   <li>같은 광석을 한 단계 위 곡괭이로 0.65배 이하 (바닥 0.5초에 닿은 쌍은 뺌)</li>
 *   <li>제 곡괭이로는 구리 약 2.0초 → 오리하르콘 약 3.5초로 조금씩 오름</li>
 *   <li>한 단계 위를 앞 곡괭이로 캐면 반 빠르기 이하 (올릴 맛)</li>
 *   <li>보석 노드도 같은 곡선 (같은 등급 광석 × 1.5)</li>
 * </ol>
 */
class MineFeelTest {

    static final List<String> PICKS = List.of("copper_pickaxe", "iron_pickaxe", "silver_pickaxe", "gold_pickaxe", "mithril_pickaxe",
            "orichalcum_pickaxe");

    static List<ToolSpec> tools(Content c) {
        List<ToolSpec> out = new ArrayList<>();
        for (String id : PICKS) {
            ItemDef d = c.item(id);
            assertNotNull(d, id);
            out.add(d.tool());
        }
        return out;
    }

    static MineDef.Node ore(MineDef m, int tier) {
        return m.ores().values().stream().filter(n -> n.tier() == tier).findFirst().orElseThrow();
    }

    static MineDef.Node gem(MineDef m, int tier) {
        return m.gems().values().stream().filter(n -> n.tier() == tier).findFirst().orElseThrow();
    }

    static boolean floored(MineDef.Node n, ToolSpec t) {
        return t.seconds(n.baseSeconds(), n.tier()) < MineMath.MIN_SECONDS - 1e-9;
    }

    @Test
    void tierUpTakesClearlyLonger() {
        Content c = Mat036.content();
        MineDef m = c.mine();
        for (ToolSpec t : tools(c)) {
            for (int o = 1; o < Math.min(6, t.maxHardness()); o++) {
                if (floored(ore(m, o), t)) continue;
                double a = MineMath.seconds(ore(m, o), t), b = MineMath.seconds(ore(m, o + 1), t);
                assertTrue(b / a >= 1.35, t.tier() + " 곡괭이: " + (o + 1) + " 등급이 " + o + " 등급의 " + b / a + "배");
            }
        }
        ToolSpec iron = tools(c).get(1);
        assertEquals(1.25, MineMath.seconds(ore(m, 1), iron), 1e-6, "철 곡괭이로 구리 1.25초");
        assertEquals(2.25, MineMath.seconds(ore(m, 2), iron), 1e-6, "철 곡괭이로 철 2.25초");
    }

    @Test
    void pickaxeUpIsClearlyFaster() {
        Content c = Mat036.content();
        MineDef m = c.mine();
        List<ToolSpec> l = tools(c);
        int checked = 0;
        for (int o = 1; o <= 6; o++) {
            for (int k = Math.max(0, o - 2); k + 1 < l.size(); k++) {
                ToolSpec lo = l.get(k), hi = l.get(k + 1);
                if (!lo.canMine(o) || floored(ore(m, o), hi)) continue;
                double r = MineMath.seconds(ore(m, o), hi) / MineMath.seconds(ore(m, o), lo);
                assertTrue(r <= 0.65, o + " 등급: " + hi.tier() + " 곡괭이가 " + lo.tier() + " 곡괭이의 " + r + "배");
                checked++;
            }
        }
        assertTrue(checked >= 15, "견준 쌍 " + checked);
    }

    @Test
    void ownPickaxeRisesGentlyAndPreviousIsHalfSpeed() {
        Content c = Mat036.content();
        MineDef m = c.mine();
        List<ToolSpec> l = tools(c);
        double prev = 0;
        for (int o = 1; o <= 6; o++) {
            double own = MineMath.seconds(ore(m, o), l.get(o - 1));
            assertTrue(own >= prev, o + " 등급 제 곡괭이 " + own + "초");
            prev = own;
            if (o >= 2) {
                double slow = MineMath.seconds(ore(m, o), l.get(o - 2));
                assertTrue(slow >= 2 * own - 1e-6, o + " 등급을 앞 곡괭이로 " + slow + "초 vs 제 곡괭이 " + own + "초 (반 빠르기 이하)");
            }
        }
        assertEquals(2.0, MineMath.seconds(ore(m, 1), l.get(0)), 0.1, "구리 곡괭이로 구리 약 2.0초");
        assertEquals(3.5, MineMath.seconds(ore(m, 6), l.get(5)), 0.1, "오리하르콘 곡괭이로 오리하르콘 약 3.5초");
    }

    @Test
    void gemNodesFollowTheSameCurve() {
        Content c = Mat036.content();
        MineDef m = c.mine();
        for (int o = 1; o <= 6; o++) assertEquals(ore(m, o).baseSeconds() * 1.5, gem(m, o).baseSeconds(), 1e-3, "보석 노드 " + o);
        for (ToolSpec t : tools(c)) {
            for (int o = 1; o < Math.min(6, t.maxHardness()); o++) {
                if (floored(gem(m, o), t)) continue;
                double a = MineMath.seconds(gem(m, o), t), b = MineMath.seconds(gem(m, o + 1), t);
                assertTrue(b / a >= 1.35, t.tier() + " 곡괭이 보석 노드 " + o + " → " + (o + 1) + ": " + b / a + "배");
            }
        }
    }
}
