package kr.labyrinth.items.weaponskills;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import kr.labyrinth.Services;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 무기 스킬의 <b>단일</b> 대상 선택 규칙. 적/아군 판정은 전부 {@code services.targets()}(pvp.TargetFilter: 몹과 다른 파티
 * 플레이어가 적, 같은 파티원은 아군 — GDD §18)에 맡기고, 여기서는 도형(원·직선·부채꼴·시선)만 계산한다.
 * 다른 곳에 대상 선택 코드를 만들지 말 것.
 */
public final class WeaponTargeting {

    private final Services services;

    public WeaponTargeting(Services services) { this.services = services; }

    public boolean isEnemy(Player source, Entity e) {
        return e instanceof LivingEntity le && le.isValid() && !le.isDead() && services.targets().isEnemy(source, le);
    }

    public boolean isAlly(Player source, Entity e) {
        return e instanceof Player p && p.isValid() && !p.isDead() && services.targets().isAlly(source, p);
    }

    /** 원(구) 안의 적 — 가까운 순. 히트박스 크기를 반영(중심이 아니라 상자까지의 거리). */
    public List<LivingEntity> enemiesInRadius(Player source, Location center, double radius) {
        List<LivingEntity> out = new ArrayList<>();
        World w = center.getWorld();
        if (w == null) return out;
        double r = radius + 2.0;
        for (Entity e : w.getNearbyEntities(center, r, r, r)) {
            if (!isEnemy(source, e)) continue;
            if (distanceToBox(center.toVector(), e.getBoundingBox()) <= radius) out.add((LivingEntity) e);
        }
        out.sort(Comparator.comparingDouble(e -> e.getLocation().distanceSquared(center)));
        return out;
    }

    /** 부채꼴: center 에서 forward 기준 전체 각도 angleDeg 안 (360 이상 = 원). */
    public List<LivingEntity> enemiesInCone(Player source, Location center, Vector forward, double radius, double angleDeg) {
        List<LivingEntity> all = enemiesInRadius(source, center, radius);
        if (angleDeg >= 359.9) return all;
        Vector f = forward.clone().setY(0);
        if (f.lengthSquared() < 1e-6) return all;
        f.normalize();
        double cos = Math.cos(Math.toRadians(angleDeg / 2.0));
        List<LivingEntity> out = new ArrayList<>();
        for (LivingEntity e : all) {
            Vector to = e.getLocation().toVector().subtract(center.toVector()).setY(0);
            if (to.lengthSquared() < 0.5 || to.normalize().dot(f) >= cos) out.add(e);
        }
        return out;
    }

    /** 선분 from→to 를 따라 폭 width(전체) 안의 적. */
    public List<LivingEntity> enemiesInLine(Player source, Location from, Location to, double width) {
        List<LivingEntity> out = new ArrayList<>();
        World w = from.getWorld();
        if (w == null) return out;
        Vector a = from.toVector();
        Vector b = to.toVector();
        BoundingBox area = BoundingBox.of(a, b).expand(width / 2.0 + 2.0);
        for (Entity e : w.getNearbyEntities(area)) {
            if (!isEnemy(source, e)) continue;
            BoundingBox bb = e.getBoundingBox();
            Vector c = bb.getCenter();
            double half = Math.max(bb.getWidthX(), bb.getWidthZ()) / 2.0;
            double yHalf = bb.getHeight() / 2.0;
            Vector closest = closestOnSegment(a, b, c);
            double dxz = Math.hypot(closest.getX() - c.getX(), closest.getZ() - c.getZ());
            double dy = Math.max(0, Math.abs(closest.getY() - c.getY()) - yHalf);
            if (dxz <= width / 2.0 + half && dy <= width / 2.0 + 0.5) out.add((LivingEntity) e);
        }
        out.sort(Comparator.comparingDouble(e -> e.getLocation().distanceSquared(from)));
        return out;
    }

    /** 시선(눈 위치)에서 range 안의 첫 적 (블록에 막히면 없음). */
    public LivingEntity firstInSight(Player source, double range, double raySize) {
        Location eye = source.getEyeLocation();
        RayTraceResult hit = source.getWorld().rayTrace(eye, eye.getDirection(), range, FluidCollisionMode.NEVER, true, raySize,
                e -> e != source && isEnemy(source, e));
        if (hit == null || !(hit.getHitEntity() instanceof LivingEntity le)) return null;
        return le;
    }

    /** 반경 안 아군 플레이어 (본인 포함). */
    public List<Player> alliesInRadius(Player source, Location center, double radius) {
        return services.targets().alliesIn(source, center, radius);
    }

    public static Vector closestOnSegment(Vector a, Vector b, Vector p) {
        Vector ab = b.clone().subtract(a);
        double len2 = ab.lengthSquared();
        if (len2 < 1e-9) return a.clone();
        double t = Math.max(0, Math.min(1, p.clone().subtract(a).dot(ab) / len2));
        return a.clone().add(ab.multiply(t));
    }

    public static double distanceToBox(Vector p, BoundingBox bb) {
        double dx = Math.max(Math.max(bb.getMinX() - p.getX(), 0), p.getX() - bb.getMaxX());
        double dy = Math.max(Math.max(bb.getMinY() - p.getY(), 0), p.getY() - bb.getMaxY());
        double dz = Math.max(Math.max(bb.getMinZ() - p.getZ(), 0), p.getZ() - bb.getMaxZ());
        return Math.sqrt(dx * dx + dy * dy + dz * dz);
    }
}
