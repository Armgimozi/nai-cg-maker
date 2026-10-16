package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;

import kr.labyrinth.core.ArmorLooks;
import org.junit.jupiter.api.Test;

/** 가죽 4부위 구르기 입력 (look_spec §1.3, 주인 결정 D1: 재사용 5초). */
class TumbleInputTest {

    static final ArmorLooks.Tumble CFG = ArmorLooks.Tumble.DEFAULT;
    static final long NONE = Long.MIN_VALUE;

    static TumbleInput.Result tap2(TumbleInput in, long first, long second, boolean ground, boolean blocked, long combo) {
        in.onSneak(first, ground, blocked, combo, CFG);
        return in.onSneak(second, ground, blocked, combo, CFG);
    }

    @Test
    void doubleTapWithinWindow() {
        assertEquals(TumbleInput.Result.TUMBLE, tap2(new TumbleInput(), 1000, 1300, true, false, NONE), "0.3초 안 두 번");
        assertEquals(TumbleInput.Result.NONE, tap2(new TumbleInput(), 1000, 1310, true, false, NONE), "0.31초는 아님");
        assertEquals(TumbleInput.Result.NONE, new TumbleInput().onSneak(1000, true, false, NONE, CFG), "한 번은 아님");
    }

    @Test
    void cooldownFiveSeconds() {
        TumbleInput in = new TumbleInput();
        assertEquals(TumbleInput.Result.TUMBLE, tap2(in, 0, 200, true, false, NONE));
        assertEquals(5.0, in.remaining(200), 1e-9);
        assertEquals(TumbleInput.Result.COOLDOWN, tap2(in, 3000, 3100, true, false, NONE));
        assertEquals(TumbleInput.Result.COOLDOWN, tap2(in, 5000, 5100, true, false, NONE), "4.9초 뒤 — 아직");
        assertEquals(TumbleInput.Result.TUMBLE, tap2(in, 5150, 5250, true, false, NONE), "5초 뒤");
    }

    @Test
    void airBlockedComboGuard() {
        assertEquals(TumbleInput.Result.NONE, tap2(new TumbleInput(), 0, 200, false, false, NONE), "공중");
        assertEquals(TumbleInput.Result.NONE, tap2(new TumbleInput(), 0, 200, true, true, NONE), "속박·꺼짐 등");
        assertEquals(TumbleInput.Result.NONE, tap2(new TumbleInput(), 1000, 1200, true, false, 900), "조합 스킬 뒤 0.4초 안");
        assertEquals(TumbleInput.Result.TUMBLE, tap2(new TumbleInput(), 1000, 1200, true, false, 700), "0.5초 뒤면 됨");
    }

    @Test
    void tripleTapRollsOnce() {
        TumbleInput in = new TumbleInput();
        assertEquals(TumbleInput.Result.TUMBLE, tap2(in, 0, 150, true, false, NONE));
        assertEquals(TumbleInput.Result.NONE, in.onSneak(280, true, false, NONE, CFG), "세 번째 누름은 새 첫 누름");
    }

    @Test
    void directionFromInput() {
        double[] back = TumbleInput.direction(false, false, false, false, 0f, CFG);
        assertArrayEquals(new double[] {0, -1, 2.0}, back, 1e-9, "방향 없음 = 뒤로 2칸");
        assertArrayEquals(new double[] {0, 1, 3.5}, TumbleInput.direction(true, false, false, false, 0f, CFG), 1e-9);
        assertArrayEquals(new double[] {1, 0, 3.5}, TumbleInput.direction(false, false, true, false, 0f, CFG), 1e-9, "남쪽을 볼 때 왼쪽 = 동쪽");
        assertArrayEquals(new double[] {-1, 0, 3.5}, TumbleInput.direction(true, false, false, false, 90f, CFG), 1e-9, "서쪽을 봄");
        double[] diag = TumbleInput.direction(true, false, false, true, 0f, CFG);
        assertEquals(1.0, Math.hypot(diag[0], diag[1]), 1e-9);
        assertEquals(1.05, TumbleInput.speedFor(3.5), 1e-9);
        assertEquals(0.6, TumbleInput.speedFor(2.0), 1e-9);
    }
}
