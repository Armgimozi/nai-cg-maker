package kr.souls;

import kr.souls.util.Text;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.minimessage.MiniMessage;
import net.kyori.adventure.text.minimessage.tag.resolver.Placeholder;
import net.kyori.adventure.text.minimessage.tag.resolver.TagResolver;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/**
 * 게임 안 시스템 문구 (lang/ko.yml, 10.3). 데이터 폴더에 꺼내 두고 고칠 수 있게 한다.
 * 고친 파일에 없는 열쇠는 jar 안 기본 문구로 채운다 (새 판에서 생긴 문구가 빈칸으로 나오지 않게).
 */
public final class Lang {
    private static final String FILE = "lang/ko.yml";
    private static final MiniMessage MM = MiniMessage.miniMessage();
    private static YamlConfiguration yml = new YamlConfiguration();

    private Lang() {}

    static void load(JavaPlugin plugin) {
        File f = new File(plugin.getDataFolder(), FILE);
        if (!f.exists()) plugin.saveResource(FILE, false);
        YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
        try (InputStream in = plugin.getResource(FILE)) {
            if (in != null) y.setDefaults(YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8)));
        } catch (Exception e) {
            plugin.getLogger().warning(FILE + " 기본 문구를 읽지 못했습니다: " + e.getMessage());
        }
        yml = y;
    }

    /** MiniMessage 원문. 없으면 열쇠 이름을 그대로 돌려줘 빠진 문구가 눈에 띄게 한다. */
    public static String raw(String key) {
        String s = yml.getString(key);
        return s == null ? key : s;
    }

    /** 문구를 Component 로. args 는 "이름", "값" 짝 (문구 안의 <이름> 을 글자 그대로 채운다). */
    public static Component c(String key, String... args) {
        if (args.length == 0) return Text.mm(raw(key));
        TagResolver.Builder b = TagResolver.builder();
        for (int i = 0; i + 1 < args.length; i += 2) b.resolver(Placeholder.unparsed(args[i], args[i + 1]));
        return MM.deserialize(raw(key), b.build()).decorationIfAbsent(
                net.kyori.adventure.text.format.TextDecoration.ITALIC, net.kyori.adventure.text.format.TextDecoration.State.FALSE);
    }

    /** 색 표시를 뺀 글 (로그·접속 거절처럼 꾸밈이 필요 없는 곳). */
    public static String plain(String key) {
        return Text.strip(raw(key));
    }
}
