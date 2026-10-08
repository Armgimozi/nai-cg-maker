"""
mood_gothic 의 플러그인 쪽. 작업 폴더의 사본 (plugin/ 을 베낀 것) 에서만 고치고 그 사본으로 jar 를 만든다.
저장소의 plugin/ 은 건드리지 않는다.

  Lang.java       YAML 꼴 태그에 <font:이름공간:이름> 을 더 받는다 (태그가 없으면 하는 일이 없다).
  GothicStats     (새 파일) 무기 설명 칸의 수치를 두 열로: 칸마다 "이름 (그 언어의 이름 열 폭까지 채운 번역) + 빈칸 + 값
                  (값 열 끝에 오른쪽 맞춤)", 두 칸 사이는 열 간격 빈칸. 값 글자의 진행 폭과 빈칸 글자는 팩을 만들 때 잰
                  gothic_layout.txt (jar 안) 에서 읽는다.
  ItemFactory     무기 설명 칸: 수치 줄을 GothicStats 로, tooltip_style souls:gothic_weapon (이름 밑 금실이 있는 칸).
  lang/*.yml      무기 이름·휴식 창 제목 → 제목 글꼴, 무기 설명 → 설명 글꼴 (조용한 톤), 분류 줄 → 흐린 옛 금빛,
                  수치 칸 이름 gothic.stat.* (두 언어).
"""
import os
import re
import shutil
import subprocess

STAT_LABEL_COLOR = "#858079"


def _sub(s, old, new, what):
    assert old in s, f"{what}: 바꿀 곳을 찾지 못했다 (원본이 바뀌었다)"
    return s.replace(old, new, 1)


