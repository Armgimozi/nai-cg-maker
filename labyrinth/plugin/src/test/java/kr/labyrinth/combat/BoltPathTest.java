package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.util.List;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;
import org.junit.jupiter.api.Test;

/** 마법탄 길·맞는 판정 (0.3.6.1). */
class BoltPathTest {

    private static final double EPS = 1e-6;

    /** 바닥 가운데가 (x, 0, z) 인 너비 w · 높이 h 상자 (몹 히트박스 꼴). */
    private static BoundingBox mob(double x, double z, double w, double h) {
        return new BoundingBox(x - w / 2, 0, z - w / 2, x + w / 2, h, z + w / 2);
    }

    private static final Vector EYE = new Vector(0, 1.6, 0);
    private static final Vector EAST = new Vector(1, 0, 0);

    @Test
    void stepsAtSpeedAndStopsAtRange() {
        BoltPath p = new BoltPath(EYE, EAST, 2.5, 16);
        int steps = 0;
        while (!p.done()) {
            double s = p.nextStep();
            assertTrue(s > 0 && s <= 2.5 + EPS);
            p.advance(s);
            steps++;
        }
        assertEquals(7, steps, "16칸 ÷ 2.5 = 6.4 → 일곱 걸음 (마지막 1칸)");
        assertEquals(16, p.travelled(), EPS);
        assertEquals(16, p.position().getX(), EPS);
        assertEquals(0, p.nextStep(), EPS);
        assertEquals(7, CasterBoltConfig.DEFAULT.maxTicks() - 1, "설정의 최대 틱도 일곱 걸음 + 1");
    }

    @Test
    void directionIsNormalised() {
        BoltPath p = new BoltPath(EYE, new Vector(3, 0, 4), 1, 10);
        assertEquals(1, p.direction().length(), EPS);
        p.advance(5);
        assertEquals(3, p.position().getX(), EPS);
        assertEquals(4, p.position().getZ(), EPS);
        assertEquals(1, new BoltPath(EYE, new Vector(), 1, 10).direction().length(), EPS, "0 방향도 단위 벡터");
    }

    @Test
    void hitsFirstEnemyOnTheLineOnly() {
        var near = new BoltPath.Candidate<>("near", mob(1.8, 0, 0.6, 1.95));
        var far = new BoltPath.Candidate<>("far", mob(2.3, 0, 0.6, 1.95));
        BoltPath.Hit<String> h = BoltPath.firstHit(EYE, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(far, near));
        assertNotNull(h);
        assertEquals("near", h.target(), "관통 없음 — 처음 닿는 하나");
        assertEquals(1.8 - 0.3 - 0.3, h.distance(), EPS, "히트박스 반폭 0.3 + 굵기 0.3 앞에서 닿음");
    }

    @Test
    void radiusWidensTheBolt() {
        var side = new BoltPath.Candidate<>("side", mob(2.0, 0.5, 0.6, 1.95)); // 상자 가장자리가 줄에서 옆으로 0.2
        assertNull(BoltPath.firstHit(EYE, EAST, 2.5, 0.0, Double.POSITIVE_INFINITY, List.of(side)), "굵기 0 이면 빗나감");
        assertNotNull(BoltPath.firstHit(EYE, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(side)), "굵기 0.3 이면 스침");
    }

    @Test
    void wallBlocksWhatIsBehindIt() {
        var behind = new BoltPath.Candidate<>("behind", mob(2.0, 0, 0.6, 1.95));
        assertNull(BoltPath.firstHit(EYE, EAST, 2.5, 0.3, 1.0, List.of(behind)), "1칸 앞 벽 → 벽 뒤 몹은 못 맞힘");
        assertNotNull(BoltPath.firstHit(EYE, EAST, 2.5, 0.3, 1.5, List.of(behind)), "벽보다 앞에 닿으면 맞음");
    }

    @Test
    void outOfThisStepIsNotHitYet() {
        var later = new BoltPath.Candidate<>("later", mob(6.0, 0, 0.6, 1.95));
        assertNull(BoltPath.firstHit(EYE, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(later)));
        BoltPath p = new BoltPath(EYE, EAST, 2.5, 16);
        p.advance(2.5);
        p.advance(2.5);
        assertNotNull(BoltPath.firstHit(p.position(), p.direction(), p.nextStep(), 0.3, Double.POSITIVE_INFINITY, List.of(later)),
                "세 번째 걸음에서 맞음");
    }

