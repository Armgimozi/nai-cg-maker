package kr.labyrinth.items.weaponskills;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.combat.HealthPool;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Log;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec.Effect;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec.Part;
import org.bukkit.Color;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 조합형 무기 스킬 실행기 (<code>id: mechanics</code>, GDD §17.5). {@link MechanicsSpec} 이 파싱한 부품 트리를
 * 실제 세계에서 돌린다. 모든 피해는 {@code DamageContext.attack(...)}(DamageService 단일 경로), 상태이상은
 * StatusEffectService, 적/아군 판정은 {@link WeaponTargeting}(→ TargetFilter), 연출은 fx 모델(ItemDisplay) 또는 입자.
 * 미궁 밖 블록은 절대 바꾸지 않는다(낙뢰는 연출 전용 strikeLightningEffect, 폭발은 입자+판정만).
 */
final class MechanicsEngine {

    private MechanicsEngine() {}

    /** params(불변, 리로드 때 새 객체) → 파싱 결과. */
    private static final Map<Params, MechanicsSpec.Result> CACHE = Collections.synchronizedMap(new WeakHashMap<>());

    static void register(Map<String, WeaponSkill> r) {
        r.put("mechanics", MechanicsEngine::cast);
    }

    static MechanicsSpec.Result spec(Params p) {
        return CACHE.computeIfAbsent(p, k -> MechanicsSpec.parse(k.get("mechanics")));
    }

    static void cast(SkillCast c) {
        MechanicsSpec.Result res = spec(c.p);
        if (!res.ok()) {
            Log.warnOnce("mech-" + c.weapon.id() + c.skill.input(),
                    "[무기 스킬] " + c.weapon.id() + " " + c.skill.input() + " mechanics 오류: " + res.problems().getFirst());
        }
        if (res.parts().isEmpty()) return;
        new Run(c, res).list(res.parts(), 0, new Ctx(null, null));
    }

    /** 문맥: at = 기준 위치(null = 시전자의 현재 위치), target = 현재 대상. */
    record Ctx(Location at, LivingEntity target) {}

    /** 시전 한 번. */
    static final class Run {
        final SkillCast c;
        final Player pl;
        final double power;
        final String source;
        final Color color;

        Run(SkillCast c, MechanicsSpec.Result res) {
            this.c = c;
            this.pl = c.player;
            double charge = c.charge();
            double p = c.num("power", 1.0);
            if (charge >= 0) p *= Math.max(0.35, charge);
            this.power = p;
            this.source = "mech:" + c.weapon.id() + ":" + c.skill.input();
            // 입자 색: params.fx 가 있으면 그 모델, 없으면 스킬이 쓰는 첫 fx 모델의 팔레트 (테마 색을 따라감)
            String firstFx = res.displays().stream().filter(d -> Fx.exists(c.services, d)).findFirst().orElse(null);
            this.color = c.p.has("fx") || firstFx == null ? c.color() : Fx.color(c.services, firstFx);
        }

        // ── 실행 ───────────────────────────────────────────────────────

        void list(List<Part> parts, int from, Ctx ctx) {
            for (int i = from; i < parts.size(); i++) {
                Part part = parts.get(i);
                if (part.type().equals("delay")) {
                    int ticks = part.p().has("ticks") ? part.integer("ticks", 10) : SkillCast.ticks(part.num("seconds", 0.5));
                    List<Part> inner = part.child("mechanics");
                    if (!inner.isEmpty()) {
                        c.later(ticks, () -> alive(() -> list(inner, 0, ctx)));
                        continue;
                    }
                    final int next = i + 1;
                    c.later(ticks, () -> alive(() -> list(parts, next, ctx)));
                    return;
                }
                try {
                    part(part, ctx);
                } catch (Throwable t) {
                    Log.error("조합형 무기 스킬 부품 오류: " + part.type() + " (" + c.weapon.id() + ")", t);
                }
            }
        }

        void alive(Runnable r) {
            if (pl.isOnline() && !pl.isDead()) r.run();
        }

        void part(Part p, Ctx ctx) {
            switch (p.type()) {
                case "cone" -> cone(p, ctx);
                case "nova" -> nova(p, ctx);
                case "projectile" -> projectile(p, ctx);
                case "beam" -> beam(p, ctx);
                case "dash" -> dash(p, ctx);
                case "leap" -> leap(p, ctx);
                case "blink" -> blink(p, ctx);
                case "rain" -> rain(p, ctx);
                case "strike" -> strike(p, ctx);
                case "chain" -> chain(p, ctx);
                case "zone" -> zone(p, ctx);
                case "orbit" -> orbit(p, ctx);
                case "vortex" -> vortex(p, ctx);
                case "summon" -> summon(p, ctx);
                case "self" -> allyEffects(p.effects(), pl, 1.0);
                case "target" -> {
                    LivingEntity t = target(ctx, p.num("range", 14));
                    if (t != null) enemyEffects(p.effects(), t, pl.getLocation(), 1.0);
                }
                case "party" -> {
                    Location at = anchor(p, ctx, "self");
                    for (Player a : c.allies(at, p.num("radius", 10))) {
                        allyEffects(p.effects().isEmpty() ? p.allyEffects() : p.effects(), a, 1.0);
                        spawn(p.str("particle", null), a.getLocation().add(0, 1, 0), 10, 0.4, 0.02);
                    }
                }
                case "repeat" -> {
                    int times = Math.max(1, p.integer("times", 2));
                    int interval = Math.max(1, p.integer("interval", 5));
                    List<Part> inner = p.child("mechanics");
                    for (int k = 0; k < times; k++) {
                        if (k == 0) list(inner, 0, ctx);
                        else c.later(k * interval, () -> alive(() -> list(inner, 0, ctx)));
                    }
                }
                case "sound" -> {
                    Location at = anchor(p, ctx, "origin");
                    playSound(at, p.str("sound", null), (float) p.num("volume", 1.0), (float) p.num("pitch", 1.0));
                }
                case "particle" -> {
                    Location at = anchor(p, ctx, "origin").add(0, p.num("y", 1.0), 0);
                    spawn(p.str("particle", null), at, p.integer("count", 20), p.num("spread", 0.5), p.num("speed", 0.05));
                }
                case "velocity" -> {
                    Vector v = c.flatLook().multiply(p.num("forward", 0)).setY(p.num("upward", 0));
                    pl.setVelocity(v);
                    c.service.noFall(pl, 60);
                }
                case "say" -> c.service.bar(pl, p.str("text", ""), 40);
                default -> { }
            }
        }

        // ── 위치·대상 ──────────────────────────────────────────────────

        Location here(Ctx ctx) {
            return ctx.at() != null ? ctx.at().clone() : pl.getLocation();
        }

