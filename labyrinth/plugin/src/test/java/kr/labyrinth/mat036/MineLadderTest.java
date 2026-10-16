package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.ItemType;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.content.ToolSpec;
import kr.labyrinth.mine.MineNames;
import org.junit.jupiter.api.Test;

/** 제련소 레시피 17 (제련 6 · 새기기 6 · 곡괭이 5) 와 곡괭이 6단 사다리 (계약 §3.5 · §2.6). 레벨 조건이 어디에도 없다. */
class MineLadderTest {

    static List<RecipeDef> smelter(Content c) {
        List<RecipeDef> out = new ArrayList<>();
        for (RecipeDef r : c.recipes().values()) if (MineNames.STATION_SMELTER.equals(r.station())) out.add(r);
        return out;
    }

    @Test
    void seventeenSmelterRecipesMatchTheContract() {
        Content c = Mat036.content();
        List<RecipeDef> sm = smelter(c);
        assertEquals(17, sm.size());
        Params mat = Mat036.json("materials.json");
        List<Params> all = new ArrayList<>(mat.maps("smelting"));
        all.addAll(mat.maps("carving"));
        all.addAll(mat.maps("pickaxe_recipes"));
        assertEquals(17, all.size());
        for (Params p : all) {
            RecipeDef r = c.recipes().get(p.str("id"));
            assertNotNull(r, p.str("id"));
            assertEquals(p.str("result"), r.result(), r.id());
            assertEquals(p.str("category"), r.category(), r.id());
            assertEquals(MineNames.STATION_SMELTER, r.station(), r.id());
            assertEquals(p.integer("gold", -1), r.gold(), r.id());
            assertEquals(p.integer("amount", 1), Math.max(1, r.amount()), r.id());
            Params m = p.sub("materials");
            assertEquals(m.keys().size(), r.materials().size(), r.id());
            for (String k : m.keys()) assertEquals(m.integer(k, -1), r.materials().get(k), r.id() + " " + k);
            assertTrue(r.levelReq() <= 1, r.id() + " 레벨 조건 없음");
        }
        // 제련: <금속>_ore ×2 → <금속>_ingot
        for (String metal : Mat036.METALS) {
            RecipeDef r = c.recipes().get(metal + "_ingot");
            assertEquals(Map.of(metal + "_ore", 2), r.materials(), metal);
        }
        // 새기기: 보석마다 1, 강화석 2개
        long carve = sm.stream().filter(r -> r.amount() == 2).count();
        assertEquals(6, carve);
        for (String g : Mat036.GEMS) assertTrue(sm.stream().anyMatch(r -> r.amount() == 2 && r.materials().containsKey(g)), g);
    }

    @Test
    void sixPickaxesFormALadder() {
        Content c = Mat036.content();
        Params mine = Mat036.json("mine.json").sub("pickaxes");
        ItemDef prev = null;
        for (int t = 1; t <= 6; t++) {
            String id = Mat036.METALS.get(t - 1) + "_pickaxe";
            ItemDef d = c.item(id);
            assertNotNull(d, id);
            assertEquals(ItemType.TOOL, d.type(), id);
            assertTrue(d.isTool(), id);
            ToolSpec s = d.tool();
            assertEquals(t, s.tier(), id);
            assertTrue(d.levelReq() <= 1 && !d.raw().has("level_req"), id + " 레벨 조건 없음");
            assertTrue(d.stats().isEmpty(), id + " 능력치 없음");
            Params pm = mine.sub(id);
            assertEquals(pm.integer("tier", -1), s.tier(), id);
            assertEquals(pm.dbl("bonus", -1), s.bonus(), 1e-9, id);
            for (int o = 1; o <= t; o++) {
                assertEquals(pm.sub("speed").dbl(String.valueOf(o), -1), s.speedFor(o), 1e-9, id + " 등급 " + o);
                if (prev != null && o <= prev.tool().tier()) assertTrue(s.speedFor(o) >= prev.tool().speedFor(o), id + " 은 앞 곡괭이보다 느리지 않다");
            }
            assertEquals(0, s.speedFor(t + 1), 1e-9, id + " 은 더 단단한 광석을 못 캔다");
            if (prev != null) {
                RecipeDef r = c.recipes().get(id);
                assertNotNull(r, id + " 벼리기");
                assertEquals(MineNames.CATEGORY_TOOL, r.category());
                assertEquals(1, r.materials().get(prev.id()), id + " 는 앞 곡괭이를 재료로 먹는다");
                assertTrue(r.materials().containsKey(Mat036.METALS.get(t - 2) + "_ingot"), id + " 앞 금속 주괴");
                assertTrue(r.materials().containsKey(Mat036.GEMS.get(t - 2)), id + " 앞 등급 보석");
            } else {
                assertTrue(d.sources().contains("starter"), "구리 곡괭이는 시작 꾸러미");
            }
            prev = d;
        }
    }
}
