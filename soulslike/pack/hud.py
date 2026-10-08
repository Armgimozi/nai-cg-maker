"""
HUD 그림과 글꼴 (DESIGN.md 10.2, 10.3, 10.9). gen_pack.py 가 부른다.

만드는 것
  허기            food_* 여섯 장을 투명하게 (허기 6 은 달리기를 막는 데만 쓴다, 3.2).
  사망 화면 제목  "YOU DIED" (사용자 결정 3). 손으로 찍은 글자 art/you_died.txt 를
                  minecraft:default 글꼴의 개인 영역 문자로 넣는다 (언어 문자열은 글꼴을 고를 수 없다, 10.9). 뒤에 화면을
                  가로지르는 검은 띠 (2 배 그림, 청동 실).
  souls:hud 글꼴  자리 맞춤 빈칸 (음수·양수), 플러그인 화면 제목용 YOU DIED (death.title: true),
                  다크 소울 HUD (2026-10-07 사용자 결정, 2026-10-08 고딕 촛불 시안 B): 왼쪽 위 막대 셋 (체력·마나·스태미나) 의
                  조각과 마구리, 오른쪽 아래 소울 상자·넋 표식·숫자, 화면 아래 가운데 보스 막대 (체력·잃은 몫·자세 조각과
                  마구리), 무기 설명 칸의 실선 (lore_rule). 자리는 아래 "다크 소울 HUD" 의 머리말. 그림은 GUI 한 픽셀에 2 텍셀
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
  U+E040~E0EF  souls:hud 그림 글자 (HUD 막대 조각·마구리, 소울 상자·표식·숫자, 보스 막대 조각·마구리, 설명 칸 실선. 지금 117개)
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

import uidraw
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
# 다크 소울의 사망 화면처럼 YOU DIED 뒤에 화면을 가로지르는 반투명 검은 띠 (2026-10-07, 다크 소울 UI). 기본 글꼴의 64 폭
# 조각 여덟 (왼쪽 끝, 가운데 여섯, 오른쪽 끝: 글꼴 그림은 256×256 판에 들어가야 하므로 한 장으로는 그릴 수 없다) 이 이어져
# 2배로 GUI 1024×44 픽셀 (GUI 폭 960 까지 덮는다). 글자 가운데에 맞춰 위·아래로 11 씩 (ascent 0), 위·아래 가장자리와
# 양 끝은 알파 계단으로 옅어진다. 띠 앞뒤의 빈칸 두 글자가 띠의 진행 폭을 지워 제목이 바닐라처럼 글자 폭으로 가운데에 놓인다.
DEATH_BAND = (("death_band_l", "\ue007"), ("death_band_m", "\ue008"), ("death_band_r", "\ue009"))
DEATH_BAND_SPACES = ("death_band_pre", "\ue010"), ("death_band_post", "\ue011"), ("death_band_back", "\ue012")
DEATH_BAND_TILE, DEATH_BAND_TILES, DEATH_BAND_H, DEATH_BAND_ASCENT = 64, 8, 22, 0

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
# (YOU_DIED_TOP). 바닐라가 사망 화면 제목에 그리는 그림자 (글자 × 0.25, 2 GUI 픽셀 오른쪽 아래) 는 거의 검은 띠 위라 묻힌다.
YOU_DIED_FLAT, YOU_DIED_TOP = "gore2", "gore3"


def you_died_sheet():
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
        back = by[DEATH_BAND_SPACES[2][0]]
        tiles = [DEATH_BAND[0][0]] + [DEATH_BAND[1][0]] * (DEATH_BAND_TILES - 2) + [DEATH_BAND[2][0]]
        band = by[DEATH_BAND_SPACES[0][0]] + "".join(by[t] + back for t in tiles) + by[DEATH_BAND_SPACES[1][0]]
    return band + you + word + died


def death_band():
    """
    YOU DIED 뒤의 띠 조각 셋 (왼쪽 끝, 가운데, 오른쪽 끝) 을 한 그림에, GUI 한 픽셀에 2 텍셀 (칸 128 텍셀 = GUI 64, 높이 44 텍셀 =
    공급자 높이 22). 먹 한 색에 알파 계단 (가운데 82%), 위·아래 안쪽에 반 픽셀 청동 실 (단추·창의 금실과 같은 말), 양 끝 32 텍셀에서
    옅어진다.
    """
    t, h = DEATH_BAND_TILE * S, DEATH_BAND_H * S
    img = Img(t * 3, h)
    rows = (0.10, 0.22, 0.36, 0.50, 0.62, 0.72)
    for y in range(h):
        d = min(y, h - 1 - y)
        ra = rows[d] if d < len(rows) else 0.82
        for i in range(3):
            for x in range(t):
                e = x if i == 0 else (t - 1 - x if i == 2 else t)
                k = 1.0 if e >= 32 else (e + 1) / 33.0
                img.put(i * t + x, y, "ink0", ra * k)
                if y in (5, h - 6):
                    img.put(i * t + x, y, "bronze2" if y == 5 else "rust1", 0.85 * k)
    return img.image()


def plugin_title(glyphs):
    """플러그인 화면 제목 한 줄 (souls:hud 글꼴)."""
    return death_title(glyphs, "you_died_title_")


# ─────────────────────────── 다크 소울 HUD (10.2, 2026-10-07 사용자 결정, 2026-10-08 고딕 촛불 시안 B) ───────────────────────────
#
# 왼쪽 위에 가는 가로 막대 셋 (체력 · 마나 · 스태미나), 오른쪽 아래에 소울 수 상자, 보스는 화면 아래 가운데에 이름 (왼쪽 맞춤) 과
# 넓은 체력 막대 + 그 밑 반 픽셀 자세 줄. 바닐라 하트·허기·방어·경험치 막대와 조준점은 그림을 투명하게 해서 숨기고 (gui_skin),
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
#   막대     위에서 비친 단조 쇠 테 (윗날에 청동빛 반 픽셀), 안쪽 홈은 위가 가장 어둡고 아래에 녹슨 입술, 채움은 윗줄이 한 단
#            밝고 아래로 어두워진다. 체력은 짙은 진홍, 마나는 다크 소울 FP 처럼 깊고 바랜 쪽빛 (palette 의 mana, 마나 막대 전용
#            예외), 스태미나는 누른 풀빛. 잃은 체력은 옅은 금빛 흰색.
#   마구리   (2026-10-08 고친 것: 막대마다 붙인 세 잎 단조 장식이 셋 쌓여 무거웠다) 막대 양 끝에 반 픽셀 위·아래로만 나오는 가는
#            쇠 기둥. 왼쪽 장식은 체력 막대 하나에만 작은 마름모 창끝 하나. 오른쪽은 기둥과 작은 마름모. 마구리끼리 세로로 닿지
#            않는다 (막대 사이 3 픽셀).
#   소울 수  검은 옻칠 상자, 윗날에 촛불 기운 (가운데가 따뜻하다), 금실 윗줄과 양 끝 마름모, 위 가운데 작은 꽃 장식. 넋 표식은
#            위로 꼬리가 선 옅은 뼈빛 불꽃, 숫자는 가라몽 라이닝 숫자 (고정 폭, fonts.digit_role).
#   보스     체력 막대와 같은 말씨에 더 큰 마구리 (고리와 창끝), 그 밑 반 픽셀 상아빛 자세 줄. 이름은 제목 글꼴 (YAML 의 꼴 태그).

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

# 막대: 채움 줄 색 (위 → 아래, 텍셀 줄), 막대 셋의 맨 위에서의 자리 (GUI)
FILL = {
    "hp": ("crimson3", "crimson2", "crimson2", "crimson2", "crimson2", "crimson1", "crimson1", "crimson0"),
    "fp": ("mana3", "mana2", "mana2", "mana2", "mana1", "mana0"),
    "st": ("sap3", "sap2", "sap2", "sap2", "sap1", "sap0"),
}
TOP = {"hp": 0, "fp": 11, "st": 21}
# 잃은 몫 (2026-10-08 비평: 옅은 금빛 흰색이 HUD 에서 가장 밝아 둘째 막대처럼 읽혔다): 진홍보다 어두운 탁한 황토 (잉걸 계열,
# UI 전용), 윗줄만 한 단 밝다
TRAIL = (("cinder2", 0.9),) + (("cinder1", 0.92),) * 5 + (("cinder0", 0.92),) * 2
RIM = ("bronze2", 0.85)                     # 윗날: 촛불이 비친 청동 한 줄 (반 픽셀)
FRAME = ("ink0", 0.95)
DROP = ("ink0", 0.40)                       # 막대 밑 그늘 반 픽셀
IRON = ["ink0", "rust1", "bronze2", "parch3"]    # 단조 쇠: 아랫날 → 몸 → 윗날 밑 → 윗날 (촛불이 위에서)
GOLD = ["rust1", "bronze3", "parch2", "glim0"]
CAP_EXT = 2                                 # 막대 셋의 마구리가 막대 위·아래로 나오는 텍셀 (반 픽셀 넘게: 1 GUI)
CAP_L_W, CAP_R_W = 12, 10                   # 마구리 칸 폭 (텍셀). 왼쪽은 셋 다 같아 채움이 같은 자리에서 시작한다
CAP_ORN = ("hp",)                           # 왼쪽 작은 마름모를 다는 막대 (하나뿐)

# 소울 상자 (행동 막대): GUI 72×15, 화면 아래에서 8 위에 끝난다 (셰이더 없이). 표식은 상자 왼쪽 안 5, 숫자는 오른쪽 안 6
SOUL_BOX_W, SOUL_BOX_H, SOUL_BOX_BOTTOM = 72, 15, 8
SOUL_INSET = 2
DIGIT_INK = "bone2"
# 보스 막대 (보스 이름 줄 안, 줄 위에서 GUI): 이름 0..7, 체력 막대 맨 위 9, 마구리 7..17, 자세 줄 15.5 (반 픽셀)
BOSS_BAR_ROW = 9
BOSS_FILL_ROWS = ("crimson3", "crimson2", "crimson2", "crimson2", "crimson2", "crimson1", "crimson1", "crimson0")


def trough(n):
    """빈 몫 (홈) n 줄: 위가 가장 어둡고 아래에 녹슨 입술."""
    rows = [("ink0", 0.97), ("ink0", 0.88)] + [("ink0", 0.82)] * max(0, n - 4) + [("rust0", 0.80), ("rust1", 0.55)]
    return rows[:n]


def column(bar, kind):
    """막대 한 칸 세로 줄 (텍셀, 위 → 아래): [(이름, 알파)]."""
    fill = FILL[bar]
    n = len(fill)
    body = {"fill": [(x, 1.0) for x in fill],
            "trail": list(TRAIL[:1] + TRAIL[-(n - 1):]),
            "empty": trough(n)}[kind]
    return [RIM, FRAME] + body + [FRAME, DROP]


def run_sheet(col):
    """폭 1, 2, 4 … 128 GUI 픽셀 조각을 256 텍셀 칸 간격으로 (bitmap 글꼴 한 공급자 = 한 그림, 칸 폭이 같다). None 은 빈 줄."""
    cell = RUN_STEPS[-1] * S
    img = Img(cell * len(RUN_STEPS), len(col))
    for i, n in enumerate(RUN_STEPS):
        for x in range(n * S):
            for y, (nm, a) in enumerate(col):
                if nm:
                    img.put(i * cell + x, y, nm, a)
    return img.image()


def cap_left(hb, ornament):
    """
    막대 셋의 왼쪽 마구리 (텍셀 CAP_L_W × (hb + 2 CAP_EXT)): 칸 오른쪽 끝의 가는 쇠 기둥 (2 텍셀 = GUI 1, 위·아래 끝 둥글게).
    ornament 면 기둥에서 왼쪽으로 짧은 자루와 작은 마름모 창끝 하나 (속이 빈). 셋 다 칸 폭이 같아 기둥과 채움이 한 줄에 선다.
    """
    w, h = CAP_L_W, hb + 2 * CAP_EXT
    cy = h / 2.0
    m = Mask(w, h)
    m.rect(w - 2, 0.9, w, h - 0.9)
    m.disc(w - 1.0, 1.0, 1.0)
    m.disc(w - 1.0, h - 1.0, 1.0)
    if ornament:
        m.rect(6.5, cy - 0.8, w - 1.5, cy + 0.8)
        m.poly([(0.6, cy), (3.8, cy - 3.0), (7.0, cy), (3.8, cy + 3.0)])
        hole = Mask(w, h).poly([(2.6, cy), (3.8, cy - 1.0), (5.0, cy), (3.8, cy + 1.0)])
        cov = np.clip(m.cov() - hole.cov(), 0, 1)
    else:
        cov = m.cov()
    return uidraw.lit(cov, IRON)


def cap_right(hb):
    """막대 셋의 오른쪽 마구리 (CAP_R_W × (hb + 2 CAP_EXT)): 칸 왼쪽 끝의 가는 쇠 기둥, 짧은 자루와 작은 마름모 창끝."""
    w, h = CAP_R_W, hb + 2 * CAP_EXT
    cy = h / 2.0
    m = Mask(w, h)
    m.rect(0, 0.9, 2, h - 0.9)
    m.disc(1.0, 1.0, 1.0)
    m.disc(1.0, h - 1.0, 1.0)
    m.rect(1.5, cy - 0.8, 4.5, cy + 0.8)
    m.poly([(3.6, cy), (6.6, cy - 2.6), (9.6, cy), (6.6, cy + 2.6)])
    hole = Mask(w, h).poly([(5.6, cy), (6.6, cy - 0.9), (7.6, cy), (6.6, cy + 0.9)])
    return uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), IRON)


def boss_cap_left(hb, ext=4):
    """
    보스 막대 왼쪽 마구리 (16 × (hb + 2 ext)): 오른쪽 마구리를 뒤집은 것 (둥근 꼭지의 기둥과 작은 마름모 창끝). 2026-10-08 비평:
    고리와 덩굴이 달린 30 텍셀 장식은 HUD 막대 셋에서 뺀 무거운 장식과 같았다.
    """
    right = boss_cap_right(hb, ext)
    return uidraw.lit(right.alpha[:, ::-1].copy(), IRON)


def boss_cap_right(hb, ext=4):
    """보스 막대 오른쪽 마구리 (16 × (hb + 2 ext)): 둥근 꼭지의 기둥과 작은 마름모 창끝."""
    w, h = 16, hb + 2 * ext
    cy = h / 2.0
    m = Mask(w, h)
    m.rect(0, 2, 4, h - 2)
    m.disc(2.0, 2.4, 2.4)
    m.disc(2.0, h - 2.4, 2.4)
    m.rect(3, cy - 1.0, 7, cy + 1.0)
    m.poly([(5.5, cy), (9.5, cy - 3.2), (w - 0.4, cy), (9.5, cy + 3.2)])
    hole = Mask(w, h).poly([(8.2, cy), (9.8, cy - 1.1), (w - 3.4, cy), (9.8, cy + 1.1)])
    return uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), IRON)


def pair_sheet(left, right):
    """마구리 둘을 한 그림에 (칸 폭 같게): [왼쪽][오른쪽]. 돌려주는 값: 그림."""
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
            add(f"hud_{bar}_{kind}", run_sheet(column(bar, kind)), asc_hud(top), [f"hud_{bar}_{kind}_{n}" for n in RUN_STEPS])
        hb = len(column(bar, "fill"))
        add(f"hud_{bar}_cap", pair_sheet(cap_left(hb, bar in CAP_ORN), cap_right(hb)), asc_hud(top - CAP_EXT // S),
            [f"hud_{bar}_cap_l", f"hud_{bar}_cap_r"])

    box_top = SOUL_BOX_BOTTOM + SOUL_BOX_H
    add("hud_soulbox", soul_box(), box_top - (ACTION_LINE_UP - 7), ["hud_soulbox"])
    add("soul_mark", soul_mark(), (box_top - 2) - (ACTION_LINE_UP - 7), ["soul_mark"])
    dimg, dasc = digits(digit_role)
    base_from_bottom = SOUL_BOX_BOTTOM + 4                     # 숫자 바탕선: 상자 아래에서 4 위
    add("hud_digits", dimg, (base_from_bottom + dasc) - (ACTION_LINE_UP - 7), [f"hud_digit_{d}" for d in range(10)],
        scale=1.0 / 4)

    # 보스 막대 (보스 이름 줄 안): 체력 (윗날·테·채움 여덟·테·그늘), 자세 (반 픽셀 줄), 마구리
    col = [RIM, FRAME] + [(x, 1.0) for x in BOSS_FILL_ROWS] + [FRAME, DROP]
    for kind in ("fill", "trail", "empty"):
        c_ = col if kind == "fill" else ([RIM, FRAME] + (list(TRAIL) if kind == "trail" else trough(8)) + [FRAME, DROP])
        add(f"hud_boss_hp_{kind}", run_sheet(c_), 7 - BOSS_BAR_ROW, [f"boss_hp_{kind}_{n}" for n in RUN_STEPS])
    # 자세 줄: 막대 밑 그늘 줄 (텍셀 11) 다음, 텍셀 13 (GUI 15.5) 에 1 텍셀. 그림은 막대와 같은 위에서
    # 2026-10-08 비평: 잃은 몫과 같은 상아빛 줄이 빈 길 없이 떠 있었다. 채움은 흐린 금 (청동 밝은 색), 빈 몫은 옅은 청동 길
    post_fill = [(None, 0)] * 13 + [("bronze3", 0.95)] + [(None, 0)] * 2
    post_empty = [(None, 0)] * 13 + [("bronze1", 0.6)] + [(None, 0)] * 2
    for kind, cl in (("fill", post_fill), ("empty", post_empty)):
        add(f"hud_boss_post_{kind}", run_sheet(cl), 7 - BOSS_BAR_ROW, [f"boss_post_{kind}_{n}" for n in RUN_STEPS])
    # 보스 마구리는 위·아래 2 GUI 픽셀만 (이름 줄 위 -1 .. +17 안: 셰이더가 꼭짓점 y 로 보스 줄을 고른다)
    add("hud_boss_cap", pair_sheet(boss_cap_left(len(col)), boss_cap_right(len(col))), 7 - (BOSS_BAR_ROW - 2),
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
    save(band, sprite_path(out, NS, "font", "hud_death_band.png"))   # hud_: 곧은 줄 띠라 artlint 가 반복으로 세지 않는다
    band_w = DEATH_BAND_TILE * DEATH_BAND_TILES
    pre = (letters_w - band_w) // 2
    post = -(pre + band_w)
    tile = DEATH_BAND_TILE * S
    for i, (name, ch) in enumerate(DEATH_BAND):
        glyphs.append(Glyph(name, ch, glyph_advance(band, i * tile, tile, band.height, 1.0 / S), DEFAULT_FONT, "bitmap"))
    for (name, ch), a in zip(DEATH_BAND_SPACES, (pre, post, -1)):
        glyphs.append(Glyph(name, ch, a, DEFAULT_FONT, "space"))
    death_providers = [
        {"type": "bitmap", "file": f"{NS}:font/hud_death_band.png", "height": DEATH_BAND_H, "ascent": DEATH_BAND_ASCENT,
         "chars": ["".join(ch for _, ch in DEATH_BAND)]},
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": YOU_DIED_HEIGHT, "ascent": YOU_DIED_ASCENT,
         "chars": ["".join(ch for _, ch in YOU_DIED_LETTERS)]},
        {"type": "space", "advances": {YOU_DIED_GAP[1]: YOU_DIED_GAP[2], YOU_DIED_WORD[1]: YOU_DIED_WORD[2],
                                       DEATH_BAND_SPACES[0][1]: pre, DEATH_BAND_SPACES[1][1]: post,
                                       DEATH_BAND_SPACES[2][1]: -1}},
    ]

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
    }
    return glyphs, fonts, providers
