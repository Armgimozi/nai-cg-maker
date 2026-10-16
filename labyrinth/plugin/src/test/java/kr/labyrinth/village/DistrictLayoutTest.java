package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * 광산 마을 배치 (0.3.6 CONTRACT §2.13 · Q2 시험 DistrictLayout): jar 의 districts/mine.json 을 배포 월드 마을(중심 (-136, 16),
 * 반시계 90°)에 펼쳐 마스크 계획기로 계획 — 겹침 0 · 큰길 끝에 붙음 · 얼린 칸(마을) 그대로 · 제련소 13×18×12.
 */
class DistrictLayoutTest {

    static final Path RES = Path.of("src/main/resources");

    static String read(String rel) {
        try {
            Path f = RES.resolve(rel);
            return Files.isRegularFile(f) ? Files.readString(f, StandardCharsets.UTF_8) : null;
        } catch (IOException e) {
            return null;
        }
    }

    static byte[] bin(String rel) {
        try {
            Path f = RES.resolve(rel);
            return Files.isRegularFile(f) ? Files.readAllBytes(f) : null;
        } catch (IOException e) {
            return null;
        }
    }

    static DistrictLibrary library() {
        DistrictLibrary lib = DistrictLibrary.load(DistrictLayoutTest::read, DistrictLayoutTest::bin);
        assertTrue(lib.problems.isEmpty(), "구역 청사진 문제: " + lib.problems);
        return lib;
    }

    static VillageMeta shipped() throws Exception { return VillageMeta.fromYaml(Fixtures.read("village/shipped-village.yml")); }

    /** 배포 마을 지형(다듬은 높이) + 그 밖은 완만한 들판 (64 → 동쪽·남쪽으로 조금씩 오름). */
    static TerrainGrid terrain(VillageMeta v) {
        TerrainGrid g = new TerrainGrid(-200, -60, 200, 200);
        for (int z = -60; z < 140; z++) {
            for (int x = -200; x < 0; x++) {
                int y = 64 + Math.floorDiv(Math.max(0, z), 12);
                if (v.terrain != null && v.terrain.in(x, z)) y = v.terrain.height(x, z);
                g.setGround(x, z, y);
            }
        }
        // 마을 길 칸 = 기록된 길 높이 (마을 길과 구역 길의 이음)
        for (VillageMeta.PathRec p : v.paths) for (int[] c : p.cells()) g.setGround(c[0], c[1], c[2]);
        return g;
    }

    static Plan plan(DistrictLibrary.Entry e, DistrictLayout.Site site, VillageMeta v, TerrainGrid g) {
        DistrictLayout L = e.layout();
        int turns = Rot.turns(org.bukkit.block.structure.StructureRotation.valueOf(v.rotation));
        DistrictLayout.Placement pl = L.place(site, v.center[0], v.center[2], turns, Map.of(), e.pieces());
        Planner.Mask mask = new Planner.Mask(L.r, L.b, FrozenCells.of(v, List.of()), L.maxFill, L.foundationDepth, L.smallWater);
        Planner planner = new Planner(pl.layout(), e.pieces(), mask);
        return planner.plan(g, pl.ox(), pl.oz(), 0, true);
    }

    @Test
    void bundledMineDistrictParses() {
        DistrictLibrary lib = library();
        DistrictLibrary.Entry e = lib.get("mine");
        assertNotNull(e, "mine 구역");
        assertTrue(e.ok(), e.problems().toString());
        assertNotNull(e.fp(), "지문");
        assertEquals(List.of("east", "south_east"), e.layout().siteIds());
        Blueprint sm = e.pieces().get("smelter");
        assertEquals(13, sm.w);
        assertEquals(18, sm.h);
        assertEquals(12, sm.d);
        Blueprint hf = e.pieces().get("mine_headframe");
        assertEquals(List.of(13, 24, 13), List.of(hf.w, hf.h, hf.d));
        assertFalse(hf.markers("interact").isEmpty());
        assertEquals("mine_lift", hf.markers("interact").get(0).action());
        assertEquals(1, hf.markers("mine_exit").size(), "승강기 앞 mine_exit 마커");
    }

    /** east: 계약 좌표 그대로 (평지에 가까운 땅 — 옮기지 않음), 겹침 0, 큰길 끝에 붙음, 얼린 칸 그대로. */
    @Test
    void eastSitePlansOnShippedVillageWithoutOverlaps() throws Exception {
        DistrictLibrary.Entry e = library().get("mine");
        VillageMeta v = shipped();
        TerrainGrid g = terrain(v);
        Plan p = plan(e, e.layout().site("east"), v, g);
        assertTrue(p.ok(), p.reason);
        assertTrue(Planner.overlaps(p.pieces, p.paths).isEmpty(), Planner.overlaps(p.pieces, p.paths).toString());
        assertEquals(0, p.steepPaths);
        assertTrue(p.skipped.isEmpty(), "빠진 장식: " + p.skipped);
        assertTrue(p.junctions > 0, "구역 큰길이 마을 큰길에 닿음");
        Plan.Placed hf = byId(p, "mine_headframe"), sm = byId(p, "smelter"), lodge = byId(p, "miners_lodge");
        // 계약 상자: 승강장 x −72..−60 z 9..21 · 제련소 x −88..−76 z 23..34 · 숙소 x −85..−75 z 4..12 (slack ±2)
        near(hf, -72, 9, 13, 13);
        near(sm, -88, 23, 13, 12);
        near(lodge, -85, 4, 11, 9);
        assertEquals(Dir.WEST, hf.front());
        assertEquals(Dir.NORTH, sm.front());
        assertEquals(Dir.SOUTH, lodge.front());
        // 모든 조각이 x ≥ −100 (마을이 다듬은 칸 x ≤ −101 과 떨어짐)
        for (Plan.Placed pl : p.pieces) assertTrue(pl.x0 >= -100, pl.bp.id + " x0=" + pl.x0);
        frozenUntouched(p, v);
    }

