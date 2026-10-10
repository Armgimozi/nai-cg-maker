package kr.souls.ui;

import kr.souls.hud.Glyphs;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;

/**
 * Dialog 창의 표 열 맞추기 (5.9, 5.10, 10.4: 능력치 표 StatSheet, 출신 줄). 바닐라는 창 본문 (plain_message) 의 줄마다, 단추는 단추마다 글을 가운데에 놓는다. 그래서 열이
 * 서려면 모든 줄의 진행 폭이 같아야 한다: 이름 칸은 팩이 그 언어의 무리에서 가장 긴 것의 폭까지 빈칸으로 채운 칸 (Lang.cell), 값은
 * 숫자라 두 언어 공통이고 glyphs.yml 의 글자 폭 (기본 글꼴, pack/typeset.py 가 잰 것) 으로 값 열 끝에 오른쪽 맞춤한다
 * (무기 설명 칸 item/StatTable 과 같은 길). 우리 글꼴의 진행 폭은 정수라 열이 픽셀까지 선다.
 * 팩 무리와 폭은 pack/typeset.py 의 CELLS 와 같다 (열쇠 꼴과 오른쪽 맞춤 칸의 폭 STAT_COL).
 */
public final class Columns {
    /** 능력치 표 오른쪽 열의 값 폭 (GUI 픽셀): "1105 → 1132" (56), "+9.5% → +9.8%" (64), 장비 중량 "21.0 / 38.9" (44) 가 든다.
     *  무게 단계 칸 (load.*.rcell) 도 이 폭 */
    public static final int VALUE = 64;
    /** 출신 줄의 레벨·능력치 칸 (오른쪽 맞춤, typeset 의 stat.*.short rcell 폭과 같다. 한국어 머리줄이 줄이지 않은 세 글자 이름
     *  "생명력" (24) 이라 사이가 6 남게 30) */
    public static final int STAT_COL = 30;
    /** 출신 줄의 능력치와 시작 아이템 사이 */
    public static final int KIT_GAP = 8;
    /** 값 글자색 (팔레트 뼈빛 bone2, 무기 설명 칸과 같다) */
    public static final TextColor VALUE_COLOR = TextColor.color(0xd6cbb0);
    /** 바뀔 값 (레벨 올리기 미리보기의 → 뒤): 바랜 금 */
    public static final TextColor NEXT_COLOR = TextColor.color(0xc9a65c);
    /** 출신 줄에서 그 출신의 주 능력치 (굵게): 양피지 */
    public static final TextColor MAIN_COLOR = TextColor.color(0xd1c3a0);
    /** 아직 적용되지 않는 값 (술법 전의 최대 마나·술법 위력), 소울이 모자란 "+": 흐린 갈색 */
    public static final TextColor DIM_COLOR = TextColor.color(0x6b5f4a);

    private Columns() {}

    /** 값 글의 진행 폭 (glyphs.yml 의 stats 폭, 없는 글자는 5). 팩이 없으면 -1. */
    public static int width(String value) {
        Glyphs.Stats st = Glyphs.stats();
        if (st == null) return -1;
        int w = 0;
        for (char ch : value.toCharArray()) w += st.widths().getOrDefault(ch, 5);
        return w;
    }

    public static boolean aligned() {
        return Glyphs.stats() != null && Glyphs.get("text_space_pos1") != null;
    }

    /** 폭 px 의 빈칸 (팩이 없으면 빈칸 하나). */
    public static Component pad(int px) {
        return Component.text(aligned() ? Glyphs.textSpaces(px) : " ");
    }

    /** 오른쪽 맞춤 값: 열 폭 col 의 끝에 붙는다. */
    public static Component right(String value, int col, TextColor color) {
        return right(value, col, color, false);
    }

    /** 오른쪽 맞춤 값. bold 면 굵게 (바닐라 굵은 글씨는 글자마다 진행 폭이 1 넓다: 그만큼 덜 채워 열이 그대로 선다). */
    public static Component right(String value, int col, TextColor color, boolean bold) {
        int w = width(value);
        if (w >= 0 && bold) w += value.length();
        Component v = Component.text(value).color(color);
        if (bold) v = v.decorate(TextDecoration.BOLD);
        if (w < 0) return Component.text().append(Component.text(" ")).append(v).build();
        return Component.text().append(pad(Math.max(0, col - w))).append(v).build();
    }

    /** 여러 색 조각의 오른쪽 맞춤 (texts[i] 를 colors[i] 로). 폭은 조각을 이은 글로 잰다. */
    public static Component rightParts(int col, String[] texts, TextColor[] colors) {
        int w = width(String.join("", texts));
        TextComponent.Builder b = Component.text();
        b.append(w < 0 ? Component.text(" ") : pad(Math.max(0, col - w)));
        for (int i = 0; i < texts.length; i++) b.append(Component.text(texts[i]).color(colors[i]));
        return b.build();
    }

    /** 미리보기 값: 바뀌지 않으면 now, 바뀌면 "now → next" (next 는 바랜 금). 열 폭 col 에 오른쪽 맞춤. */
    public static Component change(String now, String next, int col) {
        if (next == null || next.equals(now)) return right(now, col, VALUE_COLOR);
        String full = now + " → " + next;
        int w = width(full);
        TextComponent.Builder b = Component.text();
        if (w >= 0) b.append(pad(Math.max(0, col - w)));
        else b.append(Component.text(" "));
        b.append(Component.text(now + " → ").color(VALUE_COLOR)).append(Component.text(next).color(NEXT_COLOR));
        return b.build();
    }

    /** 여러 줄을 한 글로 (plain_message 는 줄바꿈 글자에서 줄을 바꾼다). */
    public static Component lines(java.util.List<Component> rows) {
        TextComponent.Builder b = Component.text();
        for (int i = 0; i < rows.size(); i++) {
            if (i > 0) b.append(Component.newline());
            b.append(rows.get(i));
        }
        return b.build();
    }
}
