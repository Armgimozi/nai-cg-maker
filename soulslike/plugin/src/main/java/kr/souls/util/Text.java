package kr.souls.util;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.minimessage.MiniMessage;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

import java.util.ArrayList;
import java.util.List;

/**
 * MiniMessage 문자열을 Component 로 바꾸는 도우미. 아이템 이름/설명은 기울임을 끈다.
 * 플레이어가 보는 글에는 쓰지 않는다: 게임 글은 언어 열쇠다 (kr.souls.Lang, 10.3). 시험 줄·기록 같은 기계 글에만.
 */
public final class Text {
    private static final MiniMessage MM = MiniMessage.miniMessage();

    private Text() {}

    public static Component mm(String s) {
        if (s == null) return Component.empty();
        return MM.deserialize(s).decorationIfAbsent(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    public static List<Component> mm(List<String> lines) {
        List<Component> out = new ArrayList<>(lines.size());
        for (String l : lines) out.add(mm(l));
        return out;
    }

    public static String plain(Component c) {
        return PlainTextComponentSerializer.plainText().serialize(c);
    }

    public static String strip(String miniMessage) {
        return plain(MM.deserialize(miniMessage == null ? "" : miniMessage));
    }

    /** 소수점이 필요 없으면 정수로, 아니면 한 자리까지. */
    public static String num(double v) {
        if (Math.abs(v - Math.round(v)) < 1e-6) return Long.toString(Math.round(v));
        return String.format("%.1f", v);
    }

    public static String pct(double ratio) {
        return num(ratio * 100) + "%";
    }
}
