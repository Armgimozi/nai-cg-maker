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
# 3인칭 셈: wkit 의 hold 식 (바닐라 handheld 자세에서 바닐라 칼 그림의 손잡이 자리 (3, 3, 8) 가 오는 곳에 쥐는 점 (8, 8, 8) 을
# 놓고, 세운 모형을 Rz(−45°) 로 바닐라 대각선에 맞춘다). 쥐는 점이 모형 원점이라 이동 값은 크기와 상관없다.
# 1인칭은 화면 자리로 정한다 (fp_pose): 가드 (자루 무기는 쥐는 점) 와 끝 (자루 무기는 머리 가운데) 이 1280×720 화면의
# 어디에 오는지를 표 FP_AIM 에 적고, 바닐라 1인칭 사슬을 거꾸로 풀어 회전·이동을 셈한다.
# 흉내 그림 (_views.first_person) 은 실제 클라이언트와 픽셀 단위로 맞는다 [확인 (클라)]: 2026-10-07 바닐라 철검 (item/handheld)
# 과 레딘 경비대 직검을 1.21.11 클라이언트 1280×720 화면 위에 겹쳐 그려 가장자리가 1~2 픽셀 안에서 겹쳤다.

_C = np.array([8.0, 8.0, 8.0])


def _hold(rot_v, trans_v, s0, extra=(0.0, 0.0, 0.0)):
    rv = _rot(*rot_v)
    r_new = rv @ _rot(0, 0, -45) @ _rot(*extra)
    t = np.array(trans_v) + rv @ (s0 * (np.array([3.0, 3.0, 8.0]) - _C))
    return [round(v, 3) + 0.0 for v in _euler_xyz(r_new)], [round(float(v), 3) + 0.0 for v in t]


def _deg(R):
    return [round(v, 2) + 0.0 for v in _euler_xyz(R)]


TP_ROT, TP_T = _hold([0, -90, 55], [0, 4.0, 0.5], 0.85)        # [-10, -90, 0], [0, -1.919, 1.544]
# 3인칭 회전은 분류마다 (이동은 TP_T 하나라 쥐는 점은 늘 주먹 한가운데). 직검·단검·도끼·망치·창은 바닐라처럼 앞으로 눕힌다.
# 1.6~2.3 블록인 대검·미늘창을 눕히면 1.4 블록이나 앞으로 나가 마상창처럼 읽혀서, 대검은 끝을 30° 내리고 미늘창은 머리를
# 45° 든다 (아이템 Z 축 둘레, 끝이 아랫날 쪽으로 돌면 내려간다). 쥐는 점이 자루 끝에서 26~28 복셀이라 자루 끝이 땅에 닿지 않는다
TP_ROT_CLASS = {
    "weapon": TP_ROT,
    "greatsword": _deg(_rot(*TP_ROT) @ _rot(0, 0, 30)),          # [−40, −90, 0]
    "polearm": _deg(_rot(*TP_ROT) @ _rot(0, 0, -45)),            # [35, −90, 0]
}
TP_CLASS_OF = {"greatsword": "greatsword", "halberd": "polearm"}
# 구르기 대역이 긴 것 (창, 미늘창, 대검, 대방패) 을 들고 구를 때의 회전: 끝이 아래팔을 따라 팔꿈치 쪽, 앞면 (+Z) 은 몸 안쪽,
# 아랫날 (−X) 은 앞. 이동은 TP_T 그대로라 쥐는 점이 같은 자리에 남는다. 쓰는 법은 tuck_pre() 와 SPEC 1.4
def _tuck():
    # 아이템 축이 팔 좌표에서 X (0,0,1) 뒤, Y (0,−1,0) 어깨 쪽, Z (1,0,0) 몸 안쪽이 되게: R팔 = Rx(−90)·Ry(180)·R자세
    chain = _rot(-90, 0, 0) @ _rot(0, 180, 0)
    want = np.c_[[0, 0, 1], [0, -1, 0], [1, 0, 0]]
    return _deg(chain.T @ want)


ROLL_TUCK = _tuck()                                              # [90, −90, 0]

