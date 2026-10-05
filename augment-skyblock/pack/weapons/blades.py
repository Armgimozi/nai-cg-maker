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
    return np.where(t < t0, 1.0, np.clip((1 - t) / (1 - t0), 0, 1) ** p)


def solid(w):
    """지금까지 채워진 복셀 (다시 칠하기용 마스크)."""
    g = w.grid.copy()
    return g > 0


def bands(w, ys, r, mat, h=0.9):
    """손잡이에 감은 고리 띠."""
    for y in ys:
        w.cyl(y, y + h, r, mat)


# ─────────────────────────── basic ───────────────────────────

def apprentice_sword():
    """견습생의 검: 곧은 쇠 날 + 가운데 홈(풀러), 끝이 뭉툭한 일자 가드, 가죽 손잡이, 원반 폼멜. 정직한 첫 검."""
    m = {
        "steel": Mat(["#4a4e58", "#7c828e", "#aab0ba", "#d8dce2"], "metal", seed=101),
        "edge": Mat(["#8a909a", "#b8bec6", "#dde1e6", "#f6f8fa"], "metal", seed=102),
        "iron": Mat(["#25272d", "#3e4148", "#5c6068", "#7c8088"], "metal", seed=103),
        "leather": Mat(["#2a170c", "#4a2a16", "#6a3e22", "#8a5632"], "grip", seed=104),
    }
    w = Weapon(m, grip_y=8.5, kind="sword", seed=101)
    # 원반 폼멜 (앞에서 보면 동그라미)
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 2.6) <= 2.7) & (np.abs(Z) <= 1.5), "iron")
    w.cyl(4.5, 13, 1.6, "leather")
    # 일자 가드 + 끝 덩어리
    w.box(-6.6, 6.6, 13, 15.9, -1.6, 1.6, "iron")
    w.fill(lambda X, Y, Z: (np.abs(X) >= 5) & (np.abs(X) <= 7.2) & (Y >= 12) & (Y <= 16.9) & (np.abs(Z) <= 1.6), "iron")
    hw = lambda t: 3.0 * taper(t, 0.8) + 0.2
    sect(w, 16, 47, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("steel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    # 풀러: 가운데 두 줄을 한 칸 파내고 어둡게
    fl = lambda X, Y: (np.abs(X) < 1) & (Y >= 17) & (Y <= 38)
    w.fill(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) <= 0.5), "iron")
    w.clear(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) > 1))
    return w


def copper_sword():
    """구리 검: 짧고 통통한 잎사귀 날(마름모 단면), 녹청 슨 네모 가드, 구리 고리 감은 나무 손잡이, 고리 폼멜."""
    m = {
        "copper": Mat(["#5a2a14", "#9a4a24", "#d0703a", "#f0a070"], "metal", seed=111),
        "bright": Mat(["#b0602a", "#e08a50", "#ffb880", "#ffe4c8"], "metal", seed=112),
        "patina": Mat(["#1e5a50", "#2e8a76", "#4ab89a", "#86e0c4"], "stone", seed=113),
        "wood": Mat(["#2e1c10", "#4e3018", "#6e4626", "#8e5e36"], "wood", seed=114),
    }
    w = Weapon(m, grip_y=11, kind="sword", seed=111)
    # 고리 폼멜
    w.fill(lambda X, Y, Z: (np.abs(np.hypot(X, Y - 3.9) - 2.8) <= 0.95) & (np.abs(Z) <= 1.0), "copper")
    w.cyl(7, 15.5, 1.6, "wood")
    bands(w, [7.5, 10.5, 13.5], 2.6, "copper")
    # 네모 가드 (녹청), 위 테두리만 구리
    w.box(-4.1, 4.1, 15, 17.9, -2.1, 2.1, "patina")
    w.box(-4.1, 4.1, 17, 17.9, -2.1, 2.1, "copper")
    # 잎사귀 날
    hw = lambda t: (2.3 + 1.7 * np.sin(np.pi * t / 1.2)) * taper(t, 0.68, 0.8) + 0.3
    zf = lambda dl, dr: 0.5 + np.clip((np.minimum(dl, dr) - 1) / 1.5, 0, 1)
    sect(w, 18, 45, lambda t: -hw(t), hw, [
        ("bright", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("copper", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= zf(dl, dr))),
        ("bright", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 1) & (t < 0.86) & (np.abs(Z) <= zf(dl, dr))),
    ])
    # 날 밑동에 번진 녹청 얼룩 (한쪽만)
    s = solid(w)
    w.fill(lambda X, Y, Z: s & (Y >= 18) & (Y <= 21 + (X + 3) * 0.6) & (X < -1) & (Y < 24), "patina")
    return w


