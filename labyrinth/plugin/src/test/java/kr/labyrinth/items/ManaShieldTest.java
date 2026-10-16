package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;

import kr.labyrinth.core.ArmorLooks;
import org.junit.jupiter.api.Test;

/** 천 4부위 마나 보호막 (look_spec §1.3): 받는 피해 20% 를 MP 로 (MP 1 = 피해 2), MP 20% 아래면 쉼. */
class ManaShieldTest {

    static final double EPS = 1e-9;
    static final ArmorLooks.ManaShield CFG = ArmorLooks.ManaShield.DEFAULT;

    @Test
    void absorbsTwentyPercentForHalfAsMuchMana() {
        ManaShield.Split s = ManaShield.split(100, 100, 100, CFG);
        assertEquals(20, s.absorbed(), EPS);
        assertEquals(10, s.mpCost(), EPS, "MP 비용 = 흡수 ÷ 2");
        assertEquals(80, s.hpDamage(), EPS);
    }

    @Test
    void restsBelowTwentyPercentMana() {
        assertEquals(100, ManaShield.split(100, 19, 100, CFG).hpDamage(), EPS);
        assertEquals(0, ManaShield.split(100, 20, 100, CFG).mpCost(), EPS, "딱 20% 면 쉼");
        assertEquals(0, ManaShield.split(100, 50, 0, CFG).mpCost(), EPS, "최대 MP 0");
    }

    @Test
    void justAboveTheLineOnlyWhatIsLeft() {
        ManaShield.Split s = ManaShield.split(100, 22, 100, CFG);
        assertEquals(2, s.mpCost(), EPS, "20% 까지 남은 2 만 쓴다");
        assertEquals(4, s.absorbed(), EPS);
        assertEquals(96, s.hpDamage(), EPS);
    }

    @Test
    void zeroDamageAndKnobs() {
        assertEquals(0, ManaShield.split(0, 100, 100, CFG).mpCost(), EPS);
        assertEquals(0, ManaShield.split(-5, 100, 100, CFG).hpDamage(), EPS);
        ManaShield.Split s = ManaShield.split(100, 100, 100, new ArmorLooks.ManaShield("마나 보호막", 0.15, 2.0, 0.2));
        assertEquals(85, s.hpDamage(), EPS, "손잡이 absorb 0.15");
    }
}
