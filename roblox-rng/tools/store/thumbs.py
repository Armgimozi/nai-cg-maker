#!/usr/bin/env python3
"""스토어 썸네일 4장(1920x1080 PNG) — 진짜 게임 그림(맵·명소 모형 3D 렌더) + 빛 효과 합성.

    python3 tools/store/thumbs.py            # art/store/thumb_1.png ~ thumb_4.png + thumbs_sheet.png
    python3 tools/store/thumbs.py 1 3        # 고른 것만

만드는 법
  1) 무대(stage.py): 진짜 맵(world.luau) 위에 게임 모형(Models.create)·바위·조각·블록 아바타를 올려 덤프
  2) 레이어(render_layers.js + world_preview/scene.js): 같은 카메라로 배경/주인공/아바타 ... 를 따로 투명 PNG 로
  3) 합성(fx.py): 하늘·구름 → 배경 → 햇살·오라 → 땅 마법진·금 → 뒤 조각·리본 → 주인공 → 앞 조각·리본·반짝이 → 아바타 → 글자
모든 이름·확률은 src/shared/Landmarks.luau 에서 읽음(게임에 있는 명소·숫자만, 쉼표 자연수 "1/40,000,000").
글꼴: Luckiest Guy(게임 UI 글꼴, mockup/fonts) + Noto Sans KR Black(한글, 처음 한 번 Google Fonts 에서 받아 cache/fonts 에).
"""
from __future__ import annotations

import math
import random
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fx  # noqa: E402
import stage as st  # noqa: E402

ROOT = st.ROOT
OUT = ROOT / "art/store"
W, H = 1920, 1080
SS = 2  # 3D 레이어는 2배로 그려서 줄임(가장자리 매끈)
INK = fx.INK
WHITE = fx.WHITE
MAX_BYTES = 3_000_000


# 게임 데이터 -------------------------------------------------------------------------------------
def _landmarks():
    text = (ROOT / "src/shared/Landmarks.luau").read_text()
    out = {}
    for m in re.finditer(r'\{\s*"(\w+)",\s*"([^"]+)",\s*"([^"]+)",\s*(\d+),', text):
        out[m.group(1)] = {"name": m.group(2), "en": m.group(3), "one_in": int(m.group(4))}
    tiers = []
    for m in re.finditer(r'Name = "([^"]+)", MinOneIn = (\d+), Color = Color3.fromRGB\((\d+), (\d+), (\d+)\)', text):
        tiers.append((int(m.group(2)), m.group(1), (int(m.group(3)), int(m.group(4)), int(m.group(5)))))
    return out, sorted(tiers)


LANDMARKS, TIERS = _landmarks()


def odds(lid: str) -> str:
    return f"1/{LANDMARKS[lid]['one_in']:,}"


def tier(lid: str):
    n = LANDMARKS[lid]["one_in"]
    best = TIERS[0]
    for t in TIERS:
        if n >= t[0]:
            best = t
    return best  # (MinOneIn, 이름, 색)


# 글꼴 ------------------------------------------------------------------------------------------
FONT_DIR = st.CACHE / "fonts"
_GF = {"NotoSansKR-Black.ttf": ("Noto+Sans+KR", 900)}


def font_path(name: str) -> str:
    if name == "luckiest":
        return "luckiest"
    path = FONT_DIR / name
    if not path.exists():
        family, weight = _GF[name]
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        ua = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/534.1 (KHTML, like Gecko)"  # 옛 브라우저 → TTF 주소를 줌
        css = subprocess.run(["curl", "-sS", "-A", ua, f"https://fonts.googleapis.com/css2?family={family}:wght@{weight}"],
                             capture_output=True, text=True, check=True).stdout
        url = re.search(r"url\((https://[^)]+\.ttf)\)", css).group(1)
        subprocess.run(["curl", "-sS", "-o", str(path), url], check=True)
    return str(path)


KR = "NotoSansKR-Black.ttf"


