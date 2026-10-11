package kr.souls.combat;

import org.bukkit.configuration.ConfigurationSection;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * 무기 분류마다의 공격 동작 (content/moves.yml, 3.6 의 분류표). 읽기만 하는 순수 셈 (13.1 의 MovesetTest).
 * moves.yml 은 열쇠마다 jar 사본 위에 겹쳐 읽은 것 (Content.merged, R20) 을 받는다. 그래도 값이 틀렸거나 (글자, 음수, 모양 이름) 빠진
 * 열쇠는 그 열쇠만 기본값 (아래 DEFAULTS: 3.6 의 직검) 으로 읽고, 틀린 것은 {@link #problems} 에 남긴다 (서버 기록에 한 번).
 * <pre>
 *   &lt;분류&gt;:
 *     shape: cone | line        cone 은 부채꼴 안 모두 (휩쓸기), line 은 첫 대상만 (찌르기)
 *     angle: 100                부채꼴의 전체 각 (도)
 *     range: 3.0                사거리 (눈에서 상자 가장자리까지, 칸). 아이템의 attack_range 도 이 값 (hitbox_margin 0, S6)
 *     width: 0.4                직선의 폭 (칸. Footprint 가 몸 0.5 를 더한다)
 *     type: slash               피해 종류 (slash | strike | thrust | standard: 적의 흡수·약점표)
 *     swing: whack              아이템의 휘두르는 모습 (whack | stab)
 *     light: [[4, 2, 7], …]     약공격 n단의 준비/판정/회복 틱 (민첩 10). 단마다 {s:, a:, r:, shape:, angle:, range:, width:, type:} 도 된다
 *     heavy: [8, 2, 12]         강공격 (웅크리기 키 + 좌클릭)
 *     running: [4, 2, 7]        달리기 공격 (없으면 약공격 1단)
 *     stamina: {light: 14, heavy: 22}
 *     poise: {light: 12, heavy: 24}
 *     step: {light: 0.2, heavy: 0.3, running: 0.45}   첫 판정 틱에 앞으로 내딛는 거리 (칸, 땅 위에서)
 *     as: dagger                다른 분류를 그대로 쓴다 (패링 단검)
 * </pre>
 */
public final class Moveset {
    /** 동작 하나의 틱과 판정. */
    public record Step(int s, int a, int r, HitQuery.Spec spec, Hit.Type type) {
        public MoveTiming.Base base() {
            return new MoveTiming.Base(s, a, r);
        }

        public int cycle() {
            return s + a + r;
        }
    }

    /** 한 분류. light 는 1단부터 (비지 않는다). */
    public record Cls(String id, HitQuery.Spec spec, Hit.Type type, boolean stab, List<Step> light, Step heavy, Step running,
                      double staminaLight, double staminaHeavy, double poiseLight, double poiseHeavy,
                      double stepLight, double stepHeavy, double stepRunning) {
        /** 약공격 i 단 (0 부터, 길이로 돌린다). */
        public Step light(int i) {
            return light.get(Math.floorMod(i, light.size()));
        }

        public int combo() {
            return light.size();
        }

        /** 약공격 1단의 한 주기 (민첩 10). M1 전의 pve.swing-ticks 와 같다 */
        public int lightCycle() {
            return light.get(0).cycle();
        }
    }

    /** 3.6 의 직검: 빠졌거나 틀린 열쇠의 기본값 */
    static final HitQuery.Spec DEFAULT_SPEC = new HitQuery.Spec(HitQuery.Shape.CONE, 100, 3.0, 0.4, 1.2);
    static final int[] DEFAULT_STEP = {4, 2, 7};
    static final int[] DEFAULT_HEAVY = {8, 2, 12};

    private final Map<String, Cls> classes;
    private final List<String> problems;

    private Moveset(Map<String, Cls> classes, List<String> problems) {
        this.classes = Collections.unmodifiableMap(classes);
        this.problems = Collections.unmodifiableList(problems);
    }

    /** 빈 것 (moves.yml 을 읽기 전). */
    public static Moveset empty() {
        return new Moveset(new LinkedHashMap<>(), new ArrayList<>());
    }

    /** 분류 cls 의 동작 (as 를 따라간 것). 없으면 null. */
    public Cls of(String cls) {
        return cls == null ? null : classes.get(cls);
    }

    public Map<String, Cls> all() {
        return classes;
    }

    /** 읽다가 기본값으로 바꾼 곳 ("straight_sword.light[1]: …"). */
    public List<String> problems() {
        return problems;
    }

    /**
     * moves.yml (겹쳐 읽은 것) 을 읽는다. vertical 은 판정 위아래 (combat.moves.vertical: 분류마다가 아니다).
     */
    public static Moveset parse(ConfigurationSection root, double vertical) {
        Map<String, Cls> out = new LinkedHashMap<>();
        List<String> bad = new ArrayList<>();
        if (root == null) return new Moveset(out, bad);
        Map<String, String> alias = new LinkedHashMap<>();
        for (String id : root.getKeys(false)) {
            ConfigurationSection c = root.getConfigurationSection(id);
            if (c == null) continue;
            if (c.isString("as")) {
                alias.put(id, c.getString("as"));
                continue;
            }
            out.put(id, cls(id, c, vertical, bad));
        }
        for (Map.Entry<String, String> e : alias.entrySet()) {
            Cls to = out.get(e.getValue());
            if (to == null) bad.add(e.getKey() + ".as: " + e.getValue() + " 가 없다"); // lang-ok: 서버 기록에만
            else out.put(e.getKey(), to);
        }
        return new Moveset(out, bad);
    }

    private static Cls cls(String id, ConfigurationSection c, double vertical, List<String> bad) {
        HitQuery.Spec spec = spec(id, c, null, vertical, bad);
        Hit.Type type = type(id, c.getString("type"), Hit.Type.SLASH, bad);
        String sw = c.getString("swing", "whack").toLowerCase(Locale.ROOT).trim();
        if (!sw.equals("whack") && !sw.equals("stab")) {
            bad.add(id + ".swing: " + sw);
            sw = "whack";
        }
        List<Step> light = new ArrayList<>();
        List<?> raw = c.getList("light");
        if (raw != null) {
            for (int i = 0; i < raw.size(); i++) {
                Step st = step(id + ".light[" + (i + 1) + "]", raw.get(i), spec, type, vertical, bad);
                if (st != null) light.add(st);
            }
        }
        if (light.isEmpty()) {
            bad.add(id + ".light: 없거나 틀렸다"); // lang-ok: 서버 기록에만
            light.add(new Step(DEFAULT_STEP[0], DEFAULT_STEP[1], DEFAULT_STEP[2], spec, type));
        }
        Step heavy = step(id + ".heavy", c.get("heavy"), spec, type, vertical, bad);
        if (heavy == null) heavy = new Step(DEFAULT_HEAVY[0], DEFAULT_HEAVY[1], DEFAULT_HEAVY[2], spec, type);
        Step running = c.contains("running") ? step(id + ".running", c.get("running"), spec, type, vertical, bad) : null;
        if (running == null) running = light.get(0);
        return new Cls(id, spec, type, sw.equals("stab"), List.copyOf(light), heavy, running,
                pos(id + ".stamina.light", c, "stamina.light", 14, bad), pos(id + ".stamina.heavy", c, "stamina.heavy", 22, bad),
                pos(id + ".poise.light", c, "poise.light", 12, bad), pos(id + ".poise.heavy", c, "poise.heavy", 24, bad),
                pos(id + ".step.light", c, "step.light", 0.2, bad), pos(id + ".step.heavy", c, "step.heavy", 0.3, bad),
                pos(id + ".step.running", c, "step.running", 0.45, bad));
    }

    /** 모양 (분류의 것, 또는 단의 것이 분류의 것을 바꾼다). */
    private static HitQuery.Spec spec(String id, ConfigurationSection c, HitQuery.Spec over, double vertical, List<String> bad) {
        HitQuery.Spec base = over != null ? over : DEFAULT_SPEC;
        HitQuery.Shape shape = base.shape();
        if (c.isString("shape")) {
            String s = c.getString("shape").toLowerCase(Locale.ROOT).trim();
            if (s.equals("cone")) shape = HitQuery.Shape.CONE;
            else if (s.equals("line")) shape = HitQuery.Shape.LINE;
            else bad.add(id + ".shape: " + s);
        }
        double angle = num(id + ".angle", c, "angle", base.angle(), 0, 360, bad);
        double range = num(id + ".range", c, "range", base.range(), 0.5, 16, bad);
        double width = num(id + ".width", c, "width", base.width(), 0, 8, bad);
        return new HitQuery.Spec(shape, angle, range, width, vertical);
    }

    /** 단 하나: [s, a, r] 또는 {s:, a:, r:, shape:, …}. 틀렸으면 null. */
    private static Step step(String where, Object o, HitQuery.Spec spec, Hit.Type type, double vertical, List<String> bad) {
        if (o instanceof List<?> l) {
            int[] t = triple(l);
            if (t == null) {
                bad.add(where + ": [준비, 판정, 회복] 이 아니다 " + l); // lang-ok: 서버 기록에만
                return null;
            }
            return new Step(t[0], t[1], t[2], spec, type);
        }
        if (o instanceof ConfigurationSection m) {
            int[] t = triple(List.of(m.get("s", -1), m.get("a", -1), m.get("r", -1)));
            if (t == null) {
                bad.add(where + ": s·a·r 이 없다"); // lang-ok: 서버 기록에만
                return null;
            }
            return new Step(t[0], t[1], t[2], spec(where, m, spec, vertical, bad), type(where, m.getString("type"), type, bad));
        }
        if (o instanceof Map<?, ?> m) {
            int[] t = triple(java.util.Arrays.asList(m.get("s"), m.get("a"), m.get("r")));
            if (t == null) {
                bad.add(where + ": s·a·r 이 없다"); // lang-ok: 서버 기록에만
                return null;
            }
            org.bukkit.configuration.MemoryConfiguration sec = new org.bukkit.configuration.MemoryConfiguration();
            for (Map.Entry<?, ?> e : m.entrySet()) sec.set(String.valueOf(e.getKey()), e.getValue());
            return new Step(t[0], t[1], t[2], spec(where, sec, spec, vertical, bad), type(where, sec.getString("type"), type, bad));
        }
        if (o != null) bad.add(where + ": " + o);
        return null;
    }

    /** [s, a, r]: 준비 1 이상, 판정 1 이상, 회복 0 이상 (모두 200 밑). */
    private static int[] triple(List<?> l) {
        if (l == null || l.size() != 3) return null;
        int[] out = new int[3];
        for (int i = 0; i < 3; i++) {
            if (!(l.get(i) instanceof Number n)) return null;
            double v = n.doubleValue();
            if (Double.isNaN(v) || v != Math.rint(v) || v < (i == 2 ? 0 : 1) || v > 200) return null;
            out[i] = (int) v;
        }
        return out;
    }

    private static Hit.Type type(String where, String s, Hit.Type def, List<String> bad) {
        if (s == null) return def;
        Hit.Type t = Hit.Type.parse(s, null);
        if (t == null) {
            bad.add(where + ".type: " + s);
            return def;
        }
        return t;
    }

    private static double num(String where, ConfigurationSection c, String path, double def, double min, double max, List<String> bad) {
        if (!c.contains(path)) return def;
        Object o = c.get(path);
        if (!(o instanceof Number n) || Double.isNaN(n.doubleValue()) || n.doubleValue() < min || n.doubleValue() > max) {
            bad.add(where + ": " + o);
            return def;
        }
        return n.doubleValue();
    }

    private static double pos(String where, ConfigurationSection c, String path, double def, List<String> bad) {
        return num(where, c, path, def, 0, 10000, bad);
    }
}
