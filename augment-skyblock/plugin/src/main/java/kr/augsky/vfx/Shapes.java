package kr.augsky.vfx;

import org.bukkit.Location;
import org.bukkit.util.Vector;
import org.joml.Matrix3f;
import org.joml.Quaternionf;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/** 모양 계산. 모든 점은 (위치, 0~1 진행값) 으로 넘긴다. 진행값은 색 그라데이션·무지개 색상에 쓴다 */
public final class Shapes {
    private Shapes() {}

    @FunctionalInterface
    public interface PointFn {
        void at(Location p, double t);
    }

    /**
     * 직교 좌표계. side = up × fwd (앞을 볼 때 왼쪽), up, fwd.
     * 판 조각(링·마법진)은 side-fwd 평면에 눕고 up 이 법선이다.
     */
    public record Frame(Vector side, Vector up, Vector fwd) {
        public static final Frame FLAT = new Frame(new Vector(1, 0, 0), new Vector(0, 1, 0), new Vector(0, 0, 1));

        /** 바닥에 눕힌 판, 앞은 dir 의 수평 성분 */
        public static Frame flat(Vector dir) {
            Vector f = dir == null ? new Vector(0, 0, 1) : dir.clone().setY(0);
            if (f.lengthSquared() < 1e-6) f = new Vector(0, 0, 1);
            f.normalize();
            Vector up = new Vector(0, 1, 0);
            return new Frame(up.getCrossProduct(f).normalize(), up, f);
        }

        /** fwd 를 앞으로 하는 좌표계 (광선용). up 은 가능한 한 하늘 쪽 */
        public static Frame along(Vector dir) {
            Vector f = dir.clone().normalize();
            Vector ref = Math.abs(f.getY()) > 0.95 ? new Vector(1, 0, 0) : new Vector(0, 1, 0);
            Vector side = ref.getCrossProduct(f).normalize();
            Vector up = f.getCrossProduct(side).normalize();
            return new Frame(side, up, f);
        }

        /** 법선이 n 인 판 (광선에 수직인 고리 등). fwd 는 판 안의 아무 방향 */
        public static Frame normal(Vector n) {
            Frame a = along(n);
            return new Frame(a.side(), a.fwd(), a.up().clone().multiply(-1));
        }

        /** fwd 축을 중심으로 deg 만큼 기울인다 (참격을 비스듬히 세우기) */
        public Frame roll(double deg) {
            double r = Math.toRadians(deg);
            Vector s = side.clone().multiply(Math.cos(r)).add(up.clone().multiply(Math.sin(r)));
            Vector u = up.clone().multiply(Math.cos(r)).subtract(side.clone().multiply(Math.sin(r)));
            return new Frame(s, u, fwd);
        }

        /** side 축을 중심으로 앞을 숙이거나 든다 */
        public Frame pitch(double deg) {
            double r = Math.toRadians(deg);
            Vector f = fwd.clone().multiply(Math.cos(r)).add(up.clone().multiply(Math.sin(r)));
            Vector u = up.clone().multiply(Math.cos(r)).subtract(fwd.clone().multiply(Math.sin(r)));
            return new Frame(side, u, f);
        }

        /** up 축을 중심으로 돈다 */
        public Frame yaw(double deg) {
            double r = Math.toRadians(deg);
            Vector f = fwd.clone().multiply(Math.cos(r)).add(side.clone().multiply(Math.sin(r)));
            Vector s = side.clone().multiply(Math.cos(r)).subtract(fwd.clone().multiply(Math.sin(r)));
            return new Frame(s, up, f);
        }

        /** 모델 축 (X=side, Y=up, Z=fwd) 을 이 좌표계로 돌리는 회전 */
        public Quaternionf quat() {
            Matrix3f m = new Matrix3f(
                    (float) side.getX(), (float) side.getY(), (float) side.getZ(),
                    (float) up.getX(), (float) up.getY(), (float) up.getZ(),
                    (float) fwd.getX(), (float) fwd.getY(), (float) fwd.getZ());
            return new Quaternionf().setFromNormalized(m);
        }

        public Location point(Location c, double s, double u, double f) {
            return c.clone().add(side.getX() * s + up.getX() * u + fwd.getX() * f,
                    side.getY() * s + up.getY() * u + fwd.getY() * f,
                    side.getZ() * s + up.getZ() * u + fwd.getZ() * f);
        }
    }

    /** 판 위의 원. 각도 0 은 fwd 방향 */
    public static void ring(Location c, double r, int n, Frame fr, PointFn fn) {
        n = Math.max(3, n);
        for (int i = 0; i < n; i++) {
            double a = Math.PI * 2 * i / n;
            fn.at(fr.point(c, Math.sin(a) * r, 0, Math.cos(a) * r), i / (double) n);
        }
    }

