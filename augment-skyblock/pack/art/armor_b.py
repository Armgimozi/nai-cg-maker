"""
증강 스카이블럭 — 방어구 세트 B (보스/엔드게임): 서리 군주 / 화염 거신 / 공허 군주 / 프리즘.

세트마다 만드는 것
  - textures/entity/equipment/humanoid/<set>.png          (64x32, 흉갑 + 부츠, 바닐라 UV 배치, 머리 칸은 비움)
  - textures/entity/equipment/humanoid_leggings/<set>.png (64x32, 각반)
  - textures/item/armor/<set>_{chestplate,leggings,boots}.png (16x16 인벤토리 아이콘)
  - models/armor/<set>_helmet.json + items/armor/<set>_helmet.json (3D 투구, 머리에 조각 호박처럼 씀)
    투구 텍스처: textures/item/armor/<set>_helmet_tex.png (16프레임 애니메이션, item/ 폴더라 블록 아틀라스에 자동 포함)

몸 갑옷은 팔레트 글자 ASCII 픽셀 그림. 한 줄 = 부위 전개도 한 줄:
  body : [오른쪽 옆 4][앞 8][왼쪽 옆 4][뒤 8]   (UV x=16..40, y=20..32)
  arm  : [바깥 4][앞 4][안쪽 4][뒤 4]           (UV x=40..56, y=20..32)
  leg  : [바깥 4][앞 4][안쪽 4][뒤 4]           (UV x=0..16,  y=20..32)
팔레트 값이 함수(x, y) 이면 텍스처 좌표로 색을 정한다 (무지개 등).

투구 좌표: 모델 0..16, 중심 (8,8,8), 얼굴은 -Z(north). 머리 큐브는 대략 1.6..14.4.
투구 면 UV 는 '평면 투영' — 면의 실제 좌표로 재질 영역을 잘라 쓰므로 이웃 박스끼리 무늬가 이어진다.
"""
import colorsys
import math
import os
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from mc3d import FACE_LIGHT, Atlas, Model, _face_corners, _rot_matrix, mat  # noqa: E402

MODULE = "armor_b"
SETS = ["frostlord", "inferno", "sovereign", "prism"]
NAMES_KO = {"frostlord": "서리 군주", "inferno": "화염 거신", "sovereign": "공허 군주", "prism": "프리즘"}
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
STEVE = "/tmp/claude-0/work/ref/steve.png"
PREVIEW_DIR = os.path.join(HERE, "preview")
SCRATCH = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")

F = 16          # 투구 텍스처 프레임 수
FT = 2          # 프레임당 틱 → 32틱(1.6초) 주기
TAU = 2 * math.pi


def _rng(*k):
    return np.random.default_rng(zlib.crc32(repr(k).encode()))


def C(h):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], dtype=float)


def HSV(h, s, v):
    return np.array(colorsys.hsv_to_rgb(h % 1.0, s, v)) * 255.0


def _grid(w, h):
    return np.meshgrid(np.arange(w, dtype=float), np.arange(h, dtype=float))


def _lerp3(stops, t):
    """stops: [(t, rgb)], t 배열 → 색 배열 (h,w,3)"""
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        m = (t >= t0) & (t <= t1)
        k = ((t - t0) / max(1e-6, t1 - t0))[..., None]
        out[m] = (c0 + (c1 - c0) * k)[m]
    return out


def _vnoise(w, h, cell, seed, periodic_y=None):
    """값 노이즈 (0..1). periodic_y 를 주면 세로로 이어지게 만든다."""
    r = _rng("vn", w, h, cell, seed)
    gw, gh = w // cell + 2, h // cell + 2
    if periodic_y:
        gh = periodic_y // cell
    g = r.random((gh, gw))
    X, Y = _grid(w, h)
    gx, gy = X / cell, Y / cell
    x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
    fx, fy = gx - x0, gy - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)

    def G(yy, xx):
        return g[yy % gh, np.clip(xx, 0, gw - 1)]
    a = G(y0, x0) * (1 - fx) + G(y0, x0 + 1) * fx
    b = G(y0 + 1, x0) * (1 - fx) + G(y0 + 1, x0 + 1) * fx
    return a * (1 - fy) + b * fy


def _rgba(rgb, a=255.0):
    h, w = rgb.shape[:2]
    out = np.zeros((h, w, 4))
    out[..., :3] = rgb
    out[..., 3] = a
    return out


def _shine(f, w, h, amt=0.45, width=2.2, speed=1.0, ph=0.0):
    """대각선 광택 띠가 지나간다 (한 주기의 절반 동안만 보임)."""
    X, Y = _grid(w, h)
    c = (((f / F) * speed + ph) % 1.0 * 2.0 - 0.3) * (w + h)
    d = np.abs((X + Y) - c)
    return np.clip(1 - d / width, 0, 1) * amt


def _pulse(f, speed=1, ph=0.0):
    return 0.5 + 0.5 * math.sin(TAU * (f / F * speed + ph))


# ═══════════════════════════════ 투구 재질 (painter(f, w, h) -> (h,w,4)) ═══════════════════════════════

def M_metal(base, hi, lo, seed=0, shine=0.4, brushed=True, bevel=False):
    base, hi, lo = C(base), C(hi), C(lo)

    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 3, seed) - 0.5
        r = _rng("metal", seed, w, h)
        streak = (r.random((h, 1)) - 0.5) * 0.18 if brushed else 0
        t = 0.62 - 0.22 * (Y / max(1, h - 1)) + n * 0.22 + streak + (r.random((h, w)) - 0.5) * 0.06
        if bevel:
            t = t + 0.25 * ((X == 0) | (Y == 0)) - 0.3 * ((X == w - 1) | (Y == h - 1))
        t = t + _shine(f, w, h, shine)
        rgb = _lerp3([(0, lo), (0.55, base), (1, hi)], t)
        return _rgba(rgb)
    return p


def M_fur(white, shade, spot, seed=0):
    white, shade, spot = C(white), C(shade), C(spot)

    def p(f, w, h):
        X, Y = _grid(w, h)
        r = _rng("fur", seed, w, h)
        strands = r.random((1, w)) * 0.5 + _vnoise(w, h, 2, seed) * 0.6
        t = np.clip(0.35 + strands * 0.7 - 0.25 * (Y / h), 0, 1)
        rgb = shade + (white - shade) * t[..., None]
        # 담비 꼬리 무늬 (작은 세로 검은 점)
        for (sx, sy) in [(2, 3), (9, 1), (13, 9), (5, 11), (11, 13), (1, 14), (7, 6)]:
            if sx < w and sy < h:
                rgb[sy, sx] = spot
                if sy + 1 < h:
                    rgb[sy + 1, sx] = spot * 1.3
        return _rgba(rgb)
    return p


def M_ice(light, mid, deep, seed=0, sparkle=0.08, alpha=255):
    light, mid, deep = C(light), C(mid), C(deep)

    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 4, seed)
        facet = ((X * 0.7 + Y * 1.3 + n * 6) % 7 < 1.0) * 0.35
        t = 0.75 - 0.5 * (Y / max(1, h - 1)) + (n - 0.5) * 0.3 + facet
        t = t + _shine(f, w, h, 0.55, 2.5, ph=seed * 0.13)
        rgb = _lerp3([(0, deep), (0.5, mid), (1, light)], t)
        r = _rng("ice-sp", seed, w, h)
        pts = r.random((h, w)) < sparkle
        ph = r.random((h, w))
        tw = np.clip(np.sin(TAU * (f / F + ph)) * 2 - 1, 0, 1)
        rgb = rgb + (255 - rgb) * (pts * tw)[..., None]
        return _rgba(rgb, alpha)
    return p


def M_gem(dark, mid, light, seed=0, speed=1):
    dark, mid, light = C(dark), C(mid), C(light)

    def p(f, w, h):
        X, Y = _grid(w, h)
        cx, cy = (w - 1) / 2, (h - 1) / 2
        d = np.sqrt(((X - cx) / (w / 2)) ** 2 + ((Y - cy) / (h / 2)) ** 2)
        pl = _pulse(f, speed, seed * 0.17)
        t = np.clip(1.05 - d * 0.75, 0, 1) * (0.75 + 0.35 * pl)
        rgb = _lerp3([(0, dark), (0.55, mid), (1, light)], t)
        hl = (np.abs(X - cx * 0.55) < 1) & (np.abs(Y - cy * 0.55) < 1)
        rgb[hl] = 255
        return _rgba(rgb)
    return p


def M_basalt(seed=0):
    k, b, B = C("1a1615"), C("2f2927"), C("4a413c")

    def p(f, w, h):
        X, Y = _grid(w, h)
        r = _rng("bas", seed, w, h)
        col = r.random((1, w))
        n = _vnoise(w, h, 3, seed)
        t = 0.45 + (col - 0.5) * 0.35 + (n - 0.5) * 0.45 - 0.15 * ((X % 4) == 0)
        return _rgba(_lerp3([(0, k), (0.5, b), (1, B)], t))
    return p


def _cracks(w, h, seed, n=4):
    """갈라진 선 마스크와 선을 따라가는 거리값."""
    r = _rng("crack", seed, w, h)
    m = np.zeros((h, w), bool)
    dist = np.zeros((h, w))
    for i in range(n):
        x, y = r.integers(0, w), 0 if i % 2 == 0 else r.integers(0, h)
        s = 0
        for _ in range(h * 2):
            if 0 <= x < w and 0 <= y < h:
                m[y, x] = True
                dist[y, x] = s
            s += 1
            y += 1
            x += r.choice([-1, 0, 0, 1])
            if y >= h:
                break
    return m, dist


LAVA = [(0, C("5a0d02")), (0.35, C("b52a04")), (0.65, C("ff6a00")), (0.85, C("ffb428")), (1, C("fff2b0"))]


def M_lava_basalt(seed=0, only_cracks=False, n=4):
    base = M_basalt(seed)

    def p(f, w, h):
        out = np.zeros((h, w, 4)) if only_cracks else base(f, w, h)
        m, dist = _cracks(w, h, seed, n)
        t = 0.55 + 0.45 * np.sin(TAU * (f / F) * 2 - dist * 0.7)
        rgb = _lerp3(LAVA, t)
        out[m, :3] = rgb[m]
        out[m, 3] = 255
        if not only_cracks:  # 금 옆이 달아오른다
            mm = np.zeros_like(m)
            mm[:, 1:] |= m[:, :-1]
            mm[:, :-1] |= m[:, 1:]
            mm &= ~m
            out[mm, :3] = out[mm, :3] * 0.5 + C("7a1a04") * 0.5
        return out
    return p


def M_lava(seed=0):
    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 3, seed, periodic_y=h)
        t = 0.6 + 0.4 * np.sin(TAU * (f / F) + n * 6 + Y * 0.5)
        return _rgba(_lerp3(LAVA, t))
    return p


def M_fire(seed=0, hot=False):
    """일렁이는 불꽃 (위쪽은 투명). 세로 주기 노이즈를 위로 흘린다."""
    def p(f, w, h):
        X, Y = _grid(w, h)
        yb = (h - 1 - Y) / max(1, h - 1)  # 아래 0 → 위 1
        hgt = 0.62 + 0.2 * np.sin(X * 0.9 + TAU * f / F + seed) + 0.12 * np.sin(X * 2.1 - TAU * 2 * f / F + 1.3 * seed)
        nz = np.zeros((h, w))
        big = _vnoise(w, h * 2, 3, seed + 7, periodic_y=h * 2)
        off = int(round(f / F * h * 2))
        nz = np.roll(big, -off, axis=0)[:h]
        v = 1 - yb / np.clip(hgt, 0.2, 1) + (nz - 0.5) * 0.55
        # 가장자리로 갈수록 낮게
        edge = 1 - (np.abs(X - (w - 1) / 2) / (w / 2)) ** 2 * 0.55
        v = v * edge
        stops = [(0, C("7a1000")), (0.25, C("e03a00")), (0.5, C("ff8a00")), (0.75, C("ffd040")), (1, C("fffbe0"))]
        out = _rgba(_lerp3(stops, v * (1.15 if hot else 1.0)))
        out[..., 3] = np.where(v > 0.08, 255, 0)
        return out
    return p


def M_horn(seed=0):
    k, b, B, ash = C("120d0c"), C("2c2220"), C("4b3a33"), C("8c7a6c")

    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 3, seed)
        ridge = ((Y % 3) == 0) * -0.25
        t = 0.45 + (n - 0.5) * 0.35 + ridge + 0.15 * (X == 0)
        return _rgba(_lerp3([(0, k), (0.45, b), (0.8, B), (1, ash)], t))
    return p


