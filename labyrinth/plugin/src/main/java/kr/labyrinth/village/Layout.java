package kr.labyrinth.village;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 마을 배치 layout.json (VILLAGE.md §3). 마을 좌표: 중심 (0, 0), 정방향에서 게이트(마을 앞)가 북쪽(−Z).
 * 조각 위치 {@code at} 은 기준점이고, 실제 자리는 계획기({@link Planner})가 slack 안에서 지형에 맞춰 옮긴다.
 */
public final class Layout {

    /** 조각 배치 한 줄. dy/slack 은 없으면 null. opts = 0.3.7 구역 조각 손잡이 (없으면 {@link Opts#NONE}). */
    public record Entry(int index, String piece, int atX, int atZ, Dir front, Integer dy, Integer slack, Opts opts) {
        public Entry {
            opts = opts == null ? Opts.NONE : opts;
        }

        public Entry(int index, String piece, int atX, int atZ, Dir front, Integer dy, Integer slack) {
            this(index, piece, atX, atZ, front, dy, slack, Opts.NONE);
        }
    }

    /**
     * 구역 조각 손잡이 (0.3.7 집 구역 — district json pieces[]).
     * @param maxFill   이 조각 깎기·메우기 한도 (null = 구역 options.max_fill) — 집터 바닥 12 (구덩이 메움)
     * @param floorRef  이 조각들(layout 순번, 앞에 놓인 것) 바닥 가운데 가장 높은 것을 바닥으로 — 울타리 줄 (낮은 쪽 집터 앞은 옹벽)
     * @param nearRef   이 조각(순번, 앞에 놓인 것) 바닥에서 {@code nearDelta} 칸 안으로 (−1 = 없음) — 거리 건너 마주 보는 집
     * @param tag       집터 번호 (표지판 글·우클릭의 {plot} · 구역 기록 plots:) — null 이면 없음
     */
    public record Opts(Integer maxFill, List<Integer> floorRef, int nearRef, int nearDelta, String tag) {
        public static final Opts NONE = new Opts(null, List.of(), -1, 0, null);

        public Opts {
            floorRef = floorRef == null ? List.of() : List.copyOf(floorRef);
        }

        public boolean none() { return maxFill == null && floorRef.isEmpty() && nearRef < 0 && tag == null; }

        /** 순번 바꾸기 (자리마다 뺀 조각이 있으면 layout 순번이 당겨진다 — 없어진 조각은 뺌). */
        public Opts remap(java.util.function.IntUnaryOperator to) {
            List<Integer> fr = new ArrayList<>();
            for (int r : floorRef) {
                int n = to.applyAsInt(r);
                if (n >= 0) fr.add(n);
            }
            int nr = nearRef < 0 ? -1 : to.applyAsInt(nearRef);
            return new Opts(maxFill, fr, nr, nr < 0 ? 0 : nearDelta, tag);
        }
    }

    /**
     * 길: 꺾은선 점들(마을 좌표), 폭, 스타일, follow = 길 높이가 양 끝 직선에서 지형을 따라 벗어날 수 있는 칸
     * (기본 {@link Planner#PATH_FOLLOW}; 0.3.6.1 광산 마당은 0 — 숙소 앞보다 마당이 불룩 솟지 않게).
     */
    public record PathDef(int index, List<int[]> points, int width, String style, int follow) {
        public PathDef(int index, List<int[]> points, int width, String style) { this(index, points, width, style, Planner.PATH_FOLLOW); }
    }

    /** 추가 단: 가운데 칸 at, 크기 [w, d], 광장 높이 H0 기준 dy. */
    public record Terrace(int atX, int atZ, int w, int d, int dy) {}

    public final String name;
    public final int radius;
    /** 혼합 띠 B (기본 16). */
    public final int blend;
    public final List<Entry> pieces;
    public final List<PathDef> paths;
    public final Map<String, List<Blueprint.Weighted>> pathStyles;
    public final List<Terrace> terraces;

    private Layout(String name, int radius, int blend, List<Entry> pieces, List<PathDef> paths,
                   Map<String, List<Blueprint.Weighted>> styles, List<Terrace> terraces) {
        this.name = name;
        this.radius = radius;
        this.blend = blend;
        this.pieces = List.copyOf(pieces);
        this.paths = List.copyOf(paths);
        this.pathStyles = Collections.unmodifiableMap(styles);
        this.terraces = List.copyOf(terraces);
    }

    /** 코드로 만든 배치 (0.3.6 구역: 자리마다 월드 방향으로 펼친 배치 — {@link DistrictLayout#place}). */
    static Layout of(String name, int radius, int blend, List<Entry> pieces, List<PathDef> paths,
                     Map<String, List<Blueprint.Weighted>> styles) {
        return new Layout(name, radius, blend, pieces, paths, new LinkedHashMap<>(styles), List.of());
    }

