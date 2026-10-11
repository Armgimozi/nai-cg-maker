"""
공허의 군주 (Void Sovereign) — 복셀 버전. boss id "void_sovereign".

작은 정육면체(복셀)를 쌓아 만든 공허 사신 군주. 1 복셀 = 1/8 블록 (모든 파트가 같은 크기의 큐브).
  - 몸 파트: wkit.part(vox=1.0) + rig scale 2.0          → 1 복셀 = 1 × 2 / 16 = 1/8 블록
  - 낫, 왕관: wkit.part(vox=0.5) + scale 4.0             → 1 복셀 = 0.5 × 4 / 16 = 1/8 블록 (회전 중심에서 6블록까지)

설계 좌표: 모든 파트를 '보스 좌표'(복셀, 발바닥 가운데가 원점, 앞 +Z, 위 +Y, 보스의 오른쪽 = -X)로 그리고
P 래퍼가 파트 피벗만큼 옮겨 준다.

색 설계 (보라 하나로 뭉치지 않게)
  - 로브: 밝기를 올린 보라 3단 (주름 골 / 주름 마루 / 위를 향한 단의 윗면 하이라이트), 'stone' 무늬로 큐브마다 다른 명도
  - 금속: 바랜 금(띠, 테, 왕관 띠, 버클) + 은(낫 금속, 어깨 가시 끝) — 참고 검처럼 보라 옆에 금/은
  - 뼈: 따뜻한 상아색 (해골이 시선의 중심), 낫 자루: 검붉은 나무
  - 빛: 기능마다 이어진 선 하나 (두건 테, 트임 가장자리, 밑단 끝), 눈은 하얗게 달아오른 심 + 자홍

키: 밑단 너덜 끝 1 → 허리 22 → 어깨 33 → 두건 꼭대기 49 (6.1블록), 떠 있는 왕관 띠 51~53, 앞 가시 끝 약 61.
낫: 자루 끝 -4 → 낫 머리 52, 날은 바깥(-X)으로 뻗어 아래로 휜다.
"""
import json
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, PACK)
import wkit  # noqa: E402
from wkit import Mat  # noqa: E402

BOSS = "void_sovereign"
MODULE = "vboss_void"
NAME_KO = "공허의 군주"
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
PREVIEW_DIR = os.path.join(HERE, "preview")
VPB = 8.0   # 블록당 복셀

# ─────────────────────────────── 재료 ───────────────────────────────
MATS = {
    # 로브: 골(robe) < 마루(robe_l) < 윗면 하이라이트(robe_hi). stone 무늬 = 큐브마다 명도가 크게 다름
    "robe":    Mat(["#1a1030", "#2a1a48", "#3a2660", "#4e3480"], "stone", seed=1),
    "robe_l":  Mat(["#261744", "#38255e", "#4c347a", "#644698"], "stone", seed=2),
    "robe_hi": Mat(["#3c2a62", "#523c80", "#6a529e", "#866cbc"], "stone", seed=13),
    "robe_in": Mat(["#040208", "#08040e", "#0d0718", "#140a22"], "stone", seed=3),
    "gold":    Mat(["#5a3e16", "#8c6a28", "#c49c42", "#f2d67c"], "metal", seed=4),
    "silver":  Mat(["#4e5264", "#7e8498", "#b0b6c8", "#e6eaf2"], "metal", seed=12),
    "obsid":   Mat(["#100c1a", "#1c162c", "#2a2242", "#3e345c"], "metal", seed=5),
    "obsid_l": Mat(["#2e2846", "#443c62", "#5c5480", "#7a74a2"], "metal", seed=14),
    "bone":    Mat(["#5e5040", "#a89878", "#d8ccac", "#f4ecd8"], "stone", seed=6),
    "bone_d":  Mat(["#3a3026", "#5e5040", "#7e6e56", "#a08e70"], "stone", seed=7),
    "shaft":   Mat(["#1c0a10", "#32141c", "#4a2029", "#622c38"], "wood", seed=8),
    "eye":     Mat(["#ff2ab0", "#ff5cc8", "#ff9ae0", "#ffd8f4"], "flat", glow=True, seed=9),
    "eye_c":   Mat(["#fff0fa", "#fff6fc", "#ffffff", "#ffffff"], "flat", glow=True, seed=15),
    "gem":     Mat(["#6a14d8", "#9a3cff", "#cc88ff", "#ffffff"], "gem", glow=True, seed=10),
    "gem_m":   Mat(["#b0107e", "#f02cb8", "#ff8ce4", "#ffffff"], "gem", glow=True, seed=11),
    # 움직이는 재료 (발광)
    "rune":    Mat(["#5a20d8", "#8a4cff", "#b88cff", "#efe0ff"], "pulse", glow=True, seed=21),
    "star":    Mat(["#05010c", "#0c0420", "#1a0838", "#2a1050"], "sparkle", glow=True, seed=22),
    "edge":    Mat(["#b060ff", "#d8a0ff", "#f2d8ff", "#ffffff"], "flow", glow=True, seed=23),
    "vblade":  Mat(["#1c0644", "#4210a0", "#8030e8", "#d090ff"], "flow", glow=True, seed=24),
    "fire_o":  Mat(["#4a0c9a", "#9a1ccc", "#e040d0", "#ff9ae8"], "fire", glow=True, seed=25),
    "fire_c":  Mat(["#e050d0", "#ff90e4", "#ffd8f6", "#ffffff"], "fire", glow=True, seed=26),
}


def mats(*names):
    return {n: MATS[n] for n in names}


# ─────────────────────────────── 파트 래퍼 ───────────────────────────────

