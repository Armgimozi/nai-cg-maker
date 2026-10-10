package kr.souls.item;

import kr.souls.Lang;
import kr.souls.hud.Glyphs;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * 무기 설명 칸의 수치 표 (9.7): 한 줄, 두 칸 "이름 + 값" (값은 값 열 끝에 오른쪽 맞춤). 장비에는 능력치 보정도 요구 능력치도 없어
 * (DECISIONS 2026-10-10) 칸은 늘 둘이다: 제 값 하나 (무기·활·패링 단검은 공격력, 방패는 막기, 촉매는 술법 세기) 와 무게.
 * 패링 창은 다크 소울처럼 보이지 않는다 (왼손 물건의 분류로 정해진다, combat.parry.windows).
 * 이름 (lang 의 weapon.stat.*) 은 리소스팩이 그 언어의 이름 열 폭까지 빈칸 글자로 채워 두었다 (pack/typeset.py). 값은 숫자라
 * 두 언어 공통이고, 값 앞을 기본 글꼴의 빈칸 글자 (glyphs.yml 의 text_space_*) 로 채워 값 열 끝에 맞춘다. 값 글자의 진행 폭과 열
 * 폭은 팩을 만들 때 잰 glyphs.yml 의 stats 에 있다. 우리 글꼴의 진행 폭은 정수라 열이 픽셀까지 맞는다.
 * 팩의 pack/typeset.py stat_cells 가 같은 칸을 셈해 무기마다 설명 칸 폭을 잡는다 (둘을 함께 고친다).
 */
final class StatTable {
    /** 값 글자색 (팔레트 뼈빛 bone2) */
    private static final TextColor VALUE = TextColor.color(0xd6cbb0);

    private StatTable() {}

    /** 칸 [이름 열쇠 끝 조각, 값] 들: 제 값 하나 (있으면) 와 무게. */
    static List<String[]> cells(Weapons.Def d) {
        List<String[]> cells = new ArrayList<>();
        if (d.shield()) cells.add(new String[] {"guard", String.valueOf(d.guard())});
        else if (d.spell() > 0) cells.add(new String[] {"spell", String.valueOf(d.spell())});
        else if (d.attack() > 0) cells.add(new String[] {"attack", String.valueOf(d.attack())});
        cells.add(new String[] {"weight", String.format(Locale.ROOT, "%.1f", d.weight())});
        return cells;
    }

    static List<Component> lines(Weapons.Def d) {
        List<String[]> cells = cells(d);
        Glyphs.Stats st = Glyphs.stats();
        List<Component> out = new ArrayList<>();
        for (int i = 0; i < cells.size(); i += 2) {
            TextComponent.Builder row = Component.text();
            row.append(cell(cells.get(i), st));
            if (i + 1 < cells.size()) {
                row.append(Component.text(st == null ? "   " : Glyphs.textSpaces(st.colGap())));
                row.append(cell(cells.get(i + 1), st));
            }
            out.add(row.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE));
        }
        return out;
    }

    /**
     * 수치와 설명 사이 실선: 번역 열쇠 weapon.rule.&lt;무기 id&gt; (팩의 언어 파일에만 있다). 리소스팩이 무기마다 기본 글꼴의 실선 그림
     * 글자로 짜 두었다 (pack/typeset.py: 그 언어에서 그 무기 설명 칸의 글 열 폭만큼, 이름 밑 금실과 같은 색·굵기·금빛 마름모의
     * 끊김 없는 한 줄. 그래서 칸이 무기마다 제 글에 맞는 폭이다). 팩이 없으면 weapon.rule 의 대체 글 (줄표).
     */
    static Component rule(Weapons.Def d) {
        return Lang.variant("weapon.rule", d.id());
    }

    private static Component cell(String[] c, Glyphs.Stats st) {
        return Component.text()
                .append(Lang.c("weapon.stat." + c[0])) // lang-dyn: weapon.stat.*
                .append(Component.text(st == null ? " " : Glyphs.textSpaces(st.valueCol() - width(c[1], st))))
                .append(Component.text(c[1]).color(VALUE))
                .build();
    }

    private static int width(String value, Glyphs.Stats st) {
        int w = 0;
        for (char ch : value.toCharArray()) w += st.widths().getOrDefault(ch, 5);
        return w;
    }
}
