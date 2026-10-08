"""
mood2_gothic 의 플러그인 쪽. 작업 폴더의 사본 (git 판의 plugin/ 을 베낀 것) 에서만 고치고 그 사본으로 jar 를 만든다.
저장소의 plugin/ 은 건드리지 않는다.

  Lang.java       YAML 꼴 태그에 <font:이름공간:이름> 을 더 받는다 (태그가 없으면 하는 일이 없다).
  GothicStats     (새 파일) 무기 설명 칸의 수치를 다크 소울 3 처럼 두 열로: 칸마다 "이름 (그 언어의 이름 열 폭까지 빈칸으로 채운
                  번역) + 빈칸 + 값 (값 열 끝에 오른쪽 맞춤)", 두 칸 사이는 열 간격 빈칸. 값 글자의 진행 폭과 빈칸 글자는 팩을
                  만들 때 잰 gothic_layout.txt (jar 안) 에서 읽는다. 우리 그림 글자는 진행 폭이 정수라 열이 픽셀까지 맞는다.
  Hud.java        보스 막대 줄: 넓은 마구리만큼 막대를 당겨 늘 가운데에서 시작하게, 마구리는 표식 색 7 (셰이더가 늘이지 않고
                  막대 끝을 따라 옮긴다).
  ItemFactory     무기 설명 칸: 수치 줄을 GothicStats 로, 수치와 설명 사이에 실선 글자, tooltip_style souls:gothic_weapon
                  (이름 밑 금실이 있는 칸).
  lang/*.yml      무기 이름·보스 이름·휴식 창 제목 → 제목 글꼴 (souls:gothic_title), 무기 설명 → 조용한 양피지빛,
                  분류 줄 → 흐린 옛 금빛, 수치 칸 이름 gothic.stat.* (두 언어).
  glyphs.yml      시안 HUD 그림 글자 표 (art_hud.py 가 막대·마구리·소울 상자·숫자를 다시 그려 폭이 바뀐다).
"""
import os
import re
import shutil
import subprocess

import lang as lang_mod
from palette import c


def palette_hex(name):
    r, g, b, _ = c(name)
    return f"#{r:02x}{g:02x}{b:02x}"


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
             "    /** 꼴 태그 &lt;font:이름공간:이름&gt; (UI 분위기 시안 mood2_gothic) */\n"
             "    private static final Pattern FONT = Pattern.compile(\"[a-z0-9_.-]+:[a-z0-9_./-]+\");\n", "Lang.HEX")
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


