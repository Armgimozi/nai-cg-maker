package kr.souls;

import kr.souls.progression.LoadTiers;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 장비 무게 단계 (DESIGN 5.8): 30% 밑 가벼움, 70% 밑 보통, 100% 까지 무거움, 넘으면 과적 (뒷걸음만, 달리기 없음). */
class LoadTiersTest {
    private final LoadTiers t = LoadTiers.defaults();

    @Test
    void boundaries() {
        assertEquals("light", t.of(0, 40).id());
        assertEquals("light", t.of(11.9, 40).id());
        assertEquals("medium", t.of(12, 40).id());
        assertEquals("medium", t.of(27.9, 40).id());
        assertEquals("heavy", t.of(28, 40).id());
        assertEquals("heavy", t.of(40, 40).id());
        assertEquals("over", t.of(40.1, 40).id());
    }

    @Test
    void overloadedCannotSprintOrRoll() {
        LoadTiers.Tier over = t.of(100, 40);
        assertFalse(over.sprint());
        assertEquals("backstep", over.roll());
        assertTrue(t.of(0, 40).sprint());
    }

    @Test
    void walkSlowsWithWeight() {
        double prev = 2;
        for (LoadTiers.Tier x : t.all()) {
            assertTrue(x.walk() <= prev, x.id());
            prev = x.walk();
        }
    }
}