# 작은 도구 ------------------------------------------------------------------------------------------
def load_layer(path) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    if im.size != (W, H):
        im = im.convert("RGBa").resize((W, H), Image.Resampling.LANCZOS).convert("RGBA")
    return im


def shadow_only(with_catcher: Image.Image, without: Image.Image, strength=1.0) -> Image.Image:
    a = np.clip(fx.alpha_of(with_catcher) - fx.alpha_of(without) * 4, 0, 1) * strength
    return fx.solid((W, H), (20, 40, 30), a)


def lighten(c, k):
    return tuple(int(v + (255 - v) * k) for v in c[:3])


def darken(c, k):
    return tuple(int(v * (1 - k)) for v in c[:3])


def sky(stops, clouds=()):
    im = fx.linear((W, H), stops)
    for (x, y, width, seed, alpha) in clouds:
        c = fx.cloud(width, seed=seed, top=(255, 255, 255), bottom=(205, 228, 250))
        im = fx.over(im, c, (x - c.width / 2, y - c.height), alpha)
    return im


def ground_quad(cam: st.Camera, center, half):
    """땅(y=center.y)에 누운 한 변 2*half 정사각형의 화면 네 점(그림 위 = 카메라에서 먼 쪽)."""
    f = np.array([cam.f[0], 0, cam.f[2]])
    f /= np.linalg.norm(f)
    r = np.array([cam.r[0], 0, cam.r[2]])
    r /= np.linalg.norm(r)
    c = np.array(center, float)
    pts = [c + (-r + f) * half, c + (r + f) * half, c + (r - f) * half, c + (-r - f) * half]
    return [tuple(p[:2]) for p in cam.project(pts)]


def edge_light(layer: Image.Image, color, shift=(6, 0), strength=1.0, blur=1.5) -> Image.Image:
    """빛 쪽 가장자리만 밝게(림 라이트): shift 방향으로 옮긴 알파 밖으로 나온 부분."""
    a = fx.alpha_of(layer)
    dx, dy = shift
    moved = np.zeros_like(a)
    h, w = a.shape
    xs = slice(max(0, dx), w + min(0, dx))
    xd = slice(max(0, -dx), w + min(0, -dx))
    ys = slice(max(0, dy), h + min(0, dy))
    yd = slice(max(0, -dy), h + min(0, -dy))
    moved[yd, xd] = a[ys, xs]
    rim = np.clip(a - moved, 0, 1)
    rim = fx.blur_alpha(rim, blur) * a
    return fx.solid((W, H), color, np.clip(rim * strength, 0, 1))


def bloom(im: Image.Image, threshold=0.78, radius=26, strength=0.45) -> Image.Image:
    a = fx.arr(im)
    lum = a[..., :3].max(-1)
    m = np.clip((lum - threshold) / (1 - threshold), 0, 1)
    bright = np.concatenate([a[..., :3], m[..., None]], -1)
    b = fx.img(bright)
    glowed = fx.arr(b)
    blurred = np.stack([fx.blur_alpha(glowed[..., c] * glowed[..., 3], radius) for c in range(3)], -1)
    out = a.copy()
    out[..., :3] = 1 - (1 - out[..., :3]) * (1 - np.clip(blurred * strength * 1.6, 0, 1))
    return fx.img(out)


def grade(im: Image.Image, saturation=1.12, contrast=1.05, vignette=0.22) -> Image.Image:
    a = fx.arr(im)
    rgb = a[..., :3]
    gray = rgb.mean(-1, keepdims=True)
    rgb = gray + (rgb - gray) * saturation
    rgb = (rgb - 0.5) * contrast + 0.5
    if vignette:
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot((xs - W / 2) / (W / 2), (ys - H / 2) / (H / 2)) / math.sqrt(2)
        rgb *= (1 - vignette * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None]
    a[..., :3] = rgb
    return fx.img(a)


def mask_img(L: Image.Image) -> np.ndarray:
    return np.asarray(L.resize((W, H), Image.Resampling.LANCZOS), np.float32) / 255


