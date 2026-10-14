package kr.labyrinth.mobs;

import java.util.Optional;
import kr.labyrinth.core.Log;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/** 안전한 기본 구현: NPC 없음. */
public class NoopNpcService implements NpcService {
    @Override
    public Entity place(String npcId, Location loc) {
        Log.notImplemented("NpcService.place");
        return null;
    }

    @Override
    public boolean remove(String npcId) { return false; }

    @Override
    public Optional<String> npcIdOf(Entity entity) { return Optional.empty(); }

    @Override
    public void interact(Player player, String npcId) { Log.notImplemented("NpcService.interact"); }

    @Override
    public Entity spawnTemporary(String npcId, Location loc) {
        Log.notImplemented("NpcService.spawnTemporary");
        return null;
    }
}