    /** 원호. a0..a1 (라디안, 0 = fwd, 양수 = side 쪽) */
    public static void arc(Location c, Frame fr, double r, double a0, double a1, int n, PointFn fn) {
        n = Math.max(2, n);
        for (int i = 0; i < n; i++) {
            double t = i / (double) (n - 1);
            double a = a0 + (a1 - a0) * t;
            fn.at(fr.point(c, Math.sin(a) * r, 0, Math.cos(a) * r), t);
        }
    }

    public static void spiral(Location c, double r0, double r1, double turns, double h, int n, double phase, PointFn fn) {
        for (int i = 0; i < n; i++) {
            double t = i / (double) Math.max(1, n - 1);
            double a = phase + t * turns * Math.PI * 2;
            double r = r0 + (r1 - r0) * t;
            fn.at(c.clone().add(Math.cos(a) * r, h * t, Math.sin(a) * r), t);
        }
    }

    public static void helix(Location base, double r, double h, int strands, double turns, int perStrand, double phase, PointFn fn) {
        for (int s = 0; s < strands; s++) {
            double off = phase + Math.PI * 2 * s / strands;
            for (int i = 0; i < perStrand; i++) {
                double t = i / (double) Math.max(1, perStrand - 1);
                double a = off + t * turns * Math.PI * 2;
                fn.at(base.clone().add(Math.cos(a) * r, h * t, Math.sin(a) * r), t);
            }
        }
    }

    /** 피보나치 구 */
    public static void sphere(Location c, double r, int n, PointFn fn) {
        double g = Math.PI * (3 - Math.sqrt(5));
        for (int i = 0; i < n; i++) {
            double y = 1 - (i / (double) Math.max(1, n - 1)) * 2;
            double rr = Math.sqrt(Math.max(0, 1 - y * y));
            double th = g * i;
            fn.at(c.clone().add(Math.cos(th) * rr * r, y * r, Math.sin(th) * rr * r), i / (double) n);
        }
    }

    /** 반구 위쪽 방향들 (분수처럼 뿜기) */
    public static List<Vector> hemisphere(int n) {
        List<Vector> out = new ArrayList<>();
        double g = Math.PI * (3 - Math.sqrt(5));
        for (int i = 0; i < n; i++) {
            double y = 1 - (i / (double) Math.max(1, n - 1));
            double rr = Math.sqrt(Math.max(0, 1 - y * y));
            out.add(new Vector(Math.cos(g * i) * rr, y, Math.sin(g * i) * rr));
        }
        return out;
    }

    public static void line(Location a, Location b, double step, PointFn fn) {
        Vector d = b.toVector().subtract(a.toVector());
        double len = d.length();
        if (len < 1e-6) {
            fn.at(a.clone(), 0);
            return;
        }
        int n = Math.max(1, (int) Math.ceil(len / step));
        for (int i = 0; i <= n; i++) {
            double t = i / (double) n;
            fn.at(a.clone().add(d.clone().multiply(t)), t);
        }
    }

    /** 두 점 사이를 지그재그로 잇는 번개. 꺾이는 점 목록을 돌려준다 */
    public static List<Location> bolt(Location a, Location b, int segments, double jitter, Random rnd) {
        List<Location> pts = new ArrayList<>();
        Vector d = b.toVector().subtract(a.toVector());
        Frame fr = Frame.along(d.lengthSquared() < 1e-6 ? new Vector(0, -1, 0) : d);
        pts.add(a.clone());
        for (int i = 1; i < segments; i++) {
            double t = i / (double) segments;
            double j = jitter * Math.sin(Math.PI * t) + jitter * 0.3;
            Location p = a.clone().add(d.clone().multiply(t));
            pts.add(fr.point(p, (rnd.nextDouble() * 2 - 1) * j, (rnd.nextDouble() * 2 - 1) * j, 0));
        }
        pts.add(b.clone());
        return pts;
    }

    /** 별 모양 다각형 꼭짓점 (바깥/안쪽 번갈아) */
    public static List<Location> star(Location c, int points, double rOut, double rIn, Frame fr, double phase) {
        List<Location> out = new ArrayList<>();
        for (int i = 0; i < points * 2; i++) {
            double a = phase + Math.PI * i / points;
            double r = i % 2 == 0 ? rOut : rIn;
            out.add(fr.point(c, Math.sin(a) * r, 0, Math.cos(a) * r));
        }
        return out;
    }

    /** 원 위의 같은 간격 점 n 개 (수평) */
    public static List<Location> around(Location c, double r, int n, double phase) {
        List<Location> out = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            double a = phase + Math.PI * 2 * i / n;
            out.add(c.clone().add(Math.cos(a) * r, 0, Math.sin(a) * r));
        }
        return out;
    }
}
