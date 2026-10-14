package kr.labyrinth.ui;

import java.util.Map;
import kr.labyrinth.content.GlyphDef;
import kr.labyrinth.core.Text;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * HUD 막대 (액션바·사이드바). 글리프가 있으면 리소스팩 그림 막대, 없으면 텍스트 막대.
 * <p>
 * <b>HUD 글리프 이름 계약</b> (kind = hp | mp | xp | party_hp):
 * <ol>
 *   <li>프레임 방식: {@code hud_<kind>_0} … {@code hud_<kind>_<N>} — 채움 단계마다 막대 한 장 (N = 가장 큰 번호).</li>
 *   <li>칸 방식: {@code hud_<kind>_full} / {@code hud_<kind>_half}(선택) / {@code hud_<kind>_empty} 를 10칸 이어 붙임
 *       (옛 이름 {@code <kind>_bar_full|half|empty} 도 인식).</li>
 *   <li>아이콘(선택): {@code hud_<kind>_icon}, {@code hud_gold_icon}, {@code hud_level_icon}.</li>
 * </ol>
 * 아무것도 없으면 {@link #textBar} 로 그린다.
 */
public final class HudBars {

    private HudBars() {}

    /** 0~1 비율을 cells 칸 텍스트 막대로 (테스트 가능한 순수 함수). */
    public static String textBar(double ratio, int cells, String fill, String empty) {
        int n = filledCells(ratio, cells);
        return fill.repeat(n) + empty.repeat(Math.max(0, cells - n));
    }

    /** 채운 칸 수: 0 초과면 최소 1칸, 1 미만이면 최대 cells-1 칸 (가득 참/텅 빔이 확실히 구분되게). */
    public static int filledCells(double ratio, int cells) {
        if (Double.isNaN(ratio) || ratio <= 0) return 0;
        if (ratio >= 1) return cells;
        int n = (int) Math.round(ratio * cells);
        return Math.max(1, Math.min(cells - 1, n));
    }

    /** 반 칸 단위 (칸 방식 글리프): 반환 = 반 칸 수 0..2*cells. */
    public static int halfCells(double ratio, int cells) {
        if (Double.isNaN(ratio) || ratio <= 0) return 0;
        if (ratio >= 1) return cells * 2;
        int n = (int) Math.round(ratio * cells * 2);
        return Math.max(1, Math.min(cells * 2 - 1, n));
    }

    /** 프레임 방식에서 쓸 프레임 번호 (0..maxFrame). */
    public static int frameIndex(double ratio, int maxFrame) {
        if (Double.isNaN(ratio) || ratio <= 0) return 0;
        if (ratio >= 1) return maxFrame;
        return Math.max(1, Math.min(maxFrame - 1, (int) Math.round(ratio * maxFrame)));
    }

    private static Map<String, GlyphDef> glyphs() {
        try {
            return kr.labyrinth.Services.get().content().glyphs();
        } catch (Throwable t) {
            return Map.of();
        }
    }

    private static Component g(GlyphDef def) {
        return Component.text(def.ch()).font(Glyphs.FONT).color(NamedTextColor.WHITE);
    }

    /** 글리프 막대가 가능한가 (프레임 또는 칸 방식). */
    public static boolean hasGlyphBar(String kind) {
        Map<String, GlyphDef> gs = glyphs();
        return gs.containsKey("hud_" + kind + "_0") || gs.containsKey("hud_" + kind + "_full") || gs.containsKey(kind + "_bar_full");
    }

    /** 아이콘 글리프 (없으면 fallback MiniMessage 문자). */
    public static Component icon(String name, String fallbackMini) {
        GlyphDef def = glyphs().get("hud_" + name + "_icon");
        return def == null ? Text.mm(fallbackMini) : g(def);
    }

    /**
     * 막대 컴포넌트. 글리프가 없으면 색 텍스트 막대(fillColor, cells 칸).
     */
    public static Component bar(String kind, double ratio, int cells, String fillColor) {
        Map<String, GlyphDef> gs = glyphs();
        // 1) 프레임 방식
        if (gs.containsKey("hud_" + kind + "_0")) {
            int max = 0;
            while (gs.containsKey("hud_" + kind + "_" + (max + 1)) && max < 200) max++;
            if (max > 0) return g(gs.get("hud_" + kind + "_" + frameIndex(ratio, max)));
        }
        // 2) 칸 방식
        GlyphDef full = gs.getOrDefault("hud_" + kind + "_full", gs.get(kind + "_bar_full"));
        GlyphDef empty = gs.getOrDefault("hud_" + kind + "_empty", gs.get(kind + "_bar_empty"));
        GlyphDef half = gs.getOrDefault("hud_" + kind + "_half", gs.get(kind + "_bar_half"));
        if (full != null && empty != null) {
            int halves = half != null ? halfCells(ratio, cells) : filledCells(ratio, cells) * 2;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < cells; i++) {
                int h = halves - i * 2;
                sb.append(h >= 2 ? full.ch() : h == 1 && half != null ? half.ch() : empty.ch());
            }
            return Component.text(sb.toString()).font(Glyphs.FONT).color(NamedTextColor.WHITE);
        }
        // 3) 텍스트
        return Text.mm("<" + fillColor + ">" + textBar(ratio, cells, "▮", "") + "</" + fillColor + "><#3a3546>"
                + "▮".repeat(Math.max(0, cells - filledCells(ratio, cells))));
    }
}
