package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/** bs362: 보스 기본 공격 닿음 — 히트박스 겉면 거리(맞대응) · 옛 규칙 · 시야 · 도약 궤적 수학. */
class BossReachTest {

    /** 1층 그로브 히트박스 (철 골렘 2.24 × 4.32, SCALE 1.6) 를 원점에. */
    private static final BossReach.Box GOLEM = BossReach.Box.of(0, 0, 0, 1.12, 4.32);
    /** 1층 옛 reach = 2.0 + 0.7 × 1.6. */
    private static final double R1 = 2.0 + 0.7 * 1.6;
    private static final double EYE = 1.62;

    private static boolean hits(double px, double py, double pz, BossReach.Box b, double reach, double slack) {
        double eyeBox = BossReach.pointToBox(px, py + EYE, pz, b);
        double cx = (b.minX() + b.maxX()) / 2, cz = (b.minZ() + b.maxZ()) / 2;
        return BossReach.inReach(Math.hypot(px - cx, pz - cz), py - b.minY(), reach, eyeBox, BossReach.PLAYER_REACH, slack);
    }

    @Test
    void pointToBoxMatchesVanillaReachRule() {
        assertEquals(0, BossReach.pointToBox(0.5, 1, 0.5, GOLEM), 1e-9); // 안
        assertEquals(1.88, BossReach.pointToBox(3.0, 1.62, 0, GOLEM), 1e-9); // 옆면
        assertEquals(Math.hypot(1.0, 1.0), BossReach.pointToBox(2.12, 1.0, 2.12, GOLEM), 1e-9); // 모서리 (수평)
        assertEquals(Math.hypot(1.0, 2.0), BossReach.pointToBox(2.12, 6.32, 0, GOLEM), 1e-9); // 위로 비스듬히
        double[] cp = BossReach.closestPoint(5, 9, -1, GOLEM);
        assertEquals(1.12, cp[0], 1e-9);
        assertEquals(4.32, cp[1], 1e-9);
        assertEquals(-1, cp[2], 1e-9);
    }

    @Test
    void mirrorClosesTheMeleeBandOfBigHitboxes() {
        // 옛 규칙만으로는 중심 3.12칸까지 — 플레이어 칼은 겉면 3.0칸 = 중심 4.12칸까지 닿았다 (그 띠가 무적 자리)
        assertTrue(BossReach.legacy(3.1, 0, R1));
        assertFalse(BossReach.legacy(3.5, 0, R1));
        assertTrue(hits(3.5, 0, 0, GOLEM, R1, 0), "플레이어가 칠 수 있으면 보스도 친다");
        assertTrue(hits(4.1, 0, 0, GOLEM, R1, 0));
        assertFalse(hits(4.2, 0, 0, GOLEM, R1, 0), "플레이어 칼이 안 닿는 거리는 그대로 안전");
        // 대각선 (모서리): 겉면까지 3.0
        double diag = 1.12 + 3.0 / Math.sqrt(2) - 0.01;
        assertTrue(hits(diag, 0, diag, GOLEM, R1, 0));
        assertFalse(hits(diag + 0.05, 0, diag + 0.05, GOLEM, R1, 0));
    }

    @Test
    void ownerSpotOnFloorOneIsNowInReach() {
        // 실서버 재현: 보스 중심에서 3.49칸, 봇 눈 → 히트박스 1.94칸 → 옛 규칙 0번, 이제는 닿는다
        double d = 3.49;
        assertFalse(BossReach.legacy(d, 0, R1));
        double eyeBox = BossReach.pointToBox(d, EYE, 0, GOLEM);
        assertTrue(eyeBox < 3.0);
        assertTrue(BossReach.inReach(d, 0, R1, eyeBox, BossReach.PLAYER_REACH, 0));
    }

    @Test
    void confirmSlackMatchesOldRule() {
        // 3틱 뒤 판정: 옛 규칙은 reach + 0.8, 맞대응도 + 0.8
        assertTrue(hits(4.8, 0, 0, GOLEM, R1, BossReach.CONFIRM_SLACK));
        assertFalse(hits(5.0, 0, 0, GOLEM, R1, BossReach.CONFIRM_SLACK));
        assertTrue(BossReach.legacy(R1 + 0.8, 0, R1 + 0.8));
    }

