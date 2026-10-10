package kr.souls;

import kr.souls.item.RingRules;
import kr.souls.item.RingRules.Act;
import kr.souls.item.RingRules.Kind;
import kr.souls.item.RingRules.Thing;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 반지 칸 판정 (DESIGN 9.4, item/RingRules): 2×2 의 왼쪽 세로 두 칸만 반지를 받고, 나머지 셋은 아무것도 받지도 내주지도 않는다. */
class RingRulesTest {
    private static final Thing E = Thing.EMPTY, R = Thing.RING, O = Thing.OTHER;

    private static Act act(int raw, Kind k, Thing cursor, Thing slot, Thing other, int free) {
        return RingRules.decide(raw, k, cursor, slot, other, free).act();
    }

    @Test
    void slotsAreTheLeftColumn() {
        assertEquals(0, RingRules.ringIndex(1));
        assertEquals(1, RingRules.ringIndex(3));
        for (int raw : new int[] {0, 2, 4, 5, 9, 36, 45, -999}) assertEquals(-1, RingRules.ringIndex(raw), "칸 " + raw);
        assertEquals(1, RingRules.rawOf(0));
        assertEquals(3, RingRules.rawOf(1));
        for (int raw = 0; raw <= 4; raw++) assertTrue(RingRules.craftArea(raw));
        assertFalse(RingRules.craftArea(5));
        assertFalse(RingRules.craftArea(-999));
    }

    /** 결과 칸과 오른쪽 두 칸: 무엇을 어떻게 눌러도 거절. */
    @Test
    void erasedSlotsRefuseEverything() {
        for (int raw : new int[] {0, 2, 4}) {
            for (Kind k : Kind.values()) {
                for (Thing c : Thing.values()) {
                    for (Thing s : Thing.values()) {
                        assertEquals(Act.DENY, act(raw, k, c, s, R, 0), "칸 " + raw + " " + k + " 손 " + c + " 칸 " + s);
                    }
                }
            }
        }
    }

    @Test
    void clickPutsTakesAndSwapsRingsOnly() {
        for (Kind k : new Kind[] {Kind.LEFT, Kind.RIGHT}) {
            assertEquals(Act.PUT, act(1, k, R, E, E, 0));
            assertEquals(Act.TAKE, act(3, k, E, R, E, -1));
            assertEquals(Act.SWAP_CURSOR, act(1, k, R, R, E, -1));
            assertEquals(Act.DENY, act(1, k, O, E, E, 0), "반지가 아닌 것은 끼지 않는다");
            assertEquals(Act.DENY, act(1, k, O, R, E, -1), "반지가 아닌 것과 바꾸지 않는다");
            assertEquals(Act.DENY, act(1, k, E, E, E, 0));
        }
        assertEquals(1, RingRules.decide(3, Kind.LEFT, R, E, E, 1).ring());
    }

    @Test
    void shiftClickEquipsAndUnequips() {
        assertEquals(Act.TO_STORAGE, act(1, Kind.SHIFT, E, R, E, -1));
        assertEquals(Act.DENY, act(3, Kind.SHIFT, E, E, E, 1));
        // 가방의 반지를 웅크리고 누르면 빈 반지 칸에
        RingRules.Decision d = RingRules.decide(20, Kind.SHIFT, E, R, E, 1);
        assertEquals(Act.EQUIP_FROM, d.act());
        assertEquals(1, d.ring());
        // 반지 칸이 차 있으면 바닐라 그대로 (가방 ↔ 단축 슬롯)
        assertEquals(Act.PASS, act(20, Kind.SHIFT, E, R, E, -1));
        // 반지가 아닌 것은 바닐라 그대로 (2×2 에는 가지 않는다: 바닐라의 웅크리고 누르기는 2×2 로 옮기지 않는다)
        assertEquals(Act.PASS, act(20, Kind.SHIFT, E, O, E, 0));
    }

    @Test
    void numberKeysAndOffhandSwapOnlyWithRingsOrEmpty() {
        for (Kind k : new Kind[] {Kind.NUMBER, Kind.OFFHAND}) {
            assertEquals(Act.SWAP_WITH, act(1, k, E, E, R, 0), "단축 칸의 반지를 낀다");
            assertEquals(Act.SWAP_WITH, act(1, k, E, R, E, -1), "낀 반지를 단축 칸으로");
            assertEquals(Act.SWAP_WITH, act(3, k, E, R, R, -1), "반지끼리 바꾼다");
            assertEquals(Act.DENY, act(1, k, E, R, O, -1), "단축 칸의 다른 것은 오지 않는다");
            assertEquals(Act.DENY, act(1, k, E, E, O, 0));
            assertEquals(Act.DENY, act(1, k, E, E, E, 0));
        }
    }

    @Test
    void dropDoubleMiddleCreativeRefusedOnRingSlots() {
        for (Kind k : new Kind[] {Kind.DROP, Kind.DOUBLE, Kind.MIDDLE, Kind.CREATIVE, Kind.OTHER}) {
            assertEquals(Act.DENY, act(1, k, E, R, E, -1), k.name());
            assertEquals(Act.DENY, act(3, k, R, E, E, 1), k.name());
        }
        // 반지를 들고 두 번 누르기 (같은 것 모으기) 는 어디서든 거절, 그 밖의 바깥 누르기는 바닐라 그대로
        assertEquals(Act.DENY, act(20, Kind.DOUBLE, R, E, E, 0));
        assertEquals(Act.PASS, act(20, Kind.DOUBLE, O, E, E, 0));
        assertEquals(Act.PASS, act(20, Kind.LEFT, R, E, E, 0));
        assertEquals(Act.PASS, act(-999, Kind.LEFT, R, E, E, 0));
    }

    @Test
    void sameRingTwiceIsRefused() {
        String[] worn = {"test_stamina", null};
        assertTrue(RingRules.duplicate(worn, 1, "test_stamina"));
        assertFalse(RingRules.duplicate(worn, 0, "test_stamina"), "같은 칸에서 바꾸는 것은 겹치지 않는다");
        assertFalse(RingRules.duplicate(worn, 1, "test_poise"));
        assertFalse(RingRules.duplicate(worn, 1, null));
        assertEquals(1, RingRules.firstFree(worn));
        assertEquals(0, RingRules.firstFree(new String[] {null, "test_poise"}));
        assertEquals(-1, RingRules.firstFree(new String[] {"a", "b"}));
    }
}
