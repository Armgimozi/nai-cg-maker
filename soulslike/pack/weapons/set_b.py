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


# ─────────────────────────── 머리 그리기 (판정 A4: 날 끝은 가장 얇고 이어진 한 줄) ───────────────────────────
# 자루 무기의 머리도 칼과 같은 말을 쓴다 (_common.draw / _common.blade, 글자 한 칸 = 복셀 하나, 좌표는 복셀 가운데).
# 가운데가 −0.5 라 두께는 홀수: 눈 (자루를 감싼 쇠) 5, 목·뺨 3, 날 끝 1 (Z −0.5 한 칸). 이 빠짐은 날 끝 줄에서 한 칸씩.
EYE = (-2.5, 1.5)        # 눈: Z 가운데 −2.5..1.5 (다섯 칸)
CHEEK = (-1.5, 0.5)      # 뺨·목: 세 칸
EDGE = (-0.5, -0.5)      # 날 끝: 한 칸


def columns(w, cols, zspan, mat):
    """옆모습을 열마다 손으로: cols = {x: (y 아래, y 위)} (둘 다 포함하는 복셀 줄), zspan(x) → (z0, z1)."""
    for x, (ylo, yhi) in cols.items():
        z0, z1 = zspan(x)
        vb(w, x, x + 1, ylo, yhi + 1, z0, z1, mat)


def disc(w, y0, y1, r, mat, cx=-0.5, cz=-0.5, octagon=False):
    """가운데 (cx, cz) 둘레 둥근 단면 (반지름 r, 복셀 가운데까지 잰다). 가운데 −0.5 면 홀수 폭."""
    if octagon:
        fn = lambda X, Y, Z: ((np.abs(X - cx) <= r) & (np.abs(Z - cz) <= r) & (np.abs(X - cx) + np.abs(Z - cz) <= r * 1.42)
                              & (Y > y0) & (Y < y1))
    else:
        fn = lambda X, Y, Z: (((X - cx) ** 2 + (Z - cz) ** 2 <= r * r) & (Y > y0) & (Y < y1))
    return w.fill(fn, mat)


def band(w, y0, y1, mat, r=2.0):
    """자루를 감는 쇠테·감기: 가운데 −0.5 둘레 네모 테에서 모서리를 뺀 것 (r 2 → 폭 5, 자루 위로 한 칸)."""
    return w.fill(lambda X, Y, Z: ((np.abs(X + 0.5) <= r) & (np.abs(Z + 0.5) <= r) & (np.abs(X + 0.5) + np.abs(Z + 0.5) <= r + 0.5)
                                   & (Y > y0) & (Y < y1)), mat)


def langets(w, y0, y1, rivets_front, rivets_back, mat="iron", rivet="iron_hi"):
    """자루 앞뒤 (Z) 에 박은 쇠띠 둘 (한 칸 나온다) 과 리벳 (띠와 같은 높이, 밝은 머리만)."""
    vb(w, -1, 0, y0, y1, 1, 2, mat)
    vb(w, -1, 0, y0, y1, -3, -2, mat)
    vs(w, [(-1, y, 1) for y in rivets_front] + [(-1, y, -3) for y in rivets_back], rivet)


# ─────────────────────────── 3.5 레딘 징집병 손도끼 ───────────────────────────
# 머리 폭 9 (날 5, 눈 3, 납작머리 1), 날 쪽 높이 6, 눈 높이 4. 위 선은 곧고 아래 선은 눈에서 날 쪽으로 두 번 처져 턱이 된다.
# 머리는 한 덩이: 검은 쇠 뺨 (I) 에 날 쪽 두 줄이 갈아 낸 강철 띠 (S), 맨 바깥 한 줄이 날 끝 (얇다, 이 빠짐 둘).

HATCHET_HEAD = [
    # x: -6.5 ... 1.5 (9 칸), 맨 윗줄 Y = 14.5.  O 눈 (자루를 감싼다), P 납작머리, n 이 빠짐
    #  -6 -5 -4 -3 -2 -1  0  1
    "ESSIIOOOP",   # 14.5
    "ESSIIOOOP",   # 13.5
    "nSSIIOOOP",   # 12.5  이 빠짐
    "ESSIIOOOP",   # 11.5
    "ESSI     ",   # 10.5
    "nS       ",   # 9.5   처진 턱 (끝 한 칸이 떨어져 나갔다)
]


def levy_hatchet():
    """
    장작 패는 손도끼에 쇠를 조금 더 댔다. 작은 쐐기 머리 (위 HATCHET_HEAD), 두께는 눈 5 → 뺨 3 → 날 끝 1.
    자루는 짙은 나무 (bronze0), 손 닿는 곳만 한 단 밝다. 끝이 조금 굵다 (손잡이 끝 혹).
    하나뿐인 것: 머리 아래로 자루 앞뒤에 박은 쇠띠 (랑겟) 둘과 리벳 셋 (띠와 같은 높이).
    """
    w = VoxWeapon(mats("iron", "iron_hi", "steel", "edge", "rust", "wood", "wood_dark", "cord", "dark"), seed=501)
    rod(w, -6, 15, "wood_dark")
    paint(w, (w._Y > -4) & (w._Y < 5), "wood", only=("wood_dark",))      # 손 닿는 곳이 한 단 밝다
    band(w, -6, -5, "wood_dark", r=2.0)                                   # 끝 혹
    vb(w, -2, 2, -5, -4, -3, 1, "wood_dark")
    cm.draw(w, HATCHET_HEAD, {"I": ("iron", *CHEEK), "S": ("steel", *CHEEK), "E": ("edge", *EDGE), "e": ("steel", *EDGE),
                              "O": ("iron", *EYE), "P": ("iron", *EYE), "n": None}, -6.5, 14.5)
    vs(w, [(-1, 14, -1)], "dark")                                         # 쐐기 자국 (자루 끝이 눈 위로 보인다)
    vs(w, [(-2, 14, -1), (0, 14, -1), (-1, 14, -2), (-1, 14, 0)], "wood_dark")
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 13) & mat_is(w, "iron"), "iron_hi")   # 빛 받는 위 모서리
    vs(w, [(-3, 11, 0), (-3, 12, 0), (-2, 11, 1)], "rust")                # 눈과 뺨이 만나는 곳
    langets(w, 4, 11, (5, 8), (6,))
    # 자루 끝 끈 고리 (3×4, 가운데가 빈 고리, 자루 끝에 붙는다)
    vb(w, -2, 1, -7, -6, -1, 0, "cord")
    vs(w, [(-2, -8, -1), (0, -8, -1), (-2, -9, -1), (0, -9, -1)], "cord")
    vb(w, -2, 1, -10, -9, -1, 0, "cord")
    return w


