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


def bloom(im: Image.Image, threshold=0.9, radius=26, strength=0.3) -> Image.Image:
    a = fx.arr(im)
    lum = a[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
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
            # 투명한 빛 띠처럼: 옆(가장자리로 보이는 곳)은 진하고 주인공 앞을 가로지르는 곳은 옅게
            span = max(abs(P[i, 0] - A[i, 0]), 1.0)
            r_px = cam.scale_at(A[i, 2], (W * SS, H * SS)) * rad[i]
            side = min(1.0, span / max(r_px, 1.0))
            weight = 0.12 + 0.88 * side ** 2.2
            (df if is_front else db).polygon(quad, fill=int(255 * spec.get("alpha", 1) * weight))
    return mask_img(back), mask_img(front)


def add_ribbon(im, a, color, core=None, deep=None):
    """빛 리본: 바깥 번짐(더하기) + 진한 색 띠(덮기 — 밝은 배경에서도 보이게) + 흰 심."""
    core = core or lighten(color, 0.7)
    deep = deep or darken(color, 0.25)
    im = fx.add(im, fx.glow(a, 26, color, 1.6), 0.8)
    im = fx.over(im, fx.solid((W, H), deep, np.clip(a * 0.85, 0, 1)))
    thin = np.clip((fx.blur_alpha(a, 1.5) - 0.45) / 0.35, 0, 1)  # 가운데 밝은 심
    im = fx.add(im, fx.glow(thin, 3, core, 1.2), 0.8)
    return fx.over(im, fx.solid((W, H), core, thin * 0.95))


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


def drop_shadow(im, t: Image.Image, xy, blur=8, alpha=0.4, offset=(3, 8)):
    """글자 그림 t 의 흐린 그림자(가장자리에서 잘리지 않게 여백을 두고 흐림)."""
    pad = int(blur * 3)
    a = np.zeros((t.height + pad * 2, t.width + pad * 2), np.float32)
    a[pad:pad + t.height, pad:pad + t.width] = fx.alpha_of(t)
    sh = fx.solid((a.shape[1], a.shape[0]), (0, 0, 0), fx.blur_alpha(a, blur) * alpha)
    return fx.over(im, sh, (xy[0] - pad + offset[0], xy[1] - pad + offset[1]))


def fitted_text(text, width, font="luckiest", **kw):
    probe = fx.chunky_text(text, font, 200, **kw)
    size = int(200 * width / probe.width)
    return fx.chunky_text(text, font, size, **kw)


def headline(im, text, stops, y=18, width=1760, outline_color=(12, 60, 20), tilt=0.0):
    t = fitted_text(text, width, "luckiest", fill_stops=stops, outline_color=outline_color,
                    depth_color=darken(outline_color, 0.45), gloss=0.35)
    if tilt:
        t = fx.rotate(t, tilt)
    im = drop_shadow(im, t, ((W - t.width) / 2, y), 10, 0.45, (4, 12))
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
        im = drop_shadow(im, t, (tx, y + dy), 8, 0.4)
        im = fx.over(im, t, (tx, y + dy))
    return im


def save(im: Image.Image, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    rgb = im.convert("RGB")
    # 3 MB 안으로: 무손실 PNG(+ oxipng 가 있으면 더 줄임) → 그래도 크면 채널 아래 비트를 1~2개 버림(눈에 거의 안 보임)
    for drop in (0, 1, 2):
        out = rgb if drop == 0 else rgb.point(lambda v, m=(0xFF << drop) & 0xFF: v & m)
        out.save(path, optimize=True)
        try:
            import oxipng

            oxipng.optimize(path, level=2)
        except ImportError:
            pass
        if path.stat().st_size <= MAX_BYTES:
            break
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


def ground_from_screen(cam: st.Camera, sx: float, sy: float):
    """화면 점 (sx, sy) 로 보이는 땅(y=0) 위 점."""
    d = cam.f + cam.r * ((sx / W * 2 - 1) * cam.t * (W / H)) + cam.u * ((1 - sy / H * 2) * cam.t)
    k = -cam.eye[1] / d[1]
    return cam.eye + d * k


# 1·2: 전설 명소 등장 -------------------------------------------------------------------------------
HEROES = {
    1: {
        "id": "worldtree",
        "angle": 337.5,  # 광장에서 본 방향(부지 사이 틈) — 해를 등지고 바다 쪽을 봄
        "radius": 214,
        "size": 26,
        "yaw": 20,
        "fov": 50,
        "eye_h": 7.5,
        "base_y": 915,
        "top_y": 318,
        "aura": (110, 255, 190),  # 전설 민트 + 세계수 초록
        "aura2": (120, 255, 235),
        "number": [(0, (240, 255, 130)), (0.45, (130, 245, 70)), (0.8, (40, 200, 60)), (1, (20, 150, 55))],
        "number_outline": (10, 58, 22),
        "shard_colors": [(22, 70, 58), (30, 96, 80), (16, 52, 44)],
        "shard_mat": "SmoothPlastic",
        "earth": 0.35,
        # 아바타: 화면 x, 카메라에서 깊이, 바라보는 쪽(0 = 주인공, 1 = 카메라)
        "avatar": {"sx": 400, "sy": 1150, "height_px": 520, "face": 0.0,
                   "pose": {"head": (-24, 10), "arm_r": (125, 22), "arm_l": (10, 12), "leg_l": 5, "leg_r": -5}},
        "sky": [(0, (60, 140, 235)), (0.55, (130, 195, 250)), (0.8, (200, 232, 255)), (1, (220, 240, 255))],
        "clouds": [(130, 12, 480, 3, 1), (1800, 14, 460, 5, 1), (470, -50, 280, 8, 0.85), (1560, -70, 260, 9, 0.8),
                   (-40, -270, 380, 10, 0.7), (1960, -300, 420, 13, 0.7)],
        "cloud_colors": ((255, 255, 255), (205, 228, 250)),
        "bg_tint": None,
        "pill_side": "right",
        "near": [(-0.4, 0.66, 34, 1.3), (0.42, 0.6, 38, 1.6), (0.47, 0.2, 44, 1.2)],
    },
    2: {
        "id": "shangrila",
        "angle": 292.5,
        "radius": 212,
        "size": 30,
        "yaw": -28,
        "fov": 50,
        "eye_h": 7.0,
        "base_y": 905,
        "top_y": 330,
        "aura": (255, 150, 60),  # 노을 금빛(샹그릴라 지붕 금색) — 흰 궁전이 묻히지 않게 진하게
        "aura2": (255, 214, 120),
        "number": [(0, (255, 252, 200)), (0.42, (255, 222, 80)), (0.78, (255, 160, 30)), (1, (226, 104, 18))],
        "number_outline": (74, 30, 8),
        "shard_colors": [(96, 54, 150), (128, 76, 186), (66, 38, 110)],
        "shard_mat": "SmoothPlastic",
        "earth": 0.15,
        "glow_k": 0.42,
        "bloom": 0.15,
        "rocks": (1.3, 0.11),  # 바위 고리 반지름(발판 반 대비), 바위 크기(모형 크기 대비)
        "shard_k": 0.1,
        "shard_n": 20,
        "avatar": {"sx": 1560, "sy": 1130, "height_px": 470, "face": 0.55,
                   "pose": {"head": (-8, -6), "arm_r": (18, 138), "arm_l": (18, 138), "leg_l": 8, "leg_r": -4,
                            "mouth": "o"}},
        "sky": [(0, (74, 52, 170)), (0.35, (170, 96, 196)), (0.62, (255, 150, 150)), (0.82, (255, 196, 140)),
                (1, (255, 226, 170))],
        "clouds": [(160, 10, 460, 21, 1), (1760, 16, 520, 22, 1), (560, -70, 300, 23, 0.9), (1380, -40, 280, 24, 0.9),
                   (-20, -300, 400, 25, 0.75), (1940, -260, 380, 26, 0.75)],
        "cloud_colors": ((255, 238, 226), (238, 160, 190)),
        "bg_tint": (1.06, 0.9, 0.84),
        "pill_side": "left",
        "near": [(0.42, 0.66, 34, 1.3), (-0.42, 0.6, 38, 1.6), (-0.47, 0.18, 44, 1.2)],
    },
}


def near_shards(cam: st.Camera, near, colors, mat, seed):
    """카메라 가까이(화면 가장자리) 떠 있는 큰 조각 — 깊이감. near = [(화면 x -0.5~0.5, 화면 위 비율, 깊이, 크기)]."""
    rnd = random.Random(seed)
    out = []
    for (fx_, fy, depth, s) in near:
        p = cam.eye + cam.f * depth + cam.r * (fx_ * 2 * cam.t * (W / H) * depth) + cam.u * ((fy - 0.5) * 2 * cam.t * depth)
        R = st.ry(rnd.uniform(0, 360)) @ st.rx(rnd.uniform(-60, 60)) @ st.rz(rnd.uniform(-60, 60))
        col = rnd.choice(colors)
        size = (s * 0.95, s * 1.9, s * 0.75)
        out.append(st.part("ShardsNear", "Block", size, p, R, col, mat))
        for sgn in (1, -1):
            tip = p + R @ np.array([0, sgn * size[1] * 0.62, 0])
            Rt = R if sgn > 0 else R @ st.rz(180)
            out.append(st.part("ShardsNear", "Wedge", (size[0], size[1] * 0.25, size[2]), tip, Rt, col, mat))
    return out


def hero_stage(cfg):
    lid = cfg["id"]
    ang = math.radians(cfg["angle"])
    u = np.array([math.cos(ang), 0, math.sin(ang)])
    hero = u * cfg["radius"]
    height = hero_height(lid, cfg["size"], cfg["yaw"])
    cam = frame_camera(hero, height, cfg["eye_h"], cfg["fov"], cfg["base_y"], cfg["top_y"], (u[0], u[2]))
    foot = cfg["size"] * 0.5
    parts = []
    rock_r, rock_s = cfg.get("rocks", (1.05, 0.17))
    parts += st.rock_ring(hero, foot * rock_r, 18, cfg["size"] * rock_s, seed=11, color=(150, 154, 162))
    hb = cam.project([hero, hero + np.array([0, height, 0])])
    half_w = cam.scale_at(hb[0][2]) * foot * 0.8

    def over_hero(sx, sy):
        return abs(sx - hb[0][0]) < half_w and hb[1][1] < sy < hb[0][1]

    parts += st.shards(hero, cfg.get("shard_n", 24), (foot * 1.4, foot * 3.0), (3, height * 0.95),
                       cfg["size"] * cfg.get("shard_k", 0.12), 12,
                       cfg["shard_colors"], "ShardsFront", "ShardsBack", cam, mat=cfg["shard_mat"], earth=cfg["earth"],
                       avoid=over_hero)
    parts += near_shards(cam, cfg["near"], cfg["shard_colors"], cfg["shard_mat"], 13)
    av = cfg["avatar"]
    av_base = ground_from_screen(cam, av["sx"], av["sy"])
    av_depth = float(np.dot(av_base - cam.eye, cam.f))
    av_scale = av["height_px"] / (5.6 * cam.scale_at(av_depth))  # 화면에서 원하는 키가 되도록(원근은 그대로)
    to_hero = (hero - av_base)[[0, 2]]
    to_cam = (cam.eye - av_base)[[0, 2]]
    look = to_hero / np.linalg.norm(to_hero) * (1 - av["face"]) + to_cam / np.linalg.norm(to_cam) * av["face"]
    parts += st.avatar("Avatar", av_base, st.yaw_facing(look), av["pose"], scale=av_scale)
    stage = {"models": [{"folder": "Hero", "id": lid, "size": cfg["size"],
                         "cf": st.cf(hero, st.ry(st.yaw_facing((-u[0], -u[2])) + cfg["yaw"]))}],
             "parts": parts}
    for p in stage["parts"]:
        if p["folder"] == "Rocks":
            p["mat"] = "SmoothPlastic"
    clear_until = float(np.dot(hero - cam.eye, cam.f)) + foot * 3
    layers = [
        {"name": "bg", "terrain": True, "exclude": ["Store"], "clear": {"until": clear_until, "margin": 1.6}},
        {"name": "hero", "terrain": False, "include": ["Store/Hero", "Store/Rocks"]},
        {"name": "hero_sh", "terrain": False, "include": ["Store/Hero", "Store/Rocks"],
         "shadow": {"x": hero[0], "y": 0.02, "z": hero[2], "size": 220, "opacity": 0.45}},
        {"name": "avatar", "terrain": False, "include": ["Store/Avatar"]},
        {"name": "avatar_sh", "terrain": False, "include": ["Store/Avatar"],
         "shadow": {"x": av_base[0], "y": 0.02, "z": av_base[2], "size": 40 * av_scale, "opacity": 0.45}},
        {"name": "sfront", "terrain": False, "include": ["Store/ShardsFront"]},
        {"name": "sback", "terrain": False, "include": ["Store/ShardsBack"]},
        {"name": "snear", "terrain": False, "include": ["Store/ShardsNear"]},
    ]
    L = st.render_layers(stage, cam, layers, size=(W * SS, H * SS))
    return cam, hero, height, av_base, L


def tint(im: Image.Image, mul) -> Image.Image:
    a = fx.arr(im)
    a[..., :3] *= np.array(mul, np.float32)
    return fx.img(a)


def add_shards(im, layer, aura, aura2, blur=0.0):
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    im = fx.add(im, fx.glow(layer, 14, aura, 1.6, spread=2), 0.9)
    im = fx.over(im, layer)
    return fx.add(im, edge_light(layer, lighten(aura2, 0.4), (5, 5), 1.4), 1.0)


def thumb_hero(n):
    cfg = HEROES[n]
    lid = cfg["id"]
    cam, hero, height, av_base, L = hero_stage(cfg)
    lay = {k: load_layer(v) for k, v in L.items()}
    aura, aura2 = cfg["aura"], cfg["aura2"]
    base_px = cam.project([hero])[0]
    core = cam.project([hero + np.array([0, height * 0.62, 0])])[0]
    top_px = cam.project([hero + np.array([0, height, 0])])[0]
    foot = cfg["size"] * 0.5

    # 하늘 + 구름 + 배경(진짜 섬: 풀밭·바다)
    horizon = cam.project([cam.eye + np.array([cam.f[0], 0, cam.f[2]]) * 3000])[0][1]
    im = fx.linear((W, H), cfg["sky"])
    ctop, cbottom = cfg["cloud_colors"]
    for (x, dy, width, seed, alpha) in cfg["clouds"]:
        c = fx.cloud(width, seed=seed, top=ctop, bottom=cbottom)
        im = fx.over(im, c, (x - c.width / 2, horizon + dy - c.height), alpha)
    bg = lay["bg"] if not cfg["bg_tint"] else tint(lay["bg"], cfg["bg_tint"])
    im = fx.over(im, bg)

    # 뒤 빛: 큰 오라 + 햇살 두 겹(땅 위에서는 약하게)
    ground = fx.alpha_of(lay["bg"])
    ground_fade = 1 - 0.8 * ground * np.clip((np.arange(H)[:, None] - base_px[1] + 60) / 120, 0, 1)
    gk = cfg.get("glow_k", 1.0)  # 밝은 색(금색)은 더하기 빛이 금방 하얘지므로 줄임
    im = fx.add(im, fx.radial((W, H), core[:2], 820, [(0, aura + (230,)), (0.35, aura + (110,)), (1, aura + (0,))]),
                0.7 * gk)
    im = fx.add(im, fx.multiply_alpha(fx.rays((W, H), core[:2], count=26, color=lighten(aura2, 0.35), width=0.42,
                                              seed=21, falloff=1.1, inner=40), ground_fade), 0.6 * gk)
    im = fx.add(im, fx.multiply_alpha(fx.rays((W, H), core[:2], count=14, color=WHITE, width=0.2, seed=22,
                                              falloff=1.6), ground_fade), 0.4 * gk)
    im = fx.add(im, fx.radial((W, H), core[:2], 260, [(0, (255, 255, 255, 200)), (0.5, aura + (80,)), (1, aura + (0,))]),
                0.45 * gk)

    # 땅: 어두운 구덩이 + 빛 웅덩이 + 금 + 마법진
    crater = fx.warp_quad(fx.radial((512, 512), (256, 256), 256, [(0, (8, 36, 26, 200)), (0.7, (8, 36, 26, 150)),
                                                                   (1, (8, 36, 26, 0))]),
                          ground_quad(cam, hero, foot * 3.6), (W, H))
    im = fx.over(im, crater)
    pool = fx.warp_quad(fx.radial((512, 512), (256, 256), 256, [(0, aura + (170,)), (0.5, aura + (50,)),
                                                                 (1, aura + (0,))]),
                        ground_quad(cam, hero, foot * 4.5), (W, H))
    im = fx.add(im, pool, 0.6)
    dark, crack_core = fx.cracks(1600, seed=31, count=13, inner=0.18, reach=(0.55, 0.98))
    q = ground_quad(cam, hero, foot * 3.6)
    dark_w, core_w = fx.warp_quad(dark, q, (W, H)), fx.warp_quad(crack_core, q, (W, H))
    im = fx.over(im, fx.solid((W, H), (30, 44, 34), fx.alpha_of(dark_w) * 0.8))
    im = fx.add(im, fx.glow(core_w, 6, aura, 1.8), 1.0)
    im = fx.add(im, fx.solid((W, H), lighten(aura, 0.6), fx.alpha_of(core_w)), 1.0)
    circle = fx.warp_quad(fx.magic_circle(2048, WHITE, seed=5, width=1.5), ground_quad(cam, hero, foot * 2.9), (W, H))
    ca = fx.alpha_of(circle)
    im = fx.add(im, fx.glow(ca, 16, aura, 2.0), 1.0)
    im = fx.add(im, fx.glow(ca, 4, aura2, 1.6), 1.0)
    im = fx.add(im, fx.solid((W, H), lighten(aura2, 0.5), ca), 1.0)
    im = fx.over(im, shadow_only(lay["hero_sh"], lay["hero"], 0.6))

    # 리본(뒤) + 조각(뒤)
    rib = [
        {"phase": 0.3, "turns": 1.35, "r0": foot * 2.7, "r1": foot * 1.5, "y0": 1, "y1": height * 0.8, "width": 44},
        {"phase": 2.6, "turns": 1.2, "r0": foot * 2.3, "r1": foot * 1.8, "y0": 3, "y1": height * 0.6, "width": 32},
        {"phase": 4.4, "turns": 1.0, "r0": foot * 3.3, "r1": foot * 2.2, "y0": 0.5, "y1": height * 0.4, "width": 18,
         "alpha": 0.8},
    ]
    rb, rf = ribbons(cam, hero, rib)
    im = add_ribbon(im, rb, aura)
    im = add_shards(im, lay["sback"], aura, aura2)

    # 주인공: 바깥 빛 + 본체 + 양옆 테두리 빛
    im = fx.add(im, fx.glow(lay["hero"], 28, aura, 1.6, spread=6), gk)
    im = fx.add(im, fx.glow(lay["hero"], 8, lighten(aura2, 0.3), 1.2, spread=2), 0.9 * gk ** 0.5)
    im = fx.over(im, lay["hero"])
    im = fx.add(im, edge_light(lay["hero"], lighten(aura2, 0.35), (-7, 5), 1.2), 0.9)
    im = fx.add(im, edge_light(lay["hero"], lighten(aura2, 0.35), (7, 5), 1.2), 0.9)

    # 앞: 리본, 조각, 알갱이, 반짝이
    im = add_ribbon(im, rf, aura)
    im = add_shards(im, lay["sfront"], aura, aura2)
    im = fx.add(im, fx.particles((W, H), core[:2], 90, (1.5, 4.5), WHITE, seed=41, spread=(0.05, 0.42),
                                 glow_color=aura), 1.0)
    hx0, hx1 = top_px[0] - 520, top_px[0] + 520
    im = scatter_sparkles(im, [(hx0, top_px[1], top_px[0] - 200, base_px[1] - 40),
                               (top_px[0] + 200, top_px[1], hx1, base_px[1] - 40)], 20, seed=51, glow_color=aura,
                          rmin=7, rmax=34,
                          big=[(top_px[0] - 360, top_px[1] + 120, 58), (top_px[0] + 390, core[1] + 40, 70),
                               (top_px[0] + 300, top_px[1] + 30, 36), (top_px[0] - 440, base_px[1] - 190, 44)])
    im = bloom(im, strength=cfg.get("bloom", 0.3))
    im = add_shards(im, lay["snear"], aura, aura2, blur=2.2)

    # 아바타(맨 앞): 그림자 + 몸 + 주인공 쪽 테두리 빛
    av_px = cam.project([av_base])[0]
    side = 1 if base_px[0] > av_px[0] else -1
    im = fx.over(im, shadow_only(lay["avatar_sh"], lay["avatar"], 0.8))
    im = fx.over(im, lay["avatar"])
    im = fx.add(im, edge_light(lay["avatar"], lighten(aura, 0.3), (8 * side, 0), 1.3, 2.0), 0.9)
    im = fx.add(im, fx.glow(lay["avatar"], 18, aura, 0.35), 0.5)

    im = grade(im, 1.12, 1.04, 0.2)

    # 글자: 큰 확률 숫자 + 이름 알약
    im = headline(im, odds(lid), cfg["number"], y=10, width=1700, outline_color=cfg["number_outline"])
    name = LANDMARKS[lid]
    t = tier(lid)
    pill = fx.pill(f"{name['name']}  {name['en']}", font_path(KR), 60, fg=WHITE, bg=darken(t[2], 0.08), outline=INK)
    x = W - pill.width - 40 if cfg["pill_side"] == "right" else 40
    im = fx.over(im, pill, (x, H - pill.height - 36))
    return im


# 3: 150개 명소를 모아라 -------------------------------------------------------------------------------
def model_heights(ids, size=10.0):
    """명소 모형 높이/크기 비(모형마다 다름). 한 덤프에 모두 넣고 잼."""
    import json

    models = [{"folder": f"M_{lid}", "id": lid, "size": size, "cf": st.cf((i * 40.0, 0, 0))} for i, lid in enumerate(ids)]
    dump = st.world_dump({"models": models}, players=0)
    parts = json.loads(dump.read_text())["parts"]
    out = {}
    for lid in ids:
        ps = [p for p in parts if p["path"].startswith(f"Store/M_{lid}/") and p["t"] < 0.99]
        out[lid] = max(p["p"][1] + max(p["z"]) / 2 for p in ps) / size
    return out


# (명소, 화면 x, 화면 y(모형 가운데), 화면 키(px), 깊이, 좌우 돌림, 기울임[, 앞으로 숙임 = 8])
COLLECT = [
    ("liberty", 205, 640, 360, 88, -30, -9),
    ("eiffel", 440, 400, 330, 96, -22, -6),
    ("moai", 640, 735, 170, 112, -35, 8),
    ("tajmahal", 790, 380, 250, 100, -12, -4),
    ("colosseum", 1150, 385, 190, 100, 22, 5, 28),
    ("alexandria", 1305, 720, 230, 112, 25, -7),
    ("pyramid", 1520, 430, 210, 96, 30, 6),
    ("greatwall", 1735, 680, 230, 88, 38, 9),
]


def world_at(cam: st.Camera, sx, sy, depth):
    return (cam.eye + cam.f * depth + cam.r * ((sx / W * 2 - 1) * cam.t * (W / H) * depth)
            + cam.u * ((1 - sy / H * 2) * cam.t * depth))


def collect_stage():
    ids = [c[0] for c in COLLECT]
    ratio = model_heights(ids)
    origin = np.array([3000.0, 60.0, 0.0])  # 섬 밖 바다 위(배경은 그리지 않으므로 어디든 됨)
    cam = st.Camera(origin + np.array([0, 0, 100.0]), origin, 45, (W, H))
    models = []
    placed = {}
    for (lid, sx, sy, hpx, depth, yaw, roll, *rest) in COLLECT:
        pitch = rest[0] if rest else 8
        size = hpx / (ratio[lid] * cam.scale_at(depth))
        center = world_at(cam, sx, sy, depth)
        R = st.rz(roll) @ st.rx(pitch) @ st.ry(yaw)  # 카메라(+Z) 쪽을 보고 조금 돌리고 기울임
        R = R @ st.ry(180)  # 모형 앞(-Z)이 카메라(+Z)를 보게
        h = ratio[lid] * size
        pivot = center - R @ np.array([0, h / 2, 0])
        models.append({"folder": f"L_{lid}", "id": lid, "size": size, "cf": st.cf(pivot, R)})
        placed[lid] = (sx, sy, hpx)
    globe_depth = 84
    globe_center = world_at(cam, 960, 1090, globe_depth)
    gsize = 44
    R = st.rx(-14) @ st.ry(160)  # 경도 40도쯤(유럽·아프리카·아시아)이 카메라 쪽, 살짝 위가 보이게
    models.append({"folder": "Globe", "id": "Globe", "size": gsize,
                   "cf": st.cf(globe_center - R @ np.array([0, gsize / 2, 0]), R)})
    layers = [{"name": "globe", "terrain": False, "include": ["Store/Globe"]}]
    layers += [{"name": f"L_{lid}", "terrain": False, "include": [f"Store/L_{lid}"]} for lid in ids]
    L = st.render_layers({"models": models}, cam, layers, size=(W * SS, H * SS), players=0)
    gp = cam.project([globe_center])[0]
    return cam, placed, (gp[0], gp[1], gsize / 2 * cam.scale_at(gp[2])), L


def streak(size, p0, p1, w0, w1):
    """p0(가늘게) → p1(굵게) 꼬리 모양(끝이 둥근 사다리꼴) 알파 + 길이 방향 t(0~1)."""
    s = SS
    Lm = Image.new("L", (size[0] * s, size[1] * s), 0)
    d = ImageDraw.Draw(Lm)
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln, dx / ln
    pts = [(x0 + nx * w0, y0 + ny * w0), (x1 + nx * w1, y1 + ny * w1), (x1 - nx * w1, y1 - ny * w1),
           (x0 - nx * w0, y0 - ny * w0)]
    d.polygon([(x * s, y * s) for x, y in pts], fill=255)
    d.ellipse(((x1 - w1) * s, (y1 - w1) * s, (x1 + w1) * s, (y1 + w1) * s), fill=255)
    a = mask_img(Lm)
    ys, xs = np.mgrid[0:size[1], 0:size[0]].astype(np.float32)
    t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / (ln * ln), 0, 1)
    return a, t


def thumb_collect():
    cam, placed, (gx, gy, gr), L = collect_stage()
    lay = {k: load_layer(v) for k, v in L.items()}

    # 배경: 파란 하늘 방사 햇살 + 아래 구름
    im = fx.radial((W, H), (gx, gy - gr * 0.6), 1500, [(0, (190, 245, 255)), (0.35, (90, 190, 250)),
                                                       (0.75, (40, 120, 225)), (1, (28, 84, 190))])
    burst = fx.rays((W, H), (gx, gy - gr * 0.6), count=22, color=WHITE, width=0.5, seed=61, falloff=0.6, inner=gr)
    im = fx.add(im, burst, 0.22)
    for (x, y, width, seed, alpha) in [(120, 1110, 620, 71, 1), (1800, 1110, 660, 72, 1), (480, 1130, 520, 73, 1),
                                       (1440, 1130, 540, 74, 1), (-60, 620, 300, 75, 0.8), (1990, 560, 320, 76, 0.8)]:
        c = fx.cloud(width, seed=seed)
        im = fx.over(im, c, (x - c.width / 2, y - c.height), alpha)

    # 꼬리(지구본 → 명소), 명소 뒤 빛
    for lid, (sx, sy, hpx) in placed.items():
        col = tier(lid)[2]
        dx, dy = sx - gx, sy - (gy - gr * 0.55)
        start = (gx + dx * 0.18, gy - gr * 0.55 + dy * 0.18)
        end = (sx - dx * 0.12, sy - dy * 0.12)
        a, t = streak((W, H), start, end, 5, hpx * 0.2)
        im = fx.add(im, fx.solid((W, H), col, fx.blur_alpha(a * t ** 1.1, 8)), 1.0)
        core_a, _ = streak((W, H), start, end, 1.5, hpx * 0.07)
        im = fx.add(im, fx.solid((W, H), WHITE, fx.blur_alpha(core_a * t ** 1.5, 2)), 0.9)
        im = fx.add(im, fx.radial((W, H), (sx, sy), hpx * 0.95, [(0, col + (200,)), (0.5, col + (70,)), (1, col + (0,))]),
                    0.8)

    # 지구본: 빛 + 도는 궤적(흰 호) + 본체
    im = fx.add(im, fx.radial((W, H), (gx, gy), gr * 1.9, [(0, (255, 255, 255, 255)), (0.5, (160, 240, 255, 150)),
                                                            (1, (120, 220, 255, 0))]), 0.9)
    arcs = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(arcs)
    for k, (rr, a0, a1, wdt) in enumerate([(1.12, 200, 250, 10), (1.2, 290, 335, 8), (1.08, 300, 318, 6),
                                           (1.28, 212, 232, 6)]):
        r = gr * rr * SS
        d.arc((gx * SS - r, gy * SS - r, gx * SS + r, gy * SS + r), a0, a1, fill=255, width=int(wdt * SS))
    arcs_a = mask_img(arcs)
    im = fx.add(im, fx.glow(arcs_a, 8, (140, 230, 255), 1.4), 1.0)
    im = fx.add(im, fx.solid((W, H), WHITE, arcs_a), 0.9)
    im = fx.add(im, fx.glow(lay["globe"], 20, (160, 240, 255), 1.3, spread=4), 0.9)
    im = fx.over(im, lay["globe"])
    im = fx.add(im, edge_light(lay["globe"], (200, 245, 255), (0, 8), 1.2, 2), 0.8)

    # 명소: 등급 색 테두리 빛 + 본체 + 반짝이
    for lid, (sx, sy, hpx) in placed.items():
        col = tier(lid)[2]
        layer = lay[f"L_{lid}"]
        im = fx.add(im, fx.glow(layer, 16, col, 1.6, spread=5), 1.0)
        im = fx.add(im, fx.solid((W, H), WHITE, fx.dilate(layer, 4) * (1 - fx.alpha_of(layer))), 0.95)
        im = fx.over(im, layer)
    im = scatter_sparkles(im, [(60, 280, 1860, 900)], 30, seed=81, glow_color=(150, 235, 255), rmin=7, rmax=30,
                          big=[(640, 300, 46), (1330, 560, 52), (300, 880, 40), (1640, 280, 40), (960, 610, 60)])
    im = fx.add(im, fx.particles((W, H), (gx, gy - gr), 110, (1.5, 4), WHITE, seed=82, spread=(0.1, 0.5),
                                 glow_color=(150, 235, 255)), 1.0)

    # 확률 표(명소 아래), 제목
    for lid, (sx, sy, hpx) in placed.items():
        col = tier(lid)[2]
        tag = fx.chunky_text(odds(lid), "luckiest", 64, fill_stops=[(0, lighten(col, 0.55)), (0.5, lighten(col, 0.1)),
                                                                     (1, darken(col, 0.15))],
                             outline_color=INK, outline=9, inner=4, depth=5, gloss=0.25)
        tag = fx.rotate(tag, random.Random(lid).uniform(-5, 5))
        ty = sy + hpx * 0.5 - tag.height * 0.35
        im = drop_shadow(im, tag, (sx - tag.width / 2, ty), 6, 0.4)
        im = fx.over(im, tag, (sx - tag.width / 2, ty))
    im = grade(im, 1.1, 1.03, 0.18)
    im = caption_block(im, "150개 명소를 모아라!", "COLLECT 150 LANDMARKS!", (W / 2, 14), kr_size=128, en_size=60,
                       align="center",
                       kr_stops=[(0, (255, 255, 255)), (0.55, (255, 246, 200)), (1, (255, 200, 70))],
                       en_stops=[(0, (190, 255, 250)), (1, (120, 255, 235))])
    return im


# 4: 나만의 관광 공원 -----------------------------------------------------------------------------------
# 부지 8곳을 모두 채운 진짜 맵(ParkService 전시) — 잘 알려진 명소를 앞에 두고 나머지는 목록에서 고름
FAMOUS = ["eiffel", "tajmahal", "liberty", "colosseum", "bigben", "pyramid", "moai", "greatwall", "sphinx", "pisa",
          "goldengate", "fuji", "stbasil", "parthenon", "machupicchu", "chichen", "alexandria", "petra", "stonehenge",
          "santorini", "notredame", "neuschwanstein", "sungnyemun", "namsan", "towerbridge", "windmill"]
PARK_CAM = ((-40, 80, 290), (-15, 0, 60), 52)


def thumb_park():
    stage = {"fillParks": {"level": 10, "count": 36, "famous": 22, "maxOneIn": 100000, "ids": FAMOUS}}
    eye, target, fov = PARK_CAM
    cam = st.Camera(eye, target, fov, (W, H))
    L = st.render_layers(stage, cam, [{"name": "bg", "terrain": True}], size=(W * SS, H * SS), players=8)
    bg = load_layer(L["bg"])

    # 하늘(맵 그림은 투명 배경) + 수평선 안개 + 구름
    a = fx.alpha_of(bg)
    rows = np.where(a[:, W // 2 - 400: W // 2 + 400].mean(1) > 0.5)[0]
    edge = int(rows[0]) if len(rows) else int(H * 0.2)  # 바다가 끝나는 줄(그 위는 하늘)
    im = fx.linear((W, H), [(0, (58, 140, 236)), (edge / H * 0.8, (140, 200, 250)), (edge / H, (214, 238, 255)),
                            (1, (214, 238, 255))])
    for (x, y, width, seed, alpha) in [(150, edge + 14, 330, 91, 0.95), (1760, edge + 16, 360, 92, 0.95),
                                       (1420, edge + 10, 220, 93, 0.85), (430, edge + 8, 200, 94, 0.8)]:
        c = fx.cloud(width, seed=seed)
        im = fx.over(im, c, (x - c.width / 2, y - c.height), alpha)
    haze = fx.linear((W, H), [(0, (255, 255, 255, 0)), (max(0, edge - 30) / H, (255, 255, 255, 0)),
                              (edge / H, (235, 246, 255, 200)), (min(1, edge + 40) / H, (235, 246, 255, 0)),
                              (1, (255, 255, 255, 0))])
    im = fx.over(im, bg)
    im = fx.over(im, haze)

    # 빛: 왼쪽 위 햇빛 + 번짐(bloom) + 지구본 빛
    im = fx.add(im, fx.radial((W, H), (120, -80), 1300, [(0, (255, 250, 220, 150)), (1, (255, 250, 220, 0))]), 0.35)
    im = fx.add(im, fx.rays((W, H), (120, -80), count=14, color=(255, 252, 230), width=0.35, seed=96, falloff=1.3), 0.12)
    globe = cam.project([(0, 20, -60)])[0]  # 광장 지구본 둘레(대략)
    im = fx.add(im, fx.radial((W, H), globe[:2], 150, [(0, (200, 245, 255, 200)), (1, (200, 245, 255, 0))]), 0.3)
    im = bloom(im, 0.86, 18, 0.28)

    # 수입 동전(게임 UI 동전 그림) + 반짝이: 앞 공원 위
    coin = Image.open(ROOT / "art/png/coin.png").convert("RGBA")
    rnd = random.Random(97)
    for (x, y, s) in [(520, 560, 92), (660, 470, 70), (1340, 520, 96), (1500, 600, 74), (1180, 440, 62),
                      (380, 470, 58)]:
        c = fx.rotate(coin.resize((s, s), Image.Resampling.LANCZOS), rnd.uniform(-18, 18))
        g = fx.glow(np.pad(fx.alpha_of(c), 30), 14, (255, 220, 90), 1.2)
        im = fx.add(im, g, 0.8, (x - c.width / 2 - 30, y - c.height / 2 - 30))
        im = fx.over(im, c, (x - c.width / 2, y - c.height / 2))
    im = scatter_sparkles(im, [(120, 380, 900, 900), (1000, 380, 1820, 900)], 22, seed=98,
                          glow_color=(255, 230, 140), rmin=6, rmax=26,
                          big=[(300, 640, 40), (1640, 700, 44), (860, 400, 34)])
    im = grade(im, 1.14, 1.04, 0.2)
    im = caption_block(im, "나만의 관광 공원", "BUILD YOUR TOURIST PARK!", (W / 2, 10), kr_size=124, en_size=58,
                       align="center",
                       kr_stops=[(0, (255, 255, 255)), (0.55, (255, 246, 200)), (1, (255, 200, 70))],
                       en_stops=[(0, (210, 255, 200)), (1, (120, 235, 110))])
    return im


def sheet() -> Path:
    """네 장을 작게(2x2) 모은 점검용 그림 — 스토어 목록에서처럼 작게 봐도 읽히는지."""
    tw, th, gap = 800, 450, 24
    out = Image.new("RGB", (tw * 2 + gap * 3, th * 2 + gap * 3), (236, 238, 242))
    for i in range(4):
        path = OUT / f"thumb_{i + 1}.png"
        if not path.exists():
            continue
        im = Image.open(path).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        out.paste(im, (gap + (i % 2) * (tw + gap), gap + (i // 2) * (th + gap)))
    path = OUT / "thumbs_sheet.png"
    out.save(path, optimize=True)
    print(f"[thumbs] {path}")
    return path


def main(which):
    made = {}
    for n in which:
        if n in HEROES:
            made[n] = save(thumb_hero(n), f"thumb_{n}.png")
        elif n == 3:
            made[n] = save(thumb_collect(), "thumb_3.png")
        elif n == 4:
            made[n] = save(thumb_park(), "thumb_4.png")
    return made


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4]
    main(args)
    sheet()
