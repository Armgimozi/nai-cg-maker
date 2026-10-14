package kr.labyrinth.bosses;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.function.IntFunction;
import java.util.function.Supplier;
import kr.labyrinth.core.Log;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * 공용 패턴 부품 (GDD §8.2) 중 {@link Ticking} 으로 도는 것: 지연 실행, 반복 실행, 잔류 장판(ZoneLevel 류 포함),
 * 머리 위 표식(Marker), 경로 투사체(Projectile — 직선·포물선·왕복), 테더(Tether).
 * 판정 대상 목록은 보스가 넘겨 준다(TargetFilter·아레나 경계 통과한 플레이어).
 */
public final class Mechanics {

    private Mechanics() {}

    /** ticks 뒤 한 번 실행. */
    public static final class Delay implements Ticking {
        private final long at;
        private final Runnable r;
        private final boolean phaseBound;
        private boolean done;

        public Delay(long now, int ticks, Runnable r, boolean phaseBound) {
            this.at = now + Math.max(0, ticks);
            this.r = r;
            this.phaseBound = phaseBound;
        }

        @Override
        public boolean tick(long now) {
            if (done) return true;
            if (now < at) return false;
            done = true;
            try {
                r.run();
            } catch (Throwable t) {
                Log.error("보스 지연 동작 오류", t);
            }
            return true;
        }

        @Override
        public void cancel() { done = true; }

        @Override
        public boolean phaseBound() { return phaseBound; }
    }

    /** durationTicks 동안 period 틱마다 실행 (t = 경과 틱). onEnd 는 정상 종료·취소 모두에서 한 번. */
    public static final class Repeat implements Ticking {
        private final int duration;
        private final int period;
        private final IntFunction<Boolean> body;
        private final Runnable onEnd;
        private final boolean phaseBound;
        private int t;
        private boolean done;

        /** body 가 false 를 돌려주면 즉시 끝. */
        public Repeat(int durationTicks, int period, IntFunction<Boolean> body, Runnable onEnd, boolean phaseBound) {
            this.duration = durationTicks;
            this.period = Math.max(1, period);
            this.body = body;
            this.onEnd = onEnd;
            this.phaseBound = phaseBound;
        }

        @Override
        public boolean tick(long now) {
            if (done) return true;
            try {
                if (t % period == 0 && !Boolean.TRUE.equals(body.apply(t))) {
                    finish();
                    return true;
                }
            } catch (Throwable ex) {
                Log.error("보스 반복 동작 오류", ex);
                finish();
                return true;
            }
            t++;
            if (duration > 0 && t > duration) {
                finish();
                return true;
            }
            return false;
        }

        private void finish() {
            if (done) return;
            done = true;
            if (onEnd != null) {
                try {
                    onEnd.run();
                } catch (Throwable ex) {
                    Log.error("보스 반복 동작 종료 오류", ex);
                }
            }
        }

        @Override
        public void cancel() { finish(); }

        @Override
        public boolean phaseBound() { return phaseBound; }
    }

    /**
     * 잔류 장판 (독 웅덩이·쇳물·감염): 도형 위 플레이어에게 period 틱마다 onTick. 모델 판은 끝날 때 제거.
     */
    public static final class Zone implements Ticking {
        private final BossFx fx;
        private final Telegraph.Shape shape;
        private final int duration;
        private final int period;
        private final Supplier<List<Player>> players;
        private final Consumer<Player> onTick;
        private final ItemDisplay plate;
        private final Color color;
        private final Particle particle;
        private int t;
        private boolean done;

        public Zone(BossFx fx, Telegraph.Shape shape, int durationTicks, int period, String model, Color color, Particle particle,
                    Supplier<List<Player>> players, Consumer<Player> onTick) {
            this.fx = fx;
            this.shape = shape;
            this.duration = durationTicks;
            this.period = Math.max(1, period);
            this.players = players;
            this.onTick = onTick;
            this.color = color;
            this.particle = particle;
            this.plate = model == null ? null : fx.plate(shape, model);
        }

        public Telegraph.Shape shape() { return shape; }

        @Override
        public boolean tick(long now) {
            if (done) return true;
            try {
                if (t % period == 0) {
                    for (Player p : players.get()) if (shape.contains(p.getLocation())) onTick.accept(p);
                }
                if (t % 8 == 0) {
                    if (plate == null && color != null) fx.outline(shape, color, 0.9f);
                    if (particle != null) {
                        Location c = shape.origin().clone().add(0, 0.2, 0);
                        double r = shape.kind() == Telegraph.Kind.LINE ? 0.5 : Math.max(0.5, shape.size() * 0.6);
                        if (shape.kind() == Telegraph.Kind.LINE) {
                            Vector d = shape.direction();
                            for (double f = 0; f < shape.size(); f += 2.5) BossFx.particle(particle, c.clone().add(d.clone().multiply(f)), 1, 0.4, 0.1, 0.4, 0.01);
                        } else {
                            BossFx.particle(particle, c, 3, r, 0.1, r, 0.01);
                        }
                    }
                }
            } catch (Throwable ex) {
                Log.error("보스 장판 오류", ex);
                cancel();
                return true;
            }
            if (++t > duration) {
                cancel();
                return true;
            }
            return false;
        }

