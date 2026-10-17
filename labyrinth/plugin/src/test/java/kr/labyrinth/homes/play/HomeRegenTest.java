package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.homes.HomesConfig;
import kr.labyrinth.homes.PlotRole;
import org.junit.jupiter.api.Test;

/** 집 안 회복 (0.3.7): 내 집·초대받은 집 · 5초 안 맞음 · PvP 전투 아님 → 1초마다 최대의 5% (20초면 가득). */
class HomeRegenTest {

    static final long NOW = 1_000_000L;

    @Test
    void onlyBuildersRegen() {
        assertTrue(HomeRegen.eligible(PlotRole.OWNER, false, false, NOW, NOW - 5_000, 5));
        assertTrue(HomeRegen.eligible(PlotRole.TRUSTED, false, false, NOW, NOW - 5_000, 5));
        assertFalse(HomeRegen.eligible(PlotRole.GUEST, false, false, NOW, 0, 5), "손님은 회복 없음");
        assertFalse(HomeRegen.eligible(PlotRole.NONE, false, false, NOW, 0, 5), "집터 밖·남의 집");
        assertFalse(HomeRegen.eligible(null, false, false, NOW, 0, 5));
    }

    @Test
    void calmCombatAndDeath() {
        assertFalse(HomeRegen.eligible(PlotRole.OWNER, false, false, NOW, NOW - 4_999, 5), "5초 안에 맞았음");
        assertTrue(HomeRegen.eligible(PlotRole.OWNER, false, false, NOW, NOW - 5_000, 5));
        assertTrue(HomeRegen.eligible(PlotRole.OWNER, false, false, NOW, 0, 5), "맞은 적 없음");
        assertFalse(HomeRegen.eligible(PlotRole.OWNER, false, true, NOW, 0, 5), "PvP 전투 중");
        assertFalse(HomeRegen.eligible(PlotRole.OWNER, true, false, NOW, 0, 5), "죽음");
        assertTrue(HomeRegen.eligible(PlotRole.OWNER, false, false, NOW, NOW, 0), "calm 0 = 바로");
    }

    @Test
    void amountsClampToMissing() {
        assertEquals(10, HomeRegen.amount(100, 200, 0.05), 1e-9);
        assertEquals(10, HomeRegen.amount(190, 200, 0.05), 1e-9);
        assertEquals(5, HomeRegen.amount(195, 200, 0.05), 1e-9);
        assertEquals(0, HomeRegen.amount(200, 200, 0.05), 1e-9);
        assertEquals(0, HomeRegen.amount(50, 200, 0), 1e-9);
        assertEquals(0, HomeRegen.amount(0, 0, 0.05), 1e-9);
    }

    @Test
    void defaultsFillInTwentySeconds() {
        HomesConfig.Regen r = HomesConfig.DEFAULT.regen();
        assertEquals(0.05, r.hp(), 1e-9);
        assertEquals(0.05, r.mp(), 1e-9);
        assertEquals(5, r.calmSeconds());
        assertEquals(20, HomeRegen.secondsToFull(r.hp()));
        assertEquals(-1, HomeRegen.secondsToFull(0));
        // 빈 상태에서 20번 (20초) 이면 가득
        double hp = 0;
        for (int i = 0; i < 20; i++) hp += HomeRegen.amount(hp, 340, r.hp());
        assertEquals(340, hp, 1e-6);
    }
}
