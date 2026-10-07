package kr.souls.skill;

import kr.souls.Lang;
import kr.souls.util.Fx;
import kr.souls.util.P;
import io.papermc.paper.datacomponent.DataComponentTypes;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.BiFunction;
import java.util.logging.Logger;

/**
 * 스킬을 이루는 부품들. skills.yml 의 mechanics 목록 한 줄이 여기 클래스 하나다.
 * 무기 스킬과 몬스터 스킬이 같은 부품을 쓰고, 누가 맞는지는 Targets 가 시전자 편에 따라 정한다.
 */
public final class Mechanics {
    private static Logger log = Logger.getLogger("Soulslike");
    public static final String FX_TAG = "souls_fx";

    /**
     * 적 스킬의 summon 부품이 부르는 적 만들기 (적 id, 자리 → 만든 몸, 못 만들면 null).
     * 적 등록부가 생기면 (M1) 거기서 바꿔 끼운다. 그 전에는 아무것도 만들지 않는다.
     */
    private static BiFunction<String, Location, LivingEntity> enemySpawner = (id, at) -> null;

    private Mechanics() {}

    public static void setLogger(Logger l) { log = l; }

    public static void setEnemySpawner(BiFunction<String, Location, LivingEntity> f) {
        enemySpawner = f == null ? (id, at) -> null : f;
    }

    public static List<Mechanic> parseList(List<Map<?, ?>> raw) {
        List<Mechanic> out = new ArrayList<>();
        for (Map<?, ?> m : raw) {
            try {
                Mechanic mech = parse(new P(m));
                if (mech != null) out.add(mech);
            } catch (Exception e) {
                log.warning("스킬 부품 해석 실패: " + m + " (" + e.getMessage() + ")");
            }
        }
        return out;
    }

    public static Mechanic parse(P p) {
        String type = p.s("type", "").toLowerCase(Locale.ROOT);
        return switch (type) {
            case "cone", "arc", "slash" -> new Cone(p);
            case "nova", "circle", "shockwave" -> new Nova(p);
            case "projectile", "missile" -> new Projectile(p);
            case "beam", "ray" -> new Beam(p);
            case "dash" -> new Dash(p);
            case "leap", "jump" -> new Leap(p);
            case "blink", "teleport" -> new Blink(p);
            case "rain", "meteor" -> new Rain(p);
            case "strike" -> new Strike(p);
            case "chain" -> new Chain(p);
            case "zone", "field" -> new Zone(p);
            case "orbit" -> new Orbit(p);
            case "vortex", "pull" -> new Vortex(p);
            case "self" -> new SelfFx(p);
            case "target" -> new TargetFx(p);
            case "party", "aura" -> new Party(p);
            case "summon" -> new Summon(p);
            case "repeat" -> new Repeat(p);
            case "delay" -> new Delay(p);
            case "sound" -> new SoundM(p);
            case "particle" -> new ParticleM(p);
            case "say", "message" -> new Say(p);
            case "skill" -> new SkillRef(p);
            case "velocity", "push_self" -> new Velocity(p);
            default -> {
                log.warning("알 수 없는 스킬 부품 type: " + type);
                yield null;
            }
        };
    }

    // ------------------------------------------------------------------ 공통

    static List<HitEffect> effects(P p, String key) {
        return HitEffects.parseList(p.maps(key));
    }

    static void runAll(List<Mechanic> list, SkillContext ctx) {
        if (list == null) return;
        for (Mechanic m : list) {
            try {
                m.run(ctx);
            } catch (Exception e) {
                log.warning("스킬 실행 중 오류: " + e);
            }
        }
    }

    static boolean solid(Location l) {
        Block b = l.getBlock();
        return b.getType().isSolid() && !b.isPassable();
    }

    /** 발밑 depth 칸 안에 밟을 블록이 있는지. 공허로 몸을 던지는 스킬을 막는 데 쓴다. */
    static boolean grounded(Location l, int depth) {
        World w = l.getWorld();
        if (w == null) return false;
        int x = l.getBlockX(), z = l.getBlockZ(), y = l.getBlockY();
        for (int i = 0; i <= depth; i++) {
            if (y - i < w.getMinHeight()) return false;
            Block b = w.getBlockAt(x, y - i, z);
            if (b.getType().isSolid() || b.isLiquid()) return true;
        }
        return false;
    }

    /**
     * 디스플레이에 띄울 아이템 글 (skyblock CustomItems 대신 쓰는 작은 해석기).
     * "souls:fx/blade" 처럼 souls 이름공간이면 그 item_model 을 씌운 종이, 아니면 바닐라 재료 이름 ("IRON_SWORD", "minecraft:bone").
     */
    static ItemStack item(String spec) {
        String s = spec.trim();
        if (s.startsWith(kr.souls.Keys.NS + ":")) {
            ItemStack it = ItemStack.of(Material.PAPER);
            it.setData(DataComponentTypes.ITEM_MODEL, Key.key(s));
            return it;
        }
        Material m = Material.matchMaterial(s);
        if (m == null || !m.isItem() || m.isAir()) {
            log.warning("디스플레이 아이템을 알 수 없습니다: " + spec);
            return null;
        }
        return ItemStack.of(m);
    }

    static ItemDisplay display(Location at, String itemSpec, float scale) {
        if (itemSpec == null || itemSpec.isBlank()) return null;
        ItemStack stack = item(itemSpec);
        if (stack == null) return null;
        World w = at.getWorld();
        if (w == null) return null;
        return w.spawn(at, ItemDisplay.class, d -> {
            d.setItemStack(stack);
            d.setPersistent(false);
            d.addScoreboardTag(FX_TAG);
            d.setTeleportDuration(1);
            d.setBrightness(new Display.Brightness(15, 15));
            d.setTransformation(new Transformation(new Vector3f(), new AxisAngle4f(),
                    new Vector3f(scale, scale, scale), new AxisAngle4f()));
        });
    }

