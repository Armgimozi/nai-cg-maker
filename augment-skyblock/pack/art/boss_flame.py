"""
화염 거신 (Inferno Colossus) 보스 리그 아트.

떠다니는 용암 바위 거인:
  - torso : 갈라진 현무암/흑요석 가슴, 가운데 맥동하는 마그마 코어, 거대한 바위 어깨(용암 이음매 + 가시 + 불꽃),
            등의 화산 굴뚝 2개에서 솟는 불꽃
  - head  : 휘어진 뿔(끝이 달아오름), 화난 V 눈썹 밑의 타오르는 눈, 용암이 새는 입, 불꽃 왕관
  - fists : 몸에서 떨어져 떠다니는 두 주먹(손가락 사이로 빛나는 균열, 흑요석 너클 스파이크, 용암 손목 고리)
  - tail  : 다리 대신 아래로 흩어지는 바위 조각 꼬리(용암 실로 이어짐)
  - rocks : 주위를 도는 불타는 바위 4개
  - halo  : 등 뒤에서 천천히 도는 용암 가시 고리

구조 원칙: 안쪽에 빛나는(light 15) 용암 몸통을 두고, 그 위를 틈이 있는 바위 판으로 덮는다
→ 틈으로 용암 이음매가 보인다. 바위는 정적 아틀라스, 용암/불꽃은 애니메이션 아틀라스.
"""
import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from mc3d import Atlas, Model, contact_sheet, mat, render  # noqa: E402

BOSS = "inferno_colossus"
MODULE = "boss_flame"
PREVIEW = os.path.join(HERE, "preview")
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
NF = 16  # 용암 애니메이션 프레임 수
FACES = ("north", "south", "east", "west", "up", "down")


# ─────────────────────────────── 색/노이즈 도구 ───────────────────────────────

def _hx(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


# 용암 팔레트: 식은 껍질 → 붉은 → 주황 → 노랑 → 백열
LAVA_STOPS = [(0.00, "#1c0300"), (0.18, "#5a0a00"), (0.36, "#b01e00"), (0.52, "#f04800"),
              (0.66, "#ff8410"), (0.80, "#ffc23a"), (0.92, "#ffeb8a"), (1.00, "#fffbe6")]


def palette(v, stops=LAVA_STOPS):
    """0..1 배열 → RGB 배열"""
    xs = [s[0] for s in stops]
    cols = np.array([_hx(s[1]) for s in stops], dtype=float)
    v = np.clip(v, 0, 1)
    return np.stack([np.interp(v, xs, cols[:, i]) for i in range(3)], axis=-1)


def value_noise(w, h, cell, rng):
    gw, gh = w // cell + 2, h // cell + 2
    g = rng.random((gh, gw))
    ys, xs = np.mgrid[0:h, 0:w] / cell
    x0, y0 = xs.astype(int), ys.astype(int)
    fx, fy = xs - x0, ys - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = g[y0, x0] * (1 - fx) + g[y0, x0 + 1] * fx
    b = g[y0 + 1, x0] * (1 - fx) + g[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def fbm(w, h, rng, octs=((8, .5), (4, .3), (2, .2))):
    return sum(value_noise(w, h, c, rng) * a for c, a in octs)


def voronoi(w, h, n, rng):
    """(d2-d1) 가 작은 곳이 균열. 가장자리 이어지도록 래핑."""
    pts = rng.random((n, 2)) * [w, h]
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    ds = []
    for px, py in pts:
        dx = np.abs(xs - px); dx = np.minimum(dx, w - dx)
        dy = np.abs(ys - py); dy = np.minimum(dy, h - dy)
        ds.append(np.sqrt(dx * dx + dy * dy))
    ds = np.sort(np.stack(ds), axis=0)
    return ds[1] - ds[0]


def to_img(rgb, alpha=None):
    a = np.full(rgb.shape[:2], 255.0) if alpha is None else alpha
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 255)]).astype("uint8"), "RGBA")


# ─────────────────────────────── 정적 바위 텍스처 ───────────────────────────────

def paint_basalt(w, h, seed, base=("#1d1716", "#4b3e39"), crack_col="#0b0707",
                 hot=0.0, n_cells=7, warm=0.0):
    """현무암: 노이즈 바탕 + 보로노이 균열 + 균열 위 하이라이트. hot>0 이면 균열이 달아오른다."""
    rng = np.random.default_rng(seed)
    v = fbm(w, h, rng)
    lo, hi = np.array(_hx(base[0]), float), np.array(_hx(base[1]), float)
    rgb = lo + (hi - lo) * v[..., None] ** 1.2
    # 위쪽이 살짝 밝게 (돌 판의 입체감)
    ys = np.mgrid[0:h, 0:w][0] / max(1, h - 1)
    rgb *= (1.08 - 0.18 * ys)[..., None]
    e = voronoi(w, h, n_cells, rng)
    crack = e < 1.15
    # 균열 바로 위 픽셀은 밝은 모서리
    edge_hi = np.roll(crack, 1, axis=0) & ~crack
    rgb[edge_hi] = rgb[edge_hi] * 1.35 + 10
    if hot > 0:
        glow = np.clip(1 - e / 2.6, 0, 1) ** 2 * hot
        hotcol = palette(0.40 + 0.42 * np.clip(1 - e / 1.2, 0, 1))
        rgb = rgb * (1 - glow[..., None] * 0.6) + np.array(_hx("#7a1000")) * glow[..., None] * 0.6
        rgb[crack] = hotcol[crack]
    else:
        rgb[crack] = _hx(crack_col)
    if warm > 0:  # 붉은 불씨 점
        sp = rng.random((h, w)) < warm
        rgb[sp] = _hx("#c4380a")
    # 미세 거칠기
    rgb *= (0.93 + 0.14 * rng.random((h, w)))[..., None]
    return to_img(rgb)


def paint_obsidian(w, h, seed):
    rng = np.random.default_rng(seed)
    v = fbm(w, h, rng, ((6, .6), (3, .4)))
    lo, hi = np.array(_hx("#0c0612"), float), np.array(_hx("#2e1840"), float)
    rgb = lo + (hi - lo) * v[..., None]
    ys, xs = np.mgrid[0:h, 0:w]
    sheen = np.clip(1 - np.abs(((xs + ys) % 12) - 3) / 2.0, 0, 1)  # 대각 광택
    rgb += sheen[..., None] * np.array([40, 24, 70])
    gl = rng.random((h, w)) < 0.04
    rgb[gl] = _hx("#a77de0")
    return to_img(rgb)


