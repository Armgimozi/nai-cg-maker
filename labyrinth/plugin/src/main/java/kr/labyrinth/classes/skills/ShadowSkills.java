package kr.labyrinth.classes.skills;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/** 그림자 (암살자): 그림자 일격 · 연막 · 독날 · 그림자 처형. */
public final class ShadowSkills {

    private ShadowSkills() {}

    public static List<Skill> all() { return List.of(new ShadowStrike(), new SmokeVeil(), new VenomBlades(), new ShadowExecution()); }

    /** 대상 바로 곁(시전자 쪽, 또는 등 뒤)으로 안전하게 이동. */
    static Location besideTarget(Player p, LivingEntity t, boolean behind) {
        Location tl = t.getLocation();
        Vector away;
        if (behind) {
            away = tl.getDirection().setY(0);
            if (away.lengthSquared() < 1e-6) away = new Vector(0, 0, 1);
            away.normalize().multiply(-(t.getWidth() / 2 + 0.7));
        } else {
            away = p.getLocation().toVector().subtract(tl.toVector()).setY(0);
            if (away.lengthSquared() < 1e-6) away = new Vector(0, 0, 1);
            away.normalize().multiply(t.getWidth() / 2 + 0.7);
        }
        Location dest = tl.clone().add(away);
        if (!Targeting.fits(dest)) dest = Targeting.safeAlong(p.getLocation(), tl.toVector().subtract(p.getLocation().toVector()),
                Math.max(0, p.getLocation().distance(tl) - 1.0));
        Vector face = tl.toVector().subtract(dest.toVector());
        if (face.lengthSquared() > 1e-6) dest.setDirection(face);
        return dest;
    }

    static void slashFx(SkillContext c, Location from, Location to) {
        Location mid = from.clone().add(to).multiply(0.5).add(0, 1.0, 0);
        Vector d = to.toVector().subtract(from.toVector());
        if (d.lengthSquared() > 1e-6) mid.setDirection(d);
        ItemDisplay dash = SkillFx.spawn(c.fx("fx", "shadow_dash"), mid, 1f, 6);
        if (dash == null) SkillFx.line(from.clone().add(0, 1, 0), to.clone().add(0, 1, 0), 0.3, Particle.DUST, SkillFx.dust(0x4a3a8a, 1.2f));
        SkillFx.line(from.clone().add(0, 0.9, 0), to.clone().add(0, 0.9, 0), 0.5, Particle.SMOKE, null);
    }

    static final class ShadowStrike implements Skill {
        public String id() { return "shadow_strike"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            LivingEntity t = c.targets().lookedAtEnemy(c.p("dash", 6) + 1.5);
            if (t == null) return c.fail("<#ff8080>돌진할 적을 바라보세요");
            double backAngle = c.p("back_angle", 100);
            boolean behind = Targeting.isBehind(p, t, backAngle);
            Location from = p.getLocation();
            Location dest = besideTarget(p, t, false);
            p.teleport(dest);
            p.setFallDistance(0);
            slashFx(c, from, dest);
            SkillFx.sound(dest, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 1.6f);
            SkillFx.sound(dest, Sound.ENTITY_PHANTOM_FLAP, 0.8f, 1.6f);
            double mult = behind ? c.p("back_damage", 3.0) : c.p("damage", 1.8);
            DamageContext r = c.services().targets().isEnemy(p, t)
                    ? c.services().damage().deal(DamageContext.skill(p, t, mult * c.skillScale(), DamageType.MELEE, c.kind(DamageType.MELEE), id())
                    .critBonus(behind && c.flag("back_guaranteed_crit", true) ? 2.0 : 0))
                    : null;
            if (r != null && behind) {
                SkillFx.burst(t.getLocation().add(0, t.getHeight() * 0.6, 0), Particle.DAMAGE_INDICATOR, 6, 0.3, 0.1, null);
                SkillFx.sound(t.getLocation(), Sound.ENTITY_PLAYER_ATTACK_CRIT, 1f, 0.7f);
            }
            return true;
        }
    }

    static final class SmokeVeil implements Skill {
        public String id() { return "smoke_veil"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location center = Targeting.dropToGround(p.getLocation(), 4);
            double radius = c.p("radius", 4);
            double duration = c.p("duration", 5);
            int life = (int) (duration * 20);
            ItemDisplay dome = SkillFx.spawn(c.fx("fx", "smoke_cloud"), center.clone().add(0, 0.2, 0),
                    (float) (radius * 2 / SkillFx.modelWidth(c.fx("fx", "smoke_cloud"))), life);
            SkillFx.spin(dome, 1.5f, life);
            SkillFx.burst(center.clone().add(0, 1, 0), Particle.CAMPFIRE_COSY_SMOKE, 30, radius * 0.4, 0.01, null);
            SkillFx.sound(center, Sound.BLOCK_FIRE_EXTINGUISH, 1f, 0.6f);
            c.services().effects().stealth(p, c.p("stealth", 3.0), c.p("stealth_bonus", 0.50));
            if (c.flag("drop_aggro", true)) {
                List<Player> others = new ArrayList<>(c.targets().alliesIn(center, 24));
                others.remove(p);
                for (LivingEntity e : c.targets().enemiesIn(center, 24)) {
                    c.mob(e).ifPresent(m -> {
                        if (p.equals(m.target()) && !others.isEmpty()) m.taunt(others.get(0), 0.5);
                    });
                }
            }
            double evasion = c.p("evasion", 0.50);
            SkillTask.repeat(0, 5, life / 5 + 1, step -> {
                for (Player a : c.targets().alliesIn(center, radius)) {
                    c.services().effects().applyBuff(a, Map.of("evasion", evasion), 0.6, "smoke_veil");
                }
                SkillFx.disc(center, radius, 14, Particle.LARGE_SMOKE, null);
                return true;
            }, null);
            return true;
        }
    }

