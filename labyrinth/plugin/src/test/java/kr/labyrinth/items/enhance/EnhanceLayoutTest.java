package kr.labyrinth.items.enhance;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** 강화 창 비용 줄 배치 — 아이콘이 배경 소켓(glyphs.yml menus.enhance.slots) 위에 오는가. */
class EnhanceLayoutTest {

    static final Path GLYPHS = Path.of("src/main/resources/content/glyphs.yml");

    @Test
    void withoutBackgroundItIsLeftToRight() {
        for (Map<String, Object> slots : java.util.Arrays.<Map<String, Object>>asList(null, Map.of("gold", 29, "stone", 31, "protection", 33))) {
            assertEquals(EnhanceLayout.PLAIN, EnhanceLayout.of(slots, false));
        }
        EnhanceLayout p = EnhanceLayout.PLAIN;
        assertEquals(28, p.gold());
        assertEquals(29, p.stone());
        assertArrayEquals(new int[] {30, 31, 32}, p.materials());
        assertEquals(33, p.protection());
        assertTrue(p.valid());
    }

    @Test
    void bundledBackgroundSocketsCarryGoldStoneAndScroll() {
        Map<String, Object> slots = EnhanceLayout.readSlots(GLYPHS);
        assertNotNull(slots, "glyphs.yml menus.enhance.slots");
        EnhanceLayout l = EnhanceLayout.of(slots, true);
        assertTrue(l.valid(), l.toString());
        assertEquals(slots.get("gold"), l.gold(), "골드 아이콘이 골드 소켓 위");
        assertEquals(slots.get("stone"), l.stone(), "강화석 아이콘이 강화석 소켓 위");
        assertEquals(slots.get("protection"), l.protection(), "주문서 아이콘이 주문서 소켓 위");
        assertEquals(EnhanceLayout.MATERIAL_SLOTS, l.materials().length);
        if (slots.get("materials") instanceof List<?> mats) {
            for (int k = 0; k < mats.size() && k < l.materials().length; k++) assertEquals(mats.get(k), l.materials()[k], "재료 소켓 " + k);
        }
        System.out.println("ENHANCE 강화 창 비용 줄 (번들 배경): " + l);
    }

    @Test
    void oldBackgroundPutsMaterialsNextToTheStone() {
        EnhanceLayout l = EnhanceLayout.of(Map.of("gold", 29, "stone", 31, "protection", 33), true);
        assertEquals(EnhanceLayout.SOCKETS_29_31_33, l);
        assertArrayEquals(new int[] {30, 32, 28}, l.materials(), "새김선 위 30 · 32, 그다음 왼쪽 28");
        assertEquals(EnhanceLayout.SOCKETS_29_31_33, EnhanceLayout.of(null, true), "배경은 있는데 glyphs.yml 항목이 없음 = 예전 배경");
    }

    @Test
    void newBackgroundWithMaterialSocketsIsUsedAsIs() {
        EnhanceLayout l = EnhanceLayout.of(Map.of("gold", 28, "stone", 29, "materials", List.of(30, 31, 32), "protection", 33), true);
        assertEquals(EnhanceLayout.PLAIN, l, "WP6 가 소켓 28 · 29 · 30~32 · 33 을 그리면 그대로");
        EnhanceLayout two = EnhanceLayout.of(Map.of("gold", 28, "stone", 29, "materials", List.of(30, 31), "protection", 33), true);
        assertArrayEquals(new int[] {30, 31}, two.materials());
    }

    @Test
    void badSlotsFallBackToOldSockets() {
        List<Map<String, Object>> bad = List.of(
                Map.of("gold", 28, "stone", 29, "materials", List.of(30, 15, 32), "protection", 33), // [강화] 칸과 겹침
                Map.of("gold", 28, "stone", 29, "materials", List.of(30, 30), "protection", 33),     // 재료끼리 겹침
                Map.of("gold", 28, "stone", 28, "protection", 33),                                  // 골드 = 강화석
                Map.of("gold", 99, "stone", 29, "protection", 33),                                  // 창 밖
                Map.of("stone", 31, "protection", 33),                                              // 골드 없음
                Map.of("gold", "스물아홉", "stone", 31, "protection", 33));
        for (Map<String, Object> m : bad) assertEquals(EnhanceLayout.SOCKETS_29_31_33, EnhanceLayout.of(m, true), m.toString());
        assertTrue(EnhanceLayout.SOCKETS_29_31_33.valid());
        assertNull(EnhanceLayout.readSlots(Path.of("no/such/glyphs.yml")));
    }
}
