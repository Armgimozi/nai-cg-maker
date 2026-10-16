package kr.labyrinth.items.weaponskills;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.combat.DamageContext;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.util.Vector;

/** 범위형 무기 스킬: nova · fissure · rain_zone · vortex · whirlwind. GDD §17.2. */
final class AreaSkills {

    private AreaSkills() {}

    static void register(Map<String, WeaponSkill> r) {
        r.put("nova", AreaSkills::nova);
        r.put("fissure", AreaSkills::fissure);
        r.put("rain_zone", AreaSkills::rainZone);
        r.put("vortex", AreaSkills::vortex);
        r.put("whirlwind", AreaSkills::whirlwind);
    }

    /** 자기 중심(또는 at_target 지점) 원형/부채꼴 폭발. delay 동안 아군에게만 장판 표시. */
    static void nova(SkillCast c) {
        double radius = c.num("radius", 5);
        double angle = c.num("angle", 360);
        double delay = c.num("delay", 0);
        double kb = c.num("knockback", 0);
        double pull = c.amountOrFlag("pull", 0.8);
        boolean atTarget = c.flag("at_target", false);
        Location center = atTarget ? c.targetPoint(c.num("range", 10)) : c.player.getLocation();
        Vector forward = c.flatLook();
        String fx = c.fx(null);
        Color col = c.color();
        Runnable blast = () -> {
            if (!c.player.isOnline() || c.player.isDead()) return;
            Location at = atTarget ? center : c.player.getLocation();
            List<LivingEntity> targets = c.targets().enemiesInCone(c.player, at, forward, radius, angle);
            for (LivingEntity e : targets) {
                if (c.hit(e, c.damage(), kb) != null && pull > 0) c.pull(e, at, pull, 0);
            }
            if (fx != null) Fx.spawn(c.services, at.clone().add(0, 0.1, 0), fx, (float) (radius / 2.0), 10);
            burstParticles(at, radius, angle, forward, col);
            c.soundAt(at, Sound.ENTITY_GENERIC_EXPLODE, 0.7f, 1.2f);
            c.soundAt(at, Sound.ENTITY_ILLUSIONER_CAST_SPELL, 0.6f, 0.8f);
        };
        if (delay > 0) {
            int ticks = SkillCast.ticks(delay);
            if (fx != null) Fx.spawnFor(c.services, center.clone().add(0, 0.05, 0), fx, (float) (radius / 2.0) * 0.6f, ticks,
                    c.allies(center, 64));
            c.sound(Sound.BLOCK_BEACON_POWER_SELECT, 0.6f, 1.6f);
            c.repeat(2, ticks, t -> {
                Location at = atTarget ? center : c.player.getLocation();
                double r = radius * Math.min(1.0, (double) t / ticks);
                for (int i = 0; i < 16; i++) {
                    double a = Math.PI * 2 * i / 16;
                    Fx.dust(at.clone().add(Math.cos(a) * r, 0.15, Math.sin(a) * r), col, 1.0f, 1, 0.02);
                }
                return true;
            }, blast);
        } else {
            blast.run();
        }
    }

    private static void burstParticles(Location at, double radius, double angle, Vector forward, Color col) {
        int n = (int) Math.max(12, radius * 10);
        double half = Math.toRadians(Math.min(360, angle) / 2);
        double base = Math.atan2(forward.getZ(), forward.getX());
        for (int i = 0; i < n; i++) {
            double a = angle >= 359.9 ? Math.PI * 2 * i / n : base - half + 2 * half * i / Math.max(1, n - 1);
            for (double r = 1; r <= radius; r += 1.2) {
                Fx.dust(at.clone().add(Math.cos(a) * r, 0.3, Math.sin(a) * r), col, 1.4f, 1, 0.05);
            }
        }
        at.getWorld().spawnParticle(Particle.EXPLOSION, at.clone().add(0, 0.5, 0), 1);
    }

