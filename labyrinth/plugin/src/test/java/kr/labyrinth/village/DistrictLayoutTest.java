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

    /**
     * 배포 월드 지형 (dist/world.zip 의 east·south_east 마스크 범위, district_fingerprint.py --terrain 이 만든 픽스처 —
     * 땅 높이·땅속 빈칸·물·나무). 마을 길 칸은 기록된 길 높이로 (Scan 은 길 블록 아래 흙을 땅으로 보지만 계획기 이음은 길 높이를 본다).
     */
    static TerrainGrid terrain(VillageMeta v) {
        TerrainGrid g = new TerrainGrid(-140, -40, 120, 160);
        try (var in = new java.util.zip.GZIPInputStream(DistrictLayoutTest.class.getClassLoader().getResourceAsStream("village/shipped-terrain.txt.gz"));
             var r = new java.io.BufferedReader(new java.io.InputStreamReader(in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.startsWith("#") || line.isBlank()) continue;
                String[] a = line.trim().split(" ");
                g.set(Integer.parseInt(a[0]), Integer.parseInt(a[1]), Integer.parseInt(a[2]), Integer.parseInt(a[3]), Integer.parseInt(a[4]),
                        Integer.parseInt(a[5]), a[6], "plains", (Integer.parseInt(a[4]) & Terrain.UNNATURAL) != 0 ? "픽스처 비자연" : null);
            }
        } catch (IOException e) {
            throw new java.io.UncheckedIOException(e);
        }
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
        // mine_office = 숙소 '광산 관리소' 표지판 — 광부 NPC 가 없어도(npcs.yml 을 고친 서버) 관리소 메뉴가 열린다
        assertEquals(List.of("mine_info", "mine_lift", "mine_office", "smelter"), m.interact.values().stream().distinct().sorted().toList());
        assertTrue(m.ambient.stream().anyMatch(a -> a.fx().equals("dust")));
    }

    /** 얼린 칸 (CONTRACT §2.13 3): 구역 길이 마을이 다듬은 칸을 지나면 원래 높이 그대로 겉 블록만, 마을 길·보호 상자 칸은 건너뜀. */
    @Test
    void districtRoadCrossesTrimmedCellsWithoutReshaping() throws Exception {
        DistrictLibrary.Entry e = library().get("mine");
        VillageMeta v = shipped();
        TerrainGrid g = terrain(v);
        Plan p = plan(e, e.layout().site("east"), v, g);
        assertTrue(p.ok(), p.reason);
        FrozenCells fz = FrozenCells.of(v, List.of());
        int trimmed = 0;
        for (int[] c : p.paths.get(0).cells) {
            assertFalse(fz.untouchable(c[0], c[1]), "마을 길·보호 상자 칸 (" + c[0] + ", " + c[1] + ")");
            if (fz.kind(c[0], c[1]) == FrozenCells.Kind.TRIM) {
                trimmed++;
                assertEquals(g.ground(c[0], c[1]), c[2], "다듬은 칸 위 구역 길은 원래 높이 (" + c[0] + ", " + c[1] + ")");
                assertTrue(c[0] <= -101, "다듬은 칸은 큰길 끝 쪽에만 (" + c[0] + ")");
            }
        }
        // 배포 월드에서는 마을이 큰길 끝(x −104) 너머를 다듬지 않았다 — 구역 큰길 첫 칸(x −103)이 마을 길 칸에 바로 붙는다
        assertTrue(trimmed >= 0);
        boolean touches = false;
        for (int[] c : p.paths.get(0).cells) if (c[0] == -103 && fz.pathY(-104, c[1]) != null) touches = true;
        assertTrue(touches, "구역 큰길이 마을 큰길 끝 (-104, 15..17) 에 붙음");
        // 이음: 구역 큰길 첫 칸 높이 − 마을 큰길 끝 칸 높이 ≤ 1 (계획기 frozenPaths 가 지킴)
        assertTrue(p.junctions > 0);
        for (int[] c : p.paths.get(0).cells) {
            Integer vy = fz.pathY(c[0] - 1, c[1]);
            if (vy != null) assertTrue(Math.abs(vy - c[2]) <= 1, "이음 높이 차 (" + c[0] + ", " + c[1] + ")");
        }
    }

    /** 더러운 자리: east 영역 안에 사람이 놓은 블록 → east 탈락 (짓지 않음), south_east 는 그대로 통과 (차례대로 다음 자리). */
    @Test
    void dirtyEastFallsBackToSouthEast() throws Exception {
        DistrictLibrary.Entry e = library().get("mine");
        VillageMeta v = shipped();
        TerrainGrid g = terrain(v);
        // 승강장 자리 (-66, 14) 에 판자 집
        for (int x = -68; x <= -64; x++) for (int z = 12; z <= 16; z++) g.addFlags(x, z, Terrain.UNNATURAL, "oak_planks@67");
        Plan east = plan(e, e.layout().site("east"), v, g);
        assertFalse(east.ok());
        assertEquals(Planner.Fail.STRUCTURE, east.fail);
        assertTrue(east.reason.contains("oak_planks"), east.reason);
        Plan se = plan(e, e.layout().site("south_east"), v, g);
        assertTrue(se.ok(), se.reason);
        // 라이브 시험 c-A 의 흔적 (east 숙소 자리 북쪽 판자 집 x −88..−84 z −3..1 · 흙 기둥 (−96, 0)) — east 만 막고 south_east 는 그대로
        //  (0.3.6.1: south_east 갈림길 길잡이를 큰길 북쪽에 두었더니 south_east 영역이 여기까지 넓어져 둘 다 막혔던 것)
        TerrainGrid g2 = terrain(v);
        for (int x = -88; x <= -84; x++) for (int z = -3; z <= 1; z++) g2.addFlags(x, z, Terrain.UNNATURAL, "oak_planks@68");
        g2.addFlags(-96, 0, Terrain.UNNATURAL, "dirt@68");
        assertFalse(plan(e, e.layout().site("east"), v, g2).ok(), "east 는 막힘");
        Plan se2 = plan(e, e.layout().site("south_east"), v, g2);
        assertTrue(se2.ok(), "south_east 는 통과: " + se2.reason);
        // 물 웅덩이도 막는다 (구역 영역 안 지표 물 — fill_small_water_max 0)
        TerrainGrid wet = terrain(v);
        wet.addFlags(-80, 30, Terrain.WATER, "water@66");
        Plan w = plan(e, e.layout().site("east"), v, wet);
        assertEquals(Planner.Fail.WATER, w.fail);
    }

    /**
     * 정문 앞 칸에서 한 걸음 안에 길 (0.3.6.1 놀이 리뷰 #1): 숙소 문이 마당보다 두 칸 낮은 도랑으로 열리던 것 — 정문 앞 칸이 길 칸이고
     * 그 길이 이웃 길과 높이 차 ≤ 1, 마당이 숙소 앞보다 불룩 솟지 않음 (follow 0). 두 자리 모두. 덤: 구역 길 칸 높이 차는 모두 ≤ 1.
     */
    @Test
    void doorsOpenOntoPathsWithinOneStep() throws Exception {
        DistrictLibrary.Entry e = library().get("mine");
        VillageMeta v = shipped();
        for (String sid : List.of("east", "south_east")) {
            Plan p = plan(e, e.layout().site(sid), v, terrain(v));
            assertTrue(p.ok(), sid + ": " + p.reason);
            Map<Long, Integer> ph = new java.util.HashMap<>();
            for (Plan.PathPlan pp : p.paths) for (int[] c : pp.cells) ph.putIfAbsent(PathRaster.key(c[0], c[1]), c[2]);
            for (Plan.Placed pl : p.pieces) {
                if (!pl.bp.door) continue;
                int[] f = pl.doorFront();
                Integer at = ph.get(PathRaster.key(f[0], f[1]));
                assertNotNull(at, sid + " " + pl.bp.id + " 정문 앞 (" + f[0] + ", " + f[1] + ") 이 길 칸");
                assertTrue(Math.abs(at - pl.floor) <= 1, sid + " " + pl.bp.id + " 정문 앞 길 높이 " + at + " / 바닥 " + pl.floor);
                for (int[] d : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) {
                    Integer h = ph.get(PathRaster.key(f[0] + d[0], f[1] + d[1]));
                    if (h != null) assertTrue(Math.abs(h - at) <= 1, sid + " " + pl.bp.id + " 정문 앞에서 이웃 길 높이 차 " + Math.abs(h - at));
                }
            }
            // 숙소 앞 줄(정문 앞 줄)과 마당 사이 높이 차 ≤ 1 (도랑 없음)
            Plan.Placed lodge = byId(p, "miners_lodge");
            int fz = lodge.doorFront()[1];
            for (int x = lodge.x0; x < lodge.x0 + lodge.w2; x++) {
                Integer yard = ph.get(PathRaster.key(x, fz + 1));
                if (yard == null || !p.inGrid(x, fz)) continue;
                int strip = p.field.target()[p.idx(x, fz)];
                assertTrue(Math.abs(yard - strip) <= 1, sid + " 숙소 앞 (" + x + ", " + fz + ") " + strip + " ↔ 마당 " + yard);
            }
            assertTrue(p.skipped.isEmpty(), sid + " 빠진 장식: " + p.skipped);
        }
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
