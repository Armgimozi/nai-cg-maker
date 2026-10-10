"""
mood2_refined 의 GUI 그림 (4배 해상도, 칸 자리는 바닐라와 픽셀까지 같게) 과 GUI 채우기 셰이더 (채팅 바탕).

모두 같은 말씨 (ornament.py): 반투명 먹 판, 두 겹 금빛 머리카락 선 (바깥 낡은 금빛, 안쪽 0.75 GUI 픽셀 안에 더 흐린 둘째 선),
귀와 끝에만 작은 마름모·덩굴. 칸은 테 대신 꺼진 먹 우물 (가장자리 1 텍셀 따뜻한 먹 선, 윗줄 그늘).

  단축 슬롯     182×22: 아홉 먹 우물 + 위·아래 가는 금빛 선 (양 끝으로 사라진다) + 양 끝 작은 마름모. 고른 칸은 금빛 머리카락 네모와
                네 귀의 작은 마름모, 바깥에 흐린 둘째 네모
  왼손 칸       같은 우물, 위·아래 짧은 선
  단추          띠 위의 글 (다크 소울 3 메뉴 줄): 위·아래 두 겹 선이 양 끝 6 GUI 에서 사라진다. 가리키면 따뜻한 띠, 밝은 선, 양 끝
                마름모와 덩굴. 꺼지면 재빛 선만
  밀대·체크 칸  같은 띠·두 겹 선. 손잡이는 먹 기둥에 금빛 테와 가운데 마름모. 체크 칸은 두 겹 네모, 고르면 가운데 금빛 마름모
  설명 칸       92% 먹 판, 두 겹 금빛 테, 네 귀 마름모와 짧은 밝은 팔
  창            판 (가장자리가 조금 진한 비네트), 두 겹 테, 네 귀 장식, 위 가운데 마름모, 칸 우물, 결과 칸 금빛 테, 제작 화살표,
                나눔줄, 창 제목 밑 짧은 선
  나눔줄        설정 화면의 머리·발 줄: 금빛 머리카락 선과 그 밑 그늘
  채팅 바탕     gui.vsh: 채팅 줄의 검은 바탕 (바닐라 0x7F000000 / 0x80000000) 을 따뜻한 먹으로, 오른쪽으로 갈수록 옅게.
                시스템 글 표시 띠 (회색 2 GUI) 는 흐린 금빛 머리카락 선으로
  사망 화면 막  gui.vsh: 바닐라의 붉은 막 (0x60500000 → 0xA0803030) 을 붉은 기 없는 먹 막으로 (다크 소울의 사망 화면처럼 세상이
                가라앉고, 붉은 것은 YOU DIED 뿐)
"""
import json
import math
import os

from PIL import Image

import ornament as orn
import palette
from ornament import Canvas, RES

GUI = ("assets", "minecraft", "textures", "gui")
INK = "ash0"
WELL = "ink0"


def _path(pack, *parts):
    p = os.path.join(pack, *GUI, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def save(img, pack, *parts):
    img.save(_path(pack, *parts))


def save_mcmeta(pack, scaling, *parts):
    with open(_path(pack, *parts) + ".mcmeta", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"gui": {"scaling": scaling}}, f, indent=2)
        f.write("\n")


def T(n):
    """GUI 픽셀 → 텍셀."""
    return int(round(n * RES))


# ─────────────────────────── 칸 우물 ───────────────────────────

def well(cv, x, y, w=18, h=18, floor=(WELL, 200), edge=("ink1", 255), shade=(WELL, 245)):
    """바닐라 칸 상자 (x, y, w×h GUI) 안의 우물: 속 (x+1..x+w-2) 이 꼭 아이템 자리. 가장자리 1 텍셀 따뜻한 먹 선, 윗줄·왼줄 그늘."""
    x0, y0, x1, y1 = T(x + 1), T(y + 1), T(x + w - 1) - 1, T(y + h - 1) - 1
    cv.rect(x0, y0, x1, y1, floor)
    cv.hline(x0 + 1, x1 - 1, y0 + 1, shade)
    cv.vline(x0 + 1, y0 + 2, y1 - 1, shade)
    cv.box(x0, y0, x1, y1, edge)


