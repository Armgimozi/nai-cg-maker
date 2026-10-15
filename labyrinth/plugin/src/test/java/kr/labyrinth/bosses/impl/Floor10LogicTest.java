package kr.labyrinth.bosses.impl;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.dungeon.gen.FloorGenerator;
import kr.labyrinth.dungeon.gen.FloorLayout;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 지하 10층 심연의 심장 넬카르 (GDD §7.10) — 투기장 ①②③ 기하·생성기 일치, 붕괴 배치·타일 상태, 해일, 응시, 박동, 메아리, YAML. */
class Floor10LogicTest {

    static Content content;
    static BossDef boss;
    static AbyssLogic.Geometry geo;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        boss = content.bosses().get("floor10_abyss_heart");
        assertNotNull(boss);
        Params a = boss.arena();
        geo = AbyssLogic.Geometry.of(a.integer("radius", 18), a.integer("corridor_length", 80), a.integer("corridor_width", 7),
                a.integer("rim_radius", 12), FloorGenerator.RIM_MOAT);
    }

    // ── 투기장 ───────────────────────────────────────────────────────────

    @Test
    void geometryMatchesGdd() {
        assertEquals(18, geo.r());
        assertEquals(3, geo.half());
        assertEquals(80, geo.uEnd() - geo.r());
        assertEquals(12, geo.rimR());
        assertEquals(FloorGenerator.rimCenterOffset(18, 80, 12), geo.rimU());
        // 회랑은 심장실과 단에 맞물린다 (틈 없음)
        assertTrue(geo.inChamber(0, geo.uStart()));
        assertTrue(geo.inMoat(0, geo.uEnd()) || geo.onRim(0, geo.uEnd()));
        assertTrue(geo.inBridge(0, geo.uEnd()));
        assertFalse(geo.onRim(0, geo.uEnd()));
        assertTrue(geo.onRim(0, geo.rimU()));
        assertTrue(geo.inMoat(geo.rimR() + 2, geo.rimU()));
        assertFalse(geo.inBridge(geo.rimR() + 2, geo.rimU()));
        assertFalse(geo.inBattle(geo.r() + 12, 0, 3));
        assertTrue(geo.inBattle(0, 50, 0));
    }

    @Test
    void generatorBuildsChamberCorridorAndRim() {
        FloorDef f = content.floor(10);
        assertNotNull(f);
        boolean liquid = f.liquid() != null && !f.liquid().isBlank() && !"null".equalsIgnoreCase(f.liquid());
        Params a = boss.arena();
        FloorGenerator.Params gp = new FloorGenerator.Params(f.cells(), f.rooms(), f.roomHeight(), 4, liquid, a.integer("radius", 14),
                a.integer("height", 10), a.integer("corridor_length", 0), a.integer("corridor_width", 7), a.integer("rim_radius", 0));
        for (long seed : new long[]{1, 7, 99}) {
            FloorLayout layout = FloorGenerator.generate(gp, seed);
            FloorLayout.Arena ar = layout.arena();
            int bossIdx = layout.bossRoom().index();
            assertEquals(geo.rimU(), ar.rimCenterZ() - ar.centerZ());
            assertTrue(layout.bossRoom().maxZ() >= ar.maxZ());
            int checked = 0;
            for (int dz = -geo.r(); dz <= geo.rimU() + geo.rimOuter(); dz++) {
                for (int dx = -geo.rimOuter(); dx <= geo.rimOuter(); dx++) {
                    boolean want = geo.inChamber(dx, dz) || geo.inCorridor(dx, dz) || geo.onRim(dx, dz) || geo.inMoat(dx, dz);
                    if (!want) continue;
                    int x = ar.centerX() + dx, z = ar.centerZ() + dz;
                    assertTrue(layout.walkable(x, z), "seed " + seed + " 칸 " + dx + "," + dz + " 이 바닥이 아님");
                    assertEquals(bossIdx, layout.region(x, z), "seed " + seed + " 칸 " + dx + "," + dz + " 이 보스방이 아님");
                    checked++;
                }
            }
            assertTrue(checked > 1000);
            // 낭떠러지 고리 바깥은 벽 (단 밖으로 걸어 나갈 수 없다)
            assertFalse(layout.walkable(ar.centerX() + geo.rimOuter() + 2, ar.centerZ() + geo.rimU()));
        }
    }

    @Test
    void gapsLieInsideCorridorAwayFromChamberAndRim() {
        int[] gaps = geo.gapStarts(3, 2);
        assertEquals(3, gaps.length);
        for (int i = 0; i < gaps.length; i++) {
            for (int dz = gaps[i]; dz < gaps[i] + 2; dz++) {
                for (int dx = -geo.half(); dx <= geo.half(); dx++) {
                    assertTrue(geo.inCorridor(dx, dz));
                    assertFalse(geo.inChamber(dx, dz));
                    assertFalse(geo.inMoat(dx, dz) || geo.onRim(dx, dz));
                }
            }
            if (i > 0) assertTrue(gaps[i] - gaps[i - 1] >= 15);
        }
        assertTrue(AbyssLogic.Geometry.inGap(gaps[1], gaps, 2));
        assertTrue(AbyssLogic.Geometry.inGap(gaps[1] + 1, gaps, 2));
        assertFalse(AbyssLogic.Geometry.inGap(gaps[1] + 2, gaps, 2));
    }

    // ── 타일 ─────────────────────────────────────────────────────────────

    @Test
    void chamberTilesFitTheGeneratedCircle() {
        int size = AbyssLogic.oddSize(3);
        assertEquals(3, size);
        assertEquals(5, AbyssLogic.oddSize(4));
        List<int[]> tiles = AbyssLogic.chamberTiles(18, size);
        assertTrue(tiles.size() > 80 && tiles.size() < 120, "타일 수 " + tiles.size());
        for (int[] t : tiles) {
            assertFalse(t[0] == 0 && t[1] == 0, "보스 자리 타일은 빠져야 함");
            for (int a = -1; a <= 1; a++) for (int b = -1; b <= 1; b++) assertTrue(geo.inChamber(t[0] * 3 + a, t[1] * 3 + b));
        }
        AbyssLogic.Grid g = new AbyssLogic.Grid(tiles, size);
        int k = g.indexOf(2, -1);
        assertTrue(k >= 0);
        assertEquals(k, g.tileAtBlock(6, -3));
        assertEquals(k, g.tileAtBlock(7, -2));
        assertEquals(k, g.tileAtBlock(5, -4));
        assertNotEquals(k, g.tileAtBlock(8, -3));
        assertEquals(-1, g.tileAtBlock(0, 0));
        assertEquals(1, AbyssLogic.tileOf(2, 3));
        assertEquals(-1, AbyssLogic.tileOf(-2, 3));
        assertEquals(0, AbyssLogic.tileOf(-1, 3));
    }

    @Test
    void tileStateMachine() {
        AbyssLogic.Grid g = new AbyssLogic.Grid(AbyssLogic.chamberTiles(18, 3), 3);
        int k = g.indexOf(1, 0);
        g.warn(k, 50);
        assertEquals(AbyssLogic.State.WARN, g.state(k));
        assertTrue(g.due(49).get(0).isEmpty());
        assertEquals(List.of(k), g.due(50).get(0));
        g.collapse(k, 350);
        assertTrue(g.hole(k));
        assertEquals(AbyssLogic.State.FALLEN, g.state(k));
        assertEquals(List.of(k), g.due(350).get(1));
        g.restore(k);
        assertEquals(AbyssLogic.State.SOLID, g.state(k));
        g.collapse(k, Long.MAX_VALUE);
        assertEquals(AbyssLogic.State.GONE, g.state(k));
        assertTrue(g.due(Long.MAX_VALUE - 1).get(1).isEmpty());
        // 가장 가까운 멀쩡한 타일 — 무너진·금 간 칸은 건너뛴다
        int near = g.nearestSolid(3, 0);
        assertNotEquals(k, near);
        assertEquals(AbyssLogic.State.SOLID, g.state(near));
        assertFalse(g.hole(-1));
    }

    @Test
    void collapseCountFollowsPartyFormula() {
        assertEquals(30, AbyssLogic.collapseCount(100, 100, 0.30, 0.02, 1));
        assertEquals(40, AbyssLogic.collapseCount(100, 100, 0.30, 0.02, 6));
        assertEquals(12, AbyssLogic.collapseCount(100, 12, 0.30, 0.02, 1));
        assertEquals(0, AbyssLogic.collapseCount(100, 0, 0.30, 0.02, 1));
    }

    @Test
    void everyLayoutPicksExactlyCountDistinctAvailableTiles() {
        List<int[]> all = AbyssLogic.chamberTiles(18, 3);
        List<int[]> avail = new ArrayList<>(all.subList(0, all.size() - 10));
        Set<String> availKeys = new HashSet<>();
        for (int[] t : avail) availKeys.add(t[0] + "," + t[1]);
        for (AbyssLogic.Layout l : AbyssLogic.Layout.values()) {
            for (int seed = 0; seed < 20; seed++) {
                List<int[]> pick = AbyssLogic.pick(l, avail, 30, new Random(seed));
                assertEquals(30, pick.size(), l + " seed " + seed);
                Set<String> keys = new HashSet<>();
                for (int[] t : pick) {
                    assertTrue(availKeys.contains(t[0] + "," + t[1]), l + " 가 남은 타일 밖을 고름");
                    assertTrue(keys.add(t[0] + "," + t[1]), l + " 중복");
                }
            }
        }
        // 같은 시드 = 같은 배치
        assertEquals(key(AbyssLogic.pick(AbyssLogic.Layout.SPIRAL, avail, 25, new Random(3))),
                key(AbyssLogic.pick(AbyssLogic.Layout.SPIRAL, avail, 25, new Random(3))));
    }

    @Test
    void layoutsHaveTheirShape() {
        List<int[]> all = AbyssLogic.chamberTiles(18, 3);
        // 체스판: 절반 이하면 전부 같은 색
        for (int seed = 0; seed < 10; seed++) {
            List<int[]> pick = AbyssLogic.pick(AbyssLogic.Layout.CHECKER, all, 30, new Random(seed));
            int parity = Math.floorMod(pick.get(0)[0] + pick.get(0)[1], 2);
            for (int[] t : pick) assertEquals(parity, Math.floorMod(t[0] + t[1], 2));
        }
        // 십자: 고른 타일이 안 고른 타일보다 축(또는 대각선)에 가깝다
        for (int seed = 0; seed < 10; seed++) {
            List<int[]> pick = AbyssLogic.pick(AbyssLogic.Layout.CROSS, all, 20, new Random(seed));
            int plus = 0, diag = 0;
            for (int[] t : pick) {
                plus += Math.min(Math.abs(t[0]), Math.abs(t[1]));
                diag += Math.min(Math.abs(t[0] - t[1]), Math.abs(t[0] + t[1]));
            }
            assertTrue(Math.min(plus, diag) <= pick.size(), "십자 모양이 아님 seed " + seed);
        }
        // 동심원: 고른 띠는 모두 같은 홀짝
        for (int seed = 0; seed < 10; seed++) {
            List<int[]> pick = AbyssLogic.pick(AbyssLogic.Layout.RINGS, all, 25, new Random(seed));
            int parity = AbyssLogic.band(pick.get(0)) % 2;
            for (int[] t : pick) assertEquals(parity, AbyssLogic.band(t) % 2);
        }
        assertEquals(AbyssLogic.Layout.CHECKER, AbyssLogic.Layout.parse("checker"));
        assertEquals(AbyssLogic.Layout.RINGS, AbyssLogic.Layout.parse("rings"));
        assertEquals(5, AbyssLogic.Layout.parseAll(boss.pattern("abyssal_collapse").strings("layouts")).size());
        List<AbyssLogic.Layout> cyc = AbyssLogic.Layout.parseAll(List.of("scatter", "cross"));
        assertEquals(AbyssLogic.Layout.SCATTER, AbyssLogic.nextLayout(cyc, 0));
        assertEquals(AbyssLogic.Layout.CROSS, AbyssLogic.nextLayout(cyc, 1));
        assertEquals(AbyssLogic.Layout.SCATTER, AbyssLogic.nextLayout(cyc, 2));
    }

    private static String key(List<int[]> l) {
        StringBuilder sb = new StringBuilder();
        for (int[] t : l) sb.append(t[0]).append(',').append(t[1]).append(';');
        return sb.toString();
    }

    // ── 추격 ─────────────────────────────────────────────────────────────

    @Test
    void wallChasesAndSafeSpotsLandAheadOfIt() {
        assertEquals(-20, AbyssLogic.wallPos(-20, 4.6, 0.05, 0), 1e-9);
        assertEquals(-20 + 46 + 2.5, AbyssLogic.wallPos(-20, 4.6, 0.05, 10), 1e-9);
        // 해일이 회랑 끝(98)까지 가는 데 걸리는 시간 > 전력 질주(5.6칸/초)로 심장실 북쪽 끝에서 가는 시간
        double t = 0;
        while (AbyssLogic.wallPos(-geo.r() - 2, 4.6, 0.05, t) < geo.uEnd()) t += 0.05;
        double sprint = (geo.uEnd() + geo.r()) / 5.6;
        assertTrue(t + 3 > sprint + 2, "해일이 너무 빠름: " + t + "초 vs 질주 " + sprint);
        assertTrue(AbyssLogic.wallTouches(10.5, 10));
        assertFalse(AbyssLogic.wallTouches(11, 10));
        int[] gaps = geo.gapStarts(3, 2);
        assertEquals(34, AbyssLogic.pursuitSafeZ(30, 30, geo, gaps, 2));
        assertEquals(60, AbyssLogic.pursuitSafeZ(60, 30, geo, gaps, 2));
        int z = AbyssLogic.pursuitSafeZ(gaps[0], gaps[0] - 10, geo, gaps, 2);
        assertEquals(gaps[0] + 2, z);
        assertEquals(geo.uEnd(), AbyssLogic.pursuitSafeZ(500, 0, geo, gaps, 2));
        assertEquals(geo.uStart() + 1, AbyssLogic.pursuitSafeZ(-15, -30, geo, gaps, 2));
    }

    // ── 회전 응시 ────────────────────────────────────────────────────────

    @Test
    void gazeBeamsRotateAndHitAlongTheirLine() {
        assertEquals(0, AbyssLogic.beamAngle(0, 0, 2, 30, 0, 1), 1e-9);
        assertEquals(180, AbyssLogic.beamAngle(0, 1, 2, 30, 0, 1), 1e-9);
        assertEquals(120, AbyssLogic.beamAngle(0, 1, 3, 30, 0, 1), 1e-9);
        assertEquals(30, AbyssLogic.beamAngle(0, 0, 2, 30, 1, 1), 1e-9);
        assertEquals(-60, AbyssLogic.beamAngle(0, 0, 2, 30, 2, -1), 1e-9);
        assertTrue(AbyssLogic.inBeam(8, 0, 0, 16, 1.5));
        assertTrue(AbyssLogic.inBeam(8, 0.7, 0, 16, 1.5));
        assertFalse(AbyssLogic.inBeam(8, 0.8, 0, 16, 1.5));
        assertFalse(AbyssLogic.inBeam(-3, 0, 0, 16, 1.5));
        assertFalse(AbyssLogic.inBeam(17, 0, 0, 16, 1.5));
        assertTrue(AbyssLogic.inBeam(0, 5, 90, 16, 1.5));
        // 광선과 같은 방향·속도로 걸으면 계속 비켜 서 있다 (30°/초, 반경 8 → 각 40° 뒤)
        for (double s = 0; s <= 8; s += 0.25) {
            double beam = AbyssLogic.beamAngle(0, 0, 2, 30, s, 1);
            double me = Math.toRadians(beam - 40);
            assertFalse(AbyssLogic.inBeam(Math.cos(me) * 8, Math.sin(me) * 8, beam, 16, 1.5));
        }
    }

    // ── 박동·메아리·구체 ─────────────────────────────────────────────────

    @Test
    void heartbeatRampsAndEchoesRotate() {
        assertEquals(0.8, AbyssLogic.heartbeatMult(0.8, 0.15, 0), 1e-9);
        assertEquals(0.92, AbyssLogic.heartbeatMult(0.8, 0.15, 1), 1e-9);
        assertEquals(1.04, AbyssLogic.heartbeatMult(0.8, 0.15, 2), 1e-9);
        List<String> pool = boss.pattern("floor_echoes").strings("pool");
        assertEquals(8, pool.size());
        Random rng = new Random(1);
        String last = null;
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 200; i++) {
            String e = AbyssLogic.pickEcho(pool, last, rng);
            assertNotEquals(last, e);
            seen.add(e);
            last = e;
        }
        assertEquals(new HashSet<>(pool), seen);
        assertEquals("a", AbyssLogic.pickEcho(List.of("a"), "a", rng));
        assertEquals(24, AbyssLogic.echoWindup(20, 1.2));
        assertEquals(10, AbyssLogic.echoWindup(2, 1.2));
        assertEquals(2, AbyssLogic.echoStakes(1));
        assertEquals(2, AbyssLogic.echoStakes(4));
        assertEquals(5, AbyssLogic.echoStakes(10));
    }

    @Test
    void orbsSteerTowardTargetAtConstantSpeed() {
        double[] v = {0.2, 0};
        for (int i = 0; i < 200; i++) v = AbyssLogic.steer(v[0], v[1], 0, 10, 0.06, 0.2);
        assertEquals(0.2, Math.hypot(v[0], v[1]), 1e-9);
        assertTrue(v[1] > 0.19, "대상 쪽으로 돌지 않음");
        double[] w = AbyssLogic.steer(0.2, 0, 0, 10, 0.06, 0.2);
        assertTrue(w[1] > 0 && w[1] < 0.05, "한 틱에 너무 많이 꺾임");
        double[] z = AbyssLogic.steer(0, 0, 0, 0, 0.06, 0.2);
        assertEquals(0.2, Math.hypot(z[0], z[1]), 1e-9);
    }

    // ── YAML ─────────────────────────────────────────────────────────────

    @Test
    void yamlHasEveryPatternAndEchoSourcesExist() {
        assertEquals(95000, boss.hp(), 1e-9);
        assertEquals(10, boss.floor());
        for (String k : List.of("tendril_lash", "void_orbs", "abyssal_collapse", "devouring_pursuit", "rotating_gaze", "abyss_rift",
                "heartbeat_pulse", "floor_echoes")) {
            assertTrue(boss.patterns().containsKey(k), "패턴 없음: " + k);
        }
        Params pc = boss.pattern("abyssal_collapse");
        assertEquals(9, pc.dbl("interval", 0), 1e-9);
        assertEquals(2.5, pc.dbl("warn_time", 0), 1e-9);
        assertEquals(15, pc.dbl("regen_time", 0), 1e-9);
        assertEquals(0.25, pc.dbl("fall_damage_pct", 0), 1e-9);
        Params pp = boss.pattern("devouring_pursuit");
        assertEquals(4.6, pp.dbl("wall_speed", 0), 1e-9);
        assertEquals(6, (int) pp.scaled("debris", 1, 0));
        assertEquals(9, (int) pp.scaled("debris", 4, 0));
        assertEquals(3, pp.integer("gaps", 0));
        assertEquals(30, boss.pattern("heartbeat_pulse").dbl("interval", 0), 1e-9);
        assertEquals(20, boss.pattern("floor_echoes").dbl("cooldown", 0), 1e-9);
        assertEquals(3, boss.pattern("rotating_gaze").phased("beams", 3, 2), 1e-9);
        assertEquals(2, boss.pattern("rotating_gaze").phased("beams", 2, 2), 1e-9);
        // 메아리 풀의 패턴은 모두 이전 층 보스에 있다
        for (String k : boss.pattern("floor_echoes").strings("pool")) {
            boolean found = false;
            for (BossDef d : content.bosses().values()) if (d.floor() < 10 && d.patterns().containsKey(k)) found = true;
            assertTrue(found, "메아리 원본 없음: " + k);
        }
        assertTrue(content.fxModels().containsKey("abyss_wall"));
        assertTrue(content.fxModels().containsKey("proj_void_orb"));
        assertTrue(content.fxModels().containsKey("telegraph_tile"));
        assertTrue(content.fxModels().containsKey("chain_anchor"));
        assertTrue(content.fxModels().containsKey("marker_target"));
    }
}