def paint_horn(w, h, seed):
    """뿔: 아래(밑동) 검은 흑요석 → 위로 갈수록 붉게 달아오름 + 고리 마디"""
    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h, 0:w]
    t = 1 - ys / (h - 1)  # 위가 1
    base = np.array(_hx("#120a18"), float) + np.array([18, 8, 30]) * (xs % 5 == 2)[..., None]  # 흑요석 결
    k = np.clip((t - 0.55) / 0.45, 0, 1)[..., None]                  # 위쪽 45% 만 달아오름
    rgb = base * (1 - k) + palette(0.3 + 0.5 * k[..., 0]) * k
    ring = (ys % 6) == 0
    rgb[ring] *= 0.55
    ridge = (xs == 1) | (xs == w // 2)
    rgb[ridge] = rgb[ridge] * 1.3 + 8
    rgb *= (0.9 + 0.2 * rng.random((h, w)))[..., None]
    return to_img(rgb)


def paint_teeth(w, h, seed):
    rng = np.random.default_rng(seed)
    ys = np.mgrid[0:h, 0:w][0] / (h - 1)
    rgb = np.array(_hx("#e8d6b0"), float) * (1 - ys[..., None] * 0.5) + np.array(_hx("#ff9030"), float) * ys[..., None] * 0.5
    rgb *= (0.9 + 0.15 * rng.random((h, w)))[..., None]
    return to_img(rgb)


# ─────────────────────────────── 애니메이션 용암/불꽃 텍스처 ───────────────────────────────

def lava_frame(w, h, f, bright=0.0):
    """흐르는 용암. 공간/시간 모두 주기적이라 프레임이 끊김 없이 반복된다."""
    t = 2 * math.pi * f / NF
    ys, xs = np.mgrid[0:h, 0:w]
    u, v = 2 * math.pi * xs / w, 2 * math.pi * ys / h
    warp = 0.9 * np.sin(u + 2 * v - t) + 0.5 * np.sin(3 * u - v + t)
    r1 = 1 - np.abs(np.sin(2 * u + warp + 0.5 * np.sin(2 * v - t)))
    r2 = 1 - np.abs(np.sin(3 * v - u + 1.3 * warp - 2 * t))
    base = 0.5 + 0.25 * np.sin(u + 3 * v - t) * np.cos(2 * u - v + t)
    val = 0.22 + 0.55 * np.maximum(r1 ** 4, r2 ** 5) + 0.30 * base + bright
    return to_img(palette(val))


def core_frame(w, h, f):
    """가슴 코어: 백열 중심이 맥동, 소용돌이 광선."""
    t = 2 * math.pi * f / NF
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    dx, dy = (xs - w / 2) / (w / 2), (ys - h / 2) / (h / 2)
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)
    pulse = 0.5 + 0.5 * math.sin(t)
    val = 1.08 - r * (0.75 - 0.2 * pulse) + 0.12 * np.sin(5 * ang + 3 * r * 4 - t) * r
    val += 0.06 * np.sin(2 * t) * (1 - r)
    rgb = palette(val)
    rim = (np.maximum(np.abs(dx), np.abs(dy)) > 0.86)
    rgb[rim] = rgb[rim] * 0.6
    return to_img(rgb)


def eye_frame(w, h, f):
    t = 2 * math.pi * f / NF
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    dx, dy = (xs - w / 2) / (w / 2), (ys - h / 2) / (h / 2)
    r = np.sqrt(dx * dx * 0.6 + dy * dy)
    val = 1.05 - 0.45 * r + 0.06 * math.sin(3 * t) + 0.04 * np.sin(4 * xs - 2 * t)
    return to_img(palette(val))


def flame_frame(w, h, f, tongues=3, seed=0):
    """
    불꽃 혀: 아래가 백열, 위로 갈수록 주황→빨강, 바깥은 투명.
    시간 성분이 정수배라 루프가 매끄럽다.
    """
    t = 2 * math.pi * f / NF
    rnd = random.Random(seed)
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    nx = xs / w * 2 - 1           # -1..1
    ny = 1 - ys / h               # 아래 0 → 위 1
    shape = np.zeros_like(nx)
    for k in range(tongues):
        c = (k + 0.5) / tongues * 1.7 - 0.85 + rnd.uniform(-.1, .1)
        hgt = 0.62 + 0.3 * (1 - abs(c)) + 0.12 * math.sin(t * (1 + k % 2) + k * 2.1)
        wid = 0.32 + 0.08 * math.sin(t + k)
        sway = 0.12 * math.sin(t + k * 1.7) * ny
        shape = np.maximum(shape, hgt * np.exp(-((nx - c - sway) / wid) ** 2))
    turb = 0.10 * np.sin(6 * nx + 7 * ny * 3.14 - 2 * t) + 0.07 * np.sin(11 * nx - 9 * ny * 3.14 - 3 * t)
    inten = shape - ny + turb * ny
    vis = inten > 0
    val = np.clip(0.36 + inten * 0.95 + (1 - ny) ** 2 * 0.22, 0, 1)
    rgb = palette(val)
    alpha = np.where(vis, 255, 0).astype(float)
    # 위로 튀는 불씨
    for k in range(5):
        ex = int((rnd.random() * w + 3 * math.sin(t + k)) % w)
        ey = int(((rnd.random() - f / NF * 2) % 1.0) * h * 0.45)
        if 0 <= ey < h:
            rgb[ey, ex] = _hx("#ffd04a")
            alpha[ey, ex] = 255
    return to_img(rgb, alpha)


# ─────────────────────────────── 아틀라스 구성 ───────────────────────────────

def make_atlases():
    rock = Atlas(f"boss/{BOSS}", size=128, frames=1)
    lava = Atlas(f"boss/{BOSS}_lava", size=64, frames=NF, frametime=3, interpolate=True)
    R = {}

    def put_static(name, img):
        reg = rock.alloc(*img.size)
        reg.paste(img)
        R[name] = ("r", reg)

    # 바위 (32x32 이 기본 크기)
    put_static("basalt", paint_basalt(32, 32, 11, base=("#141319", "#45404c"), n_cells=6))
    put_static("basalt2", paint_basalt(32, 32, 12, base=("#1a181f", "#544e5a"), n_cells=9, warm=0.012))
    put_static("hot", paint_basalt(32, 32, 13, base=("#1e1412", "#4a3530"), hot=1.0, n_cells=8))
    put_static("obsidian", paint_obsidian(32, 32, 14))
    put_static("dark", paint_basalt(32, 32, 15, base=("#0d0c10", "#28252d"), n_cells=5))
    put_static("crust", paint_basalt(32, 32, 16, base=("#2a1410", "#5a2a1a"), hot=0.7, n_cells=12))
    put_static("horn", paint_horn(16, 32, 17))
    put_static("teeth", paint_teeth(8, 8, 18))

    def put_anim(name, w, h, fn):
        reg = lava.alloc(w, h)
        for f in range(NF):
            reg.paste(fn(w, h, f), frame=f)
        R[name] = ("l", reg)

    put_anim("lava", 32, 32, lava_frame)
    put_anim("flame", 16, 32, lambda w, h, f: flame_frame(w, h, f, 3, 1))
    put_anim("core", 16, 16, core_frame)
    put_anim("ember", 16, 16, lambda w, h, f: lava_frame(w, h, f, bright=0.16))
    put_anim("flame_big", 32, 32, lambda w, h, f: flame_frame(w, h, f, 4, 2))
    put_anim("eye", 8, 8, eye_frame)
    return rock, lava, R


