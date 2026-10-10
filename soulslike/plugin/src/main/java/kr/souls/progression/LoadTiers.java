package kr.souls.progression;

import java.util.Collections;
import java.util.List;

/**
 * 장비 무게 단계 (5.8): 비율 = 무게 / 한도. 가벼움 &lt; 30%, 보통 &lt; 70%, 무거움 ≤ 100%, 과적 &gt; 100% (load.tiers).
 * 단계마다 구르기 종류, 스태미나 회복 배율, 걷기 배율, 달리기 (load.&lt;단계&gt;.*). 순수 클래스 (13.1 의 LoadTest).
 */
public final class LoadTiers {
    /**
     * 한 단계. upTo 는 이 단계의 비율 윗끝 (마지막 단계는 무한). inclusive 면 윗끝을 넣는다 (무거움 ≤ 100%).
     * roll 은 combat.roll.kinds 의 열쇠 (과적은 backstep: 방향과 상관없이 뒷걸음).
     */
    public record Tier(String id, double upTo, boolean inclusive, String roll, double regen, double walk, boolean sprint) {}

    private final List<Tier> tiers;

    public LoadTiers(List<Tier> tiers) {
        this.tiers = Collections.unmodifiableList(tiers);
    }

    public static LoadTiers defaults() {
        return new LoadTiers(List.of(
                new Tier("light", 0.30, false, "light", 1.00, 1.00, true),
                new Tier("medium", 0.70, false, "medium", 0.95, 1.00, true),
                new Tier("heavy", 1.00, true, "heavy", 0.85, 0.92, true),
                new Tier("over", Double.POSITIVE_INFINITY, true, "backstep", 0.60, 0.70, false)));
    }

    public Tier of(double weight, double cap) {
        double ratio = cap <= 0 ? Double.POSITIVE_INFINITY : weight / cap;
        for (Tier t : tiers) {
            if (ratio < t.upTo() || (t.inclusive() && ratio <= t.upTo() + 1e-9)) return t;
        }
        return tiers.get(tiers.size() - 1);
    }

    public Tier first() {
        return tiers.get(0);
    }

    public List<Tier> all() {
        return tiers;
    }
}
