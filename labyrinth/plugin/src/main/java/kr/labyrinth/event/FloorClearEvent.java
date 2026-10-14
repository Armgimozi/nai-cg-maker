package kr.labyrinth.event;

import java.util.List;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;

/**
 * 층 보스 처치로 층을 돌파했을 때 DungeonService 가 발생 (메인 스레드). 칭호 FIRST_CLEAR/CLEAR/SOLO_CLEAR/
 * NO_DEATH_CLEAR/DIFFICULTY_CLEAR/SPEED_CLEAR 판정의 입력.
 *
 * @param members    클리어 시점 인스턴스 참가자 (사망·관전 포함)
 * @param partySize  입장 당시 인원
 * @param deaths     인스턴스 중 총 사망 수
 * @param seconds    입장~보스 처치까지 걸린 시간(초)
 * @param difficulty 서버 난이도 id
 */
public final class FloorClearEvent extends Event {
    private static final HandlerList HANDLERS = new HandlerList();
    private final String instanceId;
    private final int floor;
    private final List<Player> members;
    private final int partySize;
    private final int deaths;
    private final double seconds;
    private final String difficulty;

    public FloorClearEvent(String instanceId, int floor, List<Player> members, int partySize, int deaths,
                           double seconds, String difficulty) {
        this.instanceId = instanceId;
        this.floor = floor;
        this.members = List.copyOf(members);
        this.partySize = partySize;
        this.deaths = deaths;
        this.seconds = seconds;
        this.difficulty = difficulty;
    }

    public String instanceId() { return instanceId; }
    public int floor() { return floor; }
    public List<Player> members() { return members; }
    public int partySize() { return partySize; }
    public boolean solo() { return partySize <= 1; }
    public int deaths() { return deaths; }
    public double seconds() { return seconds; }
    public String difficulty() { return difficulty; }

    @Override
    public HandlerList getHandlers() { return HANDLERS; }
    public static HandlerList getHandlerList() { return HANDLERS; }
}
