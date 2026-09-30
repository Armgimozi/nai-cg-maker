#!/usr/bin/env python3
"""게임 아이콘(512x512) — 세계수(전설 등급, 가장 희귀한 명소)가 빛을 뿜는 장면 + 위쪽 큰 확률 숫자 + 오른쪽 아래 놀란 아바타.
A/B 시험용으로 지구본 아이콘(icon_globe.png: 광장 지구본에서 에펠탑·피라미드·자유의 여신상이 튀어나옴 + 같은 숫자)도 만듦.

    python3 tools/store/make_icon.py            # art/store/icon_a.png, icon_b.png, icon.png(고른 것), icon_small.png(150px)
    python3 tools/store/make_icon.py a          # 한 변형만(icon.png 는 안 바꿈)
    python3 tools/store/make_icon.py globe      # 지구본 아이콘만(icon_globe.png — A/B 시험용)
    KEEP=1 python3 tools/store/make_icon.py     # 중간 3D 레이어를 art/store/_work/ 에 남김(점검용, .gitignore)
    PICK=a python3 tools/store/make_icon.py     # icon.png 로 쓸 변형(기본 b)

만드는 법
  1) 진짜 명소 빌더(src/shared/Models)로 세계수 파트를 덤프(tools/model_preview/mock.luau, 업로드·API 없음)
  2) tools/store/render3d.js 로 같은 카메라의 3D 층(땅, 금, 마법진, 모형, 결정 조각, 에너지 띠 ...)을 투명 PNG 로
  3) fx.py 로 합성: 하늘 + 초록 빛·햇살 + 어두운 구덩이·금·마법진 + 먹물 불꽃 + 나무(잎 그늘 에메랄드, 민트 테두리, 열매 빛)
     + 바위(잔금) + 깨진 결정(빛나는 면 선) + 에너지 띠 + 반짝이 + 확률 숫자(흰색→노랑, 두꺼운 어두운 테)
     + 놀란 블록 아바타(썸네일과 같은 아바타 + 큰 표정 그림, stage.face_decal)
숫자는 Landmarks.luau 의 세계수 OneIn(10000000000)을 읽어서 게임처럼 콤마로 씀("1/10,000,000,000", 16글자).
긴 숫자라 한 줄로 거의 전체 폭(930/1024) + 세로로 2.1배 늘여서 150px(스토어 목록 크기)에서도 읽히게, 나무는 숫자 아래로 내림.
글자는 영어·숫자만(전 세계 스토어용). Roblox 가 모서리를 둥글게 자르므로 중요한 것은 가운데 88~91% 안에 둠.
"""
from __future__ import annotations

import io
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fx  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "art" / "store"
S = 1024  # 합성 크기(마지막에 512 로 줄임)
R3 = 2048  # 3D 렌더 크기(1024 로 줄여서 가장자리 매끈)
LANDMARK = "worldtree"


# 게임 데이터 --------------------------------------------------------------------------------
def one_in(landmark_id: str) -> int:
    text = (ROOT / "src/shared/Landmarks.luau").read_text()
    m = re.search(r'\{\s*"%s",\s*"[^"]*",\s*"[^"]*",\s*(\d+),' % re.escape(landmark_id), text)
    if not m:
        raise SystemExit(f"Landmarks.luau 에 {landmark_id} 가 없습니다")
    return int(m.group(1))


def rarity_label(n: int) -> str:
    return f"1/{n:,}"


