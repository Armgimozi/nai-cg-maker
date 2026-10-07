package kr.souls.hud;

import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.ShadowColor;
import net.kyori.adventure.text.format.TextColor;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * HUD·사망 화면 그림 글자 (리소스팩의 souls:hud 글꼴). 글자 자리(개인 영역 문자)는 팩을 만드는 gen_pack.py 가 정하고
 * jar 안 glyphs.yml 에 적는다. 플러그인은 자리를 외워 두지 않고 이 파일만 읽는다.
 *   이름: {char: "", width: 72, font: "souls:hud"}
 * 팔레트(10.1)의 글자색도 여기 상수로 둔다 (pack/palette.py 와 같은 값).
 */
public final class Glyphs {
    public record Glyph(String name, String ch, int width, Key font) {
        /** 그림 글자 하나. 그림 색을 그대로 보이게 흰색, 그림자 없이. */
        public TextComponent component() {
            return Component.text(ch).font(font).color(NamedTextColor.WHITE).shadowColor(ShadowColor.none());
        }
    }

    // ── 팔레트 (어두움 → 밝음) ──
    public static final TextColor RUST0 = TextColor.color(0x2b2622), RUST1 = TextColor.color(0x4a3f36),
            RUST2 = TextColor.color(0x6e5a48), RUST3 = TextColor.color(0x8c7259);
    public static final TextColor BRONZE0 = TextColor.color(0x3a2e1e), BRONZE1 = TextColor.color(0x5c4628),
            BRONZE2 = TextColor.color(0x7d6034), BRONZE3 = TextColor.color(0x9e7c44);
    public static final TextColor PARCH0 = TextColor.color(0x6b5f4a), PARCH1 = TextColor.color(0x8f8164),
            PARCH2 = TextColor.color(0xb3a37f), PARCH3 = TextColor.color(0xd1c3a0);
    public static final TextColor BLOOD0 = TextColor.color(0x3d0f0c), BLOOD1 = TextColor.color(0x5e1611),
            BLOOD2 = TextColor.color(0x7d1f17), BLOOD3 = TextColor.color(0xa8301f);
    public static final TextColor ASH0 = TextColor.color(0x1c1b1a), ASH1 = TextColor.color(0x3a3836),
            ASH2 = TextColor.color(0x5c5955), ASH3 = TextColor.color(0x858079);
    public static final TextColor MOSS0 = TextColor.color(0x2e3322), MOSS1 = TextColor.color(0x48502f),
            MOSS2 = TextColor.color(0x646d3e);
    public static final TextColor BONE0 = TextColor.color(0x8a8270), BONE1 = TextColor.color(0xb0a68e),
            BONE2 = TextColor.color(0xd6cbb0), BONE3 = TextColor.color(0xe8dcc0);
    public static final TextColor EMBER0 = TextColor.color(0x7a2e10), EMBER1 = TextColor.color(0xb04a17),
            EMBER2 = TextColor.color(0xd9772a), EMBER3 = TextColor.color(0xf0b060);
    /** 생피: 사망 화면 "YOU DIED" 하나에만 쓴다 (사용자 결정 3, 10.1) */
    public static final TextColor GORE0 = TextColor.color(0x3b0605), GORE1 = TextColor.color(0x6e0b08),
            GORE2 = TextColor.color(0xa3110c), GORE3 = TextColor.color(0xcc2418);

    /**
     * HUD 자리 값 (glyphs.yml 의 layout, pack/hud.py 의 layout()). 글꼴 셰이더와 같은 값이다.
     * margin: 셰이더 없이 화면 가장자리 여백, left: 막대 왼쪽 끝을 가운데에서 왼쪽으로 민 거리, right: 소울 상자 오른쪽 끝을
     * 가운데에서 오른쪽으로 민 거리, markLeft/markRight: 셰이더가 왼쪽 위·오른쪽 아래로 옮기는 글자색, soulBox: 소울 상자 폭.
     * 보스 막대: markBoss (막대 그림 글자, 셰이더가 화면 아래로 내리고 가로로 늘인다), markBossName / markBossShadow (이름과
     * 그 그림자, 막대 왼쪽 끝 위로), markHidden (셰이더가 지우는 이름 사본), bossWidth (체력 막대의 바탕 길이).
     */
    public record Layout(int margin, int left, int right, TextColor markLeft, TextColor markRight, int soulBox,
                         TextColor markBoss, TextColor markBossName, TextColor markBossShadow, TextColor markHidden, int bossWidth) {}

    private static final Key DEFAULT_FONT = Key.key("souls", "hud");
    private static Map<String, Glyph> glyphs = Collections.emptyMap();
    private static Layout layout;

