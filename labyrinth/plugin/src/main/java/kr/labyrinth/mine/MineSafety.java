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
 * <p>
 * 0.3.7 주인 결정 "광산 PVP 키자": 하나만 열린다 — <b>다른 파티 플레이어가 PvP 구역(승강기 홀 밖)에 선 플레이어에게</b> 주는 피해.
 * {@link #protects(MineApi, Entity, Entity)} 에 때린 사람을 넘기면 {@link MineApi#pvpAllows} 가 판정한다 (PvP 규칙 isEnemy 그대로).
 * 떨어짐·불·몹·환경·{@code /kill} 은 그대로 없다.
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

    /** 이 엔티티(플레이어)를 광산이 지키는가 — 피해·해로운 효과 0 (때린 사람을 모를 때 · PvP 아님). */
    public static boolean protects(MineApi api, Entity e) {
        return e instanceof Player && inMine(api, e.getWorld()) && (api == null || api.safe());
    }

    /**
     * 0.3.7: source 가 target 에게 주는 피해·해로운 효과를 광산이 막는가. {@link #protects(MineApi, Entity)} 와 같고, 다만
     * source 가 다른 플레이어이고 {@link MineApi#pvpAllows} (광산 PvP 켜짐 · 두 사람 PvP 구역 · 다른 파티) 면 막지 않는다.
     */
    public static boolean protects(MineApi api, Entity target, Entity source) {
        if (!protects(api, target)) return false;
        return !(api != null && source instanceof Player a && target instanceof Player v && !a.equals(v) && api.pvpAllows(a, v));
    }

    /** 0.3.7: 광산 월드의 그 자리가 PvP 금지인가 (광산 PvP 꺼짐 · 안전 구역 · 층 상자 밖). 광산 월드 밖이면 false (광산 규칙 아님). */
    public static boolean noPvp(MineApi api, Location l) {
        return inMine(api, l) && (api == null || api.pvpSafeAt(l));
    }
}
