package kr.labyrinth.ui;

import java.util.HashMap;
import java.util.Map;
import kr.labyrinth.Services;
import kr.labyrinth.content.GlyphDef;
import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.KeybindComponent;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.TranslatableComponent;
import net.kyori.adventure.text.format.Style;
import net.kyori.adventure.text.format.TextDecoration;

/**
 * 클라이언트가 그릴 글자 폭(px) 추정 — 액션바 안내 글을 HUD 위 가운데에 놓을 때만 쓴다.
 * <p>
 * HUD 위치는 이 값과 무관하다({@link LabHudService} 가 같은 글을 화면 밖에 한 번 더 그려 폭을 상쇄). 그래서 여기 오차는
 * 글이 몇 px 옆으로 비켜 보이는 정도로 끝난다. 값은 26.3 기본 글꼴 비트맵(ascii·accented·nonlatin_european)에서 잰
 * 글자 폭(advance), 그 밖은 unifont(반 배율, 폭/2 + 1) 추정 — 한글 음절 8, 자모·한자 9, 굵게 +1.
 */
public final class TextWidth {

    /** ' '(32) ~ '~'(126) 기본 글꼴 폭. */
    private static final byte[] ASCII = {
            4, 2, 4, 6, 6, 6, 6, 2, 4, 4, 4, 6, 2, 6, 2, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 2, 2, 5, 6, 5, 6,
            7, 6, 6, 6, 6, 6, 6, 6, 6, 4, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 4, 6, 4, 6, 6,
            3, 6, 6, 6, 6, 6, 5, 6, 6, 2, 6, 5, 3, 6, 6, 6, 6, 6, 6, 6, 4, 6, 6, 6, 6, 6, 6, 4, 2, 4, 7};

    /** 미궁 문구에 실제로 쓰는 기호들의 폭 (문자열 두 줄을 code point 순서대로 짝지음, 폭 = 문자 − '0'). */
    private static final String SYMBOLS = "─═·—→§×━−…≤✦▶°▮±◆★▯⚔✔»⚠≥●○❤□◀⛃■∈✚✘🔒▪🔇❄♪▌█↔▸≈◈²÷◐│◎▼Ⅰθ☀☾⚓✿♥♠☂✉⌛☯⚖「」🔥←✖";
    private static final String SYMBOL_W = "9929866568687536683877:656867866876368659937456468626948866888:833788";
    private static final Map<Integer, Integer> SYM = new HashMap<>();

    static {
        int[] cps = SYMBOLS.codePoints().toArray();
        for (int i = 0; i < cps.length && i < SYMBOL_W.length(); i++) SYM.put(cps[i], SYMBOL_W.charAt(i) - '0');
    }

    private static final Key UI_FONT = Glyphs.FONT;

    private TextWidth() {}

    /** 기본 글꼴 한 글자 폭 (굵게 제외). */
    public static int defaultAdvance(int cp) {
        if (cp >= 32 && cp <= 126) return ASCII[cp - 32];
        Integer s = SYM.get(cp);
        if (s != null) return s;
        if (cp >= 0xAC00 && cp <= 0xD7AF) return 8;                      // 한글 음절
        if ((cp >= 0x1100 && cp <= 0x11FF) || (cp >= 0x3130 && cp <= 0x318F)) return 9;   // 자모
        if ((cp >= 0x3000 && cp <= 0x9FFF) || (cp >= 0xF900 && cp <= 0xFAFF)) return 9;   // 한자·가나
        if (cp >= 0xA0 && cp <= 0x24F) return 6;                         // 라틴 확장
        return 8;
    }

    /** 컴포넌트 전체 폭 (스타일 상속: 굵게·글꼴). */
    public static int width(Component c) {
        return c == null ? 0 : Math.max(0, walk(c, false, null));
    }

    private static int walk(Component c, boolean parentBold, Key parentFont) {
        Style own = c.style();
        TextDecoration.State b = own.decoration(TextDecoration.BOLD);
        boolean bold = b == TextDecoration.State.NOT_SET ? parentBold : b == TextDecoration.State.TRUE;
        Key font = own.font() != null ? own.font() : parentFont;
        int w = 0;
        if (c instanceof TextComponent t) {
            w += textWidth(t.content(), bold, font);
        } else if (c instanceof KeybindComponent k) {
            w += textWidth(keyName(k.keybind()), bold, font);
        } else if (c instanceof TranslatableComponent tr) {
            String fb = tr.fallback();
            w += fb != null ? textWidth(fb, bold, font) : 6 * tr.key().length() / 2;
        }
        for (Component child : c.children()) w += walk(child, bold, font);
        return w;
    }

    private static int textWidth(String s, boolean bold, Key font) {
        if (s == null || s.isEmpty()) return 0;
        boolean ui = UI_FONT.equals(font);
        Map<Integer, Integer> uiAdv = ui ? uiAdvances() : null;
        int w = 0;
        for (int i = 0; i < s.length(); ) {
            int cp = s.codePointAt(i);
            i += Character.charCount(cp);
            int a;
            if (ui) {
                if (cp >= 0xF400 && cp <= 0xF8FF) a = cp - 0xF800;      // 공백 글리프 U+F800 + v
                else a = uiAdv.getOrDefault(cp, 0);
            } else {
                a = defaultAdvance(cp);
            }
            w += a + (bold ? 1 : 0);
        }
        return w;
    }

    private static volatile Map<Integer, Integer> uiCache;
    private static volatile Object uiCacheKey;

    private static Map<Integer, Integer> uiAdvances() {
        try {
            Map<String, GlyphDef> g = Services.get().content().glyphs();
            if (uiCache != null && uiCacheKey == g) return uiCache;
            Map<Integer, Integer> m = new HashMap<>();
            for (GlyphDef d : g.values()) {
                if (d.ch() != null && !d.ch().isEmpty()) m.put(d.ch().codePointAt(0), Math.max(0, d.advance()));
            }
            uiCache = m;
            uiCacheKey = g;
            return m;
        } catch (Throwable t) {
            return Map.of();
        }
    }

    /** 기본 키 이름 추정 (한국어 클라이언트 기본 배치). 실제와 달라도 글 위치만 살짝 비킨다. */
    static String keyName(String keybind) {
        return switch (keybind == null ? "" : keybind) {
            case "key.sneak" -> "왼쪽 Shift";
            case "key.sprint" -> "왼쪽 Ctrl";
            case "key.swapOffhand" -> "F";
            case "key.drop" -> "Q";
            case "key.jump" -> "스페이스";
            case "key.attack" -> "왼쪽 버튼";
            case "key.use" -> "오른쪽 버튼";
            case "key.inventory" -> "E";
            default -> "????";
        };
    }
}
