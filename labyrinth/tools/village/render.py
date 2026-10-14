#!/usr/bin/env python3
"""render.py — 마을 조각 / 마을 전체 / 서버 덤프를 등각(isometric) 복셀 PNG 로 그린다.

    python render.py --piece plugin/src/main/resources/village/pieces/forge.json --out /tmp/forge.png
    python render.py --piece forge.json --rotate all --out /tmp/forge_rot.png     # 회전 4방향 한 장
    python render.py --layout plugin/src/main/resources/village/layout.json \\
                     --pieces-dir plugin/src/main/resources/village/pieces --out /tmp/village.png --top
    python render.py --dump plugins/Labyrinth/village/dump.txt --out /tmp/world.png --top

--view ne|sw|nw|se|all (기본 ne,sw 두 장: <out>_ne.png, <out>_sw.png). ne = 북동쪽 위에서 내려다봄 → 정방향 조각의 정면(북)이
오른쪽 면에 보인다. --top 은 위에서 본 평면도(<out>_top.png, 북쪽이 위). 큰 그림도 축소하지 않는다 (최대 4096px, 넘으면
블록당 px 를 줄임). 색은 blockdata.json(바닐라 텍스처 평균색) + 아래 손 보정표 + 키워드 대체.
"""
import argparse
import colorsys
import json
import math
import os
import sys
import zlib

from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vlib  # noqa: E402
from vlib import DIRS, DXZ, ccw, cw, opposite, parse_block  # noqa: E402

MAX_PX = 4096

# ─────────────────────────────── 시점 ───────────────────────────────
# 화면: sx = (a − b)·S, sy = (a + b)·S/2 − y·S. 보는 사람은 +a, +b, +y 쪽. 보이는 면 = 윗면, +a 면(오른쪽), +b 면(왼쪽).
# A, B = 칸의 (a, b) 최솟값, la/lb = 칸 안 좌표 변환, da/db = +a/+b 방향의 월드 (dx, dz), fa/fb = 그 면의 월드 방향 이름.
VIEWS = {
    "ne": dict(A=lambda x, z: -z - 1, B=lambda x, z: x, la=lambda lx, lz: 1 - lz, lb=lambda lx, lz: lx,
               da=(0, -1), db=(1, 0), fa="north", fb="east"),
    "sw": dict(A=lambda x, z: z, B=lambda x, z: -x - 1, la=lambda lx, lz: lz, lb=lambda lx, lz: 1 - lx,
               da=(0, 1), db=(-1, 0), fa="south", fb="west"),
    "nw": dict(A=lambda x, z: -x - 1, B=lambda x, z: -z - 1, la=lambda lx, lz: 1 - lx, lb=lambda lx, lz: 1 - lz,
               da=(-1, 0), db=(0, -1), fa="west", fb="north"),
    "se": dict(A=lambda x, z: x, B=lambda x, z: z, la=lambda lx, lz: lx, lb=lambda lx, lz: lz,
               da=(1, 0), db=(0, 1), fa="east", fb="south"),
}
SHADE_TOP, SHADE_A, SHADE_B = 1.0, 0.82, 0.64

# ─────────────────────────────── 색 ───────────────────────────────
# 손 보정표: 바이옴 색·블록 엔티티·투명 블록처럼 텍스처 평균이 실제 인상과 다른 것. 값 = (윗면, 옆면) 16진수.
OVERRIDES = {
    "grass_block": ("6c9a40", "86704a"), "water": ("3f76e4", "3a6cd0"), "lava": ("f08a22", "e0701a"),
    "oak_leaves": ("4f7f2c", "466f27"), "spruce_leaves": ("3f663f", "385a38"), "birch_leaves": ("6a9446", "5e843e"),
    "jungle_leaves": ("4c8a2a", "437a25"), "acacia_leaves": ("5d8a2c", "527a27"), "dark_oak_leaves": ("3f6a24", "385e20"),
    "mangrove_leaves": ("5f9a35", "558a2f"), "short_grass": ("6aa040", "5f9238"), "tall_grass": ("6aa040", "5f9238"),
    "fern": ("5f9238", "56853a"), "large_fern": ("5f9238", "56853a"), "vine": ("4c7f2a", "4c7f2a"),
    "lily_pad": ("2f8a3a", "2f8a3a"), "sugar_cane": ("8fc060", "8fc060"), "dirt_path": ("a88a4e", "8c6d44"),
    "glass": ("d8f0f4", "c8e4ea"), "glass_pane": ("d8f0f4", "c8e4ea"), "tinted_glass": ("3a3240", "2e2836"),
    "chest": ("a8742f", "8f5f25"), "trapped_chest": ("a8742f", "8f5f25"), "ender_chest": ("2c4448", "22383c"),
    "barrier": ("ff0000", "ff0000"), "light": ("ffff80", "ffff80"), "bell": ("e0b840", "c89a30"),
    "decorated_pot": ("a8603e", "985538"), "conduit": ("b0a080", "8a7a60"),
    "skeleton_skull": ("d0d0c8", "b8b8b0"), "wither_skeleton_skull": ("3a3a3a", "2e2e2e"),
    "zombie_head": ("4e8a40", "3f7034"), "creeper_head": ("62b04c", "4e9a3c"), "player_head": ("8a6a4a", "6a4e34"),
    "dragon_head": ("2a2a2e", "202024"), "piglin_head": ("e0a090", "c88878"),
    "campfire": ("6a5236", "5a442c"), "soul_campfire": ("5a4a3a", "4a3c2e"),
    "cauldron": ("4a4a4e", "56565a"), "water_cauldron": ("3f76e4", "56565a"), "lava_cauldron": ("f08a22", "56565a"),
    "iron_bars": ("5a5c60", "4c4e52"), "lantern": ("4a4440", "3e3834"), "soul_lantern": ("3c4448", "323a3e"),
}
# 키워드 대체 (blockdata 에 없는 블록 — 다음 버전 블록 등)
KEYWORDS = [
    ("stained_glass", "c8dce8"), ("glass", "d8f0f4"), ("leaves", "4f7f2c"), ("planks", "a2834f"), ("log", "6b5130"),
    ("wood", "6b5130"), ("stem", "6b3a4a"), ("stone_brick", "7a7a7a"), ("deepslate", "4a4a50"), ("blackstone", "3a3236"),
    ("terracotta", "985e43"), ("wool", "e0e0e0"), ("concrete", "b0b0b0"), ("copper", "c06c4c"), ("brick", "976253"),
    ("sandstone", "d8cb98"), ("sand", "dbd0a0"), ("quartz", "ece6dc"), ("prismarine", "5aa898"), ("amethyst", "8a62c0"),
    ("tuff", "6c6e66"), ("andesite", "888888"), ("diorite", "bcbcbc"), ("granite", "956755"), ("stone", "7e7e7e"),
    ("dirt", "86603e"), ("mud", "3c3a3e"), ("moss", "596d2c"), ("ice", "a0c4f8"), ("snow", "f4fafa"),
    ("iron", "d8d8d8"), ("gold", "f0d040"), ("diamond", "6ae0d8"), ("emerald", "40c060"), ("netherrack", "6a2c2c"),
    ("nether", "4a2028"), ("purpur", "a87ca8"), ("end_stone", "dcdea0"), ("obsidian", "1a1424"), ("bamboo", "c8b050"),
]
# 큰 꽃(두 칸)은 기본 상태가 아랫칸(초록)이라 꽃 색을 따로
BLOOMS = {"peony": "e8a0d0", "rose_bush": "d02838", "lilac": "c890d8", "sunflower": "f4d030",
          "pitcher_plant": "5aa0c8", "torchflower": "f08a30"}
ACCENTS = {"red": "b02e26", "orange": "f9801d", "yellow": "fed83d", "lime": "80c71f", "green": "5e7c16",
           "cyan": "169c9c", "light_blue": "3ab3da", "blue": "3c44aa", "purple": "8932b8", "magenta": "c74ebd",
           "pink": "f38baa", "white": "f9fffe", "light_gray": "9d9d97", "gray": "474f52", "black": "1d1d21",
           "brown": "835432"}

