"""
HUD 그림과 글꼴 (DESIGN.md 10.2, 10.3, 10.9). gen_pack.py 가 부른다.

만드는 것
  허기            food_* 여섯 장을 투명하게 (허기 6 은 달리기를 막는 데만 쓴다, 3.2).
  사망 화면 제목  "YOU DIED" (사용자 결정 3). 손으로 찍은 픽셀 글자 art/you_died.txt (평평한 생피, 윗가장자리만 밝게) 를
                  minecraft:default 글꼴의 개인 영역 문자로 넣는다 (언어 문자열은 글꼴을 고를 수 없다, 10.9). 뒤에 화면을
                  가로지르는 검은 띠 (2 배 그림, 청동 실).
  souls:hud 글꼴  자리 맞춤 빈칸 (음수·양수), 플러그인 화면 제목용 YOU DIED (death.title: true),
                  다크 소울 HUD (2026-10-07 사용자 결정, 2026-10-08 고딕 촛불 시안 B): 왼쪽 위 막대 셋 (체력·마나·스태미나) 의
                  조각과 마구리, 오른쪽 아래 소울 상자·넋 표식·숫자, 화면 아래 가운데 보스 막대 (체력·잃은 몫·자세 조각과
                  마구리). 막대 몸의 색 짜임은 bar_styles.py. 자리는 아래 "다크 소울 HUD" 의 머리말. 그림은 GUI 한 픽셀에 2 텍셀
                  (uidraw.py, 숫자는 4 텍셀) 이고 글꼴 셰이더가 넓이 평균으로 읽는다 (shaders.py).
  HUD 셰이더 덩이 hud_shader(): 바닐라 1.21.11 rendertype_text.vsh 에 한 덩이를 더해 표식 색의 HUD 글만 옮긴다 (막대 셋 왼쪽 위,
                  소울 상자 오른쪽 아래, 보스 막대 화면 아래 가운데). shaders.py 가 GUI 글자 덩이를 더해 쓴다 (10.8).
  하트·방어·경험치 막대는 gui_skin.py 가 투명하게 한다. 레벨 숫자는 플러그인이 레벨 0 을 보내 숨긴다.

글자 표 (glyphs.yml)
  build() 가 돌려주는 Glyph 목록을 gen_pack 이 plugin/src/main/resources/glyphs.yml 로 쓴다.
  이름에는 점을 쓰지 않는다 (Bukkit YAML 은 점을 경로 구분자로 읽는다): you_died_y, space_neg8 처럼.
  플러그인 hud/Glyphs 는 그 파일만 읽고 코드에 문자 번호를 적지 않는다.
  너비(width)는 클라이언트가 재는 것과 같은 식으로 계산한 진행 폭(글꼴 픽셀)이다.

문자 번호
  U+E000~E01F  minecraft:default (사망 화면 제목 글자와 그 사이 빈칸, E007~E009 사망 화면 띠 조각, E010~E012 띠의 빈칸)
  U+E020~E03F  souls:hud 빈칸 (E020~E02F 자리 맞춤, E030·E031 플러그인 제목의 글자 사이)
  U+E040~E0EF  souls:hud 그림 글자 (HUD 막대 조각·마구리, 소울 상자·표식·숫자, 보스 막대 조각·마구리. 지금 116개)
  U+E0F0~E0F6  souls:hud 플러그인 화면 제목 YOU DIED 글자
  (기본 글꼴의 본문·제목 글자, 금실, 빈칸은 fonts.py 와 typeset.py)

glyphs.yml 의 layout
  플러그인이 HUD 를 짤 때 쓰는 자리 값 (layout()): 셰이더 없는 가장자리 여백, 가운데에서 왼쪽·오른쪽으로 민 거리,
  표식 색 (막대 셋, 소울 상자, 보스 막대·이름·그림자·지울 사본·마구리), 소울 상자 폭, 보스 막대 폭. 셰이더와 같은 값이어야 하므로
  여기 한 곳에서 정해 둘 다에 쓴다.
"""
import os

import numpy as np
from PIL import Image

import bar_styles
import uidraw
import palette
from palette import c
from uidraw import Img, Mask

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

# art/*.txt 의 기호 → 팔레트 이름 (꼴만 정한다: 칠은 아래 you_died_sheet 가 평평한 생피와 윗가장자리로 다시 한다)
YOU_DIED_INK = {"o": "gore0", "-": "gore1", "#": "gore2", "+": "gore3"}
# 그림 이름, 문자. 두 D 는 따로 그린 다른 그림이다 (윤곽부터 다르다).
YOU_DIED_LETTERS = [("y", "\ue000"), ("o", "\ue001"), ("u", "\ue002"), ("d1", "\ue003"),
                    ("i", "\ue004"), ("e", "\ue005"), ("d2", "\ue006")]
YOU_DIED_GAP = ("you_died_gap", "\ue00e", 3)     # 글자 사이 (글꼴 픽셀). 소울 시리즈처럼 넓게 띄운다
YOU_DIED_WORD = ("you_died_word", "\ue00f", 10)  # YOU 와 DIED 사이
# 글자 그림 24줄을 글꼴 높이 12 로 넣는다 (배율 0.5). 사망 화면 제목은 2배로 그려지므로 그림 한 칸 = GUI 1픽셀
# (2026-10-08 사용자: 손으로 찍은 픽셀 글자가 더 낫다. 제목 글꼴 Cinzel 로 그린 매끈한 판은 취소).
YOU_DIED_HEIGHT = 12
# 사망 화면은 제목 줄을 GUI y 60 (2배 좌표 30) 에 그리고, 글자 위쪽은 줄 위쪽에서 7 - ascent 만큼 아래다 (2배).
# 단추는 화면 높이/4 + 72 (GUI 높이가 가장 작은 240 일 때 132) 부터라, 그 위로 가능한 한 가운데에 둔다:
# ascent -5 면 GUI y 84~108 (높이 240 에서 가운데가 40%), 단추와 24 픽셀 띈다. 바닐라 글씨 자리(9)보다 24 픽셀 아래.
YOU_DIED_ASCENT = -5
# 다크 소울의 사망 화면처럼 YOU DIED 뒤에 화면을 가로지르는 검은 띠 (2026-10-07 다크 소울 UI, 2026-10-08 사용자 결정: 테두리 없이,
# 위아래 끝이 흐려지며 사라지는 다크 소울 3 의 띠). 선·테·단단한 가장자리는 없다. 띠는 셰이더가 읽는 알파 지도다
# (RGB 는 표식 DEATH_BAND_TAG, 알파가 짙기): 글꼴 셰이더 (shaders.py) 가 먹 (ink0) 으로 칠하고, 바닐라 그림자 사본은 그리지 않고
# (띠가 두 겹으로 짙어지지 않게), 다른 그림 글자의 "알파 0.1 아래는 버림" 을 띠에는 하지 않는다 (꼬리가 끊기지 않게).
#   세로   높이 DEATH_BAND_H_GUI (72) GUI 픽셀 = 글자 높이 (24) 의 세 배, 글자 가운데 (GUI y 96) 에 맞춘다 (GUI y 60~132).
#          가운데에서 DEATH_BAND_CORE (13) 까지 DEATH_BAND_ALPHA, 그 밖은 끝 (36) 까지 smoothstep 으로 0 (23 GUI 픽셀에 걸쳐).
#          GUI 한 픽셀에 2 텍셀 (DEATH_BAND_TEX) 이라 계단이 GUI 배율 4 에서도 2 화면 픽셀이다. 아래 끝 GUI y 132 는 단추가 가장
#          높이 오는 자리 (GUI 높이 240: 240/4 + 72) 라 단추와 겹치지 않는다.
#   가로   폭 DEATH_BAND_W_GUI (1536). 가운데에서 DEATH_BAND_FLAT (256) 까지 고르고, 끝 (768) 까지 smoothstep 으로 0. GUI 폭이
#          512 이하 (1280×720 GUI 3, 1920×1080 GUI 4) 면 화면 끝까지 고르게 덮고, GUI 배율 2·1 처럼 넓은 화면에서는 양 끝이
#          연기처럼 옅어진다 (네모 상자가 아니다).
#   조각   64 GUI 픽셀 (128 텍셀) 폭 24 조각: 가운데 8 조각은 같은 그림 (m), 양쪽 8 조각씩은 저마다 다르다 (l0..l7, r0..r7).
#          글꼴 그림 한 장은 클라이언트의 256×256 글꼴 판에 들어가야 한다. 띠 앞뒤의 빈칸 글자가 띠의 진행 폭을 지워 제목이
#          바닐라처럼 글자 폭으로 가운데에 놓인다.
# 같은 그림을 두 글꼴이 쓴다: 사망 화면 제목 (minecraft:default, 2배로 그려지므로 높이 36 글꼴 픽셀) 과 서서히 나타나는
# 사망 화면 문구 줄 (souls:death, 1배라 높이 72).
DEATH_BAND_TAG = palette.BAND_TAG   # 띠 그림의 RGB (0, 0, 2): 셰이더가 띠로 알아보는 표식. 팔레트 그림에는 없는 색 (artlint data)
DEATH_BAND_H_GUI = 72
DEATH_BAND_CORE = 13
DEATH_BAND_ALPHA = 0.86
DEATH_BAND_TEX = 2
DEATH_BAND_TILE_GUI = 64
DEATH_BAND_W_GUI = 1536
DEATH_BAND_FLAT = 256
DEATH_BAND_RAMP = 8                 # 한쪽 끝의 서로 다른 조각 수 ((768 - 256) / 64)
DEATH_BAND_TILES = DEATH_BAND_W_GUI // DEATH_BAND_TILE_GUI
# 조각 이름과 문자 (두 글꼴이 같은 번호를 쓴다): 시트 순서는 l0 (맨 왼쪽) .. l7, m, r7 .. r0 (맨 오른쪽)
DEATH_BAND = tuple([(f"death_band_l{i}", chr(0xE200 + i)) for i in range(DEATH_BAND_RAMP)]
                   + [("death_band_m", chr(0xE200 + DEATH_BAND_RAMP))]
                   + [(f"death_band_r{i}", chr(0xE200 + 2 * DEATH_BAND_RAMP - i)) for i in range(DEATH_BAND_RAMP - 1, -1, -1)])