        Location anchor(Part p, Ctx ctx, String def) {
            // at 생략: 하위 문맥(착지·착탄·끝 지점) 안에서는 그 지점, 최상위에서는 부품별 기본값
            String at = p.str("at", null);
            if (at == null) at = ctx.at() != null ? "origin" : def;
            return switch (at) {
                case "self" -> pl.getLocation();
                case "aim" -> c.targetPoint(p.num("range", 16));
                case "target" -> {
                    LivingEntity t = target(ctx, p.num("range", 16));
                    yield t != null ? t.getLocation() : c.targetPoint(p.num("range", 16));
                }
                default -> here(ctx);
            };
        }

        /** 지금 대상 → 시선 → 앞쪽 가까운 적. */
        LivingEntity target(Ctx ctx, double range) {
            if (ctx.target() != null && c.targets().isEnemy(pl, ctx.target())) return ctx.target();
            LivingEntity t = c.targets().firstInSight(pl, range, 0.8);
            if (t != null) return t;
            List<LivingEntity> cone = c.targets().enemiesInCone(pl, pl.getLocation(), c.flatLook(), range, 70);
            return cone.isEmpty() ? null : cone.getFirst();
        }

        // ── 효과 ───────────────────────────────────────────────────────

        DamageType type(Effect e) {
            String t = e.p().str("damage_type");
            if (t != null) return DamageType.byId(t, c.type());
            if (e.p().bool("magic", false)) return DamageType.MAGIC;
            return c.type();
        }

        boolean isBoss(LivingEntity e) { return c.isBoss(e); }

        double hpRatio(LivingEntity e) {
            if (e instanceof Player p) {
                double max = c.services.stats().maxHp(p);
                return max <= 0 ? 1 : c.services.stats().currentHp(p) / max;
            }
            HealthPool pool = c.services.damage().poolOf(e).orElse(null);
            if (pool != null) return pool.maxHealth() <= 0 ? 1 : pool.health() / pool.maxHealth();
            var a = e.getAttribute(org.bukkit.attribute.Attribute.MAX_HEALTH);
            return a == null ? 1 : e.getHealth() / a.getValue();
        }

        /** 적 하나에 효과 목록. scale = 피해 배율(연쇄 감쇠 등). 피해가 들어갔으면 true. */
        boolean enemyEffects(List<Effect> effects, LivingEntity t, Location origin, double scale) {
            if (t == null || !c.targets().isEnemy(pl, t)) return false;
            double dealt = 0;
            boolean landed = effects.stream().noneMatch(e -> e.type().equals("damage") || e.type().equals("percent"));
            for (Effect e : effects) {
                if (t.isDead() && !e.type().equals("heal_caster") && !e.type().equals("lifesteal")) break;
                Params p = e.p();
                boolean boss = isBoss(t);
                switch (e.type()) {
                    case "damage" -> {
                        DamageContext d = DamageContext.attack(pl, t, e.amount(1.0) * power * scale, type(e)).skill(source);
                        if (p.has("knockback") && !boss) d.knockback(p.dbl("knockback", 0));
                        if (p.bool("ignore_defense", false)) d.ignoreDefense();
                        c.services.damage().deal(d);
                        if (!d.cancelled() && !d.evaded()) {
                            dealt += d.dealt();
                            landed = true;
                        }
                    }
                    case "percent" -> {
                        double pct = boss ? p.dbl("boss_amount", e.amount(0.05) * 0.1) : e.amount(0.05);
                        DamageContext d = DamageContext.percent(pl, t, pct * Math.min(1, scale)).skill(source);
                        c.services.damage().deal(d);
                        if (!d.cancelled() && !d.evaded()) {
                            dealt += d.dealt();
                            landed = true;
                        }
                    }
                    case "ignite" -> status(t, "burn", e.amount(3), p.dbl("potency", 0));
                    case "slow" -> status(t, "slow", e.amount(2), p.dbl("potency", 0.35));
                    case "poison" -> status(t, "poison", e.amount(4), p.dbl("potency", 0));
                    case "bleed" -> status(t, "bleed", e.amount(4), p.dbl("potency", 0));
                    case "wither" -> {
                        status(t, "bleed", e.amount(4), p.dbl("potency", 0));
                        status(t, "weaken", e.amount(4), p.dbl("weaken", 0.12));
                    }
                    case "freeze" -> status(t, "frost", e.amount(3), p.dbl("stacks", 1));
                    case "stun" -> { if (!boss) status(t, "stun", e.amount(1), 0); }
                    case "root" -> { if (!boss) status(t, "root", e.amount(1.5), 0); }
                    case "glow" -> status(t, "mark", e.amount(4), p.dbl("potency", 0.1));
                    case "effect" -> {
                        String id = p.str("id", "weaken");
                        if (!(boss && (id.equals("stun") || id.equals("root")))) {
                            status(t, id, p.dbl("seconds", e.amount(3)), p.dbl("potency", 0));
                        }
                    }
                    case "taunt" -> c.taunt(t, e.amount(3));
                    case "knockback" -> push(t, origin, boss ? p.dbl("boss_amount", 0) : e.amount(0.8));
                    case "pull" -> c.pull(t, origin, e.amount(0.8), p.dbl("boss_amount", 0));
                    case "launch" -> c.launch(t, e.amount(0.6), p.dbl("boss_amount", 0));
                    case "execute" -> {
                        double th = p.dbl("threshold", 0.25);
                        if (hpRatio(t) <= th) {
                            double m = boss ? p.dbl("boss_amount", e.amount(2.0) * 0.4) : e.amount(2.0);
                            DamageContext d = DamageContext.attack(pl, t, m * power, type(e)).skill(source).critBonus(1.0);
                            c.services.damage().deal(d);
                            if (!d.cancelled()) dealt += d.dealt();
                            t.getWorld().spawnParticle(Particle.DAMAGE_INDICATOR, t.getLocation().add(0, t.getHeight(), 0), 8, 0.3, 0.2, 0.3, 0.1);
                            t.getWorld().playSound(t.getLocation(), Sound.ENTITY_PLAYER_ATTACK_CRIT, 1f, 0.6f);
                        }
                    }
                    case "lightning" -> {
                        t.getWorld().strikeLightningEffect(t.getLocation());
                        if (e.amount(0) > 0) {
                            DamageContext d = DamageContext.attack(pl, t, e.amount(0) * power * scale, DamageType.MAGIC).skill(source);
                            c.services.damage().deal(d);
                            if (!d.cancelled() && !d.evaded()) dealt += d.dealt();
                        }
                    }
                    case "explosion" -> {
                        Location at = t.getLocation().add(0, t.getHeight() / 2, 0);
                        at.getWorld().spawnParticle(Particle.EXPLOSION, at, 2, 0.4, 0.4, 0.4, 0);
                        at.getWorld().playSound(at, Sound.ENTITY_GENERIC_EXPLODE, 0.6f, 1.2f);
                        double r = p.dbl("radius", 2.5);
                        if (e.amount(0) > 0) {
                            for (LivingEntity o : c.enemies(at, r)) {
                                DamageContext d = DamageContext.attack(pl, o, e.amount(0) * power * scale, type(e)).skill(source);
                                c.services.damage().deal(d);
                            }
                        }
                    }
                    case "particle" -> spawn(p.str("particle", p.str("amount")), t.getLocation().add(0, t.getHeight() / 2, 0),
                            p.integer("count", 10), p.dbl("spread", 0.3), p.dbl("speed", 0.05));
                    case "sound" -> playSound(t.getLocation(), p.str("sound", p.str("amount")), (float) p.dbl("volume", 1),
                            (float) p.dbl("pitch", 1));
                    case "lifesteal" -> { if (dealt > 0) c.services.damage().heal(pl, dealt * e.amount(0.2), true); }
                    case "heal_caster" -> c.heal(pl, e.amount(0.05), p.dbl("power", 0.3));
                    case "mana" -> c.services.classes().restoreMana(pl, c.services.classes().maxMana(pl) * e.amount(0.05));
                    default -> { }
                }
            }
            return landed;
        }

