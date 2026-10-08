"""
mood2_gothic HUD 미리보기: 플러그인 Hud.java 와 같은 차례로 그림 글자를 짜고 (진행 폭, 빈칸 글자), 기본 팩 HUD 셰이더와 같은
몫만큼 옮겨, GUI 4 텍셀 해상도에서 겹친 뒤 화면 배율 G 로 넓이 평균한다 (글꼴 셰이더와 같은 읽기).
"""
import math

import numpy as np
from PIL import Image

T = 4   # 미리보기 텍셀 / GUI 픽셀

# pack/hud.py 의 자리 값 (기본 팩 셰이더)
HUD_KL, HUD_KR, HUD_TOP, BOSS_LINE_TOP, BOSS_PITCH = 205, 206, 8, 3, 19
HUD_INSET, SOUL_INSET, BOSS_UP, BOSS_FILL, BOSS_W, SOUL_BOX_BOTTOM = (0.045, 0.05), (0.04, 0.04), 64, 0.45, 200, 8
RUNS = (128, 64, 32, 16, 8, 4, 2, 1)


class Font:
    def __init__(self, pack, providers, glyphs):
        import os
        self.by = {}
        adv = {n: w for n, _, w in glyphs}
        for p in providers:
            img = Image.open(os.path.join(pack, "assets", "souls", "textures", p["file"].split(":", 1)[1])).convert("RGBA")
            row = p["chars"][0]
            cw = img.width // len(row)
            scale = p["height"] / img.height
            for i, ch in enumerate(row):
                name = next(n for n, c_, _ in glyphs if c_ == ch)
                cell = img.crop((i * cw, 0, (i + 1) * cw, img.height))
                f = int(round(T * scale * img.height / p["height"] * (p["height"] / img.height) / scale)) if False else None
                k = round(1 / scale)
                if k != T:
                    cell = cell.resize((cell.width * T // k, cell.height * T // k), Image.NEAREST)
                self.by[name] = (cell, p["ascent"], adv[name])


class Line:
    def __init__(self, font):
        self.font, self.pen, self.items = font, 0, []

    def move(self, d):
        self.pen += d

    def glyph(self, name):
        cell, asc, w = self.font.by[name]
        self.items.append((self.pen, asc, cell))
        self.pen += w - 1

    def runs(self, prefix, n):
        for s in RUNS:
            while n >= s:
                self.glyph(prefix + str(s))
                n -= s


def bars(font, vals):
    l = Line(font)
    l.move(-HUD_KL)
    x0 = l.pen
    for bar, (length, fill, trail) in vals.items():
        l.glyph(f"hud_{bar}_cap_l")
        l.runs(f"hud_{bar}_fill_", fill)
        l.runs(f"hud_{bar}_trail_", trail)
        l.runs(f"hud_{bar}_empty_", length - fill - trail)
        l.glyph(f"hud_{bar}_cap_r")
        l.move(x0 - l.pen)
    return l


def souls(font, n, box):
    l = Line(font)
    d = str(n)
    dw = font.by["hud_digit_0"][2] - 1
    l.move(HUD_KR - box)
    x0 = l.pen
    l.glyph("hud_soulbox")
    l.move(x0 + 5 - l.pen)
    l.glyph("soul_mark")
    l.move(x0 + box - 6 - dw * len(d) - l.pen)
    for ch in d:
        l.glyph("hud_digit_" + ch)
    return l


def boss(font, fill, trail, post, w=BOSS_W):
    half = w // 2
    l = Line(font)
    l.move(-half - 2)
    l.glyph("boss_cap_l")
    l.runs("boss_hp_fill_", fill)
    l.runs("boss_hp_trail_", trail)
    l.runs("boss_hp_empty_", w - fill - trail)
    l.glyph("boss_cap_r")
    l.move(-half - l.pen)
    l.runs("boss_post_fill_", post)
    l.runs("boss_post_empty_", w - post)
    return l


def compose(W, H, layers):
    """layers: [(Line, line_top_gui, (dx, dy), stretch)] → GUI 4 텍셀 캔버스 (RGBA float, 곱하지 않은 알파)."""
    cv = np.zeros((H * T, W * T, 4), np.float32)
    cx = W // 2
    for line, top, (dx, dy), st in layers:
        lay = np.zeros_like(cv)
        for pen, asc, cell in line.items:
            a = np.asarray(cell).astype(np.float32) / 255.0
            x = (cx + pen + dx) * T
            y = (top + 7 - asc + dy) * T
            h, w = a.shape[:2]
            if st != 1.0:
                # 셰이더: 꼭짓점 x 를 가운데를 축으로 st 배 (글자 네모 전체를 늘인다)
                x = int(round(cx * T + pen * T * st)) + dx * T
                a = np.asarray(cell.resize((max(1, int(round(w * st))), h), Image.NEAREST)).astype(np.float32) / 255.0
                w = a.shape[1]
            ys, xs = max(0, -y), max(0, -x)
            y0, x0 = y + ys, x + xs
            y1, x1 = min(H * T, y + h), min(W * T, x + w)
            if y1 <= y0 or x1 <= x0:
                continue
            src = a[ys:ys + (y1 - y0), xs:xs + (x1 - x0)]
            dst = lay[y0:y1, x0:x1]
            sa = src[..., 3:4]
            dst[..., :3] = src[..., :3] * sa + dst[..., :3] * (1 - sa)
            dst[..., 3:4] = sa + dst[..., 3:4] * (1 - sa)
        la = lay[..., 3:4]
        cv[..., :3] = lay[..., :3] * la + cv[..., :3] * (1 - la) if False else np.where(la > 0, (lay[..., :3] * la + cv[..., :3] * cv[..., 3:4] * (1 - la)) / np.maximum(la + cv[..., 3:4] * (1 - la), 1e-6), cv[..., :3])
        cv[..., 3:4] = la + cv[..., 3:4] * (1 - la)
    return cv


def to_screen(cv, G, bg):
    """GUI 4 텍셀 → 배율 G 화면 픽셀 (넓이 평균, 알파 곱한 색) 을 배경 bg (H×W×3, 화면) 위에."""
    h, w = cv.shape[:2]
    prem = np.concatenate([cv[..., :3] * cv[..., 3:4], cv[..., 3:4]], -1)
    up = np.repeat(np.repeat(prem, G, 0), G, 1)
    H2, W2 = h * G // T, w * G // T
    small = up[:H2 * T, :W2 * T].reshape(H2, T, W2, T, 4).mean(axis=(1, 3))
    out = bg[:H2, :W2].astype(np.float32) / 255.0 * (1 - small[..., 3:4]) + small[..., :3]
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8), "RGB")


def shifts(W, H):
    centre = W // 2
    left = (math.floor(W * HUD_INSET[0] + 0.5) - (centre - HUD_KL), math.floor(H * HUD_INSET[1] + 0.5) - HUD_TOP)
    right = ((W - math.floor(W * SOUL_INSET[0] + 0.5)) - (centre + HUD_KR), SOUL_BOX_BOTTOM - math.floor(H * SOUL_INSET[1] + 0.5))
    s = min(2.5, max(1.0, math.floor(W * BOSS_FILL / BOSS_W * 4 + 0.5) / 4))
    line = 1
    bossd = (0, (H - BOSS_UP) - (BOSS_LINE_TOP + BOSS_PITCH * line))
    return left, right, bossd, s


def scene(font, box, W, H, G, bg, vals, souls_n, boss_vals=None):
    left, right, bossd, s = shifts(W, H)
    layers = [(bars(font, vals), BOSS_LINE_TOP, left, 1.0), (souls(font, souls_n, box), H - 72, right, 1.0)]
    if boss_vals:
        bl = boss(font, *boss_vals)
        layers.append((bl, BOSS_LINE_TOP + BOSS_PITCH, (0, bossd[1]), s))
    cv = compose(W, H, layers)
    return to_screen(cv, G, bg)
