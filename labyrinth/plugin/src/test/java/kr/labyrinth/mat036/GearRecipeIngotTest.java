package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineKind;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.mine.MineNames;
import org.junit.jupiter.api.Test;

/**
 * 장비 레시피의 주괴 (계약 §2.7 — 주인 결정 4): 금속 = 장비 힘 P = 단계 + 희귀도 걸음 + 보스 0.5 → pos = clamp(1 + (P−1)/2, 1, 6),
 * 소수부가 0.375~0.625 면 이웃 두 금속 섞음. 개수 n = 반올림(0.3.5.1 일반 재료 합 × 0.20), 최소 2. 아래 금속 먼저. 띠 표가 아니다.
 */
class GearRecipeIngotTest {

    static final Map<String, Double> STEP = Map.of("common", 0.0, "uncommon", 0.25, "rare", 0.5, "epic", 1.0, "legendary", 1.5, "mythic", 2.0);

    /** 힘 규칙 → 금속 → 개수 (윗 금속이 뒤). */
    static Map<String, Integer> expected(int tier, String rarity, boolean boss, int n) {
        double p = tier + STEP.getOrDefault(rarity, 0.0) + (boss ? 0.5 : 0);
        double pos = Math.max(1, Math.min(6, 1 + (p - 1) / 2));
        int lo = (int) pos;
        double f = pos - lo;
        Map<String, Integer> out = new LinkedHashMap<>();
        List<String> m = Mat036.METALS;
        if (lo >= 6) out.put(m.get(5) + "_ingot", n);
        else if (f < 0.375 - 1e-9) out.put(m.get(lo - 1) + "_ingot", n);
        else if (f > 0.625 + 1e-9) out.put(m.get(lo) + "_ingot", n);
        else {
            int up = Math.max(1, Math.min(n - 1, (int) (n * f + 0.5)));
            out.put(m.get(lo - 1) + "_ingot", n - up);
            out.put(m.get(lo) + "_ingot", up);
        }
        return out;
    }

    @Test
    void everyGearRecipeUsesThePowerRuleMetals() {
        Content c = Mat036.content();
        Params base = Mat036.json("base_0351.json");
        List<String> commons = base.strings("commons");
        Params baseRecipes = base.sub("recipes");
        List<String> bad = new ArrayList<>();
        int checked = 0, mixed = 0;
        for (RecipeDef r : c.recipes().values()) {
            ItemDef d = c.item(r.result());
            if (d == null || !d.isGear()) continue;
            assertEquals(MineNames.STATION_BLACKSMITH, r.station(), r.id());
            Params old = baseRecipes.sub(r.id());
            assertTrue(!old.isEmpty(), r.id() + " 가 0.3.5.1 레시피에 없다");
            int sum = 0;
            for (String k : old.keys()) if (commons.contains(k)) sum += old.integer(k, 0);
            int n = Math.max(2, (int) (sum * 0.20 + 0.5));
            Map<String, Integer> want = expected(d.tier(), d.rarity().id(), d.sources().contains("boss"), n);
            Map<String, Integer> got = new LinkedHashMap<>();
            for (var e : r.materials().entrySet()) {
                ItemDef md = c.item(e.getKey());
                assertNotNull(md, e.getKey());
                if (md.mineKind() == MineKind.INGOT) got.put(e.getKey(), e.getValue());
                assertTrue(md.mineKind() != MineKind.ORE && md.mineKind() != MineKind.GEM, r.id() + ": 장비 레시피에 광석·보석 " + e.getKey());
            }
            if (!got.equals(want) || !List.copyOf(got.keySet()).equals(List.copyOf(want.keySet()))) bad.add(r.id() + " " + got + " ≠ " + want);
            if (got.size() == 2) mixed++;
            assertTrue(got.size() <= 2, r.id() + " 금속은 둘까지");
            checked++;
        }
        assertEquals(List.of(), bad, "힘 규칙과 다른 주괴");
        Params derived = Mat036.json("materials.json").sub("derived");
        assertEquals(derived.integer("recipes_changed", -1), checked, "장비 레시피 수");
        assertEquals(derived.integer("mixed_recipes", -1), mixed, "두 금속 섞은 레시피 수");
    }

    @Test
    void examplesFromTheContractTable() {
        assertEquals(Map.of("copper_ingot", 10), expected(1, "common", false, 10));
        assertEquals(Map.of("copper_ingot", 5, "iron_ingot", 5), expected(1, "rare", true, 10));
        assertEquals(Map.of("copper_ingot", 4, "iron_ingot", 6), expected(2, "uncommon", false, 10));
        assertEquals(Map.of("iron_ingot", 10), expected(3, "rare", false, 10));
        assertEquals(Map.of("silver_ingot", 5, "gold_ingot", 5), expected(5, "epic", false, 10));
        assertEquals(Map.of("mithril_ingot", 10), expected(8, "epic", false, 10));
        assertEquals(Map.of("orichalcum_ingot", 10), expected(10, "legendary", false, 10));
    }
}
