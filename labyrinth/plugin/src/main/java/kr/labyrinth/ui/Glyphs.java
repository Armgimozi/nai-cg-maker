package kr.labyrinth.ui;

import kr.labyrinth.Services;
import kr.labyrinth.content.GlyphDef;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * UI 폰트 글리프 헬퍼 (glyphs.yml → 폰트 labyrinth:ui). 글리프가 아직 없으면 빈 컴포넌트 (안전).
 * 메뉴 배경: {@code Glyphs.menuTitle("gui_stats", Text.mm("스탯"))}.
 */
public final class Glyphs {

    public static final Key FONT = Key.key("labyrinth", "ui");

    private Glyphs() {}

    public static boolean has(String id) { return Services.get().content().glyphs().containsKey(id); }

    /** 글리프 한 글자 (흰색 = 텍스처 색 그대로). */
    public static Component glyph(String id) {
        GlyphDef g = Services.get().content().glyphs().get(id);
        if (g == null) return Component.empty();
        return Component.text(g.ch()).font(FONT).color(NamedTextColor.WHITE);
    }

    /**
     * 픽셀 단위 이동 (음수 = 왼쪽). glyphs.yml {@code spaces} 에 정의된 값들을 큰 것부터 조합한다.
     * 문자 규칙(생성기와의 계약, ARCHITECTURE §6): 공백 값 v 의 문자 = U+F800 + v (v ∈ [-1024, 255]).
     */
    public static Component space(int px) {
        if (px == 0) return Component.empty();
        var spaces = Services.get().content().spaces();
        StringBuilder sb = new StringBuilder();
        int remain = px;
        while (remain != 0) {
            int best = 0;
            for (int v : spaces.values()) {
                if (v != 0 && Integer.signum(v) == Integer.signum(remain) && Math.abs(v) <= Math.abs(remain)
                        && Math.abs(v) > Math.abs(best)) {
                    best = v;
                }
            }
            if (best == 0) break;
            sb.appendCodePoint(spaceChar(best));
            remain -= best;
        }
        return sb.isEmpty() ? Component.empty() : Component.text(sb.toString()).font(FONT);
    }

    /** 글리프의 글자 폭(px, glyphs.yml advance). 모르면 0. */
    public static int advance(String id) {
        GlyphDef g = Services.get().content().glyphs().get(id);
        return g == null || g.advance() < 0 ? 0 : g.advance();
    }

    /** 공백 값 v → 문자 코드포인트 (U+F800 + v). */
    public static int spaceChar(int px) { return 0xF800 + px; }

    /**
     * 배경 글리프를 깐 메뉴 제목: 왼쪽 8px 당겨 배경을 그린 뒤 (배경 폭 + 1)px 되돌아와 제목을 쓴다.
     * 배경 글리프가 없으면 제목만.
     */
    public static Component menuTitle(String backgroundGlyph, int backgroundWidth, Component title) {
        if (!has(backgroundGlyph)) return title;
        return Component.empty().append(space(-8)).append(glyph(backgroundGlyph))
                .append(space(-(backgroundWidth + 1) + 8)).append(title);
    }
}
