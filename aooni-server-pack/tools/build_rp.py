"""아오오니 저택 리소스팩 생성기 (표준 라이브러리만 사용).

  python tools/build_rp.py                    # dist/aooni-resourcepack.zip + tools/rp_parts.json
  python tools/build_rp.py --preview DIR      # 미리보기 PNG 도 그린다 (Pillow·numpy 필요, tools/rp_preview.py)

만드는 것
  - pack.mcmeta / pack.png
  - 아오오니 부위 모델 6개  aooni:oni_head, oni_torso, oni_arm_l, oni_arm_r, oni_leg_l, oni_leg_r
    (텍스처 한 장 aooni:item/oni, 256x256)
  - 마검  aooni:magum (handheld, 32x32 텍스처 aooni:item/magum)
  - tools/rp_parts.json : 데이터팩이 item_display 로 조립·애니메이션할 때 쓰는 관절 좌표표

좌표 약속 (tools/rp_parts.json 의 notes 에 클라이언트 바이트코드 근거가 있다)
  - 부위 모델마다 관절(회전축)은 모델 픽셀 (8,8,8) = item_display 의 원점.
  - 엔티티 기준 축(yaw 0): +Y 위, +Z 앞(아오오니 얼굴 방향, 남쪽), +X 는 아오오니의 왼쪽(동쪽).
  - item_display 는 렌더 때 Y 축 180도를 돌리므로, 모델 파일 안에서는 얼굴을 north(-Z) 면에 둔다.
    변환식: 모델px = (8 - 16*lx, 8 + 16*ly, 8 - 16*lz)   (lx,ly,lz = 관절 기준 엔티티 좌표, 블록)
  - 이 파일 안의 형상 수치는 q 단위(1 블록 = 32 q = 16 모델px)로 적는다.

머리 안의 카메라
  아오오니 플레이어의 눈(서 있을 때 1.62, 웅크릴 때 1.27)은 머리 안에 있다. 머리를 볼록한 모양(턱 모서리는
  22.5도 비스듬한 쐐기)으로 만들고 서로 맞닿아 가려지는 안쪽 면은 모두 뺐으므로, 눈에서 보이는 머리 면은
  전부 뒷면 → 그려지지 않는다. 얼굴 무늬는 앞면 텍스처로만 그린다(튀어나온 요소 없음).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
OUT_ZIP = os.path.join(DIST, "aooni-resourcepack.zip")
MANIFEST = os.path.join(HERE, "rp_parts.json")
NS = "aooni"
STAMP = (2026, 1, 1, 0, 0, 0)

# ------------------------------------------------------------------ 팩 포맷
# misode/mcmeta summary/versions/data.json 의 resource_pack_version(.minor)
RP_FORMATS = [("1.21.5", 55, 0), ("1.21.6", 63, 0), ("1.21.7", 64, 0), ("1.21.8", 64, 0),
              ("1.21.9", 69, 0), ("1.21.10", 69, 0), ("1.21.11", 75, 0),
              ("26.1", 84, 0), ("26.1.1", 84, 0), ("26.1.2", 84, 0), ("26.2", 88, 0), ("26.3", 97, 1)]
RP_MIN, RP_MAX = 55, 97
LAST_PRE_MINOR_RP = 64     # PackFormat.lastPreMinorVersion(CLIENT_RESOURCES), 1.21.9+ 클라이언트
DESCRIPTION = [{"text": "아오오니 저택 ", "color": "blue"},
               {"text": "아오오니 모형 · 마검 (1.21.5~26.3)", "color": "gray"}]

Q = 32            # 1 블록 = 32 q
ATLAS = 256       # aooni:item/oni 한 변 텍셀 수
UV_PER_TEXEL = 16 / ATLAS

# ------------------------------------------------------------------ 형상 (q 단위, 관절 기준, +X=아오오니 왼쪽, +Z=앞)
# E(이름, (x0,y0,z0), (x1,y1,z1), 생략할 면, 회전)
#   면 이름: front/back/left/right/up/down. 생략 면 = 다른 요소에 가려 밖에서 안 보이는 면.
#   회전: (축 위의 점 (x, y), 각도) — 엔티티 기준 +Z 축(앞 방향) 둘레, 오른손 법칙. 1.21.5 는 ±22.5/±45 만 허용.


def E(name, lo, hi, skip=(), rot=None):
    return {"name": name, "lo": lo, "hi": hi, "skip": set(skip), "rot": rot}


T225 = math.tan(math.radians(22.5))
FLARE = 4                       # 볼이 턱보다 한쪽으로 넓은 정도
CHIN_Y = -3                     # 머리 맨 아래 (목 관절 기준) → 1.2188 블록, 웅크린 눈 1.27 보다 아래
CHEEK_Y = CHIN_Y + FLARE / T225     # 턱 쐐기 위 끝 = 볼 상자 아래 끝 (6.657)
WEDGE_L = FLARE / math.sin(math.radians(22.5))
WEDGE_T = 4
EPS = 0.1                       # 쐐기 앞뒤 면을 살짝 안으로 (겹치는 앞면과 z-fighting 방지)
HEAD_ELEMENTS = [
    E("core", (-11, CHIN_Y, -12), (11, 28, 14), {"left", "right"}),
    E("cheek_l", (11, CHEEK_Y, -12), (15, 28, 14), {"right", "down"}),
    E("cheek_r", (-15, CHEEK_Y, -12), (-11, 28, 14), {"left", "down"}),
    E("jaw_l", (11 - WEDGE_T, CHIN_Y, -12 + EPS), (11, CHIN_Y + WEDGE_L, 14 - EPS), {"right", "up", "down"}, ((11, CHIN_Y), -22.5)),
    E("jaw_r", (-11, CHIN_Y, -12 + EPS), (-11 + WEDGE_T, CHIN_Y + WEDGE_L, 14 - EPS), {"left", "up", "down"}, ((-11, CHIN_Y), 22.5)),
    E("crown", (-14, 28, -11), (14, 31, 13), {"down"}),
    E("crown_top", (-12.5, 31, -9.5), (12.5, 34, 11.5), {"down"}),
]
LIMB_ARM = [E("arm", (-2.5, -24, -2.5), (2.5, 2, 2.5), {"down"}),
            E("hand", (-3, -28, -2.5), (3, -24, 3.5))]
LIMB_LEG = [E("thigh", (-3.5, -11, -3.5), (3.5, 1, 3.5)),
            E("shin", (-3, -20, -3), (3, -11, 3), {"up", "down"}),
            E("foot", (-3, -23, -3.5), (3, -20, 6.5))]
PARTS = {
    "head": {"joint": (0, 42, 0), "parent": "torso", "swing": 30, "range": (-30, 30), "density": 2,
             "desc": "머리 (목 관절에서 위로). 각도 + = 고개 숙임", "elements": HEAD_ELEMENTS},
    "torso": {"joint": (0, 23, 0), "parent": None, "swing": 15, "range": (-10, 15), "density": 2,
              "desc": "몸통 (엉덩이 관절에서 위로). 각도 + = 앞으로 숙임",
              "elements": [E("belly", (-7, -2, -4), (7, 10, 4), {"up"}),
                           # 가슴 윗면은 머리 속에 묻혀 밖에서 안 보인다 → 빼서, 아오오니가 내려다볼 때 발밑이 보이게
                           E("chest", (-9, 10, -5), (9, 20, 5), {"up"})]},
    "arm_l": {"joint": (11.5, 41, 0), "parent": "torso", "swing": 60, "range": (-90, 60), "density": 2,
              "desc": "왼팔 (어깨 관절에서 아래로). 각도 - = 앞으로", "elements": LIMB_ARM},
    "arm_r": {"joint": (-11.5, 41, 0), "parent": "torso", "swing": 60, "range": (-90, 60), "density": 2, "mirror": "arm_l",
              "desc": "오른팔 (어깨 관절에서 아래로). 각도 - = 앞으로", "elements": LIMB_ARM},
    "leg_l": {"joint": (4.5, 23, 0), "parent": None, "swing": 40, "range": (-45, 45), "density": 2,
              "desc": "왼다리 (엉덩이 관절에서 아래로). 각도 - = 앞으로", "elements": LIMB_LEG},
    "leg_r": {"joint": (-4.5, 23, 0), "parent": None, "swing": 40, "range": (-45, 45), "density": 2, "mirror": "leg_l",
              "desc": "오른다리 (엉덩이 관절에서 아래로). 각도 - = 앞으로", "elements": LIMB_LEG},
}
PART_ORDER = ["head", "torso", "arm_l", "arm_r", "leg_l", "leg_r"]
EYE_STAND, EYE_SNEAK = 1.62, 1.27

# 엔티티 기준 방향 → 모델 면 이름 (item_display 의 Y 180도 회전 때문에 앞 = north)
DIR_TO_FACE = {"front": "north", "back": "south", "left": "west", "right": "east", "up": "up", "down": "down"}
MIRROR_FACE = {"west": "east", "east": "west"}
# FaceInfo (클라이언트) 의 꼭짓점 순서. 꼭짓점 i 의 UV: 0=(u1,v1) 1=(u1,v2) 2=(u2,v2) 3=(u2,v1)
FACE_VERTS = {
    "down": [("x0", "y0", "z1"), ("x0", "y0", "z0"), ("x1", "y0", "z0"), ("x1", "y0", "z1")],
    "up": [("x0", "y1", "z0"), ("x0", "y1", "z1"), ("x1", "y1", "z1"), ("x1", "y1", "z0")],
    "north": [("x1", "y1", "z0"), ("x1", "y0", "z0"), ("x0", "y0", "z0"), ("x0", "y1", "z0")],
    "south": [("x0", "y1", "z1"), ("x0", "y0", "z1"), ("x1", "y0", "z1"), ("x1", "y1", "z1")],
    "west": [("x0", "y1", "z0"), ("x0", "y0", "z0"), ("x0", "y0", "z1"), ("x0", "y1", "z1")],
    "east": [("x1", "y1", "z1"), ("x1", "y0", "z1"), ("x1", "y0", "z0"), ("x1", "y1", "z0")],
}


def to_model(p):
    """관절 기준 엔티티 좌표(q) → 모델 픽셀."""
    x, y, z = p
    return (8 - x / 2, 8 + y / 2, 8 - z / 2)


def to_local(m):
    """모델 픽셀 → 관절 기준 엔티티 좌표(q)."""
    px, py, pz = m
    return ((8 - px) * 2, (py - 8) * 2, (8 - pz) * 2)


def element_box(lo, hi):
    a, b = to_model(lo), to_model(hi)
    return tuple(min(a[i], b[i]) for i in range(3)), tuple(max(a[i], b[i]) for i in range(3))


def model_rotation(el):
    """엔티티 기준 Z 축 회전 → 모델 JSON 의 rotation. 모델 공간에서는 축이 뒤집혀 각도 부호가 반대."""
    if not el["rot"]:
        return None
    (px, py), ang = el["rot"]
    ox, oy, oz = to_model((px, py, 0))
    return {"origin": [round(ox, 4), round(oy, 4), round(oz, 4)], "axis": "z", "angle": -ang, "rescale": False}


def rotate_model_point(m, rot):
    """클라이언트와 같이: Matrix4f.rotation(angle, +axis) 를 origin 둘레로 (모델 공간)."""
    if not rot:
        return m
    a = math.radians(rot["angle"])
    c, s = math.cos(a), math.sin(a)
    ox, oy, _ = rot["origin"]
    x, y = m[0] - ox, m[1] - oy
    return (ox + x * c - y * s, oy + x * s + y * c, m[2])


def face_size(frm, to, face):
    dx, dy, dz = ((to[i] - frm[i]) * 2 for i in range(3))   # q
    if face in ("north", "south"):
        return dx, dy
    if face in ("east", "west"):
        return dz, dy
    return dx, dz


def face_point(frm, to, face, s, t):
    """면 위 UV 비율 (s: u1→u2, t: v1→v2) 의 모델 좌표 (회전 전)."""
    ext = {"x0": frm[0], "x1": to[0], "y0": frm[1], "y1": to[1], "z0": frm[2], "z1": to[2]}
    v = [tuple(ext[k] for k in vert) for vert in FACE_VERTS[face]]
    return tuple(v[0][i] + s * (v[3][i] - v[0][i]) + t * (v[1][i] - v[0][i]) for i in range(3))


# ------------------------------------------------------------------ 색칠
BASE = (59, 84, 216)          # #3b54d8
LIP_UP = (78, 44, 152)
LIP_LO = (96, 60, 178)
LIP_HI = (150, 114, 226)
MOUTH = (20, 6, 40)
SCLERA = (252, 252, 248)
SCLERA_SH = (206, 210, 228)
EYE_RIM = (16, 18, 52)
PUPIL = (8, 8, 12)
DARK_LINE = (22, 30, 100)
DIRF = {"up": 1.10, "front": 1.0, "back": 0.92, "left": 0.96, "right": 0.96, "down": 0.72}


def clamp01(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def mul(c, f):
    return tuple(max(0, min(255, int(round(ch * f)))) for ch in c)


def mix(a, b, t):
    t = clamp01(t)
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def hnoise(*vals):
    """좌표에 대한 결정적 잡음 [-1, 1]."""
    h = 2166136261
    for v in vals:
        h ^= int(round(v * 4)) & 0xffffffff
        h = (h * 16777619) & 0xffffffff
        h ^= h >> 13
        h = (h * 0x5bd1e995) & 0xffffffff
        h ^= h >> 15
    return (h & 0xffff) / 32767.5 - 1.0


def ell(x, y, cx, cy, rx, ry):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2


def skin(f, x, y, z, salt=0):
    return mul(BASE, f * (1 + 0.025 * hnoise(x, y, z, salt)))


def vgrad(y, lo, hi, a=0.86, b=1.04):
    return a + (b - a) * clamp01((y - lo) / (hi - lo))


# 얼굴(머리 앞면) 배치, 목 관절 기준 q
EYE_X, EYE_Y, EYE_RX, EYE_RY = 6.5, 18.0, 4.5, 5.0     # 중심을 텍셀 모서리에 맞춰 좌우 대칭
PUPIL_R = 1.0
MOUTH_HW, MOUTH_Y, GRIN = 9.5, 4.8, 1.7


def mouth_line(x):
    return MOUTH_Y + GRIN * (x / MOUTH_HW) ** 2


def paint_face(x, y, z, f):
    """머리 앞면 (얼굴). x 는 보는 사람의 오른쪽(= 아오오니의 왼쪽)이 +."""
    ax = abs(x)
    f *= 1 - 0.12 * (x / 15) ** 2
    if y < 9:                                            # 턱 쪽 모서리 그늘
        f *= 1 - 0.12 * clamp01((ax - 5) / 7) * clamp01((9 - y) / 12)
    col = skin(f, x, y, z, 1)
    e = ell(ax, y, EYE_X, EYE_Y + 0.8, EYE_RX + 2.2, EYE_RY + 2.2)
    if e < 1:                                            # 눈두덩 그늘, 위쪽(이마뼈 밑)을 더 짙게
        col = mul(col, 1 - (0.16 + 0.14 * clamp01((y - EYE_Y) / EYE_RY)) * (1 - e))
    if EYE_Y + EYE_RY + 0.6 < y < EYE_Y + EYE_RY + 2.2 and ax < EYE_X + EYE_RX + 0.5:
        col = mul(col, 1.06)                             # 이마뼈 윗선
    if y > 24:                                           # 이마 가운데 살짝 밝게
        col = mul(col, 1 + 0.05 * clamp01(1 - ax / 9))
    e = ell(ax, y, EYE_X + 0.3, EYE_Y - EYE_RY - 1.2, 3.6, 1.1)
    if e < 1:
        col = mul(col, 0.9)                              # 눈 밑 그늘
    e = ell(ax, y, 9.8, 10.2, 3.0, 2.4)
    if e < 1:
        col = mul(col, 1 + 0.06 * (1 - e))               # 광대
    if ax < 1.4 and 10.6 < y < 15.5:                     # 콧등
        col = mul(col, 1.07)
    if 9.3 < y < 10.0 and ax < 2.4:                      # 코 밑 그늘
        col = mul(col, 0.80)
    if ell(ax, y, 1.4, 10.5, 0.75, 0.55) < 1:            # 콧구멍
        col = DARK_LINE
    yc = mouth_line(MOUTH_HW) + 0.3
    if yc < y < 10.3:                                    # 팔자 주름 (코 옆 → 입꼬리)
        xf = 2.8 + (MOUTH_HW + 1.0 - 2.8) * ((10.3 - y) / (10.3 - yc)) ** 0.7
        if abs(ax - xf) < 0.4:
            col = mul(col, 0.80)
        elif 0.4 <= ax - xf < 1.4:
            col = mul(col, 1.05)
    lip_top = mouth_line(min(ax, MOUTH_HW)) + 0.4 + 2.3 * math.sqrt(max(0.0, 1 - (x / (MOUTH_HW + 0.4)) ** 2))
    if ax < 0.6 and lip_top < y < 9.3:
        col = mul(col, 0.90)                             # 인중
    # 입술: 다문 입, 두툼한 보라색 입술, 입꼬리가 올라간 능글맞은 웃음
    if ax <= MOUTH_HW + 0.4:
        ym = mouth_line(min(ax, MOUTH_HW))
        k = math.sqrt(max(0.0, 1 - (x / (MOUTH_HW + 0.4)) ** 2))
        tu = 0.4 + 2.3 * k - 0.35 * math.exp(-(x / 0.9) ** 2)    # 윗입술 (가운데 살짝 패임)
        tl = 0.4 + 2.7 * k                                       # 아랫입술
        if ym - tl - 1.3 < y < ym - tl and ax < 7.5:
            col = mul(col, 0.84)                         # 아랫입술 밑 그늘
        if ym <= y <= ym + tu:
            col = mix(mul(LIP_UP, 0.85), mul(LIP_UP, 1.15), (y - ym) / max(tu, 0.1))
        elif ym - tl <= y < ym:
            c = (y - (ym - tl)) / max(tl, 0.1)           # 0 = 아랫입술 아래끝, 1 = 입선
            col = mix(LIP_LO, LIP_HI, clamp01(1 - abs(c - 0.55) * 2.6) * clamp01(1.3 - ax / 7))
        if abs(y - ym) < 0.36 and ax < MOUTH_HW + 0.2:
            col = MOUTH
    if ell(ax, y, MOUTH_HW + 0.6, mouth_line(MOUTH_HW) + 0.4, 0.55, 0.6) < 1:
        col = mul(BASE, 0.58)                            # 입꼬리
    # 눈: 큰 흰자 + 테두리 + 작은 검은 눈동자
    e = ell(ax, y, EYE_X, EYE_Y, EYE_RX, EYE_RY)
    if e < 1:
        if e > 0.70:
            col = EYE_RIM
        else:
            col = SCLERA_SH if y > EYE_Y + EYE_RY * 0.58 else SCLERA
            if ell(ax, y, EYE_X, EYE_Y, PUPIL_R, PUPIL_R) < 1:
                col = PUPIL
    return col


def paint_head(d, x, y, z, el):
    f = DIRF[d] * vgrad(y, CHIN_Y, 34, 0.84, 1.05)
    if d == "front":
        return paint_face(x, y, z, f)
    if d in ("left", "right"):
        f *= 1 - 0.10 * ((z - 1) / 13) ** 2
        if el.startswith("jaw"):
            f *= 0.86                                    # 비스듬히 아래를 보는 턱 면
        col = skin(f, x, y, z, 2)
        e = ell(z, y, 0.6, 15.2, 2.3, 4.1)               # 귀 (옆면 무늬)
        if e < 1:
            col = mul(col, 0.80 if e > 0.86 else 1.05 if e > 0.5 else 0.80)
            if ell(z, y, 1.0, 14.4, 0.8, 1.4) < 1:
                col = mul(col, 0.75)
        return col
    if d == "up":
        f = DIRF[d] * (1.06 - 0.10 * ((x / 15) ** 2 + ((z - 1) / 13) ** 2))
        return skin(f, x, y, z, 3)
    if d == "down":
        return skin(DIRF[d] * (0.95 + 0.05 * clamp01((z + 12) / 26)), x, y, z, 4)
    f *= 1 - 0.08 * (x / 15) ** 2
    return skin(f, x, y, z, 5)


def paint_torso(d, x, y, z, el):
    f = DIRF[d] * vgrad(y, -2, 20, 0.84, 1.04)
    if d == "front":
        f *= 1 - 0.10 * (x / 9) ** 2
        col = skin(f, x, y, z, 11)
        ax = abs(x)
        if 1.0 < ax < 8.4 and abs(y - (12.4 + 1.3 * ((ax - 4.6) / 3.8) ** 2)) < 0.55:
            col = mul(col, 0.84)                         # 가슴 아래 선
        if ax < 0.5 and 12 < y < 19:
            col = mul(col, 0.90)                         # 명치
        if 2.5 < ax < 7.5 and 18.2 < y < 18.9:
            col = mul(col, 1.08)                         # 쇄골
        if ax < 0.5 and 1.0 < y < 10.5:
            col = mul(col, 0.92)                         # 배 가운데 선
        if ax < 3.2 and (abs(y - 7.6) < 0.4 or abs(y - 9.6) < 0.4):
            col = mul(col, 0.93)
        if ell(x, y, 0, 4.0, 0.75, 0.75) < 1:
            col = DARK_LINE                              # 배꼽
        if y < 0:
            col = mul(col, 0.9)
        return col
    if d == "back":
        col = skin(f, x, y, z, 12)
        if abs(x) < 0.6 and y > 0:
            col = mul(col, 0.86)                         # 척추
        for bx in (-4.6, 4.6):
            e = ell(x, y, bx, 15.2, 3.0, 3.4)
            if 0.7 < e < 1:
                col = mul(col, 0.90)                     # 날개뼈
        return col
    if d in ("left", "right"):
        return skin(f * (1 - 0.08 * (z / 5) ** 2), x, y, z, 13)
    if d == "up":
        return skin(DIRF[d], x, y, z, 14)
    return skin(DIRF[d] * 0.92, x, y, z, 15)


def paint_arm(d, x, y, z, el):
    f = DIRF[d] * vgrad(y, -28, 2, 0.84, 1.03)
    col = skin(f, x, y, z, 21)
    if y < -24 and d != "up":                            # 손
        if d == "down":
            return mul(col, 0.9)
        if d in ("front", "back") and y < -25.6 and any(abs(x - fx) < 0.45 for fx in (-1.5, 0, 1.5)):
            col = mul(col, 0.72)                         # 손가락 사이
        if y > -24.6:
            col = mul(col, 0.9)                          # 손목
        return col
    if d == "back" and abs(y + 12) < 0.6 and abs(x) < 1.6:
        col = mul(col, 0.86)                             # 팔꿈치
    if d == "front" and abs(y + 12.5) < 0.5 and abs(x) < 1.2:
        col = mul(col, 0.9)
    return col


def paint_leg(d, x, y, z, el):
    f = DIRF[d] * vgrad(y, -23, 1, 0.82, 1.02)
    col = skin(f, x, y, z, 31)
    if y > -1.5 and d in ("front", "back", "left", "right"):
        col = mul(col, 0.88)                             # 사타구니 그늘
    if d == "front" and -20 <= y:
        e = ell(x, y, 0, -11.2, 2.2, 1.7)                # 무릎
        if e < 1:
            col = mul(col, 1.08 if y > -11.6 else 0.92)
    if y < -20:                                          # 발
        if d == "down":
            return mul(col, 0.85)
        if d == "front" and any(abs(x - tx) < 0.4 for tx in (-1.5, 0, 1.5)):
            col = mul(col, 0.72)                         # 발가락
    if d == "up" and y <= -20 and z > 3 and any(abs(x - tx) < 0.4 for tx in (-1.5, 0, 1.5)):
        col = mul(col, 0.80)
    return col


PAINTERS = {"head": paint_head, "torso": paint_torso, "arm_l": paint_arm, "arm_r": paint_arm,
            "leg_l": paint_leg, "leg_r": paint_leg}


# ------------------------------------------------------------------ 이미지 / PNG (의존성 없음)
class Img:
    def __init__(self, w, h, fill=(0, 0, 0, 0)):
        self.w, self.h = w, h
        self.px = [list(fill) for _ in range(w * h)]

    def get(self, x, y):
        return self.px[y * self.w + x]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = [c[0], c[1], c[2], c[3] if len(c) > 3 else 255]

    def png(self):
        rows = []
        for y in range(self.h):
            row = bytearray(b"\x00")
            for x in range(self.w):
                row.extend(bytes(self.px[y * self.w + x]))
            rows.append(bytes(row))

        def chunk(t, data):
            return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xffffffff)

        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a png"
    return struct.unpack(">II", data[16:24])


# ------------------------------------------------------------------ 아틀라스 굽기
def skyline_pack(sizes, W, H):
    """스카이라인(아래-왼쪽) 포장. sizes: [(w,h)] → [(x,y)]."""
    sky = [[0, 0, W]]
    pos = [None] * len(sizes)
    for i in sorted(range(len(sizes)), key=lambda k: (-sizes[k][1], -sizes[k][0], k)):
        w, h = sizes[i]
        best = None
        for si in range(len(sky)):
            x = sky[si][0]
            if x + w > W:
                break
            y, left, j = 0, w, si
            while left > 0:
                y = max(y, sky[j][1])
                left -= sky[j][2]
                j += 1
            if y + h <= H and (best is None or (y + h, x) < (best[0] + h, best[1])):
                best = (y, x)
        if best is None:
            raise SystemExit("텍스처 아틀라스 공간 부족")
        y, x = best
        pos[i] = (x, y)
        new = []
        for sx, sy, sw in sky:
            if sx + sw <= x or sx >= x + w:
                new.append([sx, sy, sw])
                continue
            if sx < x:
                new.append([sx, sy, x - sx])
            if sx + sw > x + w:
                new.append([x + w, sy, sx + sw - x - w])
        new.append([x, y + h, w])
        new.sort()
        sky = []
        for seg in new:
            if sky and sky[-1][1] == seg[1] and sky[-1][0] + sky[-1][2] == seg[0]:
                sky[-1][2] += seg[2]
            else:
                sky.append(seg)
    return pos


def build_oni():
    """부위별 모델 JSON 과 텍스처를 만든다. 오른팔·오른다리는 왼쪽 것을 좌우 뒤집어(UV u1>u2) 같이 쓴다."""
    faces = []   # (part, elem_index, face_name, local_dir, w, h)
    for part in PART_ORDER:
        if PARTS[part].get("mirror"):
            continue
        k = PARTS[part]["density"]
        for ei, el in enumerate(PARTS[part]["elements"]):
            frm, to = element_box(el["lo"], el["hi"])
            for d, fname in DIR_TO_FACE.items():
                if d in el["skip"]:
                    continue
                w, h = face_size(frm, to, fname)
                faces.append((part, ei, fname, d, max(1, round(w * k)), max(1, round(h * k))))
    # 사방 1텍셀 여백(가장자리 색으로 채움) → 밉맵에서 옆 면 색이 번지지 않게
    place = [(x + 1, y + 1) for x, y in skyline_pack([(f[4] + 2, f[5] + 2) for f in faces], ATLAS, ATLAS)]
    img = Img(ATLAS, ATLAS, (0, 0, 0, 255))
    models = {part: {"textures": {"oni": f"{NS}:item/oni", "particle": f"{NS}:item/oni"}, "elements": []}
              for part in PART_ORDER}
    elems = {}
    for part in PART_ORDER:
        for ei, el in enumerate(PARTS[part]["elements"]):
            frm, to = element_box(el["lo"], el["hi"])
            e = {"name": el["name"], "from": [round(v, 4) for v in frm], "to": [round(v, 4) for v in to]}
            rot = model_rotation(el)
            if rot:
                e["rotation"] = rot
            e["faces"] = {}
            models[part]["elements"].append(e)
            elems[(part, ei)] = (e, frm, to, rot)
    for i, (part, ei, fname, d, w, h) in enumerate(faces):
        e, frm, to, rot = elems[(part, ei)]
        rx, ry = place[i]
        paint = PAINTERS[part]
        for ty in range(-1, h + 1):
            for tx in range(-1, w + 1):
                s = (min(max(tx, 0), w - 1) + 0.5) / w
                t = (min(max(ty, 0), h - 1) + 0.5) / h
                lx, ly, lz = to_local(rotate_model_point(face_point(frm, to, fname, s, t), rot))
                img.put(rx + tx, ry + ty, paint(d, lx, ly, lz, e["name"]))
        e["faces"][fname] = {"uv": [rx * UV_PER_TEXEL, ry * UV_PER_TEXEL, (rx + w) * UV_PER_TEXEL, (ry + h) * UV_PER_TEXEL],
                             "texture": "#oni"}
    for part in PART_ORDER:
        src = PARTS[part].get("mirror")
        if not src:
            continue
        assert PARTS[part]["elements"] is PARTS[src]["elements"]
        for ei, el in enumerate(PARTS[part]["elements"]):
            assert el["lo"][0] == -el["hi"][0] and not el["rot"], "좌우 대칭 요소만 공유할 수 있다"
            e, se = elems[(part, ei)][0], elems[(src, ei)][0]
            for d, fname in DIR_TO_FACE.items():
                if d in el["skip"]:
                    continue
                u1, v1, u2, v2 = se["faces"][MIRROR_FACE.get(fname, fname)]["uv"]
                e["faces"][fname] = {"uv": [u2, v1, u1, v2], "texture": "#oni"}
    for part in PART_ORDER:   # 면 순서를 일정하게
        for e in models[part]["elements"]:
            e["faces"] = {k: e["faces"][k] for k in ("north", "east", "south", "west", "up", "down") if k in e["faces"]}
    return models, img


# ------------------------------------------------------------------ 마검 (32x32)
def build_sword():
    """손잡이(왼쪽 아래) → 칼끝(오른쪽 위) 대각선. t = 칼 방향, s = 옆 방향 (픽셀 대각선 단위)."""
    S, X0, Y0, TIP = 32, 3, 28, 53
    GOLD, GOLD_HI, GOLD_LO = (190, 132, 46), (250, 210, 104), (112, 66, 22)
    GEM, GEM_HI, SLIT = (230, 22, 44), (255, 150, 160), (24, 0, 4)
    img = Img(S, S)
    shape = {}
    for y in range(S):
        for x in range(S):
            dx, dy = x - X0, y - Y0
            t, s = dx - dy, dx + dy
            c = s + 0.5                                   # 칼 중심선에서의 거리 (+ = 오른쪽 아래)
            col = None
            if 0 <= t <= 3 and abs(c) + abs(t - 1.5) <= 3.6:                  # 폼멜
                col = GOLD_HI if c < -0.6 else GOLD if c < 1.6 else GOLD_LO
                if abs(c) <= 0.5 and 1 <= t <= 2:
                    col = GEM
            elif 4 <= t <= 15 and abs(c) <= 1.5:                              # 감은 손잡이
                band = ((t + (s & 1)) // 2) % 2
                col = (78, 26, 96) if band else (32, 8, 40)
                if band and c < 0:
                    col = (118, 48, 140)
            elif 16 <= t <= 18 and abs(c) <= 11.5:                            # 날밑
                col = GOLD_HI if t == 18 else GOLD if t == 17 else GOLD_LO
                if abs(c) >= 9.5:
                    col = GOLD
            elif 19 <= t <= 22 and 8.5 <= abs(c) <= 11.5 and abs(c) >= 8.5 + (t - 19):
                col = GOLD_HI if t >= 21 else GOLD                            # 날밑 뿔 (칼끝 쪽으로 휨)
            if 15 <= t <= 19 and abs(c) <= 2.5:                               # 날밑의 붉은 눈
                col = SLIT if abs(c) <= 0.5 else GEM_HI if (c < -1 and t >= 18) else GEM
            if col is None and 19 <= t <= TIP:                                # 칼날
                h = min(4.0, (TIP - t) / 1.6 + 0.5)
                if 21 <= t <= 30 and c > 0 and (t % 3) == 0:
                    h += 1.0                                                  # 한쪽 날의 톱니
                if abs(c) <= h:
                    edge = h - abs(c)
                    if edge < 1.0:
                        col = (255, 52, 70) if t < TIP - 8 else (255, 132, 150)   # 붉게 빛나는 날
                    elif edge < 2.0:
                        col = (128, 10, 34)
                    else:
                        col = mix((36, 3, 12), (70, 6, 24), (t - 19) / 30)
                    if abs(c) <= 1.0 and h >= 3.5:
                        col = (16, 1, 6)                                       # 홈
                        if 23 <= t <= TIP - 9 and (t % 5) in (0, 1):
                            col = (255, 64, 168) if t % 5 == 0 else (196, 30, 120)   # 룬
            if col is not None:
                shape[(x, y)] = col
    for (x, y), c in shape.items():
        img.put(x, y, c)
    for (x, y) in list(shape):
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + ddx, y + ddy
            if 0 <= nx < S and 0 <= ny < S and (nx, ny) not in shape and img.get(nx, ny)[3] == 0:
                img.put(nx, ny, (14, 2, 8, 255))
    return img


# ------------------------------------------------------------------ pack.png (머리 정면 초상)
def head_front_contains(x, y):
    """정면에서 본 머리 실루엣 안인지 (q, 목 관절 기준). 회전한 쐐기도 계산."""
    for el in HEAD_ELEMENTS:
        px, py = x, y
        if el["rot"]:
            (cx, cy), ang = el["rot"]
            a = math.radians(-ang)
            c, s = math.cos(a), math.sin(a)
            px, py = cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c
        if el["lo"][0] <= px <= el["hi"][0] and el["lo"][1] <= py <= el["hi"][1]:
            return True
    return False


def build_icon():
    S, SS = 128, 3
    img = Img(S, S)
    scale = 3.15         # 픽셀/q
    ox, oy = S / 2, S / 2 + 3
    for py in range(S):
        for px in range(S):
            acc = [0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    fx = px + (sx + 0.5) / SS
                    fy = py + (sy + 0.5) / SS
                    x = (fx - ox) / scale
                    y = 15.5 - (fy - oy) / scale
                    if head_front_contains(x, y):
                        c = paint_face(x, y, 14, DIRF["front"] * vgrad(y, CHIN_Y, 34, 0.84, 1.05))
                    else:
                        r = math.hypot(fx - S / 2, fy - S / 2) / (S * 0.72)
                        c = mix((52, 14, 32), (6, 4, 10), r)
                    for i in range(3):
                        acc[i] += c[i]
            img.put(px, py, tuple(int(round(v / (SS * SS))) for v in acc))
    return img


# ------------------------------------------------------------------ 매니페스트
def blocks(v):
    return round(v / Q, 6)


def manifest():
    parts = {}
    for part in PART_ORDER:
        p = PARTS[part]
        lo = [min(min(e["lo"][i], e["hi"][i]) for e in p["elements"]) for i in range(3)]
        hi = [max(max(e["lo"][i], e["hi"][i]) for e in p["elements"]) for i in range(3)]
        if part == "head":
            lo[0], hi[0] = -15, 15
        parts[part] = {
            "item_model": f"{NS}:oni_{part}",
            "joint": [blocks(v) for v in p["joint"]],
            "parent": p["parent"],
            "max_swing_deg": p["swing"],
            "swing_range_deg": list(p["range"]),
            "extent_min": [blocks(v) for v in lo],
            "extent_max": [blocks(v) for v in hi],
            "desc": p["desc"],
        }
    for part in ("arm_l", "arm_r", "leg_l", "leg_r"):
        parts[part]["length"] = round(-parts[part]["extent_min"][1], 6)
    hj = PARTS["head"]["joint"][1]
    top = max(PARTS[p]["joint"][1] + max(e["hi"][1] for e in PARTS[p]["elements"]) for p in PART_ORDER)
    return {
        "_comment": "tools/build_rp.py 가 생성. 손으로 고치지 말 것.",
        "texture": f"{NS}:item/oni",
        "units": "blocks",
        "frame": ("entity-local frame of each item_display (spawned at the oni player's feet, rotated by its yaw). "
                  "+Y up, +Z = forward (the oni faces +Z; yaw 0 = south), +X = the oni's LEFT (yaw 0: east), -X = the oni's right. "
                  "Joint offsets are measured from the feet."),
        "joint_contract": ("In every part model the joint/pivot is model pixel (8,8,8). With item_display:\"none\" (the default) and an "
                           "identity transformation, model pixel (px,py,pz) appears at entity-local ((8-px)/16, (py-8)/16, (8-pz)/16) "
                           "blocks from the display entity. So summon/teleport every part to the oni's feet with yaw = player yaw, pitch 0, and set "
                           "transformation.translation = joint * s, scale = [s,s,s] (s = overall size, 1.0 normal), "
                           "left_rotation = swing quaternion, right_rotation = identity. left_rotation then pivots the part about its joint."),
        "swing": ("Rotation about the entity-local +X axis (right-hand rule; quaternion [sin(a/2),0,0,cos(a/2)] or {angle:a_rad,axis:[1f,0f,0f]}). "
                  "Positive angle moves the lower end of a hanging limb BACKWARD (-Z), tips the torso/head FORWARD (head looks down, "
                  "same sign as player pitch). Forward swing of an arm/leg = NEGATIVE angle. Rest pose (angle 0) = limbs straight down, "
                  "torso/head upright, face toward +Z. If the torso is rotated, move child joints (arms, head) with it: "
                  "child_translation = s * (torso_joint + R_torso * (child_joint - torso_joint)) and child_rotation = R_torso * R_child "
                  "(all rotations about X: child angle = torso angle + own angle)."),
        "total_height": round(top / Q, 6),
        "camera": {
            "standing_eye_y": EYE_STAND,
            "sneaking_eye_y": EYE_SNEAK,
            "inside_part": "head",
            "head_box_rel_neck": {"y": [blocks(CHIN_Y), blocks(34)], "x": [blocks(-15), blocks(15)], "z": [blocks(-12), blocks(14)]},
            "note": ("At scale 1 both eye heights (feet +1.62 standing, +1.27 sneaking) are inside the convex head, whose inner faces are "
                     "omitted and outer faces are back-face culled from inside, so the oni player never sees the head from inside, at any "
                     "look direction (checked by tools/rp_preview.py). This also holds for any head pitch within max_swing_deg. "
                     "The oni player does see its own torso/arms/feet when looking down (like a body). "
                     "If the whole model is scaled by s, also set the player's minecraft:scale attribute to s so the eye stays inside "
                     "(head spans feet + s*1.21875 .. s*2.375)."),
        },
        "parts": parts,
        "walk_cycle_hint": {"arm_deg": 35, "leg_deg": 30, "phase": "arm_l swings with leg_r, arm_r with leg_l (arm and leg on the same side opposite)",
                            "head": "angle = clamp(player pitch, -30, 30)",
                            "attack": ("arm_r: raise to -90 (straight forward) then swing back to about +20 within 4-6 ticks. "
                                       "Beyond -90 the hand crosses the face/jaw (the head is wider than the shoulders).")},
        "summon_example": ('summon minecraft:item_display ~ ~ ~ {item:{id:"minecraft:paper",count:1,components:{"minecraft:item_model":"aooni:oni_head"}},'
                           'item_display:"none",transformation:{translation:[0f,%sf,0f],left_rotation:[0f,0f,0f,1f],scale:[1f,1f,1f],'
                           'right_rotation:[0f,0f,0f,1f]},teleport_duration:1,interpolation_duration:2}' % blocks(hj)),
        "magum": {"item_model": f"{NS}:magum", "parent": "minecraft:item/handheld", "texture": f"{NS}:item/magum",
                  "usage": 'e.g. minecraft:netherite_sword[minecraft:item_model="aooni:magum"]'},
        "pack_format": {"min_format": RP_MIN, "max_format": RP_MAX, "pack_format": RP_MIN, "supported_formats": [RP_MIN, RP_MAX],
                        "versions": {v: (f"{a}.{b}" if b else str(a)) for v, a, b in RP_FORMATS}},
        "notes": NOTES,
    }


NOTES = [
    "Pack formats: misode/mcmeta summary/versions/data.json resource_pack_version(.minor): 1.21.5=55, 1.21.6=63, 1.21.7/8=64, "
    "1.21.9/10=69, 1.21.11=75, 26.1-26.1.2=84, 26.2=88, 26.3=97.1 (also 26.3 client version.json pack_version resource_major=97, resource_minor=1).",
    "pack.mcmeta: 1.21.9+ parser = PackFormat$IntermediaryFormat.validate(lastPreMinor=64 for CLIENT_RESOURCES (PackFormat.lastPreMinorVersion: bipush 64), "
    "requireFormat=true, overlay=false). min_format present -> validateNewFormat: min.major(55) <= 64 so supported_formats is required with "
    "min == min_format.major and max == max_format.major (or == 64), and pack_format must lie in [55, 97]. min_format int -> [55,0] (BOTTOM_CODEC), "
    "max_format int -> [97, 2147483647] (TOP_CODEC) so 97.1 is accepted. Older parsers (1.21.5-1.21.8) read pack_format + supported_formats [55,97] "
    "and ignore min/max_format. Same logic and constants in 1.21.11 (azz$a.validate, azz.a(PackType) bipush 64/81) and 26.3.",
    "item_display 180 deg: DisplayRenderer$ItemDisplayRenderer.submitInner (26.3) = `aload_2; getstatic Axis.YP; ldc 3.1415927f; "
    "invokevirtual PoseStack.rotate(Axis,F)` then ItemStackRenderState.submit. 1.21.11 (hwe$b.a(ied,fzm,hpo,int,float)): "
    "`getstatic a.d (Axis.YP); ldc 3.1415927f; invokeinterface a.rotation(F); invokevirtual fzm.a(Quaternionfc) (PoseStack.mulPose)`. "
    "1.21.5 (gxj$b.renderInner): identical `getstatic a.d; ldc 3.1415927f; a.rotation; fld.a(Quaternionfc)`.",
    "Order in DisplayRenderer.submit/render: poseStack.rotate(calculateOrientation) [FIXED billboard: Quaternionf.rotationYXZ(-0.017453292f*yRot, "
    "0.017453292f*xRot, 0)] -> poseStack.mulPose(transformation) -> submitInner (Y 180) -> item layer transform. So the transformation acts in "
    "entity-local space where +Z = the entity's facing direction (yaw 0 = south, yaw 90 = west) and +X = its left.",
    "ItemDisplayContext NONE: ItemTransforms.getTransform(context) is a tableswitch over the named contexts (9 in 26.3/1.21.11, 8 in 1.21.5); NONE falls to "
    "`default: getstatic ItemTransform.NO_TRANSFORM`. ItemTransform.apply(boolean, PoseStack$Pose): `if (this == NO_TRANSFORM) { pose.translate(-0.5f,-0.5f,-0.5f); return; }` "
    "(otherwise translate/rotate/scale then the same -0.5 translate). Called from ItemStackRenderState$LayerRenderState.applyTransform (26.3) / render (1.21.x). "
    "No default display transform applies for 'none' (model 'display' blocks have no 'none' entry).",
    "FaceBakery.bakeVertex: position = FaceInfo$VertexInfo.select(from,to) / 16.0f (after element rotation about origin*0.0625), "
    "so model pixel p -> p/16 - 0.5 -> RotY(pi) -> (-(p.x/16-0.5), p.y/16-0.5, -(p.z/16-0.5)). Hence the face texture is on the model's north (-Z) face, "
    "which ends up facing entity +Z, and the oni's left (+X) is model -X (west).",
    "Element rotation: 26.3 CuboidRotation$SingleAxisRotation.transformation = Matrix4f.rotation(angle*0.017453292f, axis.getPositive().getUnitVec3f()); "
    "1.21.5 FaceBakery.applyElementRotation = Quaternionf.rotationAxis(angle*0.017453292f, +axis). 1.21.5 BlockElement$Deserializer.getAngle only accepts "
    "0/±22.5/±45, so the jaw wedges use ±22.5 about z (rescale false). A local rotation by a about entity +Z is model angle -a.",
    "26.3 CuboidItemModelWrapper$Unbaked has an optional 'transformation' field (identity by default) -> LayerRenderState.setLocalTransform; "
    "not used here (keeps 1.21.5 compatibility).",
    "Element coordinates must be within [-16, 32] (CuboidModelElement$Deserializer.getPosition: float -16.0f / 32.0f checks); "
    "every part fits, i.e. a part may reach at most 1.5 blocks from its joint. Flipped UVs (u1>u2, used to share the left limb texture "
    "with the right limb) are fine: FaceBakery.computeMaterialTransparency uses Math.min/max of the UVs.",
    "Culling: item pipelines (26.3 RenderPipelines.ITEM_CUTOUT/ITEM_TRANSLUCENT never call withCull(false); 1.21.x itemEntityTranslucentCull) keep back-face culling, "
    "so the inside of the head is invisible. Inner head faces that would point at the camera are omitted from the model.",
    "Texture atlas: item models resolve aooni:item/* from the item atlas (1.21.11+ atlases/items.json directory source 'item' over all namespaces; "
    "1.21.5 block atlas also includes 'item/').",
    "Display entities default to item_display:\"none\". Players without this resource pack see the magenta/black missing-model cube "
    "for aooni:* item models; use server.properties require-resource-pack=true or keep a block_display fallback.",
]


# ------------------------------------------------------------------ 검사
def check_pack_meta(meta):
    """옛 파서(1.21.5~1.21.8)와 새 파서(1.21.9+)를 흉내 내 모든 대상 버전에서 받아들여지는지 본다."""
    p = meta["pack"]
    errs = []
    fmt, sup = p["pack_format"], p["supported_formats"]
    lo, hi = (sup, sup) if isinstance(sup, int) else (sup[0], sup[1])
    mn = p["min_format"] if isinstance(p["min_format"], list) else [p["min_format"], 0]
    mx = p["max_format"] if isinstance(p["max_format"], list) else [p["max_format"], 2**31 - 1]
    if not lo <= fmt <= hi:
        errs.append("pack_format 이 supported_formats 밖")
    if tuple(mn) > tuple(mx):
        errs.append("min_format > max_format")
    if mn[0] <= LAST_PRE_MINOR_RP:
        if lo != mn[0] or (hi != mx[0] and hi != LAST_PRE_MINOR_RP):
            errs.append("1.21.9+: supported_formats 가 min/max_format 과 맞지 않음")
        if not mn[0] <= fmt <= mx[0] or fmt < 15:
            errs.append("1.21.9+: pack_format 이 min~max 밖")
    for ver, major, minor in RP_FORMATS:
        if major <= LAST_PRE_MINOR_RP:
            ok = lo <= major <= hi
        else:
            ok = tuple(mn) <= (major, minor) <= tuple(mx)
        if not ok:
            errs.append(f"{ver} ({major}.{minor}) 에서 호환되지 않음")
    return errs


def validate_zip(path):
    errs = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        for n in ("pack.mcmeta", "pack.png"):
            if n not in names:
                errs.append(f"zip 루트에 {n} 없음")
        js = {}
        for n in sorted(names):
            if n.endswith(".json") or n.endswith(".mcmeta"):
                try:
                    js[n] = json.loads(z.read(n).decode("utf-8"))
                except Exception as ex:   # noqa: BLE001
                    errs.append(f"{n}: JSON 오류 {ex}")
        if "pack.mcmeta" in js:
            errs += check_pack_meta(js["pack.mcmeta"])

        def model_path(ref):
            ns, _, p = ref.partition(":") if ":" in ref else ("minecraft", "", ref)
            return ns, f"assets/{ns}/models/{p}.json"

        for n, data in js.items():
            if "/items/" in n:
                ref = data["model"]["model"]
                ns, mp = model_path(ref)
                if ns != "minecraft" and mp not in names:
                    errs.append(f"{n}: 모델 {ref} 없음")
            if "/models/" in n:
                tex = data.get("textures", {})
                for ref in tex.values():
                    if ref.startswith("#"):
                        continue
                    ns, _, p = ref.partition(":")
                    if ns != "minecraft" and f"assets/{ns}/textures/{p}.png" not in names:
                        errs.append(f"{n}: 텍스처 {ref} 없음")
                if "parent" in data:
                    ns, mp = model_path(data["parent"])
                    if ns != "minecraft" and mp not in names:
                        errs.append(f"{n}: 부모 {data['parent']} 없음")
                for e in data.get("elements", []):
                    for i in range(3):
                        for v in (e["from"][i], e["to"][i]):
                            if not -16 <= v <= 32:
                                errs.append(f"{n}: {e.get('name')} 좌표 {v} 가 -16..32 밖")
                        if e["from"][i] > e["to"][i]:
                            errs.append(f"{n}: {e.get('name')} from > to")
                    r = e.get("rotation")
                    if r and (r["angle"] not in (-45, -22.5, 0, 22.5, 45) or r["axis"] not in ("x", "y", "z")
                              or any(not -16 <= v <= 32 for v in r["origin"])):
                        errs.append(f"{n}: {e.get('name')} 회전 {r} 는 1.21.5 에서 허용되지 않음")
                    for fn_, f in e["faces"].items():
                        if not f["texture"].startswith("#") or f["texture"][1:] not in tex:
                            errs.append(f"{n}: {e.get('name')}.{fn_} 텍스처 변수 {f['texture']} 미정의")
                        if any(not 0 <= u <= 16 for u in f["uv"]):
                            errs.append(f"{n}: {e.get('name')}.{fn_} uv 범위 밖")
        for n in names:
            if n.endswith(".png"):
                w, h = png_size(z.read(n))
                if w != h or w & (w - 1):
                    errs.append(f"{n}: {w}x{h} (정사각 2의 거듭제곱이 아님)")
    return errs


def check_head_camera():
    """눈(서기 1.62, 웅크리기 1.27)이 볼록한 머리 몸통(core) 안에 0.05 블록 이상 여유를 두고 있는지."""
    errs = []
    core = HEAD_ELEMENTS[0]
    hj = PARTS["head"]["joint"][1]
    m = 0.05 * Q
    for eye in (EYE_STAND, EYE_SNEAK):
        rel = eye * Q - hj
        if not (core["lo"][0] + m < 0 < core["hi"][0] - m and core["lo"][1] + m < rel < core["hi"][1] - m
                and core["lo"][2] + m < 0 < core["hi"][2] - m):
            errs.append(f"눈 높이 {eye} 가 머리 안(여유 0.05)에 있지 않음")
    return errs


# ------------------------------------------------------------------ 조립
def build_files():
    files = {}

    def jdump(obj, indent=None):
        return (json.dumps(obj, ensure_ascii=False, indent=indent) + "\n").encode("utf-8")

    meta = {"pack": {"description": DESCRIPTION, "pack_format": RP_MIN, "supported_formats": [RP_MIN, RP_MAX],
                     "min_format": RP_MIN, "max_format": RP_MAX}}
    files["pack.mcmeta"] = jdump(meta, 2)
    files["pack.png"] = build_icon().png()
    models, atlas = build_oni()
    files[f"assets/{NS}/textures/item/oni.png"] = atlas.png()
    for part, model in models.items():
        files[f"assets/{NS}/models/item/oni_{part}.json"] = jdump(model)
        files[f"assets/{NS}/items/oni_{part}.json"] = jdump({"model": {"type": "minecraft:model", "model": f"{NS}:item/oni_{part}"}}, 2)
    files[f"assets/{NS}/textures/item/magum.png"] = build_sword().png()
    files[f"assets/{NS}/models/item/magum.json"] = jdump({"parent": "minecraft:item/handheld", "textures": {"layer0": f"{NS}:item/magum"}}, 2)
    files[f"assets/{NS}/items/magum.json"] = jdump({"model": {"type": "minecraft:model", "model": f"{NS}:item/magum"}}, 2)
    return files


def write_zip(files):
    os.makedirs(DIST, exist_ok=True)
    with zipfile.ZipFile(OUT_ZIP, "w") as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])
    with open(OUT_ZIP, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def main():
    files = build_files()
    sha1 = write_zip(files)
    text = json.dumps(manifest(), ensure_ascii=False, indent=2)
    # 숫자만 든 짧은 배열은 한 줄로
    text = re.sub(r"\[\s*((?:-?[\d.]+|null)(?:,\s*(?:-?[\d.]+|null))*)\s*\]",
                  lambda m: "[" + ", ".join(v.strip() for v in m.group(1).split(",")) + "]", text)
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    errs = validate_zip(OUT_ZIP) + check_head_camera()
    print(f"{os.path.relpath(OUT_ZIP, ROOT)}  ({os.path.getsize(OUT_ZIP)} bytes, {len(files)} files)")
    print(f"resource-pack-sha1={sha1}")
    print(f"매니페스트: {os.path.relpath(MANIFEST, ROOT)}")
    if "--preview" in sys.argv:
        out = sys.argv[sys.argv.index("--preview") + 1]
        sys.path.insert(0, HERE)
        import rp_preview
        paths, fails = rp_preview.render_all(OUT_ZIP, MANIFEST, out)
        for p in paths:
            print("미리보기:", p)
        errs += fails
    if errs:
        print("검사 실패:")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print("검사 통과 (JSON, 텍스처 참조, 좌표·회전 범위, pack.mcmeta 1.21.5~26.3, 머리 안 카메라)")


if __name__ == "__main__":
    main()
