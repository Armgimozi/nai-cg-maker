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
 * 무기 설명 칸의 수치 표 (9.7): 다크 소울 3 처럼 두 열, 칸마다 "이름 + 값" (값은 값 열 끝에 오른쪽 맞춤).
 * 이름 (lang 의 weapon.stat.*) 은 리소스팩이 그 언어의 이름 열 폭까지 빈칸 글자로 채워 두었다 (pack/typeset.py). 값은 숫자·등급이라
 * 두 언어 공통이고, 값 앞을 기본 글꼴의 빈칸 글자 (glyphs.yml 의 text_space_*) 로 채워 값 열 끝에 맞춘다. 값 글자의 진행 폭과 열
 * 폭은 팩을 만들 때 잰 glyphs.yml 의 stats 에 있다. 우리 글꼴의 진행 폭은 정수라 열이 픽셀까지 맞는다.
 * 줄: [공격력 (방패는 물리 흡수·안정성)][무게] / [근력·기량·기억 보정] / [필요 근력·기량·기억]. 홀수 칸이면 보정 줄 뒤를 비운다.
 */
final class StatTable {
    /** 값 글자색 (팔레트 뼈빛 bone2) */
    private static final TextColor VALUE = TextColor.color(0xd6cbb0);
    private static final int[] STEPS = {128, 64, 32, 16, 8, 4, 2, 1};

    private StatTable() {}

    static List<Component> lines(Weapons.Def d) {
        List<String[]> cells = new ArrayList<>();
        if (d.shield()) {
            cells.add(new String[] {"absorb", d.absorb() + "%"});
            cells.add(new String[] {"stability", String.valueOf(d.stability())});
        } else if (d.attack() > 0) {
            cells.add(new String[] {"attack", String.valueOf(d.attack())});
        }
        cells.add(new String[] {"weight", String.format(Locale.ROOT, "%.1f", d.weight())});
        for (String s : Weapons.STATS) {
            Object v = d.scaling().get(s);
            if (v != null) cells.add(new String[] {"bonus_" + s, String.valueOf(v)});
        }
        if (cells.size() % 2 == 1) cells.add(null);
        for (String s : Weapons.STATS) {
            Object v = d.requires().get(s);
            if (v != null) cells.add(new String[] {"need_" + s, String.valueOf(v)});
        }
        Glyphs.Stats st = Glyphs.stats();
        List<Component> out = new ArrayList<>();
        for (int i = 0; i < cells.size(); i += 2) {
            TextComponent.Builder row = Component.text();
            row.append(cell(cells.get(i), st));
            if (i + 1 < cells.size() && cells.get(i + 1) != null) {
                row.append(Component.text(st == null ? "   " : spaces(st.colGap())));
                row.append(cell(cells.get(i + 1), st));
            }
            out.add(row.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE));
        }
        return out;
    }

    /** 수치와 설명 사이 실선 (souls:hud 그림 글자 lore_rule). 그림 글자가 없으면 (옛 팩) 빈 줄. */
    static Component rule() {
        Glyphs.Glyph g = Glyphs.get("lore_rule");
        return g == null ? Component.empty() : g.component().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    private static Component cell(String[] c, Glyphs.Stats st) {
        if (c == null) return Component.empty();
        return Component.text()
                .append(Lang.c("weapon.stat." + c[0])) // lang-dyn: weapon.stat.*
                .append(Component.text(st == null ? " " : spaces(st.valueCol() - width(c[1], st))))
                .append(Component.text(c[1]).color(VALUE))
                .build();
    }

    private static int width(String value, Glyphs.Stats st) {
        int w = 0;
        for (char ch : value.toCharArray()) w += st.widths().getOrDefault(ch, 5);
        return w;
    }

    /** 폭 px (0 이상) 를 기본 글꼴의 빈칸 글자로 (128, 64 … 1). 글자가 없으면 (옛 팩) 보통 빈칸 하나. */
    private static String spaces(int px) {
        StringBuilder b = new StringBuilder();
        int left = Math.max(0, px);
        for (int step : STEPS) {
            Glyphs.Glyph g = Glyphs.get("text_space_pos" + step);
            if (g == null) return " ";
            while (left >= step) {
                b.append(g.ch());
                left -= step;
            }
        }
        return b.toString();
    }
}
