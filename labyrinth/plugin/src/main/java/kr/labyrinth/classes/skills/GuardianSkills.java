package kr.labyrinth.classes.skills;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/** 수호기사 (탱커): 방패 강타 · 도발의 함성 · 수호의 맹세 · 불굴의 성채. */
public final class GuardianSkills {

    private GuardianSkills() {}

    public static List<Skill> all() { return List.of(new ShieldBash(), new TauntingRoar(), new GuardianOath(), new BulwarkCitadel()); }

    /** 전방 부채꼴 강타: 피해 + 기절(보스는 boss_stun, 0 이면 시전 끊기만) + 큰 위협. */
    static final class ShieldBash implements Skill {
        public String id() { return "shield_bash"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Vector dir = p.getLocation().getDirection();
            double range = c.p("range", 3.5);
            List<LivingEntity> hit = c.targets().enemiesInCone(p.getLocation(), dir, range, c.p("angle", 70));
            Location front = p.getLocation().add(dir.clone().setY(0).normalize().multiply(1.4)).add(0, 1.0, 0);
            SkillFx.arc(p.getLocation().add(0, 1.0, 0), dir, range * 0.8, c.p("angle", 70), 14, Particle.DUST, SkillFx.dust(0x7fb2ff, 1.4f));
            SkillFx.burst(front, Particle.ENCHANTED_HIT, 16, 0.4, 0.3, null);
            // 보조손에 방패가 없으면(장비 직업 제한 없음 — 두 손 무기·활 등) 방패 소리 대신 묵직한 밀쳐 치기 소리
            SkillFx.sound(p.getLocation(), holdsShield(c) ? Sound.ITEM_SHIELD_BLOCK : Sound.ENTITY_PLAYER_ATTACK_KNOCKBACK, 1f, 0.6f);
            SkillFx.sound(p.getLocation(), Sound.ENTITY_IRON_GOLEM_ATTACK, 0.8f, 1.2f);
            for (LivingEntity e : hit) {
                DamageContext r = c.damage(e, c.p("damage", 1.2), DamageType.MELEE, c.p("threat", 3.0), 0.6);
                if (r == null || r.cancelled()) continue;
                boolean boss = c.isBoss(e);
                double stun = boss ? c.p("boss_stun", 0) : c.p("stun", 1.0);
                if (stun > 0) c.services().effects().apply(e, "stun", stun, 1, p);
                if (boss && c.flag("interrupt", true)) c.services().effects().apply(e, "interrupt", 0.3, 1, p);
                SkillFx.burst(e.getLocation().add(0, e.getHeight() * 0.6, 0), Particle.CRIT, 10, 0.3, 0.2, null);
            }
            return true;
        }
    }

    private static boolean holdsShield(SkillContext c) {
        var off = c.caster().getInventory().getItemInOffHand();
        return off.getType() == org.bukkit.Material.SHIELD
                || c.services().items().defOf(off).map(kr.labyrinth.content.ItemDef::isShield).orElse(false);
    }

    /** 주변 적 강제 도발 + 자신 피해 감소. */
    static final class TauntingRoar implements Skill {
        public String id() { return "taunting_roar"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double radius = c.p("radius", 8);
            int taunted = 0;
            for (LivingEntity e : c.targets().enemiesIn(p.getLocation(), radius)) {
                var mob = c.mob(e);
                if (mob.isPresent()) {
                    mob.get().taunt(p, c.isBoss(e) ? c.p("boss_duration", 3) : c.p("duration", 4));
                    mob.get().addThreat(p, 50);
                    taunted++;
                    SkillFx.burst(e.getLocation().add(0, e.getHeight() + 0.4, 0), Particle.ANGRY_VILLAGER, 3, 0.3, 0, null);
                } else if (e instanceof org.bukkit.entity.Mob vanilla) {
                    vanilla.setTarget(p);
                    taunted++;
                }
            }
            c.services().effects().applyBuff(p, Map.of("damage_reduction", c.p("damage_reduction", 0.25)), c.p("dr_duration", 5), "taunting_roar");
            ItemDisplay ring = SkillFx.ground("shockwave", p.getLocation(), radius * 2, 14, 8);
            if (ring == null) SkillFx.circle(p.getLocation().add(0, 0.2, 0), radius, 48, Particle.DUST, SkillFx.dust(0x7fb2ff, 1.6f));
            SkillFx.burst(p.getLocation().add(0, 1.6, 0), Particle.SONIC_BOOM, 1, 0, 0, null);
            SkillFx.sound(p.getLocation(), Sound.ENTITY_RAVAGER_ROAR, 1f, 1.1f);
            if (taunted > 0) c.services().hud().actionBar(p, Text.mm("<#7fb2ff>도발! <white>" + taunted + "</white><gray>명이 당신을 노립니다"), 30);
            return true;
        }
    }

