package kr.labyrinth.mobs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.bosses.BossAnim;
import kr.labyrinth.content.ModelDef;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.junit.jupiter.api.Test;

/** 리그 관절·걸음 규칙 (GDD §14.3/§14.6): 다리 위상·팔 교차·발 높이·관절 회전 중심·몸 전체 변환·보스 머리 무리. */
class RigMathTest {

    private static final double FULL = 0.18;

    private static ModelDef.Part part(String name, String form, double px, double py, double pz, String anim) {
        return new ModelDef.Part(name, form, 6, 6, 6, px, py, pz, anim);
    }

    /** 다리 세트에서 자른 다리 하나: pivot = 세트 원점, joint = 엉덩이, foot = 엉덩이 → 발바닥. */
    private static ModelDef.Part leg(String name, String form, double jx, double jy, double jz, double fx, double fy, double fz,
                                     double half) {
        return new ModelDef.Part(name, form, 12, 12, 6, 0, 0.8, 0, "legs_walk", "legs", jx, jy, jz,
                new ModelDef.Foot(fx, fy, fz, half));
    }

    private static RigMath.AnimState walking(long tick, double speed) {
        return new RigMath.AnimState(tick, speed, -1, 0, -1, -1, 0, 0, -1, true, 7, false, RigMath.MOTION_NONE, 0f, -1);
    }

    /** 파트의 쉴 때 한 점(몹 로컬 블록)이 지금 있는 곳. */
    private static Vector3f world(RigMath.Solved s, ModelDef.Part p, double x, double y, double z) {
        Vector3f rel = new Vector3f((float) (x - p.pivotX()), (float) (y - p.pivotY()), (float) (z - p.pivotZ()));
        return s.rotation().transform(rel).mul(s.scale()).add(s.pivot());
    }

    private static Vector3f footAt(RigMath.Solved s, ModelDef.Part p) {
        ModelDef.Foot f = p.foot();
        return world(s, p, p.jointX() + f.dx(), p.jointY() + f.dy(), p.jointZ() + f.dz());
    }

    /** 걸음 한 주기 동안 다리마다 발 앞뒤 위치 (프레임 × 다리). */
    private static double[][] footZ(List<ModelDef.Part> parts, double speed, int frames) {
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        double[][] z = new double[frames][parts.size()];
        RigMath.Gait g = new RigMath.Gait();
        for (int k = 0; k < frames; k++) {
            g.set(k / (double) frames, 0, 2);
            RigMath.Solved[] o = sk.solve(walking(1000 + k, speed), g);
            for (int i = 0; i < parts.size(); i++) {
                ModelDef.Part p = parts.get(i);
                z[k][i] = p.foot() == null ? 0 : footAt(o[i], p).z;
            }
        }
        return z;
    }

    private static double corr(double[][] m, int a, int b) {
        int n = m.length;
        double ma = 0, mb = 0;
        for (double[] r : m) {
            ma += r[a];
            mb += r[b];
        }
        ma /= n;
        mb /= n;
        double sab = 0, saa = 0, sbb = 0;
        for (double[] r : m) {
            sab += (r[a] - ma) * (r[b] - mb);
            saa += (r[a] - ma) * (r[a] - ma);
            sbb += (r[b] - mb) * (r[b] - mb);
        }
        return sab / Math.sqrt(saa * sbb);
    }

    private static List<ModelDef.Part> biped() {
        List<ModelDef.Part> p = new ArrayList<>();
        p.add(part("torso", "box", 0, 1.3, 0, "body"));
        p.add(part("head", "box", 0, 1.8, 0, "head"));
        p.add(part("arm_left", "arm", 0.35, 1.6, 0, "arm_left"));
        p.add(part("arm_right", "arm", -0.35, 1.6, 0, "arm_right"));
        p.add(leg("leg_l", "leg_pair", 0.15, 0.75, 0, 0, -0.75, 0, 0.12));
        p.add(leg("leg_r", "leg_pair", -0.15, 0.75, 0, 0, -0.75, 0, 0.12));
        return p;
    }

    @Test
    void bipedLegsAlternateLeftRight() {
        double[][] z = footZ(biped(), FULL, 24);
        assertTrue(corr(z, 4, 5) < -0.8, "두 발은 좌우 교대: r = " + corr(z, 4, 5));
        // 오른다리 = 왼다리를 반 주기 늦춘 것
        for (int k = 0; k < 24; k++) assertEquals(z[k][4], z[(k + 12) % 24][5], 1e-4);
        double range = 0;
        for (double[] r : z) range = Math.max(range, Math.abs(r[4]));
        assertTrue(range > 0.2, "걸을 때 발이 앞뒤로 움직임: " + range);
    }