GLOW = {"lava", "core", "ember", "eye", "flame", "flame_big"}


class Builder:
    """모델에 '재질' 이름으로 박스를 쌓는다. 면마다 텍셀 밀도가 일정하도록 UV 를 잘라 쓴다."""

    def __init__(self, name, atlases, regs, dens, seed=0):
        self.m = Model(name)
        rock, lava = atlases
        self.m.use("r", rock)
        self.m.use("l", lava)
        self.R = regs
        self.dens = dens
        self.rng = random.Random(seed)

    def _uv(self, reg, a, b):
        pw = min(reg.w, max(1.0, a * self.dens))
        ph = min(reg.h, max(1.0, b * self.dens))
        ox = self.rng.uniform(0, reg.w - pw)
        oy = self.rng.uniform(0, reg.h - ph)
        return reg.uv(sub=(ox, oy, ox + pw, oy + ph))

    def box(self, frm, to, mat_, light=None, rot=None, faces=FACES, full=False):
        key, reg = self.R[mat_]
        if light is None:
            light = 15 if mat_ in GLOW else 0
        dx, dy, dz = (abs(to[i] - frm[i]) for i in range(3))
        dims = {"north": (dx, dy), "south": (dx, dy), "east": (dz, dy), "west": (dz, dy),
                "up": (dx, dz), "down": (dx, dz)}
        fd = {}
        for f in faces:
            fd[f] = (key, reg.uv() if full else self._uv(reg, *dims[f]))
        rotation = None
        if rot:
            axis, ang = rot[0], rot[1]
            origin = rot[2] if len(rot) > 2 else [(frm[i] + to[i]) / 2 for i in range(3)]
            rotation = {"origin": [round(o, 4) for o in origin], "axis": axis, "angle": ang}
        return self.m.box(frm, to, fd, light=light, rotation=rotation, shade=light < 8)

    def crack(self, pts, face_z, w=0.5, depth=0.35, mat_="ember", axis="z"):
        """앞면(face_z)에 붙는 빛나는 지그재그 균열. pts=[(x,y)...] 를 가로/세로 토막으로 잇는다.
        axis="x" 이면 옆면(face_z 가 x 좌표)에 붙고 pts 는 (z, y)."""
        h = w / 2
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            segs = [((min(x0, x1) - h, y0 - h), (max(x0, x1) + h, y0 + h)),
                    ((x1 - h, min(y0, y1) - h), (x1 + h, max(y0, y1) + h))]
            for (a0, b0), (a1, b1) in segs:
                if a1 - a0 < w * 1.01 and b1 - b0 < w * 1.01 and (x0, y0) != (x1, y1):
                    continue
                if axis == "z":
                    sgn = 1 if face_z > 8 else -1   # 앞면(+z) / 뒷면(-z)
                    lo, hi = sorted((face_z - 0.05 * sgn, face_z + depth * sgn))
                    self.box((a0, b0, lo), (a1, b1, hi), mat_)
                else:
                    sgn = 1 if face_z > 8 else -1
                    lo, hi = sorted((face_z - 0.05 * sgn, face_z + depth * sgn))
                    self.box((lo, b0, a0), (hi, b1, a1), mat_)

    def flame(self, cx, cz, y0, y1, w, mat_="flame_big", diag=True):
        """십자 불꽃 평면 2장 (대각선으로 돌려 어느 방향에서나 보이게)."""
        key, reg = self.R[mat_]
        hw = w / 2
        rot = {"origin": [cx, y0, cz], "axis": "y", "angle": 45 if diag else 0}
        for plane in ("z", "x"):
            if plane == "z":
                frm, to = (cx - hw, y0, cz), (cx + hw, y1, cz)
                fd = {"north": (key, reg.uv()), "south": (key, reg.uv())}
            else:
                frm, to = (cx, y0, cz - hw), (cx, y1, cz + hw)
                fd = {"east": (key, reg.uv()), "west": (key, reg.uv())}
            self.m.box(frm, to, fd, light=15, shade=False, rotation=dict(rot) if diag else None)


# ─────────────────────────────── 파트 모델 ───────────────────────────────

def mirror_x(frm, to):
    return (16 - to[0], frm[1], frm[2]), (16 - frm[0], to[1], to[2])


