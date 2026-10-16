package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.MineDef;
import org.junit.jupiter.api.Test;

/**
 * jar 청사진 L1..L6 (계약 §2.1·§4, §0-2 뒤): 층 6 · 광석 섞임 · 광석별 블록 수 = vein_blocks · 보석 노드 = gem_nodes ·
 * 바닥 이어짐 · 광맥이 보이고 닿음 · 장식에 광석·보석·빈 광맥 블록 없음 · 번호 = (y, z, x) 차례 · 승강기·내리는 자리·관리소.
 * 손 닿는 광맥 수 한도는 없다 (주인: "매크로 굳이 막을 필요 없음").
 */
class MineBlueprintTest {

    @Test
    void sixLevelsMatchMineDef() {
        MineDef mine = MineTestData.mine();
        assertEquals(6, mine.levels().size());
        for (MineDef.Level l : mine.levels()) {
            MineBlueprint bp = MineTestData.blueprint(l.n());
            assertEquals("mine_L" + l.n(), bp.id);
            assertEquals(l.n(), bp.level);
            assertEquals(l.floorY(), bp.floorY);
            assertEquals(61, bp.w);
            assertEquals(16, bp.h);
            assertEquals(61, bp.d);
            assertEquals(-30, bp.ox);
            assertEquals(-30, bp.oz);
            assertTrue(bp.oy >= l.floorY() - 4 && bp.oy + bp.h - 1 <= l.floorY() + 15, l.id() + " 청사진이 층 상자 [바닥 − 4, 바닥 + 15] 안");
        }
    }

    @Test
    void oreMixAndCountsPerLevel() {
        MineDef mine = MineTestData.mine();
        var levels = MineTestData.mineJson().maps("levels");
        int total = 0, gems = 0;
        for (MineDef.Level l : mine.levels()) {
            MineBlueprint bp = MineTestData.blueprint(l.n());
            Map<String, Integer> got = new HashMap<>();
            for (MineBlueprint.Node v : bp.veins()) got.merge(v.id(), 1, Integer::sum);
            Map<String, Integer> want = new HashMap<>();
            var vb = levels.get(l.n() - 1).sub("vein_blocks");
            for (String k : vb.keys()) want.put(k, vb.integer(k, 0));
            assertEquals(want, got, l.id() + " 광석별 블록 수");
            assertTrue(got.size() >= 3, l.id() + " 광석 3종 이상 섞임");
            assertEquals(l.oreWeights().keySet(), got.keySet(), l.id() + " 섞임 종류");
            List<String> gemIds = new ArrayList<>();
            for (MineBlueprint.Node g : bp.gems()) gemIds.add(g.id());
            List<String> wantGems = new ArrayList<>(levels.get(l.n() - 1).strings("gem_nodes"));
            gemIds.sort(null);
            wantGems.sort(null);
            assertEquals(wantGems, gemIds, l.id() + " 보석 노드");
            for (MineBlueprint.Node v : bp.veins()) assertNotNull(mine.ores().get(v.id()), v.id());
            for (MineBlueprint.Node g : bp.gems()) assertNotNull(mine.gems().get(g.id()), g.id());
            total += bp.veins().size();
            gems += bp.gems().size();
        }
        assertEquals(362, total);
        assertEquals(18, gems);
    }

    @Test
    void deeperLevelsLeanToHarderOres() {
        MineDef mine = MineTestData.mine();
        double prev = 0;
        for (MineDef.Level l : mine.levels()) {
            MineBlueprint bp = MineTestData.blueprint(l.n());
            double avg = 0;
            for (MineBlueprint.Node v : bp.veins()) avg += mine.ores().get(v.id()).tier();
            avg /= bp.veins().size();
            assertTrue(avg > prev, l.id() + " 평균 tier " + avg + " > " + prev);
            prev = avg;
        }
        // 가장 깊은 층은 6종 모두, 오리하르콘 몫이 가장 큼
        MineBlueprint deep = MineTestData.blueprint(6);
        Map<String, Integer> c = new HashMap<>();
        for (MineBlueprint.Node v : deep.veins()) c.merge(v.id(), 1, Integer::sum);
        assertEquals(6, c.size());
        String top = c.entrySet().stream().max(Map.Entry.comparingByValue()).orElseThrow().getKey();
        assertEquals("orichalcum_ore", top);
    }

