"""
axes_hammers: 도끼와 망치 12 자루.

python3 axes_hammers.py            -> preview/axes_hammers.png
python3 axes_hammers.py id1 id2    -> 그 무기만 preview/_scratch/axes_hammers_part.png
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


def padded(mats):
    """
    미리보기 렌더러는 면 가장자리 한 줄을 옆 아틀라스 칸에서 집어 온다 (16 경계마다 다른 색 줄이 생김).
    그래서 재료마다 같은 재료의 복사본을 옆(과 가능하면 아래)에 둔다.
    고정 재료: 4개 이하면 2x2 블록, 8개 이하면 가로 쌍 [A A' B B'] (위아래로 붙는 재료는 비슷한 색이 되게 순서를 정한다).
    움직이는 재료(2x2 칸): 2개 이하면 가로 쌍.
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


def shrink(mask, d):
    """2D 마스크를 d 만큼 안으로 줄인다 (8방향 검사)."""
    k = d * 0.7071
    return lambda X, Y: (mask(X + d, Y) & mask(X - d, Y) & mask(X, Y + d) & mask(X, Y - d)
                         & mask(X + k, Y + k) & mask(X - k, Y - k) & mask(X + k, Y - k) & mask(X - k, Y + k))


def surface_shell(solid):
    """solid(X,Y,Z) 바로 바깥 한 겹 (덩굴, 끈을 표면에 감을 때)."""
    def f(X, Y, Z):
        near = (solid(X + 1, Y, Z) | solid(X - 1, Y, Z) | solid(X, Y + 1, Z) | solid(X, Y - 1, Z)
                | solid(X, Y, Z + 1) | solid(X, Y, Z - 1))
        return near & ~solid(X, Y, Z)
    return f


def rmask(x0, x1, y0, y1, z0, z1, c=1.0):
    """한 칸 계단으로 모서리를 깎은 상자 (세 상자의 합). 대각선 깎기보다 요소가 훨씬 적다."""
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


def q2(V, off=0.0):
    """2복셀 단위로 좌표를 묶는다 (윤곽이 2칸씩 계단 → 요소 수 절반, 더 마크다운 덩어리감)."""
    return np.floor((V - off) / 2) * 2 + 1 + off


def sprite(rows, x0, y_top, px, py, depth, flip=False):
    """픽셀 그림(문자열 줄, 위→아래)을 px*py 복셀 칸으로 키운 마스크."""
    H = len(rows)
    Wd = max(len(r) for r in rows)
    grid = np.array([[c == "#" for c in r.ljust(Wd, ".")] for r in rows], bool)

    def f(X, Y, Z):
        cx = np.floor((X - x0) / px).astype(int)
        if flip:
            cx = Wd - 1 - np.floor((x0 - X) / px).astype(int)
        cy = np.floor((y_top - Y) / py).astype(int)
        ok = (cx >= 0) & (cx < Wd) & (cy >= 0) & (cy < H) & (np.abs(Z) <= depth)
        out = np.zeros(np.shape(X), bool)
        out[ok] = grid[cy[ok], cx[ok]]
        return out
    return f


def line2d(pts, r):
    """XY 꺾은선까지 거리가 r 이하인 2D 마스크 (몸통 안에서만 쓰는 금, 홈 등)."""
    P = np.array(pts, float)

    def m(X, Y):
        d = np.full(np.shape(X), 1e9)
        for (x1, y1), (x2, y2) in zip(P[:-1], P[1:]):
            dx, dy = x2 - x1, y2 - y1
            t = np.clip(((X - x1) * dx + (Y - y1) * dy) / (dx * dx + dy * dy), 0, 1)
            d = np.minimum(d, np.hypot(X - x1 - t * dx, Y - y1 - t * dy))
        return d <= r
    return m


def lash_loop(w, cx, y0, slope, hx, hz, r, mat):
    """자루 둘레를 비스듬히 한 바퀴 감는 끈 (앞은 왼쪽 아래→오른쪽 위)."""
    pts = [(-hx, y0 - slope * hx, hz), (hx, y0 + slope * hx, hz), (hx, y0 + slope * hx, -hz),
           (-hx, y0 - slope * hx, -hz), (-hx, y0 - slope * hx, hz)]
    w.tube([(cx + x, y, z) for x, y, z in pts], r, mat)


# ─────────────────────────── basic ───────────────────────────

def woodcutter_axe():
    """평범한 외날 도끼: 곧은 나무 자루, 아래로 처진 수염날, 짧은 망치머리, 붉은 플란넬 손잡이."""
    m = {
        "iron": Mat(["#2e3036", "#454850", "#5e626a", "#777c84"], "metal", seed=3),
        "edge": Mat(["#8a9098", "#aeb4bc", "#d0d6dc", "#f2f5f8"], "metal", seed=4),
        "wood": Mat(["#4a2c14", "#74471f", "#9b6630", "#c08a4c"], "wood", seed=1),
        "flannel": Mat(["#4a0e0c", "#7a1a14", "#a82c20", "#cc4a32"], "cloth", seed=2),
    }
    w = Weapon(padded(m), grip_y=9, kind="axe", seed=101)
    w.cyl(0, 57, 1.6, "wood")
    w.cyl(0, 2, 2.2, "wood")                              # 자루 끝 혹
    w.cyl(3, 15, 1.9, "flannel")
    w.cyl(15, 16, 2.0, "iron")                            # 손잡이 끝 쇠고리

    def top(X):
        return 54 + np.clip(X - 4, 0, None) * 0.4

    def bot(X):
        return 47 - np.clip(X - 4, 0, None) ** 1.3 * 0.45

    def xe(Y):
        return 15 + 2.0 * (1 - ((Y - 49) / 11) ** 2)

    prof = lambda X, Y: (X >= 0) & (X <= xe(Y)) & (Y >= bot(X)) & (Y <= top(X))
    # 두께 세 단: 볼 2.5 / 경사 1.5 / 날 1
    w.fill(lambda X, Y, Z: prof(X, Y) & (X <= xe(Y) - 6) & (np.abs(Z) <= 2.5), "iron")
    w.fill(lambda X, Y, Z: prof(X, Y) & (X > xe(Y) - 6) & (X <= xe(Y) - 2.5) & (np.abs(Z) <= 1.5), "iron")
    w.fill(lambda X, Y, Z: prof(X, Y) & (X > xe(Y) - 2.5) & (np.abs(Z) <= 1), "edge")
    w.box(-3, 3, 45, 55, -3, 3, "iron")                   # 자루 구멍(눈)
    w.box(-1.5, 1.5, 57, 58, -0.5, 0.5, "iron")           # 자루 끝 쐐기
    w.box(-6.5, -3, 46.5, 53.5, -2.2, 2.2, "iron")        # 뒤쪽 짧은 망치머리
    return w


