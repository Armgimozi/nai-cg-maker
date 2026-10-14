"""Remaining fx.yml model styles (GDD §14.4): aura rings, telegraph decals, glyphs, runes, markers,
crystals, domes/shells, wings, pillar, banner, puddle, water plane, props (sac, cocoon, pole, ice block,
clock hand, pendulum, wall, disguises).  Original procedural geometry + animated textures.

Anchors (ARCHITECTURE §2 "fx 앵커"): every model is centred on the pivot (8,8,8) except
  * telegraph_line / telegraph_arrow / telegraph_cone / clock_hand: they START at the pivot and extend toward
    model −Z (= the ItemDisplay's facing direction after the client's 180° turn), so scaling Z = length;
  * pendulum: the pivot is the top of the rod (swing = rotate about the display's Z axis).
Flat decals (`flat: true`) are a 0.1 px plate whose up face carries the texture.
"""
from __future__ import annotations

import math

from .fx_models import FxSpec, _col, motif_mod
from .materials import rune_bit
from .model import Model
from .util import clamp, darken, fbm, h2, h3, lighten, mix, vnoise

C = 8.0
T = (0, 0, 0)
W = (255, 255, 255)
EXTRA_STYLES = {
    'ring', 'rune', 'marker', 'crystal', 'glyph', 'telegraph_circle', 'telegraph_ring', 'telegraph_line',
    'telegraph_cone', 'telegraph_arrow', 'telegraph_tile', 'dome', 'disguise', 'shell', 'wings', 'pillar', 'banner',
    'puddle', 'sac', 'cocoon', 'plane', 'pole', 'ice_block', 'clock_hand', 'pendulum', 'wall',
}


def _flat_up(m, x0, z0, x1, z1, y=C, emission=15):
    return m.box((x0, y - 0.05, z0), (x1, y + 0.05, z1), 'fx', faces=('up',), shade=False, emission=emission, glow=True)


def _uv_up(tx, x0, z0, x1, z1):
    x, y, z = tx.pos
    return (x - x0) / max(1e-6, x1 - x0), (z - z0) / max(1e-6, z1 - z0)


def _plane_xy(m, w, h, z=C, faces=('north', 'south'), emission=15, shade=False, y0=None):
    yb = C - h / 2 if y0 is None else y0
    return m.box((C - w / 2, yb, z - 0.05), (C + w / 2, yb + h, z + 0.05), 'fx', faces=faces, shade=shade,
                 emission=emission, glow=True)


# ───────────────────────────── symbol SDFs (u, v ∈ [0,1], v down) ─────────────────────────────