        void status(LivingEntity t, String id, double seconds, double potency) {
            if (seconds > 0) c.services.effects().apply(t, id, seconds, potency, pl);
        }

        void push(LivingEntity t, Location origin, double strength) {
            if (strength <= 0 || c.services.effects().isKnockbackImmune(t)) return;
            Vector d = t.getLocation().toVector().subtract(origin.toVector()).setY(0);
            if (d.lengthSquared() < 1e-4) d = c.flatLook();
            d.normalize().multiply(Math.min(2.5, strength));
            d.setY(Math.min(0.6, 0.18 + strength * 0.12));
            t.setVelocity(t.getVelocity().multiply(0.3).add(d));
        }

        /** 아군(플레이어) 하나에 효과 목록. 적 전용 효과는 건너뛴다. */
        void allyEffects(List<Effect> effects, Player a, double scale) {
            if (a == null || a.isDead()) return;
            for (Effect e : effects) {
                Params p = e.p();
                switch (e.type()) {
                    case "heal" -> c.heal(a, e.amount(0.1) * scale, p.dbl("power", 0.5) * scale);
                    case "heal_caster" -> c.heal(pl, e.amount(0.05), p.dbl("power", 0.3));
                    case "absorption" -> c.service.shield(a, c.services.stats().maxHp(a) * e.amount(0.15) * scale
                            + c.services.stats().get(pl).healPower() * p.dbl("power", 0), p.dbl("seconds", 6));
                    case "cleanse" -> c.services.effects().cleanse(a);
                    case "buff" -> {
                        Map<String, Double> m = new LinkedHashMap<>();
                        Params st = p.sub("stats");
                        for (String k : st.keys()) m.put(k, st.dbl(k, 0));
                        if (!m.isEmpty()) c.services.effects().applyBuff(a, m, p.dbl("seconds", 6), source + ":" + p.str("tag", "buff"));
                    }
                    case "potion" -> {
                        String name = p.str("effect", p.str("amount"));
                        String key = name == null ? null : MechanicsSpec.POTION_BUFFS.get(name);
                        if (key != null) {
                            double v = p.dbl("value", 0.1 * (1 + p.dbl("amplifier", 0)));
                            c.services.effects().applyBuff(a, Map.of(key, v), p.dbl("seconds", 6), source + ":" + name);
                        }
                    }
                    case "mana" -> c.services.classes().restoreMana(a, c.services.classes().maxMana(a) * e.amount(0.05));
                    case "particle" -> spawn(p.str("particle", p.str("amount")), a.getLocation().add(0, 1, 0),
                            p.integer("count", 10), p.dbl("spread", 0.4), p.dbl("speed", 0.05));
                    case "sound" -> playSound(a.getLocation(), p.str("sound", p.str("amount")), (float) p.dbl("volume", 1),
                            (float) p.dbl("pitch", 1));
                    default -> { }
                }
            }
        }

        // ── 부품: 도형 ─────────────────────────────────────────────────

        void cone(Part p, Ctx ctx) {
            Location origin = anchor(p, ctx, "origin");
            double range = p.num("range", 4);
            double angle = p.num("angle", 90);
            Vector dir = c.flatLook();
            List<LivingEntity> hits = c.targets().enemiesInCone(pl, origin, dir, range, angle);
            for (LivingEntity t : hits) enemyEffects(p.effects(), t, origin, 1.0);
            // 연출: 검기 모델 + 호 입자
            String fx = display(p);
            if (fx != null) {
                Location l = origin.clone().add(0, 1.0, 0).add(dir.clone().multiply(Math.min(1.5, range * 0.35)));
                l.setDirection(dir);
                Fx.spawn(c.services, l, fx, (float) (p.num("display_scale", 1.0) * Math.max(1.0, range / 2.2)), 8);
            }
            String part = p.str("particle", null);
            int pts = (int) Math.max(6, angle / 8);
            for (int i = 0; i <= pts; i++) {
                double a = -angle / 2 + angle * i / pts;
                Vector v = dir.clone().rotateAroundY(Math.toRadians(a));
                for (double r = range * 0.45; r <= range; r += Math.max(0.8, range / 3)) {
                    spawn(part, origin.clone().add(0, 1.0, 0).add(v.clone().multiply(r)), 1, 0.05, 0.01);
                }
            }
        }

        void nova(Part p, Ctx ctx) {
            Location center = anchor(p, ctx, "origin");
            double radius = p.num("radius", 3);
            int expand = Math.max(0, p.integer("expand_ticks", 0));
            String fx = display(p);
            Location ground = SkillCast.ground(center, 4).add(0, 0.05, 0);
            if (fx != null) {
                double base = Fx.modelLength(c.services, fx, 0) / 2.0;
                float full = (float) (p.num("display_scale", 1.0) * radius / Math.max(0.1, base));
                ItemDisplay d = Fx.spawn(c.services, ground, fx, expand > 0 ? full * 0.15f : full, expand + 12);
                if (d != null && expand > 0) c.later(1, () -> Fx.transform(d, 0, full, full, full, expand));
            }
            String part = p.str("particle", null);
            if (expand <= 0) {
                for (LivingEntity t : c.enemies(center, radius)) enemyEffects(p.effects(), t, center, 1.0);
                ringParticles(part, ground.clone().add(0, 0.2, 0), radius);
                spawn(part, center.clone().add(0, 1, 0), (int) (radius * 6), radius / 3, 0.05);
                return;
            }
            Set<UUID> hit = new HashSet<>();
            c.repeat(1, expand, t -> {
                double r = radius * t / expand;
                for (LivingEntity e : c.enemies(center, r)) {
                    if (hit.add(e.getUniqueId())) enemyEffects(p.effects(), e, center, 1.0);
                }
                ringParticles(part, ground.clone().add(0, 0.2, 0), r);
                return true;
            }, null);
        }

