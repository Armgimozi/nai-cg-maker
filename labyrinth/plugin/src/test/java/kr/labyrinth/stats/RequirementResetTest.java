package kr.labyrinth.stats;

import static org.junit.jupiter.api.Assertions.*;

import java.util.UUID;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.ui.menus.StatsMenu;
import org.junit.jupiter.api.Test;

/** 0.3.4 착용 조건 변경 — 포인트를 나눈 예전 플레이어에게 무료 초기화를 한 번만 되돌려 준다. */
class RequirementResetTest {

    @Test
    void allocatedPlayerGetsFreeResetBackOnce() {
        PlayerData d = new PlayerData(UUID.randomUUID(), "a");
        d.statPoints(10);
        assertTrue(d.allocate(Stat.STR, 6));
        d.counter(StatsMenu.FREE_RESET_KEY, 1); // 예전 판에서 무료 초기화를 이미 씀
        assertTrue(LevelService.grantRequirementReset(d));
        assertEquals(0, d.counter(StatsMenu.FREE_RESET_KEY));
        d.counter(StatsMenu.FREE_RESET_KEY, 1); // 다시 씀
        assertFalse(LevelService.grantRequirementReset(d));
        assertEquals(1, d.counter(StatsMenu.FREE_RESET_KEY));
    }

    @Test
    void playerWithoutAllocationIsOnlyMarked() {
        PlayerData d = new PlayerData(UUID.randomUUID(), "b");
        d.counter(StatsMenu.FREE_RESET_KEY, 1);
        assertFalse(LevelService.grantRequirementReset(d));
        assertEquals(1, d.counter(StatsMenu.FREE_RESET_KEY));
        assertEquals(Boolean.TRUE, d.ext().get(LevelService.REQ_RESET_FLAG));
    }
}
