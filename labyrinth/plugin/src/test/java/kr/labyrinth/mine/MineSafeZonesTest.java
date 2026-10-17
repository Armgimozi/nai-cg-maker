package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.MineDef;
import org.junit.jupiter.api.Test;

/**
 * 0.3.7 광산 PvP 안전 구역 ({@link MineSafeZones}) — jar 청사진 L1..L6 로 직접 센다: 층마다 승강기 홀 + 북쪽 벽감(1층 관리소)과
 * 둘레 3칸만 안전, 둘레 칸은 홀에서 나가는 갱도 입구 세 곳뿐, 바로 밖 한 줄부터 PvP 구역. 청사진은 고치지 않는다.
 */
class MineSafeZonesTest {

    static List<MineSafeZones.Level> levels() {
        List<MineSafeZones.Level> out = new ArrayList<>();
        for (MineDef.Level l : MineTestData.mine().levels()) out.add(MineSafeZones.Level.of(l, MineTestData.blueprint(l.n())));
        return out;
    }

    static MineSafeZones zones() { return MineSafeZones.of(levels(), MineSafeZones.DEFAULT_MARGIN); }

    private static boolean core(int x, int z) {
        return (x >= -5 && x <= 5 && z >= -4 && z <= 4) || (x >= -1 && x <= 1 && z >= -7 && z <= -5);
    }

    /** 홀에서 나가는 갱도 입구 세 곳 (둘레 3칸 · 굽은 칸 하나까지): 서 x −8..−6 · 동 6..8 (z −2..2), 남 z 5..7 (x −2..2). */
    private static boolean mouth(int x, int z) {
        boolean west = x >= -8 && x <= -6 && z >= -2 && z <= 2;
        boolean east = x >= 6 && x <= 8 && z >= -2 && z <= 2;
        boolean south = z >= 5 && z <= 7 && x >= -2 && x <= 2;
        return west || east || south;
    }

    @Test
    void defaultRectIsTheSameOnEveryLevel() {
        MineSafeZones z = zones();
        assertEquals(6, z.levels());
        assertEquals(6, z.rects().size(), "층마다 사각형 하나 (1층 관리소는 벽감 안이라 따로 없음)");
        assertEquals(6, z.count());
        for (MineSafeZones.Rect r : z.rects()) {
            assertEquals("x -8..8 · z -10..7", r.blocks(), "층 " + r.level());
            assertEquals(-8, r.x0());
            assertEquals(9, r.x1());
            assertEquals(-10, r.z0());
            assertEquals(8, r.z1());
        }
    }

    @Test
    void landingLiftAndOfficeAreSafeOnAllLevels() {
        MineSafeZones z = zones();
        for (MineDef.Level l : MineTestData.mine().levels()) {
            MineBlueprint bp = MineTestData.blueprint(l.n());
            double f = l.floorY() + 1;
            MineBlueprint.Marker land = bp.marker("landing");
            assertTrue(z.safe(land.pos()[0], land.pos()[1], land.pos()[2]), l.id() + " 내리는 자리");
            MineBlueprint.Marker lift = bp.marker("lift");
            assertTrue(z.safe(lift.bx() + 0.5, f, lift.bz() + 0.5), l.id() + " 승강기");
            for (MineBlueprint.Marker o : bp.markers(MineNames.MARKER_OFFICE)) assertTrue(z.safe(o.bx() + 0.5, f, o.bz() + 0.5), l.id() + " 관리소");
            if (l.n() == 1) assertEquals(1, bp.markers(MineNames.MARKER_OFFICE).size(), "관리소는 1층 벽감 하나");
        }
    }

    @Test
    void everyStandableHallCellIsSafeAndMarginIsOnlyTheDriftMouths() {
        MineSafeZones z = zones();
        for (MineDef.Level l : MineTestData.mine().levels()) {
            MineBlueprint bp = MineTestData.blueprint(l.n());
            double feet = l.floorY() + 1;
            int hall = 0, margin = 0;
            for (int x = -8; x <= 8; x++) {
                for (int zz = -10; zz <= 7; zz++) {
                    if (!bp.standable(x - bp.ox, zz - bp.oz)) continue;
                    assertTrue(z.safe(x + 0.5, feet, zz + 0.5), l.id() + " (" + x + ", " + zz + ") 안전");
                    // 칸 가장자리까지 (근접 거리로 홀 안을 때리지 못하게 — 서 있는 칸 어디든)
                    assertTrue(z.safe(x + 0.01, feet + 1.5, zz + 0.99), l.id() + " 칸 가장자리");
                    if (core(x, zz)) hall++;
                    else {
                        margin++;
                        assertTrue(mouth(x, zz), l.id() + " 둘레 칸 (" + x + ", " + zz + ") 은 갱도 입구여야 함");
                    }
                }
            }
            assertTrue(hall >= 100 && hall <= 108, l.id() + " 홀·벽감 설 수 있는 칸 " + hall);
            assertTrue(margin >= 27 && margin <= 33, l.id() + " 둘레 칸 " + margin + " (입구 셋 × 9 + 굽은 칸)");
        }
    }

