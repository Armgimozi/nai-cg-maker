"""
mood2_gothic 의 창·단추·단축 슬롯 그림 (GUI 한 픽셀에 2 텍셀, 셰이더가 넓이 평균으로 읽는다). 칸 자리는 바닐라와 픽셀까지
같다 (pack/gui_skin.py 의 CONTAINER_LAYOUTS 를 그대로 쓴다).

말씨 (촛불 아래의 고딕)
  판     깊은 검은 옻칠 (먹 86%). 윗날 밑에 촛불 기운이 고인다 (가운데가 가장 따뜻한 청동 → 녹 → 먹의 계단, 가장자리로 갈수록
         얕다). 가장자리 두 텍셀은 알파 계단.
  테     두 줄: 바깥 굵은 줄 (위는 촛불이 비친 금빛, 옆은 청동, 아래는 녹슨 쇠로 꺼진다) 과 안쪽 가는 청동 줄.
  장식   네 귀에 단조 꺾쇠 (꺾인 쇠, 안으로 말린 덩굴 고리, 바깥 대각선 창끝), 위 가운데에 마름모 꽃 장식. 모두 위가 밝다.
  칸     판보다 진한 우물: 위·왼쪽 안벽은 그늘 (먹), 아래 안벽은 촛불을 받은 녹빛 입술. 고른 칸·결과 칸은 금빛 테.
  단추   띠 위의 글: 위 금실 (가운데가 밝다)·아래 녹슨 줄이 양 끝으로 옅어진다. 가리키면 띠 윗부분에 촛불 기운, 금실이
         밝아지고 양 끝에 단조 마름모 장식.
"""
import json
import math
import os
import sys

import numpy as np

import draw
from draw import Img, Mask

S = 2
HERE = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.dirname(os.path.dirname(HERE))
if PACK_DIR not in sys.path:
    sys.path.insert(0, PACK_DIR)
import gui_skin  # noqa: E402  (칸 배치 CONTAINER_LAYOUTS, 읽기만)

GUI = ("assets", "minecraft", "textures", "gui")
IRON = ["ink0", "rust1", "bronze2", "parch3"]
GOLD = ["rust1", "bronze3", "parch2", "glim0"]
PANEL_A = 0.88


def gpath(pack, *parts):
    return os.path.join(pack, *GUI, *parts)


def mcmeta(png, scaling):
    with open(png + ".mcmeta", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"gui": {"scaling": scaling}}, f, indent=2)
        f.write("\n")


# ─────────────────────────── 판·테·장식 ───────────────────────────

def candle(dx, dy, depth):
    """촛불 기운의 색 (없으면 None): dx = 가운데에서 가로 거리 (0..1), dy = 윗날에서 텍셀, depth = 기운이 닿는 깊이."""
    r = math.sqrt((dx * 1.05) ** 2 + (dy / max(depth, 1)) ** 2)
    if r < 0.30:
        return "bronze1"
    if r < 0.55:
        return "bronze0"
    if r < 0.82:
        return "rust0"
    return None


def panel(img, x0, y0, w, h, alpha=PANEL_A, glow=12, fade=(0.35, 0.65), uniform=False):
    """
    판 (텍셀 네모). 가장자리 len(fade) 줄은 알파 계단, 귀는 한 텍셀 깎는다. 윗날 밑 glow 텍셀에 촛불 기운.
    uniform: 9 조각 그림 (가운데가 이어 붙여진다) 이면 촛불 기운을 가로로 고르게 (위에서 아래로만 옅어진다).
    """
    for y in range(h):
        for x in range(w):
            d = min(x, y, w - 1 - x, h - 1 - y)
            corner = min(x, w - 1 - x) + min(y, h - 1 - y)
            if corner == 0:
                continue
            a = alpha * (fade[d] if d < len(fade) else 1.0)
            name = "ash0"
            if glow and y >= len(fade):
                cn = candle(0.0 if uniform else abs(x + 0.5 - w / 2.0) / (w / 2.0), y - len(fade), glow)
                if cn:
                    name = cn
            img.put(x0 + x, y0 + y, name, a)