def model_parts(landmark_id: str) -> list:
    with tempfile.TemporaryDirectory() as work:
        out = subprocess.run(
            [str(ROOT / "tools/luaurun/target/release/luaurun"), "tools/model_preview/mock.luau", work],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout
    body = out.split("DUMP_BEGIN\n", 1)[1].split("\nDUMP_END", 1)[0]
    for model in json.loads(body):
        if model["id"] == landmark_id:
            return model["parts"]
    raise SystemExit(f"덤프에 {landmark_id} 모형이 없습니다")


# 카메라(three.js PerspectiveCamera + lookAt 과 같은 식) ---------------------------------------------------
def project(cam, p, size=S):
    eye, target = np.array(cam["eye"], float), np.array(cam["target"], float)
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    d = np.array(p, float) - eye
    z = d @ f
    t = math.tan(math.radians(cam["fov"]) / 2)
    x, y = (d @ r) / (z * t), (d @ u) / (z * t)
    return ((x + 1) / 2 * size, (1 - y) / 2 * size)


def unproject(cam, px, py, depth, size=S):
    """화면 점(px, py)에서 카메라로부터 depth 스터드 떨어진 3D 점."""
    eye, target = np.array(cam["eye"], float), np.array(cam["target"], float)
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    t = math.tan(math.radians(cam["fov"]) / 2)
    d = f + ((px / size) * 2 - 1) * t * r + (1 - (py / size) * 2) * t * u
    return eye + d / np.linalg.norm(d) * depth


def fit_camera(yaw, elev, fov, top_y, base_y, center_x, top=20.9):
    """나무 꼭대기(top)·밑동(0)이 화면 top_y·base_y(0~1)에 오도록 거리·바라보는 높이를 찾음.
    elev = 밑동에서 카메라를 올려다본 각(도, 클수록 땅의 마법진이 둥글게 보임). center_x 로 좌우 이동."""
    best = None
    for dist in np.linspace(15, 90, 301):
        height = dist * math.tan(math.radians(elev))
        for ty in np.linspace(0, 20, 201):
            cam = cam_at(yaw, height, dist, ty, fov, 0)
            y0 = project(cam, (0, 0, 0))[1] / S
            y1 = project(cam, (0, top, 0))[1] / S
            err = (y0 - base_y) ** 2 + (y1 - top_y) ** 2
            if best is None or err < best[0]:
                best = (err, dist, ty)
    _, dist, ty = best
    height = dist * math.tan(math.radians(elev))
    # 좌우: 바라보는 점을 옆으로 옮겨 나무가 center_x 에 오게
    shift = 0.0
    for _ in range(30):
        cam = cam_at(yaw, height, dist, ty, fov, shift)
        x = project(cam, (0, 10, 0))[0] / S
        shift += (x - center_x) * dist * 0.8
    return cam_at(yaw, height, dist, ty, fov, shift)


def cam_at(yaw, height, dist, ty, fov, shift):
    a = math.radians(yaw)
    fwd = np.array([math.sin(a), 0, math.cos(a)])  # 카메라가 바라보는 쪽(수평)
    side = np.array([-math.cos(a), 0, math.sin(a)])  # 화면 오른쪽
    eye = -fwd * dist + np.array([0, height, 0])
    target = np.array([0, ty, 0]) + side * shift
    eye = eye + side * shift
    return {"eye": eye.round(4).tolist(), "target": target.round(4).tolist(), "fov": fov}


# 3D 장면 ---------------------------------------------------------------------------------------
def without_base(parts: list) -> list:
    """전시용 받침(바닥 원판 + 얇은 빛 고리)은 빼고 나무만: 장면에서는 땅(마법진)에서 바로 자라게."""
    out = []
    for p in parts:
        flat_disc = p["s"] == "PartType.Cylinder" and p["z"][0] <= 0.3 and p["p"][1] < 0.5
        if not flat_disc:
            out.append(p)
    return out


def root_tips(parts: list) -> list:
    """밑동에서 비스듬히 뻗은 뿌리 막대(판자처럼 보임)의 땅 쪽 끝 — 바위로 덮을 자리."""
    tips = []
    for p in parts:
        if not str(p["s"]).endswith("Block") or p["p"][1] > 3:
            continue
        k = int(np.argmax(p["z"]))
        m = p["m"]
        axis = np.array([m[k], m[3 + k], m[6 + k]])
        if p["z"][k] < 2 or abs(axis[1]) < 0.1 or abs(axis[1]) > 0.95:
            continue
        ends = [np.array(p["p"]) + axis * p["z"][k] / 2, np.array(p["p"]) - axis * p["z"][k] / 2]
        tips.append(min(ends, key=lambda e: e[1]))
    return tips


def fruit_points(parts: list) -> list:
    return [p["p"] for p in parts if "Neon" in str(p["mat"]) and "Ball" in str(p["s"])]


def ground_textures(v, work: Path):
    """땅에 눕힐 그림(위에서 본 모습): 마법진 몸(두꺼움)·심(가늚), 금(어두운 테·빛 심), 소용돌이, 어두운 구덩이."""
    fx.magic_circle(2048, seed=v["seed"], width=v["circle_w"]).save(work / "circle_body.png")
    fx.magic_circle(2048, seed=v["seed"], width=v["circle_w"] * 0.3).save(work / "circle_core.png")
    dark, core = fx.cracks(2048, seed=v["seed"] + 1, count=v["crack_count"], inner=0.14, reach=(0.86, 1.0),
                           width=v["crack_w"])
    dark.save(work / "cracks_dark.png")
    core.save(work / "cracks_core.png")
    fx.vortex(1024, center=(4, 22, 20), swirl=(60, 220, 160), seed=v["seed"], edge=0.92).save(work / "vortex.png")
    fx.radial((512, 512), (256, 256), 256, [(0, (6, 30, 22, 255)), (0.7, (6, 30, 22, 245)), (0.88, (6, 30, 22, 150)),
                                            (1, (6, 30, 22, 0))]).save(work / "crater.png")


def build_scene(v, tree, work: Path):
    rnd = random.Random(v["seed"])
    cam = v["camera"]
    ground_textures(v, work)
    ground = [{"c": "Part", "s": "PartType.Block", "p": [0, -0.705, 0], "m": [1, 0, 0, 0, 1, 0, 0, 0, 1],
               "z": [8000, 2, 8000], "col": v["grass"], "t": 0, "mat": "Material.Grass"}]
    body = without_base(tree)
    # 둥그렇게 둘러싼 각진 바위(앞쪽 가운데는 비워서 마법진이 보이게) + 뿌리 끝 바위
    rocks = []
    yaw = math.radians(v["yaw"])
    fwd = np.array([math.sin(yaw), 0, math.cos(yaw)])  # 카메라가 바라보는 쪽
    side = np.array([-math.cos(yaw), 0, math.sin(yaw)])  # 화면 오른쪽
    for i, (ang, r, s) in enumerate(v["rocks"]):
        pa = math.radians(ang)  # 0 = 카메라 쪽(앞), 양수 = 화면 오른쪽
        pos = -fwd * math.cos(pa) * r + side * math.sin(pa) * r
        h = s * (0.6 + rnd.random() * 0.35)
        rocks.append({"p": [pos[0], h * 0.42, pos[2]], "size": [s * (1 + rnd.random() * 0.4), h, s],
                      "rot": [rnd.uniform(-8, 8), rnd.uniform(0, 360), rnd.uniform(-10, 10)],
                      "col": [c * rnd.uniform(0.85, 1.1) for c in v["rock"]], "mat": "Slate", "seed": 11 + i * 7 + v["seed"]})
    for i, tip in enumerate(root_tips(body)):
        s = rnd.uniform(1.9, 2.4)
        out = tip * np.array([1, 0, 1])
        p = tip + out / max(np.linalg.norm(out), 1e-6) * 0.25
        rocks.append({"p": [p[0], s * 0.32, p[2]], "size": [s * 1.3, s * 0.95, s * 1.15],
                      "rot": [rnd.uniform(-10, 10), rnd.uniform(0, 360), rnd.uniform(-10, 10)],
                      "col": [c * rnd.uniform(0.85, 1.05) for c in v["rock"]], "mat": "Slate", "seed": 900 + i})
    # 날아오르는 깨진 결정(한쪽이 뾰족한 조각): 나무 둘레 껍질 모양, 나무 가운데에서 바깥을 향함
    shards, debris = [], []
    center = np.array([0, 11, 0])
    placed = []
    for i in range(v["shards"]):
        for _ in range(80):
            az = rnd.uniform(0, math.tau)
            el = rnd.uniform(-0.15, 0.95)
            dist = rnd.uniform(8, 17)
            p = center + np.array([math.cos(az) * math.cos(el), math.sin(el) * 1.1, math.sin(az) * math.cos(el)]) * dist
            px, py = project(cam, p)
            if abs(px - v["tree_x"] * S) < 170 and py > 150:  # 나무 앞은 비움
                continue
            if py < v["shard_top"] or py > 900 or px < 30 or px > S - 30:  # 숫자 띠 아래부터
                continue
            if px > 600 and py > 560:  # 오른쪽 아래 = 손·주사위 자리
                continue
            if px > 740 and py < 480 and rnd.random() < 0.75:  # 숫자 끝 "0" 아래는 성기게
                continue
            if any(math.hypot(px - qx, py - qy) < v.get("shard_gap", 70) for qx, qy in placed):  # 너무 뭉치지 않게
                continue
            break
        placed.append((px, py))
        out = p - center
        out = out / np.linalg.norm(out) + np.array([rnd.uniform(-0.7, 0.7), rnd.uniform(-0.4, 0.7), rnd.uniform(-0.7, 0.7)])
        big = rnd.random() < 0.3
        L = (rnd.uniform(2.6, 3.6) if big else rnd.uniform(1.5, 2.4)) * v.get("shard_scale", 1.0)
        item = {"p": p.round(3).tolist(), "len": L, "radius": L * rnd.uniform(0.3, 0.38), "flat": rnd.uniform(0.75, 1.0),
                "rot": st_outward(out, rnd.uniform(0, 360)), "seed": 100 + i, "shape": "chunk", "rough": 0.3}
        if rnd.random() < v["debris_ratio"]:
            debris.append({"p": item["p"], "size": [L * 0.5, L * 0.4, L * 0.45], "rot": [rnd.uniform(0, 360)] * 3,
                           "col": v["rock"], "mat": "Slate", "seed": 300 + i})
        else:
            item["col"] = rnd.choice(v["shard_cols"])
            shards.append(item)
    eye = np.array(cam["eye"])
    for j, (px, py, L) in enumerate(v["near_shards"]):
        depth = np.linalg.norm(eye - np.array([0, 10, 0])) * rnd.uniform(0.45, 0.6)
        q = unproject(cam, px, py, depth)
        out = q - center
        shards.append({"p": q.round(3).tolist(), "len": L, "radius": L * 0.34, "flat": 0.9, "seed": 500 + j,
                       "shape": "chunk", "rot": st_outward(out, rnd.uniform(0, 360)), "col": v["shard_cols"][j % 2]})
    # 에너지 띠: 줄기를 감고 올라가는 나선(가운데가 굵고 양끝이 가는 띠)
    ribbons = []
    for turns, r0, r1, y0, y1, phase, wmax in v["ribbons"]:
        pts, w, al = [], [], []
        n = 160
        for j in range(n):
            t = j / (n - 1)
            th = phase + t * turns * math.tau
            r = r0 + (r1 - r0) * t
            pts.append([math.cos(th) * r, y0 + (y1 - y0) * t, math.sin(th) * r])
            env = math.sin(math.pi * t)
            w.append(0.05 + wmax * env ** 0.7)
            al.append(min(1, 1.3 * env ** 0.5))
        ribbons.append({"points": pts, "width": w, "alpha": al, "color": [1, 1, 1]})
    f = "/file" + str(work)
    quad = lambda name, y, d, rot=0: [{"image": f"{f}/{name}.png", "p": [0, y, 0], "size": [d, d], "rotY": rot}]  # noqa: E731
    sun = (-fwd * 0.55 - side * 0.5 + np.array([0, 0.85, 0])).tolist()
    rim_l = (fwd * 0.8 - side * 0.7 + np.array([0, 0.35, 0])).tolist()
    rim_r = (fwd * 0.8 + side * 0.7 + np.array([0, 0.35, 0])).tolist()
    return {
        "size": [R3, R3],
        "camera": cam,
        "light": {"sun": sun, "sunColor": [1, 0.97, 0.9], "sunIntensity": 1.05, "hemiSky": [0.8, 0.95, 1],
                  "hemiGround": [0.4, 0.55, 0.45], "hemiIntensity": 0.7,
                  "rims": [{"dir": rim_l, "color": list(np.array(fx.MINT) / 255), "intensity": 0.6},
                           {"dir": rim_r, "color": list(np.array(fx.MINT) / 255), "intensity": 0.5}],
                  "shadowCenter": [0, 6, 0], "shadowBox": 28},
        "rim": {"color": list(np.array(fx.MINT) / 255), "power": 2.6, "strength": v["rim"]},
        "objects": [
            {"tag": "ground", "parts": ground},
            {"tag": "tree", "rim": True, "parts": body},
            {"tag": "rocks", "rocks": rocks, "rim": 0.2},
            {"tag": "shards", "rim": v["shard_rim"], "shards": shards},
            {"tag": "debris", "rocks": debris, "castShadow": False},
            {"tag": "ribbons", "ribbons": ribbons},
            {"tag": "circle", "quads": quad("circle_body", 0.34, v["circle"], v["seed"] * 7)},
            {"tag": "circlecore", "quads": quad("circle_core", 0.345, v["circle"], v["seed"] * 7)},
            {"tag": "crater", "quads": quad("crater", 0.3, v["crater"])},
            {"tag": "vortex", "quads": quad("vortex", 0.305, v["crater"] * 0.8)},
            {"tag": "cracksdark", "quads": quad("cracks_dark", 0.31, v["cracks"])},
            {"tag": "crackscore", "quads": quad("cracks_core", 0.32, v["cracks"])},
        ],
        "layers": [
            {"name": "ground", "draw": ["ground"], "shadow": ["tree", "rocks"]},
            {"name": "crater", "draw": ["crater"], "occlude": ["tree", "rocks"]},
            {"name": "vortex", "draw": ["vortex"], "occlude": ["tree", "rocks"]},
            {"name": "cracksdark", "draw": ["cracksdark"], "occlude": ["tree", "rocks"]},
            {"name": "crackscore", "draw": ["crackscore"], "occlude": ["tree", "rocks"]},
            {"name": "circle", "draw": ["circle"], "occlude": ["tree", "rocks"]},
            {"name": "circlecore", "draw": ["circlecore"], "occlude": ["tree", "rocks"]},
            {"name": "tree", "draw": ["tree"], "occlude": ["rocks"]},
            {"name": "rocks", "draw": ["rocks"], "occlude": ["tree"]},
            {"name": "shards", "draw": ["shards", "debris"], "occlude": ["tree", "rocks"]},
            {"name": "ribbons", "draw": ["ribbons"], "occlude": ["tree", "rocks"]},
        ],
    }


def st_outward(direction, spin):
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    return [math.degrees(math.acos(max(-1.0, min(1.0, d[1])))), math.degrees(math.atan2(d[0], d[2])), spin]


def render_layers(scene, work: Path) -> dict:
    (work / "scene.json").write_text(json.dumps(scene))
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, NODE_PATH=npm_root)
    subprocess.run(["node", str(ROOT / "tools/store/render3d.js"), str(work / "scene.json"), str(work / "layers")],
                   check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    layers = {}
    for layer in scene["layers"]:
        im = Image.open(work / "layers" / f"{layer['name']}.png").convert("RGBA")
        layers[layer["name"]] = im.convert("RGBa").resize((S, S), Image.Resampling.LANCZOS).convert("RGBA")
    return layers


# 오른쪽 아래 놀란 아바타(썸네일과 같은 블록 아바타 + 큰 표정 그림) — 나무 쪽(왼쪽 위)을 보며 두 팔 번쩍 ------------------
def shocked_avatar(px: int) -> Image.Image:
    import stage as st

    pose = {"head": (-8, -8), "arm_r": (176, 36), "arm_l": (176, 36), "face": "shock"}
    base = np.array([0.0, 0.0, 0.0])
    yaw = st.yaw_facing((-0.3, 1.0))  # 몸은 카메라(+Z) 쪽에서 조금 왼쪽(나무 쪽)으로
    parts = st.to3d(st.avatar("Avatar", base, yaw, pose))
    face = [st.face_decal(base, yaw, pose)]
    cam = {"eye": [0.8, 5.3, 9.8], "target": [0.0, 4.55, 0], "fov": 30}
    scene = {"size": [1024, 1024], "camera": cam,
             "light": {"sun": [-0.6, 0.8, 0.5], "sunColor": [1, 0.97, 0.9], "sunIntensity": 1.0, "hemiSky": [0.8, 0.95, 1],
                       "hemiGround": [0.4, 0.55, 0.45], "hemiIntensity": 0.8,
                       "rims": [{"dir": [-0.8, 0.4, -0.5], "color": list(np.array(fx.MINT) / 255), "intensity": 0.7}],
                       "shadowCenter": [0, 4, 0], "shadowBox": 8},
             "rim": {"color": list(np.array(fx.MINT) / 255), "power": 2.6, "strength": 0.3},
             "objects": [{"tag": "avatar", "parts": parts, "castShadow": True, "rim": 0.3},
                         {"tag": "face", "decals": face}],
             "layers": [{"name": "avatar", "draw": ["avatar", "face"]}]}
    path = st.render3d(scene)["avatar"]
    return Image.open(path).convert("RGBa").resize((px, px), Image.Resampling.LANCZOS).convert("RGBA")


# 합성 ---------------------------------------------------------------------------------------------
def edge_light(layer: Image.Image, color, shift=(6, 0), strength=1.0, blur=1.5) -> Image.Image:
    """빛 쪽 가장자리만 밝게(테두리 빛): shift 만큼 옮긴 알파 밖으로 나온 부분."""
    a = fx.alpha_of(layer)
    moved = np.roll(np.roll(a, shift[1], 0), shift[0], 1)
    rim = fx.blur_alpha(np.clip(a - moved, 0, 1), blur) * a
    return fx.solid(layer.size, color, np.clip(rim * strength, 0, 1))


def deepen_canopy(layer: Image.Image, emerald=(14, 96, 60)) -> Image.Image:
    """잎(초록 공)의 그늘 쪽을 짙은 에메랄드로: 밝은 쪽은 그대로, 어두운 쪽은 더 어둡고 푸르게."""
    a = fx.arr(layer)
    rgb = a[..., :3]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    green = np.clip((rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2]) - 0.08) / 0.12, 0, 1)
    dark = (1 - np.clip((lum - 0.35) / 0.35, 0, 1)) * green
    em = np.array(emerald, np.float32) / 255
    rgb = rgb * (1 - 0.5 * dark[..., None]) + em * (0.35 * dark[..., None])
    a[..., :3] = rgb
    return fx.img(a)


