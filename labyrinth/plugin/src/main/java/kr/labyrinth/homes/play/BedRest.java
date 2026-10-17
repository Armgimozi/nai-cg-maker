package kr.labyrinth.homes.play;

/**
 * 침대 쉬기 (0.3.7, plan §0) — 순수. 내 집 안 침대 우클릭 → {@code bed_rest.seconds} 초 (움직이거나 맞으면 끊김) → HP·MP 가득.
 * {@code cooldown_seconds} 에 한 번 (PlayerData ext {@code homes.rest_at}). 바닐라 침대 동작(리스폰 지점·잠)은 그대로 —
 * 밤에 누우면 서버가 몸을 침대로 옮기므로 자는 동안은 움직임으로 치지 않는다.
 */
public final class BedRest {

    private BedRest() {}

    /** 움직였다고 볼 거리 (블록, 수평). */
    public static final double MOVE_LIMIT = 0.35;

    public enum Step { WAIT, DONE, CANCELLED }

    /** 시작 때 자리와 시각. */
    public record Session(long startMs, double x, double y, double z) {}

    /** 이번 틱 결과. lastHurtMs = 마지막으로 맞은 때 (없으면 0). */
    public static Step tick(Session s, long nowMs, double x, double y, double z, boolean sleeping, long lastHurtMs, int seconds) {
        if (s == null) return Step.CANCELLED;
        if (lastHurtMs > s.startMs()) return Step.CANCELLED;
        if (!sleeping && moved(s, x, y, z)) return Step.CANCELLED;
        if (nowMs - s.startMs() >= Math.max(0, seconds) * 1000L) return Step.DONE;
        return Step.WAIT;
    }

    static boolean moved(Session s, double x, double y, double z) {
        double dx = x - s.x(), dz = z - s.z();
        return dx * dx + dz * dz > MOVE_LIMIT * MOVE_LIMIT || Math.abs(y - s.y()) > 0.6;
    }

    /** 0~1 진행 (막대). */
    public static double progress(Session s, long nowMs, int seconds) {
        if (s == null || seconds <= 0) return 1;
        return Math.max(0, Math.min(1, (nowMs - s.startMs()) / (seconds * 1000.0)));
    }

    /** 다시 쉴 수 있을 때까지 남은 ms (0 = 지금 됨). lastRestMs = 마지막으로 다 쉰 때 (없으면 0). */
    public static long cooldownLeftMs(long lastRestMs, long nowMs, int cooldownSeconds) {
        if (lastRestMs <= 0 || cooldownSeconds <= 0) return 0;
        long left = lastRestMs + cooldownSeconds * 1000L - nowMs;
        return Math.max(0, left);
    }
}
