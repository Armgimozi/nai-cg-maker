package kr.labyrinth.ui;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.FoodLevelChangeEvent;
import org.bukkit.event.player.PlayerExpChangeEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.plugin.Plugin;

/**
 * 리소스팩이 바닐라 하트·허기·경험치 바를 숨기고 우리 HUD 가 대신 그리므로,
 * 보이지 않는 허기는 항상 가득 채워 두고 바닐라 경험치(가운데 초록 숫자)는 0 으로 둔다.
 * 레벨·경험치는 미궁 자체 시스템(LevelService)만 쓴다.
 */
final class VanillaHudListener implements Listener {

    private final Plugin plugin;

    VanillaHudListener(Plugin plugin) { this.plugin = plugin; }

    private static void normalize(Player p) {
        p.setFoodLevel(20);
        if (p.getLevel() != 0) p.setLevel(0);
        if (p.getExp() != 0f) p.setExp(0f);
    }

    void normalizeOnline() {
        for (Player p : Bukkit.getOnlinePlayers()) normalize(p);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) { normalize(e.getPlayer()); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerRespawnEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTask(plugin, () -> { if (p.isOnline()) normalize(p); });
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onFood(FoodLevelChangeEvent e) {
        if (e.getEntity() instanceof Player && e.getFoodLevel() < 20) e.setFoodLevel(20);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onExp(PlayerExpChangeEvent e) { e.setAmount(0); }
}
