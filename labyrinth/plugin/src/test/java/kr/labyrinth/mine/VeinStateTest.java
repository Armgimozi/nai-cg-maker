package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * 함께 쓰는 광맥 (계약 §0-3): 모두에게 빈 광맥 · 다시 차는 시간은 사람 수와 관계 없이 정해진 초
 * (0.3.7 주인 결정 "광맥이 다시 생성되는 시간은 플레이어 유무와 관계 없이").
 */
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
        VeinState s = new VeinState();
        String k = VeinState.veinKey(1, 0);
        assertTrue(s.deplete(k, 480));
        assertFalse(s.deplete(k, 480), "이미 빈 광맥은 다시 비지 않음 (두 번째 사람도 못 캠)");
        assertTrue(s.isDepleted(k));
        assertEquals(480, s.remaining(k), 1e-9);
        assertEquals(List.of(), s.tick(479));
        assertTrue(s.isDepleted(k));
        assertEquals(List.of(k), s.tick(1));
        assertFalse(s.isDepleted(k));
        assertEquals(0, s.remaining(k));
        assertEquals(0, s.count());
    }

    @Test
    void fixedThreeMinutes() {
        // 0.3.7 기본: 층마다 3분. 179초 뒤에는 아직 빈 채, 1초 더 → 다시 참
        VeinState s = new VeinState();
        String k = VeinState.veinKey(2, 4);
        s.deplete(k, MineConfig.DEFAULT.regenSeconds(2));
        assertEquals(180, s.etaSeconds(k), 1e-9);
        assertEquals(List.of(), s.tick(179));
        assertTrue(s.isDepleted(k));
        assertEquals(1, s.etaSeconds(k), 1e-9);
        assertEquals(List.of(k), s.tick(1));
        assertFalse(s.isDepleted(k));
    }

    @Test
    void etaIsTheSameWhoeverIsThere() {
        // 남은 초는 광맥에만 달림 — 사람 수 인자가 없다. 광산에 아무도 없어도 같은 빠르기로 흐른다
        VeinState a = new VeinState();
        VeinState b = new VeinState();
        String k = VeinState.gemKey(5, 1);
        a.deplete(k, 1800);
        b.deplete(k, 1800);
        assertEquals(1800, a.etaSeconds(k), 1e-9);
        assertEquals(a.remaining(k), a.etaSeconds(k), 1e-9);
        a.tick(600);
        for (int i = 0; i < 600; i++) b.tick(1);
        assertEquals(1200, a.etaSeconds(k), 1e-9);
        assertEquals(a.etaSeconds(k), b.etaSeconds(k), 1e-6);
    }

    @Test
    void smallStepsRefillAtTheSameTime() {
        // 벽시계 틱이 0.3초씩 600번 와도 (180초) 한 번에 180초를 흘린 것과 같은 때 다시 찬다
        VeinState s = new VeinState();
        String k = VeinState.veinKey(1, 3);
        s.deplete(k, 180);
        int refilledAt = -1;
        for (int i = 1; i <= 700 && refilledAt < 0; i++) {
            if (!s.tick(0.3).isEmpty()) refilledAt = i;
        }
        assertEquals(600, refilledAt, "0.3초 × 600 = 180초");
    }

    @Test
    void groupShareWithFixedRegen() {
        // 한 층 광맥 60개, 3분 재생. 한 사람이 3초에 하나씩 캐면 혼자는 광맥이 남고, 여럿이면 서버 전체 공급(광맥 ÷ 재생)을 나눈다
        double regen = 180;
        int veins = 60;
        double soloRate = -1;
        for (int n = 1; n <= 4; n++) {
            VeinState s = new VeinState();
            int mined = 0;
            for (int t = 0; t < 3600; t++) {
                for (int p = 0; p < n; p++) {
                    if (t % 3 != 0) continue;
                    for (int i = 0; i < veins; i++) {
                        if (s.deplete(VeinState.veinKey(2, i), regen)) {
                            mined++;
                            break;
                        }
                    }
                }
                s.tick(1);
            }
            double perPlayer = mined / (double) n;
            if (soloRate < 0) soloRate = perPlayer;
            // 서버 전체 공급 = 광맥 수 ÷ 재생 (사람 수와 관계 없음): 1시간에 처음 60 + 60 × 20
            assertTrue(mined <= veins + veins * 3600 / regen + 1e-9, n + "명 합 " + mined);
            if (n == 1) assertEquals(1200, mined, "혼자 3초에 하나 = 1시간 1,200 (광맥이 남음)");
            else assertTrue(perPlayer <= soloRate + 1e-9, n + "명 한 사람 몫 " + perPlayer + " ≤ 혼자 " + soloRate);
        }
    }

    @Test
    void clearLevelAndRefill() {
        VeinState s = new VeinState();
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
        VeinState s = new VeinState();
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
        VeinState s = new VeinState();
        String k = VeinState.veinKey(1, 9);
        s.deplete(k, 0);
        assertEquals(1, s.remaining(k), 1e-9);
        assertEquals(List.of(), s.tick(0));
        assertEquals(List.of(), s.tick(Double.NaN));
        assertEquals(List.of(), s.tick(-5));
        assertEquals(List.of(k), s.tick(1));
    }
}
