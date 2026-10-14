package kr.labyrinth.classes.skills;

import java.util.List;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/** 비전술사 (마법 광역): 마력탄 · 서리 고리 · 위상 도약 · 운석 낙하. */
public final class ArcanistSkills {

    private ArcanistSkills() {}

    public static List<Skill> all() { return List.of(new ArcaneBolt(), new FrostNova(), new PhaseBlink(), new MeteorFall()); }

    static final class ArcaneBolt implements Skill {
        public String id() { return "arcane_bolt"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location eye = p.getEyeLocation();
            double range = c.p("range", 24);
            LivingEntity target = c.targets().enemyInView(range, 40);
            SkillFx.sound(eye, Sound.ENTITY_EVOKER_CAST_SPELL, 0.8f, 1.6f);
            SkillFx.burst(eye.clone().add(eye.getDirection()), Particle.ENCHANT, 12, 0.2, 0.4, null);
            new SkillProjectile(c, eye.clone().add(eye.getDirection().multiply(0.8)).subtract(0, 0.2, 0), eye.getDirection())
                    .speed(c.p("speed", 1.2)).range(range).pierce(1).hitRadius(0.55)
                    .homing(c.p("homing", 0.15), target)
                    .model(c.fx("fx", "proj_arcane_bolt"))
                    .trail(Particle.DUST, SkillFx.dust(0xb07cff, 1.0f))
                    .onHit((e, i) -> {
                        c.damage(e, c.p("damage", 1.6), DamageType.MAGIC);
                        c.reportHits(1);
                    })
                    .onEnd(at -> {
                        SkillFx.burst(at, Particle.DUST, 16, 0.3, 0, SkillFx.dust(0xd8b8ff, 1.2f));
                        SkillFx.burst(at, Particle.END_ROD, 6, 0.1, 0.08, null);
                        SkillFx.sound(at, Sound.BLOCK_AMETHYST_BLOCK_BREAK, 0.8f, 1.4f);
                    })
                    .launch();
            return true;
        }
    }

    static final class FrostNova implements Skill {
        public String id() { return "frost_nova"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double radius = c.p("radius", 5);
            Location center = p.getLocation();
            SkillFx.ground(c.fx("fx", "frost_nova_ring"), center, radius * 2, 14, 6);
            SkillFx.disc(center, radius, 40, Particle.SNOWFLAKE, null);
            SkillFx.sound(center, Sound.BLOCK_GLASS_BREAK, 1f, 0.7f);
            SkillFx.sound(center, Sound.ENTITY_PLAYER_HURT_FREEZE, 1f, 0.8f);
            int hits = 0;
            for (LivingEntity e : c.targets().enemiesIn(center, radius)) {
                DamageContext r = c.damage(e, c.p("damage", 1.2), DamageType.MAGIC);
                if (r == null || r.cancelled()) continue;
                hits++;
                if (c.isBoss(e)) {
                    c.services().effects().apply(e, "slow", c.p("boss_slow_duration", 3), c.p("boss_slow", 0.30), p);
                } else {
                    c.services().effects().apply(e, "root", c.p("root", 2.0), 1, p);
                    SkillFx.burst(e.getLocation().add(0, 0.5, 0), Particle.ITEM_SNOWBALL, 12, 0.3, 0.05, null);
                }
            }
            c.reportHits(hits);
            return true;
        }
    }

