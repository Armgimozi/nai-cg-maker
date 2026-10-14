"""Equipment-layer textures (64×32 humanoid / humanoid_leggings) for every armour set.

Original designs per set silhouette (`sets.<id>.look`: heavy | light | cloth), coloured from the
set's chest piece (GDD §14.7).  The head region stays empty: helmets are 3D item models.
"""
from __future__ import annotations

import math

from PIL import Image

from .model import value_to_color
from .util import darken, h2, lighten, mix

# (x, y, w, h) regions of the vanilla-compatible 64×32 humanoid armour UV layout
BODY = {'top': (20, 16, 8, 4), 'bottom': (28, 16, 8, 4), 'right': (16, 20, 4, 12), 'front': (20, 20, 8, 12),
        'left': (28, 20, 4, 12), 'back': (32, 20, 8, 12)}
ARM = {'top': (44, 16, 4, 4), 'bottom': (48, 16, 4, 4), 'outer': (40, 20, 4, 12), 'front': (44, 20, 4, 12),
       'inner': (48, 20, 4, 12), 'back': (52, 20, 4, 12)}
LEG = {'top': (4, 16, 4, 4), 'bottom': (8, 16, 4, 4), 'outer': (0, 20, 4, 12), 'front': (4, 20, 4, 12),
       'inner': (8, 20, 4, 12), 'back': (12, 20, 4, 12)}


class Painter:
    def __init__(self, look, seed):
        self.img = Image.new('RGBA', (64, 32), (0, 0, 0, 0))
        self.px = self.img.load()
        self.look = look
        self.seed = seed & 0xFFFF

    def put(self, x, y, c):
        if 0 <= x < 64 and 0 <= y < 32:
            self.px[x, y] = (c[0], c[1], c[2], 255)

    def clear(self, x, y):
        self.px[x, y] = (0, 0, 0, 0)

    def face(self, rect, fn):
        x0, y0, w, h = rect
        for j in range(h):
            for i in range(w):
                r = fn(i, j, w, h)
                if r is None:
                    continue
                if isinstance(r, tuple) and len(r) == 2:
                    ramp, v = r
                    self.put(x0 + i, y0 + j, value_to_color(ramp, v))
                else:
                    self.put(x0 + i, y0 + j, r)


def _bev(i, j, w, h):
    dv = 0.0
    if i == 0:
        dv += 0.1
    if i == w - 1:
        dv -= 0.15
    if j == h - 1:
        dv -= 0.12
    return dv


def _noise(lk, i, j, salt, amp=0.12):
    return (h2(i + salt * 13, j + salt * 7, lk.seed) - 0.5) * amp