        @Override
        public void cancel() {
            done = true;
            fx.discard(plate);
        }

        @Override
        public boolean phaseBound() { return false; }
    }

    /** 머리 위 표식 (marker_*): 대상을 따라다니다 ticks 뒤 onExpire(대상). 대상이 사라지면 조용히 끝. */
    public static final class Marker implements Ticking {
        private final BossFx fx;
        private final Entity target;
        private final ItemDisplay display;
        private final int duration;
        private final double height;
        private final Consumer<Entity> onExpire;
        private int t;
        private boolean done;

        public Marker(BossFx fx, String model, Entity target, int ticks, Consumer<Entity> onExpire) {
            this.fx = fx;
            this.target = target;
            this.duration = Math.max(1, ticks);
            this.onExpire = onExpire;
            this.height = target.getHeight() + 0.75;
            this.display = fx.model(model, target.getLocation().add(0, height, 0), 1.4f, Display.Billboard.CENTER);
            if (display != null) display.setBrightness(new Display.Brightness(15, 15));
        }

        public Entity target() { return target; }

        public int remaining() { return duration - t; }

        @Override
        public boolean tick(long now) {
            if (done) return true;
            if (!target.isValid() || (target instanceof Player p && !p.isOnline())) {
                cancel();
                return true;
            }
            if (display != null && display.isValid()) {
                Location at = target.getLocation().add(0, height + 0.08 * Math.sin(t * 0.3), 0);
                at.setYaw(0);
                at.setPitch(0);
                display.teleport(at);
            }
            if (++t >= duration) {
                done = true;
                fx.discard(display);
                try {
                    if (onExpire != null) onExpire.accept(target);
                } catch (Throwable ex) {
                    Log.error("보스 표식 만료 오류", ex);
                }
                return true;
            }
            return false;
        }

        @Override
        public void cancel() {
            done = true;
            fx.discard(display);
        }
    }

    /**
     * 경로 투사체: path(t) 가 t 틱째 위치(월드). ticks 동안 이동하며 hitRadius 안의 플레이어를 경로마다 한 번 onHit,
     * 끝나면 onEnd(마지막 위치). stopOnBlock = 고체 블록에 닿으면 그 자리에서 끝.
     */
    public static final class Projectile implements Ticking {
        private final BossFx fx;
        private final IntFunction<Location> path;
        private final int ticks;
        private final double hitRadius;
        private final boolean stopOnBlock;
        private final Supplier<List<Player>> players;
        private final Consumer<Player> onHit;
        private final Consumer<Location> onEnd;
        private final ItemDisplay display;
        private final float scale;
        private final Particle trail;
        private final Set<UUID> hit = new HashSet<>();
        private Location last;
        private int t;
        private boolean done;
        private boolean resetHitsAt;
        private int resetTick = -1;

        public Projectile(BossFx fx, String model, float scale, IntFunction<Location> path, int ticks, double hitRadius, boolean stopOnBlock,
                          Particle trail, Supplier<List<Player>> players, Consumer<Player> onHit, Consumer<Location> onEnd) {
            this.fx = fx;
            this.path = path;
            this.ticks = Math.max(1, ticks);
            this.hitRadius = hitRadius;
            this.stopOnBlock = stopOnBlock;
            this.players = players;
            this.onHit = onHit;
            this.onEnd = onEnd;
            this.scale = scale;
            this.trail = trail;
            this.last = path.apply(0);
            this.display = model == null ? null : fx.model(model, last, scale, Display.Billboard.FIXED);
        }

        /** 왕복 투사체: 이 틱부터 같은 플레이어를 다시 맞힐 수 있다. */
        public Projectile resetHitsAt(int tick) {
            this.resetTick = tick;
            this.resetHitsAt = true;
            return this;
        }