# 광원: id → (밝기 0..15, 빛 색). lit 속성이 false 면 끔.
LIGHTS = {
    "lantern": (15, "ffc46b"), "soul_lantern": (10, "7fe0ff"), "torch": (14, "ffc46b"), "wall_torch": (14, "ffc46b"),
    "soul_torch": (10, "7fe0ff"), "soul_wall_torch": (10, "7fe0ff"), "copper_torch": (14, "b8ff9a"),
    "copper_wall_torch": (14, "b8ff9a"), "redstone_torch": (7, "ff4030"), "redstone_wall_torch": (7, "ff4030"),
    "campfire": (15, "ffa040"), "soul_campfire": (10, "7fe0ff"), "glowstone": (15, "ffd890"),
    "sea_lantern": (15, "d0f4ff"), "shroomlight": (15, "ffb060"), "ochre_froglight": (15, "fff0a0"),
    "verdant_froglight": (15, "d8ffb0"), "pearlescent_froglight": (15, "ffd8f0"), "end_rod": (14, "fff4f0"),
    "lava": (15, "ff8a20"), "lava_cauldron": (15, "ff8a20"), "jack_o_lantern": (15, "ffb040"), "beacon": (15, "c0f8ff"),
    "conduit": (15, "a0f0ff"), "magma_block": (3, "ff6020"), "amethyst_cluster": (5, "d0a0ff"),
    "large_amethyst_bud": (4, "d0a0ff"), "crying_obsidian": (10, "a050ff"), "glow_lichen": (7, "c0ffd0"),
    "enchanting_table": (7, "c080ff"), "ender_chest": (7, "a0ffe0"), "respawn_anchor": (15, "c060ff"),
    "fire": (15, "ffa040"), "soul_fire": (10, "7fe0ff"), "cave_vines": (14, "ffc060"),
    "cave_vines_plant": (14, "ffc060"), "redstone_lamp": (15, "ffd090"), "copper_bulb": (15, "ffd090"),
    "sculk_catalyst": (6, "60e0e0"), "brewing_stand": (1, "ffe080"), "light": (15, "ffffa0"),
    "firefly_bush": (2, "e0ff80"), "creaking_heart": (0, "ff8000"),
}

_COLOR_CACHE = {}


def _hex(h):
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def vivid(c, s=1.12, v=1.06):
    r, g, b = (max(0.0, min(1.0, x / 255.0)) for x in c)
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb(hh, min(1.0, ss * s), min(1.0, vv * v))
    return (r * 255, g * 255, b * 255)


def block_colors(bid):
    """(윗면, 옆면, 강조색, 알파) — RGB 실수 튜플."""
    c = _COLOR_CACHE.get(bid)
    if c:
        return c
    data = vlib.blockdata()["colors"]
    alpha = 1.0
    if bid in OVERRIDES:
        top, side = (_hex(h) for h in OVERRIDES[bid])
        accent = data[bid][2] if bid in data else OVERRIDES[bid][0]
        accent = _hex(accent) if isinstance(accent, str) else accent
    elif bid in data:
        t, s, a, cover, al = data[bid]
        top, side, accent = _hex(t), _hex(s), _hex(a)
    else:
        h = next((col for kw, col in KEYWORDS if kw in bid), "a0a0a0")
        top = side = accent = _hex(h)
    if bid in data:
        cover, al = data[bid][3], data[bid][4]
        if vlib.is_full(bid):
            if al < 0.9:
                alpha = min(0.85, al + 0.12)          # 색유리처럼 반투명
            elif cover < 0.5 and bid not in vlib.tag("leaves"):
                alpha = 0.38                         # 테두리만 있는 유리
    if bid in ("glass", "glass_pane", "water"):
        alpha = 0.4 if bid != "water" else 0.72
    if "ice" in bid and bid != "blue_ice":
        alpha = 0.82
    c = (vivid(top), vivid(side), vivid(accent), alpha)
    _COLOR_CACHE[bid] = c
    return c


def wood_of(bid):
    for suf in ("_wall_hanging_sign", "_hanging_sign", "_wall_sign", "_sign"):
        if bid.endswith(suf):
            return bid[: -len(suf)]
    return bid


def dye_of(bid):
    for d in sorted(vlib.DYES, key=len, reverse=True):
        if bid.startswith(d + "_"):
            return d
    return None


# ─────────────────────────────── 모양 ───────────────────────────────
# 상자 = (x0, y0, z0, x1, y1, z1, 색) — 칸 안 좌표(0..1), 월드 방향. 색 = {'up':rgb, 'north':rgb, ...} 또는 rgb 하나.
# 특수 그리기 = ('bill', 종류, 높이, 줄기색, 꽃색) — 십자형 식물을 화면 정면 판으로.

def _rect_half(d):
    return {"north": (0, 0, 1, 0.5), "south": (0, 0.5, 1, 1), "east": (0.5, 0, 1, 1), "west": (0, 0, 0.5, 1)}[d]


def _isect(r1, r2):
    return (max(r1[0], r2[0]), max(r1[1], r2[1]), min(r1[2], r2[2]), min(r1[3], r2[3]))


def _side_panel(side, t, y0=0.0, y1=1.0, inset=0.0):
    """side 쪽 면에 붙은 두께 t 판."""
    a, b = inset, 1 - inset
    return {"north": (a, y0, 0, b, y1, t), "south": (a, y0, 1 - t, b, y1, 1),
            "west": (0, y0, a, t, y1, b), "east": (1 - t, y0, a, 1, y1, b)}[side]


def _axis_box(axis, w0, w1, l0=0.0, l1=1.0):
    if axis == "y":
        return (w0, l0, w0, w1, l1, w1)
    if axis == "x":
        return (l0, w0, w0, l1, w1, w1)
    return (w0, w0, l0, w1, w1, l1)


def _rot_box(box, facing, default="north"):
    """기본 모델(북향 가정) 상자를 facing 으로 돌림."""
    x0, y0, z0, x1, y1, z1 = box
    turns = (DIRS.index(facing) - DIRS.index(default)) % 4
    for _ in range(turns):     # 시계 방향 90°: (x, z) → (1 − z, x)
        x0, z0, x1, z1 = 1 - z1, x0, 1 - z0, x1
    return (min(x0, x1), y0, min(z0, z1), max(x0, x1), y1, max(z0, z1))


def _cardinal16(rot):
    return ("south", "west", "north", "east")[int(round(int(rot) / 4.0)) % 4]


def _mul(c, f):
    return tuple(v * f for v in c)


def _faces(top, side, axis=None):
    """축 블록: 축에 수직인 면은 나이테(top)색."""
    if axis == "x":
        return {"up": side, "north": side, "south": side, "east": top, "west": top}
    if axis == "z":
        return {"up": side, "north": top, "south": top, "east": side, "west": side}
    return {"up": top, "north": side, "south": side, "east": side, "west": side}


class Style:
    __slots__ = ("boxes", "bills", "opaque", "alpha", "light", "full", "bid", "occ", "tex")

    def __init__(self, bid):
        self.bid = bid
        self.boxes, self.bills = [], []
        self.opaque = False        # 완전 불투명 정육면체 (이웃 면 가림)
        self.full = False
        self.alpha = 1.0
        self.light = None
        self.occ = False           # 시야·하늘을 크게 가림 (빛 번짐 차단, 처마 그늘)
        self.tex = False           # 면을 2×2 로 나눠 얼룩 (잎)


_STYLE_CACHE = {}
AIR = {"air", "cave_air", "void_air", "structure_void", "barrier", "light", "moving_piston"}
FLOWERISH = None


def style_of(state, extra=None):
    key = (state, extra)
    st = _STYLE_CACHE.get(key)
    if st is not None:
        return st
    st = _make_style(state, extra)
    b = st.bid
    st.occ = (st.opaque or (isinstance(b, str) and (b.endswith("_stairs") or b.endswith("_slab"))
                            and st.alpha >= 1.0) or (st.full and b in vlib.tag("leaves")))
    _STYLE_CACHE[key] = st
    return st


