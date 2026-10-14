package kr.labyrinth.mobs;

import kr.labyrinth.combat.HealthPool;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

/**
 * 살아 있는 커스텀 몹 핸들 (mobs 담당 구현). 바닐라 엔티티(히트박스) + 모델 리그 + 자체 HP 풀.
 * 보스 핸들({@code bosses.BossHandle})도 이 인터페이스를 확장한다.
 */
public interface CustomMob extends HealthPool {

    /** mobs.yml / bosses.yml 정의 id. */
    String id();

    /** 표시 이름 (MiniMessage). */
    String displayName();

    /** 판정용 바닐라 엔티티. */
    @Override
    LivingEntity entity();

    /** 소속 인스턴스 (관리자 소환 등 인스턴스 밖이면 null). */
    InstanceContext instance();

    /** 기본 공격 피해 (난이도·파티 배율 적용 후). 스킬은 이 값 × 배율. */
    double damage();

    default Location location() { return entity().getLocation(); }

    /** 위협(어그로) 추가 (GDD §8.5). */
    void addThreat(Player player, double amount);

    /** 도발: seconds 동안 강제로 player 를 노린다. */
    void taunt(Player player, double seconds);

    /** 현재 공격 대상 (없으면 null). */
    Player target();

    /** 보상 없이 즉시 제거 (인스턴스 정리·관리자 명령). */
    void remove();
}
