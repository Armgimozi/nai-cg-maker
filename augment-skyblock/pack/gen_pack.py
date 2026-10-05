#!/usr/bin/env python3
"""
증강 스카이블럭 리소스팩 생성기.

plugin/src/main/resources/weapons.yml 과 items.yml 을 읽어
무기마다 32x32 픽셀 텍스처를 코드로 그리고, 1.21.4 형식의 리소스팩을 만든다.

  python3 gen_pack.py

결과
  pack/resourcepack/                   팩 폴더 (assets/augsky/...)
  plugin/src/main/resources/pack.zip   플러그인 jar 에 들어갈 팩
  dist/AugmentSkyblock-pack.zip        따로 배포할 팩
  dist/preview-weapons.png             무기 미리보기

무기 모양은 type(검, 대검, 단검 ...) 으로, 색은 element(화염, 서리 ...) 로, 장식은 pool(얻는 곳) 로 정해진다.
새 무기를 weapons.yml 에 추가하고 이 스크립트를 다시 돌리면 텍스처가 생긴다.
"""
import colorsys
import json
import math
import os
import random
import shutil
import sys
import zipfile

import yaml
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "plugin", "src", "main", "resources")
OUT = os.path.join(HERE, "resourcepack")
DIST = os.path.join(ROOT, "dist")
NS = "augsky"
S = 32  # 무기 텍스처 크기


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def mix(c1, c2, t):
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(3)) + (255,)


def shade(c, f):
    """f<1 어둡게, f>1 밝게"""
    if f >= 1:
        return mix(c, (255, 255, 255, 255), min(1, f - 1))
    return mix((0, 0, 0, 255), c, f)


# ─────────────────────────── 색상표 ───────────────────────────
# blade: 날 [어두움, 중간, 밝음, 하이라이트]   metal: 가드/금속 [어두움, 중간, 밝음]
# grip: 손잡이 [어두움, 밝음]   gem: 보석 [어두움, 밝음]   glow: 빛나는 테두리   outline: 외곽선
def pal(blade, metal, grip, gem, glow, outline):
    return {
        "blade": [hexc(x) for x in blade],
        "metal": [hexc(x) for x in metal],
        "grip": [hexc(x) for x in grip],
        "gem": [hexc(x) for x in gem],
        "glow": hexc(glow),
        "outline": hexc(outline),
    }


GOLDM = ["#8a5a12", "#d9a21b", "#ffe27a"]
IRONM = ["#4a4f57", "#9aa3ad", "#dfe6ee"]
DARKM = ["#1d1a24", "#3d3848", "#6b6280"]
WOODG = ["#4a2f17", "#8a5a2b"]
LEATHERG = ["#3a2418", "#6e4630"]

