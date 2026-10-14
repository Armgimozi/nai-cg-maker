package kr.labyrinth.classes;

/**
 * 마나 풀 (순수 로직 — 단위 테스트 대상). 틱 작업 없이 마지막 갱신 이후 경과 시간 × 초당 재생으로 지연 계산한다.
 * 최대치·재생량(직업 mana_regen + WIS×0.05 + 장비)은 매 호출 때 받는다 — 장비·스탯이 바뀌어도 바로 반영.
 */
public final class ManaPool {

    private double current;
    private long lastMs;

    public ManaPool(double current, long nowMs) {
        this.current = Math.max(0, current);
        this.lastMs = nowMs;
    }

    /** 경과 시간만큼 재생을 반영한 현재 MP. */
    public double current(double max, double regenPerSecond, long nowMs) {
        long dt = nowMs - lastMs;
        if (dt > 0 && regenPerSecond > 0) current += regenPerSecond * dt / 1000.0;
        lastMs = Math.max(lastMs, nowMs);
        if (current > max) current = Math.max(0, max);
        return current;
    }

    /** 충분하면 소모하고 true. */
    public boolean spend(double amount, double max, double regenPerSecond, long nowMs) {
        double cur = current(max, regenPerSecond, nowMs);
        if (amount <= 0) return true;
        if (cur + 1e-9 < amount) return false;
        current = cur - amount;
        return true;
    }

    public void restore(double amount, double max, double regenPerSecond, long nowMs) {
        double cur = current(max, regenPerSecond, nowMs);
        current = Math.min(Math.max(0, max), cur + Math.max(0, amount));
    }

    public void set(double value, long nowMs) {
        current = Math.max(0, value);
        lastMs = nowMs;
    }
}
