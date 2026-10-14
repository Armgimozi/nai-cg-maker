package kr.labyrinth.classes.skills;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import kr.labyrinth.Services;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/**
 * 스킬 대상 고르기. 적/아군 판정은 <b>전부</b> {@code services.targets()} (pvp.TargetFilter) 를 지난다:
 * 미궁에선 커스텀 몹이 적, PvP 매치에선 상대 팀이 적이고 아군은 절대 맞지 않는다.
 */
public final class Targeting {

    private final Services services;
    private final Player caster;

    public Targeting(Services services, Player caster) {
        this.services = services;
        this.caster = caster;
    }

    public boolean isEnemy(Entity e) { return services.targets().isEnemy(caster, e); }

    public boolean isAlly(Entity e) { return services.targets().isAlly(caster, e); }

    /** center 반경 radius 의 적 (가까운 순). */
    public List<LivingEntity> enemiesIn(Location center, double radius) {
        return services.targets().enemiesIn(caster, center, radius);
    }

    /** center 반경 radius 의 아군 플레이어 (본인 포함, 살아 있는 것만). */
    public List<Player> alliesIn(Location center, double radius) {
        List<Player> out = new ArrayList<>();
        for (Player p : services.targets().alliesIn(caster, center, radius)) {
            if (!p.isDead() && p.getGameMode() != org.bukkit.GameMode.SPECTATOR) out.add(p);
        }
        return out;
    }

    /** 수평 부채꼴 (origin 에서 dir 방향, 반각 angle/2). */
    public List<LivingEntity> enemiesInCone(Location origin, Vector dir, double range, double angleDeg) {
        Vector flat = dir.clone().setY(0);
        if (flat.lengthSquared() < 1e-6) flat = caster.getLocation().getDirection().setY(0);
        flat.normalize();
        double cos = Math.cos(Math.toRadians(angleDeg / 2.0));
        List<LivingEntity> out = new ArrayList<>();
        for (LivingEntity e : enemiesIn(origin, range + 1.0)) {
            Vector to = e.getLocation().toVector().subtract(origin.toVector()).setY(0);
            double dist = to.length();
            if (dist > range + e.getWidth() / 2) continue;
            if (dist < 0.8 || to.normalize().dot(flat) >= cos) out.add(e);
        }
        return out;
    }

    /** 직선 (start 에서 dir 로 length, 너비 width). */
    public List<LivingEntity> enemiesInLine(Location start, Vector dir, double length, double width) {
        Vector d = dir.clone();
        if (d.lengthSquared() < 1e-6) return List.of();
        d.normalize();
        Location mid = start.clone().add(d.clone().multiply(length / 2));
        List<LivingEntity> out = new ArrayList<>();
        Vector s = start.toVector();
        for (LivingEntity e : enemiesIn(mid, length / 2 + width + 1)) {
            Vector c = e.getBoundingBox().getCenter();
            Vector rel = c.clone().subtract(s);
            double along = rel.dot(d);
            if (along < -0.5 || along > length + 0.5) continue;
            double perp = rel.clone().subtract(d.clone().multiply(along)).length();
            if (perp <= width / 2 + e.getWidth() / 2) out.add(e);
        }
        out.sort(Comparator.comparingDouble(e -> e.getLocation().distanceSquared(start)));
        return out;
    }

    /** 바라보는 적 (시야 광선 + 블록 차단). */
    public LivingEntity lookedAtEnemy(double range) {
        return lookedAt(range, 0.6, this::isEnemy);
    }

    /** 바라보는 아군 플레이어 (본인 제외). */
    public Player lookedAtAlly(double range) {
        LivingEntity e = lookedAt(range, 0.8, x -> x instanceof Player p && !p.equals(caster) && isAlly(p)
                && p.getGameMode() != org.bukkit.GameMode.SPECTATOR);
        return e instanceof Player p ? p : null;
    }

    private LivingEntity lookedAt(double range, double raySize, java.util.function.Predicate<Entity> filter) {
        Location eye = caster.getEyeLocation();
        World w = caster.getWorld();
        RayTraceResult r = w.rayTrace(eye, eye.getDirection(), range, FluidCollisionMode.NEVER, true, raySize,
                e -> !e.equals(caster) && e instanceof LivingEntity && filter.test(e));
        if (r != null && r.getHitEntity() instanceof LivingEntity le) return le;
        // 광선이 빗나가면 시선 원뿔(8°) 안 가장 가까운 대상
        LivingEntity best = null;
        double bestScore = Double.MAX_VALUE;
        Vector look = eye.getDirection().normalize();
        for (Entity e : w.getNearbyEntities(eye, range, range, range)) {
            if (!(e instanceof LivingEntity le) || e.equals(caster) || !filter.test(e)) continue;
            Vector to = le.getBoundingBox().getCenter().subtract(eye.toVector());
            double dist = to.length();
            if (dist > range || dist < 1e-3) continue;
            double dot = to.clone().normalize().dot(look);
            if (dot < Math.cos(Math.toRadians(8))) continue;
            if (!caster.hasLineOfSight(le)) continue;
            double score = dist * (2 - dot);
            if (score < bestScore) {
                bestScore = score;
                best = le;
            }
        }
        return best;
    }