DEATH_BAND_SPACES = ("death_band_pre", "\ue211"), ("death_band_post", "\ue212"), ("death_band_back", "\ue213")
# 사망 화면 제목 (2배): 띠 높이 36 글꼴 픽셀, 띠 위 = 줄 y 30 + 7 - 7 = 30 (GUI 60)
DEATH_BAND_ASCENT = 7

# 서서히 나타나는 YOU DIED (config.yml death.screen-fade, 5.6). 바닐라 사망 화면은 제목을 늘 한꺼번에 그리고 화면마다 시계가 없다.
# 그래서 이 판은 제목을 비우고 (gen_pack), 플러그인이 죽은 순간 사망 화면 문구 (deathScreenMessageOverride, 1배, GUI y 85,
# 제목처럼 사망 화면의 붉은 덧칠 위) 에 같은 띠와 같은 글자를 souls:death 글꼴로 보낸다. 글자색이 표식이고 죽은 게임 시각을 싣는다:
#   (DEATH_MARK_R, DEATH_MARK_G0 + t // 256, t % 256), 그림자는 ShadowColor (DEATH_MARK_SHADOW_R, ...) 로 같은 t.
#   t = 죽은 틱의 world.getGameTime() % 24000. 글꼴 셰이더가 GameTime (클라이언트 세계의 게임 시각 % 24000, 틱 사이까지 매끈)
#   과 견주어 띠는 DEATH_FADE_BAND, 글자는 DEATH_FADE_LETTERS 틱 사이에서 smoothstep 으로 나타나게 한다 (다크 소울처럼 어둠이 먼저,
#   글자가 그 속에서). 글자색은 사망 화면 제목과 같게 TEXT (뼈빛) 을 곱하고, 그림자는 제목 (2배) 의 그림자와 같은 자리 (1.5 GUI 픽셀
#   오른쪽 아래) 에 같은 먹빛. 글자는 souls:death 의 1배 글자 (높이 24, 그림 한 칸 = GUI 1 픽셀) 와 글자마다 빈칸을 더해 제목 판과
#   같은 크기·같은 사이로 놓는다 (가로 자리는 화면 폭의 홀짝에 따라 1 GUI 픽셀까지 다를 수 있다).
DEATH_FONT = NS + ":death"
DEATH_MARK_R, DEATH_MARK_SHADOW_R, DEATH_MARK_G0 = 254, 253, 144   # G = 144 + t // 256 (144..237): HUD 표식 (G 253) 과 겹치지 않는다
DEATH_FADE_BAND = (2.0, 18.0)       # 띠: 죽은 뒤 0.1 초에서 0.9 초 사이에 나타난다 (틱)
DEATH_FADE_LETTERS = (6.0, 26.0)    # 글자: 0.3 초에서 1.3 초 사이
DEATH_FADE_WAIT = 100.0             # 클라이언트 시계가 죽은 시각보다 이만큼 (틱) 넘게 앞이거나 뒤면 (시계가 튐, 아주 오래 죽어 있음)
                                    # 기다리지 않고 바로 보인다: YOU DIED 가 오래 가려지는 일이 없게
DEATH_FADE_LETTER_ASCENT = 8        # 1배 글자: 위 = 문구 줄 y 85 + 7 - 8 = 84 (제목 판과 같은 GUI y 84~108)
DEATH_FADE_BAND_ASCENT = 32         # 1배 띠: 위 = 85 + 7 - 32 = 60 (제목 판과 같은 GUI y 60~132)
DEATH_FADE_SPACES = tuple((f"fade_after_{n}", chr(0xE214 + i)) for i, (n, _) in enumerate(YOU_DIED_LETTERS))

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


# 칠하기 (2026-10-08 비평: 글자 속의 어두운 점과 오른쪽·아래의 어두운 가장자리가 지저분하고 "만든 티" 가 났다): 손으로 찍은 꼴
# (art/you_died.txt) 은 그대로 두고 색은 평평한 생피 하나 (YOU_DIED_FLAT), 획의 윗가장자리 (바로 위 칸이 비었다) 만 한 단 밝게
# (YOU_DIED_TOP). 알파는 늘 불투명 (섞인 가장자리 없음). 바닐라가 사망 화면 제목에 그리는 그림자 (글자 × 0.25, 2 GUI 픽셀
# 오른쪽 아래) 는 거의 검은 띠 위라 묻힌다.
YOU_DIED_FLAT, YOU_DIED_TOP = "gore2", "gore3"


def you_died_sheet():
    """(글자 그림 한 장, 칸 폭 텍셀, 칸 높이 텍셀). 칸 일곱 (Y O U D I E D), 칸 폭은 가장 넓은 글자, 왼쪽 맞춤."""
    grids = load_grids(os.path.join(ART, "you_died.txt"))
    cell_h = len(grids["y"])
    cell_w = max(len(grids[n][0]) for n, _ in YOU_DIED_LETTERS)
    sheet = Image.new("RGBA", (cell_w * len(YOU_DIED_LETTERS), cell_h), (0, 0, 0, 0))
    for i, (name, _) in enumerate(YOU_DIED_LETTERS):
        rows = grids[name]
        if len(rows) != cell_h:
            raise ValueError(f"you_died [{name}]: 높이 {len(rows)} (다른 글자는 {cell_h})")
        img = grid_image(rows, YOU_DIED_INK)
        px = img.load()
        for y in range(img.height):
            for x in range(img.width):
                if px[x, y][3]:
                    top = y == 0 or px[x, y - 1][3] == 0
                    px[x, y] = c(YOU_DIED_TOP if top else YOU_DIED_FLAT)
        sheet.alpha_composite(img, (i * cell_w, 0))
    return sheet, cell_w, cell_h


def death_title(glyphs, prefix="you_died_"):
    """deathScreen.title 에 넣을 문자열: Y O U / D I E D 를 빈칸 문자로 띄운다. 사망 화면 판은 그 앞에 검은 띠."""
    by = {g.name: g.char for g in glyphs}
    gap, word = by[prefix + "gap"], by[prefix + "word"]
    you = gap.join(by[prefix + n] for n in ("y", "o", "u"))
    died = gap.join(by[prefix + n] for n in ("d1", "i", "e", "d2"))
    band = ""
    if prefix == "you_died_" and DEATH_BAND[0][0] in by:
        band = band_string(by)
    return band + you + word + died


def band_tiles():
    """띠 조각 이름을 왼쪽부터 (DEATH_BAND_TILES 개): l0..l7, m × 8, r7..r0."""
    names = [n for n, _ in DEATH_BAND]
    ramp = DEATH_BAND_RAMP
    return names[:ramp] + [names[ramp]] * (DEATH_BAND_TILES - 2 * ramp) + names[ramp + 1:]


