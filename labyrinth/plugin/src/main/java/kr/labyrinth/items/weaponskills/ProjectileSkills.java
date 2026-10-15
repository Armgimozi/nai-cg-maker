package kr.labyrinth.items.weaponskills;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.combat.DamageContext;
import org.bukkit.Color;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/** 투사체형 무기 스킬: slash_wave(검기) · missile(투사체) · blade_orbit(공전 칼날). GDD §17.2. */
final class ProjectileSkills {

    private ProjectileSkills() {}

    static void register(Map<String, WeaponSkill> r) {
        r.put("slash_wave", ProjectileSkills::slashWave);
        r.put("missile", ProjectileSkills::missile);
        r.put("blade_orbit", ProjectileSkills::bladeOrbit);
    }

    static Vector rotateY(Vector v, double deg) {
        return v.clone().rotateAroundY(Math.toRadians(deg));
    }

    /** 초승달 검기를 바라보는 방향으로 날림 — 관통(기본), count·spread 부채꼴. */
    static void slashWave(SkillCast c) {
        int count = Math.max(1, c.p.integer("count", 1));
        double spread = c.num("spread", count > 1 ? 30 : 0);
        double range = c.num("range", 12);
        double width = c.num("width", 2.0);
        double speed = Math.max(0.3, c.num("speed", 1.2));
        int pierce = c.p.has("pierce") ? c.pierce() : Integer.MAX_VALUE;
        String fx = c.fx("slash_wave");
        Vector base = c.look();
        if (Math.abs(base.getY()) > 0.6) base.setY(Math.signum(base.getY()) * 0.6);
        base.normalize();
        Location origin = c.player.getEyeLocation().subtract(0, 0.5, 0).add(base.clone().multiply(0.6));
        for (int i = 0; i < count; i++) {
            double ang = count == 1 ? 0 : -spread / 2 + spread * i / (count - 1);
            wave(c, origin.clone(), rotateY(base, ang), range, width, speed, pierce, fx);
        }
        c.sound(Sound.ENTITY_PLAYER_ATTACK_SWEEP, 0.9f, 1.25f);
    }

    private static void wave(SkillCast c, Location pos, Vector dir, double range, double width, double speed, int pierce, String fx) {
        Location start = pos.clone();
        start.setDirection(dir);
        ItemDisplay d = fx == null ? null : Fx.spawn(c.services, start, fx, (float) Math.max(0.6, width / 2.0), 0);
        Set<UUID> hit = new HashSet<>();
        int[] left = {pierce};
        double[] travelled = {0};
        Location cur = start.clone();
        Color col = c.color();
        int maxTicks = (int) Math.ceil(range / speed) + 1;
        c.repeat(1, maxTicks, t -> {
            Location next = cur.clone().add(dir.clone().multiply(speed));
            RayTraceResult block = cur.getWorld().rayTraceBlocks(cur, dir, speed, FluidCollisionMode.NEVER, true);
            for (LivingEntity e : c.targets().enemiesInLine(c.player, cur, block != null
                    ? block.getHitPosition().toLocation(cur.getWorld()) : next, width)) {
                if (!hit.add(e.getUniqueId())) continue;
                c.hit(e, c.damage());
                e.getWorld().spawnParticle(Particle.SWEEP_ATTACK, e.getLocation().add(0, e.getHeight() / 2, 0), 1);
                if (left[0]-- <= 0) return false;
            }
            if (block != null) {
                cur.getWorld().spawnParticle(Particle.CRIT, block.getHitPosition().toLocation(cur.getWorld()), 10, 0.2, 0.2, 0.2, 0.2);
                return false;
            }
            cur.setX(next.getX());
            cur.setY(next.getY());
            cur.setZ(next.getZ());
            travelled[0] += speed;
            if (d != null && d.isValid()) d.teleport(cur);
            else cur.getWorld().spawnParticle(Particle.SWEEP_ATTACK, cur, 1);
            Fx.dust(cur, col, 1.2f, 3, width / 4);
            return travelled[0] < range;
        }, () -> { if (d != null) d.remove(); });
    }

    /** 투사체 매개변수 묶음. */
    record Missile(double speed, double gravity, double homing, int pierce, double range, double explodeRadius,
                   double damage, double knockback, double pull, double bossPull, String fx) {}

