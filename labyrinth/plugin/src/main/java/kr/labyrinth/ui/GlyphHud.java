package kr.labyrinth.ui;

import java.util.List;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.GlyphDef;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.ShadowColor;
import net.kyori.adventure.text.format.TextColor;

/**
 * 리소스팩 글리프로 그린 액션바 HUD (glyphs.yml {@code hud:} 블록 계약, ARCHITECTURE §2 UI 글리프).
 * <p>
 * 좌표 x 는 핫바 왼쪽 끝 기준 0..181. 요소마다 {@code space(x − 펜) + 글리프}, 펜 += advance, 끝에 {@code space(total − 펜)}
 * → 전체 advance = 182 라서 가운데 정렬된 액션바가 핫바 위에 정확히 겹친다. 세로 위치는 각 글리프의 ascent 가 정한다.
 * 그림자는 꺼야 한다(액션바 글자 그림자가 바 밑에 겹쳐 보임).
 * <p>
 * 필요한 글리프(hud_hp_00.., hud_mp_00.., hud_xp_00.., hud_level_badge, hud_num_*)가 없으면 {@link #available()} = false
 * → LabHudService 는 텍스트 HUD 로 그린다.
 */
public final class GlyphHud {

    private static final ShadowColor NO_SHADOW = ShadowColor.none();

    private final Map<String, GlyphDef> glyphs;
    private final int total;
    private final int steps;
    private final int barWidth;
    private final int hpX, mpX, badgeX, xpX, statusX, goldRight;
    private final String digitChars;
    private final List<String> digitNames;

    private Component out = Component.empty();
    private int pen;

