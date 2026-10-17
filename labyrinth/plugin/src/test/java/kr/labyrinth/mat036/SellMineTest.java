package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineKind;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.RecipeDef;
import kr.labyrinth.items.crafting.RecipeCheck;
import kr.labyrinth.items.sell.SellPrices;
import kr.labyrinth.items.sell.SellPrices.Block;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/**
 * 광산 재료 판매가 (config sell.mine · 계약 §3.6, 0.3.7 — 주인 "광질로도 충분히 돈을 벌 수 있으면 좋을듯"): 등급 1~6 목록 · 표 값 ·
 * 녹여 팔면 늘 1 G 손해 · 사서 되팔 길 없음 · 도구는 못 팜 · 0.3.6 config 꼴 읽기.
 */
class SellMineTest {

    static SellPrices prices() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        SellPrices.Config cfg = SellPrices.Config.of(y.get("sell"));
        return new SellPrices(cfg, SellPrices.buyPrices(Mat036.content().npcs().values()), List.of());
    }

    @Test
    void jarConfigHasTheContractValues() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertNotNull(y.getConfigurationSection("sell.mine"));
        assertEquals(SellPrices.Mine.DEFAULT, SellPrices.Config.of(y.get("sell")).mine());
        assertEquals(new SellPrices.Mine(List.of(3, 4, 5, 15, 36, 46), List.of(7, 11, 17, 41, 89, 116), List.of(25, 35, 45, 130, 400, 700)),
                SellPrices.Mine.DEFAULT);
        assertEquals(SellPrices.Mine.DEFAULT, SellPrices.Mine.from(null), "sell.mine 이 없는 옛 config 는 기본값");
        // 계약 materials.json sell.config 와 같다
        Params cfg = Mat036.json("materials.json").sub("sell").sub("config").sub("sell").sub("mine");
        for (MineKind k : MineKind.values()) {
            List<Integer> want = new java.util.ArrayList<>();
            for (Object o : cfg.list(k.id())) want.add(((Number) o).intValue());
            assertEquals(want, SellPrices.Mine.DEFAULT.row(k), k.id());
        }
    }

    @Test
    void ownerConfigFrom036IsReadAsNewDefaults() throws Exception {
        // 0.3.6·0.3.6.1 로 깐 서버의 config.yml 그대로 → 새 기본값
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("sell:\n  mine: {ore: 1, ingot: 3, gem: 6, rank_bonus: 0.35}\n");
        assertEquals(SellPrices.Mine.DEFAULT, SellPrices.Config.of(y.get("sell")).mine());
        assertEquals(new SellPrices.Mine.Legacy(1, 3, 6, 0.35), SellPrices.Mine.LEGACY_0361);
        // 주인이 고친 옛 꼴은 옛 식 그대로 펼침: 반올림(2 × (1 + 0.35 × (등급 − 1))) = 2·3·3·4·5·6
        y.loadFromString("sell:\n  mine: {ore: 2, ingot: 3, gem: 6, rank_bonus: 0.35}\n");
        SellPrices.Mine m = SellPrices.Config.of(y.get("sell")).mine();
        assertEquals(List.of(2, 3, 3, 4, 5, 6), m.ore());
        assertEquals(List.of(3, 4, 5, 6, 7, 8), m.ingot(), "0.3.6.1 주괴 값 그대로");
        assertEquals(List.of(6, 8, 10, 12, 14, 17), m.gem(), "0.3.6.1 보석 값 그대로");
        // 목록이 짧거나 틀리면 기본값 · 음수는 0 (팔지 않음)
        y.loadFromString("sell:\n  mine:\n    ore: [9, -1, x]\n");
        SellPrices.Mine s = SellPrices.Config.of(y.get("sell")).mine();
        assertEquals(List.of(9, 0, 5, 15, 36, 46), s.ore());
        assertEquals(SellPrices.Mine.DEFAULT.gem(), s.gem());
        assertEquals(0, s.value(MineKind.ORE, 2));
        assertEquals(46, s.value(MineKind.ORE, 99), "범위 밖 등급 = 끝 값");
    }

    @Test
    void contractValuesAndNoSmeltProfit() {
        Content c = Mat036.content();
        SellPrices.Mine m = SellPrices.Mine.DEFAULT;
        int[][] want = {{3, 7, 25}, {4, 11, 35}, {5, 17, 45}, {15, 41, 130}, {36, 89, 400}, {46, 116, 700}};
        Map<Integer, int[]> smelt = new java.util.HashMap<>();
        for (int lv = 1; lv <= 6; lv++) {
            assertEquals(want[lv - 1][0], m.value(MineKind.ORE, lv), "광석 " + lv);
            assertEquals(want[lv - 1][1], m.value(MineKind.INGOT, lv), "주괴 " + lv);
            assertEquals(want[lv - 1][2], m.value(MineKind.GEM, lv), "보석 " + lv);
            RecipeDef r = c.recipes().get(Mat036.METALS.get(lv - 1) + "_ingot");
            long gold = RecipeCheck.goldCost(r, 0);
            // 주괴 = 광석 2 + 제련 골드 − 1 → 녹여 팔면 늘 1 G 손해
            assertEquals(2L * m.value(MineKind.ORE, lv) + gold - 1, m.value(MineKind.INGOT, lv), "등급 " + lv + " 주괴");
            if (lv > 1) {
                for (MineKind k : MineKind.values()) assertTrue(m.value(k, lv) > m.value(k, lv - 1), k + " 등급 " + lv + " 이 더 비쌈");
            }
            smelt.put(lv, new int[] {2, (int) gold});
        }
        assertTrue(m.smeltWarnings(smelt).isEmpty(), "기본값은 녹여 팔기 경고 없음");
        SellPrices.Mine bad = new SellPrices.Mine(m.ore(), List.of(8, 11, 17, 41, 89, 116), m.gem());
        List<String> w = bad.smeltWarnings(smelt);
        assertEquals(1, w.size(), "구리 주괴 8 G = 광석 2 × 3 + 제련 2 → 이득 0 이상이면 경고");
        assertTrue(w.get(0).contains("등급 1") && w.get(0).contains("7 G 이하"), w.get(0));
    }

    @Test
    void noBuySellLoop() {
        // 상인이 광석·주괴·보석을 팔지 않는다 — 사서 되팔아 골드를 불릴 길이 없음 (상인이 파는 물건은 언제나 산 값보다 싸게 삼)
        Content c = Mat036.content();
        SellPrices p = prices();
        for (ItemDef d : c.items().values()) {
            if (!d.isMineMaterial()) continue;
            assertEquals(0, p.buyPrice(d.id()), d.id() + " 를 상인이 팖");
        }
        for (var n : c.npcs().values()) {
            if (n.shop() == null) continue;
            for (var e : n.shop()) {
                ItemDef d = c.item(e.item());
                if (d == null || e.price() <= 0) continue;
                assertTrue(p.quote(d, 0).unit() < e.price(), n.id() + " " + d.id() + ": 판 값 < 산 값 " + e.price());
            }
        }
    }

    @Test
    void tableLoreShowsTheNewFloor() {
        String all = String.join("\n", prices().tableLore());
        assertTrue(all.contains("광석 <white>3 G") && all.contains("주괴 <white>7 G") && all.contains("보석 <white>25 G"), all);
    }

    @Test
    void pricesFollowTheTable() {
        Content c = Mat036.content();
        SellPrices p = prices();
        Params table = Mat036.json("materials.json").sub("sell").sub("table");
        int n = 0;
        for (ItemDef d : c.items().values()) {
            if (!d.isMineMaterial()) continue;
            int want = table.sub(String.valueOf(d.mineLevel())).integer(d.mineKind().id(), -1);
            assertEquals(want, p.quote(d, 0).unit(), d.id());
            n++;
        }
        assertEquals(18, n, "광석 6 · 주괴 6 · 보석 6");
    }

    @Test
    void smeltingNeverBeatsSellingOre() {
        Content c = Mat036.content();
        SellPrices p = prices();
        for (String m : Mat036.METALS) {
            RecipeDef r = c.recipes().get(m + "_ingot");
            long ore = p.quote(c.item(m + "_ore"), 0).unit();
            long ingot = p.quote(c.item(m + "_ingot"), 0).unit();
            // 제련소 레시피는 제작 할인이 없다 (LabCraftingService.goldCost) — 할인 0 의 골드
            long gold = RecipeCheck.goldCost(r, 0);
            assertTrue(ingot < 2 * ore + gold, m + ": 주괴 " + ingot + " < 광석 2 (" + 2 * ore + ") + 골드 " + gold);
            assertEquals(MineKind.INGOT, c.item(m + "_ingot").mineKind());
        }
    }

    @Test
    void toolsCannotBeSold() {
        Content c = Mat036.content();
        SellPrices p = prices();
        int tools = 0;
        for (ItemDef d : c.items().values()) {
            if (!d.isTool()) continue;
            tools++;
            assertFalse(p.quote(d, 0).sellable(), d.id());
            assertEquals(Block.TOOL, p.quote(d, 0).block(), d.id());
        }
        assertEquals(6, tools);
        assertEquals("도구는 팔 수 없습니다.", Block.TOOL.message());
    }
}
