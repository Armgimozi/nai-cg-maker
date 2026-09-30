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
           mat="SmoothPlastic", earth=0.0, avoid=None):
    """주인공 둘레를 날아다니는 조각들. 카메라 기준 주인공 축보다 앞/뒤로 폴더를 나눔(합성 순서).
    avoid(화면 x, y) 가 참인 곳의 앞 조각은 건너뜀(주인공을 가리지 않게)."""
    rnd = random.Random(seed)
    out = []
    axis_depth = cam.project([center])[0][2]
    made = 0
    for _ in range(count * 6):
        if made >= count:
            break
        a = rnd.uniform(0, 360)
        rr = radius[0] + (radius[1] - radius[0]) * rnd.random() ** 0.7
        y = height[0] + (height[1] - height[0]) * rnd.random()
        p = (center[0] + math.cos(math.radians(a)) * rr, center[1] + y, center[2] + math.sin(math.radians(a)) * rr)
        s = scale * rnd.uniform(0.45, 1.3)
        R = ry(rnd.uniform(0, 360)) @ rx(rnd.uniform(-70, 70)) @ rz(rnd.uniform(-70, 70))
        sx, sy, depth = cam.project([p])[0]
        folder = folder_front if depth < axis_depth else folder_back
        if avoid and folder == folder_front and avoid(sx, sy):
            continue
        made += 1
        if rnd.random() < earth:
            # 흙덩이(위는 풀): 땅이 터져 떠오른 조각
            size = (s * 1.3, s * 0.8, s * 1.1)
            out.append(part(folder, "Block", size, p, R, (120, 84, 56), "Ground"))
            top = np.array(p) + R @ np.array([0, size[1] * 0.5 + 0.12 * s, 0])
            out.append(part(folder, "Block", (size[0] * 1.02, 0.25 * s, size[2] * 1.02), top, R, (96, 190, 70), "Grass"))
        else:
            col = rnd.choice(colors)
            size = (s * 0.95, s * 1.9, s * 0.75)
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
    head=(숙임+/들기-, 좌우), arm_l/arm_r=(앞으로 들기, 옆으로 벌리기), leg_l/leg_r=(앞뒤), lean=몸 기울기,
    mouth="o" 면 놀란 입, face=False 면 얼굴(눈·입) 없음(뒷모습), tufts = 삐친 머리 뭉치 목록."""
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
    # 머리카락(뒤에서 봐도 사람 머리로): 머리를 감싸는 짧은 원통 껍질(얼굴 쪽은 비켜 뒤로 밀림) + 위 덮개
    #   + 위·뒤로 삐친 뾰족한 뭉치 몇 개(모서리 쐐기) — 둥근 공 하나면 헬멧처럼 보임
    head_part("Cylinder", (0.78, 1.4, 1.4), (0, 0.96, 0.1), col["hair"], rz(90))
    head_part("Cylinder", (0.3, 1.3, 1.3), (0, 1.36, 0.06), col["hair"], rz(90))
    for (x, z, yaw_t, tilt, s) in pose.get("tufts", ((-0.38, 0.28, 200, -32, 0.62), (0.34, 0.3, 160, -30, 0.66),
                                                     (0.0, 0.46, 180, -52, 0.6), (-0.05, -0.02, 150, -18, 0.58),
                                                     (0.42, -0.12, 120, -10, 0.46))):
        head_part("CornerWedge", (s, s * 1.1, s), (x, 1.46 + s * 0.3, z), col["hair"], ry(yaw_t) @ rx(tilt))
    head_part("Block", (1.16, 0.5, 0.3), (0, 0.5, 0.52), col["hair"])  # 뒷머리(목 위까지)
    head_part("Block", (1.0, 0.24, 0.3), (0, 1.1, -0.55), col["hair"])  # 앞머리
    # 얼굴(앞 = -Z): 눈 둘 + 입
    if pose.get("face", True):  # 뒤에서 보는 그림은 얼굴을 빼서 옆으로 보이는 눈이 띠처럼 보이지 않게
        head_part("Block", (0.16, 0.26, 0.06), (-0.26, 0.7, -0.62), col["eye"])
        head_part("Block", (0.16, 0.26, 0.06), (0.26, 0.7, -0.62), col["eye"])
        if pose.get("mouth") == "o":  # 놀란 입
            head_part("Block", (0.3, 0.3, 0.06), (0, 0.36, -0.62), col["eye"])
        else:
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


# three.js 3D 층(render3d.js + scene3d.js) — 소품(볼록 바위·결정)·아바타·주인공을 같은 카메라로 ----------------------
def sun_direction(clock=14.5, lat=41.733):
    """world_preview/scene.js 의 해 방향(Lighting.ClockTime·GeographicLatitude) — 배경 그림자와 같은 쪽에서 빛이 오게."""
    a = 2 * math.pi * clock / 24
    x, y = math.sin(a), -math.cos(a)
    la = math.radians(lat)
    v = np.array([x, y * math.cos(la), y * math.sin(la)])
    return (v / np.linalg.norm(v)).tolist()


def cam3d(cam: Camera) -> dict:
    return {"eye": cam.eye.round(4).tolist(), "target": cam.target.round(4).tolist(), "fov": cam.fov}


def to3d(parts: list) -> list:
    """무대 파트(part()) → scene3d.js 파트(덤프 모양 {c,s,p,m,z,col(0~1),mat,t})."""
    out = []
    for p in parts:
        shape = p["shape"]
        out.append({"c": {"Wedge": "WedgePart", "CornerWedge": "CornerWedgePart"}.get(shape, "Part"), "s": shape,
                    "p": p["cf"][:3], "m": p["cf"][3:], "z": p["size"], "col": [c / 255 for c in p["color"]],
                    "mat": p["mat"], "t": p.get("t", 0)})
    return out


def dump_parts(dump: Path, prefix: str) -> list:
    """덤프에서 경로가 prefix 로 시작하는 파트(scene3d.js 에 그대로 넘길 수 있는 모양)."""
    return [p for p in json.loads(Path(dump).read_text())["parts"] if p.get("path", "").startswith(prefix)]


def render3d(scene: dict) -> dict:
    """scene3d.js 장면(dict) → 층 PNG 경로 {이름: 경로}. 같은 장면이면 캐시(cache/r3d/<해시>)."""
    key = _hash({"scene": scene, "v": 1})
    out = CACHE / "r3d" / key
    names = [layer["name"] for layer in scene["layers"]]
    if not all((out / f"{n}.png").exists() for n in names):
        out.mkdir(parents=True, exist_ok=True)
        (out / "scene.json").write_text(json.dumps(scene))
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
        env = dict(os.environ, NODE_PATH=npm_root)
        proc = subprocess.run(["node", "tools/store/render3d.js", str(out / "scene.json"), str(out)], cwd=ROOT, env=env,
                              capture_output=True, text=True)
        if proc.returncode != 0:
            shutil.rmtree(out, ignore_errors=True)
            raise RuntimeError(f"render3d 실패:\n{proc.stdout[-2000:]}\n{proc.stderr[-3000:]}")
    return {n: out / f"{n}.png" for n in names}


def _outward_rot(direction, spin):
    """scene3d 결정의 긴 축(로컬 Y)이 direction 을 향하는 오일러(YXZ, 도)."""
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    return [math.degrees(math.acos(max(-1.0, min(1.0, d[1])))), math.degrees(math.atan2(d[0], d[2])), spin]


def crystals3d(center, count, radius, height, length, seed, colors, cam: Camera, avoid=None, core=None, min_y=30):
    """주인공 둘레에서 터져 나가는 길쭉한 결정(scene3d shards). 긴 축은 core(폭발 가운데)에서 바깥으로.
    결과 (앞 목록, 뒤 목록): 카메라 기준 주인공 축보다 가까우면 앞. avoid(sx, sy) 가 참인 곳의 앞 결정은 건너뜀.
    min_y = 화면에서 이보다 위(제목 글자 자리)에는 두지 않음."""
    rnd = random.Random(seed)
    c = np.array(center, float)
    core = np.array(core if core is not None else c + np.array([0, height[1] * 0.45, 0]), float)
    axis_depth = cam.project([c])[0][2]
    front, back = [], []
    tries = 0
    while len(front) + len(back) < count and tries < count * 40:
        tries += 1
        a = rnd.uniform(0, math.tau)
        rr = radius[0] + (radius[1] - radius[0]) * rnd.random() ** 0.8
        y = height[0] + (height[1] - height[0]) * rnd.random() ** 0.9
        p = c + np.array([math.cos(a) * rr, y, math.sin(a) * rr])
        sx, sy, depth = cam.project([p])[0]
        is_front = depth < axis_depth
        if not (40 < sx < cam.W - 40 and min_y < sy < cam.H - 60):
            continue
        if avoid and is_front and avoid(sx, sy):
            continue
        L = length * (0.55 + rnd.random() ** 1.6 * 0.9)
        out = p - core
        out = out / np.linalg.norm(out) + np.array([rnd.uniform(-0.8, 0.8), rnd.uniform(-0.5, 0.8), rnd.uniform(-0.8, 0.8)])
        item = {"p": p.round(3).tolist(), "len": round(L, 3), "radius": round(L * rnd.uniform(0.3, 0.4), 3),
                "flat": rnd.uniform(0.75, 1.0), "rot": _outward_rot(out, rnd.uniform(0, 360)), "seed": 100 + tries,
                "shape": "chunk", "col": [v / 255 for v in rnd.choice(colors)], "rough": 0.3}
        (front if is_front else back).append(item)
    return front, back


def rocks3d(center, radius, count, scale, seed, color, skip_angles=(), jitter=0.3):
    """주인공 발밑을 둘러싼 각진 바위(scene3d rocks, 볼록 껍질). skip_angles = [(가운데 각, 반폭)] 은 비움(앞 시야)."""
    rnd = random.Random(seed)
    c = np.array(center, float)
    out = []
    for i in range(count):
        a = (i + rnd.uniform(-jitter, jitter)) / count * 360
        if any(abs((a - s + 180) % 360 - 180) < w for s, w in skip_angles):
            continue
        rr = radius * rnd.uniform(0.85, 1.2)
        s = scale * rnd.uniform(0.65, 1.3)
        h = s * rnd.uniform(0.6, 1.0)
        pos = c + np.array([math.cos(math.radians(a)) * rr, h * 0.36, math.sin(math.radians(a)) * rr])
        shade = rnd.uniform(0.82, 1.1)
        out.append({"p": pos.round(3).tolist(), "size": [s * rnd.uniform(1.0, 1.5), h, s * rnd.uniform(0.9, 1.3)],
                    "rot": [rnd.uniform(-14, 14), rnd.uniform(0, 360), rnd.uniform(-16, 16)],
                    "col": [min(1, v / 255 * shade) for v in color], "mat": "Slate", "seed": seed * 31 + i})
        if rnd.random() < 0.6:  # 작은 돌 부스러기
            a2 = math.radians(a + rnd.uniform(-9, 9))
            r2 = rr + s * rnd.uniform(0.7, 1.2)
            s2 = s * rnd.uniform(0.28, 0.45)
            out.append({"p": (c + np.array([math.cos(a2) * r2, s2 * 0.25, math.sin(a2) * r2])).round(3).tolist(),
                        "size": [s2 * 1.2, s2 * 0.8, s2], "rot": [0, rnd.uniform(0, 360), 0],
                        "col": [min(1, v / 255 * shade * 0.92) for v in color], "mat": "Slate", "seed": seed * 57 + i})
    return out
