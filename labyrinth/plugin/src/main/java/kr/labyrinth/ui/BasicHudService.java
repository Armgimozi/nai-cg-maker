package kr.labyrinth.ui;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.DerivedStats;
import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

/**
 * 기본 HUD: 미궁 월드(또는 전투 중)에서 0.5초마다 텍스트 액션바 "❤ HP ✦ MP Lv". 보스바는 Adventure 그대로.
 * ui 담당 구현(커스텀 폰트 바)이 대체한다.
 */
public class BasicHudService implements HudService {

    protected final Services services;
    private final Map<UUID, Map<String, BossBar>> bars = new ConcurrentHashMap<>();
    private final Map<UUID, Long> overrideUntil = new ConcurrentHashMap<>();
    private BukkitTask task;

    public BasicHudService(Services services) { this.services = services; }

    public void start() {
        stop();
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 20L, 10L);
    }

    public void stop() {
        if (task != null) task.cancel();
        task = null;
        bars.forEach((u, m) -> {
            Player p = Bukkit.getPlayer(u);
            if (p != null) m.values().forEach(p::hideBossBar);
        });
        bars.clear();
    }

    private void tick() {
        long now = System.currentTimeMillis();
        for (Player p : Bukkit.getOnlinePlayers()) {
            Long until = overrideUntil.get(p.getUniqueId());
            if (until != null && until > now) continue;
            if (!services.dungeon().isInLabyrinth(p)) continue;
            p.sendActionBar(defaultLine(p));
        }
    }

    protected Component defaultLine(Player p) {
        DerivedStats s = services.stats().get(p);
        PlayerData d = services.data().get(p);
        double hp = services.stats().currentHp(p);
        double mp = services.classes().mana(p);
        return Text.mm("<#ff5f6d>❤ <white>" + Text.num(hp) + "<gray>/" + Text.num(s.maxHp())
                + "   <#6fc3ff>✦ <white>" + Text.num(mp) + "<gray>/" + Text.num(s.maxMp())
                + "   <#ffd84f>Lv." + d.level() + "   <#f2c14e>⛃ " + Text.num(d.gold()));
    }

    @Override
    public void showBossBar(Player player, String key, BossBar bar) {
        Map<String, BossBar> m = bars.computeIfAbsent(player.getUniqueId(), u -> new HashMap<>());
        BossBar old = m.put(key, bar);
        if (old != null && old != bar) player.hideBossBar(old);
        player.showBossBar(bar);
    }

    @Override
    public void hideBossBar(Player player, String key) {
        Map<String, BossBar> m = bars.get(player.getUniqueId());
        if (m == null) return;
        BossBar old = m.remove(key);
        if (old != null) player.hideBossBar(old);
    }

    @Override
    public void actionBar(Player player, Component text, int ticks) {
        overrideUntil.put(player.getUniqueId(), System.currentTimeMillis() + ticks * 50L);
        player.sendActionBar(text);
    }

    @Override
    public void refresh(Player player) {}
}
