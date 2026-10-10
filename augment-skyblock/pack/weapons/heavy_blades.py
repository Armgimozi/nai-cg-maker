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


def path2d(pts, r):
    """XY 꺾은선(굵기 r)의 마스크. 깔끔한 곧은 선."""
    def m(X, Y):
        out = np.zeros(np.shape(X), bool)
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            t = np.clip(((X - ax) * dx + (Y - ay) * dy) / (dx * dx + dy * dy), 0, 1)
            out |= np.hypot(X - ax - t * dx, Y - ay - t * dy) <= r
        return out
    return m


def disc(w, cx, cy, r, hz, mat, cz=0.0):
    """앞을 보는 원판 (XY 평면)."""
    return w.fill(lambda X, Y, Z: (np.hypot(X - cx, Y - cy) <= r) & (np.abs(Z - cz) <= hz), mat)


def octa(w, cx, cy, cz, a, b, c, mat):
    """팔면체 (각진 보석, 수정 조각)."""
    return w.fill(lambda X, Y, Z: np.abs(X - cx) / a + np.abs(Y - cy) / b + np.abs(Z - cz) / c <= 1, mat)


def groove(w, mask, mat, keep=0.5):
    """이미 있는 몸통에 홈을 파고(|Z|>keep 비움) 바닥을 mat 으로: 표면보다 한 칸 들어간 룬/홈."""
    m = np.asarray(mask(w._X, w._Y), bool) & (w.grid > 0)
    w.grid[m & (np.abs(w._Z) > keep)] = 0
    w.grid[m & (np.abs(w._Z) <= keep)] = w._id(mat)
    return w


def paint(w, mask, mat):
    """이미 있는 복셀만 색을 바꾼다 (모양은 그대로)."""
    m = np.asarray(mask(w._X, w._Y, w._Z), bool) & (w.grid > 0)
    w.grid[m] = w._id(mat)
    return w


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
    """클립 포인트 사냥칼: 외날, 곧게 깎인 클립, 날 쪽 손가락 걸이, 새머리처럼 굽은 나무 손잡이(가운데 쇠 탱, 박힌 놋쇠 리벳)."""
    m = {
        "steel": Mat(["#3e444c", "#596069", "#757d87", "#929aa4"], "metal", seed=1),
        "edge": Mat(["#9aa2ac", "#bac2ca", "#d8dee4", "#f2f6fa"], "metal", seed=2),
        "spine": Mat(["#23272d", "#33383f", "#464c54", "#5a616a"], "metal", seed=3),
        "wood": Mat(["#3e2412", "#64401f", "#8a5a30", "#ac7844"], "wood", seed=4),
        "brass": Mat(["#6a4a14", "#a07a2a", "#d0a848", "#f0d080"], "metal", seed=5),
    }
    w = Weapon(m, grip_y=7.5, kind="dagger", seed=101)
    # 손잡이 옆모습: 등 쪽은 곧고, 끝이 날 쪽(+X)으로 크게 굽은 새머리
    handle = poly([(-2.0, 14.0), (2.0, 14.0), (2.0, 7.5), (2.6, 4.6), (4.0, 2.8), (6.0, 2.0), (6.0, 0.0),
                   (1.0, 0.0), (-2.0, 1.0)])
    w.prism(handle, 1.5, "wood")
    w.prism(lambda X, Y: handle(X, Y) & (X <= 2.0) & (Y >= 6.0), 0.5, "spine")   # 나무 사이로 보이는 쇠 탱
    for yy in (4.0, 10.0):                              # 표면에 박힌 리벳 (튀어나오지 않음)
        w.fill(lambda X, Y, Z, yy=yy: (np.abs(X) <= 1.0) & (np.abs(Y - yy) <= 1.0) & (np.abs(Z) > 1.0) & (np.abs(Z) <= 1.5), "brass")
    # 가드: 등 쪽은 짧게, 날 쪽은 아래로 굽은 손가락 걸이
    w.box(-3.0, 3.0, 14.0, 16.0, -1.5, 1.5, "spine")
    w.prism(poly([(2.0, 16.0), (5.0, 16.0), (5.0, 12.0), (4.0, 11.0), (4.0, 14.0), (2.0, 14.0)]), 1.0, "spine")
    # 날: 등은 곧다가 클립에서 곧은 사선으로 끝까지, 날은 불룩한 배
    y0, yc, y1 = 16.0, 30.0, 38.0
    xs = lambda Y: np.where(Y < yc, -2.5, -2.5 + 4.0 * (Y - yc) / (y1 - yc))          # 2:1 곧은 클립
    xe = lambda Y: np.interp(Y, [16, 18, 23, 29, 33, 36, 38], [2.6, 3.6, 4.2, 4.6, 4.0, 2.8, 1.5])
    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (X >= xs(Y)) & (X <= xe(Y))
    w.prism(inb, 1.5, "steel")
    w.prism(lambda X, Y: inb(X, Y) & (Y < yc) & (X <= xs(Y) + 0.5), 1.5, "spine")    # 등 (몸통과 같은 두께)
    edge = lambda X, Y: inb(X, Y) & (X >= xe(Y) - 1.7)
    clip = lambda X, Y: inb(X, Y) & (Y >= yc) & (X <= xs(Y) + 1.2)
    groove(w, lambda X, Y: edge(X, Y) | clip(X, Y), "edge")                           # 얇게 간 날, 클립
    return w


