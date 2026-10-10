"""
magic: 마법봉과 지팡이 12 자루.

python3 magic.py            -> preview/magic.png
python3 magic.py id1 id2    -> 그 무기만 preview/_scratch/magic_part.png (크게 보기용)

설계 좌표: 손잡이 아래, 끝이 위(+Y), 앞면 +Z. X/Z 는 가운데 선(복셀 사이)에서 잰 거리.

지팡이마다 자루 생김새부터 다르게 만든다 (고리-감개-고리 틀을 되풀이하지 않는다):
  빛     곧은 상아 자루 + 홈 새긴 맨손잡이 + 목에 묶은 넓은 띠, 머리는 해 원반
  숲     밝은 참나무 가지 + 옹이 사이 손잡이, 머리는 떡잎 두 장과 튤립
  구름   바람 띠가 나선으로 감긴 자루(감개 없음), 머리는 높게 쌓인 뭉게구름
  바다   휜 유목 + 밧줄 매듭, 머리는 소라 껍데기에서 솟는 파도
  별     끝이 갈고리로 굽은 자루, 갈고리에 매달린 초승달 등불(밤하늘 구슬 + 금별)
  서리   쇠 밑동에서 자라 오르는 고드름 자루, 한쪽으로 기운 얼음 왕관
  화염   갈색 자루가 쇠 갈비 우리로 벌어지고, 그 안에 큰 불길
  세계수 비틀려 굵어지는 가지가 네 갈래로 갈라져 씨앗을 감싼다
  창세   남흑빛 자루 위 시계 고리 + 비스듬한 궤도 두 개 + 무지개 핵
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, Weapon, preview_sheet  # noqa: E402


# ─────────────────────────── 작은 도구 ───────────────────────────

def mats(**kw):
    """재료 순서(= 아틀라스 칸 배치)를 정해서 돌려준다.
    칸 경계에서 오른쪽/아래 칸 색이 번져 보일 수 있으므로(예전 분홍 실선, 붉은 점),
    이웃한 칸끼리 색이 비슷하도록 배치를 고른다. 고정 재료는 4칸씩, 움직이는 재료는 2칸씩 한 줄."""
    def avg(mt):
        return np.array([sum(c[i] for c in mt.ramp) / 4 for i in range(3)])

    def arrange(items, cols):
        if len(items) < 3:
            return items
        col = [avg(mt) for _, mt in items]
        n = len(items)

        def cost(order):
            s = 0.0
            for i in range(n):
                if (i + 1) % cols and i + 1 < n:
                    s += np.linalg.norm(col[order[i]] - col[order[i + 1]])
                if i + cols < n:
                    s += np.linalg.norm(col[order[i]] - col[order[i + cols]])
            return s
        best = list(range(n))
        bc = cost(best)
        improved = True
        while improved:
            improved = False
            for i in range(n):
                for j in range(i + 1, n):
                    o = best[:]
                    o[i], o[j] = o[j], o[i]
                    c = cost(o)
                    if c < bc - 1e-6:
                        best, bc, improved = o, c, True
        return [items[k] for k in best]
    items = list(kw.items())
    static = arrange([kv for kv in items if not kv[1].animated], 4)
    anim = arrange([kv for kv in items if kv[1].animated], 2)
    return dict(static + anim)


def rho(X, Z, cx=0.0, cz=0.0):
    return np.hypot(X - cx, Z - cz)


def helix(y0, y1, r, pitch, phase=0.0, cx=0.0, cz=0.0, step=1.0):
    """세로 나선 위의 점들."""
    pts = []
    y = y0
    while y <= y1 + 1e-6:
        a = phase + 2 * math.pi * (y - y0) / pitch
        pts.append((cx + r * math.cos(a), y, cz + r * math.sin(a)))
        y += step
    return pts


def q2(fn, ax="xy", s=2):
    """fn(X, Y, Z) 를 s 복셀 격자로 뭉뚱그려 계산한다 (2x2 픽셀처럼 굵직해지고 요소 수가 크게 준다)."""
    def g(X, Y, Z):
        if "x" in ax:
            X = np.floor(X / s) * s + s / 2
        if "y" in ax:
            Y = np.floor(Y / s) * s + s / 2
        if "z" in ax:
            Z = np.floor(Z / s) * s + s / 2
        return fn(X, Y, Z)
    return g


def line(w, pts, r, mat, rz=None, square=False, q=None, step=0.5):
    """굵은 선. square=True 면 네모 단면(요소가 적게 합쳐진다), q="xy" 등을 주면 2복셀 격자로.
    r, rz 는 숫자나 함수(t)."""
    pts = np.array(pts, dtype=float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    acc = np.concatenate([[0], np.cumsum(seg)])
    total = acc[-1] or 1
    samples = []
    d = 0.0
    while d <= total + 1e-6:
        j = min(len(seg) - 1, np.searchsorted(acc, d, side="right") - 1)
        f = (d - acc[j]) / (seg[j] or 1)
        p = pts[j] + (pts[j + 1] - pts[j]) * f
        t = d / total
        h = r(t) if callable(r) else r
        hz = h if rz is None else (rz(t) if callable(rz) else rz)
        samples.append((p, max(h, 0.3), max(hz, 0.3)))
        d += step

    def fn(X, Y, Z):
        m = np.zeros(X.shape, bool)
        for p, h, hz in samples:
            if square:
                m |= (np.abs(X - p[0]) <= h) & (np.abs(Y - p[1]) <= h) & (np.abs(Z - p[2]) <= hz)
            else:
                m |= ((X - p[0]) / h) ** 2 + ((Y - p[1]) / h) ** 2 + ((Z - p[2]) / hz) ** 2 <= 1
        return m
    return w.fill(q2(fn, q) if q else fn, mat)


def beam(w, pts, half, mat, hz=None, q=None):
    """네모 단면 굵은 선."""
    return line(w, pts, half, mat, rz=hz, square=True, q=q)


def star_mask(X, Y, cx, cy, R, r, n=5, rot=90.0):
    """곧은 변을 가진 n 각 별 (XY)."""
    a = np.arctan2(Y - cy, X - cx) - math.radians(rot)
    sec = 2 * math.pi / n
    phi = np.abs(((a + sec / 2) % sec) - sec / 2)
    al = math.pi / n
    bound = R * r * math.sin(al) / (r * np.sin(al - phi) + R * np.sin(phi) + 1e-9)
    return np.hypot(X - cx, Y - cy) <= bound


def heart_mask(X, Y, cx, cy, s):
    x = (X - cx) / s
    y = (Y - cy) / s
    return (x * x + y * y - 1) ** 3 - x * x * y ** 3 <= 0


def shard(w, bx, by, ang, L, wd, dark, light, wz=None, bz=0.0, q=None):
    """마름모 단면 결정 하나. (bx, by) 에서 ang 도(위 = 90) 방향으로 L. 왼쪽 면 dark, 오른쪽 면 light."""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)
    wz = wd * 0.75 if wz is None else wz

    def uv(X, Y):
        dx, dy = X - bx, Y - by
        return dx * ux + dy * uy, -dx * uy + dy * ux

    def body(X, Y, Z):
        u, v = uv(X, Y)
        t = np.clip(u / L, 0, 1)
        k = np.where(t < 0.62, 1.0, (1 - t) / 0.38)
        return (u >= 0) & (u <= L) & (np.abs(v) / (wd * k + 0.3) + np.abs(Z - bz) / (wz * k + 0.3) <= 1)
    fd = lambda X, Y, Z: body(X, Y, Z) & (uv(X, Y)[1] >= 0)
    fl = lambda X, Y, Z: body(X, Y, Z) & (uv(X, Y)[1] < 0)
    w.fill(q2(fd, q) if q else fd, dark)
    w.fill(q2(fl, q) if q else fl, light)
    return w


def pixel_mask(rows, x0, ytop):
    """문자열 그림('X' = 칠함)을 앞면 마스크로. 왼쪽 위 복셀 가운데가 (x0, ytop)."""
    pts = [(x0 + c, ytop - r) for r, line in enumerate(rows) for c, ch in enumerate(line) if ch == "X"]

    def fn(X, Y):
        m = np.zeros(X.shape, bool)
        for (x, y) in pts:
            m |= (np.abs(X - x) < 0.1) & (np.abs(Y - y) < 0.1)
        return m
    return fn


# ─────────────────────────── 기본 (basic) ───────────────────────────

def novice_wand():
    """구불구불한 잔가지 막대에 옹이 하나, 끝에 붉은 끈으로 감아 묶은 작은 석영 조각."""
    m = mats(
        bark=Mat(["#4a3220", "#73502e", "#9a7448", "#bc9866"], "wood", seed=101),
        knot=Mat(["#2e1e12", "#4a321c", "#644628", "#7a5834"], "wood", seed=102),
        end=Mat(["#a08058", "#c0a074", "#d8be94", "#ecd8b4"], "flat", seed=103),
        cord=Mat(["#6a2418", "#9a3a26", "#c25a38", "#e08254"], "grip", seed=104),
        q_d=Mat(["#8a8cc0", "#a6aad8", "#c2c8ec", "#dce0f8"], "crystal", seed=105),
        q_l=Mat(["#d4dcf4", "#e8eeff", "#f6f8ff", "#ffffff"], "crystal", seed=106),
        leaf=Mat(["#3e7a28", "#58a034", "#72ba44", "#90d058"], "flat", seed=107),
    )
    w = Weapon(m, grip_y=9, kind="wand", seed=101)
    # 굽은 가지 (관 하나로 — 마디가 어긋난 상자가 아니라 부드럽게 휜다)
    stick = [(0.4, 0, 0), (1.0, 6, 0), (0.0, 12, 0), (-0.8, 17, 0), (0.0, 22, 0), (0.4, 28, 0)]
    w.tube(stick, lambda t: 1.75 - 0.3 * t, "bark")
    w.ball(-1.9, 15.5, 0.3, 1.4, 2.0, 1.4, "knot")                  # 옹이
    w.box(-1, 2, 0, 0.6, -1, 1, "end")                               # 잘린 밑동
    # 잔가지 하나, 끝에 납작한 잎
    w.tube([(0.5, 20, 0), (2.8, 22.5, 0), (4.0, 25.5, 0)], 0.8, "bark")

    def leaf(X, Y, Z):
        u = (X - 4.0) * 0.34 + (Y - 25.5) * 0.94
        v = -(X - 4.0) * 0.94 + (Y - 25.5) * 0.34
        return (u >= 0) & (u <= 5) & (np.abs(v) <= 1.6 * np.sin(np.pi * np.clip(u / 5, 0, 1)) ** 0.7) & (np.abs(Z - 0.5) <= 0.5)
    w.fill(leaf, "leaf")
    # 석영: 끈 안에 박힌 작은 육각 기둥 (9 복셀), 끝이 살짝 기운다
    def quartz(X, Y, Z):
        lean = 0.12 * (Y - 27)
        hw = np.where(Y < 33.5, 1.6, 1.6 * np.clip((37.2 - Y) / 3.7, 0, 1))
        return (Y >= 26) & (Y <= 37) & (np.abs(X - 0.5 - lean) + 0.45 * np.abs(Z) <= hw + 0.45) & (np.abs(Z) <= 1.2)
    w.fill(lambda X, Y, Z: quartz(X, Y, Z) & (X < 0.5 + 0.12 * (Y - 27)), "q_d")
    w.fill(lambda X, Y, Z: quartz(X, Y, Z) & (X >= 0.5 + 0.12 * (Y - 27)), "q_l")
    # 끈: 위아래 두 줄로 감고, 꼬리가 늘어진다
    w.fill(lambda X, Y, Z: (rho(X, Z, 0.4) <= 2.2) & (Y >= 25) & (Y <= 30) & ((np.floor(Y) % 2) == 1), "cord")
    w.fill(lambda X, Y, Z: (rho(X, Z, 0.4) <= 1.9) & (Y >= 25) & (Y <= 30), "cord")
    w.tube([(2.2, 27, 1.5), (3.2, 24, 1.5), (3.0, 21.5, 1.5)], 0.6, "cord")
    return w


def gold_wand():
    """가는 금 막대 끝에 하트 테두리와 장밋빛 수정, 아래엔 분홍 리본."""
    m = {
        "gold": Mat(["#6a4410", "#b07a1c", "#e8b840", "#fff0a0"], "metal", seed=201),
        "rose": Mat(["#8a2a4a", "#d0507a", "#f490b0", "#ffe0ea"], "gem", seed=202),
        "ribbon": Mat(["#8a1e3a", "#c43a5a", "#e66a86", "#ff9ab0"], "cloth", seed=203),
        "grip": Mat(["#c8a0a0", "#dcb8b4", "#ecd0c8", "#f8e6de"], "grip", seed=204),
    }
    w = Weapon(m, grip_y=8, kind="wand", seed=201)
    w.ball(0, 1.5, 0, 2.1, 1.8, 2.1, "gold")          # 둥근 꼭지
    w.cyl(3, 13, 1.6, "grip")
    w.cyl(13, 14.5, 2.1, "gold")
    w.cyl(3, 35, 1.1, "gold")                         # 막대 (2x2)
    w.cyl(3, 3.8, 2.1, "gold")
    w.cyl(24, 25, 1.6, "gold")
    # 하트
    cy, s = 42.0, 6.2
    w.fill(lambda X, Y, Z: heart_mask(X, Y, 0, cy, s) & ~heart_mask(X, Y, 0, cy + 0.6, s * 0.72) & (np.abs(Z) <= 1), "gold")
    w.fill(lambda X, Y, Z: heart_mask(X, Y, 0, cy + 0.6, s * 0.72) & (np.abs(Z) <= 1), "rose")
    w.fill(lambda X, Y, Z: heart_mask(X, Y, 0, cy + 0.9, s * 0.45) & (np.abs(Z) <= 2), "rose")
    # 리본: 고리 둘 + 늘어진 꼬리 둘
    for sx in (1, -1):
        w.tube([(0, 33, 0), (sx * 3.5, 35, 0), (sx * 4.5, 33, 0), (sx * 2.5, 31.5, 0), (0, 33, 0)], 0.9, "ribbon")
        w.tube([(0, 33, 0.5), (sx * 1.5, 30, 0.5), (sx * 2.5, 27, 0.5)], 0.75, "ribbon")
    w.box(-1, 1, 32, 34, -1.5, 1.5, "ribbon")
    return w


CREEPER = [
    "........",
    ".XX..XX.",
    ".XX..XX.",
    "...XX...",
    "..XXXX..",
    "..XXXX..",
    "..X..X..",
    "........",
]


def amethyst_wand():
    """밝은 자작 손잡이 끝에 크리퍼 얼굴의 자수정 블록, 그 위로 바닐라 자수정 무리처럼 키가 다른 결정 넷 (한쪽으로 몰려 자란다)."""
    m = mats(
        handle=Mat(["#7a6a5a", "#a89480", "#c8b6a0", "#e2d4c0"], "wood", seed=306),
        copper=Mat(["#5a2a14", "#9a4e26", "#c87a46", "#e8a878"], "metal", seed=305),
        block=Mat(["#4a2a78", "#6a44a0", "#8a62c0", "#a882d8"], "stone", seed=303),
        face=Mat(["#160a24", "#1e0e30", "#26143c", "#2e1846"], "flat", seed=304),
        am_d=Mat(["#5a2a90", "#7a46b8", "#9a68d4", "#b88ae6"], "crystal", seed=301),
        am_l=Mat(["#a070e0", "#c49af0", "#e2c8ff", "#fbf0ff"], "crystal", seed=302),
    )
    w = Weapon(m, grip_y=10, kind="wand", seed=301)
    w.ball(0, 1.5, 0, 2.2, 1.8, 2.2, "copper")                       # 구리 꼭지
    w.cyl(2, 21, 1.6, "handle")
    w.cyl(17, 21, 2.1, "copper")                                    # 받침 고리
    # 블록을 붙드는 구리 갈퀴 넷
    for sx in (1, -1):
        for sz in (1, -1):
            w.tube([(sx * 1.5, 19, sz * 1.5), (sx * 3.5, 21.5, sz * 3.5), (sx * 3.6, 23.5, sz * 3.6)], 0.75, "copper")
    # 크리퍼 자수정 블록 (8x8x8) — 앞뒤에 얼굴
    w.box(-4, 4, 22, 30, -4, 4, "block")
    face = pixel_mask(CREEPER, -3.5, 29.5)
    w.fill(lambda X, Y, Z: face(X, Y) & (np.abs(Z) > 3) & (np.abs(Z) < 4), "face")
    # 결정 무리: 키 15 / 10 / 7 / 5 — 굵고 짧게, 서로 다른 방향과 깊이
    shard(w, -0.5, 29.5, 100, 15, 3.0, "am_d", "am_l", wz=2.4)
    shard(w, 2.5, 29.5, 68, 10, 2.2, "am_d", "am_l", wz=1.8, bz=-1.0)
    shard(w, -3.0, 29.5, 140, 7, 1.8, "am_d", "am_l", wz=1.5, bz=1.5)
    shard(w, 1.0, 29.5, 95, 5, 1.6, "am_d", "am_l", wz=1.3, bz=2.8)
    return w


# ─────────────────────────── 섬 (island) ───────────────────────────

def holy_staff():
    """곧은 상아 자루 끝에 해 원반: 진한 금 원판과 길고 짧은 빛살 여덟, 가운데 빛나는 흰 결정. 목에 묶은 넓은 푸른 띠."""
    m = mats(
        ivory=Mat(["#b8ae98", "#d8d0bc", "#ece6d8", "#fffcf4"], "metal", seed=401),
        gold=Mat(["#5a3000", "#a06408", "#d89818", "#ffd040"], "metal", seed=402),
        ray=Mat(["#b07810", "#e8b020", "#ffd848", "#fff2a0"], "metal", seed=403),
        crys=Mat(["#c8d8ff", "#eaf0ff", "#ffffff", "#ffffff"], "crystal", glow=True, seed=404),
        sash=Mat(["#102a66", "#1a409a", "#2e5cc8", "#5a88e8"], "cloth", seed=405),
    )
    w = Weapon(m, grip_y=24, kind="staff", seed=401)
    cy = 58.0
    w.fill(lambda X, Y, Z: (rho(X, Z) <= 0.4 + Y * 0.45) & (Y <= 3), "gold")       # 밑 끝
    w.cyl(3, 50, 1.6, "ivory")
    # 손잡이: 감개 없이 홈만 셋
    w.clear(lambda X, Y, Z: (rho(X, Z) > 1.2) & (Y >= 18) & (Y <= 31) & ((np.floor(Y) % 5) == 4))
    # 목: 금 깔때기
    w.fill(lambda X, Y, Z: (rho(X, Z) <= 1.6 + (Y - 44) * 0.45) & (Y >= 44) & (Y <= 51), "gold")

    # 빛살 여덟 (위, 옆은 길게, 대각선은 짧게 / 아래는 목 자리라 뺀다)
    def rays(X, Y, Z):
        a = np.arctan2(Y - cy, X)
        r = np.hypot(X, Y - cy)
        k = np.round(a / (np.pi / 4))
        da = a - k * np.pi / 4
        along, perp = r * np.cos(da), np.abs(r * np.sin(da))
        L = np.where((k.astype(int) % 2) == 0, 15.0, 12.0)
        half = 2.6 * np.clip(1 - (along - 6) / (L - 6), 0, 1)
        return (along >= 6) & (along <= L) & (perp <= half + 0.4) & (Z >= 0) & (Z <= 2) & (k != -2)
    w.fill(q2(rays, "xy"), "ray")
    # 원판 (두께 4) + 밝은 안쪽 고리
    w.fill(q2(lambda X, Y, Z: (np.hypot(X, Y - cy) <= 8.0) & (np.abs(Z) <= 1.6), "xy"), "gold")
    w.fill(q2(lambda X, Y, Z: (np.hypot(X, Y - cy) <= 6.4) & (np.hypot(X, Y - cy) >= 4.6) & (np.abs(Z) <= 2.2), "xy"), "ray")
    # 가운데 흰 결정 (팔면체, 앞뒤로 솟음) — 유일한 빛
    w.fill(lambda X, Y, Z: np.abs(X) + np.abs(Y - cy) + 0.7 * np.abs(Z) <= 4.6, "crys")
    # 넓은 띠: 목에 매듭, 꼬리 두 장이 앞으로 늘어진다 (끝은 V 자로 파임)
    w.cyl(45, 47.5, 2.4, "sash")
    for sx, (x1, y1), (x2, y2) in ((-1, (-2.4, 39), (-3.4, 30)), (1, (2.4, 40.5), (3.2, 33))):
        beam(w, [(sx * 0.8, 46, 2.5), (x1, y1, 2.5), (x2, y2, 2.5)], 1.6, "sash", hz=0.5)
        w.clear(lambda X, Y, Z, x2=x2, y2=y2: (np.abs(X - x2) <= 0.6) & (Y <= y2 + 0.5) & (Y >= y2 - 2.5) & (Z > 1))
    return w


def nature_staff():
    """밝은 참나무 가지(옹이 둘 사이가 손잡이) 끝에 갈라진 떡잎 두 장(참나무 잎 모양)과 분홍 튤립 한 송이."""
    m = mats(
        bark=Mat(["#5e4228", "#8a6640", "#ae885a", "#ccaa7c"], "wood", seed=501),
        knot=Mat(["#3e2a18", "#5a3e24", "#765432", "#8e6a42"], "wood", seed=502),
        leaf=Mat(["#3e8a24", "#58aa30", "#78c840", "#9ce060"], "flat", seed=503),
        leaf2=Mat(["#22581a", "#2e7020", "#3c862a", "#4c9a34"], "flat", seed=504),
        vein=Mat(["#a8d878", "#bce690", "#d0f0a8", "#e4f8c4"], "flat", seed=505),
        petal=Mat(["#c03a78", "#e05a96", "#f484b4", "#ffb4d2"], "cloth", seed=506),
        petal_d=Mat(["#7a1a48", "#9a2a5c", "#b83c70", "#d05086"], "flat", seed=507),
    )
    w = Weapon(m, grip_y=22, kind="staff", seed=501)
    w.tube([(0.5, 0, 0), (-0.3, 12, 0), (0.6, 26, 0), (-0.4, 40, 0), (0.0, 50, 0)], lambda t: 2.1 - 0.5 * t, "bark")
    # 옹이 둘 — 그 사이가 손잡이
    w.ball(1.0, 15, 0.5, 2.4, 2.0, 2.2, "knot")      # 한쪽으로 불거진 옹이
    w.ball(-1.0, 29.5, -0.5, 2.3, 1.8, 2.2, "knot")
    # 자루에 돋은 새싹 잎 하나
    def small_leaf(X, Y, Z):
        u = (X - 1) * 0.8 + (Y - 38) * 0.6
        v = -(X - 1) * 0.6 + (Y - 38) * 0.8
        return (u >= 0) & (u <= 5.5) & (np.abs(v) <= 1.9 * np.sin(np.pi * np.clip(u / 5.5, 0, 1)) ** 0.7) & (np.abs(Z) <= 0.5)
    w.fill(small_leaf, "leaf")

    # 참나무 잎 (갈래진 가장자리, 윗면 밝게, 잎맥)
    def oak(cx, cy, ang, L, wd):
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)

        def uv(X, Y):
            dx, dy = X - cx, Y - cy
            return dx * ux + dy * uy, -dx * uy + dy * ux

        def body(X, Y, Z):
            u, v = uv(X, Y)
            s = np.clip(u / L, 0, 1)
            prof = wd * np.sin(np.pi * np.clip(0.12 + 0.88 * s, 0, 1)) ** 0.6 * (0.62 + 0.38 * np.abs(np.cos(np.pi * s * 3.0)))
            return (u >= 0) & (u <= L) & (np.abs(v) <= prof) & (np.abs(Z) <= 1)
        side = 1 if math.cos(a) < 0 else -1      # 윗변 (위를 보는 쪽)
        w.fill(body, "leaf2")
        w.fill(lambda X, Y, Z: body(X, Y, Z) & (uv(X, Y)[1] * side < 0) | (body(X, Y, Z) & (Z > 0.5) & (uv(X, Y)[1] * side < 1.5)), "leaf")
        w.fill(lambda X, Y, Z: body(X, Y, Z) & (np.abs(uv(X, Y)[1]) <= 0.5) & (uv(X, Y)[0] < L * 0.85) & (Z > 0), "vein")
    oak(-1.0, 50.5, 152, 14, 4.2)
    oak(1.0, 50.5, 30, 12.5, 3.8)
    # 튤립 (꽃줄기 + 세 갈래 꽃잎 컵)
    w.cyl(49, 54, 0.9, "leaf2")
    fy = 54.0

    def tulip(X, Y, Z):
        s = np.clip((Y - fy) / 10.0, 0, 1)
        r = 0.8 + 3.4 * np.sin(np.pi * np.clip(0.15 + 0.75 * s, 0, 1)) ** 0.7
        a = np.arctan2(Z, X)
        top = fy + 8.0 + 2.2 * np.maximum(0, np.cos(3 * a + np.pi / 2))
        return (Y >= fy) & (Y <= top) & (rho(X, Z) <= r)
    w.fill(tulip, "petal")
    w.fill(lambda X, Y, Z: tulip(X, Y, Z) & (Y < fy + 2.5), "petal_d")
    w.clear(lambda X, Y, Z: (rho(X, Z) <= 2.2) & (Y >= fy + 7))   # 컵 속
    w.fill(lambda X, Y, Z: (rho(X, Z) <= 2.2) & (Y >= fy + 6) & (Y < fy + 7), "petal_d")
    return w


def cloud_staff():
    """바람 띠가 나선으로 감긴 하늘색 자루(감개 없음). 위에는 둥근 혹 셋이 솟은 뭉게구름(바닥 평평, 아랫배 짙은 하늘색)과
    떨어져 떠 있는 작은 구름 하나 — 섬 사이를 건너는 디딤 구름. 발끝에도 작은 구름."""
    m = mats(
        pole=Mat(["#7088a8", "#90a8c8", "#b0c8e2", "#cce0f4"], "metal", seed=601),
        wind=Mat(["#2a7ab0", "#3a9ad0", "#5ab8e8", "#8ad4f8"], "flat", seed=602),
        top=Mat(["#f4f8fc", "#fafcff", "#ffffff", "#ffffff"], "flat", seed=604),
        cloud=Mat(["#c4d6ec", "#d4e2f2", "#e2ecf8", "#eef4fc"], "cloth", seed=605),
        belly=Mat(["#5a84cc", "#6a92d4", "#7aa0dc", "#8aaee2"], "cloth", seed=606),
        shade=Mat(["#3a5aa0", "#4868ac", "#5676b8", "#6484c2"], "cloth", seed=607),
    )
    w = Weapon(m, grip_y=22, kind="staff", seed=601)
    w.cyl(2, 52, 1.1, "pole")
    # 바람 띠: 자루를 감아 오르는 굵은 띠 하나
    w.tube(helix(5, 50, 1.9, 16, 0.0), 1.0, "wind")

    def puffs(balls, base):
        """공 여러 개를 겹친 구름, base 아래는 평평하게 자른다 (2복셀 격자로 둥글고 굵직하게)."""
        def fn(X, Y, Z):
            u = np.zeros(X.shape, bool)
            for (cx, cy, r, rz) in balls:
                u |= ((X - cx) / r) ** 2 + ((Y - cy) / r) ** 2 + (Z / rz) ** 2 <= 1
            return u & (Y >= base)
        return q2(fn, "xyz")
    # 큰 구름은 자루 축을 따라 높이 쌓인 뭉게구름 기둥 (옆으로 넓은 망치 머리처럼 보이지 않게),
    # 작은 구름은 오른쪽 아래에 떨어져 떠 있다
    big = puffs([(0, 53.5, 5.6, 4.4), (-3.5, 57, 4.4, 3.8), (3, 59, 5.0, 4.2), (-1, 63.5, 5.0, 4.0), (2.5, 67, 3.8, 3.4)], 50)
    small = puffs([(8.5, 50.5, 2.8, 2.6), (11.5, 51.5, 3.0, 2.8)], 49)
    foot = puffs([(-1.5, 2, 3.0, 3.0), (1.5, 3, 3.4, 3.0)], 0)
    for c, split in ((big, 55), (small, 51), (foot, 2)):
        w.fill(c, "cloud")
        w.fill(lambda X, Y, Z, c=c, s=split: c(X, Y, Z) & (Y < s), "belly")
        w.fill(lambda X, Y, Z, c=c: c(X, Y, Z) & ~c(X, Y - 2, Z), "shade")
        w.fill(lambda X, Y, Z, c=c: c(X, Y, Z) & ~c(X, Y + 2, Z), "top")
    return w


def ocean_staff():
    """휜 유목 자루 끝, 소라 껍데기에서 말려 오르는 파도. 흰 물거품 마루, 파도 속 진주(유일한 빛), 밧줄 매듭 손잡이."""
    m = mats(
        drift=Mat(["#5a5248", "#857a6a", "#a89c88", "#c8bea8"], "wood", seed=701),
        deep=Mat(["#0a2a5a", "#124484", "#1c5ea8", "#2a78c4"], "cloth", seed=702),
        water=Mat(["#1a6aa8", "#2a90c8", "#48b4e0", "#78d4f0"], "cloth", seed=703),
        foam=Mat(["#b0d8ec", "#d4ecf8", "#f0faff", "#ffffff"], "flat", seed=708),
        pearl=Mat(["#c8d0e0", "#e4ecf6", "#f8fcff", "#ffffff"], "gem", glow=True, seed=705),
        shell=Mat(["#d0b494", "#e6ccac", "#f4e2c8", "#fff4e4"], "stone", seed=706),
        band=Mat(["#8a5236", "#a86a46", "#c0845c", "#d49c74"], "flat", seed=709),
        lip=Mat(["#d07080", "#e8909a", "#f8b4b4", "#ffd8d0"], "flat", seed=710),
        rope=Mat(["#1e5a5a", "#2a7a78", "#3e9a96", "#5ab8b0"], "grip", seed=707),
    )
    w = Weapon(m, grip_y=24, kind="staff", seed=701)
    w.tube([(0.3, 0, 0), (0.9, 14, 0), (0.2, 30, 0), (0.6, 42, 0), (0.0, 47, 0)], lambda t: 1.75 - 0.25 * t, "drift")
    # 밧줄 손잡이 + 아래 매듭 덩이와 늘어진 끝
    w.cyl(18, 30, 2.1, "rope", cx=0.5)
    w.ball(0.5, 17.5, 0, 2.8, 1.8, 2.8, "rope")
    w.tube([(2.2, 17, 1.5), (3.2, 13, 1.5), (2.8, 10, 1.5)], 0.75, "rope")
    # 파도: 소라 입에서 오른쪽으로 솟아 왼쪽으로 말려 내려온다 (옆에서도 두툼하게)
    path = [(0, 46, 0), (2.5, 52, 0), (4.5, 58, 0), (5, 63, 0), (3.5, 67, 0), (0.5, 69, 0), (-3, 68.5, 0),
            (-5.5, 66.5, 0), (-6.5, 63.5, 0), (-5.5, 61, 0), (-3.5, 60.5, 0)]
    line(w, path, lambda t: 3.6 - 2.4 * t, "water", rz=lambda t: 3.4 - 1.8 * t, q="xy")
    inner = [(1.0, 52, 0), (2.6, 57, 0), (3.0, 62, 0), (2.0, 65, 0), (0.0, 66.3, 0), (-2.5, 65.8, 0)]
    line(w, inner, lambda t: 1.6 - 0.4 * t, "deep", rz=lambda t: 3.0 - 1.0 * t, q="xy")
    crest = [(6.5, 59, 0), (6.8, 64, 0), (5, 68, 0), (1.5, 70.5, 0), (-2.5, 70.5, 0), (-6, 69, 0), (-8.5, 66, 0), (-9.5, 63, 0)]
    line(w, crest, lambda t: 1.1 + 0.4 * math.sin(math.pi * t), "foam", rz=lambda t: 2.4 - 0.8 * t, q="xy")
    w.ball(-1.5, 63.5, 0, 1.6, 1.6, 1.6, "pearl")
    # 소라: 자루 끝에 가로로 누운 원뿔 (줄무늬 띠, 위로 솟은 혹, 분홍 입이 파도 쪽을 본다)
    sy = 46.0

    def conch(X, Y, Z):
        s = np.clip((X + 12.0) / 12.0, 0, 1)          # 0 = 뾰족한 끝, 1 = 입
        r = 0.7 + 3.6 * s ** 0.8
        return (X >= -12.0) & (X <= 0.5) & (np.hypot(Y - sy, Z) <= r)
    w.fill(q2(conch, "x"), "shell")
    w.fill(lambda X, Y, Z: conch(X, Y, Z) & ((np.floor((X + 12) / 2) % 2) == 1) & (X < -2), "band")
    for (x, h) in ((-8.5, 2.6), (-5, 3.8)):
        w.box(x - 1, x + 1, sy + h - 0.5, sy + h + 1.5, -1, 1, "shell")
    w.fill(lambda X, Y, Z: (X >= -0.5) & (X <= 1.5) & (np.hypot(Y - sy, Z) <= 4.4), "lip")
    w.clear(lambda X, Y, Z: (X >= -2.5) & (X <= 1.5) & (np.hypot(Y - sy, Z) <= 2.3) & (Y < sy + 1))
    return w


def star_staff():
    """끝이 갈고리로 굽은 남빛 자루. 갈고리에 매달린 은 초승달(금별보다 크다)이 반짝이는 밤하늘 구슬을 받치고, 구슬 앞뒤에 굵은 금별."""
    m = mats(
        navy=Mat(["#1e2858", "#2e3c78", "#42549c", "#5c70bc"], "wood", seed=801),
        silver=Mat(["#6a7088", "#a0a8c0", "#d0d6e8", "#ffffff"], "metal", seed=802),
        star=Mat(["#a0701a", "#e0a830", "#f8d860", "#fff6b0"], "metal", seed=803),
        sky=Mat(["#080626", "#181050", "#382c8a", "#ffffff"], "sparkle", glow=True, seed=804),
    )
    w = Weapon(m, grip_y=26, kind="staff", seed=801)
    w.fill(lambda X, Y, Z: (rho(X, Z) <= 0.4 + Y * 0.5) & (Y <= 3), "silver")
    w.cyl(3, 51, 1.6, "navy")
    # 손잡이: 감개 없이 자루가 네모로 불룩해진다
    w.fill(lambda X, Y, Z: (np.maximum(np.abs(X), np.abs(Z)) <= 2.0) & (np.abs(X) + np.abs(Z) <= 3.0) &
           (Y >= 19) & (Y <= 33), "navy")
    # 갈고리
    crook = [(0, 50, 0), (0.3, 55, 0), (2, 59.5, 0), (5.5, 62, 0), (9, 61.5, 0), (11.5, 59, 0), (12.5, 55.5, 0)]
    line(w, crook, 1.7, "navy", q="xy")
    w.box(11, 14, 53, 55, -1.5, 1.5, "silver")
    # 사슬 (고리 둘)
    w.box(12, 13, 50.5, 53, -1, 1, "silver")
    w.box(11.5, 13.5, 51.5, 52.5, -0.5, 0.5, "silver")
    # 초승달 — 아래가 두껍고 뿔이 위로
    mx, my = 13.0, 40.0
    w.fill(q2(lambda X, Y, Z: (np.hypot(X - mx, Y - my) <= 10.0) & (np.hypot(X - mx - 1.2, Y - my - 3.6) >= 8.0) & (np.abs(Z) <= 1.5), "xy"), "silver")
    w.box(12, 14, 47, 51, -1, 1, "silver")
    # 밤하늘 구슬 (굵직한 2복셀 격자)
    ox, oy = 14.0, 42.0
    w.fill(q2(lambda X, Y, Z: ((X - ox) / 6.2) ** 2 + ((Y - oy) / 6.2) ** 2 + (Z / 4.6) ** 2 <= 1, "xyz"), "sky")
    # 금별: 구슬을 꿰뚫어 앞뒤로 솟는다 (구슬보다 작게)
    w.fill(lambda X, Y, Z: star_mask(X, Y, ox, oy, 4.0, 1.8) & (np.abs(Z) <= 5.0), "star")
    return w


# ─────────────────────────── 균열 (frost / flame) ───────────────────────────

def frost_staff():
    """홈 새긴 네모 쇠 밑동에서 고드름 자루가 자라 오르고, 서리 껍질이 쇠를 타고 내려온다.
    머리는 가지 돋은 여섯 팔 눈꽃, 가운데 빛나는 서리 핵."""
    m = mats(
        steel=Mat(["#1a2234", "#2e3a52", "#4a5a78", "#6e80a0"], "metal", seed=901),
        ice=Mat(["#6aa8d4", "#9cd0ee", "#cceefa", "#f4feff"], "crystal", seed=902),
        ice_d=Mat(["#2a5a94", "#3e7ab8", "#62a0d8", "#90c4ec"], "crystal", seed=903),
        crust=Mat(["#b8cce0", "#d4e4f2", "#eaf4fc", "#ffffff"], "stone", seed=907),
        core=Mat(["#1a6ab0", "#3ab0f0", "#90e8ff", "#f0ffff"], "flow", glow=True, seed=904),
    )
    w = Weapon(m, grip_y=15, kind="staff", seed=901)
    cy = 56.0
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Z) <= 0.4 + Y * 0.6) & (Y <= 3), "steel")   # 쇠 촉
    w.box(-1.5, 1.5, 3, 30, -1.5, 1.5, "steel")
    w.clear(lambda X, Y, Z: ((np.abs(X) > 1) | (np.abs(Z) > 1)) & (Y >= 8) & (Y <= 22) & ((np.floor(Y) % 3) == 0))  # 손잡이 홈

    # 고드름 자루: 쇠를 삼키며 위로 굵어진다 (마름모 단면, 왼쪽 면 짙게, 2칸씩 굵어짐)
    def icicle(X, Y, Z):
        r = 1.6 + 1.6 * np.clip((Y - 24) / 24, 0, 1) ** 1.2
        return (Y >= 24) & (Y <= cy) & (np.abs(X) + np.abs(Z) <= r + 0.6)
    w.fill(q2(lambda X, Y, Z: icicle(X, Y, Z) & (X < 0), "y"), "ice_d")
    w.fill(q2(lambda X, Y, Z: icicle(X, Y, Z) & (X >= 0), "y"), "ice")

    # 서리 껍질: 쇠 위로 들쭉날쭉 기어 내려온다
    def crust(X, Y, Z):
        edge = 26 - 3.0 * (0.5 + 0.5 * np.sin(X * 2.3 + Z * 1.7)) - 2.0 * (np.abs(X + Z) < 1)
        return (np.maximum(np.abs(X), np.abs(Z)) <= 2.5) & (np.maximum(np.abs(X), np.abs(Z)) > 1.5) & (Y >= edge) & (Y <= 28)
    w.fill(crust, "crust")

    # 눈꽃: 팔 여섯 (0, 60, ... 도), 팔마다 가지 두 쌍, 끝은 작은 마름모
    def arm_fn(deg, L):
        a = math.radians(deg)
        ux, uy = math.cos(a), math.sin(a)

        def fn(X, Y, Z):
            dx, dy = X, Y - cy
            u, v = dx * ux + dy * uy, -dx * uy + dy * ux
            flat = (Z >= -1) & (Z <= 1)
            main = (u >= 2) & (u <= L) & (np.abs(v) <= 1.0)
            barbs = np.zeros(X.shape, bool)
            for (b, bl) in ((L * 0.45, 3.2), (L * 0.72, 2.2)):
                for sgn in (1, -1):
                    # 가지: 팔에서 60도로 비스듬히 뻗는다
                    bu, bv = u - b, v * sgn
                    t = bu * 0.5 + bv * 0.866
                    p = -bu * 0.866 + bv * 0.5
                    barbs |= (t >= 0) & (t <= bl) & (np.abs(p) <= 0.75)
            tip = (np.abs(u - L) + np.abs(v) <= 1.8)
            return flat & (main | barbs | tip)
        return fn
    for deg in (0, 60, 120, 180, 240, 300):
        w.fill(arm_fn(deg, 11.0), "ice" if deg in (0, 60, 300) else "ice_d")
    # 가운데 육각판 + 핵
    w.fill(lambda X, Y, Z: (np.maximum(np.abs(X) * 0.866 + np.abs(Y - cy) * 0.5, np.abs(Y - cy)) <= 4.2) & (np.abs(Z) <= 1.5), "ice")
    w.fill(lambda X, Y, Z: np.abs(X) + np.abs(Y - cy) + np.abs(Z) * 0.7 <= 3.6, "core")
    return w


def flame_staff():
    """갈색 자루(용암 갈라짐)가 쇠 갈비 셋의 열린 우리로 벌어지고, 우리 안에서 큰 불길이 치솟는다. 붉은 천 손잡이와 술."""
    m = mats(
        wood=Mat(["#4a3020", "#7a5232", "#a07448", "#c09868"], "wood", seed=1001),
        lava=Mat(["#b02808", "#ff6a10", "#ffb030", "#ffe890"], "pulse", glow=True, seed=1002),
        iron=Mat(["#241e1e", "#423a3a", "#6a605c", "#948884"], "metal", seed=1003),
        flame=Mat(["#c02a08", "#ff5a14", "#ff9a28", "#ffd060"], "fire", glow=True, seed=1004),
        flame_c=Mat(["#ffa028", "#ffcc48", "#fff098", "#fffef0"], "fire", glow=True, seed=1005),
        cloth=Mat(["#5a0e0e", "#8a1a16", "#b02a20", "#d04432"], "cloth", seed=1006),
    )
    w = Weapon(m, grip_y=20, kind="staff", seed=1001)
    w.fill(lambda X, Y, Z: (rho(X, Z) <= 0.4 + Y * 0.5) & (Y <= 3), "iron")
    w.cyl(3, 42, 1.6, "wood")
    # 붉은 천 감개 + 늘어진 술
    w.cyl(13, 26, 1.9, "cloth")
    w.tube([(1.5, 26, 1.2), (3.0, 22, 1.5), (3.4, 17, 1.5)], 0.75, "cloth")
    # 용암 갈라짐 (지그재그 선, 앞뒤)
    for zs in (1, -1):
        w.tube([(0.5, 29, 1.3 * zs), (-0.7, 32, 1.3 * zs), (0.6, 35, 1.3 * zs), (-0.6, 38, 1.3 * zs), (0.3, 41, 1.3 * zs)], 0.75, "lava")
    # 쇠 목 + 갈비 셋 (밖으로 벌어졌다가 끝이 안으로 굽는 발톱)
    w.fill(lambda X, Y, Z: (np.maximum(np.abs(X), np.abs(Z)) <= 1.6 + (Y - 40) * 0.6) & (Y >= 40) & (Y <= 45), "iron")
    for deg in (20, 160, 270):
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)
        prof = [(3.0, 44), (8.0, 49), (10.0, 56), (9.5, 63), (7.0, 68), (4.5, 70)]
        beam(w, [(r * ca, y, r * sa) for r, y in prof], 1.0, "iron", q="y")

    # 불길: 큰 몸통 + 혀 셋, 가운데 밝은 심이 앞뒤로 비친다
    def tongue(X, Y, Z, x0, y0, y1, wmax, sway, dz=0.7):
        t = (Y - y0) / (y1 - y0)
        tc = np.clip(t, 0, 1)
        hw = wmax * np.sin(np.pi * np.clip(0.2 + 0.8 * tc, 0, 1) ** 0.7) * (1 - tc) ** 0.35
        off = x0 + sway * np.sin(tc * 3.5) * tc
        return (t >= 0) & (t <= 1) & (np.abs(X - off) <= hw) & (np.abs(Z) <= hw * dz)

    def fire(X, Y, Z):
        return (tongue(X, Y, Z, 0, 44, 72, 7.6, 1.2) | tongue(X, Y, Z, -4.0, 50, 66, 3.0, -1.5) |
                tongue(X, Y, Z, 4.2, 49, 64, 2.8, 1.5))
    w.fill(q2(fire, "xy"), "flame")
    w.fill(q2(lambda X, Y, Z: tongue(X, Y, Z, 0.3, 45, 64, 4.0, 0.8, dz=1.6) & (np.abs(Z) <= 5.8), "xy"), "flame_c")
    return w


# ─────────────────────────── 보스 / 프리즘 (aura) ───────────────────────────

def worldtree_staff():
    """뿌리를 뻗은 네모진 세계수 가지가 비틀리며 위로 굵어지다 세 갈래로 벌어져, 빛나는 생명의 씨앗을 손가락처럼 감싼다.
    잎 덩이는 갈래 끝에만, 수액은 줄기 앞면을 가르는 빛나는 실금 하나."""
    m = mats(
        bark=Mat(["#3a2614", "#5e4026", "#84603a", "#a88058"], "wood", seed=1101),
        bark_d=Mat(["#26180c", "#3e2a16", "#563c22", "#6e4e2e"], "wood", seed=1102),
        moss=Mat(["#2a4a1a", "#3e6a24", "#5a8a32", "#7aa648"], "cloth", seed=1103),
        leaf=Mat(["#3e8a2a", "#5aaa38", "#80cc4c", "#aee870"], "cloth", seed=1104),
        leaf2=Mat(["#1e4e1c", "#286626", "#367e30", "#46963c"], "cloth", seed=1105),
        sap=Mat(["#8a7010", "#e0b020", "#ffe070", "#fffbd0"], "flow", glow=True, seed=1106),
        seed=Mat(["#c09010", "#f0d040", "#fff4a0", "#ffffff"], "pulse", glow=True, seed=1107),
    )
    w = Weapon(m, grip_y=20, kind="staff", seed=1101)
    # 뿌리 넷 (두 계단씩)
    for (c, s) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for (d0, d1, y0, y1, h) in ((2, 6, 2, 7, 1.5), (5, 9.5, 0, 3.5, 1.5)):
            if c:
                w.box(min(c * d0, c * d1), max(c * d0, c * d1), y0, y1, -h, h, "bark_d")
            else:
                w.box(-h, h, y0, y1, min(s * d0, s * d1), max(s * d0, s * d1), "bark_d")
    w.box(-3.5, 3.5, 0, 1, -3.5, 3.5, "moss")
    # 줄기: 좌우로 비틀리며 위로 굵어진다 (손잡이 근처는 가늘게)
    trunk = [(0, 0, 0), (0.6, 8, 0), (-0.6, 16, 0.5), (0.6, 24, -0.5), (-0.4, 32, 0), (0, 41, 0)]
    beam(w, trunk, lambda t: 1.7 + 1.4 * t ** 1.5, "bark", q="xy")
    # 옹이
    w.box(1.0, 3.5, 12, 15, -1, 1.5, "bark_d")
    w.box(-4.0, -2.0, 30, 34, -1.5, 1, "bark_d")

    # 수액 실금: 앞면을 가르며 지그재그로
    def seam(X, Y, Z):
        zx = 0.9 * np.sin(Y * 0.55)
        half = 1.7 + 1.4 * np.clip(Y / 41, 0, 1) ** 1.5
        return (np.abs(X - zx) <= 0.6) & (Y >= 8) & (Y <= 39) & (Z >= half - 1.0) & (Z <= half + 1.0)
    w.fill(seam, "sap")
    # 세 갈래: 밖으로 벌어졌다가 끝이 안으로 굽어 씨앗을 감싼다 (뒤 갈래는 높이 솟는다)
    cy = 54.0
    branches = [
        ([(-1, 40, 0), (-5, 43, 0), (-10, 48, 0), (-12.5, 55, 0), (-11.5, 61, 0), (-8, 64.5, 0)], 1.6),
        ([(1, 40, 0), (5, 44, 0), (9.5, 49, 0), (12, 56, 0), (10.5, 62, 0), (7, 65.5, 0)], 1.6),
        ([(0, 40, -1), (0, 46, -4.5), (-0.5, 54, -6), (-1, 62, -5), (-1, 67, -2.5)], 1.5),
    ]
    for pts, h in branches:
        beam(w, pts, lambda t, h=h: h - 0.6 * t, "bark", q="xy")
    # 앞의 작은 잔가지
    beam(w, [(0, 41, 1.5), (1, 45, 4), (2.5, 48, 5)], 0.8, "bark")
    # 씨앗 (팔면체)
    w.fill(q2(lambda X, Y, Z: (np.abs(X) + np.abs(Y - cy) * 0.75 + np.abs(Z) <= 5.2), "y"), "seed")
    # 잎 덩이 (마크 잎 블록처럼 윗면 밝게) — 갈래 끝에만
    for (x, y, z, s) in ((-8.5, 66, 0, 3.5), (7.5, 67, 0, 3.5), (-1, 69.5, -2.5, 3.0), (3, 49.5, 5.5, 1.6)):
        blk = (lambda X, Y, Z, x=x, y=y, z=z, s=s: (np.abs(X - x) <= s) & (np.abs(Y - y) <= s * 0.75) & (np.abs(Z - z) <= s))
        w.fill(blk, "leaf2")
        w.fill(lambda X, Y, Z, b=blk: b(X, Y, Z) & ~b(X, Y + 1.5, Z), "leaf")
    w.set_aura(["#8a5a08", "#e0a020", "#ffe070", "#fffff0"], "holy", size=0.9, focus=["seed"])
    return w


def genesis_staff():
    """남흑빛 자루 위의 시계: 금 고리 안쪽으로 굵은 흰 시표 12 개와 검은 바늘, 그 뒤 무지개 핵.
    가로로 누운 궤도와 세로로 선 궤도가 엇갈려 혼천의를 이루고, 위에는 무지개 결정."""
    m = mats(
        obsid=Mat(["#120e24", "#241c44", "#3a2e66", "#5a4a90"], "metal", seed=1201),
        gold=Mat(["#6a4410", "#b07a1c", "#e8b840", "#fff0a0"], "metal", seed=1202),
        plat=Mat(["#8a90a8", "#c0c6da", "#e4e8f4", "#ffffff"], "metal", seed=1203),
        enamel=Mat(["#e8e4f0", "#f4f2fa", "#ffffff", "#ffffff"], "flat", seed=1204),
        hand=Mat(["#0a0818", "#14102a", "#1e183a", "#2a224a"], "flat", seed=1205),
        prism=Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=1206),
        crown=Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=1207),
    )
    w = Weapon(m, grip_y=24, kind="staff", seed=1201)
    cy = 54.0
    # 발끝: 금 뿔
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Z) <= 0.5 + Y * 0.55) & (Y <= 4), "gold")
    w.cyl(4, 44, 1.6, "obsid")
    # 손잡이: 모서리 깎은 네모 손잡이에 금 선 (감개, 고리 없음)
    w.fill(lambda X, Y, Z: (np.maximum(np.abs(X), np.abs(Z)) <= 2.0) & (np.abs(X) + np.abs(Z) <= 3.0) & (Y >= 16) & (Y <= 32), "obsid")
    w.fill(lambda X, Y, Z: (np.abs(X) <= 0.5) & (np.abs(Z) > 1.5) & (np.abs(Z) <= 2.0) & (Y >= 18) & (Y <= 30), "gold")
    # 목: 금 받침이 벌어져 고리를 받든다
    w.fill(lambda X, Y, Z: (np.maximum(np.abs(X), np.abs(Z)) <= 1.6 + (Y - 38) * 0.4) & (Y >= 38) & (Y <= 44.5), "gold")
    # 시계 고리 + 시표 (굵은 흰 칸이 안쪽으로)
    w.fill(q2(lambda X, Y, Z: (np.hypot(X, Y - cy) >= 8.4) & (np.hypot(X, Y - cy) <= 10.6) & (np.abs(Z) <= 1.5), "xy"), "gold")
    for k in range(12):
        a = k * math.pi / 6
        big = k % 3 == 0
        r0, r1, hw = (5.4 if big else 6.6), 8.6, (1.0 if big else 0.6)
        ca, sa = math.cos(a), math.sin(a)
        w.fill(lambda X, Y, Z, ca=ca, sa=sa, r0=r0, hw=hw: ((X * ca + (Y - cy) * sa) >= r0) & ((X * ca + (Y - cy) * sa) <= r1) &
               (np.abs(-X * sa + (Y - cy) * ca) <= hw) & (Z >= -1) & (Z <= 1), "enamel")
    # 무지개 핵
    w.fill(lambda X, Y, Z: (np.abs(X) <= 3) & (np.abs(Y - cy) <= 3) & (np.abs(Z) <= 3) &
           (np.abs(X) + np.abs(Y - cy) + np.abs(Z) <= 6), "prism")
    # 바늘: 핵 앞뒤를 가로지른다 (긴 바늘 12 시, 짧은 바늘 3 시)
    for zs in (1, -1):
        z0, z1 = sorted((zs * 3.0, zs * 4.0))
        w.box(-0.5, 0.5, cy - 1, cy + 7.5, z0, z1, "hand")
        w.box(-0.5, 5.0, cy - 0.5, cy + 0.5, z0, z1, "hand")
        w.box(-1, 1, cy - 1, cy + 1, min(z0, zs * 5), max(z1, zs * 5), "gold")
    # 궤도 둘: 하나는 X 축을 품고 앞으로 50도, 하나는 Y 축을 품고 옆으로 50도 (정면에서 엇갈린 두 타원)
    c50, s50 = math.cos(math.radians(50)), math.sin(math.radians(50))
    for n in ((0.0, s50, c50), (s50, 0.0, c50)):
        w.fill(q2(lambda X, Y, Z, n=n: (np.sqrt(X ** 2 + (Y - cy) ** 2 + Z ** 2) >= 11.6) & (np.sqrt(X ** 2 + (Y - cy) ** 2 + Z ** 2) <= 13.6) &
                  (np.abs(X * n[0] + (Y - cy) * n[1] + Z * n[2]) <= 1.1), "xyz"), "plat")
    # 왕관 결정
    w.box(-1.5, 1.5, 64, 65.5, -1.5, 1.5, "gold")
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Y - 69.0) * 0.75 + np.abs(Z) <= 3.0) & (Y >= 65.5), "crown")
    # 아우라는 핵에서만 피어올라 시계 머리를 감싼다 (왕관과 자루는 가리지 않게)
    w.set_aura("prism", "flame", size=0.8, focus=["prism"])
    return w


NAMES = {
    "novice_wand": "수습 마법봉",
    "gold_wand": "황금 마법봉",
    "amethyst_wand": "자수정 마법봉",
    "holy_staff": "빛의 지팡이",
    "nature_staff": "숲의 지팡이",
    "cloud_staff": "구름 지팡이",
    "ocean_staff": "바다의 지팡이",
    "star_staff": "별의 지팡이",
    "frost_staff": "서리 지팡이",
    "flame_staff": "화염 지팡이",
    "worldtree_staff": "세계수의 지팡이",
    "genesis_staff": "창세의 지팡이",
}

WEAPONS = {
    "novice_wand": novice_wand,
    "gold_wand": gold_wand,
    "amethyst_wand": amethyst_wand,
    "holy_staff": holy_staff,
    "nature_staff": nature_staff,
    "cloud_staff": cloud_staff,
    "ocean_staff": ocean_staff,
    "star_staff": star_staff,
    "frost_staff": frost_staff,
    "flame_staff": flame_staff,
    "worldtree_staff": worldtree_staff,
    "genesis_staff": genesis_staff,
}

if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids:
        sub = {k: WEAPONS[k] for k in ids}
        preview_sheet(sub, os.path.join(HERE, "preview", "_scratch", "magic_part.png"), names=NAMES)
    else:
        preview_sheet(WEAPONS, "/home/user/nai-cg-maker/augment-skyblock/pack/weapons/preview/magic.png", names=NAMES)
