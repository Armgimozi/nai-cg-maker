package kr.labyrinth.mobs;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Log;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.Vector;

/**
 * 일반 몹 스킬 26종 (GDD §9.1 닫힌 목록) — 전부 여기서 구현. 공통 params: damage(몹 damage 배율), windup(경고, 기본 0.6초),
 * range(발동 거리). 경고는 §8.1 도형(MobFx). 패시브(trail·aura·explode_on_death·split_on_death·enrage·ambush)는
 * cooldown 과 상관없이 훅으로 동작한다.
 * <p>
 * 스킬 대상은 {@link LivingEntity} — 보통은 플레이어, 훈련({@link MobDrill})에서는 허수아비. 대상을 다시 찾을 때는
 * {@code m.targetById}, 광역 판정은 {@code m.victimsNear} 를 쓴다(플레이어 + 허수아비).
 */
final class MobSkills {

    private MobSkills() {}

    static final Set<String> PASSIVE = Set.of("trail", "aura", "explode_on_death", "split_on_death", "enrage", "ambush");

    static final Set<String> ALL = Set.of("leap", "charge", "slam", "cleave", "projectile", "beam", "breath", "shield", "summon",
            "blink", "heal_allies", "buff_allies", "snare", "pull", "debuff", "stealth", "reflect", "life_drain", "trail", "aura",
            "explode_on_death", "split_on_death", "enrage", "ambush", "burrow", "dive");

    // ── 선택·시전 ────────────────────────────────────────────────────────

    /** 쿨다운이 돌아온 스킬 중 조건이 맞는 것을 하나 시전. @return 시전했으면 true */
    static boolean tryCast(LabMob m, Player t, long now) {
        int n = m.skills.size();
        if (n == 0) return false;
        List<Integer> order = new ArrayList<>(n);
        int start = (int) ((now / 4 + (m.seed & 0xF)) % n);
        for (int i = 0; i < n; i++) order.add((start + i) % n);
        String ai = m.def.ai() == null ? "melee" : m.def.ai();
        if (ai.equals("caster")) order.sort(Comparator.comparingInt(i -> casterPriority(m.skills.get(i).type())));
        else if (ai.equals("charger")) order.sort(Comparator.comparingInt(i -> m.skills.get(i).type().equals("charge") ? 0 : 1));
        double dist = MobAi.horizontal(m.entity.getLocation(), t.getLocation());
        for (int i : order) {
            MobDef.MobSkillDef s = m.skills.get(i);
            String type = s.type() == null ? "" : s.type().toLowerCase(Locale.ROOT);
            if (PASSIVE.contains(type)) continue;
            if (now < m.skillReady.getOrDefault(i, 0L)) continue;
            if (!ready(m, type, s.params(), t, dist, now)) continue;
            boolean ok;
            try {
                ok = cast(m, type, s.params(), t, now);
            } catch (Throwable ex) {
                Log.error("몹 스킬 오류 (" + m.def.id() + "/" + type + ")", ex);
                ok = false;
            }
            if (ok) {
                m.skillReady.put(i, now + Math.max(20, Math.round(s.cooldown() * 20)));
                m.globalSkillReady = Math.max(m.globalSkillReady, now + 20);
                m.castTick = now;
                return true;
            }
        }
        return false;
    }

    private static int casterPriority(String type) {
        return switch (type) {
            case "heal_allies" -> 0;
            case "shield" -> 1;
            case "buff_allies" -> 2;
            case "debuff" -> 3;
            default -> 4;
        };
    }

    /** 스폰 직후 쿨다운을 30~70% 로 흩어 모든 몹이 동시에 쓰지 않게. */
    static void initCooldowns(LabMob m, long now) {
        ThreadLocalRandom r = ThreadLocalRandom.current();
        for (int i = 0; i < m.skills.size(); i++) {
            MobDef.MobSkillDef s = m.skills.get(i);
            m.skillReady.put(i, now + Math.round(s.cooldown() * 20 * (0.3 + 0.4 * r.nextDouble())));
            double interval = s.params().dbl("interval", 0);
            if (interval > 0) m.passiveNext.put(i, now + Math.round(interval * 20 * r.nextDouble()));
        }
    }

    private static boolean ready(LabMob m, String type, Params p, LivingEntity t, double dist, long now) {
        double hpRatio = m.hp / m.stats.maxHp();
        boolean see = m.entity.hasLineOfSight(t);
        return switch (type) {
            case "leap" -> dist >= 3 && dist <= p.dbl("range", 8) && see;
            case "charge" -> dist >= 3 && dist <= p.dbl("distance", 8) + 2 && see;
            case "slam" -> {
                double r = p.dbl("radius", 3);
                boolean ring = "ring".equals(p.str("shape"));
                yield ring ? dist <= r + 0.5 && dist >= p.dbl("inner_radius", 1) - 0.5 : dist <= r + 0.3;
            }
            case "cleave" -> p.bool("rear", false) ? anyBehind(m, p) : dist <= p.dbl("length", 4) && see;
            case "projectile" -> dist <= p.dbl("range", 14) && see;
            case "beam" -> dist <= p.dbl("length", 14) && see;
            case "breath" -> dist <= p.dbl("length", 6) && see;
            case "shield" -> hpRatio < 0.9 || (!p.bool("self_only", true) && anyHurt(m, p.dbl("radius", 8), 0.85));
            case "summon" -> aliveSummons(m) < p.integer("max_alive", 4) && m.def.raw() != null;
            case "blink" -> p.bool("behind", false) ? dist <= p.dbl("range", 8) + 4 && dist >= 2.5
                    : (dist < 4 || dist > 7) && dist <= p.dbl("range", 8) * 2;
            case "heal_allies" -> anyHurt(m, p.dbl("radius", 10), 0.75);
            case "buff_allies" -> true;
            case "snare" -> dist <= p.dbl("range", 9);
            case "pull" -> p.dbl("radius", 0) > 0 ? dist <= p.dbl("radius", 8) && dist >= 3 : dist <= p.dbl("range", 10) && dist >= 4 && see;
            case "debuff" -> dist <= p.dbl("range", 10) && (see || dist < 4);
            case "stealth" -> now >= m.stealthUntil;
            case "reflect" -> hpRatio < 0.95;
            case "life_drain" -> dist <= p.dbl("range", 7) && see;
            case "burrow" -> !m.flying && !m.burrowed && m.entity.isOnGround() && dist >= p.dbl("min_range", 4) && dist <= p.dbl("range", 14);
            case "dive" -> m.flying && dist >= 2.5 && dist <= p.dbl("range", 16) && see;
            default -> false;
        };
    }

    private static boolean cast(LabMob m, String type, Params p, LivingEntity t, long now) {
        return switch (type) {
            case "leap" -> leap(m, p, t, now);
            case "charge" -> charge(m, p, t, now);
            case "slam" -> slam(m, p, now);
            case "cleave" -> cleave(m, p, t, now);
            case "projectile" -> projectile(m, p, t, now);
            case "beam" -> beam(m, p, t, now);
            case "breath" -> breath(m, p, t, now);
            case "shield" -> shield(m, p, now);
            case "summon" -> summon(m, p, now);
            case "blink" -> blink(m, p, t, now);
            case "heal_allies" -> healAllies(m, p);
            case "buff_allies" -> buffAllies(m, p, now);
            case "snare" -> snare(m, p, t, now);
            case "pull" -> pull(m, p, t, now);
            case "debuff" -> debuff(m, p, t, now);
            case "stealth" -> stealth(m, p, now);
            case "reflect" -> reflect(m, p, now);
            case "life_drain" -> lifeDrain(m, p, t, now);
            case "burrow" -> burrow(m, p, t, now);
            case "dive" -> dive(m, p, t, now);
            default -> false;
        };
    }

    // ── 공용 ─────────────────────────────────────────────────────────────

    static void hit(LabMob m, LivingEntity target, double amount, DamageType type, String skill, double knockback) {
        if (amount <= 0) return;
        if (target != null && target == m.drillDummy) m.drillHits++;
        DamageContext c = DamageContext.raw(m.entity.isValid() ? m.entity : null, target, amount, type).source(skill);
        if (knockback > 0) c.knockback(knockback);
        m.services.damage().deal(c);
    }

    /** 상태이상 부여 (knockback·damage 는 직접, 나머지는 StatusEffectService). */
    static void effect(LabMob m, LivingEntity p, String effect, double duration, double amount, Location from) {
        if (effect == null || effect.isBlank() || p == null) return;
        String e = effect.toLowerCase(Locale.ROOT);
        switch (e) {
            case "knockback" -> push(p, from, amount <= 0 ? 0.8 : amount);
            case "damage" -> hit(m, p, m.damage() * (amount <= 0 ? 0.25 : amount), DamageType.TRUE, "aura", 0);
            default -> {
                double a = amount > 0 ? amount : switch (e) {
                    case "slow" -> 0.3;
                    case "weaken" -> 0.2;
                    case "vulnerable" -> 0.15;
                    default -> 1.0;
                };
                m.services.effects().apply(p, e, Math.max(0.5, duration), a, m.entity.isValid() ? m.entity : null);
            }
        }
    }

