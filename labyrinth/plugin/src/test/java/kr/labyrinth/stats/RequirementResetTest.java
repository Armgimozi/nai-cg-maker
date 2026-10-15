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

    // ── 0.3.5 스탯 역할 변경 (힘 = 물리 · 지능 = 마법 · 민첩 = 공속·치명·회피) ──

    @Test
    void roleResetGivesFreeResetBackOnceForAllocatedPlayers() {
        PlayerData d = new PlayerData(UUID.randomUUID(), "c");
        d.statPoints(20);
        assertTrue(d.allocate(Stat.DEX, 15));
        d.counter(StatsMenu.FREE_RESET_KEY, 1);
        assertTrue(LevelService.grantRoleReset(d));
        assertEquals(0, d.counter(StatsMenu.FREE_RESET_KEY));
        assertEquals(Boolean.TRUE, d.ext().get(LevelService.ROLE_RESET_FLAG));
        assertEquals("stats.role_reset_035", LevelService.ROLE_RESET_FLAG);
        d.counter(StatsMenu.FREE_RESET_KEY, 1);
        assertFalse(LevelService.grantRoleReset(d), "한 번만");
        assertEquals(1, d.counter(StatsMenu.FREE_RESET_KEY));
    }

    @Test
    void roleResetDoesNotStackWithRequirementReset() {
        // 0.3.3 에서 바로 넘어온 사람: 두 깃발 모두 처음이지만 무료 초기화는 하나 (쌓이지 않음)
        PlayerData d = new PlayerData(UUID.randomUUID(), "d");
        d.statPoints(10);
        assertTrue(d.allocate(Stat.STR, 10));
        d.counter(StatsMenu.FREE_RESET_KEY, 1);
        assertTrue(LevelService.grantRequirementReset(d));
        assertTrue(LevelService.grantRoleReset(d));
        assertEquals(0, d.counter(StatsMenu.FREE_RESET_KEY), "무료 1회 (0 = 아직 안 씀)");
    }

    @Test
    void roleResetOnlyMarksPlayerWithoutAllocation() {
        PlayerData d = new PlayerData(UUID.randomUUID(), "e");
        d.counter(StatsMenu.FREE_RESET_KEY, 1);
        assertFalse(LevelService.grantRoleReset(d));
        assertEquals(1, d.counter(StatsMenu.FREE_RESET_KEY));
        assertEquals(Boolean.TRUE, d.ext().get(LevelService.ROLE_RESET_FLAG));
    }
}
