package kr.labyrinth.mobs;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.function.BiConsumer;
import java.util.function.Consumer;
import java.util.function.Predicate;
import kr.labyrinth.Services;
import kr.labyrinth.content.FxModelDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Log;
import net.kyori.adventure.key.Key;
import org.bukkit.Color;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitRunnable;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * 일반 몹 스킬용 시각 효과·판정 부품: 경고 장판(GDD §8.1 도형, 바닥에 눕힌 fx ItemDisplay + DUST 윤곽),
 * fx 모델 투사체, 잔류 장판, 테더. 블록은 절대 바꾸지 않는다. 모든 디스플레이는 임시 엔티티 태그 + 종료 시 정리.
 */
public final class MobFx {

    public static final Color RED = Color.fromRGB(255, 59, 59);
    public static final Color ORANGE = Color.fromRGB(255, 138, 42);
    public static final Color PURPLE = Color.fromRGB(192, 58, 208);
    public static final Color GREEN = Color.fromRGB(58, 208, 106);

    private final Services services;
    private final Set<Entity> active = new HashSet<>();
    private final Set<BukkitTask> tasks = new HashSet<>();

    public MobFx(Services services) { this.services = services; }

    double yawOffset() { return services.plugin().getConfig().getDouble("mobs.model_yaw_offset", 0.0); }

    // ── 도형 ─────────────────────────────────────────────────────────────

    public enum Kind { CIRCLE, RING, LINE, CONE, ARROW }

    /** 판정 도형. origin = 원 중심 또는 선/부채꼴 시작점. */
    public record Shape(Kind kind, Location origin, double dirX, double dirZ, double size, double width, double angle) {
        public static Shape circle(Location c, double r) { return new Shape(Kind.CIRCLE, c, 0, 1, r, 0, 0); }
        public static Shape ring(Location c, double inner, double r) { return new Shape(Kind.RING, c, 0, 1, r, inner, 0); }
        public static Shape line(Location o, Vector dir, double length, double width) {
            return new Shape(Kind.LINE, o, dir.getX(), dir.getZ(), length, width, 0);
        }
        public static Shape arrow(Location o, Vector dir, double length, double width) {
            return new Shape(Kind.ARROW, o, dir.getX(), dir.getZ(), length, width, 0);
        }
        public static Shape cone(Location o, Vector dir, double angle, double length) {
            return new Shape(Kind.CONE, o, dir.getX(), dir.getZ(), length, 0, angle);
        }

        public boolean contains(Location p) {
            if (p.getWorld() != origin.getWorld() || !Geometry.heightOk(origin.getY(), p.getY())) return false;
            double ox = origin.getX(), oz = origin.getZ(), px = p.getX(), pz = p.getZ();
            return switch (kind) {
                case CIRCLE -> Geometry.inCircle(ox, oz, size, px, pz);
                case RING -> Geometry.inRing(ox, oz, width, size, px, pz);
                case LINE, ARROW -> Geometry.inLine(ox, oz, dirX, dirZ, size, width, px, pz);
                case CONE -> Geometry.inCone(ox, oz, dirX, dirZ, angle, size, px, pz);
            };
        }

        String model() {
            return switch (kind) {
                case CIRCLE -> "telegraph_circle";
                case RING -> "telegraph_ring";
                case LINE -> "telegraph_line";
                case ARROW -> "telegraph_arrow";
                case CONE -> "telegraph_cone";
            };
        }
    }

    /** 진행 중인 경고 (취소 가능). */
    public interface Handle {
        void cancel();
        boolean done();
    }

    // ── 경고 장판 ────────────────────────────────────────────────────────

