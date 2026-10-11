package kr.augsky.vfx;

import kr.augsky.util.Fx;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.util.Vector;

import java.util.EnumSet;
import java.util.Set;

/**
 * 입자 보내기. 받는 사람마다 따로 보내서
 * (1) 시전자 눈앞을 가리는 점은 시전자에게만 빼고, (2) 받는 사람 한 명당 한 틱 패킷 수를 묶어 둔다.
 */
public final class Emit {
    public static final int DETAIL = 0, NORMAL = 1, YAML = 2, TELE = 3;
    static final double RANGE = 48;
    private static final double COS35 = Math.cos(Math.toRadians(35));
    /** 가까이서 화면을 크게 덮는 입자 */
    private static final Set<Particle> BULKY = EnumSet.of(Particle.TOTEM_OF_UNDYING, Particle.POOF, Particle.CLOUD,
            Particle.LARGE_SMOKE, Particle.EXPLOSION, Particle.EXPLOSION_EMITTER, Particle.SQUID_INK,
            Particle.CAMPFIRE_COSY_SMOKE, Particle.WHITE_SMOKE, Particle.SONIC_BOOM, Particle.SWEEP_ATTACK,
            Particle.GUST, Particle.SNEEZE, Particle.GLOW_SQUID_INK);

    /** 오래 떠 있는 밝은 입자 (3초 가까이 남는다) */
    private static final Set<Particle> LINGER = EnumSet.of(Particle.FIREWORK, Particle.END_ROD, Particle.TOTEM_OF_UNDYING,
            Particle.WAX_ON, Particle.WAX_OFF, Particle.GLOW, Particle.SNOWFLAKE, Particle.CHERRY_LEAVES, Particle.SCULK_SOUL,
            Particle.HAPPY_VILLAGER, Particle.COMPOSTER, Particle.SOUL);

    private Emit() {}

    static boolean lingers(Particle p) {
        return LINGER.contains(p);
    }

    public static void send(CastFx fx, Location at, Particle p, Object data, int count, double ox, double oy, double oz,
                            double speed, int pri) {
        World w = at.getWorld();
        if (w == null) return;
        if (p == Particle.FLASH) {
            flash(fx, at);
            return;
        }
        for (Vfx.Viewer v : fx.vfx.viewers()) {
            if (v.w != w) continue;
            if (fx.aud == CastFx.AUD_NOPACK && v.pack) continue;
            if (fx.aud == CastFx.AUD_PACK && !v.pack) continue;
            if (fx.aud == CastFx.AUD_SELF && v.p != fx.cp) continue;
            if (fx.aud == CastFx.AUD_OTHERS && v.p == fx.cp) continue;
            double d2 = v.dist2(at);
            if (d2 > RANGE * RANGE) continue;
            Object d = data;
            boolean self = fx.cp != null && v.p == fx.cp;
            double near = self ? 1.69 : 0.8;
            if (d2 < near && pri != TELE) continue;
            if (self && d2 < 5.76 && pri != TELE) {
                // 시전자 시선 35도 안, 2.4칸 안쪽은 화면 한가운데를 가린다
                Vector to = at.toVector().subtract(v.eye);
                double len = Math.sqrt(d2);
                if (len > 1e-6 && to.dot(v.look) / len > COS35) continue;
            }
            if (self && pri != TELE) {
                // 시전자 몸에서 바깥으로 뿜는 입자(count 0 = 방향)는 출발점이 멀어도 카메라를 뚫고 지나가며,
                // 넓게 퍼뜨린 오래 남는 반짝이는 눈앞에 떠서 1인칭 화면을 덮는다
                if ((count == 0 || p == Particle.TRAIL) && d2 < 9) continue;
                double spr = Math.max(Math.abs(ox), Math.max(Math.abs(oy), Math.abs(oz)));
                if (count > 1 && spr > 0.8 && LINGER.contains(p)) {
                    double reach = 1.3 + 1.6 * spr;
                    if (d2 < reach * reach) continue;
                }
                // 오래 떠 있는 밝은 입자(END_ROD·불꽃놀이·눈송이...)는 시전자 눈 4~5칸 안에서 커다란 흰 얼룩이 된다
                if (LINGER.contains(p) && d2 < (pri == YAML ? 16 : 25)) continue;
                // 토템 입자는 몸에서 사방으로 빠르게 튀어 카메라를 뚫고 지나간다
                if (p == Particle.TOTEM_OF_UNDYING && d2 < 36) continue;
            }
            double bulkyR2 = self ? 6.25 : 2.6;
            if (d2 < bulkyR2 && BULKY.contains(p) && pri != TELE) continue;
            double shrinkR2 = self ? 9 : 4;
            if (d2 < shrinkR2) d = shrink(d, Math.sqrt(d2) / Math.sqrt(shrinkR2));
            if (!fx.allow(v, pri)) continue;
            try {
                v.p.spawnParticle(p, at, count, ox, oy, oz, speed, d, pri != DETAIL);
            } catch (Throwable t) {
                // 데이터가 맞지 않는 입자는 건너뛴다
            }
        }
    }