    static final class PhaseBlink implements Skill {
        public String id() { return "phase_blink"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location origin = p.getLocation();
            Vector dir = origin.getDirection();
            Location dest = Targeting.safeAlong(origin, dir.clone().setY(Math.max(-0.3, Math.min(0.3, dir.getY()))), c.p("distance", 8));
            if (dest.distanceSquared(origin) < 1.0) return c.fail("<#ff8080>앞이 막혀 있습니다");
            SkillFx.burst(origin.clone().add(0, 1, 0), Particle.REVERSE_PORTAL, 40, 0.3, 0.1, null);
            SkillFx.line(origin.clone().add(0, 1, 0), dest.clone().add(0, 1, 0), 0.4, Particle.DUST, SkillFx.dust(0xb07cff, 1.0f));
            p.teleport(dest);
            p.setFallDistance(0);
            SkillFx.burst(dest.clone().add(0, 1, 0), Particle.PORTAL, 40, 0.3, 0.6, null);
            SkillFx.sound(origin, Sound.ENTITY_ENDERMAN_TELEPORT, 0.8f, 1.4f);
            SkillFx.sound(dest, Sound.ENTITY_ILLUSIONER_MIRROR_MOVE, 1f, 1.2f);
            double echoRadius = c.p("echo_radius", 3);
            int delay = (int) Math.round(c.p("echo_delay", 1.5) * 20);
            ItemDisplay echo = SkillFx.ground(c.fx("fx", "blink_echo"), origin, echoRadius * 2, delay + 2, 4);
            SkillFx.spin(echo, 12f, delay);
            SkillFx.later(delay, () -> {
                SkillFx.burst(origin.clone().add(0, 0.8, 0), Particle.DUST, 40, echoRadius * 0.4, 0, SkillFx.dust(0xb07cff, 1.6f));
                SkillFx.burst(origin.clone().add(0, 0.8, 0), Particle.END_ROD, 24, 0.2, 0.25, null);
                SkillFx.sound(origin, Sound.ENTITY_GENERIC_EXPLODE, 0.6f, 1.6f);
                int hits = 0;
                for (LivingEntity e : c.targets().enemiesIn(origin, echoRadius)) {
                    DamageContext r = c.damage(e, c.p("echo_damage", 1.0), DamageType.MAGIC);
                    if (r != null && !r.cancelled()) hits++;
                }
                c.reportHits(hits);
            });
            return true;
        }
    }

    static final class MeteorFall implements Skill {
        public String id() { return "meteor_fall"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location target = c.targets().groundTarget(c.p("range", 30));
            double radius = c.p("radius", 6);
            double delaySec = c.p("delay", 1.5);
            int delay = Math.max(5, (int) Math.round(delaySec * 20));
            SkillFx.ground("telegraph_circle", target, radius * 2, delay, 4);
            SkillFx.sound(p.getLocation(), Sound.ENTITY_EVOKER_PREPARE_SUMMON, 1f, 0.8f);
            Location start = target.clone().add(-5, 18, -5);
            ItemDisplay meteor = SkillFx.spawn(c.fx("fx", "meteor"), start, 1.6f, delay + 2);
            if (meteor != null) meteor.setTeleportDuration(2);
            Vector step = target.toVector().subtract(start.toVector()).multiply(1.0 / delay);
            SkillTask.repeat(0, 1, delay, i -> {
                Location at = start.clone().add(step.clone().multiply(i + 1));
                if (meteor != null && meteor.isValid() && i % 2 == 0) meteor.teleport(at);
                SkillFx.burst(at, Particle.FLAME, 6, 0.4, 0.02, null);
                SkillFx.burst(at, Particle.LARGE_SMOKE, 2, 0.3, 0.01, null);
                if (i % 4 == 0) SkillFx.circle(target.clone().add(0, 0.15, 0), radius * (1 - (double) i / delay) + 0.3, 24, Particle.FLAME, null);
                return true;
            }, () -> {
                SkillFx.remove(meteor);
                SkillFx.burst(target.clone().add(0, 1, 0), Particle.EXPLOSION_EMITTER, 1, 0, 0, null);
                SkillFx.burst(target.clone().add(0, 0.5, 0), Particle.LAVA, 30, radius * 0.3, 0.1, null);
                SkillFx.ground(c.fx("fx_ring", "ember_burst"), target, radius * 2, 16, 6);
                SkillFx.sound(target, Sound.ENTITY_GENERIC_EXPLODE, 1.4f, 0.6f);
                SkillFx.sound(target, Sound.ENTITY_BLAZE_SHOOT, 1f, 0.5f);
                int hits = 0;
                for (LivingEntity e : c.targets().enemiesIn(target, radius)) {
                    DamageContext r = c.damage(e, c.p("damage", 5.0), DamageType.MAGIC, 1.0, 1.0);
                    if (r != null && !r.cancelled()) hits++;
                }
                c.reportHits(hits);
                double burnDur = c.p("burn_duration", 4);
                double burnDps = c.p("burn_dps", 0.30);
                SkillTask.repeat(0, 10, (int) (burnDur * 2), k -> {
                    if (!p.isOnline()) return false;
                    SkillFx.disc(target, radius, 25, Particle.FLAME, null);
                    SkillFx.disc(target, radius, 6, Particle.SMOKE, null);
                    for (LivingEntity e : c.targets().enemiesIn(target, radius)) c.services().effects().apply(e, "burn", 1.2, burnDps, p);
                    return true;
                }, null);
            });
            return true;
        }
    }
}