def band_string(by, prefix=""):
    """[앞 빈칸][조각 + 되돌림] × 24 [뒤 빈칸]: 진행 폭의 합이 0 (by: 이름 → 문자, prefix: souls:death 는 "fade_")."""
    back = by[prefix + DEATH_BAND_SPACES[2][0]]
    return (by[prefix + DEATH_BAND_SPACES[0][0]] + "".join(by[prefix + t] + back for t in band_tiles())
            + by[prefix + DEATH_BAND_SPACES[1][0]])


def death_fade_line(glyphs):
    """
    서서히 나타나는 판의 사망 화면 문구 한 줄 (souls:death 글꼴, 1배): 띠 + 글자마다 [글자][그 뒤 빈칸]. 빈칸은 제목 판 (2배) 과
    같은 자리가 되게 gen 때 셈했다 (build).
    """
    by = {g.name: g.char for g in glyphs if g.font == DEATH_FONT}
    out = band_string(by, "fade_")
    for (n, _), (sp, _) in zip(YOU_DIED_LETTERS, DEATH_FADE_SPACES):
        out += by["fade_you_died_" + n]
        if sp in by:
            out += by[sp]
    return out


def death_mark(t, shadow=False):
    """죽은 게임 시각 t (0..23999) 를 실은 표식 글자색 (r, g, b). 플러그인 DeathFlow 와 셰이더가 같은 식을 쓴다."""
    t = int(t) % 24000
    return (DEATH_MARK_SHADOW_R if shadow else DEATH_MARK_R, DEATH_MARK_G0 + t // 256, t % 256)


def band_alpha():
    """띠의 알파 (세로 텍셀 × 가로 GUI 반 픽셀 단위 전체 폭) 를 0..1 로. 가로·세로 프로필의 곱."""
    h = DEATH_BAND_H_GUI * DEATH_BAND_TEX
    w = DEATH_BAND_W_GUI * DEATH_BAND_TEX

    def smooth(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    yc = (np.arange(h) + 0.5) / DEATH_BAND_TEX - DEATH_BAND_H_GUI / 2
    v = 1.0 - smooth(DEATH_BAND_CORE, DEATH_BAND_H_GUI / 2, np.abs(yc))
    xc = (np.arange(w) + 0.5) / DEATH_BAND_TEX - DEATH_BAND_W_GUI / 2
    hz = 1.0 - smooth(DEATH_BAND_FLAT, DEATH_BAND_W_GUI / 2, np.abs(xc))
    return DEATH_BAND_ALPHA * v[:, None] * hz[None, :]


def death_band():
    """
    YOU DIED 뒤의 띠 조각 (DEATH_BAND 순서: l0..l7, m, r7..r0) 을 한 그림에. GUI 한 픽셀에 2 텍셀 (조각 128×144 텍셀 =
    GUI 64×72). RGB 는 모두 표식 DEATH_BAND_TAG (알파 0 인 곳까지), 알파는 band_alpha 를 8 비트로 반올림.
    """
    a = band_alpha()
    tw = DEATH_BAND_TILE_GUI * DEATH_BAND_TEX
    ramp = DEATH_BAND_RAMP
    cols = [a[:, i * tw:(i + 1) * tw] for i in range(ramp)]                        # l0..l7
    cols.append(a[:, ramp * tw:(ramp + 1) * tw])                                   # m (평평한 가운데 첫 조각)
    n = DEATH_BAND_TILES
    cols += [a[:, i * tw:(i + 1) * tw] for i in range(n - ramp, n)]                # r7..r0 (왼쪽부터)
    mid = a[:, (n // 2) * tw:(n // 2 + 1) * tw]
    assert np.allclose(cols[ramp], mid), "띠 가운데 조각이 고르지 않다 (DEATH_BAND_FLAT 이 조각 경계에 맞지 않는다)"
    al = np.clip(np.rint(np.concatenate(cols, axis=1) * 255), 0, 255).astype(np.uint8)
    rgba = np.zeros(al.shape + (4,), np.uint8)
    rgba[..., :3] = DEATH_BAND_TAG
    rgba[..., 3] = al
    return Image.fromarray(rgba, "RGBA")


def plugin_title(glyphs):
    """플러그인 화면 제목 한 줄 (souls:hud 글꼴)."""
    return death_title(glyphs, "you_died_title_")


# ─────────────────────────── 다크 소울 HUD (10.2, 2026-10-07 사용자 결정, 2026-10-08 고딕 촛불 시안 B) ───────────────────────────
#
# 왼쪽 위에 가는 가로 막대 셋 (체력 · 마나 · 스태미나), 오른쪽 아래에 소울 수 상자, 보스는 화면 아래 가운데에 이름 (왼쪽 맞춤) 과
# 넓은 체력 막대 + 그 밑 1 GUI 픽셀 자세 줄. 바닐라 하트·허기·방어·경험치 막대와 조준점은 그림을 투명하게 해서 숨기고 (gui_skin),
# 막대는 플러그인이 그림 글자로 그린다:
#   막대 셋   HUD 전용 보스 막대 (WHITE, 막대 그림 투명) 의 이름 줄. 첫 보스 막대의 이름 줄은 y 3 (12 - 9) 에 놓이고,
#             줄마다 ascent 로 내려 막대 셋을 쌓는다
#   소울 수   행동 막대 (줄 위 = 화면 아래 - 72). 음수 ascent 로 화면 아래 가장자리 가까이 내린다
#   보스      보스마다 보스 막대 하나 (RED, 막대 그림 투명. HUD 막대 다음에 띄우므로 둘째 줄부터). 이름 줄 하나에
#             [이름 사본 (안 보임)][마구리][막대][마구리][자세 줄][이름][빈칸] 을 쓴다 (boss_bars). 바닐라는 이름 줄을 글 폭의
#             반만큼 왼쪽에서 시작하는데 이름 폭은 언어·글꼴마다 달라 서버가 모른다. 같은 이름을 두 번 쓰면 둘째 이름은 폭과
#             상관없이 늘 가운데 - BOSS_W/2 에서 시작하고, 막대는 첫 사본 뒤 (= 늘 가운데) 에서 그린다. 첫 사본은 셰이더가
#             지운다 (MARK_HIDDEN). 마구리는 표식 MARK_BOSS_CAP: 셰이더가 늘이지 않고 늘인 막대 끝을 따라 통째로 옮긴다
# 가로 자리: 보스 막대 이름과 행동 막대는 화면 가운데에 놓인다. 플러그인은 글 전체의 진행 폭이 0 이 되게 (빈칸 글자로
# 되돌아온다) 만들어 글이 늘 가운데 (GUI 폭 / 2, 버림) 에서 시작하게 하고, 그 자리에서 HUD_KL 만큼 왼쪽 (막대) 또는
# HUD_KR 만큼 오른쪽 (소울 상자 오른쪽 끝) 에 그린다. 글꼴 셰이더 (rendertype_text.vsh) 가 표식 색의 글자만 옮긴다 (MARK_*):
# 막대 셋은 왼쪽 위에서 화면 폭의 4.5% · 높이의 5% 안쪽, 소울 상자는 오른쪽 아래에서 4% 안쪽, 보스는 화면 아래 - BOSS_UP 줄로
# 내리고 막대를 화면 폭의 약 45% 로 늘인다 (1 ~ 2.5 배, 0.25 마디). 셰이더가 없으면 1280×720 GUI 배율 3 에서 가장자리 8 자리.
#
# 그림 (2026-10-08 사용자: 고딕 촛불 시안 B): GUI 한 픽셀에 2 텍셀 (S, 숫자는 4 텍셀) 이고 글꼴 셰이더가 넓이 평균으로 읽는다.
#   막대     위에서 비친 단조 쇠 테 (윗날에 청동빛 반 픽셀). 몸은 한 색이 아니라 거무칙칙한 "검은 심" (2026-10-08 사용자 결정,
#            bar_styles.py): 유리관 속 탁한 물처럼 거의 검은 심에 위에서 둘째 줄의 흐린 빛과 맨 아래의 비친 빛 한 줄씩 (체력 진홍,
#            마나 깊고 바랜 쪽빛 (palette 의 mana, 마나 막대 전용 예외), 스태미나 누른 풀·이끼). 잃은 체력은 같은 관을 탁한
#            황토로, 빈 몫은 빈 유리관 (먹, 빛 줄 자리에 어두운 빛 한 줄, 그을음 입술).
#   마구리   (2026-10-08 사용자: 초안 모양이 더 낫다) 왼쪽은 세 잎 단조 장식 (둥근 꼭지의 기둥, 기둥에 묶인 고리, 왼쪽으로 뻗은
#            속 빈 마름모 창끝, 꼭지에서 고리로 말린 덩굴 둘), 오른쪽은 기둥과 작은 마름모 창끝. 막대 위·아래로 3 GUI 픽셀씩
#            나와 막대 셋의 왼쪽 장식이 한 기둥으로 쌓인다 (서로 1 GUI 픽셀 겹친다).
#   소울 수  검은 옻칠 상자, 윗날에 촛불 기운 (가운데가 따뜻하다), 금실 윗줄과 양 끝 마름모, 위 가운데 작은 꽃 장식. 넋 표식은
#            위로 꼬리가 선 옅은 뼈빛 불꽃, 숫자는 가라몽 라이닝 숫자 (고정 폭, fonts.digit_role).
#   보스     체력 막대와 같은 말씨에 더 큰 마구리 (왼쪽은 고리와 덩굴, 오른쪽은 창끝), 그 밑 1 GUI 픽셀 자세 줄 (흐린 금 한 줄과
#            그을음 그늘, 빈 길은 흑갈과 옅은 먹). 이름은 제목 글꼴 (YAML 의 꼴 태그).

S = 2                       # 텍셀 / GUI 픽셀 (막대·마구리·상자·띠)
HUD_MARGIN = 8              # 셰이더 없이: 화면 가장자리와 HUD 사이 (GUI 픽셀, 폭 427 에서)
HUD_KL = 205                # 셰이더 없이: 막대 왼쪽 끝 = 화면 가운데 - 205 (폭 427 에서 8)
HUD_KR = 206                # 셰이더 없이: 소울 상자 오른쪽 끝 = 화면 가운데 + 206 (폭 427 에서 419)
HUD_INSET = (0.045, 0.05)   # 셰이더: 막대 셋의 왼쪽 위 = (GUI 폭 × 0.045, GUI 높이 × 0.05) (반올림한 GUI 픽셀)
SOUL_INSET_FR = (0.04, 0.04)  # 셰이더: 소울 상자의 오른쪽 아래 = (GUI 폭 - 폭 × 0.04, GUI 높이 - 높이 × 0.04)
MARK_LEFT = (254, 253, 1)   # 이 색의 글은 셰이더가 왼쪽 위로 (막대 셋)
MARK_RIGHT = (254, 253, 2)  # 이 색의 글은 오른쪽 아래로 (소울 상자)
MARK_BOSS = (254, 253, 3)   # 보스 막대 그림 글자: 아래 가운데로 내리고 가운데를 축으로 가로로 늘인다
MARK_BOSS_NAME = (254, 253, 4)    # 보스 이름: 아래로 내리고 늘인 막대의 왼쪽 끝에 맞춘다. 셰이더가 글자색을 BOSS_NAME_INK 로
MARK_BOSS_SHADOW = (254, 253, 5)  # 보스 이름의 그림자 (ShadowColor 로 준다): 이름과 같이 옮기고 BOSS_SHADOW_INK 로
MARK_HIDDEN = (254, 253, 6)       # 보스 이름의 앞 사본: 셰이더가 지운다 (알파 0)
MARK_BOSS_CAP = (254, 253, 7)     # 보스 막대 마구리: 아래로 내리고 늘이지 않은 채 늘인 막대 끝을 따라 옮긴다
BOSS_NAME_INK = "parch3"          # 보스 이름 글자색 (밝은 베이지)
BOSS_SHADOW_INK = ("ink0", 200)   # 보스 이름 그림자
BOSS_LINE_TOP = 3           # 첫 보스 막대 이름 줄의 위 (GUI y). 보스 막대마다 19 아래
BOSS_PITCH = 19             # 보스 막대 줄 사이 (바닐라 BossHealthOverlay: 10 + 9)
BOSS_UP = 64                # 셰이더: 보스 이름 줄의 위 = GUI 높이 - 64 (단축 슬롯과 소울 상자 위)
BOSS_STACK = 24             # 보스가 둘 이상이면 위로 이만큼씩 쌓는다
BOSS_W = 200                # 보스 체력 막대의 바탕 길이 (마구리 안, 셰이더가 늘인다)
BOSS_FILL = 0.45            # 셰이더: 늘인 보스 막대 ≈ 화면 폭 × 0.45
ACTION_LINE_UP = 72         # 행동 막대 줄의 위 = 화면 아래 - 72
HUD_TOP = 8                 # 셰이더 없이: 막대 셋의 맨 위 (GUI y)
RUN_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)   # 막대 조각 폭 (조합해 아무 길이나 만든다)

# 막대 셋의 맨 위에서의 자리 (GUI). 몸의 색 짜임 (채움·잃은 몫·빈 몫·자세 줄) 은 bar_styles.py
TOP = {"hp": 0, "fp": 11, "st": 21}
IRON = ["ink0", "rust1", "bronze2", "parch3"]    # 단조 쇠: 아랫날 → 몸 → 윗날 밑 → 윗날 (촛불이 위에서)
GOLD = ["rust1", "bronze3", "parch2", "glim0"]
EXT = 6                     # 막대 셋의 마구리가 막대 위·아래로 나오는 텍셀 (3 GUI 픽셀)
BOSS_EXT = 4                # 보스 막대 마구리 (2 GUI 픽셀: 이름 줄 위 -1 .. +17 안, 셰이더가 꼭짓점 y 로 보스 줄을 고른다)

# 소울 상자 (행동 막대): GUI 72×15, 화면 아래에서 8 위에 끝난다 (셰이더 없이). 표식은 상자 왼쪽 안 5, 숫자는 오른쪽 안 6
SOUL_BOX_W, SOUL_BOX_H, SOUL_BOX_BOTTOM = 72, 15, 8
SOUL_INSET = 2
DIGIT_INK = "bone2"
# 보스 막대 (보스 이름 줄 안, 줄 위에서 GUI): 이름 0..7, 체력 막대 맨 위 9, 마구리 7..17, 자세 줄 16 (1 GUI 픽셀)
BOSS_BAR_ROW = 9


def bar_rows(bar):
    """막대 한 칸의 텍셀 줄 수 (윗날·테·몸·테·그늘)."""
    return len(bar_styles.column(bar, "fill"))


def cap_left(hb, big=False, ext=EXT):
    """
    왼쪽 마구리 (텍셀): 높이 hb + 2 ext, 폭 26 (보스 30). 막대 끝의 세운 기둥 (위·아래 끝에 둥근 꼭지), 기둥에 붙은 단조 고리,
    고리에서 왼쪽으로 뻗은 마름모 창끝, 기둥 꼭지에서 고리로 말려 내려오는 덩굴 둘 (세 잎 장식). 획은 2 텍셀 (1 GUI 픽셀) 이상이라
    윗날 (촛불 빛) 과 아랫날 (그늘) 이 갈린다. 막대 셋의 마구리는 위·아래로 3 GUI 픽셀씩 나와 셋이 한 장식 기둥으로 쌓인다.
    """
    w = 30 if big else 26
    h = hb + 2 * ext
    cy = h / 2.0
    m = Mask(w, h)
    px = w - 3.0
    m.rect(w - 5, 2, w - 1, h - 2)                  # 기둥 4 텍셀
    m.disc(px, 2.4, 2.4)
    m.disc(px, h - 2.4, 2.4)
    rc = w - 13.0                                  # 고리 가운데
    ro = 5.2 if not big else 5.8
    m.ring(rc, cy, ro - 2.2, ro)
    m.rect(rc + ro - 1, cy - 1.2, w - 4, cy + 1.2)  # 고리 → 기둥
    tip = 0.6
    m.poly([(tip, cy), (rc - ro - 3.6, cy - 3.4), (rc - ro + 1.0, cy), (rc - ro - 3.6, cy + 3.4)])
    m.rect(rc - ro - 1.5, cy - 1.0, rc - ro + 1.0, cy + 1.0)
    # 덩굴: 기둥 꼭지에서 왼쪽으로 휘어 고리 위·아래에 닿는 반원
    rr = (h / 2.0 - ro) / 2.0 + 1.6
    m.ring(px - rr - 0.6, 2.4 + rr, rr - 2.0, rr, 180, 360)
    m.ring(px - rr - 0.6, h - 2.4 - rr, rr - 2.0, rr, 0, 180)
    hole = Mask(w, h).poly([(tip + 4.2, cy), (rc - ro - 3.6, cy - 1.4), (rc - ro - 1.2, cy), (rc - ro - 3.6, cy + 1.4)])
    return uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), IRON, light_rows=1, dark_rows=1)


def cap_right(hb, big=False, ext=EXT):
    """오른쪽 마구리: 둥근 꼭지의 기둥과 작은 마름모 창끝 (폭 14, 보스 16)."""
    w = 16 if big else 14
    h = hb + 2 * ext
    cy = h / 2.0
    m = Mask(w, h)
    m.rect(0, 2, 4, h - 2)
    m.disc(2.0, 2.4, 2.4)
    m.disc(2.0, h - 2.4, 2.4)
    m.rect(3, cy - 1.0, 7, cy + 1.0)
    m.poly([(5.5, cy), (9.5, cy - 3.2), (w - 0.4, cy), (9.5, cy + 3.2)])
    hole = Mask(w, h).poly([(8.2, cy), (9.8, cy - 1.1), (w - 3.4, cy), (9.8, cy + 1.1)])
    return uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), IRON)


