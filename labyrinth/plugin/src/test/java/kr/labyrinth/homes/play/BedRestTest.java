package kr.labyrinth.homes.play;

import static org.junit.jupiter.api.Assertions.assertEquals;

import kr.labyrinth.homes.HomesConfig;
import org.junit.jupiter.api.Test;

/** 침대 쉬기 (0.3.7): 2초 (움직이거나 맞으면 끊김 · 자는 동안은 움직임 아님) → 가득 · 60초에 한 번. */
class BedRestTest {

    static final long T0 = 5_000_000L;
    static final BedRest.Session S = new BedRest.Session(T0, 10.5, 70, -3.5);

    @Test
    void waitsThenDone() {
        assertEquals(BedRest.Step.WAIT, BedRest.tick(S, T0 + 100, 10.5, 70, -3.5, false, 0, 2));
        assertEquals(BedRest.Step.WAIT, BedRest.tick(S, T0 + 1_999, 10.5, 70, -3.5, false, 0, 2));
        assertEquals(BedRest.Step.DONE, BedRest.tick(S, T0 + 2_000, 10.5, 70, -3.5, false, 0, 2));
        assertEquals(0.5, BedRest.progress(S, T0 + 1_000, 2), 1e-9);
        assertEquals(1.0, BedRest.progress(S, T0 + 9_000, 2), 1e-9);
    }

    @Test
    void movingOrBeingHitCancels() {
        assertEquals(BedRest.Step.WAIT, BedRest.tick(S, T0 + 500, 10.7, 70, -3.4, false, 0, 2), "고개·몸 살짝은 괜찮음");
        assertEquals(BedRest.Step.CANCELLED, BedRest.tick(S, T0 + 500, 11.0, 70, -3.5, false, 0, 2), "걸음");
        assertEquals(BedRest.Step.CANCELLED, BedRest.tick(S, T0 + 500, 10.5, 71, -3.5, false, 0, 2), "뜀");
        assertEquals(BedRest.Step.CANCELLED, BedRest.tick(S, T0 + 500, 10.5, 70, -3.5, false, T0 + 400, 2), "맞음");
        assertEquals(BedRest.Step.WAIT, BedRest.tick(S, T0 + 500, 10.5, 70, -3.5, false, T0 - 10, 2), "시작 전에 맞은 것은 상관없음");
        assertEquals(BedRest.Step.CANCELLED, BedRest.tick(null, T0, 0, 0, 0, false, 0, 2));
    }

    @Test
    void sleepingMovesTheBodyButDoesNotCancel() {
        // 밤에 누우면 서버가 몸을 침대 칸으로 옮긴다
        assertEquals(BedRest.Step.WAIT, BedRest.tick(S, T0 + 500, 11.5, 70.56, -2.5, true, 0, 2));
        assertEquals(BedRest.Step.DONE, BedRest.tick(S, T0 + 2_500, 11.5, 70.56, -2.5, true, 0, 2));
    }

    @Test
    void cooldown() {
        assertEquals(0, BedRest.cooldownLeftMs(0, T0, 60), "처음");
        assertEquals(30_000, BedRest.cooldownLeftMs(T0 - 30_000, T0, 60));
        assertEquals(0, BedRest.cooldownLeftMs(T0 - 60_000, T0, 60));
        assertEquals(0, BedRest.cooldownLeftMs(T0 - 1, T0, 0), "쿨다운 0");
        HomesConfig.BedRest d = HomesConfig.DEFAULT.bedRest();
        assertEquals(2, d.seconds());
        assertEquals(60, d.cooldownSeconds());
    }
}
