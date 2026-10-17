package kr.labyrinth.bosses.impl;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

/**
 * 지하 10층 심연의 심장 넬카르 (GDD §7.10) 순수 로직 — Bukkit 없이 단위 테스트한다.
 * <ul>
 *   <li>{@link Geometry}: 투기장 ① 심장실(원) ② 탈출 회랑(+z 직사각형, 틈) ③ 심연의 가장자리(원형 단 + 낭떠러지 고리).
 *       FloorGenerator 의 셀 규칙(dx² + dz² ≤ r² + r)과 같은 정수 블록 오프셋으로 판정한다.</li>
 *   <li>{@link Grid}: 심장실 3×3 타일 상태 (멀쩡 → 금 감 → 무너짐 → 복구 / 영구 붕괴).</li>
 *   <li>붕괴 배치 5종(흩뿌리기·체스판·동심원·십자·나선), 해일 벽 이동, 회전 응시 판정, 박동 누적, 메아리 고르기, 구체 유도.</li>
 * </ul>
 */
final class AbyssLogic {

    private AbyssLogic() {}

    // ── 투기장 기하 ──────────────────────────────────────────────────────

    /**
     * 투기장 모양 (모두 심장실 중심 블록 기준 정수 오프셋, +z = 남쪽 = 회랑 방향).
     * @param r          심장실 반경
     * @param half       회랑 반폭 (폭 7 → 3)
     * @param uStart     회랑 첫 줄 z (= r − 1, 원과 겹쳐 틈이 없게)
     * @param uEnd       회랑 끝 줄 z (= r + 길이)
     * @param rimR       가장자리 단 반경 (발 디딜 수 있는 곳)
     * @param rimOuter   낭떠러지 고리 바깥 반경 (단 + RIM_MOAT)
     * @param rimU       가장자리 단 중심 z
     */
    record Geometry(int r, int half, int uStart, int uEnd, int rimR, int rimOuter, int rimU) {

        static Geometry of(int radius, int corridorLength, int corridorWidth, int rimRadius, int moat) {
            int half = Math.max(1, corridorWidth / 2);
            int len = Math.max(10, corridorLength);
            int rim = Math.max(6, rimRadius);
            int outer = rim + Math.max(1, moat);
            return new Geometry(radius, half, radius - 1, radius + len, rim, outer, radius + len + outer - 1);
        }

        boolean inChamber(int dx, int dz) { return dx * dx + dz * dz <= r * r + r; }

        boolean inCorridor(int dx, int dz) { return Math.abs(dx) <= half && dz >= uStart && dz <= uEnd; }

        private int rim2(int dx, int dz) { return dx * dx + (dz - rimU) * (dz - rimU); }

        /** 가장자리 단 (낭떠러지 제외). */
        boolean onRim(int dx, int dz) { return rim2(dx, dz) <= rimR * rimR + rimR; }

        /** 낭떠러지 고리 (단 바깥 ~ 생성 바닥 끝). */
        boolean inMoat(int dx, int dz) {
            int d = rim2(dx, dz);
            return d > rimR * rimR + rimR && d <= rimOuter * rimOuter + rimOuter;
        }

        /** 회랑이 단으로 이어지는 다리 (낭떠러지 고리 중 북쪽 회랑 폭). 추격이 끝나면 무너진다. */
        boolean inBridge(int dx, int dz) { return inMoat(dx, dz) && Math.abs(dx) <= half && dz < rimU; }

        /** 투기장 어딘가 (margin 칸 여유). */
        boolean inBattle(int dx, int dz, int margin) {
            int rr = r + margin;
            if (dx * dx + dz * dz <= rr * rr + rr) return true;
            if (Math.abs(dx) <= half + margin && dz >= uStart - margin && dz <= uEnd + margin) return true;
            int ro = rimOuter + margin;
            return rim2(dx, dz) <= ro * ro + ro;
        }

        /** 회랑 틈 시작 줄 (z) — 회랑 길이를 gaps+1 등분한 자리, 길이 gapLen. */
        int[] gapStarts(int gaps, int gapLen) {
            int n = Math.max(0, gaps);
            int[] out = new int[n];
            int len = uEnd - uStart;
            for (int k = 0; k < n; k++) out[k] = uStart + (int) Math.round(len * (k + 1) / (double) (n + 1)) - gapLen / 2;
            return out;
        }

        static boolean inGap(int dz, int[] starts, int gapLen) {
            for (int s : starts) if (dz >= s && dz < s + gapLen) return true;
            return false;
        }
    }

