package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/** 마커 회전 + labyrinth-village.yml 왕복. */
class MetaRoundTripTest {

    @Test
    void markerPositionsAndFacesRotateWithPiece() {
        Blueprint hut = Fixtures.piece("hut");
        Layout.Entry e = new Layout.Entry(0, "hut", 0, 0, Dir.NORTH, null, null);
        // npc pos [2, 2, 2] face front, floor_y 1
        Dir[] faces = {Dir.NORTH, Dir.EAST, Dir.SOUTH, Dir.WEST};
        for (int t = 0; t < 4; t++) {
            Plan.Placed pl = new Plan.Placed(e, hut, t, 10, 20);
            pl.floor = 70;
            int[] w = Markers.world(pl, new int[] {2, 2, 2});
            int[] xz = Rot.inBox(2, 2, 5, 5, t);
            assertArrayEquals(new int[] {10 + xz[0], 71, 20 + xz[1]}, w, "회전 " + t);
            assertEquals(faces[t], Markers.face(pl, "front"));
            assertEquals(faces[t].rotate(3), Markers.face(pl, "left"), "left = 정방향 서쪽");
            assertEquals(faces[t].rotate(1), Markers.face(pl, "right"));
            assertEquals(faces[t].opposite(), Markers.face(pl, "back"));
        }
        // interact 첫 칸 [1, 2, 3] → CW90: (D−1−3, 1)
        Plan.Placed pl = new Plan.Placed(e, hut, 1, 0, 0);
        pl.floor = 64;
        assertArrayEquals(new int[] {1, 65, 1}, Markers.world(pl, new int[] {1, 2, 3}));
    }

    @Test
    void metadataRoundTrips() throws Exception {
        VillageLibrary lib = Fixtures.library();
        TerrainGrid g = Fixtures.flat(80, 64);
        for (int z = 5; z <= 9; z++) for (int x = -20; x <= -14; x++) g.setGround(x, z, 66);
        Plan p = lib.planner.plan(g, 3, -2, 1, true);
        assertTrue(p.ok(), p.reason);
        VillageMeta m = Markers.meta(p, lib.layout);
        m.buildId = "test-build";
        m.builtAt = "2026-10-14T00:00:00Z";
        assertNotNull(m.spawn);
        assertNotNull(m.entrance);
        assertEquals(2, m.npcs.size(), "blacksmith(오두막 둘 → 하나로) + guide");
        assertEquals(4, m.interact.size(), "오두막 2채 × interact 2칸");
        assertEquals(3, m.ambient.size(), "오두막 불씨 2 + 광장 분수 1");
        assertTrue(m.protect.size() >= 4);
        assertEquals("CLOCKWISE_90", m.rotation);

        String yaml = m.toYaml();
        VillageMeta r = VillageMeta.fromYaml(yaml);
        assertEquals(m.name, r.name);
        assertArrayEquals(m.center, r.center);
        assertEquals(m.rotation, r.rotation);
        assertEquals(m.spawn, r.spawn);
        assertEquals(m.entrance, r.entrance);
        assertEquals(m.npcs, r.npcs);
        assertEquals(m.interact, r.interact);
        assertEquals(m.ambient, r.ambient);
        assertEquals(m.protect, r.protect);
        assertEquals(m.pieces, r.pieces);
        assertEquals(m.paths.size(), r.paths.size());
        for (int i = 0; i < m.paths.size(); i++) {
            VillageMeta.PathRec a = m.paths.get(i), b = r.paths.get(i);
            assertEquals(a.cells().size(), b.cells().size());
            for (int k = 0; k < a.cells().size(); k++) assertArrayEquals(a.cells().get(k), b.cells().get(k));
            assertEquals(a.attachA(), b.attachA());
            assertEquals(a.width(), b.width());
        }
        assertEquals("test-build", r.buildId);
        assertEquals("test-build", r.villageKey());
        VillageMeta.TerrainRec ta = m.terrain, tb = r.terrain;
        assertNotNull(tb);
        assertEquals(ta.n(), tb.n());
        for (int z = ta.z0(); z < ta.z0() + ta.n(); z += 7) {
            for (int x = ta.x0(); x < ta.x0() + ta.n(); x += 7) {
                assertEquals(ta.height(x, z), tb.height(x, z));
                assertEquals(ta.changed(x, z), tb.changed(x, z));
                assertEquals(p.target(x, z), tb.height(x, z));
            }
        }
        // 메타데이터 → 놓인 조각 복원 → 같은 발자국, 겹침 없음
        List<Plan.Placed> back = new java.util.ArrayList<>();
        for (VillageMeta.PieceRec pr : r.pieces) back.add(Markers.placed(pr, lib.layout, lib.pieces));
        List<Plan.PathPlan> paths = new java.util.ArrayList<>();
        for (VillageMeta.PathRec pr : r.paths) paths.add(Markers.path(pr));
        assertTrue(Planner.overlaps(back, paths).isEmpty());
        for (int i = 0; i < back.size(); i++) {
            assertArrayEquals(p.pieces.get(i).anchor(), back.get(i).anchor());
            assertEquals(p.pieces.get(i).floor, back.get(i).floor);
        }
    }
}
