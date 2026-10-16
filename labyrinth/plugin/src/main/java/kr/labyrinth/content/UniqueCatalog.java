package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.combat.CombatMath;
import kr.labyrinth.combat.WeaponAttack;

/**
 * 고유 효과 닫힌 목록 26개 (unique_spec §2 · §9, review2 A11·A12) — 순수 데이터. 검사기·런타임·시험이 같은 표를 쓴다.
 * <ul>
 *   <li>수치 종류: {@link ParamKind#SCALED 강도 비례} (기준값 × 강도 s, 상한 {@code hi}) · {@link ParamKind#FIXED 고정} ·
 *       {@link ParamKind#STEP 정수 단계} (대상 수·관통 수·N번째) · {@link ParamKind#ENUM 글} (imbue element)</li>
 *   <li>기준 ({@link Basis}): W = 한 방 공격력 · SP = 스킬 위력 · WG = 한 방 × 간격 보정 g (pct 에 g 를 곱해 저장 — 상한도 × g) ·
 *       MULT = 곱하기 그대로 · NONE = 무기와 무관</li>
 *   <li>{@code onSkill}: 기본 공격 말고 스킬 적중에도 켜지는 효과 (unique_spec §7 폭주 방지 1)</li>
 *   <li>{@code rangedOnly}: {@code attack.style: ranged} 무기만 (관통 사격 — 무기 종류가 아니라 방식으로 본다, A11)</li>
 * </ul>
 * 방패 강타는 직업 스킬 id 와 겹치지 않게 {@code bash_stun} (A12). 예전 이름 {@code shield_bash} 는 읽을 때 바꾼다(경고).
 */
public final class UniqueCatalog {

    private UniqueCatalog() {}

    /** 언제 켜지나. */
    public enum Trigger { ON_HIT, ON_CRIT, NTH_HIT, FIRST_HIT, VS_STATE, HP_ABOVE, HP_BELOW, ON_KILL, ON_HURT, ON_DODGE, ON_SKILL, AURA }

    /** 수치가 무엇에 곱해지나 (unique_spec §9.2). */
    public enum Basis { W, SP, WG, MULT, NONE }

    public enum ParamKind { SCALED, FIXED, STEP, ENUM }

    /** 재발동이 누구 기준인가: 전체(효과마다 한 번) · 대상마다 · 때린 쪽마다(가시 반격). */
    public enum IcdScope { NONE, GLOBAL, PER_TARGET, PER_ATTACKER }

    /**
     * 수치 하나.
     * @param ref 기준값 (강도 s = 1, 빠지면 이 값)
     * @param lo  최솟값
     * @param hi  최댓값 (강도 비례면 카탈로그 상한)
     */
    public record Param(String key, double ref, double lo, double hi, ParamKind kind) {}

    /**
     * 효과 하나.
     * @param icd 재발동(초, 0 = 없음)
     */
    public record Effect(String id, String name, String direction, Trigger trigger, Basis basis, IcdScope icdScope, double icd,
                         boolean rangedOnly, boolean onSkill, List<Param> params) {

        public Param param(String key) {
            for (Param p : params) if (p.key().equals(key)) return p;
            return null;
        }
    }

    /** 빌드 방향 12개 (directions.json). */
    public static final Map<String, String> DIRECTIONS;
    /** 닫힌 목록 26개 (순서 = unique_spec §2 표). */
    public static final Map<String, Effect> EFFECTS;
    /** 예전 id → 지금 id. */
    public static final Map<String, String> ALIASES = Map.of("shield_bash", "bash_stun");
    /** imbue element. */
    public static final Set<String> ELEMENTS = Set.of("burn", "poison", "frost");

    /** 간격 보정 g 의 기준: 장검 0.67초 근접의 (스킬 위력 ÷ 한 방) = 1 ÷ (0.67 × 1.47). */
    public static final double G_REF_INTERVAL = 0.67;
    static final double G_REF = 1.0 / (G_REF_INTERVAL * 1.47);