def _make_style(state, extra):
    global FLOWERISH
    if FLOWERISH is None:
        FLOWERISH = vlib.tag("flowers") | vlib.tag("small_flowers")
    if state.startswith("#"):
        return _pseudo_style(state)
    bid, p = parse_block(state)
    st = Style(bid)
    if bid in AIR or state == ".":
        return st
    top, side, accent, alpha = block_colors(bid)
    st.alpha = alpha
    lt = LIGHTS.get(bid)
    if lt and p.get("lit", "true") == "true" and lt[0] > 0:
        st.light = (lt[0], _hex(lt[1]))
    if bid.endswith("candle") and p.get("lit") == "true":
        st.light = (3 * int(p.get("candles", "1")), _hex("ffc870"))
    box = st.boxes.append
    f = p.get("facing")
    shapes = vlib.blockdata()["shapes"]
    kind = vlib._kind(bid)
    fc = _faces(top, side, p.get("axis"))

    if bid == "water" or bid == "lava":
        h = 0.875 if p.get("level", "0") == "0" else 0.6
        box((0, 0, 0, 1, h, 1, _faces(top, side)))
        if bid == "lava":
            st.alpha = 1.0
        return st
    if bid.endswith("_stairs"):
        half = p.get("half", "bottom")
        shape = p.get("shape", "straight")
        f = f or "north"
        sl = (0, 0, 0, 1, 0.5, 1) if half == "bottom" else (0, 0.5, 0, 1, 1, 1)
        sy0, sy1 = (0.5, 1) if half == "bottom" else (0, 0.5)
        box(sl + (fc,))
        hf = _rect_half(f)
        if shape == "straight":
            rects = [hf]
        elif shape == "inner_left":
            rects = [hf, _isect(_rect_half(ccw(f)), _rect_half(opposite(f)))]
        elif shape == "inner_right":
            rects = [hf, _isect(_rect_half(cw(f)), _rect_half(opposite(f)))]
        elif shape == "outer_left":
            rects = [_isect(hf, _rect_half(ccw(f)))]
        else:
            rects = [_isect(hf, _rect_half(cw(f)))]
        for r in rects:
            box((r[0], sy0, r[1], r[2], sy1, r[3], fc))
        return st
    if bid.endswith("_slab"):
        t = p.get("type", "bottom")
        if t == "double":
            box((0, 0, 0, 1, 1, 1, fc))
            st.opaque = st.full = alpha >= 1.0
        else:
            box((0, 0, 0, 1, 0.5, 1, fc) if t == "bottom" else (0, 0.5, 0, 1, 1, 1, fc))
        return st
    if kind == "fence":
        box((0.375, 0, 0.375, 0.625, 1, 0.625, fc))
        for d in DIRS:
            if p.get(d) == "true":
                for y0, y1 in ((0.375, 0.5625), (0.75, 0.9375)):
                    r = {"north": (0.44, 0, 0.56, 0.375), "south": (0.44, 0.625, 0.56, 1),
                         "west": (0, 0.44, 0.375, 0.56), "east": (0.625, 0.44, 1, 0.56)}[d]
                    box((r[0], y0, r[1], r[2], y1, r[3], fc))
        return st
    if kind == "pane":
        c0, c1 = 0.4375, 0.5625
        box((c0, 0, c0, c1, 1, c1, fc))
        for d in DIRS:
            if p.get(d) == "true":
                r = {"north": (c0, 0, c1, c0), "south": (c0, c1, c1, 1), "west": (0, c0, c0, c1), "east": (c1, c0, 1, c1)}[d]
                box((r[0], 0, r[1], r[2], 1, r[3], fc))
        if "bars" in bid:
            st.alpha = 1.0
        return st
    if kind == "wall":
        if p.get("up", "true") == "true":
            box((0.25, 0, 0.25, 0.75, 1, 0.75, fc))
        for d in DIRS:
            v = p.get(d, "none")
            if v != "none":
                h = 1.0 if v == "tall" else 0.875
                r = {"north": (0.3125, 0, 0.6875, 0.5), "south": (0.3125, 0.5, 0.6875, 1),
                     "west": (0, 0.3125, 0.5, 0.6875), "east": (0.5, 0.3125, 1, 0.6875)}[d]
                box((r[0], 0, r[1], r[2], h, r[3], fc))
        return st
    if kind == "gate":
        ax = vlib.AXIS.get(f or "north")
        if ax == "z":       # 북/남을 보는 문 → x 로 뻗음
            posts = [(0, 0.3, 0.4375, 0.125, 1, 0.5625), (0.875, 0.3, 0.4375, 1, 1, 0.5625)]
            bars_ = [(0.125, 0.4, 0.4375, 0.875, 0.55, 0.5625), (0.125, 0.75, 0.4375, 0.875, 0.9, 0.5625)]
        else:
            posts = [(0.4375, 0.3, 0, 0.5625, 1, 0.125), (0.4375, 0.3, 0.875, 0.5625, 1, 1)]
            bars_ = [(0.4375, 0.4, 0.125, 0.5625, 0.55, 0.875), (0.4375, 0.75, 0.125, 0.5625, 0.9, 0.875)]
        for b in posts + ([] if p.get("open") == "true" else bars_):
            box(b + (fc,))
        return st
    if bid.endswith("_door"):
        f = f or "north"
        if p.get("open") == "true":
            sd = ccw(f) if p.get("hinge", "left") == "left" else cw(f)
        else:
            sd = opposite(f)
        box(_side_panel(sd, 0.1875) + (_faces(side, side),))
        return st
    if bid.endswith("_trapdoor"):
        if p.get("open") == "true":
            box(_side_panel(opposite(f or "north"), 0.1875) + (_faces(top, top),))
        elif p.get("half") == "top":
            box((0, 0.8125, 0, 1, 1, 1, _faces(top, top)))
        else:
            box((0, 0, 0, 1, 0.1875, 1, _faces(top, top)))
        return st
    if bid.endswith("_carpet") or bid in ("pale_moss_carpet",):
        box((0, 0, 0, 1, 0.0625, 1, _faces(top, top)))
        return st
    if bid == "snow":
        box((0, 0, 0, 1, int(p.get("layers", "1")) / 8.0, 1, _faces(top, side)))
        return st
    if bid in ("leaf_litter", "pink_petals", "wildflowers"):
        box((0, 0, 0, 1, 0.04, 1, _faces(accent, accent)))
        return st
    if bid.endswith("lantern") and "hanging" in p:
        glowc = _hex("ffc46b") if "soul" not in bid else _hex("7fe0ff")
        if "copper" in bid:
            glowc = _hex("b8ff9a")
        body = _faces(_mul(glowc, 0.95), glowc)
        frame = _faces(_hex("3a3632"), _hex("3a3632"))
        if p.get("hanging") == "true":
            box((0.3125, 0.0625, 0.3125, 0.6875, 0.5, 0.6875, body))
            box((0.3, 0.45, 0.3, 0.7, 0.56, 0.7, frame))
            box((0.45, 0.56, 0.45, 0.55, 1.0, 0.55, frame))
        else:
            box((0.3125, 0, 0.3125, 0.6875, 0.4375, 0.6875, body))
            box((0.3, 0.4, 0.3, 0.7, 0.5, 0.7, frame))
            box((0.42, 0.5, 0.42, 0.58, 0.6, 0.58, frame))
        return st
    if bid.endswith("candle") and "candles" in p:
        n = int(p.get("candles", "1"))
        spots = {1: [(0.5, 0.5)], 2: [(0.38, 0.5), (0.62, 0.5)], 3: [(0.38, 0.4), (0.62, 0.42), (0.5, 0.64)],
                 4: [(0.36, 0.36), (0.64, 0.36), (0.36, 0.64), (0.64, 0.64)]}[n]
        flame = _faces(_hex("fff0a0"), _hex("ffc060"))
        for i, (cx, cz) in enumerate(spots):
            h = 0.38 - 0.05 * (i % 2)
            box((cx - 0.0625, 0, cz - 0.0625, cx + 0.0625, h, cz + 0.0625, _faces(top, side)))
            if p.get("lit") == "true":
                box((cx - 0.035, h, cz - 0.035, cx + 0.035, h + 0.1, cz + 0.035, flame))
        return st
    if bid.endswith("torch"):
        flame = _faces(_hex("fff0a0"), _hex(LIGHTS.get(bid, (0, "ffc46b"))[1]))
        stick = _faces(_hex("8a6a3c"), _hex("6a5030"))
        if "wall" in bid and f:
            ox, oz = DXZ[opposite(f)]
            cx, cz = 0.5 + ox * 0.32, 0.5 + oz * 0.32
            box((cx - 0.0625, 0.2, cz - 0.0625, cx + 0.0625, 0.75, cz + 0.0625, stick))
            box((cx - 0.08, 0.75, cz - 0.08, cx + 0.08, 0.92, cz + 0.08, flame))
        else:
            box((0.4375, 0, 0.4375, 0.5625, 0.6, 0.5625, stick))
            box((0.42, 0.6, 0.42, 0.58, 0.78, 0.58, flame))
        return st
    if bid in ("end_rod",) or bid.endswith("lightning_rod"):
        ax = {"up": "y", "down": "y", "north": "z", "south": "z", "east": "x", "west": "x"}.get(f or "up", "y")
        c = _faces(top, side) if bid != "end_rod" else _faces(_hex("fffaf0"), _hex("f0e8e0"))
        box(_axis_box(ax, 0.4375, 0.5625) + (c,))
        return st
    if bid.endswith("_chain"):
        box(_axis_box(p.get("axis", "y"), 0.42, 0.58) + (_faces(side, side),))
        return st
    if bid.endswith("_bed"):
        wcol = block_colors((dye_of(bid) or "red") + "_wool")[1]
        box((0, 0.1875, 0, 1, 0.5625, 1, _faces(wcol, _mul(wcol, 0.9))))
        box((0.05, 0, 0.05, 0.95, 0.1875, 0.95, _faces(_hex("8a6a40"), _hex("6a5030"))))
        if p.get("part") == "head":
            hx = {"north": (0.12, 0.08, 0.88, 0.42), "south": (0.12, 0.58, 0.88, 0.92),
                  "west": (0.08, 0.12, 0.42, 0.88), "east": (0.58, 0.12, 0.92, 0.88)}[f or "north"]
            box((hx[0], 0.5625, hx[1], hx[2], 0.66, hx[3], _faces(_hex("f4f4f0"), _hex("e0e0dc"))))
        return st
    if bid.endswith("_banner"):
        wcol = block_colors((dye_of(bid) or "white") + "_wool")[1]
        cloth = _faces(wcol, wcol)
        stripe = None
        if extra:   # 무늬 첫 색으로 가운데 띠
            stripe = _faces(_hex(ACCENTS.get(extra, "ffffff")), _hex(ACCENTS.get(extra, "ffffff")))
        pole = _faces(_hex("8a6a3c"), _hex("6a5030"))
        if bid.endswith("_wall_banner"):
            sd = opposite(f or "north")
            box(_side_panel(sd, 0.0625, -0.92, 0.9, 0.06) + (cloth,))
            if stripe:
                pn = _side_panel(sd, 0.075, -0.6, 0.6, 0.36)
                box(pn + (stripe,))
            box(_side_panel(sd, 0.11, 0.86, 0.96, 0.0) + (pole,))
        else:
            d = _cardinal16(p.get("rotation", "0"))
            box((0.4375, 0, 0.4375, 0.5625, 1.85, 0.5625, pole))
            pl = {"north": (0.06, 0.25, 0.56, 0.94, 1.8, 0.62), "south": (0.06, 0.25, 0.38, 0.94, 1.8, 0.44),
                  "west": (0.56, 0.25, 0.06, 0.62, 1.8, 0.94), "east": (0.38, 0.25, 0.06, 0.44, 1.8, 0.94)}[d]
            box(pl + (cloth,))
        return st
    if bid.endswith("_sign"):
        wood = wood_of(bid)
        pc = block_colors(wood + "_planks")[1] if vlib.known(wood + "_planks") else side
        board = _faces(_mul(pc, 1.05), pc)
        post = _faces(_mul(pc, 0.8), _mul(pc, 0.8))
        if bid.endswith("_wall_hanging_sign"):
            sd = f or "north"
            r = _rot_box((0.06, 0.0, 0.44, 0.94, 0.62, 0.56), sd)
            box(r + (board,))
            box(_rot_box((0, 0.86, 0.44, 1, 0.96, 0.56), sd) + (post,))
        elif bid.endswith("_hanging_sign"):
            d = _cardinal16(p.get("rotation", "0"))
            box(_rot_box((0.06, 0.0, 0.44, 0.94, 0.62, 0.56), d) + (board,))
            for cx in (0.2, 0.8):
                box(_rot_box((cx - 0.03, 0.62, 0.47, cx + 0.03, 1.0, 0.53), d) + (post,))
        elif bid.endswith("_wall_sign"):
            box(_side_panel(opposite(f or "north"), 0.125, 0.28, 0.78) + (board,))
        else:
            d = _cardinal16(p.get("rotation", "0"))
            box((0.4375, 0, 0.4375, 0.5625, 0.56, 0.5625, post))
            box(_rot_box((0, 0.56, 0.44, 1, 1.0, 0.56), d) + (board,))
        return st
    if bid in ("campfire", "soul_campfire"):
        box((0, 0, 0, 1, 0.4375, 1, _faces(_hex("6a5236"), _hex("4a3a28"))))
        if p.get("lit") == "true":
            fl = _hex("ffb040") if bid == "campfire" else _hex("70e0ff")
            box((0.25, 0.4375, 0.25, 0.75, 0.85, 0.75, _faces(_mul(fl, 1.05), fl)))
        return st
    if bid in ("cauldron", "water_cauldron", "lava_cauldron", "powder_snow_cauldron"):
        box((0, 0, 0, 1, 1, 1, _faces(top, side)))
        return st
    if bid == "ladder" or (bid.endswith("vine") and "up" in p) or bid in ("glow_lichen", "sculk_vein", "resin_clump"):
        c = _faces(side, side)
        if bid == "ladder":
            box(_side_panel(opposite(f or "north"), 0.0625) + (c,))
        else:
            for d in DIRS:
                if p.get(d) == "true":
                    box(_side_panel(d, 0.0625) + (c,))
            if p.get("up") == "true":
                box((0, 0.94, 0, 1, 1, 1, c))
            if p.get("down") == "true":
                box((0, 0, 0, 1, 0.06, 1, c))
        return st
    if bid.startswith("potted_") or bid == "flower_pot":
        pot = _faces(_hex("8a4a36"), _hex("74402e"))
        box((0.3125, 0, 0.3125, 0.6875, 0.375, 0.6875, pot))
        if bid.startswith("potted_"):
            plant = bid[7:]
            pcol = block_colors(plant)[2] if vlib.known(plant) else _hex("50a040")
            stem = _hex("4f8a30")
            if plant in FLOWERISH:
                st.bills.append(("flower", 0.5, stem, pcol, 0.375))
            else:
                st.bills.append(("bush", 0.45, block_colors(plant)[1] if vlib.known(plant) else stem, None, 0.375))
        return st
    if bid.endswith("pressure_plate"):
        box((0.0625, 0, 0.0625, 0.9375, 0.0625, 0.9375, _faces(top, side)))
        return st
    if bid.endswith("rail"):
        box((0, 0, 0, 1, 0.0625, 1, _faces(top, top)))
        return st
    if bid == "bell":
        box((0.3125, 0.25, 0.3125, 0.6875, 0.75, 0.6875, _faces(_hex("f0c848"), _hex("d8a838"))))
        box(_rot_box((0, 0.8, 0.44, 1, 0.92, 0.56), f or "north") + (_faces(_hex("5a4a3a"), _hex("4a3c2e")),))
        return st
    if bid in ("chest", "trapped_chest", "ender_chest"):
        box((0.0625, 0, 0.0625, 0.9375, 0.875, 0.9375, _faces(top, side)))
        box(_rot_box((0.44, 0.45, 0.0, 0.56, 0.7, 0.07), f or "north") + (_faces(_hex("c0c0c0"), _hex("a0a0a0")),))
        return st
    # 십자형 식물 → 화면 정면 판
    shp = shapes.get(bid)
    if (shp and shp[6] == "cross") or bid in ("sugar_cane", "bamboo", "kelp", "kelp_plant", "seagrass",
                                               "tall_seagrass", "small_dripleaf", "spore_blossom"):
        green = side
        half = p.get("half")
        if bid in ("sugar_cane", "bamboo") or "vines" in bid:
            st.bills.append(("cane", 1.0, green, None, 0.0))
        elif bid == "cobweb":
            st.bills.append(("web", 0.9, _hex("f0f0f0"), None, 0.0))
        elif "amethyst" in bid:
            st.bills.append(("crystal", 0.7 if bid == "amethyst_cluster" else 0.45, _hex("b088e0"), _hex("e0c8ff"), 0.0))
        elif "mushroom" in bid or "fungus" in bid:
            st.bills.append(("mushroom", 0.45, _hex("e0d8c8"), accent, 0.0))
        elif bid in FLOWERISH or bid in ("rose_bush", "peony", "lilac", "sunflower", "torchflower", "pitcher_plant"):
            stem = _hex("4f8a30")
            if half == "lower":
                st.bills.append(("grass", 1.0, stem, None, 0.0))
            else:
                big = half == "upper"
                bloom = _hex(BLOOMS[bid]) if bid in BLOOMS else accent
                st.bills.append(("flower", 0.75 if big else 0.62, stem, bloom, 0.0, big))
        elif "sapling" in bid or bid in ("bush", "firefly_bush", "sweet_berry_bush", "dead_bush"):
            st.bills.append(("bush", 0.7, green, accent if bid == "sweet_berry_bush" else None, 0.0))
        else:
            h = 1.0 if half == "lower" else (0.85 if half == "upper" else 0.6)
            st.bills.append(("grass", h, green, None, 0.0))
        return st
    if vlib.is_full(bid):
        box((0, 0, 0, 1, 1, 1, fc))
        st.full = True
        st.opaque = alpha >= 1.0
        st.tex = bid in vlib.tag("leaves") or bid in ("azalea_leaves", "flowering_azalea_leaves", "moss_block")
        return st
    if shp:
        b = tuple(v / 16.0 for v in shp[:6])
        b = (max(0, b[0]), max(0, b[1]), max(0, b[2]), min(1, b[3]), min(1.5, b[4]), min(1, b[5]))
        if f in DXZ:
            b = _rot_box(b, f)
        box(b + (fc,))
        return st
    box((0, 0, 0, 1, 1, 1, fc))
    st.full = True
    st.opaque = alpha >= 1.0
    return st


