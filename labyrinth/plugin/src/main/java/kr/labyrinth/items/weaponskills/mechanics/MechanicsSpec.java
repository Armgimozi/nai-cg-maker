package kr.labyrinth.items.weaponskills.mechanics;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import kr.labyrinth.content.Params;

/**
 * 조합형 무기 스킬(<code>id: mechanics</code>)의 <b>순수</b> 파서·검사기 (Bukkit 무관 — 단위 테스트 대상, GDD §17.5).
 * <p>
 * items.yml 의 무기 스킬 항목이 <code>mechanics:</code> 목록을 가지면, 각 원소는 "부품(part)" 하나이고
 * 부품은 도형·이동·연출을 정한 뒤 맞은 대상에게 <code>effects</code>(효과 목록)를 적용한다.
 * 효과는 짧게 쓸 수 있다: <code>{damage: 1.2}</code> = <code>{type: damage, amount: 1.2}</code>,
 * <code>{absorption: {amount: 0.2, seconds: 6}}</code> = 하위 맵을 그대로 펼침.
 * 부품 안의 하위 부품 목록: leap.land · vortex/zone.end · beam/dash.on_end · projectile/rain.on_impact ·
 * repeat/delay.mechanics, projectile.explode{radius, effects} 는 착탄 nova 로 바뀐다.
 */
public final class MechanicsSpec {

    private MechanicsSpec() {}

    /** 부품 종류 (GDD §17.5 표). */
    public static final Set<String> PART_TYPES = Set.of("cone", "nova", "projectile", "beam", "dash", "leap", "blink",
            "rain", "strike", "chain", "zone", "orbit", "vortex", "self", "target", "party", "summon", "repeat", "delay",
            "sound", "particle", "velocity", "say");

    /** 효과 종류. 앞 22개 = 참고 체계 그대로, 뒤 = 미궁 확장(상태이상·버프·도발·마나). */
    public static final Set<String> EFFECT_TYPES = Set.of("damage", "percent", "ignite", "slow", "poison", "wither",
            "knockback", "pull", "launch", "freeze", "stun", "heal", "heal_caster", "lifesteal", "absorption", "cleanse",
            "lightning", "explosion", "particle", "sound", "execute", "glow",
            "root", "bleed", "effect", "buff", "potion", "taunt", "mana");

    /** 하위 부품 목록 키. */
    public static final Set<String> CHILD_KEYS = Set.of("land", "end", "on_end", "on_impact", "mechanics");

    /** 위치 기준. origin = 지금 문맥 위치(최상위 = 시전자, land/end/on_impact 안 = 그 지점). */
    public static final Set<String> ANCHORS = Set.of("self", "aim", "target", "origin");

    /** StatusEffectService 가 아는 id (effect 효과의 id 검사용, GDD §9.2 + 확장). */
    public static final Set<String> STATUS_IDS = Set.of("poison", "bleed", "burn", "slow", "root", "stun", "weaken",
            "vulnerable", "blind", "silence", "frost", "infection", "venom", "mark", "cooldown_slow", "interrupt");

    /** 버프 키 (GDD §11.7 버프 키). */
    public static final Set<String> BUFF_KEYS = Set.of("damage", "damage_reduction", "attack_speed", "move_speed",
            "crit_chance", "crit_damage", "lifesteal", "evasion", "cooldown_reduction", "skill_damage", "defense",
            "hp_regen", "mana_regen", "heal_power");

    /** potion 효과 이름 → 버프 키 (참고 체계 호환). */
    public static final Map<String, String> POTION_BUFFS = Map.of("speed", "move_speed", "resistance", "damage_reduction",
            "strength", "damage", "haste", "attack_speed", "regeneration", "hp_regen", "luck", "crit_chance");

    private static final Pattern PARTICLE = Pattern.compile("[A-Za-z_]+(:[^:]+){0,3}");
    private static final int MAX_DEPTH = 6;
    private static final int MAX_PARTS = 160;

    /** 효과 하나. p 에는 type 을 뺀 값들 (짧은 표기의 값은 amount). */
    public record Effect(String type, Params p) {
        public double amount(double def) { return p.dbl("amount", def); }
    }

