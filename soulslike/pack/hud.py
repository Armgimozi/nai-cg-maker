"""
HUD 그림과 글꼴 (DESIGN.md 10.2, 10.3, 10.9). gen_pack.py 가 부른다.

만드는 것
  허기            food_* 여섯 장을 투명하게 (허기 6 은 달리기를 막는 데만 쓴다, 3.2).
  사망 화면 제목  "YOU DIED" (사용자 결정 3). 손으로 찍은 글자 art/you_died.txt 를
                  minecraft:default 글꼴의 개인 영역 문자로 넣는다 (언어 문자열은 글꼴을 고를 수 없다, 10.9).
  souls:hud 글꼴  자리 맞춤 빈칸 (음수·양수), 플러그인 화면 제목용 YOU DIED (death.title: true),
                  다크 소울 HUD (2026-10-07 사용자 결정): 왼쪽 위 막대 셋 (체력·온기·스태미나) 의 조각과 마구리,
                  오른쪽 아래 소울 상자·소울 표식·숫자 (art/hud_glyphs.txt). 자리는 아래 "다크 소울 HUD" 의 머리말.
  글꼴 셰이더     assets/minecraft/shaders/core/rendertype_text.vsh: 바닐라 1.21.11 그대로에 한 덩이를 더해, 표식 색의
                  HUD 글만 화면 가장자리로 옮긴다 (10.8).
  하트·방어·경험치 막대는 gui_skin.py 가 투명하게 한다. 레벨 숫자는 플러그인이 레벨 0 을 보내 숨긴다.

글자 표 (glyphs.yml)
  build() 가 돌려주는 Glyph 목록을 gen_pack 이 plugin/src/main/resources/glyphs.yml 로 쓴다.
  이름에는 점을 쓰지 않는다 (Bukkit YAML 은 점을 경로 구분자로 읽는다): you_died_y, space_neg8 처럼.
  플러그인 hud/Glyphs 는 그 파일만 읽고 코드에 문자 번호를 적지 않는다.
  너비(width)는 클라이언트가 재는 것과 같은 식으로 계산한 진행 폭(글꼴 픽셀)이다.

문자 번호
  U+E000~E01F  minecraft:default (사망 화면 제목 글자와 그 사이 빈칸, E007~E009 사망 화면 띠 조각, E010~E012 띠의 빈칸)
  U+E020~E03F  souls:hud 빈칸 (E020~E02F 자리 맞춤, E030·E031 플러그인 제목의 글자 사이)
  U+E040~E0EF  souls:hud 그림 글자 (HUD 막대 조각·마구리, 소울 상자·표식·숫자. 지금 74개, E040~E089)
  U+E0F0~E0F6  souls:hud 플러그인 화면 제목 YOU DIED 글자

glyphs.yml 의 layout
  플러그인이 HUD 를 짤 때 쓰는 자리 값 (layout()): 가장자리 여백, 셰이더 없이 가운데에서 왼쪽·오른쪽으로 민 거리,
  표식 색, 소울 상자 폭. 셰이더와 같은 값이어야 하므로 여기 한 곳에서 정해 둘 다에 쓴다.
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
    사망 화면 띠 조각 셋 (왼쪽 끝, 가운데, 오른쪽 끝) 을 한 그림에 (칸 폭 64). 먹 (중성 검정) 한 색에 알파만 계단: 가운데 줄은
    190 (75%), 위·아래 네 줄과 띠 양 끝 열여섯 열은 옅어진다 (재빛 띠는 붉은 사망 화면 위에서 푸르스름한 회색으로 읽혔다).
    """
    t, h = DEATH_BAND_TILE, DEATH_BAND_H
    img = Image.new("RGBA", (t * 3, h), (0, 0, 0, 0))
    px = img.load()
    rows = (40, 85, 130, 165)
    for y in range(h):
        ra = rows[min(y, h - 1 - y)] if min(y, h - 1 - y) < len(rows) else 190
        for i in range(3):
            for x in range(t):
                d = x if i == 0 else (t - 1 - x if i == 2 else t)
                a = ra if d >= 16 else ra * (d // 4 + 1) // 5
                px[i * t + x, y] = c("ink0", a)
    return img


def plugin_title(glyphs):
    """플러그인 화면 제목 한 줄 (souls:hud 글꼴)."""
    return death_title(glyphs, "you_died_title_")


# ─────────────────────────── 다크 소울 HUD (10.2, 2026-10-07 사용자 결정, 2026-10-08 비평 반영) ───────────────────────────
#
# 왼쪽 위에 가는 가로 막대 셋 (체력 · 온기 · 스태미나), 오른쪽 아래에 소울 수 상자, 보스는 화면 아래 가운데에 이름 (왼쪽 맞춤) 과
# 넓은 체력 막대 + 그 밑 1픽셀 자세 줄. 바닐라 하트·허기·방어·경험치 막대와 조준점은 그림을 투명하게 해서 숨기고 (gui_skin),
# 막대는 플러그인이 그림 글자로 그린다:
#   막대 셋   HUD 전용 보스 막대 (WHITE, 막대 그림 투명) 의 이름 줄. 첫 보스 막대의 이름 줄은 y 3 (12 - 9) 에 놓이고,
#             줄마다 ascent 로 내려 막대 셋을 쌓는다
#   소울 수   행동 막대 (줄 위 = 화면 아래 - 72). 음수 ascent 로 화면 아래 가장자리 가까이 내린다
#   보스      보스마다 보스 막대 하나 (RED, 막대 그림 투명. HUD 막대 다음에 띄우므로 둘째 줄부터). 이름 줄 하나에
#             [이름 사본 (안 보임)][막대 그림 글자][이름][빈칸] 을 쓴다 (boss_line). 바닐라는 이름 줄을 글 폭의 반만큼 왼쪽에서
#             시작하는데 이름 폭은 언어·글꼴마다 달라 서버가 모른다. 같은 이름을 두 번 쓰면 둘째 이름은 폭과 상관없이 늘 가운데
#             - BOSS_W/2 에서 시작하고 (폭 2w 의 반 = w 를 첫 사본이 먹는다), 막대 그림은 첫 사본 뒤 (= 늘 가운데) 에서 그린다.
#             첫 사본은 셰이더가 지운다 (MARK_HIDDEN)
# 가로 자리: 보스 막대 이름과 행동 막대는 화면 가운데에 놓인다. 플러그인은 글 전체의 진행 폭이 0 이 되게 (빈칸 글자로
# 되돌아온다) 만들어 글이 늘 가운데 (GUI 폭 / 2, 버림) 에서 시작하게 하고, 그 자리에서 HUD_KL 만큼 왼쪽 (막대) 또는
# HUD_KR 만큼 오른쪽 (소울 상자 오른쪽 끝) 에 그린다. 글꼴 셰이더 (rendertype_text.vsh) 가 표식 색의 글자만 옮긴다 (MARK_*):
# 막대 셋은 왼쪽 위에서 화면 폭의 4.5% · 높이의 5% 안쪽 (다크 소울처럼 가장자리에서 떨어져), 소울 상자는 오른쪽 아래에서 4%
# 안쪽, 보스는 화면 아래 - BOSS_UP 줄로 내리고 막대를 화면 폭의 약 45% 로 늘인다 (1 ~ 2.5 배, 0.25 마디). 자리는 GUI 픽셀로
# 버림해 그림이 픽셀 격자에 맞는다. 셰이더가 없으면 1280×720 GUI 배율 3 (폭 427) 에서 가장자리 HUD_MARGIN 자리에 맞는다.

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
BOSS_NAME_INK = "parch3"          # 보스 이름 글자색 (밝은 베이지)
BOSS_SHADOW_INK = ("ink0", 200)   # 보스 이름 그림자
BOSS_LINE_TOP = 3           # 첫 보스 막대 이름 줄의 위 (GUI y). 보스 막대마다 19 아래
BOSS_PITCH = 19             # 보스 막대 줄 사이 (바닐라 BossHealthOverlay: 10 + 9)
BOSS_UP = 64                # 셰이더: 보스 이름 줄의 위 = GUI 높이 - 64 (단축 슬롯과 소울 상자 위)
BOSS_STACK = 24             # 보스가 둘 이상이면 위로 이만큼씩 쌓는다
BOSS_W = 200                # 보스 체력 막대의 바탕 길이 (마구리 안, 셰이더가 늘인다)
BOSS_FILL = 0.45            # 셰이더: 늘인 보스 막대 ≈ 화면 폭 × 0.45
ACTION_LINE_UP = 72         # 행동 막대 줄의 위 = 화면 아래 - 72 (68 위로 옮기고 -4 에 쓴다)
HUD_TOP = 8                 # 셰이더 없이: 막대 셋의 맨 위 (GUI y)

# 막대: 이름 → (맨 위 줄 (막대 셋의 맨 위에서), 채움 줄 색 (위 → 아래)). 막대 한 칸 세로 줄은 [테두리 윗날][테][채움…][테],
# 마구리는 그보다 한 줄 길다 (테 위 한 줄 = 윗날 줄, 테 아래 한 줄). 막대 사이는 두 줄 띄워 마구리끼리 닿지 않는다
# (닿으면 막대 셋이 큰 [ ] 꺾쇠로 읽혔다). 다크 소울 3 처럼 가늘게: 체력 채움 3줄, 온기·스태미나 2줄.
HUD_BARS = {
    "hp": (0, ("crimson2", "crimson2", "crimson1")),   # 짙은 진홍 (위 #a0222a, 아래 #6a1218)
    "fp": (8, ("cinder2", "cinder1")),                 # 온기: 뜨거운 잉걸빛 (파랑은 팔레트가 막는다)
    "st": (15, ("sap2", "sap1")),                      # 다크 소울의 누른 풀빛
}
HUD_TRAIL = "glim0"                                 # 맞은 뒤 잠깐 남는 잃은 몫: 옅은 금빛 흰색 (창의 금빛 줄과 갈린다)
RIM = ("bronze2", 100)                              # 막대 윗날: 흐린 청동 1줄 (밝은 하늘에서도 막대가 선다)
FRAME = ("ink0", 230)                               # 막대 테 (위·아래 줄, 끝)
TROUGH = ("ink0", 217)                              # 빈 몫: 85% 검정 (구름이 비치지 않게)
CAP = "parch0"                                      # 끝 마구리: 가는 탁한 금빛 세로줄 (HUD 에서 가장 밝지 않게)
RUN_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)           # 막대 조각 폭 (조합해 아무 길이나 만든다)

