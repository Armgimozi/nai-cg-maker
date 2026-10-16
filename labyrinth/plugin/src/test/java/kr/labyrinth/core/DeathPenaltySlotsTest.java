package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import java.util.Set;
import kr.labyrinth.core.DeathPenaltyRules.Config;
import org.junit.jupiter.api.Test;

/** 검토 반영 (0.3.6.1 통합): slots_max 만 적으면 그 값이 상한 — 기본 slots_min 2 가 1 을 2 로 끌어올리지 않게. */
class DeathPenaltySlotsTest {

    private static Config read(String yaml) {
        return Config.read(WildConfigTest.yaml(yaml));
    }

    @Test
    void slotsMaxAloneIsTheCap() {
        Config c = read("death:\n  penalty:\n    dungeon_item_loss:\n      slots_max: 1\n");
        assertEquals(1, c.slotsMin());
        assertEquals(1, c.slotsMax());
    }

    @Test
    void anExplicitMinStillWins() {
        // 둘 다 적었는데 min > max 면 예전처럼 min (DeathPenaltyRulesTest.slotCountsAreClamped)
        Config c = read("death:\n  penalty:\n    dungeon_item_loss:\n      slots_min: 3\n      slots_max: 2\n");
        assertEquals(3, c.slotsMin());
        assertEquals(3, c.slotsMax());
        Config big = read("death:\n  penalty:\n    dungeon_item_loss:\n      slots_max: 5\n");
        assertEquals(2, big.slotsMin(), "slots_max 를 올리기만 하면 min 은 기본 2");
        assertEquals(5, big.slotsMax());
    }

    @Test
    void usualValuesUnchanged() {
        assertEquals(new Config(true, true, 2, 3, Set.of()), read("death:\n  penalty:\n    xp_progress_reset: true\n"));
        Config c = read("death:\n  penalty:\n    dungeon_item_loss:\n      slots_min: 1\n      slots_max: 2\n      safe_items: [return_scroll]\n");
        assertEquals(1, c.slotsMin());
        assertEquals(2, c.slotsMax());
        assertEquals(Set.of("return_scroll"), c.safeItems());
        Config zero = read("death:\n  penalty:\n    dungeon_item_loss:\n      slots_max: 0\n");
        assertEquals(0, zero.slotsMax());
        assertFalse(DeathPenaltyRules.plan(zero, DeathPenaltyRules.Where.DUNGEON_RUN, false).destroySlots(), "0칸 = 물건 안 잃음");
    }

    @Test
    void misplacedKeysAreIgnoredSoTheReadmeShowsTheBlock() {
        // README 가 dungeon_item_loss: 블록을 그대로 보여 주는 까닭: penalty: 바로 아래에 적으면 읽지 않는다
        Config c = read("death:\n  penalty:\n    safe_items: [return_scroll]\n    slots_max: 1\n");
        assertEquals(Config.DEFAULT, c);
    }
}
