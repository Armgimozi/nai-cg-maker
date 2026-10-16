package kr.labyrinth.village;

import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/**
 * 구역 청사진 묶음 (0.3.6): jar {@code village/districts/index.json} 의 구역마다 {@code <id>.json} 배치 + 조각
 * ({@code village/pieces/}, 마을과 같은 폴더) + 지문 ({@code <id>.fp}). VillageLibrary 처럼 데이터 폴더 {@code plugins/Labyrinth/village/}
 * 에 같은 이름 파일이 있으면 그것을 먼저 쓴다 (개발용). 짓는 차례 = order 작은 것부터 (광산 → 0.3.7 집 구역).
 */
public final class DistrictLibrary {

    /** 구역 하나. fp = 지문 (없거나 이 jar 규칙과 안 맞으면 null — 비자연 검사만). */
    public record Entry(DistrictLayout layout, Map<String, Blueprint> pieces, DistrictFingerprint fp, List<String> problems) {
        public String id() { return layout.id; }

        public boolean ok() { return problems.isEmpty(); }
    }

    public final List<Entry> districts;
    public final List<String> problems;

    private DistrictLibrary(List<Entry> districts, List<String> problems) {
        this.districts = List.copyOf(districts);
        this.problems = List.copyOf(problems);
    }

    public Entry get(String id) {
        for (Entry e : districts) if (e.id().equals(id)) return e;
        return null;
    }

    public List<String> ids() {
        List<String> out = new ArrayList<>();
        for (Entry e : districts) out.add(e.id());
        return out;
    }

    /**
     * @param text 경로 → 글 (없으면 null)
     * @param bin  경로 → 바이트 (없으면 null)
     */
    public static DistrictLibrary load(Function<String, String> text, Function<String, byte[]> bin) {
        List<String> problems = new ArrayList<>();
        List<Entry> out = new ArrayList<>();
        String idx = text.apply("village/districts/index.json");
        if (idx == null) return new DistrictLibrary(out, problems);
        List<String> ids = new ArrayList<>();
        try {
            for (JsonElement e : JsonParser.parseString(idx).getAsJsonObject().getAsJsonArray("districts")) ids.add(e.getAsString());
        } catch (RuntimeException e) {
            problems.add("village/districts/index.json 형식 오류: " + e.getMessage());
            return new DistrictLibrary(out, problems);
        }
        for (String id : ids) {
            String json = text.apply("village/districts/" + id + ".json");
            if (json == null) {
                problems.add("구역 " + id + ": village/districts/" + id + ".json 없음");
                continue;
            }
            DistrictLayout layout;
            try {
                layout = DistrictLayout.parse(json);
            } catch (IllegalArgumentException ex) {
                problems.add(ex.getMessage());
                continue;
            }
            List<String> pr = new ArrayList<>();
            Map<String, Blueprint> pieces = new LinkedHashMap<>();
            for (Layout.Entry e : layout.pieces) {
                if (pieces.containsKey(e.piece())) continue;
                String pj = text.apply("village/pieces/" + e.piece() + ".json");
                if (pj == null) {
                    pr.add("조각 village/pieces/" + e.piece() + ".json 없음");
                    continue;
                }
                try {
                    pieces.put(e.piece(), Blueprint.parse(pj));
                } catch (IllegalArgumentException ex) {
                    pr.add(ex.getMessage());
                }
            }
            DistrictFingerprint fp = null;
            byte[] raw = bin.apply("village/districts/" + layout.fingerprint);
            if (raw == null) {
                pr.add("지문 " + layout.fingerprint + " 없음 — 배포 월드 검사를 비자연 블록만으로");
            } else {
                try {
                    fp = DistrictFingerprint.read(raw);
                    if (!fp.compatible()) {
                        pr.add("지문 " + layout.fingerprint + " 의 블록 분류가 이 jar 와 다름 (district_fingerprint.py 다시) — 비자연 검사만");
                        fp = null;
                    }
                } catch (IOException ex) {
                    pr.add("지문 " + layout.fingerprint + " 읽기 실패: " + ex.getMessage());
                }
            }
            // 지문 문제는 짓기를 막지 않는다 (비자연 검사로 대신) — 조각 문제만 막는다
            List<String> blocking = new ArrayList<>();
            for (String s : pr) if (!s.startsWith("지문")) blocking.add(s);
            for (String s : pr) problems.add("구역 " + id + ": " + s);
            out.add(new Entry(layout, pieces, fp, blocking));
        }
        out.sort(Comparator.comparingInt(e -> e.layout().order));
        return new DistrictLibrary(out, problems);
    }

    /** 플러그인: 데이터 폴더 village/ 우선, 없으면 jar. */
    public static DistrictLibrary load(org.bukkit.plugin.java.JavaPlugin plugin) {
        File data = plugin.getDataFolder();
        Function<String, byte[]> bin = path -> {
            File f = new File(data, path);
            try {
                if (f.isFile()) return Files.readAllBytes(f.toPath());
            } catch (IOException e) {
                return null;
            }
            try (InputStream in = plugin.getResource(path)) {
                return in == null ? null : in.readAllBytes();
            } catch (IOException e) {
                return null;
            }
        };
        return load(path -> {
            byte[] b = bin.apply(path);
            return b == null ? null : new String(b, StandardCharsets.UTF_8);
        }, bin);
    }
}