    /** 부품 하나. */
    public record Part(String type, Params p, List<Effect> effects, List<Effect> allyEffects,
                       Map<String, List<Part>> children) {
        public List<Part> child(String key) { return children.getOrDefault(key, List.of()); }
        public double num(String key, double def) { return p.dbl(key, def); }
        public int integer(String key, int def) { return p.integer(key, def); }
        public String str(String key, String def) { return p.str(key, def); }
        public boolean flag(String key, boolean def) {
            Object v = p.get(key);
            if (v instanceof Boolean b) return b;
            if (v instanceof Number n) return n.doubleValue() > 0;
            if (v instanceof String s) return Boolean.parseBoolean(s);
            return def;
        }
    }

    /** 파싱 결과 + 문제 목록(빈 목록 = 정상). */
    public record Result(List<Part> parts, List<String> problems, Set<String> displays, Set<String> particles,
                         int partCount) {
        public boolean ok() { return problems.isEmpty(); }
    }

    /** raw = YAML 의 mechanics 목록(List of Map). */
    public static Result parse(Object raw) {
        List<String> problems = new ArrayList<>();
        Set<String> displays = new LinkedHashSet<>();
        Set<String> particles = new LinkedHashSet<>();
        int[] count = {0};
        List<Part> parts = parseList(raw, "mechanics", 0, problems, displays, particles, count);
        if (parts.isEmpty() && problems.isEmpty()) problems.add("mechanics 가 비어 있음");
        if (count[0] > MAX_PARTS) problems.add("부품이 너무 많음 (" + count[0] + " > " + MAX_PARTS + ")");
        return new Result(parts, List.copyOf(problems), Collections.unmodifiableSet(displays),
                Collections.unmodifiableSet(particles), count[0]);
    }

    private static List<Part> parseList(Object raw, String where, int depth, List<String> problems, Set<String> displays,
                                        Set<String> particles, int[] count) {
        if (raw == null) return List.of();
        if (!(raw instanceof List<?> list)) {
            problems.add(where + ": 목록이어야 함");
            return List.of();
        }
        if (depth > MAX_DEPTH) {
            problems.add(where + ": 하위 부품이 너무 깊음 (최대 " + MAX_DEPTH + ")");
            return List.of();
        }
        List<Part> out = new ArrayList<>();
        for (int i = 0; i < list.size(); i++) {
            Object o = list.get(i);
            String w = where + "[" + i + "]";
            if (!(o instanceof Map<?, ?> m)) {
                problems.add(w + ": 맵이어야 함");
                continue;
            }
            Part part = parsePart(Params.of(m), w, depth, problems, displays, particles, count);
            if (part != null) out.add(part);
        }
        return List.copyOf(out);
    }

    private static Part parsePart(Params p, String where, int depth, List<String> problems, Set<String> displays,
                                  Set<String> particles, int[] count) {
        String type = p.str("type");
        if (type == null) {
            problems.add(where + ": type 없음");
            return null;
        }
        type = type.trim().toLowerCase(java.util.Locale.ROOT);
        if (!PART_TYPES.contains(type)) {
            problems.add(where + ": 알 수 없는 부품 type '" + type + "'");
            return null;
        }
        count[0]++;
        String w = where + "(" + type + ")";
        List<Effect> effects = parseEffects(p.get("effects"), w + ".effects", problems, particles);
        List<Effect> ally = parseEffects(p.get("ally_effects"), w + ".ally_effects", problems, particles);
        Map<String, List<Part>> children = new LinkedHashMap<>();
        for (String k : CHILD_KEYS) {
            if (p.has(k)) children.put(k, parseList(p.get(k), w + "." + k, depth + 1, problems, displays, particles, count));
        }
        // projectile.explode {radius, effects, particle} → 착탄 nova
        if (p.get("explode") instanceof Map<?, ?> ex) {
            Params e = Params.of(ex);
            Map<String, Object> nova = new LinkedHashMap<>(e.asMap());
            nova.put("type", "nova");
            nova.putIfAbsent("at", "origin");
            Part np = parsePart(Params.of(nova), w + ".explode", depth + 1, problems, displays, particles, count);
            if (np != null) children.put("explode", List.of(np));
        }
        checkPart(type, p, w, problems, children, effects, ally);
        String at = p.str("at");
        if (at != null && !ANCHORS.contains(at)) problems.add(w + ": at 은 self|aim|target|origin — '" + at + "'");
        String display = p.str("display");
        if (display != null && !display.isBlank()) displays.add(display);
        for (String k : List.of("particle", "core", "ring", "impact_particle", "trail")) {
            String v = p.str(k);
            if (v == null || v.isBlank()) continue;
            if (!PARTICLE.matcher(v).matches()) problems.add(w + "." + k + ": 입자 표기 오류 '" + v + "' (NAME 또는 NAME:인자)");
            else particles.add(particleName(v));
        }
        return new Part(type, p, effects, ally, Collections.unmodifiableMap(children));
    }