# ── 1인칭 ──
# 바닐라 ItemInHandRenderer (1.21.11): 손 T(k·0.56, −0.52, −0.72) 뒤 아이템 1인칭 자세 (k 오른손 1). 막기 (BLOCK) 는 그 사이에
# 방패가 아닌 아이템에만 T(k·−0.1414, 0.08, 0.1414)·Rx(−102.25)·Ry(k·13.365)·Rz(k·78.05) 가 더 걸린다 (souls 무기·방패는 껍데기가
# 부싯돌이라 모두). 손 그림은 늘 세로 시야 70° 로 그린다. 화면 비가 16:9 가 아니면 가로 자리만 가운데 쪽으로 줄거나 는다.
FP_SCREEN = (1280, 720, 70.0)


def _m4(R=None, t=(0, 0, 0)):
    m = np.eye(4)
    if R is not None:
        m[:3, :3] = R
    m[:3, 3] = t
    return m


_FP_HAND = _m4(t=(0.56, -0.52, -0.72))
_FP_BLOCK = _FP_HAND @ _m4(t=(-0.14142136, 0.08, 0.14142136)) @ _m4(_rot(-102.25, 0, 0)) @ _m4(_rot(0, 13.365, 0)) \
    @ _m4(_rot(0, 0, 78.05))

# 가드 가운데 (칼, 설계 Y 복셀). 자루 무기는 쥐는 점 (0) 에서 잰다
ANCHOR = {"dagger": 4.5, "parrying_dagger": 5.0, "straight_sword": 6.0, "longsword": 6.0, "greatsword": 6.0}
# 자루 무기의 겨눔점: 맨 끝에서 이만큼 아래 (머리 가운데)
HEAD = {"hand_axe": 4.0, "axe": 6.0, "hammer": 4.0, "bell_mace": 5.0, "spear": 6.0, "halberd": 9.0}

# 1인칭 평소 자세 (분류마다): 가드 (자루 무기는 쥐는 점) 와 끝 (자루 무기는 머리 가운데) 의 화면 자리 (가로, 세로 비율과 카메라
# 깊이 블록), 기준 길이 (복셀, 그 분류의 기준 무기의 가드→끝) 와 날 면이 카메라에서 돌아간 각 phi (0 이면 날 면이 똑바로 보인다).
# 기준 길이의 무기는 끝이 정확히 그 자리에 오고, 더 긴 것은 같은 쪽으로 더 멀리 간다. 크기는 기준 무기에서 나온다.
#   칼: 가드는 오른쪽 아래 (78 %, 88 %) 에 보이고 끝은 가운데 오른쪽 위 (60 %, 35 %) 쪽. 자루 무기는 머리가 오른쪽 가운데,
#   창·미늘창은 머리가 오른쪽 위 (76 %, 22 %) 에 다 보인다 (화면 밖으로 나가지 않는다)
FP_AIM = {
    "dagger":          ((0.78, 0.88, -0.72), (0.705, 0.64, -0.88), 9.5, 25),
    "parrying_dagger": ((0.78, 0.88, -0.72), (0.705, 0.64, -0.88), 10.0, 25),
    "straight_sword":  ((0.78, 0.88, -0.75), (0.60, 0.35, -1.05), 26.0, 25),
    "longsword":       ((0.78, 0.88, -0.75), (0.585, 0.30, -1.10), 30.0, 25),
    "greatsword":      ((0.79, 0.90, -0.80), (0.565, 0.26, -1.20), 34.0, 25),
    "hand_axe":        ((0.83, 0.97, -0.74), (0.73, 0.62, -0.92), 11.0, 20),
    "axe":             ((0.84, 0.98, -0.76), (0.695, 0.47, -1.00), 18.0, 20),
    "hammer":          ((0.84, 0.98, -0.76), (0.695, 0.47, -1.00), 17.0, 20),
    "bell_mace":       ((0.84, 0.98, -0.76), (0.69, 0.43, -1.00), 23.0, 20),
    "spear":           ((0.87, 0.99, -0.85), (0.765, 0.22, -1.30), 40.0, 15),
    "halberd":         ((0.87, 0.99, -0.85), (0.765, 0.22, -1.30), 37.0, 15),
}
POLE = ("spear", "halberd")

