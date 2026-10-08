"""
mood2_refined 의 플러그인 쪽 (작업 폴더의 사본에서만. 저장소의 plugin/ 은 건드리지 않는다).

mood_serif (1차 시안 A) 의 고리를 그대로 쓴다: Lang.java 가 lang/*.yml 의 맨 앞 꼴 태그에서 <font:이름공간:이름> 을 하나 더
받는다 (YAML 에 이 태그가 없으면 하는 일이 없다 = 기본 꺼짐). 이 시안의 사본 YAML 에만 태그를 넣는다:
  제목 글꼴 souls:title (로마 대문자 Cinzel / 굵은 명조): 무기 이름 (weapon.*.name), 시험 기술 이름, 보스 이름 (boss.*.name:
  보스 막대 왼쪽 위의 이름도 로마 대문자로. 이름의 앞 사본도 같은 꼴이라 폭이 그대로 상쇄된다), 휴식 창 제목 (bonfire.test-name),
  큰 글씨 (boss.felled, taster.end)

  build(작업폴더, 저장소) → 사본에서 gradle --offline jar 로 만든 jar 경로
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
    _serif_hook()._patch_lang_java(os.path.join(dst, "src", "main", "java", "kr", "souls", "Lang.java"))
    n = sum(_patch_yaml(os.path.join(dst, "src", "main", "resources", "lang", f)) for f in ("ko.yml", "en.yml"))
    print(f"  플러그인 사본: Lang.java 에 <font:> 꼴, YAML {n} 줄에 <font:{TITLE_FONT}>")
    r = subprocess.run(["gradle", "--offline", "-q", "jar"], cwd=dst, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit("gradle 실패")
    return os.path.join(dst, "build", "libs", "Soulslike.jar")