    static void push(LivingEntity e, Location from, double strength) {
        Vector d = e.getLocation().toVector().subtract(from.toVector()).setY(0);
        if (d.lengthSquared() < 1e-4) d = new Vector(ThreadLocalRandom.current().nextDouble() - 0.5, 0, ThreadLocalRandom.current().nextDouble() - 0.5);
        d.normalize().multiply(0.6 * strength).setY(Math.min(0.6, 0.25 + 0.12 * strength));
        e.setVelocity(e.getVelocity().add(d));
    }

    private static void standStill(LabMob m, long untilTick) {
        MobAi.stop(m);
        m.busyUntil = Math.max(m.busyUntil, untilTick);
        if (m.flying) m.entity.setVelocity(new Vector());
    }

    /** 몸이 보는 수평 방향 (정규화). */
    private static Vector facing(LabMob m) {
        return new Vector(Geometry.yawX(m.bodyYaw), 0, Geometry.yawZ(m.bodyYaw));
    }

    /** 몸 뒤쪽 부채꼴(cleave rear) 안에 적이 있는가. */
    private static boolean anyBehind(LabMob m, Params p) {
        double length = p.dbl("length", 4);
        Location o = m.entity.getLocation();
        MobFx.Shape behind = MobFx.Shape.cone(o, facing(m).multiply(-1), p.dbl("angle", 90), length);
        for (LivingEntity e : m.victimsNear(o, length + 0.5)) if (behind.contains(e.getLocation())) return true;
        return false;
    }

    private static boolean anyHurt(LabMob m, double radius, double below) {
        for (LabMob a : m.alliesNear(radius)) if (a.hp / a.stats.maxHp() < below) return true;
        return false;
    }

    private static int aliveSummons(LabMob m) {
        m.summons.removeIf(u -> m.service.byUuid(u).map(x -> !x.isAlive()).orElse(true));
        return m.summons.size();
    }

    private static Location ground(Location l) {
        Location g = l.clone();
        for (int i = 0; i < 4 && g.getBlockY() > g.getWorld().getMinHeight(); i++) {
            if (g.clone().subtract(0, 0.1, 0).getBlock().isPassable()) g.subtract(0, 1, 0);
            else break;
        }
        return g;
    }

    private static void play(Location at, String sound, float vol, float pitch) {
        try {
            at.getWorld().playSound(at, sound, vol, pitch);
        } catch (Throwable ignored) {
            // 잘못된 키 무시
        }
    }

    // ── 스킬 구현 ────────────────────────────────────────────────────────

    private static boolean leap(LabMob m, Params p, LivingEntity t, long now) {
        double radius = p.dbl("radius", 0);
        Location land = ground(t.getLocation());
        int w = m.windupTicks(p, 0.6);
        standStill(m, now + w + 34);
        MobFx.Shape shape = MobFx.Shape.circle(land, radius > 0 ? radius : 1.3);
        m.track(m.service.fx().telegraph(shape, w, MobFx.RED, null, () -> {
            if (!m.isAlive()) return;
            Location from = m.entity.getLocation();
            Vector d = land.toVector().subtract(from.toVector()).setY(0);
            double dist = d.length();
            double power = p.dbl("power", 0.9);
            Vector vel = dist < 0.1 ? new Vector() : d.normalize().multiply(Math.min(2.4, dist * 0.119));
            vel.setY(0.5 + 0.12 * power + Math.max(0, land.getY() - from.getY()) * 0.06);
            m.entity.setVelocity(vel);
            m.attackTick = m.service.now();
            play(from, "minecraft:entity.goat.long_jump", 0.8f, 1.1f);
            new BukkitRunnable() {
                int ticks = 0;
                @Override
                public void run() {
                    ticks++;
                    if (!m.isAlive()) {
                        cancel();
                        return;
                    }
                    if ((ticks > 4 && m.entity.isOnGround()) || ticks > 30) {
                        cancel();
                        Location at = m.entity.getLocation();
                        MobFx.particle(Particle.CLOUD, at.clone().add(0, 0.2, 0), 14, 0.6, 0.1, 0.6, 0.02);
                        play(at, "minecraft:entity.generic.big_fall", 0.9f, 0.8f);
                        double dmg = m.skillDamage(p, "damage", 1.2);
                        if (radius > 0) {
                            MobFx.Shape impact = MobFx.Shape.circle(at, radius);
                            for (LivingEntity e : m.victimsNear(at, radius + 1)) if (impact.contains(e.getLocation())) hit(m, e, dmg, DamageType.MELEE, "leap", 0.6);
                        } else if (t.isValid() && t.getLocation().distanceSquared(at) <= 2.2 * 2.2 && m.validTarget(t)) {
                            hit(m, t, dmg, DamageType.MELEE, "leap", 0.4);
                        }
                        m.busyUntil = m.service.now() + 6;
                    }
                }
            }.runTaskTimer(m.services.plugin(), 1L, 1L);
        }));
        return true;
    }

    private static boolean charge(LabMob m, Params p, LivingEntity t, long now) {
        double speed = Math.max(0.3, p.dbl("speed", 0.9));
        double distance = p.dbl("distance", 8);
        double width = p.dbl("width", 1.5);
        Location origin = m.entity.getLocation();
        Vector dir = m.dirTo(t.getLocation());
        int w = m.windupTicks(p, 0.9);
        int travelTicks = (int) Math.ceil(distance / speed) + 2;
        standStill(m, now + w + travelTicks + 25);
        m.bodyYaw = Geometry.yawOf(dir.getX(), dir.getZ());
        m.track(m.service.fx().telegraph(MobFx.Shape.arrow(origin, dir, distance, width), w, MobFx.PURPLE, null, () -> {
            if (!m.isAlive()) return;
            play(m.entity.getLocation(), "minecraft:entity.ravager.roar", 0.6f, 1.4f);
            Set<UUID> struck = new HashSet<>();
            double dmg = m.skillDamage(p, "damage", 1.4);
            double stun = p.dbl("stun", 0);
            new BukkitRunnable() {
                int ticks = 0;
                double traveled = 0;
                Location prev = m.entity.getLocation();
                @Override
                public void run() {
                    if (!m.isAlive()) {
                        cancel();
                        return;
                    }
                    ticks++;
                    Location now2 = m.entity.getLocation();
                    double step = MobAi.horizontal(prev, now2);
                    traveled += step;
                    prev = now2;
                    boolean blocked = ticks > 3 && step < speed * 0.25;
                    if (traveled >= distance || ticks > travelTicks + 4 || blocked) {
                        cancel();
                        m.entity.setVelocity(new Vector(0, m.entity.getVelocity().getY(), 0));
                        long tnow = m.service.now();
                        if (blocked) {
                            MobFx.particle(Particle.CRIT, now2.clone().add(0, 1, 0), 16, 0.4, 0.4, 0.4, 0.2);
                            play(now2, "minecraft:entity.zombie.attack_wooden_door", 0.8f, 0.7f);
                            m.staggerUntil = tnow + 30;
                        } else if ("charger".equals(m.def.ai())) {
                            m.staggerUntil = tnow + 20; // 돌진 후 1초 경직 (GDD §9.3)
                        }
                        m.busyUntil = tnow + 2;
                        return;
                    }
                    m.entity.setVelocity(dir.clone().multiply(speed).setY(Math.min(0, m.entity.getVelocity().getY())));
                    MobFx.particle(Particle.CLOUD, now2.clone().add(0, 0.2, 0), 2, 0.2, 0.05, 0.2, 0.01);
                    for (LivingEntity e : m.victimsNear(now2, width / 2 + 1.2)) {
                        if (struck.add(e.getUniqueId())) {
                            m.attackTick = m.service.now();
                            hit(m, e, dmg, DamageType.MELEE, "charge", 1.2);
                            if (stun > 0) effect(m, e, "stun", stun, 1, now2);
                        }
                    }
                }
            }.runTaskTimer(m.services.plugin(), 0L, 1L);
        }));
        return true;
    }

    private static boolean slam(LabMob m, Params p, long now) {
        double r = p.dbl("radius", 3);
        boolean ring = "ring".equals(p.str("shape"));
        double inner = p.dbl("inner_radius", Math.max(0.5, r * 0.4));
        Location c = ground(m.entity.getLocation());
        double kb = p.dbl("knockback", 0);
        int w = m.windupTicks(p, 0.8);
        standStill(m, now + w + 8);
        MobFx.Shape shape = ring ? MobFx.Shape.ring(c, inner, r) : MobFx.Shape.circle(c, r);
        m.castTick = now;
        m.track(m.service.fx().telegraph(shape, w, kb > 0 ? MobFx.ORANGE : MobFx.RED, null, () -> {
            if (!m.isAlive()) return;
            m.attackTick = m.service.now();
            m.attackArm = 2;
            double dmg = m.skillDamage(p, "damage", 1.3);
            MobFx.ring(c, ring ? (inner + r) / 2 : r * 0.7, Particle.CLOUD, 20);
            MobFx.particle(Particle.EXPLOSION, c.clone().add(0, 0.3, 0), 1, 0, 0, 0, 0);
            play(c, "minecraft:entity.iron_golem.attack", 1f, 0.6f);
            for (LivingEntity e : m.victimsNear(c, r + 1)) {
                if (!shape.contains(e.getLocation())) continue;
                hit(m, e, dmg, DamageType.MELEE, "slam", kb > 0 ? kb * 2.2 : 0);
                if (p.dbl("stun", 0) > 0) effect(m, e, "stun", p.dbl("stun", 0), 1, c);
                if (p.has("effect")) effect(m, e, p.str("effect"), p.dbl("effect_duration", 3), p.dbl("amount", 0), c);
            }
        }));
        return true;
    }