    /** 아군과 맹세 연결: 받는 피해의 redirect 비율을 대신 받는다 + 자기 보호막. */
    static final class GuardianOath implements Skill {
        public String id() { return "guardian_oath"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            double range = c.p("range", 15);
            Player ally = c.targets().lookedAtAlly(range);
            if (ally == null && c.flag("prefer_lowest_hp", true)) {
                ally = c.targets().alliesIn(p.getLocation(), range).stream().filter(a -> !a.equals(p))
                        .min(Comparator.comparingDouble(c::hpRatio)).orElse(null);
            }
            double duration = c.p("duration", 8);
            c.services().effects().addShield(p, c.services().stats().maxHp(p) * c.p("self_shield", 0.15), duration, "guardian_oath");
            SkillFx.sound(p.getLocation(), Sound.BLOCK_BEACON_POWER_SELECT, 0.8f, 1.4f);
            SkillFx.helix(p.getLocation(), 0.7, 2.2, 24, Particle.DUST, SkillFx.dust(0x7fb2ff, 1.2f));
            if (ally == null) {
                c.services().hud().actionBar(p, Text.mm("<#7fb2ff>수호의 맹세 <gray>— 연결할 아군이 없어 보호막만 얻었습니다"), 40);
                return true;
            }
            OathLinks.link(ally, p, c.p("redirect", 0.40), duration);
            final Player target = ally;
            Text.send(target, "<#7fb2ff>" + Text.escape(p.getName()) + "</#7fb2ff><gray> 님이 수호의 맹세로 당신을 지킵니다 (" + (int) duration + "초)");
            SkillTask.repeat(0, 4, (int) (duration * 5), step -> {
                if (!OathLinks.active(target, p)) return false;
                SkillFx.line(p.getLocation().add(0, 1.2, 0), target.getLocation().add(0, 1.2, 0), 0.5, Particle.DUST,
                        SkillFx.dust(0x9ecbff, 0.9f));
                return true;
            }, () -> OathLinks.unlink(target, p));
            return true;
        }
    }

    /** 맹세 연결 상태 (ClassPassives 의 피해 훅이 읽는다). */
    public static final class OathLinks {
        private record Link(UUID guardian, double ratio, long until) {}

        private static final Map<UUID, Link> LINKS = new ConcurrentHashMap<>();
        private static final ThreadLocal<Boolean> REDIRECTING = ThreadLocal.withInitial(() -> false);

        private OathLinks() {}

        static void link(Player ally, Player guardian, double ratio, double seconds) {
            LINKS.put(ally.getUniqueId(), new Link(guardian.getUniqueId(), ratio, System.currentTimeMillis() + (long) (seconds * 1000)));
        }

        static void unlink(Player ally, Player guardian) {
            LINKS.computeIfPresent(ally.getUniqueId(), (u, l) -> l.guardian().equals(guardian.getUniqueId()) ? null : l);
        }

