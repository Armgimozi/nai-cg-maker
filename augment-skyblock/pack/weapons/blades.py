"""
blades 그룹: 검과 카타나 12 자루.
각 무기는 이름/속성/등급에 맞게 따로 디자인했다 (같은 틀을 돌려 쓰지 않는다).
  basic  : 소박한 재료, 부품 적게, 빛 없음
  island : 섬 재료로 만든 개성, 아주 작은 빛 포인트까지만
  flame  : 속성이 분명한 모양 + 빛나는 심지
  boss / prism : 화려하고 유일한 모양 + 아우라 (이 그룹에서는 성검, 혈월의 카타나, 태양검만)

단면/곡선/손잡이를 일부러 서로 다르게 했다.
  단면: 납작+풀러(견습생) / 납작 2복셀+밝은 모서리(글라디우스) / 둥근 타원(목도) / 가운데 구멍(바람)
        / 얇은 외날(해적) / 두꺼운 등+얇은 날(폭풍, 혈월) / 톱니 외날(혈검) / 불꽃 가장자리(화염) / 넓은 십자 홈(성검)
  카타나 휨: 목도=고른 휨+둥근 끝, 해적=끝쪽 휨(사키조리)+잘린 끝, 폭풍=밑동 휨(코시조리)+키사키, 혈월=깊은 휨+큰 키사키
  손잡이: 짧은 글라디우스 ~ 16복셀 노다치까지
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
    return np.clip((1 - t) / (1 - t0), 0, 1) ** p


def ramp_in(t, t0, p=1.3):
    """t0 이후로 0 → 1 로 커지는 값."""
    return np.clip((t - t0) / (1 - t0), 0, 1) ** p


def capsule(X, Y, p0, p1, r0, r1=None):
    """2D: 선분 p0→p1 둘레 반지름 r0→r1 안쪽."""
    r1 = r0 if r1 is None else r1
    ax, ay = p1[0] - p0[0], p1[1] - p0[1]
    L2 = ax * ax + ay * ay or 1e-6
    t = np.clip(((X - p0[0]) * ax + (Y - p0[1]) * ay) / L2, 0, 1)
    d = np.hypot(X - p0[0] - ax * t, Y - p0[1] - ay * t)
    return d <= r0 + (r1 - r0) * t


def stroke(X, Y, pts, r0, r1=None):
    """2D: 꺾은선 둘레 (반지름 r0 → r1 로 가늘어짐)."""
    r1 = r0 if r1 is None else r1
    n = len(pts) - 1
    m = np.zeros(np.shape(X), dtype=bool)
    for i in range(n):
        m |= capsule(X, Y, pts[i], pts[i + 1], r0 + (r1 - r0) * i / n, r0 + (r1 - r0) * (i + 1) / n)
    return m


def flat(w, mask, depth, mat):
    """2D 모양(stroke 등)을 앞뒤로 depth 만큼 세운다."""
    w.prism(mask, depth, mat)


# ─────────────────────────── basic ───────────────────────────

def apprentice_sword():
    """견습생의 검: 곧은 쇠 날 + 가운데 홈(풀러), 끝이 뭉툭한 일자 가드, 가죽 손잡이, 원반 폼멜. 정직한 첫 검."""
    m = {
        "steel": Mat(["#565c66", "#6c727c", "#828892", "#a6acb6"], "metal", seed=101),
        "edge": Mat(["#b4bac2", "#c8ced6", "#dde1e6", "#ffffff"], "metal", seed=102),
        "iron": Mat(["#25272d", "#3a3d44", "#50545c", "#7c8088"], "metal", seed=103),
        "leather": Mat(["#2a170c", "#4a2a16", "#6a3e22", "#8a5632"], "grip", seed=104),
    }
    w = Weapon(m, grip_y=8.75, kind="sword", seed=101)
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 2.6) <= 2.7) & (np.abs(Z) <= 1.5), "iron")      # 원반 폼멜
    w.cyl(4.5, 13, 1.6, "leather")
    w.box(-6.6, 6.6, 13, 15.9, -1.6, 1.6, "iron")                                          # 일자 가드
    w.fill(lambda X, Y, Z: (np.abs(X) >= 5) & (np.abs(X) <= 7.2) & (Y >= 12) & (Y <= 16.9) & (np.abs(Z) <= 1.6), "iron")
    hw = lambda t: 1.0 + 2.0 * taper(t, 0.76)            # 끝은 2복셀 뾰족
    sect(w, 16, 48, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("steel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    fl = lambda X, Y: (np.abs(X) < 1) & (Y >= 17) & (Y <= 40)                            # 풀러
    w.fill(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) <= 0.5), "iron")
    w.clear(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) > 1))
    return w


def copper_sword():
    """구리 검: 짧은 글라디우스. 나란한 두 날 + 짧은 삼각 끝, 납작한 단면에 밝은 모서리, 녹청 가드, 구리선 감은 손잡이, 둥근 고리 폼멜."""
    m = {
        "copper": Mat(["#7a3a1c", "#94482a", "#a85834", "#c06a40"], "flat", seed=111),
        "bevel": Mat(["#e08a58", "#f0a070", "#ffbe90", "#ffe0c8"], "flat", seed=112),
        "dark": Mat(["#4a1e0c", "#5e2812", "#70321a", "#843e22"], "flat", seed=115),
        "patina": Mat(["#1e5a50", "#2e8a76", "#4ab89a", "#86e0c4"], "stone", seed=113),
        "wire": Mat(["#5a2810", "#9a5028", "#d07a40", "#f8b880"], "grip", seed=114),
    }
    # 짧은 칼이라 손에 들었을 때도 짧게 보이도록 dagger 크기 기준
    w = Weapon(m, grip_y=9.5, kind="dagger", seed=111)
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 3.0) <= 3.4) & (np.hypot(X, Y - 3.0) >= 1.6) & (np.abs(Z) <= 1.0), "bevel")
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 3.0) <= 2.6) & (np.hypot(X, Y - 3.0) >= 1.6) & (np.abs(Z) <= 1.0), "copper")
    w.cyl(6, 13, 1.6, "wire")                                         # 구리선 감은 짧은 손잡이
    w.box(-4.1, 4.1, 13, 15.9, -1.6, 1.6, "patina")                   # 녹청 슨 가드
    w.box(-4.1, 4.1, 15, 15.9, -1.6, 1.6, "copper")
    hw = lambda t: 1.0 + 2.0 * taper(t, 0.8, 1.0)                     # 나란한 날 + 짧은 삼각 끝
    sect(w, 16, 38, lambda t: -hw(t), hw, [
        ("bevel", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("copper", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 0.5)),
        ("dark", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 1) & (t < 0.72) & (np.abs(Z) <= 0.5)),
    ])
    return w


def wooden_katana():
    """목도: 밝은 참나무를 깎은 두툼한 휜 칼(둥근 끝), 어두운 천을 감은 손잡이, 검은 칠 코등이와 밝은 테, 나무 그대로의 끝."""
    m = {
        "oak": Mat(["#a2783e", "#ba8e50", "#d0a666", "#ecc890"], "wood", seed=121),
        "wrap": Mat(["#14100c", "#241c16", "#362a20", "#4a3a2c"], "grip", seed=122),
        "lacq": Mat(["#0a0808", "#141010", "#1e1818", "#2c2424"], "flat", seed=123),
        "rim": Mat(["#6a6460", "#8e8680", "#b0a8a0", "#d4ccc4"], "metal", seed=124),
    }
    w = Weapon(m, grip_y=10, kind="katana", seed=121)
    w.ball(0, 2.4, 0, 2.4, 2.6, 2.1, "oak")                   # 나무 끝(카시라 자리)
    w.cyl(2.5, 17, 1.9, "wrap", rz=1.7)
    w.cyl(16.5, 18.9, 2.4, "oak", rz=2.1)                     # 후치 자리 (나무)
    w.cyl(19, 21.9, 5.6, "lacq", rz=4.6)                      # 검은 칠 코등이
    w.fill(lambda X, Y, Z: ((X / 5.6) ** 2 + (Z / 4.6) ** 2 <= 1) & ((X / 4.4) ** 2 + (Z / 3.4) ** 2 > 1) &
           (Y >= 21) & (Y <= 21.9), "rim")                      # 위쪽 밝은 테
    w.cyl(22, 22.9, 2.6, "lacq", rz=2.0)                      # 코등이 받침
    y0, y1 = 23, 64
    c = lambda t: -2.0 * t ** 2
    hw = lambda t: 2.7 - 0.5 * t
    r_tip = hw(1.0)

    def body(X, Y):
        t = np.clip((Y - y0) / (y1 - y0), 0, 1)
        band = (Y >= y0) & (Y <= y1) & (np.abs(X - c(t)) <= hw(t))
        cap = np.hypot(X - c(1.0), Y - y1) <= r_tip                # 둥근 끝
        return band | cap, hw(t) - np.abs(X - c(t)), np.hypot(X - c(1.0), Y - y1)

    w.fill(lambda X, Y, Z: (lambda b: b[0] & (np.abs(Z) <= 0.5))(body(X, Y)), "oak")
    w.fill(lambda X, Y, Z: (lambda b: b[0] & ((Y <= y1) | (b[2] <= r_tip - 1)) & (np.abs(Z) <= 1.5))(body(X, Y)), "oak")
    return w


# ─────────────────────────── island ───────────────────────────

def wind_sword():
    """바람의 검: 깊은 청록 강철에 흰 날, 한쪽 날에 위로 겹친 깃털 계단, 바람 구멍, 납작한 소용돌이 가드, 바람에 날리는 리본."""
    m = {
        "steel": Mat(["#1a4444", "#245a5a", "#307272", "#468c8c"], "metal", seed=131),
        "edge": Mat(["#d6efec", "#e8f8f6", "#f6fffd", "#ffffff"], "flat", seed=132),
        "silver": Mat(["#5a6470", "#8e98a4", "#c2cad4", "#eef2f6"], "metal", seed=133),
        "jade": Mat(["#0e3a2a", "#1a6a4a", "#2e9a6a", "#5ac898"], "grip", seed=134),
        "ribbon": Mat(["#7ab8b0", "#a8dcd4", "#d2f2ee", "#f4fffd"], "cloth", seed=136),
        "glint": Mat(["#2aa0a0", "#5ae0d8", "#a8fff4", "#ffffff"], "gem", glow=True, seed=135),
    }
    w = Weapon(m, grip_y=10, kind="sword", seed=131)
    # 바람에 날리는 리본 (폼멜에 묶임, 끝이 갈라짐)
    w.tube([(-1, 3.0, 0.5), (-4, 4.6, 0.5), (-7.5, 3.0, 0.5), (-11, 4.6, 0.5)], lambda t: 1.5 - 0.6 * t, "ribbon", rz=0.6)
    w.ball(0, 3.2, 0, 2.1, 2.6, 2.1, "silver")               # 물방울 폼멜 + 작은 빛 구슬
    w.gem(0, 3.2, 0.9, "glint", depth=2.6)
    w.cyl(5, 15, 1.6, "jade")
    # 소용돌이 가드: 오른쪽은 위로, 왼쪽은 아래로 말린다 (납작한 판, 굵게)
    w.box(-2.6, 2.6, 15, 17.9, -1.6, 1.6, "silver")
    curl = [(2, 16.5), (6, 16.2), (9.4, 17.6), (10.4, 20.8), (8.8, 23.2), (6.6, 22.8), (6.0, 20.6), (7.4, 19.6)]
    flat(w, lambda X, Y: stroke(X, Y, curl, 1.3, 1.1), 1.0, "silver")
    flat(w, lambda X, Y: stroke(X, Y, [(-x, 33 - y) for x, y in curl], 1.3, 1.1), 1.0, "silver")
    # 날: 왼쪽은 곧고, 오른쪽에는 위로 겹친 깃털(돌풍) 계단 셋
    y0, y1 = 18, 61
    base = lambda t: 1.0 + 2.0 * taper(t, 0.78, 1.0)

    def gust(t):
        Y = y0 + t * (y1 - y0)
        f = np.clip((Y - 25) / 8.0, 0, 3)
        k = np.where(f < 3, f % 1.0, 0)
        return 2.2 * k ** 1.6 * (Y < 49)
    sect(w, y0, y1, lambda t: -base(t), lambda t: base(t) + gust(t), [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("steel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])
    # 바람 구멍: 가운데를 길게 뚫는다 (양 끝은 뾰족)
    w.clear(lambda X, Y, Z: (np.abs(X) < 1.25 * np.sin(np.pi * np.clip((Y - 21) / 26, 0, 1))) & (Y > 21) & (Y < 47))
    return w


def pirate_katana():
    """해적의 카타나: 끝으로 갈수록 넓어지고 더 휘는 커틀러스 날, 잘린 끝, 한 줄 물결 하몬, 큰 이빠짐, 놋쇠 손등 보호대(D가드)."""
    m = {
        "steel": Mat(["#56606a", "#68727c", "#7c8690", "#a0aab4"], "metal", seed=141),
        "edge": Mat(["#c8d4dc", "#dce6ec", "#eef6fa", "#ffffff"], "flat", seed=142),
        "brass": Mat(["#5a3e10", "#9a7020", "#d0a438", "#f6dc80"], "metal", seed=144),
        "grip": Mat(["#120e0c", "#221a16", "#342820", "#48382c"], "grip", seed=145),
        "sash": Mat(["#5a0a0a", "#8a1414", "#c02424", "#e85050"], "cloth", seed=146),
    }
    w = Weapon(m, grip_y=9, kind="katana", seed=141)
    w.ball(0, 2.2, 0, 2.2, 2.0, 2.0, "brass")                         # 폼멜 캡
    w.cyl(3, 15, 1.6, "grip")
    w.cyl(8, 9.9, 1.9, "sash")                                         # 붉은 천 띠
    w.box(-4.6, 4.6, 14.5, 16.9, -1.6, 1.6, "brass")                   # 가드 막대
    w.ball(0, 15.7, 0, 2.2, 1.6, 2.6, "brass")
    # 손등 보호대 (D 가드): 가드 오른쪽 끝에서 폼멜까지
    flat(w, lambda X, Y: stroke(X, Y, [(4, 15.6), (6.8, 14.4), (7.6, 10.5), (6.8, 6), (4.6, 2.8), (1.6, 2.0)], 1.1), 1.0, "brass")
    # 왼쪽(칼등 쪽) 끝은 위로 말린 고리
    flat(w, lambda X, Y: stroke(X, Y, [(-4.4, 15.7), (-6.8, 16.6), (-7.6, 19.0), (-6.2, 20.4)], 1.1, 0.9), 1.0, "brass")
    y0, y1 = 17, 64
    c = lambda t: -6.0 * t ** 2.4                                      # 끝쪽이 더 휜다 (사키조리)
    wl = lambda t: 2.2 + 0 * t
    wr = lambda t: 2.0 + 2.0 * t                                       # 끝으로 갈수록 넓은 날
    P = lambda: c(1.0) - 0.8                                           # 끝점 (칼등 쪽)
    s = lambda t: ramp_in(t, 0.8, 1.0)
    lo = lambda t: (c(t) - wl(t)) * (1 - s(t)) + (P() - 0.6) * s(t)                     # 칼등: 곧게 잘린 끝
    hi = lambda t: (c(t) + wr(t)) * (1 - s(t) ** 1.8) + (P() + 0.6) * s(t) ** 1.8         # 날: 둥글게 올라감
    ham = lambda Y: 1.9 + 0.9 * np.sin((Y - y0) * 2 * np.pi / 20.0)
    sect(w, y0, y1, lo, hi, [
        ("steel", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("edge", lambda X, Y, Z, dl, dr, t: (dr < ham(Y)) & (np.abs(Z) <= 0.5)),
    ])
    # 칼등의 큰 이빠짐
    tt = (45 - y0) / (y1 - y0)
    xl = c(tt) - wl(tt)
    w.clear(lambda X, Y, Z: (np.abs(X - (xl - 0.4)) * 1.1 + np.abs(Y - 45) * 0.8 <= 2.6))      # V 자로 깊게
    return w


def crystal_sword():
    """수정 검: 견습생의 검에 자수정이 자랐다. 쇠 날 위에서 가늘게 솟아 큰 결정 기둥이 되고, 한 자리에서 결정 둘이 갈라지며, 가드 끝에도 작은 송이."""
    m = {
        "steel": Mat(["#565c66", "#6c727c", "#828892", "#a6acb6"], "metal", seed=151),
        "edge": Mat(["#b4bac2", "#c8ced6", "#dde1e6", "#ffffff"], "metal", seed=157),
        "iron": Mat(["#25272d", "#3a3d44", "#50545c", "#7c8088"], "metal", seed=152),
        "leather": Mat(["#2a170c", "#4a2a16", "#6a3e22", "#8a5632"], "grip", seed=153),
        "ame_d": Mat(["#2a0c52", "#3c1870", "#4e2488", "#6436a2"], "gem", seed=154),
        "ame_l": Mat(["#a678ec", "#bc96f6", "#d6bcff", "#f6eeff"], "gem", seed=155),
        "shine": Mat(["#c8a0ff", "#e0c8ff", "#f4ecff", "#ffffff"], "sparkle", glow=True, seed=156),
    }
    w = Weapon(m, grip_y=8.75, kind="sword", seed=151)
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 2.6) <= 2.7) & (np.abs(Z) <= 1.5), "iron")
    w.cyl(4.5, 13, 1.6, "leather")
    w.box(-6.6, 6.6, 13, 15.9, -1.6, 1.6, "iron")
    w.fill(lambda X, Y, Z: (np.abs(X) >= 5) & (np.abs(X) <= 7.2) & (Y >= 12) & (Y <= 16.9) & (np.abs(Z) <= 1.6), "iron")
    sect(w, 16, 31, lambda t: -3.0 + 0 * t, lambda t: 3.0 + 0 * t, [                    # 원래 쇠 날
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("steel", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])

    def crystal(x0, y0, ang, L, r, tip=0.35, depth=2.0, grow=0.0, shine=0):
        """결정: 뿌리(grow 구간)는 가늘고, 끝이 뾰족한 각기둥. 왼쪽 면은 밝고 오른쪽 면은 어둡다."""
        a = math.radians(ang)
        ca, sa = math.cos(a), math.sin(a)

        def geo(X, Y, Z):
            u = (X - x0) * ca + (Y - y0) * sa
            v = -(X - x0) * sa + (Y - y0) * ca
            wd = r * np.clip((L - u) / (L * tip), 0, 1)
            if grow:
                wd = wd * (0.45 + 0.55 * np.clip(u / grow, 0, 1))
            inside = (u >= -0.5) & (u <= L) & (np.abs(v) <= wd + 0.15)
            zd = depth
            return inside & (np.abs(Z) <= zd), v, u
        w.fill(lambda X, Y, Z: (lambda g: g[0] & (g[1] > 0))(geo(X, Y, Z)), "ame_l")
        w.fill(lambda X, Y, Z: (lambda g: g[0] & (g[1] <= 0))(geo(X, Y, Z)), "ame_d")
        if shine:
            w.fill(lambda X, Y, Z: (lambda g: g[0] & (g[2] > L - shine) & (g[1] > 0))(geo(X, Y, Z)), "shine")

    crystal(0, 26, 90, 41, 3.2, tip=0.3, depth=2.6, grow=8, shine=4)     # 날을 삼킨 큰 결정 기둥
    crystal(-0.5, 29, 114, 21, 2.1, tip=0.4, depth=2.0)                   # 한 자리에서 갈라진 두 결정
    crystal(1.0, 29, 58, 12, 1.7, tip=0.5, depth=1.6)
    crystal(5.6, 15, 70, 7.5, 1.5, tip=0.5, depth=1.6)                   # 가드 끝의 작은 송이
    crystal(6.4, 14.5, 32, 5, 1.2, tip=0.6, depth=1.5)
    return w


def storm_katana():
    """폭풍의 카타나: 가늘고 긴 타치(밑동에서 휜 코시조리 + 키사키 끝), 먹색 날에 각진 금빛 번개 상감과 빛나는 불꽃 두 점, 위로 뻗은 Z 번개 갈퀴."""
    m = {
        "gun": Mat(["#1c2230", "#262e40", "#323c52", "#4a5670"], "metal", seed=161),
        "spine": Mat(["#0e1018", "#161a24", "#1e2432", "#2c3446"], "metal", seed=167),
        "edge": Mat(["#a8b4cc", "#c4cee2", "#e0e8f6", "#ffffff"], "flat", seed=162),
        "inlay": Mat(["#8a7430", "#b09444", "#d0b462", "#ecd890"], "flat", seed=163),
        "spark": Mat(["#e0b010", "#ffe040", "#fff4a0", "#ffffff"], "pulse", glow=True, seed=168),
        "iron": Mat(["#202028", "#383844", "#545464", "#747488"], "metal", seed=164),
        "wrap": Mat(["#140e28", "#241a48", "#3a2c6e", "#5a4898"], "grip", seed=165),
        "silver": Mat(["#6a7080", "#a0a8b8", "#d0d6e2", "#f4f6fa"], "metal", seed=166),
    }
    w = Weapon(m, grip_y=10, kind="katana", seed=161)
    w.cyl(0.5, 2.9, 1.9, "silver")
    w.cyl(2.5, 18, 1.6, "wrap")
    w.cyl(18, 19.9, 3.4, "iron", rz=3.0)
    # Z 번개 갈퀴 (칼등 쪽, 위로 비스듬히)
    flat(w, lambda X, Y: capsule(X, Y, (-2.2, 19.4), (-6.4, 23.0), 1.4, 1.2) | capsule(X, Y, (-6.4, 23.0), (-4.2, 23.8), 1.2) |
         capsule(X, Y, (-4.2, 23.8), (-9.6, 30.0), 1.2, 0.35), 1.0, "silver")
    w.box(-1.6, 2.6, 20, 21.9, -1.1, 1.1, "silver")          # 하바키
    y0, y1 = 21, 71
    c = lambda t: -4.2 * (1 - (1 - t) ** 2.2)                  # 밑동에서 휘고 끝쪽은 곧다
    hw = lambda t: 2.6 - 0.6 * t
    hi = lambda t: c(t) + hw(t) - 2 * hw(t) * ramp_in(t, 0.9, 0.8)   # 둥글게 올라가는 키사키
    sect(w, y0, y1, lambda t: c(t) - hw(t), hi, [
        ("gun", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("spine", lambda X, Y, Z, dl, dr, t: (dl < 1) & (np.abs(Z) <= 1.5) & (t < 0.92)),
        ("edge", lambda X, Y, Z, dl, dr, t: (dr < 1) & (np.abs(Z) <= 0.5)),
    ])
    # 번개 상감: 날 가운데를 따라 각지게 꺾이고 한 번 갈라진다
    cx = lambda Y: c(np.clip((Y - y0) / (y1 - y0), 0, 1)) + 0.5
    main = [(0.0, 23), (-0.9, 27.5), (0.9, 29), (-0.7, 34), (1.0, 35.5), (-0.6, 41), (0.8, 42.5), (0.0, 48)]
    fork = [(1.0, 35.5), (0.2, 38.5), (1.4, 40)]
    s = w.grid.copy() > 0
    loc = lambda X, Y, pts, r: stroke(X - cx(Y), Y, pts, r)
    w.fill(lambda X, Y, Z: s & loc(X, Y, main, 0.55) & (np.abs(Z) <= 0.5), "inlay")
    w.fill(lambda X, Y, Z: s & loc(X, Y, fork, 0.55) & (np.abs(Z) <= 0.5), "inlay")
    w.fill(lambda X, Y, Z: s & (loc(X, Y, main[2:4], 0.55) | loc(X, Y, fork[1:], 0.55)) & (np.abs(Z) <= 0.5), "spark")
    return w


def blood_sword():
    """혈검: 검붉은 날에 밝은 핏빛 테, 한쪽에 크고 두꺼운 갈고리 톱니 셋, 칼등 쪽 피홈, 아래로 휜 송곳니 가드, 검은 테 핏방울, 층진 가시 폼멜."""
    m = {
        "crim": Mat(["#2a0408", "#3c0810", "#520c16", "#6c1420"], "metal", seed=171),
        "edge": Mat(["#c02a34", "#e04450", "#ff7480", "#ffc8cc"], "flat", seed=172),
        "black": Mat(["#120a0c", "#24161a", "#38242a", "#4e343a"], "metal", seed=173),
        "bone": Mat(["#6a5a48", "#a8987e", "#d4c6aa", "#f2ead6"], "stone", seed=174),
        "wrap": Mat(["#3a0c12", "#5a1420", "#7a2030", "#9a3040"], "grip", seed=175),
        "drop": Mat(["#5a0010", "#b0102a", "#ff3050", "#ffc0c8"], "gem", glow=True, seed=176),
    }
    w = Weapon(m, grip_y=9.5, kind="sword", seed=171)
    # 층진 가시 폼멜: 위 원뿔 + 밝은 띠 + 아래 가시
    w.tube([(0, 6, 0), (0, 3.6, 0)], lambda t: 2.0 - 0.3 * t, "black")
    w.cyl(2.9, 3.6, 1.9, "edge")
    w.tube([(0, 3.0, 0), (0, 0.4, 0)], lambda t: 1.5 * (1 - t) + 0.4, "black")
    w.cyl(5, 14.5, 1.6, "wrap")
    w.box(-4.6, 4.6, 14, 16.9, -1.6, 1.6, "black")
    for sx in (1, -1):                                                     # 송곳니 가드 (아래로)
        w.tube([(sx * 3.5, 15.5, 0), (sx * 6.5, 15, 0), (sx * 8, 12, 0), (sx * 7, 8, 0)],
               lambda t: 1.5 * (1 - t) + 0.5, "bone")
    y0, y1 = 17, 54
    base = lambda t: 1.0 + (2.2 - 0.4 * t) * taper(t, 0.78)

    sect(w, y0, y1, lambda t: -base(t), base, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("crim", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
    ])

    def sd(X, Y, a, b):                       # 선 a→b 왼쪽으로의 거리
        dx, dy = b[0] - a[0], b[1] - a[1]
        return (dx * (Y - a[1]) - dy * (X - a[0])) / math.hypot(dx, dy)
    for yb in (21, 29.5, 38):                 # 아래로 걸리는 큰 톱니 셋 (끝이 뿌리보다 낮다)
        xb = float(base((yb + 3 - y0) / (y1 - y0))) - 0.6
        A, B, C = (xb, yb + 6.5), (xb, yb + 1), (xb + 4.2, yb - 1.0)
        w.fill(lambda X, Y, Z, A=A, B=B, C=C: (np.minimum(np.minimum(sd(X, Y, A, B), sd(X, Y, B, C)), sd(X, Y, C, A)) >= 0) &
               (np.abs(Z) <= 0.5), "edge")
        w.fill(lambda X, Y, Z, A=A, B=B, C=C: (sd(X, Y, A, B) >= -1.5) & (np.minimum(sd(X, Y, B, C), sd(X, Y, C, A)) >= 1.0) &
               (np.abs(Z) <= 1.5), "crim")
    fl = lambda X, Y: (X > -2) & (X < 0) & (Y >= 18) & (Y <= 42)          # 칼등 쪽 피홈
    w.fill(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) <= 0.5), "black")
    w.clear(lambda X, Y, Z: fl(X, Y) & (np.abs(Z) > 1))
    # 검은 테 안의 작은 핏방울
    drop = lambda X, Y, k=0.0: (np.hypot(X, Y - 15.0) <= 1.3 + k) | ((np.abs(X) < 0.9 + k * 0.6) & (Y > 15) & (Y < 17.4 + k))
    w.fill(lambda X, Y, Z: drop(X, Y, 1.0) & (np.abs(Z) <= 2.0), "black")
    w.fill(lambda X, Y, Z: drop(X, Y) & (np.abs(Z) <= 2.5), "drop")
    return w


# ─────────────────────────── flame (rift) ───────────────────────────

def flame_sword():
    """화염 검: 곧은 몸통에 위로 타오르는 불꽃 혀 모양 가장자리, 검붉게 달군 날과 달아오른 테, 가운데 쇳물 줄, 바깥으로 뻗은 흑요석 뿔(한쪽 길게)."""
    m = {
        "char": Mat(["#280606", "#3c0a08", "#52100a", "#6e1a0e"], "metal", seed=181),
        "hot": Mat(["#b02808", "#d84410", "#f87020", "#ffb040"], "flat", seed=182),
        "magma": Mat(["#a01800", "#e85a0a", "#ffa020", "#fff2a0"], "fire", glow=True, seed=183),
        "obsid": Mat(["#140c22", "#2a1a44", "#4a2e70", "#7a52a8"], "stone", seed=184),
        "ember": Mat(["#7a1800", "#ff5a10", "#ffb040", "#fff4c0"], "pulse", glow=True, seed=185),
        "wrap": Mat(["#1a0a06", "#2e140a", "#4a2010", "#6a3018"], "grip", seed=186),
    }
    w = Weapon(m, grip_y=9, kind="sword", seed=181)
    w.ball(0, 2.6, 0, 2.3, 2.6, 2.1, "obsid")
    w.gem(0, 2.6, 1.0, "ember", depth=2.6)
    w.cyl(4.5, 13.5, 1.6, "wrap")
    w.box(-3.1, 3.1, 13, 16.9, -1.6, 1.6, "obsid")
    # 흑요석 뿔: 바깥으로 뻗다가 끝만 살짝 위로. 오른쪽 길게, 왼쪽 짧게. 끝은 달아올랐다
    right = [(2.5, 15), (6.5, 15.2), (10, 16.4), (12.6, 18.6), (13.6, 21.2)]
    left = [(-2.5, 15), (-5.8, 15.2), (-8.4, 16.6), (-9.6, 19.0)]
    flat(w, lambda X, Y: stroke(X, Y, right, 2.0, 0.6), 1.5, "obsid")
    flat(w, lambda X, Y: stroke(X, Y, left, 2.0, 0.7), 1.5, "obsid")
    w.ball(13.4, 20.6, 0, 1.0, 1.5, 1.0, "hot")
    w.ball(-9.4, 18.6, 0, 1.0, 1.4, 1.0, "hot")
    # 날: 곧은 가운데 + 위로 타오르는 불꽃 혀 가장자리 (좌우 엇갈림)
    y0, y1 = 17, 63
    base = lambda t: 1.0 + (2.8 - 0.8 * t) * taper(t, 0.82)

    def lick(t, ph):
        Y = y0 + t * (y1 - y0)
        f = ((Y - y0) / 7.0 + ph) % 1.0
        return 1.4 * f ** 1.6 * (t < 0.8)
    sect(w, y0, y1, lambda t: -base(t) - lick(t, 0.5), lambda t: base(t) + lick(t, 0.0), [
        ("hot", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("char", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("magma", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 1) & (t > 0.02) & (t < 0.62) & (np.abs(Z) <= 1.5)),
    ])
    return w


# ─────────────────────────── boss / prism (aura) ───────────────────────────

def holy_blade():
    """성검: 넓은 은빛 날에 빛나는 금 십자, 끝이 백합 문양으로 피어난 금 가드, 십자를 새긴 해 원반 장식, 금 삼엽 폼멜. 신성 아우라."""
    m = {
        "silver": Mat(["#8a92a4", "#a2aabc", "#bcc4d2", "#dce2ec"], "metal", seed=191),
        "edge": Mat(["#e0e4ee", "#eef1f8", "#f8faff", "#ffffff"], "flat", seed=192),
        "gold": Mat(["#6a4a10", "#b08020", "#e8c048", "#fff2a8"], "metal", seed=193),
        "goldd": Mat(["#4a300a", "#6e4a12", "#8e6418", "#ae8028"], "metal", seed=195),
        "light": Mat(["#f0c040", "#ffe070", "#fff6c8", "#ffffff"], "flow", glow=True, seed=194),
        "heart": Mat(["#f8d050", "#ffe890", "#fffae0", "#ffffff"], "pulse", glow=True, seed=196),
        "wrap": Mat(["#0e1a4a", "#1a2a6a", "#2a409a", "#4060c0"], "grip", seed=198),
    }
    w = Weapon(m, grip_y=10, kind="sword", seed=191)
    # 오른쪽 반만 만들고 mirror() 로 왼쪽을 복사한다
    w.ball(0.5, 2.0, 0, 1.9, 1.9, 1.6, "gold")                          # 삼엽 폼멜
    w.ball(1.6, 4.0, 0, 1.4, 1.4, 1.3, "gold")
    w.cyl(4.5, 15, 1.6, "wrap")
    w.cyl(13.5, 14.9, 2.0, "gold")
    # 가드: 끝이 살짝 올라간 막대 + 백합(가운데 꽃잎은 위로, 양 옆은 말림)
    bar = [(0, 16.4), (5, 16.6), (8.6, 18.0)]
    flat(w, lambda X, Y: stroke(X, Y, bar, 1.6, 1.2), 1.5, "gold")
    lily_c = [(8.6, 18.0), (9.8, 21.0), (10.4, 24.2)]
    lily_i = [(8.6, 18.0), (7.6, 20.2), (8.0, 22.0)]
    lily_o = [(8.6, 18.0), (11.0, 18.0), (12.2, 20.0), (11.6, 21.2)]
    flat(w, lambda X, Y: stroke(X, Y, lily_c, 1.5, 0.4), 1.0, "gold")
    flat(w, lambda X, Y: stroke(X, Y, lily_i, 1.0, 0.6) | stroke(X, Y, lily_o, 1.1, 0.6), 1.0, "gold")
    w.fill(lambda X, Y, Z: (np.hypot(X - 8.6, Y - 17.6) <= 1.3) & (np.abs(Z) <= 2.0), "goldd")   # 백합 묶음 띠
    w.mirror()
    # 해 원반 장식 (가운데, 앞뒤로 튀어나옴) + 은 십자 새김
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 17.5) <= 3.4) & (np.abs(Z) <= 2.1), "goldd")
    w.fill(lambda X, Y, Z: (np.hypot(X, Y - 17.5) <= 2.6) & (np.abs(Z) <= 2.6), "gold")
    w.fill(lambda X, Y, Z: (((np.abs(X) < 0.6) & (np.abs(Y - 17.5) < 2.4)) | ((np.abs(Y - 17.5) < 0.6) & (np.abs(X) < 2.4))) &
           (np.abs(Z) <= 2.6) & (np.abs(Z) > 1.6), "edge")
    # 넓은 날 + 빛나는 십자 홈
    y0, y1 = 20, 68
    hw = lambda t: 1.0 + (3.6 - 0.8 * t) * taper(t, 0.84, 0.85)
    sect(w, y0, y1, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("silver", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("light", lambda X, Y, Z, dl, dr, t: (((np.abs(X) < 1) & (Y > 21) & (Y < 50)) | ((np.abs(Y - 32) < 1) & (np.abs(X) < 3.2))) &
         (np.abs(Z) <= 1.5)),
        ("heart", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 1) & (np.abs(Y - 32) < 1) & (np.abs(Z) <= 1.5)),   # 십자 한가운데
    ])
    w.set_aura(["#8a6a10", "#e8c040", "#fff0a0", "#ffffff"], "holy", size=0.8, focus=["heart"])
    return w


def bloodmoon_katana():
    """혈월의 카타나: 긴 손잡이의 노다치, 검은 등·밝은 강철·핏빛 하몬, 칼을 받쳐 든 붉은 초승달 코등이, 카시라에 매단 고리 술."""
    m = {
        "black": Mat(["#0a0608", "#1a1014", "#2a1a20", "#3e262e"], "metal", seed=201),
        "steel": Mat(["#8a8e98", "#a2a6b0", "#bcc0c8", "#dce0e6"], "metal", seed=202),
        "crim": Mat(["#8a0014", "#c00c22", "#e82a3a", "#ff8090"], "flow", glow=True, seed=203),
        "hot": Mat(["#c00818", "#ff2a3a", "#ff7a80", "#ffe0e0"], "pulse", glow=True, seed=208),
        "moon": Mat(["#9a0a18", "#d81830", "#ff4a58", "#ffd8d8"], "pulse", glow=True, seed=204),
        "horn": Mat(["#c01020", "#ff3a48", "#ff8a90", "#ffe8e8"], "pulse", glow=True, seed=209),
        "iron": Mat(["#1a1418", "#2e2228", "#463840", "#605058"], "metal", seed=205),
        "wrap": Mat(["#0c0608", "#1a0c10", "#3a141c", "#5a1e2a"], "grip", seed=206),
        "tassel": Mat(["#5a0a10", "#8a1420", "#c02030", "#e85060"], "cloth", seed=207),
    }
    # 노다치: 손에 든 크기도 대검 기준으로 키운다
    w = Weapon(m, grip_y=13.5, kind="greatsword", seed=201)
    # 고리 술: 카시라 바로 아래 매듭 + 짧은 술
    w.tube([(0.5, 4.5, 0.5), (2.8, 3.8, 0.5)], 0.6, "tassel")
    w.ball(3.2, 3.4, 0, 1.2, 1.2, 1.2, "tassel")
    w.cyl(0, 2.6, 1.3, "tassel", cx=3.2)
    w.cyl(3.5, 5.9, 1.9, "iron")                                       # 카시라
    w.cyl(5.5, 21.5, 1.6, "wrap")                                       # 16복셀 긴 손잡이
    w.cyl(21, 22.9, 2.0, "iron")                                        # 후치
    # 초승달 코등이: 바깥 원 - 위로 밀린 안쪽 원 → 뿔이 위로 선 달
    outer = lambda X, Y, k=0.0: np.hypot(X, Y - 32) <= 10.0 - k
    inner = lambda X, Y, k=0.0: np.hypot(X, Y - 36.5) <= 8.6 + k
    w.prism(lambda X, Y: outer(X, Y) & ~inner(X, Y), 1.5, "iron")
    w.prism(lambda X, Y: outer(X, Y, 1.0) & ~inner(X, Y, 1.0), 2.0, "moon")
    w.prism(lambda X, Y: outer(X, Y, 1.0) & ~inner(X, Y, 1.0) & (Y > 35), 2.0, "horn")      # 달의 두 뿔 끝
    w.box(-2.1, 2.1, 22, 27.9, -1.6, 1.6, "iron")
    y0, y1 = 26, 71
    c = lambda t: -5.0 * t ** 2
    hw = lambda t: 3.2 - 0.6 * t
    hi = lambda t: c(t) + hw(t) - 2 * hw(t) * ramp_in(t, 0.86, 0.6)    # 큰 키사키
    ham = lambda Y: 1.9 + 0.5 * np.sin((Y - y0) * 0.32)
    sect(w, y0, y1, lambda t: c(t) - hw(t), hi, [
        ("steel", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("black", lambda X, Y, Z, dl, dr, t: (dl < 1.2) & (np.abs(Z) <= 1.5) & (t < 0.9)),
        ("crim", lambda X, Y, Z, dl, dr, t: (dr < ham(Y)) & (np.abs(Z) <= 0.5)),
        ("hot", lambda X, Y, Z, dl, dr, t: (dr < ham(Y)) & (np.abs(Z) <= 0.5) & (Y < 37)),
    ])
    w.set_aura(["#3a0008", "#8a0a18", "#e01a2c", "#ff8a94"], "flame", size=0.7, focus=["horn", "hot"])
    return w


def sun_blade():
    """태양검: 계단식으로 솟은 빛나는 태양 핵을 검은 청동 테가 감싸고, 그 밖을 마디진 무지개 햇무리와 무지개 끝 빛살이 두른다.
    날은 밑동에서 빛살처럼 퍼진 뒤 잎사귀처럼 불룩해지고, 아래쪽 심지만 빛난다."""
    m = {
        "bronze": Mat(["#2a1606", "#3e220a", "#583210", "#74461a"], "metal", seed=211),
        "gold": Mat(["#8a5a10", "#b07818", "#d89a2a", "#f4c860"], "metal", seed=212),
        "edge": Mat(["#f0d070", "#f8e090", "#fff0c0", "#ffffff"], "flat", seed=218),
        "core": Mat(["#ff9a10", "#ffc830", "#fff080", "#ffffff"], "flow", glow=True, seed=213),
        "disc": Mat(["#ff7a00", "#ffa820", "#ffd050", "#fff4b0"], "pulse", glow=True, seed=214),
        "dome": Mat(["#fff0a0", "#fff8d0", "#ffffff", "#ffffff"], "flat", glow=True, seed=219),
        "prism": Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=216),
        "wrap": Mat(["#3a0a04", "#6a1a08", "#9a2a10", "#c84a1a"], "grip", seed=217),
    }
    w = Weapon(m, grip_y=9.5, kind="sword", seed=211)
    w.fill(lambda X, Y, Z: (np.abs(X) + np.abs(Y - 2.5) * 1.2 <= 2.8) & (np.abs(Z) <= 1.5), "gold")   # 별 폼멜
    w.cyl(4.5, 15, 1.6, "wrap")
    cy = 22.0
    # 날: 밑동에서 빛살처럼 퍼졌다 좁아지고, 잎사귀 배를 지나 2복셀 끝으로
    y0, y1 = cy, 71

    def hw(t):
        Y = y0 + t * (y1 - y0)
        flare = 2.4 * np.clip(1 - (Y - 30) / 7.0, 0, 1) * (Y >= 30)
        belly = 1.5 * np.sin(np.pi * np.clip((Y - 36) / 30.0, 0, 1))
        return 1.0 + (1.8 + belly) * taper(t, 0.8, 0.9) + flare
    sect(w, y0, y1, lambda t: -hw(t), hw, [
        ("edge", lambda X, Y, Z, dl, dr, t: np.abs(Z) <= 0.5),
        ("gold", lambda X, Y, Z, dl, dr, t: (np.minimum(dl, dr) >= 1) & (np.abs(Z) <= 1.5)),
        ("bronze", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 1) & (Y >= 41) & (t < 0.86) & (np.abs(Z) <= 1.5)),
        ("core", lambda X, Y, Z, dl, dr, t: (np.abs(X) < 1) & (Y < 41) & (np.abs(Z) <= 1.5)),
    ])
    d = lambda X, Y: np.hypot(X, Y - cy)
    w.prism(lambda X, Y: (d(X, Y) <= 8.4) & (d(X, Y) > 5.8), 1.0, "prism")       # 무지개 햇무리
    # 빛살 (위: 날, 아래: 손잡이 자리는 비운다). 햇무리를 가로질러 마디로 나누고, 긴 두 빛살 끝은 무지개
    for k in (0, 1, 3, 4):       # 옆으로 긴 빛살 둘 + 날 밑동을 받치는 위쪽 빛살 둘
        a = k * math.pi / 4
        ln = 17.5 if k % 2 == 0 else 13.5
        ca, sa = math.cos(a), math.sin(a)

        def ray(X, Y, ca=ca, sa=sa, ln=ln, lo=5.6):
            u = X * ca + (Y - cy) * sa
            v = -X * sa + (Y - cy) * ca
            return (u > lo) & (u < ln) & (np.abs(v) <= np.minimum(1.3, 2.8 * (ln - u) / (ln - 8.4)) + 0.3)
        w.prism(ray, 1.0, "bronze")
        if k in (0, 4):
            w.prism(lambda X, Y, ray=ray, ln=ln: ray(X, Y, lo=ln - 4.5), 1.0, "prism")
    # 계단식 태양 핵: 청동 테 → 빛나는 원반 → 솟은 돔 → 하얀 꼭지
    w.prism(lambda X, Y: d(X, Y) <= 5.8, 2.0, "bronze")
    w.prism(lambda X, Y: d(X, Y) <= 4.4, 2.5, "disc")
    w.prism(lambda X, Y: d(X, Y) <= 2.9, 3.0, "disc")
    w.prism(lambda X, Y: d(X, Y) <= 1.5, 3.5, "dome")
    w.set_aura(["#b02a00", "#ff7a10", "#ffd040", "#fffde0"], "flame", size=0.9, focus=["disc", "dome", "core"])
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