    @Test
    void startingInsideABigHitboxHitsAtOnce() {
        var boss = new BoltPath.Candidate<>("boss", mob(0.5, 0, 4.0, 5.0)); // 눈이 보스 상자 안
        BoltPath.Hit<String> h = BoltPath.firstHit(EYE, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(boss));
        assertNotNull(h);
        assertEquals(0, h.distance(), EPS);
    }

    @Test
    void tallBossHitboxIsHitAtHeadHeightAndOverhead() {
        // 보스 몸 엔티티(크기 키운 투명 몹) 3 × 4.5 — 위로 비스듬히 쏴도 몸 상자에 맞는다 (모델 파트는 후보가 아님)
        var boss = new BoltPath.Candidate<>("boss", mob(6.0, 0, 3.0, 4.5));
        Vector up = new Vector(1, 0.35, 0);
        BoltPath p = new BoltPath(EYE, up, 2.5, 16);
        BoltPath.Hit<String> h = null;
        while (!p.done() && h == null) {
            h = BoltPath.firstHit(p.position(), p.direction(), p.nextStep(), 0.3, Double.POSITIVE_INFINITY, List.of(boss));
            p.advance(p.nextStep());
        }
        assertNotNull(h);
        assertEquals("boss", h.target());
    }

    @Test
    void behindTheShooterIsNeverHit() {
        var back = new BoltPath.Candidate<>("back", mob(-2.0, 0, 0.6, 1.95));
        assertNull(BoltPath.firstHit(EYE, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(back)));
    }

    @Test
    void segmentBoxCoversTheStepWithPad() {
        BoundingBox b = BoltPath.segmentBox(EYE, EAST, 2.5, 0.3);
        assertTrue(b.contains(new Vector(2.7, 1.6, 0.25)));
        assertFalse(b.contains(new Vector(3.0, 1.6, 0)));
        assertEquals(2.5 + 0.6, b.getWidthX(), EPS);
    }

    @Test
    void emptyOrBadInputHasNoHit() {
        assertNull(BoltPath.firstHit(EYE, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.<BoltPath.Candidate<String>>of()));
        assertNull(BoltPath.firstHit(EYE, new Vector(), 2.5, 0.3, Double.POSITIVE_INFINITY,
                List.of(new BoltPath.Candidate<>("x", mob(1, 0, 1, 2)))));
    }

    // ── 시야 (키운 테두리가 얇은 블록 너머로 삐져나오지 않게) ─────────────

    /** x = wallX 에 선 얇은 벽 (철창·유리판·닫힌 문) — at → nearest 가 그 면을 건너면 막힘. */
    private static BoltPath.Sight<String> thinWallAt(double wallX) {
        return (c, at, nearest) -> !((at.getX() - wallX) * (nearest.getX() - wallX) < 0);
    }

    @Test
    void mobRightBehindAThinBlockIsNotHit() {
        // 리뷰(안전 2): 6칸 철창 면(6.4375) 바로 뒤 0.3칸 안에 붙은 허스크 (상자 6.58~7.18) — 키운 상자(6.28~)가 철창 앞으로 나와 맞았음
        var husk = new BoltPath.Candidate<>("husk", mob(6.88, 0, 0.6, 1.95));
        Vector from = new Vector(4.0, 1.6, 0);
        double bars = 6.4375 - from.getX();
        assertNotNull(BoltPath.firstHit(from, EAST, 2.5, 0.3, bars, List.of(husk)), "시야 검사 없으면 (예전) 맞음");
        assertNull(BoltPath.firstHit(from, EAST, 2.5, 0.3, bars, List.of(husk), thinWallAt(6.4375)), "철창 뒤 → 안 맞음");
        // 철창이 다음 걸음에 있어도 (이번 걸음엔 블록 없음) 같은 판정
        Vector from2 = new Vector(3.9, 1.6, 0);
        assertNull(BoltPath.firstHit(from2, EAST, 2.45, 0.3, Double.POSITIVE_INFINITY, List.of(husk), thinWallAt(6.4375)),
                "걸음 끝(6.35)이 철창(6.44) 앞이어도 키운 테두리만 닿았으면 시야를 본다");
    }

    @Test
    void directHitAndOpenGrazeStillCount() {
        var husk = new BoltPath.Candidate<>("husk", mob(6.88, 0, 0.6, 1.95));
        Vector from = new Vector(4.0, 1.6, 0);
        assertNotNull(BoltPath.firstHit(new Vector(4.5, 1.6, 0), EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(husk), (c, at, n) -> false),
                "이번 걸음 선분이 몸에 직접 닿으면 시야 검사 없이 맞음");
        var side = new BoltPath.Candidate<>("side", mob(6.0, 0.5, 0.6, 1.95)); // 줄에서 옆으로 0.2 — 테두리로만 닿음
        assertNotNull(BoltPath.firstHit(from, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(side), thinWallAt(9.0)),
                "막는 것이 없으면 스쳐도 맞음");
        assertNull(BoltPath.firstHit(from, EAST, 2.5, 0.3, Double.POSITIVE_INFINITY, List.of(side), (c, at, n) -> false),
                "스친 몸이 막혀 있으면 안 맞음");
    }

