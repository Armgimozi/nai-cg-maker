package kr.souls.combat;

import kr.souls.Config;
import kr.souls.TestFiles;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;

/** M1 P1c: 구르기 공격 창 = [next + roll-attack.from, next + roll-attack.to] (구르기 시작에서 센 틱, 기본 config.yml). */
class RollAttackWindowTest {
    private static final Config C = new Config(TestFiles.yaml("config.yml"));

    private static long[] w(String kind) {
        CombatTuning.Moves m = C.tuning.moves;
        return MoveRunner.window(C.roll.kind(kind).next(), m.rollFrom(), m.rollTo());
    }

    @Test
    void lightRollIs9To16() {
        // DESIGN 2.3 의 표: 구르기 9~16틱째 좌클릭 = 구르기 공격
        assertArrayEquals(new long[]{9, 16}, w("light"));
    }

    @Test
    void otherKindsFollowNext() {
        assertArrayEquals(new long[]{11, 18}, w("medium"));
        assertArrayEquals(new long[]{15, 22}, w("heavy"));
        assertArrayEquals(new long[]{7, 14}, w("backstep"));
    }
}