def compose(v, L: dict, label: str, fruits: list) -> Image.Image:
    cam = v["camera"]
    P = lambda p: project(cam, p)  # noqa: E731
    cx, cy = P((0, 14.5, 0))  # 잎 가운데
    bx, by = P((0, 0.3, 0))  # 밑동
    tx, ty = P((0, 20.9, 0))  # 꼭대기
    hy = P((math.sin(math.radians(v["yaw"])) * 1e5, 0, math.cos(math.radians(v["yaw"])) * 1e5))[1]  # 지평선
    glow_c, aura = v["glow"], v["aura"]

    # 1) 하늘 + 색 빛(덮기 — 하얗게 날아가지 않게) + 햇살(초록빛)
    im = fx.linear((S, S), v["sky"])
    im = fx.over(im, fx.radial((S, S), (cx, cy), 600, [(0, glow_c + (225,)), (0.35, glow_c + (150,)),
                                                     (0.75, glow_c + (40,)), (1, glow_c + (0,))]))
    im = fx.add(im, fx.rays((S, S), (cx, cy), count=24, color=(215, 250, 255), width=0.42, seed=v["seed"], falloff=1.0,
                            inner=50), 0.4)
    im = fx.over(im, fx.rays((S, S), (cx, cy), count=12, color=glow_c, width=0.55, seed=v["seed"] + 9, falloff=0.8),
                 opacity=0.4)
    # 2) 먼 구름(오른쪽만 — 왼쪽 바위 뒤는 비워 둠)
    rnd = random.Random(v["seed"] + 3)
    for x, w, dy in v["clouds"]:
        c = fx.cloud(w, seed=rnd.randrange(1000), bottom=v["cloud_shade"])
        im = fx.over(im, c, (x, hy - c.height + dy), opacity=0.95)
    # 3) 땅(먼 곳은 조금 흐리게) + 집중선
    g = fx.arr(L["ground"])
    ys = np.arange(S, dtype=np.float32)[:, None]
    haze = np.clip(1 - (ys - hy) / 150, 0, 1) ** 1.8 * v["haze_k"]
    hz = np.array(v["haze"], np.float32) / 255
    g[..., :3] = g[..., :3] * (1 - haze[..., None]) + hz * haze[..., None]
    im = fx.over(im, fx.img(g))
    pool = v["pool"]  # 구덩이 둘레 땅을 어둡게(밝은 연두 바닥이 숫자·잎과 겹치지 않게)
    im = fx.over(im, fx.radial((S, S), (bx, by - 20), 520, [(0, pool + (200,)), (0.55, pool + (120,)), (1, pool + (0,))],
                               squash=0.45))
    if v.get("hill"):  # 둥근 언덕: 하늘과 땅이 만나는 곧은 선을 가림(위는 둥글게, 아래는 땅으로 스며듦) + 윗선 민트 빛
        top_col, rim_col = v["hill"]
        ys3, xs3 = np.mgrid[0:S, 0:S].astype(np.float32)
        hill_top = hy - 70 + ((xs3 - bx) / (S * 0.75)) ** 2 * 160  # 나무 밑에서 가장 높은 둥근 선
        a = np.clip((ys3 - hill_top) / 3, 0, 1) * np.clip(1 - (ys3 - hill_top - 60) / 160, 0, 1)
        im = fx.over(im, fx.solid((S, S), top_col, a * 0.95))
        rim = np.clip(1 - np.abs(ys3 - hill_top - 2) / 4, 0, 1)
        im = fx.add(im, fx.glow(rim, 6, rim_col, 1.2), 0.5)
    lines = fx.speed_lines((S, S), (cx, cy + 40), count=70, color=v["lines"], inner=0.55, seed=v["seed"] + 5,
                           thickness=0.009, alpha=v["lines_alpha"])
    im = fx.over(im, fx.multiply_alpha(lines, np.clip((hy - ys) / 40, 0, 1)))  # 하늘에만(땅에 줄무늬 없게)
    # 4) 빛 기둥(초록) + 잎 뒤 큰 별빛
    ys2, xs2 = np.mgrid[0:S, 0:S].astype(np.float32)
    half = 80 * (0.5 + 0.5 * np.clip((ys2 - ty) / max(1, by - ty), 0, 1))
    beam = np.clip(1 - np.abs(xs2 - bx) / half, 0, 1) ** 1.6 * np.clip((by - ys2) / 60, 0, 1)
    beam *= np.clip(1 - (by - ys2) / (by - ty + 200), 0, 1) ** 0.6
    im = fx.over(im, fx.solid((S, S), glow_c, beam * 0.55))
    fl = fx.sparkle_sprite(v["flare"], color=(235, 255, 240), glow_color=glow_c, pinch=3.4, aspect=1.35)
    im = fx.add(im, fl, 0.6, (cx - fl.width / 2, cy - 60 - fl.height / 2))
    # 5) 땅: 어두운 구덩이(불투명) + 소용돌이 + 금(어두운 테 + 민트 빛 + 흰 심) + 마법진(민트 몸 + 흰 심 + 빛)
    im = fx.over(im, L["crater"])
    im = fx.over(im, L["vortex"], opacity=0.85)
    im = fx.over(im, fx.solid((S, S), (6, 24, 18), fx.alpha_of(L["cracksdark"]) * 0.95))
    core = fx.alpha_of(L["crackscore"])
    im = fx.add(im, fx.glow(core, 7, fx.MINT, 1.8), 0.9)
    im = fx.over(im, fx.solid((S, S), (170, 255, 235), np.clip(core * 1.5, 0, 1)))
    im = fx.add(im, fx.solid((S, S), (255, 255, 255), np.clip(core * 2 - 1, 0, 1)), 0.7)
    cb, cc = fx.alpha_of(L["circle"]), fx.alpha_of(L["circlecore"])
    im = fx.add(im, fx.glow(cb, 9, fx.MINT, 1.2), 0.7)
    im = fx.over(im, fx.solid((S, S), fx.MINT, np.clip(cb * 1.25, 0, 1)))
    im = fx.over(im, fx.solid((S, S), (245, 255, 252), np.clip(cc * 1.2, 0, 1)))
    # 6) 먹물 불꽃(뒤, 짙은 대비)
    if v.get("ink", 1.0):  # 짙은 먹물 연기는 작은 크기에서 얼룩처럼 보여 기본으로 뺌(ink=0)
        ink = fx.ink_flames((S, S), (bx, by - 20), (tx, ty + 60), 150, seed=v["seed"], threshold=0.53, scale=34) * v["ink"]
        im = fx.over(im, fx.solid((S, S), (4, 28, 20), ink * 0.9))
        im = fx.add(im, fx.solid((S, S), (40, 230, 130), np.clip(fx.blur_alpha(ink, 3) - ink * 0.9, 0, 1)), 0.7)
    # 7) 나무: 바깥 빛 + 잎 그늘 에메랄드 + 민트 테두리 + 열매 빛
    tree = deepen_canopy(L["tree"])
    if v.get("canopy_sat"):  # 잎을 더 진한 초록으로(채도)
        tarr = fx.arr(tree)
        gray = tarr[..., :3].mean(-1, keepdims=True)
        tarr[..., :3] = np.clip(gray + (tarr[..., :3] - gray) * v["canopy_sat"], 0, 1)
        tree = fx.img(tarr)
    ta = fx.alpha_of(tree)
    im = fx.add(im, fx.glow(ta, 40, aura, 1.2, spread=10), 0.6)
    im = fx.over(im, fx.glow(ta, 12, aura, 1.2, spread=4))
    im = fx.over(im, tree)
    im = fx.add(im, edge_light(tree, fx.MINT, (-7, 4), 1.2, 1.5), 0.9)
    im = fx.add(im, edge_light(tree, fx.MINT, (7, 4), 1.2, 1.5), 0.9)
    if v.get("gold_rim"):  # 따뜻한 금빛 테두리(위쪽)
        im = fx.add(im, edge_light(tree, (255, 206, 90), (0, -6), 1.2, 1.6), v["gold_rim"])
    im = fx.add(im, fx.radial((S, S), (bx, by - 14), 150, [(0, (220, 255, 245, 255)), (0.35, fx.MINT + (200,)),
                                                          (1, fx.MINT + (0,))], squash=0.42), 0.95)
    for fp in fruits:
        x, y = P(fp)
        fr = v.get("fruit_r", 34)
        im = fx.add(im, fx.radial((S, S), (x, y), fr, [(0, (255, 255, 235, 255)), (0.3, (255, 225, 120, 230)),
                                                       (1, (255, 190, 70, 0))]), 1.0)
    # 8) 바위: 발밑 그림자 + 본체 + 잔금 + 윗 테두리 민트
    ra = fx.alpha_of(L["rocks"])
    sh = fx.blur_alpha(np.roll(fx.dilate(ra, 5), 8, axis=0), 9)
    im = fx.over(im, fx.solid((S, S), (4, 16, 14), np.clip(sh * (1 - ra) * 0.7, 0, 1)))
    im = fx.over(im, L["rocks"])
    cr = fx.crack_lines((S, S), 420, seed=v["seed"], length=(10, 34), width=1.8) * fx.erode(ra, 3)
    im = fx.over(im, fx.solid((S, S), (14, 16, 30), np.clip(cr * 0.9, 0, 1)))
    im = fx.add(im, edge_light(L["rocks"], fx.MINT, (0, -5), 0.9, 1.2), 0.6)
    # 9) 결정: 민트 번짐 + 본체 + 빛나는 면 선
    sl = L["shards"]
    im = fx.add(im, fx.glow(sl, 10, aura, 1.2, spread=2), 0.7)
    im = fx.over(im, sl)
    e = fx.facet_edges(sl, 0.05, 0.08)
    im = fx.add(im, fx.glow(e, 3, fx.MINT, 1.2), 0.7)
    im = fx.over(im, fx.solid((S, S), (190, 255, 240), e * 0.85))
    # 10) 에너지 띠: 민트 몸 + 흰 심 + 번짐
    ra2 = np.clip(fx.alpha_of(L["ribbons"]) * 1.3, 0, 1)
    im = fx.add(im, fx.glow(ra2, 14, fx.MINT, 1.4, spread=2), 0.7)
    im = fx.over(im, fx.solid((S, S), (110, 250, 215), ra2 * 0.95))
    corew = np.clip((fx.blur_alpha(fx.erode(ra2, 4), 1.5) - 0.2) / 0.5, 0, 1)
    im = fx.over(im, fx.solid((S, S), (255, 255, 255), corew))
    # 11) 반짝이 + 빛 알갱이 + 가장자리 어둡게
    im = fx.over(im, fx.particles((S, S), (cx, cy), 60, (1.5, 4.0), color=(220, 255, 240), seed=v["seed"] + 7,
                                  spread=(0.06, 0.5)))
    for x, y, r in v["sparkles"]:
        sp = fx.sparkle_sprite(r, glow_color=fx.MINT, rot=0)
        im = fx.over(im, sp, (x - sp.width / 2, y - sp.height / 2))
    im = fx.over(im, fx.vignette((S, S), v["lines"], strength=v["vignette"], inner=0.5, center=(cx, cy + 60)))
    # 12) 확률 숫자: 기울임 + 좁은 자간 + 위쪽 밝은 띠 + 글자에 겹친 반짝이
    text = fx.chunky_text(label, v["font"], size=220, gloss=0.3, tracking=v.get("text_tracking", -12),
                          fill_stops=v.get("text_fill"), outline=v.get("text_outline"),
                          outline_color=v.get("text_outline_color", fx.INK))
    ta2 = fx.arr(text)
    hh = ta2.shape[0]
    band = np.clip(1 - np.abs(np.arange(hh, dtype=np.float32) / hh - 0.3) / 0.07, 0, 1)[:, None]
    inner = fx.erode(fx.alpha_of(text), 18)
    ta2[..., :3] = ta2[..., :3] + (1 - ta2[..., :3]) * (band * inner * 0.55)[..., None]
    text = fx.rotate(fx.img(ta2), v["text_rot"])
    tw = v["text_w"]
    text = text.resize((tw, int(text.height * tw / text.width * v["text_stretch"])), Image.Resampling.LANCZOS)
    tx0, ty0 = (S - tw) / 2 + v.get("text_dx", 0), v["text_y"]
    sh = np.zeros((S, S), np.float32)
    sh_small = fx.alpha_of(text)
    y0i, x0i = int(ty0 + 10), int(tx0 + 6)
    h_, w_ = min(sh_small.shape[0], S - y0i), min(sh_small.shape[1], S - x0i)
    sh[y0i:y0i + h_, x0i:x0i + w_] = sh_small[:h_, :w_]
    im = fx.over(im, fx.solid((S, S), (0, 20, 12), fx.blur_alpha(sh, 8) * 0.5))
    im = fx.over(im, text, (tx0, ty0))
    for x, y, r in v["text_sparkles"]:
        sp = fx.sparkle_sprite(r, glow_color=(255, 255, 200))
        im = fx.over(im, sp, (x - sp.width / 2, y - sp.height / 2))
    # 13) 놀란 아바타(3D, 오른쪽 아래) + 부드러운 그림자 + 나무 쪽 테두리 빛
    hd = shocked_avatar(v["hand_px"])
    hx, hy2 = v["hand_xy"]
    shd = fx.solid(hd.size, (4, 20, 24), fx.blur_alpha(np.pad(fx.alpha_of(hd), 0), 16) * 0.5)
    im = fx.over(im, shd, (hx + 12, hy2 + 18))
    im = fx.over(im, hd, (hx, hy2))
    im = fx.add(im, edge_light(hd, fx.MINT, (-5, -4), 1.0, 1.2), 0.7, (hx, hy2))
    # 14) 마무리: 채도·대비
    rgb = im.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(v.get("saturation", 1.1))
    rgb = ImageEnhance.Contrast(rgb).enhance(1.05)
    return rgb


