package kr.labyrinth.dungeon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.dungeon.treasure.VaultKeys;
import org.junit.jupiter.api.Test;

/** run id — 재시작하면 번호가 0부터 다시 세져도 세션 토큰이 달라 예전 금고 열쇠가 새 공략 금고를 못 연다. */
class RunIdTest {

    @Test
    void restartDoesNotReuseRunId() {
        long before = 1_760_000_000_000L, after = before + 60_000;
        String old = DungeonManager.runId(1, 0, DungeonManager.sessionToken(before));
        String now = DungeonManager.runId(1, 0, DungeonManager.sessionToken(after));
        assertNotEquals(old, now, "재시작 뒤 첫 공략(r1s0)도 id 가 달라야 한다");
        assertFalse(VaultKeys.matches(VaultKeys.tag(old, 5), now, 5), "재시작 전 열쇠로 새 공략 금고를 못 연다");
        assertTrue(VaultKeys.matches(VaultKeys.tag(now, 5), now, 5));
        assertEquals(5, VaultKeys.floorOf(VaultKeys.tag(now, 5)));
    }

    @Test
    void runIdIsCommandWord() {
        String id = DungeonManager.runId(12, 3, DungeonManager.sessionToken(System.currentTimeMillis()));
        assertTrue(id.startsWith("r12s3-"), id);
        // /labadmin endinstance <id> (StringArgumentType.word) 로 쓸 수 있고, 열쇠 새김 구분자 '#' 이 없다
        assertTrue(id.matches("[0-9A-Za-z-]+"), id);
    }
}
