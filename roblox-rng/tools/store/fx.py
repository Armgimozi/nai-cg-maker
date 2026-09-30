"""스토어 그림(아이콘·썸네일) 합성 도구 모음 — PIL + numpy 만 씀.

아이콘(make_icon.py)과 썸네일이 같이 씁니다. 함수를 더하는 건 괜찮지만, 있는 함수의 인자·결과는 바꾸지 마세요
(다른 스크립트가 그대로 부름).

그림은 모두 RGBA PIL Image(곧은 알파). 빛 효과는 더하기(add)로 겹침:
    base = fx.add(base, fx.glow(layer, 30, fx.MINT), 0.8)
글꼴은 mockup/fonts 의 woff2(Luckiest Guy, Fredoka One — 게임 UI 글꼴)를 메모리에서 TTF 로 바꿔 씀.
"""
from __future__ import annotations

import io
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
INK = (30, 27, 46)  # 게임 그림(art/README.md) 테두리 색 #1E1B2E
MINT = (120, 255, 235)  # 전설 등급 색(Landmarks.Tiers[7])
WHITE = (255, 255, 255)

# 글꼴 ----------------------------------------------------------------------------------
_FONT_FILES = {
    "luckiest": ROOT / "mockup/fonts/LuckiestGuy-latin.woff2",
    "fredoka": ROOT / "mockup/fonts/FredokaOne-latin.woff2",
}
_font_bytes: dict[str, bytes] = {}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """name = "luckiest" | "fredoka" | ttf/otf/woff2 파일 경로."""
    path = Path(_FONT_FILES.get(name, name))
    key = str(path)
    if key not in _font_bytes:
        if path.suffix == ".woff2":
            from fontTools.ttLib import TTFont

            f = TTFont(str(path))
            f.flavor = None
            buf = io.BytesIO()
            f.save(buf)
            _font_bytes[key] = buf.getvalue()
        else:
            _font_bytes[key] = path.read_bytes()
    return ImageFont.truetype(io.BytesIO(_font_bytes[key]), size)