def _seg_d(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    t = clamp((wx * vx + wy * vy) / max(1e-9, vx * vx + vy * vy))
    return math.hypot(wx - vx * t, wy - vy * t)


def symbol(name, u, v):
    """Distance-ish value (<0.06 = stroke) for original rune/sigil/marker symbols."""
    x, y = u - 0.5, v - 0.5
    r = math.hypot(x, y)
    a = math.atan2(y, x)
    if name == 'rune_eye':
        lid = abs(abs(y) - 0.22 * math.cos(min(1.0, abs(x) / 0.36) * math.pi / 2)) if abs(x) < 0.36 else 1
        return min(lid, abs(r - 0.09))
    if name == 'rune_key':
        return min(abs(math.hypot(x, y + 0.2) - 0.1), _seg_d(x, y, 0, -0.1, 0, 0.32),
                   _seg_d(x, y, 0, 0.2, 0.12, 0.2), _seg_d(x, y, 0, 0.3, 0.1, 0.3))
    if name == 'rune_moon':
        return max(abs(r - 0.3) - 0.0, -(math.hypot(x - 0.14, y - 0.04) - 0.26)) if r < 0.33 else abs(r - 0.3)
    if name == 'rune_flame':
        k = (y + 0.32) / 0.64
        half = 0.2 * math.sin(clamp(k) * math.pi) * (1.0 if k > 0.35 else 0.7)
        return abs(abs(x + 0.04 * math.sin(k * 7)) - half) if -0.32 < y < 0.32 else 1
    if name == 'rune_wave':
        return min(abs(y - 0.12 * math.sin(x * 14) + 0.14), abs(y - 0.12 * math.sin(x * 14 + 1.5) - 0.14)) if abs(x) < 0.36 else 1
    if name == 'rune_tree':
        return min(_seg_d(x, y, 0, 0.34, 0, -0.32), _seg_d(x, y, 0, 0.0, -0.22, -0.22), _seg_d(x, y, 0, 0.0, 0.22, -0.22),
                   _seg_d(x, y, 0, 0.18, -0.16, 0.0), _seg_d(x, y, 0, 0.18, 0.16, 0.0))
    if name in ('rune_star', 'sigil_star', 'star'):
        pts = [(math.cos(-math.pi / 2 + k * 4 * math.pi / 5) * 0.34, math.sin(-math.pi / 2 + k * 4 * math.pi / 5) * 0.34)
               for k in range(6)]
        return min(_seg_d(x, y, *pts[k], *pts[k + 1]) for k in range(5))
    if name == 'rune_crown':
        zz = [(-0.32, 0.2), (-0.32, -0.18), (-0.16, 0.02), (0, -0.26), (0.16, 0.02), (0.32, -0.18), (0.32, 0.2), (-0.32, 0.2)]
        return min(_seg_d(x, y, *zz[k], *zz[k + 1]) for k in range(len(zz) - 1))
    if name == 'sigil_blade':
        return min(_seg_d(x, y, 0, -0.36, 0, 0.22), _seg_d(x, y, -0.16, 0.12, 0.16, 0.12), _seg_d(x, y, 0, 0.22, 0, 0.34) * 1.4)
    if name == 'sigil_arrow':
        return min(_seg_d(x, y, 0, -0.34, 0, 0.34), _seg_d(x, y, 0, -0.34, -0.16, -0.16), _seg_d(x, y, 0, -0.34, 0.16, -0.16),
                   _seg_d(x, y, 0, 0.34, -0.12, 0.22), _seg_d(x, y, 0, 0.34, 0.12, 0.22))
    if name == 'crosshair':
        return min(abs(r - 0.3), _seg_d(x, y, -0.45, 0, -0.14, 0), _seg_d(x, y, 0.14, 0, 0.45, 0),
                   _seg_d(x, y, 0, -0.45, 0, -0.14), _seg_d(x, y, 0, 0.14, 0, 0.45), r - 0.04)
    if name == 'spore_burst':     # spread: arrows pointing outward
        k = (a / (2 * math.pi / 6)) % 1.0
        return min(abs(r - 0.12), abs(k - 0.5) * r * 2.4 if 0.2 < r < 0.42 else 1, abs(r - 0.42) + abs(k - 0.5) * 0.3)
    if name == 'bloom':           # stack: arrows pointing inward to a centre dot
        k = (a / (2 * math.pi / 4)) % 1.0
        return min(r - 0.09, abs(k - 0.5) * r * 2.4 if 0.18 < r < 0.44 else 1,
                   abs((r - 0.2) - abs(k - 0.5) * 0.5) if r < 0.3 else 1)
    if name == 'jaw_trap':
        teeth = abs(((a / (2 * math.pi)) * 16) % 1.0 - 0.5)
        return min(abs(r - 0.4), abs(r - 0.3 + teeth * 0.12) if 0.18 < r < 0.42 else 1, abs(r - 0.08))
    if name == 'cross_flower':
        petals = abs(r - 0.22 - 0.08 * math.cos(4 * a))
        return min(petals, _seg_d(x, y, -0.1, 0, 0.1, 0), _seg_d(x, y, 0, -0.1, 0, 0.1))
    if name == 'clock_seal':
        tick = 1 if (int((a + math.pi) / (2 * math.pi) * 12 + 0.5) % 1 == 0 and abs(r - 0.36) < 0.05 and
                     abs(((a + math.pi) / (2 * math.pi) * 12) % 1.0 - 0.5) > 0.42) else 0
        return min(abs(r - 0.42), abs(r - 0.3), 0.0 if tick else 1, _seg_d(x, y, 0, 0, 0, -0.24), _seg_d(x, y, 0, 0, 0.16, 0.06))
    if name == 'shield_crest':
        shield = max(abs(x) - 0.26, y - 0.3 + abs(x) * 0.8, -y - 0.3)
        return min(abs(shield), _seg_d(x, y, 0, -0.18, 0, 0.18), _seg_d(x, y, -0.12, -0.04, 0.12, -0.04))
    # generic sigil ring
    return min(abs(r - 0.36), abs(r - 0.2))


# ───────────────────────────── builders ─────────────────────────────

def build(spec: FxSpec):
    st = spec.style
    w, h, d = [float(x) for x in spec.size]
    big = max(w, h, d)
    m = Model('fx/' + spec.name, density=2 if big <= 36 else 1)
    R = spec.ramp
    N = spec.frames
    mot = spec.motif
    seed = spec.seed
    tile = spec.d.get('size') is not None

    def P(f):
        return f / max(1, N)

    # ── flat decals ───────────────────────────────────────────────
    if st in ('ring', 'glyph', 'telegraph_circle', 'telegraph_ring', 'telegraph_tile', 'puddle', 'plane'):
        _flat_up(m, C - w / 2, C - d / 2, C + w / 2, C + d / 2)

        def fn(tx, f):
            u, v = _uv_up(tx, C - w / 2, C - d / 2, C + w / 2, C + d / 2)
            x, y = u - 0.5, v - 0.5
            r = math.hypot(x, y) * 2
            a = math.atan2(y, x)
            p = P(f)
            gx, gy = int(u * 64), int(v * 64)
            if st == 'ring':
                if r > 1.0 or r < 0.5:
                    return T, 0
                if abs(r - 0.97) < 0.03 or abs(r - 0.53) < 0.025:
                    return _col(R, 0.85), 255
                band = (r - 0.55) / 0.4
                rep = 12 if spec.size[0] < 30 else 16
                uu = ((a / (2 * math.pi)) * rep + p) % 1.0
                q = 0.75 - abs(band - 0.5) * 0.9
                q, oc = motif_mod(mot, uu, band, q, f, N, seed, R)
                if q < 0.18:
                    return T, 0
                return (oc or _col(R, q)), 255
            if st == 'glyph':
                if r > 1.0:
                    return T, 0
                rings = min(abs(r - 0.96), abs(r - 0.78), abs(r - 0.3))
                if rings < 0.025:
                    return _col(R, 0.9), 255
                if 0.8 < r < 0.94:   # rotating rune band
                    k = (a / (2 * math.pi) + p * 0.25) % 1.0
                    gi = int(k * 20)
                    lx = int((k * 20 - gi) * 4)
                    ly = int((r - 0.8) / 0.14 * 6)
                    if rune_bit(gi, lx, ly - 0):
                        return _col(R, 0.95), 255
                    return T, 0
                if r < 0.78:
                    s_ = symbol(mot, (x / 0.78) + 0.5, (y / 0.78) + 0.5)
                    poly = abs(r * math.cos((a + p * 0.5) % (2 * math.pi / 6) - math.pi / 6) - 0.62) < 0.02
                    if s_ < 0.035 or poly:
                        q = 0.85 + 0.15 * math.sin(2 * math.pi * (p - r))
                        return _col(R, q), 255
                    q, oc = motif_mod(mot, u, v, 0.3, f, N, seed, R)
                    if (h2(gx, gy, int(seed)) > 0.985) or oc:
                        return (oc or _col(R, 0.7)), 255
                return T, 0
            if st in ('telegraph_circle', 'telegraph_ring'):
                inner = 0.46 if st == 'telegraph_ring' else -1
                if r > 1.0 or r < inner:
                    return T, 0
                edge = min(1.0 - r, (r - inner) if inner > 0 else 9)
                pulse = 0.5 + 0.5 * math.sin(2 * math.pi * p)
                if edge < 0.06:
                    return _col(R, 0.75 + 0.25 * pulse), 255
                wave = (p * 1.0) % 1.0     # sweep from centre to rim = windup progress feel
                if abs(r - (inner if inner > 0 else 0) - wave * (1 - max(0, inner))) < 0.035:
                    return _col(R, 0.95), 255
                hatch = ((u + v) * 9 - p * 2) % 1.0
                if hatch < 0.22:
                    return _col(R, 0.55 + 0.2 * pulse), 200
                return _col(R, 0.3), 90
            if st == 'telegraph_tile':
                ex = min(u, v, 1 - u, 1 - v)
                pulse = 0.5 + 0.5 * math.sin(2 * math.pi * p)
                if ex < 0.06:
                    return _col(R, 0.8 + 0.2 * pulse), 255
                crack = abs(vnoise(u * 5, v * 5, int(seed)) - 0.5) < 0.04 or abs(u - v) < 0.02 and h2(gx, 3, 1) > 0.3
                if crack:
                    return _col(R, 0.6 + 0.4 * pulse), 255
                return _col(R, 0.3 + 0.1 * pulse), 100
            if st == 'puddle':
                edge = 0.8 + 0.15 * math.sin(5 * a + 1.3) + 0.06 * math.sin(11 * a)
                if r > edge:
                    return T, 0
                n = fbm(u * 5 + p, v * 5, int(seed))
                q = 0.35 + n * 0.6 + (0.2 if r > edge - 0.08 else 0)
                bub = math.hypot((u * 6) % 1 - 0.5, (v * 6) % 1 - 0.5)
                if h2(int(u * 6), int(v * 6), int(seed)) > 0.75 and bub < 0.25 * math.sin(math.pi * ((p + h2(int(u * 6), int(v * 6), 2)) % 1.0)):
                    return _col(R, 1.0), 255
                q, oc = motif_mod(mot, u, v, q, f, N, seed, R)
                return (oc or _col(R, q)), 255
            # plane (water surface)
            q = 0.45 + 0.25 * math.sin(2 * math.pi * (u * 3 + v * 2 - p)) * math.sin(2 * math.pi * (v * 2.5 - u - p))
            if h2(gx, gy, int(seed) + f) > 0.992:
                return _col(R, 1.0), 220
            return _col(R, q), 170
        return m, fn

    if st in ('telegraph_line', 'telegraph_arrow', 'telegraph_cone', 'clock_hand'):
        if st == 'telegraph_cone':
            hw = d * math.sin(math.radians(45))
            x0, x1, z0, z1 = C - hw, C + hw, C - d, C
        else:
            x0, x1, z0, z1 = C - w / 2, C + w / 2, C - d, C
        _flat_up(m, x0, z0, x1, z1)
        if st == 'clock_hand':
            m.box((C - 1.0, C - 0.6, C - 1.0), (C + 1.0, C + 0.6, C + 1.0), 'fx', shade=False, emission=12, glow=True)

        def fn(tx, f):
            if tx.el == 1:
                return _col(R, 0.8), 255
            u, v = _uv_up(tx, x0, z0, x1, z1)   # v=0 far tip (−Z), v=1 at the pivot
            p = P(f)
            pulse = 0.5 + 0.5 * math.sin(2 * math.pi * p)
            fwd = 1 - v                          # 0 at origin → 1 at the far end
            if st == 'telegraph_line':
                ex = min(u, 1 - u)
                if ex < 0.07 or v > 0.97 or v < 0.03:
                    return _col(R, 0.8 + 0.2 * pulse), 255
                chev = ((fwd * 4 - abs(u - 0.5) * 1.6 - p) % 1.0)
                if chev < 0.16:
                    return _col(R, 0.85), 255
                return _col(R, 0.3), 90
            if st == 'telegraph_arrow':
                xx = abs(u - 0.5)
                head = fwd > 0.68 and xx < (1 - fwd) / 0.32 * 0.5
                shaft = fwd <= 0.7 and xx < 0.2
                if not (head or shaft):
                    return T, 0
                edge = (head and xx > (1 - fwd) / 0.32 * 0.5 - 0.06) or (shaft and xx > 0.15) or fwd < 0.03
                if edge:
                    return _col(R, 0.8 + 0.2 * pulse), 255
                if (fwd * 5 - p) % 1.0 < 0.2:
                    return _col(R, 0.95), 255
                return _col(R, 0.4), 140
            if st == 'telegraph_cone':
                x, z = (u - 0.5) * 2 * hw, fwd * d
                rr = math.hypot(x, z) / d
                ang = math.degrees(math.atan2(abs(x), max(1e-6, z)))
                if rr > 1.0 or ang > 45:
                    return T, 0
                if rr > 0.95 or ang > 42.5 * (1 if rr > 0.15 else 0) and ang > 42:
                    return _col(R, 0.8 + 0.2 * pulse), 255
                if abs(rr - (p % 1.0)) < 0.025:
                    return _col(R, 0.95), 255
                if ((rr * 8 - p * 2) % 1.0) < 0.14:
                    return _col(R, 0.6), 200
                return _col(R, 0.3), 90
            # clock hand: tapered pointer with a counterweight ring near the pivot
            xx = abs(u - 0.5) * 2
            width = 0.35 + 0.65 * (1 - fwd) if fwd < 0.85 else (1 - fwd) / 0.15
            if fwd > 0.85:
                width = max(0.0, (1 - fwd) / 0.15) * 1.0
            if xx > width:
                return T, 0
            q = 0.5 + 0.35 * (1 - xx) + (0.15 if (fwd * 12) % 1.0 < 0.1 else 0)
            q, oc = motif_mod(mot, u, v, q, f, N, seed, R)
            return (oc or _col(R, q)), 255
        return m, fn

    # ── vertical plates ───────────────────────────────────────────
    if st in ('rune', 'marker') and not (st == 'marker' and min(w, d) >= 4):
        th = 0.6 if st == 'rune' else 0.1
        if st == 'rune':
            m.box((C - w / 2, C - h / 2, C - th / 2), (C + w / 2, C + h / 2, C + th / 2), 'fx', shade=True, emission=6, glow=True)
        else:
            _plane_xy(m, w, h)

        def fn(tx, f):
            p = P(f)
            if tx.face not in ('north', 'south'):
                return _col(R, 0.25), 255
            u, v = tx.a if hasattr(tx, 'a') else (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            u = (tx.i + 0.5) / tx.w
            s_ = symbol(mot, u, v)
            if st == 'rune':
                ex = min(u, v, 1 - u, 1 - v)
                if ex < 0.07:
                    return _col(R, 0.55 if ex > 0.035 else 0.3), 255
                if s_ < 0.05:
                    q = 0.8 + 0.2 * math.sin(2 * math.pi * (p - v))
                    return _col(R, q), 255
                n = h2(tx.i, tx.j, int(seed))
                return _col(R, 0.12 + n * 0.18), 255
            # marker icon
            if s_ < 0.055:
                q = 0.85 + 0.15 * math.sin(2 * math.pi * p)
                return _col(R, q), 255
            if s_ < 0.09:
                return _col(R, 0.25), 200
            return T, 0
        return m, fn

    # ── crystals (markers with depth, pylons, sigils) ─────────────
    if st in ('crystal', 'marker'):
        cw = min(w, d) * 0.55
        m.cbox((C, C, C), (cw, h * 0.62, cw), 'fx', rot=('y', 45, (C, C, C)), shade=True, emission=12, glow=True)
        m.cbox((C, C + h * 0.36, C), (cw * 0.6, h * 0.16, cw * 0.6), 'fx', rot=('y', 45, (C, C + h * 0.36, C)), shade=True, emission=14, glow=True)
        m.cbox((C, C - h * 0.36, C), (cw * 0.6, h * 0.16, cw * 0.6), 'fx', rot=('y', 45, (C, C - h * 0.36, C)), shade=True, emission=14, glow=True)
        if st == 'crystal':
            m.cbox((C, C - h / 2 + 1.0, C), (w, 2.0, d), 'fx', shade=True, emission=4)
            for k, (dx, dz) in enumerate(((1, 1), (-1, 1), (1, -1), (-1, -1))):
                cx, cz = C + dx * w * 0.3, C + dz * d * 0.3
                m.cbox((cx, C - h / 2 + h * 0.18, cz), (w * 0.16, h * 0.3, d * 0.16), 'fx',
                       rot=('z', -dx * 18, (cx, C - h / 2 + 2, cz)), shade=True, emission=10, glow=True)

        def fn(tx, f):
            p = P(f)
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            if tx.el == 3:   # base slab
                return _col(R, 0.2 + 0.1 * h2(tx.i, tx.j, 3)), 255
            q = 0.45 + 0.35 * (1 - abs(u - 0.5) * 2)
            if tx.face in ('north', 'south', 'east', 'west') and tx.el == 0 and st == 'crystal':
                s_ = symbol(mot, u, v * 0.9 + 0.05)
                if s_ < 0.06:
                    return _col(R, 0.9 + 0.1 * math.sin(2 * math.pi * p)), 255
            q, oc = motif_mod(mot, u, v, q, f, N, seed, R)
            glint = ((u + v * 0.6 - p * 1.4) % 1.0) < 0.08
            return (W if glint else oc or _col(R, q)), 255
        return m, fn

    # ── domes / shells ────────────────────────────────────────────
    if st in ('dome', 'shell', 'sac'):
        n = 6
        for k in range(n):
            if st == 'dome':
                t0, t1 = k / n, (k + 1) / n
                r = math.sqrt(max(0.05, 1 - t0 * t0))
                y0, y1 = C - h / 2 + h * t0, C - h / 2 + h * t1
            else:
                t = ((k + 0.5) / n) * 2 - 1
                r = math.sqrt(max(0.1, 1 - t * t))
                y0, y1 = C - h / 2 + h * k / n, C - h / 2 + h * (k + 1) / n
            m.box((C - w * r / 2, y0, C - d * r * 0.36), (C + w * r / 2, y1, C + d * r * 0.36), 'fx', shade=st != 'dome',
                  emission=10 if spec.d.get('glow') else 0, glow=True)
            m.box((C - w * r * 0.36, y0 - 0.05, C - d * r / 2), (C + w * r * 0.36, y1 + 0.05, C + d * r / 2), 'fx',
                  shade=st != 'dome', emission=10 if spec.d.get('glow') else 0, glow=True)
        if st == 'sac':
            for k in range(5):
                a = 2 * math.pi * k / 5
                m.cbox((C + math.cos(a) * w * 0.2, C - h * 0.05 + (k % 2) * 2, C + math.sin(a) * d * 0.2), (3, 3, 3), 'fx',
                       shade=False, emission=12, glow=True)
            m.cbox((C, C + h / 2 + 1.5, C), (1.0, 3.0, 1.0), 'fx')

        def fn(tx, f):
            p = P(f)
            x, y, z = tx.pos
            u = (math.atan2(z - C, x - C) / (2 * math.pi)) % 1.0
            v = (y - (C - h / 2)) / max(1e-6, h)
            if st == 'sac' and tx.el >= 2 * n:
                if tx.el == 2 * n + 5:
                    return _col(R, 0.6), 255
                q = 0.6 + 0.4 * math.sin(2 * math.pi * (p + tx.el * 0.17))
                return lighten(R[-1], 0.0) if q > 0.8 else _col(R, 0.4 + q * 0.5), 255
            if mot == 'hex_grid':
                hx, hy = u * 18, v * 9 + (int(u * 18) % 2) * 0.5
                edge = min(hx % 1.0, 1 - hx % 1.0, (hy % 1.0), 1 - hy % 1.0)
                if edge < 0.1:
                    return _col(R, 0.85 + 0.15 * math.sin(2 * math.pi * (p - v))), 230
                return _col(R, 0.35), 110
            if mot == 'smoke':
                n_ = fbm(u * 8, v * 4 - p * 2, int(seed))
                if n_ < 0.38:
                    return T, 0
                return _col(R, 0.2 + n_ * 0.7), 200
            if mot == 'silk':
                strand = abs(((u * 10 + v * 3) % 1.0) - 0.5) < 0.08 or abs(((u * 10 - v * 3) % 1.0) - 0.5) < 0.06
                return _col(R, 0.85 if strand else 0.5 + 0.1 * h2(tx.i, tx.j, 5)), (255 if strand else 225)
            q = 0.45 + 0.3 * fbm(u * 6, v * 6, int(seed))
            q, oc = motif_mod(mot, u, v, q, f, N, seed, R)
            if ((u * 3 + v * 2 - p) % 1.0) < 0.05:
                return W, 230
            return (oc or _col(R, q)), 170
        return m, fn

    # ── wings (back plate) ────────────────────────────────────────
    if st == 'wings':
        _plane_xy(m, w, h, faces=('north', 'south'))

        def fn(tx, f):
            p = P(f)
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            x = abs(u - 0.5) * 2
            yy = v
            if x < 0.08:
                return T, 0
            top = 0.12 + 0.25 * (x - 0.08) ** 1.4
            bottom = 0.45 + 0.5 * math.sin(math.pi * clamp((x - 0.08) / 0.92)) ** 0.6
            flap = 0.03 * math.sin(2 * math.pi * p)
            if yy < top + flap or yy > bottom + flap:
                return T, 0
            feather = ((x * 9 + yy * 2) % 1.0)
            if bottom - yy < 0.12 and feather < 0.25:
                return T, 0
            q = 0.5 + 0.35 * (1 - (yy - top) / max(0.05, bottom - top)) + (0.12 if feather < 0.12 else 0)
            q, oc = motif_mod(mot, x, yy, q, f, N, seed, R)
            return (oc or _col(R, q)), 255
        return m, fn

    # ── pillar of light ───────────────────────────────────────────
    if st == 'pillar':
        for ang in (0, 45, 90, 135):
            a = ang if ang <= 45 else ang - 90
            sw = (w, h, 0.1) if ang in (0, 45) else (0.1, h, d)
            m.cbox((C, C, C), sw, 'fx', faces=('north', 'south') if ang in (0, 45) else ('east', 'west'),
                   rot=('y', a, (C, C, C)) if a else None, shade=False, emission=15, glow=True)
        m.cbox((C, C, C), (w * 0.25, h, d * 0.25), 'fx', shade=False, emission=15, glow=True)

        def fn(tx, f):
            p = P(f)
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            xx = abs(u - 0.5) * 2
            fade = clamp(v * 1.3)
            if tx.el == 4:
                return _col(R, 0.95), 255
            q = (1 - xx) * fade
            rise = ((v * 4 + p) % 1.0)
            if rune_bit(int(h2(int(u * 4), int(v * 6 + p * 6), 7) * 8), int(u * 16) % 4, int((v * 24 + p * 24)) % 6) and xx < 0.6:
                q = max(q, 0.8 * fade)
            if q < 0.18 or (rise < 0.15 and q < 0.4):
                return T, 0
            return _col(R, q), 255
        return m, fn

    # ── banner ────────────────────────────────────────────────────
    if st == 'banner':
        m.box((C - 0.8, C - h / 2, C - 0.8), (C + 0.8, C + h / 2, C + 0.8), 'fx', shade=True, emission=0)
        m.box((C - w / 2, C + h / 2 - 2.5, C - 0.6), (C + w / 2, C + h / 2 - 1.2, C + 0.6), 'fx', shade=True, emission=0)
        _plane_xy(m, w * 0.92, h * 0.68, z=C - 1.0, y0=C + h / 2 - 2.5 - h * 0.68, emission=8)

        def fn(tx, f):
            p = P(f)
            if tx.el in (0, 1):
                return _col(R, 0.25 + 0.15 * (tx.face == 'up')), 255
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            if v > 0.86 and abs(((u * 4) % 1.0) - 0.5) * 2 < (v - 0.86) / 0.14:
                return T, 0
            wave = 0.12 * math.sin(2 * math.pi * (u * 1.5 - p))
            s_ = symbol(mot, u, (v - 0.05) * 1.25)
            if s_ < 0.045:
                return _col(R, 1.0), 255
            edge = min(u, 1 - u) < 0.07
            q = 0.45 + wave + (0.25 if edge else 0)
            return _col(R, q), 255
        return m, fn

    # ── props ─────────────────────────────────────────────────────
    if st == 'cocoon':
        n = 7
        for k in range(n):
            t = ((k + 0.5) / n) * 2 - 1
            r = 0.55 + 0.45 * math.sqrt(max(0.0, 1 - t * t))
            y0 = C - h / 2 + h * k / n
            m.box((C - w * r / 2, y0, C - d * r * 0.4), (C + w * r / 2, y0 + h / n, C + d * r * 0.4), 'fx')
            m.box((C - w * r * 0.4, y0 - 0.05, C - d * r / 2), (C + w * r * 0.4, y0 + h / n + 0.05, C + d * r / 2), 'fx')

        def fn(tx, f):
            p = P(f)
            x, y, z = tx.pos
            u = (math.atan2(z - C, x - C) / (2 * math.pi)) % 1.0
            v = (y - (C - h / 2)) / h
            wrap = abs(((u * 2 + v * 6 + 0.05 * math.sin(2 * math.pi * p)) % 1.0) - 0.5) < 0.09
            q = 0.5 + 0.12 * h2(tx.i, tx.j, int(seed)) + (0.3 if wrap else 0) + 0.06 * math.sin(2 * math.pi * (p + v))
            return _col(R, q), 255
        return m, fn

    if st == 'pole':
        m.cbox((C, C, C), (w * 0.4, h, d * 0.4), 'fx')
        m.cbox((C, C - h / 2 + 1, C), (w, 2, d), 'fx')
        m.cbox((C, C + h / 2 - 1, C), (w * 0.7, 2, d * 0.7), 'fx', shade=False, emission=13, glow=True)
        for k in range(4):
            yy = C - h / 2 + 4 + k * (h - 6) / 4
            m.cbox((C + w * 0.32, yy, C), (0.6, 2.2, 1.6) if k % 2 == 0 else (0.6, 2.2, 0.6), 'fx')

        def fn(tx, f):
            if tx.el == 2:
                return _col(R, 1.0), 255
            q = 0.35 + 0.25 * (1 - abs((tx.i + 0.5) / tx.w - 0.5) * 2) + 0.1 * h2(tx.i, tx.j, 4)
            return _col(R, q * (0.9 if tx.el >= 3 else 1.0)), 255
        return m, fn

    if st == 'ice_block':
        m.cbox((C, C, C), (w, h, d), 'fx', shade=True)
        m.cbox((C, C + h / 2 + 0.6, C), (w * 0.8, 1.2, d * 0.8), 'fx', shade=True)
        m.cbox((C + w * 0.4, C + h * 0.2, C - d * 0.4), (2, h * 0.4, 2), 'fx', rot=('z', -20, (C + w * 0.4, C, C - d * 0.4)))

        def fn(tx, f):
            p = P(f)
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            q = 0.5 + 0.25 * (1 - v) + 0.1 * h2(tx.i, tx.j, 9)
            if abs(vnoise(u * 4, v * 6, int(seed)) - 0.5) < 0.03:
                return _col(R, 1.0), 240
            if ((u + v - p) % 1.0) < 0.06:
                return W, 230
            ex = min(u, v, 1 - u, 1 - v)
            return _col(R, q + (0.25 if ex < 0.06 else 0)), (235 if ex < 0.06 else 170)
        return m, fn

    if st == 'pendulum':
        rod_l = h * 0.72
        m.box((C - 0.6, C - rod_l, C - 0.6), (C + 0.6, C, C + 0.6), 'fx')
        bob_r = min(w * 0.5, h - rod_l) * 0.5 + 2
        m.cbox((C, C - rod_l - bob_r * 0.6, C), (bob_r * 2, bob_r * 1.4, d), 'fx')
        m.cbox((C, C - rod_l - bob_r * 0.6, C), (bob_r * 1.4, bob_r * 2, d * 0.9), 'fx')
        m.cbox((C, C, C), (2.6, 2.6, d + 0.4), 'fx')

        def fn(tx, f):
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            if tx.el in (1, 2) and tx.face in ('north', 'south'):
                r = math.hypot(u - 0.5, v - 0.5) * 2
                if abs(r - 0.7) < 0.1:
                    return _col(R, 0.95), 255
                q, oc = motif_mod(mot, u, v, 0.55 - r * 0.2, f, N, seed, R)
                return (oc or _col(R, q)), 255
            return _col(R, 0.45 + 0.2 * (1 - abs(u - 0.5) * 2)), 255
        return m, fn

    if st == 'wall':
        _plane_xy(m, w, h, faces=('north', 'south'), emission=12)

        def fn(tx, f):
            p = P(f)
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            n = fbm(u * 4, v * 4 - p * 2, int(seed))
            edge = min(u, 1 - u) * 6
            if n * min(1.0, edge) < 0.22:
                return T, 0
            q = 0.25 + n * 0.75
            q, oc = motif_mod(mot, u, v, q, f, N, seed, R)
            return (oc or _col(R, q)), 255
        return m, fn

    if st == 'disguise':
        book = mot == 'closed_book'
        if book:
            m.cbox((C, C, C), (w, h * 0.7, d * 0.92), 'fx')                 # pages
            m.cbox((C, C + h * 0.4, C), (w + 0.4, h * 0.2, d), 'fx')       # covers
            m.cbox((C, C - h * 0.4, C), (w + 0.4, h * 0.2, d), 'fx')
            m.cbox((C - w / 2 - 0.1, C, C), (0.4, h, d), 'fx')             # spine
        else:
            m.cbox((C, C, C), (w, h, d), 'fx')

        def fn(tx, f):
            u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
            if book:
                if tx.el == 0:
                    return ((222, 210, 180) if tx.j % 2 == 0 else (196, 182, 150)), 255
                ex = min(u, v, 1 - u, 1 - v)
                q = 0.45 + 0.1 * h2(tx.i, tx.j, 5) + (0.35 if ex < 0.08 else 0)
                return _col(R, q), 255
            # ore-like block: stone mottling + metallic flecks (original pattern)
            n = fbm(u * 3 + tx.el, v * 3 + len(tx.face), int(seed))
            q = 0.25 + n * 0.35
            fl = h3(tx.i // 2, tx.j // 2, len(tx.face), int(seed))
            if fl > 0.86:
                return _col(R, 0.85 + (0.15 if (tx.i + tx.j) % 2 else 0)), 255
            ex = min(u, v, 1 - u, 1 - v)
            return _col(R, q - (0.1 if ex < 0.06 else 0)), 255
        return m, fn

    # unknown style → soft orb plate
    _plane_xy(m, w, h)

    def fn(tx, f):
        u, v = (tx.i + 0.5) / tx.w, (tx.j + 0.5) / tx.h
        r = math.hypot(u - 0.5, v - 0.5) * 2
        if r > 1:
            return T, 0
        return _col(R, 1 - r), 255
    return m, fn
