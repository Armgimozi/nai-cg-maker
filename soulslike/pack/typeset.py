"""
글자 짜기 (DESIGN.md 10.9 "글꼴"): 팩의 글꼴 (fonts.py 가 그린 bitmap 글꼴) 로 글 폭을 클라이언트와 똑같이 재고, 언어 파일에서
글꼴을 고를 수 없는 몇 곳을 언어 파일의 글로 짠다. FreeType 없이 팩 (폴더, zip, zip 바이트) 만 읽는다:
gen_pack.py 가 막 만든 팩 폴더로, tools/langcheck.py 가 검사하는 팩으로 같은 셈을 한다 (낡은 팩이면 결과가 달라 langcheck 가
잡는다).

짜는 곳 (모두 lang/ko.yml·en.yml 에서 온 글을 바꿀 뿐 글은 YAML 에만 있다)
  창 제목     바닐라 열쇠 TITLE_KEYS (vanilla.menu.game, vanilla.container.*, 영어는 설정 화면 제목 vanilla.options.*,
              vanilla.controls.* 도: title_keys) 의 글자를 기본 글꼴의 제목 글자 (개인 영역) 로
              바꾼다: 로마자는 로마 비문 대문자 (Cinzel), 한글은 무거운 명조 (Nanum Myeongjo ExtraBold). 언어 문자열은 글꼴을
              고를 수 없어서다. 로마자는 ASCII 순서 (U+F120 + 글자 - 0x20), 한글은 TITLE_KEYS 의 한국어 글에 나오는 음절의 차례
              (U+F200 부터). § 꼴 기호는 그대로 둔다.
  제목 밑 금실 DIVIDED 의 열쇠 (게임 메뉴 제목, 화톳불 이름) 뒤에 금실 그림 글자를 붙인다: 제목 폭 W 를 재서 펜을 제목 가운데 -
              금실 폭/2 로 되돌려 금실을 그리고 다시 W 로 (글 전체의 진행 폭은 W 그대로라 바닐라가 제목을 가운데에 놓는다).
              설정 화면 제목에는 붙이지 않는다 (고딕 촛불 초안 그대로, 2026-10-08 사용자 결정).
  갈래 제목   TITLE_VARIANTS: 자리 (<name>) 가 든 창 제목 (출신 확인 창 origin.confirm-title) 은 팩이 잴 수 없으므로, 갈래마다
              (출신 id) 그 이름 글 (origin.<id>.name) 로 souls.<열쇠>.<id> 를 짜고 금실을 붙인다 (플러그인 Lang.titled).
  수치 이름   weapon.stat.* (무기 설명 칸의 수치 이름): 이름 뒤를 빈칸 글자로 채워 그 언어의 이름 열 폭 (가장 긴 이름 +
              LABEL_GAP) 까지. 플러그인 (item/StatTable) 이 그 뒤에 값을 값 열 (VALUE_COL) 끝에 오른쪽 맞춤으로 붙인다.
  실선        weapon.rule.<무기 id> (무기 설명 칸의 수치와 설명 사이 실선, 팩의 언어 파일에만 있는 열쇠. 플러그인은
              Lang.variant("weapon.rule", id) 로 부르고 팩이 없으면 YAML weapon.rule 의 대체 글): 기본 글꼴의 실선 그림 글자
              (fonts.py rule_sheet: 고딕 촛불 초안의 설명 실선, 글 열 왼쪽 끝 작은 금빛 마름모와 폭 1·2·4…32 의 1 텍셀 청동 줄
              조각) 을 그 무기의 설명 칸 글 열 폭 (이름·분류 줄·수치 표·설명 줄 가운데 가장 넓은 것, weapon_width) 끝까지 잇는다.
              그래서 칸은 무기마다 제 글에 맞는 폭이고 (고딕 촛불 초안처럼) 둘째 실선은 글 열 끝까지 끊김 없는 한 알파의 줄이다
              (2026-10-08 비평: 둘째 실선이 짧고 끝이 옅어졌다). weapon.rule 자체는 가장 넓은 무기의 폭.
  가운뎃점    ko_kr 의 souls 언어 파일에서 "·" 를 한글 가운데 높이의 가운뎃점 (KO_MIDDOT) 으로 바꾼다 (가라몽의 "·" 는 로마자
              x 높이 가운데라 한글 사이에서는 바탕선에 붙은 마침표처럼 보였다). 영어는 그대로.

빈칸 글자: 기본 글꼴의 개인 영역 U+E380.. 에 ±1, 2, 4 … 128 (SPACE_STEPS). 폭은 이것들의 합으로 만든다 (souls:hud 의 빈칸과
같은 방식). 그래서 짜는 데 새 글자를 만들 일이 없고 팩과 플러그인이 같은 표를 쓴다 (glyphs.yml 의 text_space_*).

글 폭: 클라이언트처럼 글꼴의 공급자를 차례로 보고 처음 그 글자를 가진 공급자의 진행 폭을 더한다. bitmap 은 칸에서 알파가 0 이
아닌 가장 오른쪽 열 + 1 = w 를 재 (int)(0.5 + w × 배율) + 1, space 는 적힌 폭, reference 는 그 글꼴. 팩에 없는 글자 (바닐라가
그릴 글자) 는 잴 수 없어 KeyError.
"""
import fnmatch
import io
import json
import math
import os
import re
import zipfile

