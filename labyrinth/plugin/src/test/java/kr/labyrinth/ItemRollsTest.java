package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.EquipRules;
import kr.labyrinth.items.ItemRolls;
import kr.labyrinth.items.ItemTooltip;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 장비 스탯 굴림·인코딩·품질·툴팁·착용 조건. */
class ItemRollsTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void sameSeedSameRolls() {
        ItemDef def = content.item("ember_greatsword");
        assertNotNull(def);
        assertEquals(ItemRolls.roll(def, 42L), ItemRolls.roll(def, 42L));
    }

    @Test
    void everyGearRollStaysInRangeAndIsRounded() {
        int checked = 0;
        for (ItemDef def : content.items().values()) {
            if (!def.isGear()) continue;
            for (long seed = 0; seed < 40; seed++) {
                Map<String, Double> r = ItemRolls.roll(def, seed * 7919L + def.id().hashCode());
                assertEquals(def.stats().size(), r.size(), def.id());
                for (Map.Entry<String, Range> e : def.stats().entrySet()) {
                    double v = r.get(e.getKey());
                    double lo = ItemRolls.round(e.getKey(), e.getValue().min());
                    double hi = ItemRolls.round(e.getKey(), e.getValue().max());
                    assertTrue(v >= Math.min(lo, hi) - 1e-9 && v <= Math.max(lo, hi) + 1e-9,
                            def.id() + "." + e.getKey() + "=" + v + " not in " + e.getValue());
                    if (ItemRolls.INT_KEYS.contains(e.getKey())) assertEquals(Math.rint(v), v, 1e-9, def.id() + "." + e.getKey());
                }
                checked++;
            }
        }
        assertTrue(checked > 1000);
    }

    @Test
    void rollsCoverTheRange() {
        ItemDef def = content.item("ember_greatsword");
        Range dmg = def.stats().get("damage");
        double min = Double.MAX_VALUE, max = -Double.MAX_VALUE;
        for (long s = 0; s < 2000; s++) {
            double v = ItemRolls.roll(def, s).get("damage");
            min = Math.min(min, v);
            max = Math.max(max, v);
        }
        assertEquals(Math.round(dmg.min()), min, 1e-9);
        assertEquals(Math.round(dmg.max()), max, 1e-9);
    }

    @Test
    void encodeDecodeRoundTrip() {
        ItemDef def = content.item("ember_greatsword");
        Map<String, Double> r = ItemRolls.roll(def, 123L);
        Map<String, Double> back = ItemRolls.decode(ItemRolls.encode(r));
        assertEquals(r.keySet(), back.keySet());
        r.forEach((k, v) -> assertEquals(v, back.get(k), 1e-9, k));
        assertTrue(ItemRolls.decode("garbage;;x=;=3;damage=5").containsKey("damage"));
        assertTrue(ItemRolls.decode(null).isEmpty());
    }

    @Test
    void qualityBounds() {
        ItemDef def = content.item("ember_greatsword");
        Map<String, Double> lo = new java.util.LinkedHashMap<>();
        Map<String, Double> hi = new java.util.LinkedHashMap<>();
        def.stats().forEach((k, r) -> {
            lo.put(k, r.min());
            hi.put(k, r.max());
        });
        assertEquals(0.0, ItemRolls.quality(def, lo), 1e-9);
        assertEquals(1.0, ItemRolls.quality(def, hi), 1e-9);
        double q = ItemRolls.quality(def, ItemRolls.midpoint(def));
        assertTrue(q > 0.3 && q < 0.7, "midpoint quality " + q);
    }

    @Test
    void tooltipHasRequirementsStatsAndSkills() {
        ItemDef def = content.item("ember_greatsword");
        List<String> lines = ItemTooltip.lines(content, def, ItemRolls.roll(def, 1L));
        String all = String.join("\n", lines);
        assertTrue(all.contains("요구 레벨"), all);
        assertTrue(all.contains("피해"), all);
        assertTrue(all.contains("잿불 검기"), all);
        assertTrue(all.contains("굴림 품질"), all);
        assertTrue(all.contains("아우라"), all);
        // 미리보기(굴림 없음)는 범위
        assertFalse(String.join("\n", ItemTooltip.lines(content, def, null)).contains("굴림 품질"));
    }

    @Test
    void equipRules() {
        ItemDef def = content.item("ember_greatsword");
        assertEquals(EquipRules.Problem.LEVEL, EquipRules.check(def, def.levelReq() - 1, "berserker"));
        // 직업 제한 없음: 광전사 추천 대검도 사제·직업 없음이 그대로 쓴다
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(def, 50, "priest"));
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(def, 50, null));
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(def, def.levelReq(), "berserker"));
        ItemDef mat = content.item("moss_fiber");
        assertEquals(EquipRules.Problem.NONE, EquipRules.check(mat, 1, null));
    }
}
