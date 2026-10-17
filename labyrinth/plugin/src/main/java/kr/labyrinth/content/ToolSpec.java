package kr.labyrinth.content;

import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.TreeMap;

/**
 * 곡괭이 (items.yml {@code type: tool} 의 {@code tool:} 블록, 0.3.6 — 계약 tools/data/036/mine.json {@code pickaxes}).
 * <ul>
 *   <li>{@code tier} 1~6: 곡괭이 등급. 광석·보석 tier ≤ 곡괭이 tier + {@link #REACH_ABOVE} 일 때만 캔다 (0.3.6.1 주인 결정:
 *       "구리 곡괭이로 철을 캘 수 있고 철 괭이로 은을 캐는 식") — 그보다 단단하면 진행 없음 + 액션바 "곡괭이가 약해 캘 수 없습니다".
 *       플레이어 레벨 조건은 없다 (주인 결정 2).</li>
 *   <li>{@code speed}: 광석 등급 → 채굴 속도 배율. 블록 하나 = 광석 base_seconds ÷ 배율 (좋은 곡괭이일수록 모든 광석에서 빠름).
 *       한 단계 위(tier + 1) 배율은 그 광석 제 곡괭이보다 느리다 (생성기: 그 광석 제 곡괭이 빠르기 × 0.5 — 0.3.7, 딱 두 배 시간). 손으로 고친 items.yml 에 그 칸이 없으면
 *       파서가 {@link #withStretch} 로 같은 식(다음 곡괭이 빠르기 × {@link #STRETCH_FALLBACK})으로 채운다.</li>
 *   <li>{@code bonus}: 광석 1개 더 나올 확률.</li>
 * </ul>
 * 순수 값 객체 (Bukkit 없음). 곡괭이 구성요소(Tool 규칙·CAN_BREAK·UNBREAKABLE)는 {@code mine.MineApi#applyPickaxe} 가 쓴다.
 */
public record ToolSpec(String kind, int tier, Map<Integer, Double> speed, double bonus) {

    public static final String PICKAXE = "pickaxe";
    public static final int MAX_TIER = 6;
    /** 곡괭이 tier 보다 몇 단계 단단한 것까지 캐나 (0.3.6.1 주인 결정: 한 단계 위까지, 느리게). */
    public static final int REACH_ABOVE = 1;
    /** items.yml speed 에 한 단계 위 배율이 없을 때 = 그 광석 제 곡괭이(다음 곡괭이) 빠르기 × 이 값 (손으로 고친 items.yml 대비, 생성기와 같은 식). */
    public static final double STRETCH_FALLBACK = 0.5;

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

    /** 곡괭이마다 제 등급 빠르기 (등급 → 그 곡괭이 speedFor(tier)). 같은 등급이 둘이면 빠른 쪽. */
    public static Map<Integer, Double> ownSpeeds(Collection<ToolSpec> tools) {
        Map<Integer, Double> out = new TreeMap<>();
        for (ToolSpec t : tools) {
            if (t == null || !t.isPickaxe() || t.tier() < 1) continue;
            Double v = t.speed().get(t.tier());
            if (v != null && v > 0) out.merge(t.tier(), v, Math::max);
        }
        return out;
    }

    /**
     * 한 단계 위 배율이 표에 없으면 채운 사본 — 그 광석 제 곡괭이 빠르기({@code own}: {@link #ownSpeeds}) × {@link #STRETCH_FALLBACK}
     * (생성기·계약 mine.json 과 같은 식, 소수 셋째 자리). 이미 있거나 다음 곡괭이를 모르면 그대로.
     */
    public ToolSpec withStretch(Map<Integer, Double> own) {
        int up = maxHardness();
        if (up <= tier || speed.containsKey(up) || own == null) return this;
        Double o = own.get(up);
        if (o == null || o <= 0) return this;
        Map<Integer, Double> sp = new TreeMap<>(speed);
        sp.put(up, Math.round(o * STRETCH_FALLBACK * 1000.0) / 1000.0);
        return new ToolSpec(kind, tier, sp, bonus);
    }

    /** 캘 수 있는 가장 단단한 등급 (tier + 1, 최대 6). 곡괭이가 아니거나 tier 0 이면 0. */
    public int maxHardness() { return tier < 1 ? 0 : Math.min(MAX_TIER, tier + REACH_ABOVE); }

    /** 광석·보석 등급 hardness 를 캘 수 있나 (1 ≤ hardness ≤ tier + 1). */
    public boolean canMine(int hardness) { return hardness >= 1 && hardness <= maxHardness(); }

    /** 캘 수는 있지만 곡괭이보다 단단해 느린 등급인가 (tier &lt; hardness ≤ tier + 1). */
    public boolean isSlow(int hardness) { return canMine(hardness) && hardness > tier; }

    /**
     * 그 등급에 쓰는 속도 배율 (못 캐면 0, 표에 없으면 제 등급 이하 1 · 한 단계 위는 제 등급 배율 × {@link #STRETCH_FALLBACK}).
     * 파서는 먼저 {@link #withStretch} 로 한 단계 위 칸을 채우므로, 이 마지막 대비는 다음 곡괭이가 content 에 없을 때만 쓴다.
     */
    public double speedFor(int hardness) {
        if (!canMine(hardness)) return 0;
        Double v = speed.get(hardness);
        if (v != null && v > 0) return v;
        return hardness > tier ? speedFor(tier) * STRETCH_FALLBACK : 1.0;
    }

    /** 블록 하나 캐는 초 = baseSeconds ÷ speedFor (못 캐면 +∞). */
    public double seconds(double baseSeconds, int hardness) {
        double s = speedFor(hardness);
        return s <= 0 ? Double.POSITIVE_INFINITY : baseSeconds / s;
    }
}