# 보스 막대 (보스 이름 줄 안, 줄 위에서): 이름 0..7, 체력 [윗날 9][테 10][채움 11..13][테 14], 자세 15 (1줄), 마구리 9..15.
# 셰이더가 줄 번호를 글자 꼭짓점의 y 로 셈하므로 (줄 위 -1 .. +17) 그림은 줄 위 + 16 아래에서 끝난다
BOSS_ROWS = {"hp": 9, "post": 15}
BOSS_HP = ("crimson2", "crimson2", "crimson1")
BOSS_POST = ("bone3", ("ink0", 150))                # 자세: 옅은 상아빛 줄 / 빈 몫

# 소울 상자 (행동 막대): 가로 64, 세로 13. 화면 아래에서 8 위에 끝난다 (셰이더 없이). 표식과 숫자는 상자 안 위 2·3 에서
SOUL_BOX_W, SOUL_BOX_H, SOUL_BOX_BOTTOM = 64, 13, 8
SOUL_INSET = 2
SOUL_FILL = ("ink0", 166)                           # 65% 검정
DIGIT_INK = "bone2"
# 소울 표식: 옅은 뼈빛 넋 (불덩이처럼 보이지 않게), 속에 희미한 불씨 한 점 (빛 허용 그림 soul_mark)
SOUL_INK = {"o": "bone0", "+": "bone1", "*": "bone3", "@": "ember3"}


