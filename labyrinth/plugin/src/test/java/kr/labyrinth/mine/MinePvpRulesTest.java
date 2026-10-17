package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.EnumSet;
import java.util.Set;
import kr.labyrinth.core.DeathPenaltyRules;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import kr.labyrinth.core.DeathPenaltyRules.QuitVerdict;
import kr.labyrinth.core.DeathPenaltyRules.Where;
import kr.labyrinth.core.Text;
import kr.labyrinth.mine.MinePvpRules.MineQuit;
import org.bukkit.event.entity.EntityDamageEvent.DamageCause;
import org.bukkit.event.player.PlayerKickEvent;
import org.junit.jupiter.api.Test;

/**
 * 0.3.7 광산 PvP 순수 규칙 ({@link MinePvpRules}): 바닐라 피해 원인 표 · 쓰러짐 곳 · 나가기 시전 초 · 싸우는 중 끊김 조합.
 * 주인 결정: PvP 쓰러짐 = "던전과 같게" — 시전·끊김도 미궁과 같은 조건에 "PvP 구역에 서 있음" 하나를 더한다.
 */
class MinePvpRulesTest {

    private static final QuitVerdict APPLY = QuitVerdict.APPLY;
    private static final QuitVerdict NONE = QuitVerdict.NONE;

    // ── 바닐라 피해 원인 ────────────────────────────────────────────────

    @Test
    void onlyPlayerDamageCausesCanPass() {
        Set<DamageCause> pvp = EnumSet.of(DamageCause.ENTITY_ATTACK, DamageCause.ENTITY_SWEEP_ATTACK, DamageCause.PROJECTILE,
                DamageCause.MAGIC, DamageCause.THORNS, DamageCause.ENTITY_EXPLOSION);
        for (DamageCause c : DamageCause.values()) {
            assertEquals(pvp.contains(c), MinePvpRules.vanillaPvpCause(c), c.name());
        }
        for (DamageCause c : new DamageCause[] {DamageCause.FALL, DamageCause.FIRE, DamageCause.FIRE_TICK, DamageCause.LAVA,
                DamageCause.DROWNING, DamageCause.SUFFOCATION, DamageCause.POISON, DamageCause.WITHER, DamageCause.VOID,
                DamageCause.KILL, DamageCause.CUSTOM, DamageCause.BLOCK_EXPLOSION, DamageCause.STARVATION, DamageCause.FREEZE}) {
            assertFalse(MinePvpRules.vanillaPvpCause(c), "떨어짐·불·환경·/kill 은 광산에서 언제나 0: " + c);
        }
        assertFalse(MinePvpRules.vanillaPvpCause(null));
    }

    @Test
    void vanillaGateLetsOnlyEnemyPlayerDamageThrough() {
        // 다른 파티 플레이어가 PvP 구역에서 친 근접·화살·물약·가시·폭죽
        for (DamageCause c : MinePvpRules.VANILLA_PVP_CAUSES) {
            assertTrue(MinePvpRules.vanillaGate(true, true, false, c, true), c.name());
            assertFalse(MinePvpRules.vanillaGate(true, true, false, c, false), "같은 파티 · 안전 구역 · 몹 · 자기 자신: " + c);
            assertFalse(MinePvpRules.vanillaGate(false, true, false, c, true), "광산 PvP 꺼짐: " + c);
        }
        // 떨어짐·불·독·/kill 은 때린 사람이 적이어도 0
        for (DamageCause c : new DamageCause[] {DamageCause.FALL, DamageCause.FIRE_TICK, DamageCause.LAVA, DamageCause.POISON,
                DamageCause.WITHER, DamageCause.VOID, DamageCause.KILL, DamageCause.CUSTOM, DamageCause.SUFFOCATION}) {
            assertFalse(MinePvpRules.vanillaGate(true, true, false, c, true), c.name());
        }
        // 미궁 피해 처리가 판정한 막타(바닐라 길)는 원인과 상관없이 통과 — 막으면 PvP 로 0 HP 가 되어도 안 죽는다
        assertTrue(MinePvpRules.vanillaGate(true, true, true, DamageCause.ENTITY_ATTACK, false));
        assertTrue(MinePvpRules.vanillaGate(true, true, true, DamageCause.CUSTOM, false));
        assertFalse(MinePvpRules.vanillaGate(false, true, true, DamageCause.ENTITY_ATTACK, true), "광산 PvP 꺼짐이면 막타도 막음 (0.3.6 처럼)");
        // 맞는 쪽이 플레이어가 아니면 (마네킹 등) 언제나 막음
        assertFalse(MinePvpRules.vanillaGate(true, false, true, DamageCause.ENTITY_ATTACK, true));
        assertFalse(MinePvpRules.vanillaGate(true, false, false, DamageCause.ENTITY_ATTACK, true));
        assertFalse(MinePvpRules.vanillaGate(true, true, false, null, true));
    }