def wooden_katana():
    """목도: 통나무 한 덩이를 깎은 휜 칼(둥근 단면, 뭉툭한 끝), 검은 가죽 둥근 코등이, 천 테이프 두 줄."""
    m = {
        "oak": Mat(["#5a3c1e", "#8a6236", "#b48a52", "#d8b47a"], "wood", seed=121),
        "dark": Mat(["#1e140e", "#36261a", "#4e3826", "#664a34"], "wood", seed=122),
        "tape": Mat(["#8a8070", "#b0a690", "#d4ccb4", "#eee8d6"], "cloth", seed=123),
    }
    w = Weapon(m, grip_y=10, kind="katana", seed=121)
    w.cyl(1.5, 18, 1.7, "oak")
    w.cyl(0, 2.4, 1.9, "dark")
    bands(w, [15.0, 16.6], 2.0, "tape", h=0.8)
    w.cyl(18, 19.9, 4.3, "dark", rz=3.6)                    # 둥근 코등이
    c = lambda t: -4.5 * t ** 2
    hi = lambda t: c(t) + 2.0 - np.where(t > 0.9, 3.4 * ((t - 0.9) / 0.1) ** 1.4, 0)
    sect(w, 20, 68, lambda t: c(t) - 2.0, hi, [
        ("oak", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5))),
    ])
    return w


# ─────────────────────────── island ───────────────────────────

