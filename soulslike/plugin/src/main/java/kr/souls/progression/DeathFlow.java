package kr.souls.progression;

import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import kr.souls.Config;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.hud.Glyphs;
import kr.souls.util.Fx;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerRespawnEvent;

/**
 * 죽음 (5.5, 5.6). M0 판: 인벤토리는 그대로, 떨굼·경험치 없음, 채팅 사망 알림 없음, 사망 화면 밑 문구 비움.
 * 바닐라 사망 화면을 그대로 쓰고 (immediate_respawn=false), 그 위 가운데에 피처럼 붉은 "YOU DIED" 를 크게 띄운다
 * (사용자 결정: 한국어 "사망했다" 대신). 글자는 리소스팩의 손으로 찍은 그림 글자(glyphs.yml)이고, 없으면 붉은 일반 글씨로 대신한다.
 * 사망 화면 자체의 제목·단추 글(deathScreen.*)은 리소스팩의 언어 파일이 바꾼다.
 * 혈흔, 소울 잃기, 적 되살리기, 화톳불 부활은 M2.
 */
public final class DeathFlow implements Listener {
    private final Souls plugin;

    public DeathFlow(Souls plugin) {
        this.plugin = plugin;
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onDeath(PlayerDeathEvent e) {
        if (!plugin.worlds().ours(e.getEntity().getWorld())) return;
        e.setKeepInventory(true);
        e.getDrops().clear();
        e.setKeepLevel(true);
        e.setDroppedExp(0);
        // 채팅 알림은 막고, 사망 화면 밑 문구는 비운다 (이것은 show_death_messages=true 일 때만 듣는다)
        e.deathMessage(null);
        e.deathScreenMessageOverride(Component.empty());
        Player p = e.getEntity();
        plugin.test(p, "DEATH cause=" + e.getDamageSource().getDamageType().getKey().getKey() + " t=" + plugin.ticker().now());
        // 사망 화면이 열린 다음에 보낸다
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline()) showTitle(p);
        });
    }

    /** 큰 제목 "YOU DIED" (/soulstest title 도 이것을 부른다). */
    public void showTitle(Player p) {
        Config.DeathCfg c = plugin.cfg().death;
        if (!c.title()) return;
        Component title = Glyphs.line(c.titleGlyphs());
        boolean glyph = title != null;
        if (!glyph) {
            TextColor col;
            try {
                col = TextColor.color(Fx.color(c.fallbackColor()).asRGB());
            } catch (RuntimeException ex) {
                col = Glyphs.BLOOD3;
            }
            title = Component.text(Lang.plain("death.title"), col).decoration(TextDecoration.BOLD, false);
        }
        plugin.titles().big(p, plugin.ticker().now(), title, Component.empty(), c.fadeIn(), c.stay(), c.fadeOut());
        plugin.test(p, "TITLE you_died glyph=" + glyph + " names=" + c.titleGlyphs().replace(' ', ','));
    }

    /** M0 에는 화톳불이 없어 시험 방에서 일어난다. */
    @EventHandler(priority = EventPriority.HIGH)
    public void onRespawn(PlayerRespawnEvent e) {
        if (!plugin.worlds().ours(e.getPlayer().getWorld()) && !plugin.worlds().ours(e.getRespawnLocation().getWorld())) return;
        e.setRespawnLocation(plugin.worlds().roomSpawn());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onPostRespawn(PlayerPostRespawnEvent e) {
        Player p = e.getPlayer();
        plugin.titles().clear(p);
        plugin.stamina().refill(p);
        plugin.test(p, "RESPAWN world=" + p.getWorld().getName() + " t=" + plugin.ticker().now());
    }
}
