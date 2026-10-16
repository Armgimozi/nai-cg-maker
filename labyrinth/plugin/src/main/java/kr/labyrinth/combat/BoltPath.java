package kr.labyrinth.combat;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 마법탄 한 발의 길 (0.3.6.1, 순수 — 단위 테스트 대상). 엔티티를 만들지 않고 서버가 틱마다 한 걸음씩 선분을 따라가며 맞는지 본다.
 * <ul>
 *   <li>시작 = 눈 위치, 방향 = 바라보는 쪽 (조준선 그대로). 한 걸음 = min(속도, 남은 거리). 다 가면 사라진다.</li>
 *   <li>맞는 판정 ({@link #firstHit}): 이번 걸음 선분이 (후보 히트박스 + 굵기) 상자를 처음 지나는 곳. 벽(블록)이 더 가까우면 그 뒤는 못 맞힌다.
 *       시작점이 이미 상자 안이면 거리 0 (몸을 붙인 큰 보스). 키운 테두리에만 닿았으면 그 자리에서 몸까지 막는 블록이 없을 때만
 *       ({@link Sight} — 철창·유리판·닫힌 문 바로 뒤의 몹은 못 맞힌다).</li>
 *   <li>후보는 런타임이 고른다 — 살아 있는 적(몹·보스의 실제 몸 엔티티·PvP 상대)만. 모델 파트(ItemDisplay)·아군·NPC·갑옷 거치대는 후보가 아니다.</li>
 * </ul>
 */
public final class BoltPath {

    private final Vector pos;
    private final Vector dir;
    private final double speed;
    private final double range;
    private double travelled;

    /** @param dir 방향 (길이는 상관없음 — 단위 벡터로 바꾼다, 0 이면 +z) */
    public BoltPath(Vector start, Vector dir, double speed, double range) {
        this.pos = start.clone();
        Vector d = dir.clone();
        this.dir = d.lengthSquared() < 1e-12 ? new Vector(0, 0, 1) : d.normalize();
        this.speed = Math.max(0.05, speed);
        this.range = Math.max(0, range);
    }

    /** 이번 걸음 길이 (남은 거리가 속도보다 짧으면 남은 거리). */
    public double nextStep() { return Math.max(0, Math.min(speed, range - travelled)); }

    public boolean done() { return travelled >= range - 1e-9; }

    public Vector position() { return pos.clone(); }

    public Vector direction() { return dir.clone(); }

    public double travelled() { return travelled; }

    public double range() { return range; }

    /** 지금 자리에서 d 만큼 앞. */
    public Vector ahead(double d) { return pos.clone().add(dir.clone().multiply(d)); }

    /** d 만큼 나아간다 (남은 거리까지만). */
    public void advance(double d) {
        double step = Math.max(0, Math.min(d, range - travelled));
        pos.add(dir.clone().multiply(step));
        travelled += step;
    }

    /** 후보 하나 — 대상과 그 히트박스. */
    public record Candidate<T>(T target, BoundingBox box) {}

    /** 맞은 대상과 걸음 시작점에서의 거리. */
    public record Hit<T>(T target, double distance) {}

    /** 원래 히트박스를 이만큼 줄인 상자 안의 가장 가까운 점까지 시야를 본다 (바닥·벽에 붙은 면이 블록 면과 딱 맞닿아도 막힌 것으로 보지 않게). */
    public static final double SIGHT_INSET = 0.05;

    /**
     * 키운 상자(굵기 radius)에만 닿고 원래 히트박스에는 선분이 직접 닿지 않은 후보가 정말 보이는가 — 얇은 블록(철창·유리판·닫힌 문)
     * 바로 뒤에 붙은 몹을 키운 상자가 블록 앞으로 삐져나와 맞히지 않게.
     */
    @FunctionalInterface
    public interface Sight<T> {
        /**
         * @param at      선분이 키운 상자에 닿은 자리
         * @param nearest 원래 히트박스(조금 줄인 것) 안에서 at 에 가장 가까운 점 — at → nearest 사이에 막는 블록이 없으면 보인다
         */
        boolean clear(Candidate<T> candidate, Vector at, Vector nearest);
    }

    /** {@link #firstHit(Vector, Vector, double, double, double, Collection, Sight)} 를 시야 검사 없이. */
    public static <T> Hit<T> firstHit(Vector from, Vector dir, double len, double radius, double blockDistance,
                                      Collection<Candidate<T>> candidates) {
        return firstHit(from, dir, len, radius, blockDistance, candidates, null);
    }

    /**
     * from 에서 dir 로 len 만큼 가는 동안 처음 닿는 후보. 상자는 radius 만큼 키워서 본다.
     * 원래 히트박스에 선분이 직접 닿으면(벽보다 앞) 그대로 맞고, 키운 테두리에만 닿았으면 {@code sight} 가 보인다고 할 때만 맞는다
     * (안 보이면 다음으로 가까운 후보).
     * @param blockDistance 이번 걸음에서 블록에 닿는 거리 (없으면 {@link Double#POSITIVE_INFINITY}) — 그보다 먼 후보는 벽 뒤라 못 맞힌다
     * @param sight         null 이면 시야 검사 없음
     * @return 없으면 null
     */
    public static <T> Hit<T> firstHit(Vector from, Vector dir, double len, double radius, double blockDistance,
                                      Collection<Candidate<T>> candidates, Sight<T> sight) {
        if (candidates == null || candidates.isEmpty() || len < 0) return null;
        Vector d = dir.clone();
        if (d.lengthSquared() < 1e-12) return null;
        d.normalize();
        double limit = Math.min(len, blockDistance < 0 ? 0 : blockDistance);
        List<Hit<Candidate<T>>> order = new ArrayList<>(candidates.size());
        for (Candidate<T> c : candidates) {
            if (c == null || c.box() == null) continue;
            double dist = entry(from, d, limit, c.box().clone().expand(Math.max(0, radius)));
            if (!Double.isNaN(dist)) order.add(new Hit<>(c, dist));
        }
        order.sort(Comparator.comparingDouble(Hit::distance));
        for (Hit<Candidate<T>> h : order) {
            Candidate<T> c = h.target();
            boolean direct = !Double.isNaN(entry(from, d, limit, c.box()));
            if (!direct && sight != null) {
                Vector at = from.clone().add(d.clone().multiply(h.distance()));
                if (!sight.clear(c, at, nearestInside(c.box(), at, SIGHT_INSET))) continue;
            }
            return new Hit<>(c.target(), h.distance());
        }
        return null;
    }

    /** 상자를 inset 만큼(한 축이 얇으면 그 절반까지만) 줄인 상자 안에서 p 에 가장 가까운 점. */
    public static Vector nearestInside(BoundingBox box, Vector p, double inset) {
        double ix = Math.min(inset, box.getWidthX() / 4), iy = Math.min(inset, box.getHeight() / 4), iz = Math.min(inset, box.getWidthZ() / 4);
        return new Vector(clamp(p.getX(), box.getMinX() + ix, box.getMaxX() - ix),
                clamp(p.getY(), box.getMinY() + iy, box.getMaxY() - iy),
                clamp(p.getZ(), box.getMinZ() + iz, box.getMaxZ() - iz));
    }

    private static double clamp(double v, double lo, double hi) { return lo > hi ? (lo + hi) / 2 : Math.max(lo, Math.min(hi, v)); }

    /** 선분이 상자에 들어가는 거리 (시작점이 안이면 0, 안 닿으면 NaN). */
    static double entry(Vector from, Vector unitDir, double limit, BoundingBox box) {
        if (box.contains(from)) return 0;
        if (limit <= 0) return Double.NaN;
        RayTraceResult r = box.rayTrace(from, unitDir, limit);
        if (r == null) return Double.NaN;
        double dist = r.getHitPosition().distance(from);
        return dist <= limit + 1e-9 ? dist : Double.NaN;
    }

    /**
     * 눈 → 손(지팡이 끝 쪽) 어긋남 (월드 좌표). 화면 오른쪽 아래, 왼손잡이 설정이면 왼쪽 아래. 맞는 판정은 눈의 조준선 그대로이고 이것은 꼬리
     * 입자만 옮긴다 — 입자가 조준선 위에만 있으면 쏜 사람 화면에서는 모두 조준점 한 곳에 겹쳐 날아가는 게 안 보인다.
     * @param yawDeg 바라보는 방향 (마인크래프트 yaw, 0 = 남쪽 +z)
     * @param dir    조준선 방향 (단위 벡터)
     */
    public static Vector handOffset(float yawDeg, Vector dir, boolean leftHanded, double right, double down) {
        double y = Math.toRadians(yawDeg);
        Vector r = new Vector(-Math.cos(y), 0, -Math.sin(y)); // 오른쪽 (수평)
        Vector d = dir.clone();
        if (d.lengthSquared() < 1e-12) d = new Vector(0, 0, 1);
        d.normalize();
        Vector up = r.clone().crossProduct(d); // 화면 위쪽
        if (up.lengthSquared() < 1e-12) up = new Vector(0, 1, 0);
        up.normalize();
        return r.multiply(leftHanded ? -right : right).subtract(up.multiply(down));
    }

    /** 꼬리 입자 자리: 조준선 위 t 칸 + 손 어긋남 × (1 − t/converge) — converge 칸에서 조준선과 만난다. */
    public static Vector visualPoint(Vector eye, Vector unitDir, Vector handOffset, double t, double converge) {
        double k = converge <= 0 ? 0 : Math.max(0, 1 - t / converge);
        return eye.clone().add(unitDir.clone().multiply(t)).add(handOffset.clone().multiply(k));
    }

    /** 이번 걸음이 지나는 곳을 감싸는 상자 (주변 엔티티 찾기용) — 양 끝을 잇고 pad 만큼 키움. */
    public static BoundingBox segmentBox(Vector from, Vector dir, double len, double pad) {
        Vector d = dir.clone();
        if (d.lengthSquared() > 1e-12) d.normalize();
        Vector to = from.clone().add(d.multiply(Math.max(0, len)));
        return BoundingBox.of(from, to).expand(Math.max(0, pad));
    }
}
