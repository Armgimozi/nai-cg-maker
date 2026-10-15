package kr.labyrinth.items.enhance;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.ToIntFunction;

/**
 * 강화 한 번 비용 (GDD §11.13) — 골드 + 강화석 + 그 장비 재료. 순수 로직, 단위 테스트 대상.
 * <p>
 * <b>전부 아니면 아무것도</b>: {@link #pay} 는 골드와 모든 줄을 먼저 확인하고, 하나라도 모자라면 아무것도 가져가지 않는다.
 * 실패해도 돌려주지 않는다 (판정 전에 이미 낸 비용).
 *
 * @param gold  골드 (할인 적용 뒤)
 * @param lines 재료 줄 — 강화석 줄이 맨 앞, 같은 id 는 한 줄로 합쳐져 있다
 */
public record EnhanceCost(long gold, List<Line> lines) {

    /** 재료 한 줄. stone = 강화석(config.yml enhance.stones) 인가. */
    public record Line(String item, int amount, boolean stone) {}

    /** 줄 하나의 확인 결과 (창 표시용). */
    public record Check(Line line, int have) {
        public boolean ok() { return have >= line.amount(); }
    }

    /** 비용을 낼 주머니 — 실제로는 플레이어 가방 + 골드, 테스트에서는 맵. */
    public interface Purse {
        long gold();

        int count(String item);

        /** 골드를 뺀다 (모자라면 false, 아무것도 안 뺌). */
        boolean takeGold(long amount);

        /** 재료를 뺀다 — 이미 {@link #count} 로 확인한 뒤에만 부른다. */
        void take(String item, int amount);
    }

    public EnhanceCost {
        lines = List.copyOf(lines);
    }

    /** 강화석 줄 (없으면 null). */
    public Line stone() {
        for (Line l : lines) if (l.stone()) return l;
        return null;
    }

    /** 강화석이 아닌 그 장비 재료 줄. */
    public List<Line> materials() {
        List<Line> out = new ArrayList<>();
        for (Line l : lines) if (!l.stone()) out.add(l);
        return out;
    }

    /** 줄마다 보유 개수 확인. */
    public List<Check> check(ToIntFunction<String> have) {
        List<Check> out = new ArrayList<>();
        for (Line l : lines) out.add(new Check(l, Math.max(0, have.applyAsInt(l.item()))));
        return out;
    }

    /** 모자란 줄 (없으면 빈 목록). */
    public List<Line> missing(ToIntFunction<String> have) {
        List<Line> out = new ArrayList<>();
        for (Check c : check(have)) if (!c.ok()) out.add(c.line());
        return out;
    }

    /** 골드·재료가 전부 있는가. */
    public boolean affordable(Purse purse) {
        return purse.gold() >= gold && missing(purse::count).isEmpty();
    }

    /**
     * 전부 있을 때만 골드와 모든 재료를 가져가고 true. 하나라도 모자라면 아무것도 건드리지 않고 false.
     * (골드를 먼저 빼고, 그게 실패하면 재료는 손대지 않는다 — 재료는 이미 개수를 확인했으므로 빠짐없이 빠진다.)
     */
    public boolean pay(Purse purse) {
        if (!affordable(purse)) return false;
        if (gold > 0 && !purse.takeGold(gold)) return false;
        for (Line l : lines) if (l.amount() > 0) purse.take(l.item(), l.amount());
        return true;
    }

    /** 맵 주머니 (테스트·시뮬레이션용): 골드는 {@code "$gold"} 키. */
    public static Purse mapPurse(Map<String, Long> bag) {
        return new Purse() {
            @Override public long gold() { return bag.getOrDefault("$gold", 0L); }

            @Override public int count(String item) { return (int) Math.min(Integer.MAX_VALUE, bag.getOrDefault(item, 0L)); }

            @Override public boolean takeGold(long amount) {
                if (gold() < amount) return false;
                bag.put("$gold", gold() - amount);
                return true;
            }

            @Override public void take(String item, int amount) {
                long left = bag.getOrDefault(item, 0L) - amount;
                if (left < 0) throw new IllegalStateException(item + " 모자람 — pay() 는 확인 뒤에만 뺀다");
                bag.put(item, left);
            }
        };
    }
}
