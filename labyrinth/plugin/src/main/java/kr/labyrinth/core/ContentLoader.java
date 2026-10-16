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

    /**
     * 서로 아이템 id 를 주고받는 콘텐츠 파일. 하나만 옛 판(직접 고쳐서 덮어쓰지 않음)으로 남고 나머지가 새 판이면 루팅·제작·강화·상점이
     * 없는 아이템을 가리켜 조용히 빠진다 — 켤 때 크게 알린다 ({@link #coupledWarnings}).
     */
    static final List<String> COUPLED = List.of("items.yml", "loot.yml", "recipes.yml", "enhance.yml", "npcs.yml", "mine.yml");

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
        List<String> kept = new ArrayList<>(), fresh = new ArrayList<>();
        int missingItems = -1;
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
                fresh.add(file);
                continue;
            }
            String recorded = manifest.getProperty(file);
            if (bundledHash.equals(recorded)) { // 최신 (이 판을 받은 뒤 고친 파일도 이 판 기준)
                fresh.add(file);
                continue;
            }
            byte[] currentBytes = Files.readAllBytes(target);
            String current = sha1(currentBytes);
            if (current.equals(bundledHash)) {
                manifest.setProperty(file, bundledHash);
                changed = true;
                fresh.add(file);
            } else if (recorded != null && current.equals(recorded)) {
                Files.write(target, bundled); // 손대지 않은 옛 기본값 → 새 기본값
                manifest.setProperty(file, bundledHash);
                changed = true;
                fresh.add(file);
                Log.info("콘텐츠 갱신: content/" + file);
            } else {
                Log.warn("content/" + file + " 은 직접 수정된 파일이라 새 기본값으로 덮어쓰지 않았습니다. "
                        + "새 콘텐츠를 쓰려면 파일을 지우고 /labadmin reload 하세요.");
                kept.add(file);
                if (file.equals("items.yml")) missingItems = missingItemIds(bundled, currentBytes);
                if (recorded == null) {
                    manifest.setProperty(file, "user-modified");
                    changed = true;
                }
            }
        }
        for (String line : coupledWarnings(kept, fresh, missingItems)) Log.warn(line);
        // 더는 쓰지 않는 예전 기본 파일: 손대지 않았으면(해시가 기록과 같으면) 지운다. 손댄 파일은 남겨 두고 무시.
        for (String file : ContentParser.RETIRED_FILES) {
            Path target = dir.resolve(file);
            String recorded = manifest.getProperty(file);
            if (recorded == null) continue;
            if (Files.exists(target) && sha1(Files.readAllBytes(target)).equals(recorded)) {
                Files.delete(target);
                Log.info("쓰지 않는 콘텐츠 파일 정리: content/" + file);
            }
            manifest.remove(file);
            changed = true;
        }
        if (changed) {
            try (var out = Files.newBufferedWriter(manifestPath, StandardCharsets.UTF_8)) {
                manifest.store(out, "Labyrinth bundled content hashes - do not edit");
            }
        }
    }

    /**
     * 순수: 서로 기대는 파일({@link #COUPLED}) 가운데 옛 판으로 남은 것(kept)과 새 판(fresh)이 섞였으면 크게 알리는 줄들. 안 섞였으면 빈 목록.
     * @param missingItems items.yml 이 옛 판일 때 새 items.yml 에만 있는 아이템 수 (-1 = 모름)
     */
    static List<String> coupledWarnings(List<String> kept, List<String> fresh, int missingItems) {
        List<String> old = kept.stream().filter(COUPLED::contains).toList();
        List<String> now = fresh.stream().filter(COUPLED::contains).toList();
        if (old.isEmpty() || now.isEmpty()) return List.of();
        List<String> out = new ArrayList<>();
        out.add("════════════════════════════════════════════════════════════");
        if (old.contains("items.yml")) {
            String what = missingItems > 0 ? "새 장비 " + missingItems + "개가 빠집니다"
                    : missingItems == 0 ? "새 판에서 바뀐 장비 값이 빠질 수 있습니다" : "새 장비가 빠질 수 있습니다";
            out.add("[중요] content/items.yml 이 옛 판이라 " + what + " — 새 " + String.join("·", now)
                    + " 이(가) 새 장비를 가리킵니다 (루팅·제작·강화·상점에서 빠짐).");
        } else {
            out.add("[중요] content/" + String.join("·", old) + " 이(가) 옛 판이고 " + String.join("·", now)
                    + " 은(는) 새 판입니다 — 서로 맞지 않아 루팅·제작·강화·상점이 빠질 수 있습니다.");
        }
        out.add("[중요] 고친 파일(" + String.join("·", old) + ")을 다른 곳에 백업한 뒤 지우고 /labadmin reload 하세요."
                + " 고쳤던 부분만 새 파일에 다시 적으면 됩니다.");
        out.add("════════════════════════════════════════════════════════════");
        return out;
    }

    /** 새 items.yml 에만 있는 아이템 수 (옛 판 items.yml 과 비교). 못 읽으면 -1. */
    static int missingItemIds(byte[] bundled, byte[] current) {
        try {
            YamlConfiguration b = new YamlConfiguration(), c = new YamlConfiguration();
            b.loadFromString(new String(bundled, StandardCharsets.UTF_8));
            c.loadFromString(new String(current, StandardCharsets.UTF_8));
            ConfigurationSection bi = b.getConfigurationSection("items"), ci = c.getConfigurationSection("items");
            if (bi == null) return -1;
            int n = 0;
            for (String id : bi.getKeys(false)) if (ci == null || !ci.contains(id)) n++;
            return n;
        } catch (InvalidConfigurationException | RuntimeException e) {
            return -1;
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