# ─────────────────────────── 단축 슬롯 ───────────────────────────

def hotbar():
    W, H = 182, 22
    cv = Canvas(T(W), T(H))
    for k in range(9):
        x = 2 + 20 * k
        x0, y0, x1, y1 = T(x + 1), T(3), T(x + 17) - 1, T(19) - 1
        cv.rect(x0, y0, x1, y1, (WELL, 120))
        cv.hline(x0, x1, y0, (WELL, 175))
        cv.vline(x0, y0 + 1, y1, (WELL, 160))
        cv.box(x0 - 1, y0 - 1, x1 + 1, y1 + 1, ("ink1", 150))
    # 위·아래 가는 금빛 선 (텍셀 4, 83), 양 끝 마름모 (세로 가운데)
    cv.hline(T(4), T(W - 4) - 1, 3, orn.GOLD, fade=(T(18), T(18)))
    cv.hline(T(4), T(W - 4) - 1, T(H) - 4, orn.GOLD, fade=(T(18), T(18)))
    cy = T(H) // 2 - 1
    cv.lozenge(4, cy, 2)
    cv.lozenge(T(W) - 5, cy, 2)
    return cv.image()


def hotbar_selection():
    """24×23: 고른 칸의 아이템 자리 (4..19) 바로 바깥 텍셀에 금빛 네모, 네 귀 작은 마름모, 바깥 3 텍셀에 흐린 둘째 네모."""
    cv = Canvas(T(24), T(23))
    a, b = T(4) - 1, T(20)
    cv.box(a - 3, a - 3, b + 3, b + 3, (orn.GOLD_SOFT[0], 140))
    cv.box(a, a, b, b, orn.GOLD_PALE)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        cv.lozenge(x, y, 2)
    return cv.image()


def offhand(right):
    """29×24: 칸 상자 (x0+2, 3) 18×18, 아이템 (x0+3, 4)."""
    cv = Canvas(T(29), T(24))
    x = 7 if right else 0
    x0, y0, x1, y1 = T(x + 3), T(4), T(x + 19) - 1, T(20) - 1
    cv.rect(x0, y0, x1, y1, (WELL, 120))
    cv.hline(x0, x1, y0, (WELL, 175))
    cv.vline(x0, y0 + 1, y1, (WELL, 160))
    cv.box(x0 - 1, y0 - 1, x1 + 1, y1 + 1, ("ink1", 150))
    cv.hline(x0 - 4, x1 + 4, y0 - 5, orn.GOLD_SOFT, fade=(10, 10))
    cv.hline(x0 - 4, x1 + 4, y1 + 5, orn.GOLD_SOFT, fade=(10, 10))
    return cv.image()


# ─────────────────────────── 단추·밀대·체크 칸 ───────────────────────────

BUTTON_BORDER = {"left": 6, "top": 3, "right": 6, "bottom": 3}
BUTTON_SCALING = {"type": "nine_slice", "width": 200, "height": 20, "border": BUTTON_BORDER}
END = T(6)                        # 양 끝 옅어지는 텍셀 (9조각의 양옆 조각 안)

TONES = {
    #               띠 (색, 알파)        바깥 선                 안쪽 선                마름모
    "normal":      ((INK, 70),         ("bronze2", 170),        ("bronze1", 120),     False),
    "highlighted": (("bronze0", 120),  ("parch2", 235),         ("bronze3", 170),     True),
    "disabled":    ((INK, 40),         ("ash2", 90),            ("ash1", 70),         False),
}


