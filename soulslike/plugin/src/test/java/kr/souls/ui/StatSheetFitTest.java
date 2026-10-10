package kr.souls.ui;

import kr.souls.TestFiles;
import kr.souls.combat.DamageCalc;
import kr.souls.hud.Glyphs;
import kr.souls.progression.Derived;
import kr.souls.progression.LoadTiers;
import kr.souls.progression.StatBlock;
import kr.souls.progression.StatCurves;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 능력치 표의 값 칸 (5.9, ui/Columns·StatSheet): 값이 열 폭을 넘으면 그 줄이 넓어져 모든 열이 어긋난다. "now → next" 가 열을 넘으면
 * 바뀐 값만 보인다 (Columns.change, 검토 right-column-no-overflow-fallback). 모든 능력치 99 와 아주 무거운 장비에서도 값이 칸 안에 든다.
 * 폭은 저장소의 glyphs.yml (팩이 잰 값 글자 폭) 으로 잰다.
 */
class StatSheetFitTest {
    @BeforeAll
    static void loadGlyphs() {
        Glyphs.load(TestFiles.yaml("glyphs.yml"), Logger.getLogger("test"));
    }

    /** 보이는 값 (빈칸 글자를 뺀 글) 과 그 폭. */
    private static String visible(Component c) {
        String s = PlainTextComponentSerializer.plainText().serialize(c);
        StringBuilder b = new StringBuilder();
        for (char ch : s.toCharArray()) if (ch < '' || ch > '') b.append(ch);
        return b.toString().strip();
    }

    @Test
    void changeKeepsArrowWhenItFits() {
        assertTrue(Columns.aligned(), "glyphs.yml 에 값 글자 폭과 빈칸 글자가 있다");
        assertEquals("1495 → 1500", visible(Columns.change("1495", "1500", Columns.VALUE)));
        assertEquals("400", visible(Columns.change("400", "400", Columns.VALUE)));
    }

    @Test
    void changeFallsBackToTheNextValueWhenTooWide() {
        String v = visible(Columns.change("12345.6", "12350.1", Columns.VALUE));
        assertEquals("12350.1", v);
        assertTrue(Columns.width(v) <= Columns.VALUE, v);
        assertEquals("999,999,999", visible(StatSheet.head("table.held", "999,999,998", "999,999,999").value()));
    }

    /** 모든 능력치 98 → 99, 장비 무게 999.9 (과적): 오른쪽 열의 값이 모두 칸 (64) 안에 든다. */
    @Test
    void maxedStatsStillFitTheRightColumn() {
        StatCurves c = StatCurves.defaults();
        LoadTiers tiers = LoadTiers.defaults();
        StatBlock s98 = new StatBlock(98, 98, 98, 98, 98, 98), s99 = new StatBlock(99, 99, 99, 99, 99, 99);
        DamageCalc.Arms big = new DamageCalc.Arms(250, 250);
        Derived a = Derived.of(s98, c, tiers, big, true, big, 999.9, 1.0);
        Derived b = Derived.of(s99, c, tiers, big, true, big, 999.9, 1.0);
        for (int row = 0; row < 6; row++) {
            String[] va = StatRows.values(row, a), vb = StatRows.values(row, b);
            for (int j = 0; j < 2; j++) {
                String v = visible(Columns.change(va[j], vb[j], Columns.VALUE));
                assertTrue(Columns.width(v) <= Columns.VALUE, "줄 " + row + " 값 " + j + ": " + v + " (" + Columns.width(v) + ")");
            }
        }
        String load = visible(StatRows.load(a, b));
        assertTrue(Columns.width(load) <= Columns.VALUE, "장비 중량 " + load + " (" + Columns.width(load) + ")");
    }
}
