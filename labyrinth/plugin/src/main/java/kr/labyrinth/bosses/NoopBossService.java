package kr.labyrinth.bosses;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import kr.labyrinth.core.Log;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Entity;

/** 안전한 기본 구현: 보스 없음 (spawnBoss → null). */
public class NoopBossService implements BossService {
    @Override
    public BossHandle spawnBoss(int floor, Location arenaCenter, InstanceContext ctx) {
        Log.notImplemented("BossService.spawnBoss");
        return null;
    }

    @Override
    public Optional<BossHandle> byEntity(Entity entity) { return Optional.empty(); }

    @Override
    public Collection<BossHandle> active() { return List.of(); }

    @Override
    public void endAll(String instanceId) {}
}
