package kr.labyrinth.homes.rules;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import kr.labyrinth.homes.PlotGeom;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 집 주인 기록 {@code <월드>/labyrinth-plots.yml} (0.3.7, plan §4) — 월드 폴더에 두어 월드를 되돌리면 같이 맞는다. 소유: 묶음 B.
 * <pre>
 * format: 1
 * district_build: "…"          # 집 구역 build_id (다르면 주인 기록을 옛 구역 것으로 보고 관리자에게 알림)
 * lock: {state: auto, started_at: 0}       # 잠금 덮어쓰기 · 처음 켜진 때
 * grace: {days: -1, started_at: 0}         # days −1 = config legacy_grace_days
 * legacy_scanned_at: 0
 * plots: {"3": {owner, owner_name, name, trusted: {uuid: 이름}, guests, claimed_at, renamed_at}}
 * custom: {c1: {n, box: [x0, z0, x1, z1], window: [y0, y1], floor, home: [x, y, z, yaw]}}
 * vacated: {uuid: 시각}                    # 스스로 비운 때 (R13)
 * known: [uuid …]                          # 집을 받은 적 있는 사람 (처음 받기 판단)
 * </pre>
 * 저장은 원자적 (같은 폴더 tmp 에 쓰고 move). 읽기 실패한 파일은 {@code .broken-<시각>} 으로 옮기고 빈 기록으로 시작한다.
 * 이 클래스는 순수 자료 + 파일 입출력 (Bukkit 서버 불필요) — 메인 스레드에서만 쓴다.
 */
public final class PlotStore {

    public static final String FILE = "labyrinth-plots.yml";

    /** 집 하나의 소유. */
    public static final class Owner {
        public UUID owner;
        public String ownerName = "";
        public String name = "";
        /** 초대한 사람 → 이름 (차례 유지). */
        public final LinkedHashMap<UUID, String> trusted = new LinkedHashMap<>();
        public boolean guests = true;
        public long claimedAt;
        public long renamedAt;

        public Owner() {}

        public Owner(UUID owner, String ownerName, boolean guests, long claimedAt) {
            this.owner = owner;
            this.ownerName = ownerName == null ? "" : ownerName;
            this.guests = guests;
            this.claimedAt = claimedAt;
        }
    }

    /** 관리자가 옛 건물을 바꾼 집터 (convert). */
    public record Custom(String id, int n, int x0, int z0, int x1, int z1, int yMin, int yMax, int floorY, double homeX, double homeY,
                         double homeZ, float homeYaw) {

        public static final int KEY_BASE = 100;

        public PlotGeom geom() {
            int gx = (x0 + x1) / 2;
            return new PlotGeom(id, KEY_BASE + n, x0, z0, x1, z1, floorY, yMin, yMax, "S", gx, z1 + 1, gx, Integer.MIN_VALUE, z1 + 1,
                    homeX, homeY, homeZ, homeYaw, true);
        }
    }

    private final File file;
    public String districtBuild = "";
    public TerrainLock.State lockState = TerrainLock.State.AUTO;
    public long lockStartedAt;
    /** 관리자가 정한 이사 기간 (null = config). */
    public Integer graceDays;
    public long graceStartedAt;
    public long legacyScannedAt;
    public final Map<String, Owner> owners = new LinkedHashMap<>();
    public final Map<String, Custom> customs = new LinkedHashMap<>();
    public final Map<UUID, Long> vacated = new LinkedHashMap<>();
    public final Set<UUID> known = new LinkedHashSet<>();
    /** 읽을 때 생긴 일 (자가 진단·로그). */
    public String loadNote = "";

    public PlotStore(File file) { this.file = file; }

    public File file() { return file; }

