"""
mood2_refined 의 플러그인 쪽 (작업 폴더의 사본에서만. 저장소의 plugin/ 은 건드리지 않는다).

mood_serif (1차 시안 A) 의 고리를 그대로 쓴다: Lang.java 가 lang/*.yml 의 맨 앞 꼴 태그에서 <font:이름공간:이름> 을 하나 더
받는다 (YAML 에 이 태그가 없으면 하는 일이 없다 = 기본 꺼짐). 이 시안의 사본 YAML 에만 태그를 넣는다:
  제목 글꼴 souls:title (로마 대문자 Cinzel / 굵은 명조): 무기 이름 (weapon.*.name), 시험 기술 이름, 보스 이름 (boss.*.name:
  보스 막대 왼쪽 위의 이름도 로마 대문자로. 이름의 앞 사본도 같은 꼴이라 폭이 그대로 상쇄된다), 휴식 창 제목 (bonfire.test-name),
  큰 글씨 (boss.felled, taster.end)

장식 글자 (설명 칸 이름 밑 선, 휴식 창 제목 밑 선): 언어 파일 대신 사본의 Java 가 붙인다 (RefinedDecor, lang.py 머리말)

  build(작업폴더, 저장소, 장식) → 사본에서 gradle --offline jar 로 만든 jar 경로
"""
import importlib.util
import os
import re
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
TITLE_FONT = "souls:title"
EXTRA_KEYS = ("test-name", "felled", "end")
NAME_LINE = re.compile(r'^(\s+(?:name|' + "|".join(EXTRA_KEYS) + r'): ")((?:<#[0-9a-fA-F]{6}>)?)', re.M)


def _serif_hook():
    """1차 시안 A 의 Lang.java 고리 (mood_serif/java_hook.py) 를 이름이 겹치지 않게 싣는다."""
    path = os.path.join(os.path.dirname(HERE), "mood_serif", "java_hook.py")
    spec = importlib.util.spec_from_file_location("mood_serif_java_hook", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patch_yaml(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    n = 0
    for i, line in enumerate(lines):
        new, k = NAME_LINE.subn(lambda m: m.group(1) + m.group(2) + f"<font:{TITLE_FONT}>", line)
        lines[i] = new
        n += k
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return n


DECOR_JAVA = """package kr.souls;

import net.kyori.adventure.key.Key;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.entity.Player;

/** mood2_refined 시안의 장식 글자 (pack/variants/mood2_refined/lang.py 가 만든 글자열, 리소스팩 minecraft:default 의 그림 글자). */
public final class RefinedDecor {{
    private static final Key DEFAULT = Key.key("minecraft", "default");
    private static final String ITEM = "{item}";
    private static final String TITLE_KO = "{title_ko}";
    private static final String TITLE_EN = "{title_en}";

    private RefinedDecor() {{}}

    /** 설명 칸 분류 줄 앞의 이름 밑 선 (진행 폭 0). */
    public static Component itemRule(Component line) {{
        return Component.text().decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE)
                .append(Component.text(ITEM).font(DEFAULT).color(NamedTextColor.WHITE))
                .append(line).build();
    }}

    /** 가운데 맞춘 창 제목 뒤의 제목 밑 선 (진행 폭 0, 제목 폭은 언어마다 미리 셈했다). */
    public static Component titleRule(Player p, Component title) {{
        String s = Lang.KO.equals(Lang.langOf(p)) ? TITLE_KO : TITLE_EN;
        return Component.text().append(title)
                .append(Component.text(s).font(DEFAULT).color(NamedTextColor.WHITE)).build();
    }}
}}
"""


def _java(s):
    """자바 글자열 (따옴표 안). ASCII 밖은 \\uXXXX (따옴표·역빗금은 \\u 로 쓰면 자바가 글자열 밖에서 풀어 버린다)."""
    out = ""
    for c in s:
        if c in '"\\':
            out += "\\" + c
        elif 0x20 <= ord(c) < 0x7F:
            out += c
        else:
            out += "\\u%04x" % ord(c)
    return out


def _patch(path, old, new):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    assert old in s, f"{os.path.basename(path)} 가 바뀌었다: {old[:60]}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(s.replace(old, new, 1))


def _decor(dst, decor):
    """RefinedDecor.java 를 사본에 쓰고, 무기 분류 줄 (ItemFactory) 과 휴식 창 제목 (TestCommands) 에 붙인다."""
    java = os.path.join(dst, "src", "main", "java", "kr", "souls")
    with open(os.path.join(java, "RefinedDecor.java"), "w", encoding="utf-8") as f:
        f.write(DECOR_JAVA.format(item=_java(decor["item_prefix"]), title_ko=_java(decor.get("title_suffix_ko", "")),
                                  title_en=_java(decor.get("title_suffix_en", ""))))
    _patch(os.path.join(java, "item", "ItemFactory.java"),
           'lore.add(Lang.c("weapon.class." + d.cls()));',
           'lore.add(kr.souls.RefinedDecor.itemRule(Lang.c("weapon.class." + d.cls())));')
    _patch(os.path.join(java, "cmd", "TestCommands.java"),
           'DialogBase.builder(Lang.c(p, "bonfire.test-name"))',
           'DialogBase.builder(kr.souls.RefinedDecor.titleRule(p, Lang.c(p, "bonfire.test-name")))')


def build(work, root, decor=None):
    src = os.path.join(root, "plugin")
    dst = os.path.join(work, "plugin")
    if os.path.exists(os.path.join(dst, "src")):
        shutil.rmtree(os.path.join(dst, "src"))
    os.makedirs(dst, exist_ok=True)
    for name in ("build.gradle.kts", "settings.gradle.kts", "gradlew"):
        shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
    if not os.path.exists(os.path.join(dst, "gradle")):
        shutil.copytree(os.path.join(src, "gradle"), os.path.join(dst, "gradle"))
    shutil.copytree(os.path.join(src, "src"), os.path.join(dst, "src"))
    _serif_hook()._patch_lang_java(os.path.join(dst, "src", "main", "java", "kr", "souls", "Lang.java"))
    if decor:
        _decor(dst, decor)
    n = sum(_patch_yaml(os.path.join(dst, "src", "main", "resources", "lang", f)) for f in ("ko.yml", "en.yml"))
    print(f"  플러그인 사본: Lang.java 에 <font:> 꼴, YAML {n} 줄에 <font:{TITLE_FONT}>")
    r = subprocess.run(["gradle", "--offline", "-q", "jar"], cwd=dst, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("gradle 실패")
    return os.path.join(dst, "build", "libs", "Soulslike.jar")
