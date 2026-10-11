package kr.souls.enemy;

import kr.souls.combat.Hit;
import org.bukkit.configuration.ConfigurationSection;

import java.util.Collections;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;

/**
 * 적 정의 (content/enemies.yml, DESIGN 6.1, M1 P1b). 파일은 Content.merged 로 열쇠마다 jar 사본 위에 겹쳐 읽은 것을 받는다 (R20). 여기서는
 * 그 위에 한 번 더 열쇠마다 물러선다: 값이 틀리면 (수가 아니거나 범위 밖) 같은 id 의 jar 값, 그것도 없거나 틀리면 아래 기본값. 사용자가 새로 쓴
 * id (jar 에 없는 적) 는 빠진 열쇠를 기본값으로 채운다. 순수하다 (Bukkit 서버 없이 EnemyDefsTest 가 돈다): 몸 이름 (body) 이 몹인지는
 * 세울 때 Foes 가 본다.
 * <pre>
 *   &lt;id&gt;.body         바닐라 몹 종류 (zombie, husk …)        기본 zombie
 *   &lt;id&gt;.hp           가상 체력 (생길 때 × 난이도 enemy-health)  기본 100, 1 이상
 *   &lt;id&gt;.def          방어력 (3.7)                          기본 20, 0 이상
 *   &lt;id&gt;.poise        강인도 (3.8, P4 가 쓴다)              기본 0, 0 이상
 *   &lt;id&gt;.ai           두뇌 (none: 움직이지 않는 허수아비. 나머지는 P2b·P5a)  기본 none
 *   &lt;id&gt;.regen-after  마지막으로 맞고 이만큼 (틱) 지나면 가상 체력이 다 찬다. 0 이면 차지 않는다   기본 0
 *   &lt;id&gt;.respawn      쓰러진 뒤 다시 세우기까지 (틱, 도장처럼 다시 세우는 쪽이 쓴다)   기본 0 (곧바로)
 *   &lt;id&gt;.material     맞는 소리와 입자 (flesh 살, bone 뼈, iron 쇠, straw 짚: FoeBody)   기본 flesh
 *   &lt;id&gt;.absorb.&lt;종류&gt; 피해 종류마다 흡수율 0..1 (slash, strike, thrust, fire, magic, standard)   기본 없음
 *   &lt;id&gt;.weak.&lt;종류&gt;   피해 종류마다 약점 배율 (1 이면 보통, 0..10)   기본 없음
 * </pre>
 */
public final class EnemyDefs {
    /** 맞는 소리·입자의 재질 (FoeBody 의 표) */
    public enum Material {
        FLESH, BONE, IRON, STRAW;

        static Material parse(Object v) {
            if (!(v instanceof String s)) return null;
            try {
                return valueOf(s.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return null;
            }
        }
    }

    /** 적 하나의 정의. 바뀌지 않는다. */
    public record Def(String id, String body, double hp, double def, double poise, String ai, int regenAfter, int respawn, Material material,
                      Map<Hit.Type, Double> absorb, Map<Hit.Type, Double> weak) {
        /** 두뇌가 없다 (ai: none). 몸의 AI 를 끄고 (setAware false) 밀리지 않게 한다 */
        public boolean brainless() {
            return "none".equals(ai);
        }

        public double absorbOf(Hit.Type t) {
            Double v = t == null ? null : absorb.get(t);
            return v == null ? 0 : v;
        }

        public double weakOf(Hit.Type t) {
            Double v = t == null ? null : weak.get(t);
            return v == null ? 1 : v;
        }
    }

    /** 기본값 (jar 에도 없을 때) */
    public static final String BODY = "zombie";
    public static final double HP = 100, DEF = 20, POISE = 0;
    public static final String AI = "none";
    public static final int REGEN_AFTER = 0, RESPAWN = 0;
    public static final Material MATERIAL = Material.FLESH;

    private volatile Map<String, Def> defs = Map.of();

    /** 읽는다 (켤 때, /souls reload). merged: Content.merged("enemies.yml"), jar: jar 사본 (없으면 null). 틀린 값은 warn 으로 알린다. */
    public void load(ConfigurationSection merged, ConfigurationSection jar, Consumer<String> warn) {
        defs = parse(merged, jar, warn);
    }

    public Def get(String id) {
        return id == null ? null : defs.get(id);
    }

    public Set<String> ids() {
        return defs.keySet();
    }

