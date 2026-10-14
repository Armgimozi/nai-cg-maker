package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 읽기 전용 YAML 노드(맵) 래퍼. 콘텐츠의 자유 파라미터(params, patterns, gimmick_params, style …)와
 * 파서 내부 노드로 함께 쓴다. 모든 키는 문자열로 정규화되어 있고, 값은 String/Number/Boolean/List/Map 중 하나다.
 * <p>
 * 파티 인원 규칙(GDD §8.4)을 적용하는 {@link #scaled(String, int)} 같은 헬퍼도 있다.
 */
public final class Params {

    public static final Params EMPTY = new Params(Map.of());

    private final Map<String, Object> map;

    private Params(Map<String, Object> map) {
        this.map = map;
    }

    /** 원시 맵(키는 아무 타입)을 깊은 복사·정규화해 불변 Params 로 만든다. null 이면 EMPTY. */
    public static Params of(Object raw) {
        if (raw instanceof Params p) return p;
        if (!(raw instanceof Map<?, ?> m) || m.isEmpty()) return EMPTY;
        return new Params(normalizeMap(m));
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> normalizeMap(Map<?, ?> m) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (Map.Entry<?, ?> e : m.entrySet()) {
            out.put(String.valueOf(e.getKey()), normalize(e.getValue()));
        }
        return Collections.unmodifiableMap(out);
    }

    private static Object normalize(Object v) {
        if (v instanceof Params p) return p.map;
        if (v instanceof Map<?, ?> m) return normalizeMap(m);
        if (v instanceof List<?> l) {
            List<Object> out = new ArrayList<>(l.size());
            for (Object o : l) out.add(normalize(o));
            return Collections.unmodifiableList(out);
        }
        return v;
    }

    public boolean has(String key) { return map.containsKey(key) && map.get(key) != null; }
    public boolean isEmpty() { return map.isEmpty(); }
    public Set<String> keys() { return map.keySet(); }
    public Map<String, Object> asMap() { return map; }
    public Object get(String key) { return map.get(key); }

    public String str(String key) { return str(key, null); }

    public String str(String key, String def) {
        Object v = map.get(key);
        return v == null ? def : String.valueOf(v);
    }

    public double dbl(String key, double def) {
        Object v = map.get(key);
        if (v instanceof Number n) return n.doubleValue();
        if (v instanceof String s) {
            try { return Double.parseDouble(s.trim()); } catch (NumberFormatException ignored) { return def; }
        }
        return def;
    }

    public int integer(String key, int def) {
        Object v = map.get(key);
        if (v instanceof Number n) return (int) Math.round(n.doubleValue());
        if (v instanceof String s) {
            try { return Integer.parseInt(s.trim()); } catch (NumberFormatException ignored) { return def; }
        }
        return def;
    }

    public boolean bool(String key, boolean def) {
        Object v = map.get(key);
        if (v instanceof Boolean b) return b;
        if (v instanceof String s) return Boolean.parseBoolean(s.trim());
        return def;
    }

    /** 하위 맵. 없거나 맵이 아니면 EMPTY. */
    public Params sub(String key) {
        Object v = map.get(key);
        return v instanceof Map<?, ?> m ? new Params(castMap(m)) : EMPTY;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Map<?, ?> m) {
        return (Map<String, Object>) m;
    }

    public List<Object> list(String key) {
        Object v = map.get(key);
        if (v instanceof List<?> l) return Collections.unmodifiableList(new ArrayList<>(l));
        return List.of();
    }

    public List<String> strings(String key) {
        Object v = map.get(key);
        if (v instanceof List<?> l) {
            List<String> out = new ArrayList<>(l.size());
            for (Object o : l) if (o != null) out.add(String.valueOf(o));
            return List.copyOf(out);
        }
        if (v instanceof String s && !s.isBlank()) return List.of(s);
        return List.of();
    }

    public List<Double> doubles(String key) {
        List<Double> out = new ArrayList<>();
        for (Object o : list(key)) if (o instanceof Number n) out.add(n.doubleValue());
        return List.copyOf(out);
    }

    /** 리스트 안의 맵들을 Params 로. */
    public List<Params> maps(String key) {
        List<Params> out = new ArrayList<>();
        for (Object o : list(key)) if (o instanceof Map<?, ?> m) out.add(new Params(castMap(m)));
        return List.copyOf(out);
    }

    /** 이 맵의 각 (키 → 하위 맵) 쌍. 하위 값이 맵이 아니면 건너뛴다. */
    public Map<String, Params> children() {
        Map<String, Params> out = new LinkedHashMap<>();
        for (Map.Entry<String, Object> e : map.entrySet()) {
            if (e.getValue() instanceof Map<?, ?> m) out.put(e.getKey(), new Params(castMap(m)));
        }
        return Collections.unmodifiableMap(out);
    }

    /** [min, max] 리스트 또는 단일 숫자를 범위로. 없으면 def. */
    public IntRange intRange(String key, IntRange def) {
        Object v = map.get(key);
        if (v instanceof Number n) return new IntRange(n.intValue(), n.intValue());
        if (v instanceof List<?> l && !l.isEmpty() && l.get(0) instanceof Number a) {
            int min = a.intValue();
            int max = l.size() > 1 && l.get(1) instanceof Number b ? b.intValue() : min;
            return new IntRange(Math.min(min, max), Math.max(min, max));
        }
        return def;
    }

    public Range range(String key, Range def) {
        Object v = map.get(key);
        if (v instanceof Number n) return new Range(n.doubleValue(), n.doubleValue());
        if (v instanceof List<?> l && !l.isEmpty() && l.get(0) instanceof Number a) {
            double min = a.doubleValue();
            double max = l.size() > 1 && l.get(1) instanceof Number b ? b.doubleValue() : min;
            return new Range(Math.min(min, max), Math.max(min, max));
        }
        return def;
    }

    // ── 파티 인원 규칙 (GDD §8.4) ────────────────────────────────────────────

    /**
     * {@code <key>_base + floor((n-1) × <key>_per_member)} 또는 {@code <key> + floor((n-1)/<key>_per_members)}.
     * {@code solo_<key>} 가 있고 n = 1 이면 그 값. 아무것도 없으면 {@code <key>} 값 또는 def.
     */
    public double scaled(String key, int partySize, double def) {
        int n = Math.max(1, partySize);
        if (n == 1 && has("solo_" + key)) return dbl("solo_" + key, def);
        double base = has(key + "_base") ? dbl(key + "_base", def) : dbl(key, def);
        if (has(key + "_per_member")) {
            return base + Math.floor((n - 1) * dbl(key + "_per_member", 0));
        }
        if (has(key + "_per_members")) {
            double k = dbl(key + "_per_members", 0);
            return k > 0 ? base + Math.floor((n - 1) / k) : base;
        }
        return base;
    }

    public int scaledInt(String key, int partySize, int def) {
        return (int) Math.round(scaled(key, partySize, def));
    }

    /** {@code p2_<key>} / {@code p3_<key>} 가 있으면 해당 페이즈 이상에서 그 값. */
    public double phased(String key, int phase, double def) {
        for (int p = phase; p >= 2; p--) {
            if (has("p" + p + "_" + key)) return dbl("p" + p + "_" + key, def);
        }
        return dbl(key, def);
    }

    @Override
    public String toString() { return map.toString(); }

    @Override
    public boolean equals(Object o) { return o instanceof Params p && p.map.equals(map); }

    @Override
    public int hashCode() { return map.hashCode(); }
}