def ribbons(cam: st.Camera, base, specs, seed=7):
    """주인공 축을 감아 오르는 빛 리본. 결과 (뒤 알파, 앞 알파) — 카메라 기준 축보다 멀면 뒤."""
    rnd = random.Random(seed)
    back = Image.new("L", (W * SS, H * SS), 0)
    front = Image.new("L", (W * SS, H * SS), 0)
    db, df = ImageDraw.Draw(back), ImageDraw.Draw(front)
    base = np.array(base, float)
    for spec in specs:
        n = 220
        t = np.linspace(0, 1, n)
        ang = spec["phase"] + t * spec["turns"] * math.tau
        rad = spec["r0"] + (spec["r1"] - spec["r0"]) * t
        y = spec["y0"] + (spec["y1"] - spec["y0"]) * t
        pts = np.stack([base[0] + np.cos(ang) * rad, base[1] + y, base[2] + np.sin(ang) * rad], 1)
        axis = np.stack([np.full(n, base[0]), base[1] + y, np.full(n, base[2])], 1)
        P = cam.project(pts, (W * SS, H * SS))
        A = cam.project(axis, (W * SS, H * SS))
        width = spec["width"] * SS * np.sin(np.pi * t) ** 0.8 * (0.8 + 0.2 * np.sin(t * 9 + rnd.random() * 6))
        for i in range(n - 1):
            p0, p1 = P[i, :2], P[i + 1, :2]
            d = p1 - p0
            ln = np.hypot(*d) or 1
            nx, ny = -d[1] / ln, d[0] / ln
            w0, w1 = width[i] / 2, width[i + 1] / 2
            quad = [(p0[0] + nx * w0, p0[1] + ny * w0), (p1[0] + nx * w1, p1[1] + ny * w1),
                    (p1[0] - nx * w1, p1[1] - ny * w1), (p0[0] - nx * w0, p0[1] - ny * w0)]
            is_front = P[i, 2] < A[i, 2]
            (df if is_front else db).polygon(quad, fill=int(255 * spec.get("alpha", 1)))
    return mask_img(back), mask_img(front)


def add_ribbon(im, a, color, core=(255, 255, 255)):
    im = fx.add(im, fx.glow(a, 22, color, 1.6), 0.9)
    im = fx.add(im, fx.glow(a, 5, color, 1.4), 0.9)
    return fx.add(im, fx.solid((W, H), core, a * 0.85), 1.0)


def scatter_sparkles(im, rects, count, seed, color=WHITE, glow_color=fx.MINT, rmin=8, rmax=46, big=()):
    rnd = random.Random(seed)
    for _ in range(count):
        x0, y0, x1, y1 = rnd.choice(rects)
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rmin + (rmax - rmin) * rnd.random() ** 2.2
        s = fx.sparkle_sprite(r, color, glow_color, rot=rnd.uniform(-0.15, 0.15))
        im = fx.over(im, s, (x - s.width / 2, y - s.height / 2))
    for (x, y, r) in big:
        s = fx.sparkle_sprite(r, color, glow_color)
        im = fx.over(im, s, (x - s.width / 2, y - s.height / 2))
    return im


def fitted_text(text, width, font="luckiest", **kw):
    probe = fx.chunky_text(text, font, 200, **kw)
    size = int(200 * width / probe.width)
    return fx.chunky_text(text, font, size, **kw)


def headline(im, text, stops, y=18, width=1760, outline_color=(12, 60, 20), tilt=0.0):
    t = fitted_text(text, width, "luckiest", fill_stops=stops, outline_color=outline_color,
                    depth_color=darken(outline_color, 0.45), gloss=0.35)
    if tilt:
        t = fx.rotate(t, tilt)
    sh = fx.solid(t.size, (0, 0, 0), fx.blur_alpha(t, 10) * 0.45)
    im = fx.over(im, sh, ((W - t.width) / 2 + 4, y + 12))
    return fx.over(im, t, ((W - t.width) / 2, y))