    private static boolean cleave(LabMob m, Params p, LivingEntity t, long now) {
        double angle = p.dbl("angle", 90);
        double length = p.dbl("length", 4);
        boolean rear = p.bool("rear", false);
        Location o = ground(m.entity.getLocation());
        // rear = 꼬리 휩쓸기: 대상이 아니라 몸 뒤쪽 부채꼴 (뒤에 붙은 사람을 쳐냄)
        Vector dir = rear ? facing(m).multiply(-1) : m.dirTo(t.getLocation());
        int w = m.windupTicks(p, 0.6);
        standStill(m, now + w + 6);
        if (!rear) m.bodyYaw = Geometry.yawOf(dir.getX(), dir.getZ());
        MobFx.Shape shape = MobFx.Shape.cone(o, dir, angle, length);
        double kb = p.dbl("knockback", rear ? 0.8 : 0.3);
        m.track(m.service.fx().telegraph(shape, w, MobFx.RED, null, () -> {
            if (!m.isAlive()) return;
            m.attackTick = m.service.now();
            m.attackArm = rear ? RigMath.ATTACK_TAIL : 0;
            double dmg = m.skillDamage(p, "damage", 1.3);
            double base = Math.atan2(dir.getZ(), dir.getX());
            for (int i = -2; i <= 2; i++) {
                double a = base + Math.toRadians(angle / 2) * i / 2.0;
                MobFx.particle(Particle.SWEEP_ATTACK, o.clone().add(Math.cos(a) * length * 0.6, 1.0, Math.sin(a) * length * 0.6), 1, 0, 0, 0, 0);
            }
            play(o, "minecraft:entity.player.attack.sweep", 1f, rear ? 0.5f : 0.7f);
            for (LivingEntity e : m.victimsNear(o, length + 1)) if (shape.contains(e.getLocation())) hit(m, e, dmg, DamageType.MELEE, "cleave", kb);
        }));
        return true;
    }

    private static boolean projectile(LabMob m, Params p, LivingEntity t, long now) {
        int count = Math.max(1, p.integer("count", 1));
        double spread = p.dbl("spread", 0);
        double burst = p.dbl("burst_interval", 0);
        int w = Math.min(m.windupTicks(p, 0.4), 30);
        int burstTicks = (int) Math.round(burst * 20);
        standStill(m, now + w + (burstTicks > 0 ? burstTicks * (count - 1) : 0) + 6);
        m.castTick = now;
        String fx = p.str("fx");
        double speed = Math.max(0.2, p.dbl("speed", 0.8));
        Object g = p.get("gravity");
        double gravity = g instanceof Boolean b ? (b ? 0.03 : 0) : p.dbl("gravity", 0);
        Object h = p.get("homing");
        double homing = h instanceof Boolean b ? (b ? 0.5 : 0) : p.dbl("homing", 0);
        double range = p.dbl("range", 14);
        int life = (int) Math.ceil((range + 4) / speed) + 10;
        MobFx.ProjectileSpec spec = new MobFx.ProjectileSpec(fx, speed, gravity, homing, 0.45, Math.min(160, life),
                fx == null ? Particle.CRIT : null);
        double dmg = m.skillDamage(p, "damage", 1.0);
        UUID tid = t.getUniqueId();
        // 짧은 조준선
        new BukkitRunnable() {
            int i = 0;
            @Override
            public void run() {
                if (!m.isAlive() || i++ >= w) {
                    cancel();
                    return;
                }
                if (i % 3 == 0) {
                    LivingEntity tt = m.targetById(tid);
                    if (tt == null) return;
                    Location e = m.eye();
                    Vector d = tt.getLocation().add(0, 1, 0).toVector().subtract(e.toVector());
                    double len = Math.min(3, d.length());
                    d.normalize();
                    for (double s = 0.6; s <= len; s += 0.5) MobFx.dust(e.clone().add(d.clone().multiply(s)), MobFx.RED, 0.7f, 1, 0);
                }
            }
        }.runTaskTimer(m.services.plugin(), 0L, 1L);
        Runnable fire = new Runnable() {
            int shot = 0;
            @Override
            public void run() {
                if (!m.isAlive()) return;
                LivingEntity tt = m.targetById(tid);
                if (tt == null) return;
                Location from = m.eye();
                Vector aim = tt.getLocation().add(0, 1.0, 0).toVector().subtract(from.toVector());
                if (gravity > 0) aim.setY(aim.getY() + aim.length() * gravity * 6);
                int shots = burstTicks > 0 ? 1 : count;
                for (int i = 0; i < shots; i++) {
                    double off = shots == 1 ? 0 : -spread / 2 + spread * i / (shots - 1);
                    Vector d = aim.clone().rotateAroundY(Math.toRadians(off));
                    m.service.fx().projectile(from, d, spec, homing > 0 ? tt : null, m::validTarget,
                            (pl, at) -> {
                                hit(m, pl, dmg, DamageType.RANGED, "projectile", 0);
                                if (p.has("effect")) effect(m, pl, p.str("effect"), p.dbl("effect_duration", 3), p.dbl("amount", 0), at);
                                if (p.dbl("pool_radius", 0) > 0) pool(m, p, ground(at));
                                if (p.dbl("blast_radius", 0) > 0) blast(m, p, ground(at));
                            },
                            at -> {
                                MobFx.particle(Particle.SMOKE, at, 4, 0.1, 0.1, 0.1, 0.01);
                                if (p.dbl("pool_radius", 0) > 0) pool(m, p, ground(at));
                                if (p.dbl("blast_radius", 0) > 0) blast(m, p, ground(at));
                            });
                }
                play(from, "minecraft:entity.snowball.throw", 0.7f, 0.8f);
                m.castTick = m.service.now();
                shot++;
                if (burstTicks > 0 && shot < count) Bukkit.getScheduler().runTaskLater(m.services.plugin(), this, burstTicks);
            }
        };
        Bukkit.getScheduler().runTaskLater(m.services.plugin(), fire, Math.max(1, w));
        return true;
    }

    /** 착탄 폭발(projectile blast_radius): 떨어진 자리에 원 경고 → blast_delay 뒤 폭발 + 밀쳐내기. */
    private static void blast(LabMob m, Params p, Location at) {
        double r = p.dbl("blast_radius", 2.5);
        int delay = Math.max(10, m.windupTicks(p.dbl("blast_delay", 0.8)));
        double dmg = m.damage() * p.dbl("blast_damage", 1.2);
        double kb = p.dbl("blast_knockback", 0.6);
        MobFx.Shape shape = MobFx.Shape.circle(at, r);
        m.track(m.service.fx().telegraph(shape, delay, MobFx.ORANGE, null, () -> {
            MobFx.particle(Particle.EXPLOSION, at.clone().add(0, 0.4, 0), 2, 0.4, 0.2, 0.4, 0);
            MobFx.particle(Particle.LARGE_SMOKE, at.clone().add(0, 0.4, 0), 10, r / 2, 0.3, r / 2, 0.02);
            play(at, "minecraft:entity.generic.explode", 0.7f, 1.4f);
            for (LivingEntity e : m.victimsNear(at, r + 1)) {
                if (!shape.contains(e.getLocation())) continue;
                hit(m, e, dmg, DamageType.MAGIC, "blast", 0);
                if (kb > 0) push(e, at, kb * 2);
            }
        }));
    }

    private static void pool(LabMob m, Params p, Location at) {
        double r = p.dbl("pool_radius", 1.5);
        int dur = (int) Math.round(p.dbl("pool_duration", 4) * 20);
        double tickDmg = m.damage() * p.dbl("pool_damage", 0.25);
        String fx = p.str("pool_fx", m.services.content().fxModels().containsKey("molten_puddle") && p.str("fx", "").contains("molten") ? "molten_puddle" : null);
        String effect = p.str("effect");
        m.service.fx().zone(at, r, dur, fx, MobFx.RED, m::validTarget, pl -> {
            hit(m, pl, tickDmg, DamageType.TRUE, "pool", 0);
            if (effect != null) effect(m, pl, effect, 2, p.dbl("amount", 0), at);
        });
    }

