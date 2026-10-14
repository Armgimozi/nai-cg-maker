package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.bukkit.block.structure.StructureRotation;
import org.junit.jupiter.api.Test;

class RotationTest {

    @Test
    void coordinateFormulaAllFourRotations() {
        int w = 5, d = 3; // 정방향 W×D
        assertArrayEquals(new int[] {1, 2}, Rot.inBox(1, 2, w, d, 0));
        assertArrayEquals(new int[] {d - 1 - 2, 1}, Rot.inBox(1, 2, w, d, 1));
        assertArrayEquals(new int[] {w - 1 - 1, d - 1 - 2}, Rot.inBox(1, 2, w, d, 2));
        assertArrayEquals(new int[] {2, w - 1 - 1}, Rot.inBox(1, 2, w, d, 3));
        assertArrayEquals(new int[] {5, 3}, Rot.dims(w, d, 0));
        assertArrayEquals(new int[] {3, 5}, Rot.dims(w, d, 1));
        assertArrayEquals(new int[] {5, 3}, Rot.dims(w, d, 2));
        assertArrayEquals(new int[] {3, 5}, Rot.dims(w, d, 3));
        for (int t = 0; t < 4; t++) {
            int[] dm = Rot.dims(w, d, t);
            Set<Long> seen = new HashSet<>();
            for (int z = 0; z < d; z++) {
                for (int x = 0; x < w; x++) {
                    int[] r = Rot.inBox(x, z, w, d, t);
                    assertTrue(r[0] >= 0 && r[1] >= 0 && r[0] < dm[0] && r[1] < dm[1], "회전 " + t + " 상자 안");
                    assertTrue(seen.add(((long) r[0] << 32) | r[1]), "회전 " + t + " 겹침 없음");
                }
            }
        }
        assertEquals(StructureRotation.CLOCKWISE_90, Rot.forFront(Dir.EAST));
        assertEquals(StructureRotation.CLOCKWISE_180, Rot.forFront(Dir.SOUTH));
        assertEquals(StructureRotation.COUNTERCLOCKWISE_90, Rot.forFront(Dir.WEST));
        for (StructureRotation r : StructureRotation.values()) assertEquals(r, Rot.of(Rot.turns(r)));
    }

    /** §2.1 검산: 정방향 앞줄 가운데 문(북향)은 CW90 뒤 x=D−1(동쪽 끝)에서 동쪽을 본다. */
    @Test
    void frontDoorFollowsRotationWithFacing() {
        Blueprint hut = Fixtures.piece("hut");
        String door = hut.state('d');
        Dir[] expect = {Dir.NORTH, Dir.EAST, Dir.SOUTH, Dir.WEST};
        int[][] pos = {{2, 0}, {hut.d - 1, 2}, {2, hut.d - 1}, {0, 2}};
        for (int t = 0; t < 4; t++) {
            assertArrayEquals(pos[t], Rot.inBox(2, 0, hut.w, hut.d, t), "문 좌표 회전 " + t);
            Map<String, String> p = Rot.props(Rot.rotateState(door, t));
            assertEquals(expect[t].key(), p.get("facing"), "문 facing 회전 " + t);
            assertEquals("lower", p.get("half"));
            assertEquals("left", p.get("hinge"), "hinge 는 상대 속성이라 그대로");
            // 문이 바라보는 쪽 = 상자 밖 (정문 앞 칸)
            Plan.Placed pl = new Plan.Placed(new Layout.Entry(0, "hut", 0, 0, Dir.NORTH, null, null), hut, t, 100, 200);
            int[] doorW = pl.world(2, 0), front = pl.doorFront();
            assertEquals(doorW[0] + expect[t].dx, front[0]);
            assertEquals(doorW[1] + expect[t].dz, front[1]);
            assertEquals(expect[t], pl.front());
        }
    }

