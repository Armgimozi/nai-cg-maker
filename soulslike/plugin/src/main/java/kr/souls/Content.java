package kr.souls;

import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;

/**
 * 콘텐츠 YAML (plugins/Soulslike/content/) 꺼내기. skyblock AugSky 의 방식을 옮겼다:
 * 파일이 없을 때만 꺼내므로, 들어 있는 YAML 을 바꾸면 CONTENT_VERSION 을 올린다.
 * 판이 오르면 옛 파일을 old-content-v{옛 판}/ 으로 옮겨 두고(지우지 않는다) 새로 꺼낸다.
 */
public final class Content {
    /**
     * 콘텐츠 YAML 의 판 (1: M0, 시험용 스킬 둘. 2: 스킬 이름·설명을 lang 열쇠로 옮김. 3: weapons.yml, 맛보기판 무기·방패·촉매
     * 스물). 콘텐츠에는 보이는 글을 쓰지 않는다 (12.5).
     */
    public static final int CONTENT_VERSION = 3;
    public static final List<String> FILES = List.of("skills.yml", "weapons.yml");
    private static final String DIR = "content";

    private final JavaPlugin plugin;

    public Content(JavaPlugin plugin) {
        this.plugin = plugin;
    }

    public void extract() {
        File dir = new File(plugin.getDataFolder(), DIR);
        File verFile = new File(plugin.getDataFolder(), "content-version.txt");
        int stored = 0;
        if (verFile.exists()) {
            try {
                stored = Integer.parseInt(Files.readString(verFile.toPath(), StandardCharsets.UTF_8).trim());
            } catch (IOException | NumberFormatException ex) {
                stored = 0;
            }
        }
        boolean upgraded = true;
        if (stored < CONTENT_VERSION) {
            List<String> old = new ArrayList<>();
            for (String f : FILES) if (new File(dir, f).exists()) old.add(f);
            if (!old.isEmpty()) upgraded = backup(dir, old, Math.max(1, stored));
        }
        for (String f : FILES) {
            if (!new File(dir, f).exists()) plugin.saveResource(DIR + "/" + f, false);
        }
        // 옮기다 실패했으면 판을 올리지 않아 다음에 다시 시도한다
        if (upgraded && stored < CONTENT_VERSION) {
            try {
                Files.writeString(verFile.toPath(), CONTENT_VERSION + "\n", StandardCharsets.UTF_8);
            } catch (IOException ex) {
                plugin.getLogger().warning("content-version.txt 를 쓰지 못했습니다: " + ex.getMessage());
            }
        }
    }

    private boolean backup(File dir, List<String> files, int fromVersion) {
        File base = plugin.getDataFolder();
        File backup = new File(base, "old-content-v" + fromVersion);
        for (int n = 2; backup.exists(); n++) backup = new File(base, "old-content-v" + fromVersion + "-" + n);
        List<String> moved = new ArrayList<>();
        try {
            Files.createDirectories(backup.toPath());
            for (String f : files) {
                Files.move(new File(dir, f).toPath(), new File(backup, f).toPath());
                moved.add(f);
            }
        } catch (IOException ex) {
            // 옛 파일과 새 파일이 섞이면 id 가 어긋나므로, 옮긴 것을 되돌려 옛 판 그대로 쓴다
            for (String f : moved) {
                try {
                    Files.move(new File(backup, f).toPath(), new File(dir, f).toPath());
                } catch (IOException ignored) {
                    // 되돌리지 못한 파일은 백업 폴더에 남아 있다
                }
            }
            plugin.getLogger().warning("예전 콘텐츠 파일을 " + backup.getName() + "/ 로 옮기지 못해 그대로 씁니다: " + ex.getMessage());
            return false;
        }
        plugin.getLogger().info("콘텐츠가 새 판(v" + CONTENT_VERSION + ")으로 바뀌어 예전 " + String.join(", ", files) + " 을 "
                + backup.getName() + "/ 에 옮겨 두고 새로 꺼냈습니다. 고친 내용이 있으면 그 폴더에서 옮겨 오세요.");
        return true;
    }

    /** content/<name> 을 읽는다. 사용자가 지운 항목은 채우지 않고, 파일이 깨졌을 때만 jar 기본값을 쓴다. */
    public YamlConfiguration yml(String name) {
        File f = new File(new File(plugin.getDataFolder(), DIR), name);
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        if (y.getKeys(false).isEmpty()) {
            try (InputStream in = plugin.getResource(DIR + "/" + name)) {
                if (in != null) y = YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
            } catch (IOException ignored) {
                // 기본값도 못 읽으면 빈 채로 둔다
            }
        }
        return y;
    }
}
