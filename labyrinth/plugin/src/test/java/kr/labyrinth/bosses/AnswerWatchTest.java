package kr.labyrinth.bosses;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.UnaryOperator;
import org.junit.jupiter.api.Test;

/**
 * bs363: 대응 감시 — 보스가 못 닿는 자리에서 맞고 있을 때만, 그 보스 자기 패턴으로 답할 때를 정한다.
 * 트인 곳 거리 두기·원거리 카이팅은 0번, 구석(멈춤·칼끝 띠·침)은 2초 무장 뒤, 쿨·최소 간격·6초 최소.
 */
class AnswerWatchTest {

    private static final UUID A = UUID.fromString("00000000-0000-0000-0000-00000000000a");
    private static final UUID B = UUID.fromString("00000000-0000-0000-0000-00000000000b");
    private static final long NEVER = Long.MAX_VALUE / 4;

    /** 틀 입력: 대상 A 가 (3.4, 0, 0) 칼끝 띠에서 방금 때림, 보스는 멈춤, 한가함, 쓸 수 있음. */
    private record In(UUID target, double tx, double ty, double tz, boolean free, boolean stationary, boolean reached, boolean band,
                      boolean sees, long targetHitAgo, long anyHitAgo, boolean stalled, boolean castStalled, boolean moved, boolean noSpot,
                      boolean allowed, boolean gapOk) {
        static In pocket() {
            return new In(A, 3.4, 0, 0, true, false, false, true, true, 0, 0, true, false, false, false, true, true);
        }

        AnswerWatch.Input at(long now) {
            return new AnswerWatch.Input(target, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled,
                    castStalled, moved, noSpot, allowed, gapOk, now);
        }

        In with(UnaryOperator<In> f) { return f.apply(this); }

        In tx(double v) { return new In(target, v, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In ty(double v) { return new In(target, tx, v, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In target(UUID v) { return new In(v, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In free(boolean v) { return new In(target, tx, ty, tz, v, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In stationary(boolean v) { return new In(target, tx, ty, tz, free, v, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In reached(boolean v) { return new In(target, tx, ty, tz, free, stationary, v, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In band(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, v, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In sees(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, band, v, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In hit(long t, long any) { return new In(target, tx, ty, tz, free, stationary, reached, band, sees, t, any, stalled, castStalled, moved, noSpot, allowed, gapOk); }
        In stalled(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, v, castStalled, moved, noSpot, allowed, gapOk); }
        In castStalled(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, v, moved, noSpot, allowed, gapOk); }
        In moved(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, v, noSpot, allowed, gapOk); }
        In noSpot(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, v, allowed, gapOk); }
        In allowed(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, v, gapOk); }
        In gapOk(boolean v) { return new In(target, tx, ty, tz, free, stationary, reached, band, sees, targetHitAgo, anyHitAgo, stalled, castStalled, moved, noSpot, allowed, v); }
    }

    /** 틱 from..to 동안 돌리며 쏜 (틱, 종류). 쏘면 fired(쿨 cd) 로 답한다. */
    private static List<long[]> run(AnswerWatch w, long from, long to, java.util.function.LongFunction<In> in, double cd) {
        List<long[]> out = new ArrayList<>();
        for (long t = from; t < to; t++) {
            AnswerWatch.Kind k = w.update(in.apply(t).at(t));
            if (k != null) {
                out.add(new long[] {t, k.ordinal()});
                w.fired(t, cd);
            }
        }
        return out;
    }

    private static long first(List<long[]> fires) { return fires.isEmpty() ? -1 : fires.get(0)[0]; }

    @Test
    void openFieldSpacingNeverAnswers() {
        // ① 트인 곳 거리 두기: 대상이 칼끝 띠에서 치고 빠지지만 보스는 걷는다 (멈춤 아님, 창이 다시 잡힘) · 대상도 움직인다
        AnswerWatch w = new AnswerWatch();
        List<long[]> f = run(w, 0, 6000, t -> In.pocket().stalled(false).moved(t % 3 == 0).tx(3.4 + (t / 10 % 4) * 0.6)
                .band(t % 40 < 30).hit(t % 20, t % 20), 200);
        assertEquals(0, f.size(), "트인 곳 대응 0번");
    }

    @Test
    void rangedKitingNeverAnswers() {
        // ② 원거리 카이팅: 칼끝 띠 밖, 대상은 원을 그리며 움직이고 1초마다 침 — 보스는 멈췄든 걷든 대응 0번
        for (boolean stalled : new boolean[] {false, true}) {
            AnswerWatch w = new AnswerWatch();
            List<long[]> f = run(w, 0, 6000, t -> In.pocket().band(false).stalled(stalled).noSpot(stalled)
                    .tx(9 * Math.cos(t / 40.0)).hit(t % 20, t % 20), 200);
            assertEquals(0, f.size(), "카이팅 대응 0번 (stalled=" + stalled + ")");
        }
    }

    @Test
    void pocketArmsAfterFortyTicksOfStall() {
        // ③ 구석: 멈춤 + 칼끝 띠 + 침 → 40틱 무장 뒤 BAND
        AnswerWatch w = new AnswerWatch();
        List<long[]> f = run(w, 0, 200, t -> In.pocket().hit(t % 20, t % 20), 200);
        assertEquals(AnswerWatch.ARM_BAND - 1, first(f), "멈춤 뒤 40틱째");
        assertEquals(AnswerWatch.Kind.BAND.ordinal(), (int) f.get(0)[1]);
        // 시야가 없거나 쓸 수 없으면 무장이 안 쌓인다
        AnswerWatch v = new AnswerWatch();
        assertEquals(0, run(v, 0, 400, t -> In.pocket().sees(false), 200).size());
        AnswerWatch x = new AnswerWatch();
        assertEquals(0, run(x, 0, 400, t -> In.pocket().allowed(false), 200).size());
    }

    @Test
    void busyTicksCountOnlyForCastsStartedWhileStalled() {
        // ④ 걷다 시작한 시전 (castStalled 거짓): 바쁜 틱은 안 셈 → 시전 뒤 빈 틱으로 40틱
        AnswerWatch walk = new AnswerWatch();
        for (long t = 0; t < 30; t++) assertNull(walk.update(In.pocket().free(false).castStalled(false).at(t)));
        assertEquals(0, walk.arm());
        // 멈춘 채 시작한 시전: 바쁜 틱도 셈 → 시전이 끝나는 첫 빈 틱에 바로
        AnswerWatch stuck = new AnswerWatch();
        for (long t = 0; t < 45; t++) assertNull(stuck.update(In.pocket().free(false).castStalled(true).at(t)), "바쁠 땐 안 쏨");
        assertTrue(stuck.arm() >= AnswerWatch.ARM_BAND);
        assertEquals(AnswerWatch.Kind.BAND, stuck.update(In.pocket().at(45)));
    }

    @Test
    void bandInAndOutOnlyDrainsAndResetsAfterAHundredTicksOut() {
        // ⑤ 띠 들락날락: 밖에 있으면 1씩 줄기만, 밖 100틱이면 0
        AnswerWatch w = new AnswerWatch();
        for (long t = 0; t < 30; t++) w.update(In.pocket().at(t));
        assertEquals(30, w.arm());
        for (long t = 30; t < 40; t++) w.update(In.pocket().band(false).at(t));
        assertEquals(20, w.arm(), "밖 10틱 → −10");
        for (long t = 40; t < 60; t++) w.update(In.pocket().at(t));
        assertEquals(40, w.arm());
        AnswerWatch v = new AnswerWatch();
        for (long t = 0; t < 39; t++) v.update(In.pocket().at(t));
        for (long t = 39; t < 39 + AnswerWatch.OFF_RESET; t++) v.update(In.pocket().band(false).hit(NEVER, NEVER).at(t));
        assertEquals(0, v.arm());
        // 띠 밖일 땐 무장이 다 찼어도 쏘지 않는다
        AnswerWatch o = new AnswerWatch();
        for (long t = 0; t < 45; t++) o.update(In.pocket().free(false).castStalled(true).at(t));
        assertNull(o.update(In.pocket().band(false).at(45)));
        assertTrue(o.arm() >= AnswerWatch.ARM_BAND);
    }

    @Test
    void targetChangeResetsCountsButKeepsCooldown() {
        // ⑥ 대상 바뀜 → 셈 0, 쿨은 보스 하나에 하나 그대로
        AnswerWatch w = new AnswerWatch();
        for (long t = 0; t < 30; t++) w.update(In.pocket().at(t));
        w.update(In.pocket().target(B).at(30));
        assertEquals(1, w.arm(), "새 대상은 처음부터");
        AnswerWatch c = new AnswerWatch();
        List<long[]> f = run(c, 0, 50, t -> In.pocket(), 200);
        assertEquals(1, f.size());
        long fired = f.get(0)[0];
        List<long[]> g = run(c, 50, 500, t -> In.pocket().target(B), 200);
        assertEquals(fired + 200, first(g), "다른 대상에게도 쿨이 지나야");
    }

    @Test
    void reachOrLandedBasicResetsEverything() {
        // ⑦ 기본 공격이 닿거나 맞으면 셈 0
        AnswerWatch w = new AnswerWatch();
        for (long t = 0; t < 35; t++) w.update(In.pocket().at(t));
        w.update(In.pocket().reached(true).at(35));
        assertEquals(0, w.arm());
        for (long t = 36; t < 70; t++) w.update(In.pocket().at(t));
        w.landed(A);
        assertEquals(0, w.arm());
        w.landed(B); // 다른 사람은 상관없음
        for (long t = 70; t < 75; t++) w.update(In.pocket().at(t));
        assertEquals(5, w.arm());
        // 닿는 동안에는 절대 안 쏜다
        AnswerWatch r = new AnswerWatch();
        assertEquals(0, run(r, 0, 1000, t -> In.pocket().reached(true), 200).size());
    }

    @Test
    void stationaryHeartAnswersInTheBandOnly() {
        // ⑧ 10층: 칼끝 띠 30틱에 STATIONARY (멈춤 입력과 무관), 띠 밖 원거리는 0번
        AnswerWatch w = new AnswerWatch();
        List<long[]> f = run(w, 0, 100, t -> In.pocket().stationary(true).stalled(false), 160);
        assertEquals(AnswerWatch.ARM_STATIONARY - 1, first(f));
        assertEquals(AnswerWatch.Kind.STATIONARY.ordinal(), (int) f.get(0)[1]);
        AnswerWatch far = new AnswerWatch();
        assertEquals(0, run(far, 0, 4000, t -> In.pocket().stationary(true).band(false).hit(t % 20, t % 20), 160).size());
        // 걷지 않는 보스는 "걸음 −10" 이 없다
        AnswerWatch m = new AnswerWatch();
        for (long t = 0; t < 20; t++) m.update(In.pocket().stationary(true).moved(true).free(false).at(t));
        assertEquals(20, m.arm());
    }

    @Test
    void perchNeedsStillStalledNoSpotAndHits() {
        // ⑨ PERCH: 띠 밖 높은 곳 + 가만히 + 보스 멈춤 + 걸어서 갈 설 자리 없음 + 대상이 침 → 가만히 2초 + 160틱
        In perch = In.pocket().band(false).noSpot(true).tx(2).ty(5);
        AnswerWatch w = new AnswerWatch();
        List<long[]> f = run(w, 0, 400, t -> perch.hit(t % 20, t % 20), 200);
        assertEquals(AnswerWatch.STILL_TICKS + AnswerWatch.ARM_PERCH - 1, first(f));
        assertEquals(AnswerWatch.Kind.PERCH.ordinal(), (int) f.get(0)[1]);
        // 하나라도 빠지면 0
        for (UnaryOperator<In> miss : List.<UnaryOperator<In>>of(i -> i.noSpot(false), i -> i.stalled(false), i -> i.sees(false),
                i -> i.allowed(false), i -> i.hit(AnswerWatch.ENGAGE_TICKS + 1, AnswerWatch.ENGAGE_TICKS + 1))) {
            AnswerWatch x = new AnswerWatch();
            assertEquals(0, run(x, 0, 1000, t -> perch.with(miss), 200).size());
        }
        // 움직이면 (가만히 아님) 0
        AnswerWatch mv = new AnswerWatch();
        assertEquals(0, run(mv, 0, 1000, t -> perch.tx(2 + (t / 30 % 2) * 1.5), 200).size());
    }

    @Test
    void stillTargetFiresEvenIfTheBossShuffles() {
        // ⑩ 보조 셈: 보스가 왔다 갔다 (멈춤 아님 + 창이 다시 잡혀 −10) 해도, 띠에서 가만히 선 대상에게 80 빈 틱에 BAND
        AnswerWatch w = new AnswerWatch();
        List<long[]> f = run(w, 0, 300, t -> In.pocket().stalled(false).moved(t % 4 == 0), 200);
        assertEquals(AnswerWatch.STILL_TICKS + AnswerWatch.STILL_FIRE - 1, first(f));
        assertEquals(AnswerWatch.Kind.BAND.ordinal(), (int) f.get(0)[1]);
        // 대상이 움직이면 보조 셈도 0 (트인 곳)
        AnswerWatch m = new AnswerWatch();
        assertEquals(0, run(m, 0, 2000, t -> In.pocket().stalled(false).moved(t % 4 == 0).tx(3.4 + (t / 25 % 2) * 1.2), 200).size());
    }

    @Test
    void cooldownMinGapAndSixSecondFloor() {
        // ⑪ 대응 쿨 (쿨 × 배율, 최소 6초) · 최소 간격 (gapOk 거짓이면 기다림)
        AnswerWatch w = new AnswerWatch();
        List<long[]> f = run(w, 0, 2000, t -> In.pocket(), 240);
        assertTrue(f.size() >= 2);
        for (int i = 1; i < f.size(); i++) assertEquals(240, f.get(i)[0] - f.get(i - 1)[0], "쿨마다 한 번");
        AnswerWatch s = new AnswerWatch();
        List<long[]> g = run(s, 0, 1000, t -> In.pocket(), 40); // 쿨 2초를 넣어도 6초
        for (int i = 1; i < g.size(); i++) assertEquals(AnswerWatch.MIN_COOLDOWN, g.get(i)[0] - g.get(i - 1)[0]);
        AnswerWatch gap = new AnswerWatch();
        List<long[]> h = run(gap, 0, 300, t -> In.pocket().gapOk(t >= 150), 200);
        assertEquals(150, first(h), "로테이션으로 막 쓴 패턴은 최소 간격 뒤");
        // 바쁜 틱에는 절대 안 쏜다
        AnswerWatch b = new AnswerWatch();
        assertEquals(0, run(b, 0, 500, t -> In.pocket().free(false).castStalled(true), 200).size());
    }

    @Test
    void threeZerosArmHalfTheCooldown() {
        // ⑫ answer 가 0 (지금 못 함) → 10틱 뒤 다시, 세 번이면 쿨의 절반
        AnswerWatch w = new AnswerWatch();
        long t = 0;
        List<Long> tries = new ArrayList<>();
        for (; t < 400 && tries.size() < 3; t++) {
            if (w.update(In.pocket().at(t)) != null) {
                tries.add(t);
                w.zero(t, 200);
            }
        }
        assertEquals(List.of(39L, 49L, 59L), tries);
        assertEquals(59 + 100, w.readyAt(), "쿨 200 의 절반");
        assertEquals(0, w.arm());
        AnswerWatch q = new AnswerWatch();
        for (long k = 0; k < 39; k++) q.update(In.pocket().at(k));
        assertNotNull(q.update(In.pocket().at(39)));
        q.zero(39, 40);
        q.zero(49, 40);
        q.zero(59, 40);
        assertEquals(59 + AnswerWatch.MIN_HALF, q.readyAt(), "절반도 최소 3초");
        // −1 = 이 보스는 대응 없음 → 끔
        AnswerWatch n = new AnswerWatch();
        n.none();
        assertEquals(0, run(n, 0, 500, k -> In.pocket(), 200).size());
    }

    @Test
    void gapTankEngagesWhenSomeoneElseHits() {
        // ⑬ 틈 탱커: 대상(도발)은 안 때리고 가만히 띠에 서 있고, 다른 사람이 보스를 친다 → 교전
        AnswerWatch w = new AnswerWatch();
        List<long[]> f = run(w, 0, 300, t -> In.pocket().hit(NEVER, t % 20), 200);
        assertEquals(AnswerWatch.STILL_TICKS + AnswerWatch.ARM_BAND - 1, first(f), "가만히 2초가 지나야 교전으로 셈");
        // 아무도 안 때리면 0
        AnswerWatch q = new AnswerWatch();
        assertEquals(0, run(q, 0, 1000, t -> In.pocket().hit(NEVER, NEVER), 200).size());
        // 탱커가 움직이면 0 (다른 사람만 때림)
        AnswerWatch m = new AnswerWatch();
        assertEquals(0, run(m, 0, 1000, t -> In.pocket().hit(NEVER, t % 20).tx(3.4 + (t / 30 % 2) * 1.5), 200).size());
    }

    @Test
    void bodyMovedResets() {
        // ⑭ 패턴이 몸을 1칸 넘게 옮긴 시전이 끝남 → 셈 0
        AnswerWatch w = new AnswerWatch();
        for (long t = 0; t < 35; t++) w.update(In.pocket().at(t));
        w.bodyMoved();
        assertEquals(0, w.arm());
        assertEquals(0, w.still());
        assertEquals(0, w.perch());
    }

    @Test
    void deterministic() {
        // ⑮ 같은 입력 같은 출력
        AnswerWatch a = new AnswerWatch(), b = new AnswerWatch();
        for (long t = 0; t < 5000; t++) {
            int i = (int) t;
            In in = In.pocket().band(i % 7 != 0).stalled(i % 11 != 0).moved(i % 13 == 0).sees(i % 29 != 0).hit(i % 50, i % 30)
                    .free(i % 9 != 0).castStalled(i % 2 == 0).noSpot(i % 3 == 0).tx(3.4 + (i / 200 % 3) * 0.8)
                    .target(i % 1000 < 900 ? A : B);
            AnswerWatch.Kind ka = a.update(in.at(t)), kb = b.update(in.at(t));
            assertEquals(ka, kb);
            if (ka != null) {
                a.fired(t, 200);
                b.fired(t, 200);
            }
        }
        assertEquals(a.firedCount(), b.firedCount());
    }
}
