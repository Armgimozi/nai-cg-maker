package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** 기믹 배율(GDD §8.4 + 난이도)·도형 판정·아레나 배치 수학. */
class BossScalingTest {

    private static Params p(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return Params.of(m);
    }

    @Test
    void partyCountFormulasMatchGdd() {
        // root_snare: 2 + floor((n-1) × 0.34)
        assertEquals(2, BossMath.count(2, 0.34, 1));
        assertEquals(2, BossMath.count(2, 0.34, 3));
        assertEquals(3, BossMath.count(2, 0.34, 4));
        assertEquals(5, BossMath.count(2, 0.34, 10));
        // moss_pillars: 4 + floor((n-1)/4)
        assertEquals(4, BossMath.countPerMembers(4, 4, 1));
        assertEquals(4, BossMath.countPerMembers(4, 4, 4));
        assertEquals(5, BossMath.countPerMembers(4, 4, 5));
        assertEquals(6, BossMath.countPerMembers(4, 4, 9));
        // 오브젝트 HP: 220 × (1 + 0.5 × (n−1))
        assertEquals(220, BossMath.objectHp(220, 0.5, 1), 1e-9);
        assertEquals(220 * 3.0, BossMath.objectHp(220, 0.5, 5), 1e-9);
        // 모이기 분배
        assertEquals(10, BossMath.shareDamage(40, 4, 1), 1e-9);
        assertEquals(40, BossMath.shareDamage(40, 0, 1), 1e-9);
        assertEquals(20, BossMath.shareDamage(40, 1, 2), 1e-9);
    }

    @Test
    void mechanicScalingByDifficultyAndPhase() {
        MechanicScaling normal = new MechanicScaling(4, "normal", 1, false);
        MechanicScaling nightmare = new MechanicScaling(4, "nightmare", 1, false);
        MechanicScaling easy = new MechanicScaling(4, "easy", 1, false);
        assertEquals(1.0, normal.cooldownMult(), 1e-9);
        assertTrue(nightmare.cooldownMult() < normal.cooldownMult());
        assertTrue(easy.cooldownMult() > normal.cooldownMult());
        assertEquals(0.9, normal.withPhase(3).cooldownMult(), 1e-9);
        assertEquals(Math.max(MechanicScaling.MIN_COOLDOWN_MULT, 0.8 * 0.9 * MechanicScaling.ENRAGE_COOLDOWN),
                nightmare.withPhase(3).withEnraged(true).cooldownMult(), 1e-9);
        // 추가 개수: 악몽 +1, 6명 이상 어려움 +1, 악몽 +2
        assertEquals(0, normal.extraCount());
        assertEquals(1, nightmare.extraCount());
        assertEquals(0, new MechanicScaling(4, "hard", 1, false).extraCount());
        assertEquals(1, new MechanicScaling(6, "hard", 1, false).extraCount());
        assertEquals(2, new MechanicScaling(8, "nightmare", 1, false).extraCount());
        assertTrue(nightmare.speedMult() > 1 && easy.speedMult() < 1);
        assertTrue(nightmare.timerMult() < 1 && easy.timerMult() > 1);
        // 알 수 없는 난이도 = 보통
        assertEquals(1.0, new MechanicScaling(1, "custom", 1, false).cooldownMult(), 1e-9);
        assertTrue(new MechanicScaling(1, null, 1, false).solo());
    }