def wind_sword():
    """바람의 검: 가늘고 긴 민트빛 날에 비스듬한 바람 구멍 셋, 한쪽에 바람에 휜 지느러미, 위아래로 말린 소용돌이 가드."""
    m = {
        "steel": Mat(["#4a6a6a", "#7aa4a0", "#b2d8d0", "#e4fbf4"], "metal", seed=131),
        "edge": Mat(["#a4d0c8", "#c8eee6", "#ecfffa", "#ffffff"], "metal", seed=132),
        "silver": Mat(["#5a6470", "#8e98a4", "#c2cad4", "#eef2f6"], "metal", seed=133),
        "jade": Mat(["#0e3a2a", "#1a6a4a", "#2e9a6a", "#5ac898"], "grip", seed=134),
        "glint": Mat(["#2aa0a0", "#5ae0d8", "#a8fff4", "#ffffff"], "gem", glow=True, seed=135),
    }
    w = Weapon(m, grip_y=10, kind="sword", seed=131)
    # 물방울 폼멜 + 작은 빛 구슬
    w.ball(0, 3.2, 0, 2.1, 2.6, 2.1, "silver")
    w.gem(0, 3.2, 0.9, "glint", depth=2.6)
    w.cyl(5, 15, 1.6, "jade")
    # 소용돌이 가드: 오른쪽은 위로, 왼쪽은 아래로 말린다
    w.box(-2.6, 2.6, 15, 17.9, -1.6, 1.6, "silver")
    w.tube([(2, 16.5, 0), (5, 16, 0), (7.6, 17.6, 0), (8.2, 20.4, 0), (6.6, 22, 0), (5, 21, 0), (5.4, 19.6, 0)], 0.95, "silver")
    w.tube([(-2, 16.5, 0), (-5, 17, 0), (-7.6, 15.4, 0), (-8.2, 12.6, 0), (-6.6, 11, 0), (-5, 12, 0), (-5.4, 13.4, 0)], 0.95, "silver")
    # 날: 오른쪽은 곧고, 왼쪽은 밑동에 바람 지느러미가 뒤로 휘어 있다
    hw = lambda t: (2.6 - 0.5 * t) * taper(t, 0.72, 1.1) + 0.2
    fin = lambda t: 2.6 * np.clip(1 - np.abs(t - 0.14) / 0.14, 0, 1) ** 0.7
    sect(w, 18, 60, lambda t: -hw(t) - fin(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("steel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5) & (X > -2.6)),
    ])
    # 비스듬한 바람 구멍 셋
    for yc in (28, 36, 44):
        w.clear(lambda X, Y, Z, yc=yc: (np.abs(X) < 1.6) & (np.abs((Y - yc) - 1.2 * X) <= 1.1))
    return w


def pirate_katana():
    """해적의 카타나: 끝이 넓어지는 커틀러스형 휜 날에 물결 하몬, 등의 이 빠진 자국, 배 키 모양 코등이, 붉은 띠."""
    m = {
        "steel": Mat(["#4a5058", "#7a828c", "#aab2bc", "#dae0e6"], "metal", seed=141),
        "wave": Mat(["#3a7a96", "#5aa8c4", "#9ad8e8", "#e0f8ff"], "metal", seed=142),
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
    c = lambda t: -5.0 * t ** 2
    s = lambda t: np.clip((t - 0.8) / 0.2, 0, 1)
    lo = lambda t: c(t) - 2.0 + 3.0 * s(t)
    hi = lambda t: c(t) + 2.0 + 1.8 * t - 2.8 * s(t) ** 1.5
    y0, y1 = 22, 64
    wave_w = lambda Y: 1.6 + 0.9 * np.sin((Y - y0) * 0.55)
    sect(w, y0, y1, lo, hi, [
        ("steel", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((dr >= 1) & (np.abs(Z) <= 1.5))),
        ("wave", lambda X, Y, Z, dl, dr, t: (dr < wave_w(Y)) & (np.abs(Z) <= 1.5)),
    ])
    # 등의 이 빠진 자국 둘
    for yc in (38, 50):
        tt = (yc - y0) / (y1 - y0)
        xl = -5.0 * tt ** 2 - 2.0
        w.clear(lambda X, Y, Z, yc=yc, xl=xl: (X < xl + 1.6 - np.abs(Y - yc) * 0.8) & (np.abs(Y - yc) < 2) & (X > xl - 1))
    return w


def crystal_sword():
    """수정 검: 견습생의 검에 자수정이 자라나 날 끝이 커다란 결정 창이 되고, 옆으로 결정 가지가 뻗었다."""
    m = {
        "steel": Mat(["#4a4e58", "#7c828e", "#aab0ba", "#d8dce2"], "metal", seed=151),
        "iron": Mat(["#25272d", "#3e4148", "#5c6068", "#7c8088"], "metal", seed=152),
        "leather": Mat(["#2a170c", "#4a2a16", "#6a3e22", "#8a5632"], "grip", seed=153),
        "ame": Mat(["#2a0e4a", "#4e2282", "#8248c4", "#b888f0"], "crystal", seed=154),
        "ame_l": Mat(["#7a48c0", "#a878ea", "#d4b0ff", "#f6ecff"], "crystal", seed=155),
        "shine": Mat(["#8a4ae0", "#c090ff", "#ecd8ff", "#ffffff"], "sparkle", glow=True, seed=156),
    }
    w = Weapon(m, grip_y=8.5, kind="sword", seed=151)
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 2.6) <= 2.7) & (np.abs(Z) <= 1.5), "iron")
    w.cyl(4.5, 13, 1.6, "leather")
    w.box(-6.6, 6.6, 13, 15.9, -1.6, 1.6, "iron")
    # 원래 쇠 날 (아래쪽만 보인다)
    sect(w, 16, 38, lambda t: -3.0 + 0 * t, lambda t: 3.0 + 0 * t, [
        ("steel", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5))),
    ])

    def shard(p0, p1, r0, lit=(0.7, 0, 0.7)):
        w.tube([p0, p1], lambda t: r0 * (1 - t) ** 0.8 + 0.45, "ame")
        q0 = tuple(a + b for a, b in zip(p0, lit))
        q1 = tuple(a + b * 0.5 for a, b in zip(p1, lit))
        w.tube([q0, q1], lambda t: (r0 - 0.9) * (1 - t) ** 0.8 + 0.3, "ame_l")

    # 날 끝을 삼킨 큰 결정
    shard((0, 29, 0), (0.5, 66, 0), 4.2)
    # 옆 가지들 (좌우 다르게)
    shard((2, 33, 0), (8.5, 44, 0), 2.2)
    shard((-2, 40, 0), (-7.5, 50, 0.5), 1.9)
    shard((2, 48, 0), (6, 55, 0), 1.4)
    shard((-2.5, 26, 0), (-6.5, 31, 0), 1.3)
    shard((5, 14, 0), (8.5, 19.5, 0), 1.2)                    # 가드에도 하나
    # 큰 결정 끝만 반짝
    s = solid(w)
    w.fill(lambda X, Y, Z: s & (Y >= 58) & (np.abs(X - 0.4) < 2.2) & (Z > 0.2), "shine")
    return w