def build_torso(at, R):
    """scale 2.0 (1칸 = 0.125블록). 피벗 (8,8,8) = 가슴 중심."""
    b = Builder(f"boss/{BOSS}_torso", at, R, dens=2.0, seed=1)
    # 안쪽 용암 몸통 (바위 판 사이 틈으로만 보인다)
    b.box((1.2, 3.5, 4.2), (14.8, 16.8, 12.8), "lava")
    b.box((3.6, -1.6, 5.0), (12.4, 4.0, 11.6), "lava")
    # 가슴 근육판 2장 (가운데 세로 이음매)
    b.box((0.4, 11.0, 3.0), (7.6, 17.2, 13.8), "basalt")
    b.box((8.4, 11.0, 3.0), (15.6, 17.2, 13.8), "basalt")
    # 가슴판 앞쪽 돌출 (근육 느낌)
    b.box((1.2, 11.8, 13.6), (7.2, 16.4, 14.6), "basalt2")
    b.box((8.8, 11.8, 13.6), (14.8, 16.4, 14.6), "basalt2")
    # 옆구리 덩이 (코어 높이)
    b.box((0.8, 4.2, 3.4), (5.8, 10.4, 13.2), "basalt2")
    b.box((10.2, 4.2, 3.4), (15.2, 10.4, 13.2), "basalt2")
    # 갈비뼈 홈 (흑요석 띠)
    for y in (8.4, 5.8):
        b.box((1.4, y, 12.9), (5.4, y + 1.0, 13.8), "obsidian")
        b.box((10.6, y, 12.9), (14.6, y + 1.0, 13.8), "obsidian")
    # 코어 뒤판 (등 쪽 막음)
    b.box((5.8, 4.2, 3.4), (10.2, 10.4, 6.0), "dark")
    # 마그마 코어: 45도 다이아몬드 2겹 + 흑요석 발톱 4개
    b.box((4.4, 3.7, 11.8), (11.6, 10.9, 12.9), "ember", rot=("z", 45, (8, 7.3, 12.4)))
    b.box((5.4, 4.7, 12.2), (10.6, 9.9, 15.8), "core", rot=("z", 45, (8, 7.3, 14.0)))
    b.box((7.3, 11.4, 12.8), (8.7, 13.6, 15.4), "obsidian", rot=("x", -22.5, (8, 11.4, 14.0)))
    b.box((7.3, 1.0, 12.8), (8.7, 3.2, 15.4), "obsidian", rot=("x", 22.5, (8, 3.2, 14.0)))
    b.box((2.6, 6.7, 12.8), (4.2, 7.9, 15.0), "obsidian")
    b.box((11.8, 6.7, 12.8), (13.4, 7.9, 15.0), "obsidian")
    # 복부 (아래로 좁아지는 V)
    b.box((2.8, 0.4, 4.0), (13.2, 3.8, 12.8), "crust", light=6)
    b.box((4.4, -2.4, 4.8), (11.6, 0.0, 11.8), "dark")
    # 쇄골 흑요석 테
    b.box((1.6, 17.0, 4.0), (7.0, 18.2, 12.6), "obsidian")
    b.box((9.0, 17.0, 4.0), (14.4, 18.2, 12.6), "obsidian")
    # 목 (용암) + 목깃
    b.box((5.2, 16.6, 5.2), (10.8, 18.8, 10.8), "lava")
    # 등: 척추 가시 (뒤로 비스듬히)
    for i, y in enumerate((15.6, 12.2, 8.8, 5.4, 2.0)):
        ln = 5.4 - i * 0.8
        b.box((7.2, y - 0.9, 3.4 - ln), (8.8, y + 0.9, 3.6), "obsidian", rot=("x", -22.5, (8, y, 3.4)))
        b.box((7.5, y - 0.6, 3.0 - ln), (8.5, y + 0.6, 3.4 - ln + 1.0), "ember", rot=("x", -22.5, (8, y, 3.4)))
    # 등판 균열
    for sgn in (1, -1):
        def mx(x):
            return x if sgn > 0 else 16 - x
        b.crack([(mx(9.6), 15.6), (mx(11.0), 15.6), (mx(11.0), 13.0), (mx(13.0), 13.0), (mx(13.0), 11.6),
                 (mx(14.6), 11.6)], 3.0)
        b.crack([(mx(10.8), 9.4), (mx(12.4), 9.4), (mx(12.4), 6.6), (mx(14.0), 6.6)], 3.4)
    # 등의 화산 굴뚝 2개 + 불꽃
    for cx in (3.8, 12.2):
        b.box((cx - 2.2, 14.0, 0.8), (cx + 2.2, 17.6, 4.6), "dark")
        b.box((cx - 1.6, 17.4, 1.4), (cx + 1.6, 19.4, 4.0), "crust", light=6)
        b.box((cx - 1.0, 18.8, 2.0), (cx + 1.0, 19.6, 3.4), "lava")
        b.flame(cx, 2.7, 19.4, 26.0, 5.0)
    # 가슴의 빛나는 균열 (코어에서 위/바깥으로 뻗음)
    for sgn in (1, -1):
        def mx(x):
            return x if sgn > 0 else 16 - x
        b.crack([(mx(9.4), 12.3), (mx(10.6), 12.3), (mx(10.6), 13.5), (mx(12.4), 13.5), (mx(12.4), 15.0),
                 (mx(13.8), 15.0)], 14.6)
        b.crack([(mx(11.2), 10.0), (mx(12.4), 10.0), (mx(12.4), 8.6), (mx(14.2), 8.6)], 13.2)
        b.crack([(mx(10.9), 3.4), (mx(10.9), 2.2), (mx(12.0), 2.2), (mx(12.0), 1.0)], 12.8)
    # 어깨: +X 쪽을 만들고 거울로 -X 쪽
    for side in (1, -1):
        def bx(x0, y0, z0, x1, y1, z1, m, rot=None, light=None):
            a, c = (x0, x1) if side > 0 else (16 - x1, 16 - x0)
            if rot:
                ax, ang, o = rot
                o = (o[0] if side > 0 else 16 - o[0], o[1], o[2])
                ang = ang * side if ax in ("z", "y") else ang  # x 거울 → z/y 회전 부호 반전
                rot = (ax, ang, o)
            b.box((a, y0, z0), (c, y1, z1), m, rot=rot, light=light)

        bx(15.0, 9.0, 3.8, 21.6, 17.2, 12.6, "lava")                    # 어깨 속 용암
        bx(15.8, 13.6, 2.6, 22.8, 18.4, 13.6, "basalt")                 # 어깨 윗덩이
        bx(16.4, 8.2, 3.2, 23.4, 13.2, 13.0, "basalt2")                 # 어깨 아랫덩이
        bx(22.4, 9.2, 4.2, 24.2, 16.6, 12.0, "dark")                    # 바깥 갑판
        bx(16.6, 18.2, 3.6, 22.0, 19.4, 12.6, "obsidian")               # 견갑 테
        bx(17.4, 7.0, 4.4, 21.6, 8.4, 11.8, "crust", light=6)           # 겨드랑이 아래 균열
        def sx(x):
            return x if side > 0 else 16 - x
        b.crack([(sx(17.2), 17.4), (sx(18.4), 17.4), (sx(18.4), 15.8), (sx(20.0), 15.8), (sx(20.0), 14.4)], 13.6)
        b.crack([(sx(21.0), 12.4), (sx(21.0), 10.8), (sx(22.2), 10.8), (sx(22.2), 9.2)], 13.0)
        b.crack([(5.0, 17.0), (6.6, 17.0), (6.6, 15.0), (8.4, 15.0), (8.4, 12.6), (10.0, 12.6)],
                24.2 if side > 0 else -8.2, axis="x")
        # 어깨 가시 3개 (바깥/위로 부채꼴)
        for (z0, z1, ang, h, x0) in ((4.0, 6.6, -22.5, 7.4, 19.8), (9.4, 12.0, -45, 6.2, 20.6)):
            oz = (z0 + z1) / 2
            o = (x0 + 1.1, 18.6, oz)
            bx(x0, 18.0, z0, x0 + 2.2, 18.0 + h, z1, "obsidian", rot=("z", ang, o))
            bx(x0 + 0.5, 17.6 + h, z0 + 0.5, x0 + 1.7, 19.6 + h, z1 - 0.5, "ember", rot=("z", ang, o))
    return b.m