        @Override
        public boolean tick(long now) {
            if (done) return true;
            try {
                t++;
                if (resetHitsAt && t == resetTick) hit.clear();
                Location pos = path.apply(Math.min(t, ticks));
                if (pos.getWorld() == null) {
                    cancel();
                    return true;
                }
                if (stopOnBlock && pos.getBlock().getType().isSolid()) {
                    finish(last);
                    return true;
                }
                for (Player p : players.get()) {
                    if (hit.contains(p.getUniqueId())) continue;
                    Location pl = p.getLocation();
                    double r = hitRadius + 0.3;
                    double d2 = Math.min(seg2(last, pos, pl.clone().add(0, 0.9, 0)), seg2(last, pos, pl.clone().add(0, 0.2, 0)));
                    if (d2 <= r * r) {
                        hit.add(p.getUniqueId());
                        onHit.accept(p);
                    }
                }
                if (display != null && display.isValid()) {
                    Vector v = pos.toVector().subtract(last.toVector());
                    Location at = pos.clone();
                    at.setYaw(0);
                    at.setPitch(0);
                    display.teleport(at);
                    if (v.lengthSquared() > 1e-6) fx.orient(display, v, scale, scale, 1);
                }
                if (trail != null && t % 2 == 0) BossFx.particle(trail, pos, 1, 0.05, 0.05, 0.05, 0);
                last = pos;
                if (t >= ticks) {
                    finish(pos);
                    return true;
                }
                return false;
            } catch (Throwable ex) {
                Log.error("보스 투사체 오류", ex);
                cancel();
                return true;
            }
        }

        private static double seg2(Location a, Location b, Location p) {
            double vx = b.getX() - a.getX(), vy = b.getY() - a.getY(), vz = b.getZ() - a.getZ();
            double l2 = vx * vx + vy * vy + vz * vz;
            double t = l2 < 1e-9 ? 0 : Math.max(0, Math.min(1,
                    ((p.getX() - a.getX()) * vx + (p.getY() - a.getY()) * vy + (p.getZ() - a.getZ()) * vz) / l2));
            double dx = a.getX() + vx * t - p.getX(), dy = a.getY() + vy * t - p.getY(), dz = a.getZ() + vz * t - p.getZ();
            return dx * dx + dy * dy + dz * dz;
        }

        private void finish(Location at) {
            done = true;
            fx.discard(display);
            if (onEnd != null) {
                try {
                    onEnd.accept(at);
                } catch (Throwable ex) {
                    Log.error("보스 투사체 착탄 오류", ex);
                }
            }
        }

        @Override
        public void cancel() {
            done = true;
            fx.discard(display);
        }

        /** 직선 경로. */
        public static IntFunction<Location> straight(Location from, Vector dir, double speedPerTick) {
            Vector d = dir.clone().normalize().multiply(speedPerTick);
            return t -> from.clone().add(d.clone().multiply(t));
        }

        /** 포물선 경로: ticks 틱 동안 from → to, 최고 높이 apex. */
        public static IntFunction<Location> lob(Location from, Location to, int ticks, double apex) {
            return t -> {
                double f = Math.min(1.0, t / (double) Math.max(1, ticks));
                Location l = from.clone().add(to.toVector().subtract(from.toVector()).multiply(f));
                l.add(0, 4 * apex * f * (1 - f), 0);
                return l;
            };
        }

        /** 왕복 경로: outTicks 동안 나갔다가, pause 틱 멈췄다가, 같은 선으로 돌아온다. */
        public static IntFunction<Location> boomerang(Location from, Vector dir, double length, int outTicks, int pause) {
            Vector d = dir.clone().setY(0).normalize();
            return t -> {
                double f;
                if (t <= outTicks) f = t / (double) outTicks;
                else if (t <= outTicks + pause) f = 1;
                else f = Math.max(0, 1 - (t - outTicks - pause) / (double) outTicks);
                return from.clone().add(d.clone().multiply(length * f));
            };
        }
    }

    /** 두 위치 공급자 사이 늘인 테더 디스플레이. onTick 이 false 를 돌려주면 끝. */
    public static final class Tether implements Ticking {
        private final BossFx fx;
        private final String model;
        private final Supplier<Location> a, b;
        private final ItemDisplay display;
        private final IntFunction<Boolean> onTick;
        private int t;
        private boolean done;

        public Tether(BossFx fx, String model, Supplier<Location> a, Supplier<Location> b, IntFunction<Boolean> onTick) {
            this.fx = fx;
            this.model = model;
            this.a = a;
            this.b = b;
            this.onTick = onTick;
            this.display = fx.tether(model, a.get(), b.get());
        }

        public double length() {
            Location la = a.get(), lb = b.get();
            return la.getWorld() == lb.getWorld() ? la.distance(lb) : 0;
        }

        public ItemDisplay display() { return display; }

        @Override
        public boolean tick(long now) {
            if (done) return true;
            try {
                fx.updateTether(display, model, a.get(), b.get());
                if (!Boolean.TRUE.equals(onTick.apply(t++))) {
                    cancel();
                    return true;
                }
                return false;
            } catch (Throwable ex) {
                Log.error("보스 테더 오류", ex);
                cancel();
                return true;
            }
        }

        @Override
        public void cancel() {
            done = true;
            fx.discard(display);
        }
    }
}