        void projectile(Part p, Ctx ctx) {
            int count = Math.max(1, p.integer("count", 1));
            double spread = p.num("spread", count > 1 ? 20 : 0);
            int interval = Math.max(0, p.integer("interval", 0));
            for (int i = 0; i < count; i++) {
                final int idx = i;
                Runnable fire = () -> {
                    Vector base = c.look();
                    double ang = count == 1 ? 0 : interval > 0 ? (ThreadLocalRandom.current().nextDouble() - 0.5) * spread
                            : -spread / 2 + spread * idx / (count - 1);
                    Location start = ctx.at() != null ? ctx.at().clone().add(0, 1.0, 0)
                            : pl.getEyeLocation().subtract(0, 0.25, 0).add(base.clone().multiply(0.5));
                    fly(p, ctx, start, base.clone().rotateAroundY(Math.toRadians(ang)));
                };
                if (interval <= 0 || i == 0) fire.run();
                else c.later(interval * i, () -> alive(fire));
            }
        }

        private void fly(Part p, Ctx ctx, Location start, Vector dir) {
            double speed = Math.max(0.2, p.num("speed", 1.2));
            double range = p.num("range", 20);
            double homing = p.num("homing", 0);
            double gravity = p.num("gravity", 0);
            double hitR = p.num("hit_radius", 0.8);
            boolean ground = p.flag("ground", false);
            Object pv = p.p().get("pierce");
            int pierce = pv instanceof Boolean b ? (b ? Integer.MAX_VALUE : 0) : Math.max(0, p.integer("pierce", 0));
            String part = p.str("particle", null);
            int pc = p.integer("particle_count", 2);
            double ps = p.num("particle_spread", 0.08);
            Vector vel = dir.clone().normalize().multiply(speed);
            if (ground) vel.setY(0);
            Location cur = start.clone();
            if (ground) cur = SkillCast.ground(cur, 4).add(0, 0.3, 0);
            Location face = cur.clone();
            face.setDirection(vel.lengthSquared() < 1e-6 ? c.flatLook() : vel);
            String fx = display(p);
            ItemDisplay d = fx == null ? null : Fx.spawn(c.services, face, fx, (float) p.num("display_scale", 1.0), 0);
            Set<UUID> hit = new HashSet<>();
            int[] left = {pierce};
            double[] travelled = {0};
            float[] spin = {0};
            Location[] pos = {cur};
            int maxTicks = (int) Math.ceil(range / speed) + 30;
            c.repeat(1, maxTicks, t -> {
                Location now = pos[0];
                if (homing > 0) {
                    LivingEntity tgt = nearestAhead(now, vel, 10);
                    if (tgt != null) {
                        Vector want = tgt.getBoundingBox().getCenter().subtract(now.toVector()).normalize().multiply(speed);
                        vel.multiply(1 - homing).add(want.multiply(homing)).normalize().multiply(speed);
                    }
                }
                if (!ground) vel.setY(vel.getY() - gravity);
                Location next = now.clone().add(vel);
                if (ground) {
                    Location g = SkillCast.ground(next.clone().add(0, 1.0, 0), 4);
                    if (!SkillCast.standable(g)) {
                        impact(p, ctx, now, d);
                        return false;
                    }
                    next = g.add(0, 0.3, 0);
                } else {
                    RayTraceResult block = now.getWorld().rayTraceBlocks(now, vel, vel.length(), FluidCollisionMode.NEVER, true);
                    if (block != null) {
                        Location at = block.getHitPosition().toLocation(now.getWorld()).subtract(vel.clone().normalize().multiply(0.2));
                        hitAlong(p, now, at, hitR, hit, left);
                        impact(p, ctx, at, d);
                        return false;
                    }
                }
                if (!hitAlong(p, now, next, hitR, hit, left)) {
                    impact(p, ctx, next, d);
                    return false;
                }
                pos[0] = next;
                travelled[0] += vel.length();
                if (d != null && d.isValid()) {
                    Location l = next.clone();
                    l.setDirection(vel.lengthSquared() < 1e-6 ? c.flatLook() : vel);
                    d.teleport(l);
                    if (p.num("spin", 0) != 0) {
                        spin[0] += (float) Math.toRadians(p.num("spin", 0));
                        float s = (float) p.num("display_scale", 1.0);
                        d.setTransformation(new Transformation(new Vector3f(), new Quaternionf().rotateZ(spin[0]),
                                new Vector3f(s, s, s), new Quaternionf()));
                    }
                }
                if (part != null) spawn(part, next, pc, ps, 0.01);
                else if (d == null) Fx.dust(next, color, 1.2f, 2, 0.08);
                if (travelled[0] >= range) {
                    if (p.flag("impact_at_end", true)) impact(p, ctx, next, d);
                    else if (d != null) d.remove();
                    return false;
                }
                return true;
            }, () -> { if (d != null && d.isValid()) d.remove(); });
        }

        /** 선분 위 적 맞히기 — 관통이 남았으면 true, 멈춰야 하면 false. */
        private boolean hitAlong(Part p, Location a, Location b, double hitR, Set<UUID> hit, int[] left) {
            for (LivingEntity e : c.targets().enemiesInLine(pl, a, b, hitR * 2)) {
                if (!hit.add(e.getUniqueId())) continue;
                enemyEffects(p.effects(), e, a, 1.0);
                if (left[0]-- <= 0) return false;
            }
            return true;
        }

        private void impact(Part p, Ctx ctx, Location at, ItemDisplay d) {
            if (d != null && d.isValid()) d.remove();
            spawn(p.str("impact_particle", null), at, 12, 0.3, 0.05);
            Ctx inner = new Ctx(at.clone(), ctx.target());
            list(p.child("explode"), 0, inner);
            list(p.child("on_impact"), 0, inner);
        }

        private LivingEntity nearestAhead(Location from, Vector vel, double range) {
            LivingEntity best = null;
            double bestD = Double.MAX_VALUE;
            Vector f = vel.clone().normalize();
            for (LivingEntity e : c.enemies(from, range)) {
                Vector to = e.getBoundingBox().getCenter().subtract(from.toVector());
                double dist = to.length();
                if (dist < 1e-3 || to.normalize().dot(f) < 0.3) continue;
                if (dist < bestD) {
                    bestD = dist;
                    best = e;
                }
            }
            return best;
        }

        void beam(Part p, Ctx ctx) {
            int duration = SkillCast.ticks(p.num("duration", 0));
            int interval = Math.max(1, p.integer("interval", 5));
            if (p.num("duration", 0) <= 0) {
                fireBeam(p, ctx);
                return;
            }
            fireBeam(p, ctx);
            c.repeat(interval, duration, t -> {
                fireBeam(p, ctx);
                return true;
            }, null);
        }

