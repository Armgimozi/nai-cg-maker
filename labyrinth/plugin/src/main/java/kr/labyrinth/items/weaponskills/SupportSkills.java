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
import org.bukkit.entity.Player;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

/** 강화·지원·광선형 무기 스킬: empower · sanctuary · mend · riposte · beam · chain_bolt. GDD §17.2. */
final class SupportSkills {

    private SupportSkills() {}

    static void register(Map<String, WeaponSkill> r) {
        r.put("empower", SupportSkills::empower);
        r.put("sanctuary", SupportSkills::sanctuary);
        r.put("mend", SupportSkills::mend);
        r.put("riposte", SupportSkills::riposte);
        r.put("beam", SupportSkills::beam);
        r.put("chain_bolt", SupportSkills::chainBolt);
    }

    /** 자기 강화 — buff 맵을 duration 동안, hp_cost = 현재 HP 비율 소모(죽지 않음). */
    static void empower(SkillCast c) {
        double duration = c.num("duration", 8);
        double hpCost = c.num("hp_cost", 0);
        if (hpCost > 0) {
            double cur = c.services.stats().currentHp(c.player);
            c.services.stats().setHp(c.player, Math.max(1, cur * (1 - hpCost)));
            c.player.getWorld().spawnParticle(Particle.DAMAGE_INDICATOR, c.player.getLocation().add(0, 1, 0), 6, 0.3, 0.4, 0.3, 0.1);
        }
        Map<String, Double> buff = c.buffMap("buff");
        if (!buff.isEmpty()) c.services.effects().applyBuff(c.player, buff, duration, c.sourceId());
        Color col = c.color();
        String fx = c.fx(null);
        if (fx != null) Fx.spawn(c.services, c.player.getLocation().add(0, 0.1, 0), fx, 1.2f, 12);
        c.sound(Sound.ENTITY_EVOKER_PREPARE_ATTACK, 0.7f, 1.4f);
        c.sound(Sound.BLOCK_BEACON_ACTIVATE, 0.5f, 1.8f);
        c.repeat(5, Math.max(5, SkillCast.ticks(duration)), t -> {
            Location at = c.player.getLocation();
            double a = t * 0.4;
            Fx.dust(at.clone().add(Math.cos(a) * 0.6, 0.2 + (t % 40) / 20.0, Math.sin(a) * 0.6), col, 1.0f, 2, 0.05);
            return true;
        }, null);
        c.service.bar(c.player, "<#ffd27a>◆ " + c.skill.name() + " <gray>— " + Math.round(duration) + "초 강화", 40);
    }

    /** 바닥 장: tick 마다 아군 회복·적 피해/둔화, 시작 시 보호막·정화, 안의 아군에게 ally_buff. */
    static void sanctuary(SkillCast c) {
        double range = c.num("range", 0);
        double radius = c.num("radius", 6);
        double duration = c.num("duration", 6);
        int tick = SkillCast.ticks(c.num("tick", 1.0));
        double heal = c.num("heal", 0);
        double scale = c.num("heal_power_scale", 0.3);
        double shield = c.num("shield", 0);
        double enemySlow = c.num("enemy_slow", 0);
        boolean cleanse = c.flag("cleanse", false);
        Map<String, Double> allyBuff = c.buffMap("ally_buff");
        Location center = range > 0 ? c.targetPoint(range) : c.player.getLocation();
        String fx = c.fx(null);
        Color col = c.color();
        ItemDisplay ground = fx != null ? Fx.spawn(c.services, center.clone().add(0, 0.06, 0), fx, (float) (radius / 2.0), 0) : null;
        for (Player ally : c.allies(center, radius)) {
            if (shield > 0) c.service.shield(ally, c.services.stats().maxHp(ally) * shield, duration);
            if (cleanse) c.services.effects().cleanse(ally);
        }
        c.sound(Sound.BLOCK_BEACON_ACTIVATE, 0.8f, 1.3f);
        String buffId = c.sourceId() + ":" + c.player.getUniqueId();
        c.repeat(1, SkillCast.ticks(duration), t -> {
            if (ground != null && ground.isValid()) {
                Fx.transform(ground, (float) Math.toRadians(t * 1.5), (float) (radius / 2.0), (float) (radius / 2.0),
                        (float) (radius / 2.0), 1);
            }
            if (t % 5 == 0) {
                c.ring(center, radius, 32);
                center.getWorld().spawnParticle(Particle.END_ROD, center.clone().add(0, 0.3, 0), 3, radius / 2, 0.1, radius / 2, 0.01);
            }
            if (t % tick == 0) {
                for (Player ally : c.allies(center, radius)) {
                    if (heal > 0) c.heal(ally, heal, scale);
                    if (!allyBuff.isEmpty()) c.services.effects().applyBuff(ally, allyBuff, tick / 20.0 + 0.6, buffId);
                    ally.getWorld().spawnParticle(Particle.HAPPY_VILLAGER, ally.getLocation().add(0, 1.2, 0), 3, 0.3, 0.4, 0.3);
                }
                for (LivingEntity e : c.enemies(center, radius)) {
                    if (c.damage() > 0 && c.p.has("damage")) c.hit(e, c.damage() * tick / 20.0);
                    if (enemySlow > 0) c.services.effects().apply(e, "slow", tick / 20.0 + 0.5, enemySlow, c.player);
                }
            }
            return true;
        }, () -> { if (ground != null) ground.remove(); });
    }

