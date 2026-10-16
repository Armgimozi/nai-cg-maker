package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.List;
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

/** 광산 재료 판매가 (config sell.mine · 계약 §3.6): 표 값 · 녹여 팔면 언제나 손해 · 도구는 못 팜. */
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
        assertEquals(new SellPrices.Mine(1, 3, 6, 0.35), SellPrices.Mine.DEFAULT);
        assertEquals(SellPrices.Mine.DEFAULT, SellPrices.Mine.from(null), "sell.mine 이 없는 옛 config 는 기본값");
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