# 변형 --------------------------------------------------------------------------------------------
BASE = dict(
    seed=7, yaw=-20, elev=20, fov=60, top_y=0.15, base_y=1.0, tree_x=0.4,  # 잎 꼭대기가 숫자 띠 바로 아래, 밑동은 아래 끝
    grass=[0.2, 0.52, 0.3], rim=0.35, flare=150,
    shard_cols=[[0.19, 0.46, 0.37], [0.15, 0.39, 0.32], [0.24, 0.53, 0.42], [0.12, 0.33, 0.28]],
    shard_rim=0.8, shard_top=290,
    near_shards=[(40, 560, 1.5)],
    # 바위: (각도 0=앞·양수=오른쪽, 거리, 크기)
    rocks=[(-58, 10.5, 4.2), (-36, 12.0, 3.0), (-84, 10.0, 3.8), (-118, 9.5, 3.0), (46, 11, 3.6), (68, 10, 4.4),
           (96, 9.5, 3.4), (130, 9.5, 3.0), (-160, 10, 2.8), (168, 10, 3.0), (22, 13.0, 2.0), (-16, 13.5, 1.8)],
    # 에너지 띠: (감는 수, 시작 반지름, 끝 반지름, 시작 높이, 끝 높이, 시작 각, 최대 폭)
    ribbons=[(1.25, 5.0, 2.8, 0.6, 12.5, 0.3, 0.8), (1.05, 5.6, 3.4, 2.0, 14.0, 3.3, 0.65),
             (0.85, 6.2, 4.2, 0.4, 8.0, 5.0, 0.5)],
    circle=25, circle_w=3.6, crater=21, cracks=30, crack_count=8, crack_w=3.0, vignette=0.55,
    sky=[(0, (8, 58, 150)), (0.35, (20, 120, 210)), (0.6, (60, 200, 225)), (1, (140, 240, 235))],
    glow=(120, 225, 255), aura=(120, 255, 235), pool=(4, 34, 30), haze=(120, 200, 190), haze_k=0.3, cloud_shade=(150, 200, 235),
    lines=(4, 20, 60), lines_alpha=0.45,
    clouds=[(760, 250, 8), (900, 190, 12)],
    sparkles=[(150, 420, 30), (800, 360, 38), (90, 600, 20), (640, 300, 16), (330, 330, 18), (560, 520, 14)],
    # 숫자: 폭 930(가운데 91%), 세로 2.1배, 거의 수평(1도) — 150px 에서 0 과 쉼표가 뭉개지지 않게. 반짝이는 숫자 양 끝 밖에만
    font="luckiest", text_w=930, text_stretch=2.1, text_y=40, text_rot=1.0,
    text_sparkles=[(40, 262, 24), (990, 250, 18)],
    hand_px=470, hand_xy=(590, 575), saturation=1.1,
    # 검토 반영: 숫자 흰색→노랑 + 두꺼운 어두운 테 + 넓은 자간(쉼표가 보이게), 둥근 언덕, 진한 잎 + 금빛 테 + 큰 열매 빛,
    # 밝은 바위, 적고 큰 결정
    text_fill=[(0, (255, 255, 255)), (0.45, (255, 246, 160)), (1, (255, 196, 40))], text_outline=34,
    text_outline_color=(12, 22, 44), text_tracking=6,
    hill=((22, 92, 64), (120, 255, 235)), canopy_sat=1.35, gold_rim=0.7, fruit_r=44, ink=0.0,
    rock=[0.44, 0.48, 0.58], shards=12, shard_scale=1.45, shard_gap=120, debris_ratio=0.08,
)