    /** 즉발 광역 치유 — 주위 아군 회복(+치유력 × scale)·보호막·정화. */
    static void mend(SkillCast c) {
        double radius = c.num("radius", 8);
        double heal = c.num("heal", 0.1);
        double scale = c.num("heal_power_scale", 0.5);
        double shield = c.num("shield", 0);
        boolean cleanse = c.flag("cleanse", false);
        Location at = c.player.getLocation();
        int n = 0;
        for (Player ally : c.allies(at, radius)) {
            c.heal(ally, heal, scale);
            if (shield > 0) c.service.shield(ally, c.services.stats().maxHp(ally) * shield, 8);
            if (cleanse) c.services.effects().cleanse(ally);
            ally.getWorld().spawnParticle(Particle.HEART, ally.getLocation().add(0, 2.1, 0), 2, 0.3, 0.1, 0.3);
            n++;
        }
        String fx = c.fx(null);
        if (fx != null) Fx.spawn(c.services, at.clone().add(0, 0.1, 0), fx, (float) (radius / 2.0), 14);
        Color col = c.color();
        for (int i = 0; i < 40; i++) {
            double a = Math.PI * 2 * i / 40;
            Fx.dust(at.clone().add(Math.cos(a) * radius * 0.7, 0.4, Math.sin(a) * radius * 0.7), col, 1.4f, 1, 0.05);
        }
        at.getWorld().spawnParticle(Particle.END_ROD, at.clone().add(0, 1, 0), 30, radius / 3, 0.6, radius / 3, 0.05);
        c.sound(Sound.BLOCK_AMETHYST_BLOCK_RESONATE, 1f, 1.6f);
        c.sound(Sound.ENTITY_PLAYER_LEVELUP, 0.4f, 1.9f);
        c.service.bar(c.player, "<#9be89b>✚ " + c.skill.name() + " <gray>— 아군 " + n + "명 회복", 30);
    }

    /** 방어 자세 duration — 정면 angle 안의 피해를 reduction 만큼 줄이고 reflect 비율 반사. 끝나면 반격. */
    static void riposte(SkillCast c) {
        double duration = c.num("duration", 2.5);
        double reduction = c.num("reduction", 0.5);
        double angle = c.num("angle", 120);
        double counterRadius = c.num("counter_radius", 4);
        double counterDamage = c.num("counter_damage", 1.5);
        double perBlock = c.num("per_block", 0.2);
        double reflect = c.num("reflect", 0);
        double taunt = c.num("taunt", 0);
        c.service.riposte(c.player, duration, reduction, angle, reflect);
        if (taunt > 0) for (LivingEntity e : c.enemies(c.player.getLocation(), counterRadius * 2)) c.taunt(e, taunt);
        String fx = c.fx(null);
        Color col = c.color();
        ItemDisplay d = fx != null ? Fx.spawn(c.services, c.player.getLocation().add(0, 1, 0), fx, 0.8f, 0) : null;
        c.sound(Sound.ITEM_SHIELD_BLOCK, 1f, 0.7f);
        c.sound(Sound.BLOCK_ANVIL_PLACE, 0.5f, 1.6f);
        c.repeat(1, SkillCast.ticks(duration), t -> {
            Location front = c.player.getLocation().add(0, 1, 0).add(c.flatLook().multiply(0.9));
            if (d != null && d.isValid()) {
                Location l = front.clone();
                l.setDirection(c.flatLook());
                d.teleport(l);
            }
            if (t % 3 == 0) {
                double half = Math.toRadians(angle / 2);
                Vector f = c.flatLook();
                double base = Math.atan2(f.getZ(), f.getX());
                for (int i = 0; i <= 8; i++) {
                    double a = base - half + 2 * half * i / 8;
                    Fx.dust(c.player.getLocation().add(Math.cos(a) * 1.3, 1.0, Math.sin(a) * 1.3), col, 1.0f, 1, 0.02);
                }
            }
            return true;
        }, () -> {
            if (d != null) d.remove();
            int blocks = c.service.endRiposte(c.player);
            if (!c.player.isOnline() || c.player.isDead()) return;
            Location at = c.player.getLocation();
            double mult = counterDamage + blocks * perBlock;
            for (LivingEntity e : c.enemies(at, counterRadius)) c.hit(e, mult, 0.5);
            at.getWorld().spawnParticle(Particle.SWEEP_ATTACK, at.clone().add(0, 1, 0), 8, counterRadius / 2, 0.3, counterRadius / 2);
            Fx.dust(at.clone().add(0, 1, 0), col, 1.8f, 30, counterRadius / 2);
            c.soundAt(at, Sound.ENTITY_PLAYER_ATTACK_STRONG, 1f, 0.8f);
            if (blocks > 0) c.service.bar(c.player, "<#ffd27a>반격! <gray>막은 공격 " + blocks + "회", 30);
        });
    }