def stone_hammer():
    """막대기에 덩굴로 묶은 울퉁불퉁한 돌덩이: 한쪽으로 솟은 윗면, 옆 혹, 크게 떨어져 나간 앞 모서리."""
    m = {
        "stone": Mat(["#5c5c60", "#7a7a7e", "#9a9a9e", "#bcbcc0"], "stone", seed=11),
        "fresh": Mat(["#7e7a76", "#96928c", "#aeaaa4", "#c6c2bc"], "stone", seed=16),
        "cobble": Mat(["#28282c", "#38383c", "#4a4a4e", "#5c5c60"], "stone", seed=12),
        "vine": Mat(["#1e4a12", "#2e6a1a", "#46902a", "#62b03a"], "grip", seed=14),
        "stick": Mat(["#3e2812", "#5c3c1c", "#7a522a", "#96683a"], "wood", seed=13),
        "rag": Mat(["#6a5a44", "#8a7a5e", "#a89a7c", "#c4b898"], "cloth", seed=15),
    }
    w = Weapon(padded(m), grip_y=11, kind="hammer", seed=102)
    w.cyl(0, 46, 1.6, "stick")
    w.cyl(4, 18, 2.0, "rag")
    cy = 52
    lumps = [rmask(-9, 9, cy - 6, cy + 5, -5.5, 5.5, 2), rmask(-2, 7, cy + 3, cy + 9, -4, 4.5, 1.5),
             rmask(7, 12.5, cy - 6.5, cy + 1, -4, 3.5, 1.5), rmask(-11.5, -7, cy - 5, cy + 1.5, -4, 4, 1.5)]
    chip = lambda X, Y, Z: (X <= -3.5) & (Y >= cy + 0.5) & (Z >= 2)       # 떨어져 나간 앞 왼쪽 위

    def chunk(X, Y, Z):
        out = np.zeros(np.shape(X), bool)
        for f in lumps:
            out |= f(X, Y, Z)
        return out & ~chip(X, Y, Z)

    w.fill(chunk, "stone")
    for (a, b, c, d, e, f) in ((-8, -3, cy - 5, cy - 1, 3.5, 6), (1, 5, cy - 2, cy + 2, 3.5, 6),
                               (3, 8, cy - 6, cy - 2, -6, -3.5), (-6, -1, cy + 1, cy + 5, -6, -3.5),
                               (10.5, 13, cy - 5, cy - 1, -1, 4), (1, 5, cy + 7, cy + 10, -2, 2), (-12, -9, cy - 3, cy + 1, -2, 2)):
        w.fill(lambda X, Y, Z, a=(a, b, c, d, e, f): chunk(X, Y, Z) & (X >= a[0]) & (X <= a[1]) & (Y >= a[2])
               & (Y <= a[3]) & (Z >= a[4]) & (Z <= a[5]), "cobble")
    w.fill(lambda X, Y, Z: chunk(X, Y, Z) & chip(X - 1, Y + 1, Z + 1), "fresh")      # 깨진 면은 밝은 속살
    # 덩굴: 돌 표면 바로 바깥을 두 바퀴 (한 줄은 비스듬히)
    sh = surface_shell(chunk)
    w.fill(lambda X, Y, Z: sh(X, Y, Z) & (np.abs(X + 4.5) <= 1.0), "vine")
    w.fill(lambda X, Y, Z: sh(X, Y, Z) & (np.abs(X - 3.5 + np.floor((Y - cy) / 3) * 1.0) <= 1.0), "vine")
    w.cyl(41, 45, 2.1, "vine")
    w.tube([(1.5, 42, 1.8), (3, 38, 2), (2.5, 34, 1.5)], 0.75, "vine")
    return w


def thorn_club():
    """선인장 한 줄기를 통째로: 네모난 줄기, 위로 꺾여 오른 긴 곁가지, 가시, 꽃 한 송이, 비스듬히 감은 노끈."""
    m = {
        # 아틀라스 칸 순서: 선인장 아래 칸이 같은 초록(rib)이 되게 (경계 번짐 방지)
        "cactus": Mat(["#245a1a", "#347a26", "#4a9634", "#66b04a"], "stone", seed=21),
        "flower": Mat(["#a0204a", "#d84a7a", "#f07aa0", "#ffc0d4"], "flat", seed=25),
        "rib": Mat(["#143a10", "#1c4e16", "#24601c", "#2e7224"], "flat", seed=22),
        "cut": Mat(["#8aa860", "#a8c47a", "#c4dc9a", "#dcecb8"], "flat", seed=26),
        "spine": Mat(["#a89a60", "#c8bc80", "#e4dca8", "#fff8d8"], "flat", seed=23),
        "twine": Mat(["#7a6440", "#a08658", "#c0a878", "#dccaa0"], "grip", seed=24),
    }
    w = Weapon(padded(m), grip_y=8, kind="hammer", seed=103)

    def hw(Y):
        h = np.clip(2 + (Y - 14) / 7.0, 2, 5)
        top = np.sqrt(np.clip(1 - ((Y - 47) / 6.5) ** 2, 0, 1)) * 5
        return np.where(Y > 47, top, h)

    def stem(X, Y, Z):
        return (np.maximum(np.abs(X), np.abs(Z)) <= hw(Y)) & (Y >= 0) & (Y <= 54)

    w.fill(stem, "cactus")
    w.fill(lambda X, Y, Z: stem(X, Y, Z) & (np.abs(X) > hw(Y) - 1) & (np.abs(Z) > hw(Y) - 1) & (Y > 16) & (Y < 47), "rib")
    w.box(-2, 2, 0, 1, -2, 2, "cut")                      # 잘린 밑동
    # 곁가지: 옆으로 나와 위로 길게 꺾여 오른다
    w.box(3, 11, 24, 29, -2, 2, "cactus")
    w.box(7, 11, 24, 44, -2, 2, "cactus")
    w.box(7.5, 10.5, 44, 45.5, -1.5, 1.5, "cactus")
    for (x0, z0) in ((7, 1), (10, 1), (7, -2), (10, -2)):
        w.box(x0, x0 + 1, 29, 43, z0, z0 + 1, "rib")
    # 가시: 줄기 옆면(±X)과 앞뒤(±Z)
    for i, y in enumerate(range(20, 48, 5)):
        h = float(hw(np.array(y + 0.5)))
        o = 1.5 if i % 2 else -1.5
        for s in (-1, 1):
            if not (s > 0 and 22 <= y <= 30):
                w.box(s * h if s > 0 else -h - 2.2, s * h + 2.2 if s > 0 else -h, y, y + 0.9, o - 0.5, o + 0.5, "spine")
            w.box(-o - 0.5, -o + 0.5, y + 2, y + 2.9, s * h if s > 0 else -h - 2, s * h + 2 if s > 0 else -h, "spine")
    for y in (32, 37, 42):
        w.box(11, 13, y, y + 0.9, -0.5, 0.5, "spine")
    for y in (34, 40):
        w.box(8.5, 9.5, y, y + 0.9, 2, 4, "spine")
    # 손잡이: 제각각 기울어진 가는 노끈 네 바퀴
    for (y0, sl) in ((3, 0.3), (6.5, -0.2), (10, 0.35), (13.5, -0.3)):
        lash_loop(w, 0, y0, sl, 2.5, 2.5, 0.7, "twine")
    w.tube([(2.5, 13.5 - 0.75, 2.5), (3.5, 11, 3), (3.2, 9, 3.2)], 0.6, "twine")   # 늘어진 매듭 끝
    w.box(-4.2, -2, 4.5, 5.4, -0.5, 0.5, "spine")
    w.box(2, 4.2, 11.5, 12.4, -0.5, 0.5, "spine")
    # 꼭대기 꽃
    w.box(-2, 2, 53, 55, -2, 2, "flower")
    w.box(-1, 1, 55, 56, -1, 1, "spine")
    return w