    static void missile(SkillCast c) {
        int count = Math.max(1, c.p.integer("count", 1));
        double spread = c.num("spread", count > 1 ? 20 : 0);
        double interval = c.num("interval", 0);
        Missile m = new Missile(Math.max(0.2, c.num("speed", 1.5)), c.num("gravity", 0), c.num("homing", 0), c.pierce(),
                c.num("range", 20), c.num("explode_radius", 0), c.damage(), c.num("knockback", 0),
                c.amountOrFlag("pull", 0.8), c.amountOrFlag("boss_pull", 0.8), c.fx(null));
        boolean bow = c.weapon.isRanged();
        for (int i = 0; i < count; i++) {
            final int idx = i;
            Runnable fire = () -> {
                if (!c.player.isOnline() || c.player.isDead()) return;
                Vector base = c.look();
                double ang;
                if (interval > 0) ang = (Math.random() - 0.5) * spread;
                else ang = count == 1 ? 0 : -spread / 2 + spread * idx / (count - 1);
                Location eye = c.player.getEyeLocation().subtract(0, 0.25, 0);
                fly(c, eye.add(base.clone().multiply(0.5)), rotateY(base, ang), m, null);
                c.player.getWorld().playSound(c.player.getLocation(),
                        bow ? Sound.ENTITY_ARROW_SHOOT : Sound.ENTITY_BLAZE_SHOOT, bow ? 0.9f : 0.5f, bow ? 1.2f : 1.6f);
            };
            int delay = interval > 0 ? SkillCast.ticks(interval * i) : 0;
            if (delay <= 0) fire.run();
            else c.later(delay, fire);
        }
    }

    /** 투사체 비행 (중력·약유도·관통·착탄 폭발·끌기). display 가 있으면 그걸 움직인다. */
    static void fly(SkillCast c, Location start, Vector dir, Missile m, ItemDisplay existing) {
        Location cur = start.clone();
        Vector vel = dir.clone().normalize().multiply(m.speed());
        Location face = cur.clone();
        face.setDirection(vel);
        ItemDisplay d = existing != null ? existing : m.fx() == null ? null : Fx.spawn(c.services, face, m.fx(), 1f, 0);
        Set<UUID> hit = new HashSet<>();
        int[] left = {m.pierce()};
        double[] travelled = {0};
        Color col = c.color();
        int maxTicks = (int) Math.ceil(m.range() / Math.max(0.2, m.speed())) + 20;
        c.repeat(1, maxTicks, t -> {
            vel.setY(vel.getY() - m.gravity());
            if (m.homing() > 0) {
                LivingEntity target = nearestAhead(c, cur, vel, 10);
                if (target != null) {
                    Vector want = target.getBoundingBox().getCenter().subtract(cur.toVector()).normalize().multiply(m.speed());
                    vel.multiply(1 - m.homing()).add(want.multiply(m.homing()));
                    vel.normalize().multiply(m.speed());
                }
            }
            double step = vel.length();
            Vector dirN = vel.clone().normalize();
            RayTraceResult block = cur.getWorld().rayTraceBlocks(cur, dirN, step, FluidCollisionMode.NEVER, true);
            Location next = block != null ? block.getHitPosition().toLocation(cur.getWorld()) : cur.clone().add(vel);
            for (LivingEntity e : c.targets().enemiesInLine(c.player, cur, next, 0.9)) {
                if (!hit.add(e.getUniqueId())) continue;
                if (m.explodeRadius() > 0) {
                    explode(c, e.getLocation().add(0, e.getHeight() / 2, 0), m, col);
                    return false;
                }
                DamageContext ctx = c.hit(e, m.damage(), m.knockback());
                if (ctx != null && m.pull() > 0) c.pull(e, c.player.getLocation(), m.pull(), m.bossPull());
                if (left[0]-- <= 0) return false;
            }
            if (block != null) {
                if (m.explodeRadius() > 0) explode(c, next, m, col);
                else cur.getWorld().spawnParticle(Particle.CRIT, next, 6, 0.1, 0.1, 0.1, 0.15);
                return false;
            }
            cur.setX(next.getX());
            cur.setY(next.getY());
            cur.setZ(next.getZ());
            travelled[0] += step;
            if (d != null && d.isValid()) {
                Location l = cur.clone();
                l.setDirection(vel);
                d.teleport(l);
            } else {
                Fx.dust(cur, col, 1.3f, 2, 0.05);
            }
            if (t % 2 == 0) Fx.dust(cur, col, 0.8f, 1, 0.05);
            return travelled[0] < m.range();
        }, () -> { if (d != null) d.remove(); });
    }