K = 4                           # 글자 텍셀 / GUI 픽셀 (fonts.py)
DEFAULT_FONT = "minecraft:default"
TITLE_FONT = "souls:title"
TITLE_LA_PUA = 0xF120           # 제목 로마자 (기본 글꼴): ASCII 0x20..0x7E 차례
TITLE_KR_PUA = 0xF200           # 제목 한글 (기본 글꼴): TITLE_KEYS 의 한국어 글에 나오는 음절 차례
DIVIDER = ""              # 제목 밑 금실 (기본 글꼴, souls:title)
RULE_GEM = "\ue3a0"             # 무기 설명 칸 실선의 왼쪽 끝 작은 마름모 (기본 글꼴 그림 글자, 3.5 GUI 폭: 진행 폭 RULE_GEM_ADV)
RULE_GEM_ADV = 5
RULE_GEM_LEFT = 0               # 마름모 칸 왼쪽 = 펜 (고딕 촛불 초안처럼 마름모가 글 열 왼쪽 끝에 붙는다)
RULE_LINE_START = 4             # 줄은 펜 + 4 GUI 에서 (초안의 설명 실선은 텍셀 8 에서 시작했다) 글 열 끝까지
RULE_RUN_BASE = 0xE3A1          # 실선 조각: E3A1+i = 폭 2^i (1 … 32), 그림 글자라 진행 폭이 조각 폭 + 1 (뒤에 빈칸 -1)
RULE_STEPS = (1, 2, 4, 8, 16, 32)
KO_MIDDOT = "\ue3a8"            # 한글 가운데 높이의 가운뎃점 (기본 글꼴, ko_kr 만)
RULE_KEY = "weapon.rule"
DIVIDER_W = 120                 # 금실의 보이는 폭 (GUI 픽셀): 가운데 맞춤에 쓴다
SPACE_BASE = 0xE380             # 빈칸 글자: E380+i = -(2^i), E388+i = +(2^i)
SPACE_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)

# 창 제목 (바닐라 열쇠, lang 의 vanilla.*): 제목 글꼴 글자로. 게임 메뉴와 창 이름은 두 언어 모두 (고딕 촛불 초안). 설정 화면
# 제목 (vanilla.options.*, vanilla.controls.*) 은 영어만 (로마 비문 대문자, TITLE_KEYS_EN): 한국어 설정 제목은 초안처럼 본문 글꼴
# (2026-10-08 비평: 무거운 명조로 바꾼 "설정" 이 초안보다 굵었다)
TITLE_KEYS = ("vanilla.menu.game", "vanilla.container.*")
TITLE_KEYS_EN = ("vanilla.options.*", "vanilla.controls.*")
# 제목 밑 금실: 열쇠 → 그 글을 그리는 글꼴. 게임 메뉴와 화톳불 이름만 (고딕 촛불 초안 그대로: 설정 화면 제목에 붙인 금실은
# 2026-10-08 사용자 결정 "초안 모양이 더 낫다" 로 뺐다. 720p 에서 첫 밀대 줄에 붙었다)
DIVIDED = (("vanilla.menu.game", DEFAULT_FONT), ("bonfire.test-name", TITLE_FONT), ("bonfire.*.name", TITLE_FONT),
           ("start.title", TITLE_FONT), ("origin.title", TITLE_FONT), ("levelup.title", TITLE_FONT), ("stats.title", TITLE_FONT))