# ─────────────────────────── 3.6 볼크 가 고용병 도끼 ───────────────────────────
# 수염 도끼. 눈 4×5 (자루와 등 쪽 벽 한 칸), 높이 3 의 좁은 목 두 칸, 그 밖으로 날이 넓어지며 아래로 수염이 늘어진다
# (눈 밑에서 다섯 칸 아래까지, 목 밑은 오목하게 패인 곡선). 위 선은 날 쪽 끝 (발끝) 으로 조금 오른다. 등에 짧은 네모 가시.
# 두께: 눈 5, 목·뺨 3, 날 끝 1. 날 끝 줄은 발끝에서 수염 끝까지 이어지고 이 빠짐 둘 (하나는 수염 끝).

SELL_HEAD = [
    # x: -11.5 ... 4.5 (17 칸), 맨 윗줄 Y = 24.5.  I 뺨, S 갈아 낸 띠, N 목, O 눈, K 등 가시, n 이 빠짐
    #  -11 -10 -9 -8 -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4
    "ES               ",   # 24.5  발끝
    "ESII             ",   # 23.5
    "eSIIIIII  OOOO   ",   # 22.5
    "nSIIIIIINNOOOOK  ",   # 21.5  이 빠짐
    "ESIIIIIINNOOOOKKK",   # 20.5
    "ESIIIIIINNOOOOKK ",   # 19.5
    "ESIIIII   OOOO   ",   # 18.5  (목 밑은 비었다)
    "ESIIIII          ",   # 17.5
    "ESIIII           ",   # 16.5
    "ESIIII           ",   # 15.5  (수염: 목 밑은 오목하게 패였다)
    "ESIII            ",   # 14.5
    "nSSI             ",   # 13.5  수염 끝 한 칸 떨어져 나감
]


def sellsword_axe():
    """
    수염 도끼 (위 SELL_HEAD). 자루는 짙은 나무, 아래 10 복셀 가죽 (한 곳이 닳아 나무가 보인다), 쇠 마개.
    눈 아래로 자루 앞뒤에 쇠띠 둘 (랑겟).
    하나뿐인 것: 머리 앞면 (+Z) 에 박아 둔 볼크 가 청동 동전 하나 (2×2, 뺨과 같은 높이, 찍힌 사슬 자국에 녹청).
    """
    w = VoxWeapon(mats("iron", "iron_hi", "steel", "edge", "rust", "wood_dark", "leather", "bronze", "verdigris", "dark"),
                  seed=601)
    rod(w, -5, 25, "wood_dark")
    band(w, -6, -4, "iron")                                       # 쇠 마개
    rod(w, -7, -6, "iron")
    rod(w, -4, 6, "leather")
    vs(w, [(-1, 1, 0), (-1, 2, 0), (0, 2, 0)], "wood_dark")       # 닳아 벗겨진 곳
    cm.draw(w, SELL_HEAD, {"I": ("iron", *CHEEK), "S": ("steel", *CHEEK), "N": ("iron", *CHEEK), "E": ("edge", *EDGE),
                           "e": ("steel", *EDGE), "O": ("iron", *EYE), "K": ("iron", *CHEEK), "n": None}, -11.5, 24.5)
    vs(w, [(-1, 22, -1)], "dark")                                 # 쐐기 자국
    vs(w, [(-2, 22, -1), (0, 22, -1), (-1, 22, -2), (-1, 22, 0)], "wood_dark")
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 21.5) & mat_is(w, "iron"), "iron_hi")
    langets(w, 12, 18, (13, 16), (14,))
    vs(w, [(-3, 18, 0), (-2, 18, 1), (2, 19, 0), (-4, 19, 0)], "rust")
    # 볼크 동전: 뺨 앞면 (Z 0) 에 박혔다 (같은 높이). 찍힌 사슬 자국 한 칸에 녹청
    vs(w, [(-8, 20, 0), (-7, 20, 0), (-8, 19, 0)], "bronze")
    v(w, -7, 19, 0, "verdigris")
    return w


# ─────────────────────────── 3.7 볼크 간수의 곤봉 ───────────────────────────
# 참나무 몽둥이: 손잡이 굵기 3 에서 머리로 4, 5, 6 세 계단 굵어지고 위는 모서리를 깎았다 (손으로 깎아 가운데가 조금씩 어긋난다).
# 머리는 짙은 나무, 손잡이는 한 단 밝다 (손때). 쇠테 둘은 나무와 같은 높이로 박혔고, 가운데 테 하나는 +X 쪽이 한 칸 들떴다.
# 테 사이에 네모 징 대가리 다섯 (한 칸 나온다, 고르지 않게). 머리 나무에 쪼개진 금 하나.
# 하나뿐인 것: 자루 끝의 쇠 걸쇠 (허리띠에 거는 갈고리, −Y 로 세 칸 내려가 +X 로 굽어 오른다).

