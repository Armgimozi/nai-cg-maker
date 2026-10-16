package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.UUID;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/**
 * PvP 안전지대에 광산 마을 (0.3.6.1 CONTRACT §2.13 — VillageZoneDistrict): 구역 기록의 보호 상자 + safe_margin(8) 안은 싸울 수 없다.
 * 마을 원(중심 −136, 16 · 반경 37 + 8)에서 48칸 떨어진 제련소 앞도.
 */
class VillageZoneDistrictTest {

    static YamlConfiguration yaml(String s) throws InvalidConfigurationException {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(s);
        return y;
    }

    @Test
    void districtBoxesJoinTheSafeZone() throws InvalidConfigurationException {
        UUID world = UUID.randomUUID();
        VillageZone.Zone village = VillageZone.parse(yaml("center: [-136, 64, 16]\nradius: 37\n"), world, 8);
        // 제련소 상자 x −89..−75 · z 22..35 (조각 상자 + 1)
        List<double[]> rects = VillageZone.parseDistrict(yaml("state: built\nsafe_margin: 8\nprotect:\n- [-89, 60, 22, -75, 85, 35]\n"));
        assertEquals(1, rects.size());
        VillageZone.Zone z = village.withRects(rects);
        assertFalse(village.contains(world, -82, 20), "마을 원만으로는 제련소 앞이 밖");
        assertTrue(z.contains(world, -82, 20), "제련소 문 앞");
        assertTrue(z.contains(world, -89 - 8, 22 - 8), "상자 + 8칸 모서리");
        assertTrue(z.contains(world, -74 + 8, 36 + 8 - 0.01), "x1+1 · z1+1 모서리 기준");
        assertFalse(z.contains(world, -74 + 8.5, 30), "그 너머 (동쪽 — 마을 원에서도 멂)");
        assertTrue(z.contains(world, -136.5, 16.5), "마을 원도 그대로");
        assertFalse(z.contains(UUID.randomUUID(), -82, 20), "다른 월드");
        // 짓는 중도 안전지대 (보호가 켜져 있음), 지운 구역은 아님
        assertEquals(1, VillageZone.parseDistrict(yaml("state: building\nprotect:\n- [0, 0, 0, 1, 1, 1]\n")).size());
        assertTrue(VillageZone.parseDistrict(yaml("state: removed\nprotect:\n- [0, 0, 0, 1, 1, 1]\n")).isEmpty());
        assertTrue(VillageZone.districtFile("labyrinth-district-mine.yml"));
        assertFalse(VillageZone.districtFile("labyrinth-district-mine.backup.gz"));
        assertFalse(VillageZone.districtFile("labyrinth-village.yml"));
    }
}