# 표시용 가짜 블록 (마커·지면)
def _pseudo_style(state):
    st = Style(state)
    kind, _, arg = state[1:].partition(":")
    if kind == "npc":
        h = zlib.crc32(arg.encode()) & 0xFFFFFF
        body = vivid(((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF), 1.6, 1.2)
        body = tuple(60 + v * 0.7 for v in body)
        st.boxes.append((0.3, 0, 0.36, 0.7, 1.25, 0.64, _faces(body, body)))
        st.boxes.append((0.33, 1.25, 0.33, 0.67, 1.75, 0.67, _faces(_hex("f0c8a0"), _hex("e0b088"))))
        st.boxes.append((0.32, 1.62, 0.32, 0.68, 1.8, 0.68, _faces(_hex("4a3020"), _hex("4a3020"))))
    elif kind == "spawn":
        st.boxes.append((0.1, 0, 0.1, 0.9, 0.06, 0.9, _faces(_hex("60ff90"), _hex("40d070"))))
        st.light = (12, _hex("60ff90"))
    elif kind == "entrance":
        st.boxes.append((0.05, 0, 0.05, 0.95, 0.06, 0.95, _faces(_hex("c080ff"), _hex("a060e0"))))
        st.light = (14, _hex("c080ff"))
    elif kind == "interact":
        st.boxes.append((0.38, 1.12, 0.38, 0.62, 1.36, 0.62, _faces(_hex("ffe040"), _hex("e0c020"))))
    elif kind == "ambient":
        col = {"portal": "c060ff", "embers": "ff8020", "fountain": "80d0ff", "magic": "ffe0ff", "smoke": "b0b0b0"}
        st.light = (9, _hex(col.get(arg, "ffffff")))
    elif kind == "ground":
        g = {"a": _hex("6c9a40"), "b": _hex("638f3a"), "o": _hex("566e3e")}.get(arg, _hex("6c9a40"))
        st.boxes.append((0, 0, 0, 1, 1, 1, _faces(g, _hex("86704a"))))
        st.full = st.opaque = True
    elif kind == "dirt":
        st.boxes.append((0, 0, 0, 1, 1, 1, _faces(_hex("86603e"), _hex("7a573a"))))
        st.full = st.opaque = True
    return st


def _box_order(boxes):
    """한 칸 안 상자들의 그리기 순서 (보는 쪽 +a,+b,+y 에서 뒤에 있는 것 먼저)."""
    n = len(boxes)
    if n <= 1:
        return boxes
    before = {i: set() for i in range(n)}
    eps = 1e-6
    for i in range(n):
        a0, a1, b0, b1, y0, y1 = boxes[i][:6]
        for j in range(n):
            if i == j:
                continue
            c0, c1, d0, d1, z0, z1 = boxes[j][:6]
            if a1 <= c0 + eps or b1 <= d0 + eps or y1 <= z0 + eps:
                before[j].add(i)       # i 를 j 보다 먼저
    out, done = [], set()
    while len(out) < n:
        ready = [i for i in range(n) if i not in done and before[i] <= done]
        if not ready:                  # 순환(겹치는 상자) → 남은 것 아무 순서
            ready = [min(i for i in range(n) if i not in done)]
        for i in ready:
            done.add(i)
            out.append(boxes[i])
    return out


_POLY_CACHE = {}
_TEX = (1.12, 0.86, 1.0, 0.72)


def _subquads(q, fk, col, variant, out):
    """사각 면 q(4점)를 2×2 로 나눠 얼룩진 색으로."""
    p0, p1, p2, p3 = q
    lerp = lambda a, b, t: (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    grid = [[lerp(lerp(p0, p3, v), lerp(p1, p2, v), u) for u in (0, 0.5, 1)] for v in (0, 0.5, 1)]
    k = 0
    for j in range(2):
        for i in range(2):
            f = _TEX[(k + variant + fk) % 4]
            c = (int(min(255, col[0] * f)), int(min(255, col[1] * f)), int(min(255, col[2] * f)), col[3])
            out.append(([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]], c, fk))
            k += 1


def view_polys(st, view, mask, S, variant=0):
    """칸 원점 기준 화면 다각형 목록 [(점들, rgba, 면)] — (상태, 시점, 가림 마스크) 마다 한 번."""
    if not st.tex:
        variant = 0
    key = (id(st), view, mask, S, variant)
    r = _POLY_CACHE.get(key)
    if r is not None:
        return r
    V = VIEWS[view]
    la, lb = V["la"], V["lb"]
    vb = []
    for (x0, y0, z0, x1, y1, z1, col) in st.boxes:
        aa = sorted((la(x0, z0), la(x1, z1)))
        bb = sorted((lb(x0, z0), lb(x1, z1)))
        vb.append((aa[0], aa[1], bb[0], bb[1], y0, y1, col))
    out = []
    alpha = int(round(st.alpha * 255))
    for a0, a1, b0, b1, y0, y1, col in _box_order(vb):
        if isinstance(col, dict):
            ct, ca, cb = col["up"], col[V["fa"]], col[V["fb"]]
        else:
            ct = ca = cb = col

        def P(a, b, y):
            return ((a - b) * S, (a + b) * S / 2.0 - y * S)

        faces = []
        if not (mask & 2):
            faces.append(([P(a1, b0, y0), P(a1, b1, y0), P(a1, b1, y1), P(a1, b0, y1)], _rgba(ca, SHADE_A, alpha), 1))
        if not (mask & 4):
            faces.append(([P(a0, b1, y0), P(a1, b1, y0), P(a1, b1, y1), P(a0, b1, y1)], _rgba(cb, SHADE_B, alpha), 2))
        if not (mask & 1):
            faces.append(([P(a0, b0, y1), P(a1, b0, y1), P(a1, b1, y1), P(a0, b1, y1)], _rgba(ct, SHADE_TOP, alpha), 0))
        if st.tex:
            for q, c, fk in faces:
                _subquads(q, fk, c, variant, out)
        else:
            out.extend(faces)
    _POLY_CACHE[key] = out
    return out


def _rgba(c, f, a):
    return (int(min(255, c[0] * f)), int(min(255, c[1] * f)), int(min(255, c[2] * f)), a)


def _draw_bill(draw, bill, cx, cy, S, jit):
    """십자형 식물을 화면 정면 판으로 (cx, cy = 칸 바닥 가운데의 화면 좌표)."""
    kind, h, c1, c2, base = bill[:5]
    cy -= base * S
    col = lambda c, f=1.0: (int(min(255, c[0] * f * jit)), int(min(255, c[1] * f * jit)), int(min(255, c[2] * f * jit)), 255)
    if kind == "grass":
        w = 0.55 * S
        pts = [(cx - w, cy), (cx - w * 0.55, cy - h * S), (cx - w * 0.1, cy - h * S * 0.55), (cx + w * 0.15, cy - h * S * 1.02),
               (cx + w * 0.45, cy - h * S * 0.5), (cx + w * 0.7, cy - h * S * 0.9), (cx + w, cy)]
        draw.polygon(pts, fill=col(c1))
        draw.line([(cx - w * 0.2, cy), (cx + w * 0.15, cy - h * S * 0.95)], fill=col(c1, 0.75), width=max(1, int(S / 10)))
    elif kind == "flower":
        big = len(bill) > 5 and bill[5]
        sw = max(1, int(S / 9))
        draw.line([(cx, cy), (cx, cy - h * S)], fill=col(c1, 0.9), width=sw)
        draw.polygon([(cx - 0.3 * S, cy), (cx, cy - 0.3 * S), (cx + 0.3 * S, cy)], fill=col(c1))
        r = (0.3 if big else 0.22) * S
        bx, by = cx, cy - h * S
        draw.ellipse([bx - r, by - r * 0.85, bx + r, by + r * 0.85], fill=col(c2), outline=col(c2, 0.7))
        draw.ellipse([bx - r * 0.35, by - r * 0.3, bx + r * 0.35, by + r * 0.3], fill=col((255, 230, 120)))
    elif kind == "bush":
        r = 0.36 * S
        by = cy - h * S * 0.55
        draw.ellipse([cx - r, by - r, cx + r, by + r * 0.9], fill=col(c1), outline=col(c1, 0.7))
        draw.line([(cx, cy), (cx, by + r * 0.6)], fill=col((110, 80, 50)), width=max(1, int(S / 8)))
        if c2:
            for ox, oy in ((-0.35, -0.2), (0.3, 0.1), (0.05, -0.45)):
                draw.ellipse([cx + ox * r - 1.5, by + oy * r - 1.5, cx + ox * r + 1.5, by + oy * r + 1.5], fill=col(c2))
    elif kind == "cane":
        for ox in (-0.25, 0.05, 0.3):
            draw.line([(cx + ox * S, cy), (cx + ox * S * 0.8, cy - h * S)], fill=col(c1), width=max(1, int(S / 7)))
    elif kind == "web":
        w = 0.5 * S
        for a, b in (((-w, 0), (w, -h * S)), ((w, 0), (-w, -h * S)), ((0, 0), (0, -h * S))):
            draw.line([(cx + a[0], cy + a[1]), (cx + b[0], cy + b[1])], fill=(240, 240, 240, 150), width=1)
    elif kind == "crystal":
        for ox, hh in ((-0.25, 0.7), (0.0, 1.0), (0.25, 0.75)):
            x = cx + ox * S
            draw.polygon([(x - 0.1 * S, cy), (x, cy - h * hh * S), (x + 0.1 * S, cy)], fill=col(c2 if ox == 0 else c1))
    elif kind == "mushroom":
        draw.rectangle([cx - 0.06 * S, cy - h * S * 0.7, cx + 0.06 * S, cy], fill=col(c1))
        r = 0.25 * S
        draw.pieslice([cx - r, cy - h * S - r * 0.5, cx + r, cy - h * S + r * 1.1], 180, 360, fill=col(c2))


# ─────────────────────────────── 장면 ───────────────────────────────

class Scene:
    """cells: (x,y,z) → 블록 문자열 (또는 '#npc:id' 같은 표시용). marks: 표시용 칸 + 라벨."""

    def __init__(self, title=""):
        self.cells = {}
        self.extra = {}            # (x,y,z) → 깃발 무늬 첫 색 등
        self.marks = []            # (x, y, z, pseudo_state, label)
        self.labels = []           # (x, y, z, text, color)
        self.title = title

    def put(self, x, y, z, s):
        if s == "." or s.startswith("minecraft:air") or s.startswith("minecraft:cave_air") or s.startswith("minecraft:void_air"):
            self.cells.pop((x, y, z), None)
        else:
            self.cells[(x, y, z)] = s

    def add_markers(self, markers, ox, oy, oz):
        for m in markers:
            t = m["type"]
            if t == "interact":
                for p in m["pos"]:
                    self.marks.append((ox + p[0], oy + p[1], oz + p[2], "#interact", None))
                self.labels.append((ox + m["pos"][0][0], oy + m["pos"][0][1] + 1, oz + m["pos"][0][2],
                                    "[" + m["action"] + "]", (255, 230, 90)))
                continue
            x, y, z = m["pos"]
            x, y, z = ox + x, oy + y, oz + z
            if t == "npc":
                self.marks.append((x, y, z, "#npc:" + m["id"], None))
                self.labels.append((x, y + 2, z, m["id"], (255, 255, 255)))
            elif t == "spawn":
                self.marks.append((x, y, z, "#spawn", None))
                self.labels.append((x, y, z, "spawn", (120, 255, 150)))
            elif t == "entrance":
                self.marks.append((x, y, z, "#entrance", None))
                self.labels.append((x, y, z, "entrance", (220, 160, 255)))
            elif t == "ambient":
                self.marks.append((x, y, z, "#ambient:" + m["fx"], None))
            elif t == "banner" and m.get("patterns"):
                self.extra[(x, y, z)] = m["patterns"][0][1]


def scene_from_blueprint(bp, rot=0, ground=True, margin=2, labels=True):
    cells, markers, (w, d) = bp.rotated(rot)
    sc = Scene("%s · %s · %dx%dx%d" % (bp.id, bp.name, bp.W, bp.H, bp.D))
    fy = bp.floor_y
    if ground:
        y_lo = min(0, fy - 2)
        for x in range(-margin, w + margin):
            for z in range(-margin, d + margin):
                for y in range(y_lo, fy + 1):
                    if (x, y, z) in cells:
                        continue
                    sc.cells[(x, y, z)] = ("#ground:" + ("a" if (x + z) % 2 == 0 else "b")) if y == fy else "#dirt"
    for (x, y, z), s in cells.items():
        if s != ".":
            sc.cells[(x, y, z)] = s
    if labels:
        sc.add_markers(markers, 0, 0, 0)
    return sc


def layout_placements(layout, blueprints):
    """layout 의 조각들 → [(항목, Blueprint, 회전, 원점 x, 원점 z, 발자국 w, d, 단 높이 P)] (마을 좌표, H0 = 0)."""
    out = []
    terraces = layout.get("terraces", [])
    for e in layout["pieces"]:
        bp = blueprints[e["piece"]]
        r = vlib.front_rotation(e.get("front", "north"))
        w, d = vlib.rotated_size(bp.W, bp.D, r)
        ax, az = e["at"]
        ox, oz = ax - w // 2, az - d // 2
        if "dy" in e:
            P = e["dy"]
        else:
            P = 0
            for t in terraces:
                tx, tz = t["at"]
                tw, td = t["size"]
                if tx - tw // 2 <= ax < tx - tw // 2 + tw and tz - td // 2 <= az < tz - td // 2 + td:
                    P = t["dy"]
        out.append((e, bp, r, ox, oz, w, d, P))
    return out


def scene_from_layout(layout, blueprints, labels=True, margin=8):
    R = layout.get("radius", 32)
    E = R + margin
    sc = Scene("%s · 반경 %d · 조각 %d" % (layout.get("name", "마을"), R, len(layout["pieces"])))
    places = layout_placements(layout, blueprints)
    fixed = {}
    for t in layout.get("terraces", []):
        tx, tz = t["at"]
        tw, td = t["size"]
        for x in range(tx - tw // 2, tx - tw // 2 + tw):
            for z in range(tz - td // 2, tz - td // 2 + td):
                fixed[(x, z)] = t["dy"]
    foot = set()
    for e, bp, r, ox, oz, w, d, P in places:
        for x in range(ox - 1, ox + w + 1):
            for z in range(oz - 1, oz + d + 1):
                fixed[(x, z)] = P
                if ox <= x < ox + w and oz <= z < oz + d:
                    foot.add((x, z))
    # 목표 높이장 근사: 고정 칸에서 멀어질수록 이웃 차 ≤1 로 0 쪽으로
    h = {}
    for x in range(-E, E + 1):
        for z in range(-E, E + 1):
            h[(x, z)] = fixed.get((x, z), 0)
    for _ in range(40):
        changed = False
        for x in range(-E, E + 1):
            for z in range(-E, E + 1):
                if (x, z) in fixed:
                    continue
                v = h[(x, z)]
                nb = [h[(x + dx, z + dz)] for dx, dz in DXZ.values() if (x + dx, z + dz) in h]
                lo, hi = max(nb) - 1, min(nb) + 1
                nv = v
                if nv < lo:
                    nv = lo
                if nv > hi:
                    nv = hi
                if nv != v:
                    h[(x, z)] = nv
                    changed = True
        if not changed:
            break
    ymin = min(h.values()) - 3
    # 길
    styles = layout.get("path_styles", {})
    path_top = {}
    for pth in layout.get("paths", []):
        mix = styles.get(pth.get("style", "main"), [["minecraft:dirt_path", 1]])
        m = vlib.Mix([(b, w_) for b, w_ in mix])
        for c in vlib.path_cells(pth["points"], pth.get("width", 3)):
            if c in foot or c not in h:
                continue
            path_top[c] = m.pick(c[0], 0, c[1], 7)
    wallmix = vlib.mix(("stone_bricks", 3), ("mossy_stone_bricks", 1), ("cobblestone", 1))
    for (x, z), hv in h.items():
        nmin = min([h.get((x + dx, z + dz), ymin) for dx, dz in DXZ.values()])
        lo = ymin if (abs(x) == E or abs(z) == E) else max(ymin, nmin - 1)
        for y in range(lo, hv + 1):
            if y == hv:
                hh = ((x * 73856093) ^ (z * 19349663)) & 0xFF
                g = "o" if x * x + z * z > R * R else ("b" if hh % 5 == 0 else "a")   # 반경 밖은 어둡게
                s = path_top.get((x, z)) or ("#ground:" + g)
            elif hv - y <= 3 and hv - nmin >= 2 and y > nmin and (x, z) in fixed:
                s = wallmix.pick(x, y, z)
            else:
                s = "#dirt"
            sc.cells[(x, y, z)] = s
    for e, bp, r, ox, oz, w, d, P in places:
        cells, markers, _ = bp.rotated(r)
        oy = P - bp.floor_y
        for (x, y, z), s in cells.items():
            wx, wy, wz = ox + x, oy + y, oz + z
            if s == ".":
                sc.cells.pop((wx, wy, wz), None)
            else:
                sc.cells[(wx, wy, wz)] = s
        # ' ' 칸 중 단 위쪽은 공기 (평지 렌더에서 지형은 단 높이까지만)
        if labels:
            sc.add_markers(markers, ox, oy, oz)
            sc.labels.append((ox + w // 2, oy + bp.H + 1, oz + d // 2, bp.id, (255, 240, 200)))
    return sc


def scene_from_dump(path):
    sc = Scene(os.path.basename(path))
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            pos, _, data = line.partition("|")
            try:
                x, y, z = (int(v) for v in pos.split())
            except ValueError:
                continue
            if not data.startswith("minecraft:"):
                data = "minecraft:" + data
            if data.startswith("minecraft:air") or data.startswith("minecraft:cave_air"):
                continue
            sc.cells[(x, y, z)] = data
    return sc


# ─────────────────────────────── 그리기 ───────────────────────────────

def _font(size):
    for path in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _text(draw, xy, text, font, fill=(255, 255, 255), anchor="la"):
    x, y = xy
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        draw.text((x + dx, y + dy), text, font=font, fill=(10, 10, 14), anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def _is_opaque(cells, key):
    s = cells.get(key)
    if s is None:
        return False
    return style_of(s).opaque


def _is_occ(cells, key):
    s = cells.get(key)
    if s is None:
        return False
    return style_of(s).occ


def render_iso(scene, view="ne", px=10, ss=None, labels=True, glow=True):
    """등각 렌더 → PIL Image (RGB)."""
    V = VIEWS[view]
    cells = scene.cells
    if not cells:
        return Image.new("RGB", (200, 100), (30, 34, 44))
    fA, fB = V["A"], V["B"]
    # 크기 계산 (블록당 px 자동 축소)
    amin = bmin = 10 ** 9
    smin_x = smin_y = 10 ** 9
    smax_x = smax_y = -10 ** 9
    for (x, y, z) in cells:
        A, Bc = fA(x, z), fB(x, z)
        u, v = A - Bc, A + Bc
        if u < smin_x:
            smin_x = u
        if u > smax_x:
            smax_x = u
        top = v / 2.0 - y - 1.9
        bot = (v + 2) / 2.0 - y + 1.0
        if top < smin_y:
            smin_y = top
        if bot > smax_y:
            smax_y = bot
    span_x = (smax_x - smin_x + 2.4)
    span_y = (smax_y - smin_y + 1.6)
    head = 34
    while px > 2 and (span_x * px > MAX_PX or span_y * px + head > MAX_PX):
        px -= 1
    if ss is None:
        ss = 2 if span_x * px * span_y * px < 2400 * 2400 else 1
    S = px * ss
    Wimg = int(span_x * S) + 1
    Himg = int(span_y * S) + 1 + head * ss
    off_x = (-smin_x + 1.2) * S
    off_y = (-smin_y + 0.8) * S + head * ss
    img = Image.new("RGB", (Wimg, Himg), (30, 34, 44))
    # 배경 위아래 그러데이션
    grad = Image.linear_gradient("L").resize((1, Himg))
    bg2 = Image.new("RGB", (Wimg, Himg), (18, 20, 28))
    img = Image.composite(bg2, img, grad.resize((Wimg, Himg)))
    draw = ImageDraw.Draw(img, "RGBA")

    items = []
    for (x, y, z), s in cells.items():
        A, Bc = fA(x, z), fB(x, z)
        items.append((A + Bc, y, A, 0, x, z, s))
    for (x, y, z, s, _) in scene.marks:
        A, Bc = fA(x, z), fB(x, z)
        items.append((A + Bc, y, A, 1, x, z, s))
    items.sort(key=lambda t: t[:4])
    dax, daz = V["da"]
    dbx, dbz = V["db"]
    lights = []
    salt = 0x9E3779B1
    for _, y, A, _o, x, z, s in items:
        st = style_of(s, scene.extra.get((x, y, z)))
        if not st.boxes and not st.bills and not st.light:
            continue
        mask = 0
        if st.full:
            if _is_opaque(cells, (x, y + 1, z)) or (not st.opaque and cells.get((x, y + 1, z)) == s):
                mask |= 1
            na = cells.get((x + dax, y, z + daz))
            if na is not None and (style_of(na).opaque or (not st.opaque and na == s)):
                mask |= 2
            nb = cells.get((x + dbx, y, z + dbz))
            if nb is not None and (style_of(nb).opaque or (not st.opaque and nb == s)):
                mask |= 4
            if mask == 7:
                continue
        Bc = fB(x, z)
        ox = (A - Bc) * S + off_x
        oy = (A + Bc) * S / 2.0 - y * S + off_y
        h = ((x * 73856093) ^ (y * 19349663) ^ (z * 83492791) ^ salt) & 0xFFFF
        jit = 0.95 + (h % 11) * 0.01
        if st.boxes:
            if st.full:
                # 간단한 그늘: 윗면은 옆 칸 위가 막힌 만큼, 옆면은 바로 앞 기둥 위(처마)가 덮였으면 어둡게
                n = 0
                for ex, ez in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if _is_occ(cells, (x + ex, y + 1, z + ez)):
                        n += 1
                fac = [1.0 - 0.07 * n, 1.0, 1.0]
                for k, (ex, ez) in ((1, (dax, daz)), (2, (dbx, dbz))):
                    if _is_occ(cells, (x + ex, y + 1, z + ez)) or _is_occ(cells, (x + ex, y + 2, z + ez)):
                        fac[k] = 0.8
                    elif not _is_occ(cells, (x + ex, y - 1, z + ez)) and (x + ex, y - 1, z + ez) not in cells:
                        fac[k] = 1.0
                    else:
                        fac[k] = 0.95
            else:
                fac = (1.0, 1.0, 1.0)
            for pts, col, fk in view_polys(st, view, mask, S, h & 3):
                f2 = jit * fac[fk]
                c = (int(col[0] * f2), int(col[1] * f2), int(col[2] * f2), col[3])
                if c[0] > 255 or c[1] > 255 or c[2] > 255:
                    c = (min(255, c[0]), min(255, c[1]), min(255, c[2]), c[3])
                poly = [(ox + px_, oy + py_) for px_, py_ in pts]
                if col[3] >= 255:
                    draw.polygon(poly, fill=c, outline=(int(c[0] * 0.86), int(c[1] * 0.86), int(c[2] * 0.86), 255))
                else:
                    draw.polygon(poly, fill=c)
        for bill in st.bills:
            _draw_bill(draw, bill, ox, oy + S / 2.0, S, jit)
        if st.light and glow:
            lights.append((x, y, z, ox, oy, st.light))
    if glow and lights:
        img = _apply_glow(img, lights, cells, V, S)
        draw = ImageDraw.Draw(img, "RGBA")
    if ss > 1:
        img = img.resize((Wimg // ss, Himg // ss), Image.LANCZOS)
    draw = ImageDraw.Draw(img, "RGBA")
    S1 = S / float(ss)
    if labels and scene.labels:
        font = _font(max(10, min(15, int(S1 * 0.7))))
        placed = []
        for (x, y, z, text, color) in scene.labels:
            A, Bc = fA(x, z), fB(x, z)
            lx = ((A - Bc) * S + off_x) / ss
            ly = ((A + Bc) * S / 2.0 - y * S + off_y) / ss + S1 * 0.5
            _label(draw, placed, lx, ly, text, font, color)
    _header(draw, scene.title, view, img.size, S1)
    return img


def _label(draw, placed, lx, ly, text, font, color):
    """라벨 하나 (아래 가운데 기준). 이미 놓인 라벨과 겹치면 위로 비켜 놓는다."""
    w_, h_ = draw.textbbox((0, 0), text, font=font)[2:]
    box = [lx - w_ / 2 - 2, ly - h_ - 2, lx + w_ / 2 + 2, ly + 2]
    for _ in range(12):
        if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in placed):
            break
        box[1] -= h_ + 2
        box[3] -= h_ + 2
    placed.append(box)
    _text(draw, (lx, box[3] - 2), text, font, color, anchor="ms")


def _apply_glow(img, lights, cells, V, S):
    glow = Image.new("RGB", img.size, (0, 0, 0))
    dax, daz = V["da"]
    dbx, dbz = V["db"]
    sprites = {}
    for (x, y, z, ox, oy, (lvl, col)) in lights:
        # 보는 쪽(+a,+b,+y) 대각선으로 불투명 블록이 막고 있으면 빛 생략
        hidden = False
        for i in range(1, 14):
            k = (x + (dax + dbx) * i, y + i, z + (daz + dbz) * i)
            if _is_occ(cells, k):
                hidden = True
                break
        if hidden:
            continue
        rad = int(S * (0.6 + lvl / 15.0 * 1.6))
        key = (rad, col)
        spr = sprites.get(key)
        if spr is None:
            n = rad * 2 + 1
            vals = []
            for j in range(n):
                for i in range(n):
                    d = math.hypot(i - rad, j - rad) / float(rad)
                    vals.append(int(255 * 0.6 * max(0.0, 1.0 - d) ** 2))
            mask = Image.new("L", (n, n))
            mask.putdata(vals)
            spr = Image.composite(Image.new("RGB", (n, n), col), Image.new("RGB", (n, n), (0, 0, 0)), mask)
            sprites[key] = spr
        cx, cy = int(ox), int(oy + S * 0.5)
        box = (cx - rad, cy - rad, cx + rad + 1, cy + rad + 1)
        if box[0] < 0 or box[1] < 0 or box[2] > img.size[0] or box[3] > img.size[1]:
            continue
        region = glow.crop(box)
        glow.paste(ImageChops.add(region, spr), box)
    return ImageChops.screen(img, glow)


def _header(draw, title, view, size, S1):
    font = _font(15)
    names = {"ne": "북동에서", "sw": "남서에서", "nw": "북서에서", "se": "남동에서", "top": "위에서"}
    _text(draw, (10, 8), "%s   [%s]" % (title, names.get(view, view)), font, (235, 235, 240))
    if view in VIEWS:
        # 북쪽 화살표: 월드 (0,0,-1) 방향의 화면 벡터
        V = VIEWS[view]
        a = V["A"](0, -1) - V["A"](0, 0)
        b = V["B"](0, -1) - V["B"](0, 0)
        vx, vy = (a - b), (a + b) / 2.0
        n = math.hypot(vx, vy) or 1
        vx, vy = vx / n, vy / n
        cx, cy = size[0] - 34, 30
        draw.line([(cx - vx * 14, cy - vy * 14), (cx + vx * 14, cy + vy * 14)], fill=(235, 235, 240, 255), width=2)
        draw.polygon([(cx + vx * 18, cy + vy * 18), (cx + vx * 9 - vy * 5, cy + vy * 9 + vx * 5),
                      (cx + vx * 9 + vy * 5, cy + vy * 9 - vx * 5)], fill=(255, 120, 100, 255))
        _text(draw, (cx + vx * 26, cy + vy * 26), "N", _font(12), (255, 140, 120), anchor="mm")


def render_top(scene, px=8, labels=True, grid=8):
    """위에서 본 평면도 (북쪽 위, x 오른쪽). 높이 음영 + 8칸 격자."""
    cols = {}
    for (x, y, z), s in scene.cells.items():
        st = style_of(s)
        if not st.boxes and not st.bills:
            continue
        c = cols.get((x, z))
        if c is None or y > c[0]:
            cols[(x, z)] = (y, s)
    for (x, y, z, s, _) in scene.marks:
        if s.startswith("#npc") or s.startswith("#spawn") or s.startswith("#entrance"):
            c = cols.get((x, z))
            if c is None or y >= c[0]:
                cols[(x, z)] = (y + 0.5, s)
    if not cols:
        return Image.new("RGB", (200, 100), (30, 34, 44))
    xs = [k[0] for k in cols]
    zs = [k[1] for k in cols]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    while px > 2 and max(x1 - x0 + 1, z1 - z0 + 1) * px > MAX_PX - 60:
        px -= 1
    head = 34
    Wimg, Himg = (x1 - x0 + 1) * px + 40, (z1 - z0 + 1) * px + 40 + head
    img = Image.new("RGB", (Wimg, Himg), (24, 26, 34))
    draw = ImageDraw.Draw(img, "RGBA")
    hs = sorted(c[0] for c in cols.values())
    hmed = hs[len(hs) // 2]
    for (x, z), (y, s) in cols.items():
        st = style_of(s)
        if st.boxes:
            top_box = max(st.boxes, key=lambda b: b[4])
            col = top_box[6]["up"] if isinstance(top_box[6], dict) else top_box[6]
        else:
            col = st.bills[0][3] or st.bills[0][2]
        yl = cols.get((x - 1, z), (y,))[0]
        yn = cols.get((x, z - 1), (y,))[0]
        shade = 1.0 + max(-0.25, min(0.25, (y - yl) * 0.07 + (y - yn) * 0.07)) + max(-0.15, min(0.15, (y - hmed) * 0.015))
        c = tuple(int(max(0, min(255, v * shade))) for v in col)
        X, Z = (x - x0) * px + 20, (z - z0) * px + 20 + head
        draw.rectangle([X, Z, X + px - 1, Z + px - 1], fill=c)
    gcol = (255, 255, 255, 38)
    for gx in range(x0 - x0 % grid, x1 + 1, grid):
        X = (gx - x0) * px + 20
        draw.line([(X, 20 + head), (X, Himg - 20)], fill=gcol if gx else (255, 200, 120, 90))
    for gz in range(z0 - z0 % grid, z1 + 1, grid):
        Z = (gz - z0) * px + 20 + head
        draw.line([(20, Z), (Wimg - 20, Z)], fill=gcol if gz else (255, 200, 120, 90))
    if labels:
        font = _font(max(10, min(15, px + 3)))
        placed = []
        for (x, y, z, text, color) in scene.labels:
            X, Z = (x - x0) * px + 20 + px / 2, (z - z0) * px + 20 + head + px
            _label(draw, placed, X, Z, text, font, color)
    _header(draw, scene.title, "top", img.size, px)
    _text(draw, (Wimg - 30, 10), "N↑", _font(13), (255, 140, 120))
    return img


def save_views(scene, out, views=("ne", "sw"), top=False, px=10, ss=None, labels=True):
    """장면을 시점별 PNG 로. 시점 하나·평면도 없음이면 out 그대로, 아니면 <out>_<view>.png. 쓴 경로 목록."""
    stem, ext = os.path.splitext(out)
    ext = ext or ".png"
    paths = []
    single = len(views) == 1 and not top
    for v in views:
        p = out if single else "%s_%s%s" % (stem, v, ext)
        render_iso(scene, v, px, ss, labels).save(p)
        paths.append(p)
    if top:
        p = "%s_top%s" % (stem, ext)
        render_top(scene, max(4, px - 2), labels).save(p)
        paths.append(p)
    return paths


def contact_sheet(images, captions, pad=12):
    font = _font(16)
    w = sum(im.size[0] for im in images) + pad * (len(images) + 1)
    h = max(im.size[1] for im in images) + pad * 2 + 24
    sheet = Image.new("RGB", (w, h), (14, 16, 22))
    d = ImageDraw.Draw(sheet)
    x = pad
    for im, cap in zip(images, captions):
        sheet.paste(im, (x, pad + 24))
        _text(d, (x + 4, pad), cap, font, (255, 220, 160))
        x += im.size[0] + pad
    return sheet


def main(argv=None):
    ap = argparse.ArgumentParser(description="마을 등각 렌더러 (VILLAGE.md §1)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--piece", help="조각 JSON")
    src.add_argument("--layout", help="layout.json (마을 전체, 평지 위)")
    src.add_argument("--dump", help="서버 덤프 (줄마다 'x y z|blockdata')")
    ap.add_argument("--pieces-dir", help="--layout 일 때 조각 JSON 폴더")
    ap.add_argument("--out", required=True, help="출력 PNG")
    ap.add_argument("--view", default="ne,sw", help="ne|sw|nw|se|all 또는 쉼표 목록 (기본 ne,sw)")
    ap.add_argument("--top", action="store_true", help="위에서 본 평면도 추가")
    ap.add_argument("--px", type=int, default=None, help="블록당 px (기본: 조각 자동, 마을·덤프 10)")
    ap.add_argument("--ss", type=int, default=None, help="안티에일리어싱 배율 (기본 자동)")
    ap.add_argument("--rotate", default="none", help="--piece: none|cw90|cw180|ccw90|all (all = 4방향 한 장)")
    ap.add_argument("--no-ground", action="store_true", help="--piece: 바닥 격자 빼기")
    ap.add_argument("--no-labels", action="store_true")
    a = ap.parse_args(argv)
    views = list(VIEWS) if a.view == "all" else [v.strip() for v in a.view.split(",") if v.strip()]
    for v in views:
        if v not in VIEWS:
            ap.error("모르는 시점: %s" % v)
    labels = not a.no_labels
    if a.piece:
        bp = vlib.Blueprint.load(a.piece)
        px = a.px or max(10, min(26, int(900 / (bp.W + bp.D + 4))))
        if a.rotate == "all":
            stem, ext = os.path.splitext(a.out)
            paths = []
            for v in views:
                ims = [render_iso(scene_from_blueprint(bp, r, not a.no_ground, labels=labels), v, px, a.ss, labels)
                       for r in range(4)]
                p = a.out if len(views) == 1 else "%s_%s%s" % (stem, v, ext or ".png")
                contact_sheet(ims, ["%s (front=%s)" % (vlib.ROTATIONS[r], DIRS[r]) for r in range(4)]).save(p)
                paths.append(p)
        else:
            sc = scene_from_blueprint(bp, vlib.rot_index(a.rotate), not a.no_ground, labels=labels)
            paths = save_views(sc, a.out, views, a.top, px, a.ss, labels)
    elif a.layout:
        if not a.pieces_dir:
            ap.error("--layout 에는 --pieces-dir 가 필요")
        with open(a.layout, encoding="utf-8") as f:
            layout = json.load(f)
        bps = {}
        for e in layout["pieces"]:
            if e["piece"] not in bps:
                bps[e["piece"]] = vlib.Blueprint.load(os.path.join(a.pieces_dir, e["piece"] + ".json"))
        sc = scene_from_layout(layout, bps, labels)
        paths = save_views(sc, a.out, views, a.top, a.px or 10, a.ss, labels)
    else:
        sc = scene_from_dump(a.dump)
        paths = save_views(sc, a.out, views, a.top, a.px or 10, a.ss or 1, labels)
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
