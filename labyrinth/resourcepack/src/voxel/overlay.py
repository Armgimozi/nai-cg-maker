"""Animated aura overlay layer for legendary / mythic gear (original procedural sprites).

Technique (adapted from the owner's previous pack): the solid model keeps its own texture, and a
second, separately animated texture `<id>_flame.png` is mapped onto a few zero-thickness planes that
cross through the blade.  The planes carry rising flames / sparks / falling frost / swirling motes /
crackling arcs drawn here pixel by pixel, emit light 15 and are unshaded, so the weapon reads like a
looping GIF aura in the hand, in the inventory and on item frames.

Glow texels use alpha 252 — the emissive marker the owner's packs use, so a later core-shader update
can render them fullbright.  (No shader ships with this pack.)
"""
from __future__ import annotations

import math

from PIL import Image

from ..util import h2, lighten, mix

GLOW_ALPHA = 252
SIZE = 32
FRAMES = 16

# effect preset → overlay sprite kind
KIND = {
    'ember_flicker': 'flame', 'sun_glow': 'flame', 'eclipse_corona': 'flame', 'soul_flicker': 'flame',
    'blood_pulse': 'flame',
    'holy_pulse': 'spark', 'star_twinkle': 'spark', 'feather_glint': 'spark', 'crystal_glint': 'spark',
    'prism_cycle': 'spark', 'rune_flow': 'spark', 'aurora_wave': 'spark', 'gear_tick': 'spark',
    'mercury_flow': 'spark',
    'frost_shimmer': 'snow',
    'void_swirl': 'mote', 'shadow_smoke': 'mote', 'ink_bleed': 'mote', 'sculk_pulse': 'mote',
    'tide_ripple': 'bubble', 'venom_drip': 'drip',
    'lightning_arc': 'bolt', 'spark_crackle': 'bolt', 'wind_streak': 'streak',
}


def kind_of(effect):
    return KIND.get(effect, 'spark')


def _blend(px, x, y, c, a=GLOW_ALPHA):
    if 0 <= x < SIZE and 0 <= y < SIZE:
        px[x % SIZE, y] = (int(c[0]), int(c[1]), int(c[2]), a)


def _ramp_at(ramp, t):
    t = max(0.0, min(1.0, t))
    f = t * (len(ramp) - 1)
    i = min(int(f), len(ramp) - 2)
    return mix(ramp[i], ramp[i + 1], f - i)


def _particles(seed, n):
    out = []
    for k in range(n):
        out.append((h2(k, 1, seed), h2(k, 2, seed), h2(k, 3, seed), h2(k, 4, seed)))
    return out