PALETTES = {
    "iron": pal(["#5c636d", "#a9b2bc", "#dfe6ee", "#ffffff"], ["#5a4632", "#8c6e4c", "#b8956a"], LEATHERG, ["#7a1f1f", "#e05252"], "#ffffff", "#1c1f24"),
    "stone": pal(["#4c4c4c", "#7d7d7d", "#a5a5a5", "#cfcfcf"], ["#3d3d3d", "#666666", "#8f8f8f"], WOODG, ["#3d3d3d", "#8f8f8f"], "#d0d0d0", "#1a1a1a"),
    "wood": pal(["#5a3a1c", "#9a6b3a", "#c99a5f", "#e8c48d"], ["#4a2f17", "#7a5530", "#a37a4a"], ["#2e1d0f", "#5a3a1c"], ["#2e6b2e", "#7fd07f"], "#f0d9a8", "#1e130a"),
    "bone": pal(["#a89f7c", "#ddd6b4", "#f4efd6", "#ffffff"], ["#6e6650", "#a89f7c", "#ddd6b4"], LEATHERG, ["#3a7a7a", "#8ff0f0"], "#ffffff", "#2a261a"),
    "copper": pal(["#7a3d22", "#c06a3c", "#e89a6a", "#ffd2b0"], ["#3f7a6a", "#5fae94", "#9ce0c6"], LEATHERG, ["#2f8a7a", "#8ff0d8"], "#ffe0c8", "#2a140a"),
    "flame": pal(["#8a1a06", "#e0450f", "#ff9a2e", "#ffe680"], ["#3a1a12", "#6e2e1c", "#a8482a"], ["#2a0f08", "#5a2414"], ["#b81c00", "#ffcf3d"], "#ffd35c", "#2a0800"),
    "frost": pal(["#3a7aa8", "#7cc8f0", "#c8f0ff", "#ffffff"], ["#36506e", "#6a8fb8", "#a8c8e8"], ["#1e2e48", "#3e5a80"], ["#2a6ad0", "#a8e8ff"], "#e8fbff", "#0e2236"),
    "storm": pal(["#4a3a8a", "#7c6ad8", "#c8c0ff", "#fff59a"], ["#2a2a40", "#4a4a70", "#8080b0"], ["#1a1a2a", "#3a3a58"], ["#d8c000", "#fff59a"], "#fff59a", "#10102a"),
    "venom": pal(["#2c5a12", "#5aa02a", "#9ad850", "#e0ff9a"], ["#2a2a1a", "#4f4a2a", "#7a7040"], ["#1a2410", "#3a4a20"], ["#6a1a8a", "#c86bff"], "#c8ff7a", "#0e1a06"),
    "ocean": pal(["#1a5a7a", "#2a9ab8", "#6ad8e8", "#d8ffff"], ["#7a6a3a", "#c0a050", "#f0d890"], ["#1a2a3a", "#2a4a5a"], ["#e05a8a", "#ffb0d0"], "#c8ffff", "#06202a"),
    "earth": pal(["#5a3e1e", "#8a6a3a", "#b89a5a", "#e0c890"], ["#3a3a3a", "#5e5e5e", "#8a8a8a"], WOODG, ["#3a8a2a", "#90e070"], "#f0d090", "#1e1408"),
    "wind": pal(["#5a8a7a", "#9ad0c0", "#d8fff0", "#ffffff"], ["#6a7a8a", "#a8b8c8", "#e0f0ff"], ["#3a4a5a", "#6a8aa0"], ["#3ab0a0", "#a0fff0"], "#ffffff", "#1a2e2a"),
    "holy": pal(["#a89a6a", "#f0e8c8", "#fffbe8", "#ffffff"], GOLDM, ["#3a2a6a", "#5a4aa0"], ["#2a5ad0", "#a8d0ff"], "#fff6a0", "#3a2c08"),
    "nature": pal(["#2a6a2a", "#4fa83f", "#8ad870", "#d8ffb8"], ["#4a2f17", "#7a5530", "#a37a4a"], ["#2e1d0f", "#5a3a1c"], ["#d04080", "#ffa0d0"], "#c8ffb0", "#0e2008"),
    "blood": pal(["#4a0010", "#9a0a24", "#d8304a", "#ff8a9a"], ["#1e1418", "#3a2a30", "#5e4650"], ["#1a0a0e", "#3a141c"], ["#ff0030", "#ff9aaa"], "#ff5a70", "#140004"),
    "abyss": pal(["#1e0a3a", "#4a1a8a", "#8a3ad8", "#d8a0ff"], DARKM, ["#0e0a14", "#2a2034"], ["#c040ff", "#f0c0ff"], "#d070ff", "#06020e"),
    "shadow": pal(["#14141c", "#2e2e40", "#5a5a78", "#a0a0c8"], ["#0e0e14", "#24242e", "#44445a"], ["#08080c", "#1e1e2a"], ["#8a0a2a", "#ff5a7a"], "#8a8aff", "#000000"),
    "star": pal(["#1a1a5a", "#3a3aa8", "#7a8aff", "#ffffff"], GOLDM, ["#10103a", "#2a2a6a"], ["#ffe060", "#ffffff"], "#fff4a0", "#06061e"),
    "crystal": pal(["#5a2a8a", "#9a5ad8", "#d0a0ff", "#ffffff"], ["#3a2a4a", "#6a5080", "#a080c0"], ["#2a1a3a", "#4a2a6a"], ["#ff60c0", "#ffc0e8"], "#f0d0ff", "#1a0a2a"),
    "gold": pal(["#8a5a12", "#d9a21b", "#ffe27a", "#fffbe0"], ["#6a4a10", "#b08020", "#e8c050"], ["#5a1010", "#9a2a2a"], ["#1a6ae0", "#a0d0ff"], "#fff2a0", "#2a1a02"),
    "ender": pal(["#0a3a3a", "#1a7a6a", "#3ac8a8", "#c8fff0"], DARKM, ["#0a1414", "#1a2e2e"], ["#2a8a5a", "#7affc0"], "#7affd8", "#020e0e"),
    "sun": pal(["#c06a00", "#ffae1a", "#ffe066", "#ffffff"], GOLDM, ["#6a1a0a", "#a83a14"], ["#ff4a00", "#fff4a0"], "#ffffff", "#3a1800"),
    "doom": pal(["#14000e", "#3a0a2a", "#7a1a4a", "#ff3a6a"], ["#0a0408", "#24101c", "#4a2a3a"], ["#06000a", "#1a0a14"], ["#ff1a4a", "#ffa0b8"], "#ff2a5a", "#000000"),
    "prism": pal(["#5a2a8a", "#9a5ad8", "#d0a0ff", "#ffffff"], ["#d0d8e8", "#f0f4ff", "#ffffff"], ["#2a2a4a", "#4a4a7a"], ["#ff6b9d", "#ffffff"], "#ffffff", "#140a24"),
}

# 장식 정도(보석, 빛나는 날, 반짝임). 등급 표시가 아니라 그림의 화려함만 정한다
POOL_LOOK = {"basic": 0, "island": 1, "frost": 2, "flame": 2, "void": 2, "boss": 3, "prism": 4}


# ─────────────────────────── 모양 ───────────────────────────
# 텍스처 좌하단(손잡이) → 우상단(끝) 대각선을 축으로 잡는다.
# l: 축을 따라 손잡이 끝에서부터의 거리(픽셀), s: 축에 수직인 거리(+면 오른쪽 아래, -면 왼쪽 위)
AX0 = (3.0, 29.0)
AX1 = (29.0, 3.0)
AXLEN = math.dist(AX0, AX1)
U = ((AX1[0] - AX0[0]) / AXLEN, (AX1[1] - AX0[1]) / AXLEN)
N = (-U[1], U[0])  # (+0.707, +0.707) 쪽이 오른쪽 아래