    /** 직선 광선. duration 0 = 즉발, > 0 = 채널(tick 마다). 광선에 닿은 아군은 ally_heal 회복. */
    static void beam(SkillCast c) {
        double length = c.num("length", 18);
        double width = c.num("width", 1.5);
        double duration = c.num("duration", 0);
        int tick = SkillCast.ticks(c.num("tick", 0.25));
        double allyHeal = c.num("ally_heal", 0);
        double scale = c.num("heal_power_scale", 0);
        double moveSlow = c.num("move_slow", 0);
        String fx = c.fx(null);
        Color col = c.color();
        double modelLen = fx == null ? 1 : Fx.modelLength(c.services, fx, 2);
        if (duration <= 0) {
            fireBeam(c, length, width, c.damage(), allyHeal, scale, col, fx, modelLen, null, 10);
            c.sound(Sound.ENTITY_GUARDIAN_ATTACK, 0.8f, 1.6f);
            c.sound(Sound.BLOCK_BEACON_DEACTIVATE, 0.6f, 2.0f);
            return;
        }
        int total = SkillCast.ticks(duration);
        if (moveSlow > 0) c.services.effects().applyBuff(c.player, Map.of("move_speed", -moveSlow), duration, c.sourceId());
        ItemDisplay[] d = {fx != null ? Fx.spawn(c.services, c.player.getEyeLocation(), fx, 1f, 0) : null};
        double perTickMult = c.damage();
        c.sound(Sound.BLOCK_BEACON_ACTIVATE, 0.7f, 1.8f);
        c.repeat(1, total, t -> {
            boolean apply = t % tick == 0;
            fireBeam(c, length, width, apply ? perTickMult : 0, apply ? allyHeal : 0, scale, col, fx, modelLen, d[0], 0);
            if (t % 10 == 0) c.player.getWorld().playSound(c.player.getLocation(), Sound.BLOCK_BEACON_AMBIENT, 0.6f, 1.8f);
            return true;
        }, () -> { if (d[0] != null) d[0].remove(); });
    }

