package kr.labyrinth.mobs;

import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.MobDef;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * 몹 AI 타입 (GDD §9.3): melee · ranged · caster · charger · swarm · turret + flying(비행형 선회).
 * 바닐라 목표(goal)는 스폰 때 전부 제거하고, 길찾기만 Paper Pathfinder 로 쓴다. 공격·스킬은 전부 여기/스킬 코드에서.
 */
final class MobAi {

    private MobAi() {}

    static final double AGGRO_RANGE = 14;
    static final double AGGRO_RANGE_NO_LOS = 5;

    static void tick(LabMob m, long now) {
        // 대상 갱신
        if ((now + (m.seed & 7)) % 10 == 0 || m.target() == null) selectTarget(m, now);
        Player t = m.target();
        boolean stunned = m.services.effects().isStunned(m.entity);
        if (t == null) {
            idle(m, now);
            return;
        }
        Location loc = m.entity.getLocation();
        Location tl = t.getLocation();
        double dist = horizontal(loc, tl);
        face(m, t, now);
        if (stunned) {
            stop(m);
            return;
        }
        if (m.flying) fly(m, t, now);
        if (now < m.busyUntil) return;
        if (now < m.staggerUntil) {
            stop(m);
            return;
        }
        if (now >= m.globalSkillReady && (now + (m.seed & 3)) % 4 == 0 && MobSkills.tryCast(m, t, now)) return;

        String ai = m.def.ai() == null ? "melee" : m.def.ai();
        boolean rooted = m.services.effects().isRooted(m.entity);
        switch (ai) {
            case "ranged" -> keepDistance(m, t, dist, 6, 12, now, rooted);
            case "caster" -> keepDistance(m, t, dist, 8, 14, now, rooted);
            case "turret" -> { }
            default -> {
                if (!m.flying && !rooted) {
                    if (dist > reach(m) * 0.8) moveTo(m, tl, now);
                    else stop(m);
                } else if (rooted) stop(m);
            }
        }
        basicAttack(m, t, dist, now);
        // 가끔 울음소리
        if (ThreadLocalRandom.current().nextInt(160) == 0) m.sound("ambient", 0.7f);
    }

    // ── 대상 선택 ────────────────────────────────────────────────────────

    static void selectTarget(LabMob m, long now) {
        if (now % 20 == 0) m.threat.prune(m::validTarget);
        UUID top = m.threat.top(now, m::validTarget);
        if ("swarm".equals(m.def.ai()) && !m.threat.isTaunted(now)) {
            // 떼: 덜 몰린 파티원 쪽으로 분산
            UUID best = null;
            int bestCount = Integer.MAX_VALUE;
            for (Player p : m.enemiesNear(m.location(), AGGRO_RANGE)) {
                int c = m.service.targetCount(p.getUniqueId(), m);
                if (c < bestCount || (c == bestCount && top != null && p.getUniqueId().equals(top))) {
                    best = p.getUniqueId();
                    bestCount = c;
                }
            }
            if (best != null) top = best;
        }
        if (top == null) {
            Player nearest = null;
            double bestD = Double.MAX_VALUE;
            Location loc = m.location();
            for (Player p : m.enemiesNear(loc, AGGRO_RANGE)) {
                double d = p.getLocation().distanceSquared(loc);
                boolean see = d <= AGGRO_RANGE_NO_LOS * AGGRO_RANGE_NO_LOS || m.entity.hasLineOfSight(p);
                if (see && d < bestD) {
                    bestD = d;
                    nearest = p;
                }
            }
            if (nearest != null) {
                m.threat.add(nearest.getUniqueId(), 1);
                top = nearest.getUniqueId();
            }
        }
        m.targetId = top;
    }

    // ── 이동 ─────────────────────────────────────────────────────────────

    static double horizontal(Location a, Location b) {
        return Math.sqrt(Geometry.dist2(a.getX(), a.getZ(), b.getX(), b.getZ()));
    }

    static double reach(LabMob m) {
        return 1.3 + m.entity.getWidth() / 2 + 0.3 * Math.max(1, m.stats.scale());
    }

    static double speedMult(LabMob m) {
        long now = m.service.now();
        double s = (now < m.buffUntil ? m.buffSpeed : 1) * (m.enraged ? m.enrageSpeed : 1);
        if (m.services.effects().has(m.entity, "slow")) s *= 0.6;
        if ("swarm".equals(m.def.ai())) s *= 1.15;
        return s;
    }