def to_ls(x, y):
    px, py = x + 0.5 - AX0[0], y + 0.5 - AX0[1]
    return px * U[0] + py * U[1], px * N[0] + py * N[1]


def blade_material(l, s, start, end, half, tip_len, ridge=0.55, edge=1.2):
    """곧은 날: start~end 사이, 끝 tip_len 동안 뾰족해진다."""
    if l < start or l > end:
        return None
    w = half
    if l > end - tip_len:
        w = half * (end - l) / tip_len + 0.3
    a = abs(s)
    if a > w:
        return None
    if a <= ridge:
        return "ridge"
    if a > w - edge:
        return "edge"
    return "blade"


def shape_sword(l, s, lv):
    if l < 1.6:
        return "pommel" if abs(s) <= 1.6 else None
    if l < 8.5:
        return ("grip2" if int(l * 1.4) % 2 == 0 else "grip") if abs(s) <= 1.0 else None
    if l < 10.5:
        w = 4.2 + (0.6 if lv >= 3 else 0)
        if abs(s) <= w:
            if lv >= 1 and abs(s) <= 0.9:
                return "gem"
            return "metal"
        return None
    return blade_material(l, s, 10.5, 34.5, 2.2, 6.0)


def shape_greatsword(l, s, lv):
    if l < 1.8:
        return "pommel" if abs(s) <= 1.8 else None
    if l < 7.0:
        return ("grip2" if int(l * 1.4) % 2 == 0 else "grip") if abs(s) <= 1.1 else None
    if l < 9.5:
        droop = abs(s) * 0.18
        if abs(s) <= 6.0 and l < 9.5 - droop * 0.0 and l > 7.0 + max(0, abs(s) - 3.5) * 0.4:
            if lv >= 1 and abs(s) <= 1.0:
                return "gem"
            return "metal"
        return None
    return blade_material(l, s, 9.5, 35.5, 3.4, 7.0, ridge=0.8, edge=1.3)


def shape_dagger(l, s, lv):
    l2 = l - 6  # 단검은 텍스처 가운데쯤에 작게
    if l2 < 0:
        return None
    if l2 < 1.4:
        return "pommel" if abs(s) <= 1.4 else None
    if l2 < 6.5:
        return ("grip2" if int(l2 * 1.5) % 2 == 0 else "grip") if abs(s) <= 0.9 else None
    if l2 < 8.2:
        if abs(s) <= 3.0:
            return "gem" if lv >= 1 and abs(s) <= 0.7 else "metal"
        return None
    return blade_material(l2, s, 8.2, 25.0, 1.9, 6.5, ridge=0.45, edge=1.0)


def shape_katana(l, s, lv):
    if l < 1.4:
        return "pommel" if abs(s) <= 1.3 else None
    if l < 10:
        if abs(s) <= 1.05:
            # 손잡이 감기 무늬
            k = (l + s * 1.2) % 3.0
            return "grip2" if k < 1.2 else "grip"
        return None
    if l < 11.4:
        return ("gem" if lv >= 1 and abs(s) <= 0.6 else "metal") if abs(s) <= 2.6 else None
    # 살짝 휜 얇은 날
    c = 0.0045 * (l - 11.4) ** 2
    ss = s + c
    return blade_material(l, ss, 11.4, 35.0, 1.5, 7.0, ridge=0.35, edge=0.9)


def shape_axe(l, s, lv):
    if l < 1.2:
        return "pommel" if abs(s) <= 1.2 else None
    if l <= 33.5 and abs(s) <= 0.95:
        if 21 <= l <= 31:
            return "metal"
        return "grip2" if int(l) % 6 == 0 else "grip"
    # 도끼날: 축 왼쪽(s<0)으로 뻗으며 바깥쪽이 넓게 벌어지는 부채꼴
    d = -s
    if 0.9 < d <= 9.6:
        mid = 26.5
        h = 2.2 + (min(d, 8.5) / 8.5) ** 1.5 * 5.0
        if abs(l - mid) <= h:
            outer = 9.6 - ((l - mid) / 7.2) ** 2 * 2.4
            if d > outer:
                return None
            if d > outer - 1.4:
                return "edge"
            if lv >= 1 and abs(l - mid) < 0.9 and 1.6 < d < 2.8:
                return "gem"
            return "blade"
    # 반대편 작은 뿔
    if 24.0 <= l <= 28.0 and 0.9 < s <= 2.8 - abs(l - 26) * 0.6:
        return "metal"
    return None


def shape_hammer(l, s, lv):
    if l < 1.2:
        return "pommel" if abs(s) <= 1.2 else None
    if l <= 25.5:
        if abs(s) <= 0.95:
            return "grip2" if int(l) % 5 == 0 else "grip"
        return None
    if l <= 34.0:
        if abs(s) <= 5.8:
            if abs(s) > 4.6:
                return "edge"
            if 28.8 <= l <= 30.6:
                return "gem" if lv >= 1 and abs(s) <= 1.2 else "metal"
            return "blade"
        return None
    return None