    static void hitAround(SkillContext ctx, Location c, double r, List<HitEffect> effects, Set<UUID> already) {
        for (LivingEntity e : Targets.enemiesNear(ctx.caster, c, r)) {
            if (already != null && !already.add(e.getUniqueId())) continue;
            HitEffects.apply(effects, ctx, e, c);
        }
    }

    // ------------------------------------------------------------------ 부채꼴 베기

    static final class Cone implements Mechanic {
        final double range, angle, height;
        final Fx.Spec particle;
        final List<HitEffect> effects;

        Cone(P p) {
            range = p.d("range", 4);
            angle = p.d("angle", 100);
            height = p.d("height", 2.5);
            particle = Fx.parse(p.s("particle", "SWEEP_ATTACK"));
            effects = effects(p, "effects");
        }

        @Override
        public void run(SkillContext ctx) {
            Vector dir = ctx.flatDir();
            double half = Math.toRadians(angle / 2);
            Location base = ctx.caster.getLocation().add(0, Math.min(1.2, ctx.caster.getHeight() * 0.6), 0);
            if (particle != null) {
                double step = Math.toRadians(Math.max(6, 60 / Math.max(1, range)));
                for (double r = range * 0.45; r <= range + 1e-6; r += range * 0.275) {
                    for (double a = -half; a <= half + 1e-6; a += step) {
                        particle.spawn(base.clone().add(dir.clone().rotateAroundY(a).multiply(r)), 1, 0.04, 0);
                    }
                }
            }
            for (LivingEntity e : Targets.enemiesNear(ctx.caster, base, range + 1.5)) {
                double dy = e.getLocation().getY() - ctx.caster.getLocation().getY();
                if (Math.abs(dy) > height) continue;
                Vector flat = e.getLocation().toVector().subtract(base.toVector()).setY(0);
                if (flat.lengthSquared() > 0.5 && flat.angle(dir) > half) continue;
                if (Targets.distToBox(e, base) > range) continue;
                HitEffects.apply(effects, ctx, e, ctx.caster.getLocation());
            }
        }
    }

    // ------------------------------------------------------------------ 원형 폭발 / 퍼지는 충격파

    static final class Nova implements Mechanic {
        final double radius, height, range;
        final int expand;
        final String at;
        final Fx.Spec particle;
        final List<HitEffect> effects;

        Nova(P p) {
            radius = p.d("radius", 4);
            height = p.d("height", 3);
            range = p.d("range", 16);
            expand = p.i("expand_ticks", 0);
            at = p.s("at", "self");
            particle = Fx.parse(p.s("particle", "CLOUD"));
            effects = effects(p, "effects");
        }

