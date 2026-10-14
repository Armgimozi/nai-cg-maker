package kr.labyrinth.core;

import java.util.ArrayList;
import java.util.List;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.minimessage.MiniMessage;
import net.kyori.adventure.text.minimessage.tag.resolver.Placeholder;
import net.kyori.adventure.text.minimessage.tag.resolver.TagResolver;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.command.CommandSender;

/** MiniMessage 헬퍼. 레거시 § 코드 금지 — 모든 텍스트는 여기로. */
public final class Text {

    public static final MiniMessage MM = MiniMessage.miniMessage();
    /** 채팅 접두어. */
    public static final String PREFIX = "<gradient:#c9a2ff:#7fd8ff><b>미궁</b></gradient> <dark_gray>»</dark_gray> ";

    private Text() {}

    public static Component mm(String s) {
        return s == null ? Component.empty() : MM.deserialize(s);
    }

    public static Component mm(String s, TagResolver... resolvers) {
        return s == null ? Component.empty() : MM.deserialize(s, resolvers);
    }

    /** 아이템 이름/로어용: 기본 기울임 제거. */
    public static Component item(String s) {
        return mm(s).decorationIfAbsent(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    public static List<Component> itemLines(List<String> lines) {
        List<Component> out = new ArrayList<>(lines.size());
        for (String l : lines) out.add(item(l));
        return out;
    }

    /** 사용자 입력 등 태그를 해석하면 안 되는 문자열 이스케이프. */
    public static String escape(String s) {
        return s == null ? "" : MM.escapeTags(s);
    }

    public static String plain(Component c) {
        return PlainTextComponentSerializer.plainText().serialize(c);
    }

    /** MiniMessage 문자열에서 태그를 걷어 낸 일반 텍스트. */
    public static String strip(String s) {
        return s == null ? "" : MM.stripTags(s);
    }

    public static TagResolver ph(String key, String value) {
        return Placeholder.unparsed(key, value == null ? "" : value);
    }

    public static TagResolver ph(String key, Component value) {
        return Placeholder.component(key, value);
    }

    /** 접두어를 붙여 보낸다. */
    public static void send(CommandSender to, String miniMessage, TagResolver... resolvers) {
        to.sendMessage(mm(PREFIX + miniMessage, resolvers));
    }

    public static void error(CommandSender to, String miniMessage, TagResolver... resolvers) {
        to.sendMessage(mm(PREFIX + "<#ff6b6b>" + miniMessage, resolvers));
    }

    /** 1234567 → "1,234,567". */
    public static String num(long n) {
        return String.format("%,d", n);
    }

    /** 소수 → 정수(반올림) 문자열. */
    public static String num(double n) {
        return num(Math.round(n));
    }

    /** 0.153 → "15.3%". */
    public static String pct(double ratio) {
        double v = ratio * 100.0;
        return (Math.abs(v - Math.round(v)) < 0.05 ? String.valueOf(Math.round(v)) : String.format("%.1f", v)) + "%";
    }
}
