package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** 계획기: slack 조정, 겹침, 구조물/물/동굴 후보 탈락, 회전 선택. */
class PlannerTest {

    @Test
    void flatGroundPlansWithoutMovesOrChanges() {
        VillageLibrary lib = Fixtures.library();
        Plan p = lib.planner.plan(Fixtures.flat(80, 64), 0, 0, 0, true);
        assertTrue(p.ok(), p.reason);
        assertEquals(64, p.h0);
        for (Plan.Placed pl : p.pieces) {
            assertEquals(64, pl.floor, pl.bp.id);
            assertEquals(0, pl.dx, pl.bp.id + " 평지에서는 옮기지 않음");
            assertEquals(0, pl.dz, pl.bp.id);
        }
        assertEquals(0, p.cut + p.fill);
        assertTrue(Planner.overlaps(p.pieces, p.paths).isEmpty());
        // 길: 조각 발자국 안 칸은 빠짐, 붙은 조각 표시
        Plan.PathPlan path = p.paths.get(0);
        assertTrue(path.attachA >= 0 && path.attachB >= 0, "광장·오두막에 붙은 길");
        for (int[] c : path.cells) for (Plan.Placed pl : p.pieces) assertFalse(pl.occupies(c[0], c[1]), "길 칸이 발자국 안");
        assertFalse(path.cells.isEmpty());
    }

    /** 오두막 기준 자리 절반에 5칸 언덕 → slack 안에서 언덕을 피해 옮기고, 옮긴 뒤에도 겹침 없음. */
    @Test
    void slackMovesPieceOffBumpWithoutOverlap() {
        VillageLibrary lib = Fixtures.library();
        TerrainGrid g = Fixtures.flat(80, 64);
        // 동쪽 오두막(정면 서쪽) 기준 상자 x 9..13, z -2..2 — 그 북쪽 절반 + 바깥에 언덕
        for (int z = -6; z <= -2; z++) for (int x = 8; x <= 15; x++) g.setGround(x, z, 69);
        Plan moved = lib.planner.plan(g, 0, 0, 0, false);
        assertTrue(moved.ok(), moved.reason);
        Plan.Placed hut = moved.pieces.get(2);
        assertTrue(hut.dz > 0, "언덕 반대쪽(남)으로 옮김: dz=" + hut.dz);
        assertEquals(64, hut.floor);
        assertTrue(Planner.overlaps(moved.pieces, moved.paths).isEmpty());

        // 같은 지형, slack 0 이면 깎기·메우기가 더 큼 (또는 한도 초과로 탈락)
        String noSlack = Fixtures.read("village/layout.json").replace("\"front\": \"west\" }", "\"front\": \"west\", \"slack\": 0 }");
        Layout l0 = Layout.parse(noSlack);
        Planner p0 = new Planner(l0, lib.pieces);
        Plan fixed = p0.plan(g, 0, 0, 0, false);
        assertTrue(!fixed.ok() || fixed.padCost > moved.padCost, "slack 조정이 변화량을 줄임: " + fixed.padCost + " vs " + moved.padCost);
        // 길 끝도 조각을 따라 옮겨짐
        Plan.PathPlan lane = moved.paths.get(1);
        assertEquals(hut.index(), lane.attachB);
        assertEquals(0 + hut.dz, lane.points.get(1)[1]);
    }

    /** 조각끼리 붙음·정문 앞 막음·길에 닿음은 overlaps 가 잡는다 (짓기 전·자가 진단 공용). */
    @Test
    void overlapRulesCatchTouchingDoorAndPath() {
        VillageLibrary lib = Fixtures.library();
        Plan p = lib.planner.plan(Fixtures.flat(80, 64), 0, 0, 0, false);
        assertTrue(p.ok(), p.reason);
        Plan.Placed hut = p.pieces.get(1), lamp = p.pieces.get(3);
        // 가로등을 오두막 정문 앞 칸 옆으로
        int[] f = hut.doorFront();
        lamp.x0 = f[0] + 1;
        lamp.z0 = f[1];
        List<String> ov = Planner.overlaps(p.pieces, p.paths);
        assertFalse(ov.isEmpty());
        assertTrue(ov.stream().anyMatch(s -> s.contains("정문")), ov.toString());
        // 오두막 바로 옆(빈칸 0)
        lamp.x0 = hut.x0 + hut.w2;
        lamp.z0 = hut.z0 + 1;
        assertTrue(Planner.overlaps(p.pieces, p.paths).stream().anyMatch(s -> s.contains("붙음")));
        // 붙지 않은 길 위
        int[] c = p.paths.get(1).cells.get(0);
        lamp.x0 = c[0];
        lamp.z0 = c[1] + 1;
        assertTrue(Planner.overlaps(p.pieces, p.paths).stream().anyMatch(s -> s.contains("길")));
    }

