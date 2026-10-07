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
  U+E000~E01F  minecraft:default (사망 화면 제목 글자와 그 사이 빈칸)
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


# ─────────────────────────── 다크 소울 HUD (10.2, 2026-10-07 사용자 결정) ───────────────────────────
#
# 왼쪽 위에 가는 가로 막대 셋 (체력 · 온기 · 스태미나), 오른쪽 아래에 소울 수 상자. 바닐라 하트·허기·방어·경험치 막대는
# 그림을 투명하게 해서 숨기고 (gui_skin), 막대는 플러그인이 그림 글자로 그린다:
#   막대 셋   HUD 전용 보스 막대 (WHITE, 막대 그림 투명) 의 이름 줄. 첫 보스 막대의 이름 줄은 y 3 (12 - 9) 에 놓이고,
#             줄마다 ascent 로 내려 막대 셋을 쌓는다. 진짜 보스는 RED (체력)·YELLOW (자세) 를 쓴다 (gui_skin 의 보스 막대 그림)
#   소울 수   행동 막대 (줄 위 = 화면 아래 - 72). 음수 ascent 로 화면 아래 가장자리 가까이 내린다
# 가로 자리: 보스 막대 이름과 행동 막대는 화면 가운데에 놓인다. 플러그인은 글 전체의 진행 폭이 0 이 되게 (빈칸 글자로
# 되돌아온다) 만들어 글이 늘 가운데 (GUI 폭 / 2, 버림) 에서 시작하게 하고, 그 자리에서 HUD_KL 만큼 왼쪽 (막대) 또는
# HUD_KR 만큼 오른쪽 (소울 상자 오른쪽 끝) 에 그린다. 이것만으로는 화면 폭 (GUI 배율·창 크기) 에 따라 가장자리와의 거리가
# 바뀌므로, 글꼴 셰이더 (rendertype_text.vsh) 가 표식 색의 글자만 화면 가장자리로 옮긴다 (MARK_*). 셰이더가 없어도
# 1280×720 GUI 배율 3 (폭 427) 에서는 HUD_MARGIN 자리에 맞는다.

HUD_MARGIN = 8              # 화면 가장자리와 HUD 사이 (GUI 픽셀)
HUD_KL = 205                # 셰이더 없이: 막대 왼쪽 끝 = 화면 가운데 - 205 (폭 427 에서 8)
HUD_KR = 206                # 셰이더 없이: 소울 상자 오른쪽 끝 = 화면 가운데 + 206 (폭 427 에서 419)
MARK_LEFT = (254, 253, 1)   # 이 색의 글은 셰이더가 왼쪽 가장자리로 (막대 셋)
MARK_RIGHT = (254, 253, 2)  # 이 색의 글은 오른쪽 가장자리로 (소울 상자)
BOSS_LINE_TOP = 3           # 첫 보스 막대 이름 줄의 위 (GUI y)
ACTION_LINE_UP = 72         # 행동 막대 줄의 위 = 화면 아래 - 72 (68 위로 옮기고 -4 에 쓴다)

# 막대: 이름 → (위 y, 채움 줄 색 (위 → 아래)). 테는 위·아래 한 줄씩 어두운 재. 막대 사이는 한 줄 띄운다.
# 다크 소울 3 처럼 가늘게: 체력 채움 3줄, 온기·스태미나 2줄 (GUI 배율 3 에서 9·6 화면 픽셀).
# 아래 끝 (스태미나 21) 이 둘째 보스 막대의 이름 줄 (22) 위에서 끝나 진짜 보스 막대와 겹치지 않는다.
HUD_BARS = {
    "hp": (7, ("blood3", "blood2", "blood1")),      # 짙은 핏빛
    "fp": (13, ("bronze3", "bronze2")),             # 온기: 탁한 호박빛 (파랑은 팔레트가 막는다)
    "st": (18, ("moss2", "moss1")),                 # 이끼빛 올리브
}
HUD_TRAIL = ("parch2", "parch1", "parch0")          # 맞은 뒤 잠깐 남는 잃은 몫 (체력만): 바랜 양피지빛
FRAME, FRAME_A = "ash0", 235                        # 막대 테 (위·아래 줄, 끝)
TROUGH_A = 150                                      # 빈 몫: 반투명 재 (뒤 세상이 비친다)
CAP = "parch1"                                      # 끝 마구리: 가는 탁한 금빛 세로줄
RUN_STEPS = (1, 2, 4, 8, 16, 32, 64, 128)           # 막대 조각 폭 (조합해 아무 길이나 만든다)

