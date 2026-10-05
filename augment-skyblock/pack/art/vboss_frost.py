"""
서리 군주 (Frost Tyrant) — 복셀 버전. boss id "frost_tyrant".

작은 정육면체(복셀)를 쌓아 만든 보스. 1 복셀 = 1/8 블록 (모든 파트가 같은 크기의 큐브).
  - 몸 파트: wkit.part(vox=1.0) + rig scale 2.0          → 1 복셀 = 1 × 2 / 16 = 1/8 블록
  - 긴 파트(대검, 망토): wkit.part(vox=0.5) + scale 4.0   → 1 복셀 = 0.5 × 4 / 16 = 1/8 블록 (회전 중심에서 6블록까지)

설계 좌표: 모든 파트를 '보스 좌표'(복셀, 발바닥 가운데가 원점, 앞 +Z, 위 +Y, 보스의 오른쪽 = -X)로 그리고
P 래퍼가 파트 피벗만큼 옮겨 준다. 그래서 파트끼리 위치를 맞추기 쉽다.

키: 발 0, 엉덩이 17, 어깨 31, 투구 꼭대기 47 (5.9블록), 서리 왕관 끝 53, 뿔 끝 51.
대검은 평소에 앞으로 33도 기울여 든다 (끝: 6.5블록 높이, 3.8블록 앞). swing -118 = 어깨 너머로 치켜든 뒤 앞으로 내려찍기.
얼음 파편 3개는 왕관 위(7.6블록)를 반지름 1.25블록으로 도는 후광.
견갑은 몸통 파트에 있다. 견갑 가시는 모두 어깨 피벗에서 10칸 안에 두어, 대검을 치켜들 때 주먹/코등이/날이 뚫지 않는다.
"""
import copy
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
# 재료마다 명도 범위를 좁게(큐브마다 은은한 차이), 재료끼리는 대비를 크게.
# 값 구조: 짙은 남색 판금 / 밝은 은 테두리 / 빛나는 청록. 강조색 하나: 옅은 금(왕관 띠, 대검 코등이, 버클).
# 얼굴은 상아색 뼈 + 짙은 남색 턱받이로 하얀 서리 깃에서 떼어 놓는다.
MATS = {
    "armor":   Mat(["#13214a", "#1d3474", "#294a94", "#3864b6"], "metal", seed=1),
    "plate":   Mat(["#1f4690", "#2a5aac", "#3772c4", "#4a8cdc"], "metal", seed=2),
    "trim":    Mat(["#7a92b4", "#a2b8d4", "#cad9ec", "#eef6ff"], "metal", seed=3),
    "gold":    Mat(["#7a5a22", "#a8822e", "#d4ae52", "#f4de96"], "metal", seed=17),
    "chain":   Mat(["#111d3e", "#1c2e58", "#283f70", "#38548c"], "scale", seed=4),
    "navy":    Mat(["#080d22", "#0e1632", "#152044", "#1d2c58"], "metal", seed=18),
    "ice":     Mat(["#3a94de", "#5cb6f2", "#8ad6fb", "#c4efff"], "crystal", seed=5),
    "ice_d":   Mat(["#1a52a8", "#2268c2", "#2f80d8", "#4698ea"], "crystal", seed=6),
    "blade":   Mat(["#0c2860", "#133a80", "#1c4e9c", "#2862b4"], "crystal", seed=16),
    "frost":   Mat(["#b6cee8", "#d2e4f6", "#e8f3fd", "#ffffff"], "stone", seed=7),
    "snow":    Mat(["#c4d8ee", "#dceaf8", "#eef6fe", "#ffffff"], "crystal", seed=19),
    "bone":    Mat(["#8a7656", "#b29c72", "#d6c498", "#f0e6c4"], "stone", seed=8),
    "dark":    Mat(["#03050c", "#070c1c", "#0c1430", "#121c40"], "stone", seed=9),
    "gem":     Mat(["#0088e6", "#22c4ff", "#8cf0ff", "#ffffff"], "gem", glow=True, seed=10),
    "eye":     Mat(["#d4faff", "#ecfdff", "#ffffff", "#ffffff"], "flat", glow=True, seed=11),
    "eye_rim": Mat(["#1aa4ff", "#3cc4ff", "#74dcff", "#a4ecff"], "stone", glow=True, seed=23),
    "cape":    Mat(["#0f1c48", "#172a60", "#213878", "#2d4a92"], "cloth", seed=12),
    "cape_in": Mat(["#0f1a44", "#162556", "#1f3268", "#2a417e"], "cloth", seed=13),
    "grip":    Mat(["#262e58", "#3e4a7e", "#5e6ca2", "#8c9aca"], "grip", seed=14),
    "claw":    Mat(["#2c9cf0", "#4cbcff", "#86dcff", "#c8f4ff"], "crystal", glow=True, seed=15),
    # 움직이는 재료 (발광)
    "rune":    Mat(["#0a64f0", "#24b0ff", "#7ce6ff", "#eaffff"], "pulse", glow=True, seed=20),
    "edge":    Mat(["#3aa0ff", "#74d6ff", "#bcf6ff", "#ffffff"], "flow", glow=True, seed=21),
    "spark":   Mat(["#1c78e0", "#4cb8ff", "#a8ecff", "#ffffff"], "sparkle", glow=True, seed=22),
}


def mats(*names):
    return {n: MATS[n] for n in names}


# ─────────────────────────────── 파트 래퍼 ───────────────────────────────

