"""
무기 공통 부품 (SPEC.md 1절, 4절 "A: _common.py"). set_a.py 와 set_b.py 가 함께 쓴다. 고칠 것이 있으면 A 에게 말한다.

  weapon(mats, kind, seed)         쥐는 점 격자의 wkit Weapon. 설계 원점 (0, 0, 0) = 쥐는 점 = 모형 (8, 8, 8)
                                   범위 X ±24, Y ±48, Z ±16 복셀 (1 복셀 = 1/32 블록). 복셀 가운데는 ±0.5, ±1.5 ...
  pmat(rows, ink, light=0)         손으로 찍은 16×16 재료 칸 (글자 격자, 팔레트 이름만) → wkit Mat. light 는 그 재료 요소의
                                   light_emission (불씨만, 1.8). 셰이더 발광 알파는 쓰지 않는다
  hand_display(kind)               손 자세 (1.3): 3인칭 정한 값 + 1인칭 (분류마다 크기)
  guard_display(kind)              주손 무기 막기 자세 (모형 <id>_guard, 회전만 다르다)
  shield_display(), shield_block_display(), bow_display(), catalyst_display(...)
  write_item(out, wid, ...)        모형 <id>_3d (+ _guard / _block / 활 당김) 쓰기, 16px 그림 <id>, 아이템 정의 (1.9),
                                   wkit 이 같이 쓰는 items/<id>_3d.json 지우기
  load_icons(path) / icon_image(rows, ink)   pack/art/weapon_icons_*.txt 의 16×16 그림

쥐는 점 (1.2)
  모든 souls 손 아이템의 쥐는 점은 모형 (8, 8, 8) 이다. 바닐라는 모형을 (−0.5, −0.5, −0.5) 블록 옮겨 그리므로 손 자세의
  회전과 크기는 쥐는 점을 움직이지 않는다. 3인칭 이동 값 TP_T 는 무기·방패·활·촉매가 모두 같고 회전만 다르다.
  결과: 쥐는 점은 오른팔 모형 좌표 (−1, 8.46, −0.08) 픽셀 (팔 회전 중심 기준, y 는 팔을 따라 아래, −z 가 앞) = 주먹 한가운데.
  구르기 대역·몹·보스 인형이 무기를 쥐는 법은 SPEC.md 1.4 (변환 사슬) 를 본다. 아래 HOLD 표가 그 값들을 모은다.
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACK not in sys.path:
    sys.path.insert(0, PACK)

from mc3d import NS  # noqa: E402
from palette import c as pal  # noqa: E402
from wkit import Mat, Weapon, _euler_xyz, _rot  # noqa: E402

GRID = (48, 96, 32)     # X, Y, Z 복셀
PIVOT = (24, 48, 16)    # 쥐는 점 (격자 안의 자리)

# ─────────────────────────── 격자 ───────────────────────────


class SoulsWeapon(Weapon):
    """wkit Weapon + 재료마다 light_emission (Mat.light). 손 자세는 build(display=...) 로만 준다 (_display 는 쓰지 않는다)."""

    def _emit(self, model, cells, m, *a):
        lv = getattr(self.mats[self.names[m - 1]], "light", 0)
        n0 = len(model.elements)
        super()._emit(model, cells, m, *a)
        if lv:
            for el in model.elements[n0:]:
                el["light_emission"] = int(lv)

    def _display(self):
        raise RuntimeError("souls 무기는 build(..., display=hand_display(...)) 로 손 자세를 준다 (SPEC 1.2)")


def weapon(mats, kind="sword", seed=0):
    """
    설계 원점 = 쥐는 점. kind 는 기록용 (손 자세는 hand_display 가 정한다).
    B 의 _mats.VoxWeapon (같은 격자, Z 칸 경계를 옮겨 가운데에 놓인 날·자루가 앞뒤로 쪼개지지 않는다, 재료 light) 을 쓴다.
    """
    from weapons._mats import VoxWeapon
    return VoxWeapon(mats, seed=seed, kind=kind)


# ─────────────────────────── 재료: 손으로 찍은 칸 ───────────────────────────


class PMat(Mat):
    """글자 격자로 찍은 16×16 칸 (팔레트 이름만). wkit 의 무늬 생성 (잡음, 사인 광택) 은 쓰지 않는다 (SPEC 1.6)."""

    def __init__(self, img, light=0):
        super().__init__(["#000000"] * 4, style="flat")
        self.img = img
        self.light = light

    def cell(self, frame=0, frames=1):
        return self.img.copy()


def tile(rows, ink):
    if len(rows) != 16 or any(len(r) != 16 for r in rows):
        raise ValueError("재료 칸은 16×16 이어야 한다")
    img = Image.new("RGBA", (16, 16))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            px[x, y] = pal(ink[ch])
    return img


def pmat(rows, ink, light=0):
    """rows: 16 줄 × 16 글자, ink: 글자 → 팔레트 이름. 한 글자짜리 rows ("a") 는 민 칸."""
    if isinstance(rows, str):
        rows = [rows * 16] * 16
    return PMat(tile(rows, ink), light=light)


def flat(name, light=0):
    """팔레트 한 색의 민 칸 (작은 쇠붙이, 가장자리 줄처럼 복셀마다 손으로 칠하는 재료)."""
    return pmat("a", {"a": name}, light=light)


# ─────────────────────────── 2D 모양 도구 (설계 X, Y) ───────────────────────────


def poly(pts):
    """XY 다각형 마스크 (짝홀 규칙). pts: [(X, Y)...]"""
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


def capsule(X, Y, p0, p1, r0, r1=None):
    """선분 p0→p1 둘레 반지름 r0→r1 안쪽."""
    r1 = r0 if r1 is None else r1
    ax, ay = p1[0] - p0[0], p1[1] - p0[1]
    L2 = ax * ax + ay * ay or 1e-6
    t = np.clip(((X - p0[0]) * ax + (Y - p0[1]) * ay) / L2, 0, 1)
    d = np.hypot(X - p0[0] - ax * t, Y - p0[1] - ay * t)
    return d <= r0 + (r1 - r0) * t


def at(X, Y, Z, cells):
    """복셀 가운데 좌표 목록 [(X, Y, Z)...] 에 꼭 맞는 마스크 (손으로 한 칸씩 칠할 때). Z 가 None 이면 모든 깊이."""
    m = np.zeros(np.shape(X), bool)
    for x, y, z in cells:
        k = (np.abs(X - x) < 0.01) & (np.abs(Y - y) < 0.01)
        if z is not None:
            k &= np.abs(Z - z) < 0.01
        m |= k
    return m


# ─────────────────────────── 글자 그림으로 쌓기 (앞에서 본 꼴을 손으로 찍는다) ───────────────────────────


def _xi(w, X):
    return int(round(X + w.CX - 0.5))


def _yi(w, Y):
    return int(round(Y + w.CY - 0.5))


def _zs(w, z0, z1):
    """설계 Z 가운데가 z0..z1 (닫힌 범위) 인 격자 Z 칸들."""
    zc = np.arange(w.D) + 0.5 - w.CZ
    return np.nonzero((zc >= z0 - 1e-6) & (zc <= z1 + 1e-6))[0]


def draw(w, rows, legend, x_left, y_top):
    """
    앞 (+Z) 에서 본 글자 그림을 복셀로 쌓는다. 한 글자 = 복셀 한 칸 (X 한 칸, Y 한 칸).
      rows     위 (끝, +Y) 에서 아래로. ' ' 와 '.' 는 비움 (이미 있는 것을 지우지 않는다)
      legend   글자 → (재료, 반두께) 이면 Z 가운데가 ±반두께 안 (1 → 2 복셀, 2 → 4 복셀)
                       (재료, z0, z1) 이면 Z 가운데가 z0..z1 (앞뒤가 다른 쇠붙이, 한쪽으로 나온 것)
                       None 이면 그 칸을 모든 깊이에서 비운다 (이 빠짐, 구멍)
      x_left   맨 왼쪽 글자의 설계 X (복셀 가운데, 예 −1.5)
      y_top    맨 윗줄의 설계 Y (복셀 가운데, 예 31.5)
    """
    for j, row in enumerate(rows):
        yi = _yi(w, y_top - j)
        for i, ch in enumerate(row):
            if ch in " .":
                continue
            if ch not in legend:
                raise KeyError(f"그림 글자 {ch!r} 가 legend 에 없다 (줄 {j}, 칸 {i})")
            xi = _xi(w, x_left + i)
            spec = legend[ch]
            if spec is None:
                w.grid[xi, yi, :] = 0
                continue
            mat = spec[0]
            zz = _zs(w, -spec[1], spec[1]) if len(spec) == 2 else _zs(w, spec[1], spec[2])
            w.grid[xi, yi, zz] = w._id(mat)
    return w


def skin(w, rows, legend, x_left, y_top, side=+1, depth=1):
    """
    겉 칠: 이미 있는 복셀 가운데 앞 (side=+1, +Z 쪽) 또는 뒤 (−1) 의 가장 바깥 depth 칸만 재료를 바꾼다
    (문장, 긁힘, 칠 벗겨짐, 한쪽 면의 녹). 글자 → 재료 이름. ' ' 와 '.' 는 그대로.
    """
    for j, row in enumerate(rows):
        yi = _yi(w, y_top - j)
        for i, ch in enumerate(row):
            if ch in " .":
                continue
            xi = _xi(w, x_left + i)
            col = np.nonzero(w.grid[xi, yi, :])[0]
            if len(col) == 0:
                continue
            zz = col[::-1][:depth] if side > 0 else col[:depth]
            w.grid[xi, yi, zz] = w._id(legend[ch])
    return w


def put(w, cells, mat):
    """설계 좌표 (복셀 가운데) 목록에 재료 (None 이면 비움)."""
    v = 0 if mat is None else w._id(mat)
    for X, Y, Z in cells:
        w.grid[_xi(w, X), _yi(w, Y), int(round(Z + w.CZ - 0.5))] = v
    return w


# ─────────────────────────── 손 자세 (SPEC 1.3) ───────────────────────────
# 셈: wkit 의 hold 식 (바닐라 handheld 자세에서 바닐라 칼 그림의 손잡이 자리 (3, 3, 8) 가 오는 곳에 쥐는 점 (8, 8, 8) 을 놓고,
# 세운 모형을 Rz(−45°) 로 바닐라 대각선에 맞춘다). 쥐는 점이 모형 원점이라 이동 값은 크기와 상관없다.

_C = np.array([8.0, 8.0, 8.0])


def _hold(rot_v, trans_v, s0, extra=(0.0, 0.0, 0.0)):
    rv = _rot(*rot_v)
    r_new = rv @ _rot(0, 0, -45) @ _rot(*extra)
    t = np.array(trans_v) + rv @ (s0 * (np.array([3.0, 3.0, 8.0]) - _C))
    return [round(v, 3) + 0.0 for v in _euler_xyz(r_new)], [round(float(v), 3) + 0.0 for v in t]


TP_ROT, TP_T = _hold([0, -90, 55], [0, 4.0, 0.5], 0.85)        # [-10, -90, 0], [0, -1.919, 1.544]
FP_ROT, FP_T = _hold([0, -90, 25], [1.13, 3.2, 1.13], 0.68)    # [20, -90, 0], [1.13, -1.318, -0.515]
# 창·미늘창: 1인칭에서 Z −20° 를 더해 더 세운다 (머리가 십자선 위로 오지 않게 화면 오른쪽 위 밖으로)
FP_ROT_POLE, _ = _hold([0, -90, 25], [1.13, 3.2, 1.13], 0.68, extra=(0, 0, -20))

# 1인칭 크기 (SPEC 1.3). 긴 무기는 화면에서 쥐는 점 위로 뻗는 길이가 직검과 비슷하게, 짧은 것은 조금 키운다 [미확인 (클라)]
FP_SCALE = {
    "dagger": 0.85, "parrying_dagger": 0.85, "straight_sword": 0.68, "longsword": 0.62, "hand_axe": 0.8,
    "axe": 0.7, "hammer": 0.7, "bell_mace": 0.65, "greatsword": 0.55, "spear": 0.5, "halberd": 0.5,
    "bow": 0.68, "catalyst": 0.85,
}
POLE = ("spear", "halberd")

# 바꿔 들기 몸짓 (아이템 정의의 swap_animation_scale): 무거운 것은 천천히 올라온다
SWAP = {"greatsword": 1.5, "spear": 1.95, "halberd": 1.95, "greatshield": 1.5}


def _t(rot, trans, s):
    return {"rotation": [float(v) for v in rot], "translation": [float(v) for v in trans], "scale": [float(s)] * 3}


def hand_display(kind):
    """무기·쳐내기 단검 (평소). 왼손 값은 비워 둔다 (바닐라가 오른손 값을 거울로 쓴다)."""
    fp_rot = FP_ROT_POLE if kind in POLE else FP_ROT
    return {
        "thirdperson_righthand": _t(TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, FP_T, FP_SCALE[kind]),
    }


# 막기 자세 (주손 무기에 BLOCKS_ATTACKS 가 붙어 막을 때, 모형 <id>_guard). 3인칭은 이동이 그대로라 쥐는 점이 주먹에 남고
# 회전만 다르다. 바닐라 BLOCK 팔 자세 (팔을 앞으로 54° 들고 안쪽으로 30°) 위에서 날이 몸 앞을 비스듬히 가로지른다.
# 1인칭은 바닐라가 방패가 아닌 막기 아이템에 거는 몸짓 (ItemInHandRenderer 의 BLOCK) 뒤에 이 값이 걸린다.
# 값은 _views.py 의 흉내 그림으로 맞췄다 [미확인 (클라)]
GUARD = {
    # 한손 무기: 끝이 몸 안쪽 위, 날 면이 앞 (3인칭), 1인칭은 날이 화면 아래쪽을 가로지른다
    "one_hand": {"tp": [-10, -90, 0], "fp": ([20, -90, 0], [1.13, -1.318, -0.515])},
    "greatsword": {"tp": [-10, -90, 0], "fp": ([20, -90, 0], [1.13, -1.318, -0.515])},
    "pole": {"tp": [-10, -90, 0], "fp": ([20, -90, 0], [1.13, -1.318, -0.515])},
}


def guard_display(kind):
    g = GUARD["greatsword" if kind == "greatsword" else "pole" if kind in POLE else "one_hand"]
    fr, ft = g["fp"]
    return {
        "thirdperson_righthand": _t(g["tp"], TP_T, 1.0),
        "firstperson_righthand": _t(fr, ft, FP_SCALE[kind]),
    }


# 방패 (설계: +Y 위, +Z 앞면, 손잡이는 뒤, 그 가운데가 쥐는 점). 3인칭 이동은 무기와 같다 [미확인 (클라): 회전]
SHIELD_TP_ROT = [90, 90, 0]          # 평소: 앞면이 몸 바깥, 위가 위 (팔꿈치 쪽)
SHIELD_BLOCK_TP_ROT = [-90, 0, 180]  # 막기: 앞면이 팔 앞
SHIELD_FP = ([0, 0, 0], [0, 0, 0])   # set_a 가 방패마다 덮어쓴다 (크기가 달라서)
BOW_TP_ROT = [0, -90, 0]


def shield_display(fp_rot, fp_t, fp_s):
    return {
        "thirdperson_righthand": _t(SHIELD_TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, fp_t, fp_s),
    }


def shield_block_display(fp_rot, fp_t, fp_s):
    return {
        "thirdperson_righthand": _t(SHIELD_BLOCK_TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, fp_t, fp_s),
    }


def bow_display(fp_rot=None, fp_t=None):
    return {
        "thirdperson_righthand": _t(BOW_TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot or FP_ROT, fp_t or FP_T, FP_SCALE["bow"]),
    }


def catalyst_display(fp_rot, fp_t):
    """촉매: 3인칭은 무기 정한 값 그대로, 1인칭 회전·이동은 촉매마다 (크기 0.85)."""
    return {
        "thirdperson_righthand": _t(TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, fp_t, FP_SCALE["catalyst"]),
    }


# 구르기 대역·몹·보스 인형이 쓰는 값 모음 (SPEC 1.4). 플러그인이나 roll_figure 가 숫자를 옮겨 적을 때 이 표를 본다
HOLD = {
    "grip_model": [8, 8, 8],                 # 모형 좌표 (1/16 블록)
    "grip_arm_px": [-1.0, 8.46, -0.08],      # 오른팔 모형 좌표 (픽셀, 팔 회전 중심 기준) — 바닐라 ItemInHandLayer 사슬 끝
    "tp_translation": TP_T,                  # 모든 손 아이템 같다
    "tp_rotation": {"weapon": TP_ROT, "catalyst": TP_ROT, "shield": SHIELD_TP_ROT,
                    "shield_block": SHIELD_BLOCK_TP_ROT, "bow": BOW_TP_ROT},
    # ItemInHandLayer: 팔 변환 뒤 Rx(−90°)·Ry(180°)·T(±1/16, 0.125, −0.625) (오른손 +, 왼손 −) 다음 아이템의 3인칭 자세
    "hand_chain": {"rx": -90, "ry": 180, "t_right": [1 / 16, 0.125, -0.625], "t_left": [-1 / 16, 0.125, -0.625]},
}


# ─────────────────────────── 16px 그림 ───────────────────────────


def load_icons(path):
    """
    [이름] 다음 줄부터 빈 줄까지가 16×16 그림 한 장, '# ' 로 시작하는 줄은 설명.
    [이름.ink] 아래 '기호 팔레트이름' 줄들은 그 그림만의 기호 (없으면 [ink] 공통 기호).
    """
    grids, inks, cur = {}, {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("# ") or line == "#" or not line.strip():
                if not line.strip():
                    cur = None if cur and cur[1] else cur
                continue
            if line.startswith("[") and line.endswith("]"):
                name = line[1:-1]
                if name.endswith(".ink") or name == "ink":
                    cur = (name[:-4] if name.endswith(".ink") else "", True)
                    inks.setdefault(cur[0], {})
                else:
                    cur = (name, False)
                    grids[name] = []
                continue
            if cur is None:
                raise ValueError(f"{path}: 그림 밖의 줄 {line!r}")
            if cur[1]:
                for part in line.split(","):
                    k, v = part.split()
                    inks[cur[0]][k] = v
            else:
                grids[cur[0]].append(line)
    out = {}
    for name, rows in grids.items():
        if len(rows) != 16 or any(len(r) != 16 for r in rows):
            raise ValueError(f"{path} [{name}]: 16×16 이 아니다 ({len(rows)}줄, 폭 {sorted({len(r) for r in rows})})")
        ink = dict(inks.get("", {}))
        ink.update(inks.get(name, {}))
        out[name] = (rows, ink)
    return out


def icon_image(rows, ink, clear="."):
    img = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == clear:
                continue
            if ch not in ink:
                raise ValueError(f"모르는 기호 {ch!r} ({x},{y})")
            px[x, y] = pal(ink[ch])
    return img


# ─────────────────────────── 쓰기 (SPEC 1.9) ───────────────────────────


def _json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
        f.write("\n")


def _ref(name):
    return {"type": "minecraft:model", "model": f"{NS}:item/{name}"}


def _drop_def(assets, name):
    p = os.path.join(assets, "items", name + ".json")
    if os.path.exists(p):
        os.remove(p)


def write_icon(assets, wid, img):
    p = os.path.join(assets, "textures", "item", wid + ".png")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p)
    _json(os.path.join(assets, "models", "item", wid + ".json"),
          {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/{wid}"}})


def write_item(out, wid, w, display, icon, kind, use=None, use_display=None, swap=None, bow_states=None):
    """
    한 아이템을 쓴다. 돌려주는 값: {"3d": Model, "use": Model 또는 None, "pull": [Model ...]}.
      w            SoulsWeapon (평소 모양)
      display      평소 손 자세 (hand_display / shield_display / ...)
      icon         16×16 PIL 그림 (인벤토리·땅·액자·선반)
      kind         FP_SCALE·SWAP 의 열쇠
      use          "guard" (무기 막기) | "block" (방패·쳐내기 단검) | "same" (촉매: 쓰는 중에도 _3d) | "bow"
      use_display  guard / block 모형의 손 자세
      bow_states   활 당김 셋 [SoulsWeapon ×3] (use="bow")
    """
    assets = os.path.join(out, "assets", NS)
    made = {"3d": w.build(f"item/{wid}_3d", assets, display=display), "use": None, "pull": []}
    _drop_def(assets, wid + "_3d")
    write_icon(assets, wid, icon)
    if use in ("guard", "block"):
        _json(os.path.join(assets, "models", "item", f"{wid}_{use}.json"),
              {"parent": f"{NS}:item/{wid}_3d", "display": use_display})
        on_true = _ref(f"{wid}_{use}")
    elif use == "bow":
        for i, st in enumerate(bow_states):
            made["pull"].append(st.build(f"item/{wid}_3d_pulling_{i}", assets, display=display))
            _drop_def(assets, f"{wid}_3d_pulling_{i}")
        on_true = {"type": "minecraft:range_dispatch", "property": "minecraft:use_duration", "scale": 0.05,
                   "entries": [{"threshold": 0.65, "model": _ref(f"{wid}_3d_pulling_1")},
                               {"threshold": 0.9, "model": _ref(f"{wid}_3d_pulling_2")}],
                   "fallback": _ref(f"{wid}_3d_pulling_0")}
    else:
        on_true = _ref(f"{wid}_3d")
    definition = {
        "model": {
            "type": "minecraft:select", "property": "minecraft:display_context",
            "cases": [{"when": ["gui", "ground", "fixed", "on_shelf"], "model": _ref(wid)}],
            "fallback": {"type": "minecraft:condition", "property": "minecraft:using_item",
                         "on_false": _ref(f"{wid}_3d"), "on_true": on_true},
        },
        "swap_animation_scale": float(swap if swap is not None else SWAP.get(kind, 1.0)),
    }
    _json(os.path.join(assets, "items", wid + ".json"), definition)
    return made


def mat_count(w):
    """쓴 재료 수 (16 이하)."""
    return len(set(int(v) for v in np.unique(w.grid)) - {0})


def _selfcheck():
    assert TP_ROT == [-10.0, -90.0, 0.0] and TP_T == [0.0, -1.919, 1.544], (TP_ROT, TP_T)
    assert FP_ROT == [20.0, -90.0, 0.0] and FP_T == [1.13, -1.318, -0.515], (FP_ROT, FP_T)


_selfcheck()
