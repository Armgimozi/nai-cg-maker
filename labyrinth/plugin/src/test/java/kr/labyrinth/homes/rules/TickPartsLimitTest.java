package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;
import kr.labyrinth.homes.HomesConfig;
import org.junit.jupiter.api.Test;

/** 틱 부품 한도 (plan §9): 깔때기·공급기·제작기·피스톤·끈끈이 피스톤·관측기 합 16, 깔때기 8. 상자는 세지 않음. */
class TickPartsLimitTest {

    private static final int TOTAL = HomesConfig.DEFAULT.tickParts().total(), HOPPERS = HomesConfig.DEFAULT.tickParts().hoppers();

    @Test
    void defaults() {
        assertEquals(16, TOTAL);
        assertEquals(8, HOPPERS);
    }

    @Test
    void partsByName() {
        assertEquals(Limits.Part.HOPPER, Limits.part("minecraft:hopper"));
        assertEquals(Limits.Part.DROPPER, Limits.part("DROPPER"));
        assertEquals(Limits.Part.CRAFTER, Limits.part("crafter"));
        assertEquals(Limits.Part.PISTON, Limits.part("piston"));
        assertEquals(Limits.Part.STICKY_PISTON, Limits.part("sticky_piston"));
        assertEquals(Limits.Part.OBSERVER, Limits.part("observer"));
        assertNull(Limits.part("chest"), "상자는 틱을 안 씀");
        assertNull(Limits.part("piston_head"));
        assertNull(Limits.part("barrel"));
    }

    @Test
    void totalCap() {
        Map<Limits.Part, Integer> c = Limits.emptyCounts();
        c.put(Limits.Part.PISTON, 10);
        c.put(Limits.Part.OBSERVER, 5);
        assertNull(Limits.tickPart(c, Limits.Part.DROPPER, TOTAL, HOPPERS), "15 → 16 됨");
        c.put(Limits.Part.DROPPER, 1);
        String msg = Limits.tickPart(c, Limits.Part.PISTON, TOTAL, HOPPERS);
        assertNotNull(msg, "16 → 17 안 됨");
        assertTrue(msg.contains("16"));
        assertFalse(Limits.overTickParts(c, TOTAL, HOPPERS));
        c.put(Limits.Part.CRAFTER, 1);
        assertTrue(Limits.overTickParts(c, TOTAL, HOPPERS));
    }

    @Test
    void hopperCap() {
        Map<Limits.Part, Integer> c = Limits.emptyCounts();
        c.put(Limits.Part.HOPPER, 7);
        assertNull(Limits.tickPart(c, Limits.Part.HOPPER, TOTAL, HOPPERS));
        c.put(Limits.Part.HOPPER, 8);
        String msg = Limits.tickPart(c, Limits.Part.HOPPER, TOTAL, HOPPERS);
        assertNotNull(msg, "깔때기 9번째 안 됨");
        assertTrue(msg.contains("깔때기"));
        assertNull(Limits.tickPart(c, Limits.Part.OBSERVER, TOTAL, HOPPERS), "깔때기 8 + 관측기 1 = 9 ≤ 16");
        assertNull(Limits.tickPart(c, null, TOTAL, HOPPERS), "틱 부품이 아님");
    }
}
