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


def xcyl(w, x0, x1, cy, r, mat, rz=None, cz=0.0):
    """가로(X 방향) 원기둥."""
    rz = r if rz is None else rz
    return w.fill(lambda X, Y, Z: (X >= x0) & (X <= x1) & (((Y - cy) / r) ** 2 + ((Z - cz) / rz) ** 2 <= 1.0), mat)


def rings(w, ys, r, mat, h=1.0, cx=0.0):
    """손잡이에 두른 고리들."""
    for y in ys:
        w.cyl(y, y + h, r, mat, cx=cx)
    return w


def wrap(w, y0, y1, r, mat_a, mat_b, step=3):
    """감은 손잡이: 두 재료를 번갈아 감는다."""
    w.cyl(y0, y1, r, mat_a)
    y = y0 + step - 1
    while y < y1:
        w.cyl(y, y + 0.9, r, mat_b)
        y += step
    return w


# ─────────────────────────── basic ───────────────────────────

def woodcutter_axe():
    """평범한 외날 도끼: 곧은 나무 자루, 아래로 처진 수염날, 짧은 망치머리."""
    m = {
        "wood": Mat(["#4a2c14", "#74471f", "#9b6630", "#c08a4c"], "wood", seed=1),
        "leather": Mat(["#2a1a10", "#4a2e1a", "#6a4428", "#87603a"], "grip", seed=2),
        "iron": Mat(["#34373e", "#585c64", "#80848c", "#a4a8b0"], "metal", seed=3),
        "edge": Mat(["#9aa0a8", "#c0c6cc", "#e2e6ea", "#ffffff"], "metal", seed=4),
    }
    w = Weapon(m, grip_y=9, kind="axe", seed=101)
    w.cyl(0, 57, 1.6, "wood")
    w.cyl(0, 2, 2.2, "wood")                             # 자루 끝 혹
    w.cyl(3, 15, 1.9, "leather")

    def top(X):
        return 54 + np.clip(X - 3, 0, None) * 0.32

    def bot(X):
        return 46 - np.clip(X - 4, 0, None) * 0.6

    def xe(Y):
        return 13.5 + 2.0 * (1 - ((Y - 49) / 10) ** 2)

    def head(X, Y, Z):
        hz = np.clip(2.6 - (X - 2) * 0.16, 0.6, 3)
        return (X >= 0) & (X <= xe(Y)) & (Y >= bot(X)) & (Y <= top(X)) & (np.abs(Z) <= hz)

    w.fill(head, "iron")
    w.fill(lambda X, Y, Z: head(X, Y, Z) & (X > xe(Y) - 2.2), "edge")
    w.box(-3, 3, 45, 55, -2.6, 2.6, "iron")              # 자루 구멍(눈)
    w.box(-6.5, -3, 46.5, 53.5, -2.2, 2.2, "iron")       # 뒤쪽 짧은 망치머리
    return w


def stone_hammer():
    """막대기에 덩굴로 묶은 울퉁불퉁한 돌덩이."""
    m = {
        "stone": Mat(["#4a4a4e", "#6c6c70", "#8e8e92", "#b0b0b4"], "stone", seed=11),
        "cobble": Mat(["#323236", "#46464a", "#5a5a5e", "#6e6e72"], "stone", seed=12),
        "stick": Mat(["#3e2812", "#5c3c1c", "#7a522a", "#96683a"], "wood", seed=13),
        "vine": Mat(["#1e3a12", "#2e5a1a", "#447a26", "#5a9632"], "grip", seed=14),
        "rag": Mat(["#6a5a44", "#8a7a5e", "#a89a7c", "#c4b898"], "cloth", seed=15),
    }
    w = Weapon(m, grip_y=11, kind="hammer", seed=102)
    w.cyl(0, 50, 1.6, "stick")
    w.cyl(4, 18, 2.0, "rag")
    w.cyl(9, 10, 2.3, "vine")

    cy = 51

    def chunk(X, Y, Z):
        ux, uy, uz = np.abs(X) - 9.5, np.abs(Y - cy) - 7, np.abs(Z) - 5.5
        inside = (ux <= 0) & (uy <= 0) & (uz <= 0)
        # 모서리마다 다르게 깎아서 울퉁불퉁
        k = np.where(X > 0, np.where(Y > cy, 2.5, 4.0), np.where(Y > cy, 4.5, 2.0))
        inside &= (ux + uy <= -k)
        inside &= (ux + uz <= -2.5) & (uy + uz <= -2.0)
        return inside

    # 덩굴 띠 (돌보다 한 칸 크게 먼저 칠하고 돌로 덮는다)
    for x0 in (-4, 2):
        w.box(x0, x0 + 1.5, cy - 8, cy + 8, -6.6, 6.6, "vine")
    w.fill(chunk, "stone")
    w.fill(lambda X, Y, Z: chunk(X, Y, Z) & (((X < -4) & (Y > cy - 1)) | ((X > 4) & (Y < cy - 2)) |
                                            ((np.abs(X) < 2) & (Y > cy + 3))), "cobble")
    w.cyl(38, 44, 2.1, "vine")
    return w


