package kr.augsky.vfx;

import org.bukkit.Location;
import org.bukkit.util.Vector;

/** 곧 맞을 자리의 모양 (예고 표시용). 원 / 선 / 부채꼴 */
public record Footprint(Shape shape, Location c, Vector dir, double r, double len, double width, double half) {
    public enum Shape { CIRCLE, LINE, CONE }

    public static Footprint circle(Location c, double r) {
        return new Footprint(Shape.CIRCLE, c, null, r, 0, 0, 0);
    }

    public static Footprint line(Location start, Vector dir, double len, double width) {
        return new Footprint(Shape.LINE, start, dir.clone().normalize(), 0, len, width, 0);
    }

    public static Footprint cone(Location base, Vector dir, double half, double range) {
        return new Footprint(Shape.CONE, base, dir.clone().normalize(), range, range, 0, half);
    }

    public boolean contains(Location p) {
        if (p.getWorld() != c.getWorld()) return false;
        return switch (shape) {
            case CIRCLE -> {
                double dx = p.getX() - c.getX(), dz = p.getZ() - c.getZ();
                yield dx * dx + dz * dz <= r * r;
            }
            case LINE -> {
                Vector rel = p.toVector().subtract(c.toVector());
                double along = rel.dot(dir);
                if (along < 0 || along > len) yield false;
                yield rel.subtract(dir.clone().multiply(along)).length() <= width / 2 + 0.5;
            }
            case CONE -> {
                Vector rel = p.toVector().subtract(c.toVector()).setY(0);
                if (rel.length() > r) yield false;
                Vector d = dir.clone().setY(0);
                yield rel.lengthSquared() < 0.25 || d.lengthSquared() < 1e-6 || rel.angle(d) <= half;
            }
        };
    }
}