        private void fireBeam(Part p, Ctx ctx) {
            double length = p.num("length", 16);
            double width = p.num("width", 1.0);
            Location from = ctx.at() != null ? ctx.at().clone().add(0, 1.2, 0) : pl.getEyeLocation().subtract(0, 0.2, 0);
            Vector dir = c.look();
            Location to = from.clone().add(dir.clone().multiply(length));
            if (!p.flag("through_walls", false)) {
                RayTraceResult r = from.getWorld().rayTraceBlocks(from, dir, length, FluidCollisionMode.NEVER, true);
                if (r != null) to = r.getHitPosition().toLocation(from.getWorld());
            }
            for (LivingEntity e : c.targets().enemiesInLine(pl, from, to, width)) enemyEffects(p.effects(), e, from, 1.0);
            line(p.str("particle", null), from, to, 0.35, width / 4);
            if (p.str("core", null) != null) line(p.str("core", null), from, to, 0.6, 0.02);
            String fx = display(p);
            if (fx != null) {
                double len = from.distance(to);
                Location mid = from.clone().add(to.clone().subtract(from).multiply(0.5));
                mid.setDirection(dir);
                double unit = Fx.modelLength(c.services, fx, 2);
                float s = (float) (p.num("display_scale", 1.0) * Math.max(0.6, width));
                ItemDisplay d = Fx.spawn(c.services, mid, fx, 1f, 8);
                if (d != null) {
                    d.setTransformation(new Transformation(new Vector3f(), new Quaternionf(),
                            new Vector3f(s, s, (float) (len / Math.max(0.1, unit))), new Quaternionf()));
                }
            }
            list(p.child("on_end"), 0, new Ctx(to.clone(), ctx.target()));
        }

        // ── 부품: 이동 ─────────────────────────────────────────────────

        void dash(Part p, Ctx ctx) {
            double distance = p.num("distance", 6);
            int ticks = Math.max(2, p.integer("ticks", 5));
            double width = p.num("width", 2.0);
            double perTick = distance / ticks;
            Vector dir = c.flatLook();
            if (p.flag("invulnerable", true)) c.service.invulnerable(pl, ticks + 4);
            c.service.noFall(pl, 40);
            Set<UUID> hit = new HashSet<>();
            Location[] last = {pl.getLocation()};
            String part = p.str("particle", null);
            c.repeat(1, ticks, t -> {
                pl.setVelocity(dir.clone().multiply(perTick).setY(MovementSkills.onGround(pl) ? 0.0 : -0.1));
                Location now = pl.getLocation();
                for (LivingEntity e : c.targets().enemiesInLine(pl, last[0].clone().add(0, 1, 0), now.clone().add(0, 1, 0), width)) {
                    if (hit.add(e.getUniqueId())) enemyEffects(p.effects(), e, now, 1.0);
                }
                last[0] = now;
                if (part != null) spawn(part, now.clone().add(0, 1, 0), 4, 0.3, 0.02);
                else Fx.dust(now.clone().add(0, 1, 0), color, 1.4f, 5, 0.3);
                return true;
            }, () -> c.later(1, () -> alive(() -> {
                Location now = pl.getLocation();
                for (LivingEntity e : c.targets().enemiesInLine(pl, last[0].clone().add(0, 1, 0), now.clone().add(0, 1, 0), width)) {
                    if (hit.add(e.getUniqueId())) enemyEffects(p.effects(), e, now, 1.0);
                }
                pl.setVelocity(dir.clone().multiply(0.15));
                String fx = display(p);
                if (fx != null) {
                    Location l = now.clone().add(0, 1, 0);
                    l.setDirection(dir);
                    Fx.spawn(c.services, l, fx, (float) (p.num("display_scale", 1.0) * Math.max(1, width / 2)), 8);
                }
                list(p.child("on_end"), 0, new Ctx(now, ctx.target()));
            })));
        }

        void leap(Part p, Ctx ctx) {
            Vector v = c.flatLook().multiply(p.num("forward", 0.6)).setY(p.num("upward", 0.9));
            pl.setVelocity(v);
            c.service.noFall(pl, 100);
            String part = p.str("particle", null);
            c.repeat(1, 70, t -> {
                Location now = pl.getLocation();
                if (part != null) spawn(part, now.clone().add(0, 0.5, 0), 2, 0.2, 0.01);
                else Fx.dust(now.clone().add(0, 0.5, 0), color, 1.2f, 2, 0.2);
                if (t > 1 && pl.getVelocity().getY() < 0.05) pl.setVelocity(pl.getVelocity().add(new Vector(0, -0.04, 0)));
                return !(t > 4 && MovementSkills.onGround(pl));
            }, () -> alive(() -> {
                pl.setFallDistance(0);
                list(p.child("land"), 0, new Ctx(pl.getLocation(), ctx.target()));
            }));
        }

        void blink(Part p, Ctx ctx) {
            double distance = p.num("distance", 6);
            Location from = pl.getLocation();
            Location dest = null;
            if (p.flag("behind", false)) {
                LivingEntity t = target(ctx, distance + 6);
                if (t != null) {
                    Vector f = t.getLocation().getDirection().setY(0);
                    if (f.lengthSquared() < 1e-4) f = t.getLocation().toVector().subtract(from.toVector()).setY(0);
                    f.normalize();
                    Location behind = t.getLocation().clone().subtract(f.multiply(Math.max(1.2, t.getWidth() / 2 + 0.9)));
                    behind.setDirection(t.getLocation().toVector().subtract(behind.toVector()));
                    if (SkillCast.standable(behind)) dest = behind;
                }
            }
            if (dest == null) {
                Vector dir = c.flatLook();
                Location best = from.clone();
                for (double s = 0.5; s <= distance; s += 0.5) {
                    Location l = from.clone().add(dir.clone().multiply(s));
                    if (!SkillCast.standable(l)) break;
                    best = l;
                }
                dest = best;
                dest.setYaw(from.getYaw());
                dest.setPitch(from.getPitch());
            }
            String part = p.str("particle", "REVERSE_PORTAL");
            spawn(part, from.clone().add(0, 1, 0), 24, 0.35, 0.05);
            pl.teleport(dest);
            c.service.noFall(pl, 20);
            spawn(part, dest.clone().add(0, 1, 0), 24, 0.35, 0.05);
            String fx = display(p);
            if (fx != null) Fx.spawn(c.services, from.clone().add(0, 1, 0), fx, (float) p.num("display_scale", 1.0), 12);
        }

        // ── 부품: 하늘·연쇄 ────────────────────────────────────────────