def smith_hammer():
    """대장간 망치: 짧은 자루, 한쪽은 넓은 평면, 반대쪽은 쐐기(크로스핀)."""
    m = {
        "iron": Mat(["#2c2f34", "#464a50", "#5e636a", "#787d84"], "metal", seed=31),
        "face": Mat(["#7a7e84", "#a4a8ae", "#ccd0d4", "#f4f6f8"], "metal", seed=32),
        "ash": Mat(["#6a4a2a", "#8e6a40", "#b08a58", "#ccaa74"], "wood", seed=33),
        "leather": Mat(["#3a1e10", "#5a2e18", "#7a4224", "#965634"], "grip", seed=34),
    }
    w = Weapon(padded(m), grip_y=8, kind="hammer", seed=104)
    w.cyl(0, 42, 1.6, "ash")
    w.cyl(0, 2, 2.1, "ash")
    w.cyl(2, 14, 1.9, "leather")
    w.box(-2.9, 2.9, 25, 32, -0.9, 0.9, "iron")          # 양쪽 쇠띠(랑겟)
    cy = 37
    w.box(-3.5, 3.5, cy - 6, cy + 5, -3.5, 3.5, "iron")    # 눈
    w.box(-11, -3, cy - 4, cy + 4, -3, 3, "iron")          # 평면 쪽 몸통
    w.box(-14, -11, cy - 5, cy + 5, -3.6, 3.6, "iron")     # 넓어지는 머리
    w.box(-15, -14, cy - 4.5, cy + 4.5, -3.2, 3.2, "face")  # 반질반질한 치는 면

    def peen(X, Y, Z):
        h = 4.5 - (X - 3) * 0.36
        return (X >= 3) & (X <= 14) & (np.abs(Y - cy) <= h) & (np.abs(Z) <= 3)

    w.fill(peen, "iron")
    w.fill(lambda X, Y, Z: peen(X, Y, Z) & (X > 12), "face")
    w.box(-1.5, 1.5, cy + 5, cy + 6, -0.5, 0.5, "face")    # 자루에 박은 쐐기
    return w


# ─────────────────────────── island ───────────────────────────

def earth_hammer():
    """떠 있는 섬 한 덩이: 풀 덮인 윗판, 아래로 뾰족하게 좁아지는 흙/돌 뿌리, 금광맥, 매달린 뿌리, 작은 나무."""
    m = {
        "grass": Mat(["#2f5a16", "#46801f", "#5ea02c", "#80c040"], "cloth", seed=41),
        "dirt": Mat(["#4a2e18", "#6a4224", "#8a5a34", "#a87448"], "stone", seed=42),
        "stone": Mat(["#4c4a48", "#6e6a66", "#8e8a84", "#aca8a0"], "stone", seed=43),
        "deep": Mat(["#26242a", "#38363e", "#4c4a52", "#605e68"], "stone", seed=44),
        "root": Mat(["#3a2414", "#5a3a1e", "#7a522c", "#96703e"], "wood", seed=45),
        "ore": Mat(["#8a6a10", "#d0a020", "#f0d050", "#fff6b0"], "metal", seed=46),
        "leaf": Mat(["#1e4a14", "#2e6a1e", "#3e8a28", "#58a83a"], "stone", seed=47),
        "rope": Mat(["#6a5a3a", "#94805a", "#bca67a", "#dccaa0"], "grip", seed=48),
    }
    w = Weapon(padded(m), grip_y=11, kind="hammer", seed=105)
    w.tube([(0, 0, 0), (0.6, 14, 0), (-0.5, 30, 0), (0.3, 46, 0)], 1.9, "root")
    w.cyl(4, 18, 2.2, "rope")
    w.ball(0, 2, 0, 3, 2.5, 3, "stone")                       # 밑동 돌
    x0, z0, ytop = 12, 6.5, 64

    def slab(X, Y, Z):                                         # 윗판 (풀/흙)
        return (np.abs(X) <= x0) & (Y >= 55) & (Y <= ytop - 0.1) & (np.abs(Z) <= z0)

    def cone(X, Y, Z):                                         # 아래로 좁아지는 섬 밑
        k = np.floor((Y - 39) / 2.0)
        rx = 2.5 + k * 1.3 * np.where(X > 0, 1.0, 0.85)
        rz = np.minimum(z0, 1.8 + k * 0.62)
        return (Y >= 39) & (Y < 55) & (np.abs(X) <= rx) & (np.abs(Z) <= rz)

    isl = lambda X, Y, Z: slab(X, Y, Z) | cone(X, Y, Z)
    w.fill(isl, "stone")
    w.fill(lambda X, Y, Z: isl(X, Y, Z) & (Y < 46), "deep")
    w.fill(lambda X, Y, Z: isl(X, Y, Z) & (Y >= 53), "dirt")
    # 풀: 윗면 + 옆으로 들쭉날쭉 내려오는 풀 (마크 잔디 블록 옆면처럼)
    w.fill(lambda X, Y, Z: slab(X, Y, Z) & ((Y >= 61) | ((Y >= 59) & ((np.floor((X + Z + 40) / 2) % 3) == 0))), "grass")
    # 금광맥: 비스듬히 갈라진 줄기 하나 + 가지
    vein = lambda X, Y: (np.abs(X - (-6 + (54 - Y) * 0.9)) <= 1.1) & (Y >= 46) & (Y <= 54)
    vein2 = lambda X, Y: (np.abs(X - (-1 + (50 - Y) * -1.1)) <= 1.0) & (Y >= 46) & (Y <= 50)
    w.fill(lambda X, Y, Z: isl(X, Y, Z) & (vein(X, Y) | vein2(X, Y)), "ore")
    # 매달린 뿌리 둘
    w.tube([(-10, 55.5, 3), (-10.5, 51, 3.5), (-9.5, 46, 3.5), (-10.5, 41, 3)], lambda t: 1.2 - 0.6 * t, "root")
    w.tube([(10.5, 55.5, -2), (11, 51.5, -2.5), (10, 48, -2.5)], lambda t: 1.1 - 0.4 * t, "root")
    # 작은 나무 (스카이블럭의 첫 나무)
    w.box(-8, -6, 64, 68, -1, 1, "root")
    w.box(-10.5, -3.5, 67, 71, -2.5, 2.5, "leaf")
    w.box(-9, -5, 71, 72, -1, 1, "leaf")
    return w


