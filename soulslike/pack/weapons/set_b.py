"""
무기 모형 B 묶음 (weapons/SPEC.md 4절): 자루 무기와 판자 방패, 손종. 3D 복셀 (wkit) + 손으로 찍은 16px 그림.

  levy_hatchet      레딘 징집병 손도끼        (3.5)
  sellsword_axe     볼크 가 고용병 도끼        (3.6)
  gaoler_club       볼크 간수의 곤봉           (3.7)
  penitent_mace     오스윈 고행승의 철퇴       (3.8)
  mathes_bell_mace  마테스의 종 철퇴           (3.9)
  redin_spear       레딘 창병의 창             (3.10)
  hrolf_halberd     흐롤프의 미늘창            (3.11, 보스 흐롤프가 드는 것과 같은 모형)
  warden_halberd    교구 수호병의 미늘창       (3.12)
  plank_shield      탑옥 판자 방패             (3.14)
  pilgrim_handbell  오스윈 순례자의 손종       (3.20)

  python3 pack/weapons/set_b.py [id ...]   미리보기: dist/screenshots/weapons/<id>_{gui,side,fp,tp}.png 와
                                           pack/preview/weapons_b.png (한 장에 모두). 팩에 쓰는 것은 build(out) (gen_pack)

좌표 (SPEC 1.2)
  설계 원점 = 쥐는 점 = 모형 (8, 8, 8). 1 복셀 = 1/32 블록. +Y 끝, −Y 자루 끝, −X 날 (도끼날, 미늘창 날),
  +X 등 (납작머리, 가시, 갈고리), +Z 앞면 (인벤토리 그림의 기준 면, 동전·구멍·패를 두는 면).
  이 파일의 상자 도우미 (vb, v) 는 복셀 모서리 좌표를 쓴다: vb(w, x0, x1, ...) 는 아래 모서리가 x0 이상 x1 미만인 복셀.
  굵기 3 인 자루는 x, z 가 [−2, 1) 이다 (가운데 −0.5, 쥐는 점에서 반 복셀 = 1/64 블록 비껴 있다). 홀수 굵기는 모두
  가운데가 −0.5 라 자루와 머리가 한 줄에 선다.

손 자세는 _common.hand_display / guard_display / shield_display / catalyst_display (SPEC 1.3) 를 그대로 쓴다.
재료는 _mats.py (B 가 낸 손으로 찍은 칸), 격자는 _mats.VoxWeapon (Z 칸 경계를 옮겨 요소를 아낀다).
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
ROOT = os.path.dirname(PACK)
if PACK not in sys.path:
    sys.path.insert(0, PACK)

from weapons import _common as cm  # noqa: E402
from weapons._mats import VoxWeapon, mats  # noqa: E402

ICONS = os.path.join(PACK, "art", "weapon_icons_b.txt")
SHOTS = os.path.join(ROOT, "dist", "screenshots", "weapons")


# ─────────────────────────── 도우미 (복셀 모서리 좌표) ───────────────────────────

def g2(w):
    """앞에서 본 2D 격자 (복셀 가운데 X, Y)."""
    return w._X[:, :, 0], w._Y[:, :, 0]


def vb(w, x0, x1, y0, y1, z0, z1, m):
    """아래 모서리가 [x0, x1) × [y0, y1) × [z0, z1) 인 복셀."""
    return w.fill(lambda X, Y, Z: (X > x0) & (X < x1) & (Y > y0) & (Y < y1) & (Z > z0) & (Z < z1), m)


def v(w, x, y, z, m):
    """복셀 하나 (아래 모서리 x, y, z). m 이 None 이면 비운다."""
    w.grid[x + w.CX, y + w.CY, z + w.CZ] = w._id(m) if m else 0


def vs(w, cells, m):
    for x, y, z in cells:
        v(w, x, y, z, m)


def front_z(w, x, y, side=1):
    """그 (x, y) 열에서 가장 앞 (side 1: +Z, −1: −Z) 복셀의 z. 없으면 None."""
    col = w.grid[x + w.CX, y + w.CY, :]
    nz = np.nonzero(col)[0]
    if not len(nz):
        return None
    return int((nz[-1] if side > 0 else nz[0]) - w.CZ)


def get(w, x, y, z):
    k = w.grid[x + w.CX, y + w.CY, z + w.CZ]
    return w.names[k - 1] if k else None


def extrude(w, m2, z0, z1, mat):
    """2D 마스크 (W, H) 를 Z [z0, z1) 로 세운다. z0, z1 은 숫자나 (W, H) 배열."""
    z0 = np.broadcast_to(np.asarray(z0, float), m2.shape)[:, :, None]
    z1 = np.broadcast_to(np.asarray(z1, float), m2.shape)[:, :, None]
    sel = np.asarray(m2, bool)[:, :, None] & (w._Z > z0) & (w._Z < z1)
    w.grid[sel] = w._id(mat)


def paint(w, m3, mat, only=None):
    """이미 있는 복셀만 칠한다. only: 이 재료들인 복셀만."""
    sel = np.asarray(m3, bool) & (w.grid > 0)
    if only:
        sel &= np.isin(w.grid, [w._id(o) for o in only])
    w.grid[sel] = w._id(mat)


def solid(w):
    return w.grid > 0


def exposed_dir(w, axis, sign):
    """그 방향 이웃이 비어 있는 복셀 (axis 0 x, 1 y, 2 z; sign +1/−1)."""
    s = solid(w)
    nb = np.zeros_like(s)
    if sign > 0:
        sl_dst = [slice(None)] * 3
        sl_src = [slice(None)] * 3
        sl_dst[axis] = slice(0, -1)
        sl_src[axis] = slice(1, None)
        nb[tuple(sl_dst)] = s[tuple(sl_src)]
    else:
        sl_dst = [slice(None)] * 3
        sl_src = [slice(None)] * 3
        sl_dst[axis] = slice(1, None)
        sl_src[axis] = slice(0, -1)
        nb[tuple(sl_dst)] = s[tuple(sl_src)]
    return s & ~nb


def mat_is(w, *names):
    return np.isin(w.grid, [w._id(n) for n in names if n in w.mats])


def rod(w, y0, y1, mat, half=None):
    """굵기 3 자루 (x, z ∈ [−2, 1)). half: (x0, x1, z0, z1) 로 바꿀 수 있다."""
    x0, x1, z0, z1 = half or (-2, 1, -2, 1)
    return vb(w, x0, x1, y0, y1, z0, z1, mat)


def ring(w, y0, y1, mat, r=3):
    """자루를 감는 테: 굵기 r 의 네모 테에서 네 모서리를 뺀다 (r 홀수, 가운데 −0.5)."""
    a = (r - 1) // 2
    lo, hi = -1 - a, a
    vb(w, lo, hi, y0, y1, lo + 1, hi - 1, mat)
    vb(w, lo + 1, hi - 1, y0, y1, lo, hi, mat)


# ─────────────────────────── 3.5 레딘 징집병 손도끼 ───────────────────────────

def columns(w, cols, zspan, mat):
    """옆모습을 열마다 손으로: cols = {x: (y 아래, y 위)} (둘 다 포함하는 복셀 줄), zspan(x) → (z0, z1)."""
    for x, (ylo, yhi) in cols.items():
        z0, z1 = zspan(x)
        vb(w, x, x + 1, ylo, yhi + 1, z0, z1, mat)


def levy_hatchet():
    """
    장작 패는 손도끼에 쇠를 조금 더 댔다. 쐐기꼴 작은 머리: 위 선은 곧고, 아래 선은 눈 밑에서 허리로 올라갔다가
    날 쪽으로 처져 턱이 된다. 날 (−X) 은 눈에서 6 복셀, 등 (+X) 은 2 복셀 납작머리. 두께는 눈 5 → 허리 3 → 날 1.
    하나뿐인 것: 머리 아래 자루 앞뒤에 박은 쇠띠 (랑겟) 둘과 리벳 셋 (앞 둘은 머리가 튀어나온다, 뒤 하나).
    """
    w = VoxWeapon(mats("iron", "iron_hi", "steel", "steel_b", "edge", "rust", "wood", "wood_worn", "cord", "dark"),
                  seed=501)
    # 자루: 곧은 나무 3×3, 아래 끝 두 줄이 +X 로 한 복셀 굵다 (발)
    rod(w, -6, 15, "wood")
    vb(w, 1, 2, -6, -4, -2, 1, "wood")
    paint(w, (w._Y > -4) & (w._Y < 5), "wood_worn")             # 손 닿는 곳이 한 단 밝다
    # 머리 옆모습 (열마다 아래·위 줄)
    cols = {3: (9, 14), 2: (9, 14), 1: (8, 14), 0: (8, 14), -1: (8, 14), -2: (8, 14), -3: (8, 14),
            -4: (9, 13), -5: (9, 13), -6: (9, 14), -7: (8, 14), -8: (7, 14), -9: (6, 15), -10: (7, 15)}
    columns(w, cols, lambda x: (-3, 2) if x >= -3 else (-2, 1) if x >= -8 else (-1, 0), "steel_b")
    rod(w, 8, 15, "wood")                                       # 눈 안의 자루 (윗면에 끝이 보인다)
    vb(w, -2, 1, 14, 15, -1, 0, "dark")                         # 쐐기 자국
    # 눈과 납작머리는 불에 그을린 검은 쇠, 날 쪽은 갈아 낸 강철. 경계는 고르지 않다
    paint(w, w._X > -3, "iron", only=("steel_b",))
    vs(w, [(-4, 13, 1), (-4, 14, 1), (-4, 12, 1), (-4, 9, 1), (-5, 14, 1), (-4, 13, -3)], None)
    vs(w, [(-4, 14, 0), (-4, 13, 0), (-5, 14, 0), (-4, 9, 0), (-4, 10, 0)], "iron")
    paint(w, w._X < -8, "steel", only=("steel_b",))
    paint(w, exposed_dir(w, 0, -1) & (w._X < -8), "edge")
    # 이 빠짐 둘 (가운데 위쪽 두 줄, 아래쪽 한 줄): 날 끝 줄이 끊기고 안쪽 강철이 보인다
    vs(w, [(-10, 12, -1), (-10, 11, -1), (-10, 8, -1)], None)
    # 빛 받는 위 모서리 한 줄 (검은 쇠 위만)
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 13), "iron_hi", only=("iron",))
    # 녹: 눈과 허리가 만나는 앞면, 납작머리 밑
    vs(w, [(-4, 10, 0), (-5, 9, 0), (-3, 8, 1), (-3, 9, 1), (-2, 8, 1)], "rust")
    vs(w, [(2, 9, 1), (3, 9, 1), (3, 9, 0), (3, 10, 1)], "rust")
    # 쇠띠 둘 (앞 +Z, 뒤 −Z) 과 리벳 셋: 앞 둘은 머리가 한 복셀 더 나온다
    vb(w, -1, 0, 2, 8, 1, 2, "iron")
    vb(w, -1, 0, 3, 8, -3, -2, "iron")
    vs(w, [(-1, 6, 2), (-1, 3, 2), (-1, 5, -4)], "iron_hi")
    # 자루 끝 끈 고리 (발에 뚫은 구멍으로)
    vs(w, [(-1, -7, -1), (-2, -8, -1), (0, -8, -1), (-2, -9, -1), (0, -9, -1), (-1, -10, -1)], "cord")
    return w


def disc(w, y0, y1, r, mat, cx=-0.5, cz=-0.5, octagon=False):
    """가운데 (cx, cz) 둘레 둥근 단면 (반지름 r, 복셀 가운데까지 잰다). 가운데 −0.5 면 홀수 폭."""
    if octagon:
        fn = lambda X, Y, Z: ((np.abs(X - cx) <= r) & (np.abs(Z - cz) <= r) & (np.abs(X - cx) + np.abs(Z - cz) <= r * 1.42)
                              & (Y > y0) & (Y < y1))
    else:
        fn = lambda X, Y, Z: (((X - cx) ** 2 + (Z - cz) ** 2 <= r * r) & (Y > y0) & (Y < y1))
    return w.fill(fn, mat)


def band(w, y0, y1, mat, r=2.0):
    """자루를 감는 쇠테·감기: 가운데 −0.5 둘레 네모 테에서 모서리를 뺀 것 (r 2 → 폭 5)."""
    return w.fill(lambda X, Y, Z: ((np.abs(X + 0.5) <= r) & (np.abs(Z + 0.5) <= r) & (np.abs(X + 0.5) + np.abs(Z + 0.5) <= r + 0.5)
                                   & (Y > y0) & (Y < y1)), mat)


# ─────────────────────────── 3.6 볼크 가 고용병 도끼 ───────────────────────────

def sellsword_axe():
    """
    수염 도끼. 눈 (8 줄) 에서 좁은 목을 지나 날 (−X) 이 넓어지고, 아래로 수염이 늘어진다 (날 끝 높이 13, 자루에서 9).
    등 (+X) 에 짧은 네모 가시. 자루 아래 10 복셀 가죽 (한 곳이 닳아 나무가 보인다), 쇠 마개.
    하나뿐인 것: 머리 앞면 (+Z) 에 박은 볼크 가 청동 동전 하나 (2×2, 사슬 고리 1 픽셀).
    """
    w = VoxWeapon(mats("iron", "iron_hi", "steel_b", "steel", "edge", "rust", "wood_dark", "leather", "bronze_hi",
                       "bronze", "dark"), seed=601)
    rod(w, -5, 25, "wood_dark")
    band(w, -6, -4, "iron")                                       # 쇠 마개
    rod(w, -7, -6, "iron")
    rod(w, -4, 6, "leather")
    vs(w, [(-1, 1, 0), (-1, 2, 0), (0, 2, 0)], "wood_dark")       # 닳아 벗겨진 곳
    # 머리 옆모습: 눈 (16..23), 좁은 목, 넓어지는 날과 아래로 늘어진 수염
    cols = {1: (16, 23), 0: (16, 23), -1: (16, 23), -2: (16, 23), -3: (16, 23),
            -4: (18, 22), -5: (19, 22), -6: (18, 22), -7: (17, 23), -8: (15, 23), -9: (14, 24),
            -10: (12, 24), -11: (13, 24)}
    columns(w, cols, lambda x: (-3, 2) if x >= -3 else (-2, 1) if x >= -9 else (-1, 0), "steel_b")
    paint(w, w._X > -3.5, "iron", only=("steel_b",))
    vs(w, [(-4, 21, 0), (-4, 20, 0), (-4, 18, 0)], "iron")
    rod(w, 16, 24, "wood_dark")
    vb(w, -2, 1, 23, 24, -1, 0, "dark")
    # 등 가시 (네모, 3 복셀)
    vb(w, 2, 3, 18, 22, -2, 1, "iron")
    vb(w, 3, 4, 19, 21, -2, 1, "iron")
    vb(w, 4, 5, 19, 20, -1, 0, "iron")
    # 갈린 자리와 날 끝 줄 (수염의 아래 끝까지)
    paint(w, w._X < -9.5, "steel", only=("steel_b",))
    paint(w, exposed_dir(w, 0, -1) & (w._X < -9.5), "edge")
    paint(w, exposed_dir(w, 1, -1) & (w._X < -9.5), "edge")
    # 이 빠짐 셋, 수염 끝 한 복셀 떨어져 나감
    vs(w, [(-11, 21, -1), (-11, 18, -1), (-11, 17, -1), (-11, 14, -1)], None)
    vs(w, [(-10, 12, -1)], None)
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 21.5), "iron_hi", only=("iron",))
    # 녹: 눈 아래, 가시 뿌리, 목
    vs(w, [(-3, 16, 1), (-2, 16, 1), (-3, 17, 1), (2, 18, 0), (2, 19, 0), (-5, 19, 0), (-6, 18, 0)], "rust")
    # 볼크 동전 (앞면에 박았다): 2×2 밝은 청동, 사슬 고리 1 픽셀
    vb(w, -8, -6, 19, 21, 1, 2, "bronze_hi")
    v(w, -7, 20, 1, "bronze")
    return w


# ─────────────────────────── 3.7 볼크 간수의 곤봉 ───────────────────────────

def gaoler_club():
    """
    참나무 몽둥이. 손잡이 굵기 3 에서 머리 굵기 7 로 굵어지고 끝이 둥글다. 쇠테 셋 (+12, +16, +20) 은 나무와 거의 같은
    높이로 박혀 네 면에서만 조금 나온다. 테 사이에 네모 징 대가리 (고르지 않게). 머리 나무에 쪼개진 금 하나,
    가운데 테는 +X 쪽이 벌어져 들떴다. 손잡이는 맨나무, 오래 쥔 곳이 반들하다.
    하나뿐인 것: 자루 끝의 쇠 걸쇠 (허리띠에 거는 갈고리, −Y 로 3 복셀 내려가 +X 로 굽어 올라간다).
    """
    w = VoxWeapon(mats("wood", "wood_worn", "iron", "iron_hi", "rust", "dark"), seed=701)

    def radius(y):
        if y < 3:
            return 1.0
        if y < 11:
            return 1.0 + (y - 3) / 4.0
        if y < 20:
            return 3.0
        return {20: 2.4, 21: 1.6}.get(int(y), 0.0)

    def oct_(r, y):
        return lambda X, Y, Z: ((np.abs(X + 0.5) <= r) & (np.abs(Z + 0.5) <= r)
                                & (np.abs(X + 0.5) + np.abs(Z + 0.5) <= r * 1.5) & (Y > y) & (Y < y + 1))

    for y in range(-6, 22):
        r = radius(y + 0.5)
        if r >= 0.5:
            w.fill(oct_(r, y), "wood")
    paint(w, (w._Y > -5) & (w._Y < 5), "wood_worn")
    # 쇠테: 바깥 한 겹을 쇠로, 네 면 가운데에서만 한 복셀 나온다
    for y in (12, 16, 20):
        r = radius(y + 0.5)
        sel = oct_(r, y)(w._X, w._Y, w._Z) & ~oct_(r - 1.0, y)(w._X, w._Y, w._Z)
        w.grid[sel] = w._id("iron")
        d = int(r) + 1
        for a in (-1, 0, 1):
            for (x, z) in ((-1 + d, -1 + a), (-1 - d, -1 + a), (-1 + a, -1 + d), (-1 + a, -1 - d)):
                v(w, x, y, z, "iron")
    # 가운데 테의 +X 쪽이 벌어져 들떴다 (나무와 사이에 틈)
    vs(w, [(3, 16, -2), (3, 16, -1), (3, 16, 0)], "dark")
    vs(w, [(4, 16, -2), (4, 16, -1), (4, 16, 0), (4, 16, 1)], "iron")
    vs(w, [(3, 16, 1), (3, 16, -3)], "iron")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron"), "iron_hi")
    # 네모 징 대가리 (테 사이 네 면, 고르지 않게): 한 복셀 나온다
    for x, y, z in ((-1, 14, 3), (-5, 18, -1), (3, 13, -2), (0, 18, 3), (-2, 14, -5), (3, 18, 0)):
        v(w, x, y, z, "iron")
    # 쪼개진 금 (앞면, 손잡이 위에서 테 사이로)
    for x, y in ((0, 8), (0, 9), (0, 10), (-1, 11), (-1, 13), (-1, 14), (0, 15)):
        z = front_z(w, x, y)
        if z is not None:
            v(w, x, y, z, "dark")
    # 녹: 테 아래 나무 물든 곳
    for x, y in ((-3, 11), (-2, 11), (1, 19), (-4, 15)):
        z = front_z(w, x, y)
        if z is not None:
            v(w, x, y, z, "rust")
    # 쇠 걸쇠: 자루 끝 쇠고리 + J 갈고리 (끝이 위로, 고리 밑과 두 복셀 떨어져 허리띠가 걸린다)
    band(w, -6, -4, "iron", r=2.0)
    vb(w, -1, 0, -9, -6, -1, 0, "iron")
    vs(w, [(0, -10, -1), (1, -10, -1), (2, -9, -1), (2, -8, -1)], "iron")
    v(w, 2, -8, -1, "iron_hi")
    return w


# ─────────────────────────── 3.8 오스윈 고행승의 철퇴 ───────────────────────────

def penitent_mace():
    """
    짧은 쇠자루에 날개 철퇴 머리 (가운데 몸 굵기 3, 날개 끝 지름 9, 날개 여덟: 앞에서 넷이 보인다). 날개는 손으로 두드려
    높이와 길이가 조금씩 다르고, +X 날개 위 끝이 앞으로 휘었다. 위에 작은 꼭지. 손잡이는 거친 삼끈.
    하나뿐인 것: 머리 바로 아래 자루에 감아 맨 매듭 셋의 고행 끈, 끝이 −X 로 늘어진다.
    """
    w = VoxWeapon(mats("iron", "iron_hi", "iron_edge", "rust", "cord", "string"), seed=801)
    rod(w, -6, 20, "iron")
    band(w, -7, -5, "iron")                                     # 자루 끝 혹
    rod(w, -5, 5, "cord")
    band(w, 4, 5, "cord")
    # 꼭지
    vs(w, [(-1, 20, -1), (-2, 20, -1), (0, 20, -1), (-1, 20, -2), (-1, 20, 0), (-1, 21, -1)], "iron")
    # 날개 여덟: (방향, {y: 바깥 거리}). 옆모습은 둥근 렌즈꼴. 축 날개는 거리 = 복셀 수, 대각선은 계단 칸 수.
    # 날개마다 높이와 길이가 조금씩 다르다 (손으로 두드린 것). 위쪽 반의 바깥 끝만 닳아 밝다
    ax = {12: 1, 13: 2, 14: 3, 15: 4, 16: 4, 17: 4, 18: 3, 19: 2}
    flanges = [((1, 0), {**ax, 13: 3, 18: 4}), ((-1, 0), ax), ((0, 1), {**ax, 12: 0, 17: 3}),
               ((0, -1), {**ax, 14: 4, 19: 1}), ((1, 1), {13: 1, 14: 2, 15: 3, 16: 3, 17: 2, 18: 2, 19: 1}),
               ((-1, 1), {13: 1, 14: 2, 15: 2, 16: 3, 17: 3, 18: 2}), ((1, -1), {13: 2, 14: 2, 15: 3, 16: 3, 17: 2, 18: 1}),
               ((-1, -1), {13: 1, 14: 2, 15: 3, 16: 3, 17: 3, 18: 2, 19: 1})]
    for (dx, dz), reach in flanges:
        for y, n in reach.items():
            for k in range(1, n + 1):
                lit = k == n and y >= 15 and n >= 3
                if dx and dz:
                    v(w, -1 + dx * k, y, -1 + dz * k, "iron_edge" if lit else "iron")
                    if k > 1:
                        v(w, -1 + dx * k, y, -1 + dz * (k - 1), "iron")
                else:
                    v(w, -1 + dx * (k + 1), y, -1 + dz * (k + 1), "iron_edge" if lit else "iron")
    # +X 날개 위 끝이 앞으로 휘었다
    vs(w, [(4, 18, -1), (3, 19, -1), (4, 19, -1)], None)
    vs(w, [(3, 18, 0), (3, 19, 0)], "iron_edge")
    # 날개 뿌리 녹
    vs(w, [(1, 12, -1), (-1, 13, 1), (-3, 13, -1), (1, 14, 0), (-1, 19, -3), (0, 18, 0)], "rust")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron") & (w._Y > 11), "iron_hi")
    # 고행 끈: 머리 밑 감기 + 매듭 셋을 지어 −X 로 늘어진 끝
    band(w, 10, 12, "string", r=1.5)
    vs(w, [(-4, 10, -1), (-4, 9, -1), (-5, 8, -1), (-5, 7, -1), (-6, 6, -1)], "string")
    for x, y in ((-4, 10), (-5, 8), (-6, 6)):
        vs(w, [(x, y, 0), (x, y, -2)], "string")
    return w


# ─────────────────────────── 3.9 마테스의 종 철퇴 ───────────────────────────

def mathes_bell_mace():
    """
    쇠테 두른 참나무 자루 위에 입이 손 쪽 (−Y) 을 보는 작은 청동 종 (높이 10, 입술 지름 11, 허리 7, 정수리 5), 정수리에
    매달던 고리. 입 안은 납으로 메웠다 (입술에서 한 복셀 들어가 있다). 입술 찌그러짐 둘, 녹청은 입술과 소리 둘레 홈에만.
    하나뿐인 것: 종 앞면을 입술에서 위로 타고 오른 금 한 줄 (종 높이의 2/3, 한 번 꺾인다).
    """
    w = VoxWeapon(mats("wood", "leather", "iron", "iron_hi", "rust", "bronze", "bronze_hi", "verdigris", "lead", "dark"),
                  seed=901)
    rod(w, -6, 18, "wood")
    rod(w, -5, 5, "leather")
    band(w, -7, -5, "iron")                                     # 쇠 마개
    for y in (6, 11):                                           # 쇠테 둘
        band(w, y, y + 1, "iron")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron"), "iron_hi")
    vs(w, [(1, 6, -1), (1, 11, 0), (-3, 6, -2)], "rust")
    # 종: 입 17 (h 0) → 정수리 26 (h 9). 반지름 (복셀 가운데까지)
    prof = [5.1, 4.6, 4.0, 3.5, 3.4, 3.4, 3.3, 3.2, 3.0, 2.4]
    for h, r in enumerate(prof):
        disc(w, 17 + h, 18 + h, r, "bronze")
    disc(w, 27, 28, 1.5, "bronze")                              # 정수리 판
    # 입: 입술 고리만 남기고 한 복셀 파낸 뒤 납
    w.clear(lambda X, Y, Z: (Y > 17) & (Y < 18) & ((X + 0.5) ** 2 + (Z + 0.5) ** 2 < 4.0 ** 2))
    paint(w, (w._Y > 18) & (w._Y < 19) & ((w._X + 0.5) ** 2 + (w._Z + 0.5) ** 2 < 4.0 ** 2), "lead")
    rod(w, 16, 19, "wood")
    # 녹청: 입술 아래 모서리와 소리 둘레 (h 2) 바깥 몇 곳
    rr = (w._X + 0.5) ** 2 + (w._Z + 0.5) ** 2
    ang = np.degrees(np.arctan2(w._Z + 0.5, w._X + 0.5))
    paint(w, (w._Y > 17) & (w._Y < 18) & (rr > 4.4 ** 2) & ((ang % 97) < 40), "verdigris")
    paint(w, (w._Y > 19) & (w._Y < 20) & (rr > 3.4 ** 2) & ((ang % 71) < 22), "verdigris")
    # 입술 찌그러짐 둘
    vs(w, [(3, 17, 2), (3, 18, 2), (2, 17, 3)], None)
    vs(w, [(-6, 17, -2), (-6, 17, -1)], None)
    # 어깨는 손이 닿아 밝다 (왼쪽 위 빛 쪽)
    paint(w, (w._Y > 23) & (w._Y < 27) & (w._X < 0) & (w._Z > -1.5), "bronze_hi", only=("bronze",))
    # 매달던 고리
    vs(w, [(-2, 28, -1), (-2, 29, -1), (-1, 29, -1), (0, 29, -1), (0, 28, -1)], "bronze")
    # 금: 앞면 (+Z) 입술에서 위로 7 줄, 한 번 꺾인다
    for x, y in ((1, 17), (1, 18), (1, 19), (0, 20), (0, 21), (0, 22), (-1, 23)):
        z = front_z(w, x, y)
        if z is not None:
            v(w, x, y, z, "dark")
    return w


# ─────────────────────────── 3.10 레딘 창병의 창 ───────────────────────────

def redin_spear():
    """
    곧은 자루 (굵기 3) 끝에 버들잎 창날 (길이 12, 가장 넓은 곳 5, 가운데 등줄), 소켓 아래로 짧은 쇠띠 둘, 뾰족한 물미.
    창끝은 날카롭고 날에 이 빠짐 하나. 자루 아래쪽은 흙때 (곧은 경계), 쥐는 자리에 가죽 한 감기.
    하나뿐인 것: 소켓 아래 묶은 바랜 붉은 천 한 가닥 (−X 로 늘어진다).
    """
    w = VoxWeapon(mats("wood", "mud", "leather", "iron", "iron_hi", "rust", "steel", "steel_b", "edge", "cloth_red"),
                  seed=1001)
    rod(w, -19, 31, "wood")
    paint(w, w._Y < -9, "mud", only=("wood",))
    rod(w, -5, 5, "leather")
    # 물미: 쇠 깍지와 끝
    rod(w, -21, -17, "iron")
    band(w, -18, -17, "iron")
    vb(w, -1, 0, -22, -21, -1, 0, "iron")
    vs(w, [(-1, -21, -2), (-2, -21, -1), (0, -21, -1), (-1, -21, 0)], "iron")
    # 소켓: 30..34, 위로 가늘어진다
    band(w, 29, 32, "iron")
    rod(w, 32, 35, "iron")
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 31) & (w._Y < 32), "iron_hi")
    # 소켓 아래 쇠띠 둘 (앞뒤) 과 못
    vb(w, -1, 0, 25, 29, 1, 2, "iron")
    vb(w, -1, 0, 25, 29, -3, -2, "iron")
    vs(w, [(-1, 26, 1), (-1, 26, -3)], "iron_hi")
    vs(w, [(-1, 30, 1), (0, 29, 1), (-2, 31, -3)], "rust")
    # 버들잎 날: 줄마다 폭 (홀수, 가운데 −0.5)
    widths = {35: 3, 36: 3, 37: 5, 38: 5, 39: 5, 40: 5, 41: 3, 42: 3, 43: 3, 44: 3, 45: 1, 46: 1}
    for y, wd in widths.items():
        a = (wd - 1) // 2
        vb(w, -1 - a, a, y - 1, y, -1, 0, "steel")                  # 납작한 몸 (두께 1)
        vb(w, -1, 0, y - 1, y, -2, 1, "steel_b")                    # 가운데 등줄 (두께 3)
    vb(w, -1, 0, 44, 46, -1, 0, "steel")
    paint(w, (exposed_dir(w, 0, -1) | exposed_dir(w, 0, 1)) & (w._Y > 35) & (w._Y < 45), "edge", only=("steel",))
    v(w, -4, 38, -1, None)                                          # 이 빠짐
    # 붉은 천: 소켓 아래 두 번 감고 −X 로 늘어진 끝 (바래서 한 쪽 끝이 갈라졌다)
    band(w, 27, 29, "cloth_red")
    vs(w, [(-4, 27, -1), (-5, 27, -1), (-5, 26, -1), (-6, 26, -1), (-6, 25, -1), (-7, 25, -1), (-4, 28, -1),
           (-5, 28, -1), (-6, 27, -1), (-7, 24, -1), (-8, 24, -1), (-8, 26, -1)], "cloth_red")
    return w


# ─────────────────────────── 3.11 흐롤프의 미늘창 ───────────────────────────

def hrolf_halberd():
    """
    묵직한 미늘창. 넓은 도끼날 (−X, 날 끝 높이 14, 자루에서 10) 은 초승달처럼 휘어 위아래 뿔이 뒤로 젖는다.
    반대쪽 (+X) 에 아래로 굽은 갈고리, 꼭대기에 네모 송곳 (10, 끝이 무디다). 자루 위 1/4 을 쇠띠 둘 (랑겟) 이 감싼다.
    도끼날 가운데를 크게 한 입 베어 낸 이 빠짐 하나 (2×3) 와 작은 것 둘.
    하나뿐인 것: 갈고리 밑에 쇠사슬로 매단 커다란 성문 열쇠 (길이 8, 흔들리지 않는 한 덩이).
    보스 흐롤프의 인형도 이 모형을 그대로 든다 (SPEC 1.4, NONE 맥락 × 1.6).
    """
    w = VoxWeapon(mats("wood_dark", "leather", "iron", "iron_hi", "iron_edge", "steel_b", "steel", "edge", "rust"),
                  seed=1101)
    rod(w, -23, 31, "wood_dark")
    rod(w, -6, 6, "leather")
    # 물미
    band(w, -24, -21, "iron")
    rod(w, -26, -24, "iron")
    # 소켓 (28..37)
    band(w, 28, 37, "iron")
    # 랑겟 둘 (앞뒤, 15..28) 과 리벳
    vb(w, -1, 0, 15, 28, 1, 2, "iron")
    vb(w, -1, 0, 15, 28, -3, -2, "iron")
    for y in (17, 21, 25):
        vs(w, [(-1, y, 1), (-1, y + 1, -3)], "iron_hi")
    vs(w, [(-1, 19, 1), (-1, 20, 1), (-1, 23, -3)], "rust")
    # 도끼날 (−X): 열마다 아래·위. 목이 좁고 날 쪽으로 위아래 뿔
    cols = {-3: (31, 38), -4: (32, 37), -5: (32, 37), -6: (31, 38), -7: (30, 39), -8: (29, 40), -9: (28, 41),
            -10: (28, 41), -11: (29, 40), -12: (31, 38)}
    columns(w, cols, lambda x: (-2, 1) if x >= -6 else (-1, 0), "steel_b")
    paint(w, w._X > -4.5, "iron", only=("steel_b",))
    paint(w, w._X < -9.5, "steel", only=("steel_b",))
    edge = (exposed_dir(w, 0, -1) | ((exposed_dir(w, 1, 1) | exposed_dir(w, 1, -1)) & (w._X < -8.5))) & (w._X < -8.5)
    paint(w, edge, "edge", only=("steel", "steel_b"))
    # 크게 베어 낸 이 빠짐 (2×3) 과 작은 것 둘
    vs(w, [(-12, 33, -1), (-12, 34, -1), (-12, 35, -1), (-11, 33, -1), (-11, 34, -1), (-11, 35, -1)], None)
    vs(w, [(-12, 37, -1), (-11, 29, -1)], None)
    # 갈고리 (+X): 소켓에서 나와 아래로 굽는다
    hook = {2: (33, 37), 3: (33, 36), 4: (32, 35), 5: (31, 34), 6: (30, 33), 7: (29, 31), 8: (28, 29)}
    columns(w, hook, lambda x: (-2, 1) if x <= 4 else (-1, 0), "iron")
    vs(w, [(8, 28, -1), (7, 29, -1)], "iron_edge")
    # 네모 송곳 (37..46, 끝 무딤)
    rod(w, 37, 41, "iron")
    vb(w, -2, 1, 41, 44, -1, 0, "iron")
    vb(w, -1, 0, 41, 44, -2, 1, "iron")
    vb(w, -1, 0, 44, 46, -1, 0, "iron")
    paint(w, (w._Y > 37) & (w._X > -0.5) & (w._Z > -0.5), "iron_edge", only=("iron",))
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron") & (w._Y > 30), "iron_hi")
    vs(w, [(-3, 31, 0), (-3, 32, 0), (2, 33, 0), (-2, 37, 1), (3, 33, 0), (1, 28, -1)], "rust")
    # 쇠사슬과 열쇠: 갈고리 밑 (x 5) 에서 아래로
    vs(w, [(5, 30, -1), (4, 29, -1), (5, 28, -1), (4, 27, -1)], "iron")
    for x, y in ((3, 24), (4, 24), (5, 24), (3, 25), (5, 25), (3, 26), (4, 26), (5, 26)):
        v(w, x, y, -1, "rust" if (x, y) in ((5, 25), (3, 24)) else "iron")
    vb(w, 4, 5, 18, 24, -1, 0, "iron")                          # 대
    vs(w, [(5, 18, -1), (6, 18, -1), (6, 19, -1), (5, 20, -1), (6, 20, -1)], "iron")   # 이
    vs(w, [(4, 21, -1), (6, 19, -1)], "rust")
    return w


# ─────────────────────────── 3.12 교구 수호병의 미늘창 ───────────────────────────

def warden_halberd():
    """
    흐롤프 것보다 투박하고 무거운 칼날형 미늘창. 큰 날 (−X, 높이 17, 10 복셀) 은 위가 넓은 식칼꼴이라 위 모서리가
    뾰족하다. 등에 짧은 가시 (4), 꼭대기 송곳은 짧다 (4). 갈고리는 없다. 머리는 녹이 많다.
    물때 선: 머리와 자루가 Y 38 아래로 모두 한 단 어둡고 이끼빛이다. 경계는 그라데이션이 아니라 곧은 한 줄
    (교구가 물에 잠겼던 높이, 8.5). 손잡이 가죽은 썩어 몇 줄만 남았다.
    하나뿐인 것: 날에 뚫은 종 모양 구멍 (폭 5, 높이 6: 꼭지, 몸, 벌어진 입술. 명세의 4×5 보다 한 칸씩 키워 종으로 읽히게).
    """
    w = VoxWeapon(mats("wood", "wood_wet", "leather", "iron_rusty", "iron_wet", "iron_hi", "rust", "edge", "steel_b"),
                  seed=1201)
    rod(w, -28, 27, "wood")
    # 썩은 가죽: 몇 줄만 (고르지 않게)
    for y in (-5, -4, -1, 3):
        band(w, y, y + 1, "leather", r=1.5)
    vs(w, [(0, 0, 0), (-2, 1, -2), (0, 1, -1)], "leather")
    # 소켓 (26..42), 자루 끝은 쇠 테 하나
    band(w, 26, 42, "iron_rusty")
    band(w, -28, -26, "iron_rusty")
    # 큰 날: 위가 넓다
    cols = {-3: (31, 40), -4: (30, 40), -5: (29, 41), -6: (29, 41), -7: (28, 42), -8: (28, 42), -9: (28, 43),
            -10: (28, 43), -11: (28, 44), -12: (29, 45), -13: (31, 44)}
    columns(w, cols, lambda x: (-2, 1) if x >= -10 else (-1, 0), "iron_rusty")
    paint(w, exposed_dir(w, 0, -1) & (w._X < -11), "steel_b")
    vs(w, [(-13, 33, -1), (-13, 34, -1), (-13, 41, -1), (-12, 45, -1), (-13, 43, -1)], "edge")   # 갈린 자리 몇 곳만
    vs(w, [(-13, 37, -1), (-13, 31, -1)], None)                                                    # 이 빠짐
    # 종 모양 구멍 (폭 5, 높이 6): 정수리 꼭지 1, 몸 3 줄은 폭 3, 벌어진 입술 2 줄은 폭 5
    hole = [(-8, 39)] + [(x, y) for y in (36, 37, 38) for x in (-9, -8, -7)] + \
           [(x, y) for y in (34, 35) for x in (-10, -9, -8, -7, -6)]
    for x, y in hole:
        for z in (-2, -1, 0):
            v(w, x, y, z, None)
    # 등 가시 (+X, 4)
    spike = {2: (34, 38), 3: (35, 37), 4: (35, 36), 5: (35, 35)}
    columns(w, spike, lambda x: (-2, 1) if x <= 3 else (-1, 0), "iron_rusty")
    # 꼭대기 짧은 송곳 (42..46)
    rod(w, 42, 44, "iron_rusty")
    vb(w, -1, 0, 44, 46, -1, 0, "iron_rusty")
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 38), "iron_hi", only=("iron_rusty",))
    vs(w, [(-4, 40, 0), (-5, 41, 0), (-10, 43, 0), (2, 37, 0), (-11, 44, 0)], "rust")
    # 물때 선 (Y 38): 아래는 모두 물 먹은 재료
    low = w._Y < 38
    paint(w, low, "iron_wet", only=("iron_rusty", "iron_hi", "rust", "steel_b", "edge"))
    paint(w, low, "wood_wet", only=("wood",))
    paint(w, low & exposed_dir(w, 0, -1) & (w._X < -11), "iron_hi")      # 물 아래에서도 갈았던 날 끝은 한 단 밝다
    return w


# ─────────────────────────── 3.14 탑옥 판자 방패 ───────────────────────────

def plank_shield():
    """
    감방 문짝을 잘라 낸 네모 판 (폭 20, 높이 28, 판 두께 2 + 쇠띠 1). 세로 판자 셋 (폭 7, 5, 6) 사이 틈은 앞이 파인 홈,
    아래 끝은 도끼로 잘라 들쭉날쭉, 왼쪽 위 귀가 비스듬히 잘렸다. 가로 쇠띠 둘 (문 경첩 띠), 오른쪽 끝이 경첩 고리로 말렸다.
    뒷면 가운데 가로 쇠 손잡이 (감방 문 손잡이, 쥐는 점 = 손잡이 가운데) 와 팔을 끼우는 밧줄 고리, 뒷면에 손톱 긁힘.
    판 뒷면은 쥐는 점에서 Z +5 (A 의 방패와 같다): 팔이 쥐는 점에서 4 복셀까지 차 있어 그보다 가까우면 팔이 판을 뚫는다.
    하나뿐인 것: 앞면 위쪽의 들여다보는 구멍 (4×4) 과 쇠창살 두 줄.
    """
    w = VoxWeapon(mats("plank", "wood_dark", "iron", "iron_hi", "rust", "dark", "bone", "cord"), seed=1401)
    zb = 5                                                        # 판 뒷면
    # 판자 셋: (x0, x1, 아래 끝 (열마다), 재료)
    planks = [(-10, -3, [-13, -14, -14, -13, -12, -13, -13], "plank"),
              (-2, 3, [-12, -13, -13, -14, -13], "wood_dark"),
              (4, 10, [-14, -13, -12, -13, -14, -14], "plank")]
    for x0, x1, bottoms, m in planks:
        for i, x in enumerate(range(x0, x1)):
            vb(w, x, x + 1, bottoms[i], 14, zb, zb + 2, m)
    # 틈 (x −3, 3): 뒤 판만 남기고 앞은 판다
    for x in (-3, 3):
        vb(w, x, x + 1, -12, 14, zb, zb + 1, "dark")
    # 왼쪽 위 귀를 비스듬히 자른다
    for k in range(4):
        vb(w, -10, -10 + 4 - k, 13 - k, 14 - k, zb, zb + 2, None)
    # 판자 모서리 쪼개짐
    vs(w, [(9, 13, zb + 1), (9, 12, zb + 1), (-2, -12, zb + 1)], None)
    # 쇠띠 둘 (앞): 위 3..5, 아래 −9..−7. 오른쪽 끝은 경첩 고리 (판 밖으로 말려 나간다)
    zf = zb + 2
    for y0 in (3, -9):
        vb(w, -10, 10, y0, y0 + 2, zf, zf + 1, "iron")
        vb(w, 10, 11, y0, y0 + 2, zb, zf + 1, "iron")
        vb(w, 11, 12, y0, y0 + 2, zb + 1, zf, "iron")
        v(w, 11, y0, zb, "iron")
        v(w, 11, y0 + 1, zf, "iron")
        for x in (-7, -1, 6):                                     # 판자마다 못 하나 (나온 머리)
            v(w, x, y0 + (1 if x != -1 else 0), zf + 1, "iron_hi")
    vs(w, [(-9, 3, zf), (-8, 3, zf), (2, -9, zf), (3, -8, zf), (8, 4, zf), (9, 4, zf)], "rust")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron"), "iron_hi")
    # 들여다보는 구멍 (4×4) 과 쇠창살 두 줄
    vb(w, -2, 2, 7, 11, zb, zb + 2, None)
    for x in (-1, 1):
        vb(w, x, x + 1, 6, 12, zb + 1, zb + 2, "iron")
    vb(w, -3, 3, 11, 12, zb + 1, zf + 1, "iron")
    vb(w, -3, 3, 6, 7, zb + 1, zf + 1, "iron")
    # 뒷면 손잡이 (가로 쇠막대, 두 다리)
    vb(w, -3, 3, -1, 1, -1, 0, "iron")
    vb(w, -4, -3, -1, 1, -1, zb, "iron")
    vb(w, 3, 4, -1, 1, -1, zb, "iron")
    # 팔을 끼우는 밧줄 고리 (손잡이 위, 아래팔 둘레: |X|, |Z| ≤ 4 밖)
    for x in (-5, 4):
        vb(w, x, x + 1, 8, 9, -5, zb, "cord")
    vb(w, -5, 5, 8, 9, -5, -4, "cord")
    # 뒷면 손톱 긁힘 (bone0 짧은 세로 줄, 기울기가 다르다)
    for x, ys in ((-6, (4, 5, 6)), (-5, (3, 4)), (5, (5, 6, 7)), (6, (2, 3, 4)), (-1, (-5, -4, -3))):
        for y in ys:
            if get(w, x, y, zb):
                v(w, x, y, zb, "bone")
    # 썩은 얼룩 (아래쪽)
    vs(w, [(-8, -12, zb + 1), (-7, -12, zb + 1), (-7, -11, zb + 1), (5, -13, zb + 1), (6, -12, zb + 1)], "rust")
    return w


# ─────────────────────────── 3.20 오스윈 순례자의 손종 ───────────────────────────

def pilgrim_handbell():
    """
    짧은 나무 손잡이 (둥근 꼭지) 와 종 모양 청동 종 (높이 7, 입 지름 9): 둥근 어깨, 곧은 허리, 벌어진 입술.
    종 입이 +Y 끝을 보고 (앞으로 내밀어 흔든다), 입 밖으로 추가 한 복셀 보인다. 녹청 조금, 입술 찌그러짐 하나,
    청동은 손 닿는 어깨만 밝다.
    하나뿐인 것: 손잡이에 끈으로 맨 작은 순례 패 (2×3 주석 조각, 종 모양이 찍힌 오목 한 점).
    """
    w = VoxWeapon(mats("wood", "wood_worn", "bronze", "bronze_hi", "verdigris", "string", "tin", "iron_hi", "dark",
                       "iron"), seed=2001)
    rod(w, -4, 4, "wood_worn")
    band(w, -6, -4, "wood")                                     # 꼭지
    rod(w, -7, -6, "wood")
    # 종: 정수리 3 (h 0) → 입 9 (h 6). 반지름
    prof = [3.0, 3.3, 3.3, 3.3, 3.5, 4.0, 4.6]
    for h, r in enumerate(prof):
        disc(w, 3 + h, 4 + h, r, "bronze")
    disc(w, 2, 3, 1.6, "bronze")                                # 손잡이를 무는 목
    # 속을 비운다 (두께 1, 입 쪽부터)
    for h, r in enumerate(prof):
        if h >= 2:
            w.clear(lambda X, Y, Z, h=h, r=r: (Y > 3 + h) & (Y < 4 + h) & ((X + 0.5) ** 2 + (Z + 0.5) ** 2 < (r - 1.0) ** 2))
    disc(w, 4, 5, 1.6, "dark")                                  # 속 바닥 그늘
    # 추: 가운데 줄과 끝 (입 밖으로 한 복셀)
    vb(w, -1, 0, 5, 11, -1, 0, "iron")
    vs(w, [(-2, 9, -1), (0, 9, -1), (-1, 9, -2), (-1, 9, 0)], "iron")
    # 녹청 (입술 몇 곳), 어깨는 밝다, 입술 찌그러짐
    vs(w, [(3, 9, -1), (2, 9, 1), (-5, 9, -2), (-4, 8, 1), (-3, 9, -5)], "verdigris")
    paint(w, (w._Y > 3) & (w._Y < 6) & (w._X < 0), "bronze_hi", only=("bronze",))
    vs(w, [(-1, 9, 3), (0, 9, 3)], None)
    # 순례 패: 손잡이 위쪽에 끈을 감아 −X 로 늘어뜨린 주석 조각 (종 모양 찍힘 = 가운데 오목 한 점)
    band(w, 1, 2, "string", r=1.5)
    vs(w, [(-3, 1, -1), (-4, 1, -1), (-4, 0, -1)], "string")
    vb(w, -5, -3, -3, 0, -1, 0, "tin")
    v(w, -4, -2, -1, "iron_hi")
    return w


# ─────────────────────────── 목록 ───────────────────────────
# id: (만드는 함수, 분류 (FP_SCALE 열쇠), 쓰는 중 모형 "guard" | "block" | "same")
WEAPONS = {
    "levy_hatchet": (levy_hatchet, "hand_axe", "guard"),
    "sellsword_axe": (sellsword_axe, "axe", "guard"),
    "gaoler_club": (gaoler_club, "hammer", "guard"),
    "penitent_mace": (penitent_mace, "hammer", "guard"),
    "mathes_bell_mace": (mathes_bell_mace, "bell_mace", "guard"),
    "redin_spear": (redin_spear, "spear", "guard"),
    "hrolf_halberd": (hrolf_halberd, "halberd", "guard"),
    "warden_halberd": (warden_halberd, "halberd", "guard"),
    "plank_shield": (plank_shield, "shield", "block"),
    "pilgrim_handbell": (pilgrim_handbell, "catalyst", "same"),
}


def display_for(wid, kind, use):
    if use == "same":
        return cm.catalyst_display(*CATALYST_FP[wid])
    if use == "block":
        return cm.shield_display(*SHIELD_FP[wid])
    return cm.hand_display(kind)


def use_display_for(wid, kind, use):
    if use == "guard":
        return cm.guard_display(kind)
    if use == "block":
        return cm.shield_block_display(*SHIELD_BLOCK_FP[wid])
    return None


# 1인칭 회전·이동 (크기) [미확인 (클라)]. 3인칭은 _common 의 정한 값 (이동은 모두 같고 회전만 분류마다)
# 판자 방패는 A 의 경비대 방패 (shields_a.HEATER_FP, 높이 26) 와 같은 자세, 크기만 높이 28 에 맞춰 0.6
# 손종: 종이 화면 오른쪽 아래에 옆모습과 입술이 조금 보이게 세운다 (무기 1인칭 값이면 입 안만 보였다)
CATALYST_FP = {"pilgrim_handbell": ([-45, -75, 8], [0.2, 1.3, -0.8])}
SHIELD_FP = {"plank_shield": ([10, -35, 10], [-1.76, 0.0, -0.96], 0.6)}
SHIELD_BLOCK_FP = {"plank_shield": ([-40, 65, 120], [-0.53, 4.33, 0.4], 0.6)}


def icons():
    if not os.path.exists(ICONS):
        return {}
    return {k: cm.icon_image(rows, ink) for k, (rows, ink) in cm.load_icons(ICONS).items()}


def build(out, only=None, draft=False):
    """팩 폴더 out 에 B 묶음을 쓴다. 돌려주는 값 {id: write_item 결과}. draft: 그림이 없으면 빈 그림 (미리보기용)."""
    from PIL import Image
    ic = icons()
    made = {}
    for wid, (fn, kind, use) in WEAPONS.items():
        if only and wid not in only:
            continue
        w = fn()
        icon = ic.get(wid)
        if icon is None and draft:
            icon = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        if icon is None:
            raise ValueError(f"{wid}: {ICONS} 에 16px 그림이 없다")
        made[wid] = cm.write_item(out, wid, w, display_for(wid, kind, use), icon, kind, use=use,
                                  use_display=use_display_for(wid, kind, use))
        made[wid]["w"] = w
    return made


# ─────────────────────────── 미리보기 ───────────────────────────

def tp_close(model, disp, hand="r", yaw=-40, pitch=12, size=(360, 480), pose=None):
    """3인칭 가까이: 쥔 손과 든 것만 화면에 꽉 차게. yaw 0 = 사람 앞, 90 = 사람의 오른쪽."""
    from weapons import _views as vw
    root = vw.player_root(180.0)
    sc = vw.Scene()
    poses = (pose or "item", "none") if hand == "r" else ("none", pose or "item")
    arms = vw.add_player(sc, root, right=poses[0], left=poses[1])
    M = vw.hand_item_matrix(root, arms[hand], hand, disp)
    n0 = len(sc.faces)
    sc.add(model, M)
    grip = (M @ np.array([0, 0, 0, 1.0]))[:3]
    a = math.radians(yaw)
    d = 6.0
    eye = grip + np.array([math.sin(a) * d, math.sin(math.radians(pitch)) * d, -math.cos(a) * d])
    V = vw.look_at(eye, grip)
    pts = np.concatenate([(V @ np.c_[f[0], np.ones(4)].T).T[:, :2] for f in sc.faces[n0:]] + [np.zeros((1, 2))])
    lo, hi = pts.min(axis=0) - 0.08, pts.max(axis=0) + 0.08
    zoom = min(size[0] / (hi[0] - lo[0]), size[1] / (hi[1] - lo[1]), 700)
    return vw.render(sc, V, size=size, ortho=zoom, center=tuple((lo + hi) / 2))


def closeup(model, y0, y1, views=((0, 0), (-35, 15), (180, 0)), size=(320, 360)):
    """모형의 설계 Y y0..y1 (복셀) 부분만 크게 (머리 확대). 정사영, yaw 0 = 앞면."""
    from weapons import _views as vw
    sc = vw.Scene().add(model)
    cy = ((y0 + y1) / 2) / 32.0
    zoom = 0.9 * size[1] / ((y1 - y0) / 32.0)
    out = []
    for yaw, pitch in views:
        a = math.radians(yaw)
        eye = (math.sin(a) * 4, cy + math.sin(math.radians(pitch)) * 4, math.cos(a) * 4)
        V = vw.look_at(eye, (0, cy, 0))
        out.append(vw.render(sc, V, size=size, ortho=zoom, center=(0.0, 0.0)))
    return out


# 머리 확대 미리보기를 붙일 긴 무기: 설계 Y 범위
CLOSE = {"redin_spear": (22, 48), "hrolf_halberd": (14, 48), "warden_halberd": (20, 48), "sellsword_axe": (6, 28),
         "mathes_bell_mace": (10, 31), "penitent_mace": (6, 23), "gaoler_club": (-12, 24), "levy_hatchet": (-12, 18),
         "pilgrim_handbell": (-8, 13), "plank_shield": (-16, 16)}


def previews(ids=None, scratch=None):
    """
    미리보기 (게임 밖 흉내, _views): dist/screenshots/weapons/<id>_{gui,side,fp,tp}.png. set_a.previews 와 같은 짜임에
    머리 확대 (side 의 뒤 셋) 와 쥔 손 확대 (tp 의 near) 를 더했다. 모두 그리면 pack/preview/weapons_b.png 와
    weapons_lineup_b.png 도.
    """
    import shutil
    from PIL import Image
    from weapons import _views as vw
    scratch = scratch or os.path.join(os.environ.get("TMPDIR", "/tmp"), "souls_weapons_b")
    if os.path.exists(scratch):
        shutil.rmtree(scratch)
    made = build(scratch, only=ids, draft=True)
    ic = icons()
    os.makedirs(SHOTS, exist_ok=True)
    fronts = []
    for wid, res in made.items():
        fn, kind, use = WEAPONS[wid]
        model = res["3d"]
        disp = display_for(wid, kind, use)
        udisp = use_display_for(wid, kind, use) or {}
        icon = ic.get(wid) or Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        vw.gui(icon).save(os.path.join(SHOTS, f"{wid}_gui.png"))
        sides = vw.side(model, size=(300, 560))
        cl = closeup(model, *CLOSE[wid])
        vw.strip(sides + cl, ["front +Z", "3/4", "edge", "close front", "close 3/4", "close back"]).save(
            os.path.join(SHOTS, f"{wid}_side.png"))
        # 1인칭
        hand = "l" if use == "block" else "r"
        shots = [vw.first_person([(model, disp["firstperson_righthand"], hand, None)])]
        labels = ["first person, " + ("off hand" if hand == "l" else "main hand")]
        if use in ("guard", "block"):
            shots.append(vw.first_person([(model, udisp["firstperson_righthand"], hand, "block")]))
            labels.append("first person, " + ("blocking" if use == "block" else "guard"))
        vw.strip([s.resize((640, 360)) for s in shots], labels).save(os.path.join(SHOTS, f"{wid}_fp.png"))
        # 3인칭
        poses = ("none", "item") if hand == "l" else ("item", "none")
        tp = vw.third_person([(model, disp["thirdperson_righthand"], hand)], poses=poses,
                             views=((-35, 10), (90 if hand == "r" else -90, 5)), size=(380, 480), zoom=150)
        labels = ["front 3/4", "side"]
        sgn = 1 if hand == "r" else -1
        tp += [tp_close(model, disp["thirdperson_righthand"], hand, yaw, pitch)
               for yaw, pitch in ((-40 * sgn, 12), (100 * sgn, 8))]
        labels += ["near front", "near side"]
        if use in ("guard", "block"):
            bp = ("none", "block") if hand == "l" else ("block", "none")
            tp += vw.third_person([(model, udisp["thirdperson_righthand"], hand)], poses=bp, views=((-35, 10),),
                                  size=(380, 480), zoom=150)
            labels.append("blocking" if use == "block" else "guard")
        vw.strip(tp, labels).save(os.path.join(SHOTS, f"{wid}_tp.png"))
        print(f"{wid}: 요소 {len(model.elements)}, 재료 {cm.mat_count(res['w'])}")
        fronts.append((wid, model))
    if not ids:
        sheet = [vw.strip(vw.side(m, size=(220, 420), views=(("front", 0, 0, 0), ("3/4", -35, 15, 0))), [k, ""])
                 for k, m in fronts]
        rows = [vw.strip(sheet[i:i + 5]) for i in range(0, len(sheet), 5)]
        vw.strip(rows[:1]).save(os.path.join(PACK, "preview", "weapons_b.png")) if len(rows) == 1 else \
            _stack(rows).save(os.path.join(PACK, "preview", "weapons_b.png"))
        vw.lineup(fronts, os.path.join(PACK, "preview", "weapons_lineup_b.png"))
    return made


def _stack(imgs, bg=(20, 19, 18, 255)):
    from PIL import Image
    w = max(i.width for i in imgs)
    h = sum(i.height for i in imgs)
    out = Image.new("RGBA", (w, h), bg)
    y = 0
    for im in imgs:
        out.alpha_composite(im.convert("RGBA"), (0, y))
        y += im.height
    return out


if __name__ == "__main__":
    previews(sys.argv[1:] or None)


def icon_guide(wid, length_px, center=None, letters=None, shift=(0.0, 0.0)):
    """
    16px 그림을 손으로 찍을 때 곁에 두는 밑그림 (글자 격자): 앞면 (+Z) 에서 가장 앞 복셀의 재료를 대각선으로 눕혀 찍는다.
    이것을 그대로 쓰지 않는다 (SPEC 1.5). 실루엣과 재료 자리만 보고 art/weapon_icons_b.txt 에 손으로 다시 찍는다.
    """
    w = WEAPONS[wid][0]()
    lo, hi = w.bounds()
    ys = np.arange(w.H) + 0.5 - w.CY
    y0, y1 = ys[lo[1]] - 0.5, ys[hi[1]] + 0.5
    s = (y1 - y0) / (length_px * math.sqrt(2))     # 복셀 / 픽셀 (대각선 길이)
    cyd = (y0 + y1) / 2 if center is None else center
    xs = np.arange(w.W) + 0.5 - w.CX
    cxd = (xs[lo[0]] - 0.5 + xs[hi[0]] + 0.5) / 2
    letters = letters or {}
    rows = []
    for py in range(16):
        row = ""
        for px in range(16):
            votes = {}
            for a in (-0.33, 0, 0.33):
                for b in (-0.33, 0, 0.33):
                    du, dv = px + 0.5 + a - 8 - shift[0], py + 0.5 + b - 8 - shift[1]
                    Xd = s * (du + dv) / math.sqrt(2) + cxd
                    Yd = s * (du - dv) / math.sqrt(2) + cyd
                    ix, iy = int(math.floor(Xd)) + w.CX, int(math.floor(Yd)) + w.CY
                    if not (0 <= ix < w.W and 0 <= iy < w.H):
                        continue
                    col = w.grid[ix, iy, :]
                    nz = np.nonzero(col)[0]
                    if len(nz):
                        n = w.names[col[nz[-1]] - 1]
                        votes[n] = votes.get(n, 0) + 1
            if sum(votes.values()) >= 4:
                n = max(votes, key=votes.get)
                row += letters.get(n, n[0])
            else:
                row += "."
        rows.append(row)
    return rows
