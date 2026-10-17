package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.bosses.impl.Floor07Logic;
import kr.labyrinth.bosses.impl.Floor07Logic.Polarity;
import kr.labyrinth.bosses.impl.Floor07Logic.PylonSpot;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** 지하 7층 다이아드 (GDD §7.7): 극성 배정·피해 배율·반사·파동·분광 광선 흡수 순서·기둥 배치·솔로 대체·YAML 키. */
class Floor07DyadTest {

    private static final Polarity L = Polarity.LIGHT;
    private static final Polarity D = Polarity.DARK;

    @Test
    void alternateAssignmentAndLateJoiners() {
        assertEquals(List.of(L), Floor07Logic.assignAlternate(1), "솔로는 빛으로 시작");
        assertEquals(List.of(L, D, L, D, L), Floor07Logic.assignAlternate(5));
        assertTrue(Floor07Logic.assignAlternate(0).isEmpty());
        // 나중에 들어온 사람 = 적은 쪽, 같으면 빛
        assertEquals(D, Floor07Logic.forLateJoiner(3, 2));
        assertEquals(L, Floor07Logic.forLateJoiner(2, 2));
        assertEquals(L, Floor07Logic.forLateJoiner(1, 2));
        assertEquals(L, Floor07Logic.forLateJoiner(0, 0));
        assertEquals(D, L.opposite());
        assertEquals(L, D.opposite());
        assertEquals(L, Polarity.byName("light"));
        assertEquals(L, Polarity.byName(" 빛 "));
        assertEquals(D, Polarity.byName("dark"));
        assertEquals(D, Polarity.byName(null));
    }

    @Test
    void faceDamageMultiplier() {
        // 얼굴과 반대 +25%, 같으면 −50%
        assertEquals(1.25, Floor07Logic.damageMult(L, D, 0.25, 0.5), 1e-9);
        assertEquals(1.25, Floor07Logic.damageMult(D, L, 0.25, 0.5), 1e-9);
        assertEquals(0.5, Floor07Logic.damageMult(L, L, 0.25, 0.5), 1e-9);
        assertEquals(0.5, Floor07Logic.damageMult(D, D, 0.25, 0.5), 1e-9);
        assertEquals(1.0, Floor07Logic.damageMult(null, D, 0.25, 0.5), 1e-9, "극성 없음 = 배율 없음");
        assertEquals(0.0, Floor07Logic.damageMult(L, L, 0.25, 1.5), 1e-9, "음수 배율 금지");
    }

    @Test
    void refractionReflectsOnlySamePolarity() {
        // 굴절 중 + 얼굴과 같은 극성 → 피해의 50% 반사 (상한)
        assertEquals(500, Floor07Logic.reflected(L, L, true, 1000, 0.5, 0), 1e-9);
        assertEquals(300, Floor07Logic.reflected(D, D, true, 1000, 0.5, 300), 1e-9, "상한");
        assertEquals(0, Floor07Logic.reflected(D, L, true, 1000, 0.5, 0), 1e-9, "반대 극성은 반사 없음");
        assertEquals(0, Floor07Logic.reflected(L, L, false, 1000, 0.5, 0), 1e-9, "굴절 아닐 때 없음");
        assertEquals(0, Floor07Logic.reflected(null, L, true, 1000, 0.5, 0), 1e-9);
        assertEquals(0, Floor07Logic.reflected(L, L, true, 0, 0.5, 0), 1e-9);
    }

    @Test
    void polarityWaveSparesSameColor() {
        assertEquals(0, Floor07Logic.waveMult(L, L, 3.0), 1e-9);
        assertEquals(3.0, Floor07Logic.waveMult(D, L, 3.0), 1e-9);
        assertEquals(3.0, Floor07Logic.waveMult(null, L, 3.0), 1e-9, "극성 없는 사람은 못 피함");
        assertEquals(List.of(D, L), Floor07Logic.waveSequence(D, true), "3페이즈 2연속은 반대 색");
        assertEquals(List.of(L), Floor07Logic.waveSequence(L, false));
    }

