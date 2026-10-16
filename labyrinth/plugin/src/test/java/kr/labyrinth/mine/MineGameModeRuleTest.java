package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.bukkit.GameMode;
import org.junit.jupiter.api.Test;

/** 게임 모드 — 기억 없이 규칙만 (계약 §2.2): 광산 안 = 어드벤처 · 밖인데 어드벤처 = 서바이벌 · 크리에이티브·관전 그대로. */
class MineGameModeRuleTest {

    @Test
    void insideMineIsAdventure() {
        assertEquals(GameMode.ADVENTURE, MineGameModeRule.target(GameMode.SURVIVAL, true));
        assertNull(MineGameModeRule.target(GameMode.ADVENTURE, true));
    }

    @Test
    void outsideAdventureBecomesSurvival() {
        assertEquals(GameMode.SURVIVAL, MineGameModeRule.target(GameMode.ADVENTURE, false));
        assertNull(MineGameModeRule.target(GameMode.SURVIVAL, false));
    }

    @Test
    void creativeAndSpectatorUntouched() {
        for (boolean in : new boolean[] {true, false}) {
            assertNull(MineGameModeRule.target(GameMode.CREATIVE, in));
            assertNull(MineGameModeRule.target(GameMode.SPECTATOR, in));
        }
        assertNull(MineGameModeRule.target(null, true));
    }

    @Test
    void noMemoryRoundTrip() {
        // 광산 → 미궁(서바이벌로 들어감, 나갈 때 "입장 전 모드" = 어드벤처로 되돌림) → 마을: 규칙만으로 서바이벌
        GameMode m = GameMode.SURVIVAL;
        GameMode t = MineGameModeRule.target(m, true);
        m = t == null ? m : t;
        assertEquals(GameMode.ADVENTURE, m);
        GameMode restoredByDungeon = m;
        t = MineGameModeRule.target(restoredByDungeon, false);
        assertEquals(GameMode.SURVIVAL, t);
        assertEquals(java.util.List.of("mine.free_pickaxe", "mat036.notice"), MineNames.EXT_KEYS, "ext mine.prev_mode 없음");
    }
}
