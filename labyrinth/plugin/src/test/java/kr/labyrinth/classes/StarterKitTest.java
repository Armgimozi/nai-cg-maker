package kr.labyrinth.classes;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** 시작 꾸러미: 기존 플레이어가 접속할 때 받는 조건 (처음 전직할 때는 조건 없이 한 번). */
class StarterKitTest {

    @Test
    void joinGrantsKitOnlyToFreshCharacters() {
        assertTrue(LabyrinthClassService.joinGrantsKit(1, 0));
        assertTrue(LabyrinthClassService.joinGrantsKit(LabyrinthClassService.KIT_JOIN_MAX_LEVEL, 0));
        // Lv.6 이상이거나 지하 1층을 이미 깬 사람은 받은 것으로 기록만
        assertFalse(LabyrinthClassService.joinGrantsKit(LabyrinthClassService.KIT_JOIN_MAX_LEVEL + 1, 0));
        assertFalse(LabyrinthClassService.joinGrantsKit(20, 0));
        assertFalse(LabyrinthClassService.joinGrantsKit(3, 1));
        assertFalse(LabyrinthClassService.joinGrantsKit(30, 12));
    }
}