    @Test
    void armsSwingOppositeToTheSameSideLeg() {
        List<ModelDef.Part> parts = biped();
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        int n = 24;
        double[][] m = new double[n][4];
        RigMath.Gait g = new RigMath.Gait();
        for (int k = 0; k < n; k++) {
            g.set(k / (double) n, 0, 2);
            RigMath.Solved[] o = sk.solve(walking(1000 + k, FULL), g);
            // 손(어깨 아래 0.6)의 앞뒤 위치
            m[k][0] = world(o[2], parts.get(2), 0.35, 1.0, 0).z;
            m[k][1] = world(o[3], parts.get(3), -0.35, 1.0, 0).z;
            m[k][2] = footAt(o[4], parts.get(4)).z;
            m[k][3] = footAt(o[5], parts.get(5)).z;
        }
        assertTrue(corr(m, 0, 2) < -0.8, "왼팔은 왼다리와 반대: " + corr(m, 0, 2));
        assertTrue(corr(m, 1, 3) < -0.8, "오른팔은 오른다리와 반대: " + corr(m, 1, 3));
        assertTrue(corr(m, 1, 2) > 0.8, "오른팔은 왼다리와 같이: " + corr(m, 1, 2));
        assertTrue(corr(m, 0, 1) < -0.8, "두 팔은 서로 반대");
    }

    @Test
    void quadrupedMovesDiagonalPairs() {
        List<ModelDef.Part> p = new ArrayList<>();
        p.add(part("body", "rounded", 0, 0.7, 0, "body"));
        p.add(leg("leg_fl", "leg_quad", 0.2, 0.55, 0.35, 0, -0.55, 0, 0.05));
        p.add(leg("leg_bl", "leg_quad", 0.2, 0.55, -0.35, 0, -0.55, 0, 0.05));
        p.add(leg("leg_fr", "leg_quad", -0.2, 0.55, 0.35, 0, -0.55, 0, 0.05));
        p.add(leg("leg_br", "leg_quad", -0.2, 0.55, -0.35, 0, -0.55, 0, 0.05));
        double[][] z = footZ(p, FULL, 24);
        assertTrue(corr(z, 1, 4) > 0.99, "앞왼·뒤오른 같이");
        assertTrue(corr(z, 3, 2) > 0.99, "앞오른·뒤왼 같이");
        assertTrue(corr(z, 1, 3) < -0.8, "앞왼·앞오른 반대");
        assertTrue(corr(z, 1, 2) < -0.8, "앞왼·뒤왼 반대");
    }

    private static List<ModelDef.Part> splay(String form, int perSide) {
        List<ModelDef.Part> p = new ArrayList<>();
        p.add(part("body", "rounded", 0, 0.4, 0, "body"));
        for (int sd : new int[] {1, -1}) {
            for (int k = 0; k < perSide; k++) {
                double z = 0.3 - 0.6 * k / (perSide - 1);
                p.add(leg("leg_" + (sd > 0 ? "l" : "r") + (k + 1), form, sd * 0.2, 0.35, z, sd * 0.4, -0.35, z * 0.3, 0));
            }
        }
        return p;
    }

    @Test
    void sixLegsUseAlternatingTripods() {
        double[][] z = footZ(splay("leg_six", 3), FULL, 24);
        // 1..3 = 왼쪽 앞→뒤, 4..6 = 오른쪽 앞→뒤 · 삼각 A = L1 R2 L3, B = R1 L2 R3
        assertTrue(corr(z, 1, 5) > 0.99 && corr(z, 1, 3) > 0.99, "L1·R2·L3 같이");
        assertTrue(corr(z, 4, 2) > 0.99 && corr(z, 4, 6) > 0.99, "R1·L2·R3 같이");
        assertTrue(corr(z, 1, 4) < -0.8, "두 삼각은 번갈아");
        double range = 0;
        for (double[] r : z) range = Math.max(range, Math.abs(r[1] - z[0][1]));
        assertTrue(range > 0.1, "펼친 다리도 앞뒤로 디딘다: " + range);
    }

    @Test
    void eightLegsAlternateWithAWave() {
        double[][] z = footZ(splay("leg_eight", 4), FULL, 48);
        for (int k = 1; k <= 4; k++) assertTrue(corr(z, k, k + 4) < -0.6, "좌우 짝 반대: " + k);
        for (int k = 1; k < 4; k++) assertTrue(corr(z, k, k + 1) < -0.6, "같은 쪽 이웃 반대: " + k);
        assertTrue(corr(z, 1, 3) < 0.999, "같은 쪽 하나 건너는 물결로 조금 늦음");
    }

