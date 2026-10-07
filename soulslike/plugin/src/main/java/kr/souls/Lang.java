package kr.souls;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.ComponentLike;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.Style;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 게임 안 문구 (10.3, 10.9, 12.5). 원본은 jar 안 lang/ko.yml (한국어) 이고 lang/en.yml (영어) 은 따로 썼다. 열쇠가 같다.
 * 플러그인은 글을 고르지 않는다: Component.translatable("souls.열쇠", 영어 대체 글, 자리 값...) 에 그 열쇠의 꼴(색·꾸밈)을
 * 입혀 보내고, 클라이언트가 리소스팩의 assets/souls/lang/(ko_kr|en_us).json 에서 자기 언어의 글을 고른다
 * (pack/gen_pack.py 가 같은 YAML 로 만든다. 다른 언어로 들어온 사람은 en_us 를 본다). 아이템 이름·설명도 같다.
 * 팩을 싣기 전에 보이는 글 (팩 안내, 팩 때문에 쫓아낼 때, 짓는 중 접속 거절) 만 서버가 그 사람의 언어로 채운다 (render).
 * 데이터 폴더에는 꺼내 두지 않는다: 글을 바꾸면 팩도 바뀌어야 하므로 팩과 jar 를 함께 다시 만든다.
 *
 * YAML 의 한 줄 "꼴태그글 자리" (예 "#b3a37f 꼴의 소울 souls 자리"): 맨 앞 태그들이 꼴, 그 뒤의 이름 태그는 자리다.
 * 번역 인수의 차례는 한국어 원본에 자리가 나오는 차례다 (영어는 %2$s 처럼 차례를 바꿔도 된다).
 */
public final class Lang {
    /** 팩 언어 파일의 열쇠 앞머리 (바닐라 열쇠와 겹치지 않게) */
    public static final String PREFIX = "souls.";
    public static final String KO = "ko";
    public static final String EN = "en";
    /** 바닐라 열쇠를 덮어쓰는 묶음 (팩에만 들어간다) */
    private static final String VANILLA = "vanilla.";
    private static final Pattern TAG = Pattern.compile("<([^<>]+)>");
    private static final Pattern HEX = Pattern.compile("#[0-9a-fA-F]{6}");

    /**
     * 열쇠 하나. text 는 꼴 태그를 뗀 글 (자리 태그는 그대로), slots 는 한국어에 자리가 나오는 차례,
     * fallback 은 영어 글을 마인크래프트 번역 형식 (%1$s) 으로 바꾼 것 (팩이 없을 때 클라이언트가 이것을 쓴다).
     */
    private record Entry(Style style, String styleTag, Map<String, String> text, List<String> slots, String fallback) {}

    private static Map<String, Entry> entries = Collections.emptyMap();
    /** 목록 열쇠 → 줄 수 (줄마다 열쇠.1, 열쇠.2 ...) */
    private static Map<String, Integer> lists = Collections.emptyMap();
    private static final Set<String> warned = Collections.synchronizedSet(new HashSet<>());
    private static Logger log = Logger.getLogger("Soulslike");

    private Lang() {}

    static void load(JavaPlugin plugin) {
        log = plugin.getLogger();
        warned.clear();
        Map<String, Map<String, Object>> raw = new LinkedHashMap<>();
        for (String lang : List.of(KO, EN)) raw.put(lang, read(plugin, "lang/" + lang + ".yml"));
        Map<String, Entry> out = new LinkedHashMap<>();
        Map<String, Integer> listOut = new LinkedHashMap<>();
        Map<String, Object> ko = raw.get(KO);
        Map<String, Object> en = raw.get(EN);
        Set<String> all = new TreeSet<>(ko.keySet());
        all.addAll(en.keySet());
        List<String> bad = new ArrayList<>();
        for (String key : all) {
            if (key.startsWith(VANILLA)) continue;
            Object k = ko.get(key);
            Object e = en.get(key);
            if (k == null || e == null) {
                bad.add(key + ": " + (k == null ? "ko.yml" : "en.yml") + " 에 없다"); // lang-ok: 서버 기록에만
                continue;
            }
            if (k instanceof List<?> kl) {
                List<?> el = e instanceof List<?> l ? l : List.of(e);
                if (kl.size() != el.size()) bad.add(key + ": 줄 수가 다르다 (ko " + kl.size() + ", en " + el.size() + ")"); // lang-ok
                listOut.put(key, kl.size());
                for (int i = 0; i < kl.size(); i++) {
                    put(out, bad, key + "." + (i + 1), String.valueOf(kl.get(i)), i < el.size() ? String.valueOf(el.get(i)) : "");
                }
            } else {
                put(out, bad, key, String.valueOf(k), e instanceof List<?> l && !l.isEmpty() ? String.valueOf(l.get(0)) : String.valueOf(e));
            }
        }
        entries = Collections.unmodifiableMap(out);
        lists = Collections.unmodifiableMap(listOut);
        // 둘이 어긋나면 크게 남긴다 (gen_pack·make_dist 는 이런 jar 를 만들지 않는다. tools/langcheck.py)
        for (String b : bad) log.severe("문구 lang/ko.yml 과 lang/en.yml 이 어긋난다: " + b);
        log.info("문구 열쇠 " + entries.size() + "개 (ko, en)");
        File old = new File(plugin.getDataFolder(), "lang");
        if (old.isDirectory()) {
            log.info("plugins/" + plugin.getName() + "/lang/ 은 이제 읽지 않습니다. 문구는 jar 와 리소스팩 안에 있습니다 (지워도 됩니다).");
        }
    }

