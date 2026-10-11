"""
무기 공통 부품 (SPEC.md 1절, 4절 "A: _common.py"). set_a.py 와 set_b.py 가 함께 쓴다. 고칠 것이 있으면 A 에게 말한다.

  weapon(mats, kind, seed)         쥐는 점 격자의 wkit Weapon. 설계 원점 (0, 0, 0) = 쥐는 점 = 모형 (8, 8, 8)
                                   범위 X ±24, Y ±48, Z ±16 복셀 (1 복셀 = 1/32 블록). 복셀 가운데는 ±0.5, ±1.5 ...
  pmat(rows, ink, light=0)         손으로 찍은 16×16 재료 칸 (글자 격자, 팔레트 이름만) → wkit Mat. light 는 그 재료 요소의
                                   light_emission (불씨만, 1.8). 셰이더 발광 알파는 쓰지 않는다
  hand_display(kind)               손 자세 (1.3): 그 분류의 바닐라 모형 (handheld, 창, 철퇴) 을 합성한 네 손 맥락 + 구르기 head
  shield_display(), shield_block_display(), bow_display(), catalyst_display()
                                   바닐라 방패·방패 막기·활·handheld 를 합성한 네 손 맥락
  compose(vanilla, q, g, k)        바닐라 display × P (아래 "손 자세") → 우리 display
  write_item(out, wid, ...)        모형 <id>_3d (+ 방패 _block / 활 당김) 쓰기, 16px 그림 <id>, 아이템 정의 (1.9),
                                   wkit 이 같이 쓰는 items/<id>_3d.json 지우기
  load_icons(path) / icon_image(rows, ink)   pack/art/weapon_icons_*.txt 의 16×16 그림

쥐는 점 (1.2)
  모든 souls 손 아이템의 쥐는 점은 모형 (8, 8, 8) 이다. 바닐라는 모형을 (−0.5, −0.5, −0.5) 블록 옮겨 그리므로 손 자세의
  회전과 크기는 쥐는 점을 움직이지 않는다. 손 자세는 바닐라 1.21.11 그대로다 (DECISIONS 2026-10-11): 바닐라 그림의 쥐는 자리에
  우리 쥐는 점이 오도록 바닐라 display 와 합성한다 (아래 "손 자세", 검사 gripcheck.py). handheld 의 쥐는 점은 3인칭 오른팔
  모형 좌표 (−1, 8.46, −0.08) 픽셀 (팔 회전 중심 기준, y 는 팔을 따라 아래, −z 가 앞) = 주먹 한가운데. HOLD 표가 값들을 모은다.
"""
import json
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


