package kr.souls.skill;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** 엔티티별 스킬 재사용 대기시간. 서버가 꺼지면 초기화된다. */
public final class Cooldowns {
    private final Map<UUID, Map<String, Long>> map = new HashMap<>();

    public long remainingMs(UUID id, String key) {
        Map<String, Long> m = map.get(id);
        if (m == null) return 0;
        Long until = m.get(key);
        if (until == null) return 0;
        return Math.max(0, until - System.currentTimeMillis());
    }

    public boolean ready(UUID id, String key) {
        return remainingMs(id, key) <= 0;
    }

    public void set(UUID id, String key, double seconds) {
        map.computeIfAbsent(id, k -> new HashMap<>()).put(key, System.currentTimeMillis() + (long) (seconds * 1000));
    }

    public void clear(UUID id) {
        map.remove(id);
    }
}
