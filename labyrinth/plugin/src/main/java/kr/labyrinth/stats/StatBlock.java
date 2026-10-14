package kr.labyrinth.stats;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * 가산 스탯 묶음 (가변). 키는 GDD §11.7 아이템 스탯 키 26개(damage, STR…LUK, hp, mp, defense, crit_chance …).
 * <p>
 * 추가 키 (버프·상태이상 전용 — StatusEffectService 가 넣는다):
 * <ul>
 *   <li>{@code damage_mult} — 주는 피해 +% (버프 키 "damage" 를 이 키로 넣을 것. weaken 은 음수)</li>
 *   <li>{@code damage_taken} — 받는 피해 +% (vulnerable)</li>
 * </ul>
 * damage 는 "무기 피해"(공격력 기반)이므로 버프의 주는 피해 %와 섞으면 안 된다.
 */
public final class StatBlock {

    private final Map<String, Double> values = new HashMap<>();

    public StatBlock add(String key, double v) {
        if (v != 0) values.merge(key, v, Double::sum);
        return this;
    }

    public StatBlock add(Stat s, double v) { return add(s.key(), v); }

    public StatBlock addAll(Map<String, Double> m) {
        m.forEach(this::add);
        return this;
    }

    public StatBlock addAll(StatBlock o) {
        o.values.forEach(this::add);
        return this;
    }

    public double get(String key) { return values.getOrDefault(key, 0.0); }

    public double get(Stat s) { return get(s.key()); }

    public Map<String, Double> asMap() { return Collections.unmodifiableMap(values); }

    @Override
    public String toString() { return values.toString(); }
}
