#!/usr/bin/env python3
"""
문구 관문 (DESIGN.md 10.3, 10.9, 12.5, 13.7). 플레이어가 보는 글이 모두 언어 열쇠이고, 한국어 원본과 영어가 짝이 맞는지 본다.

  python3 tools/langcheck.py [--pack 팩폴더|팩.zip] [-q]

오류 (하나라도 있으면 끝 상태 1. make_dist 는 묶지 않고, run_tests 의 lang_check 가 실패한다)
  pair     lang/ko.yml 과 en.yml 의 열쇠·목록 줄 수·꼴(맨 앞 태그)·자리(<이름>) 가 같다. 꼴 태그는 맨 앞에만,
           바닐라 열쇠(vanilla.*) 는 이름 색만, 자리 이름에 MiniMessage 태그 이름(<i>, <br>, <reset> …) 을 쓰지 않는다,
           값은 모두 글 (따옴표 없는 Yes·No·12 는 YAML 이 참거짓·수로 읽는다) (pack/langpack.py 의 problems)
  java     플러그인 Java 에 한글 문자열이 없다 (\\uXXXX 로 적은 것도 푼다). 서버 기록 부르기 (getLogger()/log 의
           info·warning·severe…) 의 괄호 안만 된다. 주석은 보지 않는다. 일부러 남길 줄에는 // lang-ok
  text     번역되지 않는 글: Component.text / Text.mm 에 글자 (로마자·한글) 가 든 문자열, sendMessage·kick·disconnect·
           disallow 같은 곳에 바로 넣은 문자열. 기계 글 (시험 줄 [T], /souls 의 쓰는 법·pack·perf) 은 그 줄에 // lang-machine
  keys     열쇠를 받는 부르기 (KEY_CALLS: Lang.c / lines / render / renderBoth / tell / variant, Items.icon) 를 괄호를 세어 읽는다.
           열쇠가 글자 그대로면 lang 에 있어야 하고, 넘기는 자리 이름 ("n", n 짝) 이 그 열쇠의 자리와 같아야 한다.
           열쇠를 만들어 부르면 ("skill." + id + ".name") 그 줄에 // lang-dyn: <glob>, … 가 있어야 한다: glob 은 lang
           열쇠에 맞거나 콘텐츠 표 (CONTENT_KEYS) 의 꼴. say 는 콘텐츠 say 부품의 key, param 은 열쇠를 넘기는 도우미.
           콘텐츠: say 부품의 key 가 lang 에 있고 자리가 없다, 콘텐츠 id 마다 CONTENT_KEYS 의 열쇠가 있다 (12.5 의 표:
           skills.yml → skill.<id>.name 한 줄, skill.<id>.desc 목록)
  content  content/*.yml 에 한글 글이 없고 글 칸 (name, description, lore, text …) 이 없다 (글자와 상관없이)
  pack     팩 언어 파일이 YAML 에서 만든 것과 같다 (낡은 팩): assets/souls/lang/ko_kr.json·en_us.json,
           assets/minecraft/lang/<언어>.json 의 vanilla.* 열쇠 (ko_kr 은 한국어, 나머지는 영어). 창 제목의 제목 글자, 제목 밑
           금실, 무기 수치 이름의 열 맞춤 빈칸, 무기 설명 칸 실선 (weapon.rule), ko_kr 의 한글 가운뎃점은 검사하는 팩의 글꼴로
           gen_pack 과 같은 셈을 해 견준다 (pack/typeset.py)
  width    글이 그 자리 폭에 들어간다 (1280×720 GUI 배율 3 = 화면 426 픽셀 기준. SLOTS 표). 폭은 팩의 글꼴 (본문 가라몽·명조,
           꼴 태그 <font:souls:title> 이나 창 제목은 제목 글꼴) 로 잰다. 팩이 없거나 팩 글꼴에 없는 글자면 바닐라 기본 글꼴 폭.
           큰 글씨는 4배로 그려져 104 픽셀, 부제목은 2배라 200 픽셀, Dialog 단추(폭 160) 150, 사망 화면 단추(폭 200) 190
경고
  slot     폭을 정하지 않은 열쇠 (SLOTS 에 더한다)
  content  CONTENT_KEYS 에 없는 콘텐츠 파일, 콘텐츠에 없는 id 의 열쇠가 lang 에 남음
끝 줄에 Java 열쇠 부르기를 글자 그대로 본 곳과 lang-dyn 으로 본 곳으로 나눠 센다.
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
import typeset  # noqa: E402

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
    "dialog_body": 184,              # Dialog 본문 (plain_message 기본 폭 200. 바닐라 FocusableTextWidget 의 안쪽 여백 4×4 를 빼면 184 에서 줄이 바뀐다)
    "tooltip": 250,                  # 아이템 이름·설명 한 줄
    "screen": 400,                   # 바닐라 확인 창 제목
    "container_title": 72,           # 창 제목 (인벤토리의 "제작" 은 x 97 에서 판 안쪽 끝 168 까지, 10.4)
    "container_title_wide": 150,     # 판 왼쪽 (x 8) 에서 시작하는 창 제목 (상자·통·보관함, 판 안쪽 끝 168 까지)
    "boss_name": 200,                # 보스 막대 이름 (막대 왼쪽 끝 위, 늘이기 전 막대 폭 200 안, 10.2)
    "button150": 140,                # Dialog 단추 폭 150 (레벨 올리기 능력치 단추, 출신 확인 창, 5.9)
    "button250": 240,                # Dialog 단추 폭 250 (세계를 정한다 창의 난이도 단추, 5.7)
    "dialog_body300": 284,           # 폭 300 Dialog 본문 (세계를 정한다·레벨 올리기·능력치 창의 표, 5.9. 글이 서는 폭 300 − 16)
    "dialog_body320": 304,           # 폭 320 Dialog 본문 (출신 창 머리줄과 출신 줄, 5.10. 글이 서는 폭 320 − 16)
    "button_tip": 170,               # Dialog 단추 설명 칸 (클라이언트가 170 에서 줄을 바꾼다: 넘지 않게 쓴다)
    "wrap": None,                    # 채팅·접속 거절·팩 창 (클라이언트가 줄을 바꾼다)
}
SLOTS = [
    ("death.title", "title"), ("bonfire.lit", "title"), ("boss.felled", "title"), ("taster.end", "title"),
    ("bonfire.enemies-back", "subtitle"), ("bonfire.refuse", "subtitle"), ("souls.recovered", "subtitle"),
    ("door.*", "subtitle"), ("bell.rung", "subtitle"), ("spell.learned", "subtitle"), ("spell.none", "subtitle"),
    ("bonfire.rest", "button160"), ("bonfire.warp", "button160"), ("bonfire.leave", "button160"), ("ending.*", "button160"),
    ("bonfire.test-name", "dialog_title"), ("origin.title", "dialog_title"),
    # 시작 설정·출신·능력치·레벨 올리기 (5.7~5.10)
    ("bonfire.repick-tip", "button_tip"), ("bonfire.levelup", "button160"), ("bonfire.settings", "button160"),
    ("bonfire.stats", "button160"), ("bonfire.repick", "button160"),
    ("burden.*", "subtitle"), ("controls.hint.*", "dialog_body300"), ("derived.*", "dialog_body300"),
    ("load.*", "dialog_body300"),
    ("difficulty.summary", "button_tip"), ("difficulty.*", "button250"),
    ("levelup.title", "dialog_title"), ("levelup.head", "dialog_body300"), ("levelup.head-idle", "dialog_body300"), ("levelup.cancel", "button200"),
    ("levelup.tip", "button_tip"), ("levelup.next", "button_tip"), ("levelup.burn", "button_tip"), ("levelup.short", "button_tip"), ("levelup.later", "button_tip"),
    ("levelup.load*", "button_tip"), ("levelup.*", "button150"),
    ("origin.later", "button200"), ("origin.choose", "button150"), ("origin.back", "button150"), ("origin.none", "subtitle"),
    ("origin.none-hint*", "subtitle"), ("origin.confirm-title", "dialog_title"),
    ("origin.head-*", "dialog_body320"), ("origin.*.name", "dialog_title"), ("origin.*.desc", "button_tip"),
    ("origin.*.kit", "dialog_body320"), ("origin.*", "dialog_body300"),
    ("pvp.*", "subtitle"),
    ("start.title", "dialog_title"), ("start.body", "dialog_body300"), ("start.pvp-hit", "dialog_body300"),
    ("start.pvp-sweep", "dialog_body300"), ("start.pvp", "button250"), ("start.choice*", "button250"), ("start.later", "button250"),
    ("start.later-tip", "button_tip"), ("start.already-set", "wrap"),
    ("start.changed", "wrap"), ("start.provisional-chat", "wrap"), ("start.*", "subtitle"),
    ("stat.*.name", "button150"), ("stat.*.short", "dialog_body300"), ("stat.*.tag", "dialog_body300"),
    ("stats.title", "dialog_title"), ("stats.close", "button200"), ("stats.*", "dialog_body300"),
    ("bonfire.status", "dialog_body"), ("bonfire.no-warp", "dialog_body"), ("spell.no-slot", "dialog_body"),
    ("hud.*", "actionbar"),
    ("item.*", "tooltip"), ("weapon.*", "tooltip"), ("test.*", "tooltip"), ("skill.*", "tooltip"),
    ("vanilla.deathScreen.respawn", "button200"), ("vanilla.deathScreen.titleScreen", "button200"),
    ("vanilla.deathScreen.quit.confirm", "screen"), ("vanilla.deathScreen.score.value", "screen"),
    ("vanilla.container.crafting", "container_title"), ("vanilla.container.*", "container_title_wide"),
    ("boss.*.name", "boss_name"), ("vanilla.menu.game", "screen"), ("vanilla.options.*", "screen"),
    ("vanilla.controls.*", "screen"),
    ("pack.*", "wrap"), ("build.*", "wrap"), ("admin.*", "wrap"),
]
# 폭을 잴 때 자리에 넣는 값 (가장 길게 나올 만한 것)
SAMPLE = {"souls": "9,999,999", "n": "9,999,999", "level": "713", "m": "999", "kind": "control", "ticks": "100",
          # 레벨 올리기·능력치 창 (5.9): 레벨은 세 자리, 소울은 아홉 자리까지 (지갑 상한 999,999,999)
          "from": "713", "to": "713", "held": "999,999,999", "cost": "9,999,999", "value": "15 → 99",
          "first": "Max Stamina", "second": "Ailment Resist", "firstv": "1,000 → 1,000", "secondv": "+12% → +12%", "hp": "1,000", "mana": "200", "stamina": "200",
          "attack": "999", "weight": "99.9", "cap": "99.9", "damage": "1.25", "health": "1.4", "parry": "-1", "estus": "5",
          "next": "9,999,999", "what": "Max Mana", "tier": "Overburdened", "difficulty": "Very Hard", "pvp": "PvP off"}

# ── Java 를 읽는 표 ──
# 열쇠를 받는 부르기: (임자, 이름) → 인수 목록 → 열쇠 자리들. 열쇠 자리 뒤 인수는 (자리 이름, 값) 짝이다 (Lang.args)
#   Lang.c / lines (열쇠, 짝...) 또는 (보는 사람, 열쇠, 짝...): 첫 인수가 문자열 (또는 문자열을 이은 것) 이면 열쇠,
#     아니면 인수 개수로 가른다 (짝수면 앞에 보는 사람이 있다)
#   Lang.render (언어, 열쇠, 짝...), Lang.tell (받는 이, 열쇠, 짝...), Lang.renderBoth (열쇠, 짝...)
#   Items.icon (재료, 이름 열쇠, 설명 열쇠 또는 null): 열쇠를 그대로 넘기는 도우미 (안의 Lang 부르기는 // lang-dyn: param)


def viewer_form(args):
    if not args or any(t[0] == "str" for t in top_level(args[0])):
        return [0]
    return [1] if len(args) % 2 == 0 else [0]


KEY_CALLS = {
    ("Lang", "c"): viewer_form,
    ("Lang", "lines"): viewer_form,
    ("Lang", "render"): lambda args: [1],
    ("Lang", "tell"): lambda args: [1],
    ("Lang", "renderBoth"): lambda args: [0],
    ("Lang", "variant"): lambda args: [0],
    ("Lang", "titled"): lambda args: [1, 3],
    ("Lang", "cell"): lambda args: [1],
    ("Lang", "rcell"): lambda args: [1],
    ("Items", "icon"): lambda args: [1, 2] if len(args) == 3 else [],
}
# 둘째 인수가 자리 짝이 아닌 부르기 (Lang.variant(열쇠, 갈래): 갈래는 팩이 짠 번역 열쇠의 끝 조각)
NO_PAIRS = {("Lang", "variant"), ("Lang", "cell"), ("Lang", "rcell"), ("Lang", "titled")}
# 열쇠의 자리를 팩이 갈래마다 채우는 부르기 (Lang.titled(보는 사람, 열쇠, 갈래, 대체 글 열쇠): 팩의 TITLE_VARIANTS 가 열쇠의 자리 <name> 을
# 갈래의 이름 글로 짠다): 자리 짝을 보지 않는다 (열쇠가 있는지만)
NO_SLOT_CHECK = {"Lang.titled"}
# 열쇠를 넘기기만 하는 도우미 (그 안의 Lang 부르기에 // lang-dyn: param 을 단다). 짝이 없으니 자리가 없어야 한다
HELPERS = {("Items", "icon")}
# 서버 기록 부르기 (그 괄호 안의 한글은 기록 줄이다). getLogger() 뒤, 또는 log·logger·LOG 이름 뒤
LOG_OWNERS = {"getLogger", "log", "logger", "LOG"}
LOG_METHODS = {"info", "warning", "warn", "severe", "error", "fine", "config", "log"}
# 플레이어에게 가는 글을 만들거나 받는 곳. 여기에 글자 (로마자·한글) 가 든 문자열을 바로 넣으면 번역되지 않는다.
# 기계 글 (시험 줄 [T], 점검 줄 [CHECK], /souls 의 쓰는 법·pack·perf) 은 그 줄에 // lang-machine
TEXT_MAKERS = {("Component", "text"), ("Text", "mm"), ("MM", "deserialize")}
RAW_SINKS = {"sendMessage", "sendRichMessage", "sendPlainMessage", "sendActionBar", "sendTitle", "kickPlayer",
             "setDisplayName", "setCustomName", "setPlayerListName", "disallow", "kick", "disconnect"}
LETTER = re.compile("[A-Za-z가-힣]")
DYN = re.compile(r"//\s*lang-dyn:\s*(.+?)\s*$")

# ── 콘텐츠 → 열쇠 (12.5 의 표와 같다) ──
# 콘텐츠 파일의 맨 위 id 마다 있어야 하는 lang 열쇠. line 은 한 줄, list 는 여러 줄 (목록). 콘텐츠 파일이 생기는 마일스톤에서
# 여기에 한 줄을 더한다 (표에 없는 콘텐츠 파일은 경고)
CONTENT_KEYS = {
    "skills.yml": (("skill.{id}.name", "line"), ("skill.{id}.desc", "list")),
    "items.yml": (("item.{id}.name", "line"), ("item.{id}.lore", "list")),
    "bosses.yml": (("boss.{id}.name", "line"),),
    "weapons.yml": (("weapon.{id}.name", "line"), ("weapon.{id}.lore", "list")),
    "origins.yml": (("origin.{id}.name", "line"), ("origin.{id}.desc", "line"), ("origin.{id}.style", "line"),
                    ("origin.{id}.kit", "line")),
}
# 콘텐츠에 있으면 안 되는 글 칸 (글은 lang 열쇠로). display 는 투사체 모습 (재료 id) 이라 id 꼴이면 된다
CONTENT_TEXT_FIELDS = {"name", "display_name", "title", "subtitle", "description", "desc", "lore", "text", "flavor",
                       "message"}
ID_LIKE = re.compile(r"^[a-z0-9_:./#-]+$")


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

ESCAPE = re.compile(r"\\(u+[0-9a-fA-F]{4}|[0-3][0-7]{0,2}|[4-7][0-7]?|.)", re.S)
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "s": " "}
WORD = re.compile(r"[A-Za-z_$0-9][A-Za-z0-9_$]*")


def unescape(s):
    """Java 문자열의 \\uXXXX, \\n, 8진 escape 를 푼다 ("\\uc18c\\uc6b8" 도 한글로 본다)."""
    def one(m):
        e = m.group(1)
        if e[0] == "u":
            return chr(int(e.lstrip("u"), 16))
        if e[0] in "01234567":
            return chr(int(e, 8))
        return ESCAPES.get(e, e)
    return ESCAPE.sub(one, s)


def java_tokens(src):
    """주석을 뺀 낱말들 [(종류, 값, 줄)]. 종류: id (이름·숫자), str (문자열, escape 를 푼 값. 글 블록도), chr, op (한 글자)."""
    toks = []
    i, line, n = 0, 1, len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            i = j
        elif src.startswith('"""', i):
            j = src.find('"""', i + 3)
            j = n if j < 0 else j
            toks.append(("str", unescape(src[i + 3:j]), line))
            line += src.count("\n", i, j + 3)
            i = j + 3
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            toks.append(("str" if c == '"' else "chr", unescape(src[i + 1:j]), line))
            i = j + 1
        else:
            m = WORD.match(src, i)
            if m:
                toks.append(("id", m.group(), line))
                i = m.end()
            else:
                toks.append(("op", c, line))
                i += 1
    return toks