    private static void fireBeam(SkillCast c, double length, double width, double dmg, double allyHeal, double scale, Color col,
                                 String fx, double modelLen, ItemDisplay existing, int lifetime) {
        Location eye = c.player.getEyeLocation().subtract(0, 0.3, 0);
        Vector dir = eye.getDirection();
        RayTraceResult block = c.player.getWorld().rayTraceBlocks(eye, dir, length, FluidCollisionMode.NEVER, true);
        double len = block == null ? length : block.getHitPosition().distance(eye.toVector());
        Location end = eye.clone().add(dir.clone().multiply(len));
        if (dmg > 0) for (LivingEntity e : c.targets().enemiesInLine(c.player, eye, end, width)) c.hit(e, dmg);
        if (allyHeal > 0) {
            for (Player ally : c.allies(eye.clone().add(dir.clone().multiply(len / 2)), len / 2 + width)) {
                if (ally.equals(c.player)) continue;
                Vector closest = WeaponTargeting.closestOnSegment(eye.toVector(), end.toVector(), ally.getLocation().add(0, 1, 0).toVector());
                if (closest.distance(ally.getLocation().add(0, 1, 0).toVector()) <= width / 2 + 0.6) c.heal(ally, allyHeal, scale);
            }
        }
        // 연출: 모델을 광선 길이만큼 늘이거나 입자 선
        Location mid = eye.clone().add(dir.clone().multiply(len / 2));
        mid.setDirection(dir);
        ItemDisplay d = existing;
        if (d == null && fx != null && lifetime > 0) d = Fx.spawn(c.services, mid, fx, 1f, lifetime);
        if (d != null && d.isValid()) {
            d.teleport(mid);
            float sz = (float) (len / modelLen);
            float sw = (float) Math.max(0.5, width / 1.5);
            d.setTransformation(new org.bukkit.util.Transformation(new org.joml.Vector3f(), new org.joml.Quaternionf(),
                    new org.joml.Vector3f(sw, sw, sz), new org.joml.Quaternionf()));
        } else {
            Fx.line(eye, end, col, 1.2f, 0.4);
        }
        end.getWorld().spawnParticle(Particle.END_ROD, end, 2, 0.1, 0.1, 0.1, 0.02);
    }

    /** 시선의 첫 적 → 가장 가까운 안 맞은 적으로 bounces 번 튐 (튈 때마다 falloff 감소). */
    static void chainBolt(SkillCast c) {
        double range = c.num("range", 20);
        int bounces = Math.max(0, c.p.integer("bounces", 4));
        double bounceRange = c.num("bounce_range", 6);
        double falloff = c.num("falloff", 0.15);
        LivingEntity first = c.targets().firstInSight(c.player, range, 0.8);
        Color col = c.color();
        String fx = c.fx(null);
        Location eye = c.player.getEyeLocation().subtract(0, 0.3, 0);
        if (first == null) {
            Location end = eye.clone().add(eye.getDirection().multiply(Math.min(range, 8)));
            Fx.line(eye, end, col, 1.0f, 0.4);
            c.sound(Sound.BLOCK_FIRE_EXTINGUISH, 0.4f, 1.8f);
            return;
        }
        Set<UUID> hit = new HashSet<>();
        List<LivingEntity> chain = new ArrayList<>();
        chain.add(first);
        hit.add(first.getUniqueId());
        LivingEntity cur = first;
        for (int i = 0; i < bounces; i++) {
            LivingEntity next = null;
            for (LivingEntity e : c.enemies(cur.getLocation(), bounceRange)) {
                if (!hit.contains(e.getUniqueId())) {
                    next = e;
                    break;
                }
            }
            if (next == null) break;
            hit.add(next.getUniqueId());
            chain.add(next);
            cur = next;
        }
        c.sound(Sound.ENTITY_LIGHTNING_BOLT_THUNDER, 0.3f, 2.0f);
        Location[] prev = {eye};
        int[] idx = {0};
        c.repeat(2, chain.size() * 2, t -> {
            if (idx[0] >= chain.size()) return false;
            LivingEntity e = chain.get(idx[0]);
            Location at = e.getLocation().add(0, e.getHeight() / 2, 0);
            zigzag(prev[0], at, col);
            double mult = c.damage() * Math.pow(Math.max(0, 1 - falloff), idx[0]);
            DamageContext ctx = c.hit(e, mult);
            if (ctx != null) at.getWorld().spawnParticle(Particle.ELECTRIC_SPARK, at, 12, 0.3, 0.4, 0.3, 0.2);
            if (fx != null) Fx.spawn(c.services, at, fx, 0.8f, 6);
            at.getWorld().playSound(at, Sound.BLOCK_AMETHYST_BLOCK_HIT, 0.6f, 1.8f);
            prev[0] = at;
            idx[0]++;
            return idx[0] < chain.size();
        }, null);
    }

    private static void zigzag(Location from, Location to, Color col) {
        Vector d = to.toVector().subtract(from.toVector());
        int segs = (int) Math.max(3, d.length() / 1.2);
        Location last = from.clone();
        java.util.concurrent.ThreadLocalRandom r = java.util.concurrent.ThreadLocalRandom.current();
        for (int i = 1; i <= segs; i++) {
            Location p = from.clone().add(d.clone().multiply((double) i / segs));
            if (i < segs) p.add(r.nextDouble(-0.3, 0.3), r.nextDouble(-0.3, 0.3), r.nextDouble(-0.3, 0.3));
            Fx.line(last, p, col, 0.9f, 0.25);
            last = p;
        }
    }
}