def iron_greatsword():
    """쯔바이헨더: 긴 두 손 손잡이, 가죽 감은 리카소와 받이 돌기(파리어하켄), 곧은 막대 가드, 진한 홈, 곧게 뾰족한 끝."""
    m = {
        "iron": Mat(["#3a3f45", "#50565d", "#686f77", "#828991"], "metal", seed=11),
        "edge": Mat(["#6a7179", "#848b93", "#a0a7ae", "#bcc2c8"], "metal", seed=12),
        "dark": Mat(["#16181c", "#24282d", "#34393f", "#474d54"], "metal", seed=13),
        "leather": Mat(["#2a1810", "#4a2c1a", "#6a4228", "#8a5a38"], "grip", seed=14),
    }
    w = Weapon(m, grip_y=12, kind="greatsword", seed=102)
    disc(w, 0, 3.0, 3.4, 1.5, "dark")                       # 바퀴 폼멜
    disc(w, 0, 3.0, 1.5, 2.5, "iron")                       # 가운데 못
    w.cyl(5.5, 19, 1.6, "leather")                          # 두 손 손잡이
    w.cyl(5.5, 6.4, 2.0, "dark")
    # 가드: 곧은 막대 + 끝 덩어리 + 가운데 받침
    w.box(-12, 12, 19, 21.5, -1.5, 1.5, "dark")
    for s in (-1, 1):
        w.box(min(s * 10, s * 13), max(s * 10, s * 13), 18.5, 22, -2, 2, "dark")
    w.box(-3, 3, 18.5, 22.5, -2, 2, "dark")
    # 리카소: 좁은 쇠 + 아래쪽은 가죽으로 감쌈
    w.box(-2, 2, 22, 33, -1.5, 1.5, "iron")
    w.box(-2.5, 2.5, 22, 28, -2.5, 2.5, "leather")
    w.box(-2.5, 2.5, 28, 29, -2.5, 2.5, "dark")
    # 받이 돌기: 리카소 끝에서 옆으로, 끝이 아래로 숙임
    for s in (-1, 1):
        w.prism(poly([(s * 1.5, 31.0), (s * 1.5, 34.0), (s * 5.5, 32.0), (s * 7.5, 29.5), (s * 5.0, 30.5)]), 1.0, "dark")
    # 날: 넓게 시작해 조금씩 좁아지다가 곧은 사선으로 뾰족
    y0, yp, y1 = 33.0, 59.0, 72.0
    hw = lambda Y: np.where(Y < yp, 4.2 - 0.7 * tnorm(Y, y0, yp), 3.5 * np.clip((y1 - Y) / (y1 - yp), 0, 1) + 0.3)
    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, 1.5, "iron")
    groove(w, lambda X, Y: inb(X, Y) & (np.abs(X) >= hw(Y) - 1.5), "edge")            # 얇게 간 날
    groove(w, lambda X, Y: (np.abs(X) <= 1) & (Y >= 34) & (Y <= 56), "dark")         # 깊은 홈
    return w


# ─────────────────────────── 섬 (island) ───────────────────────────

def venom_dagger():
    """독사의 단검: 손잡이를 감고 올라온 뱀이 가드 옆에서 쐐기 모양 머리를 비스듬히 쳐들고, 상아빛 독니 날이 휘어 솟는다. 독 홈 한 줄만 빛난다."""
    m = {
        "fang": Mat(["#a89a74", "#cbbd96", "#e6dcbc", "#faf4e2"], "metal", seed=21),
        "fang_d": Mat(["#7a6c50", "#968868", "#b2a482", "#ccc09e"], "metal", seed=22),
        "venom": Mat(["#3aa010", "#7ae020", "#c0ff50", "#f0ffb0"], "pulse", glow=True, seed=23),
        "body": Mat(["#22522a", "#33763a", "#47964e", "#66b666"], "metal", seed=24),
        "belly": Mat(["#8a7a28", "#aea040", "#cec060", "#e8dc8a"], "metal", seed=25),
        "wrap": Mat(["#1a120c", "#2a1e14", "#3a2a1e", "#4a3828"], "grip", seed=26),
        "eye": Mat(["#c09000", "#f0d020", "#fff070", "#ffffff"], "flat", seed=27),
        "dark": Mat(["#08140a", "#0e2010", "#162e18", "#1e3a20"], "flat", seed=28),
    }
    w = Weapon(m, grip_y=8, kind="dagger", seed=103)
    w.cyl(2.5, 14, 1.3, "wrap")
    w.ball(0, 1.6, 0, 1.8, 1.4, 1.8, "wrap")
    # 뱀 몸통: 손잡이를 한 바퀴 반 감아 올라가 왼쪽(-X)에서 목이 된다
    pts = []
    for i in range(41):
        t = i / 40
        a = math.pi * 0.5 + t * 2.5 * math.pi
        pts.append((1.8 * math.cos(a), 3.0 + 10.5 * t, 1.8 * math.sin(a)))
    w.tube(pts, lambda t: 0.8 + 0.45 * t, "body")
    w.tube([(0, 3.0, 1.8), (0.9, 1.4, 1.2), (1.6, 0.6, 0.0)], lambda t: 0.8 - 0.3 * t, "body")      # 꼬리 끝
    # 가드: 상아빛 짧은 받침, 오른쪽 끝은 아래로 굽음
    w.box(-2.0, 3.5, 14, 16, -1.5, 1.5, "fang_d")
    w.prism(poly([(3.5, 14.0), (5.0, 12.0), (5.0, 15.0), (3.5, 16.0)]), 1.0, "fang_d")
    # 독니 날: 가드에서 솟아 +X 로 휨, 안쪽(오목한 쪽)은 그늘진 색
    y0, y1 = 16.0, 41.0

    def fang(X, Y):
        t = (Y - y0) / (y1 - y0)
        tc = np.clip(t, 0, 1)
        off = -1.0 + 3.4 * tc ** 2
        hw = 2.6 * (1 - tc) ** 0.85 + 0.3
        return (t >= 0) & (t <= 1) & (np.abs(X - off) <= hw), off, hw
    inb = lambda X, Y: fang(X, Y)[0]
    w.prism(inb, lambda X, Y: 0.5 + 0.6 * np.clip(fang(X, Y)[2] - np.abs(X - fang(X, Y)[1]), 0, 1.7), "fang")
    paint(w, lambda X, Y, Z: inb(X, Y) & (X - fang(X, Y)[1] < -0.2) & (Y >= y0), "fang_d")
    # 독 홈: 짧은 빛 줄 하나 (한 칸 들어감)
    groove(w, lambda X, Y: inb(X, Y) & (Y >= 19) & (Y <= 31) & (np.abs(X - fang(X, Y)[1] - 0.5) <= 0.5), "venom")
    # 머리: 옆모습 쐐기 머리를 왼쪽 위로 쳐듦 (오른쪽 머리를 좌우로 뒤집은 좌표)
    hx, hy, ang = 2.2, 14.8, math.radians(36)
    ca, sa = math.cos(ang), math.sin(ang)
    to_w = lambda u, v: (-(hx + u * ca - v * sa), hy + u * sa + v * ca)
    loc = lambda X, Y: ((-X - hx) * ca + (Y - hy) * sa, -(-X - hx) * sa + (Y - hy) * ca)
    prof = [(-0.5, -1.6), (-0.5, 1.4), (1.8, 2.2), (4.6, 1.8), (6.8, 0.9), (7.4, 0.0), (6.2, -0.8), (3.2, -1.4), (1.0, -2.0)]
    k = 1.35
    headm = poly([to_w(u * k, v * k) for (u, v) in prof])
    w.tube([pts[-1], to_w(0.0, 0.0) + (0,)], 1.2, "body")
    w.prism(headm, lambda X, Y: np.where(loc(X, Y)[0] < 6.0, 1.5, 1.0), "body")
    paint(w, lambda X, Y, Z: headm(X, Y) & (loc(X, Y)[1] < -1.0), "belly")                     # 턱 아래
    paint(w, lambda X, Y, Z: headm(X, Y) & (np.abs(loc(X, Y)[1] + 0.2) <= 0.5) & (loc(X, Y)[0] > 5.0), "dark")  # 입
    ex, ey = to_w(3.4, 0.9)
    w.fill(lambda X, Y, Z: (np.abs(X - ex) <= 1.0) & (np.abs(Y - ey) <= 1.0) & (np.abs(Z) > 1.0) & (np.abs(Z) <= 1.5), "eye")
    w.fill(lambda X, Y, Z: (np.abs(X - ex + 0.5) <= 0.5) & (np.abs(Y - ey) <= 1.0) & (np.abs(Z) > 1.0) & (np.abs(Z) <= 1.6), "dark")
    return w