def thorn_club():
    """선인장 한 줄기를 통째로: 네모난 줄기, 곁가지 하나, 가시, 꽃 한 송이."""
    m = {
        "cactus": Mat(["#245a1a", "#347a26", "#4a9634", "#66b04a"], "stone", seed=21),
        "rib": Mat(["#143a10", "#1c4e16", "#24601c", "#2e7224"], "flat", seed=22),
        "spine": Mat(["#a89a60", "#c8bc80", "#e4dca8", "#fff8d8"], "flat", seed=23),
        "twine": Mat(["#7a6440", "#a08658", "#c0a878", "#dccaa0"], "grip", seed=24),
        "flower": Mat(["#a0204a", "#d84a7a", "#f07aa0", "#ffc0d4"], "flat", seed=25),
        "cut": Mat(["#8aa860", "#a8c47a", "#c4dc9a", "#dcecb8"], "flat", seed=26),
    }
    w = Weapon(m, grip_y=8, kind="hammer", seed=103)

    def hw(Y):
        h = np.clip(2 + (Y - 14) / 7.0, 2, 5)
        top = np.sqrt(np.clip(1 - ((Y - 47) / 6.5) ** 2, 0, 1)) * 5
        return np.where(Y > 47, top, h)

    def stem(X, Y, Z):
        return (np.maximum(np.abs(X), np.abs(Z)) <= hw(Y)) & (Y >= 0) & (Y <= 54)

    w.fill(stem, "cactus")
    # 모서리 줄 (어두운 골)
    w.fill(lambda X, Y, Z: stem(X, Y, Z) & (np.abs(X) > hw(Y) - 1) & (np.abs(Z) > hw(Y) - 1) & (Y > 16), "rib")
    # 곁가지
    w.box(4, 9, 27, 31, -2, 2, "cactus")
    w.box(7, 11, 27, 39, -2, 2, "cactus")
    w.box(8, 10, 39, 40.5, -1, 1, "cactus")
    w.box(0, 0.9, 0, 0.9, 0, 0, "cut")
    w.box(-2, 2, 0, 1, -2, 2, "cut")                    # 잘린 밑동
    # 가시: 옆면(±X)은 바깥으로, 앞뒤(±Z)도 바깥으로
    for i, y in enumerate(range(20, 48, 5)):
        h = float(hw(np.array(y + 0.5)))
        o = 1.5 if i % 2 else -1.5
        for s in (-1, 1):
            w.box(s * h if s > 0 else -h - 2.2, s * h + 2.2 if s > 0 else -h, y, y + 0.9, o - 0.5, o + 0.5, "spine")
            w.box(-o - 0.5, -o + 0.5, y + 2, y + 2.9, s * h if s > 0 else -h - 2, s * h + 2 if s > 0 else -h, "spine")
    for y in (31, 36):
        w.box(11, 13, y, y + 0.9, -0.5, 0.5, "spine")
    w.box(9, 9.9, 41, 42.5, -0.5, 0.5, "spine")
    # 손잡이: 노끈을 듬성듬성 감고, 틈으로 가시가 삐죽
    for y0 in (2, 6, 10, 14):
        w.box(-3, 3, y0, y0 + 2, -3, 3, "twine")
    w.box(-4.2, -2, 4.5, 5.4, -0.5, 0.5, "spine")
    w.box(2, 4.2, 12.5, 13.4, -0.5, 0.5, "spine")
    # 꼭대기 꽃
    w.box(-2, 2, 53, 55, -2, 2, "flower")
    w.box(-1, 1, 55, 56, -1, 1, "spine")
    return w