def call_args(toks, at):
    """toks[at] 이 '(' 일 때 → (인수들 [[낱말...]], 닫는 ')' 의 자리). 괄호 깊이 0 의 쉼표로 나눈다."""
    args, cur, depth, i = [], [], 0, at + 1
    while i < len(toks):
        kind, val, _ = toks[i]
        if kind == "op" and val in "([{":
            depth += 1
        elif kind == "op" and val in ")]}":
            if depth == 0:
                if cur or args:
                    args.append(cur)
                return args, i
            depth -= 1
        elif kind == "op" and val == "," and depth == 0:
            args.append(cur)
            cur = []
            i += 1
            continue
        cur.append(toks[i])
        i += 1
    return args, len(toks) - 1


def calls(toks, names):
    """임자.이름( 부르기들 → [(임자, 이름, 인수들, 첫 줄, 끝 줄, 시작 자리, 끝 자리)]. names = {(임자, 이름)} 또는 이름만."""
    out = []
    for i in range(len(toks) - 3):
        a, dot, b, par = toks[i:i + 4]
        if a[0] != "id" or dot[1] != "." or b[0] != "id" or par[1] != "(":
            continue
        if (a[1], b[1]) not in names:
            continue
        args, end = call_args(toks, i + 3)
        out.append((a[1], b[1], args, a[2], toks[end][2], i, end))
    return out


