#!/usr/bin/env python3
"""
문구 관문 (DESIGN.md 10.3, 10.9, 12.5, 13.7). 플레이어가 보는 글이 모두 언어 열쇠이고, 한국어 원본과 영어가 짝이 맞는지 본다.

  python3 tools/langcheck.py [--pack 팩폴더|팩.zip] [-q]

오류 (하나라도 있으면 끝 상태 1. make_dist 는 묶지 않고, run_tests 의 lang_check 가 실패한다)
  pair     lang/ko.yml 과 en.yml 의 열쇠·목록 줄 수·꼴(맨 앞 태그)·자리(<이름>) 가 같다. 꼴 태그는 맨 앞에만,
           바닐라 열쇠(vanilla.*) 는 이름 색만 (pack/langpack.py 의 problems)
  java     플러그인 Java 에 한글 글자 문자열이 없다. 서버 기록 줄 (getLogger()/log 의 info·warning·severe…) 만 된다.
           한 문장 (; 까지) 안에 기록 부르기가 있으면 기록 줄로 본다. 주석은 보지 않는다. 일부러 남길 줄에는 // lang-ok
  keys     Java 가 부르는 Lang.c / lines / render / renderBoth / tell 의 열쇠와 콘텐츠 say 부품의 key 가 lang 에 있다
  content  content/*.yml 에 한글 글이 없다 (보이는 글은 lang 열쇠로. 주석은 된다)
  pack     팩 언어 파일이 YAML 에서 만든 것과 같다 (낡은 팩): assets/souls/lang/ko_kr.json·en_us.json,
           assets/minecraft/lang/<언어>.json 의 vanilla.* 열쇠 (ko_kr 은 한국어, 나머지는 영어)
  width    글이 그 자리 폭에 들어간다 (바닐라 기본 글꼴 폭, 1280×720 GUI 배율 3 = 화면 426 픽셀 기준. SLOTS 표).
           큰 글씨는 4배로 그려져 104 픽셀, 부제목은 2배라 200 픽셀, Dialog 단추(폭 160) 150, 사망 화면 단추(폭 200) 190
경고
  slot     폭을 정하지 않은 열쇠 (SLOTS 에 더한다)
"""
import fnmatch
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACK_SRC = os.path.join(ROOT, "pack")
if PACK_SRC not in sys.path:
    sys.path.insert(0, PACK_SRC)
import langpack  # noqa: E402

JAVA = os.path.join(ROOT, "plugin", "src", "main", "java")
CONTENT = os.path.join(ROOT, "plugin", "src", "main", "resources", "content")
PACK_DIR = os.path.join(PACK_SRC, "resourcepack")
HANGUL = re.compile("[가-힣ㄱ-ㆎ]")

# ── 폭 (바닐라 기본 글꼴, 1.21.11 client.jar 의 ascii.png 에서 잰 진행 폭. 한글은 unifont 의 반 크기 8 + 1) ──
ASCII_ADV = "42466662444626266666666666225656766666666466666666666666666464663666665662653666666646666664247"
EXTRA_ADV = {"·": 2, "×": 6, "–": 7, "—": 9, "‘": 3, "’": 3, "“": 5, "”": 5, "…": 8}
SCREEN = 426   # 1280×720, GUI 배율 3 (자동)

# 자리 → 폭 (GUI 픽셀). 큰 글씨·부제목은 바닐라가 4배·2배로 그린다
SLOT_PX = {
    "title": SCREEN // 4 - 2,        # 큰 글씨 (화톳불·보스 처치·맛보기판 끝)
    "subtitle": 200,                 # 잠깐 알림 (부제목, 2배)
    "actionbar": 300,                # 행동 막대 한 줄
    "button160": 150,                # Dialog 단추 (폭 160, 10.4)
    "button200": 190,                # 사망 화면 단추 (폭 200)
    "dialog_title": 300,             # Dialog 제목
    "dialog_body": 200,              # Dialog 본문 (plain_message 기본 폭 200, 넘으면 줄이 바뀐다)
    "tooltip": 250,                  # 아이템 이름·설명 한 줄
    "screen": 400,                   # 바닐라 확인 창 제목
    "wrap": None,                    # 채팅·접속 거절·팩 창 (클라이언트가 줄을 바꾼다)
}
SLOTS = [
    ("death.title", "title"), ("bonfire.lit", "title"), ("boss.felled", "title"), ("taster.end", "title"),
    ("bonfire.enemies-back", "subtitle"), ("bonfire.refuse", "subtitle"), ("souls.recovered", "subtitle"),
    ("door.*", "subtitle"), ("bell.rung", "subtitle"), ("spell.learned", "subtitle"), ("spell.none", "subtitle"),
    ("bonfire.rest", "button160"), ("bonfire.warp", "button160"), ("bonfire.leave", "button160"), ("ending.*", "button160"),
    ("bonfire.test-name", "dialog_title"), ("origin.title", "dialog_title"),
    ("bonfire.status", "dialog_body"), ("bonfire.no-warp", "dialog_body"), ("spell.no-slot", "dialog_body"),
    ("hud.*", "actionbar"),
    ("item.*", "tooltip"), ("test.*", "tooltip"), ("skill.*", "tooltip"),
    ("vanilla.deathScreen.respawn", "button200"), ("vanilla.deathScreen.titleScreen", "button200"),
    ("vanilla.deathScreen.quit.confirm", "screen"), ("vanilla.deathScreen.score.value", "screen"),
    ("pack.*", "wrap"), ("build.*", "wrap"), ("admin.*", "wrap"),
]
# 폭을 잴 때 자리에 넣는 값 (가장 길게 나올 만한 것)
SAMPLE = {"souls": "9,999,999", "n": "9,999,999", "level": "713", "m": "999", "kind": "control", "ticks": "100"}