def _ascent_boss(top):
    """보스 막대 이름 줄에서 GUI y top 에 그림 위쪽이 오는 ascent (글자 위쪽 = 줄 위 + 7 - ascent)."""
    return BOSS_LINE_TOP + 7 - top


def _ascent_line(r):
    """이름 줄 위에서 r 아래에 그림 위쪽이 오는 ascent (보스 막대: 줄이 어디든 같은 자리)."""
    return 7 - r


def _ascent_action(from_bottom):
    """행동 막대 줄에서 화면 아래 - from_bottom 에 그림 위쪽이 오는 ascent."""
    return 7 - (ACTION_LINE_UP - from_bottom)


def _px(col):
    return c(col) if isinstance(col, str) else c(col[0], col[1])


def _bar_rows(kind, rows, trail=HUD_TRAIL, rim=True):
    """막대 한 칸 세로 줄 (위 → 아래): [(색 이름, 알파)]."""
    body = {"fill": [(r, 255) for r in rows],
            "trail": [(trail, 255)] * len(rows),
            "empty": [TROUGH] * len(rows)}[kind]
    return ([RIM] if rim else []) + [FRAME] + body + [FRAME]


def _run_sheet(column):
    """폭 1, 2, 4 … 128 조각을 128 칸 간격으로 한 줄에 (bitmap 글꼴 한 공급자 = 한 그림, 칸 폭이 같아야 한다)."""
    cell = RUN_STEPS[-1]
    img = Image.new("RGBA", (cell * len(RUN_STEPS), len(column)), (0, 0, 0, 0))
    px = img.load()
    for i, n in enumerate(RUN_STEPS):
        for x in range(n):
            for y, col in enumerate(column):
                if col is not None:
                    px[i * cell + x, y] = _px(col)
    return img