def band(W, H, tone, band_rows=None):
    """W×H GUI 띠 (단추·밀대 길): 위 바깥 선 텍셀 4, 안쪽 선 7, 아래 안쪽 선 H*4-8, 바깥 선 H*4-5. 양 끝 END 텍셀에서 옅어진다."""
    (fc, fa), outer, inner, gem = tone
    w, h = T(W), T(H)
    cv = Canvas(w, h)
    r0, r1 = band_rows or (T(1) + 4, h - T(1) - 5)
    for x in range(w):
        d = min(x, w - 1 - x)
        k = 1.0 if d >= END else (d + 1) / (END + 1)
        for y in range(r0, r1 + 1):
            cv.put(x, y, (fc, fa * k))
    for y, c in ((4, outer), (7, inner), (h - 8, inner), (h - 5, outer)):
        cv.hline(0, w - 1, y, c, fade=(END, END))
    if gem:
        cy = h // 2 - 1
        for gx, out in ((9, -1), (w - 10, 1)):
            cv.lozenge(gx, cy, 3)
            cv.whisker(gx - out * 4, cy, -out, 7, orn.GOLD_PALE)
            cv.whisker(gx + out * 4, cy, out, 4, orn.GOLD_SOFT)
    return cv


def button(state):
    return band(200, 20, TONES[state]).image()


SLIDER_SCALING = {"type": "nine_slice", "width": 200, "height": 20, "border": {"left": 6, "top": 3, "right": 6, "bottom": 3}}
HANDLE_SCALING = {"type": "nine_slice", "width": 8, "height": 20, "border": 2}


def slider_track(hi):
    tone = ((WELL, 110), ("parch2", 210) if hi else ("bronze2", 160), ("bronze1", 120), False)
    return band(200, 20, tone).image()


