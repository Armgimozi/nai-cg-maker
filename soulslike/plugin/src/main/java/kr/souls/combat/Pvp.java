package kr.souls.combat;

import com.destroystokyo.paper.event.player.PlayerPostRespawnEvent;
import kr.souls.Souls;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerTeleportEvent;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 플레이어끼리 맞는가 (5.7). 세계 설정의 PvP 가 켜졌을 때만, 그리고 맞는 사람이:
 * <ul>
 *   <li>출신을 골랐고 (출신이 없는 사람은 맞지 않는다, 5.10),</li>
 *   <li>일어선 직후가 아니고 (접속·부활·명령 순간이동 뒤 pvp.respawn-grace 틱. 진주·후렴 과일 순간이동은 세지 않는다),</li>
 *   <li>쉬는 중이거나 우리 창 (Dialog) 을 보고 있지 않을 때 (친구끼리 겨룰 때 창 앞에서 맞지 않게, 검토 pvp-friends).</li>
 * </ul>
 * 끔일 때 막는 길은 PvpGuard, 켬일 때의 피해 계산은 DamageHook.
 */
public final class Pvp implements Listener {
    private final Souls plugin;
    /** 사람마다 보호가 끝나는 틱 */
    private final Map<UUID, Long> graceUntil = new HashMap<>();

    public Pvp(Souls plugin) {
        this.plugin = plugin;
    }

    /** 세계 설정의 PvP 가 켜졌나 (설정이 없으면 pvp.default). */
    public boolean enabled() {
        var s = plugin.worldState() == null ? null : plugin.worldState().get();
        return s != null ? s.pvp() : plugin.cfg().pvp.def();
    }

    /** attacker 가 victim 을 해칠 수 있나. 같은 사람이면 늘 참 (자기 자신은 PvP 가 아니다). */
    public boolean allowed(Player attacker, Player victim) {
        if (attacker == null || victim == null || attacker.equals(victim)) return true;
        return enabled() && plugin.profiles().of(attacker).born() && protectedWhy(victim) == null;
    }

    /** 맞지 않는 까닭 (unborn | grace | dialog | rest), 맞을 수 있으면 null. */
    public String protectedWhy(Player victim) {
        if (!plugin.profiles().of(victim).born()) return "unborn";
        Long until = graceUntil.get(victim.getUniqueId());
        if (until != null && plugin.ticker().now() < until) return "grace";
        if (plugin.ui().open(victim)) return "dialog";
        return null;
    }

    public void grace(Player p) {
        graceUntil.put(p.getUniqueId(), plugin.ticker().now() + plugin.cfg().pvp.respawnGrace());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        grace(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(PlayerPostRespawnEvent e) {
        grace(e.getPlayer());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        PlayerTeleportEvent.TeleportCause c = e.getCause();
        if (c == PlayerTeleportEvent.TeleportCause.PLUGIN || c == PlayerTeleportEvent.TeleportCause.COMMAND) grace(e.getPlayer());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        graceUntil.remove(e.getPlayer().getUniqueId());
    }
}
