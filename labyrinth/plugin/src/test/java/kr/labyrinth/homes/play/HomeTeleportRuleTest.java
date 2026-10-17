package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import kr.labyrinth.homes.HomesConfig.Toggle;
import kr.labyrinth.homes.HomesLayout;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotRole;
import kr.labyrinth.mine.MineGameModeRule;
import org.bukkit.GameMode;
import org.junit.jupiter.api.Test;

/**
 * 집 가기 · 방문 (0.3.7, review R11 · R12): auto = village.teleport_command 를 따름 (관리자는 늘) · 미궁·PvP 전투 중 안 됨 ·
 * 광산(어드벤처) → 집 가기 → 서바이벌 · 도착 칸 = 대문 바깥 거리 칸, 대문을 봄.
 */
class HomeTeleportRuleTest {

    @Test
    void autoFollowsVillageTeleport() {
        assertNull(HomeTravel.denyGo(true, Toggle.AUTO, true, false, false, false, true));
        assertNotNull(HomeTravel.denyGo(true, Toggle.AUTO, false, false, false, false, true), "마을 텔레포트를 끈 서버는 집 가기도 꺼짐 (R11)");
        assertNull(HomeTravel.denyGo(true, Toggle.AUTO, false, true, false, false, true), "관리자는 늘 됨");
        assertNull(HomeTravel.denyGo(true, Toggle.ON, false, false, false, false, true));
        assertNotNull(HomeTravel.denyGo(true, Toggle.OFF, true, false, false, false, true));
        assertNotNull(HomeTravel.denyGo(true, null, true, false, false, false, true));
    }

    @Test
    void goNeedsHomeAndCalm() {
        assertNotNull(HomeTravel.denyGo(true, Toggle.ON, true, false, false, false, false), "집이 없음");
        assertNotNull(HomeTravel.denyGo(true, Toggle.ON, true, false, true, false, true), "미궁 안");
        assertNotNull(HomeTravel.denyGo(true, Toggle.ON, true, false, false, true, true), "PvP 전투 중");
        assertNotNull(HomeTravel.denyGo(true, Toggle.ON, true, true, true, false, true), "관리자도 미궁 안에서는 안 됨");
        assertNotNull(HomeTravel.denyGo(false, Toggle.ON, true, false, false, false, true), "집 기능 꺼짐");
    }

    @Test
    void visitFollowsVisitToggleAndGuests() {
        assertNull(HomeTravel.denyVisit(true, Toggle.AUTO, true, false, false, false, true, PlotRole.GUEST));
        assertNull(HomeTravel.denyVisit(true, Toggle.AUTO, true, false, false, false, true, PlotRole.TRUSTED));
        assertNotNull(HomeTravel.denyVisit(true, Toggle.AUTO, true, false, false, false, true, PlotRole.NONE), "손님을 받지 않는 집");
        assertNull(HomeTravel.denyVisit(true, Toggle.AUTO, true, true, false, false, true, PlotRole.NONE), "관리자");
        assertNotNull(HomeTravel.denyVisit(true, Toggle.AUTO, false, false, false, false, true, PlotRole.GUEST), "auto + 마을 텔레포트 끔 (R11)");
        assertNotNull(HomeTravel.denyVisit(true, Toggle.OFF, true, false, false, false, true, PlotRole.GUEST));
        assertNotNull(HomeTravel.denyVisit(true, Toggle.ON, true, false, false, false, false, PlotRole.NONE), "그 사람은 집이 없음");
        assertNotNull(HomeTravel.denyVisit(true, Toggle.ON, true, false, true, false, true, PlotRole.GUEST), "미궁 안");
        assertNotNull(HomeTravel.denyVisit(true, Toggle.ON, true, false, false, true, true, PlotRole.GUEST), "PvP 전투 중");
    }

    @Test
    void fromTheMineBackToSurvival() {
        // R12: 광산(어드벤처) → 집 가기 → 월드 이동 → 광산 규칙이 서바이벌로 (집 가기도 같은 규칙을 한 번 더 씀)
        assertEquals(GameMode.SURVIVAL, MineGameModeRule.target(GameMode.ADVENTURE, false));
        assertEquals(GameMode.SURVIVAL, HomeTravel.modeAfter(GameMode.ADVENTURE, false));
        assertNull(HomeTravel.modeAfter(GameMode.SURVIVAL, false));
        assertNull(HomeTravel.modeAfter(GameMode.CREATIVE, false), "관리자 크리에이티브는 그대로");
    }

    @Test
    void destinationIsTheStreetCellFacingTheGate() {
        List<PlotGeom> geoms = HomesLayout.geoms(6, 24);
        for (PlotGeom g : geoms) {
            HomesLayout.Spec s = HomesLayout.plot(Integer.parseInt(g.id()));
            double[] d = HomeTravel.destination(g, (x, z) -> 70);
            assertEquals(s.homeX(), d[0], 1e-9, g.id());
            assertEquals(70, d[1], 1e-9);
            assertEquals(s.homeZ(), d[2], 1e-9, g.id());
            assertEquals(s.homeYaw(), (float) d[3], 1e-6, g.id());
            int[] out = s.gateOutside();
            assertEquals(out[0] + 0.5, d[0], 1e-9);
            assertEquals(out[1] + 0.5, d[2], 1e-9);
            assertTrue(HomesLayout.isPublic(out[0], out[1]), "대문 바깥 칸은 거리: " + g.id());
        }
        // 구역 기록에 집 가기 칸이 있으면 그대로
        PlotGeom known = new PlotGeom("3", 3, -129, 48, -116, 61, 68, 62, 92, "S", -123, 62, -121, 70, 62, -122.5, 69.0, 63.5, 180f, false);
        double[] d = HomeTravel.destination(known, (x, z) -> 0);
        assertEquals(69.0, d[1], 1e-9);
        assertEquals(-122.5, d[0], 1e-9);
        // 동·서 대문 (관리자가 here 자리로 돌려 지은 구역)
        PlotGeom east = new PlotGeom("1", 1, 0, 0, 13, 13, 64, 58, 88, "E", 14, 6, 14, 66, 8, 0, Double.NaN, 0, 0f, false);
        double[] e = HomeTravel.destination(east, (x, z) -> 65);
        assertEquals(15.5, e[0], 1e-9);
        assertEquals(6.5, e[2], 1e-9);
        assertEquals(90f, (float) e[3], 1e-6, "서쪽(대문)을 봄");
    }
}
