package kr.labyrinth.bosses;

import java.util.ArrayList;
import java.util.List;

/**
 * 보스 기본 공격·칼끝 띠·설 자리 수학 (bs362 → bs363, Bukkit 무관 — 단위 테스트 대상).
 * <p>
 * <b>기본 공격 (보스마다 다른 거리)</b>: 보스 중심 ↔ 플레이어 발 수평 거리 ≤ reach (= 2.0 + 0.7 × scale), 발 높이 차 &lt; 3.5
 * ({@link #legacy}) — 0.3.6.1 과 같다. 여기에 시야가 있어야 한다: 플레이어 눈과 히트박스 사이에 막는 블록이 없음
 * ({@link #sees(double, double, double, Box, Ray)}) — 벽 너머로 안 친다. 휘두른 뒤 3틱 뒤 판정은 {@link #CONFIRM_SLACK} 만큼 여유.
 * <p>
 * <b>칼끝 띠</b> ({@link #inBand}): 플레이어 눈 → 보스 히트박스 겉면 ≤ 플레이어 손 닿음 + 여유. 보스가 "못 닿는데 맞고 있다" 를
 * 판단할 때만 쓴다(대응 감시 {@link AnswerWatch}) — 피해 판정에는 절대 안 쓴다.
 * <p>
 * <b>설 자리</b> ({@link #standOrder}): 대상 둘레 고리에서 보스 자기 거리 − 0.3 안, 대상 몸 위가 아닌 후보를 정해진 순서로.
 * 블록 검사(몸이 들어가는가·받쳐지는가·보이는가)는 {@link Boss} 가 한다.
 */
public final class BossReach {

    private BossReach() {}

    /** 플레이어 바닐라 손 닿음 (눈 → 상대 히트박스 겉면). */
    public static final double PLAYER_REACH = 3.0;
    /** 휘두르고 3틱 뒤 맞힐 때 여유 (옛 규칙의 reach + 0.8 과 같다). */
    public static final double CONFIRM_SLACK = 0.8;
    /** 옛 규칙의 발 높이 차 한계. */
    public static final double LEGACY_DY = 3.5;
    /** 시야 광선을 끝점 조금 앞에서 멈춘다 (상자 겉면이 벽에 닿아 있어도 그 벽을 막힘으로 안 셈). */
    public static final double RAY_END_SLACK = 0.05;

    /** 축 정렬 상자 (히트박스). */
    public record Box(double minX, double minY, double minZ, double maxX, double maxY, double maxZ) {
        /** 발 가운데 (x, y, z) · 반폭 · 높이로 만든 상자. */
        public static Box of(double x, double y, double z, double halfWidth, double height) {
            return new Box(x - halfWidth, y, z - halfWidth, x + halfWidth, y + height, z + halfWidth);
        }

        public double halfWidth() { return Math.max(maxX - minX, maxZ - minZ) / 2; }

        public double height() { return maxY - minY; }
    }

    /** 블록 광선: a → b 사이를 막는 블록이 없으면 true. */
    @FunctionalInterface
    public interface Ray {
        boolean clear(double ax, double ay, double az, double bx, double by, double bz);
    }

    // ── 거리 ─────────────────────────────────────────────────────────────