    private static boolean beam(LabMob m, Params p, LivingEntity t, long now) {
        double length = p.dbl("length", 14);
        double width = p.dbl("width", 1.5);
        double duration = p.dbl("duration", 2);
        int tickEvery = Math.max(2, (int) Math.round(p.dbl("tick", 0.25) * 20));
        boolean sweep = p.bool("sweep", false);
        String fx = p.str("fx", "telegraph_line");
        Location o = ground(m.entity.getLocation());
        Vector dir0 = m.dirTo(t.getLocation());
        int w = m.windupTicks(p, 1.2);
        int dur = (int) Math.round(duration * 20);
        standStill(m, now + w + dur + 6);
        m.bodyYaw = Geometry.yawOf(dir0.getX(), dir0.getZ());
        Vector telegraphDir = sweep ? dir0.clone().rotateAroundY(Math.toRadians(40)) : dir0;
        m.castTick = now;
        m.track(m.service.fx().telegraph(MobFx.Shape.line(o, telegraphDir, length, width), w, MobFx.RED, null, () -> {
            if (!m.isAlive()) return;
            double dmg = m.skillDamage(p, "damage_per_tick", 0.5);
            ItemDisplay plate = m.service.fx().flat(fx, o.clone().add(telegraphDir.clone().multiply(length / 2)).add(0, 0.08, 0),
                    (float) width, (float) (length / 2.0), Geometry.yawOf(telegraphDir.getX(), telegraphDir.getZ()));
            play(o, "minecraft:entity.guardian.attack", 0.8f, 1.3f);
            BukkitRunnable r = new BukkitRunnable() {
                int i = 0;
                @Override
                public void run() {
                    if (!m.isAlive() || i > dur) {
                        cancel();
                        m.service.fx().discard(plate);
                        return;
                    }
                    double prog = dur <= 0 ? 1 : i / (double) dur;
                    Vector d = sweep ? dir0.clone().rotateAroundY(Math.toRadians(40 - 80 * prog)) : dir0;
                    if (sweep && plate != null && plate.isValid() && i % 2 == 0) {
                        plate.teleport(o.clone().add(d.clone().multiply(length / 2)).add(0, 0.08, 0));
                        m.bodyYaw = Geometry.yawOf(d.getX(), d.getZ());
                    }
                    if (i % 2 == 0) {
                        Location e = m.eye();
                        for (double s = 0.8; s <= length; s += 0.9) MobFx.particle(Particle.END_ROD, e.clone().add(d.clone().multiply(s)), 1, 0.02, 0.02, 0.02, 0);
                    }
                    if (i % tickEvery == 0) {
                        MobFx.Shape line = MobFx.Shape.line(o, d, length, width);
                        for (LivingEntity e : m.victimsNear(o, length + 1)) if (line.contains(e.getLocation())) hit(m, e, dmg, DamageType.MAGIC, "beam", 0);
                    }
                    i++;
                }
            };
            r.runTaskTimer(m.services.plugin(), 0L, 1L);
        }));
        return true;
    }

    private static boolean breath(LabMob m, Params p, LivingEntity t, long now) {
        double angle = p.dbl("angle", 60);
        double length = p.dbl("length", 6);
        int dur = (int) Math.round(p.dbl("duration", 1.5) * 20);
        int tickEvery = Math.max(2, (int) Math.round(p.dbl("tick", 0.5) * 20));
        Particle particle = MobFx.parseParticle(p.str("particle"), Particle.CLOUD);
        Location o = ground(m.entity.getLocation());
        Vector dir = m.dirTo(t.getLocation());
        int w = m.windupTicks(p, 0.6);
        standStill(m, now + w + dur + 6);
        m.bodyYaw = Geometry.yawOf(dir.getX(), dir.getZ());
        MobFx.Shape shape = MobFx.Shape.cone(o, dir, angle, length);
        m.castTick = now;
        m.track(m.service.fx().telegraph(shape, w, MobFx.RED, null, () -> {
            if (!m.isAlive()) return;
            double dmg = m.skillDamage(p, "damage_per_tick", 0.4);
            play(o, "minecraft:entity.ender_dragon.shoot", 0.6f, 1.4f);
            new BukkitRunnable() {
                int i = 0;
                @Override
                public void run() {
                    if (!m.isAlive() || i > dur) {
                        cancel();
                        return;
                    }
                    m.castTick = m.service.now() - 4;
                    if (i % 2 == 0) {
                        Location e = m.eye();
                        ThreadLocalRandom r = ThreadLocalRandom.current();
                        for (int k = 0; k < 6; k++) {
                            double a = Math.toRadians((r.nextDouble() - 0.5) * angle);
                            Vector d = dir.clone().rotateAroundY(a);
                            double s = 0.5 + r.nextDouble() * length;
                            MobFx.particle(particle, e.clone().add(d.multiply(s)).subtract(0, s * 0.08, 0), 1, 0.1, 0.1, 0.1, 0.01);
                        }
                    }
                    if (i % tickEvery == 0) {
                        for (LivingEntity pl : m.victimsNear(o, length + 1)) {
                            if (!shape.contains(pl.getLocation())) continue;
                            hit(m, pl, dmg, DamageType.MAGIC, "breath", 0);
                            if (p.has("effect")) effect(m, pl, p.str("effect"), p.dbl("effect_duration", 2), p.dbl("amount", 0), o);
                        }
                    }
                    i++;
                }
            }.runTaskTimer(m.services.plugin(), 0L, 1L);
        }));
        return true;
    }

    private static boolean shield(LabMob m, Params p, long now) {
        double amount = p.dbl("amount", 0.2);
        int dur = (int) Math.round(p.dbl("duration", 4) * 20);
        double reduction = p.dbl("reduction", 0);
        List<LabMob> targets = p.bool("self_only", true) ? List.of(m) : m.alliesNear(p.dbl("radius", 8));
        for (LabMob a : targets) {
            a.shieldHp = Math.max(a.shieldHp, a.stats.maxHp() * amount);
            a.shieldUntil = now + dur;
            if (reduction > 0) {
                a.shieldReduction = reduction;
                a.reductionUntil = now + dur;
            }
            Location c = a.location().add(0, a.entity.getHeight() / 2, 0);
            for (int i = 0; i < 16; i++) {
                double th = 2 * Math.PI * i / 16;
                MobFx.dust(c.clone().add(Math.cos(th) * 0.9, Math.sin(th * 2) * 0.4, Math.sin(th) * 0.9), Color.fromRGB(140, 200, 255), 1.2f, 1, 0);
            }
            a.refreshNameplate();
        }
        play(m.location(), "minecraft:block.amethyst_block.resonate", 1f, 0.8f);
        m.busyUntil = now + 8;
        return true;
    }

    private static boolean summon(LabMob m, Params p, long now) {
        String mobId = p.str("mob");
        if (mobId == null || m.services.content().mob(mobId) == null) return false;
        int room = p.integer("max_alive", 4) - aliveSummons(m);
        int count = Math.min(Math.max(1, p.integer("count", 2)), room);
        if (count <= 0) return false;
        double radius = p.dbl("radius", 3);
        standStill(m, now + 20);
        m.castTick = now;
        Location c = m.entity.getLocation();
        ThreadLocalRandom r = ThreadLocalRandom.current();
        for (int i = 0; i < count; i++) {
            double a = r.nextDouble() * Math.PI * 2;
            double d = 1 + r.nextDouble() * Math.max(0.5, radius - 1);
            Location at = c.clone().add(Math.cos(a) * d, 0, Math.sin(a) * d);
            if (!at.getBlock().isPassable() || !at.clone().add(0, 1, 0).getBlock().isPassable()) at = c.clone();
            Location spawnAt = at;
            MobFx.particle(Particle.REVERSE_PORTAL, spawnAt.clone().add(0, 0.5, 0), 20, 0.3, 0.5, 0.3, 0.05);
            Bukkit.getScheduler().runTaskLater(m.services.plugin(), () -> {
                if (!m.isAlive()) return;
                CustomMob s = m.service.spawn(mobId, spawnAt, m.ctx, false);
                if (s instanceof LabMob lm) {
                    lm.summoner = m;
                    m.summons.add(lm.entity.getUniqueId());
                    Player tt = m.target();
                    if (tt != null) lm.addThreat(tt, 1);
                }
            }, 10L);
        }
        play(c, "minecraft:entity.evoker.prepare_summon", 0.8f, 1.2f);
        return true;
    }

    private static boolean blink(LabMob m, Params p, LivingEntity t, long now) {
        double range = p.dbl("range", 8);
        boolean behind = p.bool("behind", false);
        Location from = m.entity.getLocation();
        Location tl = t.getLocation();
        Location dest;
        if (behind) {
            Vector back = tl.getDirection().setY(0);
            if (back.lengthSquared() < 1e-4) back = new Vector(0, 0, 1);
            dest = tl.clone().subtract(back.normalize().multiply(1.6));
        } else {
            double dist = MobAi.horizontal(from, tl);
            Vector d = tl.toVector().subtract(from.toVector()).setY(0);
            if (d.lengthSquared() < 1e-4) d = new Vector(1, 0, 0);
            d.normalize();
            dest = dist < 4 ? from.clone().subtract(d.multiply(Math.min(range, 7))) : tl.clone().subtract(d.multiply(3));
        }
        dest = safeSpot(dest, from);
        if (dest == null || dest.distance(from) > range * 2 + 2) return false;
        dest.setYaw(Geometry.yawOf(tl.getX() - dest.getX(), tl.getZ() - dest.getZ()));
        MobFx.particle(Particle.PORTAL, from.clone().add(0, 1, 0), 30, 0.3, 0.6, 0.3, 0.3);
        MobFx.particle(Particle.LARGE_SMOKE, from.clone().add(0, 0.5, 0), 6, 0.3, 0.3, 0.3, 0.01);
        m.entity.teleport(dest);
        m.bodyYaw = dest.getYaw();
        MobFx.particle(Particle.REVERSE_PORTAL, dest.clone().add(0, 1, 0), 30, 0.3, 0.6, 0.3, 0.05);
        play(dest, "minecraft:entity.enderman.teleport", 0.7f, 1.3f);
        m.busyUntil = now + 8;
        double dmgMult = p.dbl("damage", 0);
        if (dmgMult > 0) {
            UUID tid = t.getUniqueId();
            Bukkit.getScheduler().runTaskLater(m.services.plugin(), () -> {
                LivingEntity tt = m.targetById(tid);
                if (!m.isAlive() || tt == null) return;
                m.attackTick = m.service.now();
                if (tt.getLocation().distance(m.entity.getLocation()) <= 3.2) {
                    hit(m, tt, m.damage() * dmgMult * m.pendingFirstHitMult, DamageType.MELEE, "blink", 0);
                    m.pendingFirstHitMult = 1;
                }
            }, 5L);
        }
        return true;
    }

