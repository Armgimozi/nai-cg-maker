package kr.labyrinth.core;

import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;

/**
 * 인벤세이브 (config.yml death) — 야생·마을·네더·엔드 어디서 죽든(PvP 포함) 소지품과 바닐라 경험치 레벨을 지키고
 * 아무것도 떨구지 않는다. 미궁 월드 안의 죽음은 {@code dungeon.DungeonManager} 가 먼저 처리한다
 * (공략 중이면 죽음을 취소하고 쓰러짐·관전, 그 밖에는 이 설정과 상관없이 {@link #apply} 로 언제나 보존).
 * pvp 모듈은 죽음 메시지만 바꾸므로 PvP 로 죽어도 같은 규칙이다.
 * <p>0.3.6.1 죽음 페널티({@link DeathPenalty}): 취소되지 않은 죽음은 어디서든 이번 레벨 경험치를 잃고, 안내는 부활한 뒤 채팅으로.
 * 미궁 공략 중 쓰러짐(취소된 죽음)은 {@code dungeon.Run#onMemberDeath} 가 따로 (경험치 + 가방 2~3칸 + 골드, 0.3.6.2).
 */
public final class DeathKeep implements Module, Listener {

    private final Services services;

    public DeathKeep(Services services) { this.services = services; }

    @Override
    public String name() { return "death"; }

    @Override
    public void enable() { Bukkit.getPluginManager().registerEvents(this, services.plugin()); }

    @Override
    public void disable() {
        HandlerList.unregisterAll(this);
        afterRespawn.clear();
    }

    /** 부활한 뒤 보낼 죽음 페널티 안내 (죽음 화면에서 나갔다 들어와도 부활할 때 보냄). */
    private final Map<UUID, List<String>> afterRespawn = new ConcurrentHashMap<>();

    /** 다른 플러그인·모듈이 드롭을 정한 뒤 마지막에 (취소된 죽음 = 미궁 쓰러짐은 건너뜀). */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDeath(PlayerDeathEvent e) {
        if (services.dungeon().isLabyrinthWorld(e.getPlayer().getWorld())) return; // 미궁 월드 = DungeonManager (언제나 보존)
        Settings.Death d = services.settings().death();
        apply(e, d.keepInventory(), d.keepLevel());
    }

    /** 죽음 페널티 — 모든 처리기가 끝난 뒤 정말 죽었을 때만 (미궁 공략 중 쓰러짐 = 취소됨 → 건너뜀, Run 이 따로). */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDeathPenalty(PlayerDeathEvent e) {
        Player p = e.getPlayer();
        List<String> lines = DeathPenalty.onRealDeath(services, p, services.dungeon().isLabyrinthWorld(p.getWorld()));
        if (!lines.isEmpty()) afterRespawn.put(p.getUniqueId(), lines);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onPostRespawn(PlayerPostRespawnEvent e) {
        List<String> lines = afterRespawn.remove(e.getPlayer().getUniqueId());
        if (lines != null) for (String line : lines) Text.send(e.getPlayer(), line);
    }

    /**
     * 죽음 이벤트에 보존 규칙을 적용한다 (DungeonManager 도 같은 함수). keepInventory 를 켜도 드롭 목록은 그대로 떨어지므로
     * 비워야 복제가 생기지 않는다. false 인 부분은 건드리지 않는다(바닐라 게임 규칙대로).
     */
    public static void apply(PlayerDeathEvent e, boolean keepInventory, boolean keepLevel) {
        if (keepInventory) {
            e.setKeepInventory(true);
            e.getDrops().clear();
        }
        if (keepLevel) {
            e.setKeepLevel(true);
            e.setDroppedExp(0);
        }
    }
}
