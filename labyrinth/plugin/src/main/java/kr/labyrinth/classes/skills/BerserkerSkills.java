package kr.labyrinth.classes.skills;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/** 광전사 (근접 딜러): 회전 베기 · 대지 가르기 · 피의 갈망 · 파멸의 도약. */
public final class BerserkerSkills {

    /** 도약 중(낙하 피해 무시) 플레이어. ClassesModule 의 낙하 리스너가 읽는다. */
    public static final Set<UUID> LEAPING = ConcurrentHashMap.newKeySet();

    private BerserkerSkills() {}

    public static List<Skill> all() { return List.of(new SpinSlash(), new GroundCleaver(), new BloodFrenzy(), new RuinousLeap()); }

    static final class SpinSlash implements Skill {
        public String id() { return "spin_slash"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double radius = c.p("radius", 3.5);
            Location center = p.getLocation().add(0, 1.0, 0);
            ItemDisplay arc = SkillFx.spawn(c.fx("fx", "slash_arc"), center, (float) (radius * 2 / SkillFx.modelWidth(c.fx("fx", "slash_arc"))), 8);
            SkillFx.spin(arc, 45f, 8);
            for (int i = 0; i < 3; i++) {
                final int k = i;
                SkillFx.later(i * 2L, () -> SkillFx.arc(center, new Vector(Math.cos(k * 2.1), 0, Math.sin(k * 2.1)), radius * 0.9, 140, 16,
                        Particle.SWEEP_ATTACK, null));
            }
            SkillFx.sound(p.getLocation(), Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 0.7f);
            SkillFx.sound(p.getLocation(), Sound.ITEM_TRIDENT_RIPTIDE_1, 0.6f, 1.4f);
            for (LivingEntity e : c.targets().enemiesIn(p.getLocation(), radius)) {
                DamageContext r = c.damage(e, c.p("damage", 1.4), DamageType.MELEE, 1.0, 0.4);
                if (r == null || r.cancelled() || r.evaded()) continue;
                c.services().effects().apply(e, "bleed", c.p("bleed_duration", 4), c.p("bleed_ratio", 0.15), p);
            }
            return true;
        }
    }

    static final class GroundCleaver implements Skill {
        public String id() { return "ground_cleaver"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Vector dir = p.getLocation().getDirection().setY(0);
            if (dir.lengthSquared() < 1e-6) dir = new Vector(0, 0, 1);
            dir.normalize();
            double length = c.p("length", 9);
            double width = c.p("width", 2.0);
            Location start = p.getLocation();
            String fx = c.fx("fx", "shockwave");
            SkillFx.sound(start, Sound.ENTITY_GENERIC_EXPLODE, 0.7f, 0.6f);
            SkillFx.sound(start, Sound.BLOCK_ANVIL_LAND, 0.6f, 0.5f);
            final Vector d = dir;
            int segments = (int) Math.ceil(length / 1.5);
            for (int i = 0; i < segments; i++) {
                final double t = 1.0 + i * 1.5;
                SkillFx.later(1 + i, () -> {
                    Location at = Targeting.dropToGround(start.clone().add(d.clone().multiply(t)).add(0, 1, 0), 3);
                    SkillFx.ground(fx, at, width * 1.4, 10, 4);
                    var below = at.clone().subtract(0, 0.5, 0).getBlock();
                    if (!below.isPassable()) SkillFx.burst(at.clone().add(0, 0.2, 0), Particle.BLOCK, 14, 0.4, 0.1, below.getBlockData());
                    SkillFx.burst(at.clone().add(0, 0.3, 0), Particle.CRIT, 6, 0.3, 0.2, null);
                });
            }
            for (LivingEntity e : c.targets().enemiesInLine(start.clone().add(0, 0.5, 0), dir, length, width)) {
                DamageContext r = c.damage(e, c.p("damage", 1.8), DamageType.MELEE);
                if (r == null || r.cancelled()) continue;
                double launch = c.isBoss(e) ? c.p("boss_launch", 0) : c.p("launch", 0.6);
                if (launch > 0 && !c.services().effects().isKnockbackImmune(e)) {
                    e.setVelocity(e.getVelocity().setY(Math.max(e.getVelocity().getY(), launch)));
                }
            }
            return true;
        }
    }