def slider_handle(hi):
    cv = Canvas(T(8), T(20))
    w, h = T(8), T(20)
    cv.rect(4, 4, w - 5, h - 5, (WELL, 225))
    edge = orn.GOLD_HI if hi else orn.GOLD_PALE
    cv.box(4, 4, w - 5, h - 5, edge)
    cv.box(6, 6, w - 7, h - 7, (orn.GOLD_SOFT[0], 110))
    cv.lozenge(w // 2 - 1, h // 2 - 1, 2)
    return cv.image()


def checkbox(selected, hi):
    cv = Canvas(T(20), T(20))
    n = T(20)
    cv.rect(4, 4, n - 5, n - 5, (INK, 185))
    cv.box(4, 4, n - 5, n - 5, orn.GOLD_HI if hi else orn.GOLD)
    cv.box(7, 7, n - 8, n - 8, (orn.GOLD_SOFT[0], 120))
    if selected:
        c = n // 2 - 1
        cv.lozenge(c, c, 18, edge=orn.GOLD_HI if hi else orn.GOLD_PALE, core=("bronze3", 255), hi=None)
        cv.lozenge(c, c, 8, edge=("bronze2", 255), core=("parch3", 255), hi=None)
    return cv.image()


TEXT_FIELD_SCALING = {"type": "nine_slice", "width": 200, "height": 20, "border": 1}


def text_field(hi):
    cv = Canvas(T(200), T(20))
    w, h = T(200), T(20)
    cv.rect(0, 0, w - 1, h - 1, (INK, 228))
    cv.box(0, 0, w - 1, h - 1, orn.GOLD if hi else ("bronze1", 220))
    return cv.image()


SEPARATORS = ("header_separator", "footer_separator", "inworld_header_separator", "inworld_footer_separator")


def separator():
    cv = Canvas(T(32), T(2))
    cv.hline(0, T(32) - 1, 3, orn.GOLD)
    cv.hline(0, T(32) - 1, 4, (WELL, 120))
    cv.hline(0, T(32) - 1, 5, (WELL, 60))
    return cv.image()


# ─────────────────────────── 작은 네모 단추 (Dialog 경고, 제작법 책) ───────────────────────────

SQUARE = {
    #               바탕 (색, 알파)      바깥 선               안쪽 선                     표식
    "normal":      ((INK, 170),        orn.GOLD,             ("bronze1", 120),           orn.GOLD_PALE),
    "highlighted": (("bronze0", 200),  orn.GOLD_HI,          ("bronze3", 170),           orn.GOLD_HI),
    "disabled":    ((INK, 110),        ("ash2", 200),        ("ash1", 110),              ("ash2", 255)),
}


def square(w, h, state):
    (fc, fa), outer, inner, mark = SQUARE[state]
    W, H = T(w), T(h)
    cv = Canvas(W, H)
    cv.rect(1, 1, W - 2, H - 2, (fc, fa))
    cv.box(1, 1, W - 2, H - 2, outer)
    cv.box(4, 4, W - 5, H - 5, inner)
    return cv, mark


def warning_button(state):
    """20×20: 두 겹 테의 네모 안에 가늘게 다듬은 "!" (위가 조금 굵은 획 + 아래 마름모 점)."""
    cv, mark = square(20, 20, state)
    c = T(20) // 2 - 1
    for y in range(16, 50):
        half = 2 if y < 34 else 1
        for x in range(c - half + 1, c + half + 1):
            cv.put(x, y, mark)
    cv.lozenge(c, 60, 3, edge=mark, core=mark, hi=None)
    return cv.image()


def recipe_button(hi):
    """20×18: 같은 네모 안에 펼친 책 (금빛 머리카락 선)."""
    cv, mark = square(20, 18, "highlighted" if hi else "normal")
    x0, x1, y0, y1 = 18, 61, 18, 53
    cx = (x0 + x1) // 2
    for x in range(x0, x1 + 1):
        sag = 2 if abs(x - cx) < 4 else (1 if abs(x - cx) < 10 else 0)
        cv.put(x, y0 + sag, mark)
        cv.put(x, y1 - 2 + sag, mark)
    cv.vline(x0, y0, y1 - 2, mark)
    cv.vline(x1, y0, y1 - 2, mark)
    cv.vline(cx, y0 + 2, y1, mark)
    for y in (26, 32, 38):
        cv.hline(x0 + 5, cx - 5, y, (mark[0], 150))
        cv.hline(cx + 5, x1 - 5, y, (mark[0], 150))
    return cv.image()


# ─────────────────────────── 칸 가리킴 ───────────────────────────

SLOT_HIGHLIGHT_SCALING = {"type": "nine_slice", "width": 24, "height": 24, "border": 4}


def slot_highlight():
    """24×24 (아이템 자리 4..19). 뒤: 칸 속이 옅은 금빛으로 데워진다. 앞: 아이템 자리 바로 바깥 텍셀에 밝은 금빛 네모와 네 귀 점."""
    back, front = Canvas(T(24), T(24)), Canvas(T(24), T(24))
    back.rect(T(4), T(4), T(20) - 1, T(20) - 1, ("parch0", 60))
    a, b = T(4) - 1, T(20)
    front.box(a, a, b, b, orn.GOLD_HI)
    for x, y in ((a, a), (b, a), (a, b), (b, b)):
        front.lozenge(x, y, 1, edge=orn.GOLD_HI, core=None, hi=None)
    return back.image(), front.image()


# ─────────────────────────── 설명 칸 ───────────────────────────

TOOLTIP_SCALING = {
    "background": {"type": "nine_slice", "width": 100, "height": 100, "border": 9},
    "frame": {"type": "nine_slice", "width": 100, "height": 100, "border": 10, "stretch_inner": True},
}


def tooltip():
    """바닐라는 글 둘레 12 GUI 밖에 그린다. 바탕 3..96 (92% 먹, 가장자리 두 텍셀 옅게), 테: 바깥 선 텍셀 20 (GUI 5), 안쪽 선 23."""
    N = T(100)
    bg = Canvas(N, N)
    a0, a1 = T(3), N - T(3) - 1
    for y in range(a0, a1 + 1):
        for x in range(a0, a1 + 1):
            d = min(x - a0, y - a0, a1 - x, a1 - y)
            bg.put(x, y, (INK, (110, 180)[d] if d < 2 else 236))
    fr = Canvas(N, N)
    o0, o1 = T(5), N - T(5) - 1
    fr.box(o0, o0, o1, o1, orn.GOLD)
    fr.box(o0 + 3, o0 + 3, o1 - 3, o1 - 3, (orn.GOLD_SOFT[0], 110))
    for x, y, sx, sy in ((o0, o0, 1, 1), (o1, o0, -1, 1), (o0, o1, 1, -1), (o1, o1, -1, -1)):
        fr.corner(x, y, sx, sy, arm=14, gem=0)
        fr.lozenge(x, y, 3)
    return bg.image(), fr.image()


# ─────────────────────────── 창 ───────────────────────────

def _grid(x0, y0, cols, rows):
    return [(x0 + 18 * i, y0 + 18 * j) for j in range(rows) for i in range(cols)]


LAYOUTS = {
    "inventory": {
        "size": (176, 166),
        "wells": [(7, 7 + 18 * i) for i in range(4)] + [(76, 61)] + _grid(97, 17, 2, 2)
                 + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(153, 27, 18, 18)],
        "alcove": (25, 7, 51, 72),
        "arrow": (135, 150, 35, 6),
        "titles": [(97, 6, 64)],
        "dividers": [(7, 169, 80), (7, 169, 138)],
        "split": None,
    },
    "crafting_table": {
        "size": (176, 166),
        "wells": _grid(29, 16, 3, 3) + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(119, 30, 26, 26)],
        "alcove": None,
        "arrow": (90, 111, 42, 7),
        "titles": [(29, 6, 84), (8, 72, 70)],
        "dividers": [(7, 169, 138)],
        "split": None,
    },
    "generic_54": {
        "size": (176, 222),
        "wells": _grid(7, 17, 9, 6) + _grid(7, 139, 9, 3) + _grid(7, 197, 9, 1),
        "result": [],
        "alcove": None,
        "arrow": None,
        "titles": [(8, 6, 84), (8, 129, 70)],
        "dividers": [(7, 169, 194)],
        "split": 126,           # 바닐라가 위 (0..17+줄×18) 와 아래 (126..) 를 따로 그려 붙인다
    },
}
TITLE_RULE_DY = 10              # 제목 줄 위에서 선까지 (GUI): 명조 글자 아래 (줄 위 + 7.3) 와 칸 (줄 위 + 11) 사이


