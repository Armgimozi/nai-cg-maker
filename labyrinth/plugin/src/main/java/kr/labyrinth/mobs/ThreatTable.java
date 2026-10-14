package kr.labyrinth.mobs;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Predicate;

/**
 * 위협(어그로) 표 (GDD §8.5). 위협 = 준 피해 × 직업 위협 배율 + 치유량 × 0.5 (호출자가 계산해서 넣는다).
 * 도발 중인 대상은 지속 시간 동안 강제 1위. Bukkit 무관 — 단위 테스트 대상. 틱 = 서버 틱 카운터.
 */
public final class ThreatTable {

    private final Map<UUID, Double> threat = new HashMap<>();
    private UUID taunter;
    private long tauntUntil;

    public void add(UUID who, double amount) {
        if (who == null || !(amount > 0) || Double.isInfinite(amount)) return;
        threat.merge(who, amount, Double::sum);
    }

    public double get(UUID who) { return threat.getOrDefault(who, 0.0); }

    /** 도발: untilTick 까지 who 를 강제로 노린다. 도발한 사람은 위협도 현재 1위 + 10% 로 맞춘다. */
    public void taunt(UUID who, long untilTick) {
        if (who == null) return;
        taunter = who;
        tauntUntil = untilTick;
        double top = 0;
        for (double v : threat.values()) top = Math.max(top, v);
        threat.put(who, Math.max(get(who), top * 1.1 + 1));
    }

    public boolean isTaunted(long nowTick) { return taunter != null && nowTick < tauntUntil; }

    public UUID taunter(long nowTick) { return isTaunted(nowTick) ? taunter : null; }

    /**
     * 현재 1위 (valid 를 통과한 대상만). 도발이 살아 있고 valid 면 도발자.
     * @return 없으면 null
     */
    public UUID top(long nowTick, Predicate<UUID> valid) {
        if (isTaunted(nowTick) && valid.test(taunter)) return taunter;
        UUID best = null;
        double bestV = -1;
        for (Map.Entry<UUID, Double> e : threat.entrySet()) {
            if (e.getValue() > bestV && valid.test(e.getKey())) {
                best = e.getKey();
                bestV = e.getValue();
            }
        }
        return best;
    }

    /** 유효하지 않은 대상 제거 (접속 종료·사망·너무 멀어짐). */
    public void prune(Predicate<UUID> keep) {
        threat.keySet().removeIf(u -> !keep.test(u));
        if (taunter != null && !keep.test(taunter)) taunter = null;
    }

    /** 전체 위협에 factor 를 곱한다 (전투 이탈 시 서서히 잊기). */
    public void decay(double factor) {
        threat.replaceAll((k, v) -> v * factor);
        threat.values().removeIf(v -> v < 0.01);
    }

    public void remove(UUID who) {
        threat.remove(who);
        if (who != null && who.equals(taunter)) taunter = null;
    }

    public boolean isEmpty() { return threat.isEmpty(); }

    public Map<UUID, Double> snapshot() { return Map.copyOf(threat); }

    public void clear() {
        threat.clear();
        taunter = null;
    }
}