# 갈래 제목 (자리가 든 창 제목, 검토 confirm-title-unstyled): (열쇠, 갈래 글의 꼴 origin.*.name 의 * 가 갈래 이름). 제목 글꼴 + 금실
TITLE_VARIANTS = (("origin.confirm-title", "origin.*.name"),)
# 무기 설명 칸의 수치 표 (GUI 픽셀): 이름 열 = 가장 긴 이름 + LABEL_GAP, 값 열 VALUE_COL (값은 오른쪽 맞춤), 두 칸 사이 COL_GAP
LABEL_KEYS = "weapon.stat.*"
LABEL_GAP = 6
VALUE_COL = 18
COL_GAP = 14
VALUE_CHARS = "0123456789.-%SABCDE+/→×–, "   # 무기 수치 표와 Dialog 표의 값 글자 (플러그인 ui/Columns 가 오른쪽 맞춤에 쓴다)
# Dialog 창의 표 칸 (5.9, 5.10, 플러그인 Lang.cell·rcell, ui/Columns): 무리마다 그 언어에서 가장 긴 글의 폭 (+ gap) 또는 고정 폭까지
# 빈칸 글자로 채운 갈래 열쇠 souls.<열쇠>.<갈래> 를 만든다. 바닐라는 창 본문과 단추 글을 줄마다 가운데에 놓으므로, 한 무리의 칸
# 폭이 같고 값 (숫자) 을 플러그인이 고정 열에 오른쪽 맞춤하면 모든 줄의 폭이 같아 열이 위아래로 선다.
#   (열쇠 꼴들, 갈래, 맞춤 left|right, 폭: ("gap", n) = 가장 긴 것 + n, ("fixed", n) = n 고정 (넘으면 오류))
CELLS = (
    (("derived.*",), "cell", "left", ("gap", 6)),            # 값 표의 이름 (능력치 창·레벨 올리기 창)
    (("origin.*.name", "origin.head-name"), "cell", "left", ("gap", 6)),   # 출신 창의 이름 칸 (머리줄 origin.head-name 도 같은 무리)
    (("origin.*.kit", "origin.head-kit"), "cell", "left", ("gap", 0)),     # 출신 창의 시작 아이템 칸 (머리줄 origin.head-kit 도)
    (("stat.*.short", "origin.head-level"), "rcell", "right", ("fixed", 24)),   # 출신 창 머리줄의 능력치·레벨 (ui/Columns.STAT_COL)
    (("stat.*.tag",), "cell", "left", ("gap", 4)),            # 값 표 줄 맨 앞의 능력치 한 글자 (체·정·기 …, VIG MND …)
)
# 칸을 이은 한 줄이 Dialog 본문에 한 줄로 서는가 (검토 뒤 실제 클라이언트에서 영어 값 표 줄이 둘로 꺾였다). 바닐라의 plain_message 는
# FocusableTextWidget (안쪽 여백 4) 이라 글이 서는 폭이 본문 폭 − 16 이다: 본문 300 → 284, 320 → 304. 숫자 칸은 플러그인 ui/Columns 의
# 상수와 같다 (VALUE 64, GAP 12, STAT_COL 24, KIT_GAP 8). 넘으면 팩 만들기가 멈춘다 (그 언어의 이름을 줄인다).
#   (이름, [CELLS 의 첫 꼴 (그 무리의 칸 폭) 또는 고정 폭 (정수)], 한도)
BODY_PAD = 16
ROWS = (
    ("값 표 줄 (ui/Columns.row, 레벨 올리기·능력치 창)", ("stat.*.tag", "derived.*", 64, 12, "derived.*", 64), 300 - BODY_PAD),
    ("출신 머리줄·출신 줄 (ui/OriginDialog)", ("origin.*.name", 24 * 7, 8, "origin.*.kit"), 320 - BODY_PAD),
)

LEGACY = re.compile("§.")
HANGUL = re.compile("[가-힣]")