    /**
     * 추격 중 떨어진 사람을 내려놓을 회랑 z: 지금 자리와 해일 앞 4칸 중 먼 쪽, 틈이면 틈 너머. 회랑 끝을 넘으면 끝 줄.
     */
    static int pursuitSafeZ(int playerZ, double wallZ, Geometry g, int[] gaps, int gapLen) {
        int z = Math.max(playerZ, Math.max((int) Math.ceil(wallZ + 4), g.uStart() + 1));
        for (int guard = 0; guard < 8 && Geometry.inGap(z, gaps, gapLen); guard++) z++;
        return Math.min(z, g.uEnd());
    }

    // ── 해일 벽 ──────────────────────────────────────────────────────────

    /** 시작 후 t 초 뒤 해일 벽 위치 (초속 v0, 가속 a). */
    static double wallPos(double start, double v0, double accel, double t) { return start + v0 * t + 0.5 * accel * t * t; }

    /** 벽에 닿았는가 (벽 앞면 + 0.6칸). */
    static boolean wallTouches(double playerZ, double wallZ) { return playerZ <= wallZ + 0.6; }

    // ── 타일 격자 ────────────────────────────────────────────────────────

    /** 홀수 타일 크기 (3 → 3, 4 → 5): 중심 블록이 있어야 보스 자리 타일이 대칭이다. */
    static int oddSize(double tileSize) {
        int s = Math.max(1, (int) Math.round(tileSize));
        return s % 2 == 0 ? s + 1 : s;
    }

    /** 심장실 원 안에 통째로 들어가는 타일 (i, j). 보스가 선 (0, 0) 은 뺀다. */
    static List<int[]> chamberTiles(int radius, int size) {
        int h = size / 2;
        int n = radius / size + 1;
        List<int[]> out = new ArrayList<>();
        for (int i = -n; i <= n; i++) {
            for (int j = -n; j <= n; j++) {
                if (i == 0 && j == 0) continue;
                int mx = size * Math.abs(i) + h, mz = size * Math.abs(j) + h;
                if (mx * mx + mz * mz <= radius * radius + radius) out.add(new int[]{i, j});
            }
        }
        return out;
    }

    /** 블록 오프셋 → 타일 좌표 (중심 타일이 −h..h). */
    static int tileOf(int blockOffset, int size) { return Math.floorDiv(blockOffset + size / 2, size); }

    /** 한 번에 무너뜨릴 타일 수 = 전체 × (30% + 2% × (n−1)), 1 ~ 남은 수. */
    static int collapseCount(int total, int available, double base, double perMember, int partySize) {
        double frac = base + perMember * Math.max(0, partySize - 1);
        int c = (int) Math.round(total * frac);
        return Math.max(available > 0 ? 1 : 0, Math.min(available, c));
    }

    /** 붕괴 배치 (9초마다 바뀐다). */
    enum Layout {
        SCATTER("흩뿌리기"), CHECKER("체스판"), RINGS("동심원"), CROSS("십자"), SPIRAL("나선");

        final String label;

        Layout(String label) { this.label = label; }

        static Layout parse(String s) {
            if (s == null) return SCATTER;
            return switch (s.trim().toLowerCase(Locale.ROOT)) {
                case "checker", "chess" -> CHECKER;
                case "rings", "ring", "concentric" -> RINGS;
                case "cross", "plus" -> CROSS;
                case "spiral" -> SPIRAL;
                default -> SCATTER;
            };
        }

        static List<Layout> parseAll(List<String> keys) {
            List<Layout> out = new ArrayList<>();
            if (keys != null) for (String k : keys) {
                Layout l = parse(k);
                if (!out.contains(l)) out.add(l);
            }
            if (out.isEmpty()) out.addAll(Arrays.asList(values()));
            return out;
        }
    }

    /**
     * 배치 규칙대로 count 개를 고른다 (available = 지금 멀쩡한 타일). 모양을 먼저 채우고, 모자라면 나머지에서 무작위.
     * 같은 rng 면 같은 결과 (테스트용).
     */
    static List<int[]> pick(Layout layout, List<int[]> available, int count, Random rng) {
        List<int[]> pool = new ArrayList<>(available);
        Collections.shuffle(pool, rng);
        if (count <= 0 || pool.isEmpty()) return new ArrayList<>();
        Comparator<int[]> order;
        switch (layout) {
            case CHECKER -> {
                int parity = rng.nextInt(2);
                order = Comparator.comparingInt(t -> Math.floorMod(t[0] + t[1], 2) == parity ? 0 : 1);
            }
            case RINGS -> {
                int parity = rng.nextInt(2);
                boolean outward = rng.nextBoolean();
                order = Comparator.<int[]>comparingInt(t -> band(t) % 2 == parity ? 0 : 1)
                        .thenComparingInt(t -> outward ? band(t) : -band(t));
            }
            case CROSS -> {
                boolean diagonal = rng.nextBoolean();
                order = Comparator.comparingInt(t -> diagonal ? Math.min(Math.abs(t[0] - t[1]), Math.abs(t[0] + t[1]))
                        : Math.min(Math.abs(t[0]), Math.abs(t[1])));
            }
            case SPIRAL -> {
                int arms = 2 + rng.nextInt(2);
                double twist = 32 + rng.nextDouble() * 16;
                double rot = rng.nextDouble() * 360;
                double span = 360.0 / arms;
                order = Comparator.comparingDouble(t -> {
                    double theta = Math.toDegrees(Math.atan2(t[1], t[0]));
                    double ph = ((theta - twist * Math.hypot(t[0], t[1]) + rot) % span + span) % span;
                    return Math.min(ph, span - ph);
                });
            }
            default -> order = null;
        }
        if (order != null) pool.sort(order); // 안정 정렬 → 같은 순위는 섞인 순서 그대로
        return new ArrayList<>(pool.subList(0, Math.min(count, pool.size())));
    }

