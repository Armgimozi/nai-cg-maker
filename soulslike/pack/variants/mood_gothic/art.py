"""
mood_gothic 의 그림 (기본 팩 그림 위에 덧입힌다). 색은 팔레트 (pack/palette.py) 에서 고르고, 빛이 떨어지는 결은 그 색 사이를
GUI 한 픽셀 단위로 옮겨 간다 (부드러운 에어브러시가 아니라 한 줄씩 어두워지는 계단).

  빛의 규칙: 모든 판은 위에서 촛불 하나가 비춘다. 판의 윗날만 따뜻하게 밝고 (그을린 청동 → 먹), 금빛 테는 위쪽 가운데가
  가장 밝고 (옅은 금빛 흰색) 아래로 갈수록 녹슨 철빛으로 꺼진다. 아랫날은 거의 어둠에 묻힌다.

  container/*.png           기본 팩의 창 그림을 다시 비춘다: 판 → 검은 옻칠 (더 진하게, 따뜻한 먹), 윗날의 촛불 기운,
                            금빛 줄·장식은 높이와 가운데에서의 거리로 밝기를 옮긴다. 칸의 자리·크기는 그대로.
  sprites/tooltip/          설명 칸: 옻칠 판, 위에서 비친 테 (윗줄 밝게, 옆줄 흐리게, 아랫줄 어둡게), 위 두 귀에만 작은 꺾쇠.
  souls:tooltip/gothic_weapon_*
                            무기 설명 칸 (플러그인 사본이 tooltip_style 로 고른다): 위와 같고, 이름 줄 밑 (글 위에서 10) 에
                            금실 한 줄 (양 끝은 마름모와 알파 계단). 이름이 늘 첫 줄이라 칸 그림이 금실 자리를 안다.
  sprites/widget/button*    단추: 어두운 띠 + 위·아래 가는 줄. 가리키면 위에서 촛불이 비친 띠 (윗줄 금빛, 띠 윗부분이 따뜻하게).
  inworld_menu_background   흐림 셰이더 (shaders.py) 가 어둡게 하므로 아주 옅게.
  misc/vignette.png         게임 화면의 비네트를 무겁게 (바닐라는 어두운 곳에서 진해지는 그 값에 곱한다).
  souls:font/gothic_orn.png 기본 글꼴의 장식 글자 (개인 영역): 창 제목 밑 금실 (lang.py 가 제목 글 뒤에 붙인다).
"""
import math
import os

import numpy as np
from PIL import Image

from palette import c

GUI = ("assets", "minecraft", "textures", "gui")


def rgb(name):
    return np.array(c(name)[:3], dtype=np.float64)


