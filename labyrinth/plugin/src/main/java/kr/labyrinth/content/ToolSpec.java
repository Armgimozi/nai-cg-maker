package kr.labyrinth.content;

import java.util.Collections;
import java.util.Map;
import java.util.TreeMap;

/**
 * 곡괭이 (items.yml {@code type: tool} 의 {@code tool:} 블록, 0.3.6 — 계약 tools/data/036/mine.json {@code pickaxes}).
 * <ul>
 *   <li>{@code tier} 1~6: 이 곡괭이로 캘 수 있는 가장 단단한 광석·보석 등급. 광석 tier ≤ 곡괭이 tier 일 때만 캔다 —
 *       아니면 진행 없음 + 액션바 "곡괭이가 약해 캘 수 없습니다". 플레이어 레벨 조건은 없다 (주인 결정 2).</li>
 *   <li>{@code speed}: 광석 등급 → 채굴 속도 배율. 블록 하나 = 광석 base_seconds ÷ 배율 (좋은 곡괭이일수록 모든 광석에서 빠름).</li>
 *   <li>{@code bonus}: 광석 1개 더 나올 확률.</li>
 * </ul>
 * 순수 값 객체 (Bukkit 없음). 곡괭이 구성요소(Tool 규칙·CAN_BREAK·UNBREAKABLE)는 {@code mine.MineApi#applyPickaxe} 가 쓴다.
 */
public record ToolSpec(String kind, int tier, Map<Integer, Double> speed, double bonus) {

    public static final String PICKAXE = "pickaxe";
    public static final int MAX_TIER = 6;

    public ToolSpec {
        kind = kind == null || kind.isBlank() ? PICKAXE : kind;
        tier = Math.max(0, Math.min(MAX_TIER, tier));
        speed = speed == null ? Map.of() : Collections.unmodifiableMap(new TreeMap<>(speed));
        bonus = Math.max(0, Math.min(1, bonus));
    }

    /** items.yml {@code tool: {kind, tier, speed: {광석 등급: 배율}, bonus}} (예전 시안의 mine_tier 도 tier 로 읽음). 비면 null. */
    public static ToolSpec parse(Params p) {
        if (p == null || p.isEmpty()) return null;
        int tier = p.integer("tier", p.integer("mine_tier", 0));
        Map<Integer, Double> sp = new TreeMap<>();
        Params s = p.sub("speed");
        if (!s.isEmpty()) {
            for (String k : s.keys()) {
                try {
                    sp.put(Integer.parseInt(k.trim()), s.dbl(k, 1.0));
                } catch (NumberFormatException ignored) {
                    // 숫자가 아닌 키는 무시 (ContentValidator 가 알림)
                }
            }
        } else if (p.has("speed")) {
            double all = p.dbl("speed", 1.0);   // 숫자 하나면 캘 수 있는 모든 등급에 같은 배율
            for (int o = 1; o <= tier; o++) sp.put(o, all);
        }
        return new ToolSpec(p.str("kind", PICKAXE), tier, sp, p.dbl("bonus", 0));
    }

    public boolean isPickaxe() { return PICKAXE.equals(kind); }

    /** 광석·보석 등급 hardness 를 캘 수 있나 (hardness ≤ tier). */
    public boolean canMine(int hardness) { return hardness >= 1 && hardness <= tier; }

    /** 그 등급에 쓰는 속도 배율 (못 캐면 0, 표에 없으면 1). */
    public double speedFor(int hardness) {
        if (!canMine(hardness)) return 0;
        Double v = speed.get(hardness);
        return v == null || v <= 0 ? 1.0 : v;
    }

    /** 블록 하나 캐는 초 = baseSeconds ÷ speedFor (못 캐면 +∞). */
    public double seconds(double baseSeconds, int hardness) {
        double s = speedFor(hardness);
        return s <= 0 ? Double.POSITIVE_INFINITY : baseSeconds / s;
    }
}
