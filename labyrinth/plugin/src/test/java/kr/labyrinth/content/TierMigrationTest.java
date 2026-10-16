package kr.labyrinth.content;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Stream;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/**
 * 장비 층 이름표 → 숨은 단계 (0.3.5 gear_spec §4): items.yml 장비는 {@code tier} 를 갖고 {@code floor} 키가 없다.
 * 단계 N = 레벨 구간 Lv 5N−5 ~ 5N. 옮기는 동안 예전 {@code floor} 도 같은 값으로 읽고 검사기가 경고한다.
 */
class TierMigrationTest {

    /** gear_spec 그대로 단계보다 한 레벨 낮은 정예·대장간 세트 (Lv 5N−6 — 0.3.4 층 그대로). */
    static final Set<String> LOW_SETS = Set.of("rimefang", "crypt_mourner", "lorekeeper", "abyss_walker", "starless_choir");

    @Test
    void bundledGearHasATierAndNoFloorKey() {
        Content c = ContentLoader.load(Path.of("src/main/resources/content")).content();
        List<String> off = new ArrayList<>();
        int gear = 0;
        for (ItemDef d : c.items().values()) {
            if (!d.isGear()) {
                assertEquals(0, d.tier(), d.id() + " 장비가 아니면 단계 0");
                continue;
            }
            gear++;
            assertTrue(d.raw().has("tier"), d.id() + " tier 없음");
            assertFalse(d.raw().has("floor"), d.id() + " floor 남음");
            int t = d.tier();
            assertTrue(t >= 1 && t <= 10, d.id() + " 단계 " + t);
            int lo = 5 * t - 5;
            if (d.setBonus() != null && LOW_SETS.contains(d.setBonus())) lo = 5 * t - 6;
            if (d.levelReq() < lo || d.levelReq() > 5 * t) off.add(d.id() + " Lv" + d.levelReq() + " 단계 " + t);
            if (d.levelReq() <= 1) assertEquals(1, t, d.id() + " Lv1 장비는 단계 1");
        }
        assertEquals(List.of(), off, "레벨이 단계 구간 밖");
        assertTrue(gear >= 380, "장비 " + gear);
    }

    @Test
    void oldFloorKeyStillReadsAsTierWithAWarning(@TempDir Path dir) throws IOException {
        Path src = Path.of("src/main/resources/content");
        try (Stream<Path> files = Files.walk(src)) {
            for (Path p : (Iterable<Path>) files::iterator) {
                Path to = dir.resolve(src.relativize(p).toString());
                if (Files.isDirectory(p)) Files.createDirectories(to);
                else Files.copy(p, to);
            }
        }
        // corridor_longsword 의 tier: 1 을 예전 꼴 floor: 1 로
        Path items = dir.resolve("items.yml");
        List<String> lines = new ArrayList<>(Files.readAllLines(items, StandardCharsets.UTF_8));
        int at = lines.indexOf("  corridor_longsword:");
        assertTrue(at >= 0);
        boolean done = false;
        for (int i = at + 1; i < lines.size() && lines.get(i).startsWith("    "); i++) {
            if (lines.get(i).equals("    tier: 1")) {
                lines.set(i, "    floor: 1");
                done = true;
                break;
            }
        }
        assertTrue(done);
        Files.write(items, lines, StandardCharsets.UTF_8);
        ContentLoader.Result r = ContentLoader.load(dir);
        ItemDef d = r.content().item("corridor_longsword");
        assertEquals(1, d.tier());
        assertEquals(1, d.floor());
        ContentValidator.Report rep = ContentValidator.validate(r.content());
        assertTrue(rep.warnings().stream().anyMatch(w -> w.contains("corridor_longsword") && w.contains("tier")), rep.warnings().toString());
    }
}