    public static PlotStore load(File file) {
        PlotStore s = new PlotStore(file);
        if (file == null || !file.isFile()) return s;
        YamlConfiguration y = new YamlConfiguration();
        try {
            y.loadFromString(Files.readString(file.toPath(), StandardCharsets.UTF_8));
        } catch (IOException | InvalidConfigurationException e) {
            File broken = new File(file.getParentFile(), file.getName() + ".broken-" + System.currentTimeMillis());
            boolean moved = file.renameTo(broken);
            s.loadNote = "읽기 실패 (" + e.getClass().getSimpleName() + ") — " + (moved ? broken.getName() + " 로 옮기고 " : "") + "빈 기록으로 시작";
            return s;
        }
        s.districtBuild = y.getString("district_build", "");
        s.lockState = TerrainLock.State.of(y.getString("lock.state", "auto"));
        s.lockStartedAt = y.getLong("lock.started_at", 0);
        int gd = y.getInt("grace.days", -1);
        s.graceDays = gd >= 0 ? gd : null;
        s.graceStartedAt = y.getLong("grace.started_at", 0);
        s.legacyScannedAt = y.getLong("legacy_scanned_at", 0);
        ConfigurationSection ps = y.getConfigurationSection("plots");
        if (ps != null) for (String id : ps.getKeys(false)) {
            ConfigurationSection o = ps.getConfigurationSection(id);
            UUID u = o == null ? null : uuid(o.getString("owner"));
            if (u == null) continue;
            Owner ow = new Owner(u, o.getString("owner_name", ""), o.getBoolean("guests", true), o.getLong("claimed_at", 0));
            ow.name = o.getString("name", "");
            ow.renamedAt = o.getLong("renamed_at", 0);
            ConfigurationSection tr = o.getConfigurationSection("trusted");
            if (tr != null) for (String k : tr.getKeys(false)) {
                UUID t = uuid(k);
                if (t != null && !t.equals(u)) ow.trusted.put(t, tr.getString(k, ""));
            }
            s.owners.put(norm(id), ow);
        }
        ConfigurationSection cs = y.getConfigurationSection("custom");
        if (cs != null) for (String id : cs.getKeys(false)) {
            ConfigurationSection c = cs.getConfigurationSection(id);
            if (c == null) continue;
            List<Integer> box = c.getIntegerList("box"), win = c.getIntegerList("window");
            List<Double> home = c.getDoubleList("home");
            if (box.size() != 4 || win.size() != 2) continue;
            int n = c.getInt("n", parseN(id));
            if (n <= 0) continue;
            s.customs.put(norm(id), new Custom(norm(id), n, box.get(0), box.get(1), box.get(2), box.get(3), win.get(0), win.get(1),
                    c.getInt("floor", win.get(0)), home.size() >= 3 ? home.get(0) : Double.NaN, home.size() >= 3 ? home.get(1) : Double.NaN,
                    home.size() >= 3 ? home.get(2) : Double.NaN, home.size() >= 4 ? home.get(3).floatValue() : 0f));
        }
        ConfigurationSection vs = y.getConfigurationSection("vacated");
        if (vs != null) for (String k : vs.getKeys(false)) {
            UUID u = uuid(k);
            if (u != null) s.vacated.put(u, vs.getLong(k));
        }
        for (String k : y.getStringList("known")) {
            UUID u = uuid(k);
            if (u != null) s.known.add(u);
        }
        return s;
    }