def frame(img, x0, y0, w, h, inset=5, inner=True, uniform=False):
    """두 줄 테: 바깥 줄 (inset, 2 텍셀 굵기) 은 위 금빛·옆 청동·아래 녹, 안쪽 줄 (inset+4, 1 텍셀) 은 흐린 청동."""
    L, T, R, B = x0 + inset, y0 + inset, x0 + w - 1 - inset, y0 + h - 1 - inset
    for x in range(L, R + 1):
        dx = 0.4 if uniform else abs(x + 0.5 - (x0 + w / 2.0)) / (w / 2.0)
        img.put(x, T, "parch3" if dx < 0.25 else ("parch2" if dx < 0.6 else "parch1"), 1.0)
        img.put(x, T + 1, "bronze2", 1.0)
        img.put(x, B - 1, "rust1", 1.0)
        img.put(x, B, "ink0", 0.9)
    for y in range(T + 2, B - 1):
        t = (y - T) / max(1, B - T)
        img.put(L, y, "bronze2" if t < 0.5 else "rust2", 1.0)
        img.put(L + 1, y, "ink0", 0.9)
        img.put(R, y, "bronze2" if t < 0.5 else "rust2", 1.0)
        img.put(R - 1, y, "ink0", 0.9)
    if inner:
        i = inset + 4
        L2, T2, R2, B2 = x0 + i, y0 + i, x0 + w - 1 - i, y0 + h - 1 - i
        for x in range(L2 + 6, R2 - 5):
            img.put(x, T2, "bronze1", 0.9)
            img.put(x, B2, "rust0", 0.8)
        for y in range(T2 + 6, B2 - 5):
            img.put(L2, y, "bronze0", 0.8)
            img.put(R2, y, "bronze0", 0.8)


def corner_orn(size=16):
    """왼쪽 위 귀 장식 (size×size 텍셀): 꺾인 쇠 (L), 안쪽 덩굴 고리, 귀 대각선 창끝. 다른 귀는 뒤집어 쓴다."""
    m = Mask(size, size)
    m.rect(2, 2, size, 4.5)                    # 윗변 쇠 (테 위에 겹친다)
    m.rect(2, 2, 4.5, size)                    # 왼변
    m.ring(7.5, 7.5, 2.0, 3.8, 0, 360)         # 덩굴 고리
    m.line(3.2, 3.2, 5.0, 5.0, 2.2)
    m.poly([(0.0, 0.0), (4.6, 1.6), (1.6, 4.6)])   # 바깥 창끝
    m.disc(size - 2.2, 3.2, 1.7)               # 끝 꼭지
    m.disc(3.2, size - 2.2, 1.7)
    hole = Mask(size, size).disc(7.5, 7.5, 1.0)
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    return draw.lit(cov, IRON)


def crest(w=34, h=16):
    """위 가운데 꽃 장식: 가운데 마름모 (속이 빈) 와 양옆으로 말린 덩굴, 아래로 짧은 창끝."""
    m = Mask(w, h)
    cx = w / 2.0
    cy = 7.0
    m.poly([(cx - 6.0, cy), (cx, cy - 6.6), (cx + 6.0, cy), (cx, cy + 6.6)])
    for sx in (-1, 1):
        m.ring(cx + sx * 10.5, cy + 1.0, 2.2, 4.0, 180 if sx < 0 else 0, 360 if sx < 0 else 180)
        m.ring(cx + sx * 10.5, cy + 1.0, 2.2, 4.0, 270 if sx < 0 else 180, 360 if sx < 0 else 270)
        m.disc(cx + sx * 15.2, cy + 1.2, 1.5)
        m.line(cx + sx * 5.0, cy, cx + sx * 7.5, cy, 2.0)
    hole = Mask(w, h).poly([(cx - 2.6, cy), (cx, cy - 3.0), (cx + 2.6, cy), (cx, cy + 3.0)])
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    out = draw.lit(cov, GOLD)
    out.fill(Mask(w, h).disc(cx, cy, 1.2).cov(), "glim0", 1.0)
    return out