    public static Layout parse(String json) {
        JsonObject o;
        try {
            o = JsonParser.parseString(json).getAsJsonObject();
        } catch (RuntimeException e) {
            throw new IllegalArgumentException("layout.json 형식 오류: " + e.getMessage());
        }
        List<String> problems = new ArrayList<>();
        String name = Blueprint.str(o, "name", "마을");
        int radius = o.has("radius") ? o.get("radius").getAsInt() : 32;
        int blend = o.has("blend") ? o.get("blend").getAsInt() : 16;
        if (radius < 4 || radius > 96) problems.add("radius " + radius + " (4..96)");
        if (blend < 2 || blend > 48) problems.add("blend " + blend + " (2..48)");

        List<Entry> pieces = new ArrayList<>();
        JsonArray pa = Blueprint.arr(o, "pieces");
        if (pa == null || pa.isEmpty()) problems.add("pieces 없음");
        else {
            for (JsonElement e : pa) {
                JsonObject p = e.getAsJsonObject();
                String piece = Blueprint.str(p, "piece", null);
                JsonArray at = Blueprint.arr(p, "at");
                if (piece == null || at == null || at.size() != 2) {
                    problems.add("pieces[" + pieces.size() + "] piece/at 없음");
                    continue;
                }
                Dir front = Dir.parse(Blueprint.str(p, "front", "north"));
                if (front == null) {
                    problems.add(piece + ": front 는 north/east/south/west");
                    front = Dir.NORTH;
                }
                pieces.add(new Entry(pieces.size(), piece, at.get(0).getAsInt(), at.get(1).getAsInt(), front,
                        p.has("dy") ? p.get("dy").getAsInt() : null, p.has("slack") ? p.get("slack").getAsInt() : null));
            }
        }

        List<PathDef> paths = new ArrayList<>();
        JsonArray ps = Blueprint.arr(o, "paths");
        if (ps != null) {
            for (JsonElement e : ps) {
                JsonObject p = e.getAsJsonObject();
                List<int[]> pts = new ArrayList<>();
                JsonArray pp = Blueprint.arr(p, "points");
                if (pp != null) for (JsonElement q : pp) pts.add(Blueprint.ints(q.getAsJsonArray()));
                if (pts.size() < 2) {
                    problems.add("paths[" + paths.size() + "] 점이 2개 미만");
                    continue;
                }
                for (int[] q : pts) if (q.length != 2) problems.add("paths[" + paths.size() + "] 점은 [x, z]");
                int width = p.has("width") ? p.get("width").getAsInt() : 3;
                paths.add(new PathDef(paths.size(), pts, Math.max(1, Math.min(9, width)), Blueprint.str(p, "style", "main")));
            }
        }

        Map<String, List<Blueprint.Weighted>> styles = new LinkedHashMap<>();
        if (o.has("path_styles") && o.get("path_styles").isJsonObject()) {
            for (Map.Entry<String, JsonElement> e : o.getAsJsonObject("path_styles").entrySet()) {
                styles.put(e.getKey(), Blueprint.weighted(e.getValue().getAsJsonArray()));
            }
        }
        styles.putIfAbsent("main", List.of(new Blueprint.Weighted("minecraft:stone_bricks", 4),
                new Blueprint.Weighted("minecraft:cracked_stone_bricks", 1), new Blueprint.Weighted("minecraft:polished_andesite", 2),
                new Blueprint.Weighted("minecraft:mossy_stone_bricks", 1)));
        styles.putIfAbsent("lane", List.of(new Blueprint.Weighted("minecraft:dirt_path", 6),
                new Blueprint.Weighted("minecraft:coarse_dirt", 1), new Blueprint.Weighted("minecraft:gravel", 1)));
        for (PathDef p : paths) if (!styles.containsKey(p.style())) problems.add("길 스타일 '" + p.style() + "' 없음");

        List<Terrace> terraces = new ArrayList<>();
        JsonArray ts = Blueprint.arr(o, "terraces");
        if (ts != null) {
            for (JsonElement e : ts) {
                JsonObject t = e.getAsJsonObject();
                JsonArray at = Blueprint.arr(t, "at"), size = Blueprint.arr(t, "size");
                if (at == null || size == null || at.size() != 2 || size.size() != 2) {
                    problems.add("terraces[" + terraces.size() + "] at/size 오류");
                    continue;
                }
                terraces.add(new Terrace(at.get(0).getAsInt(), at.get(1).getAsInt(), size.get(0).getAsInt(), size.get(1).getAsInt(),
                        t.has("dy") ? t.get("dy").getAsInt() : 0));
            }
        }
        if (!problems.isEmpty()) throw new IllegalArgumentException("layout.json: " + String.join(" · ", problems));
        return new Layout(name, radius, blend, pieces, paths, styles, terraces);
    }
}