def M_cloth(dark, mid, light, seed=0, fold=5.0):
    dark, mid, light = C(dark), C(mid), C(light)

    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 3, seed)
        t = 0.45 + 0.28 * np.sin(X * TAU / fold + n * 2) + (n - 0.5) * 0.3
        return _rgba(_lerp3([(0, dark), (0.5, mid), (1, light)], t))
    return p


GLYPHS = [
    ["x.x", ".x.", "x.x", ".x."], ["xxx", "x..", "xx.", "x.."], [".x.", "xxx", ".x.", "x.x"],
    ["x..", "xxx", "..x", "xxx"], ["xxx", ".x.", "x.x", "xxx"], ["x.x", "xxx", "x.x", ".x."],
]


def M_runes(bg, glow, hot, gold, gold_hi, seed=0):
    """위아래 금테 + 어두운 바탕 위에 차례로 빛나는 룬."""
    bg, glow, hot, gold, gold_hi = C(bg), C(glow), C(hot), C(gold), C(gold_hi)

    def p(f, w, h):
        out = _rgba(np.zeros((h, w, 3)) + bg)
        n = _vnoise(w, h, 2, seed)
        out[..., :3] *= (0.8 + 0.4 * n)[..., None]
        out[0, :, :3] = gold_hi
        out[h - 1, :, :3] = gold
        if h > 7:
            out[1, :, :3] = gold
            out[h - 2, :, :3] = gold * 0.75
        gy = (h - 4) // 2
        k = 0
        for gx in range(1, w - 2, 4):
            g = GLYPHS[(k + seed) % len(GLYPHS)]
            ph = (k / max(1, (w // 4))) % 1.0
            lv = max(0.0, math.sin(TAU * (f / F - ph))) ** 2
            col = glow * (0.45 + 0.55 * lv) + (hot - glow) * lv * 0.7
            for yy, row in enumerate(g):
                for xx, ch in enumerate(row):
                    if ch == "x" and gy + yy < h and gx + xx < w:
                        out[gy + yy, gx + xx, :3] = col
            k += 1
        return out
    return p


def M_obsidian(seed=0, glint="b05cff"):
    k, b, B, gl = C("07040c"), C("160d24"), C("2b1a45"), C(glint)

    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 3, seed)
        t = 0.45 + (n - 0.5) * 0.6 + 0.25 * (((X + Y * 2) % 9) < 1)
        rgb = _lerp3([(0, k), (0.6, b), (1, B)], t)
        r = _rng("obs", seed, w, h)
        pts = r.random((h, w)) < 0.06
        ph = r.random((h, w))
        tw = np.clip(np.sin(TAU * (f / F + ph)) * 2 - 0.8, 0, 1)
        rgb = rgb + (gl - rgb) * (pts * tw)[..., None]
        rgb = rgb + (gl - rgb) * _shine(f, w, h, 0.35, 1.6)[..., None]
        return _rgba(rgb)
    return p


def M_pearl(seed=0, tint=0.16, shine=0.35):
    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 4, seed)
        hue = (X + Y) / 40.0 + f / F + n * 0.3
        irid = np.stack([np.array(colorsys.hsv_to_rgb(hh % 1, 0.35, 1.0)) * 255 for hh in hue.ravel()]).reshape(h, w, 3)
        base = C("ece6f4") * (0.86 + 0.1 * n - 0.08 * (Y / h))[..., None]
        rgb = base * (1 - tint) + irid * tint
        rgb = rgb + (255 - rgb) * _shine(f, w, h, shine, 2.5)[..., None]
        return _rgba(rgb)
    return p


def M_prism(hue0=0.0, sat=0.42, seed=0, speed=1.0):
    """색이 계속 돌아가는 프리즘 결정. 면마다 조금씩 다른 색."""
    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 4, seed)
        hue = hue0 + Y / (h * 0.9) + f / F * speed + n * 0.05
        edge = ((X % 8) == 0) | ((X % 8) == 7)
        v = 0.86 + 0.14 * (1 - Y / h) + (n - 0.5) * 0.1 - 0.18 * edge
        s = sat + 0.25 * edge - 0.2 * (((X + 2 * Y) % 11) < 1)
        rgb = np.zeros((h, w, 3))
        for yy in range(h):
            for xx in range(w):
                rgb[yy, xx] = HSV(hue[yy, xx], max(0.05, s[yy, xx]), min(1.0, v[yy, xx]))
        rgb = rgb + (255 - rgb) * _shine(f, w, h, 0.6, 2.0, ph=seed * 0.11)[..., None]
        return _rgba(rgb)
    return p


def M_halo(seed=0):
    """무지개 고리 — 가로 방향으로 색이 흐른다. 가운데 줄은 하얀 심."""
    def p(f, w, h):
        out = np.zeros((h, w, 4))
        for yy in range(h):
            core = 1 - abs(yy - (h - 1) / 2) / (h / 2)
            for xx in range(w):
                hue = xx / w + f / F
                out[yy, xx, :3] = HSV(hue, 0.85 - 0.6 * core, 1.0)
        out[..., 3] = 255
        return out
    return p


def M_glow(col_lo, col_hi, speed=1, seed=0):
    lo, hi = C(col_lo), C(col_hi)

    def p(f, w, h):
        X, Y = _grid(w, h)
        n = _vnoise(w, h, 2, seed)
        t = 0.55 + 0.45 * np.sin(TAU * (f / F * speed) + n * 3)
        return _rgba(lo + (hi - lo) * t[..., None])
    return p


def M_void(seed=0):
    """보라빛 소용돌이 (가운데로 빨려 들어감)."""
    stops = [(0, C("05020a")), (0.45, C("2a0f4a")), (0.75, C("7a2ad0")), (0.92, C("c890ff")), (1, C("f4e0ff"))]

    def p(f, w, h):
        X, Y = _grid(w, h)
        dx, dy = X - (w - 1) / 2, Y - (h - 1) / 2
        r = np.sqrt(dx * dx + dy * dy) / (w / 2)
        a = np.arctan2(dy, dx)
        t = 0.5 + 0.5 * np.sin(3 * a + r * 7 - TAU * f / F)
        t = t * np.clip(r * 1.4, 0, 1) * 0.95
        t = np.where(r < 0.18, 0.97, t)
        return _rgba(_lerp3(stops, t))
    return p


def M_flat(col):
    c = C(col)

    def p(f, w, h):
        return _rgba(np.zeros((h, w, 3)) + c)
    return p


# ═══════════════════════════════ 투구 빌더 ═══════════════════════════════

ALL = ("north", "south", "east", "west", "up", "down")
# 면 → (u 축, v 축, u 반전?) — 평면 투영
PROJ = {"north": (0, 1, True), "south": (0, 1, False), "east": (2, 1, True), "west": (2, 1, False),
        "up": (0, 2, False), "down": (0, 2, False)}


class Helm:
    """투구 하나 = 모델 하나 + 애니메이션 아틀라스 하나 (item/armor/<sid>_helmet_tex)."""

    def __init__(self, sid, size=128, ppu=1.0):
        self.sid = sid
        self.ppu = ppu
        self.at = Atlas(f"item/armor/{sid}_helmet_tex", size, F, FT, interpolate=True)
        self.m = Model(f"armor/{sid}_helmet")
        self.m.use("t", self.at)
        self.mats = {}

    def mat(self, name, painter, w=16, h=16):
        reg = self.at.alloc(w, h)
        for f in range(F):
            a = painter(f, w, h)
            reg.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA"), f)
        self.mats[name] = reg
        return reg

    def faces(self, name, frm, to, skip=(), whole=(), off=(0, 0), fmat=None):
        out = {}
        for fc in ALL:
            if fc in skip:
                continue
            reg = self.mats[(fmat or {}).get(fc, name)]
            if whole == "all" or fc in whole:
                out[fc] = ("t", reg)
                continue
            ua, va, flip = PROJ[fc]
            pw = min(reg.w, max(1.0, (to[ua] - frm[ua]) * self.ppu))
            ph = min(reg.h, max(1.0, (to[va] - frm[va]) * self.ppu))
            u0 = (frm[ua] if not flip else 16 - to[ua]) * self.ppu + off[0]
            v0 = ((32 - to[va]) if va == 1 else frm[va]) * self.ppu + off[1]
            u0 = u0 % reg.w
            v0 = v0 % reg.h
            if u0 + pw > reg.w:
                u0 = reg.w - pw
            if v0 + ph > reg.h:
                v0 = reg.h - ph
            out[fc] = ("t", reg.uv((u0, v0, u0 + pw, v0 + ph)))
        return out

    def box(self, frm, to, name, light=0, rot=None, skip=(), whole=(), shade=True, off=(0, 0), sub=None, fmat=None):
        """sub=(x0,y0,x1,y1) 이면 모든 면이 재질 영역의 그 부분을 쓴다 (고리 조각처럼 위치별 색이 필요할 때)."""
        frm = [float(v) for v in frm]
        to = [float(v) for v in to]
        for i in range(3):
            if frm[i] > to[i]:
                frm[i], to[i] = to[i], frm[i]
        rotation = None
        if rot:
            axis, ang, origin = rot
            rotation = {"origin": [round(v, 4) for v in origin], "axis": axis, "angle": ang}
        if sub:
            fc = {f: ("t", self.mats[name].uv(sub)) for f in ALL if f not in skip}
        else:
            fc = self.faces(name, frm, to, skip, whole, off, fmat)
        self.m.box(frm, to, fc, light=light, shade=shade, rotation=rotation)

    def pair(self, frm, to, name, light=0, rot=None, skip=(), whole=(), shade=True, off=(0, 0), fmat=None):
        """x=8 기준 좌우 대칭 한 쌍."""
        self.box(frm, to, name, light, rot, skip, whole, shade, off, fmat=fmat)
        mf = [16 - to[0], frm[1], frm[2]]
        mt = [16 - frm[0], to[1], to[2]]
        mrot = None
        if rot:
            axis, ang, o = rot
            mrot = (axis, -ang if axis in ("y", "z") else ang, [16 - o[0], o[1], o[2]])
        sw = {"east": "west", "west": "east"}
        sk = tuple(sw.get(s, s) for s in skip)
        wh = whole if whole == "all" else tuple(sw.get(s, s) for s in whole)
        fm = {sw.get(k, k): v for k, v in (fmat or {}).items()}
        self.box(mf, mt, name, light, mrot, sk, wh, shade, (off[0] + 3, off[1]), fmat=fm)

    def spike(self, base, w, hgt, name, tip=None, segs=3, light=0, tip_light=None, rot=None, diamond=False,
              taper=0.6, mirror=False, body=None):
        """위로 솟는 가시: 위로 갈수록 가늘어지는 박스 더미. rot=(axis, angle) 이면 밑동 기준으로 통째로 기운다.
        diamond=True 면 y 축 45도 돌려 마름모 단면 (기울기와 함께 쓸 수 없음)."""
        x, y, z = base
        cw, cy = w, y
        seg_h = hgt / segs
        tl = light if tip_light is None else tip_light
        hs = [seg_h] * segs
        if body:  # 첫 마디(몸통)를 길게, 나머지는 뾰족한 끝
            hs = [hgt * body] + [hgt * (1 - body) / (segs - 1)] * (segs - 1)
        for i in range(segs):
            seg_h = hs[i]
            hh = seg_h * (1.2 if i < segs - 1 else 1.0)
            last = i == segs - 1
            nm = tip if (tip and last) else name
            r = None
            if diamond:
                r = ("y", 45, (x, y, z))
            elif rot:
                r = (rot[0], rot[1], (x, y, z))
            fn = self.pair if mirror else self.box
            fn((x - cw / 2, cy, z - cw / 2), (x + cw / 2, cy + hh, z + cw / 2), nm,
               light=tl if last else light, rot=r, off=(i * 2, 0))
            cy += seg_h
            cw *= taper

    def gem(self, center, size, name, light=15, axis="y", mirror=False, segs=3):
        """작은 팔면체 보석: 마름모 단면 박스 3개 (작-큰-작)."""
        x, y, z = center
        fn = self.pair if mirror else self.box
        hs = size
        prof = [(0.45, 0.33), (1.0, 0.34), (0.45, 0.33)] if segs == 3 else [(1.0, 1.0)]
        cy = y - hs * 0.9
        for k, (wf, hf) in enumerate(prof):
            w = size * wf
            hh = hs * 1.8 * hf
            fn((x - w / 2, cy, z - w / 2), (x + w / 2, cy + hh, z + w / 2), name, light=light,
               rot=(axis, 45, (x, y, z)), whole="all", shade=False)
            cy += hh

    def vtrim(self, frm, to, name, light=0, mirror=False):
        """세로로 선 띠: 북/남/동/서 면에 가로 무늬 재질을 90도 돌려 붙인다."""
        reg = self.mats[name]
        L = min(reg.w, (to[1] - frm[1]) * self.ppu)
        uv = reg.uv((0, 0, L, reg.h))
        for k, (a, b) in enumerate(((frm, to), ([16 - to[0], frm[1], frm[2]], [16 - frm[0], to[1], to[2]]))):
            if k == 1 and not mirror:
                break
            fc = {f: ("t", uv, 90) for f in ("north", "south", "east", "west")}
            ends = reg.uv((0, 0, 1, reg.h))
            fc["up"] = ("t", ends)
            fc["down"] = ("t", ends)
            self.m.box(a, b, fc, light=light)

    def count(self):
        return len(self.m.elements)

    def finish(self, assets_root):
        lo, hi = self.m.bounds()
        ext = max(hi[i] - lo[i] for i in range(3))
        gs = round(min(0.6, 17.0 / ext), 3)  # 큰 투구도 칸을 거의 채우게
        cy = (lo[1] + hi[1]) / 2
        disp = {
            "gui": {"rotation": [25, 145, 0], "translation": [0, round(-(cy - 8) * gs * 0.9, 2), 0], "scale": [gs] * 3},
            "ground": {"rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [round(gs * 0.75, 3)] * 3},
            "fixed": {"rotation": [0, 180, 0], "translation": [0, round(-(cy - 8) * gs, 2), 0],
                      "scale": [round(gs * 1.1, 3)] * 3},
            "thirdperson_righthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0],
                                      "scale": [round(min(0.375, gs * 0.7), 3)] * 3},
            "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 0, 0],
                                      "scale": [round(min(0.4, gs * 0.75), 3)] * 3},
        }
        disp["thirdperson_lefthand"] = disp["thirdperson_righthand"]
        disp["firstperson_lefthand"] = disp["firstperson_righthand"]
        self.m.display = disp
        self.at.save(os.path.join(assets_root, "textures"))
        self.m.write(assets_root)
        return "augsky:" + self.m.name


