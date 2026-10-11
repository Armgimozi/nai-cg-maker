package kr.souls.input;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * M1 P1a (2.3 의 1, R2, S3): 가짜 휘두르기. 표시 (버리기·우클릭·물체 클릭) 뒤 1틱 안의 휘두르기는 입력이 아니다. 같은 틱이면 두 패킷의
 * 차례와 상관없다 (둘 다 그 틱으로 적히고 다음 틱에 정한다). 서버가 휘두른 뒤 되돌아온 휘두르기는 2026-10-11 부터 장부로 센다: 서버
 * 휘두름 하나에 그 손의 휘두르기 하나 (FakeSwingFilter.Ledger). 한 왕복이 지나기 전에 온 것은 되돌림이 아니다 (묶었다가 정한다).
 */
class FakeSwingFilterTest {
    private static final long N = FakeSwingFilter.NEVER;

    @Test
    void markWindowIsOneTick() {
        // 표시 → 휘두르기, 같은 틱 (바닐라: Q·우클릭 다음에 휘두르기)
        assertEquals("mark", FakeSwingFilter.why(100, 100, 1));
        // 두 패킷이 틱 경계에 걸쳤다
        assertEquals("mark", FakeSwingFilter.why(101, 100, 1));
        // 2틱 뒤의 휘두르기는 진짜 좌클릭
        assertNull(FakeSwingFilter.why(102, 100, 1));
        // 표시가 없으면 진짜
        assertNull(FakeSwingFilter.why(100, N, 1));
    }

    @Test
    void bothPacketOrdersInOneTick() {
        // 같은 틱에 휘두르기가 먼저 처리되고 표시가 뒤에 왔어도 둘 다 틱 100 이라 같은 판정 (판정은 다음 틱의 input 자리)
        long swingFirst = 100, markAfter = 100;
        assertEquals("mark", FakeSwingFilter.why(swingFirst, markAfter, 1));
        // 휘두르기보다 늦은 틱의 표시는 그 휘두르기를 가짜로 만들지 않는다 (클라이언트는 표시를 먼저 보낸다)
        assertNull(FakeSwingFilter.why(100, 101, 1));
    }

    @Test
    void windowFromConfig() {
        assertNull(FakeSwingFilter.why(101, 100, 0), "창 0 이면 같은 틱만");
        assertEquals("mark", FakeSwingFilter.why(100, 100, 0));
        assertEquals("mark", FakeSwingFilter.why(103, 100, 3));
        assertTrue(FakeSwingFilter.mark(103, 100, 3));
        assertFalse(FakeSwingFilter.mark(104, 100, 3));
    }

    private static FakeSwingFilter.Ledger sent(long now, int pingTicks) {
        FakeSwingFilter.Ledger l = new FakeSwingFilter.Ledger();
        l.sent(now, pingTicks, 6);
        return l;
    }

    @Test
    void consumeOneEcho() {
        // 서버가 휘두른 틱 200, 핑 50ms (1틱) + echo-window 6 = 207 까지 하나를 받는다
        FakeSwingFilter.Ledger l = sent(200, FakeSwingFilter.pingTicks(50));
        assertEquals(207, l.until());
        assertEquals(200, l.from(), "핑 1틱: 받는 첫 틱은 휘두른 틱 (1 − 2 는 0 으로)");
        assertEquals(FakeSwingFilter.Verdict.ECHO, l.take(202, true), "되돌아온 휘두르기");
        assertEquals(0, l.due(202));
        assertEquals(FakeSwingFilter.Verdict.REAL, l.take(203, true), "하나를 쓴 뒤의 휘두르기는 진짜 좌클릭 (예전 창 규칙은 이것도 버렸다)");
        assertEquals(FakeSwingFilter.Verdict.ECHO, sent(200, 1).take(207, true), "끝 틱까지 받는다");
        assertEquals(FakeSwingFilter.Verdict.REAL, new FakeSwingFilter.Ledger().take(201, true), "서버가 휘두르지 않았으면 (막혔으면) 장부가 비어 진짜");
    }

    @Test
    void consumeExpires() {
        FakeSwingFilter.Ledger l = sent(200, 1);
        l.sent(200, 1, 6);
        assertEquals(2, l.due(204));
        assertEquals(FakeSwingFilter.Verdict.ECHO, l.take(204, true));
        assertEquals(1, l.due(204), "끝 틱 전에는 하나씩만 쓴다");
        assertEquals(FakeSwingFilter.Verdict.REAL, l.take(208, true), "끝 틱 뒤에 온 휘두르기는 진짜");
        assertEquals(0, l.due(208), "지나면 남은 되돌림은 버린다 (오지 않은 되돌림이 나중의 진짜 클릭을 먹지 않게)");
        // 끝난 뒤의 새 서버 휘두름은 새로 센다
        l.sent(300, 1, 6);
        assertEquals(1, l.due(300));
        assertEquals(300, l.from());
    }