    private static void checkPart(String type, Params p, String w, List<String> problems, Map<String, List<Part>> children,
                                  List<Effect> effects, List<Effect> ally) {
        range(p, "radius", 0, 24, w, problems);
        range(p, "range", 0, 48, w, problems);
        range(p, "length", 0, 48, w, problems);
        range(p, "distance", 0, 24, w, problems);
        range(p, "count", 0, type.equals("particle") ? 200 : 48, w, problems);
        range(p, "duration", 0, 30, w, problems);
        range(p, "angle", 0, 360, w, problems);
        range(p, "times", 0, 40, w, problems);
        range(p, "jumps", 0, 16, w, problems);
        range(p, "interval", 0, 200, w, problems);
        range(p, "ticks", 0, 200, w, problems);
        range(p, "speed", 0, 60, w, problems);
        switch (type) {
            case "repeat" -> {
                if (children.getOrDefault("mechanics", List.of()).isEmpty()) problems.add(w + ": repeat 에 mechanics 가 없음");
                if (p.integer("times", 0) < 1) problems.add(w + ": repeat.times ≥ 1 이어야 함");
            }
            case "delay" -> {
                if (!p.has("ticks") && !p.has("seconds")) problems.add(w + ": delay 에 ticks 또는 seconds 가 없음");
            }
            case "sound" -> {
                if (p.str("sound") == null) problems.add(w + ": sound 키 없음");
            }
            case "particle" -> {
                if (p.str("particle") == null) problems.add(w + ": particle 키 없음");
            }
            case "say" -> {
                if (p.str("text") == null) problems.add(w + ": text 없음");
            }
            case "strike" -> {
                String v = p.str("visual");
                if (v != null && !Set.of("lightning", "pillar", "none").contains(v)) {
                    problems.add(w + ": visual 은 lightning|pillar|none — '" + v + "'");
                }
            }
            case "summon" -> {
                if (p.integer("count", 1) > 6) problems.add(w + ": summon.count 는 6 이하");
            }
            case "zone", "party" -> {
                if (effects.isEmpty() && ally.isEmpty() && children.isEmpty()) problems.add(w + ": 효과가 하나도 없음");
            }
            default -> {
                boolean needsEffects = Set.of("cone", "nova", "projectile", "beam", "rain", "strike", "chain", "orbit")
                        .contains(type);
                if (needsEffects && effects.isEmpty() && ally.isEmpty() && children.isEmpty()) {
                    problems.add(w + ": effects 가 없음");
                }
            }
        }
    }

    private static void range(Params p, String key, double min, double max, String w, List<String> problems) {
        if (!p.has(key)) return;
        Object v = p.get(key);
        if (!(v instanceof Number n)) {
            if (key.equals("count") || key.equals("range")) {
                if (v instanceof Boolean) return;
            }
            problems.add(w + "." + key + ": 숫자여야 함");
            return;
        }
        double d = n.doubleValue();
        if (d < min || d > max) problems.add(w + "." + key + ": " + min + "~" + max + " 범위 밖 (" + d + ")");
    }

    /** 효과 목록 정규화. */
    public static List<Effect> parseEffects(Object raw, String where, List<String> problems, Set<String> particles) {
        if (raw == null) return List.of();
        if (!(raw instanceof List<?> list)) {
            problems.add(where + ": 목록이어야 함");
            return List.of();
        }
        List<Effect> out = new ArrayList<>();
        for (int i = 0; i < list.size(); i++) {
            Object o = list.get(i);
            String w = where + "[" + i + "]";
            Effect e = normalizeEffect(o, w, problems);
            if (e == null) continue;
            checkEffect(e, w, problems, particles);
            out.add(e);
        }
        return List.copyOf(out);
    }