def paint_set(look, look_kind: str, seed: int):
    """Returns (humanoid_img, leggings_img)."""
    hum = Painter(look, seed)
    leg = Painter(look, seed + 1)
    lk = look
    M, G, O, A = lk.main, lk.grip, lk.orn, lk.accent
    kind = look_kind if look_kind in ('heavy', 'light', 'cloth') else 'heavy'
    lvl = lk.level

    # ───── chest (body + arms) ─────
    def body_face(name):
        def fn(i, j, w, h):
            n = _noise(lk, i, j, len(name))
            if kind == 'heavy':
                v = 0.5 + _bev(i, j, w, h) + n
                if name in ('front', 'back'):
                    if j < 6 and abs(i - (w - 1) / 2) < 1 and name == 'front':
                        v += 0.22                                    # chest ridge
                    if j >= 6 and j % 2 == 0:
                        v -= 0.2                                     # lames
                    if (i in (0, w - 1)) and j in (1, 5):
                        return O, 0.85                               # rivets
                    if j == h - 1:
                        return G, 0.45                               # belt
                    if name == 'front' and lvl >= 2 and j == 3 and abs(i - (w - 1) / 2) < 1:
                        return A, 0.95
                elif name in ('left', 'right'):
                    if j % 3 == 2:
                        v -= 0.18
                    if j == h - 1:
                        return G, 0.4
                return M, v
            if kind == 'light':
                v = 0.5 + _bev(i, j, w, h) + n
                if name in ('front', 'back'):
                    if abs((i - j * 0.66) - (1 if name == 'front' else 5)) < 0.8:
                        return O if lvl >= 2 else G, 0.65                # diagonal strap
                    if j in (0, 1):
                        return M, 0.25                               # hood shadow
                    if j == h - 2:
                        return G, 0.35
                    if name == 'front' and i in (w // 2 - 1,) and j % 2 == 0 and 2 < j < h - 2:
                        return G, 0.85                               # lacing
                    if name == 'front' and lvl >= 3 and 7 <= i <= 7 and 8 <= j <= 9:
                        return A, 0.9
                    if j == 5 or j == 6:
                        return G, 0.55 + n                           # leather harness band
                return M, v - 0.06
            # cloth / robe
            v = 0.5 + _bev(i, j, w, h) + n * 0.5
            if name == 'front' and abs(i - (w - 1) / 2) < 1:
                return O, 0.7 + (0.15 if j % 2 == 0 else 0)          # embroidered centre panel
            if j in (h - 1, h - 2) or (name == 'front' and j == 0):
                return O, 0.62 if j != h - 1 else 0.5
            if j == 7:
                return G, 0.5                                        # sash
            if name == 'front' and lvl >= 2 and j == 3 and abs(i - (w - 1) / 2) >= 2 and abs(i - (w - 1) / 2) < 3:
                return A, 0.9
            return M, v
        return fn

    for name, rect in BODY.items():
        hum.face(rect, body_face(name))

    def arm_face(name):
        def fn(i, j, w, h):
            n = _noise(lk, i, j, 40 + len(name))
            if kind == 'heavy':
                if j < 4:
                    v = 0.68 + _bev(i, j, w, h) + n - (0.18 if j == 3 else 0)   # pauldron
                    if j == 0 and lvl >= 3:
                        return O, 0.8
                    return M, v
                if j < 7:
                    return M, 0.38 + n                               # mail sleeve
                v = 0.52 + _bev(i, j, w, h) + n
                if j == 7 or j == h - 1:
                    return O if lvl >= 1 else M, 0.62
                return M, v
            if kind == 'light':
                if j < 5:
                    if name in ('outer', 'top') or j < 2:
                        return M, 0.45 + n + (0.2 if j == 0 else 0)  # shoulder pad
                    return None                                      # bare upper arm
                if j < 7:
                    return None
                if j == 7 or j == h - 1:
                    return O if lvl >= 2 else G, 0.62
                return (G if (i + j) % 3 == 0 else M), 0.5 + n
            # cloth sleeves
            if j >= h - 2:
                return O, 0.65
            return M, 0.48 + n * 0.5 + (0.1 if name == 'outer' else 0)
        return fn

    for name, rect in ARM.items():
        hum.face(rect, arm_face(name))

    # ───── boots (legs region of humanoid layer, lower 5 rows + bottom) ─────
    def boot_face(name):
        def fn(i, j, w, h):
            if name == 'top':
                return None
            if name == 'bottom':
                return G, 0.2
            if j < 7:
                return None
            n = _noise(lk, i, j, 70 + len(name))
            if kind == 'heavy':
                if j == 7:
                    return O if lvl >= 1 else M, 0.66
                if name == 'front' and j >= 10:
                    return M, 0.72 + n                               # toe cap
                return M, 0.5 + n + _bev(i, j, w, h)
            if kind == 'light':
                if j == 7:
                    return G, 0.7
                return (G, 0.6 + n) if (i + j) % 4 == 0 else (M, 0.42 + n)  # wraps
            if j == 7:
                return O, 0.6
            return M, 0.4 + n
        return fn

    for name, rect in LEG.items():
        hum.face(rect, boot_face(name))

    # ───── leggings layer ─────
    def belt_face(name):
        def fn(i, j, w, h):
            if name in ('top', 'bottom'):
                return None
            if kind == 'cloth':
                if j < 7:
                    return None
                return (O, 0.62) if j in (7, h - 1) else (M, 0.48 + _noise(lk, i, j, 90))
            if j < 9:
                return None
            if j == 9 or j == 10:
                if name == 'front' and abs(i - 3.5) < 1:
                    return O, 0.85                                   # buckle
                return G, 0.45 + (0.12 if j == 9 else 0)
            return M if kind == 'heavy' else G, 0.5 + _noise(lk, i, j, 91)
        return fn

    for name, rect in BODY.items():
        leg.face(rect, belt_face(name))

    def leg_face(name):
        def fn(i, j, w, h):
            n = _noise(lk, i, j, 100 + len(name))
            if name == 'bottom':
                return None
            if name == 'top':
                return (M if kind != 'light' else G), 0.4
            if kind == 'heavy':
                if 5 <= j <= 6 and name in ('front', 'outer'):
                    return (O, 0.75) if (j == 5 and lvl >= 2) else (M, 0.78 + n)  # knee cop
                if j > 9:
                    return M, 0.35 + n
                return M, 0.52 + n + _bev(i, j, w, h) - (0.15 if j % 3 == 2 else 0)
            if kind == 'light':
                if j in (2, 8) and name in ('front', 'outer'):
                    return O if lvl >= 2 else G, 0.66                   # thigh straps
                return M, 0.44 + n + _bev(i, j, w, h)
            # cloth trousers / skirt
            if name == 'outer' and i == 1:
                return O, 0.62
            return M, 0.46 + n * 0.6 + _bev(i, j, w, h) * 0.6
        return fn

    for name, rect in LEG.items():
        leg.face(rect, leg_face(name))
    _trims(hum, leg, lk, kind, lvl)
    return hum.img, leg.img


GLOW_ALPHA = 252   # emissive marker (owner's pack convention; fullbright once a core shader is added)


def _trims(hum: Painter, leg: Painter, lk, kind, lvl):
    """Pass-2 finish (reference look): metal trim edges, set gems and — on legendary/mythic sets —
    glowing seam lines marked with alpha 252."""
    O, A = lk.orn, lk.accent
    trim = value_to_color(O, 0.72)
    trim_hi = value_to_color(O, 0.9)
    trim_lo = value_to_color(O, 0.45)
    gem_hi, gem, gem_lo = value_to_color(A, 0.95), value_to_color(A, 0.75), value_to_color(A, 0.45)
    glow = lighten(value_to_color(A, 0.85), 0.25)
    glow_core = lighten(glow, 0.5)

    def glow_px(pt: Painter, x, y, c):
        if 0 <= x < 64 and 0 <= y < 32 and pt.px[x, y][3]:
            pt.px[x, y] = (c[0], c[1], c[2], GLOW_ALPHA)

    def solid(pt: Painter, x, y, c):
        if 0 <= x < 64 and 0 <= y < 32 and pt.px[x, y][3]:
            pt.put(x, y, c)

    fx, fy, fw, fh = BODY['front']
    bx, by, bw, bh = BODY['back']
    if lvl >= 1:
        # collar trim on chest front/back + shoulder caps
        for i in range(fw):
            solid(hum, fx + i, fy, trim_hi if i % 3 else trim)
            solid(hum, bx + i, by, trim)
        for name in ('outer', 'front', 'back', 'inner'):
            x0, y0, w, h = ARM[name]
            for i in range(w):
                solid(hum, x0 + i, y0, trim)
                if kind != 'cloth':
                    solid(hum, x0 + i, y0 + 1, trim_lo)
    if lvl >= 2:
        # set gem in the sternum: 2×2 faceted
        cx = fx + fw // 2 - 1
        for (dx, dy, c) in ((0, 0, gem_hi), (1, 0, gem), (0, 1, gem), (1, 1, gem_lo)):
            solid(hum, cx + dx, fy + 3 + dy, c)
        for (dx, dy) in ((-1, 0), (-1, 1), (2, 0), (2, 1), (0, -1), (1, -1), (0, 2), (1, 2)):
            solid(hum, cx + dx, fy + 3 + dy, trim)
        # knee / boot trims
        for name in ('front', 'outer'):
            x0, y0, w, h = LEG[name]
            for i in range(w):
                solid(hum, x0 + i, y0 + 7, trim)
                solid(leg, x0 + i, y0, trim)
    if lvl >= 4:
        # glowing seams: chest flanks → gem, arm runes, leg lines, boot rims
        for j in range(5, fh - 1):
            glow_px(hum, fx + 1, fy + j, glow)
            glow_px(hum, fx + fw - 2, fy + j, glow)
            glow_px(hum, bx + bw // 2 - 1 + (j % 2), by + j, glow)
        cx = fx + fw // 2 - 1
        glow_px(hum, cx, fy + 3, glow_core)
        for name in ('outer', 'front'):
            x0, y0, w, h = ARM[name]
            for j in range(4, h - 2, 2):
                glow_px(hum, x0 + (1 if name == 'outer' else w - 2), y0 + j, glow)
        for name in ('front', 'outer'):
            x0, y0, w, h = LEG[name]
            for j in range(1, 7):
                glow_px(leg, x0 + (1 if name == 'front' else 2), y0 + j, glow)
            for i in range(w):
                glow_px(hum, x0 + i, y0 + h - 1, glow)
    if lvl >= 5:
        # mythic: rune dots ringing the chest + shoulder sigils
        for (dx, dy) in ((2, 8), (5, 8), (3, 10), (4, 10)):
            glow_px(hum, fx + dx, fy + dy, glow_core)
        for name in ('outer',):
            x0, y0, w, h = ARM[name]
            for (dx, dy) in ((1, 2), (2, 2), (1, 3), (2, 3)):
                glow_px(hum, x0 + dx, y0 + dy, glow_core)