# 막기 자세의 1인칭 (바닐라 BLOCK 몸짓 뒤): 날이 화면 아래쪽을 왼쪽으로 가로지르고 십자선 아래에 머문다. 날 면이 화면을 본다.
# 크기는 평소와 같다 (막을 때 무기가 커지거나 줄지 않는다). 십자선 둘레 (가로 38~62 %, 세로 58 % 위) 에 모형이 들어오면
# 겨눔점을 조금씩 내린다 (fp_pose 의 keep_below)
GUARD_AIM = {
    "one_hand":   ((0.80, 0.97, -0.70), (0.30, 0.72, -0.95), 0),
    # 자루 무기 (도끼·망치): 머리가 커서 더 멀리, 화면 가운데 아래로
    "haft":       ((0.84, 1.00, -0.80), (0.44, 0.80, -1.20), 10),
    "greatsword": ((0.67, 1.00, -0.72), (0.43, 0.62, -0.95), 0),
    "pole":       ((0.80, 0.98, -0.78), (0.16, 0.70, -1.15), 0),
}


def _unproject(sx, sy, z):
    W, H, fov = FP_SCREEN
    f = 1.0 / math.tan(math.radians(fov) / 2)
    return np.array([(sx * W - W / 2) / (f * H / 2) * -z, -(sy * H - H / 2) / (f * H / 2) * -z, z])


def _project(P):
    W, H, fov = FP_SCREEN
    f = 1.0 / math.tan(math.radians(fov) / 2)
    return P[..., 0] / -P[..., 2] * f * H / 2 / W + 0.5, -P[..., 1] / -P[..., 2] * f * H / 2 / H + 0.5


def fp_pose(anchor_y, aim_y, scale, a, b, phi, block=False):
    """
    1인칭 자세 셈. anchor_y / aim_y: 설계 Y (복셀) 의 두 점 (가드·끝), scale: 크기, a: (가로, 세로, 깊이) 가드 자리,
    b: (가로, 세로) 겨눔 자리 (그 화면 점을 지나는 시선 위, 가드에서 길이만큼 떨어진 곳에 끝을 둔다. 길이가 모자라면 시선에
    가장 가까운 곳), phi: 날 면 각. block: 바닐라 BLOCK 몸짓 뒤. 돌려주는 값 (rotation, translation) — display 그대로.
    """
    A = _FP_BLOCK if block else _FP_HAND
    Pa = _unproject(*a)
    L = (aim_y - anchor_y) / 32.0 * scale
    r = _unproject(b[0], b[1], -1.0)
    r /= np.linalg.norm(r)
    bq, cq = -2 * r @ Pa, Pa @ Pa - L * L
    disc = bq * bq - 4 * cq
    t = (-bq + math.sqrt(disc)) / 2 if disc >= 0 else -bq / 2
    Pb = t * r
    d = Pb - Pa
    d /= np.linalg.norm(d)
    c = -(Pa + Pb) / 2
    c /= np.linalg.norm(c)
    z0 = c - (c @ d) * d
    z0 /= np.linalg.norm(z0)
    p = math.radians(phi)
    Z = z0 * math.cos(p) + np.cross(d, z0) * math.sin(p)
    Rc = np.c_[np.cross(d, Z), d, Z]
    RA = A[:3, :3]
    Rd = RA.T @ Rc
    t16 = RA.T @ (Pa - A[:3, 3]) - Rd @ (scale * np.array([0.0, anchor_y / 32.0, 0.0]))
    return _deg(Rd), [round(float(v) * 16, 3) + 0.0 for v in t16]


def _fp_points(disp, pts, block=False):
    """설계 복셀 점 (블록, 쥐는 점 기준) → 1인칭 화면 (가로, 세로 비율)."""
    A = _FP_BLOCK if block else _FP_HAND
    M = A @ _m4(t=np.array(disp["translation"]) / 16) @ _m4(_rot(*disp["rotation"])) @ _m4(np.eye(3) * disp["scale"][0])
    P = (M @ np.c_[pts, np.ones(len(pts))].T).T[:, :3]
    return _project(P)


def _extent(w):
    """모형의 위 끝 (설계 Y, 맨 위 복셀의 윗면) 과 복셀 가운데 점들 (블록, 쥐는 점 기준)."""
    idx = np.argwhere(w.grid > 0)
    X = idx[:, 0] + 0.5 - w.CX
    Y = idx[:, 1] + 0.5 - w.CY
    Z = idx[:, 2] + 0.5 - w.CZ
    return float(Y.max() + 0.5), np.c_[X, Y, Z] / 32.0


def _anchor_aim(kind, w):
    top = _extent(w)[0] if w is not None else None
    if kind in ANCHOR:
        anchor = ANCHOR[kind]
        aim = top if top is not None else anchor + FP_AIM[kind][2]
    else:
        anchor = 0.0
        aim = top - HEAD[kind] if top is not None else FP_AIM[kind][2]
    return anchor, aim


