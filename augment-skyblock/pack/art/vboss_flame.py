"""
vboss_flame: 화염 거신 (inferno_colossus) — 작은 정육면체(복셀)로 쌓은 보스.

떠다니는 용암 바위 거인. 1 복셀 = 1/8 블록 (part vox=1.0, rig scale 2.0).
  torso      가슴(현무암/흑요석 판 + 용암 균열) + 거대한 어깨 바위 + 가슴의 마그마 핵
  head       뿔 달린 머리, 타오르는 눈, 불꽃 볏
  tail       가슴 아래 매달린 바위 조각 꼬리 (윗마디)
  tail_low   꼬리 끝마디 (늦게 따라 흔들림)
  right_fist / left_fist   떠다니는 거대한 주먹 (손가락 사이 빛나는 균열)
  rock_a / rock_b          주위를 도는 불타는 바위 (world 프레임 orbit)

python3 vboss_flame.py   -> _scratch/vboss_flame/assets/augsky 에 짓고 preview/inferno_colossus_voxel*.png
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, part, rig_preview  # noqa: E402

BOSS = "inferno_colossus"
MODULE = "vboss_flame"
NAME_KO = "화염 거신"
FONT = "/tmp/claude-0/work/fonts/ng.ttf"

# ─────────────────────────── 재료 ───────────────────────────
# 현무암 3단(어두움/중간/밝음)은 판마다 달리 칠해 큰 면도 조각조각 보이게 한다.
PAL = {
    "bas0": Mat(["#141218", "#1f1c24", "#2c2832", "#3b3540"], "stone", seed=1),
    "bas1": Mat(["#25212a", "#332e38", "#453e4a", "#585060"], "stone", seed=2),
    "bas2": Mat(["#3a3238", "#4f4549", "#675a5c", "#82716c"], "stone", seed=3),
    "obs": Mat(["#0c0716", "#1a0f30", "#2d1a50", "#4a2f80"], "crystal", seed=4),
    "char": Mat(["#2a120e", "#401d16", "#5a2a1e", "#783a26"], "stone", seed=5),
    "hot": Mat(["#5c1a0a", "#8c2a0c", "#bb4410", "#e06a1a"], "stone", seed=6),
    "ember": Mat(["#b83206", "#ec5a0e", "#ff9424", "#ffc850"], "stone", glow=True, seed=7),
    "eye": Mat(["#ffc838", "#ffe27a", "#fff4be", "#ffffff"], "gem", glow=True, seed=8),
    "horn": Mat(["#1a1614", "#302a24", "#4c4236", "#6e6250"], "metal", seed=9),
    "hornT": Mat(["#8a2a0c", "#c24a14", "#f07a20", "#ffbc48"], "metal", glow=True, seed=10),
    "tooth": Mat(["#7c6c5a", "#9c8a74", "#bca88e", "#d8c8ac"], "stone", seed=11),
    # 움직이는 재료 (4개까지)
    "lava": Mat(["#a82806", "#e44c0c", "#ff8a20", "#ffd050"], "flow", glow=True, seed=12),
    "core": Mat(["#e04a08", "#ff9a1c", "#ffd858", "#fffbe0"], "fire", glow=True, seed=13),
    "magma": Mat(["#8c1c04", "#d4460c", "#ff8420", "#ffbe5a"], "pulse", glow=True, seed=14),
    "fire": Mat(["#c42c04", "#ff6a0a", "#ffb026", "#fff28a"], "fire", glow=True, seed=15),
}


def mats(*names):
    return {n: PAL[n] for n in names}


ROCK = ("bas0", "bas1", "bas2", "char")


# ─────────────────────────── 도구 ───────────────────────────

def hash3(X, Y, Z, seed=0, cell=1.0):
    """격자 칸(cell 복셀)마다 0..1 의 고정 난수."""
    xi = np.floor(np.asarray(X, float) / cell).astype(np.int64)
    yi = np.floor(np.asarray(Y, float) / cell).astype(np.int64)
    zi = np.floor(np.asarray(Z, float) / cell).astype(np.int64)
    v = (xi * 73856093) ^ (yi * 19349663) ^ (zi * 83492791) ^ (seed * 2654435761 + 12345)
    v = v & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    v = v ^ (v >> 16)
    return (v & 0xFFFF) / 65536.0


def erode(m):
    """6방향으로 한 겹 깎은 마스크."""
    e = m.copy()
    e[1:] &= m[:-1]
    e[:-1] &= m[1:]
    e[:, 1:] &= m[:, :-1]
    e[:, :-1] &= m[:, 1:]
    e[:, :, 1:] &= m[:, :, :-1]
    e[:, :, :-1] &= m[:, :, 1:]
    e[0], e[-1] = False, False
    e[:, 0], e[:, -1] = False, False
    e[:, :, 0], e[:, :, -1] = False, False
    return e


def dilate(m):
    d = m.copy()
    d[1:] |= m[:-1]
    d[:-1] |= m[1:]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    d[:, :, 1:] |= m[:, :, :-1]
    d[:, :, :-1] |= m[:, :, 1:]
    return d


def mid(w, name):
    return w.names.index(name) + 1


def plates(w, region, n, seed, mats_=ROCK, weights=None, crack=0.0, crack_w=0.8, crack_mat="lava", hot=0.4,
           keep=None):
    """
    region 안을 보로노이 판 n 개로 나누어 판마다 다른 돌 재료를 칠한다 (판은 3D 덩어리라 잘 합쳐진다).
    crack (0..1): 판 경계 중 용암 균열을 낼 비율 (겉면에만). hot: 균열 둘레 겉돌이 달아오르는 비율.
    keep: 칠하지 않을 마스크.
    """
    rng = np.random.default_rng(seed)
    idx = np.argwhere(region)
    if len(idx) == 0:
        return
    pts = idx[rng.choice(len(idx), size=min(n, len(idx)), replace=False)].astype(float)
    P = idx.astype(float)
    d = np.stack([np.sum((P - p) ** 2, axis=1) for p in pts], axis=1)
    order = np.argsort(d, axis=1)
    i1, i2 = order[:, 0], order[:, 1]
    d1 = np.sqrt(np.take_along_axis(d, order[:, :1], 1)[:, 0])
    d2 = np.sqrt(np.take_along_axis(d, order[:, 1:2], 1)[:, 0])
    wts = np.array(weights if weights else [1.0] * len(mats_), float)
    wts /= wts.sum()
    choice = rng.choice(len(mats_), size=len(pts), p=wts)
    ids = np.array([mid(w, m) for m in mats_])
    paint = np.ones(len(idx), bool) if keep is None else ~keep[tuple(idx.T)]
    w.grid[tuple(idx[paint].T)] = ids[choice[i1[paint]]]
    if crack <= 0:
        return
    a, b = np.minimum(i1, i2), np.maximum(i1, i2)
    pair_on = hash3(a, b, 0, seed + 77) < crack
    is_c = (d2 - d1 < crack_w) & pair_on & paint
    cm = np.zeros(w.grid.shape, bool)
    cm[tuple(idx[is_c].T)] = True
    filled = w.grid > 0
    s1 = filled & ~erode(filled)
    w.grid[cm & s1] = mid(w, crack_mat)
    if hot:
        near = dilate(cm & s1) & ~cm & s1 & np.isin(w.grid, ids)
        if keep is not None:
            near &= ~keep
        w.grid[near & (hash3(w._X, w._Y, w._Z, seed + 5) < hot)] = mid(w, "hot")


def jag(w, mask, p, seed, cell=2.0):
    """mask 의 겉 한 겹에서 cell 크기 덩어리 단위로 일부를 떼어 낸다 (울퉁불퉁 계단진 윤곽)."""
    filled = w.grid > 0
    s1 = filled & ~erode(filled) & mask
    h = hash3(w._X + 0.5, w._Y + 0.5, w._Z + 0.5, seed, cell)
    w.grid[s1 & (h < p)] = 0


def zigzag(pts, seed, jitter=1.0):
    """2D 점들을 잇는 계단진 번개 선 → 칸 좌표(복셀 가운데) 목록. 4방향으로만 움직여 끊기지 않는다."""
    rng = np.random.default_rng(seed)
    cells = []
    x, y = math.floor(pts[0][0]) + 0.5, math.floor(pts[0][1]) + 0.5
    cells.append((x, y))
    for (tx, ty) in pts[1:]:
        tx, ty = math.floor(tx) + 0.5, math.floor(ty) + 0.5
        guard = 0
        while (x, y) != (tx, ty) and guard < 400:
            guard += 1
            dx, dy = tx - x, ty - y
            # 큰 쪽으로 가되 가끔 엇나가 번개처럼
            if abs(dx) > 0 and (abs(dx) >= abs(dy) or rng.random() < 0.3 * jitter) and not (dy and rng.random() < 0.25 * jitter):
                x += np.sign(dx)
            elif dy:
                y += np.sign(dy)
            else:
                x += np.sign(dx)
            cells.append((x, y))
    return cells


def project(w, cells, axis, sign, mat, depth=1, only=None, start=0):
    """
    2D 칸들을 겉면에 칠한다 (데칼처럼). axis 'z' 면 (X, Y) 칸을 +Z(sign=1) 또는 -Z 쪽에서 본 첫 복셀부터 depth 겹.
    'x' 면 (Z, Y) 칸, 'y' 면 (X, Z) 칸. only: 이 재료 번호들 위에만. start: 겉에서 몇 겹 안쪽부터.
    """
    g = w.grid
    ax = {"x": 0, "y": 1, "z": 2}[axis]
    m_id = mid(w, mat)
    for (a, b) in cells:
        if axis == "z":
            i, j = int(round(a - 0.5 + w.CX)), int(round(b - 0.5 + w.CY))
            if not (0 <= i < w.W and 0 <= j < w.H):
                continue
            col = g[i, j, :]
        elif axis == "x":
            k, j = int(round(a - 0.5 + w.CZ)), int(round(b - 0.5 + w.CY))
            if not (0 <= k < w.D and 0 <= j < w.H):
                continue
            col = g[:, j, k]
        else:
            i, k = int(round(a - 0.5 + w.CX)), int(round(b - 0.5 + w.CZ))
            if not (0 <= i < w.W and 0 <= k < w.D):
                continue
            col = g[i, :, k]
        nz = np.nonzero(col)[0]
        if len(nz) == 0:
            continue
        first = nz[-1] if sign > 0 else nz[0]
        for dd in range(start, start + depth):
            p = first - dd if sign > 0 else first + dd
            if 0 <= p < len(col) and col[p] and (only is None or col[p] in only):
                col[p] = m_id


def ring_hot(w, mat_from, prob, seed):
    """mat_from(용암 등) 둘레 겉돌 일부를 달아오른 돌로."""
    src = w.grid == mid(w, mat_from)
    filled = w.grid > 0
    s1 = filled & ~erode(filled)
    rock = np.isin(w.grid, [mid(w, m) for m in ROCK if m in w.names])
    near = dilate(src) & s1 & rock
    w.grid[near & (hash3(w._X, w._Y, w._Z, seed) < prob)] = mid(w, "hot")


def count(model):
    return len(model.elements)


# ─────────────────────────── 몸통 ───────────────────────────

def build_torso(root):
    w = part(mats("bas0", "bas1", "bas2", "obs", "char", "hot", "ember", "hornT",
                  "lava", "core", "magma"), size=48)
    X, Y, Z = w._X, w._Y, w._Z
    # 가슴: 위가 넓은 통, 모서리를 깎는다
    hw = 7.0 + np.clip(Y + 8, 0, 17) * 0.27
    hd_f, hd_b = 6.0, 5.5
    chest = (Y >= -8) & (Y <= 9) & (np.abs(X) <= hw) & (Z <= hd_f) & (Z >= -hd_b) \
        & (np.abs(X) - hw + np.maximum(Z - hd_f, -Z - hd_b) + 2.5 <= 0)
    # 가슴 근육판 두 장 (가운데 홈)
    pec = (np.abs(X) >= 1) & (np.abs(X) <= 10) & (Y >= 2) & (Y <= 8) & (Z <= 7.5) & (Z >= 0) \
        & ((np.abs(X) - 10) + (Z - 7.5) + 1.5 <= 0) & ((Y - 8) + (Z - 7.5) + 1.5 <= 0)
    # 복근판 세 장
    abs_ = np.zeros_like(chest)
    for (y0, y1) in ((-1.0, 1.5), (-4.5, -2.0), (-7.5, -5.5)):
        abs_ |= (np.abs(X) >= 1) & (np.abs(X) <= 6.0) & (Y >= y0) & (Y <= y1) & (Z <= 7.0) & (Z >= 0)
    # 배 아래 바위 마디 (사이에 용암)
    belly = np.zeros_like(chest)
    for (y0, y1, r, rz) in ((-11.0, -8.5, 6.2, 4.8), (-14.5, -12.5, 4.6, 3.8)):
        belly |= (Y >= y0) & (Y <= y1) & ((X / r) ** 2 + (Z / rz) ** 2 <= 1.0)
    body = chest | pec | abs_ | belly
    w.fill(lambda X, Y, Z: body, "bas1")
    plates(w, body & (Y > -8.5), 14, 21, weights=[3, 5, 3, 1.5], crack=0.25)
    w.fill(lambda X, Y, Z: pec, "bas2")
    plates(w, pec, 4, 24, mats_=("bas1", "bas2"), weights=[1, 2])
    w.fill(lambda X, Y, Z: abs_, "bas1")
    plates(w, belly, 4, 23, weights=[2, 3, 1, 2])
    w.fill(lambda X, Y, Z: (Y >= -12.6) & (Y <= -7.6) & ((X / 4.0) ** 2 + (Z / 3.0) ** 2 <= 1) & ~body, "lava")

    # 어깨 바위
    sh = np.zeros_like(body)
    for s in (1, -1):
        sh |= ((X - s * 15) / 8.5) ** 2 + ((Y - 6.5) / 7.0) ** 2 + (Z / 8.0) ** 2 <= 1
        sh |= ((X - s * 18.5) / 5.0) ** 2 + ((Y - 1.0) / 5.0) ** 2 + ((Z - 0.5) / 6.5) ** 2 <= 1
        sh |= ((X - s * 12.5) / 6.5) ** 2 + ((Y - 11.5) / 3.5) ** 2 + ((Z + 0.5) / 6.5) ** 2 <= 1
    sh &= ~(np.abs(X) < 7)
    w.fill(lambda X, Y, Z: sh, "bas1")
    jag(w, sh, 0.18, 11, 2.0)
    plates(w, sh & (w.grid > 0), 14, 22, weights=[3, 4, 3, 1.5], crack=0.3)
    # 어깨 앞판: 큰 판 하나가 앞으로 (갑옷처럼 겹친 바위)
    for s in (1, -1):
        pad = (np.abs(X - s * 15) <= 6.5) & (Y >= 3) & (Y <= 10.5) & (Z >= 5) & (Z <= 8.5) \
            & (((X - s * 15) / 8.0) ** 2 + ((Y - 6.5) / 6.5) ** 2 + (Z / 9.0) ** 2 <= 1)
        w.fill(lambda X, Y, Z, pad=pad: pad, "bas2")
    # 용암 줄기 (번개처럼 계단진 선): 핵에서 어깨로, 배로, 어깨 위로
    cy = 1.5
    for s in (1, -1):
        for k, pts in enumerate(([(s * 6, cy + 5), (s * 9, cy + 7.5), (s * 13, cy + 7), (s * 18, cy + 9)],
                                 [(s * 6, cy - 5), (s * 7, cy - 8), (s * 5, cy - 11)],
                                 [(s * 11, cy - 1), (s * 15, cy + 1), (s * 19, cy - 1)])):
            project(w, zigzag(pts, 300 + k + (s > 0) * 10), "z", 1, "lava")
        # 어깨 위에서 본 선
        project(w, zigzag([(s * 9, -4), (s * 13, 0), (s * 15, 3), (s * 20, 4)], 330 + (s > 0)), "y", 1, "lava")
        # 바깥 옆면
        project(w, zigzag([(-5, 10), (-1, 6), (2, 3), (5, -2)], 340 + (s > 0)), "x", s, "lava")
    # 등: 척추를 따라 내려오는 선
    project(w, zigzag([(0, 10), (1, 4), (-1, -2), (0, -8)], 350), "z", -1, "lava")
    ring_hot(w, "lava", 0.35, 360)

    # 가슴 마그마 핵: 다이아몬드 구멍 + 흑요석 테 + 빛나는 핵
    diamond = np.abs(X) + np.abs(Y - cy)
    w.clear(lambda X, Y, Z: (diamond <= 6.0) & (Z >= 1))
    w.fill(lambda X, Y, Z: (diamond > 6.0) & (diamond <= 8.0) & (Z >= 3) & (Z <= 8.0), "obs")
    w.fill(lambda X, Y, Z: (diamond > 5.0) & (diamond <= 6.0) & (Z >= 1) & (Z <= 5), "hot")
    w.fill(lambda X, Y, Z: (diamond <= 5.0) & (Z <= 3.0) & (Z >= -1), "magma")
    w.fill(lambda X, Y, Z: (X / 4.0) ** 2 + ((Y - cy) / 4.0) ** 2 + ((Z - 3.0) / 3.2) ** 2 <= 1, "core")
    # 테의 네 꼭짓점에 흑요석 송곳
    for (dx, dy) in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        w.tube([(dx * 7.5, cy + dy * 7.5, 6), (dx * 10, cy + dy * 10, 7.5)], lambda t: 1.5 * (1 - 0.6 * t), "obs")

    # 어깨 위 흑요석 결정 (끝은 달아오름)
    for s in (1, -1):
        for (bx, by, bz, tx, ty, tz, r0) in ((13, 12, 0, 14, 20, -1, 2.6), (17.5, 10, -2, 22.5, 16, -3, 2.1),
                                             (10, 13.5, -3, 9, 18.5, -5, 1.8), (20, 6, 2, 23.5, 9, 2.5, 1.6)):
            w.tube([(s * bx, by, bz), (s * tx, ty, tz)], lambda t, r0=r0: r0 * (1 - 0.6 * t), "obs")
            f = 0.78
            w.tube([(s * (bx + (tx - bx) * f), by + (ty - by) * f, bz + (tz - bz) * f), (s * tx, ty, tz)], 0.8, "hornT")
    # 등줄기 흑요석 가시
    for i, y in enumerate((8, 3, -2)):
        w.tube([(0, y, -5), (0, y + 3, -9.5 + i * 0.7)], lambda t: 2.0 * (1 - 0.6 * t), "obs")
    # 목 자리
    w.clear(lambda X, Y, Z: (np.abs(X) <= 4.5) & (Y >= 8.0) & (Z >= -3.5) & (Z <= 5))
    w.fill(lambda X, Y, Z: (np.abs(X) <= 4.0) & (Y >= 7.0) & (Y <= 8.0) & (Z >= -3) & (Z <= 4), "magma")
    w.mirror()
    return w.build(f"boss/{BOSS}_torso", root)


# ─────────────────────────── 머리 ───────────────────────────

def build_head(root):
    w = part(mats("bas0", "bas1", "bas2", "obs", "char", "hot", "ember", "eye", "horn", "hornT", "tooth",
                  "lava", "fire", "magma"), size=48)
    X, Y, Z = w._X, w._Y, w._Z
    w.fill(lambda X, Y, Z: (np.abs(X) <= 3.5) & (Y >= -1) & (Y <= 2) & (np.abs(Z) <= 3.5), "bas0")
    hw = 7.0 - np.clip(Y - 9, 0, None) * 0.8
    skull = (Y >= 1) & (Y <= 12) & (np.abs(X) <= hw) & (Z >= -6) & (Z <= 6) \
        & (np.abs(X) - hw + np.abs(Z) - 6 + 2 <= 0) & ((Y - 12) + np.abs(Z) - 6 + 2 <= 0)
    jaw = (Y >= 0) & (Y <= 4.5) & (np.abs(X) <= 6.2) & (Z >= -3) & (Z <= 7.5) & (np.abs(X) - 6.2 + (Z - 7.5) + 2 <= 0)
    w.fill(lambda X, Y, Z: skull, "bas1")
    plates(w, skull, 8, 31, weights=[2, 4, 3, 1], crack=0.3)
    w.fill(lambda X, Y, Z: jaw, "bas0")
    plates(w, jaw, 3, 32, mats_=("bas0", "bas1", "char"), weights=[3, 2, 1])
    # 눈썹뼈: 화난 V 자 (가운데가 낮다), 앞으로 툭 튀어나옴
    brow_top = 9.5 - np.clip(3.5 - np.abs(X), 0, None) * 0.6
    brow = (Y >= brow_top - 2.2) & (Y <= brow_top) & (np.abs(X) <= 7.2) & (Z >= 3) & (Z <= 8.0) & (np.abs(X) - 7.2 + (Z - 8) + 1.5 <= 0)
    w.fill(lambda X, Y, Z: brow, "bas2")
    plates(w, brow, 3, 33, mats_=("bas2", "bas1"), weights=[3, 1])
    # 눈: 눈썹 아래 굴에서 타오른다 (뒤로 한 칸 들어가고, 둘레는 달아오름)
    eyes = (np.abs(X) >= 1.5) & (np.abs(X) <= 5.5) & (Y >= 5) & (Y <= 6.5 + (np.abs(X) - 1.5) * 0.25) & (Z >= 3.5)
    w.clear(lambda X, Y, Z: eyes & (Z > 5))
    w.fill(lambda X, Y, Z: eyes & (Z <= 5) & (Z > 3), "eye")
    w.fill(lambda X, Y, Z: (np.abs(X) >= 1.0) & (np.abs(X) <= 6.0) & (np.abs(Y - 4.5) < 0.5) & (Z >= 5) & (Z <= 6)
           & (w.grid > 0), "hot")
    # 눈꼬리에서 뺨으로 흘러내리는 용암 눈물
    for s in (1, -1):
        project(w, zigzag([(s * 5.5, 4.5), (s * 6, 2.5), (s * 5, 0.5)], 400 + (s > 0), 0.6), "z", 1, "lava")
        project(w, zigzag([(5.5, 5), (2, 3.5), (0, 1), (-2, 0)], 410 + (s > 0)), "x", s, "lava")
    # 입: 용암 빛 틈 + 이빨
    w.clear(lambda X, Y, Z: (np.abs(X) <= 4.0) & (Y >= 1.5) & (Y <= 3.0) & (Z >= 5.5))
    w.fill(lambda X, Y, Z: (np.abs(X) <= 4.0) & (Y >= 1.5) & (Y <= 3.0) & (Z >= 4.5) & (Z <= 5.5), "magma")
    for x in (0.5, 2.5):
        w.box(x, x, 2.5, 3.0, 5.5, 6.5, "tooth")
    w.box(3.5, 3.5, 1.5, 2.0, 5.5, 6.5, "tooth")
    w.box(1.5, 1.5, 1.5, 2.0, 5.5, 6.5, "tooth")
    # 뿔: 옆으로 나와 위로, 끝은 살짝 앞으로. 굵은 마디 고리
    for s in (1, -1):
        horn = [(s * 6, 9.5, 0), (s * 10.5, 10.5, -0.5), (s * 13.5, 13.5, -1.0), (s * 14, 18, -0.5), (s * 12.5, 22, 1.0)]
        w.tube(horn, lambda t: 2.8 * (1 - 0.65 * t), "horn")
        for p, r in ((horn[1], 2.9), (horn[2], 2.5)):
            w.fill(lambda X, Y, Z, p=p, r=r: ((X - p[0]) ** 2 + (Y - p[1]) ** 2 + (Z - p[2]) ** 2 <= r ** 2)
                   & (w.grid > 0) & (np.abs(Y - p[1]) <= 0.6), "obs")
        w.tube(horn[3:], lambda t: 1.4 * (1 - 0.45 * t), "hornT")
    # 불꽃 볏: 톱니 흑요석 볏 + 그 위로 타오르는 불꽃 혀
    saw = 13 + (np.floor((Z + 7) / 2) % 2) * 1.0 - np.abs(Z + 1) * 0.15
    w.fill(lambda X, Y, Z: (np.abs(X) <= 1.5) & (Y >= 10) & (Y <= saw) & (Z >= -7) & (Z <= 4), "obs")
    for (z, h, lean) in ((3.0, 3.5, -0.5), (1.0, 5.5, -1.0), (-1.5, 7.0, -1.5), (-4.0, 6.0, -2.0), (-6.5, 4.0, -2.0)):
        base = 13.5
        w.tube([(0, base, z), (0, base + h * 0.55, z + lean * 0.5), (0, base + h, z + lean)],
               lambda t: 1.6 * (1 - 0.65 * t), "fire")
    w.mirror()
    return w.build(f"boss/{BOSS}_head", root)


# ─────────────────────────── 주먹 ───────────────────────────

def build_fist(root, side):
    """side=+1 왼주먹(+X 쪽), -1 오른주먹(-X 쪽). 엄지는 몸 쪽(-side). 피벗 = 손목 위."""
    w = part(mats("bas0", "bas1", "bas2", "obs", "char", "hot", "ember", "hornT", "lava", "magma"), size=40)
    X, Y, Z = w._X, w._Y, w._Z
    inner = -side
    cy = -10.0
    Xs = X * side          # 엄지 쪽이 Xs<0
    # 손등/손바닥 덩어리 (손가락 뒤)
    hand = (Xs >= -7) & (Xs <= 8) & (Y >= cy - 5) & (Y <= cy + 5) & (Z >= -5) & (Z <= 3) \
        & (np.abs(Xs - 0.5) - 7.5 + np.abs(Z + 1) - 4 + 2 <= 0)
    w.fill(lambda X, Y, Z: hand, "bas1")
    plates(w, hand, 6, 41 + side, weights=[2, 4, 2, 1], crack=0.4)
    # 손가락 4개: 3칸 폭, 사이 1칸 틈. 위 마디(밝음)와 아래 마디(중간), 접힌 금(어두움)
    fingers = np.zeros(w.grid.shape, bool)
    for i in range(4):
        x0 = -7 + i * 4 + (1 if i == 0 else 0)
        x1 = x0 + 3 - (1 if i == 0 else 0)
        top = cy + 5 + (1 if i in (1, 2) else 0)
        f = (Xs >= x0) & (Xs <= x1) & (Y >= cy - 5) & (Y <= top) & (Z > 3) & (Z <= 7.5)
        f &= ~((Y > top - 1) & (Z > 6.5))          # 마디 모서리 둥글게
        f &= ~((Y < cy - 4) & (Z > 6.5))
        fingers |= f
        w.fill(lambda X, Y, Z, f=f: f & (Y > cy + 0.5), "bas2")
        w.fill(lambda X, Y, Z, f=f: f & (Y <= cy + 0.5), "bas1")
        w.fill(lambda X, Y, Z, f=f: f & (np.abs(Y - (cy + 0.5)) < 0.5) & (Z > 6.5), "bas0")
        # 마디 위 빛나는 금 (주먹마다 조금씩 다른 자리)
        kx = x0 + 1 + (i % 2)
        w.fill(lambda X, Y, Z, f=f, kx=kx: f & (np.abs(Xs - kx) < 0.6) & (Y > cy + 2) & (Z > 6.5), "ember")
        w.fill(lambda X, Y, Z, f=f, kx=kx: f & (np.abs(Xs - kx) < 0.6) & (Y > top - 1) & (Z > 4), "ember")
    # 손가락 사이 틈 깊은 곳 = 용암
    w.fill(lambda X, Y, Z: (Xs >= -6) & (Xs <= 8) & (Y >= cy - 4) & (Y <= cy + 4) & (Z > 3) & (Z <= 4) & ~fingers, "lava")
    # 엄지: 몸 쪽 옆에서 앞으로 감싼다
    thumb = [(inner * 7.5, cy - 0.5, -1.5), (inner * 8.5, cy - 2.0, 3.0), (inner * 6.0, cy - 3.0, 7.0)]
    w.tube(thumb, lambda t: 2.2 * (1 - 0.15 * t), "bas2")
    w.fill(lambda X, Y, Z: (np.abs(X - inner * 8.6) < 1.2) & (np.abs(Y - (cy - 1.5)) < 0.6) & (np.abs(Z - 1.5) < 2.2)
           & (w.grid > 0), "ember")
    # 손목 띠 (흑요석) + 가시 4개
    w.fill(lambda X, Y, Z: (Y >= cy + 5) & (Y <= cy + 8) & ((X / 7.4) ** 2 + ((Z + 1) / 5.8) ** 2 <= 1), "obs")
    w.fill(lambda X, Y, Z: (Y >= cy + 6) & (Y <= cy + 7) & ((X / 8.2) ** 2 + ((Z + 1) / 6.6) ** 2 <= 1), "obs")
    for a in (45, 135, 225, 315):
        r = math.radians(a)
        w.tube([(6.5 * math.cos(r), cy + 6.5, -1 + 5.0 * math.sin(r)),
                (10.0 * math.cos(r), cy + 9.0, -1 + 8.0 * math.sin(r))], lambda t: 1.5 * (1 - 0.6 * t), "obs")
        w.tube([(9.2 * math.cos(r), cy + 8.5, -1 + 7.4 * math.sin(r)),
                (10.0 * math.cos(r), cy + 9.0, -1 + 8.0 * math.sin(r))], 0.75, "hornT")
    # 부러진 손목 그루터기: 위가 녹아 끓는다
    w.fill(lambda X, Y, Z: (Y > cy + 8) & (Y <= cy + 10) & ((X / 5.2) ** 2 + ((Z + 1) / 4.4) ** 2 <= 1), "char")
    w.fill(lambda X, Y, Z: (Y > cy + 9) & (Y <= cy + 10) & ((X / 3.6) ** 2 + ((Z + 1) / 3.0) ** 2 <= 1), "magma")
    jag(w, (Y > cy + 8) & (w.grid == mid(w, "char")), 0.35, 70 + side, 1.0)
    # 손목 위에 떠 있는 팔뚝 조각 둘
    w.fill(lambda X, Y, Z: (Y >= cy + 12) & (Y <= cy + 14) & ((X / 4.2) ** 2 + ((Z + 1) / 3.6) ** 2 <= 1), "bas1")
    w.fill(lambda X, Y, Z: (Y >= cy + 12) & (Y < cy + 13) & ((X / 2.6) ** 2 + ((Z + 1) / 2.0) ** 2 <= 1), "lava")
    w.fill(lambda X, Y, Z: (Y >= cy + 16) & (Y <= cy + 17) & ((X / 2.6) ** 2 + ((Z + 1) / 2.4) ** 2 <= 1), "char")
    jag(w, (Y >= cy + 12), 0.3, 80 + side, 1.0)
    ring_hot(w, "lava", 0.4, 90 + side)
    return w.build(f"boss/{BOSS}_{'left' if side > 0 else 'right'}_fist", root)


# ─────────────────────────── 꼬리 ───────────────────────────

def build_tail(root, low=False):
    w = part(mats("bas0", "bas1", "bas2", "obs", "char", "hot", "ember", "hornT", "lava", "magma"), size=32)
    X, Y, Z = w._X, w._Y, w._Z
    if not low:
        segs = ((-0.5, -4.0, 5.2, 4.2, -0.3), (-5.5, -8.0, 4.0, 3.4, -1.0), (-9.5, -11.5, 2.9, 2.6, -1.8))
        spine = [(0, 0.5, 0), (0, -6, -0.8), (0, -11.5, -1.8)]
    else:
        segs = ((-1, -3.5, 2.6, 2.3, -0.3), (-5, -6.5, 1.9, 1.8, -0.9), (-8, -9, 1.2, 1.2, -1.5))
        spine = [(0, 0.5, 0), (0, -8.5, -1.5)]
    w.tube(spine, 1.3 if not low else 0.9, "lava")
    for k, (y0, y1, r, rz, zc) in enumerate(segs):
        t = np.clip((y0 - Y) / max(0.5, y0 - y1), 0, 1)
        seg = (Y <= y0) & (Y >= y1) & ((X / (r * (1 - 0.25 * t))) ** 2 + ((Z - zc) / (rz * (1 - 0.25 * t))) ** 2 <= 1)
        w.fill(lambda X, Y, Z, seg=seg: seg, "bas1")
    jag(w, w.grid > 0, 0.22, 90 + low, 1.0)
    plates(w, (w.grid > 0) & (w.grid != mid(w, "lava")), 5, 91 + low, weights=[3, 3, 2, 2], crack=0.3)
    for (y0, y1, r, rz, zc) in segs:
        w.fill(lambda X, Y, Z, y1=y1, zc=zc, r=r, rz=rz: (np.abs(Y - y1) < 0.6) & (w.grid > 0)
               & (hash3(X, Y, Z, 99, 1) < 0.6) & ((X / r) ** 2 + ((Z - zc) / rz) ** 2 > 0.3), "hot")
    if not low:
        for s in (1, -1):
            w.tube([(s * 4, -1.5, 0.5), (s * 7, -3.5, 1.0)], lambda t: 1.4 * (1 - 0.55 * t), "obs")
            w.tube([(s * 6.4, -3.2, 0.9), (s * 7, -3.5, 1.0)], 0.7, "hornT")
    else:
        w.tube([(0, -9, -1.6), (0, -11.5, -2.3)], lambda t: 1.0 * (1 - 0.4 * t), "magma")
    return w.build(f"boss/{BOSS}_{'tail_low' if low else 'tail'}", root)


# ─────────────────────────── 도는 바위 ───────────────────────────

def build_rock(root, kind):
    w = part(mats("bas0", "bas1", "bas2", "obs", "char", "hot", "ember", "hornT", "lava", "fire", "magma"),
             size=24)
    X, Y, Z = w._X, w._Y, w._Z
    if kind == "a":
        # 불타는 현무암 덩어리: 위에서 불꽃
        w.fill(lambda X, Y, Z: (X / 4.6) ** 2 + ((Y + 0.5) / 3.8) ** 2 + (Z / 4.2) ** 2 <= 1, "bas1")
        jag(w, w.grid > 0, 0.3, 101, 1.0)
        plates(w, w.grid > 0, 5, 102, weights=[2, 3, 2, 2], crack=0.6, hot=0.5)
        w.fill(lambda X, Y, Z: ((X / 2.6) ** 2 + (Z / 2.4) ** 2 <= 1) & (Y >= 2.0) & (Y <= 3.0), "magma")
        for (x, z, h) in ((0, 0, 5.0), (1.8, 1.0, 3.0), (-1.6, -1.0, 3.5)):
            w.tube([(x, 3, z), (x * 0.8, 3 + h * 0.6, z * 0.8), (x * 0.5 + 0.5, 3 + h, z * 0.5)],
                   lambda t: 1.3 * (1 - 0.6 * t), "fire")
    else:
        # 흑요석 결정 덩어리: 빛나는 금이 간 뾰족한 파편
        w.tube([(0, -3.5, 0), (0, 5.0, 0)], lambda t: 2.7 * (1 - 0.75 * t), "obs")
        w.tube([(0, -1, 0), (3.8, -3.8, 1.5)], lambda t: 1.8 * (1 - 0.6 * t), "obs")
        w.tube([(0, -1, 0), (-3.4, -3.0, -2.0)], lambda t: 1.6 * (1 - 0.6 * t), "obs")
        w.fill(lambda X, Y, Z: (X / 3.2) ** 2 + ((Y + 3.5) / 2.0) ** 2 + (Z / 3.0) ** 2 <= 1, "char")
        project(w, zigzag([(0.5, -2), (1, 1), (0, 3.5)], 120), "z", 1, "lava")
        project(w, zigzag([(-0.5, -2), (-1, 1), (0, 3)], 121), "z", -1, "lava")
        w.tube([(0, 4.0, 0), (0, 5.5, 0)], 0.8, "hornT")
        w.fill(lambda X, Y, Z: (Y <= -5.0) & (Y >= -6.0) & (X ** 2 + Z ** 2 <= 3.0), "magma")
    return w.build(f"boss/{BOSS}_rock_{kind}", root)


# ─────────────────────────── 깊이 버퍼 미리보기 ───────────────────────────
# mc3d.render 는 면을 평균 깊이로만 정렬해서 긴 면이 앞의 작은 면을 덮는 일이 있다.
# 복셀 모양을 정확히 보려고 픽셀마다 깊이를 비교하는 렌더러를 하나 더 둔다 (같은 정사영, 같은 면 밝기).

def zrender(parts, size=512, yaw=-35, pitch=25, bg=(28, 26, 36, 255), pad=0.08, ss=2):
    from mc3d import _face_corners, _rot_matrix, FACE_LIGHT
    from PIL import Image
    view = _rot_matrix("x", pitch) @ _rot_matrix("y", yaw)
    quads = []
    for model, M in parts:
        M = np.eye(4) if M is None else np.array(M, float)
        texs = {k: np.array(a.frame0().convert("RGBA")) for k, a in model.atlases.items()}
        for el in model.elements:
            cf = _face_corners(el["from"], el["to"])
            glow_el = el.get("light_emission", 0) >= 8
            for fname, fd in el["faces"].items():
                tex = texs.get(fd["texture"].lstrip("#"))
                if tex is None:
                    continue
                P = (np.array(cf[fname], float) - 8.0) / 16.0
                P = (M[:3, :3] @ P.T).T + M[:3, 3]
                P = (view @ P.T).T
                n = np.cross(P[1] - P[0], P[3] - P[0])
                if n[2] >= 0:
                    continue
                quads.append((P, tex, fd["uv"], 1.0 if glow_el else FACE_LIGHT[fname]))
    if not quads:
        return Image.new("RGBA", (size, size), bg)
    allp = np.concatenate([q[0] for q in quads])
    lo, hi = allp.min(0), allp.max(0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1
    S = size * ss
    sc = S * (1 - 2 * pad) / span
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    img = np.zeros((S, S, 3), float)
    img[:] = bg[:3]
    zb = np.full((S, S), np.inf)
    for P, tex, uv, light in quads:
        sx = (P[:, 0] - cx) * sc + S / 2
        sy = -(P[:, 1] - cy) * sc + S / 2
        x0, x1 = int(max(0, np.floor(sx.min()))), int(min(S, np.ceil(sx.max()) + 1))
        y0, y1 = int(max(0, np.floor(sy.min()))), int(min(S, np.ceil(sy.max()) + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        e1 = np.array([sx[1] - sx[0], sy[1] - sy[0]])
        e3 = np.array([sx[3] - sx[0], sy[3] - sy[0]])
        det = e1[0] * e3[1] - e1[1] * e3[0]
        if abs(det) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        dx, dy = gx - sx[0], gy - sy[0]
        s = (dx * e3[1] - dy * e3[0]) / det
        t = (e1[0] * dy - e1[1] * dx) / det
        inside = (s >= 0) & (s < 1) & (t >= 0) & (t < 1)
        if not inside.any():
            continue
        z = P[0, 2] + s * (P[1, 2] - P[0, 2]) + t * (P[3, 2] - P[0, 2])
        th, tw = tex.shape[:2]
        u = (uv[0] + s * (uv[2] - uv[0])) / 16.0 * tw
        v = (uv[1] + t * (uv[3] - uv[1])) / 16.0 * th
        ui = np.clip(np.floor(u).astype(int), 0, tw - 1)
        vi = np.clip(np.floor(v).astype(int), 0, th - 1)
        px = tex[vi, ui]
        a = px[..., 3]
        sub = zb[y0:y1, x0:x1]
        ok = inside & (a > 0) & (z < sub)
        glow = (a >= 250) & (a <= 252)
        col = px[..., :3].astype(float) * np.where(glow, 1.0, light)[..., None]
        sub[ok] = z[ok]
        img[y0:y1, x0:x1][ok] = col[ok]
    out = Image.fromarray(img.clip(0, 255).astype("uint8"), "RGB")
    return out.resize((size, size), Image.LANCZOS).convert("RGBA")


def zrig(spec, models, out_png, title, size=420):
    from mc3d import mat as mmat, contact_sheet
    parts = []
    for p in spec["parts"]:
        m = models.get(p["id"])
        if m is None:
            continue
        rx, ry, rz = p.get("rotation", [0, 0, 0])
        parts.append((m, mmat(translate=p.get("offset", [0, 0, 0]), scale=p.get("scale", 1.0), yaw=ry, pitch=rx, roll=rz)))
    views = [zrender(parts, size=size, yaw=y, pitch=pt) for (y, pt) in ((-35, 12), (0, 4), (-90, 6), (150, 12))]
    contact_sheet(views, [f"{title} 앞 3/4", f"{title} 정면", f"{title} 옆", f"{title} 뒤"], cols=4, cell=size,
                  font=FONT if os.path.exists(FONT) else None).save(out_png)


# ─────────────────────────── 조립 ───────────────────────────

S = 2.0           # 몸 조각 배율: 1 복셀 = 1/8 블록
V = S / 16.0      # 1 복셀의 블록 크기

TORSO_Y = 3.05
HEAD_Y = TORSO_Y + 7.5 * V
TAIL_Y = TORSO_Y - 14.5 * V
TAIL_LOW_Y = TAIL_Y - 11.5 * V
FIST_X, FIST_Y, FIST_Z = 2.85, 3.0, 0.35


def rig_spec():
    bob = {"type": "bob", "amplitude": 0.1, "period": 60, "phase": 0.0}
    parts = [
        {"id": "torso", "model": f"augsky:boss/{BOSS}_torso", "offset": [0, TORSO_Y, 0], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [bob, {"type": "sway", "axis": "z", "angle": 2.5, "period": 120, "phase": 0},
                   {"type": "swing", "axis": "x", "angle": 8, "ticks": 12}]},
        {"id": "head", "model": f"augsky:boss/{BOSS}_head", "offset": [0, HEAD_Y, 0.15], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [bob, {"type": "sway", "axis": "y", "angle": 10, "period": 140, "phase": 0},
                   {"type": "sway", "axis": "x", "angle": 4, "period": 90, "phase": 0.3},
                   {"type": "swing", "axis": "x", "angle": -16, "ticks": 12}]},
        {"id": "tail", "model": f"augsky:boss/{BOSS}_tail", "offset": [0, TAIL_Y, -0.05], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.1, "period": 60, "phase": 0.05},
                   {"type": "sway", "axis": "z", "angle": 8, "period": 80, "phase": 0},
                   {"type": "sway", "axis": "x", "angle": 6, "period": 110, "phase": 0.3}]},
        {"id": "tail_low", "model": f"augsky:boss/{BOSS}_tail_low", "offset": [0, TAIL_LOW_Y, -0.25], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.14, "period": 60, "phase": 0.15},
                   {"type": "sway", "axis": "z", "angle": 14, "period": 80, "phase": 0.18},
                   {"type": "sway", "axis": "x", "angle": 10, "period": 110, "phase": 0.5}]},
        {"id": "right_fist", "model": f"augsky:boss/{BOSS}_right_fist", "offset": [-FIST_X, FIST_Y, FIST_Z],
         "scale": S, "rotation": [0, 6, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.22, "period": 50, "phase": 0.25},
                   {"type": "sway", "axis": "x", "angle": 7, "period": 70, "phase": 0.1},
                   {"type": "swing", "axis": "x", "angle": -75, "ticks": 12}]},
        {"id": "left_fist", "model": f"augsky:boss/{BOSS}_left_fist", "offset": [FIST_X, FIST_Y, FIST_Z],
         "scale": S, "rotation": [0, -6, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.22, "period": 50, "phase": 0.75},
                   {"type": "sway", "axis": "x", "angle": 7, "period": 70, "phase": 0.6},
                   {"type": "swing", "axis": "x", "angle": -60, "ticks": 16}]},
    ]
    # 도는 바위 6개: 위 셋(어깨 위, 시계 방향) 아래 셋(꼬리 둘레, 반대 방향)
    for i in range(6):
        hi = i < 3
        k = i % 3
        parts.append({
            "id": f"rock{i + 1}", "model": f"augsky:boss/{BOSS}_rock_{'a' if (i % 2 == 0) else 'b'}",
            "offset": [0, 0, 0], "scale": S, "rotation": [0, 0, 0], "frame": "world",
            "anims": [{"type": "orbit", "radius": 3.5 if hi else 2.9, "speed": 2.2 if hi else -2.8,
                       "phase": k * 120 + (0 if hi else 60), "height": 5.0 if hi else 0.75},
                      {"type": "spin", "axis": "y", "speed": 4.0 if hi else -5.0},
                      {"type": "bob", "amplitude": 0.25, "period": 40, "phase": i / 6}],
        })
    return parts


def build(assets_root):
    models = {
        "torso": build_torso(assets_root),
        "head": build_head(assets_root),
        "tail": build_tail(assets_root),
        "tail_low": build_tail(assets_root, low=True),
        "right_fist": build_fist(assets_root, -1),
        "left_fist": build_fist(assets_root, +1),
        "rock_a": build_rock(assets_root, "a"),
        "rock_b": build_rock(assets_root, "b"),
    }
    spec = {
        "boss": BOSS,
        "parts": rig_spec(),
        "notes": ("화염 거신 (복셀): 1 복셀 = 1/8 블록 (vox 1.0, scale 2.0; 흑요석 바위만 1.6). 피벗 = 모델 (8,8,8). "
                  "torso=가슴 중심, head=목 밑동(어깨 사이에 박힘), tail=가슴 밑 꼬리 윗끝(아래로 매달림), "
                  "tail_low=꼬리 끝마디(같은 주기, 늦은 위상으로 따라 흔들림), fists=손목 위 약 1.25블록(주먹은 피벗 아래·앞) → "
                  "swing 이 앞-위로 큰 호를 그린다 (오른손 -75도/12틱, 왼손 -60도/16틱). "
                  "rocks=world 프레임 orbit (offset 0, height=발 기준 높이; 위 셋은 어깨 위, 아래 셋은 꼬리 둘레를 반대로). "
                  "앞=+Z, 오른손=-X. 용암(flow)/핵(fire)/마그마(pulse)/불꽃(fire)은 16프레임 애니메이션, glow=셰이더 자체 발광."),
    }
    spec["_models"] = models
    return spec


def _strip(spec):
    return {k: v for k, v in spec.items() if not k.startswith("_")}


def write_rig(spec):
    with open(os.path.join(HERE, MODULE + ".rig.json"), "w", encoding="utf-8") as f:
        json.dump(_strip(spec), f, ensure_ascii=False, indent=1)


def previews(spec, out_dir):
    from mc3d import render, contact_sheet
    models = spec["_models"]
    by_id = {}
    for p in spec["parts"]:
        key = p["model"].split(f"{BOSS}_", 1)[1]
        by_id[p["id"]] = models[key]
    # 바위는 미리보기에서 궤도의 한 순간에 놓는다
    shown = {"boss": BOSS, "parts": []}
    for p in spec["parts"]:
        q = dict(p)
        orb = next((a for a in p["anims"] if a["type"] == "orbit"), None)
        if orb:
            ang = math.radians(orb["phase"] + 25)
            q["offset"] = [orb["radius"] * math.sin(ang), orb["height"], orb["radius"] * math.cos(ang)]
        shown["parts"].append(q)
    rig_preview(shown, by_id, os.path.join(out_dir, f"{BOSS}_voxel.png"), NAME_KO)
    zrig(shown, by_id, os.path.join(out_dir, f"{BOSS}_voxel_hq.png"), NAME_KO)
    bg = (28, 26, 36, 255)
    for fn, tag in ((render, ""), (zrender, "_hq")):
        imgs, labels = [], []
        for key, views in (("torso", ((-30, 12), (150, 15))), ("head", ((-30, 8), (35, 4))),
                           ("left_fist", ((-40, 10), (60, 12))), ("right_fist", ((30, 10),)), ("tail", ((-30, 8),)),
                           ("tail_low", ((-30, 8),)), ("rock_a", ((-30, 18),)), ("rock_b", ((-30, 12),))):
            m = models[key]
            for (yaw, pitch) in views:
                imgs.append(fn([(m, None)], size=360, yaw=yaw, pitch=pitch, bg=bg))
                labels.append(f"{key} ({len(m.elements)})")
        contact_sheet(imgs, labels, cols=4, cell=360, font=FONT if os.path.exists(FONT) else None).save(
            os.path.join(out_dir, f"{BOSS}_voxel_parts{tag}.png"))

if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
    spec = build(root)
    write_rig(spec)
    total = 0
    for k, m in spec["_models"].items():
        print(f"{k:12s} {len(m.elements):4d} elements")
    for p in spec["parts"]:
        key = p["model"].split(f"{BOSS}_", 1)[1]
        total += len(spec["_models"][key].elements)
    print("whole boss (all displays):", total)
    previews(spec, os.path.join(HERE, "preview"))
