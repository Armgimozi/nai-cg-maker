"""
HUD 그림과 글꼴 (DESIGN.md 10.2, 10.3, 10.9). gen_pack.py 가 부른다.

M0 에서 만드는 것
  허기            food_* 여섯 장을 투명하게 (허기 6 은 달리기를 막는 데만 쓴다, 3.2).
  사망 화면 제목  "YOU DIED" (사용자 결정 3). 손으로 찍은 글자 art/you_died.txt 를
                  minecraft:default 글꼴의 개인 영역 문자로 넣는다 (언어 문자열은 글꼴을 고를 수 없다, 10.9).
  souls:hud 글꼴  행동 막대·제목에 쓸 자리 맞춤 빈칸 (음수·양수), 플러그인 화면 제목용 YOU DIED (death.title: true).
                  그림 글자(숫자, 소울 표식, 막대)는 M4.
  하트·스태미나 막대·단축 슬롯 같은 바닐라 HUD 그림은 gui_skin.py 가 그린다 (스태미나 막대 그림은 거기 하나뿐).
  레벨 숫자는 플러그인이 레벨 0 을 보내 숨긴다.

글자 표 (glyphs.yml)
  build() 가 돌려주는 Glyph 목록을 gen_pack 이 plugin/src/main/resources/glyphs.yml 로 쓴다.
  이름에는 점을 쓰지 않는다 (Bukkit YAML 은 점을 경로 구분자로 읽는다): you_died_y, space_neg8 처럼.
  플러그인 hud/Glyphs 는 그 파일만 읽고 코드에 문자 번호를 적지 않는다.
  너비(width)는 클라이언트가 재는 것과 같은 식으로 계산한 진행 폭(글꼴 픽셀)이다.

문자 번호
  U+E000~E01F  minecraft:default (사망 화면 제목 글자와 그 사이 빈칸)
  U+E020~E03F  souls:hud 빈칸 (E020~E02F 자리 맞춤, E030·E031 플러그인 제목의 글자 사이)
  U+E040~E0EF  souls:hud 그림 글자 (M4 의 숫자·소울 표식, 술을 넣을 때의 온기 막대 자리)
  U+E0F0~E0F6  souls:hud 플러그인 화면 제목 YOU DIED 글자

마나 막대 자리 (사용자 결정 2)
  체력 = 하트 줄, 스태미나 = 경험치 막대. 허기 줄은 투명하게 비워 두었으므로 단축 슬롯 오른쪽 위가 빈다.
  마나 막대는 나중에 souls:hud 의 그림 글자(음수 ascent 로 내려 그 빈자리에 맞춘다)로 넣는다.
  여기서는 그 자리와 문자 번호만 비워 둔다.
"""
import os

from PIL import Image

from palette import c

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
NS = "souls"
HUD_FONT = NS + ":hud"
DEFAULT_FONT = "minecraft:default"


class Glyph:
    """glyphs.yml 한 줄. kind 는 bitmap 또는 space."""

    def __init__(self, name, char, width, font, kind):
        self.name, self.char, self.width, self.font, self.kind = name, char, width, font, kind


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def sprite_path(out, ns, *parts):
    return os.path.join(out, "assets", ns, "textures", *parts)


# ─────────────────────────── 손으로 찍은 글자 읽기 ───────────────────────────

# art/*.txt 의 기호 → 팔레트 이름
YOU_DIED_INK = {"o": "gore0", "-": "gore1", "#": "gore2", "+": "gore3"}


def load_grids(path):
    """
    [이름] 다음 줄부터 빈 줄까지가 그림 한 장. '# ' (샵 + 빈칸) 으로 시작하는 줄은 설명.
    글자 줄은 '#' 로 시작할 수 있으므로 샵 하나만으로는 설명이 아니다.
    """
    grids, cur = {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("# ") or line == "#" or not line.strip():
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1]
                grids[cur] = []
                continue
            grids[cur].append(line)
    for name, rows in grids.items():
        widths = {len(r) for r in rows}
        if len(widths) != 1:
            raise ValueError(f"{path} [{name}]: 줄 길이가 다르다 {sorted(widths)}")
    return grids


