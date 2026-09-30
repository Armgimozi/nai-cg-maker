#!/usr/bin/env python3
"""스토어 썸네일 5장(1920x1080 PNG) — 진짜 게임 그림(맵·명소 모형 3D 렌더) + 빛 효과 합성.

    python3 tools/store/thumbs.py            # art/store/thumb_1.png ~ thumb_5.png + thumbs_sheet.png
    python3 tools/store/thumbs.py 1 3        # 고른 것만

썸네일마다 다른 약속 하나(스토어 목록에서 작게 봐도 한눈에): 1 세계수 확률(희귀) · 2 환생 행운 배율(성장) ·
3 명소 150곳(수집) · 4 내 공원(타이쿤) · 5 샹그릴라 확률(희귀, 덤). 올리는 순서도 이 번호대로.

만드는 법
  1) 무대(stage.py): 진짜 맵(world.luau) 위에 게임 모형(Models.create)·바위·조각·블록 아바타를 올려 덤프
  2) 레이어(render_layers.js + world_preview/scene.js): 같은 카메라로 배경/주인공/아바타 ... 를 따로 투명 PNG 로
  3) 합성(fx.py): 하늘·구름 → 배경 → 햇살·오라 → 땅 마법진·금 → 뒤 조각·리본 → 주인공 → 앞 조각·리본·반짝이 → 아바타 → 글자
모든 이름·확률·배율은 src/shared/Landmarks.luau · Config.luau 에서 읽음(게임에 있는 명소·숫자만, 쉼표 자연수
"1/10,000,000,000"). 공원 말풍선 "+N/s" 는 게임 코드(PlayerState.landmarkIncome)가 계산한 값 그대로.
그림 속 글자는 영어·숫자만(전 세계 스토어용 — 한글 없음. 공원 간판 이름도 stage_hook 이 영어로 바꾸고 한글이면 멈춤).
글꼴: Luckiest Guy · Fredoka One(게임 UI 글꼴, mockup/fonts).
"""
from __future__ import annotations

import io
import math
import random
import re
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
# 등급 영어 이름(스토어 그림용, Landmarks.Tiers 순서 = 흔한 것 → 희귀한 것). 게임 안 이름은 한국어(일반 명소 … 전설)
TIER_EN = ["COMMON", "CITY", "NATIONAL", "WORLD", "WONDER", "LOST HERITAGE", "LEGENDARY"]
assert len(TIER_EN) == len(TIERS), "Landmarks.Tiers 수가 바뀜 — TIER_EN 도 맞춰 주세요"


def config_number(name: str) -> float:
    text = (ROOT / "src/shared/Config.luau").read_text()
    return float(re.search(r"\n\t%s = ([0-9.]+)," % re.escape(name), text).group(1))


def odds(lid: str) -> str:
    return f"1/{LANDMARKS[lid]['one_in']:,}"


def tier(lid: str):
    n = LANDMARKS[lid]["one_in"]
    best = TIERS[0]
    for t in TIERS:
        if n >= t[0]:
            best = t
    return best  # (MinOneIn, 이름, 색)


def tier_en(lid: str) -> str:
    return TIER_EN[TIERS.index(tier(lid))]


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