    @Test
    void whereFollowsPenaltySwitch() {
        assertEquals(Where.MINE_PVP, MinePvpRules.where(true));
        assertEquals(Where.OUTSIDE, MinePvpRules.where(false));
    }

    // ── 나가기 시전 ─────────────────────────────────────────────────────

    @Test
    void exitCastOnlyOnPvpGroundInCombat() {
        Config c = Config.DEFAULT;
        assertEquals(5.0, MinePvpRules.exitCastSeconds(c, true, true, true, true, 1_000), "PvP 구역 · 1초 전에 맞음");
        assertEquals(5.0, MinePvpRules.exitCastSeconds(c, true, true, true, true, 9_999));
        assertEquals(0.0, MinePvpRules.exitCastSeconds(c, true, true, true, true, 10_000), "10초 지나면 바로");
        assertEquals(0.0, MinePvpRules.exitCastSeconds(c, true, true, true, true, -1), "싸운 적 없음");
        assertEquals(0.0, MinePvpRules.exitCastSeconds(c, true, true, false, true, 0), "안전 구역(승강기 홀)에서는 바로");
        assertEquals(0.0, MinePvpRules.exitCastSeconds(c, true, false, true, true, 0), "광산 PvP 꺼짐");
        assertEquals(0.0, MinePvpRules.exitCastSeconds(c, true, true, true, false, 0), "죽어 있음 · 크리에이티브·관전");
        assertEquals(5.0, MinePvpRules.exitCastSeconds(c, false, true, true, true, 0), "mine.pvp.penalty: false 여도 경험치를 잃으니 시전");
        assertEquals(0.0, MinePvpRules.exitCastSeconds(Config.OFF, true, true, true, true, 0), "death.penalty: false");
        assertEquals(0.0, MinePvpRules.exitCastSeconds(new Config(true, true, 2, 3, Set.of(), 0), true, true, true, true, 0),
                "combat_exit_seconds: 0");
        Config noXp = new Config(false, true, 2, 3, Set.of());
        assertEquals(5.0, MinePvpRules.exitCastSeconds(noXp, true, true, true, true, 0), "물건·골드만 켜도");
        assertEquals(0.0, MinePvpRules.exitCastSeconds(noXp, false, true, true, true, 0), "penalty false · 경험치 끔 = 잃을 것 없음 → 바로");
        assertEquals(2.5, MinePvpRules.exitCastSeconds(new Config(true, true, 2, 3, Set.of(), 2.5), true, true, true, true, 0));
    }

    // ── 싸우는 중 끊김 ──────────────────────────────────────────────────

    /** 기본 형편: 광산 PvP 켜짐 · 광산 월드 · PvP 구역 · 살아 있음 · since ms 전 PvP · 시전 없음 · 플레이어가 끊음 · 막타 아님. */
    private static MineQuit quit(long since) {
        return new MineQuit(true, true, true, true, since, false, false, false);
    }