    @Test
    void standingStillKeepsLegsAtRest() {
        List<ModelDef.Part> parts = biped();
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        RigMath.Gait g = new RigMath.Gait();
        for (long t = 0; t < 40; t += 2) {
            g.advance(sk, walking(t, 0), 2);
            RigMath.Solved[] o = sk.solve(walking(t, 0), g);
            for (int i = 4; i < 6; i++) {
                assertEquals(1f, Math.abs(o[i].rotation().w), 1e-5, "정지: 다리 회전 0");
                assertEquals(parts.get(i).pivotY(), o[i].pivot().y, 1e-5, "정지: 다리 제자리");
            }
        }
        assertEquals(0, g.phase(), 1e-9, "멈추면 걸음 위상도 멈춤");
    }

    @Test
    void gaitAdvancesWithDistanceWalked() {
        RigMath.Skeleton sk = new RigMath.Skeleton(biped());
        RigMath.Gait g = new RigMath.Gait();
        double v = 0.1;
        RigMath.Skeleton.Cadence c = sk.cadence(v, 2);
        g.advance(sk, walking(100, v), 2);
        for (long t = 102; t <= 110; t += 2) g.advance(sk, walking(t, v), 2);
        assertEquals(10 / c.ticksPerCycle(), g.phase(), 1e-9, "위상 = 지난 틱 ÷ 한 주기");
        // 한 주기 이동 거리 = 딛는 동안 발이 뒤로 가는 거리 ÷ 딛는 비율 (= 미끄럼 없음)
        double hip = 0.75;
        double angle = RigMath.strideAngle(c.amp(), RigMath.SWING_BIPED, RigMath.SWING_MAX);
        double footTravel = 2 * hip * Math.sin(Math.toRadians(angle));
        assertEquals(v * c.ticksPerCycle() * RigMath.DUTY_HANG, footTravel, 1e-6);
        // 빠를수록 박자가 빨라진다 (주기 하한까지), 느리면 박자는 두고 보폭을 줄인다
        assertTrue(sk.cadence(0.2, 2).ticksPerCycle() <= sk.cadence(0.12, 2).ticksPerCycle());
        assertTrue(sk.cadence(0.02, 2).amp() < sk.cadence(0.06, 2).amp());
        assertEquals(0, sk.cadence(0, 2).amp(), 1e-12);
        // 멀리 있어 5틱마다 갱신하면 주기를 20틱 아래로 줄이지 않는다 (깜빡임 방지)
        assertTrue(sk.cadence(0.3, 5).ticksPerCycle() >= 20);
    }

    @Test
    void swingingFeetStayOnOrAboveTheFloor() {
        // 발바닥이 긴 다리: 기울면 발끝·뒤꿈치가 내려가지만 몸 높이 보정과 들기로 바닥 아래로 가지 않는다
        List<ModelDef.Part> parts = biped();
        parts.set(4, leg("leg_l", "leg_pair", 0.15, 0.75, 0, 0, -0.75, -0.05, 0.3));
        parts.set(5, leg("leg_r", "leg_pair", -0.15, 0.75, 0, 0, -0.75, -0.05, 0.3));
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        RigMath.Gait g = new RigMath.Gait();
        double minAll = 1, maxLow = -1;
        for (int k = 0; k < 48; k++) {
            g.set(k / 48.0, 0, 2);
            RigMath.Solved[] o = sk.solve(walking(1000 + k, FULL), g);
            double low = 1;
            for (int i = 4; i < 6; i++) {
                ModelDef.Part p = parts.get(i);
                for (int e = -1; e <= 1; e += 2) {
                    Vector3f f = world(o[i], p, p.jointX(), p.jointY() - 0.75, p.jointZ() - 0.05 + e * 0.3);
                    low = Math.min(low, f.y);
                }
                // 관절(엉덩이)이 회전 중심: 다리를 돌려도 엉덩이는 몸 아래 같은 앞뒤·옆 자리
                Vector3f hip = world(o[i], p, p.jointX(), p.jointY(), p.jointZ());
                assertEquals(p.jointX(), hip.x, 1e-4);
                assertEquals(p.jointZ(), hip.z, 1e-4);
            }
            minAll = Math.min(minAll, low);
            maxLow = Math.max(maxLow, low);
        }
        assertTrue(minAll > -0.02, "발바닥이 바닥을 뚫지 않음: " + minAll);
        assertTrue(maxLow < 0.02, "디딘 발은 땅에 붙어 있음 (가장 낮은 발 = 땅): " + maxLow);
    }