# ── 공통 투구 껍질 ──
def shell(H, mat, top=15.6, low=3.2, back_low=1.8, inner=None):
    """머리(1.6..14.4)를 감싸는 기본 껍질: 정수리, 뒤, 양옆. 얼굴(-Z)은 비워 둔다.
    inner: 안쪽 면 재질 (아이콘에서 빈 얼굴 칸이 어둡게 보이도록)."""
    H.box((0.8, 14.4, 0.8), (15.2, top, 15.2), mat, fmat={"down": inner} if inner else None)       # 정수리
    H.box((1.6, back_low, 14.4), (14.4, 14.4, 15.2), mat, fmat={"north": inner} if inner else None)  # 뒤
    H.pair((0.8, low, 0.8), (1.6, 14.4, 15.2), mat, fmat={"east": inner} if inner else None)       # 옆


def wing(H, mat, tip, x, z, feathers, light=4, tip_light=12, th=0.8, hh0=2.2):
    """옆머리에서 뒤(+Z)로 뻗는 깃털들. feathers: [(y, 길이, x축 각도)] — 음수 각도는 끝이 위로 들린다."""
    for k, (y, ln, ang) in enumerate(feathers):
        o = (x, y, z)
        hh = hh0 - k * 0.3
        H.pair((x - th, y - hh / 2, z), (x, y + hh / 2, z + ln * 0.6), mat, light=light, rot=("x", ang, o) if ang else None)
        H.pair((x - th * 0.8, y - hh / 3, z + ln * 0.6 - 0.1), (x - 0.1, y + hh / 3, z + ln * 0.88), mat, light=light,
               rot=("x", ang, o) if ang else None, off=(4, 0))
        H.pair((x - th * 0.6, y - hh / 6, z + ln * 0.88 - 0.1), (x - 0.2, y + hh / 6, z + ln), tip, light=tip_light,
               rot=("x", ang, o) if ang else None)


HELMS = {}
SPECS = {}


# ═══════════════════════════════ 6) 서리 군주 frostlord ═══════════════════════════════
# 은빛 판금 + 흰 에나멜 + 담비털 띠 + 빙하색 보석. 투구: 높은 얼음 왕관(가시 여럿) + 빛나는 보석 + 떠도는 얼음 조각.

def helm_frostlord(H):
    H.mat("silver", M_metal("b9c4d8", "f4f8ff", "56647e", seed=1, shine=0.45), 32, 32)
    H.mat("enamel", M_metal("e3eaf5", "ffffff", "9aa8c4", seed=2, shine=0.3, brushed=False), 16, 16)
    H.mat("fur", M_fur("f6f6f2", "b9bfcc", "1c1e26", seed=3), 32, 16)
    H.mat("ice", M_ice("e4fbff", "7fd0ff", "2a78d0", seed=4), 16, 32)
    H.mat("ice2", M_ice("ffffff", "a8e6ff", "4a9be6", seed=5, sparkle=0.15), 16, 16)
    H.mat("gem", M_gem("0a4a9a", "3cc8ff", "e8ffff", seed=6), 8, 8)
    H.mat("gem2", M_gem("1a3a8a", "6aa8ff", "f0f8ff", seed=7, speed=2), 8, 8)
    H.mat("velvet", M_cloth("0e1e4a", "1d3f8f", "3a6cc8", seed=8, fold=4), 16, 16)
    H.mat("trim", M_runes("16306e", "6fd8ff", "e8ffff", "8e9bb5", "f4f8ff", seed=1), 32, 8)

    H.mat("lining", M_cloth("0a1430", "14285a", "1e3a7a", seed=9, fold=4), 16, 16)
    # 껍질
    shell(H, "silver", inner="lining")
    H.box((1.6, 10.6, 0.6), (14.4, 14.4, 1.6), "enamel")                    # 이마판
    H.box((0.4, 9.8, 0.2), (15.6, 11.0, 1.0), "silver")                     # 눈썹 테
    H.pair((0.3, 6.2, 0.2), (3.6, 9.8, 1.6), "silver")                      # 볼 가리개 (위 넓고 아래 좁게)
    H.pair((0.3, 3.4, 0.4), (2.6, 6.2, 1.6), "silver")
    H.pair((0.3, 2.0, 0.6), (1.6, 3.4, 1.6), "silver")
    H.pair((0.8, 6.6, -0.1), (2.6, 9.2, 0.2), "ice", light=4)             # 볼 얼음 장식
    H.box((7.3, 6.6, 0.2), (8.7, 9.8, 1.0), "silver")                       # 코 가리개
    H.box((0.4, 1.4, 13.8), (15.6, 4.0, 15.8), "silver")                    # 목 가리개
    H.box((0.2, 2.0, 15.6), (15.8, 3.4, 16.0), "trim", light=6)             # 목 가리개 룬
    H.box((6.9, 10.9, -0.4), (9.1, 13.1, 0.4), "gem", light=15, whole="all")  # 이마 보석
    # 옆/뒤 룬 띠 + 뒤 얼음 등줄기 + 옆 눈꽃 메달 (날개 뿌리)
    H.box((0.6, 11.8, 15.1), (15.4, 13.2, 15.5), "trim", light=6, skip=("north",))
    H.pair((0.4, 11.8, 1.6), (0.9, 13.2, 15.4), "trim", light=6, skip=("east",))
    H.box((7.0, 3.4, 15.1), (9.0, 11.8, 16.0), "ice", light=3)
    H.pair((-1.0, 7.8, 3.0), (0.9, 12.6, 7.2), "silver")
    H.pair((-1.4, 8.6, 2.2), (-0.8, 11.8, 8.0), "silver")
    H.pair((-1.4, 6.8, 4.0), (-0.8, 13.6, 6.2), "silver")
    H.pair((-1.9, 9.3, 4.1), (-1.3, 11.1, 6.1), "gem", light=15, whole="all")
    # 옆 얼음 날개: 뒤로 뻗어 올라가는 깃털 3장 (밑동 굵고 끝 가늘게)
    wing(H, "ice", "ice2", x=-0.2, z=4.5, feathers=[(11.0, 10.0, -45), (9.4, 9.0, -22.5), (7.6, 7.0, 0)])
    # 왕관
    H.box((0.0, 14.6, 0.0), (16.0, 16.8, 16.0), "fur")                      # 담비털 띠
    H.box((0.5, 16.8, 0.5), (15.5, 18.6, 15.5), "trim", light=5, skip=("up",))
    H.box((0.5, 18.59, 0.5), (15.5, 18.6, 15.5), "velvet", skip=("down", "north", "south", "east", "west"))
    H.box((3.0, 18.6, 3.0), (13.0, 20.2, 13.0), "velvet")                   # 벨벳 모자
    H.box((6.6, 16.2, -0.5), (9.4, 19.0, 0.5), "gem", light=15, whole="all")  # 왕관 앞 큰 보석
    H.pair((-0.5, 16.6, 6.8), (0.5, 18.8, 9.2), "gem2", light=15, whole="all")
    # 얼음 가시
    H.spike((8, 18.4, 1.3), 2.8, 13.5, "ice", tip="ice2", segs=4, diamond=True, light=3, tip_light=12)
    H.spike((4.2, 18.4, 1.2), 1.9, 8.5, "ice", tip="ice2", rot=("x", -22.5), mirror=True, tip_light=10)
    H.spike((1.4, 18.0, 1.4), 2.2, 10.5, "ice", tip="ice2", diamond=True, mirror=True, tip_light=10)
    H.spike((1.1, 18.0, 5.0), 1.6, 7.5, "ice", tip="ice2", rot=("z", 22.5), mirror=True, tip_light=10)
    H.spike((1.1, 18.0, 8.5), 2.0, 9.5, "ice", tip="ice2", rot=("z", 22.5), mirror=True, tip_light=10)
    H.spike((1.1, 18.0, 12.0), 1.6, 7.0, "ice", tip="ice2", rot=("z", 22.5), mirror=True, tip_light=10)
    H.spike((1.6, 18.0, 14.4), 2.0, 8.5, "ice", tip="ice2", diamond=True, mirror=True, tip_light=10)
    H.spike((8, 18.0, 14.8), 2.4, 10.0, "ice", tip="ice2", rot=("x", 22.5), tip_light=10)
    H.spike((5.0, 18.0, 14.9), 1.6, 6.5, "ice", tip="ice2", rot=("x", 22.5), mirror=True, tip_light=10)
    # 가시 밑동 보석
    H.pair((3.7, 17.2, 0.1), (4.7, 18.2, 0.5), "gem2", light=15, whole="all")
    H.pair((-0.1, 17.2, 3.4), (0.5, 18.2, 4.4), "gem2", light=15, whole="all")
    H.pair((-0.1, 17.2, 11.6), (0.5, 18.2, 12.6), "gem2", light=15, whole="all")
    H.box((7.5, 17.2, 15.5), (8.5, 18.2, 16.1), "gem2", light=15, whole="all")
    # 떠도는 얼음 조각
    H.gem((-3.5, 23.0, 4.0), 2.2, "ice2", light=12, mirror=True)
    H.gem((-2.0, 21.0, 13.0), 1.6, "ice2", light=12, mirror=True)
    return H