    @Test
    void quitInCombatOnPvpGroundIsADown() {
        Config c = Config.DEFAULT;
        assertEquals(APPLY, MinePvpRules.combatQuit(c, true, quit(0)));
        assertEquals(APPLY, MinePvpRules.combatQuit(c, true, quit(1_000)), "라이브 L10: 맞고 1초 뒤 끊음");
        assertEquals(APPLY, MinePvpRules.combatQuit(c, true, quit(9_999)));
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, quit(10_000)), "10초 지남");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, quit(11_000)), "라이브 L10: 11초 뒤");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, quit(-1)), "싸운 적 없음");
    }

    @Test
    void castingCountsEvenAfterTenSeconds() {
        Config c = Config.DEFAULT;
        // 9.9초에 /미궁 마을 → 5초 시전 → 14초에 끊음
        assertEquals(APPLY, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, true, true, 14_000, true, false, false)));
        assertEquals(APPLY, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, true, true, -1, true, false, false)));
    }

    @Test
    void safeZoneMineOffDeadCreativeOutsideAreNotADown() {
        Config c = Config.DEFAULT;
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, false, true, 0, false, false, false)),
                "안전 구역(승강기 홀)으로 들어간 뒤 끊음");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, false, true, 0, true, false, false)),
                "안전 구역에서 시전 중이어도");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(false, true, true, true, 0, false, false, false)), "광산 PvP 꺼짐");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, true, false, 0, false, false, false)),
                "죽어 있음 · 크리에이티브 · 관전");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(true, false, true, true, 0, false, false, false)), "광산 월드 밖");
    }

    @Test
    void serverSideNeverPenalises() {
        Config c = Config.DEFAULT;
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, true, true, 0, false, true, false)), "/stop · /restart · /kick");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, true, true, 0, true, true, false)), "시전 중이어도");
        assertEquals(NONE, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, true, true, 0, false, true, true)), "막타 뒤라도 서버 쪽이면");
        // 서버 쪽 끊김 원인 6개는 미궁과 같은 표 (DeathPenaltyRules.serverKick)
        for (PlayerKickEvent.Cause k : new PlayerKickEvent.Cause[] {PlayerKickEvent.Cause.RESTART_COMMAND, PlayerKickEvent.Cause.KICKED,
                PlayerKickEvent.Cause.BANNED, PlayerKickEvent.Cause.IP_BANNED, PlayerKickEvent.Cause.WHITELIST}) {
            assertTrue(DeathPenaltyRules.serverKick(k.name()), k.name());
        }
        assertTrue(DeathPenaltyRules.serverKick("KICK_COMMAND"));
        assertFalse(DeathPenaltyRules.serverKick(PlayerKickEvent.Cause.TIMEOUT.name()), "시간 초과 = 플레이어 쪽");
        assertFalse(DeathPenaltyRules.serverKick(PlayerKickEvent.Cause.FLYING_PLAYER.name()));
    }

    @Test
    void downingIsAlwaysADown() {
        Config c = Config.DEFAULT;
        // 막타를 맞고 다음 틱 처리 전에 끊음 — 이미 쓰러졌다
        assertEquals(APPLY, MinePvpRules.combatQuit(c, true, new MineQuit(true, true, false, true, -1, false, false, true)));
        assertEquals(APPLY, MinePvpRules.combatQuit(Config.OFF, false, new MineQuit(false, true, true, false, -1, false, false, true)),
                "페널티를 꺼도 승강장으로는 옮겨야 함");
    }

    @Test
    void switchesFollowTheDungeon() {
        assertEquals(NONE, MinePvpRules.combatQuit(Config.OFF, true, quit(0)), "death.penalty: false");
        assertEquals(NONE, MinePvpRules.combatQuit(new Config(true, true, 2, 3, Set.of(), 0), true, quit(0)), "combat_exit_seconds: 0");
        assertEquals(APPLY, MinePvpRules.combatQuit(Config.DEFAULT, false, quit(0)), "mine.pvp.penalty: false = 경험치만이지만 쓰러짐");
        Config noXp = new Config(false, true, 2, 3, Set.of());
        assertEquals(NONE, MinePvpRules.combatQuit(noXp, false, quit(0)), "penalty false · 경험치 끔 = 잃을 것 없음");
        assertEquals(NONE, MinePvpRules.combatQuit(null, true, quit(0)));
        assertEquals(NONE, MinePvpRules.combatQuit(Config.DEFAULT, true, null));
        // 미궁 판정과 같은 결과 (PvP 구역 · 광산 월드 · 광산 PvP 켜짐이면)
        for (long since : new long[] {-1, 0, 5_000, 9_999, 10_000}) {
            for (boolean casting : new boolean[] {false, true}) {
                var dungeon = new DeathPenaltyRules.Quit(true, true, false, true, false, since, casting, false);
                var mine = new MineQuit(true, true, true, true, since, casting, false, false);
                assertEquals(DeathPenaltyRules.combatQuit(Config.DEFAULT, dungeon), MinePvpRules.combatQuit(Config.DEFAULT, true, mine),
                        since + " " + casting);
            }
        }
    }

    // ── 글 ──────────────────────────────────────────────────────────────

    @Test
    void textsAreShortAndParse() {
        assertEquals("⚔ PvP 구역 · 다른 플레이어가 공격할 수 있습니다", Text.strip(MinePvpRules.TO_PVP));
        assertEquals("안전 구역 · 승강기 홀에서는 싸울 수 없습니다", Text.strip(MinePvpRules.TO_SAFE));
        assertEquals("싸우는 중에는 광산을 바로 나갈 수 없습니다. 승강기 홀로 가거나 10초 뒤에 다시 하세요.", Text.strip(MinePvpRules.TELEPORT_BLOCKED));
        assertEquals("싸우는 중이라 승강기가 5초 걸립니다. 움직이거나 맞으면 멈춥니다.",
                Text.strip(String.format(java.util.Locale.ROOT, MinePvpRules.LIFT_CAST, DeathPenaltyRules.seconds(5))));
        assertEquals("Bob 님이 광산에서 쓰러졌습니다.", Text.strip(MinePvpRules.partyDownText("Bob")));
        for (String s : new String[] {MinePvpRules.TO_PVP, MinePvpRules.TO_SAFE, MinePvpRules.DOWN_TITLE, MinePvpRules.LIFT_LORE,
                MinePvpRules.OFFICE_LORE, MinePvpRules.MAIN_MENU_LORE, MinePvpRules.TELEPORT_BLOCKED}) {
            assertNotNull(Text.mm(s));
        }
    }
}