def smith_hammer():
    """대장간 망치: 짧은 자루, 한쪽은 넓은 평면, 반대쪽은 쐐기(크로스핀)."""
    m = {
        "iron": Mat(["#202226", "#34373c", "#4a4e54", "#62666c"], "metal", seed=31),
        "face": Mat(["#6a6e74", "#9a9ea4", "#c8ccd0", "#f0f2f4"], "metal", seed=32),
        "ash": Mat(["#6a4a2a", "#8e6a40", "#b08a58", "#ccaa74"], "wood", seed=33),
        "leather": Mat(["#3a1e10", "#5a2e18", "#7a4224", "#965634"], "grip", seed=34),
    }
    w = Weapon(m, grip_y=8, kind="hammer", seed=104)
    w.cyl(0, 42, 1.6, "ash")
    w.cyl(0, 2, 2.1, "ash")
    w.cyl(2, 14, 1.9, "leather")
    w.box(-2.9, 2.9, 26, 32, -0.9, 0.9, "iron")          # 양쪽 쇠띠(랑겟)
    cy = 37
    w.box(-3.5, 3.5, cy - 6, cy + 5, -3.5, 3.5, "iron")    # 눈
    w.box(-12, -3, cy - 4, cy + 4, -3, 3, "iron")          # 평면 쪽 몸통
    w.box(-14, -12, cy - 5, cy + 5, -3.5, 3.5, "face")     # 반질반질한 치는 면
    w.box(-12, -10.5, cy - 4.5, cy + 4.5, -3.2, 3.2, "iron")

    def peen(X, Y, Z):
        h = 4.2 - (X - 3) * 0.32
        return (X >= 3) & (X <= 13) & (np.abs(Y - cy) <= h) & (np.abs(Z) <= 3)

    w.fill(peen, "iron")
    w.fill(lambda X, Y, Z: peen(X, Y, Z) & (X > 11), "face")
    w.box(-1.5, 1.5, cy + 5, cy + 6, -0.5, 0.5, "face")    # 자루에 박은 쐐기
    return w


# ─────────────────────────── island ───────────────────────────

def earth_hammer():
    """섬 한 덩이를 잘라 붙인 망치: 풀, 흙, 돌, 심층암 층과 광석, 뿌리 자루."""
    m = {
        "grass": Mat(["#2f5a16", "#46801f", "#5ea02c", "#80c040"], "cloth", seed=41),
        "dirt": Mat(["#4a2e18", "#6a4224", "#8a5a34", "#a87448"], "stone", seed=42),
        "stone": Mat(["#4c4a48", "#6e6a66", "#8e8a84", "#aca8a0"], "stone", seed=43),
        "deep": Mat(["#26242a", "#38363e", "#4c4a52", "#605e68"], "stone", seed=44),
        "root": Mat(["#3a2414", "#5a3a1e", "#7a522c", "#96703e"], "wood", seed=45),
        "ore": Mat(["#8a6a10", "#d0a020", "#f0d050", "#fff6b0"], "metal", seed=46),
        "amber": Mat(["#7a3a00", "#d07a10", "#ffb030", "#fff0a0"], "pulse", glow=True, seed=47),
        "bark": Mat(["#2a1a0e", "#3e2816", "#54381e", "#6a4828"], "grip", seed=48),
    }
    w = Weapon(m, grip_y=11, kind="hammer", seed=105)
    w.tube([(0, 0, 0), (0.6, 14, 0), (-0.5, 30, 0), (0.3, 50, 0)], 1.9, "root")
    w.cyl(4, 18, 2.2, "bark")
    w.ball(0, 2, 0, 3, 2.5, 3, "stone")                       # 밑동 돌
    # 머리를 휘감는 뿌리
    w.tube([(-2, 50, 1), (-3, 45, 2), (-1, 41, 2.5), (1.5, 37, 1)], 0.9, "root")
    w.tube([(2, 50, -1), (3, 45, -2), (1, 42, -2.5), (-1.5, 39, -1)], 0.9, "root")
    x0, x1, z = 13, 13, 6.5

    def blk(X, Y, Z):
        return (np.abs(X) <= x0) & (Y >= 47) & (Y <= 64) & (np.abs(Z) <= z)

    w.fill(blk, "stone")
    w.fill(lambda X, Y, Z: blk(X, Y, Z) & (Y < 51), "deep")
    w.fill(lambda X, Y, Z: blk(X, Y, Z) & (Y >= 57), "dirt")
    w.fill(lambda X, Y, Z: blk(X, Y, Z) & (Y >= 61), "grass")
    # 풀이 옆으로 살짝 늘어짐
    w.fill(lambda X, Y, Z: (np.abs(X) <= x0 + 1) & (Y >= 61) & (Y <= 63) & (np.abs(Z) <= z + 1)
           & ~blk(X, Y, Z) & (((X + Z * 2).astype(int) % 5) != 0), "grass")
    # 아래 모서리를 깎는다 (떠 있는 섬의 밑처럼)
    w.clear(lambda X, Y, Z: (np.abs(X) - x0 + (47 - Y) + 3 > 0) & (Y >= 46) & (Y < 51))
    # 광석 몇 점
    for (ox, oy) in ((-8, 53), (6, 49), (9, 55)):
        w.box(ox - 1, ox + 1, oy, oy + 2, -z, z, "ore")
    w.gem(0, 54, 1.6, "amber", frame=None, depth=7.2)
    # 풀 몇 포기
    for (gx, gz) in ((-9, 2), (-4, -3), (7, 1), (11, -2)):
        w.box(gx - 0.5, gx + 0.5, 64, 66, gz - 0.5, gz + 0.5, "grass")
    return w


