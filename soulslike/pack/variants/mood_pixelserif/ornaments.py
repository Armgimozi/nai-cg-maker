"""
픽셀 명조 (mood_pixelserif) 의 장식: 지금 창 그림 (gui_skin.py, 고치지 않고 불러 쓴다) 위에 조금 더 짙은 금빛 꾸밈을 얹는다.

  창 (인벤토리·제작대·상자)  네 귀의 꺾쇠를 겹 꺾쇠 + 안쪽 고리 + 대각선 점 (귀 꾸밈) 으로, 위 가운데 마름모를 가운데 큰
                              마름모와 양옆 작은 마름모의 관 (冠) 으로, 아래 가운데에도 작은 마름모. 칸 사이 나눔줄은 가운데에
                              작은 마름모가 있는 줄 (가운데 무늬의 나눔줄).
  설명 칸                     160×160 9조각: 바탕은 위가 조금 밝고 아래로 깊어지는 검정 (안쪽 위 가장자리에 옅은 빛 한 줄),
                              테는 금빛 줄 + 네 귀 꾸밈, 위 테 24 줄 안 (글 위에서 10, 이름 줄과 둘째 줄 사이) 에 이름 밑줄:
                              양 끝 작은 마름모에서 시작해 금빛 실선. 한 줄짜리 설명 칸 (바닐라 아이템 이름만) 은 9조각이
                              위 테를 반으로 줄여 밑줄이 보이지 않는다.
  단추                        띠는 그대로, 가리키면 양 끝 마름모 대신 작은 꽃잎 꾸밈 (마름모 + 양옆 꼬리).
  비네트                      textures/misc/vignette.png: 바닐라보다 넓고 깊게 (가장자리가 먹빛으로 가라앉는다).
  제목 밑줄 글자              minecraft:default 의 개인 영역 그림 글자 (2배 밀도): 가운데 마름모와 양옆 고리가 있는 금빛 나눔줄.
                              언어 파일의 제목 글 (게임 메뉴, 설정, 휴식 창 이름) 뒤에 빈칸 글자와 함께 붙여 제목 밑 가운데에 그린다.

색은 모두 palette.c (이름, 알파). 그림 한 칸 = GUI 1 픽셀 (창·설명 칸·단추), 제목 밑줄 글자만 GUI 0.5 픽셀.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE))
if PACK not in sys.path:
    sys.path.insert(0, PACK)
import gui_skin as gs  # noqa: E402
from gui_skin import Cv  # noqa: E402
from palette import c  # noqa: E402

ORN, ORN_HI, LINE, LINE_DIM = gs.ORN, gs.ORN_HI, gs.LINE, gs.LINE_DIM
INK = gs.INK
DARK = ("ink0", 230)            # 마름모 속


# ─────────────────────────── 귀 꾸밈 ───────────────────────────

# 왼쪽 위 귀 (금빛 줄의 귀가 (0, 0)). A 밝은 금빛, H 가장 밝은 점, L 보통 줄, d 흐린 점. 나머지 세 귀는 거울상
CORNER = [
    "AAAAAAAL.",
    "A.......L",
    "A.LLL....",
    "A.L......",
    "A.L.H....",
    "A........",
    "A........",
    "L........",
    ".L.......",
]
CORNER_INK = {"A": ORN, "H": ORN_HI, "L": LINE, "d": LINE_DIM}


def corner_filigree(cv, w, h, inset=2, rows=CORNER):
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx = inset if sx > 0 else w - 1 - inset
        cy = inset if sy > 0 else h - 1 - inset
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch == ".":
                    continue
                cv.put(cx + sx * dx, cy + sy * dy, CORNER_INK[ch])


# 위 가운데 관: 큰 마름모 (속은 먹) 와 양옆에 떨어진 작은 마름모 둘. 짝수 폭 (20) 이라 짝수 폭 판의 꼭 가운데.
# 가운데 줄 (2) 이 판의 금빛 줄에 걸친다
CREST = [
    ".........HA.........",
    "...A....AkkA....A...",
    "LLAkALLAkkkkALLAkALL",
    "...A....AkkA....A...",
    ".........AA.........",
]
# 아래 가운데: 작은 마름모 하나 (짝수 폭 4)
BASE_GEM = [
    ".AA.",
    "AkkA",
    ".AA.",
]
GEM_INK = {"A": ORN, "H": ORN_HI, "k": DARK, "L": LINE}


def crest(cv, w, y_line=2):
    cv.stamp(w // 2 - 10, y_line - 2, CREST, GEM_INK)


def base_gem(cv, w, h, inset=2):
    cv.stamp(w // 2 - 2, h - 1 - inset - 1, BASE_GEM, GEM_INK)


# 가운데 무늬의 나눔줄: 1픽셀 줄 (양 끝 알파 계단) 의 가운데에 작은 마름모, 마름모 양옆은 두 칸 비운다
def motif_divider(cv, x0, x1, y):
    gs.divider(cv, x0, x1, y)
    mid = (x0 + x1 + 1) // 2
    for x in range(mid - 5, mid + 5):
        cv.put(x, y, gs.PANEL)
    cv.stamp(mid - 2, y - 1, BASE_GEM, GEM_INK)
    for x in (mid - 5, mid + 4):
        cv.put(x, y, ("parch0", 120))


def container(name):
    """gui_skin.container 위에 귀 꾸밈·관·가운데 무늬 나눔줄을 바꿔 넣는다 (알파 섞기가 아니라 칸째 바꾼다)."""
    L = gs.CONTAINER_LAYOUTS[name]
    w, h = L["size"]
    img = gs.container(name)
    px = img.load()
    # 위 가운데 옛 마름모 자리를 판으로 되돌린다 (0·1 행 가장자리 계단, 2 행 금빛 줄, 3·4 행 판: 옆 칸을 그대로 옮긴다)
    for x in range(w // 2 - 8, w // 2 + 8):
        for y in range(0, 5):
            px[x, y] = px[w // 2 - 12, y]
    # 판 몸 (gui_skin.PANEL) 을 위가 조금 옅고 아래로 깊어지는 검정으로 (위에서 비치는 빛, 알파 172 → 208)
    panel_rgba = c(*gs.PANEL)
    for y in range(h):
        a = int(172 + 36 * y / (h - 1))
        for x in range(w):
            if px[x, y] == panel_rgba:
                px[x, y] = panel_rgba[:3] + (a,)
    over = Cv(256, 256)
    corner_filigree(over, w, h)
    crest(over, w)
    base_gem(over, w, h)
    for x0, x1, y in L["dividers"]:
        motif_divider(over, x0, x1, y)
    for y in range(over.h):
        for x in range(over.w):
            v = over.px[y][x]
            if v is not None:
                px[x, y] = c(v[0], v[1])
    return img


# ─────────────────────────── 설명 칸 ───────────────────────────

TIP_N = 160
TIP_TOP = 24                     # 위 테 (이름 밑줄이 든다)
TIP_LINE = 9                     # 테 줄 (가장자리에서 9 = 글에서 3). 바닐라는 설명 칸이 화면 아래에 닿으면 글 아래 3 까지만
                                 # 화면 안에 두므로 그보다 바깥의 줄은 잘린다
TIP_SCALING = {
    "background": {"type": "nine_slice", "width": TIP_N, "height": TIP_N,
                   "border": {"left": 12, "top": 12, "right": 12, "bottom": 12}, "stretch_inner": True},
    "frame": {"type": "nine_slice", "width": TIP_N, "height": TIP_N,
              "border": {"left": 12, "top": TIP_TOP, "right": 12, "bottom": 12}, "stretch_inner": True},
}
TIP_RULE = 22                    # 이름 밑줄 줄 (글 위 = 12, 이름 아래끝 = 20, 둘째 줄 = 24)


def tooltip():
    """
    (바탕, 테) 160×160. 바닐라는 글 둘레 (x-12, y-12, 폭+24, 높이+24) 에 둘을 그린다.
    바탕은 테 줄 바깥 두 칸 (7, 8) 의 계단부터 안쪽: 위가 조금 밝고 아래로 깊어지는 검정 (알파 243 → 249: 뒤의 아이템·개수가
    비치지 않게), 테 바로 안쪽 위에 옅은 빛 한 줄. 테는 금빛 줄의 네 귀가 바깥으로 세 칸 나가 엇걸리고 (비문 틀의 귀),
    귀 바깥 대각선에 점 하나. 이름 밑줄은 TIP_RULE 줄.
    """
    N = TIP_N
    o = TIP_LINE - 2                     # 바탕 바깥 끝
    bg = Cv(N, N)
    for y in range(o, N - o):
        t = (y - o) / (N - 2 * o - 1)
        a = int(243 + 6 * t)
        for x in range(o, N - o):
            d = min(x - o, y - o, N - 1 - o - x, N - 1 - o - y)
            corner = min(x - o, N - 1 - o - x) + min(y - o, N - 1 - o - y)
            if corner == 0:
                continue
            if d == 0:
                bg.put(x, y, (INK, 120))
            elif d == 1:
                bg.put(x, y, (INK, 200))
            else:
                bg.put(x, y, (INK, a))
    for x in range(TIP_LINE + 2, N - TIP_LINE - 2):
        bg.put(x, TIP_LINE + 1, ("parch0", 40))      # 금빛 줄 바로 안쪽의 옅은 빛 (위에서 비치는 촛불)
    fr = Cv(N, N)
    L = TIP_LINE
    fr.box(L, L, N - 1 - L, N - 1 - L, ("parch1", 255))
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx = L if sx > 0 else N - 1 - L
        cy = L if sy > 0 else N - 1 - L
        for i in range(1, 4):                       # 바깥으로 나간 귀 (엇걸린 줄)
            fr.put(cx - sx * i, cy, ("parch1", 255 - 50 * i))
            fr.put(cx, cy - sy * i, ("parch1", 255 - 50 * i))
        for i in range(0, 3):                       # 귀에서 안쪽으로 밝은 금빛 두 칸
            fr.put(cx + sx * i, cy, ORN)
            fr.put(cx, cy + sy * i, ORN)
        fr.put(cx, cy, ORN_HI)
        fr.put(cx - sx * 2, cy - sy * 2, ORN)       # 바깥 대각선 점
    # 이름 밑줄: 양 끝 작은 마름모 (3×3) 에서 시작하는 금빛 실선 (마름모 옆 네 칸은 알파 계단)
    y = TIP_RULE
    for gx in (L + 3, N - 1 - L - 3):
        fr.put(gx, y - 1, ORN)
        fr.put(gx - 1, y, ORN)
        fr.put(gx + 1, y, ORN)
        fr.put(gx, y + 1, ORN)
        fr.put(gx, y, ORN_HI)
    steps = (90, 140, 190, 230)
    x0, x1 = L + 5, N - 1 - L - 5
    for x in range(x0, x1 + 1):
        d = min(x - x0, x1 - x)
        a = steps[d] if d < len(steps) else 255
        fr.put(x, y, ("parch1", a))
    return bg.image(), fr.image()


# ─────────────────────────── 단추 ───────────────────────────

# 가리킨 단추의 양 끝 꾸밈 (가운데 줄 9·10 에 걸친다): 마름모와 안쪽으로 뻗는 꼬리
BTN_FLEUR = [
    "..A....",
    ".AHA...",
    "AHkHALL",
    "AHkHALL",
    ".AHA...",
    "..A....",
]


def button(state):
    img = gs.button(state)
    if state != "highlighted":
        return img
    cv = Cv(img.width, img.height)
    rows = BTN_FLEUR
    ink = {"A": ORN, "H": ORN_HI, "k": DARK, "L": ("parch1", 150)}
    # 왼쪽 끝 (x 1..7), 오른쪽은 거울상
    cv.stamp(1, 7, rows, ink)
    cv.stamp(img.width - 8, 7, [r[::-1] for r in rows], ink)
    out = img.copy()
    px = out.load()
    # gui_skin 의 양 끝 마름모 자리 (x 2..4, 8..11) 를 띠 색으로 되돌린 뒤 꾸밈을 얹는다
    for gx in (3, img.width - 4):
        for x in range(gx - 1, gx + 2):
            for y in range(8, 12):
                px[x, y] = px[12, y]
    for y in range(cv.h):
        for x in range(cv.w):
            v = cv.px[y][x]
            if v:
                px[x, y] = c(v[0], v[1])
    return out


# ─────────────────────────── 비네트 ───────────────────────────

def vignette(size=256):
    """
    바닐라 비네트 자리 (textures/misc/vignette.png). 바닐라는 화면 = 화면 × (1 − 그림 × 밝기) 로 섞는다 (밝기는 어두운 곳일수록 1).
    가운데는 0, 가장자리로 갈수록 짙게 (네 귀 0.97, 바닐라 0.82). 회색 한 가지라 팔레트와 상관없다.
    """
    import math
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            u, v = (x + 0.5) / size * 2 - 1, (y + 0.5) / size * 2 - 1
            r = math.sqrt((u * u) * 0.85 + (v * v) * 1.15) / math.sqrt(2)
            t = max(0.0, (r - 0.18) / 0.62)
            val = min(1.0, t ** 1.35 * 1.1) * 0.97
            g = int(round(val * 255))
            px[x, y] = (g, g, g)
    return img


# ─────────────────────────── 제목 밑줄 글자 (2배 밀도) ───────────────────────────

# 가운데 무늬: 마름모 (속 먹) 와 양옆 고리, 그 밖으로 1칸 실선이 양 끝으로 옅어진다. 폭 RULE_W (그림 칸, GUI 의 두 배)
RULE_W, RULE_H = 176, 10              # 높이는 짝수 (글꼴 높이 5 = 배율 0.5)
RULE_MOTIF = [
    "................A................",
    "...............AHA...............",
    "..dd..........AHkHA..........dd..",
    ".d..d........AHkkkHA........d..d.",
    "L....dLLLLLLAHkkkkkHALLLLLLd....L",
    ".d..d........AHkkkHA........d..d.",
    "..dd..........AHkHA..........dd..",
    "...............AHA...............",
    "................A................",
]


def title_rule():
    """제목 밑줄 그림 (RULE_W×RULE_H, 2배 밀도)."""
    cv = Cv(RULE_W, RULE_H)
    mid = RULE_W // 2
    y = 5
    steps = (40, 70, 100, 130, 160, 190, 215, 235)
    for x in range(RULE_W):
        d = min(x, RULE_W - 1 - x)
        a = steps[d // 4] if d // 4 < len(steps) else 255
        cv.put(x, y, ("parch2", a))
    w = len(RULE_MOTIF[0])
    ink = {"A": ORN, "H": ORN_HI, "k": DARK, "L": ("parch2", 255), "d": ("parch1", 255)}
    for dy, row in enumerate(RULE_MOTIF):
        for dx, ch in enumerate(row):
            if ch != ".":
                cv.put(mid - w // 2 + dx, y - 4 + dy, ink[ch])
    return cv.image()


def preview(out_png, base_pack):
    """장식 그림을 4배로 한 장에 (창 셋의 위쪽, 설명 칸, 단추, 제목 밑줄)."""
    tiles = []
    for name in ("inventory",):
        tiles.append(container(name).crop((0, 0, 176, 166)))
    bg, fr = tooltip()
    tip = Image.new("RGBA", (TIP_N, 80), (0, 0, 0, 0))
    tip.alpha_composite(bg.crop((0, 0, TIP_N, 80)))
    tip.alpha_composite(fr.crop((0, 0, TIP_N, 80)))
    tiles.append(tip)
    tiles.append(button("highlighted"))
    tiles.append(button("normal"))
    tiles.append(title_rule())
    W = max(t.width for t in tiles) * 4 + 16
    H = sum(t.height * 4 + 8 for t in tiles) + 8
    sheet = Image.new("RGBA", (W, H), (58, 52, 48, 255))
    y = 8
    for t in tiles:
        sheet.alpha_composite(t.resize((t.width * 4, t.height * 4), Image.NEAREST), (8, y))
        y += t.height * 4 + 8
    sheet.save(out_png)


# ─────────────────────────── HUD 소울 수 숫자 ───────────────────────────

def hud_digits():
    """
    hud.py 의 숫자 열 장 (칸 6, 높이 8, 진행 폭 7) 자리를 그대로 두고 2배 밀도 (칸 12, 높이 16) 세리프 숫자로: EB Garamond 의
    가지런한 숫자 (lnum), 뼈빛, 오른쪽 아래 한 칸 먹 그늘. 칸 맨 아래 오른쪽 (11, 15) 에 알파 1 점을 두어 모든 숫자의 진행 폭이
    int(0.5 + 12 × 0.5) + 1 = 7 로 같다 (플러그인이 glyphs.yml 의 폭 7 로 오른쪽 맞춤을 짠다).
    """
    import serif
    font = serif.load("EBGaramond[wght].ttf", 22 * serif.SS, 500)
    img = Image.new("RGBA", (12 * 10, 16), (0, 0, 0, 0))
    px = img.load()
    for d in range(10):
        g = serif.ink(serif.latin_glyph(font, str(d), base=15, thr=0.42, squash=1.0, features=["lnum"]))
        x0 = d * 12 + max(0, (10 - g.width) // 2)
        gp = g.load()
        for y in range(g.height):
            for x in range(g.width):
                if gp[x, y] and x0 + x + 1 < d * 12 + 11 and y + 1 < 16 and px[x0 + x + 1, y + 1][3] == 0:
                    px[x0 + x + 1, y + 1] = c("ink0", 150)
        for y in range(g.height):
            for x in range(g.width):
                if gp[x, y] and x0 + x < d * 12 + 11:
                    px[x0 + x, y] = c("bone2")
        px[d * 12 + 11, 15] = c("ink0", 1)
    return img
