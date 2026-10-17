package kr.labyrinth.data;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.util.UUID;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6.2 리뷰: 나갈 때(싸우는 중 끊김 페널티 뒤) 뜬 스냅샷을 파일에 다 쓰기 전에 다시 들어오면
 * 파일의 예전 값(잃기 전 골드·경험치)이 아니라 그 스냅샷을 읽어야 한다.
 */
class PendingWritesTest {

    private static final UUID VIC = new UUID(3, 4);

    @Test
    void newestUnwrittenSnapshotWinsUntilItIsWritten() {
        PendingWrites w = new PendingWrites();
        assertNull(w.get(VIC), "맡긴 것 없음 = 파일이 최신");
        w.put(VIC, "gold: 85691\n");        // 끊김 페널티 뒤 나갈 때 스냅샷
        assertEquals("gold: 85691\n", w.get(VIC), "쓰기 전에 다시 들어옴 → 파일(100000) 대신 이것");
        w.done(VIC, "gold: 85691\n");
        assertNull(w.get(VIC), "다 씀 → 파일을 읽음");
    }

    @Test
    void anOlderWriteFinishingDoesNotDropANewerSnapshot() {
        PendingWrites w = new PendingWrites();
        w.put(VIC, "gold: 100000\n");      // 오프라인 관리 명령 (saveOffline)
        w.put(VIC, "gold: 85691\n");       // 그 뒤 나감
        w.done(VIC, "gold: 100000\n");     // 앞 것을 다 씀 — 뒤 것은 아직
        assertEquals("gold: 85691\n", w.get(VIC));
        w.done(VIC, "gold: 85691\n");
        assertNull(w.get(VIC));
    }
}