class P:
    """보스 좌표(복셀)로 그리는 파트. pivot = 보스 좌표의 회전 중심."""

    def __init__(self, names, pivot, vox=1.0, size=None, seed=0):
        self.vox = vox
        self.reach = int(24 / vox)
        size = size or 2 * self.reach
        self.p = wkit.part(mats(*names), size=size, vox=vox, seed=seed)
        self.pv = tuple(float(v) for v in pivot)
        self.rng = random.Random(seed * 101 + 7)

    @property
    def X(self):
        return self.p._X + self.pv[0]

    @property
    def Y(self):
        return self.p._Y + self.pv[1]

    @property
    def Z(self):
        return self.p._Z + self.pv[2]

    def _w(self, fn):
        px, py, pz = self.pv
        return lambda X, Y, Z: fn(X + px, Y + py, Z + pz)

    @property
    def grid(self):
        return self.p.grid

    def mid(self, m):
        return self.p._id(m)

    def fill(self, fn, m):
        self.p.fill(self._w(fn), m)
        return self

    def surface(self):
        g = self.grid > 0
        inner = g.copy()
        inner[1:-1, 1:-1, 1:-1] = (g[1:-1, 1:-1, 1:-1] & g[2:, 1:-1, 1:-1] & g[:-2, 1:-1, 1:-1]
                                   & g[1:-1, 2:, 1:-1] & g[1:-1, :-2, 1:-1] & g[1:-1, 1:-1, 2:] & g[1:-1, 1:-1, :-2])
        inner[0, :, :] = inner[-1, :, :] = False
        inner[:, 0, :] = inner[:, -1, :] = False
        inner[:, :, 0] = inner[:, :, -1] = False
        return g & ~inner

    def open_to(self, axis, sign):
        """이웃 칸(axis 방향 sign 쪽)이 비어 있는 복셀."""
        g = self.grid > 0
        nb = np.zeros_like(g)
        sl_dst = [slice(None)] * 3
        sl_src = [slice(None)] * 3
        if sign > 0:
            sl_dst[axis], sl_src[axis] = slice(0, -1), slice(1, None)
        else:
            sl_dst[axis], sl_src[axis] = slice(1, None), slice(0, -1)
        nb[tuple(sl_dst)] = g[tuple(sl_src)]
        return g & ~nb

    def paint(self, fn, m, only=None, surf=False, mask=None):
        """이미 있는 복셀만 칠한다 (only: 이 재료들만, surf: 겉면 복셀만, mask: 추가 격자 조건)."""
        g = self.grid
        sel = np.asarray(fn(self.X, self.Y, self.Z), dtype=bool) & (g > 0)
        if only:
            sel &= np.isin(g, [self.mid(n) for n in only])
        if surf:
            sel &= self.surface()
        if mask is not None:
            sel &= mask
        g[sel] = self.mid(m)
        return self

    def toplight(self, pairs, fn=None):
        """위가 비어 있는 복셀(단의 윗면)을 한 단계 밝은 재료로: pairs = {어두운: 밝은}."""
        up = self.open_to(1, +1)
        g = self.grid
        sel_fn = np.ones_like(up) if fn is None else np.asarray(fn(self.X, self.Y, self.Z), dtype=bool)
        for a, b in pairs.items():
            g[up & sel_fn & (g == self.mid(a))] = self.mid(b)
        return self

    def clear(self, fn):
        self.p.clear(self._w(fn))
        return self

    def box(self, x0, x1, y0, y1, z0, z1, m):
        """칸 [x0,x1) x [y0,y1) x [z0,z1) (정수 경계) 를 채운다."""
        return self.fill(_inbox(x0, x1, y0, y1, z0, z1), m)

    def cube(self, x, y, z, m):
        """한 칸 (x, y, z 는 칸의 아래쪽 모서리)."""
        return self.box(x, x + 1, y, y + 1, z, z + 1, m)

    def pbox(self, x0, x1, y0, y1, z0, z1, m, only=None):
        return self.paint(_inbox(x0, x1, y0, y1, z0, z1), m, only)

    def unbox(self, x0, x1, y0, y1, z0, z1):
        return self.clear(_inbox(x0, x1, y0, y1, z0, z1))

    def tube(self, pts, r, m, rz=None):
        px, py, pz = self.pv
        self.p.tube([(a - px, b - py, c - pz) for a, b, c in pts], r, m, rz=rz)
        return self

    def ball(self, cx, cy, cz, rx, ry, rz, m):
        return self.fill(lambda X, Y, Z: ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2 <= 1, m)

    def path(self, pts, m, joints=None):
        """정수 칸 좌표를 면으로 이어지게(한 축씩) 잇는다. joints: 꺾이는 점에 쓸 재료."""
        cur = list(pts[0])
        self.cube(*cur, joints or m)
        for nxt in pts[1:]:
            for ax in (1, 0, 2):
                while cur[ax] != nxt[ax]:
                    cur[ax] += 1 if nxt[ax] > cur[ax] else -1
                    self.cube(*cur, m)
            if joints:
                self.cube(*cur, joints)
        return self

    def mirror(self):
        assert self.pv[0] == 0
        self.p.mirror()
        return self

    def build(self, part_name, root):
        return self.p.build(f"boss/{BOSS}_{part_name}", root)

    def scale(self):
        return round(2.0 / self.vox, 4)

    def offset(self):
        return [round(self.pv[0] / VPB, 4), round(self.pv[1] / VPB, 4), round(self.pv[2] / VPB, 4)]


def _inbox(x0, x1, y0, y1, z0, z1):
    return lambda X, Y, Z: (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (Z > z0) & (Z < z1)


def taper(r0, r1):
    return lambda t: r0 + (r1 - r0) * t


def _catmull(pts, n=200):
    """점들을 지나는 부드러운 곡선 (n 개 표본)."""
    P_ = np.array(pts, dtype=float)
    P_ = np.vstack([P_[0] * 2 - P_[1], P_, P_[-1] * 2 - P_[-2]])
    out = []
    segs = len(P_) - 3
    for i in range(n):
        u = i / (n - 1) * segs
        k = min(segs - 1, int(u))
        t = u - k
        p0, p1, p2, p3 = P_[k:k + 4]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.array(out)


def ribbon(p, pts, halfw, cz, layers):
    """
    XY 평면의 휜 띠 (낫날 등). pts: 가운데 선 (X, Y). halfw(t): 반폭.
    layers: [(재료 또는 None(비움), 조건(s, w, t) -> bool, 반두께 (숫자 또는 함수 t))] 순서대로 칠한다.
      s = 가운데 선에서 잰 '오른쪽 법선' 거리 (날이 -X 로 뻗으면 s > 0 이 아래쪽), w = 그 자리 반폭.
    """
    c = _catmull(pts, 260)
    tan = np.gradient(c, axis=0)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], axis=1)
    X, Y, Z = p.X, p.Y, p.Z
    lo = c.min(axis=0) - 8
    hi = c.max(axis=0) + 8
    sel = (X > lo[0]) & (X < hi[0]) & (Y > lo[1]) & (Y < hi[1])
    idx = np.argwhere(sel)
    xs, ys, zs = X[sel], Y[sel], Z[sel]
    best = np.full(xs.shape, 1e9)
    bi = np.zeros(xs.shape, dtype=int)
    for i in range(len(c)):
        d = (xs - c[i, 0]) ** 2 + (ys - c[i, 1]) ** 2
        m = d < best
        best[m] = d[m]
        bi[m] = i
    t = bi / (len(c) - 1)
    s = (xs - c[bi, 0]) * nrm[bi, 0] + (ys - c[bi, 1]) * nrm[bi, 1]
    along = (xs - c[bi, 0]) * tan[bi, 0] + (ys - c[bi, 1]) * tan[bi, 1]
    w = np.vectorize(halfw)(t)
    inside = (np.abs(s) <= w) & ~((bi == 0) & (along < -0.3)) & ~((bi == len(c) - 1) & (along > 0.3))
    for (m, cond, hz) in layers:
        th = np.vectorize(hz)(t) if callable(hz) else hz
        ok = inside & cond(s, w, t) & (np.abs(zs - cz) <= th)
        sub = idx[ok]
        p.grid[sub[:, 0], sub[:, 1], sub[:, 2]] = 0 if m is None else p.mid(m)


def superell(X, Z, hx, hzf, hzb, e=3.0):
    hz = np.where(Z >= 0, hzf, hzb)
    return (np.abs(X) / hx) ** e + (np.abs(Z) / hz) ** e <= 1.0


def ang01(X, Z, hx, hzf, hzb):
    """몸통 둘레 위치: 0 = 앞 가운데 → 1 = 뒤 가운데 (좌우 대칭, |X| 사용)."""
    hz = np.where(Z >= 0, hzf, hzb)
    return np.arctan2(np.abs(X) / hx, Z / hz) / math.pi


def fold_index(u, widths):
    cum = np.cumsum([0] + list(widths)) / float(sum(widths))
    return np.clip(np.searchsorted(cum, u, side="right") - 1, 0, len(widths) - 1)


# ─────────────────────────────── 로브 (아래) ───────────────────────────────
WAIST = (0, 22, 0)
HEM_TOP = 23.0
# 반 바퀴(앞 → 뒤)의 주름 폭 (단위: 둘레 비율). 폭이 2/3/4 로 섞여 바코드처럼 보이지 않게
ROBE_FOLDS = [3, 4, 3, 5, 3, 4, 4]
TATTERS = 4.5          # 반 바퀴의 너덜 자락 수 (한 바퀴 9개)
TATTER_DEPTH = [5, 4, 6, 5, 6]