    @Test
    void southEastSitePlansToo() throws Exception {
        DistrictLibrary.Entry e = library().get("mine");
        VillageMeta v = shipped();
        Plan p = plan(e, e.layout().site("south_east"), v, terrain(v));
        assertTrue(p.ok(), p.reason);
        assertTrue(Planner.overlaps(p.pieces, p.paths).isEmpty(), Planner.overlaps(p.pieces, p.paths).toString());
        Plan.Placed hf = byId(p, "mine_headframe");
        near(hf, -72, 51, 13, 13);
        assertTrue(p.junctions > 0);
        frozenUntouched(p, v);
    }

    /** NPC 자리: 광부 (-74, 13) · 제련공 (-85, 21) ±2 (CONTRACT §2.13 — 조각 마커로 맞춤). */
    @Test
    void npcSpotsMatchContract() throws Exception {
        DistrictLibrary.Entry e = library().get("mine");
        VillageMeta v = shipped();
        Plan p = plan(e, e.layout().site("east"), v, terrain(v));
        VillageMeta m = Markers.meta(p, e.layout().pieces.isEmpty() ? null : Layout.of("광산 마을", 8, 6, List.of(), List.of(), Map.of()));
        VillageMeta.Pos miner = m.npcs.get("miner"), smelter = m.npcs.get("smelter");
        assertNotNull(miner);
        assertNotNull(smelter);
        assertTrue(Math.abs(Math.floor(miner.x()) + 74) <= 2 && Math.abs(Math.floor(miner.z()) - 13) <= 2, "광부 " + miner);
        assertTrue(Math.abs(Math.floor(smelter.x()) + 85) <= 2 && Math.abs(Math.floor(smelter.z()) - 21) <= 2, "제련공 " + smelter);
        assertEquals(Dir.WEST.yaw(), miner.yaw(), 0.01);
        assertEquals(Dir.NORTH.yaw(), smelter.yaw(), 0.01);
        assertNotNull(m.points.get("mine_exit"), "mine_exit");
        assertEquals(List.of("mine_info", "mine_lift", "smelter"), m.interact.values().stream().distinct().sorted().toList());
        assertTrue(m.ambient.stream().anyMatch(a -> a.fx().equals("dust")));
    }

    /** here: 길 0 첫 점이 고른 자리, 방향을 돌리면 같은 모양이 돈다. */
    @Test
    void placeHereRotates() {
        DistrictLibrary.Entry e = library().get("mine");
        DistrictLayout L = e.layout();
        DistrictLayout.Placement east = L.placeHere(100, 200, Dir.EAST, Map.of(), e.pieces());
        assertEquals(100, east.junction()[0]);
        assertEquals(200, east.junction()[1]);
        DistrictLayout.Placement north = L.placeHere(100, 200, Dir.NORTH, Map.of(), e.pieces());
        // 동쪽으로 펼치면 승강장 정면은 서쪽, 북쪽으로 펼치면 남쪽
        assertEquals(Dir.WEST, east.layout().pieces.get(0).front());
        assertEquals(Dir.SOUTH, north.layout().pieces.get(0).front());
    }

    static Plan.Placed byId(Plan p, String id) {
        for (Plan.Placed pl : p.pieces) if (pl.bp.id.equals(id)) return pl;
        throw new AssertionError("조각 없음: " + id);
    }

    static void near(Plan.Placed pl, int x0, int z0, int w, int d) {
        assertEquals(w, pl.w2, pl.bp.id + " 폭");
        assertEquals(d, pl.d2, pl.bp.id + " 깊이");
        assertTrue(Math.abs(pl.x0 - x0) <= 2 && Math.abs(pl.z0 - z0) <= 2, pl.bp.id + " (" + pl.x0 + ", " + pl.z0 + ") ≠ (" + x0 + ", " + z0 + ")");
    }

    /** 얼린 칸: 목표 높이 = 원래 높이, 조각 발자국 없음, 구역 길 칸은 마을 길·보호 상자 밖. */
    static void frozenUntouched(Plan p, VillageMeta v) {
        FrozenCells fz = FrozenCells.of(v, List.of());
        int n = p.gn * p.gn, frozenSeen = 0;
        for (int i = 0; i < n; i++) {
            int x = p.gx0 + i % p.gn, z = p.gz0 + i / p.gn;
            if (!fz.frozen(x, z)) continue;
            frozenSeen++;
            assertEquals(p.ground[i], p.field.target()[i], "얼린 칸 높이 (" + x + ", " + z + ")");
            for (Plan.Placed pl : p.pieces) assertFalse(pl.occupies(x, z), pl.bp.id + " 이 얼린 칸 위");
        }
        assertTrue(frozenSeen > 0, "영역이 마을 다듬은 칸에 닿음 (얼린 칸 시험이 의미 있게)");
        for (Plan.PathPlan pp : p.paths) for (int[] c : pp.cells) assertFalse(fz.untouchable(c[0], c[1]), "구역 길 칸이 마을 길·보호 상자 위");
    }
}
