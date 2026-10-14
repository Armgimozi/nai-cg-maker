"""Texel shaders: original procedural pixel-art materials for model UV atlases.

A shader turns a TexCtx (element, face, local texel, model-space position) into
(ramp, value, explicit_colour, alpha).  Values index a palette ramp so every frame stays
inside the item's palette — the classic pixel-art look — while effects can later shift
values per frame.
"""
from __future__ import annotations

import math

from .util import (Palette, clamp, darken, fbm, h2, h3, hue_shift, lighten, lum, mix, saturate, vnoise)

METALS = {'steel', 'silver', 'gold', 'copper', 'dark_iron', 'rusted_iron', 'clockwork', 'holy', 'obsidian'}
ORGANIC = {'wood', 'bone', 'leather', 'cloth', 'silk', 'moss', 'coral'}
ELEMENTAL = {'crystal', 'ember', 'frost', 'shadow', 'void', 'ink', 'abyss'}
ALL_STYLES = METALS | ORGANIC | ELEMENTAL

# Original 3×5 rune glyphs (bit rows, MSB = left)
RUNES = [
    (0b010, 0b111, 0b010, 0b010, 0b101),
    (0b110, 0b101, 0b110, 0b100, 0b100),
    (0b101, 0b101, 0b010, 0b101, 0b101),
    (0b111, 0b001, 0b011, 0b001, 0b111),
    (0b011, 0b100, 0b010, 0b001, 0b110),
    (0b100, 0b110, 0b101, 0b110, 0b100),
    (0b010, 0b101, 0b111, 0b101, 0b010),
    (0b111, 0b010, 0b010, 0b010, 0b111),
]


def rune_bit(gi, x, y):
    g = RUNES[gi % len(RUNES)]
    if 0 <= x < 3 and 0 <= y < 5:
        return (g[y] >> (2 - x)) & 1
    return 0


RARITY_LEVEL = {'common': 0, 'uncommon': 1, 'rare': 2, 'epic': 3, 'legendary': 4, 'mythic': 5}


def norm_style(style: str | None) -> str:
    if style in ALL_STYLES:
        return style
    return 'steel'


