"""
polearms: 창과 낫 12 자루.

python3 polearms.py            -> preview/polearms.png
python3 polearms.py id1 id2    -> 그 무기만 preview/_scratch/polearms_part.png (크게 보기용)

설계 원칙 (이번 판)
  - 창 일곱 자루는 길이, 자루(휜 뼈 토막, 2복셀 투창, 팔각, 가늘어지는 흰 자루), 머리 잇는 방식이 모두 다르다.
  - 날은 모두 두께가 있다: 창촉은 가장자리를 한 칸씩 깎아(erode) 가장자리 2복셀, 안쪽 4복셀,
    낫날은 등 5 -> 몸 3 -> 날 2 복셀. 납작한 날은 Z>=0 쪽에 두어 element 를 절반으로 아낀다.
  - 낫 다섯 자루는 날 모양이 서로 다르다 (농사 낫 초승달, 턱뼈 갈고리, 위로 넘어가는 갈고리, 양날, S자 톱날).
  - 아우라는 보스/프리즘 네 자루만, 불꽃은 작은 빛 심지에서만 (인벤토리에서 모양이 살아 있게).
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


def tn(Y, y0, y1):
    return np.clip((Y - y0) / (y1 - y0), 0, 1)


def g2(w):
    """앞에서 본 2D 격자 좌표 (W, H)."""
    return w._X[:, :, 0], w._Y[:, :, 0]


def put(w, m2, hd, mat, cz=0.0):
    """2D 마스크 m2 를 반두께 hd (숫자나 (W,H) 배열) 로 세운다."""
    hd = np.broadcast_to(np.asarray(hd, float), m2.shape)
    w.grid[m2[:, :, None] & (np.abs(w._Z - cz) <= hd[:, :, None])] = w._id(mat)


def paint(w, m3, mat):
    """이미 있는 복셀만 색을 바꾼다."""
    w.grid[np.asarray(m3, bool) & (w.grid > 0)] = w._id(mat)


def depth_levels(m2):
    """가장자리에서 몇 칸 안쪽인지 (가장자리 1, 그 안 2, ...). 4/8 이웃을 번갈아 깎아 팔각형 거리."""
    d = np.zeros(m2.shape, np.int16)
    cur = m2.copy()
    k = 0
    while cur.any() and k < 16:
        k += 1
        d[cur] = k
        e = cur.copy()
        e[1:, :] &= cur[:-1, :]
        e[:-1, :] &= cur[1:, :]
        e[:, 1:] &= cur[:, :-1]
        e[:, :-1] &= cur[:, 1:]
        e[0, :] = e[-1, :] = False
        if k % 2 == 0:
            e[1:, 1:] &= cur[:-1, :-1]
            e[:-1, :-1] &= cur[1:, 1:]
            e[1:, :-1] &= cur[:-1, 1:]
            e[:-1, 1:] &= cur[1:, :-1]
        cur = e
    return d


BZ = 2.0   # 납작한 날의 Z 중심: 0..4 에 두면 Z=0 경계를 넘지 않아 element 가 절반 (1/16 블록 앞으로 나올 뿐)


def bevel(w, m2, hds, mat, cz=0.0):
    """
    두께 있는 날: 가장자리 칸은 hds[0], 한 칸 안은 hds[1] ... (마지막 값이 계속).
    hd 1 = 2복셀, 2 = 4복셀, 3 = 6복셀 두께. 깊이 지도 d 를 돌려준다 (색칠용).
    """
    d = depth_levels(m2)
    hd = np.zeros(m2.shape)
    for i in range(1, 17):
        hd[d == i] = hds[min(i, len(hds)) - 1]
    put(w, d > 0, hd, mat, cz)
    return d


def octshaft(w, y0, y1, r0, r1, mat, cx=0.0):
    """팔각 자루 (r0 아래 -> r1 위로 가늘어짐)."""
    def fn(X, Y, Z):
        r = r0 + (r1 - r0) * tn(Y, y0, y1)
        ax, az = np.abs(X - cx), np.abs(Z)
        return (Y >= y0) & (Y <= y1) & (ax <= r) & (az <= r) & (ax + az <= r * 1.35)
    return w.fill(fn, mat)


def band(w, y0, y1, r, mat, cx=0.0):
    """네모난 테 (원기둥 테보다 element 가 훨씬 적다)."""
    return w.box(cx - r, cx + r, y0, y1, -r, r, mat)


def grip_wrap(w, y0, y1, r, mat, edge, cx=0.0):
    """감은 손잡이 + 위아래 테."""
    w.cyl(y0, y1, r, mat, cx=cx)
    w.cyl(y0 - 1, y0, r + 0.4, edge, cx=cx)
    w.cyl(y1, y1 + 1, r + 0.4, edge, cx=cx)
    return w


def arcf(w, cx, cy, rx, ry, a0, a1):
    """타원 호를 따라: t (a0 -> a1 로 0 -> 1, 범위 밖은 >1) 와 바깥 테두리에서 잰 깊이 d."""
    X, Y = g2(w)
    nx, ny = (X - cx) / rx, (Y - cy) / ry
    ang = np.degrees(np.arctan2(ny, nx))
    if a1 >= a0:
        t = ((ang - a0) % 360) / (a1 - a0)
    else:
        t = ((a0 - ang) % 360) / (a0 - a1)
    d = (1 - np.hypot(nx, ny)) * (rx + ry) / 2
    return t, d


def arc_pt(cx, cy, rx, ry, a0, a1, t, depth=0.0):
    a = math.radians(a0 + (a1 - a0) * t)
    return (cx + (rx - depth) * math.cos(a), cy + (ry - depth) * math.sin(a))


def spline(pts, n=400):
    """Catmull-Rom 곡선 위의 점들 (길이 비례 t 와 함께)."""
    P = np.array(pts, float)
    P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    segs = len(pts) - 1
    per = max(4, n // segs)
    out = []
    for i in range(segs):
        p0, p1, p2, p3 = P[i:i + 4]
        for s in np.linspace(0, 1, per, endpoint=False):
            out.append(0.5 * (2 * p1 + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
    out.append(P[-2])
    S = np.array(out)
    L = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(S, axis=0).T))])
    return S, L / L[-1]


def pathf(w, pts):
    """곡선(척추)을 따라: t (0 -> 1), 거리 dist, 진행 방향의 왼쪽이면 side=+1."""
    S, T = spline(pts)
    X, Y = g2(w)
    P = np.stack([X.ravel(), Y.ravel()], 1)
    D = np.hypot(P[:, None, 0] - S[None, :, 0], P[:, None, 1] - S[None, :, 1])
    idx = D.argmin(1)
    tan = np.gradient(S, axis=0)[idx]
    rel = P - S[idx]
    side = np.sign(tan[:, 0] * rel[:, 1] - tan[:, 1] * rel[:, 0])
    sh = X.shape
    return T[idx].reshape(sh), D[np.arange(len(P)), idx].reshape(sh), side.reshape(sh)


def sqhelix(w, y0, y1, R, th, h, dy, mat, cx=0.0, start=0):
    """자루를 네모나게 감는 띠: 한 면에 한 토막씩, 토막마다 dy 만큼 오른다 (마크다운 계단 나선). 토막 목록을 돌려준다."""
    segs = []
    k = 0
    while y0 + k * dy + h <= y1 + 1e-6:
        y = y0 + k * dy
        f = (start + k) % 4
        if f == 0:
            box = (cx - R, cx + R, y, y + h, R - th, R)
        elif f == 1:
            box = (cx + R - th, cx + R, y, y + h, -R, R)
        elif f == 2:
            box = (cx - R, cx + R, y, y + h, -R, -R + th)
        else:
            box = (cx - R, cx - R + th, y, y + h, -R, R)
        w.box(*box, mat)
        segs.append((f, box))
        k += 1
    return segs


def slab(w, m2, z0, z1, mat):
    """2D 마스크를 Z 범위 [z0, z1] 로 세운다. 날은 Z>=0 안에 두어 element 를 아낀다
    (등 0..5 = 5복셀, 몸 1..4 = 3복셀, 날 1..3 = 2복셀)."""
    w.grid[np.asarray(m2, bool)[:, :, None] & (w._Z >= z0) & (w._Z <= z1)] = w._id(mat)


def drop2d(X, Y, x, y, ln=2.5, r=1.4):
    """매달린 물방울: 붙은 가는 목 + 둥근 방울 (2D 마스크)."""
    x = math.floor(x) + 0.5
    m = (np.abs(X - x) <= 0.6) & (Y <= y) & (Y >= y - ln)
    return m | (np.hypot(X - x, (Y - (y - ln - r * 0.8)) * 1.1) <= r)


# ─────────────────────────── basic ───────────────────────────

def bone_spear():
    """뼈창: 짧고 투박하다. 계단처럼 살짝 휜 넓적다리뼈(양 끝이 불룩) 자루, 끈으로 동여맨 깨진 뼈 조각 촉."""
    m = {
        "bone": Mat(["#74664c", "#9c8e6e", "#c0b290", "#ddd2b2"], "wood", seed=1),
        "knob": Mat(["#665a44", "#8c7f62", "#aea284", "#cabfa2"], "wood", seed=2),
        "shard": Mat(["#c8c0a8", "#e0d9c6", "#f0ebde", "#ffffff"], "flat", seed=3),
        "shard_d": Mat(["#948b74", "#aea690", "#c4bca6", "#d6cfba"], "flat", seed=4),
        "twine": Mat(["#8e7848", "#b09a62", "#ceb882", "#e6d4a0"], "grip", seed=5),
        "hide": Mat(["#2c1a0e", "#462a18", "#603e24", "#7a5232"], "grip", seed=6),
    }
    w = Weapon(m, grip_y=18, kind="spear", seed=101)
    # 휜 넓적다리뼈: 토막마다 한 칸씩 옆으로, 가운데가 가늘다
    for (y0, y1, cx, r) in ((4, 12, 0, 2.3), (12, 25, 1, 2.0), (25, 36, 2, 1.8), (36, 42, 1, 2.0), (42, 46, 0, 2.3)):
        w.cyl(y0, y1, r, "bone", cx=cx)
    # 아래 관절머리 두 덩이, 위 관절머리 + 큰돌기
    w.ball(-1.2, 3.6, 0, 2.8, 3.2, 2.6, "knob")
    w.ball(2.2, 3.0, 0, 2.4, 2.8, 2.4, "knob")
    w.ball(0.0, 45.0, 0, 3.2, 2.6, 3.0, "knob")
    w.ball(3.0, 42.6, 0, 1.6, 2.2, 1.6, "knob")
    # 가죽 손잡이 + 밝은 끈 테
    w.cyl(13, 24, 2.6, "hide", cx=1)
    w.cyl(12, 13.2, 2.9, "twine", cx=1)
    w.cyl(23.8, 25, 2.9, "twine", cx=1)
    # 깨진 뼈 조각 촉 (왼쪽은 깨진 자국, 오른쪽은 갈아 낸 날), 두께 4 -> 가장자리 2
    X, Y = g2(w)
    head = poly([(-3.2, 45.5), (3.8, 45.5), (5.8, 49.5), (4.8, 52.5), (5.6, 55.5), (3.6, 60), (1.0, 65.0),
                 (-0.6, 63.6), (-2.0, 60.6), (-4.6, 57.4), (-3.6, 54.4), (-5.4, 50.6)])(X, Y)
    bevel(w, head, (1, 2), "shard", cz=BZ)
    paint(w, (head & (X < 0.5))[:, :, None] & (w._Y > 0), "shard_d")       # 왼쪽 면은 그늘
    # 촉을 동여맨 끈: 굵은 감기 둘 + 앞을 가로지르는 한 가닥
    w.cyl(44.5, 46.0, 3.4, "twine")
    w.cyl(47.5, 49.0, 3.0, "twine")
    w.box(-3.0, 3.0, 46.0, 47.5, 3.0, 4.6, "twine")
    return w


# ─────────────────────────── island ───────────────────────────

def storm_spear():
    """번개 창: 가는 2복셀 투창 자루, 몸통의 40% 를 차지하는 굵은 계단식 번개 촉 (밝은 면/어두운 면), 굵은 구리 코일 셋."""
    m = {
        "wood": Mat(["#56607a", "#728098", "#94a0b8", "#b8c2d6"], "wood", seed=11),
        "copper": Mat(["#6a3418", "#b06030", "#e08c50", "#ffc090"], "metal", seed=12),
        "verd": Mat(["#2a5a50", "#3e8270", "#5cae94", "#98dcc4"], "flat", seed=13),
        "steel": Mat(["#b4bed0", "#ccd5e4", "#e4eaf4", "#ffffff"], "flat", seed=14),
        "steel_d": Mat(["#56627c", "#68748e", "#7a86a0", "#8c98b0"], "flat", seed=17),
        "wrap": Mat(["#141a2c", "#202a46", "#2e3c62", "#40507e"], "grip", seed=15),
        "spark": Mat(["#2a5ad8", "#6aa8ff", "#c8ecff", "#ffffff"], "pulse", glow=True, seed=16),
    }
    w = Weapon(m, grip_y=25, kind="spear", seed=111)
    # 2x2 가는 자루
    w.box(-1, 1, 5, 44, -1, 1, "wood")
    # 땅에 꽂는 구리 촉 + 녹청 테
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Z) <= 0.4 + Y * 0.3) & (Y <= 6), "copper")
    w.cyl(5.5, 7, 1.8, "verd")
    grip_wrap(w, 20, 30, 1.7, "wrap", "copper")
    # 피뢰침 코일: 굵은 구리 고리 셋 (녹청 받침)
    for y in (33.0, 35.5, 38.0):
        w.cyl(y, y + 1.5, 2.3, "copper")
    w.cyl(32, 33, 1.7, "verd")
    # 소켓 + 불꽃 구슬
    w.cyl(40, 44, 1.9, "copper")
    w.gem(0, 42, 1.0, "spark", depth=2.4)
    # 계단식 번개 촉: 비스듬한 획 셋을 가로 꺾임 둘로 잇는다
    X, Y = g2(w)

    def stroke(x0, y0, x1, y1, hw0, hw1):
        t = (Y - y0) / (y1 - y0)
        return (t >= 0) & (t <= 1) & (np.abs(X - (x0 + (x1 - x0) * t)) <= hw0 + (hw1 - hw0) * t)
    bolt = stroke(0.0, 43.5, 3.6, 55.5, 3.0, 3.0)
    bolt |= (Y >= 53.0) & (Y <= 56.5) & (X >= -5.0) & (X <= 6.6)
    bolt |= stroke(-2.6, 55.0, 1.6, 64.5, 2.6, 2.6)
    bolt |= (Y >= 62.0) & (Y <= 65.0) & (X >= -5.4) & (X <= 4.6)
    bolt |= stroke(-2.6, 64.0, 0.6, 72.5, 2.6, 0.2)
    bevel(w, bolt, (1, 2), "steel", cz=BZ)
    # 획마다 가운데 선 왼쪽은 어두운 면 (꺾임은 아래 반쪽)
    c = np.interp(Y, [43.5, 53.0, 56.5, 62.0, 65.0, 72.5], [0.0, 3.0, -1.6, 1.4, -1.8, 0.6])
    dark = bolt & (X < np.round(c))
    paint(w, dark[:, :, None] & (w._Y > 0), "steel_d")
    return w


def tide_spear():
    """파도의 창: 작살촉의 왼쪽이 그대로 큰 파도가 되어 말려 부서진다(속이 빈 통, 흰 거품 볏), 오른쪽엔 미늘. 크림색 소라 소켓, 감아 둔 작살줄."""
    m = {
        "drift": Mat(["#5c5040", "#857560", "#ab9b7e", "#cdbfa2"], "wood", seed=21),
        "prism": Mat(["#2a8a6c", "#38a886", "#52c4a0", "#7adcbc"], "flat", seed=22),
        "deep": Mat(["#1a5a66", "#22707c", "#2c8692", "#3a9ca6"], "flat", seed=23),
        "hollow": Mat(["#0a2c3a", "#103a4a", "#164a5a", "#1e5a6a"], "flat", seed=31),
        "foam": Mat(["#c8f0ea", "#e0f8f4", "#f4fffc", "#ffffff"], "flat", seed=24),
        "shell": Mat(["#c8b498", "#e0d0b6", "#f2e8d6", "#fffaf0"], "flat", seed=25),
        "spiral": Mat(["#7a5434", "#9a6c46", "#b8885c", "#d0a474"], "flat", seed=29),
        "rope": Mat(["#5a4026", "#7a5834", "#987046", "#b4885a"], "grip", seed=26),
        "hide": Mat(["#18282a", "#24383a", "#324c4c", "#446262"], "grip", seed=30),
        "lantern": Mat(["#4a8a8a", "#90d0c8", "#d8f8f0", "#ffffff"], "sparkle", glow=True, seed=27),
        "barn": Mat(["#8a8a80", "#aeaea2", "#cecec2", "#ecece2"], "flat", seed=28),
    }
    w = Weapon(m, grip_y=17, kind="spear", seed=121)
    w.cyl(4, 45, 1.6, "drift")
    # 꼬리: 작살줄을 묶는 고리
    w.cyl(3, 5, 2.0, "deep")
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 1.4) >= 0.9) & (np.hypot(X, Y - 1.4) <= 2.3) & (np.abs(Z) <= 1) & (Y < 3.2), "deep")
    grip_wrap(w, 11, 23, 2.0, "hide", "deep")
    # 감아 둔 작살줄 (굵은 고리 셋) + 촉의 미늘까지 이어지는 줄
    for y in (27.5, 29.5, 31.5):
        w.cyl(y, y + 1.4, 2.8, "rope")
    w.tube([(2.2, 33.0, 0.5), (4.2, 42, 0.5), (5.8, 50.0, 0.5)], 0.7, "rope")
    # 큰 따개비 둘 (가운데 구멍)
    for (x, y, z, r) in ((-1.4, 37.5, 0.6, 1.8), (1.2, 41.0, -0.2, 1.5)):
        w.ball(x, y, z, r, r, r, "barn")
        w.box(x - 0.5, x + 0.5, y - 0.5, y + 0.5, z + r - 1.2, z + r + 0.2, "deep")
    # 크림색 소라 소켓: 위로 갈수록 커지는 나선층 셋, 층 사이 갈색 골
    for (y0, y1, r) in ((44, 46.5, 2.1), (46.5, 49, 2.8), (49, 52, 3.4)):
        w.cyl(y0, y1, r, "shell")
        w.cyl(y0, y0 + 0.6, r + 0.2, "spiral")
    w.gem(0, 50.5, 1.0, "lantern", depth=3.9)
    # 작살촉
    X, Y = g2(w)
    t = tn(Y, 51, 72.5)
    hw = np.where(t < 0.5, 2.6 + 1.0 * np.sin(np.pi * t), 3.6 * ((1 - t) / 0.5) ** 0.9 + 0.3)
    cxl = np.round(0.8 * t)
    leaf = (Y >= 51) & (Y <= 72.5) & (np.abs(X - cxl) <= hw)
    barb = poly([(2.4, 58.5), (3.2, 54.5), (7.8, 49.6)])(X, Y)
    # 파도: 날 왼쪽에서 솟아오른 물마루가 왼쪽으로 넘어가 입술이 아래로 떨어지고, 그 밑은 빈 통(배럴)
    wave = poly([(-2.6, 50.8), (-6.0, 53.2), (-9.0, 55.6), (-10.6, 56.4), (-9.8, 59.4), (-10.6, 62.0), (-12.4, 62.4),
                 (-13.0, 60.0), (-13.0, 56.4), (-15.2, 58.6), (-15.4, 62.6), (-13.2, 65.4), (-9.0, 67.0), (-5.0, 67.4),
                 (-1.5, 68.0), (0.0, 60.0), (0.0, 50.8)])(X, Y)
    blade = leaf | barb | wave
    bevel(w, blade, (1, 2), "prism", cz=BZ)
    barrel = wave & (np.hypot(X + 11.2, Y - 59.6) <= 3.2) & (X > -13.0)
    paint(w, barrel[:, :, None] & (w._Y > 0), "hollow")                                    # 통 속 그늘
    crest = wave & ((Y > 64.2 - (X + 14) * 0.1) | (X < -13.0)) & ~barrel
    paint(w, crest[:, :, None] & (w._Y > 0), "foam")                                       # 볏과 입술의 거품
    paint(w, (leaf & (np.abs(X - cxl) <= 0.6) & (Y > 53) & (Y < 69))[:, :, None] & (w._Y > 0), "deep")
    return w


def venom_spear():
    """독사의 창: 무늬 있는 밝은 초록 독사가 팔각 자루를 계단 나선으로 감아 오르고, 옆모습 머리가 크게 벌린 입으로 날 밑동을 문다. 밝은 강철 크리스, 독빛 날, 굽이마다 독방울."""
    m = {
        "wood": Mat(["#3c2818", "#5a3e26", "#7a5636", "#9a6e46"], "wood", seed=31),
        "snake": Mat(["#2e8a20", "#44aa30", "#64c840", "#94e45a"], "flat", seed=32),
        "mark": Mat(["#0e2a0c", "#163a12", "#1e4a18", "#285c20"], "flat", seed=39),
        "belly": Mat(["#b0a868", "#cec682", "#e4dca0", "#f4eec0"], "flat", seed=33),
        "steel": Mat(["#7a8a80", "#9caca2", "#c0ccc4", "#e6eee8"], "flat", seed=34),
        "steel_d": Mat(["#4e5c54", "#5e6c64", "#6e7c74", "#7e8c84"], "flat", seed=42),
        "toxic": Mat(["#3a8a10", "#5cb81c", "#8ae030", "#c8ff70"], "flat", seed=38),
        "venom": Mat(["#1e5a00", "#5ab800", "#a8f040", "#eaffc0"], "pulse", glow=True, seed=35),
        "eye": Mat(["#c08a00", "#f0b800", "#ffe040", "#fff6a0"], "flat", seed=36),
        "fang": Mat(["#d0c8b4", "#e4dece", "#f4f0e6", "#ffffff"], "flat", seed=37),
        "mouth": Mat(["#6a1a2a", "#902a40", "#b43c56", "#d0566e"], "flat", seed=40),
        "wrap": Mat(["#141a10", "#222c1a", "#323e26", "#445234"], "grip", seed=41),
    }
    w = Weapon(m, grip_y=15, kind="spear", seed=131)
    octshaft(w, 3, 48, 2.0, 2.0, "wood")
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Z) <= 0.4 + Y * 0.6) & (Y <= 3.5), "steel")
    grip_wrap(w, 9, 20, 2.3, "wrap", "steel")
    # 몸통: 꼬리부터 자루를 계단 나선으로 두 바퀴 감아 오른다 (토막마다 등의 마름모 무늬, 아랫줄은 연한 배)
    segs = sqhelix(w, 21, 46, 3.0, 2.0, 3.2, 2.6, "snake", start=2)
    for f, (x0, x1, y0, y1, z0, z1) in segs:
        xm, zm, ym = (x0 + x1) / 2, (z0 + z1) / 2, (y0 + y1) / 2
        if f in (0, 2):
            w.fill(lambda X, Y, Z: (np.abs(X - xm) + np.abs(Y - ym - 0.3) <= 1.6) & (Z >= z0) & (Z <= z1), "mark")
        else:
            w.fill(lambda X, Y, Z: (np.abs(Z - zm) + np.abs(Y - ym - 0.3) <= 1.6) & (X >= x0) & (X <= x1), "mark")
        w.box(x0, x1, y0, y0 + 0.5, z0, z1, "belly")
    X, Y = g2(w)
    # 굽이치는 날 (밝은 강철, 독이 밴 날, 가운데 어두운 홈)
    tt = tn(Y, 49, 72.5)
    cxf = np.round(2.4 * np.sin(tt * 3 * math.pi) * (1 - 0.45 * tt))
    hwf = 4.0 * (1 - tt) ** 0.6 + 0.4
    kris = (Y >= 49) & (Y <= 72.5) & (np.abs(X - cxf) <= hwf)
    d = bevel(w, kris, (1, 2), "steel", cz=BZ)
    paint(w, (kris & (d == 1) & (Y > 53))[:, :, None] & (w._Y > 0), "toxic")
    paint(w, (kris & (np.abs(X - cxf) <= 0.6) & (Y > 52) & (Y < 68))[:, :, None] & (w._Y > 0), "steel_d")
    # 머리 옆모습 (주둥이는 왼쪽 위): 위턱과 아래턱 사이로 날 밑동을 문다
    head = poly([(8.6, 47.6), (8.6, 51.6), (6.2, 54.4), (3.0, 55.4), (-1.8, 54.8), (-2.4, 53.2), (3.2, 52.0),
                 (4.2, 50.8), (-1.6, 50.0), (-1.8, 48.2), (2.8, 46.6), (6.4, 45.6)])(X, Y)
    jaw = head & (Y < 50.6) & (X < 6.5)
    put(w, head, 2.0, "snake")
    put(w, jaw, 2.0, "belly")
    put(w, head & (X > 5.0) & (Y > 50.5) & (Y < 52.0), 2.5, "mark")                    # 눈 뒤 줄무늬
    put(w, (np.abs(X - 4.0) <= 1.0) & (Y >= 51.0) & (Y <= 53.0), 2.5, "eye")          # 눈
    put(w, (np.abs(X - 4.0) <= 0.3) & (Y >= 51.0) & (Y <= 53.0), 3.0, "mark")         # 세로 동공
    put(w, (X >= 3.0) & (X <= 4.6) & (Y >= 50.2) & (Y <= 51.2), 2.0, "mouth")         # 입꼬리
    put(w, (np.abs(X + 1.0) <= 0.6) & (Y >= 50.4) & (Y <= 52.6), 1.5, "fang")         # 위 송곳니
    put(w, (np.abs(X - 1.2) <= 0.6) & (Y >= 50.4) & (Y <= 52.2), 1.5, "fang")
    # 목: 나선 꼭대기(오른쪽 면)에서 머리 뒤로
    w.box(2.0, 6.0, 43.0, 47.0, -1.5, 1.5, "snake")
    w.box(2.0, 6.0, 43.0, 43.5, -1.5, 1.5, "belly")
    # 굽이 바깥에서 매달린 독방울 (가는 목 + 둥근 방울)
    for yy, s in ((56.5, -1), (60.6, 1)):
        t0 = (yy - 49) / 23.5
        x = round(2.4 * math.sin(t0 * 3 * math.pi) * (1 - 0.45 * t0)) + s * (4.0 * (1 - t0) ** 0.6 + 0.4) - s * 0.5
        x = math.floor(x) + 0.5
        drop = (np.abs(X - x) <= 0.6) & (Y <= yy) & (Y >= yy - 2.5)
        drop |= np.hypot(X - x, (Y - (yy - 3.6)) * 1.1) <= 1.45
        put(w, drop, 1, "venom")
    return w


def blood_scythe():
    """피의 낫: 꺾인 자루와 가운데 손잡이(니브)의 농사용 낫 꼴, 두꺼운 쇠등(5) -> 핏빛 몸(3) -> 벼린 날(2), 넓게 파인 피 홈, 날에 맺힌 핏방울."""
    m = {
        "snath": Mat(["#4e2c1c", "#724228", "#965a38", "#b8764e"], "wood", seed=41),
        "iron": Mat(["#1c181e", "#302a32", "#4a424c", "#6a606c"], "metal", seed=42),
        "blade": Mat(["#5a0c16", "#861a26", "#b02c36", "#d4504c"], "metal", seed=43),
        "groove": Mat(["#c02030", "#e03040", "#f05050", "#ff8080"], "flat", seed=44),
        "edge": Mat(["#9a8a90", "#c0b6be", "#e4dee6", "#ffffff"], "metal", seed=45),
        "wrap": Mat(["#2a0c10", "#46161c", "#64222a", "#80303a"], "grip", seed=46),
        "blood": Mat(["#5a0008", "#a00010", "#e02030", "#ff8080"], "pulse", glow=True, seed=47),
    }
    sx = 10.0
    w = Weapon(m, grip_y=16, grip_x=sx + 1, kind="scythe", seed=141)
    # 꺾인 자루: 토막마다 한 칸씩
    for (y0, y1, cx) in ((1, 12, sx), (12, 36, sx + 1), (36, 50, sx), (50, 62, sx - 1)):
        w.cyl(y0, y1, 1.7, "snath", cx=cx)
    w.cyl(0, 3, 2.1, "iron", cx=sx)
    grip_wrap(w, 10, 21, 2.2, "wrap", "iron", cx=sx + 1)
    # 가운데 손잡이(니브): 쇠고리 + 옆으로 뻗은 나무 손잡이 + 끝 마디
    w.cyl(37, 40.5, 2.3, "iron", cx=sx)
    w.box(sx - 7, sx, 38, 40, -1, 1, "snath")
    w.box(sx - 9, sx - 6, 37, 41, -1.5, 1.5, "snath")
    w.box(sx - 6, sx - 5, 37.5, 40.5, -1.5, 1.5, "iron")
    # 날을 잡는 쇠고리
    w.cyl(56, 63, 2.4, "iron", cx=sx - 1)
    # 넓고 긴 날
    A = dict(cx=sx, cy=40, rx=32, ry=22, a0=80, a1=170)
    t, d = arcf(w, **A)
    tc = np.clip(t, 0, 1)
    wd = 9.5 * (1 - tc) ** 0.6 + 0.4
    ok = (t <= 1) & (d >= 0) & (d <= wd)
    slab(w, ok & (d < 1.6), 0, 5, "iron")
    slab(w, ok & (d >= 1.6) & (d < wd - 1.6), 1, 4, "blade")
    slab(w, ok & (d >= wd - 1.6) & (d >= 1.6), 1, 3, "edge")
    # 넓은 피 홈 (몸보다 한 칸씩 얇게 파이고 밝은 붉은색)
    gr = ok & (d >= 2.4) & (d <= 4.4) & (tc > 0.04) & (tc < 0.6)
    w.grid[gr[:, :, None] & (w._Z >= 0)] = 0
    slab(w, gr, 2, 3, "groove")
    # 날 아래로 맺힌 핏방울 (붙은 목 + 둥근 방울)
    X, Y = g2(w)
    for tt, ln in ((0.3, 1.5), (0.55, 2.5)):
        x, y = arc_pt(**A, t=tt, depth=9.5 * (1 - tt) ** 0.6 + 0.4 - 0.4)
        slab(w, drop2d(X, Y, x, y, ln, 1.4), 1, 3, "blood")
    return w


def spirit_scythe():
    """영혼의 낫: 크기가 다른 등뼈 마디(뒤로 꺾인 가시돌기) 자루, 주둥이 긴 늑대 두개골(영혼빛 한쪽 눈), 고른 이빨이 박힌 턱뼈 낫날, 영혼 리본."""
    m = {
        "bone": Mat(["#a0967c", "#c4baa0", "#ddd4bc", "#f0eada"], "flat", seed=51),
        "bone_s": Mat(["#6e6656", "#8a8270", "#a49c86", "#bcb49e"], "flat", seed=52),
        "skull": Mat(["#c4bca6", "#dcd5c2", "#eee9dc", "#fffcf2"], "flat", seed=53),
        "dark": Mat(["#0c0e14", "#161a22", "#20262e", "#2a3038"], "flat", seed=54),
        "soul": Mat(["#0a6a7a", "#30c0d0", "#90f4ff", "#ffffff"], "pulse", glow=True, seed=55),
        "cloth": Mat(["#3a6888", "#5088aa", "#6ea6c6", "#9cc8e0"], "flat", seed=56),
        "wrap": Mat(["#2a2420", "#403630", "#584a40", "#6e5e50"], "grip", seed=57),
    }
    sx = 10.0
    w = Weapon(m, grip_y=15, grip_x=sx, kind="scythe", seed=151)
    # 척수 심
    w.box(sx - 1, sx + 1, 0, 56, -1, 1, "bone_s")
    # 등뼈 마디: 아래(허리뼈)는 크고 위(목뼈)로 갈수록 작다, 마디마다 뒤(+X)로 꺾여 내려가는 가시돌기
    verts = [(0.0, 3, 3), (23.0, 3, 3), (27.5, 3, 3), (32.0, 3, 2.5), (36.0, 2, 2.5), (40.0, 2, 2.5), (44.0, 2, 2), (47.5, 2, 2)]
    for i, (y, hw, h) in enumerate(verts):
        w.box(sx - hw, sx + hw, y, y + h, -hw, hw, "bone")
        if y > 20:
            w.box(sx + hw, sx + hw + 2, y + h - 1.5, y + h, -0.5, 0.5, "bone")
            w.box(sx + hw + 2, sx + hw + 4 - (i > 4), y + h - 2.5, y + h - 1, -0.5, 0.5, "bone")
    grip_wrap(w, 7, 20, 1.9, "wrap", "bone_s", cx=sx)
    # 영혼 리본 (목에서 흩날림)
    w.box(sx - 2.5, sx + 2.5, 51, 53, -2.5, 2.5, "cloth")
    w.tube([(sx + 2, 52, 0.5), (sx + 6.5, 48, 0.5), (sx + 5.5, 42, 0.5), (sx + 7.0, 38.5, 0.5)], 0.9, "cloth")
    w.tube([(sx + 2, 52, -0.5), (sx + 9.0, 50, -0.5), (sx + 10.5, 45.5, -0.5)], 0.9, "cloth")
    # 늑대 두개골 (주둥이는 -X): 둥근 머리통, 긴 위턱, 조금 벌어진 아래턱, 큰 귀
    w.box(sx - 2.5, sx + 3.5, 54, 63, -3, 3, "skull")
    w.box(sx - 1.5, sx + 4.5, 55, 62, -3.5, 3.5, "skull")
    w.fill(lambda X, Y, Z: (X <= sx - 2) & (X >= sx - 12) & (Y >= 56) & (Y <= 60.5 - np.floor((sx - 2 - X) / 3))
           & (np.abs(Z) <= 2.5), "skull")
    w.box(sx - 4.5, sx - 0.5, 60.5, 62.5, -3.2, 3.2, "skull")                         # 눈두덩
    w.box(sx - 10.5, sx - 1, 52.5, 54.5, -2.0, 2.0, "skull")                          # 아래턱 (조금 벌어짐)
    w.box(sx - 11.5, sx - 10.5, 54.5, 56.0, -2.0, 2.0, "skull")                       # 위 송곳니
    w.box(sx - 7.5, sx - 6.5, 55.0, 56.0, -2.0, 2.0, "skull")                         # 어금니
    w.box(sx - 10.5, sx - 9.5, 54.5, 55.5, -1.5, 1.5, "skull")                        # 아래 송곳니
    w.box(sx - 12.6, sx - 11.0, 58.5, 60.0, -1.0, 1.0, "dark")                        # 코
    ear = poly([(sx - 1.0, 62.0), (sx + 4.0, 62.0), (sx + 3.0, 70.0)])
    w.fill(lambda X, Y, Z: ear(X, Y) & (np.abs(Z) >= 0.8) & (np.abs(Z) <= 3.0), "skull")
    w.fill(lambda X, Y, Z: ear(X, Y) & (X > sx + 0.5) & (Y < 66) & (np.abs(Z) >= 2.0) & (np.abs(Z) <= 3.0), "bone_s")
    # 눈구멍 (옆면), 영혼빛 눈은 앞면에만
    Xs, Ys, Zs = w._X, w._Y, w._Z
    paint(w, (np.abs(Xs - (sx - 2.5)) <= 1.6) & (Ys >= 58) & (Ys <= 60.5) & (np.abs(Zs) >= 2.0), "dark")
    paint(w, (np.abs(Xs - (sx - 2.5)) <= 1.0) & (Ys >= 58.5) & (Ys <= 60) & (Zs >= 2.0), "soul")
    # 턱뼈 낫날: 짧게 휜 갈고리, 등은 두껍고, 안쪽에 고른 이빨
    A = dict(cx=sx - 8, cy=46, rx=16, ry=12, a0=100, a1=210)
    t, d = arcf(w, **A)
    tc = np.clip(t, 0, 1)
    wd = 5.0 * (1 - tc) ** 0.6 + 0.6
    ok = (t <= 1) & (d >= 0) & (d <= wd)
    slab(w, ok & (d < 1.6), 0, 5, "bone_s")
    slab(w, ok & (d >= 1.6), 1, 4, "bone")
    ph = np.mod(tc * 8, 1)
    teeth = (t <= 1) & (tc > 0.06) & (tc < 0.8) & (d > wd) & (d < wd + 2.6 * (1 - ph) * (1 - tc * 0.6)) & (ph < 0.8)
    slab(w, teeth, 1, 3, "skull")
    return w


# ─────────────────────────── rift ───────────────────────────

def frost_spear():
    """빙창: 녹지 않는 얼음 장창. 다이아몬드 단면 촉, 아래로 늘어진 고드름 깃(샹들리에), 길고 뾰족한 고드름 꼬리."""
    m = {
        "ice": Mat(["#4a7aa8", "#7ab4e0", "#b0e0fa", "#ecfbff"], "crystal", seed=61),
        "ice_d": Mat(["#1e3e70", "#2e5c9c", "#4a86c4", "#74b2e4"], "crystal", seed=62),
        "core": Mat(["#2a6ad8", "#5ab0ff", "#b0e8ff", "#ffffff"], "flow", glow=True, seed=63),
        "steel": Mat(["#28324a", "#3a4866", "#56688a", "#7a8cb0"], "metal", seed=64),
        "snow": Mat(["#b0c0d0", "#d4e0ec", "#eef4fa", "#ffffff"], "flat", seed=65),
        "wrap": Mat(["#c0ccd8", "#d8e2ec", "#eaf0f6", "#ffffff"], "grip", seed=66),
    }
    w = Weapon(m, grip_y=19, kind="spear", seed=161)
    # 길고 뾰족한 고드름 꼬리 (가운데 빛 심지)
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Z) <= 0.3 + Y * 0.3) & (Y <= 11), "ice")
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Z) <= 0.3 + Y * 0.3) & (Y <= 11) & (X < 0), "ice_d")
    w.cyl(10.5, 12.5, 2.4, "steel")
    octshaft(w, 12, 46, 1.8, 1.8, "steel")
    grip_wrap(w, 14, 24, 2.1, "wrap", "steel")
    # 자루 앞뒤의 빛나는 서리 룬 줄
    w.fill(lambda X, Y, Z: (np.abs(X) <= 0.6) & (Y >= 28) & (Y <= 38) & (np.abs(Z) >= 1.0) & (np.abs(Z) <= 2.2), "core")
    # 서리 낀 깃 + 아래로 늘어진 고드름 다섯
    w.cyl(43, 47, 3.0, "snow")
    w.cyl(42.5, 43.5, 3.3, "steel")
    for (x, z, ln) in ((3.0, 0.0, 9.0), (-3.0, 0.0, 7.0), (0.0, 3.0, 5.5), (0.0, -3.0, 6.0), (2.0, 2.2, 4.0), (-2.0, -2.2, 4.0)):
        y1 = 43 - ln
        w.fill(lambda X, Y, Z, x=x, z=z, y1=y1: (Y >= y1) & (Y <= 43.5) &
               (np.abs(X - x) + np.abs(Z - z) <= 0.4 + (Y - y1) * 1.6 / (43.5 - y1) + 0.2), "ice" if x >= 0 else "ice_d")
    # 긴 결정 촉: 다이아몬드 단면 (왼쪽 면 어둡게, 오른쪽 면 밝게)
    def hw(Y):
        t = tn(Y, 46, 72.5)
        return np.where(t < 0.22, 2.6 + 8.0 * t, 4.4 * ((1 - t) / 0.78) ** 0.9 + 0.3)
    crystal = lambda X, Y, Z: (Y >= 46) & (Y <= 72.5) & (np.abs(X) / hw(Y) + np.abs(Z) / (hw(Y) * 0.55 + 0.3) <= 1)
    w.fill(lambda X, Y, Z: crystal(X, Y, Z) & (X < 0), "ice_d")
    w.fill(lambda X, Y, Z: crystal(X, Y, Z) & (X > 0), "ice")
    w.fill(lambda X, Y, Z: crystal(X, Y, Z) & (np.abs(X) <= 0.6) & (Y >= 49) & (Y <= 66), "core")
    return w


def abyss_scythe():
    """심연의 낫: 자루 끝에서 위로 솟아 왼쪽으로 넘어가 아래로 내리찍는 넓은 검은 갈고리 날(보라 빛 날), 끝은 점점 작아지는 조각 셋으로 흩어진다."""
    m = {
        "obsid": Mat(["#2e2244", "#42345e", "#5a4a7a", "#76669a"], "metal", seed=71),
        "void": Mat(["#2c1e48", "#3a2a5c", "#4a3872", "#5c488a"], "flat", seed=72),
        "edge": Mat(["#3a0a6a", "#8a2ae0", "#d080ff", "#ffffff"], "flow", glow=True, seed=73),
        "amethyst": Mat(["#4a2a80", "#7a4ac0", "#a87ae0", "#dcc4ff"], "crystal", seed=74),
        "grip": Mat(["#120a1a", "#22142e", "#341e46", "#4a2c62"], "grip", seed=75),
        "rune": Mat(["#4a0a8a", "#9a3aff", "#e0a0ff", "#ffffff"], "pulse", glow=True, seed=76),
    }
    sx = 11.0
    w = Weapon(m, grip_y=16, grip_x=sx, kind="scythe", seed=171)
    octshaft(w, 2, 60, 1.9, 1.9, "obsid", cx=sx)
    w.fill(lambda X, Y, Z: (np.abs(X - sx) + np.abs(Z) <= 0.4 + Y * 0.6) & (Y <= 3), "amethyst")
    grip_wrap(w, 10, 22, 2.2, "grip", "amethyst", cx=sx)
    # 자루의 룬: 앞뒤로 박힌 큰 마름모 셋
    for yc in (30.0, 38.0, 46.0):
        mk = (np.abs(w._X - sx) / 1.3 + np.abs(w._Y - yc) / 2.6 <= 1) & (np.abs(w._Z) > 1.0) & (w.grid > 0)
        w.grid[mk] = w._id("rune")
    # 자수정 무리 (갈고리 뿌리 뒤)
    for (tx, ty, tz) in ((15.5, 64, 1.5), (15.0, 60.0, -2.0)):
        w.tube([(sx + 1, 58, 0), (tx, ty, tz)], lambda t: 1.8 - 1.0 * t, "amethyst")
    # 갈고리 날: 등(오른쪽 위 바깥) 5복셀, 몸 3복셀, 안쪽 빛 날 2복셀
    A = dict(cx=-1.0, cy=52, rx=15.0, ry=16.0, a0=10, a1=222)
    t, d = arcf(w, **A)
    tc = np.clip(t, 0, 1)
    wd = np.where(tc < 0.5, 7.0 + 2.6 * np.sin(np.pi * np.minimum(1, tc * 1.8)), 8.6 * np.clip((0.74 - tc) / 0.24, 0, 1) ** 0.8 + 0.4)
    ok = (t <= 0.74) & (d >= 0) & (d <= wd)
    slab(w, ok & (d < 1.6), 0, 5, "obsid")
    slab(w, ok & (d >= 1.6) & (d < wd - 1.5), 1, 4, "void")
    slab(w, ok & (d >= wd - 1.5) & (d >= 1.6), 1, 3, "edge")
    # 흩어지는 조각 셋: 점점 작아지고, 틈은 고르다
    X, Y = g2(w)
    for tt, s in ((0.80, 2.8), (0.87, 2.1), (0.93, 1.4)):
        px, py = arc_pt(**A, t=tt, depth=2.6)
        a = math.radians(A["a0"] + (A["a1"] - A["a0"]) * tt)
        tx, ty = -math.sin(a), math.cos(a)
        u = (X - px) * tx + (Y - py) * ty
        v = (X - px) * ty - (Y - py) * tx
        k = np.abs(u) / (s * 1.25) + np.abs(v) / s
        slab(w, k <= 1, 1, 4, "void")
        slab(w, (k <= 1) & (k >= 0.5), 1, 4, "edge")
    return w


# ─────────────────────────── boss ───────────────────────────

def void_reaper():
    """공허의 대낫: 앞뒤로 강착원반을 두른 블랙홀 머리, 왼쪽으로 크게 휜 별밤 날(빛 심지)과 오른쪽 아래로 꺾인 반대날, 밝은 수정 가시, 수정 깃 장식."""
    m = {
        "iron": Mat(["#2a2240", "#3e345c", "#564a7a", "#72669a"], "metal", seed=81),
        "night": Mat(["#4a2a9a", "#6440c0", "#8458e0", "#ffffff"], "sparkle", glow=True, seed=82),
        "edge": Mat(["#6a3aa0", "#b890f0", "#e8d8ff", "#ffffff"], "flow", glow=True, seed=83),
        "vcore": Mat(["#8a2ad0", "#c060ff", "#f0b0ff", "#ffffff"], "pulse", glow=True, seed=88),
        "hole": Mat(["#000000", "#020104", "#05030a", "#0a0614"], "flat", seed=84),
        "disk": Mat(["#c04a90", "#ff80c0", "#ffd0f0", "#ffffff"], "flow", glow=True, seed=85),
        "grip": Mat(["#0e0814", "#1c1028", "#2a1a3a", "#3c2850"], "grip", seed=86),
        "thorn": Mat(["#7a5ab8", "#a88ae0", "#d0bcf8", "#f6f0ff"], "crystal", seed=87),
    }
    sx = 5.0
    hy = 62.0
    w = Weapon(m, grip_y=16, grip_x=sx, kind="scythe", seed=181)
    X, Y = g2(w)
    w.box(sx - 2, sx + 2, 6, 58, -2, 2, "iron")                               # 네모나게 벼린 쇠 자루
    # 꼬리: 밝은 수정 창날
    for (y0, y1, r) in ((0, 2.5, 0.5), (2.5, 4.5, 1.0), (4.5, 7, 1.5)):          # 계단진 수정 꼬리
        w.box(sx - r, sx + r, y0, y1, -r, r, "thorn")
    band(w, 6, 7.5, 2.5, "iron", cx=sx)
    w.box(sx - 2.5, sx + 2.5, 10, 22, -2.5, 2.5, "grip")
    for y in (9, 22):
        band(w, y, y + 1, 3.0, "thorn", cx=sx)
    # 자루 장식: 수정 띠 둘 + 사이의 빛 홈
    for y in (27, 39):
        band(w, y, y + 1.5, 2.5, "thorn", cx=sx)
    for zz in (1.5, -1.5):
        w.box(sx - 0.5, sx + 0.5, 30, 37, zz - 0.5, zz + 0.5, "edge")
    # 깃: 넓은 받침 + 수정 테
    band(w, 50, 54, 3.0, "iron", cx=sx)
    band(w, 54, 55.5, 3.5, "thorn", cx=sx)
    # 큰 날 (왼쪽): 등 5 -> 별밤 몸 3 -> 빛 날 2, 가운데 빛 심지
    A = dict(cx=sx + 2, cy=42, rx=29, ry=21, a0=100, a1=178)
    t, d = arcf(w, **A)
    tc = np.clip(t, 0, 1)
    wd = 12.5 * (1 - tc) ** 0.55 + 0.4
    ok = (t <= 1) & (d >= 0) & (d <= wd)
    slab(w, ok & (d < 1.8), 0, 5, "iron")
    slab(w, ok & (d >= 1.8) & (d < wd - 1.6), 1, 4, "night")
    slab(w, ok & (d >= wd - 1.6) & (d >= 1.8), 1, 3, "edge")
    slab(w, ok & (np.abs(d - wd * 0.5) <= 0.7) & (tc > 0.12) & (tc < 0.6), 1, 4, "vcore")
    # 등의 밝은 수정 가시
    for tt, ln in ((0.36, 8.0),):
        x, y = arc_pt(**A, t=tt, depth=0.5)
        a = math.radians(A["a0"] + (A["a1"] - A["a0"]) * tt)
        tip = (x + math.cos(a) * ln - 3.0, y + math.sin(a) * ln)
        slab(w, poly([(x - 2.6, y - 1.5), (x + 2.6, y - 0.6), tip])(X, Y), 1, 4, "thorn")
    # 반대날 (오른쪽 아래로 꺾임): 뚜렷이 떨어진 두 번째 날
    B = dict(cx=sx + 1, cy=50, rx=13, ry=13, a0=62, a1=-50)
    tb, db = arcf(w, **B)
    tbc = np.clip(tb, 0, 1)
    wb = 6.5 * (1 - tbc) ** 0.6 + 0.4
    okb = (tb <= 1) & (db >= 0) & (db <= wb)
    slab(w, okb & (db < 1.6), 0, 5, "iron")
    slab(w, okb & (db >= 1.6) & (db < wb - 1.4), 1, 4, "night")
    slab(w, okb & (db >= wb - 1.4) & (db >= 1.6), 1, 3, "edge")
    # 블랙홀(둥근 모서리 덩이) + 강착원반 (아래 반은 앞, 위 반은 뒤로 지나간다)
    e = np.hypot((X - sx) / 10.0, (Y - hy) / 4.2)
    ring = (e >= 0.58) & (e <= 1.0)
    behind = (Y > hy) & (np.abs(X - sx) <= 4.0)
    slab(w, ring & ~behind, 3, 5, "disk")
    slab(w, ring & behind, -5, -3, "disk")
    w.box(sx - 3.5, sx + 3.5, hy - 2.5, hy + 2.5, -3, 3, "hole")
    w.box(sx - 2.5, sx + 2.5, hy - 3.5, hy + 3.5, -3, 3, "hole")
    # 꼭대기 수정 가시
    for (y0, y1, r) in ((65, 68, 1.5), (68, 72, 0.5)):
        w.box(sx - r, sx + r, y0, y1, -r, r, "thorn")
    w.set_aura(["#2a0050", "#6a10c0", "#c050ff", "#f6d8ff"], "void", size=0.65, focus=["disk", "vcore"])
    return w


def heavens_spear():
    """천둥의 창: 넓적한 은빛 장창 촉, 촉 밑동 뒤에 선 평평한 금빛 후광, 크게 펼친 금 날개 받침, 후광에서 비스듬히 튀는 번개 둘."""
    m = {
        "silver": Mat(["#a0a8bc", "#c4cadc", "#e4e8f4", "#ffffff"], "metal", seed=91),
        "silver_d": Mat(["#5a6278", "#727a92", "#8c94aa", "#a6aec2"], "metal", seed=97),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff4b0"], "metal", seed=92),
        "gold_d": Mat(["#4a300a", "#7a5414", "#a8781e", "#c8962e"], "metal", seed=99),
        "halo": Mat(["#c09020", "#e8c040", "#fff080", "#ffffff"], "flat", seed=98),
        "core": Mat(["#2a4aff", "#5a9aff", "#b0e0ff", "#ffffff"], "flow", glow=True, seed=93),
        "bolt": Mat(["#a07a00", "#ffd020", "#fff080", "#ffffff"], "pulse", glow=True, seed=94),
        "shaft": Mat(["#b0b4c4", "#d0d4e0", "#e8eaf2", "#fafbff"], "metal", seed=95),
        "grip": Mat(["#14183a", "#22285a", "#343c80", "#4a54a0"], "grip", seed=96),
    }
    w = Weapon(m, grip_y=18, kind="spear", seed=191)
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Z) <= 0.5 + Y * 0.5) & (Y <= 6), "gold")
    band(w, 5, 7, 2.5, "gold")
    octshaft(w, 6, 38, 2.1, 1.7, "shaft")
    grip_wrap(w, 12, 24, 2.3, "grip", "gold")
    # 소켓
    w.cyl(33, 38, 2.4, "gold")
    band(w, 37, 39, 3.0, "gold_d")
    X, Y = g2(w)
    # 평평한 후광 (촉 밑동 뒤, 앞을 본다)
    hy = 45.0
    rr = np.hypot(X, Y - hy)
    put(w, (rr >= 5.6) & (rr <= 7.4), 0.6, "halo", cz=-4.0)
    # 크게 펼친 금 날개: 밑동에서 바깥 위로 쓸어 올리고, 아래 가장자리에 깃 끝 넷
    wing = poly([(1.5, 37.5), (6.0, 38.0), (8.5, 36.0), (9.5, 39.0), (12.5, 38.0), (12.5, 41.5), (15.5, 41.5),
                 (14.5, 44.5), (17.5, 47.5), (13.0, 47.5), (9.0, 46.0), (5.0, 44.5), (1.5, 44.0)])
    wm = wing(X, Y) | wing(-X, Y)
    put(w, wm, 1.5, "gold", cz=BZ)
    # 넓은 장창 촉 (다이아몬드 단면, 왼쪽 면 어둡게, 가운데 빛 심지)
    def hw(Y):
        t = tn(Y, 38, 72.5)
        return np.where(t < 0.25, 2.8 + 13.6 * t, 6.2 * ((1 - t) / 0.75) ** 0.8 + 0.3)
    lance = lambda X, Y, Z: (Y >= 38) & (Y <= 72.5) & (np.abs(X) / hw(Y) + np.abs(Z) / (hw(Y) * 0.42 + 0.6) <= 1)
    w.fill(lambda X, Y, Z: lance(X, Y, Z) & (X < 0), "silver_d")
    w.fill(lambda X, Y, Z: lance(X, Y, Z) & (X > 0), "silver")
    w.fill(lambda X, Y, Z: lance(X, Y, Z) & (np.abs(X) <= 1.0) & (Y >= 42) & (Y <= 67), "core")
    # 번개 둘: 후광에서 왼쪽 위, 오른쪽 아래로 비스듬히
    def zig(pts, r):
        mk = np.zeros(X.shape, bool)
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            tt = np.clip(((X - ax) * dx + (Y - ay) * dy) / (dx * dx + dy * dy), 0, 1)
            mk |= np.hypot(X - ax - tt * dx, Y - ay - tt * dy) <= r
        return mk
    b1 = zig([(-6.0, 52.5), (-10.5, 54.5), (-9.5, 57.0), (-15.5, 59.5), (-14.5, 61.5), (-20.5, 64.5)], 1.0)
    b2 = zig([(7.5, 42.5), (12.0, 40.0), (10.5, 38.0), (16.0, 35.5), (15.0, 33.5), (20.5, 30.5)], 1.0)
    put(w, b1 | b2, 1, "bolt", cz=-3.0)
    w.set_aura(["#1a2a8a", "#3a6aff", "#8ad0ff", "#ffffff"], "bolt", size=0.6, focus=["core"])
    return w


def abyssal_trident():
    """심해의 삼지창: 미늘 달린 세 갈래(두께 있음), 빛나는 심해 핏줄, 굵게 가지 친 산호, 휘어 내려온 아귀 미끼, 큰 닻 꼬리."""
    m = {
        "abyss": Mat(["#163044", "#22465e", "#305e7a", "#447a96"], "flat", seed=201),
        "abyss_d": Mat(["#0a1824", "#102434", "#183244", "#224256"], "flat", seed=208),
        "vein": Mat(["#004a5a", "#00a0b0", "#40f0e0", "#d0fff8"], "flow", glow=True, seed=202),
        "vein2": Mat(["#00505a", "#109aa0", "#50d8d0", "#c0fff8"], "pulse", glow=True, seed=209),
        "coral": Mat(["#8a2a1a", "#c84a2a", "#f07a48", "#ffb488"], "flat", seed=203),
        "barn": Mat(["#7a8088", "#9aa2a8", "#bcc4c8", "#dce2e4"], "flat", seed=204),
        "lure": Mat(["#a06000", "#ffb000", "#ffe860", "#ffffff"], "pulse", glow=True, seed=205),
        "grip": Mat(["#0a1a1a", "#12302c", "#1c463e", "#285e52"], "grip", seed=206),
        "stalk": Mat(["#1a2018", "#2a3226", "#3c4636", "#525e48"], "flat", seed=207),
    }
    w = Weapon(m, grip_y=19, kind="spear", seed=211)
    octshaft(w, 6, 49, 2.0, 1.8, "abyss")
    grip_wrap(w, 13, 25, 2.3, "grip", "abyss_d")
    X, Y = g2(w)
    # 큰 닻 꼬리: 둥근 팔 + 양 끝의 삽 모양 갈고리 + 고리
    arm = (np.hypot(X / 9.0, (Y - 9.5) / 8.0) <= 1.0) & (np.hypot(X / 7.2, (Y - 9.5) / 6.2) >= 1.0) & (Y <= 8.0)
    fl = poly([(6.4, 5.5), (11.5, 6.0), (10.5, 12.0)])
    put(w, arm | fl(X, Y) | fl(-X, Y), 1.5, "abyss", cz=BZ)
    w.cyl(1.5, 7, 1.8, "abyss")
    # 큰 따개비 둘
    for (x, y, z, r) in ((1.8, 31.0, 0.8, 1.8), (-1.8, 37.0, -0.6, 1.6)):
        w.ball(x, y, z, r, r, r, "barn")
        w.box(x - 0.5, x + 0.5, y - 0.5, y + 0.5, z + r - 1.2, z + r + 0.2, "abyss_d")
    # 굽은 받침 (U) + 세 갈래 (두께 2 -> 4)
    yb = 47.5 + np.round((X / 11.0) ** 2 * 4.5) * 2.0          # 2칸씩 계단진 U
    cross = (np.abs(X) <= 12.8) & (Y >= yb) & (Y <= yb + 3.8)
    outer = np.zeros(X.shape, bool)
    for sg in (1, -1):
        px = sg * (12.0 - 1.5 * np.clip((Y - 62) / 8, 0, 1))
        pw = 2.0 * (1 - np.clip((Y - 64) / 7, 0, 1)) + 0.3
        outer |= (np.abs(X - px) <= pw) & (Y >= 55) & (Y <= 71)
        outer |= poly([(sg * 10.2, 61), (sg * 10.2, 64.5), (sg * 6.2, 59.0)])(X, Y)
        outer |= poly([(sg * 1.8, 61), (sg * 1.8, 64.5), (sg * 5.4, 58.6)])(X, Y)
    cw = np.where(Y > 66, 2.6 * (72.8 - Y) / 6.8, 2.6)
    center = (np.abs(X) <= cw) & (Y >= 48) & (Y <= 72.8)
    put(w, cross | outer, 1.5, "abyss", cz=BZ)                 # 받침과 바깥 갈래: 4복셀 두께
    bevel(w, center, (1, 2, 2), "abyss", cz=BZ)                # 가운데 갈래: 날이 선 단면
    put(w, (np.abs(X) <= 0.6) & (Y >= 50) & (Y <= 68), 2, "vein", cz=BZ)
    for sg in (1, -1):
        put(w, (np.abs(X - sg * 11.9) <= 0.6) & (Y >= 57) & (Y <= 66), 2, "vein2", cz=BZ)
    # 굵게 가지 친 산호 (오른쪽 받침 아래에서): 굵은 줄기 + 뭉툭한 가지 셋
    w.tube([(6.0, 51.0, 2.0), (9.0, 47.0, 2.0), (10.0, 42.5, 2.0)], 1.7, "coral")
    w.tube([(9.0, 47.0, 2.0), (13.0, 47.5, 2.0), (14.5, 51.0, 2.0)], 1.5, "coral")
    w.tube([(9.8, 44.0, 2.0), (13.5, 41.5, 2.0)], 1.4, "coral")
    for (x, y, r) in ((14.5, 51.5, 1.9), (13.8, 41.2, 1.7), (10.0, 41.8, 1.8)):
        w.ball(x, y, 2.0, r, r, r, "coral")
    # 아귀 미끼: 왼쪽 갈래에서 휘어 내려온 짙은 줄기 (굵다 -> 가늘다) + 빛 미끼
    w.tube([(-12.5, 65.0, 0), (-15.5, 67.5, 0), (-18.6, 66.5, 0), (-20.4, 62.0, 0), (-19.6, 57.5, 0)],
           lambda t: 1.5 - 0.7 * t, "stalk")
    w.ball(-19.4, 55.0, 0, 2.2, 2.4, 2.2, "lure")
    w.set_aura(["#002a5a", "#0a6ab0", "#30c8e0", "#c0fff8"], "wave", size=0.6, focus=["vein"])
    return w


# ─────────────────────────── prism ───────────────────────────

def apocalypse_scythe():
    """종말의 낫: 금 등을 두른 검은 결정의 S자 낫, 무지개 결정으로만 된 톱날, 크게 솟은 두 뿔과 꼭대기 창, 붉은 종말의 눈."""
    m = {
        "obsid": Mat(["#08060c", "#16121e", "#262030", "#3a3248"], "metal", seed=221),
        "glass": Mat(["#2a2040", "#3c2e5c", "#54447e", "#7464a2"], "crystal", seed=226),
        "gold": Mat(["#6a4410", "#b07a1c", "#e8b840", "#fff0a0"], "metal", seed=222),
        "core": Mat(["#ffffff"], "rainbow", glow=True, seed=223),
        "grip": Mat(["#2a0a0e", "#441418", "#601e24", "#7e2a32"], "grip", seed=225),
        "horn": Mat(["#4a3a2c", "#8a7458", "#c4ac84", "#f0e2c4"], "metal", seed=227),
        "eye": Mat(["#6a0000", "#d01010", "#ff6040", "#fff0c0"], "pulse", glow=True, seed=228),
    }
    sx = 12.0
    w = Weapon(m, grip_y=16, grip_x=sx, kind="scythe", seed=231)
    X, Y = g2(w)
    octshaft(w, 5, 56, 2.1, 2.1, "obsid", cx=sx)
    for (y0, y1, r) in ((0, 2, 0.5), (2, 4, 1.5), (4, 6, 2.5)):                # 계단진 금 꼬리
        w.box(sx - r, sx + r, y0, y1, -r, r, "gold")
    grip_wrap(w, 10, 22, 2.4, "grip", "gold", cx=sx)
    band(w, 36, 37.5, 2.5, "gold", cx=sx)
    # S자 톱날: 등(위, 금) 5 -> 검은 결정 몸 3 -> 무지개 결정 톱날 2 (무지개는 날에만)
    spine = [(sx - 2, 58.5), (5.0, 62.5), (-3.0, 63.5), (-11.0, 60.5), (-16.0, 54.0), (-17.0, 46.0), (-16.5, 39.5),
             (-19.0, 34.0), (-23.5, 30.5)]
    t, dist, side = pathf(w, spine)
    wd = 9.6 * (1 - t) ** 0.7 + 0.6
    ph = np.mod(t * 6, 1)
    serr = np.where((t > 0.08) & (t < 0.86), 3.2 * (1 - ph), 0)
    inner = side > 0
    body = (inner & (dist <= wd + serr)) | (dist <= 1.0)
    slab(w, body & ((dist < 1.6) | ~inner), 0, 5, "gold")
    slab(w, body & inner & (dist >= 1.6) & (dist <= wd - 1.6), 1, 4, "glass")
    slab(w, body & inner & (dist > wd - 1.6) & (dist >= 1.6), 1, 3, "core")          # 무지개 결정 톱날
    # 머리: 금 테 두른 검은 덩이 + 붉은 눈
    w.box(sx - 3, sx + 3, 54, 63, -3, 3, "obsid")
    w.box(sx - 3.5, sx + 3.5, 53.5, 55.5, -3.5, 3.5, "gold")
    w.box(sx - 3.5, sx + 3.5, 62, 63.5, -3.5, 3.5, "gold")
    w.box(sx - 2, sx + 2, 56.5, 61, -3.5, 3.5, "gold")
    w.box(sx - 1, sx + 1, 57.5, 60, -4, 4, "eye")
    # 크게 솟은 두 뿔 (좌우 대칭: 바깥으로 나가 위로 솟고 끝이 안으로 굽는 계단 뿔, 갈수록 가늘다)
    for s in (1, -1):
        for (x0, x1, y0, y1, hz) in ((3, 6, 59.5, 63.5, 2), (5, 8, 62.5, 66, 2), (7, 9.5, 65, 69, 1.5),
                                     (6, 8.5, 68.5, 71, 1), (4, 6.5, 70, 72, 1)):
            w.box(sx + s * x0 if s > 0 else sx - x1, sx + x1 if s > 0 else sx - x0, y0, y1, -hz, hz, "horn")
    # 꼭대기 창 (검은 날, 금 테)
    for (y0, y1, r) in ((63, 66, 2.5), (66, 69, 1.5), (69, 72, 0.5)):
        w.box(sx - r, sx + r, y0, y1, -min(r, 1.5), min(r, 1.5), "obsid" if r > 1 else "gold")
    w.set_aura("prism", "flame", size=0.5, focus=["core"])
    return w


WEAPONS = {
    "bone_spear": bone_spear,
    "storm_spear": storm_spear,
    "tide_spear": tide_spear,
    "blood_scythe": blood_scythe,
    "venom_spear": venom_spear,
    "spirit_scythe": spirit_scythe,
    "frost_spear": frost_spear,
    "abyss_scythe": abyss_scythe,
    "void_reaper": void_reaper,
    "heavens_spear": heavens_spear,
    "abyssal_trident": abyssal_trident,
    "apocalypse_scythe": apocalypse_scythe,
}

NAMES = {
    "bone_spear": "뼈창",
    "storm_spear": "번개 창",
    "tide_spear": "파도의 창",
    "blood_scythe": "피의 낫",
    "venom_spear": "독사의 창",
    "spirit_scythe": "영혼의 낫",
    "frost_spear": "빙창",
    "abyss_scythe": "심연의 낫",
    "void_reaper": "공허의 대낫",
    "heavens_spear": "천둥의 창",
    "abyssal_trident": "심해의 삼지창",
    "apocalypse_scythe": "종말의 낫",
}

if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids:
        sub = {k: WEAPONS[k] for k in ids}
        preview_sheet(sub, os.path.join(HERE, "preview", "_scratch", "polearms_part.png"), names=NAMES)
    else:
        preview_sheet(WEAPONS, os.path.join(HERE, "preview", "polearms.png"), names=NAMES)
