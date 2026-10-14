package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.SplittableRandom;

/**
 * 6층 기믹 `lights_out` 의 순수 로직: n×n 격자, 칸을 누르면 자신과 상하좌우가 반전.
 * 시작 배치는 "전부 켜짐" 에서 서로 다른 칸을 k 번 누른 상태 → 같은 칸들을 다시 누르면 반드시 풀린다.
 */
public final class LightsOutGrid {

    private final int n;
    private final boolean[] on;

    public LightsOutGrid(int n) {
        this.n = Math.max(2, Math.min(7, n));
        this.on = new boolean[this.n * this.n];
        java.util.Arrays.fill(on, true);
    }

    public int size() { return n; }

    public boolean on(int x, int z) { return on[z * n + x]; }

    public void press(int x, int z) {
        flip(x, z);
        flip(x + 1, z);
        flip(x - 1, z);
        flip(x, z + 1);
        flip(x, z - 1);
    }

    private void flip(int x, int z) {
        if (x < 0 || z < 0 || x >= n || z >= n) return;
        on[z * n + x] = !on[z * n + x];
    }

    public boolean solved() {
        for (boolean b : on) if (!b) return false;
        return true;
    }

    public int litCount() {
        int k = 0;
        for (boolean b : on) if (b) k++;
        return k;
    }

    /**
     * 서로 다른 칸 moves 개를 눌러 섞는다(이미 풀린 상태가 되면 다시 섞음).
     * @return 누른 칸 (z*n+x) — 정답 (같은 칸을 다시 누르면 풀린다)
     */
    public int[] scramble(int moves, SplittableRandom rng) {
        int k = Math.max(1, Math.min(n * n, moves));
        for (int attempt = 0; attempt < 32; attempt++) {
            java.util.Arrays.fill(on, true);
            int[] cells = new int[n * n];
            for (int i = 0; i < cells.length; i++) cells[i] = i;
            for (int i = cells.length - 1; i > 0; i--) {
                int j = rng.nextInt(i + 1);
                int t = cells[i];
                cells[i] = cells[j];
                cells[j] = t;
            }
            int[] chosen = java.util.Arrays.copyOf(cells, k);
            for (int c : chosen) press(c % n, c / n);
            if (!solved()) return chosen;
        }
        press(0, 0);
        return new int[] {0};
    }
}
