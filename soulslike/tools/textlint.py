#!/usr/bin/env python3
"""
글 검사기 (DESIGN.md 13.7, ART_DIRECTION.md 의 글 규칙과 "영어판"). 게임 안 문구가 짧고 건조한지 기계로 먼저 거른다.

  python3 tools/textlint.py [yml·json 파일 또는 폴더 ...]

  기본으로 보는 곳
    plugin/src/main/resources/lang/ko.yml, en.yml   게임 문구 (10.3). 한국어가 원본, 영어는 따로 쓴 것
    plugin/src/main/resources/content/*.yml         콘텐츠 (보이는 글은 lang 으로 옮겼다. 남은 한글이 있으면 본다)
  팩 언어 파일 (pack/resourcepack/assets/*/lang/*.json) 은 이 YAML 에서 만들어지므로 기본으로는 보지 않는다
  (YAML 과 같은지는 tools/langcheck.py 가 본다). 인수로 주면 본다.

  말씨의 규칙은 DESIGN.md 10.3 의 "UI 글 규칙" 이다. 이야기 글 (is_story: 무기·반지·아이템·스킬 설명과 출신 설명, STORY_KEYS 의 세계 안
  사건 글) 은 해라체 단문, 그 밖 (단추·칸 이름·알림·설정 창·접속·관리자 글) 은 UI 글이다.

한국어 (한글이 든 문자열)
  오류  exclaim 느낌표, emoji 이모지, hype 금지어 (전설, 궁극, 압도, 최강, 강력한),
        explain 설명문체 어미 (습니다, 할 수 있, 입니다): 이야기 글에만.
        단추·알림·설정 창·시스템 글은 존댓말 (~합니다, ~하세요) 을 쓴다 (DECISIONS 2026-10-10 "설정 창·시스템 글은 내레이션 없이 존댓말")
  경고  lines 설명(lore, desc, description …)이 4줄 넘음, long 한 줄이 32자 넘음 (채팅·접속 거절처럼 저절로 줄을 바꾸는 자리
        "wrap" 은 보지 않는다: 폭은 tools/langcheck.py 가 픽셀로 잰다), cliche 이름이 "어둠의", "그림자", "빛의" 로 시작,
        dupname 같은 이름이 두 번 넘게 나옴
  UI    (UI 글만. 단계는 UI_LEVEL = 오류: 2026-10-10 에 글을 다 고치고 올렸다)
        button-verb 단추 글 (tools/langcheck.py 의 SLOTS 가 단추 폭 button* 으로 정한 열쇠) 이 "-다" 로 끝남 (되돌린다 → 되돌리기)
        emdash      한국어 글의 줄표 "—" (쉼표·쌍점·괄호를 쓴다)
        archaic     사극투·내레이션 어미 ("다시 오라", "들어와 보라", "그만두겠나", "누구였나": ~오라·~보라·~하라·~겠나·~였나·~는가)
        polite      시스템 글 (SYSTEM_KEYS: 접속·팩·관리자 답·세계 설정 창과 그 알림·타이틀로 나가기 확인) 의 문장이 해라체 "-다" 로 끝남
                    ("세계를 짓는 중이다" → "세계를 만드는 중입니다")
        term        정한 용어를 쓰지 않음 (TERMS_KO: 술법 세기 → 술법 위력, 가진 소울 → 보유 소울, 패링 창 → 패링 판정 …)
        test-marker 시험용 물건 (TEST_LORE) 의 설명 첫 줄이 "[시험용]" / "[Test]" 가 아님 (개발 메모를 설명 칸에 쓰지 않는다)
영어 (en.yml, en_us.json 의 글)
  오류  exclaim 느낌표, emoji 이모지, hype 과장어 (legendary, ultimate, epic, mighty, powerful …),
        slang 현대 구어 (okay, cool, gonna, awesome …), explain 설명문체 (you can, allows you, lets you, please …):
        explain 은 한국어처럼 이야기 글에만
  경고  long 한 줄이 48자 넘음 ("wrap" 자리는 보지 않는다), lines
  UI    emdash 이야기 글이 아닌 영어 글의 줄표 "—", term 옛말·정하지 않은 말 (TERMS_EN: foe → enemy, terms → world settings,
        none may, depart, the living, Rite Power → Spell Power …), test-marker (UI_LEVEL)
두 언어 (UI_LEVEL)
  middot  값·이름을 " · " (띄운 가운뎃점) 으로 잇는 줄 ("레벨 8 · 소울 30,000", "구르기 · Shift"). 이야기 글은 보지 않는다.
          꼭 써야 하는 열쇠는 ALLOW["middot"] 에 glob 으로 적는다. 붙여 쓴 "직검·방패" 는 된다 (그래도 값 목록은 쉼표로 쓴다)
  ALLOW = {규칙: (열쇠 glob, …)}: UI 규칙을 일부러 어기는 열쇠를 적는 곳 (까닭을 주석으로)
이름 (lang/names.yml)
  오류  name: ko.yml 의 열쇠에 고유 이름이 있으면 en.yml 의 같은 열쇠에 정한 영어 표기가 있어야 한다 (대소문자 없이 글 안에
        들어 있으면 된다. 목록이면 하나). 이름 앞이 한글이면 이름이 아니다 (돌아오다). 낱말과 소리가 같은 이름 (오다) 은
        names.yml 의 after 에 적은 토씨가 뒤에 붙을 때만 (오다의, 오다가)

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
# 이야기·설명 글 (해라체 단문, explain 금지가 걸리는 곳): 마지막 열쇠가 DESC_KEYS 인 것 (무기·반지·아이템 설명, 출신·스킬 설명) 과
# 세계 안의 사건 글 (큰 글씨·문 알림·결말). 단추·알림·설정 창·시스템 글은 여기에 넣지 않는다 (존댓말을 쓴다)
STORY_KEYS = ("ending.*", "bell.*", "taster.*", "door.*", "bonfire.lit", "boss.felled", "souls.recovered", "death.*")
# 마지막 열쇠가 desc 여도 UI 글인 것: 난이도 한 줄은 세계 설정 창의 단추 설명 칸 (존댓말)
UI_DESC = ("difficulty.*",)
# 시스템 글 (존댓말 ~합니다·~하세요, 해라체 "-다" 로 끝나는 문장이 없어야 한다, rule polite): 접속 전 글, 관리자 답, 세계 설정 창과 그 알림,
# 사망 화면의 타이틀로 나가기 확인, 출신을 고르지 않았다는 알림, 레벨 업 창의 "소울이 부족합니다", 출신 다시 고르기 설명
SYSTEM_KEYS = ("pack.prompt", "pack.declined", "pack.failed", "build.*", "admin.*", "start.body", "start.pvp-*", "start.changed",
               "start.provisional*", "start.waiting", "start.op-only", "start.already-set", "difficulty.*.desc", "origin.none",
               "levelup.short", "bonfire.repick-tip", "vanilla.deathScreen.quit.confirm")
# 사극투·내레이션 어미 (UI 글, rule archaic). 문장 끝 (마침표·물음표·줄 끝 앞) 에서만 본다
ARCHAIC_KO = re.compile(r"(오라|보라|하라|겠나|였나|었나|는가|느냐)[.?]?(?=\s|$)")
# 정한 용어 (UI 글, rule term): 틀린 말 → 쓸 말. 2026-10-10 "소울 유저가 쓰는 말" (DECISIONS) 과 10.3 의 용어표
TERMS_KO = {
    "술법 세기": "술법 위력", "가진 소울": "보유 소울", "필요한 소울": "필요 소울", "다음 한 점": "필요 소울",
    "패링 창": "패링 판정", "너무 무거움": "과적", "장비 무게": "장비 중량", "작은 방패": "소형 방패", "대방패": "대형 방패",
    "때리기": "타격", "베기": "참격", "마법 저항": "마법 방어력", "상태 이상 저항": "상태 이상 내성", "세계를 정한다": "세계 설정",
    "월드": "세계 (바닐라 한국어와 같게)", "아직 듣지": "(미적용) / 아직 적용되지 않음", "기억할 자리": "기억 슬롯",
    "누구였": "출신", "그림 글자": "글리프",
}
# 영어 (낱말 경계로, 대소문자 없이): 옛말·은유·줄임 → 쓸 말
TERMS_EN = {
    "foe": "enemy", "foes": "enemies", "the terms": "world settings", "terms": "world settings", "none may": "a plain sentence",
    "the living": "players", "depart": "Quit / Leave", "pass between fires": "Travel", "overburdened": "Overloaded",
    "rite power": "Spell Power", "rite learned": "Spell learned", "stam.": "Stamina", "res.": "Resist / Defense",
    "another past": "Change Origin", "take this path": "Begin",
}
# 시험용 물건의 설명 (rule test-marker): 첫 줄이 이 표시 하나 (DECISIONS 2026-10-10 "시험용 표시는 [시험용] 으로 쓴다")
TEST_LORE = ("ring.test_*.lore", "skill.test_*.desc", "test.guard-lore")
TEST_MARK = {"ko": "[시험용]", "en": "[Test]"}
# UI 규칙의 단계: 2026-10-10 글을 다 고치고 "오류" 로 올렸다 (새 글이 같은 버릇을 다시 들이지 않게)
UI_LEVEL = "오류"
# UI 규칙을 일부러 어기는 열쇠 (glob). 예: "middot": ("weapon.class.*",)  # 분류 줄 "직검 · 베기/찌르기" 를 그대로 둘 때
ALLOW = {
    "middot": (),
    "button-verb": (),
    # 무기·반지 설명 칸 실선의 대체 글 (팩이 없을 때만 보인다. 팩은 실선 그림 글자로 바꾼다, pack/typeset.py)
    "emdash": ("weapon.rule", "ring.rule"),
    # 무기 이름은 이야기에 묶여 있어 이야기가 정해질 때 함께 고친다 ("볼크 가의 대방패", DECISIONS 2026-10-08·10-10)
    "term": ("weapon.*.name",),
}
# 단추 폭 자리 (tools/langcheck.py SLOTS 의 자리 이름): 이 자리의 열쇠가 단추 글이다
BUTTON_SLOTS = ("button160", "button200", "button150", "button250", "button64")
MIDDOT_CHAIN = re.compile(r"\S \u00b7 \S|\S \u00b7$|^\u00b7 \S")

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

    def counts(self):
        """규칙마다 (오류, 경고) 수."""
        out = {}
        for level, _, _, rule, _ in self.items:
            e, w = out.get(rule, (0, 0))
            out[rule] = (e + (level == "오류"), w + (level == "경고"))
        return out

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


def lang_key(key):
    """walk 의 키 ('weapon.x.lore[2]') → 언어 열쇠 ('weapon.x.lore.3', 목록 줄은 1부터)."""
    m = re.match(r"^(.*)\[(\d+)\]$", key)
    return f"{m.group(1)}.{int(m.group(2)) + 1}" if m else key


def is_story(key):
    """이야기·설명 글인가 (explain 금지와 UI 규칙을 가르는 곳)."""
    import fnmatch
    k = re.sub(r"\[\d+\]$", "", key)
    if any(fnmatch.fnmatchcase(k, g) for g in UI_DESC):
        return False
    return last_key(key) in DESC_KEYS or any(fnmatch.fnmatchcase(k, g) for g in STORY_KEYS)


def allowed(rule, key):
    import fnmatch
    k = re.sub(r"\[\d+\]$", "", key)
    return any(fnmatch.fnmatchcase(k, g) for g in ALLOW.get(rule, ()))


_SLOT_OF = None


def slot(key):
    """tools/langcheck.py 의 SLOTS 가 정한 자리 이름 (없으면 None)."""
    global _SLOT_OF
    if _SLOT_OF is None:
        try:
            sys.path.insert(0, HERE)
            import langcheck
            _SLOT_OF = langcheck.slot_of
        except Exception:
            _SLOT_OF = lambda k: None
    return _SLOT_OF(lang_key(key))


def is_button(key):
    """단추 글인가: tools/langcheck.py 의 SLOTS 가 단추 폭 (BUTTON_SLOTS) 으로 정한 열쇠."""
    return slot(key) in BUTTON_SLOTS


def wraps(key):
    """저절로 줄을 바꾸는 자리 (채팅, 접속 거절, 팩 창: langcheck 의 "wrap") 인가. long (글자 수) 은 보지 않는다."""
    return slot(key) == "wrap"


def matches_any(key, globs):
    import fnmatch
    k = re.sub(r"\[\d+\]$", "", key)
    return any(fnmatch.fnmatchcase(k, g) for g in globs)


PLACEHOLDER = re.compile(r"<[a-z][a-z0-9_-]*>")


def ui_text(text):
    """UI 규칙에서 보는 글: 맨 앞 꼴 태그를 떼고 자리 (<souls>) 는 "0" 으로 둔다 ("소울 <souls> · 레벨" 의 가운뎃점 앞뒤가 비지 않게)."""
    try:
        sys.path.insert(0, os.path.join(ROOT, "pack"))
        import langpack
        _, body = langpack.split_style(text)
    except Exception:
        body = text
    return FORMAT.sub("0", LEGACY.sub("", TAG.sub("", PLACEHOLDER.sub("0", body))))


def check_test_marker(report, path, key, text, korean):
    """시험용 물건의 설명 첫 줄은 "[시험용]" / "[Test]" 하나 (개발 메모를 설명 칸에 쓰지 않는다)."""
    if not matches_any(key, TEST_LORE) or not re.search(r"\[0\]$", key):
        return
    want = TEST_MARK["ko" if korean else "en"]
    vis = ui_text(text).strip()
    if vis != want and not allowed("test-marker", key):
        report.add(UI_LEVEL, path, key, "test-marker", f"시험용 물건의 설명 첫 줄은 {want!r} 하나: {vis!r}")


def check_ui(report, path, key, text, korean):
    """UI 규칙 (이야기 글이 아닌 것): 가운뎃점 잇기, 줄표, 단추의 "-다", 사극투, 시스템 글의 존댓말, 용어, 시험용 표시."""
    check_test_marker(report, path, key, text, korean)
    if is_story(key):
        return
    vis = ui_text(text)
    if MIDDOT_CHAIN.search(vis) and not allowed("middot", key):
        report.add(UI_LEVEL, path, key, "middot", f"\" · \" 로 잇는 줄 (칸 맞춤·쉼표·괄호를 쓴다): {vis!r}")
    if "\u2014" in vis and not allowed("emdash", key):
        report.add(UI_LEVEL, path, key, "emdash", f"줄표 \"—\" (쉼표·쌍점·괄호를 쓴다): {vis!r}")
    if korean and HANGUL.search(vis):
        if is_button(key) and not allowed("button-verb", key):
            tail = re.sub(r"[\s.)\]0]+$", "", vis)
            if tail.endswith("다"):
                report.add(UI_LEVEL, path, key, "button-verb", f"단추 글이 \"-다\" 로 끝남 (명사형: 되돌리기·결정·닫기): {vis!r}")
        if ARCHAIC_KO.search(vis) and not allowed("archaic", key):
            report.add(UI_LEVEL, path, key, "archaic", f"사극투·내레이션 어미 (존댓말이나 명사형으로): {vis!r}")
        if matches_any(key, SYSTEM_KEYS) and not allowed("polite", key):
            for sent in re.split(r"[.?\n]", vis):
                sent = re.sub(r"[\s)\]0]+$", "", sent.strip())
                if sent.endswith("다") and not sent.endswith("니다"):
                    report.add(UI_LEVEL, path, key, "polite", f"시스템 글은 존댓말 (~합니다·~하세요): {sent!r}")
                    break
        for wrong, right in TERMS_KO.items():
            if wrong in vis and not allowed("term", key):
                report.add(UI_LEVEL, path, key, "term", f"'{wrong}' 대신 '{right}': {vis!r}")
    if not korean:
        low = vis.lower()
        for wrong, right in TERMS_EN.items():
            if re.search(r"(?<![a-z])" + re.escape(wrong) + (r"(?![a-z])" if wrong[-1].isalpha() else ""), low) and not allowed("term", key):
                report.add(UI_LEVEL, path, key, "term", f"'{wrong}' -> '{right}': {vis!r}")


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
    if is_story(key):
        for w in EXPLAIN_EN:
            if re.search(r"\b" + re.escape(w.replace("'", "")) + r"\b", low.replace("'", "")):
                report.add("오류", path, key, "explain", f"설명문체 '{w}': {vis!r}")
    check_ui(report, path, key, text, korean=False)
    for line in vis.split("\n"):
        if len(line) > MAX_LINE_EN and not wraps(key):
            report.add("경고", path, key, "long", f"{len(line)}자 (>{MAX_LINE_EN}): {line!r}")


def check_text(report, path, key, text):
    if is_english(path):
        check_english(report, path, key, text)
        return
    vis = plain(text)
    check_ui(report, path, key, text, korean=True)   # 자리뿐인 글 ("<name> — <desc>") 도 본다
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
    if is_story(key):
        for w in EXPLAIN:
            if w in vis:
                report.add("오류", path, key, "explain", f"설명문체 '{w}': {vis!r}")
    for line in vis.split("\n"):
        if len(line) > MAX_LINE and not wraps(key):
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
    """lang/names.yml → [(한국어 이름, [영어 표기...], 뒤에 와야 할 토씨 또는 None)]. 긴 이름부터."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    table = data.get("names") or {}
    after = data.get("after") or {}
    out = []
    for k, v in table.items():
        forms = [str(x) for x in v] if isinstance(v, list) else [str(v)]
        tail = after.get(k)
        out.append((str(k), forms, [str(x) for x in tail] if tail else None))
    return sorted(out, key=lambda row: -len(row[0]))