def storm_dagger():
    """번개 단검: 날 자체가 꺾인 번개, 가드는 양옆으로 갈라져 튀는 작은 번개, 손잡이는 틈이 보이는 구리 코일, 피뢰침 폼멜."""
    m = {
        "rim": Mat(["#6a4206", "#8e600e", "#b6841c", "#d8a830"], "metal", seed=31),
        "bolt": Mat(["#d8a820", "#f0d040", "#fff080", "#fffbd0"], "metal", seed=32),
        "spark": Mat(["#fff4a0", "#fffbd0", "#ffffff", "#ffffff"], "sparkle", glow=True, seed=33),
        "copper": Mat(["#4a200e", "#7a3a1a", "#a85a2c", "#d0844a"], "metal", seed=34),
        "patina": Mat(["#2a6a5a", "#3a8a74", "#52aa90", "#80ccb4"], "metal", seed=35),
        "core": Mat(["#121218", "#1c1c24", "#282832", "#343440"], "grip", seed=36),
    }
    w = Weapon(m, grip_y=7.5, kind="dagger", seed=104)
    w.cyl(2.5, 12.5, 1.2, "core")
    for y in (3.5, 5.5, 7.5, 9.5, 11.5):                                # 구리 코일 (사이사이 어두운 틈)
        w.cyl(y - 0.2, y + 0.2, 1.75, "copper")
    w.ball(0, 1.6, 0, 2.0, 1.6, 2.0, "copper")                          # 피뢰침 공 + 녹청 띠 + 짧은 침
    w.cyl(1.3, 1.9, 2.2, "patina")
    w.box(-0.5, 0.5, -1, 1, -0.5, 0.5, "copper")
    # 가드: 가운데 구리 받침에서 양옆으로 갈라져 튀는 번개 두 갈래 (180도 대칭)
    w.box(-2, 2, 12.5, 14.5, -1.5, 1.5, "copper")
    for s in (-1, 1):
        w.prism(path2d([(s * 1.5, 13.5), (s * 4.5, 14.5 + s * 0.5), (s * 3.5, 13.0 - s * 0.5 + 0.5),
                        (s * 7.0, 14.0 + s * 1.5)], 0.75), 0.5, "rim")
    # 번개 날: 오른쪽으로 기운 세 마디, 마디마다 왼쪽으로 크게 꺾임
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
    w.prism(lambda X, Y: bolt(X, Y, 1.0), 0.5, "bolt")
    # 가운데 마디에만 한 칸짜리 전기 줄 (표면과 평평)
    sc = lambda Y: -2.2 + 3.8 * (Y - 23.5) / 10.0
    w.prism(lambda X, Y: (Y >= 25) & (Y <= 32) & (np.abs(X - sc(Y)) <= 0.5) & bolt(X, Y, 1.0), 0.5, "spark")
    return w


# ─────────────────────────── 서리 (frost) ───────────────────────────

def frost_dagger():
    """고드름 단검: 투명한 흰 얼음 고드름 날(한쪽 면은 그늘), 고드름이 매달린 처마 같은 얼음 가드, 얼어붙은 검은 나무 손잡이."""
    m = {
        "ice": Mat(["#a4c6dc", "#c8e2f2", "#e6f4fc", "#ffffff"], "metal", seed=41),
        "ice_d": Mat(["#6a92b0", "#8cb0cc", "#aecce2", "#cce2f2"], "metal", seed=42),
        "glint": Mat(["#80d8ff", "#c0f0ff", "#ffffff", "#ffffff"], "pulse", glow=True, seed=43),
        "wood": Mat(["#1e222c", "#2c323e", "#3c4452", "#4e5868"], "wood", seed=44),
        "rime": Mat(["#c4d8e8", "#dceaf6", "#f0f8ff", "#ffffff"], "metal", seed=45),
    }
    w = Weapon(m, grip_y=8, kind="dagger", seed=105)
    w.cyl(3, 13.5, 1.4, "wood")
    w.cyl(3, 4.6, 1.8, "rime")                                       # 서리 낀 아래 고리
    w.cyl(12.2, 13.5, 1.8, "rime")
    # 아래로 뾰족한 얼음 폼멜 (사각뿔)
    w.fill(lambda X, Y, Z: (Y >= 0) & (Y <= 3) & (np.maximum(np.abs(X), np.abs(Z)) <= 0.5 + Y * 0.55), "ice_d")
    # 처마 가드: 얼음 막대 + 아래로 매달린 고드름 (길이가 제각각)
    w.box(-5.5, 5.5, 13.5, 16, -1.5, 1.5, "ice_d")
    w.box(-4.5, 4.5, 15, 16, -1.5, 1.5, "ice")
    for (x, L) in ((-5.0, 5.0), (-3.0, 2.5), (3.0, 3.5), (5.0, 6.0)):
        w.prism(poly([(x - 1.0, 13.6), (x + 1.0, 13.6), (x, 13.6 - L)]), 0.5, "ice")
    w.fill(lambda X, Y, Z: (np.abs(X) <= 1) & (np.abs(Y - 14.75) <= 0.8) & (np.abs(Z) <= 2), "glint")   # 얼어붙은 빛
    # 고드름 날: 곧게 줄어들며 군데군데 얼어붙은 마디(물결), 가운데 등줄, 왼쪽 면은 그늘
    y0, y1 = 16, 45
    hw = lambda Y: 3.0 * (1 - tnorm(Y, y0, y1)) + 0.2 + 0.7 * ((np.sin((Y - y0) / 6.5 * 2 * math.pi) > 0.55) & (Y < 38))
    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, 0.5, "ice")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= 1) & (Y <= 39), 1.5, "ice")
    paint(w, lambda X, Y, Z: inb(X, Y) & (X < 0) & (Y >= y0), "ice_d")
    return w