    static void moveTo(LabMob m, Location goal, long now) {
        if (m.flying || !m.entity.isAware()) return;
        boolean far = m.lastPathGoal == null || m.lastPathGoal.getWorld() != goal.getWorld()
                || m.lastPathGoal.distanceSquared(goal) > 2.25;
        if (far || now - m.lastRepath >= 10 || !m.entity.getPathfinder().hasPath()) {
            m.entity.getPathfinder().moveTo(goal, speedMult(m));
            m.lastRepath = now;
            m.lastPathGoal = goal.clone();
        }
    }

    static void stop(LabMob m) {
        if (!m.flying && m.entity.isAware()) m.entity.getPathfinder().stopPathfinding();
        m.lastPathGoal = null;
    }

    private static void keepDistance(LabMob m, Player t, double dist, double min, double max, long now, boolean rooted) {
        if (m.flying || rooted) return;
        Location loc = m.entity.getLocation();
        boolean see = m.entity.hasLineOfSight(t);
        if (dist < min - 1) {
            Vector away = loc.toVector().subtract(t.getLocation().toVector()).setY(0);
            if (away.lengthSquared() < 1e-4) away = new Vector(1, 0, 0);
            away.normalize().multiply(5);
            moveTo(m, loc.clone().add(away), now);
        } else if (dist > max || !see) {
            moveTo(m, t.getLocation(), now);
        } else if ((now + m.seed) % 60 == 0) {
            // 옆걸음 (가만히 서 있는 과녁이 되지 않게)
            Vector side = t.getLocation().toVector().subtract(loc.toVector()).setY(0);
            if (side.lengthSquared() > 1e-4) {
                side.normalize();
                side = new Vector(-side.getZ(), 0, side.getX()).multiply(ThreadLocalRandom.current().nextBoolean() ? 3 : -3);
                moveTo(m, loc.clone().add(side), now);
            }
        } else if (m.entity.getPathfinder().hasPath() && dist >= min && dist <= max && (now - m.lastRepath) > 30) {
            stop(m);
        }
    }

    /** 비행형: 대상 머리 위 1.5~3칸에서 선회 (근접형은 공격 때 내려옴). */
    private static void fly(LabMob m, Player t, long now) {
        Location loc = m.entity.getLocation();
        boolean ranged = "ranged".equals(m.def.ai()) || "caster".equals(m.def.ai()) || "turret".equals(m.def.ai());
        m.flyAngle += ((m.seed & 1) == 0 ? 0.035 : -0.035);
        double r = ranged ? 5.5 : 1.8;
        double h = (ranged ? 2.6 : 1.7) + 0.5 * Math.sin(now / 25.0 + m.seed);
        Location tl = t.getLocation();
        Location want;
        if (!ranged && now >= m.nextAttack - 6 && horizontal(loc, tl) < 4) {
            want = tl.clone().add(0, 0.9, 0); // 급강하
        } else {
            want = tl.clone().add(Math.cos(m.flyAngle) * r, h, Math.sin(m.flyAngle) * r);
        }
        steer(m, want);
    }

    static void steer(LabMob m, Location want) {
        if (m.services.effects().isRooted(m.entity)) {
            m.entity.setVelocity(new Vector());
            return;
        }
        Vector v = want.toVector().subtract(m.entity.getLocation().toVector());
        double max = Math.max(0.08, m.def.speed() * speedMult(m) * 1.1);
        if (v.length() > max) v.normalize().multiply(max);
        Vector cur = m.entity.getVelocity();
        m.entity.setVelocity(cur.multiply(0.35).add(v.multiply(0.65)));
    }

    private static void idle(LabMob m, long now) {
        if (now % 20 == 0) m.threat.decay(0.97);
        if (m.flying) {
            Location want = m.home.clone().add(0, 1.2 + 0.4 * Math.sin(now / 30.0 + m.seed), 0);
            steer(m, want);
        } else if (m.entity.getLocation().distanceSquared(m.home) > 16 * 16) {
            moveTo(m, m.home, now);
        } else if (m.lastPathGoal != null && m.entity.getLocation().distanceSquared(m.home) < 4) {
            stop(m);
        }
        m.headYaw *= 0.8f;
        m.headPitch *= 0.8f;
    }