    @Test
    void stateRotationAxisConnectionsRotationAndRails() {
        assertEquals("z", Rot.props(Rot.rotateState("minecraft:oak_log[axis=x]", 1)).get("axis"));
        assertEquals("x", Rot.props(Rot.rotateState("minecraft:oak_log[axis=x]", 2)).get("axis"));
        assertEquals("y", Rot.props(Rot.rotateState("minecraft:oak_log[axis=y]", 3)).get("axis"));
        Map<String, String> f = Rot.props(Rot.rotateState("minecraft:oak_fence[east=true,north=false,south=false,waterlogged=false,west=true]", 1));
        assertEquals("true", f.get("south"));
        assertEquals("true", f.get("north"));
        assertEquals("false", f.get("east"));
        assertEquals("false", f.get("waterlogged"));
        Map<String, String> wall = Rot.props(Rot.rotateState("minecraft:cobblestone_wall[east=low,north=tall,south=none,up=true,waterlogged=false,west=none]", 1));
        assertEquals("tall", wall.get("east"));
        assertEquals("low", wall.get("south"));
        assertEquals("true", wall.get("up"));
        assertEquals("8", Rot.props(Rot.rotateState("minecraft:oak_sign[rotation=4,waterlogged=false]", 1)).get("rotation"));
        assertEquals("2", Rot.props(Rot.rotateState("minecraft:white_banner[rotation=14]", 1)).get("rotation"));
        assertEquals("south_east", Rot.props(Rot.rotateState("minecraft:rail[shape=north_east]", 1)).get("shape"));
        assertEquals("east_west", Rot.props(Rot.rotateState("minecraft:rail[shape=north_south]", 3)).get("shape"));
        assertEquals("ascending_south", Rot.props(Rot.rotateState("minecraft:rail[shape=ascending_east]", 1)).get("shape"));
        assertEquals("inner_left", Rot.props(Rot.rotateState("minecraft:oak_stairs[facing=north,half=bottom,shape=inner_left]", 1)).get("shape"));
        assertEquals("east", Rot.props(Rot.rotateState("minecraft:oak_stairs[facing=north,half=bottom,shape=inner_left]", 1)).get("facing"));
        assertEquals("down", Rot.props(Rot.rotateState("minecraft:hopper[facing=down]", 1)).get("facing"));
        assertEquals("minecraft:stone", Rot.rotateState("minecraft:stone", 1));
        // 일부만 적힌 연결 속성 (덩굴)
        Map<String, String> vine = Rot.props(Rot.rotateState("minecraft:vine[north=true,up=false]", 1));
        assertEquals("true", vine.get("east"));
        assertEquals(null, vine.get("north"));
    }

    @Test
    void villageRotationAroundCenter() {
        assertArrayEquals(new int[] {22, 0}, Rot.around(0, -22, 1), "북쪽 게이트 → 동쪽");
        assertArrayEquals(new int[] {0, 22}, Rot.around(0, -22, 2));
        assertArrayEquals(new int[] {-22, 0}, Rot.around(0, -22, 3));
        for (Dir dir : Dir.values()) assertEquals(dir, dir.rotate(4));
        assertEquals(Dir.EAST, Dir.NORTH.rotate(1));
        assertEquals(180f, Dir.NORTH.yaw());
        assertEquals(-90f, Dir.EAST.yaw());
        assertEquals(0f, Dir.SOUTH.yaw());
        assertEquals(90f, Dir.WEST.yaw());
    }

    @Test
    void wholeVillageRotationRotatesPiecePositionsAndFronts() {
        VillageLibrary lib = Fixtures.library();
        TerrainGrid flat = Fixtures.flat(80, 64);
        Plan base = lib.planner.plan(flat, 0, 0, 0, false);
        assertTrue(base.ok(), base.reason);
        for (int t = 1; t < 4; t++) {
            Plan p = lib.planner.plan(flat, 0, 0, t, false);
            assertTrue(p.ok(), p.reason);
            for (int i = 0; i < base.pieces.size(); i++) {
                Plan.Placed a = base.pieces.get(i), b = p.pieces.get(i);
                assertEquals(a.front().rotate(t), b.front(), "조각 " + i + " 정면");
                int[] ca = a.anchor(), cb = b.anchor();
                assertArrayEquals(Rot.around(ca[0], ca[1], t), cb, "조각 " + i + " anchor 가 중심 둘레로 회전");
            }
        }
    }
}
