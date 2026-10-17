package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * 구역이 놓은 칸 (0.3.7 fix, verify 찾은 것 2): DIFF 백업의 놓은 것이 공기가 아닌 칸만 — 보호 상자 밖 옹벽·기초도 구역 것으로 보아
 * 이사 기간에 부술 수 없고 옛 건물 조사에도 안 잡힌다. 짓는 중 (BEFORE) 백업은 아무 칸도 주지 않는다.
 */
class DistrictPlacedCellsTest {

    @Test
    void diffBackupPlacedNonAirCells() {
        DistrictBackup bk = new DistrictBackup("homes", DistrictBackup.Phase.DIFF, List.of(
                new DistrictBackup.Entry(-182, 63, 72, "minecraft:dirt", "minecraft:stone_bricks"),   // 옹벽
                new DistrictBackup.Entry(-165, 71, 84, "minecraft:air", "minecraft:stone_brick_wall"),
                new DistrictBackup.Entry(-150, 75, 60, "minecraft:oak_log", "minecraft:air"),          // 치운 나무 → 공기 (뺌)
                new DistrictBackup.Entry(-150, 76, 60, "minecraft:oak_leaves[persistent=false]", "minecraft:cave_air"),
                new DistrictBackup.Entry(-182, 63, 72, "minecraft:dirt", "minecraft:stone_bricks"))); // 같은 칸 두 번
        long[] k = DistrictService.placedKeys(bk);
        assertEquals(2, k.length, "공기·중복 뺌");
        assertTrue(DistrictService.containsCell(k, -182, 63, 72));
        assertTrue(DistrictService.containsCell(k, -165, 71, 84));
        assertFalse(DistrictService.containsCell(k, -150, 75, 60), "공기로 바꾼 칸은 아님");
        assertFalse(DistrictService.containsCell(k, -182, 64, 72));
        long[] sorted = k.clone();
        java.util.Arrays.sort(sorted);
        assertArrayEquals(sorted, k, "이진 탐색용 정렬");
    }

    @Test
    void beforePhaseGivesNothing() {
        DistrictBackup bk = new DistrictBackup("homes", DistrictBackup.Phase.BEFORE, List.of(new DistrictBackup.Entry(1, 2, 3, "minecraft:dirt", null)));
        assertEquals(0, DistrictService.placedKeys(bk).length);
        assertEquals(0, DistrictService.placedKeys(null).length);
        assertFalse(DistrictService.containsCell(new long[0], 1, 2, 3));
    }
}
