package kr.labyrinth.core;

import java.io.File;
import java.io.IOException;
import java.time.Instant;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * 서버 난이도 잠금 (0.3.5.3) — 한 번 정한 난이도는 다시 바꿀 수 없다.
 * plugins/Labyrinth/difficulty-lock.yml 에 처음 정한 난이도를 적어 두고, config.yml 의 difficulty 가 달라지면(직접 고치거나
 * config.yml 을 새로 덮어써도) 잠긴 값으로 되돌린다. 푸는 길은 서버 콘솔의 {@code labadmin difficulty unlock} 하나뿐.
 */
public final class DifficultyLock {

    public static final String FILE = "difficulty-lock.yml";

    private DifficultyLock() {}

    /** 잠긴 난이도 id (없으면 null). */
    public static String read(File dataFolder) {
        File f = new File(dataFolder, FILE);
        if (!f.isFile()) return null;
        String id = YamlConfiguration.loadConfiguration(f).getString("difficulty", "");
        id = id == null ? "" : id.trim().toLowerCase(java.util.Locale.ROOT);
        return id.isEmpty() ? null : id;
    }

    public static void write(File dataFolder, String id, String by) {
        YamlConfiguration y = new YamlConfiguration();
        y.options().setHeader(java.util.List.of(
                "서버 난이도 잠금 — 한 번 정한 난이도는 바꿀 수 없습니다.",
                "config.yml 의 difficulty 를 고쳐도 이 값으로 되돌아갑니다. 풀려면 서버 콘솔에서: labadmin difficulty unlock"));
        y.set("difficulty", id);
        y.set("locked_at", Instant.now().toString());
        y.set("by", by == null ? "" : by);
        try {
            dataFolder.mkdirs();
            y.save(new File(dataFolder, FILE));
        } catch (IOException e) {
            Log.warn("난이도 잠금 파일 저장 실패: " + e.getMessage());
        }
    }

    public static boolean delete(File dataFolder) {
        File f = new File(dataFolder, FILE);
        return f.isFile() && f.delete();
    }

    /** 켤 때·다시 읽을 때 할 일. */
    public enum Action { NONE, ADOPT, RESTORE }

    /**
     * @param locked     잠긴 id (없으면 null)
     * @param configured config.yml 의 difficulty (비었으면 "")
     * @param valid      configured 가 아는 난이도인가
     * @return ADOPT = 잠금이 없고 이미 정해진 난이도가 있음 → 그 값을 잠금 (예전 판에서 올라온 서버),
     *         RESTORE = 잠금과 config 가 다름 → config 를 잠긴 값으로 되돌림, NONE = 그대로
     */
    public static Action decide(String locked, String configured, boolean valid) {
        String c = configured == null ? "" : configured.trim().toLowerCase(java.util.Locale.ROOT);
        if (locked == null) return !c.isEmpty() && valid ? Action.ADOPT : Action.NONE;
        return locked.equals(c) ? Action.NONE : Action.RESTORE;
    }
}