def caps_sheet(hb, big=False, ext=EXT):
    """마구리 둘을 한 그림에 (칸 폭 같게): [왼쪽][오른쪽]. 돌려주는 값: 그림."""
    left, right = cap_left(hb, big, ext), cap_right(hb, big, ext)
    cw = max(left.w, right.w)
    sheet = Img(cw * 2, left.h)
    sheet.over(left, 0, 0)
    sheet.over(right, cw, 0)
    return sheet.image()


def soul_box():
    """소울 상자 (GUI SOUL_BOX_W × SOUL_BOX_H): 옻칠 몸, 윗날 촛불 기운, 금실 윗줄과 녹슨 아랫줄, 양 끝 마름모, 위 가운데 꽃 장식."""
    W, H = SOUL_BOX_W * S, SOUL_BOX_H * S
    img = Img(W, H)
    cx = W / 2.0
    for y in range(3, H - 3):
        for x in range(W):
            d = min(x, W - 1 - x)
            k = 1.0 if d >= 8 else (d + 1) / 9.0
            dx = abs(x + 0.5 - cx) / cx
            name = "ink0"
            if y == 3 and dx < 0.75:
                name = "bronze1" if dx < 0.35 else "bronze0"
            elif y == 4 and dx < 0.6:
                name = "bronze0" if dx < 0.3 else "rust0"
            elif y == 5 and dx < 0.45:
                name = "rust0"
            img.put(x, y, name, 0.80 * k)
    for x in range(W):
        d = min(x, W - 1 - x)
        k = 1.0 if d >= 10 else (d + 1) / 11.0
        dx = abs(x + 0.5 - cx) / cx
        img.put(x, 2, "parch2" if dx < 0.3 else ("parch1" if dx < 0.65 else "parch0"), 0.95 * k)
        img.put(x, H - 3, "rust1", 0.85 * k)
        img.put(x, H - 2, "ink0", 0.35 * k)
    orn = Mask(W, H)
    for ex in (11.0, W - 11.0):
        orn.poly([(ex - 2.6, 2.5), (ex, 0.2), (ex + 2.6, 2.5), (ex, 4.8)])
    orn.poly([(cx - 4.5, 2.6), (cx, -0.5), (cx + 4.5, 2.6), (cx, 5.6)])
    orn.disc(cx - 6.2, 2.5, 1.1)
    orn.disc(cx + 6.2, 2.5, 1.1)
    hole = Mask(W, H).poly([(cx - 1.6, 2.6), (cx, 1.2), (cx + 1.6, 2.6), (cx, 4.0)])
    img.over(uidraw.lit(np.clip(orn.cov() - hole.cov(), 0, 1), GOLD))
    return img.image()


