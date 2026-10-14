package kr.labyrinth.classes;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 보호막 (순수 로직 — 단위 테스트 대상). 출처별 보호막량·만료 시각. 피해는 <b>먼저 사라질 보호막부터</b> 흡수한다.
 * 같은 출처를 다시 걸면 더 큰 값으로 갱신, {@link #addStacking} 은 상한까지 누적(사제 은총의 넘친 치유).
 */
public final class ShieldPool {

    private static final class Entry {
        double amount;
        long expiresAt;

        Entry(double amount, long expiresAt) {
            this.amount = amount;
            this.expiresAt = expiresAt;
        }
    }

    private final Map<String, Entry> entries = new LinkedHashMap<>();

    public void add(String sourceId, double amount, long expiresAt) {
        if (amount <= 0) return;
        Entry e = entries.get(sourceId);
        if (e == null) {
            entries.put(sourceId, new Entry(amount, expiresAt));
        } else {
            e.amount = Math.max(e.amount, amount);
            e.expiresAt = Math.max(e.expiresAt, expiresAt);
        }
    }

    /** 누적형: 기존 + amount, 최대 cap. 지속시간은 갱신. */
    public void addStacking(String sourceId, double amount, double cap, long expiresAt) {
        if (amount <= 0 || cap <= 0) return;
        Entry e = entries.get(sourceId);
        if (e == null) {
            entries.put(sourceId, new Entry(Math.min(cap, amount), expiresAt));
        } else {
            e.amount = Math.min(cap, e.amount + amount);
            e.expiresAt = Math.max(e.expiresAt, expiresAt);
        }
    }

    /** 피해를 흡수하고 남은 피해를 돌려준다. */
    public double absorb(double damage, long now) {
        if (damage <= 0 || entries.isEmpty()) return Math.max(0, damage);
        expire(now);
        List<Map.Entry<String, Entry>> order = new ArrayList<>(entries.entrySet());
        order.sort(Comparator.comparingLong(e -> e.getValue().expiresAt));
        double left = damage;
        for (Map.Entry<String, Entry> me : order) {
            Entry e = me.getValue();
            double take = Math.min(e.amount, left);
            e.amount -= take;
            left -= take;
            if (e.amount <= 1e-9) entries.remove(me.getKey());
            if (left <= 0) break;
        }
        return Math.max(0, left);
    }

    public double total(long now) {
        double t = 0;
        for (Entry e : entries.values()) if (e.expiresAt > now) t += e.amount;
        return t;
    }

    public boolean expire(long now) { return entries.values().removeIf(e -> e.expiresAt <= now || e.amount <= 1e-9); }

    public boolean isEmpty() { return entries.isEmpty(); }

    public void clear() { entries.clear(); }
}