    /** 발밑에서 앞으로 퍼지는 직선 균열 (speed 블록/초, 0 = 즉시). 지나간 자리에 trail 장판. */
    static void fissure(SkillCast c) {
        double length = c.num("length", 10);
        double width = c.num("width", 2.5);
        double speed = c.num("speed", 14);
        double launch = c.num("launch", 0);
        double bossLaunch = c.num("boss_launch", 0);
        double trailDuration = c.num("trail_duration", 0);
        double trailDps = c.num("trail_dps", 0);
        Vector dir = c.flatLook();
        Location start = c.player.getLocation().add(dir.clone().multiply(0.8));
        Location end = start.clone().add(dir.clone().multiply(length));
        Set<UUID> hit = new HashSet<>();
        String fx = c.fx(null);
        Color col = c.color();
        double perTick = speed <= 0 ? length : speed / 20.0;
        int ticks = (int) Math.ceil(length / perTick);
        double[] progress = {0};
        c.sound(Sound.ENTITY_WARDEN_ATTACK_IMPACT, 0.8f, 0.8f);
        c.repeat(1, Math.max(1, ticks), t -> {
            double from = progress[0];
            double to = Math.min(length, from + perTick);
            progress[0] = to;
            Location a = start.clone().add(dir.clone().multiply(from)).add(0, 0.5, 0);
            Location b = start.clone().add(dir.clone().multiply(to)).add(0, 0.5, 0);
            for (LivingEntity e : c.targets().enemiesInLine(c.player, a, b, width)) {
                if (!hit.add(e.getUniqueId())) continue;
                if (c.hit(e, c.damage()) != null) c.launch(e, launch, bossLaunch);
            }
            for (double d = from; d <= to; d += 0.7) {
                Location p = SkillCast.ground(start.clone().add(dir.clone().multiply(d)).add(0, 0.6, 0), 3);
                p.getWorld().spawnParticle(Particle.LAVA, p, 1, width / 4, 0, width / 4, 0);
                Fx.dust(p.clone().add(0, 0.2, 0), col, 1.6f, 3, width / 4);
                var under = p.clone().subtract(0, 0.5, 0).getBlock();
                if (under.getType().isSolid()) {
                    p.getWorld().spawnParticle(Particle.BLOCK, p, 4, width / 4, 0.1, width / 4, 0.1, under.getBlockData());
                }
            }
            if (fx != null && ((int) from / 2) != ((int) to / 2)) {
                Location l = SkillCast.ground(b.clone(), 3).add(0, 0.05, 0);
                l.setDirection(dir);
                Fx.spawn(c.services, l, fx, (float) (width / 2.0), Math.max(10, SkillCast.ticks(trailDuration)));
            }
            return to < length;
        }, () -> {
            if (trailDuration <= 0 || trailDps <= 0) return;
            int period = 10;
            c.repeat(period, SkillCast.ticks(trailDuration), t -> {
                Location a = start.clone().add(0, 0.5, 0);
                Location b = end.clone().add(0, 0.5, 0);
                for (LivingEntity e : c.targets().enemiesInLine(c.player, a, b, width)) {
                    c.hit(e, trailDps * period / 20.0);
                }
                for (double d = 0; d <= length; d += 1.5) {
                    Location p = start.clone().add(dir.clone().multiply(d)).add(0, 0.3, 0);
                    p.getWorld().spawnParticle(Particle.SMOKE, p, 2, width / 4, 0.1, width / 4, 0.01);
                    if (ThreadLocalRandom.current().nextDouble() < 0.3) Fx.dust(p, col, 1.2f, 1, width / 4);
                }
                return true;
            }, null);
        });
    }