def soul_mark():
    """
    넋 표식 (빛 허용 그림 soul_mark): 둥근 몸에서 꼬리가 왼쪽 위로 휘며 가늘어지는 넋불, 옅은 뼈빛 테 (위에서 빛), 속은 밝은
    뼈빛, 한가운데 희미한 불씨. 22×22 텍셀 (11 GUI).
    """
    W = H = 22
    outer = Mask(W, H)
    outer.ellipse(11.5, 15.4, 5.2, 5.0)
    for cx, cy, r in ((10.2, 11.2, 3.9), (9.2, 7.6, 2.9), (9.4, 4.6, 2.0), (10.8, 2.4, 1.3), (12.6, 1.4, 0.8)):
        outer.disc(cx, cy, r)
    inner = Mask(W, H)
    inner.ellipse(11.6, 15.8, 3.2, 3.0)
    inner.disc(10.6, 12.0, 2.0)
    inner.disc(10.0, 9.0, 1.2)
    core = Mask(W, H).ellipse(11.7, 16.4, 1.5, 1.6)
    img = Img(W, H)
    img.over(uidraw.lit(outer.cov(), ["bone0", "bone0", "bone1", "bone2"]))
    img.fill(inner.cov(), "bone2", 0.95)
    img.fill(core.cov(), "bone3", 1.0)
    img.fill(Mask(W, H).disc(11.7, 16.8, 0.8).cov(), "ember3", 0.9)
    return img.image()


def digits(role, k=4, ink=DIGIT_INK):
    """
    소울 수 숫자 열 장 (fonts.digit_role 의 가라몽 라이닝 숫자, k 텍셀/GUI). 칸 폭 같게, 모든 숫자의 진행 폭이 같도록 같은 열에
    알파 1 점. 색은 팔레트 한 색, 덮임은 알파. 돌려주는 값: (그림, 바탕선 위 GUI 줄 수).
    """
    gl = {str(d): role.glyphs[str(d)] for d in range(10)}
    up = max(g["top"] for g in gl.values())
    down = max(g["a"].shape[0] - g["top"] for g in gl.values())
    wid = max(g["a"].shape[1] for g in gl.values())
    asc = int(np.ceil((up + 1) / k))
    desc = int(np.ceil((down + 1) / k))
    ch = (asc + desc) * k
    adv = int(np.ceil((wid + 1 + 3) / k)) + 1           # 숫자 폭 + 사이 1 GUI 픽셀
    cw = adv * k
    arr = np.zeros((ch, cw * 10, 4), np.uint8)
    r, g, b, _ = c(ink)
    for d in range(10):
        a = gl[str(d)]["a"]
        x0 = d * cw + (cw - k - a.shape[1]) // 2
        y0 = asc * k - gl[str(d)]["top"]
        al = np.clip(np.rint(a * 255), 0, 255).astype(np.uint8)
        sub = arr[y0:y0 + a.shape[0], x0:x0 + a.shape[1]]
        sub[..., 0], sub[..., 1], sub[..., 2] = r, g, b
        sub[..., 3] = np.maximum(sub[..., 3], al)
        sent = d * cw + (adv - 1) * k - 1
        if arr[ch - 1, sent, 3] == 0:
            arr[ch - 1, sent] = (r, g, b, 1)
    arr[..., 3][(arr[..., 3] >= 250) & (arr[..., 3] <= 252)] = 249
    return Image.fromarray(arr, "RGBA"), asc


HUD_SHADER = """#version 330

#moj_import <minecraft:fog.glsl>
#moj_import <minecraft:dynamictransforms.glsl>
#moj_import <minecraft:projection.glsl>

in vec3 Position;
in vec4 Color;
in vec2 UV0;
in ivec2 UV2;

uniform sampler2D Sampler2;

out float sphericalVertexDistance;
out float cylindricalVertexDistance;
out vec4 vertexColor;
out vec2 texCoord0;

// Square Soul HUD (pack/hud.py). Vanilla 1.21.11 rendertype_text.vsh plus one block:
// GUI text (orthographic projection) whose colour is a HUD marker {r} {g} b is moved (whole GUI pixels):
//   b {b1}: HUD bars (boss bar name, drawn from the screen centre minus {kl}, top at y {top0})
//          -> left edge + {ix} x width, top edge + {iy} x height
//   b {b2}: souls box (action bar, right end at the screen centre plus {kr}, bottom {bot0} above the screen bottom)
//          -> right edge - {sx} x width, bottom edge - {sy} x height
//   b {b3} / {b4} / {b5} / {b7}: boss bar glyphs / boss name / boss name shadow / boss bar end caps on boss bar line k
//          (top 3 + 19 k) -> line top at the screen bottom - {up} (stacked {stack} up per extra boss); the bar glyphs are
//          stretched around the screen centre to about {fill} x width ({bw} wide, 1 to 2.5 in quarter steps),
//          the caps move rigidly with the stretched bar ends, the name moves with the bar's left end.
//          Name -> beige, shadow -> dark
//   b {b6}: hidden (alpha 0): the boss name copy that only cancels the name width
// Other marker glyphs keep their own colours (vertex colour replaced by white).
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
    vertexColor = Color * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;

    ivec3 mark = ivec3(Color.rgb * 255.0 + 0.5);
    if (mark.r == {r} && mark.g == {g} && mark.b >= {b1} && mark.b <= {b7} && ProjMat[3][3] == 1.0) {{
        float guiWidth = ceil(2.0 / ProjMat[0][0] - 0.01);
        float guiHeight = ceil(-2.0 / ProjMat[1][1] - 0.01);
        float centre = floor(guiWidth * 0.5);
        vec2 at = (ModelViewMat * vec4(Position, 1.0)).xy;
        vec2 shift = vec2(0.0);
        vec4 ink = vec4(1.0, 1.0, 1.0, Color.a);
        if (mark.b == {b1}) {{
            shift.x = floor(guiWidth * {ix} + 0.5) - (centre - {kl}.0);
            shift.y = floor(guiHeight * {iy} + 0.5) - {top0}.0;
        }} else if (mark.b == {b2}) {{
            shift.x = (guiWidth - floor(guiWidth * {sx} + 0.5)) - (centre + {kr}.0);
            shift.y = {bot0}.0 - floor(guiHeight * {sy} + 0.5);
        }} else if (mark.b == {b6}) {{
            ink.a = 0.0;
        }} else {{
            float line = floor((at.y - 2.0) / 19.0);
            float slot = max(line, 1.0) - 1.0;
            shift.y = (guiHeight - {up}.0 - slot * {stack}.0) - (3.0 + 19.0 * line);
            float s = clamp(floor(guiWidth * {fill} / {bw}.0 * 4.0 + 0.5) / 4.0, 1.0, 2.5);
            if (mark.b == {b3}) {{
                shift.x = (at.x - centre) * (s - 1.0);
            }} else if (mark.b == {b7}) {{
                shift.x = sign(at.x - centre) * floor((s - 1.0) * {half}.0 + 0.5);
            }} else {{
                shift.x = -floor((s - 1.0) * {bw}.0 * 0.5 + 0.5);
                ink = mark.b == {b4} ? vec4({nr}, {ng}, {nb}, Color.a) : vec4({hr}, {hg}, {hb}, Color.a * {ha});
            }}
        }}
        gl_Position.x += shift.x * ProjMat[0][0];
        gl_Position.y += shift.y * ProjMat[1][1];
        vertexColor = ink * texelFetch(Sampler2, UV2 / 16, 0);
    }}
}}
"""


