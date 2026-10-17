package kr.labyrinth.village;

import static org.junit.jupiter.api.Assertions.assertEquals;

import kr.labyrinth.village.DistrictMeta.State;
import kr.labyrinth.village.DistrictPolicy.Remove;
import org.junit.jupiter.api.Test;

/**
 * {@code /labadmin village district remove <id> [force]} 판단 (0.3.7 review R9): 집 구역에 주인이 있으면 force 없이는 거절,
 * force = 모든 집 회수(맡긴 짐) → 백업이 있으면 되돌리기 · 없으면 기록만. 광산은 0.3.6.1 그대로.
 */
class DistrictRemoveRuleTest {

    @Test
    void homesWithOwnersNeedsForce() {
        assertEquals(Remove.REFUSE_OWNERS, DistrictPolicy.removeAction("homes", State.BUILT, true, 3, false));
        assertEquals(Remove.REFUSE_OWNERS, DistrictPolicy.removeAction("homes", State.BUILT, false, 1, false));
        assertEquals(Remove.RECLAIM_THEN_RESTORE, DistrictPolicy.removeAction("homes", State.BUILT, true, 3, true));
        assertEquals(Remove.RECLAIM_THEN_FORGET, DistrictPolicy.removeAction("homes", State.BUILT, false, 3, true));
    }

    @Test
    void homesWithoutOwners() {
        assertEquals(Remove.RESTORE, DistrictPolicy.removeAction("homes", State.BUILT, true, 0, false));
        assertEquals(Remove.RESTORE, DistrictPolicy.removeAction("homes", State.BUILT, true, 0, true), "force 라도 백업이 있으면 되돌린다");
        assertEquals(Remove.REFUSE, DistrictPolicy.removeAction("homes", State.BUILT, false, 0, false), "백업 없음");
        assertEquals(Remove.FORGET, DistrictPolicy.removeAction("homes", State.BUILT, false, 0, true));
        // 짓다 멈춘 것도 (짓기 전 백업으로)
        assertEquals(Remove.RESTORE, DistrictPolicy.removeAction("homes", State.BUILDING, true, 0, false));
    }

    @Test
    void mineKeeps0361Rules() {
        assertEquals(Remove.RESTORE, DistrictPolicy.removeAction("mine", State.BUILT, true, 0, false));
        assertEquals(Remove.REFUSE, DistrictPolicy.removeAction("mine", State.BUILT, false, 0, false));
        assertEquals(Remove.FORGET, DistrictPolicy.removeAction("mine", State.BUILT, true, 0, true), "광산 force = 기록만 (0.3.6.1)");
        assertEquals(Remove.FORGET, DistrictPolicy.removeAction("mine", State.BUILDING, false, 0, true));
        // 광산에는 주인 수가 없음 — 넘겨도 보지 않음
        assertEquals(Remove.RESTORE, DistrictPolicy.removeAction("mine", State.BUILT, true, 5, false));
    }

    @Test
    void nothingToRemove() {
        for (String id : new String[] {"mine", "homes"}) {
            assertEquals(Remove.REFUSE, DistrictPolicy.removeAction(id, null, true, 0, true), id + " 기록 없음");
            assertEquals(Remove.REFUSE, DistrictPolicy.removeAction(id, State.REMOVED, true, 0, true), id + " 이미 지움");
            assertEquals(Remove.REFUSE, DistrictPolicy.removeAction(id, State.REMOVED, true, 2, true));
        }
    }
}