    /** 서버 휘두름 둘 (장부 2) 뒤에 휘두르기 셋: 둘은 되돌아온 것, 하나는 진짜 (어느 것이 먼저 왔든 수는 같다). */
    @Test
    void twoServerSwingsThenThreeSwings() {
        FakeSwingFilter.Ledger l = sent(300, 1);
        l.sent(304, 1, 6);
        assertEquals(311, l.until());
        int echoes = 0, real = 0;
        for (long t : new long[]{302, 305, 306}) {
            if (l.take(t, true) == FakeSwingFilter.Verdict.ECHO) echoes++;
            else real++;
        }
        assertEquals(2, echoes);
        assertEquals(1, real);
        assertEquals(0, l.due(306));
    }

    /**
     * 검토 (2026-10-11): 핑이 큰 클라이언트는 공격이 시작된 뒤 서버 휘두름이 닿기 전에 누른 클릭을 되돌림보다 먼저 보낸다. 한 왕복 (핑 틱 − 2)
     * 전에 온 휘두르기는 되돌림일 수 없어 진짜로 묶어 두고, 되돌림이 오면 진짜로 푼다 (강공격의 웅크리기를 잃지 않는다).
     */
    @Test
    void clickBeforeTheEchoIsHeldThenReal() {
        // 핑 150ms (3틱): 받는 첫 틱 101, 끝 틱 109
        FakeSwingFilter.Ledger l = sent(100, FakeSwingFilter.pingTicks(150));
        assertEquals(101, l.from());
        assertEquals(109, l.until());
        assertEquals(FakeSwingFilter.Verdict.EARLY, l.take(100, true), "공격이 시작된 틱의 클릭은 되돌림이 아니다");
        assertNull(l.settle(101, 109), "되돌림이 오기 전에는 정하지 않는다");
        assertEquals(1, l.due(101), "이른 휘두르기는 장부를 쓰지 않는다");
        assertEquals(FakeSwingFilter.Verdict.ECHO, l.take(103, true), "그 뒤에 온 것이 되돌림");
        assertEquals(FakeSwingFilter.Verdict.REAL, l.settle(104, 109), "묶어 둔 클릭은 진짜");
        assertEquals(0, l.due(104));
        assertEquals(FakeSwingFilter.Verdict.REAL, l.take(105, true), "그 뒤의 클릭은 그냥 진짜");
    }

    /** 핑을 크게 본 때 (Paper 의 5초 평균): 되돌림이 받는 첫 틱보다 먼저 와도, 끝 틱까지 다른 것이 오지 않으면 그것을 되돌림으로 버린다. */
    @Test
    void earlyEchoIsDroppedWhenNothingFollows() {
        FakeSwingFilter.Ledger l = sent(100, 6);
        assertEquals(104, l.from());
        assertEquals(112, l.until());
        assertEquals(FakeSwingFilter.Verdict.EARLY, l.take(101, true));
        assertNull(l.settle(112, 112), "끝 틱까지는 기다린다");
        assertEquals(FakeSwingFilter.Verdict.ECHO, l.settle(113, 112), "끝 틱이 지나도록 되돌림이 없으면 그것이 되돌림이었다 (저절로 생긴 공격이 없다)");
        assertEquals(0, l.due(113));
        assertEquals(FakeSwingFilter.Verdict.REAL, l.take(113, true));
    }

    /** 남은 되돌림 하나에 이른 휘두르기는 하나만 묶는다 (둘 다 되돌림일 수는 없다). 묶는 동안 새 서버 휘두름은 앞의 받는 첫 틱을 둔다. */
    @Test
    void oneHeldPerOutstandingEcho() {
        FakeSwingFilter.Ledger l = sent(100, 4);
        assertEquals(102, l.from());
        assertEquals(FakeSwingFilter.Verdict.EARLY, l.take(100, true));
        assertEquals(FakeSwingFilter.Verdict.REAL, l.take(101, true), "둘째 이른 휘두르기는 묶지 않고 진짜");
        l.sent(101, 4, 6);
        assertEquals(102, l.from(), "남은 되돌림이 있으면 받는 첫 틱은 앞의 것");
        assertEquals(111, l.until());
        assertEquals(2, l.due(101));
        assertEquals(FakeSwingFilter.Verdict.ECHO, l.take(104, true));
        assertEquals(FakeSwingFilter.Verdict.REAL, l.settle(104, 110));
        assertEquals(FakeSwingFilter.Verdict.ECHO, l.take(105, true));
        assertEquals(0, l.due(105));
    }

    /** 왼손 (입력이 아니다): 이른 휘두르기는 진짜로만 치고 묶지 않는다. 장부는 그대로 되돌림을 기다린다. */
    @Test
    void offHandEarlyIsNotHeld() {
        FakeSwingFilter.Ledger l = sent(100, 4);
        assertEquals(FakeSwingFilter.Verdict.EARLY, l.take(100, false));
        assertEquals(1, l.due(100));
        assertEquals(FakeSwingFilter.Verdict.ECHO, l.take(104, false));
        assertNull(l.settle(104, 108), "묶은 것이 없다");
    }

    @Test
    void pingTicksRoundUp() {
        assertEquals(0, FakeSwingFilter.pingTicks(0));
        assertEquals(1, FakeSwingFilter.pingTicks(1));
        assertEquals(1, FakeSwingFilter.pingTicks(50));
        assertEquals(3, FakeSwingFilter.pingTicks(120));
        assertEquals(0, FakeSwingFilter.pingTicks(-5));
    }
}
