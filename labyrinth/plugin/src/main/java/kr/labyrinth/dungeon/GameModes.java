package kr.labyrinth.dungeon;

import org.bukkit.GameMode;

/**
 * 미궁 안 게임 모드 규칙 (순수 로직 — 단위 테스트 대상). 보스·몹은 크리에이티브·관전 플레이어를 노리지 않으므로
 * 공략 중인 파티원은 살아 있으면 항상 서바이벌, 쓰러졌으면 관전이어야 한다. 입장 전 모드는 미궁을 나갈 때만 되돌린다.
 * 관리자 테스트 입장(/labadmin tpfloor)만 예외로 지금 모드를 유지한다.
 */
public final class GameModes {

    private GameModes() {}

    /** 미궁을 나갈 때 되돌릴 입장 전 모드 (관전 중에 들어왔으면 서바이벌로). */
    public static GameMode remembered(GameMode before) {
        return before == null || before == GameMode.SPECTATOR ? GameMode.SURVIVAL : before;
    }

    /** 입장 직후 모드: 일반(파티·솔로) 입장 = 서바이벌, 관리자 테스트 입장 = 지금 모드 유지(관전이면 서바이벌). */
    public static GameMode onEnter(GameMode current, boolean adminTest) {
        return adminTest ? remembered(current) : GameMode.SURVIVAL;
    }

    /**
     * 재접속 때 모드: 쓰러진 상태 = 관전, 아니면 서바이벌. 입장 전 모드(크리에이티브 등)로 되돌리지 않는다.
     * 관리자 테스트 입장은 나갈 때의 모드를 그대로 두되 관전으로 남아 있으면 서바이벌.
     */
    public static GameMode onRejoin(boolean dead, GameMode current, boolean adminTest) {
        if (dead) return GameMode.SPECTATOR;
        return adminTest ? remembered(current) : GameMode.SURVIVAL;
    }

    /** 부활 때 모드: 항상 서바이벌. */
    public static GameMode onRevive() { return GameMode.SURVIVAL; }
}