def shape_spear(l, s, lv):
    if l < 1.0:
        return "pommel" if abs(s) <= 1.0 else None
    if l < 24.5:
        if abs(s) <= 0.8:
            return "grip2" if int(l) % 7 == 0 else "grip"
        return None
    if l < 26.0:
        return ("gem" if lv >= 1 and abs(s) <= 0.6 else "metal") if abs(s) <= 2.0 else None
    if l <= 36.0:
        k = (l - 26.0) / 10.0
        w = 2.8 * math.sin(math.pi * min(1, k * 1.15)) if k < 0.87 else 2.8 * (1 - k) * 2.5
        w = max(0.4, w)
        a = abs(s)
        if a > w:
            return None
        if a <= 0.5:
            return "ridge"
        if a > w - 1.0:
            return "edge"
        return "blade"
    return None


def shape_scythe(l, s, lv):
    if l < 1.0:
        return "pommel" if abs(s) <= 1.0 else None
    if l <= 33.0:
        if abs(s) <= 0.95:
            if 30.5 <= l:
                return "metal"
            return "grip2" if int(l) % 6 == 0 else "grip"
    # 낫날: 끝에서 왼쪽(s<0)으로 뻗어 아래로 휘는 초승달
    cx_l, cx_s = 25.0, -2.0
    dl, ds = l - cx_l, s - cx_s
    r = math.hypot(dl, ds)
    ang = math.atan2(ds, dl)  # 0 = 끝 방향, -pi/2 = 왼쪽
    if 7.0 <= r <= 10.6 and -2.9 <= ang <= -0.2:
        inner = 7.0 + (abs(ang + 0.2) / 2.7) * 2.6  # 끝으로 갈수록 가늘어짐
        if r < inner:
            return None
        if r > 9.6:
            return "edge"
        return "blade"
    if lv >= 1 and abs(l - 31.5) < 1.2 and abs(s + 1.6) < 0.9:
        return "gem"
    return None


def shape_staff(l, s, lv):
    if l < 1.0:
        return "pommel" if abs(s) <= 1.0 else None
    if l <= 27.0:
        if abs(s) <= 0.95:
            k = (l + s * 2.0) % 4.0
            return "grip2" if k < 1.4 else "grip"
        return None
    # 보주를 감싼 두 갈래 받침
    d = math.hypot(l - 31.5, s)
    if d <= 3.1:
        if d <= 1.2:
            return "glowcore"
        return "orb"
    if 27.0 < l <= 34.5 and 3.1 < d <= 4.4 and abs(s) >= 1.6:
        return "metal"
    return None


def shape_wand(l, s, lv):
    l2 = l - 3.0
    if l2 < 0:
        return None
    if l2 < 1.0:
        return "pommel" if abs(s) <= 1.0 else None
    if l2 <= 21.0:
        if abs(s) <= 0.75:
            return "grip2" if int(l2) % 4 == 0 else "grip"
        return None
    # 별 모양 끝
    dl, ds = l2 - 25.0, s
    r = math.hypot(dl, ds)
    ang = math.atan2(ds, dl)
    star = 2.0 + 1.6 * abs(math.cos(ang * 2.5))
    if r <= star:
        return "glowcore" if r <= 1.1 else "orb"
    return None


SHAPES = {
    "sword": shape_sword, "greatsword": shape_greatsword, "dagger": shape_dagger, "katana": shape_katana,
    "axe": shape_axe, "hammer": shape_hammer, "spear": shape_spear, "scythe": shape_scythe,
    "staff": shape_staff, "wand": shape_wand,
}


# ─────────────────────────── 칠하기 ───────────────────────────

def prism_color(t, light=1.0):
    r, g, b = colorsys.hsv_to_rgb(t % 1.0, 0.55, min(1.0, 0.95 * light))
    return (int(r * 255), int(g * 255), int(b * 255), 255)


def paint(mat, l, s, p, element, lv, rnd):
    side = 1.0 if s < 0 else 0.78  # 왼쪽 위가 밝고, 오른쪽 아래가 어둡다
    bl = p["blade"]
    if element == "prism" and mat in ("blade", "edge", "ridge", "orb"):
        t = l / 36.0
        base = prism_color(t * 1.2 + 0.05)
        if mat == "ridge":
            return shade(base, 1.45)
        if mat == "edge":
            return shade(base, 1.25 if s < 0 else 0.8)
        if mat == "orb":
            return prism_color(t + abs(s) * 0.08, 1.0)
        return shade(base, 1.0 if s < 0 else 0.82)
    if mat == "ridge":
        return bl[3] if s < 0 else bl[2]
    if mat == "blade":
        c = bl[1] if s < 0 else shade(bl[1], 0.82)
        return c
    if mat == "edge":
        if lv >= 2:
            return mix(bl[2], p["glow"], 0.5) if s < 0 else mix(bl[0], p["glow"], 0.25)
        return bl[2] if s < 0 else bl[0]
    if mat == "metal":
        m = p["metal"]
        return m[2] if s < -0.5 else (m[1] if s < 0.8 else m[0])
    if mat == "grip":
        return p["grip"][1] if s < 0 else p["grip"][0]
    if mat == "grip2":
        return shade(p["grip"][1], 1.15) if s < 0 else p["grip"][0]
    if mat == "pommel":
        m = p["metal"] if lv < 3 else p["gem"] + [p["gem"][1]]
        return m[1] if s < 0 else m[0]
    if mat == "gem":
        g = p["gem"]
        return g[1] if s < 0 else g[0]
    if mat == "orb":
        g = p["blade"]
        return g[2] if s < 0 else g[1]
    if mat == "glowcore":
        return p["glow"]
    return (255, 0, 255, 255)