    /** jar 안 YAML 을 점으로 이은 열쇠 → 글 또는 글 목록으로. */
    private static Map<String, Object> read(JavaPlugin plugin, String file) {
        Map<String, Object> out = new LinkedHashMap<>();
        try (InputStream in = plugin.getResource(file)) {
            if (in == null) {
                plugin.getLogger().severe("jar 안에 " + file + " 이 없습니다.");
                return out;
            }
            YamlConfiguration y = YamlConfiguration.loadConfiguration(new InputStreamReader(in, StandardCharsets.UTF_8));
            for (String path : y.getKeys(true)) {
                if (y.isConfigurationSection(path)) continue;
                if (y.isList(path)) out.put(path, y.getStringList(path));
                else out.put(path, y.getString(path, ""));
            }
        } catch (Exception ex) {
            plugin.getLogger().severe(file + " 을 읽지 못했습니다: " + ex.getMessage());
        }
        return out;
    }

    private static void put(Map<String, Entry> out, List<String> bad, String key, String ko, String en) {
        String[] kp = splitStyle(ko);
        String[] ep = splitStyle(en);
        if (!kp[0].equals(ep[0])) bad.add(key + ": 꼴이 다르다 (ko " + kp[0] + ", en " + ep[0] + ")"); // lang-ok
        List<String> slots = slots(kp[1]);
        if (!new TreeSet<>(slots).equals(new TreeSet<>(slots(ep[1])))) {
            bad.add(key + ": 자리가 다르다 (ko " + slots + ", en " + slots(ep[1]) + ")"); // lang-ok
        }
        Map<String, String> text = Map.of(KO, kp[1], EN, ep[1]);
        out.put(key, new Entry(style(kp[0]), kp[0], text, slots, mcFormat(ep[1], slots)));
    }

    /** "꼴태그들 + 글" → {꼴태그들, 글}. 맨 앞에서 꼴로 읽히는 태그만 떼고, 처음 만난 자리 태그에서 멈춘다. */
    static String[] splitStyle(String s) {
        int at = 0;
        while (at < s.length() && s.charAt(at) == '<') {
            int end = s.indexOf('>', at);
            if (end < 0 || !isStyleTag(s.substring(at + 1, end))) break;
            at = end + 1;
        }
        return new String[] {s.substring(0, at), s.substring(at)};
    }

    static boolean isStyleTag(String t) {
        String n = t.startsWith("!") ? t.substring(1) : t;
        if (HEX.matcher(n).matches()) return !t.startsWith("!");
        if (NamedTextColor.NAMES.value(n) != null) return !t.startsWith("!");
        return TextDecoration.NAMES.value(n) != null;
    }

    private static Style style(String tags) {
        Style.Builder b = Style.style();
        Matcher m = TAG.matcher(tags);
        while (m.find()) {
            String t = m.group(1);
            boolean off = t.startsWith("!");
            String n = off ? t.substring(1) : t;
            if (HEX.matcher(n).matches()) b.color(TextColor.fromHexString(n));
            else if (NamedTextColor.NAMES.value(n) != null) b.color(NamedTextColor.NAMES.value(n));
            else {
                TextDecoration d = TextDecoration.NAMES.value(n);
                if (d != null) b.decoration(d, !off);
            }
        }
        return b.build();
    }

    /** 글 안 자리 이름 (처음 나오는 차례, 겹치지 않게). */
    private static List<String> slots(String text) {
        List<String> out = new ArrayList<>();
        Matcher m = TAG.matcher(text);
        while (m.find()) if (!out.contains(m.group(1))) out.add(m.group(1));
        return out;
    }

    /** 마인크래프트 번역 형식: % → %%, 자리 → %n$s (n 은 한국어 원본의 차례). pack/langpack.py 의 mc_format 과 같다. */
    static String mcFormat(String text, List<String> order) {
        StringBuilder sb = new StringBuilder();
        Matcher m = TAG.matcher(text);
        int at = 0;
        while (m.find()) {
            sb.append(text.substring(at, m.start()).replace("%", "%%"));
            int i = order.indexOf(m.group(1));
            sb.append(i < 0 ? m.group().replace("%", "%%") : "%" + (i + 1) + "$s");
            at = m.end();
        }
        sb.append(text.substring(at).replace("%", "%%"));
        return sb.toString();
    }

