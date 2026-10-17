package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.UUID;
import org.junit.jupiter.api.Test;

/** bs362: 추격 막힘 감시 — 멈춤 → 직접 다가가기 → 거리 좁히기, 트인 곳·카이팅·안 걷는 보스는 그대로. */
class ChaseGuardTest {

    private static final UUID A = UUID.fromString("00000000-0000-0000-0000-00000000000a");
    private static final UUID B = UUID.fromString("00000000-0000-0000-0000-00000000000b");
    private static final long NEVER = Long.MAX_VALUE / 4;

    /** 보스가 (bx, 0) 에 서서 대상 A 를 못 치는 한 틱. */
    private static ChaseGuard.Input stuck(double bx, double dist, boolean sees, long sinceHit) {
        return new ChaseGuard.Input(A, true, false, dist, false, sees, sinceHit, bx, 0);
    }

    /** n 틱 돌리고, 거리 좁히기가 처음 나온 틱 (1부터, 없으면 −1). */
    private static int firstGap(ChaseGuard g, int n, java.util.function.IntFunction<ChaseGuard.Input> in) {
        for (int i = 1; i <= n; i++) {
            if (g.update(in.apply(i)).closeGap()) return i;
        }
        return -1;
    }

    @Test
    void inReachNeverEscalates() {
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < 400; i++) {
            ChaseGuard.Output o = g.update(new ChaseGuard.Input(A, true, true, 2.5, false, true, 0, 0, 0));
            assertEquals(ChaseGuard.Move.PATH, o.move());
            assertFalse(o.closeGap());
        }
    }

    @Test
    void stalledNextToEngagedTargetSteersThenClosesGap() {
        ChaseGuard g = new ChaseGuard();
        // 보스가 3.49칸에 그대로 서 있고 (길이 바로 끝남) 대상이 계속 때린다 — 사장님 자리
        ChaseGuard.Output first = g.update(stuck(0, 3.49, true, 0));
        assertEquals(ChaseGuard.Move.PATH, first.move(), "처음엔 길찾기");
        boolean steered = false;
        int gapAt = -1;
        for (int i = 2; i <= 200 && gapAt < 0; i++) {
            ChaseGuard.Output o = g.update(stuck(0, 3.49, true, 0));
            if (o.move() == ChaseGuard.Move.STEER) steered = true;
            if (o.closeGap()) gapAt = i;
        }
        assertTrue(steered, "멈추면 직접 다가가기");
        // 멈춤은 창(10틱) 끝에 알아채고, 그 뒤 40틱 → 2.5~3초 안
        assertTrue(gapAt >= ChaseGuard.WINDOW + ChaseGuard.GAP_AFTER && gapAt <= 2 * ChaseGuard.WINDOW + ChaseGuard.GAP_AFTER + 1, "gap " + gapAt);
        // 한 번 알린 뒤에는 다시 멈춤이 쌓여야 또 알린다
        int again = firstGap(g, 200, i -> stuck(0, 3.49, true, 0));
        assertTrue(again >= ChaseGuard.GAP_AFTER, "again " + again);
    }

    @Test
    void movingBossNeverClosesGap() {
        // 트인 곳 추격·원거리 카이팅: 대상은 계속 때리고 기본 공격은 안 닿지만 보스는 걷고 있다
        ChaseGuard g = new ChaseGuard();
        assertEquals(-1, firstGap(g, 2000, i -> new ChaseGuard.Input(A, true, false, 9.0, false, true, 0, i * 0.12, 0)));
        // 떠다니는 보스(길 없음)도 직접 다가가며 움직이는 동안은 그대로
        ChaseGuard f = new ChaseGuard();
        ChaseGuard.Output o = f.update(new ChaseGuard.Input(A, true, false, 12, true, true, 0, 0, 0));
        assertEquals(ChaseGuard.Move.STEER, o.move(), "길이 없으면 거리와 상관없이 바로 다가간다");
        assertEquals(-1, firstGap(f, 2000, i -> new ChaseGuard.Input(A, true, false, 12, true, true, 0, i * 0.086, 0)));
    }

    @Test
    void disengagedTargetIsLeftAlone() {
        // 멀리(8칸) 있고 4초 넘게 안 때린 대상: 멈춰도 도약하지 않는다
        ChaseGuard g = new ChaseGuard();
        assertEquals(-1, firstGap(g, 400, i -> stuck(0, 8, true, ChaseGuard.ENGAGE_TICKS + 1)));
        // 같은 자리에서 때리기 시작하면 (원거리) → 거리 좁히기
        int gap = firstGap(g, 400, i -> stuck(0, 8, true, 5));
        assertTrue(gap > 0 && gap <= ChaseGuard.GAP_AFTER + 1, "gap " + gap);
        // 가까우면(6칸 안) 안 때려도 교전 중
        ChaseGuard h = new ChaseGuard();
        assertTrue(firstGap(h, 200, i -> stuck(0, 5.5, true, NEVER)) > 0);
    }

    @Test
    void steeringNeedsSightAndRange() {
        ChaseGuard g = new ChaseGuard();
        // 안 보이면 처음엔 길찾기 그대로 — 멈춘 뒤 1초 더 지나야 잠깐(3초) 안 보여도 다가가 본다 (충돌이 벽을 막는다)
        int firstSteer = -1, steerTicks = 0;
        int total = 2 * (ChaseGuard.BLIND_TICKS + 2 * ChaseGuard.BLIND_AFTER) + ChaseGuard.WINDOW + ChaseGuard.BLIND_AFTER;
        for (int i = 1; i <= total; i++) {
            if (g.update(stuck(0, 4, false, 0)).move() == ChaseGuard.Move.STEER) {
                if (firstSteer < 0) firstSteer = i;
                steerTicks++;
            }
        }
        assertTrue(firstSteer >= ChaseGuard.WINDOW + ChaseGuard.BLIND_AFTER, "first " + firstSteer);
        assertTrue(steerTicks <= 2 * ChaseGuard.BLIND_TICKS + 2 && steerTicks < total * 0.75, "블라인드는 잠깐씩 " + steerTicks + "/" + total);
        // 다가가다 보이게 되면 그대로 이어서 다가간다
        ChaseGuard v = new ChaseGuard();
        for (int i = 0; i < ChaseGuard.WINDOW + ChaseGuard.BLIND_AFTER + 1; i++) v.update(stuck(0, 4, false, 0));
        assertTrue(v.steering());
        for (int i = 0; i < ChaseGuard.BLIND_TICKS + 20; i++) assertEquals(ChaseGuard.Move.STEER, v.update(stuck(0, 4, true, 0)).move());
        // 길이 있고 멀면(6칸 밖) 다가가기 안 함
        ChaseGuard h = new ChaseGuard();
        for (int i = 0; i < 60; i++) assertEquals(ChaseGuard.Move.PATH, h.update(stuck(0, 7, true, 0)).move());
        // 다가가는 중 대상이 멀어지면(8칸 밖) 길찾기로 돌아감
        ChaseGuard k = new ChaseGuard();
        for (int i = 0; i < 30; i++) k.update(stuck(0, 4, true, 0));
        assertTrue(k.steering());
        assertEquals(ChaseGuard.Move.PATH, k.update(stuck(0, 8.5, true, 0)).move());
    }

    @Test
    void reachResetsEverything() {
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < 45; i++) g.update(stuck(0, 3.5, true, 0));
        assertTrue(g.blocked() > 0);
        g.update(new ChaseGuard.Input(A, true, true, 3.0, false, true, 0, 0, 0));
        assertEquals(0, g.blocked());
        assertFalse(g.steering());
        // 다시 처음부터 쌓는다 (닿은 틱부터 창을 다시 잰다)
        int gap = firstGap(g, 200, i -> stuck(0, 3.5, true, 0));
        assertTrue(gap >= ChaseGuard.WINDOW + ChaseGuard.GAP_AFTER - 1, "gap " + gap);
    }

    @Test
    void cannotMoveHoldsAndNeverLeaps() {
        // 10층 심장(길찾기 꺼짐) · 패턴이 몸을 움직이는 중
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < 400; i++) {
            ChaseGuard.Output o = g.update(new ChaseGuard.Input(A, false, false, 4.5, false, true, 0, 0, 0));
            assertEquals(ChaseGuard.Move.HOLD, o.move());
            assertFalse(o.closeGap());
        }
        // 다시 걸을 수 있게 되면 처음부터 센다
        int gap = firstGap(g, 200, i -> stuck(0, 3.5, true, 0));
        assertTrue(gap >= ChaseGuard.WINDOW + ChaseGuard.GAP_AFTER, "gap " + gap);
    }

    @Test
    void targetChangeResets() {
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < 45; i++) g.update(stuck(0, 3.5, true, 0));
        assertTrue(g.blocked() > 0);
        ChaseGuard.Output o = g.update(new ChaseGuard.Input(B, true, false, 3.5, false, true, 0, 0, 0));
        assertFalse(o.closeGap());
        assertEquals(0, g.blocked());
        assertFalse(g.steering());
        // 대상 없음
        assertEquals(ChaseGuard.Move.HOLD, g.update(new ChaseGuard.Input(null, true, false, 0, false, false, NEVER, 0, 0)).move());
    }

    @Test
    void smallShufflesStillCountAsStalled() {
        // 길이 1~2칸 덜 가서 끝나며 제자리에서 0.1칸씩 흔들리는 것도 멈춤
        ChaseGuard g = new ChaseGuard();
        int gap = firstGap(g, 200, i -> stuck((i % 2) * 0.1, 3.5, true, 0));
        assertTrue(gap > 0 && gap <= 2 * ChaseGuard.WINDOW + ChaseGuard.GAP_AFTER + 1, "gap " + gap);
    }

    @Test
    void deterministic() {
        ChaseGuard a = new ChaseGuard(), b = new ChaseGuard();
        for (int i = 0; i < 500; i++) {
            ChaseGuard.Input in = new ChaseGuard.Input(A, true, i % 97 == 0, 3 + (i % 7) * 0.5, i % 31 < 3, i % 13 != 0, i % 50,
                    (i / 40) * 0.5, 0);
            assertEquals(a.update(in), b.update(in));
        }
    }
}