    private static void explode(SkillCast c, Location at, Missile m, Color col) {
        for (LivingEntity e : c.enemies(at, m.explodeRadius())) {
            DamageContext ctx = c.hit(e, m.damage(), m.knockback());
            if (ctx != null && m.pull() > 0) c.pull(e, c.player.getLocation(), m.pull(), m.bossPull());
        }
        at.getWorld().spawnParticle(Particle.EXPLOSION, at, 1);
        Fx.dust(at, col, 1.6f, 24, m.explodeRadius() / 2);
        at.getWorld().playSound(at, Sound.ENTITY_GENERIC_EXPLODE, 0.5f, 1.6f);
    }

    static LivingEntity nearestAhead(SkillCast c, Location from, Vector vel, double radius) {
        LivingEntity best = null;
        double bestD = Double.MAX_VALUE;
        Vector f = vel.clone().normalize();
        for (LivingEntity e : c.enemies(from, radius)) {
            Vector to = e.getBoundingBox().getCenter().subtract(from.toVector());
            double dist = to.length();
            if (dist < 1e-3 || to.normalize().dot(f) < 0.35) continue;
            if (dist < bestD) {
                bestD = dist;
                best = e;
            }
        }
        return best;
    }

    /** fx 오브젝트 count 개가 공전, 닿는 적은 tick 마다 피해. launch 면 끝에 바라보는 방향으로 발사. */
    static void bladeOrbit(SkillCast c) {
        int count = Math.max(1, c.p.integer("count", 3));
        double radius = c.num("radius", 2.2);
        int duration = SkillCast.ticks(c.num("duration", 6));
        int tick = SkillCast.ticks(c.num("tick", 0.5));
        boolean launch = c.flag("launch", false);
        double launchDamage = c.num("launch_damage", c.damage() * 2);
        String fx = c.fx(null);
        List<ItemDisplay> orbs = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            ItemDisplay d = fx == null ? null : Fx.spawn(c.services, c.player.getLocation().add(0, 1, 0), fx, 0.9f, 0);
            orbs.add(d);
        }
        Color col = c.color();
        double[] angle = {0};
        Location[] positions = new Location[count];
        c.sound(Sound.ITEM_TRIDENT_RIPTIDE_1, 0.6f, 1.6f);
        c.repeat(1, duration, t -> {
            angle[0] += 0.22;
            Location center = c.player.getLocation().add(0, 1.0, 0);
            for (int i = 0; i < count; i++) {
                double a = angle[0] + Math.PI * 2 * i / count;
                Location p = center.clone().add(Math.cos(a) * radius, Math.sin(angle[0] * 2 + i) * 0.15, Math.sin(a) * radius);
                positions[i] = p;
                ItemDisplay d = orbs.get(i);
                if (d != null && d.isValid()) d.teleport(p);
                else Fx.dust(p, col, 1.4f, 2, 0.05);
            }
            if (t % tick == 0) {
                Set<UUID> hitNow = new HashSet<>();
                for (Location p : positions) {
                    if (p == null) continue;
                    for (LivingEntity e : c.enemies(p, 0.9)) {
                        if (hitNow.add(e.getUniqueId())) c.hit(e, c.damage());
                    }
                }
            }
            return true;
        }, () -> {
            if (launch && c.player.isOnline() && !c.player.isDead()) {
                Missile m = new Missile(1.5, 0, 0.05, 0, 18, 0, launchDamage, 0.3, 0, 0, null);
                Vector look = c.look();
                for (int i = 0; i < count; i++) {
                    Location from = positions[i] != null ? positions[i] : c.player.getEyeLocation();
                    fly(c, from, look.clone(), m, orbs.get(i));
                }
                c.sound(Sound.ENTITY_WITHER_SHOOT, 0.4f, 1.8f);
            } else {
                for (ItemDisplay d : orbs) if (d != null) d.remove();
            }
        });
    }
}
