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
for p in (HERE, PACK):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as cm  # noqa: E402
from _common import poly  # noqa: E402
from _mats import VoxWeapon, mats  # noqa: E402

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
            -4: (9, 14), -5: (9, 14), -6: (9, 14), -7: (8, 14), -8: (7, 14), -9: (6, 15), -10: (7, 15)}
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


# ─────────────────────────── 목록 ───────────────────────────
# id: (만드는 함수, 분류 (FP_SCALE 열쇠), 쓰는 중 모형 "guard" | "block" | "same")
WEAPONS = {
    "levy_hatchet": (levy_hatchet, "hand_axe", "guard"),
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


CATALYST_FP = {}
SHIELD_FP = {}
SHIELD_BLOCK_FP = {}


def icons():
    if not os.path.exists(ICONS):
        return {}
    return {k: cm.icon_image(rows, ink) for k, (rows, ink) in cm.load_icons(ICONS).items()}


def build(out, only=None):
    """팩 폴더 out 에 B 묶음을 쓴다. 돌려주는 값 {id: write_item 결과}."""
    ic = icons()
    made = {}
    for wid, (fn, kind, use) in WEAPONS.items():
        if only and wid not in only:
            continue
        w = fn()
        icon = ic.get(wid)
        if icon is None:
            raise ValueError(f"{wid}: {ICONS} 에 16px 그림이 없다")
        made[wid] = cm.write_item(out, wid, w, display_for(wid, kind, use), icon, kind, use=use,
                                  use_display=use_display_for(wid, kind, use))
        made[wid]["w"] = w
    return made


# ─────────────────────────── 미리보기 ───────────────────────────

def previews(ids=None, scratch=None):
    import _views as vw
    from PIL import Image
    scratch = scratch or os.path.join(os.environ.get("TMPDIR", "/tmp"), "souls_weapons_b")
    made = build(scratch, only=ids)
    os.makedirs(SHOTS, exist_ok=True)
    rows = []
    for wid, res in made.items():
        fn, kind, use = WEAPONS[wid]
        model = res["3d"]
        disp = display_for(wid, kind, use)
        ic = icons()[wid]
        n_el = len(model.elements)
        n_mat = cm.mat_count(res["w"])
        vw.gui(ic).save(os.path.join(SHOTS, f"{wid}_gui.png"))
        sides = vw.side(model, size=(300, 560))
        vw.strip(sides, ["front +Z", "3/4", "edge"]).save(os.path.join(SHOTS, f"{wid}_side.png"))
        hand = "l" if use == "block" else "r"
        fp_key = "firstperson_righthand"
        fp = vw.first_person([(model, disp[fp_key], hand, None)], size=(854, 480))
        fp.save(os.path.join(SHOTS, f"{wid}_fp.png"))
        tp = vw.third_person([(model, disp["thirdperson_righthand"], hand)],
                             poses=("item", "none") if hand == "r" else ("none", "item"),
                             views=((-35, 10), (90 if hand == "r" else -90, 5)), size=(380, 480), zoom=150)
        vw.strip(tp, ["front 3/4", "side"]).save(os.path.join(SHOTS, f"{wid}_tp.png"))
        print(f"{wid}: 요소 {n_el}, 재료 {n_mat}")
        rows.append((wid, sides[0], n_el))
    return made


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
