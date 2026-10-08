"""
mood_serif 의 플러그인 쪽 (작업 폴더의 사본에서만. 저장소의 plugin/ 은 건드리지 않는다).

제목 글꼴 souls:title (Cinzel + 굵은 명조) 은 플러그인이 보내는 글 (아이템 이름, 보스 이름, 휴식 창 제목, 큰 글씨) 에만 입힌다.
lang/*.yml 의 꼴 태그에 <font:이름공간:이름> 하나를 더 받게 하는 작은 고리를 Lang.java 에 단다 (YAML 에 이 태그가 없으면 하는 일이
없다 = 기본 꺼짐). 이 시안의 사본 YAML 에만 태그를 넣는다:
  weapon.*.name, boss.*.name, 시험 기술 이름 (모든 "name:" 줄), bonfire.test-name, boss.felled, taster.end

  build(작업폴더) → 사본에서 gradle --offline jar 로 만든 jar 경로
"""
import os
import re
import shutil
import subprocess

TITLE_FONT = "souls:title"
EXTRA_KEYS = ("test-name", "felled", "end")


def _patch_lang_java(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    a = ("    static boolean isStyleTag(String t) {\n"
         "        String n = t.startsWith(\"!\") ? t.substring(1) : t;\n")
    assert a in s, "Lang.isStyleTag 이 바뀌었다"
    s = s.replace(a, a + "        if (n.startsWith(\"font:\")) return !t.startsWith(\"!\") && FONT.matcher(n.substring(5)).matches();\n", 1)
    b = "            if (HEX.matcher(n).matches()) b.color(TextColor.fromHexString(n));\n"
    assert b in s, "Lang.style 이 바뀌었다"
    s = s.replace(b, "            if (n.startsWith(\"font:\")) b.font(net.kyori.adventure.key.Key.key(n.substring(5)));\n"
                     "            else " + b.lstrip(), 1)
    c = "    private static final Pattern HEX = Pattern.compile(\"#[0-9a-fA-F]{6}\");\n"
    assert c in s
    s = s.replace(c, c + "    /** 꼴 태그 &lt;font:이름공간:이름&gt; (mood_serif 시안의 제목 글꼴) */\n"
                         "    private static final Pattern FONT = Pattern.compile(\"[a-z0-9_.-]+:[a-z0-9_./-]+\");\n", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


NAME_LINE = re.compile(r'^(\s+(?:name|' + "|".join(EXTRA_KEYS) + r'): ")((?:<#[0-9a-fA-F]{6}>)?)', re.M)


def _patch_yaml(path):
    with open(path, encoding="utf-8") as f:
        s = f.read()
    s, n = NAME_LINE.subn(lambda m: m.group(1) + m.group(2) + f"<font:{TITLE_FONT}>", s)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    return n


def build(work, root):
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
    _patch_lang_java(os.path.join(dst, "src", "main", "java", "kr", "souls", "Lang.java"))
    n = sum(_patch_yaml(os.path.join(dst, "src", "main", "resources", "lang", f)) for f in ("ko.yml", "en.yml"))
    print(f"  플러그인 사본: Lang.java 에 <font:> 꼴, YAML {n} 줄에 <font:{TITLE_FONT}>")
    r = subprocess.run(["gradle", "--offline", "-q", "jar"], cwd=dst, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("gradle 실패")
    return os.path.join(dst, "build", "libs", "Soulslike.jar")