def robe_dims(Y):
    Yq = np.floor((Y - 1) / 3) * 3 + 1.5          # 3칸 단 (계단식으로 퍼짐)
    t = np.clip((HEM_TOP - Yq) / (HEM_TOP - 1), 0, 1)
    hx = 6.2 + 5.6 * t ** 0.85
    hzf = 4.6 + 3.4 * t
    hzb = 4.6 + 5.4 * t ** 1.2
    return t, hx, hzf, hzb


def robe_hem(X, Z):
    """너덜 자락: 9개의 뾰족한 혀 (깊이 4~6칸). 앞 가운데와 뒤 가운데 사이."""
    u = ang01(X, Z, 11.8, 8.0, 10.0) * TATTERS
    i = np.floor(u).astype(int)
    f = u - i
    depth = np.array(TATTER_DEPTH)[np.clip(i, 0, len(TATTER_DEPTH) - 1)]
    tri = np.abs(2 * f - 1) ** 0.9            # 0 = 혀 끝, 1 = 혀 사이 홈
    return 1 + np.round(depth * tri)


def make_robe():
    names = ["robe", "robe_l", "robe_hi", "gold", "gem", "gem_m", "rune", "star"]
    p = P(names, WAIST, seed=1)

    def kfold(Y):
        t, *_ = robe_dims(Y)
        return 0.95 - 0.15 * t                   # 허리 0.95 → 밑단 0.8 (아래로 갈수록 깊은 골)

    def ridge(X, Y, Z):
        t, hx, hzf, hzb = robe_dims(Y)
        return fold_index(ang01(X, Z, hx, hzf, hzb), ROBE_FOLDS) % 2 == 0

    def body(X, Y, Z):
        t, hx, hzf, hzb = robe_dims(Y)
        k = np.where(ridge(X, Y, Z), 1.0, kfold(Y))
        return (Y < HEM_TOP) & (Y > robe_hem(X, Z)) & superell(X, Z, hx * k, hzf * k, hzb * k)

    p.fill(body, "robe")
    p.paint(ridge, "robe_l")
    # 금 띠 (밑단 위, 주름 골까지 메워 한 바퀴 이어진 띠, 한 칸 튀어나옴)
    def band(X, Y, Z):
        t, hx, hzf, hzb = robe_dims(Y)
        return (Y > 7) & (Y < 9) & superell(X, Z, hx + 0.6, hzf + 0.6, hzb + 0.6) & (Y > robe_hem(X, Z))
    p.fill(band, "gold")

    # 앞 트임: 아래로 넓어지는 틈. 3.5 칸 들어가 있고, 속은 거의 검은 밤하늘(드문 별이 반짝)
    def zf(X, Y):
        t, hx, hzf, hzb = robe_dims(Y)
        v = np.clip(1 - (np.abs(X) / hx) ** 3, 0, 1)
        return hzf * v ** (1 / 3)

    def opening(Y):
        t = np.clip((HEM_TOP - Y) / (HEM_TOP - 1), 0, 1)
        return 0.6 + 4.4 * t ** 1.1

    gap = lambda X, Y, Z: (Z > 0) & (np.abs(X) < opening(Y)) & (Y < HEM_TOP - 1)
    p.paint(lambda X, Y, Z: gap(X, Y, Z) & (Z > zf(X, Y) - 5.5), "star")
    p.clear(lambda X, Y, Z: gap(X, Y, Z) & (Z > zf(X, Y) - 3.5))
    # 단의 윗면 하이라이트 (마루 → 더 밝게, 골 → 마루색)
    p.toplight({"robe_l": "robe_hi"}, lambda X, Y, Z: Y < HEM_TOP - 1)
    # 트임 가장자리: 빛나는 선 하나 (벽 안쪽까지)
    p.paint(lambda X, Y, Z: (Z > 0) & (np.abs(X) >= opening(Y)) & (np.abs(X) < opening(Y) + 1.0)
            & (Z > zf(X, Y) - 3.5) & (Y < HEM_TOP - 1), "rune", surf=True)
    # 밑단 끝: 너덜 자락마다 빛나는 입술 한 줄 (겉껍질의 맨 아래 칸만)
    shell = lambda X, Y, Z: ~superell(X, Z, *[v - 1.6 for v in robe_dims(Y)[1:]])
    bottom = p.open_to(1, -1)
    lip = bottom.copy()
    lip[:, 1:, :] |= bottom[:, :-1, :]          # 맨 아래 칸 + 그 위 칸 → 계단이 끊기지 않는 선
    p.paint(lambda X, Y, Z: shell(X, Y, Z), "rune", mask=lip, only=["robe", "robe_l", "robe_hi", "star"])
    # 금 띠의 보석 (앞 양쪽, 옆)
    for ua in (0.5,):
        p.paint(lambda X, Y, Z, ua=ua: (np.abs(ang01(X, Z, 12.4, 8.6, 10.6) - ua) < 0.035), "gem",
                only=["gold"], surf=True)
    # 뒤의 군주 문장: 금 초승달 + 가운데 자홍 공허의 눈 (등 쪽 겉면)
    cy = 15.5

    def crescent(X, Y):
        r1 = np.hypot(X, (Y - cy) * 1.0)
        r2 = np.hypot(X, (Y - cy - 2.2) * 1.0)
        return (r1 < 5.2) & (r2 >= 4.2)
    back = lambda X, Y, Z: Z < -3
    p.paint(lambda X, Y, Z: back(X, Y, Z) & crescent(X, Y), "gold", surf=True)
    p.paint(lambda X, Y, Z: back(X, Y, Z) & (np.abs(X) < 1) & (np.abs(Y - (cy + 1.0)) < 1), "gem_m", surf=True)
    p.mirror()
    return p


# ─────────────────────────────── 몸통 + 두건 ───────────────────────────────
CHEST = (0, 28, 0)
MANTLE_FOLDS = [3, 2, 4, 3, 3, 2, 4]


