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
    void swappingToABowCountsTheDrawInsideTheSwapWait() {
        // 활의 첫 공격(화살)은 당김을 세기 시작한 뒤 끝까지 당겨야 나간다 — 바꿈 대기(새 주기 × 0.5)에서 당김을 뺀다 (0.3.6.1)
        AttackTiming t = new AttackTiming();
        t.click(0, 450, TOL, BUF, A, "dagger");
        t.swap(100, CYCLE, 0.5, FULL);
        assertEquals(450, t.nextReady(), "max(450, 100 + 575 − 1000) — 단도 간격이 끝나면 당김을 센다");
        AttackTiming idle = new AttackTiming();
        idle.swap(5000, CYCLE, 0.5, FULL);
        assertEquals(FULL, idle.bowDrawnMs(5000 + FULL, FULL, 0), "쉬다가 활로 바꾸면 바로 당겨 쏜다");
    }

    // ── 활: 쏘기와 근접이 시계 하나 — 공격마다 제 시간 (0.3.6.1) ──────────────

    private static final long FULL = 1000, NOCK = 150, CYCLE = FULL + NOCK;

    @Test
    void shotLeavesOnlyTheNockBeforeTheNextAction() {
        AttackTiming t = new AttackTiming();
        assertEquals(FULL, t.bowDrawnMs(1000, 1000, 0), "처음엔 바닐라가 잰 당긴 시간 그대로");
        t.shot(1000, 1000, FULL, TOL, NOCK);
        assertEquals(1000 + NOCK, t.nextReady(), "쏜 뒤 다시 메기기 0.15초");
        assertEquals(AttackTiming.Result.BUFFER, t.click(1050, CYCLE, TOL, BUF, A, "bow"), "0.1초 남음 → 기억했다가 넣음");
        assertEquals(0, t.bowDrawnMs(1100, 100, 0), "다음 당김도 다시 메기기 뒤부터");
        assertEquals(FULL, t.bowDrawnMs(1000 + CYCLE, CYCLE, 0), "다음 화살이 끝까지 = 쏜 시각 + 한 발 주기 (활만 쓰면 예전과 같음)");
        t.shot(1000 + CYCLE - 100, 1000, FULL, TOL, NOCK);
        assertFalse(t.hasBuffer(), "쏘면 기억한 근접을 지움");
    }

    @Test
    void meleeThenBowDrawStartsAfterTheMeleeInterval() {
        AttackTiming t = new AttackTiming();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(0, CYCLE, TOL, BUF, A, "bow"));
        assertEquals(0, t.bowDrawnMs(100, 100, 0), "근접 직후 → 세기 0");
        assertEquals(0, t.bowDrawnMs(CYCLE, 2000, 0), "근접 간격이 끝나는 때부터 센다 (남은 간격과 겹쳐 당기지 않음)");
        assertEquals(500, t.bowDrawnMs(CYCLE + 500, 2000, 0));
        assertEquals(300, t.bowDrawnMs(CYCLE + 500, 300, 0), "늦게 당기기 시작했으면 바닐라 시간");
        assertEquals(FULL, t.bowDrawnMs(CYCLE + FULL, CYCLE + FULL, 0), "끝까지 = 근접 간격 + 당김");
    }

    @Test
    void releaseAndRedrawAtOnceStillWaitsTheNock() {
        // 놓자마자 다시 당기는 매크로: 한 발 주기 = 당김 + 0.15초 (당김 + 0.05초가 아님)
        AttackTiming t = new AttackTiming();
        long drawStart = 0, first = -1, last = -1;
        int shots = 0;
        for (long now = 0; shots < 101; now += 10) {
            if (t.bowDrawnMs(now, now - drawStart, TOL) >= FULL) {
                t.shot(now, now - drawStart, FULL, TOL, NOCK);
                if (first < 0) first = now;
                last = now;
                shots++;
                drawStart = now;
            }
        }
        // 처음 한 번만 허용 오차(0.05초)만큼 이르고, 그 뒤로는 빌린 당김을 갚아 쌓이지 않는다
        assertEquals(100 * CYCLE, last - first, TOL + 10, "빨라지지 않음");
    }

    @Test
    void alternatingMeleeAndShotsGetOneAttackPerCycle() {
        // 같은 활로 쏘자마자 근접 한 대 → 다시 당겨 쏘기: 주기마다 화살 한 발 + 근접 한 대가 되면 안 된다
        AttackTiming t = new AttackTiming();
        long drawStart = -1;
        int attacks = 0;
        long end = 60_000;
        for (long now = 0; now < end; now += 10) {
            if (drawStart >= 0) {
                if (t.bowDrawnMs(now, now - drawStart, TOL) >= FULL) {
                    t.shot(now, now - drawStart, FULL, TOL, NOCK);
                    attacks++;
                    drawStart = -1;
                }
            } else if (t.click(now, CYCLE, TOL, 0, A, "bow") == AttackTiming.Result.ACCEPT) {
                attacks++;
                drawStart = now; // 근접 뒤 곧바로 당기기
            }
        }
        assertEquals((double) end / CYCLE, attacks, 1.5, "한 주기에 한 번");
    }

    @Test
    void earlyReleaseIsWeakAndStillCostsTheNock() {
        AttackTiming t = new AttackTiming();
        t.shot(0, FULL, FULL, TOL, NOCK);
        assertEquals(NOCK, t.nextReady());
        long drawn = t.bowDrawnMs(450, 400, TOL);
        assertEquals(450 - NOCK + TOL, drawn, "메기기 전부터 당겼어도 메기기 뒤부터 (+ 허용 오차)");
        t.shot(450, 400, FULL, TOL, NOCK);
        assertEquals(500 + NOCK, t.nextReady(), "약한 화살도 다시 메기기를 쓴다 (오차로 빌린 0.05초는 뒤로)");
        assertEquals(0, t.bowDrawnMs(600, 100, 0), "다음 당김도 다시 메기기 뒤부터");
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

    @Test
    void sameItemSwapFollowsTheVanillaGauge() {
        AttackTiming t = new AttackTiming();
        assertEquals(AttackTiming.Result.ACCEPT, t.click(1000, 1500, 100, 350, UUID.randomUUID(), "a"));
        t.swapSameItem(400); // 큰 무기로 친 직후 단도로 — 게이지는 마지막 공격 + 0.4초에 찬다
        assertEquals(AttackTiming.Result.ACCEPT, t.click(1400, 400, 100, 350, UUID.randomUUID(), "b"));
        t.swapSameItem(1500); // 단도로 친 뒤 큰 무기로 — 마지막 공격 + 1.5초까지 기다린다
        assertEquals(AttackTiming.Result.EARLY, t.click(1500, 1500, 100, 350, UUID.randomUUID(), "a"));
        assertEquals(AttackTiming.Result.ACCEPT, t.click(2850, 1500, 100, 350, UUID.randomUUID(), "a"));
    }

    @Test
    void gaugeTicksRoundToTheWeaponInterval() {
        assertEquals(20.0 / 17, kr.labyrinth.stats.StatService.clockedAttackSpeed(0.83), 1e-9);
        assertEquals(20.0, kr.labyrinth.stats.StatService.clockedAttackSpeed(0.01), 1e-9);
        assertEquals(20.0 / 30, kr.labyrinth.stats.StatService.clockedAttackSpeed(1.5), 1e-9);
    }
}