SPECS["frostlord"] = {
    "notes": "은빛 판금+흰 에나멜+담비털 망토 깃, 가슴 빙하 보석과 얼음 문양, 등에 왕실 청색 망토. "
             "투구: 담비털 띠 위 은빛 왕관, 얼음 가시 17개(가운데 최장), 발광 보석, 옆 얼음 날개, 떠도는 얼음 결정",
    "pal": {
        "O": C("1b2440"), "n": C("142a5c"), "b": C("2456b0"), "B": C("4a86e0"),
        "s": C("6f7d99"), "S": C("aeb9ce"), "H": C("eef4fc"), "w": C("dfe7f2"),
        "f": C("f4f4f0"), "F": C("c3c9d4"), "k": C("1d1f26"),
        "c": C("2f8fe0"), "i": C("8ad6ff"), "I": C("d8f7ff"), "g": C("3fd8ff"), "G": C("e6ffff"),
        "y": C("c9a640"), "Y": C("fff0a0"),
    },
    "amp": {"f": 0.03, "H": 0.02, "G": 0.0, "I": 0.02, "k": 0.0},
    "body": [
        "fkff" + "fkffffkf" + "ffkf" + "fkffffkf",
        "FfFF" + "FfFffFfF" + "FFfF" + "FfFffFfF",
        "SHHs" + "sHwyywHs" + "sHHS" + "nbbbbbbn",
        "SwHs" + "SwyGgywS" + "sHwS" + "nbIbbIbn",
        "SwHs" + "SwyggywS" + "sHwS" + "nbbIIbbn",
        "sSSs" + "sSwyywSs" + "sSSs" + "nbbIIbbn",
        "SHHs" + "HsSiiSsH" + "sHHS" + "nbIbbIbn",
        "SwHs" + "wHsciSHw" + "sHwS" + "nbbbbbbn",
        "SwHs" + "wwHsSHww" + "sHwS" + "nBbbbbBn",
        "sSSs" + "swwHHwws" + "sSSs" + "nbBbbBbn",
        "OyyO" + "yyYgGYyy" + "OyyO" + "nnbbbbnn",
        "sHHs" + "sHSssSHs" + "sHHs" + "HiHiiHiH",
    ],
    "body_top": ["fkffffkf", "ffFffFff", "fFffffFf", "ffkffkff"],
    "arm": [
        "HHHS" + "HHHS" + "sSSs" + "SHHH",
        "HgGS" + "SHHs" + "sSSs" + "sHHS",
        "SggS" + "sSSs" + "ssss" + "sSSs",
        "OyyO" + "OyyO" + "OyyO" + "OyyO",
        "fkff" + "ffkf" + "fFff" + "fkff",
        "wwHs" + "wwHs" + "wwss" + "sHww",
        "wHws" + "wHws" + "wsws" + "swHw",
        "wwHs" + "wwHs" + "wwss" + "sHww",
        "SSSS" + "SSSS" + "ssss" + "SSSS",
        "HiIH" + "HiIH" + "sics" + "HIiH",
        "SccS" + "ScIS" + "sccs" + "SccS",
        "OssO" + "OssO" + "OssO" + "OssO",
    ],
    "arm_top": ["HHHS", "HIiS", "HiiS", "SSSs"],
    "boot": [
        "fkff" + "fkff" + "ffkf" + "fkff",
        "SHHs" + "SHHs" + "sSSs" + "sHHS",
        "SwHs" + "SgGs" + "swss" + "sHwS",
        "SwHs" + "SggS" + "swss" + "sHwS",
        "sSSs" + "HSSH" + "ssss" + "sSSs",
        "SHHs" + "SHHS" + "sSSs" + "sHHS",
        "OssO" + "OssO" + "OssO" + "OssO",
    ],
    "waist": [
        "OyyO" + "yyyGgyyy" + "OyyO" + "yyyyyyyy",
        "SHHs" + "SHHssHHS" + "sHHS" + "SHHssHHS",
        "SwHs" + "SwHssHwS" + "sHwS" + "SwHssHwS",
        "SwHs" + "SwHssHwS" + "sHwS" + "SwHssHwS",
        "sSSs" + "sSSssSSs" + "sSSs" + "sSSssSSs",
        "OssO" + "OssOOssO" + "OssO" + "OssOOssO",
    ],
    "leg": [
        "SHHs" + "SHHs" + "sSSs" + "sHHS",
        "SwHs" + "SwHs" + "swss" + "sHwS",
        "SwHs" + "SwHs" + "swss" + "sHwS",
        "sSSs" + "sSSs" + "ssss" + "sSSs",
        "SHHs" + "HiIH" + "sSSs" + "sHHS",
        "SwHs" + "SgGS" + "swss" + "sHwS",
        "SwHs" + "HSSH" + "swss" + "sHwS",
        "sSSs" + "sSSs" + "ssss" + "sSSs",
        "SHHs" + "SHHs" + "sSSs" + "sHHS",
        "SwHs" + "SwHs" + "swss" + "sHwS",
        "sSSs" + "sSSs" + "ssss" + "sSSs",
        "OssO" + "OssO" + "OssO" + "OssO",
    ],
    "icons": {
        "chestplate": [
            "................",
            ".OOOO......OOOO.",
            "OfkffO....OffkfO",
            "OFfffFOOOOFfffFO",
            "OHSSSHfkkfHSSSHO",
            ".OsSHSSggSSHSsO.",
            "..OsSHyGgySHsO..",
            "..OSwHSggSHwSO..",
            "..OSwwHiiHwwSO..",
            "..OSwHicciHwSO..",
            "..OsSwHiiHwSsO..",
            "..OSSwwHHwwSSO..",
            "..OyyyYgGYyyyO..",
            "..OsSHSssSHSsO..",
            "...OOOOOOOOOO...",
            "................",
        ],
        "leggings": [
            "................",
            "..OOOOOOOOOOOO..",
            "..OyyyYgGYyyyO..",
            "..OSHwSSSSwHSO..",
            "..OSwHSOOSHwSO..",
            "..OSHHO..OHHSO..",
            "..OiIgO..OgIiO..",
            "..OSwHO..OHwSO..",
            "..OSwHO..OHwSO..",
            "..OsSSO..OSSsO..",
            "..OSwHO..OHwSO..",
            "..OSwHO..OHwSO..",
            "..OsSsO..OsSsO..",
            "..OOOOO..OOOOO..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "...OOOO..OOOO...",
            "...OfkO..OkfO...",
            "...OFfO..OfFO...",
            "...OSHO..OHSO...",
            "...OgGO..OGgO...",
            "...OSHO..OHSO...",
            ".OOOSwO..OwSOOO.",
            "OSHHSwO..OwSHHSO",
            "OsSSSsO..OsSSSsO",
            "OOOOOOO..OOOOOOO",
            "................",
        ],
    },
}
HELMS["frostlord"] = helm_frostlord


# ═══════════════════════════════ 7) 화염 거신 inferno ═══════════════════════════════
# 현무암 판갑 + 흐르는 용암 균열 + 금 장식. 투구: 닫힌 면갑(빛나는 눈), 거대한 뿔, 불타는 볏.

def helm_inferno(H):
    H.mat("basalt", M_basalt(seed=11), 32, 32)
    H.mat("cracks", M_lava_basalt(seed=12, only_cracks=True, n=5), 32, 32)
    H.mat("gold", M_metal("d9a02a", "fff0a0", "6e4510", seed=13, shine=0.5), 16, 16)
    H.mat("horn", M_horn(seed=14), 16, 32)
    H.mat("lava", M_lava(seed=15), 16, 16)
    H.mat("fire", M_fire(seed=16), 32, 32)
    H.mat("fire2", M_fire(seed=17, hot=True), 16, 16)
    H.mat("eye", M_glow("ff7a00", "fff6c0", speed=2, seed=18), 8, 8)
    H.mat("dark", M_flat("0b0807"), 8, 8)

    shell(H, "basalt", top=15.8, low=2.4, inner="dark")
    # 닫힌 면갑: 이마 / 눈 틈 / 아래 얼굴
    H.box((0.6, 10.2, 0.2), (15.4, 15.8, 1.6), "basalt")
    H.box((0.6, 2.0, 0.2), (15.4, 7.4, 1.6), "basalt")
    H.pair((0.6, 7.4, 0.2), (2.4, 10.2, 1.6), "basalt")
    H.box((6.8, 7.4, -0.2), (9.2, 10.2, 1.6), "basalt")
    H.box((2.4, 7.4, 1.0), (6.8, 10.2, 1.4), "dark")                          # 눈 틈 속 그림자
    H.box((9.2, 7.4, 1.0), (13.6, 10.2, 1.4), "dark")
    H.pair((2.9, 8.1, 0.7), (6.3, 9.4, 1.0), "eye", light=15, rot=("z", -22.5, (4.6, 8.75, 0.85)), whole="all")
    # 눈썹 능선 (무겁게 튀어나옴) + 금 테
    H.box((0.0, 10.2, -0.8), (16.0, 11.6, 0.6), "basalt")
    H.box((-0.1, 11.6, -0.6), (16.1, 12.2, 0.4), "gold")
    # 가운데 금 콧날 + 입 창살
    H.box((7.2, 2.0, -0.6), (8.8, 15.8, 0.2), "gold")
    for i, x in enumerate((3.2, 5.2, 10.0, 12.0)):
        H.box((x, 2.6, -0.1), (x + 0.8, 6.2, 0.2), "lava", light=12)
    # 턱 엄니
    H.spike((2.2, 2.0, 0.0), 1.4, 4.0, "gold", tip="lava", segs=2, mirror=True, rot=("z", 22.5), tip_light=12)
    H.box((0.2, 1.2, -0.4), (15.8, 2.4, 1.6), "gold")                          # 턱 테
    H.box((0.4, 0.6, 13.8), (15.6, 3.2, 15.8), "basalt")                       # 목 가리개
    # 용암 균열 발광 막 (어두운 곳에서 금만 빛남)
    for frm, to in [((0.8, 14.4, 0.8), (15.2, 15.8, 15.2)), ((1.6, 2.4, 14.4), (14.4, 14.4, 15.2)),
                    ((0.6, 10.2, 0.2), (15.4, 15.8, 1.6)), ((0.6, 2.0, 0.2), (15.4, 7.4, 1.6))]:
        H.box([v - 0.05 for v in frm], [v + 0.05 for v in to], "cracks", light=15, shade=False)
    H.pair((0.75, 2.4, 0.75), (1.65, 14.4, 15.25), "cracks", light=15, shade=False, off=(7, 3))
    # 거대한 뿔: 옆으로 뻗었다가 위로 휘어 오른다
    horn = [((-2.0, 9.4, 4.8), (1.0, 15.2, 10.8), "basalt", 0, None),
            ((-5.4, 10.2, 5.2), (-1.6, 15.6, 10.4), "horn", 0, None),
            ((-8.4, 11.6, 5.6), (-5.0, 16.6, 10.0), "horn", 0, None),
            ((-10.4, 14.0, 6.0), (-7.4, 19.6, 9.6), "horn", 0, None),
            ((-11.0, 18.6, 6.3), (-8.4, 23.6, 9.3), "horn", 0, None),
            ((-10.6, 22.8, 6.6), (-8.4, 26.8, 9.0), "horn", 0, ("z", -22.5, (-9.5, 22.8, 7.8))),
            ((-9.6, 25.8, 7.0), (-7.8, 29.2, 8.6), "lava", 13, ("z", -22.5, (-8.7, 25.8, 7.8))),
            ((-8.8, 28.0, 7.3), (-7.6, 30.8, 8.3), "fire2", 15, ("z", -45, (-8.2, 28.0, 7.8)))]
    for frm, to, m, lt, rot in horn:
        H.pair(frm, to, m, light=lt, rot=rot)
    H.pair((-5.7, 9.9, 5.0), (-4.9, 15.9, 10.6), "gold")                       # 뿔 금고리
    H.pair((-11.2, 18.4, 6.1), (-8.2, 19.2, 9.5), "gold")
    H.pair((-11.2, 16.0, 7.2), (-10.3, 18.0, 8.4), "lava", light=13)          # 뿔 균열
    H.pair((-8.6, 12.4, 6.4), (-7.6, 15.6, 7.2), "lava", light=13)
    # 불타는 볏: 금 받침 + 현무암 등뼈 + 불꽃 판
    H.box((6.4, 15.8, 0.4), (9.6, 17.2, 15.4), "gold")
    H.box((7.0, 17.2, 1.4), (9.0, 18.8, 14.4), "basalt")
    for z0 in (2.0, 5.0, 8.0, 11.0):
        H.box((7.4, 18.8, z0), (8.6, 20.6 + (z0 < 6) * 0.8, z0 + 1.6), "horn")
    H.box((8.0, 18.0, -1.0), (8.0, 31.0, 16.5), "fire", light=15, skip=("up", "down", "north", "south"),
          whole=("east", "west"), shade=False)
    H.box((8.0, 18.0, 3.0), (8.0, 27.0, 13.0), "fire2", light=15, skip=("up", "down", "north", "south"),
          whole=("east", "west"), shade=False, rot=("y", 45, (8, 18, 8)))
    H.box((8.0, 18.0, 3.0), (8.0, 27.0, 13.0), "fire2", light=15, skip=("up", "down", "north", "south"),
          whole=("east", "west"), shade=False, rot=("y", -45, (8, 18, 8)))
    H.box((3.0, 17.0, 3.0), (13.0, 25.0, 3.0), "fire", light=15, skip=("up", "down", "east", "west"),
          whole=("north", "south"), shade=False)
    # 떠오르는 불씨
    for (x, y, z, s) in [(3.0, 26.5, 6.0, 0.9), (12.6, 28.0, 9.0, 0.8), (5.5, 30.0, 12.0, 0.7), (10.5, 24.8, 2.0, 0.8)]:
        H.box((x, y, z), (x + s, y + s, z + s), "fire2", light=15, whole="all", shade=False)
    return H


