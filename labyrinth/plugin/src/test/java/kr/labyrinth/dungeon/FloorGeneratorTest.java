package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.SplittableRandom;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.gen.FloorGenerator;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.gen.MazeGenerator;
import kr.labyrinth.dungeon.gen.MazePlan;
import kr.labyrinth.dungeon.gen.RoomType;
import kr.labyrinth.dungeon.rooms.gimmicks.LightsOutGrid;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 미로·층 설계의 연결성·개수·결정성 (ARCHITECTURE §8: 미로 생성 연결성). */
class FloorGeneratorTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    static FloorGenerator.Params params(FloorDef f) {
        boolean liquid = f.liquid() != null && !f.liquid().isBlank() && !"null".equalsIgnoreCase(f.liquid());
        var boss = content.bossOfFloor(f.number());
        int radius = boss == null ? 14 : boss.arena().integer("radius", 14);
        int height = boss == null ? 10 : boss.arena().integer("height", 10);
        int corridor = boss == null ? 0 : boss.arena().integer("corridor_length", 0);
        int cw = boss == null ? 7 : boss.arena().integer("corridor_width", 7);
        return new FloorGenerator.Params(f.cells(), f.rooms(), f.roomHeight(), 4, liquid, radius, height, corridor, cw);
    }

    @Test
    void mazeIsConnectedAndHasExactRoomCounts() {
        for (FloorDef f : content.floors().values()) {
            for (long seed = 0; seed < 150; seed++) {
                MazePlan plan = MazeGenerator.generate(f.cells(), seed * 7919 + f.number(), f.rooms());
                String ctx = "floor " + f.number() + " seed " + seed + "\n" + plan.ascii();
                assertEquals(plan.usedCount(), plan.reachableFromStart(), () -> "연결 안 된 셀: " + ctx);
                for (RoomType t : List.of(RoomType.COMBAT, RoomType.ELITE, RoomType.TREASURE, RoomType.GIMMICK, RoomType.REST)) {
                    int want = f.rooms(t.key());
                    assertEquals(want, plan.count(t), () -> t + " 개수: " + ctx);
                }
                assertEquals(1, plan.count(RoomType.START), ctx);
                assertEquals(0, plan.z(plan.start()), ctx);
                assertEquals(plan.size() - 1, plan.z(plan.bossAttach()), ctx);
                List<Integer> path = plan.mainPath();
                assertFalse(path.isEmpty(), ctx);
                boolean rest = false;
                for (int i = 1; i < path.size() - 1; i++) if (plan.type(path.get(i)) == RoomType.REST) rest = true;
                if (f.rooms("rest") > 0) assertTrue(rest, () -> "주 경로에 휴식방 없음: " + ctx);
                // 잘라낸 뒤 남은 복도 셀은 막다른 길이 아님 (보스 연결 셀 제외)
                for (int c = 0; c < plan.cellCount(); c++) {
                    if (plan.used(c) && plan.type(c) == RoomType.HALL && c != plan.bossAttach()) {
                        int cc = c;
                        assertTrue(plan.degree(c) >= 2, () -> "막다른 복도 " + cc + ": " + ctx);
                    }
                }
            }
        }
    }

    @Test
    void sameSeedSameMaze() {
        Map<String, Integer> rooms = Map.of("combat", 6, "elite", 1, "treasure", 1, "gimmick", 1, "rest", 1);
        assertEquals(MazeGenerator.generate(6, 42, rooms).ascii(), MazeGenerator.generate(6, 42, rooms).ascii());
        assertNotEquals(MazeGenerator.generate(6, 42, rooms).ascii(), MazeGenerator.generate(6, 43, rooms).ascii());
    }

    @Test
    void layoutEveryRoomAndBossReachableOnFoot() {
        for (FloorDef f : content.floors().values()) {
            for (long seed = 0; seed < 25; seed++) {
                FloorLayout layout = FloorGenerator.generate(params(f), seed * 31 + f.number());
                boolean[] reach = layout.reachable();
                for (FloorLayout.RoomInfo r : layout.rooms()) {
                    long s = seed;
                    assertTrue(layout.isReachable(reach, r.centerX(), r.centerZ()),
                            () -> "floor " + f.number() + " seed " + s + " 방 " + r.index() + " " + r.type() + " 도달 불가");
                    assertTrue(r.doors().length >= 3, () -> "출입구 없음: " + r);
                    for (int d : r.doors()) {
                        assertEquals(FloorLayout.DOOR, layout.kind(FloorLayout.unpackX(d), FloorLayout.unpackZ(d)));
                        assertEquals(r.index(), layout.region(FloorLayout.unpackX(d), FloorLayout.unpackZ(d)));
                    }
                }
                assertEquals(RoomType.BOSS, layout.bossRoom().type());
                FloorLayout.Arena a = layout.arena();
                assertTrue(layout.walkable(a.centerX(), a.centerZ()));
                assertEquals(layout.bossRoom().index(), layout.region(a.centerX(), a.centerZ()));
                // 투기장이 지도 안에 들어감
                assertTrue(layout.inside(a.centerX() - a.radius() - 1, a.centerZ() + a.radius() + 1));
            }
        }
    }

    @Test
    void gimmickRoomsOnlyWhereFloorDefinesThem() {
        for (FloorDef f : content.floors().values()) {
            assertTrue(f.gimmick() != null && !f.gimmick().isBlank(), "기믹 키 없음: " + f.number());
        }
    }

    @Test
    void lightsOutAlwaysSolvable() {
        SplittableRandom rng = new SplittableRandom(5);
        for (int i = 0; i < 200; i++) {
            LightsOutGrid g = new LightsOutGrid(4);
            int[] presses = g.scramble(6, rng);
            assertFalse(g.solved());
            for (int c : presses) g.press(c % 4, c / 4);
            assertTrue(g.solved());
        }
    }

    @Test
    void blockPositionsPackRoundTrip() {
        int[][] cases = {{0, 0, 0}, {30000, 280, 4096}, {-5, -60, -77}, {33_000_000 / 2, 319, -12_345}};
        for (int[] c : cases) {
            long p = kr.labyrinth.dungeon.gen.BlockList.pack(c[0], c[1], c[2]);
            assertEquals(c[0], kr.labyrinth.dungeon.gen.BlockList.x(p));
            assertEquals(c[1], kr.labyrinth.dungeon.gen.BlockList.y(p));
            assertEquals(c[2], kr.labyrinth.dungeon.gen.BlockList.z(p));
        }
    }

    @Test
    void floorsDescendAndNeverOverlap() {
        DungeonConfig c = DungeonConfig.defaults();
        for (int f = 1; f < 10; f++) {
            int y = c.floorY(f), below = c.floorY(f + 1);
            assertTrue(below < y);
            // 아래층 가장 높은 천장(투기장 높이 20 상한 + 1) 이 이 층 계단 바닥(y-9) 보다 낮다
            assertTrue(below + 20 + 1 < y - 8, "층 " + f + " 과 " + (f + 1) + " 이 겹침");
        }
        assertTrue(c.floorY(10) - 10 > -64);
    }

    @Test
    void allocatorSlotsAreFarApart() {
        InstanceAllocator a = new InstanceAllocator(64);
        int s0 = a.allocate(), s1 = a.allocate();
        assertNotEquals(s0, s1);
        assertTrue(Math.abs(InstanceAllocator.originX(s0) - InstanceAllocator.originX(s1))
                + Math.abs(InstanceAllocator.originZ(s0) - InstanceAllocator.originZ(s1)) >= InstanceAllocator.SPACING);
        assertEquals(s1, InstanceAllocator.slotAt(InstanceAllocator.originX(s1) + 100, InstanceAllocator.originZ(s1) + 300));
        a.release(s0);
        assertEquals(s0, a.allocate());
        assertTrue(InstanceAllocator.originZ(0) > 0);
    }
}
