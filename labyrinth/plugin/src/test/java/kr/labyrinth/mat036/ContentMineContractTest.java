package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MineKind;
import kr.labyrinth.content.Params;
import org.junit.jupiter.api.Test;

/** items.yml 의 mine_level · mine_kind · tool 이 계약 mine.json · materials.json 과 같다 (Q3 생성기가 채움, ContentValidator 가 mine.yml 과 맞댐). */
class ContentMineContractTest {

    @Test
    void oresIngotsGemsMatchMineJson() {
        Content c = Mat036.content();
        Params ores = Mat036.json("mine.json").sub("ores");
        Params gems = Mat036.json("mine.json").sub("gems");
        Params items = Mat036.json("materials.json").sub("items");
        for (String id : ores.keys()) {
            ItemDef o = c.item(id);
            assertNotNull(o, id);
            assertEquals(MineKind.ORE, o.mineKind(), id);
            assertEquals(ores.sub(id).integer("tier", -1), o.mineLevel(), id);
            String ing = ores.sub(id).str("ingot");
            assertEquals(MineKind.INGOT, c.item(ing).mineKind(), ing);
            assertEquals(o.mineLevel(), c.item(ing).mineLevel(), ing);
        }
        for (String id : gems.keys()) {
            ItemDef g = c.item(id);
            assertNotNull(g, id);
            assertEquals(MineKind.GEM, g.mineKind(), id);
            assertEquals(gems.sub(id).integer("tier", -1), g.mineLevel(), id);
        }
        for (String id : items.keys()) {
            Params p = items.sub(id);
            ItemDef d = c.item(id);
            assertNotNull(d, id);
            assertEquals(p.str("type"), d.type().name().toLowerCase(java.util.Locale.ROOT), id);
            if (p.has("mine_level")) assertEquals(p.integer("mine_level", -1), d.mineLevel(), id);
            if (!p.has("mine_level")) assertNull(d.mineKind(), id + " 광산 재료가 아님");
            if ("tool".equals(p.str("type"))) {
                Params t = p.sub("tool");
                assertTrue(d.isTool(), id);
                assertEquals(t.integer("tier", -1), d.tool().tier(), id);
                assertEquals(t.dbl("bonus", -1), d.tool().bonus(), 1e-9, id);
                assertEquals(t.sub("speed").keys().size(), d.tool().speed().size(), id);
                assertTrue(!d.raw().has("level_req"), id + " 레벨 조건 없음");
            }
        }
    }
}