    /** 시선 원뿔(coneDeg) 안에서 가장 가까운 적 (유도 투사체 초기 대상). */
    public LivingEntity enemyInView(double range, double coneDeg) {
        Location eye = caster.getEyeLocation();
        Vector look = eye.getDirection().normalize();
        LivingEntity best = null;
        double bestDist = Double.MAX_VALUE;
        for (LivingEntity e : enemiesIn(eye, range)) {
            Vector to = e.getBoundingBox().getCenter().subtract(eye.toVector());
            double dist = to.length();
            if (dist < 1e-3 || to.normalize().dot(look) < Math.cos(Math.toRadians(coneDeg / 2))) continue;
            if (!caster.hasLineOfSight(e)) continue;
            if (dist < bestDist) {
                bestDist = dist;
                best = e;
            }
        }
        return best;
    }

    /** 바라보는 지면 지점 (최대 range). 허공을 보면 그 지점에서 아래로 바닥을 찾는다. */
    public Location groundTarget(double range) {
        Location eye = caster.getEyeLocation();
        RayTraceResult r = caster.getWorld().rayTraceBlocks(eye, eye.getDirection(), range, FluidCollisionMode.NEVER, true);
        Location point;
        if (r != null) {
            point = r.getHitPosition().toLocation(caster.getWorld());
            if (r.getHitBlockFace() != null && r.getHitBlockFace() != org.bukkit.block.BlockFace.UP) {
                point.add(r.getHitBlockFace().getDirection().multiply(0.5));
            }
        } else {
            point = eye.clone().add(eye.getDirection().multiply(range));
        }
        return dropToGround(point, 12);
    }

    /** 아래로 maxDown 블록까지 단단한 바닥을 찾아 그 위 좌표 (없으면 원래 지점). */
    public static Location dropToGround(Location point, int maxDown) {
        Location l = point.clone();
        World w = l.getWorld();
        if (w == null) return point;
        for (int i = 0; i <= maxDown; i++) {
            Block at = w.getBlockAt(l.getBlockX(), (int) Math.floor(l.getY()), l.getBlockZ());
            Block below = at.getRelative(0, -1, 0);
            if (at.isPassable() && !below.isPassable()) {
                l.setY(below.getY() + 1.0);
                return l;
            }
            l.subtract(0, 1, 0);
        }
        return point;
    }

    /**
     * from 에서 dir 로 최대 distance 만큼, 막히지 않는 마지막 안전 지점 (몸이 들어갈 2칸 공간).
     * 순간이동·돌진이 벽을 뚫지 않게 한다.
     */
    public static Location safeAlong(Location from, Vector dir, double distance) {
        Vector d = dir.clone();
        if (d.lengthSquared() < 1e-6) return from.clone();
        d.normalize();
        Location best = from.clone();
        for (double t = 0.5; t <= distance + 1e-6; t += 0.5) {
            Location c = from.clone().add(d.clone().multiply(t));
            if (!fits(c)) break;
            best = c;
        }
        best.setYaw(from.getYaw());
        best.setPitch(from.getPitch());
        return best;
    }

    /** 플레이어 크기(0.6×1.8)가 들어가는가. */
    public static boolean fits(Location l) {
        World w = l.getWorld();
        if (w == null) return false;
        BoundingBox box = BoundingBox.of(l.toVector().add(new Vector(0, 0.9, 0)), 0.3, 0.9, 0.3);
        for (int x = (int) Math.floor(box.getMinX()); x <= (int) Math.floor(box.getMaxX()); x++) {
            for (int y = (int) Math.floor(box.getMinY()); y <= (int) Math.floor(box.getMaxY()); y++) {
                for (int z = (int) Math.floor(box.getMinZ()); z <= (int) Math.floor(box.getMaxZ()); z++) {
                    Block b = w.getBlockAt(x, y, z);
                    if (!b.isPassable() && b.getBoundingBox().overlaps(box)) return false;
                }
            }
        }
        return true;
    }

    /** attacker 가 target 의 등 뒤(backAngle° 안)에 있는가. */
    public static boolean isBehind(LivingEntity attacker, LivingEntity target, double backAngleDeg) {
        Vector facing = target.getLocation().getDirection().setY(0);
        Vector toAttacker = attacker.getLocation().toVector().subtract(target.getLocation().toVector()).setY(0);
        if (facing.lengthSquared() < 1e-6 || toAttacker.lengthSquared() < 1e-6) return false;
        double cos = facing.normalize().dot(toAttacker.normalize());
        return cos <= -Math.cos(Math.toRadians(backAngleDeg / 2.0));
    }
}
