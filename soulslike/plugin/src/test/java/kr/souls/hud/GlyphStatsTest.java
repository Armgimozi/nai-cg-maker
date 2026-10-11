package kr.souls.hud;

import kr.souls.TestFiles;
import org.bukkit.configuration.ConfigurationSection;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** glyphs.yml 의 값 글자 폭 (ui/Columns 의 오른쪽 맞춤): 글자 수와 폭 수가 같고, 끝의 빈칸이 잘리지 않는다. */
class GlyphStatsTest {

    @Test
    void decodeKeepsTrailingSpaceWhenAsked() {
        assertEquals("a→ ", Glyphs.decode("a\\u2192 ", false));
        assertEquals("a→", Glyphs.decode("a\\u2192 "));
    }

    @Test
    void statsCharsMatchWidths() {
        ConfigurationSection st = TestFiles.yaml("glyphs.yml").getConfigurationSection("stats");
        String chars = Glyphs.decode(st.getString("chars", ""), false);
        List<Integer> ws = st.getIntegerList("widths");
        assertEquals(ws.size(), chars.length(), "글자 " + chars.length() + "개, 폭 " + ws.size() + "개");
        int space = chars.indexOf(' '), arrow = chars.indexOf('→');
        assertTrue(space >= 0 && arrow >= 0, "빈칸과 → 는 값 글 (\"a → b\") 에 든다");
        assertTrue(ws.get(space) < 5, "빈칸 폭은 기본값 5 보다 좁다: " + ws.get(space));
    }
}