def storm_katana():
    """폭풍의 카타나: 아주 가늘고 긴 먹색 날에 갈라지는 번개 무늬, 칼등 쪽으로 튀어나온 번개 갈퀴, 남보라 손잡이."""
    m = {
        "gun": Mat(["#1c2230", "#2e3648", "#465068", "#647090"], "metal", seed=161),
        "edge": Mat(["#8a96b0", "#b8c4dc", "#dce6f6", "#ffffff"], "metal", seed=162),
        "bolt": Mat(["#e0b010", "#ffe040", "#fff4a0", "#ffffff"], "flat", glow=True, seed=163),
        "iron": Mat(["#202028", "#383844", "#545464", "#747488"], "metal", seed=164),
        "wrap": Mat(["#140e28", "#241a48", "#3a2c6e", "#5a4898"], "grip", seed=165),
        "silver": Mat(["#6a7080", "#a0a8b8", "#d0d6e2", "#f4f6fa"], "metal", seed=166),
    }
    w = Weapon(m, grip_y=10, kind="katana", seed=161)
    w.cyl(0.5, 2.9, 1.9, "silver")
    w.cyl(2.5, 18, 1.6, "wrap")
    w.cyl(18, 19.9, 3.4, "iron", rz=3.0)
    # 칼등 쪽 번개 갈퀴
    w.tube([(-2.5, 19, 0), (-6, 21.5, 0), (-5, 18, 0), (-9.5, 20.5, 0)], 0.8, "edge")
    w.box(-1.6, 2.6, 20, 21.9, -1.1, 1.1, "silver")         # 하바키
    c = lambda t: -3.5 * t ** 2
    y0, y1 = 20, 70
    hi = lambda t: c(t) + 1.8 - np.where(t > 0.9, 3.4 * ((t - 0.9) / 0.1) ** 1.3, 0)
    sect(w, y0, y1, lambda t: c(t) - 1.8, hi, [
        ("gun", lambda X, Y, Z, dl, dr, t: (np.abs(Z) <= 0.5) | ((dl < 1) & (np.abs(Z) <= 1.5))),
        ("edge", lambda X, Y, Z, dl, dr, t: (dr < 1) & (np.abs(Z) <= 0.5)),
    ])
    # 번개 무늬: 지그재그 (날 아래 2/3 에만)
    s = solid(w)

    def zig(X, Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        tri = 2 * np.abs(((Y - y0) / 5.0) % 2 - 1) - 1
        return np.abs(X - (-3.5 * t ** 2 + 0.2 + 0.9 * tri)) < 0.75
    w.fill(lambda X, Y, Z: s & zig(X, Y) & (Y >= 23) & (Y <= 52), "bolt")
    return w


def blood_sword():
    """혈검: 한쪽 날에 갈고리 톱니가 난 핏빛 날, 검은 피홈, 아래로 휜 송곳니 가드, 핏방울 보석, 가시 폼멜."""
    m = {
        "crim": Mat(["#3a060c", "#6a0e18", "#9a1a24", "#c83a40"], "metal", seed=171),
        "edge": Mat(["#8a1a20", "#c0303a", "#e86068", "#ffb0b0"], "metal", seed=172),
        "black": Mat(["#120a0c", "#24161a", "#38242a", "#4e343a"], "metal", seed=173),
        "bone": Mat(["#6a5a48", "#a8987e", "#d4c6aa", "#f2ead6"], "stone", seed=174),
        "wrap": Mat(["#1e0608", "#3a0c12", "#5a141e", "#7a222c"], "grip", seed=175),
        "drop": Mat(["#5a0010", "#b0102a", "#ff3050", "#ffc0c8"], "gem", glow=True, seed=176),
    }
    w = Weapon(m, grip_y=10, kind="sword", seed=171)
    w.tube([(0, 6, 0), (0, 0.5, 0)], lambda t: 2.1 * (1 - t) + 0.5, "black")   # 가시 폼멜
    w.cyl(5, 14.5, 1.6, "wrap")
    w.box(-4.6, 4.6, 14, 16.9, -1.6, 1.6, "black")
    # 송곳니 가드 (아래로)
    for sx in (1, -1):
        w.tube([(sx * 3.5, 15.5, 0), (sx * 6.5, 15, 0), (sx * 8, 12, 0), (sx * 7, 8, 0)],
               lambda t: 1.5 * (1 - t) + 0.5, "bone")
    # 날: +X 쪽은 아래로 걸리는 톱니, -X 쪽은 매끈
    y0, y1 = 17, 56
    tooth = lambda Y: 1.6 * (1 - ((Y - y0) / 4.0) % 1.0)
    base = lambda t: (3.4 - 0.8 * t) * taper(t, 0.78) + 0.3
    sect(w, y0, y1, lambda t: -base(t), lambda t: base(t) + 0 * t, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("crim", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    sect(w, y0 + 2, 48, lambda t: 0 * t, lambda t: 3.6 - 0.6 * t + 0 * t, [
        ("edge", lambda X, Y, Z, dl, dr, t: (X <= base(np.clip((Y - y0) / (y1 - y0), 0, 1)) + tooth(Y)) &
         (X > 0) & (np.abs(Z) <= 0.5)),
    ])
    # 피홈
    fl = lambda X, Y: (X > -1.0) & (X < 1.0) & (Y >= 18) & (Y <= 44)
    w.fill(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) <= 0.5), "black")
    w.clear(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) > 1))
    # 핏방울 보석
    w.fill(lambda X, Y, Z: ((np.hypot(X, Y - 15.2) <= 1.6) | ((np.abs(X) < 1) & (Y > 15) & (Y < 18.2))) &
           (np.abs(Z) <= 2.5), "drop")
    return w