def _club_section(y):
    """y (모서리 좌표) 의 단면 (x0, x1, z0, z1, 모서리 깎기)."""
    if y < 8:
        return (-2, 1, -2, 1, False)
    if y < 11:
        return (-2, 2, -3, 1, True)
    if y < 14:
        return (-3, 2, -3, 2, True)
    if y < 20:
        return (-3, 3, -4, 2, True)
    if y < 21:
        return (-2, 2, -3, 1, True)
    if y < 22:
        return (-1, 1, -2, 0, False)
    return None


def gaoler_club():
    w = VoxWeapon(mats("wood", "wood_dark", "iron", "iron_hi", "rust", "dark"), seed=701)
    for y in range(-6, 22):
        sec = _club_section(y)
        x0, x1, z0, z1, cut = sec
        vb(w, x0, x1, y, y + 1, z0, z1, "wood_dark")
        if cut:
            for x, z in ((x0, z0), (x0, z1 - 1), (x1 - 1, z0), (x1 - 1, z1 - 1)):
                v(w, x, y, z, None)
    paint(w, (w._Y > -5) & (w._Y < 6), "wood", only=("wood_dark",))      # 손잡이 손때 (한 단 밝다)

    def ring_at(y):
        x0, x1, z0, z1, cut = _club_section(y)
        sel = (w._Y > y) & (w._Y < y + 1) & ((w._X < x0 + 1) | (w._X > x1 - 1) | (w._Z < z0 + 1) | (w._Z > z1 - 1))
        paint(w, sel, "iron")

    ring_at(12)
    ring_at(18)
    # 들뜬 테 (y 15): 나무 위로 +X 쪽만 한 칸 나왔고 그 밑이 어둡다
    ring_at(15)
    vb(w, 3, 4, 15, 16, -3, 1, "iron")
    vs(w, [(2, 15, -2), (2, 15, -1), (2, 15, 0)], "dark")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron"), "iron_hi")
    # 네모 징 대가리 다섯 (한 칸 나온다)
    for x, y, z in ((-1, 14, 2), (1, 17, 2), (-4, 16, -2), (3, 19, -1), (0, 16, -5)):
        v(w, x, y, z, "iron")
    # 쪼개진 금 (앞면, 머리 아래쪽에서 위로 한 줄)
    for x, y in ((0, 9), (0, 10), (0, 11), (-1, 13), (-1, 14), (-1, 16), (-1, 17)):
        z = front_z(w, x, y)
        if z is not None and get(w, x, y, z) == "wood_dark":
            v(w, x, y, z, "dark")
    for x, y in ((-3, 11), (-2, 11), (1, 19)):
        z = front_z(w, x, y)
        if z is not None:
            v(w, x, y, z, "rust")
    # 쇠 걸쇠: 자루 끝 쇠 마개 + J 갈고리 (아래로 셋, +X 로 둘, 위로 하나)
    band(w, -7, -5, "iron", r=2.0)
    vb(w, -1, 0, -10, -7, -1, 0, "iron")
    vs(w, [(0, -10, -1), (1, -10, -1), (1, -9, -1)], "iron")
    v(w, 1, -9, -1, "iron_hi")
    return w


# ─────────────────────────── 3.8 오스윈 고행승의 철퇴 ───────────────────────────
# 짧은 쇠자루 위 날개 철퇴 머리: 가운데 몸 3×3 둘레로 날개 판 여섯 (네 축 + 대각선 둘). 판은 한 칸 두께로 이어지고 옆모습이
# 사다리꼴 (몸 옆 9 줄 → 끝 5 줄). 대각선 판은 계단 두 줄을 겹쳐 면으로 잇는다 (모서리로만 닿는 칸이 없다).
# +X 날개 위 끝이 앞으로 휘었다. 손잡이는 땀에 전 짙은 삼끈 (머리보다 튀지 않게).
# 하나뿐인 것: 머리 바로 아래 감아 맨 고행 끈. −X 쪽으로 자루를 따라 곧게 늘어지고 2×2 매듭 셋.

def penitent_mace():
    w = VoxWeapon(mats("iron", "iron_hi", "iron_edge", "rust", "cord", "cord_dark"), seed=801)
    rod(w, -6, 21, "iron")
    band(w, -7, -5, "iron")                                     # 자루 끝 혹
    rod(w, -5, 6, "cord_dark")
    vs(w, [(-2, 21, -1), (0, 21, -1), (-1, 21, -2), (-1, 21, 0), (-1, 21, -1), (-1, 22, -1)], "iron")   # 꼭지
    prof = {1: (12, 21), 2: (13, 20), 3: (14, 19)}             # 몸에서 떨어진 거리 → 날개의 y 범위 (사다리꼴)
    for d, (y0, y1) in prof.items():
        vb(w, d, d + 1, y0, y1, -1, 0, "iron")                  # +X
        vb(w, -2 - d, -1 - d, y0, y1, -1, 0, "iron")            # −X
        vb(w, -1, 0, y0, y1, d, d + 1, "iron")                  # +Z
        vb(w, -1, 0, y0, y1, -2 - d, -1 - d, "iron")            # −Z
    # 대각선 둘 (+X+Z, −X−Z): 계단 두 줄 (1,0)(1,1)(2,1)(2,2) 를 겹쳐 면으로 잇는다. 사다리꼴은 한 칸 짧게
    for (sx, sz) in ((1, 1), (-1, -1)):
        for (a, b), (y0, y1) in (((1, 0), (13, 20)), ((1, 1), (13, 20)), ((2, 1), (14, 19)), ((2, 2), (14, 19))):
            x = 0 + a if sx > 0 else -2 - a
            z = 0 + b if sz > 0 else -2 - b
            vb(w, x, x + 1, y0, y1, z, z + 1, "iron")
    # 날개 바깥 끝은 닳아 밝다 (위쪽 반)
    tips = [(3, -1), (-5, -1), (-1, 3), (-1, -5), (2, 2), (-4, -4)]
    for x, z in tips:
        vb(w, x, x + 1, 16, 19, z, z + 1, "iron_edge")
    # +X 날개 위 끝이 앞으로 휘었다
    vs(w, [(3, 18, -1)], None)
    vs(w, [(3, 18, 0), (3, 17, 0)], "iron_edge")
    vs(w, [(1, 12, -1), (-3, 13, -1), (-1, 13, 1), (-1, 18, -3)], "rust")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron") & (w._Y > 11), "iron_hi")
    # 고행 끈: 머리 밑 감기 (두 줄) 와 −X 로 곧게 늘어진 끝 (한 칸 굵기), 2×2 매듭 셋
    band(w, 10, 12, "cord", r=1.5)
    vb(w, -3, -2, 4, 12, -1, 0, "cord")
    for y in (9, 6, 4):
        vb(w, -4, -2, y, y + 2, -1, 0, "cord")
    return w


