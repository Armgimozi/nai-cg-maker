package kr.labyrinth.bosses;

import java.util.ArrayList;
import java.util.List;

/**
 * 보스 기본 공격이 닿는가 (bs362, Bukkit 무관 — 단위 테스트 대상).
 * <p>
 * <b>옛 규칙</b>: 보스 중심 ↔ 플레이어 발 수평 거리 ≤ reach (= 2.0 + 0.7 × scale), 높이 차 &lt; 3.5.
 * <b>맞대응 규칙</b>: 플레이어 눈 → 보스 히트박스 겉면 ≤ 플레이어 손 닿음(바닐라 3.0) — 플레이어가 칼로 칠 수 있는 거리면
 * 보스도 친다. 히트박스가 큰 보스(골렘·판다 바탕)는 옛 규칙보다 이쪽이 약 1칸 길다 — 그 띠가 "플레이어만 치는 자리"였다.
 * <p>
 * 둘 중 하나면 닿고, 어느 쪽이든 {@link #sees 시야}(플레이어 눈과 히트박스 사이에 막는 블록 없음)가 있어야 한다 — 벽 너머로 안 친다.
 * 휘두른 뒤 3틱 뒤 판정은 둘 다 {@link #CONFIRM_SLACK} 만큼 여유 (옛 규칙 그대로).
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

    /** 옛 규칙 (중심 ↔ 발 수평 ≤ reach, 높이 차 &lt; 3.5). */
    public static boolean legacy(double horizontal, double dy, double reach) {
        return horizontal <= reach && Math.abs(dy) < LEGACY_DY;
    }

    /** 맞대응 규칙 (플레이어 눈 → 보스 상자 ≤ 플레이어 손 닿음). */
    public static boolean mirror(double eyeToBox, double playerReach) {
        return eyeToBox <= playerReach;
    }

    /**
     * 기하로 닿는가 (시야는 따로 {@link #sees}). slack = 0 은 휘두를 때, {@link #CONFIRM_SLACK} 는 3틱 뒤 맞힐 때.
     * @param horizontal 보스 중심 ↔ 플레이어 발 수평 거리
     * @param dy         플레이어 발 − 보스 발 높이
     * @param reach      보스 옛 reach
     * @param eyeToBox   플레이어 눈 → 보스 히트박스
     */
    public static boolean inReach(double horizontal, double dy, double reach, double eyeToBox, double playerReach, double slack) {
        return legacy(horizontal, dy, reach + slack) || mirror(eyeToBox, playerReach + slack);
    }

    /** 플레이어 손 닿음 속성값 → 맞대응 거리 (바닐라 3.0 아래로는 줄이지 않는다). */
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

    /** 이미 쏜 점과 0.3칸 안이면 건너뛴다 (false). */
    private static boolean tryRay(double ex, double ey, double ez, double x, double y, double z, Ray ray, List<double[]> tried) {
        for (double[] t : tried) if (dist(t[0], t[1], t[2], x, y, z) < 0.3) return false;
        if (tried.size() >= MAX_SIGHT_RAYS) return false;
        tried.add(new double[] {x, y, z});
        return ray.clear(ex, ey, ez, x, y, z);
    }

    // ── 직접 다가가기·도약 ───────────────────────────────────────────────

    /**
     * 걷기와 같은 직접 다가가기 속도 (블록/틱). 바닐라 땅 이동의 정상 속도 ≈ 2.16 × 이동 속도² (마찰 0.546, 입력 × 0.98) —
     * 1층 그로브(0.24)가 길찾기로 걸을 때 실서버 0.127칸/틱과 맞는다.
     */
    public static double walkSpeed(double movementSpeed) {
        double s = Math.max(0, movementSpeed);
        return Math.max(0.04, Math.min(0.3, 2.16 * s * s));
    }

    /** 도약 착지 후보 반경(대상 기준). 0 = 대상 자리 바로 위(내려찍기). */
    static final double[] LANDING_RADII = {0, 0.6, 1.2, 1.8, 2.4, 3.0, 3.6};
    /** 고리마다 방향 수. */
    static final int LANDING_DIRS = 16;

    /** 도약 착지 후보 (대상 둘레 고리, 가까운 순 · 같은 고리는 동쪽부터 시계 반대 — 결정적). */
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

    /**
     * 도약 궤적 표본 (양 끝 제외). 궤적은 "뛰어오르기 → 건너가기 → 내려앉기" 모양이라 벽·받침에 붙어 서 있어도
     * 먼저 위로 솟는다 ({@link #arcAt}). 표본 간격(3차원) ≤ step — 한 칸 두께 벽도 건너뛰지 않게.
     * @return {x, y, z} 목록 (발 위치)
     */
    public static List<double[]> arc(double sx, double sy, double sz, double ex, double ey, double ez, double apex, double step) {
        double horizontal = Math.hypot(ex - sx, ez - sz);
        double worst = 3 * horizontal + 6 * Math.max(0, apex) + 3 * Math.abs(ey - sy); // 단위 t 당 최대 이동
        int n = Math.max(2, (int) Math.ceil(worst / Math.max(0.05, step)));
        List<double[]> out = new ArrayList<>();
        for (int i = 1; i < n; i++) out.add(arcAt(sx, sy, sz, ex, ey, ez, apex, i / (double) n));
        return out;
    }

    /**
     * 궤적 위 t (0~1) 지점: 처음 1/4 동안 apex 만큼 솟고, 가운데 절반 동안 수평으로 건너가고(높이는 시작 → 끝 높이로),
     * 마지막 1/4 동안 내려앉는다. 수평·높이 모두 부드럽게 (smoothstep).
     */
    public static double[] arcAt(double sx, double sy, double sz, double ex, double ey, double ez, double apex, double t) {
        double k = Math.max(0, Math.min(1, t));
        double across = smooth((k - 0.25) / 0.5);
        double bump = k < 0.25 ? smooth(k / 0.25) : k > 0.75 ? smooth((1 - k) / 0.25) : 1;
        return new double[] {sx + (ex - sx) * across, sy + (ey - sy) * across + Math.max(0, apex) * bump, sz + (ez - sz) * across};
    }

    private static double smooth(double x) {
        double c = Math.max(0, Math.min(1, x));
        return c * c * (3 - 2 * c);
    }

    /** 도약 높이 후보: 짧은 도약은 낮게, 막히면 더 높게. */
    public static double[] apexOptions(double horizontal) {
        double base = Math.max(1.2, Math.min(3.0, 1.0 + horizontal * 0.25));
        return new double[] {base, base + 1.5, base + 3.0};
    }

    /** 비행 틱 수 (0.6칸/틱 · 8~16틱). */
    public static int flightTicks(double horizontal) {
        return (int) Math.max(8, Math.min(16, Math.round(horizontal / 0.6)));
    }

    private static double clamp(double v, double lo, double hi) { return Math.max(lo, Math.min(hi, v)); }

    private static double dist(double ax, double ay, double az, double bx, double by, double bz) {
        double dx = ax - bx, dy = ay - by, dz = az - bz;
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }
}
