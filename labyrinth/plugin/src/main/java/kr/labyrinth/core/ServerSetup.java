package kr.labyrinth.core;

import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * 서버 난이도 설정 (초기 설정 · 변경) 의 단일 경로.
 * config {@code setup.everyone_can_set_difficulty}(기본 true) 면 op 가 아닌 플레이어도 정할 수 있다.
 */
public final class ServerSetup {

    private ServerSetup() {}

    /** 이 사람이 서버 난이도를 정하거나 바꿀 수 있는가. 콘솔·관리자는 항상 가능. */
    public static boolean canSetDifficulty(CommandSender s) {
        if (!(s instanceof Player p)) return true;
        if (p.hasPermission(CommandService.PERM_ADMIN)) return true;
        return Services.get().plugin().getConfig().getBoolean("setup.everyone_can_set_difficulty", true);
    }

    /** 잠긴 난이도 id (한 번 정했으면 그 값, 아직이면 null). */
    public static String lockedDifficulty() {
        return DifficultyLock.read(Services.get().plugin().getDataFolder());
    }

    /** 초기 설정 메뉴를 열 수 있는가 — 난이도가 잠겼으면 아무도 못 연다 (0.3.5.3). */
    public static boolean canOpenSetup(CommandSender s) {
        return lockedDifficulty() == null && canSetDifficulty(s);
    }

    /**
     * 켤 때·labadmin reload 때: 잠금이 있으면 config.yml 의 difficulty 를 잠긴 값으로 맞추고, 잠금이 없는데 난이도가 이미
     * 정해져 있으면(예전 판에서 올라온 서버) 그 값을 잠근다.
     */
    public static void enforceLock(Services services) {
        java.io.File dir = services.plugin().getDataFolder();
        String locked = DifficultyLock.read(dir);
        String configured = services.plugin().getConfig().getString("difficulty", "");
        boolean valid = configured != null && services.settings().difficulty(configured.trim().toLowerCase(java.util.Locale.ROOT)) != null;
        switch (DifficultyLock.decide(locked, configured, valid)) {
            case ADOPT -> {
                DifficultyLock.write(dir, services.settings().difficulty().id(), "config");
                Log.info("서버 난이도 잠금: " + services.settings().difficulty().name() + " (한 번 정한 난이도는 바꿀 수 없습니다)");
            }
            case RESTORE -> {
                if (services.settings().difficulty(locked) == null) {
                    Log.warn("난이도 잠금 파일의 값(" + locked + ")을 모릅니다 — 잠금을 무시합니다. (difficulty-lock.yml)");
                    return;
                }
                services.updateConfig(c -> c.set("difficulty", locked));
                Log.warn("config.yml 의 difficulty 가 잠긴 난이도와 달라 되돌렸습니다: " + services.settings().difficulty(locked).name()
                        + " (한 번 정한 난이도는 바꿀 수 없습니다 — 풀려면 콘솔에서 labadmin difficulty unlock)");
            }
            case NONE -> { }
        }
    }

    /** 콘솔 전용: 잠금 풀기 (다음에 다시 한 번 정할 수 있게). */
    public static void unlock(CommandSender s) {
        if (!(s instanceof org.bukkit.command.ConsoleCommandSender)) {
            Text.error(s, "난이도 잠금은 서버 콘솔에서만 풀 수 있습니다.");
            return;
        }
        Services services = Services.get();
        boolean had = DifficultyLock.delete(services.plugin().getDataFolder());
        Text.send(s, had ? "<yellow>난이도 잠금을 풀었습니다.</yellow> <gray>labadmin setup <난이도> 로 한 번 더 정할 수 있습니다 (정하면 다시 잠김)."
                : "<gray>잠긴 난이도가 없습니다.");
    }

    /** 난이도 적용. 첫 설정이면 미궁 개방을 방송하고 잠근다 — 잠긴 뒤에는 바꿀 수 없다. @return 성공 여부 */
    public static boolean applyDifficulty(CommandSender s, String id) {
        Services services = Services.get();
        if ("unlock".equalsIgnoreCase(id)) {
            unlock(s);
            return false;
        }
        String locked = lockedDifficulty();
        if (locked != null) {
            Difficulty cur = services.settings().difficulty(locked);
            String name = cur == null ? locked : cur.name();
            if (locked.equalsIgnoreCase(id)) {
                Text.send(s, "<gray>서버 난이도는 이미 <white>" + name + "</white> 입니다.");
            } else {
                Text.error(s, "서버 난이도는 한 번 정하면 바꿀 수 없습니다. (지금: " + name + ")"
                        + (s instanceof org.bukkit.command.ConsoleCommandSender ? " — 꼭 바꿔야 하면 labadmin difficulty unlock" : ""));
            }
            return false;
        }
        if (!canSetDifficulty(s)) {
            Text.error(s, "서버 난이도는 관리자만 정할 수 있습니다. (config setup.everyone_can_set_difficulty)");
            return false;
        }
        Difficulty d = services.settings().difficulty(id);
        if (d == null) {
            Text.error(s, "난이도는 easy / normal / hard / nightmare 중 하나입니다.");
            return false;
        }
        boolean first = !services.settings().isDifficultySet();
        services.updateConfig(c -> c.set("difficulty", d.id()));
        DifficultyLock.write(services.plugin().getDataFolder(), d.id(), s.getName());
        // 난이도 배율 한 벌 (예: "HP ×1.8·피해 ×1.6"). 관리자가 층 램프를 직접 적었을 때만 "1층 HP … → N층부터 …"
        Text.send(s, "<green>서버 난이도: <white>" + d.name() + "</white></green> <gray>(몹 " + d.hpDamageText()
                + (d.drop() != 1.0 || d.xp() != 1.0 ? ", 드롭 ×" + Difficulty.mult(d.drop()) + ", 경험치 ×" + Difficulty.mult(d.xp()) : "")
                + ")");
        if (first) {
            Bukkit.getServer().sendMessage(Text.mm(Text.PREFIX + "<gold>미궁이 열렸습니다!</gold> <gray>난이도 <white>"
                    + d.name() + "</white> · <white>/미궁</white> 으로 시작하세요. <dark_gray>(난이도는 이제 바꿀 수 없습니다)"));
        } else {
            Bukkit.getServer().sendMessage(Text.mm(Text.PREFIX + "<gray>" + s.getName() + " 님이 서버 난이도를 바꿨습니다: <white>"
                    + d.name() + "</white> (진행 중인 공략은 다음 입장부터 적용)"));
        }
        return true;
    }
}
