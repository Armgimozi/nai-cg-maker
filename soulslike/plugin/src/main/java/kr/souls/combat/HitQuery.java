package kr.souls.combat;

import kr.souls.vfx.Footprint;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * 공격 판정 (3.6): 눈높이에서 시작하는 부채꼴 (휩쓸기: 안의 모두) 또는 직선 (찌르기: 첫 대상만). 모양은 vfx/Footprint (skyblock 에서
 * 그대로 옮긴 것, R15) 이고 여기서는 상자 가장자리까지의 거리 (Targets.distToBox 와 같은 셈) 와 위아래 띠를 더한다. 셈은 순수 (13.1 의
 * HitQueryTest): 세계를 보지 않고 눈·방향·상자만 받는다. 대상 모으기 (Foes.near, 둘레의 플레이어) 와 한 동작에 한 번은 MoveRunner 가 한다.
 * <ul>
 *   <li>사거리: 눈에서 상자 가장자리까지 (3차원) ≤ range.</li>
 *   <li>위아래: 상자가 눈높이 ± vertical 띠에 걸린다.</li>
 *   <li>모양: 눈높이로 눌러 둔 상자의 세 점 (눈에 가장 가까운 점, 축에 가장 가까운 점, 가운데) 가운데 하나라도 Footprint 안이면 든다.
 *       큰 상자는 가장자리부터 맞는다.</li>
 *   <li>차례: 부채꼴은 가까운 차례, 직선은 축을 따라 가까운 차례 (찌르기는 첫 것만 맞힌다).</li>
 * </ul>
 * 조준은 십자선 (그 사람이 보는 수평 방향). {@link AimProvider} 는 표적 고정 (P8) 이 끼우는 자리다.
 */
public final class HitQuery {
    /** 모양 */
    public enum Shape { CONE, LINE }

    /**
     * 판정 모양 하나. angle: 부채꼴의 전체 각 (도), range: 사거리 (칸), width: 직선의 폭 (칸, Footprint 가 몸 0.5 를 더한다),
     * vertical: 눈높이 위아래 (combat.moves.vertical).
     */
    public record Spec(Shape shape, double angle, double range, double width, double vertical) {
        public Spec withVertical(double v) {
            return new Spec(shape, angle, range, width, v);
        }

        public boolean thrust() {
            return shape == Shape.LINE;
        }
    }

    /** 조준 방향 (수평, 길이 1). 표적 고정 (P8) 이 바꾼다. */
    @FunctionalInterface
    public interface AimProvider {
        Vector aim(Player p, long now);
    }

    /** 기본 조준: 그 사람이 보는 수평 방향 (십자선). */
    public static final AimProvider CROSSHAIR = (p, now) -> yawDir(p.getLocation().getYaw());

    private HitQuery() {}

    /** yaw (도) 의 수평 방향 (마인크래프트: 0 = +z, 90 = −x). */
    public static Vector yawDir(float yaw) {
        double r = Math.toRadians(yaw);
        return new Vector(-Math.sin(r), 0, Math.cos(r));
    }

    /** 점 (x, y, z) 에서 상자 가장자리까지 (안이면 0). */
    public static double distToBox(BoundingBox b, double x, double y, double z) {
        double dx = Math.max(Math.max(b.getMinX() - x, 0), x - b.getMaxX());
        double dy = Math.max(Math.max(b.getMinY() - y, 0), y - b.getMaxY());
        double dz = Math.max(Math.max(b.getMinZ() - z, 0), z - b.getMaxZ());
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }

    /**
     * 상자 b 가 판정 안이면 차례의 열쇠 (부채꼴: 가장자리까지의 거리, 직선: 축을 따른 거리), 아니면 −1.
     * @param eye 눈 (세계는 보지 않는다. null 세계도 된다)
     * @param dir 조준 (수평으로 눕혀 쓴다)
     */
    public static double test(Location eye, Vector dir, Spec sp, BoundingBox b) {
        if (eye == null || dir == null || sp == null || b == null) return -1;
        Vector d = dir.clone().setY(0);
        if (d.lengthSquared() < 1e-9) return -1;
        d.normalize();
        double ex = eye.getX(), ey = eye.getY(), ez = eye.getZ();
        // 위아래 띠
        if (b.getMinY() > ey + sp.vertical() || b.getMaxY() < ey - sp.vertical()) return -1;
        // 사거리 (가장자리까지)
        double dist = distToBox(b, ex, ey, ez);
        if (dist > sp.range() + 1e-9) return -1;
        Location base = new Location(eye.getWorld(), ex, ey, ez);
        Footprint fp = sp.shape() == Shape.LINE
                ? Footprint.line(base, d, sp.range(), sp.width())
                : Footprint.cone(base, d, Math.toRadians(Math.max(0, Math.min(360, sp.angle())) / 2.0), sp.range());
        double cx = (b.getMinX() + b.getMaxX()) / 2, cz = (b.getMinZ() + b.getMaxZ()) / 2;
        // 축 위의 점 (상자 가운데를 축에 비춘 곳, 사거리 안) 에 가장 가까운 상자 점
        double t = Math.max(0, Math.min(sp.range(), (cx - ex) * d.getX() + (cz - ez) * d.getZ()));
        double ax = ex + d.getX() * t, az = ez + d.getZ() * t;
        double[][] pts = {
                {clamp(ex, b.getMinX(), b.getMaxX()), clamp(ez, b.getMinZ(), b.getMaxZ())},
                {clamp(ax, b.getMinX(), b.getMaxX()), clamp(az, b.getMinZ(), b.getMaxZ())},
                {cx, cz}};
        boolean in = false;
        double along = Double.MAX_VALUE;
        for (double[] q : pts) {
            Location at = new Location(eye.getWorld(), q[0], ey, q[1]);
            if (fp.contains(at)) {
                in = true;
                along = Math.min(along, Math.max(0, (q[0] - ex) * d.getX() + (q[1] - ez) * d.getZ()));
            }
        }
        if (!in) return -1;
        return sp.shape() == Shape.LINE ? along : dist;
    }

    /** 상자들 가운데 판정 안의 것의 번호를 맞는 차례로 (직선이면 찌르기라 맞히는 쪽이 첫 것만 쓴다). */
    public static List<Integer> order(Location eye, Vector dir, Spec sp, List<BoundingBox> boxes) {
        List<double[]> got = new ArrayList<>();
        for (int i = 0; i < boxes.size(); i++) {
            double k = test(eye, dir, sp, boxes.get(i));
            if (k >= 0) got.add(new double[] {i, k});
        }
        got.sort(Comparator.comparingDouble(x -> x[1]));
        List<Integer> out = new ArrayList<>();
        for (double[] x : got) out.add((int) x[0]);
        return out;
    }

    private static double clamp(double v, double lo, double hi) {
        return Math.max(lo, Math.min(hi, v));
    }
}
