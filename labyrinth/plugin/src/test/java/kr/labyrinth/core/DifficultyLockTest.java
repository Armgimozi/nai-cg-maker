package kr.labyrinth.core;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.nio.file.Files;
import org.junit.jupiter.api.Test;

/** 한 번 정한 난이도는 바꿀 수 없다 (0.3.5.3). */
class DifficultyLockTest {

    @Test
    void decide() {
        assertEquals(DifficultyLock.Action.NONE, DifficultyLock.decide(null, "", false), "아직 안 정함");
        assertEquals(DifficultyLock.Action.ADOPT, DifficultyLock.decide(null, "hard", true), "예전 판에서 정해 둔 난이도는 잠금");
        assertEquals(DifficultyLock.Action.NONE, DifficultyLock.decide(null, "nope", false), "모르는 값은 잠그지 않음");
        assertEquals(DifficultyLock.Action.NONE, DifficultyLock.decide("hard", "hard", true));
        assertEquals(DifficultyLock.Action.NONE, DifficultyLock.decide("hard", " HARD ", true));
        assertEquals(DifficultyLock.Action.RESTORE, DifficultyLock.decide("hard", "easy", true), "config 를 고쳐도 되돌림");
        assertEquals(DifficultyLock.Action.RESTORE, DifficultyLock.decide("hard", "", false), "config 를 새로 덮어써도 되돌림");
    }

    @Test
    void fileRoundTrip() throws Exception {
        File dir = Files.createTempDirectory("lab-lock").toFile();
        assertNull(DifficultyLock.read(dir));
        DifficultyLock.write(dir, "nightmare", "tester");
        assertEquals("nightmare", DifficultyLock.read(dir));
        assertTrue(DifficultyLock.delete(dir));
        assertNull(DifficultyLock.read(dir));
        assertFalse(DifficultyLock.delete(dir));
    }
}
