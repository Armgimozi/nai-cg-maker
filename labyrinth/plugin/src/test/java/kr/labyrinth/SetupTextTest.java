package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Settings;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 초기 설정 창·난이도 변경 메시지의 배율 안내 — 층 램프가 있으면 1층 값과 원래 값을 함께 보여 준다. */
class SetupTextTest {

    @Test
    void rampedDifficultyShowsFloorOneAndFullValues() throws Exception {
        YamlConfiguration jar = new YamlConfiguration();
        jar.load(new java.io.File("src/main/resources/config.yml"));
        Settings s = new Settings(jar);
        Difficulty nm = s.difficulty("nightmare");
        assertTrue(nm.rampsAtFloor1());
        assertEquals("1층 HP ×1.8·피해 ×1.6 → 6층부터 ×2.4·×2.0", nm.hpDamageText());
        assertEquals("×0.85 → 6층부터 ×0.7", nm.telegraphText());
        assertEquals("1층 HP ×1.2·피해 ×1.15 → 4층부터 ×1.5·×1.4", s.difficulty("hard").hpDamageText());

        Difficulty normal = s.difficulty("normal");
        assertFalse(normal.rampsAtFloor1());
        assertEquals("HP ×1.0·피해 ×1.0", normal.hpDamageText());
        assertEquals("×1.0", normal.telegraphText());
        assertEquals("HP ×0.7·피해 ×0.6", s.difficulty("easy").hpDamageText());
    }

    @Test
    void multFormat() {
        assertEquals("2.0", Difficulty.mult(2.0));
        assertEquals("1.15", Difficulty.mult(1.15));
        assertEquals("0.7", Difficulty.mult(0.7));
        assertEquals("1.33", Difficulty.mult(1.3333));
    }
}