    static {
        Map<String, String> d = new LinkedHashMap<>();
        d.put("bleed_crit", "출혈치명");
        d.put("sustain", "유지흡혈");
        d.put("bulwark", "방벽제어");
        d.put("blast", "폭발범위");
        d.put("execute", "처형");
        d.put("tempo", "속공");
        d.put("mana_flow", "마나순환");
        d.put("support", "지원");
        d.put("affliction", "상태이상");
        d.put("ambush", "기습");
        d.put("frenzy", "광기");
        d.put("sunder", "파쇄");
        DIRECTIONS = Collections.unmodifiableMap(d);

        Map<String, Effect> m = new LinkedHashMap<>();
        add(m, "rend", "찢는 치명", "bleed_crit", Trigger.ON_CRIT, Basis.W, IcdScope.PER_TARGET, 0.4, false, true,
                s("pct", 0.06, 0.15), f("duration", 4, 1, 10), st("max_stacks", 5, 1, 5));
        add(m, "hemorrhage", "피 냄새", "bleed_crit", Trigger.VS_STATE, Basis.MULT, IcdScope.NONE, 0, false, true,
                s("cc", 0.10, 0.22), s("cd", 0.20, 0.45));
        add(m, "leech", "생명 흡수", "sustain", Trigger.ON_HIT, Basis.W, IcdScope.NONE, 0, false, false,
                s("pct", 0.06, 0.14), f("cap", 0.03, 0.005, 0.2));
        add(m, "feast", "포식", "sustain", Trigger.ON_KILL, Basis.NONE, IcdScope.GLOBAL, 1.0, false, false,
                s("heal", 0.04, 0.10), s("ls", 0.04, 0.10), f("duration", 4, 1, 10));
        add(m, "thorns", "가시 반격", "bulwark", Trigger.ON_HURT, Basis.NONE, IcdScope.PER_ATTACKER, 0.5, false, false,
                s("pct", 0.30, 0.70));
        add(m, "bash_stun", "방패 강타", "bulwark", Trigger.NTH_HIT, Basis.W, IcdScope.NONE, 0, false, false,
                st("n", 5, 2, 8), s("stun", 0.8, 1.5), s("pct", 0.40, 0.90), s("vuln", 0.06, 0.14));
        add(m, "steadfast", "굳건함", "bulwark", Trigger.HP_ABOVE, Basis.NONE, IcdScope.NONE, 0, false, false,
                f("thr", 0.70, 0.3, 0.95), s("dr", 0.08, 0.18));
        add(m, "cleave", "휩쓸기", "blast", Trigger.ON_HIT, Basis.W, IcdScope.NONE, 0, false, false,
                s("pct", 0.30, 0.70), f("radius", 2.5, 1, 5), st("targets", 2, 1, 4));
        add(m, "chain_spark", "연쇄 번개", "blast", Trigger.ON_HIT, Basis.W, IcdScope.GLOBAL, 0.3, false, false,
                f("chance", 0.30, 0.05, 1), s("pct", 0.45, 1.0), st("targets", 2, 1, 4));
        add(m, "death_burst", "시체 폭발", "blast", Trigger.ON_KILL, Basis.SP, IcdScope.GLOBAL, 0.5, false, false,
                s("pct", 0.80, 1.8), f("radius", 3.0, 1, 6));
        add(m, "execute", "마무리", "execute", Trigger.VS_STATE, Basis.MULT, IcdScope.NONE, 0, false, true,
                f("thr", 0.30, 0.1, 0.5), s("pct", 0.25, 0.6));
        add(m, "bloodrush", "추격", "execute", Trigger.ON_KILL, Basis.WG, IcdScope.GLOBAL, 1.0, false, false,
                s("pct", 0.60, 1.4), f("ms", 0.10, 0, 0.3), f("duration", 3, 1, 10));
        add(m, "momentum", "가속", "tempo", Trigger.ON_HIT, Basis.MULT, IcdScope.NONE, 0, false, false,
                s("as", 0.03, 0.06), st("max_stacks", 5, 1, 5), f("decay", 3, 1, 10));
        add(m, "flurry", "연타", "tempo", Trigger.NTH_HIT, Basis.W, IcdScope.NONE, 0, false, false,
                st("n", 4, 2, 8), s("pct", 0.70, 1.6));
        add(m, "counterstep", "흘려치기", "tempo", Trigger.ON_DODGE, Basis.WG, IcdScope.GLOBAL, 2.0, false, false,
                s("pct", 0.30, 0.7), f("window", 3, 1, 10), f("ms", 0.15, 0, 0.3));
        add(m, "siphon", "마력 흡수", "mana_flow", Trigger.ON_KILL, Basis.NONE, IcdScope.GLOBAL, 0.5, false, false,
                s("mp", 0.05, 0.12), s("cdr", 0.5, 1.2));
        add(m, "overcharge", "과부하", "mana_flow", Trigger.ON_SKILL, Basis.SP, IcdScope.GLOBAL, 3.0, false, false,
                s("pct", 1.2, 2.6), f("window", 5, 1, 15), f("radius", 2.5, 1, 5));
        add(m, "sanctify", "축성", "support", Trigger.ON_HIT, Basis.W, IcdScope.GLOBAL, 0.25, false, false,
                s("pct", 0.12, 0.28), f("radius", 8, 2, 16));
        add(m, "ward_aura", "수호 기운", "support", Trigger.AURA, Basis.NONE, IcdScope.NONE, 0, false, false,
                s("pct", 0.04, 0.09), f("period", 8, 2, 30), f("radius", 8, 2, 16), f("duration", 6, 1, 15));
        add(m, "imbue", "원소 부여", "affliction", Trigger.ON_HIT, Basis.SP, IcdScope.PER_TARGET, 1.0, false, true,
                f("chance", 0.25, 0.05, 1), s("pct", 0.10, 0.22), f("duration", 3, 1, 10), new Param("element", 0, 0, 0, ParamKind.ENUM));
        add(m, "exploit", "약점 파고들기", "affliction", Trigger.VS_STATE, Basis.MULT, IcdScope.NONE, 0, false, true,
                s("pct", 0.15, 0.35));
        add(m, "first_strike", "선제", "ambush", Trigger.FIRST_HIT, Basis.WG, IcdScope.NONE, 0, false, true,
                s("pct", 0.80, 1.8), f("cc", 0.20, 0, 0.5), f("window", 10, 2, 30));
        add(m, "backstab", "등 찌르기", "ambush", Trigger.VS_STATE, Basis.MULT, IcdScope.NONE, 0, false, true,
                s("pct", 0.25, 0.6));
        add(m, "longshot", "관통 사격", "ambush", Trigger.ON_HIT, Basis.MULT, IcdScope.NONE, 0, true, false,
                f("dist", 12, 4, 30), s("pct", 0.20, 0.45), st("pierce", 1, 0, 3));
        add(m, "berserk", "광기", "frenzy", Trigger.HP_BELOW, Basis.MULT, IcdScope.NONE, 0, false, true,
                s("pct", 0.025, 0.055), s("ls", 0.05, 0.12), f("thr", 0.30, 0.1, 0.6));
        add(m, "armor_break", "갑옷 부수기", "sunder", Trigger.ON_HIT, Basis.NONE, IcdScope.PER_TARGET, 0.3, false, true,
                s("pct", 0.04, 0.08), st("max_stacks", 5, 1, 5), f("duration", 5, 1, 10));
        EFFECTS = Collections.unmodifiableMap(m);
    }

