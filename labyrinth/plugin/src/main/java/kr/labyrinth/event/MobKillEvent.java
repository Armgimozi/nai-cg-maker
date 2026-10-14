package kr.labyrinth.event;

import java.util.List;
import kr.labyrinth.mobs.CustomMob;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;

/**
 * 커스텀 몹(또는 보스)이 죽었을 때 MobService/BossService 가 발생시킨다 (메인 스레드).
 * killer = 막타 플레이어(없으면 null), participants = 보상을 받는 인스턴스 참가자.
 * 칭호(KILL/BOSS_KILL), 통계, 퀘스트 등이 듣는다.
 */
public final class MobKillEvent extends Event {
    private static final HandlerList HANDLERS = new HandlerList();
    private final CustomMob mob;
    private final Player killer;
    private final List<Player> participants;
    private final boolean boss;

    public MobKillEvent(CustomMob mob, Player killer, List<Player> participants, boolean boss) {
        this.mob = mob;
        this.killer = killer;
        this.participants = List.copyOf(participants);
        this.boss = boss;
    }

    public CustomMob mob() { return mob; }
    /** 몹 정의 id (mobs.yml / bosses.yml 키). */
    public String mobId() { return mob.id(); }
    public Player killer() { return killer; }
    public List<Player> participants() { return participants; }
    public boolean isBoss() { return boss; }

    @Override
    public HandlerList getHandlers() { return HANDLERS; }
    public static HandlerList getHandlerList() { return HANDLERS; }
}
