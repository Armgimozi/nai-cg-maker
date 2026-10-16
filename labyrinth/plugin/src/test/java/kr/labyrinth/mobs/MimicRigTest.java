package kr.labyrinth.mobs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.core.ContentLoader;
import org.joml.Vector3f;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 미믹 리그 (anim lid + 깡충 걸음, GDD §14.3): 뚜껑은 뒤 경첩에서 위로 열리고, 물 때 크게 벌렸다 쾅 닫히며, 쉴 때는 살짝 벌어진 채
 * 딱딱 씹고, 죽으면 닫힌다. 다리 없는 lid 몹은 깡충 뛰고(이동 중에만), 다리 있는 몹·다른 몹의 걸음은 그대로.
 */
class MimicRigTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    private static RigMath.AnimState st(long tick, double speed, int atk, int cast, int death, boolean target, boolean air) {
        return new RigMath.AnimState(tick, speed, atk, 0, cast, -1, 0f, 0f, death, target, 7L, air, RigMath.MOTION_NONE, 0f, -1);
    }

    private static List<ModelDef.Part> parts(String id) { return content.mob(id).model().parts(); }

    private static int idx(List<ModelDef.Part> ps, String name) {
        for (int i = 0; i < ps.size(); i++) if (ps.get(i).name().equals(name)) return i;
        throw new AssertionError(name);
    }

    /** 파트의 쉴 때 한 점(몹 로컬 블록)이 지금 있는 곳. */
    private static Vector3f world(RigMath.Solved s, ModelDef.Part p, double x, double y, double z) {
        Vector3f rel = new Vector3f((float) (x - p.pivotX()), (float) (y - p.pivotY()), (float) (z - p.pivotZ()));
        return s.rotation().transform(rel).mul(s.scale()).add(s.pivot());
    }

    @Test
    void lidAngles() {
        // 쉼: 살짝 벌어짐 (안쪽 눈·이빨이 비침), 씹기는 작게
        for (long t = 1000; t < 1090; t++) {
            double rest = RigMath.lidAngle(st(t, 0, -1, -1, -1, false, false), 0, 0);
            assertTrue(rest >= RigMath.LID_REST - 1e-9 && rest <= 24, "쉴 때 " + rest);
            double chatter = RigMath.lidAngle(st(t, 0, -1, -1, -1, true, false), 0, 0);
            assertTrue(chatter >= RigMath.LID_REST - 1e-9 && chatter <= 24, "씹기 " + chatter);
        }
        // 대상이 있으면 30틱 안에 한 번은 딱딱 (14°) 벌어진다
        double max = 0;
        for (long t = 1000; t < 1030; t++) max = Math.max(max, RigMath.lidAngle(st(t, 0, -1, -1, -1, true, false), 0, 0));
        assertTrue(max > 15, "씹기 " + max);
        // 물기: 크게 벌렸다(2~2.5틱) → 4틱에 쾅 (기본 공격 피해 = 3틱 뒤)
        assertTrue(RigMath.lidAngle(st(1000, 0, 2, -1, -1, true, false), 0, 0) > 50);
        assertEquals(RigMath.LID_REST, RigMath.lidAngle(st(1000, 0, 0, -1, -1, true, false), 0, 0), 1e-6, "물기 시작 = 쉼 각에서");
        assertTrue(RigMath.lidAngle(st(1000, 0, 3, -1, -1, true, false), 0, 0) < RigMath.LID_BITE, "3틱에는 닫히는 중");
        assertEquals(0, RigMath.lidAngle(st(1000, 0, 4, -1, -1, true, false), 0, 0), 1e-6);
        // 도약 중(공중) 크게 벌림, 시전(준비) 중 벌림
        assertTrue(RigMath.lidAngle(st(1000, 0, -1, -1, -1, true, true), 0, 0) >= 45);
        assertTrue(RigMath.lidAngle(st(1000, 0, -1, 5, -1, true, false), 0, 0) >= 38);
        // 사망: 한 번 벌렸다가 닫히고 닫힌 채
        assertTrue(RigMath.lidAngle(st(1000, 0, -1, -1, 3, false, false), 0, 0) > 20);
        for (int d = 6; d <= RigMath.DEATH_TICKS; d++) assertEquals(0, RigMath.lidAngle(st(1000, 0, -1, -1, d, false, false), 0, 0), 1e-9);
    }

    @Test
    void lidHingesAtTheBackAndOpensUp() {
        List<ModelDef.Part> ps = parts("chest_mimic");
        RigMath.Skeleton sk = new RigMath.Skeleton(ps, 1.1);
        int lid = idx(ps, "lid");
        ModelDef.Part lp = ps.get(lid);
        RigMath.Solved[] rest = sk.solve(st(1000, 0, 4, -1, -1, true, false));
        RigMath.Solved[] bite = sk.solve(st(1000, 0, 2, -1, -1, true, false));
        // 경첩은 제자리, 앞 모서리는 위로·뒤로
        Vector3f hingeRest = world(rest[lid], lp, lp.jointX(), lp.jointY(), lp.jointZ());
        Vector3f hingeBite = world(bite[lid], lp, lp.jointX(), lp.jointY(), lp.jointZ());
        assertEquals(0, hingeRest.distance(hingeBite), 1e-3, "경첩은 제자리");
        double frontZ = lp.jointZ() + lp.sizeZ() / 16.0;
        Vector3f frontRest = world(rest[lid], lp, 0, lp.jointY(), frontZ);
        Vector3f frontBite = world(bite[lid], lp, 0, lp.jointY(), frontZ);
        assertTrue(frontBite.y - frontRest.y > 0.5, "물 때 뚜껑 앞이 크게 들림: " + frontRest + " → " + frontBite);
        assertTrue(frontBite.z < frontRest.z, "뒤로 젖혀짐");
        // 몸통(아래턱)은 물 때 움직이지 않는다
        int body = idx(ps, "body");
        assertEquals(0, rest[body].pivot().distance(bite[body].pivot()), 1e-3);
    }

    @Test
    void mimicsHopOtherMobsWalkAsBefore() {
        for (String id : List.of("chest_mimic", "gilded_mimic", "mimic_whelp")) {
            RigMath.Skeleton sk = new RigMath.Skeleton(parts(id), content.mob(id).scale());
            assertTrue(sk.hopper(), id);
            assertEquals(0, sk.walkingLegs(), id);
        }
        assertFalse(new RigMath.Skeleton(parts("ore_mimic")).hopper(), "다리 있는 광맥 흉내쟁이는 걷는다");
        assertFalse(new RigMath.Skeleton(parts("biting_tome")).hopper());
        assertFalse(new RigMath.Skeleton(parts("lantern_wisp")).hopper(), "다리 없는 다른 몹은 예전대로");
        // 깡충: 이동 중 공중 비율 가운데에서 가장 높고, 서 있으면 땅
        List<ModelDef.Part> ps = parts("chest_mimic");
        RigMath.Skeleton sk = new RigMath.Skeleton(ps, 1.1);
        int body = idx(ps, "body");
        double still = sk.solve(st(1000, 0, -1, -1, -1, true, false), new RigMath.Gait().set(RigMath.HOP_AIR / 2, 0, 2))[body].pivot().y;
        double peak = sk.solve(st(1000, 0.1, -1, -1, -1, true, false), new RigMath.Gait().set(RigMath.HOP_AIR / 2, 0, 2))[body].pivot().y;
        double land = sk.solve(st(1000, 0.1, -1, -1, -1, true, false), new RigMath.Gait().set(0.9, 0, 2))[body].pivot().y;
        assertTrue(peak - still > 0.15, "깡충 높이 " + (peak - still));
        assertEquals(still, land, 0.03, "땅에 닿은 동안은 제 높이");
        RigMath.Skeleton.Cadence c = sk.cadence(0.1, 2);
        assertTrue(c.ticksPerCycle() >= RigMath.HOP_TICKS_MIN && c.ticksPerCycle() <= RigMath.HOP_TICKS_MAX, "박자 " + c);
        assertEquals(0, sk.cadence(0, 2).amp(), 1e-9, "멈추면 안 뜀");
        // 깡충 위상 한 주기 동안 높이는 이어진다 (튀지 않음)
        double prev = RigMath.hopHeight(0, 1);
        for (int k = 1; k <= 100; k++) {
            double h = RigMath.hopHeight(k / 100.0, 1);
            assertTrue(Math.abs(h - prev) < 0.02, "높이가 끊김 @" + k);
            double p0 = RigMath.hopPitch((k - 1) / 100.0, 1), p1 = RigMath.hopPitch(k / 100.0, 1);
            assertTrue(Math.abs(p1 - p0) < 1.5, "앞뒤 젖힘이 끊김 @" + k);
            prev = h;
        }
    }
}