def thunder_hammer():
    """구리 피뢰침 망치: 강철 북통에 구리 코일, 녹청 마개, 위로 솟은 피뢰침."""
    m = {
        "steel": Mat(["#1e2128", "#343844", "#4e5462", "#6e7484"], "metal", seed=51),
        "copper": Mat(["#6a3014", "#a8542a", "#d07a44", "#f0a070"], "metal", seed=52),
        "oxid": Mat(["#1e5a4e", "#2e8a76", "#4ab098", "#7ad0b8"], "stone", seed=53),
        "grip": Mat(["#141a2a", "#22304a", "#344868", "#486088"], "grip", seed=54),
        "strap": Mat(["#3a2a1a", "#5a422a", "#7a5a3c", "#9a7650"], "cloth", seed=55),
        "spark": Mat(["#4a6aff", "#8ab0ff", "#d0e4ff", "#ffffff"], "sparkle", glow=True, seed=56),
    }
    w = Weapon(m, grip_y=11, kind="hammer", seed=106)
    w.cyl(0, 50, 1.6, "steel")
    w.cyl(4, 18, 2.0, "grip")
    rings(w, (19, 24, 29), 2.1, "copper")
    w.cyl(1, 4, 2.4, "copper")
    # 손잡이 끝 가죽 고리
    w.tube([(-1.5, 2, 0.5), (-4, 0.5, 0.5), (-7, 2, 0.5), (-7.5, 6, 0.5), (-5, 8.5, 0.5), (-2, 7, 0.5)], 0.75, "strap")
    cy = 51
    xcyl(w, -9, 9, cy, 5.6, "steel")
    for s in (-1, 1):
        for x in (3, 5.2, 7.4):
            xcyl(w, s * x - 0.5, s * x + 0.5, cy, 6.3, "copper")
        xcyl(w, 9, 12, cy, 6.6, "oxid") if s > 0 else xcyl(w, -12, -9, cy, 6.6, "oxid")
        xcyl(w, s * 12.5 - 0.5, s * 12.5 + 0.5, cy, 4.0, "oxid")
    xcyl(w, -1.5, 1.5, cy, 6.0, "copper")
    # 피뢰침
    w.cyl(56, 68, 1.0, "copper")
    w.cyl(59, 60, 2.1, "oxid")
    w.cyl(68, 70, 1.6, "copper")
    w.box(-1, 1, 70, 72, -1, 1, "spark")
    return w


