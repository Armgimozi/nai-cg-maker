package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.stats.Stat;

/**
 * 장비 요구 능력치 (items.yml {@code requires}) — 순수 로직, 단위 테스트 대상.
 * <ul>
 *   <li>0.3.5: 요구는 '그리고'만 — 적힌 능력치를 <b>모두</b> 채워야 한다 ({@code requires: {DEX: 24, STR: 16}}).
 *       예전 {@code requires_any}('… 중 하나')는 없어졌다 (파서가 문제로 알리고 무시).</li>
 *   <li>요구 합 T(L) = ceil(2.75 × (L − 1)), L ≤ 2 이면 없음. 두 능력치 60 : 40, 세 능력치 50 : 30 : 20 (L ≥ 12) — {@link #split}.</li>
 *   <li>판정에 쓰는 플레이어 능력치 = 직업 기본 + 분배한 포인트 + 장착 칭호 보너스 ({@link #playerStats}).
 *       <b>장비 보너스는 넣지 않는다</b> — 장비가 스스로(또는 서로) 조건을 채우는 고리를 막는다.</li>
 *   <li>레벨 제한은 없다 (items.yml level_req 는 장비의 숨은 내부 레벨 — 정렬·강화 골드·드롭 단계에만 쓴다).</li>
 *   <li>글은 요구치 큰 순 ("요구 민첩 24 · 힘 16"), 같으면 STR→LUK 순.</li>
 * </ul>
 */
public record StatRequirement(Map<Stat, Integer> all) {

    public static final StatRequirement NONE = new StatRequirement(Map.of());

    /**
     * 0.3.5 요구 합 T(L) = ceil(2.75 × (L − 1)), L ≤ 2 이면 0 (review2 A3 — 무기·방어구 같은 식). 두 능력치면 60 : 40,
     * 세 능력치면 50 : 30 : 20 (L ≥ 12). L = 숨은 아이템 레벨(items.yml level_req).
     */
    public static int budget(int level) {
        return level <= 2 ? 0 : (int) Math.ceil(2.75 * (level - 1) - 1e-9);
    }

    /**
     * 합 T(L) 을 능력치 순서대로 나눈다 — 하나 = 전부, 둘 = 60 : 40, 셋 = 50 : 30 : 20 (L < 12 면 셋째를 버림).
     * 앞 몫은 반올림 (무기 gear_spec 규칙 — 방어구 생성기는 앞을 올림, 검사는 ±1 을 허용한다).
     */
    public static StatRequirement split(int level, List<Stat> order) {
        int t = budget(level);
        if (t == 0 || order == null || order.isEmpty()) return NONE;
        List<Stat> o = new ArrayList<>(order);
        if (o.size() == 3 && level < 12) o = o.subList(0, 2);
        EnumMap<Stat, Integer> m = new EnumMap<>(Stat.class);
        if (o.size() == 1) {
            m.put(o.get(0), t);
        } else if (o.size() == 2) {
            int a = (int) Math.floor(0.6 * t + 0.5);
            m.put(o.get(0), a);
            m.put(o.get(1), t - a);
        } else {
            int a = (int) Math.floor(0.5 * t + 0.5);
            int b = (int) Math.floor(0.3 * t + 0.5);
            m.put(o.get(0), a);
            m.put(o.get(1), b);
            m.put(o.get(2), t - a - b);
        }
        return of(m);
    }

    /** 충족 색 (툴팁·대장간·도감). */
    public static final String MET_COLOR = "#9be89b";
    /** 미달 색. */
    public static final String UNMET_COLOR = "#ff6b6b";

    public StatRequirement {
        all = copy(all);
    }

    /** 0 이하 값은 버리고 STR→LUK 순서로 고정한 불변 맵. */
    private static Map<Stat, Integer> copy(Map<Stat, Integer> m) {
        if (m == null || m.isEmpty()) return Map.of();
        EnumMap<Stat, Integer> out = new EnumMap<>(Stat.class);
        m.forEach((k, v) -> { if (k != null && v != null && v > 0) out.put(k, v); });
        return out.isEmpty() ? Map.of() : Collections.unmodifiableMap(out);
    }

    public static StatRequirement of(Map<Stat, Integer> all) {
        StatRequirement r = new StatRequirement(all);
        return r.isEmpty() ? NONE : r;
    }

    public boolean isEmpty() { return all.isEmpty(); }

    /** 요구 합. */
    public int total() {
        int t = 0;
        for (int v : all.values()) t += v;
        return t;
    }

    /** 요구치 큰 순 (같으면 STR→LUK) — 글·툴팁·드롭 편향(1위 능력치)이 같은 순서를 쓴다. */
    public List<Map.Entry<Stat, Integer>> ordered() {
        List<Map.Entry<Stat, Integer>> out = new ArrayList<>(all.entrySet());
        out.sort(Comparator.comparing((Map.Entry<Stat, Integer> e) -> -e.getValue()).thenComparing(e -> e.getKey().ordinal()));
        return out;
    }

    /** 요구치가 가장 큰 능력치 (요구 없음 = null). */
    public Stat primary() {
        return all.isEmpty() ? null : ordered().get(0).getKey();
    }

    private static int value(Map<Stat, Integer> stats, Stat s) {
        Integer v = stats == null ? null : stats.get(s);
        return v == null ? 0 : v;
    }