def fp_scale(kind):
    a, b, ref, _ = FP_AIM[kind]
    return round(float(np.linalg.norm(_unproject(*b) - _unproject(*a)) / (ref / 32.0)), 3)


FP_SCALE = {k: fp_scale(k) for k in FP_AIM}
FP_SCALE.update({"bow": 0.68, "catalyst": 0.85})

# 바꿔 들기 몸짓 (아이템 정의의 swap_animation_scale): 무거운 것은 천천히 올라온다
SWAP = {"greatsword": 1.5, "spear": 1.95, "halberd": 1.95, "greatshield": 1.5}


def _t(rot, trans, s):
    return {"rotation": [float(v) for v in rot], "translation": [float(v) for v in trans], "scale": [float(s)] * 3}


def tp_rot(kind):
    return TP_ROT_CLASS[TP_CLASS_OF.get(kind, "weapon")]


def hand_display(kind, w=None):
    """
    무기·쳐내기 단검 (평소). w (지은 SoulsWeapon) 를 주면 그 무기의 길이로 1인칭을 셈한다 (없으면 분류의 기준 길이).
    왼손 값은 비워 둔다 (바닐라가 오른손 값을 거울로 쓴다: x 이동과 y·z 회전을 뒤집는다).
    """
    a, b, _, phi = FP_AIM[kind]
    anchor, aim = _anchor_aim(kind, w)
    s = FP_SCALE[kind]
    rot, tr = fp_pose(anchor, aim, s, a, b, phi)
    return {
        "thirdperson_righthand": _t(tp_rot(kind), TP_T, 1.0),
        "firstperson_righthand": _t(rot, tr, s),
        # 구르기 대역용 (SPEC 1.4): ItemDisplay 의 head 맥락으로 그리면 ROLL_TUCK 자세 (쥐는 점은 같은 자리)
        "head": _t(ROLL_TUCK, TP_T, 1.0),
    }


# 막기 자세 (주손 무기에 BLOCKS_ATTACKS 가 붙어 막을 때, 모형 <id>_guard). 3인칭은 이동이 그대로라 쥐는 점이 주먹에 남고
# 회전만 다르다. 바닐라 BLOCK 팔 자세 (팔을 앞으로 54° 들고 안쪽으로 30°) 위에서 날이 몸 앞을 비스듬히 가로지른다.
# 3인칭 값은 _views 흉내 그림으로 맞췄다 [미확인 (클라)]. 1인칭은 GUARD_AIM 의 화면 자리에서 셈한다
GUARD = {
    # 한손 무기: 3인칭은 날이 몸 앞을 비스듬히 가로지르고 (끝이 몸 안쪽 위) 날 면이 앞
    "one_hand": {"tp": [-150, 30, 130]},
    "haft": {"tp": [-150, 30, 130]},
    # 대검: 날 면을 앞으로 세워 방패처럼 (끝이 위, 조금 안쪽)
    "greatsword": {"tp": [-150, 30, 170]},
    # 창·미늘창: 자루를 몸 앞에 비스듬히 (머리가 안쪽 위)
    "pole": {"tp": [30, -30, 40]},
}


def guard_group(kind):
    if kind == "greatsword":
        return "greatsword"
    if kind in POLE:
        return "pole"
    return "haft" if kind in HEAD else "one_hand"


def guard_display(kind, w=None):
    g = guard_group(kind)
    a, b, phi = GUARD_AIM[g]
    anchor, aim = _anchor_aim(kind, w)
    s = FP_SCALE[kind]
    pts = _extent(w)[1] if w is not None else None
    b = list(b)
    for _ in range(20):
        rot, tr = fp_pose(anchor, aim, s, a, b, phi, block=True)
        if pts is None:
            break
        sx, sy = _fp_points(_t(rot, tr, s), pts, block=True)
        near = (sx > 0.38) & (sx < 0.62) & (sy < 0.58)
        if not near.any():
            break
        b[1] += 0.02
    return {
        "thirdperson_righthand": _t(GUARD[g]["tp"], TP_T, 1.0),
        "firstperson_righthand": _t(rot, tr, s),
    }