def make_torso():
    names = ["robe", "robe_l", "robe_hi", "robe_in", "gold", "silver", "obsid", "bone", "bone_d",
             "eye", "eye_c", "gem", "gem_m", "rune"]
    p = P(names, CHEST, seed=2)

    def tdims(Y):
        t = np.clip((np.floor(Y / 2) * 2 + 1 - 21) / 13, 0, 1)
        hx = 6.0 + 2.2 * t ** 0.7
        return hx, 4.4 + 0.8 * t, 4.4 + 1.2 * t

    def body(X, Y, Z):
        hx, hzf, hzb = tdims(Y)
        return (Y > 20) & (Y < 34) & superell(X, Z, hx, hzf, hzb)

    p.fill(body, "robe")

    # 가슴 트임: 위로 넓어지는 V, 그 속에 상아색 갈비뼈와 빛나는 공허 심장
    def zf(X, Y):
        hx, hzf, hzb = tdims(Y)
        v = np.clip(1 - (np.abs(X) / hx) ** 3, 0, 1)
        return hzf * v ** (1 / 3)

    vopen = lambda Y: 1.2 + (Y - 24) * 0.42
    gap = lambda X, Y, Z: (Z > 0) & (Y > 24) & (Y < 33) & (np.abs(X) < vopen(Y))
    p.paint(lambda X, Y, Z: gap(X, Y, Z) & (Z > zf(X, Y) - 3.5), "robe_in")
    p.clear(lambda X, Y, Z: gap(X, Y, Z) & (Z > zf(X, Y) - 1.5))
    for y in (25, 27, 29, 31):
        p.fill(lambda X, Y, Z, y=y: gap(X, Y, Z) & (Y > y) & (Y < y + 1) & (Z > zf(X, Y) - 2.5)
               & (Z < zf(X, Y) - 1.0) & (np.abs(X) > 0.5), "bone")
    p.fill(lambda X, Y, Z: gap(X, Y, Z) & (np.abs(X) < 1) & (Y > 24) & (Y < 32) & (Z > zf(X, Y) - 2.5)
           & (Z < zf(X, Y) - 0.6), "bone_d")
    p.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Y - 28.5) < 2.1) & (Z > 2) & (Z < zf(X, Y) - 0.4), "gem_m")
    # V 깃: 금 테 (빛나지 않는 금속 선)
    p.paint(lambda X, Y, Z: (Z > 0) & (Y > 24) & (Y < 33) & (np.abs(X) >= vopen(Y)) & (np.abs(X) < vopen(Y) + 1.05),
            "gold", surf=True)

    # 허리띠 + 은 버클 + 보라 보석
    p.fill(lambda X, Y, Z: (Y > 20) & (Y < 24) & superell(X, Z, 7.3, 5.6, 5.6), "obsid")
    p.fill(lambda X, Y, Z: (Y > 21) & (Y < 23) & superell(X, Z, 7.6, 5.9, 5.9), "gold")
    p.box(-2, 2, 20, 24, 4, 7, "silver")
    p.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Y - 22) < 1.6) & (Z > 4) & (Z < 7.5), "gem")

    # 어깨 망토 두 겹: 주름이 폭 2/3/4 로 섞이고, 마루가 아래로 더 늘어진 끝 (작은 톱니가 아니라 주름마다 한 칸 차)
    def mantle(y0, y1, hx0, hx1, hz0, hz1, kd):
        def dims(Y):
            tt = np.clip((y1 - Y) / (y1 - y0), 0, 1)
            return hx1 + (hx0 - hx1) * tt, hz1 + (hz0 - hz1) * tt

        def is_ridge(X, Y, Z):
            hx, hz = dims(Y)
            return fold_index(ang01(X, Z, hx, hz, hz + 0.6), MANTLE_FOLDS) % 2 == 0

        def fn(X, Y, Z):
            hx, hz = dims(Y)
            rd = is_ridge(X, Y, Z)
            k = np.where(rd, 1.0, kd)
            bot = y0 - np.where(rd, 2, 0)
            return (Y > bot) & (Y < y1) & superell(X, Z, hx * k, hz * k, hz * k + 0.6)
        return fn, is_ridge

    m1, r1 = mantle(28, 33, 12.0, 9.0, 7.6, 6.2, 0.9)
    m2, r2 = mantle(31, 36, 10.2, 7.0, 7.0, 5.6, 0.9)
    vcut = lambda X, Y, Z: (Z > 0) & (Y > 24) & (Y < 33.5) & (np.abs(X) < vopen(Y) + 0.2)
    p.fill(lambda X, Y, Z: m1(X, Y, Z) & ~vcut(X, Y, Z), "robe")
    p.paint(lambda X, Y, Z: m1(X, Y, Z) & r1(X, Y, Z) & ~vcut(X, Y, Z), "robe_l", only=["robe"])
    # 아래 망토 끝: 금 테 한 줄 (겉면)
    m1_lip = p.open_to(1, -1)
    p.paint(lambda X, Y, Z: m1(X, Y, Z) & (Y < 31) & ~vcut(X, Y, Z), "gold", mask=m1_lip, surf=True,
            only=["robe", "robe_l"])
    p.fill(lambda X, Y, Z: m2(X, Y, Z) & ~vcut(X, Y, Z), "robe_l")
    p.paint(lambda X, Y, Z: m2(X, Y, Z) & ~r2(X, Y, Z) & ~vcut(X, Y, Z), "robe", only=["robe_l"])

    # ── 두건 ──
    HY0, HPEAK = 33, 49

    def hood(X, Y, Z):
        # 41 까지는 통, 그 위로 2칸 단마다 좁아지며 뒤로 물러난다 (꼭대기 49)
        u = np.clip((np.floor(Y / 2) * 2 + 1 - 41) / (HPEAK - 41), 0, 1)
        sh = 1 - 0.62 * u ** 1.5
        zc = -u * 3.0
        return (Y > HY0) & (Y < HPEAK) & superell(X, Z - zc, 8.0 * sh, 7.4 * sh + 0.4, 7.0 * sh, 3.0)

    p.fill(hood, "robe")
    # 두건의 큰 주름 셋 (양옆, 뒤 가운데): 반 칸 튀어나온 밝은 띠
    def hood_fold(X, Y, Z):
        a = ang01(X, Z, 8.0, 7.8, 7.0)
        return (np.abs(a - 0.55) < 0.07) | (a > 0.9)
    p.fill(lambda X, Y, Z: hood_fold(X, Y, Z) & (Y > HY0) & (Y < 45) & (Y > 35)
           & superell(X, Z, 8.6, 8.0, 7.6), "robe_l")
    # 두건 끝자락(리리파이프): 꼭대기에서 뒤로 7칸, 아래로 늘어진다
    p.tube([(0, 47.5, -3), (0, 48.5, -6.5), (0, 47, -10), (0, 43.5, -12)], taper(2.4, 0.8), "robe")
    p.paint(lambda X, Y, Z: (Z < -5) & (Y > 42) & (np.abs(X) < 0.9), "robe_l")
    # 두건 입구 (깊은 그림자)
    arch = lambda X, Y: (np.abs(X) < 6.2) & (Y > 34) & (Y < 46.5 - (np.abs(X) / 6.2) ** 2 * 3.0)
    p.fill(lambda X, Y, Z: arch(X + np.sign(X) * 0.9, Y - 0.6) & (Y > 34) & (Z > -3.5) & (Z < 6), "robe_in")
    p.clear(lambda X, Y, Z: arch(X, Y) & (Z > -2.5))
    p.toplight({"robe_l": "robe_hi"}, lambda X, Y, Z: (Y > 26))

    # ── 해골 얼굴 (상아색). 앞면 Z = SZ ──
    SZ = 3
    rows = {44: 3, 43: 4, 42: 5, 41: 5, 40: 5, 39: 5, 38: 5, 37: 4}   # 행 → 반폭 (둥근 머리뼈)
    for y, hw in rows.items():
        p.box(-hw, hw, y, y + 1, -3, SZ, "bone")
    p.box(-4, 4, 37, 38, -3, SZ, "bone")
    # 눈구멍: 2칸 깊이, 그 안 1칸 뒤에 눈 (하얀 심 + 자홍)
    for s in (-1, 1):
        x0, x1 = (1, 4) if s > 0 else (-4, -1)
        p.unbox(x0, x1, 39, 42, SZ - 2, SZ + 1)
        p.box(x0, x1, 39, 42, SZ - 3, SZ - 2, "robe_in")
        ex0 = 1 if s > 0 else -3
        p.box(ex0, ex0 + 2, 39, 41, SZ - 2, SZ - 1, "eye")
        cx = 1 if s > 0 else -2                      # 하얀 심: 가운데 쪽 위
        p.cube(cx, 40, SZ - 2, "eye_c")
        # 찡그린 눈썹: 가운데 쪽 위 칸을 눈구멍 안으로 내린다
        bx = 1 if s > 0 else -2
        p.box(bx, bx + 1, 41, 42, SZ - 2, SZ, "bone_d")
    # 광대 턱: 한 칸 앞으로 나온 선반
    for s in (-1, 1):
        x0, x1 = (2, 5) if s > 0 else (-5, -2)
        p.box(x0, x1, 38, 39, SZ, SZ + 1, "bone")
    # 코 (어두운 세모 구멍)
    p.unbox(-1, 1, 37, 39, SZ - 2, SZ + 1)
    p.box(-1, 1, 37, 39, SZ - 3, SZ - 2, "robe_in")
    p.box(-1, 1, 38, 39, SZ - 2, SZ - 1, "bone_d")
    # 윗니 셋 (2칸 폭) + 사이의 1칸 깊이 어두운 틈
    p.box(-4, 4, 35, 37, -3, SZ, "bone")
    for gx in (-2, 1):
        p.box(gx, gx + 1, 35, 37, SZ - 1, SZ, "robe_in")
    p.box(-4, 4, 35, 36, SZ - 1, SZ, "bone_d")       # 이 끝 그림자
    for gx in (-2, 1):
        p.box(gx, gx + 1, 35, 36, SZ - 1, SZ, "robe_in")
    # 좁은 아래턱 (6칸, 한 칸 뒤)
    p.box(-3, 3, 33, 35, -3, SZ - 1, "bone_d")
    p.box(-2, 2, 33, 34, SZ - 2, SZ - 1, "bone")

    # 두건 앞 테: 얼굴을 두른 빛 선 하나
    def grow(f, n):
        return lambda X, Y: f(X - n, Y) | f(X + n, Y) | f(X, Y - n) | f(X - n, Y - n) | f(X + n, Y - n)
    rim1 = lambda X, Y: grow(arch, 1)(X, Y) & ~arch(X, Y)
    p.paint(lambda X, Y, Z: (Z > 3.5) & rim1(X, Y), "rune", surf=True)
    # 목의 금 걸쇠 (망토를 여미는 고리)
    for s in (-1, 1):
        p.box(s * 3.5 - 1.5, s * 3.5 + 1.5, 32, 35, 4, 7, "gold")
    return p


