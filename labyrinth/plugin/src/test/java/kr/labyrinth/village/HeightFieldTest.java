package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import org.junit.jupiter.api.Test;

/** 목표 높이장 성질 (가짜 높이맵). */
class HeightFieldTest {

    static final int N = 81, C = 40, R = 20, B = 16;

    /** 동쪽으로 올라가는 경사(4칸에 1) + 작은 굴곡. */
    static int[] slope() {
        int[] g = new int[N * N];
        for (int z = 0; z < N; z++) for (int x = 0; x < N; x++) g[z * N + x] = 60 + x / 4 + ((x * 7 + z * 3) % 5 == 0 ? 1 : 0);
        return g;
    }

    static int[] none() {
        int[] f = new int[N * N];
        Arrays.fill(f, HeightField.NONE);
        return f;
    }

    static void pad(int[] fixed, int x0, int z0, int w, int d, int h) {
        for (int z = z0; z < z0 + d; z++) for (int x = x0; x < x0 + w; x++) fixed[z * N + x] = h;
    }

    @Test
    void padsStayFixedAndNeighboursDifferAtMostOneInsideR() {
        int[] g = slope();
        int[] f = none();
        pad(f, 30, 30, 9, 9, 70);   // 원래 ~67~69 → 조금 메움
        pad(f, 46, 36, 7, 7, 71);   // 원래 ~71~73 → 조금 깎음
        HeightField.Result r = HeightField.compute(N, N, C, C, R, B, g, f);
        int[] t = r.target();
        for (int i = 0; i < N * N; i++) if (f[i] != HeightField.NONE) assertEquals(f[i], t[i], "단 고정");
        int bad = 0;
        for (int z = 0; z < N; z++) {
            for (int x = 0; x < N; x++) {
                if (Math.hypot(x - C, z - C) > R) continue;
                int i = z * N + x;
                if (x + 1 < N && !(f[i] != HeightField.NONE && f[i + 1] != HeightField.NONE) && Math.abs(t[i] - t[i + 1]) > 1) bad++;
                if (z + 1 < N && !(f[i] != HeightField.NONE && f[i + N] != HeightField.NONE) && Math.abs(t[i] - t[i + N]) > 1) bad++;
            }
        }
        assertEquals(0, bad, "R 안 이웃 높이 차 ≤ 1");
    }

    @Test
    void outsideBlendUntouchedAndBandConvergesToGround() {
        int[] g = slope();
        int[] f = none();
        pad(f, 34, 34, 13, 13, 75); // 크게 메운 단 (원래 ~68~71)
        HeightField.Result r = HeightField.compute(N, N, C, C, R, B, g, f);
        int[] t = r.target();
        double sumInner = 0, sumOuter = 0;
        int nInner = 0, nOuter = 0;
        for (int z = 0; z < N; z++) {
            for (int x = 0; x < N; x++) {
                int i = z * N + x;
                double d = Math.hypot(x - C, z - C);
                if (d > R + B) assertEquals(g[i], t[i], "R+B 밖은 그대로");
                if (d > R && d <= R + 4) {
                    sumInner += Math.abs(t[i] - g[i]);
                    nInner++;
                }
                if (d > R + B - 4 && d <= R + B) {
                    sumOuter += Math.abs(t[i] - g[i]);
                    nOuter++;
                }
            }
        }
        assertTrue(sumOuter / nOuter < sumInner / nInner, "띠 바깥쪽으로 갈수록 원래 높이에 가까움");
        assertTrue(sumOuter / nOuter < 0.5, "띠 끝에서는 거의 원래 높이: " + sumOuter / nOuter);
        assertTrue(r.fill() > 0);
    }

    @Test
    void flatGroundWithMatchingPadChangesNothing() {
        int[] g = new int[N * N];
        Arrays.fill(g, 64);
        int[] f = none();
        pad(f, 35, 35, 10, 10, 64);
        HeightField.Result r = HeightField.compute(N, N, C, C, R, B, g, f);
        assertEquals(0, r.cut());
        assertEquals(0, r.fill());
        for (int e : r.exposed()) assertEquals(0, e);
    }

    @Test
    void neighbouringPadsAtDifferentHeightsGetRetainingWall() {
        int[] g = new int[N * N];
        Arrays.fill(g, 64);
        int[] f = none();
        pad(f, 30, 35, 6, 6, 64);
        pad(f, 36, 35, 6, 6, 68); // 바로 옆 4칸 높은 단
        HeightField.Result r = HeightField.compute(N, N, C, C, R, B, g, f);
        int walls = 0;
        for (int e : r.exposed()) if (e >= 2) walls++;
        assertTrue(walls >= 6, "높은 단 가장자리 = 옹벽: " + walls);
        assertEquals(4, r.exposed()[38 * N + 36], "옹벽 높이 = 단 차");
    }

    @Test
    void naturalCliffInsideRIsSmoothed() {
        int[] g = new int[N * N];
        for (int z = 0; z < N; z++) for (int x = 0; x < N; x++) g[z * N + x] = x < C ? 64 : 68; // 4칸 절벽
        HeightField.Result r = HeightField.compute(N, N, C, C, R, B, g, none());
        int[] t = r.target();
        for (int x = C - 10; x < C + 10; x++) assertTrue(Math.abs(t[C * N + x] - t[C * N + x + 1]) <= 1, "x=" + x);
    }
}