    @Test
    void splitBeamAbsorbOrder() {
        double soak = 0.6, full = 3.0;
        // 아무도 막지 않음: 다른 극성 대상만 → 3.0
        assertArrayEquals(new double[]{3.0}, Floor07Logic.resolveBeam(new double[]{10}, new Polarity[]{D}, L, soak, full), 1e-9);
        // 대상이 광선과 같은 색 → 스스로 흡수 0.6 (솔로 대응)
        assertArrayEquals(new double[]{0.6}, Floor07Logic.resolveBeam(new double[]{10}, new Polarity[]{L}, L, soak, full), 1e-9);
        // 같은 색 동료가 대상 앞(보스 쪽) → 동료 0.6, 대상 0
        assertArrayEquals(new double[]{0.0, 0.6},
                Floor07Logic.resolveBeam(new double[]{12, 5}, new Polarity[]{D, L}, L, soak, full), 1e-9);
        // 흡수자보다 앞의 다른 극성은 맞고, 흡수자 뒤는 무사 (입력 순서 유지)
        assertArrayEquals(new double[]{3.0, 0.6, 0.0, 0.0},
                Floor07Logic.resolveBeam(new double[]{2, 6, 9, 14}, new Polarity[]{D, L, L, D}, L, soak, full), 1e-9);
        // 같은 색이 대상 뒤에 있으면 못 막음 → 대상 3.0, 뒤 사람이 흡수
        assertArrayEquals(new double[]{3.0, 0.6},
                Floor07Logic.resolveBeam(new double[]{8, 15}, new Polarity[]{D, L}, L, soak, full), 1e-9);
        // 극성 없는 사람은 흡수 못 함
        assertArrayEquals(new double[]{3.0, 3.0},
                Floor07Logic.resolveBeam(new double[]{3, 9}, new Polarity[]{null, D}, L, soak, full), 1e-9);
        assertEquals(0, Floor07Logic.resolveBeam(new double[0], new Polarity[0], L, soak, full).length);
        // 흡수자 = 보스에 가장 가까운 같은 색
        assertEquals(1, Floor07Logic.absorberIndex(new double[]{2, 6, 9}, new Polarity[]{D, L, L}, L));
        assertEquals(-1, Floor07Logic.absorberIndex(new double[]{2, 6}, new Polarity[]{D, D}, L));
    }

    @Test
    void beamLineGeometry() {
        // 보스 (0,0) → 대상 (0,10) 방향, 폭 1.5 길이 22: 옆으로 0.7 은 안, 0.8 은 밖
        assertTrue(BossMath.inLine(0, 0, 0, 1, 22, 1.5, 0.7, 5));
        assertFalse(BossMath.inLine(0, 0, 0, 1, 22, 1.5, 0.8, 5));
        assertFalse(BossMath.inLine(0, 0, 0, 1, 22, 1.5, 0, -1), "보스 뒤는 밖");
        assertTrue(BossMath.inLine(0, 0, 0, 1, 22, 1.5, 0, 22));
        // 아레나 전체 파동 원(반경 17)은 반경 16 아레나 끝까지 덮는다
        assertTrue(BossMath.inCircle(0, 0, 17, 16, 0));
        // 수정 궤도 r4
        assertTrue(BossMath.inCircle(0, 0, 4, 2.8, 2.8));
        assertFalse(BossMath.inCircle(0, 0, 4, 3, 3));
    }

    @Test
    void soloFallbacks() {
        // 솔로 광선: 기둥을 쓸 수 있으면 반대 색(바꿔서 0.6배), 대기 중이면 지금 색(그대로 흡수)
        assertEquals(D, Floor07Logic.soloBeamColor(L, true));
        assertEquals(L, Floor07Logic.soloBeamColor(L, false));
        assertEquals(D, Floor07Logic.soloBeamColor(null, true));
        assertEquals(0, Floor07Logic.swapRemaining(100, 80));
        assertEquals(20, Floor07Logic.swapRemaining(100, 120));
        // 얼굴 전환: 20초, 3페이즈 10초
        assertEquals(20, Floor07Logic.faceInterval(1, 20, 10), 1e-9);
        assertEquals(20, Floor07Logic.faceInterval(2, 20, 10), 1e-9);
        assertEquals(10, Floor07Logic.faceInterval(3, 20, 10), 1e-9);
        assertEquals(20, Floor07Logic.faceInterval(3, 20, 0), 1e-9);
    }

    @Test
    void pylonPairsFlankTheArenaAwayFromStairsAndEntrance() {
        for (int total : new int[]{2, 4, 6, 8}) {
            List<PylonSpot> spots = Floor07Logic.pylonLayout(total, 28);
            assertEquals(Math.max(2, total), spots.size(), "기둥 수 " + total);
            long light = spots.stream().filter(s -> s.polarity() == L).count();
            assertEquals(spots.size() / 2, light, "빛·어둠 같은 수");
            for (PylonSpot s : spots) {
                double dx = BossMath.ax(s.angle()) * 12, dz = BossMath.az(s.angle()) * 12;
                assertFalse(BossMath.inStairZone(dx, dz, 2.5), "남쪽 계단 자리: " + s);
                assertTrue(BossMath.angleGap(s.angle(), 270) > 15, "북쪽 입구 앞: " + s);
            }
            // 쌍마다: 북쪽(입구 쪽)이 빛, 둘 사이 거리는 한두 걸음 (2연속 파동을 쌍 사이에서 처리)
            for (int i = 0; i + 1 < spots.size(); i += 2) {
                PylonSpot a = spots.get(i), b = spots.get(i + 1);
                assertEquals(L, a.polarity());
                assertEquals(D, b.polarity());
                assertEquals(28, BossMath.angleGap(a.angle(), b.angle()), 1e-6);
                assertTrue(BossMath.angleGap(a.angle(), 270) <= BossMath.angleGap(b.angle(), 270));
                double chord = 2 * 12 * Math.sin(Math.toRadians(14));
                assertTrue(chord > 4 && chord < 7, "쌍 간격 " + chord);
            }
        }
        // 기본(4) = 동·서 양쪽
        List<PylonSpot> four = Floor07Logic.pylonLayout(4, 28);
        assertEquals(346, four.get(0).angle(), 1e-6);
        assertEquals(14, four.get(1).angle(), 1e-6);
        assertEquals(194, four.get(2).angle(), 1e-6);
        assertEquals(166, four.get(3).angle(), 1e-6);
    }