# ─────────────────────────────── 왕관 ───────────────────────────────
CROWN_Y = 51.0          # 띠 아래쪽
CROWN_R = 7.5


def make_crown():
    """두건 위에 떠 있는 검은 가시 왕관 (후광처럼 넓게). 피벗 = 가슴 (몸통이 기울면 같이 기운다). vox 0.5 × scale 4."""
    names = ["obsid", "obsid_l", "gold", "gem"]
    p = P(names, CHEST, vox=0.5, size=96, seed=3)
    R, CY = CROWN_R, CROWN_Y
    ring = lambda X, Z, r0, r1: (np.hypot(X, Z) < r1) & (np.hypot(X, Z) >= r0)
    # 얇은 금 띠 2줄 + 아래 흑요 선
    p.fill(lambda X, Y, Z: ring(X, Z, R - 1.0, R + 1.0) & (Y > CY) & (Y < CY + 2), "gold")
    p.fill(lambda X, Y, Z: ring(X, Z, R - 0.8, R + 0.8) & (Y > CY - 1) & (Y < CY), "obsid")

    # 가시: 3x3 → 2x2 → 1x1 로 가늘어지며 한 단에 0.6칸씩 바깥으로 기울고, 끝은 바깥으로 갈고리
    def thorn(ang, h):
        a = math.radians(ang)
        dx, dz = math.sin(a), math.cos(a)
        prev = None
        for i in range(h):
            t = i / h
            w = 3 if t < 0.34 else 2 if t < 0.67 else 1
            rr = R + 0.55 * i
            x0 = math.floor(dx * rr - w / 2 + 0.5)
            z0 = math.floor(dz * rr - w / 2 + 0.5)
            y = CY + 2 + i
            p.box(x0, x0 + w, y, y + 1, z0, z0 + w, "obsid")
            if w == 1 and prev is not None and prev != (x0, z0):
                # 가는 끝이 비스듬히 끊기지 않게 아래 칸 자리도 채운다 (면으로 이어진 계단)
                p.box(prev[0], prev[0] + 1, y, y + 1, prev[1], prev[1] + 1, "obsid")
            prev = (x0, z0) if w == 1 else (math.floor(dx * rr), math.floor(dz * rr))
        # 갈고리: 끝 칸 위에서 바깥(주된 축)으로 한 칸 꺾인다
        ox, oz = (int(math.copysign(1, dx)), 0) if abs(dx) >= abs(dz) else (0, int(math.copysign(1, dz)))
        p.box(prev[0] + ox, prev[0] + ox + 1, CY + 1 + h, CY + 2 + h, prev[1] + oz, prev[1] + oz + 1, "obsid_l")
        p.box(prev[0], prev[0] + 1, CY + 1 + h, CY + 2 + h, prev[1], prev[1] + 1, "obsid_l")

    for ang, h in ((0, 8), (45, 6), (-45, 6), (90, 6), (-90, 6), (135, 4), (-135, 4), (180, 5)):
        thorn(ang, h)
    p.toplight({"obsid": "obsid_l"})
    # 띠의 보석: 가시 사이마다 빛나는 보라 (앞은 크게)
    for ang in (22.5, -22.5, 67.5, -67.5, 112.5, -112.5, 157.5, -157.5):
        a = math.radians(ang)
        gx, gz = math.sin(a) * (R + 0.6), math.cos(a) * (R + 0.6)
        p.fill(lambda X, Y, Z, gx=gx, gz=gz: (np.hypot(X - gx, Z - gz) < 1.0) & (Y > CY) & (Y < CY + 2), "gem")
    p.fill(lambda X, Y, Z: (np.abs(X) < 1.0) & (Y > CY - 1) & (Y < CY + 2) & (Z > R) & (Z < R + 1.6), "gem")
    return p


# ─────────────────────────────── 팔 ───────────────────────────────
SH_Y = 33
R_SHOULDER = (-10, SH_Y, 0)
L_SHOULDER = (10, SH_Y, 0)
SHAFT_X0, SHAFT_X1, SHAFT_Z0, SHAFT_Z1 = -19, -16, 8, 11   # 낫 자루 (3x3)
SHAFT_CX, SHAFT_CZ = -17.5, 9.5


def sleeve(p, s, elbow, wrist, r_end=4.6):
    """s = -1 오른쪽 / +1 왼쪽. 어깨 → 팔꿈치 (좁은 소매) → 손목 (넓어지는 종 모양 소매) + 금 소맷부리."""
    sh = (s * 10.5, 32.0, 0.0)
    p.tube([sh, elbow], taper(3.3, 3.0), "robe")
    p.tube([elbow, wrist], taper(3.0, r_end), "robe")
    w = np.array(wrist, dtype=float)
    e = np.array(elbow, dtype=float)
    d = (w - e) / np.linalg.norm(w - e)

    def along(X, Y, Z):
        return (X - w[0]) * d[0] + (Y - w[1]) * d[1] + (Z - w[2]) * d[2]

    def rad2(X, Y, Z):
        a = along(X, Y, Z)
        return ((X - w[0]) - a * d[0]) ** 2 + ((Y - w[1]) - a * d[1]) ** 2 + ((Z - w[2]) - a * d[2]) ** 2

    # 소매 주름: 팔을 감는 넓은 띠 두 개 (줄무늬 아님)
    p.paint(lambda X, Y, Z: (np.abs(along(X, Y, Z) + 5.5) < 1.0) | (np.abs(along(X, Y, Z) + 9.0) < 0.8),
            "robe_l", only=["robe"])
    p.paint(lambda X, Y, Z: along(X, Y, Z) > -1.1, "gold", surf=True)
    p.clear(lambda X, Y, Z: (along(X, Y, Z) > -1.5) & (rad2(X, Y, Z) < (r_end - 1.4) ** 2))
    p.fill(lambda X, Y, Z: (along(X, Y, Z) > -2.6) & (along(X, Y, Z) <= -1.5) & (rad2(X, Y, Z) < (r_end - 1.4) ** 2),
           "robe_in")
    p.toplight({"robe": "robe_l", "robe_l": "robe_hi"})
    pauldron(p, s)


