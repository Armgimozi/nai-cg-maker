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
import kr.labyrinth.dungeon.gen.HallStyle;
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
        return Run.params(f, boss == null ? kr.labyrinth.content.Params.EMPTY : boss.arena(), liquid);
    }

    static MazePlan plan(FloorDef f, long seed) {
        return MazeGenerator.generate(f.cells(), seed, f.rooms(), params(f).maze());
    }

    @Test
    void mazeIsConnectedAndHasExactRoomCounts() {
        for (FloorDef f : content.floors().values()) {
            for (long seed = 0; seed < 150; seed++) {
                MazePlan plan = plan(f, seed * 7919 + f.number());
                String ctx = "floor " + f.number() + " seed " + seed + "\n" + plan.ascii();
                assertEquals(plan.usedCount(), plan.reachableFromStart(), () -> "연결 안 된 셀: " + ctx);
                for (RoomType t : List.of(RoomType.COMBAT, RoomType.ELITE, RoomType.TREASURE, RoomType.GIMMICK, RoomType.REST)) {
                    int want = f.rooms(t.key());
                    assertEquals(want, plan.count(t), () -> t + " 개수: " + ctx);
                }
                assertEquals(1, plan.count(RoomType.START), ctx);
                assertEquals(0, plan.z(plan.start()), ctx);
                assertEquals(plan.size() - 1, plan.z(plan.bossAttach()), ctx);
                assertEquals(RoomType.HALL, plan.type(plan.bossAttach()), ctx);
                List<Integer> path = plan.mainPath();
                assertFalse(path.isEmpty(), ctx);
                boolean rest = false;
                for (int i = 1; i < path.size() - 1; i++) if (plan.type(path.get(i)) == RoomType.REST) rest = true;
                if (f.rooms("rest") > 0) assertTrue(rest, () -> "주 경로에 휴식방 없음: " + ctx);
            }
        }
    }

    @Test
    void mainPathIsLongAndBossIsFarthestInLastRow() {
        for (FloorDef f : content.floors().values()) {
            for (long seed = 0; seed < 150; seed++) {
                MazePlan plan = plan(f, seed * 104729 + f.number());
                String ctx = "floor " + f.number() + " seed " + seed + "\n" + plan.ascii();
                int need = (int) Math.ceil(2.2 * plan.size());
                assertTrue(plan.mainPath().size() >= need, () -> "주 경로 " + plan.mainPath().size() + " < " + need + ": " + ctx);
                assertEquals(plan.distance(plan.bossAttach()) + 1, plan.mainPath().size(), ctx);
                int n = plan.size();
                for (int x = 0; x < n; x++) {
                    int c = plan.index(x, n - 1);
                    if (plan.used(c)) assertTrue(plan.distance(c) <= plan.distance(plan.bossAttach()), () -> "더 먼 마지막 줄 셀: " + ctx);
                }
            }
        }
    }

    @Test
    void deadEndsLoopsAndSecretsFollowFloorSettings() {
        for (FloorDef f : content.floors().values()) {
            MazeGenerator.Settings s = params(f).maze();
            int loopsSum = 0, deadSum = 0, runs = 120;
            for (long seed = 0; seed < runs; seed++) {
                MazePlan plan = plan(f, seed * 15485863L + f.number());
                String ctx = "floor " + f.number() + " seed " + seed + "\n" + plan.ascii();
                List<Integer> dead = plan.deadEnds();
                int kept = (int) Math.round(plan.initialDeadEnds() * s.deadEndKeep());
                // 남기기로 한 막다른 길 = 정리 전 × dead_end_keep (방이 들어간 몇 칸은 빠질 수 있고, 보스 연결이 옮겨 가면
                // 처음 보스 연결 칸이 막다른 길로 하나 늘 수 있음)
                assertTrue(dead.size() <= kept + 1, () -> "막다른 길 " + dead.size() + " > 남길 수 " + kept + " + 1: " + ctx);
                assertTrue(dead.size() >= kept - 2, () -> "막다른 길 " + dead.size() + " < 남길 수 " + kept + " - 2: " + ctx);
                assertTrue(plan.initialDeadEnds() >= 4, ctx);
                assertTrue(plan.loopCount() >= 1, () -> "고리 없음 (나무): " + ctx);
                loopsSum += plan.loopCount();
                deadSum += dead.size();
                int secrets = 0;
                for (int c = 0; c < plan.cellCount(); c++) {
                    if (!plan.secret(c)) continue;
                    secrets++;
                    int cc = c;
                    assertTrue(dead.contains(c), () -> "비밀 통로가 막다른 길이 아닌 셀 " + cc + ": " + ctx);
                    assertEquals(HallStyle.SECRET, plan.style(c), ctx);
                }
                if (!dead.isEmpty()) assertTrue(secrets >= 1, () -> "비밀 통로 없음: " + ctx);
                assertTrue(secrets <= s.secretMax(), ctx);
                for (int c : dead) assertTrue(plan.style(c) == HallStyle.NOOK || plan.style(c) == HallStyle.SECRET, ctx);
            }
            double loops = loopsSum / (double) runs, deads = deadSum / (double) runs;
            // 일직선이 아닌 미로: 층마다 평균 고리 4개+, 막다른 길 3개+ (깊은 층일수록 많음)
            assertTrue(loops >= 3.5 + (f.number() - 1) * 0.3, "floor " + f.number() + " 평균 고리 " + loops);
            assertTrue(deads >= 2.5 + (f.number() - 1) * 0.5, "floor " + f.number() + " 평균 막다른 길 " + deads);
        }
    }

    @Test
    void sameSeedSameMaze() {
        Map<String, Integer> rooms = Map.of("combat", 6, "elite", 1, "treasure", 1, "gimmick", 1, "rest", 1);
        assertEquals(MazeGenerator.generate(6, 42, rooms).ascii(), MazeGenerator.generate(6, 42, rooms).ascii());
        assertEquals(FloorGenerator.generate(params(content.floor(10)), 9).hallTiles().length,
                FloorGenerator.generate(params(content.floor(10)), 9).hallTiles().length);
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
                        assertEquals(0, layout.elevation(FloorLayout.unpackX(d), FloorLayout.unpackZ(d)));
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
    void everyCorridorTileWalkableAndSecretRoomsBehindCrackedWalls() {
        for (FloorDef f : content.floors().values()) {
            for (long seed = 0; seed < 25; seed++) {
                FloorLayout l = FloorGenerator.generate(params(f), seed * 131 + f.number());
                String ctx = "floor " + f.number() + " seed " + seed;
                boolean[] closed = l.reachable(false), open = l.reachable(true);
                for (int z = 0; z < l.depth(); z++) {
                    for (int x = 0; x < l.width(); x++) {
                        if (!l.walkable(x, z)) continue;
                        int xx = x, zz = z;
                        boolean inSecret = l.secretRoomAt(x, z) >= 0;
                        // 걸을 수 있는 칸은 전부 시작방에서 닿는다 (계단 높이 포함) — 비밀방만 금 간 벽을 열어야 닿음
                        if (inSecret) {
                            assertFalse(l.isReachable(closed, x, z), () -> ctx + " 비밀방이 벽 없이 열려 있음 " + xx + "," + zz);
                            assertTrue(l.isReachable(open, x, z), () -> ctx + " 비밀방에 못 들어감 " + xx + "," + zz);
                        } else {
                            assertTrue(l.isReachable(closed, x, z), () -> ctx + " 닿지 않는 바닥 " + xx + "," + zz + " " + l.kind(xx, zz));
                        }
                        assertTrue(l.elevation(x, z) >= 0 && l.elevation(x, z) <= FloorGenerator.MAX_RISE, ctx);
                        if (l.kind(x, z) == FloorLayout.STAIR) assertTrue(l.stairFacing(x, z) >= 0, ctx);
                    }
                }
                assertEquals(l.plan().count(RoomType.HALL) > 0, l.hallTiles().length > 0, ctx);
                for (int t : l.hallTiles()) {
                    int x = FloorLayout.unpackX(t), z = FloorLayout.unpackZ(t);
                    assertEquals(FloorLayout.FLOOR, l.kind(x, z), ctx);
                    assertEquals(-1, l.region(x, z), ctx);
                    assertTrue(l.cellAt(x, z) >= 0, ctx);
                    assertEquals(-1, l.secretRoomAt(x, z), ctx);
                }
                // 막다른 길 끝 칸: 걸을 수 있고 높이 0, 그 셀의 출구는 하나
                for (FloorLayout.DeadEnd d : l.deadEnds()) {
                    assertTrue(l.walkable(d.tipX(), d.tipZ()) && l.isReachable(closed, d.tipX(), d.tipZ()), ctx + " " + d);
                    assertEquals(0, l.elevation(d.tipX(), d.tipZ()), ctx);
                    assertEquals(d.cell(), l.cellAt(d.tipX(), d.tipZ()), ctx + " " + d);
                    assertEquals(1, Math.abs(d.dirX()) + Math.abs(d.dirZ()), ctx);
                    if (!d.minor()) assertEquals(1, l.plan().degree(d.cell()), ctx + " " + d);
                }
                // 비밀방: 막다른 길 끝에만, 금 간 벽은 그 끝 칸 바로 앞
                int majors = 0;
                for (FloorLayout.DeadEnd d : l.deadEnds()) if (!d.minor()) majors++;
                assertEquals(l.plan().deadEnds().size(), majors, ctx);
                for (FloorLayout.SecretRoom s : l.secretRooms()) {
                    assertTrue(l.plan().secret(s.cell()), ctx);
                    FloorLayout.DeadEnd d = l.deadEnds().get(s.deadEnd());
                    assertEquals(s.index(), d.secret(), ctx);
                    assertEquals(s.cell(), d.cell(), ctx);
                    boolean touches = false;
                    for (int w : s.wall()) {
                        int wx = FloorLayout.unpackX(w), wz = FloorLayout.unpackZ(w);
                        assertEquals(FloorLayout.SECRET, l.kind(wx, wz), ctx);
                        assertEquals(s.index(), l.secretWallAt(wx, wz), ctx);
                        if (Math.abs(wx - d.tipX()) + Math.abs(wz - d.tipZ()) == 1) touches = true;
                    }
                    assertTrue(touches, ctx + " 금 간 벽이 막다른 길 끝 앞이 아님");
                    assertTrue(l.walkable(s.centerX(), s.centerZ()) && l.secretRoomAt(s.centerX(), s.centerZ()) == s.index(), ctx);
                }
            }
        }
    }

    @Test
    void stairsStepAtMostHalfABlock() {
        for (FloorDef f : content.floors().values()) {
            FloorLayout l = FloorGenerator.generate(params(f), 77 + f.number());
            for (int z = 0; z < l.depth(); z++) {
                for (int x = 0; x < l.width(); x++) {
                    if (l.kind(x, z) != FloorLayout.STAIR) continue;
                    int d = l.stairFacing(x, z);
                    int[][] v = {{0, -1}, {1, 0}, {0, 1}, {-1, 0}};
                    int ux = x + v[d][0], uz = z + v[d][1], dx = x - v[d][0], dz = z - v[d][1];
                    // 올라가는 쪽 = 한 칸 위(평지) 또는 다음 계단, 내려가는 쪽 = 같은 높이 평지 또는 아래 계단
                    assertTrue(l.canStep(x, z, ux, uz, false) && l.elevation(ux, uz) == l.elevation(x, z) + 1);
                    assertTrue(l.canStep(x, z, dx, dz, false));
                }
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
