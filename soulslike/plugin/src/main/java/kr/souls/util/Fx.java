package kr.souls.util;

import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.SoundCategory;
import org.bukkit.World;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Vector;

import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import java.util.logging.Logger;

/**
 * 파티클/사운드 도우미.
 * 파티클은 "FLAME", "DUST:#ff8800:1.5", "DUST_COLOR_TRANSITION:#ff0000:#ffff00:1.2",
 * "BLOCK:ice", "ITEM:diamond", "ENTITY_EFFECT:#55ffff" 형태의 문자열로 적는다.
 */
public final class Fx {
    private static Logger log = Logger.getLogger("AugmentSkyblock");

    private Fx() {}

    public static void setLogger(Logger l) { log = l; }

    public record Spec(Particle particle, Object data) {
        public void spawn(Location at, int count, double spread, double speed) {
            spawn(at, count, spread, spread, spread, speed);
        }

        /** except 플레이어 화면에는 보내지 않는다 (손에 든 무기 입자가 1인칭 카메라를 가리지 않게). */
        public void spawnExcept(org.bukkit.entity.Player except, Location at, int count, double ox, double oy, double oz, double speed) {
            World w = at.getWorld();
            if (w == null) return;
            for (org.bukkit.entity.Player v : w.getPlayers()) {
                if (v.equals(except) || v.getLocation().distanceSquared(at) > 48 * 48) continue;
                try {
                    v.spawnParticle(particle, at, count, ox, oy, oz, speed, data);
                } catch (Throwable t) {
                    // 데이터 형식이 맞지 않는 파티클은 건너뛴다
                }
            }
        }

        public void spawn(Location at, int count, double ox, double oy, double oz, double speed) {
            World w = at.getWorld();
            if (w == null) return;
            try {
                w.spawnParticle(particle, at, count, ox, oy, oz, speed, data, true);
            } catch (Throwable t) {
                // 데이터 형식이 맞지 않는 파티클이 와도 스킬 전체가 멈추지 않게 한다
            }
        }
    }

    public static final Spec NONE = new Spec(Particle.CRIT, null);

    public static Spec parse(String spec) {
        if (spec == null || spec.isBlank() || spec.equalsIgnoreCase("none")) return null;
        String[] parts = spec.split(":");
        String name = parts[0].trim().toUpperCase(Locale.ROOT);
        Particle p;
        try {
            p = Particle.valueOf(name);
        } catch (IllegalArgumentException e) {
            log.warning("알 수 없는 파티클: " + spec + " (CRIT 으로 대체)");
            return new Spec(Particle.CRIT, null);
        }
        Class<?> type = p.getDataType();
        try {
            if (type == Void.class) return new Spec(p, null);
            if (type == Particle.DustOptions.class) {
                Color c = parts.length > 1 ? color(parts[1]) : Color.WHITE;
                float size = parts.length > 2 ? Float.parseFloat(parts[2]) : 1.0f;
                return new Spec(p, new Particle.DustOptions(c, size));
            }
            if (type == Particle.DustTransition.class) {
                Color a = parts.length > 1 ? color(parts[1]) : Color.WHITE;
                Color b = parts.length > 2 ? color(parts[2]) : a;
                float size = parts.length > 3 ? Float.parseFloat(parts[3]) : 1.0f;
                return new Spec(p, new Particle.DustTransition(a, b, size));
            }
            if (type == Color.class) {
                Color c = parts.length > 1 ? color(parts[1]) : Color.WHITE;
                return new Spec(p, c);
            }
            if (type == org.bukkit.block.data.BlockData.class) {
                Material m = parts.length > 1 ? Material.matchMaterial(parts[1]) : Material.STONE;
                if (m == null || !m.isBlock()) m = Material.STONE;
                return new Spec(p, m.createBlockData());
            }
            if (type == ItemStack.class) {
                Material m = parts.length > 1 ? Material.matchMaterial(parts[1]) : Material.STONE;
                if (m == null) m = Material.STONE;
                return new Spec(p, new ItemStack(m));
            }
            if (type == Float.class) {
                return new Spec(p, parts.length > 1 ? Float.parseFloat(parts[1]) : 1.0f);
            }
            if (type == Integer.class) {
                return new Spec(p, parts.length > 1 ? Integer.parseInt(parts[1]) : 0);
            }
        } catch (Exception e) {
            log.warning("파티클 데이터 해석 실패: " + spec);
        }
        log.warning("데이터가 필요한 파티클은 지원하지 않음: " + spec + " (CRIT 으로 대체)");
        return new Spec(Particle.CRIT, null);
    }

    public static Color color(String hex) {
        String h = hex.trim();
        if (h.startsWith("#")) h = h.substring(1);
        int rgb = Integer.parseInt(h, 16);
        return Color.fromRGB(rgb);
    }

    public static void sound(Location at, String key, float volume, float pitch) {
        if (key == null || key.isBlank() || at.getWorld() == null) return;
        String k = key.toLowerCase(Locale.ROOT).replace('_', '.');
        // YAML 에 ENTITY_BLAZE_SHOOT 처럼 적어도, entity.blaze.shoot 처럼 적어도 되게 한다
        if (key.contains(".")) k = key.toLowerCase(Locale.ROOT);
        at.getWorld().playSound(at, k, SoundCategory.PLAYERS, volume, pitch);
    }

    /** 두 점 사이에 파티클 선을 긋는다. */
    public static void line(Spec spec, Location a, Location b, double step) {
        if (spec == null) return;
        Vector d = b.toVector().subtract(a.toVector());
        double len = d.length();
        if (len < 1e-6) return;
        d.multiply(1.0 / len);
        Location p = a.clone();
        for (double t = 0; t <= len; t += step) {
            spec.spawn(p, 1, 0, 0);
            p.add(d.getX() * step, d.getY() * step, d.getZ() * step);
        }
    }

    /** 수평 원을 그린다. */
    public static void ring(Spec spec, Location center, double radius, int points) {
        if (spec == null) return;
        for (int i = 0; i < points; i++) {
            double a = Math.PI * 2 * i / points;
            Location p = center.clone().add(Math.cos(a) * radius, 0, Math.sin(a) * radius);
            spec.spawn(p, 1, 0, 0);
        }
    }

    /** 하늘에서 떨어지는 지그재그 번개 모양 파티클. 실제 번개 이펙트와 함께 쓴다. */
    public static void bolt(Location target, Spec spec) {
        if (spec == null) spec = new Spec(Particle.ELECTRIC_SPARK, null);
        ThreadLocalRandom r = ThreadLocalRandom.current();
        Location prev = target.clone().add(r.nextDouble(-1, 1), 12, r.nextDouble(-1, 1));
        for (int i = 0; i < 6; i++) {
            Location next = (i == 5) ? target.clone()
                    : target.clone().add(r.nextDouble(-1.2, 1.2), 12 - (i + 1) * 2.0, r.nextDouble(-1.2, 1.2));
            line(spec, prev, next, 0.35);
            prev = next;
        }
    }

    public static boolean isMain() { return Bukkit.isPrimaryThread(); }
}