# numpy <-> PIL, 겹치기 --------------------------------------------------------------------
def arr(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGBA"), np.float32) / 255.0


def img(a: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def over(base: Image.Image, top: Image.Image, xy=(0, 0), opacity: float = 1.0) -> Image.Image:
    """보통 겹치기(알파). xy 는 top 의 왼쪽 위 위치(음수 가능)."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    if opacity < 1:
        top = top.copy()
        top.putalpha(top.getchannel("A").point(lambda v: int(v * opacity)))
    layer.paste(top, (int(xy[0]), int(xy[1])))
    out = base.copy()
    out.alpha_composite(layer)
    return out


def add(base: Image.Image, top: Image.Image, strength: float = 1.0, xy=(0, 0)) -> Image.Image:
    """더하기(빛): base.rgb += top.rgb * top.a * strength. 투명한 base 에도 알파를 더함."""
    if xy != (0, 0) or top.size != base.size:
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        layer.paste(top, (int(xy[0]), int(xy[1])))
        top = layer
    b = arr(base)
    t = arr(top)
    ta = t[..., 3:4] * strength
    pb = b[..., :3] * b[..., 3:4] + t[..., :3] * ta
    a = np.clip(b[..., 3:4] + np.clip(ta, 0, 1) * (1 - b[..., 3:4]), 1e-6, 1)
    out = np.concatenate([pb / a, a], -1)
    return img(out)


def screen(base: Image.Image, top: Image.Image, strength: float = 1.0) -> Image.Image:
    b = arr(base)
    t = arr(top)
    k = t[..., 3:4] * strength
    rgb = 1 - (1 - b[..., :3]) * (1 - t[..., :3] * k)
    return img(np.concatenate([rgb, b[..., 3:4]], -1))


def solid(size, color, alpha: np.ndarray | Image.Image | None = None) -> Image.Image:
    """한 색 + 알파(0~1 배열 또는 L 그림)."""
    w, h = size
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = np.array(color[:3], np.float32) / 255
    if alpha is None:
        out[..., 3] = 1
    elif isinstance(alpha, Image.Image):
        out[..., 3] = np.asarray(alpha.convert("L"), np.float32) / 255
    else:
        out[..., 3] = alpha
    return img(out)


def alpha_of(im: Image.Image) -> np.ndarray:
    return np.asarray(im.getchannel("A"), np.float32) / 255


def multiply_alpha(im: Image.Image, k: float | np.ndarray) -> Image.Image:
    a = arr(im)
    a[..., 3] *= k
    return img(a)


# 그라데이션 ------------------------------------------------------------------------------
def _stops(t: np.ndarray, stops) -> np.ndarray:
    """stops = [(0, (r,g,b[,a])), (0.5, ...), (1, ...)] → t(0~1) 위치의 RGBA(0~1)."""
    pos = np.array([s[0] for s in stops], np.float32)
    cols = np.array([list(s[1]) + ([255] if len(s[1]) == 3 else []) for s in stops], np.float32) / 255
    out = np.zeros(t.shape + (4,), np.float32)
    for c in range(4):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out


def linear(size, stops, angle: float = 90) -> Image.Image:
    """직선 그라데이션. angle 90 = 위→아래, 0 = 왼→오른."""
    w, h = size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    proj = (xs - w / 2) * dx + (ys - h / 2) * dy
    half = abs(w / 2 * dx) + abs(h / 2 * dy)
    return img(_stops((proj / max(half, 1e-6) + 1) / 2, stops))


def radial(size, center, radius, stops, squash: float = 1.0) -> Image.Image:
    """원(타원) 그라데이션: 가운데 t=0 → radius 에서 t=1. squash<1 이면 세로로 납작."""
    w, h = size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot(xs - center[0], (ys - center[1]) / squash) / radius
    return img(_stops(np.clip(r, 0, 1), stops))


# 빛 효과 ---------------------------------------------------------------------------------
def blur_alpha(im: Image.Image | np.ndarray, radius: float) -> np.ndarray:
    a = im if isinstance(im, np.ndarray) else alpha_of(im)
    if radius <= 0:
        return a
    L = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "L")
    # 큰 반경은 줄여서 흐린 뒤 키움(빠르고 결과는 거의 같음)
    k = 1
    while radius / k > 24 and min(L.size) / (k * 2) > 32:
        k *= 2
    if k > 1:
        small = L.resize((max(1, L.width // k), max(1, L.height // k)), Image.Resampling.BILINEAR)
        small = small.filter(ImageFilter.GaussianBlur(radius / k))
        L = small.resize(L.size, Image.Resampling.BICUBIC)
    else:
        L = L.filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(L, np.float32) / 255


def dilate(im: Image.Image | np.ndarray, radius: float) -> np.ndarray:
    """알파를 radius 만큼 둥글게 부풀림(흐림 + 문턱, 가는 곳은 조금 덜 부풂)."""
    a = im if isinstance(im, np.ndarray) else alpha_of(im)
    if radius <= 0:
        return a
    b = blur_alpha(a, radius * 0.6)
    return np.clip((b - 0.02) / 0.1, 0, 1)


def glow(im: Image.Image | np.ndarray, radius: float, color=MINT, strength: float = 1.0, spread: float = 0) -> Image.Image:
    """모양(알파)을 흐려서 color 빛으로. spread 만큼 먼저 부풀림. 결과는 add() 로 겹침."""
    a = im if isinstance(im, np.ndarray) else alpha_of(im)
    if spread > 0:
        a = dilate(a, spread)
    g = blur_alpha(a, radius) * strength
    h, w = g.shape
    return solid((w, h), color, np.clip(g, 0, 1))


def rays(size, center, count=18, color=WHITE, length=None, width=0.5, seed=1, falloff=1.4, inner=0.0,
         twist=0.0) -> Image.Image:
    """햇살(방사 빛줄기). width = 줄기 사이 간격 대비 굵기(0~1), 줄기마다 굵기·세기가 조금씩 다름."""
    w, h = size
    rnd = random.Random(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = xs - center[0], ys - center[1]
    r = np.hypot(dx, dy)
    L = length or math.hypot(w, h)
    th = np.arctan2(dy, dx) + twist * r / L
    val = np.zeros_like(r)
    offs = rnd.random() * math.tau
    for i in range(count):
        a0 = offs + i * math.tau / count + (rnd.random() - 0.5) * 0.4 * math.tau / count
        half = width * math.pi / count * (0.55 + rnd.random() * 0.9)
        k = 0.55 + rnd.random() * 0.45
        d = np.abs((th - a0 + math.pi) % math.tau - math.pi)
        val = np.maximum(val, k * np.clip(1 - d / half, 0, 1) ** 0.6)
    fall = np.clip(1 - r / L, 0, 1) ** falloff
    if inner > 0:
        fall *= np.clip(r / inner, 0, 1)
    return solid(size, color, np.clip(val * fall, 0, 1))


def speed_lines(size, center, count=70, color=INK, inner=0.62, seed=2, thickness=0.012, alpha=0.9) -> Image.Image:
    """만화 집중선: 바깥에서 center 쪽으로 가늘어지는 어두운 줄. inner = 줄이 시작하는 반경(대각선 반 길이 비)."""
    w, h = size
    rnd = random.Random(seed)
    im = Image.new("L", (w * 2, h * 2), 0)
    d = ImageDraw.Draw(im)
    R = math.hypot(w, h)
    cx, cy = center[0] * 2, center[1] * 2
    for _ in range(count):
        a = rnd.random() * math.tau
        r0 = R * (inner + rnd.random() * 0.25)
        half = thickness * (0.4 + rnd.random()) * R
        p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0)
        nx, ny = -math.sin(a), math.cos(a)
        far = R * 1.6
        p1 = (cx + math.cos(a) * far + nx * half, cy + math.sin(a) * far + ny * half)
        p2 = (cx + math.cos(a) * far - nx * half, cy + math.sin(a) * far - ny * half)
        d.polygon([p0, p1, p2], fill=int(255 * (0.5 + rnd.random() * 0.5)))
    im = im.resize((w, h), Image.Resampling.LANCZOS)
    return solid(size, color, np.asarray(im, np.float32) / 255 * alpha)


def star_polygon(cx, cy, r, pinch=2.6, aspect=1.0, rot=0.0, n=160):
    """오목한 반짝이 별(4개 뾰족): 아스트로이드 비슷한 곡선(pinch 3 = 아스트로이드). pinch 클수록 가늘게."""
    pts = []
    for i in range(n):
        t = i / n * math.tau
        x = math.copysign(abs(math.cos(t)) ** pinch, math.cos(t)) * r
        y = math.copysign(abs(math.sin(t)) ** pinch, math.sin(t)) * r * aspect
        xr = x * math.cos(rot) - y * math.sin(rot)
        yr = x * math.sin(rot) + y * math.cos(rot)
        pts.append((cx + xr, cy + yr))
    return pts


def sparkle(size, center, r, color=WHITE, glow_color=MINT, glow_radius=None, pinch=2.6, aspect=1.25, rot=0.0,
            core=True) -> Image.Image:
    """4개 뾰족 반짝이(세로가 조금 긴) + 빛 번짐. 결과는 over() 로(빛 부분은 알파에 포함)."""
    w, h = size
    s = 4
    L = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(L).polygon(star_polygon(center[0] * s, center[1] * s, r * s, pinch=pinch, aspect=aspect, rot=rot),
                              fill=255)
    L = L.resize((w, h), Image.Resampling.LANCZOS)
    a = np.asarray(L, np.float32) / 255
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    if glow_color is not None:
        g = glow(a, glow_radius or r * 0.45, glow_color, 1.6)
        out = add(out, g, 1.0)
        if core:
            out = add(out, glow(a, r * 0.12, WHITE, 1.0), 0.8)
    return over(out, solid(size, color, a))


def sparkle_sprite(r, color=WHITE, glow_color=MINT, pinch=2.6, aspect=1.25, rot=0.0) -> Image.Image:
    """sparkle 을 작은 그림 한 장으로(붙일 때 over(base, sprite, (x - s/2, y - s/2)))."""
    s = int(r * 3.2) + 8
    return sparkle((s, s), (s / 2, s / 2), r, color, glow_color, pinch=pinch, aspect=aspect, rot=rot)


def particles(size, center, count, radius_range, color=WHITE, seed=3, spread=(0.1, 0.5), glow_color=MINT) -> Image.Image:
    """빛 알갱이: center 둘레(화면 대각선 비 spread 범위)에 작은 점 + 번짐."""
    w, h = size
    rnd = random.Random(seed)
    s = 3
    L = Image.new("L", (w * s, h * s), 0)
    d = ImageDraw.Draw(L)
    R = math.hypot(w, h)
    for _ in range(count):
        a = rnd.random() * math.tau
        rr = R * (spread[0] + rnd.random() * (spread[1] - spread[0]))
        x, y = center[0] + math.cos(a) * rr, center[1] + math.sin(a) * rr
        pr = radius_range[0] + rnd.random() * (radius_range[1] - radius_range[0])
        d.ellipse((x * s - pr * s, y * s - pr * s, x * s + pr * s, y * s + pr * s), fill=int(160 + rnd.random() * 95))
    a = np.asarray(L.resize((w, h), Image.Resampling.LANCZOS), np.float32) / 255
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    if glow_color is not None:
        out = add(out, glow(a, radius_range[1] * 2.5, glow_color, 2.0))
    return over(out, solid(size, color, a))


# 구름 ---------------------------------------------------------------------------------------
def cloud(width, seed=4, top=(255, 255, 255), bottom=(196, 222, 250), puffs=7) -> Image.Image:
    """뭉게구름 한 덩이(아래가 평평, 위 흰색 → 아래 하늘빛 그늘). 크기 = width x 약 width*0.55."""
    rnd = random.Random(seed)
    s = 2
    W, H = int(width * s), int(width * 0.6 * s)
    L = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(L)
    base = H * 0.86
    for i in range(puffs):
        t = (i + 0.5) / puffs
        cx = W * (0.1 + 0.8 * t) + (rnd.random() - 0.5) * W * 0.06
        bump = math.sin(math.pi * t) ** 0.8
        r = W * (0.09 + 0.12 * bump) * (0.8 + rnd.random() * 0.45)
        cy = base - r * (1.0 + 0.35 * bump)  # 공 아래가 바닥선 위에(바닥은 둥근 띠가 만듦)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    d.rounded_rectangle((W * 0.06, base - H * 0.2, W * 0.94, base), radius=H * 0.1, fill=255)
    L = L.crop((0, 0, W, int(base) + 1)).resize((int(width), int((base + 1) / s)), Image.Resampling.LANCZOS)
    a = np.asarray(L.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    h, w = a.shape
    grad = arr(linear((w, h), [(0, top), (0.55, top), (1, bottom)]))
    # 윗쪽 가장자리 안쪽을 살짝 밝게(부피감)
    grad[..., 3] = a
    return img(grad)


# 땅 무늬(3D 판에 붙이는 그림) ----------------------------------------------------------------------
def magic_circle(px=2048, color=WHITE, seed=5, width=1.0) -> Image.Image:
    """마법진(위에서 본 모습, 흰 선 + 투명): 겹 원, 룬 칸, 육망성, 안쪽 별. 3D 에서 땅에 눕혀 씀."""
    rnd = random.Random(seed)
    s = px
    L = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(L)
    c = s / 2
    lw = s / 260 * width

    def ring(r, wdt):
        d.ellipse((c - r * c, c - r * c, c + r * c, c + r * c), outline=255, width=max(1, int(wdt * lw)))

    ring(0.985, 3.2)
    ring(0.94, 1.4)
    ring(0.79, 2.6)
    ring(0.75, 1.2)
    # 룬 칸: 0.80~0.93 사이에 짧은 기호(선·점·삼각형) 반복
    n = 36
    for i in range(n):
        a = i / n * math.tau
        r0, r1 = 0.815 * c, 0.915 * c
        ca, sa = math.cos(a), math.sin(a)
        kind = rnd.randrange(4)
        tx, ty = -sa, ca  # 접선
        mid = (r0 + r1) / 2
        if kind == 0:
            d.line((c + ca * r0, c + sa * r0, c + ca * r1, c + sa * r1), fill=255, width=int(1.6 * lw))
        elif kind == 1:
            q = 0.03 * c
            d.ellipse((c + ca * mid - q, c + sa * mid - q, c + ca * mid + q, c + sa * mid + q), outline=255,
                      width=int(1.3 * lw))
        elif kind == 2:
            q = 0.035 * c
            pts = [(c + ca * (mid + q), c + sa * (mid + q)), (c + ca * (mid - q) + tx * q, c + sa * (mid - q) + ty * q),
                   (c + ca * (mid - q) - tx * q, c + sa * (mid - q) - ty * q)]
            d.polygon(pts, outline=255, width=int(1.3 * lw))
        else:
            q = 0.03 * c
            d.line((c + ca * (mid - q) - tx * q, c + sa * (mid - q) - ty * q, c + ca * (mid + q) + tx * q,
                    c + sa * (mid + q) + ty * q), fill=255, width=int(1.4 * lw))
            d.line((c + ca * (mid - q) + tx * q, c + sa * (mid - q) + ty * q, c + ca * (mid + q) - tx * q,
                    c + sa * (mid + q) - ty * q), fill=255, width=int(1.4 * lw))
    # 육망성
    for k in range(2):
        pts = [(c + math.cos(a) * 0.75 * c, c + math.sin(a) * 0.75 * c)
               for a in [math.pi / 2 + k * math.pi + j * math.tau / 3 for j in range(3)]]
        d.polygon(pts, outline=255, width=int(2.2 * lw))
    # 꼭짓점 작은 원
    for j in range(6):
        a = math.pi / 2 + j * math.tau / 6
        x, y = c + math.cos(a) * 0.75 * c, c + math.sin(a) * 0.75 * c
        q = 0.05 * c
        d.ellipse((x - q, y - q, x + q, y + q), outline=255, width=int(1.8 * lw))
    ring(0.43, 2.0)
    ring(0.39, 1.0)
    # 안쪽 8각 별
    pts = []
    for j in range(16):
        a = j / 16 * math.tau
        rr = (0.37 if j % 2 == 0 else 0.2) * c
        pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
    d.polygon(pts, outline=255, width=int(1.8 * lw))
    ring(0.12, 2.0)
    return solid((s, s), color, np.asarray(L, np.float32) / 255)


def vortex(px=1024, center=(8, 22, 40), swirl=(90, 230, 255), arms=7, twist=3.2, seed=8, edge=0.92) -> Image.Image:
    """소용돌이 구멍(위에서 본 모습): 가운데 짙은 색 → 가장자리 투명 + 밝은 나선 줄기. 마법진 밑 땅에 깔아 씀."""
    rnd = random.Random(seed)
    ys, xs = np.mgrid[0:px, 0:px].astype(np.float32)
    c = px / 2
    dx, dy = (xs - c) / c, (ys - c) / c
    r = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    body = np.clip(1 - (r / edge) ** 2, 0, 1) ** 1.2
    phase = rnd.random() * math.tau
    s = np.sin(arms * (th + twist * np.log(np.maximum(r, 0.02))) + phase)
    streak = np.clip((s - 0.55) / 0.45, 0, 1) ** 1.5 * np.clip(r / 0.25, 0, 1) * np.clip(1 - r / edge, 0, 1) ** 0.5
    out = np.zeros((px, px, 4), np.float32)
    col = np.array(center, np.float32) / 255
    sw = np.array(swirl, np.float32) / 255
    k = streak[..., None] * 0.8
    out[..., :3] = col * (1 - k) + sw * k
    out[..., 3] = np.clip(body * 0.85 + streak * 0.3, 0, 1)
    return img(out)


def vignette(size, color=(10, 30, 90), strength=0.55, inner=0.55, center=None) -> Image.Image:
    """가장자리 어둡게(색 + 알파). over() 로 겹침."""
    w, h = size
    cx, cy = center or (w / 2, h / 2)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xs - cx) / (w / 2), (ys - cy) / (h / 2)) / math.sqrt(2)
    a = np.clip((r - inner) / (1 - inner), 0, 1) ** 1.6 * strength
    return solid(size, color, a)


def cracks(px=2048, seed=6, count=11, inner=0.2, reach=(0.6, 0.98), width=1.0):
    """땅 갈라짐(위에서 본 모습): 가운데 둘레에서 바깥으로 뻗는 들쭉날쭉한 금 + 곁가지.
    결과 (어두운 금 그림, 빛나는 속 그림) — 둘 다 흰색 + 알파(색은 3D 판·합성에서 입힘)."""
    rnd = random.Random(seed)
    s = px
    dark = Image.new("L", (s, s), 0)
    core = Image.new("L", (s, s), 0)
    dd, dc = ImageDraw.Draw(dark), ImageDraw.Draw(core)
    c = s / 2
    lw = s / 180 * width

    def branch(x, y, a, length, wdt, depth):
        steps = max(3, int(length / (s * 0.03)))
        for i in range(steps):
            t = i / steps
            a += (rnd.random() - 0.5) * 0.7
            step = length / steps
            nx, ny = x + math.cos(a) * step, y + math.sin(a) * step
            wd = max(1.0, wdt * (1 - t * 0.85))
            dd.line((x, y, nx, ny), fill=255, width=int(wd * lw * 2.2))
            dc.line((x, y, nx, ny), fill=255, width=max(1, int(wd * lw * 0.8)))
            if depth < 2 and rnd.random() < 0.18:
                branch(nx, ny, a + rnd.choice([-1, 1]) * (0.5 + rnd.random() * 0.6), length * (1 - t) * 0.5, wd * 0.6,
                       depth + 1)
            x, y = nx, ny

    for i in range(count):
        a = i / count * math.tau + (rnd.random() - 0.5) * 0.4
        r0 = inner * c
        length = (reach[0] + rnd.random() * (reach[1] - reach[0])) * c - r0
        branch(c + math.cos(a) * r0, c + math.sin(a) * r0, a, length, 2.4, 0)
    dark = dark.filter(ImageFilter.GaussianBlur(lw * 0.4))
    return solid((s, s), WHITE, np.asarray(dark, np.float32) / 255), solid((s, s), WHITE, np.asarray(core, np.float32) / 255)


# 글자 --------------------------------------------------------------------------------------
def chunky_text(text, font_name="luckiest", size=200, fill_stops=None, outline=None, outline_color=INK,
                inner=None, inner_color=WHITE, depth=None, depth_color=None, gloss=0.28, tracking=0,
                shadow=None) -> Image.Image:
    """굵은 게임 글자: 세로 그라데이션 채움 + 흰 안쪽 테 + 두꺼운 어두운 바깥 테 + 아래로 두께(depth) + 윗부분 광택.
    fill_stops 기본 = 밝은 연두 → 초록. 결과는 글자에 딱 맞춘 투명 그림(여백 = 테·두께만큼)."""
    f = font(font_name, size)
    outline = int(size * 0.11) if outline is None else outline
    inner = int(size * 0.045) if inner is None else inner
    depth = int(size * 0.07) if depth is None else depth
    fill_stops = fill_stops or [(0, (236, 255, 120)), (0.42, (120, 240, 70)), (0.75, (40, 200, 60)), (1, (20, 150, 55))]
    depth_color = depth_color or tuple(int(v * 0.55) for v in outline_color)
    pad = outline + inner + depth + 8
    # 글자 위치(자간 조절이 있으면 한 글자씩)
    glyphs = []
    x = 0
    for ch in text:
        glyphs.append((x, ch))
        x += f.getlength(ch) + tracking
    width = int(x - tracking) if tracking else int(f.getlength(text))
    asc, desc = f.getmetrics()
    W, H = width + pad * 2, asc + desc + pad * 2

    def mask(stroke):
        L = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(L)
        if tracking:
            for gx, ch in glyphs:
                d.text((pad + gx, pad), ch, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
        else:
            d.text((pad, pad), text, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
        return L

    m_fill = mask(0)
    m_inner = mask(inner)
    m_out = mask(inner + outline)
    bbox = m_fill.getbbox()
    top, bottom = bbox[1], bbox[3]
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shadow:
        sh = solid((W, H), shadow.get("color", (0, 0, 0)),
                   blur_alpha(np.asarray(m_out, np.float32) / 255, shadow.get("blur", 6)) * shadow.get("alpha", 0.5))
        out = over(out, sh, shadow.get("offset", (0, depth + 4)))
    # 두께: 바깥 테 모양을 아래로 여러 번
    for k in range(depth, 0, -1):
        out = over(out, solid((W, H), depth_color, m_out), (0, k))
    out = over(out, solid((W, H), outline_color, m_out))
    out = over(out, solid((W, H), inner_color, m_inner))
    ys = np.arange(H, dtype=np.float32)[:, None].repeat(W, 1)
    t = np.clip((ys - top) / max(1, bottom - top), 0, 1)
    fill = _stops(t, fill_stops)
    fill[..., 3] = np.asarray(m_fill, np.float32) / 255
    out = over(out, img(fill))
    if gloss > 0:
        # 윗부분 광택: 글자 높이 위쪽 45% 에 흰 띠(아래로 흐려짐)
        g = np.clip(1 - (ys - top) / max(1, (bottom - top) * 0.45), 0, 1) ** 1.5 * gloss
        g *= np.asarray(m_fill.filter(ImageFilter.MinFilter(5)), np.float32) / 255
        out = add(out, solid((W, H), WHITE, g))
    return out.crop(out.getbbox())


def rotate(im: Image.Image, deg: float) -> Image.Image:
    return im.rotate(deg, resample=Image.Resampling.BICUBIC, expand=True)


def pill(text, font_name="fredoka", size=48, fg=WHITE, bg=(255, 94, 91), outline=INK, pad=(0.55, 0.28),
         border=None) -> Image.Image:
    """둥근 알약 이름표(테두리 + 아래 두께) + 가운데 글자."""
    f = font(font_name, size)
    tw = f.getlength(text)
    asc, desc = f.getmetrics()
    border = border or max(3, size // 9)
    w = int(tw + size * pad[0] * 2)
    h = int(size * (1 + pad[1] * 2))
    depth = max(2, size // 12)
    W, H = w + border * 2 + 4, h + border * 2 + depth + 4
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = border + 2, border + 2
    d.rounded_rectangle((x0 - border, y0 - border + depth, x0 + w + border, y0 + h + border + depth), radius=h // 2 + border,
                        fill=outline)
    d.rounded_rectangle((x0 - border, y0 - border, x0 + w + border, y0 + h + border), radius=h // 2 + border, fill=outline)
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=h // 2, fill=bg)
    hl = tuple(min(255, int(v + (255 - v) * 0.35)) for v in bg[:3])
    d.rounded_rectangle((x0 + h * 0.25, y0 + h * 0.12, x0 + w - h * 0.25, y0 + h * 0.3), radius=h // 8, fill=hl)
    d.text((x0 + w / 2, y0 + h / 2), text, font=f, fill=fg, anchor="mm", stroke_width=max(1, size // 16),
           stroke_fill=outline)
    return im


# 모양 변환·점검 -------------------------------------------------------------------------------------
def warp_quad(im: Image.Image, quad, size) -> Image.Image:
    """im(사각형)을 화면의 네 점 quad(왼위, 오른위, 오른아래, 왼아래)에 원근으로 붙인 size 그림."""
    w, h = im.size
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, B = [], []
    for (x, y), (u, v) in zip(quad, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B += [u, v]
    coeffs = np.linalg.solve(np.array(A, np.float64), np.array(B, np.float64))
    return im.transform(size, Image.Transform.PERSPECTIVE, tuple(coeffs), Image.Resampling.BICUBIC)


def round_mask_preview(im: Image.Image, radius_ratio=0.18, bg=(245, 246, 248)) -> Image.Image:
    """Roblox 스토어처럼 모서리를 둥글게 잘라 본 모습(점검용)."""
    w, h = im.size
    m = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 4 - 1, h * 4 - 1), radius=int(w * 4 * radius_ratio), fill=255)
    m = m.resize((w, h), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (w, h), bg + (255,))
    out.paste(im.convert("RGBA"), (0, 0), m)
    return out
