package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.EnhanceDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineKind;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.items.enhance.EnhanceRules;
import org.junit.jupiter.api.Test;

/**
 * 강화 재료의 주괴 (계약 §2.9 · gen_enhance): mid(+4~+6)·high(+7~+10) 에 그 장비의 주 금속 주괴가 든다.
 * 레시피 장비 = 레시피에서 가장 많이 드는 주괴(같으면 윗 금속) · 드롭 장비 = 힘 규칙 pos 반올림 금속. low 에는 주괴가 없다
 * (부위가 하나뿐인 7층에서 겹침을 피하려고 주괴가 P 가 된 장비만 예외). R·K(정예 재료·정수·핵) 는 주괴·부위가 아니다.
 */
class EnhanceIngotTest {

    static final Map<String, Double> STEP = GearRecipeIngotTest.STEP;

    static String primary(ItemDef d) {
        double p = d.tier() + STEP.getOrDefault(d.rarity().id(), 0.0) + (d.sources().contains("boss") ? 0.5 : 0);
        double pos = Math.max(1, Math.min(6, 1 + (p - 1) / 2));
        int lo = (int) pos;
        int r = lo + (pos - lo >= 0.375 - 1e-9 ? 1 : 0);
        return Mat036.METALS.get(Math.max(1, Math.min(6, r)) - 1) + "_ingot";
    }

    static String recipeIngot(Content c, RecipeDef r) {
        String best = null;
        int bn = -1, br = -1;
        for (var e : r.materials().entrySet()) {
            ItemDef m = c.item(e.getKey());
            if (m == null || m.mineKind() != MineKind.INGOT) continue;
            if (e.getValue() > bn || (e.getValue() == bn && m.mineLevel() > br)) {
                best = e.getKey();
                bn = e.getValue();
                br = m.mineLevel();
            }
        }
        return best;
    }

    @Test
    void midAndHighUseTheMainMetalIngot() {
        Content c = Mat036.content();
        EnhanceDef t = c.enhance();
        Map<String, RecipeDef> recipeOf = new HashMap<>();
        for (RecipeDef r : c.recipes().values()) recipeOf.putIfAbsent(r.result(), r);
        List<String> bad = new ArrayList<>();
        int n = 0, ingotP = 0;
        for (ItemDef d : c.items().values()) {
            if (!EnhanceRules.enhanceable(d)) continue;
            n++;
            RecipeDef r = recipeOf.get(d.id());
            String want = r != null && recipeIngot(c, r) != null ? recipeIngot(c, r) : primary(d);
            for (int tg : new int[] {4, 5, 6, 7, 8, 9, 10}) {
                List<String> ing = new ArrayList<>();
                for (EnhanceDef.Cost k : t.costs(d.id(), tg)) {
                    ItemDef m = c.item(k.item());
                    if (m != null && m.mineKind() == MineKind.INGOT) ing.add(k.item());
                }
                if (!ing.equals(List.of(want))) bad.add(d.id() + " +" + tg + " " + ing + " (기대 " + want + ")");
            }
            boolean lowIngot = t.costs(d.id(), 1).stream().anyMatch(k -> c.item(k.item()) != null && c.item(k.item()).mineKind() == MineKind.INGOT);
            if (lowIngot) {
                ingotP++;
                assertEquals(7, d.tier(), d.id() + ": 주괴가 P 인 장비는 부위가 하나뿐인 층(7)만");
            }
            // R (+7~+8) 은 정예 재료·정수 — 주괴·광석·보석이 아니다
            List<EnhanceDef.Cost> high = t.costs(d.id(), 8);
            String rItem = high.get(high.size() - 1).item();
            ItemDef rm = c.item(rItem);
            assertTrue(rm != null && rm.mineKind() == null, d.id() + " R = " + rItem);
        }
        assertEquals(List.of(), bad, "mid·high 주괴가 주 금속이 아님");
        assertEquals(370, n, "강화 장비 수 (0.3.6 364 + 0.3.7 신화 6)");
        System.out.println("ENHANCE036 장비 " + n + " · 주괴가 P 인 장비 " + ingotP);
    }
}