def literal(arg):
    """인수가 문자열 하나뿐이면 그 값, 아니면 None."""
    return arg[0][1] if len(arg) == 1 and arg[0][0] == "str" else None


def log_spans(toks):
    """서버 기록 부르기의 괄호 안 (낱말 자리 범위들)."""
    spans = []
    for i in range(len(toks) - 3):
        a, dot, b, par = toks[i:i + 4]
        owner = a[1]
        if a[0] == "op" and a[1] == ")" and i >= 2 and toks[i - 1][1] == "(" and toks[i - 2][1] == "getLogger":
            owner = "getLogger"
        if owner not in LOG_OWNERS or dot[1] != "." or b[1] not in LOG_METHODS or par[1] != "(":
            continue
        _, end = call_args(toks, i + 3)
        spans.append((i + 3, end))
    return spans


def marker_lines(src, word):
    return {i for i, l in enumerate(src.split("\n"), 1) if word in l}


def dyn_markers(src):
    """줄 번호 → // lang-dyn: 뒤의 항목들."""
    out = {}
    for i, l in enumerate(src.split("\n"), 1):
        m = DYN.search(l)
        if m:
            out[i] = [x.strip() for x in m.group(1).split(",") if x.strip()]
    return out


def check_java(report, root=JAVA):
    """Java 를 읽어 한글 문자열·번역 안 되는 글을 거르고, 열쇠 부르기 [(파일, 줄, 임자.이름, 열쇠 인수, 짝 인수, 표시)] 를 낸다."""
    found = []
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            if not f.endswith(".java"):
                continue
            path = os.path.join(base, f)
            rel = os.path.relpath(path, ROOT)
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            toks = java_tokens(src)
            ok_lines = marker_lines(src, "lang-ok")
            machine = marker_lines(src, "lang-machine")
            dyn = dyn_markers(src)

            # 한글: 서버 기록 부르기의 괄호 안이거나 // lang-ok 줄만 된다
            logged = set()
            for a, b in log_spans(toks):
                logged.update(range(a, b + 1))
            for i, (kind, val, ln) in enumerate(toks):
                if kind == "str" and HANGUL.search(val) and i not in logged and ln not in ok_lines:
                    report.add("오류", "java", f"{rel}:{ln}", f"한글 문자열 (언어 열쇠로, 또는 서버 기록 줄로): {val[:60]!r}")

            # 번역되지 않는 글: Component.text("글자") 같은 것, sendMessage("글자") 같은 문자열 받는 곳
            for owner, name, args, ln, last, *_ in calls(toks, TEXT_MAKERS):
                lits = [t[1] for t in (args[0] if args else []) if t[0] == "str" and LETTER.search(t[1])]
                if lits and not machine & set(range(ln, last + 1)):
                    report.add("오류", "text", f"{rel}:{ln}", f"{owner}.{name}({lits[0][:40]!r}...) 는 번역되지 않는다 "
                               "(Lang.c 열쇠로. 기계 글이면 그 줄에 // lang-machine)")
            for i in range(len(toks) - 2):
                dot, b, par = toks[i:i + 3]
                if dot[1] != "." or b[0] != "id" or b[1] not in RAW_SINKS or par[1] != "(":
                    continue
                args, end = call_args(toks, i + 2)
                bare = [t[1] for a in args for t in top_level(a) if t[0] == "str" and LETTER.search(t[1])]
                if bare and not machine & set(range(b[2], toks[end][2] + 1)):
                    report.add("오류", "text", f"{rel}:{b[2]}", f"{b[1]}({bare[0][:40]!r}...) 에 글을 바로 넣었다 "
                               "(Lang.c 열쇠로. 기계 글이면 그 줄에 // lang-machine)")

            # 열쇠 부르기
            for owner, name, args, ln, last, *_ in calls(toks, set(KEY_CALLS)):
                marks = [m for x in range(ln, last + 1) for m in dyn.get(x, [])]
                for k in KEY_CALLS[(owner, name)](args):
                    if k >= len(args):
                        report.add("오류", "keys", f"{rel}:{ln}", f"{owner}.{name} 에 열쇠 인수가 없다")
                        continue
                    pairs = [] if (owner, name) in HELPERS | NO_PAIRS else args[k + 1:]
                    found.append((rel, ln, f"{owner}.{name}", args[k], pairs, marks))
    return found


