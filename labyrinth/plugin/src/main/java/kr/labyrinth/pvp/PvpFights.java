package kr.labyrinth.pvp;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 'PvP 전투 중' 기록 (pvp_spec §8) — 순수 로직. 다른 파티 플레이어에게 피해를 주거나 받으면 {@link #mark}.
 * 마지막 PvP 피해에서 combatSeconds 안이면 전투 중, 그보다 오래 조용하면 다음 피해부터 새 전투(긴 싸움 시간이 0 부터).
 */
public final class PvpFights {

    private record Fight(long start, long last) {}

    private final Map<UUID, Fight> fights = new ConcurrentHashMap<>();

    public void mark(UUID u, long now, double combatSeconds) {
        long window = (long) (combatSeconds * 1000);
        fights.compute(u, (k, f) -> f == null || now - f.last() > window ? new Fight(now, now) : new Fight(f.start(), now));
    }

    public boolean inCombat(UUID u, long now, double combatSeconds) {
        Fight f = fights.get(u);
        return f != null && now - f.last() <= (long) (combatSeconds * 1000);
    }

    /** 이번 전투가 이어진 시간(초). 전투 중이 아니면 0. */
    public double seconds(UUID u, long now, double combatSeconds) {
        Fight f = fights.get(u);
        if (f == null || now - f.last() > (long) (combatSeconds * 1000)) return 0;
        return (now - f.start()) / 1000.0;
    }

    public void forget(UUID u) { fights.remove(u); }

    /** 끝난 전투 지우기. */
    public void prune(long now, double combatSeconds) {
        long window = (long) (combatSeconds * 1000);
        fights.values().removeIf(f -> now - f.last() > window);
    }

    public void clear() { fights.clear(); }
}