def patch_lang_java(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    s = _sub(s, "        String n = t.startsWith(\"!\") ? t.substring(1) : t;\n        if (HEX.matcher(n).matches()) return !t.startsWith(\"!\");\n",
             "        String n = t.startsWith(\"!\") ? t.substring(1) : t;\n"
             "        if (n.startsWith(\"font:\")) return !t.startsWith(\"!\") && FONT.matcher(n.substring(5)).matches();\n"
             "        if (HEX.matcher(n).matches()) return !t.startsWith(\"!\");\n", "Lang.isStyleTag")
    s = _sub(s, "            if (HEX.matcher(n).matches()) b.color(TextColor.fromHexString(n));\n",
             "            if (n.startsWith(\"font:\")) b.font(net.kyori.adventure.key.Key.key(n.substring(5)));\n"
             "            else if (HEX.matcher(n).matches()) b.color(TextColor.fromHexString(n));\n", "Lang.style")
    s = _sub(s, "    private static final Pattern HEX = Pattern.compile(\"#[0-9a-fA-F]{6}\");\n",
             "    private static final Pattern HEX = Pattern.compile(\"#[0-9a-fA-F]{6}\");\n"
             "    /** 꼴 태그 &lt;font:이름공간:이름&gt; (UI 분위기 시안 mood_gothic) */\n"
             "    private static final Pattern FONT = Pattern.compile(\"[a-z0-9_.-]+:[a-z0-9_./-]+\");\n", "Lang.HEX")
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


def patch_item_factory(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    s = _sub(s, "        lore.addAll(statLines(d));\n", "        lore.addAll(GothicStats.lines(d));\n", "ItemFactory.weapon 수치")
    s = _sub(s, "        it.setData(DataComponentTypes.LORE, ItemLore.lore(lore));\n        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);\n",
             "        it.setData(DataComponentTypes.LORE, ItemLore.lore(lore));\n"
             "        it.setData(DataComponentTypes.TOOLTIP_STYLE, Key.key(Keys.NS, \"gothic_weapon\"));\n"
             "        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);\n", "ItemFactory.weapon 칸")
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


def gothic_stats_java(value_hex):
    return f"""package kr.souls.item;

import kr.souls.Lang;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * UI 분위기 시안 mood_gothic: 무기 설명 칸의 수치를 다크 소울 3 처럼 두 열로 (이름은 왼쪽, 값은 열 끝에 오른쪽 맞춤).
 * 이름 번역 (souls.gothic.stat.*) 은 팩이 그 언어의 이름 열 폭까지 빈칸으로 채워 두었다. 값의 폭은 팩을 만들 때 잰
 * 글자 폭 표 (jar 안 gothic_layout.txt) 로 셈해 값 앞을 빈칸 글자로 채운다.
 */
final class GothicStats {{
    private static final TextColor VALUE = TextColor.color({value_hex});
    private static final Map<Character, Double> ADV = new LinkedHashMap<>();
    private static final List<Map.Entry<String, Double>> PADS = new ArrayList<>();
    private static String gap = " ";
    private static double valueCol = 18.0;

    static {{
        try (InputStream in = GothicStats.class.getResourceAsStream("/gothic_layout.txt")) {{
            if (in != null) {{
                BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
                String line;
                while ((line = r.readLine()) != null) {{
                    String[] p = line.trim().split(" ");
                    if (p.length < 2) continue;
                    switch (p[0]) {{
                        case "value" -> ADV.put((char) Integer.parseInt(p[1], 16), Double.parseDouble(p[2]));
                        case "pad" -> PADS.add(Map.entry(String.valueOf((char) Integer.parseInt(p[1], 16)), Double.parseDouble(p[2])));
                        case "gap" -> gap = String.valueOf((char) Integer.parseInt(p[1], 16));
                        case "valuecol" -> valueCol = Double.parseDouble(p[1]);
                        default -> {{ }}
                    }}
                }}
            }}
        }} catch (Exception ignored) {{
            // 표가 없으면 빈칸 하나로 (가지런하지 않을 뿐 글은 다 보인다)
        }}
        PADS.sort((a, b) -> Double.compare(b.getValue(), a.getValue()));
    }}

    private GothicStats() {{}}

    static List<Component> lines(Weapons.Def d) {{
        List<String[]> cells = new ArrayList<>();
        if (d.shield()) {{
            cells.add(new String[] {{"absorb", d.absorb() + "%"}});
            cells.add(new String[] {{"stability", String.valueOf(d.stability())}});
        }} else if (d.attack() > 0) {{
            cells.add(new String[] {{"attack", String.valueOf(d.attack())}});
        }}
        cells.add(new String[] {{"weight", String.format(Locale.ROOT, "%.1f", d.weight())}});
        for (String s : Weapons.STATS) {{
            Object v = d.scaling().get(s);
            if (v != null) cells.add(new String[] {{"bonus_" + s, String.valueOf(v)}});
        }}
        if (cells.size() % 2 == 1 && d.scaling().isEmpty()) cells.add(null);
        for (String s : Weapons.STATS) {{
            Object v = d.requires().get(s);
            if (v != null) cells.add(new String[] {{"need_" + s, String.valueOf(v)}});
        }}
        List<Component> out = new ArrayList<>();
        for (int i = 0; i < cells.size(); i += 2) {{
            TextComponent.Builder row = Component.text();
            row.append(cell(cells.get(i)));
            if (i + 1 < cells.size() && cells.get(i + 1) != null) {{
                row.append(Component.text(gap));
                row.append(cell(cells.get(i + 1)));
            }}
            out.add(row.build().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE));
        }}
        return out;
    }}

    private static Component cell(String[] c) {{
        if (c == null) return Component.empty();
        return Component.text()
                .append(Lang.c("gothic.stat." + c[0])) // lang-dyn: gothic.stat.*
                .append(Component.text(pad(c[1])))
                .append(Component.text(c[1]).color(VALUE))
                .build();
    }}

    private static String pad(String value) {{
        double w = 0;
        for (char ch : value.toCharArray()) w += ADV.getOrDefault(ch, 5.0);
        double left = Math.max(0.0, valueCol - w);
        StringBuilder b = new StringBuilder();
        for (Map.Entry<String, Double> p : PADS) {{
            while (left >= p.getValue() - 1e-6) {{
                b.append(p.getKey());
                left -= p.getValue();
            }}
        }}
        return b.toString();
    }}
}}
"""


def patch_yaml(path, lang, st, palette_hex):
    """무기 이름·휴식 창 제목 → 제목 글꼴, 무기 설명 → 설명 글꼴, 분류 줄 색, 수치 칸 이름."""
    import lang as lang_mod
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out = []
    section = None
    sub = None
    n_name = n_lore = n_class = 0
    for line in lines:
        if line and not line.startswith(" ") and not line.startswith("#"):
            section = line.split(":")[0]
        m = re.match(r"^  ([a-z_-]+):", line)
        if m:
            sub = m.group(1)
        if section == "weapon":
            m = re.match(r'^(    name: ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
            if m:
                line = m.group(1) + f"<{palette_hex(st.NAME)}><font:{st.FONT_TITLE}>" + m.group(3)
                n_name += 1
            m = re.match(r'^(      - ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
            if m:
                line = m.group(1) + f"<{palette_hex(st.LORE_INK)}><font:{st.FONT_LORE}>" + m.group(3)
                n_lore += 1
            if sub == "class":
                m = re.match(r'^(    [a-z_]+: ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
                if m:
                    line = m.group(1) + f"<{palette_hex(st.CLASS)}>" + m.group(3)
                    n_class += 1
        if section == "bonfire":
            m = re.match(r'^(  test-name: ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
            if m:
                line = m.group(1) + f"<{palette_hex(st.NAME)}><font:{st.FONT_TITLE}>" + m.group(3)
        out.append(line)
    i = 0 if lang == "ko" else 1
    add = ["", "gothic:", "  # UI 분위기 시안 mood_gothic: 무기 설명 칸의 수치 이름 (팩이 이름 열 폭까지 빈칸으로 채운다)", "  stat:"]
    for k, v in lang_mod.STAT_LABELS.items():
        add.append(f'    {k}: "<{palette_hex(st.LABEL)}>{v[i]}"')
    text = "\n".join(out).rstrip("\n") + "\n" + "\n".join(add) + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return n_name, n_lore, n_class


def layout_text(layout):
    lines = ["# mood_gothic: 무기 설명 칸 수치 열 (pack/variants/mood_gothic/lang.py 가 잰 값)"]
    for ch, adv in layout["values"].items():
        lines.append(f"value {ord(ch):04x} {adv}")
    for ch, adv in layout["pads"].items():
        lines.append(f"pad {ord(ch):04x} {adv}")
    lines.append(f"gap {ord(layout['gap']):04x}")
    lines.append(f"valuecol {layout['value_col']}")
    return "\n".join(lines) + "\n"


def build(work, src, st, layout, palette_hex):
    """src (plugin/ 의 사본, 보통 git HEAD 판) 을 work/plugin 에 베껴 고치고 gradle --offline jar. 만든 jar 경로."""
    dst = os.path.join(work, "plugin")
    if os.path.exists(os.path.join(dst, "src")):
        shutil.rmtree(os.path.join(dst, "src"))
    os.makedirs(dst, exist_ok=True)
    for name in ("build.gradle.kts", "settings.gradle.kts"):
        shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
    if not os.path.exists(os.path.join(dst, "gradle")) and os.path.exists(os.path.join(src, "gradle")):
        shutil.copytree(os.path.join(src, "gradle"), os.path.join(dst, "gradle"))
    shutil.copytree(os.path.join(src, "src"), os.path.join(dst, "src"))
    java = os.path.join(dst, "src", "main", "java", "kr", "souls")
    patch_lang_java(os.path.join(java, "Lang.java"))
    patch_item_factory(os.path.join(java, "item", "ItemFactory.java"))
    r, g, b, _ = __import__("palette").c(st.VALUE)
    with open(os.path.join(java, "item", "GothicStats.java"), "w", encoding="utf-8") as f:
        f.write(gothic_stats_java(f"0x{r:02x}{g:02x}{b:02x}"))
    res = os.path.join(dst, "src", "main", "resources")
    counts = [patch_yaml(os.path.join(res, "lang", f"{lg}.yml"), lg, st, palette_hex) for lg in ("ko", "en")]
    with open(os.path.join(res, "gothic_layout.txt"), "w", encoding="utf-8") as f:
        f.write(layout_text(layout))
    print(f"  플러그인 사본: Lang <font:>, GothicStats, tooltip_style, YAML (이름·설명·분류) {counts}")
    r = subprocess.run(["gradle", "--offline", "-q", "jar"], cwd=dst, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("gradle 실패")
    return os.path.join(dst, "build", "libs", "Soulslike.jar")
