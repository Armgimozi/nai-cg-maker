package kr.souls.combat;

import kr.souls.Config;
import kr.souls.TestFiles;
import kr.souls.item.ItemFactory;
import kr.souls.progression.StatCurves;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * M1 P1a (R13, 9.8 의 지문) + 2026-10-11 휘두름 잠금: 아이템의 휘두르는 길이 D = 2 × Cmin − swing-margin. Cmin 은 그 분류의 약공격 단들
 * 가운데 가장 짧은 한 주기를 민첩 단계 (combat.moves.swing-tiers) 의 가장 빠른 민첩으로 셈한 것 (MoveRunner.swing 과 같은 셈).
 * 단계가 바뀔 때만 아이템을 다시 쓴다. 값은 plan 의 표 (margin 2: 도끼 0단계 32, 단도 18, 대검 0단계 38 …) 에서 검토 뒤의 기본 margin 3
 * 으로 하나씩 짧다 (도끼 0단계 31, 단도 17, 대검 0단계 37 …: 가장 짧은 주기에서도 서버·클라이언트의 휘두름 규칙에 한 틱이 남는다).
 */
class SwingTierTest {
    private static final Config CFG = new Config(TestFiles.yaml("config.yml"));
    private static final StatCurves C = CFG.stats;
    private static final Moveset M = Moveset.parse(TestFiles.yaml("content/moves.yml"), 1.2);
    private static final CombatTuning.Moves MV = CFG.tuning.moves;
    private static final List<Integer> STEPS = MV.swingTiers();
    private static final MoveTiming.Rules R = new MoveTiming.Rules(MV.minStartup(), MV.minRecovery(), MV.minCycle());

    private static List<MoveTiming.Base> lights(String cls) {
        List<MoveTiming.Base> out = new ArrayList<>();
        for (Moveset.Step s : M.of(cls).light()) out.add(s.base());
        return out;
    }

    /** MoveRunner.swing 과 같은 셈: 분류·단계의 휘두르는 길이. */
    private static int lockTier(String cls, int tier) {
        return MoveTiming.lockTicks(lights(cls), DamageCalc.attackSpeed(C, MoveTiming.fastestDex(tier, STEPS)), R, MV.swingMargin());
    }

    private static int lock(String cls, int dex) {
        return lockTier(cls, MoveTiming.tier(dex, STEPS));
    }

    @Test
    void defaultSteps() {
        assertEquals(List.of(10, 20, 30, 40, 60, 99), STEPS);
        assertEquals(3, MV.swingMargin());
        assertEquals(19, MoveTiming.fastestDex(0, STEPS));
        assertEquals(29, MoveTiming.fastestDex(1, STEPS));
        assertEquals(59, MoveTiming.fastestDex(3, STEPS));
        assertEquals(98, MoveTiming.fastestDex(4, STEPS));
        assertEquals(99, MoveTiming.fastestDex(5, STEPS), "끝 단계는 99");
        assertEquals(99, MoveTiming.fastestDex(9, STEPS));
        assertEquals(19, MoveTiming.fastestDex(-1, STEPS));
    }

    @Test
    void sameTierSameSwing() {
        // 민첩 10~19 는 한 단계: 아이템을 다시 쓰지 않는다 (민첩 15 의 궁수도 민첩 10 의 길이)
        for (String cls : M.all().keySet()) assertEquals(lock(cls, 10), lock(cls, 19), cls);
        assertEquals(lock("straight_sword", 40), lock("straight_sword", 59));
    }

