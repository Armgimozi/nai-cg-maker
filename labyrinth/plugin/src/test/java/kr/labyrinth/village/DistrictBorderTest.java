package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * 야생 경계에 광산 마을 상자 (0.3.6.1 CONTRACT §2.13 — WildBorderDistrict): 지은 자리가 east 든 south_east 든 구역 보호 상자가
 * 마을 경계 안에 들고, 경계는 저절로 넓어진다.
 */
class DistrictBorderTest {

    static VillageMeta district(String site) throws Exception {
        DistrictLibrary.Entry e = DistrictLayoutTest.library().get("mine");
        VillageMeta v = DistrictLayoutTest.shipped();
        Plan p = DistrictLayoutTest.plan(e, e.layout().site(site), v, DistrictLayoutTest.terrain(v));
        assertTrue(p.ok(), p.reason);
        return Markers.meta(p, Layout.of("광산 마을", 8, 6, List.of(), List.of(), java.util.Map.of()));
    }

    @Test
    void districtBoxesInsideBorderWhereverBuilt() throws Exception {
        VillageMeta v = DistrictLayoutTest.shipped();
        WildBorder.Square village = WildBorder.compute(v, 30);
        for (String site : List.of("east", "south_east")) {
            VillageMeta d = district(site);
            WildBorder.Square both = WildBorder.compute(v, List.of(d), 30);
            assertTrue(WildBorder.boxesOutside(both, d.protect).isEmpty(), site + ": 구역 상자가 경계 밖");
            assertTrue(WildBorder.boxesOutside(both, v.protect).isEmpty(), site + ": 마을 상자가 경계 밖");
            assertTrue(both.size() > village.size(), site + ": 경계가 넓어짐");
            // 구역 상자는 마을만의 경계 밖으로 나가 있었다 (그래서 더해야 한다)
            assertTrue(!WildBorder.boxesOutside(village, d.protect).isEmpty() || both.size() > village.size());
            // NPC·광산에서 돌아오는 자리도 경계 안
            for (VillageMeta.Pos p : d.npcs.values()) assertTrue(both.contains(p.x(), p.z()), site + " NPC " + p);
            VillageMeta.Pos exit = d.points.get("mine_exit");
            assertTrue(exit != null && both.contains(exit.x(), exit.z()), site + " mine_exit");
        }
    }
}
