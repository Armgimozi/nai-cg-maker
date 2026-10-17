package kr.labyrinth.mine;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 광산 PvP '싸우는 중' 시계 (0.3.7) — 순수 자료 ({@code dungeon.CombatClock} 을 본뜸). 주인 말대로 10초 안에 <b>때렸거나 맞았으면</b>
 * 싸우는 중이다 ({@code DeathPenaltyRules.COMBAT_MS}, 미궁 퇴장 시전·귀환 주문서와 같은 10초). PvP 회복을 줄이는
 * {@code pvp.combat_seconds}(8초)와는 따로 둔다.
 * <ul>
 *   <li>{@link #mark}: 다른 파티 플레이어끼리 광산에서 규칙을 통과한 공격 (맞힘·피함 모두) — 때린 쪽과 맞은 쪽 둘 다</li>
 *   <li>{@link #hurt}: 실제로 피해가 들어감 — 시전·승강기 끊기에 쓴다 (맞은 쪽만, 싸우는 중으로도 셈)</li>
 *   <li>쓰러지거나 광산을 떠나면 지운다. 보통 접속 끊김에는 남긴다 (끊고 바로 다시 들어와 곧장 나가는 길을 막으려고 — 미궁과 같음).</li>
 * </ul>
 */
final class MineCombat {

    private final Map<UUID, Long> last = new ConcurrentHashMap<>();
    private final Map<UUID, Long> hurt = new ConcurrentHashMap<>();

    /** a 가 v 를 공격함 (규칙 통과). 둘 다 싸우는 중. */
    void mark(UUID a, UUID v, long now) {
        if (a != null) last.put(a, now);
        if (v != null) last.put(v, now);
    }

    /** v 가 피해를 받음 (0 보다 큼). 맞은 쪽만. */
    void hurt(UUID v, long now) {
        if (v == null) return;
        hurt.put(v, now);
        last.put(v, now);
    }

    /** 마지막 PvP 에서 지난 ms (없으면 -1. 시계가 뒤로 가 음수가 되면 그대로 — 싸우는 중이 아닌 것으로 본다). */
    long since(UUID u, long now) {
        Long l = u == null ? null : last.get(u);
        return l == null ? -1 : now - l;
    }

    /** 마지막으로 피해를 받은 시각 (없으면 -1). 시전 시작 뒤 이 값이 커지면 맞은 것이다. */
    long lastHurt(UUID u) {
        Long l = u == null ? null : hurt.get(u);
        return l == null ? -1 : l;
    }

    void forget(UUID u) {
        if (u == null) return;
        last.remove(u);
        hurt.remove(u);
    }

    void clear() {
        last.clear();
        hurt.clear();
    }
}
