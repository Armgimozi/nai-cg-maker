package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** 경계 넘는 것 (plan §9): 흐름·피스톤·깔때기·자람·퍼짐·뼛가루·발사기·골렘·스펀지·차원문·몹. zone 3·7 = 집터, 0 = 보호 상자, −1 = 그 밖. */
class CrossZoneTest {

    @Test
    void flow() {
        assertTrue(CrossZone.flow(3, 3));
        assertTrue(CrossZone.flow(-1, -1), "밖 → 밖 자연 물은 그대로");
        assertFalse(CrossZone.flow(3, -1), "집 물이 밖으로");
        assertFalse(CrossZone.flow(-1, 3), "바깥 용암이 집으로");
        assertFalse(CrossZone.flow(3, 7), "이웃 집으로");
        assertFalse(CrossZone.flow(3, 0), "골목으로");
    }

    @Test
    void piston() {
        assertTrue(CrossZone.piston(3, new int[] {3, 3, 3}, true));
        assertFalse(CrossZone.piston(3, new int[] {3, 7}, true), "생울타리 너머 이웃 집으로 밀기");
        assertFalse(CrossZone.piston(3, new int[] {3, -1}, false), "집 밖 (높이 창 위) 으로");
        assertTrue(CrossZone.piston(-1, new int[] {-1, -1}, true), "잠긴 들판의 옛 피스톤 문 (들판 → 들판) 은 움직임 (live 8)");
        assertFalse(CrossZone.piston(-1, new int[] {-1, 0}, true), "잠긴 들판 피스톤이 보호 칸으로");
        assertFalse(CrossZone.piston(-1, new int[] {-1, 3}, true), "잠긴 들판 피스톤이 집 칸으로");
        assertTrue(CrossZone.piston(-1, new int[] {-1, -1}, false), "잠금 꺼진 들판은 그대로");
        assertFalse(CrossZone.piston(-1, new int[] {-1, 3}, false), "들판 피스톤이 집 칸을 건드림");
        assertTrue(CrossZone.piston(0, new int[] {0}, true), "보호 칸은 마을 핸들러가 봄");
        assertFalse(CrossZone.piston(0, new int[] {3}, true));
    }

    @Test
    void hoppersAndGolems() {
        assertTrue(CrossZone.transfer(3, 3));
        assertFalse(CrossZone.transfer(3, 7), "생울타리 너머 깔때기");
        assertFalse(CrossZone.transfer(-1, 3));
        assertTrue(CrossZone.transfer(-1, -1));
        assertTrue(CrossZone.pickup(3, 3));
        assertFalse(CrossZone.pickup(7, 3), "이웃 집 아이템 줍기");
        assertTrue(CrossZone.golem(3, 3));
        assertFalse(CrossZone.golem(3, 7), "구리 골렘이 이웃 집 상자로 (R4)");
        assertFalse(CrossZone.golem(-1, 3));
    }

    @Test
    void growthSpreadFertilize() {
        assertTrue(CrossZone.allSame(3, new int[] {3, 3, 3}));
        assertFalse(CrossZone.allSame(3, new int[] {3, -1}), "가장자리 나무 (R17)");
        assertTrue(CrossZone.allSame(-1, new int[] {-1, -1}), "들판 나무");
        assertTrue(CrossZone.allSame(3, new int[0]));
        assertTrue(CrossZone.spread(3, 3, false));
        assertFalse(CrossZone.spread(3, 7, false));
        assertFalse(CrossZone.spread(3, 3, true), "불 번짐은 늘 취소");
        assertTrue(CrossZone.falling(3, 3));
        assertFalse(CrossZone.falling(-1, 3), "모래가 집으로 떨어짐");
    }

    @Test
    void dispenser() {
        assertTrue(CrossZone.dispense(101, 101, true), "convert 집 안 발사기");
        assertFalse(CrossZone.dispense(101, -1, true), "옛 발사기가 물·뼛가루를 집 밖으로 (R4)");
        assertFalse(CrossZone.dispense(-1, -1, true), "잠긴 들판 발사기");
        assertTrue(CrossZone.dispense(-1, -1, false));
        assertFalse(CrossZone.dispense(-1, 3, false));
        assertFalse(CrossZone.dispense(0, 0, false));
    }

    @Test
    void spongeAndPortals() {
        assertTrue(CrossZone.sponge(3, 3));
        assertFalse(CrossZone.sponge(3, 0));
        assertTrue(CrossZone.portalByPlayer(3, new int[] {3, 3, 3}));
        assertFalse(CrossZone.portalByPlayer(3, new int[] {3, -1}));
        assertFalse(CrossZone.portalByPlayer(-1, new int[] {-1, -1}), "들판 차원문 (잠금 켜짐)");
        assertTrue(CrossZone.portalPair(new int[] {5, 5}, 5), "지나온 사람의 집 안");
        assertFalse(CrossZone.portalPair(new int[] {5, 5}, -1), "남의 집·빈 집에 돌아오는 문 (exploit L4)");
        assertFalse(CrossZone.portalPair(new int[] {5, 5}, 6), "다른 사람 집");
        assertFalse(CrossZone.portalPair(new int[] {-1, -1}, -1), "돌아오는 문이 들판에 → 취소");
        assertFalse(CrossZone.portalPair(new int[] {5, 6}, 5));
    }

    @Test
    void mobs() {
        assertTrue(CrossZone.mobChange(-1, -1, true, false), "잠금 꺼진 들판은 바닐라 (엔더맨도)");
        assertFalse(CrossZone.mobChange(-1, -1, true, true), "잠긴 들판의 엔더맨");
        assertTrue(CrossZone.mobChange(-1, -1, false, true), "잠긴 들판의 양이 풀을 먹음");
        assertFalse(CrossZone.mobChange(-1, 3, false, true), "밖의 몹이 집 블록을");
        assertTrue(CrossZone.mobChange(3, 3, false, true), "집 안 양·주민");
        assertFalse(CrossZone.mobChange(3, 3, true, true), "집 안 엔더맨");
        assertTrue(CrossZone.entityForm(3, true));
        assertFalse(CrossZone.entityForm(-1, true), "잠긴 들판의 눈 골렘 자국");
        assertFalse(CrossZone.entityForm(0, false));
        assertTrue(CrossZone.entityForm(-1, false));
    }
}
