package kr.labyrinth.bosses.impl;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.Arrays;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.bosses.BossMath;
import kr.labyrinth.bosses.MechanicScaling;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import org.junit.jupiter.api.Test;

/** 지하 6층 얼음관의 여제 시린 (GDD §7.6) — 인장 규칙·동상 판정·빙창 각도·영구 동토 관성·YAML 키. */
class Floor06LogicTest {

    private static final double EPS = 1e-9;

    @Test
    void classRolesMapToDamageTypes() {
        assertEquals(DamageType.MELEE, FrostLogic.roleDamage("tank", null));
        assertEquals(DamageType.MELEE, FrostLogic.roleDamage("melee", null));
        assertEquals(DamageType.MELEE, FrostLogic.roleDamage("assassin", null));
        assertEquals(DamageType.RANGED, FrostLogic.roleDamage("ranged", null));
        assertEquals(DamageType.MAGIC, FrostLogic.roleDamage("magic", null));
        assertEquals(DamageType.MAGIC, FrostLogic.roleDamage("healer", null));
        assertEquals(DamageType.MELEE, FrostLogic.roleDamage(null, null), "직업 없음 = 기본 공격(근접)");
        // YAML role_damage 가 우선, TRUE·잘못된 값은 무시
        assertEquals(DamageType.RANGED, FrostLogic.roleDamage("tank", Map.of("tank", "ranged")));
        assertEquals(DamageType.MELEE, FrostLogic.roleDamage("tank", Map.of("tank", "true")));
        assertEquals(DamageType.MAGIC, FrostLogic.roleDamage("healer", Map.of("healer", "???")));
        assertEquals(EnumSet.of(DamageType.MELEE, DamageType.MAGIC),
                FrostLogic.presentTypes(Arrays.asList("tank", "healer", "assassin", null), null));
    }

