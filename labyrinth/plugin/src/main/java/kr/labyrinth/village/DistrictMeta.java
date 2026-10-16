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
        y.options().setHeader(List.of("미궁 라비린스 — 광산 마을 기록 (0.3.6.1, 플러그인이 씀 — 직접 고치지 마세요)",
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
        return d;
    }
}
