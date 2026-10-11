package kr.souls.combat;

import org.bukkit.util.Vector;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** M1 P1-0 계약: 한 대 (combat/Hit) 는 builder 로만 만들고 바뀌지 않는다. */
class HitTest {
    @Test
    void defaults() {
        Hit h = Hit.builder().build();
        assertEquals("-", h.moveId());
        assertEquals("-", h.cls());
        assertEquals(0, h.raw());
        assertEquals(0, h.poise());
        assertSame(Hit.Type.STANDARD, h.type());
        assertFalse(h.counter());
        assertEquals(1.0, h.crit());
        assertNull(h.dir());
        assertNull(h.attacker());
    }

    @Test
    void fieldsAndCopy() {
        Hit h = Hit.builder().moveId("light1").cls("straight_sword").raw(72).poise(12).type(Hit.Type.SLASH).counter(true).crit(1.1)
                .dir(new Vector(3, 5, 4)).build();
        assertEquals("light1", h.moveId());
        assertEquals("straight_sword", h.cls());
        assertEquals(72, h.raw());
        assertEquals(12, h.poise());
        assertSame(Hit.Type.SLASH, h.type());
        assertTrue(h.counter());
        assertEquals(1.1, h.crit());
        // 방향은 수평으로 눕혀 길이 1
        assertEquals(0, h.dir().getY(), 1e-12);
        assertEquals(1, h.dir().length(), 1e-12);
        assertEquals(0.6, h.dir().getX(), 1e-12);
        // 돌려준 방향을 바꿔도 한 대는 그대로
        h.dir().multiply(10);
        assertEquals(1, h.dir().length(), 1e-12);
        Hit h2 = h.toBuilder().raw(80).build();
        assertEquals(80, h2.raw());
        assertEquals(72, h.raw());
        assertEquals("light1", h2.moveId());
        assertSame(Hit.Type.SLASH, h2.type());
        assertTrue(h2.counter());
    }

    @Test
    void verticalOrZeroDirIsNull() {
        assertNull(Hit.builder().dir(new Vector(0, 1, 0)).build().dir());
        assertNull(Hit.builder().dir(new Vector()).build().dir());
    }

    @Test
    void rejectsBadNumbers() {
        assertThrows(IllegalArgumentException.class, () -> Hit.builder().raw(-1).build());
        assertThrows(IllegalArgumentException.class, () -> Hit.builder().raw(Double.NaN).build());
        assertThrows(IllegalArgumentException.class, () -> Hit.builder().raw(Double.POSITIVE_INFINITY).build());
        assertThrows(IllegalArgumentException.class, () -> Hit.builder().poise(-0.5).build());
        assertThrows(IllegalArgumentException.class, () -> Hit.builder().crit(0).build());
    }

    @Test
    void typeParse() {
        assertSame(Hit.Type.STRIKE, Hit.Type.parse(" strike ", Hit.Type.STANDARD));
        assertSame(Hit.Type.STANDARD, Hit.Type.parse("nonsense", Hit.Type.STANDARD));
        assertSame(Hit.Type.STANDARD, Hit.Type.parse(null, Hit.Type.STANDARD));
        assertTrue(Hit.Type.THRUST.physical());
        assertFalse(Hit.Type.FIRE.physical());
        assertFalse(Hit.Type.MAGIC.physical());
    }
}
