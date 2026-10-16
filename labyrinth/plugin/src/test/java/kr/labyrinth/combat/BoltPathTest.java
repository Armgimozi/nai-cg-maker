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
}