# ─────────────────────────── flame (rift) ───────────────────────────

def flame_sword():
    """화염 검: 불꽃처럼 일렁이는 플랑베르주 날, 검게 탄 몸통에 달아오른 날끝과 녹은 심지, 위로 솟는 불꽃 뿔 가드."""
    m = {
        "char": Mat(["#140c0a", "#2a1a14", "#40281e", "#58382a"], "metal", seed=181),
        "hot": Mat(["#8a1a04", "#d8460a", "#ff8a20", "#ffd060"], "metal", seed=182),
        "magma": Mat(["#6a1000", "#d84a0a", "#ffa020", "#fff2a0"], "fire", glow=True, seed=183),
        "obsid": Mat(["#0c0814", "#1c1428", "#2e2240", "#463656"], "stone", seed=184),
        "ember": Mat(["#7a1800", "#ff5a10", "#ffb040", "#fff4c0"], "pulse", glow=True, seed=185),
        "wrap": Mat(["#1a0a06", "#2e140a", "#4a2010", "#6a3018"], "grip", seed=186),
    }
    w = Weapon(m, grip_y=9, kind="sword", seed=181)
    w.ball(0, 2.6, 0, 2.3, 2.6, 2.1, "obsid")
    w.gem(0, 2.6, 1.0, "ember", depth=2.6)
    w.cyl(4.5, 13.5, 1.6, "wrap")
    w.box(-3.1, 3.1, 13, 16.9, -2.1, 2.1, "obsid")
    # 불꽃 뿔: 오른쪽 길게, 왼쪽 짧게
    w.tube([(2.5, 15, 0), (6, 15.5, 0), (8.2, 18.5, 0), (8, 22.5, 0), (9.6, 26, 0)], lambda t: 1.6 * (1 - t) + 0.5, "obsid")
    w.tube([(-2.5, 15, 0), (-5.5, 15.5, 0), (-7.4, 18, 0), (-7, 21, 0), (-8.4, 23.5, 0)], lambda t: 1.5 * (1 - t) + 0.5, "obsid")
    w.ball(9.4, 25.4, 0, 0.9, 1.4, 0.9, "hot")
    w.ball(-8.2, 23, 0, 0.9, 1.4, 0.9, "hot")
    # 플랑베르주 날
    y0, y1 = 17, 63
    c = lambda t: 1.1 * np.sin((t * (y1 - y0)) * 0.42)
    hw = lambda t: (3.4 - 1.0 * t) * taper(t, 0.84) + 0.2
    sect(w, y0, y1, lambda t: c(t) - hw(t), lambda t: c(t) + hw(t), [
        ("hot", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("char", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("magma", lambda X, Y, Z, dl, dr, t: (np.abs(dl - dr) < 2.0) & (t < 0.86) & (np.abs(Z) <= 1.5)),
    ])
    return w


# ─────────────────────────── boss / prism (aura) ───────────────────────────

def holy_blade():
    """성검: 넓고 곧은 은빛 날에 빛나는 금빛 십자 홈, 펼친 깃털 날개 가드, 금 십자 폼멜, 푸른 보석. 신성 아우라."""
    m = {
        "silver": Mat(["#7a8090", "#b0b8c6", "#dce2ea", "#ffffff"], "metal", seed=191),
        "edge": Mat(["#c8ccd8", "#e6eaf2", "#f8faff", "#ffffff"], "metal", seed=192),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff2a8"], "metal", seed=193),
        "light": Mat(["#e0b030", "#ffe070", "#fff6c8", "#ffffff"], "flow", glow=True, seed=194),
        "feather": Mat(["#8a94aa", "#c4ccdc", "#e8edf6", "#ffffff"], "cloth", seed=195),
        "feather2": Mat(["#a8b2c4", "#dce2ec", "#f6f8fc", "#ffffff"], "cloth", seed=196),
        "sapph": Mat(["#0a1a6a", "#2a4ad0", "#6a9aff", "#e0eeff"], "gem", glow=True, seed=197),
        "wrap": Mat(["#0e1a4a", "#1a2a6a", "#2a409a", "#4060c0"], "grip", seed=198),
    }
    w = Weapon(m, grip_y=9.5, kind="sword", seed=191)
    # 십자 폼멜
    w.box(-0.6, 0.6, 0, 5, -1.1, 1.1, "gold")
    w.box(-2.6, 2.6, 2, 3.9, -1.1, 1.1, "gold")
    w.cyl(4.5, 15, 1.6, "wrap")
    bands(w, [4.5, 14], 2.1, "gold")
    # 깃털 날개 (가운데에서 부채꼴로)
    for sx in (1, -1):
        for i, (ang, ln) in enumerate(((8, 9.5), (28, 12), (48, 11.5), (68, 9))):
            a = math.radians(ang)
            p0 = (sx * 3, 17.5, 0)
            p1 = (sx * (3 + ln * math.cos(a)), 17.5 + ln * math.sin(a), 0)
            w.tube([p0, p1], lambda t: 1.5 * (1 - t) ** 0.6 + 0.5, "feather" if i % 2 else "feather2")
    # 가운데 금 덩어리 + 보석
    w.box(-3.6, 3.6, 15, 20.9, -2.1, 2.1, "gold")
    w.gem(0, 18, 1.6, "sapph", depth=2.6)
    # 넓은 날
    y0, y1 = 21, 67
    hw = lambda t: (4.6 - 0.9 * t) * taper(t, 0.84, 0.85) + 0.3
    sect(w, y0, y1, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("silver", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("light", lambda X, Y, Z, dl, dr, t: (((np.abs(X) < 1) & (t < 0.8)) |
                                             ((np.abs(Y - 28.5) < 1) & (np.abs(X) < 3))) &
         (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    w.set_aura(["#8a6a10", "#e8c040", "#fff0a0", "#ffffff"], "holy", size=1.1, focus=["light", "edge"])
    return w


def bloodmoon_katana():
    """혈월의 카타나: 아주 긴 노다치, 검은 등과 피처럼 빛나는 물결 하몬, 칼을 받친 붉은 초승달 코등이, 긴 술."""
    m = {
        "black": Mat(["#0a0608", "#1a1014", "#2a1a20", "#3e262e"], "metal", seed=201),
        "steel": Mat(["#3a2a30", "#5a4048", "#806068", "#a88890"], "metal", seed=202),
        "crim": Mat(["#6a0010", "#c00a24", "#ff3a4a", "#ffc0c8"], "flow", glow=True, seed=203),
        "moon": Mat(["#7a0a14", "#d01428", "#ff4a58", "#ffd8d8"], "pulse", glow=True, seed=204),
        "iron": Mat(["#1a1418", "#2e2228", "#463840", "#605058"], "metal", seed=205),
        "wrap": Mat(["#0c0608", "#1a0c10", "#3a141c", "#5a1e2a"], "grip", seed=206),
        "tassel": Mat(["#5a0a10", "#8a1420", "#c02030", "#e85060"], "cloth", seed=207),
    }
    w = Weapon(m, grip_y=9, kind="katana", seed=201)
    w.cyl(1.5, 3.9, 1.9, "iron")
    w.cyl(3.5, 15.5, 1.6, "wrap")
    # 술
    w.tube([(0.5, 1.5, 0.5), (3, 0.8, 0.5), (5.5, 2.8, 0.5), (7.5, 1.2, 0.5)], 0.7, "tassel")
    w.ball(8.6, 1.6, 0.5, 1.4, 1.6, 1.2, "tassel")
    # 초승달 코등이 (뿔이 위로)
    moon = lambda X, Y: (np.hypot(X, Y - 22) <= 7.4) & (np.hypot(X, Y - 25.2) > 6.4) & (Y >= 15)
    w.prism(moon, 1.5, "iron")
    w.fill(lambda X, Y, Z: moon(X, Y) & (np.hypot(X, Y - 22) <= 6.3) & (np.abs(Z) <= 2.0), "moon")
    w.box(-2.1, 2.1, 17, 22.9, -1.6, 1.6, "iron")
    # 긴 날
    y0, y1 = 23, 71
    c = lambda t: -5.0 * t ** 2
    hi = lambda t: c(t) + 2.2 - np.where(t > 0.9, 4.0 * ((t - 0.9) / 0.1) ** 1.3, 0)
    ham = lambda Y: 1.4 + 0.7 * np.sin((Y - y0) * 0.7)
    sect(w, y0, y1, lambda t: c(t) - 2.2, hi, [
        ("steel", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("black", lambda X, Y, Z, dl, dr, t: (dl < 1.6) & (np.abs(Z) <= 1.5)),
        ("crim", lambda X, Y, Z, dl, dr, t: (dr < ham(Y)) & (np.abs(Z) <= 0.5)),
    ])
    w.set_aura(["#3a0008", "#9a0a1a", "#ff2a3a", "#ffc0c8"], "drip", size=1.0, focus=["crim", "moon"])
    return w


def sun_blade():
    """태양검: 손잡이 위에 빛살이 뻗은 태양 원반(무지개 고리), 거기서 뻗어 나간 빛줄기 모양의 넓은 삼각 날. 태양 불꽃 아우라."""
    m = {
        "gold": Mat(["#7a4a08", "#c08018", "#f0b830", "#fff0a0"], "metal", seed=211),
        "sunsteel": Mat(["#b07010", "#e8a830", "#ffd878", "#fffbe0"], "metal", seed=212),
        "core": Mat(["#ff9a10", "#ffc830", "#fff080", "#ffffff"], "flow", glow=True, seed=213),
        "disc": Mat(["#ff7a00", "#ffb020", "#ffe060", "#fffcd8"], "pulse", glow=True, seed=214),
        "ray": Mat(["#8a3a04", "#d06a10", "#f8a030", "#ffd890"], "metal", seed=215),
        "prism": Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=216),
        "wrap": Mat(["#3a0a04", "#6a1a08", "#9a2a10", "#c84a1a"], "grip", seed=217),
    }
    w = Weapon(m, grip_y=9, kind="sword", seed=211)
    # 작은 별 폼멜
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Y - 2.5) * 1.2 <= 2.8) & (np.abs(Z) <= 1.5), "gold")
    w.cyl(4.5, 14, 1.6, "wrap")
    bands(w, [9], 2.1, "gold")
    # 태양 원반
    cy = 20.5
    for k in range(12):
        a = k * math.pi / 6
        if k in (3,):          # 날이 나가는 위쪽은 비운다
            continue
        ln = 11.5 if k % 2 == 0 else 9.0
        ca, sa = math.cos(a), math.sin(a)
        w.prism(lambda X, Y, ca=ca, sa=sa, ln=ln: (lambda u, v: (u > 5) & (np.abs(v) <= 1.8 * np.clip((ln - u) / (ln - 5), 0, 1) + 0.1))(
            X * ca + (Y - cy) * sa, -X * sa + (Y - cy) * ca), 1.0, "ray")
    w.prism(lambda X, Y: np.hypot(X, Y - cy) <= 6.4, 2.0, "gold")
    w.prism(lambda X, Y: np.abs(np.hypot(X, Y - cy) - 5.2) <= 0.6, 2.5, "prism")
    w.prism(lambda X, Y: np.hypot(X, Y - cy) <= 3.8, 2.5, "disc")
    # 빛줄기 날
    y0, y1 = 26, 71
    hw = lambda t: 4.8 * (1 - t) ** 0.9 + 0.7
    sect(w, y0, y1, lambda t: -hw(t), hw, [
        ("gold", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("sunsteel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("core", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 0.6 + 1.6 * (1 - t)) & (t < 0.9) & (np.abs(Z) <= 1.5)),
    ])
    w.set_aura(["#b02a00", "#ff7a10", "#ffd040", "#fffde0"], "flame", size=1.3, focus=["core", "disc"])
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