# 서버 기록 부르기 (이 문장 안의 한글은 기록 줄이다)
LOG_CALL = re.compile(r"(\bgetLogger\(\)|\blog|\blogger|\bLOG)\s*\.\s*(info|warning|warn|severe|error|fine|config|log)\s*\(")
LANG_CALL = re.compile(r'\bLang\.(c|lines|render|renderBoth|tell)\(\s*(?:[^,()"]+,\s*)?"([^"]+)"\s*[,)]')


def advance(ch):
    o = ord(ch)
    if 32 <= o < 127:
        return int(ASCII_ADV[o - 32])
    if HANGUL.match(ch):
        return 9
    return EXTRA_ADV.get(ch, 6)


def width(text):
    """한 줄의 폭 (GUI 픽셀). § 코드는 폭이 없다."""
    text = re.sub("§.", "", text)
    return sum(advance(c) for c in text)


def slot_of(key):
    for pat, slot in SLOTS:
        if fnmatch.fnmatchcase(key, pat):
            return slot
    return None


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, rule, where, msg):
        self.items.append((level, rule, where, msg))

    @property
    def errors(self):
        return [i for i in self.items if i[0] == "오류"]

    @property
    def warnings(self):
        return [i for i in self.items if i[0] == "경고"]

    def print(self):
        for level, rule, where, msg in self.items:
            print(f"  [{level}] {rule}: {where}: {msg}")


# ── Java ──

def java_strings(src):
    """주석을 뺀 소스에서 (문장 글, [(줄 번호, 문자열 글)]) 들을 낸다. 문장은 ; { } 로 끊는다."""
    stmts = []
    cur, lits = [], []
    i, line, n = 0, 1, len(src)
    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            i = j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            i = j
            continue
        if src.startswith('"""', i):
            j = src.find('"""', i + 3)
            j = n if j < 0 else j + 3
            lits.append((line, src[i + 3:j - 3]))
            line += src.count("\n", i, j)
            cur.append('""')
            i = j
            continue
        if c == '"' or c == "'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            if c == '"':
                lits.append((line, src[i + 1:j]))
            cur.append(c + c)
            i = j + 1
            continue
        if c == "\n":
            line += 1
        if c in ";{}":
            stmts.append(("".join(cur), lits))
            cur, lits = [], []
        else:
            cur.append(c)
        i += 1
    stmts.append(("".join(cur), lits))
    return stmts


def check_java(report, root=JAVA):
    calls = []
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            if not f.endswith(".java"):
                continue
            path = os.path.join(base, f)
            rel = os.path.relpath(path, ROOT)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            for m in LANG_CALL.finditer(src):
                calls.append((rel, src.count("\n", 0, m.start()) + 1, m.group(2)))
            ok_lines = {i for i, l in enumerate(src.split("\n"), 1) if "lang-ok" in l}
            for text, lits in java_strings(src):
                korean = [(ln, s) for ln, s in lits if HANGUL.search(s) and ln not in ok_lines]
                if not korean or LOG_CALL.search(text):
                    continue
                for ln, s in korean:
                    report.add("오류", "java", f"{rel}:{ln}", f"한글 문자열 (언어 열쇠로, 또는 서버 기록 줄로): {s[:60]!r}")
    return calls


