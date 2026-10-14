"""Colour, hashing and noise helpers shared by every generator module (all original code)."""
from __future__ import annotations

import colorsys
import hashlib
import math
import random

RGBA = tuple  # (r, g, b, a)


def hex2rgb(h: str) -> tuple:
    h = h.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def clamp8(v) -> int:
    v = int(round(v))
    return 0 if v < 0 else 255 if v > 255 else v


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(clamp8(lerp(c1[i], c2[i], t)) for i in range(3))


def lum(c) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def lighten(c, t):
    return mix(c, (255, 255, 255), t)


def darken(c, t):
    return mix(c, (0, 0, 0), t)


def hue_shift(c, deg, sat_mul=1.0, val_mul=1.0):
    h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
    h = (h + deg / 360.0) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, clamp(s * sat_mul), clamp(v * val_mul))
    return (clamp8(r * 255), clamp8(g * 255), clamp8(b * 255))


def saturate(c, mul):
    return hue_shift(c, 0, mul, 1.0)


def stable_seed(*parts) -> int:
    s = '|'.join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha1(s.encode('utf-8')).digest()[:8], 'big')


def rng_for(*parts) -> random.Random:
    return random.Random(stable_seed(*parts))


def h2(x: int, y: int, seed: int = 0) -> float:
    """Deterministic integer hash → [0,1)."""
    n = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0xFFFFFF) / float(0x1000000)


def h3(x: int, y: int, z: int, seed: int = 0) -> float:
    return h2(x * 31 + z * 1013, y * 17 - z * 7, seed)


def vnoise(x: float, y: float, seed: int = 0) -> float:
    """Smooth value noise in [0,1)."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    a = h2(xi, yi, seed)
    b = h2(xi + 1, yi, seed)
    c = h2(xi, yi + 1, seed)
    d = h2(xi + 1, yi + 1, seed)
    return lerp(lerp(a, b, u), lerp(c, d, u), v)


def fbm(x, y, seed=0, octaves=3):
    t, amp, f, norm = 0.0, 1.0, 1.0, 0.0
    for i in range(octaves):
        t += vnoise(x * f, y * f, seed + i * 101) * amp
        norm += amp
        amp *= 0.5
        f *= 2.0
    return t / norm


class Palette:
    """Interprets a YAML palette (dark → light, optional trailing accent colour)."""

    def __init__(self, colors):
        cols = [hex2rgb(c) for c in (colors or ['#202020', '#505050', '#909090', '#d0d0d0'])]
        if len(cols) == 1:
            cols = [darken(cols[0], 0.6), darken(cols[0], 0.3), cols[0], lighten(cols[0], 0.5)]
        if len(cols) == 2:
            cols = [darken(cols[0], 0.3), cols[0], cols[1], lighten(cols[1], 0.5)]
        self.raw = cols
        # main ramp = leading run of (roughly) increasing luminance; the remainder is accent
        ramp = [cols[0]]
        i = 1
        while i < len(cols) and lum(cols[i]) >= lum(ramp[-1]) - 0.04:
            ramp.append(cols[i])
            i += 1
        rest = cols[i:]
        if len(ramp) < 3:
            ramp = sorted(cols, key=lum)
            rest = []
        self.ramp = ramp
        if rest:
            self.accent = max(rest, key=lambda c: sum(c))
        else:
            # brightest saturated colour acts as accent/glow
            best = max(cols, key=lambda c: (max(c) - min(c)) * 0.6 + lum(c) * 120)
            self.accent = best
        self.dark = ramp[0]
        self.light = ramp[-1]

    def ramp_n(self, n=6, base=None):
        src = base or self.ramp
        out = []
        for k in range(n):
            t = k / (n - 1) * (len(src) - 1)
            i = min(int(t), len(src) - 2)
            out.append(mix(src[i], src[i + 1], t - i))
        return out

    def accent_ramp(self, n=6):
        a = self.accent
        base = [darken(a, 0.72), darken(a, 0.45), darken(a, 0.18), a, lighten(a, 0.45), lighten(a, 0.8)]
        return self.ramp_n(n, base)

    def grip_ramp(self, n=5):
        d = self.ramp[0]
        m = self.ramp[min(1, len(self.ramp) - 1)]
        warm = hue_shift(mix(d, (90, 60, 40), 0.35), 0, 0.9)
        base = [darken(d, 0.35), darken(warm, 0.1), mix(warm, m, 0.5), lighten(mix(warm, m, 0.6), 0.18)]
        return self.ramp_n(n, base)