def grid_image(rows, ink, clear="."):
    """기호 그림 → RGBA. clear 기호는 투명 (None 이면 투명 칸이 없다)."""
    img = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == clear:
                continue
            if ch not in ink:
                raise ValueError(f"모르는 기호 {ch!r} ({x},{y})")
            px[x, y] = c(ink[ch])
    return img


def glyph_advance(img, x0, cell_w, cell_h, scale):
    """클라이언트 bitmap 글꼴과 같은 식: 오른쪽에서부터 첫 불투명 열 + 1 을 재고, (int)(0.5 + 폭 × 배율) + 1."""
    a = img.getchannel("A").load()
    width = 0
    for i in range(cell_w - 1, -1, -1):
        if any(a[x0 + i, y] for y in range(cell_h)):
            width = i + 1
            break
    return int(0.5 + width * scale) + 1


# ─────────────────────────── 사망 화면 제목 ───────────────────────────

# 그림 이름, 문자. 두 D 는 따로 그린 다른 그림이다 (윤곽부터 다르다).
YOU_DIED_LETTERS = [("y", "\ue000"), ("o", "\ue001"), ("u", "\ue002"), ("d1", "\ue003"),
                    ("i", "\ue004"), ("e", "\ue005"), ("d2", "\ue006")]
YOU_DIED_GAP = ("you_died_gap", "\ue00e", 3)     # 글자 사이 (글꼴 픽셀). 소울 시리즈처럼 넓게 띄운다
YOU_DIED_WORD = ("you_died_word", "\ue00f", 10)  # YOU 와 DIED 사이
# 글자 그림 24줄을 글꼴 높이 12 로 넣는다 (배율 0.5). 사망 화면 제목은 2배로 그려지므로 그림 한 칸 = GUI 1픽셀.
YOU_DIED_HEIGHT = 12
# 사망 화면은 제목 줄을 GUI y 60 (2배 좌표 30) 에 그리고, 글자 위쪽은 줄 위쪽에서 7 - ascent 만큼 아래다 (2배).
# 단추는 화면 높이/4 + 72 (GUI 높이가 가장 작은 240 일 때 132) 부터라, 그 위로 가능한 한 가운데에 둔다:
# ascent -5 면 GUI y 84~108 (높이 240 에서 가운데가 40%), 단추와 24 픽셀 띈다. 바닐라 글씨 자리(9)보다 24 픽셀 아래.
YOU_DIED_ASCENT = -5

# 플러그인 화면 제목용 (death.title: true). 사망 화면 판과 같은 그림을 souls:hud 글꼴에 따로 넣어, 사망 화면 판의
# 자리(ascent)를 바꿔도 이 판은 그대로 둔다. 화면 제목은 4배로 그려지므로 높이 12 면 그림 한 칸이 GUI 2픽셀:
# 사망 화면 판의 두 배 크기다 (이 판을 고르는 까닭). 대신 단추·HUD 와 픽셀 크기가 섞인다 (16절 질문 4 에 적었다).
# 제목 줄은 화면 가운데에서 -10 (4배 좌표) 에 놓이고 글자 아래끝은 -10 + 7 - ascent + 12 이라, ascent 9 면 가운데보다
# GUI 24픽셀 위에서 끝난다. 세로 한가운데에 두면 바닐라 단추(화면 높이/4 + 72)와 겹친다.
TITLE_LETTERS = [(name, chr(0xE0F0 + i)) for i, (name, _) in enumerate(YOU_DIED_LETTERS)]
TITLE_HEIGHT = 12
TITLE_ASCENT = 9
TITLE_GAP = ("you_died_title_gap", "\ue030", 3)
TITLE_WORD = ("you_died_title_word", "\ue031", 10)


def you_died_sheet():
    grids = load_grids(os.path.join(ART, "you_died.txt"))
    cell_h = len(grids["y"])
    cell_w = max(len(grids[n][0]) for n, _ in YOU_DIED_LETTERS)
    sheet = Image.new("RGBA", (cell_w * len(YOU_DIED_LETTERS), cell_h), (0, 0, 0, 0))
    for i, (name, _) in enumerate(YOU_DIED_LETTERS):
        rows = grids[name]
        if len(rows) != cell_h:
            raise ValueError(f"you_died [{name}]: 높이 {len(rows)} (다른 글자는 {cell_h})")
        sheet.alpha_composite(grid_image(rows, YOU_DIED_INK), (i * cell_w, 0))
    return sheet, cell_w, cell_h


