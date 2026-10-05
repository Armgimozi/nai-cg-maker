"""
blades 그룹: 검과 카타나 12 자루.
각 무기는 이름/속성/등급에 맞게 따로 디자인했다 (같은 틀을 돌려 쓰지 않는다).
  basic  : 소박한 재료, 부품 적게, 빛 없음
  island : 섬 재료로 만든 개성, 아주 작은 빛 포인트까지만
  flame  : 속성이 분명한 모양 + 빛나는 심지
  boss / prism : 화려하고 유일한 모양 + 아우라 (이 그룹에서는 성검, 혈월의 카타나, 태양검만)
python3 blades.py  →  preview/blades.png
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, Weapon, preview_sheet  # noqa: E402


# ─────────────────────────── 작은 도구 ───────────────────────────

def sect(w, y0, y1, lo, hi, layers):
    """
    Y 구간 [y0, y1] 에서 X 가 lo(t)..hi(t) 사이인 날 단면을 층별로 칠한다 (t = 0 밑동 → 1 끝).
    layers: [(재료, cond(X, Y, Z, dl, dr, t))] 순서대로 칠함. dl/dr = 왼쪽/오른쪽 가장자리까지 거리.
    """
    def geo(X, Y):
        t = (Y - y0) / float(y1 - y0)
        tc = np.clip(t, 0, 1)
        a, b = lo(tc), hi(tc)
        return (t >= 0) & (t <= 1) & (X >= a) & (X <= b), X - a, b - X, tc

    for mat, cond in layers:
        def fn(X, Y, Z, cond=cond):
            m, dl, dr, t = geo(X, Y)
            return m & cond(X, Y, Z, dl, dr, t)
        w.fill(fn, mat)


def taper(t, t0, p=0.9):
    """t0 이후로 1 → 0 으로 줄어드는 끝 모양 계수."""
    return np.clip((1 - t) / (1 - t0), 0, 1) ** p


def ramp_in(t, t0, p=1.3):
    """t0 이후로 0 → 1 로 커지는 값 (카타나 끝 기울기 등)."""
    return np.clip((t - t0) / (1 - t0), 0, 1) ** p


def solid(w):
    """지금까지 채워진 복셀 (다시 칠하기용 마스크)."""
    return w.grid.copy() > 0


def capsule(X, Y, p0, p1, r0, r1=None):
    """2D: 선분 p0→p1 둘레 반지름 r0→r1 안쪽."""
    r1 = r0 if r1 is None else r1
    ax, ay = p1[0] - p0[0], p1[1] - p0[1]
    L2 = ax * ax + ay * ay
    t = np.clip(((X - p0[0]) * ax + (Y - p0[1]) * ay) / L2, 0, 1)
    d = np.hypot(X - p0[0] - ax * t, Y - p0[1] - ay * t)
    return d <= r0 + (r1 - r0) * t


def bands(w, ys, r, mat, h=0.9):
    """손잡이에 감은 고리 띠."""
    for y in ys:
        w.cyl(y, y + h, r, mat)


# ─────────────────────────── basic ───────────────────────────

def apprentice_sword():
    """견습생의 검: 곧은 쇠 날 + 가운데 홈(풀러), 끝이 뭉툭한 일자 가드, 가죽 손잡이, 원반 폼멜. 정직한 첫 검."""
    m = {
        "steel": Mat(["#6e747e", "#8a909a", "#a2a8b2", "#d0d4da"], "metal", seed=101),
        "edge": Mat(["#b4bac2", "#c8ced6", "#dde1e6", "#ffffff"], "metal", seed=102),
        "iron": Mat(["#25272d", "#3a3d44", "#50545c", "#7c8088"], "metal", seed=103),
        "leather": Mat(["#2a170c", "#4a2a16", "#6a3e22", "#8a5632"], "grip", seed=104),
    }
    w = Weapon(m, grip_y=8.5, kind="sword", seed=101)
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 2.6) <= 2.7) & (np.abs(Z) <= 1.5), "iron")      # 원반 폼멜
    w.cyl(4.5, 13, 1.6, "leather")
    w.box(-6.6, 6.6, 13, 15.9, -1.6, 1.6, "iron")                                          # 일자 가드
    w.fill(lambda X, Y, Z: (np.abs(X) >= 5) & (np.abs(X) <= 7.2) & (Y >= 12) & (Y <= 16.9) & (np.abs(Z) <= 1.6), "iron")
    hw = lambda t: 3.0 * taper(t, 0.8) + 0.2
    sect(w, 16, 47, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("steel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    # 풀러: 가운데 두 줄을 한 칸 파내고 어둡게
    fl = lambda X, Y: (np.abs(X) < 1) & (Y >= 17) & (Y <= 40)
    w.fill(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) <= 0.5), "iron")
    w.clear(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) > 1))
    return w


def copper_sword():
    """구리 검: 짧고 통통한 잎사귀 날(마름모 단면), 녹청 슨 네모 가드, 구리 고리 감은 나무 손잡이, 고리 폼멜."""
    m = {
        "copper": Mat(["#7a3a1c", "#a8562c", "#c86e3a", "#f0a070"], "metal", seed=111),
        "bright": Mat(["#d07a40", "#e89458", "#f8b078", "#ffe0c0"], "metal", seed=112),
        "patina": Mat(["#1e5a50", "#2e8a76", "#4ab89a", "#86e0c4"], "stone", seed=113),
        "wood": Mat(["#2e1c10", "#4e3018", "#6e4626", "#8e5e36"], "wood", seed=114),
    }
    w = Weapon(m, grip_y=11, kind="sword", seed=111)
    w.fill(lambda X, Y, Z: (np.abs(np.hypot(X, Y - 3.9) - 2.8) <= 0.95) & (np.abs(Z) <= 1.0), "copper")   # 고리 폼멜
    w.cyl(7, 15.5, 1.6, "wood")
    bands(w, [8.5, 12.5], 2.6, "copper")
    w.box(-4.1, 4.1, 15, 17.9, -2.1, 2.1, "patina")                 # 녹청 슨 네모 가드
    w.box(-4.1, 4.1, 17, 17.9, -2.1, 2.1, "copper")
    # 잎사귀 날 (마름모 단면, 가운데 등줄)
    hw = lambda t: (2.3 + 1.7 * np.sin(np.pi * t / 1.2)) * taper(t, 0.68, 0.8) + 0.3
    zf = lambda dl, dr: 0.5 + np.clip((np.minimum(dl, dr) - 1) / 1.5, 0, 1)
    sect(w, 18, 45, lambda t: -hw(t), hw, [
        ("bright", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("copper", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= zf(dl, dr))),
        ("bright", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 1) & (t < 0.86) & (np.abs(Z) <= zf(dl, dr))),
    ])
    return w


def wooden_katana():
    """목도: 나무 한 덩이를 깎은 굵고 휜 칼(둥근 단면, 둥근 끝), 검은 둥근 코등이, 손잡이에 감은 천 테이프."""
    m = {
        "oak": Mat(["#8a6236", "#a27644", "#b88a52", "#e0bc80"], "wood", seed=121),
        "dark": Mat(["#1e140e", "#36261a", "#4e3826", "#664a34"], "wood", seed=122),
        "tape": Mat(["#8a8070", "#b0a690", "#d4ccb4", "#eee8d6"], "cloth", seed=123),
    }
    w = Weapon(m, grip_y=9, kind="katana", seed=121)
    w.cyl(0, 17, 1.9, "oak", rz=1.6)
    w.cyl(0, 0.9, 1.6, "dark")                               # 닳은 손잡이 끝
    bands(w, [12.6, 14.4], 2.2, "tape", h=1.0)
    w.cyl(17, 19.9, 5.2, "dark", rz=4.4)                     # 둥근 코등이 (두툼한 가죽)
    w.cyl(20, 20.9, 3.0, "tape", rz=2.4)                     # 코등이 받침
    c = lambda t: -3.2 * t ** 2
    lo = lambda t: c(t) - 2.6 + 1.6 * ramp_in(t, 0.9, 2.0)
    hi = lambda t: c(t) + 2.6 - 3.8 * ramp_in(t, 0.88, 1.6)
    sect(w, 21, 65, lo, hi, [
        ("oak", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5))),
    ])
    return w


# ─────────────────────────── island ───────────────────────────

def wind_sword():
    """바람의 검: 바람이 지나가는 긴 구멍이 뚫린 가는 민트빛 날, 위아래로 말린 소용돌이 가드, 옥빛 손잡이."""
    m = {
        "steel": Mat(["#6a9a94", "#86b8b0", "#a4d4cc", "#e4fbf4"], "metal", seed=131),
        "edge": Mat(["#c8eee6", "#dcf8f2", "#f0fffc", "#ffffff"], "metal", seed=132),
        "silver": Mat(["#5a6470", "#8e98a4", "#c2cad4", "#eef2f6"], "metal", seed=133),
        "jade": Mat(["#0e3a2a", "#1a6a4a", "#2e9a6a", "#5ac898"], "grip", seed=134),
        "glint": Mat(["#2aa0a0", "#5ae0d8", "#a8fff4", "#ffffff"], "gem", glow=True, seed=135),
    }
    w = Weapon(m, grip_y=10, kind="sword", seed=131)
    w.ball(0, 3.2, 0, 2.1, 2.6, 2.1, "silver")               # 물방울 폼멜 + 작은 빛 구슬
    w.gem(0, 3.2, 0.9, "glint", depth=2.6)
    w.cyl(5, 15, 1.6, "jade")
    # 소용돌이 가드: 오른쪽은 위로, 왼쪽은 아래로 말린다
    w.box(-2.6, 2.6, 15, 17.9, -1.6, 1.6, "silver")
    w.tube([(2, 16.5, 0), (5, 16, 0), (7.6, 17.6, 0), (8.2, 20.4, 0), (6.6, 22, 0), (5, 21, 0), (5.4, 19.6, 0)], 0.95, "silver")
    w.tube([(-2, 16.5, 0), (-5, 17, 0), (-7.6, 15.4, 0), (-8.2, 12.6, 0), (-6.6, 11, 0), (-5, 12, 0), (-5.4, 13.4, 0)], 0.95, "silver")
    hw = lambda t: (2.8 - 0.5 * t) * taper(t, 0.74, 1.1) + 0.2
    sect(w, 18, 60, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("steel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    # 바람 구멍: 가운데를 길게 뚫는다 (양 끝은 뾰족)
    w.clear(lambda X, Y, Z: (np.abs(X) < 1.2 * np.sin(np.pi * np.clip((Y - 22) / 28, 0, 1))) & (Y > 22) & (Y < 50))
    return w


def pirate_katana():
    """해적의 카타나: 끝이 넓어지는 커틀러스형 휜 날에 물결 하몬, 등의 이 빠진 자국, 배 키 모양 코등이, 붉은 띠."""
    m = {
        "steel": Mat(["#56606a", "#68727c", "#7c8690", "#b8c2cc"], "metal", seed=141),
        "edge": Mat(["#c8d4dc", "#dce6ec", "#eef6fa", "#ffffff"], "metal", seed=142),
        "wave": Mat(["#3a8aa8", "#4aa0c0", "#6ac0dc", "#c0f0ff"], "flat", seed=148),
        "wood": Mat(["#2a120a", "#4a2210", "#6a3418", "#8a4a24"], "wood", seed=143),
        "brass": Mat(["#5a3e10", "#9a7020", "#d0a438", "#f6dc80"], "metal", seed=144),
        "navy": Mat(["#0e1430", "#1a2450", "#2a3a78", "#4058a0"], "grip", seed=145),
        "sash": Mat(["#5a0a0a", "#8a1414", "#c02424", "#e85050"], "cloth", seed=146),
        "pearl": Mat(["#8a8aa0", "#c8c8dc", "#f0f0ff", "#ffffff"], "gem", glow=True, seed=147),
    }
    w = Weapon(m, grip_y=10, kind="katana", seed=141)
    w.cyl(1, 3.9, 1.9, "brass")
    w.gem(0, 2.4, 0.9, "pearl", depth=2.6)
    w.cyl(3.5, 19, 1.6, "navy")
    w.cyl(12.5, 14.4, 2.0, "sash")
    w.tube([(1.5, 13.5, 1.2), (3, 11, 1.6), (3.6, 7.5, 1.6)], lambda t: 1.0 - 0.3 * t, "sash")
    # 배 키 코등이 (가로로 누운 바퀴): 테, 바퀴살, 손잡이 끝
    w.fill(lambda X, Y, Z: (np.abs(np.hypot(X, Z) - 5.3) <= 0.85) & (Y >= 19) & (Y <= 20.9), "wood")
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        ca, sa = math.cos(a), math.sin(a)
        w.fill(lambda X, Y, Z, ca=ca, sa=sa: (np.abs(-X * sa + Z * ca) <= 0.6) & (X * ca + Z * sa > 1) &
               (X * ca + Z * sa < 7.6) & (Y >= 19) & (Y <= 20.9), "wood")
        w.ball(8.3 * ca, 20, 8.3 * sa, 1.1, 1.6, 1.1, "brass")
    w.cyl(18.5, 21.9, 2.3, "brass")                         # 가운데 통
    # 날: 휜 커틀러스 (끝 쪽이 넓고, 등이 비스듬히 잘린 끝)
    y0, y1 = 22, 64
    c = lambda t: -5.0 * t ** 2
    s = lambda t: ramp_in(t, 0.8, 1.0)
    lo = lambda t: c(t) - 2.0 + 3.4 * s(t)
    hi = lambda t: c(t) + 2.0 + 2.2 * t - 3.0 * s(t) ** 1.5
    wave_w = lambda Y: 2.1 + 0.8 * np.sin((Y - y0) * 0.6)
    sect(w, y0, y1, lo, hi, [
        ("steel", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((dl < 2) & (np.abs(Z) <= 1.5))),
        ("edge", lambda X, Y, Z, dl, dr, t: (dr < wave_w(Y)) & (np.abs(Z) <= 0.5)),
        ("wave", lambda X, Y, Z, dl, dr, t: (np.abs(dr - wave_w(Y)) < 0.5) & (np.abs(Z) <= 0.5) & (t < 0.9)),
    ])
    # 등의 이 빠진 자국
    for yc in (45,):
        tt = (yc - y0) / (y1 - y0)
        xl = -5.0 * tt ** 2 - 2.0
        w.clear(lambda X, Y, Z, yc=yc, xl=xl: (X < xl + 1.5 - np.abs(Y - yc) * 0.9) & (np.abs(Y - yc) < 1.8) & (X > xl - 1))
    return w


def crystal_sword():
    """수정 검: 견습생의 검에 자수정이 자라나 날 끝이 커다란 결정 기둥이 되고, 옆으로 결정 가지가 뻗었다."""
    m = {
        "steel": Mat(["#6e747e", "#8a909a", "#a2a8b2", "#d0d4da"], "metal", seed=151),
        "iron": Mat(["#25272d", "#3a3d44", "#50545c", "#7c8088"], "metal", seed=152),
        "leather": Mat(["#2a170c", "#4a2a16", "#6a3e22", "#8a5632"], "grip", seed=153),
        "ame": Mat(["#3a1466", "#58288e", "#7444b0", "#a070e0"], "crystal", seed=154),
        "ame_l": Mat(["#9a68e0", "#b488f0", "#d0b0ff", "#f6ecff"], "crystal", seed=155),
        "shine": Mat(["#a070f0", "#c8a0ff", "#ecd8ff", "#ffffff"], "sparkle", glow=True, seed=156),
    }
    w = Weapon(m, grip_y=8.5, kind="sword", seed=151)
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 2.6) <= 2.7) & (np.abs(Z) <= 1.5), "iron")
    w.cyl(4.5, 13, 1.6, "leather")
    w.box(-6.6, 6.6, 13, 15.9, -1.6, 1.6, "iron")
    sect(w, 16, 34, lambda t: -3.0 + 0 * t, lambda t: 3.0 + 0 * t, [          # 원래 쇠 날
        ("steel", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5))),
    ])

    def crystal(x0, y0, ang, L, r, tip=0.35, depth=2.0):
        """결정 기둥: 끝이 뾰족한 네모 기둥, 한쪽 면은 밝게."""
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)

        def geo(X, Y, Z):
            u = (X - x0) * ca + (Y - y0) * sa
            v = -(X - x0) * sa + (Y - y0) * ca
            wd = r * np.clip((L - u) / (L * tip), 0, 1)
            return (u >= -0.5) & (u <= L) & (np.abs(v) <= wd + 0.1) & (np.abs(Z) <= np.minimum(depth, wd + 0.6)), v
        w.fill(lambda X, Y, Z: (lambda g: g[0] & (g[1] >= 0))(geo(X, Y, Z)), "ame")
        w.fill(lambda X, Y, Z: (lambda g: g[0] & (g[1] < 0))(geo(X, Y, Z)), "ame_l")

    crystal(0, 26, 90, 41, 4.1, tip=0.4, depth=2.6)          # 날 끝을 삼킨 큰 결정
    crystal(2, 29, 38, 12, 2.2)                              # 옆 가지들 (좌우 다르게)
    crystal(-2, 37, 140, 10, 2.0)
    crystal(2, 46, 58, 9, 1.6, depth=1.6)
    crystal(-2.5, 23, 155, 6, 1.4, depth=1.5)
    crystal(5.5, 14.5, 62, 6.5, 1.4, depth=1.5)              # 가드에도 하나
    s = solid(w)
    w.fill(lambda X, Y, Z: s & (Y >= 58) & (X > 0) & (np.abs(X) < 3), "shine")   # 큰 결정 끝만 반짝
    return w


def storm_katana():
    """폭풍의 카타나: 아주 가늘고 긴 먹색 날에 갈라지는 번개 무늬, 칼등 쪽으로 튀어나온 번개 갈퀴, 남보라 손잡이."""
    m = {
        "gun": Mat(["#1c2230", "#2a3244", "#3a4458", "#647090"], "metal", seed=161),
        "edge": Mat(["#a8b4cc", "#c4cee2", "#e0e8f6", "#ffffff"], "metal", seed=162),
        "bolt": Mat(["#e0b010", "#ffe040", "#fff4a0", "#ffffff"], "flat", glow=True, seed=163),
        "iron": Mat(["#202028", "#383844", "#545464", "#747488"], "metal", seed=164),
        "wrap": Mat(["#140e28", "#241a48", "#3a2c6e", "#5a4898"], "grip", seed=165),
        "silver": Mat(["#6a7080", "#a0a8b8", "#d0d6e2", "#f4f6fa"], "metal", seed=166),
    }
    w = Weapon(m, grip_y=10, kind="katana", seed=161)
    w.cyl(0.5, 2.9, 1.9, "silver")
    w.cyl(2.5, 18, 1.6, "wrap")
    w.cyl(18, 19.9, 3.4, "iron", rz=3.0)
    # 칼등 쪽 번개 갈퀴 (갈라지는 모양)
    w.tube([(-2.5, 19, 0), (-6.5, 22.5, 0), (-5.2, 18.5, 0), (-10.5, 22, 0)], 0.9, "silver")
    w.tube([(-6.0, 20.5, 0), (-8.5, 16.5, 0)], 0.8, "silver")
    w.box(-1.6, 2.6, 20, 21.9, -1.1, 1.1, "silver")         # 하바키
    y0, y1 = 20, 70
    c = lambda t: -3.5 * t ** 2
    hi = lambda t: c(t) + 1.8 - 3.4 * ramp_in(t, 0.9)
    sect(w, y0, y1, lambda t: c(t) - 1.8, hi, [
        ("gun", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((dl < 1) & (np.abs(Z) <= 1.5))),
        ("edge", lambda X, Y, Z, dl, dr, t: (dr < 1) & (np.abs(Z) <= 0.5)),
    ])
    # 번개 무늬: 지그재그 (날 아래쪽 2/3)
    s = solid(w)

    def zig(X, Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        tri = 2 * np.abs(((Y - y0) / 5.0) % 2 - 1) - 1
        return np.abs(X - (-3.5 * t ** 2 + 0.2 + 0.9 * tri)) < 0.75
    w.fill(lambda X, Y, Z: s & zig(X, Y) & (Y >= 23) & (Y <= 54), "bolt")
    return w


def blood_sword():
    """혈검: 한쪽 날에 아래로 걸리는 톱니가 난 핏빛 날, 검은 피홈, 아래로 휜 송곳니 가드, 핏방울 보석, 가시 폼멜."""
    m = {
        "crim": Mat(["#4a0a12", "#6a0e18", "#8a1622", "#c83a40"], "metal", seed=171),
        "edge": Mat(["#a82830", "#c83a44", "#e86068", "#ffb0b0"], "metal", seed=172),
        "black": Mat(["#120a0c", "#24161a", "#38242a", "#4e343a"], "metal", seed=173),
        "bone": Mat(["#6a5a48", "#a8987e", "#d4c6aa", "#f2ead6"], "stone", seed=174),
        "wrap": Mat(["#1e0608", "#3a0c12", "#5a141e", "#7a222c"], "grip", seed=175),
        "drop": Mat(["#5a0010", "#b0102a", "#ff3050", "#ffc0c8"], "gem", glow=True, seed=176),
    }
    w = Weapon(m, grip_y=10, kind="sword", seed=171)
    w.tube([(0, 6, 0), (0, 0.5, 0)], lambda t: 2.1 * (1 - t) + 0.5, "black")   # 가시 폼멜
    w.cyl(5, 14.5, 1.6, "wrap")
    w.box(-4.6, 4.6, 14, 16.9, -1.6, 1.6, "black")
    for sx in (1, -1):                                                     # 송곳니 가드 (아래로)
        w.tube([(sx * 3.5, 15.5, 0), (sx * 6.5, 15, 0), (sx * 8, 12, 0), (sx * 7, 8, 0)],
               lambda t: 1.5 * (1 - t) + 0.5, "bone")
    y0, y1 = 17, 54
    base = lambda t: (3.2 - 0.6 * t) * taper(t, 0.76) + 0.3
    sect(w, y0, y1, lambda t: -base(t), base, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("crim", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    # +X 쪽 톱니: 6줄마다 아래로 걸리는 큰 이빨 넷
    tooth = lambda Y: 2.8 * (1 - ((Y - y0 - 2) / 6.0) % 1.0) ** 1.3
    w.fill(lambda X, Y, Z: (X > 0) & (X <= base(np.clip((Y - y0) / (y1 - y0), 0, 1)) + tooth(Y)) &
           (Y >= 19) & (Y < 43) & (np.abs(Z) <= 0.5), "edge")
    # 피홈
    fl = lambda X, Y: (np.abs(X) < 1) & (Y >= 18) & (Y <= 40)
    w.fill(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) <= 0.5), "black")
    w.clear(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) > 1))
    # 핏방울 보석
    w.fill(lambda X, Y, Z: ((np.hypot(X, Y - 15.2) <= 1.6) | ((np.abs(X) < 1) & (Y > 15) & (Y < 18.2))) &
           (np.abs(Z) <= 2.5), "drop")
    return w


# ─────────────────────────── flame (rift) ───────────────────────────

def flame_sword():
    """화염 검: 불꽃처럼 일렁이는 플랑베르주 날, 검게 탄 몸통의 홈 속에 녹은 쇳물, 달아오른 날끝, 위로 솟는 불꽃 뿔 가드."""
    m = {
        "char": Mat(["#1a100c", "#2a1a14", "#3a261c", "#58382a"], "metal", seed=181),
        "hot": Mat(["#a8300a", "#d8500e", "#ff8a20", "#ffd060"], "metal", seed=182),
        "magma": Mat(["#a01800", "#e85a0a", "#ffa020", "#fff2a0"], "fire", glow=True, seed=183),
        "obsid": Mat(["#0c0814", "#1c1428", "#2e2240", "#463656"], "stone", seed=184),
        "ember": Mat(["#7a1800", "#ff5a10", "#ffb040", "#fff4c0"], "pulse", glow=True, seed=185),
        "wrap": Mat(["#1a0a06", "#2e140a", "#4a2010", "#6a3018"], "grip", seed=186),
    }
    w = Weapon(m, grip_y=9, kind="sword", seed=181)
    w.ball(0, 2.6, 0, 2.3, 2.6, 2.1, "obsid")
    w.gem(0, 2.6, 1.0, "ember", depth=2.6)
    w.cyl(4.5, 13.5, 1.6, "wrap")
    w.box(-3.1, 3.1, 13, 16.9, -2.1, 2.1, "obsid")
    # 불꽃 뿔: 오른쪽 길게, 왼쪽 짧게, 끝이 달아올랐다
    w.tube([(2.5, 15, 0), (6, 15.5, 0), (8.2, 18.5, 0), (8, 22.5, 0), (9.6, 26, 0)], lambda t: 1.6 * (1 - t) + 0.5, "obsid")
    w.tube([(-2.5, 15, 0), (-5.5, 15.5, 0), (-7.4, 18, 0), (-7, 21, 0), (-8.4, 23.5, 0)], lambda t: 1.5 * (1 - t) + 0.5, "obsid")
    w.ball(9.4, 25.4, 0, 0.9, 1.4, 0.9, "hot")
    w.ball(-8.2, 23, 0, 0.9, 1.4, 0.9, "hot")
    # 플랑베르주 날
    y0, y1 = 17, 63
    c = lambda t: 1.1 * np.sin((t * (y1 - y0)) * 0.42)
    hw = lambda t: (4.3 - 1.3 * t) * taper(t, 0.84) + 0.2
    sect(w, y0, y1, lambda t: c(t) - hw(t), lambda t: c(t) + hw(t), [
        ("hot", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("char", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    # 가운데 홈 속 쇳물 (겉 한 칸을 파내고 그 안이 빛난다)
    core = lambda X, Y: (lambda t: (np.abs(X - c(t)) < 1.0) & (t > 0.02) & (t < 0.8))((Y - y0) / (y1 - y0))
    w.fill(lambda X, Y, Z: core(X, Y) & (np.abs(Z) <= 0.5), "magma")
    w.clear(lambda X, Y, Z: core(X, Y) & (np.abs(Z) > 1))
    return w


# ─────────────────────────── boss / prism (aura) ───────────────────────────

def holy_blade():
    """성검: 넓고 곧은 은빛 날에 빛나는 금빛 십자 홈, 크게 펼친 깃털 날개 가드, 푸른 보석, 금 십자 폼멜. 신성 아우라."""
    m = {
        "silver": Mat(["#9aa2b2", "#b0b8c6", "#ccd4de", "#ffffff"], "metal", seed=191),
        "edge": Mat(["#dce0ea", "#eaeef6", "#f8faff", "#ffffff"], "metal", seed=192),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff2a8"], "metal", seed=193),
        "light": Mat(["#f0c040", "#ffe070", "#fff6c8", "#ffffff"], "flow", glow=True, seed=194),
        "feather": Mat(["#8a94aa", "#b4bccc", "#dce2ee", "#ffffff"], "cloth", seed=195),
        "feather2": Mat(["#c4ccdc", "#dce2ec", "#f2f5fa", "#ffffff"], "cloth", seed=196),
        "sapph": Mat(["#0a1a6a", "#2a4ad0", "#6a9aff", "#e0eeff"], "gem", glow=True, seed=197),
        "wrap": Mat(["#0e1a4a", "#1a2a6a", "#2a409a", "#4060c0"], "grip", seed=198),
    }
    w = Weapon(m, grip_y=9.5, kind="sword", seed=191)
    # 오른쪽 반만 만들고 mirror() 로 왼쪽을 복사한다
    # 날개: 위로 휘어 오르는 금빛 날개뼈에서 깃털이 바깥 아래로 늘어진다 (안쪽 깃은 밝게, 앞으로 겹침)
    bone = [(3, 19), (7, 22.5), (11, 27), (13.5, 32), (14.5, 36)]
    primaries = [((5.5, 21.5), (8.5, 14.0), 2.2, 1.1), ((8.5, 24.5), (12.5, 16.5), 2.2, 1.1),
                 ((11.0, 28.0), (16.0, 20.5), 2.0, 1.0), ((13.0, 31.5), (18.5, 25.5), 1.9, 0.9),
                 ((14.0, 35.0), (19.5, 31.0), 1.6, 0.8)]
    for i, (p0, p1, r0, r1) in enumerate(primaries):
        w.prism(lambda X, Y, p0=p0, p1=p1, r0=r0, r1=r1: capsule(X, Y, p0, p1, r0, r1) & (X > 0),
                1.0, "feather" if i % 2 == 0 else "feather2")
    w.prism(lambda X, Y: capsule(X, Y, (4, 19), (10, 25), 3.0, 2.2) & (X > 0), 1.5, "feather2")   # 어깨 깃
    w.tube([(x, y, 0) for x, y in bone], lambda t: 1.4 - 0.6 * t, "gold")
    w.box(0, 3.6, 15, 21.9, -2.1, 2.1, "gold")
    w.box(0, 0.6, 0, 5, -1.1, 1.1, "gold")                   # 십자 폼멜
    w.box(0, 2.6, 2, 3.9, -1.1, 1.1, "gold")
    w.cyl(4.5, 15, 1.6, "wrap")
    bands(w, [4.5, 14], 2.1, "gold")
    w.mirror()
    w.gem(0, 18.5, 1.6, "sapph", depth=2.6)
    # 넓은 날 + 빛나는 십자 홈
    y0, y1 = 22, 68
    hw = lambda t: (4.4 - 0.8 * t) * taper(t, 0.84, 0.85) + 0.3
    sect(w, y0, y1, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("silver", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("light", lambda X, Y, Z, dl, dr, t: (((np.abs(X) < 1) & (t < 0.8)) | ((np.abs(Y - 30) < 1) & (np.abs(X) < 3))) &
         (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    w.set_aura(["#8a6a10", "#e8c040", "#fff0a0", "#ffffff"], "holy", size=1.1, focus=["light", "edge"])
    return w


def bloodmoon_katana():
    """혈월의 카타나: 아주 긴 노다치, 검은 등과 피처럼 빛나는 물결 하몬, 칼을 받쳐 든 큰 붉은 초승달 코등이, 긴 술."""
    m = {
        "black": Mat(["#0a0608", "#1a1014", "#2a1a20", "#3e262e"], "metal", seed=201),
        "steel": Mat(["#5a464e", "#6a5660", "#806a74", "#b898a2"], "metal", seed=202),
        "crim": Mat(["#8a0014", "#d01028", "#ff3a4a", "#ffc0c8"], "flow", glow=True, seed=203),
        "moon": Mat(["#9a0a18", "#d81830", "#ff4a58", "#ffd8d8"], "pulse", glow=True, seed=204),
        "iron": Mat(["#1a1418", "#2e2228", "#463840", "#605058"], "metal", seed=205),
        "wrap": Mat(["#0c0608", "#1a0c10", "#3a141c", "#5a1e2a"], "grip", seed=206),
        "tassel": Mat(["#5a0a10", "#8a1420", "#c02030", "#e85060"], "cloth", seed=207),
    }
    w = Weapon(m, grip_y=8, kind="katana", seed=201)
    w.cyl(0.5, 2.9, 1.9, "iron")
    w.cyl(2.5, 14, 1.6, "wrap")
    w.tube([(0.5, 1.5, 0.5), (3, 0.8, 0.5), (5.5, 2.8, 0.5), (7.5, 1.2, 0.5)], 0.7, "tassel")   # 술
    w.ball(8.6, 1.6, 0.5, 1.4, 1.6, 1.2, "tassel")
    # 초승달 코등이: 바깥 원 - 위로 밀린 안쪽 원 → 뿔이 위로 선 달
    outer = lambda X, Y, k=0.0: np.hypot(X, Y - 21.5) <= 10.0 - k
    inner = lambda X, Y, k=0.0: np.hypot(X, Y - 26) <= 8.6 + k
    w.prism(lambda X, Y: outer(X, Y) & ~inner(X, Y), 1.5, "iron")
    w.prism(lambda X, Y: outer(X, Y, 1.0) & ~inner(X, Y, 1.0), 2.0, "moon")
    w.box(-2.1, 2.1, 12, 19.9, -1.6, 1.6, "iron")
    y0, y1 = 19, 71
    c = lambda t: -5.0 * t ** 2
    hi = lambda t: c(t) + 2.7 - 4.6 * ramp_in(t, 0.9)
    ham = lambda Y: 1.6 + 0.8 * np.sin((Y - y0) * 0.7)
    sect(w, y0, y1, lambda t: c(t) - 2.7, hi, [
        ("steel", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("black", lambda X, Y, Z, dl, dr, t: (dl < 1.6) & (np.abs(Z) <= 1.5)),
        ("crim", lambda X, Y, Z, dl, dr, t: (dr < ham(Y)) & (np.abs(Z) <= 0.5)),
    ])
    w.set_aura(["#3a0008", "#9a0a1a", "#ff2a3a", "#ffc0c8"], "drip", size=1.0, focus=["crim", "moon"])
    return w


def sun_blade():
    """태양검: 빛살이 뻗은 태양 원반(무지개 고리)에서 넓은 빛줄기 모양의 삼각 날이 솟는다. 태양 불꽃 아우라."""
    m = {
        "gold": Mat(["#8a5a0c", "#c08018", "#f0b830", "#fff0a0"], "metal", seed=211),
        "sunsteel": Mat(["#d09020", "#e8a830", "#ffd070", "#fffbe0"], "metal", seed=212),
        "core": Mat(["#ff9a10", "#ffc830", "#fff080", "#ffffff"], "flow", glow=True, seed=213),
        "disc": Mat(["#ff7a00", "#ffb020", "#ffe060", "#fffcd8"], "pulse", glow=True, seed=214),
        "ray": Mat(["#a04a08", "#d06a10", "#f8a030", "#ffd890"], "metal", seed=215),
        "prism": Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=216),
        "wrap": Mat(["#3a0a04", "#6a1a08", "#9a2a10", "#c84a1a"], "grip", seed=217),
    }
    w = Weapon(m, grip_y=9, kind="sword", seed=211)
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Y - 2.5) * 1.2 <= 2.8) & (np.abs(Z) <= 1.5), "gold")   # 별 폼멜
    w.cyl(4.5, 15, 1.6, "wrap")
    bands(w, [9], 2.1, "gold")
    # 빛줄기 날 (원반 가운데에서 시작해 원반이 밑동을 덮는다)
    cy = 22.0
    y0, y1 = cy, 71
    hw = lambda t: 5.4 * (1 - t) ** 0.9 + 0.7
    sect(w, y0, y1, lambda t: -hw(t), hw, [
        ("gold", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("sunsteel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("core", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 0.6 + 1.8 * (1 - t)) & (t < 0.9) & (np.abs(Z) <= 1.5)),
    ])
    # 태양 원반과 빛살 (위: 날, 아래: 손잡이 자리는 비운다)
    for k in range(12):
        if k in (3, 9):
            continue
        a = k * math.pi / 6
        ln = 17.0 if k % 2 == 0 else 13.0
        ca, sa = math.cos(a), math.sin(a)

        def ray(X, Y, ca=ca, sa=sa, ln=ln):
            u = X * ca + (Y - cy) * sa
            v = -X * sa + (Y - cy) * ca
            return (u > 6) & (u < ln) & (np.abs(v) <= 2.8 * (ln - u) / (ln - 6) + 0.3)
        w.prism(ray, 1.0, "ray")
    w.prism(lambda X, Y: np.hypot(X, Y - cy) <= 8.0, 2.0, "gold")
    w.prism(lambda X, Y: np.abs(np.hypot(X, Y - cy) - 6.4) <= 0.7, 2.5, "prism")
    w.prism(lambda X, Y: np.hypot(X, Y - cy) <= 5.0, 2.5, "disc")
    w.set_aura(["#b02a00", "#ff7a10", "#ffd040", "#fffde0"], "flame", size=1.2, focus=["core", "disc"])
    return w


# ─────────────────────────── 목록 ───────────────────────────

WEAPONS = {
    "apprentice_sword": apprentice_sword,
    "copper_sword": copper_sword,
    "wooden_katana": wooden_katana,
    "wind_sword": wind_sword,
    "pirate_katana": pirate_katana,
    "crystal_sword": crystal_sword,
    "storm_katana": storm_katana,
    "blood_sword": blood_sword,
    "flame_sword": flame_sword,
    "holy_blade": holy_blade,
    "bloodmoon_katana": bloodmoon_katana,
    "sun_blade": sun_blade,
}

NAMES = {
    "apprentice_sword": "견습생의 검",
    "copper_sword": "구리 검",
    "wooden_katana": "목도",
    "wind_sword": "바람의 검",
    "pirate_katana": "해적의 카타나",
    "crystal_sword": "수정 검",
    "storm_katana": "폭풍의 카타나",
    "blood_sword": "혈검",
    "flame_sword": "화염 검",
    "holy_blade": "성검",
    "bloodmoon_katana": "혈월의 카타나",
    "sun_blade": "태양검",
}

if __name__ == "__main__":
    preview_sheet(WEAPONS, os.path.join(HERE, "preview", "blades.png"), names=NAMES)