    @Test
    void mechanicScalingFollowsFloorRamp() {
        // 악몽 1층(ramp 0) = 보통과 같은 패턴: 쿨 ×1.0 · 추가 +0 · 속도·오브젝트 HP·제한 시간 ×1.0
        MechanicScaling f1 = new MechanicScaling(1, "nightmare", 1, false, 0.0);
        assertEquals(1.0, f1.cooldownMult(), 1e-9);
        assertEquals(0, f1.extraCount());
        assertEquals(1.0, f1.speedMult(), 1e-9);
        assertEquals(1.0, f1.objectHpMult(), 1e-9);
        assertEquals(1.0, f1.timerMult(), 1e-9);
        // 3층(0.4): 쿨 ×0.92, 추가는 아직 0 / 4층(0.6): ×0.88, +1 / 6층(1.0): ×0.8, +1
        MechanicScaling f3 = new MechanicScaling(1, "nightmare", 1, false, 0.4);
        assertEquals(0.92, f3.cooldownMult(), 1e-9);
        assertEquals(0, f3.extraCount());
        assertEquals(1.08, f3.speedMult(), 1e-9);
        assertEquals(1.24, f3.objectHpMult(), 1e-9);
        assertEquals(0.92, f3.timerMult(), 1e-9);
        MechanicScaling f4 = new MechanicScaling(1, "nightmare", 1, false, 0.6);
        assertEquals(0.88, f4.cooldownMult(), 1e-9);
        assertEquals(1, f4.extraCount());
        MechanicScaling full = new MechanicScaling(1, "nightmare", 1, false, 1.0);
        assertEquals(new MechanicScaling(1, "nightmare", 1, false), full, "4인자 = 램프 다 오름");
        assertEquals(0.8, full.cooldownMult(), 1e-9);
        assertEquals(1, full.extraCount());
        // 어려움 2층(1/3): 쿨 ×0.967, 6인 이상 추가 +1 은 ramp 0.5 부터
        assertEquals(1 - 0.1 / 3, new MechanicScaling(4, "hard", 1, false, 1 / 3.0).cooldownMult(), 1e-9);
        assertEquals(0, new MechanicScaling(6, "hard", 1, false, 1 / 3.0).extraCount());
        assertEquals(1, new MechanicScaling(6, "hard", 1, false, 2 / 3.0).extraCount());
        // 페이즈·광폭화는 램프 뒤에 곱하고, withPhase/withEnraged 는 램프를 이어받는다
        assertEquals(0.92 * 0.9 * MechanicScaling.ENRAGE_COOLDOWN, f3.withPhase(3).withEnraged(true).cooldownMult(), 1e-9);
        assertEquals(0.4, f3.withPhase(2).withEnraged(true).ramp(), 1e-9);
        assertEquals(0.9, f1.withPhase(3).cooldownMult(), 1e-9);
        // 개수: 악몽 1층은 보통과 같은 수
        Params brand = p("count_base", 1, "count_per_member", 0.5, "max", 5);
        assertEquals(new MechanicScaling(5, "normal", 1, false).count(brand, "count", 1, 0),
                new MechanicScaling(5, "nightmare", 1, false, 0.0).count(brand, "count", 1, 0));
        assertEquals(20 * 12, f1.cooldownTicks(12));
        // 범위 밖·NaN 은 자른다
        assertEquals(1.0, new MechanicScaling(1, "nightmare", 1, false, 7).ramp(), 1e-9);
        assertEquals(0.0, new MechanicScaling(1, "nightmare", 1, false, -1).ramp(), 1e-9);
        assertEquals(1.0, new MechanicScaling(1, "nightmare", 1, false, Double.NaN).ramp(), 1e-9);
        // 쉬움·보통은 램프가 없어도(ramp 1) 그대로
        assertEquals(1.15, new MechanicScaling(1, "easy", 1, false, 1.0).cooldownMult(), 1e-9);
    }