SPECS["inferno"] = {
    "notes": "검은 현무암 판갑에 흐르는 용암 균열, 금 테두리, 가슴 한가운데 녹아내리는 용암 핵. "
             "투구: 닫힌 면갑과 비스듬히 빛나는 눈, 바깥으로 뻗었다 휘어 오르는 거대한 뿔(끝은 불), 불꽃 볏과 불씨",
    "pal": {
        "O": C("0d0a0a"), "k": C("1c1716"), "b": C("2e2826"), "B": C("463d39"), "h": C("6a5d55"),
        "r": C("9a2005"), "l": C("ff5a00"), "L": C("ffb020"), "W": C("fff3a0"),
        "y": C("8c5a10"), "g": C("dca02a"), "G": C("ffe27a"),
    },
    "amp": {"W": 0.0, "L": 0.02, "l": 0.03, "G": 0.02},
    "body": [
        "ygGy" + "kygGGgyk" + "yGgy" + "kyggggyk",
        "bBhb" + "BhbkkbhB" + "bhBb" + "bBhbbhBb",
        "bBrb" + "hbkrrkbh" + "brBb" + "bBbrlbBb",
        "kblb" + "BkrLLrkB" + "blbk" + "kbBlrBbk",
        "bBlb" + "bklWWlkb" + "blBb" + "bBbrlbBb",
        "bBrb" + "bklWWlkb" + "brBb" + "bhBlbBhb",
        "kbBb" + "BkrLLrkB" + "bBbk" + "kbBrlBbk",
        "bBhb" + "hbkrlkbh" + "bhBb" + "bBblrBBb",
        "bBrb" + "bBbrlbBb" + "brBb" + "bBbrlbBb",
        "kblb" + "kbBblrbk" + "blbk" + "kbBlrBbk",
        "yggy" + "ygGlLGgy" + "yggy" + "yggggggy",
        "kbBk" + "kbBhhBbk" + "kBbk" + "kbBhhBbk",
    ],
    "body_top": ["kyggggyk", "bBhbbhBb", "bBlbblBb", "kygGGgyk"],
    "arm": [
        "hBBh" + "hBBh" + "bBBb" + "hBBh",
        "BlLB" + "BhhB" + "bbbb" + "BhhB",
        "bLrb" + "bBBb" + "kbbk" + "bBBb",
        "yggy" + "yggy" + "yggy" + "yggy",
        "kbbk" + "kbbk" + "kbbk" + "kbbk",
        "bBhb" + "bBhb" + "bbBb" + "bhBb",
        "brlb" + "bBhb" + "bbBb" + "blrb",
        "bBlb" + "bBhb" + "bbBb" + "blBb",
        "yggy" + "yGgy" + "yggy" + "ygGy",
        "BrlB" + "BlLB" + "bBBb" + "BLlB",
        "bBhb" + "bBhb" + "bbbb" + "bhBb",
        "kyyk" + "kyyk" + "kyyk" + "kyyk",
    ],
    "arm_top": ["hBhB", "BlLB", "hLrB", "BBbk"],
    "boot": [
        "yggy" + "yGgy" + "yggy" + "ygGy",
        "bBhb" + "bBhb" + "bbBb" + "bhBb",
        "brlb" + "bLlb" + "bbBb" + "blrb",
        "bBlb" + "bWLb" + "bbBb" + "blBb",
        "bBhb" + "bLlb" + "bbBb" + "bhBb",
        "yggy" + "gGGg" + "yggy" + "ygGy",
        "kkkk" + "kyyk" + "kkkk" + "kkkk",
    ],
    "waist": [
        "yggy" + "yggLWggy" + "yggy" + "yggggggy",
        "bBhb" + "bBhbbhBb" + "bhBb" + "bBhbbhBb",
        "brlb" + "bBlbblBb" + "blrb" + "bBhbbhBb",
        "bBlb" + "bBrbbrBb" + "blBb" + "bBlbblBb",
        "bBhb" + "kBhbbhBk" + "bhBb" + "bBhbbhBb",
        "kyyk" + "kyykkyyk" + "kyyk" + "kyykkyyk",
    ],
    "leg": [
        "bBhb" + "bBhb" + "bbBb" + "bhBb",
        "brlb" + "bBhb" + "bbBb" + "blrb",
        "bBlb" + "bBlb" + "bbBb" + "blBb",
        "bBhb" + "bBrb" + "bbBb" + "bhBb",
        "yggy" + "yGGy" + "yggy" + "ygGy",
        "bBhb" + "gLWg" + "bbBb" + "bhBb",
        "brlb" + "yggy" + "bbBb" + "blrb",
        "bBlb" + "bBhb" + "bbBb" + "blBb",
        "bBhb" + "bBlb" + "bbBb" + "bhBb",
        "kbbk" + "bBrb" + "kbbk" + "kbbk",
        "bBhb" + "bBhb" + "bbBb" + "bhBb",
        "kkkk" + "kkkk" + "kkkk" + "kkkk",
    ],
    "icons": {
        "chestplate": [
            "................",
            ".OOOO......OOOO.",
            "OhBBhO....OhBBhO",
            "OBlLBOOOOOOBLlBO",
            "OyggyOygGyOyggyO",
            ".OkbBhbrrbhBbkO.",
            "..ObBkrLLrkBbO..",
            "..ObkrLWWLrkbO..",
            "..ObkrLWWLrkbO..",
            "..ObBkrLLrkBbO..",
            "..ObBbbrlbbBbO..",
            "..OkbBblrbBbkO..",
            "..OyggGLWGggyO..",
            "..ObBhbkkbhBbO..",
            "...OOOOOOOOOO...",
            "................",
        ],
        "leggings": [
            "................",
            "..OOOOOOOOOOOO..",
            "..OyggGLWGggyO..",
            "..ObBhbbbbhBbO..",
            "..ObrlbOOblrbO..",
            "..ObBlO..OlBbO..",
            "..OyGgO..OgGyO..",
            "..OgLWO..OWLgO..",
            "..ObBhO..OhBbO..",
            "..ObrlO..OlrbO..",
            "..ObBlO..OlBbO..",
            "..ObBhO..OhBbO..",
            "..OkbbO..ObbkO..",
            "..OOOOO..OOOOO..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "...OOOO..OOOO...",
            "...OggO..OggO...",
            "...ObhO..OhbO...",
            "...OlLO..OLlO...",
            "...ObWO..OWbO...",
            "...ObhO..OhbO...",
            ".OOObBO..OBbOOO.",
            "OgGgbrO..OrbgGgO",
            "OkyykkO..OkkyykO",
            "OOOOOOO..OOOOOOO",
            "................",
        ],
    },
}
HELMS["inferno"] = helm_inferno


# ═══════════════════════════════ 8) 공허 군주 sovereign ═══════════════════════════════
# 검보라 왕실 로브 갑옷 + 보라 룬 + 금. 투구: 두건 + 검은 가시 왕관 + 떠 있는 보라 보석.

def helm_sovereign(H):
    H.mat("cloth", M_cloth("100818", "2a1446", "4c2a7c", seed=21, fold=5), 32, 32)
    H.mat("inner", M_flat("07040c"), 8, 8)
    H.mat("void", M_void(), 32, 32)
    H.mat("runes", M_runes("120a20", "a050ff", "f2d8ff", "a87a1c", "ffe08a", seed=2), 32, 8)
    H.mat("gold", M_metal("d6a83a", "fff0a8", "6a4a10", seed=23, shine=0.5), 16, 16)
    H.mat("obsidian", M_obsidian(seed=24), 16, 32)
    H.mat("vtip", M_glow("7a20d0", "f0c8ff", speed=1, seed=25), 8, 8)
    H.mat("vgem", M_gem("3a0a6a", "b050ff", "fbe8ff", seed=26), 8, 8)
    H.mat("vgem2", M_gem("2a0850", "8a3cff", "e8d0ff", seed=27, speed=2), 8, 8)

    # 두건: 아래는 넓게 퍼지고 위로 갈수록 좁아진다 (천이 둥글게 감싼 느낌)
    inn = {"east": "inner"}
    H.box((0.4, 14.4, -0.4), (15.6, 16.4, 15.8), "cloth", fmat={"down": "inner"})  # 정수리
    H.box((1.6, 12.0, 14.4), (14.4, 14.4, 16.0), "cloth", fmat={"north": "inner"})  # 뒤 3단
    H.box((0.8, 5.0, 14.4), (15.2, 12.0, 16.4), "cloth", fmat={"north": "inner"})   # 뒤 2단
    H.box((-0.2, -2.0, 14.4), (16.2, 5.0, 16.8), "cloth", fmat={"north": "inner"})  # 뒤 1단
    H.pair((0.4, 12.0, -0.4), (1.6, 14.4, 14.4), "cloth", fmat=inn)                # 옆 3단
    H.pair((-0.2, 5.0, -0.6), (1.6, 12.0, 14.4), "cloth", fmat=inn)                # 옆 2단
    H.pair((-0.8, -0.6, -0.8), (1.6, 5.0, 14.4), "cloth", fmat=inn)                # 옆 1단
    H.box((2.0, -4.6, 15.0), (14.0, -2.0, 16.8), "cloth")                        # 뒤 자락
    H.box((3.5, -6.2, 15.4), (12.5, -4.6, 16.9), "cloth")
    H.box((1.8, -4.9, 14.8), (14.2, -4.1, 17.0), "runes", light=7)               # 자락 룬 띠
    # 얼굴 테두리: 앞으로 튀어나온 처마 + 옆 자락 (얼굴 그늘)
    H.box((-0.2, 12.4, -1.4), (16.2, 16.4, 1.6), "cloth", fmat={"down": "inner"})
    H.pair((-0.6, -0.6, -1.2), (2.8, 12.4, 1.6), "cloth", fmat={"east": "inner"})
    H.box((-0.3, 12.2, -1.6), (16.3, 13.4, -1.0), "runes", light=9, skip=("up", "down"))  # 처마 룬 띠
    H.vtrim((1.6, -0.6, -1.5), (2.6, 12.2, -1.1), "runes", light=9, mirror=True)  # 옆 자락 세로 룬 띠
    H.box((5.0, 10.9, -1.5), (11.0, 12.4, 0.8), "cloth")                          # V 처마 (이마로 내려옴)
    H.box((6.4, 9.6, -1.5), (9.6, 10.9, 0.8), "cloth")
    H.pair((4.6, 10.5, -1.7), (6.6, 11.1, -1.3), "gold", rot=("z", -22.5, (6.6, 10.8, -1.5)))
    H.pair((-1.0, -1.1, -1.0), (1.8, -0.4, 14.6), "gold")                       # 두건 밑단
    H.box((-0.4, -2.5, 14.2), (16.4, -1.8, 17.0), "gold")
    H.box((1.6, 12.4, 0.8), (14.4, 14.4, 1.6), "inner")                          # 처마 안쪽 그늘
    H.box((6.9, 9.8, -2.0), (9.1, 12.0, -1.4), "vgem", light=15, whole="all")  # 이마 보석
    # 왕관: 금 띠 + 흑요석 띠 + 가시
    H.box((0.2, 16.4, 0.2), (15.8, 17.6, 15.8), "gold")
    H.box((0.6, 17.6, 0.6), (15.4, 19.4, 15.4), "obsidian")
    H.box((0.3, 19.4, 0.3), (15.7, 19.9, 1.1), "gold")
    H.box((0.3, 19.4, 14.9), (15.7, 19.9, 15.7), "gold")
    H.pair((0.3, 19.4, 1.1), (1.1, 19.9, 14.9), "gold")
    H.box((1.1, 19.0, 1.1), (14.9, 19.45, 14.9), "void", light=12, whole=("up",), shade=False,
          skip=("down", "north", "south", "east", "west"))
    H.spike((8, 19.6, 1.0), 2.6, 11.0, "obsidian", tip="vtip", segs=4, diamond=True, tip_light=15)
    H.spike((4.4, 19.6, 1.0), 1.8, 7.5, "obsidian", tip="vtip", mirror=True, rot=("x", -22.5), tip_light=15)
    H.spike((1.2, 19.6, 1.2), 2.2, 9.5, "obsidian", tip="vtip", mirror=True, diamond=True, tip_light=15)
    H.spike((1.0, 19.6, 5.0), 1.6, 6.0, "obsidian", tip="vtip", mirror=True, rot=("z", 22.5), tip_light=15)
    H.spike((1.0, 19.6, 8.4), 2.0, 8.5, "obsidian", tip="vtip", mirror=True, rot=("z", 22.5), tip_light=15)
    H.spike((1.0, 19.6, 12.0), 1.6, 6.0, "obsidian", tip="vtip", mirror=True, rot=("z", 22.5), tip_light=15)
    H.spike((1.3, 19.6, 14.7), 2.0, 8.0, "obsidian", tip="vtip", mirror=True, diamond=True, tip_light=15)
    H.spike((8, 19.6, 15.0), 2.2, 9.0, "obsidian", tip="vtip", rot=("x", 22.5), tip_light=15)
    # 띠의 보석
    H.box((6.9, 17.4, 0.0), (9.1, 19.6, 0.6), "vgem", light=15, whole="all")
    H.pair((-0.1, 17.8, 6.9), (0.6, 19.2, 9.1), "vgem2", light=15, whole="all")
    H.pair((3.9, 17.9, 0.2), (4.9, 18.9, 0.6), "vgem2", light=15, whole="all")
    # 떠 있는 보석들
    H.gem((8.0, 27.6, 8.0), 3.2, "vgem", light=15)
    H.gem((-3.2, 24.0, 2.0), 1.8, "vgem2", light=15, mirror=True)
    H.gem((-3.6, 22.0, 13.0), 1.6, "vgem2", light=15, mirror=True)
    H.gem((8.0, 25.0, -3.4), 1.7, "vgem2", light=15)
    return H