    // ------------------------------------------------------------------ 쓰기

    /**
     * 번역 열쇠로 된 글 (클라이언트가 자기 언어로 고른다). args 는 "자리 이름", 값 짝. 값은 글이나 Component
     * (Component 면 그것도 번역 열쇠일 수 있다: 보스 이름 같은 것). 아이템 이름·설명에 그대로 써도 되게 기울임을 끈다.
     */
    public static Component c(String key, Object... args) {
        Entry e = entries.get(key);
        if (e == null) return missing(key);
        return Component.translatable(PREFIX + key, e.fallback(), e.style(), args(key, e, args))
                .decorationIfAbsent(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    /** 목록 열쇠 (아이템 설명 같은 여러 줄). 줄마다 c(열쇠.n). 목록이 아니면 한 줄. */
    public static List<Component> lines(String key, Object... args) {
        Integer n = lists.get(key);
        if (n == null) return List.of(c(key, args));
        List<Component> out = new ArrayList<>(n);
        for (int i = 1; i <= n; i++) out.add(c(key + "." + i, args));
        return out;
    }

    /** 서버가 채운 글 (팩을 싣기 전에 보이는 곳만). lang 은 KO 또는 EN (langOf). */
    public static Component render(String lang, String key, Object... args) {
        Entry e = entries.get(key);
        if (e == null) return missing(key);
        String text = e.text().getOrDefault(lang, e.text().get(EN));
        List<Component> vals = args(key, e, args);
        TextComponent.Builder b = Component.text().style(e.style());
        Matcher m = TAG.matcher(text);
        int at = 0;
        while (m.find()) {
            b.append(Component.text(text.substring(at, m.start())));
            int i = e.slots().indexOf(m.group(1));
            b.append(i < 0 ? Component.text(m.group()) : vals.get(i));
            at = m.end();
        }
        b.append(Component.text(text.substring(at)));
        return b.build().decorationIfAbsent(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    /** 언어를 모를 때 (접속하기 전): 한국어 줄 다음에 영어 줄. */
    public static Component renderBoth(String key, Object... args) {
        return Component.text().append(render(KO, key, args)).append(Component.newline()).append(render(EN, key, args)).build();
    }

    /** 명령어의 답. 플레이어에게는 번역 열쇠로, 콘솔에는 한국어로 (서버 기록은 한국어다). */
    public static void tell(CommandSender to, String key, Object... args) {
        to.sendMessage(to instanceof Player ? c(key, args) : render(KO, key, args));
    }

    /** 클라이언트 언어 (ko_kr, en_us ...) → KO 또는 EN. 한국어가 아니면 모두 영어 (팩의 en_us 와 같다). */
    public static String langOf(String clientLocale) {
        return clientLocale != null && clientLocale.toLowerCase(Locale.ROOT).startsWith("ko") ? KO : EN;
    }

    public static String langOf(Player p) {
        return p == null ? EN : langOf(p.locale().toString());
    }

    public static boolean has(String key) {
        return entries.containsKey(key) || lists.containsKey(key);
    }

    public static int size() {
        return entries.size();
    }

    /** 모든 열쇠 (목록은 줄마다, souls. 앞머리 없이). 팩의 souls 언어 파일과 같아야 한다. */
    public static Set<String> keys() {
        return entries.keySet();
    }

    /** 자리 값을 한국어 원본의 차례로. 없는 자리는 빈칸 (한 번 경고). */
    private static List<Component> args(String key, Entry e, Object[] args) {
        if (e.slots().isEmpty()) return List.of();
        Map<String, Object> given = new LinkedHashMap<>();
        for (int i = 0; i + 1 < args.length; i += 2) given.put(String.valueOf(args[i]), args[i + 1]);
        List<Component> out = new ArrayList<>(e.slots().size());
        for (String s : e.slots()) {
            Object v = given.get(s);
            if (v == null && warned.add(key + "<" + s + ">")) log.warning("문구 " + key + " 의 자리 <" + s + "> 에 값이 없습니다");
            out.add(v == null ? Component.empty() : v instanceof ComponentLike cl ? cl.asComponent() : Component.text(String.valueOf(v)));
        }
        return out;
    }

    /** 없는 열쇠는 열쇠 이름을 그대로 보여 눈에 띄게 한다. */
    private static Component missing(String key) {
        if (warned.add(key)) log.warning("문구 열쇠가 없습니다: " + key);
        return Component.text(key);
    }
}