def frost_greatsword():
    """빙하 대검: 금속 없이 청록빛 빙하 얼음으로 자란 날. 밑동의 빙하 바위에서 얼음 가시가 비스듬히 터져 나오고, 갈라진 금 속에서 빛이 샌다. 끝은 비스듬히 잘린 결정."""
    m = {
        "ice": Mat(["#3a7880", "#5a9ea2", "#86c4c2", "#c2eae6"], "metal", seed=51),
        "ice_hi": Mat(["#86c8c6", "#aee2de", "#d6f6f2", "#ffffff"], "metal", seed=52),
        "rune": Mat(["#30d8c8", "#70fff0", "#c0fff8", "#ffffff"], "pulse", glow=True, seed=54),
        "leather": Mat(["#142224", "#203436", "#2e4846", "#3e5c58"], "grip", seed=55),
        "rock": Mat(["#323c40", "#46525a", "#5c6a72", "#748288"], "stone", seed=56),
    }
    w = Weapon(m, grip_y=11.5, kind="greatsword", seed=106)
    # 폼멜: 빙하 바위 덩어리 + 아래로 얼음 한 조각
    w.ball(0, 3.0, 0, 2.8, 2.4, 2.6, "rock")
    w.fill(lambda X, Y, Z: (Y >= 0) & (Y <= 2) & (np.abs(X - 0.5) + np.abs(Z) <= 0.4 + Y * 0.8), "ice_hi")
    w.cyl(5, 18.5, 1.6, "leather")
    # 가드 대신 빙하 바위 (울퉁불퉁)
    w.ball(-0.5, 19.5, 0, 4.2, 2.2, 2.8, "rock")
    w.ball(2.0, 20.5, 0.5, 2.8, 1.8, 2.4, "rock")
    y0, y1 = 20, 71.5
    hw = lambda Y: 5.0 - 1.4 * tnorm(Y, y0, y1)
    body = lambda X, Y: (Y >= y0) & (np.abs(X) <= hw(Y)) & (Y <= 71.5 - 1.7 * (X + 3.4))
    w.prism(body, 1.5, "ice")
    groove(w, lambda X, Y: body(X, Y) & ((np.abs(X) >= hw(Y) - 1.2) | (Y >= 69.5 - 1.7 * (X + 3.4))), "ice_hi")
    # 밑동에서 터져 나온 큰 얼음 가시: (쪽, 시작 Y, 길이)
    spikes = ((-1, 21, 11.0), (1, 24, 9.0), (-1, 32, 6.5), (1, 38, 5.0))
    for (s, yb, L) in spikes:
        e = s * (float(hw(np.array(yb))) - 1.5)
        tip = (e + s * L * 0.85, yb + L * 1.1)
        w.prism(poly([(e, yb), tip, (e, yb + L * 0.8)]), 1.0, "ice_hi")
    # 가시 뿌리에서 날 안쪽으로 뻗은 빛나는 금 (한 칸 들어감)
    cracks = path2d([(-2.6, 23.5), (-0.8, 27.5), (0.6, 33.0)], 0.55)
    cracks2 = path2d([(2.4, 26.5), (1.2, 30.0)], 0.55)
    cracks3 = path2d([(-2.2, 34.0), (-0.6, 38.5), (0.2, 44.0)], 0.55)
    groove(w, lambda X, Y: (cracks(X, Y) | cracks2(X, Y) | cracks3(X, Y)) & body(X, Y), "rune")
    return w


# ─────────────────────────── 화염 (flame) ───────────────────────────

def ember_greatsword():
    """화염 대검: 양쪽 날이 따로 크게 물결치며 끝으로 좁아지는 플람베르주. 그을린 몸통 위로 달군 날과 금 간 용암 줄기, 위로 말려 오르는 불꽃 갈퀴 가드, 쇠 발톱이 쥔 불씨 폼멜."""
    m = {
        "char": Mat(["#2a1410", "#3e1e17", "#542a20", "#6a362a"], "metal", seed=61),
        "hot": Mat(["#8a2a08", "#c84a0c", "#ee7a1e", "#ffb04a"], "metal", seed=62),
        "magma": Mat(["#8a1a00", "#e04a0a", "#ffa020", "#fff0a0"], "fire", glow=True, seed=63),
        "iron": Mat(["#2c2826", "#46403c", "#625a54", "#7e746c"], "metal", seed=64),
        "leather": Mat(["#2a0a08", "#4a1410", "#6a2018", "#8a3020"], "grip", seed=65),
    }
    w = Weapon(m, grip_y=12, kind="greatsword", seed=107)
    # 폼멜: 쇠 발톱이 잡은 불씨
    w.ball(0, 2.8, 0, 2.2, 2.2, 2.2, "magma")
    for s in (-1, 1):
        w.tube([(s * 0.8, 6, 0), (s * 2.8, 3.5, 0), (s * 2.2, 0.8, 0)], 0.8, "iron")
        w.tube([(0, 6, s * 0.8), (0, 3.5, s * 2.8), (0, 0.8, s * 2.2)], 0.8, "iron")
    w.cyl(5, 19, 1.6, "leather")
    w.cyl(5, 5.9, 1.9, "iron")
    # 가드: 가운데 덩어리 + 굵게 말려 올라가는 불꽃 갈퀴 (안쪽 면은 달아오름)
    w.box(-3, 3, 19, 23, -2, 2, "iron")
    for s in (-1, 1):
        curl = [(s * 2.5, 21, 0), (s * 6.5, 20.5, 0), (s * 9.5, 23, 0), (s * 10, 27, 0), (s * 8, 29.5, 0)]
        w.tube(curl, lambda t: 1.9 - 0.9 * t, "iron")
        w.tube([(x - s * 0.9, y + 0.9, z) for (x, y, z) in curl[1:]], lambda t: 1.0 - 0.5 * t, "hot")
    # 날: 두 가장자리가 따로 물결치고 끝으로 갈수록 좁아짐 (두께 2, 물결은 두 줄씩 끊어 픽셀이 깔끔하게)
    y0, y1 = 23, 72

    def edges(Y):
        Yq = np.floor(Y / 2) * 2 + 1
        t = tnorm(Yq, y0, y1)
        hw = 4.0 * (1 - t) ** 0.75 + 0.4
        A = 1.9 * (1 - t) ** 0.6
        ph = (Yq - y0) / 12.0 * 2 * math.pi
        return -hw + A * np.sin(ph), hw + A * np.sin(ph + 0.35 * math.pi), t

    def inb(X, Y):
        a, b, _ = edges(Y)
        return (Y >= y0) & (Y <= y1) & (X >= a) & (X <= b)

    def hot(X, Y):
        a, b, t = edges(Y)
        band = 9.0 * np.clip(t - 0.42, 0, 1) ** 0.8        # 위쪽 절반부터 가장자리에서 달아오름
        return inb(X, Y) & ((X <= a + band) | (X >= b - band))
    w.prism(inb, 0.5, "char")
    w.prism(hot, 0.5, "hot")
    # 금 간 용암 줄기: 그을린 몸통 가운데를 따라 끊어진 줄 (표면과 평평)
    mid = lambda Y: np.round((edges(Y)[0] + edges(Y)[1]) / 2 - 0.5) + 0.5
    seg = lambda Y: ((Y >= 25) & (Y <= 34)) | ((Y >= 37) & (Y <= 45)) | ((Y >= 48) & (Y <= 53))
    w.prism(lambda X, Y: seg(Y) & (np.abs(X - mid(Y)) <= 0.5) & inb(X, Y) & ~hot(X, Y), 0.5, "magma")
    return w


