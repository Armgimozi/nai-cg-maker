package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import kr.labyrinth.homes.rules.PlotRules.Act;
import kr.labyrinth.homes.rules.PlotRules.Verdict;
import kr.labyrinth.homes.rules.PlotRules.Where;
import kr.labyrinth.village.DistrictBackup;
import org.bukkit.block.BlockFace;
import org.junit.jupiter.api.Test;

/**
 * 0.3.7 검증·리뷰 고친 것 (plots-037 fix) — 서버 없이 보는 규칙.
 * <ul>
 *   <li>잠긴 들판의 옛 거치대·액자: 장비·물건 꺼내기는 늘, 떼어 옮기기는 이사 기간에만 (exploit M2 · live 5)</li>
 *   <li>남의 집에서 블록을 놓으려 할 때 글 (verify 1) · 막힌 서버 받기 글 (verify 4) · 안전 모드 · 새 월드 잠금 · 집터 없이 lock on</li>
 *   <li>짐을 진 동물 · 장식 항아리 (exploit L5·L6) · 구역이 놓은 칸 (verify 2) · 큰 상자 짝 (exploit L1)</li>
 * </ul>
 */
class PlotFix037Test {

    @Test
    void legacyDecorationsInLockedWild() {
        // 꺼내기·넣기·돌리기 (DECO_USE): 잠긴 들판에서는 상자처럼 늘 됨, 남의 집에서는 안 됨, 마을 보호 칸에서도 안 됨
        assertEquals(Verdict.ALLOW, PlotRules.decide(Act.DECO_USE, Where.WILD_LOCKED, false, false));
        assertEquals(Verdict.ALLOW, PlotRules.decide(Act.DECO_USE, Where.OWN, false, false));
        assertEquals(Verdict.DENY, PlotRules.decide(Act.DECO_USE, Where.GUEST, false, false));
        assertEquals(Verdict.DENY, PlotRules.decide(Act.DECO_USE, Where.STRANGER, false, false));
        assertEquals(Verdict.DENY, PlotRules.decide(Act.DECO_USE, Where.PROTECTED, false, false));
        assertEquals(Verdict.PASS, PlotRules.decide(Act.DECO_USE, Where.WILD_OPEN, false, false));
        // 떼기 (걸개·거치대·탈것 부수기): 이사 기간이면 됨, 끝나면 막힘
        for (Act a : List.of(Act.HANGING, Act.ARMOR_STAND, Act.VEHICLE)) {
            assertEquals(Verdict.ALLOW, PlotRules.decide(a, Where.WILD_LOCKED, false, true), a + " 이사 기간");
            assertEquals(Verdict.DENY, PlotRules.decide(a, Where.WILD_LOCKED, false, false), a + " 이사 기간 끝");
            assertEquals(Verdict.DENY, PlotRules.decide(a, Where.STRANGER, false, true), a + " 남의 집은 이사 기간과 상관없음");
        }
        // 놓기는 grace 를 넘기지 않으므로 그대로 막힘 · 다른 행동은 이사 기간에도 그대로
        assertEquals(Verdict.DENY, PlotRules.decide(Act.PLACE, Where.WILD_LOCKED, false, true));
        assertEquals(Verdict.DENY, PlotRules.decide(Act.BUCKET, Where.WILD_LOCKED, false, true));
        int[] r = PlotRules.selfCheck();
        assertEquals(r[1], r[0], "자가 진단 표가 모두 맞음");
    }

    @Test
    void worldItemsGetAMessageWhenBlockUseIsDenied() {
        // Paper 는 블록 쓰기를 막으면 손에 든 것 쓰기도 막아 놓기 이벤트가 오지 않음 → 놓는·바꾸는 아이템이면 글을 보냄
        assertTrue(PlotRules.worldItem("OAK_PLANKS", true, false));
        assertTrue(PlotRules.worldItem("WATER_BUCKET", false, true));
        assertTrue(PlotRules.worldItem("IRON_HOE", false, true));
        assertTrue(PlotRules.worldItem("OAK_BOAT", false, false));
        assertTrue(PlotRules.worldItem("WHEAT_SEEDS", false, false));
        assertTrue(PlotRules.worldItem("COW_SPAWN_EGG", false, false));
        assertTrue(PlotRules.worldItem("ARMOR_STAND", false, true));
        assertTrue(PlotRules.worldItem("ITEM_FRAME", false, false));
        assertFalse(PlotRules.worldItem("BREAD", false, false), "먹기는 글 없음");
        assertFalse(PlotRules.worldItem("MILK_BUCKET", false, false), "마시기");
        assertFalse(PlotRules.worldItem("DIAMOND_SWORD", false, false));
        assertFalse(PlotRules.worldItem("", false, false));
    }

    @Test
    void claimOnBlockedServerSaysNoDistrictFirst() {
        // verify 4: 집 구역이 없으면 번지를 찾기 전에 "아직 집 구역이 없습니다."
        assertEquals("아직 집 구역이 없습니다.", ClaimRules.preClaim(true, false, false, false));
        assertEquals("이 서버에서는 집 기능을 쓰지 않습니다.", ClaimRules.preClaim(false, false, true, false));
        assertEquals(Guard.BROKEN, ClaimRules.preClaim(true, true, true, false), "안전 모드 (live 6)");
        assertEquals("집 구역을 지우는 중입니다.", ClaimRules.preClaim(true, false, true, true), "force 로 지우는 동안 (live 11)");
        assertNull(ClaimRules.preClaim(true, false, true, false));
    }

