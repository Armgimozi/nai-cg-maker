package kr.labyrinth.bosses.impl;

/**
 * 위치 링버퍼 (GDD §8.2 {@code PositionHistory} — 되감기 메아리·시간 역류). Bukkit 무관: 좌표 5개 {x, y, z, yaw, pitch} 와 기록 틱.
 * interval 틱마다 {@link #record} 하면, capacity 개를 넘는 오래된 기록은 덮어쓴다.
 */
public final class PositionHistory {

    private final double[][] pos;
    private final long[] at;
    private int head;  // 다음에 쓸 칸
    private int size;

    /** @param capacity 보관할 기록 수 (예: 0.5초 간격 · 8초 = 16) */
    public PositionHistory(int capacity) {
        int n = Math.max(2, capacity);
        this.pos = new double[n][];
        this.at = new long[n];
    }

    /** 필요한 보관 수: ⌈seconds ÷ interval⌉ + 2 (최소 2). */
    public static int capacityFor(double seconds, double intervalSeconds) {
        if (intervalSeconds <= 0) return 2;
        return Math.max(2, (int) Math.ceil(seconds / intervalSeconds) + 2);
    }

    public void record(long tick, double x, double y, double z, float yaw, float pitch) {
        pos[head] = new double[]{x, y, z, yaw, pitch};
        at[head] = tick;
        head = (head + 1) % pos.length;
        if (size < pos.length) size++;
    }

    public int size() { return size; }

    public void clear() {
        head = 0;
        size = 0;
    }

    /** 가장 최근 기록 (없으면 null). */
    public double[] latest() {
        if (size == 0) return null;
        return pos[Math.floorMod(head - 1, pos.length)].clone();
    }

    /**
     * ticksAgo 틱 전(기준 now)에 가장 가까운 기록 — 그 시점 이전 기록 중 가장 최근 것, 그만큼 오래된 기록이 없으면 가장 오래된 기록.
     * 기록이 없으면 null.
     */
    public double[] ago(long now, long ticksAgo) {
        if (size == 0) return null;
        long want = now - Math.max(0, ticksAgo);
        double[] oldest = null;
        for (int i = 1; i <= size; i++) {
            int idx = Math.floorMod(head - i, pos.length);
            oldest = pos[idx];
            if (at[idx] <= want) return pos[idx].clone();
        }
        return oldest == null ? null : oldest.clone();
    }
}