# ─────────────────────────── 3.9 마테스의 종 철퇴 ───────────────────────────
# 쇠테 둘을 두른 짙은 참나무 자루 위에 입이 손 쪽 (−Y) 을 보는 작은 청동 종. 종은 고리를 쌓아 만든다: 입술 테 11 (한 줄),
# 벌어지는 줄 9, 허리 7 (여섯 줄), 어깨 5, 정수리 판 3, 매달던 고리. 입 안은 납으로 메웠다 (입술에서 두 칸 들어가 있다).
# 녹청은 입술 테 위 홈 (끊긴 줄 둘) 과 금 끝에만.
# 하나뿐인 것: 종 앞면을 입술에서 위로 타고 오른 금 한 줄 (한 칸 폭, 여섯 줄, 끝이 두 갈래).

def mathes_bell_mace():
    w = VoxWeapon(mats("wood_dark", "leather", "iron", "iron_hi", "rust", "bronze", "bronze_hi", "verdigris", "lead", "dark"),
                  seed=901)
    rod(w, -6, 19, "wood_dark")
    rod(w, -5, 5, "leather")
    band(w, -7, -5, "iron")                                     # 쇠 마개
    for y in (8, 14):                                           # 쇠테 둘 (한 칸 나온다)
        band(w, y, y + 1, "iron")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron"), "iron_hi")
    vs(w, [(1, 8, -1), (-3, 14, -2)], "rust")
    rings = {17: 5.05, 18: 4.15, 19: 3.2, 20: 3.2, 21: 3.2, 22: 3.2, 23: 3.2, 24: 3.2, 25: 2.9, 26: 2.3, 27: 1.5}
    for y, r in rings.items():
        disc(w, y, y + 1, r, "bronze")
    # 입: 입술 테는 바깥 한 칸만, 벌어지는 줄과 그 위 한 줄은 속을 비운다. 그 위가 납 (두 칸 들어가 있다)
    rr = (w._X + 0.5) ** 2 + (w._Z + 0.5) ** 2
    w.clear(lambda X, Y, Z: (Y > 17) & (Y < 18) & (rr < 4.0 ** 2))
    w.clear(lambda X, Y, Z: (Y > 18) & (Y < 19) & (rr < 3.1 ** 2))
    paint(w, (w._Y > 19) & (w._Y < 20) & (rr < 2.3 ** 2), "lead")
    # 녹청: 입술 테 위 홈 (벌어지는 줄의 바깥) 두 곳, 끊긴 줄
    ang = np.degrees(np.arctan2(w._Z + 0.5, w._X + 0.5)) % 360
    groove = (w._Y > 18) & (w._Y < 19) & (rr > 3.4 ** 2)
    paint(w, groove & (((ang > 20) & (ang < 95)) | ((ang > 200) & (ang < 245))), "verdigris", only=("bronze",))
    # 입술 찌그러짐 둘
    vs(w, [(3, 17, 2), (2, 17, 3)], None)
    vs(w, [(-6, 17, -1), (-6, 17, -2)], None)
    # 어깨는 손이 닿아 밝다 (왼쪽 위 빛 쪽)
    paint(w, (w._Y > 23) & (w._Y < 27) & (w._X < 0) & (w._Z > -1.5), "bronze_hi", only=("bronze",))
    # 매달던 고리
    vs(w, [(-2, 28, -1), (-2, 29, -1), (-1, 29, -1), (0, 29, -1), (0, 28, -1)], "bronze")
    # 금: 앞면 (+Z) 입술에서 위로 여섯 줄 (한 칸 폭), 끝이 두 갈래, 갈래 끝 하나에 녹청
    for x, y in ((0, 17), (0, 18), (0, 19), (0, 20), (0, 21), (0, 22), (-1, 23), (1, 23), (1, 24)):
        z = front_z(w, x, y)
        if z is not None:
            v(w, x, y, z, "dark")
    z = front_z(w, -1, 24)
    if z is not None:
        v(w, -1, 24, z, "verdigris")
    return w


# ─────────────────────────── 3.10 레딘 창병의 창 ───────────────────────────
# 곧은 자루 (굵기 3) 끝에 버들잎 창날: 어깨가 날카롭게 꺾여 (폭 3 → 5) 네 줄 곧게 가다 5 → 3 → 1 로 좁아진다.
# 가운데 등줄은 세 칸 두께, 날 몸은 한 칸, 바깥 한 줄이 날 끝 (양쪽 모두 끊기지 않는 bone 줄, 이 빠짐 하나).
# 소켓 아래로 짧은 쇠띠 둘, 뾰족한 물미. 자루 아래쪽은 흙때 (곧은 경계), 쥐는 자리에 가죽 한 감기.
# 하나뿐인 것: 소켓 아래 묶은 바랜 붉은 천. 곧게 두 가닥 늘어진다 (길이가 다르다).

