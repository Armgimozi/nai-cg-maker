package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.homes.HomesApi;
import kr.labyrinth.homes.PlotRole;
import kr.labyrinth.homes.rules.PlotRules.Where;
import org.junit.jupiter.api.Test;

/** 지형 잠금 판단 (plan §9): 켜짐 조건 · zone → 어디 · 이사 기간에 부술 수 있는 블록 · 글 없는 블록. */
class TerrainLockClassifierTest {

    @Test
    void lockTurnsOnOnlyAfterDistrictBuilt() {
        TerrainLock.State auto = TerrainLock.State.AUTO, on = TerrainLock.State.ON, off = TerrainLock.State.OFF;
        assertFalse(TerrainLock.locked(true, true, auto, false), "jar 만 바꿨고 집 구역이 아직 (막힘) → 잠금 꺼짐");
        assertTrue(TerrainLock.locked(true, true, auto, true), "집 구역 built → 켜짐");
        assertTrue(TerrainLock.locked(true, true, on, false), "convert 집만 있는 서버는 관리자가 lock on");
        assertFalse(TerrainLock.locked(true, true, off, true), "lock off 면 늘 꺼짐");
        assertFalse(TerrainLock.locked(true, false, on, true), "config homes.terrain_lock: false 면 늘 꺼짐");
        assertFalse(TerrainLock.locked(false, true, on, true), "homes.enabled: false");
    }

    @Test
    void stateParsing() {
        assertEquals(TerrainLock.State.ON, TerrainLock.State.of("on"));
        assertEquals(TerrainLock.State.ON, TerrainLock.State.of("켬"));
        assertEquals(TerrainLock.State.OFF, TerrainLock.State.of("OFF"));
        assertEquals(TerrainLock.State.AUTO, TerrainLock.State.of("이상한 값"));
        assertEquals(TerrainLock.State.AUTO, TerrainLock.State.of(null));
        assertEquals("auto", TerrainLock.State.AUTO.id());
    }

    @Test
    void zoneToWhere() {
        assertEquals(Where.OWN, TerrainLock.where(3, PlotRole.OWNER, true));
        assertEquals(Where.OWN, TerrainLock.where(3, PlotRole.TRUSTED, false));
        assertEquals(Where.GUEST, TerrainLock.where(3, PlotRole.GUEST, true));
        assertEquals(Where.STRANGER, TerrainLock.where(3, PlotRole.NONE, true));
        assertEquals(Where.STRANGER, TerrainLock.where(101, null, true), "빈 집·convert 집도 같은 규칙");
        assertEquals(Where.PROTECTED, TerrainLock.where(HomesApi.ZONE_PROTECTED, PlotRole.OWNER, true), "보호 상자는 주인이어도 보호 상자");
        assertEquals(Where.WILD_LOCKED, TerrainLock.where(HomesApi.ZONE_OUTSIDE, PlotRole.OWNER, true), "높이 창 밖은 내 집 열이라도 그 밖");
        assertEquals(Where.WILD_OPEN, TerrainLock.where(HomesApi.ZONE_OUTSIDE, null, false));
    }

    @Test
    void graceOnlyForHumanBlocks() {
        for (String s : new String[] {"oak_planks", "glass", "glass_pane", "chest", "torch", "cobblestone_wall", "stone_bricks", "white_wool", "crafting_table",
                "oak_door", "stripped_oak_log", "smooth_stone", "cobblestone", "bricks"}) {
            assertTrue(TerrainLock.graceBreakable(s, false), s);
        }
        for (String s : new String[] {"stone", "dirt", "grass_block", "oak_log", "iron_ore", "deepslate", "sand", "gravel", "andesite"}) {
            assertFalse(TerrainLock.graceBreakable(s, false), "R2: 흙·돌·원목·광석은 기간에도 잠김 — " + s);
        }
        assertTrue(TerrainLock.graceBreakable("oak_leaves", true), "지속 잎 (사람이 놓음)");
        assertFalse(TerrainLock.graceBreakable("oak_leaves", false), "자연 잎");
    }

    @Test
    void plantsAreSilent() {
        assertTrue(TerrainLock.silent("short_grass"));
        assertTrue(TerrainLock.silent("poppy"));
        assertTrue(TerrainLock.silent("tall_grass"));
        assertFalse(TerrainLock.silent("stone"));
        assertFalse(TerrainLock.silent("oak_planks"));
    }
}
