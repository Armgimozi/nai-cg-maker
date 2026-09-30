"""스토어 그림 3D 무대: 카메라 수학 + 무대 소품(바위, 수정 조각, 블록 아바타) + 레이어 렌더 실행.

흐름: 무대(dict) → stage_hook.luau 가 진짜 맵 위에 올려 덤프(world.luau) → render_layers.js 가 같은 카메라로
레이어 PNG(배경/주인공/아바타 ...) → thumbs.py 가 fx.py 로 합성.
같은 무대·카메라면 캐시(tools/store/cache/layers/<해시>)를 다시 씀.

좌표는 Roblox 그대로(오른손, Y 위, 모델 앞 = -Z). 회전 행렬 R 의 열 = 로컬 X/Y/Z 축(세계 좌표).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get("STORE_CACHE", ROOT / "tools/store/cache"))
LUAURUN = ROOT / "tools/luaurun/target/release/luaurun"


# 회전 ---------------------------------------------------------------------------------
def rx(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def ry(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


def rz(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def yaw_facing(direction):
    """모델 앞(-Z)이 수평 방향 direction(x, z)을 보게 하는 Y 회전 각(도)."""
    dx, dz = direction[0], direction[-1]
    return math.degrees(math.atan2(-dx, -dz))


def cf(pos, R=None):
    """CFrame 12개 값: 위치 + 회전 행(row) 순서."""
    R = np.eye(3) if R is None else R
    return [float(v) for v in pos] + [float(v) for v in R.reshape(-1)]


class Camera:
    """three.js PerspectiveCamera(fov = 세로 화각) + lookAt(위 = +Y) 와 같은 투영."""

    def __init__(self, eye, target, fov, size=(1920, 1080)):
        self.eye = np.array(eye, float)
        self.target = np.array(target, float)
        self.fov = float(fov)
        self.W, self.H = size
        f = self.target - self.eye
        self.f = f / np.linalg.norm(f)
        r = np.cross(self.f, [0, 1, 0])
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.r, self.f)
        self.t = math.tan(math.radians(self.fov) / 2)

    def spec(self):
        e, t = self.eye, self.target
        return f"cam:{e[0]:.3f},{e[1]:.3f},{e[2]:.3f}:{t[0]:.3f},{t[1]:.3f},{t[2]:.3f}:{self.fov:.2f}"

    def project(self, p, size=None):
        """세계 점(들) → (화면 x, y, 깊이). size 를 주면 그 그림 크기 기준."""
        W, H = size or (self.W, self.H)
        p = np.atleast_2d(np.array(p, float))
        d = p - self.eye
        x, y, z = d @ self.r, d @ self.u, d @ self.f
        z = np.maximum(z, 1e-6)
        aspect = W / H
        sx = (x / (z * self.t * aspect) + 1) / 2 * W
        sy = (1 - y / (z * self.t)) / 2 * H
        return np.stack([sx, sy, z], axis=1)

    def scale_at(self, depth, size=None):
        """깊이 depth 에서 1 스터드가 몇 픽셀인지."""
        H = (size or (self.W, self.H))[1]
        return H / (2 * depth * self.t)


# 무대 소품 ---------------------------------------------------------------------------
def part(folder, shape, size, pos, R=None, color=(200, 200, 200), mat="SmoothPlastic", t=0.0, shadow=True, name=None):
    d = {
        "folder": folder,
        "shape": shape,
        "size": [float(v) for v in size],
        "cf": cf(pos, R),
        "color": [int(round(c)) for c in color],
        "mat": mat,
        "t": t,
        "shadow": shadow,
    }
    if name:
        d["name"] = name
    return d


def rock_ring(center, radius, count, scale, seed, folder="Rocks", color=(150, 152, 158)):
    """주인공 발밑이 터져 올라온 듯한 바위 고리: 바깥으로 기운 뭉툭한 바위들."""
    rnd = random.Random(seed)
    out = []
    cx, cy, cz = center
    for i in range(count):
        a = (i + rnd.uniform(-0.3, 0.3)) / count * 360
        rr = radius * rnd.uniform(0.85, 1.2)
        px, pz = cx + math.cos(math.radians(a)) * rr, cz + math.sin(math.radians(a)) * rr
        s = scale * rnd.uniform(0.6, 1.25)
        size = (s * rnd.uniform(0.9, 1.5), s * rnd.uniform(0.8, 1.4), s * rnd.uniform(0.8, 1.3))
        # 바깥(중심 반대쪽)으로 기울임: 로컬 Y 를 바깥·위로
        outward = yaw_facing((math.cos(math.radians(a)), math.sin(math.radians(a))))
        R = ry(outward) @ rx(-rnd.uniform(18, 40)) @ ry(rnd.uniform(-25, 25)) @ rz(rnd.uniform(-12, 12))
        shade = rnd.uniform(0.85, 1.12)
        col = tuple(min(255, c * shade) for c in color)
        out.append(part(folder, "Block", size, (px, cy + size[1] * 0.18, pz), R, col, "Slate"))
        if rnd.random() < 0.55:  # 작은 돌 부스러기
            s2 = s * rnd.uniform(0.3, 0.5)
            a2 = math.radians(a + rnd.uniform(-8, 8))
            r2 = rr + s * rnd.uniform(0.6, 1.1)
            R2 = ry(rnd.uniform(0, 360)) @ rx(rnd.uniform(-30, 30))
            out.append(
                part(folder, "Block", (s2, s2 * 0.8, s2), (cx + math.cos(a2) * r2, cy + s2 * 0.25, cz + math.sin(a2) * r2),
                     R2, tuple(c * 0.95 for c in col), "Slate")
            )
    return out


def shards(center, count, radius, height, scale, seed, colors, folder_front, folder_back, cam: Camera,
           mat="SmoothPlastic", earth=0.0):
    """주인공 둘레를 날아다니는 조각들. 카메라 기준 주인공 축보다 앞/뒤로 폴더를 나눔(합성 순서)."""
    rnd = random.Random(seed)
    out = []
    axis_depth = cam.project([center])[0][2]
    for i in range(count):
        a = rnd.uniform(0, 360)
        rr = radius[0] + (radius[1] - radius[0]) * rnd.random() ** 0.7
        y = height[0] + (height[1] - height[0]) * rnd.random()
        p = (center[0] + math.cos(math.radians(a)) * rr, center[1] + y, center[2] + math.sin(math.radians(a)) * rr)
        s = scale * rnd.uniform(0.45, 1.3)
        R = ry(rnd.uniform(0, 360)) @ rx(rnd.uniform(-70, 70)) @ rz(rnd.uniform(-70, 70))
        depth = cam.project([p])[0][2]
        folder = folder_front if depth < axis_depth else folder_back
        if rnd.random() < earth:
            # 흙덩이(위는 풀): 땅이 터져 떠오른 조각
            size = (s * 1.3, s * 0.8, s * 1.1)
            out.append(part(folder, "Block", size, p, R, (120, 84, 56), "Ground"))
            top = np.array(p) + R @ np.array([0, size[1] * 0.5 + 0.12 * s, 0])
            out.append(part(folder, "Block", (size[0] * 1.02, 0.25 * s, size[2] * 1.02), top, R, (96, 190, 70), "Grass"))
        else:
            col = rnd.choice(colors)
            size = (s * 0.7, s * 2.2, s * 0.7)
            R2 = R @ ry(45)
            out.append(part(folder, "Block", size, p, R2, col, mat))
            # 뾰족한 끝(위아래 쐐기 둘)
            for sgn in (1, -1):
                tip = np.array(p) + R2 @ np.array([0, sgn * size[1] * 0.62, 0])
                Rt = R2 if sgn > 0 else R2 @ rz(180)
                out.append(part(folder, "Wedge", (size[0], size[1] * 0.25, size[2]), tip, Rt, col, mat))
    return out


# 블록 아바타(R6 비율, 어느 실제 아바타도 아닌 기본 모양) ------------------------------------------
AVATAR_COLORS = {
    "skin": (255, 206, 160),
    "hair": (84, 54, 36),
    "shirt": (236, 86, 58),
    "shirt2": (255, 255, 255),
    "pants": (44, 62, 110),
    "shoe": (245, 245, 245),
    "eye": (30, 27, 46),
}


def avatar(folder, base, yaw, pose=None, colors=None, scale=1.0):
    """블록 아바타 파트 목록. base = 발 가운데(땅), yaw = 앞(-Z)이 향할 Y 각. pose(도):
    head=(숙임+/들기-, 좌우), arm_l/arm_r=(앞으로 들기, 옆으로 벌리기), leg_l/leg_r=(앞뒤), lean=몸 기울기."""
    pose = pose or {}
    col = dict(AVATAR_COLORS, **(colors or {}))
    k = scale
    B = np.array(base, float)
    W = ry(yaw) @ rx(pose.get("lean", 0))
    out = []

    def add(shape, size, local_pos, R_local, color, mat="SmoothPlastic", name=None):
        pos = B + W @ (np.array(local_pos, float) * k)
        out.append(part(folder, shape, np.array(size) * k, pos, W @ R_local, color, mat, name=name))

    def limb(pivot, R_joint, offset, size, color, mat="SmoothPlastic"):
        # 관절(pivot) 기준으로 돌린 팔다리: 중심 = pivot + R_joint @ offset
        center = np.array(pivot, float) + R_joint @ np.array(offset, float)
        add("Block", size, center, R_joint, color, mat)
        return center

    # 몸통(허리 높이 2, 가슴 4)
    add("Block", (2, 2, 1), (0, 3, 0), np.eye(3), col["shirt"], name="Torso")
    # 옷 무늬: 등판 가운데 흰 띠(뒤에서 봐도 캐릭터 느낌)
    add("Block", (2.02, 0.28, 1.02), (0, 2.25, 0), np.eye(3), col["shirt2"])
    # 머리 + 머리카락
    hp, hy = pose.get("head", (0, 0))
    Rh = ry(hy) @ rx(-hp)
    neck = np.array([0, 4.0, 0])

    def head_part(shape, size, off, color, R_extra=np.eye(3), mat="SmoothPlastic"):
        center = neck + Rh @ np.array(off, float)
        add(shape, size, center, Rh @ R_extra, color, mat)

    head_part("Cylinder", (1.2, 1.25, 1.25), (0, 0.62, 0), col["skin"], rz(90))
    head_part("Block", (1.34, 0.42, 1.34), (0, 1.12, 0.05), col["hair"])
    head_part("Block", (1.34, 0.8, 0.4), (0, 0.78, 0.5), col["hair"])  # 뒷머리
    head_part("Block", (0.3, 0.6, 1.1), (-0.58, 0.8, 0.12), col["hair"])
    head_part("Block", (0.3, 0.6, 1.1), (0.58, 0.8, 0.12), col["hair"])
    head_part("Block", (0.5, 0.3, 0.5), (0.25, 1.35, 0.1), col["hair"], ry(20))
    # 얼굴(앞 = -Z): 눈 둘 + 입
    head_part("Block", (0.16, 0.26, 0.06), (-0.26, 0.7, -0.62), col["eye"])
    head_part("Block", (0.16, 0.26, 0.06), (0.26, 0.7, -0.62), col["eye"])
    head_part("Block", (0.46, 0.1, 0.06), (0, 0.38, -0.62), col["eye"])
    # 팔: 어깨 관절(±1.5, 3.5), 팔 중심은 관절 아래 0.5
    for side, key in ((-1, "arm_l"), (1, "arm_r")):
        fwd, out_ang = pose.get(key, (0, 0))
        Rj = rx(fwd) @ rz(side * out_ang)
        pivot = (side * 1.5, 3.5, 0)
        limb(pivot, Rj, (0, -0.5, 0), (1, 2, 1), col["skin"])
        limb(pivot, Rj, (0, 0.2, 0), (1.04, 0.64, 1.04), col["shirt"])  # 소매
    # 다리: 엉덩이 관절(±0.5, 2)
    for side, key in ((-1, "leg_l"), (1, "leg_r")):
        swing = pose.get(key, 0)
        Rj = rx(swing)
        pivot = (side * 0.5, 2.0, 0)
        limb(pivot, Rj, (0, -1.0, 0), (1, 2, 1), col["pants"])
        limb(pivot, Rj, (0, -1.85, -0.08), (1.04, 0.32, 1.2), col["shoe"])
    return out


# 실행 -------------------------------------------------------------------------------
def _hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def world_dump(stage: dict, players: int = 8) -> Path:
    """무대를 올린 맵 덤프(JSON) 경로. 같은 무대면 캐시."""
    key = _hash({"stage": stage, "players": players, "v": 1})
    out = CACHE / "dumps" / f"{key}.json"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    stage_file = out.with_suffix(".stage.json")
    stage_file.write_text(json.dumps(stage))
    proc = subprocess.run(
        [str(LUAURUN), "tools/world_preview/world.luau", f"players={players}", "hook=tools/store/stage_hook.luau",
         f"stage={stage_file}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    text = proc.stdout
    if proc.returncode != 0 or "DUMP_BEGIN" not in text:
        raise RuntimeError(f"world.luau 실패:\n{text[-3000:]}\n{proc.stderr[-3000:]}")
    for line in text.splitlines():
        if line.startswith("[world]") and ("실패" in line or "공원" in line):
            print("   ", line)
    body = text.split("DUMP_BEGIN\n", 1)[1].split("\nDUMP_END", 1)[0]
    out.write_text(body)
    return out


def render_layers(stage: dict, cam: Camera, layers: list, size=None, players: int = 8) -> dict:
    """레이어 PNG 경로 사전 {이름: 경로}. size = 렌더 크기(기본 카메라 크기)."""
    size = size or (cam.W, cam.H)
    dump = world_dump(stage, players)
    spec = {"size": list(size), "cam": cam.spec(), "layers": layers}
    key = _hash({"dump": dump.name, "spec": spec, "v": 2})
    out = CACHE / "layers" / key
    names = [layer["name"] for layer in layers]
    if not all((out / f"{n}.png").exists() for n in names):
        out.mkdir(parents=True, exist_ok=True)
        spec_file = out / "spec.json"
        spec_file.write_text(json.dumps(spec))
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
        env = dict(os.environ, NODE_PATH=npm_root)
        wp = ROOT / "tools/world_preview/node_modules/three"
        if not wp.exists():
            subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=ROOT / "tools/world_preview", check=True)
        proc = subprocess.run(["node", "tools/store/render_layers.js", str(dump), str(spec_file), str(out)],
                              cwd=ROOT, env=env, capture_output=True, text=True)
        print(proc.stdout.strip())
        if proc.returncode != 0:
            shutil.rmtree(out, ignore_errors=True)
            raise RuntimeError(f"render_layers 실패:\n{proc.stdout[-2000:]}\n{proc.stderr[-3000:]}")
    return {n: out / f"{n}.png" for n in names}