# ─────────────────────────── 공허 (void) ───────────────────────────

def shadow_dagger():
    """그림자 쿠나이: 뾰족한 잎 모양 마름모 날(한쪽 면은 검정, 한쪽 면은 보랏빛 쇠), 날 밑동에 빛나는 짧은 홈, 굵은 천 손잡이, 작은 고리와 짧은 끈."""
    m = {
        "black": Mat(["#0c0a12", "#16121e", "#221c2c", "#2e2738"], "metal", seed=71),
        "bevel": Mat(["#4a4258", "#62587a", "#807498", "#a092b8"], "metal", seed=72),
        "rune": Mat(["#8a3af0", "#b070ff", "#e0b8ff", "#ffffff"], "pulse", glow=True, seed=73),
        "cloth": Mat(["#100c16", "#2a1e3a", "#4c3866", "#604a80"], "grip", seed=74),
        "ribbon": Mat(["#4a1478", "#6a22a0", "#8a3ac8", "#aa5ae0"], "cloth", seed=75),
        "steel": Mat(["#2e2a36", "#46404e", "#625a6c", "#80788a"], "metal", seed=76),
    }
    w = Weapon(m, grip_y=11.5, kind="dagger", seed=108)
    # 작은 고리 폼멜 + 짧은 끈
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 3.0) <= 2.6) & (np.hypot(X, Y - 3.0) > 1.1) & (np.abs(Z) <= 0.5), "steel")
    w.tube([(1.0, 1.0, 0.5), (2.5, -0.5 + 0.5, 0.5), (4.5, 0.5, 0.5)], 0.7, "ribbon")
    w.box(-1.5, 1.5, 5.5, 6.5, -1.5, 1.5, "steel")
    w.cyl(6.5, 17, 1.7, "cloth")                                    # 굵은 천 손잡이
    w.box(-2, 2, 17, 18.5, -1.5, 1.5, "steel")
    # 쿠나이 날: 밑동 좁게 → 넓어졌다가 곧게 뾰족 (최대 반폭 3)
    y0, yw, y1 = 18.5, 23.5, 38.5
    hw = lambda Y: np.where(Y < yw, 1.5 + 2.1 * np.sin(tnorm(Y, y0, yw) * math.pi / 2),
                            3.6 * np.clip((y1 - Y) / (y1 - yw), 0, 1))
    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y) + 0.05)
    w.prism(inb, lambda X, Y: 0.5 + 0.6 * np.clip(hw(Y) - np.abs(X), 0, 1.7), "black")
    paint(w, lambda X, Y, Z: inb(X, Y) & (X > 0) & (Y >= y0), "bevel")              # 빛 받는 면 / 그늘진 면 (마름모 날)
    # 밑동의 빛나는 세로 홈 (한 칸 들어감)
    groove(w, lambda X, Y: (np.abs(X) <= 0.5) & (Y >= 19.5) & (Y <= 22.5), "rune")
    return w


