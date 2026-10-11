"""
증강 스카이블럭 — 방어구 세트 A (개척자 / 광부 / 서리 / 화염 / 공허).

각 세트마다 만드는 것
  - textures/entity/equipment/humanoid/<set>.png          (64x32, 흉갑 + 부츠, 바닐라 UV 배치)
  - textures/entity/equipment/humanoid_leggings/<set>.png (64x32, 각반)
  - textures/item/armor/<set>_{chestplate,leggings,boots}.png (16x16 인벤토리 아이콘)
  - models/armor/<set>_helmet.json + items/armor/<set>_helmet.json (3D 투구, 머리에 조각 호박처럼 씀)
    투구 텍스처는 textures/item/armor/<set>_helmet_tex.png (애니메이션) — item/ 폴더라서
    바닐라 blocks 아틀라스에 자동으로 들어간다.

몸 갑옷 텍스처는 ASCII 픽셀 그림(팔레트 글자)으로 직접 그린다. 한 줄이 부위 전개도 한 줄:
  body : [오른쪽 옆 4][앞 8][왼쪽 옆 4][뒤 8]   (UV x=16..40, y=20..32)
  arm  : [바깥 4][앞 4][안쪽 4][뒤 4]           (UV x=40..56, y=20..32)
  leg  : [바깥 4][앞 4][안쪽 4][뒤 4]           (UV x=0..16,  y=20..32)
왼팔/왼다리는 게임이 좌우 반전해서 쓴다.

투구 좌표: 모델 0..16, 중심 (8,8,8), 얼굴은 -Z(north). 머리 큐브는 대략 1.6..14.4.
"""
import json
import math
import os
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from mc3d import FACE_LIGHT, Atlas, Model, _face_corners, _rot_matrix, mat  # noqa: E402

MODULE = "armor_a"
SETS = ["pioneer", "miner", "frost", "flame", "void"]
NAMES_KO = {"pioneer": "개척자", "miner": "광부", "frost": "서리", "flame": "화염", "void": "공허"}
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
STEVE = "/tmp/claude-0/work/ref/steve.png"
PREVIEW_DIR = os.path.join(HERE, "preview")
SCRATCH = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")

F = 16          # 투구 텍스처 애니메이션 프레임 수
FT = 2          # 프레임당 틱 → 32틱(1.6초) 주기
PPU = 0.7       # 투구 표면의 텍셀 밀도 (픽셀 / 모델 단위). 머리 = 8px / 12.8 = 0.625