    /**
     * 경고 장판을 ticks 동안 보여 준 뒤 onFire 실행. 끝나기 6틱 전에 밝게 깜빡인다(GDD §8.1).
     * @param modelOverride fx 모델 id (null = 도형 기본 모델)
     */
    public Handle telegraph(Shape shape, int ticks, Color color, String modelOverride, Runnable onFire) {
        ItemDisplay plate = spawnPlate(shape, modelOverride);
        final int total = Math.max(1, ticks);
        BukkitRunnable r = new BukkitRunnable() {
            int t = 0;
            boolean flashed;
            @Override
            public void run() {
                try {
                    if (t % 4 == 0) outline(shape, color, t >= total - 6 ? 1.4f : 1.0f);
                    if (!flashed && t >= total - 6 && plate != null && plate.isValid()) {
                        flashed = true;
                        plate.setGlowing(true);
                        plate.setGlowColorOverride(color);
                        plate.setBrightness(new Display.Brightness(15, 15));
                    }
                    if (t >= total) {
                        cancelSelf();
                        try {
                            onFire.run();
                        } catch (Throwable ex) {
                            Log.error("몹 스킬 발동 오류", ex);
                        }
                        return;
                    }
                    t++;
                } catch (Throwable ex) {
                    Log.error("경고 장판 오류", ex);
                    cancelSelf();
                }
            }
            void cancelSelf() {
                cancel();
                if (plate != null) {
                    plate.remove();
                    active.remove(plate);
                }
            }
        };
        BukkitTask task = r.runTaskTimer(services.plugin(), 0L, 1L);
        tasks.add(task);
        return new Handle() {
            @Override
            public void cancel() {
                if (!task.isCancelled()) task.cancel();
                if (plate != null) {
                    plate.remove();
                    active.remove(plate);
                }
            }
            @Override
            public boolean done() { return task.isCancelled(); }
        };
    }

    private ItemDisplay spawnPlate(Shape shape, String modelOverride) {
        String model = modelOverride != null ? modelOverride : shape.model();
        FxModelDef def = services.content().fxModels().get(model);
        double sx = def != null && def.size().size() >= 1 ? def.size().get(0) / 16.0 : 2.0;
        double sz = def != null && def.size().size() >= 3 ? def.size().get(2) / 16.0 : sx;
        if (sx <= 0) sx = 2.0;
        if (sz <= 0) sz = 2.0;
        Location at = shape.origin().clone();
        float scaleX, scaleZ;
        float yaw = Geometry.yawOf(shape.dirX(), shape.dirZ());
        switch (shape.kind()) {
            case CIRCLE, RING -> {
                scaleX = (float) (shape.size() * 2 / sx);
                scaleZ = (float) (shape.size() * 2 / sz);
                yaw = 0;
            }
            case LINE, ARROW -> {
                scaleX = (float) (shape.width() / sx);
                scaleZ = (float) (shape.size() / sz);
                Vector d = new Vector(shape.dirX(), 0, shape.dirZ());
                if (d.lengthSquared() > 1e-6) at.add(d.normalize().multiply(shape.size() / 2));
            }
            case CONE -> {
                scaleZ = (float) (shape.size() / sz);
                double half = Math.toRadians(Math.min(170, Math.max(10, shape.angle())) / 2);
                scaleX = (float) (scaleZ * Math.tan(half));
                Vector d = new Vector(shape.dirX(), 0, shape.dirZ());
                if (d.lengthSquared() > 1e-6) at.add(d.normalize().multiply(shape.size() / 2));
            }
            default -> {
                scaleX = 1;
                scaleZ = 1;
            }
        }
        at.add(0, 0.06, 0);
        return flat(model, at, scaleX, scaleZ, yaw);
    }

