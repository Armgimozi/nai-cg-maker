package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.junit.jupiter.api.Test;

/**
 * 0.3.7 광산 PvP 이벤트 차례 — 미궁 쓰러짐·싸우는 중 끊김과 같은 자리에 선다.
 * <ul>
 *   <li>죽음 = HIGH + ignoreCancelled (DungeonManager.onDeath 와 같음 — DeathKeep HIGHEST·MONITOR 는 ignoreCancelled 라 취소된 죽음을 건너뜀)</li>
 *   <li>끊김 판정 = LOW: 시전 취소(NORMAL)·스탯 정리·데이터 저장(MONITOR)보다 먼저</li>
 *   <li>바닐라 피해 문 = MineListener LOWEST·HIGHEST, 근접·화살은 그 사이 CombatListener HIGH 가 DamageService 로</li>
 *   <li>/미궁 마을 (VillageService.teleport) 이 holdExit 을 부르고, 승강기(MineLift.go) 가 싸우는 중 시전을 본다</li>
 * </ul>
 */
class MinePvpOrderTest {

    private static EventHandler handler(String cls, String method, Class<? extends Event> type) throws Exception {
        Method m = Class.forName(cls).getDeclaredMethod(method, type);
        EventHandler h = m.getAnnotation(EventHandler.class);
        assertTrue(h != null, cls + "." + method + " 은 @EventHandler");
        return h;
    }

    @Test
    void knockDownSitsWhereTheDungeonDownSits() throws Exception {
        EventHandler mine = handler("kr.labyrinth.mine.MinePvp", "onDeath", PlayerDeathEvent.class);
        EventHandler dungeon = handler("kr.labyrinth.dungeon.DungeonManager", "onDeath", PlayerDeathEvent.class);
        assertEquals(EventPriority.HIGH, mine.priority());
        assertTrue(mine.ignoreCancelled());
        assertEquals(dungeon.priority(), mine.priority());
        EventHandler keep = handler("kr.labyrinth.core.DeathKeep", "onDeath", PlayerDeathEvent.class);
        EventHandler xp = handler("kr.labyrinth.core.DeathKeep", "onDeathPenalty", PlayerDeathEvent.class);
        assertTrue(keep.priority().getSlot() > mine.priority().getSlot() && keep.ignoreCancelled(), "인벤세이브는 취소된 쓰러짐을 건너뜀");
        assertTrue(xp.priority().getSlot() > mine.priority().getSlot() && xp.ignoreCancelled(), "경험치를 두 번 빼지 않음");
        EventHandler line = handler("kr.labyrinth.pvp.PvpListener", "onDeath", PlayerDeathEvent.class);
        assertEquals(EventPriority.MONITOR, line.priority());
        assertTrue(!line.ignoreCancelled(), "죽음 줄은 취소된 쓰러짐에도 (당사자 둘에게)");
        EventHandler real = handler("kr.labyrinth.mine.MinePvp", "onRealDeath", PlayerDeathEvent.class);
        assertTrue(real.ignoreCancelled() && real.priority() == EventPriority.MONITOR, "PvP 아닌 진짜 죽음만 부활 자리 표시");
        assertEquals(EventPriority.HIGHEST, handler("kr.labyrinth.mine.MinePvp", "onRespawn", PlayerRespawnEvent.class).priority());
    }

    @Test
    void quitDecisionBeforeCastsCancelAndDataSave() throws Exception {
        EventPriority decide = handler("kr.labyrinth.mine.MinePvp", "onQuit", PlayerQuitEvent.class).priority();
        assertEquals(EventPriority.LOW, decide);
        assertEquals(handler("kr.labyrinth.dungeon.DungeonManager", "onQuitInCombat", PlayerQuitEvent.class).priority(), decide,
                "미궁 끊김 판정과 같은 자리");
        for (String[] later : new String[][] {
                {"kr.labyrinth.mine.MinePvp", "onQuitCleanup"},
                {"kr.labyrinth.mine.MinePvp", "onQuitDone"},
                {"kr.labyrinth.stats.StatService", "onQuit"},
                {"kr.labyrinth.data.PlayerDataService", "onQuit"},
                {"kr.labyrinth.mine.MineListener", "onQuit"}}) {
            EventPriority p = handler(later[0], later[1], PlayerQuitEvent.class).priority();
            assertTrue(p.getSlot() > decide.getSlot(), later[0] + "." + later[1] + " (" + p + ") 은 판정 뒤에 돌아야 한다");
        }
        assertEquals(EventPriority.MONITOR, handler("kr.labyrinth.data.PlayerDataService", "onQuit", PlayerQuitEvent.class).priority());
    }

