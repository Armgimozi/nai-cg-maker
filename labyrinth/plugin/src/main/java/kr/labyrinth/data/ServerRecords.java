package kr.labyrinth.data;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import kr.labyrinth.Services;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import org.bukkit.Bukkit;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 서버 최초 달성 기록 (plugins/Labyrinth/records.yml). 키 예: "first_clear.floor_3", "pvp.first_win",
 * "speed.floor_5" (스피드 기록은 {@link #bestTime}). 칭호 모듈의 FIRST_CLEAR 판정이 여기를 쓴다.
 */
public final class ServerRecords implements Module {

    /** 기록 한 건. extra 는 난이도·시간 등 자유 값. */
    public record Record(String key, long time, List<UUID> players, List<String> names, Map<String, Object> extra) {}

    private final Services services;
    private final Path file;
    private final Map<String, Record> records = new LinkedHashMap<>();

    public ServerRecords(Services services) {
        this.services = services;
        this.file = services.plugin().getDataFolder().toPath().resolve("records.yml");
    }

    @Override
    public String name() { return "records"; }

    @Override
    public void enable() {
        records.clear();
        if (!Files.exists(file)) return;
        try {
            YamlConfiguration y = new YamlConfiguration();
            y.loadFromString(Files.readString(file, StandardCharsets.UTF_8));
            ConfigurationSection rs = y.getConfigurationSection("records");
            if (rs == null) return;
            for (String k : rs.getKeys(false)) {
                ConfigurationSection r = rs.getConfigurationSection(k);
                if (r == null) continue;
                List<UUID> ids = new ArrayList<>();
                for (String s : r.getStringList("players")) {
                    try { ids.add(UUID.fromString(s)); } catch (IllegalArgumentException ignored) { /* skip */ }
                }
                ConfigurationSection ex = r.getConfigurationSection("extra");
                String key = k.replace('/', '.');
                records.put(key, new Record(key, r.getLong("time"), List.copyOf(ids), List.copyOf(r.getStringList("names")),
                        ex == null ? Map.of() : Collections.unmodifiableMap(ContentLoader.toPlain(ex))));
            }
        } catch (Exception e) {
            Log.error("records.yml 읽기 실패", e);
        }
    }

    @Override
    public void disable() { saveSync(); }

    public boolean isClaimed(String key) { return records.containsKey(key); }

    public Optional<Record> get(String key) { return Optional.ofNullable(records.get(key)); }

    public Map<String, Record> all() { return Collections.unmodifiableMap(records); }

    /**
     * 최초 달성 시도. 아직 기록이 없으면 저장하고 true (= 서버 최초), 이미 있으면 false.
     */
    public boolean claim(String key, List<UUID> players, List<String> names, Map<String, Object> extra) {
        if (records.containsKey(key)) return false;
        records.put(key, new Record(key, System.currentTimeMillis(), List.copyOf(players), List.copyOf(names),
                extra == null ? Map.of() : Map.copyOf(extra)));
        saveAsync();
        return true;
    }

    /** 최단 시간 기록 갱신 (초). 갱신했으면 true. */
    public boolean bestTime(String key, double seconds, List<UUID> players, List<String> names) {
        Record old = records.get(key);
        if (old != null && old.extra().get("seconds") instanceof Number n && n.doubleValue() <= seconds) return false;
        records.put(key, new Record(key, System.currentTimeMillis(), List.copyOf(players), List.copyOf(names),
                Map.of("seconds", seconds)));
        saveAsync();
        return true;
    }

    /** 관리자 초기화용. */
    public void remove(String key) {
        if (records.remove(key) != null) saveAsync();
    }

    private String serialize() {
        YamlConfiguration y = new YamlConfiguration();
        y.set("version", 1);
        for (Record r : records.values()) {
            String base = "records." + r.key().replace('.', '/');
            y.set(base + ".time", r.time());
            List<String> ids = new ArrayList<>();
            for (UUID u : r.players()) ids.add(u.toString());
            y.set(base + ".players", ids);
            y.set(base + ".names", r.names());
            if (!r.extra().isEmpty()) y.createSection(base + ".extra", r.extra());
        }
        return y.saveToString();
    }

    private void saveAsync() {
        String text = serialize();
        if (!services.plugin().isEnabled()) {
            writeFile(text);
            return;
        }
        Bukkit.getScheduler().runTaskAsynchronously(services.plugin(), () -> writeFile(text));
    }

    private void saveSync() { writeFile(serialize()); }

    private synchronized void writeFile(String text) {
        try {
            Files.createDirectories(file.getParent());
            Files.writeString(file, text, StandardCharsets.UTF_8);
        } catch (IOException e) {
            Log.error("records.yml 저장 실패", e);
        }
    }
}
