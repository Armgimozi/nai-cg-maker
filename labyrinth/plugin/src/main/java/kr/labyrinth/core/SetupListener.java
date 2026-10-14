package kr.labyrinth.core;

import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;

/**
 * 초기 설정 안내 (ARCHITECTURE §5): 서버 난이도가 비어 있으면 접속한 관리자에게 초기 설정 메뉴를 띄우고,
 * 일반 플레이어에게는 대기 안내. 입장 차단 자체는 DungeonService 가 {@code settings().isDifficultySet()} 로 검사.
 */
public final class SetupListener implements Module, Listener {

    private final Services services;

    public SetupListener(Services services) { this.services = services; }

    @Override
    public String name() { return "setup"; }

    @Override
    public void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        if (!services.settings().isDifficultySet()) {
            Log.warn("서버 난이도가 아직 정해지지 않았습니다. 처음 접속한 사람에게 초기 설정 창이 뜹니다 (op 아니어도 됨). (콘솔: labadmin setup <easy|normal|hard|nightmare>)");
        }
    }

    @Override
    public void disable() { HandlerList.unregisterAll(this); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        if (services.settings().isDifficultySet()) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (!p.isOnline() || services.settings().isDifficultySet()) return;
            if (ServerSetup.canSetDifficulty(p)) {
                services.menus().openSetup(p);
            } else {
                Text.send(p, "<gray>서버 관리자가 아직 미궁 난이도를 정하지 않았습니다. 잠시만 기다려 주세요.");
            }
        }, 60L);
    }
}