    /** 동심원 띠 번호 (타일 단위 거리 반올림). */
    static int band(int[] t) { return (int) Math.round(Math.hypot(t[0], t[1])); }

    /** 다음 배치: 목록을 차례로 돌되 직전과 다른 것. */
    static Layout nextLayout(List<Layout> cycle, int wave) {
        if (cycle.isEmpty()) return Layout.SCATTER;
        return cycle.get(Math.floorMod(wave, cycle.size()));
    }

    /** 타일 상태 (심장실). */
    enum State { SOLID, WARN, FALLEN, GONE }

    /** 심장실 타일 격자 — 상태와 시각(틱)만. 블록·연출은 보스가 한다. */
    static final class Grid {
        final int size;
        final List<int[]> tiles;
        private final Map<Long, Integer> index = new HashMap<>();
        private final State[] state;
        private final long[] until;

        Grid(List<int[]> tiles, int size) {
            this.size = size;
            this.tiles = List.copyOf(tiles);
            this.state = new State[tiles.size()];
            this.until = new long[tiles.size()];
            Arrays.fill(state, State.SOLID);
            for (int k = 0; k < tiles.size(); k++) index.put(key(tiles.get(k)[0], tiles.get(k)[1]), k);
        }

        private static long key(int i, int j) { return ((long) i << 32) ^ (j & 0xffffffffL); }

        int count() { return tiles.size(); }

        int indexOf(int i, int j) { return index.getOrDefault(key(i, j), -1); }

        /** 블록 오프셋의 타일 번호 (−1 = 격자 밖 또는 보스 자리). */
        int tileAtBlock(int dx, int dz) { return indexOf(tileOf(dx, size), tileOf(dz, size)); }

        State state(int k) { return state[k]; }

        long until(int k) { return until[k]; }

        int[] tile(int k) { return tiles.get(k); }

        /** 타일 중심 블록 오프셋. */
        int centerX(int k) { return tiles.get(k)[0] * size; }

        int centerZ(int k) { return tiles.get(k)[1] * size; }

        void warn(int k, long at) {
            if (state[k] != State.SOLID) return;
            state[k] = State.WARN;
            until[k] = at;
        }

        /** 무너짐. restoreAt = Long.MAX_VALUE 면 영구(GONE). */
        void collapse(int k, long restoreAt) {
            state[k] = restoreAt == Long.MAX_VALUE ? State.GONE : State.FALLEN;
            until[k] = restoreAt;
        }

        void restore(int k) {
            state[k] = State.SOLID;
            until[k] = 0;
        }

        /** 떨어지는 칸인가 (무너짐·영구 붕괴). */
        boolean hole(int k) { return k >= 0 && (state[k] == State.FALLEN || state[k] == State.GONE); }

        List<int[]> solidTiles() {
            List<int[]> out = new ArrayList<>();
            for (int k = 0; k < state.length; k++) if (state[k] == State.SOLID) out.add(tiles.get(k));
            return out;
        }

        /** now 에 상태가 바뀌어야 하는 타일: [0] 금 간 → 무너짐, [1] 무너짐 → 복구. */
        List<List<Integer>> due(long now) {
            List<Integer> fall = new ArrayList<>(), back = new ArrayList<>();
            for (int k = 0; k < state.length; k++) {
                if (state[k] == State.WARN && now >= until[k]) fall.add(k);
                else if (state[k] == State.FALLEN && now >= until[k]) back.add(k);
            }
            return List.of(fall, back);
        }

        /** (dx, dz) 블록 오프셋에서 가장 가까운 멀쩡한 타일 (−1 = 없음). 금 간 타일은 피한다. */
        int nearestSolid(double dx, double dz) {
            int best = -1;
            double bd = Double.MAX_VALUE;
            for (int k = 0; k < state.length; k++) {
                if (state[k] != State.SOLID) continue;
                double ddx = centerX(k) - dx, ddz = centerZ(k) - dz;
                double d = ddx * ddx + ddz * ddz;
                if (d < bd) {
                    bd = d;
                    best = k;
                }
            }
            return best;
        }