    @Test
    void floorConnectedAndEveryVeinReachable() {
        for (int n = 1; n <= 6; n++) {
            MineBlueprint bp = MineTestData.blueprint(n);
            Set<Long> reach = bp.reachableFloor();
            assertTrue(reach.size() > 300, bp.id + " 바닥 " + reach.size());
            assertEquals(bp.floorCount(), reach.size(), bp.id + " 모든 바닥이 내리는 자리와 이어짐");
            assertEquals(0, bp.unreachable(), bp.id + " 보이지 않거나 손이 닿지 않는 광맥·보석");
        }
    }

    @Test
    void decorationNeverUsesMineBlocks() {
        MineDef mine = MineTestData.mine();
        Set<String> forbidden = new HashSet<>();
        for (MineDef.Node o : mine.ores().values()) forbidden.add(o.block());
        for (MineDef.Node g : mine.gems().values()) forbidden.add(g.block());
        assertEquals(12, forbidden.size(), "광석·보석 블록 12 서로 다름");
        for (MineDef.Level l : mine.levels()) forbidden.add(l.depletedBlock());
        for (int n = 1; n <= 6; n++) {
            Set<String> used = MineTestData.blueprint(n).usedBlocks();
            for (String f : forbidden) assertTrue(!used.contains(f), "L" + n + " 장식·벽에 " + f);
        }
    }

    @Test
    void idsFollowYzxOrder() {
        for (int n = 1; n <= 6; n++) {
            MineBlueprint bp = MineTestData.blueprint(n);
            for (List<MineBlueprint.Node> list : List.of(bp.veins(), bp.gems())) {
                for (int i = 0; i < list.size(); i++) {
                    MineBlueprint.Node a = list.get(i);
                    assertEquals(i, a.index());
                    if (i == 0) continue;
                    MineBlueprint.Node p = list.get(i - 1);
                    long ka = ((long) a.y() << 40) | ((long) (a.z() + 1000) << 20) | (a.x() + 1000);
                    long kp = ((long) p.y() << 40) | ((long) (p.z() + 1000) << 20) | (p.x() + 1000);
                    assertTrue(ka > kp, bp.id + " #" + i + " 차례");
                }
            }
        }
    }

    @Test
    void liftLandingOffice() {
        MineDef mine = MineTestData.mine();
        int offices = 0;
        for (MineDef.Level l : mine.levels()) {
            MineBlueprint bp = MineTestData.blueprint(l.n());
            MineBlueprint.Marker lift = bp.marker("lift");
            MineBlueprint.Marker land = bp.marker("landing");
            assertNotNull(lift, l.id() + " lift");
            assertNotNull(land, l.id() + " landing");
            assertEquals(0, lift.bx());
            assertEquals(0, lift.bz());
            assertEquals(l.floorY() + 1, lift.by());
            assertEquals(0.5, land.pos()[0], 1e-9);
            assertEquals(l.floorY() + 1, land.pos()[1], 1e-9);
            assertEquals(3.5, land.pos()[2], 1e-9);
            assertTrue(bp.standable(land.bx() - bp.ox, land.bz() - bp.oz), l.id() + " 내리는 자리에 설 수 있음");
            offices += bp.markers("office").size();
            if (l.n() == 1) assertEquals(1, bp.markers("office").size(), "관리소 = 얕은 갱도 홀");
        }
        assertEquals(1, offices);
    }

    @Test
    void hashChangesWithContent() {
        String a = "{\"id\":\"t\",\"level\":1,\"size\":[1,1,1],\"origin\":[0,0,0],\"palette\":{\"a\":\"minecraft:stone\"},\"layers\":[[\"a\"]]}";
        String b = a.replace("stone", "andesite");
        MineBlueprint x = MineBlueprint.parse(a), y = MineBlueprint.parse(b);
        assertTrue(!x.sha1.equals(y.sha1));
        assertEquals(1, x.nonKeepCount());
    }

    @Test
    void badBlueprintsRejected() {
        assertThrows(IllegalArgumentException.class, () -> MineBlueprint.parse("{"));
        assertThrows(IllegalArgumentException.class, () -> MineBlueprint.parse("{\"id\":\"t\",\"size\":[1,1,1],\"origin\":[0,0,0],"
                + "\"palette\":{},\"layers\":[[\"z\"]]}"), "팔레트에 없는 글자");
        assertThrows(IllegalArgumentException.class, () -> MineBlueprint.parse("{\"id\":\"t\",\"size\":[1,1,1],\"origin\":[0,0,0],"
                + "\"palette\":{\"a\":\"stone!!\"},\"layers\":[[\"a\"]]}"), "블록 형식");
    }
}
