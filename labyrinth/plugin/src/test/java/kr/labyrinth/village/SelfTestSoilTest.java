package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.bukkit.Material;
import org.junit.jupiter.api.Test;

/** 자가 진단: 풀 ↔ 흙 (무작위 틱) 은 어긋남이 아니다 — 그 밖의 바뀜은 그대로 어긋남 (0.3.6.1 검증). */
class SelfTestSoilTest {

    @Test
    void grassAndDirtAreNatural() {
        assertTrue(VillageSelfTest.naturalSoil(Material.GRASS_BLOCK, Material.DIRT), "덮인 풀 → 흙");
        assertTrue(VillageSelfTest.naturalSoil(Material.DIRT, Material.GRASS_BLOCK), "흙에 풀이 번짐");
        assertTrue(VillageSelfTest.naturalSoil(Material.GRASS_BLOCK, Material.GRASS_BLOCK), "눈 덮인 풀(snowy)도 같은 풀");
    }

    @Test
    void otherChangesStillCount() {
        assertFalse(VillageSelfTest.naturalSoil(Material.GRASS_BLOCK, Material.AIR), "파낸 칸");
        assertFalse(VillageSelfTest.naturalSoil(Material.GRASS_BLOCK, Material.DIRT_PATH), "길로 바꾼 칸");
        assertFalse(VillageSelfTest.naturalSoil(Material.DIRT, Material.COBBLESTONE), "흙 → 조약돌");
        assertFalse(VillageSelfTest.naturalSoil(Material.STONE_BRICKS, Material.DIRT), "돌벽돌 → 흙");
        assertFalse(VillageSelfTest.naturalSoil(Material.COARSE_DIRT, Material.DIRT), "거친 흙은 조각이 일부러 쓴 블록");
    }
}