def flip(img, fx, fy):
    out = Img(img.w, img.h)
    n, a = img.name, img.alpha
    if fx:
        n, a = n[:, ::-1], a[:, ::-1]
    if fy:
        n, a = n[::-1], a[::-1]
    out.name, out.alpha = n.copy(), a.copy()
    return out


def corners(img, x0, y0, w, h, inset=3, size=16, top=True, bottom=True):
    o = corner_orn(size)
    if top:
        img.over(o, x0 + inset, y0 + inset)
        img.over(flip(o, True, False), x0 + w - inset - size, y0 + inset)
    if bottom:
        # 아래 귀는 위아래를 뒤집어도 빛은 위에서: 다시 비춘다
        ob = flip(o, False, True)
        relit = draw.lit(ob.alpha, IRON)
        img.over(relit, x0 + inset, y0 + h - inset - size)
        img.over(flip(relit, True, False), x0 + w - inset - size, y0 + h - inset - size)


def well(img, x, y, w=18, h=18, rim=None, floor=0.93):
    """
    바닐라 칸 상자 (GUI x, y, w×h) 안의 우물: 아이템 자리 (x+1..x+w-2) 가 텍셀 [2(x+1), 2(x+w-1)). 바깥 한 텍셀 (바닐라 그늘·입술
    자리의 안쪽 반) 에 쇠 테 (위는 촛불을 받은 청동, 옆·아래는 녹), 안쪽 위·왼쪽 벽은 그늘, 아래 벽은 녹빛 입술.
    """
    X0, Y0, X1, Y1 = 2 * (x + 1), 2 * (y + 1), 2 * (x + w - 1), 2 * (y + h - 1)
    for yy in range(Y0, Y1):
        for xx in range(X0, X1):
            img.put(xx, yy, "ink0", floor)
    for xx in range(X0, X1):
        img.put(xx, Y0, "ink0", 1.0)                 # 위 안벽: 그늘
        img.put(xx, Y0 + 1, "ink0", 0.97)
        img.put(xx, Y1 - 1, "rust0", 0.95)           # 아래 입술: 촛불을 받은 녹
    for yy in range(Y0 + 1, Y1 - 1):
        img.put(X0, yy, "ink0", 1.0)
        img.put(X1 - 1, yy, "ink0", 0.97)
    top, bot, side = rim or ("bronze1", "rust1", "rust1")
    for xx in range(X0 - 1, X1 + 1):
        img.put(xx, Y0 - 1, top, 0.95)
        img.put(xx, Y1, bot, 0.9)
    for yy in range(Y0, Y1):
        img.put(X0 - 1, yy, side, 0.85)
        img.put(X1, yy, side, 0.85)


def divider(img, x0, x1, y, gem=True):
    """나눔줄 (텍셀): 금실 한 줄과 밑의 그늘, 양 끝 12 텍셀 알파 계단, 가운데 작은 마름모."""
    n = x1 - x0
    for i in range(n):
        d = min(i, n - 1 - i)
        k = 1.0 if d >= 12 else (d + 1) / 13.0
        img.put(x0 + i, y, "parch1", 0.9 * k)
        img.put(x0 + i, y + 1, "ink0", 0.6 * k)
    if gem:
        cx = (x0 + x1) / 2.0
        m = Mask(img.w, 8)
        m.poly([(cx - 4.0, 4.0), (cx, 0.5), (cx + 4.0, 4.0), (cx, 7.5)])
        g = draw.lit(m.cov(), GOLD)
        img.over(g, 0, y - 4)


def arrow(img, x0, x1, ym, half):
    """제작 화살표 (GUI 자리): 단조 쇠 자루와 두 갈래 촉, 위가 밝다."""
    W = img.w
    m = Mask(W, 2 * (2 * half + 3))
    oy = 2 * (ym - half - 1)
    yc = 2 * ym + 1 - oy
    m.line(2 * x0 + 1, yc, 2 * x1 - 2, yc, 2.2)
    m.line(2 * x1 - 1.5, yc, 2 * (x1 - half) + 0.5, yc - 2 * half + 0.5, 2.2)
    m.line(2 * x1 - 1.5, yc, 2 * (x1 - half) + 0.5, yc + 2 * half - 0.5, 2.2)
    m.disc(2 * x0 + 1.5, yc, 1.8)
    img.over(draw.lit(m.cov(), IRON), 0, oy)