    /** 바닥에 눕힌 fx 디스플레이 (flat 모델은 원래 수평). */
    public ItemDisplay flat(String fxModel, Location at, float scaleX, float scaleZ, float yawDeg) {
        if (at.getWorld() == null) return null;
        Location l = at.clone();
        l.setYaw(0);
        l.setPitch(0);
        float off = (float) yawOffset();
        ItemDisplay d = at.getWorld().spawn(l, ItemDisplay.class, e -> {
            e.setPersistent(false);
            e.setItemStack(ModelRig.modelItem(Key.key(Keys.NS, "fx/" + fxModel)));
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setBrightness(new Display.Brightness(12, 15));
            e.setViewRange(0.6f);
            Quaternionf q = new Quaternionf().rotationY((float) Math.toRadians(-yawDeg));
            if (off != 0) q.rotateY((float) Math.toRadians(off));
            e.setTransformation(new Transformation(new Vector3f(), q, new Vector3f(scaleX, 1f, scaleZ), new Quaternionf()));
            Keys.tagTransient(e, Keys.FX, "telegraph");
        });
        active.add(d);
        return d;
    }

    /** 도형 윤곽 DUST 입자. */
    public void outline(Shape s, Color color, float size) {
        World w = s.origin().getWorld();
        if (w == null) return;
        Particle.DustOptions dust = new Particle.DustOptions(color, size);
        double y = s.origin().getY() + 0.15;
        double ox = s.origin().getX(), oz = s.origin().getZ();
        switch (s.kind()) {
            case CIRCLE, RING -> {
                int n = (int) Math.max(12, Math.min(64, s.size() * 8));
                for (int i = 0; i < n; i++) {
                    double a = 2 * Math.PI * i / n;
                    w.spawnParticle(Particle.DUST, ox + Math.cos(a) * s.size(), y, oz + Math.sin(a) * s.size(), 1, 0, 0, 0, 0, dust);
                    if (s.kind() == Kind.RING && s.width() > 0.3 && i % 2 == 0) {
                        w.spawnParticle(Particle.DUST, ox + Math.cos(a) * s.width(), y, oz + Math.sin(a) * s.width(), 1, 0, 0, 0, 0, dust);
                    }
                }
            }
            case LINE, ARROW -> {
                Vector d = new Vector(s.dirX(), 0, s.dirZ());
                if (d.lengthSquared() < 1e-6) return;
                d.normalize();
                Vector side = new Vector(-d.getZ(), 0, d.getX()).multiply(s.width() / 2);
                int n = (int) Math.max(4, Math.min(48, s.size() * 2));
                for (int i = 0; i <= n; i++) {
                    double f = s.size() * i / n;
                    double x = ox + d.getX() * f, z = oz + d.getZ() * f;
                    w.spawnParticle(Particle.DUST, x + side.getX(), y, z + side.getZ(), 1, 0, 0, 0, 0, dust);
                    w.spawnParticle(Particle.DUST, x - side.getX(), y, z - side.getZ(), 1, 0, 0, 0, 0, dust);
                }
            }
            case CONE -> {
                double base = Math.atan2(s.dirZ(), s.dirX());
                double half = Math.toRadians(s.angle() / 2);
                int n = (int) Math.max(8, Math.min(40, s.size() * s.angle() / 20));
                for (int i = 0; i <= n; i++) {
                    double a = base - half + 2 * half * i / n;
                    w.spawnParticle(Particle.DUST, ox + Math.cos(a) * s.size(), y, oz + Math.sin(a) * s.size(), 1, 0, 0, 0, 0, dust);
                }
                int m = (int) Math.max(3, s.size() * 1.5);
                for (int i = 0; i <= m; i++) {
                    double f = s.size() * i / m;
                    w.spawnParticle(Particle.DUST, ox + Math.cos(base - half) * f, y, oz + Math.sin(base - half) * f, 1, 0, 0, 0, 0, dust);
                    w.spawnParticle(Particle.DUST, ox + Math.cos(base + half) * f, y, oz + Math.sin(base + half) * f, 1, 0, 0, 0, 0, dust);
                }
            }
        }
    }

    // ── 투사체 ───────────────────────────────────────────────────────────

    /** 투사체 설정. speed = 블록/틱, gravity = 틱당 낙하 가속, homing = 0~1 유도 세기. */
    public record ProjectileSpec(String fx, double speed, double gravity, double homing, double hitRadius, int maxTicks,
                                 Particle trail) {}