    @Test
    void airborneLegsTuckAndStay() {
        List<ModelDef.Part> parts = biped();
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        RigMath.Gait g = new RigMath.Gait();
        Vector3f first = null;
        for (int k = 0; k < 12; k++) {
            g.set(k / 12.0, 1, 2);
            RigMath.AnimState s = new RigMath.AnimState(1000, FULL, -1, 0, -1, -1, 0, 0, -1, true, 7, true,
                    RigMath.MOTION_NONE, 0f, -1);
            Vector3f f = footAt(sk.solve(s, g)[4], parts.get(4));
            assertTrue(f.z < -0.2, "공중: 다리를 뒤로 접음 " + f);
            if (first == null) first = f;
            assertEquals(first.z, f.z, 1e-4, "공중에서는 걸음 위상과 상관없이 접은 채");
        }
    }

    @Test
    void attackArmStillSwingsDownWhileWalking() {
        List<ModelDef.Part> parts = biped();
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        RigMath.AnimState s = new RigMath.AnimState(1000, FULL, 2, 0, -1, -1, 0, 0, -1, true, 7, false,
                RigMath.MOTION_NONE, 0f, -1);
        RigMath.Solved arm = sk.solve(s, new RigMath.Gait().set(0.3, 0, 2))[3];
        Vector3f down = arm.rotation().transform(new Vector3f(0, -1, 0));
        double deg = -Math.toDegrees(Math.atan2(down.z, -down.y));
        assertEquals(-110, deg, 8, "공격 팔은 걷는 중에도 머리 위로 든다");
    }

    @Test
    void deathShrinksTheWholeModelTogether() {
        List<ModelDef.Part> parts = biped();
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        RigMath.AnimState alive = new RigMath.AnimState(1000, 0, -1, 0, -1, -1, 0, 0, -1, true, 7);
        RigMath.AnimState dead = new RigMath.AnimState(1000, 0, -1, 0, -1, -1, 0, 0, RigMath.DEATH_TICKS / 2, true, 7);
        RigMath.Solved[] a = sk.solve(alive), d = sk.solve(dead);
        float k = d[0].scale() / a[0].scale();
        assertTrue(k < 0.7f, "작아짐");
        for (int i = 1; i < parts.size(); i++) {
            assertEquals(k, d[i].scale() / a[i].scale(), 1e-5, "모든 파트가 같은 비율");
            double da = new Vector3f(a[i].pivot()).sub(a[1].pivot()).length();
            double dd = new Vector3f(d[i].pivot()).sub(d[1].pivot()).length();
            assertEquals(da * k, dd, 1e-4, "파트 사이 거리도 같은 비율 → 조각나지 않음");
        }
    }

    @Test
    void hurtTiltsEveryPartTheSameWay() {
        List<ModelDef.Part> parts = biped();
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        RigMath.AnimState calm = new RigMath.AnimState(1000, 0, -1, 0, -1, -1, 0, 0, -1, true, 7);
        RigMath.AnimState hit = new RigMath.AnimState(1000, 0, -1, 0, -1, 0, 0, 0, -1, true, 7);
        RigMath.Solved[] a = sk.solve(calm), h = sk.solve(hit);
        Quaternionf d0 = new Quaternionf(h[0].rotation()).mul(new Quaternionf(a[0].rotation()).invert());
        assertTrue(Math.abs(d0.w) < 0.99999f, "피격 때 기울어짐");
        for (int i = 1; i < parts.size(); i++) {
            Quaternionf di = new Quaternionf(h[i].rotation()).mul(new Quaternionf(a[i].rotation()).invert());
            assertTrue(Math.abs(di.dot(d0)) > 0.99999f, "모든 파트가 같은 방향으로: " + parts.get(i).name());
        }
    }