        void rain(Part p, Ctx ctx) {
            Location center = anchor(p, ctx, "aim");
            int count = Math.max(1, p.integer("count", 8));
            double radius = p.num("radius", 4);
            int interval = Math.max(0, p.integer("interval", 3));
            double height = p.num("height", 12);
            double speed = Math.max(0.3, p.num("speed", 1.0));
            double impactR = p.num("impact_radius", 2);
            String fx = display(p);
            for (int i = 0; i < count; i++) {
                Runnable drop = () -> {
                    Location at = center.clone();
                    if (count > 1 && radius > 0) {
                        double a = ThreadLocalRandom.current().nextDouble(Math.PI * 2);
                        double r = Math.sqrt(ThreadLocalRandom.current().nextDouble()) * radius;
                        at.add(Math.cos(a) * r, 0, Math.sin(a) * r);
                    }
                    Location g = SkillCast.ground(at.clone().add(0, 2, 0), 8);
                    ringParticles("DUST:" + hex(color) + ":0.9", g.clone().add(0, 0.15, 0), impactR);
                    Location top = g.clone().add(0, height, 0);
                    top.setDirection(new Vector(0, -1, 0.0001));
                    ItemDisplay d = fx == null ? null : Fx.spawn(c.services, top, fx, (float) p.num("display_scale", 1.0), 0);
                    Location[] pos = {top};
                    int max = (int) Math.ceil(height / speed) + 2;
                    c.repeat(1, max, t -> {
                        Location n = pos[0].clone().subtract(0, speed, 0);
                        if (n.getY() <= g.getY() + 0.2) {
                            if (d != null) d.remove();
                            for (LivingEntity e : c.enemies(g, impactR)) enemyEffects(p.effects(), e, g, 1.0);
                            spawn(p.str("impact_particle", "EXPLOSION"), g.clone().add(0, 0.4, 0), 3, impactR / 3, 0.02);
                            g.getWorld().playSound(g, Sound.ENTITY_GENERIC_EXPLODE, 0.35f, 1.6f);
                            list(p.child("on_impact"), 0, new Ctx(g.clone(), ctx.target()));
                            return false;
                        }
                        pos[0] = n;
                        if (d != null && d.isValid()) d.teleport(n);
                        String tr = p.str("particle", null);
                        if (tr != null) spawn(tr, n, 2, 0.1, 0.01);
                        else if (d == null) Fx.dust(n, color, 1.5f, 3, 0.12);
                        return true;
                    }, () -> { if (d != null && d.isValid()) d.remove(); });
                };
                if (interval <= 0 || i == 0) drop.run();
                else c.later(interval * i, () -> alive(drop));
            }
        }

        void strike(Part p, Ctx ctx) {
            Location center = anchor(p, ctx, "aim");
            int count = Math.max(1, p.integer("count", 1));
            double radius = p.num("radius", 0);
            int interval = Math.max(0, p.integer("interval", 0));
            double impactR = p.num("impact_radius", 2);
            String visual = p.str("visual", "lightning");
            List<Location> points = new ArrayList<>();
            if (p.flag("targets", false)) {
                for (LivingEntity e : c.enemies(center, Math.max(radius, 1))) {
                    if (points.size() >= count) break;
                    points.add(e.getLocation());
                }
            }
            while (points.size() < count) {
                Location at = center.clone();
                if (radius > 0 && (count > 1 || points.size() > 0)) {
                    double a = ThreadLocalRandom.current().nextDouble(Math.PI * 2);
                    double r = Math.sqrt(ThreadLocalRandom.current().nextDouble()) * radius;
                    at.add(Math.cos(a) * r, 0, Math.sin(a) * r);
                }
                points.add(at);
            }
            String fx = display(p);
            for (int i = 0; i < points.size(); i++) {
                Location at = SkillCast.ground(points.get(i).clone().add(0, 1.5, 0), 6);
                Runnable hit = () -> {
                    switch (visual) {
                        case "lightning" -> at.getWorld().strikeLightningEffect(at);
                        case "pillar" -> {
                            if (fx != null) {
                                // 기둥 모델(세로로 긴 모델)은 그대로, Z 로 긴 광선 모델은 위를 보게 세운다
                                boolean lengthwise = Fx.modelLength(c.services, fx, 2) > Fx.modelLength(c.services, fx, 1) * 1.5;
                                Location l = at.clone().add(0, lengthwise ? 3.0 : 1.5, 0);
                                if (lengthwise) l.setPitch(-90);
                                float s = (float) p.num("display_scale", 1.0);
                                ItemDisplay d = Fx.spawn(c.services, l, fx, s, 14);
                                if (d != null && lengthwise) {
                                    d.setTransformation(new Transformation(new Vector3f(), new Quaternionf(),
                                            new Vector3f(s, s, (float) (6.0 / Fx.modelLength(c.services, fx, 2))), new Quaternionf()));
                                }
                            }
                            for (double y = 0; y < 6; y += 0.4) spawn(p.str("particle", "END_ROD"), at.clone().add(0, y, 0), 2, 0.15, 0.01);
                            at.getWorld().playSound(at, Sound.BLOCK_BEACON_POWER_SELECT, 0.6f, 1.6f);
                        }
                        default -> { }
                    }
                    if (!visual.equals("pillar") && p.str("particle", null) != null) {
                        spawn(p.str("particle", null), at.clone().add(0, 0.5, 0), 20, impactR / 2, 0.05);
                    }
                    for (LivingEntity e : c.enemies(at, impactR)) enemyEffects(p.effects(), e, at, 1.0);
                    list(p.child("on_impact"), 0, new Ctx(at.clone(), ctx.target()));
                };
                if (interval <= 0 || i == 0) hit.run();
                else c.later(interval * i, () -> alive(hit));
            }
        }

        void chain(Part p, Ctx ctx) {
            int jumps = Math.max(1, p.integer("jumps", 4));
            double range = p.num("range", 6);
            double falloff = p.num("falloff", 0.85);
            int interval = Math.max(1, p.integer("interval", 2));
            LivingEntity first;
            Location start;
            if (ctx.at() != null) { // 착탄 지점 등에서 시작: 그 지점에서 가장 가까운 적
                start = ctx.at().clone().add(0, 0.8, 0);
                List<LivingEntity> near = c.enemies(ctx.at(), p.num("first_range", 6));
                first = near.isEmpty() ? null : near.getFirst();
            } else {
                start = pl.getEyeLocation().subtract(0, 0.3, 0);
                first = target(ctx, p.num("first_range", 14));
            }
            if (first == null) {
                spawn(p.str("particle", "ELECTRIC_SPARK"), ctx.at() != null ? start : pl.getEyeLocation().add(c.look().multiply(2)),
                        10, 0.2, 0.05);
                return;
            }
            Set<UUID> hit = new HashSet<>();
            LivingEntity[] cur = {first};
            Location[] from = {start};
            double[] scale = {1.0};
            String part = p.str("particle", "ELECTRIC_SPARK");
            Runnable step = new Runnable() {
                int k = 0;

                @Override
                public void run() {
                    LivingEntity t = cur[0];
                    if (t == null || !t.isValid()) return;
                    hit.add(t.getUniqueId());
                    Location to = t.getLocation().add(0, t.getHeight() / 2, 0);
                    line(part, from[0], to, 0.3, 0.05);
                    enemyEffects(p.effects(), t, from[0], scale[0]);
                    from[0] = to;
                    scale[0] *= falloff;
                    k++;
                    if (k > jumps) return;
                    LivingEntity next = null;
                    for (LivingEntity e : c.enemies(to, range)) {
                        if (!hit.contains(e.getUniqueId())) {
                            next = e;
                            break;
                        }
                    }
                    if (next == null) return;
                    cur[0] = next;
                    c.later(interval, () -> alive(this));
                }
            };
            step.run();
        }

        // ── 부품: 지속형 ───────────────────────────────────────────────

