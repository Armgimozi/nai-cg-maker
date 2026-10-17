package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.homes.HomesLayout;
import kr.labyrinth.homes.PlotGeom;
import org.bukkit.Material;
import org.junit.jupiter.api.Test;

/** 되돌린 칸 = 바닥 틀 (구역 계획기 plot_pad 와 같음): 잔디 1 · 흙 3 · 돌 (−4..−8) · 위 공기. 높이 창 안만. */
class PlotResetPlanTest {

    @Test
    void templateLayers() {
        int f = 68;
        assertEquals("grass_block", PlotResetPlan.template(f, f));
        assertEquals("dirt", PlotResetPlan.template(f - 1, f));
        assertEquals("dirt", PlotResetPlan.template(f - 3, f));
        assertEquals("stone", PlotResetPlan.template(f - 4, f));
        assertEquals("stone", PlotResetPlan.template(f - 6, f), "창 맨 아래 (바닥 −6)");
        assertEquals("stone", PlotResetPlan.template(f - 8, f));
        assertEquals("air", PlotResetPlan.template(f + 1, f));
        assertEquals("air", PlotResetPlan.template(f + 24, f));
    }

    @Test
    void templateBlocksAreRealMaterials() {
        for (int y = 60; y <= 92; y++) {
            String id = PlotResetPlan.template(y, 68);
            Material m = Material.matchMaterial(id);
            assertTrue(m != null, id); // isBlock() 은 서버가 있어야 함
        }
    }

    @Test
    void wholeWindowIsTemplateAfterReset() {
        // 모든 집터: 창 안 칸을 틀로 되돌린 뒤 isTemplate 이 참 (되돌리기 = 같은 것을 두 번 해도 같음)
        for (PlotGeom p : HomesLayout.geoms(6, 24)) {
            long cells = 0;
            for (int y = p.yMin(); y <= p.yMax(); y++) {
                String t = PlotResetPlan.template(y, p.floorY());
                assertTrue(PlotResetPlan.isTemplate("minecraft:" + t, y, p.floorY()));
                cells += (long) p.width() * p.depth();
            }
            assertEquals(14 * 14 * 31, cells, p.label());
            assertEquals(cells, PlotResetPlan.volume(p.x0(), p.z0(), p.x1(), p.z1(), p.yMin(), p.yMax()));
        }
    }

    @Test
    void differencesAreTouched() {
        assertFalse(PlotResetPlan.isTemplate("oak_planks", 69, 68), "바닥 위 판자");
        assertFalse(PlotResetPlan.isTemplate("dirt", 68, 68), "잔디가 흙이 됨");
        assertFalse(PlotResetPlan.isTemplate("farmland", 68, 68));
        assertFalse(PlotResetPlan.isTemplate("air", 66, 68), "판 구덩이");
        assertFalse(PlotResetPlan.isTemplate("cobblestone", 63, 68));
        assertTrue(PlotResetPlan.isTemplate("CAVE_AIR", 80, 68));
        assertTrue(PlotResetPlan.isTemplate("minecraft:stone", 63, 68));
    }

    @Test
    void propsParse() {
        var p = PlotResetPlan.props("minecraft:oak_slab[type=double,waterlogged=false]");
        assertEquals("double", p.get("type"));
        assertEquals("false", p.get("waterlogged"));
        assertTrue(PlotResetPlan.props("stone").isEmpty());
        assertTrue(PlotResetPlan.props(null).isEmpty());
    }
}
