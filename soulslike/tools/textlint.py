#!/usr/bin/env python3
"""
글 검사기 (DESIGN.md 13.7, ART_DIRECTION.md 의 글 규칙). 게임 안 한국어 문구가 짧고 건조한지 기계로 먼저 거른다.

  python3 tools/textlint.py [yml·json 파일 또는 폴더 ...]

  기본으로 보는 곳
    plugin/src/main/resources/lang/ko.yml        시스템 문구 (10.3)
    plugin/src/main/resources/content/*.yml      아이템·장소·적·대사
    pack/resourcepack/assets/minecraft/lang/ko_kr.json   리소스팩이 덮어쓰는 사망 화면 문구 (있으면)

오류 (하나라도 있으면 끝 상태 1, make_dist 는 묶지 않는다)
  exclaim    느낌표
  emoji      이모지
  hype       금지어: 전설, 궁극, 압도, 최강, 강력한
  explain    설명문체 어미: 습니다, 할 수 있, 입니다
경고
  lines      설명(lore, desc, description …)이 4줄 넘음
  long       한 줄이 32자 넘음
  cliche     이름이 "어둠의", "그림자", "빛의" 로 시작
  dupname    같은 이름이 두 번 넘게 나옴

  한글이 든 문자열만 본다 (id, 재료 이름, 소리 이름 같은 값은 건너뛴다).
  MiniMessage 태그(<red>, <!italic>)와 § 색 코드는 지우고 잰다. YAML 주석은 보지 않는다.
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
    os.path.join(RES, "content"),
    os.path.join(ROOT, "pack", "resourcepack", "assets", "minecraft", "lang", "ko_kr.json"),
]

HYPE = ("전설", "궁극", "압도", "최강", "강력한")
EXPLAIN = ("습니다", "할 수 있", "입니다")
CLICHE = ("어둠의", "그림자", "빛의")
EXCLAIM = ("!", "\uff01")
MAX_LINES = 4
MAX_LINE = 32

NAME_KEYS = {"name", "display", "display_name", "title"}
DESC_KEYS = {"lore", "desc", "description", "flavor", "text", "lines"}

EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2300, 0x23FF), (0x2B50, 0x2B55),
                (0xFE0F, 0xFE0F), (0x200D, 0x200D))
HANGUL = re.compile("[\uac00-\ud7a3\u3131-\u318e]")
TAG = re.compile(r"<[^<>]*>")
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
    """태그와 색 코드를 지운 보이는 글."""
    return LEGACY.sub("", TAG.sub("", s))


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


def check_text(report, path, key, text):
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


def lint(paths=None, quiet=False):
    paths = paths or DEFAULT_PATHS
    report = Report()
    names = {}
    files = collect(paths)
    for f in files:
        lint_file(report, f, names)
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