def pauldron(p, s):
    """어깨 받이 (흑요 돔 + 금 테) 와 큰 가시 둘. 팔과 같이 움직인다. 윗면은 밝은 흑요, 끝은 은."""
    p.fill(lambda X, Y, Z: (((X - s * 10.5) / 4.6) ** 2 + ((Y - 33.5) / 3.2) ** 2 + (Z / 4.8) ** 2 <= 1)
           & (Y > 32), "obsid")
    p.fill(lambda X, Y, Z: (((X - s * 10.5) / 5.0) ** 2 + (Z / 5.2) ** 2 <= 1) & (Y > 32) & (Y < 33), "gold")
    for (pts, r0, r1_) in ((((9.5, 35, -1), (12.5, 41, -3), (14, 46, -6.5)), 2.6, 0.7),
                           (((12.5, 34, 0), (16, 36.5, -1.5), (19, 37, -4)), 2.0, 0.6)):
        P3 = [(s * a, b, c) for a, b, c in pts]
        p.tube(P3, taper(r0, r1_), "obsid")
        tip = P3[-1]
        p.paint(lambda X, Y, Z, tip=tip: np.hypot(np.hypot(X - tip[0], Y - tip[1]), Z - tip[2]) < 2.2,
                "silver", only=["obsid"])
    p.toplight({"obsid": "obsid_l"})


def make_right_arm():
    names = ["robe", "robe_l", "robe_hi", "robe_in", "gold", "silver", "obsid", "obsid_l", "bone", "bone_d"]
    p = P(names, R_SHOULDER, seed=4)
    sleeve(p, -1, (-14, 26, 0.5), (-16.5, 23, 5.0))
    # 손목뼈 두 가닥 (소맷부리 아래로 보임) → 자루를 감싸 쥔 손
    p.path([(-17, 22, 5), (-17, 21, 7)], "bone_d")
    p.path([(-16, 22, 5), (-16, 21, 6)], "bone_d")
    x0, x1, z0, z1 = SHAFT_X0, SHAFT_X1, SHAFT_Z0, SHAFT_Z1
    p.box(x0, x1, 17, 22, z0 - 1, z0, "bone")             # 손바닥 (자루 뒤)
    for y in (17, 19):                                   # 손가락 두 개: 바깥 → 앞 → 안쪽으로 감싼다
        p.box(x0 - 1, x0, y, y + 2, z0 - 1, z1, "bone")
        p.box(x0 - 1, x1, y, y + 1, z1, z1 + 1, "bone")
        p.box(x0 - 1, x1, y + 1, y + 2, z1, z1 + 1, "bone_d")
        p.box(x1, x1 + 1, y, y + 1, z0 + 1, z1 + 1, "bone_d")   # 손가락 끝 (몸 쪽)
    p.box(x1, x1 + 1, 21, 23, z0 - 1, z1, "bone")        # 엄지: 몸 쪽에서 위로 감음
    p.box(x0, x1, 22, 23, z1, z1 + 1, "bone_d")
    return p


def make_left_arm():
    names = ["robe", "robe_l", "robe_hi", "robe_in", "gold", "silver", "obsid", "obsid_l", "bone", "bone_d",
             "fire_o", "fire_c"]
    p = P(names, L_SHOULDER, seed=5)
    # 팔을 가슴 높이로 들어 앞으로 내민다
    sleeve(p, 1, (14.5, 25.5, 1.5), (15.5, 27.5, 8.0), r_end=4.4)
    # 손목뼈 두 가닥
    p.path([(14, 26, 8), (14, 26, 11)], "bone_d")
    p.path([(16, 26, 8), (16, 26, 11)], "bone_d")
    # 손바닥 (위를 향함): x 13..17, z 11..15, 높이 26
    p.box(13, 17, 25, 26, 11, 15, "bone")
    p.box(14, 16, 24, 25, 12, 14, "bone_d")
    # 길게 벌어진 갈고리 손가락 4개 (마디 2개, 관절은 어두운 뼈): 바깥 위로 → 불꽃 쪽으로 굽음
    corners = ((16, 14, 1, 1), (13, 14, -1, 1), (16, 11, 1, -1), (13, 11, -1, -1))
    for (bx, bz, dx, dz) in corners:
        pts = [(bx + dx, 26, bz + dz), (bx + 2 * dx, 28, bz + 2 * dz), (bx + 2 * dx, 31, bz + dz),
               (bx + dx, 33, bz)]
        p.path(pts[:2], "bone")
        p.path(pts[1:3], "bone")
        p.path(pts[2:], "bone")
        p.cube(*pts[1], "bone_d")
        p.cube(*pts[2], "bone_d")
    # 공허 불꽃 (12칸): 엇갈린 계단식 혀, 바깥은 보라-자홍, 속은 하얗게 달아오름
    fo = [
        (13, 17, 26, 29, 11, 15),
        (13, 16, 29, 32, 12, 15),
        (15, 17, 29, 31, 11, 13),
        (14, 16, 32, 35, 13, 15),
        (16, 17, 31, 33, 11, 12),
        (13, 14, 32, 34, 12, 13),
        (14, 15, 35, 38, 13, 14),
        (15, 16, 36, 37, 14, 15),
        (15, 16, 33, 34, 11, 12),
    ]
    for b in fo:
        p.box(*b, "fire_o")
    fc = [(14, 16, 26, 31, 12, 15), (14, 15, 31, 34, 13, 15), (14, 15, 34, 36, 14, 15), (16, 17, 27, 29, 14, 15)]
    for b in fc:
        p.box(*b, "fire_c")
    return p


# ─────────────────────────────── 낫 ───────────────────────────────