    @Test
    void hiddenNearestFallsThroughToTheNextCandidate() {
        var hidden = new BoltPath.Candidate<>("hidden", mob(5.0, 0.5, 0.6, 1.95)); // 스침만, 막힘
        var open = new BoltPath.Candidate<>("open", mob(5.5, 0, 0.6, 1.95));     // 직접
        BoltPath.Hit<String> h = BoltPath.firstHit(new Vector(4.0, 1.6, 0), EAST, 2.5, 0.3, Double.POSITIVE_INFINITY,
                List.of(hidden, open), (c, at, n) -> !c.target().equals("hidden"));
        assertNotNull(h);
        assertEquals("open", h.target(), "가려진 앞 후보를 건너뛰고 다음 후보");
    }

    @Test
    void nearestInsideStaysJustInsideTheBox() {
        BoundingBox b = mob(0, 0, 0.6, 1.95);
        Vector n = BoltPath.nearestInside(b, new Vector(-2, 5, 0.1), BoltPath.SIGHT_INSET);
        assertEquals(-0.25, n.getX(), EPS);
        assertEquals(1.90, n.getY(), EPS);
        assertEquals(0.1, n.getZ(), EPS);
        Vector floor = BoltPath.nearestInside(b, new Vector(0, -1, 0), BoltPath.SIGHT_INSET);
        assertTrue(floor.getY() > 0, "바닥 면과 딱 맞닿지 않게 조금 안쪽 (바닥 블록에 막힌 것으로 보지 않게)");
        BoundingBox thin = new BoundingBox(0, 0, 0, 0.04, 1, 1);
        assertTrue(thin.contains(BoltPath.nearestInside(thin, new Vector(5, 0.5, 0.5), BoltPath.SIGHT_INSET)), "얇은 상자도 안쪽");
    }

    // ── 보이는 꼬리 (손에서 조준선으로) ─────────────────────────────────────

    @Test
    void handOffsetIsLowerRightOnScreen() {
        Vector south = new Vector(0, 0, 1); // yaw 0
        Vector off = BoltPath.handOffset(0f, south, false, 0.35, 0.3);
        assertEquals(-0.35, off.getX(), EPS, "남쪽을 보면 오른쪽은 서쪽(−x)");
        assertEquals(-0.3, off.getY(), EPS, "아래");
        assertEquals(0, off.getZ(), EPS);
        assertEquals(0.35, BoltPath.handOffset(0f, south, true, 0.35, 0.3).getX(), EPS, "왼손잡이는 왼쪽");
        assertEquals(-0.3, BoltPath.handOffset(0f, south, true, 0.35, 0.3).getY(), EPS, "왼손잡이도 아래");
        Vector down = BoltPath.handOffset(0f, new Vector(0, -1, 0), false, 0.35, 0.3);
        assertEquals(-0.3, down.getZ(), EPS, "바로 아래를 보면 화면 아래 = 뒤쪽(−z)");
        assertEquals(0, down.getY(), EPS);
    }

    @Test
    void trailLeavesTheCrosshairLineThenJoinsIt() {
        // 리뷰(느낌 2): 꼬리가 조준선 위에만 있으면 쏜 사람 화면에서는 조준점 한 곳에 겹친다
        Vector eye = new Vector(0, 65.62, 0), dir = new Vector(0, 0, 1);
        Vector off = BoltPath.handOffset(0f, dir, false, 0.35, 0.3);
        Vector near = BoltPath.visualPoint(eye, dir, off, 1.0, 6.0);
        double angle = Math.toDegrees(Math.atan2(Math.hypot(near.getX(), near.getY() - eye.getY()), near.getZ()));
        assertTrue(angle > 15, "1칸 앞 꼬리는 조준점에서 " + angle + "° 떨어져 보임 (손 쪽)");
        Vector far = BoltPath.visualPoint(eye, dir, off, 6.0, 6.0);
        assertEquals(0, far.clone().subtract(eye.clone().add(dir.clone().multiply(6))).length(), EPS, "6칸에서 조준선과 만남");
        assertEquals(0, BoltPath.visualPoint(eye, dir, off, 12.0, 6.0).getX(), EPS, "그 뒤로는 조준선 그대로");
    }
}
