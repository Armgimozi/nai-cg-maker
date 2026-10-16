package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * 가방 자리 계산 (순수). 수확은 가방에 바로 들어가고, 다 들어갈 자리가 없으면 캐지지도 비워지지도 않는다 (계약 §2.3).
 * 칸 = (같은 물건 열쇠, 개수, 한 칸 최대). 빈 칸은 key == null.
 */
public final class BagFit {

    private BagFit() {}

    public record Slot(String key, int amount, int max) {}

    public record Add(String key, int amount, int max) {}

    /** adds 가 모두 들어가는가 (겹칠 수 있는 칸 먼저, 그다음 빈 칸 — 바닐라 addItem 과 같은 차례). */
    public static boolean fits(List<Slot> slots, List<Add> adds) {
        List<int[]> s = new ArrayList<>();
        List<String> keys = new ArrayList<>();
        for (Slot sl : slots) {
            keys.add(sl == null ? null : sl.key());
            s.add(new int[] {sl == null || sl.key() == null ? 0 : sl.amount(), sl == null ? 64 : Math.max(1, sl.max())});
        }
        for (Add a : adds) {
            int left = a.amount();
            if (left <= 0) continue;
            for (int i = 0; i < s.size() && left > 0; i++) {
                if (keys.get(i) != null && Objects.equals(keys.get(i), a.key())) {
                    int room = Math.max(0, Math.min(s.get(i)[1], a.max()) - s.get(i)[0]);
                    int put = Math.min(room, left);
                    s.get(i)[0] += put;
                    left -= put;
                }
            }
            for (int i = 0; i < s.size() && left > 0; i++) {
                if (keys.get(i) == null) {
                    keys.set(i, a.key());
                    int put = Math.min(Math.max(1, a.max()), left);
                    s.get(i)[0] = put;
                    s.get(i)[1] = Math.max(1, a.max());
                    left -= put;
                }
            }
            if (left > 0) return false;
        }
        return true;
    }
}