def build_head(at, R):
    """scale 1.7 (1칸 ≈ 0.106블록). 피벗 = 목 밑동, 위로 자란다."""
    b = Builder(f"boss/{BOSS}_head", at, R, dens=1.7, seed=2)
    b.box((3.8, 7.6, 4.2), (12.2, 18.6, 12.2), "lava")                 # 안쪽 용암
    b.box((3.0, 15.0, 3.0), (13.0, 20.8, 12.0), "basalt")              # 두개골 윗덩이
    b.box((3.4, 9.8, 3.0), (12.6, 15.4, 6.6), "dark")                  # 뒤통수
    b.box((3.2, 10.2, 7.6), (12.8, 14.6, 12.4), "basalt2")             # 얼굴 덩이
    # 화난 V 눈썹 (안쪽 끝이 아래로)
    b.box((8.0, 14.4, 11.2), (13.8, 16.4, 14.6), "obsidian", rot=("z", 22.5, (8.0, 15.4, 13)))
    b.box((2.2, 14.4, 11.2), (8.0, 16.4, 14.6), "obsidian", rot=("z", -22.5, (8.0, 15.4, 13)))
    # 타오르는 눈
    b.box((3.8, 12.4, 12.2), (7.2, 14.0, 13.4), "eye")
    b.box((8.8, 12.4, 12.2), (12.2, 14.0, 13.4), "eye")
    # 콧등
    b.box((7.2, 10.8, 12.2), (8.8, 14.4, 13.8), "basalt")
    # 광대
    b.box((2.6, 10.2, 9.0), (4.6, 12.6, 13.4), "basalt")
    b.box((11.4, 10.2, 9.0), (13.4, 12.6, 13.4), "basalt")
    # 아래턱 + 용암 입 + 송곳니
    b.box((3.4, 6.0, 4.6), (12.6, 9.2, 13.8), "basalt")
    b.box((4.6, 8.4, 13.0), (11.4, 9.0, 14.2), "obsidian")
    b.box((4.4, 9.2, 11.2), (11.6, 10.2, 12.8), "ember")
    for x in (4.8, 10.2):
        b.box((x, 8.6, 12.6), (x + 1.0, 10.6, 13.6), "teeth")
    for x in (6.6, 8.4):
        b.box((x, 9.4, 12.4), (x + 1.0, 10.4, 13.2), "teeth")
    # 정수리 볏 (뒤로 솟은 흑요석 가시)
    b.box((7.0, 19.0, 4.6), (9.0, 25.0, 7.6), "obsidian", rot=("x", -22.5, (8, 19, 6.1)))
    b.box((7.4, 24.6, 5.0), (8.6, 26.6, 7.2), "ember", rot=("x", -22.5, (8, 19, 6.1)))
    # 뿔: 옆으로 나왔다가 S 자로 휘어 위로 (마디가 이어지도록 회전 원점을 마디 밑동에)
    s22 = math.sin(math.radians(22.5)); c22 = math.cos(math.radians(22.5))
    for side in (1, -1):
        def hb(x0, y0, z0, x1, y1, z1, m, ang=0, o=None, full=False):
            a, c = (x0, x1) if side > 0 else (16 - x1, 16 - x0)
            rot = None
            if ang:
                ox = o[0] if side > 0 else 16 - o[0]
                rot = ("z", ang * side, (ox, o[1], o[2]))
            b.box((a, y0, z0), (c, y1, z1), m, rot=rot, full=full)

        hb(12.2, 15.6, 5.0, 17.4, 19.0, 10.0, "obsidian")               # 밑동 (옆으로)
        bx0, by0 = 16.0, 17.4                                           # 2마디 밑동 중심
        hb(bx0 - 1.6, by0, 5.6, bx0 + 1.6, by0 + 7.0, 9.4, "obsidian", -22.5, (bx0, by0, 7.5))
        tx, ty = bx0 + 6.4 * s22, by0 + 6.4 * c22                        # 2마디 끝
        hb(tx - 1.2, ty, 6.0, tx + 1.2, ty + 5.4, 9.0, "horn", 22.5, (tx, ty, 7.5), full=True)
        hb(tx - 0.7, ty + 5.0, 6.6, tx + 0.7, ty + 7.6, 8.4, "ember", 22.5, (tx, ty, 7.5))
    # 머리 위 불꽃
    b.flame(8.0, 6.0, 20.4, 28.0, 7.0)
    return b.m


def build_fist(at, R, side):
    """scale 1.9 (1칸 ≈ 0.12블록). side=+1 → +X(왼손), -1 → -X(오른손). 엄지는 몸 안쪽(-X 쪽 기준 작성 후 거울)."""
    name = "left_fist" if side > 0 else "right_fist"
    b = Builder(f"boss/{BOSS}_{name}", at, R, dens=1.9, seed=3 if side > 0 else 4)
    mir = side < 0

    def bx(x0, y0, z0, x1, y1, z1, m, rot=None, light=None):
        a, c = (x0, x1) if not mir else (16 - x1, 16 - x0)
        if rot and mir and rot[0] in ("y", "z"):
            ax, ang, o = rot
            rot = (ax, -ang, (16 - o[0], o[1], o[2]))
        elif rot and mir:
            ax, ang, o = rot
            rot = (ax, ang, (16 - o[0], o[1], o[2]))
        b.box((a, y0, z0), (c, y1, z1), m, rot=rot, light=light)

    bx(3.6, 1.8, 4.6, 13.4, 10.6, 16.6, "lava")                        # 안쪽 용암 (틈으로 보임)
    # 손등 (2조각, 가운데 용암 이음매)
    bx(3.0, 9.4, 3.8, 8.2, 12.6, 13.4, "basalt")
    bx(8.8, 9.4, 3.8, 14.0, 12.6, 13.4, "basalt")
    bx(5.0, 12.4, 5.0, 12.0, 13.4, 11.0, "obsidian")                   # 손등 힘줄 판
    bx(3.2, 1.0, 4.2, 13.8, 9.0, 12.4, "basalt2")                      # 손바닥
    # 손가락 4개
    for i in range(4):
        x0 = 3.0 + i * 2.8
        hx = 0.25 if i in (1, 2) else 0.0                                # 가운데 두 손가락이 살짝 더 앞으로
        bx(x0, 5.2, 12.4, x0 + 2.4, 10.2, 17.6 + hx, "basalt")           # 너클 (첫마디)
        bx(x0 + 0.15, 1.0, 12.0, x0 + 2.25, 5.0, 16.4 + hx, "dark")      # 말린 둘째마디
        # 너클 위 빛나는 균열 (지그재그 두 줄)
        bx(x0 + 0.3, 8.2, 17.5 + hx, x0 + 1.4, 8.7, 17.9 + hx, "ember")
        bx(x0 + 1.1, 7.4, 17.5 + hx, x0 + 2.1, 7.9, 17.9 + hx, "ember")
        # 너클 스파이크 (앞-위로)
        o = (x0 + 1.2, 9.8, 16.0)
        bx(x0 + 0.55, 9.6, 14.8, x0 + 1.85, 12.6, 16.6, "obsidian", rot=("x", 22.5, o))
        bx(x0 + 0.8, 12.4, 15.1, x0 + 1.6, 13.8, 16.3, "ember", rot=("x", 22.5, o))
    # 엄지: 옆면 + 앞으로 감싸는 끝마디
    bx(0.6, 1.6, 7.0, 3.4, 6.6, 14.6, "basalt")
    bx(1.0, 1.4, 14.2, 8.0, 4.4, 18.6, "basalt2")
    bx(1.4, 3.9, 17.6, 3.2, 4.8, 18.8, "ember")
    # 손목: 용암 고리 + 깨진 흑요석 팔찌 4조각
    bx(4.2, 3.0, 0.6, 12.8, 10.2, 4.6, "lava")
    bx(3.2, 9.6, 1.4, 13.8, 11.4, 4.0, "obsidian")
    bx(3.6, 1.8, 1.4, 13.4, 3.4, 4.0, "obsidian")
    bx(2.6, 3.8, 1.6, 4.0, 9.0, 3.8, "obsidian")
    bx(13.0, 3.8, 1.6, 14.4, 9.0, 3.8, "obsidian")
    # 뒤로 흩어지는 파편
    bx(5.2, 4.0, -2.4, 8.2, 7.0, 0.4, "dark", rot=("y", 22.5, (6.7, 5.5, -1.0)))
    bx(9.4, 6.4, -4.0, 11.4, 8.4, -2.0, "crust", rot=("x", 22.5, (10.4, 7.4, -3.0)), light=6)
    bx(6.8, 2.2, -5.6, 8.2, 3.6, -4.2, "ember")
    bx(10.6, 3.0, -7.0, 11.6, 4.0, -6.0, "ember")
    return b.m


