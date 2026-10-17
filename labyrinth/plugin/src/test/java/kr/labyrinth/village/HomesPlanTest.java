package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.homes.HomesLayout;
import org.junit.jupiter.api.Test;

/**
 * 집 구역 계획 (0.3.7 — design/037/PLAN.md §1·§2, review R1·R7·R10): jar 의 districts/homes.json 을 배포 월드 마을(중심 (-136, 16),
 * 반시계 90°)에 펼쳐 마스크 계획기로 — 배포 지형 픽스처(0.3.6.1 world.zip, district_fingerprint.py --district homes --terrain) +
 * 얼린 칸 = 마을 + 지은 광산(east, 0.3.6.1 world.zip 의 labyrinth-district-mine.yml).
 * 겹침 0 · 길 경사 0 · 바닥 = 설계 ±1 (3번은 마을이 다듬은 칸 높이 68) · 이음 · 대문이 거리에서 한 걸음 · 울타리 줄 보호 상자가 집터 둘레를
 * 빈틈없이 덮고 집 안은 보호 상자가 아님 · PvP 안전 · 광산 south_east 뒤에도 통과.
 */
class HomesPlanTest {

    static VillageMeta shipped() throws Exception { return DistrictLayoutTest.shipped(); }

    static VillageMeta mineEast() throws Exception {
        return DistrictMeta.fromYaml(Fixtures.read("village/shipped-district-mine.yml")).meta;
    }

    /** 집 구역 둘레 배포 지형 (0.3.6.1 world.zip — 광산 east 지어짐). */
    static TerrainGrid terrain() {
        List<String[]> rows = new ArrayList<>();
        int x0 = Integer.MAX_VALUE, z0 = Integer.MAX_VALUE, x1 = Integer.MIN_VALUE, z1 = Integer.MIN_VALUE;
        try (var in = new java.util.zip.GZIPInputStream(HomesPlanTest.class.getClassLoader().getResourceAsStream("village/shipped-terrain-homes.txt.gz"));
             var r = new java.io.BufferedReader(new java.io.InputStreamReader(in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.startsWith("#") || line.isBlank()) continue;
                String[] a = line.trim().split(" ");
                rows.add(a);
                int x = Integer.parseInt(a[0]), z = Integer.parseInt(a[1]);
                x0 = Math.min(x0, x);
                z0 = Math.min(z0, z);
                x1 = Math.max(x1, x);
                z1 = Math.max(z1, z);
            }
        } catch (IOException e) {
            throw new java.io.UncheckedIOException(e);
        }
        TerrainGrid g = new TerrainGrid(x0, z0, x1 - x0 + 1, z1 - z0 + 1);
        for (String[] a : rows) {
            g.set(Integer.parseInt(a[0]), Integer.parseInt(a[1]), Integer.parseInt(a[2]), Integer.parseInt(a[3]), Integer.parseInt(a[4]),
                    Integer.parseInt(a[5]), a[6], "plains", (Integer.parseInt(a[4]) & Terrain.UNNATURAL) != 0 ? "픽스처 비자연" : null);
        }
        return g;
    }

    static DistrictLibrary.Entry homes() {
        DistrictLibrary.Entry e = DistrictLayoutTest.library().get("homes");
        assertNotNull(e, "homes 구역");
        assertTrue(e.ok(), e.problems().toString());
        return e;
    }

    static Plan plan(DistrictLibrary.Entry e, VillageMeta v, List<VillageMeta> others, TerrainGrid g) {
        DistrictLayout L = e.layout();
        int turns = Rot.turns(org.bukkit.block.structure.StructureRotation.valueOf(v.rotation));
        DistrictLayout.Placement pl = L.place(L.site("south_west"), v.center[0], v.center[2], turns, Map.of(), e.pieces());
        Planner.Mask mask = new Planner.Mask(L.r, L.b, FrozenCells.of(v, others), L.maxFill, L.foundationDepth, L.smallWater);
        Planner planner = new Planner(pl.layout(), e.pieces(), mask);
        return planner.plan(g, pl.ox(), pl.oz(), 0, true);
    }

    static Map<String, Plan.Placed> pads(Plan p) {
        Map<String, Plan.Placed> out = new HashMap<>();
        for (Plan.Placed pl : p.pieces) if (pl.bp.pad) out.put(pl.entry.opts().tag(), pl);
        return out;
    }

    static long k(int x, int z) { return PathRaster.key(x, z); }