    @Test
    void jointDefaultsToPivotAndRotatesAboutJoint() {
        // joint 없음 = 예전처럼 피벗 중심: 머리를 돌려도 원점 자리 그대로
        List<ModelDef.Part> plain = List.of(part("head", "rounded", 0, 1.5, 0.1, "head"));
        RigMath.AnimState look = new RigMath.AnimState(0, 0, -1, 0, -1, -1, 40, 15, -1, true, 7);
        RigMath.Solved o = new RigMath.Skeleton(plain).solve(look)[0];
        assertEquals(0, o.pivot().distance(new Vector3f(0, 1.5f, 0.1f)), 1e-5);
        assertEquals(new Quaternionf(RigMath.pose("head", "rounded", look).rotation()).dot(o.rotation()), 1f, 1e-5);
        // joint = 목(머리 아래): 끄덕이면 원점이 목을 중심으로 돈다, 목 자리는 그대로
        ModelDef.Part neckJoint = plain.get(0).withJoint(0, 1.3, 0.1, null);
        RigMath.Solved q = new RigMath.Skeleton(List.of(neckJoint)).solve(look)[0];
        assertTrue(q.pivot().distance(new Vector3f(0, 1.5f, 0.1f)) > 0.03, "회전 중심이 목이면 원점이 움직임");
        assertEquals(0, world(q, neckJoint, 0, 1.3, 0.1).distance(new Vector3f(0, 1.3f, 0.1f)), 1e-5, "목은 제자리");
        assertEquals(0.2, q.pivot().distance(new Vector3f(0, 1.3f, 0.1f)), 1e-5, "목 ↔ 원점 거리 유지");
    }

    @Test
    void lowerJawOpensDownLidOpensUp() {
        List<ModelDef.Part> parts = List.of(
                part("head", "rounded", 0, 1.0, 0.5, "head"),
                new ModelDef.Part("jaw", "claw", 5, 2, 5, 0, 0.9, 0.65, "jaw", null, 0, 0.95, 0.5, null),
                part("lid", "slab", 0, 1.2, 0.3, "jaw"));
        RigMath.AnimState bite = new RigMath.AnimState(0, 0, 2, 0, -1, -1, 0, 0, -1, true, 7);
        RigMath.Solved[] o = new RigMath.Skeleton(parts).solve(bite);
        Vector3f tip = o[1].rotation().transform(new Vector3f(0, 0, 1));
        assertTrue(tip.y < -0.3, "아래턱 앞 끝이 아래로: " + tip);
        assertEquals(0, world(o[1], parts.get(1), 0, 0.95, 0.5).distance(new Vector3f(0, 0.95f, 0.5f)), 1e-4,
                "경첩(뒤 끝 위)은 제자리");
        Vector3f lid = o[2].rotation().transform(new Vector3f(0, 0, 1));
        assertTrue(lid.y > 0.3, "뚜껑은 위로: " + lid);
    }

    @Test
    void bossCrownFollowsTheHeadUnderOverlays() {
        List<ModelDef.Part> parts = List.of(
                part("body", "rounded", 0, 1.0, 0, "body"),
                part("head", "rounded", 0, 1.8, 0.2, "head").withJoint(0, 1.6, 0.2, null),
                part("crown", "crystal_cluster", 0, 2.2, 0.2, "head"),
                part("arm_left", "arm", 0.5, 1.5, 0, "arm_left"));
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        RigMath.AnimState s = new RigMath.AnimState(1000, 0, -1, 2, -1, -1, 20, 5, -1, true, 7);
        for (double p = 0.1; p < 1; p += 0.2) {
            RigMath.Solved[] o = sk.solve(s, null, BossAnim.rig(BossAnim.ROAR, p, 0.5, 1000));
            assertTrue(Math.abs(o[2].rotation().dot(o[1].rotation())) > 0.99999f, "왕관 = 머리 회전");
            double rest = 0.6;   // 왕관 원점 ↔ 머리 관절
            assertEquals(rest, o[2].pivot().distance(world(o[1], parts.get(1), 0, 1.6, 0.2)), 1e-4, "왕관이 머리에 붙어 있음");
        }
        // 오버레이가 없으면 몹 리그와 같은 결과
        RigMath.Solved[] a = sk.solve(s), b = sk.solve(s, null, BossAnim.rig(BossAnim.NONE, 0, 0.5, 1000));
        for (int i = 0; i < parts.size(); i++) assertEquals(0, a[i].pivot().distance(b[i].pivot()), 1e-6);
    }

    @Test
    void raisedLegDoesNotWalk() {
        // 치켜든 앞다리(발이 다른 다리보다 훨씬 높음)는 걷기 위상에 끼지 않는다
        List<ModelDef.Part> p = splay("leg_eight", 4);
        p.set(1, leg("leg_l1", "leg_eight", 0.2, 0.5, 0.3, 0.2, 0.2, 0.2, 0));
        RigMath.Skeleton sk = new RigMath.Skeleton(p);
        assertTrue(!sk.walking(1) && sk.walking(2), "치켜든 다리 = 걷지 않음");
        assertEquals(7, sk.walkingLegs());
    }
}