def build_tail(at, R):
    """scale 1.4. 피벗 = 꼬리 맨 위, 아래로 흩어지는 바위 조각 (용암 실로 이어짐)."""
    b = Builder(f"boss/{BOSS}_tail", at, R, dens=1.4, seed=5)
    b.box((6.6, -14.0, 6.6), (9.4, 9.0, 9.4), "lava")                  # 용암 실 (척추)
    segs = [  # (y0, y1, 반폭, 재질, y회전)
        (2.2, 9.4, 5.8, "basalt", 0),
        (-4.0, 0.8, 4.8, "basalt2", 22.5),
        (-9.0, -5.4, 3.6, "dark", 45),
        (-12.8, -10.2, 2.4, "basalt", 22.5),
    ]
    for (y0, y1, hw, m, ang) in segs:
        rot = ("y", ang) if ang else None
        b.box((8 - hw, y0, 8 - hw), (8 + hw, y1, 8 + hw), m, rot=rot)
        # 아랫면이 달아오른 균열 껍질
        b.box((8 - hw + 0.6, y0 - 0.6, 8 - hw + 0.6), (8 + hw - 0.6, y0 + 0.2, 8 + hw - 0.6), "crust",
              rot=rot, light=10)
    # 첫 마디 앞의 흑요석 판 + 용암 균열
    b.box((3.6, 3.4, 13.6), (12.4, 8.4, 14.6), "obsidian")
    b.box((7.4, 4.0, 14.4), (8.6, 7.8, 14.9), "ember")
    b.box((7.1, -16.0, 7.1), (8.9, -13.6, 8.9), "ember")                # 떨어지는 용암 방울
    # 주변을 떠도는 작은 파편
    for (x, y, z, s, m) in ((0.6, -2.4, 9.0, 2.2, "dark"), (13.6, -1.4, 5.0, 2.0, "basalt"),
                            (3.0, -8.4, 3.6, 1.6, "crust"), (12.2, -7.4, 11.0, 1.6, "obsidian"),
                            (10.2, -12.8, 3.6, 1.2, "ember"), (4.4, -12.0, 11.8, 1.2, "ember")):
        b.box((x, y, z), (x + s, y + s, z + s), m, rot=("y", 45))
    return b.m


def build_rock(at, R, variant):
    """scale 1.0. 주위를 도는 불타는 바위. 피벗 = 중심."""
    b = Builder(f"boss/{BOSS}_rock_{variant}", at, R, dens=1.0, seed=6 + (variant == "b"))
    if variant == "a":
        b.box((5.0, 4.6, 5.0), (11.0, 10.6, 11.0), "lava")
        b.box((4.2, 6.6, 4.2), (11.8, 11.4, 11.8), "basalt", rot=("y", 22.5))
        b.box((4.6, 3.4, 4.6), (11.4, 7.0, 11.4), "crust", rot=("x", 22.5), light=8)
        b.box((9.6, 8.6, 6.0), (13.0, 12.0, 9.6), "obsidian", rot=("z", -22.5))
        b.flame(8, 8, 11.0, 19.0, 6.0, "flame")
    else:
        b.box((5.4, 5.0, 5.4), (10.6, 10.6, 10.6), "lava")
        b.box((4.0, 5.6, 4.6), (12.0, 10.0, 11.4), "basalt2", rot=("z", 22.5))
        b.box((5.4, 8.2, 5.0), (10.2, 11.8, 10.6), "crust", rot=("x", -22.5))
        b.box((3.4, 3.6, 7.0), (6.4, 6.6, 10.0), "dark", rot=("y", 45))
        b.flame(8, 8, 11.2, 18.0, 5.0, "flame")
    return b.m


def build_halo(at, R):
    """scale 2.2. 등 뒤의 용암 가시 고리 (z축으로 천천히 회전)."""
    b = Builder(f"boss/{BOSS}_halo", at, R, dens=2.2, seed=8)
    # 8방향 가시: 축 방향 4개 + 45도 회전 4개. 안쪽 반지름 r0 ~ 바깥 r1
    r0, r1, w, d = 9.0, 16.0, 1.6, 1.2
    c = 8.0
    for ang in (0, 45):
        rot = ("z", ang, (c, c, c)) if ang else None
        # 위/아래/좌/우
        b.box((c - w / 2, c + r0, c - d / 2), (c + w / 2, c + r1 - 2, c + d / 2), "obsidian", rot=rot)
        b.box((c - w / 2, c - r1 + 2, c - d / 2), (c + w / 2, c - r0, c + d / 2), "obsidian", rot=rot)
        b.box((c + r0, c - w / 2, c - d / 2), (c + r1 - 2, c + w / 2, c + d / 2), "obsidian", rot=rot)
        b.box((c - r1 + 2, c - w / 2, c - d / 2), (c - r0, c + w / 2, c + d / 2), "obsidian", rot=rot)
        # 달아오른 끝
        e = 0.5
        b.box((c - w / 2 + e, c + r1 - 2, c - d / 2 + .2), (c + w / 2 - e, c + r1, c + d / 2 - .2), "ember", rot=rot)
        b.box((c - w / 2 + e, c - r1, c - d / 2 + .2), (c + w / 2 - e, c - r1 + 2, c + d / 2 - .2), "ember", rot=rot)
        b.box((c + r1 - 2, c - w / 2 + e, c - d / 2 + .2), (c + r1, c + w / 2 - e, c + d / 2 - .2), "ember", rot=rot)
        b.box((c - r1, c - w / 2 + e, c - d / 2 + .2), (c - r1 + 2, c + w / 2 - e, c + d / 2 - .2), "ember", rot=rot)
    # 고리 몸체: 22.5도씩 돌린 얇은 용암 막대 8개 = 16각형 근사
    rr = 8.2
    seg = 2 * rr * math.tan(math.radians(11.25)) + 0.3
    for ang in (0, 22.5, 45, -22.5):
        rot = ("z", ang, (c, c, c)) if ang else None
        b.box((c - seg / 2, c + rr - 0.6, c - 0.5), (c + seg / 2, c + rr + 0.6, c + 0.5), "lava", rot=rot)
        b.box((c - seg / 2, c - rr - 0.6, c - 0.5), (c + seg / 2, c - rr + 0.6, c + 0.5), "lava", rot=rot)
        b.box((c + rr - 0.6, c - seg / 2, c - 0.5), (c + rr + 0.6, c + seg / 2, c + 0.5), "lava", rot=rot)
        b.box((c - rr - 0.6, c - seg / 2, c - 0.5), (c - rr + 0.6, c + seg / 2, c + 0.5), "lava", rot=rot)
    return b.m



