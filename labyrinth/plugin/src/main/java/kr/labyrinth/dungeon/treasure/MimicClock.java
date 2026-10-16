package kr.labyrinth.dungeon.treasure;

/**
 * 미믹이 달아날 때까지 남은 시간 (순수, {@link MimicEncounter}). 시간은 <b>근처에 살아 있는 파티원이 있을 때만</b> 흐른다 —
 * 상자를 열고 멀리 가서 기다리기만 해서는 미믹이 달아나지 않는다(그 자리에 상자도 돌아오지 않음). 맞으면 남은 시간이 적어도
 * engagedMs 로 늘어난다(싸우는 도중에 사라지지 않게). 한 번에 흐르는 시간은 {@link #MAX_STEP_MS} 까지(서버 렉에 한꺼번에 줄지 않게).
 */
public final class MimicClock {

    /** 한 번 부를 때 흐를 수 있는 최대 시간(ms). */
    public static final long MAX_STEP_MS = 500;

    private final long engagedMs;
    private long remaining;
    private long last = Long.MIN_VALUE;

    public MimicClock(long lockMs, long engagedMs) {
        this.remaining = Math.max(1, lockMs);
        this.engagedMs = Math.max(0, engagedMs);
    }

    /**
     * @param now 지금(ms) · someoneNear 상자 자리 근처에 살아 있는 파티원이 있나 · hit 이번에 미믹이 맞았나
     * @return 시간이 다 됐나 (= 달아날 때)
     */
    public boolean tick(long now, boolean someoneNear, boolean hit) {
        long dt = last == Long.MIN_VALUE ? 0 : Math.max(0, Math.min(MAX_STEP_MS, now - last));
        last = now;
        if (hit) remaining = Math.max(remaining, engagedMs);
        if (someoneNear) remaining -= dt;
        return remaining <= 0;
    }

    /** 자가 진단: 지금 다 된 것으로. */
    public void expire() { remaining = 0; }

    /** 남은 시간(ms, 0 이하 = 다 됨). */
    public long remaining() { return remaining; }
}
