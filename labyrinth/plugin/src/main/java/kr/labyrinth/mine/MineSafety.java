package kr.labyrinth.mine;

import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * 광산 안전 (계약 §2.2, R §2-2) — 다른 패키지가 부르는 한 줄 검사. 광산 월드 안의 플레이어는 어떤 경로로도 피해를 받지 않는다:
 * {@code combat.DamageService} (스킬·지속 피해가 setHealth 로 들어오는 길) · 상태 이상 진입점 ·
 * {@code TargetFilter.inSafeZone} · PvP 게임 규칙 · 바닐라 EntityDamageEvent (MineListener).
 * config {@code mine.safe: false} 면 끈다 (기본 켬).
 */
public final class MineSafety {

    private MineSafety() {}

    /** 그 월드가 광산 월드인가 (api 가 없으면 이름으로). */
    public static boolean inMine(MineApi api, World world) {
        if (world == null) return false;
        return api != null ? api.isMineWorld(world) : MineNames.WORLD.equals(world.getName());
    }

    public static boolean inMine(MineApi api, Location l) {
        return l != null && inMine(api, l.getWorld());
    }

    /** 이 엔티티(플레이어)를 광산이 지키는가 — 피해·해로운 효과 0. */
    public static boolean protects(MineApi api, Entity e) {
        return e instanceof Player && inMine(api, e.getWorld()) && (api == null || api.safe());
    }
}
