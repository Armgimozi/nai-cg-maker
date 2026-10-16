package kr.labyrinth.items;

import kr.labyrinth.core.ArmorLooks;

/**
 * 가죽 4부위 — 구르기 입력 (look_spec §1.3, 순수 — 단위 테스트 대상). 사람마다 하나.
 * <ul>
 *   <li>웅크리기 키를 누를 때마다 {@link #onSneak}. 앞 누름에서 {@code double_tap} 초 안에 또 누르면(누름-뗌-누름) 구르기 후보.</li>
 *   <li>못 구르는 때: 땅 위가 아님 · 막힘(물속·탈것·활공·비행·기절·속박·빙결·끔) · 웅크리기 조합 스킬을 쓴 뒤 {@code combo_guard} 초 안 ·
 *       재사용 대기 중. 침묵이어도 구를 수 있다(스킬이 아니다).</li>
 *   <li>한 번 판정한 두 번째 누름은 다음 두 번 누름의 첫 누름이 되지 않는다 (세 번 눌러 두 번 구르지 않게).</li>
 * </ul>
 */
public final class TumbleInput {

    public enum Result { NONE, TUMBLE, COOLDOWN }

    private long lastPress = Long.MIN_VALUE;
    private long readyAt = Long.MIN_VALUE;

    /**
     * @param now        지금 (ms)
     * @param onGround   땅 위인가
     * @param blocked    물속·탈것·활공·기절·속박·빙결·끔 중 하나인가
     * @param lastComboAt 웅크리기 조합 스킬을 마지막으로 쓴 때 (ms, 없으면 Long.MIN_VALUE)
     */
    public Result onSneak(long now, boolean onGround, boolean blocked, long lastComboAt, ArmorLooks.Tumble cfg) {
        long window = Math.round(cfg.doubleTap() * 1000);
        boolean twice = lastPress != Long.MIN_VALUE && now - lastPress <= window && now >= lastPress;
        if (!twice) {
            lastPress = now;
            return Result.NONE;
        }
        lastPress = Long.MIN_VALUE;
        if (!onGround || blocked) return Result.NONE;
        if (lastComboAt != Long.MIN_VALUE && now - lastComboAt < Math.round(cfg.comboGuard() * 1000)) return Result.NONE;
        if (now < readyAt) return Result.COOLDOWN;
        readyAt = now + Math.round(cfg.cooldown() * 1000);
        return Result.TUMBLE;
    }

    /** 다시 구를 수 있게 되는 때 (ms). */
    public long readyAt() { return readyAt; }

    /** 재사용 대기 남은 시간 (초). */
    public double remaining(long now) { return readyAt == Long.MIN_VALUE ? 0 : Math.max(0, (readyAt - now) / 1000.0); }

    /**
     * 구르는 방향 (수평 단위 벡터 x, z)과 거리. 방향 키(앞·뒤·왼쪽·오른쪽)를 바라보는 방향에 맞춰 돌리고, 아무것도 안 누르면 뒤로 back_distance.
     * Minecraft 좌표: yaw 0 = +z(남쪽), 앞 = (−sin yaw, cos yaw), 왼쪽 = (cos yaw, sin yaw).
     * @return {x, z, 거리}
     */
    public static double[] direction(boolean forward, boolean backward, boolean left, boolean right, float yawDeg,
                                     ArmorLooks.Tumble cfg) {
        double f = (forward ? 1 : 0) - (backward ? 1 : 0);
        double s = (left ? 1 : 0) - (right ? 1 : 0);
        double dist = cfg.distance();
        if (f == 0 && s == 0) {
            f = -1;
            dist = cfg.backDistance();
        }
        double yaw = Math.toRadians(yawDeg);
        double fx = -Math.sin(yaw), fz = Math.cos(yaw);
        double lx = Math.cos(yaw), lz = Math.sin(yaw);
        double x = f * fx + s * lx, z = f * fz + s * lz;
        double len = Math.sqrt(x * x + z * z);
        if (len < 1e-9) return new double[] {0, 0, 0};
        return new double[] {x / len, z / len, dist};
    }

    /** 수평 속도 (블록/틱): 3.5칸 ≈ 1.05 — 거리에 비례. */
    public static double speedFor(double distance) { return 1.05 * distance / 3.5; }
}
