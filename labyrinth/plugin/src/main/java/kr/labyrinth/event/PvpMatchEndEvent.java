package kr.labyrinth.event;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;

/**
 * 파티 대 파티 매치가 끝났을 때 MatchService 가 발생. 칭호 PVP_WIN/PVP_STREAK/PVP_RATING/PVP_FIRST_WIN 판정의 입력.
 * ratings = 매치 후 개인 레이팅, streaks = 매치 후 개인 연승 수.
 */
public final class PvpMatchEndEvent extends Event {
    private static final HandlerList HANDLERS = new HandlerList();
    private final String matchId;
    private final List<UUID> winners;
    private final List<UUID> losers;
    private final Map<UUID, Integer> ratings;
    private final Map<UUID, Integer> streaks;

    public PvpMatchEndEvent(String matchId, List<UUID> winners, List<UUID> losers, Map<UUID, Integer> ratings,
                            Map<UUID, Integer> streaks) {
        this.matchId = matchId;
        this.winners = List.copyOf(winners);
        this.losers = List.copyOf(losers);
        this.ratings = Map.copyOf(ratings);
        this.streaks = Map.copyOf(streaks);
    }

    public String matchId() { return matchId; }
    public List<UUID> winners() { return winners; }
    public List<UUID> losers() { return losers; }
    public Map<UUID, Integer> ratings() { return ratings; }
    public Map<UUID, Integer> streaks() { return streaks; }

    @Override
    public HandlerList getHandlers() { return HANDLERS; }
    public static HandlerList getHandlerList() { return HANDLERS; }
}