SPEAR_LEAF = [
    # x: -2.5 ... 1.5 (5 칸, 가운데 X −0.5), 맨 윗줄 Y = 45.5.  R 등줄 (세 칸 두께), F 날 몸 (한 칸), n 이 빠짐
    "  E  ",   # 45.5  끝
    "  E  ",   # 44.5
    " FRF ",   # 43.5
    " FRF ",   # 42.5
    " FRF ",   # 41.5
    " FRF ",   # 40.5
    "FFRFF",   # 39.5
    "FFRFF",   # 38.5
    "nFRFF",   # 37.5  이 빠짐
    "FFRFF",   # 36.5  날카로운 어깨
    " FRF ",   # 35.5
    " FRF ",   # 34.5
]


def redin_spear():
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
    # 소켓: 29..34, 위로 가늘어진다
    band(w, 29, 32, "iron")
    rod(w, 32, 34, "iron")
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 31) & (w._Y < 32), "iron_hi")
    # 소켓 아래 쇠띠 둘 (앞뒤) 과 못 (같은 높이)
    langets(w, 25, 29, (26,), (27,))
    vs(w, [(-1, 30, 1), (0, 29, 1), (-2, 31, -3)], "rust")
    # 버들잎 날: 가장자리 (여덟 이웃에 빈칸) 는 모두 얇은 날 끝 (edge), 등줄은 늘 두껍다
    cm.blade(w, SPEAR_LEAF, {"E": "edge", "F": "steel", "R": "steel_b"}, -2.5, 45.5, edges="E", dull="E", keep="R",
             slab=CHEEK, thin=EDGE)
    # 날 몸 (F) 은 한 칸 두께: blade() 가 세 칸으로 찍은 것을 얇게
    w.clear(lambda X, Y, Z: (Y > 33) & (Y < 46) & (np.abs(Z + 0.5) > 0.6) & (np.abs(X + 0.5) > 0.6))
    # 붉은 천: 소켓 아래 두 번 감고 −X 로 곧게 두 가닥 (길이가 다르다)
    band(w, 27, 29, "cloth_red")
    vb(w, -4, -3, 21, 29, -1, 0, "cloth_red")
    vb(w, -5, -4, 24, 28, -1, 0, "cloth_red")
    return w


# ─────────────────────────── 3.11 흐롤프의 미늘창 ───────────────────────────
# 묵직한 미늘창 (보스 흐롤프가 드는 것과 같은 모형). 도끼날 (−X) 은 초승달: 바깥 날은 볼록하고, 자루 쪽 등은 오목하게 패여
# 위아래 뿔 끝이 소켓에 닿는다 (가운데는 빈 틈). 위 뿔이 더 길다. 날 가운데를 크게 한 입 베어 낸 이 빠짐 (2×3).
# 날 끝은 볼록한 바깥 둘레를 따라 한 칸 두께로 이어진다. 반대쪽 (+X) 에 두 칸 두께로 아래로 굽은 갈고리, 꼭대기에 네모 송곳 (끝이
# 무디다). 자루 위 1/4 을 쇠띠 둘 (랑겟) 이 감싼다.
# 하나뿐인 것: 갈고리 밑에 쇠사슬 (고리 넷, 누운 것과 선 것이 번갈아) 로 곧게 매단 성문 열쇠 (두 칸 두께, 길이 6).

