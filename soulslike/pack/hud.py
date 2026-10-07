"""
HUD 그림과 글꼴 (DESIGN.md 10.2, 10.3, 10.9). gen_pack.py 가 부른다.

M0 에서 만드는 것
  스태미나 막대   경험치 막대 그림 둘 (gui/sprites/hud/experience_bar_background, _progress).
                  녹슨 쇠 테 + 이끼색 채움. 레벨 숫자는 플러그인이 레벨 0 을 보내 숨긴다.
  허기            food_* 여섯 장을 투명하게 (허기 6 은 달리기를 막는 데만 쓴다, 3.2).
  사망 화면 제목  "YOU DIED" (사용자 결정 3). 손으로 찍은 글자 art/you_died.txt 를
                  minecraft:default 글꼴의 개인 영역 문자로 넣는다 (언어 문자열은 글꼴을 고를 수 없다, 10.9).
  souls:hud 글꼴  행동 막대·제목에 쓸 자리 맞춤 빈칸 (음수·양수). 그림 글자(숫자, 소울 표식, 막대)는 M4.

글자 표 (glyphs.yml)
  build() 가 돌려주는 Glyph 목록을 gen_pack 이 plugin/src/main/resources/glyphs.yml 로 쓴다.
  이름에는 점을 쓰지 않는다 (Bukkit YAML 은 점을 경로 구분자로 읽는다): you_died_y, space_neg8 처럼.
  플러그인 hud/Glyphs 는 그 파일만 읽고 코드에 문자 번호를 적지 않는다.
  너비(width)는 클라이언트가 재는 것과 같은 식으로 계산한 진행 폭(글꼴 픽셀)이다.

문자 번호
  U+E000~E01F  minecraft:default (사망 화면 제목 글자와 그 사이 빈칸)
  U+E020~E03F  souls:hud 빈칸
  U+E040~E0FF  souls:hud 그림 글자 (M4 의 숫자·소울 표식, 마법을 넣을 때의 마나 막대 자리)

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

# 그림 이름, 문자. 두 D 는 따로 그린 다른 그림이다.
YOU_DIED_LETTERS = [("y", "\ue000"), ("o", "\ue001"), ("u", "\ue002"), ("d1", "\ue003"),
                    ("i", "\ue004"), ("e", "\ue005"), ("d2", "\ue006")]
YOU_DIED_GAP = ("you_died_gap", "\ue00e", 3)     # 글자 사이 (글꼴 픽셀). 소울 시리즈처럼 넓게 띄운다
YOU_DIED_WORD = ("you_died_word", "\ue00f", 10)  # YOU 와 DIED 사이
# 글자 그림 24줄을 글꼴 높이 12 로 넣는다 (배율 0.5). 사망 화면 제목은 2배로 그려지므로 그림 한 칸 = GUI 1픽셀.
YOU_DIED_HEIGHT = 12
# 줄 위쪽에서 7 - ascent 만큼 내려 그린다. 9 면 바닐라 제목 글씨와 가운데가 거의 같다 (y 28~40, 바닐라 30~37).
YOU_DIED_ASCENT = 9


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


def death_title(glyphs):
    """deathScreen.title 에 넣을 문자열: Y O U / D I E D 를 빈칸 문자로 띄운다."""
    by = {g.name: g.char for g in glyphs}
    gap, word = by[YOU_DIED_GAP[0]], by[YOU_DIED_WORD[0]]
    you = gap.join(by["you_died_" + n] for n in ("y", "o", "u"))
    died = gap.join(by["you_died_" + n] for n in ("d1", "i", "e", "d2"))
    return you + word + died


# ─────────────────────────── 스태미나 막대 ───────────────────────────

BAR_W, BAR_H = 182, 5


def _row(length, base, marks):
    """바탕색 한 줄에 손으로 고른 자리 [(색, [(x, 길이), ...]), ...] 를 칠한다. x 는 막대 왼쪽 끝 기준."""
    row = [base] * length
    for col, spots in marks:
        for x, n in spots:
            for i in range(n):
                if 0 <= x + i < length:
                    row[x + i] = col
    return row


def stamina_bar():
    """
    배경: 녹슨 쇠 테와 빈 홈. 위 테는 빛을 받아 rust2, 아래 테는 그늘이라 rust0.
          닳은 곳·이 빠진 곳·리벳 다섯 개는 손으로 자리를 골랐고, 리벳은 하나하나 모양이 다르다.
    채움: 이끼 세 단 (위 moss2, 가운데 moss2 와 moss1 이 섞임, 아래 moss1 과 moss0).
          테 줄과 양 끝 열은 비워 배경의 테가 그대로 보이게 한다 (바닐라는 채움을 배경 위에 폭만큼 잘라 그린다).
    """
    W = BAR_W
    bg = Image.new("RGBA", (W, BAR_H), (0, 0, 0, 0))
    px = bg.load()
    rows = [
        _row(W, "rust2", [("rust1", [(6, 4), (27, 2), (33, 7), (61, 3), (79, 5), (102, 2), (113, 6), (139, 3),
                                     (151, 4), (170, 5)]),
                          ("rust0", [(15, 1), (48, 1), (96, 1), (124, 1), (157, 1)]),
                          ("ash0", [(44, 2), (117, 1)])]),
        _row(W, "ash0", [("rust0", [(19, 1), (131, 1), (45, 1)])]),
        _row(W, "ash0", [("ash1", [(110, 2)]), ("rust0", [(19, 1)])]),
        _row(W, "ash0", [("ash1", [(30, 4), (87, 3), (137, 5)])]),
        _row(W, "rust0", [("rust1", [(3, 6), (22, 3), (40, 9), (67, 4), (85, 2), (99, 8), (120, 3), (141, 6),
                                     (166, 4)]),
                          ("ash0", [(150, 1)])]),
    ]
    for y, row in enumerate(rows):
        for x in range(1, W - 1):
            px[x, y] = c(row[x])
    # 리벳: 같은 모양을 두 번 쓰지 않는다
    for (x, y), col in {(19, 0): "rust3", (20, 0): "rust0",                       # 녹물이 아래로 흘렀다
                        (57, 0): "rust1", (58, 0): "rust3",
                        (90, 0): "rust3", (90, 4): "rust2",                       # 위아래로 꿰뚫은 못
                        (131, 0): "rust3", (132, 0): "rust3", (133, 0): "rust0",  # 머리가 큰 것
                        (163, 0): "rust1", (164, 0): "rust3"}.items():
        px[x, y] = c(col)
    # 양 끝 마개: 왼쪽은 두껍게 녹슬고, 오른쪽은 위 귀퉁이가 떨어져 나갔다
    for y, col in enumerate(("rust1", "rust3", "rust2", "rust2", "rust0")):
        px[0, y] = c(col)
    for y, col in enumerate((None, "rust2", "rust1", "rust2", "rust1")):
        if col:
            px[W - 1, y] = c(col)

    fill = Image.new("RGBA", (W, BAR_H), (0, 0, 0, 0))
    fp = fill.load()
    frows = [
        _row(W, "moss2", [("moss1", [(12, 3), (40, 2), (66, 5), (95, 2), (121, 4), (150, 3), (173, 2)])]),
        _row(W, "moss2", [("moss1", [(1, 3), (9, 4), (22, 7), (44, 3), (53, 9), (77, 4), (98, 6), (115, 3),
                                     (128, 8), (146, 2), (159, 6), (176, 4)]),
                          ("moss0", [(76, 1), (133, 2)])]),
        _row(W, "moss1", [("moss0", [(1, 4), (14, 6), (31, 3), (47, 5), (70, 8), (89, 2), (104, 7), (125, 3),
                                     (138, 9), (162, 5), (174, 6)])]),
    ]
    for y, row in enumerate(frows):
        for x in range(1, W - 1):
            fp[x, y + 1] = c(row[x])
    return bg, fill


# ─────────────────────────── 빌드 ───────────────────────────

FOOD_SPRITES = ("food_empty", "food_half", "food_full", "food_empty_hunger", "food_half_hunger", "food_full_hunger")

# souls:hud 빈칸: 음수는 왼쪽으로, 양수는 오른쪽으로 민다. 2의 거듭제곱이라 조합으로 아무 폭이나 만든다.
SPACE_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)


def build(out):
    """out (팩 뿌리) 에 HUD 그림과 글꼴을 쓰고 Glyph 목록을 돌려준다."""
    glyphs = []

    # 스태미나 막대와 투명한 허기
    bg, fill = stamina_bar()
    save(bg, sprite_path(out, "minecraft", "gui", "sprites", "hud", "experience_bar_background.png"))
    save(fill, sprite_path(out, "minecraft", "gui", "sprites", "hud", "experience_bar_progress.png"))
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

    # souls:hud: 빈칸만 (그림 글자는 M4)
    advances = {}
    code = 0xE020
    for sign, label in ((-1, "neg"), (1, "pos")):
        for step in SPACE_STEPS:
            ch = chr(code)
            code += 1
            advances[ch] = sign * step
            glyphs.append(Glyph(f"space_{label}{step}", ch, sign * step, HUD_FONT, "space"))
    hud_font = {"providers": [{"type": "space", "advances": advances}]}

    fonts = {
        ("minecraft", "default"): default_font,
        # 유니코드 글꼴 강제 설정을 켠 사람도 같은 제목을 보게 같은 공급자를 넣는다
        ("minecraft", "uniform"): default_font,
        (NS, "hud"): hud_font,
    }
    return glyphs, fonts
