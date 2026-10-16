package kr.labyrinth.items.unique;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;

/**
 * 띠별 다양성 (unique_spec §9.5·§9.8, review2 A11) — 무기 종류 대신 공격 방식(attack.style)으로 본다.
 * <ul>
 *   <li>(5레벨 띠, 방식)마다 빌드 방향 3개 이상</li>
 *   <li>같은 (띠, 방식, 획득처 종류, 숨은 Lv) 안에서 간격이 비슷한(0.2초 안) 무기끼리 같은 효과 없음.
 *       간격이 크게 다르면 다른 고름으로 본다(§9.5 "같은 효과가 두 번 나오는 곳은 대부분 획득처나 간격이 다르다" —
 *       31–35 몹·상자 Lv32 대도 0.90초·단검 0.45초의 찢는 치명, 36–40 대장간 Lv38 망치 0.75초·카타르 0.45초의 마력 흡수)</li>
 * </ul>
 */
class UniqueDiversityTest {

    static final double SIMILAR_INTERVAL = 0.2;

    @Test
    void everyBandAndStyleHasThreeDirections() {
        Map<String, Set<String>> dirs = new TreeMap<>();
        for (UniqueData.Entry e : UniqueData.all().values()) {
            dirs.computeIfAbsent(e.band() + " " + e.attack().style(), k -> new TreeSet<>()).add(e.direction());
        }
        List<String> few = new ArrayList<>();
        dirs.forEach((k, v) -> {
            if (v.size() < 3) few.add(k + " " + v);
        });
        assertTrue(dirs.size() >= 30, "띠 10 × 방식 3: " + dirs.keySet());
        assertTrue(few.isEmpty(), () -> "방향 3개 미만: " + few);
    }

    @Test
    void noSameEffectTwiceInTheSameSlot() {
        List<UniqueData.Entry> all = new ArrayList<>(UniqueData.all().values());
        List<String> dup = new ArrayList<>();
        for (int i = 0; i < all.size(); i++) {
            for (int j = i + 1; j < all.size(); j++) {
                UniqueData.Entry a = all.get(i), b = all.get(j);
                if (!a.effect().equals(b.effect()) || !a.band().equals(b.band()) || a.attack().style() != b.attack().style()) continue;
                if (a.level() != b.level() || !new TreeSet<>(a.sourceKinds()).equals(new TreeSet<>(b.sourceKinds()))) continue;
                if (Math.abs(a.attack().interval() - b.attack().interval()) >= SIMILAR_INTERVAL) continue;
                dup.add(a.weaponId() + " · " + b.weaponId() + " (" + a.effect() + ")");
            }
        }
        assertTrue(dup.isEmpty(), () -> "같은 자리 같은 효과: " + dup);
    }
}
