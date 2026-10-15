package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.mobs.EliteVariants;
import kr.labyrinth.mobs.Geometry;
import kr.labyrinth.mobs.MobStats;
import kr.labyrinth.mobs.RigMath;
import kr.labyrinth.mobs.ThreatTable;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.junit.jupiter.api.Test;

/** mobs 패키지 순수 로직: 수치 배율, 위협 표, 판정 도형, 리그 수학, 정예 변종 스킬. */
class MobLogicTest {

    private static final double EPS = 1e-6;

    @Test
    void statsApplyMultipliersAndElite() {
        MobStats normal = MobStats.compute(60, 6, 2, 12, 1.0, 1.0, 1.0, false);
        assertEquals(60, normal.maxHp(), EPS);
        assertEquals(6, normal.damage(), EPS);
        assertEquals(1.0, normal.goldMultiplier(), EPS);

        // 악몽(×2.4 HP, ×2.0 피해) + 4인 파티(HP ×(1+0.6×3), 피해 ×(1+0.08×3))
        double hp = 2.4 * 2.8, dmg = 2.0 * 1.24;
        MobStats party = MobStats.compute(60, 6, 2, 12, 1.0, hp, dmg, false);
        assertEquals(Math.round(60 * hp), party.maxHp(), EPS);
        assertEquals(6 * dmg, party.damage(), EPS);

        MobStats elite = MobStats.compute(60, 6, 2, 12, 1.0, 1.0, 1.0, true);
        assertEquals(60 * MobStats.ELITE_HP, elite.maxHp(), EPS);
        assertEquals(6 * MobStats.ELITE_DAMAGE, elite.damage(), EPS);
        assertEquals(12 * MobStats.ELITE_XP, elite.xp(), EPS);
        assertEquals(MobStats.ELITE_SCALE, elite.scale(), EPS);
        assertTrue(elite.goldMultiplier() > 1);

        MobStats broken = MobStats.compute(0, -5, -1, -3, 0, 0, 0, false);
        assertTrue(broken.maxHp() >= 1);
        assertEquals(0, broken.damage(), EPS);
        assertEquals(1.0, broken.scale(), EPS);
    }

    @Test
    void threatTopAndTaunt() {
        ThreatTable t = new ThreatTable();
        UUID a = UUID.randomUUID(), b = UUID.randomUUID(), c = UUID.randomUUID();
        t.add(a, 100);
        t.add(b, 250);
        t.add(c, 50);
        assertEquals(b, t.top(0, u -> true));
        assertEquals(a, t.top(0, u -> !u.equals(b)));

        t.taunt(c, 100);
        assertTrue(t.isTaunted(50));
        assertEquals(c, t.top(50, u -> true));
        assertTrue(t.get(c) > t.get(b), "도발자는 위협도 1위 이상");
        assertFalse(t.isTaunted(100));

        t.prune(u -> !u.equals(c));
        assertNull(t.taunter(0));
        assertEquals(b, t.top(200, u -> true));

        t.add(a, -10);
        t.add(a, Double.NaN);
        t.decay(0.5);
        assertEquals(125, t.get(b), EPS);
        t.clear();
        assertTrue(t.isEmpty());
        assertNull(t.top(0, u -> true));
    }

    @Test
    void geometryShapes() {
        assertTrue(Geometry.inCircle(0, 0, 3, 2, 2));
        assertFalse(Geometry.inCircle(0, 0, 3, 3, 3));
        assertTrue(Geometry.inRing(0, 0, 2, 4, 3, 0));
        assertFalse(Geometry.inRing(0, 0, 2, 4, 1, 0));
        assertFalse(Geometry.inRing(0, 0, 2, 4, 5, 0));
        // 선: +Z 방향 길이 10, 폭 2
        assertTrue(Geometry.inLine(0, 0, 0, 1, 10, 2, 0.9, 5));
        assertFalse(Geometry.inLine(0, 0, 0, 1, 10, 2, 1.1, 5));
        assertFalse(Geometry.inLine(0, 0, 0, 1, 10, 2, 0, -0.5));
        assertFalse(Geometry.inLine(0, 0, 0, 1, 10, 2, 0, 10.5));
        // 부채꼴: +X 방향 90°, 길이 5
        assertTrue(Geometry.inCone(0, 0, 1, 0, 90, 5, 3, 2.9));
        assertFalse(Geometry.inCone(0, 0, 1, 0, 90, 5, 3, 3.2));
        assertFalse(Geometry.inCone(0, 0, 1, 0, 90, 5, -1, 0));
        assertTrue(Geometry.inCone(0, 0, 1, 0, 90, 5, 0.1, 0.1), "원점 바로 위는 포함");
        assertEquals(0.25, Geometry.segmentDist2(0, 0, 0, 0, 0, 10, 0.5, 0, 5), EPS);
        assertEquals(0, Geometry.yawOf(0, 1), 1e-4);
        assertEquals(90, Geometry.yawOf(-1, 0), 1e-4);
        assertEquals(-90, Geometry.wrapDegrees(270), EPS);
        assertEquals(-1, Geometry.yawX(90), 1e-9);
    }