def space_chars():
    """[(이름, 글자, 폭)]: glyphs.yml 의 text_space_* (기본 글꼴의 빈칸)."""
    out = []
    for i, n in enumerate(SPACE_STEPS):
        out.append((f"text_space_neg{n}", chr(SPACE_BASE + i), -n))
    for i, n in enumerate(SPACE_STEPS):
        out.append((f"text_space_pos{n}", chr(SPACE_BASE + len(SPACE_STEPS) + i), n))
    return out


def space_advances():
    return {ch: adv for _, ch, adv in space_chars()}


def spaces(adv):
    """폭 adv (정수 GUI 픽셀, 음수면 왼쪽) 를 빈칸 글자로."""
    adv = int(adv)
    base = SPACE_BASE if adv < 0 else SPACE_BASE + len(SPACE_STEPS)
    left, out = abs(adv), []
    for i in reversed(range(len(SPACE_STEPS))):
        while left >= SPACE_STEPS[i]:
            out.append(chr(base + i))
            left -= SPACE_STEPS[i]
    return "".join(out)


def rule_text(width):
    """
    무기 설명 칸 실선: 펜 - RULE_GEM_LEFT 에 마름모 (초안 그대로 글 열 왼쪽 끝), 펜 + RULE_LINE_START 에서 width 까지 줄 조각 (큰
    것부터, 조각마다 진행 폭 n + 1 을 빈칸 -1 로 되돌려 이음매 없이). 글 전체의 진행 폭은 width.
    """
    out = [spaces(-RULE_GEM_LEFT), RULE_GEM, spaces(-(RULE_GEM_ADV - RULE_GEM_LEFT - RULE_LINE_START))]
    left = int(width) - RULE_LINE_START
    for i in reversed(range(len(RULE_STEPS))):
        while left >= RULE_STEPS[i]:
            out.append(chr(RULE_RUN_BASE + i) + spaces(-1))
            left -= RULE_STEPS[i]
    return "".join(out)


WEAPONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "plugin", "src", "main", "resources", "content", "weapons.yml")
STATS = ("str", "dex", "int")           # 플러그인 item/Weapons.STATS 와 같은 차례 (1.3판: att → int)


def load_weapons(path=WEAPONS):
    """content/weapons.yml → {id: 정의 (dict)}. 무기마다 실선 폭을 재는 데 쓴다 (분류, 수치 표의 칸)."""
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def stat_cells(d):
    """
    수치 표의 칸 (플러그인 item/StatTable.lines 와 같은 차례): [이름 또는 None]. 두 칸씩 한 줄이고 홀수면 보정 줄 뒤를 비운다.
    """
    cells = []
    if int(d.get("absorb", 0) or 0) > 0:
        cells += ["absorb", "stability"]
    elif int(d.get("attack", 0) or 0) > 0:
        cells.append("attack")
    cells.append("weight")
    sc, rq = d.get("scaling") or {}, d.get("requires") or {}
    cells += ["bonus_" + s for s in STATS if isinstance(sc.get(s), str)]
    if len(cells) % 2:
        cells.append(None)
    cells += ["need_" + s for s in STATS if isinstance(rq.get(s), int)]
    return cells


def matches(key, patterns):
    return any(fnmatch.fnmatchcase(key, p) for p in patterns)


def title_keys(lang):
    """그 언어 (langpack 의 "ko"/"en" 또는 팩 코드 "ko_kr"/"en_us"/…) 에서 제목 글자로 바꾸는 바닐라 열쇠의 꼴."""
    return TITLE_KEYS if lang in ("ko", "ko_kr") else TITLE_KEYS + TITLE_KEYS_EN


def title_syllables(ko):
    """창 제목 (TITLE_KEYS) 의 한국어 글에 나오는 음절 (처음 나온 차례, 열쇠는 가나다 차례). ko = {점 열쇠: 글}."""
    out = []
    for k in sorted(ko):
        if matches(k, TITLE_KEYS) and isinstance(ko[k], str):
            for ch in ko[k]:
                if HANGUL.match(ch) and ch not in out:
                    out.append(ch)
    return out


def title_map(syllables):
    """원 글자 → 제목 글자 (기본 글꼴 개인 영역)."""
    m = {chr(c): chr(TITLE_LA_PUA + c - 0x20) for c in range(0x20, 0x7F)}
    m.update({ch: chr(TITLE_KR_PUA + i) for i, ch in enumerate(syllables)})
    return m


