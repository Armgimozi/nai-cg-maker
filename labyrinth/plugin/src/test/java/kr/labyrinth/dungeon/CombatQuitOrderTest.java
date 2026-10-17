package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.player.PlayerQuitEvent;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.2 싸우는 중 접속 끊김 판정의 순서. 판정(DungeonManager.onQuitInCombat)은
 * 시전 취소(ExitCast · 귀환 주문서)와 스탯 캐시 정리보다 먼저 — 시전 중인지·최대 HP 를 보려면,
 * 플레이어 데이터 저장(MONITOR)보다 먼저 — 잃은 골드·경험치·안내가 저장되게.
 */
class CombatQuitOrderTest {

    private static EventPriority priority(String cls, String method) throws Exception {
        EventHandler h = Class.forName(cls).getDeclaredMethod(method, PlayerQuitEvent.class).getAnnotation(EventHandler.class);
        return h.priority();
    }

    @Test
    void decidesBeforeCastsAreCancelledAndBeforeDataIsSaved() throws Exception {
        EventPriority decide = priority("kr.labyrinth.dungeon.DungeonManager", "onQuitInCombat");
        assertEquals(EventPriority.LOW, decide);
        for (String[] later : new String[][] {
                {"kr.labyrinth.dungeon.ExitCast", "onQuit"},
                {"kr.labyrinth.items.ConsumableListener", "onQuit"},
                {"kr.labyrinth.stats.StatService", "onQuit"},
                {"kr.labyrinth.data.PlayerDataService", "onQuit"},
                {"kr.labyrinth.ui.LabHudService", "onQuit"},
                {"kr.labyrinth.dungeon.DungeonManager", "onQuit"}}) {
            EventPriority p = priority(later[0], later[1]);
            assertTrue(p.getSlot() > decide.getSlot(), later[0] + "." + later[1] + " (" + p + ") 은 판정 뒤에 돌아야 한다");
        }
        assertEquals(EventPriority.MONITOR, priority("kr.labyrinth.data.PlayerDataService", "onQuit"), "저장은 맨 끝");
    }
}
