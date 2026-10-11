package kr.souls.combat;

import kr.souls.Config;
import kr.souls.TestFiles;
import kr.souls.progression.StatCurves;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * M1 P1a (R13, 9.8 의 지문): 아이템의 휘두르는 길이는 민첩 단계 (combat.moves.swing-tiers) 의 첫 값으로 셈한 약공격 1단의 준비 + 판정.
 * 단계가 바뀔 때만 아이템을 다시 쓴다.
 */
class SwingTierTest {
    private static final Config CFG = new Config(TestFiles.yaml("config.yml"));
    private static final StatCurves C = CFG.stats;
    private static final Moveset M = Moveset.parse(TestFiles.yaml("content/moves.yml"), 1.2);
    private static final List<Integer> STEPS = CFG.tuning.moves.swingTiers();

    private static int ticks(String cls, int dex) {
        Moveset.Step l1 = M.of(cls).light(0);
        int tier = MoveTiming.tier(dex, STEPS);
        return MoveTiming.swingTicks(l1.s(), l1.a(), DamageCalc.attackSpeed(C, MoveTiming.tierDex(tier, STEPS)), CFG.tuning.moves.minStartup());
    }

    @Test
    void defaultSteps() {
        assertEquals(List.of(10, 20, 30, 40, 60, 99), STEPS);
    }

    @Test
    void sameTierSameSwing() {
        // 민첩 10~19 는 한 단계: 아이템을 다시 쓰지 않는다 (민첩 15 의 도적도 민첩 10 의 길이)
        for (String cls : M.all().keySet()) assertEquals(ticks(cls, 10), ticks(cls, 19), cls);
        assertEquals(ticks("straight_sword", 40), ticks("straight_sword", 59));
    }

    @Test
    void lengthsByClassAndTier() {
        assertEquals(6, ticks("straight_sword", 10), "4 + 2 (바닐라 기본 6 과 같다)");
        assertEquals(5, ticks("straight_sword", 40), "3 + 2");
        assertEquals(4, ticks("dagger", 10));
        assertEquals(3, ticks("dagger", 40));
        assertEquals(10, ticks("greatsword", 10));
        assertEquals(9, ticks("greatsword", 20), "8 / 1.1 = 7.3 → 7, + 2");
        assertEquals(8, ticks("hammer", 10));
        assertEquals(5, ticks("spear", 10));
        assertEquals(9, ticks("halberd", 10));
        assertEquals(14, ticks("ultra_greatsword", 10));
    }
}
