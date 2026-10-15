package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.util.UUID;
import org.junit.jupiter.api.Test;

/** 게이지 없는 공격 시계 (combat_spec §2.1~2.3, §12). */
class AttackTimingTest {

    private static final long TOL = 50, BUF = 350;
    private static final UUID A = UUID.randomUUID(), B = UUID.randomUUID();

    @Test
    void passesOnlyOnInterval() {
        AttackTiming t = new AttackTiming();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(1000, 670, TOL, BUF, A, "w"));
        assertEquals(1670, t.nextReady());
        assertEquals(AttackTiming.Result.EARLY, t.click(1100, 670, TOL, BUF, A, "w"), "570ms 남음 → 너무 이름");
        assertFalse(t.hasBuffer());
        assertEquals(AttackTiming.Result.ACCEPT, t.click(1700, 670, TOL, BUF, A, "w"), "늦게 누르면 지금부터 간격");
        assertEquals(2370, t.nextReady());
    }

    @Test
    void clickWithinToleranceIsAcceptedWithoutGainingSpeed() {
        AttackTiming t = new AttackTiming();
        t.click(0, 450, TOL, BUF, A, "w");
        assertEquals(AttackTiming.Result.ACCEPT, t.click(410, 450, TOL, BUF, A, "w"), "40ms 이름 → 통과");
        assertEquals(900, t.nextReady(), "다음 시각은 원래 시각 + 간격 (빨라지지 않음)");
    }

    @Test
    void earlyClickInsideBufferIsRememberedOnceAndFiredAtReady() {
        AttackTiming t = new AttackTiming();
        t.click(0, 1000, TOL, BUF, A, "w");
        assertEquals(AttackTiming.Result.EARLY, t.click(500, 1000, TOL, BUF, A, "w"), "500ms 남음 > 기억창 350ms");
        assertEquals(AttackTiming.Result.BUFFER, t.click(700, 1000, TOL, BUF, A, "w"));
        assertEquals(AttackTiming.Result.BUFFER, t.click(800, 1000, TOL, BUF, B, "w"), "새 클릭은 대상만 바꿈");
        assertTrue(t.hasBuffer());
        assertEquals(B, t.bufferedTarget());
        assertEquals(800, t.bufferedAt());
        assertFalse(t.bufferReady(900));
        assertTrue(t.bufferReady(1000));
        t.fireBuffered(1000, 1000, TOL);
        assertFalse(t.hasBuffer());
        assertEquals(2000, t.nextReady(), "넣은 뒤 다음 시각 = 그 시각 + 간격");
    }

    @Test
    void bufferWindowShrinksToIntervalForFastWeapons() {
        AttackTiming t = new AttackTiming();
        t.click(0, 300, TOL, BUF, A, "w");
        assertEquals(AttackTiming.Result.BUFFER, t.click(10, 300, TOL, BUF, A, "w"), "290ms 남음 ≤ 간격 300ms");
        AttackTiming off = new AttackTiming();
        off.click(0, 1000, TOL, 0, A, "w");
        assertEquals(AttackTiming.Result.EARLY, off.click(900, 1000, TOL, 0, A, "w"), "기억창 0 = 끔");
    }

    @Test
    void bufferExpiresAndCanBeDropped() {
        AttackTiming t = new AttackTiming();
        t.click(0, 1000, TOL, BUF, A, "w");
        t.click(700, 1000, TOL, BUF, A, "w");
        assertFalse(t.bufferExpired(1200, 600));
        assertTrue(t.bufferExpired(1301, 600));
        assertEquals("w", t.bufferedWeapon());
        t.clearBuffer();
        assertFalse(t.hasBuffer());
        assertFalse(t.bufferReady(5000));
    }

    @Test
    void spammingEveryTickDoesNotLeakSpeed() {
        // 매 틱(50ms) 누르는 연타: 100번 맞는 데 걸린 시간 = 100 × 간격 (±1틱)
        for (long interval : new long[] {450, 670, 1000, 1150, 250}) {
            AttackTiming t = new AttackTiming();
            int hits = 0;
            long first = -1, last = -1;
            for (long now = 0; hits < 101; now += 50) {
                if (t.bufferReady(now)) {
                    t.fireBuffered(now, interval, TOL);
                    hits++;
                    last = now;
                    continue;
                }
                if (t.click(now, interval, TOL, BUF, A, "w") == AttackTiming.Result.ACCEPT) {
                    hits++;
                    if (first < 0) first = now;
                    last = now;
                }
            }
            assertEquals(100 * interval, last - first, 50, "간격 " + interval);
        }
    }

    @Test
    void slowClickerAlsoGetsFullHitsEveryInterval() {
        // 박자에 맞춰 누르는 사람 (끝나기 100ms 전) — 기억했다가 넣으므로 손해 없음
        AttackTiming t = new AttackTiming();
        long interval = 1000;
        t.click(0, interval, TOL, BUF, A, "w");
        int hits = 1;
        for (long beat = 900; beat < 10_000; beat += 1000) {
            assertEquals(AttackTiming.Result.BUFFER, t.click(beat, interval, TOL, BUF, A, "w"));
            long ready = t.nextReady();
            assertTrue(t.bufferReady(ready));
            t.fireBuffered(ready, interval, TOL);
            hits++;
        }
        assertEquals(11, hits);
        assertEquals(11_000, t.nextReady());
    }

    @Test
    void swappingWeaponWaitsHalfTheNewInterval() {
        AttackTiming t = new AttackTiming();
        t.click(0, 450, TOL, BUF, A, "dagger");
        t.click(400, 450, TOL, BUF, A, "dagger"); // 기억
        t.swap(460, 1000, 0.5);
        assertFalse(t.hasBuffer(), "바꾸면 기억한 클릭을 지움");
        assertEquals(960, t.nextReady(), "max(450, 460 + 500)");
        assertEquals(AttackTiming.Result.EARLY, t.click(500, 1000, TOL, BUF, A, "sword"));
        AttackTiming late = new AttackTiming();
        late.click(0, 2000, TOL, BUF, A, "x");
        late.swap(100, 400, 0.5);
        assertEquals(2000, late.nextReady(), "이미 더 늦으면 그대로");
    }

    @Test
    void whooshIsRateLimited() {
        AttackTiming t = new AttackTiming();
        assertTrue(t.whoosh(1000, 150));
        assertFalse(t.whoosh(1100, 150));
        assertTrue(t.whoosh(1150, 150));
    }

    @Test
    void distanceToHitbox() {
        var box = new org.bukkit.util.BoundingBox(0, 0, 0, 1, 2, 1);
        assertEquals(0, AttackClock.distanceToBox(new org.bukkit.util.Vector(0.5, 1, 0.5), box), 1e-9);
        assertEquals(2, AttackClock.distanceToBox(new org.bukkit.util.Vector(3, 1, 0.5), box), 1e-9);
        assertEquals(Math.sqrt(2), AttackClock.distanceToBox(new org.bukkit.util.Vector(2, 3, 0.5), box), 1e-9);
    }
}
