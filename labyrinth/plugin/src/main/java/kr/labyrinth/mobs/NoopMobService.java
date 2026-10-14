package kr.labyrinth.mobs;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import kr.labyrinth.core.Log;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Location;
import org.bukkit.entity.Entity;

/** 안전한 기본 구현: 아무것도 스폰하지 않는다. */
public class NoopMobService implements MobService {
    @Override
    public CustomMob spawn(String mobId, Location loc, InstanceContext ctx) {
        Log.notImplemented("MobService.spawn");
        return null;
    }

    @Override
    public Optional<CustomMob> byEntity(Entity entity) { return Optional.empty(); }

    @Override
    public Collection<CustomMob> alive(String instanceId) { return List.of(); }

    @Override
    public void removeAll(String instanceId) {}
}