def top_level(arg):
    """인수 안에서 괄호 깊이 0 의 낱말들 (sendMessage("글" + x) 의 "글". Component.text("글") 안은 따로 본다)."""
    out, depth = [], 0
    for t in arg:
        if t[0] == "op" and t[1] in "([{":
            depth += 1
        elif t[0] == "op" and t[1] in ")]}":
            depth -= 1
        elif depth == 0:
            out.append(t)
    return out


def key_slots(key, table):
    """열쇠의 자리 이름들 (목록 열쇠는 모든 줄의 자리). 없는 열쇠면 None."""
    flat = langpack.lines(table)
    if key in table and isinstance(table[key], list):
        names = set()
        for i in range(1, len(table[key]) + 1):
            names.update(langpack.slots(langpack.split_style(flat[f"{key}.{i}"])[1]))
        return names
    if key in flat:
        return set(langpack.slots(langpack.split_style(flat[key])[1]))
    return None


def content_patterns():
    """CONTENT_KEYS 의 열쇠 꼴을 glob 으로 ("skill.{id}.name" → "skill.*.name")."""
    return {pat.replace("{id}", "*") for rules in CONTENT_KEYS.values() for pat, _ in rules}


def check_keys(report, found, ko):
    """
    부르는 열쇠가 있는지, 넘기는 자리 이름이 그 열쇠의 자리와 같은지. 열쇠가 글자 그대로가 아니면 (만든 열쇠)
    그 줄에 // lang-dyn: <glob>, … 가 있어야 한다: glob 은 lang 열쇠에 맞거나 콘텐츠 표 (CONTENT_KEYS) 의 꼴이다.
    say 는 콘텐츠 say 부품의 key (check_content 가 본다), param 은 열쇠를 넘기는 도우미 (HELPERS, 부르는 곳을 본다).
    돌려주는 값: (글자 그대로 본 곳, lang-dyn 으로 본 곳).
    """
    keys = set(langpack.lines(ko)) | set(ko)
    patterns = content_patterns()
    checked = dynamic = 0
    for rel, ln, what, karg, pairs, marks in found:
        where = f"{rel}:{ln}"
        key = literal(karg)
        if what in {f"{o}.{n}" for o, n in HELPERS} and len(karg) == 1 and karg[0][1] == "null":
            continue      # Items.icon(재료, 이름, null): 설명 없음
        if key is not None:
            checked += 1
            want = key_slots(key, ko)
            if want is None:
                report.add("오류", "keys", where, f"{what}: lang 에 없는 열쇠 {key!r}")
                continue
            if what not in NO_SLOT_CHECK:
                check_pairs(report, where, what, key, want, pairs)
            continue
        dynamic += 1
        if not marks:
            hint = literal(pairs[0]) if pairs else None
            if what in ("Lang.c", "Lang.lines") and hint in keys:
                report.add("오류", "keys", where, f"{what}(보는 사람, {hint!r}, ...): 자리 인수는 (이름, 값) 짝이다 (남는 인수 하나)")
            else:
                report.add("오류", "keys", where, f"{what}: 열쇠가 글자 그대로가 아니다 ({src_text(karg)}). "
                           "그 줄에 // lang-dyn: <열쇠 glob> 을 단다 (12.5, 13.7)")
            continue
        for m in marks:
            if m in ("say", "param"):
                if m == "param" and not any(rel.endswith(os.sep + h[0] + ".java") for h in HELPERS):
                    report.add("오류", "keys", where, f"lang-dyn: param 은 열쇠를 넘기는 도우미 (HELPERS) 안에서만")
                continue
            hits = sorted(k for k in keys if fnmatch.fnmatchcase(k, m))
            if m not in patterns and not hits:
                report.add("오류", "keys", where, f"lang-dyn: {m!r} 에 맞는 lang 열쇠가 없다 (콘텐츠 표에도 없다)")
            for k in hits:
                if what in NO_SLOT_CHECK:
                    break
                if k in ko or not isinstance(ko.get(k.rsplit(".", 1)[0]), list):
                    want = key_slots(k, ko)
                    if want is not None:
                        check_pairs(report, where, what, k, want, pairs)
    return checked, dynamic