def thunder_hammer():
    """구리 피뢰침 망치: 한쪽에만 붙은 작은 구리 북통, 반대쪽 사기 애자, 위로 길게 솟은 코일 감긴 피뢰침과 유리구."""
    m = {
        "copper": Mat(["#6a3014", "#a8542a", "#d07a44", "#f0a070"], "metal", seed=52),
        "steel": Mat(["#1e2128", "#343844", "#4e5462", "#6e7484"], "metal", seed=51),
        "leather": Mat(["#4a2e14", "#74481e", "#9c6a34", "#c08c50"], "grip", seed=54),
        "porcelain": Mat(["#8a8a92", "#b8b8c0", "#dcdce2", "#f8f8fc"], "metal", seed=53),
        "glass": Mat(["#3a5aa0", "#6a90e0", "#a8ccff", "#ffffff"], "sparkle", glow=True, seed=56),
    }
    w = Weapon(padded(m), grip_y=10, kind="hammer", seed=106)
    w.cyl(0, 52, 1.6, "steel")
    w.cyl(3, 17, 2.0, "leather")
    rbox(w, -2.5, 2.5, 0, 3, -2.5, 2.5, 1, "copper")          # 구리 폼멜
    w.cyl(17, 18.5, 2.2, "copper")
    cy = 44

    def octx(x0, x1, r):                                       # X 로 누운 팔각 기둥
        c = max(1.0, round(r * 0.35))
        ay = lambda Y: np.abs(Y - cy)
        return lambda X, Y, Z: ((X >= x0) & (X <= x1) & (((ay(Y) <= r) & (np.abs(Z) <= r - c))
                                                          | ((ay(Y) <= r - c) & (np.abs(Z) <= r))))

    rbox(w, -2.5, 2.5, cy - 6, cy + 6, -2.5, 2.5, 0.5, "copper")   # 자루 꽂는 통
    # -X: 작은 구리 북통 + 굵은 강철 띠 + 치는 면
    w.fill(octx(-12, -2, 4.6), "copper")
    for a, b in ((-10.5, -9), (-5.5, -4)):
        w.fill(octx(a, b, 5.6), "steel")
    w.fill(octx(-14, -12, 5.0), "steel")
    # +X: 사기 애자 셋
    w.fill(octx(2, 9, 1.5), "steel")
    for x in (3, 5.5, 8):
        w.fill(octx(x, x + 1.2, 3.2), "porcelain")
    w.fill(octx(9, 10.5, 2.0), "copper")
    # 피뢰침: 강철 대 + 도드라진 구리 코일
    w.cyl(cy + 6, 64, 1.5, "steel")
    for y in (51, 54, 57, 60):
        w.cyl(y, y + 1.6, 2.6, "copper")
    rbox(w, -2.6, 2.6, 62, 67.5, -2.6, 2.6, 1, "glass")        # 유리구 (작은 빛)
    w.fill(lambda X, Y, Z: (Y >= 67.5) & (Y <= 72) & (np.maximum(np.abs(X), np.abs(Z)) <= 1.6 - (Y - 67.5) * 0.25), "copper")
    for s in (-1, 1):                                          # 피뢰침 갈래
        w.box(s * 1 if s > 0 else -4, 4 if s > 0 else -1, 67.5, 68.5, -0.6, 0.6, "copper")
        w.box(s * 3 if s > 0 else -4, 4 if s > 0 else -3, 68.5, 71, -0.6, 0.6, "copper")
    return w


