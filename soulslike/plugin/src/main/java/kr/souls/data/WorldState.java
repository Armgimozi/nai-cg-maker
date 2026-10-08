package kr.souls.data;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import kr.souls.Keys;
import kr.souls.Souls;
import org.bukkit.World;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.persistence.PersistentDataType;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.Locale;
import java.util.UUID;

/**
 * 세계 설정 (5.7, 12.6): 난이도와 PvP. souls_world 의 PDC souls:settings (JSON) 가 정본이고, 사본은 plugins/Soulslike/souls-state.yml 의
 * settings: (그 세계의 UID 와 함께). 바꾼 기록은 plugins/Soulslike/settings.log (덧붙이기만).
 * 세계 PDC 는 세계를 저장할 때 디스크에 가므로 바꾼 직후 world.save() 를 한 번 부른다 (드문 일이다). 켤 때 PDC 가 없고 YAML 의 UID 가
 * 그 세계와 같으면 YAML 에서 되살리고 (저장 전에 서버가 죽었을 때), UID 가 다르면 (세계 폴더를 지웠다) 무시하고 다시 묻는다.
 */
public final class WorldState {
    /**
     * 세계 설정 한 판. confirmed 가 거짓이면 잠정 (창을 닫았거나 아직 정하지 않았다: 기본값으로 돌고 정할 사람에게 다시 묻는다).
     * rev 는 바뀔 때마다 오른다 (나중에 들어온 사람이 지난번에 본 판과 견준다). by/name 은 정한 사람 (잠정이면 처음 연 사람).
     * via: dialog | esc | command | default | auto | yaml.
     */
    public record Settings(String difficulty, boolean pvp, boolean confirmed, int rev, String by, String name, long at, String via) {
        public String json() {
            JsonObject o = new JsonObject();
            o.addProperty("v", 1);
            o.addProperty("difficulty", difficulty);
            o.addProperty("pvp", pvp);
            o.addProperty("confirmed", confirmed);
            o.addProperty("rev", rev);
            if (by != null) o.addProperty("by", by);
            if (name != null) o.addProperty("name", name);
            o.addProperty("at", at);
            o.addProperty("via", via);
            return GSON.toJson(o);
        }

        public static Settings parse(String json) {
            try {
                JsonObject o = JsonParser.parseString(json).getAsJsonObject();
                return new Settings(o.has("difficulty") ? o.get("difficulty").getAsString() : "normal",
                        o.has("pvp") && o.get("pvp").getAsBoolean(), o.has("confirmed") && o.get("confirmed").getAsBoolean(),
                        o.has("rev") ? o.get("rev").getAsInt() : 0, o.has("by") ? o.get("by").getAsString() : null,
                        o.has("name") ? o.get("name").getAsString() : null, o.has("at") ? o.get("at").getAsLong() : 0,
                        o.has("via") ? o.get("via").getAsString() : "default");
            } catch (RuntimeException ex) {
                return null;
            }
        }

        public UUID byId() {
            try {
                return by == null ? null : UUID.fromString(by);
            } catch (IllegalArgumentException ex) {
                return null;
            }
        }

        /** 시험 줄 꼬리 */
        public String line() {
            return "difficulty=" + difficulty + " pvp=" + pvp + " confirmed=" + confirmed + " rev=" + rev + " by=" + (name == null ? "-" : name)
                    + " via=" + via;
        }
    }

    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();
    private final Souls plugin;
    private Settings current;

    public WorldState(Souls plugin) {
        this.plugin = plugin;
    }

    /** 켤 때 (세계를 연 뒤): PDC 에서, 없으면 같은 세계의 YAML 사본에서 읽는다. */
    public void load(World w) {
        current = null;
        if (w == null) return;
        String json = w.getPersistentDataContainer().get(Keys.SETTINGS, PersistentDataType.STRING);
        if (json != null) current = Settings.parse(json);
        if (current == null) {
            YamlConfiguration y = YamlConfiguration.loadConfiguration(stateFile());
            String uid = y.getString("settings.world-uid");
            String yj = y.getString("settings.json");
            if (uid != null && yj != null) {
                if (uid.equals(w.getUID().toString())) {
                    Settings s = Settings.parse(yj);
                    if (s != null) {
                        current = s;
                        w.getPersistentDataContainer().set(Keys.SETTINGS, PersistentDataType.STRING, s.json());
                        plugin.getLogger().warning("세계 설정이 세계에 없어 souls-state.yml 의 사본에서 되살렸습니다: " + s.line());
                    }
                } else {
                    plugin.getLogger().info("souls-state.yml 의 세계 설정은 다른 세계의 것이라 쓰지 않습니다 (세계를 새로 만들었다). 처음 들어온 사람에게 다시 묻습니다.");
                }
            }
        }
        if (current != null) plugin.getLogger().info("세계 설정: " + current.line());
    }

    /** 지금 세계 설정 (아직 아무도 정하지 않았으면 null). */
    public Settings get() {
        return current;
    }

    /**
     * 세계 설정을 바꾸고 저장한다 (PDC + world.save() + YAML 사본 + 기록). 기록 줄은 서버 기록 (INFO) 과 settings.log 에 남긴다.
     */
    public void set(World w, Settings s) {
        Settings old = current;
        current = s;
        if (w != null) {
            w.getPersistentDataContainer().set(Keys.SETTINGS, PersistentDataType.STRING, s.json());
            w.save();
            YamlConfiguration y = YamlConfiguration.loadConfiguration(stateFile());
            y.set("settings.world-uid", w.getUID().toString());
            y.set("settings.json", s.json());
            try {
                y.save(stateFile());
            } catch (IOException ex) {
                plugin.getLogger().warning("souls-state.yml 에 세계 설정을 쓰지 못했습니다: " + ex.getMessage());
            }
        }
        String line = OffsetDateTime.now().truncatedTo(ChronoUnit.SECONDS).format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)
                + " difficulty " + (old == null ? "-" : old.difficulty()) + " -> " + s.difficulty()
                + ", pvp " + (old == null ? "-" : onOff(old.pvp())) + " -> " + onOff(s.pvp())
                + ", confirmed " + s.confirmed() + ", rev " + s.rev()
                + ", by " + (s.name() == null ? "-" : s.name()) + " (" + (s.by() == null ? "-" : s.by()) + "), via " + s.via();
        plugin.getLogger().info("세계 설정: " + line);
        try {
            Files.createDirectories(plugin.getDataFolder().toPath());
            Files.writeString(new File(plugin.getDataFolder(), "settings.log").toPath(), line + "\n", StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException ex) {
            plugin.getLogger().warning("settings.log 에 쓰지 못했습니다: " + ex.getMessage());
        }
    }

    private static String onOff(boolean b) {
        return b ? "on" : "off";
    }

    private File stateFile() {
        return new File(plugin.getDataFolder(), "souls-state.yml");
    }

    public static String normalize(String id) {
        return id == null ? null : id.trim().toLowerCase(Locale.ROOT).replace('-', '_');
    }
}