def strip_frames(kind, ramp, seed, frames=FRAMES):
    """→ list of SIZE×SIZE RGBA frames looping seamlessly.  ramp: dark → bright colours of the aura."""
    hot = [lighten(ramp[-1], 0.5), ramp[-1], ramp[len(ramp) * 2 // 3], ramp[len(ramp) // 2], ramp[len(ramp) // 3]]
    out = []
    for f in range(frames):
        img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
        px = img.load()
        T = f / frames
        if kind == 'flame':
            for (a, b, c, d) in _particles(seed, 11):
                speed = 1 + int(c * 2)                     # whole cycles per loop → seamless
                life = (T * speed + a) % 1.0               # 0 = born at the bottom, 1 = gone
                x0 = 3 + b * (SIZE - 6) + math.sin((life * 2 + d) * math.pi * 2) * 1.2
                y0 = (SIZE - 1) - life * (SIZE + 4)
                size = 1.7 * (1 - life) + 0.5
                for yy in range(int(y0 - size * 1.8), int(y0 + size) + 1):
                    for xx in range(int(x0 - size), int(x0 + size) + 1):
                        dx = (xx + 0.5 - x0) / size
                        dy = (yy + 0.5 - y0) / (size * (1.8 if yy < y0 else 1.0))
                        r = dx * dx + dy * dy
                        if r <= 1.0:
                            heat = (1 - r) * (1 - life)
                            _blend(px, xx, yy, _ramp_at(hot[::-1], 0.25 + heat * 0.9))
        elif kind in ('spark', 'snow', 'bubble', 'drip'):
            down = kind in ('snow', 'drip')
            n = 9 if kind != 'drip' else 7
            for (a, b, c, d) in _particles(seed, n):
                speed = 1 + int(c * 2) if kind != 'spark' else 1
                life = (T * speed + a) % 1.0
                x = int(2 + b * (SIZE - 4) + math.sin((life + d) * math.pi * 2) * (2.2 if kind == 'snow' else 1.0))
                y = int(life * (SIZE + 2)) - 1 if down else int((SIZE - 1) - life * (SIZE + 2))
                tw = 0.5 + 0.5 * math.sin((T * 2 + d) * math.pi * 2)
                col = _ramp_at(hot[::-1], 0.35 + 0.6 * tw)
                if kind == 'spark':
                    _blend(px, x, y, lighten(col, 0.3))
                    if tw > 0.45:                          # four-point twinkle
                        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            _blend(px, x + ddx, y + ddy, col)
                    if tw > 0.92:
                        for ddx, ddy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                            _blend(px, x + ddx, y + ddy, _ramp_at(hot[::-1], 0.4))
                elif kind == 'snow':
                    _blend(px, x, y, (255, 255, 255))
                    for ddx, ddy in ((1, 1), (-1, -1), (1, -1), (-1, 1)) if tw > 0.5 else ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        _blend(px, x + ddx, y + ddy, col)
                elif kind == 'bubble':
                    r = 1 + int(c * 1.5)
                    for k in range(12):
                        ang = k / 12 * math.pi * 2
                        _blend(px, int(round(x + math.cos(ang) * r)), int(round(y + math.sin(ang) * r)), col)
                    _blend(px, x - r // 2, y - r // 2, (255, 255, 255))
                else:   # drip: elongated drop falling and stretching
                    ln = 1 + int(life * 3)
                    for k in range(ln):
                        _blend(px, x, y - k, _ramp_at(hot[::-1], 0.4 + 0.15 * k))
                    _blend(px, x, y + 1, lighten(col, 0.4))
        elif kind == 'mote':
            for (a, b, c, d) in _particles(seed, 12):
                life = (T + a) % 1.0
                ang = (life * 1.0 + d) * math.pi * 2
                rad = 3 + b * 10
                x = int(SIZE / 2 + math.cos(ang) * rad)
                y = int((SIZE - 2) - life * (SIZE - 2) + math.sin(ang) * 2)
                fade = math.sin(life * math.pi)
                col = _ramp_at(hot[::-1], 0.2 + 0.7 * fade)
                _blend(px, x, y, col)
                if fade > 0.5:
                    _blend(px, x + 1, y, _ramp_at(hot[::-1], 0.15 + 0.4 * fade))
                    _blend(px, x, y + 1, _ramp_at(hot[::-1], 0.1 + 0.3 * fade))
                if fade > 0.8:
                    _blend(px, x, y, (255, 255, 255))
        elif kind == 'bolt':
            # 2 arcs per frame; each arc lives 2 frames, deterministic jagged path
            for arc in range(2):
                key = (f // 2) * 2 + arc
                x = 4 + h2(key, 9, seed) * (SIZE - 8)
                y = 0
                while y < SIZE:
                    step = 2 + int(h2(key, y, seed) * 3)
                    nx = x + (h2(key, y + 50, seed) - 0.5) * 7
                    nx = max(1, min(SIZE - 2, nx))
                    for s in range(step):
                        t = s / step
                        xx = int(round(x + (nx - x) * t))
                        _blend(px, xx, y + s, (255, 255, 255) if (f % 2 == 0) else hot[1])
                        _blend(px, xx + 1, y + s, hot[2])
                    x = nx
                    y += step
            for (a, b, c, d) in _particles(seed, 6):   # loose sparks
                life = (T * 2 + a) % 1.0
                _blend(px, int(2 + b * (SIZE - 4)), int(life * SIZE), hot[1])
        else:   # streak: horizontal wind streaks drifting upward-diagonal
            for (a, b, c, d) in _particles(seed, 9):
                life = (T + a) % 1.0
                y = int((SIZE - 1) - life * SIZE)
                x0 = int(b * SIZE + life * 10)
                ln = 3 + int(c * 6)
                for k in range(ln):
                    _blend(px, (x0 + k) % SIZE, y, _ramp_at(hot[::-1], 0.3 + 0.6 * k / ln))
        out.append(img)
    return out


def _bounds(elements):
    lo = [99.0, 99.0, 99.0]
    hi = [-99.0, -99.0, -99.0]
    for e in elements:
        for a in range(3):
            lo[a] = min(lo[a], e['from'][a], e['to'][a])
            hi[a] = max(hi[a], e['from'][a], e['to'][a])
    return lo, hi


def _clamp(v):
    return max(-15.9, min(31.9, v))


def add_planes(model_json, tex_ref, mode='blade', emission=15):
    """Append crossed aura planes (texture '#f') to a model JSON in place.

    mode 'blade': upper 70 % of an upright weapon (blade/head + tip), 'bow': around the limbs,
    'helmet': a crest above the head."""
    els = model_json['elements']
    if not els:
        return
    lo, hi = _bounds(els)
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    H = hi[1] - lo[1]
    if mode == 'helmet':
        y0, y1 = hi[1] - 4.0, hi[1] + 6.0
        hw, hd = (hi[0] - lo[0]) / 2 + 1.0, (hi[2] - lo[2]) / 2 + 1.0
    elif mode == 'bow':
        y0, y1 = lo[1] - 0.5, hi[1] + 1.0
        hw, hd = (hi[0] - lo[0]) / 2 + 1.5, max(2.5, (hi[2] - lo[2]) / 2 + 1.5)
    else:
        y0, y1 = lo[1] + H * 0.35, hi[1] + 1.5
        hw = max(2.5, (hi[0] - lo[0]) / 2 + 0.75)
        hd = max(2.5, (hi[2] - lo[2]) / 2 + 0.75)
    y0, y1 = _clamp(y0), _clamp(y1)
    planes = [
        # x–y plane through the centre (seen from the front/back)
        {'from': [_clamp(cx - hw), y0, cz], 'to': [_clamp(cx + hw), y1, cz],
         'faces': {'north': {'uv': [16, 0, 0, 16], 'texture': '#f'}, 'south': {'uv': [0, 0, 16, 16], 'texture': '#f'}}},
        # z–y plane (seen from the sides) — second half of the loop for variety (uv mirrored)
        {'from': [cx, y0, _clamp(cz - hd)], 'to': [cx, y1, _clamp(cz + hd)],
         'faces': {'east': {'uv': [0, 0, 16, 16], 'texture': '#f'}, 'west': {'uv': [16, 0, 0, 16], 'texture': '#f'}}},
    ]
    for p in planes:
        p['shade'] = False
        p['light_emission'] = emission
        els.append(p)
    model_json['textures']['f'] = tex_ref