    /**
     * fx 모델 투사체 발사. 적(isEnemy 통과 플레이어)에 닿으면 onHit, 블록·수명 끝이면 onImpact(위치).
     * @param homingTarget 유도 대상 (null 가능)
     */
    public void projectile(Location from, Vector dir, ProjectileSpec spec, Entity homingTarget, Predicate<Player> isEnemy,
                           BiConsumer<Player, Location> onHit, Consumer<Location> onImpact) {
        World w = from.getWorld();
        if (w == null) return;
        Vector vel = dir.clone().normalize().multiply(spec.speed());
        FxModelDef def = spec.fx() == null ? null : services.content().fxModels().get(spec.fx());
        Display.Billboard billboard = billboard(def);
        float off = (float) yawOffset();
        ItemDisplay disp = spec.fx() == null ? null : w.spawn(from.clone().setDirection(new Vector(0, 0, 1)), ItemDisplay.class, e -> {
            e.setPersistent(false);
            e.setItemStack(ModelRig.modelItem(Key.key(Keys.NS, "fx/" + spec.fx())));
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setBillboard(billboard);
            e.setTeleportDuration(1);
            e.setViewRange(0.6f);
            if (def != null && def.glow()) e.setBrightness(new Display.Brightness(15, 15));
            e.setTransformation(orient(vel, off));
            Keys.tagTransient(e, Keys.FX, "projectile");
        });
        if (disp != null) active.add(disp);
        BukkitRunnable r = new BukkitRunnable() {
            final Location pos = from.clone();
            int t = 0;
            @Override
            public void run() {
                try {
                    if (t++ > spec.maxTicks() || pos.getWorld() == null) {
                        finish(pos, true);
                        return;
                    }
                    if (spec.homing() > 0 && homingTarget != null && homingTarget.isValid() && homingTarget.getWorld() == pos.getWorld()) {
                        Vector want = homingTarget.getLocation().add(0, 1.0, 0).toVector().subtract(pos.toVector());
                        if (want.lengthSquared() > 1e-6) {
                            want.normalize().multiply(spec.speed());
                            vel.multiply(1 - spec.homing() * 0.25).add(want.multiply(spec.homing() * 0.25));
                            if (vel.lengthSquared() > 1e-6) vel.normalize().multiply(spec.speed());
                        }
                    }
                    if (spec.gravity() > 0) vel.setY(vel.getY() - spec.gravity());
                    double len = vel.length();
                    if (len < 1e-6) {
                        finish(pos, true);
                        return;
                    }
                    RayTraceResult hit = w.rayTraceBlocks(pos, vel.clone().normalize(), len, FluidCollisionMode.NEVER, true);
                    Location next = pos.clone().add(vel);
                    // 플레이어 판정 (구간 선분)
                    for (Player p : w.getPlayers()) {
                        if (p.getLocation().distanceSquared(pos) > (len + 3) * (len + 3)) continue;
                        if (!isEnemy.test(p)) continue;
                        Location pl = p.getLocation();
                        double r2 = spec.hitRadius() + 0.3;
                        double d2 = Math.min(
                                Geometry.segmentDist2(pos.getX(), pos.getY(), pos.getZ(), next.getX(), next.getY(), next.getZ(),
                                        pl.getX(), pl.getY() + 0.9, pl.getZ()),
                                Geometry.segmentDist2(pos.getX(), pos.getY(), pos.getZ(), next.getX(), next.getY(), next.getZ(),
                                        pl.getX(), pl.getY() + 0.3, pl.getZ()));
                        if (d2 <= r2 * r2) {
                            onHit.accept(p, pos.clone());
                            finish(pos, false);
                            return;
                        }
                    }
                    if (hit != null && hit.getHitBlock() != null) {
                        Location impact = hit.getHitPosition().toLocation(w);
                        finish(impact, true);
                        return;
                    }
                    pos.add(vel);
                    if (disp != null && disp.isValid()) {
                        disp.teleport(pos);
                        if (billboard == Display.Billboard.FIXED && (t % 2 == 0)) {
                            disp.setInterpolationDelay(0);
                            disp.setInterpolationDuration(2);
                            disp.setTransformation(orient(vel, off));
                        }
                    }
                    if (spec.trail() != null && t % 2 == 0) particle(spec.trail(), pos, 1, 0.03, 0.03, 0.03, 0);
                } catch (Throwable ex) {
                    Log.error("몹 투사체 오류", ex);
                    finish(pos, false);
                }
            }
            void finish(Location at, boolean impact) {
                cancel();
                if (disp != null) {
                    disp.remove();
                    active.remove(disp);
                }
                if (impact && onImpact != null) {
                    try {
                        onImpact.accept(at);
                    } catch (Throwable ex) {
                        Log.error("몹 투사체 착탄 오류", ex);
                    }
                }
            }
        };
        tasks.add(r.runTaskTimer(services.plugin(), 1L, 1L));
    }