    public static final class VenomBlades implements Skill {
        public String id() { return "venom_blades"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double duration = c.p("duration", 8);
            c.services().effects().applyBuff(p, Map.of("venom_blades", 1.0), duration, "venom_blades");
            SkillFx.burst(p.getLocation().add(0, 1, 0), Particle.DUST, 30, 0.4, 0, SkillFx.dust(0x6ad13a, 1.3f));
            SkillFx.sound(p.getLocation(), Sound.ENTITY_SPIDER_AMBIENT, 0.8f, 1.6f);
            SkillFx.sound(p.getLocation(), Sound.ITEM_BOTTLE_EMPTY, 1f, 0.8f);
            SkillTask.repeat(0, 4, (int) (duration * 5), step -> {
                if (!p.isOnline() || p.isDead() || !c.services().effects().hasBuff(p, "venom_blades")) return false;
                Location hand = p.getLocation().add(0, 1.0, 0).add(p.getLocation().getDirection().setY(0).normalize()
                        .rotateAroundY(-Math.PI / 4).multiply(0.45));
                SkillFx.burst(hand, Particle.DUST, 2, 0.05, 0, SkillFx.dust(0x6ad13a, 0.8f));
                if (step % 3 == 0) SkillFx.burst(hand, Particle.FALLING_SPORE_BLOSSOM, 1, 0.05, 0, null);
                return true;
            }, null);
            return true;
        }

        /** 독날 활성 중 적중 1회 → 독 중첩 (ClassPassives 의 피해 훅이 부른다). */
        public static void onHit(kr.labyrinth.Services services, Player shadow, LivingEntity target, kr.labyrinth.content.ClassDef cls) {
            var sk = cls.skills().stream().filter(s -> s.id().equals("venom_blades")).findFirst().orElse(null);
            if (sk == null) return;
            var pr = sk.params();
            double ratio = SkillContext.dotRatio(pr.dbl("dps_per_stack", 0.10), SkillContext.skillScale(cls));
            services.effects().apply(target, "venom", pr.dbl("stack_duration", 6), ratio, shadow);
            if (services.effects().stacks(target, "venom") >= pr.integer("max_stacks", 5)) {
                services.effects().apply(target, "weaken", pr.dbl("stack_duration", 6), pr.dbl("weaken_at_max", 0.10), shadow);
            }
        }
    }

    static final class ShadowExecution implements Skill {
        public String id() { return "shadow_execution"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double radius = c.p("radius", 10);
            List<LivingEntity> enemies = new ArrayList<>(c.targets().enemiesIn(p.getLocation(), radius));
            enemies.removeIf(e -> !p.hasLineOfSight(e));
            if (enemies.isEmpty()) return c.fail("<#ff8080>주변에 벨 적이 없습니다");
            int max = c.pi("max_targets", 6);
            List<LivingEntity> seq = new ArrayList<>();
            if (enemies.size() == 1) {
                int hits = c.pi("boss_hits", 3);
                for (int i = 0; i < hits; i++) seq.add(enemies.get(0));
            } else {
                seq.addAll(enemies.subList(0, Math.min(max, enemies.size())));
            }
            int interval = Math.max(2, (int) Math.round(c.p("interval", 0.25) * 20));
            double threshold = c.p("execute_threshold", 0.30);
            double bonus = c.p("execute_bonus", 1.0);
            double dmg = c.p("damage", 2.2);
            BerserkerSkills.LEAPING.add(p.getUniqueId());
            c.services().effects().applyBuff(p, Map.of("evasion", 0.4), seq.size() * interval / 20.0 + 0.5, "shadow_execution");
            SkillFx.sound(p.getLocation(), Sound.ENTITY_ILLUSIONER_PREPARE_MIRROR, 1f, 1.4f);
            Location[] last = {p.getLocation()};
            SkillTask.repeat(0, interval, seq.size(), i -> {
                if (!p.isOnline() || p.isDead()) return false;
                LivingEntity t = seq.get(i);
                if (!t.isValid() || t.isDead()) return true;
                Location dest = besideTarget(p, t, true);
                p.teleport(dest);
                p.setFallDistance(0);
                slashFx(c, last[0], dest);
                last[0] = dest;
                double mult = dmg * (c.hpRatio(t) <= threshold ? 1 + bonus : 1);
                DamageContext r = c.damage(t, mult, DamageType.MELEE);
                if (r != null && c.hpRatio(t) <= threshold) SkillFx.burst(t.getLocation().add(0, 1, 0), Particle.DUST, 16, 0.3, 0, SkillFx.dust(0x8a0000, 1.4f));
                SkillFx.sound(dest, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 1.3f + i * 0.08f);
                SkillFx.burst(t.getLocation().add(0, t.getHeight() * 0.6, 0), Particle.SWEEP_ATTACK, 1, 0, 0, null);
                return true;
            }, () -> {
                SkillFx.later(10, () -> BerserkerSkills.LEAPING.remove(p.getUniqueId()));
                SkillFx.burst(p.getLocation().add(0, 1, 0), Particle.LARGE_SMOKE, 20, 0.4, 0.02, null);
            });
            return true;
        }
    }
}
