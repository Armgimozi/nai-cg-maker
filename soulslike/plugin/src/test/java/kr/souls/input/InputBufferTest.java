package kr.souls.input;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** M1 P1a (3.6, R35): 입력 기억의 정확한 경계 (가짜 시계). 회복 − 6 은 받고 − 7 은 버린다. 받은 지 6틱이 넘으면 버린다. */
class InputBufferTest {
    private static final long END = 1000; // 지금 동작이 끝나는 틱

    @Test
    void acceptedFromRecoveryMinusSix() {
        InputBuffer b = new InputBuffer();
        assertFalse(b.offer(InputBuffer.Kind.LIGHT, END - 7, END, 6, null), "회복 − 7 은 이르다");
        assertNull(b.peek());
        assertTrue(b.offer(InputBuffer.Kind.LIGHT, END - 6, END, 6, null), "회복 − 6 은 받는다");
        InputBuffer.Entry e = b.take(END, 6);
        assertNotNull(e, "끝나는 틱에 꺼낸다 (받은 지 6틱)");
        assertEquals(InputBuffer.Kind.LIGHT, e.kind());
        assertEquals(END - 6, e.at());
        assertNull(b.take(END, 6), "꺼내면 비운다");
    }

    @Test
    void lastInputWins() {
        InputBuffer b = new InputBuffer();
        assertTrue(b.offer(InputBuffer.Kind.LIGHT, END - 5, END, 6, null));
        assertTrue(b.offer(InputBuffer.Kind.HEAVY, END - 2, END, 6, null));
        assertEquals(InputBuffer.Kind.HEAVY, b.take(END, 6).kind(), "나중 것이 앞의 것을 바꾼다");
    }

    @Test
    void expiresAfterBuffer() {
        InputBuffer b = new InputBuffer();
        assertTrue(b.offer(InputBuffer.Kind.LIGHT, END - 6, END, 6, null));
        assertNull(b.take(END + 1, 6), "받은 지 7틱: 버린다");
        b.offer(InputBuffer.Kind.RUNNING, END, END, 6, null);
        assertNotNull(b.take(END + 6, 6), "끝난 틱에 받은 것은 6틱 뒤까지");
    }

    @Test
    void acceptBeforeZero() {
        InputBuffer b = new InputBuffer();
        assertFalse(b.offer(InputBuffer.Kind.LIGHT, END - 1, END, 0, null));
        assertTrue(b.offer(InputBuffer.Kind.LIGHT, END, END, 0, null));
    }

    @Test
    void keepsAim() {
        InputBuffer b = new InputBuffer();
        java.util.UUID u = java.util.UUID.randomUUID();
        b.offer(InputBuffer.Kind.LIGHT, END - 1, END, 6, u);
        assertEquals(u, b.take(END, 6).aim());
    }
}