    /** plan 의 표 − 1 (margin 3, 단계 0..5 = 민첩 10/20/30/40/60/99). */
    @Test
    void lockTableByClassAndTier() {
        Map<String, int[]> want = new LinkedHashMap<>();
        want.put("dagger", new int[]{17, 17, 17, 17, 17, 17});
        want.put("straight_sword", new int[]{21, 19, 17, 17, 17, 17});
        want.put("curved_sword", new int[]{19, 19, 17, 17, 17, 17});
        want.put("greatsword", new int[]{37, 35, 33, 31, 31, 31});
        want.put("ultra_greatsword", new int[]{51, 47, 47, 45, 43, 43});
        want.put("axe", new int[]{31, 27, 27, 25, 25, 25});
        want.put("hammer", new int[]{31, 27, 27, 25, 25, 25});
        want.put("spear", new int[]{21, 17, 17, 17, 17, 17});
        want.put("halberd", new int[]{33, 31, 31, 29, 27, 27});
        want.put("parrying_dagger", new int[]{17, 17, 17, 17, 17, 17});
        for (Map.Entry<String, int[]> e : want.entrySet()) {
            for (int t = 0; t < 6; t++) assertEquals(e.getValue()[t], lockTier(e.getKey(), t), e.getKey() + " 단계 " + t);
        }
        assertEquals(want.keySet(), M.all().keySet(), "moves.yml 의 분류가 모두 표에 있다");
        // 궁수의 손도끼 (도끼, 민첩 15 = 0단계) 와 빈털터리의 곤봉 (망치, 민첩 10)
        assertEquals(31, lock("axe", 15));
        assertEquals(31, lock("hammer", 10));
        assertEquals(25, lock("hammer", 40), "민첩 40 (3단계, 가장 빠른 민첩 59)");
    }

    /**
     * 잠금의 뜻: 한 단계 안의 어느 민첩에서도 이어지는 약공격의 한 주기 (모아 둔 몫으로 한 틱 짧아진 것까지) 는 D/2 + 1 이상이다. 그래야
     * 다음 동작의 시작에 서버가 휘두를 수 있다 (Swings.free: 서버 쪽 휘두름 규칙). 2026-10-11 검토 (margin 3): 한 틱 일찍이어도 된다.
     * 클라이언트도 같은 규칙이라, 서버 휘두름 패킷이 한 클라이언트 틱 일찍 닿아도 그 내려치기를 버리지 않는다.
     */
    @Test
    void everyLightCycleLetsTheServerSwing() {
        for (String cls : M.all().keySet()) {
            for (int dex = 1; dex <= 99; dex++) {
                int d = lock(cls, dex);
                double a = DamageCalc.attackSpeed(C, dex);
                double carry = 0;
                for (int i = 0; i < 60; i++) {
                    MoveTiming.Timed t = MoveTiming.time(M.of(cls).light(i).base(), a, carry, R);
                    carry = t.carry();
                    assertTrue(Swings.free(1000 + t.cycle() - 1, 1000, d), cls + " 민첩 " + dex + " 주기 " + t.cycle() + " D " + d + " (한 틱 남아야)");
                }
            }
        }
    }

    /**
     * margin 0 (D = 2C) 은 가장 짧은 주기에서 서버가 제 휘두름을 막는다. margin 2 (D 32) 는 꼭 맞아 남는 틱이 없다 (패킷이 한 클라이언트 틱
     * 일찍 닿으면 클라이언트가 막는다). margin 3 (D 31, 기본) 은 한 틱 남는다.
     */
    @Test
    void marginsOnTheShortestCycle() {
        double a = DamageCalc.attackSpeed(C, 19);
        int d0 = MoveTiming.lockTicks(lights("axe"), a, R, 0);
        assertEquals(34, d0);
        assertFalse(Swings.free(1017, 1000, d0), "17틱 주기에 D 34 는 서버가 제 휘두름을 막는다");
        int d2 = MoveTiming.lockTicks(lights("axe"), a, R, 2);
        assertEquals(32, d2);
        assertTrue(Swings.free(1017, 1000, d2));
        assertFalse(Swings.free(1016, 1000, d2), "margin 2: 한 틱 일찍이면 막힌다");
        int d3 = MoveTiming.lockTicks(lights("axe"), a, R, 3);
        assertEquals(31, d3);
        assertTrue(Swings.free(1016, 1000, d3), "margin 3: 한 틱 일찍이어도 된다");
        assertFalse(Swings.free(1015, 1000, d3));
    }

