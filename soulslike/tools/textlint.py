#!/usr/bin/env python3
"""
글 검사기 (DESIGN.md 13.7, ART_DIRECTION.md 의 글 규칙과 "영어판"). 게임 안 문구가 짧고 건조한지 기계로 먼저 거른다.

  python3 tools/textlint.py [yml·json 파일 또는 폴더 ...]

  기본으로 보는 곳
    plugin/src/main/resources/lang/ko.yml, en.yml   게임 문구 (10.3). 한국어가 원본, 영어는 따로 쓴 것
    plugin/src/main/resources/content/*.yml         콘텐츠 (보이는 글은 lang 으로 옮겼다. 남은 한글이 있으면 본다)
  팩 언어 파일 (pack/resourcepack/assets/*/lang/*.json) 은 이 YAML 에서 만들어지므로 기본으로는 보지 않는다
  (YAML 과 같은지는 tools/langcheck.py 가 본다). 인수로 주면 본다.

한국어 (한글이 든 문자열)
  오류  exclaim 느낌표, emoji 이모지, hype 금지어 (전설, 궁극, 압도, 최강, 강력한),
        explain 설명문체 어미 (습니다, 할 수 있, 입니다)
  경고  lines 설명(lore, desc, description …)이 4줄 넘음, long 한 줄이 32자 넘음,
        cliche 이름이 "어둠의", "그림자", "빛의" 로 시작, dupname 같은 이름이 두 번 넘게 나옴
영어 (en.yml, en_us.json 의 글)
  오류  exclaim 느낌표, emoji 이모지, hype 과장어 (legendary, ultimate, epic, mighty, powerful …),
        slang 현대 구어 (okay, cool, gonna, awesome …), explain 설명문체 (you can, allows you, lets you, please …)
  경고  long 한 줄이 48자 넘음 (폭은 tools/langcheck.py 가 픽셀로 잰다), lines
이름 (lang/names.yml)
  오류  name: ko.yml 의 열쇠에 고유 이름이 있으면 en.yml 의 같은 열쇠에 정한 영어 이름이 있어야 한다

  MiniMessage 태그(<red>, <!italic>)와 자리(<souls>), § 색 코드는 지우고 잰다. YAML 주석은 보지 않는다.
"""
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "plugin", "src", "main", "resources")
DEFAULT_PATHS = [
    os.path.join(RES, "lang", "ko.yml"),
    os.path.join(RES, "lang", "en.yml"),
    os.path.join(RES, "content"),
]
NAMES = os.path.join(RES, "lang", "names.yml")
ENGLISH_FILES = ("en.yml", "en_us.json")

HYPE = ("전설", "궁극", "압도", "최강", "강력한")
EXPLAIN = ("습니다", "할 수 있", "입니다")
CLICHE = ("어둠의", "그림자", "빛의")
EXCLAIM = ("!", "\uff01")
MAX_LINES = 4
MAX_LINE = 32
MAX_LINE_EN = 48
# 영어 (소울류 영어판 문체: 짧고 건조한 옛 말투). 낱말 단위, 대소문자 가리지 않는다
HYPE_EN = ("legendary", "ultimate", "epic", "mighty", "powerful", "overwhelming", "unstoppable", "invincible",
           "supreme", "godlike", "awesome", "amazing", "incredible", "insane", "unbelievable", "ultra", "mega",
           "super", "strongest", "greatest", "overpowered", "badass", "devastating", "epicness", "op")
SLANG_EN = ("ok", "okay", "cool", "lol", "gg", "dude", "guys", "gonna", "wanna", "gotta", "yeah", "yep", "nope",
            "hey", "wow", "oops", "btw", "kinda", "sorta", "lmao", "omg", "noob", "stuff", "nah")
EXPLAIN_EN = ("you can", "can be used", "allows you", "lets you", "is able to", "will allow", "please", "click here",
              "make sure", "don't forget")

NAME_KEYS = {"name", "display", "display_name", "title"}
DESC_KEYS = {"lore", "desc", "description", "flavor", "text", "lines"}

EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2300, 0x23FF), (0x2B50, 0x2B55),
                (0xFE0F, 0xFE0F), (0x200D, 0x200D))
HANGUL = re.compile("[\uac00-\ud7a3\u3131-\u318e]")
TAG = re.compile(r"<[^<>]*>")
FORMAT = re.compile(r"%(\d+\$)?s|%%")
LATIN_WORD = re.compile(r"[A-Za-z']+")
LEGACY = re.compile("[\u00a7&][0-9a-fk-orx]", re.I)


class Report:
    def __init__(self):
        self.items = []   # (등급, 파일, 키, 규칙, 글)

    def add(self, level, path, key, rule, msg):
        self.items.append((level, path, key, rule, msg))

    @property
    def errors(self):
        return [i for i in self.items if i[0] == "오류"]

    @property
    def warnings(self):
        return [i for i in self.items if i[0] == "경고"]

    def print(self):
        for level, path, key, rule, msg in self.items:
            print(f"  [{level}] {show(path)}: {key}: {rule} — {msg}")


def show(path):
    """저장소 안이면 soulslike/ 기준 경로, 밖이면 그대로."""
    rel = os.path.relpath(os.path.abspath(path), ROOT)
    return path if rel.startswith("..") else rel


def plain(s):
    """태그·자리·번역 인수와 색 코드를 지운 보이는 글."""
    return FORMAT.sub("", LEGACY.sub("", TAG.sub("", s)))


def is_english(path):
    return os.path.basename(path) in ENGLISH_FILES


def is_emoji(ch):
    o = ord(ch)
    return any(a <= o <= b for a, b in EMOJI_RANGES)


def walk(node, key=""):
    """YAML/JSON 트리의 (점으로 이은 키, 마지막 키 이름, 값) 를 모두 낸다. 목록은 [i] 로 적는다."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{key}.{k}" if key else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{key}[{i}]")
    else:
        yield key, node


def last_key(key):
    """'items.rusted_key.lore[2]' → 'lore'"""
    return re.sub(r"\[\d+\]$", "", key).split(".")[-1]


def check_english(report, path, key, text):
    vis = plain(text)
    if any(e in vis for e in EXCLAIM):
        report.add("오류", path, key, "exclaim", f"느낌표: {vis!r}")
    emo = sorted({ch for ch in vis if is_emoji(ch)})
    if emo:
        report.add("오류", path, key, "emoji", f"이모지 {' '.join(emo)}: {vis!r}")
    if HANGUL.search(vis):
        report.add("오류", path, key, "hangul", f"영어 글에 한글: {vis!r}")
    words = [w.lower().strip("'") for w in LATIN_WORD.findall(vis)]
    for w in HYPE_EN:
        if w in words:
            report.add("오류", path, key, "hype", f"과장어 '{w}': {vis!r}")
    for w in SLANG_EN:
        if w in words:
            report.add("오류", path, key, "slang", f"현대 구어 '{w}': {vis!r}")
    low = " ".join(words)
    for w in EXPLAIN_EN:
        if re.search(r"\b" + re.escape(w.replace("'", "")) + r"\b", low.replace("'", "")):
            report.add("오류", path, key, "explain", f"설명문체 '{w}': {vis!r}")
    for line in vis.split("\n"):
        if len(line) > MAX_LINE_EN:
            report.add("경고", path, key, "long", f"{len(line)}자 (>{MAX_LINE_EN}): {line!r}")


def check_text(report, path, key, text):
    if is_english(path):
        check_english(report, path, key, text)
        return
    vis = plain(text)
    if not HANGUL.search(vis):
        return
    if any(e in vis for e in EXCLAIM):
        report.add("오류", path, key, "exclaim", f"느낌표: {vis!r}")
    emo = sorted({ch for ch in vis if is_emoji(ch)})
    if emo:
        report.add("오류", path, key, "emoji", f"이모지 {' '.join(emo)}: {vis!r}")
    for w in HYPE:
        if w in vis:
            report.add("오류", path, key, "hype", f"금지어 '{w}': {vis!r}")
    for w in EXPLAIN:
        if w in vis:
            report.add("오류", path, key, "explain", f"설명문체 '{w}': {vis!r}")
    for line in vis.split("\n"):
        if len(line) > MAX_LINE:
            report.add("경고", path, key, "long", f"{len(line)}자 (>{MAX_LINE}): {line!r}")


def load(path):
    with open(path, encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        return yaml.safe_load(f)


def lint_file(report, path, names):
    try:
        data = load(path)
    except Exception as ex:
        report.add("오류", path, "-", "parse", f"읽지 못했다: {ex}")
        return
    if data is None:
        return
    desc_lines = {}
    for key, val in walk(data):
        if not isinstance(val, str):
            continue
        check_text(report, path, key, val)
        lk = last_key(key)
        if lk in NAME_KEYS and HANGUL.search(plain(val)):
            name = plain(val).strip()
            names.setdefault(name, []).append((path, key))
            for c in CLICHE:
                if name.startswith(c):
                    report.add("경고", path, key, "cliche", f"흔한 이름 '{c}…': {name!r}")
        if lk in DESC_KEYS:
            parent = re.sub(r"\[\d+\]$", "", key)
            desc_lines[parent] = desc_lines.get(parent, 0) + len(plain(val).rstrip("\n").split("\n"))
    for parent, n in desc_lines.items():
        if n > MAX_LINES:
            report.add("경고", path, parent, "lines", f"설명 {n}줄 (>{MAX_LINES})")


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for base, dirs, fs in os.walk(p):
                dirs.sort()
                files += [os.path.join(base, f) for f in sorted(fs) if f.endswith((".yml", ".yaml", ".json"))]
        elif os.path.exists(p):
            files.append(p)
    return files


def load_names(path=NAMES):
    """lang/names.yml 의 {한국어 이름: 영어 이름}. 긴 이름부터."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        table = (yaml.safe_load(f) or {}).get("names") or {}
    return sorted(((str(k), str(v)) for k, v in table.items()), key=lambda kv: -len(kv[0]))