    /** 바라보는 지점(range) 원 안에 duration 동안 tick 마다 타격 (연출 strikes 개, slow·pull). */
    static void rainZone(SkillCast c) {
        double range = c.num("range", 20);
        double radius = c.num("radius", 5);
        int duration = SkillCast.ticks(c.num("duration", 4));
        int tick = SkillCast.ticks(c.num("tick", 0.5));
        int strikes = Math.max(1, c.p.integer("strikes", 3));
        double slow = c.num("slow", 0);
        double pull = c.num("pull", 0);
        Location center = c.targetPoint(range);
        String fx = c.fx(null);
        Color col = c.color();
        ItemDisplay ground = fx != null ? Fx.spawn(c.services, center.clone().add(0, 0.05, 0), fx, (float) (radius / 2.0), 0) : null;
        boolean bow = c.weapon.isRanged();
        c.sound(bow ? Sound.ENTITY_ARROW_SHOOT : Sound.ENTITY_EVOKER_CAST_SPELL, 0.8f, 0.7f);
        c.repeat(1, duration, t -> {
            if (t % 4 == 0) c.ring(center, radius, 24);
            if (ground != null && ground.isValid()) Fx.transform(ground, (float) Math.toRadians(t * 3), (float) (radius / 2.0),
                    (float) (radius / 2.0), (float) (radius / 2.0), 1);
            if (t % tick == 0) {
                for (int i = 0; i < strikes; i++) {
                    double a = ThreadLocalRandom.current().nextDouble(Math.PI * 2);
                    double r = Math.sqrt(ThreadLocalRandom.current().nextDouble()) * radius;
                    Location p = center.clone().add(Math.cos(a) * r, 0, Math.sin(a) * r);
                    Fx.line(p.clone().add(0, 6, 0), p.clone().add(0, 0.2, 0), col, 1.0f, 0.5);
                    p.getWorld().spawnParticle(bow ? Particle.CRIT : Particle.ELECTRIC_SPARK, p.clone().add(0, 0.2, 0), 8, 0.3, 0.1, 0.3, 0.1);
                }
                center.getWorld().playSound(center, bow ? Sound.ENTITY_ARROW_HIT : Sound.ENTITY_LIGHTNING_BOLT_IMPACT, 0.4f, 1.4f);
                for (LivingEntity e : c.enemies(center.clone().add(0, 0.5, 0), radius)) {
                    DamageContext ctx = c.hit(e, c.damage());
                    if (ctx == null) continue;
                    if (slow > 0) c.services.effects().apply(e, "slow", tick / 20.0 + 0.5, slow, c.player);
                    if (pull > 0) c.pull(e, center, pull * 4, 0);
                }
            }
            return true;
        }, () -> { if (ground != null) ground.remove(); });
    }

