"""방어구 3세트(가죽 / 철 / 기사) × 투구·갑옷·각반을 코드로 모델링한다.

  python roblox_items/tools/build_armor.py --out roblox_items/armor            # 전체(베이크+내보내기+미리보기)
  python roblox_items/tools/build_armor.py --out /tmp/x --no-bake --sets knight  # 형태만 빠르게 미리보기

결과
  <out>/<세트>_<부위>.fbx              로블록스 3D Importer 로 가져올 파일(메시 이름 = 붙을 R15 부위, 텍스처 내장)
  <out>/textures/<세트>_<부위>_*       베이크된 PBR 텍스처(색·노멀 jpg / 거칠기·금속 png)
  <out>/fit_data.json                  부위 기준 오프셋·크기(→ Luau ArmorData 로 변환됨)
  <out>/previews/*.png                 마네킹 착용 렌더
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import armor_lib as L  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from armor_lib import M, TAU, mirror_x, rivets, shell, spline, tube  # noqa: E402
from mathutils import Vector  # noqa: E402

PI = math.pi
FRONT = -PI / 2
# 로프트 축(z_b)을 앞(-Y)으로 눕히는 회전: (x_b, y_b, z_b) → (x_b, -z_b, y_b)
TO_FRONT = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)
# 로프트 축을 바깥(-X, 오른쪽 다리 바깥)으로 눕히는 회전: (x_b, y_b, z_b) → (-z_b, -x_b, y_b)
TO_OUT = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], float)


# ───────────────────────────────────────────────────────────── 헬퍼 ──
def prof(ctrl, num):
    """(z, A, B[, n, cx, cy]) 제어점 → 각 열 배열."""
    P = spline(ctrl, num)
    return [P[:, i] for i in range(P.shape[1])]


def lshell(name, ctrl, num, mat, t=0.04, th=(0.0, TAU), M_=48, deform=None, xform=None,
           n=None, bev=0.012, caps=(False, False)):
    cols = prof(ctrl, num)
    z, A, B = cols[:3]
    nn = cols[3] if len(cols) > 3 else (n if n is not None else 4.0)
    cx = cols[4] if len(cols) > 4 else 0.0
    cy = cols[5] if len(cols) > 5 else 0.0
    return shell(name, z, A, B, t=t, mat=M(mat), n=nn, th=th, M=M_, cx=cx, cy=cy,
                 deform=deform, xform=xform, bev=bev, cap_bottom=caps[0], cap_top=caps[1])


def edge(ctrl_row, th, grow=0.0, n=4.0, deform=None, xform=None, M_=48, cx=0.0, cy=0.0):
    """단면 하나(z,A,B)의 가장자리 점들."""
    z, A, B = ctrl_row[:3]
    full = abs((th[1] - th[0]) - TAU) < 1e-6
    t = np.linspace(th[0], th[1], M_, endpoint=not full)
    x, y = L.sq_ring(A + grow, B + grow, n, t, cx, cy)
    p = np.stack([x, y, np.full_like(x, z)], 1)
    if deform is not None:
        p = deform(p, t)
    if xform is not None:
        p = L.apply_xform(p, xform)
    return p, full


def rim(name, ctrl_row, th, r, mat, grow=0.0, **kw):
    p, full = edge(ctrl_row, th, grow, **kw)
    return tube(name, p, r, closed=full, segs=8, mat=M(mat))


def studs(name, ctrl_row, th, count, r, mat, grow=0.0, n=4.0, deform=None, xform=None, cx=0.0, cy=0.0):
    z, A, B = ctrl_row[:3]
    full = abs((th[1] - th[0]) - TAU) < 1e-6
    t = np.linspace(th[0], th[1], count, endpoint=not full)
    x, y = L.sq_ring(A + grow, B + grow, n, t, cx, cy)
    p = np.stack([x, y, np.full_like(x, z)], 1)
    nr = np.stack([x - cx, y - cy, np.zeros_like(x)], 1)
    if deform is not None:
        p = deform(p, t)
    if xform is not None:
        p = L.apply_xform(p, xform)
        nr = L.apply_xform(nr, (xform[0] if isinstance(xform, tuple) else xform, (0, 0, 0)))
    return rivets(name, p, nr, r=r, mat=M(mat))


def meridian(ctrl, theta, grow, num=24, n=4.0, z0=None, z1=None):
    """돔 표면을 따라 위로 올라가는 선(세로 띠·볏)."""
    cols = prof(ctrl, num)
    z, A, B = cols[:3]
    nn = cols[3] if len(cols) > 3 else np.full_like(z, n)
    pts = []
    for i in range(num):
        if (z0 is not None and z[i] < z0) or (z1 is not None and z[i] > z1):
            continue
        x, y = L.sq_ring(A[i] + grow, B[i] + grow, nn[i], np.array([theta]))
        pts.append((x[0], y[0], z[i]))
    return np.asarray(pts)


def front_mask(p, B=0.6):
    return np.clip(-p[:, 1] / B, 0, 1)


# ─────────────────────────────────────────────────────── 갑옷 (상체) ──
CUIRASS = [  # z, A, B, n
    (-0.90, 1.06, 0.60, 6), (-0.50, 1.05, 0.60, 6), (0.00, 1.08, 0.63, 6), (0.40, 1.10, 0.65, 6),
    (0.68, 1.09, 0.64, 6), (0.81, 1.04, 0.63, 5), (0.89, 0.92, 0.63, 4), (0.94, 0.77, 0.65, 3),
]


def chest_deform(bulge, ridge):
    def f(p, th):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        fm = np.clip(-y / 0.6, 0, 1)
        g = np.exp(-((z - 0.25) / 0.45) ** 2)
        y2 = y - bulge * fm ** 2 * g - ridge * np.exp(-(x / 0.12) ** 2) * fm * np.exp(-((z - 0.05) / 0.7) ** 2)
        return np.stack([x, y2, z], 1)
    return f


def build_chest(style):
    up, low, ra, la = [], [], [], []
    if style == "leather":
        dfm = chest_deform(0.03, 0.0)
        up.append(lshell("cuirass", CUIRASS, 22, "leather", t=0.05, deform=dfm, M_=56))
        up.append(rim("collar", CUIRASS[-1], (0, TAU), 0.035, "leather_dark", grow=0.03, n=3, deform=dfm))
        up.append(rim("hem", CUIRASS[0], (0, TAU), 0.03, "leather_dark", grow=0.035, n=6, deform=dfm))
        # 앞판 징(다이아 배열)
        pts, nrm = [], []
        for row, z in enumerate(np.linspace(-0.65, 0.55, 6)):
            for k in range(5 - (row % 2)):
                x = (k - (4 - (row % 2)) / 2) * 0.32
                y = -0.62 - 0.03 * math.exp(-((z - 0.25) / 0.45) ** 2) - 0.05
                pts.append((x, y, z))
                nrm.append((0, -1, 0))
        up.append(rivets("studs", pts, nrm, r=0.035, mat=M("bronze")))
        # 옆구리 끈
        for sx in (-1, 1):
            for z in (-0.45, 0.0, 0.45):
                p = np.array([(sx * 1.13, -0.18, z), (sx * 1.15, 0.0, z + 0.04), (sx * 1.13, 0.18, z)])
                up.append(tube("lace", p, 0.02, closed=False, mat=M("leather_dark")))
        # 허리띠 + 가죽 술(pteruges)
        low.append(lshell("belt", [(-0.08, 1.10, 0.64, 6), (0.14, 1.10, 0.64, 6)], 3, "leather_dark", t=0.04, M_=56))
        low += buckle("bronze", -0.69)
        for k in range(14):
            c = k / 14 * TAU
            strip = lshell("strip", [(-0.58, 1.20, 0.74, 5), (-0.30, 1.15, 0.69, 5), (-0.06, 1.12, 0.66, 6)], 6,
                           "leather" if k % 2 else "leather_red", t=0.03, th=(c - 0.19, c + 0.19), M_=8)
            low.append(strip)
        low.append(studs("strip_studs", (-0.5, 1.19, 0.73), (0, TAU), 14, 0.03, "bronze", grow=0.035, n=5))
        # 어깨 가죽 패드
        ra.append(pauldron("leather", "leather_dark", lames=2, stud_mat="bronze"))
    elif style == "iron":
        dfm = chest_deform(0.05, 0.03)
        up.append(lshell("cuirass", CUIRASS, 22, "iron", t=0.05, deform=dfm, M_=56))
        up.append(rim("collar", CUIRASS[-1], (0, TAU), 0.04, "darkiron", grow=0.03, n=3, deform=dfm))
        up.append(rim("hem", CUIRASS[0], (0, TAU), 0.035, "darkiron", grow=0.035, n=6, deform=dfm))
        up.append(studs("hem_rivets", (-0.80, 1.06, 0.60), (0, TAU), 26, 0.03, "darkiron", grow=0.05, n=6, deform=dfm))
        up.append(studs("collar_rivets", (0.86, 0.95, 0.64), (0, TAU), 16, 0.026, "darkiron", grow=0.05, n=4))
        # 옆구리 가죽 버클 끈
        for sx in (-1, 1):
            for z in (-0.4, 0.3):
                up.append(lshell("side_strap", [(z - 0.06, 1.12, 0.66, 6), (z + 0.06, 1.12, 0.66, 6)], 2,
                                 "leather_dark", t=0.02, th=(-0.45, 0.45) if sx > 0 else (PI - 0.45, PI + 0.45), M_=10))
        low.append(lshell("belt", [(-0.06, 1.10, 0.64, 6), (0.14, 1.10, 0.64, 6)], 3, "leather_dark", t=0.04, M_=56))
        low += buckle("darkiron", -0.69)
        low.append(lshell("mail_skirt", [(-0.60, 1.22, 0.76, 4), (-0.30, 1.16, 0.70, 5), (-0.02, 1.11, 0.65, 6)], 7,
                          "mail", t=0.025, M_=56, bev=0))
        low.append(rim("mail_hem", (-0.60, 1.22, 0.76), (0, TAU), 0.02, "darkiron", grow=0.01, n=4))
        ra.append(pauldron("iron", "darkiron", lames=2, stud_mat="darkiron"))
    else:  # knight
        dfm = chest_deform(0.07, 0.045)
        up.append(lshell("cuirass", CUIRASS, 24, "steel", t=0.05, deform=dfm, M_=64))
        up.append(rim("collar", CUIRASS[-1], (0, TAU), 0.045, "gold", grow=0.03, n=3, deform=dfm))
        up.append(rim("hem", CUIRASS[0], (0, TAU), 0.04, "gold", grow=0.035, n=6, deform=dfm))
        up.append(emblem())  # 가슴 중앙 금 방패 문양
        up.append(studs("hem_rivets", (-0.80, 1.06, 0.60), (0, TAU), 24, 0.026, "gold", grow=0.05, n=6, deform=dfm))
        low.append(lshell("belt", [(-0.06, 1.10, 0.64, 6), (0.14, 1.10, 0.64, 6)], 3, "leather_red", t=0.04, M_=56))
        low += buckle("gold", -0.69)
        for i in range(3):
            z1 = 0.02 - i * 0.16
            ctrl = [(z1 - 0.20, 1.17 + 0.04 * i, 0.71 + 0.04 * i, 5), (z1, 1.12 + 0.04 * i, 0.66 + 0.04 * i, 6)]
            low.append(lshell(f"fauld{i}", ctrl, 3, "steel", t=0.035, M_=56))
            low.append(rim(f"fauld_rim{i}", ctrl[0], (0, TAU), 0.022, "gold", grow=0.03, n=5))
        ra.append(pauldron("steel", "gold", lames=3, stud_mat="gold", big=True))
    la = [mirror_x(o, o.name + "_L") for o in ra]
    return {"UpperTorso": up, "LowerTorso": low, "RightUpperArm": ra, "LeftUpperArm": la}


def buckle(mat, y):
    pts = np.array([(-0.13, y - 0.03, -0.07), (0.13, y - 0.03, -0.07), (0.13, y - 0.03, 0.13), (-0.13, y - 0.03, 0.13)])
    # 모서리를 촘촘히 해서 관이 둥글게 꺾이도록
    dense = []
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        for t in np.linspace(0, 1, 6, endpoint=False):
            dense.append(a + (b - a) * t)
    frame = tube("buckle", np.asarray(dense), 0.025, closed=True, segs=6, mat=M(mat))
    pin = tube("pin", np.array([(0.0, y - 0.035, -0.07), (0.0, y - 0.04, 0.13)]), 0.014, closed=False, segs=6, mat=M(mat))
    return [frame, pin]


def emblem():
    """가슴 중앙의 금 방패 문양(살짝 돋은 판)."""
    zs = np.linspace(0.0, 0.5, 9)
    def wdt(z):
        s = (z - 0.0) / 0.5
        return 0.06 + 0.16 * np.sqrt(np.clip(s, 0, 1)) * (1 - 0.25 * s)
    verts, faces = [], []
    cols = 9
    for i, z in enumerate(zs):
        w = wdt(z)
        for j in range(cols):
            x = (j / (cols - 1) * 2 - 1) * w
            y = -0.64 - 0.07 * math.exp(-((z - 0.25) / 0.45) ** 2) - 0.045 * math.exp(-(x / 0.12) ** 2) * math.exp(-((z - 0.05) / 0.7) ** 2)
            verts.append((x, y - 0.055, z))
    for i in range(len(zs) - 1):
        for j in range(cols - 1):
            a = i * cols + j
            faces.append((a, a + cols, a + cols + 1, a + 1))
    ob = L.mesh_from("emblem", verts, faces, M("gold"))
    L.outward_normals_open(ob, (0, 0.5, 0.25))
    L.solidify(ob, 0.025, offset=1.0)
    L.bevel(ob, 0.008, 1, 50)
    return ob


def pauldron(mat, trim, lames=2, stud_mat=None, big=False):
    """오른팔 어깨받이(바깥 = -X). 왼팔은 거울 복사."""
    th = (PI - 2.25, PI + 2.25)
    s = 1.08 if big else 1.0
    dome = [(0.10, 0.70 * s, 0.68 * s, 4, -0.06, 0), (0.45, 0.70 * s, 0.68 * s, 4, -0.06, 0),
            (0.63, 0.67 * s, 0.65 * s, 4, -0.05, 0), (0.76, 0.56 * s, 0.54 * s, 3.5, -0.04, 0),
            (0.85, 0.36 * s, 0.35 * s, 3, -0.03, 0), (0.90, 0.04, 0.04, 2.5, -0.02, 0)]
    objs = [lshell("pauldron", dome, 16, mat, t=0.045, th=th, M_=36)]
    objs.append(rim("p_rim", (0.10, 0.70 * s, 0.68 * s), th, 0.026, trim, grow=0.03, n=4, cx=-0.06))
    for i in range(1, lames + 1):
        zt = 0.16 - i * 0.17
        a = (0.73 + 0.03 * i) * s
        ctrl = [(zt - 0.24, a + 0.04, a + 0.02, 4, -0.08 - 0.02 * i, 0), (zt, a, a - 0.02, 4, -0.07 - 0.02 * i, 0)]
        objs.append(lshell(f"lame{i}", ctrl, 3, mat, t=0.04, th=(PI - 2.0, PI + 2.0), M_=32))
        objs.append(rim(f"lame_rim{i}", ctrl[0], (PI - 2.0, PI + 2.0), 0.022, trim, grow=0.03, n=4, cx=-0.08 - 0.02 * i))
    if stud_mat:
        objs.append(studs("p_studs", (0.22, 0.70 * s, 0.68 * s), (PI - 1.8, PI + 1.8), 7, 0.03, stud_mat,
                          grow=0.045, n=4, cx=-0.06))
    return L.join(objs, "pauldron_R")


# ─────────────────────────────────────────────────────────── 투구 ──
def build_helmet(style):
    objs = []
    if style == "leather":
        dome = [(0.16, 0.70, 0.71, 2.4), (0.36, 0.70, 0.71, 2.4), (0.55, 0.62, 0.63, 2.4),
                (0.70, 0.42, 0.43, 2.4), (0.79, 0.10, 0.10, 2.4), (0.81, 0.0, 0.0, 2.4)]
        objs.append(lshell("cap", dome, 16, "leather", t=0.05, M_=48))
        # 뒤·옆 덮개(귀 덮개 포함), 얼굴은 열림
        gap = 1.05
        skirt = [(-0.46, 0.73, 0.73, 2.4), (-0.10, 0.71, 0.71, 2.4), (0.20, 0.70, 0.71, 2.4)]
        objs.append(lshell("flaps", skirt, 8, "leather", t=0.045, th=(FRONT + gap, FRONT + TAU - gap), M_=40))
        objs.append(rim("brow", (0.16, 0.70, 0.71), (0, TAU), 0.045, "leather_dark", grow=0.035, n=2.4))
        objs.append(rim("flap_hem", (-0.46, 0.73, 0.73), (FRONT + gap, FRONT + TAU - gap), 0.03, "leather_dark", grow=0.03, n=2.4))
        for k in range(4):  # 박음질 솔기
            th = FRONT + k * PI / 2
            p = meridian(dome, th, 0.055, z0=0.16)
            objs.append(tube("seam", p, 0.016, closed=False, segs=6, mat=M("leather_dark")))
        objs.append(studs("brow_studs", (0.16, 0.70, 0.71), (0, TAU), 14, 0.03, "bronze", grow=0.07, n=2.4))
    elif style == "iron":
        dome = [(0.14, 0.71, 0.71, 2.2), (0.34, 0.70, 0.70, 2.2), (0.55, 0.62, 0.62, 2.2),
                (0.75, 0.38, 0.38, 2.2), (0.92, 0.10, 0.10, 2.2), (0.98, 0.0, 0.0, 2.2)]
        objs.append(lshell("dome", dome, 18, "iron", t=0.05, M_=48))
        objs.append(rim("brow", (0.15, 0.71, 0.71), (0, TAU), 0.05, "darkiron", grow=0.035, n=2.2))
        objs.append(studs("brow_rivets", (0.15, 0.71, 0.71), (0, TAU), 16, 0.03, "darkiron", grow=0.085, n=2.2))
        for k in range(4):
            th = FRONT + PI / 4 + k * PI / 2
            p = meridian(dome, th, 0.06, z0=0.17, z1=0.95)
            objs.append(tube("band", p, 0.035, closed=False, segs=8, mat=M("darkiron"), flat=0.35))
        # 코 가리개
        objs.append(lshell("nasal", [(-0.24, 0.74, 0.74, 2.2), (0.0, 0.74, 0.745, 2.2), (0.18, 0.72, 0.725, 2.2)], 4,
                           "iron", t=0.04, th=(FRONT - 0.12, FRONT + 0.12), M_=6))
        # 사슬 목가리개
        gap = 0.95
        mail = [(-0.66, 0.80, 0.80, 2.4), (-0.30, 0.76, 0.76, 2.4), (0.14, 0.70, 0.70, 2.3)]
        objs.append(lshell("aventail", mail, 9, "mail", t=0.025, th=(FRONT + gap, FRONT + TAU - gap), M_=40, bev=0))
        objs.append(rim("aventail_hem", (-0.66, 0.80, 0.80), (FRONT + gap, FRONT + TAU - gap), 0.02, "darkiron", n=2.4))
    else:  # knight close helm
        dome = [(0.12, 0.71, 0.72, 2.3), (0.38, 0.71, 0.72, 2.3), (0.60, 0.60, 0.61, 2.3),
                (0.78, 0.36, 0.37, 2.3), (0.86, 0.10, 0.10, 2.3), (0.88, 0.0, 0.0, 2.3)]
        objs.append(lshell("skull", dome, 18, "steel", t=0.05, M_=56))

        def beak(p, th):
            x, y, z = p[:, 0], p[:, 1], p[:, 2]
            fm = np.clip(-y / 0.7, 0, 1) ** 3
            y = y - 0.13 * fm * np.exp(-((z + 0.12) / 0.28) ** 2) * np.exp(-(x / 0.45) ** 2)
            return np.stack([x, y, z], 1)
        lower = [(-0.70, 0.76, 0.78, 2.5), (-0.50, 0.71, 0.73, 2.5), (-0.20, 0.71, 0.73, 2.4), (0.06, 0.71, 0.72, 2.3)]
        objs.append(lshell("face", lower, 14, "steel", t=0.05, M_=56, deform=beak))
        slit = 0.85
        objs.append(lshell("slit_fill", [(0.04, 0.71, 0.72, 2.3), (0.14, 0.71, 0.72, 2.3)], 2, "steel", t=0.05,
                           th=(FRONT + slit, FRONT + TAU - slit), M_=40))
        objs.append(lshell("liner", [(-0.12, 0.645, 0.645, 2.3), (0.28, 0.645, 0.645, 2.3)], 3, "inner", t=0.01,
                           th=(FRONT - 1.0, FRONT + 1.0), M_=16, bev=0))
        objs.append(rim("slit_top", (0.12, 0.71, 0.72), (FRONT - slit, FRONT + slit), 0.022, "gold", grow=0.05, n=2.3))
        objs.append(rim("slit_bot", (0.06, 0.71, 0.72), (FRONT - slit, FRONT + slit), 0.022, "gold", grow=0.05, n=2.3,
                        deform=beak))
        objs.append(rim("gorget", (-0.70, 0.76, 0.78), (0, TAU), 0.035, "gold", grow=0.035, n=2.5))
        crest = meridian(dome, FRONT, 0.055, z0=0.13)
        crest_b = meridian(dome, FRONT + PI, 0.055, z0=0.13)[::-1]
        objs.append(tube("crest", np.vstack([crest, crest_b]), 0.03, closed=False, segs=8, mat=M("gold"), flat=0.5))
        # 숨구멍(오른뺨 쪽)
        pts, nrm = [], []
        for i in range(3):
            for j in range(4):
                th = FRONT - 0.55 - j * 0.12
                z = -0.10 - i * 0.11
                x, y = L.sq_ring(0.77, 0.79, 2.4, np.array([th]))
                pts.append((x[0], y[0], z))
                nrm.append((x[0], y[0], 0))
        objs.append(rivets("breaths", pts, nrm, r=0.022, mat=M("inner"), h=0.15))
        pts2 = [(-x, y, z) for (x, y, z) in pts]
        objs.append(rivets("breaths_L", pts2, [(-a, b, c) for (a, b, c) in nrm], r=0.022, mat=M("inner"), h=0.15))
        # 깃털 장식(붉은 술)
        for k in range(9):
            off = (k - 4) * 0.022
            s = np.linspace(0, 1, 14)
            y = -0.22 + 1.05 * s
            z = 0.90 + 0.28 * np.sin(PI * s * 0.75) - 0.78 * s ** 2.2
            x = np.full_like(s, off) * (1 + 1.6 * s)
            r = 0.05 * (1 - 0.65 * s) + 0.012
            objs.append(tube("plume", np.stack([x, y, z], 1), r, closed=False, segs=6, mat=M("cloth_red"), flat=0.45))
    return {"Head": objs}


# ─────────────────────────────────────────────────────────── 각반 ──
def build_greaves(style):
    ru, rl, rf = [], [], []
    th_thigh = (-PI - 0.40, -0.30)  # 바깥(-X) ~ 앞 ~ 안쪽 앞
    thigh = [(-0.52, 0.62, 0.63, 4), (0.0, 0.65, 0.66, 4), (0.55, 0.67, 0.67, 4)]

    def calf(p, th):
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        bm = np.clip(y / 0.6, 0, 1) ** 2
        return np.stack([x, y + 0.07 * bm * np.exp(-((z - 0.12) / 0.32) ** 2), z], 1)
    shin = [(-0.66, 0.60, 0.60, 4), (-0.40, 0.60, 0.62, 4), (0.0, 0.63, 0.67, 4), (0.32, 0.64, 0.66, 4), (0.50, 0.63, 0.64, 4)]
    # 발(로프트 축 = 뒤꿈치→발끝): z_b, A(폭), B(높이), n, cx, cy(높이 중심)
    foot = [(-0.58, 0.52, 0.24, 4, 0, 0.03), (-0.30, 0.56, 0.27, 4, 0, 0.04), (0.10, 0.56, 0.24, 4, 0, 0.0),
            (0.40, 0.50, 0.20, 4, 0, -0.02), (0.58, 0.36, 0.15, 4, 0, -0.04), (0.66, 0.10, 0.07, 4, 0, -0.05)]
    th_foot = (-0.55, PI + 0.55)

    if style == "leather":
        ru.append(lshell("thigh_guard", thigh, 8, "leather", t=0.045, th=th_thigh, M_=36))
        for z in (-0.32, 0.05, 0.40):  # 다리 뒤로 감기는 끈(앞은 보호대 안쪽에 숨음)
            ru.append(lshell("strap", [(z - 0.05, 0.565, 0.565, 10), (z + 0.05, 0.565, 0.565, 10)], 2, "leather_dark", t=0.025, M_=48))
        ru.append(studs("thigh_studs", (0.22, 0.65, 0.66), (-PI - 0.2, -0.5), 6, 0.03, "bronze", grow=0.045))
        rl.append(lshell("shin_guard", shin[1:], 9, "leather", t=0.045, th=(FRONT - 1.7, FRONT + 1.7), M_=36, deform=calf))
        rl.append(lshell("boot_shaft", [(-0.68, 0.64, 0.64, 4), (-0.36, 0.63, 0.63, 4)], 3, "leather_dark", t=0.04, M_=40))
        rl.append(rim("boot_cuff", (-0.36, 0.63, 0.63), (0, TAU), 0.035, "leather_dark", grow=0.04))
        for z in (-0.15, 0.25):
            rl.append(lshell("strap", [(z - 0.045, 0.565, 0.565, 10), (z + 0.045, 0.565, 0.565, 10)], 2, "leather_dark", t=0.02, M_=48))
        knee = [(0.0, 0.26, 0.24, 3), (0.08, 0.22, 0.20, 3), (0.14, 0.10, 0.09, 3), (0.16, 0.0, 0.0, 3)]
        rl.append(lshell("knee_pad", knee, 6, "leather_dark", t=0.035, M_=24, xform=(TO_FRONT, (0, -0.64, 0.52))))
        rf.append(lshell("boot", foot, 12, "leather_dark", t=0.045, th=th_foot, M_=28, xform=TO_FRONT, caps=(True, False)))
    else:
        mat = "iron" if style == "iron" else "steel"
        trim = "darkiron" if style == "iron" else "gold"
        ru.append(lshell("cuisse", thigh, 9, mat, t=0.045, th=th_thigh, M_=40))
        ru.append(rim("cuisse_rim", thigh[0], th_thigh, 0.026, trim, grow=0.03))
        ru.append(rim("cuisse_rim_t", thigh[-1], th_thigh, 0.026, trim, grow=0.03))
        for z in (-0.25, 0.30):
            ru.append(lshell("strap", [(z - 0.05, 0.565, 0.565, 10), (z + 0.05, 0.565, 0.565, 10)], 2, "leather_dark",
                             t=0.02, M_=48))
        if style == "iron":
            ru.append(studs("cuisse_rivets", (-0.40, 0.62, 0.63), (-PI - 0.25, -0.45), 8, 0.026, "darkiron", grow=0.05))
        rl.append(lshell("greave", shin, 11, mat, t=0.045, M_=48, deform=calf))
        rl.append(rim("greave_rim", shin[0], (0, TAU), 0.028, trim, grow=0.035))
        rl.append(rim("greave_rim_t", shin[-1], (0, TAU), 0.028, trim, grow=0.035))
        # 정강이 능선
        p = np.array([(0, -0.67 - 0.02, z) for z in np.linspace(-0.6, 0.45, 10)])
        rl.append(tube("shin_ridge", p, 0.02, closed=False, segs=6, mat=M(mat), flat=0.6))
        knee = [(0.0, 0.31, 0.29, 3), (0.08, 0.27, 0.25, 3), (0.15, 0.15, 0.14, 3), (0.18, 0.0, 0.0, 3)]
        rl.append(lshell("poleyn", knee, 7, mat, t=0.04, M_=28, xform=(TO_FRONT, (0, -0.66, 0.55))))
        rl.append(rim("poleyn_rim", knee[0], (0, TAU), 0.022, trim, grow=0.03, n=3, xform=(TO_FRONT, (0, -0.66, 0.55))))
        wing = [(0.0, 0.22, 0.30, 3), (0.03, 0.18, 0.25, 3), (0.06, 0.0, 0.0, 3)]
        rl.append(lshell("knee_wing", wing, 4, mat, t=0.03, M_=24, xform=(TO_OUT, (-0.70, -0.30, 0.52))))
        rf.append(lshell("sabaton", foot, 12, mat, t=0.045, th=th_foot, M_=28, xform=TO_FRONT, caps=(True, False)))
        for i, zb in enumerate((-0.05, 0.12, 0.29, 0.44)):
            A = float(np.interp(zb, [f[0] for f in foot], [f[1] for f in foot]))
            B = float(np.interp(zb, [f[0] for f in foot], [f[2] for f in foot]))
            cy = float(np.interp(zb, [f[0] for f in foot], [f[5] for f in foot]))
            rf.append(rim(f"lame{i}", (zb, A, B), (-0.35, PI + 0.35), 0.02, trim, grow=0.045, n=4, cy=cy, xform=TO_FRONT))
    lu = [mirror_x(o, o.name + "_L") for o in ru]
    ll = [mirror_x(o, o.name + "_L") for o in rl]
    lf = [mirror_x(o, o.name + "_L") for o in rf]
    return {"RightUpperLeg": ru, "LeftUpperLeg": lu, "RightLowerLeg": rl, "LeftLowerLeg": ll,
            "RightFoot": rf, "LeftFoot": lf}


SLOTS = {"helmet": build_helmet, "chest": build_chest, "greaves": build_greaves}
SETS = ["leather", "iron", "knight"]
SET_KO = {"leather": "가죽", "iron": "철", "knight": "기사"}
SLOT_KO = {"helmet": "투구", "chest": "갑옷", "greaves": "각반"}


# ────────────────────────────────────────────────────────── 마네킹/렌더 ──
def mannequin(offset=Vector((0, 0, 0))):
    mat = bpy.data.materials.get("clay") or bpy.data.materials.new("clay")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.42, 0.43, 0.46, 1)
    b.inputs["Roughness"].default_value = 0.6
    objs = []
    for part, (sx, sy, sz) in L.R15_SIZE.items():
        loc = L.part_loc_bl(part) + offset
        if part == "Head":
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.6, depth=1.2, location=loc)
            ob = bpy.context.active_object
            m = ob.modifiers.new("b", "BEVEL")
            m.width = 0.22
            m.segments = 4
        else:
            bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
            ob = bpy.context.active_object
            ob.scale = (sx * 0.995, sz * 0.995, sy * 0.995)
            bpy.ops.object.transform_apply(scale=True)
            m = ob.modifiers.new("b", "BEVEL")
            m.width = 0.06
            m.segments = 2
        ob.name = "mannequin_" + part
        ob.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        objs.append(ob)
    return objs


def setup_render(res=900, samples=48):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.sample_clamp_direct = 3.0  # 반짝이는 점(파이어플라이) 억제
    sc.cycles.sample_clamp_indirect = 0.8
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.045, 0.05, 0.06, 1)
    bg.inputs["Strength"].default_value = 1.0
    if "key" not in bpy.data.objects:
        for name, rotd, energy, size in (("key", (55, 0, -35), 3.2, 3), ("rim", (60, 0, 160), 2.2, 2), ("fill", (75, 0, 60), 0.8, 8)):
            ld = bpy.data.lights.new(name, "SUN")
            ld.energy = energy
            ld.angle = math.radians(size)
            lo = bpy.data.objects.new(name, ld)
            lo.rotation_euler = [math.radians(a) for a in rotd]
            L.link(lo)


def render(path, target, dist=12.5, az=30, el=12, lens=50, ortho=None):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("cam")
    if cam is None:
        cd = bpy.data.cameras.new("cam")
        cam = bpy.data.objects.new("cam", cd)
        L.link(cam)
    cam.data.lens = lens
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
    a, e = math.radians(az), math.radians(el)
    t = Vector(target)
    cam.location = t + Vector((dist * math.sin(a) * math.cos(e), -dist * math.cos(a) * math.cos(e), dist * math.sin(e)))
    d = t - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


# ─────────────────────────────────────────────────────────────── 메인 ──
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sets", default=",".join(SETS))
    ap.add_argument("--slots", default=",".join(SLOTS))
    ap.add_argument("--no-bake", action="store_true")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--tex", type=int, default=1024)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--preview-samples", type=int, default=64)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])

    out = Path(a.out)
    (out / "textures").mkdir(parents=True, exist_ok=True)
    (out / "previews").mkdir(parents=True, exist_ok=True)
    fit_path = out / "fit_data.json"
    fit = json.loads(fit_path.read_text("utf-8")) if fit_path.exists() else {}

    L.reset_scene()
    setup_render(samples=a.preview_samples)
    sets = [s for s in a.sets.split(",") if s]
    lineup, done_objs = [], []
    for si, st in enumerate(sets):
        set_objs = []
        for slot in [s for s in a.slots.split(",") if s]:
            t0 = time.time()
            parts = SLOTS[slot](st)
            objs = []
            for part, olist in parts.items():
                olist = [o for o in olist if o is not None]
                if not olist:
                    continue
                ob = L.join(olist, part)
                L.limit_tris(ob)
                L.finish(ob)
                ob.location = L.part_loc_bl(part)
                objs.append(ob)
            key = f"{st}_{slot}"
            if not a.no_bake:
                L.unwrap_pack(objs)
                maps = L.bake_atlas(objs, out / "textures", key, size=a.tex, samples=a.samples)
                L.assign_single(objs, L.atlas_material(key, maps))
                L.export(objs, out / f"{key}.fbx")
            meta = {}
            for ob in objs:
                c, s = L.bbox_local(ob)
                meta[ob.name] = {
                    "offset": [round(v, 4) for v in L.bl_to_rbx(c)],
                    "size": [round(abs(v), 4) for v in (s[0], s[2], s[1])],
                    "tris": L.tri_count(ob),
                }
            fit.setdefault(st, {})[slot] = meta
            for ob in objs:  # 다음 세트가 같은 부위 이름(Head 등)을 그대로 쓸 수 있게 이름 비우기
                ob.name = ob.data.name = f"{key}__{ob.name}"
            tris = sum(m["tris"] for m in meta.values())
            print(f"[{key}] 부위 {len(objs)}개, 삼각형 {tris:,} (최대 {max(m['tris'] for m in meta.values()):,}/부위), "
                  f"{time.time() - t0:.0f}s", flush=True)
            set_objs += objs
        # 세트 미리보기(앞서 만든 세트는 숨김)
        if not a.no_preview:
            for o in done_objs:
                o.hide_render = True
            man = mannequin()
            render(out / "previews" / f"{st}_front.png", (0, 0, 2.85), az=28)
            render(out / "previews" / f"{st}_back.png", (0, 0, 2.85), az=200)
            render(out / "previews" / f"{st}_helmet.png", (0, 0, 4.85), dist=4.2, az=35, el=8)
            for o in man:
                bpy.data.objects.remove(o)
        off = Vector(((si - (len(sets) - 1) / 2) * -4.6, 0, 0))
        for o in set_objs:
            o.location += off
        lineup.append(off)
        done_objs += set_objs
    fit_path.write_text(json.dumps(fit, ensure_ascii=False, indent=1), "utf-8")
    if not a.no_preview and len(lineup) == len(SETS):  # 전 세트를 한 번에 만든 경우에만 단체 사진
        for o in done_objs:
            o.hide_render = False
        for off in lineup:
            mannequin(off)
        bpy.context.scene.render.resolution_x = 1500
        render(out / "previews" / "lineup.png", (0, 0, 2.95), dist=21, az=12, el=10)
    print("완료:", out)


if __name__ == "__main__":
    main()