        void zone(Part p, Ctx ctx) {
            Location start = anchor(p, ctx, "self");
            double radius = p.num("radius", 4);
            int duration = SkillCast.ticks(p.num("duration", 5));
            int interval = Math.max(1, p.integer("interval", 10));
            boolean follow = p.flag("follow", false);
            Location[] center = {SkillCast.ground(start, 4)};
            String fx = display(p);
            ItemDisplay d = null;
            if (fx != null) {
                double w = Fx.modelLength(c.services, fx, 0);
                float s = (float) (p.num("display_scale", 1.0) * 2 * radius / Math.max(0.1, w));
                d = Fx.spawn(c.services, center[0].clone().add(0, 0.06, 0), fx, s, duration + 2);
            }
            ItemDisplay disp = d;
            String part = p.str("particle", null);
            String ring = p.str("ring", null);
            c.repeat(1, duration, t -> {
                if (follow) {
                    center[0] = pl.getLocation();
                    if (disp != null && disp.isValid()) disp.teleport(center[0].clone().add(0, 0.06, 0));
                }
                Location cc = center[0];
                if (t % 4 == 0) {
                    if (ring != null) ringParticles(ring, cc.clone().add(0, 0.15, 0), radius);
                    else if (disp == null) ringParticles("DUST:" + hex(color) + ":1.0", cc.clone().add(0, 0.15, 0), radius);
                    if (part != null) {
                        double a = ThreadLocalRandom.current().nextDouble(Math.PI * 2);
                        double r = ThreadLocalRandom.current().nextDouble() * radius;
                        spawn(part, cc.clone().add(Math.cos(a) * r, 0.4, Math.sin(a) * r), 3, 0.2, 0.02);
                    }
                }
                if (t % interval == 0) {
                    for (LivingEntity e : c.enemies(cc, radius)) enemyEffects(p.effects(), e, cc, 1.0);
                    if (!p.allyEffects().isEmpty()) for (Player a : c.allies(cc, radius)) allyEffects(p.allyEffects(), a, 1.0);
                }
                return true;
            }, () -> {
                if (disp != null && disp.isValid()) disp.remove();
                alive(() -> list(p.child("end"), 0, new Ctx(center[0].clone(), ctx.target())));
            });
        }

        void orbit(Part p, Ctx ctx) {
            int count = Math.max(1, p.integer("count", 3));
            double radius = p.num("radius", 2);
            int duration = SkillCast.ticks(p.num("duration", 5));
            double speed = p.num("speed", 18);
            double hitR = p.num("hit_radius", 1.0);
            int hitCd = Math.max(1, p.integer("hit_cooldown", 10));
            String fx = display(p);
            String part = p.str("particle", null);
            List<ItemDisplay> blades = new ArrayList<>();
            if (fx != null) {
                for (int i = 0; i < count; i++) {
                    ItemDisplay d = Fx.spawn(c.services, pl.getLocation().add(0, 1, 0), fx, (float) p.num("display_scale", 0.8), 0);
                    if (d != null) blades.add(d);
                }
            }
            Map<UUID, Integer> last = new HashMap<>();
            c.repeat(1, duration, t -> {
                Location center = pl.getLocation().add(0, 1.0, 0);
                for (int i = 0; i < count; i++) {
                    double a = Math.toRadians(speed * t + 360.0 * i / count);
                    Location at = center.clone().add(Math.cos(a) * radius, Math.sin(t * 0.15 + i) * 0.15, Math.sin(a) * radius);
                    if (i < blades.size() && blades.get(i).isValid()) {
                        Location l = at.clone();
                        l.setDirection(new Vector(-Math.sin(a), 0, Math.cos(a)));
                        blades.get(i).teleport(l);
                    } else if (part != null) {
                        spawn(part, at, 1, 0.02, 0);
                    } else {
                        Fx.dust(at, color, 1.3f, 2, 0.05);
                    }
                    for (LivingEntity e : c.enemies(at, hitR)) {
                        Integer prev = last.get(e.getUniqueId());
                        if (prev != null && t - prev < hitCd) continue;
                        last.put(e.getUniqueId(), t);
                        enemyEffects(p.effects(), e, center, 1.0);
                    }
                }
                return true;
            }, () -> blades.forEach(b -> { if (b.isValid()) b.remove(); }));
        }

        void vortex(Part p, Ctx ctx) {
            Location center = SkillCast.ground(anchor(p, ctx, "aim"), 6);
            double radius = p.num("radius", 6);
            int duration = SkillCast.ticks(p.num("duration", 3));
            double strength = p.num("strength", 0.3);
            double bossStrength = p.num("boss_strength", 0);
            int interval = Math.max(1, p.integer("interval", 10));
            String fx = display(p);
            ItemDisplay d = null;
            if (fx != null) {
                double w = Fx.modelLength(c.services, fx, 0);
                d = Fx.spawn(c.services, center.clone().add(0, 0.08, 0), fx,
                        (float) (p.num("display_scale", 1.0) * 2 * radius / Math.max(0.1, w)), duration + 2);
            }
            ItemDisplay disp = d;
            String part = p.str("particle", null);
            Location pull = center.clone().add(0, 0.5, 0);
            c.repeat(1, duration, t -> {
                if (t % 2 == 0) {
                    for (LivingEntity e : c.enemies(center, radius)) c.pull(e, pull, strength, bossStrength);
                }
                if (t % interval == 0) for (LivingEntity e : c.enemies(center, radius)) enemyEffects(p.effects(), e, pull, 1.0);
                for (int k = 0; k < 3; k++) {
                    double a = Math.toRadians(t * 24 + k * 120);
                    double r = radius * (1 - (t % 20) / 20.0);
                    Location at = center.clone().add(Math.cos(a) * r, 0.3 + (t % 20) * 0.08, Math.sin(a) * r);
                    if (part != null) spawn(part, at, 1, 0.05, 0.01);
                    else Fx.dust(at, color, 1.2f, 1, 0.02);
                }
                if (disp != null && disp.isValid()) Fx.transform(disp, (float) Math.toRadians(-t * 18),
                        disp.getTransformation().getScale().x(), disp.getTransformation().getScale().y(),
                        disp.getTransformation().getScale().z(), 1);
                return true;
            }, () -> {
                if (disp != null && disp.isValid()) disp.remove();
                alive(() -> list(p.child("end"), 0, new Ctx(center.clone(), ctx.target())));
            });
        }