    /** 순수: 겹쳐 읽은 파일과 jar 사본 → id 차례대로의 정의. */
    public static Map<String, Def> parse(ConfigurationSection merged, ConfigurationSection jar, Consumer<String> warn) {
        Consumer<String> w = warn == null ? s -> { } : warn;
        Map<String, Def> out = new LinkedHashMap<>();
        if (merged == null) return Collections.unmodifiableMap(out);
        for (String id : merged.getKeys(false)) {
            ConfigurationSection s = merged.getConfigurationSection(id);
            if (s == null) {
                w.accept("enemies.yml 의 " + id + " 는 절이 아니라 건너뜁니다 (id: {body: …, hp: …} 꼴로 씁니다).");
                continue;
            }
            ConfigurationSection j = jar == null ? null : jar.getConfigurationSection(id);
            Reader r = new Reader(id, s, j, w);
            String body = r.word("body", BODY);
            double hp = r.num("hp", HP, 1, 1e9);
            double def = r.num("def", DEF, 0, 1e6);
            double poise = r.num("poise", POISE, 0, 1e6);
            String ai = r.word("ai", AI);
            int regen = (int) r.num("regen-after", REGEN_AFTER, 0, 1_000_000);
            int respawn = (int) r.num("respawn", RESPAWN, 0, 1_000_000);
            Material mat = r.material();
            Map<Hit.Type, Double> absorb = r.table("absorb", 0, 1);
            Map<Hit.Type, Double> weak = r.table("weak", 0, 10);
            out.put(id, new Def(id, body, hp, def, poise, ai, regen, respawn, mat, absorb, weak));
        }
        return Collections.unmodifiableMap(out);
    }

    /** 열쇠 하나를 사용자 값 → jar 값 → 기본값 차례로 읽는다. */
    private record Reader(String id, ConfigurationSection s, ConfigurationSection jar, Consumer<String> warn) {
        double num(String key, double def, double lo, double hi) {
            Double v = number(s.get(key), lo, hi);
            if (v != null) return v;
            Double j = jar == null ? null : number(jar.get(key), lo, hi);
            double use = j != null ? j : def;
            if (s.isSet(key)) warn.accept(String.format(Locale.ROOT, "enemies.yml 의 %s.%s = %s 는 %s..%s 의 수가 아니라 %s 로 읽습니다.", id, key,
                    s.get(key), trim(lo), trim(hi), trim(use)));
            return use;
        }

        String word(String key, String def) {
            Object v = s.get(key);
            if (v instanceof String x && !x.isBlank()) return x.trim().toLowerCase(Locale.ROOT);
            Object j = jar == null ? null : jar.get(key);
            String use = j instanceof String x && !x.isBlank() ? x.trim().toLowerCase(Locale.ROOT) : def;
            if (s.isSet(key)) warn.accept("enemies.yml 의 " + id + "." + key + " = " + v + " 는 글이 아니라 " + use + " 로 읽습니다.");
            return use;
        }

        Material material() {
            Material m = Material.parse(s.get("material"));
            if (m != null) return m;
            Material j = jar == null ? null : Material.parse(jar.get("material"));
            Material use = j != null ? j : MATERIAL;
            if (s.isSet("material")) warn.accept("enemies.yml 의 " + id + ".material = " + s.get("material") + " 를 몰라 "
                    + use.name().toLowerCase(Locale.ROOT) + " 로 읽습니다 (flesh, bone, iron, straw).");
            return use;
        }

        /** absorb·weak: 종류마다 수. 모르는 종류나 틀린 값은 그 칸만 jar 값 (없으면 뺀다). */
        Map<Hit.Type, Double> table(String key, double lo, double hi) {
            Map<Hit.Type, Double> out = new EnumMap<>(Hit.Type.class);
            ConfigurationSection js = jar == null ? null : jar.getConfigurationSection(key);
            if (js != null) {
                for (String k : js.getKeys(false)) {
                    Hit.Type t = Hit.Type.parse(k, null);
                    Double v = number(js.get(k), lo, hi);
                    if (t != null && v != null) out.put(t, v);
                }
            }
            if (s.isSet(key) && !s.isConfigurationSection(key)) {
                warn.accept("enemies.yml 의 " + id + "." + key + " 는 {slash: 0.1, …} 꼴이 아니라 jar 값으로 읽습니다.");
                return Collections.unmodifiableMap(out);
            }
            ConfigurationSection us = s.getConfigurationSection(key);
            if (us != null) {
                for (String k : us.getKeys(false)) {
                    Hit.Type t = Hit.Type.parse(k, null);
                    Double v = number(us.get(k), lo, hi);
                    if (t == null || v == null) {
                        warn.accept("enemies.yml 의 " + id + "." + key + "." + k + " = " + us.get(k) + " 는 읽지 않습니다 (종류 "
                                + "standard·slash·strike·thrust·fire·magic, 값 " + trim(lo) + ".." + trim(hi) + ").");
                        continue;
                    }
                    out.put(t, v);
                }
            }
            return Collections.unmodifiableMap(out);
        }
    }

    private static Double number(Object v, double lo, double hi) {
        if (!(v instanceof Number n)) return null;
        double d = n.doubleValue();
        if (Double.isNaN(d) || Double.isInfinite(d) || d < lo || d > hi) return null;
        return d;
    }

    private static String trim(double d) {
        return d == Math.rint(d) && Math.abs(d) < 1e15 ? String.valueOf((long) d) : String.valueOf(d);
    }
}
