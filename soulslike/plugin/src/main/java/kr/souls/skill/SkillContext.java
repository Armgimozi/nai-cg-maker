package kr.souls.skill;

import kr.souls.AugSky;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/** 스킬 한 번 시전에 대한 정보. 무기 스킬과 몬스터 스킬이 같이 쓴다. */
public final class SkillContext {
    public final AugSky plugin;
    public final LivingEntity caster;
    public final boolean byPlayer;
    public LivingEntity target;
    public double power;
    public double lastDamage;
    /** 투사체 착탄 지점 같은 '여기서 이어서 실행' 위치. 있으면 aim 이 이 위치를 돌려준다. */
    public Location point;

    public SkillContext(AugSky plugin, LivingEntity caster, LivingEntity target, double power) {
        this.plugin = plugin;
        this.caster = caster;
        this.byPlayer = caster instanceof Player || Targets.isAlly(caster);
        this.target = target;
        this.power = power;
    }

    public SkillContext at(Location loc) {
        SkillContext c = new SkillContext(plugin, caster, target, power);
        c.point = loc == null ? null : loc.clone();
        c.lastDamage = lastDamage;
        return c;
    }

    public World world() { return caster.getWorld(); }

    public Location eye() { return caster.getEyeLocation(); }

    public boolean hasTarget() {
        return target != null && target.isValid() && !target.isDead() && target.getWorld().equals(caster.getWorld());
    }

    /** 시전 방향. 몬스터는 대상 쪽, 플레이어는 바라보는 쪽. */
    public Vector dir() {
        if (!(caster instanceof Player) && hasTarget()) {
            Vector v = target.getEyeLocation().toVector().subtract(eye().toVector());
            if (v.lengthSquared() > 1e-6) return v.normalize();
        }
        return eye().getDirection().normalize();
    }

    public Vector flatDir() {
        Vector d = dir().clone().setY(0);
        if (d.lengthSquared() < 1e-6) {
            double yaw = Math.toRadians(caster.getLocation().getYaw());
            d = new Vector(-Math.sin(yaw), 0, Math.cos(yaw));
        }
        return d.normalize();
    }

    /** 조준 지점. 블록/적에 닿는 곳, 없으면 사거리 끝에서 아래로 내린 바닥. */
    public Location aim(double range) {
        if (point != null) return point.clone();
        if (!(caster instanceof Player) && hasTarget()) return target.getLocation();
        Location eye = eye();
        Vector d = dir();
        RayTraceResult r = world().rayTrace(eye, d, range, FluidCollisionMode.NEVER, true, 0.6,
                e -> Targets.isEnemy(caster, e));
        Location hit;
        if (r != null) {
            if (r.getHitEntity() != null) return r.getHitEntity().getLocation();
            hit = r.getHitPosition().toLocation(world());
            if (r.getHitBlockFace() != null) {
                hit.add(r.getHitBlockFace().getDirection().multiply(0.5));
            }
        } else {
            hit = eye.clone().add(d.clone().multiply(range));
        }
        return ground(hit, 12);
    }

    /** 지정한 위치에서 아래로 내려가 첫 단단한 블록 위를 찾는다. 없으면 그대로. */
    public static Location ground(Location loc, int maxDown) {
        Location l = loc.clone();
        World w = l.getWorld();
        int y0 = l.getBlockY();
        for (int i = 0; i <= maxDown; i++) {
            Block b = w.getBlockAt(l.getBlockX(), y0 - i, l.getBlockZ());
            if (b.getType().isSolid()) {
                l.setY(y0 - i + 1);
                return l;
            }
        }
        return loc.clone();
    }

    /** "self" / "aim" / "target" 중 하나로 중심점을 고른다. */
    public Location center(String at, double range) {
        if ("self".equals(at)) return point != null ? point.clone() : caster.getLocation();
        if ("target".equals(at)) {
            if (hasTarget()) return target.getLocation();
            return aim(range);
        }
        return aim(range);
    }
}