# 소울 상자 (행동 막대): 가로 60, 세로 12. 화면 아래에서 8 위에 끝난다. 표식과 숫자는 상자 안 위 2 에서
SOUL_BOX_W, SOUL_BOX_H, SOUL_BOX_BOTTOM = 60, 12, 8
SOUL_INSET = 2
DIGIT_INK = "bone2"
SOUL_INK = {"o": "ember0", "+": "ember1", "*": "ember2", "@": "ember3"}


def _ascent_boss(top):
    """보스 막대 이름 줄에서 GUI y top 에 그림 위쪽이 오는 ascent (글자 위쪽 = 줄 위 + 7 - ascent)."""
    return BOSS_LINE_TOP + 7 - top


def _ascent_action(from_bottom):
    """행동 막대 줄에서 화면 아래 - from_bottom 에 그림 위쪽이 오는 ascent."""
    return 7 - (ACTION_LINE_UP - from_bottom)


def _bar_rows(kind, rows):
    """막대 한 칸 세로 줄 (위 → 아래): [(색, 알파)]."""
    body = {"fill": [(r, 255) for r in rows],
            "trail": [(HUD_TRAIL[min(i, len(HUD_TRAIL) - 1)], 255) for i in range(len(rows))],
            "empty": [(FRAME, TROUGH_A)] * len(rows)}[kind]
    return [(FRAME, FRAME_A)] + body + [(FRAME, FRAME_A)]


def _run_sheet(column):
    """폭 1, 2, 4 … 128 조각을 128 칸 간격으로 한 줄에 (bitmap 글꼴 한 공급자 = 한 그림, 칸 폭이 같아야 한다)."""
    cell = RUN_STEPS[-1]
    img = Image.new("RGBA", (cell * len(RUN_STEPS), len(column)), (0, 0, 0, 0))
    px = img.load()
    for i, n in enumerate(RUN_STEPS):
        for x in range(n):
            for y, (col, a) in enumerate(column):
                px[i * cell + x, y] = c(col, a)
    return img