    @Test
    void homesDistrictParses() {
        DistrictLibrary.Entry e = homes();
        DistrictLayout L = e.layout();
        assertEquals(20, L.order, "광산(10) 다음");
        assertEquals(List.of("south_west"), L.siteIds());
        assertEquals(1, L.r);
        assertEquals(2, L.b);
        assertEquals(8, L.foundationDepth);
        assertEquals(8, L.smallWater);
        assertEquals(4, L.maxFill);
        int pads = 0, fronts = 0;
        for (Layout.Entry en : L.pieces) {
            Blueprint bp = e.pieces().get(en.piece());
            if (bp.pad) {
                pads++;
                assertEquals(12, en.opts().maxFill(), "집터 max_fill");
                assertNotNull(en.opts().tag());
            }
            if (bp.abut && bp.door) fronts++;
            for (int r : en.opts().floorRef()) assertTrue(r < en.index(), "floor_ref 는 앞 조각");
        }
        assertEquals(10, pads);
        assertEquals(10, fronts);
        Blueprint pad = e.pieces().get("plot_pad");
        assertEquals(List.of(14, 33, 14), List.of(pad.w, pad.h, pad.d));
        assertEquals(8, pad.floorY);
        assertTrue(pad.abut && pad.pad && !pad.door);
        Blueprint stall = e.pieces().get("keeper_stall");
        assertEquals("estate", stall.markers("interact").get(0).action());
        assertEquals("estate_keeper", stall.markers("npc").get(0).id());
        Blueprint front = e.pieces().get("plot_front");
        assertEquals("plot:{plot}", front.markers("interact").get(0).action());
        assertTrue(front.markers("sign").get(0).lines().get(0).contains("{plot}"));
        // 구역 청사진 지문 (district_fingerprint.py --district homes)
        assertNotNull(e.fp(), "homes.fp");
    }