SPECS["sovereign"] = {
    "notes": "검보라 왕실 로브 갑옷: 금 깃과 금테, 가슴 앞섶을 따라 빛나는 보라 룬, 흑요석 견갑과 보라 보석. "
             "투구: 얼굴을 그늘지게 덮는 두건(룬 띠 발광), 검은 흑요석 가시 왕관(끝이 보랏빛), 머리 위와 둘레에 떠 있는 보라 보석",
    "pal": {
        "O": C("0a0612"), "k": C("140b20"), "o": C("1c1230"), "p": C("2a1544"), "P": C("43226c"), "q": C("6a38a2"),
        "v": C("a24cff"), "V": C("ecc8ff"), "e": C("9a3cff"), "E": C("f4e0ff"),
        "y": C("86601a"), "g": C("d6a83a"), "G": C("ffe08a"),
    },
    "amp": {"V": 0.0, "E": 0.0, "v": 0.02, "G": 0.02},
    "body": [
        "ygGy" + "gGkkkkGg" + "yGgy" + "gGGggGGg",
        "pPqP" + "PgkVvkgP" + "PqPp" + "pPqPPqPp",
        "pPqP" + "qgkvVkgq" + "PqPp" + "pPqvvqPp",
        "pPqP" + "PgkEekgP" + "PqPp" + "pPvVVvPp",
        "pPqP" + "PgkeekgP" + "PqPp" + "pPVeEVPp",
        "pPqP" + "qgkVvkgq" + "PqPp" + "pPvVVvPp",
        "pPqP" + "PgkvVkgP" + "PqPp" + "pPqvvqPp",
        "ppPp" + "PgkVvkgP" + "pPpp" + "pPqPPqPp",
        "gGgy" + "yggGGggy" + "ygGg" + "ygggggGy",
        "pPqP" + "PgkvVkgP" + "PqPp" + "pPqPPqPp",
        "pPqP" + "qgkVvkgq" + "PqPp" + "pPqPPqPp",
        "kppk" + "pykkkkyp" + "kppk" + "kppppppk",
    ],
    "body_top": ["gGGggGGg", "yPPqqPPy", "yPqkkqPy", "gGgkkgGg"],
    "arm": [
        "oqoo" + "ooqo" + "oooo" + "oqoo",
        "oeEo" + "oqoo" + "oooo" + "ooqo",
        "gGgy" + "gGgy" + "yggy" + "ygGg",
        "pPqP" + "PqPp" + "ppPp" + "pPqP",
        "pPqP" + "PqPp" + "ppPp" + "pPqP",
        "pPqP" + "PqPp" + "ppPp" + "pPqP",
        "kvVk" + "kVvk" + "kvvk" + "kvVk",
        "pPqP" + "PqPp" + "ppPp" + "pPqP",
        "pPqP" + "PqPp" + "ppPp" + "pPqP",
        "ygGg" + "gGgy" + "yggy" + "gGgy",
        "PqPp" + "qPPq" + "pPPp" + "pPqP",
        "ygGy" + "ygGy" + "yggy" + "yGgy",
    ],
    "arm_top": ["oqoo", "oeEo", "oeeo", "oooq"],
    "boot": [
        "ygGy" + "ygGy" + "yggy" + "yGgy",
        "okoo" + "okqo" + "oooo" + "ooko",
        "oqoo" + "oeEo" + "oooo" + "ooqo",
        "okoo" + "oeeo" + "oooo" + "ooko",
        "oqoo" + "okqo" + "oooo" + "ooqo",
        "gGgy" + "gGGg" + "yggy" + "ygGg",
        "kkkk" + "kkkk" + "kkkk" + "kkkk",
    ],
    "waist": [
        "gGgy" + "yggeEggy" + "ygGg" + "yggggggy",
        "pPqP" + "PqPkkPqP" + "PqPp" + "pPqPPqPp",
        "pPqP" + "PqgkkgqP" + "PqPp" + "pPqPPqPp",
        "pPqP" + "PqgvVgqP" + "PqPp" + "pPqPPqPp",
        "pPqP" + "PqgVvgqP" + "PqPp" + "pPqPPqPp",
        "ygGy" + "ygGyyGgy" + "yGgy" + "ygGyyGgy",
    ],
    "leg": [
        "pPqP" + "PqPg" + "pPPp" + "pPqP",
        "pPqP" + "PqPg" + "pPPp" + "pPqP",
        "pPqP" + "qPvg" + "pPPp" + "pPqP",
        "pPqP" + "PqVg" + "pPPp" + "pPqP",
        "pPqP" + "PqPg" + "pPPp" + "pPqP",
        "pPqP" + "PqvG" + "pPPp" + "pPqP",
        "pPqP" + "qPVg" + "pPPp" + "pPqP",
        "pPqP" + "PqPg" + "pPPp" + "pPqP",
        "ppqP" + "PqPg" + "pPPp" + "pPqp",
        "pPqP" + "PqPg" + "pPPp" + "pPqP",
        "ygGy" + "ygGG" + "yggy" + "yGgy",
        "kppk" + "kppk" + "kppk" + "kppk",
    ],
    "icons": {
        "chestplate": [
            "................",
            ".OOO..OggO..OOO.",
            "OoqoO.OGGO.OoqoO",
            "OoeEoOgkkgOoEeoO",
            "OgGgyPgkkgPygGgO",
            ".OPqPPgvVgPPqPO.",
            "..OqPPgVvgPPqO..",
            "..OPqPgeEgPqPO..",
            "..OPPqgvVgqPPO..",
            "..OyggGggGggyO..",
            "..OPqPgVvgPqPO..",
            "..OPqPgvVgPqPO..",
            ".OPqPPgkkgPPqPO.",
            ".OyggyykkyyggyO.",
            ".OOOOOOOOOOOOOO.",
            "................",
        ],
        "leggings": [
            "................",
            "..OOOOOOOOOOOO..",
            "..OyggGeEGggyO..",
            "..OPqPgkkgPqPO..",
            "..OPqPgOOgPqPO..",
            "..OPqgO..OgqPO..",
            "..OqPvO..OvPqO..",
            "..OPqVO..OVqPO..",
            "..OPqgO..OgqPO..",
            "..OqPgO..OgPqO..",
            "..OPqgO..OgqPO..",
            "..OygGO..OGgyO..",
            "..OkppO..OppkO..",
            "..OOOOO..OOOOO..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "...OOOO..OOOO...",
            "...OgGO..OGgO...",
            "...OoqO..OqoO...",
            "...OeEO..OEeO...",
            "...OoqO..OqoO...",
            "...OokO..OkoO...",
            "..OOoqO..OqoOO..",
            "OOoooqO..OqoooOO",
            "OgGggyO..OyggGgO",
            "OOOOOOO..OOOOOOO",
            "................",
        ],
    },
}
HELMS["sovereign"] = helm_sovereign


# ═══════════════════════════════ 9) 프리즘 prism ═══════════════════════════════
# 진주빛 흰 판갑 + 무지개 프리즘 결정. 투구: 결정 왕관 + 머리 위에 떠 있는 무지개 후광 고리(발광).

def _halo(H, cx, cy, cz, r, th=1.0, hgt=1.0, light=15):
    """16각형 고리. 각 조각을 접선 방향으로 놓고 22.5도 단위로 돌린다. 색은 둘레를 따라 이어진다."""
    seg = 2 * r * math.tan(math.pi / 16) + 0.35
    reg = H.mats["halo"]
    for k in range(16):
        ph = math.radians(k * 22.5)
        px, pz = cx + r * math.sin(ph), cz + r * math.cos(ph)
        tx, tz = math.cos(ph), -math.sin(ph)  # 접선
        best = None
        for along in ("x", "z"):
            for a in (-45, -22.5, 0, 22.5, 45):
                ar = math.radians(a)
                d = (math.cos(ar), -math.sin(ar)) if along == "x" else (math.sin(ar), math.cos(ar))
                err = 1 - abs(d[0] * tx + d[1] * tz)
                if best is None or err < best[0]:
                    best = (err, along, a)
        _, along, a = best
        if along == "x":
            frm, to = (px - seg / 2, cy - hgt / 2, pz - th / 2), (px + seg / 2, cy + hgt / 2, pz + th / 2)
        else:
            frm, to = (px - th / 2, cy - hgt / 2, pz - seg / 2), (px + th / 2, cy + hgt / 2, pz + seg / 2)
        u0 = k * reg.w / 16
        H.box(frm, to, "halo", light=light, shade=False, rot=("y", a, (px, cy, pz)) if a else None,
              sub=(u0, 0, u0 + reg.w / 16, reg.h))


def helm_prism(H):
    H.mat("pearl", M_pearl(seed=31), 32, 32)
    H.mat("trim", M_metal("ead9a0", "fffbe8", "9c8650", seed=32, shine=0.6), 16, 16)
    for i, h0 in enumerate((0.0, 0.12, 0.55, 0.7)):
        H.mat(f"c{i}", M_prism(h0, sat=0.3, seed=33 + i), 16, 32)
    H.mat("halo", M_halo(), 64, 4)
    H.mat("core", M_glow("c8b0ff", "ffffff", speed=2, seed=38), 8, 8)
    H.mat("inner", M_flat("3b3550"), 8, 8)

    H.mat("lining", M_cloth("5a4a7a", "7a6aa0", "9a8ac0", seed=39, fold=4), 16, 16)
    shell(H, "pearl", inner="lining")
    H.box((1.6, 10.6, 0.6), (14.4, 14.4, 1.6), "pearl")                          # 이마판
    H.box((0.3, 10.0, 0.0), (15.7, 10.9, 0.9), "trim")                           # 눈썹 테
    H.pair((4.2, 11.4, -0.3), (7.0, 12.2, 0.6), "trim", rot=("z", -22.5, (7.0, 11.8, 0.0)))  # V 티아라
    H.pair((2.4, 12.6, -0.2), (4.6, 13.3, 0.6), "trim")
    H.pair((0.3, 6.4, 0.2), (3.4, 10.0, 1.6), "pearl")                           # 볼 가리개 (아래로 좁게)
    H.pair((0.3, 3.6, 0.4), (2.4, 6.4, 1.6), "pearl")
    H.pair((0.3, 2.2, 0.6), (1.4, 3.6, 1.6), "pearl")
    H.pair((0.9, 6.8, -0.1), (2.4, 9.4, 0.3), "c1", light=12)                    # 볼 결정
    H.box((0.4, 1.6, 13.8), (15.6, 4.0, 15.8), "pearl")                          # 목 가리개
    H.box((0.2, 3.9, 13.6), (15.8, 4.5, 16.0), "trim")
    H.box((6.9, 10.6, -0.6), (9.1, 13.4, 0.3), "c0", light=15, whole="all")     # 이마 결정
    # 옆 날개: 진주 깃털 + 결정 끝
    wing(H, "pearl", "c2", x=-0.2, z=4.0, feathers=[(11.4, 13.5, -45), (9.6, 11.5, -22.5), (7.6, 9.0, 0)],
         light=0, tip_light=13, th=1.2, hh0=3.0)
    H.pair((-1.2, 7.4, 2.6), (0.9, 12.8, 6.6), "trim")                          # 날개 뿌리 메달
    H.pair((-1.7, 9.0, 3.5), (-1.1, 11.2, 5.7), "c0", light=15, whole="all")
    H.box((0.5, 13.8, 15.1), (15.5, 14.6, 15.5), "trim")                        # 뒤/옆 금 테
    H.pair((0.4, 13.8, 1.0), (0.9, 14.6, 15.5), "trim")
    H.box((7.2, 4.4, 15.1), (8.8, 13.8, 15.6), "c0", light=10)                  # 뒤 결정 줄
    # 결정 왕관: 금 띠 + 결정 다발 (가운데 크게, 좌우 대칭)
    H.box((0.4, 15.4, 0.4), (15.6, 17.0, 15.6), "trim")
    H.box((2.0, 17.0, 2.0), (14.0, 17.6, 14.0), "pearl")
    H.spike((8, 16.8, 2.0), 3.6, 12.5, "c0", segs=3, diamond=True, light=9, tip_light=15, taper=0.62, body=0.55)
    H.spike((4.0, 16.8, 2.0), 2.4, 8.0, "c1", diamond=True, mirror=True, light=9, tip_light=15, body=0.55)
    H.spike((1.6, 16.8, 5.5), 2.0, 6.5, "c2", rot=("z", 22.5), mirror=True, light=9, tip_light=15, body=0.55)
    H.spike((1.6, 16.8, 10.5), 1.8, 5.5, "c3", rot=("z", 22.5), mirror=True, light=9, tip_light=15, body=0.55)
    H.spike((8, 16.8, 14.2), 2.6, 8.5, "c2", rot=("x", 22.5), light=9, tip_light=15, body=0.55)
    H.spike((4.4, 16.8, 14.0), 1.8, 5.5, "c3", rot=("x", 22.5), mirror=True, light=9, tip_light=15, body=0.55)
    # 결정 사이 작은 보석
    H.pair((3.0, 16.0, 0.0), (4.0, 17.0, 0.5), "core", light=15, whole="all")
    # 후광 고리 + 고리 안 떠 있는 결정
    _halo(H, 8, 29.0, 8, 8.2, th=1.0, hgt=1.2)
    H.gem((8.0, 29.0, 8.0), 2.4, "c0", light=15)
    H.gem((-3.0, 22.0, 6.0), 1.7, "c2", light=14, mirror=True)
    return H


