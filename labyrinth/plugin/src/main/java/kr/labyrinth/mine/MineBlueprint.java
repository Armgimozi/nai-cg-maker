package kr.labyrinth.mine;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 광산 층 청사진 (jar {@code mine/levels/L<n>.json}, tools/mine/gen_mine.py 생성물). 순수 — 서버 없이 파싱·검사.
 * <p>
 * 형식: size [61,16,61] · origin = 칸 (0,0,0) 의 광산 월드 좌표 · palette 글자 → 블록 상태 · layers[y][z] = 글자 줄 (x 순).
 * 글자 ' ' = 건드리지 않음(공허) · '.' = 공기 · 팔레트 값이 {@code @vein:<광석 id>} · {@code @gem:<보석 id>} 이면 짓는 순간
 * mine.yml 의 그 광석·보석 블록으로 바꾼다 (블록을 바꿔도 청사진은 그대로). 마커(광산 월드 좌표): lift · landing · office · sign · ambient.
 * 광맥 번호 = (y, z, x) 정렬 순 (계약 §2.3) — {@link #veins()}·{@link #gems()} 가 그 차례다.
 */
public final class MineBlueprint {

    public static final int KEEP = ' ';
    public static final int AIR = '.';
    public static final String VEIN = "@vein:";
    public static final String GEM = "@gem:";

    /** 발 높이에서 걸어 지나갈 수 있는 블록 (tools/mine/levels.py PASSABLE 과 같음). */
    static final Set<String> PASSABLE = Set.of("rail", "moss_carpet", "light", "oak_wall_sign", "dark_oak_wall_sign", "spruce_wall_sign",
            "acacia_wall_sign", "warped_wall_sign", "crimson_wall_sign", "glow_lichen");

    public record Marker(String type, double[] pos, float yaw, List<String> lines, String fx) {
        public int bx() { return (int) Math.floor(pos[0]); }
        public int by() { return (int) Math.floor(pos[1]); }
        public int bz() { return (int) Math.floor(pos[2]); }
    }

    /** 광맥 하나 또는 보석 노드 하나 (광산 월드 좌표). face = 보이는 면 쪽 (보석 결정 방향). */
    public record Node(int index, int x, int y, int z, String id, int fx, int fy, int fz) {
        public long key() { return MineBlueprint.blockKey(x, y, z); }
    }

    public final String id;
    public final int level;
    public final int w, h, d;
    public final int ox, oy, oz;
    public final int floorY;
    public final String sha1;
    private final Map<Integer, String> palette;
    private final int[] cells;
    private final List<Marker> markers;
    private final List<Node> veins;
    private final List<Node> gems;

    private MineBlueprint(String id, int level, int w, int h, int d, int ox, int oy, int oz, int floorY, String sha1,
                          Map<Integer, String> palette, int[] cells, List<Marker> markers) {
        this.id = id;
        this.level = level;
        this.w = w;
        this.h = h;
        this.d = d;
        this.ox = ox;
        this.oy = oy;
        this.oz = oz;
        this.floorY = floorY;
        this.sha1 = sha1;
        this.palette = Collections.unmodifiableMap(palette);
        this.cells = cells;
        this.markers = List.copyOf(markers);
        List<Node> v = new ArrayList<>();
        List<Node> g = new ArrayList<>();
        // (y, z, x) 차례 = 칸 배열 차례
        for (int y = 0; y < h; y++) {
            for (int z = 0; z < d; z++) {
                for (int x = 0; x < w; x++) {
                    String s = palette.get(cell(x, y, z));
                    if (s == null) continue;
                    if (s.startsWith(VEIN)) {
                        int[] f = face(x, y, z);
                        v.add(new Node(v.size(), x + ox, y + oy, z + oz, s.substring(VEIN.length()), f[0], f[1], f[2]));
                    } else if (s.startsWith(GEM)) {
                        int[] f = face(x, y, z);
                        g.add(new Node(g.size(), x + ox, y + oy, z + oz, s.substring(GEM.length()), f[0], f[1], f[2]));
                    }
                }
            }
        }
        this.veins = List.copyOf(v);
        this.gems = List.copyOf(g);
    }

    // ── 칸 ──────────────────────────────────────────────────────────────

    public int cell(int x, int y, int z) {
        if (x < 0 || y < 0 || z < 0 || x >= w || y >= h || z >= d) return KEEP;
        return cells[(y * d + z) * w + x];
    }

    /** 팔레트 값 (KEEP·AIR 은 null). */
    public String state(int cp) { return palette.get(cp); }

    public Map<Integer, String> palette() { return palette; }

    public List<Marker> markers() { return markers; }

    public List<Marker> markers(String type) {
        List<Marker> out = new ArrayList<>();
        for (Marker m : markers) if (m.type().equals(type)) out.add(m);
        return out;
    }

    public Marker marker(String type) {
        for (Marker m : markers) if (m.type().equals(type)) return m;
        return null;
    }

    public List<Node> veins() { return veins; }

    public List<Node> gems() { return gems; }

    public static long blockKey(int x, int y, int z) {
        return ((long) (x & 0x3FFFFFF) << 38) | ((long) (z & 0x3FFFFFF) << 12) | (y & 0xFFF);
    }

    /** 블록 id (minecraft: 뒤, 속성 앞). 논리 글자·공기면 null. */
    static String blockId(String state) {
        if (state == null || state.startsWith("@")) return null;
        String s = state.startsWith("minecraft:") ? state.substring(10) : state;
        int b = s.indexOf('[');
        return b < 0 ? s : s.substring(0, b);
    }

    boolean passable(int x, int y, int z) {
        int c = cell(x, y, z);
        if (c == AIR) return true;
        if (c == KEEP) return false;
        String id = blockId(palette.get(c));
        return id != null && PASSABLE.contains(id);
    }

    boolean solid(int x, int y, int z) {
        int c = cell(x, y, z);
        if (c == AIR || c == KEEP) return false;
        String s = palette.get(c);
        if (s.startsWith("@")) return true;
        return !PASSABLE.contains(blockId(s));
    }

    /** 칸 (x, z) 가 설 수 있는 바닥인가: 그 층 바닥 블록 위 두 칸이 비어 있음. */
    public boolean standable(int x, int z) {
        int fl = floorY - oy;
        return solid(x, fl, z) && passable(x, fl + 1, z) && passable(x, fl + 2, z);
    }

    private int[] face(int x, int y, int z) {
        int fl = floorY - oy;
        int[][] dirs = {{0, 0, 1}, {0, 0, -1}, {1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}};
        for (int[] dd : dirs) {
            int ax = x + dd[0], ay = y + dd[1], az = z + dd[2];
            if (dd[1] == 0 && passable(ax, ay, az) && solid(ax, fl, az)) return dd;
        }
        for (int[] dd : dirs) if (passable(x + dd[0], y + dd[1], z + dd[2])) return dd;
        return new int[] {0, 1, 0};
    }

    // ── 검사 (자가 진단·시험) ────────────────────────────────────────────

    /** 내리는 자리에서 걸어 닿는 바닥 칸 (청사진 좌표 x·z). */
    public Set<Long> reachableFloor() {
        Marker land = marker("landing");
        Set<Long> seen = new HashSet<>();
        if (land == null) return seen;
        int sx = land.bx() - ox, sz = land.bz() - oz;
        if (!standable(sx, sz)) return seen;
        ArrayDeque<int[]> q = new ArrayDeque<>();
        q.add(new int[] {sx, sz});
        seen.add(col(sx, sz));
        while (!q.isEmpty()) {
            int[] p = q.poll();
            for (int[] dd : new int[][] {{1, 0}, {-1, 0}, {0, 1}, {0, -1}}) {
                int nx = p[0] + dd[0], nz = p[1] + dd[1];
                if (standable(nx, nz) && seen.add(col(nx, nz))) q.add(new int[] {nx, nz});
            }
        }
        return seen;
    }

    public int floorCount() {
        int n = 0;
        for (int x = 0; x < w; x++) for (int z = 0; z < d; z++) if (standable(x, z)) n++;
        return n;
    }

    static long col(int x, int z) { return ((long) x << 32) | (z & 0xffffffffL); }

    /**
     * 손이 닿지 않는 광맥·보석 수: 보이는 면(걸어 지나갈 수 있는 이웃)이 없거나, 걸어 닿는 어느 바닥에서도 눈(발 + 1.62)에서
     * 블록 상자까지 바닐라 손 닿는 거리 4.5 를 넘는 것. 매크로 막기용 한도가 아니라 "캘 수 있는가" 검사다.
     */
    public int unreachable() {
        Set<Long> floor = reachableFloor();
        int bad = 0;
        List<Node> all = new ArrayList<>(veins);
        all.addAll(gems);
        for (Node n : all) if (!reachable(n, floor)) bad++;
        return bad;
    }

    boolean reachable(Node n, Set<Long> floor) {
        int x = n.x() - ox, y = n.y() - oy, z = n.z() - oz;
        boolean exposed = false;
        for (int[] dd : new int[][] {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}}) {
            if (passable(x + dd[0], y + dd[1], z + dd[2])) exposed = true;
        }
        if (!exposed) return false;
        double eyeY = floorY - oy + 1 + 1.62;
        for (int fx = x - 6; fx <= x + 6; fx++) {
            for (int fz = z - 6; fz <= z + 6; fz++) {
                if (!floor.contains(col(fx, fz))) continue;
                double ex = Math.max(fx + 0.3, Math.min(fx + 0.7, x + 0.5));
                double ez = Math.max(fz + 0.3, Math.min(fz + 0.7, z + 0.5));
                double dx = Math.max(Math.max(x - ex, 0), ex - (x + 1));
                double dy = Math.max(Math.max(y - eyeY, 0), eyeY - (y + 1));
                double dz = Math.max(Math.max(z - ez, 0), ez - (z + 1));
                if (Math.sqrt(dx * dx + dy * dy + dz * dz) <= 4.5) return true;
            }
        }
        return false;
    }

    /** 논리 글자가 아닌 칸에 쓰인 블록 id 들 (장식·벽·바닥·빛). */
    public Set<String> usedBlocks() {
        Set<String> out = new HashSet<>();
        for (int c : cells) {
            if (c == KEEP || c == AIR) continue;
            String id = blockId(palette.get(c));
            if (id != null) out.add("minecraft:" + id);
        }
        return out;
    }

    /** 칸 차례대로 (청사진 x, y, z, 글자) — 짓기·자가 진단. */
    public interface CellVisitor {
        void visit(int x, int y, int z, int cp);
    }

    public void forEachCell(CellVisitor v) {
        for (int y = 0; y < h; y++) {
            for (int z = 0; z < d; z++) {
                for (int x = 0; x < w; x++) {
                    int c = cells[(y * d + z) * w + x];
                    if (c != KEEP) v.visit(x, y, z, c);
                }
            }
        }
    }

    public int nonKeepCount() {
        int n = 0;
        for (int c : cells) if (c != KEEP) n++;
        return n;
    }

    // ── 파싱 ────────────────────────────────────────────────────────────

    public static MineBlueprint parse(String json) {
        JsonObject o;
        try {
            o = JsonParser.parseString(json).getAsJsonObject();
        } catch (RuntimeException e) {
            throw new IllegalArgumentException("광산 청사진 JSON 형식 오류: " + e.getMessage());
        }
        List<String> problems = new ArrayList<>();
        String id = o.has("id") ? o.get("id").getAsString() : "?";
        int level = o.has("level") ? o.get("level").getAsInt() : 0;
        JsonArray size = o.getAsJsonArray("size");
        JsonArray origin = o.getAsJsonArray("origin");
        if (size == null || size.size() != 3 || origin == null || origin.size() != 3) throw new IllegalArgumentException(id + ": size·origin 없음");
        int w = size.get(0).getAsInt(), h = size.get(1).getAsInt(), d = size.get(2).getAsInt();
        if (w <= 0 || h <= 0 || d <= 0 || w > 128 || h > 64 || d > 128) throw new IllegalArgumentException(id + ": size 범위");
        int ox = origin.get(0).getAsInt(), oy = origin.get(1).getAsInt(), oz = origin.get(2).getAsInt();
        int floorY = o.has("floor_y") ? o.get("floor_y").getAsInt() : oy + 2;
        Map<Integer, String> pal = new LinkedHashMap<>();
        JsonObject po = o.getAsJsonObject("palette");
        if (po != null) {
            for (Map.Entry<String, JsonElement> e : po.entrySet()) {
                String k = e.getKey();
                if (k.codePointCount(0, k.length()) != 1) {
                    problems.add("팔레트 글자 '" + k + "'");
                    continue;
                }
                int cp = k.codePointAt(0);
                if (cp == KEEP || cp == AIR) {
                    problems.add("팔레트에 ' '·'.' 를 쓸 수 없음");
                    continue;
                }
                String v = e.getValue().getAsString().trim();
                if (!v.startsWith(VEIN) && !v.startsWith(GEM)
                        && !v.matches("minecraft:[a-z0-9_]+(\\[[a-z0-9_]+=[a-z0-9_]+(,[a-z0-9_]+=[a-z0-9_]+)*\\])?")) {
                    problems.add("팔레트 '" + k + "' 형식: " + v);
                }
                pal.put(cp, v);
            }
        }
        int[] cells = new int[w * h * d];
        JsonArray layers = o.getAsJsonArray("layers");
        if (layers == null || layers.size() != h) problems.add("layers 수 ≠ " + h);
        for (int y = 0; y < h; y++) {
            JsonArray rows = layers != null && y < layers.size() ? layers.get(y).getAsJsonArray() : null;
            if (rows == null || rows.size() != d) {
                problems.add("layer " + y + " 줄 수");
                continue;
            }
            for (int z = 0; z < d; z++) {
                int[] cps = rows.get(z).getAsString().codePoints().toArray();
                if (cps.length != w) problems.add("layer " + y + " z=" + z + " 길이 " + cps.length);
                for (int x = 0; x < w; x++) {
                    int cp = x < cps.length ? cps[x] : KEEP;
                    if (cp != KEEP && cp != AIR && !pal.containsKey(cp)) {
                        problems.add("팔레트에 없는 글자 '" + new String(Character.toChars(cp)) + "'");
                        cp = KEEP;
                    }
                    cells[(y * d + z) * w + x] = cp;
                }
            }
        }
        List<Marker> markers = new ArrayList<>();
        JsonArray ms = o.getAsJsonArray("markers");
        if (ms != null) {
            for (JsonElement me : ms) {
                JsonObject m = me.getAsJsonObject();
                JsonArray pa = m.getAsJsonArray("pos");
                double[] pos = new double[3];
                if (pa != null && pa.size() >= 3) for (int i = 0; i < 3; i++) pos[i] = pa.get(i).getAsDouble();
                List<String> lines = new ArrayList<>();
                if (m.has("lines")) for (JsonElement le : m.getAsJsonArray("lines")) lines.add(le.getAsString());
                markers.add(new Marker(m.get("type").getAsString(), pos, m.has("yaw") ? m.get("yaw").getAsFloat() : 0f, List.copyOf(lines),
                        m.has("fx") ? m.get("fx").getAsString() : null));
            }
        }
        if (!problems.isEmpty()) throw new IllegalArgumentException(id + ": " + String.join(" · ", problems.subList(0, Math.min(8, problems.size()))));
        return new MineBlueprint(id, level, w, h, d, ox, oy, oz, floorY, sha1(json), pal, cells, markers);
    }

    static String sha1(String s) {
        try {
            byte[] b = MessageDigest.getInstance("SHA-1").digest(s.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(b);
        } catch (Exception e) {
            return Integer.toHexString(s.hashCode());
        }
    }
}
