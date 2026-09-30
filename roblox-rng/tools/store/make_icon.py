#!/usr/bin/env python3
"""게임 아이콘(512x512) — 세계수(1/40,000,000, 전설 등급)가 빛을 뿜는 장면 + 위쪽 큰 확률 숫자 + 오른쪽 아래 주사위 쥔 손.

    python3 tools/store/make_icon.py            # art/store/icon_a.png, icon_b.png, icon.png(고른 것), icon_small.png(150px)
    python3 tools/store/make_icon.py a          # 한 변형만(icon.png 는 안 바꿈)
    KEEP=1 python3 tools/store/make_icon.py     # 중간 레이어를 art/store/_work/ 에 남김(점검용, 커밋하지 않음)

만드는 법
  1) 진짜 명소 빌더(src/shared/Models)로 세계수 파트를 덤프(tools/model_preview/mock.luau, 업로드·API 없음)
  2) tools/store/render3d.js 로 같은 카메라의 3D 층(땅, 금, 마법진, 모형, 결정 조각, 에너지 띠 ...)을 투명 PNG 로
  3) fx.py 로 합성: 하늘 + 햇살 + 오라 + 빛 기둥 + 마법진 빛 + 반짝이 + 확률 숫자 + 손·주사위(SVG, 게임 스티커 그림체)
숫자는 Landmarks.luau 의 세계수 OneIn(40000000)을 읽어서 게임처럼 콤마로 씀.
Roblox 가 모서리를 둥글게 자르므로 중요한 것은 가운데 88% 안에 둠.
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


def fit_camera(yaw, height, fov, top_y, base_y, center_x, top=20.9):
    """나무 꼭대기(top)·밑동(0)이 화면 top_y·base_y(0~1)에 오도록 거리·바라보는 높이를 찾음. center_x 로 좌우 이동."""
    best = None
    for dist in np.linspace(20, 80, 241):
        for ty in np.linspace(2, 18, 161):
            cam = cam_at(yaw, height, dist, ty, fov, 0)
            y0 = project(cam, (0, 0, 0))[1] / S
            y1 = project(cam, (0, top, 0))[1] / S
            err = (y0 - base_y) ** 2 + (y1 - top_y) ** 2
            if best is None or err < best[0]:
                best = (err, dist, ty)
    _, dist, ty = best
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
def build_scene(v, tree, work: Path):
    rnd = random.Random(v["seed"])
    cam = v["camera"]
    # 땅 무늬 그림(위에서 본 모습) → 3D 판
    circle = fx.magic_circle(2048, seed=v["seed"])
    circle.save(work / "circle_tex.png")
    dark, core = fx.cracks(2048, seed=v["seed"] + 1, count=13, inner=0.18, reach=(0.55, 1.0))
    dark.save(work / "cracks_dark.png")
    core.save(work / "cracks_core.png")
    ground = [{"c": "Part", "s": "PartType.Block", "p": [0, -0.705, 0], "m": [1, 0, 0, 0, 1, 0, 0, 0, 1],
               "z": [600, 2, 600], "col": v["grass"], "t": 0, "mat": "Material.Grass"}]
    # 둥그렇게 둘러싼 각진 바위(앞쪽 가운데는 비워서 마법진이 보이게)
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
                      "col": v["rock"], "mat": "Slate", "seed": 11 + i * 7 + v["seed"]})
    # 날아오르는 결정 조각·돌 부스러기: 나무 둘레 껍질 모양으로, 나무 가운데에서 바깥을 향함
    shards, debris = [], []
    center = np.array([0, 11, 0])
    for i in range(v["shards"]):
        for _ in range(50):
            az = rnd.uniform(0, math.tau)
            el = rnd.uniform(-0.15, 0.95)
            dist = rnd.uniform(8, 17)
            p = center + np.array([math.cos(az) * math.cos(el), math.sin(el) * 1.1, math.sin(az) * math.cos(el)]) * dist
            px, py = project(cam, p)
            # 화면 가운데 나무(캔버스 가운데 기둥)·숫자 띠 위·너무 바깥은 피함
            if abs(px - v["tree_x"] * S) < 150 and py > 180:
                continue
            if py < 200 or py > 880 or px < 20 or px > S - 20:
                continue
            break
        out = p - center
        out /= np.linalg.norm(out)
        # 조각의 긴 축(Y)을 바깥으로: rot 를 대략 맞춤(YXZ 오일러)
        yaw_d = math.degrees(math.atan2(out[0], out[2]))
        pitch = math.degrees(math.acos(max(-1, min(1, out[1]))))
        big = rnd.random() < 0.3
        L = rnd.uniform(2.6, 4.2) if big else rnd.uniform(1.2, 2.4)
        item = {"p": p.round(3).tolist(), "len": L, "radius": L * rnd.uniform(0.2, 0.3),
                "rot": [pitch, yaw_d, rnd.uniform(-20, 20)], "seed": 100 + i, "sides": rnd.choice([4, 5, 6])}
        if rnd.random() < v["debris_ratio"]:
            debris.append({"p": item["p"], "size": [L * 0.6, L * 0.45, L * 0.55], "rot": [rnd.uniform(0, 360)] * 3,
                           "col": v["rock"], "mat": "Slate", "seed": 300 + i})
        else:
            item["col"] = rnd.choice(v["shard_cols"])
            shards.append(item)
    # 에너지 띠: 나무를 감고 올라가는 나선 두 줄
    ribbons = []
    for k, (turns, r0, r1, y0, y1, phase, wmax) in enumerate(v["ribbons"]):
        pts, w, al = [], [], []
        n = 140
        for j in range(n):
            t = j / (n - 1)
            th = phase + t * turns * math.tau
            r = r0 + (r1 - r0) * t
            pts.append([math.cos(th) * r, y0 + (y1 - y0) * t, math.sin(th) * r])
            env = math.sin(math.pi * t)
            w.append(0.15 + wmax * env ** 0.8)
            al.append(min(1, 1.3 * env ** 0.6))
        ribbons.append({"points": pts, "width": w, "alpha": al, "color": [0.8, 1, 0.96]})
    quads_circle = [{"image": "/file" + str(work / "circle_tex.png"), "p": [0, 0.33, 0], "size": [v["circle"]] * 2,
                     "rotY": v["seed"] * 7}]
    quads_dark = [{"image": "/file" + str(work / "cracks_dark.png"), "p": [0, 0.31, 0], "size": [v["cracks"]] * 2}]
    quads_core = [{"image": "/file" + str(work / "cracks_core.png"), "p": [0, 0.32, 0], "size": [v["cracks"]] * 2}]
    fwd = np.array([math.sin(yaw), 0, math.cos(yaw)])
    side = np.array([-math.cos(yaw), 0, math.sin(yaw)])
    sun = (-fwd * 0.55 - side * 0.5 + np.array([0, 0.85, 0])).tolist()
    rim_l = (fwd * 0.8 - side * 0.7 + np.array([0, 0.35, 0])).tolist()
    rim_r = (fwd * 0.8 + side * 0.7 + np.array([0, 0.35, 0])).tolist()
    return {
        "size": [R3, R3],
        "camera": cam,
        "light": {"sun": sun, "sunColor": [1, 0.97, 0.9], "sunIntensity": 1.05, "hemiSky": [0.8, 0.95, 1],
                  "hemiGround": [0.5, 0.65, 0.5], "hemiIntensity": 0.8,
                  "rims": [{"dir": rim_l, "color": list(np.array(fx.MINT) / 255), "intensity": 1.3},
                           {"dir": rim_r, "color": list(np.array(fx.MINT) / 255), "intensity": 1.1}],
                  "shadowCenter": [0, 6, 0], "shadowBox": 28},
        "rim": {"color": list(np.array(fx.MINT) / 255), "power": 2.6, "strength": v["rim"]},
        "objects": [
            {"tag": "ground", "parts": ground},
            {"tag": "tree", "rim": True, "parts": tree},
            {"tag": "rocks", "rim": True, "rocks": rocks},
            {"tag": "shards", "rim": True, "shards": shards},
            {"tag": "debris", "rim": True, "rocks": debris, "castShadow": False},
            {"tag": "ribbons", "ribbons": ribbons},
            {"tag": "circle", "quads": quads_circle},
            {"tag": "cracksdark", "quads": quads_dark},
            {"tag": "crackscore", "quads": quads_core},
        ],
        "layers": [
            {"name": "ground", "draw": ["ground"], "shadow": ["tree", "rocks"]},
            {"name": "cracksdark", "draw": ["cracksdark"], "occlude": ["tree", "rocks"]},
            {"name": "crackscore", "draw": ["crackscore"], "occlude": ["tree", "rocks"]},
            {"name": "model", "draw": ["tree", "rocks"]},
            {"name": "tree", "draw": ["tree"]},
            {"name": "circle", "draw": ["circle"], "occlude": ["tree", "rocks"]},
            {"name": "shards", "draw": ["shards", "debris"], "occlude": ["tree", "rocks"]},
            {"name": "ribbons", "draw": ["ribbons"], "occlude": ["tree", "rocks"]},
        ],
    }


def render_layers(scene, work: Path) -> dict:
    (work / "scene.json").write_text(json.dumps(scene))
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, NODE_PATH=npm_root)
    subprocess.run(["node", str(ROOT / "tools/store/render3d.js"), str(work / "scene.json"), str(work / "layers")],
                   check=True, env=env, cwd=ROOT, stdout=subprocess.DEVNULL)
    layers = {}
    for layer in scene["layers"]:
        im = Image.open(work / "layers" / f"{layer['name']}.png").convert("RGBA")
        layers[layer["name"]] = im.resize((S, S), Image.Resampling.LANCZOS)
    return layers


# 손 + 주사위(게임 스티커 그림체: Ink 테두리, 아래 두께, 평면 색 + 그늘 + 하이라이트) -------------------------------
INK_HEX = "#1E1B2E"


def hand_dice_svg(skin="#FFD1A3", shade="#E9A273", light="#FFE9D3") -> str:
    """400x400. 주사위(게임 dice.svg 와 같은 흰 정육면체, 윗면 산호색 1) 를 오른쪽 아래에서 쥔 만화 손."""
    fingers = [((112, 40), (64, 52), 17), ((104, 84), (42, 70), 18), ((88, 122), (18, 86), 18)]
    thumb = ((30, 150), (-62, 82), 21)
    arm = ((100, 150), (270, 320), 56)
    palm = (80, 128, 66, 56, 35)
    hexpts = "0,-100 89,-50 89,50 0,100 -89,50 -89,-50"

    def cap(p, q, r, fill, extra=0.0, dx=0.0, dy=0.0):
        return (f'<line x1="{p[0] + dx}" y1="{p[1] + dy}" x2="{q[0] + dx}" y2="{q[1] + dy}" stroke="{fill}" '
                f'stroke-width="{2 * r + 2 * extra}" stroke-linecap="round"/>')

    def ell(fill, extra=0.0, dx=0.0, dy=0.0):
        cx, cy, rx, ry, rot = palm
        return (f'<ellipse cx="{cx + dx}" cy="{cy + dy}" rx="{rx + extra}" ry="{ry + extra}" '
                f'transform="rotate({rot} {cx + dx} {cy + dy})" fill="{fill}"/>')

    def silhouette(extra, dy=0):
        s = [f'<polygon points="{hexpts}" fill="{INK_HEX}" stroke="{INK_HEX}" stroke-width="{2 * extra + 14}" '
             f'stroke-linejoin="round" transform="translate(0,{dy})"/>',
             cap(arm[0], arm[1], arm[2], INK_HEX, extra, 0, dy), ell(INK_HEX, extra, 0, dy)]
        s += [cap(p, q, r, INK_HEX, extra, 0, dy) for p, q, r in fingers]
        s.append(cap(thumb[0], thumb[1], thumb[2], INK_HEX, extra, 0, dy))
        return "\n".join(s)

    def finger(p, q, r):
        hx, hy = p[0] * 0.35 + q[0] * 0.65, p[1] * 0.35 + q[1] * 0.65
        ux, uy = (q[0] - p[0]) * 0.12, (q[1] - p[1]) * 0.12
        return "\n".join([
            cap(p, q, r, INK_HEX, 6), cap(p, q, r, shade), cap(p, q, r - 5, skin, 0, -3, -4),
            cap((hx - ux - 2, hy - r * 0.45 - uy), (hx + ux - 2, hy - r * 0.45 + uy), 3.2, light),
        ])

    dice = f"""