def check_pairs(report, where, what, key, want, pairs):
    if len(pairs) % 2:
        report.add("오류", "keys", where, f"{what} {key!r}: 자리 인수는 (이름, 값) 짝이다 (남는 인수 하나)")
        return
    names = []
    for j in range(0, len(pairs), 2):
        n = literal(pairs[j])
        if n is None:
            report.add("오류", "keys", where, f"{what} {key!r}: 자리 이름은 글자 그대로 쓴다 ({src_text(pairs[j])})")
            return
        names.append(n)
    got = set(names)
    if got != want:
        miss, extra = sorted(want - got), sorted(got - want)
        report.add("오류", "keys", where, f"{what} {key!r}: 자리가 lang 과 다르다"
                   + (f" (빠짐 {miss})" if miss else "") + (f" (lang 에 없음 {extra})" if extra else ""))


def src_text(arg):
    return " ".join(t[1] if t[0] != "str" else repr(t[1]) for t in arg)[:60]


def check_content(report, ko, root=CONTENT):
    """
    콘텐츠 YAML: 한글 글이 없고, 글 칸 (name, description, lore, text …) 이 없고 (글자와 상관없이), id 마다
    CONTENT_KEYS 의 열쇠가 lang 에 있고, say 부품의 key 가 lang 에 있다 (자리 없이).
    """
    import yaml
    keys = set(langpack.lines(ko)) | set(ko)

    def walk(node, where):
        if isinstance(node, dict):
            if node.get("type") in ("say", "message"):
                k = node.get("key")
                if not k or k not in keys:
                    report.add("오류", "keys", where, f"say 부품의 key {k!r} 가 lang 에 없다")
                elif key_slots(k, ko):
                    report.add("오류", "keys", where, f"say 부품의 key {k!r} 에 자리가 있다 (say 는 자리 값을 넘기지 않는다)")
            for k, v in node.items():
                if k in CONTENT_TEXT_FIELDS or (k == "display" and isinstance(v, str) and not ID_LIKE.match(v)):
                    report.add("오류", "content", f"{where}.{k}", f"콘텐츠에 글 칸 '{k}' (글은 lang 열쇠로, 12.5): {str(v)[:40]!r}")
                walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")
        elif isinstance(node, str) and HANGUL.search(node):
            report.add("오류", "content", where, f"콘텐츠에 한글 글 (lang 열쇠로 옮긴다): {node[:40]!r}")

    if not os.path.isdir(root):
        return
    for f in sorted(os.listdir(root)):
        if not f.endswith((".yml", ".yaml")):
            continue
        rel = os.path.relpath(os.path.join(root, f), ROOT)
        with open(os.path.join(root, f), encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        walk(data, rel)
        rules = CONTENT_KEYS.get(f)
        if rules is None:
            report.add("경고", "content", rel, "CONTENT_KEYS 에 없는 콘텐츠 파일 (id 마다 있어야 할 lang 열쇠를 표에 더한다, 12.5)")
            continue
        ids = [str(k) for k in data] if isinstance(data, dict) else []
        for pat, kind in rules:
            for i in ids:
                k = pat.format(id=i)
                if k not in ko:
                    report.add("오류", "keys", f"{rel}:{i}", f"lang 에 {k} 가 없다 (콘텐츠 id 의 열쇠, 12.5)")
                elif kind == "list" and not isinstance(ko[k], list):
                    report.add("오류", "keys", f"{rel}:{i}", f"{k} 는 목록 (여러 줄) 이어야 한다")
                elif kind == "line" and isinstance(ko[k], list):
                    report.add("오류", "keys", f"{rel}:{i}", f"{k} 는 한 줄이어야 한다 (목록이 아니다)")
            # 콘텐츠에 없는 id 의 열쇠 (지운 스킬의 글이 남았다)
            head, tail = pat.split("{id}")
            for k in sorted(ko):
                if k.startswith(head) and k.endswith(tail) and len(k) > len(head) + len(tail):
                    i = k[len(head):len(k) - len(tail)]
                    if "." not in i and i not in ids:
                        report.add("경고", "content", k, f"{rel} 에 id {i!r} 가 없는데 lang 에 열쇠가 남았다")


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
    try:
        want = langpack.build(tables, gen_pack.LANGS, typeset=typeset.Typeset(typeset.PackFonts.open(pack)))
    except KeyError as ex:
        report.add("오류", "pack", "font", f"팩 글꼴로 창 제목·수치 이름을 짤 수 없다 (낡은 팩, gen_pack 을 다시): {ex}")
        return
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


def measurer(pack):
    """(열쇠, 꼴 태그, 글) → 폭 (GUI 픽셀). 팩 글꼴로 재고, 못 재면 바닐라 기본 글꼴 폭."""
    pf = typeset.PackFonts.open(pack) if pack is not None else None
    ko_map = {}

    def measure(key, tags, line, ko, lang="ko"):
        if pf is not None:
            try:
                if typeset.matches(key, typeset.title_keys(lang)):
                    if "map" not in ko_map:
                        ko_map["map"] = typeset.title_map(typeset.title_syllables(ko))
                    return pf.width(typeset.DEFAULT_FONT, typeset.to_title(line, ko_map["map"]))
                return pf.width(typeset.font_of(tags), line)
            except KeyError:
                pass
        return width(line)
    return measure


def check_width(report, tables, pack=None):
    ko = langpack.lines(tables["ko"])
    measure = measurer(pack)
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
            tags, text = langpack.split_style(raw)
            for name in langpack.slots(langpack.split_style(ko.get(key, raw))[1]):
                text = text.replace(f"<{name}>", SAMPLE.get(name, "0"))
            for line in text.split("\n"):
                w = measure(key, tags, line, ko, lang)
                if w > px:
                    report.add("오류", "width", f"{lang}.yml {key}", f"{w}px > {slot} {px}px: {line!r}")


def lint(pack=PACK_DIR, quiet=False):
    report = Report()
    tables = langpack.load_all()
    for key, why in langpack.problems(tables):
        report.add("오류", "pair", key, why)
    found = check_java(report)
    checked, dynamic = check_keys(report, found, tables["ko"])
    check_content(report, tables["ko"])
    check_pack(report, tables, pack)
    check_width(report, tables, pack)
    report.calls = (checked, dynamic)
    if not quiet:
        report.print()
        keys = langpack.lines(tables["ko"])
        van = sum(1 for k in keys if k.startswith(langpack.VANILLA))
        print(f"langcheck: 열쇠 {len(keys) - van}개 + 바닐라 {van}개 (ko, en), Java 열쇠 부르기 {checked + dynamic}곳 "
              f"(글자 그대로 {checked}곳: 열쇠·자리 확인, 만든 열쇠 {dynamic}곳: lang-dyn 표시로 확인), "
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