    /** 발 디딜 수 있는 위치 (발·머리 통과 가능 + 아래 단단함). */
    private static Location safeSpot(Location want, Location fallback) {
        for (int dy : new int[] {0, 1, -1, 2}) {
            Location l = want.clone().add(0, dy, 0);
            Block feet = l.getBlock();
            if (feet.isPassable() && feet.getRelative(0, 1, 0).isPassable() && !feet.getRelative(0, -1, 0).isPassable()
                    && feet.getType() != Material.LAVA) {
                return new Location(l.getWorld(), feet.getX() + 0.5, feet.getY(), feet.getZ() + 0.5);
            }
        }
        return null;
    }

    private static boolean healAllies(LabMob m, Params p) {
        double amount = p.dbl("amount", 0.12);
        m.castTick = m.service.now();
        for (LabMob a : m.alliesNear(p.dbl("radius", 10))) {
            m.services.damage().heal(a.entity, a.stats.maxHp() * amount, true);
            MobFx.particle(Particle.HAPPY_VILLAGER, a.location().add(0, a.entity.getHeight() + 0.2, 0), 8, 0.4, 0.3, 0.4, 0);
        }
        MobFx.ring(m.location(), 1.5, Particle.HAPPY_VILLAGER, 14);
        play(m.location(), "minecraft:block.amethyst_block.chime", 1f, 1.4f);
        m.busyUntil = m.service.now() + 12;
        return true;
    }

    private static boolean buffAllies(LabMob m, Params p, long now) {
        int dur = (int) Math.round(p.dbl("duration", 8) * 20);
        double dm = p.dbl("damage_mult", 1.2), sm = p.dbl("speed_mult", 1.0);
        for (LabMob a : m.alliesNear(p.dbl("radius", 10))) {
            a.buffDamage = Math.max(a.service.now() < a.buffUntil ? a.buffDamage : 1, dm);
            a.buffSpeed = Math.max(a.service.now() < a.buffUntil ? a.buffSpeed : 1, sm);
            a.buffUntil = now + dur;
            MobFx.dust(a.location().add(0, a.entity.getHeight() + 0.3, 0), Color.fromRGB(255, 70, 50), 1.3f, 8, 0.3);
        }
        MobFx.ring(m.location(), 2, Particle.ANGRY_VILLAGER, 8);
        play(m.location(), "minecraft:event.raid.horn", 0.25f, 1.6f);
        m.busyUntil = now + 12;
        return true;
    }

    private static boolean snare(LabMob m, Params p, LivingEntity t, long now) {
        double radius = p.dbl("radius", 1.5);
        Location c = ground(t.getLocation());
        int w = m.windupTicks(p, 1.0);
        standStill(m, now + Math.min(w, 20));
        m.castTick = now;
        String fx = p.str("fx");
        String plate = fx != null && fx.startsWith("telegraph") ? fx : null;
        MobFx.Shape shape = MobFx.Shape.circle(c, radius);
        m.track(m.service.fx().telegraph(shape, w, MobFx.PURPLE, plate, () -> {
            if (!m.isAlive()) return;
            double root = p.dbl("root", p.dbl("duration", 1.5));
            MobFx.particle(Particle.CRIT, c.clone().add(0, 0.2, 0), 10, radius / 2, 0.1, radius / 2, 0.05);
            MobFx.ring(c, radius * 0.8, Particle.SPORE_BLOSSOM_AIR, 16);
            play(c, "minecraft:block.rooted_dirt.break", 1f, 0.7f);
            for (LivingEntity e : m.victimsNear(c, radius + 1)) {
                if (!shape.contains(e.getLocation())) continue;
                hit(m, e, m.skillDamage(p, "damage", 0.6), DamageType.MAGIC, "snare", 0);
                if (root > 0) effect(m, e, "root", root, 1, c);
                if (p.dbl("slow", 0) > 0) effect(m, e, "slow", p.dbl("duration", root + 1), p.dbl("slow", 0.3), c);
            }
        }));
        return true;
    }

    private static boolean pull(LabMob m, Params p, LivingEntity t, long now) {
        double radius = p.dbl("radius", 0);
        double strength = p.dbl("strength", 1.2);
        String fx = p.str("fx");
        int w = m.windupTicks(p, 0.7);
        standStill(m, now + w + 8);
        m.castTick = now;
        Location o = ground(m.entity.getLocation());
        MobFx.Shape shape = radius > 0 ? MobFx.Shape.circle(o, radius)
                : MobFx.Shape.line(o, m.dirTo(t.getLocation()), Math.max(2, MobAi.horizontal(o, t.getLocation())), 1.2);
        UUID tid = t.getUniqueId();
        m.track(m.service.fx().telegraph(shape, w, MobFx.PURPLE, null, () -> {
            if (!m.isAlive()) return;
            List<LivingEntity> victims = new ArrayList<>();
            if (radius > 0) {
                for (LivingEntity e : m.victimsNear(o, radius + 0.5)) if (shape.contains(e.getLocation())) victims.add(e);
            } else {
                LivingEntity tt = m.targetById(tid);
                if (tt != null && tt.getLocation().distance(o) <= p.dbl("range", 10) + 2) victims.add(tt);
            }
            play(o, "minecraft:item.trident.return", 1f, 0.8f);
            for (LivingEntity e : victims) {
                Location me = m.eye();
                ItemDisplay tether = fx != null ? m.service.fx().tether(fx, me, e.getLocation().add(0, 1, 0)) : null;
                Vector d = me.toVector().subtract(e.getLocation().toVector());
                double len = d.length();
                d.setY(0);
                if (d.lengthSquared() > 1e-4) d.normalize().multiply(Math.min(2.2, 0.32 * strength * Math.sqrt(Math.max(1, len)) * 1.6));
                d.setY(0.35);
                e.setVelocity(d);
                hit(m, e, m.skillDamage(p, "damage", 0.8), DamageType.MELEE, "pull", 0);
                for (double s = 0; s < len; s += 0.6) {
                    Vector dir = e.getLocation().add(0, 1, 0).toVector().subtract(me.toVector()).normalize();
                    MobFx.dust(me.clone().add(dir.multiply(s)), Color.fromRGB(150, 150, 160), 0.8f, 1, 0);
                }
                if (tether != null) Bukkit.getScheduler().runTaskLater(m.services.plugin(), () -> m.service.fx().discard(tether), 8L);
            }
        }));
        return true;
    }

    private static boolean debuff(LabMob m, Params p, LivingEntity t, long now) {
        double radius = p.dbl("radius", 0);
        String effect = p.str("effect", "slow");
        double duration = p.dbl("duration", 3);
        double amount = p.dbl("amount", 0);
        double cdSlow = p.dbl("cooldown_slow", 0);
        Particle particle = MobFx.parseParticle(p.str("particle"), Particle.WITCH);
        int w = m.windupTicks(p, 0.8);
        standStill(m, now + Math.min(w, 16));
        m.castTick = now;
        UUID tid = t.getUniqueId();
        Location c = ground(t.getLocation());
        MobFx.Shape shape = MobFx.Shape.circle(c, radius > 0 ? radius : 1.0);
        m.track(m.service.fx().telegraph(shape, w, MobFx.PURPLE, null, () -> {
            if (!m.isAlive()) return;
            List<LivingEntity> victims = new ArrayList<>();
            if (radius > 0) {
                for (LivingEntity e : m.victimsNear(c, radius + 1)) if (shape.contains(e.getLocation())) victims.add(e);
            } else {
                LivingEntity tt = m.targetById(tid);
                if (tt != null && tt.getLocation().distance(c) <= 3.0) victims.add(tt);
            }
            MobFx.particle(particle, c.clone().add(0, 0.5, 0), 20, Math.max(0.3, radius / 2), 0.4, Math.max(0.3, radius / 2), 0.02);
            play(c, "minecraft:entity.evoker.cast_spell", 0.8f, 1.2f);
            for (LivingEntity e : victims) {
                effect(m, e, effect, duration, amount, c);
                if (cdSlow > 0) m.services.effects().apply(e, "cooldown_slow", duration, cdSlow, m.entity.isValid() ? m.entity : null);
                MobFx.particle(particle, e.getLocation().add(0, 2.1, 0), 6, 0.2, 0.1, 0.2, 0.01);
            }
        }));
        return true;
    }