def to_title(text, mapping):
    """§ 꼴 기호는 그대로, 나머지는 제목 글자로 (없는 글자는 그대로)."""
    out, i = [], 0
    while i < len(text):
        if text[i] == "§" and i + 1 < len(text):
            out.append(text[i:i + 2])
            i += 2
            continue
        out.append(mapping.get(text[i], text[i]))
        i += 1
    return "".join(out)


# ─────────────────────────── 팩 글꼴 읽기 ───────────────────────────

def open_pack(pack):
    """팩 폴더 · zip 경로 · zip 바이트 → 읽개 (팩 안 경로 → 바이트, 없으면 None)."""
    if isinstance(pack, (bytes, bytearray)) or (isinstance(pack, str) and os.path.isfile(pack)):
        z = zipfile.ZipFile(io.BytesIO(pack) if isinstance(pack, (bytes, bytearray)) else pack)
        names = set(z.namelist())
        return lambda rel: z.read(rel) if rel in names else None
    if isinstance(pack, str) and os.path.isdir(pack):
        def read(rel):
            p = os.path.join(pack, *rel.split("/"))
            if not os.path.isfile(p):
                return None
            with open(p, "rb") as fh:
                return fh.read()
        return read
    return None


def _split_id(rid):
    ns, _, path = rid.partition(":")
    return (ns, path) if path else ("minecraft", ns)


class PackFonts:
    """팩의 글꼴로 글 폭을 잰다 (클라이언트와 같은 셈). read = open_pack(...)."""

    def __init__(self, read):
        self.read = read
        self._fonts = {}

    @classmethod
    def open(cls, pack):
        read = open_pack(pack)
        return None if read is None else cls(read)

    def _bitmap(self, p):
        import numpy as np
        from PIL import Image
        ns, path = _split_id(p["file"])
        data = self.read(f"assets/{ns}/textures/{path}")
        if data is None:
            raise KeyError(f"글꼴 그림 {p['file']} 이 팩에 없다")
        a = np.asarray(Image.open(io.BytesIO(data)).convert("RGBA"))[..., 3]
        rows = p["chars"]
        nr, nc = len(rows), len(rows[0])
        ch, cw = a.shape[0] // nr, a.shape[1] // nc
        scale = p.get("height", 8) / ch
        cells = (a[:nr * ch, :nc * cw] > 0).reshape(nr, ch, nc, cw).any(axis=1)     # (줄, 칸, 열)
        out = {}
        for r, row in enumerate(rows):
            for c_, glyph in enumerate(row):
                if glyph in ("\u0000", " ") or glyph in out:
                    continue
                cols = np.nonzero(cells[r, c_])[0]
                w = int(cols[-1]) + 1 if len(cols) else 0
                out[glyph] = int(0.5 + w * scale) + 1
        return out

    def table(self, fid, depth=0):
        """글꼴 fid 의 공급자 차례대로 [{글자: 폭}] (reference 는 펼친다)."""
        if fid in self._fonts:
            return self._fonts[fid]
        ns, path = _split_id(fid)
        data = self.read(f"assets/{ns}/font/{path}.json")
        maps = []
        if data is not None and depth < 8:
            for p in json.loads(data.decode("utf-8")).get("providers", []):
                t = p.get("type")
                if t == "bitmap":
                    maps.append(self._bitmap(p))
                elif t == "space":
                    maps.append({k: v for k, v in p.get("advances", {}).items()})
                elif t == "reference":
                    maps.extend(self.table(p["id"], depth + 1))
        self._fonts[fid] = maps
        return maps

    def advance(self, fid, ch):
        for m in self.table(fid):
            if ch in m:
                return m[ch]
        return None

    def width(self, fid, text):
        """글 한 줄의 진행 폭 (GUI 픽셀, § 꼴 기호는 폭이 없다). 팩 글꼴에 없는 글자가 있으면 KeyError."""
        w = 0
        for ch in LEGACY.sub("", text):
            a = self.advance(fid, ch)
            if a is None:
                raise KeyError(f"글꼴 {fid} 에 없는 글자 {ch!r} (U+{ord(ch):04X}) ({text!r})")
            w += a
        return int(round(w))