def check_names(report, ko_path, en_path, names):
    """ko.yml 열쇠의 고유 이름 → en.yml 같은 열쇠에 정한 영어 이름. 이름 앞이 한글이면 (돌아오다의 '오다') 이름이 아니다."""
    try:
        ko = flat_strings(load(ko_path))
        en = flat_strings(load(en_path))
    except Exception as ex:
        report.add("오류", ko_path, "-", "parse", f"읽지 못했다: {ex}")
        return
    for key, text in ko.items():
        vis = plain(text)
        target = plain(en.get(key, "")).lower()
        for kname, ename in names:
            pat = re.compile(r"(?<![\uac00-\ud7a3])" + re.escape(kname))
            if not pat.search(vis):
                continue
            vis = pat.sub(" ", vis)     # 긴 이름이 먹은 자리 (볼크 탑옥 → 탑옥은 다시 세지 않는다)
            if ename.lower() not in target:
                report.add("오류", en_path, key, "name", f"'{kname}' 은 영어로 '{ename}' (names.yml): {plain(en.get(key, ''))!r}")


def flat_strings(data):
    out = {}
    for key, val in walk(data):
        if isinstance(val, str):
            out[key] = val
    return out


def lint(paths=None, quiet=False):
    paths = paths or DEFAULT_PATHS
    report = Report()
    names = {}
    files = collect(paths)
    for f in files:
        lint_file(report, f, names)
    ko_path = next((f for f in files if os.path.basename(f) == "ko.yml"), None)
    en_path = next((f for f in files if os.path.basename(f) == "en.yml"), None)
    if ko_path and en_path:
        check_names(report, ko_path, en_path, load_names())
    for name, where in sorted(names.items()):
        if len(where) > 1:
            locs = ", ".join(f"{show(p)}:{k}" for p, k in where[:3])
            report.add("경고", where[0][0], where[0][1], "dupname", f"이름 {name!r} 이 {len(where)}번: {locs}")
    if not quiet:
        report.print()
        print(f"textlint: 파일 {len(files)}개, 오류 {len(report.errors)}, 경고 {len(report.warnings)}")
    return report


def main(argv):
    report = lint(argv or None)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
