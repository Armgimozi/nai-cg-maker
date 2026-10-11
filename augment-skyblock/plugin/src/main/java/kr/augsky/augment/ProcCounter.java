package kr.augsky.augment;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 전투 효과를 확률 대신 'N번째 공격마다' 터뜨리려고 세는 횟수. 플레이어마다, 효과마다 따로 센다.
 * 운에 맡기지 않고 몇 번 더 때리면 터지는지 알 수 있게 하려는 것이다.
 * 서버 메모리에만 두며, 접속을 끊거나 관리자가 증강을 초기화하면 처음부터 다시 센다.
 */
public final class ProcCounter {
    private final Map<UUID, Map<String, Integer>> counts = new HashMap<>();

    /**
     * 한 번 센다. every 번째가 되면 true 를 돌려주고 0 부터 다시 센다.
     * every 가 1 이면 매번, 0 이하면 효과가 없는 것이므로 세지도 않는다.
     */
    public boolean hit(UUID id, String key, int every) {
        if (every <= 0) return false;
        if (every == 1) return true;
        Map<String, Integer> m = counts.computeIfAbsent(id, k -> new HashMap<>());
        int n = m.merge(key, 1, Integer::sum);
        // 장비를 바꿔 every 가 줄었을 수도 있으니 == 가 아니라 >= 로 본다
        if (n >= every) {
            m.remove(key);
            return true;
        }
        return false;
    }

    public void clear(UUID id) {
        counts.remove(id);
    }
}
