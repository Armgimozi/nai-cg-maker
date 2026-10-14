package kr.labyrinth.village;

/**
 * 목표 높이장 (VILLAGE.md §4.1 3번) — 순수 함수. 원래 땅높이 + "바뀐 양" 장으로 계산한다:
 * <ol>
 *   <li>고정 칸(조각 단·길·추가 단)의 바뀐 양 Δ = 고정 높이 − 원래 높이.</li>
 *   <li>나머지 칸의 Δ 는 고정 칸 값에서 멀어질수록 줄어드는 매끄러운 보간 (가려진 라플라스 방정식, SOR, 감쇠 길이
 *       {@link #DECAY}칸, R+B 밖 = 0) — 가까운 단·길 높이를 거리에 따라 섞는 효과. 바꾼 양만 퍼지므로 원래 지형의
 *       굴곡은 그대로 남고(평판 금지), 단에서 먼 곳은 거의 손대지 않는다.</li>
 *   <li>R~R+B 띠에서는 Δ 에 (1 − smoothstep) 을 곱해 원래 높이로 돌아간다. R+B 밖은 손대지 않는다.</li>
 *   <li>걸어 다닐 수 있게: 고정이 아닌 칸은 이웃(4방향) 높이 차가 1 이하가 될 때까지 다듬는다
 *       (R 안은 전부, 띠는 바뀐 칸과 그 이웃만 — 띠 밖 자연 절벽은 건드리지 않음).</li>
 *   <li>그래도 이웃보다 2칸 이상 높은 칸(R 안 전부 + 띠의 바뀐 칸) = 옹벽 (드러난 높이 {@code exposed}).</li>
 * </ol>
 */
public final class HeightField {

    public static final int NONE = Integer.MIN_VALUE;
    /** 바뀐 양이 단에서 퍼지는 감쇠 길이 (칸). */
    public static final double DECAY = 6.0;

    /** 결과: 목표 높이, 원래와 다른가, 옹벽 드러난 높이(0 = 아님). 배열 순서 = z*nx + x. */
    public record Result(int nx, int nz, int[] target, boolean[] changed, int[] exposed, long cut, long fill) {}

    private HeightField() {}

    /**
     * @param cx,cz 중심의 배열 좌표 (0..nx-1)
     * @param r 안쪽 반경 R (이 안은 Δ 그대로), b 혼합 띠 폭 B
     * @param ground 원래 땅높이, fixed 고정 높이 ({@link #NONE} = 자유)
     */
    public static Result compute(int nx, int nz, int cx, int cz, int r, int b, int[] ground, int[] fixed) {
        int n = nx * nz;
        double[] dist = new double[n];
        boolean[] region = new boolean[n];
        boolean[] isFixed = new boolean[n];
        for (int z = 0; z < nz; z++) {
            for (int x = 0; x < nx; x++) {
                int i = z * nx + x;
                dist[i] = Math.hypot(x - cx, z - cz);
                region[i] = dist[i] <= r + b;
                isFixed[i] = fixed[i] != NONE;
            }
        }
        // 1~2. Δ 보간 (가려진 라플라스, SOR — 고정 칸·영역 밖은 디리클레 조건)
        double[] delta = new double[n];
        for (int i = 0; i < n; i++) if (isFixed[i]) delta[i] = fixed[i] - ground[i];
        double omega = 1.85, k2 = 1.0 / (DECAY * DECAY);
        for (int it = 0; it < 600; it++) {
            double maxChange = 0;
            for (int z = 0; z < nz; z++) {
                for (int x = 0; x < nx; x++) {
                    int i = z * nx + x;
                    if (isFixed[i] || !region[i]) continue;
                    double s = 0;
                    s += x > 0 && region[i - 1] ? delta[i - 1] : 0;
                    s += x < nx - 1 && region[i + 1] ? delta[i + 1] : 0;
                    s += z > 0 && region[i - nx] ? delta[i - nx] : 0;
                    s += z < nz - 1 && region[i + nx] ? delta[i + nx] : 0;
                    double nv = delta[i] + omega * (s / (4.0 + k2) - delta[i]);
                    maxChange = Math.max(maxChange, Math.abs(nv - delta[i]));
                    delta[i] = nv;
                }
            }
            if (maxChange < 0.004) break;
        }
        // 3. 띠에서 원래 높이로
        int[] t = new int[n];
        for (int i = 0; i < n; i++) {
            if (isFixed[i]) t[i] = fixed[i];
            else if (!region[i]) t[i] = ground[i];
            else t[i] = (int) Math.floor(ground[i] + delta[i] * weight(dist[i], r, b) + 0.5);
        }
        // 4. 이웃 차 ≤ 1 로 다듬기 (고정 칸은 그대로)
        int[] dx = {-1, 1, 0, 0}, dz = {0, 0, -1, 1};
        for (int pass = 0; pass < 400; pass++) {
            boolean any = false;
            boolean reverse = (pass & 1) == 1;
            for (int k = 0; k < n; k++) {
                int i = reverse ? n - 1 - k : k;
                if (isFixed[i] || !region[i]) continue;
                int x = i % nx, z = i / nx;
                int lo = Integer.MIN_VALUE, hi = Integer.MAX_VALUE;
                boolean neighborChanged = false;
                for (int q = 0; q < 4; q++) {
                    int ax = x + dx[q], az = z + dz[q];
                    if (ax < 0 || az < 0 || ax >= nx || az >= nz) continue;
                    int j = az * nx + ax;
                    lo = Math.max(lo, t[j] - 1);
                    hi = Math.min(hi, t[j] + 1);
                    if (t[j] != ground[j]) neighborChanged = true;
                }
                if (lo == Integer.MIN_VALUE) continue;
                if (!(dist[i] <= r || t[i] != ground[i] || neighborChanged)) continue;
                int nv = lo <= hi ? Math.max(lo, Math.min(hi, t[i])) : Math.floorDiv(lo + hi, 2);
                if (nv != t[i]) {
                    t[i] = nv;
                    any = true;
                }
            }
            if (!any) break;
        }
        // 5. 옹벽
        boolean[] changed = new boolean[n];
        int[] exposed = new int[n];
        long cut = 0, fill = 0;
        for (int i = 0; i < n; i++) {
            changed[i] = t[i] != ground[i];
            if (t[i] > ground[i]) fill += t[i] - ground[i];
            else cut += ground[i] - t[i];
            if (!region[i] || !(changed[i] || isFixed[i] || dist[i] <= r)) continue; // R 안은 그대로인 칸도 (흙 절벽 대신 돌 옹벽)
            int x = i % nx, z = i / nx;
            int min = t[i];
            for (int q = 0; q < 4; q++) {
                int ax = x + dx[q], az = z + dz[q];
                if (ax < 0 || az < 0 || ax >= nx || az >= nz) continue;
                min = Math.min(min, t[az * nx + ax]);
            }
            if (t[i] - min >= 2) exposed[i] = t[i] - min;
        }
        return new Result(nx, nz, t, changed, exposed, cut, fill);
    }

    /** 안쪽 1, 띠에서 1 − smoothstep, 밖 0. */
    public static double weight(double dist, int r, int b) {
        if (dist <= r) return 1;
        if (dist >= r + b) return 0;
        double u = (dist - r) / b;
        return 1 - u * u * (3 - 2 * u);
    }
}
