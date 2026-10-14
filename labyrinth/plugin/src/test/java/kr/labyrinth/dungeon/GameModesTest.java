package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.bukkit.GameMode;
import org.junit.jupiter.api.Test;

/** 미궁 안 게임 모드 규칙 — 크리에이티브로 들어왔다 재접속해도 서바이벌이어야 보스가 공격한다. */
class GameModesTest {

    @Test
    void normalEntryAlwaysSurvival() {
        for (GameMode m : GameMode.values()) assertEquals(GameMode.SURVIVAL, GameModes.onEnter(m, false), m.name());
    }

    @Test
    void adminEntryKeepsMode() {
        assertEquals(GameMode.CREATIVE, GameModes.onEnter(GameMode.CREATIVE, true));
        assertEquals(GameMode.SURVIVAL, GameModes.onEnter(GameMode.SPECTATOR, true));
    }

    @Test
    void rememberedModeRestoresOnLeave() {
        assertEquals(GameMode.CREATIVE, GameModes.remembered(GameMode.CREATIVE));
        assertEquals(GameMode.ADVENTURE, GameModes.remembered(GameMode.ADVENTURE));
        assertEquals(GameMode.SURVIVAL, GameModes.remembered(GameMode.SPECTATOR));
        assertEquals(GameMode.SURVIVAL, GameModes.remembered(null));
    }

    @Test
    void rejoinNeverRestoresCreative() {
        // 크리에이티브로 입장 → 안에서 서바이벌 → 재접속: 서바이벌 (예전엔 입장 전 크리에이티브로 되돌아감)
        assertEquals(GameMode.SURVIVAL, GameModes.onRejoin(false, GameMode.SURVIVAL, false));
        assertEquals(GameMode.SURVIVAL, GameModes.onRejoin(false, GameMode.CREATIVE, false));
        assertEquals(GameMode.SURVIVAL, GameModes.onRejoin(false, GameMode.SPECTATOR, false));
        assertEquals(GameMode.SPECTATOR, GameModes.onRejoin(true, GameMode.SURVIVAL, false));
        assertEquals(GameMode.SPECTATOR, GameModes.onRejoin(true, GameMode.CREATIVE, false));
    }

    @Test
    void adminRejoinKeepsCurrentMode() {
        assertEquals(GameMode.CREATIVE, GameModes.onRejoin(false, GameMode.CREATIVE, true));
        assertEquals(GameMode.SURVIVAL, GameModes.onRejoin(false, GameMode.SURVIVAL, true));
        assertEquals(GameMode.SURVIVAL, GameModes.onRejoin(false, GameMode.SPECTATOR, true));
        assertEquals(GameMode.SPECTATOR, GameModes.onRejoin(true, GameMode.CREATIVE, true));
    }

    @Test
    void reviveIsSurvival() {
        assertEquals(GameMode.SURVIVAL, GameModes.onRevive());
    }
}