SPECS["prism"] = {
    "notes": "진주빛 흰 판갑, 가슴의 무지개 결정 다발과 무지개 띠, 연금 테두리. "
             "투구: 진주 투구+깃털 날개(결정 끝), 색이 계속 도는 프리즘 결정 왕관, 머리 위에 떠 도는 16각 무지개 후광(발광)과 결정",
    "pal": {
        "O": C("3b3550"), "l": C("9e94b8"), "p": C("d4cde2"), "P": C("efeaf6"), "W": C("ffffff"),
        "y": C("cdb36a"), "Y": C("fff2c0"),
        "r": lambda x, y: HSV(x / 14.0, 0.55, 1.0), "R": lambda x, y: HSV(x / 8.0 + y / 16.0 + 0.1, 0.28, 1.0),
        "c": lambda x, y: HSV(x / 8.0 + y / 16.0, 0.72, 0.95),
    },
    "amp": {"W": 0.0, "P": 0.02, "p": 0.03, "r": 0.0, "R": 0.0, "c": 0.0, "Y": 0.0},
    "body": [
        "yYyy" + "yYyWWyYy" + "yyYy" + "yYyyyyYy",
        "pPWP" + "PWPyyPWP" + "PWPp" + "pPWPPWPp",
        "pPWP" + "WPPccPPW" + "PWPp" + "pPPccPPp",
        "pPWP" + "PPcRWcPP" + "PWPp" + "pPcRWcPp",
        "lpPp" + "pcRWRrcp" + "pPpl" + "pcRWRrcp",
        "pPWP" + "pcrRrrcp" + "PWPp" + "pcrRrrcp",
        "pPWP" + "PPcrrcPP" + "PWPp" + "pPcrrcPp",
        "pPWP" + "PWPccPWP" + "PWPp" + "pPPccPPp",
        "lpPp" + "pPWPPWPp" + "pPpl" + "pPWPPWPp",
        "pPWP" + "PWPPPPWP" + "PWPp" + "pPWPPWPp",
        "rrrr" + "rrrrrrrr" + "rrrr" + "rrrrrrrr",
        "lppl" + "lpPWWPpl" + "lppl" + "lpPWWPpl",
    ],
    "body_top": ["yYyyyyYy", "pPWrrWPp", "pPWrrWPp", "yYyrryYy"],
    "arm": [
        "WPPW" + "WPPW" + "pPPp" + "WPPW",
        "PcRP" + "PWWP" + "pPPp" + "PRcP",
        "pRrp" + "pPPp" + "pppp" + "prRp",
        "yYyy" + "yYYy" + "yyyy" + "yyYy",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "lpPp" + "lpPp" + "lppl" + "pPpl",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "rrrr" + "rrrr" + "rrrr" + "rrrr",
        "PWWP" + "PcRP" + "pPPp" + "PRcP",
        "pPPp" + "pRrp" + "pppp" + "prRp",
        "lyyl" + "lyyl" + "lyyl" + "lyyl",
    ],
    "arm_top": ["WPPW", "PcRP", "PRrP", "pPPp"],
    "boot": [
        "rrrr" + "rrrr" + "rrrr" + "rrrr",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "pPWP" + "PcRP" + "pPPp" + "PWPp",
        "lpPp" + "pRrp" + "pPPp" + "pPpl",
        "pPWP" + "PWWP" + "pPPp" + "PWPp",
        "yYyy" + "yYYy" + "yyyy" + "yyYy",
        "OllO" + "OllO" + "OllO" + "OllO",
    ],
    "waist": [
        "yYyy" + "yYcRRcYy" + "yyYy" + "yYyyyyYy",
        "pPWP" + "PWPrrPWP" + "PWPp" + "pPWPPWPp",
        "pPWP" + "PWPRrPWP" + "PWPp" + "pPWPPWPp",
        "lpPp" + "pPWPPWPp" + "pPpl" + "pPWPPWPp",
        "pPWP" + "PWPPPPWP" + "PWPp" + "pPWPPWPp",
        "lppl" + "lyyllyyl" + "lppl" + "lyyllyyl",
    ],
    "leg": [
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "lpPp" + "lpPp" + "lppl" + "pPpl",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "yYyy" + "yYYy" + "yyyy" + "yyYy",
        "pPWP" + "PcWP" + "pPPp" + "PWPp",
        "pPWP" + "PrcP" + "pPPp" + "PWPp",
        "yYyy" + "yYYy" + "yyyy" + "yyYy",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "lpPp" + "lpPp" + "lppl" + "pPpl",
        "pPWP" + "pPWP" + "pPPp" + "PWPp",
        "lppl" + "lppl" + "lppl" + "lppl",
    ],
    "icons": {
        "chestplate": [
            "................",
            ".OOOO......OOOO.",
            "OPWWPO....OPWWPO",
            "OPcRPOOOOOOPRcPO",
            "OyYyyOyYYyOyyYyO",
            ".OpPWPPccPPWPpO.",
            "..OpPWcRWcWPpO..",
            "..OPWcRWRrcWPO..",
            "..OPPcrRrrcPPO..",
            "..OpPWPcrcPWpO..",
            "..OPWPPPPPPWPO..",
            "..OrrrrrrrrrrO..",
            "..OpPWPPPPWPpO..",
            "..OlppPWWPpplO..",
            "...OOOOOOOOOO...",
            "................",
        ],
        "leggings": [
            "................",
            "..OOOOOOOOOOOO..",
            "..OyYycRRcyYyO..",
            "..OPWPPPPPPWPO..",
            "..OPWPPOOPPWPO..",
            "..OPWPO..OPWPO..",
            "..OyYyO..OyYyO..",
            "..OcRPO..OPRcO..",
            "..OPrpO..OprPO..",
            "..OPWPO..OPWPO..",
            "..OyYyO..OyYyO..",
            "..OPWPO..OPWPO..",
            "..OlppO..OpplO..",
            "..OOOOO..OOOOO..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "...OOOO..OOOO...",
            "...OrrO..OrrO...",
            "...OPWO..OWPO...",
            "...OcRO..ORcO...",
            "...ORrO..OrRO...",
            "...OPWO..OWPO...",
            ".OOOPWO..OWPOOO.",
            "OPWWPPO..OPPWWPO",
            "OyYyyyO..OyyyYyO",
            "OOOOOOO..OOOOOOO",
            "................",
        ],
    },
}
HELMS["prism"] = helm_prism


# ═══════════════════════════════ 몸 갑옷 / 아이콘 그리기 ═══════════════════════════════

def _put(arr, x0, y0, rows, pal, amp, seed, mirror=False):
    rng = _rng("px", seed, x0, y0)
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in ". ":
                continue
            if ch not in pal:
                raise KeyError(f"팔레트에 없는 글자 {ch!r} (seed={seed}, row={j})")
            v = pal[ch]
            col = np.array(v(x0 + i, y0 + j) if callable(v) else v, dtype=float)
            a = amp.get(ch, 0.05)
            col = col * (1 + (rng.random() - 0.5) * 2 * a)
            arr[y0 + j, x0 + i, :3] = np.clip(col, 0, 255)
            arr[y0 + j, x0 + i, 3] = 255


def _check(rows, w, h, what):
    assert len(rows) == h, f"{what}: 줄 수 {len(rows)} != {h}"
    for j, r in enumerate(rows):
        assert len(r) == w, f"{what} {j}번 줄 길이 {len(r)} != {w}: {r!r}"


def paint_humanoid(sid, spec):
    a = np.zeros((32, 64, 4))
    pal, amp = spec["pal"], spec.get("amp", {})
    _check(spec["body"], 24, 12, sid + " body")
    _check(spec["arm"], 16, 12, sid + " arm")
    _check(spec["boot"], 16, len(spec["boot"]), sid + " boot")
    _put(a, 16, 20, spec["body"], pal, amp, sid + "b")
    _put(a, 20, 16, spec["body_top"], pal, amp, sid + "bt")
    _put(a, 40, 20, spec["arm"], pal, amp, sid + "a")
    _put(a, 44, 16, spec["arm_top"], pal, amp, sid + "at")
    _put(a, 0, 32 - len(spec["boot"]), spec["boot"], pal, amp, sid + "bo")
    if "sole" in spec:
        _put(a, 8, 16, spec["sole"], pal, amp, sid + "so")
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def paint_leggings(sid, spec):
    a = np.zeros((32, 64, 4))
    pal, amp = spec["pal"], spec.get("amp", {})
    _check(spec["leg"], 16, 12, sid + " leg")
    _put(a, 16, 32 - len(spec["waist"]), spec["waist"], pal, amp, sid + "w")
    _put(a, 0, 20, spec["leg"], pal, amp, sid + "l")
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def paint_icon(sid, rows, spec):
    _check(rows, 16, 16, sid + " icon")
    a = np.zeros((16, 16, 4))
    _put(a, 0, 0, rows, spec["pal"], {k: v * 0.5 for k, v in spec.get("amp", {}).items()}, sid + "icon")
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


# ═══════════════════════════════ z-버퍼 미리보기 렌더러 ═══════════════════════════════
# 카메라는 +z 쪽에서 -z 를 본다 (화면 앞쪽일수록 z 가 크다).

def _frame(atlas, f):
    s = atlas.size
    f = f % atlas.frames
    return np.array(atlas.img.crop((0, f * s, s, f * s + s)))


