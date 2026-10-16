package kr.labyrinth.pvp;

import java.io.File;
import java.util.List;
import java.util.UUID;
import kr.labyrinth.core.Log;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 마을 안전지대 (PvP 금지). 마을 기능(VILLAGE.md §4.2)이 주 월드 폴더에 남기는 {@code labyrinth-village.yml} 의
 * {@code center: [x, y, z]} · {@code radius} 만 읽는다 — 마을 코드에 의존하지 않는 느슨한 연결이라 파일이 없으면 안전지대도 없다.
 * 0.3.6.1: 같은 폴더의 구역 기록 {@code labyrinth-district-*.yml} (광산 마을) 이 {@code state: built|building} 이면 그 보호 상자
 * (+ {@code safe_margin}, 기본 8칸) 도 안전지대다 — 승강장·제련소 앞에서도 싸울 수 없다 (CONTRACT §2.13).
 * 마을을 서버가 켜진 중에 지어도 반영되도록 10초마다 파일 수정 시각을 확인한다.
 */
final class VillageZone {

    static final String FILE = "labyrinth-village.yml";
    private static final long RECHECK_MS = 10_000;

    /** 안전지대: 마을 원기둥 + 구역 상자들 [x0, z0, x1, x2] (블록 모서리 기준, 높이 무관). */
    record Zone(UUID world, double x, double z, double radius, List<double[]> rects) {
        Zone(UUID world, double x, double z, double radius) { this(world, x, z, radius, List.of()); }

        boolean contains(UUID worldId, double px, double pz) {
            if (!world.equals(worldId)) return false;
            if (within(x, z, radius, px, pz)) return true;
            for (double[] r : rects) if (px >= r[0] && px <= r[2] && pz >= r[1] && pz <= r[3]) return true;
            return false;
        }

        Zone withRects(List<double[]> more) {
            List<double[]> all = new java.util.ArrayList<>(rects);
            all.addAll(more);
            return new Zone(world, x, z, radius, List.copyOf(all));
        }
    }

    /** 구역 기록 파일 이름 (labyrinth-district-<id>.yml). */
    static boolean districtFile(String name) { return name.startsWith("labyrinth-district-") && name.endsWith(".yml"); }

    /**
     * 구역 기록 → 안전 상자들. state 가 built·building 일 때만, protect 상자마다 safe_margin(없으면 8) 만큼 넓힌다.
     * 땅 블록 x0..x1 은 x0 ~ x1+1 을 덮는다.
     */
    static List<double[]> parseDistrict(YamlConfiguration y) {
        if (y == null) return List.of();
        String state = y.getString("state", "built");
        if (!"built".equalsIgnoreCase(state) && !"building".equalsIgnoreCase(state)) return List.of();
        int m = Math.max(0, y.getInt("safe_margin", 8));
        List<double[]> out = new java.util.ArrayList<>();
        for (Object o : y.getList("protect", List.of())) {
            if (!(o instanceof List<?> l) || l.size() < 6) continue;
            try {
                double x0 = ((Number) l.get(0)).doubleValue(), z0 = ((Number) l.get(2)).doubleValue();
                double x1 = ((Number) l.get(3)).doubleValue(), z1 = ((Number) l.get(5)).doubleValue();
                out.add(new double[] {Math.min(x0, x1) - m, Math.min(z0, z1) - m, Math.max(x0, x1) + 1 + m, Math.max(z0, z1) + 1 + m});
            } catch (ClassCastException | NullPointerException e) {
                // 형식이 다른 상자는 건너뜀
            }
        }
        return out;
    }

    private Zone zone;
    private long checkedAt;
    private long fileStamp = Long.MIN_VALUE;
    private int margin = -1;

    /** 수평 거리 r 안인가 (경계 포함). */
    static boolean within(double cx, double cz, double r, double x, double z) {
        double dx = x - cx, dz = z - cz;
        return r > 0 && dx * dx + dz * dz <= r * r;
    }

    /** labyrinth-village.yml 내용 → 안전지대 (center·radius 가 없거나 이상하면 null). */
    static Zone parse(YamlConfiguration y, UUID world, int margin) {
        if (y == null || world == null) return null;
        List<?> c = y.getList("center");
        double radius = y.getDouble("radius", -1);
        if (c == null || c.size() < 3 || radius <= 0) return null;
        try {
            double x = ((Number) c.get(0)).doubleValue();
            double z = ((Number) c.get(2)).doubleValue();
            return new Zone(world, x + 0.5, z + 0.5, radius + Math.max(0, margin));
        } catch (ClassCastException | NullPointerException e) {
            return null;
        }
    }

    /** 다음 조회 때 파일을 다시 읽는다 (/labadmin reload). */
    void invalidate() {
        checkedAt = 0;
        fileStamp = Long.MIN_VALUE;
    }

    boolean contains(Location l, int margin) {
        if (l == null || l.getWorld() == null) return false;
        Zone z = current(margin);
        return z != null && z.contains(l.getWorld().getUID(), l.getX(), l.getZ());
    }

    /** 현재 안전지대 (없으면 null). */
    Zone current(int margin) {
        long now = System.currentTimeMillis();
        if (margin != this.margin) invalidate();
        if (now - checkedAt < RECHECK_MS) return zone;
        checkedAt = now;
        this.margin = margin;
        List<World> worlds = Bukkit.getWorlds();
        if (worlds.isEmpty()) return zone = null;
        World main = worlds.get(0);
        File f = new File(main.getWorldFolder(), FILE);
        File[] districts = main.getWorldFolder().listFiles((d, n) -> districtFile(n));
        long stamp = f.isFile() ? f.lastModified() ^ f.length() : -1;
        if (stamp != -1 && districts != null) for (File d : districts) stamp = stamp * 31 + (d.lastModified() ^ d.length());
        if (stamp == fileStamp) return zone;
        fileStamp = stamp;
        if (stamp == -1) return zone = null;
        try {
            zone = parse(YamlConfiguration.loadConfiguration(f), main.getUID(), margin);
            if (zone != null && districts != null) {
                for (File d : districts) zone = zone.withRects(parseDistrict(YamlConfiguration.loadConfiguration(d)));
            }
            if (zone != null) {
                Log.info("PvP 안전지대: 마을 중심 (" + Math.round(zone.x()) + ", " + Math.round(zone.z()) + ") 반경 "
                        + Math.round(zone.radius()) + "칸" + (zone.rects().isEmpty() ? "" : " + 광산 마을 상자 " + zone.rects().size() + "개")
                        + " — 이 안에서는 플레이어끼리 싸울 수 없습니다.");
            } else {
                Log.warn(FILE + " 에 center/radius 가 없어 마을 PvP 안전지대를 쓰지 않습니다.");
            }
        } catch (Throwable t) {
            zone = null;
            Log.warn(FILE + " 읽기 실패 — 마을 PvP 안전지대 없음 (" + t.getMessage() + ")");
        }
        return zone;
    }
}
