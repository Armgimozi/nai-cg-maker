package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.UUID;
import org.junit.jupiter.api.Test;

/** bs362 → bs363: 추격 막힘 감시 — 멈춤 → 곧장 걷기 → 자리 지키기. 트인 곳·카이팅·안 걷는 보스는 그대로, 거리 좁히기는 없다. */
class ChaseGuardTest {

    private static final UUID A = UUID.fromString("00000000-0000-0000-0000-00000000000a");
    private static final UUID B = UUID.fromString("00000000-0000-0000-0000-00000000000b");

    /** 보스가 (bx, 0) 에 서서 (bx + dist, 0) 의 대상 A 를 못 치는 한 틱. */
    private static ChaseGuard.Input stuck(double bx, double dist, boolean sees) {
        return new ChaseGuard.Input(A, true, false, dist, false, sees, bx, 0, bx + dist, 0, false);
    }

    private static ChaseGuard.Input reach(double bx, double tx, boolean detouring) {
        return new ChaseGuard.Input(A, true, true, Math.abs(tx - bx), false, true, bx, 0, tx, 0, detouring);
    }

    @Test
    void inReachInTheOpenIsPlainPathingAndNeverHolds() {
        // 트인 곳 길찾기로 닿은 경우: 0.3.6.1 그대로 (자리 지키기 없음)
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < 400; i++) {
            ChaseGuard.Output o = g.update(reach(0, 2.5, false));
            assertEquals(ChaseGuard.Move.PATH, o.move());
            assertFalse(o.stalled());
            assertFalse(g.latched());
        }
    }

    @Test
    void stalledNextToTargetSteers() {
        ChaseGuard g = new ChaseGuard();
        // 보스가 3.37칸에 그대로 서 있고 (길이 바로 끝남) 대상이 보인다 — 사장님 자리
        ChaseGuard.Output first = g.update(stuck(0, 3.37, true));
        assertEquals(ChaseGuard.Move.PATH, first.move(), "처음엔 길찾기");
        int steerAt = -1;
        for (int i = 2; i <= 40 && steerAt < 0; i++) {
            ChaseGuard.Output o = g.update(stuck(0, 3.37, true));
            if (o.move() == ChaseGuard.Move.STEER) {
                steerAt = i;
                assertTrue(o.stalled(), "멈춤이 곧장 걷기를 연다");
            }
        }
        assertTrue(steerAt > 0 && steerAt <= ChaseGuard.WINDOW + 1, "steer " + steerAt);
    }

    @Test
    void steeringIntoReachLatchesAndHolds() {
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < ChaseGuard.WINDOW + 2; i++) g.update(stuck(0, 3.4, true));
        assertTrue(g.steering());
        // 설 자리로 걸어 닿았다 → 자리 지키기
        ChaseGuard.Output o = g.update(reach(0.5, 3.4, false));
        assertEquals(ChaseGuard.Move.HOLD, o.move());
        assertTrue(g.latched());
        // 대상이 0.75칸 안에서 조금 움직여도 지킨다 (보스가 0.85 × reach 길찾기로 길 끝까지 끌려 나가지 않게)
        for (int i = 0; i < 200; i++) {
            ChaseGuard.Output h = g.update(reach(0.5, 3.4 + (i % 2) * 0.5, false));
            assertEquals(ChaseGuard.Move.HOLD, h.move(), "tick " + i);
            assertFalse(h.stalled());
        }
    }

    @Test
    void latchReleasesWhenTargetMovesOrReachIsLost() {
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < ChaseGuard.WINDOW + 2; i++) g.update(stuck(0, 3.4, true));
        assertEquals(ChaseGuard.Move.HOLD, g.update(reach(0.5, 3.4, false)).move());
        // 대상이 0.75칸 넘게 움직임 → 풂 → 보통 추격
        assertEquals(ChaseGuard.Move.PATH, g.update(reach(0.5, 3.4 + ChaseGuard.LATCH_MOVE + 0.05, false)).move());
        assertFalse(g.latched());
        // 다시 걸어 닿으면 다시 지킨다 (돌아가기로 닿음)
        assertEquals(ChaseGuard.Move.HOLD, g.update(reach(0.5, 3.4, true)).move());
        assertTrue(g.latched());
        // 안 닿게 되면 풂
        ChaseGuard.Output o = g.update(stuck(0.5, 4.5, true));
        assertFalse(g.latched());
        assertTrue(o.move() != ChaseGuard.Move.HOLD);
    }

    @Test
    void detourArrivalLatchesButOpenPathArrivalDoesNot() {
        ChaseGuard d = new ChaseGuard();
        d.update(stuck(0, 5, true));
        assertEquals(ChaseGuard.Move.HOLD, d.update(reach(0, 3.0, true)).move(), "돌아가기로 닿음 → 지킴");
        ChaseGuard p = new ChaseGuard();
        p.update(stuck(0, 5, true));
        assertEquals(ChaseGuard.Move.PATH, p.update(reach(0, 3.0, false)).move(), "트인 곳 길찾기로 닿음 → 그대로");
    }

    @Test
    void movingBossIsNeverStalled() {
        // 트인 곳 추격·원거리 카이팅: 기본 공격은 안 닿지만 보스는 걷고 있다
        ChaseGuard g = new ChaseGuard();
        int moved = 0;
        for (int i = 0; i < 2000; i++) {
            ChaseGuard.Output o = g.update(new ChaseGuard.Input(A, true, false, 9.0, false, true, i * 0.12, 0, i * 0.12 + 9, 0, false));
            assertFalse(o.stalled(), "tick " + i);
            assertEquals(ChaseGuard.Move.PATH, o.move());
            if (o.moved()) moved++;
        }
        assertTrue(moved >= 600, "걸으면 창이 계속 다시 잡힌다 " + moved);
        // 떠다니는 보스(길 없음)는 거리와 상관없이 바로 다가가고, 움직이는 동안 멈춤이 아니다
        ChaseGuard f = new ChaseGuard();
        assertEquals(ChaseGuard.Move.STEER, f.update(new ChaseGuard.Input(A, true, false, 12, true, true, 0, 0, 12, 0, false)).move());
        for (int i = 1; i < 500; i++) {
            assertFalse(f.update(new ChaseGuard.Input(A, true, false, 12, true, true, i * 0.086, 0, i * 0.086 + 12, 0, false)).stalled());
        }
    }

    @Test
    void steeringNeedsSightAndRange() {
        ChaseGuard g = new ChaseGuard();
        // 안 보이면 처음엔 길찾기 그대로 — 멈춘 뒤 1초 더 지나야 잠깐(3초) 안 보여도 다가가 본다 (충돌이 벽을 막는다)
        int firstSteer = -1, steerTicks = 0;
        int total = 2 * (ChaseGuard.BLIND_TICKS + 2 * ChaseGuard.BLIND_AFTER) + ChaseGuard.WINDOW + ChaseGuard.BLIND_AFTER;
        for (int i = 1; i <= total; i++) {
            if (g.update(stuck(0, 4, false)).move() == ChaseGuard.Move.STEER) {
                if (firstSteer < 0) firstSteer = i;
                steerTicks++;
            }
        }
        assertTrue(firstSteer >= ChaseGuard.WINDOW + ChaseGuard.BLIND_AFTER, "first " + firstSteer);
        assertTrue(steerTicks <= 2 * ChaseGuard.BLIND_TICKS + 2 && steerTicks < total * 0.75, "블라인드는 잠깐씩 " + steerTicks + "/" + total);
        // 다가가다 보이게 되면 그대로 이어서 다가간다
        ChaseGuard v = new ChaseGuard();
        for (int i = 0; i < ChaseGuard.WINDOW + ChaseGuard.BLIND_AFTER + 1; i++) v.update(stuck(0, 4, false));
        assertTrue(v.steering());
        for (int i = 0; i < ChaseGuard.BLIND_TICKS + 20; i++) assertEquals(ChaseGuard.Move.STEER, v.update(stuck(0, 4, true)).move());
        // 길이 있고 멀면(6칸 밖) 다가가기 안 함
        ChaseGuard h = new ChaseGuard();
        for (int i = 0; i < 60; i++) assertEquals(ChaseGuard.Move.PATH, h.update(stuck(0, 7, true)).move());
        // 다가가는 중 대상이 멀어지면(8칸 밖) 길찾기로 돌아감
        ChaseGuard k = new ChaseGuard();
        for (int i = 0; i < 30; i++) k.update(stuck(0, 4, true));
        assertTrue(k.steering());
        assertEquals(ChaseGuard.Move.PATH, k.update(stuck(0, 8.5, true)).move());
    }

    @Test
    void cannotMoveHolds() {
        // 10층 심장(길찾기 꺼짐) · 패턴이 몸을 움직이는 중
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < 400; i++) {
            ChaseGuard.Output o = g.update(new ChaseGuard.Input(A, false, false, 4.5, false, true, 0, 0, 4.5, 0, false));
            assertEquals(ChaseGuard.Move.HOLD, o.move());
            assertFalse(o.stalled());
            assertFalse(g.latched());
        }
    }

    @Test
    void targetChangeAndResetStartOver() {
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < 45; i++) g.update(stuck(0, 3.5, true));
        assertTrue(g.blocked() > 0 && g.stalled());
        ChaseGuard.Output o = g.update(new ChaseGuard.Input(B, true, false, 3.5, false, true, 0, 0, 3.5, 0, false));
        assertFalse(o.stalled());
        assertEquals(0, g.blocked());
        assertFalse(g.steering());
        // 대상 없음
        assertEquals(ChaseGuard.Move.HOLD, g.update(new ChaseGuard.Input(null, true, false, 0, false, false, 0, 0, 0, 0, false)).move());
        // reset (대응 뒤): 멈춤·걷기·지키기 처음으로
        ChaseGuard r = new ChaseGuard();
        for (int i = 0; i < ChaseGuard.WINDOW + 2; i++) r.update(stuck(0, 3.4, true));
        r.update(reach(0.5, 3.4, false));
        assertTrue(r.latched());
        r.reset();
        assertFalse(r.latched() || r.steering() || r.stalled());
    }

    @Test
    void smallShufflesStillCountAsStalled() {
        // 길이 1~2칸 덜 가서 끝나며 제자리에서 0.1칸씩 흔들리는 것도 멈춤
        ChaseGuard g = new ChaseGuard();
        boolean stalled = false;
        for (int i = 1; i <= 2 * ChaseGuard.WINDOW + 1; i++) {
            ChaseGuard.Output o = g.update(stuck((i % 2) * 0.1, 3.5, true));
            assertFalse(o.moved());
            stalled |= o.stalled();
        }
        assertTrue(stalled);
    }

    @Test
    void movedBossIsNotStalledEvenMidWindow() {
        // 멈춤이 쌓인 뒤 패턴 이동·순간이동으로 몸이 옮겨지면, 창 끝을 기다리지 않고 바로 처음부터 센다
        ChaseGuard g = new ChaseGuard();
        for (int i = 0; i < ChaseGuard.WINDOW + 20; i++) g.update(stuck(0, 2.1, false));
        assertTrue(g.stalled());
        ChaseGuard.Output o = g.update(stuck(3.9, 9.0, true));
        assertFalse(o.stalled());
        assertTrue(o.moved());
        assertEquals(0, g.blocked());
        // 거기서 다시 멈추면 창(10틱) 뒤에야 멈춤
        int at = -1;
        for (int i = 1; i <= 40 && at < 0; i++) if (g.update(stuck(3.9, 9.0, true)).stalled()) at = i;
        assertTrue(at >= ChaseGuard.WINDOW - 1, "at " + at);
    }

    @Test
    void deterministic() {
        ChaseGuard a = new ChaseGuard(), b = new ChaseGuard();
        for (int i = 0; i < 500; i++) {
            ChaseGuard.Input in = new ChaseGuard.Input(A, true, i % 97 == 0, 3 + (i % 7) * 0.5, i % 31 < 3, i % 13 != 0, (i / 40) * 0.5, 0,
                    (i / 40) * 0.5 + 3, (i % 5) * 0.3, i % 17 == 0);
            assertEquals(a.update(in), b.update(in));
        }
    }
}
