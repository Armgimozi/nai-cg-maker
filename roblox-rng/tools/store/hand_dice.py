"""아이콘 오른쪽 아래 '주사위 쥔 손' — three.js(scene3d.js prims)로 그린 3D 모형(둥근 주사위 + 캡슐 손가락).

좌표: 카메라가 +Z 쪽에서 -Z 를 봄(화면 오른쪽 = +X, 위 = +Y). 주사위는 모서리 2 인 둥근 정육면체(윗면 산호색 1, 앞 2, 오른쪽 3 —
게임 dice.svg 와 같은 흰 주사위), 손바닥이 주사위 밑을 받치고 손가락은 왼쪽 앞에서 감싸 올라오며, 엄지는 앞면 위로 걸침.
    layers = hand_dice.render(size=1024)   # {"dice": 경로, ...} 투명 PNG
"""
from __future__ import annotations

import math

import numpy as np

import stage as st

SKIN = [1.0, 0.8, 0.64]
SKIN_DARK = [0.95, 0.66, 0.5]
INK = [0.12, 0.1, 0.18]
CORAL = [1.0, 0.37, 0.36]
DICE = [0.97, 0.96, 1.0]

DICE_ROT = [16, -40, 4]  # 주사위 묶음 돌림(YXZ 도): 윗면·앞면·오른면이 보이게


def _pips(face_n, face_u, face_v, spots, r, color):
    out = []
    n, u, v = (np.array(x, float) for x in (face_n, face_u, face_v))
    for (a, b) in spots:
        p = n * 1.0 + u * a * 0.52 + v * b * 0.52
        # 납작한 점(타원체): 면 방향으로 얇게. 오일러 대신 축을 맞춘 회전 = u, v, n 을 열로
        R = np.stack([u, v, n], 1)
        yaw = math.degrees(math.atan2(R[0, 2], R[2, 2]))
        pitch = math.degrees(math.asin(-R[1, 2]))
        roll = math.degrees(math.atan2(R[1, 0], R[1, 1]))
        out.append({"type": "sphere", "p": p.round(4).tolist(), "scale": [r, r, r * 0.22], "rot": [pitch, yaw, roll],
                    "col": color, "rough": 0.4, "parent": {"p": [0, 0, 0], "rot": DICE_ROT}})
    return out


def dice_prims():
    prims = [{"type": "roundbox", "p": [0, 0, 0], "size": [2, 2, 2], "radius": 0.34, "col": DICE, "rough": 0.32,
              "rot": [0, 0, 0], "parent": {"p": [0, 0, 0], "rot": DICE_ROT}}]
    prims += _pips([0, 1, 0], [1, 0, 0], [0, 0, -1], [(0, 0)], 0.36, CORAL)  # 위 1
    prims += _pips([0, 0, 1], [1, 0, 0], [0, 1, 0], [(-0.55, 0.55), (0.55, -0.55)], 0.2, INK)  # 앞 2
    prims += _pips([1, 0, 0], [0, 0, -1], [0, 1, 0], [(-0.6, 0.6), (0, 0), (0.6, -0.6)], 0.2, INK)  # 오른쪽 3
    return prims


def _finger(base, direction, lengths, r, curl, axis=None):
    """마디 캡슐들: base 에서 direction 으로, 마디마다 curl 도씩 위로(axis 가 없으면 방향×위 축 둘레) 굽힘."""
    out = []
    p = np.array(base, float)
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    k = np.array(axis if axis is not None else np.cross(d, [0, 1, 0]), float)
    k /= np.linalg.norm(k)
    for i, L in enumerate(lengths):
        q = p + d * L
        rr = r * (1 - 0.07 * i)
        out.append({"type": "capsule", "a": p.round(4).tolist(), "b": q.round(4).tolist(), "r": rr, "col": SKIN,
                    "rough": 0.62})
        th = math.radians(curl)
        d = d * math.cos(th) + np.cross(k, d) * math.sin(th) + k * np.dot(k, d) * (1 - math.cos(th))
        p = q
    return out


def hand_prims():
    prims = []
    # 팔뚝(오른쪽 아래 밖에서) + 손바닥(주사위 밑, 위를 봄)
    prims.append({"type": "capsule", "a": [1.0, -1.9, 0.4], "b": [4.0, -4.8, 1.4], "r": 0.9, "col": SKIN, "rough": 0.62})
    prims.append({"type": "sphere", "p": [0.2, -1.52, 0.25], "scale": [1.35, 0.5, 1.2], "rot": [6, 25, -10],
                  "col": SKIN, "rough": 0.62})
    # 네 손가락: 손바닥 왼쪽 가장자리에서 왼쪽으로 나가 주사위 왼쪽 옆면을 감싸 올라감
    for i, (bz, ln) in enumerate([(1.0, 0.62), (0.45, 0.68), (-0.1, 0.66), (-0.62, 0.55)]):
        base = [-0.55 - 0.08 * abs(i - 1.5), -1.5, bz]
        prims += _finger(base, [-1, 0.15, 0.25 - 0.1 * i], [ln, ln * 0.8, ln * 0.7], 0.29, 52)
    # 엄지: 손바닥 오른쪽 앞에서 위로 올라와 앞면(오른쪽) 아래 모서리를 덮음
    prims += _finger([0.95, -1.25, 1.0], [-0.25, 0.9, 0.35], [0.72, 0.62], 0.33, 30, axis=[0, 0, 1])
    return prims


def scene(size=1024):
    cam = {"eye": [-0.6, 3.4, 9.0], "target": [0.2, -0.6, 0], "fov": 34}
    return {
        "size": [size, size],
        "camera": cam,
        "light": {"sun": [-0.5, 0.85, 0.6], "sunColor": [1, 0.97, 0.92], "sunIntensity": 1.0,
                  "hemiSky": [0.85, 0.95, 1], "hemiGround": [0.6, 0.55, 0.6], "hemiIntensity": 0.9,
                  "rims": [{"dir": [-0.6, 0.5, -0.8], "color": [0.47, 1, 0.92], "intensity": 1.0}],
                  "shadowCenter": [0, -0.5, 0], "shadowBox": 5},
        "rim": {"color": [0.47, 1, 0.92], "power": 3.0, "strength": 0.5},
        "objects": [{"tag": "dice", "prims": dice_prims(), "rim": 0.35}, {"tag": "hand", "prims": hand_prims(), "rim": 0.25}],
        "layers": [{"name": "handdice", "draw": ["dice", "hand"]}],
    }


def render(size=1024) -> dict:
    return st.render3d(scene(size))
