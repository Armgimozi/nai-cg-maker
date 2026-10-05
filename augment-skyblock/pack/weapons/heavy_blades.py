"""
heavy_blades: 단검과 대검 13 자루.

python3 heavy_blades.py            -> preview/heavy_blades.png
python3 heavy_blades.py id1 id2    -> 그 무기만 _scratch 미리보기
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, Weapon, preview_sheet  # noqa: E402


# ─────────────────────────── 작은 도구 ───────────────────────────

def poly(pts):
    """XY 다각형 마스크 (짝홀 규칙)."""
    P = np.array(pts, float)

    def m(X, Y):
        inside = np.zeros(np.shape(X), bool)
        for i in range(len(P)):
            x1, y1 = P[i]
            x2, y2 = P[(i + 1) % len(P)]
            if y1 == y2:
                continue
            cond = (y1 > Y) != (y2 > Y)
            xi = (x2 - x1) * (Y - y1) / (y2 - y1) + x1
            inside ^= cond & (X < xi)
        return inside
    return m


def disc(w, cx, cy, r, hz, mat, cz=0.0):
    """앞을 보는 원판 (XY 평면)."""
    return w.fill(lambda X, Y, Z: (np.hypot(X - cx, Y - cy) <= r) & (np.abs(Z - cz) <= hz), mat)


def helix(w, y0, y1, R, turns, r, mat, phase=0.0, cx=0.0):
    """손잡이를 감는 나선 (끈, 뱀, 코일)."""
    pts = []
    n = int(turns * 16) + 2
    for i in range(n + 1):
        t = i / n
        a = phase + t * turns * 2 * math.pi
        pts.append((cx + R * math.cos(a), y0 + (y1 - y0) * t, R * math.sin(a)))
    return w.tube(pts, r, mat)


def rot180(w, y_mid):
    """Z 축으로 180도 돌린 사본을 빈 칸에 더한다 (y_mid 기준). 쌍검용."""
    g = w.grid
    H = g.shape[1]
    shift = int(round(2 * y_mid)) - H        # Y -> 2*y_mid - Y
    g2 = g[::-1, ::-1, :]
    g2 = np.roll(g2, shift, axis=1)
    if shift > 0:
        g2[:, :shift, :] = 0
    elif shift < 0:
        g2[:, shift:, :] = 0
    w.grid = np.where(g > 0, g, g2).astype(g.dtype)
    return w


# ─────────────────────────── 기본 (basic) ───────────────────────────

def hunter_dagger():
    """클립 포인트 사냥칼: 한쪽 날, 두꺼운 등, 나무 손잡이에 놋쇠 리벳, 손가락 가드는 날 쪽에만."""
    m = {
        "steel": Mat(["#4c525a", "#7e868f", "#aab2ba", "#d4dae0"], "metal", seed=1),
        "edge": Mat(["#9aa2aa", "#c4ccd4", "#e4eaf0", "#ffffff"], "metal", seed=2),
        "spine": Mat(["#32373e", "#50565e", "#6c737b", "#8a9198"], "metal", seed=3),
        "wood": Mat(["#3e2412", "#6a4020", "#8e5a30", "#b07a46"], "wood", seed=4),
        "brass": Mat(["#5a4012", "#a07a2a", "#d8b050", "#fff0a0"], "metal", seed=5),
    }
    w = Weapon(m, grip_y=8, kind="dagger", seed=101)
    # 손잡이: 아래가 살짝 불룩한 타원 나무
    w.fill(lambda X, Y, Z: (Y >= 3) & (Y <= 13.5) &
           ((X / (1.9 + 0.35 * np.sin((Y - 3) / 10.5 * math.pi))) ** 2 + (Z / 1.5) ** 2 <= 1), "wood")
    for y in (6, 10.5):
        w.box(-0.6, 0.6, y - 0.6, y + 0.6, -2, 2, "brass")             # 리벳
    w.fill(lambda X, Y, Z: (Y >= 0.5) & (Y <= 3.4) & ((X / 2.3) ** 2 + (Z / 1.8) ** 2 <= 1), "spine")  # 끝 캡
    # 가드: 날 쪽(+X)으로만 튀어나와 아래로 살짝 굽음
    w.box(-2.5, 3.5, 13.5, 15.5, -1.6, 1.6, "spine")
    w.box(3.0, 5.0, 12.0, 15.5, -1.2, 1.2, "spine")

    y0, y1 = 15.5, 35.0

    def xs(t):          # 등 (왼쪽): 곧다가 끝에서 클립(오목하게 깎임)
        return np.where(t < 0.68, -2.0, -2.0 + 1.6 * ((t - 0.68) / 0.32) ** 0.7)

    def xe(t):          # 날 (오른쪽): 배가 불룩했다가 끝으로 휘어 올라감
        u = np.clip((t - 0.55) / 0.45, 0, 1)
        return np.where(t < 0.55, 2.6 + 0.9 * t / 0.55, -0.4 + 3.9 * np.sqrt(1 - u ** 2))

    def blade(X, Y, Z, part):
        t = (Y - y0) / (y1 - y0)
        ok = (t >= 0) & (t <= 1)
        a, b = xs(t), xe(t)
        inb = ok & (X >= a) & (X <= b)
        if part == "spine":
            return inb & (X <= a + 1.2) & (np.abs(Z) <= 1.5)
        if part == "edge":
            return inb & (X >= b - 1.2) & (np.abs(Z) <= 0.5)
        return inb & (np.abs(Z) <= 1.0)

    w.fill(lambda X, Y, Z: blade(X, Y, Z, "body"), "steel")
    w.fill(lambda X, Y, Z: blade(X, Y, Z, "edge"), "edge")
    w.fill(lambda X, Y, Z: blade(X, Y, Z, "spine"), "spine")
    return w


def iron_greatsword():
    """정직한 대검: 넓은 곧은 날 + 홈(fuller), 네모 끝 막대 가드, 긴 가죽 손잡이, 바퀴 폼멜."""
    m = {
        "iron": Mat(["#555b62", "#868d95", "#b0b7bf", "#d8dde2"], "metal", seed=11),
        "edge": Mat(["#9aa1a8", "#c6ccd2", "#e6eaee", "#ffffff"], "metal", seed=12),
        "dark": Mat(["#2c3036", "#454a52", "#60666e", "#7a8088"], "metal", seed=13),
        "leather": Mat(["#2a1810", "#4a2c1a", "#6a4228", "#8a5a38"], "grip", seed=14),
    }
    w = Weapon(m, grip_y=13, kind="greatsword", seed=102)
    disc(w, 0, 3.2, 3.3, 1.5, "dark")                       # 바퀴 폼멜
    disc(w, 0, 3.2, 1.3, 2.5, "iron")                       # 가운데 못
    w.cyl(6, 21, 1.6, "leather")
    w.cyl(6, 7, 1.9, "dark")
    w.cyl(20, 21, 1.9, "dark")
    # 가드: 곧은 막대 + 끝 덩어리 + 가운데 받침
    w.box(-10.5, 10.5, 21, 24, -1.5, 1.5, "dark")
    for s in (-1, 1):
        w.box(min(s * 9.5, s * 12.5), max(s * 9.5, s * 12.5), 20, 25, -2, 2, "dark")
    w.box(-3, 3, 21, 26, -2, 2, "dark")
    # 리카소 + 날
    w.box(-2.5, 2.5, 26, 30, -1.5, 1.5, "iron")
    w.blade(29, 71.5, lambda t: 4.6 - 1.2 * t, mats=("edge", "iron", None), thick=(0.5, 1.5, 1.5), tip=0.14, edge_w=1.2)
    # 홈: 가운데를 얇게 파고 어두운 쇠
    w.clear(lambda X, Y, Z: (np.abs(X) <= 1) & (Y >= 30) & (Y <= 58) & (np.abs(Z) > 0.5))
    w.fill(lambda X, Y, Z: (np.abs(X) <= 1) & (Y >= 30) & (Y <= 58) & (np.abs(Z) <= 0.5), "dark")
    return w


# ─────────────────────────── 섬 (island) ───────────────────────────

def venom_dagger():
    """독니 단검: 코브라 후드 가드의 입에서 휘어진 상아 독니가 뻗고, 끝은 독에 물들었다. 손잡이는 감긴 뱀."""
    m = {
        "fang": Mat(["#8a7a5a", "#c8b890", "#e8dcb8", "#fff8e0"], "flat", seed=21),
        "toxic": Mat(["#1a4a10", "#3a8a1a", "#6ac030", "#b0f060"], "gem", seed=22),
        "venom": Mat(["#3aa010", "#7ae020", "#c0ff50", "#f0ffb0"], "pulse", glow=True, seed=23),
        "scale": Mat(["#10301a", "#1e5028", "#2e7038", "#4a9050"], "scale", seed=24),
        "belly": Mat(["#6a6a20", "#a0a040", "#c8c060", "#e8e090"], "scale", seed=25),
        "core": Mat(["#141410", "#24241c", "#34342a", "#44443a"], "wood", seed=26),
        "eye": Mat(["#a08000", "#f0d020", "#fff070", "#ffffff"], "flat", seed=27),
    }
    w = Weapon(m, grip_y=8, kind="dagger", seed=103)
    w.cyl(2, 14, 1.2, "core")
    helix(w, 1.0, 14.5, 1.5, 3.2, 0.95, "scale", phase=0.3)          # 감긴 뱀 몸
    w.ball(1.4, 1.0, 0.4, 1.2, 1.0, 1.0, "scale")                    # 꼬리 끝
    # 코브라 후드 (앞을 보는 넓은 판)
    hood = lambda X, Y: ((X / 5.8) ** 2 + ((Y - 18.0) / 4.5) ** 2 <= 1) & (Y >= 14)
    w.prism(hood, 1.0, "scale")
    w.prism(lambda X, Y: hood(X, Y) & ((X / 2.2) ** 2 + ((Y - 17.5) / 3.6) ** 2 <= 1), 1.5, "belly")
    # 머리 (후드 위, 입을 벌려 독니를 문다)
    w.ball(0, 22.0, 0.6, 2.6, 2.0, 2.4, "scale")
    for s in (-1, 1):
        w.box(s * 1.5 - 0.5, s * 1.5 + 0.5, 22, 23, 2.2, 3.0, "eye")
    # 독니: 상아에서 독색으로, +X 로 휨
    y0, y1 = 22.5, 41.0

    def fang(X, Y, Z, lo, hi):
        t = (Y - y0) / (y1 - y0)
        off = 2.8 * np.clip(t, 0, 1) ** 1.8
        hw = 2.2 * (1 - np.clip(t, 0, 1)) ** 0.75 + 0.3
        hz = hw * 0.75 + 0.2
        return (t >= lo) & (t <= hi) & (((X - off) / hw) ** 2 + (Z / hz) ** 2 <= 1)
    w.fill(lambda X, Y, Z: fang(X, Y, Z, 0, 0.62), "fang")
    w.fill(lambda X, Y, Z: fang(X, Y, Z, 0.62, 1.0), "toxic")
    # 독 홈 (앞면 가는 빛 줄)
    w.fill(lambda X, Y, Z: fang(X, Y, Z, 0.08, 0.55) & (np.abs(X - 2.8 * ((Y - y0) / (y1 - y0)) ** 1.8) <= 0.5) & (Z > 0.6), "venom")
    return w


def storm_dagger():
    """번개 단검: 날 자체가 지그재그 번개, 손잡이는 구리 코일, 폼멜은 피뢰침 공."""
    m = {
        "bolt": Mat(["#a07a10", "#e0b020", "#f8dc50", "#fff8c0"], "metal", seed=31),
        "rim": Mat(["#e0c040", "#fff080", "#fffbd0", "#ffffff"], "flat", seed=32),
        "spark": Mat(["#fff080", "#fffbd0", "#ffffff", "#ffffff"], "sparkle", glow=True, seed=33),
        "copper": Mat(["#6a3018", "#b0582c", "#e08050", "#ffb080"], "metal", seed=34),
        "patina": Mat(["#2a6a5a", "#3a9a80", "#5ac0a0", "#90e0c8"], "stone", seed=35),
        "core": Mat(["#1a1a22", "#2a2a34", "#3a3a46", "#4a4a58"], "grip", seed=36),
    }
    w = Weapon(m, grip_y=7.5, kind="dagger", seed=104)
    w.cyl(2.5, 12.5, 1.1, "core")
    helix(w, 2.8, 12.2, 1.45, 4.0, 0.75, "copper")                 # 구리 코일
    w.ball(0, 1.6, 0, 2.1, 1.7, 2.1, "copper")                      # 피뢰침 공
    w.ball(0, 1.6, 0, 2.3, 0.6, 2.3, "patina")
    # 가드: 구리 막대, 양 끝 녹청
    w.box(-4, 4, 12.5, 14.5, -1.5, 1.5, "copper")
    w.box(-5, -3.5, 12, 15, -1.5, 1.5, "patina")
    w.box(3.5, 5, 12, 15, -1.5, 1.5, "patina")

    # 번개 모양 날: 오른쪽으로 기운 세 마디
    segs = [(14.5, 23.0, -1.0, 1.6, 2.6, 2.4), (21.5, 31.0, -1.6, 1.4, 2.4, 2.0), (29.5, 41.0, -1.0, 1.4, 2.2, 0.0)]

    def bolt(X, Y, shrink=0.0):
        m_ = np.zeros(np.shape(X), bool)
        for (ya, yb, ca, cb, ha, hb) in segs:
            t = (Y - ya) / (yb - ya)
            c = ca + (cb - ca) * t
            h = ha + (hb - ha) * t - shrink
            m_ |= (t >= 0) & (t <= 1) & (np.abs(X - c) <= h)
        return m_
    w.prism(lambda X, Y: bolt(X, Y), 0.5, "rim")
    w.prism(lambda X, Y: bolt(X, Y, 1.0), 1.0, "bolt")
    # 가운데 전기 줄 (작은 빛)
    w.prism(lambda X, Y: bolt(X, Y, 1.9) & (Y < 38), 1.5, "spark")
    return w


# ─────────────────────────── 서리 (frost) ───────────────────────────

def frost_dagger():
    """고드름 단검: 마름모 단면의 고드름 날, 비대칭 얼음 조각 가드, 서리 낀 손잡이, 아래로 뾰족한 얼음 끝."""
    m = {
        "ice": Mat(["#3a7ab0", "#6ab0e0", "#a8daf8", "#e8f8ff"], "crystal", seed=41),
        "ice_hi": Mat(["#a0d8f8", "#c8ecff", "#e8f8ff", "#ffffff"], "crystal", seed=42),
        "core": Mat(["#40a0ff", "#80d0ff", "#c0f0ff", "#ffffff"], "pulse", glow=True, seed=43),
        "wrap": Mat(["#5a7a98", "#8aa8c4", "#b8d0e4", "#e0eef8"], "grip", seed=44),
        "rime": Mat(["#c8e0f0", "#e0f0fa", "#f4faff", "#ffffff"], "stone", seed=45),
    }
    w = Weapon(m, grip_y=8, kind="dagger", seed=105)
    w.cyl(3, 13.5, 1.3, "wrap")
    for (x, y, z) in ((1.2, 5, 0.8), (-1.0, 9, -0.9), (0.6, 12, 1.1)):
        w.ball(x, y, z, 0.9, 0.9, 0.9, "rime")                     # 서리 덩어리
    # 아래로 뾰족한 얼음 폼멜
    w.fill(lambda X, Y, Z: (Y >= 0) & (Y <= 3.2) & (np.abs(X) + np.abs(Z) <= 0.4 + Y * 0.7), "ice")
    # 가드: 크기가 다른 얼음 조각 세 개
    w.ball(0, 14.5, 0, 2.6, 1.6, 2.0, "ice")
    w.tube([(1, 14.5, 0), (5.5, 17.5, 0.3), (7.5, 21.5, 0.5)], lambda t: 1.4 * (1 - t) + 0.4, "ice_hi")
    w.tube([(-1, 14.5, 0), (-4.0, 16.0, -0.3), (-5.0, 18.5, -0.5)], lambda t: 1.2 * (1 - t) + 0.4, "ice_hi")
    # 고드름 날 (마름모 단면)
    y0, y1 = 15, 42

    def icicle(X, Y, Z, inner=0.0):
        t = (Y - y0) / (y1 - y0)
        hw = 3.0 * (1 - np.clip(t, 0, 1)) ** 0.9 + 0.2 - inner
        hz = 0.4 + 0.75 * (hw - np.abs(X))
        return (t >= 0) & (t <= 1) & (np.abs(X) <= hw) & (np.abs(Z) <= hz)
    w.fill(lambda X, Y, Z: icicle(X, Y, Z), "ice_hi")
    w.fill(lambda X, Y, Z: icicle(X, Y, Z, 1.0), "ice")
    # 빛나는 심지: 마디로 끊긴 룬
    w.fill(lambda X, Y, Z: (np.abs(X) <= 0.5) & (Y >= 17) & (Y <= 33) & (((Y - 17) % 5) < 3.2) & (np.abs(Z) <= 1.6), "core")
    return w


def frost_greatsword():
    """빙하 대검: 금속 없이 얼음으로 자란 날. 가장자리마다 위로 솟은 얼음 가시, 가운데 깊은 청색 심과 룬."""
    m = {
        "ice": Mat(["#4a8ac0", "#7ab8e8", "#b0dcf8", "#e8f8ff"], "crystal", seed=51),
        "frost": Mat(["#b0d8f0", "#d0ecfa", "#eef8ff", "#ffffff"], "crystal", seed=52),
        "deep": Mat(["#0a1a4a", "#14306a", "#20488e", "#3060b0"], "crystal", seed=53),
        "rune": Mat(["#20a0ff", "#60d0ff", "#b0f0ff", "#ffffff"], "pulse", glow=True, seed=54),
        "fur": Mat(["#8090a0", "#b0c0cc", "#d8e2ea", "#f4f8fc"], "cloth", seed=55),
        "strap": Mat(["#1a2a40", "#2a4060", "#3a5880", "#5070a0"], "grip", seed=56),
    }
    w = Weapon(m, grip_y=12, kind="greatsword", seed=106)
    # 육각 얼음 폼멜 (아래로 뾰족)
    w.fill(lambda X, Y, Z: (Y >= 0) & (Y <= 5) & (np.maximum(np.abs(X), np.abs(Z)) <= np.minimum(2.6, 0.5 + Y * 0.9)), "ice")
    w.cyl(5, 20, 1.7, "fur")
    for y in (8, 13, 18):
        w.cyl(y, y + 1, 1.95, "strap")
    # 빙하 덩어리 가드: 높이 다른 결정 기둥들
    for (x, h, r) in ((-6.5, 25, 1.6), (-3.5, 27.5, 2.0), (0, 24, 2.6), (3.5, 26, 1.8), (6.5, 23.5, 1.5), (8.5, 22, 1.0)):
        w.fill(lambda X, Y, Z, x=x, h=h, r=r: (Y >= 20) & (Y <= h) &
               (np.abs(X - x) + np.abs(Z) * 0.8 <= r * np.minimum(1, (h - Y) / 1.8 + 0.35)), "frost")
    # 날 몸통
    y0, y1 = 22, 71.5

    def hw(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        return np.where(t < 0.82, 4.4 - 0.9 * t, (3.66) * ((1 - t) / 0.18) ** 0.9 + 0.3)

    def teeth(X, Y, side, phase):
        # 위로 솟는 가시: 각 마디의 위쪽에서 가장 바깥으로
        p = 8.0
        k = ((Y - y0 - phase) % p) / p
        big = np.clip(1 - (Y - y0) / 40, 0.25, 1)
        out = 3.2 * big * k ** 1.5
        return (Y >= y0 + 3) & (Y <= y0 + 38) & (side * X > 0) & (np.abs(X) <= hw(Y) + out)

    body = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(lambda X, Y: body(X, Y) | teeth(X, Y, 1, 0) | teeth(X, Y, -1, 4), 1.0, "ice")
    w.prism(lambda X, Y: body(X, Y) & (np.abs(X) <= hw(Y) - 1.2), 1.5, "ice")
    w.prism(lambda X, Y: (Y >= y0) & (Y <= y1 - 6) & (np.abs(X) <= 1.0), 2.0, "deep")
    # 룬: 깊은 심 위의 작은 마름모들
    for yc in (30, 40, 50):
        w.fill(lambda X, Y, Z, yc=yc: (np.abs(X) + np.abs(Y - yc) <= 1.6) & (np.abs(Z) <= 2.5), "rune")
    return w


# ─────────────────────────── 화염 (flame) ───────────────────────────

def ember_greatsword():
    """화염 대검: 물결치는 플람베르주 날, 검게 그을린 강철 사이로 녹은 균열이 빛나고, 가드는 불꽃처럼 말려 올라감."""
    m = {
        "char": Mat(["#141010", "#241a18", "#3a2a24", "#4e3a30"], "metal", seed=61),
        "hot": Mat(["#6a1a08", "#b0400c", "#e07020", "#ffb050"], "metal", seed=62),
        "magma": Mat(["#8a1a00", "#e04a0a", "#ffa020", "#fff0a0"], "fire", glow=True, seed=63),
        "iron": Mat(["#1e1c1c", "#3a3434", "#565050", "#746c6a"], "metal", seed=64),
        "leather": Mat(["#2a0a08", "#4a1410", "#6a2018", "#8a3020"], "grip", seed=65),
    }
    w = Weapon(m, grip_y=12, kind="greatsword", seed=107)
    # 폼멜: 쇠 발톱이 잡은 불씨
    w.ball(0, 2.8, 0, 2.2, 2.2, 2.2, "magma")
    for s in (-1, 1):
        w.tube([(s * 0.8, 6, 0), (s * 2.8, 3.5, 0), (s * 2.2, 0.8, 0)], 0.8, "iron")
        w.tube([(0, 6, s * 0.8), (0, 3.5, s * 2.8), (0, 0.8, s * 2.2)], 0.8, "iron")
    w.cyl(5, 20, 1.6, "leather")
    w.cyl(5, 6, 1.9, "iron")
    # 가드: 가운데 덩어리 + 위로 말려 올라가는 불꽃 갈퀴
    w.box(-3.5, 3.5, 20, 24, -2, 2, "iron")
    for s in (-1, 1):
        w.tube([(s * 3, 22, 0), (s * 7, 21.5, 0), (s * 9.5, 24, 0), (s * 9.5, 27, 0), (s * 8, 28.5, 0)],
               lambda t: 1.6 - 0.9 * t, "iron")
        w.tube([(s * 6.5, 22.5, 0), (s * 6.5, 25.5, 0), (s * 5.2, 27, 0)], lambda t: 1.0 - 0.4 * t, "char")
    # 플람베르주 날
    y0, y1 = 24, 71.5

    def off(Y):
        return 1.3 * np.sin((Y - y0) / 8.0 * 2 * math.pi)

    def hw(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        base = 4.4 - 1.2 * t
        return np.where(t > 0.86, base * ((1 - t) / 0.14) ** 0.8 + 0.3, base)

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X - off(Y)) <= hw(Y))
    w.prism(inb, 0.5, "hot")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X - off(Y)) <= hw(Y) - 1.1), 1.5, "char")
    # 녹은 균열: 날 가운데 물결 심지
    w.prism(lambda X, Y: (Y >= y0 + 1) & (Y <= y1 - 7) & (np.abs(X - off(Y) * 0.6) <= 0.9), 1.9, "magma")
    return w


# ─────────────────────────── 공허 (void) ───────────────────────────

def shadow_dagger():
    """그림자 쿠나이: 가드 없이 잎 모양 날, 천을 감은 손잡이, 고리 폼멜에서 흩날리는 보라 끈."""
    m = {
        "black": Mat(["#0c0a12", "#18141e", "#241e2c", "#342c3e"], "metal", seed=71),
        "edge": Mat(["#2a2238", "#40345a", "#5a4a7a", "#7a68a0"], "metal", seed=72),
        "glow": Mat(["#6a20c0", "#9a4af0", "#c890ff", "#f0e0ff"], "flow", glow=True, seed=73),
        "cloth": Mat(["#120e18", "#221a2c", "#342840", "#463656"], "grip", seed=74),
        "ribbon": Mat(["#3a1060", "#5a1a8a", "#7a2ab0", "#9a4ad0"], "cloth", seed=75),
    }
    w = Weapon(m, grip_y=13, kind="dagger", seed=108)
    # 고리 폼멜
    w.fill(lambda X, Y, Z: (np.abs(np.hypot(X, Y - 5.5) - 2.6) <= 0.9) & (np.abs(Z) <= 0.6), "black")
    # 끈: 고리에서 아래로 흩날림
    w.tube([(1.5, 3.2, 0.5), (3.5, 1.5, 0.5), (6.0, 1.8, 0.5), (8.0, 0.6, 0.5)], 0.8, "ribbon")
    w.tube([(0.5, 3.0, -0.5), (1.5, 0.8, -0.5), (3.5, 0.5, -0.5)], 0.7, "ribbon")
    w.box(-1.5, 1.5, 8.5, 9.5, -1.5, 1.5, "black")
    w.cyl(9, 18, 1.2, "cloth")
    helix(w, 9.2, 17.8, 1.35, 3.0, 0.5, "ribbon", phase=1.0)
    w.box(-1.5, 1.5, 18, 19.5, -1.5, 1.5, "black")
    # 잎 모양 날 (마름모 단면)
    y0, y1 = 19.5, 41

    def hw(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        return 1.2 + 2.6 * np.sin(np.minimum(t / 0.4, 1) * math.pi / 2) * np.where(t > 0.4, ((1 - t) / 0.6) ** 0.9, 1)

    leaf = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(leaf, lambda X, Y: 0.5 + 0.45 * np.clip(hw(Y) - np.abs(X), 0, 3), "edge")
    w.prism(lambda X, Y: leaf(X, Y) & (np.abs(X) <= hw(Y) - 1.1), lambda X, Y: 0.5 + 0.45 * np.clip(hw(Y) - np.abs(X), 0, 3), "black")
    # 빛나는 등줄 (가운데 가는 보라 선)
    w.fill(lambda X, Y, Z: (np.abs(X) <= 0.5) & (Y >= y0 + 1) & (Y <= y1 - 4) & (np.abs(Z) <= 1.9), "glow")
    return w


def ender_dagger():
    """엔더 단검: 흑요석 날이 세 토막으로 떨어져 떠 있고(순간이동 중), 엔드석 가드 가운데 엔더의 눈."""
    m = {
        "obsid": Mat(["#0e0818", "#1e1030", "#30184a", "#482a66"], "crystal", seed=81),
        "rim": Mat(["#5a3a8a", "#8a5ac0", "#b88ae8", "#e0c8ff"], "metal", seed=82),
        "portal": Mat(["#6a10a0", "#b030e0", "#e070ff", "#ffd0ff"], "sparkle", glow=True, seed=83),
        "endstone": Mat(["#a8a670", "#cccc90", "#e0e0aa", "#f4f4c8"], "stone", seed=84),
        "purpur": Mat(["#6a4a6a", "#946a94", "#b48cb4", "#d0aed0"], "stone", seed=85),
        "eye": Mat(["#0a4a3a", "#1a8a6a", "#40c8a0", "#a0ffe0"], "gem", glow=True, seed=86),
        "pupil": Mat(["#020806", "#061410", "#0a201a", "#102a22"], "flat", seed=87),
    }
    w = Weapon(m, grip_y=8, kind="dagger", seed=109)
    w.box(-2, 2, 0, 3, -2, 2, "endstone")                          # 엔드석 폼멜
    w.box(-1.5, 1.5, 3, 13, -1.5, 1.5, "purpur")                    # 퍼퍼 기둥 손잡이
    for y in (5.5, 10):
        w.box(-1.8, 1.8, y, y + 1, -1.8, 1.8, "endstone")
    # 가드: 엔드석 틀 + 양옆 흑요석 뿔 + 엔더의 눈
    w.box(-4.5, 4.5, 13, 16, -1.5, 1.5, "endstone")
    for s in (-1, 1):
        w.tube([(s * 4.5, 14.5, 0), (s * 6.5, 16.5, 0), (s * 7, 19.5, 0)], lambda t: 1.2 - 0.6 * t, "obsid")
    w.ball(0, 15.5, 0, 2.6, 2.6, 2.3, "eye")
    w.box(-0.5, 0.5, 14, 17, 1.5, 2.5, "pupil")
    w.box(-0.5, 0.5, 14, 17, -2.5, -1.5, "pupil")

    # 떠 있는 세 토막 (조금씩 옆으로 밀려 있음)
    y0, y1 = 18, 42
    hw = lambda Y: 2.9 * (1 - np.clip((Y - y0) / (y1 - y0), 0, 1)) ** 0.6 + 0.3
    pieces = [(18.5, 26, 0.0), (27.5, 34.5, 0.9), (36, 42, -0.6)]
    for (a, b, dx) in pieces:
        cut = lambda X, Y, a=a, b=b, dx=dx: (Y >= a + 0.25 * (X - dx)) & (Y <= b + 0.25 * (X - dx)) & (Y >= y0) & (Y <= y1)
        w.prism(lambda X, Y, dx=dx, cut=cut: cut(X, Y) & (np.abs(X - dx) <= hw(Y)), 0.5, "rim")
        w.prism(lambda X, Y, dx=dx, cut=cut: cut(X, Y) & (np.abs(X - dx) <= hw(Y) - 1), 1.0, "obsid")
    # 토막 사이 틈에서 새는 포털 빛
    for (yy, dx) in ((26.8, 0.4), (35.3, 0.2)):
        w.fill(lambda X, Y, Z, yy=yy, dx=dx: (np.abs(X - dx) <= 1.0) & (np.abs(Y - yy - 0.25 * (X - dx)) <= 0.6) & (np.abs(Z) <= 0.5), "portal")
    # 떠다니는 작은 포털 조각
    for (x, y) in ((4.5, 30.5), (-4, 37.5), (3.5, 41)):
        w.box(x - 0.5, x + 0.5, y - 0.5, y + 0.5, -0.5, 0.5, "portal")
    return w


# ─────────────────────────── 보스 (boss) ───────────────────────────

def frostlord_greatsword():
    """서리 군주의 대검: 왕관 가드(얼음 보석 박힌 은관), 한밤 강철 날 가운데 흐르는 서리 심지, 한쪽에 얼어붙은 가시."""
    m = {
        "night": Mat(["#0a1030", "#16204e", "#24346e", "#344a90"], "metal", seed=91),
        "silver": Mat(["#6a7a94", "#a0b0c8", "#d0dcec", "#ffffff"], "metal", seed=92),
        "frost": Mat(["#1a5ad0", "#40a0ff", "#a0e0ff", "#ffffff"], "flow", glow=True, seed=93),
        "icegem": Mat(["#2080e0", "#60c0ff", "#c0f0ff", "#ffffff"], "sparkle", glow=True, seed=94),
        "ice": Mat(["#6aa8d8", "#a0d0f0", "#d0ecfc", "#ffffff"], "crystal", seed=95),
        "grip": Mat(["#0a0e20", "#141c36", "#202c50", "#2c3c6a"], "grip", seed=96),
    }
    w = Weapon(m, grip_y=14, kind="greatsword", seed=110)
    # 폼멜: 눈송이 (여섯 팔)
    yc = 4.2
    for k in range(6):
        a = math.pi / 2 + k * math.pi / 3
        w.tube([(0, yc, 0), (3.8 * math.cos(a), yc + 3.8 * math.sin(a), 0)], 0.9, "silver")
    w.gem(0, yc, 1.4, "icegem", depth=1.8)
    w.cyl(7, 21, 1.6, "grip")
    helix(w, 7.5, 20.5, 1.6, 4.0, 0.5, "silver")
    # 왕관 가드: 띠 + 다섯 개의 뾰족한 관 + 보석
    w.box(-8, 8, 21, 24.5, -2, 2, "silver")
    w.box(-9, 9, 20.5, 21.5, -2.4, 2.4, "silver")
    for (x, h) in ((-7, 29), (-3.5, 31), (3.5, 31), (7, 29)):
        w.fill(lambda X, Y, Z, x=x, h=h: (Y >= 24) & (Y <= h) & (np.abs(X - x) <= 1.6 * (h - Y) / (h - 24) + 0.4) & (np.abs(Z) <= 1.5), "silver")
        w.ball(x, h, 0, 0.9, 0.9, 1.0, "icegem")
    w.gem(0, 22.8, 1.9, "icegem", frame="silver", depth=2.6)
    # 날: 넓고 위로 갈수록 살짝 넓어졌다가 뾰족
    y0, y1 = 24.5, 72

    def hw(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        base = 4.4 + 1.3 * np.sin(t * math.pi * 0.8)
        return np.where(t > 0.8, base * ((1 - t) / 0.2) ** 0.8 + 0.3, base)

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, 0.5, "silver")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.2), 1.5, "night")
    w.prism(lambda X, Y: (Y >= y0 + 4) & (Y <= y1 - 8) & (np.abs(X) <= 1.0), 2.0, "frost")
    # 한쪽(+X)에 얼어붙은 얼음 가시
    for (y, L, ang) in ((36, 5.5, 50), (42, 4.0, 55), (47, 2.5, 60)):
        a = math.radians(ang)
        x = hw(np.array(y)) - 0.5
        w.tube([(float(x), y, 0), (float(x) + L * math.sin(a), y + L * math.cos(a), 0)], lambda t: 1.3 * (1 - t) + 0.4, "ice")
    w.set_aura(["#1a2a8a", "#2a6ae0", "#5ad0ff", "#e8ffff"], "frost", size=1.2, focus=["frost", "icegem"])
    return w


def shadow_twinblade():
    """암살자의 쌍검: 손잡이 하나 양끝에 서로 반대로 휜 초승달 날 (180도 대칭). 등에 톱니, 날끝은 보라빛."""
    m = {
        "blade": Mat(["#0e0a16", "#1c1428", "#2c203e", "#3e3056"], "metal", seed=121),
        "edge": Mat(["#8a3af0", "#b070ff", "#d8b0ff", "#ffffff"], "flow", glow=True, seed=122),
        "steel": Mat(["#2a2436", "#463c58", "#62567a", "#80749a"], "metal", seed=123),
        "wrap": Mat(["#0a0810", "#18121e", "#261c30", "#342842"], "grip", seed=124),
        "gem": Mat(["#5a0aa0", "#a030f0", "#e090ff", "#ffffff"], "pulse", glow=True, seed=125),
    }
    yc = 36
    w = Weapon(m, grip_y=yc, kind="sword", seed=111)
    # 위쪽 절반만 만들고 180도 돌려 복사
    w.cyl(yc, yc + 8, 1.5, "wrap")
    w.box(-2, 2, yc + 8, yc + 10, -1.8, 1.8, "steel")
    # 갈고리 가드 (날 반대쪽으로 굽은 발톱)
    w.tube([(-1.5, yc + 9, 0), (-4.5, yc + 9.5, 0), (-6, yc + 7, 0)], lambda t: 1.2 - 0.5 * t, "steel")
    # 초승달 날: 등(왼쪽)은 바깥으로 휘고, 날(오른쪽)은 빛나는 가장자리
    y0, y1 = yc + 10, 71.5

    def ctr(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        return 6.5 * t ** 2

    def hw(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        return 2.8 * (1 - t) ** 0.7 + 0.4 + 0.8 * np.sin(t * math.pi)

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X - ctr(Y)) <= hw(Y))
    w.prism(inb, 1.0, "blade")
    w.prism(lambda X, Y: inb(X, Y) & (X - ctr(Y) >= hw(Y) - 1.1), 0.5, "edge")
    # 등 톱니 (왼쪽)
    w.prism(lambda X, Y: (Y >= y0 + 2) & (Y <= y0 + 14) & (X - ctr(Y) < -hw(Y) + 0.2) &
            (X - ctr(Y) >= -hw(Y) - 1.8 * (((Y - y0) % 4) / 4)), 1.0, "steel")
    rot180(w, yc)
    # 가운데 보석
    w.gem(0, yc, 1.6, "gem", frame="steel", depth=2.4)
    w.box(-2, 2, yc - 0.5, yc + 0.5, -2, 2, "steel")
    w.gem(0, yc, 1.4, "gem", depth=2.6)
    w.set_aura(["#2a0a5a", "#6a1ad0", "#b060ff", "#f0d8ff"], "void", size=1.0, focus=["edge", "gem"])
    return w


def star_greatsword():
    """별의 대검: 별밤처럼 반짝이는 남색 날 + 금 테두리, 날 끝은 네 갈래 별빛, 가드는 커다란 금빛 오각 별."""
    m = {
        "night": Mat(["#0a0a2a", "#16164a", "#262a70", "#3a4098"], "sparkle", glow=True, seed=131),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c050", "#fff4b0"], "metal", seed=132),
        "white": Mat(["#c8c8f0", "#e8e8ff", "#ffffff", "#ffffff"], "pulse", glow=True, seed=133),
        "rock": Mat(["#1a1820", "#2e2a34", "#46404c", "#5e5664"], "stone", seed=134),
        "wrap": Mat(["#10143a", "#1c2458", "#2a3478", "#3a4698"], "grip", seed=135),
        "silver": Mat(["#6a6a8a", "#a0a0c0", "#d0d0ea", "#ffffff"], "metal", seed=136),
    }
    w = Weapon(m, grip_y=11, kind="greatsword", seed=112)
    # 폼멜: 운석 덩어리
    w.ball(0, 2.8, 0, 2.8, 2.8, 2.6, "rock")
    w.ball(0.8, 3.3, 1.2, 1.1, 1.0, 1.6, "white")
    w.cyl(5, 18, 1.6, "wrap")
    helix(w, 5.5, 17.5, 1.6, 3.0, 0.55, "gold")
    # 오각 별 가드
    sc, R, r = 22.5, 8.5, 3.6
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = R if k % 2 == 0 else r
        pts.append((rr * math.cos(a), sc + rr * math.sin(a)))
    w.prism(poly(pts), 1.5, "gold")
    w.gem(0, sc, 2.0, "white", frame="silver", depth=2.5)
    # 날: 금 테두리, 별밤 몸통
    y0, y1, ys = 28, 63, 63      # ys: 네 갈래 별의 가운데

    def hw(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        return 4.6 - 1.4 * t

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, 0.5, "gold")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.0), 1.5, "night")
    # 끝: 네 갈래 별빛 (세로가 길다)
    star4 = lambda X, Y: (np.abs(X) / 6.5) ** 0.55 + (np.abs(Y - ys) / 9.0) ** 0.55 <= 1
    w.prism(star4, lambda X, Y: 0.5 + 1.0 * np.clip(1 - np.abs(X) / 3 - np.abs(Y - ys) / 5, 0, 1), "gold")
    w.prism(lambda X, Y: (np.abs(X) / 4.8) ** 0.55 + (np.abs(Y - ys) / 7.0) ** 0.55 <= 1, 1.0, "white")
    w.set_aura(["#2a1a7a", "#6a5ae0", "#ffd86a", "#fffbe0"], "holy", size=1.1, focus=["white", "night"])
    return w


def prism_greatsword():
    """프리즘 대검: 아래를 향한 삼각 프리즘 가드에서 무지개 빛줄기가 갈라져 두 장의 수정 판 사이로 솟는다."""
    m = {
        "crystal": Mat(["#a8a0d8", "#d0c8f0", "#ece8ff", "#ffffff"], "crystal", seed=141),
        "facet": Mat(["#e0e8ff", "#f0f4ff", "#ffffff", "#ffffff"], "crystal", seed=142),
        "beam": Mat(["#ff0000", "#00ff00", "#0000ff", "#ffffff"], "rainbow", glow=True, seed=143),
        "gold": Mat(["#7a5a18", "#c09030", "#f0d060", "#fff8c0"], "metal", seed=144),
        "white": Mat(["#a8a8b8", "#d0d0dc", "#ececf4", "#ffffff"], "grip", seed=145),
        "pink": Mat(["#c04080", "#f070b0", "#ffb0d8", "#ffffff"], "gem", glow=True, seed=146),
        "cyan": Mat(["#2090c0", "#40c8f0", "#a0f0ff", "#ffffff"], "gem", glow=True, seed=147),
        "yellow": Mat(["#c09010", "#f0c830", "#fff080", "#ffffff"], "gem", glow=True, seed=148),
    }
    w = Weapon(m, grip_y=11, kind="greatsword", seed=113)
    w.gem(0, 2.6, 1.8, "beam", frame="gold", depth=2.0)               # 무지개 폼멜
    w.cyl(4.5, 18, 1.6, "white")
    for y in (4.5, 11, 17.5):
        w.cyl(y, y + 0.9, 1.9, "gold")
    # 삼각 프리즘 가드 (꼭짓점이 아래)
    tri = poly([(-9, 27), (9, 27), (0, 17.5)])
    w.prism(tri, 2.0, "gold")
    w.prism(lambda X, Y: poly([(-7, 26), (7, 26), (0, 19.5)])(X, Y), 2.5, "crystal")
    w.prism(lambda X, Y: poly([(-1.5, 26), (1.5, 26), (0, 21)])(X, Y), 3.0, "beam")
    # 날: 두 장의 수정 판, 사이에 무지개 빛줄기
    y0, y1 = 27, 72

    def hw(Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        return np.where(t > 0.78, 5.6 * ((1 - t) / 0.22) ** 0.75 + 0.3, 5.6 - 0.2 * t)

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, lambda X, Y: 0.5 + 0.5 * np.clip(hw(Y) - np.abs(X), 0, 2), "facet")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.2), 1.5, "crystal")
    slot = lambda X, Y: (Y >= y0) & (Y <= 62) & (np.abs(X) <= 1.6)
    w.clear(lambda X, Y, Z: slot(X, Y))
    w.prism(slot, 1.0, "beam")
    # 떠 있는 작은 수정 조각
    for (x, y, mt) in ((-9, 36, "pink"), (9.5, 44, "cyan"), (-8.5, 52, "yellow")):
        w.fill(lambda X, Y, Z, x=x, y=y: (np.abs(X - x) / 1.4 + np.abs(Y - y) / 2.4 + np.abs(Z) / 1.2) <= 1, mt)
    w.set_aura("prism", "holy", size=1.25, focus=["beam"])
    return w


# ─────────────────────────── 등록 ───────────────────────────

WEAPONS = {
    "hunter_dagger": hunter_dagger,
    "iron_greatsword": iron_greatsword,
    "venom_dagger": venom_dagger,
    "storm_dagger": storm_dagger,
    "frost_dagger": frost_dagger,
    "frost_greatsword": frost_greatsword,
    "ember_greatsword": ember_greatsword,
    "shadow_dagger": shadow_dagger,
    "ender_dagger": ender_dagger,
    "frostlord_greatsword": frostlord_greatsword,
    "shadow_twinblade": shadow_twinblade,
    "star_greatsword": star_greatsword,
    "prism_greatsword": prism_greatsword,
}

NAMES = {
    "hunter_dagger": "사냥꾼의 단검",
    "iron_greatsword": "철 대검",
    "venom_dagger": "독사의 단검",
    "storm_dagger": "번개 단검",
    "frost_dagger": "서리 단검",
    "frost_greatsword": "서리 대검",
    "ember_greatsword": "화염 대검",
    "shadow_dagger": "그림자 단검",
    "ender_dagger": "엔더 단검",
    "frostlord_greatsword": "서리 군주의 대검",
    "shadow_twinblade": "암살자의 쌍검",
    "star_greatsword": "별의 대검",
    "prism_greatsword": "프리즘 대검",
}

if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids:
        sub = {k: WEAPONS[k] for k in ids}
        out = os.path.join(HERE, "preview", "_scratch", "heavy_blades_part.png")
        preview_sheet(sub, out, names=NAMES)
    else:
        preview_sheet(WEAPONS, os.path.join(HERE, "preview", "heavy_blades.png"), names=NAMES)