    @Test
    void ringJustOutsideIsPvpGroundAndFarDriftsToo() {
        MineSafeZones z = zones();
        for (MineDef.Level l : MineTestData.mine().levels()) {
            MineBlueprint bp = MineTestData.blueprint(l.n());
            double feet = l.floorY() + 1;
            int ring = 0;
            for (int x = -9; x <= 9; x++) {
                for (int zz = -11; zz <= 8; zz++) {
                    boolean edge = x == -9 || x == 9 || zz == -11 || zz == 8;
                    if (!edge || !bp.standable(x - bp.ox, zz - bp.oz)) continue;
                    ring++;
                    assertTrue(z.pvpGround(x + 0.5, feet, zz + 0.5), l.id() + " (" + x + ", " + zz + ") PvP 구역");
                }
            }
            assertTrue(ring >= 9, l.id() + " 바로 밖 갱도 칸 " + ring + " (입구 셋 × 3)");
            assertTrue(z.pvpGround(0.5, feet, 14.5), l.id() + " 남쪽 갱도 안");
            assertTrue(z.pvpGround(-14.5, feet, 0.5), l.id() + " 서쪽 곁방 쪽");
            assertTrue(z.pvpGround(25.5, feet, 0.5), l.id() + " 끝 채굴장 쪽");
            // 경계: x 8.99 안전 · 9.0 PvP, z 7.99 안전 · 8.0 PvP, x −8.0 안전 · −8.01 PvP
            assertTrue(z.safe(8.99, feet, 0.5));
            assertFalse(z.safe(9.0, feet, 0.5));
            assertTrue(z.safe(0.5, feet, 7.99));
            assertFalse(z.safe(0.5, feet, 8.0));
            assertTrue(z.safe(-8.0, feet, 0.5));
            assertFalse(z.safe(-8.01, feet, 0.5));
            assertTrue(z.safe(0.5, feet, -10.0));
            assertFalse(z.safe(0.5, feet, -10.01));
        }
    }

    @Test
    void wholeLevelHeightAndGapsBetweenLevels() {
        MineSafeZones z = zones();
        for (MineDef.Level l : MineTestData.mine().levels()) {
            List<Integer> b = l.box();
            assertFalse(z.safe(20.5, b.get(1), 0.5), l.id() + " 층 상자 바닥 = PvP 구역");
            assertFalse(z.safe(20.5, b.get(4) + 0.99, 0.5), l.id() + " 층 상자 꼭대기 = PvP 구역");
            assertTrue(z.safe(0.5, b.get(4) + 0.5, 0.5), l.id() + " 홀 위 높이도 같은 사각형");
            assertTrue(z.safe(20.5, b.get(1) - 0.5, 0.5), l.id() + " 층 상자 밑 (층 사이 틈 · 떨어지는 중) = 안전");
            assertTrue(z.safe(20.5, b.get(4) + 1.0, 0.5), l.id() + " 층 상자 위 = 안전");
        }
        assertTrue(z.safe(20.5, 128, 0.5), "1층과 2층 사이");
        assertTrue(z.safe(20.5, 300, 0.5), "하늘");
        assertTrue(z.safe(20.5, -40, 0.5), "공허");
    }

    @Test
    void marginZeroSixteenAndClamp() {
        MineSafeZones zero = MineSafeZones.of(levels(), 0);
        assertEquals("x -5..5 · z -7..4", zero.rects().get(0).blocks(), "둘레 0 = 홀·벽감 그대로");
        assertFalse(zero.safe(-6.5, 136, 0.5), "둘레 0 이면 입구 첫 칸부터 PvP");
        MineSafeZones big = MineSafeZones.of(levels(), 16);
        assertEquals("x -21..21 · z -23..20", big.rects().get(0).blocks());
        assertEquals(16, MineSafeZones.of(levels(), 99).margin());
        assertEquals(0, MineSafeZones.of(levels(), -5).margin());
        assertEquals("x -5..5 · z -7..4", MineSafeZones.of(levels(), -5).rects().get(0).blocks());
    }

    @Test
    void missingLiftMarkerUsesOriginLikeTheLanding() {
        MineSafeZones.Level noLift = new MineSafeZones.Level(1, 131, 151, null, List.of());
        MineSafeZones z = MineSafeZones.of(List.of(noLift), 3);
        assertEquals("x -8..8 · z -10..7", z.rects().get(0).blocks());
        assertTrue(z.safe(0.5, 136, 3.5), "MineLevel.landing 기본 자리 (0.5, F+1, 3.5) 는 안전");
        MineSafeZones moved = MineSafeZones.of(List.of(new MineSafeZones.Level(1, 131, 151, new MineSafeZones.Cell(10, 4), List.of())), 3);
        assertEquals("x 2..18 · z -6..11", moved.rects().get(0).blocks(), "승강기를 옮기면 사각형도 따라감");
    }

    @Test
    void officeOutsideTheHallGetsItsOwnSquare() {
        MineSafeZones.Level l = new MineSafeZones.Level(1, 131, 151, new MineSafeZones.Cell(0, 0),
                List.of(new MineSafeZones.Cell(0, -7), new MineSafeZones.Cell(20, 0)));
        MineSafeZones z = MineSafeZones.of(List.of(l), 3);
        assertEquals(2, z.rects().size(), "벽감 안 관리소는 홀 사각형으로 · 홀 밖 관리소는 따로");
        assertEquals(1, z.count(), "층 수로 셈");
        assertEquals("x 16..24 · z -4..4", z.rects().get(1).blocks(), "관리소 ±1 + 둘레 3");
        assertTrue(z.safe(20.5, 136, 0.5));
        assertFalse(z.safe(12.5, 136, 0.5), "홀과 관리소 사이 갱도는 PvP");
    }

    @Test
    void emptyMeansSafeEverywhere() {
        assertTrue(MineSafeZones.EMPTY.safe(0, 136, 0));
        assertTrue(MineSafeZones.EMPTY.safe(100, 136, 100));
        assertEquals(0, MineSafeZones.EMPTY.count());
    }
}