def name_pattern(kname, tail):
    """이름 앞이 한글이면 (돌아오다의 '오다') 이름이 아니다. tail 이 있으면 그 토씨가 뒤에 붙을 때만 (오다의, 오다가)."""
    pat = r"(?<![\uac00-\ud7a3])" + re.escape(kname)
    if tail:
        pat += "(?=" + "|".join(re.escape(t) for t in sorted(tail, key=len, reverse=True)) + ")"
    return re.compile(pat)


def check_names(report, ko_path, en_path, names):
    """ko.yml 열쇠의 고유 이름 → en.yml 같은 열쇠에 정한 영어 표기 (목록이면 그 가운데 하나)."""
    try:
        ko = flat_strings(load(ko_path))
        en = flat_strings(load(en_path))
    except Exception as ex:
        report.add("오류", ko_path, "-", "parse", f"읽지 못했다: {ex}")
        return
    for key, text in ko.items():
        vis = plain(text)
        target = plain(en.get(key, "")).lower()
        for kname, forms, tail in names:
            pat = name_pattern(kname, tail)
            if not pat.search(vis):
                continue
            vis = pat.sub(" ", vis)     # 긴 이름이 먹은 자리 (볼크 탑옥 → 탑옥은 다시 세지 않는다)
            if not any(f.lower() in target for f in forms):
                report.add("오류", en_path, key, "name", f"'{kname}' 은 영어로 '{' / '.join(forms)}' (names.yml): "
                           f"{plain(en.get(key, ''))!r}")


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
        rules = ", ".join(f"{r} {e + w}" for r, (e, w) in sorted(report.counts().items()))
        print(f"textlint: 파일 {len(files)}개, 오류 {len(report.errors)}, 경고 {len(report.warnings)}" + (f" ({rules})" if rules else ""))
    return report


def main(argv):
    report = lint(argv or None)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