def caption_block(im, kr, en, xy, kr_size=118, en_size=64, align="left", kr_stops=None, en_stops=None,
                  outline=INK):
    """한글 큰 줄 + 영어 작은 줄(두꺼운 테 글자). xy = 블록 왼쪽 위(align=right 면 오른쪽 위)."""
    kr_stops = kr_stops or [(0, (255, 255, 255)), (0.6, (255, 250, 225)), (1, (255, 214, 120))]
    en_stops = en_stops or [(0, (255, 255, 255)), (1, (255, 240, 200))]
    k = fx.chunky_text(kr, font_path(KR), kr_size, fill_stops=kr_stops, outline_color=outline,
                       outline=int(kr_size * 0.12), inner=0, depth=int(kr_size * 0.07), gloss=0.0)
    e = fx.chunky_text(en, "luckiest", en_size, fill_stops=en_stops, outline_color=outline,
                       outline=int(en_size * 0.14), inner=0, depth=int(en_size * 0.08), gloss=0.0)
    x, y = xy
    for t, dy in ((k, 0), (e, k.height - int(kr_size * 0.1))):
        tx = x if align == "left" else (x - t.width if align == "right" else x - t.width / 2)
        sh = fx.solid(t.size, (0, 0, 0), fx.blur_alpha(t, 8) * 0.4)
        im = fx.over(im, sh, (tx + 3, y + dy + 8))
        im = fx.over(im, t, (tx, y + dy))
    return im