def hrolf_halberd():
    w = VoxWeapon(mats("wood_dark", "leather", "iron", "iron_hi", "iron_edge", "steel_b", "steel_dark", "edge", "rust"),
                  seed=1101)
    rod(w, -23, 31, "wood_dark")
    rod(w, -6, 6, "leather")
    band(w, -24, -21, "iron")                                   # 물미
    rod(w, -26, -24, "iron")
    band(w, 28, 37, "iron")                                     # 소켓
    langets(w, 15, 28, (17, 21, 25), (19, 23))
    vs(w, [(-1, 19, 1), (-1, 20, -3)], "rust")
    # 초승달 날: 바깥 원 (가운데 (−2, 37.5), 반지름 11.5) 안, 안쪽 원 (가운데 (1.5, 36), 반지름 8.5) 밖, X ≤ −2.5, Y 29..46
    c1, r1, c2, r2 = (-2.0, 37.5), 11.5, (1.5, 36.0), 8.5
    X, Y = w._X[:, :, 0], w._Y[:, :, 0]
    m2 = (((X - c1[0]) ** 2 + (Y - c1[1]) ** 2) <= r1 * r1) & (((X - c2[0]) ** 2 + (Y - c2[1]) ** 2) > r2 * r2) \
        & (X <= -2.4) & (Y > 29) & (Y < 46)
    outer = m2 & (((X - c1[0]) ** 2 + (Y - c1[1]) ** 2) > (r1 - 1.15) ** 2)          # 바깥 둘레 한 줄 = 날 끝
    band_ = m2 & ~outer & (((X - c1[0]) ** 2 + (Y - c1[1]) ** 2) > (r1 - 2.3) ** 2)   # 갈아 낸 띠
    for (mask, mat, z0, z1) in ((m2 & ~outer & ~band_, "steel_dark", -2, 1), (band_, "steel_b", -2, 1), (outer, "edge", -1, 0)):
        extrude(w, mask, z0, z1, mat)
    # 크게 베어 낸 이 빠짐 (2×3, 날 가운데 조금 아래) 과 날 끝 줄의 작은 이 빠짐 둘
    w.clear(lambda X, Y, Z: (X < -11.9) & (Y > 34) & (Y < 37))
    for y in (42, 31):                                          # 그 줄의 맨 바깥 날 끝 한 칸
        xs = [x for x in range(-16, -2) if get(w, x, y, -1)]
        if xs:
            v(w, min(xs), y, -1, None)
    # 갈고리 (+X): 소켓에서 나와 아래로 굽는다 (두 칸 두께)
    hook = {2: (33, 36), 3: (33, 36), 4: (32, 35), 5: (31, 34), 6: (29, 33), 7: (28, 31), 8: (27, 29)}
    columns(w, hook, lambda x: (-2, 0), "iron")
    vs(w, [(8, 27, -2), (8, 27, -1), (7, 28, -2)], "iron_edge")
    # 네모 송곳 (37..46, 끝 무딤)
    rod(w, 37, 41, "iron")
    vb(w, -2, 1, 41, 44, -1, 0, "iron")
    vb(w, -1, 0, 41, 44, -2, 1, "iron")
    vb(w, -1, 0, 44, 46, -1, 0, "iron")
    paint(w, (w._Y > 37) & (w._X > -0.5) & (w._Z > -0.5), "iron_edge", only=("iron",))
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron") & (w._Y > 30), "iron_hi")
    vs(w, [(-3, 31, 0), (2, 33, 0), (-2, 37, 1), (3, 33, -1), (1, 28, -1)], "rust")
    # 쇠사슬: 갈고리 밑 (x 5..6) 에서 곧게. 누운 고리 (XY 면, 3×3 가운데 빔) 와 선 고리 (ZY 면) 가 번갈아 한 줄씩 겹친다
    top = 28
    for k in range(4):
        y1 = top - 2 * k                                        # 고리 윗줄 (모서리 좌표)
        if k % 2 == 0:
            for x in (4, 5, 6):
                v(w, x, y1, -1, "iron")
                v(w, x, y1 - 2, -1, "iron")
            v(w, 4, y1 - 1, -1, "iron")
            v(w, 6, y1 - 1, -1, "iron")
        else:
            for z in (-2, -1, 0):
                v(w, 5, y1, z, "iron")
                v(w, 5, y1 - 2, z, "iron")
            v(w, 5, y1 - 1, -2, "iron")
            v(w, 5, y1 - 1, 0, "iron")
    v(w, 5, 22, -1, "rust")
    # 성문 열쇠: 고리 (3×3, 가운데 빔) 아래로 대 (세 칸) 와 이 (2×2). 두 칸 두께 (Z −2..0), 길이 6
    for z in (-2, -1):
        for x, y in ((4, 20), (5, 20), (6, 20), (4, 19), (6, 19), (4, 18), (5, 18), (6, 18)):
            v(w, x, y, z, "iron")
        for y in (17, 16, 15):
            v(w, 5, y, z, "iron")
        for x, y in ((6, 16), (6, 15)):
            v(w, x, y, z, "iron")
    vs(w, [(4, 20, -2), (6, 16, -1)], "rust")
    return w


# ─────────────────────────── 3.12 교구 수호병의 미늘창 ───────────────────────────
# 흐롤프 것보다 투박하고 무거운 칼날형 미늘창. 큰 날 (−X) 은 위가 넓은 식칼꼴, 위 선은 곧다. 등에 짧은 가시 (4), 꼭대기 송곳은
# 짧다 (4). 갈고리는 없다. 머리는 녹이 많다.
# 날 끝: 바깥 한 줄이 한 칸 두께로 위에서 아래까지 이어진다 (물때 선 위아래 모두 ash2 의 갈린 띠). 이 빠짐 셋.
# 물때 선 (Y 38): 아래는 모두 한 단 어둡고 이끼빛이다. 경계는 그라데이션이 아니라 곧은 한 줄 (교구가 물에 잠겼던 높이, 8.5).
# 하나뿐인 것: 날에 뚫은 종 모양 구멍 (뚫렸다: 정수리 2, 몸 3 줄은 폭 3, 벌어진 입술 폭 5).