def render_weapon(wtype, element, look, seed, halo=True, layers=None):
    """무기 그림(32x32). layers 에 dict 를 주면 픽셀별 재료(mats)와 외곽선 픽셀(outline)을 담아 준다 (3D 용)."""
    lv = look
    p = PALETTES.get(element, PALETTES["iron"])
    shape = SHAPES.get(wtype, shape_sword)
    rnd = random.Random(seed)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mats = {}
    for y in range(S):
        for x in range(S):
            l, s = to_ls(x, y)
            m = shape(l, s, lv)
            if m:
                mats[(x, y)] = (m, l, s)
                img.putpixel((x, y), paint(m, l, s, p, element, lv, rnd))
    # 외곽선 (4방향)
    ol = p["outline"]
    outl = set()
    for y in range(S):
        for x in range(S):
            if (x, y) in mats:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) in mats:
                    img.putpixel((x, y), ol)
                    outl.add((x, y))
                    break
    if layers is not None:
        layers.update(mats=mats, outline=outl, palette=p)
    # 등급 장식: 반짝임
    if lv >= 3:
        cands = [k for k, v in mats.items() if v[0] in ("blade", "edge", "ridge", "orb")]
        rnd.shuffle(cands)
        for (x, y) in cands[: 3 + lv]:
            img.putpixel((x, y), (255, 255, 255, 255))
        # 날 주변 빛 번짐(반투명). 3D 에서는 따로 아우라를 붙이므로 뺀다
        if not halo:
            return img
        glow = p["glow"]
        for y in range(S):
            for x in range(S):
                if img.getpixel((x, y))[3] != 0:
                    continue
                near = 0
                for dx in (-2, -1, 0, 1, 2):
                    for dy in (-2, -1, 0, 1, 2):
                        q = (x + dx, y + dy)
                        if q in mats and mats[q][0] in ("edge", "orb", "glowcore"):
                            near += 1
                if near >= 2 and rnd.random() < (0.25 if lv == 3 else 0.4):
                    img.putpixel((x, y), glow[:3] + (110,))
    return img


# ─────────────────────────── 재료 아이템 (16x16) ───────────────────────────

def item_canvas():
    return Image.new("RGBA", (16, 16), (0, 0, 0, 0))


def outline(img, color):
    w, h = img.size
    src = img.copy()
    for y in range(h):
        for x in range(w):
            if src.getpixel((x, y))[3] != 0:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h and src.getpixel((xx, yy))[3] == 255:
                    img.putpixel((x, y), color)
                    break


def draw_shard(colors, sparkle=True):
    img = item_canvas()
    dark, mid, light, hi = colors
    # 비스듬한 결정 조각 두 개
    pts = [(4, 12), (9, 2), (11, 4), (7, 13)]
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=mid)
    d.polygon([(4, 12), (9, 2), (8, 5), (5, 12)], fill=light)
    d.line([(9, 3), (6, 11)], fill=hi)
    d.polygon([(9, 13), (12, 8), (13, 9), (10, 14)], fill=dark)
    d.polygon([(9, 13), (12, 8), (11, 10)], fill=mid)
    outline(img, shade(dark, 0.4))
    if sparkle:
        img.putpixel((12, 3), hi)
        img.putpixel((3, 6), light)
    return img


def draw_prism_crystal():
    img = item_canvas()
    for y in range(16):
        for x in range(16):
            dx, dy = x - 7.5, y - 7.5
            if abs(dx) + abs(dy) * 0.8 <= 6.6 and abs(dx) <= 5.5:
                t = (math.atan2(dy, dx) / (2 * math.pi)) + 0.5
                light = 1.15 if dx + dy < 0 else 0.85
                img.putpixel((x, y), prism_color(t, light))
    d = ImageDraw.Draw(img)
    d.line([(7, 3), (4, 7), (7, 12)], fill=(255, 255, 255, 220))
    outline(img, (40, 20, 60, 255))
    img.putpixel((11, 4), (255, 255, 255, 255))
    return img


def draw_ticket(band, star):
    img = item_canvas()
    d = ImageDraw.Draw(img)
    paper = hexc("#f2e8d0")
    d.rectangle([2, 4, 13, 11], fill=paper)
    d.rectangle([2, 4, 13, 5], fill=band)
    d.rectangle([2, 10, 13, 11], fill=shade(band, 0.75))
    # 가장자리 톱니
    for x in (2, 13):
        img.putpixel((x, 7), (0, 0, 0, 0))
        img.putpixel((x, 8), (0, 0, 0, 0))
    cx, cy = 8, 8
    for (x, y) in [(cx, cy - 1), (cx - 1, cy), (cx, cy), (cx + 1, cy), (cx, cy + 1)]:
        img.putpixel((x, y), star)
    img.putpixel((cx - 1, cy - 1), shade(star, 0.8))
    img.putpixel((cx + 1, cy + 1), shade(star, 0.8))
    outline(img, hexc("#3a2c18"))
    return img