    @Test
    void lockFloorsAndRules() {
        // 회복은 내림 (모아 둔 몫으로 한 틱 짧아질 수 있다): 도끼 민첩 19 = 6 + 2 + floor(10 / 1.09 = 9.17) = 17
        assertEquals(32, MoveTiming.lockTicks(List.of(new MoveTiming.Base(6, 2, 10)), 1.09, MoveTiming.Rules.DEFAULT, 2));
        // 가장 짧은 단을 쓴다
        assertEquals(2 * 12 - 2, MoveTiming.lockTicks(List.of(new MoveTiming.Base(5, 2, 8), new MoveTiming.Base(4, 2, 6)), 1, MoveTiming.Rules.DEFAULT, 2));
        // 한 주기는 min-cycle 밑으로 가지 않는다
        assertEquals(18, MoveTiming.lockTicks(List.of(new MoveTiming.Base(1, 1, 1)), 1.3, MoveTiming.Rules.DEFAULT, 2));
        assertEquals(18, MoveTiming.lockTicks(List.of(), 1, MoveTiming.Rules.DEFAULT, 2), "단이 없으면 min-cycle");
        assertEquals(2, MoveTiming.lockTicks(List.of(new MoveTiming.Base(1, 1, 1)), 1, new MoveTiming.Rules(1, 0, 1), 40), "2 밑으로 가지 않는다");
        assertEquals(MoveTiming.lockTicks(List.of(new MoveTiming.Base(6, 2, 10)), 1, MoveTiming.Rules.DEFAULT, 2),
                MoveTiming.lockTicks(List.of(new MoveTiming.Base(6, 2, 10)), Double.NaN, MoveTiming.Rules.DEFAULT, 2), "틀린 배율은 1");
    }

    /** 서버 쪽 휘두름 규칙 (LivingEntity.swing: 휘두르는 중이면 swingTime ≥ D/2): 우리 틱으로 D/2 + 1. */
    @Test
    void serverSwingRule() {
        long n = CombatState.NEVER;
        assertTrue(Swings.free(5, n, 32), "휘두른 적이 없으면 된다");
        assertFalse(Swings.free(116, 100, 32));
        assertTrue(Swings.free(117, 100, 32), "32 / 2 + 1 = 17");
        assertFalse(Swings.free(103, 100, 6));
        assertTrue(Swings.free(104, 100, 6), "길이가 없는 아이템 (바닐라 6): 4틱");
        assertTrue(Swings.free(118, 100, 33), "홀수는 내림: 33 / 2 + 1 = 17");
        assertFalse(Swings.free(100, 100, 1), "같은 틱에는 두 번 휘두르지 않는다");
    }

    /** ItemFactory.swingStale (2026-10-11): 판·단계만이 아니라 붙은 휘두르기·사거리도 지금 셈과 견준다. */
    @Test
    void swingStaleSeesTheActualSwing() {
        int fmt = ItemFactory.WEAPON_FMT;
        assertEquals(3, fmt);
        ItemFactory.SwingSpec want = new ItemFactory.SwingSpec(false, 32, 2.9f);
        assertFalse(ItemFactory.swingStale(fmt, 0, 0, want, new ItemFactory.SwingSpec(false, 32, 2.9f)), "같으면 그대로");
        assertTrue(ItemFactory.swingStale(fmt, 0, 0, want, new ItemFactory.SwingSpec(false, 18, 2.9f)), "길이가 틀리면 (무기 판 2 의 18) 다시 만든다");
        assertTrue(ItemFactory.swingStale(fmt, 0, 0, want, new ItemFactory.SwingSpec(false, 8, 2.9f)), "무기 판 1 의 8");
        assertTrue(ItemFactory.swingStale(fmt, 0, 0, want, new ItemFactory.SwingSpec(true, 32, 2.9f)), "종류 (stab) 가 틀리면");
        assertTrue(ItemFactory.swingStale(fmt, 0, 0, want, new ItemFactory.SwingSpec(false, 32, 3.0f)), "사거리가 틀리면");
        assertTrue(ItemFactory.swingStale(fmt, 0, 0, want, null), "휘두르기·사거리가 없거나 우리 꼴이 아니면");
        assertTrue(ItemFactory.swingStale(fmt, 1, 0, want, new ItemFactory.SwingSpec(false, 32, 2.9f)), "단계가 다르면");
        assertTrue(ItemFactory.swingStale(2, 0, 0, want, new ItemFactory.SwingSpec(false, 32, 2.9f)), "판이 낮으면");
        assertFalse(ItemFactory.swingStale(fmt, -1, 0, null, null), "근접 무기가 아니면 판만 본다");
        assertTrue(ItemFactory.swingStale(1, -1, 0, null, null));
    }
}
