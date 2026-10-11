package kr.souls.combat;

import org.bukkit.Location;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** M1 P1a (3.6): 판정 모양 (Footprint 부채꼴·직선) + 상자 가장자리까지 + 위아래 띠. 세계 없이 상자만으로. */
class HitQueryTest {
    /** 눈 높이 1.62 (서 있는 플레이어), +z 를 본다 */
    private static final Location EYE = new Location(null, 0, 1.62, 0);
    private static final Vector FWD = new Vector(0, 0, 1);
    private static final HitQuery.Spec CONE100 = new HitQuery.Spec(HitQuery.Shape.CONE, 100, 3.0, 0.4, 1.2);
    private static final HitQuery.Spec LINE = new HitQuery.Spec(HitQuery.Shape.LINE, 20, 4.2, 0.4, 1.2);

    /** 좀비 크기 상자 (0.6 × 1.95), 발이 (x, y, z) */
    private static BoundingBox body(double x, double y, double z) {
        return new BoundingBox(x - 0.3, y, z - 0.3, x + 0.3, y + 1.95, z + 0.3);
    }

    @Test
    void rangeIsToTheBoxEdge() {
        // 가운데 3.25 칸, 가장자리 2.95 칸: 사거리 3.0 안
        assertTrue(HitQuery.test(EYE, FWD, CONE100, body(0, 0, 3.25)) >= 0);
        // 가장자리 3.05 칸: 밖
        assertEquals(-1, HitQuery.test(EYE, FWD, CONE100, body(0, 0, 3.35)));
        // 큰 상자 (가운데는 사거리 밖, 가장자리는 안)
        BoundingBox big = new BoundingBox(-1.5, 0, 2.6, 1.5, 4, 5.6);
        assertTrue(HitQuery.test(EYE, FWD, CONE100, big) >= 0, "큰 몸은 가장자리부터 맞는다");
    }

    @Test
    void coneEdges() {
        // 50° (반각) 안쪽과 바깥쪽: 거리 2 칸에 49° 와 60°
        double r = 2.0;
        BoundingBox in = body(Math.sin(Math.toRadians(40)) * r, 0, Math.cos(Math.toRadians(40)) * r);
        assertTrue(HitQuery.test(EYE, FWD, CONE100, in) >= 0, "40° 는 안");
        BoundingBox out = body(Math.sin(Math.toRadians(75)) * r, 0, Math.cos(Math.toRadians(75)) * r);
        assertEquals(-1, HitQuery.test(EYE, FWD, CONE100, out), "75° 는 밖 (상자 폭을 더해도)");
        assertEquals(-1, HitQuery.test(EYE, FWD, CONE100, body(0, 0, -2)), "등 뒤");
        assertTrue(HitQuery.test(EYE, FWD, CONE100, body(0.2, 0, 0.2)) >= 0, "몸에 붙은 것은 늘 맞는다");
        // 상자의 한쪽이 부채꼴에 걸린다 (가운데는 50.5°, 눈에 가까운 모서리는 53°, 축에 가까운 가장자리는 41°)
        BoundingBox edge = new BoundingBox(1.2, 0, 0.9, 2.2, 2, 1.9);
        assertTrue(HitQuery.test(EYE, FWD, CONE100, edge) >= 0, "모서리가 걸리면 맞는다");
    }

    @Test
    void verticalBand() {
        // 눈 1.62 ± 1.2 = 0.42 .. 2.82
        assertTrue(HitQuery.test(EYE, FWD, CONE100, body(0, 0, 2)) >= 0, "같은 바닥");
        assertTrue(HitQuery.test(EYE, FWD, CONE100, body(0, 0.8, 2)) >= 0, "한 칸 위 (발 0.8, 상자가 띠에 걸린다)");
        assertEquals(-1, HitQuery.test(EYE, FWD, new HitQuery.Spec(HitQuery.Shape.CONE, 100, 5, 0.4, 1.2), body(0, 3.0, 2)),
                "발이 3칸 위 (띠 2.82 위)");
        assertEquals(-1, HitQuery.test(EYE, FWD, new HitQuery.Spec(HitQuery.Shape.CONE, 100, 5, 0.4, 1.2), body(0, -2.5, 1.5)),
                "2.5칸 아래 (머리 끝 −0.55 가 띠 0.42 밑)");
    }

    @Test
    void lineHitsAlongTheAxis() {
        assertTrue(HitQuery.test(EYE, FWD, LINE, body(0, 0, 4.0)) >= 0, "4.2칸 직선 끝");
        assertEquals(-1, HitQuery.test(EYE, FWD, LINE, body(1.5, 0, 2)), "축에서 1.2칸 떨어진 몸은 밖");
        assertTrue(HitQuery.test(EYE, FWD, LINE, body(0.7, 0, 2)) >= 0, "축에서 0.4 (가장자리) 는 안 (폭 0.4 + 몸 0.5)");
        assertEquals(-1, HitQuery.test(EYE, FWD, LINE, body(0, 0, -1.5)), "등 뒤");
    }

    @Test
    void thrustOrderIsAlongTheLine() {
        List<BoundingBox> boxes = List.of(body(0, 0, 3.5), body(0.1, 0, 1.5), body(0, 0, 2.5));
        assertEquals(List.of(1, 2, 0), HitQuery.order(EYE, FWD, LINE, boxes), "가까운 것부터: 찌르기는 첫 것만 맞힌다");
        List<BoundingBox> cone = List.of(body(0, 0, 2.6), body(-1, 0, 1), body(5, 0, 5));
        assertEquals(List.of(1, 0), HitQuery.order(EYE, FWD, CONE100, cone), "부채꼴은 안의 모두, 가까운 차례");
    }

    @Test
    void aimIsFlattened() {
        Vector down = new Vector(0, -0.9, 0.3);
        assertTrue(HitQuery.test(EYE, down, CONE100, body(0, 0, 2)) >= 0, "아래를 봐도 수평 방향으로");
        assertEquals(-1, HitQuery.test(EYE, new Vector(0, -1, 0), CONE100, body(0, 0, 2)), "수평 방향이 없으면 판정 없음");
        Vector yaw0 = HitQuery.yawDir(0);
        assertEquals(1, yaw0.getZ(), 1e-9, "yaw 0 = +z");
        Vector yaw90 = HitQuery.yawDir(90);
        assertEquals(-1, yaw90.getX(), 1e-9, "yaw 90 = −x");
    }
}
