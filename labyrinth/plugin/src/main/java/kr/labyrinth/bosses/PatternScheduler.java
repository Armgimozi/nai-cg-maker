package kr.labyrinth.bosses;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.function.Predicate;
import kr.labyrinth.content.Params;

/**
 * 패턴 스케줄러 (GDD §8.3). Bukkit 무관 — 단위 테스트 대상. 시간 단위는 틱.
 * <ol>
 *   <li>{@code cooldown} 이 있는 패턴 → 쿨다운이 돌아온 것 중 하나를 고른다(동시에 한 개, 직전 패턴과 다른 것 우선,
 *       패턴 사이 최소 {@link #MIN_GAP_TICKS}). 여럿이면 {@code weight}(기본 1) 가중 무작위.</li>
 *   <li>{@code interval} 만 있는 패턴 → 그 페이즈 동안 자기 타이머로 따로 반복 ({@link #dueIntervals}).</li>
 *   <li>둘 다 없는 패턴 → 상시 시스템 ({@link #systems}).</li>
 * </ol>
 * 페이즈가 바뀌면 {@link #setPhase} 로 활성 목록을 갈아 끼운다(새로 들어온 패턴은 첫 사용까지 {@code first_delay}
 * 또는 쿨다운의 절반을 기다린다 — 페이즈 시작과 동시에 큰 패턴이 쏟아지지 않게).
 */
public final class PatternScheduler {

    /** 패턴 사이 최소 간격 1.2초. */
    public static final int MIN_GAP_TICKS = 24;

    public enum Kind { COOLDOWN, INTERVAL, SYSTEM }

    /** 활성 패턴 하나. cooldownTicks/intervalTicks 는 배율 적용 전 원값. */
    public static final class Entry {
        final String key;
        final Kind kind;
        final int cooldownTicks;
        final int intervalTicks;
        final double weight;
        long readyAt;

        Entry(String key, Kind kind, int cooldownTicks, int intervalTicks, double weight) {
            this.key = key;
            this.kind = kind;
            this.cooldownTicks = cooldownTicks;
            this.intervalTicks = intervalTicks;
            this.weight = weight;
        }

        public String key() { return key; }
        public Kind kind() { return kind; }
        public long readyAt() { return readyAt; }
    }

    private final Map<String, Entry> entries = new LinkedHashMap<>();
    private final Random rng;
    private String last;
    private long nextAllowed;
    private double cooldownMult = 1.0;

    public PatternScheduler(Random rng) { this.rng = rng; }

    /** 패턴 params → 종류. */
    public static Kind kindOf(Params p) {
        if (p.has("cooldown")) return Kind.COOLDOWN;
        if (p.has("interval")) return Kind.INTERVAL;
        return Kind.SYSTEM;
    }

    /**
     * 페이즈 활성 패턴 교체. 이미 있던 패턴은 쿨다운 상태를 유지한다.
     * @param keys    rotation.&lt;phase&gt; 의 패턴 키
     * @param params  키 → 패턴 params (없으면 EMPTY 취급)
     * @param now     현재 틱
     */
    public void setPhase(Collection<String> keys, Map<String, Params> params, long now) {
        Map<String, Entry> next = new LinkedHashMap<>();
        for (String k : keys) {
            Entry old = entries.get(k);
            if (old != null) {
                next.put(k, old);
                continue;
            }
            Params p = params.getOrDefault(k, Params.EMPTY);
            Kind kind = kindOf(p);
            int cd = (int) Math.round(p.dbl("cooldown", 0) * 20);
            int iv = (int) Math.round(p.dbl("interval", 0) * 20);
            Entry e = new Entry(k, kind, cd, iv, Math.max(0.01, p.dbl("weight", 1.0)));
            double firstDelay = p.dbl("first_delay", -1);
            if (kind == Kind.COOLDOWN) {
                e.readyAt = now + (firstDelay >= 0 ? Math.round(firstDelay * 20) : Math.round(cd * 0.5 * cooldownMult));
            } else if (kind == Kind.INTERVAL) {
                e.readyAt = now + (firstDelay >= 0 ? Math.round(firstDelay * 20) : Math.round(iv * 0.5));
            }
            next.put(k, e);
        }
        entries.clear();
        entries.putAll(next);
    }

    /** 쿨다운 배율 (난이도·페이즈·광폭화, {@link MechanicScaling#cooldownMult}). */
    public void setCooldownMult(double mult) { this.cooldownMult = Math.max(0.05, mult); }

    public double cooldownMult() { return cooldownMult; }

    /**
     * 다음 쿨다운 패턴 고르기 (없으면 null). 고른 패턴은 바로 쿨다운에 들어간다.
     * @param usable 지금 쓸 수 있는가 (대상 없음·조건 미달 패턴 제외). null = 전부 가능
     */
    public String next(long now, Predicate<String> usable) {
        if (now < nextAllowed) return null;
        List<Entry> ready = new ArrayList<>();
        for (Entry e : entries.values()) {
            if (e.kind != Kind.COOLDOWN || now < e.readyAt) continue;
            if (usable != null && !usable.test(e.key)) continue;
            ready.add(e);
        }
        if (ready.isEmpty()) return null;
        if (ready.size() > 1 && last != null) ready.removeIf(e -> e.key.equals(last));
        Entry pick = weighted(ready);
        trigger(pick, now);
        return pick.key;
    }

    private Entry weighted(List<Entry> list) {
        double total = 0;
        for (Entry e : list) total += e.weight;
        double r = rng.nextDouble() * total;
        for (Entry e : list) {
            r -= e.weight;
            if (r <= 0) return e;
        }
        return list.get(list.size() - 1);
    }

    private void trigger(Entry e, long now) {
        e.readyAt = now + Math.max(MIN_GAP_TICKS, Math.round(e.cooldownTicks * cooldownMult));
        last = e.key;
        nextAllowed = now + MIN_GAP_TICKS;
    }

    /**
     * 패턴이 끝난 뒤 다음 패턴까지 최소 간격을 다시 건다 (시전 시간이 긴 패턴 뒤 숨 돌릴 틈).
     */
    public void busyUntil(long tick) {
        nextAllowed = Math.max(nextAllowed, tick + MIN_GAP_TICKS);
    }

    /** interval 패턴 중 시간이 된 것 (자기 타이머 재시작). */
    public List<String> dueIntervals(long now) {
        List<String> out = new ArrayList<>();
        for (Entry e : entries.values()) {
            if (e.kind != Kind.INTERVAL || e.intervalTicks <= 0 || now < e.readyAt) continue;
            e.readyAt = now + e.intervalTicks;
            out.add(e.key);
        }
        return out;
    }

    /** 상시 시스템 패턴 (rotation 에 있고 cooldown·interval 둘 다 없음). */
    public List<String> systems() {
        List<String> out = new ArrayList<>();
        for (Entry e : entries.values()) if (e.kind == Kind.SYSTEM) out.add(e.key);
        return out;
    }

    public boolean active(String key) { return entries.containsKey(key); }

    /** 강제로 쿨다운 재설정 (조합 패턴이 다른 패턴을 썼을 때 등). */
    public void delay(String key, long untilTick) {
        Entry e = entries.get(key);
        if (e != null) e.readyAt = Math.max(e.readyAt, untilTick);
    }

    public String last() { return last; }

    public Entry entry(String key) { return entries.get(key); }

    public Collection<Entry> entries() { return entries.values(); }
}
