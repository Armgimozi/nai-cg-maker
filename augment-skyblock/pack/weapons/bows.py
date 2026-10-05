"""
bows: 활 8 자루. 함수 하나가 당김 정도 p (0 평소, 1~3 당김) 를 받아 Weapon 을 돌려준다.

좌표: 활은 세워서, 손잡이(그립)가 -X 로 볼록, 화살은 -X 로 날아가고 시위는 +X 쪽.
      당길수록 시위의 가운데(오늬 자리)가 +X 로 가고, 활 끝이 조금 +X 로 휜다 (세로 크기는 그대로).

손에 든 길이는 키트가 23 단위로 맞추므로, 활마다 다른 것은 높이가 아니라 폭과 실루엣이다:
  사냥꾼  짧고 깊게 휜 통나무 평궁 (D)        바람  깊은 리커브, 끝이 -X 로 말린 소용돌이
  독사    S 자로 꿈틀대는 뱀 몸통              서리  꺾인 마디(갈매기 모양)와 굵은 고드름 가시
  화염    짧고 굵은 합성궁 + 거대한 화로 손잡이   공허  타원 고리 손잡이 + 떠 있는 흑요석 조각
  뇌천궁  손잡이가 아래 1/3 에 있는 비대칭 장궁, 팔은 이어진 번개
  별무리  초승달, 뿔 끝이 시위 너머로 휘어 나감

python3 bows.py            -> preview/bows.png (+ preview/bows_bare.png: 아우라 활을 아우라 없이)
python3 bows.py id1 id2    -> 그 활만 preview/_scratch/bows_<id>.png (네 단계 모두 크게, 아우라 없이)
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, Weapon, preview_sheet  # noqa: E402

AURA = True   # 미리보기에서 아우라를 끄고 무기만 볼 때 False


# ─────────────────────────── 작은 도구 ───────────────────────────

def smooth(pts, n=6):
    """Catmull-Rom 으로 점들을 부드럽게 잇는다."""
    P = [np.array(p, float) for p in pts]
    P = [P[0]] + P + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return [tuple(float(v) for v in p) for p in out]


def flip_y(pts, gy):
    """위 팔(림)을 손잡이 높이 기준으로 뒤집어 아래 팔을 만든다."""
    return [(q[0], 2 * gy - q[1]) + tuple(q[2:]) for q in pts]


def line(w, pts, mat, z=0.5):
    """1 복셀 굵기 선 (시위, 화살대). 세로선은 X 를 복셀 가운데(.5)에 둘 것."""
    return w.tube([(q[0], q[1], z) for q in pts], 0.6, mat)


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


def stroke(w, pts, rad, hd, mat, zc=0.0, cut=None, keep=None):
    """
    XY 평면의 굵은 선. 단면이 네모라 행마다 상자 하나로 합쳐져 요소 수가 적다 (활 팔다리용).
    rad: 반폭, hd: 반두께 — 숫자나 함수(t) (t 0 시작 → 1 끝, numpy 배열을 받음).
    cut: 함수(X, Y) -> bool 이면 그 부분만 칠한다.  keep: 함수(t) -> bool 이면 선을 따라 그 구간만 (끊긴 선).
    """
    P = np.array([(q[0], q[1]) for q in pts], float)
    X2, Y2 = w._X[:, :, 0], w._Y[:, :, 0]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    acc = np.concatenate([[0], np.cumsum(seg)])
    total = acc[-1] or 1.0
    best = np.full(X2.shape, np.inf)
    tmap = np.zeros(X2.shape)
    for i in range(len(P) - 1):
        a, d = P[i], P[i + 1] - P[i]
        L2 = float(d @ d) or 1e-6
        u = np.clip(((X2 - a[0]) * d[0] + (Y2 - a[1]) * d[1]) / L2, 0, 1)
        dist = np.hypot(X2 - a[0] - d[0] * u, Y2 - a[1] - d[1] * u)
        better = dist < best
        best = np.where(better, dist, best)
        tmap = np.where(better, (acc[i] + u * seg[i]) / total, tmap)
    r = rad(tmap) if callable(rad) else rad
    h = np.broadcast_to(np.asarray(hd(tmap) if callable(hd) else hd, float), X2.shape)
    m2 = best <= r
    if cut is not None:
        m2 &= np.asarray(cut(X2, Y2), bool)
    if keep is not None:
        m2 &= np.asarray(keep(tmap), bool)
    m3 = m2[:, :, None] & (np.abs(w._Z - zc) <= h[:, :, None])
    w.grid[m3] = w._id(mat)
    return w


def pack_z(w):
    """
    모델 요소는 16 복셀 경계(Z=0 면)를 넘지 못해 가운데 면에서 둘로 쪼개진다.
    활은 두께가 얇으니 통째로 앞(+Z)으로 몇 복셀 밀어 한 칸(16) 안에 넣는다 → 요소 수가 거의 절반.
    """
    occ = np.where(w.grid.any(axis=(0, 1)))[0]
    lo, hi = int(occ.min()), int(occ.max())
    half = w.D // 2
    if lo < half and hi - lo < 16:
        shift = half - lo
        if hi + shift < w.D:
            w.grid = np.roll(w.grid, shift, axis=2)
    return w


def slab(w, mask, hd, mat, zc=0.0):
    """2D 모양을 앞뒤로 hd 만큼 (zc 중심)."""
    return w.fill(lambda X, Y, Z: np.asarray(mask(X, Y), bool) & (np.abs(Z - zc) <= hd), mat)


def along(pts, t):
    """점 목록을 따라 t(0..1) 위치의 점과 단위 접선."""
    P = np.array([(q[0], q[1]) for q in pts], float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    acc = np.concatenate([[0], np.cumsum(seg)])
    d = t * acc[-1]
    i = int(min(len(seg) - 1, np.searchsorted(acc, d, side="right") - 1))
    f = (d - acc[i]) / (seg[i] or 1)
    p = P[i] + (P[i + 1] - P[i]) * f
    tg = (P[i + 1] - P[i]) / (seg[i] or 1)
    return (float(p[0]), float(p[1])), (float(tg[0]), float(tg[1]))


def field(w, pts):
    """중심선까지의 거리, 선을 따른 위치 t(0..1), 어느 쪽인지(+1 = 진행 방향의 오른쪽) 를 XY 격자로."""
    P = np.array([(q[0], q[1]) for q in pts], float)
    X2, Y2 = w._X[:, :, 0], w._Y[:, :, 0]
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    acc = np.concatenate([[0], np.cumsum(seg)])
    best = np.full(X2.shape, np.inf)
    tmap = np.zeros(X2.shape)
    side = np.zeros(X2.shape)
    for i in range(len(P) - 1):
        a, d = P[i], P[i + 1] - P[i]
        L2 = float(d @ d) or 1e-6
        u = np.clip(((X2 - a[0]) * d[0] + (Y2 - a[1]) * d[1]) / L2, 0, 1)
        dist = np.hypot(X2 - a[0] - d[0] * u, Y2 - a[1] - d[1] * u)
        cr = d[0] * (Y2 - a[1]) - d[1] * (X2 - a[0])
        better = dist < best
        best = np.where(better, dist, best)
        tmap = np.where(better, (acc[i] + u * seg[i]) / acc[-1], tmap)
        side = np.where(better, -np.sign(cr), side)
    return best, tmap, side


def star4(cx, cy, r, inner=0.28):
    """또렷한 네 갈래 별 (꼭짓점 8 개). cx, cy 정수(복셀 경계)면 좌우상하 대칭."""
    pts = []
    for i in range(8):
        a = math.pi / 2 * (i // 2) + (math.pi / 4 if i % 2 else 0)
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return poly(pts)


def star_mask(cx, cy, r, k=0.55):
    """네 갈래 별. cx, cy 는 둘 다 복셀 경계(정수)이거나 둘 다 가운데(.5)여야 모양이 대칭."""
    def m(X, Y):
        return (np.abs(X - cx) ** k + np.abs(Y - cy) ** k) <= r ** k
    return m


def arrowhead(w, hx, ay, ln, mat, slope=0.5, hz=0.5, z=0.5):
    """-X 를 가리키는 삼각 화살촉 (hx 가 뾰족한 끝)."""
    return w.fill(lambda X, Y, Z: (X >= hx) & (X <= hx + ln) & (np.abs(Y - ay) <= (X - hx) * slope + 0.1)
                  & (np.abs(Z - z) <= hz), mat)


def fletching(w, sx, ay, ln, mat, spread=0.35, z=0.5):
    """오늬 쪽 깃: 위아래로 벌어지는 두 장 (사냥꾼, 독사 화살)."""
    return w.fill(lambda X, Y, Z: (X >= sx - ln) & (X <= sx - 1) & (np.abs(Y - ay) >= 0.6)
                  & (np.abs(Y - ay) <= 0.6 + (X - (sx - ln)) * spread) & (np.abs(Z - z) <= 0.5), mat)


# ─────────────────────────── 1. 사냥꾼의 활 (기본) ───────────────────────────

def hunter_bow(p):
    """짧고 깊게 휜 통나무 평궁 하나. 가죽 손잡이, 노끈 매듭, 검은 뿔 고자. 꾸밈 없는 첫 활."""
    m = {
        "wood": Mat(["#3e2613", "#68421f", "#8c5e30", "#ad7f48"], "wood", seed=101),
        "leather": Mat(["#2a1a10", "#4a2f1c", "#6a4428", "#865a36"], "grip", seed=102),
        "twine": Mat(["#6a5a3a", "#94805a", "#b8a47a", "#d6c49a"], "cloth", seed=103),
        "horn": Mat(["#120e0a", "#241c16", "#3a3026", "#524436"], "flat", seed=104),
        "string": Mat(["#d8d0bc", "#e8e2d2", "#f4f0e6", "#fffcf4"], "flat", seed=105),
        "shaft": Mat(["#5a4228", "#86643c", "#a88252", "#c4a06a"], "wood", seed=106),
        "flint": Mat(["#3a3a44", "#4e4e5a", "#62626e", "#787884"], "flat", seed=107),
        "knap": Mat(["#8a8a96", "#b0b0bc", "#d0d0da", "#ececf4"], "flat", seed=109),
        "fletch": Mat(["#6a2018", "#963426", "#bf5034", "#de7448"], "cloth", seed=108),
    }
    gy, gx = 31, -5
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=110)
    k, H = 11.0 + p, 24.0              # 당길수록 끝이 +X 로
    up = [(gx + k * v * v, gy + H * v) for v in np.linspace(0, 1, 14)]
    for s in (1, -1):
        pts = up if s == 1 else flip_y(up, gy)
        # 평궁: 앞뒤(Z)로 넓고 X 로 얇다
        stroke(w, pts, lambda t: 2.0 - 1.0 * t, lambda t: 2.6 - 1.3 * t, "wood")
        nock = [(gx + k * v * v, gy + s * H * v) for v in np.linspace(0.86, 1.05, 4)]
        stroke(w, nock, 1.3, 1.5, "horn")
    # 손잡이 가죽과 노끈 매듭
    w.cyl(26, 36, 2.3, "leather", rz=3.0, cx=gx)
    for y0 in (24.8, 36.0):
        w.cyl(y0, y0 + 1.2, 2.5, "twine", rz=3.2, cx=gx)
    # 시위와 화살
    tsx = math.floor(gx + k) + 0.5
    ay = gy + 6.5
    sx = tsx + p * 3.5
    line(w, [(tsx, gy + H - 1.5), (sx, ay), (tsx, gy - H + 1.5)], "string")
    if p > 0:
        hx = sx - 28
        line(w, [(sx, ay), (hx + 3, ay)], "shaft")
        arrowhead(w, hx, ay, 5, "knap", slope=0.55, hz=1)        # 뗀석기 촉: 밝은 날, 어두운 속
        arrowhead(w, hx + 2.2, ay, 2.8, "flint", slope=0.45, hz=1.1)
        fletching(w, sx, ay, 7, "fletch", 0.3)
    return pack_z(w)


# ─────────────────────────── 2. 바람의 활 (섬) ───────────────────────────

def wind_bow(p):
    """자작나무 리커브. 팔이 시위 쪽으로 나왔다가 끝에서 -X 로 말려 소용돌이가 된다. 리본 둘이 위아래로 날린다."""
    m = {
        "birch": Mat(["#b4aa8c", "#d2caae", "#e4dec8", "#f6f2e4"], "wood", seed=201),
        "bark": Mat(["#1e1e1e", "#2a2826", "#36332f", "#423e38"], "flat", seed=202),
        "wrap": Mat(["#1a222c", "#28343f", "#3a4a58", "#4e6070"], "grip", seed=203),
        "ribbon": Mat(["#0a6a6a", "#12908a", "#24b8aa", "#5ee0cc"], "cloth", seed=211),
        "feather": Mat(["#9aa8b8", "#c6d2de", "#e6eef6", "#ffffff"], "cloth", seed=204),
        "quill": Mat(["#1e4a78", "#3a78b0", "#68a8dc", "#a6d4f8"], "flat", seed=205),
        "silver": Mat(["#4a5260", "#8a94a4", "#c4ccd8", "#f0f4fa"], "metal", seed=206),
        "stone": Mat(["#1a8a90", "#3ad0c8", "#90ffe8", "#ffffff"], "pulse", glow=True, seed=207),
        "string": Mat(["#a8b8c4", "#c4d2dc", "#dce6ee", "#eef6fa"], "flat", seed=208),
        "shaft": Mat(["#8a8270", "#b4ac94", "#d4ccb2", "#ece6d0"], "wood", seed=209),
    }
    gy, gx = 32, -4
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=210)
    bx = float(p)
    # 손잡이 → 시위 쪽으로 깊게 → 끝에서 뒤(-X)로 말려 소용돌이
    base = [(gx, 32), (gx + 0.6, 39), (-1.4, 45), (2.6, 49.5), (6.4, 53), (7.4, 56.6), (6.0, 59.8),
            (3.0, 61.0), (0.6, 59.6), (0.4, 57.0), (2.4, 56.2)]
    up = smooth([(x + bx * min(1.0, max(0.0, (y - 40) / 13)), y) for x, y in base], 4)
    rad = lambda t: np.where(t < 0.5, 1.95 - 0.35 * t / 0.5, 1.6 - 0.75 * (t - 0.5) / 0.5)
    hd = lambda t: 1.7 - 0.6 * t
    ys_up = np.array([q[1] for q in up[:14]])
    xs_up = np.array([q[0] for q in up[:14]])
    for s in (1, -1):
        pts = up if s == 1 else flip_y(up, gy)
        stroke(w, pts, rad, hd, "birch")
        # 자작나무 껍질: 앞면에만, 팔의 등 쪽 절반에 짧은 검은 줄
        for yy in (40.5, 46.5):
            cy = gy + s * (yy - gy)
            xc = float(np.interp(yy, ys_up, xs_up))
            w.fill(lambda X, Y, Z, cy=cy, xc=xc: (w.grid == w._id("birch")) & (np.abs(Y - cy) <= 0.55)
                   & (Z > 0) & (X < xc + 0.6), "bark")
    # 손잡이: 짙은 감은 끈 + 은 고리 + 작은 바람돌
    w.cyl(27, 37, 2.2, "wrap", rz=2.4, cx=gx)
    for y0 in (26, 37):
        w.cyl(y0, y0 + 1, 2.4, "silver", rz=2.6, cx=gx)
    w.box(gx - 2.9, gx - 1.1, 31.1, 32.9, -1, 1, "stone")
    # 리본 둘: 위 리본은 바람을 타고 위로, 아래 리본은 아래로 (끝에 깃털)
    rib_up = smooth([(gx - 1.5, 38), (gx - 3.5, 42), (gx - 6.5, 43.5), (gx - 9, 42.5), (gx - 12, 46)], 4)
    stroke(w, rib_up, lambda t: 1.05 - 0.45 * t, 0.5, "ribbon", zc=0.5)
    rib_dn = smooth([(gx - 1.5, 26), (gx - 4, 23), (gx - 4.2, 19.5), (gx - 6.8, 16.5), (gx - 7.4, 13)], 4)
    stroke(w, rib_dn, lambda t: 1.05 - 0.3 * t, 0.5, "ribbon", zc=-0.5)
    ex, ey = rib_dn[-1]
    stroke(w, [(ex, ey), (ex - 3.2, ey - 7.5)], lambda t: 0.5 + 1.6 * np.sin(np.pi * np.clip(t * 1.15, 0, 1)) ** 0.7,
           0.5, "feather", zc=-0.5)
    stroke(w, [(ex, ey), (ex - 2.4, ey - 5.6)], 0.6, 0.5, "quill", zc=-0.5)
    w.ball(ex, ey, -0.5, 1.0, 1.0, 1.0, "silver")
    # 시위: 리커브의 가장 볼록한 곳에 걸린다
    tx = 8.5 + bx
    ay = 38.5
    sx = tx + p * 3.5
    line(w, [(tx, 55.5), (sx, ay), (tx, 2 * gy - 55.5)], "string")
    if p > 0:
        hx = sx - 29
        line(w, [(sx, ay), (hx + 3, ay)], "shaft")
        arrowhead(w, hx, ay, 4, "silver", slope=0.45)
        # 큰 흰 깃 (뒤로 길게 누운 깃)
        w.fill(lambda X, Y, Z: (X >= sx - 10) & (X <= sx - 1) & (np.abs(Y - ay) >= 0.6)
               & (np.abs(Y - ay) <= 0.6 + np.minimum((X - (sx - 10)) * 0.45, 2.2)) & (np.abs(Z - 0.5) <= 0.5), "feather")
    return pack_z(w)


# ─────────────────────────── 3. 독사의 활 (섬) ───────────────────────────

def venom_bow(p):
    """활대가 통째로 독사. 몸은 S 자로 꿈틀, 위 끝은 입을 벌린 머리(송곳니에 독 한 방울), 아래 끝은 말린 꼬리."""
    m = {
        "scale": Mat(["#1c4a22", "#2a6a30", "#4c9642", "#5aa84c"], "scale", seed=301),
        "band": Mat(["#0e2412", "#14301a", "#1a3a20", "#204426"], "flat", seed=302),
        "mouth": Mat(["#4a0e18", "#7a1a2a", "#a02a3a", "#c04454"], "flat", seed=304),
        "fang": Mat(["#c8c0b0", "#e0d8ca", "#f0ece2", "#ffffff"], "flat", seed=305),
        "eye": Mat(["#c09000", "#f0c800", "#ffe040", "#ffffa0"], "flat", seed=306),
        "venom": Mat(["#3a8a10", "#6ad020", "#a8ff50", "#eaffb0"], "pulse", glow=True, seed=307),
        "wrap": Mat(["#1a120c", "#30221a", "#463226", "#5c4434"], "grip", seed=308),
        "string": Mat(["#6a7a58", "#86967a", "#a0b090", "#bccaa8"], "flat", seed=309),
        "shaft": Mat(["#2a2418", "#4a4030", "#6a5c44", "#88785a"], "wood", seed=310),
    }
    gy, gx = 30, -4
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=311)
    k = 14.0 + 1.2 * p

    def cx(s):  # s = -1 (꼬리) .. 0.9 (목). 손잡이는 곧고 팔마다 S 자 한 번
        env = min(1.0, abs(s) * 3)
        return gx + k * s * s + 3.0 * math.sin(2 * math.pi * s / 0.9) * env

    ss = np.linspace(-0.98, 0.9, 64)
    body = [(cx(s), gy + 26 * s) for s in ss]
    body = [(body[0][0] + 1.0, body[0][1] - 2.4), (body[0][0] + 2.6, body[0][1] - 1.2)] + body   # 꼬리 끝이 말림

    def rad(t):  # t 0 꼬리 끝 → 1 목
        s = -1 + 1.9 * t
        return np.where(s < 0, 0.6 + 1.5 * np.clip(1 + s, 0, 1) ** 0.6, 2.1 - 0.2 * s)

    stroke(w, body, rad, lambda t: rad(t) * 0.95, "scale")
    # 등의 어두운 마디 무늬 (몇 개만, 굵게)
    for s0 in (-0.72, -0.42, 0.42, 0.66):
        i = int(np.argmin(np.abs(ss - s0))) + 2
        t = i / (len(body) - 1)
        stroke(w, body[i:i + 2], float(rad(t)) + 0.2, float(rad(t)) + 0.2, "band")
    # 손잡이 가죽
    w.cyl(25, 35, 2.4, "wrap", rz=2.4, cx=gx)
    # 머리 (옆모습): -X 를 보고 입을 크게 벌림. 턱도 비늘색
    nx, ny = cx(0.9), gy + 26 * 0.9
    skull = poly([(nx + 2.2, ny - 0.5), (nx + 2.8, ny + 3.5), (nx + 1.0, ny + 6.0), (nx - 3.0, ny + 6.6),
                  (nx - 7.6, ny + 5.4), (nx - 8.2, ny + 4.0), (nx - 3.5, ny + 3.2), (nx - 0.4, ny + 1.5)])
    jaw = poly([(nx + 1.6, ny - 1.0), (nx - 0.2, ny + 0.9), (nx - 6.6, ny - 1.4), (nx - 7.0, ny - 2.6),
                (nx - 1.0, ny - 2.8)])
    mouth = poly([(nx + 0.6, ny + 0.4), (nx - 7.0, ny + 4.2), (nx - 6.4, ny - 1.2)])
    slab(w, mouth, 1.2, "mouth")
    slab(w, skull, 2.2, "scale")
    slab(w, jaw, 1.6, "scale")
    fx = math.floor(nx - 6.8) + 0.5                     # 송곳니 (복셀 가운데)
    for z in (1.0, -1.0):
        line(w, [(fx, ny + 3.8), (fx, ny + 1.6)], "fang", z=z)
    w.box(fx - 0.6, fx + 0.6, ny + 0.2, ny + 1.6, 0.0, 1.0, "venom")   # 송곳니 끝에 붙은 독 한 방울
    ex0, ey0 = math.floor(nx - 3.4), math.floor(ny + 3.6)            # 눈 2x2
    for z in (1.5, -1.5):
        w.box(ex0 + 0.1, ex0 + 1.9, ey0 + 0.1, ey0 + 1.9, z - 0.6, z + 0.6, "eye")
    # 시위 (목과 꼬리 사이)
    top = (math.floor(cx(0.8) + 1.6) + 0.5, gy + 26 * 0.8)
    bot = (math.floor(cx(-0.9) + 1.0) + 0.5, gy - 26 * 0.9)
    ay = gy + 6.5
    sx = max(top[0], bot[0]) + p * 3.6
    line(w, [top, (sx, ay), bot], "string")
    if p > 0:
        hx = sx - 30
        line(w, [(sx, ay), (hx + 3, ay)], "shaft")
        arrowhead(w, hx, ay, 5, "fang", slope=0.5, hz=1)
        arrowhead(w, hx, ay, 1.6, "venom", slope=0.5, hz=1.2)        # 촉 끝에 독이 묻었다
        fletching(w, sx, ay, 6, "band", 0.4)
    return pack_z(w)


# ─────────────────────────── 4. 서리 활 ───────────────────────────

def frost_bow(p):
    """꺾인 얼음 마디로 이어진 활. 등에서 굵은 고드름 두 개씩, 끝은 얼음 결정, 손잡이 위아래에 서리 룬."""
    m = {
        "ice": Mat(["#7ab4dc", "#9ccce8", "#bce0f4", "#e4f6ff"], "flat", seed=401),
        "deep": Mat(["#1c3e6e", "#285488", "#36689e", "#4a7cb4"], "flat", seed=402),
        "crys": Mat(["#6aa8d8", "#a4d8f4", "#d4f0ff", "#ffffff"], "crystal", seed=408),
        "steel": Mat(["#36465a", "#647c96", "#9cb2c8", "#d8e6f4"], "metal", seed=403),
        "wrap": Mat(["#141e30", "#22344e", "#34506e", "#4c6c8e"], "grip", seed=404),
        "rune": Mat(["#30a8e0", "#62d4ff", "#b0f0ff", "#ffffff"], "pulse", glow=True, seed=405),
        "string": Mat(["#8ac4e4", "#a8d8f2", "#c4e8fa", "#e0f6ff"], "flat", seed=406),
        "shaft": Mat(["#4a5a6a", "#74889a", "#9cb0c2", "#c4d6e6"], "metal", seed=407),
    }
    gy, gx = 33, -5
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=412)
    bx = float(p)
    joints = [(gx, 38), (gx + 0.5, 45), (-1.0 + 0.4 * bx, 52), (3.5 + bx, 57.5), (5.5 + bx, 60.5)]

    def fy(f, s):   # 아래 팔: 마스크를 Y 로 뒤집는다
        return f if s == 1 else (lambda X, Y: f(X, 2 * gy - Y))

    for s in (1, -1):
        J = [(x, gy + s * (y - gy)) for (x, y) in joints]
        for i in range(4):
            stroke(w, J[i:i + 2], 2.1 - 0.3 * i, 1.9 - 0.25 * i, "deep" if i % 2 else "ice")
        # 굵은 고드름 두 개 (등 쪽, 끝을 향해 기움): 앞면은 밝고 뒷면은 어둡다
        for (t0, bw, ln, lean) in ((0.16, 2.6, 9.0, 3.5), (0.55, 2.1, 6.5, 3.0)):
            P, T = along(joints, t0)
            nx, ny = -T[1], T[0]
            apex = (P[0] + nx * ln + T[0] * lean, P[1] + ny * ln + T[1] * lean)
            msk = poly([(P[0] - T[0] * bw, P[1] - T[1] * bw), (P[0] + T[0] * bw, P[1] + T[1] * bw), apex])
            slab(w, fy(msk, s), 1.0, "deep")
            w.fill(lambda X, Y, Z, f=fy(msk, s): f(X, Y) & (Z > 0) & (Z <= 1.0), "ice")
        # 이음매 강철 고리
        for (x, y) in J[1:3]:
            w.box(x - 2.2, x + 2.2, y - 0.8, y + 0.8, -2.2, 2.2, "steel")
        # 끝 결정: 정수 좌표라 당겨도 모양이 같다
        px = 6 + p
        tip = poly([(px - 2, 59), (px + 2, 59), (px + 1, 63), (px - 0.5, 66)])
        slab(w, fy(tip, s), 1.0, "crys")
    # 손잡이 몸체: 서리강철 + 감은 천 + 룬
    w.box(gx - 2.6, gx + 2.0, 22, 44, -2.0, 2.0, "steel")
    w.cyl(28, 38, 2.6, "wrap", rz=2.6, cx=gx - 0.3)
    for y in (25, 41):
        w.fill(lambda X, Y, Z, y=y: (np.abs(X - (gx - 0.3)) + np.abs(Y - y) <= 1.8) & (np.abs(Z) <= 2.6), "rune")
    # 시위와 화살
    tx = 6.5 + bx
    ay = gy + 6.5
    sx = tx + p * 4.0
    line(w, [(tx, 60.5), (sx, ay), (tx, 2 * gy - 60.5)], "string")
    if p > 0:
        hx = sx - 30
        line(w, [(sx, ay), (hx + 5, ay)], "shaft")
        diamond = poly([(hx, ay), (hx + 4, ay + 2.4), (hx + 7, ay), (hx + 4, ay - 2.4)])   # 얼음 결정 촉
        slab(w, diamond, 1.0, "deep", zc=0.5)
        w.fill(lambda X, Y, Z: diamond(X, Y) & (Z > 0.5) & (Z <= 1.5), "ice")
        # 얼음 조각 깃: 위아래로 뾰족한 결정
        for sg in (1, -1):
            slab(w, poly([(sx - 1, ay + sg * 0.6), (sx - 7, ay + sg * 0.6), (sx - 1.5, ay + sg * 3.6)]), 0.5, "ice", zc=0.5)
    return pack_z(w)


# ─────────────────────────── 5. 화염 활 ───────────────────────────

def flame_bow(p):
    """짧고 굵은 무쇠 합성궁. 손잡이 뒤가 거대한 화로 몸체이고, 그 등에서 세 갈래 불길이 솟는다. 팔 배에는 용암 홈."""
    m = {
        "iron": Mat(["#101012", "#1c1d21", "#2c2e34", "#5c626e"], "metal", seed=501),
        "fire_o": Mat(["#8a1606", "#c42a0a", "#e8460e", "#ff6a1a"], "flat", seed=502),
        "fire_i": Mat(["#e88a10", "#ffb020", "#ffd040", "#fff090"], "flat", seed=508),
        "magma": Mat(["#7a1200", "#e04a08", "#ffa020", "#fff2a0"], "fire", glow=True, seed=503),
        "wrap": Mat(["#200808", "#3e1010", "#5a1a16", "#782620"], "grip", seed=504),
        "string": Mat(["#7a3418", "#9a4a24", "#b45e30", "#cc7444"], "flat", seed=505),
        "shaft": Mat(["#7a6a58", "#a08c74", "#c0aa8e", "#dcc8aa"], "wood", seed=506),
        "tip": Mat(["#a83e10", "#e87a20", "#ffb040", "#ffe08a"], "metal", seed=507),
    }
    gy, gx = 32, -4
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=513)
    bx = float(p)
    # 짧고 굵은 팔: 화로 몸체 위아래 끝에서 시작해 급하게 시위 쪽으로
    up = smooth([(gx + 0.5, 44), (gx + 1.5, 48), (0.5, 51.5), (4.0 + 0.5 * bx, 54), (7.0 + bx, 56)], 4)
    rad = lambda t: 2.6 - 1.2 * t
    for s in (1, -1):
        pts = up if s == 1 else flip_y(up, gy)
        stroke(w, pts, rad, lambda t: 2.3 - 0.9 * t, "iron")
        inner = [(x + float(rad(i / (len(pts) - 1))) - 0.4, y) for i, (x, y) in enumerate(pts)]
        stroke(w, inner[2:-3], 0.7, lambda t: 2.4 - 0.9 * t, "magma")
        w.box(6.0 + bx, 8.0 + bx, gy + s * 24 - 1.0, gy + s * 24 + 1.0, -1.5, 1.5, "tip")   # 달군 고자
    # 화로 몸체: 손잡이 뒤로 넓게 튀어나온 무쇠 방패꼴
    forge = poly([(gx + 2.4, 19), (gx + 2.4, 45), (gx - 2, 47.5), (gx - 7, 43), (gx - 9, 32), (gx - 7, 21), (gx - 2, 16.5)])
    slab(w, forge, 2.4, "iron")
    # 화로 창: 가로 불씨 틈 두 줄
    for y in (22.5, 41.5):
        w.box(gx - 6.6, gx - 1.8, y - 0.9, y + 0.9, -2.6, 2.6, "magma")
    w.cyl(27, 37, 2.6, "wrap", rz=2.8, cx=gx + 0.6)
    # 등에서 솟는 세 갈래 불길 (바깥 빨강, 안쪽 노랑)
    ox, oy = gx - 7.5, 22.0
    flame = [(0, 0), (-3.5, 3), (-6, 8.5), (-5.6, 14), (-9.5, 22.5), (-4.6, 18.6), (-4.4, 24.5), (-5.6, 30.5),
             (-1.4, 24), (-0.8, 27.5), (1.6, 21)]
    outer = [(ox + x, oy + y) for (x, y) in flame]
    cxm, cym = ox - 2.8, oy + 9.0
    inner_f = [(cxm + (x - cxm) * 0.58, cym + (y - cym) * 0.62 - 1.0) for (x, y) in outer]
    slab(w, poly(outer), 1.0, "fire_o")
    slab(w, poly(inner_f), 1.5, "fire_i")
    # 시위와 화살: 화살은 몸체 앞면(+Z)을 지나 촉이 화로 밖으로 나온다
    tx = 7.5 + bx
    ay = gy + 6.0
    sx = tx + p * 3.5
    az = 3.5
    if p == 0:
        line(w, [(tx, 55.5), (tx, 2 * gy - 55.5)], "string")
    else:
        w.tube([(tx, 55.5, 0.5), (sx, ay, az), (tx, 2 * gy - 55.5, 0.5)], 0.6, "string")
        hx = sx - 33
        line(w, [(sx, ay), (hx + 3, ay)], "shaft", z=az)
        arrowhead(w, hx, ay, 5, "iron", slope=0.5, hz=0.5, z=az)       # 검은 무쇠 촉, 끝만 벌겋게
        arrowhead(w, hx, ay, 1.6, "tip", slope=0.5, hz=0.5, z=az)
        slab(w, poly([(hx + 1, ay + 1), (hx + 4.5, ay + 1), (hx + 4, ay + 4), (hx + 2.5, ay + 6), (hx + 1.5, ay + 3)]),
             0.5, "magma", zc=az)
        w.fill(lambda X, Y, Z: (X >= sx - 6) & (X <= sx - 1) & (np.abs(Y - ay) >= 0.6)
               & (np.abs(Y - ay) <= 0.6 + (X - (sx - 6)) * 0.4) & (np.abs(Z - az) <= 0.5), "fire_o")
    return pack_z(w)


# ─────────────────────────── 6. 공허의 활 ───────────────────────────

def void_bow(p):
    """손잡이는 공허가 일렁이는 타원 고리, 팔은 서로 떨어져 떠 있는 흑요석 조각 셋. 시위와 화살도 끊겼다 이어진다."""
    m = {
        "obsid": Mat(["#1a1228", "#2a1e40", "#3a2c58", "#4c3a70"], "stone", seed=601),
        "rim": Mat(["#5a4690", "#7a62b4", "#9a84d4", "#c4b4f0"], "metal", seed=602),
        "void": Mat(["#12042a", "#4a1488", "#9a4ae0", "#f0c4ff"], "flow", glow=True, seed=603),
        "spark": Mat(["#b050f0", "#d080ff", "#f0b8ff", "#ffffff"], "flat", glow=True, seed=604),
        "wrap": Mat(["#08060c", "#16121e", "#262030", "#363044"], "cloth", seed=605),
        "string": Mat(["#8a4ab6", "#a060c8", "#b878dc", "#cc90ec"], "flat", seed=606),
        "purpur": Mat(["#4a2466", "#7a46a0", "#a874cc", "#d4a8f0"], "metal", seed=607),
    }
    gy, gx = 34, -5
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=614)
    bx = float(p)
    # 고리 (타원): 밝은 테두리 + 어두운 흑요석 + 안은 공허
    ring = lambda X, Y: ((X - gx) / 6.0) ** 2 + ((Y - gy) / 11.0) ** 2
    slab(w, lambda X, Y: (ring(X, Y) <= 1.0) & (ring(X, Y) >= 0.5), 1.8, "rim")
    slab(w, lambda X, Y: (ring(X, Y) <= 0.8) & (ring(X, Y) >= 0.58), 1.8, "obsid")
    slab(w, lambda X, Y: ring(X, Y) < 0.5, 0.5, "void")
    w.box(gx - 1.6, gx + 1.6, 27, 41, -1.6, 1.6, "wrap")
    # 떠 있는 팔 조각: 한 곡선을 세 토막으로 (틈은 3~4 칸), 조각마다 밝은 테두리
    arc = smooth([(gx + 1.0, 45.5), (gx + 2.2, 51.0), (-0.6 + 0.3 * bx, 56.0), (3.2 + 0.8 * bx, 60.5),
                  (6.6 + bx, 64.5)], 5)
    gaps = ((0.30, 0.45), (0.64, 0.79))
    solid = lambda t: ~(((t > gaps[0][0]) & (t < gaps[0][1])) | ((t > gaps[1][0]) & (t < gaps[1][1])))
    rad = lambda t: 2.3 - 0.4 * t - 1.0 * np.clip((t - 0.8) / 0.2, 0, 1) ** 1.5
    for pts in (arc, flip_y(arc, gy)):
        stroke(w, pts, rad, lambda t: rad(t) * 0.85, "rim", keep=solid)
        stroke(w, pts, lambda t: rad(t) - 1.0, lambda t: rad(t) * 0.85 + 0.01, "obsid", keep=solid)
    # 고리와 팔 사이의 빛 한 점
    for s in (1, -1):
        w.box(gx - 0.1, gx + 2.1, gy + s * 11.5 - 1, gy + s * 11.5 + 1, -1.2, 1.2, "spark")
    # 시위 (1 복셀, 세 토막씩)
    tx = 6.5 + bx
    ay = gy + 7.5
    sx = tx + p * 4.0
    for (y0, y1) in ((63.5, ay), (2 * gy - 63.5, ay)):
        for (t0, t1) in ((0.0, 0.3), (0.42, 0.62), (0.74, 1.0)):
            line(w, [(tx + (sx - tx) * t0, y0 + (y1 - y0) * t0), (tx + (sx - tx) * t1, y0 + (y1 - y0) * t1)], "string")
    if p > 0:
        hx = sx - 30
        # 화살도 사라졌다 나타나는 중: 대 사이사이가 비었다
        for x0 in np.arange(hx + 4, sx, 5.0):
            line(w, [(x0, ay), (min(sx, x0 + 2.6), ay)], "spark")
        slab(w, poly([(hx, ay), (hx + 5, ay + 2.5), (hx + 3.5, ay), (hx + 5, ay - 2.5)]), 1.0, "purpur")
    return pack_z(w)


# ─────────────────────────── 7. 뇌천궁 (보스) ───────────────────────────

def storm_longbow(p):
    """
    비대칭 장궁 (손잡이가 아래 1/3). 팔은 이어진 번개 한 줄기: 넓은 판이 위로 기울다 짧게 뒤로 꺾이기를 반복,
    가운데에 전류 심지. 금도금 손잡이 몸체, 뒤로 크게 휜 금 뿔, 아래에 폭풍 구슬, 끝은 두 갈래 금 창끝.
    """
    m = {
        "steel": Mat(["#4a5878", "#7486a8", "#a4b4d0", "#dce6f6"], "metal", seed=701),
        "gold": Mat(["#6a4410", "#b07a1c", "#e8b840", "#fff0a0"], "metal", seed=702),
        "volt": Mat(["#1a4ad0", "#3a9aff", "#9ae4ff", "#ffffff"], "flow", glow=True, seed=703),
        "orb": Mat(["#2a5ae0", "#6ab0ff", "#c8ecff", "#ffffff"], "sparkle", glow=True, seed=704),
        "wrap": Mat(["#0c0e18", "#1a1e30", "#2a3048", "#3c4462"], "grip", seed=705),
        "string": Mat(["#6ab8e8", "#90d0f4", "#b8e4fa", "#e0f4ff"], "flat", glow=True, seed=706),
        "shaft": Mat(["#3a3f50", "#5a6278", "#7e88a0", "#a4aec4"], "metal", seed=707),
    }
    gy, gx = 21.5, -5
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=715)
    bx = float(p)
    TOP, BOT = 61.5, 3.0

    def bend(x, y):   # 당길수록 끝쪽이 +X 로
        f = (y - gy) / (TOP - gy) if y > gy else (gy - y) / (gy - BOT)
        return gx + x + round(bx * f * f)   # 정수만큼 밀어 판 모양이 그대로 (요소 수 절약)

    # 번개 팔: 넓은 판(시위 쪽으로 기움)과 짧게 뒤로 꺾이는 이음이 번갈아. 가운데에 이어진 전류 심지
    up_pts = [(0.5, 35), (6.0, 43), (2.0, 45.5), (8.5, 52.5), (4.5, 55), (12.0, TOP)]
    lo_pts = [(0.5, 14), (5.5, 9.5), (1.5, 7.5), (12.0, BOT)]
    tips = []
    for pts, s in ((up_pts, 1), (lo_pts, -1)):
        P = [(bend(x, y), y) for (x, y) in pts]
        stroke(w, P, lambda t: 3.0 - 1.6 * t ** 2.5, 1.6, "steel")
        stroke(w, P[:-1] + [along(P, 0.93)[0]], 0.95, 1.6, "volt")
        tip = P[-1]
        tips.append(tip)
        # 두 갈래 금 창끝
        for (dx, dy) in ((-3.0, 3.6), (1.8, 3.0)):
            stroke(w, [tip, (tip[0] + dx, tip[1] + s * dy)], lambda t: 1.3 - 0.9 * t, 1.0, "gold")
        w.box(tip[0] - 1.6, tip[0] + 1.6, tip[1] - 1.2, tip[1] + 1.2, -1.8, 1.8, "gold")
    # 금도금 손잡이 몸체 + 뒤쪽 전류 홈
    w.box(gx - 3.0, gx + 2.4, 13, 36, -2.2, 2.2, "gold")
    w.box(gx - 4.6, gx - 2.9, 14, 35, -1.2, 1.2, "volt")      # 손잡이 등을 따라 이어진 전류 (아우라가 끊기지 않게)
    w.cyl(17, 26, 2.7, "wrap", rz=2.6, cx=gx - 0.2)
    # 뒤로 크게 휜 금 뿔 (위는 길게, 아래는 짧게)
    stroke(w, smooth([(gx - 2.0, 35.0), (gx - 7.5, 38.5), (gx - 11.5, 44.5), (gx - 12.0, 52.0)], 4),
           lambda t: 2.5 - 2.0 * t, lambda t: 1.8 - 0.8 * t, "gold")
    stroke(w, smooth([(gx - 2.0, 14.5), (gx - 6.5, 11.5), (gx - 9.0, 7.0), (gx - 8.5, 2.0)], 4),
           lambda t: 2.2 - 1.7 * t, lambda t: 1.8 - 0.8 * t, "gold")
    # 폭풍 구슬: 손잡이 위, 금 마름모 틀 (등 쪽으로 튀어나옴)
    ox, oy = gx - 2.0, 31.5
    slab(w, lambda X, Y: np.abs(X - ox) + np.abs(Y - oy) <= 4.4, 2.3, "gold")
    slab(w, lambda X, Y: np.hypot(X - ox, Y - oy) <= 2.4, 2.8, "orb")
    # 시위와 화살
    tx = math.floor(max(tips[0][0], tips[1][0])) + 0.5
    ay = 26.5
    sx = tx + p * 4.0
    line(w, [(tx, TOP), (sx, ay), (tx, BOT)], "string")
    if p > 0:
        hx = sx - 31
        line(w, [(sx, ay), (hx + 4, ay)], "volt")                 # 전류가 감도는 화살대
        arrowhead(w, hx, ay, 5, "gold", slope=0.5, hz=1)
        for sg in (1, -1):                                        # 계단꼴 금 깃
            w.box(sx - 6, sx - 1, ay + sg * 1.5 - 0.5, ay + sg * 1.5 + 0.5, 0, 1, "gold")
            w.box(sx - 3, sx - 1, ay + sg * 2.5 - 0.5, ay + sg * 2.5 + 0.5, 0, 1, "gold")
    if AURA:
        w.set_aura(["#16228a", "#2a66e0", "#5ad0ff", "#eaffff"], "bolt", size=1.25, focus=["volt", "orb"])
    return pack_z(w)


# ─────────────────────────── 8. 별무리 활 (프리즘) ───────────────────────────

def prism_bow(p):
    """밤하늘 초승달 활. 몸통은 별이 반짝이는 남색, 등은 금테, 안쪽 날만 무지개. 뿔 끝은 시위 너머로 휘어 나가고,
    등 뒤로 별 결정이 떠 있다. 시위는 옅은 금빛 한 줄."""
    m = {
        "night": Mat(["#0e0e34", "#1c1c56", "#2e2e80", "#5050b0"], "sparkle", seed=801),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c050", "#fff4b0"], "metal", seed=802),
        "band": Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=803),
        "star": Mat(["#c89a38", "#f0d070", "#fae8a8", "#fff6d8"], "flat", glow=True, seed=804),
        "core": Mat(["#ffffff"] * 4, "flat", glow=True, seed=807),
        "wrap": Mat(["#0e0a24", "#1c163e", "#2c2458", "#3e3474"], "cloth", seed=805),
        "string": Mat(["#f0e0a8", "#f8ecc4", "#fff6dc", "#fffcf0"], "flat", glow=True, seed=806),
    }
    gy, gx = 33, -6
    w = Weapon(m, grip_y=gy, grip_x=gx, kind="bow", seed=816)
    k1 = 12.0 + 0.8 * p
    L = 28.5

    def cx(s):   # 초승달 중심선: 끝 30% 에서 뿔이 +X 로 더 휘어 나간다
        a = abs(s)
        return gx + k1 * a * a + 55.0 * max(0.0, a - 0.7) ** 2

    def hw(s):   # 반폭: 손잡이에서 잘록, 그 위아래로 두툼, 끝은 뾰족
        a = min(1.0, abs(s))
        return (1.8 + 2.3 * math.sin(math.pi * a ** 0.75) * (1 - 0.2 * a)) * (1 - a ** 5) + 0.45

    ss = np.linspace(-1.0, 1.0, 81)
    pts = [(cx(v), gy + L * v) for v in ss]
    dist, tm, side = field(w, pts)
    r = np.vectorize(hw)(tm * 2 - 1)
    body = dist <= r
    dep = np.round(2.2 - 0.9 * np.abs(tm * 2 - 1))[:, :, None]
    # 진행 방향(아래→위)의 오른쪽 = +X = 배(무지개), 왼쪽 = 등(금테)
    lay = [("night", body), ("gold", body & (side < 0) & (dist > r - 1.0)),
           ("band", body & (side > 0) & (dist > r - 1.2) & (np.abs(tm * 2 - 1) < 0.9))]
    for name, msk in lay:
        w.grid[msk[:, :, None] & (np.abs(w._Z) <= dep)] = w._id(name)
    w.cyl(28, 38, 2.6, "wrap", rz=2.9, cx=gx + 0.6)
    # 등 뒤에 떠 있는 별 결정: 금빛 네 갈래 별 + 흰 심 (좌표는 모두 정수)
    for (sx_, sy_, r_) in ((-16, 33, 7.0), (-13, 47, 5.0), (-13, 19, 4.5), (-20, 42, 4.0), (-20, 24, 4.0)):
        w.prism(star4(sx_, sy_, r_), 1.0, "star")
        w.prism(star4(sx_, sy_, r_ * 0.45, 0.5), 1.4, "core")
    # 시위: 뿔 안쪽(s=±0.72)에 걸린다
    ya, yb = gy + 0.72 * L, gy - 0.72 * L
    tx = math.floor(cx(0.72) + hw(0.72) - 0.6) + 0.5
    ay = gy + 6.5
    sx = tx + p * 4.0
    line(w, [(tx, ya), (sx, ay), (tx, yb)], "string")
    if p > 0:
        hx = sx - 28
        line(w, [(sx, ay), (hx + 2, ay)], "string")
        w.prism(star4(hx, ay, 3.5), 1.0, "star")
        w.prism(lambda X, Y: (np.abs(X - hx) < 1) & (np.abs(Y - ay) < 1), 1.4, "core")
    if AURA:
        w.set_aura(["#2a1a8a", "#7a5ae8", "#f0d878", "#ffffff"], "holy", size=0.9, focus=["band", "gold"])
    return pack_z(w)


WEAPONS = {
    "hunter_bow": lambda: [hunter_bow(i) for i in range(4)],
    "wind_bow": lambda: [wind_bow(i) for i in range(4)],
    "venom_bow": lambda: [venom_bow(i) for i in range(4)],
    "frost_bow": lambda: [frost_bow(i) for i in range(4)],
    "flame_bow": lambda: [flame_bow(i) for i in range(4)],
    "void_bow": lambda: [void_bow(i) for i in range(4)],
    "storm_longbow": lambda: [storm_longbow(i) for i in range(4)],
    "prism_bow": lambda: [prism_bow(i) for i in range(4)],
}

NAMES = {
    "hunter_bow": "사냥꾼의 활",
    "wind_bow": "바람의 활",
    "venom_bow": "독사의 활",
    "frost_bow": "서리 활",
    "flame_bow": "화염 활",
    "void_bow": "공허의 활",
    "storm_longbow": "뇌천궁",
    "prism_bow": "별무리 활",
}

AURA_BOWS = ("storm_longbow", "prism_bow")


def _detail(ids):
    """한 자루씩 크게: 인벤토리(아우라 포함), 네 단계 비스듬히(아우라 없이), 정면."""
    global AURA
    from wkit import build_bow, preview
    from mc3d import contact_sheet, render
    scratch = os.path.join(HERE, "preview", "_scratch", "assets", "augsky")
    for wid in ids:
        AURA = True
        inv = preview(build_bow("item/" + wid, scratch, WEAPONS[wid]())[0], 300)[0]
        AURA = False
        states = WEAPONS[wid]()
        for i, st in enumerate(states):
            lo, hi = st.bounds()
            print(wid, i, "X", lo[0], hi[0], "Y", lo[1], hi[1], "Z", lo[2], hi[2])
        models = build_bow("item/" + wid, scratch, states)
        imgs = [inv] + [preview(mm, 300)[1] for mm in models]
        imgs.append(render([(models[0], None)], size=300, yaw=0, pitch=0, bg=(28, 26, 36, 255)))
        labels = ["inv"] + [f"p{i} ({len(mm.elements)})" for i, mm in enumerate(models)] + ["front p0"]
        out = os.path.join(HERE, "preview", "_scratch", f"bows_{wid}.png")
        contact_sheet(imgs, labels, cols=3, cell=300).save(out)
        print(out)
    AURA = True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _detail(sys.argv[1:])
    else:
        print(preview_sheet(WEAPONS, os.path.join(HERE, "preview", "bows.png"), names=NAMES))
        # 아우라 활은 미리보기 세 칸 모두 아우라가 덮으므로, 활만 따로 한 장 더
        AURA = False
        bare = {k: WEAPONS[k] for k in AURA_BOWS}
        print(preview_sheet(bare, os.path.join(HERE, "preview", "bows_bare.png"),
                            names={k: NAMES[k] + " (아우라 없이)" for k in AURA_BOWS},
                            scratch=os.path.join(HERE, "preview", "_scratch", "bare", "assets", "augsky")))
        AURA = True
