package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Set;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import kr.labyrinth.core.DeathPenaltyRules.GoldLoss;
import kr.labyrinth.core.DeathPenaltyRules.Plan;
import kr.labyrinth.core.DeathPenaltyRules.Quit;
import kr.labyrinth.core.DeathPenaltyRules.QuitVerdict;
import kr.labyrinth.core.DeathPenaltyRules.Where;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.event.player.PlayerKickEvent;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.2 주인 결정: 공략 중 싸우는 중(10초 안에 맞음 · 싸우는 중에 시작한 퇴장/귀환 시전 중)에 접속을 끊으면 쓰러진 것으로 친다.
 * 순수 판정 {@link DeathPenaltyRules#combatQuit} — 형편/스위치 → APPLY · NONE.
 */
class DeathPenaltyQuitTest {

    private static final QuitVerdict APPLY = QuitVerdict.APPLY;
    private static final QuitVerdict NONE = QuitVerdict.NONE;

    /** 기본 형편: 공략 중 · 미궁 월드 · 일반 입장 · 살아 있음 · 끝나는 중 아님 · 시전 없음 · 플레이어가 끊음. */
    private static Quit quit(long sinceHurtMs) {
        return new Quit(true, true, false, true, false, sinceHurtMs, false, false);
    }

    private static Config yaml(String text) throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        return Config.read(y);
    }

    // ── 싸우는 중인가 ─────────────────────────────────────────────────────

    @Test
    void hitWithinTenSecondsThenQuitCountsAsDown() {
        Config c = Config.DEFAULT;
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(c, quit(0)), "막 맞고 끊음");
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(c, quit(3_200)));
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(c, quit(9_999)), "10초 바로 앞");
    }

    @Test
    void notInCombatStaysInTheRun() {
        Config c = Config.DEFAULT;
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, quit(10_000)), "10초 지남");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, quit(15_000)), "15초 안 맞음 (라이브 시험 2)");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, quit(-1)), "맞은 적 없음");
    }

    @Test
    void quitDuringCombatCastCountsEvenAfterTenSeconds() {
        Config c = Config.DEFAULT;
        // 9.9초에 /미궁 퇴장 → 5초 시전 → 14초에 끊음: 마지막 피해는 10초를 넘었지만 시전 중이라 싸우는 중
        Quit casting = new Quit(true, true, false, true, false, 14_000, true, false);
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(c, casting));
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(c, new Quit(true, true, false, true, false, -1, true, false)));
    }

    // ── 두 번 받지 않음 · 공략 밖 ─────────────────────────────────────────

    @Test
    void neverTwiceAndNeverOutsideTheRun() {
        Config c = Config.DEFAULT;
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, new Quit(true, true, false, false, false, 0, false, false)),
                "이미 쓰러져 관전 중 (DEAD)");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, new Quit(true, true, false, true, true, 0, false, false)),
                "공략이 끝나는 중 (전멸·정복·관리자 종료)");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, new Quit(true, true, false, true, true, 0, true, false)),
                "끝나는 중이면 시전 중이어도");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, new Quit(false, true, false, true, false, 0, false, false)),
                "공략 참가자 아님 (떠남)");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, new Quit(true, false, false, true, false, 0, false, false)),
                "미궁 월드 밖 (입장 준비 중 마을 · 야생 · 광산)");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, new Quit(true, true, true, true, false, 0, true, false)),
                "관리자 시험 입장 (/labadmin tpfloor)");
    }

    @Test
    void serverSideDisconnectsNeverPenalise() {
        Config c = Config.DEFAULT;
        assertEquals(NONE, DeathPenaltyRules.combatQuit(c, new Quit(true, true, false, true, false, 0, true, true)),
                "서버 종료 · 재시작 · 플러그인 끄기 · 관리자 /kick");
        assertTrue(DeathPenaltyRules.serverKick("RESTART_COMMAND"), "/restart 는 플러그인을 끄기 전에 모두 내보낸다");
        assertTrue(DeathPenaltyRules.serverKick("KICKED"), "관리자 /kick (Paper KickCommand 가 쓰는 원인)");
        for (String player : List.of("TIMEOUT", "SPAM", "DUPLICATE_LOGIN", "FLYING_PLAYER", "IDLING", "PLUGIN", "UNKNOWN")) {
            assertFalse(DeathPenaltyRules.serverKick(player), player + " 는 보통 끊김과 같다");
        }
        assertFalse(DeathPenaltyRules.serverKick(null));
        // 이름이 Paper API 의 원인 이름과 같아야 한다 (바뀌면 여기서 걸림)
        assertTrue(DeathPenaltyRules.serverKick(PlayerKickEvent.Cause.RESTART_COMMAND.name()));
        assertTrue(DeathPenaltyRules.serverKick(PlayerKickEvent.Cause.KICKED.name()), "KICK_COMMAND 는 KICKED 의 별칭");
        // 관리자가 내보냄은 /kick 과 같게: /ban (BanPlayerCommands) · /ban-ip (BanIpCommands) · 명단 밖 (kickUnlistedPlayers)
        for (PlayerKickEvent.Cause admin : List.of(PlayerKickEvent.Cause.BANNED, PlayerKickEvent.Cause.IP_BANNED,
                PlayerKickEvent.Cause.WHITELIST)) {
            assertTrue(DeathPenaltyRules.serverKick(admin.name()), admin + " = 관리자가 내보냄");
        }
        // 플레이어 쪽 (튕김 · 도배 · 이상한 움직임 · 같은 계정 · 팩 거절 · 다른 플러그인) 은 모두 보통 끊김
        Set<PlayerKickEvent.Cause> server = Set.copyOf(List.of(PlayerKickEvent.Cause.RESTART_COMMAND, PlayerKickEvent.Cause.KICKED,
                PlayerKickEvent.Cause.KICK_COMMAND, PlayerKickEvent.Cause.BANNED, PlayerKickEvent.Cause.IP_BANNED,
                PlayerKickEvent.Cause.WHITELIST)); // KICK_COMMAND 는 KICKED 와 같은 값일 수 있음
        for (PlayerKickEvent.Cause cause : PlayerKickEvent.Cause.values()) {
            assertEquals(server.contains(cause), DeathPenaltyRules.serverKick(cause.name()), cause.name());
        }
    }

    // ── 스위치 ────────────────────────────────────────────────────────────

    @Test
    void switchesOff() throws Exception {
        assertEquals(NONE, DeathPenaltyRules.combatQuit(Config.OFF, quit(0)), "penalty: false (라이브 시험 6)");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(yaml("death:\n  penalty: false\n"), quit(0)));
        assertEquals(NONE, DeathPenaltyRules.combatQuit(yaml("death:\n  penalty:\n    combat_exit_seconds: 0\n"), quit(0)),
                "combat_exit_seconds: 0 = 예전처럼 (퇴장 시전도, 끊김 판정도 없음)");
        Config nothing = new Config(false, false, 2, 3, Set.of(), 5, GoldLoss.OFF);
        assertEquals(NONE, DeathPenaltyRules.combatQuit(nothing, quit(0)), "잃을 것이 모두 꺼짐 — 쓰러진 것으로 칠 까닭이 없음");
        assertEquals(NONE, DeathPenaltyRules.combatQuit(null, quit(0)));
        assertEquals(NONE, DeathPenaltyRules.combatQuit(Config.DEFAULT, null));
    }

    @Test
    void eachSwitchDecidesItsOwnPart() throws Exception {
        // 물건만 끔: 쓰러진 것으로 치되 골드·경험치만 (같은 plan 을 쓰는 DeathPenalty.onCombatQuit)
        Config noItems = yaml("death:\n  penalty:\n    dungeon_item_loss: false\n");
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(noItems, quit(0)));
        Plan p = DeathPenaltyRules.plan(noItems, Where.DUNGEON_RUN, false);
        assertFalse(p.destroySlots());
        assertTrue(p.loseGold());
        assertTrue(p.resetXp());
        // 골드만 끔
        Config noGold = yaml("death:\n  penalty:\n    gold_loss: false\n");
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(noGold, quit(0)));
        p = DeathPenaltyRules.plan(noGold, Where.DUNGEON_RUN, false);
        assertTrue(p.destroySlots());
        assertFalse(p.loseGold());
        // 골드만 켬 (경험치·물건 끔)
        Config goldOnly = new Config(false, false, 2, 3, Set.of(), 5, GoldLoss.DEFAULT);
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(goldOnly, quit(0)));
        // 0.3.6.1 config (gold_loss · 새 키 없음) 도 그대로 켜짐
        Config old = yaml("death:\n  penalty:\n    xp_progress_reset: true\n    combat_exit_seconds: 5\n"
                + "    dungeon_item_loss:\n      enabled: true\n      slots_min: 2\n      slots_max: 3\n");
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(old, quit(0)));
        assertEquals(APPLY, DeathPenaltyRules.combatQuit(yaml("other: 1\n"), quit(0)), "death 블록이 없어도 기본값");
    }

    /** 끊김 판정은 퇴장 시전과 같은 조건 — 시전이 걸릴 때(전투 중에 /미궁 퇴장) 끊으면 쓰러짐, 바로 나갈 수 있을 때 끊으면 그대로. */
    @Test
    void sameConditionsAsTheExitCast() {
        List<Config> configs = List.of(Config.DEFAULT, Config.OFF, new Config(true, false, 2, 3, Set.of(), 5, GoldLoss.OFF),
                new Config(false, true, 2, 3, Set.of(), 0, GoldLoss.DEFAULT), new Config(false, false, 0, 0, Set.of(), 2.5, GoldLoss.DEFAULT),
                new Config(false, false, 2, 3, Set.of(), 5, GoldLoss.OFF));
        long[] times = {-1, 0, 1, 5_000, 9_999, 10_000, 10_001, 60_000};
        int checked = 0;
        for (Config c : configs) {
            for (boolean admin : new boolean[] {false, true}) {
                for (boolean alive : new boolean[] {false, true}) {
                    for (long t : times) {
                        boolean cast = DeathPenaltyRules.exitCastSeconds(c, admin, alive, t) > 0;
                        QuitVerdict v = DeathPenaltyRules.combatQuit(c, new Quit(true, true, admin, alive, false, t, false, false));
                        assertEquals(cast ? APPLY : NONE, v, "config " + c + " admin " + admin + " alive " + alive + " t " + t);
                        checked++;
                    }
                }
            }
        }
        assertEquals(configs.size() * 2 * 2 * times.length, checked);
    }

    // ── 안내 ──────────────────────────────────────────────────────────────

    @Test
    void notices() {
        assertEquals("싸우는 중에 접속을 끊어 쓰러진 것으로 쳤습니다.", Text.plain(Text.mm(DeathPenaltyRules.QUIT_DOWN_TEXT)));
        assertEquals("Vic 님이 싸우는 중에 접속을 끊어 쓰러졌습니다.", Text.plain(Text.mm(DeathPenaltyRules.quitDownPartyText("Vic"))));
        // 콘솔 줄 = 쓰러짐과 같은 꼴, 곳만 "미궁 · 접속 끊김" (DeathPenalty.onCombatQuit), 바꾸기 전 값
        assertEquals("[죽음 페널티] Vic (미궁 · 접속 끊김) 잃은 물건 iron_ingot×13 (철 주괴) · 골드 -520 (보유 10000 → 9480) · 경험치 -30",
                DeathPenalty.logLine("Vic", "미궁 · 접속 끊김", List.of("iron_ingot×13 (철 주괴)"), 30, 520, 10_000));
    }
}
