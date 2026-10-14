package kr.labyrinth.core;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ContentParser;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * content/*.yml 를 데이터 폴더(plugins/Labyrinth/content/)로 복사하고 읽어 {@link Content} 로 만든다.
 * <p>
 * 업데이트 규칙: 복사할 때 원본 해시를 {@code content/.bundled} 에 적어 두고, 다음 시작 때
 * 데이터 폴더 파일이 그 해시와 같으면(= 구매자가 손대지 않았으면) jar 의 새 버전으로 교체한다.
 * 손댄 파일은 그대로 두고 경고만 한다.
 */
public final class ContentLoader {

    public record Result(Content content, List<String> problems) {}

    private static final String MANIFEST = ".bundled";

    private ContentLoader() {}

    /** jar 의 기본 콘텐츠를 데이터 폴더로 복사/갱신. */
    public static void copyDefaults(JavaPlugin plugin) throws IOException {
        Path dir = plugin.getDataFolder().toPath().resolve("content");
        Files.createDirectories(dir);
        Path manifestPath = dir.resolve(MANIFEST);
        Properties manifest = new Properties();
        if (Files.exists(manifestPath)) {
            try (var in = Files.newBufferedReader(manifestPath, StandardCharsets.UTF_8)) {
                manifest.load(in);
            }
        }
        boolean changed = false;
        for (String file : ContentParser.FILES) {
            byte[] bundled;
            try (InputStream in = plugin.getResource("content/" + file)) {
                if (in == null) continue;
                bundled = in.readAllBytes();
            }
            String bundledHash = sha1(bundled);
            Path target = dir.resolve(file);
            if (!Files.exists(target)) {
                Files.write(target, bundled);
                manifest.setProperty(file, bundledHash);
                changed = true;
                continue;
            }
            String recorded = manifest.getProperty(file);
            if (bundledHash.equals(recorded)) continue; // 최신
            String current = sha1(Files.readAllBytes(target));
            if (current.equals(bundledHash)) {
                manifest.setProperty(file, bundledHash);
                changed = true;
            } else if (recorded != null && current.equals(recorded)) {
                Files.write(target, bundled); // 손대지 않은 옛 기본값 → 새 기본값
                manifest.setProperty(file, bundledHash);
                changed = true;
                Log.info("콘텐츠 갱신: content/" + file);
            } else {
                Log.warn("content/" + file + " 은 직접 수정된 파일이라 새 기본값으로 덮어쓰지 않았습니다. "
                        + "새 콘텐츠를 쓰려면 파일을 지우고 /labadmin reload 하세요.");
                if (recorded == null) {
                    manifest.setProperty(file, "user-modified");
                    changed = true;
                }
            }
        }
        if (changed) {
            try (var out = Files.newBufferedWriter(manifestPath, StandardCharsets.UTF_8)) {
                manifest.store(out, "Labyrinth bundled content hashes - do not edit");
            }
        }
    }

    /** 디렉터리의 content/*.yml 을 모두 읽는다. 없는 파일은 problems 에 기록(선택 파일 제외). */
    public static Result load(Path dir) {
        Map<String, Map<String, Object>> raw = new LinkedHashMap<>();
        List<String> problems = new ArrayList<>();
        for (String file : ContentParser.FILES) {
            Path p = dir.resolve(file);
            if (!Files.exists(p)) continue;
            try {
                YamlConfiguration yc = new YamlConfiguration();
                yc.loadFromString(Files.readString(p, StandardCharsets.UTF_8));
                raw.put(file, toPlain(yc));
            } catch (IOException | InvalidConfigurationException e) {
                problems.add(file + " 읽기 실패: " + e.getMessage());
            }
        }
        ContentParser parser = new ContentParser();
        Content content = parser.parse(raw);
        problems.addAll(parser.problems());
        return new Result(content, problems);
    }

    /** ConfigurationSection → 순수 Map/List 트리. */
    public static Map<String, Object> toPlain(ConfigurationSection section) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (String key : section.getKeys(false)) {
            out.put(key, plainValue(section.get(key)));
        }
        return out;
    }

    private static Object plainValue(Object v) {
        if (v instanceof ConfigurationSection cs) return toPlain(cs);
        if (v instanceof Map<?, ?> m) {
            Map<String, Object> out = new LinkedHashMap<>();
            m.forEach((k, val) -> out.put(String.valueOf(k), plainValue(val)));
            return out;
        }
        if (v instanceof List<?> l) {
            List<Object> out = new ArrayList<>(l.size());
            for (Object o : l) out.add(plainValue(o));
            return out;
        }
        return v;
    }

    static String sha1(byte[] data) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-1").digest(data));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
