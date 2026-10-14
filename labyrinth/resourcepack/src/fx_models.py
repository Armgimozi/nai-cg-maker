"""Weapon-skill effect models (`labyrinth:fx/<name>`): crescent sword-waves, shockwaves, orbs,
beams (tethers) and projectiles — original procedural geometry + animated motif textures.

Coordinate contract (ARCHITECTURE §2 / GDD §14.6): pivot at model (8,8,8); `size` [w,h,d] px is the
world size at display scale 1; models larger than the −16..32 element box are shrunk by s and
`display.fixed.scale = 1/s` (rotation/translation 0).
"""
from __future__ import annotations

import math

from .model import Model, fit_transform
from .util import Palette, clamp, darken, fbm, h2, h3, hue_shift, lighten, mix, vnoise
from .materials import rune_bit

C = 8.0


def _ramp(pal: Palette, n=6):
    cols = pal.raw
    return pal.ramp_n(n, cols if len(cols) >= 2 else None)


class FxSpec:
    def __init__(self, name, d):
        self.name = name
        self.d = d
        self.style = d.get('style', 'orb')
        self.motif = d.get('motif') or d.get('shape') or 'runes'
        self.pal = Palette(d.get('palette') or ['#202020', '#808080', '#ffffff'])
        self.ramp = _ramp(self.pal)
        self.frames = int(d.get('frames') or 1) if d.get('animated') else 1
        self.frames = max(1, min(32, self.frames))
        self.frametime = int(d.get('frametime') or 2)
        self.size = d.get('size') or [16, 16, 16]
        self.seed = h2(len(name), sum(map(ord, name)), 3) * 9999


def _col(ramp, q):
    q = clamp(q)
    return ramp[min(len(ramp) - 1, int(q * (len(ramp) - 1) + 0.5))]


# ───────────────────────────── motifs ─────────────────────────────

