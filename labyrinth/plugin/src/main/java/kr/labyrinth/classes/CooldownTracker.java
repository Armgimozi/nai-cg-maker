package kr.labyrinth.classes;

import java.util.HashMap;
import java.util.Map;

/**
 * 스킬 재사용 대기 (순수 로직 — 단위 테스트 대상). 남은 시간을 초 단위로 들고 {@link #advance} 로 흐르게 한다.
 * rate &lt; 1 이면 느리게 돈다 (GDD §9.2 cooldown_slow: 9층 시간 나방).
 */
public final class CooldownTracker {

    private final Map<String, Double> remaining = new HashMap<>();

    /** 재사용 감소(0~1, 상한은 StatCalculator 가 이미 적용)를 반영한 실제 대기 시간. */
    public static double effective(double baseSeconds, double cooldownReduction) {
        double cdr = Math.max(0, Math.min(0.95, cooldownReduction));
        return Math.max(0, baseSeconds * (1.0 - cdr));
    }

    public void start(String id, double seconds) {
        if (seconds <= 0) remaining.remove(id);
        else remaining.put(id, seconds);
    }

    /** 남은 시간(초). 준비됐으면 0. */
    public double remaining(String id) {
        Double r = remaining.get(id);
        return r == null ? 0 : Math.max(0, r);
    }

    public boolean ready(String id) { return remaining(id) <= 0; }

    /**
     * 시간 흐름. @param rate 1 = 정상, 0.7 = 30% 느리게.
     * @return 이번에 준비 완료된 스킬 id 하나 (없으면 null) — 준비 알림용
     */
    public String advance(double dtSeconds, double rate) {
        if (remaining.isEmpty() || dtSeconds <= 0) return null;
        double step = dtSeconds * Math.max(0, rate);
        String readied = null;
        var it = remaining.entrySet().iterator();
        while (it.hasNext()) {
            var e = it.next();
            double left = e.getValue() - step;
            if (left <= 1e-9) {
                it.remove();
                if (readied == null) readied = e.getKey();
            } else {
                e.setValue(left);
            }
        }
        return readied;
    }

    /** 남은 시간을 seconds 로 덮어쓰기 (취소된 시전의 부분 환급 등). */
    public void set(String id, double seconds) { start(id, seconds); }

    public void reset(String id) { remaining.remove(id); }

    public void clear() { remaining.clear(); }

    public boolean isEmpty() { return remaining.isEmpty(); }
}