def _caps(h):
    """막대 양 끝 마구리 (2칸 폭 두 장을 한 그림에): 왼쪽은 [금빛 줄][테], 오른쪽은 [테][금빛 줄]. 위·아래 끝은 한 단 어둡다."""
    img = Image.new("RGBA", (4, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        edge = y in (0, h - 1)
        line = c("parch0" if edge else CAP)
        px[0, y] = line
        px[1, y] = c(FRAME, FRAME_A)
        px[2, y] = c(FRAME, FRAME_A)
        px[3, y] = line
    return img


def _soul_box():
    """
    소울 수 상자: 반투명 검정 판. 가장자리는 계단으로 옅어진다 (부드러운 그라데이션이 아니라 두 단). 위에 가는 금빛 줄 하나
    (다크 소울 3 의 소울 상자처럼 판 위 가장자리만 빛을 받는다), 줄도 양 끝에서 계단으로 옅어진다.
    """
    w, h = SOUL_BOX_W, SOUL_BOX_H
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            d = min(x, w - 1 - x, y, h - 1 - y)
            a = (70, 120, 165)[min(d, 2)]
            px[x, y] = c("ash0", a)
    for x in range(3, w - 3):
        d = min(x - 3, w - 4 - x)
        px[x, 0] = c("parch0", (90, 150, 200, 230)[min(d, 3)])
    return img


def _digits(grids):
    """숫자 열 장 (칸 폭 6, 높이 8): 뼈빛 숫자 + 오른쪽 아래 한 칸 그림자 (재). 6째 열의 맨 아래 칸에 거의 투명한 점
    (알파 1, 글꼴 셰이더가 0.1 아래는 버린다) 을 두어 모든 숫자의 진행 폭이 같다 (고정폭, 셀 때 숫자가 흔들리지 않는다)."""
    img = Image.new("RGBA", (6 * 10, 8), (0, 0, 0, 0))
    px = img.load()
    for d in range(10):
        rows = grids[str(d)]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    if px[d * 6 + x + 1, y + 1][3] == 0:
                        px[d * 6 + x + 1, y + 1] = c("ash0", 200)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    px[d * 6 + x, y] = c(DIGIT_INK)
        if px[d * 6 + 5, 7][3] == 0:
            px[d * 6 + 5, 7] = c("ash0", 1)
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
// GUI text (orthographic projection) whose colour is a HUD marker is moved to a screen edge.
//   marker {r} {g} {b1}: HUD bars (boss bar name, drawn from the screen centre minus {kl}) -> left edge + {margin}
//   marker {r} {g} {b2}: souls box (action bar, right end at the screen centre plus {kr}) -> right edge - {margin}
// The marker colour is replaced by white so the glyph keeps its own colours.
void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    sphericalVertexDistance = fog_spherical_distance(Position);
    cylindricalVertexDistance = fog_cylindrical_distance(Position);
    vertexColor = Color * texelFetch(Sampler2, UV2 / 16, 0);
    texCoord0 = UV0;

    ivec3 mark = ivec3(Color.rgb * 255.0 + 0.5);
    if (mark.r == {r} && mark.g == {g} && (mark.b == {b1} || mark.b == {b2}) && ProjMat[3][3] == 1.0) {{
        float guiWidth = ceil(2.0 / ProjMat[0][0] - 0.01);
        float centre = floor(guiWidth * 0.5);
        float shift = mark.b == {b1} ? ({margin}.0 - (centre - {kl}.0)) : ((guiWidth - {margin}.0) - (centre + {kr}.0));
        gl_Position.x += shift * ProjMat[0][0];
        vertexColor = vec4(1.0, 1.0, 1.0, Color.a) * texelFetch(Sampler2, UV2 / 16, 0);
    }}
}}
"""


def hud_shader():
    return HUD_SHADER.format(r=MARK_LEFT[0], g=MARK_LEFT[1], b1=MARK_LEFT[2], b2=MARK_RIGHT[2],
                             kl=HUD_KL, kr=HUD_KR, margin=HUD_MARGIN)


def layout():
    """플러그인이 읽는 자리 값 (glyphs.yml 의 layout). 셰이더와 같은 값이어야 한다."""
    return {"margin": HUD_MARGIN, "left": HUD_KL, "right": HUD_KR,
            "mark_left": "#%02x%02x%02x" % MARK_LEFT, "mark_right": "#%02x%02x%02x" % MARK_RIGHT,
            "soul_box": SOUL_BOX_W, "soul_inset": SOUL_INSET}


def hud_glyphs(out, code):
    """
    다크 소울 HUD 그림 글자 (souls:hud). (공급자 목록, Glyph 목록, 다음 문자 번호). 그림은 assets/souls/textures/font/.
    이름: hud_<막대>_<fill|empty|trail>_<폭>, hud_<막대>_cap_l / _cap_r, hud_soulbox, soul_mark, hud_digit_<0..9>.
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

    for bar, (top, rows) in HUD_BARS.items():
        h = len(rows) + 2
        asc = _ascent_boss(top)
        kinds = ("fill", "trail", "empty") if bar == "hp" else ("fill", "empty")
        for kind in kinds:
            add(f"hud_{bar}_{kind}", _run_sheet(_bar_rows(kind, rows)), asc,
                [f"hud_{bar}_{kind}_{n}" for n in RUN_STEPS])
        add(f"hud_{bar}_cap", _caps(h), asc, [f"hud_{bar}_cap_l", f"hud_{bar}_cap_r"])

    box_top = SOUL_BOX_BOTTOM + SOUL_BOX_H          # 화면 아래에서 상자 위쪽까지
    add("hud_soulbox", _soul_box(), _ascent_action(box_top), ["hud_soulbox"])
    grids = load_grids(os.path.join(ART, "hud_glyphs.txt"))
    inner = box_top - SOUL_INSET
    add("soul_mark", grid_image(grids["soul"], SOUL_INK), _ascent_action(inner), ["soul_mark"])
    add("hud_digits", _digits(grids), _ascent_action(inner), [f"hud_digit_{d}" for d in range(10)])
    return providers, glyphs, code


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
    default_font = {"providers": [
        {"type": "bitmap", "file": f"{NS}:font/you_died.png", "height": YOU_DIED_HEIGHT, "ascent": YOU_DIED_ASCENT,
         "chars": ["".join(ch for _, ch in YOU_DIED_LETTERS)]},
        {"type": "space", "advances": {YOU_DIED_GAP[1]: YOU_DIED_GAP[2], YOU_DIED_WORD[1]: YOU_DIED_WORD[2]}},
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