    private GlyphHud(Map<String, GlyphDef> glyphs, Map<String, Object> hud) {
        this.glyphs = glyphs;
        this.total = num(hud, "total", 182);
        this.steps = num(hud, "bar_steps", 20);
        this.barWidth = num(hud, "bar_width", 82);
        this.hpX = num(hud, "hp_x", 0);
        this.mpX = num(hud, "mp_x", 100);
        this.badgeX = num(hud, "badge_x", 82);
        this.xpX = num(hud, "xp_x", 0);
        this.statusX = num(hud, "status_x", 0);
        this.goldRight = num(hud, "gold_right", 182);
        Object dc = hud.get("digit_chars");
        this.digitChars = dc instanceof String s ? s : "0123456789/+-k M.:";
        List<String> names = List.of("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "slash", "plus", "minus", "k", "", "M", "dot", "colon");
        if (hud.get("digit_names") instanceof List<?> l && l.size() == digitChars.length()) {
            names = l.stream().map(o -> o == null ? "" : String.valueOf(o)).toList();
        }
        this.digitNames = names;
    }

    private static int num(Map<String, Object> m, String k, int def) {
        Object v = m.get(k);
        return v instanceof Number n ? n.intValue() : def;
    }

    /** 글리프 HUD 를 그릴 수 있는가 (팩 단계 글리프가 다 있는가). */
    public static boolean available() {
        try {
            Map<String, GlyphDef> g = Services.get().content().glyphs();
            return g.containsKey("hud_hp_00") && g.containsKey("hud_mp_00") && g.containsKey("hud_xp_00")
                    && g.containsKey("hud_level_badge") && g.containsKey("hud_num_0");
        } catch (Throwable t) {
            return false;
        }
    }

    /**
     * 액션바 한 줄.
     * @param status 상태 아이콘 글리프 id 목록 (status_*; 없는 건 건너뜀, 최대 8개)
     */
    public static Component compose(Map<String, Object> hudSection, double hp, double maxHp, double mp, double maxMp,
                                    double shield, int level, double xpRatio, long gold, List<String> status) {
        GlyphHud h = new GlyphHud(Services.get().content().glyphs(), hudSection == null ? Map.of() : hudSection);
        return h.build(hp, maxHp, mp, maxMp, shield, level, xpRatio, gold, status);
    }

    private Component build(double hp, double maxHp, double mp, double maxMp, double shield, int level, double xpRatio,
                            long gold, List<String> status) {
        double hpRatio = maxHp <= 0 ? 0 : hp / maxHp;
        double mpRatio = maxMp <= 0 ? 0 : mp / maxMp;
        // draw_order: xp, hp, (shield), mp, badge, hp_text, mp_text, level_text, status, gold
        put(xpX, bar("hud_xp_", xpRatio));
        put(hpX, bar("hud_hp_", hpRatio));
        if (shield > 0 && glyphs.containsKey("hud_shield_00")) put(hpX, bar("hud_shield_", Math.min(1, shield / Math.max(1, maxHp))));
        put(mpX, bar("hud_mp_", mpRatio));
        put(badgeX, "hud_level_badge");
        String hpText = shortNum(hp) + "/" + shortNum(maxHp);
        digits(hpX + (barWidth - inkWidth(hpText, "hud_num_")) / 2, hpText, "hud_num_", NamedTextColor.WHITE);
        String mpText = shortNum(mp) + "/" + shortNum(maxMp);
        digits(mpX + (barWidth - inkWidth(mpText, "hud_num_")) / 2, mpText, "hud_num_", NamedTextColor.WHITE);
        String lv = String.valueOf(level);
        int badgeW = Math.max(1, advance("hud_level_badge") - 1);
        digits(badgeX + (badgeW - inkWidth(lv, "hud_num_")) / 2, lv, "hud_num_", TextColor.color(0xffe08a));
        int x = statusX;
        int shown = 0;
        if (status != null) {
            for (String s : status) {
                if (shown >= 8 || !glyphs.containsKey(s)) continue;
                put(x, s);
                x += advance(s);
                shown++;
            }
        }
        if (glyphs.containsKey("hud_gold") && glyphs.containsKey("gold_num_0")) {
            String g = shortNum(gold);
            int w = advance("hud_gold") + textWidth(g, "gold_num_");
            int gx = goldRight - w;
            put(gx, "hud_gold");
            digits(gx + advance("hud_gold"), g, "gold_num_", TextColor.color(0xffd36b));
        }
        if (total != pen) out = out.append(Glyphs.space(total - pen));
        return out.shadowColor(NO_SHADOW);
    }

    private String bar(String prefix, double ratio) {
        int n;
        if (Double.isNaN(ratio) || ratio <= 0) n = 0;
        else if (ratio >= 1) n = steps;
        else n = Math.max(1, Math.min(steps - 1, (int) Math.round(ratio * steps)));
        return prefix + String.format("%02d", n);
    }

    private int advance(String id) {
        GlyphDef g = glyphs.get(id);
        return g == null || g.advance() < 0 ? 0 : g.advance();
    }

    private void put(int x, String id) {
        GlyphDef g = glyphs.get(id);
        if (g == null) return;
        if (x != pen) out = out.append(Glyphs.space(x - pen));
        out = out.append(glyph(g, NamedTextColor.WHITE));
        pen = x + Math.max(0, g.advance());
    }

    private TextComponent glyph(GlyphDef g, TextColor color) {
        return Component.text(g.ch()).font(Glyphs.FONT).color(color).shadowColor(NO_SHADOW);
    }

    private String digitGlyph(char c, String prefix) {
        int i = digitChars.indexOf(c);
        if (i < 0 || i >= digitNames.size() || digitNames.get(i).isEmpty()) return null;
        return prefix + digitNames.get(i);
    }

    private int textWidth(String s, String prefix) {
        int w = 0;
        for (char c : s.toCharArray()) {
            String id = digitGlyph(c, prefix);
            w += id == null ? 4 : advance(id);
        }
        return Math.max(0, w);
    }

    /** 가운데 정렬용 실제 그림 폭: advance 합에서 마지막 글자 뒤 1px 간격을 뺀 값. */
    private int inkWidth(String s, String prefix) {
        return Math.max(0, textWidth(s, prefix) - 1);
    }

    private void digits(int x, String s, String prefix, TextColor color) {
        if (x != pen) out = out.append(Glyphs.space(x - pen));
        pen = x;
        StringBuilder sb = new StringBuilder();
        for (char c : s.toCharArray()) {
            String id = digitGlyph(c, prefix);
            GlyphDef g = id == null ? null : glyphs.get(id);
            if (g == null) {
                if (!sb.isEmpty()) {
                    out = out.append(Component.text(sb.toString()).font(Glyphs.FONT).color(color).shadowColor(NO_SHADOW));
                    sb.setLength(0);
                }
                out = out.append(Glyphs.space(4));
                pen += 4;
                continue;
            }
            sb.append(g.ch());
            pen += Math.max(0, g.advance());
        }
        if (!sb.isEmpty()) out = out.append(Component.text(sb.toString()).font(Glyphs.FONT).color(color).shadowColor(NO_SHADOW));
    }

    /** 1234 → "1234", 12345 → "12.3k", 1234567 → "1.2M" (바 안에 들어가게 짧게). */
    static String shortNum(double v) {
        long n = Math.round(Math.max(0, v));
        if (n < 10_000) return Long.toString(n);
        if (n < 1_000_000) {
            double k = n / 1000.0;
            return k < 100 ? String.format(java.util.Locale.ROOT, "%.1fk", k) : (n / 1000) + "k";
        }
        double m = n / 1_000_000.0;
        return m < 100 ? String.format(java.util.Locale.ROOT, "%.1fM", m) : (n / 1_000_000) + "M";
    }
}
