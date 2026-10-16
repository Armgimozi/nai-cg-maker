package kr.labyrinth.content;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/**
 * 무기 고유 효과 하나 (items.yml {@code unique: {id, name, 수치…}}, unique_spec §7). 무기마다 하나, 수치는 굴리지 않는다(고정)
 * — 강화로도 바뀌지 않는다. 빠진 수치는 카탈로그 기준값({@link UniqueCatalog.Param#ref()}).
 * <pre>
 *   spore_kris:
 *     unique: {id: rend, name: "아물지 않는 상처", pct: 0.15, duration: 4, max_stacks: 5}
 * </pre>
 *
 * @param id     닫힌 목록 26개 중 하나 ({@link UniqueCatalog#EFFECTS}). 예전 이름 {@code shield_bash} 는 {@code bash_stun} 으로 읽는다
 * @param name   툴팁 이름 (무기마다 따로)
 * @param params 나머지 수치 (id·name 뺀 것)
 */
public record UniqueDef(String id, String name, Params params) {

    public UniqueDef {
        id = UniqueCatalog.canonical(id);
        if (params == null) params = Params.EMPTY;
        if (name == null || name.isBlank()) {
            UniqueCatalog.Effect e = UniqueCatalog.get(id);
            name = e == null ? id : e.name();
        }
    }

    /** 아이템 항목(raw)의 {@code unique} 블록 → 정의. 블록이 없거나 맵이 아니거나 id 가 없으면 null. */
    public static UniqueDef parse(Params item) {
        if (item == null || !(item.get("unique") instanceof Map<?, ?>)) return null;
        Params u = item.sub("unique");
        String id = u.str("id");
        if (id == null || id.isBlank()) return null;
        Map<String, Object> rest = new LinkedHashMap<>();
        u.asMap().forEach((k, v) -> {
            if (!k.equals("id") && !k.equals("name")) rest.put(k, v);
        });
        return new UniqueDef(id.trim().toLowerCase(Locale.ROOT), u.str("name"), Params.of(rest));
    }

    /** 카탈로그 정의 (닫힌 목록에 없는 id 면 null — 검사기가 오류로 잡는다). */
    public UniqueCatalog.Effect effect() { return UniqueCatalog.get(id); }

    /** 수치 (없으면 카탈로그 기준값, 카탈로그에도 없으면 0). */
    public double num(String key) {
        UniqueCatalog.Effect e = effect();
        UniqueCatalog.Param p = e == null ? null : e.param(key);
        return params.dbl(key, p == null ? 0 : p.ref());
    }

    /** 정수 수치 (중첩·대상 수·N번째). */
    public int count(String key) { return (int) Math.round(num(key)); }

    /** 글 수치 (imbue element 등). */
    public String text(String key, String def) {
        String v = params.str(key);
        return v == null || v.isBlank() ? def : v.trim().toLowerCase(Locale.ROOT);
    }

    public boolean is(String effectId) { return id.equals(effectId); }
}
