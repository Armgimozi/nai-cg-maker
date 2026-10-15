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

    /** 난이도 적용. 첫 설정이면 미궁 개방을 방송한다. @return 성공 여부 */
    public static boolean applyDifficulty(CommandSender s, String id) {
        Services services = Services.get();
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
        // 난이도 배율 한 벌 (예: "HP ×1.8·피해 ×1.6"). 관리자가 층 램프를 직접 적었을 때만 "1층 HP … → N층부터 …"
        Text.send(s, "<green>서버 난이도: <white>" + d.name() + "</white></green> <gray>(몹 " + d.hpDamageText() + ", 드롭 ×"
                + Difficulty.mult(d.drop()) + ", 경험치 ×" + Difficulty.mult(d.xp()) + ")");
        if (first) {
            Bukkit.getServer().sendMessage(Text.mm(Text.PREFIX + "<gold>미궁이 열렸습니다!</gold> <gray>난이도 <white>"
                    + d.name() + "</white> · <white>/미궁</white> 으로 시작하세요."));
        } else {
            Bukkit.getServer().sendMessage(Text.mm(Text.PREFIX + "<gray>" + s.getName() + " 님이 서버 난이도를 바꿨습니다: <white>"
                    + d.name() + "</white> (진행 중인 공략은 다음 입장부터 적용)"));
        }
        return true;
    }
}