def holy_hammer():
    """성기사의 쌍면 망치: 대리석 팔각 머리, 금테, 태양 문장, 첨탑, 푸른 술."""
    m = {
        "marble": Mat(["#a8a49a", "#cac6bc", "#e6e2d8", "#fffcf2"], "stone", seed=61),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff0a0"], "metal", seed=62),
        "blue": Mat(["#14246a", "#22409a", "#3a64c8", "#5a88e8"], "cloth", seed=63),
        "haft": Mat(["#8a7a64", "#b0a084", "#d0c4a8", "#ece4cc"], "wood", seed=64),
        "sun": Mat(["#c08010", "#ffc030", "#ffe890", "#ffffff"], "pulse", glow=True, seed=65),
        "grip": Mat(["#101a4a", "#1c2c6a", "#2a4090", "#3a56b0"], "grip", seed=66),
    }
    w = Weapon(m, grip_y=10, kind="hammer", seed=107)
    w.cyl(0, 50, 1.6, "haft")
    w.cyl(3, 17, 1.9, "grip")
    rings(w, (17, 30, 42), 2.1, "gold")
    w.cyl(0, 3, 2.6, "gold")
    cy = 52

    def octa(r):
        return lambda X, Y, Z: (np.abs(Y - cy) <= r) & (np.abs(Z) <= r) & (np.abs(Y - cy) + np.abs(Z) <= r * 1.45)

    w.box(-4, 4, cy - 7, cy + 7, -4.2, 4.2, "marble")
    o5, o6 = octa(5.5), octa(6.3)
    w.fill(lambda X, Y, Z: (np.abs(X) >= 4) & (np.abs(X) <= 12) & o5(X, Y, Z), "marble")
    w.fill(lambda X, Y, Z: (np.abs(X) >= 4) & (np.abs(X) <= 5) & o6(X, Y, Z), "gold")
    w.fill(lambda X, Y, Z: (np.abs(X) >= 10) & (np.abs(X) <= 11) & o6(X, Y, Z), "gold")
    w.box(-4.5, 4.5, cy + 7, cy + 8, -4.5, 4.5, "gold")
    w.box(-4.5, 4.5, cy - 8, cy - 7, -4.5, 4.5, "gold")
    w.gem(0, cy, 1.6, "sun", frame="gold", depth=5.4, frame_w=1.6)
    # 첨탑
    w.fill(lambda X, Y, Z: (Y >= cy + 8) & (Y <= 70) & (np.maximum(np.abs(X), np.abs(Z)) <= 2.6 - (Y - cy - 8) * 0.2), "gold")
    # 푸른 술
    w.tube([(-3, cy - 8, 3.5), (-4, cy - 12, 4), (-4, cy - 15, 4)], 0.7, "gold")
    w.ball(-4, cy - 18, 4, 1.6, 3.2, 1.6, "blue")
    return w


def earth_axe():
    """쪼갠 바위 양날 도끼: 깨진 날, 이끼, 밧줄로 묶은 화석 나무 자루."""
    m = {
        "rock": Mat(["#5a4630", "#7a6044", "#9a7c58", "#bca07a"], "stone", seed=71),
        "flint": Mat(["#9a8a70", "#bcaa8a", "#d8c8a8", "#f0e4c8"], "stone", seed=72),
        "moss": Mat(["#2a4a14", "#3a6a1c", "#4e8a28", "#64a434"], "stone", seed=73),
        "petri": Mat(["#3a3430", "#5a504a", "#7a6e64", "#968a7e"], "wood", seed=74),
        "rope": Mat(["#5a4a2a", "#8a7448", "#b09a68", "#d0bc88"], "grip", seed=75),
    }
    w = Weapon(m, grip_y=11, kind="axe", seed=108)
    w.cyl(0, 63, 1.7, "petri")
    w.cyl(4, 18, 2.0, "rope")
    w.ball(0, 64, 0, 2.4, 2.2, 2.4, "rock")
    pts = [(1, 45), (6, 43), (11, 39), (16, 40), (17.5, 46), (18, 52), (16.5, 59), (12, 62), (7, 58), (1, 57)]
    bit = poly(pts)
    anc = np.array([1.0, 51.0])
    inner = poly([tuple(anc + (np.array(p) - anc) * 0.8) for p in pts])

    def body(X, Y, Z):
        hz = np.clip(3.2 - (X - 1) * 0.16, 0.6, 4)
        return bit(X, Y) & (np.abs(Z) <= hz) & (X >= 0)

    w.fill(body, "rock")
    w.fill(lambda X, Y, Z: body(X, Y, Z) & ~inner(X, Y) & (X > 9), "flint")
    # 이 빠진 날
    w.clear(lambda X, Y, Z: (np.hypot(X - 18.5, Y - 49) < 1.6) | (np.hypot(X - 17, Y - 56.5) < 1.2))
    w.mirror()
    w.box(-3, 3, 44, 58, -3.2, 3.2, "rock")
    for y in (45, 48, 54, 57):
        w.box(-3.5, 3.5, y, y + 1.5, -3.7, 3.7, "rope")
    # 이끼 (왼쪽 위만)
    w.fill(lambda X, Y, Z: body(-X, Y, Z) & (X < -3) & (Y > 56 + (X + 10) * 0.2), "moss")
    return w