def save(img, *parts):
    path = os.path.join(*parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def to_img(arr):
    a = np.clip(np.rint(arr), 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def ramp(stops, t):
    """stops = [(t, rgb)], t 를 그 사이에서 고른다 (계단 없이 사이 값, 끝은 붙든다)."""
    if t <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return c0 + (c1 - c0) * k
    return stops[-1][1]


# 금빛 테가 받는 빛: 1 = 그 색 그대로. 위 가운데가 가장 밝다
LINE_STOPS = [(0.0, rgb("glim0")), (0.22, rgb("parch3")), (0.42, rgb("parch2")), (0.62, rgb("parch1")),
              (0.80, rgb("parch0")), (1.0, rgb("rust1"))]
LACQUER = (rgb("ink0") * 0.55 + rgb("rust0") * 0.45)        # 검은 옻칠 (따뜻한 먹)
CANDLE = [(0.0, rgb("bronze1")), (0.35, rgb("bronze0")), (0.7, rgb("rust0")), (1.0, LACQUER)]


def light(x, y, w, h):
    """판 안 (x, y) 가 받는 빛 0 (가장 밝다) .. 1 (어둠). 위에서, 가운데에서 멀수록 어둡다."""
    ty = y / max(h, 1)
    dx = abs(x - w / 2) / max(w / 2, 1)
    return min(1.0, 0.08 + 0.95 * ty ** 0.8 + 0.22 * dx ** 2)


# ─────────────────────────── 창 그림 다시 비추기 ───────────────────────────

def relight_container(img):
    """기본 팩 창 그림: 판 (재빛 반투명) → 옻칠, 금빛 줄·장식 → 위에서 받은 빛, 칸 테 → 조금."""
    a = np.array(img.convert("RGBA"), dtype=np.float64)
    h0, w0 = a.shape[:2]
    alpha = a[..., 3]
    ys, xs = np.nonzero(alpha)
    if len(ys) == 0:
        return img
    top, bot, left, right = ys.min(), ys.max(), xs.min(), xs.max()
    W, H = right - left + 1, bot - top + 1
    panel = tuple(c("ash0")[:3])
    well = tuple(c("ink0")[:3])
    edge = tuple(c("ink1")[:3])
    golds = {tuple(c(n)[:3]) for n in ("parch0", "parch1", "parch2", "parch3", "bronze3", "bronze2")}
    out = a.copy()
    for y in range(top, bot + 1):
        for x in range(left, right + 1):
            px = tuple(int(v) for v in a[y, x, :3])
            al = a[y, x, 3]
            if al == 0:
                continue
            yy, xx = y - top, x - left
            if px == panel:
                k = min(1.0, yy / 15.0)
                col = ramp(CANDLE, k + 0.12 * (abs(xx - W / 2) / (W / 2)) ** 2)
                out[y, x, :3] = col
                # 옻칠: 더 진하게 (가장자리 알파 계단은 비율 그대로)
                out[y, x, 3] = min(255.0, al * (222.0 / 185.0)) if al >= 150 else al * 1.15
            elif px in golds:
                lum = sum(px) / (3 * 255.0)
                base = light(xx, yy, W, H)
                # 원래 밝은 장식 (꺾쇠·마름모) 은 한 단 더 밝게 남긴다
                t = max(0.0, base - (lum - 0.42) * 0.9)
                out[y, x, :3] = ramp(LINE_STOPS, t)
            elif px == edge:
                t = light(xx, yy, W, H)
                out[y, x, :3] = rgb("ink1") * (1.15 - 0.35 * t) + rgb("bronze0") * 0.0
            elif px == well:
                out[y, x, 3] = min(255.0, al * 1.08)
    return to_img(out)


# ─────────────────────────── 설명 칸 ───────────────────────────

def _panel(w, h, inset, top_border, divider_at=None):
    """
    설명 칸 한 장 (w×h, 아홉 조각으로 늘어난다). inset = 판 가장자리 (그림 가장자리에서). 글은 12 안쪽.
    top_border 는 조각 경계 (윗날 조각의 높이): 그 아래 가운데 줄이 이어 붙여지므로 촛불 기운은 그 안에서 끝난다.
    divider_at = 금실 줄 (그림 y). 글 첫 줄 (이름) 밑.
    """
    a = np.zeros((h, w, 4))
    x0, y0, x1, y1 = inset, inset, w - 1 - inset, h - 1 - inset
    glow_rows = max(4, min(top_border - inset - 1, 12))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            yy = y - y0
            k = min(1.0, yy / glow_rows)
            col = ramp(CANDLE, k)
            al = 248.0
            # 가장자리 두 줄은 알파 계단으로 (판이 흐린 세상 위에 떠 보이게)
            d = min(x - x0, x1 - x, y - y0, y1 - y)
            if d == 0:
                al = 150.0
            elif d == 1:
                al = 205.0
            a[y, x, :3] = col
            a[y, x, 3] = al
    # 테: 판 가장자리에서 2 안쪽
    fx0, fy0, fx1, fy1 = x0 + 2, y0 + 2, x1 - 2, y1 - 2
    top_col = ramp(LINE_STOPS, 0.30)
    side_col = ramp(LINE_STOPS, 0.78)
    bot_col = ramp(LINE_STOPS, 0.98)
    for x in range(fx0, fx1 + 1):
        a[fy0, x, :3], a[fy0, x, 3] = top_col, 255
        a[fy1, x, :3], a[fy1, x, 3] = bot_col, 200
    for y in range(fy0 + 1, fy1):
        # 옆줄: 윗귀 조각 안에서 위 → 옆 색으로, 아랫귀 조각 안에서 옆 → 아래 색으로 옮겨 간다
        if y < top_border:
            t = (y - fy0) / max(top_border - fy0, 1)
            col, al = top_col + (side_col - top_col) * t, 255 - 40 * t
        elif y >= h - 12:
            t = (y - (h - 12)) / max(fy1 - (h - 12), 1)
            col, al = side_col + (bot_col - side_col) * t, 215 - 15 * t
        else:
            col, al = side_col, 215
        for x in (fx0, fx1):
            a[y, x, :3], a[y, x, 3] = col, al
    # 위 두 귀: 작은 꺾쇠 (밝은 금빛) 와 바깥의 점
    glim, p3 = rgb("glim0"), rgb("parch3")
    for cx, sx in ((fx0, 1), (fx1, -1)):
        for i in range(4):
            a[fy0, cx + sx * i, :3], a[fy0, cx + sx * i, 3] = (glim if i < 2 else p3), 255
        for i in range(1, 3):
            a[fy0 + i, cx, :3], a[fy0 + i, cx, 3] = p3, 255
        a[fy0 - 2, cx - sx * 0, :3], a[fy0 - 2, cx, 3] = p3, 120
    if divider_at is not None:
        _divider_row(a, divider_at, fx0 + 2, fx1 - 2)
    return to_img(a)


def _divider_row(a, y, x0, x1):
    """금실: 양 끝의 작은 마름모, 그 사이 1 픽셀 줄 (끝 6 픽셀은 알파 계단), 밑에 반투명 먹 그늘 한 줄."""
    line = ramp(LINE_STOPS, 0.34)
    dark = rgb("ink0")
    n = x1 - x0
    for x in range(x0 + 3, x1 - 2):
        d = min(x - (x0 + 3), (x1 - 3) - x)
        al = 235 if d >= 6 else 70 + 27 * d
        a[y, x, :3], a[y, x, 3] = line, al
        a[y + 1, x, :3], a[y + 1, x, 3] = dark, 150
    for cx in (x0 + 1, x1 - 1):
        for dx, dy, col in ((0, -1, rgb("parch2")), (-1, 0, rgb("parch2")), (1, 0, rgb("parch2")), (0, 1, rgb("parch1")),
                            (0, 0, rgb("glim0"))):
            a[y + dy, cx + dx, :3], a[y + dy, cx + dx, 3] = col, 255
    return n


TOOLTIP = {"w": 64, "h": 64, "inset": 5}
WEAPON_TOP = 26                         # 무기 설명 칸의 윗날 조각 높이 (금실 줄 22 를 품는다)


def tooltips(pack):
    w, h, inset = TOOLTIP["w"], TOOLTIP["h"], TOOLTIP["inset"]
    out = []
    empty = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # 기본: 아홉 조각 (윗날 12)
    bg = _panel(w, h, inset, 12)
    meta = {"gui": {"scaling": {"type": "nine_slice", "width": w, "height": h, "border": 12}}}
    for ns, name in (("minecraft", "tooltip/background"), ("minecraft", "tooltip/frame")):
        img = bg if name.endswith("background") else empty
        p = save(img, pack, "assets", ns, "textures", "gui", "sprites", name + ".png")
        _mcmeta(p, meta)
        out.append(p)
    # 무기: 이름 밑 금실 (글 위 y = 12 에서 9 아래 = 21. 둘째 줄은 24 에서)
    wb = _panel(w, h, inset, WEAPON_TOP, divider_at=21)
    wmeta = {"gui": {"scaling": {"type": "nine_slice", "width": w, "height": h,
                                 "border": {"left": 12, "right": 12, "top": WEAPON_TOP, "bottom": 12}}}}
    for name, img in (("gothic_weapon_background", wb), ("gothic_weapon_frame", empty)):
        p = save(img, pack, "assets", "souls", "textures", "gui", "sprites", "tooltip", name + ".png")
        _mcmeta(p, wmeta)
        out.append(p)
    return out


def _mcmeta(png_path, data):
    import json
    with open(png_path + ".mcmeta", "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# ─────────────────────────── 단추 ───────────────────────────

def button(state):
    """200×20, 아홉 조각 (양 끝 6, 위·아래 3). 띠 + 위·아래 가는 줄 (양 끝 6 픽셀은 알파 계단)."""
    w, h = 200, 20
    a = np.zeros((h, w, 4))

    def fade(x):
        d = min(x, w - 1 - x)
        return 1.0 if d >= 6 else (d + 1) / 7.0

    for x in range(w):
        f = fade(x)
        for y in range(2, h - 2):
            yy = (y - 2) / (h - 5)
            if state == "highlighted":
                col = ramp([(0.0, rgb("bronze1")), (0.45, rgb("bronze0")), (1.0, LACQUER)], yy)
                al = 150 - 40 * yy
            elif state == "disabled":
                col, al = LACQUER, 45
            else:
                col, al = LACQUER, 105 - 25 * yy
            a[y, x, :3], a[y, x, 3] = col, al * f
        if state == "highlighted":
            top, bot = (rgb("glim0") * 0.5 + rgb("parch3") * 0.5, 255), (rgb("bronze2"), 230)
        elif state == "disabled":
            top, bot = (rgb("ash1"), 120), (rgb("ash1"), 90)
        else:
            top, bot = (ramp(LINE_STOPS, 0.62), 170), (ramp(LINE_STOPS, 0.92), 150)
        a[1, x, :3], a[1, x, 3] = top[0], top[1] * f
        a[h - 2, x, :3], a[h - 2, x, 3] = bot[0], bot[1] * f
    if state == "highlighted":
        for cx in (3, w - 4):
            for dx, dy, col in ((0, -1, rgb("parch2")), (-1, 0, rgb("parch2")), (1, 0, rgb("parch2")),
                                (0, 1, rgb("parch1")), (0, 0, rgb("glim0"))):
                a[10 + dy, cx + dx, :3], a[10 + dy, cx + dx, 3] = col, 255
    return to_img(a)


# ─────────────────────────── 비네트·메뉴 바탕 ───────────────────────────

def vignette():
    """256×256 회색 (흰 = 어둡게). 바닐라는 가운데 0, 가장자리 가운데 99, 귀 210. 이 시안은 더 넓고 무겁게."""
    n = 256
    yy, xx = np.mgrid[0:n, 0:n]
    p = (np.stack([xx, yy], -1) + 0.5) / n * 2 - 1
    r = np.sqrt((p[..., 0] * 0.92) ** 2 + p[..., 1] ** 2)
    v = np.clip((r - 0.42) / (1.30 - 0.42), 0, 1)
    v = v * v * (3 - 2 * v)
    g = np.clip(np.rint(v * 255), 0, 255).astype(np.uint8)
    return Image.fromarray(g, "L").convert("RGB")


def menu_background():
    return Image.new("RGBA", (16, 16), c("ink0", 40))


# ─────────────────────────── 장식 글자 ───────────────────────────

ORN_SCALE = 2           # 장식 글자는 GUI 한 픽셀에 두 텍셀 (TTF 글자의 가는 획과 맞게)


def title_divider():
    """
    창 제목 밑 금실 (GUI 120×5, 텍셀 240×10). 가운데 마름모 (밝은 금빛) 와 양쪽으로 가는 두 줄 (위 줄은 길고 금빛, 아래 줄은
    짧고 청동), 끝은 알파 계단으로 사라지고 마지막에 점 하나.
    """
    s = ORN_SCALE
    W, H = 120 * s, 5 * s
    a = np.zeros((H, W, 4))
    cx, cy = W // 2, H // 2
    gold, dim = rgb("parch2"), rgb("bronze2")
    for x in range(W):
        d = abs(x - cx) / (W / 2)
        al = 255 * max(0.0, 1.0 - d ** 1.6) if d < 0.97 else 0
        if abs(x - cx) > 6 * s:
            a[cy, x, :3], a[cy, x, 3] = gold, al
        if 6 * s < abs(x - cx) < 34 * s:
            al2 = 200 * max(0.0, 1.0 - (abs(x - cx) - 6 * s) / (28 * s))
            a[cy + 2, x, :3], a[cy + 2, x, 3] = dim, al2
            a[cy - 2, x, :3], a[cy - 2, x, 3] = dim, al2 * 0.7
    # 마름모 (반지름 4 텍셀) 와 속 (먹)
    for y in range(H):
        for x in range(cx - 6 * s, cx + 6 * s + 1):
            dd = abs(x - cx) + abs(y - cy) * 1.4
            if dd <= 4.6:
                a[y, x, :3], a[y, x, 3] = (rgb("glim0") if dd > 2.2 else rgb("ink0")), 255
            elif abs(x - cx) in (6, 7) and y == cy:
                a[y, x, :3], a[y, x, 3] = rgb("parch3"), 255
    # 양 끝 점
    for ex in (int(W * 0.02), W - 1 - int(W * 0.02)):
        a[cy, ex, :3], a[cy, ex, 3] = rgb("parch1"), 200
    return to_img(a)


def soul_digits(font_path, out_path):
    """
    오른쪽 아래 소울 수의 숫자 (기본 팩 hud_digits.png, 칸 6×8 의 열 장) 를 명조 숫자로 다시 그린다. 텍셀 4배 (칸 24×32,
    공급자 높이 8 은 그대로라 줄여 그려진다). 진행 폭이 기본 팩과 같도록 (플러그인이 glyphs.yml 의 폭으로 자리를 셈한다)
    칸마다 맨 오른쪽 열 맨 아래에 알파 1 점을 둔다 (셰이더가 0.1 아래는 버린다). 숫자는 뼈빛, 오른쪽 아래 두 텍셀 먹 그늘.
    """
    from PIL import ImageDraw, ImageFont
    k = 4
    cw, ch = 6 * k, 8 * k
    img = Image.new("RGBA", (cw * 10, ch), (0, 0, 0, 0))
    font = ImageFont.truetype(font_path, 46)
    for d in range(10):
        glyph = Image.new("L", (cw * 2, ch * 2), 0)
        ImageDraw.Draw(glyph).text((0, 0), str(d), fill=255, font=font)
        box = glyph.getbbox()
        g = glyph.crop(box)
        gw, gh = g.size
        x0 = d * cw + (cw - 1 - gw) // 2
        y0 = ch - 1 - gh
        shadow = Image.new("RGBA", g.size, c("ink0")[:3] + (0,))
        shadow.putalpha(g.point(lambda v: v * 150 // 255))
        img.alpha_composite(shadow, (x0 + 2, min(y0 + 2, ch - gh)))
        fill = Image.new("RGBA", g.size, c("bone2")[:3] + (0,))
        fill.putalpha(g)
        img.alpha_composite(fill, (x0, y0))
        if img.getpixel((d * cw + cw - 1, ch - 1))[3] == 0:
            img.putpixel((d * cw + cw - 1, ch - 1), c("ink0", 1))
    img.save(out_path)
    return out_path


def build(pack, base_pack):
    """덧입힌 그림 경로 목록."""
    out = []
    for name in ("inventory", "generic_54", "crafting_table"):
        p = os.path.join(pack, *GUI, "container", name + ".png")
        if os.path.exists(p):
            relight_container(Image.open(p)).save(p)
            out.append(p)
    out += tooltips(pack)
    for state, fname in (("normal", "button"), ("highlighted", "button_highlighted"), ("disabled", "button_disabled")):
        out.append(save(button(state), pack, *GUI, "sprites", "widget", fname + ".png"))
    out.append(save(menu_background(), pack, *GUI, "inworld_menu_background.png"))
    out.append(save(vignette(), pack, "assets", "minecraft", "textures", "misc", "vignette.png"))
    return out


def preview(pack, path):
    """사람이 볼 한 장: 창, 설명 칸 둘, 단추 셋, 제목 금실 (어두운 흐린 바탕 위)."""
    bgc = (46, 40, 36, 255)
    sheet = Image.new("RGBA", (760, 420), bgc)
    inv = Image.open(os.path.join(pack, *GUI, "container", "inventory.png")).convert("RGBA").crop((0, 0, 176, 166))
    sheet.alpha_composite(inv.resize((352, 332), Image.NEAREST), (8, 8))
    tt = Image.open(os.path.join(pack, *GUI, "sprites", "tooltip", "background.png")).convert("RGBA")
    sheet.alpha_composite(tt.resize((192, 192), Image.NEAREST), (370, 8))
    wt = Image.open(os.path.join(pack, "assets", "souls", "textures", "gui", "sprites", "tooltip",
                                 "gothic_weapon_background.png")).convert("RGBA")
    sheet.alpha_composite(wt.resize((192, 192), Image.NEAREST), (565, 8))
    y = 210
    for f in ("button", "button_highlighted", "button_disabled"):
        b = Image.open(os.path.join(pack, *GUI, "sprites", "widget", f + ".png")).convert("RGBA")
        sheet.alpha_composite(b.resize((400, 40), Image.NEAREST), (370, y))
        y += 46
    div = Image.open(os.path.join(pack, "assets", "souls", "textures", "font", "gothic_orn.png")).convert("RGBA")
    sheet.alpha_composite(div.resize((div.width, div.height), Image.NEAREST), (8, 360))
    sheet.save(path)