    @Test
    void crystalRainCountFollowsPartyFormula() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        Params rain = c.bosses().get("floor07_dyad").pattern("crystal_rain");
        // 4 + (n−1)
        assertEquals(4, new MechanicScaling(1, "normal", 1, false).count(rain, "count", 4, 24));
        assertEquals(8, new MechanicScaling(5, "normal", 1, false).count(rain, "count", 4, 24));
        assertEquals(13, new MechanicScaling(10, "normal", 1, false).count(rain, "count", 4, 24));
        assertEquals(9, new MechanicScaling(5, "nightmare", 1, false).count(rain, "count", 4, 24), "악몽 +1");
    }

    @Test
    void yamlMatchesImplementation() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        BossDef d = c.bosses().get("floor07_dyad");
        assertNotNull(d);
        assertEquals("polarity", d.core());
        assertEquals(7, d.floor());
        assertEquals(36000, d.hp(), 1e-9);
        assertEquals(List.of(1.0, 0.6, 0.3), d.phases());
        Set<String> implemented = Set.of("polarity_assign", "face_shift", "polarity_wave", "split_beam", "prism_refraction",
                "crystal_rain", "shard_orbit", "answer");
        for (String k : d.patterns().keySet()) assertTrue(implemented.contains(k), "패턴 미구현: " + k);
        for (String k : implemented) assertTrue(d.patterns().containsKey(k), "YAML 에 없음: " + k);
        for (List<String> rot : d.rotation().values()) for (String k : rot) assertTrue(d.patterns().containsKey(k), "rotation 키: " + k);
        // 스케줄러 분류: 쿨다운 패턴 5개, 상시 기믹 2개는 rotation 밖
        for (String k : List.of("shard_orbit", "crystal_rain", "polarity_wave", "split_beam", "prism_refraction")) {
            assertEquals(PatternScheduler.Kind.COOLDOWN, PatternScheduler.kindOf(d.pattern(k)), k);
        }
        assertEquals(List.of("shard_orbit", "crystal_rain", "polarity_wave"), d.rotation().get(1));
        assertTrue(d.rotation().get(2).contains("split_beam"));
        assertTrue(d.rotation().get(3).contains("prism_refraction"));
        for (List<String> rot : d.rotation().values()) {
            assertFalse(rot.contains("polarity_assign"));
            assertFalse(rot.contains("face_shift"));
        }
        // GDD 수치
        assertEquals(3.0, d.pattern("polarity_wave").dbl("damage", 0), 1e-9);
        assertEquals(3.0, d.pattern("polarity_wave").dbl("windup", 0), 1e-9);
        assertEquals(2.5, d.pattern("polarity_wave").dbl("p3_gap", 0), 1e-9);
        assertEquals(0.6, d.pattern("split_beam").dbl("soak_damage", 0), 1e-9);
        assertEquals(22, d.pattern("split_beam").dbl("length", 0), 1e-9);
        assertEquals(1.5, d.pattern("split_beam").dbl("width", 0), 1e-9);
        assertEquals(0.5, d.pattern("prism_refraction").dbl("reflect_ratio", 0), 1e-9);
        assertEquals(6, d.pattern("prism_refraction").dbl("duration", 0), 1e-9);
        assertEquals(10, d.pattern("face_shift").phased("interval", 3, 0), 1e-9);
        assertEquals(20, d.pattern("face_shift").phased("interval", 2, 0), 1e-9);
        assertEquals(5, d.pattern("polarity_assign").dbl("swap_cooldown", 0), 1e-9);
        // 얼굴 전환은 모델 파트 light_half / dark_half 를 밝힌다
        Set<String> parts = new java.util.HashSet<>();
        for (var part : d.model().parts()) parts.add(part.name());
        assertTrue(parts.contains("light_half") && parts.contains("dark_half"), "모델 파트: " + parts);
        // 패턴이 쓰는 fx 모델(fx / fx_*)은 전부 fx.yml 에 있다
        for (Map.Entry<String, Params> e : d.patterns().entrySet()) {
            for (String k : e.getValue().keys()) {
                if (!k.equals("fx") && !k.startsWith("fx_")) continue;
                String fx = e.getValue().str(k);
                assertTrue(c.fxModels().containsKey(fx), e.getKey() + "." + k + " → 없는 fx 모델 " + fx);
            }
        }
        for (String fx : List.of("telegraph_light", "telegraph_dark", "telegraph_beam_light", "telegraph_beam_dark", "beam_light", "beam_dark",
                "pylon_light", "pylon_dark", "marker_light", "marker_dark", "refraction_shell", "proj_crystal", "telegraph_circle")) {
            assertTrue(c.fxModels().containsKey(fx), "fx.yml: " + fx);
        }
    }
}
