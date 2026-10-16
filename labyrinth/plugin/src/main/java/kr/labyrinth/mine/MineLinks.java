package kr.labyrinth.mine;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;
import kr.labyrinth.core.Log;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 광산 ↔ 오버월드 광산 마을(구역, Q2) 잇기. 광산에서 "마을로" 가면 구역 승강장 {@code mine_exit} 에, 구역이 없으면 마을 광장에 내린다.
 * {@code /미궁 광산} 은 구역이 있으면 승강장 앞으로, 없으면 얕은 갱도로 바로 간다.
 * <p>
 * 구역 정보 얻는 길 (먼저 것이 이김):
 * <ol>
 *   <li>Q2 가 부르는 {@link #setDistrict} (나가는 자리 + 승강기 칸들)</li>
 *   <li>{@code <주 월드>/labyrinth-district-mine.yml} (VillageMeta 모양): {@code state: built} 일 때
 *       {@code points.mine_exit} (0.3.6.1 구역 기록) / {@code mine_exit} / {@code exit} / {@code markers.mine_exit} ([x, y, z, yaw] 또는 {x, y, z, yaw}) 와
 *       {@code interact} 의 "x,y,z" → mine_lift 칸들</li>
 * </ol>
 * 둘 다 없으면 구역 없음으로 본다 (광산은 관리소로 그대로 된다).
 */
public final class MineLinks {

    private MineLinks() {}

    public static final String DISTRICT_FILE = "labyrinth-district-mine.yml";

    /** 구역 정보. exit = 내리는 자리 (null 가능), lifts = 승강기 우클릭 칸들. */
    public record District(Location exit, List<Location> lifts) {}

    private static volatile Supplier<District> registered;
    private static volatile District cached;
    private static volatile long cachedAt;
    private static volatile long cachedModified = -1;

    /** Q2 광산 마을이 지어졌을 때 부른다 (null = 지움). */
    public static void setDistrict(Supplier<District> supplier) {
        registered = supplier;
        cached = null;
    }

    /** 지금 구역 (없으면 null). 파일은 5초마다 바뀐 때만 다시 읽는다. */
    public static District district() {
        Supplier<District> s = registered;
        if (s != null) {
            try {
                District d = s.get();
                if (d != null) return d;
            } catch (Throwable t) {
                Log.warnOnce("mine-district-supplier", "[광산] 광산 마을 정보 오류: " + t.getMessage());
            }
        }
        long now = System.currentTimeMillis();
        if (now - cachedAt < 5000) return cached;
        cachedAt = now;
        try {
            if (Bukkit.getWorlds().isEmpty()) return cached = null;
            World main = Bukkit.getWorlds().get(0);
            File f = new File(main.getWorldFolder(), DISTRICT_FILE);
            if (!f.isFile()) {
                cachedModified = -1;
                return cached = null;
            }
            if (f.lastModified() == cachedModified && cached != null) return cached;
            cachedModified = f.lastModified();
            return cached = read(main, YamlConfiguration.loadConfiguration(f));
        } catch (Throwable t) {
            Log.warnOnce("mine-district-file", "[광산] " + DISTRICT_FILE + " 를 읽지 못했습니다: " + t.getMessage());
            return cached = null;
        }
    }

    static District read(World w, ConfigurationSection y) {
        String state = y.getString("state", "built");
        if (state != null && !state.equalsIgnoreCase("built")) return null;
        Location exit = null;
        for (String k : new String[] {"points.mine_exit", "mine_exit", "exit", "markers.mine_exit", "spawn"}) {
            exit = pos(w, y.get(k));
            if (exit != null) break;
        }
        List<Location> lifts = new ArrayList<>();
        ConfigurationSection inter = y.getConfigurationSection("interact");
        if (inter != null) {
            for (String key : inter.getKeys(false)) {
                if (!MineNames.INTERACT_LIFT.equals(inter.getString(key))) continue;
                String[] p = key.split(",");
                if (p.length != 3) continue;
                try {
                    lifts.add(new Location(w, Integer.parseInt(p[0].trim()) + 0.5, Integer.parseInt(p[1].trim()), Integer.parseInt(p[2].trim()) + 0.5));
                } catch (NumberFormatException ignored) {
                    // 형식이 다른 칸은 건너뜀
                }
            }
        }
        if (exit == null && lifts.isEmpty()) return null;
        if (exit == null) exit = lifts.get(0).clone().add(0, 0, 0);
        return new District(exit, List.copyOf(lifts));
    }

    static Location pos(World w, Object v) {
        try {
            if (v instanceof List<?> l && l.size() >= 3) {
                double x = num(l.get(0)), yy = num(l.get(1)), z = num(l.get(2));
                float yaw = l.size() > 3 ? (float) num(l.get(3)) : 0f;
                return new Location(w, x, yy, z, yaw, 0f);
            }
            if (v instanceof ConfigurationSection s) v = s.getValues(false);
            if (v instanceof Map<?, ?> m) {
                if (m.get("pos") != null) return pos(w, m.get("pos"));
                if (m.get("x") == null) return null;
                Location l = new Location(w, num(m.get("x")), num(m.get("y")), num(m.get("z")));
                if (m.get("yaw") != null) l.setYaw((float) num(m.get("yaw")));
                return l;
            }
        } catch (RuntimeException ignored) {
            // 아래 null
        }
        return null;
    }

    private static double num(Object o) { return Double.parseDouble(String.valueOf(o)); }

    /**
     * 구역 승강장 앞(exit)으로 보내도 되는가 — 월드 경계 안 (관리자가 /worldborder 로 좁힌 서버에서 경계 밖이면 야생 막기가 곧바로
     * 광장으로 되돌리니, 광산 가기·마을로 나가기는 예전처럼 광산 1층·마을 광장으로, 0.3.6.1 리뷰).
     */
    public static boolean usable(District d) {
        if (d == null || d.exit() == null || d.exit().getWorld() == null) return false;
        try {
            return d.exit().getWorld().getWorldBorder().isInside(d.exit());
        } catch (Throwable t) {
            return true;
        }
    }

    /** 그 자리가 구역 승강기 가까이(radius 칸)인가. 구역 정보가 없으면 false. */
    public static boolean nearLift(Location at, double radius) {
        District d = district();
        if (d == null || at == null || at.getWorld() == null) return false;
        double r2 = radius * radius;
        for (Location l : d.lifts()) if (at.getWorld().equals(l.getWorld()) && at.distanceSquared(l) <= r2) return true;
        Location e = d.exit();
        return e != null && at.getWorld().equals(e.getWorld()) && at.distanceSquared(e) <= r2;
    }
}
