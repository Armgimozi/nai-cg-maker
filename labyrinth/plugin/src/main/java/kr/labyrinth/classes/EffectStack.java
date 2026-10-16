package kr.labyrinth.classes;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 한 엔티티의 상태이상 묶음 (순수 로직 — 단위 테스트 대상). 중첩 규칙 = GDD §9.2:
 * <ul>
 *   <li>{@link Rule#REFRESH} (poison·bleed·burn·root·stun·blind·silence·mark·interrupt·frozen):
 *       지속시간은 남은 것과 새 것 중 긴 쪽, 세기는 큰 쪽(같거나 크면 출처 교체)</li>
 *   <li>{@link Rule#MAX} (slow·weaken·vulnerable·cooldown_slow): 세기 = 최대치, 지속시간 = 긴 쪽</li>
 *   <li>{@link Rule#STACKS} (frost·infection·venom · 고유 효과 중첩 출혈·독 bleed_stack·poison_stack): 중첩 += n (상한),
 *       지속시간 갱신. 상한 도달을 알려 준다</li>
 *   <li>{@link Rule#INSTANT} (knockback·damage): 저장하지 않음</li>
 * </ul>
 */
public final class EffectStack {

    public enum Rule { REFRESH, MAX, STACKS, INSTANT }

    /** 정화로 지울 수 있는 해로운 효과 (stun·빙결 제외 — GDD §9.2). */
    public static final Set<String> CLEANSABLE = Set.of("poison", "bleed", "burn", "slow", "root", "weaken",
            "vulnerable", "blind", "silence", "frost", "infection", "venom", "mark", "cooldown_slow", "bleed_stack", "poison_stack");
    /** 지속 피해 효과. */
    public static final Set<String> DOT = Set.of("poison", "bleed", "burn", "venom", "bleed_stack", "poison_stack");

    /**
     * 고유 효과의 중첩 지속 피해 층 (unique_spec rend · imbue 독): 일반 bleed/poison 과 따로 쌓이고(중첩당 피해 × 중첩),
     * {@code has("bleed")}·{@code has("poison")} 에는 함께 잡힌다. 없으면 null.
     */
    public static String stackLayer(String id) {
        return switch (id == null ? "" : id) {
            case "bleed", "bleed_stack" -> "bleed_stack";
            case "poison", "poison_stack" -> "poison_stack";
            default -> null;
        };
    }

    /** 피해가 중첩 수만큼 곱해지는 지속 피해 (맹독·고유 효과 중첩 층). */
    public static boolean dotScalesWithStacks(String id) {
        return "venom".equals(id) || "bleed_stack".equals(id) || "poison_stack".equals(id);
    }

    public static Rule rule(String id) {
        return switch (id) {
            case "slow", "weaken", "vulnerable", "cooldown_slow" -> Rule.MAX;
            case "frost", "infection", "venom", "bleed_stack", "poison_stack" -> Rule.STACKS;
            case "knockback", "damage" -> Rule.INSTANT;
            default -> Rule.REFRESH;
        };
    }

    public static int defaultMaxStacks(String id) {
        return switch (id) {
            case "frost", "infection", "venom", "bleed_stack", "poison_stack" -> 5;
            default -> 1;
        };
    }

    /** 해로운 효과인가. */
    public static boolean harmful(String id) {
        return CLEANSABLE.contains(id) || "stun".equals(id) || "frozen".equals(id);
    }

    /** 효과 하나의 상태 (가변). value = 세기(둔화 비율·초당 피해량 등), stacks = 중첩 수. */
    public static final class Entry {
        public final String id;
        public double value;
        public int stacks;
        public int maxStacks;
        public long expiresAt;
        public UUID source;
        /** 지속 피해 다음 틱 시각 (ms). */
        public long nextTickAt;

        Entry(String id) { this.id = id; }

        public long remainingMs(long now) { return Math.max(0, expiresAt - now); }
    }

    /** apply 결과: 저장된 항목(INSTANT 면 null), 이번에 중첩 상한에 도달했는지, 새로 걸렸는지. */
    public record Applied(Entry entry, boolean reachedMax, boolean isNew) {}

    private final Map<String, Entry> entries = new LinkedHashMap<>();

    public Applied apply(String id, double value, int addStacks, long durationMs, UUID source, long now, int maxStacks) {
        Rule r = rule(id);
        if (r == Rule.INSTANT) return new Applied(null, false, false);
        Entry e = entries.get(id);
        if (e != null && e.expiresAt <= now) {
            entries.remove(id);
            e = null;
        }
        long until = now + Math.max(0, durationMs);
        boolean isNew = e == null;
        if (e == null) {
            e = new Entry(id);
            e.maxStacks = Math.max(1, maxStacks);
            e.nextTickAt = now + 1000;
            entries.put(id, e);
        }
        boolean reached = false;
        if (r == Rule.STACKS) {
            e.maxStacks = Math.max(e.maxStacks, Math.max(1, maxStacks));
            int before = isNew ? 0 : e.stacks;
            e.stacks = Math.min(e.maxStacks, before + Math.max(1, addStacks));
            if (isNew || value >= e.value) {
                e.value = value;
                e.source = source;
            }
            e.expiresAt = until;
            reached = e.stacks >= e.maxStacks && before < e.maxStacks;
        } else {
            if (isNew || value >= e.value) {
                e.value = value;
                e.source = source;
            }
            e.expiresAt = isNew ? until : Math.max(e.expiresAt, until);
            e.stacks = 1;
        }
        return new Applied(e, reached, isNew);
    }

    /** 만료되지 않은 항목 (없으면 null). */
    public Entry get(String id, long now) {
        Entry e = entries.get(id);
        return e == null || e.expiresAt <= now ? null : e;
    }

    public boolean has(String id, long now) { return get(id, now) != null; }

    public int stacks(String id, long now) {
        Entry e = get(id, now);
        return e == null ? 0 : e.stacks;
    }

    public double value(String id, long now) {
        Entry e = get(id, now);
        return e == null ? 0 : e.value;
    }

    public Entry remove(String id) { return entries.remove(id); }

    /** 정화 가능한 효과 전부 제거. @return 지운 id */
    public List<String> cleanse() {
        List<String> removed = new ArrayList<>();
        entries.keySet().removeIf(id -> {
            boolean c = CLEANSABLE.contains(id);
            if (c) removed.add(id);
            return c;
        });
        return removed;
    }

    /** 만료된 항목 제거. @return 지운 항목 */
    public List<Entry> expire(long now) {
        List<Entry> out = new ArrayList<>();
        entries.values().removeIf(e -> {
            boolean x = e.expiresAt <= now;
            if (x) out.add(e);
            return x;
        });
        return out;
    }

    public Collection<Entry> all() { return entries.values(); }

    public boolean isEmpty() { return entries.isEmpty(); }

    public void clear() { entries.clear(); }
}
