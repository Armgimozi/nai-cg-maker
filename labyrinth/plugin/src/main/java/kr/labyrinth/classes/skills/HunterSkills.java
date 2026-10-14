package kr.labyrinth.classes.skills;

import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.core.Text;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/** 사냥꾼 (원거리): 관통 화살 · 사냥꾼의 표식 · 회피 덫 · 화살비. */
public final class HunterSkills {

    private HunterSkills() {}

    public static List<Skill> all() { return List.of(new PiercingArrow(), new HuntersMark(), new EvasiveTrap(), new ArrowStorm()); }

    static final class PiercingArrow implements Skill {
        public String id() { return "piercing_arrow"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location eye = p.getEyeLocation();
            double falloff = c.p("falloff", 0.20);
            double dmg = c.p("damage", 2.0);
            SkillFx.sound(eye, Sound.ITEM_CROSSBOW_SHOOT, 1f, 0.8f);
            SkillFx.sound(eye, Sound.ENTITY_ARROW_SHOOT, 1f, 1.4f);
            new SkillProjectile(c, eye.clone().add(eye.getDirection().multiply(0.6)).subtract(0, 0.15, 0), eye.getDirection())
                    .speed(c.p("speed", 3.0)).range(c.p("range", 40)).pierce(c.pi("pierce", 4)).hitRadius(0.45)
                    .model(c.fx("fx", "proj_piercing_arrow"))
                    .trail(Particle.DUST, SkillFx.dust(0xc8f08a, 0.9f))
                    .onHit((e, i) -> {
                        c.damage(e, dmg * Math.pow(1 - falloff, i), DamageType.RANGED);
                        SkillFx.burst(e.getLocation().add(0, e.getHeight() * 0.6, 0), Particle.CRIT, 10, 0.2, 0.3, null);
                        SkillFx.sound(e.getLocation(), Sound.ENTITY_ARROW_HIT, 0.8f, 1.2f + i * 0.1f);
                    })
                    .launch();
            return true;
        }
    }

