package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;

/** jar 에 들어갈 진짜 청사진(src/main/resources/village)이 Java 파서·계획기와 맞는지 — 설계 도구 결과물 검사. */
class BundledVillageTest {

    static final Path DIR = Path.of("src/main/resources");

    static String read(String rel) {
        Path f = DIR.resolve(rel);
        try {
            return Files.isRegularFile(f) ? Files.readString(f, StandardCharsets.UTF_8) : null;
        } catch (IOException e) {
            return null;
        }
    }

    @Test
    void bundledBlueprintsParseAndPlanOnFlatGround() {
        assumeTrue(read("village/layout.json") != null, "청사진이 아직 없음");
        VillageLibrary lib = VillageLibrary.load(BundledVillageTest::read);
        assertTrue(lib.problems.isEmpty(), "청사진 문제: " + lib.problems);
        assertTrue(lib.ok());
        TerrainGrid flat = Fixtures.flat(lib.planner.reach() + 4, 64);
        for (int t = 0; t < 4; t++) {
            Plan p = lib.planner.plan(flat, 0, 0, t, true);
            assertTrue(p.ok(), "평지 회전 " + t + ": " + p.reason);
            List<String> ov = Planner.overlaps(p.pieces, p.paths);
            assertTrue(ov.isEmpty(), "겹침: " + ov);
            assertEquals(0, p.steepPaths);
            VillageMeta m = Markers.meta(p, lib.layout);
            assertTrue(m.spawn != null, "spawn 마커");
        }
    }
}
