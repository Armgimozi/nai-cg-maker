package kr.labyrinth.items.weaponskills;

import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Vector;

/** 이동형 무기 스킬: dash_strike(돌진 베기) · leap_slam(도약 내려찍기) · shadow_step(그림자 이동). GDD §17.2. */
final class MovementSkills {

    private MovementSkills() {}

    static void register(Map<String, WeaponSkill> r) {
        r.put("dash_strike", MovementSkills::dashStrike);
        r.put("leap_slam", MovementSkills::leapSlam);
        r.put("shadow_step", MovementSkills::shadowStep);
    }

    /** 바라보는 방향으로 돌진, 경로 폭 안의 적을 한 번씩 벰. 끝에서 추가 휘두르기(end_radius·end_damage). */
    static void dashStrike(SkillCast c) {
        double distance = c.num("distance", 8);
        double width = c.num("width", 2.0);
        boolean invuln = c.flag("invulnerable", false);
        double endRadius = c.num("end_radius", 0);
        double endDamage = c.num("end_damage", 0);
        int ticks = 6;
        double perTick = distance / ticks;
        Vector dir = c.flatLook();
        if (invuln) c.service.invulnerable(c.player, ticks + 6);
        c.service.noFall(c.player, 40);
        Set<UUID> hit = new HashSet<>();
        Location[] last = {c.player.getLocation()};
        Color col = c.color();
        String fx = c.fx(null);
        c.sound(Sound.ENTITY_BREEZE_JUMP, 0.8f, 1.2f);
        c.repeat(1, ticks, t -> {
            c.player.setVelocity(dir.clone().multiply(perTick).setY(onGround(c.player) ? 0.0 : -0.1));
            Location now = c.player.getLocation();
            strikeAlong(c, last[0], now, width, hit, c.damage());
            last[0] = now;
            Fx.dust(now.clone().add(0, 1, 0), col, 1.5f, 6, 0.3);
            now.getWorld().spawnParticle(Particle.CLOUD, now.clone().add(0, 0.2, 0), 3, 0.2, 0.05, 0.2, 0.01);
            return true;
        }, () -> c.later(1, () -> {
            if (!c.player.isOnline() || c.player.isDead()) return;
            Location now = c.player.getLocation();
            strikeAlong(c, last[0], now, width, hit, c.damage());
            c.player.setVelocity(dir.clone().multiply(0.2));
            if (endRadius > 0 && endDamage > 0) {
                for (LivingEntity e : c.enemies(now, endRadius)) c.hit(e, endDamage, 0.4);
                c.soundAt(now, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 1f, 0.8f);
                now.getWorld().spawnParticle(Particle.SWEEP_ATTACK, now.clone().add(0, 1, 0), 6, endRadius / 2, 0.3, endRadius / 2);
            }
            if (fx != null) {
                Location l = now.clone().add(0, 1, 0);
                l.setDirection(dir);
                Fx.spawn(c.services, l, fx, (float) Math.max(1, width / 2), 8);
            }
        }));
    }

    private static void strikeAlong(SkillCast c, Location from, Location to, double width, Set<UUID> hit, double mult) {
        Location a = from.clone().add(0, 1, 0);
        Location b = to.clone().add(0, 1, 0);
        for (LivingEntity e : c.targets().enemiesInLine(c.player, a, b, width)) {
            if (hit.add(e.getUniqueId())) {
                c.hit(e, mult);
                e.getWorld().spawnParticle(Particle.SWEEP_ATTACK, e.getLocation().add(0, e.getHeight() / 2, 0), 1);
            }
        }
    }

    /** 바라보는 지점(최대 range)으로 포물선 도약 → 착지 원형 피해·기절·띄우기·넉백. */
    static void leapSlam(SkillCast c) {
        double range = c.num("range", 10);
        double radius = c.num("radius", 4);
        double stun = c.num("stun", 0);
        double bossStun = c.num("boss_stun", 0);
        double launch = c.num("launch", 0);
        double bossLaunch = c.num("boss_launch", 0);
        double kb = c.num("knockback", 0);
        Location from = c.player.getLocation();
        Location target = c.targetPoint(range);
        double dist = Math.hypot(target.getX() - from.getX(), target.getZ() - from.getZ());
        int flight = (int) Math.max(8, Math.min(22, 8 + dist * 0.9));
        double height = 1.6 + dist * 0.18;
        c.service.noFall(c.player, flight + 60);
        Color col = c.color();
        c.sound(Sound.ENTITY_RAVAGER_ROAR, 0.5f, 1.6f);
        String fx = c.fx(null);
        // 착지 지점 아군 표시 (짧게)
        if (fx != null) Fx.spawnFor(c.services, target.clone().add(0, 0.05, 0), fx, (float) (radius / 2.0), flight,
                c.allies(target, 64));
        c.repeat(1, flight, t -> {
            double s = (double) t / flight;
            double s2 = Math.min(1.0, (double) (t + 1) / flight);
            Location want = lerpArc(from, target, s2, height);
            Location cur = c.player.getLocation();
            Vector v = want.toVector().subtract(cur.toVector());
            if (v.length() > 3) v.normalize().multiply(3);
            c.player.setVelocity(v);
            Fx.dust(cur.clone().add(0, 0.5, 0), col, 1.3f, 3, 0.25);
            return s < 1.0 && !(t > 4 && onGround(c.player) && cur.distanceSquared(target) < 2.5);
        }, () -> {
            if (!c.player.isOnline() || c.player.isDead()) return;
            Location land = c.player.getLocation();
            c.player.setVelocity(new Vector(0, -0.2, 0));
            c.player.setFallDistance(0);
            for (LivingEntity e : c.enemies(land, radius)) {
                if (c.hit(e, c.damage(), kb) == null) continue;
                boolean boss = c.isBoss(e);
                c.stun(e, boss ? bossStun : stun);
                c.launch(e, launch, bossLaunch);
            }
            land.getWorld().spawnParticle(Particle.EXPLOSION, land, 2, 0.5, 0.1, 0.5);
            var under = land.clone().subtract(0, 0.5, 0).getBlock();
            if (under.getType().isSolid()) {
                land.getWorld().spawnParticle(Particle.BLOCK, land, 40, radius / 2, 0.1, radius / 2, 0.1, under.getBlockData());
            }
            Fx.dust(land.clone().add(0, 0.3, 0), col, 1.8f, 30, radius / 2);
            c.soundAt(land, Sound.ENTITY_GENERIC_EXPLODE, 0.8f, 0.9f);
            c.soundAt(land, Sound.BLOCK_ANVIL_LAND, 0.5f, 0.7f);
            if (fx != null) Fx.spawn(c.services, land.clone().add(0, 0.1, 0), fx, (float) (radius / 2.0), 12);
        });
    }

