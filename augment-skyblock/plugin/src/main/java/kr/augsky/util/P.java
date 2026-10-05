package kr.augsky.util;

import org.bukkit.configuration.ConfigurationSection;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** YAML 에서 읽은 Map 을 타입별로 꺼내 쓰는 얇은 래퍼. */
public final class P {
    public final Map<String, Object> m;

    public P(Map<?, ?> raw) {
        Map<String, Object> mm = new LinkedHashMap<>();
        if (raw != null) for (Map.Entry<?, ?> e : raw.entrySet()) mm.put(String.valueOf(e.getKey()), e.getValue());
        this.m = mm;
    }

    public static P of(ConfigurationSection sec) {
        return new P(sec == null ? Collections.emptyMap() : sec.getValues(false));
    }

    public boolean has(String k) { return m.containsKey(k); }

    public double d(String k, double def) {
        Object o = m.get(k);
        if (o instanceof Number n) return n.doubleValue();
        if (o instanceof String s) try { return Double.parseDouble(s); } catch (NumberFormatException ignored) {}
        return def;
    }

    public int i(String k, int def) { return (int) Math.round(d(k, def)); }

    public String s(String k, String def) {
        Object o = m.get(k);
        return o == null ? def : String.valueOf(o);
    }

    public boolean b(String k, boolean def) {
        Object o = m.get(k);
        if (o instanceof Boolean bo) return bo;
        if (o instanceof String s) return Boolean.parseBoolean(s);
        return def;
    }

    @SuppressWarnings("unchecked")
    public List<Map<?, ?>> maps(String k) {
        Object o = m.get(k);
        List<Map<?, ?>> out = new ArrayList<>();
        if (o instanceof List<?> l) {
            for (Object x : l) {
                if (x instanceof Map<?, ?> mx) out.add(mx);
                else if (x instanceof ConfigurationSection cs) out.add(cs.getValues(false));
            }
        } else if (o instanceof Map<?, ?> mx) {
            out.add(mx);
        } else if (o instanceof ConfigurationSection cs) {
            out.add(cs.getValues(false));
        }
        return out;
    }

    public P sub(String k) {
        Object o = m.get(k);
        if (o instanceof Map<?, ?> mx) return new P(mx);
        if (o instanceof ConfigurationSection cs) return P.of(cs);
        return null;
    }

    public List<String> strings(String k) {
        Object o = m.get(k);
        List<String> out = new ArrayList<>();
        if (o instanceof List<?> l) for (Object x : l) out.add(String.valueOf(x));
        else if (o != null) out.add(String.valueOf(o));
        return out;
    }
}