def panel_alpha(x, y, w, h, split=None):
    """판 몸 알파 (가장자리로 갈수록 조금 진하게). 위아래는 가장자리 20 GUI 안에서만 (상자 창의 이음매가 보이지 않게)."""
    dx = abs(x - w / 2) / (w / 2)
    ty = min(y, h - y)
    if split:
        ty = min(ty, abs(y - split) + 40)
    ey = max(0.0, 1 - ty / 22)
    r = min(1.0, max(dx ** 2.2, ey ** 1.6))
    return 168 + (214 - 168) * r


def container(name):
    L = LAYOUTS[name]
    w, h = L["size"]
    cv = Canvas(T(256), T(256))
    W, H = T(w), T(h)
    split = L["split"]
    # 1. 판 (가장자리 6 텍셀은 알파 계단으로 옅어진다)
    for y in range(H):
        for x in range(W):
            d = min(x, y, W - 1 - x, H - 1 - y)
            if split:
                pass
            k = 1.0 if d >= 6 else (d + 1) / 7
            gx, gy = (x + 0.5) / RES, (y + 0.5) / RES
            cv.put(x, y, (INK, panel_alpha(gx, gy, w, h, split) * k))
    # 2. 두 겹 테 (바깥 텍셀 8, 안쪽 11)
    for inset, c in ((8, orn.GOLD), (11, (orn.GOLD_SOFT[0], 105))):
        cv.box(inset, inset, W - 1 - inset, H - 1 - inset, c)
    # 3. 네 귀, 위 가운데 마름모 (상자 창은 아래 판의 위쪽 귀도: 바닐라가 위 판을 줄 수에 맞춰 잘라 붙인다)
    for x, y, sx, sy in ((8, 8, 1, 1), (W - 9, 8, -1, 1), (8, H - 9, 1, -1), (W - 9, H - 9, -1, -1)):
        cv.corner(x, y, sx, sy, arm=30, gem=0)
        # 귀 안쪽 둘째 선의 꺾쇠도 밝게, 귀 대각선 안쪽에 작은 점
        for i in range(14):
            cv.put(x + sx * (3 + i), y + sy * 3, (orn.GOLD_PALE[0], 200 * (1 - i / 14)))
            cv.put(x + sx * 3, y + sy * (3 + i), (orn.GOLD_PALE[0], 200 * (1 - i / 14)))
        cv.lozenge(x, y, 4)
        cv.lozenge(x + sx * 7, y + sy * 7, 1, edge=orn.GOLD_PALE, core=None, hi=None)
    cv.terminal(W // 2 - 1, 8, r=5, arm=28)
    cv.lozenge(W // 2 - 1 - 36, 8, 1, edge=orn.GOLD_PALE, core=None, hi=None)
    cv.lozenge(W // 2 - 1 + 36, 8, 1, edge=orn.GOLD_PALE, core=None, hi=None)
    # 4. 인물 자리, 칸, 결과 칸
    if L["alcove"]:
        x, y, aw, ah = L["alcove"]
        well(cv, x, y, aw, ah, floor=(WELL, 222))
    for x, y in L["wells"]:
        well(cv, x, y)
    for x, y, rw, rh in L["result"]:
        well(cv, x, y, rw, rh, edge=orn.GOLD)
        x0, y0, x1, y1 = T(x + 1), T(y + 1), T(x + rw - 1) - 1, T(y + rh - 1) - 1
        cv.box(x0 - 2, y0 - 2, x1 + 2, y1 + 2, (orn.GOLD_SOFT[0], 120))
    # 5. 제작 화살표: 금빛 머리카락 자루, 꼬리는 옅게, 촉은 두 갈래 45° (끝에 밝은 점)
    if L["arrow"]:
        x0, x1, ym, half = L["arrow"]
        X0, X1, Y = T(x0), T(x1 + 1) - 1, T(ym) + 1
        cv.hline(X0, X1 - 1, Y, orn.GOLD, fade=(10, 0))
        for k in range(1, T(half)):
            c = orn.GOLD_PALE if k < T(half) - 3 else orn.GOLD
            cv.put(X1 - k, Y - k, c)
            cv.put(X1 - k, Y + k, c)
        cv.put(X1, Y, orn.GOLD_HI)
    # 6. 나눔줄 (양 끝으로 사라지는 머리카락 선, 가운데 작은 마름모)
    for x0, x1, y in L["dividers"]:
        Y = T(y) + 1
        cv.hline(T(x0), T(x1) - 1, Y, (orn.GOLD_SOFT[0], 170), fade=(40, 40))
        cv.lozenge((T(x0) + T(x1)) // 2, Y, 2)
    # 7. 창 제목 밑 짧은 선 (왼쪽 끝 작은 마름모, 오른쪽으로 사라진다)
    for tx, ty, rw in L["titles"]:
        Y = T(ty + TITLE_RULE_DY) + 3
        cv.hline(T(tx) + 4, T(tx + rw), Y, orn.GOLD, fade=(0, T(rw) - 12))
        cv.lozenge(T(tx) + 1, Y, 2)
    return cv.image()


# ─────────────────────────── 채팅 바탕 셰이더 ───────────────────────────

GUI_VSH = """#version 330

// Block Soul mood2_refined: vanilla gui.vsh plus one block. The chat's black line backgrounds (and the chat input
// box: vanilla fills 0x7F000000 / 0x80000000) become warm ink that fades out towards the right, like a DS3 message band.
// Can't moj_import in things used during startup, when resource packs don't exist.
layout(std140) uniform DynamicTransforms {{
    mat4 ModelViewMat;
    vec4 ColorModulator;
    vec3 ModelOffset;
    mat4 TextureMat;
}};
layout(std140) uniform Projection {{
    mat4 ProjMat;
}};

in vec3 Position;
in vec4 Color;

out vec4 vertexColor;

void main() {{
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);

    vertexColor = Color;
    ivec4 c = ivec4(Color * 255.0 + 0.5);
    if (c.r == 0 && c.g == 0 && c.b == 0 && (c.a == 127 || c.a == 128) && ProjMat[3][3] == 1.0) {{
        float x = (ModelViewMat * vec4(Position, 1.0)).x;
        float k = clamp(1.12 - x / 300.0, 0.12, 1.0);
        vertexColor = vec4({ink}, Color.a * 1.25 * k);
    }}
    // the death screen's red veil (vanilla gradient 0x60500000 -> 0xA0803030) -> a neutral ink veil, darker below
    if (c.r == 80 && c.g == 0 && c.b == 0 && c.a == 96 && ProjMat[3][3] == 1.0) vertexColor = vec4({ink}, 0.34);
    if (c.r == 128 && c.g == 48 && c.b == 48 && c.a == 160 && ProjMat[3][3] == 1.0) vertexColor = vec4({ink}, 0.66);
    // the chat's grey "system message" tag (0xFFD0D0D0, 2 GUI px wide) -> a dim gold hairline (right edge pulled in)
    if (c.r == 208 && c.g == 208 && c.b == 208 && c.a == 255 && ProjMat[3][3] == 1.0) {{
        vertexColor = vec4({tag}, 0.85);
        if (gl_VertexID % 4 >= 2) gl_Position.x -= 1.5 * ProjMat[0][0];
    }}
}}
"""


def write_shaders(pack):
    r, g, b, _ = palette.c("ink0")
    core = os.path.join(pack, "assets", "minecraft", "shaders", "core")
    os.makedirs(core, exist_ok=True)
    with open(os.path.join(core, "gui.vsh"), "w", encoding="ascii", newline="\n") as f:
        t = palette.c("bronze2")
        f.write(GUI_VSH.format(ink="%.4f, %.4f, %.4f" % (r / 255, g / 255, b / 255),
                               tag="%.4f, %.4f, %.4f" % (t[0] / 255, t[1] / 255, t[2] / 255)))


# ─────────────────────────── 빌드 ───────────────────────────

def build(pack):
    hud = ("sprites", "hud")
    save(hotbar(), pack, *hud, "hotbar.png")
    save(hotbar_selection(), pack, *hud, "hotbar_selection.png")
    save(offhand(False), pack, *hud, "hotbar_offhand_left.png")
    save(offhand(True), pack, *hud, "hotbar_offhand_right.png")
    for state, fname in (("normal", "button"), ("highlighted", "button_highlighted"), ("disabled", "button_disabled")):
        save(button(state), pack, "sprites", "widget", fname + ".png")
        save_mcmeta(pack, BUTTON_SCALING, "sprites", "widget", fname + ".png")
    for hi in (False, True):
        sfx = "_highlighted" if hi else ""
        save(slider_track(hi), pack, "sprites", "widget", "slider" + sfx + ".png")
        save_mcmeta(pack, SLIDER_SCALING, "sprites", "widget", "slider" + sfx + ".png")
        save(slider_handle(hi), pack, "sprites", "widget", "slider_handle" + sfx + ".png")
        save_mcmeta(pack, HANDLE_SCALING, "sprites", "widget", "slider_handle" + sfx + ".png")
        save(checkbox(False, hi), pack, "sprites", "widget", "checkbox" + sfx + ".png")
        save(checkbox(True, hi), pack, "sprites", "widget", "checkbox_selected" + sfx + ".png")
        save(text_field(hi), pack, "sprites", "widget", "text_field" + sfx + ".png")
        save_mcmeta(pack, TEXT_FIELD_SCALING, "sprites", "widget", "text_field" + sfx + ".png")
    hb, hf = slot_highlight()
    for img, n in ((hb, "slot_highlight_back"), (hf, "slot_highlight_front")):
        save(img, pack, "sprites", "container", n + ".png")
        save_mcmeta(pack, SLOT_HIGHLIGHT_SCALING, "sprites", "container", n + ".png")
    tbg, tfr = tooltip()
    save(tbg, pack, "sprites", "tooltip", "background.png")
    save(tfr, pack, "sprites", "tooltip", "frame.png")
    for n in ("background", "frame"):
        save_mcmeta(pack, TOOLTIP_SCALING[n], "sprites", "tooltip", n + ".png")
    for name in LAYOUTS:
        save(container(name), pack, "container", name + ".png")
    for n in SEPARATORS:
        save(separator(), pack, n + ".png")
    for state, fname in (("normal", "warning_button"), ("highlighted", "warning_button_highlighted"),
                         ("disabled", "warning_button_disabled")):
        save(warning_button(state), pack, "sprites", "dialog", fname + ".png")
    save(recipe_button(False), pack, "sprites", "recipe_book", "button.png")
    save(recipe_button(True), pack, "sprites", "recipe_book", "button_highlighted.png")