    private static boolean stealth(LabMob m, Params p, long now) {
        int dur = (int) Math.round(p.dbl("duration", 4) * 20);
        m.stealthUntil = now + dur;
        m.stealthRevealOnHit = p.bool("reveal_on_hit", true);
        m.pendingFirstHitMult = 1 + p.dbl("bonus_damage", 0.5);
        m.rig.setHidden(true);
        m.entity.setGlowing(false);
        MobFx.particle(Particle.LARGE_SMOKE, m.location().add(0, 0.8, 0), 25, 0.4, 0.6, 0.4, 0.02);
        play(m.location(), "minecraft:entity.illusioner.mirror_move", 0.8f, 1.0f);
        m.busyUntil = now + 4;
        return true;
    }

    static void endStealth(LabMob m) {
        if (m.stealthUntil == 0) return;
        m.stealthUntil = 0;
        m.rig.setHidden(false);
        MobFx.particle(Particle.SMOKE, m.location().add(0, 0.8, 0), 14, 0.3, 0.5, 0.3, 0.02);
    }

    private static boolean reflect(LabMob m, Params p, long now) {
        m.reflectRatio = p.dbl("ratio", 0.3);
        m.reflectUntil = now + Math.round(p.dbl("duration", 4) * 20);
        MobFx.particle(Particle.ENCHANTED_HIT, m.location().add(0, m.entity.getHeight() / 2, 0), 24, 0.5, 0.6, 0.5, 0.2);
        play(m.location(), "minecraft:block.beacon.power_select", 0.6f, 1.8f);
        m.refreshNameplate();
        m.busyUntil = now + 6;
        return true;
    }

    private static boolean lifeDrain(LabMob m, Params p, LivingEntity t, long now) {
        double range = p.dbl("range", 7);
        int dur = (int) Math.round(p.dbl("duration", 3) * 20);
        int tickEvery = Math.max(2, (int) Math.round(p.dbl("tick", 0.5) * 20));
        double healRatio = p.dbl("heal_ratio", 1.0);
        String fx = p.str("fx");
        standStill(m, now + dur + 4);
        UUID tid = t.getUniqueId();
        ItemDisplay tether = fx != null ? m.service.fx().tether(fx, m.eye(), t.getLocation().add(0, 1, 0)) : null;
        play(m.location(), "minecraft:entity.vex.charge", 0.8f, 0.6f);
        new BukkitRunnable() {
            int i = 0;
            @Override
            public void run() {
                LivingEntity tt = m.targetById(tid);
                boolean ok = m.isAlive() && tt != null && i <= dur
                        && tt.getLocation().distance(m.location()) <= range + 2 && !m.services.effects().isStunned(m.entity);
                if (!ok) {
                    cancel();
                    m.service.fx().discard(tether);
                    if (m.isAlive()) m.busyUntil = Math.min(m.busyUntil, m.service.now() + 2);
                    return;
                }
                m.castTick = m.service.now() - 4;
                Location a = m.eye(), b = tt.getLocation().add(0, 1, 0);
                if (i % 2 == 0) {
                    if (tether != null) m.service.fx().updateTether(tether, fx, a, b);
                    Vector d = a.toVector().subtract(b.toVector());
                    double len = d.length();
                    d.normalize();
                    double s = (i * 0.35) % Math.max(0.5, len);
                    MobFx.dust(b.clone().add(d.multiply(s)), Color.fromRGB(200, 30, 60), 1f, 1, 0);
                }
                if (i % tickEvery == 0 && i > 0) {
                    DamageContext c = DamageContext.raw(m.entity, tt, m.skillDamage(p, "damage", 0.5), DamageType.MAGIC).source("life_drain");
                    m.services.damage().deal(c);
                    if (c.dealt() > 0) m.services.damage().heal(m.entity, c.dealt() * healRatio, true);
                }
                i++;
            }
        }.runTaskTimer(m.services.plugin(), 0L, 1L);
        return true;
    }

    // ── 땅속·급강하 (새 몸 형태: 땅굴웜 · 와이번 · 하피) ─────────────────────

    /**
     * burrow — 땅속으로 파고들어(몸이 가라앉은 뒤 모델 숨김·무적·충돌 끔) 흙더미를 밀며 대상 쪽으로 이동 → 대상 발밑에
     * 경고 원 → 솟구쳐 원 안을 띄운다. 시야가 막혀도 쓸 수 있다(땅속으로 돌아감).
     * params: range(14) · min_range(4) · speed(땅속 이동 배율, 1.6) · duration(땅속 최대 초, 3) · windup(솟구치기 전 경고, 1.0)
     *         · radius(2) · damage(1.5) · launch(띄우는 세기, 1.0) · effect/amount/effect_duration(선택)
     */
    private static boolean burrow(LabMob m, Params p, LivingEntity t, long now) {
        if (m.flying || m.burrowed) return false;
        double radius = p.dbl("radius", 2.0);
        double speed = Math.max(0.5, p.dbl("speed", 1.6));
        int maxTravel = (int) Math.round(Math.max(0.5, p.dbl("duration", 3)) * 20);
        int w = m.windupTicks(p, 1.0);
        UUID tid = t.getUniqueId();
        Location start = m.entity.getLocation();
        MobAi.stop(m);
        m.castTick = now;
        m.motionLocked = true;
        m.busyUntil = Math.max(m.busyUntil, now + 10 + maxTravel + w + 20);
        dirt(start, 24, 0.5);
        play(start, "minecraft:block.rooted_dirt.break", 1f, 0.6f);
        play(start, "minecraft:block.gravel.break", 0.8f, 0.5f);
        new BukkitRunnable() {
            int i = 0;
            boolean under, surfacing;
            Location mark;

            @Override
            public void run() {
                if (!m.isAlive()) {
                    cancel(); // 제거·정리 경로 — 몹과 함께 상태도 사라진다
                    return;
                }
                i++;
                Location cur = m.entity.getLocation();
                if (!under) {
                    // 0.4초 동안 파고드는 흙 + 소리, 그 뒤 숨김
                    if (i % 2 == 0) dirt(cur, 6, 0.4);
                    if (i >= 8) {
                        under = true;
                        m.burrowed = true;
                        m.rig.setHidden(true);
                        m.entity.setCollidable(false);
                    }
                    return;
                }
                if (!surfacing) {
                    LivingEntity tt = m.targetById(tid);
                    if (i % 2 == 0) mound(cur);
                    if (i % 10 == 0) play(cur, "minecraft:block.gravel.step", 0.7f, 0.6f);
                    if (tt != null && i % 5 == 0 && m.entity.isAware()) m.entity.getPathfinder().moveTo(tt.getLocation(), speed);
                    boolean close = tt == null || MobAi.horizontal(cur, tt.getLocation()) <= 1.3;
                    if (close || i >= maxTravel + 8) {
                        surfacing = true;
                        MobAi.stop(m);
                        Location at = ground(tt != null ? tt.getLocation() : cur);
                        mark = at;
                        MobFx.Shape shape = MobFx.Shape.circle(at, radius);
                        m.track(m.service.fx().telegraph(shape, w, MobFx.ORANGE, null, () -> {
                            cancel();
                            erupt(m, p, at, shape);
                        }));
                    }
                } else if (i % 3 == 0 && mark != null) {
                    dirt(mark, 4, radius * 0.4); // 솟구칠 자리의 땅울림
                }
            }
        }.runTaskTimer(m.services.plugin(), 1L, 1L);
        return true;
    }

    /** burrow 의 솟구침: 경고 원 자리로 나와 모델을 드러내고(바닥 아래에서 올라옴) 원 안을 띄운다. */
    private static void erupt(LabMob m, Params p, Location at, MobFx.Shape shape) {
        if (!m.isAlive()) return;
        Location dest = safeSpot(at, m.entity.getLocation());
        if (dest != null) {
            dest.setYaw(m.bodyYaw);
            m.entity.teleport(dest);
        }
        m.burrowed = false;
        m.motionLocked = false;
        m.entity.setCollidable(true);
        m.rig.setHidden(false);
        long tn = m.service.now();
        m.emergeTick = tn;
        m.attackTick = tn;
        m.attackArm = 2;
        m.castTick = tn;
        m.busyUntil = tn + 14;
        m.refreshNameplate();
        dirt(at, 40, Math.max(0.6, shape.size() * 0.5));
        MobFx.particle(Particle.EXPLOSION, at.clone().add(0, 0.3, 0), 1, 0, 0, 0, 0);
        play(at, "minecraft:entity.zombie.break_wooden_door", 0.8f, 0.6f);
        play(at, "minecraft:block.rooted_dirt.break", 1f, 0.5f);
        double dmg = m.skillDamage(p, "damage", 1.5);
        double launch = p.dbl("launch", 1.0);
        for (LivingEntity e : m.victimsNear(at, shape.size() + 1)) {
            if (!shape.contains(e.getLocation())) continue;
            hit(m, e, dmg, DamageType.MELEE, "burrow", 0);
            if (launch > 0 && !m.services.effects().isKnockbackImmune(e)) {
                e.setVelocity(e.getVelocity().setY(0.55 + 0.35 * launch));
            }
            if (p.has("effect")) effect(m, e, p.str("effect"), p.dbl("effect_duration", 2), p.dbl("amount", 0), at);
        }
    }