    private static Display.Billboard billboard(FxModelDef def) {
        if (def == null || def.billboard() == null) return Display.Billboard.CENTER;
        try {
            return Display.Billboard.valueOf(def.billboard().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            return Display.Billboard.CENTER;
        }
    }

    /** 진행 방향을 향하는 Transformation (FIXED 투사체·테더). */
    static Transformation orient(Vector dir, float yawOffset) {
        double h = Math.sqrt(dir.getX() * dir.getX() + dir.getZ() * dir.getZ());
        float yaw = Geometry.yawOf(dir.getX(), dir.getZ());
        float pitch = (float) Math.toDegrees(Math.atan2(-dir.getY(), Math.max(1e-6, h)));
        Quaternionf q = new Quaternionf().rotationY((float) Math.toRadians(-yaw)).rotateX((float) Math.toRadians(pitch));
        if (yawOffset != 0) q.rotateY((float) Math.toRadians(yawOffset));
        return new Transformation(new Vector3f(), q, new Vector3f(1, 1, 1), new Quaternionf());
    }

    // ── 잔류 장판 ────────────────────────────────────────────────────────

    /**
     * 잔류 장판: durationTicks 동안 10틱마다 반경 안 적에게 onTick. fx == null 이면 입자만.
     */
    public void zone(Location center, double radius, int durationTicks, String fx, Color color, Predicate<Player> isEnemy,
                     Consumer<Player> onTick) {
        World w = center.getWorld();
        if (w == null) return;
        ItemDisplay plate = fx == null ? null : spawnPlate(Shape.circle(center, radius), fx);
        BukkitRunnable r = new BukkitRunnable() {
            int t = 0;
            @Override
            public void run() {
                try {
                    if (t >= durationTicks) {
                        cancel();
                        if (plate != null) {
                            plate.remove();
                            active.remove(plate);
                        }
                        return;
                    }
                    if (t % 10 == 0) {
                        Shape s = Shape.circle(center, radius);
                        if (plate == null) outline(s, color, 1.0f);
                        for (Player p : w.getPlayers()) {
                            if (s.contains(p.getLocation()) && isEnemy.test(p)) onTick.accept(p);
                        }
                    }
                    t++;
                } catch (Throwable ex) {
                    Log.error("몹 장판 오류", ex);
                    cancel();
                }
            }
        };
        tasks.add(r.runTaskTimer(services.plugin(), 0L, 1L));
    }

    // ── 테더 ─────────────────────────────────────────────────────────────

    /** 두 엔티티 사이에 늘인 fx 모델 (life_drain·pull). 반환된 디스플레이는 {@link #updateTether} 로 갱신, remove 로 제거. */
    public ItemDisplay tether(String fx, Location a, Location b) {
        if (fx == null || a.getWorld() == null) return null;
        ItemDisplay d = a.getWorld().spawn(a.clone().setDirection(new Vector(0, 0, 1)), ItemDisplay.class, e -> {
            e.setPersistent(false);
            e.setItemStack(ModelRig.modelItem(Key.key(Keys.NS, "fx/" + fx)));
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.FIXED);
            e.setTeleportDuration(2);
            e.setBrightness(new Display.Brightness(12, 15));
            Keys.tagTransient(e, Keys.FX, "tether");
        });
        active.add(d);
        updateTether(d, fx, a, b);
        return d;
    }