def motif_mod(motif, u, v, q, f, N, seed, ramp):
    """Modulate intensity q for a texel at plane coords (u,v ∈ [0,1]) and frame f.
    Returns (q, colour_override|None)."""
    p = f / max(1, N)
    s = int(seed)
    gx, gy = int(u * 64), int(v * 64)
    W = (255, 255, 255)
    if motif in ('flames', 'soul_flames', 'lava'):
        n = vnoise(u * 9, v * 9 + p * 6, s)
        q = q * (0.65 + 0.6 * n)
        if motif == 'soul_flames' and h2(gx, gy, s + f) > 0.992:
            return 1.0, W
    elif motif in ('sculk_veins', 'hyphae'):
        r = abs(fbm(u * 5, v * 5, s) - 0.5)
        if r < 0.05:
            band = 0.5 + 0.5 * math.sin(2 * math.pi * (u * 2 - p))
            return clamp(0.7 + 0.3 * band), None
        q *= 0.7
    elif motif == 'aurora_bands':
        w = math.sin(2 * math.pi * (u * 1.5 + v * 0.7 - p))
        col = mix(ramp[-2], (255, 140, 215), (w + 1) / 2)
        return q, (col if q > 0.35 else None)
    elif motif in ('blood_drops', 'venom_drops', 'mercury_drops'):
        if h2(gx // 3, gy // 3, s) > 0.9 and q > 0.2:
            return 1.0, None
        q *= 0.85 + 0.15 * math.sin(2 * math.pi * (p + u))
    elif motif in ('crescent', 'black_sun', 'corona'):
        q = q * (0.8 + 0.25 * math.sin(2 * math.pi * (u * 3 - p * 2)))
    elif motif in ('constellation', 'star_dots'):
        if h2(gx, gy, s) > 0.985 and q > 0.1:
            tw = math.cos(2 * math.pi * (p - h2(gx, gy, s + 1)))
            return 1.0, (W if tw > 0.3 else None)
        q *= 0.75
    elif motif in ('clock_gears', 'brass'):
        a = math.atan2(v - 0.5, u - 0.5)
        teeth = math.cos(12 * (a - p * math.pi / 6))
        q = q * (0.75 + (0.35 if teeth > 0.6 else 0))
    elif motif in ('script_letters', 'runes', 'halo_runes'):
        k = int(p * 8)
        if rune_bit(int(h2(gx // 4, 0, s) * 8), gx % 4, (gy + k) % 6) and q > 0.25:
            return 1.0, None
        q *= 0.8
    elif motif == 'sun_rays':
        a = math.atan2(v - 0.5, u - 0.5)
        if math.cos(16 * a + p * math.pi) > 0.7:
            q = min(1.0, q * 1.35)
    elif motif == 'wind_streaks':
        if ((u * 3 + v * 1.5 - p * 2) % 1.0) < 0.12:
            q = min(1.0, q * 1.4)
        else:
            q *= 0.8
    elif motif in ('geode_shards', 'crystal_facets', 'light_crystal', 'dark_crystal'):
        cell = h2(gx // 6, gy // 6, s)
        q = q * (0.7 + 0.5 * cell)
        if int(cell * N) == f and q > 0.3:
            return 1.0, W
    elif motif == 'ink_splash':
        n = fbm(u * 6, v * 6, s)
        if n < 0.35 + 0.15 * math.sin(2 * math.pi * p):
            q *= 0.4
    elif motif == 'thorns':
        if (gx + gy) % 7 == 0 and q > 0.3:
            q = 1.0
        q *= 0.9
    elif motif in ('frost', 'snowflakes'):
        if h2(gx, gy, s + f) > 0.97 and q > 0.15:
            return 1.0, W
    elif motif == 'feathers':
        if ((u * 10 + v * 4) % 1.0) < 0.2:
            q = min(1.0, q * 1.25)
    elif motif == 'lightning':
        path = 0.5 + (h2(int(u * 10), f, s) - 0.5) * 0.6
        if abs(v - path) < 0.03 and q > 0.1:
            return 1.0, W
    elif motif == 'waves':
        q = q * (0.75 + 0.3 * math.sin(2 * math.pi * (u * 4 + v * 2 - p)))
        if h2(gx, gy, s + f) > 0.985 and q > 0.2:
            return 1.0, W
    elif motif in ('void_rift', 'abyss_tide'):
        a = math.atan2(v - 0.5, u - 0.5)
        r = math.hypot(u - 0.5, v - 0.5)
        q = q * (0.6 + 0.5 * (math.sin(3 * a + r * 18 - 2 * math.pi * p) > 0))
    elif motif == 'copper_coils':
        if h2(gx, gy, s + f * 7) > 0.975 and q > 0.2:
            return 1.0, W
        q = q * (0.8 + 0.2 * math.sin(u * 40))
    else:
        q = q * (0.85 + 0.2 * math.sin(2 * math.pi * (u + v - p)))
    return q, None


# ───────────────────────────── style builders ─────────────────────────────

def _flat(m, w, d, y=C, density_faces=('up', 'down')):
    return m.box((C - w / 2, y - 0.05, C - d / 2), (C + w / 2, y + 0.05, C + d / 2), 'fx', faces=density_faces,
                 shade=False, emission=15, glow=True)


def build(spec: FxSpec):
    """→ (Model, texel_fn(texel, frame) -> (colour, alpha) | None)"""
    st = spec.style
    w, h, d = [float(x) for x in spec.size]
    m = Model('fx/' + spec.name, density=2 if max(w, d) <= 36 else 1)
    R = spec.ramp
    N = spec.frames

    if st == 'slash':
        _flat(m, w, d)
        # thin vertical spine for side visibility
        m.box((C - w * 0.35, C - h / 2, C - d / 2 + 1.0), (C + w * 0.35, C + h / 2, C - d / 2 + 1.2), 'fx',
              faces=('north', 'south'), shade=False, emission=15, glow=True)
        Rout = (w * w / 4 + d * d) / (2 * d)
        t = d * 0.45
        Rin = (w * w / 4 + (d - t) ** 2) / (2 * (d - t))

        def fn(tx, f):
            x, y, z = tx.pos
            px, pz = x - C, C - z      # forward (convex edge) = model −Z
            if tx.face in ('north', 'south'):
                u = (px + w / 2) / w
                q = 1 - abs(u - 0.5) * 2
                qq, oc = motif_mod(spec.motif, u, 0.5, q, f, N, spec.seed, R)
                return (oc or _col(R, 0.4 + qq * 0.6)), (255 if q > 0.15 else 0)
            co = (0.0, d / 2 - Rout)
            ci = (0.0, d / 2 - t - Rin)
            ro = math.hypot(px - co[0], pz - co[1])
            ri = math.hypot(px - ci[0], pz - ci[1])
            if ro > Rout or ri < Rin or pz < -d / 2:
                return (0, 0, 0), 0
            thick = (Rout - ro) / max(0.01, (Rout - ro) + (ri - Rin))
            q = 1.0 - thick       # 1 at leading (outer) edge
            u = (px + w / 2) / w
            sweep = 0.5 + 0.5 * math.sin(2 * math.pi * (u - f / max(1, N)))
            q = q * 0.8 + 0.25 * sweep * q
            q, oc = motif_mod(spec.motif, u, (pz + d / 2) / d, q, f, N, spec.seed, R)
            if q < 0.12:
                return (0, 0, 0), 0
            return (oc or _col(R, q)), 255
        return m, fn

    if st == 'shockwave':
        _flat(m, w, d)

        def fn(tx, f):
            x, y, z = tx.pos
            u, v = (x - C + w / 2) / w, (z - C + d / 2) / d
            r = math.hypot(u - 0.5, v - 0.5) * 2
            p = (f + 0.5) / max(1, N)
            rc = 0.25 + 0.7 * p
            th = 0.16 * (1 - 0.5 * p)
            dd = abs(r - rc)
            if dd > th or r > 1.0:
                inner = r < rc - th
                if inner and r > 0.15 and h2(int(u * 64), int(v * 64), int(spec.seed) + f) > 0.985:
                    return R[-1], 255
                return (0, 0, 0), 0
            q = 1 - dd / th
            q, oc = motif_mod(spec.motif, u, v, q, f, N, spec.seed, R)
            if q < 0.15:
                return (0, 0, 0), 0
            return (oc or _col(R, q)), 255
        return m, fn

    if st == 'orb':
        r = w / 2
        for sz in ((w, h * 0.5, d * 0.5), (w * 0.5, h, d * 0.5), (w * 0.5, h * 0.5, d), (w * 0.82, h * 0.82, d * 0.82)):
            m.cbox((C, C, C), sz, 'fx', shade=False, emission=15, glow=True)
        # corona planes
        m.box((C - r * 1.6, C - r * 1.6, C - 0.02), (C + r * 1.6, C + r * 1.6, C + 0.02), 'fx',
              faces=('north', 'south'), shade=False, emission=15, glow=True)

        def fn(tx, f):
            x, y, z = tx.pos
            if tx.el == 4:
                u, v = (x - C + r * 1.6) / (r * 3.2), (y - C + r * 1.6) / (r * 3.2)
                rr = math.hypot(u - 0.5, v - 0.5) * 2
                if rr < 0.55 or rr > 1.0:
                    return (0, 0, 0), 0
                a = math.atan2(v - 0.5, u - 0.5)
                ray = math.cos(6 * a + 2 * math.pi * f / max(1, N))
                q = (1 - rr) * 2.2 * (0.6 + 0.4 * ray)
                q, oc = motif_mod(spec.motif, u, v, q, f, N, spec.seed, R)
                if q < 0.3:
                    return (0, 0, 0), 0
                return (oc or _col(R, q)), 255
            u = (tx.i + 0.5) / tx.w
            v = (tx.j + 0.5) / tx.h
            core = 1 - math.hypot(u - 0.5, v - 0.5) * 1.3
            q = 0.45 + core * 0.6
            q, oc = motif_mod(spec.motif, u, v, q, f, N, spec.seed, R)
            return (oc or _col(R, q)), 255
        return m, fn

    if st == 'tether':
        m.cbox((C, C, C), (w * 0.4, h * 0.4, d), 'fx', shade=False, emission=15, glow=True)
        m.cbox((C, C, C), (w, h, d), 'fx', faces=('north', 'south', 'east', 'west', 'up', 'down'),
               shade=False, emission=15, glow=True)

        def fn(tx, f):
            x, y, z = tx.pos
            v = (z - C + d / 2) / d
            u = (tx.i + 0.5) / tx.w
            if tx.el == 0:
                q = 0.85 + 0.15 * math.sin(2 * math.pi * (v * 2 - f / max(1, N)))
                return _col(R, q), 255
            if tx.face in ('north', 'south'):
                return (0, 0, 0), 0
            edge = abs(u - 0.5) * 2
            q = (1 - edge) * 0.9
            q, oc = motif_mod(spec.motif, u, (v * 2 - f / max(1, N)) % 1.0, q, f, N, spec.seed, R)
            if q < 0.3 or (h2(tx.i, int(v * 32) - f, int(spec.seed)) > 0.7 and q < 0.6):
                return (0, 0, 0), 0
            return (oc or _col(R, q)), 255
        return m, fn

    # projectiles
    shape = spec.d.get('shape') or 'arrow'
    # projectiles fly toward model −Z (ItemDisplay renders the model turned 180° about Y)
    if shape in ('arrow', 'quill'):
        m.box((C - 0.5, C - 0.5, C - d / 2 + 3), (C + 0.5, C + 0.5, C + d / 2 - 2), 'fx', shade=False, emission=12, glow=True)
        m.cbox((C, C, C - d / 2 + 2.0), (w * 0.9, w * 0.9, 3.0), 'fx', shade=False, emission=15, glow=True,
               rot=('z', 45, (C, C, C - d / 2 + 2.0)))
        fl = 4.0 if shape == 'arrow' else d * 0.6
        m.cbox((C, C, C + d / 2 - fl / 2), (w, 0.2, fl), 'fx', shade=False, emission=12, glow=True)
        m.cbox((C, C, C + d / 2 - fl / 2), (0.2, w, fl), 'fx', shade=False, emission=12, glow=True)
    elif shape == 'shard':
        m.cbox((C, C, C), (w, h, d * 0.6), 'fx', shade=False, emission=13, glow=True, rot=('z', 45, (C, C, C)))
        m.cbox((C, C, C - d * 0.3), (w * 0.6, h * 0.6, d * 0.4), 'fx', shade=False, emission=15, glow=True,
               rot=('z', 45, (C, C, C - d * 0.3)))
        m.cbox((C, C, C + d * 0.32), (w * 0.5, h * 0.5, d * 0.36), 'fx', shade=False, emission=11, glow=True,
               rot=('z', 45, (C, C, C + d * 0.32)))
    elif shape in ('meteor', 'glob', 'web_ball'):
        for sz in ((w, h * 0.5, d * 0.5), (w * 0.5, h, d * 0.5), (w * 0.5, h * 0.5, d), (w * 0.8, h * 0.8, d * 0.8)):
            m.cbox((C, C, C), sz, 'fx', shade=shape != 'meteor', emission=12 if shape == 'meteor' else 0, glow=True)
        if shape == 'meteor':
            m.cbox((C, C, C + d * 0.55), (w * 0.5, h * 0.5, d * 0.6), 'fx', shade=False, emission=15, glow=True)
        if shape == 'web_ball':
            for ang in (0, 60, 120):
                m.cbox((C, C, C), (0.3, h * 1.15, w * 1.15), 'fx', rot=('y', ang, (C, C, C)) if ang else None)
    elif shape in ('pickaxe', 'hammer'):
        m.cbox((C, C - h * 0.1, C), (1.2, h * 0.85, 1.2), 'fx')
        if shape == 'hammer':
            m.cbox((C, C + h * 0.32, C), (w * 0.8, h * 0.3, min(d, w * 0.5)), 'fx')
            m.cbox((C, C + h * 0.32, C), (w * 0.9, h * 0.2, min(d, w * 0.5) * 0.8), 'fx')
        else:
            for s_ in (-1, 1):
                m.cbox((C + s_ * w * 0.25, C + h * 0.36, C), (w * 0.5, 1.6, 1.4), 'fx',
                       rot=('z', -s_ * 15, (C + s_ * w * 0.25, C + h * 0.36, C)))
    elif shape == 'hook':
        m.cbox((C, C + h * 0.15, C), (1.2, h * 0.65, 1.2), 'fx')
        m.cbox((C + w * 0.2, C - h * 0.3, C), (w * 0.5, 1.2, 1.2), 'fx')
        m.cbox((C + w * 0.42, C - h * 0.18, C), (1.2, h * 0.3, 1.2), 'fx', rot=('z', 15, (C + w * 0.42, C - h * 0.3, C)))
        m.cbox((C, C + h * 0.48, C), (2.4, 2.4, 1.0), 'fx')
    elif shape == 'anchor':
        m.cbox((C, C + 1, C), (2.0, h - 6, 2.0), 'fx')
        m.cbox((C, C + h / 2 - 2.5, C), (w * 0.55, 1.6, 1.6), 'fx')
        m.cbox((C, C + h / 2 - 0.5, C), (3.0, 3.0, 1.2), 'fx')
        for s in (-1, 1):
            x = C + s * w * 0.3
            m.cbox((x, C - h / 2 + 3.5, C), (w * 0.42, 2.0, 2.0), 'fx', rot=('z', -s * 30, (x, C - h / 2 + 3.5, C)))
            m.cbox((C + s * (w / 2 - 1.2), C - h / 2 + 6.5, C), (2.0, 3.6, 1.8), 'fx',
                   rot=('z', s * 20, (C + s * (w / 2 - 1.2), C - h / 2 + 6.5, C)))
        m.cbox((C, C - h / 2 + 2.0, C), (2.6, 2.6, 2.0), 'fx', rot=('z', 45, (C, C - h / 2 + 2.0, C)))
    elif shape == 'gear':
        m.cbox((C, C, C), (w * 0.7, h * 0.7, d), 'fx', glow=True)
        m.cbox((C, C, C), (w * 0.7, h * 0.7, d), 'fx', glow=True, rot=('z', 45, (C, C, C)))
        for k in range(4):
            m.cbox((C, C, C), (w, 1.4, d * 0.9), 'fx', glow=True, rot=('z', k * 45, (C, C, C)) if k else None)
    else:
        m.cbox((C, C, C), (w, h, d), 'fx', shade=False, emission=12, glow=True)

    def fn(tx, f):
        q = 0.45 + 0.5 * (1 - abs((tx.i + 0.5) / tx.w - 0.5) * 2) * (1 - abs((tx.j + 0.5) / tx.h - 0.5))
        if tx.face == 'up':
            q += 0.1
        if shape in ('meteor', 'glob', 'web_ball'):
            r_ = math.hypot((tx.i + 0.5) / tx.w - 0.5, (tx.j + 0.5) / tx.h - 0.5)
            q = 0.9 - r_ * 0.9 + (0.2 if h2(tx.i, tx.j - f, int(spec.seed)) > 0.8 else 0)
            if shape == 'web_ball' and (tx.i + tx.j) % 3 == 0:
                q += 0.3
        if shape in ('arrow', 'shard', 'quill', 'meteor'):
            v = (C + d / 2 - tx.pos[2]) / d
            band = 0.5 + 0.5 * math.sin(2 * math.pi * (v * 2 - f / max(1, N)))
            q = q * 0.8 + 0.3 * band
        if shape in ('pickaxe', 'hammer', 'hook', 'anchor') and N > 1:
            q += 0.2 * math.sin(2 * math.pi * ((tx.pos[1] - C) / max(1.0, h) - f / N))
        if shape == 'gear' and N > 1:
            a = math.atan2(tx.pos[1] - C, tx.pos[0] - C)
            if math.cos(4 * a - 2 * math.pi * f / N) > 0.85:
                q += 0.25
        return _col(R, q), 255
    return m, fn


def finalize_display(m: Model):
    """display.fixed = identity (or 1/s restore) + a GUI view for creative inspection."""
    s = m.fit_into_limits(pivot=(8, 8, 8))
    inv = 1.0 / s if s < 1.0 else 1.0
    m.display = {
        'fixed': {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [inv, inv, inv]},
        'gui': fit_transform(m, (30, 225, 0), target=15.0, max_scale=4.0),
        'ground': fit_transform(m, (0, 0, 0), target=8.0, max_scale=2.0),
    }
    return s