    /** 발밑 블록 조각 입자 (흙·돌 — 블록은 바꾸지 않는다). */
    private static void dirt(Location at, int count, double spread) {
        if (at.getWorld() == null) return;
        Block b = at.clone().subtract(0, 0.2, 0).getBlock();
        BlockData data = b.getType().isSolid() ? b.getBlockData() : Material.DIRT.createBlockData();
        at.getWorld().spawnParticle(Particle.BLOCK, at.clone().add(0, 0.15, 0), count, spread, 0.1, spread, 0.1, data);
    }

    /** 땅속 이동 흔적: 흙더미가 밀려 올라오는 입자. */
    private static void mound(Location at) {
        dirt(at, 5, 0.3);
        MobFx.particle(Particle.SMOKE, at.clone().add(0, 0.1, 0), 1, 0.2, 0.02, 0.2, 0.005);
    }

    /**
     * dive — 비행 몹이 대상 위로 높이 날아올라(천장 아래까지) 공중에 멈춘 채 바닥에 직선 경고 → 그 선을 따라 급강하해
     * 착지점을 지나 overshoot 만큼 낮게 미끄러진다. 선 밖으로 비키면 맞지 않는다.
     * params: range(16) · height(대상 위 높이, 5) · windup(경고, 1.0) · speed(블록/틱, 1.1) · width(1.8) · overshoot(3)
     *         · damage(1.6) · knockback(0.8) · stun · effect/amount/effect_duration
     */
    private static boolean dive(LabMob m, Params p, LivingEntity t, long now) {
        if (!m.flying) return false;
        int w = m.windupTicks(p, 1.0);
        m.motionLocked = true;
        m.motion = RigMath.MOTION_RISE;
        m.castTick = now;
        m.busyUntil = Math.max(m.busyUntil, now + 30 + w + 70);
        play(m.location(), "minecraft:entity.ender_dragon.flap", 0.8f, 1.3f);
        new DiveTask(m, p, t.getUniqueId(), t.getLocation(), w).runTaskTimer(m.services.plugin(), 1L, 1L);
        return true;
    }

    /** dive 진행: 0 = 날아오름, 1 = 공중 정지·경고, 2 = 급강하(착지점까지), 3 = 낮게 미끄러짐. */
    private static final class DiveTask extends BukkitRunnable {
        private final LabMob m;
        private final Params p;
        private final UUID tid;
        private final int windup;
        private final double speed, width, overshoot;
        private final Set<UUID> struck = new HashSet<>();
        private Location lastSeen, climb, impact, end, prev;
        private MobFx.Shape line;
        private int phase, i, stuck;

        DiveTask(LabMob m, Params p, UUID tid, Location targetAt, int windup) {
            this.m = m;
            this.p = p;
            this.tid = tid;
            this.windup = windup;
            this.lastSeen = targetAt.clone();
            this.speed = Math.max(0.4, p.dbl("speed", 1.1));
            this.width = p.dbl("width", 1.8);
            this.overshoot = Math.max(0, p.dbl("overshoot", 3));
        }

        @Override
        public void run() {
            if (!m.isAlive()) {
                cancel();
                return;
            }
            i++;
            LivingEntity tt = m.targetById(tid);
            if (tt != null && phase == 0) lastSeen = tt.getLocation();
            Location cur = m.entity.getLocation();
            try {
                switch (phase) {
                    case 0 -> rise(cur);
                    case 1 -> hover();
                    default -> swoop(cur);
                }
            } catch (Throwable ex) {
                Log.error("몹 스킬 오류 (" + m.def.id() + "/dive)", ex);
                finish();
            }
        }

        private void rise(Location cur) {
            if (climb == null) {
                // 대상에서 몹 쪽으로 조금 물러난 하늘 — 천장 아래로 제한
                Vector back = cur.toVector().subtract(lastSeen.toVector()).setY(0);
                if (back.lengthSquared() < 1e-4) back = facing(m).multiply(-1);
                back.normalize().multiply(Math.max(2.5, Math.min(4.5, MobAi.horizontal(cur, lastSeen))));
                Location base = lastSeen.clone().add(back);
                double top = ceiling(base, p.dbl("height", 5) + 1) - m.entity.getHeight() - 0.4;
                climb = base.add(0, p.dbl("height", 5), 0);
                climb.setY(Math.max(lastSeen.getY() + 1.5, Math.min(climb.getY(), top)));
            }
            Vector v = climb.toVector().subtract(cur.toVector());
            if (v.length() > 0.5) v.normalize().multiply(0.5);
            m.entity.setVelocity(v);
            if (i % 6 == 0) play(cur, "minecraft:entity.ender_dragon.flap", 0.6f, 1.4f);
            if (cur.distanceSquared(climb) < 0.8 || i >= 26) {
                phase = 1;
                i = 0;
                m.entity.setVelocity(new Vector());
                aim(cur);
            }
        }

        private void aim(Location cur) {
            impact = ground(lastSeen).add(0, 0.4, 0);
            Vector flat = impact.toVector().subtract(cur.toVector()).setY(0);
            Vector dir = flat.lengthSquared() < 1e-4 ? facing(m) : flat.clone().normalize();
            Location groundStart = new Location(cur.getWorld(), cur.getX(), impact.getY() - 0.4, cur.getZ());
            line = MobFx.Shape.line(groundStart, dir, flat.length() + overshoot, width);
            end = impact.clone().add(dir.clone().multiply(overshoot));
            m.bodyYaw = Geometry.yawOf(dir.getX(), dir.getZ());
            play(cur, "minecraft:entity.phantom.swoop", 1f, 0.8f);
            m.track(m.service.fx().telegraph(line, windup, MobFx.RED, null, () -> {
                phase = 2;
                i = 0;
                prev = m.entity.getLocation();
                m.motion = RigMath.MOTION_DIVE;
                m.attackTick = m.service.now();
                play(prev, "minecraft:entity.phantom.bite", 1f, 0.6f);
            }));
        }

        private void hover() {
            m.entity.setVelocity(new Vector());
            if (i % 3 == 0 && impact != null) {
                Location e = m.eye();
                Vector d = impact.toVector().subtract(e.toVector());
                double len = d.length();
                if (len > 0.1) {
                    d.normalize();
                    for (double s = 0.8; s < len; s += 0.8) MobFx.dust(e.clone().add(d.clone().multiply(s)), MobFx.RED, 0.8f, 1, 0);
                }
            }
            if (i > windup + 20) finish(); // 경고가 취소됨(대상 이탈 등)
        }

        private void swoop(Location cur) {
            Location goal = phase == 2 ? impact : end;
            Vector v = goal.toVector().subtract(cur.toVector());
            if (v.length() <= speed * 0.9 || i > 60) {
                if (phase == 2) {
                    phase = 3;
                    MobFx.particle(Particle.CLOUD, impact, 14, 0.6, 0.1, 0.6, 0.03);
                    play(impact, "minecraft:entity.generic.big_fall", 0.9f, 0.8f);
                } else {
                    finish();
                    return;
                }
                v = end.toVector().subtract(cur.toVector());
                if (v.lengthSquared() < 1e-4) {
                    finish();
                    return;
                }
            }
            v.normalize().multiply(speed);
            m.entity.setVelocity(v);
            double step = prev == null ? speed : prev.distance(cur);
            stuck = step < speed * 0.25 && i > 3 ? stuck + 1 : 0;
            if (i % 2 == 0) MobFx.particle(Particle.CLOUD, cur.clone().add(0, 0.3, 0), 2, 0.2, 0.2, 0.2, 0.01);
            double dmg = m.skillDamage(p, "damage", 1.6);
            double reach = width / 2 + 0.9;
            Location from = prev == null ? cur : prev;
            for (LivingEntity e : m.victimsNear(cur, reach + speed + 2)) {
                if (struck.contains(e.getUniqueId()) || !line.contains(e.getLocation())) continue;
                Location el = e.getLocation();
                double d2 = Geometry.segmentDist2(from.getX(), from.getY(), from.getZ(), cur.getX(), cur.getY(), cur.getZ(),
                        el.getX(), el.getY() + 0.9, el.getZ());
                if (d2 > (reach + 0.4) * (reach + 0.4)) continue;
                struck.add(e.getUniqueId());
                m.attackTick = m.service.now();
                hit(m, e, dmg, DamageType.MELEE, "dive", p.dbl("knockback", 0.8));
                if (p.dbl("stun", 0) > 0) effect(m, e, "stun", p.dbl("stun", 0), 1, cur);
                if (p.has("effect")) effect(m, e, p.str("effect"), p.dbl("effect_duration", 3), p.dbl("amount", 0), cur);
            }
            prev = cur.clone();
            if (stuck >= 3) finish(); // 벽·바닥에 막힘
        }