def wind_axe():
    """바람 도끼: 자루와 떨어진 초승달 날이 위로 말려 올라가고, 뒤에는 소용돌이, 깃털 장식."""
    m = {
        "silver": Mat(["#5a6a78", "#8a9caa", "#bccad4", "#eef6fa"], "metal", seed=81),
        "teal": Mat(["#0e4a4e", "#17706e", "#2a9a90", "#4ac4b4"], "metal", seed=82),
        "birch": Mat(["#8a8478", "#b4ae9e", "#d4cebe", "#eeeadc"], "wood", seed=83),
        "wrap": Mat(["#0e3a3e", "#145458", "#1e7074", "#2c8c90"], "grip", seed=84),
        "feather": Mat(["#9aa4ae", "#c8d0d8", "#e8eef2", "#ffffff"], "flat", seed=85),
        "wind": Mat(["#2a8a9a", "#5ad0e0", "#a8f4ff", "#ffffff"], "flow", glow=True, seed=86),
    }
    w = Weapon(m, grip_y=12, kind="axe", seed=109)
    w.cyl(0, 63, 1.6, "birch")
    w.cyl(4, 20, 1.9, "wrap")
    rings(w, (21, 42), 2.0, "silver")
    w.fill(lambda X, Y, Z: (Y >= 63) & (Y <= 67) & (np.maximum(np.abs(X), np.abs(Z)) <= 1.6 - (Y - 63) * 0.3), "silver")
    outer = [(-3, 71), (4, 70), (10, 67), (14.5, 62), (16.5, 55), (16, 48), (13, 41), (8, 36), (3, 34.5),
             (5, 38), (9, 43), (11, 50), (10.5, 57), (8, 62), (3, 66), (-1, 68)]
    blade = poly(outer)
    w.prism(blade, 1.5, "teal")
    inner = poly([(-1, 69.2), (4, 68.5), (9, 65.5), (13, 61), (15, 55), (14.6, 48), (12, 42), (8, 37.5), (4, 35.5),
                  (6, 37), (10, 42.5), (12.3, 50), (12, 57), (9.5, 63), (4, 67.3)])
    w.fill(lambda X, Y, Z: blade(X, Y) & ~inner(X, Y) & (np.abs(Z) <= 0.6), "silver")
    w.clear(lambda X, Y, Z: blade(X, Y) & ~inner(X, Y) & (np.abs(Z) > 0.6))
    # 자루와 날을 잇는 다리
    w.box(0, 11, 49, 52, -1.5, 1.5, "silver")
    w.box(-2.5, 2.5, 46, 56, -2.4, 2.4, "teal")
    w.gem(5.5, 56, 1.6, "wind", depth=1.6)
    # 뒤쪽 소용돌이
    sp = [(-2.5 - 3.5 * (1 - t / 12) * math.cos(t), 51 + 3.5 * (1 - t / 12) * math.sin(t) + 1.5, 0)
          for t in np.linspace(0, 1.6 * math.pi, 14)]
    w.tube([(-2.5, 51, 0)] + sp, 0.9, "silver")
    # 깃털 장식
    w.tube([(-2.5, 46, 0), (-4.5, 43, 0)], 0.6, "silver")
    w.prism(poly([(-4, 43), (-6, 41), (-6.5, 35), (-5, 31), (-4, 36)]), 0.6, "feather")
    w.prism(poly([(-4.5, 43), (-3, 40), (-2.8, 34), (-3.6, 32), (-4.3, 37)]), 0.6, "feather")
    return w


# ─────────────────────────── flame ───────────────────────────

