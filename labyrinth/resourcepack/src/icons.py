"""2D icon art for materials, consumables and keys (GDD §14.2 icon styles).

Each icon is composed from signed-distance shapes, bevel-lit from the top-left, quantised to
the item's palette ramps and outlined — an original procedural pixel-art pipeline at 32×32
(the same texel density as the 3D gear: 2 px per model unit).
"""
from __future__ import annotations

import math

from PIL import Image

from .model import Texel, value_to_color
from .util import clamp, darken, h2, lighten, mix

SIZE = 32
_L = (-0.55, -0.7, 0.9)
_LN = math.sqrt(sum(c * c for c in _L))
LIGHT = tuple(c / _LN for c in _L)


# ───────────────────────────── SDF primitives ─────────────────────────────

def circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def ellipse(cx, cy, rx, ry, ang=0.0):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    def f(x, y):
        dx, dy = x - cx, y - cy
        u, v = dx * c + dy * s, -dx * s + dy * c
        k = math.hypot(u / rx, v / ry)
        return (k - 1.0) * min(rx, ry)
    return f


def rbox(cx, cy, hw, hh, r=0.0, ang=0.0):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    def f(x, y):
        dx, dy = x - cx, y - cy
        u, v = abs(dx * c + dy * s), abs(-dx * s + dy * c)
        qx, qy = u - hw + r, v - hh + r
        out = math.hypot(max(qx, 0), max(qy, 0))
        return out + min(max(qx, qy), 0) - r
    return f


def capsule(ax, ay, bx, by, r, r2=None):
    r2 = r if r2 is None else r2

    def f(x, y):
        px, py = x - ax, y - ay
        bax, bay = bx - ax, by - ay
        h = clamp((px * bax + py * bay) / (bax * bax + bay * bay + 1e-9))
        return math.hypot(px - bax * h, py - bay * h) - (r + (r2 - r) * h)
    return f


def poly(pts):
    n = len(pts)

    def f(x, y):
        d = 1e9
        inside = False
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            ex, ey = bx - ax, by - ay
            wx, wy = x - ax, y - ay
            h = clamp((wx * ex + wy * ey) / (ex * ex + ey * ey + 1e-9))
            d = min(d, math.hypot(wx - ex * h, wy - ey * h))
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay + 1e-12) + ax:
                inside = not inside
        return -d if inside else d
    return f


def union(*fs):
    return lambda x, y: min(f(x, y) for f in fs)


def sub(a, b):
    return lambda x, y: max(a(x, y), -b(x, y))


def inter(a, b):
    return lambda x, y: max(a(x, y), b(x, y))


def star(cx, cy, r1, r2, n, rot=-90):
    pts = []
    for k in range(n * 2):
        a = math.radians(rot + 180.0 * k / n)
        r = r1 if k % 2 == 0 else r2
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return poly(pts)


def ngon(cx, cy, r, n, rot=-90):
    return poly([(cx + math.cos(math.radians(rot + 360.0 * k / n)) * r,
                  cy + math.sin(math.radians(rot + 360.0 * k / n)) * r) for k in range(n)])


# ───────────────────────────── icon canvas ─────────────────────────────

class Layer:
    __slots__ = ('sdf', 'ramp', 'base', 'bevel', 'glow', 'gloss', 'pattern', 'role', 'flat')

    def __init__(self, sdf, ramp, base, bevel, glow, gloss, pattern, role, flat):
        self.sdf, self.ramp, self.base, self.bevel = sdf, ramp, base, bevel
        self.glow, self.gloss, self.pattern, self.role, self.flat = glow, gloss, pattern, role, flat