        private void finish() {
            cancel();
            m.motion = RigMath.MOTION_NONE;
            m.motionLocked = false;
            if (m.isAlive()) {
                m.entity.setVelocity(new Vector(0, 0.25, 0));
                long tn = m.service.now();
                m.busyUntil = tn + 10;
            }
        }
    }

    /** from 위로 maxUp 칸 안의 첫 막힌 블록 높이 (없으면 from.y + maxUp). */
    private static double ceiling(Location from, double maxUp) {
        for (int dy = 1; dy <= Math.ceil(maxUp); dy++) {
            Block b = from.clone().add(0, dy, 0).getBlock();
            if (!b.isPassable()) return b.getY();
        }
        return from.getY() + maxUp;
    }

    /** 훈련용({@link MobDrill}): 거리·시야 조건을 건너뛰고 skills[index] 를 대상에게 바로 시전. 예외는 호출자가 센다. */
    static boolean forceCast(LabMob m, int index, LivingEntity t) {
        if (index < 0 || index >= m.skills.size()) return false;
        MobDef.MobSkillDef s = m.skills.get(index);
        String type = s.type() == null ? "" : s.type().toLowerCase(Locale.ROOT);
        if (PASSIVE.contains(type)) return false;
        long now = m.service.now();
        Location loc = m.entity.getLocation(), tl = t.getLocation();
        m.bodyYaw = Geometry.yawOf(tl.getX() - loc.getX(), tl.getZ() - loc.getZ());
        boolean ok = cast(m, type, s.params(), t, now);
        if (ok) m.castTick = now;
        return ok;
    }

    // ── 패시브 ───────────────────────────────────────────────────────────

    /** 매 틱: 은신 만료·trail·aura·시각 효과. */
    static void tickPassives(LabMob m, long now) {
        if (m.stealthUntil > 0 && now >= m.stealthUntil) endStealth(m);
        if (m.shieldHp > 0 && now >= m.shieldUntil) {
            m.shieldHp = 0;
            m.refreshNameplate();
        }
        if (m.reflectUntil > 0 && now < m.reflectUntil && now % 8 == 0) {
            MobFx.particle(Particle.ENCHANTED_HIT, m.location().add(0, m.entity.getHeight() / 2, 0), 3, 0.4, 0.5, 0.4, 0.05);
        }
        if (m.enraged && now % 10 == 0) {
            MobFx.dust(m.location().add(0, m.entity.getHeight() * 0.6, 0), Color.fromRGB(220, 30, 30), 1.2f, 3, 0.4);
        }
        if (m.ambushing || m.targetId == null) return;
        for (int i = 0; i < m.skills.size(); i++) {
            MobDef.MobSkillDef s = m.skills.get(i);
            String type = s.type();
            if (!"trail".equals(type) && !"aura".equals(type)) continue;
            Params p = s.params();
            long interval = Math.max(5, Math.round(p.dbl("interval", "trail".equals(type) ? 0.5 : 2.0) * 20));
            long next = m.passiveNext.getOrDefault(i, 0L);
            if (now < next) continue;
            m.passiveNext.put(i, now + interval);
            if ("trail".equals(type)) {
                if (m.moveSpeed < 0.03) continue;
                Location at = ground(m.entity.getLocation());
                double r = p.dbl("radius", 1.2);
                int dur = (int) Math.round(p.dbl("duration", 4) * 20);
                double dmg = m.damage() * p.dbl("damage_per_second", 0.3) * 0.5;
                m.service.fx().zone(at, r, dur, p.str("fx"), MobFx.ORANGE, m::validTarget,
                        pl -> hit(m, pl, dmg, DamageType.TRUE, "trail", 0));
            } else {
                double r = p.dbl("radius", 3);
                String effect = p.str("effect", "damage");
                Location c = m.location();
                MobFx.ring(c, r, auraParticle(effect), (int) Math.max(10, r * 6));
                for (LivingEntity pl : m.victimsNear(c, r)) effect(m, pl, effect, Math.max(3, interval / 20.0 + 1), p.dbl("amount", 0), c);
            }
        }
    }

    private static Particle auraParticle(String effect) {
        return switch (effect == null ? "" : effect) {
            case "frost" -> Particle.SNOWFLAKE;
            case "infection" -> Particle.SPORE_BLOSSOM_AIR;
            case "burn" -> Particle.FLAME;
            case "poison" -> Particle.ITEM_SLIME;
            default -> Particle.CRIT;
        };
    }

    /** 피격 후: 분노 임계 확인. */
    static void onHurt(LabMob m) {
        if (m.enraged) return;
        for (MobDef.MobSkillDef s : m.skills) {
            if (!"enrage".equals(s.type())) continue;
            Params p = s.params();
            if (m.hp / m.stats.maxHp() <= p.dbl("threshold", 0.3)) {
                m.enraged = true;
                m.enrageDamage = p.dbl("damage_mult", 1.3);
                m.enrageSpeed = p.dbl("speed_mult", 1.15);
                MobFx.particle(Particle.ANGRY_VILLAGER, m.location().add(0, m.entity.getHeight() + 0.3, 0), 6, 0.4, 0.2, 0.4, 0);
                m.sound("hurt", 1.2f);
                play(m.location(), "minecraft:entity.ravager.roar", 0.5f, 1.5f);
                m.refreshNameplate();
            }
            return;
        }
    }

    /** 스폰 직후: 위장(ambush) 설정. */
    static void onSpawn(LabMob m) {
        for (MobDef.MobSkillDef s : m.skills) {
            if (!"ambush".equals(s.type())) continue;
            Params p = s.params();
            m.ambushing = true;
            m.ambushRevealRange = p.dbl("reveal_range", 4);
            m.pendingFirstHitMult = p.dbl("first_hit_mult", 1.8);
            m.rig.setHidden(true);
            String fx = p.str("disguise_fx");
            if (fx != null) {
                Location at = m.entity.getLocation();
                m.disguise = m.service.fx().flat(fx, at.clone().add(0, 0.5, 0), 1f, 1f, at.getYaw());
            }
            if (m.entity.isAware()) m.entity.getPathfinder().stopPathfinding();
            return;
        }
    }

    static void checkAmbush(LabMob m) {
        if (!m.enemiesNear(m.location(), m.ambushRevealRange).isEmpty()) revealAmbush(m);
    }

    static void revealAmbush(LabMob m) {
        if (!m.ambushing) return;
        m.ambushing = false;
        if (m.disguise != null) {
            m.service.fx().discard(m.disguise);
            m.disguise = null;
        }
        m.rig.setHidden(false);
        Location c = m.location();
        MobFx.particle(Particle.POOF, c.clone().add(0, 0.6, 0), 18, 0.4, 0.4, 0.4, 0.05);
        play(c, "minecraft:entity.silverfish.ambient", 1f, 0.6f);
        m.nextAttack = m.service.now();
        MobAi.selectTarget(m, m.service.now());
    }

    /** 사망 시: explode_on_death · split_on_death. */
    static void onDeath(LabMob m, Location at) {
        for (MobDef.MobSkillDef s : m.skills) {
            Params p = s.params();
            if ("explode_on_death".equals(s.type())) {
                double r = p.dbl("radius", 2.5);
                int delay = Math.max(6, (int) Math.round(p.dbl("delay", 0.5) * 20));
                Location c = ground(at);
                MobFx.Shape shape = MobFx.Shape.circle(c, r);
                double dmg = m.damage() * p.dbl("damage", 1.0);
                String effect = p.str("effect");
                m.service.fx().telegraph(shape, delay, MobFx.ORANGE, null, () -> {
                    MobFx.particle(Particle.EXPLOSION, c.clone().add(0, 0.5, 0), 2, 0.3, 0.2, 0.3, 0);
                    play(c, "minecraft:entity.generic.explode", 0.8f, 1.3f);
                    for (LivingEntity e : m.victimsNear(c, r + 1)) {
                        if (!shape.contains(e.getLocation())) continue;
                        hit(m, e, dmg, DamageType.MAGIC, "explode_on_death", 0);
                        if (effect != null) effect(m, e, effect, p.dbl("effect_duration", 3), p.dbl("amount", 0), c);
                    }
                });
            } else if ("split_on_death".equals(s.type())) {
                String mobId = p.str("mob");
                int count = Math.max(1, p.integer("count", 2));
                if (mobId == null || m.services.content().mob(mobId) == null) continue;
                Player tt = m.lastDamager == null ? null : Bukkit.getPlayer(m.lastDamager);
                for (int i = 0; i < count; i++) {
                    double a = 2 * Math.PI * i / count;
                    Location l = at.clone().add(Math.cos(a) * 0.8, 0.1, Math.sin(a) * 0.8);
                    if (!l.getBlock().isPassable()) l = at.clone();
                    CustomMob child = m.service.spawn(mobId, l, m.ctx, false);
                    if (child != null) {
                        child.entity().setVelocity(new Vector(Math.cos(a) * 0.3, 0.35, Math.sin(a) * 0.3));
                        if (tt != null) child.addThreat(tt, 1);
                    }
                }
                MobFx.particle(Particle.ITEM_SLIME, at.clone().add(0, 0.5, 0), 16, 0.4, 0.3, 0.4, 0.05);
            }
        }
    }
}