    public void updateTether(ItemDisplay d, String fx, Location a, Location b) {
        if (d == null || !d.isValid() || a.getWorld() != b.getWorld()) return;
        Vector v = b.toVector().subtract(a.toVector());
        double len = v.length();
        if (len < 0.05) return;
        FxModelDef def = services.content().fxModels().get(fx);
        double baseLen = def != null && def.size().size() >= 3 && def.size().get(2) > 0 ? def.size().get(2) / 16.0 : 1.0;
        Location mid = a.clone().add(v.clone().multiply(0.5));
        mid.setYaw(0);
        mid.setPitch(0);
        d.teleport(mid);
        Transformation o = orient(v, (float) yawOffset());
        d.setInterpolationDelay(0);
        d.setInterpolationDuration(2);
        d.setTransformation(new Transformation(new Vector3f(), o.getLeftRotation(), new Vector3f(1, 1, (float) (len / baseLen)),
                new Quaternionf()));
    }

    public void discard(Entity e) {
        if (e == null) return;
        e.remove();
        active.remove(e);
    }

    // ── 입자 ─────────────────────────────────────────────────────────────

    /** 데이터가 필요 없는 입자만 안전하게 (잘못된 이름·데이터 형식은 무시). */
    public static void particle(Particle p, Location at, int count, double dx, double dy, double dz, double speed) {
        if (p == null || at.getWorld() == null) return;
        Class<?> type = p.getDataType();
        if (type == Particle.DustOptions.class) {
            at.getWorld().spawnParticle(p, at, count, dx, dy, dz, speed, new Particle.DustOptions(Color.WHITE, 1f));
        } else if (type == Void.class) {
            at.getWorld().spawnParticle(p, at, count, dx, dy, dz, speed);
        }
    }

    public static Particle parseParticle(String name, Particle def) {
        if (name == null || name.isBlank()) return def;
        try {
            Particle p = Particle.valueOf(name.trim().toUpperCase(Locale.ROOT));
            return p.getDataType() == Void.class ? p : def;
        } catch (IllegalArgumentException e) {
            return def;
        }
    }

    public static void dust(Location at, Color c, float size, int count, double spread) {
        if (at.getWorld() == null) return;
        at.getWorld().spawnParticle(Particle.DUST, at, count, spread, spread, spread, 0, new Particle.DustOptions(c, size));
    }

    /** 원형 입자 링. */
    public static void ring(Location c, double r, Particle p, int n) {
        for (int i = 0; i < n; i++) {
            double a = 2 * Math.PI * i / n;
            particle(p, c.clone().add(Math.cos(a) * r, 0.1, Math.sin(a) * r), 1, 0, 0, 0, 0);
        }
    }

    /** 플러그인 종료·리로드 시 모든 효과 정리. */
    public void shutdown() {
        for (BukkitTask t : new ArrayList<>(tasks)) if (!t.isCancelled()) t.cancel();
        tasks.clear();
        for (Entity e : new ArrayList<>(active)) e.remove();
        active.clear();
    }

    /** 끝난 작업 정리 (주기적으로). */
    public void sweep() {
        tasks.removeIf(BukkitTask::isCancelled);
        List<Entity> dead = new ArrayList<>();
        for (Entity e : active) if (!e.isValid()) dead.add(e);
        dead.forEach(active::remove);
    }
}