def _caps(n, rim=True):
    """
    막대 양 끝 마구리 (2칸 폭 두 장을 한 그림에, 높이 n + 1: 막대 칸 줄 n 과 그 아래 한 줄). 왼쪽은 [마구리 줄][막대 끝],
    오른쪽은 [막대 끝][마구리 줄]. 마구리 줄은 막대보다 한 줄씩 위·아래로 나온다 (윗날 줄과 그 아래 줄), 나온 끝은 반쯤 옅다.
    막대 끝 열: 윗날 줄은 윗날 색, 그 아래는 테 (막대의 세로 끝).
    """
    h = n + 1
    img = Image.new("RGBA", (4, h), (0, 0, 0, 0))
    px = img.load()
    top = 0 if rim else 1
    for y in range(h):
        if y < top:
            continue
        edge = y in (top, h - 1)
        line = c(CAP, 150 if edge else 255)
        px[0, y] = line
        px[3, y] = line
        if y == 0 and rim:
            end = _px(RIM)
        elif y < n:
            end = _px(FRAME)
        else:
            continue
        px[1, y] = end
        px[2, y] = end
    return img


def _soul_box():
    """
    소울 수 상자: 다크 소울 3 처럼 65% 검은 띠. 양 끝 여섯 열은 세 단으로 옅어지고 (2열씩), 위·아래 가장자리 한 줄도 한 단 옅다.
    그 안쪽 (위 1, 아래 h-2) 에 1픽셀 탁한 금빛 줄 (같은 계단으로 양 끝에서 사라진다): 줄이 채움 안에 든다.
    """
    w, h = SOUL_BOX_W, SOUL_BOX_H
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    base = SOUL_FILL[1]
    steps = (0.25, 0.5, 0.75)
    for x in range(w):
        d = min(x, w - 1 - x)
        k = steps[d // 2] if d < 6 else 1.0
        for y in range(h):
            if y in (1, h - 2):
                px[x, y] = c("parch0", int(170 * k))
            else:
                a = base * k * (0.6 if y in (0, h - 1) else 1.0)
                px[x, y] = c(SOUL_FILL[0], int(a))
    return img


def _digits(grids):
    """숫자 열 장 (칸 폭 6, 높이 8): 뼈빛 숫자 + 오른쪽 아래 한 칸 옅은 그늘 (먹). 6째 열의 맨 아래 칸에 거의 투명한 점
    (알파 1, 글꼴 셰이더가 0.1 아래는 버린다) 을 두어 모든 숫자의 진행 폭이 같다 (고정폭, 셀 때 숫자가 흔들리지 않는다)."""
    img = Image.new("RGBA", (6 * 10, 8), (0, 0, 0, 0))
    px = img.load()
    for d in range(10):
        rows = grids[str(d)]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    if px[d * 6 + x + 1, y + 1][3] == 0:
                        px[d * 6 + x + 1, y + 1] = c("ink0", 140)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    px[d * 6 + x, y] = c(DIGIT_INK)
        if px[d * 6 + 5, 7][3] == 0:
            px[d * 6 + 5, 7] = c("ink0", 1)
    return img


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
//   b {b3} / {b4} / {b5}: boss bar glyphs / boss name / boss name shadow on boss bar line k (top 3 + 19 k)
//          -> line top at the screen bottom - {up} (stacked {stack} up per extra boss); the bar glyphs are
//             stretched around the screen centre to about {fill} x width ({bw} wide, 1 to 2.5 in quarter steps),
//             the name moves with the bar's left end. Name -> beige, shadow -> dark
//   b {b6}: hidden (alpha 0): the boss name copy that only cancels the name width
// Other marker glyphs keep their own colours (vertex colour replaced by white).
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
    vertexColor = Color * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;

    ivec3 mark = ivec3(Color.rgb * 255.0 + 0.5);
    if (mark.r == {r} && mark.g == {g} && mark.b >= {b1} && mark.b <= {b6} && ProjMat[3][3] == 1.0) {{
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
    n, h = c(BOSS_NAME_INK), c(BOSS_SHADOW_INK[0])
    return HUD_SHADER.format(r=MARK_LEFT[0], g=MARK_LEFT[1], b1=MARK_LEFT[2], b2=MARK_RIGHT[2], b3=MARK_BOSS[2],
                             b4=MARK_BOSS_NAME[2], b5=MARK_BOSS_SHADOW[2], b6=MARK_HIDDEN[2],
                             kl=HUD_KL, kr=HUD_KR, top0=HUD_TOP, bot0=SOUL_BOX_BOTTOM,
                             ix=_f(HUD_INSET[0]), iy=_f(HUD_INSET[1]), sx=_f(SOUL_INSET_FR[0]), sy=_f(SOUL_INSET_FR[1]),
                             up=BOSS_UP, stack=BOSS_STACK, fill=_f(BOSS_FILL), bw=BOSS_W,
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
            "boss_width": BOSS_W, "soul_box": SOUL_BOX_W, "soul_inset": SOUL_INSET}


def hud_glyphs(out, code):
    """
    다크 소울 HUD 그림 글자 (souls:hud). (공급자 목록, Glyph 목록, 다음 문자 번호). 그림은 assets/souls/textures/font/.
    이름: hud_<막대>_<fill|empty|trail>_<폭>, hud_<막대>_cap_l / _cap_r, hud_soulbox, soul_mark, hud_digit_<0..9>,
    boss_hp_<fill|trail|empty>_<폭>, boss_post_<fill|empty>_<폭>, boss_cap_l / _cap_r.
    """
    providers, glyphs = [], []

    def add(name, img, ascent, cells, file_name=None):
        nonlocal code
        fname = file_name or name
        save(img, sprite_path(out, NS, "font", fname + ".png"))
        cw = img.width // len(cells)
        chars = ""
        for i, cell in enumerate(cells):
            ch = chr(code)
            code += 1
            chars += ch
            glyphs.append(Glyph(cell, ch, glyph_advance(img, i * cw, cw, img.height, 1.0), HUD_FONT, "bitmap"))
        providers.append({"type": "bitmap", "file": f"{NS}:font/{fname}.png", "height": img.height,
                          "ascent": ascent, "chars": [chars]})

    for bar, (off, rows) in HUD_BARS.items():
        n = len(rows) + 3
        asc = _ascent_boss(HUD_TOP + off)
        kinds = ("fill", "trail", "empty") if bar == "hp" else ("fill", "empty")
        for kind in kinds:
            add(f"hud_{bar}_{kind}", _run_sheet(_bar_rows(kind, rows)), asc,
                [f"hud_{bar}_{kind}_{n_}" for n_ in RUN_STEPS])
        add(f"hud_{bar}_cap", _caps(n), asc, [f"hud_{bar}_cap_l", f"hud_{bar}_cap_r"])

    box_top = SOUL_BOX_BOTTOM + SOUL_BOX_H          # 화면 아래에서 상자 위쪽까지
    add("hud_soulbox", _soul_box(), _ascent_action(box_top), ["hud_soulbox"])
    grids = load_grids(os.path.join(ART, "hud_glyphs.txt"))
    add("soul_mark", grid_image(grids["soul"], SOUL_INK), _ascent_action(box_top - 2), ["soul_mark"])
    add("hud_digits", _digits(grids), _ascent_action(box_top - 3), [f"hud_digit_{d}" for d in range(10)])

    # 보스 막대 (보스 이름 줄 안): 체력 (윗날·테·채움 셋·테), 자세 (1줄), 마구리
    asc = _ascent_line(BOSS_ROWS["hp"])
    for kind in ("fill", "trail", "empty"):
        add(f"boss_hp_{kind}", _run_sheet(_bar_rows(kind, BOSS_HP)), asc, [f"boss_hp_{kind}_{n_}" for n_ in RUN_STEPS],
            file_name=f"hud_boss_hp_{kind}")
    for kind, col in (("fill", BOSS_POST[0]), ("empty", BOSS_POST[1])):
        add(f"boss_post_{kind}", _run_sheet([col]), _ascent_line(BOSS_ROWS["post"]),
            [f"boss_post_{kind}_{n_}" for n_ in RUN_STEPS], file_name=f"hud_boss_post_{kind}")
    # 마구리는 체력 막대의 윗날 줄부터 자세 줄까지 (테보다 위·아래로 한 줄씩 나온다): 막대와 자세 줄을 한 묶음으로 닫는다
    add("boss_cap", _caps(len(BOSS_HP) + 3), asc, ["boss_cap_l", "boss_cap_r"], file_name="hud_boss_cap")
    return providers, glyphs, code


# ─────────────────────────── HUD 짜기 (플러그인 hud/Hud 와 같은 차례) 와 미리보기 ───────────────────────────

def _runs(seq, prefix, n):
    for step in reversed(RUN_STEPS):
        while n >= step:
            seq += [f"{prefix}{step}", ("move", -1)]
            n -= step


def bar_line(lengths):
    """
    막대 셋의 글자 차례: [(이름 | ("move", 픽셀))]. lengths = {막대: (길이, 채움, 잃은 몫)}. 플러그인 Hud.bars 와 같다:
    가운데에서 HUD_KL 왼쪽으로 가서 막대마다 [왼쪽 마구리][채움][잃은 몫][빈 몫][오른쪽 마구리] 를 그리고 처음 자리로
    돌아와 다음 줄 (ascent 가 다른 그림이라 아래 줄에 그려진다), 끝에 가운데로 돌아와 글 전체의 진행 폭이 0 이다.
    그림 글자는 폭 + 1 만큼 나아가므로 조각마다 1 을 되돌린다.
    """
    seq = [("move", -HUD_KL)]
    for bar in HUD_BARS:
        if bar not in lengths:
            continue
        length, fill, trail = lengths[bar]
        seq += [f"hud_{bar}_cap_l", ("move", -1)]
        for kind, n in (("fill", fill), ("trail", trail), ("empty", length - fill - trail)):
            _runs(seq, f"hud_{bar}_{kind}_", n)
        seq += [f"hud_{bar}_cap_r", ("move", -1)]
        seq.append(("move", -(length + 4)))
    seq.append(("move", HUD_KL))
    return seq


def boss_bars(hp, trail, post):
    """
    보스 막대 그림 글자의 차례 (가운데에서 시작해 가운데 - BOSS_W/2 에서 끝난다, 진행 폭 -BOSS_W/2): 마구리, 체력
    (채움·잃은 몫·빈 몫, 합 BOSS_W), 마구리, 자세 줄 (채움·빈 몫, 합 BOSS_W). hp, trail, post 는 픽셀. 플러그인 Hud.bossLine 과 같다.
    """
    half = BOSS_W // 2
    seq = [("move", -half - 2), "boss_cap_l", ("move", -1)]
    for kind, n in (("fill", hp), ("trail", trail), ("empty", BOSS_W - hp - trail)):
        _runs(seq, f"boss_hp_{kind}_", n)
    seq += ["boss_cap_r", ("move", -1), ("move", -(BOSS_W + 2))]
    for kind, n in (("fill", post), ("empty", BOSS_W - post)):
        _runs(seq, f"boss_post_{kind}_", n)
    seq.append(("move", -BOSS_W))
    return seq


def souls_line(n, by_name):
    """소울 상자의 글자 차례: 상자 오른쪽 끝이 가운데 + HUD_KR, 표식은 상자 왼쪽 안, 숫자는 오른쪽 안에 붙인다."""
    digits = str(max(0, int(n)))
    dw = by_name["hud_digit_0"].width - 1
    seq = [("move", HUD_KR - SOUL_BOX_W), "hud_soulbox", ("move", -(SOUL_BOX_W + 1)),
           ("move", 5), "soul_mark", ("move", -(by_name["soul_mark"].width + 5))]
    x = SOUL_BOX_W - 6 - dw * len(digits)
    seq.append(("move", x))
    for d in digits:
        seq += [f"hud_digit_{d}", ("move", -1)]
    seq.append(("move", -(x + dw * len(digits)) - (HUD_KR - SOUL_BOX_W)))
    return seq


def _advance(seq, by_name):
    return sum(s[1] if isinstance(s, tuple) else by_name[s].width for s in seq)


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


def preview_hud(out, path, glyphs, gui=3, size=(427, 240)):
    """
    HUD 미리보기 (pack/preview/hud.png): 저녁 화면 위에 바닐라처럼 그린 막대 셋과 소울 상자 네 장면 (가득, 맞은 뒤 잃은 몫과
    보스 막대, 달려 스태미나가 준 것, 스태미나가 바닥). 셰이더가 옮긴 자리로 그린다 (보스 이름 글은 그리지 않는다).
    """
    import json
    import previews as pv
    by_name = {g.name: g for g in glyphs}
    font = json.load(open(os.path.join(out, "assets", NS, "font", "hud.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(out, "assets", NS, "font", "hud.json")) else None
    sheets = {}

    def glyph_image(name):
        ch = by_name[name].char
        for p in hud_font_providers:
            if p["type"] == "bitmap" and ch in "".join(p["chars"]):
                f = p["file"].split(":", 1)[1]
                if f not in sheets:
                    sheets[f] = Image.open(os.path.join(out, "assets", NS, "textures", f)).convert("RGBA")
                sh = sheets[f]
                row = p["chars"][0]
                cw = sh.width // len(row)
                i = row.index(ch)
                return sh.crop((i * cw, 0, (i + 1) * cw, sh.height)), p["ascent"]
        raise KeyError(name)

    hud_font_providers = font["providers"] if font else []
    W, H = size
    scenes = [("full", {"hp": (100, 100, 0), "fp": (60, 60, 0), "st": (90, 90, 0)}, 1240, None),
              ("damaged", {"hp": (100, 58, 22), "fp": (60, 60, 0), "st": (90, 71, 0)}, 1240, (128, 30, 140)),
              ("sprint", {"hp": (100, 100, 0), "fp": (60, 41, 0), "st": (90, 37, 0)}, 87650, None),
              ("low", {"hp": (100, 21, 0), "fp": (60, 9, 0), "st": (90, 3, 0)}, 0, None)]
    rows = []
    for _, lengths, souls, boss in scenes:
        canvas = pv.dusk_scene(W * gui, H * gui)
        small = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lines = [(bar_line(lengths), BOSS_LINE_TOP, W // 2, shader_shift("left", W, H), 0),
                 (souls_line(souls, by_name), H - ACTION_LINE_UP, W // 2, shader_shift("right", W, H), 0)]
        if boss:
            lines.append((boss_bars(*boss), BOSS_LINE_TOP + BOSS_PITCH, W // 2, shader_shift("boss", W, H, 1), -(BOSS_W // 2)))
        for seq, line_top, anchor, (dx, dy, st), net in lines:
            assert _advance(seq, by_name) == net, "HUD 글의 진행 폭이 맞지 않는다"
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            pen = anchor
            for s_ in seq:
                if isinstance(s_, tuple):
                    pen += s_[1]
                    continue
                img, asc = glyph_image(s_)
                layer.alpha_composite(img, (pen, line_top + 7 - asc))
                pen += by_name[s_].width
            if st != 1.0:
                cx = W // 2
                stretched = layer.resize((round(W * st), H), Image.NEAREST)
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                layer.alpha_composite(stretched.crop((round(cx * st) - cx, 0, round(cx * st) - cx + W, H)))
            small.alpha_composite(layer, (int(dx), int(dy)))
        canvas.alpha_composite(small.resize((W * gui, H * gui), Image.NEAREST))
        rows.append(canvas)
    sheet = Image.new("RGBA", (W * gui * 2 + 8, H * gui * 2 + 8), (12, 12, 12, 255))
    for i, r in enumerate(rows):
        sheet.alpha_composite(r, ((i % 2) * (W * gui + 8), (i // 2) * (H * gui + 8)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)


# ─────────────────────────── 빌드 ───────────────────────────

FOOD_SPRITES = ("food_empty", "food_half", "food_full", "food_empty_hunger", "food_half_hunger", "food_full_hunger")

# souls:hud 빈칸: 음수는 왼쪽으로, 양수는 오른쪽으로 민다. 2의 거듭제곱이라 조합으로 아무 폭이나 만든다.
SPACE_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)


def build(out):
    """out (팩 뿌리) 에 HUD 그림과 글꼴을 쓰고 Glyph 목록을 돌려준다."""
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
    for i, (name, ch) in enumerate(DEATH_BAND):
        glyphs.append(Glyph(name, ch, glyph_advance(band, i * DEATH_BAND_TILE, DEATH_BAND_TILE, band.height, 1.0),
                            DEFAULT_FONT, "bitmap"))
    for (name, ch), a in zip(DEATH_BAND_SPACES, (pre, post, -1)):
        glyphs.append(Glyph(name, ch, a, DEFAULT_FONT, "space"))
    default_font = {"providers": [
        {"type": "bitmap", "file": f"{NS}:font/hud_death_band.png", "height": DEATH_BAND_H, "ascent": DEATH_BAND_ASCENT,
         "chars": ["".join(ch for _, ch in DEATH_BAND)]},
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": YOU_DIED_HEIGHT, "ascent": YOU_DIED_ASCENT,
         "chars": ["".join(ch for _, ch in YOU_DIED_LETTERS)]},
        {"type": "space", "advances": {YOU_DIED_GAP[1]: YOU_DIED_GAP[2], YOU_DIED_WORD[1]: YOU_DIED_WORD[2],
                                       DEATH_BAND_SPACES[0][1]: pre, DEATH_BAND_SPACES[1][1]: post,
                                       DEATH_BAND_SPACES[2][1]: -1}},
    ]}

    # souls:hud: 빈칸 + 플러그인 화면 제목 + HUD 막대·소울 상자
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
    # 다크 소울 HUD: 막대 조각·마구리, 소울 상자·표식·숫자 (U+E040 부터)
    providers, hud_glyph_list, _ = hud_glyphs(out, 0xE040)
    hud_font["providers"] += providers
    glyphs += hud_glyph_list
    # 표식 색의 HUD 글을 화면 가장자리로 옮기는 글꼴 셰이더 (10.8)
    shader = os.path.join(out, "assets", "minecraft", "shaders", "core", "rendertype_text.vsh")
    os.makedirs(os.path.dirname(shader), exist_ok=True)
    with open(shader, "w", encoding="ascii", newline="\n") as f:
        f.write(hud_shader())

    fonts = {
        ("minecraft", "default"): default_font,
        # 유니코드 글꼴 강제 설정을 켠 사람도 같은 제목을 보게 같은 공급자를 넣는다
        ("minecraft", "uniform"): default_font,
        (NS, "hud"): hud_font,
    }
    return glyphs, fonts
