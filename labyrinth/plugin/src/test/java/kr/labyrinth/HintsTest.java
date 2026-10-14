package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Hints;
import kr.labyrinth.core.Text;
import org.junit.jupiter.api.Test;

/** 점진 힌트 단계 계산 (GDD "보스 문구 규칙 · 점진 힌트"). */
class HintsTest {

    private static final Hints.Config DEF = Hints.Config.DEFAULT;

    @Test
    void progressiveLevelsFollowThresholds() {
        // 0~1회 없음, 2회 흐릿, 4회 조금 분명, 6회 거의 정답
        int[] expected = {0, 0, 1, 1, 2, 2, 3, 3, 3, 3};
        for (int f = 0; f < expected.length; f++) assertEquals(expected[f], Hints.level(DEF, f), "실패 " + f + "회");
        assertEquals(3, Hints.level(DEF, 1000));
        assertEquals(0, Hints.level(DEF, -3));
    }

    @Test
    void modesNoneAndFull() {
        Hints.Config none = Hints.Config.of("none", List.of(2, 4, 6));
        Hints.Config full = Hints.Config.of("FULL", List.of(2, 4, 6));
        for (int f = 0; f < 10; f++) {
            assertEquals(0, Hints.level(none, f));
            assertEquals(3, Hints.level(full, f));
        }
        assertEquals(Hints.Mode.PROGRESSIVE, Hints.Mode.parse("이상한 값"));
        assertEquals(Hints.Mode.PROGRESSIVE, Hints.Mode.parse(null));
        assertEquals(Hints.Mode.NONE, Hints.Mode.parse(" None "));
    }

    @Test
    void customThresholdsAreSortedAndClamped() {
        Hints.Config c = Hints.Config.of("progressive", List.of(5, 1, 3, 0));
        assertArrayEquals(new int[] {1, 1, 3, 5}, c.thresholds());
        assertEquals(4, c.maxLevel());
        assertEquals(2, Hints.level(c, 1));
        assertEquals(3, Hints.level(c, 4));
        assertEquals(Hints.Config.DEFAULT, Hints.Config.of("progressive", List.of()));
        assertEquals(Hints.Config.DEFAULT, Hints.Config.of(null, null));
    }

    @Test
    void clueForLevel() {
        List<String> clues = List.of("흐릿", "분명", "정답");
        assertNull(Hints.clue(clues, 0));
        assertEquals("흐릿", Hints.clue(clues, 1));
        assertEquals("분명", Hints.clue(clues, 2));
        assertEquals("정답", Hints.clue(clues, 3));
        assertEquals("정답", Hints.clue(clues, 4), "단계가 단서 수보다 많으면 마지막 단서");
        assertEquals("하나", Hints.clue(List.of("하나"), 2));
        assertNull(Hints.clue(List.of(), 3));
        assertNull(Hints.clue(null, 3));
    }

    @Test
    void failuresFromExtAndPartyMax() {
        String key = Hints.bossKey("floor01_moss_warden");
        Map<String, Object> a = new HashMap<>();
        Map<String, Object> b = new HashMap<>();
        Map<String, Object> c = new HashMap<>();
        a.put(Hints.extKey(key), 1);
        b.put(Hints.extKey(key), 5);
        c.put(Hints.extKey(key), "3");
        assertEquals(1, Hints.failures(a, key));
        assertEquals(3, Hints.failures(c, key));
        assertEquals(0, Hints.failures(new HashMap<>(), key));
        assertEquals(0, Hints.failures(a, Hints.gimmickKey("lever_sequence")));
        // 파티 기준 = 가장 많이 실패한 사람
        assertEquals(5, Hints.partyFailures(List.of(a, b, c), key));
        assertEquals(2, Hints.level(DEF, Hints.partyFailures(List.of(a, b, c), key)));
        assertEquals(0, Hints.partyFailures(List.of(), key));
    }

    @Test
    void floorOneToFiveBossesHaveThreeClues() {
        Content content = ContentLoader.load(Path.of("src/main/resources/content")).content();
        for (int f = 1; f <= 5; f++) {
            BossDef b = content.bossOfFloor(f);
            assertTrue(b != null, "지하 " + f + "층 보스");
            List<String> clues = Hints.bossClues(b);
            assertEquals(3, clues.size(), b.id() + " 단서 3단계");
            for (String s : clues) {
                assertFalse(s.isBlank());
                Text.mm(Hints.format(s)); // MiniMessage 로 읽혀야 한다
            }
            // 단서는 갈수록 길고 분명해진다 (마지막 = 거의 정답)
            assertTrue(clues.get(2).length() > clues.get(0).length(), b.id() + " 3단계가 1단계보다 자세해야 함");
        }
    }
}