    /** 바라보는 지점에 소용돌이 — duration 동안 끌어당김(pull_strength/틱)·tick 피해, 끝에 burst_damage. */
    static void vortex(SkillCast c) {
        double range = c.num("range", 12);
        double radius = c.num("radius", 5);
        int duration = SkillCast.ticks(c.num("duration", 2.5));
        double pullStrength = c.num("pull_strength", 0.3);
        int tick = SkillCast.ticks(c.num("tick", 0.5));
        double burst = c.num("burst_damage", 0);
        Location center = c.targetPoint(range).add(0, 0.6, 0);
        String fx = c.fx(null);
        Color col = c.color();
        ItemDisplay d = fx != null ? Fx.spawn(c.services, center.clone(), fx, (float) (radius / 2.5), 0) : null;
        c.sound(Sound.ENTITY_ENDER_DRAGON_FLAP, 0.6f, 0.6f);
        c.repeat(1, duration, t -> {
            if (d != null && d.isValid()) Fx.transform(d, (float) Math.toRadians(t * 18), (float) (radius / 2.5),
                    (float) (radius / 2.5), (float) (radius / 2.5), 1);
            for (int i = 0; i < 3; i++) {
                double a = t * 0.5 + i * Math.PI * 2 / 3;
                double r = radius * (1 - (t % 20) / 20.0);
                Fx.dust(center.clone().add(Math.cos(a) * r, 0.2 + (t % 10) * 0.05, Math.sin(a) * r), col, 1.3f, 1, 0.05);
            }
            center.getWorld().spawnParticle(Particle.PORTAL, center, 4, radius / 3, 0.3, radius / 3, 0.5);
            List<LivingEntity> in = c.enemies(center, radius);
            for (LivingEntity e : in) {
                if (c.isBoss(e)) continue;
                Vector v = center.toVector().subtract(e.getLocation().toVector());
                double len = v.length();
                if (len > 0.7) e.setVelocity(e.getVelocity().multiply(0.6).add(v.multiply(pullStrength / len).setY(0.02)));
            }
            if (t % tick == 0 && c.damage() > 0) for (LivingEntity e : in) c.hit(e, c.damage());
            if (t % 20 == 0) center.getWorld().playSound(center, Sound.ENTITY_PHANTOM_FLAP, 0.4f, 0.5f);
            return true;
        }, () -> {
            if (d != null) d.remove();
            if (burst > 0 && c.player.isOnline()) {
                for (LivingEntity e : c.enemies(center, radius)) c.hit(e, burst, 0.6);
                center.getWorld().spawnParticle(Particle.EXPLOSION_EMITTER, center, 1);
                Fx.dust(center, col, 2.0f, 40, radius / 2);
                center.getWorld().playSound(center, Sound.ENTITY_GENERIC_EXPLODE, 0.9f, 0.7f);
            }
        });
    }

    /** duration 동안 회전 채널 — tick 마다 주위 피해, 이동 가능(move_slow), 흡혈. */
    static void whirlwind(SkillCast c) {
        double radius = c.num("radius", 3.5);
        int duration = SkillCast.ticks(c.num("duration", 3));
        int tick = SkillCast.ticks(c.num("tick", 0.4));
        double moveSlow = c.num("move_slow", 0);
        double pull = c.num("pull", 0);
        double lifesteal = c.num("lifesteal", 0);
        String fx = c.fx(null);
        Color col = c.color();
        if (moveSlow > 0) c.services.effects().applyBuff(c.player, Map.of("move_speed", -moveSlow), duration / 20.0, c.sourceId());
        ItemDisplay d = fx != null ? Fx.spawn(c.services, c.player.getLocation().add(0, 1, 0), fx, (float) (radius / 1.6), 0) : null;
        c.repeat(1, duration, t -> {
            Location at = c.player.getLocation();
            if (d != null && d.isValid()) {
                d.teleport(at.clone().add(0, 1, 0));
                Fx.transform(d, (float) Math.toRadians(t * 40), (float) (radius / 1.6), (float) (radius / 1.6), (float) (radius / 1.6), 1);
            }
            double a = t * 0.9;
            for (int i = 0; i < 2; i++) {
                double aa = a + i * Math.PI;
                Fx.dust(at.clone().add(Math.cos(aa) * radius * 0.8, 1.0, Math.sin(aa) * radius * 0.8), col, 1.5f, 2, 0.1);
            }
            if (t % tick == 0) {
                at.getWorld().playSound(at, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 0.7f, 1.4f);
                at.getWorld().spawnParticle(Particle.SWEEP_ATTACK, at.clone().add(0, 1, 0), 3, radius / 2, 0.2, radius / 2);
                for (LivingEntity e : c.enemies(at.clone().add(0, 1, 0), radius)) {
                    DamageContext ctx = c.hit(e, c.damage());
                    if (ctx == null) continue;
                    if (lifesteal > 0 && ctx.dealt() > 0) c.services.damage().lifesteal(c.player, e, ctx.dealt() * lifesteal, false);
                    if (pull > 0) c.pull(e, at, pull * 3, 0);
                }
            }
            return true;
        }, () -> { if (d != null) d.remove(); });
    }
}