def holy_hammer():
    """성기사의 전투망치: 긴 자루, 한쪽은 태양을 새긴 평평한 치는 면, 반대쪽은 아래로 굽은 부리, 위로 긴 창끝, 술."""
    m = {
        "steel": Mat(["#7a8090", "#a4aab8", "#ccd2dc", "#f4f6fa"], "metal", seed=61),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff0a0"], "metal", seed=62),
        "blue": Mat(["#14246a", "#22409a", "#3a64c8", "#5a88e8"], "cloth", seed=63),
        "haft": Mat(["#8a7a64", "#b0a084", "#d0c4a8", "#ece4cc"], "wood", seed=64),
        "sun": Mat(["#c08010", "#ffc030", "#ffe890", "#ffffff"], "pulse", glow=True, seed=65),
        "grip": Mat(["#0c1440", "#18265e", "#263a84", "#3450a8"], "grip", seed=66),
    }
    w = Weapon(padded(m), grip_y=10, kind="hammer", seed=107)
    w.cyl(0, 62, 1.6, "haft")
    w.cyl(3, 17, 1.9, "grip")
    w.cyl(0, 3, 2.4, "gold")
    w.cyl(17, 18, 2.1, "gold")
    w.box(-0.6, 0.6, 38, 50, -2.1, 2.1, "gold")            # 랑겟
    cy = 56
    w.box(-3, 3, cy - 5, cy + 5, -3, 3, "steel")           # 소켓
    w.box(-3.4, 3.4, cy - 6.5, cy - 5, -3.4, 3.4, "gold")
    w.box(-3.4, 3.4, cy + 5, cy + 6, -3.4, 3.4, "gold")
    # 십자 상감 (소켓 앞뒤)
    for s in (-1, 1):
        a, b = sorted((s * 2.6, s * 3.4))
        w.box(-1, 1, cy - 4, cy + 4, a, b, "gold")
        w.box(-2.6, 2.6, cy + 0.6, cy + 2.4, a, b, "gold")
    # -X: 목 + 넓어지는 망치 머리 + 태양 면
    w.box(-8, -3, cy - 3, cy + 3, -3, 3, "steel")
    w.box(-12, -8, cy - 4.5, cy + 4.5, -4.5, 4.5, "steel")
    w.box(-13, -12, cy - 4, cy + 4, -4, 4, "gold")
    w.fill(lambda X, Y, Z: (X >= -14) & (X <= -13) & (((np.abs(Y - cy) <= 1.6) & (np.abs(Z) <= 1.6))
                                                      | ((np.abs(Y - cy) <= 3.6) & (np.abs(Z) <= 0.6))
                                                      | ((np.abs(Z) <= 3.6) & (np.abs(Y - cy) <= 0.6))), "sun")
    # +X: 아래로 굽은 까마귀 부리
    w.box(3, 4.6, cy - 3.4, cy + 3.4, -3.4, 3.4, "gold")
    w.tube([(4, cy, 0), (9, cy + 0.6, 0), (13.5, cy - 1.5, 0), (16.5, cy - 6, 0), (17, cy - 9, 0)],
           lambda t: 2.9 - 2.2 * t, "steel", rz=lambda t: 2.4 - 1.8 * t)
    # 위: 마름모 단면 창끝
    w.fill(lambda X, Y, Z: (Y >= cy + 6) & (Y <= 72) & (np.abs(X) + np.abs(Z) * 1.3 <= 3.6 - (Y - cy - 6) * 0.2), "steel")
    w.box(-2, 2, cy + 6, cy + 7, -2, 2, "gold")
    # 술: 치는 면 목 아래에 매단, 아래로 넓어지는 푸른 술 + 금매듭
    tx = -6.5
    w.box(tx - 0.5, tx + 0.5, cy - 6, cy - 3, -0.5, 0.5, "gold")
    w.box(tx - 1, tx + 1, cy - 8, cy - 6, -1, 1, "gold")

    def tassel(X, Y, Z):
        h = 0.9 + (cy - 8 - Y) * 0.17
        return (Y >= cy - 19) & (Y < cy - 8) & (np.abs(X - tx) <= h) & (np.abs(Z) <= h * 0.8)

    w.fill(tassel, "blue")
    w.box(tx - 1.6, tx + 1.6, cy - 11, cy - 10, -1.4, 1.4, "gold")
    w.clear(lambda X, Y, Z: tassel(X, Y, Z) & (Y < cy - 16) & ((np.floor(X - tx + 10) % 2) == 1))   # 술 끝 가닥
    return w


def earth_axe():
    """쪼갠 바위 양날 도끼(라브리스): 큼직하게 떼어 낸 부싯돌 날, X 자로 감은 밧줄, 짙은 화석 나무 자루."""
    m = {
        "rock": Mat(["#3e3832", "#5e554c", "#80766a", "#a29888"], "stone", seed=71),
        "flint": Mat(["#22262e", "#3c424e", "#606a7a", "#96a2b4"], "crystal", seed=72),
        "petri": Mat(["#1e1a18", "#302a26", "#463e38", "#5c524a"], "wood", seed=74),
        "rope": Mat(["#5a3018", "#844822", "#ac6634", "#cc8a4c"], "grip", seed=75),
    }
    w = Weapon(padded(m), grip_y=11, kind="axe", seed=108)
    w.cyl(0, 63, 1.7, "petri")
    w.cyl(4, 18, 2.1, "rope")
    rbox(w, -2.5, 2.5, 62, 66, -2.5, 2.5, 1, "rock")
    rbox(w, -2.5, 2.5, 0, 3, -2.5, 2.5, 1, "rock")
    pts = [(1, 45), (6, 43), (11, 39), (16, 40), (17.5, 46), (18, 52), (16.5, 59), (12, 62), (7, 58), (1, 57)]
    raw = poly(pts)
    bit = lambda X, Y: raw(X, q2(Y))
    edge = lambda X, Y: bit(X, Y) & ~bit(X + 3, Y) & (X > 11)
    w.fill(lambda X, Y, Z: bit(X, Y) & (X >= 0) & ~edge(X, Y) & (np.abs(Z) <= np.where(X < 7, 3.0, 2.0)), "rock")
    w.fill(lambda X, Y, Z: edge(X, Y) & (np.abs(Z) <= 1.0), "flint")
    # 큼직한 떼어 낸 홈 (날 쪽)
    for (yc, ex, dep) in ((44, 17.5, 3.5), (56, 17.5, 3.5)):
        w.clear(lambda X, Y, Z, yc=yc, ex=ex, dep=dep: (X > ex - dep) & (np.abs(Y - yc) <= (X - (ex - dep)) * 0.8))
    w.mirror()
    rbox(w, -3, 3, 44, 58, -3.2, 3.2, 0.5, "rock")
    # 밧줄: 위아래 한 바퀴씩 + 가운데 X 자
    w.box(-3.6, 3.6, 44.5, 46, -3.8, 3.8, "rope")
    w.box(-3.6, 3.6, 56, 57.5, -3.8, 3.8, "rope")
    for sl in (0.6, -0.6):
        lash_loop(w, 0, 51, sl, 3.7, 3.9, 0.75, "rope")
    return w