    @Test
    void lockStateAndRules() {
        // 집터 없이 lock on: 이제 실제로 막는다 (rulesOn) · 집 기능을 꺼도 집터가 있으면 지킨다
        assertTrue(TerrainLock.rulesOn(false, false, true), "집터 없이 lock on");
        assertTrue(TerrainLock.rulesOn(true, true, false), "homes: false 여도 지어진 집터는 지킴");
        assertTrue(TerrainLock.rulesOn(false, true, false), "convert 집만");
        assertFalse(TerrainLock.rulesOn(false, false, false), "막힌 서버 · 잠금 꺼짐 = 예전 그대로");
        // 안전 모드: lock off 였어도 잠금 (상태를 모름) · 설정이 끄면 끔
        assertTrue(TerrainLock.locked(true, true, TerrainLock.State.OFF, false, true));
        assertFalse(TerrainLock.locked(true, false, TerrainLock.State.ON, true, true), "terrain_lock: false");
        assertFalse(TerrainLock.locked(false, true, TerrainLock.State.ON, true, true), "homes: false");
        assertEquals(TerrainLock.locked(true, true, TerrainLock.State.AUTO, true), TerrainLock.locked(true, true, TerrainLock.State.AUTO, true, false));
    }

    @Test
    void freshWorldStartsLockWithoutGrace() {
        // live 2 · fun 1: 배포 world.zip (fresh_world) 은 이사 기간·옛 건물 조사 없이
        assertEquals(Grace.Start.FRESH, Grace.start(true, 0, true));
        assertEquals(Grace.Start.GRACE, Grace.start(true, 0, false), "업그레이드한 서버는 그대로 14일");
        assertEquals(Grace.Start.NONE, Grace.start(false, 0, true), "아직 잠금 꺼짐");
        assertEquals(Grace.Start.NONE, Grace.start(true, 123, false), "두 번째 켜기 — 다시 세지 않음");
        assertEquals(Grace.Start.NONE, Grace.start(true, 123, true));
    }

    @Test
    void animalsKeepedButGearGoesToParcel() {
        for (String t : List.of("horse", "donkey", "mule", "llama", "trader_llama", "camel", "pig", "strider", "wolf", "happy_ghast")) {
            assertEquals(PlotResetPlan.EntityTake.ANIMAL_GEAR, PlotResetPlan.entity(t), t);
            assertTrue(PlotResetPlan.gearAnimal(t), t);
        }
        assertEquals(PlotResetPlan.EntityTake.NONE, PlotResetPlan.entity("cow"), "짐 없는 동물은 그대로");
        assertEquals(PlotResetPlan.EntityTake.NONE, PlotResetPlan.entity("player"));
        assertEquals(PlotResetPlan.EntityTake.VEHICLE, PlotResetPlan.entity("oak_chest_boat"));
        assertTrue(PlotResetPlan.dropsWithoutTool("DECORATED_POT"), "장식 항아리는 맨손 드롭 (조각 안 나게)");
        assertTrue(PlotResetPlan.dropsWithoutTool("minecraft:decorated_pot"));
        assertFalse(PlotResetPlan.dropsWithoutTool("GLASS"), "유리는 섬세한 손길 그대로");
    }

    @Test
    void districtPlacedCellsAreNotLegacy() {
        long[] placed = {DistrictBackup.pack(-182, 63, 72), DistrictBackup.pack(-74, 60, -7), DistrictBackup.pack(-74, 61, -7)};
        java.util.Arrays.sort(placed);
        assertTrue(LegacyScan.placedCell(placed, -182, 63, 72), "집 구역 서쪽 옹벽 (verify 2)");
        assertTrue(LegacyScan.placedCell(placed, -74, 61, -7), "광산 마을 벽");
        assertFalse(LegacyScan.placedCell(placed, -182, 64, 72));
        assertFalse(LegacyScan.placedCell(new long[0], -182, 63, 72));
        assertFalse(LegacyScan.placedCell(null, 0, 0, 0));
    }

    @Test
    void doubleChestPairSide() {
        // 바닐라 ChestBlock.getConnectedDirection: LEFT → 시계 방향, RIGHT → 반시계
        assertEquals(BlockFace.EAST, PlotRulesListener.pairSide(BlockFace.NORTH, true));
        assertEquals(BlockFace.WEST, PlotRulesListener.pairSide(BlockFace.NORTH, false));
        assertEquals(BlockFace.SOUTH, PlotRulesListener.pairSide(BlockFace.EAST, true));
        assertEquals(BlockFace.WEST, PlotRulesListener.pairSide(BlockFace.SOUTH, true));
        assertEquals(BlockFace.NORTH, PlotRulesListener.pairSide(BlockFace.WEST, true));
        assertEquals(BlockFace.SOUTH, PlotRulesListener.pairSide(BlockFace.WEST, false));
    }
}