    private static void add(Map<String, Effect> m, String id, String name, String dir, Trigger t, Basis b, IcdScope scope,
                            double icd, boolean rangedOnly, boolean onSkill, Param... ps) {
        m.put(id, new Effect(id, name, dir, t, b, scope, icd, rangedOnly, onSkill, List.of(ps)));
    }

    private static Param s(String key, double ref, double max) { return new Param(key, ref, 0, max, ParamKind.SCALED); }

    private static Param f(String key, double ref, double lo, double hi) { return new Param(key, ref, lo, hi, ParamKind.FIXED); }

    private static Param st(String key, double ref, double lo, double hi) { return new Param(key, ref, lo, hi, ParamKind.STEP); }

    /** 예전 id 를 지금 id 로 (없으면 그대로, null 이면 ""). */
    public static String canonical(String id) {
        if (id == null) return "";
        String t = id.trim().toLowerCase(java.util.Locale.ROOT);
        return ALIASES.getOrDefault(t, t);
    }

    public static Effect get(String id) { return id == null ? null : EFFECTS.get(canonical(id)); }

    // ── 무기마다 정해지는 값 (unique_spec §9.2) ─────────────────────────────

    /**
     * 간격 보정 g = 그 무기의 (스킬 위력 ÷ 한 방) ÷ 장검 0.67초의 값 = (1 ÷ (간격 × K) × skill_power_mult) ÷ (1 ÷ (0.67 × 1.47)).
     * 단검 0.45초 ≈ 1.60 · 대검 1.0초 ≈ 0.67 · 장궁 1.25초 ≈ 0.56. 선제·추격·흘려치기의 pct 는 이 값을 곱해 저장한다.
     */
    public static double g(WeaponAttack a) {
        WeaponAttack w = a == null ? WeaponAttack.DEFAULT : a;
        return (1.0 / (w.interval() * CombatMath.k(w.style(), w.interval())) * w.skillPowerMult()) / G_REF;
    }

    /** imbue 확률 = 0.25 × min(1.5, 간격 ÷ 0.67), 소수 둘째 자리 (무기마다 저장 — 서비스는 다시 곱하지 않는다). */
    public static double imbueChance(double interval) {
        return Math.round(0.25 * Math.min(1.5, interval / G_REF_INTERVAL) * 100.0) / 100.0;
    }