# ─────────────────────────── 언어 파일 짜기 ───────────────────────────

def with_divider(title, width, divider_adv):
    """제목 뒤에 금실: 펜 W → (W - D)/2 에서 금실 (진행 A) → 다시 W. 글 전체 진행 폭은 W 그대로."""
    s1 = -int(math.floor((width + DIVIDER_W) / 2.0 + 0.5))
    return title + spaces(s1) + DIVIDER + spaces(-(s1 + divider_adv))


class Typeset:
    """
    langpack.build 가 만든 언어 파일 {팩 안 경로: {열쇠: 글}} 을 팩 글꼴로 짠다 (apply). weapons = {id: 정의} (기본은
    content/weapons.yml): 무기마다 실선 폭을 잴 때 분류와 수치 표의 칸을 본다.
    """

    def __init__(self, fonts, weapons=None):
        self.fonts = fonts
        self.weapons = load_weapons() if weapons is None else weapons

    def apply(self, files, ko_lines):
        """ko_lines = langpack.lines(ko 표) (점 열쇠 → 한국어 원문, 꼴 태그 포함). files 를 고쳐 돌려준다."""
        mapping = title_map(title_syllables(ko_lines))
        div_adv = {f: self.fonts.advance(f, DIVIDER) for f in (DEFAULT_FONT, TITLE_FONT)}
        for rel, data in files.items():
            if rel.startswith("assets/minecraft/lang/"):
                keys = title_keys(rel.rsplit("/", 1)[-1][:-len(".json")])
                for k in list(data):
                    vk = "vanilla." + k
                    if not matches(vk, keys):
                        continue
                    v = to_title(data[k], mapping)
                    font = next((f for p, f in DIVIDED if fnmatch.fnmatchcase(vk, p)), None)
                    if font:
                        v = with_divider(v, self.fonts.width(font, v), self._div(div_adv, font))
                    data[k] = v
            elif rel.startswith("assets/souls/lang/"):
                if rel.endswith("/ko_kr.json"):
                    for k in list(data):
                        data[k] = data[k].replace("\u00b7", KO_MIDDOT)
                labels = {k: v for k, v in data.items() if fnmatch.fnmatchcase(k, "souls." + LABEL_KEYS)}
                col = 0
                if labels:
                    widths = {k: self.fonts.width(DEFAULT_FONT, v) for k, v in labels.items()}
                    col = max(widths.values()) + LABEL_GAP
                    for k, v in labels.items():
                        data[k] = v + spaces(col - widths[k])
                if "souls." + RULE_KEY in data:
                    widths = {wid: self.weapon_width(data, col, wid, d) for wid, d in self.weapons.items()
                              if "souls.weapon." + wid + ".name" in data}
                    data["souls." + RULE_KEY] = rule_text(max(widths.values(), default=0))
                    for wid, w in widths.items():
                        data[f"souls.{RULE_KEY}.{wid}"] = rule_text(w)
                for k in list(data):
                    if not k.startswith("souls."):
                        continue
                    font = next((f for p, f in DIVIDED if fnmatch.fnmatchcase(k[len("souls."):], p)), None)
                    if font:
                        data[k] = with_divider(data[k], self.fonts.width(font, data[k]), self._div(div_adv, font))
                for key, pattern in TITLE_VARIANTS:
                    if "souls." + key not in data:
                        continue
                    head, _, tail = pattern.partition("*")
                    for k in sorted(data):
                        name = k[len("souls."):]
                        if not k.startswith("souls.") or not fnmatch.fnmatchcase(name, pattern) or name.count(".") != pattern.count("."):
                            continue
                        branch = name[len(head):len(name) - len(tail)]
                        v = data[k]
                        data[f"souls.{key}.{branch}"] = with_divider(v, self.fonts.width(TITLE_FONT, v), self._div(div_adv, TITLE_FONT))
                self.cells(data, rel)
        return files

    def cells(self, data, rel=""):
        """
        CELLS 의 칸 열쇠를 더한다 (souls.<열쇠>.cell / .rcell). 같은 무리의 칸은 모두 같은 폭이다. 고정 폭을 넘는 글은 ValueError
        (그 언어의 글을 줄이거나 ui/Columns 의 폭을 늘린다). 칸 열쇠는 자리 (%s) 가 없는 글만.
        """
        cols = {}
        for patterns, branch, align, (kind, n) in CELLS:
            group = {k: v for k, v in data.items() if k.startswith("souls.") and not k.endswith(".cell") and not k.endswith(".rcell")
                     and any(fnmatch.fnmatchcase(k[len("souls."):], p) for p in patterns) and "%" not in v.replace("%%", "")}
            if not group:
                continue
            widths = {k: self.fonts.width(DEFAULT_FONT, v.replace("%%", "%")) for k, v in group.items()}
            col = max(widths.values()) + n if kind == "gap" else n
            cols[patterns[0]] = col
            for k, v in group.items():
                if widths[k] > col:
                    raise ValueError(f"{rel}: {k} 의 글 폭 {widths[k]} 이 칸 폭 {col} 을 넘는다 ({v!r}, pack/typeset.py CELLS)")
                pad = spaces(col - widths[k])
                data[f"{k}.{branch}"] = v + pad if align == "left" else pad + v
        for name, parts, limit in ROWS:
            if not all(isinstance(x, int) or x in cols for x in parts):
                continue
            w = sum(x if isinstance(x, int) else cols[x] for x in parts)
            if w > limit:
                raise ValueError(f"{rel}: {name} 의 폭 {w} 이 본문에 서는 폭 {limit} 을 넘는다 (칸 "
                                 f"{[cols.get(x, x) for x in parts]}, pack/typeset.py ROWS: 그 언어의 이름을 줄인다)")

    @staticmethod
    def cell_keys(keys):
        """lang 열쇠 (souls. 없이) 에서 팩이 더하는 칸 열쇠 (souls. 없이). 플러그인의 /souls check 와 langcheck 가 같은 셈을 한다."""
        out = []
        for patterns, branch, _, _ in CELLS:
            for k in keys:
                if any(fnmatch.fnmatchcase(k, p) for p in patterns):
                    out.append(f"{k}.{branch}")
        return out

    def weapon_width(self, data, label_col, wid, d):
        """
        무기 wid 의 설명 칸 글 열 폭 (한 언어, GUI 픽셀): 이름 (제목 글꼴)·분류 줄·수치 표·설명 줄 가운데 가장 넓은 것.
        수치 표 한 줄은 칸 하나가 이름 열 + 값 열 (label_col + VALUE_COL), 두 칸이면 사이 COL_GAP.
        """
        cells = stat_cells(d)
        pair = any(cells[i] and i + 1 < len(cells) and cells[i + 1] for i in range(0, len(cells), 2))
        w = (2 * (label_col + VALUE_COL) + COL_GAP if pair else label_col + VALUE_COL) if label_col else 0
        w = max(w, self.fonts.width(TITLE_FONT, data["souls.weapon." + wid + ".name"]))
        cls = data.get("souls.weapon.class." + str(d.get("class", "")))
        if cls is not None:
            w = max(w, self.fonts.width(DEFAULT_FONT, cls.replace("%%", "%")))
        pre = "souls.weapon." + wid + ".lore"
        for k, v in data.items():
            if k == pre or fnmatch.fnmatchcase(k, pre + ".*"):
                w = max(w, self.fonts.width(DEFAULT_FONT, v.replace("%%", "%")))
        return w

    @staticmethod
    def _div(div_adv, font):
        a = div_adv.get(font)
        if a is None:
            raise KeyError(f"글꼴 {font} 에 제목 밑 금실 (U+{ord(DIVIDER):04X}) 이 없다")
        return a

    def value_widths(self):
        """플러그인 수치 표의 값 글자 폭 (glyphs.yml 의 stats)."""
        return {ch: self.fonts.advance(DEFAULT_FONT, ch) for ch in VALUE_CHARS}


def font_of(style):
    """꼴 태그 (YAML 글 맨 앞) 가 고른 글꼴: <font:…> 가 있으면 그것, 없으면 기본 글꼴. 창 제목은 제목 글자로 바꾼 뒤 기본 글꼴."""
    m = re.search(r"<font:([a-z0-9_.-]+:[a-z0-9_./-]+)>", style or "")
    return m.group(1) if m else DEFAULT_FONT