# ─────────────────────────────── z-버퍼 미리보기 렌더러 ───────────────────────────────
# mc3d.render 는 면을 깊이 평균으로 정렬하는 화가 알고리즘이라, 큰 안쪽 용암 상자가 바깥 판 위로
# 그려지는 일이 잦다. 미리보기 정확도를 위해 픽셀 단위 z-버퍼 렌더러를 따로 둔다 (같은 좌표 규칙).

def zrender(parts, size=512, yaw=-35, pitch=25, bg=(24, 22, 32), pad=0.06, ss=2):
    from mc3d import _face_corners, _rot_matrix, FACE_LIGHT
    S = size * ss
    view = _rot_matrix("x", pitch) @ _rot_matrix("y", yaw)
    faces = []
    for model, M in parts:
        M = np.eye(4) if M is None else np.array(M, dtype=float)
        texs = {k: np.array(a.frame0()).astype(float) for k, a in model.atlases.items()}
        for el in model.elements:
            cbf = _face_corners(el["from"], el["to"])
            rot = el.get("rotation")
            for fname, fd in el["faces"].items():
                tex = texs.get(fd["texture"].lstrip("#"))
                if tex is None:
                    continue
                pts = []
                for q in cbf[fname]:
                    v = np.array(q, dtype=float)
                    if rot:
                        o = np.array(rot["origin"], dtype=float)
                        v = _rot_matrix(rot["axis"], rot["angle"]) @ (v - o) + o
                    w4 = M @ np.append((v - 8.0) / 16.0, 1.0)
                    pts.append(view @ w4[:3])
                pts = np.array(pts)
                n = np.cross(pts[1] - pts[0], pts[3] - pts[0])
                if n[2] >= 0 or np.linalg.norm(n) < 1e-12:
                    continue
                lit = 1.0 if el.get("light_emission", 0) >= 8 else FACE_LIGHT[fname]
                faces.append((pts, tex, fd["uv"], fd.get("rotation", 0), lit))
    img = np.zeros((S, S, 3)) + np.array(bg[:3], float)
    if not faces:
        return Image.fromarray(img.astype("uint8"))
    allp = np.concatenate([f[0] for f in faces])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1
    sc = S * (1 - 2 * pad) / span
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    zbuf = np.full((S, S), -np.inf)  # 뷰 공간에서 z 가 클수록 카메라에 가깝다
    for pts, tex, uv, frot, lit in faces:
        sp = np.array([((q[0] - cx) * sc + S / 2, -(q[1] - cy) * sc + S / 2, q[2]) for q in pts])
        th, tw = tex.shape[:2]
        u0, v0, u1, v1 = uv[0] / 16 * tw, uv[1] / 16 * th, uv[2] / 16 * tw, uv[3] / 16 * th
        src = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for _ in range(int(frot) // 90):
            src = src[1:] + src[:1]
        p0, e1, e3 = sp[0], sp[1] - sp[0], sp[3] - sp[0]
        det = e1[0] * e3[1] - e1[1] * e3[0]
        if abs(det) < 1e-9:
            continue
        x0, x1 = int(max(0, np.floor(sp[:, 0].min()))), int(min(S, np.ceil(sp[:, 0].max()) + 1))
        y0, y1 = int(max(0, np.floor(sp[:, 1].min()))), int(min(S, np.ceil(sp[:, 1].max()) + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1] + 0.5
        dx, dy = xs - p0[0], ys - p0[1]
        s_ = (dx * e3[1] - dy * e3[0]) / det
        t_ = (e1[0] * dy - e1[1] * dx) / det
        inside = (s_ >= 0) & (s_ <= 1) & (t_ >= 0) & (t_ <= 1)
        if not inside.any():
            continue
        z = p0[2] + s_ * e1[2] + t_ * e3[2]
        a, b_, c, d = [np.array(q) for q in src]
        uvx = a + s_[..., None] * (b_ - a) + t_[..., None] * (d - a)
        ui = np.clip(np.floor(uvx[..., 0] - 1e-6 * np.sign(b_[0] - a[0])), 0, tw - 1).astype(int)
        vi = np.clip(np.floor(uvx[..., 1] - 1e-6 * np.sign(d[1] - a[1])), 0, th - 1).astype(int)
        col = tex[vi, ui]
        sub_z = zbuf[y0:y1, x0:x1]
        ok = inside & (col[..., 3] > 100) & (z > sub_z + 1e-7)
        sub_z[ok] = z[ok]
        img[y0:y1, x0:x1][ok] = col[..., :3][ok] * lit
    out = Image.fromarray(np.clip(img, 0, 255).astype("uint8"))
    return out.resize((size, size), Image.LANCZOS) if ss > 1 else out


# ─────────────────────────────── 리그 + 미리보기 ───────────────────────────────

def rig_spec():
    def bob(a, p, ph=0.0):
        return {"type": "bob", "amplitude": a, "period": p, "phase": ph}

    body_bob = bob(0.10, 60, 0.0)
    parts = [
        {"id": "tail", "model": "tail", "offset": [0, 2.05, -0.05], "scale": 1.4, "rotation": [0, 0, 0], "frame": "body",
         "anims": [bob(0.10, 60, 0.08), {"type": "sway", "axis": "z", "angle": 7, "period": 80, "phase": 0},
                   {"type": "sway", "axis": "x", "angle": 5, "period": 110, "phase": 0.3}]},
        {"id": "torso", "model": "torso", "offset": [0, 3.0, 0], "scale": 2.0, "rotation": [0, 0, 0], "frame": "body",
         "anims": [body_bob]},
        {"id": "halo", "model": "halo", "offset": [0, 3.9, -1.05], "scale": 2.2, "rotation": [0, 0, 0], "frame": "body",
         "anims": [body_bob, {"type": "spin", "axis": "z", "speed": 1.5}]},
        {"id": "head", "model": "head", "offset": [0, 4.18, 0.3], "scale": 1.7, "rotation": [0, 0, 0], "frame": "body",
         "anims": [body_bob, {"type": "sway", "axis": "y", "angle": 9, "period": 120, "phase": 0},
                   {"type": "swing", "axis": "x", "angle": -18, "ticks": 12}]},
        {"id": "right_fist", "model": "right_fist", "offset": [-2.3, 2.4, 0.2], "scale": 1.9, "rotation": [0, 8, 0],
         "frame": "body",
         "anims": [bob(0.22, 50, 0.25), {"type": "sway", "axis": "x", "angle": 7, "period": 70, "phase": 0.1},
                   {"type": "swing", "axis": "x", "angle": -75, "ticks": 12}]},
        {"id": "left_fist", "model": "left_fist", "offset": [2.3, 2.4, 0.2], "scale": 1.9, "rotation": [0, -8, 0],
         "frame": "body",
         "anims": [bob(0.22, 50, 0.75), {"type": "sway", "axis": "x", "angle": 7, "period": 70, "phase": 0.6},
                   {"type": "swing", "axis": "x", "angle": -75, "ticks": 12}]},
    ]
    for i in range(4):
        parts.append({"id": f"rock{i + 1}", "model": "rock_a" if i % 2 == 0 else "rock_b", "offset": [0, 0, 0],
                      "scale": 1.7 if i % 2 == 0 else 1.5, "rotation": [0, 0, 0], "frame": "world",
                      "anims": [{"type": "orbit", "radius": 3.6, "speed": 2.4, "phase": i * 90,
                                 "height": 4.4 if i % 2 else 1.4},  # 주먹 높이(1.8~3.0)를 피해 위/아래로
                                {"type": "spin", "axis": "y", "speed": 5.0 if i % 2 else -4.0},
                                bob(0.25, 40, i * 0.25)]})
    for p in parts:
        p["model"] = f"augsky:boss/{BOSS}_{p['model']}"
    return parts


def part_matrix(p, yaw_body=0.0):
    """미리보기용 배치. orbit 은 phase 각도의 원 위에 놓는다."""
    pitch, yaw, roll = p["rotation"]
    off = list(p["offset"])
    for a in p["anims"]:
        if a["type"] == "orbit":
            ph = math.radians(a["phase"] + 20)
            off = [a["radius"] * math.sin(ph), off[1] + a["height"], a["radius"] * math.cos(ph)]
    return mat(translate=off, scale=p["scale"], yaw=yaw + yaw_body, pitch=pitch, roll=roll)


def hitbox_model(w=1.8, h=5.4):
    """미리보기 전용: 히트박스 와이어프레임 (게임에 쓰지 않음)."""
    a = Atlas("preview/hitbox", size=16)
    reg = a.cell((90, 220, 255, 255), "flat")
    m = Model("preview/hitbox")
    m.use("c", a)
    W, H, t = w * 16, h * 16, 0.25
    x0, x1 = 8 - W / 2, 8 + W / 2
    y0, y1 = 8, 8 + H
    z0, z1 = 8 - W / 2, 8 + W / 2
    for (xa, xb) in ((x0, x0 + t), (x1 - t, x1)):
        for (za, zb) in ((z0, z0 + t), (z1 - t, z1)):
            m.box((xa, y0, za), (xb, y1, zb), ("c", reg), light=15)
    for (ya, yb) in ((y0, y0 + t), (y1 - t, y1)):
        for (za, zb) in ((z0, z0 + t), (z1 - t, z1)):
            m.box((x0, ya, za), (x1, yb, zb), ("c", reg), light=15)
        for (xa, xb) in ((x0, x0 + t), (x1 - t, x1)):
            m.box((xa, ya, z0), (xb, yb, z1), ("c", reg), light=15)
    return m


def build(assets_root):
    at_rock, at_lava, R = make_atlases()
    at = (at_rock, at_lava)
    models = {
        "torso": build_torso(at, R),
        "head": build_head(at, R),
        "left_fist": build_fist(at, R, +1),
        "right_fist": build_fist(at, R, -1),
        "tail": build_tail(at, R),
        "rock_a": build_rock(at, R, "a"),
        "rock_b": build_rock(at, R, "b"),
        "halo": build_halo(at, R),
    }
    tex_root = os.path.join(assets_root, "textures")
    at_rock.save(tex_root)
    at_lava.save(tex_root)
    for m in models.values():
        m.write(assets_root)

    parts = rig_spec()
    spec = {
        "boss": BOSS,
        "parts": parts,
        "notes": ("화염 거신: 떠다니는 용암 바위 거인. 피벗 (8,8,8). torso=가슴 중심(발 기준 3.0블록), head=목 밑동, "
                  "fists=손목 뒤쪽(주먹은 피벗 앞/아래), tail=꼬리 윗끝(아래로 매달림), halo=등 뒤 고리 중심(z축 회전), "
                  "rocks=world 프레임 orbit (offset 0, height 가 발 기준 높이). 앞=+Z, 오른손=-X. "
                  "용암/불꽃은 애니메이션 텍스처(boss/inferno_colossus_lava, 16프레임x3틱)이며 light_emission 15."),
    }
    os.makedirs(HERE, exist_ok=True)
    with open(os.path.join(HERE, f"{MODULE}.rig.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)

    # ── 미리보기 ──
    os.makedirs(PREVIEW, exist_ok=True)
    by_name = {k: v for k, v in models.items()}

    def scene(with_hitbox=False):
        out = []
        for p in parts:
            key = p["model"].split(f"{BOSS}_")[1]
            out.append((by_name[key], part_matrix(p)))
        if with_hitbox:
            out.append((hitbox_model(), mat(translate=(0, 0, 0))))
        return out

    views = [(35, 12, "앞 3/4"), (0, 4, "정면"), (90, 8, "옆"), (180 + 35, 15, "뒤 3/4")]
    imgs = [zrender(scene(), size=640, yaw=y, pitch=pt) for y, pt, _ in views]
    imgs.append(zrender(scene(True), size=640, yaw=35, pitch=12))
    labels = [v[2] for v in views] + ["히트박스 1.8x5.4"]
    contact_sheet(imgs, labels, cols=5, cell=420, font=FONT).save(os.path.join(PREVIEW, f"{BOSS}.png"))
    # 크게 한 장
    zrender(scene(), size=900, yaw=28, pitch=10).save(os.path.join(PREVIEW, f"{BOSS}_hero.png"))

    pi, pl = [], []
    for k, m in models.items():
        pi.append(zrender([(m, None)], size=400, yaw=35, pitch=20))
        pl.append(f"{k} 앞")
        pi.append(zrender([(m, None)], size=400, yaw=180 + 35, pitch=20))
        pl.append(f"{k} 뒤")
    contact_sheet(pi, pl, cols=4, cell=300, font=FONT).save(os.path.join(PREVIEW, f"{BOSS}_parts.png"))
    # 텍스처 확인용
    tex = Image.new("RGBA", (128 + 64 * 4, 128), (18, 16, 26, 255))
    tex.alpha_composite(at_rock.img)
    for i in range(4):
        tex.alpha_composite(at_lava.img.crop((0, i * 4 * 64, 64, i * 4 * 64 + 64)), (128 + 64 * i, 0))
    tex.resize((tex.width * 3, tex.height * 3), Image.NEAREST).save(os.path.join(PREVIEW, f"{BOSS}_tex.png"))
    return spec


if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
    s = build(root)
    for m in os.listdir(os.path.join(root, "models", "boss")):
        with open(os.path.join(root, "models", "boss", m)) as f:
            print(m, len(json.load(f)["elements"]), "elements")
    print("parts:", [p["id"] for p in s["parts"]])