        @Override
        public void run(SkillContext ctx) {
            Location c = ctx.center(at, range).add(0, 0.2, 0);
            if (expand <= 0) {
                if (particle != null) {
                    for (double r = radius / 3; r <= radius + 1e-6; r += radius / 3) {
                        Fx.ring(particle, c, r, (int) Math.max(10, r * 9));
                    }
                }
                for (LivingEntity e : Targets.enemiesNear(ctx.caster, c, radius)) {
                    if (Math.abs(e.getLocation().getY() - c.getY()) > height) continue;
                    HitEffects.apply(effects, ctx, e, c);
                }
                return;
            }
            Set<UUID> hit = new HashSet<>();
            new BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    t++;
                    double r = radius * t / expand;
                    if (particle != null) Fx.ring(particle, c, r, (int) Math.max(8, r * 8));
                    for (LivingEntity e : Targets.enemiesNear(ctx.caster, c, r)) {
                        if (Math.abs(e.getLocation().getY() - c.getY()) > height) continue;
                        if (hit.add(e.getUniqueId())) HitEffects.apply(effects, ctx, e, c);
                    }
                    if (t >= expand) cancel();
                }
            }.runTaskTimer(ctx.plugin, 0, 1);
        }
    }

    // ------------------------------------------------------------------ 투사체

    static final class Projectile implements Mechanic {
        final double speed, range, hitRadius, gravity, homing, spread, pSpread, displayScale;
        final int count, pCount;
        final boolean pierce, ground, throughWalls, spin, explodeAtEnd;
        final Fx.Spec particle;
        final String display, hitSound;
        final List<HitEffect> effects;
        final double explodeRadius;
        final Fx.Spec explodeParticle;
        final List<HitEffect> explodeEffects;
        final List<Mechanic> onImpact;

        Projectile(P p) {
            speed = p.d("speed", 1.2);
            range = p.d("range", 28);
            hitRadius = p.d("hit_radius", 0.8);
            gravity = p.d("gravity", 0);
            homing = p.d("homing", 0);
            spread = p.d("spread", 10);
            count = Math.max(1, p.i("count", 1));
            pierce = p.b("pierce", false);
            ground = p.b("ground", false);
            throughWalls = p.b("through_walls", false);
            particle = Fx.parse(p.s("particle", "CRIT"));
            pCount = p.i("particle_count", 2);
            pSpread = p.d("particle_spread", 0.08);
            display = p.s("display", null);
            displayScale = p.d("display_scale", 0.9);
            spin = p.b("spin", false);
            hitSound = p.s("hit_sound", null);
            effects = effects(p, "effects");
            P ex = p.sub("explode");
            if (ex != null) {
                explodeRadius = ex.d("radius", 3);
                explodeParticle = Fx.parse(ex.s("particle", "EXPLOSION"));
                explodeEffects = HitEffects.parseList(ex.maps("effects"));
                explodeAtEnd = ex.b("at_end", true);
            } else {
                explodeRadius = 0;
                explodeParticle = null;
                explodeEffects = List.of();
                explodeAtEnd = false;
            }
            onImpact = parseList(p.maps("on_impact"));
        }

        @Override
        public void run(SkillContext ctx) {
            Vector base = ground ? ctx.flatDir() : ctx.dir();
            for (int i = 0; i < count; i++) {
                double off = count == 1 ? 0 : Math.toRadians((i - (count - 1) / 2.0) * spread);
                Vector d = base.clone().rotateAroundY(off);
                launch(ctx, d);
            }
        }

        void launch(SkillContext ctx, Vector dir) {
            Location start = ground
                    ? ctx.caster.getLocation().add(dir.clone().multiply(1.0)).add(0, 0.15, 0)
                    : ctx.eye().add(dir.clone().multiply(0.8)).add(0, -0.15, 0);
            ItemDisplay disp = display(start, display, (float) displayScale);
            Set<UUID> hit = new HashSet<>();
            new BukkitRunnable() {
                final Location pos = start.clone();
                final Vector vel = dir.clone().multiply(speed);
                double traveled = 0;
                int ticks = 0;
                float spinAngle = 0;

                void finish(Location at, boolean impact) {
                    if (impact || explodeAtEnd) explode(ctx, at);
                    if (impact && !onImpact.isEmpty()) runAll(onImpact, ctx.at(at));
                    if (disp != null) disp.remove();
                    cancel();
                }

                @Override
                public void run() {
                    ticks++;
                    if (ticks > 200 || pos.getWorld() == null) {
                        finish(pos, false);
                        return;
                    }
                    if (homing > 0) steer();
                    int sub = (int) Math.ceil(vel.length() / 0.4);
                    Vector step = vel.clone().multiply(1.0 / sub);
                    for (int s = 0; s < sub; s++) {
                        pos.add(step);
                        traveled += step.length();
                        if (ground && !followGround()) {
                            finish(pos, true);
                            return;
                        }
                        if (!throughWalls && !ground && solid(pos)) {
                            finish(pos.clone().subtract(step), true);
                            return;
                        }
                        for (Entity e : pos.getWorld().getNearbyEntities(pos, hitRadius + 1, hitRadius + 1.5, hitRadius + 1)) {
                            if (!Targets.isEnemy(ctx.caster, e)) continue;
                            LivingEntity le = (LivingEntity) e;
                            if (Targets.distToBox(le, pos) > hitRadius) continue;
                            if (!hit.add(le.getUniqueId())) continue;
                            if (explodeRadius > 0 && !pierce) {
                                finish(pos, true);
                                return;
                            }
                            HitEffects.apply(effects, ctx, le, pos);
                            if (hitSound != null) Fx.sound(pos, hitSound, 1, 1);
                            if (!pierce) {
                                if (!onImpact.isEmpty()) runAll(onImpact, ctx.at(pos));
                                if (disp != null) disp.remove();
                                cancel();
                                return;
                            }
                        }
                        if (traveled >= range) {
                            finish(pos, false);
                            return;
                        }
                    }
                    if (particle != null) particle.spawn(pos, pCount, pSpread, 0.01);
                    if (gravity != 0) vel.setY(vel.getY() - gravity);
                    if (disp != null && disp.isValid()) {
                        Location dl = pos.clone();
                        dl.setDirection(vel);
                        disp.teleport(dl);
                        if (spin) {
                            spinAngle += 0.9f;
                            disp.setInterpolationDelay(0);
                            disp.setInterpolationDuration(1);
                            float sc = (float) displayScale;
                            disp.setTransformation(new Transformation(new Vector3f(),
                                    new AxisAngle4f(spinAngle, 1, 0, 0), new Vector3f(sc, sc, sc), new AxisAngle4f()));
                        }
                    }
                }

                boolean followGround() {
                    // 땅을 타고 미끄러지는 파동. 한 칸 턱은 넘고, 낭떠러지는 한두 칸까지 따라 내려간다
                    if (solid(pos)) {
                        pos.add(0, 1, 0);
                        return !solid(pos);
                    }
                    for (int i = 0; i < 2; i++) {
                        if (solid(pos.clone().add(0, -1, 0))) return true;
                        pos.add(0, -1, 0);
                    }
                    return solid(pos.clone().add(0, -1, 0));
                }

                void steer() {
                    LivingEntity tgt = null;
                    if (ctx.hasTarget() && !(ctx.caster instanceof Player)) tgt = ctx.target;
                    else {
                        double best = 10;
                        for (LivingEntity e : Targets.enemiesNear(ctx.caster, pos, 10)) {
                            double dd = e.getLocation().distance(pos);
                            if (dd < best) {
                                best = dd;
                                tgt = e;
                            }
                        }
                    }
                    if (tgt == null) return;
                    Vector want = tgt.getLocation().add(0, tgt.getHeight() / 2, 0).toVector().subtract(pos.toVector());
                    if (want.lengthSquared() < 1e-6) return;
                    want.normalize().multiply(speed);
                    vel.add(want.subtract(vel).multiply(Math.min(1, homing)));
                    if (vel.lengthSquared() > 1e-6) vel.normalize().multiply(speed);
                }
            }.runTaskTimer(ctx.plugin, 0, 1);
        }

        void explode(SkillContext ctx, Location at) {
            if (explodeRadius <= 0) return;
            if (explodeParticle != null) {
                explodeParticle.spawn(at, (int) Math.max(1, explodeRadius * 2), explodeRadius * 0.3, 0.02);
                Fx.ring(explodeParticle, at, explodeRadius, (int) (explodeRadius * 8));
            }
            Fx.sound(at, "entity.generic.explode", 0.7f, 1.3f);
            hitAround(ctx, at, explodeRadius, explodeEffects, null);
        }
    }

    // ------------------------------------------------------------------ 광선

    static final class Beam implements Mechanic {
        final double length, width;
        final boolean pierce, throughWalls;
        final Fx.Spec particle, core;
        final List<HitEffect> effects;
        final List<Mechanic> onEnd;

        Beam(P p) {
            length = p.d("length", 18);
            width = p.d("width", 0.8);
            pierce = p.b("pierce", true);
            throughWalls = p.b("through_walls", false);
            particle = Fx.parse(p.s("particle", "END_ROD"));
            core = Fx.parse(p.s("core", null));
            effects = effects(p, "effects");
            onEnd = parseList(p.maps("on_end"));
        }

        @Override
        public void run(SkillContext ctx) {
            Location pos = ctx.eye().add(0, -0.2, 0);
            Vector d = ctx.dir();
            Set<UUID> hit = new HashSet<>();
            double step = 0.4;
            Location end = pos.clone();
            outer:
            for (double t = 0; t <= length; t += step) {
                end = pos.clone().add(d.clone().multiply(t));
                if (!throughWalls && solid(end)) break;
                if (particle != null) particle.spawn(end, 1, width * 0.15, 0);
                if (core != null && ((int) (t / step)) % 2 == 0) core.spawn(end, 1, 0, 0);
                for (LivingEntity e : Targets.enemiesNear(ctx.caster, end, width)) {
                    if (!hit.add(e.getUniqueId())) continue;
                    HitEffects.apply(effects, ctx, e, ctx.caster.getLocation());
                    if (!pierce) break outer;
                }
            }
            if (!onEnd.isEmpty()) runAll(onEnd, ctx.at(end));
        }
    }

    // ------------------------------------------------------------------ 돌진

    static final class Dash implements Mechanic {
        final double distance, width, upward;
        final int ticks;
        final Fx.Spec particle;
        final List<HitEffect> effects;
        final List<Mechanic> onEnd;

        Dash(P p) {
            distance = p.d("distance", 7);
            ticks = Math.max(1, p.i("ticks", 5));
            width = p.d("width", 1.4);
            upward = p.d("upward", 0.05);
            particle = Fx.parse(p.s("particle", "CLOUD"));
            effects = effects(p, "effects");
            onEnd = parseList(p.maps("on_end"));
        }

        @Override
        public void run(SkillContext ctx) {
            Vector d = ctx.flatDir();
            double per = distance / ticks * 1.15;
            Set<UUID> hit = new HashSet<>();
            LivingEntity c = ctx.caster;
            new BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    if (!c.isValid() || c.isDead()) {
                        cancel();
                        return;
                    }
                    t++;
                    Vector v = d.clone().multiply(per);
                    // 섬 가장자리: 앞이 공허면 거기서 멈춘다
                    Location ahead = c.getLocation().add(d.clone().multiply(Math.max(1.2, per * 1.5)));
                    if (!grounded(ahead, 5)) {
                        c.setVelocity(new Vector(0, Math.min(c.getVelocity().getY(), 0), 0));
                        if (!onEnd.isEmpty()) runAll(onEnd, ctx.at(c.getLocation()));
                        cancel();
                        return;
                    }
                    v.setY(t == 1 ? upward + 0.1 : Math.min(c.getVelocity().getY(), 0.1));
                    c.setVelocity(v);
                    c.setFallDistance(0);
                    Location at = c.getLocation().add(0, c.getHeight() / 2, 0);
                    if (particle != null) particle.spawn(at, 4, 0.25, 0.01);
                    for (LivingEntity e : Targets.enemiesNear(c, at, width)) {
                        if (hit.add(e.getUniqueId())) HitEffects.apply(effects, ctx, e, c.getLocation());
                    }
                    if (t >= ticks) {
                        c.setVelocity(d.clone().multiply(0.25).setY(Math.min(c.getVelocity().getY(), 0)));
                        if (!onEnd.isEmpty()) runAll(onEnd, ctx.at(c.getLocation()));
                        cancel();
                    }
                }
            }.runTaskTimer(ctx.plugin, 0, 1);
        }
    }

    // ------------------------------------------------------------------ 도약 후 착지

    static final class Leap implements Mechanic {
        final double forward, upward;
        final Fx.Spec particle;
        final List<Mechanic> land;

        Leap(P p) {
            forward = p.d("forward", 1.1);
            upward = p.d("upward", 0.9);
            particle = Fx.parse(p.s("particle", "CLOUD"));
            land = parseList(p.maps("land"));
        }

        @Override
        public void run(SkillContext ctx) {
            LivingEntity c = ctx.caster;
            double fwd = forward;
            // 대략 착지할 곳 아래가 공허면 제자리에서 뛰어오른다
            Location land0 = c.getLocation().add(ctx.flatDir().multiply(forward * 9));
            if (!grounded(land0.add(0, 2, 0), 10)) fwd = 0;
            Vector v = ctx.flatDir().multiply(fwd);
            v.setY(upward);
            c.setVelocity(v);
            if (particle != null) particle.spawn(c.getLocation(), 12, 0.4, 0.02);
            new BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    t++;
                    if (!c.isValid() || c.isDead()) {
                        cancel();
                        return;
                    }
                    c.setFallDistance(0);
                    if (particle != null && t % 2 == 0) particle.spawn(c.getLocation(), 2, 0.1, 0);
                    if ((t > 4 && c.isOnGround()) || t > 60) {
                        cancel();
                        runAll(land, ctx.at(c.getLocation()));
                    }
                }
            }.runTaskTimer(ctx.plugin, 1, 1);
        }
    }

    // ------------------------------------------------------------------ 순간이동

    static final class Blink implements Mechanic {
        final double distance;
        final boolean behind;
        final Fx.Spec particle;

        Blink(P p) {
            distance = p.d("distance", 8);
            behind = p.b("behind", false);
            particle = Fx.parse(p.s("particle", "PORTAL"));
        }

        @Override
        public void run(SkillContext ctx) {
            LivingEntity c = ctx.caster;
            Location from = c.getLocation();
            Location dest;
            if (behind && ctx.hasTarget()) {
                Location t = ctx.target.getLocation();
                Vector back = t.getDirection().setY(0);
                if (back.lengthSquared() < 1e-6) back = new Vector(0, 0, 1);
                dest = t.clone().subtract(back.normalize().multiply(1.6));
                dest.setDirection(t.toVector().subtract(dest.toVector()));
            } else {
                Location eye = c.getEyeLocation();
                Vector d = eye.getDirection();
                RayTraceResult r = c.getWorld().rayTraceBlocks(eye, d, distance, FluidCollisionMode.NEVER, true);
                double dist = r == null ? distance : Math.max(0, r.getHitPosition().distance(eye.toVector()) - 0.8);
                dest = eye.clone().add(d.clone().multiply(dist));
                dest.setY(dest.getY() - c.getEyeHeight() + 0.1);
                dest.setYaw(from.getYaw());
                dest.setPitch(from.getPitch());
            }
            Location safe = safeSpot(dest);
            if (!behind) {
                // 공허 위로 순간이동하지 않도록, 밟을 곳이 있는 지점까지 거리를 줄인다
                Vector back = from.toVector().subtract(dest.toVector());
                double len = back.length();
                if (len > 1e-6) back.multiply(1.0 / len);
                double moved = 0;
                while ((safe == null || !grounded(safe, 4)) && moved < len) {
                    dest.add(back.clone().multiply(0.5));
                    moved += 0.5;
                    safe = safeSpot(dest);
                }
                if (safe == null || !grounded(safe, 4)) return;
            }
            if (safe == null) return;
            if (particle != null) {
                particle.spawn(from.clone().add(0, 1, 0), 30, 0.3, 0.6, 0.3, 0.1);
                particle.spawn(safe.clone().add(0, 1, 0), 30, 0.3, 0.6, 0.3, 0.1);
            }
            c.teleport(safe);
            c.setFallDistance(0);
            Fx.sound(safe, "entity.enderman.teleport", 0.8f, 1.2f);
        }

        static Location safeSpot(Location l) {
            for (int dy = 0; dy <= 2; dy++) {
                Location t = l.clone().add(0, dy, 0);
                if (!solid(t) && !solid(t.clone().add(0, 1, 0))) return t;
            }
            return null;
        }
    }

    // ------------------------------------------------------------------ 하늘에서 떨어지는 공격

    static final class Rain implements Mechanic {
        final int count, interval;
        final double radius, height, fall, impactRadius, range, displayScale;
        final String at, display, impactSound;
        final Fx.Spec particle, impactParticle;
        final List<HitEffect> effects;

        Rain(P p) {
            count = Math.max(1, p.i("count", 6));
            interval = Math.max(0, p.i("interval", 3));
            radius = p.d("radius", 4);
            height = p.d("height", 14);
            fall = p.d("speed", 1.1);
            impactRadius = p.d("impact_radius", 2.2);
            range = p.d("range", 22);
            at = p.s("at", "aim");
            display = p.s("display", null);
            displayScale = p.d("display_scale", 1.0);
            particle = Fx.parse(p.s("particle", "FLAME"));
            impactParticle = Fx.parse(p.s("impact_particle", "EXPLOSION"));
            impactSound = p.s("impact_sound", "entity.generic.explode");
            effects = effects(p, "effects");
        }

        @Override
        public void run(SkillContext ctx) {
            Location center = ctx.center(at, range);
            for (int i = 0; i < count; i++) {
                int delay = i * interval;
                Bukkit.getScheduler().runTaskLater(ctx.plugin, () -> drop(ctx, center), delay);
            }
        }

        void drop(SkillContext ctx, Location center) {
            ThreadLocalRandom r = ThreadLocalRandom.current();
            double a = r.nextDouble(Math.PI * 2);
            double dist = count == 1 ? 0 : Math.sqrt(r.nextDouble()) * radius;
            Location target = center.clone().add(Math.cos(a) * dist, 0, Math.sin(a) * dist);
            Location ground = SkillContext.ground(target.clone().add(0, 4, 0), 20);
            Location pos = ground.clone().add(r.nextDouble(-2, 2), height, r.nextDouble(-2, 2));
            Vector v = ground.toVector().subtract(pos.toVector()).normalize().multiply(fall);
            ItemDisplay disp = display(pos, display, (float) displayScale);
            new BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    t++;
                    pos.add(v);
                    if (particle != null) particle.spawn(pos, 3, 0.15, 0.01);
                    if (disp != null && disp.isValid()) disp.teleport(pos);
                    if (pos.getY() <= ground.getY() || solid(pos) || t > 80) {
                        if (disp != null) disp.remove();
                        Location hitAt = pos.getY() <= ground.getY() ? ground : pos;
                        if (impactParticle != null) impactParticle.spawn(hitAt, 3, impactRadius * 0.3, 0.02);
                        Fx.sound(hitAt, impactSound, 0.6f, 1.0f + (float) r.nextDouble(0.3));
                        hitAround(ctx, hitAt, impactRadius, effects, null);
                        cancel();
                    }
                }
            }.runTaskTimer(ctx.plugin, 0, 1);
        }
    }

    // ------------------------------------------------------------------ 낙뢰/기둥

    static final class Strike implements Mechanic {
        final int count, interval;
        final double radius, impactRadius, range;
        final boolean targets;
        final String at, visual;
        final Fx.Spec particle;
        final List<HitEffect> effects;

        Strike(P p) {
            count = Math.max(1, p.i("count", 1));
            interval = Math.max(0, p.i("interval", 4));
            radius = p.d("radius", 0);
            impactRadius = p.d("impact_radius", 1.6);
            range = p.d("range", 20);
            targets = p.b("targets", false);
            at = p.s("at", "aim");
            visual = p.s("visual", "lightning");
            particle = Fx.parse(p.s("particle", "ELECTRIC_SPARK"));
            effects = effects(p, "effects");
        }

        @Override
        public void run(SkillContext ctx) {
            Location center = ctx.center(at, range);
            List<Location> points = new ArrayList<>();
            if (targets) {
                List<LivingEntity> list = Targets.enemiesNear(ctx.caster, center, Math.max(radius, 3));
                list.sort(Comparator.comparingDouble(e -> e.getLocation().distanceSquared(center)));
                for (int i = 0; i < Math.min(count, list.size()); i++) points.add(list.get(i).getLocation());
                if (points.isEmpty()) points.add(center);
            } else {
                ThreadLocalRandom r = ThreadLocalRandom.current();
                for (int i = 0; i < count; i++) {
                    if (radius <= 0) points.add(center.clone());
                    else {
                        double a = r.nextDouble(Math.PI * 2), d = Math.sqrt(r.nextDouble()) * radius;
                        points.add(SkillContext.ground(center.clone().add(Math.cos(a) * d, 3, Math.sin(a) * d), 10));
                    }
                }
            }
            for (int i = 0; i < points.size(); i++) {
                Location pt = points.get(i);
                Bukkit.getScheduler().runTaskLater(ctx.plugin, () -> hit(ctx, pt), (long) i * interval);
            }
        }

        void hit(SkillContext ctx, Location pt) {
            switch (visual) {
                case "lightning" -> {
                    pt.getWorld().strikeLightningEffect(pt);
                    Fx.bolt(pt, particle);
                }
                case "pillar" -> {
                    if (particle != null) for (double y = 0; y < 6; y += 0.3) particle.spawn(pt.clone().add(0, y, 0), 2, 0.2, 0.01);
                }
                default -> {
                    if (particle != null) particle.spawn(pt.clone().add(0, 0.5, 0), 20, 0.5, 0.05);
                }
            }
            hitAround(ctx, pt, impactRadius, effects, null);
        }
    }

    // ------------------------------------------------------------------ 연쇄

    static final class Chain implements Mechanic {
        final int jumps, delay;
        final double range, firstRange;
        final Fx.Spec particle;
        final List<HitEffect> effects;

        Chain(P p) {
            jumps = Math.max(1, p.i("jumps", 4));
            delay = Math.max(1, p.i("delay", 2));
            range = p.d("range", 6);
            firstRange = p.d("first_range", 14);
            particle = Fx.parse(p.s("particle", "ELECTRIC_SPARK"));
            effects = effects(p, "effects");
        }

        @Override
        public void run(SkillContext ctx) {
            LivingEntity first = null;
            if (ctx.hasTarget() && Targets.isEnemy(ctx.caster, ctx.target)) first = ctx.target;
            else {
                Vector d = ctx.dir();
                double best = Double.MAX_VALUE;
                for (LivingEntity e : Targets.enemiesNear(ctx.caster, ctx.eye(), firstRange)) {
                    Vector to = e.getEyeLocation().toVector().subtract(ctx.eye().toVector());
                    if (to.lengthSquared() < 1e-6) continue;
                    double ang = to.angle(d);
                    if (ang > Math.toRadians(40)) continue;
                    double score = ang * 10 + to.length();
                    if (score < best) {
                        best = score;
                        first = e;
                    }
                }
            }
            if (first == null) return;
            Set<UUID> hit = new HashSet<>();
            jump(ctx, ctx.eye(), first, hit, 0);
        }

        void jump(SkillContext ctx, Location from, LivingEntity to, Set<UUID> hit, int n) {
            hit.add(to.getUniqueId());
            Location toLoc = to.getLocation().add(0, to.getHeight() / 2, 0);
            Fx.line(particle, from, toLoc, 0.3);
            HitEffects.apply(effects, ctx, to, from);
            if (n + 1 >= jumps) return;
            LivingEntity next = null;
            double best = range;
            for (LivingEntity e : Targets.enemiesNear(ctx.caster, toLoc, range)) {
                if (hit.contains(e.getUniqueId())) continue;
                double dd = e.getLocation().distance(toLoc);
                if (dd < best) {
                    best = dd;
                    next = e;
                }
            }
            if (next == null) return;
            LivingEntity nx = next;
            Bukkit.getScheduler().runTaskLater(ctx.plugin, () -> {
                if (nx.isValid()) jump(ctx, toLoc, nx, hit, n + 1);
            }, delay);
        }
    }

    // ------------------------------------------------------------------ 장판

    static final class Zone implements Mechanic {
        final double radius, height, range;
        final int duration, interval;
        final boolean follow;
        final String at;
        final Fx.Spec particle, ringParticle;
        final List<HitEffect> effects, allyEffects;

        Zone(P p) {
            radius = p.d("radius", 3.5);
            height = p.d("height", 3);
            range = p.d("range", 16);
            duration = (int) (p.d("duration", 5) * 20);
            interval = Math.max(1, p.i("interval", 10));
            follow = p.b("follow", false);
            at = p.s("at", "aim");
            particle = Fx.parse(p.s("particle", "WITCH"));
            ringParticle = Fx.parse(p.s("ring", null));
            effects = effects(p, "effects");
            allyEffects = effects(p, "ally_effects");
        }

        @Override
        public void run(SkillContext ctx) {
            Location fixed = ctx.center(at, range);
            new BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    if (follow && (!ctx.caster.isValid() || ctx.caster.isDead())) {
                        cancel();
                        return;
                    }
                    Location c = follow ? ctx.caster.getLocation() : fixed;
                    if (t % 4 == 0) {
                        if (ringParticle != null) Fx.ring(ringParticle, c.clone().add(0, 0.15, 0), radius, (int) (radius * 7));
                        if (particle != null) particle.spawn(c.clone().add(0, 0.6, 0), (int) (radius * 3), radius * 0.45, 0.3, radius * 0.45, 0.01);
                    }
                    if (t % interval == 0) {
                        for (LivingEntity e : Targets.enemiesNear(ctx.caster, c, radius)) {
                            if (Math.abs(e.getLocation().getY() - c.getY()) > height) continue;
                            HitEffects.apply(effects, ctx, e, c);
                        }
                        if (!allyEffects.isEmpty()) {
                            for (LivingEntity e : Targets.friendsNear(ctx.caster, c, radius)) {
                                HitEffects.apply(allyEffects, ctx, e, c);
                            }
                        }
                    }
                    t++;
                    if (t > duration) cancel();
                }
            }.runTaskTimer(ctx.plugin, 0, 1);
        }
    }

    // ------------------------------------------------------------------ 주위를 도는 칼날

    static final class Orbit implements Mechanic {
        final int count, duration, hitCooldown;
        final double radius, speed, yOff, displayScale;
        final Fx.Spec particle;
        final String display;
        final List<HitEffect> effects;

        Orbit(P p) {
            count = Math.max(1, p.i("count", 3));
            duration = (int) (p.d("duration", 5) * 20);
            hitCooldown = Math.max(1, p.i("hit_cooldown", 10));
            radius = p.d("radius", 2.6);
            speed = Math.toRadians(p.d("speed", 14));
            yOff = p.d("y", 1.0);
            particle = Fx.parse(p.s("particle", "SWEEP_ATTACK"));
            display = p.s("display", null);
            displayScale = p.d("display_scale", 0.8);
            effects = effects(p, "effects");
        }

        @Override
        public void run(SkillContext ctx) {
            List<ItemDisplay> discs = new ArrayList<>();
            for (int i = 0; i < count; i++) {
                ItemDisplay d = display(ctx.caster.getLocation(), display, (float) displayScale);
                if (d != null) discs.add(d);
            }
            Map<UUID, Integer> last = new HashMap<>();
            new BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    t++;
                    if (t > duration || !ctx.caster.isValid() || ctx.caster.isDead()) {
                        discs.forEach(Entity::remove);
                        cancel();
                        return;
                    }
                    Location c = ctx.caster.getLocation().add(0, yOff, 0);
                    for (int i = 0; i < count; i++) {
                        double a = t * speed + Math.PI * 2 * i / count;
                        Location pt = c.clone().add(Math.cos(a) * radius, 0, Math.sin(a) * radius);
                        if (particle != null) particle.spawn(pt, 1, 0.05, 0);
                        if (i < discs.size()) {
                            Location dl = pt.clone();
                            dl.setYaw((float) Math.toDegrees(a));
                            discs.get(i).teleport(dl);
                        }
                        for (LivingEntity e : Targets.enemiesNear(ctx.caster, pt, 1.1)) {
                            Integer prev = last.get(e.getUniqueId());
                            if (prev != null && t - prev < hitCooldown) continue;
                            last.put(e.getUniqueId(), t);
                            HitEffects.apply(effects, ctx, e, c);
                        }
                    }
                }
            }.runTaskTimer(ctx.plugin, 0, 1);
        }
    }

    // ------------------------------------------------------------------ 소용돌이(끌어당김)

    static final class Vortex implements Mechanic {
        final double radius, strength, range;
        final int duration, interval;
        final String at;
        final Fx.Spec particle;
        final List<HitEffect> effects;
        final List<Mechanic> end;

        Vortex(P p) {
            radius = p.d("radius", 6);
            strength = p.d("strength", 0.25);
            range = p.d("range", 18);
            duration = (int) (p.d("duration", 3) * 20);
            interval = Math.max(1, p.i("interval", 10));
            at = p.s("at", "aim");
            particle = Fx.parse(p.s("particle", "PORTAL"));
            effects = effects(p, "effects");
            end = parseList(p.maps("end"));
        }

        @Override
        public void run(SkillContext ctx) {
            Location c = ctx.center(at, range).add(0, 0.8, 0);
            new BukkitRunnable() {
                int t = 0;

                @Override
                public void run() {
                    t++;
                    if (particle != null) {
                        for (int i = 0; i < 3; i++) {
                            double a = t * 0.5 + i * 2.1;
                            double r = radius * (1 - (t % 20) / 20.0);
                            particle.spawn(c.clone().add(Math.cos(a) * r, 0, Math.sin(a) * r), 2, 0.05, 0);
                        }
                    }
                    for (LivingEntity e : Targets.enemiesNear(ctx.caster, c, radius)) {
                        Vector pull = c.toVector().subtract(e.getLocation().toVector());
                        if (pull.lengthSquared() > 1) {
                            double kb = HitEffects.kbResist(e);
                            pull.normalize().multiply(strength * (1 - kb * 0.7));
                            pull.setY(Math.max(-0.1, Math.min(0.2, pull.getY())));
                            e.setVelocity(pull);
                        }
                        if (t % interval == 0) HitEffects.apply(effects, ctx, e, c);
                    }
                    if (t >= duration) {
                        cancel();
                        runAll(end, ctx.at(c));
                    }
                }
            }.runTaskTimer(ctx.plugin, 0, 1);
        }
    }

    // ------------------------------------------------------------------ 자기 강화 / 아군 강화

    static final class SelfFx implements Mechanic {
        final List<HitEffect> effects;
        final Fx.Spec particle;

        SelfFx(P p) {
            effects = effects(p, "effects");
            particle = Fx.parse(p.s("particle", null));
        }

        @Override
        public void run(SkillContext ctx) {
            if (particle != null) particle.spawn(ctx.caster.getLocation().add(0, 1, 0), 20, 0.4, 0.05);
            for (HitEffect e : effects) e.apply(ctx, ctx.caster, ctx.caster.getLocation());
        }
    }

    /** 지금 대상(몬스터가 노리는 플레이어, 맞힌 적)에게 바로 효과를 건다. */
    static final class TargetFx implements Mechanic {
        final List<HitEffect> effects;
        final Fx.Spec particle;

        TargetFx(P p) {
            effects = effects(p, "effects");
            particle = Fx.parse(p.s("particle", null));
        }

        @Override
        public void run(SkillContext ctx) {
            if (!ctx.hasTarget() || !Targets.isEnemy(ctx.caster, ctx.target)) return;
            if (particle != null) particle.spawn(ctx.target.getLocation().add(0, 1, 0), 15, 0.3, 0.05);
            HitEffects.apply(effects, ctx, ctx.target, ctx.caster.getLocation());
        }
    }

    static final class Party implements Mechanic {
        final double radius;
        final List<HitEffect> effects;
        final Fx.Spec particle;

        Party(P p) {
            radius = p.d("radius", 8);
            effects = effects(p, "effects");
            particle = Fx.parse(p.s("particle", "HAPPY_VILLAGER"));
        }

        @Override
        public void run(SkillContext ctx) {
            Location c = ctx.point != null ? ctx.point : ctx.caster.getLocation();
            for (LivingEntity e : Targets.friendsNear(ctx.caster, c, radius)) {
                if (particle != null) particle.spawn(e.getLocation().add(0, 1, 0), 10, 0.4, 0.02);
                for (HitEffect h : effects) h.apply(ctx, e, c);
            }
        }
    }

    // ------------------------------------------------------------------ 소환

    static final class Summon implements Mechanic {
        final String mob;
        final int count;

        Summon(P p) {
            mob = p.s("mob", null);
            count = Math.max(1, p.i("count", 1));
        }

        @Override
        public void run(SkillContext ctx) {
            // 플레이어 편 소환수는 없다. 적이 부르는 졸개만 적 등록부로 만든다
            if (ctx.byPlayer || mob == null) return;
            Location base = ctx.point != null ? ctx.point : ctx.caster.getLocation();
            ThreadLocalRandom r = ThreadLocalRandom.current();
            for (int i = 0; i < count; i++) {
                Location at = base.clone().add(r.nextDouble(-1.5, 1.5), 0.2, r.nextDouble(-1.5, 1.5));
                if (solid(at)) at = base.clone().add(0, 0.2, 0);
                new Fx.Spec(Particle.LARGE_SMOKE, null).spawn(at.clone().add(0, 0.5, 0), 10, 0.3, 0.02);
                LivingEntity spawned = enemySpawner.apply(mob, at);
                if (spawned instanceof org.bukkit.entity.Mob m && ctx.hasTarget()) m.setTarget(ctx.target);
            }
        }
    }

    // ------------------------------------------------------------------ 흐름 제어

    static final class Repeat implements Mechanic {
        final int times, interval;
        final List<Mechanic> body;

        Repeat(P p) {
            times = Math.max(1, p.i("times", 3));
            interval = Math.max(1, p.i("interval", 5));
            body = parseList(p.maps("mechanics"));
        }

        @Override
        public void run(SkillContext ctx) {
            new BukkitRunnable() {
                int n = 0;

                @Override
                public void run() {
                    if (!ctx.caster.isValid() || ctx.caster.isDead()) {
                        cancel();
                        return;
                    }
                    runAll(body, ctx);
                    if (++n >= times) cancel();
                }
            }.runTaskTimer(ctx.plugin, 0, interval);
        }
    }

    static final class Delay implements Mechanic {
        final int ticks;
        final List<Mechanic> body;

        Delay(P p) {
            ticks = Math.max(1, p.i("ticks", 10));
            body = parseList(p.maps("mechanics"));
        }

        @Override
        public void run(SkillContext ctx) {
            Bukkit.getScheduler().runTaskLater(ctx.plugin, () -> {
                if (ctx.caster.isValid() && !ctx.caster.isDead()) runAll(body, ctx);
            }, ticks);
        }
    }

    static final class SoundM implements Mechanic {
        final String sound, at;
        final float volume, pitch;

        SoundM(P p) {
            sound = p.s("sound", "entity.player.attack.sweep");
            volume = (float) p.d("volume", 1);
            pitch = (float) p.d("pitch", 1);
            at = p.s("at", "self");
        }

        @Override
        public void run(SkillContext ctx) {
            Fx.sound(ctx.center(at, 20), sound, volume, pitch);
        }
    }

    static final class ParticleM implements Mechanic {
        final Fx.Spec spec;
        final int count;
        final double spread, speed, yOff, range;
        final String at;

        ParticleM(P p) {
            spec = Fx.parse(p.s("particle", "CRIT"));
            count = p.i("count", 20);
            spread = p.d("spread", 0.5);
            speed = p.d("speed", 0.05);
            yOff = p.d("y", 1);
            at = p.s("at", "self");
            range = p.d("range", 20);
        }

        @Override
        public void run(SkillContext ctx) {
            if (spec != null) spec.spawn(ctx.center(at, range).add(0, yOff, 0), count, spread, speed);
        }
    }

    /** 둘레 사람에게 채팅 한 줄 (보스 대사 같은 것). 글은 콘텐츠에 쓰지 않고 lang 열쇠로 가리킨다: {type: say, key: boss.hrolf.taunt} */
    static final class Say implements Mechanic {
        final String key;
        final double radius;

        Say(P p) {
            key = p.s("key", "");
            radius = p.d("radius", 40);
            if (key.isEmpty() || !p.s("text", "").isEmpty()) log.warning("say 부품은 글(text) 대신 lang 열쇠(key)를 쓴다: " + p.s("text", ""));
        }

        @Override
        public void run(SkillContext ctx) {
            if (key.isEmpty()) return;
            var comp = Lang.c(key);
            for (Player pl : ctx.caster.getWorld().getPlayers()) {
                if (pl.getLocation().distance(ctx.caster.getLocation()) <= radius) pl.sendMessage(comp);
            }
        }
    }

    static final class SkillRef implements Mechanic {
        final String id;

        SkillRef(P p) {
            id = p.s("id", p.s("skill", ""));
        }

        @Override
        public void run(SkillContext ctx) {
            SkillDef def = ctx.plugin.skills().get(id);
            if (def != null) runAll(def.mechanics(), ctx);
        }
    }

    static final class Velocity implements Mechanic {
        final double forward, upward;

        Velocity(P p) {
            forward = p.d("forward", 0.8);
            upward = p.d("upward", 0.3);
        }

        @Override
        public void run(SkillContext ctx) {
            Vector v = ctx.flatDir().multiply(forward);
            v.setY(upward);
            ctx.caster.setVelocity(v);
            ctx.caster.setFallDistance(0);
        }
    }
}