        /** 정령 소환: 시전자 곁을 떠도는 빛(모델/입자)이 interval 마다 가까운 적을 쏜다. */
        void summon(Part p, Ctx ctx) {
            int count = Math.max(1, Math.min(6, p.integer("count", 2)));
            int duration = SkillCast.ticks(p.num("duration", 10));
            int interval = Math.max(5, p.integer("interval", 20));
            double range = p.num("range", 10);
            List<Effect> effects = p.effects().isEmpty()
                    ? List.of(new Effect("damage", Params.of(Map.of("amount", 0.5)))) : p.effects();
            String fx = display(p);
            String part = p.str("particle", null);
            List<ItemDisplay> spirits = new ArrayList<>();
            if (fx != null) {
                for (int i = 0; i < count; i++) {
                    ItemDisplay d = Fx.spawn(c.services, pl.getLocation().add(0, 2, 0), fx, (float) p.num("display_scale", 0.9), 0);
                    if (d != null) spirits.add(d);
                }
            }
            c.repeat(1, duration, t -> {
                Location base = pl.getLocation();
                List<Location> at = new ArrayList<>();
                for (int i = 0; i < count; i++) {
                    double a = Math.toRadians(t * 4 + 360.0 * i / count);
                    Location l = base.clone().add(Math.cos(a) * 1.4, 2.0 + Math.sin(t * 0.1 + i) * 0.25, Math.sin(a) * 1.4);
                    at.add(l);
                    if (i < spirits.size() && spirits.get(i).isValid()) spirits.get(i).teleport(l);
                    else if (t % 2 == 0) {
                        if (part != null) spawn(part, l, 1, 0.03, 0);
                        else Fx.dust(l, color, 1.4f, 1, 0.03);
                    }
                }
                if (t % interval == 0) {
                    List<LivingEntity> near = c.enemies(base, range);
                    for (int i = 0; i < count && !near.isEmpty(); i++) {
                        LivingEntity e = near.get(i % near.size());
                        Location to = e.getLocation().add(0, e.getHeight() / 2, 0);
                        line(part != null ? part : "DUST:" + hex(color) + ":0.8", at.get(i), to, 0.3, 0.02);
                        enemyEffects(effects, e, at.get(i), 1.0);
                    }
                    if (!near.isEmpty()) base.getWorld().playSound(base, Sound.ENTITY_ALLAY_ITEM_THROWN, 0.5f, 1.6f);
                }
                return true;
            }, () -> spirits.forEach(s -> { if (s.isValid()) s.remove(); }));
        }

        // ── 연출 헬퍼 ──────────────────────────────────────────────────

        String display(Part p) {
            String d = p.str("display", null);
            return d != null && Fx.exists(c.services, d) ? d : null;
        }

        void ringParticles(String spec, Location center, double radius) {
            if (radius <= 0.05) return;
            int points = (int) Math.max(8, Math.min(64, radius * 8));
            for (int i = 0; i < points; i++) {
                double a = Math.PI * 2 * i / points;
                Location l = center.clone().add(Math.cos(a) * radius, 0, Math.sin(a) * radius);
                if (spec != null) spawn(spec, l, 1, 0.02, 0);
                else Fx.dust(l, color, 1.1f, 1, 0.02);
            }
        }

        void line(String spec, Location from, Location to, double step, double spread) {
            Vector d = to.toVector().subtract(from.toVector());
            double len = d.length();
            if (len < 1e-4) return;
            d.multiply(1.0 / len);
            for (double s = 0; s <= len; s += step) {
                Location l = from.clone().add(d.clone().multiply(s));
                if (spec != null) spawn(spec, l, 1, spread, 0);
                else Fx.dust(l, color, 1.0f, 1, spread);
            }
        }

        void spawn(String spec, Location at, int count, double spread, double speed) {
            if (spec == null || spec.isBlank() || at.getWorld() == null || count <= 0) return;
            Pfx fx = Pfx.of(spec, color);
            if (fx == null) return;
            at.getWorld().spawnParticle(fx.type(), at, count, spread, spread, spread, speed, fx.data(), false);
        }

        void playSound(Location at, String key, float volume, float pitch) {
            if (key == null || key.isBlank() || at.getWorld() == null) return;
            at.getWorld().playSound(at, key.toLowerCase(java.util.Locale.ROOT), volume, pitch);
        }
    }

    static String hex(Color c) {
        return String.format("#%06x", c.asRGB());
    }

    /** 입자 표기 "NAME[:인자…]" → (Particle, data). DUST:#rrggbb:크기 · DUST_COLOR_TRANSITION:#a:#b:크기 · BLOCK:재질 · ITEM:재질. */
    record Pfx(Particle type, Object data) {
        private static final Map<String, Pfx> CACHE = new ConcurrentHashMap<>();
        private static final Pfx NONE = new Pfx(Particle.CRIT, null);

        static Pfx of(String spec, Color fallback) {
            String key = spec.indexOf(':') < 0 && spec.toUpperCase(java.util.Locale.ROOT).startsWith("DUST")
                    ? spec + "@" + fallback.asRGB() : spec;
            Pfx p = CACHE.computeIfAbsent(key, k -> parse(spec, fallback));
            return p == NONE ? null : p;
        }

        private static Pfx parse(String spec, Color fallback) {
            String[] a = spec.trim().split(":");
            Particle type;
            try {
                type = Particle.valueOf(a[0].trim().toUpperCase(java.util.Locale.ROOT));
            } catch (IllegalArgumentException e) {
                Log.warnOnce("pfx-" + a[0], "[무기 스킬] 알 수 없는 입자: " + spec);
                return NONE;
            }
            Class<?> dt = type.getDataType();
            try {
                if (dt == Void.class) return new Pfx(type, null);
                if (dt == Particle.DustOptions.class) {
                    Color col = a.length > 1 ? Fx.parseColor(a[1], fallback) : fallback;
                    float size = a.length > 2 ? Float.parseFloat(a[2]) : 1.2f;
                    return new Pfx(type, new Particle.DustOptions(col, size));
                }
                if (dt == Particle.DustTransition.class) {
                    Color c1 = a.length > 1 ? Fx.parseColor(a[1], fallback) : fallback;
                    Color c2 = a.length > 2 ? Fx.parseColor(a[2], Color.WHITE) : Color.WHITE;
                    float size = a.length > 3 ? Float.parseFloat(a[3]) : 1.2f;
                    return new Pfx(type, new Particle.DustTransition(c1, c2, size));
                }
                if (dt == BlockData.class) {
                    Material m = a.length > 1 ? Material.matchMaterial(a[1]) : null;
                    if (m == null || !m.isBlock()) m = Material.STONE;
                    return new Pfx(type, m.createBlockData());
                }
                if (dt == ItemStack.class) {
                    Material m = a.length > 1 ? Material.matchMaterial(a[1]) : null;
                    if (m == null || !m.isItem()) m = Material.PAPER;
                    return new Pfx(type, new ItemStack(m));
                }
                if (dt == Color.class) return new Pfx(type, a.length > 1 ? Fx.parseColor(a[1], fallback) : fallback);
                if (dt == Float.class) return new Pfx(type, a.length > 1 ? Float.parseFloat(a[1]) : 1.0f);
                if (dt == Integer.class) return new Pfx(type, a.length > 1 ? Integer.parseInt(a[1]) : 0);
            } catch (RuntimeException e) {
                Log.warnOnce("pfx-bad-" + spec, "[무기 스킬] 입자 인자 오류: " + spec);
                return NONE;
            }
            Log.warnOnce("pfx-type-" + a[0], "[무기 스킬] 지원하지 않는 입자 데이터(" + dt.getSimpleName() + "): " + spec);
            return NONE;
        }
    }

    /** 테스트·명령용: 이 문자열이 유효한 입자 이름인가. */
    static boolean knownParticle(String name) {
        try {
            Particle.valueOf(name);
            return true;
        } catch (IllegalArgumentException e) {
            return false;
        }
    }
}