    @Test
    void plansOnShippedWorldWithMineEast() throws Exception {
        DistrictLibrary.Entry e = homes();
        VillageMeta v = shipped();
        Plan p = plan(e, v, List.of(mineEast()), terrain());
        assertTrue(p.ok(), p.reason);
        assertTrue(Planner.overlaps(p.pieces, p.paths).isEmpty(), Planner.overlaps(p.pieces, p.paths).toString());
        assertEquals(0, p.steepPaths);
        assertTrue(p.skipped.isEmpty(), "빠진 장식: " + p.skipped);
        assertTrue(p.junctions > 0, "골목 이음 칸이 마을 길 1 에 닿음");
        Map<String, Plan.Placed> pads = pads(p);
        assertEquals(10, pads.size());
        StringBuilder floors = new StringBuilder();
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            Plan.Placed pl = pads.get(String.valueOf(s.id()));
            assertNotNull(pl, s.id() + "번");
            assertEquals(s.x0(), pl.x0, s.id() + "번 x");
            assertEquals(s.z0(), pl.z0, s.id() + "번 z");
            floors.append(s.id()).append(':').append(pl.floor).append(' ');
            assertTrue(Math.abs(pl.floor - s.floorY()) <= 1, s.id() + "번 바닥 " + pl.floor + " (설계 " + s.floorY() + ")");
        }
        System.out.println("[HomesPlanTest] 바닥 " + floors + "· 깎기 " + p.cut + " · 메우기 " + p.fill + " · 조각 " + p.pieces.size());
        assertEquals(68, pads.get("3").floor, "3번 = 마을이 다듬은 칸 높이 (R1)");
        // 마주 보는 집 (같은 거리 칸에서 한 걸음): 1|4 · 2|5 · 3|7
        for (int[] pair : new int[][] {{1, 4}, {2, 5}, {3, 7}}) {
            assertTrue(Math.abs(pads.get("" + pair[0]).floor - pads.get("" + pair[1]).floor) <= 2, pair[0] + "|" + pair[1]);
        }
    }

    /** 대문 = 앞 울타리 줄 (설계 칸), 대문 앞 칸 = 거리 칸, 그 높이 = 바닥 ±1, 표지판·우클릭 plot:&lt;번지&gt;. */
    @Test
    void gatesOpenOntoStreetsWithinOneStep() throws Exception {
        DistrictLibrary.Entry e = homes();
        Plan p = plan(e, shipped(), List.of(mineEast()), terrain());
        assertTrue(p.ok(), p.reason);
        Map<Long, Integer> ph = new HashMap<>();
        for (Plan.PathPlan pp : p.paths) for (int[] c : pp.cells) ph.putIfAbsent(k(c[0], c[1]), c[2]);
        List<DistrictMeta.PlotRec> plots = Markers.plots(p, 6, 24);
        assertEquals(10, plots.size());
        Map<Long, Integer> pins = p.doorPins();
        assertEquals(10, pins.size(), "대문 앞 칸 10");
        VillageMeta m = Markers.meta(p, Layout.of("집 구역", 8, 4, List.of(), List.of(), Map.of()));
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            DistrictMeta.PlotRec r = plots.get(s.id() - 1);
            assertEquals(String.valueOf(s.id()), r.id());
            assertEquals(s.front(), r.front(), s.id() + "번 앞");
            assertEquals(s.gateX(), r.gateX(), s.id() + "번 대문 x");
            assertEquals(s.gateZ(), r.gateZ(), s.id() + "번 대문 z");
            assertEquals(s.signX(), r.signX(), s.id() + "번 표지판 x");
            assertEquals(s.gateZ(), r.signZ(), s.id() + "번 표지판 z");
            assertEquals(r.floor() + 1, r.gateY(), s.id() + "번 대문 높이");
            assertEquals(r.floor() + 2, r.signY(), s.id() + "번 표지판 높이");
            assertEquals(s.homeX(), r.homeX(), 1e-9, s.id() + "번 집 가기 x");
            assertEquals(s.homeZ(), r.homeZ(), 1e-9, s.id() + "번 집 가기 z");
            assertEquals(s.homeYaw(), r.homeYaw(), 1e-3, s.id() + "번 집 가기 방향");
            assertEquals(r.floor() - 6, r.y0());
            assertEquals(r.floor() + 24, r.y1());
            int[] out = s.gateOutside();
            Integer street = ph.get(k(out[0], out[1]));
            assertNotNull(street, s.id() + "번 대문 앞 칸이 거리 칸");
            assertTrue(Math.abs(street - r.floor()) <= 1, s.id() + "번 대문 앞 거리 " + street + " / 바닥 " + r.floor());
            // 짓는 칸 일과 같은 반 칸 계단 규칙: 이웃 길이 한 칸 높으면 반블록 — 대문보다 높은 대문 앞 칸에는 놓지 않음 (자가 진단 blocked_doors)
            boolean higher = false;
            for (int[] d : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) higher |= Integer.valueOf(street + 1).equals(ph.get(k(out[0] + d[0], out[1] + d[1])));
            int top = street + (higher && Plan.halfStepOk(pins.get(k(out[0], out[1])), street) ? 1 : 0);
            assertTrue(Math.abs(top - r.floor()) <= 1, s.id() + "번 대문 앞 겉 블록 " + top + " / 바닥 " + r.floor());
            assertNotNull(pins.get(k(out[0], out[1])), s.id() + "번 대문 앞 칸이 묶임");
            assertEquals(street + 1, r.homeY(), 1e-9, s.id() + "번 집 가기 높이 = 거리 + 1");
            assertEquals("plot:" + s.id(), m.interact.get(VillageMeta.key(r.signX(), r.signY(), r.signZ())), s.id() + "번 표지판 우클릭");
        }
        assertTrue(m.interact.containsValue("estate"), "관리인 노점 우클릭");
        assertNotNull(m.npcs.get("estate_keeper"), "관리인 자리");
    }

    /**
     * review R10: 울타리·생울타리 줄 = 보호 상자 (zone 0), 집터 둘레를 빈틈없이 — 집 안 14×14 칸은 보호 상자가 아님.
     * 보호 상자 높이 = 낮은 쪽 바닥 − 8 ~ 높은 쪽 바닥 + 3 이상 (단 사이 옹벽까지).
     */
    @Test
    void ringBoxesCoverEveryRingCellButNotPlots() throws Exception {
        DistrictLibrary.Entry e = homes();
        Plan p = plan(e, shipped(), List.of(mineEast()), terrain());
        assertTrue(p.ok(), p.reason);
        VillageMeta m = Markers.meta(p, Layout.of("집 구역", 8, 4, List.of(), List.of(), Map.of()));
        Map<String, Plan.Placed> pads = pads(p);
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            int floor = pads.get(String.valueOf(s.id())).floor;
            for (long c : HomesLayout.ringCells(s)) {
                int x = (int) (c >> 32), z = (int) c;
                boolean covered = false;
                for (VillageMeta.Box b : m.protect) {
                    if (x >= b.x0() && x <= b.x1() && z >= b.z0() && z <= b.z1() && b.y0() <= floor - 8 && b.y1() >= floor + 3) covered = true;
                }
                assertTrue(covered, s.id() + "번 둘레 (" + x + ", " + z + ") 가 보호 상자 아님");
            }
            for (int x = s.x0(); x <= s.x1(); x++) {
                for (int z = s.z0(); z <= s.z1(); z++) {
                    for (VillageMeta.Box b : m.protect) {
                        assertFalse(x >= b.x0() && x <= b.x1() && z >= b.z0() && z <= b.z1(), s.id() + "번 안 (" + x + ", " + z + ") 이 보호 상자");
                    }
                }
            }
        }
        // PvP 안전 (pvp/VillageZone: 보호 상자 + safe_margin 8) — 집 안 모든 칸
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            for (int x = s.x0(); x <= s.x1(); x++) {
                for (int z = s.z0(); z <= s.z1(); z++) {
                    boolean safe = false;
                    for (VillageMeta.Box b : m.protect) {
                        if (x >= b.x0() - 8 && x <= b.x1() + 8 && z >= b.z0() - 8 && z <= b.z1() + 8) safe = true;
                    }
                    assertTrue(safe, s.id() + "번 (" + x + ", " + z + ") PvP 안전 밖");
                }
            }
        }
    }

    /** review R1: 3번 안 마을이 다듬은 칸 8칸은 높이 68 = 바닥, 겉 그대로 (얼린 칸 — 지형 쓰기·조각 바닥 층 쓰기 없음). */
    @Test
    void plotThreeKeepsVillageTrimmedSurface() throws Exception {
        DistrictLibrary.Entry e = homes();
        VillageMeta v = shipped();
        Plan p = plan(e, v, List.of(mineEast()), terrain());
        assertTrue(p.ok(), p.reason);
        FrozenCells fz = FrozenCells.of(v, List.of(mineEast()));
        HomesLayout.Spec s3 = HomesLayout.plot(3);
        int trim = 0;
        for (int x = s3.x0(); x <= s3.x1(); x++) {
            for (int z = s3.z0(); z <= s3.z1(); z++) {
                if (fz.kind(x, z) != FrozenCells.Kind.TRIM) continue;
                trim++;
                assertTrue(p.isFrozen(x, z));
                assertEquals(68, p.ground[p.idx(x, z)]);
                assertEquals(6, p.fixedSrc[p.idx(x, z)], "다듬은 칸은 원래 높이로 고정");
            }
        }
        assertEquals(8, trim, "3번 안 다듬은 칸");
        // 다른 집 안에는 다듬은 칸이 없다
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            if (s.id() == 3) continue;
            for (int x = s.x0(); x <= s.x1(); x++) for (int z = s.z0(); z <= s.z1(); z++) assertFalse(p.isFrozen(x, z), s.id() + "번 (" + x + "," + z + ")");
        }
    }

    /** 집터 바닥 높이를 다듬은 칸이 막으면 (높이가 다름) 짓지 않는다 — 그 칸을 덮어 마을 진단이 깨지지 않게. */
    @Test
    void padRefusesTrimmedCellsAtOtherHeight() throws Exception {
        DistrictLibrary.Entry e = homes();
        VillageMeta v = shipped();
        TerrainGrid g = terrain();
        // 3번 다듬은 칸 하나를 70 으로 (기록은 68 그대로 — 다듬은 칸 높이가 여럿)
        g.set(-129, 48, 70, 0, 0, 0, "grass_block", "plains", null);
        Plan p = plan(e, v, List.of(mineEast()), g);
        assertFalse(p.ok());
        assertEquals(Planner.Fail.LIMIT, p.fail);
        assertTrue(p.reason.contains("다듬은 칸"), p.reason);
    }

    /** review R7: 광산이 south_east 에 지어진 서버 — 광산이 다듬은 칸·보호 상자를 얼린 채로 집 구역도 통과. */
    @Test
    void plansAfterMineSouthEast() throws Exception {
        DistrictLibrary.Entry mine = DistrictLayoutTest.library().get("mine");
        VillageMeta v = shipped();
        Plan se = DistrictLayoutTest.plan(mine, mine.layout().site("south_east"), v, DistrictLayoutTest.terrain(v));
        assertTrue(se.ok(), se.reason);
        VillageMeta seMeta = Markers.meta(se, Layout.of("광산 마을", 8, 6, List.of(), List.of(), Map.of()));
        Plan p = plan(homes(), v, List.of(seMeta), terrain());
        assertTrue(p.ok(), p.reason);
        assertTrue(Planner.overlaps(p.pieces, p.paths).isEmpty());
        FrozenCells fz = FrozenCells.of(v, List.of(seMeta));
        int onMine = 0;
        for (Plan.Placed pl : p.pieces) {
            for (int rz = 0; rz < pl.d2; rz++) {
                for (int rx = 0; rx < pl.w2; rx++) {
                    int x = pl.x0 + rx, z = pl.z0 + rz;
                    if (!pl.occupies(x, z)) continue;
                    assertFalse(fz.untouchable(x, z), pl.bp.id + " 가 광산 보호 상자·길 (" + x + ", " + z + ")");
                    if (fz.kind(x, z) == FrozenCells.Kind.TRIM && z >= 41) onMine++;
                }
            }
        }
        System.out.println("[HomesPlanTest] 광산 south_east 다듬은 칸 위 울타리 칸 " + onMine);
    }

    /** 집 구역 조각·길이 마을 보호 상자·길과 겹치지 않음 (얼린 칸 PATH·PROTECT). */
    @Test
    void stayClearOfVillage() throws Exception {
        VillageMeta v = shipped();
        Plan p = plan(homes(), v, List.of(mineEast()), terrain());
        assertTrue(p.ok(), p.reason);
        FrozenCells fz = FrozenCells.of(v, List.of(mineEast()));
        Set<Long> seen = new HashSet<>();
        for (Plan.Placed pl : p.pieces) {
            for (int rz = 0; rz < pl.d2; rz++) {
                for (int rx = 0; rx < pl.w2; rx++) {
                    int x = pl.x0 + rx, z = pl.z0 + rz;
                    if (!pl.occupies(x, z)) continue;
                    assertTrue(seen.add(k(x, z)), "조각 겹침 (" + x + ", " + z + ")");
                    assertFalse(fz.untouchable(x, z), pl.bp.id + " (" + x + ", " + z + ") 이 마을 보호 상자·길");
                }
            }
        }
        for (Plan.PathPlan pp : p.paths) for (int[] c : pp.cells) assertFalse(fz.untouchable(c[0], c[1]), "길 #" + pp.def.index() + " (" + c[0] + ", " + c[1] + ")");
    }
    @Test
    void halfStepRuleAtGates() {
        assertTrue(Plan.halfStepOk(null, 80), "대문 앞이 아니면 늘 됨");
        assertTrue(Plan.halfStepOk(71, 70));
        assertTrue(Plan.halfStepOk(71, 71), "바닥과 같은 높이 + 반블록 = 반 칸 위");
        assertFalse(Plan.halfStepOk(71, 72), "한 칸 높은 길에 반블록 = 1.5 칸 — 못 오름");
    }

    /** jar 의 homes.fp: 배포 월드 두 판 build_id · 계획 영역의 얼리지 않은 열을 모두 덮고 땅 높이 = 0.3.6.1 world.zip 지형 (광산 east 를 지은 뒤에도). */
    @Test
    void homesFingerprintMatchesShippedWorld() throws Exception {
        byte[] raw = DistrictLayoutTest.bin("village/districts/homes.fp");
        assertNotNull(raw, "jar village/districts/homes.fp");
        DistrictFingerprint fp = DistrictFingerprint.read(raw);
        assertTrue(fp.compatible());
        DistrictFingerprint.World a = fp.forBuild("a06800d8-7a5d-452d-b3eb-79364ebfac99");
        assertNotNull(a, "0.3.x 배포 월드");
        assertNotNull(fp.forBuild("c99c3fb3-4621-4037-b7dd-26f71e3edfce"), "0.2.0 배포 월드");
        VillageMeta v = shipped();
        TerrainGrid g = terrain();
        Plan p = plan(homes(), v, List.of(mineEast()), g);
        assertTrue(p.ok(), p.reason);
        int n = 0;
        for (int lz = 0; lz < p.gn; lz++) {
            for (int lx = 0; lx < p.gn; lx++) {
                int x = p.gx0 + lx, z = p.gz0 + lz;
                if (!p.inRegion(x, z) || p.isFrozen(x, z)) continue;
                DistrictFingerprint.Column c = a.at(x, z);
                assertNotNull(c, "지문이 덮지 않는 열 (" + x + ", " + z + ")");
                assertEquals(g.ground(x, z), c.h(), "땅 높이 (" + x + ", " + z + ")");
                n++;
            }
        }
        assertTrue(n > 4000, "검사한 열 " + n);
    }
}