class Icon:
    def __init__(self, look):
        self.look = look
        self.layers: list[Layer] = []

    def ramp(self, name):
        lk = self.look
        return {'main': lk.main, 'accent': lk.accent, 'metal': lk.metal, 'wood': lk.wood, 'grip': lk.grip,
                'orn': lk.orn, 'string': lk.string, 'dark': lk.dark, 'horn': lk.horn, 'glass': self._glass()}[name]

    def _glass(self):
        l = self.look.pal.light
        g = mix(l, (220, 235, 245), 0.6)
        return [darken(g, 0.55), darken(g, 0.35), darken(g, 0.15), g, lighten(g, 0.5), (255, 255, 255)]

    def add(self, sdf, ramp='main', base=0.5, bevel=2.5, glow=False, gloss=False, pattern=None, role='body', flat=False):
        self.layers.append(Layer(sdf, self.ramp(ramp) if isinstance(ramp, str) else ramp, base, bevel, glow, gloss,
                                 pattern, role, flat))
        return self

    def texels(self):
        out = []
        top = [[None] * SIZE for _ in range(SIZE)]
        for y in range(SIZE):
            for x in range(SIZE):
                px, py = x + 0.5, y + 0.5
                for li in range(len(self.layers) - 1, -1, -1):
                    L = self.layers[li]
                    d = L.sdf(px, py)
                    if d < 0:
                        top[y][x] = li
                        if L.flat:
                            v = L.base
                        else:
                            def hh(qx, qy):
                                return clamp(-L.sdf(qx, qy) / L.bevel)
                            e = 0.8
                            gx = (hh(px + e, py) - hh(px - e, py)) / (2 * e)
                            gy = (hh(px, py + e) - hh(px, py - e)) / (2 * e)
                            n = (-gx * 2.2, -gy * 2.2, 1.0)
                            nl = math.sqrt(n[0] ** 2 + n[1] ** 2 + 1.0)
                            sh = (n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]) / nl
                            v = L.base + (sh - 0.62) * 1.1
                            v += (0.5 - py / SIZE) * 0.12
                        color = None
                        if L.pattern is not None:
                            r = L.pattern(px, py, d)
                            if isinstance(r, tuple):
                                color = r
                            elif r:
                                v += r
                        if L.gloss and not L.flat and color is None:
                            if v > L.base + 0.36 and h2(x, y, 5) > 0.35:
                                color = (255, 255, 255)
                        out.append(Texel(x, y, L.ramp, v, L.role, (x / 2.0, (SIZE - y) / 2.0, 0.0), 'south', li,
                                         L.glow, 255, color, x, y, SIZE, SIZE))
                        break
        # outline
        ol = darken(self.look.pal.dark, 0.45)
        for y in range(SIZE):
            for x in range(SIZE):
                if top[y][x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < SIZE and 0 <= ny < SIZE and top[ny][nx] is not None:
                        out.append(Texel(x, y, [ol], 0, 'outline', (x / 2.0, (SIZE - y) / 2.0, 0.0), 'south', -1,
                                         False, 255, ol, x, y, SIZE, SIZE))
                        break
        return out


def frame_from(texels, vfn=None):
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    px = img.load()
    for t in texels:
        color, dv = t.color, 0.0
        if vfn is not None:
            r = vfn(t)
            if r is not None:
                if r[0] is not None:
                    color = r[0]
                dv = r[1]
        if color is None:
            color = value_to_color(t.ramp, t.v + dv)
        elif dv:
            color = lighten(color, min(0.9, dv)) if dv > 0 else darken(color, min(0.9, -dv))
        px[t.x, t.y] = (color[0], color[1], color[2], 255)
    return img


# ───────────────────────────── patterns ─────────────────────────────

def stripes(period=3, ang=45, amp=0.18):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return lambda x, y, d: amp if int(math.floor((x * c + y * s) / period)) % 2 == 0 else -amp * 0.5


def speckle(seed=1, amp=0.25, dens=0.12):
    return lambda x, y, d: (amp if h2(int(x), int(y), seed) < dens else 0.0)


def rune_mark(cx, cy, color):
    from .materials import rune_bit
    gi = int(cx * 7 + cy * 3) % 8

    def f(x, y, d):
        lx, ly = int(math.floor(x - cx + 1.5)), int(math.floor(y - cy + 2.5))
        return color if rune_bit(gi, lx, ly) else 0.0
    return f


# ───────────────────────────── icon styles ─────────────────────────────

def draw(icon: Icon, style: str, seed: int):
    lk = icon.look
    acc_hi = lk.accent[5]
    s = style
    if s == 'fiber':
        for k, off in enumerate((-4.5, 0, 4.5)):
            pts = [(16 + off + 2.5 * math.sin(t * 0.5 + k), 4 + t) for t in range(0, 25, 3)]
            for a, b in zip(pts, pts[1:]):
                icon.add(capsule(a[0], a[1], b[0], b[1], 1.6), 'main', 0.45 + 0.08 * k, 1.6)
        icon.add(rbox(16, 17, 8, 1.8, 0.8), 'grip', 0.55, 1.2)
    elif s in ('shard', 'crystal'):
        if s == 'shard':
            icon.add(poly([(9, 27), (13, 9), (19, 3), (22, 12), (20, 26)]), 'main', 0.55, 3.0, glow=True, gloss=True)
            icon.add(poly([(13, 9), (19, 3), (17.5, 14), (14, 25)]), 'main', 0.78, 2.0, glow=True)
        else:
            icon.add(poly([(5, 27), (7, 14), (10, 10), (12, 15), (12, 27)]), 'main', 0.45, 2.0, glow=True)
            icon.add(poly([(20, 27), (21, 12), (25, 8), (27, 13), (27, 27)]), 'main', 0.5, 2.0, glow=True)
            icon.add(poly([(10, 28), (12, 9), (16, 3), (20, 9), (22, 28)]), 'main', 0.62, 3.0, glow=True, gloss=True)
            icon.add(poly([(16, 3), (20, 9), (18, 27), (16, 27)]), 'main', 0.82, 2.0, glow=True)
        icon.add(poly([(6, 29), (26, 29), (24, 26), (8, 26)]), 'dark', 0.4, 1.0)
    elif s == 'ingot':
        icon.add(poly([(3, 21), (8, 14), (29, 14), (25, 21)]), 'main', 0.78, 1.5, gloss=True)
        icon.add(poly([(3, 21), (25, 21), (25, 27), (3, 27)]), 'main', 0.45, 1.5)
        icon.add(poly([(25, 21), (29, 14), (29, 20), (25, 27)]), 'main', 0.3, 1.0)
        icon.add(rbox(16, 17.5, 5, 1.2, 0.5), 'main', 0.6, 1.0, flat=True)
    elif s == 'core':
        icon.add(circle(16, 16, 11), 'metal', 0.4, 3.0)
        icon.add(circle(16, 16, 8), 'accent', 0.7, 6.0, glow=True, gloss=True)
        icon.add(circle(16, 16, 3.5), 'accent', 1.0, 2.0, glow=True)
        for a in (0, 90, 180, 270):
            r = math.radians(a + 45)
            icon.add(rbox(16 + math.cos(r) * 10, 16 + math.sin(r) * 10, 2.2, 2.2, 0.6, a + 45), 'orn', 0.6, 1.2)
    elif s == 'silk_bundle':
        icon.add(rbox(16, 16, 9, 8, 3), 'main', 0.6, 3.0, pattern=lambda x, y, d: 0.18 if int(y) % 2 == 0 else -0.05)
        icon.add(rbox(16, 7, 11, 2.2, 1), 'wood', 0.55, 1.5)
        icon.add(rbox(16, 25, 11, 2.2, 1), 'wood', 0.5, 1.5)
        icon.add(capsule(23, 18, 28, 27, 0.8), 'main', 0.7, 1.0)
    elif s == 'scale':
        icon.add(poly([(16, 29), (5, 16), (7, 6), (16, 3), (25, 6), (27, 16)]), 'main', 0.55, 4.0, gloss=True,
                 pattern=lambda x, y, d: -0.22 if abs((x - 16) * 0.5) < 0.5 and y < 24 else (0.15 if int(y) % 6 == 0 else 0))
    elif s == 'bone':
        icon.add(capsule(9, 23, 23, 9, 2.8), 'horn', 0.6, 2.0)
        for (cx, cy) in ((7, 21.5), (10.5, 25), (21.5, 7), (25, 10.5)):
            icon.add(circle(cx, cy, 3.3), 'horn', 0.62, 2.2)
    elif s == 'essence':
        icon.add(poly([(16, 3), (22, 13), (24, 20), (20, 27), (12, 27), (8, 20), (10, 13)]), 'accent', 0.62, 5.0, glow=True)
        icon.add(ellipse(16, 20, 4, 5), 'accent', 0.95, 3.0, glow=True)
        for (x, y) in ((6, 8), (26, 10), (25, 26)):
            icon.add(star(x, y, 2.5, 0.8, 4), 'accent', 1.0, 1.0, glow=True, flat=True)
    elif s == 'gem':
        icon.add(ngon(16, 17, 12, 8, -90 + 22.5), 'accent', 0.5, 2.0, glow=True)
        icon.add(ngon(16, 17, 7, 8, -90 + 22.5), 'accent', 0.75, 2.0, glow=True, gloss=True)
        icon.add(poly([(16, 10), (21, 17), (16, 24), (11, 17)]), 'accent', 0.92, 1.5, glow=True)
    elif s in ('cloth',):
        icon.add(rbox(15, 17, 11, 9, 2, -8), 'main', 0.5, 2.0, pattern=stripes(2, 0, 0.08))
        icon.add(rbox(17, 14, 10, 8, 2, 6), 'main', 0.65, 2.5, pattern=stripes(2, 90, 0.08))
        icon.add(rbox(17, 21, 10, 1, 0.5, 6), 'accent', 0.7, 1.0)
    elif s == 'plate':
        icon.add(rbox(16, 16, 12, 10, 2.5), 'main', 0.55, 3.0, gloss=True)
        for (x, y) in ((7, 9), (25, 9), (7, 23), (25, 23)):
            icon.add(circle(x, y, 1.6), 'metal', 0.75, 1.2)
        icon.add(rbox(16, 16, 9, 1.0, 0.4), 'main', 0.3, 1.0)
    elif s in ('potion_small', 'potion', 'potion_large', 'ink_vial'):
        R = {'potion_small': 7.5, 'potion': 9.5, 'potion_large': 11.5, 'ink_vial': 8}[s]
        by = 31 - R - 1.5
        if s == 'ink_vial':
            body = rbox(16, by, R, R - 0.5, 2.5)
        else:
            body = circle(16, by, R)
        neck_h = 4 if s != 'potion_large' else 3
        icon.add(rbox(16, by - R - neck_h / 2 + 1, 3.2, neck_h / 2 + 1, 1), 'glass', 0.55, 1.5)
        icon.add(rbox(16, by - R - neck_h - 1, 4.2, 2.2, 1), 'wood', 0.55, 1.5)
        icon.add(body, 'glass', 0.6, 2.5)
        liq = inter(body, lambda x, y: (by - R * 0.25) - y)
        icon.add(inter(liq, circle(16, by, R - 1.5) if s != 'ink_vial' else rbox(16, by, R - 1.5, R - 2, 2)),
                 'accent' if s != 'ink_vial' else 'dark', 0.62, 4.0, glow=True)
        icon.add(ellipse(16 - R * 0.45, by - R * 0.35, 1.2, 2.4, 25), 'glass', 1.0, 1.0, flat=True)
        if s == 'potion_large':
            icon.add(rbox(16, by + 1, R - 2, 2.2, 0.5), 'orn', 0.6, 1.0)
    elif s in ('scroll', 'page', 'map'):
        if s == 'scroll':
            icon.add(rbox(16, 16, 9, 10, 1), 'horn', 0.68, 1.5, pattern=lambda x, y, d: -0.25 if int(y) % 3 == 0 and 10 < x < 22 and 9 < y < 24 else 0)
            icon.add(capsule(5, 6, 27, 6, 2.6), 'horn', 0.55, 2.0)
            icon.add(capsule(5, 26, 27, 26, 2.6), 'horn', 0.55, 2.0)
            icon.add(rbox(16, 16, 1.6, 10, 0.4), 'accent', 0.6, 1.0)
        elif s == 'page':
            icon.add(poly([(7, 3), (21, 3), (26, 8), (26, 29), (7, 29)]), 'horn', 0.7, 1.5,
                     pattern=lambda x, y, d: -0.3 if int(y) % 3 == 0 and 10 < x < 23 and 9 < y < 26 else 0)
            icon.add(poly([(21, 3), (26, 8), (21, 8)]), 'horn', 0.45, 1.0)
        else:
            icon.add(poly([(3, 6), (11, 4), (21, 7), (29, 5), (29, 26), (21, 28), (11, 25), (3, 27)]), 'horn', 0.66, 1.5)
            icon.add(poly([(11, 4), (21, 7), (21, 28), (11, 25)]), 'horn', 0.5, 1.0)
            for k in range(6):
                icon.add(circle(7 + k * 3.3, 20 - k * 1.6 - (k % 2), 0.9), 'accent', 0.5, 1.0, flat=True)
            icon.add(union(capsule(22, 9, 26, 13, 0.9), capsule(26, 9, 22, 13, 0.9)), 'accent', 0.85, 1.0, flat=True)
    elif s == 'blueprint':
        # 0.3.6 도안: 말린 양피지 한 장 + 먹선 설계도(칼 · 원 · 치수선). 봉인·끈은 둘째 층(blueprint_seal, 희귀도 색으로 칠함)
        icon.add(poly([(6, 5), (24, 3), (27, 6), (27, 27), (8, 29), (5, 26)]), 'main', 0.72, 1.6,
                 pattern=lambda x, y, d: -0.12 if h2(int(x), int(y), 11) < 0.10 else 0)
        icon.add(capsule(6, 5, 24, 3, 2.2), 'main', 0.55, 1.8)
        icon.add(capsule(8, 28.5, 27, 26.5, 2.0), 'main', 0.5, 1.6)
        ink = 'dark'
        icon.add(capsule(10, 22, 20, 9, 0.7), ink, 0.35, 1.0, flat=True)          # 칼날 선
        icon.add(capsule(8.5, 20.5, 12.5, 23.5, 0.6), ink, 0.35, 1.0, flat=True)  # 손잡이 가로대
        icon.add(sub(circle(21, 12.5, 3.2), circle(21, 12.5, 2.4)), ink, 0.35, 1.0, flat=True)
        icon.add(capsule(9, 11, 15, 10.2, 0.45), ink, 0.42, 1.0, flat=True)       # 치수선
        icon.add(capsule(8, 25, 14, 24.3, 0.45), ink, 0.42, 1.0, flat=True)
    elif s == 'blueprint_seal':
        # 도안 둘째 층 — 밝은 회색으로만 그려 아이템 정의의 tint(희귀도 색)가 그대로 먹게
        icon.add(capsule(16, 29, 18.5, 23.5, 1.4), 'main', 0.62, 1.2)
        icon.add(capsule(22, 29.5, 20, 23.5, 1.4), 'main', 0.55, 1.2)
        icon.add(circle(20, 23.5, 3.9), 'main', 0.7, 2.5, gloss=True)
        icon.add(star(20, 23.5, 2.2, 1.0, 5), 'main', 0.95, 1.0, flat=True)
    elif s == 'key':
        icon.add(sub(circle(10, 10, 6.5), circle(10, 10, 3)), 'metal', 0.6, 2.0, gloss=True)
        icon.add(capsule(14, 14, 26, 26, 2.0), 'metal', 0.55, 1.5)
        icon.add(rbox(22, 25, 1.6, 3, 0.4, 45), 'metal', 0.5, 1.0)
        icon.add(rbox(25.5, 21.5, 1.6, 3, 0.4, 45), 'metal', 0.5, 1.0)
        icon.add(circle(10, 10, 1.6), 'accent', 0.9, 1.0, glow=True)
    elif s == 'rune_stone':
        icon.add(poly([(6, 10), (12, 4), (23, 5), (27, 13), (25, 25), (15, 28), (6, 23)]), 'main', 0.5, 4.0,
                 pattern=speckle(seed, -0.15, 0.15))
        icon.add(rbox(16, 16, 5, 7, 1), 'main', 0.45, 1.0, glow=True, flat=True,
                 pattern=lambda x, y, d, _r=rune_mark(16, 16, lk.accent[5]): (_r(x * 0.5 + 8, y * 0.5 + 8, d) or -0.05))
    elif s in ('gear', 'coil'):
        if s == 'gear':
            def gear(x, y):
                a = math.atan2(y - 16, x - 16)
                r = 10.5 + (2.2 if math.cos(a * 8) > 0.2 else 0)
                return math.hypot(x - 16, y - 16) - r
            icon.add(sub(gear, circle(16, 16, 4)), 'main', 0.55, 2.0, gloss=True)
            icon.add(sub(circle(16, 16, 6.5), circle(16, 16, 4)), 'main', 0.75, 1.5)
        else:
            for k in range(6):
                icon.add(sub(ellipse(16, 7 + k * 3.6, 9, 3), ellipse(16, 6.2 + k * 3.6, 7.2, 1.8)), 'main', 0.55 + 0.04 * k, 1.5, gloss=True)
            icon.add(capsule(16, 4, 25, 2, 1.0), 'main', 0.6, 1.0)
    elif s == 'pearl':
        icon.add(circle(16, 16, 10), 'accent', 0.58, 9.0, glow=True, gloss=True)
        icon.add(ellipse(12, 11, 2.5, 1.6, -30), 'accent', 1.0, 1.0, flat=True)
    elif s == 'fang':
        icon.add(poly([(9, 4), (20, 4), (22, 10), (20, 19), (15, 28), (13, 20), (10, 12)]), 'horn', 0.62, 3.5, gloss=True)
        icon.add(rbox(15, 6, 7, 2.5, 1), 'horn', 0.4, 1.5)
    elif s == 'spore':
        for (x, y, r) in ((11, 19, 6), (21, 18, 7), (16, 11, 7), (16, 23, 5)):
            icon.add(circle(x, y, r), 'main', 0.55, 4.0, pattern=speckle(seed + x, 0.3, 0.1))
        for (x, y) in ((6, 7), (26, 6), (27, 27), (5, 27)):
            icon.add(circle(x, y, 1.3), 'accent', 0.95, 1.0, glow=True, flat=True)
    elif s == 'feather':
        vane = poly([(24, 4), (28, 7), (24, 16), (15, 24), (9, 26), (11, 20), (18, 10)])
        icon.add(vane, 'main', 0.6, 3.0, glow=True, pattern=stripes(2.0, 135, 0.12))
        icon.add(capsule(5, 29, 25, 5, 0.9), 'horn', 0.75, 1.0)
    elif s == 'heart':
        hrt = union(circle(11, 12, 6.5), circle(21, 12, 6.5), poly([(4.8, 14), (27.2, 14), (16, 28)]))
        icon.add(hrt, 'accent', 0.6, 5.0, glow=True, gloss=True)
        icon.add(poly([(16, 9), (20, 14), (16, 22), (12, 14)]), 'accent', 0.85, 2.0, glow=True)
    elif s == 'dust':
        icon.add(poly([(4, 27), (10, 19), (16, 15), (22, 19), (28, 27)]), 'main', 0.55, 3.0, glow=True,
                 pattern=speckle(seed, 0.3, 0.2))
        for (x, y) in ((9, 9), (17, 6), (24, 11), (13, 13)):
            icon.add(star(x, y, 2.4, 0.8, 4), 'accent', 1.0, 1.0, glow=True, flat=True)
    elif s == 'leaf':
        icon.add(ellipse(17, 14, 11, 6.5, -40), 'main', 0.55, 3.5, glow=True,
                 pattern=lambda x, y, d: -0.3 if abs((x - 17) * 0.64 + (y - 14) * 0.77) < 0.6 else 0)
        icon.add(capsule(6, 27, 10, 22, 1.0), 'wood', 0.55, 1.0)
    elif s == 'coin_pouch':
        icon.add(circle(16, 20, 9.5), 'grip', 0.55, 4.0, pattern=speckle(seed, -0.12, 0.2))
        icon.add(poly([(10, 12), (22, 12), (25, 5), (20, 8), (16, 4), (12, 8), (7, 5)]), 'grip', 0.6, 2.0)
        icon.add(rbox(16, 12, 6.5, 1.4, 0.5), 'accent', 0.6, 1.0)
        icon.add(circle(23, 26, 3.5), 'orn', 0.7, 2.0, gloss=True)
        icon.add(circle(27, 23, 3), 'orn', 0.65, 2.0)
    elif s == 'badge':
        icon.add(poly([(5, 4), (27, 4), (27, 16), (16, 29), (5, 16)]), 'main', 0.5, 3.0)
        icon.add(poly([(8, 7), (24, 7), (24, 15.5), (16, 25), (8, 15.5)]), 'main', 0.7, 2.0)
        icon.add(star(16, 14, 6, 2.6, 5), 'accent', 0.85, 1.5, glow=True)
    elif s == 'shell':
        icon.add(sub(ellipse(16, 20, 13, 10), lambda x, y: 21 - y), 'main', 0.55, 4.0, gloss=True,
                 pattern=lambda x, y, d: -0.25 if (int(math.degrees(math.atan2(y - 21, x - 16))) % 30) < 4 else 0)
        icon.add(rbox(16, 22, 13, 1.5, 0.6), 'main', 0.35, 1.0)
    elif s == 'crown':
        icon.add(poly([(4, 26), (4, 10), (10, 17), (16, 6), (22, 17), (28, 10), (28, 26)]), 'orn', 0.6, 2.5, gloss=True)
        icon.add(rbox(16, 23.5, 12, 2.5, 0.5), 'orn', 0.45, 1.2)
        for (x, y) in ((16, 15), (9, 21), (23, 21)):
            icon.add(circle(x, y, 2.0), 'accent', 0.85, 1.5, glow=True, gloss=True)
    elif s == 'blade':
        icon.add(poly([(5, 27), (8, 24), (21, 8), (24, 5), (25, 10), (22, 12), (24, 14), (10, 28)]), 'main', 0.65, 2.0, gloss=True, glow=True)
        icon.add(poly([(8, 24), (21, 8), (23, 10), (10, 26)]), 'main', 0.85, 1.0, glow=True)
    elif s == 'bell':
        icon.add(poly([(16, 4), (21, 7), (23, 18), (27, 24), (5, 24), (9, 18), (11, 7)]), 'main', 0.55, 4.0, gloss=True)
        icon.add(rbox(16, 24.5, 11, 1.8, 0.8), 'main', 0.4, 1.0)
        icon.add(circle(16, 27.5, 2.4), 'metal', 0.6, 1.5)
        icon.add(sub(circle(16, 3.5, 2.6), circle(16, 3.5, 1.2)), 'metal', 0.6, 1.0)
    elif s == 'pendulum':
        icon.add(rbox(16, 11, 1.1, 9, 0.5), 'metal', 0.55, 1.0)
        icon.add(sub(circle(16, 3, 2.6), circle(16, 3, 1.2)), 'metal', 0.6, 1.0)
        icon.add(circle(16, 22, 7.5), 'main', 0.58, 4.0, gloss=True)
        icon.add(circle(16, 22, 3), 'accent', 0.85, 2.0, glow=True)
    elif s == 'tendril':
        pts = [(6 + t * 0.7 + 4 * math.sin(t * 0.35), 28 - t) for t in range(0, 22)]
        for k, (a, b) in enumerate(zip(pts, pts[1:])):
            icon.add(capsule(a[0], a[1], b[0], b[1], 2.6 - k * 0.09), 'main', 0.55, 2.0, glow=True)
        cx, cy = pts[-1]
        for k in range(10):
            a = k * 0.7
            icon.add(circle(cx + math.cos(a) * (3.4 - k * 0.3), cy + math.sin(a) * (3.4 - k * 0.3), 1.2), 'main', 0.6, 1.0, glow=True)
    else:
        icon.add(circle(16, 16, 10), 'main', 0.55, 4.0, gloss=True)
        icon.add(circle(16, 16, 4), 'accent', 0.85, 2.0, glow=True)


ICON_STYLES = {'fiber', 'shard', 'ingot', 'core', 'silk_bundle', 'scale', 'bone', 'essence', 'gem', 'cloth', 'plate',
               'potion_small', 'potion', 'potion_large', 'scroll', 'key', 'rune_stone', 'gear', 'pearl', 'fang', 'spore',
               'ink_vial', 'feather', 'heart', 'dust', 'crystal', 'leaf', 'coin_pouch', 'map', 'badge', 'shell', 'crown',
               'blade', 'bell', 'page', 'coil', 'pendulum', 'tendril', 'blueprint'}