def wind_axe():
    """폭풍의 도끼: 넓게 휘어 오른 초승달 날이 자루 위로 말려 넘어가고, 날에는 소용돌이 바람구멍, 자루엔 휘날리는 붉은 끈."""
    m = {
        "sky": Mat(["#284e7a", "#3a6ea0", "#5a94c8", "#88bce8"], "metal", seed=82),
        "silver": Mat(["#6a7684", "#9aa8b6", "#c8d2dc", "#f4f8fc"], "metal", seed=81),
        "wrap": Mat(["#14163a", "#222660", "#343a86", "#4a52a8"], "grip", seed=84),
        "birch": Mat(["#8a8478", "#b4ae9e", "#d4cebe", "#eeeadc"], "wood", seed=83),
        "ribbon": Mat(["#8a1e2e", "#c0343e", "#e05a58", "#ff8a7a"], "cloth", seed=85),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff0a0"], "metal", seed=87),
    }
    w = Weapon(padded(m), grip_y=12, kind="axe", seed=109)
    w.cyl(0, 62, 1.6, "birch")
    w.cyl(4, 20, 1.9, "wrap")
    for y in (20, 38):
        w.cyl(y, y + 1.2, 2.1, "gold")
    w.cyl(0, 1.5, 2.2, "gold")
    w.fill(lambda X, Y, Z: (Y >= 62) & (Y <= 65) & (np.maximum(np.abs(X), np.abs(Z)) <= 1.6 - (Y - 62) * 0.4), "silver")
    outer = [(1, 49), (4, 47), (8, 42), (11, 37), (13.5, 33), (15, 38), (16.5, 44), (17.5, 51), (17, 58),
             (15, 64), (11.5, 68.5), (6.5, 71.5), (1, 72), (-4, 70.5), (-1, 69), (3, 68.5), (6.5, 66.5),
             (8, 63), (6, 59), (1, 57)]
    raw = poly(outer)
    blade = lambda X, Y: raw(X, q2(Y))
    core = shrink(blade, 2.6)
    # 부피: 가운데 4~6 두께 → 날 2
    w.fill(lambda X, Y, Z: blade(X, Y) & (np.abs(Z) <= 1), "silver")
    w.fill(lambda X, Y, Z: core(X, Y) & (np.abs(Z) <= np.where(X < 6, 2.5, 2.0)), "sky")
    # 소용돌이 바람구멍 (날을 뚫는다)
    cx, cyy = 9.5, 51.5

    def spiral(X, Y, Z):
        dx, dy = X - cx, Y - cyy
        r = np.hypot(dx, dy)
        th = np.arctan2(dy, dx)
        hit = np.zeros(np.shape(X), bool)
        for k in range(0, 2):
            arm = 0.8 + 0.6 * (th + math.pi + 2 * math.pi * k)
            hit |= (np.abs(r - arm) <= 0.8) & (arm <= 4.8)
        return hit | (r <= 1.2)

    w.clear(spiral)
    # 날 밑동 금띠와 눈
    rbox(w, -2.5, 2.5, 46, 58, -2.6, 2.6, 0.5, "sky")
    w.box(-3, 3, 45, 46.5, -3, 3, "gold")
    w.box(-3, 3, 57.5, 59, -3, 3, "gold")
    # 휘날리는 끈 두 가닥 (금매듭에서 -X 로, 넓고 납작하게)
    w.box(-3, 0, 41, 43.5, -2.2, 2.2, "gold")
    t1 = line2d([(-2.5, 42), (-7, 40.5), (-11.5, 41), (-16, 39.5)], 2.0)
    tail = lambda X, Y: t1(X, q2(Y))
    vcut = lambda X, Y: (X < -13) & (np.abs(Y - 40) < (-13 - X) * 0.9)              # 끝을 V 자로 갈라
    w.prism(lambda X, Y: tail(X, Y) & ~vcut(X, Y) & (X < -2), 0.5, "ribbon")
    return w


# ─────────────────────────── flame ───────────────────────────

def volcano_axe():
    """화산 도끼: 나무꾼 도끼를 용암에 담갔다 뺀 것 — 녹아 처진 긴 수염날(밑면이 녹아내림), 흰빛 날, 불꽃 혀 모양 뒷가시, 가지 친 용암 금."""
    m = {
        "basalt": Mat(["#363034", "#4e4548", "#685c5e", "#847676"], "stone", seed=91),
        "char": Mat(["#3a2418", "#5a3a26", "#7a5232", "#9a6a42"], "wood", seed=92),
        "ember": Mat(["#a02800", "#e05010", "#ff8a28", "#ffc060"], "flat", glow=True, seed=96),
        "ash": Mat(["#4a4440", "#6e6660", "#948a82", "#b8aea4"], "grip", seed=95),
        "magma": Mat(["#8a1a00", "#e04a08", "#ffa020", "#fff0a0"], "fire", glow=True, seed=93),
        "hot": Mat(["#c03000", "#ff7010", "#ffc040", "#fff8c0"], "pulse", glow=True, seed=94),
    }
    w = Weapon(padded(m), grip_y=10, kind="axe", seed=110)
    w.cyl(0, 61, 1.7, "char")
    rbox(w, -2.4, 2.4, 0, 2.5, -2.4, 2.4, 0.8, "basalt")
    w.cyl(3, 17, 2.0, "ash")
    for y in (21, 28, 35):                                     # 자루의 불씨 고리
        w.cyl(y, y + 1, 1.75, "ember")
    raw = poly([(3.5, 58.5), (10, 60), (15, 63.5), (18.5, 65), (20, 60), (20.5, 54), (19.5, 47), (17.5, 41),
                (15.5, 36), (13.5, 33.5), (12, 37), (10, 41), (7, 44.5), (3.5, 47)])
    head = lambda X, Y: raw(X, q2(Y))
    edge = lambda X, Y: head(X, Y) & ~head(X + 2.5, Y)                       # 앞 날
    under = lambda X, Y: head(X, Y) & ~head(X, Y - 2.5) & (X > 7)             # 녹아내리는 밑면
    w.fill(lambda X, Y, Z: head(X, Y) & ~edge(X, Y) & (np.abs(Z) <= np.where(X < 6, 2.5, 1.5)), "basalt")
    w.fill(lambda X, Y, Z: under(X, Y) & ~edge(X, Y) & (np.abs(Z) <= 1.5), "magma")
    w.fill(lambda X, Y, Z: edge(X, Y) & (np.abs(Z) <= 1), "hot")
    # 떨어져 나간 흑요석 날 두 군데
    for (yc, ex, dep) in ((56, 20.3, 2.6), (47, 19.6, 2.6)):
        w.clear(lambda X, Y, Z, yc=yc, ex=ex, dep=dep: (X > ex - dep) & (np.abs(Y - yc) <= (X - (ex - dep)) * 0.8))
    # 비스듬히 가지 친 용암 금 (날을 꿰뚫는다)
    crack = [(lambda f: (lambda X, Y: f(q2(X), q2(Y))))(line2d(p, 1.1)) for p in ([(4, 53), (8, 55.5), (12, 54), (15.5, 57.5)], [(12, 54), (13, 50)],
                                       [(5, 49.5), (9.5, 46.5), (12.5, 41)])]
    w.fill(lambda X, Y, Z: head(X, Y) & ~edge(X, Y) & (crack[0](X, Y) | crack[1](X, Y) | crack[2](X, Y))
           & (np.abs(Z) <= np.where(X < 6, 2.5, 1.5)), "magma")
    rbox(w, -3.5, 3.5, 46, 59, -3, 3, 0.8, "basalt")          # 눈
    w.box(-1.5, 1.5, 59, 60.5, -0.6, 0.6, "magma")             # 달아오른 쐐기
    # 뒤: 위로 솟아 휘는 불꽃 혀 모양 가시
    tongue = poly([(-3, 57), (-6, 57.5), (-8.5, 59.5), (-10, 63), (-10.5, 67), (-12, 63), (-13, 58.5), (-12.5, 54),
                   (-10.5, 50.5), (-7, 48.5), (-3, 48.5)])
    tq = lambda X, Y: tongue(X, q2(Y))
    w.prism(tq, 1.5, "basalt")
    w.prism(lambda X, Y: tq(X, Y) & (Y >= 61), 1.5, "hot")
    vein = line2d([(-3, 52), (-7, 52.5), (-10, 55.5), (-11, 60)], 1.1)
    w.prism(lambda X, Y: tq(X, Y) & (Y < 61) & vein(q2(X), q2(Y)),
            1.5, "magma")
    # 녹아 흘러내리는 방울
    for (x, y, h, wd) in ((17, 41, 7, 1.5), (13.5, 34.5, 8, 1.5)):
        w.box(x - wd, x + wd, y - h * 0.5, y, -1, 1, "magma")
        w.box(x - wd + 0.5, x + wd - 0.5, y - h, y - h * 0.5, -1, 1, "magma")
        w.box(x - 0.5, x + 0.5, y - h - 1.5, y - h, -0.5, 0.5, "magma")
    return w


