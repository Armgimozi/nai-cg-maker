package kr.labyrinth.village;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/**
 * 청사진 묶음: layout.json + layout 이 쓰는 조각 JSON. jar 안 {@code village/} 에서 읽고, 개발 중에는
 * {@code plugins/Labyrinth/village/} 에 같은 이름 파일이 있으면 그것을 먼저 쓴다 (jar 다시 빌드 없이 고쳐 보기).
 */
public final class VillageLibrary {

    public final Layout layout;
    public final Map<String, Blueprint> pieces;
    public final Planner planner;
    public final List<String> problems;

    private VillageLibrary(Layout layout, Map<String, Blueprint> pieces, Planner planner, List<String> problems) {
        this.layout = layout;
        this.pieces = pieces;
        this.planner = planner;
        this.problems = List.copyOf(problems);
    }

    public boolean ok() { return layout != null && planner != null; }

    /**
     * @param reader 경로("village/layout.json") → 내용 (없으면 null)
     */
    public static VillageLibrary load(Function<String, String> reader) {
        List<String> problems = new ArrayList<>();
        String lj = reader.apply("village/layout.json");
        if (lj == null) {
            problems.add("village/layout.json 없음 (청사진이 아직 jar 에 들어 있지 않음)");
            return new VillageLibrary(null, Map.of(), null, problems);
        }
        Layout layout;
        try {
            layout = Layout.parse(lj);
        } catch (IllegalArgumentException e) {
            problems.add(e.getMessage());
            return new VillageLibrary(null, Map.of(), null, problems);
        }
        Map<String, Blueprint> pieces = new LinkedHashMap<>();
        for (Layout.Entry e : layout.pieces) {
            if (pieces.containsKey(e.piece())) continue;
            String pj = reader.apply("village/pieces/" + e.piece() + ".json");
            if (pj == null) {
                problems.add("조각 village/pieces/" + e.piece() + ".json 없음");
                continue;
            }
            try {
                Blueprint bp = Blueprint.parse(pj);
                if (!bp.id.equals(e.piece())) problems.add("조각 파일 " + e.piece() + ".json 의 id 가 '" + bp.id + "'");
                pieces.put(e.piece(), bp);
            } catch (IllegalArgumentException ex) {
                problems.add(ex.getMessage());
            }
        }
        Planner planner = null;
        try {
            planner = new Planner(layout, pieces);
        } catch (IllegalArgumentException ex) {
            problems.add(ex.getMessage());
        }
        return new VillageLibrary(layout, pieces, planner, problems);
    }

    /** 플러그인: 데이터 폴더 village/ 우선, 없으면 jar. */
    public static VillageLibrary load(org.bukkit.plugin.java.JavaPlugin plugin) {
        File data = plugin.getDataFolder();
        return load(path -> {
            File f = new File(data, path);
            if (f.isFile()) {
                try {
                    return Files.readString(f.toPath(), StandardCharsets.UTF_8);
                } catch (IOException e) {
                    return null;
                }
            }
            try (InputStream in = plugin.getResource(path)) {
                return in == null ? null : new String(in.readAllBytes(), StandardCharsets.UTF_8);
            } catch (IOException e) {
                return null;
            }
        });
    }
}
