package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** 받은 뒤 가는 길 한 줄 (0.3.7 fix, fun 5): 집 가기를 쓸 수 있고 그 집 앞이 아니면 " 가려면 /미궁 집 가기". */
class ClaimHintTest {

    @Test
    void hintOnlyWhenFarAndAllowed() {
        assertTrue(PlayUi.claimedHint(true, false).contains("/미궁 집 가기"));
        assertEquals("", PlayUi.claimedHint(true, true), "이미 대문 앞 (표지판으로 받음)");
        assertEquals("", PlayUi.claimedHint(false, false), "집 가기가 꺼진 서버");
    }
}