# ─────────────────────────── boss / prism ───────────────────────────

def inferno_hammer():
    """화염 거신의 망치: 허리가 잘록하고 양끝이 벌어진 흑철 덩이, 달아오른 타격면, 청동 창살 속 심장, 타격면을 감아 도는 거대한 상아 숫양 뿔."""
    m = {
        "black": Mat(["#2a2226", "#3c3236", "#52464a", "#6a5c60"], "stone", seed=111),
        "bronze": Mat(["#5a2a10", "#8a4418", "#b8682a", "#e09a48"], "metal", seed=112),
        "grip": Mat(["#1a0c08", "#3a1a10", "#5a2a18", "#7a3a20"], "grip", seed=116),
        "bone": Mat(["#8a7a5a", "#b8a882", "#ddd0aa", "#f6eed4"], "metal", seed=115),
        "magma": Mat(["#d04000", "#ff7a10", "#ffb830", "#fff4b0"], "fire", glow=True, seed=113),
        "heart": Mat(["#c02000", "#ff6a10", "#ffd040", "#fffbe0"], "pulse", glow=True, seed=114),
        "ember": Mat(["#8a1a00", "#d04a08", "#ff8a20", "#ffc060"], "fire", glow=True, seed=117),
    }
    w = Weapon(padded(m), grip_y=11, kind="hammer", seed=111)
    w.cyl(0, 46, 2.2, "black")
    w.cyl(4, 18, 2.6, "grip")
    w.cyl(18, 19.5, 2.8, "bronze")
    rbox(w, -3.2, 3.2, 1, 4, -3.2, 3.2, 1, "bronze")           # 폼멜
    w.box(-1.5, 1.5, 0, 1, -1.5, 1.5, "black")
    for (y, s) in ((26, 1), (34, -1)):                           # 자루 용암 틈 (아우라 초점 아님)
        w.box(-0.5, 0.5, y, y + 4, 1.4 if s > 0 else -2.4, 2.4 if s > 0 else -1.4, "ember")
    rbox(w, -4, 4, 41, 46, -4, 4, 1, "bronze")
    cy = 56
    rbox(w, -6, 6, cy - 8.5, cy + 8.5, -7, 7, 2, "black")      # 가운데
    rbox(w, -11, 11, cy - 7, cy + 7, -6, 6, 1.5, "black")      # 잘록한 허리
    for s in (-1, 1):
        sb = lambda a, b: sorted((s * a, s * b))
        rbox(w, *sb(11, 12), cy - 7.5, cy + 7.5, -6.5, 6.5, 1.5, "magma")    # 허리 이음매
        rbox(w, *sb(12, 16), cy - 10, cy + 10, -8, 8, 3, "black")            # 벌어진 머리
        rbox(w, *sb(16, 17.5), cy - 8, cy + 8, -6.5, 6.5, 2, "magma")         # 달아오른 타격면
        w.box(*sb(9, 11), cy - 11, cy - 7, -1.6, 1.6, "black")               # 아래 송곳
    # 심장 창: 2칸만 파고 그 바닥을 심장으로, 청동 창살 둘
    win = lambda X, Y: ((np.abs(X) <= 5) & (np.abs(Y - cy) <= 4)) | ((np.abs(X) <= 4) & (np.abs(Y - cy) <= 5))
    w.clear(lambda X, Y, Z: win(X, Y) & (np.abs(Z) > 5))
    w.prism(win, 5, "heart")
    w.prism(lambda X, Y: (np.abs(X) <= 1.5) & (np.abs(Y - cy) <= 2.5), 6, "heart")
    for x in (-3, 2):
        w.box(x, x + 1, cy - 5, cy + 5, -7, -5, "bronze")
        w.box(x, x + 1, cy - 5, cy + 5, 5, 7, "bronze")
    # 상아 숫양 뿔: 벌어진 머리 위에서 솟아 바깥으로 말려 타격면 옆까지 내려온다
    path = [(12.5, cy + 11.5, 3.0), (16, cy + 13.8, 2.8), (19.5, cy + 12.5, 2.5), (21.4, cy + 9, 2.2),
            (21.6, cy + 5.5, 1.9), (20.6, cy + 2.5, 1.6), (19.6, cy, 1.2)]
    for (x, y, h) in path:
        for s in (-1, 1):
            w.box(s * x - h, s * x + h, y - h, y + h, -h * 0.85, h * 0.85, "bone")
    for s in (-1, 1):
        a, b = sorted((s * 10, s * 15))
        w.box(a, b, cy + 9.5, cy + 11, -3.6, 3.6, "bronze")      # 뿔 뿌리 띠
    w.set_aura(["#8a1000", "#ff4a0a", "#ffa020", "#fff4b0"], "flame", size=1.1, focus=["magma", "heart"])
    return w