def check_keys(report, calls, ko):
    keys = set(langpack.lines(ko)) | set(ko)
    for rel, ln, key in calls:
        if key not in keys:
            report.add("오류", "keys", f"{rel}:{ln}", f"lang 에 없는 열쇠 {key!r}")


def check_content(report, ko, root=CONTENT):
    import yaml
    keys = set(langpack.lines(ko)) | set(ko)

    def walk(node, where):
        if isinstance(node, dict):
            if node.get("type") in ("say", "message"):
                k = node.get("key")
                if not k or k not in keys:
                    report.add("오류", "keys", where, f"say 부품의 key {k!r} 가 lang 에 없다")
            for k, v in node.items():
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")
        elif isinstance(node, str) and HANGUL.search(node):
            report.add("오류", "content", where, f"콘텐츠에 한글 글 (lang 열쇠로 옮긴다): {node[:40]!r}")

    if not os.path.isdir(root):
        return
    for f in sorted(os.listdir(root)):
        if f.endswith((".yml", ".yaml")):
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                walk(yaml.safe_load(fh) or {}, os.path.relpath(os.path.join(root, f), ROOT))


def pack_reader(pack):
    """팩 폴더, zip 파일, 또는 zip 바이트 (make_dist 가 jar 안 pack.zip 을 넘긴다) → (경로 → json) 읽개. 없으면 None."""
    if isinstance(pack, (bytes, bytearray)) or (pack and os.path.isfile(pack)):
        z = zipfile.ZipFile(io.BytesIO(pack) if isinstance(pack, (bytes, bytearray)) else pack)
        names = set(z.namelist())
        return lambda rel: json.loads(z.read(rel).decode("utf-8")) if rel in names else None
    if pack and os.path.isdir(pack):
        def read(rel):
            p = os.path.join(pack, *rel.split("/"))
            if not os.path.isfile(p):
                return None
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        return read
    return None


def check_pack(report, tables, pack):
    read = pack_reader(pack)
    if read is None:
        report.add("경고", "pack", str(pack)[:80], "팩이 없어 언어 파일을 견주지 못했다 (python3 pack/gen_pack.py)")
        return
    import gen_pack
    want = langpack.build(tables, gen_pack.LANGS)
    for rel, data in sorted(want.items()):
        got = read(rel)
        if got is None:
            report.add("오류", "pack", rel, "팩에 없다")
            continue
        if rel.startswith("assets/minecraft/"):
            got = {k: v for k, v in got.items() if k in data}
        if got != data:
            diff = sorted(k for k in set(got) | set(data) if got.get(k) != data.get(k))
            report.add("오류", "pack", rel, f"YAML 에서 만든 것과 다르다 (낡은 팩, gen_pack 을 다시): {diff[:5]}")


def check_width(report, tables):
    ko = langpack.lines(tables["ko"])
    for lang in langpack.LANGS:
        for key, raw in sorted(langpack.lines(tables[lang]).items()):
            slot = slot_of(key)
            if slot is None:
                if lang == "ko":
                    report.add("경고", "slot", key, "폭을 정하지 않았다 (tools/langcheck.py 의 SLOTS)")
                continue
            px = SLOT_PX[slot]
            if px is None:
                continue
            text = langpack.split_style(raw)[1]
            for name in langpack.slots(langpack.split_style(ko.get(key, raw))[1]):
                text = text.replace(f"<{name}>", SAMPLE.get(name, "0"))
            for line in text.split("\n"):
                w = width(line)
                if w > px:
                    report.add("오류", "width", f"{lang}.yml {key}", f"{w}px > {slot} {px}px: {line!r}")


def lint(pack=PACK_DIR, quiet=False):
    report = Report()
    tables = langpack.load_all()
    for key, why in langpack.problems(tables):
        report.add("오류", "pair", key, why)
    calls = check_java(report)
    check_keys(report, calls, tables["ko"])
    check_content(report, tables["ko"])
    check_pack(report, tables, pack)
    check_width(report, tables)
    if not quiet:
        report.print()
        keys = langpack.lines(tables["ko"])
        van = sum(1 for k in keys if k.startswith(langpack.VANILLA))
        print(f"langcheck: 열쇠 {len(keys) - van}개 + 바닐라 {van}개 (ko, en), Java 열쇠 부르기 {len(calls)}곳, "
              f"오류 {len(report.errors)}, 경고 {len(report.warnings)}")
    return report


def main(argv):
    pack = PACK_DIR
    if "--pack" in argv:
        pack = argv[argv.index("--pack") + 1]
    report = lint(pack, quiet="-q" in argv)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