def draw_essence(colors):
    img = item_canvas()
    dark, mid, light, hi = colors
    for y in range(16):
        for x in range(16):
            dx, dy = x - 7.5, y - 9.0
            # 아래는 둥글고 위는 뾰족한 불꽃/물방울
            r = 4.6 if dy >= 0 else 4.6 * (1 + dy / 7.5)
            if dy < -7.5:
                continue
            if math.hypot(dx, max(dy, 0)) <= 4.6 and abs(dx) <= r:
                k = math.hypot(dx + 1, dy + 1) / 5.5
                img.putpixel((x, y), mix(hi, mix(light, mid, min(1, k)), min(1, k * 1.2)) if k < 0.4 else (light if k < 0.7 else mid))
    outline(img, shade(dark, 0.5))
    img.putpixel((6, 8), hi)
    img.putpixel((12, 3), light)
    img.putpixel((3, 4), mid)
    return img


ITEM_ART = {
    "shard": lambda: draw_shard([hexc("#3a1a5a"), hexc("#8a4ad8"), hexc("#c89aff"), hexc("#ffffff")]),
    "prism_crystal": draw_prism_crystal,
    "ticket_silver": lambda: draw_ticket(hexc("#9aa8b8"), hexc("#ffffff")),
    "ticket_gold": lambda: draw_ticket(hexc("#d9a21b"), hexc("#fff2a0")),
    "ticket_prism": lambda: draw_ticket(hexc("#c86bff"), hexc("#6bffb0")),
    "essence_frost": lambda: draw_essence([hexc("#1e4a7a"), hexc("#4aa0e0"), hexc("#a8e8ff"), hexc("#ffffff")]),
    "essence_flame": lambda: draw_essence([hexc("#6a1a06"), hexc("#e0450f"), hexc("#ffae3a"), hexc("#fff2a0")]),
    "essence_void": lambda: draw_essence([hexc("#1a0a3a"), hexc("#6a2ac8"), hexc("#c08aff"), hexc("#ffffff")]),
}


def pack_icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, 63, 63], radius=10, fill=hexc("#140a24"))
    for i in range(6):
        t = i / 6
        r = 26 - i * 3.5
        d.regular_polygon((32, 32, r), 4, rotation=45, fill=prism_color(t + 0.1, 1.05))
    d.regular_polygon((32, 32, 6), 4, rotation=45, fill=(255, 255, 255, 255))
    return img


# ─────────────────────────── 팩 쓰기 ───────────────────────────

def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


ART = os.path.join(HERE, "art")
BOSS_ART = {"boss_frost": "frost_tyrant", "boss_flame": "inferno_colossus", "boss_void": "void_sovereign"}
ARMOR_ART = ["armor_a", "armor_b"]
CATALOG = os.path.join(DIST, "catalog")