def warden_halberd():
    w = VoxWeapon(mats("wood", "wood_wet", "leather", "iron_rusty", "iron_wet", "iron_hi", "rust", "steel_b"), seed=1201)
    rod(w, -28, 27, "wood")
    for y in (-5, -4, -1, 3):                                   # 썩은 가죽: 몇 줄만 (고르지 않게)
        band(w, y, y + 1, "leather", r=1.5)
    vs(w, [(0, 0, 0), (-2, 1, -2), (0, 1, -1)], "leather")
    band(w, 26, 42, "iron_rusty")                               # 소켓
    band(w, -28, -26, "iron_rusty")
    # 큰 날: 위 선은 곧다 (y 43), 아래로 좁아지고 위가 넓은 식칼꼴
    cols = {-3: (31, 40), -4: (30, 41), -5: (29, 42), -6: (29, 43), -7: (28, 43), -8: (28, 43), -9: (28, 43),
            -10: (28, 43), -11: (28, 43), -12: (29, 43)}
    columns(w, cols, lambda x: (-2, 1), "iron_rusty")
    # 날 끝: 바깥 한 줄 (x −13) 은 한 칸 두께, 그 안 한 줄은 갈린 띠 (ash2). 이 빠짐 셋
    vb(w, -13, -12, 29, 44, -1, 0, "iron_hi")
    paint(w, (w._X > -12) & (w._X < -11), "iron_hi", only=("iron_rusty",))
    for y in (40, 35, 31):
        v(w, -13, y, -1, None)
    # 종 모양 구멍 (뚫렸다): 정수리 2, 몸 3 줄은 폭 3, 벌어진 입술 1 줄은 폭 5
    hole = [(-9, 40), (-8, 40)] + [(x, y) for y in (37, 38, 39) for x in (-9, -8, -7)] + \
           [(x, 36) for x in (-10, -9, -8, -7, -6)]
    for x, y in hole:
        for z in (-2, -1, 0):
            v(w, x, y, z, None)
    # 구멍 둘레 한 칸은 닳아 밝다 (뚫린 것이 어두운 칠로 읽히지 않게, 판정 B 수호병 1)
    hs = set(hole)
    rim = {(x + dx, y + dy) for x, y in hole for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - hs
    for x, y in rim:
        for z in (-2, -1, 0):
            if get(w, x, y, z):
                v(w, x, y, z, "iron_hi")
    # 등 가시 (+X, 4)
    spike = {2: (34, 38), 3: (35, 37), 4: (35, 36), 5: (35, 35)}
    columns(w, spike, lambda x: (-2, 1) if x <= 3 else (-1, 0), "iron_rusty")
    # 꼭대기 짧은 송곳 (42..46)
    rod(w, 42, 44, "iron_rusty")
    vb(w, -1, 0, 44, 46, -1, 0, "iron_rusty")
    paint(w, exposed_dir(w, 1, 1) & (w._Y > 38), "iron_hi", only=("iron_rusty",))
    vs(w, [(-4, 40, 0), (-5, 41, 0), (-10, 42, 0), (2, 37, 0), (-11, 43, 0)], "rust")
    # 물때 선 (Y 38): 아래는 물 먹은 재료. 날 끝의 갈린 띠는 물 아래에서도 ash2 로 이어진다 (판정 B 수호병 3)
    low = w._Y < 38
    paint(w, low, "iron_wet", only=("iron_rusty", "rust", "steel_b"))
    paint(w, low, "wood_wet", only=("wood",))
    return w


# ─────────────────────────── 3.14 탑옥 판자 방패 ───────────────────────────

def plank_shield():
    """
    감방 문짝을 잘라 낸 네모 판 (폭 20, 높이 28, 판 두께 2 + 쇠띠 1). 세로 판자 셋 (폭 7, 5, 6) 사이 틈은 앞이 파인 홈,
    아래 끝은 도끼로 잘라 들쭉날쭉, 왼쪽 위 귀가 비스듬히 잘렸다. 가로 쇠띠 둘 (문 경첩 띠): 왼쪽 끝은 판 가장자리에서 한 칸 안에서
    멈추고, 오른쪽 끝은 판 밖으로 말려 경첩 고리가 된다.
    뒷면: 손잡이 (가로 쇠막대, 판 바로 뒤에서 판과 나란히. 주먹이 그것을 쥔다), 팔을 끼우는 밧줄 고리, 손톱 긁힘.
    판 뒷면은 쥐는 점에서 Z +5 (A 의 방패와 같다: 팔이 쥐는 점에서 4 복셀까지 차 있어 그보다 가까우면 팔이 판을 뚫는다).
    하나뿐인 것: 앞면 위쪽의 들여다보는 구멍 (4×4, 안은 어둡다) 과 쇠창살 두 줄.
    """
    w = VoxWeapon(mats("plank", "wood_dark", "iron", "iron_hi", "rust", "dark", "bone", "cord"), seed=1401)
    zb = 5                                                        # 판 뒷면
    planks = [(-10, -3, [-13, -14, -14, -13, -12, -13, -13], "plank"),
              (-2, 3, [-12, -13, -13, -14, -13], "wood_dark"),
              (4, 10, [-14, -13, -12, -13, -14, -14], "plank")]
    for x0, x1, bottoms, m in planks:
        for i, x in enumerate(range(x0, x1)):
            vb(w, x, x + 1, bottoms[i], 14, zb, zb + 2, m)
    for x in (-3, 3):                                             # 틈: 뒤 판만 남기고 앞은 판다
        vb(w, x, x + 1, -12, 14, zb, zb + 1, "dark")
    for k in range(4):                                            # 왼쪽 위 귀를 비스듬히 자른다
        vb(w, -10, -10 + 4 - k, 13 - k, 14 - k, zb, zb + 2, None)
    vs(w, [(9, 13, zb + 1), (9, 12, zb + 1), (-2, -12, zb + 1)], None)   # 판자 모서리 쪼개짐
    # 쇠띠 둘 (앞): 왼쪽 끝은 판 가장자리 한 칸 안, 오른쪽 끝은 경첩 고리 (판 옆을 돌아 뒤로 말린다)
    zf = zb + 2
    for y0 in (3, -9):
        vb(w, -9, 10, y0, y0 + 2, zf, zf + 1, "iron")
        vb(w, 10, 11, y0, y0 + 2, zb, zf + 1, "iron")
        vb(w, 11, 12, y0, y0 + 2, zb, zf, "iron")
        for x in (-7, -1, 6):                                     # 판자마다 못 하나 (머리가 한 칸 나온다)
            v(w, x, y0 + (1 if x != -1 else 0), zf + 1, "iron")
    vs(w, [(-8, 3, zf), (2, -9, zf), (3, -8, zf), (8, 4, zf), (9, 4, zf)], "rust")
    paint(w, exposed_dir(w, 1, 1) & mat_is(w, "iron") & ~((w._Y > 5) & (w._Y < 12) & (np.abs(w._X) < 3)), "iron_hi")
    # 들여다보는 구멍 (4×4): 판을 뚫고 뒤에 어두운 그늘 판 (문 안쪽의 어둠), 쇠창살 두 줄과 테 (어두운 쇠)
    vb(w, -2, 2, 7, 11, zb, zb + 2, None)
    vb(w, -2, 2, 7, 11, zb, zb + 1, "dark")
    for x in (-1, 1):
        vb(w, x, x + 1, 7, 11, zb + 1, zb + 2, "iron")
    vb(w, -3, 3, 11, 12, zb + 1, zf + 1, "iron")
    vb(w, -3, 3, 6, 7, zb + 1, zf + 1, "iron")
    # 뒷면 손잡이: 판 바로 뒤에서 판과 나란한 가로 쇠막대 (주먹이 감싼다), 짧은 다리 둘
    vb(w, -3, 3, -1, 1, 2, 4, "iron")
    vb(w, -4, -3, -1, 1, 2, zb, "iron")
    vb(w, 3, 4, -1, 1, 2, zb, "iron")
    # 팔을 끼우는 밧줄 고리 (손잡이 위, 아래팔 둘레: |X|, |Z| ≤ 4 밖)
    for x in (-5, 4):
        vb(w, x, x + 1, 8, 9, -5, zb, "cord")
    vb(w, -5, 5, 8, 9, -5, -4, "cord")
    # 뒷면 손톱 긁힘 (bone0 짧은 세로 줄, 기울기가 다르다)
    for x, ys in ((-6, (4, 5, 6)), (-5, (3, 4)), (5, (5, 6, 7)), (6, (2, 3, 4)), (-1, (-5, -4, -3))):
        for y in ys:
            if get(w, x, y, zb):
                v(w, x, y, zb, "bone")
    vs(w, [(-8, -12, zb + 1), (-7, -12, zb + 1), (-7, -11, zb + 1), (5, -13, zb + 1), (6, -12, zb + 1)], "rust")
    return w


# ─────────────────────────── 3.20 오스윈 순례자의 손종 ───────────────────────────

def pilgrim_handbell():
    """
    짧은 짙은 나무 손잡이 (둥근 꼭지, 종과 만나는 곳에 쇠 깃) 와 종 모양 청동 종. 종은 고리를 쌓았다: 좁은 정수리 3, 어깨 5,
    허리 5 (두 줄), 벌어지는 줄 7, 두꺼운 입술 9. 입이 +Y 끝을 보고 (앞으로 내밀어 흔든다), 입 밖으로 추가 한 칸 보인다.
    입술 찌그러짐 하나. 청동은 손 닿는 어깨만 밝다. 녹청은 없다 (판정 B 손종 4).
    하나뿐인 것: 손잡이에 한 칸 끈으로 매단 작은 순례 패 (2×3 쇠 조각, 종 모양 찍힘).
    """
    w = VoxWeapon(mats("wood_dark", "bronze", "bronze_hi", "string", "iron", "iron_hi", "dark"), seed=2001)
    rod(w, -4, 2, "wood_dark")
    band(w, -6, -4, "wood_dark")                                # 꼭지
    rod(w, -7, -6, "wood_dark")
    band(w, 1, 3, "iron", r=2.0)                                # 쇠 깃 (한 칸 나온다)
    prof = [1.5, 2.3, 2.3, 2.3, 3.2, 4.2, 4.2]                  # 정수리 3, 어깨·허리 5, 벌어짐 7, 입술 9 (두 줄)
    for h, r in enumerate(prof):
        disc(w, 3 + h, 4 + h, r, "bronze")
    rr = (w._X + 0.5) ** 2 + (w._Z + 0.5) ** 2
    for h, r in enumerate(prof):
        if h >= 2:
            w.clear(lambda X, Y, Z, h=h, r=r: (Y > 3 + h) & (Y < 4 + h) & (rr < (r - 1.0) ** 2))
    disc(w, 4, 5, 1.5, "dark")                                  # 속 바닥 그늘
    paint(w, (w._Y > 9) & (w._Y < 10) & (rr > 3.3 ** 2), "bronze_hi", only=("bronze",))   # 두꺼운 입술 테의 빛
    # 추: 가운데 줄과 끝 (입 밖으로 한 칸)
    vb(w, -1, 0, 5, 11, -1, 0, "iron")
    vs(w, [(-2, 9, -1), (0, 9, -1), (-1, 9, -2), (-1, 9, 0)], "iron")
    paint(w, (w._Y > 3) & (w._Y < 6) & (w._X < 0), "bronze_hi", only=("bronze",))
    vs(w, [(-1, 9, 3), (0, 9, 3)], None)                        # 입술 찌그러짐
    # 순례 패: 손잡이 아래쪽에 한 칸 끈 (세 칸) 으로 매단 2×3 쇠 조각 (ash2), 찍힌 종 한 칸
    vs(w, [(-2, -1, -1), (-3, -1, -1), (-3, -2, -1)], "string")
    vb(w, -4, -2, -5, -2, -1, 0, "iron_hi")
    v(w, -3, -4, -1, "iron")
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


def display_for(wid, kind, use, w=None):
    """w: 지은 무기 (1인칭을 그 길이로 셈한다, _common.hand_display)."""
    if use == "same":
        return cm.catalyst_display(*CATALYST_FP[wid])
    if use == "block":
        return cm.shield_display(*SHIELD_FP[wid])
    return cm.hand_display(kind, w)


def use_display_for(wid, kind, use, w=None):
    if use == "guard":
        return cm.guard_display(kind, w)
    if use == "block":
        return cm.shield_block_display(*SHIELD_BLOCK_FP[wid])
    return None


# 1인칭 회전·이동 (크기) [확인 (클라)]. 3인칭은 _common 의 정한 값 (이동은 모두 같고 회전만 분류마다)
# 판자 방패는 A 의 경비대 방패 (shields_a.HEATER_FP, 높이 26) 와 같은 자세, 크기만 높이 28 에 맞춰 0.6
# 손종: 종 입 (+Y) 이 앞 위로 45° 기울어 화면 오른쪽 아래에 종과 손잡이가 함께 보인다 (_common.fp_frame)
CATALYST_FP = {"pilgrim_handbell": cm.fp_frame((1, 0, 0), (-0.5, math.sin(math.radians(45)), -math.cos(math.radians(45))),
                                                (0.80, 0.80, -0.75))}
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
        disp, udisp = display_for(wid, kind, use, w), use_display_for(wid, kind, use, w)
        made[wid] = cm.write_item(out, wid, w, disp, icon, kind, use=use, use_display=udisp)
        made[wid]["w"] = w
        made[wid]["display"], made[wid]["use_display"] = disp, udisp
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
        disp = res["display"]
        udisp = res["use_display"] or {}
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