def zrender(parts, size=360, yaw=-35, pitch=25, frame=0, bg=(22, 20, 30), ss=2, pad=0.06, night=False, fit=None,
            bloom=True):
    view = _rot_matrix("x", pitch) @ _rot_matrix("y", yaw)
    faces = []
    for model, M in parts:
        M = np.eye(4) if M is None else np.array(M, dtype=float)
        texs = {k: _frame(a, frame) for k, a in model.atlases.items()}
        for el in model.elements:
            corners = _face_corners(el["from"], el["to"])
            rot = el.get("rotation")
            glow = el.get("light_emission", 0)
            for fname, fd in el["faces"].items():
                tex = texs.get(fd["texture"].lstrip("#"))
                if tex is None:
                    continue
                pts = []
                for p in corners[fname]:
                    v = np.array(p, dtype=float)
                    if rot:
                        o = np.array(rot["origin"], dtype=float)
                        v = _rot_matrix(rot["axis"], rot["angle"]) @ (v - o) + o
                    v = (v - 8.0) / 16.0
                    pts.append(view @ (M @ np.append(v, 1.0))[:3])
                pts = np.array(pts)
                n = np.cross(pts[1] - pts[0], pts[3] - pts[0])
                if n[2] >= -1e-12:
                    continue
                sh = FACE_LIGHT[fname] if el.get("shade", True) else 1.0
                if night:
                    lt = max(sh * 0.2, glow / 15.0)
                else:
                    lt = max(sh, glow / 15.0 * 0.9) if glow else sh
                faces.append((pts, tex, fd["uv"], fd.get("rotation", 0), lt, glow))
    S = size * ss
    img = np.zeros((S, S, 3)) + np.array(bg[:3], dtype=float) * (0.45 if night else 1.0)
    gl = np.zeros((S, S))
    if not faces:
        return Image.fromarray(img.astype(np.uint8))
    allp = np.concatenate([f[0] for f in faces])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    if fit:
        cx, cy, span = fit
    else:
        span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    sc = S * (1 - 2 * pad) / span
    zb = np.full((S, S), -1e9)
    for pts, tex, uv, frot, lt, glow in faces:
        scr = np.stack([(pts[:, 0] - cx) * sc + S / 2, -(pts[:, 1] - cy) * sc + S / 2], 1)
        th, tw = tex.shape[:2]
        u0, v0, u1, v1 = uv[0] / 16 * tw, uv[1] / 16 * th, uv[2] / 16 * tw, uv[3] / 16 * th
        src = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for _ in range(int(frot) // 90):
            src = src[1:] + src[:1]
        src = np.array(src)
        e1, e2 = scr[1] - scr[0], scr[3] - scr[0]
        det = e1[0] * e2[1] - e1[1] * e2[0]
        if abs(det) < 1e-6:
            continue
        x0 = int(max(0, math.floor(scr[:, 0].min())))
        x1 = int(min(S, math.ceil(scr[:, 0].max()) + 1))
        y0 = int(max(0, math.floor(scr[:, 1].min())))
        y1 = int(min(S, math.ceil(scr[:, 1].max()) + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        dx, dy = X - scr[0, 0], Y - scr[0, 1]
        s = (dx * e2[1] - dy * e2[0]) / det
        t = (e1[0] * dy - e1[1] * dx) / det
        inside = (s >= -1e-4) & (s <= 1 + 1e-4) & (t >= -1e-4) & (t <= 1 + 1e-4)
        if not inside.any():
            continue
        z = pts[0, 2] + s * (pts[1, 2] - pts[0, 2]) + t * (pts[3, 2] - pts[0, 2])
        tu = src[0, 0] + s * (src[1, 0] - src[0, 0]) + t * (src[3, 0] - src[0, 0])
        tv = src[0, 1] + s * (src[1, 1] - src[0, 1]) + t * (src[3, 1] - src[0, 1])
        lu, hu = src[:, 0].min(), src[:, 0].max()
        lv, hv = src[:, 1].min(), src[:, 1].max()
        iu = np.clip(np.floor(np.clip(tu, lu, hu - 1e-3)).astype(int), 0, tw - 1)
        iv = np.clip(np.floor(np.clip(tv, lv, hv - 1e-3)).astype(int), 0, th - 1)
        texel = tex[iv, iu]
        ok = inside & (texel[..., 3] >= 26)
        sub = zb[y0:y1, x0:x1]
        ok &= z > sub + 1e-7
        if not ok.any():
            continue
        sub[ok] = z[ok]
        img[y0:y1, x0:x1][ok] = texel[..., :3][ok] * lt
        gl[y0:y1, x0:x1][ok] = glow / 15.0
    if bloom and gl.max() > 0:  # 발광 부분에 은은한 번짐 (미리보기 전용)
        src = Image.fromarray(np.clip(img * gl[..., None], 0, 255).astype(np.uint8))
        bl = np.array(src.filter(ImageFilter.GaussianBlur(S / 70)), dtype=float)
        img = img + bl * (0.9 if night else 0.45)
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return out.resize((size, size), Image.LANCZOS) if ss > 1 else out


# ═══════════════════════════════ 착용 마네킹 ═══════════════════════════════

def _tex_model(name, img):
    at = Atlas("_preview/" + name, 64, 1)
    at.img.alpha_composite(img.convert("RGBA").crop((0, 0, 64, min(64, img.height))), (0, 0))
    m = Model("_preview/" + name)
    m.use("t", at)
    return m


def _limb(m, frm, to, u, v, w, h, d, infl=0.0, mirror=False):
    """바닐라 전개도 (u,v,w,h,d) 박스. 얼굴 = -Z, 플레이어 오른쪽 = +X."""
    k = 16.0 / 64.0

    def U(x0, y0, x1, y1, flip=False):
        if flip:
            x0, x1 = x1, x0
        return [x0 * k, y0 * k, x1 * k, y1 * k]
    front = (u + d, v + d, u + d + w, v + d + h)
    right = (u, v + d, u + d, v + d + h)
    left = (u + d + w, v + d, u + 2 * d + w, v + d + h)
    back = (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h)
    top = (u + d + w, v + d, u + d, v)
    bot = (u + d + w, v, u + 2 * d + w, v + d)
    if not mirror:
        faces = {"north": ("t", U(*front)), "east": ("t", U(*right)), "west": ("t", U(*left)),
                 "south": ("t", U(*back)), "up": ("t", [c * k for c in top]), "down": ("t", U(*bot))}
    else:
        faces = {"north": ("t", U(*front, flip=True)), "west": ("t", U(*right, flip=True)),
                 "east": ("t", U(*left, flip=True)), "south": ("t", U(*back, flip=True)),
                 "up": ("t", [top[2] * k, top[1] * k, top[0] * k, top[3] * k]), "down": ("t", U(*bot, flip=True))}
    m.box([frm[i] - infl for i in range(3)], [to[i] + infl for i in range(3)], faces)


def mannequin(humanoid, leggings, helmet=None):
    steve = Image.open(STEVE).convert("RGBA")
    base = _tex_model("steve", steve)
    _limb(base, (4, 24, 4), (12, 32, 12), 0, 0, 8, 8, 8)
    _limb(base, (4, 12, 6), (12, 24, 10), 16, 16, 8, 12, 4)
    _limb(base, (12, 12, 6), (16, 24, 10), 40, 16, 4, 12, 4)
    _limb(base, (0, 12, 6), (4, 24, 10), 40, 16, 4, 12, 4, mirror=True)
    _limb(base, (8, 0, 6), (12, 12, 10), 0, 16, 4, 12, 4)
    _limb(base, (4, 0, 6), (8, 12, 10), 0, 16, 4, 12, 4, mirror=True)
    legm = _tex_model("legs", leggings)
    _limb(legm, (4, 12, 6), (12, 24, 10), 16, 16, 8, 12, 4, infl=0.5)
    _limb(legm, (8, 0, 6), (12, 12, 10), 0, 16, 4, 12, 4, infl=0.5)
    _limb(legm, (4, 0, 6), (8, 12, 10), 0, 16, 4, 12, 4, infl=0.5, mirror=True)
    outer = _tex_model("outer", humanoid)
    _limb(outer, (4, 12, 6), (12, 24, 10), 16, 16, 8, 12, 4, infl=1.0)
    _limb(outer, (12, 12, 6), (16, 24, 10), 40, 16, 4, 12, 4, infl=1.0)
    _limb(outer, (0, 12, 6), (4, 24, 10), 40, 16, 4, 12, 4, infl=1.0, mirror=True)
    _limb(outer, (8, 0, 6), (12, 12, 10), 0, 16, 4, 12, 4, infl=1.0)
    _limb(outer, (4, 0, 6), (8, 12, 10), 0, 16, 4, 12, 4, infl=1.0, mirror=True)
    parts = [(base, None), (legm, None), (outer, None)]
    if helmet is not None:
        # 머리 중심 = 모델 (8,28,8) → 월드 (0, 20/16, 0). 게임은 투구 모델을 0.625 배로 머리에 씌운다.
        parts.append((helmet, mat((0, 20 / 16, 0), 0.625)))
    return parts


# ═══════════════════════════════ 빌드 ═══════════════════════════════

_BUILT = {}


def build(assets_root):
    res = {"sets": {}}
    tex = os.path.join(assets_root, "textures")
    for sid in SETS:
        if sid not in SPECS:
            continue
        spec = SPECS[sid]
        hum = paint_humanoid(sid, spec)
        leg = paint_leggings(sid, spec)
        for sub, img in (("humanoid", hum), ("humanoid_leggings", leg)):
            p = os.path.join(tex, "entity", "equipment", sub, sid + ".png")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            img.save(p)
        icons = {}
        for kind in ("chestplate", "leggings", "boots"):
            ic = paint_icon(sid, spec["icons"][kind], spec)
            p = os.path.join(tex, "item", "armor", f"{sid}_{kind}.png")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            ic.save(p)
            icons[kind] = ic
        H = HELMS[sid](Helm(sid))
        ref = H.finish(assets_root)
        _BUILT[sid] = (H, hum, leg, icons)
        res["sets"][sid] = {"helmet_model": ref, "notes": spec["notes"], "elements": H.count()}
    return res


# ═══════════════════════════════ 미리보기 ═══════════════════════════════

def _label(img, text, size=18):
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, size)
    d.text((8, 6), text, font=f, fill=(235, 235, 245))
    return img


def _enlarge(img, k, bg=(48, 46, 58)):
    w, h = img.size
    back = Image.new("RGBA", (w * k, h * k), bg + (255,))
    chk = ImageDraw.Draw(back)
    for y in range(h):
        for x in range(w):
            if (x + y) % 2:
                chk.rectangle((x * k, y * k, x * k + k - 1, y * k + k - 1), fill=(58, 56, 70, 255))
    back.alpha_composite(img.resize((w * k, h * k), Image.NEAREST))
    return back.convert("RGB")


def gui_icon(m, px=96):
    """display.gui 변환을 흉내 낸 인벤토리 칸 미리보기 (칸 = 16단위 = 1블록)."""
    d = m.display["gui"]
    R = np.eye(4)
    R[:3, :3] = _rot_matrix("x", d["rotation"][0]) @ _rot_matrix("y", d["rotation"][1])
    S = np.diag([d["scale"][0]] * 3 + [1.0])
    T = np.eye(4)
    T[:3, 3] = np.array(d["translation"]) / 16.0
    img = zrender([(m, T @ R @ S)], px, yaw=0, pitch=0, fit=(0, 0, 1.0 / 0.88), bg=(139, 139, 139), bloom=False)
    return img


def preview_set(sid):
    H, hum, leg, icons = _BUILT[sid]
    m = H.m
    ko = NAMES_KO[sid]
    cell = 300
    tiles = [
        _label(zrender([(m, None)], cell, yaw=180 - 30, pitch=18), "투구 앞"),
        _label(zrender([(m, None)], cell, yaw=180 + 40, pitch=12, frame=8), "투구 옆 (8프레임)"),
        _label(zrender([(m, None)], cell, yaw=35, pitch=25), "투구 뒤"),
        _label(zrender([(m, None)], cell, yaw=180 - 30, pitch=18, night=True, frame=4), "투구 밤"),
    ]
    parts = mannequin(hum, leg, m)
    fit = (0, 0.86, 2.95)
    tiles += [
        _label(zrender(parts, cell, yaw=180 - 25, pitch=10, fit=fit), "착용 앞"),
        _label(zrender(parts, cell, yaw=25, pitch=10, fit=fit), "착용 뒤"),
        _label(zrender(parts, cell, yaw=180 - 90, pitch=8, fit=fit), "착용 옆"),
        _label(zrender(parts, cell, yaw=180 - 25, pitch=10, fit=fit, night=True, frame=6), "착용 밤"),
    ]
    W = cell * 4
    sheet = Image.new("RGB", (W, cell * 2 + 420), (18, 16, 26))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 4) * cell, (i // 4) * cell))
    y = cell * 2 + 10
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 18)
    d.text((10, y), f"{ko} ({sid}) — 아이콘 / humanoid / humanoid_leggings   투구 요소 {H.count()}개", font=f,
           fill=(235, 235, 245))
    y += 28
    for i, k in enumerate(("chestplate", "leggings", "boots")):
        sheet.paste(_enlarge(icons[k], 8), (10 + i * 140, y))
        sheet.paste(_enlarge(icons[k], 2), (10 + i * 40, y + 140))
    g = gui_icon(m)
    sheet.paste(g, (10, y + 200))
    d.text((10 + 104, y + 200), "GUI 칸\n(display)", font=f, fill=(200, 200, 210))
    sheet.paste(_enlarge(hum, 6), (440, y))
    sheet.paste(_enlarge(leg, 6), (440, y + 196))
    return sheet


def make_previews():
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    paths = []
    for sid in SETS:
        if sid not in _BUILT:
            continue
        p = os.path.join(PREVIEW_DIR, f"{MODULE}_{sid}.png")
        preview_set(sid).save(p)
        paths.append(p)
    # 전체 모음: 착용 앞 / 뒤 / 밤
    sids = [sid for sid in SETS if sid in _BUILT]
    if sids:
        T = 420
        fit = (0, 0.86, 2.95)
        sheet = Image.new("RGB", (T * len(sids), T * 3), (18, 16, 26))
        for i, sid in enumerate(sids):
            H, hum, leg, icons = _BUILT[sid]
            parts = mannequin(hum, leg, H.m)
            sheet.paste(_label(zrender(parts, T, yaw=180 - 28, pitch=10, fit=fit), NAMES_KO[sid] + " 앞"), (i * T, 0))
            sheet.paste(_label(zrender(parts, T, yaw=28, pitch=10, fit=fit, frame=5), NAMES_KO[sid] + " 뒤"), (i * T, T))
            sheet.paste(_label(zrender(parts, T, yaw=180 + 30, pitch=10, fit=fit, frame=10, night=True),
                               NAMES_KO[sid] + " 밤"), (i * T, 2 * T))
        p = os.path.join(PREVIEW_DIR, f"{MODULE}.png")
        sheet.save(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    import json
    import shutil
    only = sys.argv[1:] or None
    if only:
        SETS[:] = [s for s in SETS if s in only]
    if os.path.exists(SCRATCH) and not only:
        shutil.rmtree(SCRATCH)
    r = build(SCRATCH)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    for p in make_previews():
        print("preview:", p)