def tuck_pre(rot_cls):
    """
    구르기 대역이 THIRDPERSON_RIGHTHAND 로 그리면서 자세만 ROLL_TUCK 으로 바꾸려면 손 사슬과 ItemDisplay 의 Y 180° 지움
    사이에 이 4×4 (블록 단위) 를 끼운다: Q = T(t)·R(ROLL_TUCK)·R(rot_cls)⁻¹·T(−t) (t = TP_T/16). rot_cls 는 그 아이템의
    3인칭 회전 (TP_ROT_CLASS 의 하나, 방패 SHIELD_TP_ROT, 활 BOW_TP_ROT). head 맥락을 쓰면 이것이 필요 없다 (모형에 있다).
    """
    t = np.array(TP_T) / 16
    return _m4(t=t) @ _m4(_rot(*ROLL_TUCK) @ _rot(*rot_cls).T) @ _m4(t=-t)


# 방패 (설계: +Y 위, +Z 앞면, 손잡이는 뒤, 그 가운데가 쥐는 점). 3인칭 이동은 무기와 같다 [미확인 (클라): 회전]
SHIELD_TP_ROT = [90, 90, 0]          # 평소: 앞면이 몸 바깥, 위가 팔꿈치 쪽 (팔에 매인 방패라 팔을 따라 기운다)
# 막기: 바닐라 BLOCK 팔 자세 (팔을 앞으로 54° 들고 안쪽으로 30°) 에서 방패가 곧게 서고 앞면이 앞을 본다.
# SPEC 의 첫 값 [−90, 0, 180] 은 흉내 그림에서 앞면이 위를 보아 (_views) 바꿨다 [미확인 (클라)]
SHIELD_BLOCK_TP_ROT = [-145, 40, -180]
SHIELD_FP = ([0, 0, 0], [0, 0, 0])   # set_a 가 방패마다 덮어쓴다 (크기가 달라서)
# 활 평소: 팔을 내린 채 활대가 서고 화살 쪽 (−X) 이 앞. 곧게 세우면 ([−175, −90, 115]) 위 활대가 아래팔을 뚫어서,
# 아이템 Z 축 둘레로 35° 앞으로 기울인다 (위 활대가 팔 앞으로, 아래 활대가 다리 뒤로)
BOW_TP_ROT = _deg(_rot(-175, -90, 115) @ _rot(0, 0, 35))      # [35, −90, 0]
BOW_PULL_TP_ROT = [-125, -80, -125]  # 활 당김 (BOW_AND_ARROW 팔 자세): 활대가 서고 화살이 앞


def shield_display(fp_rot, fp_t, fp_s):
    """방패: 평소 자세가 이미 아래팔을 따라 서 있으므로 구르기 대역의 head 맥락도 같은 회전 (앞면이 몸 바깥)."""
    return {
        "thirdperson_righthand": _t(SHIELD_TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, fp_t, fp_s),
        "head": _t(SHIELD_TP_ROT, TP_T, 1.0),
    }


def shield_block_display(fp_rot, fp_t, fp_s):
    return {
        "thirdperson_righthand": _t(SHIELD_BLOCK_TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, fp_t, fp_s),
    }


def bow_display(tp_rot=None, fp_rot=None, fp_t=None, fp_s=None):
    """활 (설계: 활대 ±Y, 시위 +X, 화살 −X). 3인칭 이동은 정한 값, 회전은 평소·당김이 다르다 (set_a 의 bow_a 가 준다)."""
    return {
        "thirdperson_righthand": _t(tp_rot or BOW_TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, fp_t, fp_s or FP_SCALE["bow"]),
    }


def catalyst_display(fp_rot, fp_t):
    """촉매: 3인칭은 무기 정한 값 그대로, 1인칭 회전·이동은 촉매마다 (크기 0.85)."""
    return {
        "thirdperson_righthand": _t(TP_ROT, TP_T, 1.0),
        "firstperson_righthand": _t(fp_rot, fp_t, FP_SCALE["catalyst"]),
    }