def make_scythe():
    names = ["shaft", "obsid", "silver", "gold", "bone", "bone_d", "gem", "eye", "rune", "vblade", "edge"]
    p = P(names, R_SHOULDER, vox=0.5, size=96, seed=6)
    x0, x1, z0, z1 = SHAFT_X0, SHAFT_X1, SHAFT_Z0, SHAFT_Z1
    cx, cz = SHAFT_CX, SHAFT_CZ
    TOP = 52
    # 자루 3x3: 검붉은 나무. 금속 띠와 빛 고리는 세 곳에만 (머리, 손잡이, 발)
    p.box(x0, x1, 1, TOP, z0, z1, "shaft")

    def band(y0, y1, m, grow=1):
        p.box(x0 - grow, x1 + grow, y0, y1, z0 - grow, z1 + grow, m)

    band(44, 47, "silver")
    p.box(x0 - 1, x1 + 1, 45, 46, z0 - 1, z1 + 1, "rune")
    band(40, 41, "gold")
    band(37, 38, "gold")
    band(14, 16, "silver")                                  # 손잡이 아래
    p.box(x0 - 1, x1 + 1, 14, 15, z0 - 1, z1 + 1, "rune")
    band(24, 25, "gold")                                    # 손잡이 위
    band(1, 4, "silver")                                    # 발
    p.box(x0 - 1, x1 + 1, 2, 3, z0 - 1, z1 + 1, "rune")
    # 발 끝 흑요 창끝 (계단식)
    for i, w in enumerate((3, 3, 1, 1, 1)):
        o = (3 - w) / 2
        p.box(x0 + o, x0 + o + w, 0 - i, 1 - i, z0 + o, z0 + o + w, "obsid")
    # 낫 머리: 은 받침 + 흑요 테 + 상아 해골 + 보석
    p.box(x0 - 1, x1 + 1, TOP - 3, TOP + 3, z0 - 1, z1 + 1, "silver")
    p.box(x0 - 2, x1 + 2, TOP - 1, TOP + 1, z0 - 2, z1 + 2, "obsid")
    p.box(x0 - 1, x1 + 1, TOP + 3, TOP + 8, z0 - 1, z1 + 1, "bone")
    p.box(x0 - 1, x1 + 1, TOP + 3, TOP + 4, z0 - 1, z1 + 1, "bone_d")
    p.box(x0, x0 + 1, TOP + 5, TOP + 7, z1, z1 + 1, "eye")
    p.box(x1 - 1, x1, TOP + 5, TOP + 7, z1, z1 + 1, "eye")
    p.box(x0 + 1, x1 - 1, TOP + 4, TOP + 5, z1, z1 + 1, "bone_d")
    p.box(x0, x1, TOP - 2, TOP + 1, z1 + 1, z1 + 2, "gem")
    p.box(x0, x1, TOP - 2, TOP + 1, z0 - 2, z0 - 1, "gem")
    # 등 쪽 가시 (몸 쪽으로 뒤로 휜 갈고리)
    p.tube([(x1 + 1, TOP + 1, cz), (cx + 6, TOP + 2.5, cz), (cx + 9, TOP + 6, cz)], taper(1.6, 0.7), "obsid")
    p.paint(lambda X, Y, Z: (X > cx + 7.5), "silver", only=["obsid"])

    # 날: 위 등(흑요 + 은 줄) → 빛나는 공허 몸통 → 아래 오목한 쪽이 날카로운 빛 날
    pts = [(cx - 1, TOP + 1.0), (cx - 9, TOP + 4.5), (cx - 18, TOP + 4.6), (cx - 26, TOP + 1.8),
           (cx - 32, TOP - 4.0), (cx - 35, TOP - 11.5)]

    def halfw(t):
        if t < 0.7:
            return 4.8 - 2.6 * (t / 0.7)            # 뒤꿈치 약 10칸 폭 → 70% 지점 4칸 폭
        return 0.5 + 1.7 * (1 - t) / 0.3

    spine = lambda s, w, t: s < -(w - 1.3)
    ribbon(p, pts, halfw, cz, [
        ("vblade", lambda s, w, t: np.ones_like(s, dtype=bool), lambda t: 1.0 if t < 0.85 else 0.5),
        ("obsid", spine, lambda t: 2.0 if t < 0.6 else 1.0 if t < 0.9 else 0.5),
        ("silver", lambda s, w, t: (s < -(w - 0.5)) & (t < 0.92), lambda t: 1.0 if t < 0.6 else 0.5),
        ("edge", lambda s, w, t: s > w - 1.2, 0.5),
        ("rune", lambda s, w, t: (np.abs(s + 0.6) < 0.5) & (t > 0.1) & (t < 0.75), 1.0),
        # 뒤꿈치의 홈 (턱 수염처럼 날이 한 번 꺾인다)
        (None, lambda s, w, t: (t > 0.06) & (t < 0.13) & (s > w - 2.4), 3.0),
    ])
    return p


# ─────────────────────────────── 공허 구슬 ───────────────────────────────

def make_orb():
    names = ["gem_m", "eye", "star"]
    p = P(names, (0, 0, 0), seed=7)
    # 사건의 지평선: 거의 검은(드문 별이 반짝이는) 구 + 자홍으로 빛나는 적도 띠, 띠는 한 칸 밖으로 나온 얇은 테로 끝난다
    p.ball(0, 0, 0, 3.6, 3.6, 3.6, "star")
    tilt = lambda X, Y: Y - 0.3 * X
    p.paint(lambda X, Y, Z: np.abs(tilt(X, Y)) < 1.0, "gem_m", surf=True)
    p.fill(lambda X, Y, Z: (tilt(X, Y) >= -0.5) & (tilt(X, Y) < 0.5) & (np.hypot(X, Z) >= 3.0)
           & (np.hypot(X, Z) < 4.9), "gem_m")
    p.paint(lambda X, Y, Z: (tilt(X, Y) >= -0.5) & (tilt(X, Y) < 0.5) & (np.hypot(X, Z) >= 4.0), "eye")
    return p


# ─────────────────────────────── 조립 ───────────────────────────────
BOB = {"type": "bob", "amplitude": 0.08, "period": 70, "phase": 0.0}
TORSO_SWAY = {"type": "sway", "axis": "x", "angle": 2, "period": 70, "phase": 0.5}
TORSO_SWING = {"type": "swing", "axis": "x", "angle": 10, "ticks": 16}
ORBIT_R = 3.7