def save(im: Image.Image, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    rgb = im.convert("RGB")
    rgb.save(path, optimize=True)
    if path.stat().st_size > MAX_BYTES:  # 너무 크면 색 수를 줄인 PNG
        rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(
            path, optimize=True)
    print(f"[thumbs] {path} ({path.stat().st_size / 1e6:.2f} MB)")
    return path


# 무대 배치 ------------------------------------------------------------------------------------------
def hero_height(lid: str, size: float, yaw: float) -> float:
    """게임 모형을 size 로 만들었을 때 높이(덤프에서 잼)."""
    dump = st.world_dump({"models": [{"folder": "Hero", "id": lid, "size": size, "cf": st.cf((0, 0, 0), st.ry(yaw))}]},
                         players=0)
    import json

    parts = [p for p in json.loads(dump.read_text())["parts"] if p["path"].startswith("Store/Hero")]
    top = max(p["p"][1] + max(p["z"]) / 2 for p in parts if p["t"] < 0.99)
    return top


def frame_camera(hero, height, eye_h, fov, base_y, top_y, look):
    """주인공 바닥이 화면 base_y, 꼭대기가 top_y 에 오도록 거리와 겨냥 높이를 찾음(look = 카메라→주인공 수평 방향)."""
    look = np.array([look[0], 0, look[1]], float)
    look /= np.linalg.norm(look)
    best = None
    for D in np.arange(50, 260, 1.0):
        for th in np.arange(0, height * 1.2, 0.5):
            eye = hero - look * D + np.array([0, eye_h, 0])
            cam = st.Camera(eye, hero + np.array([0, th, 0]), fov, (W, H))
            p = cam.project([hero, hero + np.array([0, height, 0])])
            err = (p[0, 1] - base_y) ** 2 + (p[1, 1] - top_y) ** 2
            if best is None or err < best[0]:
                best = (err, D, th)
    _, D, th = best
    eye = hero - look * D + np.array([0, eye_h, 0])
    return st.Camera(eye, hero + np.array([0, th, 0]), fov, (W, H))


def ground_point(cam: st.Camera, sx: float, depth: float):
    """화면 x 가 sx 이고 카메라에서 depth 만큼 앞(수평)인 땅 위 점."""
    f = np.array([cam.f[0], 0, cam.f[2]])
    f /= np.linalg.norm(f)
    r = np.array([cam.r[0], 0, cam.r[2]])
    lateral = (sx / W * 2 - 1) * cam.t * (W / H) * depth
    p = cam.eye + f * depth + r * lateral
    p[1] = 0
    return p


# 1·2: 전설 명소 등장 -------------------------------------------------------------------------------
HEROES = {
    1: {
        "id": "worldtree",
        "angle": 337.5,  # 광장에서 본 방향(부지 사이 틈) — 해를 등지고 바다 쪽을 봄
        "radius": 214,
        "size": 26,
        "yaw": 20,
        "fov": 40,
        "eye_h": 2.6,
        "base_y": 900,
        "top_y": 250,
        "aura": (110, 255, 190),  # 전설 민트 + 세계수 초록
        "aura2": (120, 255, 235),
        "number": [(0, (240, 255, 130)), (0.45, (130, 245, 70)), (0.8, (40, 200, 60)), (1, (20, 150, 55))],
        "number_outline": (10, 58, 22),
        "shard_colors": [(40, 170, 140), (22, 110, 96), (90, 225, 190)],
        "earth": 0.35,
        "avatar": {"sx": 400, "depth": 17.0, "pose": {"head": (-26, 10), "arm_r": (150, 14), "arm_l": (8, 10),
                                                        "leg_l": 5, "leg_r": -5}},
        "sky": [(0, (60, 140, 235)), (0.55, (130, 195, 250)), (0.8, (200, 232, 255)), (1, (220, 240, 255))],
        "pill_side": "right",
    },
}


def hero_stage(cfg):
    lid = cfg["id"]
    ang = math.radians(cfg["angle"])
    u = np.array([math.cos(ang), 0, math.sin(ang)])
    hero = u * cfg["radius"]
    height = hero_height(lid, cfg["size"], cfg["yaw"])
    cam = frame_camera(hero, height, cfg["eye_h"], cfg["fov"], cfg["base_y"], cfg["top_y"], (u[0], u[2]))
    foot = cfg["size"] * 0.5
    parts = []
    parts += st.rock_ring(hero, foot * 1.05, 18, cfg["size"] * 0.17, seed=11, color=(150, 154, 162))
    parts += st.shards(hero, 34, (foot * 1.2, foot * 2.9), (3, height * 0.95), cfg["size"] * 0.085, 12,
                       cfg["shard_colors"], "ShardsFront", "ShardsBack", cam, earth=cfg["earth"])
    av = cfg["avatar"]
    av_base = ground_point(cam, av["sx"], av["depth"])
    to_hero = hero - av_base
    parts += st.avatar("Avatar", av_base, st.yaw_facing((to_hero[0], to_hero[2])), av["pose"])
    stage = {"models": [{"folder": "Hero", "id": lid, "size": cfg["size"],
                         "cf": st.cf(hero, st.ry(st.yaw_facing((-u[0], -u[2])) + cfg["yaw"]))}],
             "parts": parts}
    for p in stage["parts"]:
        if p["folder"] == "Rocks":
            p["mat"] = "SmoothPlastic"
    clear_until = float(np.dot(hero - cam.eye, cam.f)) + foot * 3
    layers = [
        {"name": "bg", "terrain": True, "exclude": ["Store"], "clear": {"until": clear_until, "margin": 1.35}},
        {"name": "hero", "terrain": False, "include": ["Store/Hero", "Store/Rocks"]},
        {"name": "hero_sh", "terrain": False, "include": ["Store/Hero", "Store/Rocks"],
         "shadow": {"x": hero[0], "y": 0.02, "z": hero[2], "size": 220, "opacity": 0.45}},
        {"name": "avatar", "terrain": False, "include": ["Store/Avatar"]},
        {"name": "avatar_sh", "terrain": False, "include": ["Store/Avatar"],
         "shadow": {"x": av_base[0], "y": 0.02, "z": av_base[2], "size": 40, "opacity": 0.45}},
        {"name": "sfront", "terrain": False, "include": ["Store/ShardsFront"]},
        {"name": "sback", "terrain": False, "include": ["Store/ShardsBack"]},
    ]
    L = st.render_layers(stage, cam, layers, size=(W * SS, H * SS))
    return cam, hero, height, av_base, L


def thumb_hero(n):
    cfg = HEROES[n]
    lid = cfg["id"]
    cam, hero, height, av_base, L = hero_stage(cfg)
    lay = {k: load_layer(v) for k, v in L.items()}
    aura, aura2 = cfg["aura"], cfg["aura2"]
    base_px = cam.project([hero])[0]
    core = cam.project([hero + np.array([0, height * 0.62, 0])])[0]
    top_px = cam.project([hero + np.array([0, height, 0])])[0]

    # 하늘 + 구름 + 배경(진짜 섬: 풀밭·바다)
    horizon = cam.project([cam.eye + np.array([cam.f[0], 0, cam.f[2]]) * 3000])[0][1]
    im = sky(cfg["sky"], clouds=[(150, horizon + 12, 520, 3, 1), (1780, horizon + 16, 560, 5, 1),
                                 (520, horizon - 40, 300, 8, 0.85), (1430, horizon - 70, 360, 9, 0.9),
                                 (-40, horizon - 260, 380, 10, 0.7), (1960, horizon - 300, 420, 13, 0.7)])
    im = fx.over(im, lay["bg"])

    # 뒤 빛: 큰 오라 + 햇살 두 겹
    im = fx.add(im, fx.radial((W, H), core[:2], 820, [(0, aura + (255,)), (0.35, aura + (140,)), (1, aura + (0,))]), 0.85)
    im = fx.add(im, fx.rays((W, H), core[:2], count=26, color=lighten(aura2, 0.5), width=0.42, seed=21, falloff=1.1,
                            inner=40), 0.75)
    im = fx.add(im, fx.rays((W, H), core[:2], count=14, color=WHITE, width=0.22, seed=22, falloff=1.6), 0.5)
    im = fx.add(im, fx.radial((W, H), core[:2], 330, [(0, (255, 255, 255, 230)), (0.5, aura + (90,)), (1, aura + (0,))]),
                0.8)

    # 땅: 빛 웅덩이 + 금 + 마법진
    foot = cfg["size"] * 0.5
    pool = fx.radial((W, H), base_px[:2], 520, [(0, aura + (220,)), (0.5, aura + (60,)), (1, aura + (0,))], squash=0.22)
    im = fx.add(im, pool, 0.8)
    dark, crack_core = fx.cracks(1600, seed=31, count=13, inner=0.18, reach=(0.55, 0.98))
    q = ground_quad(cam, hero, foot * 3.4)
    dark_w, core_w = fx.warp_quad(dark, q, (W, H)), fx.warp_quad(crack_core, q, (W, H))
    im = fx.over(im, fx.solid((W, H), (40, 60, 40), fx.alpha_of(dark_w) * 0.75))
    im = fx.add(im, fx.glow(core_w, 6, aura, 1.8), 1.0)
    im = fx.add(im, fx.solid((W, H), lighten(aura, 0.6), fx.alpha_of(core_w)), 1.0)
    circle = fx.warp_quad(fx.magic_circle(2048, WHITE, seed=5, width=1.3), ground_quad(cam, hero, foot * 2.5), (W, H))
    ca = fx.alpha_of(circle)
    im = fx.add(im, fx.glow(ca, 14, aura, 1.6), 1.0)
    im = fx.add(im, fx.glow(ca, 4, aura2, 1.2), 1.0)
    im = fx.add(im, fx.solid((W, H), lighten(aura2, 0.7), ca), 1.0)
    # 주인공 그림자(마법진 위라 옅게)
    im = fx.over(im, shadow_only(lay["hero_sh"], lay["hero"], 0.6))

    # 리본(뒤) + 조각(뒤)
    rib = [
        {"phase": 0.3, "turns": 1.35, "r0": foot * 2.6, "r1": foot * 1.3, "y0": 1, "y1": height * 0.8, "width": 16},
        {"phase": 2.6, "turns": 1.2, "r0": foot * 2.2, "r1": foot * 1.7, "y0": 3, "y1": height * 0.55, "width": 11},
        {"phase": 4.4, "turns": 1.0, "r0": foot * 3.2, "r1": foot * 2.0, "y0": 0.5, "y1": height * 0.35, "width": 9,
         "alpha": 0.8},
    ]
    rb, rf = ribbons(cam, hero, rib)
    im = add_ribbon(im, rb, aura)
    im = fx.add(im, fx.glow(lay["sback"], 12, aura, 1.5, spread=2), 0.9)
    im = fx.over(im, lay["sback"])
    im = fx.add(im, edge_light(lay["sback"], lighten(aura2, 0.4), (4, 4), 1.4), 1.0)

    # 주인공: 바깥 빛 + 본체 + 빛 쪽 테두리
    im = fx.add(im, fx.glow(lay["hero"], 28, aura, 1.6, spread=6), 1.0)
    im = fx.add(im, fx.glow(lay["hero"], 8, lighten(aura2, 0.3), 1.2, spread=2), 0.9)
    im = fx.over(im, lay["hero"])
    im = fx.add(im, edge_light(lay["hero"], lighten(aura2, 0.35), (-7, 5), 1.2), 0.9)
    im = fx.add(im, edge_light(lay["hero"], lighten(aura2, 0.35), (7, 5), 1.2), 0.9)

    # 앞: 리본, 조각, 알갱이, 반짝이
    im = add_ribbon(im, rf, aura)
    im = fx.add(im, fx.glow(lay["sfront"], 14, aura, 1.6, spread=2), 0.9)
    im = fx.over(im, lay["sfront"])
    im = fx.add(im, edge_light(lay["sfront"], lighten(aura2, 0.4), (5, 5), 1.4), 1.0)
    im = fx.add(im, fx.particles((W, H), core[:2], 90, (1.5, 4.5), WHITE, seed=41, spread=(0.05, 0.42),
                                 glow_color=aura), 1.0)
    hx0, hx1 = top_px[0] - 520, top_px[0] + 520
    im = scatter_sparkles(im, [(hx0, top_px[1], hx1, base_px[1] - 40)], 26, seed=51, glow_color=aura, rmin=8, rmax=40,
                          big=[(top_px[0] - 330, top_px[1] + 140, 62), (top_px[0] + 360, core[1] + 60, 74),
                               (top_px[0] + 240, top_px[1] + 40, 40), (top_px[0] - 420, base_px[1] - 170, 46)])
    im = bloom(im, 0.82, 24, 0.35)

    # 아바타(맨 앞): 그림자 + 몸 + 주인공 쪽 테두리 빛
    im = fx.over(im, shadow_only(lay["avatar_sh"], lay["avatar"], 0.8))
    im = fx.over(im, lay["avatar"])
    im = fx.add(im, edge_light(lay["avatar"], lighten(aura, 0.3), (8, 0), 1.3, 2.0), 0.9)
    im = fx.add(im, fx.glow(lay["avatar"], 18, aura, 0.35), 0.5)

    im = grade(im, 1.12, 1.04, 0.2)

    # 글자: 큰 확률 숫자 + 이름 알약
    im = headline(im, odds(lid), cfg["number"], y=14, width=1780, outline_color=cfg["number_outline"])
    name = LANDMARKS[lid]
    t = tier(lid)
    pill = fx.pill(f"{name['name']}  {name['en']}", font_path(KR), 50, fg=WHITE, bg=darken(t[2], 0.08), outline=INK)
    x = W - pill.width - 40 if cfg["pill_side"] == "right" else 40
    im = fx.over(im, pill, (x, H - pill.height - 36))
    return im


def main(which):
    made = {}
    for n in which:
        if n in HEROES:
            made[n] = save(thumb_hero(n), f"thumb_{n}.png")
    return made


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4]
    main(args)
