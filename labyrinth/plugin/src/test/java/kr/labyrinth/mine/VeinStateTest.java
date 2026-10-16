package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/** 함께 쓰는 광맥 (계약 §0-3): 모두에게 빈 광맥 · 다시 차는 시간 ÷ min(광산 사람 수, cap). */
class VeinStateTest {

    @Test
    void keys() {
        assertEquals("L3:v12", VeinState.veinKey(3, 12));
        assertEquals("L6:g0", VeinState.gemKey(6, 0));
        assertEquals(3, VeinState.levelOf("L3:v12"));
        assertEquals(0, VeinState.levelOf("x"));
        assertEquals(0, VeinState.levelOf(null));
    }

    @Test
    void depleteIsSharedAndExpires() {
        VeinState s = new VeinState(4);
        String k = VeinState.veinKey(1, 0);
        assertTrue(s.deplete(k, 480));
        assertFalse(s.deplete(k, 480), "이미 빈 광맥은 다시 비지 않음 (두 번째 사람도 못 캠)");
        assertTrue(s.isDepleted(k));
        assertEquals(480, s.remaining(k), 1e-9);
        assertEquals(List.of(), s.tick(479, 1));
        assertTrue(s.isDepleted(k));
        assertEquals(List.of(k), s.tick(1, 1));
        assertFalse(s.isDepleted(k));
        assertEquals(0, s.remaining(k));
        assertEquals(0, s.count());
    }

    @Test
    void regrowScalesWithPlayersInMine() {
        double solo = 600;
        for (int players = 0; players <= 8; players++) {
            VeinState s = new VeinState(4);
            String k = VeinState.veinKey(4, 7);
            s.deplete(k, solo);
            int f = Math.max(1, Math.min(4, players));
            assertEquals(solo / f, s.etaSeconds(k, players), 1e-9, players + "명");
            int secs = 0;
            while (s.isDepleted(k) && secs < 10_000) {
                s.tick(1, players);
                secs++;
            }
            assertEquals((int) Math.ceil(solo / f), secs, players + "명이면 " + f + "배 빨리");
        }
    }

    @Test
    void perPlayerYieldInGroupStaysNearSolo() {
        // 한 층 광맥 60개를 사람 n 명이 쉬지 않고 캔다: 1분당 한 사람 몫은 사람 수와 거의 같다 (cap 까지)
        double solo = 540;
        double soloRate = -1;
        for (int n = 1; n <= 4; n++) {
            VeinState s = new VeinState(4);
            int mined = 0;
            int veins = 60;
            for (int t = 0; t < 3600; t++) {
                for (int p = 0; p < n; p++) {
                    // 한 사람이 3초에 하나 — 찬 광맥이 있으면 캔다
                    if (t % 3 != 0) continue;
                    for (int i = 0; i < veins; i++) {
                        if (s.deplete(VeinState.veinKey(2, i), solo)) {
                            mined++;
                            break;
                        }
                    }
                }
                s.tick(1, n);
            }
            double perPlayer = mined / (double) n;
            if (soloRate < 0) soloRate = perPlayer;
            assertTrue(Math.abs(perPlayer - soloRate) / soloRate < 0.12, n + "명 한 사람 몫 " + perPlayer + " vs 혼자 " + soloRate);
        }
    }

    @Test
    void capLimitsSpeedUp() {
        VeinState s = new VeinState(2);
        String k = VeinState.gemKey(5, 1);
        s.deplete(k, 1800);
        assertEquals(900, s.etaSeconds(k, 10), 1e-9);
        assertEquals(2, s.cap());
        assertEquals(1, new VeinState(0).cap());
    }

    @Test
    void clearLevelAndRefill() {
        VeinState s = new VeinState(4);
        s.deplete(VeinState.veinKey(1, 0), 100);
        s.deplete(VeinState.veinKey(1, 1), 100);
        s.deplete(VeinState.veinKey(2, 0), 100);
        assertEquals(2, s.count(1));
        assertEquals(2, s.clearLevel(1));
        assertEquals(0, s.count(1));
        assertEquals(1, s.count());
        assertTrue(s.refill(VeinState.veinKey(2, 0)));
        assertFalse(s.refill(VeinState.veinKey(2, 0)));
        assertEquals(0, s.count());
    }

    @Test
    void richIsTakenOnceAndClearedOnDeplete() {
        VeinState s = new VeinState(4);
        String k = VeinState.veinKey(3, 3);
        s.markRich(k);
        assertTrue(s.isRich(k));
        assertTrue(s.takeRich(k));
        assertFalse(s.takeRich(k));
        s.markRich(k);
        s.deplete(k, 60);
        assertFalse(s.isRich(k), "비면 풍부함도 사라짐");
        s.markRich(k);
        assertFalse(s.isRich(k), "빈 광맥은 풍부해지지 않음");
    }

    @Test
    void minimumOneSecondAndBadTicks() {
        VeinState s = new VeinState(4);
        String k = VeinState.veinKey(1, 9);
        s.deplete(k, 0);
        assertEquals(1, s.remaining(k), 1e-9);
        assertEquals(List.of(), s.tick(0, 4));
        assertEquals(List.of(), s.tick(Double.NaN, 4));
        assertEquals(List.of(k), s.tick(0.25, 4));
    }
}
