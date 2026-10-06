"""
pickaxes: 곡괭이 7 자루 (개척자 → 광부 → 자수정 → 심층 → 용암 → 운석 → 프리즘).

세워서 만든다: 자루가 아래, 머리는 위에서 X 로 가로놓이고 양팔이 아래로 처진다
(인벤토리에서 45도 눕히면 바닐라 곡괭이 그림과 같은 방향). 아우라는 맨 윗 등급(프리즘)만.
머리는 Y 48..64 (16 복셀 한 칸) 안에 두어 element 가 덜 쪼개지게 한다. 그래서 자루는 Y=8 에서 시작.

python3 pickaxes.py            -> preview/pickaxes.png
python3 pickaxes.py id1 id2    -> 그 곡괭이만 preview/_scratch/pickaxes_part.png
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, Weapon, preview_sheet  # noqa: E402

HB = 8      # 자루 맨 아래 (설계 Y)
CY = 56     # 머리(눈) 가운데 높이


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


def padded(mats):
    """
    미리보기 렌더러는 면 가장자리 한 줄을 옆 아틀라스 칸에서 집어 온다 (axes_hammers 와 같은 방법).
    그래서 재료마다 같은 재료의 복사본을 옆(과 가능하면 아래)에 둔다.
    """
    st = [(k, v) for k, v in mats.items() if not v.animated]
    an = [(k, v) for k, v in mats.items() if v.animated]
    out = {}

    def lay(items, per):
        if not items or len(items) * 2 > per * per:
            out.update(items)
            return
        half = per // 2
        block = len(items) * 4 <= per * per
        for i in range(0, len(items), half):
            row = list(items[i:i + half])
            while len(row) < half:
                row.append(row[-1])
            for rep in range(2 if block else 1):
                for k, v in row:
                    out[k if (rep == 0 and k not in out) else "_p%d_%s" % (len(out), k)] = v
                    out["_p%d_%s" % (len(out), k)] = v

    lay(st, 4)
    lay(an, 2)
    return out


def q2(V, off=0.0):
    """2복셀 단위로 좌표를 묶는다 (윤곽이 2칸씩 계단 → 마크 픽셀 같은 덩어리감, 요소 수 절반)."""
    return np.floor((V - off) / 2) * 2 + 1 + off


def rmask(x0, x1, y0, y1, z0, z1, c=1.0):
    """한 칸 계단으로 모서리를 깎은 상자."""
    def f(X, Y, Z):
        ix = (X >= x0) & (X <= x1)
        iy = (Y >= y0) & (Y <= y1)
        iz = (Z >= z0) & (Z <= z1)
        jx = (X >= x0 + c) & (X <= x1 - c)
        jy = (Y >= y0 + c) & (Y <= y1 - c)
        jz = (Z >= z0 + c) & (Z <= z1 - c)
        return (ix & jy & jz) | (jx & iy & jz) | (jx & jy & iz)
    return f


def rbox(w, x0, x1, y0, y1, z0, z1, c, mat):
    w.fill(rmask(x0, x1, y0, y1, z0, z1, c), mat)
    return w


def line2d(pts, r):
    """XY 꺾은선까지 거리가 r 이하인 2D 마스크 (금, 맥, 홈)."""
    P = np.array(pts, float)

    def m(X, Y):
        d = np.full(np.shape(X), 1e9)
        for (x1, y1), (x2, y2) in zip(P[:-1], P[1:]):
            dx, dy = x2 - x1, y2 - y1
            t = np.clip(((X - x1) * dx + (Y - y1) * dy) / (dx * dx + dy * dy), 0, 1)
            d = np.minimum(d, np.hypot(X - x1 - t * dx, Y - y1 - t * dy))
        return d <= r
    return m


def paint(w, mask, mat):
    """이미 있는 복셀만 색을 바꾼다 (모양은 그대로)."""
    m = np.asarray(mask(w._X, w._Y, w._Z), bool) & (w.grid > 0)
    w.grid[m] = w._id(mat)
    return w


def face_paint(w, mask2d, mat, only=None):
    """앞뒤(±Z)에서 보이는 맨 바깥 복셀만 칠한다 — 몸통 색은 그대로 두고 겉에 맥·금을 그릴 때."""
    g = w.grid > 0
    m2 = np.asarray(mask2d(w._X[:, :, 0], w._Y[:, :, 0]), bool)
    ids = None if only is None else [w._id(n) for n in only]
    for x, y in np.argwhere(m2):
        col = np.nonzero(g[x, y, :])[0]
        if len(col) == 0:
            continue
        for z in (col[0], col[-1]):
            if ids is None or w.grid[x, y, z] in ids:
                w.grid[x, y, z] = w._id(mat)
    return w


def lash_loop(w, cx, y0, slope, hx, hz, r, mat):
    """자루(머리) 둘레를 비스듬히 한 바퀴 감는 끈."""
    pts = [(-hx, y0 - slope * hx, hz), (hx, y0 + slope * hx, hz), (hx, y0 + slope * hx, -hz),
           (-hx, y0 - slope * hx, -hz), (-hx, y0 - slope * hx, hz)]
    w.tube([(cx + x, y, z) for x, y, z in pts], r, mat)


def arm(x0, x1, yc, hh, hz, side=1, qy=False):
    """
    곡괭이 팔 한쪽: X 를 2칸 기둥으로 묶어 기둥마다 높이 가운데 yc(u), 반높이 hh(u), 반두께 hz(u).
    u = 0 (눈 쪽) → 1 (끝). side = +1 오른쪽, -1 왼쪽. qy=True 면 높이도 2칸 계단 (거친 돌).
    """
    def f(X, Y, Z):
        sx = X * side
        u = np.clip((q2(sx) - x0) / (x1 - x0), 0, 1)
        yy = q2(Y) if qy else Y
        return (sx >= x0) & (sx <= x1) & (np.abs(yy - yc(u)) <= hh(u)) & (np.abs(Z) <= hz(u))
    return f


def arm_u(x0, x1, side=1):
    """arm() 과 같은 u (칠할 때 쓰는 끝 쪽 비율)."""
    return lambda X: np.clip((q2(X * side) - x0) / (x1 - x0), 0, 1)


def diamond_arm(x0, x1, yc, hh, hzm, side=1):
    """마름모 단면의 결정 팔 (2칸 기둥): |높이차|/hh(u) + |Z|/hzm(u) <= 1. 자수정·흑요석처럼 각진 결정 날."""
    uu = arm_u(x0, x1, side)

    def f(X, Y, Z):
        u = uu(X)
        return (X * side >= x0) & (X * side <= x1) & (np.abs(Y - yc(u)) / hh(u) + np.abs(Z) / hzm(u) <= 1.0)
    return f, uu


def spike(p0, p1, r0, r1=0.4, tip=0.35, zk=1.0, quant=True):
    """
    p0 → p1 로 뻗는 결정 (XY 평면, 마름모 단면). 끝 tip 비율에서 뾰족해진다.
    돌려주는 값: (마스크, 축의 어느 쪽인지 알려 주는 함수 side(X, Y) — 두 빛깔 결정 면을 칠할 때).
    """
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = p1 - p0
    L = float(np.hypot(*d))
    ux, uy = d / L
    nx, ny = -uy, ux

    def rad(t):
        return r0 + (r1 - r0) * np.clip((t - (1 - tip)) / tip, 0, 1)

    def f(X, Y, Z):
        Xq, Yq = (q2(X), q2(Y)) if quant else (X, Y)
        dx, dy = Xq - p0[0], Yq - p0[1]
        t = (dx * ux + dy * uy) / L
        s = dx * nx + dy * ny
        return (t >= -0.05) & (t <= 1) & (np.abs(s) + np.abs(Z) * zk <= rad(t))

    def side(X, Y):
        return (X - p0[0]) * nx + (Y - p0[1]) * ny
    return f, side


# ─────────────────────────── basic ───────────────────────────

def pioneer_pickaxe():
    """개척자의 곡괭이: 구불구불한 나뭇가지 자루에 한쪽으로 치우친 뗀석기 쐐기를 가죽끈으로 동여맸다. 긴 끝엔 검은 부싯돌 조각."""
    m = {
        "bark": Mat(["#3a2614", "#563a1e", "#74502a", "#8e663a"], "wood", seed=301),
        "wood": Mat(["#8a6a3e", "#a8865a", "#c4a476", "#dcc094"], "wood", seed=302),
        "stone": Mat(["#5a5a5c", "#78787a", "#969698", "#b4b4b6"], "stone", seed=303),
        "chip": Mat(["#46464a", "#58585c", "#6a6a6e", "#7c7c80"], "stone", seed=304),
        "flint": Mat(["#18181c", "#2a2a30", "#40404a", "#5c5c68"], "stone", seed=305),
        "thong": Mat(["#4a2a14", "#6e3e1e", "#91562a", "#b07040"], "grip", seed=306),
    }
    w = Weapon(padded(m), grip_y=HB + 8, kind="pickaxe", seed=301)
    # 구불구불한 가지 자루 + 잘린 곁가지 하나
    w.tube([(0.4, HB, 0), (1.3, HB + 10, 0), (0.2, HB + 21, 0), (-0.9, HB + 32, 0), (0.1, HB + 42, 0), (0.3, CY + 4, 0)],
           1.7, "bark")
    w.tube([(0.0, 34, 0), (3.6, 37.5, 0.5)], 1.0, "bark")
    w.box(3, 4.6, 37, 39, -0.5, 1.5, "wood")                    # 곁가지 잘린 면
    w.box(-1, 2, HB, HB + 1, -1, 1, "wood")                     # 밑동 잘린 면
    for (y0, sl) in ((HB + 3, 0.3), (HB + 7, -0.25), (HB + 11, 0.3)):   # 손잡이: 거칠게 감은 가죽끈
        lash_loop(w, 0.9, y0, sl, 2.3, 2.3, 0.7, "thong")

    # 머리: 오른쪽은 길게 처진 뾰족 끝, 왼쪽은 짧고 뭉툭한 끝 — 높이도 2칸 계단으로 거칠게
    hz = lambda u: np.where(u < 0.3, 2.5, np.where(u < 0.7, 1.5, 1.0))
    right = arm(3, 21, lambda u: CY + 0.5 - 8.0 * u ** 1.4, lambda u: 2.9 * (1 - u) ** 0.85 + 0.5, hz, side=1, qy=True)
    left = arm(3, 13, lambda u: CY + 0.5 - 4.0 * u ** 1.3, lambda u: 3.0 * (1 - u) ** 0.85 + 0.5, hz, side=-1, qy=True)
    lump = rmask(-4, 4, CY - 4, CY + 4.5, -3, 3, 1.5)
    head = lambda X, Y, Z: right(X, Y, Z) | left(X, Y, Z) | lump(X, Y, Z)
    w.fill(head, "stone")
    # 떼어 낸 홈: 아래 날 한 군데를 깎아 낸다
    w.clear(lambda X, Y, Z: (np.abs(q2(X) - 11) <= 1) & (q2(Y) <= 51) & (Y < CY - 2))
    # 떼어 낸 자국: 어두운 면 몇 군데 (앞뒤로 엇갈리게)
    for (x0, x1, y0, y1, s) in ((6, 10, 52, 57, 1), (-7, -3, 53, 57, -1), (12, 16, 49, 53, -1), (-2, 2, 57, 61, 1)):
        paint(w, lambda X, Y, Z, a=(x0, x1, y0, y1, s): (X >= a[0]) & (X <= a[1]) & (Y >= a[2]) & (Y <= a[3])
              & (Z * a[4] > 0.5), "chip")
    paint(w, lambda X, Y, Z: X >= 17, "flint")                 # 긴 끝의 부싯돌
    paint(w, lambda X, Y, Z: X <= -11, "chip")
    # 가죽끈: 머리와 자루가 만나는 곳을 X 자로 두 번, 그 아래 한 바퀴, 늘어진 끈 끝
    for sl in (0.75, -0.75):
        lash_loop(w, 0.0, CY + 0.5, sl, 4.5, 3.6, 0.75, "thong")
    w.cyl(CY - 8, CY - 6, 2.3, "thong", cx=0.1)
    w.tube([(-2.2, CY - 7, 1.6), (-3.4, CY - 11, 1.8), (-2.8, CY - 15, 1.6)], 0.7, "thong")
    return w


def miner_pickaxe():
    """광부의 곡괭이: 살짝 아치진 양끝 쇠 곡괭이, 쇠고리 둘 감은 참나무 자루, 왼팔에서 사슬로 늘어진 작은 초롱."""
    m = {
        "iron": Mat(["#34373e", "#4c5058", "#666a72", "#80848c"], "metal", seed=311),
        "steel": Mat(["#8a9098", "#aeb4bc", "#d0d6dc", "#f2f5f8"], "metal", seed=312),
        "oak": Mat(["#5a3a1a", "#7e5428", "#a07038", "#be8c4e"], "wood", seed=313),
        "leather": Mat(["#2e1a0e", "#462814", "#5e381e", "#7a4a2a"], "grip", seed=314),
        "chain": Mat(["#202228", "#30333a", "#44474e", "#5a5e66"], "metal", seed=315),
        "lamp": Mat(["#c06010", "#f0a030", "#ffd070", "#fff4c0"], "pulse", glow=True, seed=316),
    }
    w = Weapon(padded(m), grip_y=HB + 8, kind="pickaxe", seed=302)
    w.cyl(HB, CY + 6, 1.6, "oak")
    w.cyl(HB + 2, HB + 15, 1.9, "leather")
    w.cyl(HB, HB + 2, 2.1, "iron")                              # 자루 끝 쇠마개
    for y in (HB + 15, CY - 9):                                  # 쇠고리 둘
        w.cyl(y, y + 1.5, 2.1, "iron")
    # 머리: 가운데가 굵고 양끝으로 가늘어지며 아래로 휜다. 끝은 벼린 강철
    yc = lambda u: CY - 7.0 * u ** 1.6
    hh = lambda u: 3.2 * (1 - u) ** 0.9 + 0.7
    hz = lambda u: np.where(u < 0.4, 2.5, np.where(u < 0.75, 1.5, 1.0))
    for s in (1, -1):
        w.fill(arm(2, 20, yc, hh, hz, side=s), "iron")
    paint(w, lambda X, Y, Z: (np.abs(X) >= 16) & (Y > CY - 10), "steel")
    rbox(w, -3.5, 3.5, CY - 5, CY + 5, -3, 3, 1, "iron")        # 눈
    w.box(-1.5, 1.5, CY + 5, CY + 6, -1, 1, "oak")             # 자루 끝
    w.box(-0.5, 0.5, CY + 5, CY + 6.5, -1.5, 1.5, "steel")     # 쐐기
    # 사슬 + 초롱 (왼팔 아래, 자루와 떨어져서)
    lx = -8.5
    for i, y in enumerate(range(CY - 10, CY - 3, 2)):
        if i % 2:
            w.box(lx - 0.5, lx + 0.5, y, y + 1.5, -1, 1, "chain")
        else:
            w.box(lx - 1, lx + 1, y, y + 1.5, -0.5, 0.5, "chain")
    w.box(lx - 1, lx + 1, CY - 12, CY - 10, -1, 1, "chain")      # 고리
    rbox(w, lx - 2.5, lx + 2.5, CY - 14, CY - 12, -2.5, 2.5, 0.5, "chain")  # 뚜껑
    w.box(lx - 2, lx + 2, CY - 19, CY - 14, -2, 2, "lamp")      # 불빛
    w.fill(lambda X, Y, Z: (np.abs(X - lx) > 1) & (np.abs(Z) > 1) & (np.abs(X - lx) <= 2) & (np.abs(Z) <= 2)
           & (Y >= CY - 19) & (Y <= CY - 14), "chain")          # 모서리 살
    rbox(w, lx - 2.5, lx + 2.5, CY - 20, CY - 19, -2.5, 2.5, 0.5, "chain")  # 바닥
    return w


# ─────────────────────────── island ───────────────────────────

def amethyst_pickaxe():
    """자수정 곡괭이: 방해석 흰 자루를 자수정 띠가 나선으로 감고, 정동 덩이 양쪽으로 각진 두 빛깔 자수정 날, 위에는 결정 다발이 자란다. 눈엔 싹트는 보석."""
    m = {
        "calcite": Mat(["#a8a8b0", "#c8c8d0", "#e2e2e8", "#f6f6fa"], "stone", seed=321),
        "basalt": Mat(["#2a2a30", "#3a3a42", "#4c4c56", "#60606a"], "stone", seed=322),
        "am_l": Mat(["#7a4ac0", "#a070e0", "#c8a0f8", "#f0e0ff"], "crystal", seed=323),
        "am_d": Mat(["#3a1a70", "#5a2ea0", "#7a48c8", "#9a68e0"], "crystal", seed=324),
        "bud": Mat(["#6a2ad0", "#a060ff", "#d8b0ff", "#ffffff"], "sparkle", glow=True, seed=325),
    }
    w = Weapon(padded(m), grip_y=HB + 9, kind="pickaxe", seed=303)
    w.cyl(HB + 3, CY - 2, 1.6, "calcite")
    # 나선 띠: 자루 네 면을 2칸씩 돌아 오른다 (한 바퀴마다 빛깔을 바꿔 조각처럼)
    faces = [lambda X, Z: (X >= 1.6) & (X <= 2.6) & (np.abs(Z) <= 2.6),
             lambda X, Z: (Z >= 1.6) & (Z <= 2.6) & (np.abs(X) <= 2.6),
             lambda X, Z: (X <= -1.6) & (X >= -2.6) & (np.abs(Z) <= 2.6),
             lambda X, Z: (Z <= -1.6) & (Z >= -2.6) & (np.abs(X) <= 2.6)]
    for k in range(13):
        y = HB + 5 + k * 2
        fm = faces[k % 4]
        w.fill(lambda X, Y, Z, fm=fm, y=y: fm(X, Z) & (Y >= y) & (Y <= y + 2), "am_l" if (k // 4) % 2 else "am_d")
    # 밑동: 아래로 뾰족한 자수정 + 방해석 고리
    f, _ = spike((0, HB + 4), (0, HB - 3), 2.4, 0.4, tip=0.7, quant=False)
    w.fill(f, "am_d")
    w.cyl(HB + 3, HB + 4.5, 2.1, "calcite")
    # 날: 마름모 단면의 결정 (윗면은 밝은 빛깔, 아랫면은 짙은 빛깔), 끝으로 갈수록 처지며 뾰족하다
    yc = lambda u: CY - 7.0 * u ** 1.5
    hh = lambda u: 3.4 * (1 - u) ** 0.8 + 0.5
    hzm = lambda u: 2.6 * (1 - u) ** 0.6 + 0.6
    for s in (1, -1):
        blade, uu = diamond_arm(3, 21 if s > 0 else 20, yc, hh, hzm, side=s)
        w.fill(blade, "am_d")
        paint(w, lambda X, Y, Z, blade=blade, uu=uu: blade(X, Y, Z) & (Y >= yc(uu(X))), "am_l")
    # 정동 덩이: 현무암 껍질, 앞뒤로 방해석 테와 싹트는 보석
    rbox(w, -4.5, 4.5, CY - 4.5, CY + 4.5, -3.5, 3.5, 1, "basalt")
    face_paint(w, lambda X, Y: (np.abs(X) <= 2.5) & (np.abs(Y - CY) <= 2.5), "calcite", only=["basalt"])
    w.gem(0, CY, 1.6, "bud", depth=4.0)
    # 결정 다발: 머리 위와 날 위에서 곧게 자라는 뾰족한 결정 (왼쪽 면 밝게, 오른쪽 면 짙게)
    for (x, y0, h, hw) in ((0, CY + 3.5, 8.5, 1.5), (-3.5, CY + 3, 5, 1.0), (3.5, CY + 3, 4, 1.0),
                           (9, CY + 1, 5, 1.0), (-10, CY + 0.5, 4, 1.0)):
        def shard(X, Y, Z, x=x, y0=y0, h=h, hw=hw):
            t = np.clip((Y - y0) / h, 0, 1)
            r = np.where(t < 0.6, hw, hw * (1 - t) / 0.4 + 0.1)
            return (Y >= y0) & (Y <= min(y0 + h, 64)) & (np.abs(X - x) <= r + 0.01) & (np.abs(Z) <= r + 0.01)
        w.fill(shard, "am_d")
        paint(w, lambda X, Y, Z, shard=shard, x=x: shard(X, Y, Z) & (X < x), "am_l")
    return w


def deep_pickaxe():
    """심층 곡괭이: 묵직한 곡괭이망치 — 거의 검은 심층암 덩이, 왼쪽은 넓적한 망치 면, 오른쪽은 다이아몬드 끝이 박힌 긴 송곳. 붉은 레드스톤 맥이 맥박친다."""
    m = {
        "deep": Mat(["#1c1c22", "#2a2a32", "#383842", "#484852"], "stone", seed=331),
        "deep_l": Mat(["#3a3a44", "#4c4c58", "#5e5e6a", "#72727e"], "metal", seed=332),
        "dia": Mat(["#1a8a9a", "#3cc8d0", "#8af0f0", "#e8ffff"], "gem", seed=333),
        "haft": Mat(["#2a1a10", "#3e2818", "#523622", "#68462e"], "wood", seed=334),
        "tuff": Mat(["#4a4a42", "#62625a", "#7a7a70", "#929288"], "stone", seed=335),
        "grip": Mat(["#141416", "#222226", "#323238", "#44444c"], "grip", seed=336),
        "red": Mat(["#6a0000", "#c01010", "#ff3a2a", "#ffa090"], "pulse", glow=True, seed=337),
    }
    w = Weapon(padded(m), grip_y=HB + 9, kind="pickaxe", seed=304)
    rbox(w, -2.5, 2.5, HB, CY, -2.5, 2.5, 1, "haft")            # 굵은 자루
    rbox(w, -3, 3, HB + 2, HB + 16, -3, 3, 1, "grip")
    for y in (HB, HB + 16, HB + 29, CY - 10):                    # 응회암 띠
        rbox(w, -3, 3, y, y + 2, -3, 3, 1, "tuff")
    rbox(w, -5, 5, CY - 6.5, CY + 6.5, -4.5, 4.5, 1.5, "deep")  # 눈 덩이
    rbox(w, -9, -5, CY - 4.5, CY + 4.5, -3.5, 3.5, 1, "deep")   # 망치 목
    rbox(w, -13, -9, CY - 6, CY + 6, -4.5, 4.5, 1, "deep")      # 넓적한 망치 머리
    rbox(w, -14, -13, CY - 5, CY + 5, -3.5, 3.5, 1, "deep_l")   # 반들반들한 치는 면
    paint(w, lambda X, Y, Z: (X >= -13) & (X <= -9) & (np.abs(np.abs(Y - CY) - 4.5) <= 0.6), "deep_l")   # 판석 줄 (심층암 결)
    # 오른쪽 송곳: 네모 단면, 아래로 휘며 가늘어진다. 끝은 다이아몬드, 그 앞에 쇠테
    yc = lambda u: CY + 0.5 - 8.0 * u ** 1.5
    hh = lambda u: 4.2 * (1 - u) ** 0.85 + 0.6
    hz = lambda u: np.where(u < 0.35, 3.5, np.where(u < 0.7, 2.5, 1.5))
    w.fill(arm(5, 23, yc, hh, hz, side=1), "deep")
    paint(w, lambda X, Y, Z: X >= 18, "dia")
    paint(w, lambda X, Y, Z: (X >= 16) & (X < 18), "deep_l")
    # 레드스톤 맥: 앞뒤 겉면에 갈라진 붉은 줄
    veins = [line2d([(-12, CY - 2.5), (-8, CY), (-4, CY - 1.5), (0, CY + 1.5), (5, CY), (10, CY + 0.5), (14, CY - 2)], 0.6),
             line2d([(0, CY + 1.5), (-1.5, CY + 5)], 0.6)]
    face_paint(w, lambda X, Y: veins[0](X, Y) | veins[1](X, Y), "red", only=["deep", "deep_l"])
    return w


# ─────────────────────────── flame ───────────────────────────

def magma_pickaxe():
    """용암 곡괭이: 윗등이 톱니처럼 들쭉날쭉한 흑암 바위 머리, 뒤로 젖혀 솟은 현무암 지느러미, 겉을 타고 흐르는 용암 금. 자루는 블레이즈 막대, 끝엔 마그마 크림."""
    m = {
        "black": Mat(["#141014", "#221c22", "#322a32", "#443a44"], "stone", seed=341),
        "basalt": Mat(["#3a3838", "#504c4c", "#686262", "#827a7a"], "wood", seed=342),
        "grip": Mat(["#1a0c08", "#2e1610", "#44221a", "#5a3024"], "grip", seed=343),
        "cream": Mat(["#8a3a08", "#d06a14", "#f0a030", "#ffd070"], "stone", seed=344),
        "magma": Mat(["#8a1a00", "#e04a08", "#ffa020", "#fff0a0"], "fire", glow=True, seed=345),
        "blaze": Mat(["#c86000", "#f09a10", "#ffd040", "#fff8b0"], "flow", glow=True, seed=346),
        "hot": Mat(["#c03000", "#ff7010", "#ffc040", "#fff8c0"], "pulse", glow=True, seed=347),
    }
    w = Weapon(padded(m), grip_y=HB + 9, kind="pickaxe", seed=305)
    w.cyl(HB + 2, CY, 1.5, "blaze")                             # 블레이즈 막대
    w.cyl(HB + 3, HB + 16, 2.0, "grip")
    w.cyl(HB + 16, HB + 17, 2.1, "black")
    w.ball(0, HB + 2, 0, 2.7, 2.4, 2.7, "cream")                # 마그마 크림 마개
    w.fill(lambda X, Y, Z: (np.abs(Y - HB - 2) <= 0.5) & (np.hypot(X, Z) <= 2.8) & (np.hypot(X, Z) > 1.8), "magma")
    # 바위 머리: 양끝 곡괭이, 윗등은 톱니, 아랫면은 매끈하게 휜다
    raw = poly([(-21, 48.5), (-19, 51.5), (-16, 54), (-14, 53.5), (-12, 56.5), (-9.5, 56), (-7, 59), (-4, 58.5),
                (-2, 61), (2, 61), (4, 58.5), (7, 59), (9.5, 56), (12, 56.5), (14, 53.5), (16, 54), (19, 51.5),
                (21.5, 48.5), (18.5, 49), (14, 50.5), (9, 51.5), (4, 51.5), (3.5, 49), (-3.5, 49), (-4, 51.5),
                (-9, 51.5), (-14, 50.5), (-18.5, 49)])
    head = lambda X, Y: raw(q2(X), q2(Y))
    hz = lambda X: np.where(np.abs(X) < 5, 3.0, np.where(np.abs(X) < 14, 2.0, 1.0))
    w.fill(lambda X, Y, Z: head(X, Y) & (np.abs(Z) <= hz(X)), "black")
    # 지느러미: 뒤로 젖혀 솟은 현무암 판 둘 + 가운데 뿔
    for pts in ([(3, 58), (7, 58), (13, 64.5), (9, 64.5), (4, 61.5)], [(-3, 58), (-7, 58), (-13, 64.5), (-9, 64.5), (-4, 61.5)]):
        fin = poly(pts)
        w.fill(lambda X, Y, Z, fin=fin: fin(q2(X), q2(Y)) & (np.abs(Z) <= 1.0), "basalt")
    w.fill(lambda X, Y, Z: (Y >= 60) & (Y <= 64) & (np.abs(X) + np.abs(Z) <= 2.6 - (Y - 60) * 0.5), "basalt")
    # 겉을 타고 흐르는 용암 금 (팔 한가운데를 따라, 몸통 색은 그대로), 양끝은 달아오름
    cracks = [line2d([(-19, 50), (-14, 52.5), (-9, 54), (-4, 54), (-1, 56.5), (2, 54.5), (6, 54), (10, 54.5), (14, 52.5), (19, 50)], 0.6),
              line2d([(-1, 56.5), (0, 59.5)], 0.6), line2d([(-9, 54), (-8, 56.5)], 0.6), line2d([(10, 54.5), (11, 56)], 0.6)]
    face_paint(w, lambda X, Y: cracks[0](X, Y) | cracks[1](X, Y) | cracks[2](X, Y) | cracks[3](X, Y), "magma", only=["black"])
    paint(w, lambda X, Y, Z: (np.abs(X) >= 19.5) & (Y < 53), "hot")
    rbox(w, -3.5, 3.5, CY - 7, CY + 2, -3.5, 3.5, 1, "black")   # 눈
    return w


# ─────────────────────────── boss ───────────────────────────

def meteor_pickaxe():
    """운석 곡괭이: 울퉁불퉁한 운석 덩이를 흰 엔드 막대 위에 꽂고, 휘어진 긴 우는 흑요석 송곳과 짧은 맞송곳이 덩이를 꿰뚫는다. 보라 맥, 별 반짝임."""
    m = {
        "rock": Mat(["#2a2420", "#3e3630", "#544a42", "#6c6056"], "stone", seed=351),
        "iron": Mat(["#3a3c44", "#585c66", "#7a7e88", "#9ea2ac"], "metal", seed=352),
        "obs": Mat(["#1c1030", "#2c1a48", "#40286a", "#5a3a8e"], "crystal", seed=353),
        "rod": Mat(["#c8c4d0", "#e0dce8", "#f2f0f8", "#ffffff"], "flat", seed=354),
        "rodb": Mat(["#5a4a6a", "#76628a", "#9480a8", "#b2a0c4"], "metal", seed=355),
        "grip": Mat(["#120a1e", "#201432", "#2e1e48", "#3e2a5e"], "grip", seed=356),
        "cry": Mat(["#3a0a8a", "#7a2ae8", "#b070ff", "#e8d0ff"], "pulse", glow=True, seed=357),
        "star": Mat(["#a08a40", "#e8d070", "#fff4c0", "#ffffff"], "sparkle", glow=True, seed=358),
    }
    w = Weapon(padded(m), grip_y=HB + 9, kind="pickaxe", seed=306)
    w.cyl(HB + 2, CY - 3, 1.6, "rod")                            # 엔드 막대
    rbox(w, -2.5, 2.5, HB, HB + 2, -2.5, 2.5, 0.5, "rodb")      # 막대 받침
    w.cyl(HB + 3, HB + 16, 2.0, "grip")
    w.cyl(HB + 16, HB + 17.5, 2.1, "rodb")
    # 운석 덩이: 혹 몇 개를 합치고 (2칸 덩어리), 패인 자국을 낸다
    lumps = [(0, CY, 0, 7.0, 6.5, 6), (3, CY + 3, 1, 4.5, 4, 4), (-4, CY - 2.5, -1, 4.5, 4, 4.5)]

    def rock(X, Y, Z):
        out = np.zeros(np.shape(X), bool)
        for (cx, cyy, cz, rx, ry, rz) in lumps:
            out |= ((q2(X) - cx) / rx) ** 2 + ((q2(Y) - cyy) / ry) ** 2 + ((q2(Z) - cz) / rz) ** 2 <= 1.0
        return out

    w.fill(rock, "rock")
    for (px, py, pz, pr) in ((4, CY - 3, 6, 2.2), (1, CY + 4, -6, 2.2)):
        w.clear(lambda X, Y, Z, a=(px, py, pz, pr): np.hypot(np.hypot(q2(X) - a[0], q2(Y) - a[1]), q2(Z) - a[2]) <= a[3])
    # 운철 얼룩 (4칸 덩어리), 보라 맥, 별 반짝임 — 겉면에만
    face_paint(w, lambda X, Y: (((np.floor(X / 4) * 7 + np.floor(Y / 4) * 3) % 5) == 0) & (np.abs(X) < 9), "iron", only=["rock"])
    vein_l = line2d([(-6.5, CY - 4), (-2, CY - 1), (1, CY + 1.5), (5, CY + 2), (6, CY + 5)], 0.9)
    vein = lambda X, Y: vein_l(q2(X), q2(Y))     # 2칸 굵기 (겉이 울퉁불퉁해 가는 줄은 element 가 많이 쪼개진다)
    face_paint(w, lambda X, Y: vein(X, Y), "cry", only=["rock", "iron"])
    stars = [(-4.5, CY + 3.5), (3.5, CY - 4.5), (-1.5, CY - 5.5), (5.5, CY + 4.5), (-6.5, CY - 0.5), (1.5, CY + 6.5)]
    face_paint(w, lambda X, Y: np.any([(np.abs(X - sx) < 0.6) & (np.abs(Y - sy) < 0.6) for sx, sy in stars], axis=0),
               "star", only=["rock", "iron"])
    # 우는 흑요석 송곳: 긴 쪽은 오른쪽으로 휘어 내려가고, 짧은 맞송곳은 왼쪽
    long_, _ = diamond_arm(2, 22.5, lambda u: CY + 1 - 8.0 * u ** 1.8, lambda u: 3.2 * (1 - u) ** 0.85 + 0.5,
                           lambda u: 2.8 * (1 - u) ** 0.7 + 0.6, side=1)
    short, _ = diamond_arm(2, 16, lambda u: CY - 3.0 * u ** 1.5, lambda u: 2.8 * (1 - u) ** 0.85 + 0.5,
                           lambda u: 2.5 * (1 - u) ** 0.7 + 0.6, side=-1)
    w.fill(lambda X, Y, Z: long_(X, Y, Z) | short(X, Y, Z), "obs")
    # 흑요석의 보라 눈물 (드문드문, 겉면)
    face_paint(w, lambda X, Y: ((np.floor(X / 2) * 3 + np.floor(Y / 2) * 5) % 7 == 0) & (np.abs(X) > 8), "cry", only=["obs"])
    return w


# ─────────────────────────── prism ───────────────────────────

def prism_pickaxe():
    """프리즘 곡괭이: 가늘고 좌우 대칭인 두 프리즘 날 — 흰 다이아몬드 날끝, 왼쪽 자홍·오른쪽 청록 결정, 가운데로 흐르는 무지개 심지. 은 자루, 눈엔 무지개 보석."""
    m = {
        "silver": Mat(["#6a7080", "#9aa0b0", "#c8ced8", "#f4f6fa"], "metal", seed=361),
        "facet": Mat(["#c8d0f0", "#e0e6ff", "#f4f6ff", "#ffffff"], "metal", seed=362),
        "magenta": Mat(["#4a1070", "#7420a8", "#a046d0", "#cc86ec"], "metal", seed=363),
        "cyan": Mat(["#08427a", "#1268b0", "#2c9ade", "#80d0ff"], "metal", seed=364),
        "white": Mat(["#9a9ab0", "#c4c4d4", "#e2e2ec", "#ffffff"], "grip", seed=365),
        "core": Mat(["#ff0000", "#00ff00", "#0000ff", "#ffffff"], "rainbow", glow=True, seed=366),
        "gem": Mat(["#ff0000", "#00ff00", "#0000ff", "#ffffff"], "rainbow", glow=True, seed=367),
        "heart": Mat(["#ff0000", "#00ff00", "#0000ff", "#ffffff"], "rainbow", glow=True, seed=368),
    }
    w = Weapon(m, grip_y=HB + 8.5, kind="pickaxe", seed=307)
    w.box(-1, 1, HB + 2, CY, -1, 1, "silver")                   # 가는 은 자루 (2x2)
    w.cyl(HB + 3, HB + 15, 1.8, "white")
    for y in (HB + 2, HB + 15, CY - 12):
        w.box(-1.5, 1.5, y, y + 1.2, -1.5, 1.5, "silver")
    # 자루 끝: 아래로 뾰족한 작은 무지개 결정
    w.fill(lambda X, Y, Z: (Y <= HB + 2) & (Y >= HB - 2) & (np.abs(X) + np.abs(Z) <= 0.6 + (Y - HB + 2) * 0.6), "gem")
    yc = lambda u: CY - 6.5 * u ** 1.7
    hh = lambda u: 4.0 * (1 - u) ** 0.85 + 0.5
    for s, col in ((1, "cyan"), (-1, "magenta")):
        uu = arm_u(3, 20, s)

        def blade(X, Y, Z, s=s, uu=uu):
            u = uu(X)
            dy = np.abs(Y - yc(u))
            hzz = np.where(hh(u) - dy >= 1.6, 1.5, 0.5)          # 마름모 단면: 가운데 줄이 두껍고 날은 얇다
            return (X * s >= 3) & (X * s <= 20) & (dy <= hh(u)) & (np.abs(Z) <= hzz)

        w.fill(blade, "facet")
        paint(w, lambda X, Y, Z, blade=blade, uu=uu: blade(X, Y, Z) & (np.abs(Y - yc(uu(X))) <= hh(uu(X)) - 1.0), col)
        paint(w, lambda X, Y, Z, blade=blade, uu=uu: blade(X, Y, Z) & (np.abs(Y - yc(uu(X))) <= 0.6) & (uu(X) < 0.8), "core")
    w.box(-3, 3, CY - 5, CY + 5, -2.5, 2.5, "silver")             # 눈
    w.gem(0, CY, 1.8, "heart", frame="facet", depth=3.4)
    # 윗 장식: 위로 뾰족한 작은 마름모 결정
    w.fill(lambda X, Y, Z: (Y >= CY + 5) & (Y <= 64) & (np.abs(X) + np.abs(Z) <= 2.4 - (Y - CY - 5) * 0.3), "facet")
    # 아우라는 눈의 보석에서만 피어오른다 (날 전체에서 피우면 인벤토리에서 날 모양이 가려진다)
    w.set_aura("prism", "holy", size=0.8, focus=["heart"])
    return w


# ─────────────────────────── 등록 ───────────────────────────

WEAPONS = {
    "pioneer_pickaxe": pioneer_pickaxe,
    "miner_pickaxe": miner_pickaxe,
    "amethyst_pickaxe": amethyst_pickaxe,
    "deep_pickaxe": deep_pickaxe,
    "magma_pickaxe": magma_pickaxe,
    "meteor_pickaxe": meteor_pickaxe,
    "prism_pickaxe": prism_pickaxe,
}

NAMES = {
    "pioneer_pickaxe": "개척자의 곡괭이",
    "miner_pickaxe": "광부의 곡괭이",
    "amethyst_pickaxe": "자수정 곡괭이",
    "deep_pickaxe": "심층 곡괭이",
    "magma_pickaxe": "용암 곡괭이",
    "meteor_pickaxe": "운석 곡괭이",
    "prism_pickaxe": "프리즘 곡괭이",
}

if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids:
        sub = {k: WEAPONS[k] for k in ids}
        out = os.path.join(HERE, "preview", "_scratch", "pickaxes_part.png")
        preview_sheet(sub, out, names=NAMES)
    else:
        preview_sheet(WEAPONS, os.path.join(HERE, "preview", "pickaxes.png"), names=NAMES)