    private Glyphs() {}

    /** jar 안 glyphs.yml 을 읽는다. 없으면 그림 글자 없이 (일반 글씨로 대신) 돈다. */
    public static void load(JavaPlugin plugin) {
        Map<String, Glyph> out = new LinkedHashMap<>();
        try (InputStream in = plugin.getResource("glyphs.yml")) {
            layout = null;
            if (in == null) {
                plugin.getLogger().warning("jar 안에 glyphs.yml 이 없습니다 (pack/gen_pack.py 를 gradle 보다 먼저 돌리세요). 그림 글자 대신 일반 글씨를 씁니다.");
                glyphs = out;
                return;
            }
            YamlConfiguration y = YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
            ConfigurationSection root = y.isConfigurationSection("glyphs") ? y.getConfigurationSection("glyphs") : y;
            ConfigurationSection lay = root.getConfigurationSection("layout");
            layout = lay == null ? null : new Layout(lay.getInt("margin", 8), lay.getInt("left", 205), lay.getInt("right", 206),
                    color(lay.getString("mark_left"), 0xfefd01), color(lay.getString("mark_right"), 0xfefd02), lay.getInt("soul_box", 64),
                    color(lay.getString("mark_boss"), 0xfefd03), color(lay.getString("mark_boss_name"), 0xfefd04),
                    color(lay.getString("mark_boss_shadow"), 0xfefd05), color(lay.getString("mark_hidden"), 0xfefd06),
                    lay.getInt("boss_width", 200));
            for (String name : root.getKeys(false)) {
                if (name.equals("layout")) continue;
                ConfigurationSection g = root.getConfigurationSection(name);
                if (g == null) continue;
                String ch = decode(g.getString("char", ""));
                if (ch.isEmpty()) {
                    plugin.getLogger().warning("glyphs.yml 의 " + name + " 에 char 가 없습니다");
                    continue;
                }
                String font = g.getString("font", DEFAULT_FONT.asString());
                Key key;
                try {
                    key = Key.key(font);
                } catch (RuntimeException ex) {
                    plugin.getLogger().warning("glyphs.yml 의 " + name + " 글꼴 이름이 틀렸습니다: " + font);
                    key = DEFAULT_FONT;
                }
                out.put(name, new Glyph(name, ch, g.getInt("width", 0), key));
            }
        } catch (Exception ex) {
            plugin.getLogger().warning("glyphs.yml 을 읽지 못했습니다: " + ex.getMessage());
        }
        glyphs = Collections.unmodifiableMap(out);
        plugin.getLogger().info("그림 글자 " + glyphs.size() + "개 (glyphs.yml)");
    }

    private static TextColor color(String hex, int fallback) {
        TextColor c = hex == null ? null : TextColor.fromHexString(hex.trim());
        return c == null ? TextColor.color(fallback) : c;
    }

    /** HUD 자리 값. glyphs.yml 에 layout 이 없으면 (옛 팩) null: HUD 는 그림 글자 막대 없이 글로 대신한다. */
    public static Layout layout() {
        return layout;
    }

    /** YAML 이 "" 을 풀지 않은 채(작은따옴표) 적었거나 "U+E001" 로 적었어도 받아 준다. */
    static String decode(String s) {
        if (s == null) return "";
        String t = s.trim();
        StringBuilder sb = new StringBuilder();
        int i = 0;
        while (i < t.length()) {
            if (t.startsWith("\\u", i) && i + 6 <= t.length()) {
                sb.append((char) Integer.parseInt(t.substring(i + 2, i + 6), 16));
                i += 6;
            } else if ((t.startsWith("U+", i) || t.startsWith("u+", i)) && i + 6 <= t.length()) {
                sb.append((char) Integer.parseInt(t.substring(i + 2, i + 6), 16));
                i += 6;
            } else {
                sb.append(t.charAt(i++));
            }
        }
        return sb.toString();
    }

    public static Glyph get(String name) {
        return glyphs.get(name);
    }

    public static int size() {
        return glyphs.size();
    }

    public static Map<String, Glyph> all() {
        return glyphs;
    }

    /** 빈칸으로 가른 이름들을 이어 붙인 글. 하나라도 없으면 null (부른 쪽이 일반 글씨로 대신한다). */
    public static Component line(String names) {
        if (names == null || names.isBlank()) return null;
        Component out = Component.empty();
        for (String n : names.trim().split("\\s+")) {
            Glyph g = glyphs.get(n);
            if (g == null) return null;
            out = out.append(g.component());
        }
        return out;
    }
}