    public String toYaml() {
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(List.of("미궁 라비린스 — 집 주인 기록 (0.3.7). 서버가 꺼진 동안에만 고치세요. 이 파일은 월드와 같이 다닙니다."));
        y.set("format", 1);
        y.set("district_build", districtBuild);
        y.set("lock.state", lockState.id());
        y.set("lock.started_at", lockStartedAt);
        y.set("grace.days", graceDays == null ? -1 : graceDays);
        y.set("grace.started_at", graceStartedAt);
        y.set("legacy_scanned_at", legacyScannedAt);
        y.createSection("plots");
        for (Map.Entry<String, Owner> e : owners.entrySet()) {
            Owner o = e.getValue();
            String p = "plots." + e.getKey() + ".";
            y.set(p + "owner", o.owner.toString());
            y.set(p + "owner_name", o.ownerName);
            y.set(p + "name", o.name);
            y.createSection(p + "trusted");
            for (Map.Entry<UUID, String> t : o.trusted.entrySet()) y.set(p + "trusted." + t.getKey(), t.getValue() == null ? "" : t.getValue());
            y.set(p + "guests", o.guests);
            y.set(p + "claimed_at", o.claimedAt);
            y.set(p + "renamed_at", o.renamedAt);
        }
        y.createSection("custom");
        for (Custom c : customs.values()) {
            String p = "custom." + c.id() + ".";
            y.set(p + "n", c.n());
            y.set(p + "box", List.of(c.x0(), c.z0(), c.x1(), c.z1()));
            y.set(p + "window", List.of(c.yMin(), c.yMax()));
            y.set(p + "floor", c.floorY());
            if (!Double.isNaN(c.homeY())) y.set(p + "home", List.of(c.homeX(), c.homeY(), c.homeZ(), (double) c.homeYaw()));
        }
        y.createSection("vacated");
        for (Map.Entry<UUID, Long> e : vacated.entrySet()) y.set("vacated." + e.getKey(), e.getValue());
        List<String> k = new ArrayList<>();
        for (UUID u : known) k.add(u.toString());
        y.set("known", k);
        return y.saveToString();
    }

    /** 원자적 저장 (tmp → move). */
    public void save() throws IOException {
        if (file == null) return;
        writeAtomic(file.toPath(), toYaml());
    }

    /** 같은 폴더의 tmp 에 다 쓴 뒤 바꿔 끼움 (중간에 꺼져도 예전 파일이나 새 파일 둘 중 하나). */
    public static void writeAtomic(Path target, String text) throws IOException {
        Path dir = target.toAbsolutePath().getParent();
        if (dir != null) Files.createDirectories(dir);
        Path tmp = target.resolveSibling(target.getFileName() + ".tmp");
        Files.writeString(tmp, text, StandardCharsets.UTF_8);
        try {
            Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException e) {
            Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    // ── 조회 ─────────────────────────────────────────────────────────────

    public Owner owner(String plotId) { return owners.get(norm(plotId)); }

    /** 그 사람이 주인인 집 id (없으면 null). */
    public String homeOf(UUID player) {
        if (player == null) return null;
        for (Map.Entry<String, Owner> e : owners.entrySet()) if (player.equals(e.getValue().owner)) return e.getKey();
        return null;
    }

    /** 다음 convert 번호 (c1, c2 …, 지운 번호는 다시 안 씀이 아니라 가장 작은 빈 번호). */
    public int nextCustomN() {
        int n = 1;
        Set<Integer> used = new java.util.HashSet<>();
        for (Custom c : customs.values()) used.add(c.n());
        while (used.contains(n)) n++;
        return n;
    }

    /** 주인 기록이 다른 집 구역 것인가 (district_build 가 있고 지금과 다르고 주인이 있음). */
    public boolean stale(String currentBuildId) {
        if (districtBuild == null || districtBuild.isEmpty() || currentBuildId == null || currentBuildId.isEmpty()) return false;
        if (districtBuild.equals(currentBuildId)) return false;
        for (String id : owners.keySet()) if (!customs.containsKey(id)) return true;
        return false;
    }

    /** 구역 집터 주인 수 (convert 집 제외). */
    public int districtOwned() {
        int n = 0;
        for (String id : owners.keySet()) if (!customs.containsKey(id)) n++;
        return n;
    }

    public static String norm(String id) { return id == null ? "" : id.trim().toLowerCase(Locale.ROOT); }

    private static int parseN(String id) {
        String s = norm(id);
        if (!s.startsWith("c")) return -1;
        try {
            return Integer.parseInt(s.substring(1));
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    private static UUID uuid(String s) {
        if (s == null || s.isBlank()) return null;
        try {
            return UUID.fromString(s.trim());
        } catch (IllegalArgumentException e) {
            return null;
        }
    }
}
