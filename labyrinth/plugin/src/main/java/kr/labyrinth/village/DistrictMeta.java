package kr.labyrinth.village;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Base64;
import java.util.BitSet;
import java.util.List;
import java.util.Locale;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * {@code <주 월드>/labyrinth-district-<id>.yml} (0.3.6 광산 마을, CONTRACT §2.13 · district.json meta) — 지은 구역 기록.
 * VillageMeta 와 같은 필드(pieces·paths·protect·npcs·interact·ambient·points·terrain·build_id)에 state·site·village_build_id·
 * backup·region 을 더한다. 월드 폴더에 있어 월드와 함께 다닌다 (world.zip·백업·월드 갈아 끼우기).
 * <ul>
 *   <li>state building = 짓는 중 (꺼지면 다음 시작 때 백업으로 되돌린 뒤 처음부터), built = 다 지음, removed = 관리자가 지움
 *       (자동으로 다시 짓지 않음 — 파일이 없을 때만 자동으로 짓는다).</li>
 *   <li>region = terrain 격자에서 구역이 손댈 수 있는 칸 (자가 진단의 나무·뜬 지형 범위).</li>
 * </ul>
 * pvp/VillageZone 은 이 파일의 state·protect·safe_margin 만 따로 읽는다 (느슨한 연결).
 */
public final class DistrictMeta {

    public enum State {
        BUILDING, BUILT, REMOVED;

        public String key() { return name().toLowerCase(Locale.ROOT); }

        static State parse(String s) {
            try {
                return State.valueOf(String.valueOf(s).trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                return BUILT;
            }
        }
    }

    public static String fileName(String id) { return "labyrinth-district-" + id + ".yml"; }

    public static String backupName(String id) { return "labyrinth-district-" + id + ".backup.gz"; }

    /**
     * 집터 하나 (0.3.7 집 구역 — {@code plots:}). 상자 x0..x1 · z0..z1 (블록, 양 끝 포함) · 바닥 floor · 짓기 높이 창 y0..y1 ·
     * 앞 N/E/S/W · 대문 칸 (gate) · 표지판 칸 (sign) · 집 가기 자리 (home, 칸 가운데 + yaw).
     */
    public record PlotRec(String id, int x0, int z0, int x1, int z1, int floor, int y0, int y1, String front, int gateX, int gateY, int gateZ,
                          int signX, int signY, int signZ, double homeX, double homeY, double homeZ, float homeYaw) {}

    public String id;
    public String name = "";
    public State state = State.BUILDING;
    public String site = "";
    public String villageBuildId = "";
    public String backup = "";
    public int safeMargin = 8;
    /** terrain 격자 칸 비트 (구역 영역, 얼린 칸 제외). */
    public BitSet region = new BitSet();
    public VillageMeta meta = new VillageMeta();
    /** 집터들 (집 구역만, 나머지 구역은 빈 목록). */
    public List<PlotRec> plots = new java.util.ArrayList<>();

    public boolean built() { return state == State.BUILT; }

    /** 보호 상자·우클릭·NPC 가 살아 있는 상태 (짓는 중 = 보호만). */
    public boolean active() { return state == State.BUILT || state == State.BUILDING; }

    public boolean inRegion(int x, int z) {
        VillageMeta.TerrainRec t = meta.terrain;
        return t != null && t.in(x, z) && region.get((z - t.z0()) * t.n() + (x - t.x0()));
    }

    public String toYaml() throws InvalidConfigurationException {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(meta.toYaml());
        y.options().setHeader(List.of("미궁 라비린스 — 구역 기록 (" + (name == null || name.isBlank() ? id : name) + " — 플러그인이 씀, 직접 고치지 마세요)",
                "state: building(짓는 중) | built(다 지음) | removed(지움 — 자동으로 다시 짓지 않음)",
                "되돌리기 백업: " + (backup.isBlank() ? backupName(id) : backup) + " (같은 폴더)"));
        y.set("district", id);
        y.set("district_name", name);
        y.set("state", state.key());
        y.set("site", site);
        y.set("village_build_id", villageBuildId);
        y.set("backup", backup);
        y.set("safe_margin", safeMargin);
        y.set("region", Base64.getEncoder().encodeToString(region.toByteArray()));
        if (!plots.isEmpty()) {
            List<java.util.Map<String, Object>> ps = new java.util.ArrayList<>();
            for (PlotRec p : plots) {
                java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
                m.put("id", p.id());
                m.put("box", List.of(p.x0(), p.z0(), p.x1(), p.z1()));
                m.put("floor", p.floor());
                m.put("window", List.of(p.y0(), p.y1()));
                m.put("front", p.front());
                m.put("gate", List.of(p.gateX(), p.gateY(), p.gateZ()));
                m.put("sign", List.of(p.signX(), p.signY(), p.signZ()));
                m.put("home", List.of(p.homeX(), p.homeY(), p.homeZ(), (double) p.homeYaw()));
                ps.add(m);
            }
            y.set("plots", ps);
        }
        return y.saveToString();
    }

    public void save(File file) throws IOException {
        File parent = file.getParentFile();
        if (parent != null) parent.mkdirs();
        File tmp = new File(file.getPath() + ".tmp");
        try {
            Files.writeString(tmp.toPath(), toYaml(), StandardCharsets.UTF_8);
        } catch (InvalidConfigurationException e) {
            throw new IOException(e);
        }
        Files.move(tmp.toPath(), file.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
    }

    public static DistrictMeta load(File file) throws IOException, InvalidConfigurationException {
        return fromYaml(Files.readString(file.toPath(), StandardCharsets.UTF_8));
    }

    public static DistrictMeta fromYaml(String text) throws InvalidConfigurationException {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        DistrictMeta d = new DistrictMeta();
        d.meta = VillageMeta.fromYaml(text);
        d.id = y.getString("district", "");
        d.name = y.getString("district_name", d.meta.name);
        d.state = State.parse(y.getString("state", "built"));
        d.site = y.getString("site", "");
        d.villageBuildId = y.getString("village_build_id", "");
        d.backup = y.getString("backup", "");
        d.safeMargin = y.getInt("safe_margin", 8);
        String rg = y.getString("region", "");
        d.region = rg.isBlank() ? new BitSet() : BitSet.valueOf(Base64.getDecoder().decode(rg));
        for (java.util.Map<?, ?> m : y.getMapList("plots")) {
            try {
                List<?> box = (List<?>) m.get("box"), win = (List<?>) m.get("window"), gate = (List<?>) m.get("gate"), sign = (List<?>) m.get("sign"),
                        home = (List<?>) m.get("home");
                d.plots.add(new PlotRec(String.valueOf(m.get("id")), num(box.get(0)), num(box.get(1)), num(box.get(2)), num(box.get(3)),
                        num(m.get("floor")), num(win.get(0)), num(win.get(1)), String.valueOf(m.get("front")), num(gate.get(0)), num(gate.get(1)),
                        num(gate.get(2)), num(sign.get(0)), num(sign.get(1)), num(sign.get(2)), dbl(home.get(0)), dbl(home.get(1)), dbl(home.get(2)),
                        (float) dbl(home.get(3))));
            } catch (RuntimeException e) {
                // 형식이 다른 집터 줄은 건너뜀 (자가 진단 plots=n/10 이 잡음)
            }
        }
        return d;
    }

    private static int num(Object o) {
        if (o instanceof Number n) return n.intValue();
        return Integer.parseInt(String.valueOf(o).trim());
    }

    private static double dbl(Object o) {
        if (o instanceof Number n) return n.doubleValue();
        return Double.parseDouble(String.valueOf(o).trim());
    }
}