def thundergod_hammer():
    """천뢰의 망치: 폭풍 강철 몸통 양끝에 각진 보라 뇌정 수정, 무지개 테와 촉, 머리에서 갈라져 솟는 굵은 번개 두 줄기."""
    m = {
        "storm": Mat(["#141028", "#241c48", "#382c6c", "#4e4090"], "metal", seed=121),
        "plat": Mat(["#8a8ea8", "#b8bccc", "#dde2ec", "#ffffff"], "metal", seed=123),
        "crys": Mat(["#5a2ac8", "#8a5af0", "#c0a0ff", "#f4ecff"], "crystal", glow=True, seed=124),
        "crys_d": Mat(["#2a1070", "#4a24b0", "#7048e0", "#a080ff"], "crystal", glow=True, seed=128),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff0a0"], "metal", seed=122),
        "grip": Mat(["#8a8478", "#b4ac9c", "#d8d0bc", "#f4eedc"], "grip", seed=127),
        "spark": Mat(["#e8c020", "#ffe050", "#fff4a0", "#ffffff"], "flat", glow=True, seed=129),
        "prism": Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=125),
        "bolt": Mat(["#e8c020", "#ffe050", "#fff4a0", "#ffffff"], "pulse", glow=True, seed=126),
    }
    w = Weapon(padded(m), grip_y=13, kind="hammer", seed=112)
    # 폼멜: 아래로 뾰족한 수정 + 금 고리
    for i, r in enumerate((0.6, 1.4, 2.2)):
        w.box(-r, r, i * 1.7, i * 1.7 + 1.7, -r, r, "crys")
    rbox(w, -2.8, 2.8, 5, 6.5, -2.8, 2.8, 0.5, "gold")
    w.box(-2, 2, 6.5, 44, -2, 2, "storm")                      # 각진 자루
    w.cyl(6.5, 19.5, 2.6, "grip")
    for y in (20, 30, 38):
        w.box(-2.5, 2.5, y, y + 1.5, -2.5, 2.5, "plat")
    w.box(-0.5, 0.5, 22, 29, -2.6, 2.6, "spark")              # 자루에 흐르는 번개 줄 (아우라 초점 아님)
    cy = 49
    rbox(w, -7, 7, cy - 7, cy + 7, -6, 6, 2, "storm")
    for s in (-1, 1):
        sb = lambda a, b: sorted((s * a, s * b))
        rbox(w, *sb(5.5, 7), cy - 7.6, cy + 7.6, -6.6, 6.6, 2, "plat")
        rbox(w, *sb(7, 9), cy - 5.6, cy + 5.6, -4.6, 4.6, 1, "gold")
        # 각진 수정 머리: 2칸마다 굵기가 바뀌는 쌍뿔, 위는 밝고 아래는 어둡게 (면이 갈려 보이게)
        for (x0, x1, r, rz, c) in ((9, 11, 6, 5, 1.5), (11, 13, 7.5, 6, 2), (13, 15, 8, 6.5, 2.5), (15, 17, 6.5, 5, 2),
                                   (17, 19, 4.6, 3.6, 1.5)):
            f = rmask(*sb(x0, x1), cy - r, cy + r, -rz, rz, c)
            w.fill(lambda X, Y, Z, f=f: f(X, Y, Z) & (Y >= cy), "crys")
            w.fill(lambda X, Y, Z, f=f: f(X, Y, Z) & (Y < cy), "crys_d")
        rbox(w, *sb(13, 14), cy - 8.5, cy + 8.5, -6.9, 6.9, 2.5, "prism")    # 무지개 테 (거의 평평하게 둘러)
        rbox(w, *sb(19, 21), cy - 2.6, cy + 2.6, -2, 2, 0.6, "prism")     # 무지개 촉
        w.box(*sb(21, 23), cy - 1, cy + 1, -1, 1, "prism")
    # 번개: 머리 위로 솟구치는 큰 번개 하나 + 오른쪽 수정에서 튀는 작은 번개 (픽셀 2칸, 두께 4)
    big = sprite(["....#.", "...##.", "..##..", ".##...", "#####.", "..###.", ".###..", "####.."], -5, 72, 2, 2, 2)
    small = sprite(["...#", "..##", ".##.", "####", ".##.", "##.."], 12, cy + 19, 2, 2, 1.5)
    w.fill(lambda X, Y, Z: big(X, Y, Z) | small(X, Y, Z), "bolt")
    # 몸통 앞뒤: 백금 갈매기 무늬 (번개 기호)
    for sz in (-1, 1):
        a, b = sorted((sz * 6, sz * 7))
        w.fill(lambda X, Y, Z, a=a, b=b: (Z >= a) & (Z <= b) & (np.abs(Y - cy - 1 + np.floor(np.abs(X) / 2) * 1.5) <= 1.0)
               & (np.abs(X) <= 4.5), "plat")
    w.set_aura(["#3a0a8a", "#7a2ae8", "#c08aff", "#fff6c0"], "bolt", size=1.0, focus=["crys", "crys_d", "prism", "bolt"])
    return w


WEAPONS = {
    "woodcutter_axe": woodcutter_axe,
    "stone_hammer": stone_hammer,
    "thorn_club": thorn_club,
    "smith_hammer": smith_hammer,
    "earth_hammer": earth_hammer,
    "thunder_hammer": thunder_hammer,
    "holy_hammer": holy_hammer,
    "earth_axe": earth_axe,
    "wind_axe": wind_axe,
    "volcano_axe": volcano_axe,
    "inferno_hammer": inferno_hammer,
    "thundergod_hammer": thundergod_hammer,
}

NAMES = {
    "woodcutter_axe": "나무꾼의 도끼",
    "stone_hammer": "돌망치",
    "thorn_club": "가시 곤봉",
    "smith_hammer": "대장장이 망치",
    "earth_hammer": "대지의 망치",
    "thunder_hammer": "뇌신의 망치",
    "holy_hammer": "성기사의 망치",
    "earth_axe": "대지의 도끼",
    "wind_axe": "폭풍의 도끼",
    "volcano_axe": "화산 도끼",
    "inferno_hammer": "화염 거신의 망치",
    "thundergod_hammer": "천뢰의 망치",
}

if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids:
        sub = {k: WEAPONS[k] for k in ids}
        out = os.path.join(HERE, "preview", "_scratch", "axes_hammers_part.png")
        preview_sheet(sub, out, names=NAMES)
    else:
        preview_sheet(WEAPONS, os.path.join(HERE, "preview", "axes_hammers.png"), names=NAMES)
