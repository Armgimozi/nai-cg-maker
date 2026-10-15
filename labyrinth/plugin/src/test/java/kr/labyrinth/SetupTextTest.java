package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Settings;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 초기 설정 창·난이도 변경 메시지의 배율 안내 — 기본은 숫자 한 벌, 직접 적은 층 램프가 있을 때만 1층 값과 원래 값을 함께. */
class SetupTextTest {

    @Test
    void bundledDifficultiesShowOneNumberSet() throws Exception {
        YamlConfiguration jar = new YamlConfiguration();
        jar.load(new java.io.File("src/main/resources/config.yml"));
        Settings s = new Settings(jar);
        Difficulty nm = s.difficulty("nightmare");
        assertFalse(nm.rampsAtFloor1());
        assertEquals("HP ×1.8·피해 ×1.6", nm.hpDamageText());
        assertEquals("×0.85", nm.telegraphText());
        assertEquals("HP ×1.4·피해 ×1.3", s.difficulty("hard").hpDamageText());
        assertEquals("×0.9", s.difficulty("hard").telegraphText());

        Difficulty normal = s.difficulty("normal");
        assertFalse(normal.rampsAtFloor1());
        assertEquals("HP ×1.0·피해 ×1.0", normal.hpDamageText());
        assertEquals("×1.0", normal.telegraphText());
        assertEquals("HP ×0.7·피해 ×0.6", s.difficulty("easy").hpDamageText());
        for (Difficulty d : s.difficulties().values()) assertFalse(d.hpDamageText().contains("층"), d.id());

        // 0.3.2 묶음을 그대로 둔 서버도 한 벌
        Settings old = new Settings(yaml("""
                difficulties:
                  nightmare: {name: "악몽", hp: 2.4, damage: 2.0, drop: 1.8, xp: 1.7, telegraph: 0.7,
                              ramp: {from_floor: 1, full_floor: 6, start: {hp: 1.8, damage: 1.6, telegraph: 0.85}}}
                """));
        assertEquals("HP ×1.8·피해 ×1.6", old.difficulty("nightmare").hpDamageText());
        assertEquals("×0.85", old.difficulty("nightmare").telegraphText());
    }

    @Test
    void handWrittenRampShowsFloorOneAndFullValues() throws Exception {
        Settings s = new Settings(yaml("""
                difficulties:
                  nightmare: {hp: 1.8, damage: 1.6, telegraph: 0.85, ramp: {from_floor: 1, full_floor: 5, start: {hp: 1.5, damage: 1.3, telegraph: 0.95}}}
                  hard: {hp: 1.4, damage: 1.3, telegraph: 0.9, ramp: {from_floor: 1, full_floor: 4, start: {hp: 1.2, damage: 1.3, telegraph: 0.9}}}
                """));
        Difficulty nm = s.difficulty("nightmare");
        assertTrue(nm.rampsAtFloor1());
        assertEquals("1층 HP ×1.5·피해 ×1.3 → 5층부터 ×1.8·×1.6", nm.hpDamageText());
        assertEquals("×0.95 → 5층부터 ×0.85", nm.telegraphText());
        // 경고 시간은 램프하지 않는 램프
        assertEquals("1층 HP ×1.2·피해 ×1.3 → 4층부터 ×1.4·×1.3", s.difficulty("hard").hpDamageText());
        assertEquals("×0.9", s.difficulty("hard").telegraphText());
    }

    private static YamlConfiguration yaml(String text) throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(text);
        return y;
    }

    @Test
    void multFormat() {
        assertEquals("2.0", Difficulty.mult(2.0));
        assertEquals("1.15", Difficulty.mult(1.15));
        assertEquals("0.7", Difficulty.mult(0.7));
        assertEquals("1.33", Difficulty.mult(1.3333));
    }
}
