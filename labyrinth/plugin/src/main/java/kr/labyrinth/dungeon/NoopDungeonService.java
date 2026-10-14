package kr.labyrinth.dungeon;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import kr.labyrinth.Services;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.entity.Player;

/** 안전한 기본 구현: 월드 이름 비교만 하고, 입장은 안내 메시지로 거절. */
public class NoopDungeonService implements DungeonService {
    private final Services services;

    public NoopDungeonService(Services services) { this.services = services; }

    @Override
    public World world() { return Bukkit.getWorld(services.settings().worldName()); }

    @Override
    public boolean isLabyrinthWorld(World world) {
        return world != null && world.getName().equals(services.settings().worldName());
    }

    @Override
    public Optional<InstanceContext> currentInstance(Player player) { return Optional.empty(); }

    @Override
    public Collection<InstanceContext> instances() { return List.of(); }

    @Override
    public boolean enter(Player leader, int floor) {
        Log.notImplemented("DungeonService.enter");
        Text.error(leader, "미궁 입장 기능이 아직 준비되지 않았습니다.");
        return false;
    }

    @Override
    public void leave(Player player) { Log.notImplemented("DungeonService.leave"); }

    @Override
    public void endInstance(String instanceId) {}
}
