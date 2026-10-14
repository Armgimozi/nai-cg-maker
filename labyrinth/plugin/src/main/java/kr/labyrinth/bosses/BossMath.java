package kr.labyrinth.bosses;

/**
 * 보스 패턴의 순수 수학 (Bukkit 무관 — 단위 테스트 대상): 경고 장판 도형 판정(GDD §8.1), 파티 인원 공식(GDD §8.4),
 * 각도·방향 변환. 좌표는 전부 수평(x, z) 평면, 각도는 도(degree).
 */
public final class BossMath {

    private BossMath() {}

    /** GDD §8.1: 장판 판정 높이 차 한계 (블록). */
    public static final double HEIGHT_TOLERANCE = 3.0;

    public static boolean heightOk(double originY, double y) {
        return Math.abs(y - originY) <= HEIGHT_TOLERANCE;
    }

    public static double dist2(double ax, double az, double bx, double bz) {
        double dx = ax - bx, dz = az - bz;
        return dx * dx + dz * dz;
    }

    /** circle: 중심 거리 ≤ r. */
    public static boolean inCircle(double cx, double cz, double r, double px, double pz) {
        return dist2(cx, cz, px, pz) <= r * r + 1e-9;
    }

    /** ring(도넛): inner &lt; 거리 ≤ r. */
    public static boolean inRing(double cx, double cz, double inner, double r, double px, double pz) {
        double d2 = dist2(cx, cz, px, pz);
        return d2 > inner * inner && d2 <= r * r + 1e-9;
    }

    /** line/rect/arrow: 선분까지 거리 ≤ width/2, 0 ≤ 투영 ≤ length. dir 은 정규화되지 않아도 된다. */
    public static boolean inLine(double ox, double oz, double dirX, double dirZ, double length, double width,
                                 double px, double pz) {
        double len = Math.sqrt(dirX * dirX + dirZ * dirZ);
        if (len < 1e-9) return false;
        double ux = dirX / len, uz = dirZ / len;
        double rx = px - ox, rz = pz - oz;
        double along = rx * ux + rz * uz;
        if (along < -1e-9 || along > length + 1e-9) return false;
        double side = Math.abs(rx * -uz + rz * ux);
        return side <= width / 2 + 1e-9;
    }

    /** cone(부채꼴): 거리 ≤ length 이고 방향과 각도 ≤ angle/2. 꼭짓점 바로 위(거리 0)는 맞음. */
    public static boolean inCone(double ox, double oz, double dirX, double dirZ, double angleDeg, double length,
                                 double px, double pz) {
        double rx = px - ox, rz = pz - oz;
        double d2 = rx * rx + rz * rz;
        if (d2 > length * length + 1e-9) return false;
        if (d2 < 0.25) return true; // 보스 발밑 (0.5블록)
        double len = Math.sqrt(dirX * dirX + dirZ * dirZ);
        if (len < 1e-9) return false;
        double cos = (rx * dirX + rz * dirZ) / (Math.sqrt(d2) * len);
        double half = Math.toRadians(Math.min(360, angleDeg) / 2);
        return cos >= Math.cos(half) - 1e-9;
    }

    /** tile: 격자 (tileX, tileZ) 의 정사각형 안. 격자 원점 (gx, gz), 한 변 size. */
    public static boolean inTile(double gx, double gz, int tileX, int tileZ, double size, double px, double pz) {
        double x0 = gx + tileX * size, z0 = gz + tileZ * size;
        return px >= x0 && px < x0 + size && pz >= z0 && pz < z0 + size;
    }

    /** 위치가 속한 타일 좌표. */
    public static int tileOf(double origin, double size, double p) {
        return (int) Math.floor((p - origin) / size);
    }

    /** 선분 (a→b) 과 점 p 의 수평 거리² (돌진 경로 판정). */
    public static double segmentDist2(double ax, double az, double bx, double bz, double px, double pz) {
        double vx = bx - ax, vz = bz - az;
        double l2 = vx * vx + vz * vz;
        if (l2 < 1e-12) return dist2(ax, az, px, pz);
        double t = Math.max(0, Math.min(1, ((px - ax) * vx + (pz - az) * vz) / l2));
        return dist2(ax + vx * t, az + vz * t, px, pz);
    }

