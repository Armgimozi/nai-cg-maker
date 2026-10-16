package kr.labyrinth.mine;

import org.bukkit.GameMode;

/**
 * 광산 게임 모드 — 기억 없이 규칙만 (R §2-3, 계약 §2.2). 순수.
 * <ul>
 *   <li>광산 월드 안 = 어드벤처 (부술 수 있는 것 = 곡괭이 CAN_BREAK 광맥뿐)</li>
 *   <li>광산 밖인데 어드벤처 = 서바이벌 (미궁·마을로 나갔을 때 어드벤처에 갇히지 않게)</li>
 *   <li>크리에이티브·관전은 어디서든 건드리지 않는다 (관리자)</li>
 * </ul>
 * 접속·월드 이동·리스폰·텔레포트 때 같은 규칙을 쓴다. 이전 모드를 저장하지 않는다 (ext mine.prev_mode 없음).
 */
public final class MineGameModeRule {

    private MineGameModeRule() {}

    /** 바꿀 모드 (바꿀 필요 없으면 null). */
    public static GameMode target(GameMode current, boolean inMineWorld) {
        if (current == null || current == GameMode.CREATIVE || current == GameMode.SPECTATOR) return null;
        if (inMineWorld) return current == GameMode.ADVENTURE ? null : GameMode.ADVENTURE;
        return current == GameMode.ADVENTURE ? GameMode.SURVIVAL : null;
    }
}