    /** 눈 가까운 큰 먼지는 거리 비례로 작게 (1인칭 얼룩 방지) */
    private static Object shrink(Object d, double k) {
        k = Math.max(0.25, Math.min(1, k));
        if (d instanceof Particle.DustOptions o) return new Particle.DustOptions(o.getColor(), (float) Math.max(0.3, o.getSize() * k));
        if (d instanceof Particle.DustTransition t)
            return new Particle.DustTransition(t.getColor(), t.getToColor(), (float) Math.max(0.3, t.getSize() * k));
        return d;
    }

    public static void spec(CastFx fx, Fx.Spec s, Location at, int count, double spread, double speed, int pri) {
        if (s == null) return;
        send(fx, at, s.particle(), s.data(), count, spread, spread, spread, speed, pri);
    }

    public static void spec(CastFx fx, Fx.Spec s, Location at, int count, double ox, double oy, double oz, double speed, int pri) {
        if (s == null) return;
        send(fx, at, s.particle(), s.data(), count, ox, oy, oz, speed, pri);
    }

    public static void dust(CastFx fx, Location at, Color c, double size, int pri) {
        send(fx, at, Particle.DUST, new Particle.DustOptions(c, (float) size), 1, 0, 0, 0, 0, pri);
    }

    public static void dust(CastFx fx, Location at, Color c, double size, int n, double spread, int pri) {
        send(fx, at, Particle.DUST, new Particle.DustOptions(c, (float) size), n, spread, spread, spread, 0, pri);
    }

    public static void trans(CastFx fx, Location at, Color c1, Color c2, double size, int pri) {
        send(fx, at, Particle.DUST_COLOR_TRANSITION, new Particle.DustTransition(c1, c2, (float) size), 1, 0, 0, 0, 0, pri);
    }

    /** TRAIL 은 목표로 날아가는 점 하나다. 선처럼 보이게 하려면 streak 을 쓴다 */
    public static void trail(CastFx fx, Location from, Location to, Color c, int dur, int pri) {
        if (from.getWorld() != to.getWorld()) return;
        send(fx, from, Particle.TRAIL, new Particle.Trail(to, c, Math.max(1, dur)), 1, 0, 0, 0, 0, pri);
    }

    /** 선분을 따라 시작점을 엇갈린 TRAIL 여러 개 → 짧은 빛줄기 */
    public static void streak(CastFx fx, Location from, Location to, Color c, int n, int dur, int pri) {
        Vector d = to.toVector().subtract(from.toVector());
        for (int i = 0; i < n; i++) {
            double t = i / (double) Math.max(1, n);
            trail(fx, from.clone().add(d.clone().multiply(t)), to, c, Math.max(1, (int) Math.round(dur * (1 - t))), pri);
        }
    }

    /** 한 방향으로 쏘는 입자 (count 0 = 오프셋이 속도) */
    public static void dir(CastFx fx, Location at, Particle p, Object data, Vector v, double speed, int pri) {
        send(fx, at, p, data, 0, v.getX(), v.getY(), v.getZ(), speed, pri);
    }

    public static void dir(CastFx fx, Location at, Fx.Spec s, Vector v, double speed, int pri) {
        if (s == null) return;
        // DUST 처럼 방향이 안 먹는 입자도 있지만 그대로 보낸다
        send(fx, at, s.particle(), s.data(), 0, v.getX(), v.getY(), v.getZ(), speed, pri);
    }

    public static void block(CastFx fx, Location at, org.bukkit.Material m, int n, double spread, int pri) {
        if (!m.isBlock()) return;
        send(fx, at, Particle.BLOCK, m.createBlockData(), n, spread, spread, spread, 0.1, pri);
    }

    public static void line(CastFx fx, Location a, Location b, double step, Color c, double size, int pri) {
        Shapes.line(a, b, step, (p, t) -> dust(fx, p, c, size, pri));
    }

    /**
     * 섬광(FLASH)은 색을 못 바꾸고 14칸 크기로 화면을 하얗게 덮는다. 낮에는 계단진 허연 반원(유령 돔)으로 보여서
     * 팩을 받은 사람에게는 보내지 않는다 (그 자리에는 큰 별 조각이 있다). 팩이 없는 사람에게만,
     * 시전자 제외, 10칸 밖에서만, 한 사람에게 0.5초에 한 번만.
     */
    public static void flash(CastFx fx, Location at) {
        if (!fx.mayFlash()) return;
        for (Vfx.Viewer v : fx.vfx.viewers()) {
            if (v.w != at.getWorld() || v.p == fx.cp || v.pack) continue;
            double d2 = v.dist2(at);
            if (d2 < 100 || d2 > 96 * 96) continue;
            Long last = fx.vfx.lastFlash.get(v.id);
            if (last != null && fx.vfx.tick - last < 10) continue;
            fx.vfx.lastFlash.put(v.id, fx.vfx.tick);
            try {
                v.p.spawnParticle(Particle.FLASH, at, 1, 0, 0, 0, 0, null, true);
            } catch (Throwable ignored) {
                // 무시
            }
        }
    }
}
