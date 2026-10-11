"""
증강 스카이블럭 — 복셀 투구 세트 A (개척자 / 광부 / 서리 / 화염 / 공허).

네모네모 복셀 아트: 1 복셀 = 플레이어 스킨 1픽셀 크기의 정육면체. 투구 전체가 작은 큐브로 쌓여 있고
큐브마다 색이 조금씩 달라서(재료 무늬의 텍셀 1개 = 큐브 면 1개) 격자가 그대로 보인다.

좌표 (wkit.helmet): 원점 = 머리 가운데, 머리는 X,Y,Z 모두 -4..4, 얼굴은 -Z. 복셀 가운데는 ±0.5, ±1.5 ...
껍데기 한 겹은 |.| = 4.5 (머리 바로 바깥) 층이다. 착용자의 왼쪽 = -X.

게임 안 맞춤 (머리 아이템은 목을 축으로 머리와 함께 돈다):
  - 가슴/어깨 갑옷이 Y -6..-3, |X|<=9, |Z|<=3 을 채우므로 Y<-3 에서는 |X|<=4.5 안쪽만, 목 아래로는 거의 내려가지 않는다.
  - 턱 밑(머리 아래 Y<-4, |X|,|Z|<4)은 비워 둔다.

몸 갑옷(armor_a.py)과 같은 팔레트:
  pioneer  갈색 가죽 + 놋쇠 + 초록 스카프, 밝은 청록 고글 렌즈
  miner    회색 철판(세로 이음매 + 리벳) + 구리 테 + 밝은 램프 + 다이아 원석 무리
  frost    짙은 남색 받침 + 청록 결정 + 흰 끝, 빛나는 청록 보석
  flame    숯빛/검붉은 흑요석 + 주황 용암 틈 + 불꽃 볏, 검은→검붉은→달아오른 뿔
  void     보라 두건 + 자홍 룬 글자 가리개 + 떠 있는 룬 후광
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, PACK)
import wkit  # noqa: E402
from wkit import Mat  # noqa: E402

MODULE = "helmets_a"
PREVIEW_DIR = os.path.join(HERE, "preview")
SCRATCH = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
NAMES_KO = {"pioneer": "개척자", "miner": "광부", "frost": "서리", "flame": "화염", "void": "공허"}

A = np.abs


def head(X, Y, Z, m=4.0):
    """머리(8x8x8) 안쪽."""
    return (A(X) < m) & (A(Y) < m) & (A(Z) < m)


def rbox(X, Y, Z, rx, y0, y1, z0, z1, cham=1.0):
    """X 대칭 상자 (복셀 가운데 기준), 위쪽 모서리를 cham 만큼 계단식으로 깎는다."""
    inside = (A(X) <= rx) & (Y >= y0) & (Y <= y1) & (Z >= z0) & (Z <= z1)
    if cham > 0:
        inside &= (rx - A(X)) + (y1 - Y) >= cham
        inside &= (Z - z0) + (y1 - Y) >= cham
        inside &= (z1 - Z) + (y1 - Y) >= cham
    return inside


def ring(X, Z, r):
    """X-Z 평면에서 |X|<=r, |Z|<=r 인 네모 테두리 한 겹 (복셀 가운데 기준)."""
    return (np.maximum(A(X), A(Z)) <= r) & (np.maximum(A(X), A(Z)) > r - 1)


def sq(X, Z, rx, rz=None, p=4.0):
    """둥근 네모 (superellipse)."""
    rz = rx if rz is None else rz
    return (A(X) / rx) ** p + (A(Z) / rz) ** p <= 1.0


def tang(X, Z):
    """네모 테두리 위에서 테를 따라가는 좌표 (옆면은 Z, 앞뒤면은 X)."""
    return np.where(A(X) > A(Z), Z, X)


def put(h, x, y, z, mat):
    """설계 좌표 (x, y, z) 를 품은 복셀 하나."""
    i, j, k = int(math.floor(x + h.CX)), int(math.floor(y + h.CY)), int(math.floor(z + h.CZ))
    if 0 <= i < h.W and 0 <= j < h.H and 0 <= k < h.D:
        h.grid[i, j, k] = 0 if mat is None else h._id(mat)


def puts(h, cells, mat, mirror=False):
    for (x, y, z) in cells:
        put(h, x, y, z, mat)
        if mirror:
            put(h, -x, y, z, mat)


def at(h, x, y, z):
    i, j, k = int(math.floor(x + h.CX)), int(math.floor(y + h.CY)), int(math.floor(z + h.CZ))
    return h.grid[i, j, k]


def stair(pts):
    """(u, y) 점들을 면으로 이어지는 계단 칸 목록으로 (대각선 걸음은 옆으로 한 칸 → 위로 한 칸)."""
    out = [tuple(pts[0])]
    for (u0, y0), (u1, y1) in zip(pts[:-1], pts[1:]):
        u, y = u0, y0
        while (u, y) != (u1, y1):
            if u != u1:
                u += 1 if u1 > u else -1
            else:
                y += 1 if y1 > y else -1
            out.append((u, y))
    return out


# ═══════════════════════════════ 개척자 ═══════════════════════════════

def helm_pioneer():
    M = {
        "leather": Mat(["#4e2c12", "#6a3d1c", "#865026", "#a06434"], "stone", seed=101),
        "leather_d": Mat(["#2e180a", "#3e2210", "#4e2c16", "#5e361c"], "stone", seed=113),
        "leather_l": Mat(["#8a5628", "#a46c34", "#bc8442", "#d4a056"], "stone", seed=102),
        "fleece": Mat(["#b89c74", "#cdb48c", "#e0caa6", "#f0e2c4"], "cloth", seed=114),
        "strap": Mat(["#1e1008", "#2e1a0e", "#3e2414", "#4e301c"], "grip", seed=103),
        "stitch": Mat(["#d2b07a", "#e2c592", "#efd8ac", "#fbeccc"], "flat", seed=104),
        "brass": Mat(["#7a5214", "#a6741e", "#cc9a34", "#eec65a"], "metal", seed=105),
        "lens": Mat(["#6ae0e4", "#94ecee", "#c0f6f6", "#e8ffff"], "crystal", glow=True, seed=106),
        "lens_w": Mat(["#f6ffff", "#f8ffff", "#fcffff", "#ffffff"], "flat", glow=True, seed=115),
        "scarf": Mat(["#245a1e", "#307428", "#3e8e32", "#52a842"], "cloth", seed=107),
        "scarf_d": Mat(["#143a10", "#1c4c18", "#265e20", "#307028"], "cloth", seed=108),
        "feather": Mat(["#3a7e26", "#4a9630", "#5eae3c", "#7cc650"], "cloth", seed=109),
        "feather_d": Mat(["#28601c", "#327024", "#3e822c", "#4a9434"], "cloth", seed=112),
        "feather_t": Mat(["#a8d878", "#c0e48e", "#d6eea8", "#eef8d4"], "flat", seed=110),
        "quill": Mat(["#9cd070", "#a8d87c", "#b4e088", "#c0e894"], "flat", seed=116),
        "red": Mat(["#a01c12", "#c42a1a", "#e03c26", "#f45a3a"], "flat", seed=111),
    }
    h = wkit.helmet(M, seed=1)

    # 둥근 가죽 모자: 위로 갈수록 세 번 계단식으로 깎여 정수리가 둥글다
    def cap(X, Y, Z):
        R = np.select([Y <= 4.5, Y <= 5.5, Y <= 6.5], [4.5, 3.5, 2.5], -1)
        C = np.select([Y <= 3.5, Y <= 4.5, Y <= 5.5, Y <= 6.5], [8, 7, 6, 4], -1)
        return (np.maximum(A(X), A(Z)) <= R) & (A(X) + A(Z) <= C) & (Y >= 0.5)
    h.fill(cap, "leather")
    top = lambda X, Y, Z: cap(X, Y, Z) & ~cap(X, Y + 1, Z)
    # 뒤통수와 옆 (목 위까지)
    h.fill(lambda X, Y, Z: (Y >= -2.5) & (Y <= 0.5) & (((Z == 4.5) & (A(X) <= 3.5)) | ((A(X) == 4.5) & (Z >= -2.5) & (Z <= 3.5))), "leather")
    # 모자 아래 테 (밝은 가죽 한 줄) + 정수리 솔기 십자 (밝은 가죽 줄 + 실땀)
    h.fill(lambda X, Y, Z: cap(X, Y, Z) & (Y == 0.5), "leather_l")
    h.fill(lambda X, Y, Z: top(X, Y, Z) & ((A(X) == 0.5) | (A(Z) == 0.5)), "leather_l")
    h.fill(lambda X, Y, Z: top(X, Y, Z) & (((A(X) == 0.5) & (np.floor(Z) % 2 == 0)) | ((A(Z) == 0.5) & (np.floor(X) % 2 == 0) & (A(X) > 1))), "stitch")
    # 세로 솔기 (옆, 3칸마다 어두운 가죽)
    h.fill(lambda X, Y, Z: cap(X, Y, Z) & ~top(X, Y, Z) & (Y >= 1.5) & (A(tang(X, Z)) == 2.5) & (np.maximum(A(X), A(Z)) == 4.5), "leather_d")
    # 뒤 덧댄 조각 (실땀 테두리)
    h.fill(lambda X, Y, Z: (Z == 4.5) & (A(X) <= 2.5) & (Y >= -1.5) & (Y <= 1.5), "leather_l")
    h.fill(lambda X, Y, Z: (Z == 4.5) & (A(X) <= 1.5) & (Y >= -0.5) & (Y <= 0.5), "leather")
    # 귀덮개: 한 칸 밖으로, 모자 테 아래로 내려오고, 앞과 밑에 크림색 털
    flap = lambda X, Y, Z: (A(X) == 5.5) & (Y >= -2.5) & (Y <= 1.5) & (Z >= -2.5) & (Z <= 1.5)
    h.fill(flap, "leather")
    h.fill(lambda X, Y, Z: (A(X) == 4.5) & (Y >= -2.5) & (Y <= 0.5) & (Z >= -2.5) & (Z <= 1.5), "leather_d")
    h.fill(lambda X, Y, Z: flap(X, Y, Z) & ((Y == -2.5) | (Z == -2.5)), "fleece")
    h.fill(lambda X, Y, Z: (A(X) == 4.5) & (Y == -2.5) & (Z >= -2.5) & (Z <= 1.5), "fleece")
    h.fill(lambda X, Y, Z: (A(X) == 6.5) & (Y == -0.5) & (A(Z) <= 0.5), "brass")      # 단추
    # 고글 끈 (한 바퀴, 한 칸 밖)
    h.fill(lambda X, Y, Z: ring(X, Z, 5.5) & (Y >= 2.5) & (Y <= 3.5) & (Z > -5), "strap")
    h.fill(lambda X, Y, Z: (A(X) == 5.5) & (Y >= 2.5) & (Y <= 3.5) & (Z == -5.5), "strap")
    # 고글: 모서리 깎은 팔각 놋쇠 테 두 개 (두 칸 깊이) + 1칸 다리 + 안쪽에 밝은 렌즈와 흰 반짝임
    for s in (-1, 1):
        cx = 3.0 * s
        dx = lambda X, cx=cx: X - cx
        rim = lambda X, Y, Z, cx=cx: (A(X - cx) <= 1.5) & (A(Y - 3) <= 1.5) & ~((A(X - cx) == 1.5) & (A(Y - 3) == 1.5))
        lens = lambda X, Y, Z, cx=cx: (A(X - cx) <= 0.5) & (A(Y - 3) <= 0.5)
        h.fill(lambda X, Y, Z: rim(X, Y, Z) & ~lens(X, Y, Z) & (Z >= -6.5) & (Z <= -5.5), "brass")
        h.fill(lambda X, Y, Z: lens(X, Y, Z) & (Z == -5.5), "lens")
        put(h, cx + 0.5 * s, 3.5, -5.5, "lens_w")
    h.fill(lambda X, Y, Z: (A(X) == 0.5) & (Y == 3.5) & (Z == -5.5), "brass")          # 다리
    # 나침반 (착용자 왼쪽 끈): 놋쇠 팔각 + 크림 판 + 빨간 바늘
    h.fill(lambda X, Y, Z: (X == -6.5) & (A(Y - 3) <= 1.5) & (A(Z) <= 1.5) & ~((A(Y - 3) == 1.5) & (A(Z) == 1.5)), "brass")
    h.fill(lambda X, Y, Z: (X == -6.5) & (A(Y - 3) <= 0.5) & (A(Z) <= 0.5), "stitch")
    put(h, -6.5, 3.5, -0.5, "red")
    put(h, -7.5, 3.0, 0.0, "brass")                                                           # 꼭지
    # 깃털 (착용자 오른쪽 끈에 꽂음): 1칸 두께의 납작한 깃, 밝은 깃대 줄, 계단 모양 깃가지 홈
    fz = 2.5
    puts(h, [(6.5, 2.5, fz), (6.5, 3.5, fz)], "quill")
    shape = [(0, 0), (-1, 1), (-1, 1), (-1, 2), (0, 2), (-1, 1), (-1, 0), (0, 1), (0, 0)]
    for i, (l, r) in enumerate(shape):
        y = 4.5 + i
        q = 6.5 + (1 if i >= 3 else 0) + (1 if i >= 6 else 0)
        for dx in range(l, r + 1):
            if i == len(shape) - 1:
                m = "feather_t"
            elif dx == 0:
                m = "quill"
            else:
                m = "feather_d" if dx < 0 else "feather"
            put(h, q + dx, y, fz, m)
    # 초록 스카프: 목둘레 한 줄(3칸마다 주름) + 뒤 매듭 + 짧은 두 가닥 (목에 붙임)
    h.fill(lambda X, Y, Z: ring(X, Z, 4.5) & (Y == -3.5), "scarf")
    h.fill(lambda X, Y, Z: ring(X, Z, 4.5) & (Y == -3.5) & (np.floor(tang(X, Z) + 0.5) % 3 == 0), "scarf_d")
    h.fill(lambda X, Y, Z: (X >= -3.5) & (X <= -1.5) & (Y >= -3.5) & (Y <= -2.5) & (Z == 5.5), "scarf")
    put(h, -2.5, -3.0, 5.5, "scarf_d")
    puts(h, [(-3.5, -4.5, 4.5), (-3.5, -5.5, 4.5)], "scarf_d")
    puts(h, [(-1.5, -4.5, 4.5)], "scarf")
    h.clear(lambda X, Y, Z: head(X, Y, Z))
    return h


# ═══════════════════════════════ 광부 ═══════════════════════════════

def helm_miner():
    M = {
        "iron": Mat(["#565c64", "#6c727b", "#848a93", "#9ea4ac"], "cloth", seed=201),
        "iron_l": Mat(["#6c727b", "#848a93", "#9da3ab", "#b6bbc2"], "cloth", seed=212),
        "seam": Mat(["#363a40", "#3e434a", "#474c53", "#50555d"], "flat", seed=202),
        "rivet": Mat(["#a4aab2", "#b0b6bd", "#bcc1c7", "#c8ccd2"], "flat", seed=203),
        "copper": Mat(["#7a3c1a", "#a45426", "#c87034", "#e6904c"], "metal", seed=204),
        "copper_d": Mat(["#40200e", "#562c14", "#6c381a", "#844620"], "stone", seed=205),
        "verdigris": Mat(["#2a7a6a", "#3a9a84", "#56b89c", "#7ad4b4"], "stone", seed=206),
        "lamp": Mat(["#e88010", "#ffa020", "#ffc448", "#ffe48a"], "pulse", glow=True, seed=207),
        "lamp_c": Mat(["#fff2c4", "#fff8dc", "#fffcee", "#ffffff"], "flat", glow=True, seed=208),
        "dia": Mat(["#28b4e0", "#4ccaee", "#7ee0f8", "#b4f2ff"], "crystal", seed=209),
        "dia_d": Mat(["#0c4e7c", "#126492", "#1a7aa8", "#2490bc"], "crystal", seed=213),
        "dia_t": Mat(["#d4faff", "#e4fcff", "#f2feff", "#ffffff"], "flat", seed=214),
        "batt": Mat(["#18191d", "#24262b", "#30333a", "#3e4149"], "stone", seed=210),
        "led": Mat(["#20a040", "#40d866", "#90f8a6", "#e8ffee"], "flat", glow=True, seed=211),
    }
    h = wkit.helmet(M, seed=2)

    def dome(X, Y, Z, grow=0.0):
        r = np.select([Y <= 2.5, Y <= 3.5, Y <= 4.5, Y <= 5.5, Y <= 6.5, Y <= 7.5],
                      [5.7, 5.6, 5.15, 4.45, 3.45, 2.1], 0.01) + grow
        return sq(X, Z, r, p=2.4) & (Y >= 1.5) & (Y <= 7.5)
    h.fill(dome, "iron")
    surf = lambda X, Y, Z: dome(X, Y, Z) & ~dome(X, Y, Z, -1.0)
    h.fill(lambda X, Y, Z: dome(X, Y, Z) & (Y >= 6.5), "iron_l")
    # 세로 판 이음매 (3칸마다, 어두운 줄) + 이음매 위 리벳
    seam = lambda X, Y, Z: surf(X, Y, Z) & np.isin(A(tang(X, Z)), (1.5, 4.5)) & (Y <= 5.5)
    h.fill(seam, "seam")
    h.fill(lambda X, Y, Z: seam(X, Y, Z) & (Y == 2.5), "rivet")
    h.fill(lambda X, Y, Z: dome(X, Y, Z) & (Y == 1.5), "seam")                    # 아래 이음 띠
    # 구리 볏 (앞에서 뒤로, 한 칸 솟음) + 녹청 얼룩
    crest = lambda X, Y, Z: dome(X, Y - 1, Z) & ~dome(X, Y, Z) & (A(X) == 0.5) & (Y >= 4.5)
    h.fill(crest, "copper")
    h.fill(lambda X, Y, Z: crest(X, Y, Z) & (np.floor(Z) % 4 == 1), "verdigris")
    # 구리 챙 (앞뒤로 길쭉한 둥근 판) + 어두운 가장자리
    brim = lambda X, Y, Z, s=1.0: (Y == 0.5) & sq(X, Z, 6.6 * s, 7.6 * s, p=2.6)
    h.fill(brim, "copper")
    h.fill(lambda X, Y, Z: brim(X, Y, Z) & ~brim(X, Y, Z, 0.86), "copper_d")
    # 뒤 목가리개 (챙 아래로)
    h.fill(lambda X, Y, Z: (A(X) <= 3.5) & (Y >= -2.5) & (Y <= -0.5) & (Z == 4.5), "iron")
    h.fill(lambda X, Y, Z: (A(X) <= 3.5) & (Y == -2.5) & (Z == 4.5), "seam")
    h.fill(lambda X, Y, Z: (A(X) == 2.5) & (Y == -1.5) & (Z == 4.5), "rivet")
    # 램프: 어두운 구리 함 → 한 칸 솟은 구리 고리(모서리 깎음) → 안쪽 4x4 렌즈(모서리 깎음)
    #       렌즈 가장자리 = 숨쉬는 호박색(pulse, 맨 바깥 층), 가운데 2x2 = 거의 흰 빛
    LY = 3.0
    oct6 = lambda X, Y: (A(X) <= 2.5) & (A(Y - LY) <= 2.5) & ~((A(X) == 2.5) & (A(Y - LY) == 2.5))
    oct4 = lambda X, Y: (A(X) <= 1.5) & (A(Y - LY) <= 1.5) & ~((A(X) == 1.5) & (A(Y - LY) == 1.5))
    h.fill(lambda X, Y, Z: oct6(X, Y) & (Z >= -6.5) & (Z <= -3.5) & ~dome(X, Y, Z) & (Y >= 1.5), "copper_d")
    h.fill(lambda X, Y, Z: oct6(X, Y) & ~oct4(X, Y) & (Z == -7.5), "copper")
    h.fill(lambda X, Y, Z: oct4(X, Y) & (Z == -6.5), "lamp")
    h.fill(lambda X, Y, Z: (A(X) <= 0.5) & (A(Y - LY) <= 0.5) & (Z == -6.5), "lamp_c")
    h.fill(lambda X, Y, Z: (A(X) == 3.5) & (A(Y - LY) <= 0.5) & (Z == -6.5), "seam")     # 고정쇠
    # 뒤 전지함 + 초록 표시등 + 전선
    h.fill(lambda X, Y, Z: (A(X) <= 1.5) & (Y >= 1.5) & (Y <= 3.5) & (Z == 6.5), "batt")
    h.fill(lambda X, Y, Z: (A(X) <= 1.5) & (Y == 4.5) & (Z == 6.5), "copper_d")
    put(h, 0.5, 2.5, 7.5, "led")
    put(h, -0.5, 2.5, 7.5, "seam")
    # 다이아 원석 무리 (정수리 오른쪽 뒤): 2x2 짙은 뿌리 → 밝은 몸 → 흰 끝, 큰/중간/작은 세 개
    crystals = [
        # (뿌리 x0, z0, 뿌리 y, 몸 칸 [(x, z, 높이 수)], 끝 (x, z))
        ((3.5, 1.5), 5.5, [(4.5, 2.5, 2)], (4.5, 2.5), "big"),
        ((1.5, 3.5), 6.5, [(1.5, 4.5, 1)], (1.5, 4.5), "mid"),
        ((4.5, -0.5), 4.5, [(5.5, -0.5, 1)], (5.5, -0.5), "small"),
    ]
    for (x0, z0), y0, body, tip, kind in crystals:
        for ox in (0, 1):
            for oz in (0, 1):
                put(h, x0 + ox, y0, z0 + oz, "dia_d")
        y = y0 + 1
        if kind == "big":
            for ox in (0, 1):
                for oz in (0, 1):
                    put(h, x0 + ox, y, z0 + oz, "dia")
            y += 1
        for (bx, bz, n) in body:
            for i in range(n):
                put(h, bx, y + i, bz, "dia")
            y += n
        put(h, tip[0], y, tip[1], "dia_t")
    h.clear(lambda X, Y, Z: head(X, Y, Z))
    return h


# ═══════════════════════════════ 서리 ═══════════════════════════════

def helm_frost():
    M = {
        "ice": Mat(["#1c5ea8", "#2874c0", "#3a8cd6", "#52a6ea"], "stone", seed=301),
        "ice_d": Mat(["#0c2a5c", "#123874", "#1a488c", "#2458a2"], "crystal", seed=302),
        "cryst": Mat(["#12a0dc", "#32bcee", "#5cd6fa", "#94ecff"], "crystal", seed=305),
        "cryst_d": Mat(["#0a4a8a", "#0e5ea2", "#1474b8", "#1e8acc"], "crystal", seed=309),
        "silver": Mat(["#8ea6c0", "#a8bed4", "#c4d6e6", "#e2eef8"], "metal", seed=304),
        "stud": Mat(["#e8f6ff", "#f2faff", "#f8fdff", "#ffffff"], "flat", seed=303),
        "gem": Mat(["#00a4ea", "#30d8ff", "#a0f6ff", "#ffffff"], "sparkle", glow=True, seed=306),
        "tip": Mat(["#c8f4ff", "#e0faff", "#f2fdff", "#ffffff"], "sparkle", glow=True, seed=307),
        "core": Mat(["#2cb8f0", "#5cd4ff", "#a0ecff", "#e6fcff"], "pulse", glow=True, seed=308),
    }
    h = wkit.helmet(M, seed=3)
    # 반투구: 정수리와 옆, 뒤만 (낮은 서클릿 + 결정)
    shell = lambda X, Y, Z: rbox(X, Y, Z, 4.5, -2.5, 5.5, -4.5, 4.5, cham=2.0)
    h.fill(shell, "ice")
    h.clear(lambda X, Y, Z: (Z < -2) & (Y <= 0.5) & (A(X) <= 3.5))          # 얼굴은 이마 아래로 열림
    h.clear(lambda X, Y, Z: (Z < 1) & (Y <= -1.5))                           # 볼은 짧게
    h.fill(lambda X, Y, Z: shell(X, Y, Z) & (A(X) == 4.5) & (Y <= 0.5) & (Z < 1), "ice_d")   # 볼가리개
    h.fill(lambda X, Y, Z: shell(X, Y, Z) & (Y >= 4.5) & ((A(X) == 0.5) | (A(Z) == 0.5)) & ~shell(X, Y + 1, Z), "ice_d")  # 정수리 십자 결
    # 서클릿: 짙은 남색 띠 + 깨끗한 은줄 한 줄 (3칸마다 흰 징)
    h.fill(lambda X, Y, Z: ring(X, Z, 5.5) & (Y == 1.5), "ice_d")
    h.fill(lambda X, Y, Z: ring(X, Z, 5.5) & (Y == 2.5), "silver")
    h.fill(lambda X, Y, Z: ring(X, Z, 5.5) & (Y == 2.5) & np.isin(A(tang(X, Z)), (1.5, 4.5)), "stud")
    # 이마 보석: 은 마름모 테 + 2x2 보석 (앞으로 두 칸)
    h.fill(lambda X, Y, Z: (A(X) + A(Y - 2) <= 2.6) & (Z == -6.5), "silver")
    h.fill(lambda X, Y, Z: (A(X) <= 0.5) & (A(Y - 2) <= 0.5) & (Z >= -7.5) & (Z <= -6.5), "gem")

    # 결정: 2x2 짙은 뿌리 → 청록 몸 → 흰 끝. 칸은 모두 정수 칸이고 위아래가 면으로 붙는다.
    def crystal(cells, mirror=True):
        for (x, y, z, m) in cells:
            put(h, x, y, z, m)
            if mirror:
                put(h, -x, y, z, m)
    # 가운데 큰 결정 (이마 위, 4칸 폭 뿌리 → 2x2 몸 → 2x1 끝), 앞면에 빛나는 심
    big = []
    for y in (3.5, 4.5):
        big += [(x, y, z, "cryst_d") for x in (0.5, 1.5) for z in (-5.5, -4.5)]
    for y in (5.5, 6.5, 7.5):
        big += [(0.5, y, z, "cryst") for z in (-5.5, -4.5)]
    big += [(0.5, 8.5, -5.5, "cryst"), (0.5, 9.5, -5.5, "tip")]
    big += [(0.5, y, -5.5, "core") for y in (5.5, 6.5, 7.5)]
    big += [(1.5, 5.5, -5.5, "cryst")]
    crystal(big)
    # 앞 양옆 중간 결정 (바깥으로 한 칸 기울어짐)
    crystal([(x, 3.5, z, "cryst_d") for x in (3.5, 4.5) for z in (-5.5, -4.5)]
            + [(x, 4.5, z, "cryst") for x in (3.5, 4.5) for z in (-5.5, -4.5)]
            + [(4.5, 5.5, -5.5, "cryst"), (5.5, 5.5, -5.5, "cryst"), (5.5, 6.5, -5.5, "cryst"), (5.5, 7.5, -5.5, "tip")])
    # 옆 작은-중간 결정
    crystal([(x, 3.5, z, "cryst_d") for x in (4.5, 5.5) for z in (-1.5, -0.5)]
            + [(5.5, 4.5, -1.5, "cryst"), (5.5, 4.5, -0.5, "cryst"), (5.5, 5.5, -0.5, "cryst"),
               (6.5, 5.5, -0.5, "cryst"), (6.5, 6.5, -0.5, "tip")])
    # 뒤 작은 결정
    crystal([(x, 3.5, z, "cryst_d") for x in (2.5, 3.5) for z in (4.5, 5.5)]
            + [(3.5, 4.5, 5.5, "cryst"), (3.5, 5.5, 5.5, "tip")])
    # 고드름: 띠 아래로 매달림 (위 칸은 두 칸 폭, 끝은 흰색)
    icicles = [(5.5, -3.5, 2), (5.5, -1.5, 4), (5.5, 1.5, 3), (5.5, 4.5, 2), (3.5, 5.5, 4), (0.5, 5.5, 3)]
    for (ix, iz, ln) in icicles:
        for sgn in (1, -1):
            x = ix * sgn
            # 위 칸은 띠를 따라 두 칸 폭
            wide = (x, iz + (1 if iz < 0 else -1)) if abs(ix) == 5.5 else (x - sgn, iz)
            put(h, wide[0], 0.5, wide[1], "cryst_d")
            for i in range(ln):
                put(h, x, 0.5 - i, iz, "tip" if i == ln - 1 else "cryst")
    h.clear(lambda X, Y, Z: head(X, Y, Z))
    return h


# ═══════════════════════════════ 화염 ═══════════════════════════════

def helm_flame():
    M = {
        "obsid": Mat(["#24161a", "#3a2428", "#523438", "#6c4448"], "stone", seed=401),
        "obsid_d": Mat(["#0e0808", "#160c0c", "#1e1212", "#281818"], "flat", seed=411),
        "face": Mat(["#2e2222", "#433030", "#5a4040", "#725250"], "crystal", seed=402),
        "iron": Mat(["#34302e", "#48423e", "#5e5650", "#766c64"], "metal", seed=403),
        "horn": Mat(["#241c20", "#362a2e", "#4a3a3e", "#604c50"], "stone", seed=404),
        "horn_r": Mat(["#4a1410", "#661c14", "#84281a", "#a03420"], "stone", seed=405),
        "tip": Mat(["#ff7a18", "#ffa834", "#ffd060", "#fff4c0"], "flat", glow=True, seed=409),
        "hot": Mat(["#ffb030", "#ffcc50", "#ffe488", "#fff6c8"], "flat", glow=True, seed=412),
        "magma": Mat(["#8a2008", "#a82e0c", "#c64212", "#e05a1a"], "stone", glow=True, seed=410),
        "lava": Mat(["#d04408", "#ff6a10", "#ffa030", "#ffe080"], "pulse", glow=True, seed=406),
        "ember": Mat(["#ff4a08", "#ff8a1c", "#ffc448", "#fff4b0"], "fire", glow=True, seed=407),
        "eye": Mat(["#ff9a18", "#ffc038", "#ffe47a", "#ffffe8"], "flow", glow=True, seed=408),
    }
    h = wkit.helmet(M, seed=4)
    shell = lambda X, Y, Z: rbox(X, Y, Z, 4.5, -3.5, 5.5, -4.5, 4.5, cham=1.5)
    h.fill(shell, "obsid")
    # 판 이음매: 가로 한 줄 (Y 2.5) + 옆/뒤 세로 판 가장자리 (3칸마다)
    outer = lambda X, Y, Z: shell(X, Y, Z) & ((A(X) == 4.5) | (A(Z) == 4.5))
    h.fill(lambda X, Y, Z: outer(X, Y, Z) & (Y == 2.5), "obsid_d")
    h.fill(lambda X, Y, Z: outer(X, Y, Z) & np.isin(A(tang(X, Z)), (1.5,)) & (Y <= 1.5) & (Z > -4), "obsid_d")
    # 아래 쇠 테 (껍데기와 같은 면, Y -3.5)
    h.fill(lambda X, Y, Z: ring(X, Z, 4.5) & (Y == -3.5), "iron")
    # 얼굴 판 (앞으로 한 겹, 숯빛) + 이마 돌기 + T 자 눈 틈
    slit = lambda X, Y, Z: ((A(X) <= 3.5) & (Y == 0.5)) | ((A(X) <= 0.5) & (Y <= 0.5) & (Y >= -2.5))
    h.fill(lambda X, Y, Z: (A(X) <= 3.5) & (Y >= -3.5) & (Y <= 3.5) & (Z == -5.5), "face")
    h.fill(lambda X, Y, Z: (A(X) <= 3.5) & (Y == 1.5) & (Z == -6.5), "face")
    h.fill(lambda X, Y, Z: (A(X) <= 0.5) & (Y >= 1.5) & (Y <= 4.5) & (Z == -6.5), "face")
    h.fill(lambda X, Y, Z: (A(X) <= 3.5) & (Y == -3.5) & (Z == -5.5), "iron")
    h.clear(lambda X, Y, Z: slit(X, Y, Z) & (Z == -5.5))
    h.fill(lambda X, Y, Z: slit(X, Y, Z) & (Z == -4.5), "eye")
    # 턱 아래 송곳 (계단)
    h.fill(lambda X, Y, Z: (A(X) <= 1.5) & (Y == -4.5) & (Z == -5.5), "face")
    h.fill(lambda X, Y, Z: (A(X) <= 0.5) & (Y == -5.5) & (Z == -5.5), "face")

    # 용암 틈: 아래 테에서 위로 갈라지는 계단 대각선. 아래쪽은 넓고 밝고(hot), 위로 갈수록 가늘고 어둡다(magma).
    def surface_put(side, u, y, mat):
        """side: +1/-1 = 오른쪽/왼쪽 옆면 (u = Z), 0 = 뒷면 (u = X). 껍데기 바깥 칸에 칠한다."""
        if side == 0:
            for z in (4.5, 3.5, 2.5):
                if at(h, u, y, z) and shell(np.float64(u), np.float64(y), np.float64(z)):
                    put(h, u, y, z, mat)
                    return
        else:
            for x in (4.5, 3.5, 2.5):
                if at(h, x * side, y, u) and shell(np.float64(x * side), np.float64(y), np.float64(u)):
                    put(h, x * side, y, u, mat)
                    return

    def crack(side, pts, branch=None):
        cells = stair(pts)
        for (u, y) in cells:
            m = "hot" if y <= -2.5 else ("lava" if y <= 1.5 else "magma")
            surface_put(side, u, y, m)
        u0, y0 = pts[0]
        for du in (-1, 1):                       # 밑동은 넓게
            surface_put(side, u0 + du, y0, "hot")
        if branch:
            for (u, y) in stair(branch):
                surface_put(side, u, y, "magma")
    # 오른쪽 옆: 뒤 아래에서 앞 위로 → 눈 틈 끝(앞 모서리)에 이어진다
    crack(1, [(2.5, -2.5), (1.5, -1.5), (0.5, -1.5), (-0.5, -0.5), (-2.5, 0.5), (-3.5, 0.5)],
          branch=[(0.5, -1.5), (1.5, 0.5), (2.5, 1.5)])
    put(h, 4.5, 0.5, -4.5, "lava")
    # 왼쪽 옆: 다른 모양
    crack(-1, [(1.5, -2.5), (0.5, -1.5), (-1.5, -0.5), (-2.5, 0.5), (-3.5, 0.5)],
          branch=[(-1.5, -0.5), (-1.5, 1.5), (-0.5, 2.5)])
    put(h, -4.5, 0.5, -4.5, "lava")
    # 뒤: 아래에서 정수리까지 → 볏의 용암 줄과 만난다
    crack(0, [(-0.5, -2.5), (0.5, -1.5), (0.5, -0.5), (-0.5, 0.5), (-0.5, 1.5), (0.5, 2.5), (0.5, 3.5)],
          branch=[(0.5, -0.5), (2.5, 0.5), (2.5, 1.5)])
    h.fill(lambda X, Y, Z: (X == 0.5) & (Y >= 4.5) & (Y <= 5.5) & (Z >= 3.5) & (Z <= 4.5) & shell(X, Y, Z), "magma")
    # 뿔: 관자놀이 높이(Y 3.5~4.5)에서 바깥-위로 한 번에 휘어 안쪽으로 감긴다.
    #     검은 흑요석 → 검붉은 → 달아오른 끝. 끝은 한 칸.
    horn = []
    rows = {4.5: (4.5, 5.5), 5.5: (4.5, 6.5), 6.5: (5.5, 6.5), 7.5: (6.5, 7.5)}
    for y, (x0, x1) in rows.items():
        horn += [(x, y, z, "horn") for x in np.arange(x0, x1 + 0.1) for z in (-0.5, 0.5)]
    horn = [(x, y, z, "horn_r") if y == 7.5 and x == 7.5 else (x, y, z, m) for (x, y, z, m) in horn]
    horn += [(7.5, 8.5, -0.5, "horn_r"), (7.5, 8.5, 0.5, "horn_r"), (7.5, 9.5, -0.5, "magma"), (7.5, 10.5, -0.5, "tip")]
    puts_m = lambda cells: [put(h, s * x, y, z, m) for (x, y, z, m) in cells for s in (1, -1)]
    puts_m(horn)
    # 불꽃 볏: 숯빛 받침 + 용암 줄 + 일렁이는 불길 (모든 칸이 면으로 붙음)
    h.fill(lambda X, Y, Z: (A(X) <= 1.5) & (Y == 6.5) & (A(Z) <= 3.5), "face")
    h.fill(lambda X, Y, Z: (A(X) <= 0.5) & (Y == 6.5) & (A(Z) <= 3.5), "lava")
    prof = {-3.5: 1, -2.5: 3, -1.5: 2, -0.5: 4, 0.5: 3, 1.5: 4, 2.5: 2, 3.5: 1}
    for z, hgt in prof.items():
        top_x = 0.5 if (int(z + 10)) % 2 else -0.5
        for i in range(hgt):
            y = 7.5 + i
            if i < hgt - 2 or hgt <= 2 and i == 0:
                put(h, -0.5, y, z, "ember")
                put(h, 0.5, y, z, "ember")
            else:
                put(h, top_x, y, z, "ember")
            if i == 0 and hgt >= 3:
                put(h, -1.5, y, z, "ember")
                put(h, 1.5, y, z, "ember")
    h.clear(lambda X, Y, Z: head(X, Y, Z))
    return h


# ═══════════════════════════════ 공허 ═══════════════════════════════

def helm_void():
    M = {
        "cloth": Mat(["#2a1546", "#3c2062", "#52307e", "#6a42a0"], "stone", seed=501),
        "cloth_d": Mat(["#1c0c30", "#281444", "#341c56", "#42246a"], "stone", seed=502),
        "cloth_l": Mat(["#4a2a74", "#5e3890", "#7448aa", "#8c5cc4"], "cloth", seed=510),
        "trim": Mat(["#7a46aa", "#9460c6", "#ae7ede", "#ca9cf2"], "metal", seed=503),
        "mask": Mat(["#1e1230", "#2a1a40", "#382452", "#463064"], "stone", seed=504),
        "rune": Mat(["#c02aa0", "#ff4cd0", "#ff9ae8", "#ffe0fa"], "flow", glow=True, seed=506),
        "gem": Mat(["#a01a8a", "#e040c0", "#ff90e8", "#ffffff"], "sparkle", glow=True, seed=507),
        "ring": Mat(["#3e1c60", "#56287e", "#70389c", "#8c4cba"], "crystal", seed=508),
        "pink": Mat(["#e070cc", "#f090dc", "#f8b4ea", "#fde0f8"], "flat", glow=True, seed=509),
        "glyph": Mat(["#d04aac", "#d856b4", "#e062bc", "#e86ec4"], "flat", glow=True, seed=511),
    }
    h = wkit.helmet(M, seed=5)

    # 두건: 머리를 1~2칸 두께로 감싸는 속 빈 껍데기, |X|<=5.5, 목 아래로 거의 안 내려감.
    #       앞 가장자리는 이마 위에서 앞으로 나왔다가(챙) 아래로 갈수록 들어간다(고깔 곡선).
    def zf(Y):   # 앞 가장자리
        return np.select([Y >= 6.5, Y >= 5.5, Y >= 2.5, Y >= -0.5], [-3.5, -5.5, -6.5, -5.5], -4.5)

    def rx(Y):
        return np.select([Y >= 6.5, Y >= 5.5, Y >= 0.5], [3.5, 4.5, 5.5], 4.5)

    def zb(Y):
        return np.select([Y >= 6.5, Y >= 5.5], [2.5, 4.5], 5.5)

    def ymin(X, Z):  # 밑단: 앞은 높고 뒤로 갈수록 내려간다 (옆에서 보면 비스듬한 단)
        y = np.select([Z <= -3.5, Z <= 0.5], [-1.5, -2.5], -3.5)
        return np.where((Z >= 4.5) & (A(X) <= 2.5), -4.5, y)

    def hood(X, Y, Z):
        R, F, B = rx(Y), zf(Y), zb(Y)
        body = (A(X) <= R) & (Z >= F) & (Z <= B) & (Y <= 6.5) & (Y >= ymin(X, Z))
        body &= (R - A(X)) + (B - Z) >= 2.0            # 뒤 모서리 둥글게
        body &= (R - A(X)) + (Z - F) >= 1.0
        return body
    h.fill(hood, "cloth")
    surf = lambda X, Y, Z: hood(X, Y, Z) & ~(hood(X + 1, Y, Z) & hood(X - 1, Y, Z) & hood(X, Y, Z + 1) & hood(X, Y + 1, Z))
    # 주름: 옆면 세로 골(짙음) + 그 옆 밝은 마루, 뒷면도 3칸마다
    side = lambda X, Y, Z: surf(X, Y, Z) & (A(X) >= 4.5) & (Y <= 2.5)
    h.fill(lambda X, Y, Z: side(X, Y, Z) & np.isin(Z, (-2.5, 1.5)), "cloth_d")
    back = lambda X, Y, Z: surf(X, Y, Z) & (Z >= 4.5) & (Y <= 2.5)
    h.fill(lambda X, Y, Z: back(X, Y, Z) & (A(X) == 2.5), "cloth_d")
    h.fill(lambda X, Y, Z: back(X, Y, Z) & (A(X) == 1.5), "cloth_l")
    # 밑단 테 (밝은 보라)
    h.fill(lambda X, Y, Z: hood(X, Y, Z) & ~hood(X, Y - 1, Z) & (Y < 0), "trim")
    # 룬 띠 (몸 갑옷처럼): 밝은 테 한 줄 + 자홍 점 (Y 0.5)
    band = lambda X, Y, Z: surf(X, Y, Z) & (Y == 0.5) & ((A(X) >= 5.5) | (Z >= 5.5))
    h.fill(band, "trim")
    h.fill(lambda X, Y, Z: band(X, Y, Z) & (np.floor(tang(X, Z) + 0.5) % 4 == 0), "rune")
    # 처진 뾰족 끝: 4x4 → 2x4 → 2x3 → 뒤로 꺾여 2칸 → 1칸 + 보석
    tip = []
    tip += [(x, 7.5, z) for x in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5) for z in (-1.5, -0.5, 0.5, 1.5)
            if not (abs(x) == 2.5 and z in (-1.5, 1.5))]
    tip += [(x, 8.5, z) for x in (-1.5, -0.5, 0.5, 1.5) for z in (-0.5, 0.5, 1.5, 2.5) if not (abs(x) == 1.5 and z == -0.5)]
    tip += [(x, 9.5, z) for x in (-0.5, 0.5) for z in (1.5, 2.5, 3.5)]
    tip += [(x, 10.5, z) for x in (-0.5, 0.5) for z in (3.5, 4.5)]
    tip += [(x, 9.5, z) for x in (-0.5, 0.5) for z in (4.5, 5.5)]
    tip += [(0.5, 8.5, 5.5), (0.5, 8.5, 6.5), (0.5, 7.5, 6.5)]
    puts(h, tip, "cloth")
    puts(h, [(x, 7.5, 1.5) for x in (-1.5, 1.5)] + [(x, 8.5, 2.5) for x in (-1.5, 1.5)], "cloth_d")
    puts(h, [(x, 9.5, 1.5) for x in (-0.5, 0.5)] + [(-0.5, 10.5, 3.5)], "cloth_l")
    put(h, 0.5, 6.5, 6.5, "gem")
    # 얼굴 구멍: 뾰족 아치. 이마 쪽은 짙은 그림자.
    arch = lambda X, Y, Z: (Y <= 3.5) & (Y >= -5.5) & (A(X) <= 3.5 - np.maximum(0, Y - 1.5))
    h.clear(lambda X, Y, Z: arch(X, Y, Z) & (Z <= -4))
    h.fill(lambda X, Y, Z: arch(X, Y, Z) & (Z == -4.5) & (Y >= 1.5), "cloth_d")
    # 아치 테 (맨 앞 가장자리, 밝은 보라) + 꼭대기 보석
    edge = lambda X, Y, Z: (arch(X - 1, Y, Z) | arch(X + 1, Y, Z) | arch(X, Y - 1, Z)) & ~arch(X, Y, Z)
    h.fill(lambda X, Y, Z: hood(X, Y, Z) & edge(X, Y, Z) & (Z == zf(Y)), "trim")
    puts(h, [(-0.5, 5.5, -5.5), (0.5, 5.5, -5.5)], "gem")
    # 아래 얼굴 가리개: 몸 갑옷의 가로 룬 글자 (X · H)
    h.fill(lambda X, Y, Z: (A(X) <= 3.5) & (Y <= -1.5) & (Y >= -3.5) & (Z == -4.5), "mask")
    glyph = ["x.x..x.x",
             ".x...xxx",
             "x.x..x.x"]
    for r, row in enumerate(glyph):
        for c, ch in enumerate(row):
            if ch == "x":
                put(h, -3.5 + c, -1.5 - r, -4.5, "glyph")
    h.fill(lambda X, Y, Z: (A(X) <= 3.5) & (Y == -0.5) & (Z == -4.5) & (A(X) >= 3.5), "trim")
    # 떠 있는 룬 후광 (머리 뒤, 2칸 두께 고리, 아래는 열림) + 안쪽 분홍 호 (3~4칸씩 이어짐)
    cy, cz, R = 3.0, 9.0, 8.0
    ang = lambda X, Y: (np.arctan2(Y - cy, X) / (2 * np.pi)) % 1.0
    open_bottom = lambda X, Y: (Y - cy) > -R * 0.62
    ringm = lambda X, Y, Z: (A(np.hypot(X, Y - cy) - R) < 0.72) & (A(Z - cz) <= 0.5) & open_bottom(X, Y)
    h.fill(ringm, "ring")
    h.fill(lambda X, Y, Z: ringm(X, Y, Z) & (np.floor(ang(X, Y) * 24) % 3 == 1), "rune")
    h.clear(lambda X, Y, Z: ringm(X, Y, Z) & np.isin(np.floor(ang(X, Y) * 48), (9, 15, 32, 38)))
    ring2 = lambda X, Y, Z: (A(np.hypot(X, Y - cy) - (R - 1.7)) < 0.62) & (Z == cz - 0.5) & (Y > cy - 0.5)
    h.fill(lambda X, Y, Z: ring2(X, Y, Z) & (np.floor(ang(X, Y) * 20) % 3 != 0), "pink")
    # 고리 위 보석 (십자 모양, 앞으로 한 칸)
    for a in (90, 30, 150):
        gx, gy = R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a))
        gx, gy = math.floor(gx) + 0.5, math.floor(gy) + 0.5
        for (ox, oy) in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            put(h, gx + ox, gy + oy, cz - 0.5, "gem")
            put(h, gx + ox, gy + oy, cz + 0.5, "gem")
        put(h, gx, gy, cz - 1.5, "gem")
    h.clear(lambda X, Y, Z: head(X, Y, Z))
    return h


HELMETS = {"pioneer": helm_pioneer, "miner": helm_miner, "frost": helm_frost, "flame": helm_flame, "void": helm_void}


# ─────────────────────────── 미리보기 ───────────────────────────
# 복셀 격자를 그대로 그리는 미리보기 (면 하나 = 큐브 한 면, 텍셀 한 개 = 그 면의 색, 가까운 면이 나중에 그려짐).
# 마네킹 머리(스킨 8x8x8, 얼굴 -Z 에 눈)와 함께, 게임처럼 얼굴 쪽에서 본 모습이 왼쪽/오른쪽이 맞게 나온다.
# night=True 면 조명을 받는 면은 어둡게, 스스로 빛나는(glow) 재료만 그대로 밝게.

_FACE_DIRS = {  # 이름: (법선, 밝기)
    "up": ((0, 1, 0), 1.0), "down": ((0, -1, 0), 0.5), "north": ((0, 0, -1), 0.8),
    "south": ((0, 0, 1), 0.8), "east": ((1, 0, 0), 0.62), "west": ((-1, 0, 0), 0.62),
}


def _texel_tables(h, frame=0):
    tabs = []
    for n in h.names:
        mt = h.mats[n]
        img = mt.cell(frame, wkit.ANIM_FRAMES) if mt.animated else mt.cell()
        tabs.append((np.array(img.convert("RGBA")), mt.glow))
    return tabs


def _face_quads(c, n):
    """복셀 가운데 c, 법선 n 인 면의 네 꼭짓점."""
    c = np.asarray(c, float)
    n = np.asarray(n, float)
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.5 else np.array([0, 1.0, 0])
    b = np.cross(n, a)
    o = c + n * 0.5
    return [o + (a * sa + b * sb) * 0.5 for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def texel(h, tabs, x, y, z, name):
    """복셀 (격자 칸) 의 면 name 에 찍히는 텍셀 색 (빌드된 모델과 같은 규칙)."""
    tex, glow = tabs[h.grid[x, y, z] - 1]
    if name in ("north", "south"):
        tu, tv = x % 16, 15 - (y % 16)
    elif name in ("east", "west"):
        tu, tv = z % 16, 15 - (y % 16)
    else:
        tu, tv = x % 16, z % 16
    if name in ("north", "east"):
        tu = 15 - tu
    return tex[tv, tu, :3].astype(float), glow


def vox_render(h, yaw=0.0, pitch=20.0, size=420, with_head=True, frame=0, bg=(28, 26, 36), fit=None, night=False):
    """yaw 0 = 얼굴(-Z) 정면, 양수면 착용자의 왼쪽으로 돈다. pitch 양수 = 위에서 내려다봄."""
    from PIL import Image, ImageDraw
    g = h.grid
    W, Hh, D = g.shape
    tabs = _texel_tables(h, frame)
    occ = g > 0
    skin = np.zeros_like(occ)
    if with_head:
        skin = head(h._X, h._Y, h._Z) & ~occ
    solid = occ | skin
    th, ph = math.radians(yaw), math.radians(pitch)
    f = np.array([math.sin(th) * math.cos(ph), -math.sin(ph), math.cos(th) * math.cos(ph)])
    r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    faces = []
    for (x, y, z) in np.argwhere(solid):
        c = np.array([x + 0.5 - h.CX, y + 0.5 - h.CY, z + 0.5 - h.CZ])
        for name, (n, lit) in _FACE_DIRS.items():
            if np.dot(n, f) >= -1e-6:
                continue
            nx, ny, nz = x + n[0], y + n[1], z + n[2]
            if 0 <= nx < W and 0 <= ny < Hh and 0 <= nz < D and solid[nx, ny, nz]:
                continue
            glow = False
            if skin[x, y, z]:
                k = ((x * 7 + y * 13 + z * 5) % 5) / 40.0
                col = np.array([200, 148, 106]) * (0.95 + k)
                if name == "north" and abs(c[1] + 0.5) < 0.6 and 1 <= abs(c[0]) <= 3:
                    col = np.array([245, 245, 245]) if abs(c[0]) > 2 else np.array([70, 50, 120])
                if c[1] > 2.5:   # 머리카락
                    col = np.array([70, 46, 28]) * (0.9 + k)
            else:
                col, glow = texel(h, tabs, x, y, z, name)
            if not glow:
                col = col * lit * (0.28 if night else 1.0)
            pts = [(float(np.dot(q, r)), float(np.dot(q, u))) for q in _face_quads(c, n)]
            depth = float(np.dot(c + np.asarray(n) * 0.5, f))
            faces.append((depth, pts, tuple(int(v) for v in np.clip(col, 0, 255))))
    allp = np.array([p for fc in faces for p in fc[1]])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    mid = (lo + hi) / 2
    if fit is None:
        fit = max(6.0, float((hi - lo).max()) / 2 * 1.08)
    ss = 2
    S = size * ss
    img = Image.new("RGB", (S, S), tuple(int(v * (0.45 if night else 1)) for v in bg))
    d = ImageDraw.Draw(img)
    sc = S / (2 * fit)
    faces.sort(key=lambda t: -t[0])
    for depth, pts, col in faces:
        d.polygon([(S / 2 + (px - mid[0]) * sc, S / 2 - (py - mid[1]) * sc) for px, py in pts], fill=col)
    return img.resize((size, size), Image.LANCZOS)


VIEWS = ((-32, 20, "앞 3/4", 0, False), (0, 6, "정면", 4, False), (90, 10, "옆", 8, False),
         (148, 24, "뒤 3/4", 12, False), (-32, 20, "밤", 6, True))


def set_views(h, size=300):
    return [vox_render(h, yaw, pitch, size=size, frame=fr, night=nt) for yaw, pitch, _, fr, nt in VIEWS]


def _caption(text, width, font, height=30, bg=(44, 30, 30), fg=(255, 210, 160)):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(font, 16) if font else ImageFont.load_default()
    d.text((8, 6), text, font=f, fill=fg)
    return img


def main(only=None):
    from PIL import Image
    from mc3d import contact_sheet
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    imgs, labels = [], []
    font = FONT if os.path.exists(FONT) else None
    for sid, fn in HELMETS.items():
        if only and sid not in only:
            continue
        h = fn()
        model = h.build(f"armor/{sid}_helmet", SCRATCH)
        n = len(model.elements)
        st = sum(1 for m in h.mats.values() if not m.animated)
        print(f"{sid}: {n} elements, mats {st} static + {len(h.mats) - st} anim")
        png = os.path.join(PREVIEW_DIR, f"helmet_{sid}.png")
        wkit.helmet_preview(model, png)            # 키트 미리보기 (아래 줄에 참고용으로 붙인다)
        kit = Image.open(png).convert("RGB")
        views = set_views(h, size=300)
        row = contact_sheet(views, [f"{NAMES_KO[sid]} {t} · {n}" for _, _, t, _, _ in VIEWS], cols=5, cell=300, font=font)
        cap = _caption("아래: 키트 렌더러 helmet_preview — 참고용 (라벨 '앞'이 실제로는 뒤, '뒤'가 앞. 일부 면이 안 그려져 속이 비쳐 보임)",
                       row.width, font)
        out = Image.new("RGB", (row.width, row.height + cap.height + kit.height), (18, 16, 26))
        out.paste(row, (0, 0))
        out.paste(cap, (0, row.height))
        out.paste(kit, (0, row.height + cap.height))
        out.save(png)
        for v, (_, _, tag, _, _) in zip(views, VIEWS):
            imgs.append(v)
            labels.append(f"{NAMES_KO[sid]} ({sid}) · {tag} · {n}")
    if not only:
        contact_sheet(imgs, labels, cols=5, cell=300, font=font).save(os.path.join(PREVIEW_DIR, f"{MODULE}.png"))


if __name__ == "__main__":
    main(sys.argv[1:] or None)