def volcano_axe():
    """화산 도끼: 나무꾼 도끼를 용암에 담근 모양 — 숯 자루, 현무암 날, 갈라진 용암 결, 흘러내리는 방울."""
    m = {
        "basalt": Mat(["#1a1416", "#2c2226", "#40343a", "#584a50"], "stone", seed=91),
        "char": Mat(["#120c0a", "#241814", "#36241c", "#4a3226"], "wood", seed=92),
        "magma": Mat(["#8a1a00", "#e04a08", "#ffa020", "#fff0a0"], "fire", glow=True, seed=93),
        "hot": Mat(["#b02a00", "#ff6a10", "#ffc040", "#fff8c0"], "pulse", glow=True, seed=94),
        "wrap": Mat(["#1a0e0a", "#2e1a12", "#44261a", "#5a3424"], "grip", seed=95),
    }
    w = Weapon(m, grip_y=10, kind="axe", seed=110)
    w.cyl(0, 61, 1.7, "char")
    w.cyl(0, 2.5, 2.3, "basalt")
    w.cyl(3, 17, 2.0, "wrap")
    # 자루의 갈라진 틈
    for (y, s) in ((22, 1), (30, -1), (37, 1)):
        w.box(-0.5, 0.5, y, y + 3, s * 1.0 if s > 0 else -2, 2 if s > 0 else -1.0, "magma")

    def top(X):
        return 57 + np.clip(X - 3, 0, None) * 0.45

    def bot(X):
        return 48 - np.clip(X - 3, 0, None) * 0.9

    def xe(Y):
        # 톱니 날
        return 17 + 1.5 * (1 - ((Y - 50) / 13) ** 2) - (np.floor(Y / 3) % 2) * 1.0

    def head(X, Y, Z):
        hz = np.clip(3.0 - (X - 2) * 0.16, 0.6, 3.2)
        return (X >= 0) & (X <= xe(Y)) & (Y >= bot(X)) & (Y <= top(X)) & (np.abs(Z) <= hz)

    w.fill(head, "basalt")
    w.fill(lambda X, Y, Z: head(X, Y, Z) & (X > xe(Y) - 1.6), "hot")
    # 용암 결 (앞뒤로 갈라진 금)
    vein = [(3, 52, 0), (7, 54, 0), (10, 51, 0), (13, 53, 0), (15, 49, 0)]
    w.tube([(x, y, 0) for x, y, _ in vein], 0.8, "magma", rz=3.0)
    w.tube([(6, 49, 0), (9, 45, 0), (12, 44, 0)], 0.8, "magma", rz=3.0)
    w.box(-3.5, 3.5, 47, 58, -2.8, 2.8, "basalt")
    w.box(-7, -3.5, 48.5, 56.5, -2.4, 2.4, "basalt")
    w.box(-7.5, -6.5, 50, 55, -1.4, 1.4, "magma")
    # 흘러내리는 방울
    for (x, y, L) in ((11, 43.5, 3), (15, 40.5, 4)):
        w.box(x - 1, x + 1, y - L, y, -0.9, 0.9, "magma")
        w.box(x - 1, x, y - L - 1.5, y - L, -0.5, 0.5, "magma")
    return w


# ─────────────────────────── boss / prism ───────────────────────────

def inferno_hammer():
    """화염 거신의 망치: 거대한 흑철 덩이, 가운데 창살 속에 타오르는 심장, 양끝 용암 통풍구, 뿔."""
    m = {
        "black": Mat(["#141012", "#241c1e", "#382c2c", "#4e3e3a"], "metal", seed=111),
        "bronze": Mat(["#4a1e0c", "#7a3414", "#a8541e", "#d07a30"], "metal", seed=112),
        "magma": Mat(["#8a1a00", "#e04a08", "#ffa020", "#fff0a0"], "fire", glow=True, seed=113),
        "heart": Mat(["#c02000", "#ff6a10", "#ffd040", "#fffbe0"], "pulse", glow=True, seed=114),
        "horn": Mat(["#1a1214", "#2e2226", "#4a3a3a", "#6a5650"], "stone", seed=115),
        "grip": Mat(["#1a0c08", "#3a1a10", "#5a2a18", "#7a3a20"], "grip", seed=116),
    }
    w = Weapon(m, grip_y=11, kind="hammer", seed=111)
    w.cyl(0, 52, 2.2, "black")
    w.cyl(4, 19, 2.6, "grip")
    w.box(-3, 3, 0, 3, -3, 3, "bronze")
    rings(w, (20, 26), 2.7, "bronze")
    for y in (31, 38):
        w.box(-0.5, 0.5, y, y + 4, 1.4, 2.4, "magma")
    # 목 장식 (가시 달린 깃)
    w.box(-4, 4, 46, 50, -4, 4, "bronze")
    for s in (-1, 1):
        w.box(s * 4 if s > 0 else -6, 6 if s > 0 else -4, 47, 48.5, -1, 1, "bronze")
    cy = 60
    w.box(-11, 11, cy - 9, cy + 9, -6.5, 6.5, "black")
    # 양끝 망치머리 (더 크게)
    for s in (-1, 1):
        lo, hi = (10.5, 16) if s > 0 else (-16, -10.5)
        w.box(lo, hi, cy - 11, cy + 11, -8, 8, "black")
        bl, bh = (10, 11.5) if s > 0 else (-11.5, -10)
        w.box(bl, bh, cy - 11.5, cy + 11.5, -8.5, 8.5, "bronze")
        el, eh = (15, 16) if s > 0 else (-16, -15)
        w.box(el, eh, cy - 7, cy + 7, -5, 5, "magma")
        for y in (cy - 6, cy - 2, cy + 2, cy + 6):
            w.box(lo + 1.5, hi - 1.5, y, y + 1, 7, 8, "magma")
            w.box(lo + 1.5, hi - 1.5, y, y + 1, -8, -7, "magma")
        # 뿔
        w.tube([(s * 14, cy + 10, 0), (s * 18, cy + 11, 0), (s * 21, cy + 9, 0), (s * 23, cy + 5, 0)],
               lambda t: 2.6 - 1.8 * t, "horn")
    # 창살 속 심장
    w.clear(lambda X, Y, Z: (np.abs(X) <= 6) & (np.abs(Y - cy) <= 6) & (np.abs(Z) <= 7))
    w.ball(0, cy, 0, 4.6, 5.2, 4.6, "heart")
    for x in (-3.5, 2.5):
        w.box(x, x + 1, cy - 6, cy + 6, 5, 7, "bronze")
        w.box(x, x + 1, cy - 6, cy + 6, -7, -5, "bronze")
    w.box(-6, 6, cy - 0.5, cy + 0.5, 5, 7, "bronze")
    w.box(-6, 6, cy - 0.5, cy + 0.5, -7, -5, "bronze")
    w.set_aura(["#8a1000", "#ff4a0a", "#ffa020", "#fff4b0"], "flame", size=1.2, focus=["magma", "heart"])
    return w