def ender_dagger():
    """엔더 단검: 거의 검은 흑요석 날이 비스듬히 세 조각으로 부러져 옆으로 크게 밀린 채 떠 있다(순간이동 중). 잘린 면만 연보랏빛, 엔드석 가드 가운데 둥근 엔더의 눈."""
    m = {
        "obsid": Mat(["#05030a", "#0c0814", "#160f22", "#221832"], "metal", seed=81),
        "cut": Mat(["#8a6ab8", "#b090e0", "#d4bcf6", "#f4ecff"], "metal", seed=82),
        "portal": Mat(["#8a20d0", "#c040f0", "#e888ff", "#ffe0ff"], "sparkle", glow=True, seed=83),
        "endstone": Mat(["#b0ae78", "#c8c890", "#dcdca6", "#eeeec0"], "stone", seed=84),
        "purpur": Mat(["#6a4a6a", "#8a648a", "#a682a6", "#c0a0c0"], "metal", seed=85),
        "eye": Mat(["#0c4a30", "#1e8a58", "#4ac888", "#b8f4d0"], "gem", glow=True, seed=86),
        "pupil": Mat(["#020806", "#06140c", "#0a2014", "#10301c"], "flat", seed=87),
    }
    w = Weapon(m, grip_y=7.5, kind="dagger", seed=109)
    w.box(-2, 2, 0, 3, -2, 2, "endstone")                          # 엔드석 폼멜
    w.box(-1.5, 1.5, 3, 12, -1.5, 1.5, "purpur")                    # 퍼퍼 기둥 손잡이
    w.box(-2, 2, 7, 8, -2, 2, "endstone")
    # 가드: 엔드석 막대, 양끝은 위로 꺾인 퍼퍼 받침, 가운데 둥근 엔더의 눈
    w.box(-5.5, 5.5, 12, 15, -1.5, 1.5, "endstone")
    for s in (-1, 1):
        w.box(min(s * 4.5, s * 6.5), max(s * 4.5, s * 6.5), 12, 17, -1.5, 1.5, "purpur")
    w.ball(0, 13.5, 0, 2.6, 2.6, 2.6, "eye")
    paint(w, lambda X, Y, Z: (np.abs(X) <= 0.6) & (np.abs(Y - 13.5) <= 1.2) & (np.abs(Z) >= 1.5), "pupil")
    # 날 (하나의 쐐기를 45도로 잘라 세 조각으로)
    y0, y1 = 17.0, 47.0
    hw = lambda Y: np.interp(Y, [17, 36, 47], [4.0, 3.2, 0.2])
    k = 0.8                                         # 자르는 선의 기울기 (Y - k*X = 일정)
    pieces = ((17.0, 26.0, 0.0, 0.0), (27.5, 34.5, 3.5, 1.5), (36.0, 70.0, -3.5, 3.0))   # (아래, 위, dx, dy)
    for (a, b, dx, dy) in pieces:
        def shard(X, Y, a=a, b=b, dx=dx, dy=dy):
            x, y = X - dx, Y - dy
            c = y - k * x
            return (y >= y0) & (y <= y1) & (np.abs(x) <= hw(y)) & (c >= a) & (c <= b), x, y, c
        hz = lambda X, Y, s=shard: 0.5 + 0.6 * np.clip(hw(s(X, Y)[2]) - np.abs(s(X, Y)[1]), 0, 1.7)
        w.prism(lambda X, Y, s=shard: s(X, Y)[0], hz, "obsid")
        cutm = lambda X, Y, a=a, b=b, s=shard: s(X, Y)[0] & (((s(X, Y)[3] - a) < 1.2 * (a > y0)) | ((b - s(X, Y)[3]) < 1.2 * (b < 50)))
        paint(w, lambda X, Y, Z, cm=cutm: cm(X, Y), "cut")
    # 틈새의 포털 불티 (조각이 밀려난 자리)
    for (x, y) in ((2.5, 28.5), (-2.5, 39.5), (6.0, 41.0)):
        w.box(x - 0.5, x + 0.5, y - 0.5, y + 0.5, -0.5, 0.5, "portal")
    return w


# ─────────────────────────── 보스 (boss) ───────────────────────────

def frostlord_greatsword():
    """서리 군주의 대검: 한밤 강철의 넓은 외날 처형검(곧은 은빛 등, 불룩한 날, 곧게 깎인 날카로운 끝). 리카소를 두른 은관의 끝은 고드름처럼 바깥 아래로 뻗고, 각진 얼음 심장이 박혔으며, 서리가 날 위로 기어오른다."""
    m = {
        "night": Mat(["#0a0f24", "#121a36", "#1c284c", "#283866"], "metal", seed=91),
        "silver": Mat(["#56607a", "#8490a8", "#b8c4d6", "#eef2f8"], "metal", seed=92),
        "edge": Mat(["#8a98b4", "#aebcd2", "#d2dcea", "#ffffff"], "metal", seed=97),
        "frost": Mat(["#3a8aff", "#70c0ff", "#b8e8ff", "#ffffff"], "flow", glow=True, seed=93),
        "heart": Mat(["#1a70d0", "#50b0ff", "#b0e4ff", "#ffffff"], "gem", glow=True, seed=94),
        "icegem": Mat(["#3a7ab8", "#6aa8e0", "#b0dcfa", "#ffffff"], "gem", seed=98),
        "grip": Mat(["#0a0e1e", "#121a32", "#1c284a", "#283862"], "grip", seed=96),
        "fur": Mat(["#a8b0bc", "#c8d0da", "#e2e8ee", "#f8fafc"], "cloth", seed=95),
    }
    w = Weapon(m, grip_y=12, kind="greatsword", seed=110)
    # 폼멜: 은 받침 + 아래로 매달린 각진 얼음
    octa(w, 0, 2.2, 0, 2.2, 3.0, 2.2, "icegem")
    w.cyl(3.8, 5.5, 2.2, "silver")
    w.cyl(5.5, 19.5, 1.7, "grip")                          # 긴 두 손 손잡이
    w.cyl(18.5, 21.0, 2.5, "fur")                          # 털 깃
    # 은관: 리카소를 감싼 띠, 양옆은 고드름처럼 처진 긴 가로 날개, 띠 아래로 짧은 고드름
    w.box(-6.5, 6.5, 21, 25, -2.5, 2.5, "silver")
    w.box(-5.5, 5.5, 25, 26, -2.0, 2.0, "silver")
    for s in (-1, 1):
        w.prism(poly([(s * 6.0, 21.0), (s * 6.0, 25.5), (s * 10.0, 24.0), (s * 15.0, 20.5), (s * 10.0, 21.0)]), 1.0, "silver")
        for (x, L) in ((5.0, 4.5),):
            w.prism(poly([(s * (x - 1.0), 21.0), (s * (x + 1.0), 21.0), (s * x, 21.0 - L)]), 1.0, "silver")
    # 날: 등(-X)은 곧고, 날(+X)은 위로 갈수록 크게 불룩하다가 휘어 올라 등 쪽 끝에서 뾰족 (팔시온)
    y0, y1 = 26.0, 72.0
    xs = lambda Y: np.where(Y < 66, -3.5, -3.5 + 1.5 * (Y - 66) / 6)
    xe = lambda Y: np.interp(Y, [26, 40, 52, 59, 64, 68, 72], [4.5, 5.8, 7.4, 8.0, 6.8, 3.6, -1.9])
    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (X >= xs(Y)) & (X <= xe(Y))
    w.prism(inb, 1.5, "night")
    paint(w, lambda X, Y, Z: inb(X, Y) & (X <= xs(Y) + 1.0) & (Y >= y0), "silver")          # 곧은 은빛 등
    groove(w, lambda X, Y: inb(X, Y) & (X >= xe(Y) - 1.6) & (X > xs(Y) + 1.0), "edge")
    # 얼음 심장: 은 테 안의 각진 보석 (앞뒤로 튀어나옴)
    disc(w, 0.5, 31.5, 4.0, 2.0, "silver")
    octa(w, 0.5, 31.5, 0, 3.0, 3.6, 3.6, "heart")
    # 심장에서 날 위로 기어오르는 서리 (한 칸 들어간 빛나는 가지)
    fr = (path2d([(1.0, 34.5), (2.0, 40.0), (1.2, 46.0)], 0.5), path2d([(2.0, 40.0), (4.5, 44.0)], 0.5),
          path2d([(0.0, 34.5), (-1.8, 39.0), (-1.4, 43.0)], 0.5), path2d([(1.2, 46.0), (2.6, 50.5)], 0.5))
    groove(w, lambda X, Y: inb(X, Y) & (fr[0](X, Y) | fr[1](X, Y) | fr[2](X, Y) | fr[3](X, Y)), "frost")
    w.set_aura(["#1a2a8a", "#2a6ae0", "#5ad0ff", "#e8ffff"], "frost", size=0.8, focus=["heart"])
    return w