    @Test
    void smallHitboxKeepsOldReachWhereItIsLonger() {
        // 4층 허스크 (1.14 × 3.71, scale 1.9): 옛 3.33 · 맞대응 0.57 + 3.0 = 3.57 — 어느 쪽이든 짧아지지 않는다
        BossReach.Box husk = BossReach.Box.of(0, 0, 0, 0.57, 3.71);
        double r4 = 2.0 + 0.7 * 1.9;
        assertTrue(hits(3.3, 0, 0, husk, r4, 0));
        assertTrue(hits(3.55, 0, 0, husk, r4, 0));
        assertFalse(hits(3.6, 0, 0, husk, r4, 0));
        // 높이: 옛 규칙은 발 높이 차 3.5 미만
        assertFalse(BossReach.legacy(1.0, 3.5, r4));
        assertTrue(BossReach.legacy(1.0, 3.4, r4));
    }

    @Test
    void standingOnTopOfSomethingIsMirrored() {
        // 5칸 기둥 위 (발 +5, 눈 +6.62), 히트박스 겉면에서 수평 1.5칸: 눈 → 상자 = √(1.5² + 2.3²) ≈ 2.75 → 서로 닿음
        assertTrue(hits(1.12 + 1.5, 5, 0, GOLEM, R1, 0));
        // 더 높으면 (발 +7) 칼이 안 닿으니 보스도 안 닿음 (거리 좁히기가 맡는다)
        assertFalse(hits(1.12 + 1.5, 7, 0, GOLEM, R1, 0));
        // 옛 규칙은 높이 차 5 라서 못 쳤다
        assertFalse(BossReach.legacy(2.62, 5, R1));
    }

    @Test
    void playerReachAttributeNeverShrinksBelowVanilla() {
        assertEquals(3.0, BossReach.playerReach(Double.NaN), 1e-9);
        assertEquals(3.0, BossReach.playerReach(2.0), 1e-9);
        assertEquals(4.5, BossReach.playerReach(4.5), 1e-9);
    }

    // ── 시야 ─────────────────────────────────────────────────────────────

    /** x = wallX 에 높이 wallTop 까지의 벽 (z 무한). */
    private static BossReach.Ray wall(double wallX, double wallTop) {
        return (ax, ay, az, bx, by, bz) -> {
            if ((ax - wallX) * (bx - wallX) > 0) return true; // 벽을 안 건넘
            double t = (wallX - ax) / (bx - ax);
            double y = ay + (by - ay) * t;
            return y > wallTop;
        };
    }

    @Test
    void sightBlocksHittingThroughWalls() {
        BossReach.Ray open = (ax, ay, az, bx, by, bz) -> true;
        assertTrue(BossReach.sees(3.0, EYE, 0, GOLEM, open));
        // 키 큰 벽 (x = 2, 높이 10) 사이 → 안 보임 (보스가 벽 너머로 못 침)
        assertFalse(BossReach.sees(3.0, EYE, 0, GOLEM, wall(2.0, 10)));
        // 2칸 받침 너머: 눈 높이 광선은 막혀도 히트박스 위쪽은 보인다 (플레이어도 그 위를 칠 수 있다)
        assertTrue(BossReach.sees(3.5, EYE, 0, GOLEM, wall(1.6, 2.0)));
        // 눈이 히트박스 안이면 보인다
        assertTrue(BossReach.sees(0.2, 1.0, 0.1, GOLEM, wall(0.5, 99)));
    }

    @Test
    void sightUsesBoundedRays() {
        int[] n = {0};
        BossReach.Ray count = (ax, ay, az, bx, by, bz) -> {
            n[0]++;
            return false;
        };
        assertFalse(BossReach.sees(3.0, EYE, 0, GOLEM, count));
        assertTrue(n[0] <= BossReach.MAX_SIGHT_RAYS && n[0] >= 4, "광선 " + n[0]);
    }

