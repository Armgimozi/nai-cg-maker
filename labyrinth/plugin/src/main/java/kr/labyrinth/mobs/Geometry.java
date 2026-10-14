package kr.labyrinth.mobs;

/**
 * 경고 장판 판정 도형 (GDD §8.1) — 수평(x,z) 기준. Bukkit 무관 — 단위 테스트 대상.
 * 방향(dirX, dirZ)은 정규화하지 않아도 된다(내부에서 정규화).
 */
public final class Geometry {

    /** 높이 차 허용 (원·도넛·부채꼴·선 공통, GDD §8.1). */
    public static final double MAX_HEIGHT_DIFF = 3.0;

    private Geometry() {}

    public static double dist2(double ax, double az, double bx, double bz) {
        double dx = ax - bx, dz = az - bz;
        return dx * dx + dz * dz;
    }

    /** 중심 거리 ≤ r. */
    public static boolean inCircle(double cx, double cz, double r, double px, double pz) {
        return dist2(cx, cz, px, pz) <= r * r;
    }

    /** inner &lt; 거리 ≤ r. */
    public static boolean inRing(double cx, double cz, double inner, double r, double px, double pz) {
        double d2 = dist2(cx, cz, px, pz);
        return d2 > inner * inner && d2 <= r * r;
    }

    /** 원점에서 방향으로 length, 폭 width 의 직사각형 (선분까지 거리 ≤ width/2, 0 ≤ 투영 ≤ length). */
    public static boolean inLine(double ox, double oz, double dirX, double dirZ, double length, double width,
                                 double px, double pz) {
        double len = Math.sqrt(dirX * dirX + dirZ * dirZ);
        if (len < 1e-9) return inCircle(ox, oz, width / 2, px, pz);
        double ux = dirX / len, uz = dirZ / len;
        double rx = px - ox, rz = pz - oz;
        double proj = rx * ux + rz * uz;
        if (proj < 0 || proj > length) return false;
        double perp = Math.abs(rx * uz - rz * ux);
        return perp <= width / 2;
    }

    /** 원점에서 방향으로 각도 angle(도), 길이 length 의 부채꼴. 원점 바로 위(0.3블록 이내)는 포함. */
    public static boolean inCone(double ox, double oz, double dirX, double dirZ, double angleDeg, double length,
                                 double px, double pz) {
        double rx = px - ox, rz = pz - oz;
        double d2 = rx * rx + rz * rz;
        if (d2 > length * length) return false;
        if (d2 < 0.09) return true;
        double len = Math.sqrt(dirX * dirX + dirZ * dirZ);
        if (len < 1e-9) return true;
        double cos = (rx * dirX + rz * dirZ) / (Math.sqrt(d2) * len);
        return cos >= Math.cos(Math.toRadians(Math.min(360, Math.max(0, angleDeg)) / 2.0)) - 1e-9;
    }

    /** 높이 차 검사. */
    public static boolean heightOk(double cy, double py) {
        return Math.abs(py - cy) <= MAX_HEIGHT_DIFF;
    }

    /** 선분 (ax,ay,az)-(bx,by,bz) 과 점 사이 최단 거리 제곱 (3D, 투사체·돌진 판정). */
    public static double segmentDist2(double ax, double ay, double az, double bx, double by, double bz,
                                      double px, double py, double pz) {
        double vx = bx - ax, vy = by - ay, vz = bz - az;
        double wx = px - ax, wy = py - ay, wz = pz - az;
        double vv = vx * vx + vy * vy + vz * vz;
        double t = vv < 1e-12 ? 0 : Math.max(0, Math.min(1, (wx * vx + wy * vy + wz * vz) / vv));
        double cx = ax + vx * t - px, cy = ay + vy * t - py, cz = az + vz * t - pz;
        return cx * cx + cy * cy + cz * cz;
    }

    /** yaw(도, 마인크래프트 규칙: 0 = +Z, 90 = −X) → 방향 x 성분. */
    public static double yawX(double yawDeg) { return -Math.sin(Math.toRadians(yawDeg)); }

    public static double yawZ(double yawDeg) { return Math.cos(Math.toRadians(yawDeg)); }

    /** 방향 → yaw(도). */
    public static float yawOf(double dx, double dz) {
        return (float) Math.toDegrees(Math.atan2(-dx, dz));
    }

    /** 각도 차 (−180, 180]. */
    public static double wrapDegrees(double d) {
        d %= 360.0;
        if (d > 180) d -= 360;
        if (d <= -180) d += 360;
        return d;
    }
}