def patch_item_factory(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    s = _sub(s, "        lore.addAll(statLines(d));\n        lore.add(Component.empty());\n",
             "        lore.addAll(GothicStats.lines(d));\n"
             "        lore.add(Lang.c(\"gothic.lore-rule\").color(TextColor.color(0xFFFFFF)));"
             " // 그림 글자: 흰색이라야 그림 색 그대로\n", "ItemFactory.weapon 수치")
    s = _sub(s, "        it.setData(DataComponentTypes.LORE, ItemLore.lore(lore));\n        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);\n"
                "        it.setData(DataComponentTypes.DAMAGE_RESISTANT",
             "        it.setData(DataComponentTypes.LORE, ItemLore.lore(lore));\n"
             "        it.setData(DataComponentTypes.TOOLTIP_STYLE, Key.key(Keys.NS, \"gothic_weapon\"));\n"
             "        it.setData(DataComponentTypes.MAX_STACK_SIZE, 1);\n"
             "        it.setData(DataComponentTypes.DAMAGE_RESISTANT", "ItemFactory.weapon 칸")
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


BOSS_LINE_OLD = """        int half = w / 2;
        Line l = new Line();
        l.move(-half - 2);
        l.glyph("boss_cap_l");
        l.runs("boss_hp_fill_", fill);
        l.runs("boss_hp_trail_", trail);
        l.runs("boss_hp_empty_", w - fill - trail);
        l.glyph("boss_cap_r");
        l.move(-half - l.pen);
        l.runs("boss_post_fill_", post);
        l.runs("boss_post_empty_", w - post);
        l.move(-half - l.pen);
        Line tail = new Line();
        tail.move(half);
        ShadowColor shadow = ShadowColor.shadowColor(0xFF000000 | lay.markBossShadow().value());
        return Component.text()
                .append(name.color(lay.markHidden()).shadowColor(ShadowColor.none()))
                .append(l.component(lay.markBoss()))
                .append(name.color(lay.markBossName()).shadowColor(shadow))
                .append(tail.component(lay.markBoss()))
                .build();
"""

BOSS_LINE_NEW = """        // UI 분위기 시안 mood2_gothic: 마구리가 넓은 단조 장식이라 (1) 막대가 늘 가운데 - half 에서 시작하게 왼쪽 마구리 폭만큼
        // 앞으로 당기고, (2) 마구리는 표식 색 7 로 따로 보내 셰이더가 늘이지 않고 막대 끝을 따라 통째로 옮기게 한다.
        int half = w / 2;
        Glyphs.Glyph capL = Glyphs.get("boss_cap_l");
        int capW = capL == null ? 2 : capL.width() - 1;
        net.kyori.adventure.text.format.TextColor capMark = net.kyori.adventure.text.format.TextColor.color(
                lay.markBoss().red(), lay.markBoss().green(), 7);
        Line c1 = new Line();
        c1.move(-half - capW);
        c1.glyph("boss_cap_l");
        int pen = c1.pen;
        Line b1 = new Line();
        b1.runs("boss_hp_fill_", fill);
        b1.runs("boss_hp_trail_", trail);
        b1.runs("boss_hp_empty_", w - fill - trail);
        pen += b1.pen;
        Line c2 = new Line();
        c2.glyph("boss_cap_r");
        pen += c2.pen;
        Line b2 = new Line();
        b2.move(-half - pen);
        b2.runs("boss_post_fill_", post);
        b2.runs("boss_post_empty_", w - post);
        b2.move(-half - (pen + b2.pen));
        Line tail = new Line();
        tail.move(half);
        ShadowColor shadow = ShadowColor.shadowColor(0xFF000000 | lay.markBossShadow().value());
        return Component.text()
                .append(name.color(lay.markHidden()).shadowColor(ShadowColor.none()))
                .append(c1.component(capMark))
                .append(b1.component(lay.markBoss()))
                .append(c2.component(capMark))
                .append(b2.component(lay.markBoss()))
                .append(name.color(lay.markBossName()).shadowColor(shadow))
                .append(tail.component(lay.markBoss()))
                .build();
"""


def patch_hud(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    s = _sub(s, BOSS_LINE_OLD, BOSS_LINE_NEW, "Hud.bossLine")
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
 * UI 분위기 시안 mood2_gothic: 무기 설명 칸의 수치를 다크 소울 3 처럼 두 열로 (이름은 왼쪽, 값은 열 끝에 오른쪽 맞춤).
 * 이름 번역 (souls.gothic.stat.*) 은 팩이 그 언어의 이름 열 폭까지 빈칸으로 채워 두었다. 값의 폭은 팩을 만들 때 잰
 * 글자 폭 표 (jar 안 gothic_layout.txt) 로 셈해 값 앞을 빈칸 글자로 채운다.
 */
final class GothicStats {{
    private static final TextColor VALUE = TextColor.color({value_hex});
    private static final Map<Character, Integer> ADV = new LinkedHashMap<>();
    private static final List<Map.Entry<String, Integer>> PADS = new ArrayList<>();
    private static String gap = " ";
    private static int valueCol = 18;

    static {{
        try (InputStream in = GothicStats.class.getResourceAsStream("/gothic_layout.txt")) {{
            if (in != null) {{
                BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
                String line;
                while ((line = r.readLine()) != null) {{
                    String[] p = line.trim().split(" ");
                    if (p.length < 2 || p[0].startsWith("#")) continue;
                    switch (p[0]) {{
                        case "value" -> ADV.put((char) Integer.parseInt(p[1], 16), Integer.parseInt(p[2]));
                        case "pad" -> PADS.add(Map.entry(String.valueOf((char) Integer.parseInt(p[1], 16)), Integer.parseInt(p[2])));
                        case "gap" -> gap = String.valueOf((char) Integer.parseInt(p[1], 16));
                        case "valuecol" -> valueCol = Integer.parseInt(p[1]);
                        default -> {{ }}
                    }}
                }}
            }}
        }} catch (Exception ignored) {{
            // 표가 없으면 빈칸 하나로 (가지런하지 않을 뿐 글은 다 보인다)
        }}
        PADS.sort((a, b) -> Integer.compare(b.getValue(), a.getValue()));
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
        if (cells.size() % 2 == 1) cells.add(null);
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
        int w = 0;
        for (char ch : value.toCharArray()) w += ADV.getOrDefault(ch, 5);
        int left = Math.max(0, valueCol - w);
        StringBuilder b = new StringBuilder();
        for (Map.Entry<String, Integer> p : PADS) {{
            while (left >= p.getValue()) {{
                b.append(p.getKey());
                left -= p.getValue();
            }}
        }}
        return b.toString();
    }}
}}
"""


def patch_yaml(path, lng, st):
    """무기 이름·보스 이름·휴식 창 제목 → 제목 글꼴, 무기 설명 색, 분류 줄 색, 수치 칸 이름."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out = []
    section = None
    sub = None
    n = {"name": 0, "lore": 0, "class": 0, "boss": 0, "rest": 0}
    font = f"<font:{st.FONT_TITLE}>"
    for line in lines:
        if line and not line.startswith(" ") and not line.startswith("#"):
            section = line.split(":")[0]
        m = re.match(r"^  ([a-z_-]+):", line)
        if m:
            sub = m.group(1)
        if section == "weapon":
            m = re.match(r'^(    name: ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
            if m:
                line = m.group(1) + f"<{palette_hex(st.NAME)}>{font}" + m.group(3)
                n["name"] += 1
            m = re.match(r'^(      - ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
            if m:
                line = m.group(1) + f"<{palette_hex(st.LORE_INK)}>" + m.group(3)
                n["lore"] += 1
            if sub == "class":
                m = re.match(r'^(    [a-z_]+: ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
                if m:
                    line = m.group(1) + f"<{palette_hex(st.CLASS)}>" + m.group(3)
                    n["class"] += 1
        if section == "boss":
            m = re.match(r'^(    name: ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
            if m:
                line = m.group(1) + (m.group(2) or "") + font + m.group(3)
                n["boss"] += 1
        if section == "bonfire":
            m = re.match(r'^(  test-name: ")(<#[0-9a-fA-F]{6}>)?(.*)$', line)
            if m:
                line = m.group(1) + f"<{palette_hex(st.NAME)}>{font}" + m.group(3)
                n["rest"] += 1
        out.append(line)
    i = 0 if lng == "ko" else 1
    add = ["", "gothic:", "  # UI 분위기 시안 mood2_gothic: 수치와 설명 사이 실선 (팩의 언어 파일이 실선 그림 글자로 바꾼다)",
           '  lore-rule: " "',
           "  # 무기 설명 칸의 수치 이름 (팩이 이름 열 폭까지 빈칸으로 채운다)", "  stat:"]
    for k, v in lang_mod.STAT_LABELS.items():
        add.append(f'    {k}: "<{palette_hex(st.LABEL)}>{v[i]}"')
    text = "\n".join(out).rstrip("\n") + "\n" + "\n".join(add) + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return n


def layout_text(layout):
    lines = ["# mood2_gothic: 무기 설명 칸 수치 열 (pack/variants/mood2_gothic/lang.py 가 잰 값, GUI 픽셀)"]
    for ch, adv in layout["values"].items():
        lines.append(f"value {ord(ch):04x} {int(adv)}")
    for ch, adv in layout["pads"].items():
        lines.append(f"pad {ord(ch):04x} {int(adv)}")
    lines.append(f"gap {ord(layout['gap']):04x}")
    lines.append(f"valuecol {int(layout['value_col'])}")
    return "\n".join(lines) + "\n"


def build(work, src, st, layout, glyphs_yml=None):
    """src (plugin/ 의 사본) 을 work/plugin 에 베껴 고치고 gradle --offline jar. 만든 jar 경로."""
    dst = os.path.join(work, "plugin")
    if os.path.exists(os.path.join(dst, "src")):
        shutil.rmtree(os.path.join(dst, "src"))
    os.makedirs(dst, exist_ok=True)
    for name in ("build.gradle.kts", "settings.gradle.kts", "gradle.properties"):
        if os.path.exists(os.path.join(src, name)):
            shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
    if not os.path.exists(os.path.join(dst, "gradle")) and os.path.exists(os.path.join(src, "gradle")):
        shutil.copytree(os.path.join(src, "gradle"), os.path.join(dst, "gradle"))
    shutil.copytree(os.path.join(src, "src"), os.path.join(dst, "src"))
    java = os.path.join(dst, "src", "main", "java", "kr", "souls")
    patch_lang_java(os.path.join(java, "Lang.java"))
    patch_item_factory(os.path.join(java, "item", "ItemFactory.java"))
    patch_hud(os.path.join(java, "hud", "Hud.java"))
    r, g, b, _ = c(st.VALUE)
    with open(os.path.join(java, "item", "GothicStats.java"), "w", encoding="utf-8") as f:
        f.write(gothic_stats_java(f"0x{r:02x}{g:02x}{b:02x}"))
    res = os.path.join(dst, "src", "main", "resources")
    counts = {lg: patch_yaml(os.path.join(res, "lang", f"{lg}.yml"), lg, st) for lg in ("ko", "en")}
    with open(os.path.join(res, "gothic_layout.txt"), "w", encoding="utf-8") as f:
        f.write(layout_text(layout))
    if glyphs_yml:
        with open(os.path.join(res, "glyphs.yml"), "w", encoding="utf-8", newline="\n") as f:
            f.write(glyphs_yml)
    print(f"  플러그인 사본: Lang <font:>, GothicStats, tooltip_style, YAML {counts}")
    r = subprocess.run(["gradle", "--offline", "-q", "jar"], cwd=dst, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("gradle 실패")
    return os.path.join(dst, "build", "libs", "Soulslike.jar")