def bloom(im: Image.Image, threshold=0.9, radius=26, strength=0.3, exclude=None) -> Image.Image:
    """밝은 곳 번짐. exclude(알파 0~1) 가 있는 곳(예: 흰 대리석 명소)은 번지지 않게."""
    a = fx.arr(im)
    lum = a[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    m = np.clip((lum - threshold) / (1 - threshold), 0, 1)
    if exclude is not None:
        m *= 1 - exclude
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
            weight = 0.5 + 0.5 * side ** 2
            (df if is_front else db).polygon(quad, fill=int(255 * spec.get("alpha", 1) * weight))
    return mask_img(back), mask_img(front)


def add_ribbon(im, a, color, core=None, deep=None, front=False):
    """빛 리본: 바깥 번짐 + 색 띠(부드러운 가장자리, 덮기 — 밝은 배경에서도 보이게) + 가운데 흰 심."""
    core = core or lighten(color, 0.8)
    shape = np.clip(fx.blur_alpha(a, 1.2), 0, 1)
    im = fx.add(im, fx.glow(shape, 20, color, 1.3), 0.55)
    if deep:
        im = fx.over(im, fx.solid((W, H), deep, np.clip(fx.dilate(shape, 2) * 0.5, 0, 1)))
    im = fx.over(im, fx.solid((W, H), color, np.clip(shape * 0.95, 0, 1)))
    thin = np.clip((fx.blur_alpha(fx.erode(a, 5), 2) - 0.2) / 0.5, 0, 1)
    im = fx.add(im, fx.glow(thin, 4, core, 1.0), 0.5)
    return fx.over(im, fx.solid((W, H), core, thin))


def scatter_sparkles(im, rects, count, seed, color=WHITE, glow_color=fx.MINT, rmin=8, rmax=46, big=(), avoid=None):
    """반짝이 흩뿌리기. avoid(알파 0~1, H x W) 가 있으면 그 위(명소 모형 등)에는 두지 않음."""
    rnd = random.Random(seed)
    for _ in range(count):
        x0, y0, x1, y1 = rnd.choice(rects)
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rmin + (rmax - rmin) * rnd.random() ** 2.2
        if avoid is not None and avoid[int(np.clip(y, 0, H - 1)), int(np.clip(x, 0, W - 1))] > 0.05:
            continue
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


def fitted_text(text, width, font="luckiest", tracking=0, **kw):
    """글자 폭이 width 가 되는 크기로(자간 tracking 은 200px 글자 기준 값, 크기에 맞춰 늘림)."""
    probe = fx.chunky_text(text, font, 200, tracking=tracking, **kw)
    size = int(200 * width / probe.width)
    t = fx.chunky_text(text, font, size, tracking=int(round(tracking * size / 200)), **kw)
    return t


def headline(im, text, stops, y=18, width=1760, outline_color=(12, 60, 20), tilt=0.0, tracking=0, slant=0.0):
    """큰 확률 숫자. tracking(음수 = 좁게), slant(오른쪽으로 기울임). 결과 (그림, 글자 상자 x0, y0, x1, y1)."""
    t = fitted_text(text, width, "luckiest", fill_stops=stops, outline_color=outline_color,
                    depth_color=darken(outline_color, 0.45), gloss=0.35, tracking=tracking)
    if slant:
        t = fx.shear(t, slant)
        t = t.resize((width, int(t.height * width / t.width)), Image.Resampling.LANCZOS)
    if tilt:
        t = fx.rotate(t, tilt)
    x = (W - t.width) / 2
    im = drop_shadow(im, t, (x, y), 10, 0.45, (4, 12))
    return fx.over(im, t, (x, y)), (x, y, x + t.width, y + t.height)


def title_line(im, text, xy, size=120, stops=None, outline=INK, align="center", tilt=0.0):
    """영어 제목 한 줄(두꺼운 테 + 두께 + 광택, Luckiest Guy). xy = 글자 가운데 위(align=left 면 왼쪽 위).
    결과 (그림, 글자 상자 x0, y0, x1, y1)."""
    stops = stops or [(0, (255, 255, 255)), (0.55, (255, 246, 200)), (1, (255, 200, 70))]
    t = fx.chunky_text(text, "luckiest", size, fill_stops=stops, outline_color=outline, outline=int(size * 0.13),
                       inner=int(size * 0.04), depth=int(size * 0.08), depth_color=darken(outline, 0.45), gloss=0.3)
    if tilt:
        t = fx.rotate(t, tilt)
    x, y = xy
    tx = x if align == "left" else (x - t.width if align == "right" else x - t.width / 2)
    im = drop_shadow(im, t, (tx, y), 9, 0.45, (4, 10))
    return fx.over(im, t, (tx, y)), (tx, y, tx + t.width, y + t.height)


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


# 1·5: 전설 명소 등장 -------------------------------------------------------------------------------
# 배경(섬 지형)과 주인공 그림자는 맵 미리보기 렌더(render_layers.js), 주인공·바위·결정·아바타는 scene3d.js(render3d.js)로
# 같은 카메라에서 따로 그려 합성. 결정은 볼록 껍질(면이 평평한 뾰족한 수정), 바위도 볼록 껍질(각진 돌).
AWE = {"head": (-26, 10), "arm_r": (124, 8), "arm_l": (14, 16), "leg_l": 6, "leg_r": -6, "face": False}  # 올려다보며 한 팔을 뻗음
HOORAY = {"head": (-16, 0), "arm_r": (158, 52), "arm_l": (158, 52), "leg_l": 8, "leg_r": -4, "face": False}  # 두 팔 V

HEROES = {
    1: {
        "id": "worldtree",
        "number_w": 1800,  # 1/10,000,000,000(16글자) — 화면 폭 거의 다
        "angle": 337.5,  # 광장에서 본 방향(부지 사이 틈) — 해를 등지고 바다 쪽을 봄
        "radius": 214,
        "size": 26,
        "yaw": 20,
        "fov": 50,
        "eye_h": 21,
        "base_y": 1010,
        "top_y": 130,  # 잎 꼭대기가 숫자 아래 띠 뒤로 조금 들어감(참고 그림의 칼끝처럼)
        "aura": (40, 230, 130),  # 세계수 초록 — 가운데 빛은 흰색이 아니라 초록
        "aura2": (120, 255, 235),  # 전설 등급 민트(테두리·결정 모서리·마법진)
        "core": (170, 255, 200),
        "ink": (4, 30, 20),
        "number": [(0, (240, 255, 130)), (0.45, (130, 245, 70)), (0.8, (40, 200, 60)), (1, (20, 150, 55))],
        "number_outline": (10, 58, 22),
        "crystal_colors": [(70, 150, 120), (58, 132, 106), (84, 168, 136), (50, 118, 96)],
        "rock_color": (62, 70, 96),
        "crater": (10, 40, 30),
        "tip_rocks": {"angles": [i * 60 + 17.2 for i in range(6)], "r": 4.1 / 9.6},  # 뿌리 끝(모형 비율) 위 바위
        "avatar": {"sx": 300, "sy": 1150, "height_px": 480, "face": 0.0, "pose": AWE},
        "sky": [(0, (40, 128, 232)), (0.55, (110, 190, 250)), (0.8, (190, 230, 255)), (1, (215, 240, 255))],
        "clouds": [(150, 14, 470, 3, 1), (1790, 16, 470, 5, 1), (470, -46, 280, 8, 0.85), (1560, -66, 260, 9, 0.8),
                   (-30, -270, 360, 10, 0.7), (1970, -300, 400, 13, 0.7)],
        "cloud_colors": ((255, 255, 255), (205, 228, 250)),
        "bg_tint": None,
        "pill_side": "right",
        "near": [(110, 360, 0.4, 0.13), (1800, 560, 0.42, 0.15), (1850, 900, 0.36, 0.12)],  # 화면 x, y, 깊이 비, 길이 비
        "wisps": 1.0,
        "ray_center": 0.62,
        "base_glow": 0.85,
    },
    5: {
        "id": "shangrila",
        "seed": 2,  # 먹물 불꽃 무늬(예전 2번 썸네일과 같은 모양)
        "angle": 292.5,
        "radius": 212,
        "size": 30,
        "yaw": -28,
        "fov": 50,
        "eye_h": 9.0,
        "base_y": 915,
        "top_y": 300,
        "aura": (255, 150, 40),  # 노을 금빛(샹그릴라 지붕 금색 = 모형 둘째 색)
        "aura2": (255, 214, 110),
        "core": (255, 200, 120),
        "ink": (40, 14, 60),
        "number": [(0, (255, 252, 200)), (0.42, (255, 222, 80)), (0.78, (255, 160, 30)), (1, (226, 104, 18))],
        "number_outline": (74, 30, 8),
        "crystal_colors": [(250, 170, 60), (230, 140, 40), (255, 200, 90), (210, 115, 35)],  # 호박빛 결정
        "rock_color": (96, 84, 120),
        "crater": (40, 16, 56),
        "tip_rocks": None,
        "rocks_r": 1.02,
        "avatar": {"sx": 1540, "sy": 1150, "height_px": 430, "face": 0.1, "pose": HOORAY},
        "sky": [(0, (60, 36, 150)), (0.35, (140, 70, 190)), (0.62, (236, 120, 170)), (0.82, (255, 180, 140)),
                (1, (255, 214, 160))],
        "clouds": [(160, 10, 460, 21, 1), (1760, 16, 520, 22, 1), (560, -70, 300, 23, 0.9), (1380, -40, 280, 24, 0.9),
                   (-20, -300, 400, 25, 0.75), (1940, -260, 380, 26, 0.75)],
        "cloud_colors": ((255, 232, 226), (220, 150, 196)),
        "bg_tint": (1.0, 0.86, 0.98),
        "bg_desat": 0.55,
        "pill_side": "left",
        "near": [(1800, 420, 0.42, 0.1), (110, 520, 0.44, 0.1)],
        "wisps": 0.8,
        "ray_center": 0.45,  # 빛 가운데 = 탑 지붕 뒤(흰 봉우리 끝이 날아가지 않게)
        "aura_k": 0.45,
        "sun_side": 0.9,
        "crystal_len": 0.22,
        "ribbon_k": 0.7,
        "purple_back": (58, 18, 104),
        "clear_screen": [[0.72, 0.5, 0.88, 0.74]],  # 아바타 머리 뒤 먼 야자수(머리에 싹이 난 것처럼 보임)는 뺌
        "pill_bg": (38, 18, 60),
        "white_guard": True,
    },
}


def lighthouse_paths(dump: Path) -> list:
    """맵 왼쪽 등대(주인공과 겨루는 높은 탑)는 배경에서 뺌."""
    import json

    return sorted({p["path"] for p in json.loads(dump.read_text())["parts"]
                   if p["path"].startswith("Scenery/Beach/Lighthouse")})


def root_tips(parts, hero, height):
    """밑동에서 비스듬히 뻗은 막대(뿌리)의 땅 쪽 끝 점들."""
    tips = []
    for p in parts:
        if p["s"] != "Block" or p["p"][1] > height * 0.15:
            continue
        k = int(np.argmax(p["z"]))
        if p["z"][k] < height * 0.08:
            continue
        m = p["m"]
        axis = np.array([m[k], m[3 + k], m[6 + k]])
        if abs(axis[1]) < 0.1 or abs(axis[1]) > 0.95:  # 비스듬한 것만
            continue
        ends = [np.array(p["p"]) + axis * p["z"][k] / 2, np.array(p["p"]) - axis * p["z"][k] / 2]
        tips.append(min(ends, key=lambda e: e[1]))
    return tips


def hero_stage(cfg):
    lid = cfg["id"]
    ang = math.radians(cfg["angle"])
    u = np.array([math.cos(ang), 0, math.sin(ang)])
    hero = u * cfg["radius"]
    height = hero_height(lid, cfg["size"], cfg["yaw"])
    cam = frame_camera(hero, height, cfg["eye_h"], cfg["fov"], cfg["base_y"], cfg["top_y"], (u[0], u[2]))
    size = cfg["size"]
    foot = size * 0.5
    model_yaw = st.yaw_facing((-u[0], -u[2])) + cfg["yaw"]
    stage = {"models": [{"folder": "Hero", "id": lid, "size": size, "cf": st.cf(hero, st.ry(model_yaw)),
                         "dropBase": True}]}
    dump = st.world_dump(stage)
    clear_until = float(np.dot(hero - cam.eye, cam.f)) + foot * 3
    layers = [
        {"name": "bg", "terrain": True, "exclude": ["Store"] + lighthouse_paths(dump),
         "clear": {"until": clear_until, "margin": 1.6}, "clearScreen": cfg.get("clear_screen", [])},
        {"name": "hero_mask", "terrain": False, "include": ["Store/Hero"]},
        {"name": "hero_sh", "terrain": False, "include": ["Store/Hero"],
         "shadow": {"x": hero[0], "y": 0.02, "z": hero[2], "size": 220, "opacity": 0.45}},
    ]
    L = st.render_layers(stage, cam, layers, size=(W * SS, H * SS))

    # 3D 소품 --------------------------------------------------------------------------------
    hero_parts = [p for p in st.dump_parts(dump, "Store/Hero/") if p["t"] < 0.999]
    to_cam = cam.eye - hero
    front_deg = math.degrees(math.atan2(to_cam[2], to_cam[0]))
    rock_col = cfg["rock_color"]
    rocks = st.rocks3d(hero, foot * cfg.get("rocks_r", 1.22), 15, size * 0.15, seed=11, color=rock_col,
                       skip_angles=[(front_deg, 16)])
    if cfg.get("tip_rocks"):  # 뿌리 끝(판자처럼 보이는 곳)을 바위로 덮음: 밑동 둘레 비스듬한 막대의 낮은 끝
        rnd = random.Random(5)
        for i, tip in enumerate(root_tips(hero_parts, hero, height)):
            s = size * rnd.uniform(0.15, 0.19)
            p = tip + (tip - hero) * np.array([1, 0, 1]) * 0.05
            p[1] = s * 0.3
            rocks.append({"p": p.round(3).tolist(), "size": [s * 1.3, s * 0.95, s * 1.15],
                          "rot": [rnd.uniform(-10, 10), rnd.uniform(0, 360), rnd.uniform(-10, 10)],
                          "col": [v / 255 * rnd.uniform(0.85, 1.0) for v in rock_col], "mat": "Slate", "seed": 900 + i})
    hb = cam.project([hero, hero + np.array([0, height, 0])])
    half_w = cam.scale_at(hb[0][2]) * foot * 1.3

    def over_hero(sx, sy):
        return abs(sx - hb[0][0]) < half_w and hb[1][1] < sy < hb[0][1]

    cols = cfg["crystal_colors"]
    cfront, cback = st.crystals3d(hero, cfg.get("crystals", 26), (foot * 1.4, foot * 3.6), (2, height * 0.95),
                                  size * cfg.get("crystal_len", 0.3), 12, cols, cam, avoid=over_hero, min_y=340)
    # 떠오른 돌 조각(전체의 15% 쯤): 결정 사이사이
    rnd = random.Random(17)
    dfront, dback = [], []
    for item in (cfront[::7] + cback[::7]):
        target = dfront if item in cfront else dback
        s = item["len"] * 0.4
        target.append({"p": item["p"], "size": [s * 1.2, s * 0.8, s], "rot": [rnd.uniform(0, 360)] * 3,
                       "col": [v / 255 * 0.9 for v in rock_col], "mat": "Slate", "seed": 700 + len(target)})
    cfront = [c for c in cfront if c not in cfront[::7]]
    cback = [c for c in cback if c not in cback[::7]]
    near = []
    base_depth = float(np.dot(hero - cam.eye, cam.f))
    for j, (sx, sy, dk, lk) in enumerate(cfg["near"]):
        depth = base_depth * dk
        p = world_at(cam, sx, sy, depth)
        out = p - (hero + np.array([0, height * 0.4, 0]))
        near.append({"p": p.round(3).tolist(), "len": size * lk, "radius": size * lk * 0.34, "flat": 0.9,
                     "rot": st._outward_rot(out, rnd.uniform(0, 360)), "seed": 800 + j, "shape": "chunk",
                     "col": [v / 255 for v in cols[j % len(cols)]], "rough": 0.3})
    av = cfg["avatar"]
    av_base = ground_from_screen(cam, av["sx"], av["sy"])
    av_depth = float(np.dot(av_base - cam.eye, cam.f))
    av_scale = av["height_px"] / (5.6 * cam.scale_at(av_depth))  # 화면에서 원하는 키가 되도록(원근은 그대로)
    to_hero = (hero - av_base)[[0, 2]]
    to_c = (cam.eye - av_base)[[0, 2]]
    look = to_hero / np.linalg.norm(to_hero) * (1 - av["face"]) + to_c / np.linalg.norm(to_c) * av["face"]
    avatar = st.to3d(st.avatar("Avatar", av_base, st.yaw_facing(look), av["pose"], scale=av_scale))

    sun = st.sun_direction()
    if cfg.get("sun_side"):  # 옆에서 오는 빛(흰 면마다 밝기가 달라 모양이 보이게): 화면 오른쪽 뒤 위
        k = cfg["sun_side"]
        sun = (cam.r * k - cam.f * 0.35 + np.array([0, 0.75, 0])).tolist()
    side = cam.r
    back = cam.f
    a2 = [v / 255 for v in cfg["aura2"]]
    rim_l = (back * 0.8 - side * 0.7 + np.array([0, 0.3, 0])).tolist()
    rim_r = (back * 0.8 + side * 0.7 + np.array([0, 0.3, 0])).tolist()
    scene = {
        "size": [W * SS, H * SS],
        "camera": st.cam3d(cam),
        "light": {"sun": sun, "sunColor": [1, 0.97, 0.9], "sunIntensity": 1.0, "hemiSky": [0.8, 0.92, 1],
                  "hemiGround": [0.5, 0.6, 0.55], "hemiIntensity": 0.8,
                  "rims": [{"dir": rim_l, "color": a2, "intensity": 0.45}, {"dir": rim_r, "color": a2, "intensity": 0.4}],
                  "shadowCenter": (hero + np.array([0, height * 0.4, 0])).tolist(), "shadowBox": height * 0.75},
        "rim": {"color": a2, "power": 2.4, "strength": 0.75},
        "objects": [
            {"tag": "hero", "rim": 0.12, "parts": hero_parts},
            {"tag": "rocks", "rocks": rocks, "rim": 0.25},
            {"tag": "cfront", "shards": cfront, "rim": 0.8},
            {"tag": "cback", "shards": cback, "rim": 0.8},
            {"tag": "dfront", "rocks": dfront, "castShadow": False, "rim": 0.4},
            {"tag": "dback", "rocks": dback, "castShadow": False, "rim": 0.4},
            {"tag": "near", "shards": near, "rim": 1.3},
            {"tag": "avatar", "parts": avatar, "castShadow": False},
        ],
        "layers": [
            {"name": "hero", "draw": ["hero"], "occlude": ["rocks"]},
            {"name": "rocks", "draw": ["rocks"], "occlude": ["hero"]},
            {"name": "sback", "draw": ["cback", "dback"], "occlude": ["hero", "rocks"]},
            {"name": "sfront", "draw": ["cfront", "dfront"], "occlude": ["rocks"]},
            {"name": "snear", "draw": ["near"]},
            {"name": "avatar", "draw": ["avatar"]},
        ],
    }
    L.update(st.render3d(scene))
    fruits = [p["p"] for p in hero_parts if p["mat"] == "Neon" and p["s"] == "Ball"]
    return cam, hero, height, (av_base, av_scale), L, fruits


def tint(im: Image.Image, mul) -> Image.Image:
    a = fx.arr(im)
    a[..., :3] *= np.array(mul, np.float32)
    return fx.img(a)


def add_crystals(im, layer, aura2, glow_col, blur=0.0, glow_k=1.0):
    """결정: 바깥 빛(민트) + 본체 + 면 경계·윤곽에 밝은 민트 선(빛나는 모서리)."""
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    a = fx.alpha_of(layer)
    im = fx.add(im, fx.glow(a, 14, glow_col, 1.3, spread=1), 0.8 * glow_k)
    # 그늘 면이 까만 판처럼 보이지 않게: 어두운 면을 결정 빛깔(aura2 의 짙은 색) 쪽으로 들어 올림
    la = fx.arr(layer)
    lum = la[..., :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lift = np.clip((0.32 - lum) / 0.32, 0, 1)[..., None] * 0.55
    la[..., :3] = la[..., :3] * (1 - lift) + np.array(darken(aura2, 0.45), np.float32) / 255 * lift
    layer = fx.img(la)
    im = fx.over(im, layer)
    if not blur:
        e = fx.facet_edges(layer, 0.08, 0.08)
        im = fx.add(im, fx.glow(e, 3, aura2, 1.2), 0.7)
        im = fx.over(im, fx.solid((W, H), lighten(aura2, 0.3), e * 0.8))
    else:
        im = fx.add(im, edge_light(layer, lighten(aura2, 0.4), (4, 4), 1.2, 2), 0.8)
    return im


def ground_fx(im, cam, hero, foot, cfg):
    """발밑: 어두운 구덩이 + 소용돌이 + 멀리 뻗는 빛나는 금 + 두꺼운 마법진(민트 + 흰 심 + 빛)."""
    aura, aura2 = cfg["aura"], cfg["aura2"]
    crater_c = cfg["crater"]
    crater = fx.warp_quad(fx.radial((512, 512), (256, 256), 256, [(0, crater_c + (240,)), (0.7, crater_c + (230,)),
                                                                   (0.88, crater_c + (140,)), (1, crater_c + (0,))]),
                          ground_quad(cam, hero, foot * 3.1), (W, H))
    im = fx.over(im, crater)
    vort = fx.vortex(1024, center=darken(crater_c, 0.3), swirl=aura, arms=7, twist=3.0, seed=4, edge=0.95)
    im = fx.over(im, fx.warp_quad(vort, ground_quad(cam, hero, foot * 2.2), (W, H)), opacity=0.8)
    # 금: 구덩이 가장자리에서 화면 폭의 30~40% 까지
    dark, core = fx.cracks(1800, seed=31, count=10, inner=0.1, reach=(0.75, 1.0), width=3.4)
    q = ground_quad(cam, hero, foot * 6.0)
    dark_w, core_w = fx.alpha_of(fx.warp_quad(dark, q, (W, H))), fx.alpha_of(fx.warp_quad(core, q, (W, H)))
    im = fx.over(im, fx.solid((W, H), darken(crater_c, 0.2), dark_w * 0.9))
    im = fx.add(im, fx.glow(core_w, 7, aura2, 1.8), 0.9)
    im = fx.over(im, fx.solid((W, H), lighten(aura2, 0.3), np.clip(core_w * 1.4, 0, 1)))
    im = fx.add(im, fx.solid((W, H), WHITE, np.clip((core_w - 0.5) * 2, 0, 1)), 0.6)
    # 마법진: 두꺼운 민트 몸 + 가는 흰 심 + 번짐
    q2 = ground_quad(cam, hero, foot * 2.9)
    body = fx.alpha_of(fx.warp_quad(fx.magic_circle(2048, WHITE, seed=5, width=3.6), q2, (W, H)))
    thin = fx.alpha_of(fx.warp_quad(fx.magic_circle(2048, WHITE, seed=5, width=1.3), q2, (W, H)))
    im = fx.add(im, fx.glow(body, 9, aura2, 1.0), 0.55)
    im = fx.over(im, fx.solid((W, H), aura2, np.clip(body * 1.3, 0, 1)))
    im = fx.over(im, fx.solid((W, H), (240, 255, 250), thin))
    return im


def add_wisps(im, a, ink, edge_col, k=1.0):
    """먹물 연기: 짙은 색 몸 + 가장자리 빛(색)."""
    im = fx.over(im, fx.solid((W, H), ink, np.clip(a * 0.92 * k, 0, 1)))
    rim = np.clip(fx.blur_alpha(a, 4) - a * 0.9, 0, 1)
    return fx.add(im, fx.solid((W, H), edge_col, rim), 0.8 * k)


def thumb_hero(n):
    cfg = HEROES[n]
    lid = cfg["id"]
    n = cfg.get("seed", n)
    cam, hero, height, (av_base, av_scale), L, fruits = hero_stage(cfg)
    lay = {k: load_layer(v) for k, v in L.items()}
    aura, aura2, core_col = cfg["aura"], cfg["aura2"], cfg["core"]
    base_px = cam.project([hero])[0]
    core = cam.project([hero + np.array([0, height * cfg["ray_center"], 0])])[0]
    top_px = cam.project([hero + np.array([0, height, 0])])[0]
    foot = cfg["size"] * 0.5

    # 하늘 + 구름 + 배경(진짜 섬: 풀밭·바다)
    horizon = cam.project([cam.eye + np.array([cam.f[0], 0, cam.f[2]]) * 3000])[0][1]
    im = fx.linear((W, H), cfg["sky"])
    ctop, cbottom = cfg["cloud_colors"]
    for (x, dy, width, seed, alpha) in cfg["clouds"]:
        c = fx.cloud(width, seed=seed, top=ctop, bottom=cbottom)
        im = fx.over(im, c, (x - c.width / 2, horizon + dy - c.height), alpha)
    bg = lay["bg"]
    if cfg.get("bg_desat"):  # 노을 장면: 풀밭 초록을 눌러 보라·금 두 색이 주인공이 되게
        ba = fx.arr(bg)
        gray = ba[..., :3].mean(-1, keepdims=True)
        ba[..., :3] = gray + (ba[..., :3] - gray) * (1 - cfg["bg_desat"])
        bg = fx.img(ba)
    if cfg["bg_tint"]:
        bg = tint(bg, cfg["bg_tint"])
    im = fx.over(im, bg)

    # 뒤 빛: 색 오라(덮기 — 하얗게 날아가지 않게) + 햇살(땅 위에서는 약하게)
    ground = fx.alpha_of(lay["bg"])
    ground_fade = 1 - 0.85 * ground * np.clip((np.arange(H)[:, None] - base_px[1] + 60) / 120, 0, 1)
    ak = cfg.get("aura_k", 1.0)
    im = fx.over(im, fx.radial((W, H), core[:2], 760, [(0, aura + (int(170 * ak),)), (0.4, aura + (int(95 * ak),)),
                                                        (1, aura + (0,))]))
    if cfg.get("purple_back"):  # 흰 봉우리 뒤는 짙은 보라(흰 것이 흰 빛에 묻히지 않게)
        pb = cfg["purple_back"]
        im = fx.over(im, fx.radial((W, H), (top_px[0], top_px[1] + (base_px[1] - top_px[1]) * 0.3), 520,
                                   [(0, pb + (230,)), (0.55, pb + (150,)), (1, pb + (0,))], squash=1.2))
    im = fx.add(im, fx.multiply_alpha(fx.rays((W, H), core[:2], count=26, color=lighten(aura, 0.45), width=0.4,
                                              seed=21, falloff=1.15, inner=60), ground_fade), 0.45)
    im = fx.add(im, fx.multiply_alpha(fx.rays((W, H), core[:2], count=12, color=WHITE, width=0.16, seed=22,
                                              falloff=1.7, inner=90), ground_fade), 0.25)
    im = fx.over(im, fx.radial((W, H), core[:2], 300, [(0, core_col + (150,)), (1, core_col + (0,))]))

    # 땅 효과 + 주인공 그림자
    im = ground_fx(im, cam, hero, foot, cfg)
    im = fx.over(im, shadow_only(lay["hero_sh"], lay["hero_mask"], 0.6))

    # 먹물 불꽃(뒤) — 빛 가운데에 어두운 대비(참고 그림의 검은 기운)
    wk = cfg.get("wisps", 1.0)
    col_w = foot * 1.25 * cam.scale_at(base_px[2])
    # 먹물: 위로 튀는 들쭉날쭉한 얼룩(가는 머리카락 같은 줄이 아니게 — 세로로 조금만 늘임)
    wb = np.maximum(fx.ink_flames((W, H), (base_px[0], base_px[1] - 10), (top_px[0], top_px[1] + 40), col_w, seed=3 + n,
                                  scale=40, threshold=0.56, stretch=0.45, turns=0.6, soft=0.03),
                    fx.ink_flames((W, H), (base_px[0], base_px[1] - 10), (top_px[0], top_px[1] + 40), col_w, seed=8 + n,
                                  scale=60, threshold=0.56, stretch=0.8, turns=0.3, soft=0.03))
    im = add_wisps(im, wb, cfg["ink"], aura, wk)

    # 리본(뒤) + 결정(뒤)
    rib = [
        {"phase": 0.3, "turns": 1.25, "r0": foot * 2.4, "r1": foot * 1.2, "y0": 1, "y1": height * 0.8, "width": 58},
        {"phase": 3.2, "turns": 1.05, "r0": foot * 2.1, "r1": foot * 1.4, "y0": 4, "y1": height * 0.6, "width": 42},
    ]
    for r_ in rib:
        r_["width"] *= cfg.get("ribbon_k", 1.0)
    rb, rf = ribbons(cam, hero, rib)
    im = add_ribbon(im, rb, aura2, deep=darken(aura, 0.35))
    im = add_crystals(im, lay["sback"], aura2, aura)

    # 바위: 발밑 그림자 + 본체 + 금 + 빛 쪽 테두리
    ra = fx.alpha_of(lay["rocks"])
    sh = fx.blur_alpha(np.roll(fx.dilate(ra, 6), 10, axis=0), 12)
    im = fx.over(im, fx.solid((W, H), darken(cfg["crater"], 0.3), np.clip(sh * (1 - ra) * 0.75, 0, 1)))
    im = fx.over(im, lay["rocks"])
    cr = fx.crack_lines((W, H), 700, seed=9, length=(14, 44), width=2.0) * fx.erode(ra, 4)
    im = fx.over(im, fx.solid((W, H), (18, 20, 32), np.clip(cr * 0.85, 0, 1)))
    im = fx.add(im, edge_light(lay["rocks"], lighten(aura2, 0.2), (0, -5), 0.9, 1.5), 0.6)

    # 주인공: 바깥 빛(색) + 본체 + 양옆 민트 테두리 + 열매 빛
    im = fx.add(im, fx.glow(lay["hero"], 26, aura, 1.3, spread=6), 0.7)
    hero_layer = lay["hero"]
    if cfg.get("white_guard"):  # 흰 대리석이 하얗게 날아가지 않게 밝은 곳을 눌러 줌 + 노을빛
        ha = fx.arr(hero_layer)
        rgb = ha[..., :3] * np.array([1.0, 0.93, 0.9], np.float32)
        ha[..., :3] = np.where(rgb > 0.7, 0.7 + (rgb - 0.7) * 0.55, rgb)
        hero_layer = fx.img(ha)
    im = fx.over(im, hero_layer)
    im = fx.add(im, edge_light(lay["hero"], aura2, (-4, 3), 1.0, 1.2), 0.6)
    im = fx.add(im, edge_light(lay["hero"], aura2, (4, 3), 1.0, 1.2), 0.6)
    if cfg.get("base_glow"):  # 밑동 빛: 판자처럼 보이는 뿌리 이음매를 구덩이 빛 속에 묻음
        bw = foot * 1.5 * cam.scale_at(base_px[2])
        im = fx.add(im, fx.radial((W, H), (base_px[0], base_px[1] - bw * 0.12), bw,
                                  [(0, (225, 255, 245, 255)), (0.35, aura2 + (190,)), (1, aura2 + (0,))], squash=0.4),
                    cfg["base_glow"])
    if fruits:
        fp = cam.project(fruits)
        r0 = cam.scale_at(fp[0][2]) * cfg["size"] * 0.07 / 2  # 열매 반지름(px)
        for (x, y, _) in fp:
            im = fx.add(im, fx.radial((W, H), (x, y), r0 * 2.6, [(0, (255, 255, 230, 255)), (0.3, (255, 245, 160, 170)),
                                                                  (1, (255, 230, 120, 0))]), 0.3)

    # 앞: 먹물 연기(옅게), 리본, 결정, 알갱이, 반짝이
    wf = fx.ink_flames((W, H), (base_px[0], base_px[1] - 10), (top_px[0], top_px[1] + 120), col_w * 1.1, seed=21 + n,
                       scale=40, threshold=0.62, stretch=0.45, turns=0.6, soft=0.03)
    wf *= 1 - fx.dilate(lay["hero"], 5)
    im = add_wisps(im, wf, cfg["ink"], aura, 0.9 * wk)
    im = add_ribbon(im, rf, aura2, deep=darken(aura, 0.35), front=True)
    im = add_crystals(im, lay["sfront"], aura2, aura)
    im = fx.add(im, fx.particles((W, H), core[:2], 90, (1.5, 4.5), lighten(aura2, 0.6), seed=41, spread=(0.05, 0.42),
                                 glow_color=aura2), 1.0)
    hx0, hx1 = top_px[0] - 560, top_px[0] + 560
    im = scatter_sparkles(im, [(hx0, top_px[1] + 60, top_px[0] - 230, base_px[1] - 60),
                               (top_px[0] + 230, top_px[1] + 60, hx1, base_px[1] - 60)], 14, seed=51,
                          color=lighten(aura2, 0.7), glow_color=aura2, rmin=7, rmax=28)
    im = bloom(im, threshold=0.95, strength=0.15,
               exclude=fx.dilate(lay["hero"], 3) if cfg.get("white_guard") else None)
    im = add_crystals(im, lay["snear"], aura2, aura, blur=3.0, glow_k=0.6)

    # 아바타(빛 뒤에 맨 앞): 발밑 접지 그림자 + 몸 + 주인공 쪽 가는 테두리 빛
    av_px = cam.project([av_base])[0]
    side = 1 if base_px[0] > av_px[0] else -1
    aa = fx.alpha_of(lay["avatar"])
    foot_sh = fx.warp_quad(fx.radial((256, 256), (128, 128), 128, [(0, (0, 0, 0, 200)), (0.5, (0, 0, 0, 120)),
                                                                   (1, (0, 0, 0, 0))]),
                           ground_quad(cam, av_base, 2.4 * av_scale), (W, H))
    im = fx.over(im, foot_sh, opacity=0.8)
    im = fx.over(im, lay["avatar"])
    im = fx.add(im, edge_light(lay["avatar"], lighten(aura2, 0.35), (3 * side, 0), 1.0, 1.0), 0.8)

    im = grade(im, 1.1, 1.05, 0.2)

    # 글자: 큰 확률 숫자(기울임 + 좁은 자간) + 숫자 가장자리 반짝이 + 이름 알약(등급 뱃지)
    im, box = headline(im, odds(lid), cfg["number"], y=12, width=cfg.get("number_w", 1640),
                       outline_color=cfg["number_outline"], tracking=-6, slant=0.12)
    x0, y0, x1, y1 = box
    for (x, y, r) in [(x0 + 30, y0 + 40, 40), (x0 + (x1 - x0) * 0.46, y1 - 18, 30), (x0 + (x1 - x0) * 0.7, y0 + 6, 30),
                      (x0 + (x1 - x0) * 0.23, y1 + 34, 22), (120, 520, 34), (1800, 330, 28)]:
        s = fx.sparkle_sprite(r, WHITE, aura2)
        im = fx.over(im, s, (x - s.width / 2, y - s.height / 2))
    t = tier(lid)
    pill = fx.badge_pill([(tier_en(lid), INK, t[2]), (LANDMARKS[lid]["en"].upper(), t[2], None)], "luckiest", 60,
                         bg=cfg.get("pill_bg", (16, 30, 38)), border=t[2], outline=INK)
    x = W - pill.width - 36 if cfg["pill_side"] == "right" else 36
    im = fx.over(im, pill, (x, H - pill.height - 30))
    return im


# 2: 환생할 때마다 행운 ×2 -----------------------------------------------------------------------------
# 하늘로 오르는 계단 10칸(= 환생 10번, 칸마다 행운 ×2) 꼭대기에서 두 팔을 든 아바타 + 게임 행운 아이콘(클로버, art/src/clover.svg)
# + 큰 배율 숫자 "x1,024 LUCK!"(Config: REBIRTH_LUCK_MULT ^ MAX_REBIRTHS) + "x2 EVERY REBIRTH!".
# 3D(계단·아바타)는 scene3d.js, 카메라 공간에서 화면 자리·깊이로 놓음(world_at).
STEP_COLORS = [(70, 150, 255), (90, 120, 255), (130, 100, 255), (170, 90, 250), (215, 85, 220), (245, 85, 160),
               (255, 110, 90), (255, 150, 50), (255, 190, 40), (255, 214, 70)]  # 아래(파랑) → 꼭대기(금)
CHEER = {"head": (-8, 0), "arm_r": (160, 40), "arm_l": (160, 40), "leg_l": 10, "leg_r": -6, "mouth": "o"}  # 두 팔 V + 놀란 입


def rebirth_numbers():
    """(칸마다 행운 배율, 최대 환생 수, 최대 배율) — Config.luau 에서."""
    mult = config_number("REBIRTH_LUCK_MULT")
    count = int(config_number("MAX_REBIRTHS"))
    return mult, count, int(mult ** count)


def svg_icon(name: str, px: int) -> Image.Image:
    """게임 아이콘(art/src/<name>.svg)을 원하는 크기로(선명하게)."""
    import resvg_py

    data = bytes(resvg_py.svg_to_bytes(svg_path=str(ROOT / "art/src" / f"{name}.svg"), width=px, height=px))
    return Image.open(io.BytesIO(data)).convert("RGBA")


def rebirth_stage(steps: int):
    cam = st.Camera((0, 0, 0), (0, 0, -1), 40, (W, H))
    # 칸 자리(화면 x, 윗면 y, 깊이): 가운데 아래에서 오른쪽 위로, 올라갈수록 조금씩 뒤로
    pts = []
    for i in range(steps):
        t = i / (steps - 1)
        sx = 860 + 600 * t + 40 * math.sin(t * math.pi)
        sy = 1060 - 470 * t ** 0.92
        depth = 62 + 10 * t
        pts.append((sx, sy, depth))
    prims = []
    tops = []
    for i, (sx, sy, depth) in enumerate(pts):
        top = world_at(cam, sx, sy, depth)
        big = i == steps - 1
        size = [10.5, 2.6, 8.0] if big else [6.6, 2.2, 5.6]
        center = top - np.array([0, size[1] / 2, 0])
        col = [c / 255 for c in STEP_COLORS[i * (len(STEP_COLORS) - 1) // max(1, steps - 1)]]
        prims.append({"type": "roundbox", "p": center.round(4).tolist(), "size": size, "radius": 0.6,
                      "rot": [0, -28, 0], "col": col, "rough": 0.35})
        tops.append(top)
    av_base = tops[-1] + np.array([0.2, 0, -0.4])
    av_scale = 300 / (5.6 * cam.scale_at(pts[-1][2]))
    avatar = st.to3d(st.avatar("Avatar", av_base, st.yaw_facing((0.25, 1)), CHEER, scale=av_scale))
    scene = {
        "size": [W * SS, H * SS],
        "camera": st.cam3d(cam),
        "light": {"sun": [-0.55, 0.75, 0.55], "sunColor": [1, 0.96, 0.9], "sunIntensity": 1.0,
                  "hemiSky": [0.85, 0.85, 1], "hemiGround": [0.6, 0.5, 0.7], "hemiIntensity": 0.85,
                  "rims": [{"dir": [0.7, 0.3, -0.6], "color": [1, 0.85, 0.5], "intensity": 0.6}],
                  "shadowCenter": tops[-1].tolist(), "shadowBox": 40},
        "rim": {"color": [1, 0.9, 0.6], "power": 2.2, "strength": 0.5},
        "objects": [
            {"tag": "steps", "prims": prims, "rim": 0.45},
            {"tag": "avatar", "parts": avatar, "castShadow": True},
        ],
        "layers": [
            {"name": "steps", "draw": ["steps"], "shadow": ["avatar"]},
            {"name": "avatar", "draw": ["avatar"]},
        ],
    }
    L = st.render3d(scene)
    screen_tops = [cam.project([p])[0] for p in tops]
    av_px = cam.project([av_base, av_base + np.array([0, 5.6 * av_scale, 0])])
    return cam, L, screen_tops, av_px


def thumb_rebirth():
    mult, steps, top_mult = rebirth_numbers()
    cam, L, tops, av_px = rebirth_stage(steps)
    lay = {k: load_layer(v) for k, v in L.items()}
    (fx0, fy0, _), (hx, hy, _) = av_px
    clover_c = (min(hx + 290, W - 235), max(hy + 10, 240))  # 클로버 가운데(아바타 오른쪽 위, 화면 안)

    # 하늘: 짙은 보라 → 자홍 → 금빛 지평 + 클로버에서 뿜는 햇살 + 집중선 + 아래 구름
    im = fx.linear((W, H), [(0, (46, 22, 120)), (0.45, (120, 40, 170)), (0.78, (236, 96, 150)), (1, (255, 170, 110))])
    im = fx.over(im, fx.radial((W, H), clover_c, 900, [(0, (255, 236, 150, 230)), (0.3, (255, 190, 90, 140)),
                                                        (1, (255, 150, 80, 0))]))
    im = fx.add(im, fx.rays((W, H), clover_c, count=28, color=(255, 240, 180), width=0.42, seed=201, falloff=1.0,
                            inner=120), 0.5)
    im = fx.add(im, fx.rays((W, H), clover_c, count=12, color=WHITE, width=0.14, seed=202, falloff=1.5, inner=160), 0.3)
    # 구름 무늬(seed)는 위가 잘리지 않는 것만(fx.cloud 는 seed 에 따라 윗부분이 그림 밖으로 나가 평평하게 잘림)
    for (x, y, width, seed, alpha) in [(150, 1130, 640, 204, 0.95), (620, 1150, 560, 210, 0.9), (1800, 1120, 560, 213, 0.9),
                                       (1250, 1170, 520, 220, 0.85)]:
        c = fx.cloud(width, seed=seed, top=(255, 236, 246), bottom=(214, 150, 210))
        im = fx.over(im, c, (x - c.width / 2, y - c.height), alpha)

    # 계단: 칸 색 번짐 + 본체 + 윗면 빛 + 칸 사이 빛 줄기(오르는 길)
    sa = fx.alpha_of(lay["steps"])
    im = fx.add(im, fx.glow(sa, 26, (255, 200, 120), 1.2, spread=4), 0.6)
    path = Image.new("L", (W * SS, H * SS), 0)
    ImageDraw.Draw(path).line([(x * SS, (y - 8) * SS) for (x, y, _) in tops], fill=255, width=int(10 * SS), joint="curve")
    pa = fx.blur_alpha(mask_img(path), 10)
    im = fx.add(im, fx.solid((W, H), (255, 240, 170), pa), 0.3)
    im = fx.over(im, lay["steps"])
    im = fx.add(im, edge_light(lay["steps"], (255, 250, 220), (0, 6), 1.3, 1.5), 0.9)
    for i, (x, y, _) in enumerate(tops):  # 칸마다 윗면 반짝 + 위로 갈수록 강한 빛
        k = (i + 1) / steps
        im = fx.add(im, fx.radial((W, H), (x, y), 50 + 80 * k, [(0, (255, 250, 210, int(90 + 110 * k))),
                                                              (1, (255, 230, 150, 0))], squash=0.4), 0.25 + 0.5 * k)
    # 꼭대기: 금빛 기둥
    tx, ty, _ = tops[-1]
    ys2, xs2 = np.mgrid[0:H, 0:W].astype(np.float32)
    beam = np.clip(1 - np.abs(xs2 - tx) / 150, 0, 1) ** 1.5 * np.clip((ty - ys2) / 40, 0, 1) * np.clip(1 - (ty - ys2) / 700, 0, 1)
    im = fx.add(im, fx.solid((W, H), (255, 236, 160), beam * 0.5))

    # 클로버(게임 행운 아이콘): 빛 + 흰 테두리 빛 + 본체
    clover = svg_icon("clover", 460)
    clover = fx.rotate(clover, -8)
    cx0, cy0 = clover_c[0] - clover.width / 2, clover_c[1] - clover.height / 2
    ca = np.zeros((H, W), np.float32)
    ch = fx.alpha_of(clover)
    x0i, y0i = int(cx0), int(cy0)
    xa, ya = max(0, x0i), max(0, y0i)
    xb, yb = min(W, x0i + clover.width), min(H, y0i + clover.height)
    ca[ya:yb, xa:xb] = ch[ya - y0i:yb - y0i, xa - x0i:xb - x0i]
    im = fx.add(im, fx.glow(ca, 40, (170, 255, 150), 1.4, spread=10), 0.9)
    im = fx.over(im, fx.solid((W, H), (255, 255, 230), np.clip(fx.dilate(ca, 8) - ca, 0, 1)))
    im = fx.over(im, clover, (cx0, cy0))

    # 아바타: 몸 + 금빛 테두리
    im = fx.over(im, lay["avatar"])
    im = fx.add(im, edge_light(lay["avatar"], (255, 236, 170), (-4, 0), 1.0, 1.2), 0.8)
    im = fx.add(im, edge_light(lay["avatar"], (255, 236, 170), (4, 0), 1.0, 1.2), 0.8)

    # 반짝이 + 빛 알갱이
    avoid = np.maximum(fx.dilate(lay["avatar"], 10), fx.dilate(ca, 10))
    im = scatter_sparkles(im, [(960, 110, 1880, 760)], 22, seed=221, color=WHITE, glow_color=(255, 220, 140), rmin=8,
                          rmax=34, big=[(clover_c[0] - 200, clover_c[1] - 190, 44), (clover_c[0] + 60, clover_c[1] + 330, 30)],
                          avoid=avoid)
    im = fx.add(im, fx.particles((W, H), clover_c, 90, (1.5, 4.5), (255, 245, 200), seed=222, spread=(0.05, 0.5),
                                 glow_color=(255, 210, 120)), 1.0)
    im = grade(im, 1.1, 1.05, 0.2)

    # 글자: 큰 배율(금) + LUCK!(클로버 초록) + 작은 줄
    gold = [(0, (255, 252, 200)), (0.42, (255, 222, 80)), (0.78, (255, 160, 30)), (1, (226, 104, 18))]
    num = fitted_text(f"x{top_mult:,}", 900, "luckiest", tracking=-4, fill_stops=gold, outline_color=(74, 24, 60),
                      depth_color=(40, 10, 34), gloss=0.35)
    num = fx.rotate(num, 4)
    nx, ny = 60, 30
    im = drop_shadow(im, num, (nx, ny), 10, 0.5, (4, 12))
    im = fx.over(im, num, (nx, ny))
    green = [(0, (240, 255, 150)), (0.45, (130, 245, 80)), (0.8, (40, 200, 70)), (1, (20, 150, 60))]
    im, box = title_line(im, "LUCK!", (nx + 60, ny + num.height - 40), size=260, stops=green, outline=(12, 56, 30),
                         align="left", tilt=4)
    sub = f"x{mult:g} EVERY REBIRTH!"
    im, _ = title_line(im, sub, (nx + 40, box[3] + 30), size=92,
                       stops=[(0, (255, 255, 255)), (1, (200, 255, 245))], outline=(40, 16, 70), align="left", tilt=4)
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


# (명소, 화면 x, 화면 y(모형 가운데), 화면 키(px), 깊이, 좌우 돌림, 기울임, 앞으로 숙임)
# 가장 희귀한 것(알렉산드리아 등대 1/15,000)을 가운데 위에 가장 크게, 흔한 것일수록 바깥·작게. 받침(판)은 뺌.
COLLECT = [
    ("alexandria", 960, 420, 350, 100, 24, -4, 10),
    ("moai", 640, 500, 205, 104, -30, 4, 8),  # 얼굴이 보이게(앞 = 카메라 쪽, 비스듬히 — 눈썹·코 옆모습)
    ("pyramid", 1275, 500, 175, 104, 28, -6, 24),
    ("greatwall", 1545, 725, 215, 100, -90, 8, 35),  # 위에서 비스듬히: 성가퀴 달린 성벽 길이 대각선으로 망루까지
    ("tajmahal", 375, 720, 215, 100, -20, -7, 10),
    ("colosseum", 1720, 420, 150, 100, 18, 8, 30),
    ("eiffel", 150, 430, 265, 100, -16, -9, 6),
    ("liberty", 1805, 760, 250, 100, 26, 9, 6),
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
    for (lid, sx, sy, hpx, depth, yaw, roll, pitch) in COLLECT:
        size = hpx / (ratio[lid] * cam.scale_at(depth))
        center = world_at(cam, sx, sy, depth)
        R = st.rz(roll) @ st.rx(pitch) @ st.ry(yaw)  # 카메라(+Z) 쪽을 보고 조금 돌리고 기울임
        R = R @ st.ry(180)  # 모형 앞(-Z)이 카메라(+Z)를 보게
        h = ratio[lid] * size
        pivot = center - R @ np.array([0, h / 2, 0])
        models.append({"folder": f"L_{lid}", "id": lid, "size": size, "cf": st.cf(pivot, R), "dropBase": True})
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
    # 왼쪽 아래 작은 아바타(뒤에서, 올려다봄) — scene3d 로 같은 카메라
    av_depth = 60
    av_base = world_at(cam, 175, 1150, av_depth)
    av_scale = 330 / (5.6 * cam.scale_at(av_depth))
    look = world_at(cam, 960, 420, 100) - av_base
    avatar = st.to3d(st.avatar("Avatar", av_base, st.yaw_facing((look[0], look[2])),
                               {"head": (-30, 6), "arm_r": (150, 20), "arm_l": (20, 18), "face": False}, scale=av_scale))
    scene = {"size": [W * SS, H * SS], "camera": st.cam3d(cam),
             "light": {"sun": [-0.4, 0.8, 0.6], "hemiIntensity": 0.85, "shadowCenter": av_base.tolist(), "shadowBox": 20},
             "objects": [{"tag": "avatar", "parts": avatar, "castShadow": False}],
             "layers": [{"name": "avatar", "draw": ["avatar"]}]}
    L.update(st.render3d(scene))
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


def motion_blur(a: np.ndarray, direction, length=40, steps=12) -> np.ndarray:
    """알파를 direction 쪽 뒤로 끌어 번지게(움직임 흐림)."""
    d = np.array(direction, float)
    d /= np.linalg.norm(d) or 1
    out = np.zeros_like(a)
    for i in range(steps):
        k = i / (steps - 1)
        sx, sy = int(round(-d[0] * length * k)), int(round(-d[1] * length * k))
        out = np.maximum(out, np.roll(np.roll(a, sy, 0), sx, 1) * (1 - k) ** 1.5)
    return out


def thumb_collect():
    cam, placed, (gx, gy, gr), L = collect_stage()
    lay = {k: load_layer(v) for k, v in L.items()}
    src = (gx, gy - gr * 0.55)

    # 배경: 하늘색 방사(가운데 청록, 아래로 짙은 파랑) + 햇살 + 아래 구름(하늘빛 그늘)
    im = fx.radial((W, H), (gx, gy - gr * 0.9), 1500, [(0, (130, 225, 255)), (0.3, (70, 175, 245)),
                                                       (0.7, (30, 105, 215)), (1, (18, 64, 170))])
    im = fx.over(im, fx.linear((W, H), [(0, (0, 0, 0, 0)), (0.6, (10, 40, 140, 0)), (1, (10, 40, 140, 150))]))
    burst = fx.rays((W, H), src, count=22, color=(200, 245, 255), width=0.45, seed=61, falloff=0.7, inner=gr)
    im = fx.add(im, burst, 0.25)
    for (x, y, width, seed, alpha) in [(120, 1110, 620, 71, 0.95), (1800, 1110, 660, 72, 0.95), (480, 1140, 520, 73, 0.9),
                                       (1440, 1140, 540, 74, 0.9)]:
        c = fx.cloud(width, seed=seed, top=(225, 240, 255), bottom=(120, 170, 235))
        im = fx.over(im, c, (x - c.width / 2, y - c.height), alpha)

    # 꼬리: 지구본 → 명소, 등급 색 + 흰 심, 움직임 흐림
    for lid, (sx, sy, hpx) in placed.items():
        col = tier(lid)[2]
        dx, dy = sx - src[0], sy - src[1]
        start = (src[0] + dx * 0.12, src[1] + dy * 0.12)
        end = (sx - dx * 0.1, sy - dy * 0.1)
        a, t = streak((W, H), start, end, 8, hpx * 0.26)
        body = motion_blur(a * np.clip(t * 1.4, 0, 1) ** 0.8, (dx, dy), 40)
        im = fx.add(im, fx.glow(body, 16, col, 1.5), 0.7)
        im = fx.over(im, fx.solid((W, H), darken(col, 0.1), np.clip(body * 0.95, 0, 1)))
        core_a, _ = streak((W, H), start, end, 2, hpx * 0.06)
        im = fx.over(im, fx.solid((W, H), lighten(col, 0.75), np.clip(fx.blur_alpha(core_a * t ** 1.3, 1.5), 0, 1)))
        glow_r = hpx * (1.05 if lid == "alexandria" else 0.75)
        im = fx.add(im, fx.radial((W, H), (sx, sy), glow_r, [(0, col + (210,)), (0.5, col + (80,)), (1, col + (0,))]),
                    0.85)
    # 가장 희귀한 것: 뒤에 주황 햇살
    ax, ay, ahp = placed["alexandria"]
    acol = tier("alexandria")[2]
    im = fx.over(im, fx.radial((W, H), (ax, ay), ahp * 0.9, [(0, acol + (230,)), (0.55, acol + (120,)),
                                                            (1, acol + (0,))]))
    im = fx.add(im, fx.rays((W, H), (ax, ay), count=16, color=lighten(acol, 0.35), width=0.5, seed=63, falloff=1.0,
                            length=ahp * 1.5), 0.8)

    # 지구본: 빛 + 도는 궤적(호) + 민트 고리 + 본체
    im = fx.add(im, fx.radial((W, H), (gx, gy), gr * 1.7, [(0, (200, 250, 255, 220)), (0.55, (120, 230, 255, 120)),
                                                            (1, (120, 220, 255, 0))]), 0.8)
    arcs = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(arcs)
    for (rr, a0, a1, wdt) in [(1.1, 196, 262, 12), (1.18, 280, 344, 10), (1.07, 300, 322, 7), (1.26, 206, 236, 7),
                              (1.3, 300, 318, 6)]:
        r = gr * rr * SS
        d.arc((gx * SS - r, gy * SS - r, gx * SS + r, gy * SS + r), a0, a1, fill=255, width=int(wdt * SS))
    arcs_a = mask_img(arcs)
    im = fx.add(im, fx.glow(arcs_a, 8, (140, 230, 255), 1.4), 1.0)
    im = fx.over(im, fx.solid((W, H), WHITE, arcs_a))
    ring = Image.new("L", (W * SS, H * SS), 0)
    ring_y = gy - gr * 0.5
    rx_, ry_ = gr * 1.22 * SS, gr * 0.26 * SS
    ImageDraw.Draw(ring).ellipse((gx * SS - rx_, ring_y * SS - ry_, gx * SS + rx_, ring_y * SS + ry_),
                                 outline=255, width=int(10 * SS))
    ring_a = mask_img(ring)
    ring_back = ring_a * (np.arange(H)[:, None] < ring_y)  # 고리 뒤쪽 절반(지구본 뒤)
    im = fx.add(im, fx.glow(ring_back, 10, fx.MINT, 1.4), 0.8)
    im = fx.over(im, fx.solid((W, H), fx.MINT, ring_back))
    im = fx.add(im, fx.glow(lay["globe"], 20, (160, 240, 255), 1.3, spread=4), 0.8)
    im = fx.over(im, lay["globe"])
    im = fx.add(im, edge_light(lay["globe"], (200, 245, 255), (0, 8), 1.2, 2), 0.8)
    ring_front = ring_a * (np.arange(H)[:, None] >= ring_y)
    im = fx.add(im, fx.glow(ring_front, 10, fx.MINT, 1.4), 0.8)
    im = fx.over(im, fx.solid((W, H), fx.MINT, ring_front))
    im = fx.over(im, fx.solid((W, H), (235, 255, 250), fx.erode(ring_front, 2)))

    # 명소: 등급 색 번짐 + 등급 색 얇은 테 + 본체 + 흰 테두리 빛(양옆)
    for lid, (sx, sy, hpx) in placed.items():
        col = tier(lid)[2]
        layer = lay[f"L_{lid}"]
        la_ = fx.arr(layer)
        mean = float((la_[..., :3].mean(-1) * la_[..., 3]).sum() / max(la_[..., 3].sum(), 1))
        if mean < 0.42:  # 평균 밝기를 0.42 쪽으로(색은 그대로, 밝기만)
            la_[..., :3] = np.clip(la_[..., :3] * min(1.5, 0.42 / max(mean, 1e-3)), 0, 1)
            layer = fx.img(la_)
        la = fx.alpha_of(layer)
        im = fx.add(im, fx.glow(la, 16, col, 1.6, spread=5), 1.0)
        im = fx.over(im, fx.solid((W, H), darken(col, 0.35), np.clip(fx.dilate(la, 3) - la, 0, 1)))
        im = fx.over(im, layer)
        im = fx.add(im, edge_light(layer, lighten(col, 0.6), (-5, 3), 1.2, 1.2), 0.9)
        im = fx.add(im, edge_light(layer, lighten(col, 0.6), (5, 3), 1.2, 1.2), 0.9)
    models_a = np.zeros((H, W), np.float32)
    for lid in placed:
        models_a = np.maximum(models_a, fx.dilate(lay[f"L_{lid}"], 12))
    im = scatter_sparkles(im, [(60, 280, 1860, 900)], 30, seed=81, glow_color=(150, 235, 255), rmin=7, rmax=28,
                          big=[(600, 330, 40), (1340, 330, 44), (300, 900, 36), (1640, 600, 36), (820, 600, 30)],
                          avoid=models_a)
    im = fx.add(im, fx.particles((W, H), (gx, gy - gr), 110, (1.5, 4), WHITE, seed=82, spread=(0.1, 0.5),
                                 glow_color=(150, 235, 255)), 1.0)
    # 아바타(왼쪽 아래, 올려다봄)
    im = fx.over(im, lay["avatar"])
    im = fx.add(im, edge_light(lay["avatar"], (190, 245, 255), (4, -2), 1.0, 1.0), 0.8)

    # 확률 표(명소 아래), 제목
    for lid, (sx, sy, hpx) in placed.items():
        col = tier(lid)[2]
        big = lid == "alexandria"
        tag = fx.chunky_text(odds(lid), "luckiest", 84 if big else 62,
                             fill_stops=[(0, lighten(col, 0.55)), (0.5, lighten(col, 0.1)), (1, darken(col, 0.15))],
                             outline_color=INK, outline=11 if big else 9, inner=4, depth=6 if big else 5, gloss=0.25)
        tag = fx.rotate(tag, random.Random(lid).uniform(-5, 5))
        ty = sy + hpx * 0.5 - tag.height * 0.35
        im = drop_shadow(im, tag, (sx - tag.width / 2, ty), 6, 0.4)
        im = fx.over(im, tag, (sx - tag.width / 2, ty))
    im = grade(im, 1.1, 1.04, 0.18)
    im, _ = title_line(im, f"COLLECT {len(LANDMARKS)} LANDMARKS!", (W / 2, 14), size=128)
    return im


# 4: 나만의 관광 공원 -----------------------------------------------------------------------------------
# 가까이서 본 "내 공원"(진짜 ParkEdit 3D 배치 모드: 빛나는 판 + 들고 있는 반투명 복사본) + 뒤로 흐린 광장·다른 공원.
# 카메라는 내 부지 뒤(바다 쪽)에서 광장 지구본 쪽을 봄. 다른 샘플 플레이어 부지는 stage_hook 의 fillParks 로 가득.
FAMOUS = ["eiffel", "tajmahal", "liberty", "colosseum", "bigben", "pyramid", "moai", "greatwall", "sphinx", "pisa",
          "goldengate", "fuji", "stbasil", "parthenon", "machupicchu", "chichen", "alexandria", "petra", "stonehenge",
          "santorini", "notredame", "neuschwanstein", "sungnyemun", "namsan", "towerbridge", "windmill"]
# 내 공원: 줄(6 = 카메라 쪽 맨 앞) -> 카메라에서 본 왼쪽→오른쪽 명소. None = 빈 칸(들고 있는 명소를 놓을 칸)
MY_PARK = {
    1: ["notredame", "namsan", "waverock", "lakehillier", "clocktower", "towerbridge"],
    2: ["neuschwanstein", "stbasil", "moeraki", "sungnyemun", "fuji", "lighthouse"],
    3: ["skytower", "parthenon", "angkor", "flindersst", "liberty", "petra"],
    4: ["moai", "machupicchu", "alexandria", "windmill", "chichen", "santorini"],
    5: ["tajmahal", "colosseum", "yonggung", "pyramid", "fountainofyouth", "apostles"],
    6: ["harbourbridge", None, "stonehenge", "sphinx", "atlantis", "greatwall"],
}
MY_HELD = "eiffel"  # 보관함에서 집어 빈 칸 위에 든 명소(반투명 복사본)
# 초당 수입 말풍선(명소, 받침 위 높이). 숫자는 park_hook 이 게임 코드로 계산한 그 칸 명소의 수입(extra.SlotIncome)
POPUPS = [("yonggung", 7.5), ("fountainofyouth", 7.5), ("atlantis", 5.0)]
# 카메라(내 부지 좌표: 가운데 바닥 원점, -Z = 입구 = 광장 쪽): 눈, 겨냥, 시야각
PARK_CAM = ((-10, 21, 69), (3, 6, -10), 55)
PARK_AVATAR = {"sx": 290, "sy": 1150, "height_px": 530}  # 화면 발 자리·키(px)


def _row_slots(row: int) -> list:
    """카메라(부지 뒤)에서 본 왼쪽→오른쪽 칸 번호. 한 줄 안 칸 번호는 입구에서 볼 때 가운데 오른쪽·가운데 왼쪽·…
    (PlayerState.slotCell) 이라 뒤에서 보면 [5, 3, 1, 2, 4, 6] 순서."""
    return [s + 6 * (row - 1) for s in (5, 3, 1, 2, 4, 6)]


def income_text(income: float) -> str:
    """게임 간판·수입 칩과 같은 표기(ParkService.incomeText): 100 미만은 소수 한 자리, 그 위는 Format.short."""
    if income < 100:
        return "+" + f"{math.floor(income * 10) / 10:.1f}".removesuffix(".0") + "/s"
    for unit, suffix in ((1e15, "Qa"), (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if income >= unit:
            v = income / unit
            body = str(math.floor(v)) if v >= 100 else f"{math.floor(v * 10) / 10:.1f}".removesuffix(".0")
            return "+" + body + suffix + "/s"
    return "+" + f"{int(income):,}" + "/s"


def expected_income(lid: str, count: int) -> float:
    """검산용(파이썬): Config.TIER_INCOME[등급] × (1 + STAR_INCOME_BONUS × 별). 별 = 보유 수가 STAR_THRESHOLDS 몇 개를 넘었나."""
    text = (ROOT / "src/shared/Config.luau").read_text()
    table = [int(v) for v in re.search(r"TIER_INCOME = \{([^}]*)\}", text).group(1).split(",")]
    thresholds = [int(v) for v in re.search(r"STAR_THRESHOLDS = \{([^}]*)\}", text).group(1).split(",")]
    stars = sum(1 for t in thresholds if count >= t)
    return table[TIERS.index(tier(lid))] * (1 + config_number("STAR_INCOME_BONUS") * stars)


def park_stage() -> dict:
    display, target = {}, None
    for row, ids in MY_PARK.items():
        for slot, lid in zip(_row_slots(row), ids):
            if lid:
                display[str(slot)] = lid
            else:
                target = slot
    return {"fillParks": {"level": 10, "count": 36, "famous": 22, "maxOneIn": 100000, "ids": FAMOUS},
            "myPark": {"level": 10, "display": display, "storage": [MY_HELD], "pick": MY_HELD, "target": target,
                       "frames": 60, "counts": 1, "name": "You"}}


def coin_popup(text: str, coin: Image.Image, size=110, color=(255, 214, 60)) -> Image.Image:
    """동전 + "+250/s" 두꺼운 글자(게임 수입 칩처럼)."""
    c = coin.resize((size, size), Image.Resampling.LANCZOS)
    t = fx.chunky_text(text, "fredoka", int(size * 0.66), fill_stops=[(0, (255, 255, 230)), (0.5, color), (1, darken(color, 0.25))],
                       outline_color=INK, outline=int(size * 0.08), inner=0, depth=int(size * 0.05), gloss=0.2)
    w = c.width + t.width - int(size * 0.08)
    h = max(c.height, t.height)
    out = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    g = fx.glow(np.pad(fx.alpha_of(c), 20), 12, (255, 220, 90), 1.3)
    out = fx.add(out, g, 0.9, (0, (h - c.height) // 2))
    out = fx.over(out, c, (20, 20 + (h - c.height) // 2))
    out = fx.over(out, t, (20 + c.width - int(size * 0.08), 20 + (h - t.height) // 2 + int(size * 0.04)))
    return out


def thumb_park():
    import json

    stage = park_stage()
    hook = "tools/store/park_hook.luau"
    dump = st.world_dump(stage, players=7, hook=hook)
    extra = json.loads(dump.read_text())["extra"]
    o = np.array(extra["Origin"][:3], float)
    Ro = np.array(extra["Origin"][3:], float).reshape(3, 3)
    local = lambda v: o + Ro @ np.array(v, float)  # noqa: E731
    eye, target, fov = PARK_CAM
    cam = st.Camera(local(eye), local(target), fov, (W, H))
    plot = f"Parks/{extra['Plot']}"
    held = f"ParkEditLocal/{extra['Held']}"
    fence_depth = float(np.dot(local((0, 0, 40)) - cam.eye, cam.f))
    layers = [
        {"name": "bg", "terrain": True, "exclude": [plot, "ParkEditLocal"],
         "clear": {"until": fence_depth - 2, "margin": 1.4}},
        {"name": "park", "terrain": False, "include": [plot, "ParkEditLocal"], "exclude": [held]},
        {"name": "ghost", "terrain": False, "include": [held]},
    ]
    L = st.render_layers(stage, cam, layers, size=(W * SS, H * SS), players=7, hook=hook)

    # 아바타(scene3d, 같은 카메라): 부지 뒤 풀밭에서 들고 있는 명소를 향해 팔을 뻗음(배치하는 손짓)
    ghost_at = np.array(extra["SlotWorld"][extra["Target"] - 1], float) + np.array([0, 6, 0])
    av_base = ground_from_screen(cam, PARK_AVATAR["sx"], PARK_AVATAR["sy"])
    av_depth = float(np.dot(av_base - cam.eye, cam.f))
    av_scale = PARK_AVATAR["height_px"] / (5.6 * cam.scale_at(av_depth))
    look = (ghost_at - av_base)[[0, 2]]
    pose = {"head": (-18, -6), "arm_r": (128, -8), "arm_l": (18, 14), "leg_l": 5, "leg_r": -5, "face": False}
    avatar = st.to3d(st.avatar("Avatar", av_base, st.yaw_facing(look), pose, scale=av_scale))
    sun = st.sun_direction()
    scene = {"size": [W * SS, H * SS], "camera": st.cam3d(cam),
             "light": {"sun": sun, "sunIntensity": 1.0, "hemiIntensity": 0.85, "shadowCenter": av_base.tolist(),
                       "shadowBox": 20},
             "objects": [{"tag": "avatar", "parts": avatar, "castShadow": False}],
             "layers": [{"name": "avatar", "draw": ["avatar"]}]}
    L.update(st.render3d(scene))
    lay = {k: load_layer(v) for k, v in L.items()}

    # 하늘 + 구름(수평선 위) ---------------------------------------------------------------------------
    horizon = cam.project([cam.eye + np.array([cam.f[0], 0, cam.f[2]]) * 3000])[0][1]
    im = fx.linear((W, H), [(0, (40, 124, 230)), (max(0.05, horizon / H - 0.02), (140, 205, 252)), (horizon / H, (220, 240, 255)),
                            (1, (220, 240, 255))])
    for (x, dy, width, seed, alpha) in [(180, 20, 420, 91, 0.95), (1740, 24, 460, 92, 0.95), (560, 10, 260, 93, 0.85),
                                        (1380, 12, 280, 94, 0.85)]:
        c = fx.cloud(width, seed=seed)
        im = fx.over(im, c, (x - c.width / 2, horizon + dy - c.height), alpha)

    # 뒤(광장·다른 공원): 흐림 + 옅은 안개(멀수록) — 초점은 내 공원 ----------------------------------------------
    bg = lay["bg"].filter(ImageFilter.GaussianBlur(3.2))
    ba = fx.arr(bg)
    ys = np.arange(H, dtype=np.float32)[:, None]
    haze = np.clip(1 - (ys - horizon) / 420, 0, 1) ** 1.5 * 0.35
    ba[..., :3] = ba[..., :3] * (1 - haze[..., None]) + np.array([0.86, 0.94, 1.0], np.float32) * haze[..., None]
    im = fx.over(im, fx.img(ba))
    # 광장 지구본 빛(멀리서도 눈에 띄게)
    gp = cam.project([np.array([0, 22, 0])])[0]
    im = fx.add(im, fx.radial((W, H), gp[:2], 170, [(0, (200, 245, 255, 190)), (1, (200, 245, 255, 0))]), 0.45)

    # 내 공원(또렷) + 부지 둘레 그림자 ------------------------------------------------------------------------
    pa = fx.alpha_of(lay["park"])
    im = fx.over(im, fx.solid((W, H), (20, 60, 30), fx.blur_alpha(pa, 14) * (1 - pa) * 0.35))
    im = fx.over(im, lay["park"])
    # 가리키는 칸(초록 판) 빛: 게임의 강한 판 + 번짐
    tgt = np.array(extra["SlotWorld"][extra["Target"] - 1], float)
    q = ground_quad(cam, tgt + np.array([0, 0.05, 0]), 5.9)
    plate = fx.alpha_of(fx.warp_quad(fx.radial((256, 256), (128, 128), 128, [(0, (255, 255, 255, 255)), (0.8, (255, 255, 255, 200)),
                                                                          (1, (255, 255, 255, 0))]), q, (W, H)))
    im = fx.add(im, fx.glow(plate, 26, (76, 217, 100), 1.0), 0.45)

    # 들고 있는 명소(반투명 복사본): 노란 채우기(게임 Highlight 색) + 흰 테두리 + 빛 + 아래로 빛기둥 --------------------------
    gl = lay["ghost"]
    ga = fx.alpha_of(gl)
    gx, gy, _ = cam.project([ghost_at])[0]
    tx_, ty_, _ = cam.project([tgt])[0]
    ys2, xs2 = np.mgrid[0:H, 0:W].astype(np.float32)
    beam_half = 70
    beam = np.clip(1 - np.abs(xs2 - tx_) / beam_half, 0, 1) ** 1.4 * ((ys2 < ty_) & (ys2 > gy - 40)) * \
        np.clip((ty_ - ys2) / 30, 0, 1)
    im = fx.add(im, fx.solid((W, H), (255, 236, 150), beam * 0.35))
    im = fx.add(im, fx.glow(ga, 26, (255, 205, 70), 1.3, spread=4), 0.8)
    sun_col = (255, 197, 61)  # Ui.colorPair("Sun").Face
    ghost_rgb = fx.arr(gl)
    ghost_rgb[..., :3] = ghost_rgb[..., :3] * 0.7 + np.array(sun_col, np.float32) / 255 * 0.3
    im = fx.over(im, fx.img(ghost_rgb))
    ring = np.clip(fx.dilate(ga, 3) - np.clip(ga * 3, 0, 1), 0, 1)
    im = fx.over(im, fx.solid((W, H), WHITE, ring))

    # 수입: 동전 말풍선(등급 기본 수입, 진짜 값) + 간판으로 흘러가는 동전 줄 -------------------------------------------------
    coin = Image.open(ROOT / "art/png/coin.png").convert("RGBA")
    sign = np.array(extra["Sign"], float) if extra.get("Sign") else local((0, 8, -40))
    sx_, sy_, _ = cam.project([sign + np.array([0, 2.5, 0])])[0]
    rnd = random.Random(97)
    placed = {lid: slot for slot, lid in enumerate(extra["Slots"], start=1) if lid}
    pops = []
    counts = stage["myPark"]["counts"]
    for lid, above in POPUPS:
        slot = placed[lid]
        p = np.array(extra["SlotWorld"][slot - 1], float)
        px, py, _ = cam.project([p + np.array([0, above, 0])])[0]
        income = extra["SlotIncome"][slot - 1]
        assert abs(income - expected_income(lid, counts)) < 1e-6, (lid, income, expected_income(lid, counts))
        size = 116 if income >= 250 else 100
        pops.append((lid, px, py, size, income))
        print(f"[thumbs] 공원 말풍선 {lid}: {income_text(income)} (보유 {counts}개, 게임 계산 {income})")
    # 동전 줄(뒤): 말풍선 → 간판, 멀어질수록 작게
    for (lid, px, py, size, _) in pops:
        n = 6
        ctrl = ((px + sx_) / 2, min(py - size * 0.6, sy_) - 110)
        trail = Image.new("L", (W * SS, H * SS), 0)
        pts = []
        for i in range(41):
            t = i / 40
            pts.append((((1 - t) ** 2 * px + 2 * (1 - t) * t * ctrl[0] + t * t * sx_) * SS,
                        ((1 - t) ** 2 * (py - size * 0.6) + 2 * (1 - t) * t * ctrl[1] + t * t * sy_) * SS))
        ImageDraw.Draw(trail).line(pts, fill=255, width=int(10 * SS), joint="curve")
        ta_ = fx.blur_alpha(mask_img(trail), 4)
        im = fx.add(im, fx.solid((W, H), (255, 230, 120), ta_), 0.45)
        for i in range(1, n + 1):
            t = i / (n + 1)
            x = (1 - t) ** 2 * px + 2 * (1 - t) * t * ctrl[0] + t * t * sx_
            y = (1 - t) ** 2 * (py - size * 0.6) + 2 * (1 - t) * t * ctrl[1] + t * t * sy_
            s = int(size * 0.42 * (1 - 0.6 * t))
            c = fx.rotate(coin.resize((s, s), Image.Resampling.LANCZOS), rnd.uniform(-30, 30))
            im = fx.add(im, fx.glow(np.pad(fx.alpha_of(c), 12), 6, (255, 220, 90), 1.0), 0.6,
                        (x - c.width / 2 - 12, y - c.height / 2 - 12))
            im = fx.over(im, c, (x - c.width / 2, y - c.height / 2), 0.95)
    for (lid, px, py, size, income) in pops:
        pop = coin_popup(income_text(income), coin, size, color=(255, 214, 60))
        im = drop_shadow(im, pop, (px - pop.width / 2, py - pop.height), 6, 0.35)
        im = fx.over(im, pop, (px - pop.width / 2, py - pop.height))
    im = scatter_sparkles(im, [(200, 380, 900, 820), (1000, 380, 1800, 820)], 16, seed=98,
                          glow_color=(255, 230, 140), rmin=6, rmax=22, big=[(gx + 150, gy - 120, 34), (gx - 170, gy + 40, 26)])
    # 아바타: 접지 그림자 + 몸 + 빛 쪽 테두리 ----------------------------------------------------------------
    foot_sh = fx.warp_quad(fx.radial((256, 256), (128, 128), 128, [(0, (0, 0, 0, 190)), (0.55, (0, 0, 0, 110)), (1, (0, 0, 0, 0))]),
                           ground_quad(cam, av_base, 2.6 * av_scale), (W, H))
    im = fx.over(im, foot_sh, opacity=0.8)
    im = fx.over(im, lay["avatar"])
    im = fx.add(im, edge_light(lay["avatar"], (255, 240, 190), (4, -2), 1.0, 1.2), 0.7)

    im = grade(im, 1.12, 1.04, 0.2)
    im, _ = title_line(im, "BUILD YOUR PARK!", (W / 2, 14), size=150)
    return im


def sheet() -> Path:
    """다섯 장 + 아이콘(150px)을 작게 모은 점검용 그림 — 스토어 목록에서처럼 작게 봐도 읽히는지."""
    tw, th, gap = 640, 360, 24
    out = Image.new("RGB", (tw * 3 + gap * 4, th * 2 + gap * 3), (236, 238, 242))
    for i in range(5):
        path = OUT / f"thumb_{i + 1}.png"
        if not path.exists():
            continue
        im = Image.open(path).convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        out.paste(im, (gap + (i % 3) * (tw + gap), gap + (i // 3) * (th + gap)))
    icon = OUT / "icon_small.png"
    if icon.exists():
        ic = Image.open(icon).convert("RGB")
        out.paste(ic, (gap + 2 * (tw + gap) + (tw - ic.width) // 2, gap + (th + gap) + (th - ic.height) // 2))
    path = OUT / "thumbs_sheet.png"
    out.save(path, optimize=True)
    print(f"[thumbs] {path}")
    return path


def main(which):
    made = {}
    for n in which:
        if n in HEROES:
            made[n] = save(thumb_hero(n), f"thumb_{n}.png")
        elif n == 2:
            made[n] = save(thumb_rebirth(), "thumb_2.png")
        elif n == 3:
            made[n] = save(thumb_collect(), "thumb_3.png")
        elif n == 4:
            made[n] = save(thumb_park(), "thumb_4.png")
    return made


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4, 5]
    main(args)
    sheet()
