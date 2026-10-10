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
     * 스물. 4: 1.3판 능력치 열쇠 (att → int, 모든 근접 무기에 근력·민첩 보정, 곤봉 필요 근력 10) 와 출신 여섯 origins.yml.
     * 5: 장비에서 보정 (scaling) 과 요구 능력치 (requires) 를 없앴다 (DECISIONS 2026-10-10). 방패는 absorb·stability·parry·fire 대신
     * 막기 guard 하나, 촉매는 술법 세기 spell, 패링 단검은 막지 않는 왼손 무기 (use: none, attack), 경비대 방패의 분류는 medium_shield.
     * 패링 창은 분류마다 config.yml combat.parry.windows). 6: 같은 분류의 무거운 무기 공격력 (장검 66, 용병 도끼 78, 참회자 메이스 80,
     * 간수장 미늘창 94, 창 60), 대방패 무게 14, 판자 방패 무게 1.0, 촉매는 왼손 (hand: off, 마법사의 쇠단지도 왼손으로).
     * 새 파일 (반지 rings.yml, 9.4) 은 없을 때 꺼내므로 판을 올리지 않는다 (판을 올리면 고친 옛 파일까지 옮겨진다).
     * 콘텐츠에는 보이는 글을 쓰지 않는다 (12.5).
     */
    public static final int CONTENT_VERSION = 6;
    public static final List<String> FILES = List.of("skills.yml", "weapons.yml", "origins.yml", "rings.yml");
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
