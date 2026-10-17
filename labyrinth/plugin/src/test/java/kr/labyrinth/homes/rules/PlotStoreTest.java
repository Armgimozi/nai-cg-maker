package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import kr.labyrinth.homes.PlotGeom;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** {@code <월드>/labyrinth-plots.yml} (plan §4): yml 왕복 · 원자적 저장 · 깨진 파일 · 옛 구역 기록. */
class PlotStoreTest {

    @TempDir
    Path dir;

    private static final UUID A = UUID.fromString("00000000-0000-0000-0000-00000000000a");
    private static final UUID B = UUID.fromString("00000000-0000-0000-0000-00000000000b");
    private static final UUID C = UUID.fromString("00000000-0000-0000-0000-00000000000c");

    @Test
    void roundTrip() throws Exception {
        File f = dir.resolve(PlotStore.FILE).toFile();
        PlotStore s = new PlotStore(f);
        s.districtBuild = "homes-1234";
        s.lockState = TerrainLock.State.ON;
        s.lockStartedAt = 111;
        s.graceDays = 3;
        s.graceStartedAt = 222;
        s.legacyScannedAt = 333;
        PlotStore.Owner o = new PlotStore.Owner(A, "하린", false, 444);
        o.name = "하린네 <b>집</b>";
        o.renamedAt = 555;
        o.trusted.put(B, "도윤");
        o.trusted.put(C, "서아");
        s.owners.put("3", o);
        s.owners.put("c1", new PlotStore.Owner(B, "도윤", true, 666));
        s.customs.put("c1", new PlotStore.Custom("c1", 1, -100, -100, -80, -80, 60, 100, 68, -90.5, 69, -90.5, 90f));
        s.vacated.put(C, 777L);
        s.known.add(A);
        s.known.add(B);
        s.save();
        assertTrue(f.isFile());
        assertFalse(new File(f.getPath() + ".tmp").exists(), "tmp 가 남지 않음");

        PlotStore r = PlotStore.load(f);
        assertEquals("", r.loadNote);
        assertEquals("homes-1234", r.districtBuild);
        assertEquals(TerrainLock.State.ON, r.lockState);
        assertEquals(111, r.lockStartedAt);
        assertEquals(3, r.graceDays);
        assertEquals(222, r.graceStartedAt);
        assertEquals(333, r.legacyScannedAt);
        PlotStore.Owner ro = r.owner("3");
        assertNotNull(ro);
        assertEquals(A, ro.owner);
        assertEquals("하린", ro.ownerName);
        assertEquals("하린네 <b>집</b>", ro.name, "이름은 글 그대로 (보일 때 escape)");
        assertFalse(ro.guests);
        assertEquals(444, ro.claimedAt);
        assertEquals(555, ro.renamedAt);
        assertEquals(2, ro.trusted.size());
        assertEquals("도윤", ro.trusted.get(B));
        assertEquals(B, ro.trusted.keySet().iterator().next(), "초대 차례 유지");
        assertEquals("3", r.homeOf(A));
        assertEquals("c1", r.homeOf(B));
        assertNull(r.homeOf(C));
        PlotStore.Custom c1 = r.customs.get("c1");
        assertNotNull(c1);
        PlotGeom g = c1.geom();
        assertEquals(101, g.key());
        assertTrue(g.custom());
        assertEquals(-100, g.x0());
        assertEquals(-80, g.z1());
        assertEquals(60, g.yMin());
        assertEquals(100, g.yMax());
        assertTrue(g.homeKnown());
        assertEquals(69, g.homeY(), 1e-9);
        assertEquals(777L, r.vacated.get(C));
        assertTrue(r.known.contains(A) && r.known.contains(B));
        assertEquals(1, r.districtOwned(), "convert 집은 구역 주인 수에서 뺌");
        assertEquals(2, r.nextCustomN());
    }

    @Test
    void missingFileIsEmpty() {
        PlotStore s = PlotStore.load(dir.resolve("none.yml").toFile());
        assertTrue(s.owners.isEmpty());
        assertEquals(TerrainLock.State.AUTO, s.lockState);
        assertNull(s.graceDays);
        assertEquals(1, s.nextCustomN());
    }

    @Test
    void brokenFileKeptAndNeverOverwritten() throws Exception {
        // live 6: 못 읽은 파일을 빈 기록으로 덮으면 모든 집이 빈 집이 되고 되살리기도 어려움 → 그대로 두고 저장을 거절
        Path f = dir.resolve(PlotStore.FILE);
        String bad = "plots: [::: {";
        Files.writeString(f, bad, StandardCharsets.UTF_8);
        PlotStore s = PlotStore.load(f.toFile());
        assertTrue(s.broken, "안전 모드");
        assertTrue(s.owners.isEmpty());
        assertFalse(s.loadNote.isEmpty());
        assertTrue(Files.exists(f), "깨진 파일은 그 자리에 그대로");
        try (var l = Files.list(dir)) {
            assertTrue(l.anyMatch(p -> p.getFileName().toString().startsWith(PlotStore.FILE + ".broken-")), "사본은 남김");
        }
        s.owners.put("3", new PlotStore.Owner(A, "a", true, 1));
        assertThrows(java.io.IOException.class, s::save, "안전 모드에서는 저장하지 않음");
        assertEquals(bad, Files.readString(f), "파일이 바뀌지 않음");
    }

    @Test
    void freshWorldFlagRoundTrip() throws Exception {
        // 배포 world.zip 의 주인 없는 파일 (tools/village/fresh_plots.py 와 같은 내용)
        Path f = dir.resolve(PlotStore.FILE);
        Files.writeString(f, "# 배포 월드\nformat: 1\nfresh_world: true\n", StandardCharsets.UTF_8);
        PlotStore s = PlotStore.load(f.toFile());
        assertFalse(s.broken);
        assertTrue(s.freshWorld);
        assertTrue(s.owners.isEmpty());
        assertEquals(0, s.lockStartedAt);
        s.save();
        assertTrue(PlotStore.load(f.toFile()).freshWorld, "저장해도 남음 (잠금이 처음 켜질 때까지)");
        s.freshWorld = false;
        s.save();
        assertFalse(PlotStore.load(f.toFile()).freshWorld);
        assertFalse(Files.readString(f).contains("fresh_world"), "지우면 줄도 없음");
    }

    @Test
    void staleDistrict() {
        PlotStore s = new PlotStore(null);
        assertFalse(s.stale("b2"), "기록 없음");
        s.districtBuild = "b1";
        assertFalse(s.stale("b2"), "주인이 없으면 상관없음");
        s.owners.put("c1", new PlotStore.Owner(A, "a", true, 1));
        s.customs.put("c1", new PlotStore.Custom("c1", 1, 0, 0, 3, 3, 0, 10, 2, Double.NaN, Double.NaN, Double.NaN, 0f));
        assertFalse(s.stale("b2"), "convert 집은 구역과 무관");
        s.owners.put("3", new PlotStore.Owner(B, "b", true, 1));
        assertTrue(s.stale("b2"));
        assertFalse(s.stale("b1"));
    }

    @Test
    void atomicWriteReplaces() throws Exception {
        Path f = dir.resolve("x.yml");
        PlotStore.writeAtomic(f, "a: 1\n");
        PlotStore.writeAtomic(f, "a: 2\n");
        assertEquals("a: 2\n", Files.readString(f));
        assertFalse(Files.exists(dir.resolve("x.yml.tmp")));
    }
}
