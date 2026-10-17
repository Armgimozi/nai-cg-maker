package kr.labyrinth.homes.play;

import kr.labyrinth.homes.PlotRole;

/**
 * 집 안 회복 규칙 (0.3.7, plan §0·설계 §8) — 순수.
 * 내 집·초대받은 집 높이 창 안 + {@code calm_seconds} 동안 피해 없음 + PvP 전투 아님 → 1초마다 최대 HP·MP 의 {@code home_regen} 비율.
 * 미궁에는 넘어가지 않는다 (주 월드 집터 안에서만 돈다 — 집터 밖·다른 월드는 {@code role} 이 NONE).
 */
public final class HomeRegen {

    private HomeRegen() {}

    /** 이번 초에 회복하나. role = 서 있는 집터에서의 자리 (집터 밖이면 NONE). */
    public static boolean eligible(PlotRole role, boolean dead, boolean inCombat, long nowMs, long lastHurtMs, int calmSeconds) {
        if (role == null || !role.builds() || dead || inCombat) return false;
        return nowMs - lastHurtMs >= Math.max(0, calmSeconds) * 1000L;
    }

    /** 1초 회복량: 최대 × 비율, 모자란 만큼까지 (가득이면 0). */
    public static double amount(double current, double max, double ratio) {
        if (max <= 0 || ratio <= 0) return 0;
        return Math.max(0, Math.min(max - current, max * ratio));
    }

    /** 빈 상태에서 가득 차는 데 걸리는 초 (비율 0 이면 -1). */
    public static int secondsToFull(double ratio) {
        if (ratio <= 0) return -1;
        return (int) Math.ceil(1.0 / ratio - 1e-9);
    }
}