def blade(w, rows, legend, x_left, y_top, edges="Ee", dull="e", keep="", base=True, slab=(-0.5, 0.5), thin=(-0.5, -0.5)):
    """
    날 (판정 A3·A4 의 말: 이어진 날 몸 판 두께 2 + 바깥 한 줄 날 끝 두께 1, 이 빠짐은 날 끝 줄에서 한 칸).
      rows   앞 (+Z) 에서 본 날의 꼴. ' ' 비움, 'n' 이 빠짐 (꼴로는 날이지만 비운다), 그 밖의 글자는 legend 의 재료
      legend 글자 → 재료 이름
      edges  늘 얇은 날 끝 글자 (재료는 legend)
      dull   꼴의 가장자리 (여덟 이웃에 빈칸) 에 온 날 몸 글자를 얇게 할 때 쓰는 날 끝 글자 (계단의 안쪽 귀도 날 끝이 되어
             비탈이 계단을 따라 끊기지 않는다)
      keep   가장자리여도 얇게 하지 않는 글자 (외날의 등, 리카소, 쇠붙이)
      base   맨 아랫줄 밑은 가드가 있으니 막힌 것으로 본다
      slab / thin  날 몸과 날 끝의 Z (복셀 가운데 범위). 기본은 칼 (몸 Z −0.5, +0.5 두 칸, 끝 Z −0.5 한 칸). 가운데가 −0.5 인
             B 의 자루 무기는 몸 (−1.5, 0.5) 세 칸, 끝 (−0.5, −0.5) 한 칸으로 앞뒤가 고르다
    """
    H = len(rows)
    Wd = max(len(r) for r in rows)
    grid = [list(r.ljust(Wd)) for r in rows]

    def filled(i, j):
        if j >= H:
            return base and 0 <= i < Wd and grid[H - 1][i] != " "
        if j < 0 or i < 0 or i >= Wd:
            return False
        return grid[j][i] != " "

    thin_z = _zs(w, *thin)
    slab_z = _zs(w, *slab)
    for j in range(H):
        yi = _yi(w, y_top - j)
        for i in range(Wd):
            ch = grid[j][i]
            if ch in " n":
                continue
            xi = _xi(w, x_left + i)
            border = any(not filled(i + di, j + dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj)
            if ch in edges:
                w.grid[xi, yi, thin_z] = w._id(legend[ch])
            elif border and ch not in keep:
                w.grid[xi, yi, thin_z] = w._id(legend[dull])
            else:
                w.grid[xi, yi, slab_z] = w._id(legend[ch])
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


# ─────────────────────────── 손 자세: 바닐라 그대로 (SPEC 1.3, DECISIONS 2026-10-11) ───────────────────────────
# 손에 든 자세는 바닐라 1.21.11 과 똑같다. 우리 것은 모형과 그림뿐이다. 모형을 옮겨 맞추지 않고 바닐라 display 와 합성한다:
#   쥐는 점은 모형 (8, 8, 8) 그대로. 바닐라 모형 (그림 판) 의 쥐는 자리 g_v 와 그림의 축을 정하고,
#   P(p) = Q·K·(p − 8) + g_v  (우리 모형 점 → 그 바닐라 그림의 점) 을 손 맥락마다 바닐라 display 뒤에 붙인다.
#   display 는 T(t)·R·S·(q − 8) 이라 합성하면 rotation = euler(R·Q), translation = t + R·S·(g_v − 8), scale = S·K.
#   왼손은 바닐라가 거울로 쓰는 몫 (ItemTransform.apply: 왼손이면 x 이동과 y·z 회전의 부호를 뒤집는다. 모형에 왼손 값을 적어도
#   그 값을 거울로 쓴다) 을 풀어 실제로 그려지는 변환에서 합성하고, 다시 거울로 적는다. 네 손 맥락을 늘 모두 적는다 (왼손을
#   비우면 바닐라가 오른손 값을 거울로 써서 바닐라 모형과 어긋난다: 활의 왼손은 오른손의 거울이 아니다).
# 바닐라 모형마다 (P 의 Q, K, g_v):
#   handheld         item/handheld (검·도구). 그림 대각선 (1, 1) 이 끝. Q = Rz(−45°), g_v (3, 3, 8) 은 칼 손잡이 위의 점이고
#                    3인칭 오른손에서 팔 한가운데 줄 위 주먹 한가운데 (팔 좌표 (−1, 8.46, −0.08) 픽셀) 에 온다
#   spear            item/spear_in_hand (1.21.11 창). 32×32 그림을 xy 로 두 배 (1.7) 키워 그린다. 그림 대각선 (−1, 1) 이 끝이라
#                    Q = Rz(45°). 그림 한 칸이 우리 복셀 한 칸이 되게 K = xy 반 (크기가 handheld 와 같다: 3인칭 0.85, 1인칭 0.68).
#                    g_v 는 위 주먹 한가운데를 창 그림 공간으로 되돌려 자루 가운데 줄 (x + y = 16) 에 내린 점
#   mace             item/handheld_mace (철퇴). Q = Rz(−45°), g_v 는 주먹 한가운데를 자루 가운데 줄 (x = y) 에 내린 점.
#                    바닐라 철퇴처럼 칼보다 크게 든다 (3인칭 1.0, 1인칭 0.9)
#   shield           item/shield 와 item/shield_blocking (방패 특수 모형 ShieldModel: 모형 모서리 원점에 scale(1, −1, −1). 손잡이
#                    가운데 (0, 0, −2), 판은 z 1..2 앞). Q = I (우리 +Y 위, +Z 앞면, 손잡이는 뒤)
#   bow              item/bow (당김 셋도 같은 display: 바닐라 bow_pulling_* 가 item/bow 를 부모로 둔다). Q = Rz(−45°),
#                    g_v (6, 10, 8) 은 그림의 대칭 줄 (u = v) 위 활대 가운데 (손잡이)
# 분류 → 바닐라 모형 (DECISIONS 2026-10-11 기본안): 창·미늘창은 창, 망치 (곤봉·철퇴·종 철퇴) 는 철퇴, 나머지 무기와 촉매는 handheld,
# 방패는 방패, 활은 활. 열쇠 (master_key) 와 반지는 이미 item/generated (바닐라 trial_key 와 같은 납작 그림) 라 손대지 않는다.
# 팔 자세는 모형이 아니라 아이템이 정한다: 바닐라 창은 아이템 태그 #minecraft:spears 라서 3인칭에서 팔을 들어 앞으로 겨눈다
# (ArmPose.SPEAR). 그래서 플러그인의 창·미늘창 껍데기는 바닐라 창 아이템이다 (item/ItemFactory.SPEAR_SHELL). 방패의 1인칭 막기도
# 아이템이 ShieldItem 이어야 바닐라 방패와 같다 (SHIELD_SHELL). 검사: weapons/gripcheck.py (바닐라 jar 의 값과 견준다)

HANDS = ("thirdperson_righthand", "thirdperson_lefthand", "firstperson_righthand", "firstperson_lefthand")


def _v(r, t, s):
    return {"rotation": list(r), "translation": list(t), "scale": [s] * 3 if not isinstance(s, (list, tuple)) else list(s)}


# 1.21.11 클라이언트 jar 의 값 (assets/minecraft/models/item/*.json, 부모 사슬을 푼 네 손 맥락). gripcheck 가 jar 와 견준다
VANILLA = {
    "handheld": {
        "thirdperson_righthand": _v([0, -90, 55], [0, 4.0, 0.5], 0.85),
        "thirdperson_lefthand": _v([0, 90, -55], [0, 4.0, 0.5], 0.85),
        "firstperson_righthand": _v([0, -90, 25], [1.13, 3.2, 1.13], 0.68),
        "firstperson_lefthand": _v([0, 90, -25], [1.13, 3.2, 1.13], 0.68),
    },
    "spear": {
        "thirdperson_righthand": _v([5, 270, -40], [0, 2, 2], [1.7, 1.7, 0.85]),
        "thirdperson_lefthand": _v([5, -270, 40], [0, 2, 2], [1.7, 1.7, 0.85]),
        "firstperson_righthand": _v([-20, 90, -35], [3.13, 2.0, 0.13], [1.36, 1.36, 0.68]),
        "firstperson_lefthand": _v([-20, -90, 35], [3.13, 2.0, 0.13], [1.36, 1.36, 0.68]),
    },
    "mace": {
        "thirdperson_righthand": _v([0, -90, 55], [0, 4.0, 1], 1),
        "thirdperson_lefthand": _v([0, 90, -55], [0, 4.0, 1], 1),
        "firstperson_righthand": _v([0, -90, 25], [0, 3, 0.8], 0.9),
        "firstperson_lefthand": _v([0, 90, -25], [0, 3, 0.8], 0.9),
    },
    "shield": {
        "thirdperson_righthand": _v([0, 90, 0], [10, 6, -4], 1),
        "thirdperson_lefthand": _v([0, 90, 0], [10, 6, 12], 1),
        "firstperson_righthand": _v([0, 180, 5], [-10, 2, -10], 1.25),
        "firstperson_lefthand": _v([0, 180, 5], [10, 0, -10], 1.25),
    },
    "shield_blocking": {
        "thirdperson_righthand": _v([45, 155, 0], [-3.49, 11, -2], 1),
        "thirdperson_lefthand": _v([45, 155, 0], [11.51, 7, 2.5], 1),
        "firstperson_righthand": _v([0, 180, -5], [-15, 5, -11], 1.25),
        "firstperson_lefthand": _v([0, 180, -5], [5, 5, -11], 1.25),
    },
    "bow": {
        "thirdperson_righthand": _v([-80, 260, -40], [-1, -2, 2.5], 0.9),
        "thirdperson_lefthand": _v([-80, -280, 40], [-1, -2, 2.5], 0.9),
        "firstperson_righthand": _v([0, -90, 25], [1.13, 3.2, 1.13], 0.68),
        "firstperson_lefthand": _v([0, 90, -25], [1.13, 3.2, 1.13], 0.68),
    },
}
# 그 바닐라 모형의 jar 이름과 견줄 바닐라 아이템 (gripcheck, tools/client/grip_shots.sh)
VANILLA_MODEL = {"handheld": "item/handheld", "spear": "item/spear_in_hand", "mace": "item/handheld_mace",
                 "shield": "item/shield", "shield_blocking": "item/shield_blocking", "bow": "item/bow"}

# P 의 값: q (Rz 각, 도), k (xy 배율), g (바닐라 그림의 쥐는 자리, 모형 픽셀). g 를 셈하는 법은 gripcheck.grip_points
GRIP = {
    "handheld": {"q": -45.0, "k": 1.0, "g": (3.0, 3.0, 8.0)},
    "spear": {"q": 45.0, "k": 0.5, "g": (9.630, 6.370, 8.0)},
    "mace": {"q": -45.0, "k": 1.0, "g": (3.811, 3.811, 8.0)},
    "shield": {"q": 0.0, "k": 1.0, "g": (0.0, 0.0, -2.0)},
    "shield_blocking": {"q": 0.0, "k": 1.0, "g": (0.0, 0.0, -2.0)},
    "bow": {"q": -45.0, "k": 1.0, "g": (6.0, 10.0, 8.0)},
}
# 분류 (weapon(kind=...), write_item 의 kind) → 바닐라 모형. 여기 없는 분류 (칼 넷, 도끼 둘, 패링 단검, 촉매) 는 handheld
GRIP_OF = {"spear": "spear", "halberd": "spear", "hammer": "mace", "bell_mace": "mace",
           "small_shield": "shield", "shield": "shield", "greatshield": "shield", "bow": "bow"}


def grip_set(kind):
    return GRIP_OF.get(kind, "handheld")


def _eff(d, left):
    """모형 display 한 칸 → 실제로 그려지는 (R, t 픽셀, S) (바닐라 ItemTransform.apply 의 왼손 거울 포함)."""
    r = [float(v) for v in d.get("rotation", [0, 0, 0])]
    t = [float(v) for v in d.get("translation", [0, 0, 0])]
    s = [float(v) for v in d.get("scale", [1, 1, 1])]
    if left:
        r = [r[0], -r[1], -r[2]]
        t = [-t[0], t[1], t[2]]
    return _rot(*r), np.array(t), np.diag(s)


def _num(v, nd=3):
    v = round(float(v), nd) + 0.0
    return 0.0 if v == 0 else v


def p_matrix(q=0.0, k=1.0):
    """P 의 선형 몫 Q·K (3×3)."""
    return _rot(0, 0, q) @ np.diag([k, k, 1.0])


def compose(vanilla, q=0.0, g=(8.0, 8.0, 8.0), k=1.0):
    """바닐라 display (네 손 맥락) × P → 우리 display (네 손 맥락). P(p) = Rz(q)·diag(k, k, 1)·(p − 8) + g."""
    Q = p_matrix(q, k)
    g = np.array(g, float)
    out = {}
    for ctx in HANDS:
        left = ctx.endswith("lefthand")
        R, t, S = _eff(vanilla[ctx], left)
        M = R @ S @ Q
        MtM = M.T @ M
        if not np.allclose(MtM, np.diag(np.diag(MtM)), atol=1e-9):
            raise ValueError(f"{ctx}: R·S·Q 가 회전·크기로 나뉘지 않는다 (P 의 축이 바닐라 크기 축과 어긋남)")
        s = np.sqrt(np.diag(MtM))
        R2 = M @ np.diag(1 / s)
        t2 = t + R @ S @ (g - 8.0)
        e = _euler_xyz(R2)
        if left:      # 실제 변환 → 적는 값 (바닐라가 다시 거울로 쓴다)
            e = [e[0], -e[1], -e[2]]
            t2 = np.array([-t2[0], t2[1], t2[2]])
        out[ctx] = {"rotation": [_num(v) for v in e], "translation": [_num(v) for v in t2],
                    "scale": [_num(v, 4) for v in s]}
    return out


def vanilla_display(name):
    """바닐라 모형 name (GRIP 의 열쇠) 의 자세를 우리 모형에 합성한 네 손 맥락."""
    p = GRIP[name]
    return compose(VANILLA[name], p["q"], p["g"], p["k"])


# 구르기 대역 (combat/Tumble) 이 긴 것을 들고 구를 때 쓸 수 있는 회전 (head 맥락, SPEC 1.4): 끝이 아래팔을 따라 팔꿈치 쪽, 앞면 (+Z) 은
# 몸 안쪽, 아랫날 (−X) 은 앞. 이동·크기는 그 아이템의 3인칭 오른손 값 그대로라 쥐는 점이 같은 자리에 남는다 (handheld 0.85).
# 대역은 지금 THIRDPERSON_RIGHTHAND / LEFTHAND 로 그린다 (바닐라 자세 그대로). 쓰는 법은 tuck_pre() 와 SPEC 1.4
def _tuck():
    # 아이템 축이 팔 좌표에서 X (0,0,1) 뒤, Y (0,−1,0) 어깨 쪽, Z (1,0,0) 몸 안쪽이 되게: R팔 = Rx(−90)·Ry(180)·R자세
    chain = _rot(-90, 0, 0) @ _rot(0, 180, 0)
    want = np.c_[[0, 0, 1], [0, -1, 0], [1, 0, 0]]
    return [_num(v, 2) for v in _euler_xyz(chain.T @ want)]


ROLL_TUCK = _tuck()                                              # [90, −90, 0]


def _m4(R=None, t=(0, 0, 0)):
    m = np.eye(4)
    if R is not None:
        m[:3, :3] = R
    m[:3, 3] = t
    return m


def _t(rot, trans, s):
    s = list(s) if isinstance(s, (list, tuple)) else [s] * 3
    return {"rotation": [float(v) for v in rot], "translation": [float(v) for v in trans], "scale": [float(v) for v in s]}


def _with_head(disp, rot):
    """구르기 자세 (head 맥락): 회전 rot, 이동·크기는 3인칭 오른손 값."""
    tp = disp["thirdperson_righthand"]
    out = dict(disp)
    out["head"] = _t(rot, tp["translation"], tp["scale"])
    return out


def hand_display(kind):
    """무기 (분류 kind), 패링 단검, 촉매의 손 자세: 바닐라 모형 (grip_set) 의 네 손 맥락 + 구르기 head."""
    return _with_head(vanilla_display(grip_set(kind)), ROLL_TUCK)


def catalyst_display():
    """촉매 (쇠단지, 손종): 바닐라 검처럼 handheld."""
    return hand_display("catalyst")


def shield_display():
    """방패 평소: 바닐라 item/shield. 구르기 head 는 평소 자세 그대로 (이미 아래팔을 따른다)."""
    d = vanilla_display("shield")
    return _with_head(d, d["thirdperson_righthand"]["rotation"])


def shield_block_display():
    """방패 막기 (using_item, 모형 <id>_block): 바닐라 item/shield_blocking. 껍데기가 바닐라 방패라 1인칭에 칼 막기 몸짓이 붙지 않는다."""
    return vanilla_display("shield_blocking")


def bow_display():
    """활: 바닐라 item/bow. 평소와 당김 셋 (_3d_pulling_0..2) 이 같은 display (바닐라 bow_pulling_* 가 item/bow 를 부모로 둔다)."""
    return vanilla_display("bow")


def tuck_pre(tp):
    """
    구르기 대역이 THIRDPERSON_RIGHTHAND 로 그리면서 자세만 ROLL_TUCK 으로 바꾸려면 손 사슬과 ItemDisplay 의 Y 180° 지움
    사이에 이 4×4 (블록 단위) 를 끼운다: Q = T(t)·R(ROLL_TUCK)·R(tp)⁻¹·T(−t) (t = tp 이동/16, 크기는 head 가 tp 와 같아 빠진다).
    tp 는 그 아이템 모형의 thirdperson_righthand display. head 맥락을 쓰면 이것이 필요 없다 (모형에 있다).
    """
    t = np.array(tp["translation"], float) / 16
    return _m4(t=t) @ _m4(_rot(*ROLL_TUCK) @ _rot(*tp["rotation"]).T) @ _m4(t=-t)


# 바꿔 들기 몸짓 (아이템 정의의 swap_animation_scale): 바닐라 아이템 정의 그대로. 창·미늘창은 바닐라 창 (items/iron_spear.json
# 1.95), 나머지 (검, 철퇴, 방패, 활) 는 바닐라 기본 1.0
SWAP = {"spear": 1.95, "halberd": 1.95}


def _arm_px(disp, left=False):
    """3인칭 쥐는 점 (모형 (8, 8, 8)) 의 팔 모형 좌표 (픽셀, 팔 회전 중심 기준, y 는 팔을 따라 아래, −z 가 앞)."""
    ctx = "thirdperson_lefthand" if left else "thirdperson_righthand"
    _, t, _ = _eff(disp[ctx], left)
    k = -1 if left else 1
    p = np.array([k / 16, 0.125, -0.625]) + t / 16
    return [_num(v * 16, 2) for v in _rot(-90, 0, 0) @ _rot(0, 180, 0) @ p]


# 구르기 대역·몹·보스 인형이 쓰는 값 모음 (SPEC 1.4). 플러그인이나 roll_figure 가 숫자를 옮겨 적을 때 이 표를 본다.
HOLD = {
    "grip_model": [8, 8, 8],                 # 모형 좌표 (1/16 블록). 모든 손 아이템 같다
    # 바닐라 모형마다 3인칭 오른손 쥐는 점의 팔 모형 좌표 (픽셀). handheld 는 주먹 한가운데 (−1, 8.46, −0.08)
    "grip_arm_px": {name: _arm_px(vanilla_display(name)) for name in ("handheld", "spear", "mace", "shield", "bow")},
    "grip_set": dict(GRIP_OF, default="handheld"),
    "vanilla": {name: dict(GRIP[name], model=VANILLA_MODEL[name]) for name in GRIP},
    # 3인칭 오른손 display (왼손은 모형에 따로 적었다. 바닐라처럼 ItemTransform 이 거울로 쓴다)
    "tp_righthand": {name: vanilla_display(name)["thirdperson_righthand"] for name in GRIP},
    "roll_tuck": ROLL_TUCK,                  # head 맥락의 회전 (무기·촉매). 방패는 평소 자세. 활은 head 가 없다
    # ItemInHandLayer: 팔 변환 뒤 Rx(−90°)·Ry(180°)·T(±1/16, 0.125, −0.625) (오른손 +, 왼손 −) 다음 아이템의 3인칭 자세
    "hand_chain": {"rx": -90, "ry": 180, "t_right": [1 / 16, 0.125, -0.625], "t_left": [-1 / 16, 0.125, -0.625]},
    "checked": {
        "client": ["시험 모형 souls:test_grip_* 를 바닐라 철검·창·철퇴·방패·활과 겹쳐 본 것 (tools/client/grip_shots.sh, "
                   "dist/screenshots/grip/)"],
        "sim": ["roll_tuck (head 맥락, 구르기 대역이 아직 쓰지 않는다)"],
    },
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


def _need_hands(wid, display):
    miss = [c for c in HANDS if c not in (display or {})]
    if miss:
        raise ValueError(f"{wid}: 손 맥락 {miss} 가 없다 (바닐라 자세는 네 손 맥락을 모두 적는다, SPEC 1.3)")


def write_item(out, wid, w, display, icon, kind, use=None, use_display=None, swap=None, bow_states=None):
    """
    한 아이템을 쓴다. 돌려주는 값: {"3d": Model, "use": None, "pull": [Model ...]}.
      w            SoulsWeapon (평소 모양)
      display      손 자세 (hand_display / shield_display / bow_display / catalyst_display): 네 손 맥락 모두
      icon         16×16 PIL 그림 (인벤토리·땅·액자·선반)
      kind         SWAP 의 열쇠 (분류)
      use          None (무기·패링 단검·촉매: 쓰는 중에도 _3d. 무기 막기는 바닐라 칼 막기 몸짓이 _3d 위에 걸린다) |
                   "block" (방패: 모형 <id>_block, 바닐라 방패 막기) | "bow" (당김 셋 _3d_pulling_0..2, 같은 display)
      use_display  방패 막기 모형의 손 자세 (shield_block_display)
      bow_states   활 당김 셋 [SoulsWeapon ×3] (use="bow")
    """
    if use not in (None, "block", "bow"):
        raise ValueError(f"{wid}: use={use!r} — 무기 막기 모형 (_guard) 은 없앴다 (바닐라 칼 막기, SPEC 1.3)")
    _need_hands(wid, display)
    assets = os.path.join(out, "assets", NS)
    made = {"3d": w.build(f"item/{wid}_3d", assets, display=display), "use": None, "pull": []}
    _drop_def(assets, wid + "_3d")
    write_icon(assets, wid, icon)
    if use == "block":
        _need_hands(wid + "_block", use_display)
        _json(os.path.join(assets, "models", "item", f"{wid}_block.json"),
              {"parent": f"{NS}:item/{wid}_3d", "display": use_display})
        on_true = _ref(f"{wid}_block")
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
    fallback = _ref(f"{wid}_3d") if use is None else {
        "type": "minecraft:condition", "property": "minecraft:using_item", "on_false": _ref(f"{wid}_3d"), "on_true": on_true}
    definition = {
        "model": {
            "type": "minecraft:select", "property": "minecraft:display_context",
            "cases": [{"when": ["gui", "ground", "fixed", "on_shelf"], "model": _ref(wid)}],
            "fallback": fallback,
        },
        "swap_animation_scale": float(swap if swap is not None else SWAP.get(kind, 1.0)),
    }
    _json(os.path.join(assets, "items", wid + ".json"), definition)
    return made


def mat_count(w):
    """쓴 재료 수 (16 이하)."""
    return len(set(int(v) for v in np.unique(w.grid)) - {0})


def _selfcheck():
    # M1 계획 P0 의 표 (바닐라 handheld·방패·방패 막기·활을 우리 모형에 합성한 값)
    h = vanilla_display("handheld")
    assert h["thirdperson_righthand"] == _t([-10, -90, 0], [0, -1.919, 1.544], 0.85), h["thirdperson_righthand"]
    assert h["thirdperson_lefthand"] == _t([-10, 90, 0], [0, -1.919, 1.544], 0.85), h["thirdperson_lefthand"]
    assert h["firstperson_righthand"] == _t([20, -90, 0], [1.13, -1.318, -0.515], 0.68), h["firstperson_righthand"]
    assert h["firstperson_lefthand"] == _t([20, 90, 0], [1.13, -1.318, -0.515], 0.68), h["firstperson_lefthand"]
    sh, bl, bw = vanilla_display("shield"), vanilla_display("shield_blocking"), vanilla_display("bow")
    assert sh["thirdperson_righthand"] == _t([0, 90, 0], [0, -2, 4], 1) == sh["thirdperson_lefthand"], sh
    assert sh["firstperson_righthand"] == _t([-180, 0, -175], [-0.91, -8.834, 2.5], 1.25), sh
    assert sh["firstperson_lefthand"] == _t([-180, 0, -175], [-0.834, -9.09, 2.5], 1.25), sh
    assert bl["thirdperson_righthand"] == _t([-135, 25, -180], [-0.466, -3.456, 1.142], 1), bl
    assert bl["thirdperson_lefthand"] == _t([-135, 25, 180], [0.033, -2.675, 0.861], 1), bl
    assert bl["firstperson_righthand"] == _t([-180, 0, 175], [-4.166, -4.09, 1.5], 1.25), bl
    assert bl["firstperson_lefthand"] == _t([-180, 0, 175], [-4.09, -5.834, 1.5], 1.25), bl
    assert bw["thirdperson_righthand"] == _t([100, -80, 95], [-0.961, -1.775, -0.035], 0.9), bw
    assert bw["thirdperson_lefthand"] == _t([-80, 80, 85], [-0.961, -1.775, -0.035], 0.9), bw
    assert bw["firstperson_righthand"] == _t([20, -90, 0], [1.13, 3.858, -0.677], 0.68), bw
    assert bw["firstperson_lefthand"] == _t([20, 90, 0], [1.13, 3.858, -0.677], 0.68), bw
    # 창은 handheld 크기 (K = 반), 철퇴는 바닐라 철퇴 크기
    sp, mc = vanilla_display("spear"), vanilla_display("mace")
    assert sp["thirdperson_righthand"]["scale"] == [0.85] * 3 and sp["firstperson_righthand"]["scale"] == [0.68] * 3, sp
    assert mc["thirdperson_righthand"]["scale"] == [1.0] * 3 and mc["firstperson_righthand"]["scale"] == [0.9] * 3, mc
    assert HOLD["grip_arm_px"]["handheld"] == [-1.0, 8.46, -0.08], HOLD["grip_arm_px"]
    assert ROLL_TUCK == [90.0, -90.0, 0.0], ROLL_TUCK


_selfcheck()