def shadow_twinblade():
    """암살자의 쌍검: 긴 진홍 손잡이 양끝에 서로 반대로 휜 초승달 날(180도 대칭). 은빛으로 간 바깥 날, 안쪽 등의 굵은 톱니, 고리마다 갈고리 발톱과 자홍 보석."""
    m = {
        "blade": Mat(["#1a1720", "#28232f", "#383242", "#4a4256"], "metal", seed=121),
        "edge": Mat(["#8a8a9c", "#b4b4c6", "#dadae6", "#ffffff"], "metal", seed=122),
        "steel": Mat(["#2a2630", "#423c4a", "#5c5468", "#7a7088"], "metal", seed=123),
        "wrap": Mat(["#2a0a10", "#460f1a", "#661a26", "#862834"], "grip", seed=124),
        "gem": Mat(["#7a0a4a", "#c02080", "#ff60c0", "#ffd8f4"], "pulse", glow=True, seed=125),
    }
    yc = 36
    w = Weapon(m, grip_y=yc, kind="katana", seed=111)
    # 위쪽 절반만 만들고 180도 돌려 복사
    w.cyl(yc, yc + 8.5, 1.6, "wrap")                               # 손잡이 (가운데 17칸)
    w.box(-2.5, 2.5, yc + 8.5, yc + 12, -2, 2, "steel")            # 고리
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - (yc + 10.25)) <= 1.2) & (np.abs(Z) <= 2.6), "gem")
    # 갈고리 발톱 (날 안쪽으로 굽은 굵은 갈고리)
    w.tube([(2.0, yc + 11, 0), (5.5, yc + 11.5, 0), (8.0, yc + 9.5, 0), (8.0, yc + 6.0, 0)], lambda t: 1.4 - 0.7 * t, "steel")
    y0, y1 = yc + 12, 71.5
    ctr = lambda Y: 8.0 * tnorm(Y, y0, y1) ** 2

    def hw(Y):
        t = tnorm(Y, y0, y1)
        return 2.4 * (1 - t) ** 0.7 + 0.4 + 2.4 * np.sin(t * math.pi) ** 0.8 * (1 - t) ** 0.3

    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X - ctr(Y)) <= hw(Y))
    w.prism(inb, 1.0, "blade")
    paint(w, lambda X, Y, Z: inb(X, Y) & (X - ctr(Y) <= -hw(Y) + 1.4), "edge")      # 바깥(볼록한 쪽) 날
    # 안쪽 등의 굵은 톱니 3개
    for yb in (y0 + 1.5, y0 + 5.5, y0 + 9.5):
        cb = float(ctr(np.array(yb))) + float(hw(np.array(yb)))
        w.prism(poly([(cb - 1.0, yb), (cb + 2.8, yb + 3.2), (cb - 1.0, yb + 3.6)]), 1.0, "steel")
    rot180(w, yc)
    w.set_aura(["#3a0a4a", "#8a1a9a", "#e050d0", "#ffd0f8"], "void", size=0.8, focus=["gem"])
    return w


def star_greatsword():
    """별의 대검: 별빛이 반짝이는 남색 에스톡 날이 금 테두리와 함께 곧게 좁아지다가 네 갈래 별이 되어 그 위 꼭짓점이 칼끝이 된다. 가드는 날을 받치는 초승달, 가운데 금 테 각진 보석, 폼멜은 빛 새는 운석."""
    m = {
        "night": Mat(["#0c0e30", "#161a4a", "#222a66", "#323c86"], "sparkle", seed=131),
        "gold": Mat(["#6a4a10", "#a87c20", "#dcb448", "#fff0a8"], "metal", seed=132),
        "star": Mat(["#ffe080", "#fff2b8", "#ffffff", "#ffffff"], "pulse", glow=True, seed=133),
        "moon": Mat(["#7a7aa0", "#a8acc8", "#d4d8ec", "#f8f8ff"], "metal", seed=136),
        "gem": Mat(["#2050c0", "#4a90f0", "#a8d4ff", "#ffffff"], "gem", glow=True, seed=137),
        "frame": Mat(["#1a1440", "#2a2260", "#3c3282", "#5046a0"], "metal", seed=138),
        "rock": Mat(["#1a1820", "#2a2630", "#3c3644", "#504858"], "stone", seed=134),
        "wrap": Mat(["#10143a", "#1a2256", "#283274", "#384494"], "grip", seed=135),
    }
    w = Weapon(m, grip_y=9.5, kind="greatsword", seed=112)
    # 폼멜: 운석 (빛이 새는 틈)
    w.ball(0, 2.6, 0, 2.8, 2.6, 2.6, "rock")
    paint(w, lambda X, Y, Z: (np.abs(X - 0.5 - (Y - 2.5) * 0.6) <= 0.5) & (np.abs(Y - 2.5) <= 1.5) & (np.abs(Z) >= 1.5), "gem")
    w.cyl(5, 16.5, 1.6, "wrap")
    w.cyl(14.5, 16.5, 1.9, "gold")
    # 초승달 가드 (뿔이 위로), 가운데 금 테 보석
    moon = lambda X, Y: (np.hypot(X, Y - 24.0) <= 8.0) & (np.hypot(X * 1.05, Y - 27.5) > 7.0) & (Y >= 16)
    w.prism(moon, 1.5, "moon")
    paint(w, lambda X, Y, Z: moon(X, Y) & (np.hypot(X, Y - 24.0) > 7.0), "gold")
    disc(w, 0, 19.0, 2.8, 2.0, "frame")
    disc(w, 0, 19.0, 3.5, 1.0, "gold")
    octa(w, 0, 19.0, 0, 2.0, 2.0, 2.8, "gem")
    # 에스톡 날: 넓은 밑동에서 별까지 곧게 좁아지는 긴 삼각형, 마름모 단면
    y0, ys, y1 = 20.0, 62.0, 72.0
    hw = lambda Y: 4.6 - 2.8 * tnorm(Y, y0, ys)
    inb = lambda X, Y: (Y >= y0) & (Y <= ys) & (np.abs(X) <= hw(Y))
    w.prism(inb, lambda X, Y: 0.5 + 0.7 * np.clip(hw(Y) - np.abs(X), 0, 1.5), "night")
    paint(w, lambda X, Y, Z: inb(X, Y) & (np.abs(X) >= hw(Y) - 1.0), "gold")
    # 끝: 네 갈래 별 (위 갈래가 칼끝, 아래 갈래는 날에 녹아듦), 금 테두리 안에 빛나는 별
    def star(r_in, up, side, down):
        return poly([(0, ys + up), (r_in, ys + r_in), (side, ys), (r_in, ys - r_in), (0, ys - down),
                     (-r_in, ys - r_in), (-side, ys), (-r_in, ys + r_in)])
    w.prism(star(2.1, 10.0, 8.0, 7.0), lambda X, Y: np.where(np.hypot(X, Y - ys) < 2.5, 2.0, 1.0), "gold")
    paint(w, lambda X, Y, Z: star(1.2, 8.2, 6.4, 5.2)(X, Y), "star")
    w.set_aura(["#8a6a20", "#d8a838", "#ffe27a", "#fffbe8"], "holy", size=0.65, focus=["star"])
    return w