        /** 상태 개수 (테스트·디버그). */
        int countState(State s) {
            int n = 0;
            for (State x : state) if (x == s) n++;
            return n;
        }
    }

    // ── 회전 응시 ────────────────────────────────────────────────────────

    /**
     * 맥동 고리 끌기 (GDD §8.6): 심장실 단계면 대상 → 고리 안 반경까지 0.5칸마다 발밑 타일을 보고, 무너졌거나 무너질 경고 중인 타일이
     * 하나라도 있으면 끌지 않는다 (피해·잔류만 — 구멍 너머로 끌려 떨어지지 않게). 가장자리 단계는 단 안쪽이라 늘 끈다.
     * 좌표는 심장실 중심 블록에서의 오프셋 (블록 = floor).
     */
    static boolean pullClear(Grid grid, double tx, double tz, double hx, double hz, double inner, boolean chamber) {
        if (!chamber || grid == null) return true;
        double dx = hx - tx, dz = hz - tz;
        double d = Math.hypot(dx, dz);
        double travel = d - inner;
        if (travel <= 0 || d < 1e-9) return true;
        for (double s = 0; s <= travel + 1e-9; s += 0.5) {
            double x = tx + dx / d * s, z = tz + dz / d * s;
            int k = grid.tileAtBlock((int) Math.floor(x), (int) Math.floor(z));
            if (k >= 0 && grid.state(k) != State.SOLID) return false;
        }
        return true;
    }

    /** k 번째 광선 각도(도): 시작각 + 등분 + 방향 × 속도 × 경과초. */
    static double beamAngle(double start, int k, int beams, double degPerSec, double seconds, int dir) {
        return start + k * 360.0 / Math.max(1, beams) + dir * degPerSec * seconds;
    }

    /** (dx, dz) 가 각도 ang(도, 0 = +X, 90 = +Z) 광선 위인가: 0 ≤ 투영 ≤ 길이, 수직 거리 ≤ 폭/2. */
    static boolean inBeam(double dx, double dz, double angDeg, double length, double width) {
        double a = Math.toRadians(angDeg);
        double c = Math.cos(a), s = Math.sin(a);
        double t = dx * c + dz * s;
        if (t < 0 || t > length) return false;
        return Math.abs(-dx * s + dz * c) <= width / 2;
    }

    // ── 심장 박동 (소프트 엔레이지) ──────────────────────────────────────

    /** k 번째 박동(0부터) 피해 배율 = 기본 × (1 + 누적 × k). */
    static double heartbeatMult(double base, double ramp, int k) { return base * (1 + ramp * Math.max(0, k)); }

    // ── 지난 층의 메아리 ─────────────────────────────────────────────────

    /** 메아리 하나 고르기 — 직전과 다른 것 (목록이 하나뿐이면 그것). */
    static String pickEcho(List<String> pool, String last, Random rng) {
        if (pool == null || pool.isEmpty()) return null;
        List<String> c = new ArrayList<>(pool);
        if (c.size() > 1 && last != null) c.remove(last);
        return c.get(rng.nextInt(c.size()));
    }

    /** 메아리 경고 시간(틱) = 원래 경고 × 배율, 최소 0.5초. */
    static int echoWindup(int originalTicks, double mult) { return Math.max(10, (int) Math.round(originalTicks * mult)); }

    /** 단조 진동 메아리: 말뚝 수 = 파티가 2명씩 붙잡을 수 있게 ⌈n/2⌉, 최소 2. */
    static int echoStakes(int partySize) { return Math.max(2, (partySize + 1) / 2); }

    // ── 공허 구체 유도 ───────────────────────────────────────────────────

    /** 수평 유도: 지금 방향(vx, vz)을 대상 방향(tx, tz) 쪽으로 homing 비율만큼 꺾고 speed 로 맞춘다. */
    static double[] steer(double vx, double vz, double tx, double tz, double homing, double speed) {
        double vl = Math.hypot(vx, vz), tl = Math.hypot(tx, tz);
        double ux = vl < 1e-9 ? 0 : vx / vl, uz = vl < 1e-9 ? 0 : vz / vl;
        if (tl > 1e-9) {
            double h = Math.max(0, Math.min(1, homing));
            ux += (tx / tl - ux) * h;
            uz += (tz / tl - uz) * h;
        }
        double l = Math.hypot(ux, uz);
        if (l < 1e-9) return new double[]{tl < 1e-9 ? speed : tx / tl * speed, tl < 1e-9 ? 0 : tz / tl * speed};
        return new double[]{ux / l * speed, uz / l * speed};
    }
}