    /** 마인크래프트 yaw(도) — 방향 (dx, dz) 를 바라보는 값. yaw 0 = +Z(남), 90 = −X(서). */
    public static float yawOf(double dx, double dz) {
        if (Math.abs(dx) < 1e-9 && Math.abs(dz) < 1e-9) return 0f;
        return (float) Math.toDegrees(Math.atan2(-dx, dz));
    }

    public static double yawX(double yawDeg) { return -Math.sin(Math.toRadians(yawDeg)); }

    public static double yawZ(double yawDeg) { return Math.cos(Math.toRadians(yawDeg)); }

    /** 두 yaw 의 차 (−180~180]. */
    public static float yawDelta(float from, float to) {
        float d = (to - from) % 360f;
        if (d > 180f) d -= 360f;
        if (d <= -180f) d += 360f;
        return d;
    }

    /** from 에서 to 로 최대 maxStep 도만 회전. */
    public static float turn(float from, float to, float maxStep) {
        float d = yawDelta(from, to);
        if (Math.abs(d) <= maxStep) return to;
        return from + Math.signum(d) * maxStep;
    }

    // ── 파티 인원 공식 (GDD §8.4) ────────────────────────────────────────

    /** {@code base + floor((n−1) × perMember)}. */
    public static int count(double base, double perMember, int partySize) {
        int n = Math.max(1, partySize);
        return (int) Math.floor(base + Math.floor((n - 1) * perMember) + 1e-9);
    }

    /** {@code base + floor((n−1) / k)} (k ≤ 0 이면 base). */
    public static int countPerMembers(double base, double k, int partySize) {
        int n = Math.max(1, partySize);
        if (k <= 0) return (int) Math.floor(base + 1e-9);
        return (int) Math.floor(base + Math.floor((n - 1) / k) + 1e-9);
    }

    /** 오브젝트 HP: {@code hp × (1 + perMember × (n−1))}. */
    public static double objectHp(double hp, double perMember, int partySize) {
        int n = Math.max(1, partySize);
        return hp * (1 + perMember * (n - 1));
    }

    /** 모이기 피해 분배: total ÷ max(minShare, 원 안 인원). */
    public static double shareDamage(double total, int inside, int minShare) {
        return total / Math.max(Math.max(1, minShare), inside);
    }

    /** 원 위 균등 배치 각도(도) 목록에서, 금지 방향(도) ± margin 을 피하도록 시작 각을 돌린 결과. */
    public static double[] ringAngles(int count, double forbiddenDeg, double marginDeg) {
        double[] out = new double[Math.max(0, count)];
        if (count <= 0) return out;
        double step = 360.0 / count;
        double start = forbiddenDeg + step / 2;
        // step/2 가 margin 보다 작으면 금지 방향이 두 점 사이 가운데 오도록 이미 최선
        for (int i = 0; i < count; i++) out[i] = norm(start + step * i);
        if (step / 2 < marginDeg && count > 1) {
            // 너무 촘촘하면 금지 구역 바깥 호에 다시 균등 배치
            double arc = 360 - 2 * marginDeg;
            double s2 = arc / count;
            for (int i = 0; i < count; i++) out[i] = norm(forbiddenDeg + marginDeg + s2 * (i + 0.5));
        }
        return out;
    }

    /** 각도(도) → [0, 360). */
    public static double norm(double deg) {
        double d = deg % 360.0;
        return d < 0 ? d + 360 : d;
    }

    /** 두 각도(도) 사이 최소 차. */
    public static double angleGap(double a, double b) {
        double d = Math.abs(norm(a) - norm(b));
        return Math.min(d, 360 - d);
    }

    /**
     * 수학 각도(도, 0 = +X, 90 = +Z) → 방향 벡터 x 성분. 아레나 배치(기둥·밸브)는 이 규칙을 쓴다.
     * 남쪽 계단 구역(중심 +2~+11 z) = 각도 90°.
     */
    public static double ax(double deg) { return Math.cos(Math.toRadians(deg)); }

    public static double az(double deg) { return Math.sin(Math.toRadians(deg)); }

    /** 남쪽 계단 구역 (중심 기준 |x| ≤ halfWidth, +2 ≤ z ≤ +11) 과 겹치는가 — 보스가 블록을 놓으면 안 되는 곳. */
    public static boolean inStairZone(double dx, double dz, double halfWidth) {
        return Math.abs(dx) <= halfWidth && dz >= 1.5 && dz <= 11.5;
    }
}
