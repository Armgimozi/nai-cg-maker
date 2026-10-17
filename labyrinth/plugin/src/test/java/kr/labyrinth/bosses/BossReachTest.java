package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** bs362 → bs363: 보스 기본 공격 = 보스별 거리(0.3.6.1) + 시야 · 칼끝 띠(판단 전용) · 설 자리 순서. 맞대응 거리·도약 궤적은 없다. */
class BossReachTest {

    /** 1층 그로브 히트박스 (철 골렘 2.24 × 4.32, SCALE 1.6) 를 원점에. */
    private static final BossReach.Box GOLEM = BossReach.Box.of(0, 0, 0, 1.12, 4.32);
    /** 1층 옛 reach = 2.0 + 0.7 × 1.6. */
    private static final double R1 = 2.0 + 0.7 * 1.6;
    private static final double EYE = 1.62;

    /** 0.3.6.1 Boss.chase 그대로 옮긴 기본 공격 판정 (휘두를 때): dist ≤ reach && |dy| < 3.5, reach = 2.0 + scale × 0.7. */
    private static boolean old0361Swing(double dist, double dy, double scale) {
        double reach = 2.0 + scale * 0.7;
        return dist <= reach && Math.abs(dy) < 3.5;
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
    void openFieldReachEquals0361ForEveryBoss() {
        // bs363: 보스마다 자기 거리 (맞대응 거리 없음). bosses.yml 의 모든 보스 scale 로, 트인 곳 격자 전체에서 0.3.6.1 과 같다.
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        assertEquals(10, c.bosses().size());
        for (BossDef d : c.bosses().values()) {
            double r = BossReach.reach(d.scale());
            assertEquals(2.0 + d.scale() * 0.7, r, 1e-12, d.id());
            for (double dist = 0; dist <= 8; dist += 0.05) {
                for (double dy = -5; dy <= 5; dy += 0.25) {
                    assertEquals(old0361Swing(dist, dy, d.scale()), BossReach.legacy(dist, dy, r), d.id() + " dist " + dist + " dy " + dy);
                }
            }
            // 3틱 뒤 맞힐 때 여유도 0.3.6.1 과 같다 (reach + 0.8)
            assertTrue(BossReach.legacy(r + BossReach.CONFIRM_SLACK - 1e-9, 0, r + BossReach.CONFIRM_SLACK), d.id());
            assertFalse(BossReach.legacy(r + BossReach.CONFIRM_SLACK + 0.01, 0, r + BossReach.CONFIRM_SLACK), d.id());
        }
        // 보스마다 다르다: 1층 3.12 · 2층 3.54 · 10층 3.68
        assertEquals(R1, BossReach.reach(c.boss("floor01_moss_warden").scale()), 1e-9);
        assertEquals(2.0 + 0.7 * 2.2, BossReach.reach(c.boss("floor02_silk_queen").scale()), 1e-9);
        assertEquals(2.0 + 0.7 * 2.4, BossReach.reach(c.boss("floor10_abyss_heart").scale()), 1e-9);
    }

    @Test
    void ownerSpotOnFloorOneIsOutOfReachButInTheBand() {
        // 실서버 재현: 보스 중심에서 3.37칸, 봇 눈 → 히트박스 약 2.25칸. 기본 공격은 보스 자기 거리(3.12)라 안 닿고,
        // 플레이어 칼은 닿는 칼끝 띠 안 → 막힘이면 설 자리로 걷거나 보스 자기 패턴으로 답한다 (거리를 늘리지 않음)
        double d = 3.37;
        assertFalse(BossReach.legacy(d, 0, R1));
        double eyeBox = BossReach.pointToBox(d, EYE, 0, GOLEM);
        assertTrue(eyeBox < BossReach.PLAYER_REACH);
        assertTrue(BossReach.inBand(eyeBox, BossReach.PLAYER_REACH, AnswerWatch.BAND_SLACK));
    }

    @Test
    void bandIsPlayerReachPlusSlackFromTheEye() {
        double pr = BossReach.PLAYER_REACH, slack = AnswerWatch.BAND_SLACK;
        assertTrue(BossReach.inBand(pr + slack, pr, slack));
        assertFalse(BossReach.inBand(pr + slack + 0.01, pr, slack));
        assertTrue(BossReach.inBand(0, pr, slack));
        // 골렘 옆면: 눈 → 상자 3.5 = 중심 4.62 까지가 띠, 그 밖(원거리 카이팅)은 띠 아님
        assertTrue(BossReach.inBand(BossReach.pointToBox(4.6, EYE, 0, GOLEM), pr, slack));
        assertFalse(BossReach.inBand(BossReach.pointToBox(4.7, EYE, 0, GOLEM), pr, slack));
        assertFalse(BossReach.inBand(BossReach.pointToBox(9, EYE, 0, GOLEM), pr, slack));
        // 손 닿음 속성이 길면 띠도 길다
        assertTrue(BossReach.inBand(4.9, BossReach.playerReach(4.5), slack));
    }

    @Test
    void legacyHeightLimitIsThreeAndAHalf() {
        double r4 = BossReach.reach(1.9);
        assertFalse(BossReach.legacy(1.0, 3.5, r4));
        assertTrue(BossReach.legacy(1.0, 3.49, r4));
        assertFalse(BossReach.legacy(1.0, -3.5, r4));
        // 5칸 기둥 위는 보스 자기 거리로는 못 친다 (그 자리는 대응이 맡는다)
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

    // ── 거리 안 시야 (칼끝 띠 판단) ──────────────────────────────────────

    /** 막는 블록 상자들 (선분 ↔ 상자 교차 = 막힘). */
    private static BossReach.Ray blocks(BossReach.Box... boxes) {
        return (ax, ay, az, bx, by, bz) -> {
            for (BossReach.Box k : boxes) if (segmentHits(ax, ay, az, bx, by, bz, k)) return false;
            return true;
        };
    }

    private static boolean segmentHits(double ax, double ay, double az, double bx, double by, double bz, BossReach.Box k) {
        double t0 = 0, t1 = 1;
        double[] a = {ax, ay, az}, d = {bx - ax, by - ay, bz - az};
        double[] lo = {k.minX(), k.minY(), k.minZ()}, hi = {k.maxX(), k.maxY(), k.maxZ()};
        for (int i = 0; i < 3; i++) {
            if (Math.abs(d[i]) < 1e-12) {
                if (a[i] < lo[i] || a[i] > hi[i]) return false;
                continue;
            }
            double u = (lo[i] - a[i]) / d[i], v = (hi[i] - a[i]) / d[i];
            t0 = Math.max(t0, Math.min(u, v));
            t1 = Math.min(t1, Math.max(u, v));
            if (t0 > t1) return false;
        }
        return true;
    }

    /** 등불 받침 (높이 2칸, z 로 넓게): x 2.2 ~ 3.2. */
    private static final BossReach.Box PEDESTAL = new BossReach.Box(2.2, 0, -5, 3.2, 2.0, 5);

    @Test
    void lanternPocketUpperBodyPastReachIsNotAHit() {
        // verify 재현: 눈 → 히트박스 2.78칸 (맞대응 거리 안) 인데 가까운 점은 받침에 가리고, 받침 위로 보이는 윗몸은 3칸 밖
        double ex = 3.9;
        assertTrue(BossReach.pointToBox(ex, EYE, 0, GOLEM) < BossReach.PLAYER_REACH);
        assertFalse(BossReach.legacy(ex, 0, R1));
        BossReach.Ray ray = blocks(PEDESTAL);
        assertTrue(BossReach.sees(ex, EYE, 0, GOLEM, ray), "어느 점이든 (옛 규칙용): 윗몸은 보인다");
        assertFalse(BossReach.sees(ex, EYE, 0, GOLEM, ray, BossReach.PLAYER_REACH), "손 닿음 안에서 보이는 점이 없다 → 플레이어도 못 친다");
        // 3틱 뒤 판정 여유(+0.8) 안에는 윗몸이 들어온다 (휘두를 때 막히니 이 여유로 새로 맞지는 않는다)
        assertTrue(BossReach.sees(ex, EYE, 0, GOLEM, ray, BossReach.PLAYER_REACH + BossReach.CONFIRM_SLACK));
    }

    @Test
    void lowWallInsideReachStillSeesOverTheTop() {
        // 받침이 더 가까이 (x 1.6 ~ 2.0): 받침 위로 보이는 윗몸이 3칸 안 → 플레이어 칼이 닿는다 (칼끝 띠)
        BossReach.Ray ray = blocks(new BossReach.Box(1.6, 0, -5, 2.0, 2.0, 5));
        assertFalse(ray.clear(3.0, EYE, 0, 1.12, EYE, 0), "가장 가까운 점은 가린다");
        assertTrue(BossReach.sees(3.0, EYE, 0, GOLEM, ray, BossReach.PLAYER_REACH));
    }

    @Test
    void withinReachSeesAroundANarrowPost() {
        // 좁은 기둥 (x 1.9 ~ 2.1, |z| < 0.4, 아주 높음): 가운데는 가려도 면 옆쪽(손 닿음 안)은 보인다
        BossReach.Ray post = blocks(new BossReach.Box(1.9, -5, -0.4, 2.1, 20, 0.4));
        assertFalse(post.clear(3.0, EYE, 0, 1.12, EYE, 0));
        assertTrue(BossReach.sees(3.0, EYE, 0, GOLEM, post, BossReach.PLAYER_REACH));
        // 아주 넓은 벽이면 못 본다 (벽 너머 공격 없음)
        assertFalse(BossReach.sees(3.0, EYE, 0, GOLEM, blocks(new BossReach.Box(1.9, -5, -9, 2.1, 20, 9)), BossReach.PLAYER_REACH));
    }

    @Test
    void withinReachSightRespectsTheDistance() {
        BossReach.Ray open = (ax, ay, az, bx, by, bz) -> true;
        assertTrue(BossReach.sees(4.0, EYE, 0, GOLEM, open, 3.0)); // 2.88
        assertFalse(BossReach.sees(4.2, EYE, 0, GOLEM, open, 3.0)); // 3.08
        assertTrue(BossReach.sees(4.2, EYE, 0, GOLEM, open, 3.8));
        assertTrue(BossReach.sees(0.2, 1.0, 0.1, GOLEM, blocks(new BossReach.Box(-9, -9, -9, 9, 9, 9)), 3.0), "눈이 상자 안");
        assertEquals(BossReach.sees(3.5, EYE, 0, GOLEM, blocks(PEDESTAL)),
                BossReach.sees(3.5, EYE, 0, GOLEM, blocks(PEDESTAL), Double.POSITIVE_INFINITY), "무한 = 옛 시야");
    }

    @Test
    void withinReachSamplesStayInReachOnTheSurfaceAndAreBounded() {
        for (double[] eye : new double[][] {{3.0, EYE, 0}, {3.6, EYE, 2.4}, {1.8, 6.6, 0.3}, {-3.2, 0.4, -1.0}}) {
            List<double[]> pts = BossReach.reachSamples(eye[0], eye[1], eye[2], GOLEM, 3.0);
            assertTrue(pts.size() <= BossReach.MAX_REACH_RAYS && pts.size() >= 2, "점 " + pts.size());
            double[] cp = BossReach.closestPoint(eye[0], eye[1], eye[2], GOLEM);
            for (int k = 0; k < 3; k++) assertEquals(cp[k], pts.get(0)[k], 1e-9, "가장 가까운 점부터");
            for (double[] p : pts) {
                double d = Math.sqrt(Math.pow(p[0] - eye[0], 2) + Math.pow(p[1] - eye[1], 2) + Math.pow(p[2] - eye[2], 2));
                assertTrue(d <= 3.0 + 1e-9, "손 닿음 밖 점 " + d);
                assertEquals(0, BossReach.pointToBox(p[0], p[1], p[2], GOLEM), 1e-9, "히트박스 겉면");
            }
            List<double[]> again = BossReach.reachSamples(eye[0], eye[1], eye[2], GOLEM, 3.0);
            assertEquals(pts.size(), again.size());
            for (int i = 0; i < pts.size(); i++) for (int k = 0; k < 3; k++) assertEquals(pts.get(i)[k], again.get(i)[k], 0, "결정적");
        }
        // 비스듬히 선 자리: 눈을 향한 두 면 모두에서 고른다
        boolean onX = false, onZ = false;
        for (double[] p : BossReach.reachSamples(2.6, EYE, 2.6, GOLEM, 3.0)) {
            if (Math.abs(p[0] - 1.12) < 1e-9 && p[2] < 1.0) onX = true;
            if (Math.abs(p[2] - 1.12) < 1e-9 && p[0] < 1.0) onZ = true;
        }
        assertTrue(onX && onZ);
        int[] n = {0};
        BossReach.Ray count = (ax, ay, az, bx, by, bz) -> {
            n[0]++;
            return false;
        };
        assertFalse(BossReach.sees(3.0, EYE, 0, GOLEM, count, 3.0));
        assertTrue(n[0] <= BossReach.MAX_REACH_RAYS && n[0] >= 8, "광선 " + n[0]);
    }

    // ── 곧장 걷기·설 자리 고리 ───────────────────────────────────────────

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

    // ── 설 자리 순서 ─────────────────────────────────────────────────────

    @Test
    void standOrderKeepsReachMarginAndStaysOffTheTargetsBody() {
        double tx = 3, tz = -2, hw = 1.12;
        List<double[]> c = BossReach.standOrder(tx, tz, hw, R1, 0, 0, 14, 0, 0);
        assertFalse(c.isEmpty());
        for (double[] p : c) {
            double d = Math.hypot(p[0] - tx, p[1] - tz);
            assertTrue(d >= hw + BossReach.STAND_CLEAR - 1e-9, "대상 몸 위 " + d);
            assertTrue(d <= R1 - BossReach.STAND_MARGIN + 1e-9, "자기 거리 − 0.3 밖 " + d);
            // 서면 보스 자기 거리로 닿는다
            assertTrue(BossReach.legacy(d, 0, R1));
        }
        // 아레나 안 (중심에서 반경 − 반폭 − 0.3)
        for (double[] p : BossReach.standOrder(12.5, 0, hw, R1, 0, 0, 14, 0, 0)) {
            assertTrue(Math.hypot(p[0], p[1]) <= 14 - hw - 0.3 + 1e-9);
        }
        // 대상 몸이 너무 커서(반폭 + 0.5 > reach − 0.3) 후보 없음
        assertTrue(BossReach.standOrder(0, 0, 3.0, R1, 0, 0, 14, 0, 0).isEmpty());
    }

    @Test
    void standOrderSortsByReferencePointThenTargetAndIsDeterministic() {
        double tx = 5, tz = 5, hw = 0.57;
        double r = BossReach.reach(1.9);
        // BOSS 순서 = 보스 자리에서 가까운 순 (보스가 서쪽 (0, 5) 에 있으면 첫 후보는 대상 서쪽)
        List<double[]> boss = BossReach.standOrder(tx, tz, hw, r, 0, 0, 16, 0, 5);
        assertTrue(boss.get(0)[0] < tx, "서쪽 먼저 " + boss.get(0)[0]);
        double last = -1;
        for (double[] p : boss) {
            double d = Math.hypot(p[0], p[1] - 5);
            assertTrue(d >= last - 1e-9, "가까운 순");
            last = d;
        }
        // NEAR 순서 = 주어진 점에서 가까운 순 (대상 발 = 같은 거리 → 대상에 가까운 고리 먼저)
        List<double[]> near = BossReach.standOrder(tx, tz, hw, r, 0, 0, 16, tx, tz);
        double first = Math.hypot(near.get(0)[0] - tx, near.get(0)[1] - tz);
        for (double[] p : near) assertTrue(Math.hypot(p[0] - tx, p[1] - tz) >= first - 1e-9);
        assertEquals(hw + BossReach.STAND_CLEAR, first, 0.7, "가장 안쪽 고리");
        // 결정적
        List<double[]> again = BossReach.standOrder(tx, tz, hw, r, 0, 0, 16, 0, 5);
        assertEquals(boss.size(), again.size());
        for (int i = 0; i < boss.size(); i++) {
            assertEquals(boss.get(i)[0], again.get(i)[0], 0);
            assertEquals(boss.get(i)[1], again.get(i)[1], 0);
        }
    }
}