def death_title(glyphs, prefix="you_died_"):
    """deathScreen.title 에 넣을 문자열: Y O U / D I E D 를 빈칸 문자로 띄운다."""
    by = {g.name: g.char for g in glyphs}
    gap, word = by[prefix + "gap"], by[prefix + "word"]
    you = gap.join(by[prefix + n] for n in ("y", "o", "u"))
    died = gap.join(by[prefix + n] for n in ("d1", "i", "e", "d2"))
    return you + word + died


def plugin_title(glyphs):
    """플러그인 화면 제목 한 줄 (souls:hud 글꼴)."""
    return death_title(glyphs, "you_died_title_")


# ─────────────────────────── 빌드 ───────────────────────────

FOOD_SPRITES = ("food_empty", "food_half", "food_full", "food_empty_hunger", "food_half_hunger", "food_full_hunger")

# souls:hud 빈칸: 음수는 왼쪽으로, 양수는 오른쪽으로 민다. 2의 거듭제곱이라 조합으로 아무 폭이나 만든다.
SPACE_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)


def build(out):
    """out (팩 뿌리) 에 HUD 그림과 글꼴을 쓰고 Glyph 목록을 돌려준다."""
    glyphs = []

    # 투명한 허기 (스태미나 막대는 gui_skin)
    for name in FOOD_SPRITES:
        save(Image.new("RGBA", (9, 9), (0, 0, 0, 0)), sprite_path(out, "minecraft", "gui", "sprites", "hud", name + ".png"))

    # 사망 화면 제목: 글자 그림 한 장 + 기본 글꼴에 더할 공급자
    sheet, cell_w, cell_h = you_died_sheet()
    save(sheet, sprite_path(out, NS, "font", "you_died.png"))
    scale = YOU_DIED_HEIGHT / cell_h
    for i, (name, ch) in enumerate(YOU_DIED_LETTERS):
        glyphs.append(Glyph("you_died_" + name, ch, glyph_advance(sheet, i * cell_w, cell_w, cell_h, scale),
                            DEFAULT_FONT, "bitmap"))
    for name, ch, adv in (YOU_DIED_GAP, YOU_DIED_WORD):
        glyphs.append(Glyph(name, ch, adv, DEFAULT_FONT, "space"))
    default_font = {"providers": [
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": YOU_DIED_HEIGHT, "ascent": YOU_DIED_ASCENT,
         "chars": ["".join(ch for _, ch in YOU_DIED_LETTERS)]},
        {"type": "space", "advances": {YOU_DIED_GAP[1]: YOU_DIED_GAP[2], YOU_DIED_WORD[1]: YOU_DIED_WORD[2]}},
    ]}

    # souls:hud: 빈칸 (그림 글자는 M4) + 플러그인 화면 제목
    advances = {}
    code = 0xE020
    for sign, label in ((-1, "neg"), (1, "pos")):
        for step in SPACE_STEPS:
            ch = chr(code)
            code += 1
            advances[ch] = sign * step
            glyphs.append(Glyph(f"space_{label}{step}", ch, sign * step, HUD_FONT, "space"))
    tscale = TITLE_HEIGHT / cell_h
    for i, (name, ch) in enumerate(TITLE_LETTERS):
        glyphs.append(Glyph("you_died_title_" + name, ch, glyph_advance(sheet, i * cell_w, cell_w, cell_h, tscale),
                            HUD_FONT, "bitmap"))
    for name, ch, adv in (TITLE_GAP, TITLE_WORD):
        advances[ch] = adv
        glyphs.append(Glyph(name, ch, adv, HUD_FONT, "space"))
    hud_font = {"providers": [
        {"type": "space", "advances": advances},
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": TITLE_HEIGHT, "ascent": TITLE_ASCENT,
         "chars": ["".join(ch for _, ch in TITLE_LETTERS)]},
    ]}

    fonts = {
        ("minecraft", "default"): default_font,
        # 유니코드 글꼴 강제 설정을 켠 사람도 같은 제목을 보게 같은 공급자를 넣는다
        ("minecraft", "uniform"): default_font,
        (NS, "hud"): hud_font,
    }
    return glyphs, fonts
