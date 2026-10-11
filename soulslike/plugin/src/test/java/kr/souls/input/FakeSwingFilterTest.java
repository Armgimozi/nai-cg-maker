package kr.souls.input;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * M1 P1a (2.3 의 1, R2, S3): 가짜 휘두르기. 표시 (버리기·우클릭·물체 클릭) 뒤 1틱 안의 휘두르기, 서버가 휘두른 뒤 왕복 + 2틱 안의
 * 되돌아온 휘두르기는 입력이 아니다. 같은 틱이면 두 패킷의 차례와 상관없다 (둘 다 그 틱으로 적히고 다음 틱에 정한다).
 */
class FakeSwingFilterTest {
    private static final long N = FakeSwingFilter.NEVER;

    @Test
    void markWindowIsOneTick() {
        // 표시 → 휘두르기, 같은 틱 (바닐라: Q·우클릭 다음에 휘두르기)
        assertEquals("mark", FakeSwingFilter.why(100, 100, 1, N, 3));
        // 두 패킷이 틱 경계에 걸쳤다
        assertEquals("mark", FakeSwingFilter.why(101, 100, 1, N, 3));
        // 2틱 뒤의 휘두르기는 진짜 좌클릭
        assertNull(FakeSwingFilter.why(102, 100, 1, N, 3));
        // 표시가 없으면 진짜
        assertNull(FakeSwingFilter.why(100, N, 1, N, 3));
    }

    @Test
    void bothPacketOrdersInOneTick() {
        // 같은 틱에 휘두르기가 먼저 처리되고 표시가 뒤에 왔어도 둘 다 틱 100 이라 같은 판정 (판정은 다음 틱의 input 자리)
        long swingFirst = 100, markAfter = 100;
        assertEquals("mark", FakeSwingFilter.why(swingFirst, markAfter, 1, N, 3));
        // 휘두르기보다 늦은 틱의 표시는 그 휘두르기를 가짜로 만들지 않는다 (클라이언트는 표시를 먼저 보낸다)
        assertNull(FakeSwingFilter.why(100, 101, 1, N, 3));
    }

    @Test
    void windowFromConfig() {
        assertNull(FakeSwingFilter.why(101, 100, 0, N, 3), "창 0 이면 같은 틱만");
        assertEquals("mark", FakeSwingFilter.why(100, 100, 0, N, 3));
        assertEquals("mark", FakeSwingFilter.why(103, 100, 3, N, 3));
    }

    @Test
    void serverSwingEcho() {
        // 핑 50ms (1틱) + 2틱 = 3틱 안: 서버가 휘두른 뒤 되돌아온 주손 휘두르기
        int echo = FakeSwingFilter.pingTicks(50) + 2;
        assertEquals(3, echo);
        assertEquals("echo", FakeSwingFilter.why(200, N, 1, 200, echo));
        assertEquals("echo", FakeSwingFilter.why(203, N, 1, 200, echo));
        assertNull(FakeSwingFilter.why(204, N, 1, 200, echo), "그 뒤는 진짜 좌클릭");
        assertNull(FakeSwingFilter.why(199, N, 1, 200, echo), "서버가 휘두르기 전의 것은 진짜");
        // 둘 다 맞으면 표시가 먼저
        assertEquals("mark", FakeSwingFilter.why(200, 200, 1, 200, echo));
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