class P:
    """보스 좌표(복셀)로 그리는 파트. pivot = 보스 좌표의 회전 중심."""

    def __init__(self, names, pivot, vox=1.0, size=None, seed=0, shift=(0, 0, 0)):
        """shift: 그린 좌표에서 실제 보스 좌표까지 옮김 (파트 전체를 통째로 올리거나 내릴 때)."""
        self.vox = vox
        self.shift = tuple(float(v) for v in shift)
        self.reach = int(24 / vox)
        size = size or 2 * self.reach
        self.p = wkit.part(mats(*names), size=size, vox=vox, seed=seed)
        self.pv = tuple(float(v) for v in pivot)
        self.rng = random.Random(seed * 101 + 7)

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

    def paint(self, fn, m, only=None):
        """이미 있는 복셀만 칠한다 (only: 이 재료들만)."""
        px, py, pz = self.pv
        g = self.grid
        mask = np.asarray(fn(self.p._X + px, self.p._Y + py, self.p._Z + pz), dtype=bool) & (g > 0)
        if only:
            mask &= np.isin(g, [self.mid(n) for n in only])
        g[mask] = self.mid(m)
        return self

    def clear(self, fn):
        self.p.clear(self._w(fn))
        return self

    def box(self, x0, x1, y0, y1, z0, z1, m):
        """칸 [x0,x1) x [y0,y1) x [z0,z1) (정수 경계) 를 채운다."""
        return self.fill(_inbox(x0, x1, y0, y1, z0, z1), m)

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

    def spike(self, x, y, z, h, w, m, down=False, tip=None, tip_at=0.62):
        """계단식 사각뿔 (위로/아래로). 밑면 반폭 w, 높이 h. tip 재료가 있으면 끝 부분을 그 재료로."""
        def fn_for(lo, hi):
            def fn(X, Y, Z):
                t = ((y - Y) if down else (Y - y)) / h
                hw = np.maximum(0.5, np.floor(w * (1 - t) + 0.5))
                return (t >= lo) & (t <= hi) & (np.abs(X - x) <= hw) & (np.abs(Z - z) <= hw)
            return fn
        if tip:
            self.fill(fn_for(0, tip_at), m)
            self.fill(fn_for(tip_at, 1.0), tip)
        else:
            self.fill(fn_for(0, 1.0), m)
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
        return [round((self.pv[i] + self.shift[i]) / VPB, 4) for i in range(3)]


class Tilt:
    """P 위에 기울어진 '국소 좌표'로 그린다: (cy, cz) 를 중심으로 X 축 둘레로 angle 도 (위쪽 +Y 가 앞 +Z 로 기운다).
    국소 Y = 칼날 방향, 국소 Z = 칼날 두께 방향. 대검과 그것을 쥔 주먹이 같은 기울기를 쓴다."""

    def __init__(self, p, cy, cz, angle):
        self.p, self.cy, self.cz = p, float(cy), float(cz)
        a = math.radians(angle)
        self.c, self.s = math.cos(a), math.sin(a)

    def _loc(self, X, Y, Z):
        dY, dZ = Y - self.cy, Z - self.cz
        return X, self.cy + dY * self.c + dZ * self.s, self.cz - dY * self.s + dZ * self.c

    def to_boss(self, x, y, z):
        u, w = y - self.cy, z - self.cz
        return x, self.cy + u * self.c - w * self.s, self.cz + u * self.s + w * self.c

    def fill(self, fn, m):
        self.p.fill(lambda X, Y, Z: fn(*self._loc(X, Y, Z)), m)
        return self

    def paint(self, fn, m, only=None):
        self.p.paint(lambda X, Y, Z: fn(*self._loc(X, Y, Z)), m, only)
        return self

    def box(self, x0, x1, y0, y1, z0, z1, m):
        return self.fill(_inbox(x0, x1, y0, y1, z0, z1), m)

    def pbox(self, x0, x1, y0, y1, z0, z1, m, only=None):
        return self.paint(_inbox(x0, x1, y0, y1, z0, z1), m, only)

    def tube(self, pts, r, m):
        self.p.tube([self.to_boss(*q) for q in pts], r, m)
        return self


