package kr.labyrinth.pvp;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 플레이어 한 명이 다른 파티 플레이어에게 맞는 상태이상 기록 (pvp_spec §9.1) — 순수 로직, 단위 테스트 대상.
 * <pre>
 * 시간 = (정신·판금 감소를 거친 시간) × PvP 배율(종류) → 상한(종류)
 *      × 줄어듦 (같은 분류를 window 초 안에 다시: 1.0 → 0.5 → 0.25 → 면역, window 동안 안 맞으면 처음으로)
 *      → 행동 불가(control) 면역 중이면 0
 *      → min_seconds 보다 짧으면 0 (그래도 횟수는 센다)
 * 행동 불가(기절·빙결)가 끝나면 {@link #onControlEnd} → control_immunity 초 동안 행동 불가 면역
 * </pre>
 * 기절을 느려짐으로 바꾸지 않는다 — 기절은 기절 그대로, 시간만 줄인다. 둔화·재사용 둔화는 줄어듦 없이 배율·상한만.
 */
public final class PvpCc {

    private static final class Count {
        int hits;
        long lastAt;
    }

    private final Map<String, Count> counts = new HashMap<>();
    private long controlImmuneUntil;

    /**
     * PvP 규칙을 거친 시간(초). 0 = 걸지 않음.
     * @param id      효과 id (stun·frozen·root·silence·blind·slow·cooldown_slow …)
     * @param seconds 정신(WIS)·판금 감소까지 거친 시간
     */
    public synchronized double duration(PvpConfig.CcConfig c, String id, double seconds, long now) {
        if (id == null || seconds <= 0) return Math.max(0, seconds);
        double d = seconds * c.duration().getOrDefault(id, 1.0);
        Double max = c.maxSeconds().get(id);
        if (max != null) d = Math.min(d, max);
        String group = c.groupOf(id);
        if (group != null) {
            Count n = counts.computeIfAbsent(group, g -> new Count());
            if (n.hits > 0 && now - n.lastAt > (long) (c.window() * 1000)) n.hits = 0;
            List<Double> steps = c.steps();
            d *= steps.get(Math.min(n.hits, steps.size() - 1));
            n.hits++;
            n.lastAt = now;
        }
        if (c.isControl(id) && now < controlImmuneUntil) return 0;
        return d < c.minSeconds() - 1e-9 ? 0 : d;
    }

    /** 행동 불가(기절·빙결)가 끝났다 (만료·동료가 깨 줌·정화) → 잠깐 면역. */
    public synchronized void onControlEnd(PvpConfig.CcConfig c, long now) {
        controlImmuneUntil = Math.max(controlImmuneUntil, now + (long) (c.controlImmunity() * 1000));
    }

    /** 지금 행동 불가 면역인가. */
    public synchronized boolean controlImmune(long now) { return now < controlImmuneUntil; }

    /** 그 분류의 지금 줄어듦 횟수 (window 가 지났으면 0). */
    public synchronized int hits(PvpConfig.CcConfig c, String group, long now) {
        Count n = counts.get(group);
        if (n == null || now - n.lastAt > (long) (c.window() * 1000)) return 0;
        return n.hits;
    }

    /** 기록이 모두 지났는가 (지워도 되는가). */
    public synchronized boolean idle(PvpConfig.CcConfig c, long now) {
        if (now < controlImmuneUntil) return false;
        for (Count n : counts.values()) if (now - n.lastAt <= (long) (c.window() * 1000)) return false;
        return true;
    }

    /** 둔화 세기 상한 (플레이어에게 건 것만). */
    public static double slowPotency(PvpConfig.CcConfig c, double potency) { return Math.min(potency, c.slowMaxPotency()); }
}