# 구르기 대역·몹·보스 인형이 쓰는 값 모음 (SPEC 1.4). 플러그인이나 roll_figure 가 숫자를 옮겨 적을 때 이 표를 본다.
# 확인: "client" 는 실제 1.21.11 클라이언트 화면으로 본 값, "sim" 은 _views 흉내 그림으로만 맞춘 값
HOLD = {
    "grip_model": [8, 8, 8],                 # 모형 좌표 (1/16 블록). 모든 손 아이템 같다
    "grip_arm_px": [-1.0, 8.46, -0.08],      # 오른팔 모형 좌표 (픽셀, 팔 회전 중심 기준) — 바닐라 ItemInHandLayer 사슬 끝
    "tp_translation": TP_T,                  # 모든 손 아이템 같다 (무기, 막기, 방패, 활, 촉매)
    # 3인칭 회전 (thirdperson_righthand). thirdperson_lefthand 는 어느 모형에도 쓰지 않는다: 바닐라가 오른손 값을 거울로 쓴다
    # (이동 x 와 회전 y·z 의 부호를 뒤집는다). 그래서 왼손의 쥐는 점도 왼주먹 한가운데에 온다
    "tp_rotation": {
        "weapon": TP_ROT,                    # 직검, 장검, 단검, 쳐내기 단검 (평소), 도끼, 망치, 창
        "greatsword": TP_ROT_CLASS["greatsword"],
        "polearm": TP_ROT_CLASS["polearm"],  # 미늘창 둘
        "catalyst": TP_ROT,
        "shield": SHIELD_TP_ROT,
        "bow": BOW_TP_ROT, "bow_pulling": BOW_PULL_TP_ROT,
        # 막는 모형 (<id>_guard, <id>_block): 막는 동안만 (using_item)
        "guard_one_hand": GUARD["one_hand"]["tp"], "guard_greatsword": GUARD["greatsword"]["tp"],
        "guard_pole": GUARD["pole"]["tp"], "shield_block": SHIELD_BLOCK_TP_ROT,
        "parrying_dagger_block": [-160, 30, -170],
    },
    # 구르기 대역이 긴 것을 들고 구를 때 (창, 미늘창, 대검, 대방패): 끝이 아래팔을 따라 팔꿈치 쪽. 쥐는 점은 같은 자리.
    # 모형마다 head 맥락에 이 자세를 넣어 두었다 (ItemDisplay 를 HEAD 로 그리면 된다). THIRDPERSON_RIGHTHAND 그대로 쓰려면 tuck_pre
    "roll_tuck": ROLL_TUCK,
    "roll_tuck_shield": SHIELD_TP_ROT,       # 방패는 평소 자세가 이미 팔을 따른다 (앞면이 몸 바깥)
    # ItemInHandLayer: 팔 변환 뒤 Rx(−90°)·Ry(180°)·T(±1/16, 0.125, −0.625) (오른손 +, 왼손 −) 다음 아이템의 3인칭 자세
    "hand_chain": {"rx": -90, "ry": 180, "t_right": [1 / 16, 0.125, -0.625], "t_left": [-1 / 16, 0.125, -0.625]},
    "checked": {
        "client": ["1인칭 무기 평소 (흉내 그림 = 실제 화면, 바닐라 철검과 직검으로 맞춤)", "3인칭 쥐는 점이 주먹 한가운데",
                   "1인칭·3인칭 모습 (dist/screenshots/weapons/ingame_*.png)"],
        "sim": ["1인칭 막기 (GUARD_AIM)", "방패·활·촉매 1인칭", "3인칭 막기 회전", "roll_tuck"],
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


def write_item(out, wid, w, display, icon, kind, use=None, use_display=None, swap=None, bow_states=None,
               pull_display=None):
    """
    한 아이템을 쓴다. 돌려주는 값: {"3d": Model, "use": Model 또는 None, "pull": [Model ...]}.
      w            SoulsWeapon (평소 모양)
      display      평소 손 자세 (hand_display / shield_display / ...)
      icon         16×16 PIL 그림 (인벤토리·땅·액자·선반)
      kind         FP_SCALE·SWAP 의 열쇠
      use          "guard" (무기 막기) | "block" (방패·쳐내기 단검) | "same" (촉매: 쓰는 중에도 _3d) | "bow"
      use_display  guard / block 모형의 손 자세
      bow_states   활 당김 셋 [SoulsWeapon ×3] (use="bow")
      pull_display 당긴 활 모형의 손 자세 (없으면 display). 당기는 동안 팔 자세가 바뀌므로 따로 둔다
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
            made["pull"].append(st.build(f"item/{wid}_3d_pulling_{i}", assets, display=pull_display or display))
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
    assert TP_ROT_CLASS["greatsword"] == [-40.0, -90.0, 0.0] and TP_ROT_CLASS["polearm"] == [35.0, -90.0, 0.0], TP_ROT_CLASS
    assert ROLL_TUCK == [90.0, -90.0, 0.0], ROLL_TUCK


_selfcheck()