    @Test
    void rigComposeRotatesPivotWithYaw() {
        Vector3f tr = new Vector3f();
        Quaternionf left = new Quaternionf();
        RigMath.Pose id = RigMath.Pose.identity();
        // yaw 0: 앞(+Z) 피벗은 그대로
        float s = RigMath.compose(0, 2f, 0, 1, 0.5f, id, 0, tr, left);
        assertEquals(2f, s, 1e-6);
        assertEquals(0, tr.x, 1e-5);
        assertEquals(2, tr.y, 1e-5);
        assertEquals(1, tr.z, 1e-5);
        // yaw 90 (서쪽 −X 를 봄): 앞 피벗이 −X 로
        RigMath.compose(90, 1f, 0, 0, 1, id, 0, tr, left);
        assertEquals(-1, tr.x, 1e-5);
        assertEquals(0, tr.z, 1e-5);
        Vector3f fwd = left.transform(new Vector3f(0, 0, 1));
        assertEquals(-1, fwd.x, 1e-5);
        // 모델 방향 보정 180°
        RigMath.compose(0, 1f, 0, 0, 0, id, 180, tr, left);
        Vector3f back = left.transform(new Vector3f(0, 0, 1));
        assertEquals(-1, back.z, 1e-5);
    }

    @Test
    void rigAnimations() {
        RigMath.AnimState idle = new RigMath.AnimState(10, 0, -1, 0, -1, -1, 0, 0, -1, false, 7);
        RigMath.Pose body = RigMath.pose("body", "box", idle);
        assertTrue(Math.abs(body.offset().y) <= 0.0201);
        RigMath.Pose legs = RigMath.pose("legs_walk", "leg_pair", idle);
        assertEquals(1f, Math.abs(legs.rotation().w), 1e-5, "정지 시 다리 회전 0");
        // 공격: 0.3초 동안 −110° 까지 들었다가 0 으로
        assertEquals(0, RigMath_attack(0), 1e-9);
        assertEquals(-110, RigMath_attack(2), 6);
        assertEquals(0, RigMath_attack(RigMath.ATTACK_TICKS), 1e-9);
        RigMath.AnimState dying = new RigMath.AnimState(10, 0, -1, 0, -1, -1, 0, 0, RigMath.DEATH_TICKS, false, 7);
        RigMath.Pose dead = RigMath.pose("static", "box", dying);
        assertTrue(dead.scale() < 0.2f);
        assertTrue(dead.offset().y < -0.5f);
        RigMath.AnimState t1 = new RigMath.AnimState(0, 0, -1, 0, -1, -1, 0, 0, -1, false, 7);
        RigMath.AnimState t2 = new RigMath.AnimState(20, 0, -1, 0, -1, -1, 0, 0, -1, false, 7);
        assertNotEquals(RigMath.pose("spin", "ring", t1).rotation(), RigMath.pose("spin", "ring", t2).rotation());
        RigMath.Pose pulse = RigMath.pose("pulse", "sphere", t1);
        assertTrue(pulse.scale() >= 1.0f && pulse.scale() <= 1.061f);
        // 머리 회전 제한 ±45°
        RigMath.AnimState look = new RigMath.AnimState(0, 0, -1, 0, -1, -1, 170, 0, -1, true, 7);
        Vector3f f = RigMath.pose("head", "rounded", look).rotation().transform(new Vector3f(0, 0, 1));
        assertEquals(Math.cos(Math.toRadians(45)), f.z, 1e-4);
    }

    private static ModelDef.Part part(String name, String form, double px, double py, double pz, String anim) {
        return new ModelDef.Part(name, form, 6, 6, 6, px, py, pz, anim);
    }

    private static RigMath.AnimState state(long tick, double speed, boolean airborne, int motion, float headYaw) {
        return new RigMath.AnimState(tick, speed, -1, 0, -1, -1, headYaw, 0, -1, true, 7, airborne, motion, 0f, -1);
    }

    @Test
    void wingsFlapMirrorsAndFolds() {
        // 날 때: 왼쪽(+X) 날개 끝과 오른쪽(−X) 날개 끝은 좌우 대칭으로 같이 오르내린다
        for (long t = 0; t < 12; t += 3) {
            RigMath.AnimState fly = state(t, 0, true, RigMath.MOTION_NONE, 0);
            Vector3f l = RigMath.pose("wings_flap", "wing", fly, 1, 0).rotation().transform(new Vector3f(1, 0, 0));
            Vector3f r = RigMath.pose("wings_flap", "wing", fly, -1, 0).rotation().transform(new Vector3f(-1, 0, 0));
            assertEquals(l.y, r.y, 1e-4);
            assertEquals(-l.x, r.x, 1e-4);
        }
        // 급강하: 날개 끝이 뒤(−Z)로 접힌다
        Vector3f dive = RigMath.pose("wings_flap", "wing", state(5, 0, true, RigMath.MOTION_DIVE, 0), 1, 0).rotation()
                .transform(new Vector3f(1, 0, 0));
        assertTrue(dive.z < -0.6, "급강하 중 날개는 뒤로 접힘: " + dive);
        // 땅 위: 반쯤 접어 위·뒤로
        Vector3f rest = RigMath.pose("wings_flap", "wing", state(5, 0, false, RigMath.MOTION_NONE, 0), 1, 0).rotation()
                .transform(new Vector3f(1, 0, 0));
        assertTrue(rest.z < 0 && rest.y > 0, "땅 위 날개는 뒤로 접혀 위로: " + rest);
    }