def build(assets_root):
    """모든 파트 모델을 쓰고 rig spec 을 돌려준다."""
    made = {
        "robe_lower": make_robe(), "torso_hood": make_torso(), "crown": make_crown(),
        "right_arm": make_right_arm(), "scythe": make_scythe(), "left_arm": make_left_arm(), "orb": make_orb(),
    }
    models = {k: v.build(k, assets_root) for k, v in made.items()}

    def entry(pid, part, anims, rot=(0, 0, 0), frame="body", offset=None):
        pp = made[part]
        return {"id": pid, "model": f"augsky:boss/{BOSS}_{part}",
                "offset": offset if offset is not None else pp.offset(), "scale": pp.scale(),
                "rotation": list(rot), "frame": frame, "anims": anims}

    arm_r = [dict(BOB), {"type": "sway", "axis": "x", "angle": 4, "period": 70, "phase": 0.1},
             {"type": "swing", "axis": "y", "angle": 75, "ticks": 16},
             {"type": "swing", "axis": "x", "angle": -30, "ticks": 16}]
    arm_l = [dict(BOB), {"type": "sway", "axis": "x", "angle": 5, "period": 70, "phase": 0.6},
             {"type": "swing", "axis": "x", "angle": -45, "ticks": 14}]
    parts = [
        entry("robe_lower", "robe_lower", [dict(BOB), {"type": "sway", "axis": "x", "angle": 4, "period": 70, "phase": 0.25},
                                           {"type": "sway", "axis": "z", "angle": 2.5, "period": 110, "phase": 0.0}]),
        entry("torso_hood", "torso_hood", [dict(BOB), dict(TORSO_SWAY), dict(TORSO_SWING)]),
        # 왕관은 가슴 피벗: 몸통과 같이 기울고(sway, swing), 그 위에서 천천히 돌며 떠오른다 (spin 이 맨 뒤 = 자기 축)
        entry("crown", "crown", [{"type": "bob", "amplitude": 0.12, "period": 50, "phase": 0.3},
                                 dict(TORSO_SWAY), dict(TORSO_SWING),
                                 {"type": "spin", "axis": "y", "speed": 1.5}]),
        entry("right_arm", "right_arm", arm_r),
        entry("scythe", "scythe", [dict(a) for a in arm_r]),
        entry("left_arm", "left_arm", arm_l),
    ]
    for i, ph in enumerate((0.0, 120.0, 240.0)):
        parts.append({"id": f"orb_{i + 1}", "model": f"augsky:boss/{BOSS}_orb", "offset": [0.0, 0.0, 0.0],
                      "scale": 2.0, "rotation": [0, 0, 0], "frame": "world",
                      "anims": [{"type": "orbit", "radius": ORBIT_R, "speed": 2.4, "phase": ph, "height": 4.2},
                                {"type": "spin", "axis": "y", "speed": 5.0},
                                {"type": "bob", "amplitude": 0.3, "period": 46, "phase": i / 3}]})
    spec = {
        "boss": BOSS,
        "parts": parts,
        "notes": ("공허의 군주 복셀 버전. 1 복셀 = 1/8 블록: 몸 파트 vox 1.0 × scale 2, 낫·왕관 vox 0.5 × scale 4 "
                  "(큐브 크기 같음). 키: 두건 꼭대기 약 6.1블록, 떠 있는 왕관 띠 약 6.4블록(앞 가시 끝 약 7.6블록), 낫 머리 약 7.5블록. "
                  "로브 밑단 폭 약 3블록(히트박스 1.68 을 덮음). 보스 오른손 = -X (낫), 왼손 = +X (가슴 높이의 공허 불꽃), 앞 = +Z. "
                  "포즈는 모델에 구워 넣어 rotation 은 0. scythe 는 right_arm 과 같은 피벗(오른 어깨)·같은 anims 라야 손에 붙어 있다. "
                  "crown 은 torso_hood 와 같은 가슴 피벗·같은 sway/swing 이라 공격 때 몸통과 함께 앞으로 기울고, spin(마지막)은 자기 세로축. "
                  "공격 swing: 낫 y +75 (바깥에서 앞으로 크게 휘두름) + x -30, 몸통·왕관 x +10, 왼팔 x -45 (불꽃을 내밂). "
                  "orb 3개는 같은 모델, frame=world orbit 반지름 3.7 (낫 자루·불꽃과 겹치지 않음). "
                  "발광: 눈(하얀 심+자홍), 두건 테·트임 가장자리·밑단 끝(rune pulse), 보석, 낫날(flow), 불꽃(fire), 트임 속 별(sparkle)."),
    }
    spec["_counts"] = {k: len(m.elements) for k, m in models.items()}
    spec["_made"] = made
    with open(os.path.join(HERE, MODULE + ".rig.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in spec.items() if not k.startswith("_")}, f, ensure_ascii=False, indent=2)
    spec["_models"] = models
    return spec


# ─────────────────────────────── 미리보기 ───────────────────────────────
SKY = (126, 170, 232, 255)     # 스카이블럭 낮 하늘에서도 큐브가 읽히는지


def zrender(parts, size=512, yaw=-35, pitch=25, **kw):
    """mc3d.render 와 같지만 겹친 면의 앞뒤 순서를 바로잡는다 (깊이만 뒤집는 반사를 곱해 그리는 순서를 바르게)."""
    import mc3d
    V = mc3d._rot_matrix("x", pitch) @ mc3d._rot_matrix("y", yaw)
    Fm = np.eye(4)
    Fm[:3, :3] = V.T @ np.diag([1.0, 1.0, -1.0]) @ V
    fixed = [(m, Fm @ (np.eye(4) if M is None else np.array(M, dtype=float))) for m, M in parts]
    return _ORIG_RENDER(fixed, size=size, yaw=yaw, pitch=pitch, **kw)


_ORIG_RENDER = None


class _fixed_depth:
    def __enter__(self):
        import mc3d
        global _ORIG_RENDER
        _ORIG_RENDER = getattr(mc3d.render, "_orig", mc3d.render)
        zrender._orig = _ORIG_RENDER
        mc3d.render = zrender
        return self

    def __exit__(self, *a):
        import mc3d
        mc3d.render = _ORIG_RENDER


def _view(parts, yaw, pitch, size=360, bg=(28, 26, 36, 255)):
    with _fixed_depth():
        return zrender(parts, size=size, yaw=yaw, pitch=pitch, bg=bg)


def _rig_parts(spec, by_id, swing=0.0, orbs=True):
    from mc3d import mat
    out = []
    for p in spec["parts"]:
        rx, ry, rz = p.get("rotation", [0, 0, 0])
        off = list(p["offset"])
        skip = False
        for a in p["anims"]:
            if a["type"] == "swing":
                if a["axis"] == "x":
                    rx += a["angle"] * swing
                elif a["axis"] == "y":
                    ry += a["angle"] * swing
                else:
                    rz += a["angle"] * swing
            if a["type"] == "orbit":
                if not orbs:
                    skip = True
                    break
                th = math.radians(a["phase"] + 40)
                off = [a["radius"] * math.cos(th), off[1] + a["height"], a["radius"] * math.sin(th)]
        if not skip:
            out.append((by_id[p["id"]], mat(translate=off, scale=p["scale"], yaw=ry, pitch=rx, roll=rz)))
    return out


def previews(spec):
    from mc3d import contact_sheet
    models = spec["_models"]
    by_id = {p["id"]: models[p["model"].split(f"boss/{BOSS}_", 1)[1]] for p in spec["parts"]}
    clean = {k: v for k, v in spec.items() if not k.startswith("_")}
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    font = FONT if os.path.exists(FONT) else None
    # 미리보기에서는 구슬을 궤도 위 한 순간의 자리에 둔다 (spec 의 offset 은 [0,0,0], 게임에서는 orbit 이 정함)
    shown = json.loads(json.dumps(clean))
    for p in shown["parts"]:
        for a in p["anims"]:
            if a["type"] == "orbit":
                th = math.radians(a["phase"] + 40)
                p["offset"] = [a["radius"] * math.cos(th), p["offset"][1] + a["height"], a["radius"] * math.sin(th)]
    with _fixed_depth():
        wkit.rig_preview(shown, by_id, os.path.join(PREVIEW_DIR, f"{BOSS}_voxel.png"), NAME_KO, size=520)
    counts = spec["_counts"]
    imgs, labels = [], []
    for k in ("torso_hood", "robe_lower", "crown", "right_arm", "left_arm", "scythe", "orb"):
        m = models[k]
        for (yw, pt, tag) in ((-30, 14, "앞"), (150, 14, "뒤")):
            imgs.append(_view([(m, None)], yw, pt))
            labels.append(f"{k} {tag} ({counts[k]})")
    imgs.append(_view(_rig_parts(clean, by_id, swing=1.0, orbs=False), -30, 10))
    labels.append("공격 자세 (스윙 최고점)")
    total = sum(counts.values()) + 2 * counts["orb"]
    imgs.append(_view(_rig_parts(clean, by_id, orbs=False), 0, 4))
    labels.append(f"정면 (element {total})")
    imgs.append(_view(_rig_parts(clean, by_id), -30, 10, bg=SKY))
    labels.append("하늘 배경 앞")
    imgs.append(_view(_rig_parts(clean, by_id), 90, 6, bg=SKY))
    labels.append("하늘 배경 옆")
    contact_sheet(imgs, labels, cols=6, cell=360, font=font).save(os.path.join(PREVIEW_DIR, f"{BOSS}_voxel_parts.png"))
    dev = os.path.join(HERE, "_scratch", MODULE)
    os.makedirs(dev, exist_ok=True)
    big = [_view(_rig_parts(clean, by_id), y, p, size=760, bg=bg) for (y, p, bg) in
           ((-25, 8, (28, 26, 36, 255)), (20, 8, SKY))]
    contact_sheet(big, ["dev 앞 왼쪽", "dev 앞 오른쪽 (하늘)"], cols=2, cell=760, font=font).save(os.path.join(dev, "dev_big.png"))
    side = [_view(_rig_parts(clean, by_id, orbs=False), y, 4, size=600) for y in (-90, 180, 90)]
    contact_sheet(side, ["옆(왼손 쪽)", "뒤", "옆(낫 쪽)"], cols=3, cell=600, font=font).save(os.path.join(dev, "dev_side.png"))


def glow_count(spec):
    """발광 복셀 수 (파트별)."""
    out = {}
    for k, pp in spec["_made"].items():
        g = pp.grid
        n = 0
        for name in pp.p.names:
            if pp.p.mats[name].glow:
                n += int(np.sum(g == pp.mid(name)))
        out[k] = n
    return out


if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
    os.makedirs(root, exist_ok=True)
    spec = build(root)
    c = spec["_counts"]
    total = sum(c.values()) + 2 * c["orb"]
    print("elements:", c, "total(with 3 orbs):", total)
    print("glow voxels:", glow_count(spec))
    previews(spec)
    print("ok")