def load_art(name):
    """pack/art/<name>.py (보스·갑옷 그림 모듈)을 불러온다. 없으면 None."""
    import importlib.util
    path = os.path.join(ART, name + ".py")
    if not os.path.exists(path):
        return None
    for d in (HERE, ART):
        if d not in sys.path:
            sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location("art_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_weapon_designs():
    """pack/weapons/<그룹>.py 의 WEAPONS 를 모두 모은다 (_ 로 시작하는 파일은 예시라 뺀다)."""
    import importlib.util
    designs = {}
    wdir = os.path.join(HERE, "weapons")
    for d in (HERE, wdir):
        if d not in sys.path:
            sys.path.insert(0, d)
    for f in sorted(os.listdir(wdir)):
        if not f.endswith(".py") or f.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("weapons_" + f[:-3], os.path.join(wdir, f))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            designs.update(getattr(mod, "WEAPONS", {}))
        except Exception as ex:  # 그룹 하나가 깨져도 나머지는 만든다
            import traceback
            traceback.print_exc()
            print("무기 디자인 모듈 실패:", f, ex)
    return designs


def build_weapon_model(wid, w, a, designs):
    """디자인된 복셀 무기가 있으면 그것으로, 없으면 예전 방식(그림을 두껍게)으로 만든다. 미리보기용 모델을 돌려준다."""
    import weapons3d
    import wkit
    fn = designs.get(wid)
    if fn is not None:
        made = fn()
        if isinstance(made, (list, tuple)):
            return wkit.build_bow("item/" + wid, a, list(made))[0]
        return made.build("item/" + wid, a)
    print("디자인이 없는 무기 (예전 방식으로):", wid)
    model, _, _ = weapons3d.build_weapon(wid, w, a, POOL_LOOK)
    return model


def build_bosses(a):
    """보스 모델 조각을 쓰고, 플러그인이 읽을 rigs.yml 을 만든다."""
    rigs = {}
    for mod_name, boss in BOSS_ART.items():
        mod = load_art(mod_name)
        if mod is None:
            print("보스 그림 모듈이 없음:", mod_name)
            continue
        spec = mod.build(a)
        rigs[spec.get("boss", boss)] = {"parts": spec["parts"]}
        print(f"보스 {boss}: 조각 {len(spec['parts'])}개")
    with open(os.path.join(RES, "rigs.yml"), "w", encoding="utf-8") as f:
        f.write("# 보스 3D 모델 조각 (pack/gen_pack.py 가 pack/art/boss_*.py 로 만든다. 직접 고치지 말 것)\n")
        class NoAlias(yaml.SafeDumper):
            def ignore_aliases(self, data):
                return True
        yaml.dump(rigs, f, Dumper=NoAlias, allow_unicode=True, sort_keys=False, default_flow_style=None)
    return rigs


def build_armor(a, armor):
    """갑옷: 그림 모듈이 투구 3D 모델과 장비 텍스처, 아이콘을 그리고, 여기서 장비/아이템 정의를 쓴다."""
    for name in ARMOR_ART:
        try:
            mod = load_art(name)
            if mod is None:
                print("갑옷 그림 모듈이 없음:", name)
                continue
            mod.build(a)
        except Exception as ex:  # 그림 모듈 하나가 깨져도 팩 전체는 만든다
            import traceback
            traceback.print_exc()
            print("갑옷 그림 모듈 실패:", name, ex)
    for sid in armor:
        write_json(os.path.join(a, "equipment", sid + ".json"), {"layers": {
            "humanoid": [{"texture": f"{NS}:{sid}"}],
            "humanoid_leggings": [{"texture": f"{NS}:{sid}"}],
        }})
        for slot in ("chestplate", "leggings", "boots"):
            tex = os.path.join(a, "textures", "item", "armor", f"{sid}_{slot}.png")
            if not os.path.exists(tex):
                print("갑옷 아이콘이 없음:", tex)
            write_json(os.path.join(a, "models", "item", "armor", f"{sid}_{slot}.json"),
                       {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/armor/{sid}_{slot}"}})
            write_json(os.path.join(a, "items", "armor", f"{sid}_{slot}.json"),
                       {"model": {"type": "minecraft:model", "model": f"{NS}:item/armor/{sid}_{slot}"}})
        for kind in ("humanoid", "humanoid_leggings"):
            tex = os.path.join(a, "textures", "entity", "equipment", kind, sid + ".png")
            if not os.path.exists(tex):
                print("갑옷 텍스처가 없음:", tex)
        if not os.path.exists(os.path.join(a, "items", "armor", f"{sid}_helmet.json")):
            print("투구 모델이 없음:", sid)
            continue
        armor_card(a, sid)


def armor_card(a, sid):
    """도감용 그림: 3D 투구 + 갑옷/각반/신발 아이콘."""
    from mc3d import load_model, render
    os.makedirs(os.path.join(CATALOG, "armor"), exist_ok=True)
    try:
        helm = render([(load_model(f"augsky:armor/{sid}_helmet", a), None)], size=160, yaw=-30, pitch=15, bg=(0, 0, 0, 0))
    except Exception as ex:
        print("투구 그림 실패:", sid, ex)
        return
    card = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    card.alpha_composite(helm.resize((132, 132), Image.LANCZOS), (30, 0))
    for i, slot in enumerate(("chestplate", "leggings", "boots")):
        p = os.path.join(a, "textures", "item", "armor", f"{sid}_{slot}.png")
        if os.path.exists(p):
            ic = Image.open(p).convert("RGBA").resize((56, 56), Image.NEAREST)
            card.alpha_composite(ic, (8 + i * 62, 134))
    card.save(os.path.join(CATALOG, "armor", sid + ".png"))


def write_atlas_sources(a):
    """textures/item, block 밖의 폴더(boss/ 등)도 블록 아틀라스에 넣어야 아이템 모델에서 쓸 수 있다."""
    tex = os.path.join(a, "textures")
    dirs = sorted(d for d in os.listdir(tex) if os.path.isdir(os.path.join(tex, d)) and d not in ("item", "block", "entity"))
    if dirs:
        write_json(os.path.join(OUT, "assets", "minecraft", "atlases", "blocks.json"),
                   {"sources": [{"type": "directory", "source": d, "prefix": d + "/"} for d in dirs]})


def main():
    from mc3d import render
    weapons = yaml.safe_load(open(os.path.join(RES, "weapons.yml"), encoding="utf-8"))
    items = yaml.safe_load(open(os.path.join(RES, "items.yml"), encoding="utf-8"))
    armor = yaml.safe_load(open(os.path.join(RES, "armor.yml"), encoding="utf-8"))
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    a = os.path.join(OUT, "assets", NS)
    write_json(os.path.join(OUT, "pack.mcmeta"), {
        "pack": {
            "pack_format": 46,
            "supported_formats": {"min_inclusive": 46, "max_inclusive": 99},
            "min_format": 46,
            "max_format": 99,
            "description": "증강 스카이블럭 무기, 갑옷, 보스",
        }
    })
    pack_icon().save(os.path.join(OUT, "pack.png"))
    os.makedirs(os.path.join(CATALOG, "weapons"), exist_ok=True)

    rendered = []
    designs = load_weapon_designs()
    from mc3d import mat
    for wid, w in weapons.items():
        model = build_weapon_model(wid, w, a, designs)
        # 도감/미리보기 그림: 인벤토리처럼 대각선으로 눕힌 모습
        img = render([(model, mat(roll=-45))], size=192, yaw=-18, pitch=10, bg=(0, 0, 0, 0))
        img.save(os.path.join(CATALOG, "weapons", wid + ".png"))
        rendered.append((wid, w, img))

    for iid in items:
        art = ITEM_ART.get(iid)
        if art is None:
            print("그림이 없는 아이템:", iid, "(종이 모양으로 대체)")
            art = lambda: draw_ticket(hexc("#888888"), hexc("#ffffff"))
        img = art()
        os.makedirs(os.path.join(a, "textures", "item"), exist_ok=True)
        img.save(os.path.join(a, "textures", "item", iid + ".png"))
        write_json(os.path.join(a, "models", "item", iid + ".json"),
                   {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/{iid}"}})
        write_json(os.path.join(a, "items", iid + ".json"),
                   {"model": {"type": "minecraft:model", "model": f"{NS}:item/{iid}"}})

    if "--no-art" not in sys.argv:
        build_bosses(a)
        build_armor(a, armor)
    write_atlas_sources(a)
    # 스스로 빛나는 픽셀(알파 252/251/250)을 위한 셰이더
    shd = os.path.join(OUT, "assets", "minecraft", "shaders", "core")
    os.makedirs(shd, exist_ok=True)
    for f in os.listdir(os.path.join(HERE, "shaders")):
        if f.endswith((".vsh", ".fsh")):
            shutil.copy(os.path.join(HERE, "shaders", f), os.path.join(shd, f))

    # zip
    os.makedirs(DIST, exist_ok=True)
    zips = [os.path.join(DIST, "AugmentSkyblock-pack.zip"), os.path.join(RES, "pack.zip")]
    for zp in zips:
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _, files in os.walk(OUT):
                for f in sorted(files):
                    full = os.path.join(base, f)
                    arc = os.path.relpath(full, OUT).replace(os.sep, "/")
                    zi = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as fh:
                        z.writestr(zi, fh.read())
    preview(rendered, items)
    print(f"무기 {len(rendered)}종, 아이템 {len(items)}종, 갑옷 {len(armor)}세트 → {zips[0]}")


ELEMENT_COLOR = {
    "iron": "#d8dde3", "stone": "#b8b8b8", "wood": "#d9a86a", "bone": "#ece6c8", "copper": "#e8916a",
    "flame": "#ff8a3d", "frost": "#9ad8ff", "storm": "#c8b8ff", "venom": "#a8e060", "ocean": "#5ad0e8",
    "earth": "#d0a868", "wind": "#b8f0e0", "holy": "#fff0a8", "nature": "#8ad870", "blood": "#ff5a6e",
    "abyss": "#b06bff", "shadow": "#a0a0c0", "star": "#a8b8ff", "crystal": "#d0a0ff", "prism": "#ff9ad0",
    "gold": "#ffd84d", "ender": "#5ae8c0", "sun": "#ffd04a", "doom": "#ff3a6a",
}
POOL_NAME = {"basic": "섬 초반", "island": "섬 재료", "frost": "서리 균열", "flame": "화염 균열",
             "void": "공허 균열", "boss": "보스", "prism": "프리즘"}


def preview(rendered, items):
    font_path = os.environ.get("PREVIEW_FONT", "")
    cols = 8
    cell_w, cell_h = 150, 150
    # 얻는 곳별로 줄을 나눈다
    groups = []
    for pool in POOL_NAME:
        g = [r for r in rendered if r[1].get("pool", "basic") == pool]
        if g:
            groups.append((pool, g))
    rows = sum((len(g) + cols - 1) // cols for _, g in groups)
    W, H = cols * cell_w + 20, rows * cell_h + 60 + len(groups) * 36
    sheet = Image.new("RGBA", (W, H), hexc("#15131c"))
    d = ImageDraw.Draw(sheet)
    try:
        f_title = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
        f_head = ImageFont.truetype(font_path, 20) if font_path else ImageFont.load_default()
        f_name = ImageFont.truetype(font_path, 15) if font_path else ImageFont.load_default()
    except OSError:
        f_title = f_head = f_name = ImageFont.load_default()
    d.text((14, 14), f"증강 스카이블럭 무기 {len(rendered)}종", font=f_title, fill=(255, 255, 255, 255))
    y = 60
    for pool, g in groups:
        d.text((16, y + 6), f"{POOL_NAME[pool] if font_path else pool}  ({len(g)})", font=f_head, fill=(200, 200, 215, 255))
        y += 36
        for i, (wid, w, img) in enumerate(g):
            cx = 10 + (i % cols) * cell_w
            cy = y + (i // cols) * cell_h
            col = ELEMENT_COLOR.get(w.get("element"), "#d8d8d8")
            d.rounded_rectangle([cx + 4, cy + 4, cx + cell_w - 4, cy + cell_h - 4], radius=8, fill=hexc("#221f2c"), outline=hexc(col), width=2)
            big = img.resize((104, 104), Image.LANCZOS)
            sheet.alpha_composite(big, (cx + (cell_w - 104) // 2, cy + 8))
            label = w.get("name", wid) if font_path else wid
            tw = d.textlength(label, font=f_name)
            d.text((cx + (cell_w - tw) / 2, cy + 116), label, font=f_name, fill=hexc(col))
        y += ((len(g) + cols - 1) // cols) * cell_h
    sheet.save(os.path.join(DIST, "preview-weapons.png"))


if __name__ == "__main__":
    main()
