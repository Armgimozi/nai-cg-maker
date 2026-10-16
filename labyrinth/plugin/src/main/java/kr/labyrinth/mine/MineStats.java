package kr.labyrinth.mine;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.bukkit.entity.Player;

/**
 * {@code /labadmin mine stats <이름>} — 서버가 켜진 뒤 캔 블록 수 (층별) · 최근 1시간. 보기만 하는 기록이다
 * (매크로 막기·알림·수확 상한은 없다, 계약 §0-2).
 */
final class MineStats {

    static final class Entry {
        final int[] perLevel = new int[7];
        final Deque<Long> recent = new ArrayDeque<>();
        int total;
    }

    private final Map<UUID, Entry> byPlayer = new ConcurrentHashMap<>();
    private volatile int serverTotal;

    void add(Player p, int level) {
        serverTotal++;
        if (p == null) return;
        Entry e = byPlayer.computeIfAbsent(p.getUniqueId(), k -> new Entry());
        synchronized (e) {
            e.total++;
            if (level >= 1 && level <= 6) e.perLevel[level]++;
            long now = System.currentTimeMillis();
            e.recent.addLast(now);
            while (!e.recent.isEmpty() && now - e.recent.peekFirst() > 3_600_000L) e.recent.pollFirst();
        }
    }

    Entry get(UUID id) { return byPlayer.get(id); }

    int lastHour(Entry e) {
        synchronized (e) {
            long now = System.currentTimeMillis();
            while (!e.recent.isEmpty() && now - e.recent.peekFirst() > 3_600_000L) e.recent.pollFirst();
            return e.recent.size();
        }
    }

    int serverTotal() { return serverTotal; }
}