# ─────────────────────────── 창 (256×256 GUI → 512 텍셀) ───────────────────────────

def container(name):
    L = gui_skin.CONTAINER_LAYOUTS[name]
    w, h = L["size"]
    img = Img(512, 512)
    panel(img, 0, 0, 2 * w, 2 * h, glow=22)
    frame(img, 0, 0, 2 * w, 2 * h)
    if name == "generic_54":
        corners(img, 0, 0, 2 * w, 2 * h)
    else:
        corners(img, 0, 0, 2 * w, 2 * h)
    c = crest()
    img.over(c, w - c.w // 2, 0)
    if L["alcove"]:
        x, y, aw, ah = L["alcove"]
        well(img, x, y, aw, ah, floor=0.97)
    for x, y in L["wells"]:
        well(img, x, y)
    for x, y, rw, rh in L["result"]:
        well(img, x, y, rw, rh, rim=("parch3", "bronze2", "bronze3"))
    if L["arrow"]:
        arrow(img, *L["arrow"])
    for x0, x1, y in L["dividers"]:
        divider(img, 2 * x0, 2 * (x1 + 1), 2 * y + 1, gem=True)
    return img


# ─────────────────────────── 단축 슬롯 ───────────────────────────

def hotbar():
    """
    182×22 GUI. 칸 상자 (2+20k, 2) 18×18, 아이템 (3+20k, 3). 칸마다 쇠 테 우물, 칸 뒤로 지나가는 단조 쇠 띠 (윗날 청동),
    칸 사이 띠 위에 작은 마름모 못, 양 끝에 둥근 꼭지의 기둥.
    """
    img = Img(364, 44)
    for x in range(2, 362):
        img.put(x, 19, "bronze2", 0.9)
        img.put(x, 20, "rust1", 0.95)
        img.put(x, 21, "rust1", 0.95)
        img.put(x, 22, "ink0", 0.9)
        img.put(x, 23, "ink0", 0.5)
    for k in range(9):
        x = 2 + 20 * k
        X0 = 2 * x
        for yy in range(4, 40):
            for xx in range(X0, X0 + 36):
                img.put(xx, yy, "ink0", 0.62)
        well(img, x, 2, floor=0.80)
    for k in range(8):
        cx = 2 * (2 + 20 * k + 19) + 0.0
        m = Mask(364, 44).poly([(cx - 3.2, 21), (cx, 16.6), (cx + 3.2, 21), (cx, 25.4)])
        img.over(draw.lit(m.cov(), GOLD))
    for ex in (0, 360):
        m = Mask(4, 44)
        m.rect(0.5, 8, 3.5, 36)
        m.disc(2, 8, 1.8)
        m.disc(2, 36, 1.8)
        img.over(draw.lit(m.cov(), IRON), ex, 0)
    return img


def selection():
    """24×23 GUI (바닐라는 고른 칸보다 한 칸 왼쪽 위에서 그린다): 금빛 테 (텍셀 6..41), 네 귀 꼭지, 위 가운데 작은 마름모."""
    W, H = 48, 46
    m = Mask(W, H)
    m.rect(4, 4, 44, 7)
    m.rect(4, 40, 44, 43)
    m.rect(4, 4, 7, 43)
    m.rect(41, 4, 44, 43)
    for cx, cy in ((5.5, 5.5), (42.5, 5.5), (5.5, 41.5), (42.5, 41.5)):
        m.disc(cx, cy, 2.8)
    m.poly([(24 - 5, 5.5), (24, 0.3), (24 + 5, 5.5), (24, 10.5)])
    hole = Mask(W, H).poly([(24 - 2, 5.5), (24, 3.2), (24 + 2, 5.5), (24, 7.8)])
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    img = draw.lit(cov, GOLD)
    return img


def offhand(right):
    """29×24 GUI: 칸 상자 (x0+2, 3) 18×18 (왼쪽 x0 = 0, 오른쪽 7)."""
    img = Img(58, 48)
    x0 = 7 if right else 0
    for yy in range(6, 42):
        for xx in range(2 * (x0 + 2), 2 * (x0 + 20)):
            img.put(xx, yy, "ink0", 0.62)
    well(img, x0 + 2, 3, floor=0.80)
    return img


def crosshair():
    """15×15 GUI: 가운데 작은 마름모 하나 (바닐라는 조준점을 뒤 색을 뒤집어 섞는다: 겨눌 자리만 겨우 보인다)."""
    img = Img(30, 30)
    m = Mask(30, 30).poly([(13.2, 15), (15, 13.2), (16.8, 15), (15, 16.8)])
    img.fill(m.cov(), "ash2", 1.0)
    return img


# ─────────────────────────── 단추·위젯 ───────────────────────────

def finial(h=24, flip_x=False):
    """단추 양 끝의 단조 마름모 장식 (14×h 텍셀)."""
    w = 14
    cy = h / 2.0
    m = Mask(w, h)
    m.poly([(1.0, cy), (6.0, cy - 5.0), (11.0, cy), (6.0, cy + 5.0)])
    m.line(10.0, cy, 13.5, cy, 1.8)
    m.ring(6.0, cy - 7.5, 1.4, 2.8, 90, 270)
    m.ring(6.0, cy + 7.5, 1.4, 2.8, 90, 270)
    hole = Mask(w, h).poly([(3.6, cy), (6.0, cy - 2.4), (8.4, cy), (6.0, cy + 2.4)])
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    if flip_x:
        cov = cov[:, ::-1]
    out = draw.lit(cov, GOLD)
    out.fill(Mask(w, h).disc(6.0 if not flip_x else w - 6.0, cy, 1.0).cov(), "glim0", 1.0)
    return out


def button(state, W=400, H=40):
    img = Img(W, H)
    ends = 28
    for x in range(W):
        d = min(x, W - 1 - x)
        k = 1.0 if d >= ends else (d + 1) / (ends + 1.0)
        dx = 0.4                       # 9 조각: 가운데는 이어 붙여지므로 가로로 고르게
        for y in range(4, H - 4):
            if state == "highlighted":
                dy = y - 4
                name = "ink0"
                if dy < 4:
                    name = "bronze1" if dx < 0.5 else "bronze0"
                elif dy < 9:
                    name = "bronze0" if dx < 0.6 else "rust0"
                elif dy < 14:
                    name = "rust0"
                img.put(x, y, name, 0.78 * k)
            elif state == "disabled":
                img.put(x, y, "ink0", 0.30 * k)
            else:
                img.put(x, y, "ink0", 0.58 * k)
        if state == "highlighted":
            top = "parch3" if dx < 0.35 else ("parch2" if dx < 0.75 else "parch1")
            img.put(x, 2, top, 1.0 * k)
            img.put(x, 3, "bronze2", 0.9 * k)
            img.put(x, H - 4, "bronze2", 0.9 * k)
            img.put(x, H - 3, "rust1", 0.9 * k)
        elif state == "disabled":
            img.put(x, 3, "ash1", 0.6 * k)
            img.put(x, H - 4, "ash1", 0.5 * k)
        else:
            img.put(x, 3, "parch1" if dx < 0.6 else "parch0", 0.85 * k)
            img.put(x, H - 4, "rust1", 0.8 * k)
    if state == "highlighted":
        f = finial(H - 12)
        img.over(f, 6, 6)
        img.over(finial(H - 12, flip_x=True), W - 6 - f.w, 6)
    return img


BUTTON_SCALING = {"type": "nine_slice", "width": 200, "height": 20, "border": {"left": 14, "top": 4, "right": 14, "bottom": 4}}


def slider_track(hi):
    img = Img(400, 40)
    for x in range(400):
        d = min(x, 399 - x)
        k = 1.0 if d >= 20 else (d + 1) / 21.0
        for y in range(4, 36):
            img.put(x, y, "ink0", 0.62 * k)
        img.put(x, 3, ("parch2" if hi else "parch0"), 0.85 * k)
        img.put(x, 36, "rust1", 0.8 * k)
        img.put(x, 19, "rust1", 0.7 * k)          # 가운데 홈
        img.put(x, 20, "ink0", 0.9 * k)
    return img


def slider_handle(hi):
    """8×20 GUI: 단조 쇠 기둥 손잡이, 위·아래 둥근 꼭지 (가리키면 금빛)."""
    W, H = 16, 40
    m = Mask(W, H)
    m.rect(5, 5, 11, 35)
    m.disc(8, 5, 3.6)
    m.disc(8, 35, 3.6)
    m.ellipse(8, 20, 4.4, 5.5)
    hole = Mask(W, H).ellipse(8, 20, 1.6, 2.6)
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    return draw.lit(cov, GOLD if hi else IRON)


def checkbox(selected, hi):
    img = Img(40, 40)
    panel(img, 2, 2, 36, 36, alpha=0.8, glow=0, fade=(0.5,))
    m = Mask(40, 40)
    m.rect(4, 4, 36, 6)
    m.rect(4, 34, 36, 36)
    m.rect(4, 4, 6, 36)
    m.rect(34, 4, 36, 36)
    img.over(draw.lit(m.cov(), GOLD if hi else IRON))
    if selected:
        g = Mask(40, 40).poly([(20, 9), (31, 20), (20, 31), (9, 20)])
        hole = Mask(40, 40).poly([(20, 15), (25, 20), (20, 25), (15, 20)])
        img.over(draw.lit(np.clip(g.cov() - hole.cov(), 0, 1), GOLD))
        img.fill(Mask(40, 40).disc(20, 20, 2.0).cov(), "glim0", 1.0)
    return img


def text_field(hi):
    img = Img(400, 40)
    for y in range(2, 38):
        for x in range(2, 398):
            img.put(x, y, "ink0", 0.9)
    for x in range(400):
        img.put(x, 0, "parch1" if hi else "rust1", 1.0)
        img.put(x, 1, "ink0", 1.0)
        img.put(x, 39, "bronze2" if hi else "rust0", 1.0)
    for y in range(40):
        img.put(0, y, "parch0" if hi else "rust1", 1.0)
        img.put(399, y, "parch0" if hi else "rust1", 1.0)
    return img


def warning_button(state):
    """Dialog 경고 단추 20×20 GUI: 작은 옻칠 판과 단조 테, 가운데 금빛 "!" (창끝 모양)."""
    img = Img(40, 40)
    panel(img, 1, 1, 38, 38, alpha={"normal": 0.75, "highlighted": 0.85, "disabled": 0.45}[state], glow=10 if state == "highlighted" else 0,
          fade=(0.5,))
    m = Mask(40, 40)
    m.rect(3, 3, 37, 5)
    m.rect(3, 35, 37, 37)
    m.rect(3, 3, 5, 37)
    m.rect(35, 3, 37, 37)
    img.over(draw.lit(m.cov(), GOLD if state == "highlighted" else IRON))
    ex = Mask(40, 40)
    ex.poly([(17.4, 9), (22.6, 9), (21.0, 24), (19.0, 24)])
    ex.disc(20, 29.5, 2.4)
    ramp = GOLD if state != "disabled" else ["ink0", "ash1", "ash2", "ash3"]
    img.over(draw.lit(ex.cov(), ramp))
    return img


# ─────────────────────────── 설명 칸 ───────────────────────────

TT = 100            # GUI (텍셀 200)


def tooltip_bg(divider_at=None, top_border=12):
    """
    설명 칸 바탕 (바닐라는 글 둘레 12 GUI 밖까지 그린다). 판 3..96 GUI, 두 줄 테 (가장자리에서 5), 네 귀 단조 꺾쇠. 9 조각
    (가장자리 14) 이라 가운데·변은 이어 붙여진다: 장식은 귀 조각 안에만, 촛불 기운과 테 색은 가로로 고르다.
    divider_at (GUI y) 면 그 줄에 이름 밑 금실 (왼쪽 끝 마름모는 왼쪽 조각 안).
    """
    W = H = TT * S
    img = Img(W, H)
    panel(img, 6, 6, W - 12, H - 12, alpha=0.92, glow=min(2 * top_border - 10, 22), uniform=True)
    frame(img, 6, 6, W - 12, H - 12, inset=4, inner=False, uniform=True)
    corners(img, 6, 6, W - 12, H - 12, inset=1, size=14)
    if divider_at is not None:
        y = 2 * divider_at
        for x in range(24, W - 24):
            d = W - 25 - x
            k = 1.0 if d >= 20 else (d + 1) / 21.0
            img.put(x, y, "parch1", 0.9 * k)
            img.put(x, y + 1, "ink0", 0.6 * k)
        m = Mask(W, 8)
        m.poly([(18.0, 4.0), (22.0, 0.6), (26.0, 4.0), (22.0, 7.4)])
        img.over(draw.lit(m.cov(), GOLD), 0, y - 4)
    return img


def write_all(pack):
    """그림과 .mcmeta 를 쓰고 쓴 경로 목록을 돌려준다."""
    out = []

    def save(img, *parts):
        p = gpath(pack, *parts)
        draw.save(img.image(), p)
        out.append(p)
        return p

    for name in ("inventory", "generic_54", "crafting_table"):
        save(container(name), "container", name + ".png")
    hud = ("sprites", "hud")
    save(hotbar(), *hud, "hotbar.png")
    save(selection(), *hud, "hotbar_selection.png")
    save(offhand(False), *hud, "hotbar_offhand_left.png")
    save(offhand(True), *hud, "hotbar_offhand_right.png")
    save(crosshair(), *hud, "crosshair.png")
    for st, fn in (("normal", "button"), ("highlighted", "button_highlighted"), ("disabled", "button_disabled")):
        p = save(button(st), "sprites", "widget", fn + ".png")
        mcmeta(p, BUTTON_SCALING)
    for hi in (False, True):
        sfx = "_highlighted" if hi else ""
        p = save(slider_track(hi), "sprites", "widget", "slider" + sfx + ".png")
        mcmeta(p, BUTTON_SCALING)
        p = save(slider_handle(hi), "sprites", "widget", "slider_handle" + sfx + ".png")
        mcmeta(p, {"type": "nine_slice", "width": 8, "height": 20, "border": {"left": 2, "top": 6, "right": 2, "bottom": 6}})
        save(checkbox(False, hi), "sprites", "widget", "checkbox" + sfx + ".png")
        save(checkbox(True, hi), "sprites", "widget", "checkbox_selected" + sfx + ".png")
        p = save(text_field(hi), "sprites", "widget", "text_field" + sfx + ".png")
        mcmeta(p, {"type": "nine_slice", "width": 200, "height": 20, "border": 1})
    for st, fn in (("normal", "warning_button"), ("highlighted", "warning_button_highlighted"),
                   ("disabled", "warning_button_disabled")):
        save(warning_button(st), "sprites", "dialog", fn + ".png")
    bg = tooltip_bg()
    p = save(bg, "sprites", "tooltip", "background.png")
    mcmeta(p, {"type": "nine_slice", "width": TT, "height": TT, "border": 14})
    empty = Img(TT * S, TT * S)
    p = save(empty, "sprites", "tooltip", "frame.png")
    mcmeta(p, {"type": "nine_slice", "width": TT, "height": TT, "border": 14})
    # 무기 칸 (플러그인 사본이 tooltip_style souls:gothic_weapon): 이름 (글 위 12) 밑 금실 (22.5)
    wb = tooltip_bg(divider_at=22, top_border=26)
    p = os.path.join(pack, "assets", "souls", "textures", "gui", "sprites", "tooltip", "gothic_weapon_background.png")
    draw.save(wb.image(), p)
    out.append(p)
    wmeta = {"type": "nine_slice", "width": TT, "height": TT, "border": {"left": 14, "right": 14, "top": 26, "bottom": 14}}
    mcmeta(p, wmeta)
    p2 = os.path.join(pack, "assets", "souls", "textures", "gui", "sprites", "tooltip", "gothic_weapon_frame.png")
    draw.save(empty.image(), p2)
    mcmeta(p2, wmeta)
    out.append(p2)
    # 게임 중 메뉴 뒤 (흐림 셰이더가 어둡게 한다) 와 머리·발 나눔줄
    mb = Img(32, 32)
    mb.fill(1.0, "ink0", 0.30)
    save(mb, "inworld_menu_background.png")
    for n in ("header_separator", "footer_separator", "inworld_header_separator", "inworld_footer_separator"):
        sep = Img(64, 4)
        sep.hline(0, 64, 0, "parch0", 0.85)
        sep.hline(0, 64, 1, "ink0", 0.5)
        save(sep, n + ".png")
    return out


# ─────────────────────────── 사망 화면 띠, 제목 금실, 설명 칸 실선 (글꼴 그림) ───────────────────────────

def death_band():
    """
    YOU DIED 뒤의 띠 (기본 팩 hud_death_band.png 를 2 배로, 공급자 높이 22 그대로라 진행 폭은 같다): 조각 셋 (왼쪽 끝, 가운데,
    오른쪽 끝) 칸 폭 128 텍셀. 먹 한 색에 알파 계단 (가운데 82%), 위·아래 안쪽에 반 픽셀 청동 실 (단추·창의 금실과 같은
    말), 양 끝 32 텍셀에서 옅어진다.
    """
    t, h = 128, 44
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
    return img


ORN_S = 2


def title_divider(width_gui=120):
    """창 제목 밑 금실 (GUI width×5): 가운데 단조 마름모, 양쪽으로 금실 (위 줄 길고, 아래 짧은 청동), 끝은 알파 계단."""
    W, H = width_gui * ORN_S, 5 * ORN_S
    img = Img(W, H)
    cx = W / 2.0
    for x in range(W):
        d = abs(x + 0.5 - cx) / cx
        if abs(x + 0.5 - cx) > 8:
            img.put(x, 4, "parch2" if d < 0.3 else "parch1", 0.95 * max(0.0, 1 - d ** 1.6))
            img.put(x, 5, "ink0", 0.5 * max(0.0, 1 - d ** 1.6))
        if 8 < abs(x + 0.5 - cx) < 60:
            img.put(x, 7, "bronze2", 0.8 * max(0.0, 1 - (abs(x + 0.5 - cx) - 8) / 52.0))
    m = Mask(W, H).poly([(cx - 7, 4.5), (cx, 0.0), (cx + 7, 4.5), (cx, 9.5)])
    hole = Mask(W, H).poly([(cx - 3, 4.5), (cx, 2.4), (cx + 3, 4.5), (cx, 6.6)])
    img.over(draw.lit(np.clip(m.cov() - hole.cov(), 0, 1), GOLD))
    img.fill(Mask(W, H).disc(cx, 4.5, 1.0).cov(), "glim0", 1.0)
    return img


def lore_rule(width_gui):
    """설명 칸의 수치와 설명 사이 실선 (GUI width×3): 왼쪽 끝 작은 마름모와 1 텍셀 청동 줄 (오른쪽으로 옅어진다)."""
    W, H = int(round(width_gui * ORN_S)), 4 * ORN_S
    img = Img(W, H)
    for x in range(8, W):
        d = (x - 8) / max(1.0, W - 8.0)
        img.put(x, 3, "bronze2", 0.85 * max(0.0, 1 - d) ** 0.7)
    m = Mask(W, H).poly([(0.5, 3.0), (3.5, 0.2), (6.5, 3.0), (3.5, 5.8)])
    img.over(draw.lit(m.cov(), GOLD))
    return img