    /** 몸·머리 방향: 움직이는 중이면 진행 방향, 아니면 대상 쪽으로 부드럽게. */
    static void face(LabMob m, Player t, long now) {
        Location loc = m.entity.getLocation();
        Location tl = t.getLocation();
        float toTarget = Geometry.yawOf(tl.getX() - loc.getX(), tl.getZ() - loc.getZ());
        float desired;
        double dist = horizontal(loc, tl);
        if (m.moveSpeed > 0.04 && dist > 4 && !m.flying) desired = loc.getYaw();
        else desired = toTarget;
        float diff = (float) Geometry.wrapDegrees(desired - m.bodyYaw);
        float step = now < m.busyUntil ? 9f : 18f;
        m.bodyYaw += Math.max(-step, Math.min(step, diff));
        m.bodyYaw = (float) Geometry.wrapDegrees(m.bodyYaw);
        m.headYaw = (float) Geometry.wrapDegrees(toTarget - m.bodyYaw);
        double dy = (tl.getY() + 1.4) - m.eye().getY();
        m.headPitch = (float) Math.max(-20, Math.min(20, -Math.toDegrees(Math.atan2(dy, Math.max(0.5, dist)))));
    }

    // ── 기본 공격 ────────────────────────────────────────────────────────

    static int attackInterval(LabMob m) {
        int base = (int) Math.round(m.def.raw().dbl("attack_interval", 1.2) * 20);
        if ("swarm".equals(m.def.ai())) base = (int) (base * 0.85);
        return Math.max(8, base);
    }

    private static void basicAttack(LabMob m, Player t, double dist, long now) {
        if (now < m.nextAttack) return;
        String ai = m.def.ai() == null ? "melee" : m.def.ai();
        boolean rangedAi = ai.equals("ranged") || ai.equals("caster") || ai.equals("turret");
        double d3 = m.entity.getLocation().distance(t.getLocation());
        double reach = reach(m);
        if (d3 <= reach + (m.flying ? 0.8 : 0.3) && Math.abs(t.getLocation().getY() - m.entity.getLocation().getY()) < 2.8) {
            melee(m, t, now);
            return;
        }
        if (rangedAi && dist <= 15 && m.entity.hasLineOfSight(t)) rangedBasic(m, t, now, ai.equals("caster"));
    }

    static void melee(LabMob m, Player t, long now) {
        m.attackTick = now;
        m.attackArm = (m.attackArm + 1) % 2;
        m.nextAttack = now + attackInterval(m);
        UUID tid = t.getUniqueId();
        Bukkit.getScheduler().runTaskLater(m.services.plugin(), () -> {
            if (!m.isAlive()) return;
            Player p = Bukkit.getPlayer(tid);
            if (p == null || !m.validTarget(p)) return;
            if (m.entity.getLocation().distance(p.getLocation()) > reach(m) + 1.0) return;
            double mult = m.pendingFirstHitMult;
            m.pendingFirstHitMult = 1;
            if (m.service.now() < m.stealthUntil) MobSkills.endStealth(m);
            m.services.damage().deal(DamageContext.raw(m.entity, p, m.damage() * mult, DamageType.MELEE).source("basic_attack"));
            MobFx.particle(Particle.SWEEP_ATTACK, p.getLocation().add(0, 1, 0), 1, 0, 0, 0, 0);
        }, 3L);
    }

    private static void rangedBasic(LabMob m, Player t, long now, boolean magic) {
        m.castTick = now;
        m.nextAttack = now + Math.max(30, attackInterval(m) + 16);
        String fx = basicFx(m.def);
        Location from = m.eye();
        Vector dir = t.getLocation().add(0, 1.1, 0).toVector().subtract(from.toVector());
        MobFx.ProjectileSpec spec = new MobFx.ProjectileSpec(fx, 0.75, 0, 0, 0.45, 40,
                fx == null ? (magic ? Particle.ENCHANT : Particle.CRIT) : null);
        double dmg = m.damage() * 0.75;
        DamageType type = magic ? DamageType.MAGIC : DamageType.RANGED;
        m.service.fx().projectile(from, dir, spec, null, m::validTarget,
                (p, at) -> m.services.damage().deal(DamageContext.raw(m.entity.isValid() ? m.entity : null, p, dmg, type)
                        .source("basic_ranged")),
                at -> MobFx.particle(Particle.SMOKE, at, 3, 0.05, 0.05, 0.05, 0.01));
    }

    /** 기본 원거리 공격 모델 = 첫 projectile 스킬의 fx. */
    static String basicFx(MobDef def) {
        for (MobDef.MobSkillDef s : def.skills()) {
            if ("projectile".equals(s.type()) && s.params().has("fx")) return s.params().str("fx");
        }
        return null;
    }
}
