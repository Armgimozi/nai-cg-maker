package kr.labyrinth.classes;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 출처(sourceId)별 버프 묶음 (순수 로직 — 단위 테스트 대상). 같은 출처를 다시 걸면 <b>갱신</b>(값·지속시간 교체),
 * 다른 출처끼리는 <b>합산</b>된다. 키는 StatBlock 키로 정규화된다 (버프 키 "damage" → "damage_mult").
 */
public final class BuffSet {

    private record Buff(Map<String, Double> values, long expiresAt) {}

    private final Map<String, Buff> buffs = new LinkedHashMap<>();

    /** GDD §11.7 버프 키 → StatBlock 키. */
    public static String statKey(String buffKey) {
        return switch (buffKey) {
            case "damage" -> "damage_mult";
            case "vulnerability" -> "damage_taken";
            default -> buffKey;
        };
    }

    public void put(String sourceId, Map<String, Double> values, long expiresAt) {
        Map<String, Double> norm = new HashMap<>();
        values.forEach((k, v) -> {
            if (k != null && v != null) norm.merge(statKey(k), v, Double::sum);
        });
        buffs.put(sourceId, new Buff(Map.copyOf(norm), expiresAt));
    }

    public boolean remove(String sourceId) { return buffs.remove(sourceId) != null; }

    public boolean has(String sourceId, long now) {
        Buff b = buffs.get(sourceId);
        return b != null && b.expiresAt() > now;
    }

    /** 남은 시간(ms). 없으면 0. */
    public long remainingMs(String sourceId, long now) {
        Buff b = buffs.get(sourceId);
        return b == null ? 0 : Math.max(0, b.expiresAt() - now);
    }

    /** 만료되지 않은 버프의 키별 합. */
    public Map<String, Double> totals(long now) {
        Map<String, Double> out = new HashMap<>();
        for (Buff b : buffs.values()) {
            if (b.expiresAt() <= now) continue;
            b.values().forEach((k, v) -> out.merge(k, v, Double::sum));
        }
        return out;
    }

    public double total(String statKey, long now) { return totals(now).getOrDefault(statKey, 0.0); }

    /** 만료된 버프 제거. @return 하나라도 지웠으면 true (능력치 재계산 필요) */
    public boolean expire(long now) { return buffs.values().removeIf(b -> b.expiresAt() <= now); }

    public boolean isEmpty() { return buffs.isEmpty(); }

    public void clear() { buffs.clear(); }
}
