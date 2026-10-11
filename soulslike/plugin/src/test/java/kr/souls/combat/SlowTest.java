package kr.souls.combat;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** M1 P1-0 계약 (S4): 느려짐은 걸린 몫 가운데 가장 느린 것 하나 (곱하지 않는다), 뿌리 0 이 이긴다. */
class SlowTest {
    @Test
    void strongestWins() {
        assertEquals(1.0, Slow.strongest(null));
        assertEquals(1.0, Slow.strongest(List.of()));
        assertEquals(0.5, Slow.strongest(List.of(0.5, 0.75)));
        assertEquals(0.5, Slow.strongest(List.of(0.75, 0.5)), "차례와 상관없다");
        assertEquals(0.5, Slow.strongest(List.of(0.5, 0.5)), "같은 몫 둘은 −75% 가 아니다");
        assertEquals(0.0, Slow.strongest(List.of(0.5, 0.0, 0.25)), "뿌리가 이긴다");
        assertEquals(1.0, Slow.strongest(Arrays.asList((Double) null)));
        assertEquals(0.0, Slow.strongest(List.of(-3.0)), "0 밑으로 내려가지 않는다");
    }

    @Test
    void vanillaWalk() {
        assertEquals(0.2f, Slow.WALK);
    }
}
