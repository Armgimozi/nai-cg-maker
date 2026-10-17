package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.core.NetherRule.Portal;
import org.bukkit.PortalType;
import org.bukkit.World.Environment;
import org.bukkit.event.player.PlayerTeleportEvent.TeleportCause;
import org.bukkit.event.world.PortalCreateEvent.CreateReason;
import org.junit.jupiter.api.Test;

/** 네더 막기 (0.3.7, 서버장 결정 "네더 막아"): 들어가기만 막고 나가기는 늘 · 엔드는 그대로 · wild.nether: true 면 아무것도 안 막음. */
class NetherRuleTest {

    static final Environment O = Environment.NORMAL, N = Environment.NETHER, E = Environment.THE_END, C = Environment.CUSTOM;

    @Test
    void selfCheckTableIsAllOk() {
        int[] r = NetherRule.selfCheck();
        assertEquals(r[1], r[0], "자가 진단 표");
        assertTrue(r[1] >= 27 + TeleportCause.values().length + PortalType.values().length);
    }

    @Test
    void goingIntoTheNetherIsBlocked() {
        assertTrue(NetherRule.blocksTravel(false, Portal.NETHER, O, N), "오버월드 → 네더");
        assertTrue(NetherRule.blocksTravel(false, Portal.NETHER, C, N), "미궁·광산 월드 → 네더");
        assertTrue(NetherRule.blocksTravel(false, Portal.NETHER, E, N), "엔드에 만든 네더 차원문");
        assertTrue(NetherRule.blocksTravel(false, Portal.NETHER, O, null), "갈 곳을 안 알려 줌 = 바닐라 = 네더");
    }

    @Test
    void leavingTheNetherIsAlwaysAllowed() {
        assertFalse(NetherRule.blocksTravel(false, Portal.NETHER, N, O), "네더 → 오버월드 (집으로)");
        assertFalse(NetherRule.blocksTravel(false, Portal.NETHER, N, null));
        assertFalse(NetherRule.blocksTravel(false, Portal.NETHER, N, C));
        assertFalse(NetherRule.blocksCreate(false, CreateReason.FIRE, N), "네더 쪽 틀에 불 = 돌아가는 문");
        assertFalse(NetherRule.blocksCreate(false, CreateReason.NETHER_PAIR, O), "오버월드에 생기는 돌아오는 짝");
        assertFalse(NetherRule.blocksCreate(false, CreateReason.NETHER_PAIR, C));
    }

    @Test
    void endTravelIsUntouched() {
        for (Environment from : new Environment[] {O, N, E, C}) {
            for (Environment to : new Environment[] {O, N, E, C, null}) {
                assertFalse(NetherRule.blocksTravel(false, Portal.END, from, to), from + " → " + to + " 엔드 차원문");
                assertFalse(NetherRule.blocksTravel(false, Portal.OTHER, from, to), "명령·플러그인 순간이동은 규칙 밖");
            }
        }
        assertFalse(NetherRule.blocksCreate(false, CreateReason.END_PLATFORM, E));
        assertFalse(NetherRule.blocksCreate(false, CreateReason.END_PLATFORM, O));
        assertEquals(Portal.END, NetherRule.of(TeleportCause.END_PORTAL));
        assertEquals(Portal.END, NetherRule.of(TeleportCause.END_GATEWAY));
        assertEquals(Portal.END, NetherRule.of(PortalType.ENDER));
        assertEquals(Portal.END, NetherRule.of(PortalType.END_GATEWAY));
    }

    @Test
    void portalCreation() {
        assertTrue(NetherRule.blocksCreate(false, CreateReason.FIRE, O), "오버월드 흑요석 틀에 불");
        assertTrue(NetherRule.blocksCreate(false, CreateReason.FIRE, C));
        assertTrue(NetherRule.blocksCreate(false, CreateReason.FIRE, E));
        assertTrue(NetherRule.blocksCreate(false, CreateReason.NETHER_PAIR, N), "네더 안에 새 짝 = 들어가는 중");
        assertFalse(NetherRule.blocksCreate(false, null, O));
        assertFalse(NetherRule.blocksCreate(false, CreateReason.FIRE, null));
    }

    @Test
    void openSwitchAllowsEverything() {
        for (Environment from : new Environment[] {O, N, E, C, null}) {
            for (Environment to : new Environment[] {O, N, E, C, null}) {
                for (Portal p : Portal.values()) assertFalse(NetherRule.blocksTravel(true, p, from, to));
            }
            for (CreateReason r : CreateReason.values()) assertFalse(NetherRule.blocksCreate(true, r, from));
        }
    }

    @Test
    void unknownSourceIsNotBlocked() {
        assertFalse(NetherRule.blocksTravel(false, Portal.NETHER, null, N), "어디서 오는지 모르면 막지 않음");
        assertFalse(NetherRule.blocksTravel(false, Portal.NETHER, O, O), "다른 플러그인이 오버월드로 돌린 문");
    }

    @Test
    void portalKinds() {
        assertEquals(Portal.NETHER, NetherRule.of(TeleportCause.NETHER_PORTAL));
        assertEquals(Portal.NETHER, NetherRule.of(PortalType.NETHER));
        assertEquals(Portal.OTHER, NetherRule.of(TeleportCause.PLUGIN));
        assertEquals(Portal.OTHER, NetherRule.of(TeleportCause.COMMAND));
        assertEquals(Portal.OTHER, NetherRule.of(PortalType.CUSTOM));
        assertEquals(Portal.OTHER, NetherRule.of((TeleportCause) null));
        assertEquals(Portal.OTHER, NetherRule.of((PortalType) null));
        assertArrayEquals(new Portal[] {Portal.NETHER, Portal.END, Portal.OTHER}, Portal.values());
    }
}
