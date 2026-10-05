"""
heavy_blades: 단검과 대검 13 자루.

python3 heavy_blades.py            -> preview/heavy_blades.png
python3 heavy_blades.py id1 id2    -> 그 무기만 preview/_scratch/heavy_blades_part.png
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


def rings(w, ys, r, mat, h=1.0, cx=0.0):
    """손잡이에 두른 고리들."""
    for y in ys:
        w.cyl(y, y + h, r, mat, cx=cx)
    return w


def helix(w, y0, y1, R, turns, r, mat, phase=0.0, cx=0.0):
    """손잡이를 감는 나선."""
    pts = []
    n = int(turns * 16) + 2
    for i in range(n + 1):
        t = i / n
        a = phase + t * turns * 2 * math.pi
        pts.append((cx + R * math.cos(a), y0 + (y1 - y0) * t, R * math.sin(a)))
    return w.tube(pts, r, mat)


def tri(w, a, b, c, hz, mat):
    """XY 삼각형 판."""
    return w.prism(poly([a, b, c]), hz, mat)


def tnorm(Y, y0, y1):
    return np.clip((Y - y0) / (y1 - y0), 0, 1)


def rot180(w, y_mid):
    """Z 축으로 180도 돌린 사본을 빈 칸에 더한다 (y_mid 기준). 쌍검용."""
    g = w.grid
    H = g.shape[1]
    shift = int(round(2 * y_mid)) - H        # Y -> 2*y_mid - Y
    g2 = np.roll(g[::-1, ::-1, :], shift, axis=1)
    if shift > 0:
        g2[:, :shift, :] = 0
    elif shift < 0:
        g2[:, shift:, :] = 0
    w.grid = np.where(g > 0, g, g2).astype(g.dtype)
    return w


# ─────────────────────────── 기본 (basic) ───────────────────────────

def hunter_dagger():
    """클립 포인트 사냥칼: 불룩한 배의 외날, 두꺼운 등과 반짝이는 클립(가짜 날), 날 쪽으로 굽은 나무 손잡이와 놋쇠 리벳, 손가락 가드."""
    m = {
        "steel": Mat(["#3e444c", "#646c76", "#8a929c", "#b0b8c2"], "metal", seed=1),
        "edge": Mat(["#b8c0c8", "#d8dee4", "#f0f4f8", "#ffffff"], "metal", seed=2),
        "spine": Mat(["#24282e", "#3a3f46", "#50565e", "#6a7078"], "metal", seed=3),
        "wood": Mat(["#3e2412", "#6a4020", "#8e5a30", "#b07a46"], "wood", seed=4),
        "brass": Mat(["#5a4012", "#a07a2a", "#d8b050", "#fff0a0"], "metal", seed=5),
    }
    w = Weapon(m, grip_y=8.5, kind="dagger", seed=101)
    # 손잡이: 아래로 갈수록 날 쪽(+X)으로 굽는다 (새머리 손잡이)
    cx = lambda Y: 1.6 * np.clip((9 - Y) / 7, 0, 1) ** 2
    w.fill(lambda X, Y, Z: (Y >= 1.5) & (Y <= 13.5) & (((X - cx(Y)) / 1.9) ** 2 + (Z / 1.5) ** 2 <= 1), "wood")
    w.ball(1.9, 1.6, 0, 2.6, 1.6, 1.7, "spine")                      # 굽은 끝 캡
    for y in (6, 10.5):
        w.box(-0.6 + cx(y), 0.6 + cx(y), y - 0.6, y + 0.6, -2, 2, "brass")   # 리벳
    # 가드: 날 쪽(+X)으로 길고 끝이 아래로 굽은 손가락 걸이
    w.box(-3.0, 3.5, 13.5, 15.5, -1.6, 1.6, "spine")
    w.box(3.0, 5.0, 11.5, 15.5, -1.2, 1.2, "spine")

    y0, y1 = 15.5, 36.0

    def xs(t):          # 등 (왼쪽): 곧다가 끝에서 오목하게 깎인 클립
        u = np.clip((t - 0.58) / 0.42, 0, 1)
        return np.where(t < 0.58, -2.5, -2.5 + 3.8 * u ** 1.6)

    def xe(t):          # 날 (오른쪽): 배가 불룩했다가 끝으로 휘어 올라감
        u = np.clip((t - 0.45) / 0.55, 0, 1)
        return np.where(t < 0.45, 3.0 + 1.6 * t / 0.45, 1.3 + 3.3 * np.sqrt(1 - u ** 2))

    def blade(X, Y, Z, part):
        t = (Y - y0) / (y1 - y0)
        tc = np.clip(t, 0, 1)
        a, b = xs(tc), xe(tc)
        inb = (t >= 0) & (t <= 1) & (X >= a) & (X <= b)
        if part == "spine":
            return inb & (X <= a + 1.2) & (np.abs(Z) <= 1.5) & (t < 0.58)
        if part == "clip":
            return inb & (X <= a + 1.2) & (t >= 0.58)
        if part == "edge":
            return inb & (X >= b - 1.3) & (np.abs(Z) <= 0.5)
        return inb & (np.abs(Z) <= 1.0)

    w.fill(lambda X, Y, Z: blade(X, Y, Z, "body"), "steel")
    w.fill(lambda X, Y, Z: blade(X, Y, Z, "edge") | (blade(X, Y, Z, "clip") & (np.abs(Z) <= 0.5)), "edge")
    w.fill(lambda X, Y, Z: blade(X, Y, Z, "spine"), "spine")
    # 엄지 홈 (등에 파인 톱니)
    w.clear(lambda X, Y, Z: (X < -2) & (Y > 16) & (Y < 22) & ((Y.astype(int) % 2) == 0))
    return w


def iron_greatsword():
    """정직한 대검: 넓은 곧은 날 + 홈(fuller), 네모 끝 막대 가드, 긴 가죽 손잡이, 바퀴 폼멜."""
    m = {
        "iron": Mat(["#555b62", "#868d95", "#b0b7bf", "#d8dde2"], "metal", seed=11),
        "edge": Mat(["#a8aeb4", "#ccd2d8", "#eaeef2", "#ffffff"], "metal", seed=12),
        "dark": Mat(["#25292e", "#3c4148", "#565c64", "#70767e"], "metal", seed=13),
        "leather": Mat(["#2a1810", "#4a2c1a", "#6a4228", "#8a5a38"], "grip", seed=14),
    }
    w = Weapon(m, grip_y=14, kind="greatsword", seed=102)
    disc(w, 0, 3.6, 3.7, 1.5, "dark")                       # 바퀴 폼멜
    disc(w, 0, 3.6, 1.6, 2.5, "iron")                       # 가운데 못
    w.cyl(7, 21, 1.6, "leather")
    rings(w, (7, 20), 1.9, "dark")
    # 가드: 곧은 막대 + 끝 덩어리 + 가운데 받침
    w.box(-11, 11, 21, 24, -1.5, 1.5, "dark")
    for s in (-1, 1):
        w.box(min(s * 10, s * 13), max(s * 10, s * 13), 20, 25, -2, 2, "dark")
    w.box(-3.5, 3.5, 20.5, 26, -2, 2, "dark")
    # 리카소 + 날
    w.box(-2.5, 2.5, 26, 30, -1.5, 1.5, "iron")
    w.blade(29, 71.5, lambda t: 4.8 - 1.4 * t, mats=("edge", "iron", None), thick=(0.5, 1.5, 1.5), tip=0.14, edge_w=1.2)
    # 홈: 가운데를 얇게 파고 어두운 쇠
    w.clear(lambda X, Y, Z: (np.abs(X) <= 1) & (Y >= 31) & (Y <= 61) & (np.abs(Z) > 0.5))
    w.fill(lambda X, Y, Z: (np.abs(X) <= 1) & (Y >= 31) & (Y <= 61) & (np.abs(Z) <= 0.5), "dark")
    return w


# ─────────────────────────── 섬 (island) ───────────────────────────

def venom_dagger():
    """독사의 단검: 옆모습 뱀 머리가 가드 한쪽(입을 벌리고 송곳니), 다른 쪽은 몸통이 감긴 고리. 목에서 휘어진 상아 독니 날이 솟고, 홈에 독이 빛난다."""
    m = {
        "fang": Mat(["#9a8a68", "#cfc09a", "#ece2c4", "#fffaea"], "flat", seed=21),
        "bone": Mat(["#6a5a40", "#8a7a5a", "#a89a78", "#c4b896"], "flat", seed=22),
        "venom": Mat(["#3aa010", "#7ae020", "#c0ff50", "#f0ffb0"], "pulse", glow=True, seed=23),
        "scale": Mat(["#1e4a24", "#2e6a36", "#428a48", "#62aa62"], "scale", seed=24),
        "mark": Mat(["#08140a", "#0e2010", "#162e18", "#1e3a20"], "scale", seed=28),
        "belly": Mat(["#7a7020", "#a8a040", "#ccc060", "#e8e090"], "scale", seed=25),
        "eye": Mat(["#a08000", "#f0d020", "#fff070", "#ffffff"], "flat", seed=27),
        "mouth": Mat(["#4a0a14", "#7a1a24", "#a02a34", "#c04048"], "flat", seed=29),
    }
    w = Weapon(m, grip_y=7.5, kind="dagger", seed=103)
    # 손잡이: 뱀 몸통 (앞에 노란 배 줄무늬, 어두운 띠), 끝은 둥근 똬리
    w.cyl(2.5, 13, 1.6, "scale")
    w.fill(lambda X, Y, Z: (Y >= 2.5) & (Y <= 13) & (np.abs(X) <= 0.6) & (np.abs(Z) > 0.8) & (np.abs(Z) <= 1.6), "belly")
    rings(w, (4.5, 7.5, 10.5), 1.75, "mark")
    w.ball(0, 1.8, 0, 2.4, 1.8, 2.4, "scale")
    w.cyl(1.5, 2.2, 2.5, "mark")
    # 가드 왼쪽: 몸통이 한 번 감긴 고리
    w.fill(lambda X, Y, Z: (np.abs(np.hypot(X + 4.0, (Y - 15.0) * 1.15) - 2.6) <= 1.1) & (np.abs(Z) <= 1.3), "scale")
    # 가드 오른쪽: 옆모습 머리, 입을 벌림
    upper = poly([(-1.5, 14.6), (-1.5, 18.2), (4.0, 19.0), (8.0, 18.4), (10.4, 17.0), (10.2, 16.2), (6.0, 16.0)])
    lower = poly([(-1.5, 12.4), (-1.5, 14.6), (6.0, 15.0), (9.6, 13.6), (9.2, 12.6), (4.5, 11.8)])
    w.prism(upper, lambda X, Y: 1.7 - 0.06 * np.clip(X, 0, 10), "scale")
    w.prism(lower, lambda X, Y: 1.4 - 0.05 * np.clip(X, 0, 10), "scale")
    w.prism(poly([(4.0, 15.0), (10.6, 16.8), (10.0, 13.4)]), 0.9, "mouth")              # 벌린 입 안
    w.box(-1.5, 9.0, 11.5, 12.6, -1.0, 1.0, "belly")                                    # 턱 밑 배
    w.box(3.6, 5.6, 16.6, 18.2, -1.9, 1.9, "eye")
    w.box(4.4, 4.8, 16.6, 18.2, -2.1, 2.1, "mark")                                      # 세로 동공
    w.prism(poly([(1.0, 18.4), (6.5, 18.9), (2.0, 19.2)]), 1.8, "mark")                 # 눈썹 비늘
    tri(w, (8.4, 16.4), (9.8, 16.6), (9.2, 13.6), 0.6, "fang")                          # 위 송곳니
    tri(w, (8.0, 14.2), (9.0, 13.9), (8.0, 15.6), 0.6, "fang")                          # 아래 송곳니
    # 독니 날: 목에서 솟아 +X 로 휨
    y0, y1 = 17.5, 41.5

    def fang(X, Y, Z):
        t = (Y - y0) / (y1 - y0)
        tc = np.clip(t, 0, 1)
        off = -0.6 + 3.0 * tc ** 2
        hw = 2.4 * (1 - tc) ** 0.8 + 0.6
        hz = 0.45 + 0.45 * np.clip(hw - np.abs(X - off), 0, 2)
        return (t >= 0) & (t <= 1) & (np.abs(X - off) <= hw) & (np.abs(Z) <= hz), off, hw
    w.fill(lambda X, Y, Z: fang(X, Y, Z)[0], "bone")
    w.fill(lambda X, Y, Z: fang(X, Y, Z)[0] & (np.abs(X - fang(X, Y, Z)[1]) <= fang(X, Y, Z)[2] - 1.0), "fang")
    # 독 홈 (짧은 빛 줄 하나)
    w.fill(lambda X, Y, Z: fang(X, Y, Z)[0] & (Y >= 21) & (Y <= 31) & (np.abs(X - fang(X, Y, Z)[1]) <= 0.5), "venom")
    return w


def storm_dagger():
    """번개 단검: 날 자체가 크게 꺾인 번개, 손잡이는 구리 코일 고리, 폼멜은 녹청 낀 피뢰침 공."""
    m = {
        "rim": Mat(["#6a4206", "#9a6a10", "#c89020", "#e8b838"], "metal", seed=31),
        "bolt": Mat(["#d0a020", "#f0d040", "#fff080", "#fffbd0"], "metal", seed=32),
        "spark": Mat(["#fff080", "#fffbd0", "#ffffff", "#ffffff"], "sparkle", glow=True, seed=33),
        "copper": Mat(["#6a3018", "#b0582c", "#e08050", "#ffb080"], "metal", seed=34),
        "patina": Mat(["#2a6a5a", "#3a9a80", "#5ac0a0", "#90e0c8"], "stone", seed=35),
        "core": Mat(["#1a1a22", "#2a2a34", "#3a3a46", "#4a4a58"], "grip", seed=36),
    }
    w = Weapon(m, grip_y=7.5, kind="dagger", seed=104)
    w.cyl(2.5, 12.5, 1.2, "core")
    rings(w, (3.5, 5.5, 7.5, 9.5, 11.5), 1.75, "copper")               # 구리 코일
    w.ball(0, 1.7, 0, 2.2, 1.8, 2.2, "copper")                          # 피뢰침 공
    w.cyl(1.2, 2.2, 2.5, "patina")
    # 가드: 구리 막대, 양 끝 녹청
    w.box(-4, 4, 12.5, 14.5, -1.5, 1.5, "copper")
    for s in (-1, 1):
        w.box(min(s * 3.5, s * 5.5), max(s * 3.5, s * 5.5), 12, 15, -1.8, 1.8, "patina")

    # 번개 모양 날: 오른쪽으로 기운 세 마디, 마디마다 왼쪽으로 크게 꺾임
    segs = [(14.5, 24.5, -1.5, 2.2, 2.6, 2.3), (23.5, 33.5, -2.2, 1.6, 2.4, 2.0), (32.5, 43.0, -1.6, 1.6, 2.2, 0.5)]

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
    w.prism(lambda X, Y: bolt(X, Y, 1.9) & (Y < 39), 1.5, "spark")        # 가운데 전기 줄 (작은 빛)
    return w


# ─────────────────────────── 서리 (frost) ───────────────────────────

def frost_dagger():
    """고드름 단검: 마름모 단면의 긴 고드름 날, 크기가 다른 얼음 조각 가드, 서리 낀 손잡이, 아래로 뾰족한 얼음."""
    m = {
        "ice": Mat(["#1e4a8a", "#3a7ac0", "#7ab8e8", "#c8ecff"], "crystal", seed=41),
        "ice_hi": Mat(["#4a8ac8", "#80bce8", "#c0e4fc", "#ffffff"], "crystal", seed=42),
        "core": Mat(["#40a0ff", "#80d0ff", "#c0f0ff", "#ffffff"], "pulse", glow=True, seed=43),
        "wrap": Mat(["#28384c", "#3e5470", "#5a7494", "#7c98b8"], "grip", seed=44),
        "rime": Mat(["#b8d4ea", "#d8ecf8", "#f0f8ff", "#ffffff"], "stone", seed=45),
    }
    w = Weapon(m, grip_y=8, kind="dagger", seed=105)
    w.cyl(3, 13.5, 1.3, "wrap")
    for (x, y, z) in ((1.0, 5, 0.9), (-1.0, 9, -0.9), (0.8, 12, 1.0)):
        w.ball(x, y, z, 1.0, 1.0, 1.0, "rime")                       # 서리 덩어리
    # 아래로 뾰족한 얼음 폼멜
    w.fill(lambda X, Y, Z: (Y >= 0) & (Y <= 3.2) & (np.abs(X) + np.abs(Z) <= 0.4 + Y * 0.7), "ice")
    # 가드: 얼음 덩어리 + 크기가 다른 비스듬한 얼음 조각 (오른쪽이 길다), 아래로 늘어진 고드름
    w.ball(0, 14.5, 0, 2.8, 1.6, 2.2, "ice")
    w.prism(poly([(1.0, 13.5), (2.0, 16.0), (7.5, 21.5), (5.0, 14.0)]), 1.2, "ice_hi")
    w.prism(poly([(-1.0, 13.5), (-2.0, 15.6), (-5.5, 18.5), (-4.0, 13.5)]), 1.0, "ice_hi")
    w.prism(poly([(-4.0, 13.5), (-2.2, 13.5), (-3.4, 10.0)]), 0.6, "ice")
    # 고드름 날 (마름모 단면)
    y0, y1 = 15, 44

    def icicle(X, Y, Z, inner=0.0):
        t = (Y - y0) / (y1 - y0)
        hw = 3.0 * (1 - np.clip(t, 0, 1)) ** 0.9 + 0.2 - inner
        hz = 0.4 + 0.75 * (hw - np.abs(X))
        return (t >= 0) & (t <= 1) & (np.abs(X) <= hw) & (np.abs(Z) <= hz)
    w.fill(lambda X, Y, Z: icicle(X, Y, Z), "ice_hi")
    w.fill(lambda X, Y, Z: icicle(X, Y, Z, 1.0), "ice")
    # 빛나는 심지: 마디로 끊긴 룬
    w.fill(lambda X, Y, Z: (np.abs(X) <= 0.5) & (Y >= 17) & (Y <= 34) & (((Y - 17) % 5) < 3.2) & icicle(X, Y, Z), "core")
    return w


def frost_greatsword():
    """빙하 대검: 금속 없이 얼음으로 자란 날. 밑동에서 큰 얼음 가시가 비스듬히 터져 나오고, 끝은 비스듬히 잘린 결정, 깊은 청색 심과 룬."""
    m = {
        "ice": Mat(["#2a5a9a", "#4a88c8", "#86c0ec", "#d0f0ff"], "crystal", seed=51),
        "spike": Mat(["#6aa8de", "#9cd0f4", "#d0eeff", "#ffffff"], "crystal", seed=52),
        "deep": Mat(["#08143c", "#10265e", "#1c3a82", "#2c52a8"], "crystal", seed=53),
        "rune": Mat(["#20a0ff", "#60d0ff", "#b0f0ff", "#ffffff"], "pulse", glow=True, seed=54),
        "fur": Mat(["#8090a0", "#b0c0cc", "#d8e2ea", "#f4f8fc"], "cloth", seed=55),
        "strap": Mat(["#1a2a40", "#2a4060", "#3a5880", "#5070a0"], "grip", seed=56),
    }
    w = Weapon(m, grip_y=11.5, kind="greatsword", seed=106)
    # 네모 얼음 폼멜 (아래로 뾰족)
    w.fill(lambda X, Y, Z: (Y >= 0) & (Y <= 5) & (np.maximum(np.abs(X), np.abs(Z)) <= np.minimum(2.6, 0.5 + Y * 0.9)), "spike")
    w.cyl(5, 19.5, 1.7, "fur")
    rings(w, (8, 12.5, 17), 1.95, "strap")
    # 빙하 덩어리 가드: 높이 다른 결정 기둥들
    for (x, h, r) in ((-6.5, 23.5, 1.8), (-3.5, 25.5, 2.2), (0, 23.5, 2.8), (3.5, 25, 2.0), (6.5, 22.5, 1.6)):
        w.fill(lambda X, Y, Z, x=x, h=h, r=r: (Y >= 19) & (Y <= h) &
               (np.abs(X - x) + np.abs(Z) * 0.8 <= r * np.minimum(1, (h - Y) / 1.8 + 0.35)), "spike")
    y0, y1 = 22, 71.5
    hw = lambda Y: 4.4 - 1.0 * tnorm(Y, y0, y1)
    # 날 몸통 + 비스듬히 잘린 결정 끝
    body = lambda X, Y: (Y >= y0) & (np.abs(X) <= hw(Y)) & (Y <= 71.5 - 1.7 * (X + 3.4))
    w.prism(body, 1.0, "ice")
    w.prism(lambda X, Y: body(X, Y) & (np.abs(X) <= hw(Y) - 1.2), 1.5, "ice")
    # 밑동에서 터져 나온 큰 얼음 가시: (쪽, 시작 Y, 길이)
    for (s, yb, L) in ((-1, 23, 11.0), (1, 25, 9.0), (-1, 33, 6.5), (1, 38, 5.0)):
        e = s * (hw(np.array(yb)) - 1.5)
        w.prism(poly([(float(e), yb), (float(e + s * L * 0.85), yb + L * 1.1), (float(e), yb + L * 0.8)]),
                lambda X, Y: 1.5, "spike")
    w.prism(lambda X, Y: (Y >= y0) & (Y <= 60) & (np.abs(X) <= 1.0), 2.0, "deep")
    for yc in (29, 39, 49):
        w.fill(lambda X, Y, Z, yc=yc: (np.abs(X) + np.abs(Y - yc) <= 1.6) & (np.abs(Z) <= 2.5), "rune")
    return w


# ─────────────────────────── 화염 (flame) ───────────────────────────

def ember_greatsword():
    """화염 대검: 계단처럼 물결치는 플람베르주 날, 검게 그을린 강철 사이로 녹은 심이 빛나고, 가드는 불꽃처럼 말려 올라감."""
    m = {
        "char": Mat(["#141010", "#241a18", "#3a2a24", "#4e3a30"], "metal", seed=61),
        "hot": Mat(["#7a2008", "#c0480c", "#e87a20", "#ffb850"], "metal", seed=62),
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
    rings(w, (5,), 1.9, "iron")
    # 가드: 가운데 덩어리 + 위로 말려 올라가는 불꽃 갈퀴
    w.box(-3.5, 3.5, 20, 24, -2, 2, "iron")
    for s in (-1, 1):
        w.tube([(s * 3, 22, 0), (s * 7, 21.5, 0), (s * 9.5, 24, 0), (s * 9.5, 27, 0), (s * 8, 28.5, 0)],
               lambda t: 1.6 - 0.9 * t, "iron")
        w.tube([(s * 6.5, 22.5, 0), (s * 6.5, 25.5, 0), (s * 5.2, 27, 0)], lambda t: 1.0 - 0.4 * t, "char")
    y0, y1 = 24, 71.5

    def off(Y):          # 정수 칸으로 꺾이는 물결 (요소 수를 줄이고 픽셀이 깔끔)
        return np.round(np.sin((Y - y0) / 14.0 * 2 * math.pi))

    yt = 63.5            # 여기부터 끝까지는 달군 쇠 한 덩어리 (뾰족한 끝)

    def hw(Y):
        return np.where(Y < 46, 4.5, 3.5)

    tip = lambda X, Y: (Y >= yt) & (Y <= y1) & (np.abs(X - off(Y)) <= 3.6 * (y1 - Y) / (y1 - yt) + 0.4)
    inb = lambda X, Y: (Y >= y0) & (Y < yt) & (np.abs(X - off(Y)) <= hw(Y))
    w.prism(lambda X, Y: inb(X, Y) | tip(X, Y), 0.5, "hot")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X - off(Y)) <= hw(Y) - 1), 1.5, "char")
    w.prism(lambda X, Y: (Y >= y0 + 1) & (Y <= 60) & (np.abs(X - off(Y)) <= 1.0), 1.9, "magma")   # 녹은 심
    return w


# ─────────────────────────── 공허 (void) ───────────────────────────

def shadow_dagger():
    """그림자 쿠나이: 가드 없는 넓은 잎 날(검은 몸통, 보랏빛 날 테두리), 천을 감은 손잡이, 고리 폼멜에서 흩날리는 끈."""
    m = {
        "black": Mat(["#0a0810", "#16121c", "#221c2a", "#30283a"], "metal", seed=71),
        "ridge": Mat(["#1c1626", "#2c2438", "#40344e", "#564668"], "metal", seed=72),
        "glow": Mat(["#6a20c0", "#9a4af0", "#c890ff", "#f0e0ff"], "flow", glow=True, seed=73),
        "cloth": Mat(["#120e18", "#221a2c", "#342840", "#463656"], "grip", seed=74),
        "ribbon": Mat(["#4a1478", "#6a22a0", "#8a3ac8", "#aa5ae0"], "cloth", seed=75),
        "steel": Mat(["#2a2632", "#423c4c", "#5c5468", "#787086"], "metal", seed=76),
    }
    w = Weapon(m, grip_y=12.5, kind="dagger", seed=108)
    # 고리 폼멜
    w.fill(lambda X, Y, Z: (np.abs(np.hypot(X, Y - 4.4) - 2.7) <= 1.0) & (np.abs(Z) <= 0.9), "steel")
    # 끈: 고리에서 옆으로 흩날림
    w.tube([(2.2, 2.6, 0.5), (4.5, 1.2, 0.5), (7.0, 2.2, 0.5), (9.5, 1.0, 0.5)], lambda t: 1.0 - 0.3 * t, "ribbon")
    w.tube([(1.0, 2.0, -0.5), (2.5, 0.6, -0.5), (5.0, 0.6, -0.5)], 0.7, "ribbon")
    w.box(-1.5, 1.5, 7.5, 8.5, -1.5, 1.5, "steel")
    w.cyl(8, 18, 1.25, "cloth")
    rings(w, (10, 13, 16), 1.45, "ribbon")
    w.box(-1.5, 1.5, 18, 19.5, -1.5, 1.5, "steel")
    # 넓은 잎 날 (마름모 단면)
    y0, y1 = 19.5, 42

    def hw(Y):
        t = tnorm(Y, y0, y1)
        return 1.2 + 3.0 * np.sin(np.minimum(t / 0.38, 1) * math.pi / 2) * np.where(t > 0.38, ((1 - t) / 0.62) ** 0.9, 1)

    hz = lambda X, Y: 0.5 + 0.45 * np.clip(hw(Y) - np.abs(X), 0, 3)
    leaf = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(leaf, hz, "glow")
    w.prism(lambda X, Y: leaf(X, Y) & (np.abs(X) <= hw(Y) - 1.0), hz, "black")
    w.prism(lambda X, Y: leaf(X, Y) & (np.abs(X) <= 0.5) & (Y < y1 - 2), hz, "ridge")
    return w


def ender_dagger():
    """엔더 단검: 흑요석 날이 세 토막으로 떨어져 옆으로 밀린 채 떠 있고(순간이동 중), 엔드석 가드 가운데 엔더의 눈."""
    m = {
        "obsid": Mat(["#0e0818", "#1e1030", "#30184a", "#482a66"], "crystal", seed=81),
        "rim": Mat(["#6a4a9a", "#9a6ad0", "#c49af0", "#ecdcff"], "metal", seed=82),
        "portal": Mat(["#6a10a0", "#b030e0", "#e070ff", "#ffd0ff"], "sparkle", glow=True, seed=83),
        "endstone": Mat(["#a8a670", "#cccc90", "#e0e0aa", "#f4f4c8"], "stone", seed=84),
        "purpur": Mat(["#6a4a6a", "#946a94", "#b48cb4", "#d0aed0"], "stone", seed=85),
        "eye": Mat(["#0a4a3a", "#1a8a6a", "#40c8a0", "#a0ffe0"], "gem", glow=True, seed=86),
        "pupil": Mat(["#020806", "#061410", "#0a201a", "#102a22"], "flat", seed=87),
    }
    w = Weapon(m, grip_y=7, kind="dagger", seed=109)
    w.box(-2, 2, 0, 3, -2, 2, "endstone")                          # 엔드석 폼멜
    w.box(-1.5, 1.5, 3, 11.5, -1.5, 1.5, "purpur")                  # 퍼퍼 기둥 손잡이
    w.box(-1.8, 1.8, 7, 8, -1.8, 1.8, "endstone")
    # 가드: 엔드석 틀 + 양옆 흑요석 뿔 + 엔더의 눈
    w.box(-5, 5, 11.5, 15, -1.5, 1.5, "endstone")
    for s in (-1, 1):
        w.tube([(s * 5, 13, 0), (s * 7, 15.5, 0), (s * 7.2, 19, 0)], lambda t: 1.3 - 0.6 * t, "obsid")
    w.ball(0, 13.5, 0, 3.0, 3.0, 2.5, "eye")
    w.box(-0.5, 0.5, 11.5, 15.5, -2.8, 2.8, "pupil")

    # 떠 있는 세 토막: (아래, 위, 옆으로 밀린 정도)
    y0, y1 = 16.5, 43
    hw = lambda Y: 3.0 * (1 - tnorm(Y, y0, y1)) ** 0.6 + 0.3
    for (a, b, dx) in ((16.5, 24.5, 0.0), (26.5, 34, 1.5), (36, 43, -1.0)):
        cut = lambda X, Y, a=a, b=b, dx=dx: (Y >= a + 0.35 * (X - dx)) & (Y <= b + 0.35 * (X - dx)) & (Y >= y0) & (Y <= y1)
        w.prism(lambda X, Y, dx=dx, cut=cut: cut(X, Y) & (np.abs(X - dx) <= hw(Y)), 0.5, "rim")
        w.prism(lambda X, Y, dx=dx, cut=cut: cut(X, Y) & (np.abs(X - dx) <= hw(Y) - 1), 1.0, "obsid")
    # 떠다니는 작은 포털 조각
    for (x, y, z) in ((5.5, 29.5, 0.5), (-4.5, 38.5, -0.5), (4, 43.5, 0.5), (-5, 24, 0.5)):
        w.box(x - 0.5, x + 0.5, y - 0.5, y + 0.5, z - 0.5, z + 0.5, "portal")
    return w


# ─────────────────────────── 보스 (boss) ───────────────────────────

def frostlord_greatsword():
    """서리 군주의 대검: 날보다 넓은 은빛 왕관 가드(관 끝마다 얼음 보석, 아래로 고드름), 위로 갈수록 넓어지는 한밤 강철 날과 흐르는 서리 심지."""
    m = {
        "night": Mat(["#0a1030", "#16204e", "#24346e", "#344a90"], "metal", seed=91),
        "silver": Mat(["#6a7a94", "#a0b0c8", "#d0dcec", "#ffffff"], "metal", seed=92),
        "frost": Mat(["#1a5ad0", "#40a0ff", "#a0e0ff", "#ffffff"], "flow", glow=True, seed=93),
        "icegem": Mat(["#2080e0", "#60c0ff", "#c0f0ff", "#ffffff"], "sparkle", glow=True, seed=94),
        "ice": Mat(["#4a88c0", "#80bce8", "#c0e4fc", "#ffffff"], "crystal", seed=95),
        "grip": Mat(["#0a0e20", "#141c36", "#202c50", "#2c3c6a"], "grip", seed=96),
    }
    w = Weapon(m, grip_y=13.5, kind="greatsword", seed=110)
    # 폼멜: 은 받침 위 팔면체 얼음 보석
    w.fill(lambda X, Y, Z: np.abs(X) / 2.8 + np.abs(Y - 3.6) / 3.6 + np.abs(Z) / 2.8 <= 1, "icegem")
    w.cyl(5.5, 7, 2.0, "silver")
    w.cyl(7, 20.5, 1.6, "grip")
    rings(w, (10, 13.5, 17), 1.85, "silver")
    # 왕관 가드: 넓은 띠 + 바깥으로 네 개의 관 + 가운데 얼어붙은 심장 보석
    w.box(-12, 12, 20.5, 25, -2, 2, "silver")
    w.box(-13, 13, 20, 21, -2.4, 2.4, "silver")
    for (x, h, b) in ((-11, 32, 1.8), (-7, 36, 2.0), (7, 36, 2.0), (11, 32, 1.8)):
        w.fill(lambda X, Y, Z, x=x, h=h, b=b: (Y >= 24.5) & (Y <= h) & (np.abs(X - x) <= b * (h - Y) / (h - 24.5) + 0.3) & (np.abs(Z) <= 1.5), "silver")
        w.ball(x, h, 0, 1.1, 1.1, 1.2, "icegem")
    # 띠 아래로 늘어진 고드름
    for (x, L) in ((-11, 4), (-7.5, 6.5), (7.5, 5.5), (11, 3.5)):
        tri(w, (x - 1.2, 20.5), (x + 1.2, 20.5), (x, 20.5 - L), 1.0, "ice")
    w.gem(0, 22.8, 2.2, "icegem", frame="silver", depth=2.8)
    # 날: 넓고 위로 갈수록 넓어졌다가 뾰족
    y0, y1 = 25, 72

    def hw(Y):
        t = tnorm(Y, y0, y1)
        base = 4.2 + 2.0 * np.sin(t * math.pi * 0.8)
        return np.where(t > 0.8, base * ((1 - t) / 0.2) ** 0.8 + 0.3, base)

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, 0.5, "silver")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.2), 1.5, "night")
    w.prism(lambda X, Y: (Y >= y0 + 2) & (Y <= y1 - 8) & (np.abs(X) <= 1.0), 2.0, "frost")
    w.set_aura(["#1a2a8a", "#2a6ae0", "#5ad0ff", "#e8ffff"], "frost", size=1.1, focus=["frost", "icegem"])
    return w


def shadow_twinblade():
    """암살자의 쌍검: 손잡이 하나 양끝에 서로 반대로 휜 넓은 초승달 날 (180도 대칭). 바깥 날은 보랏빛, 안쪽 등은 톱니, 가운데 보석 고리."""
    m = {
        "blade": Mat(["#221830", "#362848", "#4e3c66", "#6a5488"], "metal", seed=121),
        "edge": Mat(["#8a3af0", "#b070ff", "#d8b0ff", "#ffffff"], "flow", glow=True, seed=122),
        "steel": Mat(["#3a3248", "#5a4e6e", "#7a6c92", "#a094b8"], "metal", seed=123),
        "wrap": Mat(["#201828", "#342840", "#4a3a5c", "#62507a"], "grip", seed=124),
        "gem": Mat(["#5a0aa0", "#a030f0", "#e090ff", "#ffffff"], "pulse", glow=True, seed=125),
    }
    yc = 36
    w = Weapon(m, grip_y=yc, kind="sword", seed=111)
    # 위쪽 절반만 만들고 180도 돌려 복사
    w.cyl(yc, yc + 7.5, 1.5, "wrap")
    w.box(-2, 2, yc + 7.5, yc + 9.5, -1.8, 1.8, "steel")
    # 발톱 가드 (날 등 쪽으로 굽음)
    w.tube([(1.5, yc + 8.5, 0), (4.5, yc + 9, 0), (6, yc + 6.5, 0)], lambda t: 1.2 - 0.5 * t, "steel")
    y0, y1 = yc + 9.5, 71.5
    ctr = lambda Y: 7.0 * tnorm(Y, y0, y1) ** 2

    def hw(Y):
        t = tnorm(Y, y0, y1)
        return 2.6 * (1 - t) ** 0.7 + 0.5 + 2.3 * np.sin(t * math.pi) ** 0.8 * (1 - t) ** 0.3

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X - ctr(Y)) <= hw(Y))
    w.prism(inb, 1.0, "blade")
    w.prism(lambda X, Y: inb(X, Y) & (X - ctr(Y) <= -hw(Y) + 1.4), 0.5, "edge")      # 바깥(볼록한 쪽) 날
    # 안쪽 등 톱니
    w.prism(lambda X, Y: (Y >= y0 + 2) & (Y <= y0 + 15) & (X - ctr(Y) > hw(Y) - 0.2) &
            (X - ctr(Y) <= hw(Y) + 1.8 * (((Y - y0) % 4) / 4)), 1.0, "steel")
    rot180(w, yc)
    # 가운데 고리 + 보석
    disc(w, 0, yc, 3.6, 1.5, "steel")
    w.gem(0, yc, 2.0, "gem", depth=2.4)
    w.set_aura(["#2a0a5a", "#6a1ad0", "#b060ff", "#f0d8ff"], "void", size=1.0, focus=["edge", "gem"])
    return w


def star_greatsword():
    """별의 대검: 별밤처럼 반짝이는 남색 날 + 금 테두리, 끝은 네 갈래 별빛, 가드는 가운데가 솟은 커다란 금빛 오각 별, 폼멜은 운석."""
    m = {
        "night": Mat(["#0a0a2a", "#16164a", "#262a70", "#3a4098"], "sparkle", glow=True, seed=131),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c050", "#fff4b0"], "metal", seed=132),
        "white": Mat(["#c8c8f0", "#e8e8ff", "#ffffff", "#ffffff"], "pulse", glow=True, seed=133),
        "rock": Mat(["#1a1820", "#2e2a34", "#46404c", "#5e5664"], "stone", seed=134),
        "wrap": Mat(["#10143a", "#1c2458", "#2a3478", "#3a4698"], "grip", seed=135),
        "silver": Mat(["#6a6a8a", "#a0a0c0", "#d0d0ea", "#ffffff"], "metal", seed=136),
    }
    w = Weapon(m, grip_y=11.5, kind="greatsword", seed=112)
    # 폼멜: 운석 덩어리 (빛나는 틈)
    w.ball(0, 2.8, 0, 2.9, 2.8, 2.7, "rock")
    w.ball(0.9, 3.3, 1.3, 1.1, 1.0, 1.6, "white")
    w.cyl(5.5, 18.5, 1.6, "wrap")
    rings(w, (11.5,), 1.85, "gold")
    # 오각 별 가드 (가운데가 두껍게 솟음)
    sc, R, r = 23.5, 12.5, 5.0
    pts = [((R if k % 2 == 0 else r) * math.cos(math.pi / 2 + k * math.pi / 5),
            sc + (R if k % 2 == 0 else r) * math.sin(math.pi / 2 + k * math.pi / 5)) for k in range(10)]
    w.prism(poly(pts), 1.2, "gold")
    w.gem(0, sc, 2.5, "white", frame="silver", depth=2.8)
    # 날: 금 테두리, 별밤 몸통
    y0, ys = 30, 62.5
    hw = lambda Y: np.where(Y < 47, 4.5, 3.5)
    inb = lambda X, Y: (Y >= y0) & (Y <= ys) & (np.abs(X) <= hw(Y))
    w.prism(inb, 0.5, "gold")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.0), 1.5, "night")
    # 끝: 네 갈래 별빛 (세로가 길다)
    star4 = lambda X, Y, a, b: (np.abs(X) / a) ** 0.6 + (np.abs(Y - ys) / b) ** 0.6 <= 1
    w.prism(lambda X, Y: star4(X, Y, 8.5, 10.0), 1.0, "gold")
    w.prism(lambda X, Y: star4(X, Y, 6.5, 8.0), 1.5, "white")
    w.set_aura(["#2a1a7a", "#6a5ae0", "#ffd86a", "#fffbe0"], "holy", size=1.0, focus=["white", "night"])
    return w


def prism_greatsword():
    """프리즘 대검: 아래를 향한 삼각 프리즘 가드에서 무지개 빛줄기가 솟아 분홍·하늘 두 장의 수정 판 사이를 지나간다."""
    m = {
        "rose": Mat(["#9a5ab8", "#c084e0", "#e4b8f8", "#fff0ff"], "crystal", seed=141),
        "sky": Mat(["#4a88c8", "#78b8ec", "#b8e4ff", "#f0ffff"], "crystal", seed=142),
        "facet": Mat(["#e0e8ff", "#f0f4ff", "#ffffff", "#ffffff"], "crystal", seed=149),
        "beam": Mat(["#ff0000", "#00ff00", "#0000ff", "#ffffff"], "rainbow", glow=True, seed=143),
        "gold": Mat(["#7a5a18", "#c09030", "#f0d060", "#fff8c0"], "metal", seed=144),
        "white": Mat(["#a8a8b8", "#d0d0dc", "#ececf4", "#ffffff"], "grip", seed=145),
        "pink": Mat(["#c04080", "#f070b0", "#ffb0d8", "#ffffff"], "gem", glow=True, seed=146),
        "cyan": Mat(["#2090c0", "#40c8f0", "#a0f0ff", "#ffffff"], "gem", glow=True, seed=147),
        "yellow": Mat(["#c09010", "#f0c830", "#fff080", "#ffffff"], "gem", glow=True, seed=148),
    }
    w = Weapon(m, grip_y=10.5, kind="greatsword", seed=113)
    w.gem(0, 2.6, 1.9, "beam", frame="gold", depth=2.0)               # 무지개 폼멜
    w.cyl(4.5, 17, 1.6, "white")
    rings(w, (4.5, 10.5, 16.5), 1.9, "gold", h=0.9)
    # 삼각 프리즘 가드 (꼭짓점이 아래)
    w.prism(poly([(-10.5, 28), (10.5, 28), (0, 16)]), 2.0, "gold")
    w.prism(poly([(-8.2, 27), (8.2, 27), (0, 18.5)]), 2.5, "facet")
    w.prism(poly([(-2.2, 27), (2.2, 27), (0, 21.5)]), 3.0, "beam")
    # 날: 왼쪽 분홍, 오른쪽 하늘빛 수정 판, 가운데 무지개 빛줄기
    y0, y1 = 28, 72

    def hw(Y):
        t = tnorm(Y, y0, y1)
        return np.where(t > 0.76, 6.0 * ((1 - t) / 0.24) ** 0.75 + 0.3, 6.0 - 0.2 * t)

    hz = lambda X, Y: 0.5 + 0.5 * np.clip(hw(Y) - np.abs(X), 0, 2)
    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, hz, "facet")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.2) & (X < 0), 1.5, "rose")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.2) & (X > 0), 1.5, "sky")
    slot = lambda X, Y: (Y >= y0) & (Y <= 63) & (np.abs(X) <= 2.0)
    w.clear(lambda X, Y, Z: slot(X, Y))
    w.prism(slot, 1.0, "beam")
    # 가드 양 끝에서 비스듬히 자란 수정
    for s_, mt in ((-1, "rose"), (1, "sky")):
        w.prism(poly([(s_ * 7.5, 27.5), (s_ * 11.5, 26.5), (s_ * 12.5, 34.5)]), 1.5, mt)
    # 떠 있는 작은 수정 조각
    for (x, y, mt) in ((-10.5, 40, "pink"), (11, 47, "cyan"), (-9.5, 56, "yellow")):
        w.fill(lambda X, Y, Z, x=x, y=y: (np.abs(X - x) / 1.8 + np.abs(Y - y) / 3.0 + np.abs(Z) / 1.5) <= 1, mt)
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
