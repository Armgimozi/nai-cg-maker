package kr.labyrinth.village;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;

/** 테스트용 조각/배치 (src/test/resources/village/**). */
final class Fixtures {

    private Fixtures() {}

    static String read(String path) {
        try (InputStream in = Fixtures.class.getClassLoader().getResourceAsStream(path)) {
            return in == null ? null : new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    static VillageLibrary library() {
        VillageLibrary lib = VillageLibrary.load(Fixtures::read);
        if (!lib.ok() || !lib.problems.isEmpty()) throw new IllegalStateException("픽스처 문제: " + lib.problems);
        return lib;
    }

    static Blueprint piece(String id) { return Blueprint.parse(read("village/pieces/" + id + ".json")); }

    /** 중심 둘레 반경 r 평지 (높이 y). */
    static TerrainGrid flat(int r, int y) {
        TerrainGrid g = TerrainGrid.around(0, 0, r);
        g.fill(y);
        return g;
    }
}