    /** 조건을 모두 맞췄는가 (요구 없음 = 언제나 참). */
    public boolean met(Map<Stat, Integer> stats) {
        for (Map.Entry<Stat, Integer> e : all.entrySet()) if (value(stats, e.getKey()) < e.getValue()) return false;
        return true;
    }

    /**
     * 조건을 맞추려면 더 분배해야 하는 최소 포인트 = 모자란 만큼의 합 (이미 맞췄으면 0) — 시작 무기·초반 장비를
     * Lv.1 시작 포인트로 쓸 수 있는지 검사할 때 쓴다.
     */
    public int pointsNeeded(Map<Stat, Integer> stats) {
        int need = 0;
        for (Map.Entry<Stat, Integer> e : all.entrySet()) need += Math.max(0, e.getValue() - value(stats, e.getKey()));
        return need;
    }

    // ── 플레이어 능력치 ───────────────────────────────────────────────────

    /**
     * 요구치 판정용 플레이어 능력치 = 직업 기본(base_stats) + 분배 포인트 + 칭호 보너스(STR… 키만, 반올림). 장비는 넣지 않는다.
     * @param cls        직업 (null = 직업 없음 → 기본 0)
     * @param titleBonus 장착 칭호 보너스 (titles.yml bonus — xp_bonus 같은 다른 키는 무시, null 허용)
     */
    public static Map<Stat, Integer> playerStats(ClassDef cls, Map<Stat, Integer> allocated, Map<String, Double> titleBonus) {
        EnumMap<Stat, Integer> out = new EnumMap<>(Stat.class);
        for (Stat s : Stat.values()) {
            double title = titleBonus == null ? 0 : titleBonus.getOrDefault(s.key(), 0.0);
            int v = (cls == null ? 0 : cls.baseStat(s)) + (allocated == null ? 0 : allocated.getOrDefault(s, 0))
                    + (int) Math.round(title);
            out.put(s, Math.max(0, v));
        }
        return Collections.unmodifiableMap(out);
    }

    /**
     * 능력치 상위 n 개 (값 큰 순, 같으면 STR→LUK) — 드롭 편향 own_build_bias 가 '그 사람 빌드' 로 본다.
     * 0 인 능력치는 넣지 않는다 (모두 0 이면 빈 목록).
     */
    public static List<Stat> top(Map<Stat, Integer> stats, int n) {
        List<Stat> out = new ArrayList<>();
        if (stats == null) return out;
        List<Stat> all = new ArrayList<>(List.of(Stat.values()));
        all.sort(Comparator.comparing((Stat s) -> -value(stats, s)).thenComparing(Stat::ordinal));
        for (Stat s : all) {
            if (out.size() >= n || value(stats, s) <= 0) break;
            out.add(s);
        }
        return out;
    }

    // ── 문구 ──────────────────────────────────────────────────────────────

    /** "요구 민첩 24 · 힘 16" (요구치 큰 순, 태그 없음, 요구 없음 = 빈 문자열). */
    public String text() {
        if (isEmpty()) return "";
        List<String> t = new ArrayList<>();
        for (Map.Entry<Stat, Integer> e : ordered()) t.add(e.getKey().displayName() + " " + e.getValue());
        return "요구 " + String.join(" · ", t);
    }

    /**
     * 못 맞춘 조건만 지금 값과 함께: "요구 힘 30 (현재 22)". 다 맞췄으면 빈 문자열 (착용 거절·경고 메시지용, 태그 없음).
     */
    public String shortfall(Map<Stat, Integer> stats) {
        List<String> t = new ArrayList<>();
        for (Map.Entry<Stat, Integer> e : ordered()) {
            int have = value(stats, e.getKey());
            if (have < e.getValue()) t.add(e.getKey().displayName() + " " + e.getValue() + " (현재 " + have + ")");
        }
        return t.isEmpty() ? "" : "요구 " + String.join(" · ", t);
    }

    /**
     * 툴팁 한 줄 (MiniMessage). {@code viewer == null}(아이템에 박힌 설명 — 보는 사람을 모름) 이면 "요구 힘 30" 회색·흰색,
     * 보는 사람을 알면 맞춘 조건은 초록, 못 맞춘 조건은 빨강 + "(현재 22)". 요구 없음 = null. 능력치는 요구치 큰 순.
     */
    public String tooltipLine(Map<Stat, Integer> viewer) {
        if (isEmpty()) return null;
        List<String> t = new ArrayList<>();
        if (viewer == null) {
            for (Map.Entry<Stat, Integer> e : ordered()) {
                t.add(e.getKey().displayName() + " <white>" + e.getValue() + "</white>");
            }
            return "<gray>요구 " + String.join(" · ", t);
        }
        boolean ok = met(viewer);
        for (Map.Entry<Stat, Integer> e : ordered()) {
            int have = value(viewer, e.getKey());
            boolean m = have >= e.getValue();
            String c = m ? MET_COLOR : UNMET_COLOR;
            t.add("<" + c + ">" + e.getKey().displayName() + " " + e.getValue() + (m ? "" : " (현재 " + have + ")") + "</" + c + ">");
        }
        String c = ok ? MET_COLOR : UNMET_COLOR;
        return "<" + c + ">요구</" + c + "> " + String.join(" <dark_gray>·</dark_gray> ", t);
    }
}
