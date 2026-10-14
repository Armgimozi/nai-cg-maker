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
import java.util.Set;

/**
 * 조각 청사진 (VILLAGE.md §2) — JSON 하나 = 건물/장식 하나. 순수 데이터 (서버 없이 파싱·검사 가능).
 * 칸은 유니코드 코드포인트로 저장한다: {@link #KEEP}(공백) = 건드리지 않음, {@link #AIR}('.') = 공기여야 함, 그 밖 = 팔레트.
 */
public final class Blueprint {

    public static final int KEEP = ' ';
    public static final int AIR = '.';

    /** 장식 조각 id (slack 3, 정문 검사 생략) — JSON "deco": true 로도 지정 (VILLAGE.md §0, §5 9번). */
    private static final List<String> DECO_PREFIXES = List.of("lamp_post", "bench", "well", "flower_bed", "tree_", "signpost",
            "cart", "fence", "planter", "statue", "banner_pole", "crate", "barrel_stack", "hay");

    public record Weighted(String block, int weight) {}

    /** 마커 (§2.4). pos 는 정방향 조각 좌표 [x, y, z] — interact 는 여러 개, 나머지는 하나. */
    public record Marker(String type, String id, String action, String fx, String face, List<int[]> pos, List<String> lines,
                         List<String> back, boolean glow, List<String[]> patterns) {
        public int[] first() { return pos.isEmpty() ? null : pos.get(0); }
    }

    public final String id;
    public final String name;
    public final int w, h, d;
    public final int floorY;
    public final String foundation;
    public final List<Weighted> foundationMix;
    public final int anchorX, anchorZ;
    public final Map<Integer, String> palette;
    public final List<Marker> markers;
    /** JSON 에 적힌 slack (없으면 null → 기본값). */
    public final Integer slack;
    public final boolean deco;
    /** 정문 앞 걸어 들어가기 검사 대상인가 (장식이 아니고 "door": false 가 아니면). */
    public final boolean door;
    private final int[] cells;
    private final boolean[] occupied;

    private Blueprint(String id, String name, int w, int h, int d, int floorY, String foundation, List<Weighted> mix,
                      int ax, int az, Map<Integer, String> palette, int[] cells, List<Marker> markers, Integer slack,
                      boolean deco, boolean door) {
        this.id = id;
        this.name = name;
        this.w = w;
        this.h = h;
        this.d = d;
        this.floorY = floorY;
        this.foundation = foundation;
        this.foundationMix = List.copyOf(mix);
        this.anchorX = ax;
        this.anchorZ = az;
        this.palette = Collections.unmodifiableMap(palette);
        this.cells = cells;
        this.markers = List.copyOf(markers);
        this.slack = slack;
        this.deco = deco;
        this.door = door;
        this.occupied = new boolean[w * d];
        for (int z = 0; z < d; z++) {
            for (int x = 0; x < w; x++) {
                for (int y = 0; y < h; y++) {
                    if (cell(x, y, z) != KEEP) {
                        occupied[z * w + x] = true;
                        break;
                    }
                }
            }
        }
    }

    /** 칸 코드포인트 (범위 밖 = KEEP). */
    public int cell(int x, int y, int z) {
        if (x < 0 || y < 0 || z < 0 || x >= w || y >= h || z >= d) return KEEP;
        return cells[(y * d + z) * w + x];
    }

    /** 이 (x, z) 열에 공백이 아닌 칸이 하나라도 있는가 (= 발자국). */
    public boolean occupied(int x, int z) {
        return x >= 0 && z >= 0 && x < w && z < d && occupied[z * w + x];
    }

    public int occupiedCount() {
        int n = 0;
        for (boolean b : occupied) if (b) n++;
        return n;
    }

    /** 팔레트 글자 → 블록 상태 문자열 (KEEP/AIR 은 null). */
    public String state(int cp) { return palette.get(cp); }

    public List<Marker> markers(String type) {
        List<Marker> out = new ArrayList<>();
        for (Marker m : markers) if (m.type().equals(type)) out.add(m);
        return out;
    }

    /** foundation_mix 에서 결정적으로 하나 (같은 칸이면 늘 같은 블록). 없으면 foundation. */
    public String foundationAt(long hash) {
        return pick(foundationMix, hash, foundation == null ? "minecraft:cobblestone" : foundation);
    }