VARIANTS = {
    # A: 카메라를 조금 높여 땅의 마법진·금이 더 보임 + 밝은 낮 하늘(하늘색)
    "a": dict(BASE, seed=7, elev=26, base_y=0.97, top_y=0.15, fov=56, circle=21, crater=17, cracks=26,
              sky=[(0, (40, 128, 232)), (0.5, (110, 190, 250)), (1, (200, 236, 255))],
              lines=(18, 44, 110), lines_alpha=0.35, cloud_shade=(186, 220, 250), haze=(200, 245, 245), haze_k=0.5,
              grass=[0.4, 0.74, 0.24]),
    # B: 짙은 청록 하늘에 초록 빛이 더 강함 — icon.png
    "b": dict(BASE, seed=13, clouds=[]),
}


# 지구본 아이콘(A/B 시험용 icon_globe.png): 게임의 핵심 = 지구본을 돌려 명소 뽑기. 광장 지구본에서 잘 알려진 명소 셋이
# 등급 색 꼬리를 달고 튀어나옴 + 위쪽 같은 확률 숫자(게임에서 가장 희귀한 세계수 1/10,000,000,000). 모형은 진짜 빌더
GLOBE_BURST = [  # (명소, 화면 x, 화면 y(모형 가운데), 화면 키(px), 좌우 돌림, 기울임) — 1024 칸 기준
    ("eiffel", 215, 520, 330, -16, -12),
    ("pyramid", 512, 470, 190, 28, 0),
    ("liberty", 815, 530, 330, 26, 12),
]


