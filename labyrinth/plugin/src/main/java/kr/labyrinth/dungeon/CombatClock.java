package kr.labyrinth.dungeon;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 공략 중 마지막 피해 시각 — '싸우는 중'(10초 안에 맞음) 판정에 쓴다 ({@link ExitCast} 퇴장 시전 ·
 * 싸우는 중 접속 끊김 {@code DeathPenaltyRules.combatQuit}). 순수 자료 (Bukkit 없음, 시험할 수 있게).
 *
 * <ul>
 *   <li>공략 참가자가 미궁 월드 안에서 받은 피해만 센다 — 입장 준비 중 마을·야생에서 맞은 것은 미궁 전투가 아니다.</li>
 *   <li>공략을 떠나면(퇴장·귀환·공략 끝) · 쓰러지면 지운다 — 앞 공략에서 맞은 것이 다음 공략으로 넘어가지 않게,
 *       부활한 뒤 쓰러지기 전 피해로 다시 '싸우는 중' 이 되지 않게.</li>
 *   <li>보통 접속 끊김(싸우는 중 아님)에는 남긴다 — 끊고 바로 다시 들어와 곧장 나가는 길을 만들지 않게.</li>
 * </ul>
 */
final class CombatClock {

    private final Map<UUID, Long> last = new ConcurrentHashMap<>();

    /** 피해를 받음. 공략 중 · 미궁 월드 안일 때만 적는다. */
    void hurt(UUID u, boolean inRun, boolean labyrinthWorld, long now) {
        if (u != null && inRun && labyrinthWorld) last.put(u, now);
    }

    /** 마지막 피해 시각 (없으면 -1). */
    long last(UUID u) { return u == null ? -1L : last.getOrDefault(u, -1L); }

    /** 마지막 피해에서 지난 ms (없으면 -1. 시계가 뒤로 가 음수가 되면 그대로 — 싸우는 중이 아닌 것으로 본다). */
    long since(UUID u, long now) {
        long l = last(u);
        return l < 0 ? -1 : now - l;
    }

    /** 싸우는 중인가 (마지막 피해 10초 안 — {@link kr.labyrinth.core.DeathPenaltyRules#inCombat}). */
    boolean inCombat(UUID u, long now) { return kr.labyrinth.core.DeathPenaltyRules.inCombat(since(u, now)); }

    void forget(UUID u) {
        if (u != null) last.remove(u);
    }

    void clear() { last.clear(); }
}