    static String pick(List<Weighted> mix, long hash, String fallback) {
        if (mix == null || mix.isEmpty()) return fallback;
        int total = 0;
        for (Weighted wt : mix) total += Math.max(0, wt.weight());
        if (total <= 0) return fallback;
        long r = Math.floorMod(mix(hash), total);
        for (Weighted wt : mix) {
            r -= Math.max(0, wt.weight());
            if (r < 0) return wt.block();
        }
        return mix.get(mix.size() - 1).block();
    }

    /** 칸 좌표 해시 (결정적 무작위 — 다시 지어도 같은 무늬). */
    public static long hash(int x, int y, int z) {
        long h = x * 73856093L ^ y * 19349663L ^ z * 83492791L;
        return mix(h);
    }

    static long mix(long z) {
        z = (z ^ (z >>> 33)) * 0xff51afd7ed558ccdL;
        z = (z ^ (z >>> 33)) * 0xc4ceb9fe1a85ec53L;
        return z ^ (z >>> 33);
    }

    public static boolean isDecoId(String id) {
        for (String p : DECO_PREFIXES) if (id.startsWith(p)) return true;
        return false;
    }

    // ── 파싱 ─────────────────────────────────────────────────────────────

    /** JSON 문자열 → 청사진. 형식 오류는 IllegalArgumentException (메시지에 모든 문제). */
    public static Blueprint parse(String json) {
        JsonObject o;
        try {
            o = JsonParser.parseString(json).getAsJsonObject();
        } catch (RuntimeException e) {
            throw new IllegalArgumentException("JSON 형식 오류: " + e.getMessage());
        }
        List<String> problems = new ArrayList<>();
        String id = str(o, "id", null);
        if (id == null || id.isBlank()) throw new IllegalArgumentException("id 없음");
        int format = o.has("format") ? o.get("format").getAsInt() : 1;
        if (format != 1) problems.add("format " + format + " (1 만 지원)");
        JsonArray size = arr(o, "size");
        if (size == null || size.size() != 3) throw new IllegalArgumentException(id + ": size [W,H,D] 없음");
        int w = size.get(0).getAsInt(), h = size.get(1).getAsInt(), d = size.get(2).getAsInt();
        if (w <= 0 || h <= 0 || d <= 0 || w > 128 || h > 128 || d > 128) throw new IllegalArgumentException(id + ": size 범위 오류");
        int floorY = o.has("floor_y") ? o.get("floor_y").getAsInt() : 0;
        if (floorY < 0 || floorY >= h) problems.add("floor_y " + floorY + " 가 0.." + (h - 1) + " 밖");

        Map<Integer, String> palette = new LinkedHashMap<>();
        JsonObject pal = o.has("palette") && o.get("palette").isJsonObject() ? o.getAsJsonObject("palette") : new JsonObject();
        for (Map.Entry<String, JsonElement> e : pal.entrySet()) {
            String k = e.getKey();
            if (k.codePointCount(0, k.length()) != 1) {
                problems.add("팔레트 글자 '" + k + "' 는 한 글자여야 함");
                continue;
            }
            int cp = k.codePointAt(0);
            if (cp == KEEP || cp == AIR) {
                problems.add("팔레트에 ' ' / '.' 는 쓸 수 없음");
                continue;
            }
            String v = e.getValue().getAsString().trim();
            if (!v.matches("[a-z0-9_.\\-]+:[a-z0-9_./\\-]+(\\[[a-z0-9_]+=[a-z0-9_]+(,[a-z0-9_]+=[a-z0-9_]+)*\\])?")) {
                problems.add("팔레트 '" + k + "' 블록 문자열 형식 오류: " + v);
            }
            palette.put(cp, v);
        }

        int[] cells = new int[w * h * d];
        JsonArray layers = arr(o, "layers");
        if (layers == null || layers.size() != h) {
            problems.add("layers 수 " + (layers == null ? 0 : layers.size()) + " ≠ H " + h);
        }
        Set<Integer> unknown = new java.util.TreeSet<>();
        for (int y = 0; y < h; y++) {
            JsonArray rows = layers != null && y < layers.size() && layers.get(y).isJsonArray() ? layers.get(y).getAsJsonArray() : null;
            if (rows == null || rows.size() != d) {
                problems.add("layer " + y + " 의 줄 수 " + (rows == null ? 0 : rows.size()) + " ≠ D " + d);
            }
            for (int z = 0; z < d; z++) {
                String row = rows != null && z < rows.size() ? rows.get(z).getAsString() : "";
                int[] cps = row.codePoints().toArray();
                if (cps.length != w) problems.add("layer " + y + " z=" + z + " 길이 " + cps.length + " ≠ W " + w);
                for (int x = 0; x < w; x++) {
                    int cp = x < cps.length ? cps[x] : KEEP;
                    if (cp != KEEP && cp != AIR && !palette.containsKey(cp)) {
                        unknown.add(cp);
                        cp = KEEP;
                    }
                    cells[(y * d + z) * w + x] = cp;
                }
            }
        }
        for (int cp : unknown) problems.add("팔레트에 없는 글자 '" + new String(Character.toChars(cp)) + "'");

        int ax = w / 2, az = 0;
        JsonArray anchor = arr(o, "anchor");
        if (anchor != null && anchor.size() == 2) {
            ax = anchor.get(0).getAsInt();
            az = anchor.get(1).getAsInt();
        }
        if (ax < 0 || az < 0 || ax >= w || az >= d) problems.add("anchor [" + ax + "," + az + "] 가 크기 밖");

        List<Weighted> mix = weighted(arr(o, "foundation_mix"));
        String foundation = str(o, "foundation", mix.isEmpty() ? "minecraft:cobblestone" : mix.get(0).block());

        List<Marker> markers = new ArrayList<>();
        JsonArray ms = arr(o, "markers");
        if (ms != null) {
            for (JsonElement me : ms) {
                if (!me.isJsonObject()) continue;
                JsonObject m = me.getAsJsonObject();
                String type = str(m, "type", "");
                List<int[]> pos = new ArrayList<>();
                JsonArray pa = arr(m, "pos");
                if (pa != null && pa.size() > 0) {
                    if (pa.get(0).isJsonArray()) {
                        for (JsonElement pe : pa) pos.add(ints(pe.getAsJsonArray()));
                    } else {
                        pos.add(ints(pa));
                    }
                }
                for (int[] p : pos) {
                    if (p.length != 3 || p[0] < 0 || p[1] < 0 || p[2] < 0 || p[0] >= w || p[1] >= h + 2 || p[2] >= d) {
                        problems.add("마커 " + type + " 좌표가 크기 밖: " + java.util.Arrays.toString(p));
                    }
                }
                List<String[]> patterns = new ArrayList<>();
                JsonArray pt = arr(m, "patterns");
                if (pt != null) {
                    for (JsonElement pe : pt) {
                        JsonArray a = pe.getAsJsonArray();
                        if (a.size() == 2) patterns.add(new String[] {a.get(0).getAsString(), a.get(1).getAsString()});
                    }
                }
                markers.add(new Marker(type, str(m, "id", null), str(m, "action", null), str(m, "fx", null), str(m, "face", "front"),
                        pos, strings(arr(m, "lines")), strings(arr(m, "back")), m.has("glow") && m.get("glow").getAsBoolean(), patterns));
            }
        }
        Integer slack = o.has("slack") ? o.get("slack").getAsInt() : null;
        boolean deco = o.has("deco") ? o.get("deco").getAsBoolean() : isDecoId(id);
        boolean door = !deco && (!o.has("door") || o.get("door").getAsBoolean());
        if (!problems.isEmpty()) throw new IllegalArgumentException(id + ": " + String.join(" · ", problems));
        return new Blueprint(id, str(o, "name", id), w, h, d, floorY, foundation, mix, ax, az, palette, cells, markers, slack, deco, door);
    }

    static List<Weighted> weighted(JsonArray a) {
        List<Weighted> out = new ArrayList<>();
        if (a == null) return out;
        for (JsonElement e : a) {
            if (e.isJsonArray() && e.getAsJsonArray().size() == 2) {
                out.add(new Weighted(e.getAsJsonArray().get(0).getAsString(), e.getAsJsonArray().get(1).getAsInt()));
            } else if (e.isJsonPrimitive()) {
                out.add(new Weighted(e.getAsString(), 1));
            }
        }
        return out;
    }

    static String str(JsonObject o, String k, String def) {
        return o.has(k) && o.get(k).isJsonPrimitive() ? o.get(k).getAsString() : def;
    }

    static JsonArray arr(JsonObject o, String k) {
        return o.has(k) && o.get(k).isJsonArray() ? o.getAsJsonArray(k) : null;
    }

    static int[] ints(JsonArray a) {
        int[] out = new int[a.size()];
        for (int i = 0; i < out.length; i++) out[i] = a.get(i).getAsInt();
        return out;
    }

    static List<String> strings(JsonArray a) {
        List<String> out = new ArrayList<>();
        if (a != null) for (JsonElement e : a) out.add(e.getAsString());
        return out;
    }
}