    @Test
    void waterStructureAndCaveRejectCandidate() {
        VillageLibrary lib = Fixtures.library();
        TerrainGrid water = Fixtures.flat(80, 64);
        water.addFlags(25, 10, Terrain.WATER, "water@63");
        Plan pw = lib.planner.plan(water, 0, 0, 0, false);
        assertEquals(Planner.Fail.WATER, pw.fail);
        assertTrue(pw.reason.contains("water"), pw.reason);

        TerrainGrid struct = Fixtures.flat(80, 64);
        struct.addFlags(-30, 5, Terrain.UNNATURAL, "oak_planks@66");
        Plan ps = lib.planner.plan(struct, 0, 0, 0, false);
        assertEquals(Planner.Fail.STRUCTURE, ps.fail);

        // 오두막 기준 자리 ± slack 전체 아래 2칸에 큰 동굴
        TerrainGrid cave = Fixtures.flat(80, 64);
        for (int z = -16; z <= -5; z++) for (int x = -6; x <= 6; x++) cave.setHoles(x, z, 0b110);
        Plan pc = lib.planner.plan(cave, 0, 0, 0, false);
        assertEquals(Planner.Fail.CAVE, pc.fail, pc.reason);

        // 작은 동굴(1/3 미만)은 탈락 대신 기초로 메움
        TerrainGrid small = Fixtures.flat(80, 64);
        small.setHoles(0, -11, 0b1);
        Plan pm = lib.planner.plan(small, 0, 0, 0, false);
        assertTrue(pm.ok(), pm.reason);
        assertTrue(pm.caveFill > 0);
    }

    @Test
    void steepSiteExceedsCutFillLimit() {
        VillageLibrary lib = Fixtures.library();
        TerrainGrid g = Fixtures.flat(80, 64);
        for (int z = -80; z <= 80; z++) for (int x = -80; x <= 80; x++) g.setGround(x, z, 64 + Math.max(0, -z - 6) * 2);
        Plan p = lib.planner.plan(g, 0, 0, 0, false);
        assertFalse(p.ok());
        assertEquals(Planner.Fail.LIMIT, p.fail, p.reason);
    }

    @Test
    void outsideSurveyedAreaIsRange() {
        VillageLibrary lib = Fixtures.library();
        Plan p = lib.planner.plan(Fixtures.flat(30, 64), 0, 0, 0, false);
        assertEquals(Planner.Fail.RANGE, p.fail);
    }

    /** 남쪽이 높은 경사: 회전 4방향 중 변화량이 가장 적은 방향을 고르고, 조각 단은 지형을 따라 계단식. */
    @Test
    void bestRotationFollowsSlope() {
        VillageLibrary lib = Fixtures.library();
        TerrainGrid g = Fixtures.flat(80, 64);
        for (int z = -80; z <= 80; z++) for (int x = -80; x <= 80; x++) g.setGround(x, z, 64 + Math.floorDiv(z, 6));
        Plan best = lib.planner.bestRotation(g, 0, 0);
        assertTrue(best.ok(), best.reason);
        double[] scores = new double[4];
        for (int t = 0; t < 4; t++) {
            Plan p = lib.planner.plan(g, 0, 0, t, true);
            scores[t] = p.ok() ? p.score() : Double.MAX_VALUE;
            assertTrue(best.score() <= scores[t]);
        }
        java.util.Set<Integer> floors = new java.util.HashSet<>();
        for (Plan.Placed pl : best.pieces) floors.add(pl.floor);
        assertTrue(floors.size() > 1, "조각 단 높이가 지형을 따라 다름 (평판 아님): " + floors);
        assertTrue(Planner.overlaps(best.pieces, best.paths).isEmpty());
        // 길 이웃 차 ≤ 1
        assertEquals(0, best.steepPaths);
    }

    @Test
    void surveyRanksAndDedupes() {
        VillageLibrary lib = Fixtures.library();
        TerrainGrid g = Fixtures.flat(140, 64);
        // 서쪽 반은 울퉁불퉁 → 동쪽이 좋음
        for (int z = -140; z <= 140; z++) for (int x = -140; x <= 0; x++) g.setGround(x, z, 64 + ((x * 31 + z * 17) & 3));
        Planner.SurveyResult r = lib.planner.survey(g, 0, 0, 112, 8, 3, null, () -> false);
        assertFalse(r.best().isEmpty());
        Plan top = r.best().get(0);
        assertTrue(top.cx > 0, "평탄한 동쪽을 고름: " + top.cx);
        for (int i = 0; i < r.best().size(); i++) {
            for (int j = i + 1; j < r.best().size(); j++) {
                Plan a = r.best().get(i), b = r.best().get(j);
                assertTrue(Math.hypot(a.cx - b.cx, a.cz - b.cz) >= 16, "서로 다른 자리");
            }
        }
        Map<Planner.Fail, Integer> rej = r.rejects();
        assertTrue(rej.getOrDefault(Planner.Fail.RANGE, 0) > 0, "조사 범위 밖 후보는 탈락으로 셈: " + rej);
        List<Plan> best = r.best();
        assertTrue(best.get(0).field != null, "상위 후보는 목표 높이장까지 계산");
    }
}
