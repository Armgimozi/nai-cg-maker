package kr.labyrinth.bosses;

import java.util.function.Consumer;
import kr.labyrinth.core.Log;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.util.Vector;

/**
 * 경고 장판 (GDD §8.1): 바닥에 눕힌 fx ItemDisplay + 윤곽 DUST 입자 → windup 이 끝나는 틱에 {@code onFire} 한 번.
 * 끝나기 6틱(0.3초) 전에 밝게 깜빡여 "곧 터짐" 신호. 블록 변경 없음.
 * {@link #follow(Entity)} 로 대상 발밑을 따라다니게 할 수 있다(흩어지기·모이기 표식의 원).
 */
public final class Telegraph implements Ticking {

    /** 색 규칙 (GDD §8.1). */
    public static final Color RED = Color.fromRGB(255, 59, 59);
    public static final Color ORANGE = Color.fromRGB(255, 138, 42);
    public static final Color PURPLE = Color.fromRGB(192, 58, 208);
    public static final Color YELLOW = Color.fromRGB(255, 214, 74);
    public static final Color BLUE = Color.fromRGB(58, 120, 230);
    public static final Color GREEN = Color.fromRGB(58, 208, 106);

    public enum Kind { CIRCLE, RING, LINE, CONE, ARROW, TILE, SAFE }

    /**
     * 판정 도형. origin = 원 중심 또는 선·부채꼴·화살표 시작점, size = 반경/길이/타일 한 변, width = 선 폭/도넛 안쪽 반경,
     * angle = 부채꼴 각도. 판정은 수평 + 높이 차 ≤ 3.
     */
    public record Shape(Kind kind, Location origin, double dirX, double dirZ, double size, double width, double angle) {
        public static Shape circle(Location c, double r) { return new Shape(Kind.CIRCLE, c.clone(), 0, 1, r, 0, 0); }
        public static Shape safe(Location c, double r) { return new Shape(Kind.SAFE, c.clone(), 0, 1, r, 0, 0); }
        public static Shape ring(Location c, double inner, double r) { return new Shape(Kind.RING, c.clone(), 0, 1, r, inner, 0); }
        public static Shape line(Location o, Vector dir, double length, double width) {
            Vector d = flat(dir);
            return new Shape(Kind.LINE, o.clone(), d.getX(), d.getZ(), length, width, 0);
        }
        public static Shape arrow(Location o, Vector dir, double length, double width) {
            Vector d = flat(dir);
            return new Shape(Kind.ARROW, o.clone(), d.getX(), d.getZ(), length, width, 0);
        }
        public static Shape cone(Location o, Vector dir, double angle, double length) {
            Vector d = flat(dir);
            return new Shape(Kind.CONE, o.clone(), d.getX(), d.getZ(), length, 0, angle);
        }
        /** 타일: origin = 타일 모서리(최소 x,z), size = 한 변. */
        public static Shape tile(Location corner, double size) { return new Shape(Kind.TILE, corner.clone(), 0, 1, size, 0, 0); }

        private static Vector flat(Vector dir) {
            Vector d = new Vector(dir.getX(), 0, dir.getZ());
            return d.lengthSquared() < 1e-9 ? new Vector(0, 0, 1) : d.normalize();
        }

        public Vector direction() { return new Vector(dirX, 0, dirZ); }

        public Shape at(Location newOrigin) { return new Shape(kind, newOrigin.clone(), dirX, dirZ, size, width, angle); }

        public boolean contains(Location p) {
            if (p == null || p.getWorld() != origin.getWorld() || !BossMath.heightOk(origin.getY(), p.getY())) return false;
            double ox = origin.getX(), oz = origin.getZ(), px = p.getX(), pz = p.getZ();
            return switch (kind) {
                case CIRCLE, SAFE -> BossMath.inCircle(ox, oz, size, px, pz);
                case RING -> BossMath.inRing(ox, oz, width, size, px, pz);
                case LINE, ARROW -> BossMath.inLine(ox, oz, dirX, dirZ, size, width, px, pz);
                case CONE -> BossMath.inCone(ox, oz, dirX, dirZ, angle, size, px, pz);
                case TILE -> px >= ox && px < ox + size && pz >= oz && pz < oz + size;
            };
        }

        String model() {
            return switch (kind) {
                case CIRCLE -> "telegraph_circle";
                case SAFE -> "telegraph_safe";
                case RING -> "telegraph_ring";
                case LINE -> "telegraph_line";
                case ARROW -> "telegraph_arrow";
                case CONE -> "telegraph_cone";
                case TILE -> "telegraph_tile";
            };
        }
    }

    private final BossFx fx;
    private Shape shape;
    private final int total;
    private final Color color;
    private final Runnable onFire;
    private final ItemDisplay plate;
    private Entity follow;
    private Consumer<Telegraph> onTick;
    private int t;
    private boolean flashed;
    private boolean done;
    private boolean outline = true;

    /** @param model fx 모델 id (null = 도형 기본 모델, "" = 입자만) */
    public Telegraph(BossFx fx, Shape shape, int ticks, Color color, String model, Runnable onFire) {
        this.fx = fx;
        this.shape = shape;
        this.total = Math.max(1, ticks);
        this.color = color;
        this.onFire = onFire;
        this.plate = "".equals(model) ? null : fx.plate(shape, model == null ? shape.model() : model);
    }

    /** 대상 발밑을 따라가게 (원·안전지대 전용). */
    public Telegraph follow(Entity e) {
        this.follow = e;
        return this;
    }

    /** 매 틱 부가 동작 (예: 화살표가 대상 쪽으로 계속 돌아감). */
    public Telegraph onTick(Consumer<Telegraph> c) {
        this.onTick = c;
        return this;
    }

    public Telegraph noOutline() {
        this.outline = false;
        return this;
    }

    public Shape shape() { return shape; }

    public int elapsed() { return t; }

    public int total() { return total; }

    /** 도형 갱신 (같은 종류 — 위치·방향만). 판정은 발동 시점 도형으로. */
    public void reshape(Shape s) {
        this.shape = s;
        fx.movePlate(plate, s);
    }

    @Override
    public boolean tick(long now) {
        if (done) return true;
        try {
            if (follow != null) {
                if (!follow.isValid()) {
                    cancel();
                    return true;
                }
                Location l = follow.getLocation();
                Location o = shape.origin();
                Location next = new Location(o.getWorld(), l.getX(), fx.groundY(l), l.getZ());
                if (next.distanceSquared(o) > 0.0025) reshape(shape.at(next));
            }
            if (onTick != null) onTick.accept(this);
            boolean late = t >= total - 6;
            if (outline && t % 4 == 0) fx.outline(shape, color, late ? 1.5f : 1.0f);
            if (!flashed && late && plate != null && plate.isValid()) {
                flashed = true;
                plate.setGlowing(true);
                plate.setGlowColorOverride(color);
                plate.setBrightness(new Display.Brightness(15, 15));
            }
            if (t >= total) {
                done = true;
                fx.discard(plate);
                try {
                    if (onFire != null) onFire.run();
                } catch (Throwable ex) {
                    Log.error("보스 패턴 발동 오류", ex);
                }
                return true;
            }
            t++;
            return false;
        } catch (Throwable ex) {
            Log.error("경고 장판 오류", ex);
            cancel();
            return true;
        }
    }

    @Override
    public void cancel() {
        done = true;
        fx.discard(plate);
    }
}
