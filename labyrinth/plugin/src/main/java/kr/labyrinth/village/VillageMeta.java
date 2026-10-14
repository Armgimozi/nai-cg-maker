package kr.labyrinth.village;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Base64;
import java.util.BitSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * {@code <월드 폴더>/labyrinth-village.yml} (VILLAGE.md §4.2) — 월드와 함께 배포되는 마을 메타데이터.
 * 좌표는 정수 블록 좌표, 위치(spawn/entrance/npcs)는 [x, y, z, yaw] (x/z 는 칸 가운데 .5).
 * 자가 진단용으로 조각 자리·길 칸·목표 높이장도 함께 적는다.
 */
public final class VillageMeta {

    public static final String FILE = "labyrinth-village.yml";

    /** [x, y, z, yaw]. */
    public record Pos(double x, double y, double z, float yaw) {}

    public record Box(int x0, int y0, int z0, int x1, int y1, int z1) {
        public boolean contains(int x, int y, int z) {
            return x >= x0 && x <= x1 && y >= y0 && y <= y1 && z >= z0 && z <= z1;
        }
    }

    public record Ambient(int x, int y, int z, String fx) {}

    /** 놓은 조각: 청사진 id, 총 회전, 상자 모서리 (x0, z0), 단 높이, slack 오프셋, layout 순번. */
    public record PieceRec(int index, String piece, int turns, int x0, int z0, int floor, int dx, int dz) {}

    /** 길: 순번, 폭, 스타일, 월드 꺾은선, 붙은 조각 순번(−1 없음), 칸 [x, z, y]. */
    public record PathRec(int index, int width, String style, List<int[]> points, int attachA, int attachB, List<int[]> cells) {}

    /** 목표 높이장 (격자 왼쪽-북쪽 모서리, 한 변, 기준 높이, 높이 − 기준(바이트), 바뀐 칸 비트). */
    public record TerrainRec(int x0, int z0, int n, int base, byte[] heights, BitSet changed) {
        public boolean in(int x, int z) { return x >= x0 && z >= z0 && x < x0 + n && z < z0 + n; }

        public int height(int x, int z) { return base + (heights[(z - z0) * n + (x - x0)] & 0xFF); }

        public boolean changed(int x, int z) { return changed.get((z - z0) * n + (x - x0)); }
    }

    public int format = 1;
    public String name = "마을";
    public int[] center = {0, 64, 0};
    public String rotation = "NONE";
    public int radius = 32;
    public int blend = 16;
    public Pos spawn;
    public Pos entrance;
    public final Map<String, Pos> npcs = new LinkedHashMap<>();
    /** "x,y,z" → action. */
    public final Map<String, String> interact = new LinkedHashMap<>();
    public final List<Ambient> ambient = new ArrayList<>();
    public final List<Box> protect = new ArrayList<>();
    public final List<PieceRec> pieces = new ArrayList<>();
    public final List<PathRec> paths = new ArrayList<>();
    public TerrainRec terrain;
    public String buildId = "";
    public String builtAt = "";
    public String pluginVersion = "";

    public static String key(int x, int y, int z) { return x + "," + y + "," + z; }

    /** 이 마을을 구별하는 열쇠: 빌드 id (없으면 이름+중심). */
    public String villageKey() {
        return buildId != null && !buildId.isBlank() ? buildId : name + "@" + center[0] + "," + center[2];
    }

    // ── 쓰기 ─────────────────────────────────────────────────────────────