        static boolean active(Player ally, Player guardian) {
            Link l = LINKS.get(ally.getUniqueId());
            return l != null && l.guardian().equals(guardian.getUniqueId()) && l.until() > System.currentTimeMillis()
                    && guardian.isOnline() && !guardian.isDead() && ally.isOnline() && !ally.isDead()
                    && guardian.getWorld().equals(ally.getWorld());
        }

        /** 연결된 아군이 받는 피해 중 비율만큼 수호기사에게 넘기고 남은 피해를 돌려준다. */
        public static double redirect(Services services, DamageContext ctx, double damage) {
            if (REDIRECTING.get() || !(ctx.target() instanceof Player ally)) return damage;
            Link l = LINKS.get(ally.getUniqueId());
            if (l == null) return damage;
            Player g = Bukkit.getPlayer(l.guardian());
            if (g == null || !active(ally, g) || g.getLocation().distanceSquared(ally.getLocation()) > 40 * 40) return damage;
            double portion = damage * l.ratio();
            if (portion <= 0) return damage;
            REDIRECTING.set(true);
            try {
                services.damage().deal(DamageContext.raw(ctx.attacker(), g, portion, DamageType.TRUE).source("guardian_oath")
                        .noCrit().noEvade().noBlock().noLifesteal());
            } finally {
                REDIRECTING.set(false);
            }
            SkillFx.line(ally.getLocation().add(0, 1.2, 0), g.getLocation().add(0, 1.2, 0), 0.4, Particle.DUST, SkillFx.dust(0xffd27a, 1.0f));
            return damage - portion;
        }

        public static void clear() { LINKS.clear(); }
    }

    /** 성채 깃발 + 방벽: 안의 아군 피해 감소·넉백 면역, 들어온 적 둔화. */
    static final class BulwarkCitadel implements Skill {
        public String id() { return "bulwark_citadel"; }

        public boolean cast(SkillContext c) {
            Player p = c.caster();
            Location center = Targeting.dropToGround(p.getLocation(), 4);
            double radius = c.p("radius", 6);
            double duration = c.p("duration", 6);
            int life = (int) (duration * 20);
            ItemDisplay banner = SkillFx.spawn(c.fx("fx_banner", "citadel_banner"), center.clone().add(0, 1.25, 0), 1f, life);
            ItemDisplay dome = SkillFx.spawn(c.fx("fx_dome", "citadel_dome"), center.clone().add(0, 0.6, 0),
                    (float) (radius * 2 / SkillFx.modelWidth(c.fx("fx_dome", "citadel_dome"))), life);
            if (dome != null) SkillFx.scaleTo(dome, (float) (radius * 2 / SkillFx.modelWidth(c.fx("fx_dome", "citadel_dome"))), 1);
            SkillFx.spin(banner, 0f, life);
            SkillFx.sound(center, Sound.BLOCK_ANVIL_PLACE, 0.8f, 0.7f);
            SkillFx.sound(center, Sound.BLOCK_BEACON_ACTIVATE, 1f, 1.2f);
            SkillFx.burst(center.clone().add(0, 0.2, 0), Particle.CLOUD, 30, radius * 0.4, 0.02, null);
            Map<String, Double> buff = c.flag("knockback_immune", true)
                    ? Map.of("damage_reduction", c.p("damage_reduction", 0.40), "knockback_immune", 1.0)
                    : Map.of("damage_reduction", c.p("damage_reduction", 0.40));
            double slow = c.p("enemy_slow", 0.30);
            SkillTask.repeat(0, 5, life / 5 + 1, step -> {
                if (!p.isOnline()) return false;
                for (Player a : c.targets().alliesIn(center, radius)) c.services().effects().applyBuff(a, buff, 0.6, "bulwark_citadel");
                for (LivingEntity e : c.targets().enemiesIn(center, radius)) c.services().effects().apply(e, "slow", 0.6, slow, p);
                if (step % 2 == 0) SkillFx.circle(center.clone().add(0, 0.15, 0), radius, 40, Particle.DUST, SkillFx.dust(0x7fb2ff, 1.3f));
                return true;
            }, null);
            return true;
        }
    }
}
