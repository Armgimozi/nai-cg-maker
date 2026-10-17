package kr.labyrinth.homes.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.HomesLayout;
import kr.labyrinth.homes.PlotGeom;
import org.junit.jupiter.api.Test;

/** 받기 규칙 (plan §6 · R13·R18): 한 사람 한 집 (convert 포함) · 스스로 비운 뒤 24시간 · 아무 데나 · 이름 · 초대. */
class ClaimRulesTest {

    private static final List<PlotGeom> PLOTS = HomesLayout.geoms(6, 24);

    @Test
    void reclaimCooldownIs24h() {
        int min = HomesConfig.DEFAULT.reclaimCooldownMinutes();
        assertEquals(1440, min);
        long t = 1_000_000_000L;
        assertEquals(24 * 3_600_000L, ClaimRules.cooldownLeft(t, t, min));
        assertEquals(60_000L, ClaimRules.cooldownLeft(t, t + 24 * 3_600_000L - 60_000L, min));
        assertEquals(0, ClaimRules.cooldownLeft(t, t + 24 * 3_600_000L, min));
        assertEquals(0, ClaimRules.cooldownLeft(0, t, min), "비운 적 없음");
        assertEquals(0, ClaimRules.cooldownLeft(t, t, 0), "0분 = 바로");
    }

    @Test
    void durationText() {
        assertEquals("1분", ClaimRules.duration(1));
        assertEquals("2분", ClaimRules.duration(120_000));
        assertEquals("1시간 30분", ClaimRules.duration(5_400_000));
        assertEquals("24시간", ClaimRules.duration(86_400_000));
    }

    @Test
    void claimChecks() {
        PlotGeom p3 = PLOTS.get(2);
        assertNull(ClaimRules.checkClaim(true, false, false, 0, p3, false, false));
        assertNotNull(ClaimRules.checkClaim(false, false, false, 0, p3, false, false), "집 구역 없음");
        assertNotNull(ClaimRules.checkClaim(true, true, false, 0, p3, false, false), "미궁 안");
        String one = ClaimRules.checkClaim(true, false, true, 0, p3, false, false);
        assertTrue(one.contains("한 집"), "한 사람 한 집 (convert 집도 셈 — 부르는 쪽이 homeOf 로)");
        String cd = ClaimRules.checkClaim(true, false, false, 3_600_000, p3, false, false);
        assertTrue(cd.contains("1시간"), cd);
        assertNotNull(ClaimRules.checkClaim(true, false, false, 0, null, false, false), "빈 집 없음");
        assertTrue(ClaimRules.checkClaim(true, false, false, 0, p3, true, false).startsWith("3번지는"));
        assertTrue(ClaimRules.checkClaim(true, false, false, 0, p3, false, true).startsWith("3번지를"));
        PlotGeom c1 = new PlotStore.Custom("c1", 1, 0, 0, 5, 5, 0, 10, 2, Double.NaN, Double.NaN, Double.NaN, 0f).geom();
        assertNotNull(ClaimRules.checkClaim(true, false, false, 0, c1, false, false), "convert 집터는 관리자만 줌");
    }

    @Test
    void pickAnyChoosesFreeDistrictPlot() {
        List<PlotGeom> all = new ArrayList<>(PLOTS);
        all.add(new PlotStore.Custom("c1", 1, 0, 0, 5, 5, 0, 10, 2, Double.NaN, Double.NaN, Double.NaN, 0f).geom());
        Set<String> taken = new HashSet<>(List.of("1", "2", "3", "4", "5", "6", "7", "8", "9"));
        Random r = new Random(1);
        for (int i = 0; i < 20; i++) {
            PlotGeom p = ClaimRules.pickAny(all, g -> !taken.contains(g.id()), r);
            assertEquals("10", p.id(), "남은 구역 집 하나 (c1 은 아님)");
        }
        taken.add("10");
        assertNull(ClaimRules.pickAny(all, g -> !taken.contains(g.id()), r), "10채가 다 차면 없음 (11번째부터 convert)");
    }

    @Test
    void names() {
        assertEquals("하린네", ClaimRules.cleanName("  하린네  "));
        assertEquals("b집/b", ClaimRules.cleanName("<b>집</b>"), "꺾쇠만 뺌 (보일 때 escape)");
        assertEquals("가나다라마바사아자차카타파하가나", ClaimRules.cleanName("가나다라마바사아자차카타파하가나다라"), "16자");
        assertEquals("a b", ClaimRules.cleanName("a\n\tb"));
        assertEquals("", ClaimRules.cleanName(null));
        assertEquals("하린의 집", ClaimRules.displayName("", "하린"));
        assertEquals("작은 집", ClaimRules.displayName("작은 집", "하린"));
        assertEquals(5 * 60_000L, ClaimRules.renameLeft(1000, 1000, 5));
    }

    @Test
    void invites() {
        assertNull(ClaimRules.checkInvite(false, false, 0, 8));
        assertNotNull(ClaimRules.checkInvite(true, false, 0, 8));
        assertNotNull(ClaimRules.checkInvite(false, true, 0, 8));
        assertTrue(ClaimRules.checkInvite(false, false, 8, 8).contains("8명"));
    }

    @Test
    void particles() {
        PlotGeom p3 = PLOTS.get(2);
        assertEquals("3번지는", ClaimRules.topic(p3));
        assertEquals("3번지를", ClaimRules.object(p3));
        PlotGeom c1 = new PlotStore.Custom("c1", 1, 0, 0, 5, 5, 0, 10, 2, Double.NaN, Double.NaN, Double.NaN, 0f).geom();
        assertEquals("c1 집터는", ClaimRules.topic(c1));
    }
}