<polygon points="0,0 89,-50 89,50 0,100" fill="#B9B3D1" stroke="#B9B3D1" stroke-width="14" stroke-linejoin="round"/>
<polygon points="-89,-50 0,0 0,100 -89,50" fill="#E3DFF0" stroke="#E3DFF0" stroke-width="14" stroke-linejoin="round"/>
<polygon points="0,-100 89,-50 0,0 -89,-50" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="14" stroke-linejoin="round"/>
<path d="M-89,-48 L0,2 L89,-48 M0,2 V98" fill="none" stroke="#8F88AE" stroke-width="5" stroke-linecap="round"/>
<g transform="matrix(44.7,24.7,-44.7,24.7,0,-50)"><circle r="0.36" fill="#FF5E5B"/></g>
<g transform="matrix(44.7,24.7,0,50.6,-44.7,24.7)" fill="{INK_HEX}"><circle cx="-0.48" cy="-0.5" r="0.2"/><circle cx="0.48" cy="0.5" r="0.2"/></g>
<g transform="matrix(44.7,-24.7,0,50.6,44.7,24.7)" fill="{INK_HEX}"><circle cx="-0.52" cy="-0.52" r="0.2"/><circle r="0.2"/><circle cx="0.52" cy="0.52" r="0.2"/></g>
<path d="M-70,-52 L-52,-62" stroke="#FFFFFF" stroke-width="0" />"""
    body = [silhouette(12, 9), silhouette(12, 0),
            "\n".join([cap(arm[0], arm[1], arm[2], INK_HEX, 6), cap(arm[0], arm[1], arm[2], shade),
                       cap(arm[0], arm[1], arm[2] - 6, skin, 0, -4, -5)]),
            "\n".join([ell(INK_HEX, 6), ell(shade), ell(skin, -6, -4, -5)]),
            dice]
    body += [finger(*f) for f in fingers]
    body.append(finger(*thumb))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">\n'
            '<g transform="translate(165,160) rotate(-12)">\n' + "\n".join(body) + "\n</g></svg>")


def hand_dice(px: int) -> Image.Image:
    import resvg_py

    png = bytes(resvg_py.svg_to_bytes(svg_string=hand_dice_svg(), width=px * 2, height=px * 2))
    return Image.open(io.BytesIO(png)).convert("RGBA").resize((px, px), Image.Resampling.LANCZOS)


# 합성 ---------------------------------------------------------------------------------------------
def compose(v, L: dict, label: str) -> Image.Image:
    cam = v["camera"]
    P = lambda p: project(cam, p)  # noqa: E731
    cx, cy = P((0, 14.5, 0))  # 잎 가운데
    bx, by = P((0, 0.3, 0))  # 밑동
    tx, ty = P((0, 20.9, 0))  # 꼭대기
    hy = P((math.sin(math.radians(v["yaw"])) * 1e5, 0, math.cos(math.radians(v["yaw"])) * 1e5))[1]  # 지평선

    # 1) 하늘 + 큰 빛 + 햇살
    im = fx.linear((S, S), v["sky"])
    im = fx.add(im, fx.radial((S, S), (cx, cy), 620, [(0, (255, 255, 255, 255)), (0.25, v["glow"] + (200,)),
                                                    (0.6, v["glow"] + (70,)), (1, v["glow"] + (0,))]), 0.9)
    im = fx.add(im, fx.rays((S, S), (cx, cy), count=26, width=0.42, seed=v["seed"], falloff=1.1, inner=60), 0.55)
    im = fx.add(im, fx.rays((S, S), (cx, cy), count=14, color=v["glow"], width=0.6, seed=v["seed"] + 9, falloff=0.9),
                0.35)
    # 2) 지평선 구름
    rnd = random.Random(v["seed"] + 3)
    for x, w, dy in v["clouds"]:
        c = fx.cloud(w, seed=rnd.randrange(1000), bottom=v["cloud_shade"])
        im = fx.over(im, c, (x, hy - c.height + dy), opacity=0.95)
    # 3) 땅(먼 곳은 하늘빛으로 흐리게) + 집중선
    g = fx.arr(L["ground"])
    ys = np.arange(S, dtype=np.float32)[:, None]
    haze = np.clip(1 - (ys - hy) / 200, 0, 1) ** 1.6 * 0.75
    hz = np.array(v["haze"], np.float32) / 255
    g[..., :3] = g[..., :3] * (1 - haze[..., None]) + hz * haze[..., None]
    im = fx.over(im, fx.img(g))
    im = fx.over(im, fx.speed_lines((S, S), (cx, cy + 40), count=80, color=v["lines"], inner=0.5, seed=v["seed"] + 5,
                                    thickness=0.01, alpha=v["lines_alpha"]))
    # 4) 땅 갈라짐(어두운 금 + 빛나는 속)
    im = fx.over(im, fx.solid((S, S), (28, 40, 44), fx.alpha_of(L["cracksdark"]) * 0.9))
    core = fx.alpha_of(L["crackscore"])
    im = fx.add(im, fx.glow(core, 10, fx.MINT, 1.6), 0.9)
    im = fx.add(im, fx.solid((S, S), (225, 255, 250), core), 1.0)
    # 5) 빛 기둥 + 나무 뒤 오라
    ys2, xs2 = np.mgrid[0:S, 0:S].astype(np.float32)
    half = 120 * (0.55 + 0.45 * np.clip((ys2 - ty) / max(1, by - ty), 0, 1))
    beam = np.clip(1 - np.abs(xs2 - bx) / half, 0, 1) ** 1.8 * np.clip((by + 20 - ys2) / 120, 0, 1)
    beam *= np.clip(1 - (by - ys2) / (by - ty + 260), 0, 1) ** 0.7
    im = fx.add(im, fx.solid((S, S), (210, 255, 248), beam), 0.75)
    tree_a = fx.alpha_of(L["tree"])
    im = fx.add(im, fx.glow(tree_a, 70, v["aura"], 1.3, spread=16), 0.9)
    im = fx.add(im, fx.glow(tree_a, 22, (220, 255, 250), 1.4, spread=8), 0.9)
    # 6) 모형(나무 + 바위)
    im = fx.over(im, L["model"])
    # 7) 마법진(발 밑, 빛남)
    ca = fx.alpha_of(L["circle"])
    im = fx.add(im, fx.glow(ca, 26, fx.MINT, 2.2), 0.8)
    im = fx.add(im, fx.glow(ca, 6, fx.MINT, 1.8), 0.9)
    im = fx.add(im, fx.solid((S, S), (235, 255, 252), ca), 1.0)
    # 8) 결정 조각·부스러기 + 테두리 빛, 에너지 띠
    sa = fx.alpha_of(L["shards"])
    im = fx.add(im, fx.glow(sa, 14, fx.MINT, 1.0), 0.7)
    im = fx.over(im, L["shards"])
    ra = fx.alpha_of(L["ribbons"])
    im = fx.add(im, fx.glow(ra, 18, fx.MINT, 1.5), 0.8)
    im = fx.add(im, fx.solid((S, S), (235, 255, 250), ra), 0.95)
    # 9) 반짝이 + 빛 알갱이
    im = fx.over(im, fx.particles((S, S), (cx, cy), 70, (1.5, 4.5), seed=v["seed"] + 7, spread=(0.06, 0.55)))
    for x, y, r in v["sparkles"]:
        sp = fx.sparkle_sprite(r, glow_color=fx.MINT, rot=0)
        im = fx.over(im, sp, (x - sp.width / 2, y - sp.height / 2))
    # 10) 확률 숫자
    text = fx.chunky_text(label, v["font"], size=220, gloss=0.32)
    text = fx.rotate(text, v["text_rot"])
    tw = v["text_w"]
    text = text.resize((tw, int(text.height * tw / text.width)), Image.Resampling.LANCZOS)
    im = fx.over(im, text, ((S - tw) / 2 + v.get("text_dx", 0), v["text_y"]))
    for x, y, r in v["text_sparkles"]:
        sp = fx.sparkle_sprite(r, glow_color=(255, 255, 200))
        im = fx.over(im, sp, (x - sp.width / 2, y - sp.height / 2))
    # 11) 손 + 주사위(그림자 먼저)
    hd = hand_dice(v["hand_px"])
    hx, hy2 = v["hand_xy"]
    sh = fx.solid(hd.size, (10, 30, 40), fx.blur_alpha(hd, 14) * 0.45)
    im = fx.over(im, sh, (hx + 10, hy2 + 16))
    im = fx.over(im, hd, (hx, hy2))
    # 12) 마무리: 살짝 선명·채도
    rgb = im.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(v.get("saturation", 1.08))
    rgb = ImageEnhance.Contrast(rgb).enhance(1.04)
    return rgb


# 변형 --------------------------------------------------------------------------------------------
BASE = dict(
    seed=7, yaw=0, height=6.5, fov=34, top_y=0.2, base_y=0.845, tree_x=0.46,
    grass=[0.36, 0.76, 0.26], rock=[0.66, 0.68, 0.74], rim=0.7,
    shard_cols=[[0.08, 0.3, 0.36], [0.12, 0.42, 0.46], [0.3, 0.75, 0.72]], shards=34, debris_ratio=0.3,
    rocks=[(-62, 10.5, 3.6), (-40, 11.5, 2.6), (-88, 9.5, 3.2), (-120, 9.0, 2.4), (50, 11, 3.0), (72, 10, 3.8),
           (100, 9.5, 2.8), (135, 9, 2.4), (-160, 9.5, 2.2), (170, 9.5, 2.6), (25, 12.5, 1.6), (-22, 12.8, 1.5)],
    ribbons=[(1.35, 8.5, 3.5, 0.8, 21.5, 0.4, 1.1), (1.1, 7.5, 5.5, 3.0, 19.0, 3.6, 0.8)],
    circle=21, cracks=34,
    sky=[(0, (26, 118, 238)), (0.45, (66, 178, 255)), (0.7, (150, 226, 255)), (1, (190, 240, 255))],
    glow=(150, 255, 238), aura=fx.MINT, haze=(200, 245, 245), cloud_shade=(186, 220, 250),
    lines=(18, 44, 110), lines_alpha=0.55,
    clouds=[(-60, 330, 30), (180, 220, 34), (620, 260, 30), (820, 300, 28)],
    sparkles=[(180, 330, 34), (800, 300, 42), (140, 600, 22), (880, 520, 26), (300, 250, 16), (690, 420, 18),
              (250, 760, 16), (600, 230, 14)],
    font="luckiest", text_w=900, text_y=40, text_rot=3.5, text_sparkles=[(90, 70, 26), (960, 170, 18)],
    hand_px=520, hand_xy=(560, 560),
)

VARIANTS = {
    # A: 정면, 밝은 낮 하늘(참고 그림 느낌)
    "a": dict(BASE),
    # B: 3/4 각도·더 낮은 카메라, 짙은 청록 하늘에 빛이 더 강함
    "b": dict(BASE, seed=13, yaw=-32, height=4.2, fov=36, top_y=0.19, base_y=0.85, tree_x=0.45,
              sky=[(0, (8, 58, 150)), (0.4, (20, 120, 210)), (0.72, (60, 200, 225)), (1, (140, 240, 235))],
              glow=(130, 255, 235), haze=(150, 235, 230), cloud_shade=(150, 200, 235), lines=(4, 20, 60),
              lines_alpha=0.7, rim=1.0, text_rot=-3, grass=[0.3, 0.72, 0.3],
              text_sparkles=[(950, 60, 24), (70, 200, 18)]),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:] or list(VARIANTS)
    label = rarity_label(one_in(LANDMARK))
    tree = model_parts(LANDMARK)
    keep = os.environ.get("KEEP")
    made = {}
    for name in wanted:
        v = dict(VARIANTS[name])
        v["camera"] = fit_camera(v["yaw"], v["height"], v["fov"], v["top_y"], v["base_y"], v["tree_x"])
        work = Path(tempfile.mkdtemp(prefix=f"icon_{name}_"))
        try:
            layers = render_layers(build_scene(v, tree, work), work)
            icon = compose(v, layers, label).resize((512, 512), Image.Resampling.LANCZOS)
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
    if not sys.argv[1:]:
        pick = os.environ.get("PICK", "a")
        made[pick].save(OUT / "icon.png", optimize=True)
        made[pick].resize((150, 150), Image.Resampling.LANCZOS).save(OUT / "icon_small.png", optimize=True)
        print(f"[icon] icon.png = icon_{pick}.png, icon_small.png (150px)")


if __name__ == "__main__":
    main()