    static final class HuntersMark implements Skill {
        public String id() { return "hunters_mark"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            LivingEntity t = c.targets().lookedAtEnemy(c.p("range", 32));
            if (t == null) return c.fail("<#ff8080>표식을 남길 적을 바라보세요");
            double duration = c.p("duration", 10);
            c.services().effects().apply(t, "mark", duration, c.p("damage_taken", 0.20), p);
            if (c.flag("reveal", true)) c.services().effects().breakStealth(t);
            SkillFx.line(p.getEyeLocation(), t.getLocation().add(0, t.getHeight() * 0.6, 0), 0.6, Particle.DUST, SkillFx.dust(0xffb060, 0.8f));
            SkillFx.burst(t.getLocation().add(0, t.getHeight() + 0.5, 0), Particle.DUST, 20, 0.3, 0, SkillFx.dust(0xc84a1a, 1.4f));
            SkillFx.sound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.7f, 0.6f);
            SkillFx.sound(t.getLocation(), Sound.BLOCK_NOTE_BLOCK_PLING, 0.8f, 0.5f);
            String name = c.mob(t).map(m -> m.displayName()).orElse(t instanceof Player tp ? Text.escape(tp.getName()) : "대상");
            for (Player a : c.targets().alliesIn(p.getLocation(), 48)) {
                c.services().hud().actionBar(a, Text.mm("<#ffb060>◎ 표식: </#ffb060>" + name + " <gray>— 받는 피해 +"
                        + Text.pct(c.p("damage_taken", 0.20)) + " (" + (int) duration + "초)"), 40);
            }
            return true;
        }
    }

    static final class EvasiveTrap implements Skill {
        public String id() { return "evasive_trap"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location trapAt = Targeting.dropToGround(p.getLocation(), 4);
            Vector back = p.getLocation().getDirection().setY(0);
            if (back.lengthSquared() < 1e-6) back = new Vector(0, 0, 1);
            back.normalize().multiply(-c.p("leap", 1.3));
            back.setY(0.55);
            p.setVelocity(back);
            BerserkerSkills.LEAPING.add(p.getUniqueId());
            SkillFx.later(40, () -> BerserkerSkills.LEAPING.remove(p.getUniqueId()));
            SkillFx.burst(p.getLocation(), Particle.CLOUD, 10, 0.3, 0.05, null);
            SkillFx.sound(p.getLocation(), Sound.ENTITY_BAT_TAKEOFF, 0.8f, 1.2f);
            double radius = c.p("trap_radius", 2.0);
            double life = c.p("trap_duration", 15);
            ItemDisplay trap = SkillFx.ground(c.fx("fx", "snare_trap"), trapAt, radius * 2, (int) (life * 20), 4);
            SkillFx.sound(trapAt, Sound.BLOCK_CHAIN_PLACE, 1f, 0.8f);
            SkillTask.repeat(10, 5, (int) (life * 4), step -> {
                if (!p.isOnline()) return false;
                List<LivingEntity> in = c.targets().enemiesIn(trapAt, radius);
                if (in.isEmpty()) {
                    if (trap == null && step % 4 == 0) SkillFx.circle(trapAt.clone().add(0, 0.1, 0), radius, 16, Particle.DUST, SkillFx.dust(0xa8c46a, 1f));
                    return true;
                }
                for (LivingEntity e : in) {
                    c.damage(e, c.p("trap_damage", 1.0), DamageType.RANGED);
                    c.services().effects().apply(e, "root", c.isBoss(e) ? 0 : c.p("trap_root", 2.5), 1, p);
                    if (c.isBoss(e)) c.services().effects().apply(e, "slow", c.p("trap_root", 2.5), 0.4, p);
                }
                SkillFx.sound(trapAt, Sound.ENTITY_IRON_GOLEM_DAMAGE, 0.9f, 1.6f);
                SkillFx.burst(trapAt.clone().add(0, 0.4, 0), Particle.CRIT, 20, radius * 0.4, 0.2, null);
                return false;
            }, () -> SkillFx.remove(trap));
            return true;
        }
    }

    static final class ArrowStorm implements Skill {
        public String id() { return "arrow_storm"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location center = c.targets().groundTarget(c.p("range", 28));
            double radius = c.p("radius", 6);
            double duration = c.p("duration", 4);
            double tick = Math.max(0.25, c.p("tick", 0.5));
            int period = (int) Math.round(tick * 20);
            SkillFx.sound(p.getLocation(), Sound.ITEM_CROSSBOW_SHOOT, 1f, 0.5f);
            SkillFx.ground("telegraph_circle", center, radius * 2, (int) (duration * 20) + 10, 5);
            SkillTask.repeat(4, 2, (int) (duration * 10), step -> {
                if (!p.isOnline()) return false;
                var rnd = ThreadLocalRandom.current();
                for (int i = 0; i < 6; i++) {
                    double r = radius * Math.sqrt(rnd.nextDouble());
                    double a = rnd.nextDouble() * Math.PI * 2;
                    Location ground = center.clone().add(Math.cos(a) * r, 0.1, Math.sin(a) * r);
                    SkillFx.line(ground.clone().add(0.6, 7, 0.3), ground, 0.7, Particle.CRIT, null);
                    SkillFx.burst(ground, Particle.DUST, 2, 0.1, 0, SkillFx.dust(0x8fd16a, 0.8f));
                }
                if (step % 2 == 0) SkillFx.sound(center, Sound.ENTITY_ARROW_HIT, 0.9f, 0.8f + rnd.nextFloat() * 0.6f);
                if ((step * 2) % period == 0) {
                    for (LivingEntity e : c.targets().enemiesIn(center, radius)) {
                        DamageContext r = c.damage(e, c.p("damage", 0.6), DamageType.RANGED);
                        if (r != null) c.services().effects().apply(e, "slow", tick + 0.3, c.p("slow", 0.25), p);
                    }
                }
                return true;
            }, null);
            return true;
        }
    }
}