    public String toYaml() {
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(List.of("미궁 라비린스 — 미리 지은 마을 메타데이터 (/labadmin village build 가 씀, 직접 고치지 마세요)",
                "VILLAGE.md §4.2"));
        y.set("format", format);
        y.set("name", name);
        y.set("center", ints(center));
        y.set("rotation", rotation);
        y.set("radius", radius);
        y.set("blend", blend);
        if (spawn != null) y.set("spawn", pos(spawn));
        if (entrance != null) y.set("entrance", pos(entrance));
        for (Map.Entry<String, Pos> e : npcs.entrySet()) y.set("npcs." + e.getKey(), pos(e.getValue()));
        Map<String, Object> inter = new LinkedHashMap<>(interact);
        y.set("interact", inter);
        List<List<Object>> amb = new ArrayList<>();
        for (Ambient a : ambient) amb.add(List.of(a.x(), a.y(), a.z(), a.fx()));
        y.set("ambient", amb);
        List<List<Integer>> prot = new ArrayList<>();
        for (Box b : protect) prot.add(List.of(b.x0(), b.y0(), b.z0(), b.x1(), b.y1(), b.z1()));
        y.set("protect", prot);
        List<Map<String, Object>> ps = new ArrayList<>();
        for (PieceRec p : pieces) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("index", p.index());
            m.put("piece", p.piece());
            m.put("turns", p.turns());
            m.put("origin", List.of(p.x0(), p.z0()));
            m.put("floor", p.floor());
            m.put("offset", List.of(p.dx(), p.dz()));
            ps.add(m);
        }
        y.set("pieces", ps);
        List<Map<String, Object>> pa = new ArrayList<>();
        for (PathRec p : paths) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("index", p.index());
            m.put("width", p.width());
            m.put("style", p.style());
            List<List<Integer>> pts = new ArrayList<>();
            for (int[] q : p.points()) pts.add(List.of(q[0], q[1]));
            m.put("points", pts);
            m.put("attach", List.of(p.attachA(), p.attachB()));
            StringBuilder sb = new StringBuilder();
            for (int[] c : p.cells()) {
                if (sb.length() > 0) sb.append(';');
                sb.append(c[0]).append(',').append(c[1]).append(',').append(c[2]);
            }
            m.put("cells", sb.toString());
            pa.add(m);
        }
        y.set("paths", pa);
        if (terrain != null) {
            y.set("terrain.origin", List.of(terrain.x0(), terrain.z0()));
            y.set("terrain.size", terrain.n());
            y.set("terrain.base", terrain.base());
            y.set("terrain.heights", Base64.getEncoder().encodeToString(terrain.heights()));
            y.set("terrain.changed", Base64.getEncoder().encodeToString(terrain.changed().toByteArray()));
        }
        y.set("build_id", buildId);
        y.set("built_at", builtAt);
        y.set("plugin_version", pluginVersion);
        return y.saveToString();
    }

    public void save(File file) throws IOException {
        File parent = file.getParentFile();
        if (parent != null) parent.mkdirs();
        File tmp = new File(file.getPath() + ".tmp");
        Files.writeString(tmp.toPath(), toYaml(), StandardCharsets.UTF_8);
        Files.move(tmp.toPath(), file.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
    }

    // ── 읽기 ─────────────────────────────────────────────────────────────

    public static VillageMeta load(File file) throws IOException, InvalidConfigurationException {
        return fromYaml(Files.readString(file.toPath(), StandardCharsets.UTF_8));
    }

    public static VillageMeta fromYaml(String text) throws InvalidConfigurationException {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        VillageMeta m = new VillageMeta();
        m.format = y.getInt("format", 1);
        m.name = y.getString("name", "마을");
        List<Integer> c = y.getIntegerList("center");
        if (c.size() == 3) m.center = new int[] {c.get(0), c.get(1), c.get(2)};
        m.rotation = y.getString("rotation", "NONE");
        m.radius = y.getInt("radius", 32);
        m.blend = y.getInt("blend", 16);
        m.spawn = pos(y.getList("spawn"));
        m.entrance = pos(y.getList("entrance"));
        ConfigurationSection ns = y.getConfigurationSection("npcs");
        if (ns != null) for (String k : ns.getKeys(false)) {
            Pos p = pos(ns.getList(k));
            if (p != null) m.npcs.put(k, p);
        }
        ConfigurationSection is = y.getConfigurationSection("interact");
        if (is != null) for (String k : is.getKeys(false)) m.interact.put(k, is.getString(k));
        List<?> amb = y.getList("ambient");
        if (amb != null) for (Object o : amb) {
            if (o instanceof List<?> l && l.size() >= 4) {
                m.ambient.add(new Ambient(num(l.get(0)), num(l.get(1)), num(l.get(2)), String.valueOf(l.get(3))));
            }
        }
        List<?> prot = y.getList("protect");
        if (prot != null) for (Object o : prot) {
            if (o instanceof List<?> l && l.size() >= 6) {
                m.protect.add(new Box(num(l.get(0)), num(l.get(1)), num(l.get(2)), num(l.get(3)), num(l.get(4)), num(l.get(5))));
            }
        }
        for (Map<?, ?> p : y.getMapList("pieces")) {
            List<?> o = (List<?>) p.get("origin"), off = p.get("offset") instanceof List<?> l ? l : List.of(0, 0);
            m.pieces.add(new PieceRec(num(p.get("index")), String.valueOf(p.get("piece")), num(p.get("turns")), num(o.get(0)), num(o.get(1)),
                    num(p.get("floor")), num(off.get(0)), num(off.get(1))));
        }
        for (Map<?, ?> p : y.getMapList("paths")) {
            List<int[]> pts = new ArrayList<>();
            if (p.get("points") instanceof List<?> l) for (Object q : l) {
                List<?> qq = (List<?>) q;
                pts.add(new int[] {num(qq.get(0)), num(qq.get(1))});
            }
            List<?> at = p.get("attach") instanceof List<?> l ? l : List.of(-1, -1);
            List<int[]> cells = new ArrayList<>();
            String cs = p.get("cells") == null ? "" : String.valueOf(p.get("cells"));
            if (!cs.isBlank()) for (String part : cs.split(";")) {
                String[] a = part.split(",");
                if (a.length == 3) cells.add(new int[] {Integer.parseInt(a[0].trim()), Integer.parseInt(a[1].trim()), Integer.parseInt(a[2].trim())});
            }
            m.paths.add(new PathRec(num(p.get("index")), num(p.get("width")), String.valueOf(p.get("style")), pts, num(at.get(0)), num(at.get(1)), cells));
        }
        if (y.isConfigurationSection("terrain")) {
            List<Integer> o = y.getIntegerList("terrain.origin");
            int n = y.getInt("terrain.size");
            byte[] hs = Base64.getDecoder().decode(y.getString("terrain.heights", ""));
            BitSet ch = BitSet.valueOf(Base64.getDecoder().decode(y.getString("terrain.changed", "")));
            if (o.size() == 2 && hs.length == n * n) m.terrain = new TerrainRec(o.get(0), o.get(1), n, y.getInt("terrain.base"), hs, ch);
        }
        m.buildId = y.getString("build_id", "");
        m.builtAt = y.getString("built_at", "");
        m.pluginVersion = y.getString("plugin_version", "");
        return m;
    }

    /** 목표 높이장 → TerrainRec (높이 범위가 255 를 넘으면 잘림). */
    public static TerrainRec terrainOf(Plan plan) {
        int n = plan.gn;
        int[] t = plan.field.target();
        int min = Integer.MAX_VALUE;
        for (int v : t) min = Math.min(min, v);
        byte[] hs = new byte[n * n];
        BitSet ch = new BitSet(n * n);
        for (int i = 0; i < n * n; i++) {
            hs[i] = (byte) Math.max(0, Math.min(255, t[i] - min));
            if (plan.field.changed()[i]) ch.set(i);
        }
        return new TerrainRec(plan.gx0, plan.gz0, n, min, hs, ch);
    }

    private static List<Integer> ints(int[] a) {
        List<Integer> out = new ArrayList<>();
        for (int v : a) out.add(v);
        return out;
    }

    private static List<Object> pos(Pos p) {
        return List.of(p.x(), p.y(), p.z(), (double) p.yaw());
    }

    private static Pos pos(List<?> l) {
        if (l == null || l.size() < 3) return null;
        return new Pos(dbl(l.get(0)), dbl(l.get(1)), dbl(l.get(2)), l.size() > 3 ? (float) dbl(l.get(3)) : 0f);
    }

    private static int num(Object o) {
        if (o instanceof Number n) return n.intValue();
        try {
            return Integer.parseInt(String.valueOf(o).trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private static double dbl(Object o) {
        if (o instanceof Number n) return n.doubleValue();
        try {
            return Double.parseDouble(String.valueOf(o).trim());
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
