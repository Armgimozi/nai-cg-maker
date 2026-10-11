"""
vboss_flame: 화염 거신 (inferno_colossus) — 작은 정육면체(복셀)로 쌓은 보스.

떠다니는 용암 바위 거인. 1 복셀 = 1/8 블록 (모든 조각 part vox=1.0, rig scale 2.0, 오프셋은 1/8 블록 격자 위).
  torso            가슴(계단진 현무암 세 층 + 층 사이 빛나는 홈) + 다이아몬드 흑요석 테 속 마그마 핵 (가장 밝은 초점)
  left/right_shoulder  어깨 바위 (위 밝음 / 가운데 / 아래 어두움, 층 사이 홈, 큰 흑요석 결정 둘)
  head             목 틈(마그마) 위에 떠 있는 머리: 어두운 흑요석 눈썹 밑 비스듬한 실눈, 송곳니 으르렁 입, 상아 뿔, 불꽃 볏
  tail / tail_low  배 밑에 매달린, 점점 작아지는 바위 덩어리 탑 (사이사이 빛나는 틈, 가운데 용암 심)
  right/left_fist  가슴 높이 앞에 떠 있는 주먹. 마디 4개가 앞-아래 모서리로, 손가락은 바닥으로 감기고 엄지가 바닥을 가로지른다
                   (휘두르면(-X 75도) 바닥 = 마디 면이 앞을 향한다)
  rock_a / rock_b  둘레를 도는 불타는 바위 4개 (world 프레임 orbit 한 고리)

모양 언어: cbox() 계단 상자 + 모서리 깎기, 곧은 홈(빛나는 층 경계), 면마다 금 하나까지.
명암: 재료를 층별로 고정해 칠한 뒤 shade() 가 위가 열린 복셀은 한 단계 밝게(bas3 테두리 빛), 아래가 열린 복셀은 한 단계 어둡게.
빛: core(흰-노랑, 가장 밝음) = eye > lava(깊은 주황-빨강 홈) > magma(맥동, 틈) > ember(주먹 금, 가장 어두운 빛). 뿔/결정 끝은 빛나지 않는다.

python3 vboss_flame.py   -> _scratch/vboss_flame/assets/augsky 에 짓고 preview/inferno_colossus_voxel*.png
  inferno_colossus_voxel.png        조립 (깊이 버퍼 렌더 — 대표 미리보기) 앞 3/4, 옆, 뒤 + 정면, 휘두르기, 게임 속 크기
  inferno_colossus_voxel_hq.png     몸 확대 네 방향
  inferno_colossus_voxel_parts.png  조각별 확대 (깊이 버퍼)
  *_mc3d.png                        같은 것을 wkit.rig_preview / mc3d.render(면 평균 깊이 정렬)로 — 면이 비쳐 보이는 오류가 있다
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
# 현무암 사다리 bas0 < bas1 < bas2 < bas3. 한 재료 안의 복셀끼리 차이 ≈ 사다리 한 칸의 절반 → 큐브는 보이되 자갈 잡음은 아니다.
PAL = {
    "bas0": Mat(["#18121a", "#211a22", "#2a212a", "#332832"], "stone", seed=1),
    "bas1": Mat(["#2c2329", "#362b32", "#41343b", "#4b3c44"], "stone", seed=2),
    "bas2": Mat(["#4c3e42", "#58494c", "#655457", "#725f61"], "stone", seed=3),
    "bas3": Mat(["#9a8274", "#ab9181", "#bca18f", "#cab09c"], "stone", seed=4),
    "obs": Mat(["#150b26", "#1f1238", "#2a1a4c", "#35225e"], "stone", seed=5),
    "cry": Mat(["#150b26", "#1f1238", "#2a1a4c", "#35225e"], "stone", seed=17),   # 결정 몸통 (obs 와 같은 색, 명암 규칙만 다름)
    "cryM": Mat(["#34206a", "#3e287c", "#48308e", "#5238a0"], "stone", seed=18),  # 결정 앞면 (중간 보라)
    "obsH": Mat(["#5a36aa", "#6a42c2", "#7a52d2", "#8a62e0"], "stone", seed=6),
    "horn": Mat(["#c4b494", "#d2c3a2", "#e1d3b4", "#efe2c4"], "stone", seed=7),
    "hornD": Mat(["#8e7e64", "#9c8c70", "#ab9b7e", "#b8a888"], "stone", seed=8),
    "ember": Mat(["#8a2006", "#a82c0a", "#c43a0e", "#d84a12"], "stone", glow=True, seed=10),
    "eye": Mat(["#ffe7a0", "#fff1c4", "#fff9e6", "#ffffff"], "gem", glow=True, seed=11),
    "eyeR": Mat(["#e85a0c", "#f46c14", "#ff801e", "#ff9a30"], "stone", glow=True, seed=12),
    # 움직이는 재료 (조각마다 4개까지)
    "lava": Mat(["#c03008", "#d63e0e", "#ec5614", "#ff7a1a"], "flow", glow=True, seed=13),
    "core": Mat(["#ffb434", "#ffd668", "#fff2b0", "#fffcec"], "fire", glow=True, seed=14),
    "magma": Mat(["#7c1604", "#a02406", "#c8380c", "#e85414"], "pulse", glow=True, seed=15),
    "fire": Mat(["#b42a04", "#e04a0a", "#ff7418", "#ffa63a"], "fire", glow=True, seed=16),
}

ROCK = ("bas0", "bas1", "bas2", "bas3")
OBS = ("obs", "obsH")
HORN = ("hornD", "horn")


def mats(*names):
    return {n: PAL[n] for n in names}


# ─────────────────────────── 도구 ───────────────────────────

def mid(w, name):
    return w.names.index(name) + 1


def nb(filled, axis, d):
    """각 칸의 axis 방향 d(±1) 이웃이 차 있는가."""
    n = np.zeros_like(filled)
    src = [slice(None)] * 3
    dst = [slice(None)] * 3
    if d > 0:
        dst[axis], src[axis] = slice(0, -1), slice(1, None)
    else:
        dst[axis], src[axis] = slice(1, None), slice(0, -1)
    n[tuple(dst)] = filled[tuple(src)]
    return n


def erode_xz(m):
    """가로(X, Z)로만 한 겹 깎기."""
    e = m.copy()
    for ax in (0, 2):
        e &= nb(m, ax, 1) & nb(m, ax, -1)
    return e


def cbox(X, Y, Z, x0, x1, y0, y1, z0, z1, ch=0.0, cht=0.0, chb=0.0):
    """경계 좌표로 준 상자 (복셀 가운데가 안에 들면). ch: 세로 모서리, cht: 윗 모서리, chb: 아랫 모서리 깎기."""
    m = (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (Z > z0) & (Z < z1)
    dx = np.minimum(X - x0, x1 - X)
    dz = np.minimum(Z - z0, z1 - Z)
    if ch:
        m &= dx + dz > ch
    if cht:
        dy = y1 - Y
        m &= (dx + dy > cht) & (dz + dy > cht)
    if chb:
        dy = Y - y0
        m &= (dx + dy > chb) & (dz + dy > chb)
    return m


def groove(w, region, y0, mat="lava"):
    """region 의 Y=y0-1..y0 한 층을 둘레 한 칸 파내고, 그 안쪽 한 칸에 빛나는 재료 → 오목한 곧은 홈."""
    layer = region & (w._Y > y0 - 1) & (w._Y < y0)
    inner = erode_xz(layer)
    w.grid[layer & ~inner] = 0
    w.grid[inner & ~erode_xz(inner)] = mid(w, mat)


def crystal(w, x, y, z, sizes, lean=(0.0, 0.0), mat="cry"):
    """
    뭉툭한 네모 결정: 곧은 상자 마디를 쌓는다. sizes = [(폭, 높이), ...] 아래 → 위 (끝 마디도 폭 2 이상).
    lean = 마디마다 옮기는 (X, Z) 칸 수 (기울기). 마디가 곧아서 계단 무늬가 생기지 않는다.
    """
    cx, cz, cy = x, z, y
    for (s_, h) in sizes:
        ax = round(cx - s_ / 2) + s_ / 2
        az = round(cz - s_ / 2) + s_ / 2
        w.fill(lambda X, Y, Z, ax=ax, az=az, s_=s_, y0=cy, y1=cy + h: (np.abs(X - ax) < s_ / 2) & (np.abs(Z - az) < s_ / 2)
               & (Y > y0) & (Y < y1), mat)
        cy += h
        cx += lean[0]
        cz += lean[1]


def surface_line(w, cells, axis, sign, mat, only=None, depth=1):
    """2D 칸들을 겉면에 데칼처럼 칠한다 (axis 'z': (X, Y) 칸, 'x': (Z, Y) 칸, 'y': (X, Z) 칸)."""
    g = w.grid
    m_id = mid(w, mat)
    only_ids = None if only is None else [mid(w, n) for n in only if n in w.names]
    for (a, b) in cells:
        if axis == "z":
            i, j = int(round(a - 0.5 + w.CX)), int(round(b - 0.5 + w.CY))
            col = g[i, j, :] if (0 <= i < w.W and 0 <= j < w.H) else None
        elif axis == "x":
            k, j = int(round(a - 0.5 + w.CZ)), int(round(b - 0.5 + w.CY))
            col = g[:, j, k] if (0 <= k < w.D and 0 <= j < w.H) else None
        else:
            i, k = int(round(a - 0.5 + w.CX)), int(round(b - 0.5 + w.CZ))
            col = g[i, :, k] if (0 <= i < w.W and 0 <= k < w.D) else None
        if col is None:
            continue
        nz = np.nonzero(col)[0]
        if len(nz) == 0:
            continue
        first = nz[-1] if sign > 0 else nz[0]
        for dd in range(depth):
            p = first - dd if sign > 0 else first + dd
            if 0 <= p < len(col) and col[p] and (only_ids is None or col[p] in only_ids):
                col[p] = m_id


def stair(p0, p1):
    """두 점 사이의 계단진 곧은 선 (4방향 연결) → 칸 가운데 목록."""
    (x0, y0), (x1, y1) = p0, p1
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
    out = []
    for k in range(n + 1):
        t = k / n
        c = (math.floor(x0 + (x1 - x0) * t) + 0.5, math.floor(y0 + (y1 - y0) * t) + 0.5)
        if out and c[0] != out[-1][0] and c[1] != out[-1][1]:
            out.append((c[0], out[-1][1]))
        if not out or out[-1] != c:
            out.append(c)
    return out


def shade(w, ladder, up=1, down=1, vedge=0, rim=False, front_edges=False):
    """
    모양을 따라 명암: ladder (어두움 → 밝음) 재료 중
      위(+Y)가 비어 있으면 up 칸 밝게 (윗면과 윗 모서리 = 테두리 빛)
      아래가 비어 있고 위는 막혀 있으면 down 칸 어둡게 (밑면)
      vedge: 세로 모서리(X 와 Z 둘 다 열림)를 몇 칸 밝게
      rim: True 면 위가 열려도 옆도 열린 칸(윗 테두리)만 밝게
      front_edges: True 면 세로 모서리 중 앞(+Z)이 열린 것만
    """
    ids = [mid(w, n) for n in ladder if n in w.names]
    g = w.grid
    filled = g > 0
    up_e = ~nb(filled, 1, 1)
    dn_e = ~nb(filled, 1, -1) & ~up_e
    ex = ~nb(filled, 0, 1) | ~nb(filled, 0, -1)
    ez = ~nb(filled, 2, 1) | ~nb(filled, 2, -1)
    if front_edges:
        ez = ~nb(filled, 2, 1)
    edge = ex & ez & ~up_e
    if rim:
        up_e = up_e & (ex | ez)
    new = g.copy()
    top = len(ids) - 1
    for i, idv in enumerate(ids):
        m = g == idv
        lev = np.full(g.shape, i, int)
        lev = lev + up * up_e - down * dn_e + vedge * edge
        lev = np.clip(lev, 0, top)
        for j in range(len(ids)):
            new[m & (lev == j)] = ids[j]
    w.grid = new


def facet(w, front_sign=1):
    """결정 세 톤: 윗면 = obsH(밝음), 앞(+Z)이 열린 면 = cryM(중간), 나머지 = cry(어두움)."""
    g = w.grid
    filled = g > 0
    m = g == mid(w, "cry")
    up_e = ~nb(filled, 1, 1)
    fz = ~nb(filled, 2, front_sign)
    g[m & fz & ~up_e] = mid(w, "cryM")
    g[m & up_e] = mid(w, "obsH")


def count(model):
    return len(model.elements)


# ─────────────────────────── 몸통 ───────────────────────────

def build_torso(root):
    w = part(mats("bas0", "bas1", "bas2", "bas3", "obs", "obsH", "lava", "core", "magma"), size=48)
    X, Y, Z = w._X, w._Y, w._Z
    AX = np.abs(X)
    # 계단진 네 층 (위가 넓다): 가슴 / 갈비 / 허리 / 배 밑 (꼬리 첫 덩어리 폭 12)
    t3 = cbox(AX, Y, Z, -11, 11, 2, 9, -6.5, 6.5, ch=2.5, cht=2)
    t2 = cbox(AX, Y, Z, -9, 9, -3, 2, -6, 6, ch=2.5)
    t1 = cbox(AX, Y, Z, -7.5, 7.5, -7, -3, -5, 5, ch=2, chb=1)
    w.fill(lambda *_: t1, "bas1")
    w.fill(lambda *_: t2, "bas1")
    w.fill(lambda *_: t3, "bas2")
    # 가슴판 둘 (앞으로 툭)
    pec = cbox(AX, Y, Z, 1, 10, 2, 8.5, 0, 8, ch=1.5, cht=1.5)
    w.fill(lambda *_: pec, "bas2")
    # 승모근: 어깨에서 목 쪽으로 솟은 바위 (가슴 윗면이 탁자처럼 평평하지 않게)
    w.fill(lambda *_: cbox(AX, Y, Z, 4, 10.5, 7, 10, -5, 2, ch=1.5, cht=1.5), "bas2")
    # 갈비 옆판: 갈비층 옆에 덧댄 판 (가로 홈 하나)
    w.fill(lambda *_: cbox(AX, Y, Z, 6, 10, -2.5, 1.5, -4.5, 4.5, ch=1.5), "bas2")
    # 층 사이 곧은 홈
    groove(w, t2, 2, "lava")
    groove(w, t1, -3, "lava")
    # 등: 흑요석 등판 둘 (뭉툭한 계단 덩어리)
    for (y0, y1) in ((3, 8), (-3, 1)):
        w.fill(lambda *_, y0=y0, y1=y1: cbox(X, Y, Z, -2, 2, y0, y1, -8.5, -4, ch=1, cht=1), "obs")
    # 등 대각선 금 하나씩
    for s in (1,):
        surface_line(w, stair((s * 3.5, 7.5), (s * 8.5, 1.5)), "z", -1, "lava", only=("bas1", "bas2"))
    # 옆구리 대각선 금 하나 (옆면)
    surface_line(w, stair((-3.5, 7.5), (3.5, 3.0)), "x", 1, "lava", only=("bas1", "bas2"))

    # 가슴 마그마 핵: 다이아몬드 구멍 + 두꺼운 흑요석 테 + 빛나는 핵 (가장 밝은 초점)
    diamond = AX + np.abs(Y)
    w.clear(lambda *_: (diamond <= 6.0) & (Z >= 1))
    w.fill(lambda *_: (diamond > 6.0) & (diamond <= 8.5) & (Z >= 3) & (Z <= 9), "obs")
    w.fill(lambda *_: (diamond > 6.0) & (diamond <= 7.0) & (Z > 8) & (Z <= 9), "obsH")
    w.fill(lambda *_: (diamond > 5.0) & (diamond <= 6.0) & (Z >= 1) & (Z <= 5), "lava")
    w.fill(lambda *_: (diamond <= 5.0) & (Z <= 3.0) & (Z >= -1), "magma")
    w.fill(lambda *_: (X / 4.0) ** 2 + (Y / 4.0) ** 2 + ((Z - 3.0) / 3.2) ** 2 <= 1, "core")
    # 목 자리: 파인 소켓, 바닥은 마그마 (머리와 사이 틈이 빛난다)
    w.clear(lambda *_: (AX <= 3.5) & (Y >= 7.0) & (Z >= 0) & (Z <= 8))
    w.fill(lambda *_: (AX <= 3.5) & (Y >= 6.0) & (Y <= 7.0) & (Z >= 0) & (Z <= 8), "magma")
    w.mirror()
    shade(w, ROCK, up=1, down=1)
    shade(w, OBS, up=1, down=0, rim=True)
    return w.build(f"boss/{BOSS}_torso", root)


SHOULDER_X, SHOULDER_Y = 10.0, 5.0   # 몸통 피벗에서 어깨 피벗까지 (복셀)


def build_shoulder(root, side):
    """어깨 바위. side=+1 왼쪽(+X), -1 오른쪽. 피벗 = 어깨 관절. 좌우는 같은 모양을 거울로 (같은 씨앗)."""
    w = part(mats("bas0", "bas1", "bas2", "bas3", "obs", "cry", "cryM", "obsH", "lava", "magma"), size=40)
    X, Y, Z = w._X, w._Y, w._Z
    xs = X * side
    # 겹겹이 쌓인 바위 갑옷: 위(밝음) → 가운데 → 아래(어두움). 층 사이마다 곧은 빛 홈
    A = cbox(xs, Y, Z, -0.5, 9, 0, 7, -6.5, 4.5, ch=2.5, cht=2.5)
    B = cbox(xs, Y, Z, 0.5, 9.25, -4, 0, -7, 4, ch=2.5)
    C = cbox(xs, Y, Z, 2, 8, -8, -4, -6, 1, ch=2, chb=1.5)
    w.fill(lambda *_: C, "bas0")
    w.fill(lambda *_: B, "bas1")
    w.fill(lambda *_: A, "bas2")
    groove(w, B, 0, "lava")
    groove(w, C, -4, "lava")
    # 앞면 대각선 금 하나 (B 층)
    surface_line(w, [(side * a, b) for (a, b) in stair((2.5, -0.5), (7.5, -3.5))], "z", 1, "lava", only=("bas1", "bas0"))
    # 바깥 옆면 금 하나
    surface_line(w, stair((3.5, 5.5), (-3.5, 1.5)), "x", side, "lava", only=("bas2", "bas1"))
    # 위로 솟은 큰 흑요석 결정 둘 (바깥, 뒤로) — 끝도 2x2
    crystal(w, side * 5.0, 5, -2.0, [(6, 3), (4, 3), (2, 2)], lean=(side * 1.0, -0.5))
    crystal(w, side * 1.0, 5, -4.5, [(4, 3), (2, 2)], lean=(0.0, -0.5))
    shade(w, ROCK, up=1, down=1)
    shade(w, OBS, up=1, down=0, rim=True)
    facet(w)
    return w.build(f"boss/{BOSS}_{'left' if side > 0 else 'right'}_shoulder", root)


# ─────────────────────────── 머리 ───────────────────────────

# 얼굴 칸 (+X 쪽 반; 거울로 왼쪽). (|X| 칸 가운데, Y 칸 가운데)
# 눈: 안쪽이 낮고 바깥으로 올라가는 화난 실눈 (1~2 높이). eye = 흰 불꽃 가운데, eyeR = 주황 테
EYE = {(1.5, 7.5): "eyeR", (2.5, 7.5): "eye", (3.5, 7.5): "eye", (4.5, 7.5): "eyeR",
       (2.5, 8.5): "eyeR", (3.5, 8.5): "eye", (4.5, 8.5): "eyeR", (5.5, 8.5): "eyeR", (6.5, 8.5): "eyeR"}
# 눈썹(흑요석): 눈 바로 위로 두 칸 튀어나온 V — 가운데(미간)로 내려온다
BROW = [(0.5, 8.5), (0.5, 9.5), (1.5, 8.5), (1.5, 9.5), (2.5, 9.5), (3.5, 9.5), (4.5, 9.5), (5.5, 9.5), (6.5, 9.5),
        (1.5, 10.5), (2.5, 10.5), (3.5, 10.5), (4.5, 10.5), (5.5, 10.5), (6.5, 10.5), (7.5, 10.5),
        (4.5, 11.5), (5.5, 11.5), (6.5, 11.5), (7.5, 11.5), (7.5, 9.5)]
# 입: 가운데가 넓고 모서리가 올라가는 계단진 으르렁 (마그마), 위 송곳니 2폭 3높이
MOUTH = [(0.5, 1.5), (0.5, 2.5), (0.5, 3.5), (1.5, 1.5), (1.5, 2.5), (1.5, 3.5), (2.5, 1.5), (2.5, 2.5), (2.5, 3.5),
         (3.5, 1.5), (3.5, 2.5), (3.5, 3.5), (4.5, 2.5), (4.5, 3.5), (5.5, 3.5), (5.5, 4.5)]
FANG = [(3.5, 3.5), (4.5, 3.5), (3.5, 2.5), (4.5, 2.5), (4.5, 1.5)]


def build_head(root):
    w = part(mats("bas0", "bas1", "bas2", "bas3", "obs", "obsH", "eye", "eyeR", "horn", "hornD",
                  "lava", "fire", "magma"), size=48)
    X, Y, Z = w._X, w._Y, w._Z
    AX = np.abs(X)

    def at(a, y):
        return (np.abs(AX - a) < 0.5) & (np.abs(Y - y) < 0.5)

    # 목: 마그마 기둥 (몸통 소켓과 머리 사이의 빛나는 틈)
    w.fill(lambda *_: (AX <= 2) & (Y >= -3) & (Y <= 1) & (np.abs(Z - 1) <= 2), "magma")
    skull = cbox(AX, Y, Z, -8, 8, 1, 14, -6, 7, ch=2.5, cht=3)
    jaw = cbox(AX, Y, Z, -7, 7, -1, 5, 0, 8, ch=2.5, chb=1)
    w.fill(lambda *_: skull, "bas1")
    w.fill(lambda *_: jaw, "bas1")
    # 광대: 눈 밑에서 앞으로
    w.fill(lambda *_: cbox(AX, Y, Z, 2, 7.5, 4, 7, 0, 8, ch=1), "bas2")
    # 이마판 (밝은 층)
    w.fill(lambda *_: cbox(AX, Y, Z, -7, 7, 11, 14, -4, 7.5, ch=2, cht=2), "bas2")
    # 눈구멍: 어두운 굴 (얼굴면보다 한 칸 들어감)
    w.clear(lambda *_: (AX < 7.5) & (Y > 7) & (Y < 10) & (Z > 6))
    w.fill(lambda *_: (AX < 7.5) & (Y > 7) & (Y < 10) & (Z > 5) & (Z < 6), "bas0")
    # 흑요석 눈썹: 눈보다 두 칸 앞으로 튀어나와 그늘을 드리운다
    for (a, y) in BROW:
        w.fill(lambda X, Y, Z, a=a, y=y: at(a, y) & (Z > 4) & (Z < 8), "obs")
    for (a, y), m in EYE.items():
        w.fill(lambda X, Y, Z, a=a, y=y: at(a, y) & (Z > 4) & (Z < 6), m)
    # 입: 앞면을 파내고 안쪽은 마그마, 송곳니는 앞면에
    for (a, y) in MOUTH:
        w.clear(lambda X, Y, Z, a=a, y=y: at(a, y) & (Z > 6))
        w.fill(lambda X, Y, Z, a=a, y=y: at(a, y) & (Z > 5) & (Z < 7), "magma")
    for (a, y) in FANG:
        w.fill(lambda X, Y, Z, a=a, y=y: at(a, y) & (Z > 6) & (Z < 8), "horn")
    # 뿔: 상아색, 옆으로 나와 위로. 흑요석 고리 둘. 70% 까지 반지름 2 이상, 끝은 빛나지 않는다
    horn = [(7.0, 10.5, -1.0), (11.5, 11.5, -1.5), (15.0, 13.5, -1.5), (16.5, 17.0, -0.5), (15.5, 20.5, 1.0)]
    w.tube(horn, lambda t: 2.8 - 1.0 * t if t < 0.7 else 2.1 - (t - 0.7) / 0.3 * 1.1, "horn")
    for p, r in ((horn[1], 3.1), (horn[2], 2.8)):
        w.fill(lambda X, Y, Z, p=p, r=r: ((X - p[0]) ** 2 + (Y - p[1]) ** 2 + (Z - p[2]) ** 2 <= r ** 2)
               & (w.grid > 0) & (np.abs((X - p[0]) * 0.4 + (Y - p[1]) * 0.9) <= 0.7), "obs")
    # 불꽃 볏: 계단진 흑요석 지느러미 + 굵은 불꽃 혀 셋
    saw = 15.0 + (np.floor((Z + 7) / 3) % 2) * 1.0
    w.fill(lambda *_: (AX <= 1) & (Y >= 13) & (Y <= saw) & (Z >= -6.5) & (Z <= 4), "obs")
    for (z, h, lean) in ((2.0, 2.5, -0.5), (-1.5, 4.0, -1.5), (-5.0, 3.0, -2.0)):
        base = 15.5
        w.tube([(0, base, z), (0, base + h * 0.55, z + lean * 0.5), (0, base + h, z + lean)],
               lambda t: 1.3 * (1 - 0.4 * t), "fire")
    # 뒤통수: 가로 홈 하나
    w.fill(lambda *_: (AX <= 6) & (Y > 6) & (Y < 7) & (Z < -5) & (Z > -6), "lava")
    w.mirror()
    shade(w, ROCK, up=1, down=1)
    shade(w, OBS, up=1, down=0, rim=True)
    shade(w, HORN, up=0, down=1)
    return w.build(f"boss/{BOSS}_head", root)


# ─────────────────────────── 주먹 ───────────────────────────

FINGERS = [(-7, -4), (-3, 0), (1, 4), (5, 7)]   # Xs 범위: 검지(엄지 쪽 Xs<0) 3, 중지 3, 약지 3, 새끼 2. 사이 1칸 틈


def build_fist(root, side):
    """
    side=+1 왼주먹(+X 쪽), -1 오른주먹(-X 쪽). 엄지는 몸 쪽(Xs<0). 피벗 = 손목(주먹 바로 위).
    앞(+Z) = 손등 판(금 하나), 앞-아래 모서리 = 3x3 마디 넷(가운데 둘이 한 칸 더 나옴), 바닥(-Y) = 손가락 첫 마디(치는 면, 사이 빛 금),
    뒤-아래 = 접힌 둘째 마디, 엄지는 바닥 뒤쪽에서 검지·중지를 가로지른다.
    휘두르기(-X 75도)에서 바닥(마디·손가락·엄지 면)이 앞을 향한다.
    """
    w = part(mats("bas0", "bas1", "bas2", "bas3", "ember", "lava"), size=40)
    X, Y, Z = w._X, w._Y, w._Z
    Xs = X * side
    # 손 덩어리 + 앞 손등 판 (한 칸 튀어나옴)
    w.fill(lambda *_: cbox(Xs, Y, Z, -6, 6, -10, -1, -5, 4, ch=2.5, cht=3), "bas1")
    w.fill(lambda *_: cbox(Xs, Y, Z, -5.5, 5.5, -7, -1.5, 0, 5, ch=2, cht=2.5), "bas1")
    for i, (x0, x1) in enumerate(FINGERS):
        lead = 1 if i in (1, 2) else 0
        kn = cbox(Xs, Y, Z, x0, x1, -12, -6, 2, 7 + lead)                  # 손등 마디 3x3(+): 앞-아래 모서리, 판보다 2칸 앞
        kn &= ~((Y < -11) & (Z > 6 + lead)) & ~((Y > -7) & (Z > 6 + lead))
        prox = cbox(Xs, Y, Z, x0, x1, -12, -9, -5, 3)                      # 첫 마디: 바닥 (치는 면)
        pip = cbox(Xs, Y, Z, x0, x1, -12, -6, -7, -4)                      # 둘째 마디: 뒤-아래로 접혀 올라감
        pip &= ~((Y < -11) & (Z < -6))
        w.fill(lambda *_, m=prox | pip: m, "bas1")
        w.fill(lambda *_, m=kn: m, "bas2")
    # 손가락 사이 틈: 겉 한 칸은 비우고 안쪽 한 줄만 빛나는 곧은 금
    for (a, b) in ((-4, -3), (0, 1), (4, 5)):
        col = (Xs > a) & (Xs < b)
        w.grid[col & (Y < -6) & (Z > 3)] = 0
        w.grid[col & (Y < -10)] = 0
        w.grid[col & (Y < -6) & (Z < -5)] = 0
        w.grid[col & (Y > -11) & (Y < -8) & (Z > -5) & (Z < 4)] = mid(w, "ember")
    # 엄지: 몸 쪽 옆의 두툼한 뿌리 → 바닥 뒤쪽에서 검지·중지 밑을 가로지른다 (3x3 단면)
    w.fill(lambda *_: cbox(Xs, Y, Z, -9, -6, -10, -2, -5, 2, ch=1, cht=1), "bas2")
    w.fill(lambda *_: cbox(Xs, Y, Z, -9, -6, -12, -9, -6, -1, ch=1), "bas2")
    w.fill(lambda *_: cbox(Xs, Y, Z, -9, 0.5, -13, -10, -5, -2, ch=1, chb=1), "bas2")
    # 손등 대각선 금 하나 (앞 판)
    surface_line(w, [(side * a, b) for (a, b) in stair((-3.0, -2.0), (2.0, -6.0))], "z", 1, "ember", only=("bas1",))
    shade(w, ROCK, up=1, down=0)
    return w.build(f"boss/{BOSS}_{'left' if side > 0 else 'right'}_fist", root)


# ─────────────────────────── 꼬리 ───────────────────────────

def build_tail(root, low=False):
    """
    허리(폭 15) 아래로 점점 작아지는 바위 덩어리 탑: 10 → 6 → 4 → 2. 덩어리 사이 1칸 틈으로 용암 심(2x2)이 빛난다.
    tail: 폭 10 덩어리 (피벗 = 위 끝). tail_low: 폭 6, 4 덩어리 + 폭 2 흑요석 끝 (늦게 따라 흔들림).
    """
    w = part(mats("bas0", "bas1", "bas2", "bas3", "obs", "obsH", "lava"), size=32)
    X, Y, Z = w._X, w._Y, w._Z
    if not low:
        w.fill(lambda *_: (np.abs(X) < 1) & (np.abs(Z) < 1) & (Y > -6) & (Y < 1), "lava")
        w.fill(lambda *_: cbox(X, Y, Z, -5, 5, -5, -1, -4, 4, ch=2.5, cht=1, chb=1.5), "bas1")
    else:
        w.fill(lambda *_: (np.abs(X) < 1) & (np.abs(Z) < 1) & (Y > -8) & (Y < 0), "lava")
        w.fill(lambda *_: cbox(X, Y, Z, -3, 3, -4, -1, -3, 3, ch=1.5, chb=1), "bas1")
        w.fill(lambda *_: cbox(X, Y, Z, -2, 2, -7, -5, -2, 2, ch=1), "bas1")
        w.fill(lambda *_: (np.abs(X) < 1) & (np.abs(Z) < 1) & (Y > -9) & (Y < -8), "obs")
    shade(w, ROCK, up=1, down=1)
    shade(w, OBS, up=1, down=0, rim=True)
    return w.build(f"boss/{BOSS}_{'tail_low' if low else 'tail'}", root)


# ─────────────────────────── 도는 바위 ───────────────────────────

def build_rock(root, kind):
    w = part(mats("bas0", "bas1", "bas2", "bas3", "obs", "cry", "cryM", "obsH", "lava", "fire", "magma"), size=24)
    X, Y, Z = w._X, w._Y, w._Z
    if kind == "a":
        # 불타는 현무암 덩어리: 어긋나게 겹친 계단 상자 셋 + 갈라진 틈에서 새는 불 (위에 불꽃 혀 없음)
        r = cbox(X, Y, Z, -4, 3, -3.5, 2, -3, 4, ch=2, cht=1.5, chb=1.5)
        r |= cbox(X, Y, Z, -2, 4.5, -2, 3.5, -4, 2, ch=2, cht=1.5)
        r |= cbox(X, Y, Z, -3, 2, -4.5, -1, -2, 2.5, ch=1.5, chb=1)
        w.fill(lambda *_: r, "bas1")
        # 갈라진 틈: 대각선으로 바위를 가르는 판 (겉은 불, 속은 용암)
        cut = np.abs(X * 0.7 + Y * 0.7 - Z * 0.15 - 0.3) < 0.55
        w.grid[r & cut] = mid(w, "lava")
        surf = r & cut & ~(nb(r, 1, 1) & nb(r, 0, 1) & nb(r, 0, -1) & nb(r, 2, 1) & nb(r, 2, -1))
        w.grid[surf & (Y > 0)] = mid(w, "fire")
    else:
        # 낮고 넓은 흑요석 덩어리 + 뭉툭한 결정 둘 (끝도 2x2) + 밑 홈
        base = cbox(X, Y, Z, -4.5, 4.5, -3, 0, -4, 3.5, ch=2.5, chb=1.5, cht=1)
        w.fill(lambda *_: base, "obs")
        crystal(w, 1.0, -1, -0.5, [(4, 3), (2, 2)], lean=(1.0, 0.0))
        crystal(w, -2.5, -1, 1.0, [(2, 3)], lean=(-1.0, 0.0))
        groove(w, base, -1.0, "lava")
    shade(w, ROCK, up=1, down=1)
    shade(w, OBS, up=1, down=0, rim=True)
    facet(w)
    return w.build(f"boss/{BOSS}_rock_{kind}", root)

# ─────────────────────────── 깊이 버퍼 미리보기 ───────────────────────────
# mc3d.render 는 면을 평균 깊이로만 정렬해서 긴 면이 앞의 작은 면을 덮는 일이 있다.
# 복셀 모양을 정확히 보려고 픽셀마다 깊이를 비교하는 렌더러를 하나 더 둔다 (같은 정사영, 같은 면 밝기).

def zrender(parts, size=512, yaw=-35, pitch=25, bg=(28, 26, 36, 255), pad=0.08, ss=2, frame=None):
    """frame: (cx, cy, span) 를 주면 그 화면 틀에 맞춘다 (여러 장의 크기를 같게)."""
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
    if frame is None:
        span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    else:
        cx, cy, span = frame
    S = size * ss
    sc = S * (1 - 2 * pad) / span
    img = np.zeros((S, S, 3), float)
    img[:] = bg[:3]
    zb = np.full((S, S), -np.inf)   # 카메라는 +z 쪽: z 가 클수록 가깝다
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
        ok = inside & (a > 0) & (z > sub)
        glow = (a >= 250) & (a <= 252)
        col = px[..., :3].astype(float) * np.where(glow, 1.0, light)[..., None]
        sub[ok] = z[ok]
        img[y0:y1, x0:x1][ok] = col[ok]
    out = Image.fromarray(img.clip(0, 255).astype("uint8"), "RGB")
    return out.resize((size, size), Image.LANCZOS).convert("RGBA")


def placed(spec, models, swing=0.0, body_only=False):
    """[(model, 4x4)] — swing 0..1: 공격 동작의 sin 진폭 (1 = 가장 크게)."""
    from mc3d import mat as mmat
    out = []
    for p in spec["parts"]:
        m = models.get(p["id"])
        if m is None or (body_only and p.get("frame") == "world"):
            continue
        rx, ry, rz = p.get("rotation", [0, 0, 0])
        M = mmat(translate=p.get("offset", [0, 0, 0]), scale=p.get("scale", 1.0), yaw=ry, pitch=rx, roll=rz)
        if swing:
            for a in p.get("anims", []):
                if a["type"] == "swing":
                    from mc3d import _rot_matrix
                    R = np.eye(4)
                    R[:3, :3] = _rot_matrix(a["axis"], a["angle"] * swing)
                    M = M.copy()
                    M[:3, :3] = R[:3, :3] @ M[:3, :3]
        out.append((m, M))
    return out


def zrig(spec, models, out_png, title, size=560):
    """[바위까지 전체 앞 3/4 | 몸 확대 앞 3/4 / 몸 확대 정면 | 몸 확대 뒤]."""
    from mc3d import contact_sheet
    allp, body = placed(spec, models), placed(spec, models, body_only=True)
    views = [zrender(allp, size=size, yaw=-35, pitch=12), zrender(body, size=size, yaw=-35, pitch=10, pad=0.04),
             zrender(body, size=size, yaw=0, pitch=4, pad=0.04), zrender(body, size=size, yaw=155, pitch=10, pad=0.04)]
    contact_sheet(views, [f"{title} (도는 바위 포함)", f"{title} 앞 3/4", f"{title} 정면", f"{title} 뒤"], cols=2, cell=size,
                  font=FONT if os.path.exists(FONT) else None).save(out_png)


def zmain(spec, models, out_png, title, size=400):
    """대표 미리보기: 앞 3/4, 옆, 뒤 3/4 (rig_preview 와 같은 각도) + 정면, 휘두르기 정점, 게임 속 크기(약 140px)."""
    from mc3d import contact_sheet
    from PIL import Image
    allp = placed(spec, models)
    views = [zrender(allp, size=size, yaw=y, pitch=p) for (y, p) in ((-35, 12), (-90, 6), (150, 12))]
    views.append(zrender(allp, size=size, yaw=0, pitch=4))
    views.append(zrender(placed(spec, models, swing=1.0), size=size, yaw=-25, pitch=6))
    small = zrender(allp, size=150, yaw=-25, pitch=8, pad=0.03)
    tile = Image.new("RGBA", (size, size), (28, 26, 36, 255))
    tile.paste(small, ((size - 150) // 2, (size - 150) // 2))
    views.append(tile)
    labels = [f"{title} 앞", f"{title} 옆", f"{title} 뒤", f"{title} 정면", f"{title} 주먹 휘두르기 (정점)", "게임 속 크기 (150px)"]
    contact_sheet(views, labels, cols=3, cell=size, font=FONT if os.path.exists(FONT) else None).save(out_png)


# ─────────────────────────── 조립 ───────────────────────────

S = 2.0           # 몸 조각 배율: 1 복셀 = 1/8 블록
V = S / 16.0      # 1 복셀의 블록 크기 (0.125)

# 모든 오프셋은 V 의 배수 (몸 전체 큐브 격자가 이어진다)
TORSO_Y = 24 * V                     # 3.0 — 가슴 핵 가운데
HEAD_Y = TORSO_Y + 11 * V            # 목 밑동: 몸통 위 끝(+9)보다 2칸 위, 틈은 마그마로 빛난다
HEAD_Z = 3 * V
TAIL_Y = TORSO_Y - 7 * V             # 허리 밑 (몸통 맨 아래)
TAIL_LOW_Y = TAIL_Y - 6 * V
FIST_X, FIST_Y, FIST_Z = 19 * V, 26 * V, 10 * V   # 손목 피벗 (주먹 몸통 y 1.63..3.13)


def rig_spec():
    bob = {"type": "bob", "amplitude": 0.1, "period": 60, "phase": 0.0}
    parts = [
        {"id": "torso", "model": f"augsky:boss/{BOSS}_torso", "offset": [0, TORSO_Y, 0], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [bob, {"type": "sway", "axis": "z", "angle": 2.0, "period": 120, "phase": 0},
                   {"type": "swing", "axis": "x", "angle": 6, "ticks": 12}]},
        {"id": "right_shoulder", "model": f"augsky:boss/{BOSS}_right_shoulder",
         "offset": [-SHOULDER_X * V, TORSO_Y + SHOULDER_Y * V, 0], "scale": S, "rotation": [0, 0, 0], "frame": "body",
         "anims": [bob, {"type": "sway", "axis": "z", "angle": 3, "period": 60, "phase": 0.5},
                   {"type": "swing", "axis": "z", "angle": -8, "ticks": 12}]},
        {"id": "left_shoulder", "model": f"augsky:boss/{BOSS}_left_shoulder",
         "offset": [SHOULDER_X * V, TORSO_Y + SHOULDER_Y * V, 0], "scale": S, "rotation": [0, 0, 0], "frame": "body",
         "anims": [bob, {"type": "sway", "axis": "z", "angle": 3, "period": 60, "phase": 0.0},
                   {"type": "swing", "axis": "z", "angle": 8, "ticks": 12}]},
        {"id": "head", "model": f"augsky:boss/{BOSS}_head", "offset": [0, HEAD_Y, HEAD_Z], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.12, "period": 60, "phase": 0.04},
                   {"type": "sway", "axis": "y", "angle": 9, "period": 140, "phase": 0},
                   {"type": "sway", "axis": "x", "angle": 3, "period": 90, "phase": 0.3},
                   {"type": "swing", "axis": "x", "angle": -10, "ticks": 12}]},
        {"id": "tail", "model": f"augsky:boss/{BOSS}_tail", "offset": [0, TAIL_Y, 0], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.1, "period": 60, "phase": 0.04},
                   {"type": "sway", "axis": "z", "angle": 6, "period": 80, "phase": 0},
                   {"type": "sway", "axis": "x", "angle": 5, "period": 110, "phase": 0.3}]},
        {"id": "tail_low", "model": f"augsky:boss/{BOSS}_tail_low", "offset": [0, TAIL_LOW_Y, 0], "scale": S,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.1, "period": 60, "phase": 0.1},
                   {"type": "sway", "axis": "z", "angle": 8, "period": 80, "phase": 0.1},
                   {"type": "sway", "axis": "x", "angle": 6, "period": 110, "phase": 0.4}]},
        {"id": "right_fist", "model": f"augsky:boss/{BOSS}_right_fist", "offset": [-FIST_X, FIST_Y, FIST_Z],
         "scale": S, "rotation": [0, 6, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.15, "period": 50, "phase": 0.25},
                   {"type": "sway", "axis": "x", "angle": 6, "period": 70, "phase": 0.1},
                   {"type": "swing", "axis": "x", "angle": -75, "ticks": 12}]},
        {"id": "left_fist", "model": f"augsky:boss/{BOSS}_left_fist", "offset": [FIST_X, FIST_Y, FIST_Z],
         "scale": S, "rotation": [0, -6, 0], "frame": "body",
         "anims": [{"type": "bob", "amplitude": 0.15, "period": 50, "phase": 0.75},
                   {"type": "sway", "axis": "x", "angle": 6, "period": 70, "phase": 0.6},
                   {"type": "swing", "axis": "x", "angle": -60, "ticks": 10}]},
    ]
    # 도는 바위 4개: 어깨 높이 바깥 한 고리 (머리·볏 앞을 지나지 않는다)
    for i in range(4):
        parts.append({
            "id": f"rock{i + 1}", "model": f"augsky:boss/{BOSS}_rock_{'a' if i % 2 == 0 else 'b'}",
            "offset": [0, 0, 0], "scale": S, "rotation": [0, 0, 0], "frame": "world",
            "anims": [{"type": "orbit", "radius": ORBIT_R, "speed": 1.8, "phase": i * 90, "height": ORBIT_H},
                      {"type": "spin", "axis": "y", "speed": 4.0 if i % 2 == 0 else -5.0},
                      {"type": "bob", "amplitude": 0.2, "period": 40, "phase": i / 4}],
        })
    return parts


ORBIT_R, ORBIT_H = 4.6, 4.2

MODELS = {}   # build() 가 마지막으로 지은 조각 모델 (미리보기용)


def build(assets_root):
    models = {
        "torso": build_torso(assets_root),
        "right_shoulder": build_shoulder(assets_root, -1),
        "left_shoulder": build_shoulder(assets_root, +1),
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
        "notes": (
            "화염 거신 (복셀): 1 복셀 = 1/8 블록 (모든 조각 vox 1.0, scale 2.0), 몸 조각 오프셋은 모두 1/8 블록의 배수라 큐브 격자가 "
            "조각 사이에서 이어진다. 피벗 = 모델 (8,8,8). 앞=+Z, 오른손=-X. "
            "torso=가슴 핵 가운데(y 3.0; 몸통 y 2.13..4.25, x ±1.38), shoulders=어깨 관절(몸통에서 옆 1.25·위 0.63블록, 바깥 끝 x ±2.38, 위 끝 y 4.5), "
            "head=목 밑동(y 4.38 = 몸통 위 끝보다 2칸 위, 0.38 앞; 그 틈에 마그마 목이 빛난다. 눈 높이 y≈5.3..5.4, 정수리 6.1, 뿔 끝 6.9), "
            "tail/tail_low=허리 밑 바위 덩어리 탑(폭 10 / 6·4·2, 맨 아래 y 0.25, bob 0.1 → 가장 낮을 때도 바닥 위 0.15), "
            "fists=손목 피벗 (±2.38, 3.25, +1.25): 주먹 몸통 y 1.63..3.13, x ±1.25..3.25, z 0.6..2.1 — 가슴 높이, 어깨선 앞. "
            "swing 은 -X(앞-위로 올려 치기): 오른손 -75도/12틱, 왼손 -60도/10틱 (Rigs.swing 재무장 12틱 이내) → 정점에서 주먹 바닥(마디·손가락·엄지 면)이 앞을 향한다. "
            f"rocks=world 프레임 orbit 한 고리 (반지름 {ORBIT_R}, 발 기준 높이 {ORBIT_H}, 넷이 90도 간격). "
            "빛 순서: core(흰-노랑 fire)=눈 > lava(깊은 주황-빨강 flow 홈) > magma(pulse, 틈/입) > ember(주먹 금, 고정). "
            "미리보기: inferno_colossus_voxel*.png 는 깊이 버퍼 렌더(정확), *_mc3d.png 는 wkit.rig_preview/mc3d.render(면 정렬 오류 있음)."),
    }
    MODELS.clear()
    MODELS.update(models)
    return spec


def write_rig(spec):
    with open(os.path.join(HERE, MODULE + ".rig.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)


def shown_spec(spec, orbit_deg=25):
    """미리보기용: 도는 바위를 궤도의 한 순간에 놓는다."""
    shown = {"boss": BOSS, "parts": []}
    for p in spec["parts"]:
        q = dict(p)
        orb = next((a for a in p["anims"] if a["type"] == "orbit"), None)
        if orb:
            ang = math.radians(orb["phase"] + orbit_deg)
            q["offset"] = [orb["radius"] * math.cos(ang), orb["height"], orb["radius"] * math.sin(ang)]
        shown["parts"].append(q)
    return shown


def by_id(spec):
    out = {}
    for p in spec["parts"]:
        key = p["model"].split(f"{BOSS}_", 1)[1]
        out[p["id"]] = MODELS[key]
    return out


def previews(spec, out_dir):
    from mc3d import render, contact_sheet
    models = MODELS
    shown = shown_spec(spec)
    ids = by_id(spec)
    zmain(shown, ids, os.path.join(out_dir, f"{BOSS}_voxel.png"), NAME_KO)
    zrig(shown, ids, os.path.join(out_dir, f"{BOSS}_voxel_hq.png"), NAME_KO)
    rig_preview(shown, ids, os.path.join(out_dir, f"{BOSS}_voxel_mc3d.png"), NAME_KO)
    bg = (28, 26, 36, 255)
    for fn, tag in ((zrender, ""), (render, "_mc3d")):
        imgs, labels = [], []
        for key, views in (("torso", ((-30, 12), (150, 15))), ("head", ((-30, 8), (0, 2))),
                           ("left_shoulder", ((-40, 12),)), ("right_shoulder", ((40, 12),)),
                           ("left_fist", ((-40, 10), (0, 5), (-20, -60))), ("right_fist", ((30, 10),)),
                           ("tail", ((-30, 8),)), ("tail_low", ((-30, 8),)), ("rock_a", ((-30, 18),)), ("rock_b", ((-30, 12),))):
            m = models[key]
            for (yaw, pitch) in views:
                imgs.append(fn([(m, None)], size=360, yaw=yaw, pitch=pitch, bg=bg))
                labels.append(f"{key} ({len(m.elements)})" + (" 밑면" if pitch < -30 else ""))
        contact_sheet(imgs, labels, cols=4, cell=360, font=FONT if os.path.exists(FONT) else None).save(
            os.path.join(out_dir, f"{BOSS}_voxel_parts{tag}.png"))
    # 예전 이름으로 남은 파일은 지운다 (헷갈리지 않게)
    old = os.path.join(out_dir, f"{BOSS}_voxel_parts_hq.png")
    if os.path.exists(old):
        os.remove(old)


if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
    spec = build(root)
    write_rig(spec)
    total = 0
    for k, m in MODELS.items():
        print(f"{k:14s} {len(m.elements):4d} elements")
    for p in spec["parts"]:
        key = p["model"].split(f"{BOSS}_", 1)[1]
        total += len(MODELS[key].elements)
    print("whole boss (all displays):", total)
    previews(spec, os.path.join(HERE, "preview"))
