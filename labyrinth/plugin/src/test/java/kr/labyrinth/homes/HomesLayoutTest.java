package kr.labyrinth.homes;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import kr.labyrinth.village.Blueprint;
import kr.labyrinth.village.DistrictLayout;
import kr.labyrinth.village.DistrictLibrary;
import kr.labyrinth.village.Layout;
import kr.labyrinth.village.PathRaster;
import kr.labyrinth.village.Planner;
import kr.labyrinth.village.Rot;
import kr.labyrinth.village.VillageMeta;
import org.junit.jupiter.api.Test;

/**
 * 집 구역 10채 설계 (0.3.7, pl37/plan.md §1) — 배포 월드 좌표.
 * 10채 · 14×14 · 안 겹침 (사이 생울타리 1칸) · 대문이 앞 울타리 줄 · 마을 길 1 첫 칸에서 공용 칸만 걸어 모든 대문에 닿음 ·
 * 마을 보호 상자·길과 안 겹침 · 광산 구역 east·south_east 마스크 (jar mine.json — 조각 + slack · 길 칸 + R + B) 와 안 겹침 ·
 * 마을이 다듬은 칸은 3번에만 있고 그 높이 = 3번 바닥 68 (review R1) · PvP 안전 (구역 보호 상자 + 8) 이 집 안을 모두 덮음.
 */
class HomesLayoutTest {

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

    static VillageMeta shipped() throws Exception {
        try (InputStream in = HomesLayoutTest.class.getClassLoader().getResourceAsStream("village/shipped-village.yml")) {
            assertNotNull(in, "test resources village/shipped-village.yml");
            return VillageMeta.fromYaml(new String(in.readAllBytes(), StandardCharsets.UTF_8));
        }
    }

    static long k(int x, int z) { return HomesLayout.key(x, z); }

    static Set<Long> cells(int x0, int z0, int x1, int z1) {
        Set<Long> out = new HashSet<>();
        for (int x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) for (int z = Math.min(z0, z1); z <= Math.max(z0, z1); z++) out.add(k(x, z));
        return out;
    }

    static Set<Long> plotCells(HomesLayout.Spec s) { return cells(s.x0(), s.z0(), s.x1(), s.z1()); }

