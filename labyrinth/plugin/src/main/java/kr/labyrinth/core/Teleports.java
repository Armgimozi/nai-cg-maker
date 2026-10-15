package kr.labyrinth.core;

import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.event.player.PlayerTeleportEvent;

/**
 * 플레이어 순간이동 — <b>다른 월드로 옮길 때는 반드시 이것</b>을 쓴다.
 * Paper 26.3 은 탑승물(어깨·등 장식 {@code items.ArmorCosmetics}, 표식 디스플레이 등)이 있는 플레이어의 월드 간
 * {@code teleport} 를 이벤트도 없이 거부(false)한다 (CraftPlayer#teleport0). 그래서 월드가 다르면 탑승물을 먼저 내린다
 * — 장식은 PlayerChangedWorldEvent 뒤 다음 갱신 때 새 월드에서 다시 생긴다. 같은 월드 안 순간이동은 탑승물이 그대로
 * 따라오므로 아무것도 내리지 않는다.
 */
public final class Teleports {

    private Teleports() {}

    public static boolean to(Player p, Location to) {
        return to(p, to, PlayerTeleportEvent.TeleportCause.PLUGIN);
    }

    public static boolean to(Player p, Location to, PlayerTeleportEvent.TeleportCause cause) {
        if (p == null || to == null || to.getWorld() == null) return false;
        if (crossWorld(p, to) && !p.getPassengers().isEmpty()) p.eject();
        return p.teleport(to, cause);
    }

    /** 다른 월드로 가는가. */
    public static boolean crossWorld(Player p, Location to) {
        return to.getWorld() != null && !to.getWorld().equals(p.getWorld());
    }
}
