package kr.labyrinth.mobs;

import java.util.Collection;
import java.util.Optional;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Entity;

/**
 * 커스텀 몹 스폰·틱·AI·스킬 (소유: mobs+npc 담당). 기본 구현 {@link NoopMobService}.
 * 구현은 사망 시 보상(경험치·골드·루팅)을 지급하고 {@code event.MobKillEvent} 를 발생시킨다.
 */
public interface MobService {

    /**
     * mobs.yml 의 mobId 를 loc 에 스폰. ctx 의 난이도·파티 배율로 HP/피해를 키운다(ctx null = 솔로·서버 난이도).
     * @return 스폰된 몹, 정의가 없거나 실패하면 null
     */
    CustomMob spawn(String mobId, Location loc, InstanceContext ctx);

    /** 엔티티(히트박스 또는 모델 파트)로 커스텀 몹 찾기. 보스는 {@code BossService#byEntity}. */
    Optional<CustomMob> byEntity(Entity entity);

    /** 인스턴스에 살아 있는 몹 (instanceId null = 전체). */
    Collection<CustomMob> alive(String instanceId);

    /** 인스턴스의 몹 전부 제거 (보상 없음). */
    void removeAll(String instanceId);
}
