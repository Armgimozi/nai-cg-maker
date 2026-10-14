package kr.labyrinth.bosses;

import java.util.Collection;
import java.util.Optional;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Entity;

/**
 * 층 보스 (소유: bosses 담당 — impl/Floor01Boss..Floor10Boss). 기본 구현 {@link NoopBossService}.
 * 보스방 블록은 DungeonService 가 만들고, 보스 구현은 arena 키(기둥·플랫폼 등)만 그 위에 배치한다.
 */
public interface BossService {

    /**
     * floor 층 보스를 arenaCenter(보스방 바닥 중앙)에 소환. ctx 의 배율 적용.
     * @return 핸들, 실패/미구현이면 null (DungeonService 는 null 이면 층을 바로 클리어 처리해 진행이 막히지 않게 할 것)
     */
    BossHandle spawnBoss(int floor, Location arenaCenter, InstanceContext ctx);

    Optional<BossHandle> byEntity(Entity entity);

    Collection<BossHandle> active();

    /** 인스턴스의 보스전 강제 종료. */
    void endAll(String instanceId);
}