    static Location lerpArc(Location a, Location b, double s, double height) {
        double x = a.getX() + (b.getX() - a.getX()) * s;
        double z = a.getZ() + (b.getZ() - a.getZ()) * s;
        double y = a.getY() + (b.getY() - a.getY()) * s + 4 * height * s * (1 - s);
        return new Location(a.getWorld(), x, y, z);
    }

    /** 바라보는 적의 등 뒤로 순간이동해 일격. 대상이 없으면 fallback_distance 만큼 전방 순간이동. */
    static void shadowStep(SkillCast c) {
        double range = c.num("range", 10);
        double backBonus = c.num("back_bonus", 1.5);
        boolean guaranteedCrit = c.flag("guaranteed_crit", false);
        double stealth = c.num("stealth", 0);
        double fallback = c.num("fallback_distance", 6);
        LivingEntity target = c.targets().firstInSight(c.player, range, 1.0);
        Location origin = c.player.getLocation();
        origin.getWorld().spawnParticle(Particle.LARGE_SMOKE, origin.clone().add(0, 1, 0), 20, 0.3, 0.6, 0.3, 0.02);
        Color col = c.color();
        if (target != null) {
            Location tl = target.getLocation();
            Vector back = tl.getDirection().setY(0);
            if (back.lengthSquared() < 1e-6) back = tl.toVector().subtract(origin.toVector()).setY(0);
            back.normalize();
            double off = target.getWidth() / 2 + 0.8;
            Location dest = tl.clone().subtract(back.clone().multiply(off));
            if (!SkillCast.standable(dest)) dest = tl.clone().add(back.clone().rotateAroundY(Math.PI / 2).multiply(off));
            if (!SkillCast.standable(dest)) dest = tl.clone().subtract(tl.toVector().subtract(origin.toVector()).setY(0).normalize().multiply(off));
            dest.setDirection(tl.toVector().subtract(dest.toVector()).setY(0.0));
            c.player.teleport(dest);
            c.player.setFallDistance(0);
            double mult = c.damage() * backBonus;
            if (guaranteedCrit) mult *= Math.max(1.0, c.services.stats().get(c.player).critDamage());
            var ctx = kr.labyrinth.combat.DamageContext.attack(c.player, target, mult, c.type()).skill(c.skill.id());
            if (guaranteedCrit) ctx.noCrit();
            if (c.targets().isEnemy(c.player, target)) {
                c.services.damage().deal(ctx);
                if (!ctx.cancelled() && !ctx.evaded()) c.afterHit(target);
            }
            Location hitAt = target.getLocation().add(0, target.getHeight() / 2, 0);
            hitAt.getWorld().spawnParticle(Particle.SWEEP_ATTACK, hitAt, 2, 0.2, 0.2, 0.2);
            if (guaranteedCrit) hitAt.getWorld().spawnParticle(Particle.CRIT, hitAt, 25, 0.3, 0.4, 0.3, 0.3);
            String fx = c.fx(null);
            if (fx != null) {
                Location l = hitAt.clone();
                l.setDirection(c.player.getLocation().getDirection());
                Fx.spawn(c.services, l, fx, 1.2f, 8);
            }
        } else {
            Vector dir = c.flatLook();
            Location dest = origin.clone();
            for (double d = 0.5; d <= fallback; d += 0.5) {
                Location next = origin.clone().add(dir.clone().multiply(d));
                if (!SkillCast.standable(next)) break;
                dest = next;
            }
            dest.setYaw(origin.getYaw());
            dest.setPitch(origin.getPitch());
            c.player.teleport(dest);
            c.player.setFallDistance(0);
        }
        Location now = c.player.getLocation();
        Fx.dust(now.clone().add(0, 1, 0), col, 1.4f, 16, 0.4);
        c.soundAt(now, Sound.ENTITY_ENDERMAN_TELEPORT, 0.6f, 1.4f);
        if (stealth > 0) {
            c.player.addPotionEffect(new PotionEffect(PotionEffectType.INVISIBILITY, SkillCast.ticks(stealth), 0, false, false, true));
        }
    }

    /** 사용하지 않는 디스플레이 정리 헬퍼 (안전). */
    static void remove(ItemDisplay d) { if (d != null && d.isValid()) d.remove(); }

    /** 서버 기준 착지 판정 (발밑 블록이 막혀 있음). Player#isOnGround 는 클라이언트 값이라 쓰지 않는다. */
    static boolean onGround(org.bukkit.entity.Player p) {
        return !p.getLocation().subtract(0, 0.08, 0).getBlock().isPassable();
    }
}