    @Test
    void scaledCountUsesYamlKeysPlusDifficultyAndCap() {
        Params brand = p("count_base", 1, "count_per_member", 0.5, "max", 5);
        assertEquals(1, new MechanicScaling(1, "normal", 1, false).count(brand, "count", 1, 0));
        assertEquals(3, new MechanicScaling(5, "normal", 1, false).count(brand, "count", 1, 0));
        assertEquals(4, new MechanicScaling(5, "nightmare", 1, false).count(brand, "count", 1, 0));
        assertEquals(5, new MechanicScaling(10, "nightmare", 1, false).count(brand, "count", 1, 0), "max 5 상한");
        assertEquals(2, new MechanicScaling(10, "normal", 1, false).count(brand, "count", 1, 2), "명시 상한");
        // solo_ 대체 값
        Params solo = p("count", 3, "solo_count", 1);
        assertEquals(1, new MechanicScaling(1, "normal", 1, false).count(solo, "count", 1, 0));
        assertEquals(3, new MechanicScaling(2, "normal", 1, false).count(solo, "count", 1, 0));
        // 오브젝트 HP: 난이도 배율까지
        Params egg = p("hp", 220, "hp_per_member", 0.5);
        assertEquals(220 * 2.5 * 1.6, new MechanicScaling(4, "nightmare", 1, false).objectHp(egg, 100), 1e-6);
        assertEquals(220 * 0.8, new MechanicScaling(1, "easy", 1, false).objectHp(egg, 100), 1e-6);
        // 쿨다운 틱
        assertEquals(240, new MechanicScaling(1, "normal", 1, false).cooldownTicks(12));
        assertEquals(20, new MechanicScaling(1, "nightmare", 3, true).cooldownTicks(0.1), "최소 1초");
    }

    @Test
    void telegraphShapes() {
        // circle
        assertTrue(BossMath.inCircle(0, 0, 5, 3, 4));
        assertFalse(BossMath.inCircle(0, 0, 5, 3.1, 4));
        // ring (도넛)
        assertFalse(BossMath.inRing(0, 0, 2, 6, 1, 1));
        assertTrue(BossMath.inRing(0, 0, 2, 6, 4, 0));
        assertFalse(BossMath.inRing(0, 0, 2, 6, 7, 0));
        // line: +Z 로 길이 10, 폭 4
        assertTrue(BossMath.inLine(0, 0, 0, 1, 10, 4, 1.9, 9.9));
        assertFalse(BossMath.inLine(0, 0, 0, 1, 10, 4, 2.1, 5));
        assertFalse(BossMath.inLine(0, 0, 0, 1, 10, 4, 0, -0.5));
        assertFalse(BossMath.inLine(0, 0, 0, 1, 10, 4, 0, 10.5));
        // cone: +X 방향 90°, 길이 6
        assertTrue(BossMath.inCone(0, 0, 1, 0, 90, 6, 4, 3.9));
        assertFalse(BossMath.inCone(0, 0, 1, 0, 90, 6, 4, 4.2));
        assertFalse(BossMath.inCone(0, 0, 1, 0, 90, 6, -1, 0));
        assertFalse(BossMath.inCone(0, 0, 1, 0, 90, 6, 6.1, 0));
        assertTrue(BossMath.inCone(0, 0, 1, 0, 90, 6, 0.1, -0.1), "보스 발밑은 맞음");
        // tile
        assertTrue(BossMath.inTile(-10, -10, 2, 3, 3, -10 + 6.5, -10 + 9.1));
        assertEquals(2, BossMath.tileOf(-10, 3, -3.5));
        // 높이 차
        assertTrue(BossMath.heightOk(64, 66.9));
        assertFalse(BossMath.heightOk(64, 67.5));
        // 선분 거리
        assertEquals(1.0, BossMath.segmentDist2(0, 0, 10, 0, 5, 1), 1e-9);
        assertEquals(4.0, BossMath.segmentDist2(0, 0, 10, 0, 12, 0), 1e-9);
    }

    @Test
    void yawConventionMatchesMinecraft() {
        assertEquals(0f, BossMath.yawOf(0, 1), 1e-4);     // +Z = 남 = yaw 0
        assertEquals(90f, BossMath.yawOf(-1, 0), 1e-4);   // −X = 서 = yaw 90
        assertEquals(-90f, BossMath.yawOf(1, 0), 1e-4);
        assertEquals(1.0, BossMath.yawZ(0), 1e-9);
        assertEquals(-1.0, BossMath.yawX(90), 1e-9);
        assertEquals(20f, BossMath.yawDelta(350, 10), 1e-4);
        assertEquals(-20f, BossMath.yawDelta(10, 350), 1e-4);
        assertEquals(22f, BossMath.turn(10, 100, 12), 1e-4);
        assertEquals(100f, BossMath.turn(95, 100, 12), 1e-4);
    }