def _f(v):
    return f"{v:.4f}"


def hud_shader():
    """HUD 덩이를 더한 rendertype_text.vsh (shaders.py 가 GUI 글자 덩이를 더해 쓴다)."""
    n, h = c(BOSS_NAME_INK), c(BOSS_SHADOW_INK[0])
    return HUD_SHADER.format(r=MARK_LEFT[0], g=MARK_LEFT[1], b1=MARK_LEFT[2], b2=MARK_RIGHT[2], b3=MARK_BOSS[2],
                             b4=MARK_BOSS_NAME[2], b5=MARK_BOSS_SHADOW[2], b6=MARK_HIDDEN[2], b7=MARK_BOSS_CAP[2],
                             kl=HUD_KL, kr=HUD_KR, top0=HUD_TOP, bot0=SOUL_BOX_BOTTOM,
                             ix=_f(HUD_INSET[0]), iy=_f(HUD_INSET[1]), sx=_f(SOUL_INSET_FR[0]), sy=_f(SOUL_INSET_FR[1]),
                             up=BOSS_UP, stack=BOSS_STACK, fill=_f(BOSS_FILL), bw=BOSS_W, half=BOSS_W // 2,
                             nr=_f(n[0] / 255), ng=_f(n[1] / 255), nb=_f(n[2] / 255),
                             hr=_f(h[0] / 255), hg=_f(h[1] / 255), hb=_f(h[2] / 255), ha=_f(BOSS_SHADOW_INK[1] / 255))


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def layout():
    """플러그인이 읽는 자리 값 (glyphs.yml 의 layout). 셰이더와 같은 값이어야 한다."""
    return {"margin": HUD_MARGIN, "left": HUD_KL, "right": HUD_KR,
            "mark_left": _hex(MARK_LEFT), "mark_right": _hex(MARK_RIGHT),
            "mark_boss": _hex(MARK_BOSS), "mark_boss_name": _hex(MARK_BOSS_NAME),
            "mark_boss_shadow": _hex(MARK_BOSS_SHADOW), "mark_hidden": _hex(MARK_HIDDEN),
            "mark_boss_cap": _hex(MARK_BOSS_CAP),
            "boss_width": BOSS_W, "soul_box": SOUL_BOX_W, "soul_inset": SOUL_INSET}