HEAD_DISPLAY = {
    "gui": {"rotation": [25, 145, 0], "translation": [0, 0, 0], "scale": [0.55, 0.55, 0.55]},
    "ground": {"rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [0.4, 0.4, 0.4]},
    "fixed": {"rotation": [0, 180, 0], "translation": [0, 0, 0], "scale": [0.6, 0.6, 0.6]},
    "thirdperson_righthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
    "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 0, 0], "scale": [0.4, 0.4, 0.4]},
}


def _rng(*k):
    return np.random.default_rng(zlib.crc32(repr(k).encode()))


def C(h):
    """'#rrggbb' → (r, g, b)"""
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ═══════════════════════════════ 몸 갑옷 (64x32) ═══════════════════════════════

def _put(arr, x0, y0, rows, pal, amp, seed, mirror=False):
    """ASCII 줄들을 arr 의 (x0, y0) 에 찍는다. '.' 은 투명."""
    rng = _rng("px", seed, x0, y0)
    for j, row in enumerate(rows):
        if mirror:
            row = row[::-1]
        for i, ch in enumerate(row):
            if ch in ". ":
                continue
            if ch not in pal:
                raise KeyError(f"팔레트에 없는 글자 {ch!r} (seed={seed}, row={j})")
            col = np.array(pal[ch][:3], dtype=float)
            a = amp.get(ch, 0.05)
            col = col * (1 + (rng.random() - 0.5) * 2 * a)
            arr[y0 + j, x0 + i, :3] = np.clip(col, 0, 255)
            arr[y0 + j, x0 + i, 3] = 255


def _check_rows(rows, w, what):
    for r in rows:
        if len(r) != w:
            raise ValueError(f"{what}: 줄 길이 {len(r)} != {w}: {r!r}")


def paint_humanoid(spec):
    """흉갑(몸통+팔) + 부츠(다리 아래쪽). 머리 영역은 비워 둔다 (투구는 3D)."""
    a = np.zeros((32, 64, 4))
    pal, amp, s = spec["pal"], spec.get("amp", {}), spec["id"]
    _check_rows(spec["body"], 24, s + " body")
    _check_rows(spec["arm"], 16, s + " arm")
    _check_rows(spec["boot"], 16, s + " boot")
    _put(a, 16, 20, spec["body"], pal, amp, s)
    _put(a, 40, 20, spec["arm"], pal, amp, s)
    n = len(spec["boot"])
    _put(a, 0, 32 - n, spec["boot"], pal, amp, s)
    _put(a, 20, 16, spec["body_top"], pal, amp, s)        # 어깨 윗면
    _put(a, 28, 16, spec.get("body_bot", ["KKKKKKKK"] * 4), pal, amp, s)
    _put(a, 44, 16, spec["arm_top"], pal, amp, s)
    _put(a, 48, 16, spec["arm_bot"], pal, amp, s)
    _put(a, 8, 16, spec["sole"], pal, amp, s)             # 부츠 밑창
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def paint_leggings(spec):
    a = np.zeros((32, 64, 4))
    pal, amp, s = spec["pal"], spec.get("amp", {}), spec["id"]
    _check_rows(spec["leg"], 16, s + " leg")
    _check_rows(spec["waist"], 24, s + " waist")
    _put(a, 0, 20, spec["leg"], pal, amp, s + "L")
    _put(a, 4, 16, spec["leg_top"], pal, amp, s + "L")
    n = len(spec["waist"])
    _put(a, 16, 32 - n, spec["waist"], pal, amp, s + "L")
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def paint_icon(rows, spec):
    _check_rows(rows, 16, spec["id"] + " icon")
    if len(rows) != 16:
        raise ValueError(spec["id"] + " icon 줄 수 != 16")
    a = np.zeros((16, 16, 4))
    amp = {k: v * 0.6 for k, v in spec.get("amp", {}).items()}
    _put(a, 0, 0, rows, spec["pal"], amp, spec["id"] + "icon")
    return Image.fromarray(a.astype(np.uint8), "RGBA")


# ═══════════════════════════════ 투구 텍스처 페인터 ═══════════════════════════════
# 정적 페인터: fn(w, h) -> (h, w, 4) float 배열.  애니메이션 페인터: fn(f, w, h) -> 배열

def _arr(w, h, col, a=255):
    out = np.zeros((h, w, 4))
    out[..., :3] = np.array(col[:3], dtype=float)
    out[..., 3] = a
    return out


def _grid(w, h):
    return np.meshgrid(np.arange(w), np.arange(h))


def _lerp(c1, c2, t):
    c1 = np.array(c1[:3], dtype=float)
    c2 = np.array(c2[:3], dtype=float)
    t = np.clip(np.asarray(t, dtype=float), 0, 1)[..., None]
    return c1 + (c2 - c1) * t


def S_noise(col, amp=0.12, grad=0.18, seed=0, hi=None, lo=None, bevel=False):
    """기본 재질: 노이즈 + 세로 그라데이션 (+ 테두리 하이라이트/그림자)."""
    def paint(w, h):
        r = _rng("n", col, seed, w, h)
        a = _arr(w, h, col)
        X, Y = _grid(w, h)
        g = 1 + grad / 2 - grad * Y / max(1, h - 1)
        a[..., :3] *= (g * (1 - amp / 2 + amp * r.random((h, w))))[..., None]
        if bevel:
            if hi is not None:
                a[0, :, :3] = a[0, :, :3] * 0.4 + np.array(hi) * 0.6
                a[:, 0, :3] = a[:, 0, :3] * 0.6 + np.array(hi) * 0.4
            if lo is not None:
                a[-1, :, :3] = a[-1, :, :3] * 0.4 + np.array(lo) * 0.6
                a[:, -1, :3] = a[:, -1, :3] * 0.6 + np.array(lo) * 0.4
        return a
    return paint


def S_leather(col, seed=0, stitch=None):
    """가죽: 거친 결 + 군데군데 긁힌 밝은 점 + (선택) 바느질 땀."""
    def paint(w, h):
        a = S_noise(col, 0.16, 0.2, seed)(w, h)
        r = _rng("lea", seed, w, h)
        X, Y = _grid(w, h)
        grain = ((X * 3 + Y * 7 + (Y // 3) * 5) % 11) == 0
        a[grain, :3] *= 0.8
        sc = r.random((h, w)) < 0.04
        a[sc, :3] = a[sc, :3] * 0.6 + np.array(col) * 1.5 * 0.4
        if stitch is not None:
            for yy in (1, h - 2):
                a[yy, ::2, :3] = np.array(stitch)
        return a
    return paint


def S_metal(col, hi, lo, seed=0, rivets=None, step=7):
    """금속판: 대각선 광택 줄 + 테두리 경사 + (선택) 리벳."""
    def paint(w, h):
        a = S_noise(col, 0.06, 0.25, seed, hi=hi, lo=lo, bevel=True)(w, h)
        X, Y = _grid(w, h)
        k = ((X + Y * 2 + seed) % step) / (step - 1)
        a[..., :3] *= (0.86 + 0.3 * np.clip(1 - np.abs(k - 0.35) * 2.2, 0, 1))[..., None]
        if rivets is not None:
            for yy in range(2, h - 1, 5):
                for xx in range(2, w - 1, 5):
                    a[yy, xx, :3] = np.array(rivets)
                    if yy + 1 < h:
                        a[yy + 1, xx, :3] *= 0.6
        return np.clip(a, 0, 255)
    return paint


def S_cloth(col, seed=0, stripe=None):
    def paint(w, h):
        a = S_noise(col, 0.18, 0.22, seed)(w, h)
        X, Y = _grid(w, h)
        a[..., :3] *= np.where((X + Y) % 2 == 0, 1.06, 0.94)[..., None]
        fold = ((X * 2 + seed) % 7) == 0
        a[fold, :3] *= 0.78
        if stripe is not None:
            a[h // 2, :, :3] = np.array(stripe)
        return a
    return paint


def S_wood(col, seed=0):
    def paint(w, h):
        a = S_noise(col, 0.1, 0.1, seed)(w, h)
        X, Y = _grid(w, h)
        ring = (np.sin(X * 0.9 + np.sin(Y * 0.5 + seed) * 2) > 0.6)
        a[ring, :3] *= 0.78
        return a
    return paint


def S_ice(col, light, deep, seed=0):
    """얼음 결정: 위는 밝고 아래는 깊은 푸른빛, 큰 대각선 깎인 면, 드문 흰 결정선."""
    def paint(w, h):
        X, Y = _grid(w, h)
        a = _arr(w, h, col)
        t = Y / max(1, h - 1)
        a[..., :3] = _lerp(light, col, t * 1.6) * (t < 0.6)[..., None] + _lerp(col, deep, (t - 0.6) * 2.2) * (t >= 0.6)[..., None]
        band = ((X + Y * 2 + seed * 3) // 6) % 3
        a[band == 0, :3] = a[band == 0, :3] * 0.88 + np.array(light) * 0.12
        a[band == 2, :3] = a[band == 2, :3] * 0.9 + np.array(deep) * 0.1
        glint = ((X - Y + seed * 7) % 23) == 0
        a[glint, :3] = a[glint, :3] * 0.3 + 255 * 0.7
        r = _rng("ice", seed, w, h)
        a[..., :3] *= (0.97 + 0.06 * r.random((h, w)))[..., None]
        a[0, :, :3] = a[0, :, :3] * 0.4 + 255 * 0.6
        return a
    return paint


def S_obsidian(seed=0):
    def paint(w, h):
        a = S_noise((34, 22, 46), 0.14, 0.25, seed)(w, h)
        r = _rng("obs", seed, w, h)
        X, Y = _grid(w, h)
        sheen = ((X * 2 + Y + seed) % 9) == 0
        a[sheen, :3] = a[sheen, :3] * 0.5 + np.array((92, 64, 128)) * 0.5
        sp = r.random((h, w)) < 0.012
        a[sp, :3] = np.array((112, 86, 150))
        a[0, :, :3] = a[0, :, :3] * 0.6 + np.array((90, 70, 110)) * 0.4
        return a
    return paint


def S_flat(col):
    return lambda w, h: _arr(w, h, col)


def S_pixels(rows, pal):
    """작은 ASCII 그림 그대로 (정적)."""
    def paint(w, h):
        a = np.zeros((h, w, 4))
        _put(a, 0, 0, rows, {k: v for k, v in pal.items()}, {}, "pix")
        return a
    return paint


# ─── 애니메이션 (빛나는 부분) ───

def _pulse(f, speed=1, ph=0.0):
    return 0.5 + 0.5 * math.sin(2 * math.pi * (speed * f / F) + ph)


def A_glow(c_lo, c_mid, c_hi, speed=1, k=0.5, seed=0, sparkle=0.1, axis="y"):
    """물결치는 빛: 어두운 색 → 중간 → 거의 흰 색. 반짝이는 점이 떠다닌다."""
    def paint(f, w, h):
        X, Y = _grid(w, h)
        pos = (Y if axis == "y" else X) + (X if axis == "y" else Y) * 0.4
        v = 0.5 + 0.5 * np.sin(2 * math.pi * speed * f / F - pos * k + seed)
        out = _arr(w, h, c_lo)
        out[..., :3] = _lerp(c_lo, c_mid, v * 1.5)
        out[..., :3] += (_lerp(c_mid, c_hi, (v - 0.6) * 2.5) - np.array(c_mid, dtype=float)) * (v > 0.6)[..., None]
        r = _rng("sp", seed, w, h)
        ph = r.integers(0, F, size=(h, w))
        sel = (r.random((h, w)) < sparkle) & ((ph == f) | (ph == (f + 1) % F))
        out[sel, :3] = 255
        return out
    return paint


def A_gem(c_d, c_m, c_l, seed=0):
    """보석: 가운데 밝은 심, 테두리 깊은 색, 맥동 + 대각선 반짝임이 지나간다."""
    def paint(f, w, h):
        X, Y = _grid(w, h)
        cx, cy = (w - 1) / 2, (h - 1) / 2
        d = np.maximum(np.abs(X - cx) / (w / 2), np.abs(Y - cy) / (h / 2))
        p = _pulse(f)
        out = _arr(w, h, c_d)
        out[..., :3] = _lerp(c_l, c_d, d * (1.25 - 0.35 * p))
        facet = (X + Y) % 4 == 0
        out[facet, :3] = out[facet, :3] * 0.85 + 255 * 0.15
        sweep = ((X - Y) - (f * (w + h) / F - h)) % (w + h)
        shine = np.abs(sweep - 2) < 1.0
        out[shine, :3] = out[shine, :3] * 0.3 + 255 * 0.7
        out[int(cy) - 1, int(cx) - 1, :3] = 255
        return out
    return paint


def A_fire(seed=0, cols=None, alpha=True):
    """불꽃: 위로 흘러 올라가는 혀 모양. 끝은 투명하게 깜빡인다."""
    cols = cols or [(120, 20, 0), (232, 80, 10), (255, 170, 40), (255, 240, 170)]

    def paint(f, w, h):
        X, Y = _grid(w, h)
        yy = Y / max(1, h - 1)                       # 0 위 → 1 아래
        t = f / F * 2 * math.pi
        n = (np.sin(X * 1.7 + Y * 0.9 + t * 2 + seed) + np.sin(X * 0.6 - Y * 1.3 - t * 3 + seed * 2)
             + np.sin(X * 2.9 - t * 1 + seed)) / 3
        heat = yy * 1.15 + n * 0.35 - 0.05
        out = np.zeros((h, w, 4))
        hv = np.clip(heat, 0, 1)
        stops = np.array(cols, dtype=float)
        idx = hv * (len(stops) - 1)
        i0 = np.clip(np.floor(idx).astype(int), 0, len(stops) - 2)
        fr = (idx - i0)[..., None]
        out[..., :3] = stops[i0] * (1 - fr) + stops[i0 + 1] * fr
        out[..., 3] = 255
        if alpha:
            out[heat < 0.18, 3] = 0
        return out
    return paint


def A_overlay(col_lo, col_hi, pattern, speed=1, seed=0):
    """투명 바탕에 빛나는 무늬(균열/룬)만. 같은 크기 박스를 살짝 키워 겹쳐서 '발광 덧칠'로 쓴다.
    pattern(w, h) -> bool 마스크."""
    def paint(f, w, h):
        m = pattern(w, h)
        X, Y = _grid(w, h)
        v = 0.5 + 0.5 * np.sin(2 * math.pi * speed * f / F - (X + Y) * 0.45 + seed)
        out = np.zeros((h, w, 4))
        out[..., :3] = _lerp(col_lo, col_hi, v)
        out[..., 3] = np.where(m, 255, 0)
        return out
    return paint


def M_cracks(seed=0, density=3):
    """갈라진 마그마 균열 마스크: 대각선으로 흐르는 가는 선 + 짧은 가지."""
    def mask(w, h):
        r = _rng("crack", seed, w, h)
        m = np.zeros((h, w), dtype=bool)

        def walk(x, y, n, dx):
            for _ in range(n):
                m[y % h, x % w] = True
                if r.random() < 0.55:
                    y += 1
                else:
                    x += dx
                if r.random() < 0.12:
                    walk(x, y, n // 2, -dx)
                    n = n // 2 + 1
        for _ in range(max(1, density * w * h // 300)):
            walk(int(r.integers(0, w)), int(r.integers(0, h)), int(r.integers(6, 12)), 1 if r.random() < 0.5 else -1)
        return m
    return mask


GLYPHS = [  # 3x4 룬 글자
    ["X.X", ".X.", "X.X", ".X."], ["XXX", "X..", "XX.", "X.."], [".X.", "XXX", ".X.", "X.X"],
    ["X..", "XX.", "X.X", "XXX"], ["XXX", ".X.", ".X.", "X.X"], ["X.X", "XXX", "X.X", ".X."],
    [".XX", "X..", ".X.", "XX."], ["X.X", "X.X", ".X.", ".X."],
]


def M_runes(seed=0, line=True):
    """룬 글자 띠 마스크: 위아래 가는 선 + 4px 간격 글자."""
    def mask(w, h):
        m = np.zeros((h, w), dtype=bool)
        r = _rng("rune", seed, w, h)
        top = max(0, (h - 4) // 2)
        for x0 in range(0, w - 2, 4):
            if x0 + 3 > w:
                break
            g = GLYPHS[r.integers(0, len(GLYPHS))]
            for j, row in enumerate(g):
                for i, ch in enumerate(row):
                    if ch == "X" and top + j < h and x0 + i < w:
                        m[top + j, x0 + i] = True
        if line and h >= 7:
            m[top - 1 if top > 0 else 0, :] = True
            m[min(h - 1, top + 4), :] = True
        return m
    return mask


# ═══════════════════════════════ 투구 빌더 ═══════════════════════════════

FACE_DIMS = {"north": (0, 1), "south": (0, 1), "east": (2, 1), "west": (2, 1), "up": (0, 2), "down": (0, 2)}
ALL = ("north", "south", "east", "west", "up", "down")


class Helm:
    """투구 하나 = 모델 하나 + 애니메이션 아틀라스 하나."""

    def __init__(self, sid, size=64):
        self.sid = sid
        self.at = Atlas(f"item/armor/{sid}_helmet_tex", size, F, FT, interpolate=True)
        self.m = Model(f"armor/{sid}_helmet")
        self.m.use("t", self.at)
        self.mats = {}
        self.n = 0

    def mat(self, name, painter, w=16, h=16, anim=False):
        reg = self.at.alloc(w, h)
        for f in range(F):
            a = painter(f, w, h) if anim else painter(w, h)
            reg.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA"), f)
        self.mats[name] = reg
        return reg

    def faces(self, name, frm, to, skip=(), whole=(), salt=0):
        """면 크기에 맞춰 재질 영역의 일부를 잘라 쓴다 (텍셀 밀도 일정). whole 면은 영역 전체."""
        reg = self.mats[name]
        r = _rng("uv", self.sid, name, tuple(frm), tuple(to), salt)
        size = [abs(to[i] - frm[i]) for i in range(3)]
        out = {}
        for f in ALL:
            if f in skip:
                continue
            if f in whole or whole == "all":
                out[f] = ("t", reg)
                continue
            a, b = FACE_DIMS[f]
            pw = min(reg.w, max(1.0, size[a] * PPU))
            ph = min(reg.h, max(1.0, size[b] * PPU))
            ox = int(r.integers(0, int(reg.w - pw) + 1))
            oy = int(r.integers(0, int(reg.h - ph) + 1))
            out[f] = ("t", reg.uv((ox, oy, ox + pw, oy + ph)))
        return out

    def box(self, frm, to, name, light=0, rot=None, skip=(), whole=(), shade=True, salt=0):
        frm = [float(v) for v in frm]
        to = [float(v) for v in to]
        for i in range(3):
            if frm[i] > to[i]:
                frm[i], to[i] = to[i], frm[i]
        rotation = None
        if rot:
            axis, ang, origin = rot
            rotation = {"origin": list(origin), "axis": axis, "angle": ang}
        self.m.box(frm, to, self.faces(name, frm, to, skip, whole, salt), light=light, shade=shade, rotation=rotation)
        self.n += 1

    def pair(self, frm, to, name, light=0, rot=None, skip=(), whole=(), salt=0):
        """x=8 을 기준으로 좌우 대칭 한 쌍."""
        self.box(frm, to, name, light, rot, skip, whole, salt=salt)
        mf = [16 - to[0], frm[1], frm[2]]
        mt = [16 - frm[0], to[1], to[2]]
        mrot = None
        if rot:
            axis, ang, origin = rot
            o = [16 - origin[0], origin[1], origin[2]]
            mrot = (axis, -ang if axis in ("y", "z") else ang, o)
        sk = tuple({"east": "west", "west": "east"}.get(s, s) for s in skip)
        wh = whole if whole == "all" else tuple({"east": "west", "west": "east"}.get(s, s) for s in whole)
        self.box(mf, mt, name, light, mrot, sk, wh, salt=salt + 1)

    def glow_skin(self, frm, to, name, eps=0.06, light=15, skip=(), rot=None, whole=()):
        """같은 박스를 eps 만큼 키워 투명 바탕 발광 무늬를 덧입힌다."""
        f2 = [v - eps for v in frm]
        t2 = [v + eps for v in to]
        self.box(f2, t2, name, light=light, skip=skip, rot=rot, shade=False, whole=whole)

    def spike(self, base, w, hgt, name, tip=None, segs=3, light=0, tip_light=0, axis=None, ang=0, origin=None,
              taper=0.62):
        """위로 솟는 뾰족한 가시: 위로 갈수록 가늘어지는 박스를 쌓는다. (axis, ang) 로 통째로 기울인다."""
        x, y, z = base
        cw, cy = w, y
        seg_h = hgt / segs
        org = origin or (x, y, z)
        for i in range(segs):
            hh = seg_h * (1.15 if i < segs - 1 else 1.0)
            n = tip if (tip and i == segs - 1) else name
            lt = tip_light if (tip and i == segs - 1) else light
            rot = (axis, ang, org) if axis else None
            self.box((x - cw / 2, cy, z - cw / 2), (x + cw / 2, cy + hh, z + cw / 2), n, light=lt, rot=rot,
                     salt=i)
            cy += seg_h
            cw *= taper

    def fit_display(self):
        """모델 크기에 맞춰 gui/ground/fixed 의 크기와 중심을 맞춘다 (뿔/후광이 칸 밖으로 나가지 않게)."""
        lo, hi = self.m.bounds()
        # 회전된 element 는 모서리가 bounds 를 살짝 넘을 수 있어 여유를 둔다
        lo = np.array(lo) - 0.8
        hi = np.array(hi) + 0.8
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]) - 8
        cen = (lo + hi) / 2 - 8
        disp = json.loads(json.dumps(HEAD_DISPLAY))
        for key, target, cap in (("gui", 15.0, 0.62), ("fixed", 15.0, 0.62), ("ground", 9.0, 0.4)):
            rx, ry, rz = [math.radians(v) for v in disp[key]["rotation"]]
            R = _rot_matrix("x", math.degrees(rx)) @ _rot_matrix("y", math.degrees(ry)) @ _rot_matrix("z", math.degrees(rz))
            p = corners @ R.T
            ext = max(p[:, 0].max() - p[:, 0].min(), p[:, 1].max() - p[:, 1].min())
            sc = round(min(cap, target / ext), 3)
            c = R @ (cen * sc)
            tr = [round(float(np.clip(-c[0], -80, 80)), 2), round(float(np.clip(-c[1], -80, 80)), 2), 0]
            if key == "ground":
                tr[1] += 3
            disp[key]["scale"] = [sc, sc, sc]
            disp[key]["translation"] = tr
        span = float(max(hi - lo))
        for key in ("thirdperson_righthand", "firstperson_righthand"):
            sc = round(min(disp[key]["scale"][0], disp[key]["scale"][0] * 18.0 / span), 3)
            disp[key]["scale"] = [sc, sc, sc]
        return disp

    def finish(self, assets_root, display=None):
        self.m.display = display or self.fit_display()
        self.at.save(os.path.join(assets_root, "textures"))
        self.m.write(assets_root)
        return "augsky:" + self.m.name


# ═══════════════════════════════ z-버퍼 미리보기 렌더러 ═══════════════════════════════
# (mc3d.render 는 면 단위 정렬이라 겹치는 박스가 많은 투구에서 앞뒤가 뒤집혀 보여서 따로 만든다)

def _frame(atlas, f):
    s = atlas.size
    f = f % atlas.frames
    return np.array(atlas.img.crop((0, f * s, s, f * s + s)))


def zrender(parts, size=320, yaw=-35, pitch=25, frame=0, bg=(22, 20, 30), ss=2, pad=0.08, night=False,
            fit=None):
    """parts: [(Model, 4x4 행렬)]. 카메라는 +z 쪽에서 -z 를 본다 (mc3d.render 와 같은 각도 규칙)."""
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
                    w4 = M @ np.append(v, 1.0)
                    pts.append(view @ w4[:3])
                pts = np.array(pts)
                n = np.cross(pts[1] - pts[0], pts[3] - pts[0])
                if n[2] >= -1e-9:
                    continue
                if glow >= 8 or not el.get("shade", True) and glow:
                    lt = 1.0
                else:
                    lt = FACE_LIGHT[fname] if el.get("shade", True) else 1.0
                    if night:
                        lt = lt * 0.22 + 0.06 * glow
                faces.append((pts, tex, fd["uv"], fd.get("rotation", 0), lt))
    S = size * ss
    img = np.zeros((S, S, 3))
    img[...] = np.array(bg[:3], dtype=float) * (0.5 if night else 1.0)
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
    faces.sort(key=lambda fc: fc[0][:, 2].mean())   # 먼 면부터 (반투명 섞기용)
    for pts, tex, uv, frot, lt in faces:
        scr = np.stack([(pts[:, 0] - cx) * sc + S / 2, -(pts[:, 1] - cy) * sc + S / 2], 1)
        th, tw = tex.shape[:2]
        u0, v0, u1, v1 = uv[0] / 16 * tw, uv[1] / 16 * th, uv[2] / 16 * tw, uv[3] / 16 * th
        src = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for _ in range(int(frot) // 90):
            src = src[1:] + src[:1]
        src = np.array(src)
        e1 = scr[1] - scr[0]
        e2 = scr[3] - scr[0]
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
        lo_u, hi_u = min(src[:, 0]), max(src[:, 0])
        lo_v, hi_v = min(src[:, 1]), max(src[:, 1])
        iu = np.clip(np.floor(np.clip(tu, lo_u, hi_u - 1e-3)).astype(int), 0, tw - 1)
        iv = np.clip(np.floor(np.clip(tv, lo_v, hi_v - 1e-3)).astype(int), 0, th - 1)
        texel = tex[iv, iu].astype(float)
        al = texel[..., 3]
        sub = zb[y0:y1, x0:x1]
        front = inside & (z > sub + 1e-7)
        ok = front & (al >= 200)
        if ok.any():
            sub[ok] = z[ok]
            img[y0:y1, x0:x1][ok] = texel[..., :3][ok] * lt
        tr = front & (al >= 12) & (al < 200)        # 반투명: 섞기만, 깊이는 안 씀
        if tr.any():
            k = (al[tr] / 255.0)[:, None]
            blk = img[y0:y1, x0:x1]
            blk[tr] = blk[tr] * (1 - k) + texel[..., :3][tr] * lt * k
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return out.resize((size, size), Image.LANCZOS) if ss > 1 else out


# ═══════════════════════════════ 착용 마네킹 (미리보기) ═══════════════════════════════

def _tex_model(name, img):
    """64xN 이미지를 64 크기 아틀라스에 담은 미리보기용 모델."""
    at = Atlas("_preview/" + name, 64, 1)
    at.img.alpha_composite(img.convert("RGBA").crop((0, 0, 64, min(64, img.height))), (0, 0))
    m = Model("_preview/" + name)
    m.use("t", at)
    return m


def _limb(m, frm, to, u, v, w, h, d, infl=0.0, mirror=False):
    """엔티티 박스 하나: 바닐라 전개도 (u,v,w,h,d) 를 6면에 붙인다. 얼굴 = -Z, 플레이어 오른쪽 = +X."""
    k = 16.0 / 64.0

    def U(x0, y0, x1, y1, flip=False):
        if flip:
            x0, x1 = x1, x0
        return [x0 * k, y0 * k, x1 * k, y1 * k]

    front = (u + d, v + d, u + d + w, v + d + h)
    right = (u, v + d, u + d, v + d + h)
    left = (u + d + w, v + d, u + 2 * d + w, v + d + h)
    back = (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h)
    top = (u + d + w, v + d, u + d, v)          # 180도 돌린 윗면
    bot = (u + d + w, v, u + 2 * d + w, v + d)
    if not mirror:
        faces = {"north": ("t", U(*front)), "east": ("t", U(*right)), "west": ("t", U(*left)),
                 "south": ("t", U(*back)), "up": ("t", [c * k for c in top]), "down": ("t", U(*bot))}
    else:
        faces = {"north": ("t", U(*front, flip=True)), "west": ("t", U(*right, flip=True)),
                 "east": ("t", U(*left, flip=True)), "south": ("t", U(*back, flip=True)),
                 "up": ("t", [top[2] * k, top[1] * k, top[0] * k, top[3] * k]), "down": ("t", U(*bot, flip=True))}
    f = [frm[i] - infl for i in range(3)]
    t = [to[i] + infl for i in range(3)]
    m.box(f, t, faces)


def mannequin(humanoid, leggings, helmet=None):
    """스티브 + 각반(0.5 부풀림) + 흉갑/부츠(1.0 부풀림) + 3D 투구."""
    steve = Image.open(STEVE).convert("RGBA")
    base = _tex_model("steve", steve)
    # 몸 중심 x=8, z=8.  다리 y 0..12, 몸 12..24, 머리 24..32
    _limb(base, (4, 24, 4), (12, 32, 12), 0, 0, 8, 8, 8)              # 머리
    _limb(base, (4, 12, 6), (12, 24, 10), 16, 16, 8, 12, 4)           # 몸
    _limb(base, (12, 12, 6), (16, 24, 10), 40, 16, 4, 12, 4)          # 오른팔 (+X)
    _limb(base, (0, 12, 6), (4, 24, 10), 40, 16, 4, 12, 4, mirror=True)
    _limb(base, (8, 0, 6), (12, 12, 10), 0, 16, 4, 12, 4)             # 오른다리
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
        parts.append((helmet, mat((0, 20 / 16, 0), 0.625)))
    return parts


# ═══════════════════════════════ 세트 정의 ═══════════════════════════════
SPECS = {}     # sid -> 픽셀 그림 사양
HELMETS = {}   # sid -> fn(Helm) -> Helm

# ─────────────────────────── 1) 개척자 pioneer ───────────────────────────
# 갈색 가죽 재킷 + 초록 스카프/짧은 망토 + 나무 토글 단추 + 놋쇠 버클.
# 투구: 가죽 탐험가 모자 + 놋쇠 고글(렌즈가 은은하게 빛남) + 초록 깃털 두 개.

SPECS["pioneer"] = {
    "id": "pioneer",
    "notes": "가죽 재킷·초록 스카프 망토·나무 토글, 탐험가 모자+발광 고글+깃털",
    "pal": {
        "K": C("2c180c"), "d": C("4a2c14"), "D": C("5e3a1e"), "M": C("7c4f2b"), "L": C("9c6a3c"),
        "W": C("c08d56"), "s": C("e0c49a"), "a": C("245c2c"), "A": C("3e8a3c"), "B": C("74c25c"),
        "e": C("a8743a"), "E": C("dcae64"), "r": C("b48a2e"), "R": C("f6d87c"),
        "c": C("6f6648"), "C": C("978b62"), "h": C("bfb383"),
    },
    "amp": {"s": 0.02, "R": 0.0, "r": 0.03, "E": 0.03},
    #          오른옆      앞        왼옆       뒤(망토)
    "body": [
        "AaBA" + "aABBBBAa" + "ABaA" + "aABBBBAa",
        "MDaA" + "WaABBAaW" + "AaDM" + "aAABBAAa",
        "LMDM" + "LMaABaML" + "MDML" + "AAaBBaAA",
        "LMDM" + "LWMaaMWL" + "MDML" + "ABAaaABA",
        "MLMD" + "MdRsEdRM" + "DMLM" + "AABAABAA",
        "MLMD" + "MLLsKLLM" + "DMLM" + "aAAaaAAa",
        "DMLD" + "MLWsEWLM" + "DLMD" + "AaBAABaA",
        "DMLD" + "MDDsKDDM" + "DLMD" + "aAAaaAAa",
        "KKrK" + "KKKrRKKK" + "KrKK" + "AaAAAAaA",
        "DMMD" + "LMWsEsWL" + "DMMD" + "aAaAAaAa",
        "DLMD" + "MLMsKsLM" + "DMLD" + "DaDAMaAD",
        "KDDK" + "DDDdddDD" + "KDDK" + "DDKDDKDD",
    ],
    "body_top": ["MaBAABaM", "LAaBBaAL", "LaABBAaL", "MaBBBBaM"],
    #        바깥    앞     안쪽    뒤
    "arm": [
        "LWWL" + "LWWL" + "LWWL" + "LWWL",
        "MLLM" + "MLLM" + "MLLM" + "MLLM",
        "DMMD" + "MLMD" + "DMMD" + "DMLM",
        "ssss" + "ssss" + "ssss" + "ssss",
        "aAAa" + "aABa" + "aAAa" + "aBAa",
        "AaaA" + "AaaA" + "AaaA" + "AaaA",
        "CChC" + "ChCC" + "CChC" + "ChCC",
        "cCCc" + "cCCc" + "cCCc" + "cCCc",
        "CcCC" + "CCcC" + "CcCC" + "CCcC",
        "KDDK" + "DMMD" + "KDDK" + "DMMD",
        "DMLD" + "MEKL" + "DLMD" + "MLMD",
        "dKKd" + "dKKd" + "dKKd" + "dKKd",
    ],
    "arm_top": ["LWWL", "WLLW", "WLLW", "LWWL"],
    "arm_bot": ["dKKd", "KddK", "KddK", "dKKd"],
    "boot": [
        "LWWL" + "LWWL" + "LWWL" + "LWWL",
        "MLLM" + "MLLM" + "MLLM" + "MLLM",
        "KKKK" + "KrRK" + "KKKK" + "KKKK",
        "DMMD" + "MLLM" + "DMMD" + "DMMD",
        "DMLD" + "MLWM" + "DLMD" + "DMLD",
        "DDMD" + "WLLW" + "DMDD" + "DDDD",
        "KKKK" + "KddK" + "KKKK" + "KKKK",
    ],
    "sole": ["KddK", "dKKd", "dKKd", "KddK"],
    "leg": [
        "CCCC" + "CCCC" + "CCCC" + "CCCC",
        "CChC" + "ChCC" + "CChC" + "ChCC",
        "cDDc" + "ChCC" + "CCCC" + "CCCC",
        "cDMc" + "CCCc" + "CCCC" + "cCCC",
        "cDMc" + "CChC" + "CChC" + "CCCC",
        "cDDc" + "DMMD" + "CCCC" + "CChC",
        "CCCC" + "MWLM" + "CCCC" + "CCCC",
        "CChC" + "DMMD" + "CChC" + "cCCc",
        "cCCc" + "cCCc" + "cCCc" + "cCCc",
        "aAAa" + "aABa" + "aAAa" + "aBAa",
    ],
    "leg_top": ["CCCC", "ChCC", "CChC", "CCCC"],
    "waist": [
        "CCCC" + "CCCCCCCC" + "CCCC" + "CCCCCCCC",
        "CChC" + "ChCCCChC" + "ChCC" + "CChCCChC",
        "KKKK" + "KKKrRKKK" + "KKKK" + "KKKKKKKK",
        "CCCC" + "CCChhCCC" + "CCCC" + "CCCCCCCC",
        "cDDc" + "CCcCCcCC" + "cDDc" + "CCCCCCCC",
        "cDDc" + "cCCcCCCc" + "cDDc" + "cCCCCCCc",
    ],
    "icons": {
        "chestplate": [
            "................",
            "..KKKK....KKKK..",
            ".KLWWLKKKKLWWLK.",
            ".KLLLaABBAaLLLK.",
            ".KMMLaAAAAaLMMK.",
            ".KDMMLaBBaLMMDK.",
            ".KKDMWLaaLWMDKK.",
            "..KKdRdsEdRdKK..",
            "...KLWLsKLWLK...",
            "...KLLLsELLLK...",
            "...KDDDsKDDDK...",
            "...KKKKrRKKKK...",
            "...KLMWsEsWMK...",
            "...KMLMsKsLMK...",
            "...KKKKKKKKKK...",
            "................",
        ],
        "leggings": [
            "................",
            "..KKKKKKKKKKKK..",
            "..KdddKrRKdddK..",
            "..KCChCCCCChCK..",
            "..KCCCCKKCCCCK..",
            "..KcCCK..KCCcK..",
            "..KDMMK..KMMDK..",
            "..KMWLK..KLWMK..",
            "..KDMMK..KMMDK..",
            "..KCChK..KhCCK..",
            "..KcCCK..KCCcK..",
            "..KaAAK..KAAaK..",
            "..KABAK..KABAK..",
            "..KKKKK..KKKKK..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "................",
            "...KKKK..KKKK...",
            "...KWWK..KWWK...",
            "...KLLK..KLLK...",
            "...KrRK..KRrK...",
            "...KMMK..KMMK...",
            "...KDMK..KMDK...",
            ".KKDMMK..KMMDKK.",
            ".KLWMMK..KMMWLK.",
            ".KMLMDK..KDMLMK.",
            ".KKKKKK..KKKKKK.",
            "................",
            "................",
        ],
    },
}


def _feather(col_d, col_m, col_l, tip):
    """깃털 그림 (세로로 긴 잎 모양, 가운데 깃대)."""
    def paint(w, h):
        a = np.zeros((h, w, 4))
        cx = (w - 1) / 2
        for y in range(h):
            t = y / (h - 1)                         # 0 = 위 끝
            half = (w / 2) * math.sin(min(1.0, t * 1.25) * math.pi) ** 0.7
            for x in range(w):
                dx = abs(x - cx)
                if dx <= half + 0.2 and t < 0.92:
                    c = _lerp(col_l, col_d, dx / max(0.5, half + 0.5))
                    if t < 0.22:
                        c = _lerp(tip, c, t / 0.22)
                    if (y + x) % 4 == 0:
                        c = c * 0.82
                    a[y, x, :3] = c
                    a[y, x, 3] = 255
            # 깃대
            if t > 0.05:
                a[y, int(cx), :3] = np.array(col_m) * 0.55 + 255 * 0.3
                a[y, int(cx), 3] = 255
        return a
    return paint


def A_compass():
    """나침반 문자판: 크림색 판 + 흔들리는 붉은 바늘."""
    def paint(f, w, h):
        out = _arr(w, h, (236, 222, 180))
        X, Y = _grid(w, h)
        cx, cy = (w - 1) / 2, (h - 1) / 2
        d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        out[d > w / 2 - 0.6, :3] = (150, 110, 40)
        out[(np.abs(X - cx) < 0.6) | (np.abs(Y - cy) < 0.6), :3] *= 0.85
        ang = math.radians(20 * math.sin(2 * math.pi * f / F) + 35)
        for t in np.linspace(0, w / 2 - 1.2, 12):
            x, y = int(round(cx + math.sin(ang) * t)), int(round(cy - math.cos(ang) * t))
            out[y, x, :3] = (220, 30, 20)
            x, y = int(round(cx - math.sin(ang) * t)), int(round(cy + math.cos(ang) * t))
            out[y, x, :3] = (60, 60, 70)
        return out
    return paint


def helm_pioneer(H):
    H.mat("lea", S_leather(C("7c4f2b"), seed=0))
    H.mat("lea_d", S_leather(C("4e2f17"), seed=1))
    H.mat("lea_l", S_leather(C("a2703f"), seed=2, stitch=C("e8cc9e")))
    H.mat("brass", S_metal(C("c49a3a"), hi=C("fff0b0"), lo=C("5e4210"), seed=1), 8, 8)
    H.mat("lens", A_glow(C("1e5a66"), C("4fd0c4"), C("eafff8"), speed=1, k=0.7, sparkle=0.06), 8, 8, anim=True)
    H.mat("feather", _feather(C("1d5a2a"), C("3f9a3e"), C("8ee070"), C("f4f0d0")), 8, 32)
    H.mat("feather2", _feather(C("6a3a18"), C("b06a2c"), C("f0b060"), C("fff4d8")), 8, 32)
    H.mat("green", S_cloth(C("3a7a3a"), seed=1))
    H.mat("green_l", S_cloth(C("5aa04a"), seed=2), 8, 8)
    H.mat("compass", A_compass(), 8, 8, anim=True)

    # 둥근 모자 (가죽): 윗판 + 한 단 더 올린 정수리 + 꼭지 단추
    H.box((0.8, 14.4, 0.8), (15.2, 15.6, 15.2), "lea")
    H.box((2.2, 15.6, 2.2), (13.8, 16.8, 13.8), "lea")
    H.box((4.6, 16.8, 4.6), (11.4, 17.4, 11.4), "lea_l")
    H.box((7.2, 17.4, 7.2), (8.8, 18.0, 8.8), "lea_d")
    # 옆판/뒤판 + 귀덮개
    H.pair((0.4, 7.0, 0.8), (1.6, 14.4, 15.2), "lea")
    H.box((1.6, 3.6, 14.4), (14.4, 14.4, 15.6), "lea")
    H.pair((-0.2, 3.4, 4.6), (1.4, 8.4, 11.0), "lea_l")
    H.pair((-0.5, 4.4, 6.8), (-0.2, 6.2, 8.8), "brass")         # 귀덮개 놋쇠 단추
    # 앞 이마띠 + 챙
    H.box((1.6, 11.0, 0.4), (14.4, 14.4, 1.6), "lea_d")
    H.box((1.0, 10.4, -3.6), (15.0, 11.2, 0.6), "lea_l")
    H.box((2.6, 10.0, -4.6), (13.4, 10.8, -3.2), "lea_d")
    # 모자 띠 (초록 천)
    H.pair((0.0, 12.6, 0.4), (0.4, 14.0, 15.6), "green")
    H.box((0.4, 12.6, 15.6), (15.6, 14.0, 16.0), "green")
    # 놋쇠 고글: 테 + 빛나는 렌즈 + 콧등
    H.pair((2.4, 11.6, -1.2), (7.4, 15.8, 0.4), "brass")
    H.pair((3.0, 12.2, -1.6), (6.8, 15.2, -1.2), "lens", light=11, whole="all")
    H.box((7.4, 13.0, -0.8), (8.6, 14.2, 0.4), "brass")
    # 깃털 두 개 (플레이어 왼쪽 = -X), 바깥으로 22.5도 기울임
    H.box((-0.8, 12.0, 7.4), (-0.2, 28.0, 12.2), "feather", rot=("z", 22.5, (-0.5, 12.0, 9.8)),
          whole=("east", "west"))
    H.box((-0.4, 12.0, 9.4), (0.2, 24.0, 13.4), "feather2", rot=("x", 22.5, (-0.1, 12.0, 11.4)),
          whole=("east", "west"))
    H.box((-0.9, 11.6, 8.6), (0.5, 13.6, 12.6), "brass")           # 깃털 꽂는 놋쇠 핀
    # 정수리 바느질 솔기
    H.box((7.5, 16.8, 2.2), (8.5, 17.0, 13.8), "lea_d")
    H.box((2.2, 16.8, 7.5), (13.8, 17.0, 8.5), "lea_d")
    # 오른쪽 띠의 나침반 (바늘이 흔들림)
    H.box((15.6, 10.8, 5.4), (16.6, 15.0, 9.6), "brass")
    H.box((16.6, 11.4, 6.0), (16.8, 14.4, 9.0), "compass", light=7, whole="all")
    # 뒤로 휘날리는 스카프 매듭 + 꼬리 두 갈래
    H.box((1.0, 11.8, 15.4), (4.4, 14.6, 17.0), "green")
    H.box((1.4, 11.0, 16.4), (3.8, 13.2, 23.4), "green", rot=("x", 22.5, (2.6, 12.1, 16.4)))
    H.box((2.8, 10.0, 16.2), (4.6, 11.8, 21.4), "green_l", rot=("x", 45, (3.7, 10.9, 16.2)))
    return H


HELMETS["pioneer"] = helm_pioneer


# ─────────────────────────── 2) 광부 miner ───────────────────────────
# 철판 + 구리 테두리/리벳, 교차한 곡괭이 문장, 데님 작업복.
# 투구: 철 안전모 + 구리 능선 + 앞쪽 큰 램프(빛남, 십자 광채) + 옆 호박색 보조등 + 뒤 배터리.

SPECS["miner"] = {
    "id": "miner",
    "notes": "철판+구리 리벳 작업 갑옷, 안전모+발광 램프(십자 광채)+보조등+배터리",
    "pal": {
        "K": C("18181e"), "D": C("464b56"), "M": C("767d8a"), "L": C("a6adb9"), "W": C("e4e9f0"),
        "r": C("cdd2da"), "o": C("6a3216"), "c": C("b0602c"), "C": C("e48c4a"), "h": C("ffc88e"),
        "p": C("3f8f7c"), "l": C("33241a"), "e": C("5c4128"), "E": C("80603c"),
        "u": C("26344e"), "U": C("3e5478"), "V": C("5c76a0"), "y": C("ffd84a"),
    },
    "amp": {"W": 0.02, "r": 0.0, "y": 0.0, "h": 0.02},
    "body": [
        "oCCC" + "oCChhCCo" + "CCCo" + "oCCCCCCo",
        "DLMc" + "cLWWWWLc" + "cMLD" + "DLcLLcLD",
        "DrMc" + "cLrLLrLc" + "cMrD" + "DLcrrcLD",
        "DLMc" + "cMhDDhMc" + "cMLD" + "DMcMMcMD",
        "DMMc" + "cMDhCDMc" + "cMMD" + "DMcMMcMD",
        "DMMc" + "cMDChDMc" + "cMMD" + "DrcMMcrD",
        "DMMc" + "cMhDDhMc" + "cMMD" + "DMcMMcMD",
        "DDMc" + "cDMMMMDc" + "cMDD" + "DDcDDcDD",
        "Kllo" + "lleyyell" + "olll" + "llllllll",
        "DLMD" + "DLMDDMLD" + "DMLD" + "DLMDDMLD",
        "DMrD" + "DMrDDrMD" + "DrMD" + "DMrDDrMD",
        "KDDK" + "KDDKKDDK" + "KDDK" + "KDDKKDDK",
    ],
    "body_top": ["oCCCCCCo", "cLWLLWLc", "cLWLLWLc", "oCCCCCCo"],
    "arm": [
        "LWWL" + "LWWL" + "LWWL" + "LWWL",
        "LLrL" + "LrLL" + "LLrL" + "LrLL",
        "MLLM" + "MLLM" + "MLLM" + "MLLM",
        "DMMD" + "DMMD" + "DMMD" + "DMMD",
        "oCCo" + "oChc" + "oCCo" + "cCCo",
        "uUUu" + "uUVu" + "uUUu" + "uVUu",
        "UuuU" + "UuuU" + "UuuU" + "UuuU",
        "uUUu" + "uUUu" + "uUUu" + "uUUu",
        "oCCo" + "oCCo" + "oCCo" + "oCCo",
        "cCrc" + "chCc" + "crCc" + "cChc",
        "cCCc" + "cCCc" + "cCCc" + "cCCc",
        "oooo" + "oooo" + "oooo" + "oooo",
    ],
    "arm_top": ["LWWL", "WLLW", "WLLW", "LWWL"],
    "arm_bot": ["oooo", "occo", "occo", "oooo"],
    "boot": [
        "oCCo" + "oChc" + "oCCo" + "oCCo",
        "eEEe" + "eEEe" + "eEEe" + "eEEe",
        "elle" + "eyye" + "elle" + "elle",
        "eEEe" + "EEEE" + "eEEe" + "eEEe",
        "elEe" + "cCCc" + "eElE" + "eeEe",
        "eeee" + "CChC" + "eeee" + "eeee",
        "KKKK" + "KooK" + "KKKK" + "KKKK",
    ],
    "sole": ["KooK", "oKKo", "oKKo", "KooK"],
    "leg": [
        "uUUu" + "uUUu" + "uUUu" + "uUUu",
        "UUVU" + "UVUU" + "UUVU" + "UVUU",
        "uUcU" + "UUUu" + "UcUu" + "UUUU",
        "uUUU" + "UVUU" + "UUUu" + "uUUU",
        "UuUU" + "DLLD" + "UUuU" + "UUUu",
        "UUuU" + "LWrL" + "UuUU" + "UUUU",
        "uUUU" + "MLLM" + "UUUu" + "uUUU",
        "UUVU" + "DMMD" + "UVUU" + "UVUU",
        "uUUu" + "uUUu" + "uUUu" + "uUUu",
        "uuuu" + "uuuu" + "uuuu" + "uuuu",
    ],
    "leg_top": ["UUUU", "UVUU", "UUVU", "UUUU"],
    "waist": [
        "UUUU" + "UUVUUVUU" + "UUUU" + "UUUUUUUU",
        "llll" + "lleyyell" + "llll" + "llllllll",
        "UcUU" + "UUUUUUUU" + "UUcU" + "UUUUUUUU",
        "EeeE" + "UVUUUUVU" + "EeeE" + "UUVUUVUU",
        "EyeE" + "UUcUUcUU" + "EeyE" + "UUUUUUUU",
        "eeee" + "uUUuuUUu" + "eeee" + "uUUuuUUu",
    ],
    "icons": {
        "chestplate": [
            "................",
            "..KKKK....KKKK..",
            ".KLWWLKKKKLWWLK.",
            ".KLrLLoCCoLLrLK.",
            ".KMLMLcLLcLMLMK.",
            ".KDMMMcLLcMMMDK.",
            ".KKDMcWchWcMDKK.",
            "..KKMcMhcMcMKK..",
            "...KcLMchMLcK...",
            "...KcMcLLcMcK...",
            "...KcDMMMMDcK...",
            "...KlleyyellK...",
            "...KLMrDDrMLK...",
            "...KDMDKKDMDK...",
            "...KKKK..KKKK...",
            "................",
        ],
        "leggings": [
            "................",
            "..KKKKKKKKKKKK..",
            "..KllleyyelllK..",
            "..KUUVUUUUVUUK..",
            "..KUcUUKKUUcUK..",
            "..KUUUK..KUUUK..",
            "..KLWLK..KLWLK..",
            "..KMrMK..KMrMK..",
            "..KDMDK..KDMDK..",
            "..KUVUK..KUVUK..",
            "..KUUUK..KUUUK..",
            "..KuUuK..KuUuK..",
            "..KuuuK..KuuuK..",
            "..KKKKK..KKKKK..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "................",
            "...KKKK..KKKK...",
            "...KChK..KhCK...",
            "...KEEK..KEEK...",
            "...KyyK..KyyK...",
            "...KEeK..KeEK...",
            "...KeEK..KEeK...",
            ".KKeEeK..KeEeKK.",
            ".KCChcK..KchCCK.",
            ".KocCcK..KcCcoK.",
            ".KKKKKK..KKKKKK.",
            "................",
            "................",
        ],
    },
}


def A_lamp(c_out, c_mid, c_core):
    """램프 렌즈: 동심원 빛, 천천히 맥동 + 깜빡임 없는 따뜻한 빛."""
    def paint(f, w, h):
        X, Y = _grid(w, h)
        cx, cy = (w - 1) / 2, (h - 1) / 2
        d = np.sqrt(((X - cx) / (w / 2)) ** 2 + ((Y - cy) / (h / 2)) ** 2)
        p = _pulse(f)
        out = _arr(w, h, c_out)
        out[..., :3] = _lerp(c_core, c_mid, d * (1.3 - 0.4 * p))
        edge = d > 0.92
        out[edge, :3] = _lerp(c_mid, c_out, 0.8)
        ring = np.abs(d - (0.25 + 0.6 * ((f / F) % 1))) < 0.09
        out[ring, :3] = out[ring, :3] * 0.6 + 255 * 0.4
        return out
    return paint


def A_flare(col, horizontal=True):
    """렌즈 광채: 가운데가 진하고 양 끝으로 갈수록 투명해지는 가는 빛줄기. 길이가 맥동."""
    def paint(f, w, h):
        X, Y = _grid(w, h)
        p = _pulse(f, 1)
        t = np.abs(X - (w - 1) / 2) / (w / 2) if horizontal else np.abs(Y - (h - 1) / 2) / (h / 2)
        a = np.clip(1 - t / (0.55 + 0.45 * p), 0, 1) ** 1.5
        out = _arr(w, h, col)
        out[..., :3] = _lerp(col, (255, 255, 255), a)
        out[..., 3] = (a * 235).astype(int)
        return out
    return paint


def helm_miner(H):
    H.mat("iron", S_metal(C("7a818e"), hi=C("e8edf4"), lo=C("2e323a"), seed=0))
    H.mat("iron_d", S_metal(C("4c515c"), hi=C("9aa2ae"), lo=C("1c1e24"), seed=2))
    H.mat("copper", S_metal(C("b4642e"), hi=C("ffc89a"), lo=C("5a2810"), seed=1, rivets=C("ffe0c0"), step=5))
    H.mat("patina", S_metal(C("4f9a84"), hi=C("a8e8d0"), lo=C("1e4a40"), seed=3), 8, 8)
    H.mat("leather", S_leather(C("4e3624"), seed=4), 8, 16)
    H.mat("lamp", A_lamp(C("c87a10"), C("ffd860"), C("ffffff")), 8, 8, anim=True)
    H.mat("amber", A_glow(C("a04a00"), C("ff9a20"), C("fff0b0"), speed=2, k=0.8, sparkle=0.0), 4, 4, anim=True)
    H.mat("gauge", A_glow(C("0a5a20"), C("40e060"), C("e0ffe0"), speed=1, k=1.0, sparkle=0.0, axis="x"), 8, 4,
          anim=True)
    H.mat("flare_h", A_flare((255, 236, 160), True), 32, 2, anim=True)
    H.mat("flare_v", A_flare((255, 236, 160), False), 2, 32, anim=True)
    H.mat("crystal", A_glow(C("1a7ab0"), C("50e0ff"), C("f0ffff"), speed=1, k=0.9, sparkle=0.15), 4, 8, anim=True)
    H.mat("picks", S_pixels(["W.....W.", "LW...WL.", ".eW.We..", "..eWe...", "..eWe...", ".e...e..",
                             "e.....e.", "........"], {"W": C("e4e9f0"), "L": C("a6adb9"), "e": C("8a5a30")}), 8, 8)

    # 안전모 돔 (3 단) + 구리 능선
    H.box((0.6, 14.4, 0.6), (15.4, 15.6, 15.4), "iron")
    H.box((1.6, 15.6, 1.6), (14.4, 16.8, 14.4), "iron")
    H.box((3.4, 16.8, 3.4), (12.6, 17.6, 12.6), "iron")
    H.box((6.8, 15.6, -0.4), (9.2, 18.4, 16.2), "copper")
    H.pair((3.0, 15.4, 3.0), (4.2, 17.2, 13.0), "copper")         # 옆 보강 띠
    # 옆판/뒤판, 챙 (둘레)
    H.pair((0.4, 9.6, 0.6), (1.6, 14.4, 15.4), "iron")
    H.box((1.6, 6.0, 14.4), (14.4, 14.4, 15.6), "iron")
    H.box((-0.6, 9.0, -2.6), (16.6, 9.8, 0.6), "iron_d")
    H.pair((-1.4, 9.0, 0.6), (0.4, 9.8, 16.6), "iron_d")
    H.box((0.4, 9.0, 15.6), (15.6, 9.8, 17.4), "iron_d")
    H.box((-0.8, 9.8, -2.8), (16.8, 10.2, -2.2), "copper")         # 챙 앞 구리 테
    # 이마 구리띠
    H.box((1.6, 9.8, 0.2), (14.4, 14.4, 1.6), "copper")
    # 앞 램프: 구리 하우징 + 철 베젤 + 빛나는 렌즈 + 십자 광채
    H.box((5.0, 10.4, -2.4), (11.0, 15.8, 0.2), "copper")
    H.box((4.4, 15.4, -3.2), (11.6, 16.4, -2.2), "iron_d")
    H.box((4.4, 9.8, -3.2), (11.6, 10.8, -2.2), "iron_d")
    H.pair((4.4, 10.8, -3.2), (5.4, 15.4, -2.2), "iron_d")
    H.box((5.4, 10.8, -2.8), (10.6, 15.4, -2.4), "lamp", light=15, whole="all")
    H.box((-2.0, 12.8, -3.4), (18.0, 13.4, -3.3), "flare_h", light=15, whole="all", shade=False)
    H.box((7.7, 3.0, -3.4), (8.3, 23.0, -3.3), "flare_v", light=15, whole="all", shade=False)
    # 옆 보조등 (호박색)
    H.pair((-0.4, 11.0, 5.4), (0.4, 13.6, 9.6), "iron_d")
    H.pair((-0.8, 11.4, 5.8), (-0.4, 13.2, 9.2), "amber", light=13, whole="all")
    # 뒤 배터리 팩 + 게이지 + 구리 단자, 능선을 따라 오는 전선
    H.box((3.6, 6.6, 15.6), (12.4, 12.6, 17.8), "iron_d")
    H.box((6.0, 8.0, 17.8), (10.0, 10.4, 18.0), "gauge", light=12, whole="all")
    H.pair((4.4, 12.6, 16.0), (5.8, 13.6, 17.4), "copper")
    H.box((3.6, 6.2, 15.4), (12.4, 6.8, 18.0), "patina")
    # 옆판의 교차 곡괭이 문양
    H.pair((0.1, 10.2, 9.8), (0.4, 14.2, 13.8), "picks", whole=("west",), skip=("east", "north", "south", "up", "down"))
    # 왼쪽 위에 박힌 빛나는 수정 다발 (광부의 전리품)
    H.box((1.0, 15.4, 9.4), (4.6, 16.4, 13.4), "iron_d")
    H.spike((2.4, 16.0, 11.0), 1.8, 6.5, "crystal", segs=3, light=12, axis="z", ang=22.5, origin=(2.4, 16.0, 11.0))
    H.spike((3.8, 16.2, 12.4), 1.3, 4.6, "crystal", segs=2, light=12, axis="x", ang=22.5, origin=(3.8, 16.2, 12.4))
    H.spike((1.6, 15.6, 9.8), 1.1, 3.8, "crystal", segs=2, light=12, axis="z", ang=45, origin=(1.6, 15.6, 9.8))
    return H


HELMETS["miner"] = helm_miner


# ─────────────────────────── 공용: 사슬 박스 / 고리 ───────────────────────────

def chain(H, base, segs, name_of, light_of=lambda i: 0, axis="z", side=-1):
    """
    휘어지는 뿔/가시: segs = [(길이, 굵기, 각도)], 각 마디는 앞 마디 끝에서 이어진다.
    axis='z' 면 XY 평면에서 휜다 (side=-1 → -X 쪽으로 휨), axis='x' 면 YZ 평면 (side=+1 → +Z 뒤로).
    """
    x, y, z = base
    for i, (L, w, ang) in enumerate(segs):
        a = math.radians(ang)
        if axis == "z":
            dx, dy = side * math.sin(a), math.cos(a)
            cx, cy, cz = x + dx * L / 2, y + dy * L / 2, z
            rot = ("z", -side * ang if ang else 0, (cx, cy, cz))
        else:
            dz, dy = side * math.sin(a), math.cos(a)
            cx, cy, cz = x, y + dy * L / 2, z + dz * L / 2
            rot = ("x", side * ang if ang else 0, (cx, cy, cz))
        frm = (cx - w / 2, cy - L / 2 - 0.15, cz - w / 2)
        to = (cx + w / 2, cy + L / 2 + 0.15, cz + w / 2)
        H.box(frm, to, name_of(i), light=light_of(i), rot=rot if ang else None, salt=i)
        if axis == "z":
            x, y = x + dx * L, y + dy * L
        else:
            z, y = z + dz * L, y + dy * L


def chain_pair(H, base, segs, name_of, light_of=lambda i: 0):
    """x=8 대칭으로 뿔 한 쌍. base 는 -X 쪽(플레이어 왼쪽) 기준."""
    chain(H, base, segs, name_of, light_of, side=-1)
    chain(H, (16 - base[0], base[1], base[2]), segs, name_of, light_of, side=+1)


def ring_xy(H, center, R, n, L, thick, depth, name, light=15, phase=0.0):
    """XY 평면(정면에서 보이는) 고리. 22.5° 배수 회전만 쓰므로 n=16 또는 8."""
    cx, cy, cz = center
    for k in range(n):
        th = 2 * math.pi * k / n + phase
        px, py = cx + R * math.cos(th), cy + R * math.sin(th)
        phi = (math.degrees(th) + 90) % 180          # 접선 방향 0..180
        if phi > 90:
            phi -= 180                               # -90..90
        if abs(phi) <= 45 + 1e-6:
            frm = (px - L / 2, py - thick / 2, cz - depth / 2)
            to = (px + L / 2, py + thick / 2, cz + depth / 2)
            ang = round(phi / 22.5) * 22.5
        else:
            frm = (px - thick / 2, py - L / 2, cz - depth / 2)
            to = (px + thick / 2, py + L / 2, cz + depth / 2)
            ang = round((phi - 90 if phi > 0 else phi + 90) / 22.5) * 22.5
        rot = ("z", ang, (px, py, cz)) if ang else None
        H.box(frm, to, name, light=light, rot=rot, shade=False, salt=k)


def drip(H, top, w, hgt, name, segs=3, light=0, taper=0.6):
    """아래로 늘어지는 고드름."""
    x, y, z = top
    cw = w
    sh = hgt / segs
    for i in range(segs):
        H.box((x - cw / 2, y - sh * 1.1, z - cw / 2), (x + cw / 2, y, z + cw / 2), name, light=light, salt=i)
        y -= sh
        cw *= taper


# ─────────────────────────── 3) 서리 frost ───────────────────────────
# 얼음 결정 판금 + 빛나는 눈꽃 룬, 털 깃, 남색 망토, 고드름 장식.
# 투구: 결정 투구 + 고드름 왕관(5개) + 이마의 빛나는 청록 보석 + 빛나는 서리 룬 띠 + 떠다니는 얼음 조각.

SPECS["frost"] = {
    "id": "frost",
    "notes": "얼음 결정 판금+눈꽃 룬+털 깃+남색 망토, 고드름 왕관 투구+발광 청록 보석+룬 띠+부유 얼음 조각",
    "pal": {
        "K": C("0e1c38"), "D": C("1f4a84"), "M": C("3a7ac0"), "L": C("72b6ea"), "W": C("c6eaff"),
        "w": C("ffffff"), "s": C("8ea4c4"), "S": C("dfe8f4"), "n": C("16224a"), "N": C("26407c"),
        "g": C("2ec8f8"), "G": C("b0f6ff"), "f": C("c4d4e4"), "F": C("f2f8ff"),
    },
    "amp": {"g": 0.0, "G": 0.0, "w": 0.0, "F": 0.02, "W": 0.03},
    "body": [
        "fFFf" + "fFfFFfFf" + "fFFf" + "fFfFFfFf",
        "FfSs" + "sSWLLWSs" + "sSfF" + "FfFffFfF",
        "DLMs" + "DLWMMWLD" + "sMLD" + "NnNNNNnN",
        "DMLs" + "DLgMMgLD" + "sLMD" + "nNNggNNn",
        "DMMs" + "DMMGGMMD" + "sMMD" + "NNgGGgNN",
        "DLMs" + "DggGGggD" + "sMLD" + "NgGwwGgN",
        "DMMs" + "DMMGGMMD" + "sMMD" + "NNgGGgNN",
        "DMLs" + "DLgMMgLD" + "sLMD" + "nNNggNNn",
        "sSSs" + "sSSwwSSs" + "sSSs" + "NnNNNNnN",
        "DLWD" + "DLMWWMLD" + "DWLD" + "SsSssSsS",
        "DMLD" + "WMLDDLMW" + "DLMD" + "WLWLLWLW",
        "KDDK" + "L.W..W.L" + "KDDK" + "L.W..W.L",
    ],
    "body_top": ["fFfFFfFf", "FfFffFfF", "fFfFFfFf", "fFFffFFf"],
    "arm": [
        "WwWW" + "WwWW" + "WWwW" + "WWwW",
        "LWLL" + "LWLL" + "LLWL" + "LLWL",
        "MLMM" + "gMLg" + "MMLM" + "MLMM",
        "DMDD" + "DgGD" + "DDMD" + "DMDD",
        "sSSs" + "sSSs" + "sSSs" + "sSSs",
        "nNNn" + "nNNn" + "nNNn" + "nNNn",
        "NnnN" + "NnnN" + "NnnN" + "NnnN",
        "nNNn" + "nNNn" + "nNNn" + "nNNn",
        "sSSs" + "sSSs" + "sSSs" + "sSSs",
        "LWLD" + "WLgL" + "DLWL" + "LMLD",
        "MLMD" + "LgGL" + "DMLM" + "MLMD",
        "W.WD" + "LWLW" + "DW.W" + "LWLW",
    ],
    "arm_top": ["WwWW", "wWWw", "WWwW", "WwWW"],
    "arm_bot": ["sSSs", "SssS", "SssS", "sSSs"],
    "boot": [
        "fFFf" + "fFFf" + "fFFf" + "fFFf",
        "FffF" + "FffF" + "FffF" + "FffF",
        "DLMD" + "LWWL" + "DMLD" + "DMMD",
        "DMLD" + "LgGL" + "DLMD" + "DLMD",
        "DMMD" + "MLLM" + "DMMD" + "DMMD",
        "sSSs" + "SwwS" + "sSSs" + "sSSs",
        "KKKK" + "KssK" + "KKKK" + "KKKK",
    ],
    "sole": ["KssK", "sKKs", "sKKs", "KssK"],
    "leg": [
        "nNNn" + "nNNn" + "nNNn" + "nNNn",
        "NNsN" + "NnNN" + "NsNN" + "NNnN",
        "nNsN" + "NNNn" + "NsNn" + "nNNN",
        "NNsN" + "DLLD" + "NsNN" + "NNnN",
        "nNsN" + "LWwL" + "NsNn" + "nNNN",
        "NNsN" + "MgGM" + "NsNN" + "NNnN",
        "nNsN" + "DLLD" + "NsNn" + "nNNN",
        "NNsN" + "NDDN" + "NsNN" + "NNnN",
        "nNNn" + "nNNn" + "nNNn" + "nNNn",
        "sSSs" + "sSSs" + "sSSs" + "sSSs",
    ],
    "leg_top": ["NNNN", "NnNN", "NNnN", "NNNN"],
    "waist": [
        "NNNN" + "NNNNNNNN" + "NNNN" + "NNNNNNNN",
        "nNNn" + "NnNNNNnN" + "nNNn" + "NnNNNNnN",
        "sSSs" + "sSSwwSSs" + "sSSs" + "sSSssSSs",
        "NNNN" + "NLWNNWLN" + "NNNN" + "NNNNNNNN",
        "nNNn" + "NLLnnLLN" + "nNNn" + "nNNnnNNn",
        "NnnN" + "NDDNNDDN" + "NnnN" + "NnnNNnnN",
    ],
    "icons": {
        "chestplate": [
            "................",
            ".KK..........KK.",
            ".KWK.KKKKKK.KWK.",
            ".KLWKfFfFfFKWLK.",
            ".KLLWFfFfFfWLLK.",
            ".KMLLWLLLLWLLMK.",
            ".KDMMLgMMgLMMDK.",
            "..KKMMMGGMMMKK..",
            "...KMggGGggMK...",
            "...KLMMGGMMLK...",
            "...KLLgMMgLLK...",
            "...KsSSwwSSsK...",
            "...KWLMWWMLWK...",
            "...KMLDKKDLMK...",
            "...KWK.KK.KWK...",
            "....K..KK..K....",
        ],
        "leggings": [
            "................",
            "..KKKKKKKKKKKK..",
            "..KsSSSwwSSSsK..",
            "..KNNnNNNNnNNK..",
            "..KNsNNKKNNsNK..",
            "..KNsNK..KNsNK..",
            "..KLWLK..KLWLK..",
            "..KgGgK..KgGgK..",
            "..KDLDK..KDLDK..",
            "..KNsNK..KNsNK..",
            "..KnsNK..KNsnK..",
            "..KsSsK..KsSsK..",
            "..KnNnK..KnNnK..",
            "..KKKKK..KKKKK..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "...KKKK..KKKK...",
            "...KFfK..KfFK...",
            "...KfFK..KFfK...",
            "...KWLK..KLWK...",
            "...KgGK..KGgK...",
            "...KMLK..KLMK...",
            "...KDMK..KMDK...",
            ".KKDMLK..KLMDKK.",
            ".KWLMMK..KMMLWK.",
            ".KsSSsK..KsSSsK.",
            ".KKKKKK..KKKKKK.",
            "................",
            "................",
        ],
    },
}


def helm_frost(H):
    H.mat("ice", S_ice(C("6aaee6"), C("e6f8ff"), C("2a6cb4"), seed=0))
    H.mat("ice_d", S_ice(C("3a7cc4"), C("a8dcff"), C("163e80"), seed=3))
    H.mat("ice_l", S_ice(C("b6e4ff"), C("ffffff"), C("5aa0e0"), seed=5), 8, 16)
    H.mat("silver", S_metal(C("a8b8cc"), hi=C("ffffff"), lo=C("4a5a74"), seed=1), 16, 8)
    H.mat("navy", S_cloth(C("22386e"), seed=2), 8, 8)
    H.mat("gem", A_gem(C("0a6cc0"), C("38d8ff"), C("e8ffff")), 8, 8, anim=True)
    H.mat("runes", A_overlay(C("20a8ff"), C("c8faff"), M_runes(seed=1), speed=1), 12, 4, anim=True)
    H.mat("runes2", A_overlay(C("20a8ff"), C("c8faff"), M_runes(seed=2), speed=1, seed=2), 12, 4, anim=True)
    H.mat("shard", A_glow(C("2a8ad8"), C("8ae6ff"), C("ffffff"), speed=1, k=0.9, sparkle=0.15), 4, 4, anim=True)

    # 결정 껍데기
    H.box((0.6, 14.4, 0.6), (15.4, 15.6, 15.4), "ice")
    H.box((2.0, 15.6, 2.0), (14.0, 16.4, 14.0), "ice_d")
    H.pair((0.4, 5.0, 0.6), (1.6, 14.4, 15.4), "ice")
    H.box((1.6, 3.0, 14.4), (14.4, 14.4, 15.6), "ice")
    H.box((1.6, 1.6, 15.6), (14.4, 4.0, 16.4), "silver")             # 목 가리개 테
    # 은 이마띠 + 빛나는 룬 덧칠 (앞/옆)
    H.box((1.2, 10.8, -0.2), (14.8, 14.4, 1.6), "silver")
    H.glow_skin((1.2, 10.8, -0.2), (14.8, 14.4, 1.6), "runes", skip=("up", "down", "south", "east", "west"),
                whole=("north",))
    H.pair((0.0, 10.8, 1.6), (0.4, 14.4, 15.0), "silver")
    H.glow_skin((0.0, 10.8, 1.6), (0.4, 14.4, 15.0), "runes2", skip=("up", "down", "north", "south", "east"),
                whole=("west",))
    H.glow_skin((15.6, 10.8, 1.6), (16.0, 14.4, 15.0), "runes2", skip=("up", "down", "north", "south", "west"),
                whole=("east",))
    # 볼 가리개 + 아래로 늘어진 고드름
    H.pair((0.6, 3.6, -0.8), (2.8, 10.8, 2.0), "ice_d")
    drip(H, (1.7, 3.8, 0.6), 1.8, 4.6, "ice_l")
    drip(H, (14.3, 3.8, 0.6), 1.8, 4.6, "ice_l")
    drip(H, (4.0, 3.2, 15.6), 1.6, 4.0, "ice_l")
    drip(H, (8.0, 3.2, 15.6), 2.0, 5.2, "ice_l")
    drip(H, (12.0, 3.2, 15.6), 1.6, 4.0, "ice_l")
    # 이마 보석: 은 받침 + 45도 돌린 마름모 보석
    H.box((5.6, 10.2, -1.0), (10.4, 15.0, 0.0), "silver")
    H.box((6.4, 11.0, -1.6), (9.6, 14.2, -0.8), "gem", light=15, whole="all",
          rot=("z", 45, (8.0, 12.6, -1.2)))
    # 고드름 왕관: 가운데 큰 것 + 양옆 두 쌍 (바깥으로 기울임) + 뒤쪽 하나
    H.spike((8.0, 15.0, 3.0), 3.4, 14.0, "ice", tip="ice_l", segs=4, taper=0.7)
    H.box((7.2, 26.0, 2.2), (8.8, 27.6, 3.8), "shard", light=15)       # 꼭대기 빛 조각
    for x, w, h, ang in ((4.4, 2.6, 10.0, 22.5), (1.8, 2.0, 7.0, 45)):
        H.spike((x, 14.6, 4.0), w, h, "ice", tip="ice_l", segs=3, axis="z", ang=ang, origin=(x, 14.6, 4.0))
        H.spike((16 - x, 14.6, 4.0), w, h, "ice", tip="ice_l", segs=3, axis="z", ang=-ang,
                origin=(16 - x, 14.6, 4.0))
    H.spike((8.0, 15.0, 11.0), 2.8, 9.0, "ice_d", tip="ice_l", segs=3, axis="x", ang=22.5,
            origin=(8.0, 15.0, 11.0))
    # 관자놀이 옆에 떠 있는 얼음 조각 (빛남)
    for sx in (-1, 1):
        x = 8 + sx * 11.2
        H.box((x - 1.0, 11.0, 5.4), (x + 1.0, 15.0, 7.4), "shard", light=14, rot=("y", 45, (x, 13.0, 6.4)))
        H.box((x - 0.5, 16.4, 8.6), (x + 0.5, 18.4, 9.6), "shard", light=14, rot=("y", 45, (x, 17.4, 9.1)))
    return H


HELMETS["frost"] = helm_frost


# ─────────────────────────── 4) 화염 flame ───────────────────────────
# 흑요석 판금 + 빛나는 마그마 균열, 녹아내린 심장(가슴), 검붉은 천.
# 투구: 닫힌 흑요석 투구 + 이글거리는 눈 틈 + 휘어 오른 뿔(끝이 불씨) + 불꽃 볏(애니메이션) + 마그마 균열 덧칠.

SPECS["flame"] = {
    "id": "flame",
    "notes": "흑요석 판금+마그마 균열+녹은 심장, 뿔 투구+발광 눈 틈+불꽃 볏+균열 발광",
    "pal": {
        "K": C("0a0610"), "D": C("1c1024"), "M": C("2c1c38"), "L": C("46305c"), "W": C("6e5090"),
        "o": C("7a1a04"), "O": C("d8480a"), "y": C("ff9a1c"), "Y": C("ffe070"),
        "r": C("3a0c08"), "R": C("6e1810"), "g": C("3e3846"), "G": C("6e6878"),
    },
    "amp": {"y": 0.0, "Y": 0.0, "O": 0.03, "o": 0.04},
    "body": [
        "KMLM" + "KMWLLWMK" + "MLMK" + "KMLMMLMK",
        "DLWL" + "DLOMMoLD" + "LWLD" + "DLWLLWLD",
        "DMoL" + "DMyOOyMD" + "LoMD" + "DMLyyLMD",
        "DOMM" + "DOyYYyOD" + "MMOD" + "DoMOOMoD",
        "DMyM" + "DMOYYOMD" + "MyMD" + "DMoyyoMD",
        "DMOM" + "DoMyyMoD" + "MOMD" + "DMMOOMMD",
        "DLMD" + "DLoMMoLD" + "DMLD" + "DLMooMLD",
        "DMMD" + "DMMOOMMD" + "DMMD" + "DMMyyMMD",
        "KoOo" + "KoOyyOoK" + "oOoK" + "KoOyyOoK",
        "RrRR" + "DLMRRMLD" + "RRrR" + "RrRRRRrR",
        "rRrR" + "DMORROMD" + "RrRr" + "rRrRRrRr",
        "KrKr" + "KDDrrDDK" + "rKrK" + "r.Rr.rR.",
    ],
    "body_top": ["KMLMMLMK", "MLWLLWLM", "MLWLLWLM", "KMLMMLMK"],
    "arm": [
        "LWWL" + "LWWL" + "LWWL" + "LWWL",
        "MLWM" + "MWLM" + "MLWM" + "MWLM",
        "DMOD" + "DyMD" + "DMoD" + "DOMD",
        "KoOK" + "KOoK" + "KoOK" + "KOoK",
        "gGGg" + "gGGg" + "gGGg" + "gGGg",
        "GgGg" + "gGgG" + "GgGg" + "gGgG",
        "gGgG" + "GgGg" + "gGgG" + "GgGg",
        "DLMD" + "DLLD" + "DMLD" + "DMMD",
        "DMMD" + "DOyD" + "DMMD" + "DLMD",
        "DLoD" + "DyYD" + "DoLD" + "DMMD",
        "DMMD" + "DOyD" + "DMMD" + "DMMD",
        "KKKK" + "KooK" + "KKKK" + "KKKK",
    ],
    "arm_top": ["LWWL", "WLLW", "WLOW", "LWWL"],
    "arm_bot": ["KooK", "oKKo", "oKKo", "KooK"],
    "boot": [
        "LWWL" + "LWWL" + "LWWL" + "LWWL",
        "DMoD" + "MyOM" + "DoMD" + "DMMD",
        "DOMD" + "OYyO" + "DMOD" + "DoMD",
        "DMMD" + "MyOM" + "DMMD" + "DMMD",
        "DLMD" + "LWWL" + "DMLD" + "DMMD",
        "KoOK" + "OyyO" + "KOoK" + "KooK",
        "KKKK" + "KKKK" + "KKKK" + "KKKK",
    ],
    "sole": ["KooK", "oKKo", "oKKo", "KooK"],
    "leg": [
        "RrRR" + "RRrR" + "RrRR" + "RRrR",
        "rRRr" + "rRRr" + "rRRr" + "rRRr",
        "DLMD" + "DLWD" + "DMLD" + "DMMD",
        "DMMD" + "DLMD" + "DMMD" + "DMLD",
        "DLoD" + "LOOL" + "DoLD" + "DMMD",
        "DMMD" + "OYyO" + "DMMD" + "DLMD",
        "DMLD" + "LOOL" + "DLMD" + "DMMD",
        "DoMD" + "DoMD" + "DMoD" + "DMMD",
        "DMMD" + "DMMD" + "DMMD" + "DMMD",
        "KDDK" + "KDDK" + "KDDK" + "KDDK",
    ],
    "leg_top": ["RRRR", "RrRR", "RRrR", "RRRR"],
    "waist": [
        "RRRR" + "RRRRRRRR" + "RRRR" + "RRRRRRRR",
        "rRRr" + "RrRRRRrR" + "rRRr" + "RrRRRRrR",
        "KoOo" + "KoOyyOoK" + "oOoK" + "KoOooOoK",
        "DLMD" + "DLMDDMLD" + "DMLD" + "DLMDDMLD",
        "DMOD" + "DMODDOMD" + "DOMD" + "DMoDDoMD",
        "KDDK" + "KDDKKDDK" + "KDDK" + "KDDKKDDK",
    ],
    "icons": {
        "chestplate": [
            "................",
            ".KK..........KK.",
            ".KWK.KK..KK.KWK.",
            ".KLWKLMKKMLKWLK.",
            ".KMLWLWLLWLWLMK.",
            ".KDMLLOMMoLLMDK.",
            ".KDMMOyOOyOMMDK.",
            "..KKMyOYYOyMKK..",
            "...KDOYYYYODK...",
            "...KMoyYYyoMK...",
            "...KLMoyyoMLK...",
            "...KoOyyyyOoK...",
            "...KLMRrrRMLK...",
            "...KDMRrrRMDK...",
            "...KKKKRRKKKK...",
            ".......KK.......",
        ],
        "leggings": [
            "................",
            "..KKKKKKKKKKKK..",
            "..KoOOyyyyOOoK..",
            "..KRrRRRRRRrRK..",
            "..KDLMDKKDMLDK..",
            "..KDOMK..KMODK..",
            "..KLyLK..KLyLK..",
            "..KWYWK..KWYWK..",
            "..KLyLK..KLyLK..",
            "..KDOMK..KMODK..",
            "..KDMoK..KoMDK..",
            "..KMLMK..KMLMK..",
            "..KDDDK..KDDDK..",
            "..KKKKK..KKKKK..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "...KKKK..KKKK...",
            "..KLWWK..KWWLK..",
            "...KMoK..KoMK...",
            "...KOyK..KyOK...",
            "...KyYK..KYyK...",
            "...KOyK..KyOK...",
            "...KDMK..KMDK...",
            ".KKDMLK..KLMDKK.",
            "KWLMMOK..KOMMLWK",
            ".KoOyOK..KOyOoK.",
            ".KKKKKK..KKKKKK.",
            "................",
            "................",
        ],
    },
}


def helm_flame(H):
    H.mat("obs", S_obsidian(0))
    H.mat("obs2", S_obsidian(3))
    H.mat("horn", S_metal(C("2a1a22"), hi=C("6a4a5a"), lo=C("0a0408"), seed=4, step=4), 8, 16)
    H.mat("steel", S_metal(C("3c3644"), hi=C("8a8296"), lo=C("120e16"), seed=2), 16, 8)
    H.mat("cracks", A_overlay(C("c02a00"), C("ffb030"), M_cracks(seed=1, density=4), speed=1), 16, 16, anim=True)
    H.mat("cracks2", A_overlay(C("c02a00"), C("ffb030"), M_cracks(seed=7, density=3), speed=1, seed=1.5),
          16, 16, anim=True)
    H.mat("slit", A_glow(C("ff5a00"), C("ffc040"), C("fffbe0"), speed=2, k=1.2, sparkle=0.2, axis="x"), 16, 4,
          anim=True)
    H.mat("ember", A_glow(C("b02800"), C("ff8a10"), C("fff0a0"), speed=1, k=0.6, sparkle=0.1), 8, 8, anim=True)
    H.mat("fire", A_fire(seed=0), 8, 16, anim=True)
    H.mat("fire2", A_fire(seed=2.3), 8, 16, anim=True)

    # 닫힌 흑요석 투구 (위 2 단 + 옆/뒤)
    H.box((0.4, 14.4, 0.4), (15.6, 15.8, 15.6), "obs")
    H.box((1.8, 15.8, 1.8), (14.2, 16.8, 14.2), "obs2")
    H.pair((0.2, 1.0, 0.4), (1.6, 14.4, 15.6), "obs")
    H.box((1.6, 1.0, 14.4), (14.4, 14.4, 15.8), "obs")
    H.glow_skin((0.4, 14.4, 0.4), (15.6, 15.8, 15.6), "cracks", skip=("down",))
    H.glow_skin((0.2, 1.0, 0.4), (1.6, 14.4, 15.6), "cracks2", skip=("east", "up", "down", "north", "south"))
    H.glow_skin((14.4, 1.0, 0.4), (15.8, 14.4, 15.6), "cracks", skip=("west", "up", "down", "north", "south"))
    H.glow_skin((1.6, 1.0, 14.4), (14.4, 14.4, 15.8), "cracks2", skip=("north", "up", "down", "east", "west"))
    # 얼굴 가리개: 윗판 / 이글거리는 눈 틈 / 아래판(숨구멍)
    H.box((1.0, 8.6, -1.0), (15.0, 14.4, 1.6), "obs2")
    H.box((1.8, 7.0, -0.4), (14.2, 8.6, 0.6), "slit", light=15, whole=("north",))
    H.box((1.0, 0.6, -1.0), (15.0, 7.0, 1.6), "obs")
    H.glow_skin((1.0, 0.6, -1.0), (15.0, 7.0, 1.6), "cracks", skip=("south", "up", "down", "east", "west"))
    # 성난 눈썹 (V 자) + 가운데 콧날 + 턱 가시
    H.pair((1.4, 8.6, -1.8), (8.4, 10.0, -0.6), "steel", rot=("z", -22.5, (8.0, 9.3, -1.2)))
    H.box((7.2, 1.0, -2.0), (8.8, 11.0, -0.8), "steel")
    H.box((6.8, -1.4, -1.6), (9.2, 1.2, 0.4), "steel")
    H.box((7.4, -3.2, -1.2), (8.6, -1.2, 0.0), "steel")
    # 휘어 오르는 뿔 (밖 → 위 → 안쪽으로 말림), 끝 두 마디는 불씨처럼 빛남
    for sx in (-1, 1):
        x0 = 0.4 if sx < 0 else 15.6
        xa, xb = (x0 - 3.2, x0) if sx < 0 else (x0, x0 + 3.2)
        H.box((xa, 10.6, 5.8), (xb, 14.0, 9.8), "horn", salt=sx)
    chain_pair(H, (-2.4, 13.2, 7.8),
               [(4.2, 3.0, 45), (4.2, 2.6, 22.5), (4.0, 2.1, 0), (3.6, 1.6, -22.5), (3.0, 1.1, -45)],
               lambda i: "horn" if i < 3 else "ember", lambda i: 0 if i < 3 else 15)
    # 불꽃 볏: 흑요석 능선 위로 높이가 다른 불꽃 지느러미 5장 (투명 가장자리, 빛남)
    H.box((7.0, 16.8, 1.0), (9.0, 17.8, 15.0), "steel")
    for i, (z0, z1, hh) in enumerate(((0.6, 4.2, 6.0), (3.4, 7.4, 9.5), (6.6, 10.6, 11.0), (9.8, 13.6, 8.5),
                                     (12.8, 16.0, 5.5))):
        H.box((7.4, 17.4, z0), (8.6, 17.4 + hh, z1), "fire" if i % 2 == 0 else "fire2", light=15,
              whole=("east", "west"), skip=("up", "down", "north", "south"), shade=False)
        H.box((7.6, 17.4, z0 + 0.6), (8.4, 17.4 + hh * 0.55, z1 - 0.6), "ember", light=15, salt=i)
    return H


HELMETS["flame"] = helm_flame


# ─────────────────────────── 5) 공허 void ───────────────────────────
# 짙은 보라 로브 + 판금, 빛나는 자홍 룬과 '눈' 문양.
# 투구: 두건형 투구(얼굴 아래 가리개) + 이마 왕관판 + 뒤에 떠 있는 자홍 룬 고리(16 마디) + 부유 수정.

SPECS["void"] = {
    "id": "void",
    "notes": "짙은 보라 로브+판금+자홍 룬/눈 문양, 두건 투구+부유 룬 후광(발광 16마디)+부유 수정",
    "pal": {
        "K": C("08040e"), "D": C("1c0f30"), "M": C("32205a"), "L": C("523688"), "W": C("7c5cb8"),
        "n": C("140a20"), "N": C("26163e"), "e": C("3c2660"), "g": C("8a1878"), "G": C("f038d0"),
        "Y": C("ffb8f4"), "s": C("8a84a8"), "S": C("d4ccec"),
    },
    "amp": {"g": 0.0, "G": 0.0, "Y": 0.0, "S": 0.02},
    "body": [
        "NeSS" + "SSNeeNSS" + "SSeN" + "SSNeeNSS",
        "nNsN" + "sMLWWLMs" + "NsNn" + "NnNeeNnN",
        "NnsN" + "sLgMMgLs" + "NsnN" + "nNeNNeNn",
        "nNsN" + "sMMGGMMs" + "NsNn" + "NNgNNgNN",
        "NnsN" + "sgMYYMgs" + "NsnN" + "NgNGGNgN",
        "nNsN" + "sMMGGMMs" + "NsNn" + "gNGYYGNg",
        "NnsN" + "sLgMMgLs" + "NsnN" + "NgNGGNgN",
        "nNsN" + "sDMLLMDs" + "NsNn" + "NNgNNgNN",
        "KSGS" + "KSSGGSSK" + "SGSK" + "KSSGGSSK",
        "NnNe" + "nNeGGeNn" + "eNnN" + "NnNeeNnN",
        "nNeN" + "NnNgGNnN" + "NeNn" + "nNnNNnNn",
        "NnNn" + "nNnggNnN" + "nNnN" + "N.nN.nN.",
    ],
    "body_top": ["SSNeeNSS", "SNeNNeNS", "SNeNNeNS", "SSNeeNSS"],
    "arm": [
        "LWWL" + "LWWL" + "LWWL" + "LWWL",
        "MLLM" + "MLLM" + "MLLM" + "MLLM",
        "DgMD" + "DMgD" + "DgMD" + "DMgD",
        "KSSK" + "KSSK" + "KSSK" + "KSSK",
        "NnNe" + "NenN" + "eNnN" + "NneN",
        "nNeN" + "NeNn" + "NeNn" + "nNeN",
        "NnNN" + "NNnN" + "NnNN" + "NNnN",
        "nNNn" + "nNNn" + "nNNn" + "nNNn",
        "SssS" + "SssS" + "SssS" + "SssS",
        "DMLD" + "MgGM" + "DLMD" + "DMMD",
        "DLMD" + "MGYM" + "DMLD" + "DLMD",
        "KSSK" + "KSSK" + "KSSK" + "KSSK",
    ],
    "arm_top": ["LWWL", "WLLW", "WLLW", "LWWL"],
    "arm_bot": ["KSSK", "SKKS", "SKKS", "KSSK"],
    "boot": [
        "SssS" + "SssS" + "SssS" + "SssS",
        "DMLD" + "MLWM" + "DLMD" + "DMMD",
        "DMMD" + "MgGM" + "DMMD" + "DMMD",
        "DLMD" + "MGYM" + "DMLD" + "DLMD",
        "DMMD" + "MgGM" + "DMMD" + "DMMD",
        "DMLD" + "LWWL" + "DLMD" + "DMMD",
        "KKKK" + "KSSK" + "KKKK" + "KKKK",
    ],
    "sole": ["KSSK", "SKKS", "SKKS", "KSSK"],
    "leg": [
        "NnNN" + "NNnN" + "NnNN" + "NNnN",
        "nNeN" + "NeNn" + "NeNn" + "nNeN",
        "NNgN" + "DLLD" + "NgNN" + "NNnN",
        "NnGN" + "LWWL" + "NGnN" + "nNNN",
        "NNgN" + "MgGM" + "NgNN" + "NNnN",
        "NnNN" + "DLLD" + "NNnN" + "nNNN",
        "nNNn" + "NDDN" + "nNNn" + "NNnN",
        "NnNe" + "NenN" + "eNnN" + "NneN",
        "nNNn" + "nNNn" + "nNNn" + "nNNn",
        "SssS" + "SssS" + "SssS" + "SssS",
    ],
    "leg_top": ["NNNN", "NnNN", "NNnN", "NNNN"],
    "waist": [
        "NNNN" + "NNNeeNNN" + "NNNN" + "NNNNNNNN",
        "nNNn" + "NnNNNNnN" + "nNNn" + "NnNNNNnN",
        "KSGS" + "KSSGGSSK" + "SGSK" + "KSSssSSK",
        "NNeN" + "NeNggNeN" + "NeNN" + "NeNNNNeN",
        "nNNn" + "NnNGGNnN" + "nNNn" + "NnNNNNnN",
        "NnnN" + "nNNggNNn" + "NnnN" + "nNNnnNNn",
    ],
    "icons": {
        "chestplate": [
            "................",
            "..KKKK....KKKK..",
            ".KLWWLKKKKLWWLK.",
            ".KMLgLSSSSLgLMK.",
            ".KDMMKsNNsKMMDK.",
            ".KKDMsLgGLsMDKK.",
            "..KKKsGYYGsKKK..",
            "...KNsLgGLsNK...",
            "...KnsMMMMsnK...",
            "...KSSSGGSSSK...",
            "...KNeNGGNeNK...",
            "...KnNegGeNnK...",
            "...KNnNggNnNK...",
            "...KnNKggKNnK...",
            "...KKK.KK.KKK...",
            "................",
        ],
        "leggings": [
            "................",
            "..KKKKKKKKKKKK..",
            "..KSSSSGGSSSSK..",
            "..KNeNNggNNeNK..",
            "..KNgNNKKNNgNK..",
            "..KNGNK..KNGNK..",
            "..KLWLK..KLWLK..",
            "..KgGgK..KgGgK..",
            "..KDLDK..KDLDK..",
            "..KNeNK..KNeNK..",
            "..KnNNK..KNNnK..",
            "..KNeNK..KNeNK..",
            "..KsSsK..KsSsK..",
            "..KKKKK..KKKKK..",
            "................",
            "................",
        ],
        "boots": [
            "................",
            "................",
            "................",
            "...KKKK..KKKK...",
            "...KSSK..KSSK...",
            "...KLWK..KWLK...",
            "...KgGK..KGgK...",
            "...KGYK..KYGK...",
            "...KgGK..KGgK...",
            "...KDMK..KMDK...",
            ".KKDMLK..KLMDKK.",
            ".KWLMMK..KMMLWK.",
            ".KsSSsK..KsSSsK.",
            ".KKKKKK..KKKKKK.",
            "................",
            "................",
        ],
    },
}


def A_abyss(seed=0):
    """공허 안감: 거의 검은 보라 바탕에 별이 깜빡이며 천천히 흐른다."""
    def paint(f, w, h):
        X, Y = _grid(w, h)
        out = _arr(w, h, (14, 6, 26))
        v = 0.5 + 0.5 * np.sin(X * 0.7 + Y * 0.5 + 2 * math.pi * f / F)
        out[..., :3] = _lerp((10, 4, 20), (48, 14, 70), v * 0.8)
        r = _rng("abyss", seed, w, h)
        n = max(3, w * h // 14)
        sx, sy = r.integers(0, w, n), r.integers(0, h, n)
        ph = r.integers(0, F, n)
        for i in range(n):
            b = 0.5 + 0.5 * math.cos(2 * math.pi * (f - ph[i]) / F)
            out[sy[i], (sx[i] + f // 4) % w, :3] = _lerp((90, 30, 120), (255, 200, 255), b)
        return out
    return paint


def helm_void(H):
    H.mat("cloth", S_cloth(C("3a2262"), seed=0))
    H.mat("cloth_d", S_cloth(C("24143e"), seed=1))
    H.mat("plate", S_metal(C("4c3478"), hi=C("b49ae8"), lo=C("140a24"), seed=2))
    H.mat("pale", S_metal(C("a49cc4"), hi=C("f4f0ff"), lo=C("4a4466"), seed=1), 16, 8)
    H.mat("abyss", A_abyss(0), 16, 16, anim=True)
    H.mat("runes", A_overlay(C("a0108c"), C("ffb4f4"), M_runes(seed=4), speed=1), 12, 4, anim=True)
    H.mat("halo", A_glow(C("8a0c78"), C("f040d4"), C("fff0ff"), speed=1, k=0.35, sparkle=0.12, axis="x"), 16, 4,
          anim=True)
    H.mat("halo2", A_glow(C("4a0a6a"), C("a040f0"), C("f0d0ff"), speed=2, k=0.6, sparkle=0.1, axis="x"), 16, 4,
          anim=True)
    H.mat("gem", A_gem(C("5a0858"), C("e030c8"), C("ffe0ff")), 8, 8, anim=True)
    H.mat("tip", A_glow(C("a01090"), C("ff50e0"), C("fff0ff"), speed=1, k=0.8, sparkle=0.0), 4, 8, anim=True)

    # 두건: 위 2 단 + 뒤로 처진 끝 + 어깨까지 내려오는 옆/뒤
    H.box((0.2, 14.4, 0.0), (15.8, 16.0, 16.0), "cloth")
    H.box((1.4, 16.0, 1.6), (14.6, 17.4, 15.0), "cloth")
    H.box((3.4, 17.4, 4.0), (12.6, 18.4, 14.0), "cloth_d")
    H.box((4.6, 15.0, 13.0), (11.4, 18.4, 18.6), "cloth_d", rot=("x", -22.5, (8.0, 16.6, 15.8)))
    H.pair((-0.2, -0.6, 0.0), (1.6, 14.4, 16.0), "cloth")
    H.box((1.6, -1.6, 14.4), (14.4, 14.4, 16.4), "cloth")
    # 얼굴 테두리: 앞으로 튀어나온 두건 가장자리 (안쪽은 별빛 공허)
    H.box((-0.4, 14.0, -2.6), (16.4, 16.4, 0.0), "cloth_d", skip=("down",))
    H.box((0.0, 13.4, -2.4), (16.0, 14.0, 0.0), "abyss", light=6, whole=("down",), skip=("up",))
    H.pair((-0.6, -0.6, -2.2), (1.4, 14.0, 0.0), "cloth_d", skip=("east",))
    H.pair((1.4, -0.6, -2.0), (1.8, 13.4, 0.0), "abyss", light=6, whole=("east",), skip=("west",))
    # 두건 주름 (옆/뒤로 늘어진 천 골)
    for z0, y0 in ((4.0, -0.2), (9.0, 0.6)):
        H.pair((-0.7, y0, z0), (-0.2, 13.6, z0 + 1.4), "cloth_d")
    for x0 in (4.0, 10.6):
        H.box((x0, -1.2, 16.4), (x0 + 1.4, 13.0, 16.9), "cloth_d")
    # 아래 얼굴 가리개 (판금) + 룬 덧칠
    H.box((1.6, 0.4, -1.2), (14.4, 6.0, 1.0), "plate")
    H.glow_skin((1.6, 1.2, -1.2), (14.4, 5.2, 1.0), "runes", skip=("south", "up", "down", "east", "west"),
                whole=("north",))
    # 가시 왕관: 은빛 띠 + 다섯 가시(끝이 자홍빛) + 가운데 마름모 보석
    H.box((0.6, 16.0, -2.8), (15.4, 17.2, -0.6), "pale")
    H.spike((8.0, 16.6, -1.7), 3.4, 12.0, "plate", tip="tip", segs=4, tip_light=15, taper=0.7)
    for x, w, hgt, ang in ((5.0, 2.6, 8.5, 22.5), (2.0, 2.2, 6.5, 45)):
        H.spike((x, 16.6, -1.7), w, hgt, "plate", tip="tip", segs=3, tip_light=15, axis="z", ang=ang,
                origin=(x, 16.6, -1.7))
        H.spike((16 - x, 16.6, -1.7), w, hgt, "plate", tip="tip", segs=3, tip_light=15, axis="z", ang=-ang,
                origin=(16 - x, 16.6, -1.7))
    H.box((6.5, 12.6, -3.4), (9.5, 15.6, -2.8), "gem", light=15, whole="all", rot=("z", 45, (8.0, 14.1, -3.1)))
    # 뒤에 떠 있는 룬 후광: 큰 고리 16 마디 + 안쪽 작은 고리 8 마디 + 네 방향 수정
    ring_xy(H, (8.0, 15.0, 19.6), 10.2, 16, 4.4, 1.2, 0.8, "halo")
    ring_xy(H, (8.0, 15.0, 19.2), 6.6, 8, 5.2, 0.7, 0.6, "halo2", phase=math.pi / 8)
    for k in range(4):
        th = math.pi / 2 * k + math.pi / 4
        px, py = 8 + 10.2 * math.cos(th), 15 + 10.2 * math.sin(th)
        H.box((px - 1.3, py - 1.3, 19.0), (px + 1.3, py + 1.3, 20.2), "gem", light=15, whole="all",
              rot=("z", 45, (px, py, 19.6)))
    # 양옆에 떠 있는 수정 조각
    for sx in (-1, 1):
        x = 8 + sx * 11.0
        H.box((x - 0.9, 6.0, 6.6), (x + 0.9, 10.4, 8.4), "gem", light=14, rot=("y", 45, (x, 8.2, 7.5)))
    return H


HELMETS["void"] = helm_void

# @@SETS@@


# ═══════════════════════════════ 빌드 ═══════════════════════════════

def build(assets_root):
    tex = os.path.join(assets_root, "textures")
    out = {"sets": {}}
    for sid in [x for x in SETS if x in SPECS]:
        spec = SPECS[sid]
        hum = paint_humanoid(spec)
        leg = paint_leggings(spec)
        for sub, img in (("humanoid", hum), ("humanoid_leggings", leg)):
            p = os.path.join(tex, "entity", "equipment", sub, sid + ".png")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            img.save(p)
        for kind in ("chestplate", "leggings", "boots"):
            p = os.path.join(tex, "item", "armor", f"{sid}_{kind}.png")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            paint_icon(spec["icons"][kind], spec).save(p)
        helm = HELMETS[sid](Helm(sid))
        ref = helm.finish(assets_root, getattr(helm, "display", None))
        out["sets"][sid] = {"helmet_model": ref, "notes": spec["notes"] + f" (투구 element {helm.n}개)"}
    return out


# ═══════════════════════════════ 미리보기 ═══════════════════════════════

def _label(img, text, size=18):
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, size)
    d.text((8, 6), text, font=f, fill=(235, 235, 245))
    return img


def _enlarge(img, k, bg=(48, 46, 58)):
    big = img.resize((img.width * k, img.height * k), Image.NEAREST)
    canvas = Image.new("RGBA", big.size, bg + (255,))
    # 체커보드로 투명 영역 표시
    d = ImageDraw.Draw(canvas)
    for y in range(0, big.height, k):
        for x in range(0, big.width, k):
            if (x // k + y // k) % 2:
                d.rectangle((x, y, x + k - 1, y + k - 1), fill=(56, 54, 68, 255))
    canvas.alpha_composite(big)
    return canvas.convert("RGB")


def display_matrix(d):
    """아이템 display 변환 (translation/16 + Rx Ry Rz + scale) → 미리보기 4x4 행렬."""
    rx, ry, rz = d["rotation"]
    R = _rot_matrix("x", rx) @ _rot_matrix("y", ry) @ _rot_matrix("z", rz)
    M = np.eye(4)
    M[:3, :3] = R @ np.diag(d["scale"])
    M[:3, 3] = np.array(d["translation"]) / 16.0
    return M


def slot_preview(helm, size=300, frame=3):
    """인벤토리 한 칸(16px) 안에 gui 변환으로 그린 모습. 회색 칸 = 실제 슬롯 크기."""
    disp = helm.fit_display()
    img = zrender([(helm.m, display_matrix(disp["gui"]))], size, yaw=0, pitch=0, frame=frame,
                  bg=(139, 139, 139), fit=(0.0, 0.0, 1.0), pad=0.12)
    d = ImageDraw.Draw(img)
    k = size * (1 - 2 * 0.12)
    o = (size - k) / 2
    d.rectangle((o, o, o + k, o + k), outline=(60, 60, 60), width=2)
    return img


def preview_set(sid, assets_root):
    spec = SPECS[sid]
    hum = paint_humanoid(spec)
    leg = paint_leggings(spec)
    helm = HELMETS[sid](Helm(sid))
    m = helm.m
    T = 300
    tiles = []
    tiles.append(_label(zrender([(m, None)], T, yaw=200, pitch=18, frame=0), "투구 앞"))
    tiles.append(_label(zrender([(m, None)], T, yaw=35, pitch=22, frame=5), "투구 뒤"))
    tiles.append(_label(zrender([(m, None)], T, yaw=-150, pitch=30, frame=10, night=True), "투구 밤"))
    # 인벤토리 GUI 각도 근사 (rotation [25,145,0])
    tiles.append(_label(slot_preview(helm, T), "인벤토리 칸 (gui 변환)"))
    parts = mannequin(hum, leg, m)
    fitc = None
    tiles.append(_label(zrender(parts, T, yaw=180 + 20, pitch=8, frame=0, fit=fitc), "착용 앞"))
    tiles.append(_label(zrender(parts, T, yaw=20, pitch=8, frame=6), "착용 뒤"))
    tiles.append(_label(zrender(parts, T, yaw=180 + 75, pitch=5, frame=9), "착용 옆"))
    tiles.append(_label(zrender(parts, T, yaw=180 - 20, pitch=8, frame=12, night=True), "착용 밤"))
    row1 = Image.new("RGB", (T * 4, T * 2), (18, 16, 26))
    for i, t in enumerate(tiles):
        row1.paste(t, ((i % 4) * T, (i // 4) * T))
    # 아이콘(8x) + humanoid(6x) + humanoid_leggings(6x)
    icons = [paint_icon(spec["icons"][k], spec) for k in ("chestplate", "leggings", "boots")]
    strip = Image.new("RGB", (T * 4, 260), (18, 16, 26))
    for i, ic in enumerate(icons):
        strip.paste(_enlarge(ic, 8), (8 + i * 134, 34))
    small = Image.new("RGBA", (16 * 3 + 16, 20), (139, 139, 139, 255))  # 실제 크기 (인벤토리 회색 칸)
    for i, ic in enumerate(icons):
        small.alpha_composite(ic, (4 + i * 20, 2))
    strip.paste(small.resize((small.width * 2, small.height * 2), Image.NEAREST).convert("RGB"), (8, 172))
    strip.paste(_enlarge(hum, 6).crop((0, 16 * 6 - 2, 384, 192)), (412, 34))
    strip.paste(_enlarge(leg, 6).crop((0, 16 * 6 - 2, 240, 192)), (412 + 384 + 12, 34))
    _label(strip, f"{NAMES_KO[sid]} ({sid}) — 아이콘 / humanoid (y16~32) / humanoid_leggings (y16~32)", 16)
    sheet = Image.new("RGB", (T * 4, T * 2 + 160), (18, 16, 26))
    sheet.paste(row1, (0, 0))
    sheet.paste(strip.crop((0, 0, T * 4, 160)), (0, T * 2))
    return sheet


def make_previews(assets_root):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    paths = []
    sheets = []
    for sid in SETS:
        sh = preview_set(sid, assets_root)
        p = os.path.join(PREVIEW_DIR, f"{MODULE}_{sid}.png")
        sh.save(p)
        paths.append(p)
        sheets.append(sh)
    # 전체 요약: 세트별 착용 앞모습 + 투구
    T = 260
    over = Image.new("RGB", (T * len(SETS), T * 2 + 30), (18, 16, 26))
    d = ImageDraw.Draw(over)
    f = ImageFont.truetype(FONT, 18)
    for i, sid in enumerate(SETS):
        spec = SPECS[sid]
        helm = HELMETS[sid](Helm(sid))
        parts = mannequin(paint_humanoid(spec), paint_leggings(spec), helm.m)
        over.paste(zrender([(helm.m, None)], T, yaw=200, pitch=18, frame=i * 3), (i * T, 0))
        over.paste(zrender(parts, T, yaw=200, pitch=8, frame=i * 3), (i * T, T))
        d.text((i * T + 8, T * 2 + 4), f"{NAMES_KO[sid]} ({sid})", font=f, fill=(235, 235, 245))
    p = os.path.join(PREVIEW_DIR, f"{MODULE}.png")
    over.save(p)
    return [p] + paths


def make_gif(sid, path):
    helm = HELMETS[sid](Helm(sid))
    frames = [zrender([(helm.m, None)], 220, yaw=200 + i * 360 / F / 2, pitch=18, frame=i, ss=1) for i in range(F)]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)


if __name__ == "__main__":
    import json
    res = build(SCRATCH)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    only = sys.argv[1:] or None
    if only:
        for sid in only:
            p = os.path.join(PREVIEW_DIR, f"{MODULE}_{sid}.png")
            preview_set(sid, SCRATCH).save(p)
            print(p)
    else:
        for p in make_previews(SCRATCH):
            print(p)
