package kr.labyrinth.content;

import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import kr.labyrinth.stats.Stat;

/**
 * 장비 요구 능력치 (items.yml {@code requires} / {@code requires_any}) — 순수 로직, 단위 테스트 대상.
 * <ul>
 *   <li>{@code all} = 모두 맞아야 한다 ({@code requires: {STR: 30}}), {@code any} = 하나만 맞으면 된다
 *       ({@code requires_any: {INT: 30, WIS: 30}}). 둘 다 비면 요구 없음.</li>
 *   <li>판정에 쓰는 플레이어 능력치 = 직업 기본 + 분배한 포인트 + 장착 칭호 보너스 ({@link #playerStats}).
 *       <b>장비 보너스는 넣지 않는다</b> — 장비가 스스로(또는 서로) 조건을 채우는 고리를 막는다.</li>
 *   <li>레벨 제한은 없다 (items.yml level_req 는 장비의 숨은 내부 레벨 — 정렬·강화 골드·드롭 단계에만 쓴다).</li>
 * </ul>
 */
public record StatRequirement(Map<Stat, Integer> all, Map<Stat, Integer> any) {

    public static final StatRequirement NONE = new StatRequirement(Map.of(), Map.of());

    /** 충족 색 (툴팁·대장간·도감). */
    public static final String MET_COLOR = "#9be89b";
    /** 미달 색. */
    public static final String UNMET_COLOR = "#ff6b6b";

    public StatRequirement {
        all = copy(all);
        any = copy(any);
    }

    /** 0 이하 값은 버리고 STR→LUK 순서로 고정한 불변 맵. */
    private static Map<Stat, Integer> copy(Map<Stat, Integer> m) {
        if (m == null || m.isEmpty()) return Map.of();
        EnumMap<Stat, Integer> out = new EnumMap<>(Stat.class);
        m.forEach((k, v) -> { if (k != null && v != null && v > 0) out.put(k, v); });
        return out.isEmpty() ? Map.of() : Collections.unmodifiableMap(out);
    }

    public static StatRequirement of(Map<Stat, Integer> all, Map<Stat, Integer> any) {
        StatRequirement r = new StatRequirement(all, any);
        return r.isEmpty() ? NONE : r;
    }

    public boolean isEmpty() { return all.isEmpty() && any.isEmpty(); }

    private static int value(Map<Stat, Integer> stats, Stat s) {
        Integer v = stats == null ? null : stats.get(s);
        return v == null ? 0 : v;
    }

    /** 조건을 모두 맞췄는가 (요구 없음 = 언제나 참). */
    public boolean met(Map<Stat, Integer> stats) {
        for (Map.Entry<Stat, Integer> e : all.entrySet()) if (value(stats, e.getKey()) < e.getValue()) return false;
        return anyMet(stats);
    }

    private boolean anyMet(Map<Stat, Integer> stats) {
        if (any.isEmpty()) return true;
        for (Map.Entry<Stat, Integer> e : any.entrySet()) if (value(stats, e.getKey()) >= e.getValue()) return true;
        return false;
    }

    /**
     * 조건을 맞추려면 더 분배해야 하는 최소 포인트 (이미 맞췄으면 0). all 은 모자란 만큼 모두, any 는 all 을 채운 뒤
     * 가장 가까운 능력치 하나 — 시작 무기·초반 장비를 Lv.1 시작 포인트로 쓸 수 있는지 검사할 때 쓴다.
     */
    public int pointsNeeded(Map<Stat, Integer> stats) {
        int need = 0;
        EnumMap<Stat, Integer> after = new EnumMap<>(Stat.class);
        for (Stat s : Stat.values()) after.put(s, value(stats, s));
        for (Map.Entry<Stat, Integer> e : all.entrySet()) {
            int gap = e.getValue() - after.get(e.getKey());
            if (gap > 0) {
                need += gap;
                after.put(e.getKey(), e.getValue());
            }
        }
        if (!any.isEmpty()) {
            int best = Integer.MAX_VALUE;
            for (Map.Entry<Stat, Integer> e : any.entrySet()) best = Math.min(best, Math.max(0, e.getValue() - after.get(e.getKey())));
            need += best;
        }
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

    // ── 문구 ──────────────────────────────────────────────────────────────

    /** "힘 30 · 체력 20" 의 한 칸 = 능력치 하나 (all) 또는 "지능 또는 정신 30" (any 전체). */
    private record Part(String text, boolean met, String now) {}

    private List<Part> parts(Map<Stat, Integer> stats) {
        List<Part> out = new ArrayList<>();
        for (Map.Entry<Stat, Integer> e : all.entrySet()) {
            int have = value(stats, e.getKey());
            out.add(new Part(e.getKey().displayName() + " " + e.getValue(), have >= e.getValue(), String.valueOf(have)));
        }
        if (!any.isEmpty()) {
            List<String> names = new ArrayList<>();
            List<String> now = new ArrayList<>();
            boolean same = new HashSet<>(any.values()).size() == 1;
            for (Map.Entry<Stat, Integer> e : any.entrySet()) {
                names.add(e.getKey().displayName() + (same ? "" : " " + e.getValue()));
                now.add(e.getKey().displayName() + " " + value(stats, e.getKey()));
            }
            String text = String.join(" 또는 ", names) + (same ? " " + any.values().iterator().next() : "");
            out.add(new Part(text, anyMet(stats), String.join(" · ", now)));
        }
        return out;
    }

    /** "요구 힘 30" · "요구 힘 30 · 체력 20" · "요구 지능 또는 정신 30" (태그 없음, 요구 없음 = 빈 문자열). */
    public String text() {
        if (isEmpty()) return "";
        List<String> t = new ArrayList<>();
        for (Part p : parts(null)) t.add(p.text());
        return "요구 " + String.join(" · ", t);
    }

    /**
     * 못 맞춘 조건만 지금 값과 함께: "요구 힘 30 (현재 22)" · "요구 지능 또는 정신 30 (현재 지능 22 · 정신 18)".
     * 다 맞췄으면 빈 문자열 (착용 거절·경고 메시지용, 태그 없음).
     */
    public String shortfall(Map<Stat, Integer> stats) {
        List<String> t = new ArrayList<>();
        for (Part p : parts(stats)) if (!p.met()) t.add(p.text() + " (현재 " + p.now() + ")");
        return t.isEmpty() ? "" : "요구 " + String.join(" · ", t);
    }

    /**
     * 툴팁 한 줄 (MiniMessage). {@code viewer == null}(아이템에 박힌 설명 — 보는 사람을 모름) 이면 "요구 힘 30" 회색·흰색,
     * 보는 사람을 알면 맞춘 조건은 초록, 못 맞춘 조건은 빨강 + "(현재 22)". 요구 없음 = null.
     */
    public String tooltipLine(Map<Stat, Integer> viewer) {
        if (isEmpty()) return null;
        List<String> t = new ArrayList<>();
        if (viewer == null) {
            for (Part p : parts(null)) t.add(p.text().replaceAll("(\\d+)", "<white>$1</white>"));
            return "<gray>요구 " + String.join(" · ", t);
        }
        boolean ok = met(viewer);
        for (Part p : parts(viewer)) {
            String c = p.met() ? MET_COLOR : UNMET_COLOR;
            t.add("<" + c + ">" + p.text() + (p.met() ? "" : " (현재 " + p.now() + ")") + "</" + c + ">");
        }
        String c = ok ? MET_COLOR : UNMET_COLOR;
        return "<" + c + ">요구</" + c + "> " + String.join(" <dark_gray>·</dark_gray> ", t);
    }
}