def hud_glyphs(out, code, digit_role):
    """
    다크 소울 HUD 그림 글자 (souls:hud). (공급자 목록, Glyph 목록, 다음 문자 번호). 그림은 assets/souls/textures/font/.
    이름: hud_<막대>_<fill|empty|trail>_<폭>, hud_<막대>_cap_l / _cap_r, hud_soulbox, soul_mark, hud_digit_<0..9>,
    boss_hp_<fill|trail|empty>_<폭>, boss_post_<fill|empty>_<폭>, boss_cap_l / _cap_r.
    """
    providers, glyphs = [], []

    def add(fname, img, ascent, names, scale=1.0 / S):
        nonlocal code
        save(img, sprite_path(out, NS, "font", fname + ".png"))
        cw = img.width // len(names)
        chars = ""
        for i, nm in enumerate(names):
            ch = chr(code)
            code += 1
            chars += ch
            glyphs.append(Glyph(nm, ch, glyph_advance(img, i * cw, cw, img.height, scale), HUD_FONT, "bitmap"))
        h = img.height * scale
        assert abs(h - round(h)) < 1e-6, f"{fname}: 높이가 GUI 픽셀 정수가 아니다 ({img.height} 텍셀)"
        providers.append({"type": "bitmap", "file": f"{NS}:font/{fname}.png", "height": int(round(h)),
                          "ascent": ascent, "chars": [chars]})

    def asc_hud(top_gui):
        return BOSS_LINE_TOP + 7 - top_gui

    for bar in ("hp", "fp", "st"):
        top = HUD_TOP + TOP[bar]
        kinds = ("fill", "trail", "empty") if bar == "hp" else ("fill", "empty")
        for kind in kinds:
            add(f"hud_{bar}_{kind}", bar_styles.run_sheet(bar_styles.column(bar, kind)), asc_hud(top),
                [f"hud_{bar}_{kind}_{n}" for n in RUN_STEPS])
        add(f"hud_{bar}_cap", caps_sheet(bar_rows(bar)), asc_hud(top - EXT // S), [f"hud_{bar}_cap_l", f"hud_{bar}_cap_r"])

    box_top = SOUL_BOX_BOTTOM + SOUL_BOX_H
    add("hud_soulbox", soul_box(), box_top - (ACTION_LINE_UP - 7), ["hud_soulbox"])
    add("soul_mark", soul_mark(), (box_top - 2) - (ACTION_LINE_UP - 7), ["soul_mark"])
    dimg, dasc = digits(digit_role)
    base_from_bottom = SOUL_BOX_BOTTOM + 4                     # 숫자 바탕선: 상자 아래에서 4 위
    add("hud_digits", dimg, (base_from_bottom + dasc) - (ACTION_LINE_UP - 7), [f"hud_digit_{d}" for d in range(10)],
        scale=1.0 / 4)

    # 보스 막대 (보스 이름 줄 안): 체력 (윗날·테·몸 여덟·테·그늘), 자세 줄 (막대 밑 1 GUI 띄고 1 GUI 픽셀), 마구리.
    # 그림은 모두 막대와 같은 위에서 (자세 줄 그림은 16 텍셀 = GUI 8: 이름 줄 위 +17 을 넘지 않는다)
    for kind in ("fill", "trail", "empty"):
        add(f"hud_boss_hp_{kind}", bar_styles.run_sheet(bar_styles.column("boss", kind)), 7 - BOSS_BAR_ROW,
            [f"boss_hp_{kind}_{n}" for n in RUN_STEPS])
    for kind in ("fill", "empty"):
        add(f"hud_boss_post_{kind}", bar_styles.run_sheet(bar_styles.column("boss", "post_" + kind)), 7 - BOSS_BAR_ROW,
            [f"boss_post_{kind}_{n}" for n in RUN_STEPS])
    # 보스 마구리: 큰 고리·덩굴 (왼쪽, 30 텍셀) 과 창끝 (오른쪽), 위·아래 2 GUI 픽셀만
    add("hud_boss_cap", caps_sheet(bar_rows("boss"), big=True, ext=BOSS_EXT), 7 - (BOSS_BAR_ROW - BOSS_EXT // S),
        ["boss_cap_l", "boss_cap_r"])
    return providers, glyphs, code


# ─────────────────────────── HUD 짜기 (플러그인 hud/Hud 와 같은 차례) 와 미리보기 ───────────────────────────

PREVIEW_T = 4       # 미리보기 텍셀 / GUI 픽셀


class _Line:
    """플러그인 Hud.Line 과 같은 셈: 그림 글자는 폭 + 1 을 나아가고 1 을 되돌린다."""

    def __init__(self, cells):
        self.cells, self.pen, self.items = cells, 0, []

    def move(self, d):
        self.pen += d

    def glyph(self, name):
        cell, asc, w = self.cells[name]
        self.items.append((self.pen, asc, cell))
        self.pen += w - 1

    def runs(self, prefix, n):
        for s in reversed(RUN_STEPS):
            while n >= s:
                self.glyph(prefix + str(s))
                n -= s


def bar_line(cells, lengths):
    """막대 셋 (플러그인 Hud.bars): lengths = {막대: (길이, 채움, 잃은 몫)}."""
    ln = _Line(cells)
    ln.move(-HUD_KL)
    x0 = ln.pen
    for bar, (length, fill, trail) in lengths.items():
        ln.glyph(f"hud_{bar}_cap_l")
        ln.runs(f"hud_{bar}_fill_", fill)
        ln.runs(f"hud_{bar}_trail_", trail)
        ln.runs(f"hud_{bar}_empty_", length - fill - trail)
        ln.glyph(f"hud_{bar}_cap_r")
        ln.move(x0 - ln.pen)
    return ln


def souls_line(cells, n):
    """소울 상자 (플러그인 Hud.soulBox)."""
    ln = _Line(cells)
    d = str(max(0, int(n)))
    dw = cells["hud_digit_0"][2] - 1
    ln.move(HUD_KR - SOUL_BOX_W)
    x0 = ln.pen
    ln.glyph("hud_soulbox")
    ln.move(x0 + 5 - ln.pen)
    ln.glyph("soul_mark")
    ln.move(x0 + SOUL_BOX_W - 6 - dw * len(d) - ln.pen)
    for ch in d:
        ln.glyph("hud_digit_" + ch)
    return ln


def boss_line(cells, fill, trail, post, w=BOSS_W):
    """보스 막대 (플러그인 Hud.bossLine): 마구리 [표식 7], 체력, 마구리, 자세. 돌려주는 값: (막대 줄, 마구리 줄)."""
    half = w // 2
    cap_w = cells["boss_cap_l"][2] - 1
    caps, bar = _Line(cells), _Line(cells)
    caps.move(-half - cap_w)
    caps.glyph("boss_cap_l")
    bar.move(caps.pen)
    bar.runs("boss_hp_fill_", fill)
    bar.runs("boss_hp_trail_", trail)
    bar.runs("boss_hp_empty_", w - fill - trail)
    caps.move(bar.pen - caps.pen)
    caps.glyph("boss_cap_r")
    bar.move(-half - bar.pen)
    bar.runs("boss_post_fill_", post)
    bar.runs("boss_post_empty_", w - post)
    return bar, caps


def preview_cells(out, providers, glyphs):
    """그림 글자 이름 → (PREVIEW_T 텍셀/GUI 칸 그림, ascent, 진행 폭)."""
    adv = {g.name: g.width for g in glyphs}
    by_char = {g.char: g.name for g in glyphs if g.font == HUD_FONT}
    cells = {}
    for p in providers:
        img = Image.open(os.path.join(out, "assets", NS, "textures", p["file"].split(":", 1)[1])).convert("RGBA")
        row = p["chars"][0]
        cw = img.width // len(row)
        k = img.height // p["height"]
        for i, ch in enumerate(row):
            cell = img.crop((i * cw, 0, (i + 1) * cw, img.height))
            if k != PREVIEW_T:
                cell = cell.resize((cell.width * PREVIEW_T // k, cell.height * PREVIEW_T // k), Image.NEAREST)
            cells[by_char[ch]] = (cell, p["ascent"], adv[by_char[ch]])
    return cells


def _compose(W, H, layers):
    """layers: [(_Line, 줄 위 GUI, (dx, dy), 늘림 (가운데 축))] → PREVIEW_T 텍셀 캔버스 (RGBA float, 곱하지 않은 알파)."""
    T = PREVIEW_T
    cv = np.zeros((H * T, W * T, 4), np.float32)
    cx = W // 2
    for line, top, (dx, dy), st in layers:
        for pen, asc, cell in line.items:
            a = np.asarray(cell).astype(np.float32) / 255.0
            x = (cx + pen + dx) * T
            y = (top + 7 - asc + dy) * T
            if st is not None and st != 1.0:
                x = int(round(cx * T + pen * T * st)) + dx * T
                a = np.asarray(cell.resize((max(1, int(round(cell.width * st))), cell.height), Image.NEAREST)).astype(
                    np.float32) / 255.0
            h, w = a.shape[:2]
            ys, xs = max(0, -y), max(0, -x)
            y0, x0 = y + ys, x + xs
            y1, x1 = min(H * T, y + h), min(W * T, x + w)
            if y1 <= y0 or x1 <= x0:
                continue
            src = a[ys:ys + (y1 - y0), xs:xs + (x1 - x0)]
            dst = cv[y0:y1, x0:x1]
            sa = src[..., 3:4]
            da = dst[..., 3:4]
            oa = sa + da * (1 - sa)
            dst[..., :3] = np.where(oa > 0, (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6), 0)
            dst[..., 3:4] = oa
    return cv


def _to_screen(cv, G, bg):
    """PREVIEW_T 텍셀 → 배율 G 화면 픽셀 (넓이 평균, 글꼴 셰이더와 같은 읽기) 을 배경 bg (Image, 화면 크기) 위에."""
    T = PREVIEW_T
    h, w = cv.shape[:2]
    prem = np.concatenate([cv[..., :3] * cv[..., 3:4], cv[..., 3:4]], -1)
    up = np.repeat(np.repeat(prem, G, 0), G, 1)
    H2, W2 = h * G // T, w * G // T
    small = up[:H2 * T, :W2 * T].reshape(H2, T, W2, T, 4).mean(axis=(1, 3))
    base = np.asarray(bg.convert("RGB")).astype(np.float32)[:H2, :W2] / 255.0
    out = base * (1 - small[..., 3:4]) + small[..., :3]
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8), "RGB")


def shader_shift(kind, W, H, line=0):
    """셰이더가 옮기는 몫 (미리보기용, HUD_SHADER 와 같은 셈): (dx, dy, 늘림)."""
    import math
    centre = W // 2
    if kind == "left":
        return math.floor(W * HUD_INSET[0] + 0.5) - (centre - HUD_KL), math.floor(H * HUD_INSET[1] + 0.5) - HUD_TOP, 1.0
    if kind == "right":
        return (W - math.floor(W * SOUL_INSET_FR[0] + 0.5)) - (centre + HUD_KR), SOUL_BOX_BOTTOM - math.floor(H * SOUL_INSET_FR[1] + 0.5), 1.0
    s = min(2.5, max(1.0, math.floor(W * BOSS_FILL / BOSS_W * 4 + 0.5) / 4))
    slot = max(line, 1) - 1
    return 0, (H - BOSS_UP - slot * BOSS_STACK) - (BOSS_LINE_TOP + BOSS_PITCH * line), s


def preview_hud(out, path, glyphs, providers, gui=3, size=(427, 240)):
    """
    HUD 미리보기 (pack/preview/hud.png): 저녁 화면 위에 플러그인과 같은 차례로 짠 막대 셋·소울 상자·보스 막대 네 장면 (가득, 맞은
    뒤 잃은 몫과 보스 막대, 달려 스태미나가 준 것, 바닥). 셰이더가 옮긴 자리와 넓이 평균 읽기로 그린다 (보스 이름 글은 없다).
    """
    import previews as pv
    cells = preview_cells(out, providers, glyphs)
    W, H = size
    scenes = [({"hp": (100, 100, 0), "fp": (60, 60, 0), "st": (90, 90, 0)}, 1240, None),
              ({"hp": (100, 58, 22), "fp": (60, 60, 0), "st": (90, 71, 0)}, 1240, (128, 30, 140)),
              ({"hp": (100, 100, 0), "fp": (60, 41, 0), "st": (90, 37, 0)}, 87650, None),
              ({"hp": (100, 21, 0), "fp": (60, 9, 0), "st": (90, 3, 0)}, 0, None)]
    rows = []
    for lengths, souls, boss in scenes:
        left, right = shader_shift("left", W, H)[:2], shader_shift("right", W, H)[:2]
        layers = [(bar_line(cells, lengths), BOSS_LINE_TOP, left, 1.0),
                  (souls_line(cells, souls), H - ACTION_LINE_UP, right, 1.0)]
        if boss:
            dx, dy, st = shader_shift("boss", W, H, 1)
            bar, caps = boss_line(cells, *boss)
            layers.append((bar, BOSS_LINE_TOP + BOSS_PITCH, (0, dy), st))
            shift = int(np.floor((st - 1.0) * (BOSS_W // 2) + 0.5))
            capl, capr = _Line(cells), _Line(cells)
            capl.items, capr.items = [caps.items[0]], [caps.items[1]]
            layers.append((capl, BOSS_LINE_TOP + BOSS_PITCH, (-shift, dy), 1.0))
            layers.append((capr, BOSS_LINE_TOP + BOSS_PITCH, (shift, dy), 1.0))
        rows.append(_to_screen(_compose(W, H, layers), gui, pv.dusk_scene(W * gui, H * gui)))
    sheet = Image.new("RGB", (W * gui * 2 + 8, H * gui * 2 + 8), (12, 12, 12))
    for i, r in enumerate(rows):
        sheet.paste(r, ((i % 2) * (W * gui + 8), (i // 2) * (H * gui + 8)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)


# ─────────────────────────── 빌드 ───────────────────────────

FOOD_SPRITES = ("food_empty", "food_half", "food_full", "food_empty_hunger", "food_half_hunger", "food_full_hunger")

# souls:hud 빈칸: 음수는 왼쪽으로, 양수는 오른쪽으로 민다. 2의 거듭제곱이라 조합으로 아무 폭이나 만든다.
SPACE_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)


def build(out, digit_role):
    """
    out (팩 뿌리) 에 HUD 그림과 글꼴을 쓰고 (Glyph 목록, 글꼴 {(이름공간, 이름): json}, souls:hud 의 HUD 공급자) 를 돌려준다.
    digit_role = fonts.digit_role() (소울 수 숫자). 기본 글꼴은 사망 화면 공급자만 (fonts.py 의 본문 공급자는 gen_pack 이 앞에 붙인다).
    """
    glyphs = []

    # 투명한 허기 (하트·방어·경험치 막대도 gui_skin 이 투명하게 한다. HUD 는 다크 소울처럼 왼쪽 위 막대 셋)
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
    # 띠: 글자 폭 (사이 빈칸까지) 의 가운데에 띠 가운데가 오게 앞으로 당기고, 띠를 그린 뒤 글 처음 자리로 돌아온다
    adv = {g.name: g.width for g in glyphs}
    letters_w = (sum(adv["you_died_" + n] for n, _ in YOU_DIED_LETTERS) + 5 * YOU_DIED_GAP[2] + YOU_DIED_WORD[2])
    band = death_band()
    save(band, sprite_path(out, NS, "font", "hud_death_band.png"))   # 알파 지도 (artlint data band, palette.BAND_MAP)
    tile = DEATH_BAND_TILE_GUI * DEATH_BAND_TEX
    band_font_h = DEATH_BAND_H_GUI // 2                # 사망 화면 제목은 2배: 글꼴 픽셀 = GUI 2 픽셀
    band_scale = band_font_h / band.height
    tile_adv = {}
    for i, (name, ch) in enumerate(DEATH_BAND):
        tile_adv[name] = glyph_advance(band, i * tile, tile, band.height, band_scale)
        glyphs.append(Glyph(name, ch, tile_adv[name], DEFAULT_FONT, "bitmap"))
    band_w = DEATH_BAND_W_GUI // 2
    pre = (letters_w - band_w) // 2
    post = -(pre + sum(tile_adv[t] - 1 for t in band_tiles()))
    for (name, ch), a in zip(DEATH_BAND_SPACES, (pre, post, -1)):
        glyphs.append(Glyph(name, ch, a, DEFAULT_FONT, "space"))
    death_providers = [
        {"type": "bitmap", "file": f"{NS}:font/hud_death_band.png", "height": band_font_h, "ascent": DEATH_BAND_ASCENT,
         "chars": ["".join(ch for _, ch in DEATH_BAND)]},
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": YOU_DIED_HEIGHT, "ascent": YOU_DIED_ASCENT,
         "chars": ["".join(ch for _, ch in YOU_DIED_LETTERS)]},
        {"type": "space", "advances": {YOU_DIED_GAP[1]: YOU_DIED_GAP[2], YOU_DIED_WORD[1]: YOU_DIED_WORD[2],
                                       DEATH_BAND_SPACES[0][1]: pre, DEATH_BAND_SPACES[1][1]: post,
                                       DEATH_BAND_SPACES[2][1]: -1}},
    ]

    # souls:death: 서서히 나타나는 판의 사망 화면 문구 (1배, GUI 픽셀 = 글꼴 픽셀). 같은 띠 그림과 같은 글자 그림을 1배 높이로,
    # 글자마다 뒤에 빈칸을 두어 제목 판 (2배) 과 같은 자리에 놓는다: 제목 판의 글자 i 는 진행 폭 adv_i (글꼴 픽셀) × 2 와
    # 사이 빈칸 × 2 만큼 가고, 1배 글자는 그림 폭 + 1 만큼 가므로 그 차를 빈칸으로 채운다
    fscale = YOU_DIED_HEIGHT * 2 / cell_h
    fade_adv = {}
    for i, (name, ch) in enumerate(YOU_DIED_LETTERS):
        fade_adv[name] = glyph_advance(sheet, i * cell_w, cell_w, cell_h, fscale)
        glyphs.append(Glyph("fade_you_died_" + name, ch, fade_adv[name], DEATH_FONT, "bitmap"))
    gaps = [YOU_DIED_GAP[2]] * 2 + [YOU_DIED_WORD[2]] + [YOU_DIED_GAP[2]] * 3 + [0]
    fade_space = {}
    for (name, _), (sp, ch), gp in zip(YOU_DIED_LETTERS, DEATH_FADE_SPACES, gaps):
        w = 2 * (adv["you_died_" + name] + gp) - fade_adv[name]
        assert w >= 0, f"souls:death {name}: 빈칸이 음수 ({w})"
        if w:
            fade_space[ch] = w
            glyphs.append(Glyph(sp, ch, w, DEATH_FONT, "space"))
    fade_tile = {}
    for i, (name, ch) in enumerate(DEATH_BAND):
        fade_tile[name] = glyph_advance(band, i * tile, tile, band.height, DEATH_BAND_H_GUI / band.height)
        glyphs.append(Glyph("fade_" + name, ch, fade_tile[name], DEATH_FONT, "bitmap"))
    fpre = 2 * pre
    fpost = -(fpre + sum(fade_tile[t] - 1 for t in band_tiles()))
    for (name, ch), a in zip(DEATH_BAND_SPACES, (fpre, fpost, -1)):
        glyphs.append(Glyph("fade_" + name, ch, a, DEATH_FONT, "space"))
    death_fade_font = {"providers": [
        {"type": "bitmap", "file": f"{NS}:font/hud_death_band.png", "height": DEATH_BAND_H_GUI,
         "ascent": DEATH_FADE_BAND_ASCENT, "chars": ["".join(ch for _, ch in DEATH_BAND)]},
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": YOU_DIED_HEIGHT * 2,
         "ascent": DEATH_FADE_LETTER_ASCENT, "chars": ["".join(ch for _, ch in YOU_DIED_LETTERS)]},
        {"type": "space", "advances": {**fade_space, DEATH_BAND_SPACES[0][1]: fpre, DEATH_BAND_SPACES[1][1]: fpost,
                                       DEATH_BAND_SPACES[2][1]: -1}},
    ]}

    # souls:hud: 빈칸 + 플러그인 화면 제목 + HUD 막대·소울 상자·보스 막대
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
    for name, ch, adv_ in (TITLE_GAP, TITLE_WORD):
        advances[ch] = adv_
        glyphs.append(Glyph(name, ch, adv_, HUD_FONT, "space"))
    hud_font = {"providers": [
        {"type": "space", "advances": advances},
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": TITLE_HEIGHT, "ascent": TITLE_ASCENT,
         "chars": ["".join(ch for _, ch in TITLE_LETTERS)]},
    ]}
    providers, hud_glyph_list, _ = hud_glyphs(out, 0xE040, digit_role)
    hud_font["providers"] += providers
    glyphs += hud_glyph_list

    fonts = {
        ("minecraft", "default"): {"providers": death_providers},
        # 유니코드 글꼴 강제 설정을 켠 사람도 같은 제목을 보게 같은 공급자를 넣는다
        ("minecraft", "uniform"): {"providers": list(death_providers)},
        (NS, "hud"): hud_font,
        (NS, "death"): death_fade_font,
    }
    return glyphs, fonts, providers