def globe_icon(label: str) -> Image.Image:
    import stage as st
    import thumbs as th

    size = S * 2
    origin = np.array([3000.0, 60.0, 0.0])
    cam = st.Camera(origin + np.array([0, 0, 100.0]), origin, 45, (size, size))

    def at(sx, sy, depth):  # 1024 칸 화면 점 → 깊이 depth 의 3D 점
        x, y = sx / S * 2 - 1, 1 - sy / S * 2
        return cam.eye + cam.f * depth + cam.r * (x * cam.t * depth) + cam.u * (y * cam.t * depth)

    ids = [b[0] for b in GLOBE_BURST]
    ratio = th.model_heights(ids)
    models, placed = [], {}
    for (lid, sx, sy, hpx, yaw, roll) in GLOBE_BURST:
        depth = 100
        msize = hpx / (ratio[lid] * cam.scale_at(depth, (S, S)))
        R = st.rz(roll) @ st.rx(10) @ st.ry(yaw) @ st.ry(180)
        h = ratio[lid] * msize
        pivot = at(sx, sy, depth) - R @ np.array([0, h / 2, 0])
        models.append({"folder": f"L_{lid}", "id": lid, "size": msize, "cf": st.cf(pivot, R), "dropBase": True})
        placed[lid] = (sx, sy, hpx)
    gsize = 46
    gdepth = 84
    gc = at(512, 1075, gdepth)
    R = st.rx(-16) @ st.ry(160)
    models.append({"folder": "Globe", "id": "Globe", "size": gsize, "cf": st.cf(gc - R @ np.array([0, gsize / 2, 0]), R)})
    layers = [{"name": "globe", "terrain": False, "include": ["Store/Globe"]}]
    layers += [{"name": f"L_{lid}", "terrain": False, "include": [f"Store/L_{lid}"]} for lid in ids]
    L = st.render_layers({"models": models}, cam, layers, size=(size, size), players=0)
    lay = {k: Image.open(v).convert("RGBa").resize((S, S), Image.Resampling.LANCZOS).convert("RGBA") for k, v in L.items()}
    gp = cam.project([gc], (S, S))[0]
    gr = gsize / 2 * cam.scale_at(gp[2], (S, S))
    gx, gy = gp[0], gp[1]
    src = (gx, gy - gr * 0.8)

    # 배경: 가운데 밝은 하늘색 → 가장자리 짙은 파랑 + 햇살 + 집중선
    im = fx.radial((S, S), (512, 560), 760, [(0, (150, 235, 255)), (0.35, (70, 170, 245)), (0.75, (24, 90, 200)),
                                               (1, (12, 40, 130))])
    im = fx.add(im, fx.rays((S, S), src, count=22, color=(210, 245, 255), width=0.45, seed=61, falloff=0.8, inner=gr * 0.5),
                0.35)
    im = fx.over(im, fx.speed_lines((S, S), src, count=60, color=(10, 30, 90), inner=0.62, seed=7, thickness=0.008,
                                    alpha=0.4))
    # 꼬리: 지구본 꼭대기 → 명소(등급 색 + 흰 심)
    for lid, (sx, sy, hpx) in placed.items():
        col = th.tier(lid)[2]
        dx, dy = sx - src[0], sy - src[1]
        start, end = (src[0] + dx * 0.1, src[1] + dy * 0.1), (sx - dx * 0.12, sy - dy * 0.12)
        a, t = th_streak((S, S), start, end, 6, hpx * 0.28)
        body = a * np.clip(t * 1.4, 0, 1) ** 0.8
        im = fx.add(im, fx.glow(body, 12, col, 1.5), 0.8)
        im = fx.over(im, fx.solid((S, S), col, np.clip(body * 0.95, 0, 1)))
        core, _ = th_streak((S, S), start, end, 2, hpx * 0.07)
        im = fx.over(im, fx.solid((S, S), (255, 255, 255), np.clip(fx.blur_alpha(core * t ** 1.3, 1.2), 0, 1)))
        im = fx.add(im, fx.radial((S, S), (sx, sy), hpx * 0.8, [(0, col + (200,)), (0.5, col + (80,)), (1, col + (0,))]), 0.8)
    # 지구본: 빛 + 도는 호 + 본체 + 테두리
    im = fx.add(im, fx.radial((S, S), (gx, gy), gr * 1.5, [(0, (200, 250, 255, 230)), (0.6, (120, 230, 255, 120)),
                                                            (1, (120, 220, 255, 0))]), 0.9)
    arcs = np.zeros((S, S), np.float32)
    from PIL import ImageDraw

    arc_im = Image.new("L", (S * 2, S * 2), 0)
    d = ImageDraw.Draw(arc_im)
    for (rr, a0, a1, wdt) in [(1.08, 200, 262, 12), (1.16, 282, 340, 10), (1.24, 212, 240, 7), (1.26, 300, 322, 6)]:
        r = gr * rr * 2
        d.arc((gx * 2 - r, gy * 2 - r, gx * 2 + r, gy * 2 + r), a0, a1, fill=255, width=int(wdt * 2))
    arcs = np.asarray(arc_im.resize((S, S), Image.Resampling.LANCZOS), np.float32) / 255
    im = fx.add(im, fx.glow(arcs, 8, (140, 230, 255), 1.4), 1.0)
    im = fx.over(im, fx.solid((S, S), (255, 255, 255), arcs))
    im = fx.add(im, fx.glow(lay["globe"], 18, (160, 240, 255), 1.3, spread=4), 0.8)
    im = fx.over(im, lay["globe"])
    im = fx.add(im, edge_light(lay["globe"], (210, 250, 255), (0, 8), 1.2, 2), 0.8)
    # 명소: 등급 색 번짐 + 얇은 테 + 본체 + 흰 테두리
    for lid in placed:
        col = th.tier(lid)[2]
        layer = lay[f"L_{lid}"]
        la = fx.alpha_of(layer)
        im = fx.add(im, fx.glow(la, 14, col, 1.6, spread=5), 1.0)
        im = fx.over(im, fx.solid((S, S), tuple(int(c * 0.6) for c in col), np.clip(fx.dilate(la, 3) - la, 0, 1)))
        im = fx.over(im, layer)
        im = fx.add(im, edge_light(layer, (255, 255, 255), (-5, 3), 1.2, 1.2), 0.7)
        im = fx.add(im, edge_light(layer, (255, 255, 255), (5, 3), 1.2, 1.2), 0.7)
    for x, y, r in [(90, 360, 30), (940, 380, 26), (380, 330, 18), (660, 320, 20), (120, 720, 22), (900, 740, 24)]:
        sp = fx.sparkle_sprite(r, glow_color=(150, 235, 255), rot=0)
        im = fx.over(im, sp, (x - sp.width / 2, y - sp.height / 2))
    im = fx.over(im, fx.particles((S, S), src, 70, (1.5, 4.0), color=(255, 255, 255), seed=12, spread=(0.08, 0.5),
                                  glow_color=(150, 235, 255)))
    im = fx.over(im, fx.vignette((S, S), (8, 24, 80), strength=0.5, inner=0.55))
    # 숫자: 나무 아이콘과 같은 모양(흰색→노랑, 두꺼운 어두운 테, 세로로 늘임)
    v = BASE
    text = fx.chunky_text(label, v["font"], size=220, gloss=0.3, tracking=v["text_tracking"], fill_stops=v["text_fill"],
                          outline=v["text_outline"], outline_color=v["text_outline_color"])
    text = fx.rotate(text, v["text_rot"])
    tw = v["text_w"]
    text = text.resize((tw, int(text.height * tw / text.width * v["text_stretch"])), Image.Resampling.LANCZOS)
    tx0, ty0 = (S - tw) / 2, v["text_y"]
    sh = np.zeros((S, S), np.float32)
    ta = fx.alpha_of(text)
    sh[int(ty0 + 10):int(ty0 + 10) + ta.shape[0], int(tx0 + 6):int(tx0 + 6) + ta.shape[1]] = ta[:S - int(ty0 + 10), :S - int(tx0 + 6)]
    im = fx.over(im, fx.solid((S, S), (0, 10, 40), fx.blur_alpha(sh, 8) * 0.5))
    im = fx.over(im, text, (tx0, ty0))
    rgb = im.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(1.1)
    return ImageEnhance.Contrast(rgb).enhance(1.05)