class Look:
    """Per-item colour/material set derived from palette + style + rarity."""

    def __init__(self, palette, style, rarity, seed):
        self.pal = palette if isinstance(palette, Palette) else Palette(palette)
        self.style = norm_style(style)
        self.rarity = rarity or 'common'
        self.level = RARITY_LEVEL.get(self.rarity, 0)
        self.seed = seed & 0xFFFF
        p = self.pal
        self.main = p.ramp_n(6)
        self.accent = p.accent_ramp(6)
        self.grip = p.grip_ramp(5)
        # metal used for guards/fittings: the item ramp unless the item is organic/elemental,
        # then a neutral-tinted metal derived from the palette's mid colour.
        if self.style in METALS:
            self.metal = self.main
        else:
            mid = p.ramp[len(p.ramp) // 2]
            base = [darken(mid, 0.65), darken(mid, 0.4), saturate(mix(mid, (150, 150, 160), 0.5), 0.6),
                    lighten(saturate(mix(mid, (170, 170, 180), 0.5), 0.5), 0.3), lighten(mid, 0.7)]
            self.metal = p.ramp_n(6, base)
        # ornament ramp: accent-tinted precious metal
        a = p.accent
        orn = [darken(a, 0.7), darken(mix(a, (200, 160, 60), 0.35), 0.4), mix(a, (230, 190, 90), 0.3),
               lighten(mix(a, (250, 220, 120), 0.3), 0.25), lighten(a, 0.75)]
        self.orn = p.ramp_n(6, orn)
        wood_src = self.main if self.style == 'wood' else None
        if wood_src is None:
            wb = mix(p.ramp[min(1, len(p.ramp) - 1)], (110, 72, 42), 0.6)
            wood_src = p.ramp_n(6, [darken(wb, 0.55), darken(wb, 0.3), wb, lighten(wb, 0.22), lighten(wb, 0.4)])
        self.wood = wood_src
        light = p.light
        self.string = p.ramp_n(4, [darken(light, 0.45), darken(light, 0.2), light, lighten(light, 0.5)])
        hb = mix(p.light, (225, 210, 180), 0.55)
        self.horn = p.ramp_n(6, [darken(hb, 0.6), darken(hb, 0.38), darken(hb, 0.18), hb, lighten(hb, 0.4)])
        self.dark = p.ramp_n(4, [darken(p.dark, 0.5), p.dark, mix(p.dark, p.ramp[1], 0.5), p.ramp[1]])
        self.patina = hue_shift(mix(p.ramp[len(p.ramp) // 2], (60, 160, 140), 0.65), 0, 1.1)
        self.rust = mix(p.ramp[len(p.ramp) // 2], (160, 78, 32), 0.6)


def _bevel(ctx, strength=1.0):
    w, h, i, j = ctx.w, ctx.h, ctx.i, ctx.j
    dv = 0.0
    if w >= 3:
        if i == 0:
            dv += 0.14 * strength
        elif i == w - 1:
            dv -= 0.2 * strength
    if h >= 3:
        if j == 0:
            dv += 0.12 * strength
        elif j == h - 1:
            dv -= 0.2 * strength
    if ctx.face == 'up':
        dv += 0.06
    elif ctx.face == 'down':
        dv -= 0.08
    return dv


def make_shader(look: Look, overrides=None):
    """Returns shader(ctx) -> (ramp, value, colour|None, alpha)."""
    overrides = overrides or {}
    seed = look.seed

    def along(ctx):
        """0..1 along the element's longest axis (in model space)."""
        e = ctx.el
        d = e.dims()
        k = max(range(3), key=lambda q: d[q])
        if d[k] <= 0:
            return 0.5
        return clamp((ctx.pos[k] - e.frm[k]) / d[k])

    def style_pattern(style, ctx, v, ramp_name):
        """Returns (v, colour|None)."""
        i, j, w, h = ctx.i, ctx.j, ctx.w, ctx.h
        x, y, z = ctx.pos
        gx, gy = int(round(x * 2 + z * 2)), int(round(y * 2))
        col = None
        n = h3(int(x * 2), int(y * 2), int(z * 2), seed)
        if style == 'steel':
            if (gx + gy + seed) % 9 == 0:
                v += 0.18
            v += (n - 0.5) * 0.08
        elif style == 'silver':
            v += 0.06
            if w >= 4 and h >= 4 and 0 < i < w - 1:
                curl = math.sin(gy * 0.9 + math.sin(gx * 1.3) * 2.0)
                if abs(curl) < 0.18:
                    v -= 0.24
            if n > 0.94:
                v += 0.25
        elif style == 'gold':
            v += 0.04
            if (gx * 3 + gy * 5 + seed) % 11 == 0:
                v += 0.22
            if w >= 4 and h >= 4 and (i == 1 or i == w - 2) and j % 2 == 0:
                v += 0.18
        elif style == 'copper':
            f = fbm(x * 0.35 + seed, y * 0.35, seed)
            if f > 0.62:
                col = mix(look.patina, lighten(look.patina, 0.4), (f - 0.62) * 3)
            v += (n - 0.5) * 0.1
        elif style == 'dark_iron':
            v -= 0.06
            v += (h2(gx // 2, gy // 2, seed) - 0.5) * 0.26
            if w >= 6 and h >= 6 and i in (1, w - 2) and j in (1, h - 2):
                v += 0.35
        elif style == 'rusted_iron':
            f = fbm(x * 0.5, y * 0.5 + seed * 0.01, seed + 7)
            if f > 0.57:
                col = mix(look.rust, darken(look.rust, 0.35), clamp((f - 0.57) * 4))
            v += (n - 0.5) * 0.14
        elif style == 'clockwork':
            if w >= 4 and h >= 4 and i in (1, w - 2) and j in (1, h - 2):
                v += 0.35
            elif (i == 0 or i == w - 1) and j % 3 == 0:
                v -= 0.2
            v += (n - 0.5) * 0.06
        elif style == 'holy':
            v += 0.08
            if w >= 4 and h >= 5 and ramp_name == 'main':
                gi = (gy // 6 + seed) % 8
                if rune_bit(gi, i - (w - 3) // 2, gy % 6):
                    col = look.accent[5]
            if n > 0.95:
                v += 0.3
        elif style == 'obsidian':
            v -= 0.12
            if (gx - gy + seed) % 7 == 0:
                col = look.accent[3]
            elif n > 0.9:
                v += 0.3
        elif style == 'wood':
            g = math.sin((ctx.pos[0] + ctx.pos[2]) * 2.3 + fbm(x * 0.3, y * 0.15, seed) * 6)
            v += 0.12 * (1 if g > 0.3 else -1 if g < -0.5 else 0)
            if h2(gx // 3, gy // 4, seed + 3) > 0.94:
                v -= 0.3
        elif style == 'bone':
            v += 0.08
            f = fbm(x * 0.6, y * 0.6, seed + 11)
            if abs(f - 0.5) < 0.025:
                v -= 0.35
            elif n > 0.9:
                v -= 0.15
        elif style == 'leather':
            v += (n - 0.5) * 0.14
            if w >= 4 and (i == 1 or i == w - 2) and j % 2 == 0:
                v += 0.3
        elif style == 'cloth':
            v += 0.07 if (gx + gy) % 2 == 0 else -0.07
            if w >= 5 and h >= 5 and (j == 1 or j == h - 2):
                col = look.accent[3]
        elif style == 'silk':
            s = math.sin((gx + gy * 0.6) * 0.5 + seed)
            v += 0.16 * s
        elif style == 'moss':
            v += (n - 0.5) * 0.45
            if n > 0.93:
                col = look.accent[4]
        elif style == 'coral':
            if gx % 3 == 1 and gy % 3 == 1:
                v -= 0.3
            v += (n - 0.5) * 0.12
        elif style == 'crystal':
            cell = _voronoi(x * 0.5, y * 0.35, z * 0.5, seed)
            v += (cell[0] - 0.5) * 0.4
            if cell[1] < 0.08:
                v += 0.28
            if n > 0.96:
                col = (255, 255, 255)
        elif style == 'ember':
            v -= 0.18
            r = abs(fbm(x * 0.45, y * 0.3, seed + 5) - 0.5)
            if r < 0.045:
                col = look.accent[4] if r < 0.02 else look.accent[3]
        elif style == 'frost':
            v += 0.06
            if ctx.face == 'up' or (h >= 3 and j == 0):
                v += 0.3
            if n > 0.95:
                col = (245, 252, 255)
            elif (gx * 7 + gy * 3) % 13 == 0:
                v += 0.2
        elif style == 'shadow':
            v -= 0.15
            f = fbm(x * 0.3, y * 0.25 - seed * 0.1, seed + 9)
            if f > 0.64:
                col = look.accent[2] if f < 0.7 else look.accent[3]
        elif style == 'void':
            v -= 0.25
            if n > 0.955:
                col = (255, 255, 255) if n > 0.985 else look.accent[4]
        elif style == 'ink':
            v -= 0.1
            if h2(gx, 0, seed + 13) > 0.7 and (y * 2) % 16 > h2(gx, 1, seed) * 10:
                v -= 0.2
            if n > 0.97:
                col = look.accent[4]
        elif style == 'abyss':
            v -= 0.18
            r = abs(fbm(x * 0.4 + 3, y * 0.4, seed + 21) - 0.5)
            if r < 0.04:
                col = look.accent[3] if r > 0.015 else look.accent[4]
        return v, col

    def shader(ctx):
        e = ctx.el
        role = e.role
        mat = e.mat or overrides.get(role)
        bev = _bevel(ctx)
        t = along(ctx)
        color = None
        alpha = 255
        if role in ('blade', 'head', 'plate', 'body', 'limb'):
            ramp, base = look.main, 0.55
            style = mat or look.style
            v = base + bev + (t - 0.5) * 0.12
            v, color = style_pattern(style, ctx, v, 'main')
            return ramp, v, color, alpha
        if role == 'edge':
            v = 0.82 + bev * 0.5 + (t - 0.5) * 0.1
            if h3(int(ctx.pos[0] * 2), int(ctx.pos[1] * 2), 1, seed) > 0.85:
                v += 0.15
            return look.main, v, None, alpha
        if role == 'fuller':
            v = 0.3 + bev * 0.4
            if look.level >= 3 and ctx.face in ('north', 'south') and ctx.w >= 1:
                gy = int(ctx.pos[1] * 2)
                gi = (gy // 6 + seed) % 8
                lx = ctx.i - (ctx.w - 3) // 2
                if ctx.w >= 3 and rune_bit(gi, lx, gy % 6):
                    return look.accent, 0.95, None, alpha
                if ctx.w < 3 and (gy % 3 == 0):
                    return look.accent, 0.85, None, alpha
            return look.main, v, None, alpha
        if role in ('guard', 'pommel', 'metal', 'cap', 'band'):
            ramp = look.metal
            style = mat or (look.style if look.style in METALS else 'steel')
            v = (0.5 if role != 'pommel' else 0.55) + bev
            v, color = style_pattern(style, ctx, v, 'metal')
            return ramp, v, color, alpha
        if role == 'orn':
            v = 0.6 + bev
            v, color = style_pattern('gold', ctx, v, 'orn')
            return look.orn, v, color, alpha
        if role == 'grip':
            # spiral leather wrap
            x, y, z = ctx.pos
            k = int(math.floor(y * 2 + (x + z) * 1.0))
            v = 0.55 + (0.22 if k % 3 == 0 else -0.12 if k % 3 == 2 else 0.0) + bev * 0.5
            return look.grip, v, None, alpha
        if role in ('wood', 'shaft'):
            ramp = look.wood if (mat or 'wood') == 'wood' else look.metal
            v = 0.5 + bev
            v, color = style_pattern(mat or 'wood', ctx, v, 'wood')
            return ramp, v, color, alpha
        if role == 'string':
            return look.string, 0.7 + ((ctx.j // 2) % 2) * 0.15, None, alpha
        if role in ('gem', 'crystal'):
            a, b = ctx.a, ctx.b
            v = 0.95 - 0.55 * (a * 0.5 + b * 0.5)
            if ctx.border and ctx.w >= 3 and ctx.h >= 3:
                v -= 0.18
            if ctx.w >= 3 and ctx.h >= 3 and ctx.i == 1 and ctx.j == 1:
                return look.accent, 1.0, (255, 255, 255), alpha
            if role == 'crystal':
                cell = _voronoi(ctx.pos[0] * 0.8, ctx.pos[1] * 0.5, ctx.pos[2] * 0.8, seed)
                v += (cell[0] - 0.5) * 0.3
            if ctx.face == 'up':
                v += 0.1
            return look.accent, v, None, alpha
        if role == 'glow':
            d = max(abs(ctx.a - 0.5), abs(ctx.b - 0.5)) * 2
            v = 1.0 - d * 0.45
            return look.accent, v, None, alpha
        if role == 'rune':
            x, y, z = ctx.pos
            gi = (int(y) // 3 + seed) % 8
            if rune_bit(gi, ctx.i % 4, ctx.j % 6):
                return look.accent, 1.0, None, alpha
            return look.accent, 0.45, None, alpha
        if role == 'cloth':
            v = 0.5 + bev
            v, color = style_pattern(mat or 'cloth', ctx, v, 'main')
            return look.main, v, color, alpha
        if role == 'leather':
            v = 0.5 + bev
            v, color = style_pattern('leather', ctx, v, 'grip')
            return look.grip, v, color, alpha
        if role == 'horn':
            v = 0.45 + bev + t * 0.35
            v, color = style_pattern('bone', ctx, v, 'string')
            return look.horn, v, color, alpha
        if role == 'dark':
            return look.dark, 0.2 + bev * 0.3, None, alpha
        if role == 'trim':
            v = 0.62 + bev
            return look.orn, v, None, alpha
        if role == 'chain':
            v = 0.45 + (0.3 if (ctx.i + ctx.j) % 2 == 0 else -0.1)
            return look.metal, v, None, alpha
        # fallback
        v = 0.5 + bev
        v, color = style_pattern(look.style, ctx, v, 'main')
        return look.main, v, color, alpha

    return shader


def _voronoi(x, y, z, seed):
    """Tiny 2.5D cellular noise → (cell value, edge distance)."""
    xi, yi = math.floor(x), math.floor(y)
    best, second, val = 9.0, 9.0, 0.0
    zz = int(math.floor(z))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = xi + dx, yi + dy
            px = cx + h3(cx, cy, zz, seed)
            py = cy + h3(cx, cy, zz, seed + 1)
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best:
                second, best, val = best, d, h3(cx, cy, zz, seed + 2)
            elif d < second:
                second = d
    return val, math.sqrt(second) - math.sqrt(best)