    @Test
    void arenaPlacementAvoidsStairsAndSpreadsEvenly() {
        for (int n = 1; n <= 8; n++) {
            double[] a = BossMath.ringAngles(n, 90, 26);
            assertEquals(n, a.length);
            for (double ang : a) {
                assertTrue(BossMath.angleGap(ang, 90) >= 20, "n=" + n + " ang=" + ang);
                // 반경 8 기둥(반경 1)이 계단 구역(|x|≤2.5, z 2~11)과 겹치지 않음
                double x = BossMath.ax(ang) * 8, z = BossMath.az(ang) * 8;
                assertFalse(BossMath.inStairZone(x, z, 2.5 - 1.5), "n=" + n + " ang=" + ang);
            }
        }
        assertTrue(BossMath.inStairZone(0, 5, 2));
        assertFalse(BossMath.inStairZone(0, -5, 2));
        assertFalse(BossMath.inStairZone(4, 5, 2));
    }

    @Test
    void bossAnimOverlayIsBoundedAndNeutralAtRest() {
        BossAnim.Pose pose = BossAnim.overlay(BossAnim.NONE, "arm_left", "arm_left", 0.5, 0.7, 10, null);
        assertEquals(1f, pose.baseWeight, 1e-6);
        assertEquals(0f, pose.offset.length(), 1e-6);
        for (BossAnim a : BossAnim.values()) {
            for (String part : List.of("body", "head", "arm_left", "arm_right", "legs_walk", "jaw")) {
                for (double t = 0; t <= 1.0001; t += 0.1) {
                    BossAnim.Pose o = BossAnim.overlay(a, part, part, t, a.defaultWindup(), (long) (t * 40), null);
                    assertTrue(Float.isFinite(o.rotation.w) && Math.abs(o.rotation.lengthSquared() - 1) < 1e-3, a + "/" + part);
                    assertTrue(o.globalOffset.length() < 10, a + " offset");
                    assertTrue(o.scale > 0 && o.scale < 1.5f, a + " scale");
                }
            }
        }
        // 내려찍기: 준비 끝 무렵 팔이 머리 위(−X 회전)로 들려 있다
        BossAnim.Pose slam = BossAnim.overlay(BossAnim.SLAM, "arm_right", "arm_right", 0.7, 0.75, 0, null);
        org.joml.Vector3f down = new org.joml.Vector3f(0, -1, 0);
        slam.rotation.transform(down);
        assertTrue(down.y > 0.5, "팔 끝이 위를 향함: " + down);
    }

    @Test
    void floorBossesOneToFiveHaveImplementedPatternKeys() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        java.util.Set<String> implemented = java.util.Set.of(
                "vine_lash", "root_snare", "rampage_charge", "spore_burst", "sproutling_call", "moss_pillars", "overgrowth",
                "venom_spit", "foreleg_sweep", "silk_tether", "egg_sacs", "ceiling_ambush", "cocoon",
                "cap_slam", "puffball_toss", "spore_brand", "symbiosis_bloom", "brand_and_bloom", "mycelium_network",
                "key_strike", "anchor_hurl", "tidal_sweep", "rising_flood", "whirlpool", "floodling_tide",
                "hammer_swing", "forge_quake", "chain_grip", "molten_pour", "hammer_toss", "bellows_gale", "anvil_crush");
        int checked = 0;
        for (BossDef d : c.bosses().values()) {
            if (d.floor() > 5) continue;
            checked++;
            for (String k : d.patterns().keySet()) assertTrue(implemented.contains(k), d.id() + " 패턴 미구현: " + k);
            for (List<String> rot : d.rotation().values()) for (String k : rot) assertTrue(d.patterns().containsKey(k), d.id() + " rotation 키: " + k);
            assertEquals(3, d.phases().size(), d.id());
        }
        assertEquals(5, checked);
    }
}
