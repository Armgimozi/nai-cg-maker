"""
서리 군주 (Frost Tyrant) — 복셀 버전. boss id "frost_tyrant".

작은 정육면체(복셀)를 쌓아 만든 보스. 1 복셀 = 1/8 블록 (모든 파트가 같은 크기의 큐브).
  - 몸 파트: wkit.part(vox=1.0) + rig scale 2.0          → 1 복셀 = 1 × 2 / 16 = 1/8 블록
  - 긴 파트(대검, 망토): wkit.part(vox=0.5) + scale 4.0   → 1 복셀 = 0.5 × 4 / 16 = 1/8 블록 (회전 중심에서 6블록까지)

설계 좌표: 모든 파트를 '보스 좌표'(복셀, 발바닥 가운데가 원점, 앞 +Z, 위 +Y, 보스의 오른쪽 = -X)로 그리고
P 래퍼가 파트 피벗만큼 옮겨 준다. 그래서 파트끼리 위치를 맞추기 쉽다.

키: 발 0 → 왕관 띠 48 (6블록), 얼음 왕관 끝 약 58, 대검 끝 약 59 (7.4블록).
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

BOSS = "frost_tyrant"
MODULE = "vboss_frost"
NAME_KO = "서리 군주"
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
PREVIEW_DIR = os.path.join(HERE, "preview")
VPB = 8.0   # 블록당 복셀

# ─────────────────────────────── 재료 ───────────────────────────────
MATS = {
    "armor":   Mat(["#0e1b3a", "#1a3366", "#2a5294", "#3f76bc"], "metal", seed=1),
    "armor2":  Mat(["#13285a", "#21468a", "#3366b0", "#4f8ad0"], "scale", seed=2),
    "trim":    Mat(["#557fae", "#88b0d6", "#bcd8f0", "#eef8ff"], "metal", seed=3),
    "chain":   Mat(["#070c1a", "#111b33", "#1d2b4c", "#2c3f66"], "scale", seed=4),
    "ice":     Mat(["#2f7cc0", "#5fb2e8", "#9cdcf8", "#e6fbff"], "crystal", seed=5),
    "ice_d":   Mat(["#14397c", "#2160ac", "#3a8ad4", "#6cbcee"], "crystal", seed=6),
    "frost":   Mat(["#9cb8d4", "#c2d8ec", "#e0eef9", "#ffffff"], "stone", seed=7),
    "bone":    Mat(["#7a8494", "#a8b1bf", "#d0d7e1", "#f2f5f9"], "stone", seed=8),
    "dark":    Mat(["#02040c", "#060b1c", "#0c142e", "#131f42"], "stone", seed=9),
    "gem":     Mat(["#0088e6", "#22c4ff", "#8cf0ff", "#ffffff"], "gem", glow=True, seed=10),
    "eye":     Mat(["#7ae8ff", "#a8f4ff", "#d8fdff", "#ffffff"], "stone", glow=True, seed=11),
    "cape":    Mat(["#0a1230", "#122050", "#1b2e6c", "#273f88"], "cloth", seed=12),
    "cape_in": Mat(["#04081a", "#09122c", "#0f1a3c", "#16244e"], "cloth", seed=13),
    "grip":    Mat(["#100e26", "#1d1a3e", "#2c285a", "#403a7a"], "grip", seed=14),
    "claw":    Mat(["#2a90f0", "#62c8ff", "#a8eeff", "#ffffff"], "crystal", glow=True, seed=15),
    # 움직이는 재료 (발광)
    "rune":    Mat(["#0a64f0", "#24b0ff", "#7ce6ff", "#eaffff"], "pulse", glow=True, seed=20),
    "edge":    Mat(["#2c94ff", "#6ad2ff", "#b8f4ff", "#ffffff"], "flow", glow=True, seed=21),
    "spark":   Mat(["#1c78e0", "#4cb8ff", "#a8ecff", "#ffffff"], "sparkle", glow=True, seed=22),
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

    # 좌표 변환
    def _w(self, fn):
        px, py, pz = self.pv
        return lambda X, Y, Z: fn(X + px, Y + py, Z + pz)

    @property
    def grid(self):
        return self.p.grid

    def coords(self):
        px, py, pz = self.pv
        return self.p._X + px, self.p._Y + py, self.p._Z + pz

    def mid(self, m):
        return self.p._id(m)

    def fill(self, fn, m):
        self.p.fill(self._w(fn), m)
        return self

    def clear(self, fn):
        self.p.clear(self._w(fn))
        return self

    def box(self, x0, x1, y0, y1, z0, z1, m):
        """칸 [x0,x1) x [y0,y1) x [z0,z1) (정수 경계) 를 채운다."""
        return self.fill(lambda X, Y, Z: (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (Z > z0) & (Z < z1), m)

    def unbox(self, x0, x1, y0, y1, z0, z1):
        return self.clear(lambda X, Y, Z: (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (Z > z0) & (Z < z1))

    def tube(self, pts, r, m, rz=None):
        px, py, pz = self.pv
        self.p.tube([(a - px, b - py, c - pz) for a, b, c in pts], r, m, rz=rz)
        return self

    def ball(self, cx, cy, cz, rx, ry, rz, m):
        return self.fill(lambda X, Y, Z: ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2 <= 1, m)

    def spike(self, x, y, z, h, w, m, down=False, tip=None):
        """계단식 사각뿔 (위로/아래로). 밑면 반폭 w, 높이 h. tip 재료가 있으면 끝 1/3 을 그 재료로."""
        def fn_for(lo, hi):
            def fn(X, Y, Z):
                t = ((y - Y) if down else (Y - y)) / h
                hw = np.maximum(0.5, np.floor(w * (1 - t) + 0.5))
                return (t >= lo) & (t <= hi) & (np.abs(X - x) <= hw) & (np.abs(Z - z) <= hw)
            return fn
        if tip:
            self.fill(fn_for(0, 0.62), m)
            self.fill(fn_for(0.62, 1.0), tip)
        else:
            self.fill(fn_for(0, 1.0), m)
        return self

    def frost_tops(self, on, prob=0.55, mat="frost"):
        """on 재료의 위쪽이 비어 있는 복셀에 눈/서리를 얹는다(재료 교체)."""
        g = self.grid
        ids = [self.mid(n) for n in on]
        src = np.isin(g, ids)
        above_empty = np.zeros_like(src)
        above_empty[:, :-1, :] = g[:, 1:, :] == 0
        top = src & above_empty
        r = np.random.default_rng(self.rng.randrange(1 << 30))
        pick = top & (r.random(g.shape) < prob)
        g[pick] = self.mid(mat)
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


def _rng(seed):
    return random.Random(seed)


# ─────────────────────────────── 다리 ───────────────────────────────
HIP = (0, 16, 0)


def make_legs():
    p = P(["armor", "armor2", "trim", "chain", "ice", "ice_d", "frost", "dark", "gem", "rune"], HIP, seed=1)
    # 왼다리(+X)만 그리고 mirror
    # 발 (사바톤): 바닥 검은 밑창, 계단식 발끝
    p.box(1, 8, 0, 1, -4, 7, "dark")
    p.box(1, 8, 1, 3, -4, 6, "armor")
    p.box(2, 7, 1, 2, 6, 8, "armor")           # 발끝
    p.box(2, 7, 2, 3, 5, 7, "trim")
    p.box(1, 8, 3, 4, -3, 4, "trim")             # 발목 띠
    p.box(3, 6, 1, 3, 7, 8, "ice")              # 발끝 얼음 발톱
    # 정강이받이
    p.box(1, 8, 4, 11, -3, 4, "armor")
    p.box(3, 6, 4, 11, 4, 5, "trim")            # 앞 등줄
    p.box(4, 5, 5, 10, 5, 6, "rune")            # 빛나는 룬 줄
    p.box(8, 9, 5, 10, -2, 3, "armor2")         # 바깥쪽 덧판
    # 무릎 덮개 + 얼음 가시
    p.box(1, 8, 10, 13, -2, 5, "trim")
    p.box(2, 7, 11, 13, 5, 6, "armor")
    p.box(3, 6, 11, 12, 6, 7, "gem")
    p.tube([(4.5, 12, 6), (4.5, 13.5, 8.5), (4.5, 15.5, 10.5)], lambda t: 1.4 - 0.7 * t, "ice")
    # 허벅지 (사슬)
    p.box(1, 7, 13, 17, -3, 3, "chain")
    p.box(0, 7, 15, 17, -3, 3, "chain")
    # 정강이 바깥 얼음 결정
    p.tube([(8.5, 5, 0.5), (10.5, 7.5, 0.5), (11.5, 10.5, 0.5)], lambda t: 1.3 - 0.6 * t, "ice_d")
    p.tube([(8.5, 8, -1.5), (10, 10.5, -2.5)], lambda t: 1.1 - 0.4 * t, "ice")
    p.mirror()
    p.frost_tops(["armor", "trim"], prob=0.5)
    return p


# ─────────────────────────────── 몸통 ───────────────────────────────

def snowflake(cx, cy, r):
    """앞에서 본 눈꽃 무늬 (X, Y) → bool, 복셀 계단."""
    def fn(X, Y):
        dx, dy = X - cx, Y - cy
        ax, ay = np.abs(dx), np.abs(dy)
        arm = ((ax < 1) & (ay < r)) | ((ay < 1) & (ax < r)) | ((np.abs(ax - ay) < 1) & (ax < r * 0.72))
        # 가지 끝의 작은 가로대
        bar = ((ay > r - 3) & (ay < r - 2) & (ax < 2.0)) | ((ax > r - 3) & (ax < r - 2) & (ay < 2.0))
        core = (ax < 2) & (ay < 2)
        return arm | bar | core
    return fn


def make_torso():
    names = ["armor", "armor2", "trim", "chain", "ice", "ice_d", "frost", "dark", "gem", "cape", "rune"]
    p = P(names, HIP, seed=2)
    # 허리 아래 판(태싯) 3단: 아래로 갈수록 넓어지고 앞으로 나온다
    for (y0, y1, x, zf, zb) in ((14, 17, 7, 5, -5), (11, 14, 8, 6, -6), (8, 11, 9, 6, -6)):
        p.box(-x, x, y0, y1, zb, zf, "armor")
        p.box(-x, x, y0, y0 + 1, zb, zf, "trim")       # 각 판 아래 테두리
    p.unbox(-2, 2, 7, 14, 3, 8)                          # 가운데 앞 틈 (휘장이 들어갈 자리)
    p.unbox(-1, 1, 7, 14, -8, -3)
    # 앞 휘장 (천, 너덜너덜한 끝 + 룬)
    p.box(-2, 2, 4, 17, 4, 6, "cape")
    for i, x in enumerate((-2, -1, 0, 1)):
        p.box(x, x + 1, 3 + (i * 7 % 3), 4, 4, 6, "cape")
    p.box(-1, 1, 8, 9, 6, 7, "rune")
    p.box(-1, 1, 11, 13, 6, 7, "rune")
    # 허리띠 + 버클 보석
    p.box(-8, 8, 16, 19, -5, 6, "trim")
    p.box(-2, 2, 16, 19, 6, 7, "armor")
    p.box(-1, 1, 17, 18, 7, 8, "gem")
    # 배 (마디 판)
    for y0 in (19, 22):
        p.box(-6, 6, y0, y0 + 2, -4, 5, "armor")
        p.box(-5, 5, y0 + 2, y0 + 3, -4, 4, "chain")
    p.box(-7, -6, 19, 25, -4, 4, "chain")
    p.box(6, 7, 19, 25, -4, 4, "chain")
    # 가슴 (넓은 흉갑)
    p.box(-7, 7, 25, 28, -5, 6, "armor")
    p.box(-9, 9, 28, 35, -5, 6, "armor")
    p.box(-8, -1, 27, 34, 6, 7, "armor2")               # 가슴 판 (도드라짐)
    p.box(1, 8, 27, 34, 6, 7, "armor2")
    p.box(-9, 9, 34, 35, -5, 7, "trim")                  # 위 테두리
    p.box(-8, -1, 27, 28, 6, 7, "trim")
    p.box(1, 8, 27, 28, 6, 7, "trim")
    # 눈꽃 문장: 금속 테두리 + 빛나는 룬
    p.fill(lambda X, Y, Z: (np.hypot(X, Y - 30.5) < 5.6) & (Z > 6) & (Z < 8), "trim")
    p.fill(lambda X, Y, Z: (np.hypot(X, Y - 30.5) < 4.6) & (Z > 6) & (Z < 8), "dark")
    p.fill(lambda X, Y, Z: snowflake(0, 30.5, 4.6)(X, Y) & (np.hypot(X, Y - 30.5) < 4.6) & (Z > 6) & (Z < 8.5), "rune")
    # 배의 빛나는 룬 줄
    for x in (-4, 3):
        p.box(x, x + 1, 19, 25, 4, 5, "rune")
    # 등판 + 등줄
    p.box(-8, 8, 24, 34, -6, -5, "armor2")
    p.box(-1, 1, 19, 35, -7, -5, "trim")
    # 어깨를 잇는 판
    p.box(-11, 11, 30, 35, -4, 4, "armor")
    # 목가리개 + 서리 털 망토 깃
    p.box(-5, 5, 34, 38, -4, 4, "trim")
    p.fill(lambda X, Y, Z: (Y > 34) & (Y < 37) & ((X / 8.6) ** 2 + (Z / 5.6) ** 2 <= 1) & ((X / 5) ** 2 + (Z / 3.2) ** 2 > 1), "frost")
    # 목 뒤로 솟은 얼음 깃 (왕의 후광 같은 실루엣)
    for x, h, lean in ((-7, 6, -2.5), (-4, 9, -1.5), (0, 11, 0), (4, 9, 1.5), (7, 6, 2.5)):
        p.tube([(x, 35, -4), (x + lean * 0.5, 35 + h * 0.55, -5.5), (x + lean, 35 + h, -6.5)],
               lambda t: 1.6 - 1.0 * t, "ice" if abs(x) != 4 else "ice_d")
    p.frost_tops(["armor", "trim"], prob=0.45)
    return p


# ─────────────────────────────── 머리 ───────────────────────────────
NECK = (0, 36, 0)


def make_head():
    names = ["armor", "trim", "ice", "ice_d", "frost", "bone", "dark", "gem", "eye", "chain"]
    p = P(names, NECK, seed=3)
    p.box(-2, 2, 34, 38, -2, 2, "chain")                 # 목
    # 해골
    p.box(-4, 4, 40, 47, -4, 4, "bone")
    p.box(-3, 3, 37, 40, -3, 5, "bone")                  # 턱
    p.box(-4, 4, 40, 44, 4, 5, "bone")                   # 얼굴 앞판
    p.box(-5, -4, 41, 44, -1, 4, "bone")                 # 광대
    p.box(4, 5, 41, 44, -1, 4, "bone")
    # 눈구멍 + 빛나는 눈
    for sx in (-1, 1):
        x0 = 1 if sx > 0 else -4
        p.unbox(x0, x0 + 3, 42, 45, 2, 6)
        p.box(x0, x0 + 3, 42, 45, 2, 3, "dark")
        p.box(x0 + (1 if sx > 0 else 0), x0 + (3 if sx > 0 else 2), 43, 44, 2, 4, "eye")
    # 코
    p.unbox(-1, 1, 40, 42, 3, 6)
    p.box(-1, 1, 40, 42, 3, 4, "dark")
    # 이빨 (뼈/어둠 번갈아)
    p.box(-3, 3, 38, 39, 4, 5, "dark")
    for x in range(-3, 3):
        if x % 2 == 0:
            p.box(x, x + 1, 37, 39, 5, 6, "bone")
    # 이마 투구 (찡그린 눈썹)
    p.box(-5, 5, 45, 47, -5, 5, "armor")
    p.box(-5, 5, 45, 46, 5, 6, "armor")
    for sx in (-1, 1):
        for i in range(3):
            x = sx * (1 + i)
            x0 = x if sx > 0 else x - 1
            p.box(x0, x0 + 1, 44 + (i // 2), 45 + (i // 2), 5, 6, "armor")
    p.box(-5, 5, 47, 48, -5, 5, "armor")
    # 뒤통수/볼가리개
    p.box(-5, 5, 38, 47, -5, -3, "armor")
    p.box(-6, -4, 38, 45, -4, 1, "armor")
    p.box(4, 6, 38, 45, -4, 1, "armor")
    p.box(-6, -4, 38, 39, -4, 1, "trim")
    p.box(4, 6, 38, 39, -4, 1, "trim")
    # 왕관 띠
    p.box(-6, 6, 47, 49, -6, 6, "trim")
    p.box(-5, 5, 49, 50, -5, 5, "armor")
    # 왕관 보석
    p.box(-1, 1, 47, 50, 6, 7, "gem")
    p.box(-2, 2, 48, 49, 6, 7, "gem")
    for x in (-4, 3):
        p.box(x, x + 1, 47, 49, 6, 7, "gem")
    for z in (-1,):
        p.box(-7, -6, 47, 49, z, z + 2, "gem")
        p.box(6, 7, 47, 49, z, z + 2, "gem")
    # 얼음 왕관 가시 (계단식 사각뿔)
    p.spike(0, 49, 4, 10, 2.0, "ice", tip="frost")
    for sx in (-1, 1):
        p.spike(sx * 3, 49, 4, 6, 1.0, "ice_d", tip="ice")
        p.spike(sx * 5, 49, 2, 7, 1.0, "ice", tip="frost")
        p.spike(sx * 5, 49, -3, 5, 1.0, "ice_d", tip="ice")
        p.spike(sx * 2, 49, -5, 6, 1.0, "ice", tip="frost")
    # 뿔: 관자놀이에서 바깥 위로 휘어 오른다
    for sx in (-1, 1):
        pts = [(sx * 5.5, 44, -1), (sx * 8.5, 45.5, -2), (sx * 11, 48.5, -2.5), (sx * 12, 52.5, -2.5),
               (sx * 11.5, 56, -1.5), (sx * 10, 58, -0.5)]
        p.tube(pts, lambda t: 1.9 - 1.25 * t, "ice_d")
        p.tube(pts[3:], lambda t: 1.15 - 0.55 * t, "ice")
    # 고드름 수염
    for x, h in ((-3, 2), (-1, 4), (1, 3), (3, 2)):
        p.spike(x, 37, 4, h, 1.0, "ice", down=True)
    p.frost_tops(["armor", "trim"], prob=0.5)
    return p


# ─────────────────────────────── 팔 ───────────────────────────────
R_SHOULDER = (-11, 33, 0)
L_SHOULDER = (11, 33, 0)


def pauldron(p, s):
    """s = -1 (오른쪽, -X) / +1 (왼쪽). 3단 견갑 + 얼음 가시."""
    def X(a, b):
        return (min(s * a, s * b), max(s * a, s * b))
    x0, x1 = X(7, 17)
    p.box(x0, x1, 32, 37, -6, 6, "armor")
    x0, x1 = X(8, 16)
    p.box(x0, x1, 37, 39, -5, 5, "armor2")
    x0, x1 = X(7, 17)
    p.box(x0, x1, 32, 33, -6, 6, "trim")
    x0, x1 = X(8, 18)
    p.box(x0, x1, 29, 32, -6, 6, "armor")
    p.box(x0, x1, 29, 30, -6, 6, "trim")
    x0, x1 = X(9, 19)
    p.box(x0, x1, 26, 29, -5, 5, "armor2")
    p.box(x0, x1, 26, 27, -5, 5, "trim")
    # 바깥면 룬 (작은 십자)
    xo0, xo1 = X(19, 20)
    p.box(xo0, xo1, 27, 28, -2, 2, "rune")
    xo0, xo1 = X(18, 19)
    p.box(xo0, xo1, 30, 31, -1, 1, "rune")
    xo0, xo1 = X(17, 18)
    p.box(xo0, xo1, 34, 36, -1, 1, "gem")
    p.box(xo0, xo1, 33, 37, 0, 0.01, "gem")
    # 얼음 가시
    sp = [((12, 38, 0), (14, 47, -1), 2.0, "ice"),
          ((15, 37, -3), (21, 43, -4), 1.6, "ice_d"),
          ((10, 38, 3), (11, 44, 5), 1.3, "ice"),
          ((16, 35, 3), (21, 38.5, 5), 1.3, "ice"),
          ((14, 38, -4), (16, 43, -7), 1.2, "ice")]
    for (a, b, r, m) in sp:
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.5, (a[2] + b[2]) / 2)
        p.tube([(s * a[0], a[1], a[2]), (s * mid[0], mid[1], mid[2]), (s * b[0], b[1], b[2])],
               (lambda r0: (lambda t: r0 * (1 - 0.72 * t)))(r), m)


def make_right_arm():
    names = ["armor", "armor2", "trim", "chain", "ice", "ice_d", "frost", "dark", "gem", "rune"]
    p = P(names, R_SHOULDER, seed=4)
    pauldron(p, -1)
    # 위팔 (사슬 + 바깥 덧판)
    p.box(-14, -8, 21, 30, -3, 3, "chain")
    p.box(-15, -13, 22, 28, -3, 3, "armor")
    # 팔꿈치 + 뒤로 뻗은 얼음 가시
    p.box(-15, -7, 19, 23, -4, 4, "trim")
    p.tube([(-11, 21, -4), (-11, 20, -7), (-11, 19.5, -9)], lambda t: 1.4 - 0.6 * t, "ice")
    # 아래팔: 앞으로 굽힌 완갑 (계단)
    p.box(-15, -8, 18, 23, 0, 5, "armor")
    p.box(-16, -9, 17, 23, 4, 9, "armor")
    p.box(-16, -9, 17, 23, 7, 9, "trim")             # 손목 테두리
    p.box(-16, -15, 18, 22, 1, 7, "armor2")           # 바깥 덧판
    p.box(-17, -16, 19, 21, 2, 6, "rune")
    # 주먹 (대검 손잡이를 감싼다: 손잡이 X -15..-13, Z 10..12)
    p.box(-18, -10, 16, 23, 8, 14, "armor")
    p.box(-18, -10, 22, 23, 8, 14, "trim")
    p.box(-17, -11, 17, 22, 14, 15, "armor2")          # 손가락 마디
    for y in (17, 19, 21):
        p.box(-17, -11, y, y + 1, 14, 15, "trim")
    p.box(-19, -18, 17, 22, 9, 13, "armor2")          # 엄지
    p.frost_tops(["armor", "armor2", "trim"], prob=0.5)
    return p


def make_left_arm():
    names = ["armor", "armor2", "trim", "chain", "ice", "ice_d", "frost", "dark", "gem", "rune", "claw"]
    p = P(names, L_SHOULDER, seed=5)
    pauldron(p, 1)
    # 위팔
    p.box(8, 14, 21, 30, -3, 3, "chain")
    p.box(13, 15, 22, 28, -3, 3, "armor")
    p.box(7, 15, 19, 23, -4, 4, "trim")
    p.tube([(11, 21, -4), (11, 20, -7), (11, 19.5, -9)], lambda t: 1.4 - 0.6 * t, "ice")
    # 아래팔: 살짝 앞으로
    p.box(8, 15, 15, 20, -3, 4, "armor")
    p.box(15, 16, 15, 19, -2, 3, "armor2")
    p.box(16, 17, 16, 18, -1, 2, "rune")
    p.box(7, 16, 14, 16, -4, 5, "trim")
    # 거대한 얼음 발톱 손 (건틀릿)
    p.box(7, 16, 10, 14, -3, 6, "armor")
    p.box(7, 16, 13, 14, -3, 6, "trim")
    p.box(9, 14, 11, 13, 6, 7, "gem")
    # 발톱 4개: 손등에서 아래 앞으로 휘어진 빛나는 얼음
    for i, x in enumerate((8, 10.5, 13, 15.5)):
        L = 1.0 if i in (1, 2) else 0.8
        pts = [(x, 11.5, 5.5), (x, 10.5 - 1.5 * L, 8 + 1.5 * L), (x, 10.0 - 1.0 * L, 11 + 2.5 * L), (x, 11.5 - 0.5 * L, 13 + 3.2 * L)]
        p.tube(pts, lambda t: 1.15 - 0.5 * t, "claw")
    # 엄지 발톱 (안쪽)
    p.tube([(7, 12, 3), (5.5, 11, 6), (5, 11.5, 9)], lambda t: 1.0 - 0.4 * t, "claw")
    # 손등 위 얼음 결정
    p.tube([(12, 13, 0), (13.5, 16, -3), (14, 18.5, -5)], lambda t: 1.3 - 0.6 * t, "ice")
    p.frost_tops(["armor", "armor2", "trim"], prob=0.5)
    return p


# ─────────────────────────────── 대검 ───────────────────────────────
SWORD_X, SWORD_Z = -14, 11   # 칼 가운데 선 (보스 좌표, 칸 경계)


def make_sword():
    names = ["armor", "trim", "ice", "ice_d", "frost", "dark", "gem", "grip", "edge", "rune"]
    p = P(names, R_SHOULDER, vox=0.5, size=96, seed=6)
    cx, cz = SWORD_X, SWORD_Z
    # 손잡이 + 칼자루 끝
    p.box(cx - 1, cx + 1, 11, 25, cz - 1, cz + 1, "grip")
    p.box(cx - 2, cx + 2, 9, 12, cz - 2, cz + 2, "trim")
    p.box(cx - 1, cx + 1, 8, 13, cz - 3, cz + 3, "trim")
    p.box(cx - 3, cx + 3, 10, 11, cz - 1, cz + 1, "trim")
    p.box(cx - 1, cx + 1, 9, 12, cz - 3, cz + 3, "gem")
    p.box(cx - 1, cx + 1, 6, 8, cz - 1, cz + 1, "ice")
    # 코등이: 가운데 높고 양 끝이 위로 휘어 오른 날개
    p.box(cx - 6, cx + 6, 24, 27, cz - 2, cz + 2, "trim")
    p.box(cx - 4, cx + 4, 23, 24, cz - 2, cz + 2, "armor")
    p.box(cx - 3, cx + 3, 27, 28, cz - 2, cz + 2, "trim")
    for s in (-1, 1):
        p.tube([(cx + s * 6, 25.5, cz), (cx + s * 8.5, 26.5, cz), (cx + s * 10, 29, cz), (cx + s * 10.5, 32, cz)],
               lambda t: 1.5 - 0.6 * t, "ice")
        p.box(min(cx + s * 6, cx + s * 8), max(cx + s * 6, cx + s * 8), 25, 26, cz - 2, cz + 2, "armor")
    # 코등이 보석 (앞뒤)
    p.box(cx - 2, cx + 2, 24, 28, cz + 2, cz + 3, "trim")
    p.box(cx - 1, cx + 1, 25, 27, cz + 2, cz + 4, "gem")
    p.box(cx - 2, cx + 2, 24, 28, cz - 3, cz - 2, "trim")
    p.box(cx - 1, cx + 1, 25, 27, cz - 4, cz - 2, "gem")

    # 날: 밑동 28 → 끝 60. 가장자리(빛), 몸통(짙은 얼음), 가운데 등줄(밝은 얼음 + 룬)
    y0, y1 = 28, 60

    def half_w(Y):
        t = (Y - y0) / (y1 - y0)
        w = 5.0 + 0.6 * np.sin(np.clip(t, 0, 1) * math.pi * 0.9)
        taper = np.clip((1 - t) / 0.24, 0, 1)
        w = np.where(t > 0.76, 0.6 + (w - 0.6) * taper ** 0.9, w)
        # 톱니: 3칸마다 한 칸 들어간 얼음 이빨
        notch = ((np.floor(Y) - y0) % 4 == 0) & (t > 0.08) & (t < 0.7)
        return np.floor(w + 0.5) - np.where(notch, 1, 0)

    def blade(X, Y, Z):
        return (Y > y0) & (Y < y1) & (np.abs(X - cx) < half_w(Y))

    p.fill(lambda X, Y, Z: blade(X, Y, Z) & (np.abs(Z - cz) < 1), "edge")
    p.fill(lambda X, Y, Z: blade(X, Y, Z) & (np.abs(X - cx) < half_w(Y) - 1) & (np.abs(Z - cz) < 2), "ice_d")
    p.fill(lambda X, Y, Z: blade(X, Y, Z) & (np.abs(X - cx) < np.minimum(2, half_w(Y) - 1)) & (np.abs(Z - cz) < 3) & (Y < y1 - 3), "ice")
    # 등줄 룬 (앞뒤, 3칸마다)
    p.fill(lambda X, Y, Z: (Y > y0 + 2) & (Y < y1 - 7) & (np.abs(X - cx) < 1) & (np.abs(Z - cz) > 2) & (np.abs(Z - cz) < 3)
           & (((np.floor(Y) - y0) % 3) != 0), "rune")
    # 날 밑동에 솟은 얼음 결정 (비대칭)
    p.tube([(cx + 4, 30, cz), (cx + 7, 34, cz + 1), (cx + 8.5, 38, cz + 1)], lambda t: 1.4 - 0.6 * t, "ice")
    p.tube([(cx - 4, 33, cz), (cx - 7.5, 36, cz - 1), (cx - 8.5, 39, cz - 1)], lambda t: 1.2 - 0.5 * t, "ice")
    p.tube([(cx + 4, 42, cz), (cx + 6.5, 45, cz)], lambda t: 1.0 - 0.3 * t, "ice")
    return p


# ─────────────────────────────── 망토 ───────────────────────────────
CAPE_PIVOT = (0, 35, -5)


def make_cape():
    names = ["cape", "cape_in", "frost", "ice", "trim", "gem", "rune", "dark"]
    p = P(names, CAPE_PIVOT, vox=0.5, size=80, seed=7)
    rng = _rng(77)
    top, bottom = 36, 3

    def back(Y):
        d = np.clip((top - Y) / (top - bottom), 0, 1)
        return -5 - np.floor(d ** 1.5 * 5 + 0.5)          # 아래로 갈수록 뒤로 펄럭

    def halfw(Y):
        d = np.clip((top - Y) / (top - bottom), 0, 1)
        return np.floor(9 + d * 3.5)

    # 너덜너덜한 밑단: 2칸 기둥마다 길이가 다르다
    cols = {}
    for c in range(-7, 7):
        cols[c] = bottom + rng.choice((0, 0, 1, 2, 3, 4, 6, 8))
    hem = np.vectorize(lambda X: cols.get(int(math.floor(X / 2)), 99))

    # 주름: 3칸마다 한 칸 뒤로
    def fold(X):
        return np.where((np.floor(X) % 6 + 6) % 6 < 3, 0, 1)

    def sheet(X, Y, Z):
        zb = back(Y) - fold(X)
        return (Y < top) & (Y > hem(X)) & (np.abs(X) < halfw(Y)) & (Z < zb) & (Z > zb - 2)

    p.fill(sheet, "cape")
    # 안쪽 면(몸 쪽) 은 더 어둡게
    p.fill(lambda X, Y, Z: sheet(X, Y, Z) & (Z > back(Y) - fold(X) - 1), "cape_in")
    # 밑단 서리 (끝 3칸)
    p.fill(lambda X, Y, Z: sheet(X, Y, Z) & (Y < hem(X) + 3.5), "frost")
    # 옆단 서리 테두리
    p.fill(lambda X, Y, Z: sheet(X, Y, Z) & (np.abs(X) > halfw(Y) - 1), "frost")
    # 고드름
    for c, yb in cols.items():
        if rng.random() < 0.6:
            x = c * 2 + 1
            h = rng.choice((2, 3, 4))
            zb = float(back(np.array(yb + 0.5)) - fold(np.array(x - 0.5)))
            p.spike(x, yb + 1, zb - 1, h + 1, 1.0, "ice", down=True)
    # 구멍 몇 개
    for _ in range(5):
        x = rng.randrange(-10, 9)
        y = rng.randrange(6, 14)
        p.clear(lambda X, Y, Z, x=x, y=y: (X > x) & (X < x + 2) & (Y > y) & (Y < y + 2) & (Z < -3))
    # 등의 룬: 세로 점선 두 줄 + 가운데 눈꽃
    for x in (-6, 5):
        p.fill(lambda X, Y, Z, x=x: sheet(X, Y, Z) & (X > x) & (X < x + 1) & (Y > 9) & (Y < 26)
               & ((np.floor(Y) % 3) != 0) & (Z < back(Y) - fold(X) - 1), "rune")
    flake = snowflake(0, 26, 5.2)
    p.fill(lambda X, Y, Z: sheet(X, Y, Z) & flake(X, Y) & (np.hypot(X, Y - 26) < 5.2) & (Z < back(Y) - fold(X) - 1), "rune")
    # 위쪽 서리 털 깃 + 걸쇠
    p.fill(lambda X, Y, Z: (Y > 33) & (Y < 37) & (np.abs(X) < 10) & (Z < -3) & (Z > -8), "frost")
    for x in (-8, 7):
        p.box(x, x + 1, 34, 36, -3, -2, "gem")
    return p


# ─────────────────────────────── 얼음 파편 ───────────────────────────────

def make_shard():
    names = ["ice", "ice_d", "frost", "claw", "spark"]
    p = P(names, (0, 0, 0), seed=8)

    def body(X, Y, Z, s=1.0):
        t = np.abs(Y) / (7.0 if s else 1)
        hw = np.floor(3.2 * (1 - t) + 0.5) * s
        return (np.abs(Y) < 7) & (np.abs(X) <= hw) & (np.abs(Z) <= hw)

    p.fill(lambda X, Y, Z: body(X, Y, Z), "ice")
    # 결정 면마다 짙은/밝은 띠
    p.fill(lambda X, Y, Z: body(X, Y, Z) & (np.abs(X) > np.abs(Z)) & (np.floor(Y) % 3 == 0), "ice_d")
    # 빛나는 심(겉으로 보이는 세로 줄)
    p.fill(lambda X, Y, Z: body(X, Y, Z) & (np.abs(X) < 1) & (np.abs(Y) < 6), "spark")
    p.fill(lambda X, Y, Z: body(X, Y, Z) & (np.abs(Z) < 1) & (np.abs(Y) < 6), "spark")
    p.spike(0, 6, 0, 3, 1.0, "frost")
    # 작은 곁결정
    p.tube([(1.5, -1, 1.5), (4.5, 2, 3.5)], lambda t: 1.0 - 0.3 * t, "claw")
    p.tube([(-1.5, 0, -1.5), (-4, -3.5, -3)], lambda t: 0.95 - 0.25 * t, "claw")
    return p


# ─────────────────────────────── 조립 ───────────────────────────────
BOB = {"type": "bob", "amplitude": 0.04, "period": 60, "phase": 0.0}


def build(assets_root):
    """모든 파트 모델을 쓰고 rig spec 을 돌려준다."""
    made = {
        "legs": make_legs(), "torso": make_torso(), "head": make_head(), "cape": make_cape(),
        "right_arm": make_right_arm(), "sword": make_sword(), "left_arm": make_left_arm(), "shard": make_shard(),
    }
    models = {k: v.build(k, assets_root) for k, v in made.items()}

    def entry(pid, part, anims, rot=(0, 0, 0), frame="body", model=None, offset=None, scale=None):
        pp = made[part]
        return {"id": pid, "model": f"augsky:boss/{BOSS}_{model or part}",
                "offset": offset if offset is not None else pp.offset(), "scale": scale or pp.scale(),
                "rotation": list(rot), "frame": frame, "anims": anims}

    arm_r = [dict(BOB), {"type": "sway", "axis": "x", "angle": 3, "period": 60, "phase": 0.0},
             {"type": "swing", "axis": "x", "angle": -100, "ticks": 14}]
    arm_l = [dict(BOB), {"type": "sway", "axis": "x", "angle": 5, "period": 60, "phase": 0.5},
             {"type": "swing", "axis": "x", "angle": -75, "ticks": 10}]
    parts = [
        entry("legs", "legs", []),
        entry("torso", "torso", [dict(BOB)]),
        entry("cape", "cape", [dict(BOB), {"type": "sway", "axis": "x", "angle": 5, "period": 50, "phase": 0.0}]),
        entry("head", "head", [dict(BOB), {"type": "sway", "axis": "y", "angle": 9, "period": 120, "phase": 0.0}]),
        entry("right_arm", "right_arm", arm_r),
        entry("sword", "sword", [dict(a) for a in arm_r]),
        entry("left_arm", "left_arm", arm_l),
    ]
    for i, (ph, h) in enumerate(((0.0, 3.3), (120.0, 4.1), (240.0, 3.3))):
        parts.append(entry(f"shard_{i + 1}", "shard",
                           [{"type": "orbit", "radius": 2.5, "speed": 3.0, "phase": ph, "height": h},
                            {"type": "spin", "axis": "y", "speed": 6.0},
                            {"type": "bob", "amplitude": 0.25, "period": 50, "phase": i / 3}],
                           frame="world", offset=[0.0, 0.0, 0.0]))
    spec = {
        "boss": BOSS,
        "parts": parts,
        "notes": ("서리 군주 복셀 버전. 1 복셀 = 1/8 블록: 몸 파트 vox 1.0 × scale 2, 대검/망토 vox 0.5 × scale 4 "
                  "(큐브 크기 같음, 회전 중심에서 6블록까지). 키: 왕관 띠 6블록, 왕관 가시/대검 끝 약 7.3블록. "
                  "보스 오른손 = -X (대검), 왼손 = +X (얼음 발톱), 앞 = +Z. 모든 포즈는 모델에 구워 넣어 rotation 은 0. "
                  "sword 는 right_arm 과 같은 피벗(오른 어깨)·같은 anims 라야 손에 붙어 있다. "
                  "swing angle 음수 = 팔을 앞으로 들어 올림: 대검을 머리 위로 치켜든 뒤 내려친다. "
                  "legs 는 고정, 나머지 몸 파트는 같은 bob 으로 숨쉰다. shard 3개는 같은 모델, frame=world orbit. "
                  "발광: 눈/보석/룬(pulse)/대검 날(flow)/발톱/파편 심(sparkle)."),
    }
    spec["_counts"] = {k: len(m.elements) for k, m in models.items()}
    with open(os.path.join(HERE, MODULE + ".rig.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in spec.items() if not k.startswith("_")}, f, ensure_ascii=False, indent=2)
    spec["_models"] = models
    return spec


def _view(parts, yaw, pitch, size=360, bg=(28, 26, 36, 255)):
    """mc3d.render 는 좌우가 뒤집힌 그림을 준다 (테스트: +X 큐브가 정면에서 왼쪽에 보임). 다시 뒤집어 실제 모습으로.
    yaw 180 = 정면(+Z 쪽에서 봄)."""
    from mc3d import render
    from PIL import ImageOps
    return ImageOps.mirror(render(parts, size=size, yaw=yaw, pitch=pitch, bg=bg))


def _turned(spec):
    """미리보기 전용: 보스 전체를 Y 축으로 180도 돌린 spec (wkit.rig_preview 의 '앞' 카메라가 +Z 앞면을 보게)."""
    s = json.loads(json.dumps({k: v for k, v in spec.items() if not k.startswith("_")}))
    for p in s["parts"]:
        x, y, z = p["offset"]
        p["offset"] = [-x, y, -z]
        r = p.get("rotation", [0, 0, 0])
        p["rotation"] = [r[0], r[1] + 180, r[2]]
    return s


def _rig_parts(spec, by_id, swing=0.0, shards=True):
    from mc3d import mat
    out = []
    for p in spec["parts"]:
        rx, ry, rz = p.get("rotation", [0, 0, 0])
        off = list(p["offset"])
        for a in p["anims"]:
            if a["type"] == "swing":
                rx += a["angle"] * swing
            if a["type"] == "orbit":
                if not shards:
                    break
                th = math.radians(a["phase"] + 40)
                off = [a["radius"] * math.cos(th), off[1] + a["height"], a["radius"] * math.sin(th)]
        else:
            out.append((by_id[p["id"]], mat(translate=off, scale=p["scale"], yaw=ry, pitch=rx, roll=rz)))
    return out


def previews(spec):
    from mc3d import contact_sheet
    from PIL import ImageOps
    models = spec["_models"]
    by_id = {p["id"]: models[p["model"].split(f"boss/{BOSS}_", 1)[1]] for p in spec["parts"]}
    clean = {k: v for k, v in spec.items() if not k.startswith("_")}
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    font = FONT if os.path.exists(FONT) else None
    # 1) 조립 미리보기: wkit.rig_preview (돌린 spec + 좌우 되돌림 → 앞 3/4, 옆, 뒤 3/4 가 실제 모습)
    views = wkit.rig_preview(_turned(clean), by_id, None, NAME_KO, size=520)
    views = [ImageOps.mirror(v) for v in views]
    contact_sheet(views, [f"{NAME_KO} 앞", f"{NAME_KO} 옆", f"{NAME_KO} 뒤"], cols=3, cell=520, font=font).save(
        os.path.join(PREVIEW_DIR, f"{BOSS}_voxel.png"))
    # 2) 파트 확대
    counts = spec["_counts"]
    imgs, labels = [], []
    for k in ("head", "torso", "legs", "cape", "right_arm", "left_arm", "sword", "shard"):
        m = models[k]
        for (yw, pt, tag) in ((150, 14, "앞"), (-30, 14, "뒤")):
            imgs.append(_view([(m, None)], yw, pt))
            labels.append(f"{k} {tag} ({counts[k]})")
    imgs.append(_view(_rig_parts(clean, by_id, swing=1.0, shards=False), 115, 8))
    labels.append("공격 자세 (스윙 최고점)")
    imgs.append(_view(_rig_parts(clean, by_id, shards=False), 180, 4))
    total = sum(counts.values()) + 2 * counts["shard"]
    labels.append(f"정면 (element {total})")
    contact_sheet(imgs, labels, cols=4, cell=360, font=font).save(os.path.join(PREVIEW_DIR, f"{BOSS}_voxel_parts.png"))
    # 3) 작업용 큰 그림 (scratch)
    big = [_view(_rig_parts(clean, by_id), y, p, size=700) for (y, p) in ((155, 10), (205, 10))]
    contact_sheet(big, ["dev 앞 왼쪽", "dev 앞 오른쪽"], cols=2, cell=700, font=font).save(
        os.path.join(HERE, "_scratch", MODULE, "dev_big.png"))


if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
    os.makedirs(root, exist_ok=True)
    spec = build(root)
    c = spec["_counts"]
    total = sum(c.values()) + 2 * c["shard"]
    print("elements:", c, "total(with 3 shards):", total)
    previews(spec)
    print("ok")