def thundergod_hammer():
    """천뢰의 망치: 금 고리 속 무지개 핵, 양쪽으로 벌어지는 폭풍 수정 머리, 머리 위로 치솟는 번개 두 줄기."""
    m = {
        "navy": Mat(["#0e1230", "#1a2050", "#283070", "#3a4490"], "metal", seed=121),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff0a0"], "metal", seed=122),
        "white": Mat(["#8a8aa0", "#b8bccc", "#dde2ec", "#ffffff"], "metal", seed=123),
        "crystal": Mat(["#1a2a8a", "#2a6ae0", "#5ad0ff", "#e8ffff"], "flow", glow=True, seed=124),
        "core": Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=125),
        "bolt": Mat(["#e8c020", "#ffe050", "#fff4a0", "#ffffff"], "pulse", glow=True, seed=126),
        "grip": Mat(["#0a0e24", "#141c40", "#20305e", "#2e4480"], "grip", seed=127),
    }
    w = Weapon(m, grip_y=11, kind="hammer", seed=112)
    w.cyl(0, 52, 2.2, "navy")
    w.cyl(4, 19, 2.6, "grip")
    rings(w, (19, 32, 45), 2.7, "gold")
    w.box(-3, 3, 0, 3, -3, 3, "gold")
    w.box(-1, 1, 3, 4, -1, 1, "crystal")
    cy = 59
    # 양쪽 수정 머리 (끝으로 갈수록 벌어진다)
    def hd(X, Y, Z):
        ax = np.abs(X)
        h = 4.5 + (ax - 7) * 0.32
        zz = 4 + (ax - 7) * 0.2
        return (ax >= 7) & (ax <= 19) & (np.abs(Y - cy) <= h) & (np.abs(Z) <= zz) & (np.abs(Y - cy) + np.abs(Z) <= h + zz - 2)
    w.fill(hd, "crystal")
    w.fill(lambda X, Y, Z: hd(X, Y, Z) & (np.abs(X) >= 18), "white")
    w.fill(lambda X, Y, Z: (np.abs(X) >= 7) & (np.abs(X) <= 9) & (np.abs(Y - cy) <= 5.5) & (np.abs(Z) <= 5), "gold")
    w.fill(lambda X, Y, Z: (np.abs(X) >= 16) & (np.abs(X) <= 17) & hd(X * 0 + 18 * np.sign(X), Y, Z * 0.9), "gold")
    # 금 고리와 무지개 핵
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - cy) <= 7.5) & (np.hypot(X, Y - cy) >= 5) & (np.abs(Z) <= 2.2), "gold")
    w.ball(0, cy, 0, 4.4, 4.4, 3.4, "core")
    w.box(-7, 7, cy - 1, cy + 1, -1.5, 1.5, "navy")
    w.ball(0, cy, 0, 3.6, 3.6, 3.6, "core")
    # 번개 두 줄기
    for s in (-1, 1):
        bolt = poly([(s * 11, cy + 5), (s * 15, cy + 5), (s * 15, cy + 8), (s * 18.5, cy + 8), (s * 18, cy + 13.5),
                     (s * 15.5, cy + 10.5), (s * 15.5, cy + 13), (s * 13, cy + 8.5), (s * 13, cy + 7.5)][::s])
        w.prism(bolt, 1.0, "bolt")
    w.set_aura(["#1a2a8a", "#2a6ae0", "#5ad0ff", "#e8ffff"], "bolt", size=1.3, focus=["crystal", "core", "bolt"])
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