    @Test
    void tenPlotsFourteenSquare() {
        assertEquals(HomesLayout.COUNT, HomesLayout.PLOTS.size());
        Set<Integer> ids = new TreeSet<>(), old = new TreeSet<>();
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            ids.add(s.id());
            old.add(s.oldId());
            assertEquals(HomesLayout.SIZE, s.x1() - s.x0() + 1, s.id() + "번 가로");
            assertEquals(HomesLayout.SIZE, s.z1() - s.z0() + 1, s.id() + "번 세로");
            assertTrue(s.front().equals("N") || s.front().equals("S"), s.id() + "번 앞");
        }
        assertEquals(new TreeSet<>(List.of(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)), ids);
        // 설계 12채에서 옛 3번(마을이 다듬은 칸 위)·옛 9번(광장에서 가장 멂)을 뺌
        assertEquals(new TreeSet<>(List.of(1, 2, 4, 5, 6, 7, 8, 10, 11, 12)), old);
        assertEquals(68, HomesLayout.plot(3).floorY(), "3번 바닥 = 마을이 다듬은 칸 높이");
    }

    @Test
    void plotsDoNotTouchEachOtherOrStreets() {
        Set<Long> pub = HomesLayout.publicCells();
        Set<Long> yard = cells(HomesLayout.YARD.x0(), HomesLayout.YARD.z0(), HomesLayout.YARD.x1(), HomesLayout.YARD.z1());
        for (HomesLayout.Spec a : HomesLayout.PLOTS) {
            Set<Long> ca = plotCells(a);
            for (Long c : ca) {
                assertFalse(pub.contains(c), a.id() + "번이 공용 칸과 겹침");
                assertFalse(yard.contains(c), a.id() + "번이 골목 마당과 겹침");
            }
            for (HomesLayout.Spec b : HomesLayout.PLOTS) {
                if (b.id() <= a.id()) continue;
                Set<Long> ring = HomesLayout.ringCells(a);
                for (Long c : plotCells(b)) {
                    assertFalse(ca.contains(c), a.id() + "·" + b.id() + "번 겹침");
                    assertFalse(ring.contains(c), a.id() + "·" + b.id() + "번 사이에 생울타리 칸이 없음");
                }
            }
            assertTrue(HomesLayout.DISTRICT.contains(a.x0(), a.z0()) && HomesLayout.DISTRICT.contains(a.x1(), a.z1()), a.id() + "번이 구역 상자 밖");
        }
        for (Long c : yard) assertFalse(pub.contains(c), "골목 마당이 공용 칸과 겹침");
    }

    @Test
    void gatesOnFrontFenceAndReachableFromVillagePath() {
        Set<Long> pub = HomesLayout.publicCells();
        // 이음 칸 서쪽 끝이 아니라 마을 길 1 첫 칸 (-137, 26..27) 바로 옆 (-138, 26..27) 에서 출발
        Map<Long, Integer> dist = new HashMap<>();
        ArrayDeque<int[]> q = new ArrayDeque<>();
        for (int[] j : HomesLayout.JUNCTION) {
            int[] start = {j[0] - 1, j[1]};
            assertTrue(pub.contains(k(start[0], start[1])), "이음 칸이 마을 길 1 첫 칸에 붙지 않음: " + start[0] + "," + start[1]);
            dist.put(k(start[0], start[1]), 0);
            q.add(start);
        }
        while (!q.isEmpty()) {
            int[] c = q.poll();
            int d = dist.get(k(c[0], c[1]));
            for (int[] o : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) {
                long n = k(c[0] + o[0], c[1] + o[1]);
                if (pub.contains(n) && !dist.containsKey(n)) {
                    dist.put(n, d + 1);
                    q.add(new int[] {c[0] + o[0], c[1] + o[1]});
                }
            }
        }
        assertEquals(pub.size(), dist.size(), "공용 칸이 한 덩어리가 아님");
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            int fz = s.front().equals("S") ? s.z1() + 1 : s.z0() - 1;
            assertEquals(fz, s.gateZ(), s.id() + "번 대문이 앞 울타리 줄이 아님");
            assertTrue(s.gateX() > s.x0() && s.gateX() < s.x1(), s.id() + "번 대문이 집터 앞 가운데쪽이 아님");
            assertTrue(s.signX() > s.x0() && s.signX() < s.x1() && Math.abs(s.signX() - s.gateX()) == 2, s.id() + "번 표지판 자리");
            int[] out = s.gateOutside();
            assertTrue(dist.containsKey(k(out[0], out[1])), s.id() + "번 대문 바깥 칸에 못 감");
            assertArrayEquals(out, new int[] {(int) Math.floor(s.homeX()), (int) Math.floor(s.homeZ())}, s.id() + "번 집 가기 칸 = 대문 바깥 칸");
            float want = s.front().equals("S") ? 180f : 0f;
            assertEquals(want, s.homeYaw(), s.id() + "번 집 가기 방향 (대문을 봄)");
            assertTrue(dist.get(k(out[0], out[1])) <= 105, s.id() + "번 골목 걸음 " + dist.get(k(out[0], out[1])) + " (가장 먼 10번 ≈ 103)");
        }
        assertNull(HomesLayout.plotAt(-138, 55), "골목 마당은 집터가 아님");
        assertEquals(6, HomesLayout.plotAt(-138, 75).id());
    }

    @Test
    void clearOfVillageProtectionAndPaths() throws Exception {
        VillageMeta v = shipped();
        Set<Long> village = new HashSet<>();
        for (VillageMeta.Box b : v.protect) village.addAll(cells(b.x0(), b.z0(), b.x1(), b.z1()));
        Set<Long> path = new HashSet<>();
        for (VillageMeta.PathRec p : v.paths) for (int[] c : p.cells()) path.add(k(c[0], c[1]));
        for (int[] j : HomesLayout.JUNCTION) assertTrue(path.contains(k(j[0], j[1])), "마을 길 1 첫 칸 " + j[0] + "," + j[1]);
        Set<Long> ours = new HashSet<>(HomesLayout.publicCells());
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            ours.addAll(plotCells(s));
            ours.addAll(HomesLayout.ringCells(s));
        }
        for (Long c : ours) {
            assertFalse(village.contains(c), "마을 보호 상자와 겹침 " + (c >> 32) + "," + (int) (long) c);
            assertFalse(path.contains(c), "마을 길과 겹침 " + (c >> 32) + "," + (int) (long) c);
        }
    }

    /** review R1: 마을이 다듬은 칸(terrain.changed)은 3번(옛 4번)에만 8칸, 기록 높이 = 3번 바닥 68. 옛 3번 자리는 마당 (집터 아님). */
    @Test
    void villageTrimmedCellsOnlyUnderPlotThreeAtItsFloor() throws Exception {
        VillageMeta v = shipped();
        VillageMeta.TerrainRec t = v.terrain;
        assertNotNull(t, "마을 terrain 기록");
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            int n = 0;
            for (int x = s.x0(); x <= s.x1(); x++) {
                for (int z = s.z0(); z <= s.z1(); z++) {
                    if (!t.in(x, z) || !t.changed(x, z)) continue;
                    n++;
                    assertEquals(s.floorY(), t.height(x, z), s.id() + "번 다듬은 칸 (" + x + "," + z + ") 높이");
                }
            }
            if (s.id() == 3) assertEquals(8, n, "3번 안 다듬은 칸");
            else assertEquals(0, n, s.id() + "번 안 다듬은 칸");
        }
    }

    /** 광산 구역 (jar districts/mine.json) east·south_east 마스크 = 조각(+slack)·길 칸에서 R + B — 집터·공용 칸과 안 겹침. */
    @Test
    void clearOfMineDistrictMasks() throws Exception {
        DistrictLibrary lib = DistrictLibrary.load(HomesLayoutTest::read, HomesLayoutTest::bin);
        DistrictLibrary.Entry e = lib.get("mine");
        assertNotNull(e, "jar 광산 구역");
        VillageMeta v = shipped();
        int turns = Rot.turns(org.bukkit.block.structure.StructureRotation.valueOf(v.rotation));
        Set<Long> ours = new HashSet<>(HomesLayout.publicCells());
        for (HomesLayout.Spec s : HomesLayout.PLOTS) ours.addAll(plotCells(s));
        for (DistrictLayout.Site site : e.layout().sites) {
            DistrictLayout.Placement pl = e.layout().place(site, v.center[0], v.center[2], turns, Map.of(), e.pieces());
            List<int[]> seeds = new ArrayList<>();
            for (Layout.Entry en : pl.layout().pieces) {
                Blueprint bp = e.pieces().get(en.piece());
                int[] d = Rot.dims(bp.w, bp.d, en.front().turns());
                int sl = Planner.slackOf(en, bp);
                int x0 = pl.ox() + en.atX() - d[0] / 2, z0 = pl.oz() + en.atZ() - d[1] / 2;
                for (int x = x0 - sl; x <= x0 + d[0] - 1 + sl; x++) for (int z = z0 - sl; z <= z0 + d[1] - 1 + sl; z++) seeds.add(new int[] {x, z});
            }
            for (Layout.PathDef p : pl.layout().paths) {
                List<int[]> pts = new ArrayList<>();
                for (int[] q : p.points()) pts.add(new int[] {q[0] + pl.ox(), q[1] + pl.oz()});
                for (PathRaster.Cell c : PathRaster.cells(pts, p.width())) seeds.add(new int[] {c.x(), c.z()});
            }
            int grow = e.layout().r + e.layout().b;
            int minX = Integer.MAX_VALUE;
            for (int[] s : seeds) {
                minX = Math.min(minX, s[0] - grow);
                for (int dx = -grow; dx <= grow; dx++) {
                    for (int dz = -grow; dz <= grow; dz++) {
                        long c = k(s[0] + dx, s[1] + dz);
                        assertFalse(ours.contains(c), "광산 " + site.id() + " 마스크와 겹침 " + (s[0] + dx) + "," + (s[1] + dz));
                    }
                }
            }
            int east = Integer.MIN_VALUE;
            for (HomesLayout.Spec s : HomesLayout.PLOTS) east = Math.max(east, s.x1());
            assertTrue(minX > east, "광산 " + site.id() + " 마스크 서쪽 끝 " + minX + " 이 집터 동쪽 끝 " + east + " 안쪽");
        }
    }

    /** PvP 안전 = 구역 보호 상자(공용 칸 + 집터 둘레 울타리 줄) + safe_margin 8 → 집 안 모든 칸 (pvp/VillageZone 규칙). */
    @Test
    void pvpSafeCoversEveryPlotCell() {
        List<int[]> prot = new ArrayList<>();
        for (Long c : HomesLayout.publicCells()) prot.add(new int[] {(int) (c >> 32), (int) (long) c});
        for (HomesLayout.Spec s : HomesLayout.PLOTS) for (Long c : HomesLayout.ringCells(s)) prot.add(new int[] {(int) (c >> 32), (int) (long) c});
        int m = 8;
        for (HomesLayout.Spec s : HomesLayout.PLOTS) {
            for (int x = s.x0(); x <= s.x1(); x++) {
                for (int z = s.z0(); z <= s.z1(); z++) {
                    boolean ok = false;
                    for (int[] p : prot) {
                        if (Math.abs(p[0] - x) <= m && Math.abs(p[1] - z) <= m) {
                            ok = true;
                            break;
                        }
                    }
                    assertTrue(ok, s.id() + "번 (" + x + "," + z + ") PvP 안전 밖");
                }
            }
        }
    }

    @Test
    void geomsCarryWindowFromConfig() {
        List<PlotGeom> g = HomesLayout.geoms(6, 24);
        assertEquals(10, g.size());
        PlotGeom p3 = g.get(2);
        assertEquals("3", p3.id());
        assertEquals(62, p3.yMin());
        assertEquals(92, p3.yMax());
        assertTrue(p3.contains(-120, 68, 50));
        assertFalse(p3.contains(-120, 61, 50), "바닥 −7 은 창 밖");
        assertFalse(p3.contains(-120, 93, 50), "바닥 +25 는 창 밖");
        assertFalse(p3.homeKnown(), "지어지기 전 집 가기 높이는 모름");
        assertEquals("3번지", p3.label());
        int[] w = HomesConfig.DEFAULT.window(70);
        assertArrayEquals(new int[] {64, 94}, w);
    }
}
