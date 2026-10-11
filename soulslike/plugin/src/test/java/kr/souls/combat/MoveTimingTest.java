package kr.souls.combat;

import kr.souls.Config;
import kr.souls.TestFiles;
import kr.souls.progression.StatCurves;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** M1 P1a (3.6): 민첩의 공격 속도로 나눈 틱. 보기는 DESIGN 3.6 의 것 그대로 (기본 config.yml 의 민첩 곡선). */
class MoveTimingTest {
    private static final StatCurves C = new Config(TestFiles.yaml("config.yml")).stats;
    private static final MoveTiming.Rules R = MoveTiming.Rules.DEFAULT;

    private static double a(int dex) {
        return DamageCalc.attackSpeed(C, dex);
    }

    @Test
    void dex10IsTheTable() {
        for (int[] t : new int[][] {{3, 1, 6}, {4, 2, 7}, {5, 2, 8}, {13, 3, 16}, {6, 2, 10}}) {
            MoveTiming.Timed x = MoveTiming.time(new MoveTiming.Base(t[0], t[1], t[2]), a(10), 0, R);
            assertEquals(t[0], x.s());
            assertEquals(t[1], x.a());
            assertEquals(t[2], x.r());
            assertEquals(0, x.carry(), 1e-9);
        }
    }

    @Test
    void daggerOnlyStartupShrinks() {
        MoveTiming.Base dagger = new MoveTiming.Base(3, 1, 6);
        MoveTiming.Timed d36 = MoveTiming.time(dagger, a(36), 0, R);
        assertEquals(1.20, a(36), 1e-9);
        assertEquals(3, d36.s(), "민첩 36 (×1.20): 3 / 1.2 = 2.5 는 올려 3");
        assertEquals(10, d36.cycle(), "한 주기 10틱 밑으로 가지 않는다");
        MoveTiming.Timed d37 = MoveTiming.time(dagger, a(37), 0, R);
        assertEquals(2, d37.s(), "민첩 37 부터 준비 2틱");
        assertEquals(1, d37.a());
        assertEquals(7, d37.r(), "모자란 몫은 회복에 되돌린다: 2/1/7");
        assertEquals(0, d37.carry(), 1e-9, "최소에 걸렸으면 몫을 모으지 않는다");
        MoveTiming.Timed d99 = MoveTiming.time(dagger, a(99), 0, R);
        assertEquals(10, d99.cycle(), "민첩 99 도 단도 약공격은 10틱");
    }

    @Test
    void straightSwordAtDex40AveragesTenPointSeven() {
        MoveTiming.Base ss = new MoveTiming.Base(4, 2, 7);
        double carry = 0;
        int sum = 0, n = 300;
        for (int i = 0; i < n; i++) {
            MoveTiming.Timed t = MoveTiming.time(ss, a(40), carry, R);
            assertEquals(3, t.s(), "4 / 1.22 = 3.28 → 3");
            assertEquals(2, t.a(), "판정 틱은 그대로");
            assertTrue(t.r() == 5 || t.r() == 6, "회복 5.74 → 5 또는 6: " + t.r());
            assertTrue(t.carry() >= 0 && t.carry() < 1);
            carry = t.carry();
            sum += t.cycle();
        }
        assertEquals(3 + 2 + 7 / 1.22, sum / (double) n, 0.01, "평균 10.74");
        assertEquals(10.7, sum / (double) n, 0.05);
    }

    @Test
    void fractionalCarryOrder() {
        // 직검 7 / 1.22 = 5.74: 올린 6 으로 하다가 더 쓴 몫 (0.26 씩) 이 1틱 차면 5
        MoveTiming.Base ss = new MoveTiming.Base(4, 2, 7);
        double carry = 0;
        int[] want = {6, 6, 6, 5};
        for (int w : want) {
            MoveTiming.Timed t = MoveTiming.time(ss, a(40), carry, R);
            assertEquals(w, t.r());
            carry = t.carry();
        }
        assertEquals(4 * (6 - 7 / 1.22) - 1, carry, 1e-9);
    }

    @Test
    void greatswordHeavy() {
        MoveTiming.Base gs = new MoveTiming.Base(13, 3, 16);
        double carry = 0, sumR = 0;
        int n = 200;
        for (int i = 0; i < n; i++) {
            MoveTiming.Timed t = MoveTiming.time(gs, a(40), carry, R);
            assertEquals(11, t.s(), "13 / 1.22 = 10.66 → 11");
            assertEquals(3, t.a());
            carry = t.carry();
            sumR += t.r();
        }
        assertEquals(13.1, sumR / n, 0.02, "회복 평균 13.1");
    }

    @Test
    void daggerHeavyAtDex40() {
        MoveTiming.Base dh = new MoveTiming.Base(6, 1, 10);
        double carry = 0, sumR = 0;
        for (int i = 0; i < 100; i++) {
            MoveTiming.Timed t = MoveTiming.time(dh, a(40), carry, R);
            assertEquals(5, t.s());
            carry = t.carry();
            sumR += t.r();
        }
        assertEquals(8.2, sumR / 100, 0.02);
    }

    @Test
    void floors() {
        MoveTiming.Timed t = MoveTiming.time(new MoveTiming.Base(1, 1, 3), a(99), 0, R);
        assertEquals(2, t.s(), "준비는 2틱 밑으로 가지 않는다");
        assertEquals(10, t.cycle(), "한 주기 10");
        MoveTiming.Timed u = MoveTiming.time(new MoveTiming.Base(9, 2, 4), a(99), 0, R);
        assertEquals(4, u.r(), "회복 4 / 1.3 = 3.1 → 최소 4");
        MoveTiming.Timed v = MoveTiming.time(new MoveTiming.Base(1, 1, 1), 1, 0, new MoveTiming.Rules(1, 0, 1));
        assertEquals(3, v.cycle(), "최소값은 설정을 따른다");
        assertEquals(MoveTiming.time(new MoveTiming.Base(4, 2, 7), 1, 0, R), MoveTiming.time(new MoveTiming.Base(4, 2, 7), Double.NaN, 0, R),
                "틀린 배율은 1");
    }

    @Test
    void swingTiers() {
        List<Integer> steps = List.of(10, 20, 30, 40, 60, 99);
        assertEquals(0, MoveTiming.tier(1, steps));
        assertEquals(0, MoveTiming.tier(19, steps));
        assertEquals(1, MoveTiming.tier(20, steps));
        assertEquals(3, MoveTiming.tier(40, steps));
        assertEquals(4, MoveTiming.tier(98, steps));
        assertEquals(5, MoveTiming.tier(99, steps));
        assertEquals(40, MoveTiming.tierDex(3, steps));
        assertEquals(99, MoveTiming.tierDex(9, steps), "넘으면 끝 단계");
        assertEquals(10, MoveTiming.tierDex(-1, steps));
        // 휘두르는 길이 = 준비 + 판정 (그 단계의 첫 민첩으로)
        assertEquals(6, MoveTiming.swingTicks(4, 2, a(10), 2), "직검 민첩 10: 4 + 2");
        assertEquals(5, MoveTiming.swingTicks(4, 2, a(40), 2), "직검 민첩 40: 3 + 2");
        assertEquals(4, MoveTiming.swingTicks(3, 1, a(30), 2), "단도 민첩 30: 3/1.17 = 2.56 → 3, + 1");
        assertEquals(3, MoveTiming.swingTicks(3, 1, a(40), 2), "단도 민첩 40: 2 + 1");
        assertEquals(10, MoveTiming.swingTicks(8, 2, a(10), 2), "대검 민첩 10");
    }
}