    @Test
    void damageGateAroundCombatListener() throws Exception {
        assertEquals(EventPriority.LOWEST, handler("kr.labyrinth.mine.MineListener", "onDamageEarly", EntityDamageEvent.class).priority());
        assertEquals(EventPriority.HIGHEST, handler("kr.labyrinth.mine.MineListener", "onDamageLate", EntityDamageEvent.class).priority());
        EventHandler combat = handler("kr.labyrinth.combat.CombatListener", "onDamage", EntityDamageEvent.class);
        assertEquals(EventPriority.HIGH, combat.priority());
        assertTrue(combat.ignoreCancelled(), "LOWEST 에서 막힌 피해는 DamageService 로 가지 않음");
        EventHandler tp = handler("kr.labyrinth.mine.MinePvp", "onTeleport", PlayerTeleportEvent.class);
        assertTrue(tp.ignoreCancelled());
    }

    @Test
    void exitPathsAskTheCast() throws Exception {
        String village = Files.readString(Path.of("src/main/java/kr/labyrinth/village/VillageService.java"));
        int teleport = village.indexOf("    void teleport(Player p) {");
        int hold = village.indexOf("services().mine().holdExit(p, () -> teleport(p))");
        int go = village.indexOf("kr.labyrinth.core.Teleports.to(p, to);", teleport);
        assertTrue(teleport > 0 && hold > teleport && hold < go, "/미궁 마을 · 메인 메뉴 '마을' 은 보내기 전에 holdExit");
        String lift = Files.readString(Path.of("src/main/java/kr/labyrinth/mine/MineLift.java"));
        int g = lift.indexOf("private void go(");
        assertTrue(g > 0 && lift.indexOf("module.pvp().exitCastSeconds(p)", g) > g, "승강기 타기가 싸우는 중 시전을 봄");
        assertTrue(lift.indexOf("module.pvp().runBypassed(p, () -> kr.labyrinth.core.Teleports.to(p, to))", g) > g,
                "승강기 도착은 허락한 순간이동");
        String menu = Files.readString(Path.of("src/main/java/kr/labyrinth/ui/menus/MainMenu.java"));
        assertTrue(menu.contains("VillageService.teleportCommand(ctx.player())"), "메인 메뉴 '마을' = /미궁 마을 과 같은 길");
        String dungeon = Files.readString(Path.of("src/main/java/kr/labyrinth/dungeon/DungeonManager.java"));
        int enter = dungeon.indexOf("private boolean enter(Player leader, int floor, boolean admin)");
        assertTrue(enter > 0 && dungeon.indexOf("services.mine().inPvpCombat(m)", enter) > enter,
                "미궁 입장(미룰 수 없는 광산 밖 이동)은 광산에서 싸우는 중이면 거절");
        String listener = Files.readString(Path.of("src/main/java/kr/labyrinth/mine/MineListener.java"));
        int spawn = listener.indexOf("public void onSpawn(EntitySpawnEvent e)");
        assertTrue(spawn > 0 && listener.indexOf("AbstractWindCharge", spawn) > spawn, "돌풍구는 광산 PvP 가 켜져도 막음 (안전 구역 사람을 밀어냄)");
        String pvp = Files.readString(Path.of("src/main/java/kr/labyrinth/mine/MinePvp.java"));
        assertTrue(pvp.contains("MinePvpRules.vanillaGate(on, true, applying, e.getCause(), enemy)"), "바닐라 피해 문 = 순수 규칙");
        assertTrue(pvp.contains("DeathPenalty.onMineDown(s, p, MinePvpRules.where(module.config().pvp().penalty()))"), "미궁과 같은 페널티 길");
        assertTrue(pvp.contains("DeathPenalty.onMineCombatQuit("), "끊김도 같은 길");
    }
}