    /** 방패 강타 N번째 = clamp(round(N기준 × 0.67 ÷ 간격), 2, 8), N기준 = 4(강도 1.4 이상) 또는 5. */
    public static int bashN(int nBase, double interval) {
        long n = Math.round(nBase * G_REF_INTERVAL / Math.max(0.05, interval));
        return (int) Math.max(2, Math.min(8, n));
    }

    // ── 검사 (ContentValidator · 시험) ─────────────────────────────────────

    /** 저장값은 소수 둘째 자리로 반올림한다 — 상한 × g 같은 곱한 상한을 반올림이 0.005 까지 넘을 수 있다. */
    static final double ROUND_SLACK = 0.005 + 1e-9;

    public record Check(List<String> errors, List<String> warnings) {
        public boolean ok() { return errors.isEmpty(); }
    }

    /**
     * 무기 하나의 고유 효과 검사. 닫힌 목록 · 알 수 없는 수치 키 · 범위(강도 비례는 상한, 선제·추격·흘려치기는 상한 × g,
     * 방패 강타 pct 는 상한 × N ÷ 4) · 정수 단계 · imbue element · 원거리 전용 · imbue 확률과 방패 강타 N 이 간격 공식과 맞는지(경고).
     */
    public static Check check(UniqueDef u, WeaponAttack attack) {
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        if (u == null) return new Check(errors, warnings);
        Effect e = get(u.id());
        if (e == null) {
            errors.add("unique.id '" + u.id() + "' 는 닫힌 목록에 없음 (" + String.join(", ", EFFECTS.keySet()) + ")");
            return new Check(errors, warnings);
        }
        WeaponAttack a = attack == null ? WeaponAttack.DEFAULT : attack;
        for (String k : u.params().keys()) {
            if (e.param(k) == null) warnings.add("unique." + k + " — " + e.id() + " 에는 없는 수치 (무시됨)");
        }
        for (Param p : e.params()) {
            if (!u.params().has(p.key())) continue;
            if (p.kind() == ParamKind.ENUM) {
                String v = u.text(p.key(), null);
                if (v == null || !ELEMENTS.contains(v)) errors.add("unique." + p.key() + " 는 burn | poison | frost: " + v);
                continue;
            }
            Object raw = u.params().get(p.key());
            if (!(raw instanceof Number)) {
                errors.add("unique." + p.key() + " 는 숫자여야 함: " + raw);
                continue;
            }
            double v = ((Number) raw).doubleValue();
            double hi = p.hi();
            if (p.kind() == ParamKind.SCALED && e.basis() == Basis.WG && p.key().equals("pct")) hi *= g(a);
            if (e.id().equals("bash_stun") && p.key().equals("pct")) hi *= Math.max(1, u.num("n")) / 4.0;
            if (v < p.lo() - 1e-9 || v > hi + ROUND_SLACK) {
                errors.add("unique." + p.key() + " = " + v + " — " + fmt(p.lo()) + " ~ " + fmt(hi) + " 이어야 함");
            }
            if (p.kind() == ParamKind.STEP && Math.abs(v - Math.rint(v)) > 1e-9) errors.add("unique." + p.key() + " 는 정수: " + v);
        }
        if (e.id().equals("imbue") && !u.params().has("element")) errors.add("unique.element 가 없음 (burn | poison | frost)");
        if (e.rangedOnly() && !a.ranged()) errors.add(e.id() + " 는 원거리(attack.style: ranged) 무기만");
        if (e.id().equals("imbue") && u.params().has("chance")) {
            double want = imbueChance(a.interval());
            if (Math.abs(u.num("chance") - want) > 0.011) {
                warnings.add("unique.chance " + u.num("chance") + " — 간격 " + a.interval() + "초면 " + want + " (0.25 × min(1.5, 간격 ÷ 0.67))");
            }
        }
        if (e.id().equals("bash_stun") && u.params().has("n")) {
            int n = u.count("n");
            if (n != bashN(4, a.interval()) && n != bashN(5, a.interval())) {
                warnings.add("unique.n " + n + " — 간격 " + a.interval() + "초면 " + bashN(4, a.interval()) + " 또는 " + bashN(5, a.interval()));
            }
        }
        return new Check(errors, warnings);
    }

    private static String fmt(double v) {
        return v == Math.rint(v) ? String.valueOf((long) v) : String.format(java.util.Locale.ROOT, "%.3f", v);
    }
}