def _inbox(x0, x1, y0, y1, z0, z1):
    return lambda X, Y, Z: (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (Z > z0) & (Z < z1)


def taper(r0, r1):
    return lambda t: r0 + (r1 - r0) * t


# ─────────────────────────────── 다리 ───────────────────────────────
HIP = (0, 17, 0)


def make_legs():
    p = P(["armor", "plate", "trim", "chain", "ice", "ice_d", "dark", "rune", "navy"], HIP, seed=1)
    # 왼다리(+X)만 그리고 mirror
    # 사바톤: 검은 밑창, 계단식 발등, 얼음 발톱
    p.box(2, 9, 0, 1, -4, 8, "dark")
    p.box(2, 9, 1, 3, -4, 6, "armor")
    p.box(3, 8, 1, 3, 6, 8, "plate")
    p.box(3, 8, 3, 4, 2, 7, "plate")
    p.box(4, 7, 4, 5, 3, 6, "plate")
    p.box(4, 7, 0, 2, 8, 10, "ice")
    p.box(2, 9, 3, 4, -4, 2, "trim")             # 발목 띠
    p.box(3, 8, 1, 4, -5, -4, "navy")            # 뒤꿈치
    # 정강이받이: 아래는 좁고 위는 넓게, 옆면은 계단 + 덧판
    p.box(2, 9, 4, 10, -3, 4, "armor")
    p.box(1, 10, 7, 10, -3, 4, "armor")
    p.box(1, 10, 7, 8, -3, 4, "plate")           # 가운데 이음 줄 (옆에서도 보이게)
    p.box(4, 7, 4, 9, 4, 5, "plate")             # 앞 등줄
    p.box(5, 6, 6, 7, 5, 6, "rune")              # 빛 점 하나
    p.box(10, 11, 5, 10, -2, 3, "plate")         # 바깥 덧판 (계단)
    p.box(11, 12, 6, 9, -1, 2, "trim")
    p.box(1, 10, 8, 10, -4, -3, "plate")         # 종아리 뒤판
    p.box(2, 9, 5, 7, -4, -3, "navy")
    # 무릎: 은 테두리 + 앞으로 튀어나온 계단식 무릎덮개. 태싯(Y12 아래 끝) 밑에 두어 면이 겹치지 않게
    p.box(2, 9, 10, 12, -2, 5, "trim")
    p.box(3, 8, 9, 12, 5, 6, "plate")
    p.box(4, 7, 10, 12, 6, 7, "ice_d")
    p.box(5, 6, 10, 11, 7, 8, "ice")
    # 허벅지 (사슬), |X| <= 7 로 태싯(|X| 9~10)과 떨어뜨림
    p.box(1, 7, 13, 18, -3, 3, "chain")
    p.box(2, 7, 12, 13, -2, 3, "chain")          # 아래 끝은 무릎 위에 숨긴다 (태싯 밑면 Y12 와 겹치지 않게)
    p.mirror()
    return p


# ─────────────────────────────── 몸통 ───────────────────────────────

def snowflake(cx, cy, r):
    """앞에서 본 눈꽃 무늬 (X, Y) → bool, 복셀 계단 (망토 등판용)."""
    def fn(X, Y):
        dx, dy = X - cx, Y - cy
        ax, ay = np.abs(dx), np.abs(dy)
        arm = ((ax < 1) & (ay < r)) | ((ay < 1) & (ax < r)) | ((np.abs(ax - ay) < 1) & (ax < r * 0.72))
        bar = ((ay > r - 3) & (ay < r - 2) & (ax < 2.0)) | ((ax > r - 3) & (ax < r - 2) & (ay < 2.0))
        core = (ax < 2) & (ay < 2)
        return arm | bar | core
    return fn


def flake6(cx, cy, r, w=0.62, branch=True):
    """여섯 갈래 눈꽃: 세로 갈래 2 + 30도 갈래 4, 각 갈래 가운데에 곁가지 한 쌍."""
    def fn(X, Y):
        dx, dy = X - cx, Y - cy
        m = np.zeros(np.shape(dx), dtype=bool)
        for k in range(6):
            th = math.radians(90 + 60 * k)
            c, s = math.cos(th), math.sin(th)
            a = dx * c + dy * s
            b = -dx * s + dy * c
            m |= (a > 0) & (a < r) & (np.abs(b) < (0.75 if k % 3 == 0 else w))
            if branch:
                a0 = r * 0.5
                for sg in (-1, 1):
                    bc, bs = math.cos(math.radians(55)), sg * math.sin(math.radians(55))
                    ra, rb = a - a0, b
                    t = ra * bc + rb * bs
                    d = np.abs(-ra * bs + rb * bc)
                    m |= (t > 0) & (t < r * 0.42) & (d < 0.6)
        return m
    return fn


TORSO_PIVOT = (0, 22, 0)
SH_Y = 31


def pauldron(p):
    """+X 쪽 견갑 (몸통에 붙어 있다 → 팔을 휘둘러도 어깨에 남는다). mirror 로 오른쪽도.
    계단식 돔(위로 갈수록 좁아짐) + 아래로 갈수록 바깥/아래로 벌어지는 판 2장, 판마다 은 테두리 한 줄.
    바깥으로 기운 큰 얼음 가시 3개."""
    # 아래 판 (가장 바깥, 가장 아래)
    p.box(13, 22, 27, 30, -6, 6, "armor")
    p.box(13, 22, 27, 28, -6, 6, "trim")
    p.box(21, 22, 28, 30, -5, 5, "plate")
    # 가운데 판
    p.box(11, 21, 30, 33, -6, 6, "plate")
    p.box(11, 21, 30, 31, -6, 6, "trim")
    # 돔
    p.box(9, 19, 33, 36, -6, 6, "armor")
    p.box(10, 18, 36, 38, -5, 5, "armor")
    p.box(11, 16, 38, 39, -4, 4, "plate")
    p.box(12, 15, 39, 40, -3, 3, "frost")         # 눈 덮인 꼭대기
    p.box(11, 16, 38, 39, -4, -3, "frost")
    # 돔 옆면 리벳
    for z in (-4, 0, 4):
        p.box(19, 20, 34, 35, z, z + 1, "trim")
    # 얼음 가시: 바깥으로 크게 하나, 앞뒤로 작게 둘. 모두 어깨 피벗에서 10칸 안 → 대검을 치켜들 때
    # 주먹/코등이/날(피벗에서 10.5칸 밖을 지난다)이 가시를 뚫지 않는다
    p.tube([(16, 36.5, -1), (19.5, 38.3, -2.5), (23.2, 40.2, -4)], taper(2.6, 0.75), "ice")
    p.tube([(14, 38, 2.5), (14.8, 39.6, 4), (15.3, 40.4, 5.5)], taper(1.6, 0.7), "ice_d")
    p.tube([(14, 38, -2.5), (15.2, 39.3, -5.5), (16, 39.8, -8)], taper(1.6, 0.7), "ice_d")


def make_torso():
    names = ["armor", "plate", "trim", "chain", "ice", "ice_d", "frost", "dark", "gem", "cape", "gold", "navy"]
    p = P(names, TORSO_PIVOT, seed=2)
    # 허리 아래 판(태싯) 2단: 아래로 갈수록 넓어지고 앞으로 나온다 (끝 Y12 → 무릎과 정강이가 1.5블록 보인다)
    p.box(-9, 9, 14, 17, -6, 6, "armor")
    p.box(-9, 9, 14, 15, -6, 6, "navy")
    p.box(-10, 10, 12, 14, -7, 7, "plate")
    p.box(-10, 10, 12, 13, -7, 7, "trim")
    p.unbox(-2, 2, 11, 16, 4, 8)                          # 가운데 앞 틈 (휘장 자리)
    p.unbox(-11, 11, 11, 15, -2, 2)                       # 옆 트임 (허벅지가 보이게)
    # 앞 휘장 (천, 너덜너덜한 끝, 금 고리 하나)
    p.box(-2, 2, 6, 17, 5, 7, "cape")
    for x, yb in ((-2, 4), (-1, 3), (0, 5), (1, 4)):
        p.box(x, x + 1, yb, 6, 5, 7, "cape")
    p.box(-2, 2, 14, 15, 5, 8, "gold")
    # 허리띠 + 금 버클
    p.box(-9, 9, 17, 20, -6, 6, "trim")
    p.box(-3, 3, 16, 21, 6, 7, "gold")
    p.box(-2, 2, 17, 20, 6, 7, "navy")
    p.box(-1, 1, 17, 20, 7, 8, "gold")
    # 배: 판 두 줄 (사이는 짙은 홈), 옆은 사슬
    p.box(-7, 7, 20, 25, -5, 5, "chain")
    p.box(-6, 6, 20, 22, -5, 6, "plate")
    p.box(-6, 6, 23, 25, -5, 6, "plate")
    p.box(-6, 6, 22, 23, -5, 5, "navy")
    p.box(-1, 1, 20, 25, 6, 7, "armor")                    # 가운데 등줄
    # 가슴: 계단식으로 위가 넓어지는 흉갑
    p.box(-8, 8, 25, 27, -6, 6, "armor")
    p.box(-9, 9, 27, 29, -6, 6, "armor")
    p.box(-10, 10, 29, 33, -6, 6, "armor")
    p.box(-9, -1, 25, 32, 6, 7, "plate")                   # 가슴 판 (도드라짐)
    p.box(1, 9, 25, 32, 6, 7, "plate")
    p.box(-10, 10, 32, 33, -6, 6, "trim")                  # 위 테두리 (앞은 판으로 덮어 서리 깃과 떨어뜨림)
    p.box(-9, 9, 32, 33, 6, 7, "plate")
    p.box(-1, 1, 25, 32, 6, 7, "armor")
    # 가슴 옆면: 이음 줄 + 리벳
    p.box(9, 10, 29, 30, -5, 5, "plate")
    for z in (-4, 0, 4):
        p.box(9, 10, 31, 32, z, z + 1, "trim")
        p.box(8, 9, 26, 27, z, z + 1, "trim")
    # 눈꽃 문장: 작은 짙은 바탕 + 은 여섯 갈래 + 빛나는 심
    cy = 28
    p.fill(lambda X, Y, Z: (np.hypot(X, Y - cy) < 2.3) & (Z > 6) & (Z < 7.5), "navy")
    p.fill(lambda X, Y, Z: flake6(0, cy, 5.2)(X, Y) & (Z > 6) & (Z < 8), "trim")
    p.fill(lambda X, Y, Z: (np.abs(X) < 1) & (np.abs(Y - cy) < 1) & (Z > 6) & (Z < 9), "gem")
    # 등판 (이음 줄 + 리벳), 등줄은 Y25 에서 멈춘다 (망토 안쪽 면과 떨어뜨림)
    p.box(-8, 8, 21, 32, -7, -6, "plate")
    p.box(-8, 8, 26, 27, -7, -6, "armor")
    p.box(-1, 1, 17, 25, -8, -6, "trim")
    for x in (-6, 5):
        p.box(x, x + 1, 23, 24, -8, -7, "trim")
    # 어깨를 잇는 판 + 견갑
    p.box(-13, 13, 27, 33, -6, 6, "armor")               # 견갑 안쪽 면을 덮는다 (팔과 면이 겹치지 않게)
    pauldron(p)
    # 목가리개 + 서리 털 깃 (깃은 몸통에만, 망토에는 없다)
    p.box(-5, 5, 32, 34, -4, 4, "navy")
    p.fill(lambda X, Y, Z: (Y > 32) & (Y < 34) & ((X / 9.0) ** 2 + (Z / 6.2) ** 2 <= 1)
           & ((X / 5.8) ** 2 + (Z / 4.4) ** 2 > 1), "frost")
    p.mirror()
    return p


# ─────────────────────────────── 머리 ───────────────────────────────
NECK = (0, 34, 0)            # 그린 좌표의 목 (실제 보스 좌표는 HEAD_SHIFT 만큼 위: 35)
HEAD_SHIFT = (0, 1, 0)


def make_head():
    names = ["armor", "plate", "trim", "ice", "ice_d", "frost", "snow", "bone", "dark", "gem", "eye", "eye_rim",
             "chain", "gold", "navy"]
    p = P(names, NECK, seed=3, shift=HEAD_SHIFT)
    p.box(-2, 2, 31, 36, -2, 2, "chain")                 # 목
    # 짙은 남색 턱받이(후드 테): 이빨과 하얀 서리 깃 사이를 2칸 끊는다
    p.box(-6, 6, 33, 35, -3, 7, "navy")
    p.box(-5, 5, 35, 36, 3, 7, "navy")
    p.box(-7, -5, 33, 42, -4, 3, "navy")                  # 볼 테 (실제 Y34 = 서리 깃 꼭대기 위)
    p.box(5, 7, 33, 42, -4, 3, "navy")
    # 해골 (상아색): 머리통 + 턱
    p.box(-5, 5, 38, 45, -4, 5, "bone")
    p.box(-4, 4, 35, 38, -3, 5, "bone")
    p.box(-6, -5, 38, 41, 0, 5, "bone")                  # 광대
    p.box(5, 6, 38, 41, 0, 5, "bone")
    # 눈: 짙은 눈구멍 안 2x2 흰빛 심 + 바깥 위 청록 한 칸 (찡그린 눈매)
    for sx in (-1, 1):
        x0, x1 = (1, 5) if sx > 0 else (-5, -1)
        p.unbox(x0, x1, 39, 42, 2, 6)
        p.box(x0, x1, 39, 42, 2, 3, "dark")
        ex0, ex1 = (1, 3) if sx > 0 else (-3, -1)
        p.box(ex0, ex1, 39, 41, 2, 5, "eye")
        rx0 = 3 if sx > 0 else -4
        p.box(rx0, rx0 + 1, 40, 42, 2, 4, "eye_rim")
    p.box(-1, 1, 41, 42, 3, 5, "dark")
    # 코
    p.unbox(-1, 1, 37, 39, 3, 6)
    p.box(-1, 1, 37, 39, 3, 4, "dark")
    # 이빨: 뼈/어둠 번갈아
    p.box(-4, 4, 35, 37, 4, 5, "dark")
    for x in range(-4, 4):
        if x % 2 == 0:
            p.box(x, x + 1, 34, 37, 5, 6, "bone")
    # 이마 투구: 화난 V 자 눈썹
    p.box(-6, 6, 42, 47, -6, 5, "armor")
    p.box(-6, 6, 42, 44, 5, 6, "plate")
    p.box(-5, 5, 44, 46, 5, 6, "armor")
    p.box(-1, 1, 41, 42, 5, 6, "plate")
    for x in (-4, -3, 2, 3):
        p.box(x, x + 1, 42, 43, 5, 6, "armor")
    p.unbox(-6, -5, 42, 43, 5, 6)
    p.unbox(5, 6, 42, 43, 5, 6)
    # 뒤통수: 판 이음, 리벳, 가운데 볏, 고드름 갈기
    p.box(-6, 6, 35, 47, -6, -3, "armor")
    p.box(-7, 7, 40, 41, -7, -3, "plate")                # 가로 이음 띠
    p.box(-1, 1, 36, 48, -7, -6, "trim")                 # 세로 볏
    for x in (-5, 4):
        for y in (37, 43):
            p.box(x, x + 1, y, y + 1, -7, -6, "trim")
    p.box(-6, 6, 35, 36, -7, -3, "trim")
    for i, x in enumerate((-5.5, -3.5, 3.5, 5.5)):       # 고드름 갈기
        p.spike(x, 36, -6.5, (2, 3, 3, 2)[i], 1.0, "ice", down=True)
    # 금 왕관 띠 + 가운데 청록 보석 하나
    p.box(-7, 7, 45, 47, -7, 7, "gold")
    p.box(-6, 6, 47, 48, -6, 6, "armor")
    p.box(-2, 2, 44, 48, 7, 8, "gold")
    p.box(-1, 1, 45, 47, 7, 9, "gem")
    for x in (-5, 4):
        p.box(x, x + 1, 45, 47, 7, 8, "ice_d")
    # 서리 왕관 가시 (하얀 결정, 계단식 사각뿔) — 뿔(짙은 얼음)과 구별된다
    p.spike(0, 47, 4.5, 6, 2.0, "snow", tip="frost")
    for sx in (-1, 1):
        p.spike(sx * 3.5, 47, 5, 3, 1.0, "snow")
        p.spike(sx * 6, 47, 1.5, 4, 1.0, "snow", tip="frost")
        p.spike(sx * 3, 47, -5, 3, 1.0, "snow")
    # 뿔: 관자놀이에서 바깥으로 뻗다가 위로 휘어 오른다 (짙은 얼음, 끝만 밝게)
    for sx in (-1, 1):
        pts = [(sx * 6.5, 43, -1), (sx * 9, 44, -2), (sx * 10.6, 46, -2.5), (sx * 11.1, 48.5, -2),
               (sx * 10.4, 51, -1)]
        p.tube(pts, taper(2.0, 0.7), "ice_d")
        p.tube(pts[3:], taper(1.0, 0.7), "ice")
    return p


# ─────────────────────────────── 팔 ───────────────────────────────
R_SHOULDER = (-12, SH_Y, 0)
L_SHOULDER = (12, SH_Y, 0)
SWORD_X = -20                    # 대검 가운데 선 (보스 좌표, 칸 경계)
GRIP = (21.5, 10)                # 주먹/손잡이 가운데 (Y, Z)
TILT = 33                        # 평소 대검 기울기 (앞으로)


def make_right_arm():
    names = ["armor", "plate", "trim", "chain", "navy", "dark", "gold"]
    p = P(names, R_SHOULDER, seed=4)
    # 위팔 (견갑 안에서 시작)
    p.tube([(-12.5, 30, 0), (-16.5, 23, -0.5)], 2.7, "chain")
    p.tube([(-14.5, 29, 0), (-17.5, 24, -0.5)], 2.0, "plate")
    # 팔꿈치
    p.ball(-17, 22.5, -0.5, 3.2, 2.6, 3.2, "trim")
    p.box(-21, -19, 21, 24, -3, 2, "armor")
    # 아래팔: 앞으로 굽힌 완갑
    p.tube([(-17.5, 22, 1.5), (-19.5, 21.5, 6)], 2.9, "armor")
    p.box(-23, -16, 20, 23, 3, 5, "trim")                # 완갑 테
    # 주먹: 대검과 같이 기울어진 국소 좌표. 손잡이(X -21..-19, 국소 Z 9..11)를 감싼다
    t = Tilt(p, GRIP[0], GRIP[1], TILT)
    gy, gz = GRIP
    t.box(-24, -16, gy - 4, gy + 4, gz - 4, gz + 4, "armor")     # 손바닥/손등
    t.box(-24, -16, gy - 4, gy + 4, gz - 5, gz - 4, "trim")      # 손목 테
    # 손가락 4개: 국소 Y 로 쌓인 은 판(앞면), 마디가 바깥 앞 모서리에서 한 칸씩 튀어나온다
    for k in range(4):
        y0 = gy - 4 + 2 * k
        t.box(-24, -17, y0, y0 + 2, gz + 4, gz + 5, "trim" if k % 2 == 0 else "plate")
        t.box(-25, -21, y0, y0 + 2, gz + 3, gz + 6 - (k % 2), "trim" if k % 2 == 0 else "plate")
        t.box(-25, -24, y0, y0 + 2, gz - 3, gz + 3, "armor" if k % 2 == 0 else "navy")
    # 엄지: 손잡이 위로 감아 쥔다 (몸 쪽)
    t.box(-18, -15, gy + 1, gy + 4, gz - 1, gz + 4, "plate")
    t.box(-18, -15, gy + 3, gy + 4, gz - 1, gz + 4, "trim")
    p.clear(lambda X, Y, Z: Y > 27)      # 견갑 속(Y27 위)은 비운다: 휘둘러도 견갑 안에 숨는 자리, 평소엔 면이 겹친다
    return p


def make_left_arm():
    names = ["armor", "plate", "trim", "chain", "ice", "ice_d", "navy", "claw"]
    p = P(names, L_SHOULDER, seed=5)
    # 위팔
    p.tube([(12.5, 30, 0), (16.5, 23, -0.5)], 2.7, "chain")
    p.tube([(14.5, 29, 0), (17.5, 24, -0.5)], 2.0, "plate")
    p.ball(17, 22.5, -0.5, 3.2, 2.6, 3.2, "trim")
    # 아래팔: 앞으로, 살짝 위로 (발톱이 허리 높이)
    p.tube([(17, 22, 1), (16.5, 23, 7.5)], 2.9, "armor")
    p.box(12, 21, 20, 26, 7, 9, "trim")                  # 손목 테
    # 건틀릿 손등 + 마디판
    p.box(10, 22, 20, 26, 9, 13, "armor")
    p.box(10, 22, 24, 26, 9, 14, "plate")
    p.box(13, 19, 26, 27, 9, 12, "plate")
    p.box(15, 17, 26, 27, 10, 12, "ice_d")
    p.box(10, 22, 20, 21, 9, 13, "navy")
    # 발톱 4개: 3칸 간격(2칸 굵기 + 1칸 틈), 앞으로 뻗다가 아래로 갈고리. 끝 2~3칸만 빛난다
    for i, x in enumerate((11, 14, 17, 20)):
        L = 1.0 if i in (1, 2) else 0.8
        pts = [(x, 23, 12.5), (x, 23.5, 15 + L), (x, 22, 17.5 + 1.5 * L), (x, 19.5, 18.5 + 2 * L),
               (x, 17, 18 + 2 * L)]
        p.tube(pts, taper(1.0, 0.7), "ice_d")
        p.tube(pts[2:4], taper(0.9, 0.8), "ice")
        p.tube(pts[-2:], taper(0.85, 0.7), "claw")
        p.box(x - 1, x + 1, 22, 25, 13, 14, "trim")      # 손가락 끝 은 고리
    p.tube([(10, 22, 11), (8.5, 22, 14), (8, 20, 16), (8.5, 18, 16)], taper(1.0, 0.7), "ice_d")   # 엄지 발톱
    p.tube([(8, 20, 16), (8.5, 18, 16)], 0.8, "claw")
    p.clear(lambda X, Y, Z: Y > 27)
    return p


# ─────────────────────────────── 대검 ───────────────────────────────

def make_sword():
    names = ["armor", "trim", "ice", "ice_d", "blade", "frost", "gold", "grip", "navy", "edge", "rune"]
    p = P(names, R_SHOULDER, vox=0.5, size=96, seed=6)
    t = Tilt(p, GRIP[0], GRIP[1], TILT)
    cx = SWORD_X
    gy, cz = GRIP
    # 손잡이 (밝게 감은 끈) + 주먹 바로 밑의 금 칼자루 끝
    t.box(cx - 1, cx + 1, gy - 6, gy - 4, cz - 1, cz + 1, "grip")       # 주먹 밖으로 보이는 부분만 (주먹 안은 비움:
    t.box(cx - 1, cx + 1, gy + 4, gy + 5, cz - 1, cz + 1, "grip")       #  같은 칸을 두 모델이 채우면 면이 겹친다)
    t.box(cx - 2, cx + 2, gy - 8, gy - 5, cz - 2, cz + 2, "gold")
    t.box(cx - 1, cx + 1, gy - 9, gy - 8, cz - 1, cz + 1, "gold")
    t.box(cx - 1, cx + 1, gy - 7, gy - 6, cz - 3, cz + 3, "ice_d")
    t.box(cx - 3, cx + 3, gy - 7, gy - 6, cz - 1, cz + 1, "ice_d")
    # 코등이: 두꺼운 금 가로대, 끝은 아래로 꺾인 은 발톱 (날과 평행한 장식 없음)
    g0 = gy + 5
    t.box(cx - 6, cx + 6, g0, g0 + 3, cz - 2, cz + 2, "gold")
    t.box(cx - 4, cx + 4, g0 + 3, g0 + 4, cz - 2, cz + 2, "gold")
    t.box(cx - 3, cx + 3, g0 - 1, g0, cz - 2, cz + 2, "navy")
    for s in (-1, 1):
        xa, xb = (cx + 6, cx + 8) if s > 0 else (cx - 8, cx - 6)
        t.box(xa, xb, g0 - 1, g0 + 3, cz - 2, cz + 2, "trim")
        xa, xb = (cx + 7, cx + 8) if s > 0 else (cx - 8, cx - 7)
        t.box(xa, xb, g0 - 3, g0 - 1, cz - 1, cz + 1, "trim")
    t.box(cx - 2, cx + 2, g0, g0 + 3, cz + 2, cz + 3, "navy")
    t.box(cx - 1, cx + 1, g0, g0 + 3, cz + 2, cz + 4, "ice")   # 코등이 가운데 얼음 (빛 없음)
    t.box(cx - 2, cx + 2, g0, g0 + 3, cz - 3, cz - 2, "navy")
    t.box(cx - 1, cx + 1, g0, g0 + 3, cz - 4, cz - 2, "ice")

    # 날: 국소 Y y0 → y1. 가장자리(빛), 몸통(짙은 얼음), 가운데 등줄(밝은 얼음 + 룬)
    y0, y1 = g0 + 4, gy + 37

    def half_w(Y):
        tt = (Y - y0) / (y1 - y0)
        w = 4.6 + 0.8 * np.sin(np.clip(tt, 0, 1) * math.pi * 0.85)
        tp = np.clip((1 - tt) / 0.26, 0, 1)
        w = np.where(tt > 0.74, 0.6 + (w - 0.6) * tp ** 0.9, w)
        notch = ((np.floor(Y) - y0) % 4 == 1) & (tt > 0.06) & (tt < 0.7)    # 톱니처럼 들어간 얼음 이빨
        return np.floor(w + 0.5) - np.where(notch, 1, 0)

    def blade(X, Y, Z):
        return (Y > y0 - 0.5) & (Y < y1) & (np.abs(X - cx) < half_w(Y))

    t.fill(lambda X, Y, Z: blade(X, Y, Z) & (np.abs(Z - cz) < 1.1), "edge")
    t.fill(lambda X, Y, Z: blade(X, Y, Z) & (np.abs(X - cx) < half_w(Y) - 1) & (np.abs(Z - cz) < 2), "blade")
    t.fill(lambda X, Y, Z: blade(X, Y, Z) & (np.abs(X - cx) < np.minimum(1, half_w(Y) - 1)) & (np.abs(Z - cz) < 3)
           & (Y < y1 - 4), "ice")
    # 등줄 양옆의 빛나는 룬 (앞뒤, 3칸마다 끊김)
    t.paint(lambda X, Y, Z: (Y > y0 + 1) & (Y < y1 - 6) & (np.abs(np.abs(X - cx) - 1.5) < 0.6)
            & (((np.floor(Y) - y0) % 3) != 0), "rune", only=["blade"])
    return p


# ─────────────────────────────── 망토 ───────────────────────────────
CAPE_PIVOT = (0, 32, -8)


def make_cape():
    names = ["cape", "cape_in", "frost", "ice", "trim", "gold", "rune"]
    p = P(names, CAPE_PIVOT, vox=0.5, size=80, seed=7)
    rng = random.Random(77)
    top, bottom = 32, 3

    def dd(Y):
        return np.clip((top - Y) / (top - bottom), 0, 1)

    def back(Y):
        return -8 - np.floor(dd(Y) ** 1.35 * 12 + 0.5)        # 아래로 갈수록 뒤로 12칸 펄럭

    def halfw(Y):
        return np.floor(9 + dd(Y) ** 1.2 * 6)                  # 아래로 갈수록 넓게 (밑단 반폭 15)

    FOLD = (0, 0, 1, 2, 2, 2, 1, 0)                             # 주름: 8칸 주기, 깊이 2

    def fold(X):
        i = (np.floor(X).astype(int) % 8 + 8) % 8
        return np.take(np.array(FOLD), i)

    def fold_y(X, Y):
        # 위쪽(어깨)은 주름이 얕고 아래로 갈수록 깊다
        return np.floor(fold(X) * np.clip(dd(Y) * 2.2, 0, 1) + 0.5)

    cols = {c: bottom + rng.choice((0, 0, 1, 2, 3, 4, 6, 7)) for c in range(-8, 8)}   # 2칸 기둥마다 밑단 길이
    hem = np.vectorize(lambda X: cols.get(int(math.floor(X / 2)), 99))

    def front_z(X, Y):
        return back(Y) - fold_y(X, Y)

    def sheet(X, Y, Z):
        zb = front_z(X, Y)
        return (Y < top) & (Y > hem(X)) & (np.abs(X) < halfw(Y)) & (Z < zb) & (Z > zb - 2)

    def outer(X, Y, Z):
        return sheet(X, Y, Z) & (Z < front_z(X, Y) - 1)

    p.fill(sheet, "cape_in")
    p.fill(outer, "cape")
    p.fill(lambda X, Y, Z: sheet(X, Y, Z) & (Y < hem(X) + 3.5), "frost")          # 밑단 서리
    p.fill(lambda X, Y, Z: sheet(X, Y, Z) & (np.abs(X) > halfw(Y) - 1), "frost")   # 옆단
    for c, yb in cols.items():                                                     # 고드름 (바닥 Y0.5 위에서 멈춤)
        if rng.random() < 0.6:
            x = c * 2 + 1
            zb = float(front_z(np.array(x - 0.5), np.array(yb + 0.5)))
            h = min(rng.choice((3, 4, 5)), yb + 0.5)
            if h >= 2:
                p.spike(x, yb + 1, zb - 1, h, 1.0, "ice", down=True)
    for _ in range(5):                                                              # 해진 구멍
        x, y = rng.randrange(-11, 10), rng.randrange(7, 14)
        p.clear(lambda X, Y, Z, x=x, y=y: (X > x) & (X < x + 2) & (Y > y) & (Y < y + 2) & (Z < -9))
    # 등: 은 점선 두 줄 + 가운데 빛나는 눈꽃 (은 고리 안)
    for x in (-7, 6):
        p.paint(lambda X, Y, Z, x=x: outer(X, Y, Z) & (X > x) & (X < x + 1) & (Y > 8) & (Y < 21)
                & ((np.floor(Y) % 3) != 0), "trim")
    flake = snowflake(0, 22, 5.2)
    p.paint(lambda X, Y, Z: outer(X, Y, Z) & flake(X, Y) & (np.hypot(X, Y - 22) < 5.2), "rune")
    p.paint(lambda X, Y, Z: outer(X, Y, Z) & (np.abs(np.hypot(X, Y - 22) - 6.2) < 0.55), "trim")
    # 어깨 걸쇠 (금)
    for x in (-9, 8):
        p.box(x, x + 1, 29, 32, -10, -8, "gold")
    return p


# ─────────────────────────────── 얼음 파편 ───────────────────────────────

def make_shard():
    """가늘고 긴 얼음 결정: 마름모 단면(|x|+|z| <= h), 위아래가 계단식으로 1칸 끝까지 가늘어진다.
    가운데 칸을 (0.5, 0.5) 에 두어 1칸 끝이 가능하다 (회전 중심에서 반 칸 비켜남 → 돌 때 살짝 흔들림).
    네 면을 서로 다른 명도로, 네 모서리(마름모 꼭짓점 줄)는 반짝이는 심."""
    names = ["ice", "ice_d", "frost", "plate", "spark"]
    p = P(names, (0, 0, 0), seed=8)
    rows = [0, 1, 1, 2, 2, 2, 3, 3, 2, 2, 1, 1, 0]            # 위(Y 6.5) → 아래(Y -5.5), 가운데가 볼록
    top = 6.5

    def h_of(Y):
        i = np.clip(np.round(top - Y).astype(int), 0, len(rows) - 1)
        inside = (Y < top + 0.6) & (Y > top - len(rows) + 0.4)
        return np.where(inside, np.take(np.array(rows), i), -1)

    def body(X, Y, Z):
        dx, dz = np.abs(X - 0.5), np.abs(Z - 0.5)
        return dx + dz <= h_of(Y)

    p.fill(body, "ice")
    p.paint(lambda X, Y, Z: (X - 0.5 > 0) & (Z - 0.5 >= 0), "frost")
    p.paint(lambda X, Y, Z: (X - 0.5 < 0) & (Z - 0.5 <= 0), "ice_d")
    p.paint(lambda X, Y, Z: (X - 0.5 <= 0) & (Z - 0.5 > 0), "plate")
    p.paint(lambda X, Y, Z: (((np.abs(X - 0.5) < 0.1) & (np.abs(Z - 0.5) > 1.5)) | ((np.abs(Z - 0.5) < 0.1)
            & (np.abs(X - 0.5) > 1.5))) & (Y > -3) & (Y < 3), "spark")
    p.paint(lambda X, Y, Z: (Y > 5.4) | (Y < -4.4), "frost")
    p.paint(lambda X, Y, Z: (np.abs(X - 0.5) + np.abs(Z - 0.5) > 2.5), "ice")        # 볼록한 띠
    return p


# ─────────────────────────────── 조립 ───────────────────────────────
BOB = {"type": "bob", "amplitude": 0.04, "period": 60, "phase": 0.0}
SHARD_ORBIT = {"radius": 1.25, "height": 7.6, "speed": 3.0}


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
             {"type": "swing", "axis": "x", "angle": -118, "ticks": 14}]
    arm_l = [dict(BOB), {"type": "sway", "axis": "x", "angle": 4, "period": 60, "phase": 0.5},
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
    for i, ph in enumerate((0.0, 120.0, 240.0)):
        parts.append(entry(f"shard_{i + 1}", "shard",
                           [{"type": "orbit", "radius": SHARD_ORBIT["radius"], "speed": SHARD_ORBIT["speed"],
                             "phase": ph, "height": SHARD_ORBIT["height"]},
                            {"type": "spin", "axis": "y", "speed": 6.0},
                            {"type": "bob", "amplitude": 0.12, "period": 50, "phase": i / 3}],
                           frame="world", offset=[0.0, 0.0, 0.0]))
    spec = {
        "boss": BOSS,
        "parts": parts,
        "notes": ("서리 군주 복셀 버전. 1 복셀 = 1/8 블록: 몸 파트 vox 1.0 × scale 2, 대검/망토 vox 0.5 × scale 4 "
                  "(큐브 크기 같음, 회전 중심에서 6블록까지). 키: 엉덩이 2.1블록, 투구 꼭대기 5.9블록, 서리 왕관 끝 6.6블록. "
                  "몸 폭 약 2.8블록(견갑 포함, 히트박스 1.56 을 덮음). "
                  "보스 오른손 = -X (대검), 왼손 = +X (얼음 발톱), 앞 = +Z. 모든 포즈는 모델에 구워 넣어 rotation 은 0. "
                  "대검은 평소 앞으로 33도 기울여 든다(끝: 6.5블록 높이, 3.8블록 앞). sword 는 right_arm 과 같은 피벗(오른 어깨)·"
                  "같은 anims 라야 손에 붙어 있다. swing -118: 최고점에서 어깨 너머로 치켜들고, 돌아오며 앞으로 내려찍어 "
                  "칼끝이 앞을 겨눈 채 끝난다. 왼팔 -75 로 발톱을 앞으로 할퀸다. 견갑은 몸통 파트에 있어 휘둘러도 어깨에 남는다. "
                  "legs 는 고정, 나머지 몸 파트는 같은 bob 으로 숨쉰다. shard 3개는 같은 모델, frame=world orbit: "
                  f"반지름 {SHARD_ORBIT['radius']}블록, 높이 {SHARD_ORBIT['height']}블록 = 왕관/뿔 끝(6.6블록) 위를 도는 후광 "
                  "(몸, 견갑, 대검, 휘두른 팔과 어느 각도에서도 겹치지 않음). "
                  "강한 발광: 눈(흰빛 심), 가슴 눈꽃 심, 왕관 보석, 대검 날(flow). 약한 발광: 발톱 끝, 파편 심(sparkle), "
                  "정강이 점, 망토 등 눈꽃(pulse)."),
    }
    spec["_counts"] = {k: len(m.elements) for k, m in models.items()}
    with open(os.path.join(HERE, MODULE + ".rig.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in spec.items() if not k.startswith("_")}, f, ensure_ascii=False, indent=2)
    spec["_models"] = models
    return spec


def zrender(parts, size=512, yaw=-35, pitch=25, **kw):
    """mc3d.render 와 같지만 겹친 면의 앞뒤 순서를 바로잡는다.
    mc3d.render 는 가까운 면을 먼저 그려서(정렬 방향이 반대) 멀리 있는 면이 앞을 덮는다
    (시험: 앞판 위에 붙인 작은 큐브가 앞판에 가려짐). 화면 좌표는 그대로 두고 깊이만 뒤집는 반사
    V^T·diag(1,1,-1)·V 를 각 파트 행렬 앞에 곱하면, 면 고르기(뒷면 생략)는 그대로이고 그리는 순서만 바르게 된다."""
    import mc3d
    V = mc3d._rot_matrix("x", pitch) @ mc3d._rot_matrix("y", yaw)
    Fm = np.eye(4)
    Fm[:3, :3] = V.T @ np.diag([1.0, 1.0, -1.0]) @ V
    fixed = [(m, Fm @ (np.eye(4) if M is None else np.array(M, dtype=float))) for m, M in parts]
    return _ORIG_RENDER(fixed, size=size, yaw=yaw, pitch=pitch, **kw)


def _orig_render():
    import mc3d
    return getattr(mc3d.render, "_orig", mc3d.render)


_ORIG_RENDER = None


class _fixed_depth:
    """with 블록 안에서 mc3d.render 를 zrender 로 바꿔 둔다 (wkit.rig_preview 가 바른 순서로 그리게)."""

    def __enter__(self):
        import mc3d
        global _ORIG_RENDER
        _ORIG_RENDER = _orig_render()
        zrender._orig = _ORIG_RENDER
        mc3d.render = zrender
        return self

    def __exit__(self, *a):
        import mc3d
        mc3d.render = _ORIG_RENDER


def _view(parts, yaw, pitch, size=360, bg=(28, 26, 36, 255)):
    """yaw 0 = 정면(+Z 쪽에서 봄)."""
    with _fixed_depth():
        return zrender(parts, size=size, yaw=yaw, pitch=pitch, bg=bg)


def orbit_spec(spec, extra_deg=40.0):
    """미리보기용: orbit 파트의 offset 을 실제 궤도 위치로 옮긴 spec 사본 (wkit.rig_preview 는 orbit 을 모른다)."""
    out = copy.deepcopy({k: v for k, v in spec.items() if not k.startswith("_")})
    for p in out["parts"]:
        for a in p["anims"]:
            if a["type"] == "orbit":
                th = math.radians(a["phase"] + extra_deg)
                p["offset"] = [round(a["radius"] * math.cos(th), 4), round(p["offset"][1] + a["height"], 4),
                               round(a["radius"] * math.sin(th), 4)]
    return out


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
    models = spec["_models"]
    by_id = {p["id"]: models[p["model"].split(f"boss/{BOSS}_", 1)[1]] for p in spec["parts"]}
    clean = {k: v for k, v in spec.items() if not k.startswith("_")}
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    font = FONT if os.path.exists(FONT) else None
    # 1) 조립 미리보기: wkit.rig_preview (파편을 실제 궤도 위치에 둔 spec 사본)
    with _fixed_depth():
        wkit.rig_preview(orbit_spec(spec), by_id, os.path.join(PREVIEW_DIR, f"{BOSS}_voxel.png"), NAME_KO, size=520)
    # 2) 파트 확대
    counts = spec["_counts"]
    imgs, labels = [], []
    for k in ("head", "torso", "legs", "cape", "right_arm", "left_arm", "sword", "shard"):
        m = models[k]
        for (yw, pt, tag) in ((-30, 14, "앞"), (150, 14, "뒤")):
            imgs.append(_view([(m, None)], yw, pt))
            labels.append(f"{k} {tag} ({counts[k]})")
    imgs.append(_view(_rig_parts(clean, by_id, swing=1.0), -65, 8))
    labels.append("스윙 최고점 (치켜듦)")
    imgs.append(_view(_rig_parts(clean, by_id, swing=0.5), -90, 4))
    labels.append("스윙 중간 (옆)")
    imgs.append(_view(_rig_parts(clean, by_id), -90, 4))
    labels.append("평소 (옆) = 내려찍기 끝")
    imgs.append(_view(_rig_parts(clean, by_id), 0, 4))
    total = sum(counts.values()) + 2 * counts["shard"]
    labels.append(f"정면 (element {total})")
    contact_sheet(imgs, labels, cols=4, cell=360, font=font).save(os.path.join(PREVIEW_DIR, f"{BOSS}_voxel_parts.png"))
    # 3) 작업용 큰 그림 (scratch)
    os.makedirs(os.path.join(HERE, "_scratch", MODULE), exist_ok=True)
    big = [_view(_rig_parts(clean, by_id), y, p, size=700) for (y, p) in ((-25, 10), (25, 10))]
    contact_sheet(big, ["dev 앞 왼쪽", "dev 앞 오른쪽"], cols=2, cell=700, font=font).save(
        os.path.join(HERE, "_scratch", MODULE, "dev_big.png"))
    small = [_view(_rig_parts(clean, by_id), y, p, size=260) for (y, p) in ((0, 4), (-35, 10), (180, 6))]
    contact_sheet(small, ["260 정면", "260 3/4", "260 뒤"], cols=3, cell=260, font=font).save(
        os.path.join(HERE, "_scratch", MODULE, "dev_small.png"))


if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
    os.makedirs(root, exist_ok=True)
    spec = build(root)
    c = spec["_counts"]
    total = sum(c.values()) + 2 * c["shard"]
    print("elements:", c, "total(with 3 shards):", total)
    previews(spec)
    print("ok")