def prism_greatsword():
    """프리즘 대검: 금속 없는 수정 날 — 자홍·청록 두 장의 결정 판 사이로 넓은 무지개 빛줄기가 평평하게 흐르고, 끝은 각진 마름모 단면. 아래를 향한 삼각 프리즘 가드에서 빛이 시작되고, 팔면체 수정 셋이 떠 돈다."""
    m = {
        "magenta": Mat(["#4a1070", "#7420a8", "#a046d0", "#cc86ec"], "metal", seed=141),
        "cyan": Mat(["#08427a", "#1268b0", "#2c9ade", "#80d0ff"], "metal", seed=142),
        "facet": Mat(["#c8d0f0", "#e0e6ff", "#f4f6ff", "#ffffff"], "metal", seed=149),
        "beam": Mat(["#ff0000", "#00ff00", "#0000ff", "#ffffff"], "rainbow", glow=True, seed=143),
        "beam_g": Mat(["#ff0000", "#00ff00", "#0000ff", "#ffffff"], "rainbow", glow=True, seed=150),
        "gold": Mat(["#7a5a18", "#b88a2c", "#e8c858", "#fff4b8"], "metal", seed=144),
        "white": Mat(["#9a9ab0", "#c4c4d4", "#e2e2ec", "#ffffff"], "grip", seed=145),
        "pink": Mat(["#c02070", "#f060a8", "#ffa8d4", "#ffffff"], "gem", glow=True, seed=146),
        "aqua": Mat(["#108ab8", "#30c0ec", "#98ecff", "#ffffff"], "gem", glow=True, seed=147),
        "sun": Mat(["#c08a00", "#f0c020", "#fff07a", "#ffffff"], "gem", glow=True, seed=148),
    }
    w = Weapon(m, grip_y=10.5, kind="greatsword", seed=113)
    w.gem(0, 2.6, 1.9, "beam_g", frame="gold", depth=2.0)               # 무지개 폼멜
    w.cyl(4.5, 17, 1.6, "white")
    w.cyl(4.5, 5.4, 1.9, "gold")
    w.cyl(16.1, 17, 1.9, "gold")
    # 삼각 프리즘 가드 (꼭짓점이 아래), 안에서 빛이 시작
    w.prism(poly([(-10.5, 28), (10.5, 28), (0, 16)]), 2.0, "gold")
    w.prism(poly([(-8.2, 27), (8.2, 27), (0, 18.5)]), 2.5, "facet")
    w.prism(poly([(-2.6, 28), (2.6, 28), (0, 21.0)]), 3.0, "beam_g")
    # 날: 마름모 단면의 수정, 왼쪽 자홍 / 오른쪽 청록, 흰 결정 날 면, 가운데 넓은 빛줄기 (판과 같은 높이)
    y0, yp, y1 = 28.0, 59.0, 72.0
    hw = lambda Y: np.where(Y < yp, 6.0 - 0.6 * tnorm(Y, y0, yp), 5.4 * np.clip((y1 - Y) / (y1 - yp), 0, 1) + 0.2)
    hz = lambda X, Y: 0.5 + 0.55 * np.clip(hw(Y) - np.abs(X), 0, 2)
    inb = lambda X, Y: (Y >= y0) & (Y <= y1) & (np.abs(X) <= hw(Y))
    w.prism(inb, hz, "facet")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.2) & (X < 0), hz, "magenta")
    w.prism(lambda X, Y: inb(X, Y) & (np.abs(X) <= hw(Y) - 1.2) & (X > 0), hz, "cyan")
    bw = lambda Y: np.minimum(2.0, hw(Y) - 1.6)
    paint(w, lambda X, Y, Z: inb(X, Y) & (np.abs(X) <= bw(Y)), "beam")
    # 떠 있는 팔면체 수정 셋
    # 떠 있는 결정 셋: 양끝이 뾰족한 육각 기둥, 마름모 단면
    for (x, y, mt) in ((-11.0, 40, "pink"), (11.0, 49, "aqua"), (-10.0, 59, "sun")):
        w.prism(poly([(x, y + 5.5), (x + 1.8, y + 2.2), (x + 1.8, y - 2.2), (x, y - 5.5), (x - 1.8, y - 2.2), (x - 1.8, y + 2.2)]),
                lambda X, Y, x=x: 0.5 + np.clip(1.6 - np.abs(X - x), 0, 1), mt)
    w.set_aura("prism", "holy", size=0.8, focus=["beam_g"])
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
