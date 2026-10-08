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
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerRespawnEvent;

/**
 * 죽음 (5.5, 5.6). M0 판: 인벤토리는 그대로, 떨굼·경험치 없음, 채팅 사망 알림 없음, 사망 화면 밑 문구 비움.
 * 바닐라 사망 화면을 그대로 쓰고 (immediate_respawn=false), 피처럼 붉은 "YOU DIED" 는 한 번만 보인다 (사용자 결정 3).
 * 자리는 셋 (5.6, config.yml death.*): 서서히 나타나는 판 (screen-fade, 기본) 은 죽는 순간 사망 화면 문구
 * (deathScreenMessageOverride) 에 띠와 글자를 souls:death 그림 글자 한 줄로 보내고, 글자색에 죽은 게임 시각을 실어 글꼴 셰이더가
 * 다크 소울처럼 서서히 나타나게 한다. 사망 화면 제목 판은 리소스팩이 바꾼 deathScreen.title 이 YOU DIED 이고 플러그인은 아무것도
 * 보내지 않는다. death.title: true 면 화면 한가운데에 화면 제목으로 크게 띄우고 일어설 때까지 남긴다 (사망 화면의 붉은 덧칠 밑에
 * 그려져 조금 어둡다). 팩은 같은 config.yml 을 읽어 만들고 (gen_pack), 플러그인은 문구 줄을 보낼지를 설정이 아니라 jar 안 팩의
 * 사망 화면 제목이 비었는지로 정한다: 설정과 팩이 어긋나도 YOU DIED 가 둘이 되지 않는다 (/souls check 가 어긋남을 알린다).
 * 그림 글자가 없으면 붉은 일반 글씨로 대신한다. 단추 글(deathScreen.*)은 리소스팩이 바꾼다.
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
        // 채팅 알림은 막고, 사망 화면 밑 문구는 비운다 (이것은 show_death_messages=true 일 때만 듣는다).
        // 서서히 나타나는 판이면 그 문구 줄이 YOU DIED 다
        e.deathMessage(null);
        Player p = e.getEntity();
        long gameTime = p.getWorld().getGameTime();
        plugin.test(p, "DEATH cause=" + e.getDamageSource().getDamageType().getKey().getKey() + " t=" + plugin.ticker().now());
        if (fadeMode()) {
            Component line = Glyphs.deathFadeLine(gameTime);
            boolean glyph = line != null;
            e.deathScreenMessageOverride(glyph ? line : fallbackTitle(p));
            plugin.test(p, "TITLE mode=fade glyph=" + glyph + " gt=" + Math.floorMod(gameTime, 24000L));
            return;
        }
        e.deathScreenMessageOverride(Component.empty());
        if (!plugin.cfg().death.title()) {
            plugin.test(p, "TITLE mode=screen");
            return;
        }
        // 사망 화면이 열린 다음에 보낸다
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline()) showTitle(p, false);
        });
    }

    /**
     * 서서히 나타나는 판인가: 화면 제목 판 (death.title) 이 아니고 jar 안 팩의 사망 화면 제목이 비었다 (팩이 YOU DIED 를 문구 줄에
     * 맡겼다, gen_pack fade). 설정 death.screen-fade 는 팩을 만들 때 읽힌다.
     */
    private boolean fadeMode() {
        return !plugin.cfg().death.title() && plugin.pack().deathTitleBlank();
    }

    /**
     * 죽은 채 나갔다 들어오면 사망 화면이 다시 열린다. 화면 제목을 쓰는 판이면 그 제목도 다시 띄운다. 서서히 나타나는 판은
     * YOU DIED 가 죽는 순간의 문구 줄에만 있어 다시 열린 사망 화면에는 없으므로, 바로 일으켜 세운다 (화톳불에서 깨어난다).
     */
    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        boolean title = plugin.cfg().death.title();
        if (!title && !fadeMode()) return;
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline() || !p.isDead()) return;
            if (title) {
                showTitle(p, false);
            } else {
                plugin.test(p, "DEATH_REJOIN respawn");
                p.spigot().respawn();
            }
        }, 10);
    }

    /** 그림 글자가 없을 때의 YOU DIED: lang 의 death.title 을 death.fallback-color 로. */
    private Component fallbackTitle(Player p) {
        TextColor col;
        try {
            col = TextColor.color(Fx.color(plugin.cfg().death.fallbackColor()).asRGB());
        } catch (RuntimeException ex) {
            col = Glyphs.GORE3;
        }
        return Lang.c(p, "death.title").color(col).decoration(TextDecoration.BOLD, false);
    }

    /** 큰 제목 "YOU DIED". force 면 death.title 이 꺼져 있어도 띄운다 (/soulstest title 로 그림 글자를 볼 때). */
    public void showTitle(Player p, boolean force) {
        Config.DeathCfg c = plugin.cfg().death;
        if (!c.title() && !force) return;
        Component title = Glyphs.line(c.titleGlyphs());
        boolean glyph = title != null;
        if (!glyph) title = fallbackTitle(p);
        plugin.titles().big(p, plugin.ticker().now(), title, Component.empty(), c.fadeIn(), c.stay(), c.fadeOut());
        plugin.test(p, "TITLE mode=plugin glyph=" + glyph + " names=" + c.titleGlyphs().replace(' ', ','));
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