    @Test
    void everyClassInContentHasASigilType() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        Map<String, String> overrides = new java.util.HashMap<>();
        BossDef d = c.bosses().get("floor06_frost_empress");
        for (var e : d.pattern("glacier_shell").sub("role_damage").asMap().entrySet()) overrides.put(e.getKey(), e.getValue().toString());
        Set<DamageType> all = EnumSet.noneOf(DamageType.class);
        for (ClassDef cd : c.classes().values()) {
            assertTrue(overrides.containsKey(cd.role()), "role_damage 에 직업 역할이 없음: " + cd.role());
            all.add(FrostLogic.roleDamage(cd.role(), overrides));
        }
        assertEquals(EnumSet.of(DamageType.MELEE, DamageType.RANGED, DamageType.MAGIC), all, "6직업으로 세 인장을 모두 깰 수 있어야 함");
    }

    @Test
    void sigilRulesFollowGdd() {
        Set<DamageType> meleeAndMagic = EnumSet.of(DamageType.MELEE, DamageType.MAGIC);
        // 해당 유형을 낼 직업이 있으면 그 유형만
        FrostLogic.SigilRule melee = FrostLogic.sigilRule(DamageType.MELEE, meleeAndMagic, false, 1.5);
        assertTrue(melee.filtered());
        assertEquals(1.0, melee.hpMult(), EPS);
        // 없으면 모든 피해 허용 + HP ×1.5
        FrostLogic.SigilRule ranged = FrostLogic.sigilRule(DamageType.RANGED, meleeAndMagic, false, 1.5);
        assertFalse(ranged.filtered());
        assertEquals(1.5, ranged.hpMult(), EPS);
        // 솔로: 전부 허용, HP 배율 없음
        for (DamageType t : List.of(DamageType.MELEE, DamageType.RANGED, DamageType.MAGIC)) {
            FrostLogic.SigilRule s = FrostLogic.sigilRule(t, EnumSet.of(DamageType.RANGED), true, 1.5);
            assertFalse(s.filtered(), "솔로 " + t);
            assertEquals(1.0, s.hpMult(), EPS);
        }
        // 직업 정보가 없으면(관리자 소환 등) 필터 유지
        assertTrue(FrostLogic.sigilRule(DamageType.MAGIC, EnumSet.noneOf(DamageType.class), false, 1.5).filtered());
        // 배율이 1 미만이면 1
        assertEquals(1.0, FrostLogic.sigilRule(DamageType.MAGIC, EnumSet.of(DamageType.MELEE), false, 0.5).hpMult(), EPS);
    }

    @Test
    void sigilHpAndCastTime() {
        // 900 × (1 + 0.6 × (n−1))
        assertEquals(900, FrostLogic.sigilHp(900, 0.6, 1, 1.0, null), EPS);
        assertEquals(900 * 2.8, FrostLogic.sigilHp(900, 0.6, 4, 1.0, null), 1e-6);
        assertEquals(900 * 6.4, FrostLogic.sigilHp(900, 0.6, 10, 1.0, null), 1e-6);
        // 없는 역할 ×1.5, 악몽 오브젝트 HP ×1.6
        FrostLogic.SigilRule missing = new FrostLogic.SigilRule(DamageType.RANGED, false, 1.5);
        double nightmare = new MechanicScaling(4, "nightmare", 2, false).objectHpMult();
        assertEquals(900 * 2.8 * 1.6 * 1.5, FrostLogic.sigilHp(900, 0.6, 4, nightmare, missing), 1e-6);
        // 시전: 파티 12초 / 솔로 16초 × 난이도 제한 시간 배율
        assertEquals(240, FrostLogic.shellCastTicks(12, 16, false, 1.0));
        assertEquals(320, FrostLogic.shellCastTicks(12, 16, true, 1.0));
        assertEquals(Math.round(12 * 0.8 * 20), FrostLogic.shellCastTicks(12, 16, false, new MechanicScaling(4, "nightmare", 2, false).timerMult()));
        assertEquals(Math.round(16 * 1.25 * 20), FrostLogic.shellCastTicks(12, 16, true, new MechanicScaling(1, "easy", 2, false).timerMult()));
        assertEquals(60, FrostLogic.shellCastTicks(0.1, 0.1, false, 1.0), "최소 3초");
    }

    @Test
    void sigilTypesAndPhaseTriggers() {
        assertEquals(List.of(DamageType.MELEE, DamageType.RANGED, DamageType.MAGIC), FrostLogic.sigilTypes(List.of("melee", "ranged", "magic")));
        assertEquals(List.of(DamageType.MAGIC, DamageType.MELEE), FrostLogic.sigilTypes(List.of("magic", "true", "melee", "magic", "x")));
        assertEquals(3, FrostLogic.sigilTypes(List.of()).size(), "비면 기본 3종");
        assertEquals(3, FrostLogic.sigilTypes(null).size());
        assertTrue(FrostLogic.triggersAt(List.of(2, 3), 2));
        assertTrue(FrostLogic.triggersAt(List.of(2, 3), 3));
        assertFalse(FrostLogic.triggersAt(List.of(2, 3), 1));
        assertTrue(FrostLogic.triggersAt(List.of("3"), 3));
        assertFalse(FrostLogic.triggersAt(null, 2));
    }

    @Test
    void sigilRingAvoidsStairs() {
        // 인장 링 반경 10, 3개 — 남쪽 계단 구역과 겹치지 않고 서로 120° 간격
        double[] a = BossMath.ringAngles(3, 90, 30);
        assertEquals(3, a.length);
        for (int i = 0; i < a.length; i++) {
            assertTrue(BossMath.angleGap(a[i], 90) >= 30, "계단 방향과 떨어짐: " + a[i]);
            assertFalse(BossMath.inStairZone(BossMath.ax(a[i]) * 10, BossMath.az(a[i]) * 10, 2.5 + 0.7));
            assertEquals(120, BossMath.angleGap(a[i], a[(i + 1) % 3]), 1e-6);
        }
    }

    @Test
    void frostbiteMovementWindow() {
        assertTrue(FrostLogic.frostbiteStacks(0.0, 1.5), "제자리 = 중첩");
        assertTrue(FrostLogic.frostbiteStacks(1.49, 1.5));
        assertFalse(FrostLogic.frostbiteStacks(1.5, 1.5), "1.5칸 이상 = 무사");
        assertFalse(FrostLogic.frostbiteStacks(8, 1.5));
        assertFalse(FrostLogic.frostbiteStacks(Double.NaN, 1.5), "첫 판정(이전 위치 없음)은 중첩 없음");
    }

    @Test
    void glacialSpikeFanGeometry() {
        assertArrayEquals(new double[]{0}, FrostLogic.spreadOffsets(1, 35), EPS);
        assertArrayEquals(new double[]{-35, 0, 35}, FrostLogic.spreadOffsets(3, 35), EPS);
        assertArrayEquals(new double[]{-17.5, 17.5}, FrostLogic.spreadOffsets(2, 35), EPS);
        assertArrayEquals(new double[]{0}, FrostLogic.spreadOffsets(0, 35), EPS);
        // +X 를 90° 돌리면 +Z (x→z 방향)
        double[] r = FrostLogic.rotate(1, 0, 90);
        assertEquals(0, r[0], 1e-9);
        assertEquals(1, r[1], 1e-9);
        double[] n = FrostLogic.rotate(3, 4, 0);
        assertEquals(0.6, n[0], 1e-9);
        assertEquals(0.8, n[1], 1e-9);
        // 3갈래 35°: 가운데 선 위의 점은 옆 갈래(폭 2)에 들지 않는다 (거리 10 기준)
        double[] side = FrostLogic.rotate(0, 1, 35);
        assertTrue(BossMath.inLine(0, 0, 0, 1, 16, 2, 0, 10));
        assertFalse(BossMath.inLine(0, 0, side[0], side[1], 16, 2, 0, 10));
        // 갈래 사이(17.5°)로 가면 거리 10 에서 어느 선에도 없다
        double[] mid = FrostLogic.rotate(0, 1, 17.5);
        double px = mid[0] * 10, pz = mid[1] * 10;
        for (double off : FrostLogic.spreadOffsets(3, 35)) {
            double[] d = FrostLogic.rotate(0, 1, off);
            assertFalse(BossMath.inLine(0, 0, d[0], d[1], 16, 2, px, pz), "off=" + off);
        }
    }

    @Test
    void permafrostTileCount() {
        assertEquals(0, FrostLogic.tilesToFreeze(0, 0.3));
        assertEquals(1, FrostLogic.tilesToFreeze(2, 0.1), "최소 1");
        assertEquals(23, FrostLogic.tilesToFreeze(78, 0.3));
        assertEquals(10, FrostLogic.tilesToFreeze(10, 2.0), "최대 전부");
    }

    @Test
    void iceSlideKeepsMomentumAndDecays() {
        // 지난 틱 속도 0, 입력만으로 0.2 이동 → 입력 반영률 0.12 × 유지 0.9
        double[] v = FrostLogic.slide(0, 0, 0.2, 0, 0.9, 0.12, 0.5);
        assertEquals(0.9 * 0.12 * 0.2, v[0], 1e-9);
        assertEquals(0, v[1], EPS);
        // 입력을 멈춰도(이동 = 보낸 속도 그대로) 속도가 대부분 유지 → 미끄러짐
        double[] glide = FrostLogic.slide(0.3, 0, 0.3, 0, 0.9, 0.12, 0.5);
        assertEquals(0.27, glide[0], 1e-9);
        // 반대로 걸어도 바로 멈추지 않는다 (관성)
        double[] turn = FrostLogic.slide(0.3, 0, 0.1, 0, 0.9, 0.12, 0.5);
        assertTrue(turn[0] > 0.2, "관성: " + turn[0]);
        // 계속 굴리면 0 으로 수렴
        double[] s = {0.4, 0.1};
        for (int i = 0; i < 200; i++) s = FrostLogic.slide(s[0], s[1], s[0], s[1], 0.9, 0.12, 0.5);
        assertArrayEquals(new double[]{0, 0}, s, EPS);
        // 최대 속도
        double[] fast = FrostLogic.slide(2, 0, 3, 0, 0.9, 1.0, 0.5);
        assertEquals(0.5, Math.hypot(fast[0], fast[1]), 1e-9);
        // 유지율 상한 0.99 (무한 미끄러짐 방지)
        double[] cap = FrostLogic.slide(0.1, 0, 0.1, 0, 5, 0, 0);
        assertEquals(0.099, cap[0], 1e-9);
    }

    @Test
    void hailCountUsesPartyFormula() {
        BossDef d = ContentLoader.load(Path.of("src/main/resources/content")).content().bosses().get("floor06_frost_empress");
        Params b = d.pattern("blizzard");
        // 우박 6 + (n−1)
        assertEquals(6, new MechanicScaling(1, "normal", 2, false).count(b, "hail", 6, 20));
        assertEquals(9, new MechanicScaling(4, "normal", 2, false).count(b, "hail", 6, 20));
        assertEquals(15, new MechanicScaling(10, "normal", 2, false).count(b, "hail", 6, 20));
        assertEquals(17, new MechanicScaling(10, "nightmare", 2, false).count(b, "hail", 6, 20), "악몽 6인+ +2");
        // 빙창 3페이즈 3갈래 35°
        Params g = d.pattern("glacial_spikes");
        assertEquals(1, (int) Math.round(g.phased("count", 1, 1)));
        assertEquals(1, (int) Math.round(g.phased("count", 2, 1)));
        assertEquals(3, (int) Math.round(g.phased("count", 3, 1)));
        assertEquals(35, g.phased("spread", 3, 0), EPS);
    }

    @Test
    void floor06YamlMatchesImplementation() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        BossDef d = c.bosses().get("floor06_frost_empress");
        assertEquals(6, d.floor());
        assertEquals("shield_break_roles", d.core());
        assertEquals(List.of(1.0, 0.7, 0.35), d.phases());
        assertEquals(26000, d.hp(), EPS);
        assertEquals(15, d.arena().dbl("radius", 0), EPS);
        assertEquals(10, d.arena().dbl("sigil_ring_radius", 0), EPS);
        Set<String> implemented = Set.of("scepter_sweep", "glacial_spikes", "frostbite", "glacier_shell", "blizzard", "permafrost");
        assertEquals(implemented, d.patterns().keySet());
        for (List<String> rot : d.rotation().values()) for (String k : rot) assertTrue(d.patterns().containsKey(k), "rotation 키: " + k);
        // 페이즈별 활성 (GDD 표의 페이즈 열)
        assertEquals(List.of("scepter_sweep", "glacial_spikes", "frostbite"), d.rotation().get(1));
        assertTrue(d.rotation().get(2).contains("blizzard") && !d.rotation().get(2).contains("permafrost"));
        assertTrue(d.rotation().get(3).containsAll(List.of("blizzard", "permafrost")));
        assertFalse(d.rotation().values().stream().anyMatch(r -> r.contains("glacier_shell")), "껍질은 페이즈 트리거(rotation 밖)");
        // 스케줄러 종류: 동상 = interval, 나머지 = cooldown
        assertEquals(kr.labyrinth.bosses.PatternScheduler.Kind.INTERVAL, kr.labyrinth.bosses.PatternScheduler.kindOf(d.pattern("frostbite")));
        for (String k : List.of("scepter_sweep", "glacial_spikes", "blizzard", "permafrost")) {
            assertEquals(kr.labyrinth.bosses.PatternScheduler.Kind.COOLDOWN, kr.labyrinth.bosses.PatternScheduler.kindOf(d.pattern(k)), k);
        }
        // GDD 수치
        Params shell = d.pattern("glacier_shell");
        assertEquals(12, shell.dbl("cast_time", 0), EPS);
        assertEquals(16, shell.dbl("solo_cast_time", 0), EPS);
        assertEquals(9.0, shell.dbl("wipe_damage", 0), EPS);
        assertEquals(6.0, shell.dbl("shatter_stun", 0), EPS);
        assertEquals(0.3, shell.dbl("shatter_vulnerable", 0), EPS);
        assertEquals(List.of(DamageType.MELEE, DamageType.RANGED, DamageType.MAGIC), FrostLogic.sigilTypes(shell.strings("sigils")));
        // fx 모델 참조가 모두 fx.yml 에 있음
        for (Params p : d.patterns().values()) {
            for (String k : p.keys()) {
                if ((k.equals("fx") || k.startsWith("fx_")) && p.get(k) instanceof String s) {
                    assertTrue(c.fxModels().containsKey(s), "fx 모델 없음: " + s);
                }
            }
        }
        assertTrue(c.fxModels().containsKey("frost_nova_ring"));
    }
}