def th_streak(size, p0, p1, w0, w1):
    """thumbs.streak 과 같은 꼬리 모양(정사각 그림용)."""
    from PIL import ImageDraw

    s = 2
    Lm = Image.new("L", (size[0] * s, size[1] * s), 0)
    d = ImageDraw.Draw(Lm)
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln, dx / ln
    pts = [(x0 + nx * w0, y0 + ny * w0), (x1 + nx * w1, y1 + ny * w1), (x1 - nx * w1, y1 - ny * w1), (x0 - nx * w0, y0 - ny * w0)]
    d.polygon([(x * s, y * s) for x, y in pts], fill=255)
    d.ellipse(((x1 - w1) * s, (y1 - w1) * s, (x1 + w1) * s, (y1 + w1) * s), fill=255)
    a = np.asarray(Lm.resize(size, Image.Resampling.LANCZOS), np.float32) / 255
    ys, xs = np.mgrid[0:size[1], 0:size[0]].astype(np.float32)
    t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / (ln * ln), 0, 1)
    return a, t


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = [a for a in sys.argv[1:] if a in VARIANTS] if sys.argv[1:] else list(VARIANTS)
    label = rarity_label(one_in(LANDMARK))
    tree = model_parts(LANDMARK)
    fruits = fruit_points(tree)
    keep = os.environ.get("KEEP")
    made = {}
    for name in wanted:
        v = dict(VARIANTS[name])
        v["camera"] = fit_camera(v["yaw"], v["elev"], v["fov"], v["top_y"], v["base_y"], v["tree_x"])
        work = Path(tempfile.mkdtemp(prefix=f"icon_{name}_"))
        try:
            layers = render_layers(build_scene(v, tree, work), work)
            icon = compose(v, layers, label, fruits).resize((512, 512), Image.Resampling.LANCZOS)
            path = OUT / f"icon_{name}.png"
            icon.save(path, optimize=True)
            made[name] = icon
            print(f"[icon] {path} ({label}, 카메라 {v['camera']})")
            if keep:
                dst = OUT / "_work" / name
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(work / "layers", dst)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    if not sys.argv[1:] or "globe" in sys.argv[1:]:
        icon = globe_icon(label).resize((512, 512), Image.Resampling.LANCZOS)
        icon.save(OUT / "icon_globe.png", optimize=True)
        print(f"[icon] {OUT / 'icon_globe.png'} (지구본 + 명소 셋, A/B 시험용)")
    if not sys.argv[1:]:
        pick = os.environ.get("PICK", "b")
        made[pick].save(OUT / "icon.png", optimize=True)
        made[pick].resize((150, 150), Image.Resampling.LANCZOS).save(OUT / "icon_small.png", optimize=True)
        print(f"[icon] icon.png = icon_{pick}.png, icon_small.png (150px)")


if __name__ == "__main__":
    main()
