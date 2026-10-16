package kr.labyrinth.combat;

import java.util.Collection;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 마법탄 한 발의 길 (0.3.6.1, 순수 — 단위 테스트 대상). 엔티티를 만들지 않고 서버가 틱마다 한 걸음씩 선분을 따라가며 맞는지 본다.
 * <ul>
 *   <li>시작 = 눈 위치, 방향 = 바라보는 쪽 (조준선 그대로). 한 걸음 = min(속도, 남은 거리). 다 가면 사라진다.</li>
 *   <li>맞는 판정 ({@link #firstHit}): 이번 걸음 선분이 (후보 히트박스 + 굵기) 상자를 처음 지나는 곳. 벽(블록)이 더 가까우면 그 뒤는 못 맞힌다.
 *       시작점이 이미 상자 안이면 거리 0 (몸을 붙인 큰 보스).</li>
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

    /**
     * from 에서 dir 로 len 만큼 가는 동안 처음 닿는 후보. 상자는 radius 만큼 키워서 본다.
     * @param blockDistance 이번 걸음에서 블록에 닿는 거리 (없으면 {@link Double#POSITIVE_INFINITY}) — 그보다 먼 후보는 벽 뒤라 못 맞힌다
     * @return 없으면 null
     */
    public static <T> Hit<T> firstHit(Vector from, Vector dir, double len, double radius, double blockDistance,
                                      Collection<Candidate<T>> candidates) {
        if (candidates == null || candidates.isEmpty() || len < 0) return null;
        Vector d = dir.clone();
        if (d.lengthSquared() < 1e-12) return null;
        d.normalize();
        double limit = Math.min(len, blockDistance < 0 ? 0 : blockDistance);
        Hit<T> best = null;
        for (Candidate<T> c : candidates) {
            if (c == null || c.box() == null) continue;
            double dist = entry(from, d, limit, c.box().clone().expand(Math.max(0, radius)));
            if (Double.isNaN(dist)) continue;
            if (best == null || dist < best.distance()) best = new Hit<>(c.target(), dist);
        }
        return best;
    }

    /** 선분이 상자에 들어가는 거리 (시작점이 안이면 0, 안 닿으면 NaN). */
    static double entry(Vector from, Vector unitDir, double limit, BoundingBox box) {
        if (box.contains(from)) return 0;
        if (limit <= 0) return Double.NaN;
        RayTraceResult r = box.rayTrace(from, unitDir, limit);
        if (r == null) return Double.NaN;
        double dist = r.getHitPosition().distance(from);
        return dist <= limit + 1e-9 ? dist : Double.NaN;
    }

    /** 이번 걸음이 지나는 곳을 감싸는 상자 (주변 엔티티 찾기용) — 양 끝을 잇고 pad 만큼 키움. */
    public static BoundingBox segmentBox(Vector from, Vector dir, double len, double pad) {
        Vector d = dir.clone();
        if (d.lengthSquared() > 1e-12) d.normalize();
        Vector to = from.clone().add(d.multiply(Math.max(0, len)));
        return BoundingBox.of(from, to).expand(Math.max(0, pad));
    }
}