    /** 점 → 상자 최단 거리 (안이면 0) — 바닐라 손 닿음과 같은 잣대. */
    public static double pointToBox(double px, double py, double pz, Box b) {
        double dx = Math.max(Math.max(b.minX() - px, 0), px - b.maxX());
        double dy = Math.max(Math.max(b.minY() - py, 0), py - b.maxY());
        double dz = Math.max(Math.max(b.minZ() - pz, 0), pz - b.maxZ());
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    /** 상자 위에서 점에 가장 가까운 점. */
    public static double[] closestPoint(double px, double py, double pz, Box b) {
        return new double[] {clamp(px, b.minX(), b.maxX()), clamp(py, b.minY(), b.maxY()), clamp(pz, b.minZ(), b.maxZ())};
    }

    /** 보스 기본 공격 거리 (보스 중심 ↔ 플레이어 발 수평): 2.0 + 0.7 × scale — 보스마다 다르다 (0.3.6.1 그대로). */
    public static double reach(double scale) { return 2.0 + 0.7 * scale; }

    /** 기본 공격 기하 (중심 ↔ 발 수평 ≤ reach, 높이 차 &lt; 3.5 — 0.3.6.1 그대로). */
    public static boolean legacy(double horizontal, double dy, double reach) {
        return horizontal <= reach && Math.abs(dy) < LEGACY_DY;
    }

    /**
     * 칼끝 띠: 플레이어 눈 → 보스 상자 ≤ 플레이어 손 닿음 + slack. 판단 전용 (피해 아님) — 보스 기본 공격이 안 닿는데
     * 플레이어 칼은 닿는 자리인가.
     */
    public static boolean inBand(double eyeToBox, double playerReach, double slack) {
        return eyeToBox <= playerReach + slack;
    }

    /** 플레이어 손 닿음 속성값 → 칼끝 띠 거리 (바닐라 3.0 아래로는 줄이지 않는다). */
    public static double playerReach(double attributeValue) {
        return Double.isNaN(attributeValue) ? PLAYER_REACH : Math.max(PLAYER_REACH, attributeValue);
    }

    // ── 시야 ─────────────────────────────────────────────────────────────

    /** 시야 광선 최대 수. */
    public static final int MAX_SIGHT_RAYS = 8;

    /**
     * 시야: 플레이어 눈에서 히트박스의 가장 가까운 점, 같은 기둥의 위·가운데·아래 높이 점, 눈에 가까운 세로 모서리 둘(눈 높이·가운데)
     * 중 하나라도 막힘 없이 보이면 true. 광선은 최대 {@link #MAX_SIGHT_RAYS}개 (겹치는 점은 건너뜀). 플레이어가 칼로 칠 수 있는 점을
     * 고르는 것과 같은 잣대라 "플레이어는 보이는데 보스는 안 보임" 이 생기지 않게 한다. 눈이 상자 안이면 보인다.
     */
    public static boolean sees(double ex, double ey, double ez, Box b, Ray ray) {
        double[] cp = closestPoint(ex, ey, ez, b);
        if (dist(ex, ey, ez, cp[0], cp[1], cp[2]) < 1e-6) return true;
        List<double[]> tried = new ArrayList<>();
        if (tryRay(ex, ey, ez, cp[0], cp[1], cp[2], ray, tried)) return true;
        double inset = Math.min(0.25, b.height() / 4);
        double mid = (b.minY() + b.maxY()) / 2;
        for (double y : new double[] {b.maxY() - inset, mid, b.minY() + inset}) {
            if (tryRay(ex, ey, ez, cp[0], y, cp[2], ray, tried)) return true;
        }
        // 눈에 가까운 세로 모서리 둘 (등불 받침이 가까운 기둥을 가려도 면 끝은 보일 수 있다)
        double e = 0.02;
        double[][] corners = {{b.minX() + e, b.minZ() + e}, {b.minX() + e, b.maxZ() - e}, {b.maxX() - e, b.minZ() + e}, {b.maxX() - e, b.maxZ() - e}};
        java.util.Arrays.sort(corners, java.util.Comparator.comparingDouble(c -> Math.hypot(c[0] - ex, c[1] - ez)));
        double eyeY = clamp(ey, b.minY() + inset, b.maxY() - inset);
        for (int i = 0; i < 2; i++) {
            for (double y : new double[] {eyeY, mid}) {
                if (tryRay(ex, ey, ez, corners[i][0], y, corners[i][1], ray, tried)) return true;
            }
        }
        return false;
    }

    /** 거리 안 시야 광선 최대 수. */
    public static final int MAX_REACH_RAYS = 14;
    /** 거리 안 시야 표본 격자 간격 (히트박스 면 위). */
    static final double REACH_GRID = 0.3;

    /**
     * 거리 안 시야 (칼끝 띠 판단): 플레이어 눈에서 maxDist 안에 있는 히트박스 겉면 점 중 하나라도 막힘 없이 보이면 true.
     * 플레이어 칼이 실제로 닿는 점(손 닿음 안 + 보임)과 같은 잣대 — 가까운 점은 등불 받침에 가리고 받침 위로 보이는 윗몸은
     * 손 닿음 밖이면 플레이어도 못 친다 (그 자리는 칼끝 띠가 아니다). 표본은 가장 가까운 점, 그다음 눈을 향한 면 위 격자(거리 안)에서
     * 이미 고른 점과 가장 멀리 떨어진 점 순 (위·옆으로 고루 퍼짐), 광선 최대 {@link #MAX_REACH_RAYS}개. 눈이 상자 안이면 보인다.
     * maxDist 가 무한이면 {@link #sees(double, double, double, Box, Ray)} 와 같다.
     */
    public static boolean sees(double ex, double ey, double ez, Box b, Ray ray, double maxDist) {
        if (Double.isInfinite(maxDist)) return sees(ex, ey, ez, b, ray);
        double[] cp = closestPoint(ex, ey, ez, b);
        double d0 = dist(ex, ey, ez, cp[0], cp[1], cp[2]);
        if (d0 < 1e-6) return true;
        if (d0 > maxDist) return false;
        for (double[] p : reachSamples(ex, ey, ez, b, maxDist)) {
            if (ray.clear(ex, ey, ez, p[0], p[1], p[2])) return true;
        }
        return false;
    }

    /** {@link #sees(double, double, double, Box, Ray, double)} 가 광선을 쏘는 점들 (쏘는 순서 · 결정적). */
    static List<double[]> reachSamples(double ex, double ey, double ez, Box b, double maxDist) {
        double[] cp = closestPoint(ex, ey, ez, b);
        double e = 0.02;
        List<double[]> cand = new ArrayList<>();
        // 눈을 향한 면 (눈이 그 축의 상자 밖일 때만)
        if (ex < b.minX()) faceGrid(cand, 0, b.minX(), b, e);
        if (ex > b.maxX()) faceGrid(cand, 0, b.maxX(), b, e);
        if (ez < b.minZ()) faceGrid(cand, 2, b.minZ(), b, e);
        if (ez > b.maxZ()) faceGrid(cand, 2, b.maxZ(), b, e);
        if (ey > b.maxY()) faceGrid(cand, 1, b.maxY(), b, e);
        if (ey < b.minY()) faceGrid(cand, 1, b.minY(), b, e);
        cand.removeIf(p -> dist(ex, ey, ez, p[0], p[1], p[2]) > maxDist);
        List<double[]> out = new ArrayList<>();
        out.add(cp);
        double[] gap = new double[cand.size()];
        for (int i = 0; i < gap.length; i++) gap[i] = dist(cp[0], cp[1], cp[2], cand.get(i)[0], cand.get(i)[1], cand.get(i)[2]);
        while (out.size() < MAX_REACH_RAYS) {
            int best = -1;
            for (int i = 0; i < gap.length; i++) if (gap[i] > 0.3 && (best < 0 || gap[i] > gap[best])) best = i;
            if (best < 0) break;
            double[] q = cand.get(best);
            out.add(q);
            for (int i = 0; i < gap.length; i++) {
                double[] c = cand.get(i);
                gap[i] = Math.min(gap[i], dist(q[0], q[1], q[2], c[0], c[1], c[2]));
            }
        }
        return out;
    }

    /** 축 axis(0 = x, 1 = y, 2 = z) 값이 at 인 면 위 격자 (모서리에서 e 안쪽). */
    private static void faceGrid(List<double[]> out, int axis, double at, Box b, double e) {
        double[] lo = {b.minX() + e, b.minY() + e, b.minZ() + e};
        double[] hi = {b.maxX() - e, b.maxY() - e, b.maxZ() - e};
        int u = axis == 0 ? 1 : 0, v = axis == 2 ? 1 : 2;
        int nu = Math.max(1, (int) Math.ceil((hi[u] - lo[u]) / REACH_GRID));
        int nv = Math.max(1, (int) Math.ceil((hi[v] - lo[v]) / REACH_GRID));
        for (int i = 0; i <= nu; i++) {
            for (int j = 0; j <= nv; j++) {
                double[] p = new double[3];
                p[axis] = at;
                p[u] = lo[u] + (hi[u] - lo[u]) * i / nu;
                p[v] = lo[v] + (hi[v] - lo[v]) * j / nv;
                out.add(p);
            }
        }
    }

    /** 이미 쏜 점과 0.3칸 안이면 건너뛴다 (false). */
    private static boolean tryRay(double ex, double ey, double ez, double x, double y, double z, Ray ray, List<double[]> tried) {
        for (double[] t : tried) if (dist(t[0], t[1], t[2], x, y, z) < 0.3) return false;
        if (tried.size() >= MAX_SIGHT_RAYS) return false;
        tried.add(new double[] {x, y, z});
        return ray.clear(ex, ey, ez, x, y, z);
    }

    // ── 직접 다가가기·설 자리 ────────────────────────────────────────────

    /**
     * 걷기와 같은 직접 다가가기 속도 (블록/틱). 바닐라 땅 이동의 정상 속도 ≈ 2.16 × 이동 속도² (마찰 0.546, 입력 × 0.98) —
     * 1층 그로브(0.24)가 길찾기로 걸을 때 실서버 0.127칸/틱과 맞는다.
     */
    public static double walkSpeed(double movementSpeed) {
        double s = Math.max(0, movementSpeed);
        return Math.max(0.04, Math.min(0.3, 2.16 * s * s));
    }

    /** 설 자리 후보 반경(대상 기준). 0 = 대상 자리 (설 자리에서는 빠짐 — 몸 위). */
    static final double[] LANDING_RADII = {0, 0.6, 1.2, 1.8, 2.4, 3.0, 3.6};
    /** 고리마다 방향 수. */
    static final int LANDING_DIRS = 16;

    /** 설 자리·끼임 빼기 후보 (대상 둘레 고리, 가까운 순 · 같은 고리는 동쪽부터 시계 반대 — 결정적). */
    public static List<double[]> landingRing(double tx, double tz) {
        List<double[]> out = new ArrayList<>();
        for (double r : LANDING_RADII) {
            if (r == 0) {
                out.add(new double[] {tx, tz});
                continue;
            }
            for (int i = 0; i < LANDING_DIRS; i++) {
                double a = 2 * Math.PI * i / LANDING_DIRS;
                out.add(new double[] {tx + Math.cos(a) * r, tz + Math.sin(a) * r});
            }
        }
        return out;
    }

    /** 설 자리 순서 잣대: BOSS = 보스 자리에서 가까운 순 (걷기), NEAR = 주어진 점에서 가까운 순 (착지·순간이동). */
    public enum Order { BOSS, NEAR }

    /** 설 자리 거리 여유: 보스 자기 거리 − 이만큼 안 (닿은 뒤 대상이 조금 움직여도 닿게). */
    public static final double STAND_MARGIN = 0.3;
    /** 대상 몸 위에 서지 않게: 대상 발 ↔ 후보 수평 ≥ 반폭 + 이만큼. */
    public static final double STAND_CLEAR = 0.5;

    /**
     * 설 자리 후보 (블록 검사 전): 대상 발 둘레 {@link #landingRing} 가운데 대상과 수평 {@code hw + 0.5} 이상(몸 위가 아님),
     * {@code reach − 0.3} 이하(서면 자기 거리로 닿음), 아레나 중심에서 {@code arenaR − hw − 0.3} 이하인 점.
     * 순서는 (ox, oz) 에서 가까운 순, 같으면 대상에 가까운 순, 그것도 같으면 고리 순서 — 결정적.
     * @return {x, z} 목록
     */
    public static List<double[]> standOrder(double tx, double tz, double hw, double reach, double cx, double cz, double arenaR,
                                            double ox, double oz) {
        List<double[]> out = new ArrayList<>();
        double min = hw + STAND_CLEAR, max = reach - STAND_MARGIN, inside = arenaR - hw - 0.3;
        for (double[] c : landingRing(tx, tz)) {
            double d = Math.hypot(c[0] - tx, c[1] - tz);
            if (d < min - 1e-9 || d > max + 1e-9) continue;
            if (Math.hypot(c[0] - cx, c[1] - cz) > inside) continue;
            out.add(c);
        }
        // 안정 정렬 (같은 값이면 고리 순서 그대로)
        out.sort((a, b) -> {
            int k = Double.compare(Math.hypot(a[0] - ox, a[1] - oz), Math.hypot(b[0] - ox, b[1] - oz));
            if (k != 0) return k;
            return Double.compare(Math.hypot(a[0] - tx, a[1] - tz), Math.hypot(b[0] - tx, b[1] - tz));
        });
        return out;
    }

    private static double clamp(double v, double lo, double hi) { return Math.max(lo, Math.min(hi, v)); }

    private static double dist(double ax, double ay, double az, double bx, double by, double bz) {
        double dx = ax - bx, dy = ay - by, dz = az - bz;
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }
}
