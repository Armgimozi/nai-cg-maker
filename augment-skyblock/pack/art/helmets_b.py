"""
증강 스카이블럭 — 복셀 투구 세트 B (보스 / 최종 세트): 서리 군주, 화염 거신, 공허 군주, 프리즘.

네모네모 복셀 아트: 1 복셀 = 플레이어 스킨 1픽셀 크기의 정육면체. 투구 전체가 작은 큐브로 쌓여 있고,
큐브 한 면 = 재료 무늬의 텍셀 하나라서 큐브마다 색이 조금씩 달라 격자가 그대로 보인다.
곡선(뿔, 왕관 가시, 후광)은 모두 계단식으로 꺾이고, 계단의 층끼리는 반드시 면으로 붙는다
(모서리로만 닿아 점선처럼 보이는 조각이 없다 — check() 가 6방향 연결을 검사한다).

좌표 (wkit.helmet): 원점 = 머리 가운데, 머리는 X,Y,Z 모두 -4..4, 얼굴은 -Z. 복셀 가운데는 ±0.5, ±1.5 ...
껍데기 한 겹은 |.| = 4.5 (머리 바로 바깥) 층, 한 겹 더 바깥은 5.5 층.
대부분 오른쪽(X>0)을 만들고 mirror() 로 왼쪽에 복사한다.

게임 안 맞춤: 모든 복셀은 Y >= -4.5 (바닐라 투구 층의 아래 끝 -5 위). Y -4.5 줄은 |X| <= 4.5 이거나 뒤쪽(Z >= 2.5)만.

몸 갑옷(armor_b.py)과 같은 팔레트 (실제로 지어지는 그대로):
  frostlord  은 판금 투구 + 크림빛 털 두루마리(2칸 두께) + 금 테 + 하늘빛 얼음 왕관: 앞 가운데 큰 가시(6→4→2폭→2x1),
             둘레 가시 10개, 정수리 가시 1개. 가시는 짙은 얼음 → 밝은 얼음(반짝이는 애니메이션) → 하얗게 빛나는 끝.
             이마 보석 = 금 1칸 테 안의 빛나는 청록 8복셀 육각 + 흰 하이라이트 1칸, 띠에 작은 보석 6개,
             뒤 얼음 마름모 문장, 왕관 양옆 위에 떠 있는 ✦ 반짝이 2개(숨쉬듯 빛남)
  inferno    현무암 통투구(정수리 2단 계단, 위 가장자리에 밝은 판 이음매 + 금 리벳) + 얼굴: 청동 눈썹, 2칸 높이 눈
             (흰 심지 + 빨간 테, 스스로 빛남), 짧은 콧날, 용암 입 창살, 앞으로 튀어나온 턱과 금 송곳니, 비스듬한 볼판.
             뿔은 3x3 → 2x2 → 1x1 로 가늘어지며 바깥-위로 뻗다 안쪽-앞으로 휘고(금 고리 둘, 타오르는 끝),
             볏은 불꽃 혀 3개(앞이 가장 높음, 노란 심지). 옆과 뒤에 계단식 용암 틈(숨쉬듯 빛남), 뒤 목가리개 한 단
  sovereign  짙은 보라 두건(옆과 뒤 세로 주름, 아래 단이 한 칸 벌어짐, 뒤로 뾰족한 두건 끝) + 뾰족 아치 얼굴 구멍
             (금 테 + 검은 안감) + 강철빛 가시 왕관(가시 9개, 바깥 면은 스스로 빛나는 밝은 강철 날이라 밤에도 윤곽이
             보임, 앞 가운데가 가장 높음, 끝 한 칸만 빛나는 보라) + 이마 보석(금 1칸 테, 빛나는 2x2x2 + 흰 하이라이트) +
             떠 있는 보라 보석 4개(1-2-2-1 쌍뿔, 숨쉬듯 빛남), 뒤 두건 끝을 따라 흐르는 룬 줄
  prism      진주빛 흰 투구(반짝임 애니메이션) + 금/무지개/금 이마 띠 + 무지개 이마 보석 + 결정 7개: 가운데 진주 결정
             (앞면이 무지개 심, 스스로 빛남) + 연보라 결정 4개 + 하늘빛 결정 2개(3톤 면: 짙은 그늘/몸/흰 모서리,
             끝은 숨쉬듯 빛남) + 관자놀이의 하늘빛 결정 날개(가는 깃 3장이 뿌리에서 이어진 부채) + 떠 있는 무지개 후광.
             무지개 재료는 하나(띠, 보석, 결정 심, 뒤 줄, 후광이 함께 씀)
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

MODULE = "helmets_b"
PREVIEW_DIR = os.path.join(HERE, "preview")
SCRATCH = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
NAMES_KO = {"frostlord": "서리 군주", "inferno": "화염 거신", "sovereign": "공허 군주", "prism": "프리즘"}

A = np.abs


# ─────────────────────────── 도우미 ───────────────────────────

def head(X, Y, Z, m=4.0):
    """머리(8x8x8) 안쪽."""
    return (A(X) < m) & (A(Y) < m) & (A(Z) < m)


def sqr(X, Z, r, cham=0.0):
    """X-Z 평면의 꽉 찬 네모 (복셀 가운데 기준 |X|,|Z| <= r), 모서리를 계단식으로 cham 만큼 깎는다."""
    m = (A(X) <= r) & (A(Z) <= r)
    if cham > 0:
        m &= A(X) + A(Z) <= 2 * r - cham
    return m


def ring(X, Z, r, cham=0.0):
    """sqr 의 테두리 한 겹 (모서리를 깎아도 대각선 계단으로 이어진다)."""
    return sqr(X, Z, r, cham) & ~sqr(X, Z, r - 1, cham)


def idx(h, x, y, z):
    return int(math.floor(x + h.CX)), int(math.floor(y + h.CY)), int(math.floor(z + h.CZ))


def put(h, x, y, z, mat):
    """설계 좌표 (x, y, z) 를 품은 복셀 하나."""
    i, j, k = idx(h, x, y, z)
    if 0 <= i < h.W and 0 <= j < h.H and 0 <= k < h.D:
        h.grid[i, j, k] = 0 if mat is None else h._id(mat)


def get(h, x, y, z):
    i, j, k = idx(h, x, y, z)
    if 0 <= i < h.W and 0 <= j < h.H and 0 <= k < h.D:
        g = h.grid[i, j, k]
        return h.names[g - 1] if g else None
    return None


def vbox(h, x0, x1, y0, y1, z0, z1, mat):
    """복셀 가운데 좌표로 양끝 포함 상자."""
    return h.fill(lambda X, Y, Z: (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1) & (Z >= z0) & (Z <= z1), mat)


def blk(h, cx, cy, cz, s, mat):
    """가운데 (cx, cy, cz), 한 변 s 복셀의 정육면체 (s 가 홀수면 가운데는 복셀 가운데, 짝수면 복셀 경계)."""
    d = (s - 1) / 2
    vbox(h, cx - d, cx + d, cy - d, cy + d, cz - d, cz + d, mat)


def spike(h, cx, cz, y0, sizes, mat_of_t, lean=(0.0, 0.0), edge=None, cell=None):
    """
    계단식 가시 (얼음 가시, 결정, 왕관 뿔). 층마다 (sx, sz) 크기의 네모를 쌓고, 층이 오를 때마다 lean 만큼 옮긴다.
    층끼리는 언제나 면으로 붙는다: 원하는 위치가 아래 층과 겹치지 않으면 한 칸만 옮기고, 아래 층 위에
    다리 복셀을 하나 더 놓아 계단이 끊기지 않게 한다 (모서리로만 닿는 점선 조각 방지).
    cx, cz: 밑동 가운데, y0: 맨 아래 층의 복셀 가운데 Y. mat_of_t(t): t = 0 밑동 → 1 끝.
    edge = (재료, t_max): t < t_max 인 층에서 바깥쪽(원점에서 먼 쪽) 줄을 이 재료로 (강철 날 등).
    cell(t, out, side, sx, sz): 복셀마다 재료를 바꾼다 (out: 바깥쪽 줄이면 True, side: 옆 방향 -1/0/1). None 이면 층 재료.
    """
    n = len(sizes)
    prev = None
    norm = math.hypot(cx, cz) or 1.0
    ox, oz = cx / norm, cz / norm
    for i, s in enumerate(sizes):
        sx, sz = (s, s) if not isinstance(s, (tuple, list)) else s
        x_lo = math.floor(cx + lean[0] * i - sx / 2 + 0.5)
        z_lo = math.floor(cz + lean[1] * i - sz / 2 + 0.5)
        bridges = []
        if prev is not None:
            px0, px1, pz0, pz1 = prev
            lo_x, hi_x = px0 - sx + 1, px1 - 1          # 아래 층과 겹치는 위치 범위
            lo_z, hi_z = pz0 - sz + 1, pz1 - 1
            x_lo = min(max(x_lo, lo_x - 1), hi_x + 1)   # 겹침에서 한 칸 밖까지만
            z_lo = min(max(z_lo, lo_z - 1), hi_z + 1)
            out_x = x_lo < lo_x or x_lo > hi_x
            out_z = z_lo < lo_z or z_lo > hi_z
            if out_x and out_z:
                z_lo = min(max(z_lo, lo_z), hi_z)
                out_z = False
            if out_x:   # 아래 층 위, 새 층 바로 옆에 다리 한 칸
                bridges.append((px1 - 1 if x_lo > hi_x else px0, max(z_lo, pz0)))
            if out_z:
                bridges.append((max(x_lo, px0), pz1 - 1 if z_lo > hi_z else pz0))
        y = y0 + i
        t = i / max(1, n - 1)
        m = mat_of_t(t)
        vbox(h, x_lo + 0.5, x_lo + sx - 0.5, y, y, z_lo + 0.5, z_lo + sz - 0.5, m)
        for bx, bz in bridges:
            put(h, bx + 0.5, y, bz + 0.5, m)
        if edge and t < edge[1] and m != edge[0] and (sx > 1 or sz > 1):
            cells = [(x_lo + a + 0.5, z_lo + b + 0.5) for a in range(sx) for b in range(sz)]
            best = max(c[0] * ox + c[1] * oz for c in cells)
            for c in cells:
                if c[0] * ox + c[1] * oz >= best - 0.35:
                    put(h, c[0], y, c[1], edge[0])
        if cell:
            cells = [(x_lo + a + 0.5, z_lo + b + 0.5) for a in range(sx) for b in range(sz)]
            o = [c[0] * ox + c[1] * oz for c in cells]
            p = [-c[0] * oz + c[1] * ox for c in cells]
            for c, oo, pp in zip(cells, o, p):
                sd = -1 if pp <= min(p) + 0.35 and max(p) - min(p) > 0.5 else 1 if pp >= max(p) - 0.35 and max(p) - min(p) > 0.5 else 0
                mm = cell(t, oo >= max(o) - 0.35, sd, sx, sz)
                if mm:
                    put(h, c[0], y, c[1], mm)
        prev = (x_lo, x_lo + sx, z_lo, z_lo + sz)


def bipyr(h, cx, cy, cz, layers, mat, hi=None, core=None):
    """
    떠 있는 쌍뿔 보석. layers: 아래→위 층 크기. 짝수 크기는 (cx, cz) 가 복셀 경계, 홀수는 복셀 가운데여야 대칭.
    'c4' = 모서리를 깎은 4x4. 크기 1 층이 짝수 가운데에 놓이면 아래 끝은 +X+Z, 위 끝은 -X-Z 로 반 칸 치우친다 (비틀린 결정).
    hi: 맨 위에서 두 번째 층의 왼쪽 위 복셀을 이 재료(흰 하이라이트)로.
    """
    y = cy - (len(layers) - 1) / 2
    for i, s in enumerate(layers):
        clip = s == "c4"
        n = 4 if clip else s
        x_lo = math.floor(cx - n / 2 + 0.5)
        z_lo = math.floor(cz - n / 2 + 0.5)
        if n == 1 and float(cx).is_integer() and i == len(layers) - 1:
            x_lo -= 1                                     # 위 끝은 -X 쪽, 아래 끝은 +X 쪽 (비틀린 결정)
        if n == 1 and float(cz).is_integer() and i == len(layers) - 1:
            z_lo -= 1
        cells = [(x_lo + a + 0.5, z_lo + b + 0.5) for a in range(n) for b in range(n)
                 if not (clip and a in (0, n - 1) and b in (0, n - 1))]
        for c in cells:
            put(h, c[0], y + i, c[1], mat)
        if hi and i == len(layers) - 2:
            c = min(cells, key=lambda c: (c[1], c[0]))   # 앞(-Z) 면의 왼쪽
            put(h, c[0], y + i, c[1], hi)


def sparkle_cross(h, cx, cy, cz, mat, arm=1):
    """✦ 반짝이 (X-Y 평면 십자 + 앞뒤 한 칸 = 서로 면으로 붙은 7복셀)."""
    vbox(h, cx - arm, cx + arm, cy, cy, cz, cz, mat)
    vbox(h, cx, cx, cy - arm, cy + arm, cz, cz, mat)


def hollow(h, y_min=-1.5, keep=None):
    """
    머리 바로 바깥 4.5 층 중, 바깥 5.5 층이 덮고 있는 면 복셀을 비운다 (속 빈 껍데기 → element 절약).
    모서리/꼭짓점 복셀과 y_min 아래(투구 아랫단)는 남겨 아래에서 틈이 보이지 않게 한다.
    """
    g = h.grid
    X, Y, Z = h._X, h._Y, h._Z
    cnt = (A(X) == 4.5).astype(int) + (A(Y) == 4.5) + (A(Z) == 4.5)
    inner = (np.maximum(np.maximum(A(X), A(Y)), A(Z)) == 4.5) & (cnt == 1) & (g > 0) & (Y >= y_min)
    if keep is not None:
        inner &= ~np.asarray(keep(X, Y, Z), dtype=bool)
    occ = g > 0
    out = np.zeros_like(occ)
    for ax, C in ((0, X), (1, Y), (2, Z)):
        up = np.zeros_like(occ)
        dn = np.zeros_like(occ)
        sl_a = [slice(None)] * 3
        sl_b = [slice(None)] * 3
        sl_a[ax], sl_b[ax] = slice(0, -1), slice(1, None)
        up[tuple(sl_a)] = occ[tuple(sl_b)]      # 다음 칸(+) 이 차 있음
        dn[tuple(sl_b)] = occ[tuple(sl_a)]      # 이전 칸(-) 이 차 있음
        out |= (C == 4.5) & up
        out |= (C == -4.5) & dn
    g[inner & out] = 0
    return h


# ─────────────────────────── 검사 ───────────────────────────

def components(grid):
    """6방향(면) 연결 덩어리. (라벨 격자, 덩어리 목록[(크기, 라벨)]) — 큰 것부터."""
    occ = grid > 0
    lab = np.zeros(grid.shape, dtype=np.int32)
    sizes = []
    W, H, D = grid.shape
    n = 0
    for start in map(tuple, np.argwhere(occ)):
        if lab[start]:
            continue
        n += 1
        lab[start] = n
        stack = [start]
        cnt = 0
        while stack:
            x, y, z = stack.pop()
            cnt += 1
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (x + dx, y + dy, z + dz)
                if 0 <= q[0] < W and 0 <= q[1] < H and 0 <= q[2] < D and occ[q] and not lab[q]:
                    lab[q] = n
                    stack.append(q)
        sizes.append((cnt, n))
    sizes.sort(reverse=True)
    return lab, sizes


def check(h, floaters=(), n_elements=None, limit=220, verbose=True):
    """
    계약 검사: 머리 안 복셀 0, 범위 ±15, Y>=-4.5, Y=-4.5 줄은 |X|<=4.5 또는 뒤(Z>=2.5),
    본체 하나 + 의도한 떠 있는 장식(floaters 재료로만 된 덩어리)만. 문제 목록을 돌려준다.
    """
    g = h.grid
    X, Y, Z = h._X, h._Y, h._Z
    occ = g > 0
    probs = []
    if (occ & head(X, Y, Z)).any():
        probs.append(f"머리 안 복셀 {int((occ & head(X, Y, Z)).sum())}")
    if (occ & (Y < -4.6)).any():
        probs.append(f"Y<-5 복셀 {int((occ & (Y < -4.6)).sum())}")
    bad = occ & (Y < -4) & (A(X) > 4.6) & (Z < 2.5)
    if bad.any():
        probs.append(f"Y=-4.5 에서 |X|>4.5 (어깨) {int(bad.sum())}")
    lab, comps = components(g)
    fl_ids = [h.names.index(f) + 1 for f in floaters if f in h.names]
    body = comps[0][1]
    extra = []
    for cnt, l in comps[1:]:
        mats = set(np.unique(g[lab == l]).tolist())
        if not mats <= set(fl_ids):
            pos = np.argwhere(lab == l)[0]
            extra.append((cnt, tuple(float(v) for v in (pos[0] + 0.5 - h.CX, pos[1] + 0.5 - h.CY, pos[2] + 0.5 - h.CZ)),
                          [h.names[m - 1] for m in mats]))
    if extra:
        probs.append(f"떨어진 조각 {len(extra)}: {extra[:8]}")
    if n_elements is not None and n_elements > limit:
        probs.append(f"element {n_elements} > {limit}")
    if verbose:
        print(f"    덩어리 {len(comps)} (본체 {comps[0][0]} 복셀, 떠 있는 장식 {len(comps) - 1 - len(extra)}), "
              f"복셀 {int(occ.sum())}, 문제: {probs or '없음'}")
    return probs


# ═══════════════════════════════ 서리 군주 ═══════════════════════════════

def helm_frostlord():
    M = {
        "silver": Mat(["#6e7c94", "#8e9cb2", "#aebcd0", "#d2dcea"], "metal", seed=201),
        "silver_d": Mat(["#3e4a66", "#52607e", "#687896", "#8090ae"], "metal", seed=202),
        "fur": Mat(["#b09a7a", "#cab496", "#e0ceb0", "#f2e6d0"], "stone", seed=203),
        "fur_d": Mat(["#7e6a52", "#968066", "#ac987c", "#c2ae92"], "stone", seed=204),
        "gold": Mat(["#8a5a12", "#b88424", "#e0b040", "#fae07a"], "metal", seed=205),
        "ice_d": Mat(["#1a4a90", "#2860a8", "#367cc4", "#4e94da"], "crystal", seed=206),
        "ice": Mat(["#3a84cc", "#56a2e2", "#7ac0f2", "#a2dcff"], "crystal", seed=207),
        "ice_l": Mat(["#8ccaf2", "#a4d8f8", "#c0e6fe", "#eafaff"], "sparkle", seed=208),
        "ice_tip": Mat(["#a0e4ff", "#ccf2ff", "#eafcff", "#ffffff"], "stone", glow=True, seed=209),
        "gem": Mat(["#40d8f0", "#5ee6fa", "#8cf2ff", "#c8fcff"], "stone", glow=True, seed=210),
        "gem_hi": Mat(["#f4ffff", "#ffffff", "#ffffff", "#ffffff"], "flat", glow=True, seed=212),
        "spark": Mat(["#70d8ff", "#a8ecff", "#dcfaff", "#ffffff"], "pulse", glow=True, seed=211),
    }
    h = wkit.helmet(M, seed=21)

    # 은 투구 (머리 한 겹 위): 정수리, 옆, 뒤. 얼굴은 눈썹 아래로 열어 둔다
    def shell(X, Y, Z):
        return sqr(X, Z, 4.5) & (Y >= -3.5) & (Y <= 4.5) & ~head(X, Y, Z)
    h.fill(shell, "silver")
    h.clear(lambda X, Y, Z: (Z == -4.5) & (A(X) <= 3.5) & (Y <= 0.5))
    h.clear(lambda X, Y, Z: (Z <= -2.5) & (A(X) == 4.5) & (Y <= -2.5))          # 볼 아래 트임
    # 볼가리개: 옆으로 한 칸 튀어나온 어두운 은 판 + 금 테
    h.fill(lambda X, Y, Z: (A(X) == 5.5) & (Y >= -2.5) & (Y <= -0.5) & (Z >= -3.5) & (Z <= 1.5), "silver_d")
    h.fill(lambda X, Y, Z: (A(X) == 5.5) & (Y == -3.5) & (Z >= -3.5) & (Z <= 1.5), "gold")
    # 뒤 목가리개 (어두운 은, 뒤쪽만 -4.5 까지)
    h.fill(lambda X, Y, Z: (Z == 5.5) & (A(X) <= 3.5) & (Y >= -4.5) & (Y <= -1.5), "silver_d")
    h.fill(lambda X, Y, Z: (Z == 5.5) & (A(X) <= 3.5) & (Y == -4.5), "gold")

    # 털 두루마리: 이마 높이로 한 바퀴, 두 칸 두께 (안 5.5 층 3줄 + 바깥 6.5 층 2줄), 아래 줄은 그늘색
    fur_r = lambda X, Z: ring(X, Z, 5.5, 2)
    face_gap = lambda X, Y, Z: (Z < -5) & (A(X) <= 3.5) & (Y < 1)
    h.fill(lambda X, Y, Z: fur_r(X, Z) & (Y >= 0.5) & (Y <= 2.5) & ~face_gap(X, Y, Z), "fur")
    h.fill(lambda X, Y, Z: ring(X, Z, 6.5, 4) & (Y >= 1.5) & (Y <= 2.5) & ~((Z < -6) & (A(X) <= 2.5)), "fur")
    h.fill(lambda X, Y, Z: fur_r(X, Z) & (Y == 0.5) & ~face_gap(X, Y, Z), "fur_d")
    # 두루마리 마디 (3칸마다 그늘 한 줄 → 털 뭉치가 굴러가는 모양)
    # 뒤 목 털 (뒤 반쪽만, 투구 아래 끝과 같은 높이)
    h.fill(lambda X, Y, Z: ring(X, Z, 5.5, 2) & (Y >= -3.5) & (Y <= -2.5) & (Z >= 2.5), "fur")
    h.fill(lambda X, Y, Z: ring(X, Z, 5.5, 2) & (Y == -3.5) & (Z >= 2.5) & (np.floor(X + 40) % 3 == 0), "fur_d")

    # 금 테 + 얼음 왕관 띠
    h.fill(lambda X, Y, Z: fur_r(X, Z) & (Y == 3.5), "gold")
    h.fill(lambda X, Y, Z: fur_r(X, Z) & (Y == 4.5), "ice_d")

    def ice_t(t):
        return "ice" if t < 0.4 else "ice_l" if t < 0.8 else "ice_tip"

    # 가운데 큰 가시: 6 → 4 → 2 폭으로 가늘어지고 끝은 2x1 (가운데 선이 복셀 경계라 1폭은 비대칭이 된다)
    spike(h, 0.0, -5.0, 5.5, [(6, 2), (4, 2), (4, 2), (4, 2), (2, 2), (2, 2), (2, 2), (2, 1), (2, 1), (2, 1), (2, 1)],
          ice_t, (0.0, -0.1))
    # 둘레 가시 (오른쪽 반) — 바깥으로 벌어지는 왕관. 층끼리 면으로 붙는 계단
    spikes = [
        (3.5, -5.5, [(3, 2), (2, 2), (2, 1), 1, 1, 1], (0.15, -0.2)),
        (5.5, -3.5, [3, 2, 2, 2, 1, 1, 1, 1], (0.3, -0.25)),
        (5.5, 0.5, [(2, 3), 2, 2, 1, 1, 1], (0.35, 0.0)),
        (4.5, 4.5, [2, 2, 2, 1, 1], (0.25, 0.25)),
        (1.0, 5.5, [(2, 2), 2, 2, 1, 1, 1], (0.0, 0.3)),
    ]
    for cx, cz, sizes, lean in spikes:
        spike(h, cx, cz, 5.5, sizes, ice_t, lean)
    # 정수리 안쪽 가시 (두 번째 단)
    spike(h, 0.0, 1.0, 5.5, [(4, 2), (2, 2), (2, 2), (2, 2), (2, 1), (2, 1), (2, 1)], ice_t, (0.0, 0.1))

    # 띠의 작은 보석 (가시 밑동, 띠 표면에 붙음)
    put(h, 6.5, 3.5, -2.5, "gem")
    put(h, 6.5, 3.5, 2.5, "gem")
    # 이마 큰 보석: 금 받침(1칸 테) + 빛나는 8복셀 육각 보석 + 흰 하이라이트
    h.fill(lambda X, Y, Z: (Z == -6.5) & (A(X) <= 2.5) & (Y >= 0.5) & (Y <= 4.5)
           & ~((A(X) == 2.5) & ((Y == 0.5) | (Y == 4.5))), "gold")
    h.fill(lambda X, Y, Z: (Z == -7.5) & (A(X) <= 1.5) & (Y >= 1.5) & (Y <= 3.5)
           & ~((A(X) == 1.5) & (Y != 2.5)), "gem")
    h.mirror()
    put(h, -0.5, 3.5, -7.5, "gem_hi")
    put(h, 0.5, 3.5, 6.5, "gem")
    put(h, -0.5, 3.5, 6.5, "gem")
    # 뒤 문장: 얼음 마름모 + 보석
    h.fill(lambda X, Y, Z: (Z == 5.5) & (A(X) + A(Y + 1.0) <= 2.5) & (Y <= 0.5) & (Y >= -1.5), "ice")
    vbox(h, -0.5, 0.5, -1.5, -0.5, 6.5, 6.5, "gem")
    # 떠 있는 반짝이 (왕관 바깥 위)
    for sx in (-1, 1):
        sparkle_cross(h, sx * 11.5, 13.5, -0.5, "spark")
    return h


# ═══════════════════════════════ 화염 거신 ═══════════════════════════════

def helm_inferno():
    M = {
        "basalt": Mat(["#1c1820", "#2a2530", "#3a3442", "#4c4454"], "stone", seed=301),
        "basalt_l": Mat(["#4a4352", "#5e5568", "#746a7e", "#8c8096"], "stone", seed=302),
        "bronze": Mat(["#3c2414", "#5a361c", "#784a24", "#946030"], "metal", seed=309),
        "gold": Mat(["#7a4a0c", "#a8701a", "#d49a2c", "#f6cc5c"], "metal", seed=303),
        "eye_c": Mat(["#ffe890", "#fff3b0", "#fff8d0", "#ffffff"], "flat", glow=True, seed=304),
        "eye_r": Mat(["#d82000", "#ff3000", "#ff4410", "#ff7040"], "flat", glow=True, seed=310),
        "ember": Mat(["#c02606", "#ff5a10", "#ff9a30", "#ffd890"], "stone", glow=True, seed=305),
        "lava": Mat(["#b01e06", "#e8500c", "#ff8c1a", "#ffd060"], "pulse", glow=True, seed=306),
        "flame_o": Mat(["#a01404", "#dc3c08", "#ff7a12", "#ffbe40"], "fire", glow=True, seed=307),
        "flame_y": Mat(["#ff9a14", "#ffc034", "#ffe676", "#fffad0"], "fire", glow=True, seed=308),
    }
    h = wkit.helmet(M, seed=31)

    # 육중한 현무암 통투구: 바깥 5.5 층, 정수리는 두 단 계단으로 둥글게 (5.5 → 4.5 → 3.5)
    def hull(X, Y, Z):
        m = sqr(X, Z, 5.5, 2) & (Y >= -3.5) & (Y <= 4.5)
        m |= sqr(X, Z, 4.5, 2) & (Y == 5.5)
        m |= sqr(X, Z, 3.5, 2) & (Y == 6.5)
        m |= sqr(X, Z, 4.5, 1) & (Y == -4.5)                     # 목 둘레 (어깨에 닿지 않게 4.5 안쪽)
        return m & ~(head(X, Y, Z) | ((A(X) < 4) & (A(Z) < 4) & (Y < -4)))
    h.fill(hull, "basalt")
    # 가로 판 이음매 (밝은 현무암) 두 줄 + 금 리벳
    h.fill(lambda X, Y, Z: hull(X, Y, Z) & (Y == 4.5) & (Z > -5), "basalt_l")
    h.fill(lambda X, Y, Z: hull(X, Y, Z) & (Y == 4.5) & (Z > -5) & (np.floor(X + Z + 41) % 6 == 0), "gold")
    # 뒤 목가리개 (한 겹 벌어짐, 뒤쪽만) — 금 테
    h.fill(lambda X, Y, Z: ring(X, Z, 6.5, 3) & (Y == -3.5) & (Z >= 1.5), "basalt_l")

    # 얼굴 (Z -5.5 판): 눈 구멍 그림자, 2칸 높이 눈(흰 심지 + 빨간 테), 청동 눈썹, 짧은 콧날, 용암 입 창살
    for sx, sy in ((1.5, 0.5), (4.5, 0.5), (3.5, -1.5), (4.5, -0.5)):
        put(h, sx, sy, -5.5, "basalt")
    for ex, ey, m in ((2.5, 0.5, "eye_c"), (3.5, 0.5, "eye_r"), (1.5, -0.5, "eye_r"), (2.5, -0.5, "eye_c"),
                      (3.5, -0.5, "eye_r")):
        put(h, ex, ey, -5.5, m)
    for bx, by in ((1.5, 1.5), (2.5, 1.5), (3.5, 1.5), (3.5, 2.5), (4.5, 2.5), (1.5, 0.5)):
        put(h, bx, by, -6.5, "bronze")
    vbox(h, 0.5, 0.5, -1.5, 1.5, -6.5, -6.5, "basalt_l")                      # 콧날 (짧게, 눈썹 높이까지)
    # 입 창살: 어두운 기둥 사이로 안쪽 용암
    h.clear(lambda X, Y, Z: (Z == -5.5) & (A(X) <= 2.5) & (Y >= -3.5) & (Y <= -2.5) & (np.floor(X) % 2 == 0))
    h.fill(lambda X, Y, Z: (Z == -4.5) & (A(X) <= 2.5) & (Y >= -3.5) & (Y <= -2.5) & (np.floor(X) % 2 == 0), "lava")
    # 앞으로 튀어나온 턱 (밝은 현무암, 위로 솟은 금 송곳니 두 개)
    vbox(h, 0.5, 3.5, -4.5, -4.5, -6.5, -5.5, "basalt_l")
    vbox(h, 0.5, 1.5, -4.5, -4.5, -7.5, -7.5, "basalt")
    put(h, 2.5, -3.5, -6.5, "gold")
    # 비스듬한 볼판: 깎인 모서리 바깥 한 겹 (|X|+|Z| = 10), 아래 두 줄
    h.fill(lambda X, Y, Z: (A(X) + A(Z) == 10) & (Z < 0) & (A(X) >= 4.5) & (A(X) <= 6.5) & (Y >= -3.5) & (Y <= 0.5), "basalt_l")

    # 옆과 뒤의 용암 틈 (계단식 번개 모양, 숨쉬듯 빛남)
    for (y0, y1, z) in ((3.5, 3.5, -1.5), (2.5, 3.5, -0.5), (0.5, 2.5, 0.5), (-1.5, 0.5, 1.5), (-2.5, -1.5, 2.5)):
        vbox(h, 5.5, 5.5, y0, y1, z, z, "lava")
    for (y0, y1, x) in ((3.5, 3.5, 2.5), (1.5, 3.5, 1.5), (0.5, 1.5, 2.5), (-1.5, 0.5, 1.5), (-3.5, -1.5, 2.5)):
        vbox(h, x, x, y0, y1, 5.5, 5.5, "lava")

    # 볏 받침: 정수리 위 금 등줄 (앞에서 뒤로)
    vbox(h, 0.5, 0.5, 7.5, 7.5, -3.5, 3.5, "gold")
    # 타오르는 볏: 뒤로 휘날리는 불꽃 혀 3개 (앞이 가장 높다), 노란 심지가 앞에서 보인다
    for z, n, w in ((-2.5, 8, 4), (0.5, 6, 4), (3.0, 5, 2)):
        sizes = [(w, 2)] * 2 + [(2, 2)] * (n - 3) + [(2, 1)]
        spike(h, 0.0, z, 8.5, sizes, lambda t: "flame_o", (0.0, 0.3))
        spike(h, 0.0, z - 0.5, 8.5, [(2, 1)] * max(1, n - 3), lambda t: "flame_y", (0.0, 0.3))

    # 큰 뿔: 옆 판에서 나와 비스듬히 바깥-위로, 끝은 안쪽-앞으로 휜다. 3x3 → 2x2 → 1x1, 금 고리 두 개, 타오르는 끝
    blk(h, 6.5, 2.5, -0.5, 3, "gold")
    blk(h, 7.5, 3.5, -0.5, 3, "basalt_l")
    blk(h, 8.5, 4.5, -0.5, 3, "basalt_l")
    blk(h, 10.0, 6.0, -1.0, 2, "gold")
    blk(h, 10.0, 7.0, -1.0, 2, "basalt_l")
    blk(h, 10.0, 8.0, -2.0, 2, "basalt_l")
    for x, y, z in ((10.5, 9.5, -2.5), (10.5, 10.5, -2.5), (10.5, 11.5, -2.5), (9.5, 11.5, -2.5),
                    (9.5, 12.5, -2.5), (9.5, 12.5, -3.5)):
        put(h, x, y, z, "ember" if y > 10 else "basalt_l")
    h.mirror()
    hollow(h, keep=lambda X, Y, Z: (Z < -4) & (A(X) <= 4.5))
    return h


# ═══════════════════════════════ 공허 군주 ═══════════════════════════════

def helm_sovereign():
    M = {
        "hood": Mat(["#24103e", "#2e1650", "#3a1c62", "#482474"], "stone", seed=401),
        "hood_l": Mat(["#40205e", "#4e2876", "#5e3290", "#7040a6"], "stone", seed=402),
        "lining": Mat(["#07030e", "#0d0718", "#140c22", "#1c122e"], "stone", seed=403),
        "gold": Mat(["#7a5410", "#a87a1e", "#d4a432", "#f4d060"], "metal", seed=404),
        "crown": Mat(["#3a3448", "#4a4260", "#5e5478", "#7a6e94"], "metal", seed=405),
        "crown_k": Mat(["#0e0c14", "#16131e", "#1e1a28", "#282234"], "stone", seed=410),
        "crown_e": Mat(["#6e6290", "#8478a6", "#9a90bc", "#b8b0d4"], "metal", glow=True, seed=406),
        "gem": Mat(["#b060ff", "#c27cff", "#d49cff", "#ecd4ff"], "stone", glow=True, seed=407),
        "gem_hi": Mat(["#fbf0ff", "#ffffff", "#ffffff", "#ffffff"], "flat", glow=True, seed=411),
        "rune": Mat(["#8a2ad0", "#b04cf0", "#d48aff", "#f4e0ff"], "flow", glow=True, seed=408),
        "orb": Mat(["#b060ff", "#c47eff", "#dca8ff", "#fff0ff"], "pulse", glow=True, seed=409),
    }
    h = wkit.helmet(M, seed=41)

    # 두건: 머리를 감싸는 벽 (위쪽은 왕관 띠와 검은 바닥이 덮는다), 아래 단은 한 칸 벌어지고, 뒤는 목 아래(-4.5)까지
    def hood(X, Y, Z):
        m = sqr(X, Z, 5.5, 2) & (Y >= -3.5) & (Y <= 3.5)
        m |= ring(X, Z, 6.5, 3) & (Y == -3.5) & (Z > -4)                          # 아래 단 벌어짐 (옆, 뒤)
        m |= (A(X) <= 4.5) & (Z >= 3.5) & (Z <= 5.5) & (Y == -4.5)               # 뒤 자락
        return m & ~head(X, Y, Z) & ~((A(X) < 4) & (A(Z) < 4) & (Y < -4))
    h.fill(hood, "hood")
    # 뒤로 뾰족한 두건 끝: 왕관 띠 아래에서 한 겹 부풀고 가운데가 아래로 뾰족하게 내려온다
    for y, xw in ((2.5, 2.5), (1.5, 1.5), (0.5, 1.5), (-0.5, 0.5), (-1.5, 0.5)):
        vbox(h, -xw, xw, y, y, 6.5, 6.5, "hood")
    vbox(h, -0.5, 0.5, 1.5, 2.5, 7.5, 7.5, "hood")
    # 주름: 옆과 뒤에 세로 밝은 줄 (3칸마다)
    fold = lambda X, Y, Z: hood(X, Y, Z) & ~sqr(X, Z, 4.5, 2)
    h.fill(lambda X, Y, Z: fold(X, Y, Z) & (np.floor(X) % 3 == 0) & (Z > 4) & (A(X) >= 1.5), "hood_l")
    h.fill(lambda X, Y, Z: fold(X, Y, Z) & (np.floor(Z + 0.5) % 3 == 0) & (A(X) > 5) & (Z > -4), "hood_l")

    # 얼굴 구멍 (위가 뾰족한 아치) + 앞으로 튀어나온 두건 챙 + 금 테
    def hole(X, Y):
        return ((A(X) <= 3.5) & (Y <= 0.5)) | ((A(X) <= 2.5) & (Y == 1.5)) | ((A(X) <= 0.5) & (Y == 2.5))

    def near(X, Y, d=1):
        m = np.zeros_like(X, dtype=bool)
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                m |= hole(X + dx, Y + dy)
        return m & ~hole(X, Y)
    h.clear(lambda X, Y, Z: (Z <= -4.5) & hole(X, Y))
    h.fill(lambda X, Y, Z: (Z == -6.5) & (A(X) <= 5.5) & (Y >= -3.5) & (Y <= 3.5) & ~hole(X, Y)
           & ~((A(X) == 5.5) & (Y >= 2.5)), "hood")
    h.fill(lambda X, Y, Z: (Z >= -6.5) & (Z <= -4.5) & near(X, Y) & (Y >= -3.5), "lining")
    h.fill(lambda X, Y, Z: (Z == -7.5) & near(X, Y) & (Y >= -3.5) & ~((A(X) <= 3.5) & (Y < -3)), "gold")

    # 가시 왕관: 금 아래 테 + 강철 띠 두 줄, 안은 검은 바닥(머리 위를 덮음)
    band = lambda X, Z: ring(X, Z, 6.5, 1)
    h.fill(lambda X, Y, Z: band(X, Z) & (Y == 3.5), "gold")
    h.fill(lambda X, Y, Z: band(X, Z) & (Y >= 4.5) & (Y <= 5.5), "crown")
    h.fill(lambda X, Y, Z: sqr(X, Z, 5.5) & (Y == 4.5), "crown_k")

    # 가시 9개: 바깥 면은 밝은 강철 날, 속은 강철, 맨 끝 한 칸만 빛나는 보라
    def crown_t(t):
        return "crown" if t < 0.99 else "gem"
    edge = ("crown_e", 0.99)
    # 앞 가운데: 가장 높은 가시 (4 → 2 → 2x1, 9층)
    spike(h, 0.0, -6.5, 6.5, [(4, 2), (4, 2), (2, 2), (2, 2), (2, 2), (2, 1), (2, 1), (2, 1), (2, 1)],
          crown_t, (0.0, -0.05), edge=edge)
    spike(h, 4.0, -6.5, 6.5, [2, 2, 2, 2, 1, 1, 1], crown_t, (0.1, -0.12), edge=edge)
    spike(h, 6.5, -3.0, 6.5, [2, 2, 2, 1, 1, 1], crown_t, (0.15, 0.0), edge=edge)
    spike(h, 6.5, 2.0, 6.5, [2, 2, 2, 1, 1, 1], crown_t, (0.15, 0.0), edge=edge)
    spike(h, 3.0, 6.5, 6.5, [2, 2, 2, 1, 1], crown_t, (0.0, 0.12), edge=edge)
    # 이마 보석: 1칸 금 테 안의 빛나는 2x2 (두건 아치 끝 바로 위, 왕관 띠 앞)
    h.fill(lambda X, Y, Z: (Z == -7.5) & (A(X) <= 1.5) & (Y >= 3.5) & (Y <= 6.5)
           & ~((A(X) == 1.5) & ((Y == 3.5) | (Y == 6.5))), "gold")
    vbox(h, -0.5, 0.5, 4.5, 5.5, -8.5, -7.5, "gem")
    h.mirror()
    put(h, -0.5, 5.5, -8.5, "gem_hi")

    # 뒤의 룬 줄 (흐르는 빛): 두건 끝 가운데를 따라 아래로
    for y in (2.5, 1.5, 0.5, -0.5, -1.5, -2.5, -3.5, -4.5):
        if y % 3 == 0.5 - 0 and False:
            continue
        z = 7.5 if y >= 1.5 else 6.5 if y >= -1.5 else 5.5
        if int(math.floor(y)) % 3 != 0:
            put(h, 0.5, y, z, "rune")
            put(h, -0.5, y, z, "rune")
    # 떠 있는 보라 보석 (쌍뿔, 1-2-2-1 층, 비틀린 끝): 옆 둘은 왕관 띠 높이 바깥, 뒤 둘은 뒤 가시 위
    for x, y, z in ((12.0, 8.0, -2.0), (-12.0, 8.0, -2.0), (9.0, 12.0, 6.0), (-9.0, 12.0, 6.0)):
        bipyr(h, x, y, z, [1, 2, 2, 1], "orb")
    hollow(h, keep=lambda X, Y, Z: (Z < -4) & (A(X) <= 4.5))
    return h


# ═══════════════════════════════ 프리즘 ═══════════════════════════════

def helm_prism():
    M = {
        "pearl": Mat(["#c4bcd4", "#d8d2e6", "#eae6f4", "#fdfbff"], "sparkle", seed=501),
        "pearl_d": Mat(["#968eac", "#aaa2c0", "#bfb7d2", "#d4cde2"], "metal", seed=502),
        "gold": Mat(["#9a6a16", "#c49028", "#e8ba44", "#fce07c"], "metal", seed=503),
        "cr": Mat(["#d0c8ec", "#e0daf6", "#eeeaff", "#ffffff"], "crystal", glow=True, seed=504),
        "lil": Mat(["#9a86dc", "#ae9cea", "#c4b6f4", "#ddd4fc"], "crystal", seed=505),
        "lil_d": Mat(["#5e4aa8", "#6e5aba", "#806cca", "#9684d8"], "crystal", seed=506),
        "cy": Mat(["#78bfe8", "#92d0f2", "#b0e2fa", "#d6f4ff"], "crystal", seed=507),
        "cy_d": Mat(["#3c80b4", "#4a92c6", "#5ca6d6", "#74bae2"], "crystal", seed=508),
        "tip": Mat(["#f4f0ff", "#faf8ff", "#ffffff", "#ffffff"], "pulse", glow=True, seed=509),
        "rb": Mat(["#ffffff"] * 4, "rainbow", glow=True, seed=510),
    }
    h = wkit.helmet(M, seed=51)

    # 진주빛 투구: 정수리, 옆, 뒤, 얼굴은 열림
    def shell(X, Y, Z):
        return sqr(X, Z, 4.5) & (Y >= -3.5) & (Y <= 4.5) & ~head(X, Y, Z)
    h.fill(shell, "pearl")
    h.clear(lambda X, Y, Z: (Z == -4.5) & (A(X) <= 3.5) & (Y <= 0.5))
    h.clear(lambda X, Y, Z: (Z <= -2.5) & (A(X) == 4.5) & (Y <= -2.5))
    # 뒤통수 세로 무지개 줄 (금 테두리)
    h.fill(lambda X, Y, Z: (Z == 4.5) & (A(X) == 0.5) & (Y <= 0.5) & (Y >= -3.5), "rb")
    # 관자놀이: 진주 판 + 금 받침 (날개 뿌리)
    vbox(h, 6.5, 6.5, -0.5, 2.5, -1.5, 0.5, "gold")
    # 이마 띠: 금 + 무지개 줄 + 금, 위에 진주 받침
    band = lambda X, Z: ring(X, Z, 5.5, 1)
    h.fill(lambda X, Y, Z: band(X, Z) & (Y == 1.5), "gold")
    h.fill(lambda X, Y, Z: band(X, Z) & (Y == 2.5), "rb")
    h.fill(lambda X, Y, Z: band(X, Z) & (Y == 3.5), "gold")
    h.fill(lambda X, Y, Z: band(X, Z) & (Y == 4.5), "pearl_d")


    def facet(body, dark):
        """결정 한 층 (3톤): 한쪽 옆은 짙은 그늘, 반대쪽 옆은 흰 빛 모서리, 나머지는 몸 색, 끝은 빛."""
        def f(t, out, side, sx, sz):
            if t >= 0.85:
                return "tip"
            if side == -1:
                return dark
            if side == 1 and sx * sz > 1:
                return "cr"
            return body
        return f

    # 큰 결정 7개: 가운데 진주 결정(가장 높고, 앞면에 무지개 심, 후광 구멍을 지난다) + 앞 둘(연보라) + 옆 둘(하늘) + 뒤 둘(연보라)
    spike(h, 0.0, -1.0, 5.5, [(4, 4), (4, 4), (4, 3), (2, 2), (2, 2), (2, 2), (2, 1)],
          lambda t: "cr" if t < 0.85 else "tip", (0.0, 0.0))
    vbox(h, 1.5, 1.5, 5.5, 6.5, -2.5, 0.5, "lil")                  # 가운데 결정 옆 그늘 면
    vbox(h, 0.5, 0.5, 7.5, 10.5, -1.5, 0.5, "lil")
    vbox(h, -0.5, 0.5, 5.5, 6.5, -2.5, -2.5, "rb")                 # 앞면 무지개 심 (후광 아래로 이어지는 빛 기둥)
    vbox(h, -0.5, 0.5, 7.5, 10.5, -1.5, -1.5, "rb")
    big = [
        (3.5, -4.5, [3, 3, 3, 2, 2, 2, 1, 1], (0.35, -0.3), "lil", "lil_d"),
        (6.5, 0.5, [3, 3, 2, 2, 2, 1, 1], (0.45, 0.0), "cy", "cy_d"),
        (3.5, 4.5, [3, 3, 2, 2, 1, 1], (0.3, 0.35), "lil", "lil_d"),
    ]
    for cx, cz, sizes, lean, body, dark in big:
        spike(h, cx, cz, 5.5, sizes, lambda t, b=body: b if t < 0.85 else "tip", lean, cell=facet(body, dark))
    # 결정 날개: 관자놀이에서 뒤-위로 펼쳐지는 가는 깃 3장 (뿌리에서 하나로 이어진 부채): 짙은 하늘 → 하늘 → 빛나는 끝
    def wing(X, Y, Z):
        y, z = Y - 1.0, Z + 0.5
        m = np.zeros_like(X, dtype=bool)
        for ang, L, w in ((22, 7.0, 0.7), (60, 8.5, 0.8), (98, 6.5, 0.6)):
            a = math.radians(ang)
            d = (math.sin(a), math.cos(a))            # (z, y) 방향: 0도 = 위, 90도 = 뒤
            s = z * d[0] + y * d[1]
            p = -z * d[1] + y * d[0]
            m |= (s >= -0.5) & (s <= L) & (A(p) <= w * (1 - s / (L + 1.5)) + 0.5)
        return m & (Y >= -0.5)
    rr = lambda Y, Z: np.hypot(Y - 1.0, Z + 0.5)
    h.fill(lambda X, Y, Z: wing(X, Y, Z) & (X == 7.5) & (rr(Y, Z) <= 4.0), "cy_d")
    h.fill(lambda X, Y, Z: wing(X, Y, Z) & (X == 8.5) & (rr(Y, Z) >= 3.0), "cy")
    h.fill(lambda X, Y, Z: wing(X, Y, Z) & (X == 8.5) & (rr(Y, Z) >= 6.0), "tip")
    # 이마 보석 (무지개, 금 받침 1칸 테)
    h.fill(lambda X, Y, Z: (Z == -6.5) & (A(X) <= 1.5) & (Y >= 0.5) & (Y <= 4.5) & ~((A(X) == 1.5) & ((Y == 0.5) | (Y == 4.5))), "gold")
    vbox(h, -0.5, 0.5, 1.5, 3.5, -7.5, -7.5, "rb")
    h.mirror()
    # 떠 있는 무지개 후광 (계단식 둥근 고리), 가운데 결정이 구멍을 지난다
    h.fill(lambda X, Y, Z: (Y == 15.5 - 1) & (np.hypot(X, Z + 1.0) <= 5.0) & (np.hypot(X, Z + 1.0) >= 3.5), "rb")
    return h


HELMETS = {"frostlord": helm_frostlord, "inferno": helm_inferno, "sovereign": helm_sovereign, "prism": helm_prism}
FLOATERS = {"frostlord": ("spark",), "inferno": (), "sovereign": ("orb",), "prism": ("rb",)}


# ─────────────────────────── 미리보기 ───────────────────────────
# 복셀 격자를 그대로 그린다 (면 하나 = 큐브 한 면, 텍셀 한 개 = 그 면의 색).
# 마네킹 머리(스킨 8x8x8, 얼굴 -Z 에 눈)와 함께. night=True 면 조명은 어둡게, 빛나는 재료만 밝게.

_FACE_DIRS = {
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


def _quad(c, n):
    c = np.asarray(c, float)
    n = np.asarray(n, float)
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.5 else np.array([0, 1.0, 0])
    b = np.cross(n, a)
    o = c + n * 0.5
    return [o + (a * sa + b * sb) * 0.5 for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def vox_render(h, yaw=0.0, pitch=20.0, size=420, frame=0, bg=(28, 26, 36), fit=None, night=False):
    """yaw 0 = 얼굴(-Z) 정면. pitch 양수 = 위에서 내려다봄."""
    from PIL import Image, ImageDraw
    g = h.grid
    W, Hh, D = g.shape
    tabs = _texel_tables(h, frame)
    occ = g > 0
    X, Y, Z = h._X, h._Y, h._Z
    skin = head(X, Y, Z) & ~occ
    solid = occ | skin
    th, ph = math.radians(yaw), math.radians(pitch)
    f = np.array([math.sin(th) * math.cos(ph), -math.sin(ph), math.cos(th) * math.cos(ph)])
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
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
                if c[1] > 2.5:
                    col = np.array([70, 46, 28]) * (0.9 + k)
            else:
                tex, glow = tabs[g[x, y, z] - 1]
                if name in ("north", "south"):
                    tu, tv = x % 16, 15 - (y % 16)
                elif name in ("east", "west"):
                    tu, tv = z % 16, 15 - (y % 16)
                else:
                    tu, tv = x % 16, z % 16
                if name in ("north", "east"):
                    tu = 15 - tu
                col = tex[tv, tu, :3].astype(float)
            if not glow:
                col = col * lit * (0.28 if night else 1.0)
            pts = [(float(np.dot(q, r)), float(np.dot(q, u))) for q in _quad(c, n)]
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
         (150, 24, "뒤 3/4", 12, False), (-32, 20, "밤", 6, True))


def set_views(h, size=320):
    return [vox_render(h, yaw, pitch, size=size, frame=fr, night=nt) for yaw, pitch, _, fr, nt in VIEWS]


def _caption(text, width, font, height=28, bg=(44, 30, 30), fg=(255, 210, 160)):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (width, height), bg)
    f = ImageFont.truetype(font, 15) if font else ImageFont.load_default()
    ImageDraw.Draw(img).text((8, 5), text, font=f, fill=fg)
    return img


def main(only=None):
    from PIL import Image
    from mc3d import contact_sheet
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    font = FONT if os.path.exists(FONT) else None
    imgs, labels = [], []
    problems = {}
    for sid, fn in HELMETS.items():
        if only and sid not in only:
            continue
        h = fn()
        model = h.build(f"armor/{sid}_helmet", SCRATCH)
        n = len(model.elements)
        st = sum(1 for m in h.mats.values() if not m.animated)
        an = len(h.mats) - st
        print(f"{sid}: {n} elements, mats {st} static + {an} anim")
        problems[sid] = check(h, FLOATERS[sid], n)
        png = os.path.join(PREVIEW_DIR, f"helmet_{sid}.png")
        # 키트 미리보기: wkit.helmet_preview 는 yaw 155/110/25 를 '앞(얼굴)/옆/뒤' 로 적지만,
        # 실제로는 yaw 155 가 뒤(+Z), yaw 25 가 얼굴(-Z) 쪽이다 (wkit 라벨 버그). 순서를 바로잡고 다시 적는다.
        kv = wkit.helmet_preview(model, png)
        kit = contact_sheet([kv[2], kv[1], kv[0]], ["앞(얼굴, -Z)", "옆", "뒤(+Z)"], cols=3, cell=300, font=font)
        views = set_views(h, size=320)
        row = contact_sheet(views, [f"{NAMES_KO[sid]} {v[2]} · {n}" for v in VIEWS], cols=5, cell=320, font=font)
        cap1 = _caption(f"{NAMES_KO[sid]} ({sid}) — 복셀 렌더 (주 검토 이미지): 앞 3/4 · 정면 · 옆 · 뒤 3/4 · 밤   "
                        f"element {n}, 재료 {st}+{an}", row.width, font, bg=(30, 34, 50), fg=(220, 230, 255))
        cap2 = _caption("아래: 게임 모델 mc3d 원본 (참고용). wkit.helmet_preview 의 라벨 '앞(얼굴)'은 실제로 뒤쪽이라 순서를 바로잡음. "
                        "단순 깊이 정렬이라 머리 살갗/안쪽 면이 투구 위로 겹쳐 그려질 수 있음", row.width, font)
        out = Image.new("RGB", (row.width, cap1.height + row.height + cap2.height + kit.height), (18, 16, 26))
        y = 0
        for im in (cap1, row, cap2):
            out.paste(im, (0, y))
            y += im.height
        out.paste(kit, (0, y))
        out.save(png)
        for v, vv in zip(views, VIEWS):
            imgs.append(v)
            labels.append(f"{NAMES_KO[sid]} ({sid}) · {vv[2]} · {n}")
    if not only:
        contact_sheet(imgs, labels, cols=5, cell=320, font=font).save(os.path.join(PREVIEW_DIR, f"{MODULE}.png"))
    bad = {k: v for k, v in problems.items() if v}
    if bad:
        print("검사 실패:", bad)
    return problems


if __name__ == "__main__":
    main(sys.argv[1:] or None)