    static final class BloodFrenzy implements Skill {
        public String id() { return "blood_frenzy"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            var stats = c.services().stats();
            double cur = stats.currentHp(p);
            double cost = cur * c.p("hp_cost", 0.10);
            if (cur - cost < 1) return c.fail("<#ff8080>HP 가 너무 적습니다");
            stats.setHp(p, cur - cost);
            double duration = c.p("duration", 8);
            c.services().effects().applyBuff(p, Map.of(
                    "attack_speed", c.p("attack_speed", 0.30),
                    "damage", c.p("damage", 0.20),
                    "lifesteal", c.p("lifesteal", 0.10)), duration, "blood_frenzy");
            SkillFx.burst(p.getLocation().add(0, 1, 0), Particle.DUST, 40, 0.5, 0, SkillFx.dust(0xa01010, 1.6f));
            SkillFx.sound(p.getLocation(), Sound.ENTITY_WARDEN_HEARTBEAT, 1f, 1.2f);
            SkillFx.sound(p.getLocation(), Sound.ENTITY_RAVAGER_ROAR, 0.5f, 1.6f);
            SkillTask.repeat(0, 4, (int) (duration * 5), step -> {
                if (!p.isOnline() || p.isDead() || !c.services().effects().hasBuff(p, "blood_frenzy")) return false;
                SkillFx.circle(p.getLocation().add(0, 0.1 + (step % 10) * 0.2, 0), 0.6, 8, Particle.DUST, SkillFx.dust(0xff3a2a, 1.0f));
                if (step % 5 == 0) SkillFx.burst(p.getLocation().add(0, 1.2, 0), Particle.DAMAGE_INDICATOR, 2, 0.3, 0.05, null);
                return true;
            }, null);
            return true;
        }
    }

    static final class RuinousLeap implements Skill {
        public String id() { return "ruinous_leap"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location target = c.targets().groundTarget(c.p("range", 12));
            Vector delta = target.toVector().subtract(p.getLocation().toVector());
            double horiz = Math.hypot(delta.getX(), delta.getZ());
            Vector vel = delta.clone().setY(0);
            if (vel.lengthSquared() > 1e-6) vel.normalize().multiply(Math.min(2.2, 0.35 + horiz * 0.16));
            vel.setY(Math.max(0.7, Math.min(1.3, 0.75 + delta.getY() * 0.1 + horiz * 0.02)));
            p.setVelocity(vel);
            LEAPING.add(p.getUniqueId());
            SkillFx.sound(p.getLocation(), Sound.ENTITY_RAVAGER_ROAR, 0.8f, 0.8f);
            SkillFx.burst(p.getLocation(), Particle.CLOUD, 16, 0.4, 0.05, null);
            double radius = c.p("radius", 5);
            SkillFx.circle(target.clone().add(0, 0.15, 0), radius, 36, Particle.DUST, SkillFx.dust(0xff5a3c, 1.3f));
            SkillTask.repeat(3, 1, 60, step -> {
                if (!p.isOnline() || p.isDead()) return false;
                SkillFx.burst(p.getLocation().add(0, 1, 0), Particle.DUST, 3, 0.2, 0, SkillFx.dust(0xff5a3c, 1.2f));
                boolean grounded = p.getVelocity().getY() <= 0.01 && !p.getLocation().subtract(0, 0.08, 0).getBlock().isPassable();
                return !(grounded && step > 2);
            }, () -> {
                if (!p.isOnline() || p.isDead()) {
                    LEAPING.remove(p.getUniqueId());
                    return;
                }
                Location land = p.getLocation();
                SkillFx.ground(c.fx("fx", "shockwave"), land, radius * 2, 14, 6);
                SkillFx.burst(land.clone().add(0, 0.5, 0), Particle.EXPLOSION, 3, 1.0, 0, null);
                var below = land.clone().subtract(0, 0.5, 0).getBlock();
                if (!below.isPassable()) SkillFx.burst(land.clone().add(0, 0.3, 0), Particle.BLOCK, 60, radius * 0.4, 0.2, below.getBlockData());
                SkillFx.sound(land, Sound.ENTITY_GENERIC_EXPLODE, 1f, 0.7f);
                SkillFx.sound(land, Sound.BLOCK_ANVIL_LAND, 0.8f, 0.5f);
                for (LivingEntity e : c.targets().enemiesIn(land, radius)) {
                    DamageContext r = c.damage(e, c.p("damage", 3.5), DamageType.MELEE, 1.0, 0.8);
                    if (r != null && !r.cancelled()) {
                        c.services().effects().apply(e, "vulnerable", c.p("vuln_duration", 6), c.p("vulnerability", 0.15), p);
                    }
                }
                SkillFx.later(10, () -> LEAPING.remove(p.getUniqueId()));
            });
            return true;
        }
    }
}