    @Test
    void sightSeesFaceEdgePastANarrowPost() {
        // 눈 (3, 1.62, 0) 과 가장 가까운 기둥 사이 x = 2 에 좁은 기둥 (|z| < 0.5, 아주 높음): 가운데 기둥은 가려도 면 모서리(z = ±1.1)는 보인다
        BossReach.Ray post = (ax, ay, az, bx, by, bz) -> {
            if ((ax - 2.0) * (bx - 2.0) > 0) return true;
            double t = (2.0 - ax) / (bx - ax);
            double z = az + (bz - az) * t;
            return Math.abs(z) >= 0.5;
        };
        assertTrue(BossReach.sees(3.0, EYE, 0, GOLEM, post));
    }

    // ── 직접 다가가기·도약 ───────────────────────────────────────────────

    @Test
    void walkSpeedMatchesVanillaGroundSpeed() {
        // 1층 그로브 0.24 → 실서버 길찾기 걸음 0.127칸/틱
        assertEquals(0.127, BossReach.walkSpeed(0.24), 0.006);
        assertEquals(0.086, BossReach.walkSpeed(0.20), 0.005);
        assertEquals(0.04, BossReach.walkSpeed(0), 1e-9);
        assertEquals(0.3, BossReach.walkSpeed(5), 1e-9);
    }

    @Test
    void landingRingIsDeterministicAndClosestFirst() {
        List<double[]> a = BossReach.landingRing(10, -4);
        List<double[]> b = BossReach.landingRing(10, -4);
        assertEquals(1 + (BossReach.LANDING_RADII.length - 1) * BossReach.LANDING_DIRS, a.size());
        assertEquals(10, a.get(0)[0], 1e-9);
        assertEquals(-4, a.get(0)[1], 1e-9);
        double last = 0;
        for (int i = 0; i < a.size(); i++) {
            assertEquals(a.get(i)[0], b.get(i)[0], 0);
            assertEquals(a.get(i)[1], b.get(i)[1], 0);
            double d = Math.hypot(a.get(i)[0] - 10, a.get(i)[1] + 4);
            assertTrue(d >= last - 1e-9, "가까운 순");
            last = d;
        }
    }

    @Test
    void arcSamplesAreDenseAndAboveTheLine() {
        List<double[]> pts = BossReach.arc(0, 64, 0, 6, 64, 0, 2.0, 0.45);
        assertFalse(pts.isEmpty());
        double[] prev = {0, 64, 0};
        double top = 0;
        for (double[] p : pts) {
            double step = Math.sqrt(Math.pow(p[0] - prev[0], 2) + Math.pow(p[1] - prev[1], 2) + Math.pow(p[2] - prev[2], 2));
            assertTrue(step <= 0.46, "표본 간격 " + step);
            assertTrue(p[1] >= 64 - 1e-9);
            top = Math.max(top, p[1] - 64);
            prev = p;
        }
        assertEquals(2.0, top, 0.01);
        double[] mid = BossReach.arcAt(0, 64, 0, 6, 64, 0, 2.0, 0.5);
        assertEquals(3, mid[0], 1e-9);
        assertEquals(66, mid[1], 1e-9);
        double[] end = BossReach.arcAt(0, 64, 0, 6, 66, 0, 2.0, 1.0);
        assertEquals(6, end[0], 1e-9);
        assertEquals(66, end[1], 1e-9);
    }

    @Test
    void arcRisesBeforeMovingSoAWallAtTheFeetIsCleared() {
        // 2칸 받침에 몸이 붙어 있어도 (수평 0.1칸 안에) 먼저 2칸 넘게 솟는다
        double apex = BossReach.apexOptions(4.6)[1];
        for (double[] p : BossReach.arc(0, 0, 0, 4.6, 2, 0, apex, 0.45)) {
            if (p[0] > 0.1 && p[0] < 4.5) assertTrue(p[1] > 2.0, "x=" + p[0] + " y=" + p[1]);
        }
    }

    @Test
    void apexAndFlightStayShort() {
        double[] a = BossReach.apexOptions(2);
        assertEquals(1.5, a[0], 1e-9);
        assertTrue(a[1] > a[0] && a[2] > a[1]);
        assertEquals(3.0, BossReach.apexOptions(40)[0], 1e-9);
        assertEquals(8, BossReach.flightTicks(1));
        assertEquals(10, BossReach.flightTicks(6));
        assertEquals(16, BossReach.flightTicks(40));
    }
}