    /**
     * 효과 하나 정규화: {type: x, ...} 그대로 / {x: 값, 다른키...} → type x, amount 값 / {x: {맵}} → 맵을 펼침.
     * 문자열 "cleanse" 처럼 이름만 쓰면 값 없는 효과.
     */
    public static Effect normalizeEffect(Object o, String where, List<String> problems) {
        if (o instanceof String s) {
            String t = s.trim().toLowerCase(java.util.Locale.ROOT);
            if (!EFFECT_TYPES.contains(t)) {
                problems.add(where + ": 알 수 없는 효과 '" + s + "'");
                return null;
            }
            return new Effect(t, Params.EMPTY);
        }
        if (!(o instanceof Map<?, ?> m)) {
            problems.add(where + ": 효과는 맵이어야 함");
            return null;
        }
        Params p = Params.of(m);
        String type = p.str("type");
        Map<String, Object> rest = new LinkedHashMap<>(p.asMap());
        if (type != null) {
            rest.remove("type");
        } else {
            for (String k : p.keys()) {
                if (EFFECT_TYPES.contains(k)) {
                    type = k;
                    break;
                }
            }
            if (type == null) {
                problems.add(where + ": 효과 종류를 찾을 수 없음 " + p.keys());
                return null;
            }
            Object v = rest.remove(type);
            if (v instanceof Map<?, ?> sub) {
                for (Map.Entry<?, ?> e : sub.entrySet()) rest.putIfAbsent(String.valueOf(e.getKey()), e.getValue());
            } else if (v != null) {
                rest.put("amount", v);
            }
        }
        type = type.trim().toLowerCase(java.util.Locale.ROOT);
        if (!EFFECT_TYPES.contains(type)) {
            problems.add(where + ": 알 수 없는 효과 type '" + type + "'");
            return null;
        }
        return new Effect(type, Params.of(rest));
    }

    private static void checkEffect(Effect e, String w, List<String> problems, Set<String> particles) {
        Params p = e.p();
        switch (e.type()) {
            case "damage" -> {
                double a = p.dbl("amount", -1);
                if (a <= 0 || a > 30) problems.add(w + ": damage.amount 는 0~30 (공격력 배율) — " + p.get("amount"));
                String t = p.str("damage_type");
                if (t != null && !Set.of("melee", "ranged", "magic", "true").contains(t)) {
                    problems.add(w + ": damage_type 은 melee|ranged|magic|true");
                }
            }
            case "percent" -> {
                double a = p.dbl("amount", -1);
                if (a <= 0 || a > 1) problems.add(w + ": percent.amount 는 0~1 (최대 HP 비율)");
            }
            case "effect" -> {
                String id = p.str("id");
                if (id == null || !STATUS_IDS.contains(id)) problems.add(w + ": effect.id 가 상태이상 목록에 없음 '" + id + "'");
            }
            case "buff" -> {
                Params stats = p.sub("stats");
                if (stats.isEmpty()) problems.add(w + ": buff.stats 가 비어 있음");
                for (String k : stats.keys()) if (!BUFF_KEYS.contains(k)) problems.add(w + ": 알 수 없는 버프 키 '" + k + "'");
            }
            case "potion" -> {
                String id = p.str("effect", p.str("amount"));
                if (id == null || !POTION_BUFFS.containsKey(id)) {
                    problems.add(w + ": potion.effect 는 " + POTION_BUFFS.keySet() + " 중 하나");
                }
            }
            case "heal", "heal_caster", "lifesteal", "absorption", "mana" -> {
                double a = p.dbl("amount", 0.1);
                if (a < 0 || a > 2) problems.add(w + ": " + e.type() + ".amount 는 0~2 (비율)");
            }
            case "particle" -> {
                String v = p.str("particle", p.str("amount"));
                if (v == null || !PARTICLE.matcher(v).matches()) problems.add(w + ": particle 표기 오류");
                else particles.add(particleName(v));
            }
            case "sound" -> {
                if (p.str("sound", p.str("amount")) == null) problems.add(w + ": sound 없음");
            }
            default -> {
                Object a = p.get("amount");
                if (a != null && !(a instanceof Number) && !(a instanceof Boolean)) {
                    problems.add(w + ": " + e.type() + " 값은 숫자여야 함");
                }
            }
        }
    }

    /** "DUST:#ff0000:1.2" → "DUST". */
    public static String particleName(String spec) {
        int i = spec.indexOf(':');
        return (i < 0 ? spec : spec.substring(0, i)).trim().toUpperCase(java.util.Locale.ROOT);
    }

    /** 부품 트리 안 모든 부품(깊이 우선). */
    public static List<Part> flatten(List<Part> parts) {
        List<Part> out = new ArrayList<>();
        for (Part p : parts) {
            out.add(p);
            for (List<Part> ch : p.children().values()) out.addAll(flatten(ch));
        }
        return out;
    }
}