    @Test
    void skeletonChainsNeckHeadJawAndTail() {
        List<ModelDef.Part> parts = List.of(
                part("body", "rounded", 0, 0.5, 0, "body"),
                part("neck", "neck", 0, 0.6, 0.3, "neck"),
                part("head", "rounded", 0, 0.9, 0.8, "head"),
                part("jaw", "claw", 0, 0.8, 0.9, "jaw"),
                part("horns", "horn_pair", 0, 1.05, 0.7, "head"),
                part("tail_1", "tail", 0, 0.5, -0.4, "tail_chain"),
                part("tail_2", "tail", 0, 0.5, -0.8, "tail_chain"));
        RigMath.Skeleton sk = new RigMath.Skeleton(parts);
        // 대상이 왼쪽 45°: 목이 절반을 돌고 머리가 목 끝에 붙어 함께 옮겨 간다
        RigMath.Solved[] o = sk.solve(state(0, 0, false, RigMath.MOTION_NONE, 45));
        Vector3f headFwd = o[2].rotation().transform(new Vector3f(0, 0, 1));
        assertTrue(headFwd.x < -0.5, "머리는 대상 쪽으로 (목 + 머리 합): " + headFwd);
        assertTrue(Math.abs(o[2].pivot().x) > 0.05, "목이 돌면 머리 피벗도 옆으로 옮겨 감");
        // 턱·뿔은 머리 피벗을 기준으로 머리와 같은 거리 유지 (떨어지지 않음)
        Vector3f head = o[2].pivot();
        assertEquals(new Vector3f(0, -0.1f, 0.1f).length(), new Vector3f(o[3].pivot()).sub(head).length(), 1e-4);
        assertEquals(new Vector3f(0, 0.15f, -0.1f).length(), new Vector3f(o[4].pivot()).sub(head).length(), 1e-4);
        // 뿔(anim head)은 머리와 같은 회전 (yaw 를 두 번 받지 않음)
        Vector3f hornFwd = o[4].rotation().transform(new Vector3f(0, 0, 1));
        assertEquals(headFwd.x, hornFwd.x, 1e-4);
        // 꼬리 둘째 마디는 첫 마디 끝에 붙어 있다 (마디 길이 유지)
        for (long t = 0; t < 40; t += 7) {
            RigMath.Solved[] q = sk.solve(state(t, 0.2, false, RigMath.MOTION_NONE, 0));
            assertEquals(0.4, new Vector3f(q[6].pivot()).sub(q[5].pivot()).length(), 1e-4);
        }
        // 솟구침: 처음엔 모델이 바닥 아래, 다 올라오면 제자리
        RigMath.AnimState rising = new RigMath.AnimState(0, 0, -1, 0, -1, -1, 0, 0, -1, true, 7, false, 0, 0f, 0);
        assertTrue(sk.solve(rising)[0].pivot().y < 0, "솟구치기 시작 = 바닥 아래");
        RigMath.AnimState up = new RigMath.AnimState(0, 0, -1, 0, -1, -1, 0, 0, -1, true, 7, false, 0, 0f, RigMath.EMERGE_TICKS);
        assertEquals(0.5, sk.solve(up)[0].pivot().y, 0.03);
    }

    private static double RigMath_attack(int ticks) {
        RigMath.AnimState s = new RigMath.AnimState(0, 0, ticks, 0, -1, -1, 0, 0, -1, true, 0);
        Vector3f v = RigMath.pose("arm_right", "arm", s).rotation().transform(new Vector3f(0, -1, 0));
        // 팔(아래 방향)이 X 축으로 회전한 각도
        return Math.toDegrees(Math.atan2(v.z, -v.y)) * -1;
    }

    @Test
    void eliteVariantPicksNewSkillType() {
        MobDef def = new MobDef("t", "테스트", "", 1, "normal", "HUSK", 1, 60, 6, 2, 0.25, 12, new IntRange(1, 2), "melee",
                List.of(new MobDef.MobSkillDef("slam", 8, Params.EMPTY)), "t", false, Params.EMPTY, ModelDef.EMPTY, Params.EMPTY);
        Set<String> seen = new HashSet<>();
        for (long seed = 0; seed < 20; seed++) {
            MobDef.MobSkillDef s = EliteVariants.pick(def, seed);
            assertNotNull(s);
            assertNotEquals("slam", s.type());
            seen.add(s.type());
        }
        assertTrue(seen.size() >= 2);
        MobDef caster = new MobDef("c", "c", "", 1, "normal", "HUSK", 1, 60, 6, 2, 0.25, 12, new IntRange(1, 2), "caster",
                List.of(), "c", false, Params.EMPTY, ModelDef.EMPTY, Params.EMPTY);
        assertNotNull(EliteVariants.pick(caster, -7));
    }
}
