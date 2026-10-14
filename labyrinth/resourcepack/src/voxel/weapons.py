"""Original voxel weapon designs (swords, axes, maces, daggers, staves, scepters, censers, bows).

Voxel space: hold point at (0, 0, 0), +Y along the weapon, blade flat in the XY plane (width X,
thickness Z).  1 voxel = 0.5 model units (items.py maps the grid onto the model's hold point).
Rarity escalation (P.lv 0..5): common clean → rare trims+gem → epic organic motif → legendary /
mythic dramatic silhouettes (coiling creatures, wings, crystal growth, floating shards, glow).
"""
from __future__ import annotations

import math
import random

from .core import Grid, bezier, catmull, helix

# ───────────────────────────── design parameters ─────────────────────────────

THEME_KEYS = (
    ('vine', ('moss', 'corridor', 'root', 'grove', 'wayfarer', 'lantern', 'acolyte')),
    ('fungi', ('spore', 'mycel', 'glowcap', 'hypha', 'bloom', 'capsplit')),
    ('abyss', ('abyss', 'void', 'nightshade', 'eclipse', 'viper')),
    ('web', ('skitter', 'silk', 'fang')),
    ('water', ('brine', 'tide', 'eel', 'drowned', 'sluice', 'verdigris')),
    ('forge', ('ember', 'cinder', 'slag', 'anvil', 'bellows', 'forge', 'minewarden', 'miners', 'ore_')),
    ('frost', ('rime', 'frost', 'soulflame')),
    ('crystal', ('crystal', 'geode', 'amethyst', 'prism', 'resonan', 'shardglass', 'twin_light')),
    ('ink', ('ink', 'index', 'lore')),
    ('clock', ('clock', 'regulator', 'doomclock', 'mainspring', 'spring', 'orrery', 'pendulum', 'tesla')),
    ('blood', ('bloodmoon',)),
    ('storm', ('tempest', 'galewing', 'quicksilver')),
    ('holy', ('dawn', 'celestial', 'sanctum', 'seraph', 'aurora', 'embersong')),
)
STYLE_THEME = {'moss': 'vine', 'wood': 'vine', 'silver': 'storm', 'copper': 'water', 'ember': 'forge',
               'dark_iron': 'forge', 'rusted_iron': 'forge', 'frost': 'frost', 'crystal': 'crystal', 'ink': 'ink',
               'clockwork': 'clock', 'abyss': 'abyss', 'void': 'abyss', 'shadow': 'abyss', 'holy': 'holy',
               'gold': 'holy', 'bone': 'web', 'coral': 'water', 'leather': 'vine', 'cloth': 'fungi', 'silk': 'web',
               'obsidian': 'blood', 'steel': 'plain'}
CREATURE = ('viper', 'bloodmoon', 'abyss_sentinel', 'tidecaller', 'eel', 'drowned', 'celestial', 'nightshade')


def theme_of(iid, style):
    for th, keys in THEME_KEYS:
        if any(k in iid for k in keys):
            return th
    return STYLE_THEME.get(style, 'plain')


class P:
    def __init__(self, iid, lv, theme, length, seed, animated):
        self.iid = iid
        self.lv = lv
        self.theme = theme
        self.L = length
        self.rng = random.Random(seed)
        self.anim = animated
        self.creature = lv >= 3 and any(k in iid for k in CREATURE)
        self.glow = lv >= 4


# ───────────────────────────── common parts ─────────────────────────────

def grip(g: Grid, y0, y1, r=1.25, mat='grip'):
    for j in range(y0, y1 + 1):
        for i in range(-2, 3):
            for k in range(-2, 3):
                if i * i + k * k <= r * r + 0.3:
                    w = (j * 2 + i - k) % 4
                    g.put(i, j, k, mat, 0.66 if w == 0 else 0.28 if w == 2 else 0.46)
    for y in (y0, y1):
        for i in range(-1, 2):
            for k in range(-1, 2):
                g.put(i, y, k, 'metal', 0.55, prio=2)


def pommel(g: Grid, y, p: P, r=1.7):
    g.ball((0, y, 0), r, 'metal', vfn=lambda i, j, k, d: 0.35 + 0.35 * (1 - d) + (0.1 if j > y else 0))
    if p.lv >= 1:
        g.crystal((0, y - r + 0.5, 0), (0, -1, 0), 2.6, 0.9, 'metal', prio=2)
    if p.lv >= 2:
        for s in (-1, 1):
            g.gem((0, y, s * (r - 0.2)), 0.8, 'gem', glow=p.glow)
    if p.lv >= 4:
        g.torus((0, y, 0), r + 0.9, 0.5, 'y', 'orn', 0.65)


def crossguard(g: Grid, y, half, p: P, curl=None):
    """Cross-guard in the XY plane at height y (2 voxels tall), tips by rarity."""
    lv = p.lv

    def m(u, v):
        if abs(u) <= half and y <= v <= y + 1:
            return True
        if abs(u) <= 2 and y - 1 <= v <= y + 2:
            return True
        return False

    g.slab(m, (-half - 1, y - 2), (half + 1, y + 3), 'xy', 0, max_half=1, slope=1.0, mat='metal',
           vfn=lambda u, v, w, d: 0.5 + 0.18 * (v - y) / 2 - 0.1 * (abs(u) / max(1, half)) + (0.12 if d == 0 else 0))
    for s in (-1, 1):
        tip = (s * (half + 0.3), y + 0.5, 0)
        if lv >= 1 and (curl if curl is not None else True):
            pts = bezier(tip, (s * (half + 1.5), y + 1.0, 0), (s * (half + 1.8), y + 3.0, 0), (s * (half + 0.6), y + 4.2, 0), 12)
            g.tube(pts, 1.0, 0.6, 'orn' if lv >= 2 else 'metal', vfn=lambda t, d, q: 0.7 - 0.25 * d + 0.1 * t, prio=2)
        else:
            g.ball(tip, 1.2, 'metal', 0.6)
    if lv >= 2:
        g.gem((0, y + 0.5, 1), 1.2 if lv >= 3 else 1.0, 'gem', glow=p.glow)
        g.gem((0, y + 0.5, -1), 1.0, 'gem', glow=p.glow)
        for s in (-1, 1):
            g.box((s * 3, y, -1), (s * 3, y + 1, 1), 'orn', 0.75, prio=2)


def blade(g: Grid, y0, length, hw, p: P, tip=0.2, curve=0.0, wave=0.0, thick=1, fuller=True, edge_mat='edge',
          body_mat='blade', taper=0.12, wave_n=3.0, asym=0.0, rune=None):
    """Tapered blade with diamond cross-section, bevelled edges and a fuller (rune-lit at high rarity)."""
    rune = p.lv >= 3 if rune is None else rune
    top = y0 + length
    for j in range(y0, top + 1):
        t = (j - y0) / max(1, length)
        if t < 1 - tip:
            w = hw * (1 - taper * t)
        else:
            w = hw * (1 - taper * (1 - tip)) * ((1 - t) / tip) ** 0.85
        c = curve * t * t + wave * math.sin(t * math.pi * wave_n) * (1 - t * 0.5)
        lo = c - w - asym * w * 0.4
        hi = c + w
        for i in range(math.floor(lo) - 1, math.ceil(hi) + 2):
            if i < lo - 0.45 or i > hi + 0.45:
                continue
            dx = i - c
            e = min(1.0, abs(dx) / max(w, 0.8))
            dist_edge = min(i - lo, hi - i)
            th = thick if e < 0.55 else max(0, thick - 1)
            if thick >= 2 and e < 0.25:
                th = thick
            groove = fuller and abs(dx) < 0.6 and t < 0.72 and length >= 14 and w >= 2.2
            for k in range(-th, th + 1):
                if dist_edge < 0.9:
                    mat, v = edge_mat, 0.62 + 0.18 * (1 - t) * 0 + (0.12 if k == 0 else 0)
                elif groove:
                    if abs(k) == th and th > 0:
                        continue
                    if rune and (j % 5) in (1, 2, 3):
                        g.put(i, j, k, 'glow', 0.75, glow=True, prio=3)
                        continue
                    mat, v = 'fuller', 0.3
                else:
                    mat, v = body_mat, 0.42 + 0.22 * (1 - e) + (0.05 if k > 0 else -0.03 if k < 0 else 0)
                g.put(i, j, k, mat, v)
    return top


def shaft(g: Grid, y0, y1, r=1.25, mat='wood', bands=()):
    for j in range(y0, y1 + 1):
        for i in range(-2, 3):
            for k in range(-2, 3):
                if i * i + k * k <= r * r + 0.3:
                    g.put(i, j, k, mat, 0.45 + (0.12 if (j + i * 3) % 7 == 0 else 0) + 0.06 * (i - k) / 2)
    for y in bands:
        for i in range(-2, 3):
            for k in range(-2, 3):
                if i * i + k * k <= 2.3:
                    g.put(i, y, k, 'metal', 0.6, prio=2)


def float_shards(g: Grid, pts, p: P, size=3.0, r=0.9, mat='crystal'):
    for (x, y, z) in pts:
        g.crystal((x, y - size / 2, z), (0, 1, 0), size, r, mat, glow=True, prio=4, tip=0.5)
        g.crystal((x, y - size / 2 + 0.3, z), (0, -1, 0), size * 0.45, r * 0.9, mat, glow=True, prio=4, tip=0.9)


def halo(g: Grid, c, R, axis='y', p=None):
    g.torus(c, R, 0.5, axis, 'glow', 0.8, glow=True, prio=4)
    n = 8
    for k in range(n):
        a = 2 * math.pi * k / n
        if axis == 'y':
            q = (c[0] + math.cos(a) * R, c[1], c[2] + math.sin(a) * R)
        else:
            q = (c[0] + math.cos(a) * R, c[1] + math.sin(a) * R, c[2])
        g.gem(q, 1.0, 'glow', glow=True)


# ───────────────────────────── motifs ─────────────────────────────

def serpent(g: Grid, y0, y1, R, turns, p: P, phase=0.0, rmax=1.7, zs=1.0, head=True):
    rmax = rmax * 1.3
    """Coiling creature (serpent / dragon / eel) around the Y axis, head at the top end."""
    pts = helix(y0, y1, R, turns, phase, zs=zs)
    rr = random.Random(p.rng.random())

    def vfn(t, d, q):
        ax = math.hypot(q[0], q[2] / max(zs, 0.3))
        band = (t * 44) % 2 < 1
        if ax < R - 0.4 and d > 0.35:
            return ('belly', 0.45 + (0.15 if band else 0))
        return 0.3 + 0.32 * (1 - d) + (0.14 if band else 0)

    seen = g.tube(pts, 0.7, rmax, 'scale', step=0.28,
                  vfn=lambda t, d, q: (lambda r: r if not isinstance(r, tuple) else None)(vfn(t, d, q)))
    for q, (t, d) in seen.items():
        r = vfn(t, d, q)
        if isinstance(r, tuple):
            g.put(q[0], q[1], q[2], r[0], r[1])
    # dorsal fins
    n = len(pts)
    for s in range(4, n - 6, 5):
        x, y, z = pts[s]
        ln = math.hypot(x, z) or 1
        ox, oz = x / ln, z / ln
        t = s / n
        rad = 0.7 + (rmax - 0.7) * t
        a = (x + ox * rad, y, z + oz * rad)
        b = (x + ox * (rad + 1.6), y - 0.8, z + oz * (rad + 1.6))
        g.tube([a, b], 0.6, 0.45, 'fin', vfn=lambda t_, d_, q_: 0.55 + 0.25 * t_, prio=2)
    if not head:
        return
    # head along the final tangent
    (x1, y1_, z1), (x0, y0_, z0) = pts[-1], pts[-4]
    tx, ty, tz = x1 - x0, y1_ - y0_, z1 - z0
    tl = math.sqrt(tx * tx + ty * ty + tz * tz) or 1
    tx, ty, tz = tx / tl, ty / tl + 0.35, tz / tl
    tl = math.sqrt(tx * tx + ty * ty + tz * tz)
    tx, ty, tz = tx / tl, ty / tl, tz / tl
    h0 = (x1, y1_, z1)
    snout = (x1 + tx * 4.2, y1_ + ty * 4.2, z1 + tz * 4.2)
    g.tube([h0, snout], rmax + 0.4, 0.9, 'scale', vfn=lambda t, d, q: 0.42 + 0.3 * (1 - d) + 0.1 * t, prio=3)
    jaw0 = (x1, y1_ - 1.2, z1)
    jaw1 = (x1 + tx * 3.6, y1_ + ty * 3.6 - 1.8, z1 + tz * 3.6)
    g.tube([jaw0, jaw1], rmax * 0.7, 0.6, 'belly', 0.5, prio=3)
    # horns sweeping back
    for s in (-1, 1):
        side = (-tz * s, 0, tx * s)
        hb = (x1 + side[0] * 1.2, y1_ + 1.2, z1 + side[2] * 1.2)
        hm = (hb[0] - tx * 1.5 + side[0] * 0.8, hb[1] + 1.6, hb[2] - tz * 1.5 + side[2] * 0.8)
        he = (hb[0] - tx * 3.6 + side[0] * 1.2, hb[1] + 2.0, hb[2] - tz * 3.6 + side[2] * 1.2)
        g.tube(catmull([hb, hm, he], 6), 0.75, 0.45, 'bone', vfn=lambda t, d, q: 0.4 + 0.45 * t, prio=4)
        eye = (x1 + tx * 1.4 + side[0] * (rmax + 0.1), y1_ + 0.6, z1 + tz * 1.4 + side[2] * (rmax + 0.1))
        g.put(round(eye[0]), round(eye[1]), round(eye[2]), 'eye', 0.9, glow=True, prio=5)
    if p.lv >= 5:
        # breath wisps
        b0 = (snout[0] + tx, snout[1] + ty, snout[2] + tz)
        g.tube([b0, (b0[0] + tx * 2 + 0.8, b0[1] + 2.2, b0[2] + tz * 2)], 0.6, 0.5, 'glow', 0.8, glow=True, prio=4)


def vines(g: Grid, y0, y1, R, p: P, n=2, leaves=True, buds=True, zs=1.0, r=0.6):
    for v in range(n):
        ph = p.rng.random() * 6.28
        turns = (y1 - y0) / 11.0
        pts = helix(y0, y1, R, turns * (1 if v % 2 == 0 else -1), ph,
                    rfn=lambda t, v=v: 1.0 + 0.22 * math.sin(t * 17 + v), zs=zs)
        g.tube(pts, r + 0.25, r, 'vine', vfn=lambda t, d, q: 0.35 + 0.35 * (1 - d) + 0.1 * math.sin(t * 40), prio=2)
        for s in range(3, len(pts) - 2, 4):
            x, y, z = pts[s]
            ln = math.hypot(x, z) or 1
            ox, oz = x / ln, z / ln
            if leaves and s % 8 == 3:
                c = (x + ox * 1.4, y + 0.6, z + oz * 1.4)
                g.ball(c, 1.25, 'leaf', sq=(1.2, 0.65, 1.2) if abs(ox) > abs(oz) else (0.8, 0.65, 1.3),
                       vfn=lambda i, j, k, d: 0.35 + 0.4 * (1 - d) + (0.15 if j > c[1] else 0), prio=2)
            elif buds and s % 8 == 7 and p.lv >= 3:
                g.gem((round(x + ox * 1.3), round(y), round(z + oz * 1.3)), 0.6, 'glow', glow=True)


def tendrils(g: Grid, base, p: P, n=5, length=10, spread=6.0, up=1.0, r0=1.3, mat='tendril'):
    rr = p.rng
    for k in range(n):
        a = 2 * math.pi * k / n + rr.random() * 0.6
        dx, dz = math.cos(a), math.sin(a) * 0.55
        pts = [base]
        x, y, z = base
        for s in range(1, 5):
            f = s / 4
            x = base[0] + dx * spread * f + math.sin(f * 5 + k) * 1.4
            z = base[2] + dz * spread * f * 0.6
            y = base[1] + up * length * f + math.cos(f * 4 + k * 1.7) * 1.2
            pts.append((x, y, z))
        g.tube(catmull(pts, 6), r0, 0.45, mat, vfn=lambda t, d, q: 0.3 + 0.45 * (1 - d) * (1 - t * 0.5) + 0.25 * t,
               prio=2)
        g.put(round(pts[-1][0]), round(pts[-1][1]), round(pts[-1][2]), 'glow', 0.9, glow=True, prio=4)


def wing(g: Grid, root, side, p: P, span=9.0, rise=12.0, n=6, mat='feather', droop=0.0):
    """Feathered wing in the XY plane: a leading arm arcs up/out; feathers hang from it toward the tip."""
    rx, ry, rz = root
    arm = bezier(root, (rx + side * span * 0.35, ry + rise * 0.55, rz), (rx + side * span * 0.8, ry + rise * 0.95, rz),
                 (rx + side * span, ry + rise, rz), 20)
    g.tube(arm, 1.1, 0.6, 'orn', vfn=lambda t, d, q: 0.55 + 0.25 * (1 - d), prio=3)
    for f in range(n):
        t = 0.18 + 0.82 * f / max(1, n - 1)
        a = arm[min(len(arm) - 1, int(t * (len(arm) - 1)))]
        ln = 3.0 + 6.5 * t
        ang = math.radians(-90 + 55 * t - droop)   # pointing down-out, flaring outward toward tip
        tip = (a[0] + side * math.cos(ang) * ln * 0.55 + side * 0.8 * t, a[1] + math.sin(ang) * ln, rz)
        mid = ((a[0] + tip[0]) / 2 + side * 0.6, (a[1] + tip[1]) / 2, rz)
        alt = 0.08 if f % 2 == 0 else -0.06
        g.tube(catmull([a, mid, tip], 5), 1.15, 0.5, mat, sq=(1, 1, 0.7),
               vfn=lambda tt, d, q, alt=alt: 0.38 + 0.4 * tt + alt + 0.12 * (1 - d), prio=2)
        if p.lv >= 4 and f == n - 1:
            g.put(round(tip[0]), round(tip[1]), rz, 'glow', 0.9, glow=True, prio=4)


def crystal_cluster(g: Grid, base, p: P, n=4, size=4.0, r=1.1, up=(0, 1, 0), spread=0.7, glow=False):
    rr = p.rng
    g.crystal(base, up, size * 1.25, r * 1.15, 'crystal', glow=glow, prio=3)
    for k in range(n - 1):
        a = 2 * math.pi * k / (n - 1) + rr.random()
        d = (up[0] + math.cos(a) * spread, up[1] + 0.2, up[2] + math.sin(a) * spread * 0.7)
        g.crystal((base[0] + math.cos(a) * 0.8, base[1], base[2] + math.sin(a) * 0.5), d,
                  size * (0.55 + rr.random() * 0.35), r * 0.8, 'crystal', glow=glow, prio=3)


def gear(g: Grid, c, R, p: P, teeth=8, plane='xy', mat='orn', hole=True, glow=False):
    def m(u, v):
        x, y = u - c[0], v - (c[1] if plane == 'xy' else c[2])
        d = math.hypot(x, y)
        a = math.atan2(y, x)
        if hole and d < R * 0.32:
            return False
        if d <= R - 0.8:
            if R >= 4 and R * 0.38 < d < R - 1.6:
                return any(abs(((a - s * math.pi / 2) + math.pi) % (2 * math.pi) - math.pi) < 0.3 for s in range(4))
            return True
        return d <= R + 0.6 and ((a * teeth / (2 * math.pi)) % 1.0) < 0.5
    R2 = int(R + 2)
    if plane == 'xy':
        g.slab(m, (int(c[0]) - R2, int(c[1]) - R2), (int(c[0]) + R2, int(c[1]) + R2), 'xy', int(c[2]), max_half=0,
               mat=mat, glow=glow, prio=3, vfn=lambda u, v, w, d: 0.45 + 0.25 * min(1, d / 2))
    else:
        g.slab(lambda u, v: m(u, v), (int(c[0]) - R2, int(c[2]) - R2), (int(c[0]) + R2, int(c[2]) + R2), 'xz',
               int(c[1]), max_half=0, mat=mat, glow=glow, prio=3, vfn=lambda u, v, w, d: 0.45 + 0.25 * min(1, d / 2))


def flames(g: Grid, y0, y1, xfn, p: P, n=6):
    """Flame tongues licking up from both blade edges; xfn(y) → half width at y."""
    for s in (-1, 1):
        for k in range(n):
            y = y0 + (y1 - y0) * (k + 0.5 * (s > 0)) / n
            x = s * (xfn(y) + 0.3)
            h = 3.5 + (k % 3) * 1.2
            pts = catmull([(x, y, 0), (x + s * 1.6, y + h * 0.4, 0), (x + s * 0.6, y + h * 0.8, 0),
                           (x + s * 1.2, y + h, 0)], 5)
            g.tube(pts, 1.1, 0.5, 'flame', glow=True, vfn=lambda t, d, q: 0.85 - 0.5 * t + 0.15 * (1 - d), prio=2)


def fungi(g: Grid, c, p: P, size=2.2, up=(0, 1, 0)):
    x, y, z = c
    top = (x + up[0] * 1.8, y + up[1] * 1.8, z + up[2] * 1.8)
    g.tube([c, top], 0.7, 0.6, 'belly', 0.55, prio=2)
    g.ball(top, size, 'fungus', sq=(1, 0.5, 1), prio=3,
           vfn=lambda i, j, k, d: (0.85 if (i * 7 + k * 3 + j) % 5 == 0 and d > 0.6 else 0.42 + 0.3 * (1 - d)))
    if p.lv >= 3:
        g.put(round(top[0]), round(top[1] + size * 0.5 + 0.6), round(top[2]), 'glow', 0.9, glow=True, prio=4)


def shell(g: Grid, c, p: P, R=2.6, turns=2.2, plane='xy'):
    pts = []
    n = 36
    for k in range(n + 1):
        t = k / n
        a = turns * 2 * math.pi * t
        r = R * (1 - 0.82 * t)
        if plane == 'xy':
            pts.append((c[0] + math.cos(a) * r, c[1] + math.sin(a) * r, c[2] + t * 1.2))
        else:
            pts.append((c[0] + t * 1.2, c[1] + math.sin(a) * r, c[2] + math.cos(a) * r))
    g.tube(pts, 1.2, 0.45, 'shell', vfn=lambda t, d, q: 0.35 + 0.45 * (1 - d) + (0.12 if int(t * 18) % 2 else 0), prio=3)


def ribbon(g: Grid, y0, y1, R, p: P, turns=2.0, phase=0.0, mat='paper'):
    pts = helix(y0, y1, R, turns, phase, zs=0.9)
    g.tube(pts, 0.55, 0.55, mat, sq=(1, 2.6, 1), step=0.25,
           vfn=lambda t, d, q: 0.72 if int(t * 60) % 3 else 0.35, prio=3)
    # ink glyph dots on the ribbon
    for s in range(2, len(pts), 6):
        x, y, z = pts[s]
        g.put(round(x), round(y), round(z), 'glow' if p.glow else 'ink', 0.8, glow=p.glow, prio=4)


def drips(g: Grid, pts, p: P, mat='ink'):
    for (x, y, z) in pts:
        ln = 2 + int(abs(x * 13 + y * 7) % 3)
        g.tube([(x, y, z), (x, y - ln, z)], 0.65, 0.55, mat, 0.4, prio=2)
        g.ball((x, y - ln - 0.6, z), 0.85, 'glow' if p.glow else mat, 0.8, glow=p.glow, prio=3)


def web(g: Grid, c, R, p: P, z=0):
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.3
        g.tube([(c[0], c[1], z), (c[0] + math.cos(a) * R, c[1] + math.sin(a) * R, z)], 0.5, 0.5, 'string', 0.8, prio=1)
    for rr in (R * 0.45, R * 0.8):
        pts = [(c[0] + math.cos(2 * math.pi * k / 6 + 0.3) * rr, c[1] + math.sin(2 * math.pi * k / 6 + 0.3) * rr, z)
               for k in range(7)]
        g.tube(pts, 0.5, 0.5, 'string', 0.6, prio=1)


def zigzag(g: Grid, a, b, p: P, n=5, amp=1.8):
    pts = [a]
    for k in range(1, n):
        t = k / n
        q = (a[0] + (b[0] - a[0]) * t + (amp if k % 2 else -amp), a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
        pts.append(q)
    pts.append(b)
    g.tube(pts, 0.6, 0.5, 'glow', 0.9, glow=True, step=0.25, prio=4)


def ice_spikes(g: Grid, pts, p: P, size=3.5):
    for (x, y, z, dx, dy) in pts:
        g.crystal((x, y, z), (dx, dy, 0), size, 0.9, 'ice', glow=p.glow and p.lv >= 4, prio=3)


# ───────────────────────────── theme dressing ─────────────────────────────

def dress_blade(g: Grid, p: P, A):
    """Theme motifs on bladed weapons. A: y0/y1 blade span, hw, guard y/half, top."""
    th, lv = p.theme, p.lv
    y0, y1, hw, gy, gh = A['y0'], A['y1'], A['hw'], A['gy'], A['gh']
    span = y1 - y0
    if lv < 3:
        if lv == 2 and th in ('vine', 'fungi', 'water'):
            vines(g, gy - 1, gy + 5, hw + 1.2, p, n=1, leaves=True, buds=False)
        return
    big = lv >= 4
    if th == 'vine':
        vines(g, gy, y0 + int(span * (0.75 if big else 0.45)), hw + 1.3, p, n=2 if big else 1)
        if big:
            for s in (-1, 1):
                fungi(g, (s * (gh + 1), gy + 2, 0), p, 1.6)
    elif th == 'fungi':
        for k, (x, y) in enumerate(((-gh, gy + 2), (gh, gy + 1), (-hw - 1, y0 + 6), (hw + 1, y0 + 10))):
            fungi(g, (x, y, 0), p, 2.0 if k < 2 else 1.6, up=(0.4 if x > 0 else -0.4, 1, 0))
        if big:
            vines(g, gy, y0 + int(span * 0.6), hw + 1.2, p, n=1, leaves=False)
    elif th == 'web':
        for s in (-1, 1):
            pts = bezier((s * gh, gy, 0), (s * (gh + 2), gy - 2, 0), (s * (gh + 2), gy - 5, 0), (s * (gh - 1), gy - 7, 0), 10)
            g.tube(pts, 1.1, 0.4, 'bone', vfn=lambda t, d, q: 0.45 + 0.45 * t, prio=3)
        if big:
            web(g, (0, y0 + 4, 0), hw + 4, p, z=0)
    elif th == 'water':
        for s in (-1, 1):
            shell(g, (s * (gh + 1), gy + 2, 0.5), p, 2.3)
        if big or p.creature:
            serpent(g, gy - 1, y0 + int(span * 0.72), hw + 1.6, 1.6, p, phase=0.6, rmax=1.5)
        else:
            vines(g, gy, y0 + int(span * 0.4), hw + 1.2, p, n=1, leaves=False)
    elif th == 'forge':
        # glowing cracks across the blade + spikes on the guard
        for s in (-1, 1):
            g.crystal((s * gh, gy + 1, 0), (s, 0.6, 0), 3.5, 0.9, 'metal', prio=3)
        rr = p.rng
        for k in range(5 if big else 3):
            yy = y0 + 3 + rr.randint(0, max(1, span - 8))
            xx = rr.randint(-int(hw) + 1, int(hw) - 1)
            pts = [(xx, yy, 1.2), (xx + rr.choice((-1, 1)), yy + 2, 1.2), (xx, yy + 4, 1.2)]
            g.tube(pts, 0.5, 0.5, 'glow', 0.8, glow=True, prio=4)
            g.tube([(q[0], q[1], -1.2) for q in pts], 0.5, 0.5, 'glow', 0.8, glow=True, prio=4)
        if big:
            flames(g, y0 + 2, y1 - 6, lambda y: A['wfn'](y), p, n=4)
    elif th == 'frost':
        ice_spikes(g, [(s * gh, gy + 1, 0, s, 0.9) for s in (-1, 1)] + [(0, gy - 1, 0, 0, -1)], p, 3.2)
        if big:
            for k in range(4):
                yy = y0 + 4 + k * (span - 8) // 4
                s = -1 if k % 2 else 1
                ice_spikes(g, [(s * (A['wfn'](yy) - 0.5), yy, 0, s, 1.1)], p, 3.0)
    elif th == 'crystal':
        for s in (-1, 1):
            crystal_cluster(g, (s * (gh - 1), gy + 1, 0), p, 3, 3.2, 0.9, up=(s * 0.6, 1, 0), glow=big)
        if big:
            for k in range(3):
                yy = y0 + 3 + k * (span // 4)
                s = 1 if k % 2 else -1
                g.crystal((s * A['wfn'](yy), yy, 0), (s, 1.2, 0), 3.4, 0.9, 'crystal', glow=True, prio=3)
    elif th == 'ink':
        ribbon(g, gy - 2, y0 + int(span * (0.7 if big else 0.4)), hw + 1.4, p, turns=1.6 if big else 1.0)
        for s in (-1, 1):
            q = bezier((s * gh, gy + 1, 0), (s * (gh + 2), gy + 3, 0), (s * (gh + 3), gy + 6, 0), (s * (gh + 2), gy + 9, 0), 12)
            g.tube(q, 1.0, 0.45, 'feather', vfn=lambda t, d, q_: 0.5 + 0.35 * t, prio=3)
        if big:
            drips(g, [(-hw, y0 + 8, 0), (hw, y0 + 13, 0), (-hw, y0 + 18, 0)], p)
    elif th == 'clock':
        gear(g, (0, gy + 0.5, 2), 3.6 if big else 3.0, p, 8, mat='orn')
        if big:
            gear(g, (-gh - 1, gy + 3, 0), 2.6, p, 6, mat='metal')
            gear(g, (gh + 1, gy - 1, 0), 2.2, p, 6, mat='metal')
            pts = helix(y0, y0 + int(span * 0.55), hw + 1.2, 3.0, 0.0, zs=0.9)
            g.tube(pts, 0.5, 0.5, 'orn', 0.7, prio=2)
    elif th == 'abyss':
        tendrils(g, (0, gy, 0), p, n=4 if big else 3, length=6, spread=gh + 2, up=-0.5 if not big else 0.8)
        if big or p.creature:
            serpent(g, gy - 2, y0 + int(span * 0.78), hw + 1.6, 1.8, p, phase=2.0, rmax=1.5)
        g.ball((0, gy + 0.5, 1.6), 1.3, 'eye', 0.8, glow=True, prio=5)
    elif th == 'holy':
        for s in (-1, 1):
            wing(g, (s * (gh - 1), gy + 1, 0), s, p, span=7 + 3 * big, rise=10 + 6 * big, n=5 + 2 * big)
    elif th == 'storm':
        for s in (-1, 1):
            wing(g, (s * (gh - 1), gy + 1, 0), s, p, span=6 + 2 * big, rise=8 + 4 * big, n=5)
        if big:
            zigzag(g, (hw + 3, y0 + 4, 0), (hw + 2, y1 - 6, 0), p)
    elif th == 'blood':
        serpent(g, gy - 2, y0 + int(span * 0.8), hw + 1.8, 1.7, p, rmax=1.6)
    if p.creature and th not in ('water', 'abyss', 'blood'):
        serpent(g, gy - 2, y0 + int(span * 0.7), hw + 1.8, 1.6, p, phase=1.2, rmax=1.5)
    if big:
        side = [(-(hw + 5), y0 + span * 0.55, 0), (hw + 5, y0 + span * 0.35, 0)]
        if lv >= 5:
            side.append((hw + 4, y0 + span * 0.8, 0))
            side.append((-(hw + 4), y0 + span * 0.2, 0))
        float_shards(g, side, p, 3.2, 0.85, 'crystal' if th not in ('frost',) else 'ice')
    if lv >= 5:
        for k in range(5):
            a = 2 * math.pi * k / 5 + 0.3
            g.gem((math.cos(a) * (hw + 6), y1 + 2 - k * 1.5, math.sin(a) * 2), 1.0, 'glow', glow=True)


# ───────────────────────────── weapon templates ─────────────────────────────

def _sword(g, p: P, hw, length, grip_len, guard_half, two=False, **bk):
    L = p.L
    length = int(length * L)
    gl = grip_len
    grip(g, -gl // 2, gl // 2)
    pommel(g, -gl // 2 - 2, p, 1.9 if two else 1.6)
    gy = gl // 2 + 1
    crossguard(g, gy, guard_half, p)
    y0 = gy + 2
    blade(g, y0, length, hw, p, **bk)
    tip = bk.get('tip', 0.2)
    taper = bk.get('taper', 0.12)
    wfn = lambda y: hw * (1 - taper * min(1 - tip, (y - y0) / length)) * (
        1 if (y - y0) / length < 1 - tip else max(0.0, (1 - (y - y0) / length) / tip))
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': hw, 'gy': gy, 'gh': guard_half, 'wfn': wfn})


def longsword(g, p):
    _sword(g, p, 3.0 if p.lv < 4 else 3.4, 30, 9, 7 + (p.lv >= 3), tip=0.2)


def broadsword(g, p):
    _sword(g, p, 4.2, 26, 9, 8 + (p.lv >= 3), tip=0.16, taper=0.05, thick=1)


def greatsword(g, p):
    _sword(g, p, 4.6, 40, 15, 10 + (p.lv >= 3), two=True, tip=0.15, thick=2, taper=0.08)


def dagger(g, p):
    _sword(g, p, 2.2, 17, 7, 4 + (p.lv >= 3), tip=0.32, fuller=p.lv >= 2, taper=0.15)


def kris(g, p):
    _sword(g, p, 2.3, 20, 7, 4 + (p.lv >= 3), tip=0.28, wave=1.1, wave_n=5.0, fuller=False, taper=0.25)


def fang_blade(g, p):
    _sword(g, p, 2.6, 19, 7, 3 + (p.lv >= 3), tip=0.45, curve=4.0, fuller=False, taper=0.3, edge_mat='bone'
           if p.theme == 'web' else 'edge')
    if p.lv >= 2:  # serrations along the back edge
        for j in range(8, 20, 3):
            t = (j - 6) / 19
            x = -2.6 * (1 - 0.3 * t) + 4.0 * t * t - 0.6
            g.put(round(x) - 1, j, 0, 'edge', 0.8, prio=2)


def cleaver(g, p):
    L = p.L
    gl = 14
    grip(g, -gl // 2, gl // 2)
    pommel(g, -gl // 2 - 2, p, 1.8)
    gy = gl // 2 + 1
    length = int(30 * L)
    y0 = gy + 1
    # broad asymmetric slab: straight back on −x, bellied edge on +x, chisel tip
    def m(u, v):
        t = (v - y0) / length
        if t < 0 or t > 1:
            return False
        back = -2.5
        edge = 3.5 + 3.2 * math.sin(min(1.0, t * 1.15) * math.pi * 0.85)
        top = 1 - 0.25 * max(0.0, (u - back) / (edge - back + 1e-6))
        if t > top:
            return False
        if p.lv >= 2 and 0.15 < t < 0.3 and abs(u - 1.5) < 1.0:
            return False  # hanging hole
        return back <= u <= edge
    g.slab(m, (-4, y0), (8, y0 + length), 'xy', 0, max_half=1, slope=0.5, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.7) if d == 0 and u > 0 else 0.4 + 0.08 * min(d, 3) + 0.04 * w)
    # spine
    g.box((-3, y0, -1), (-3, y0 + int(length * 0.82), 1), 'metal', 0.6, prio=2)
    g.box((-2, gy - 1, -1), (2, gy, 1), 'metal', 0.5)
    hw = 4
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': hw, 'gy': gy, 'gh': 3, 'wfn': lambda y: 5.0})


def great_axe(g, p):
    L = p.L
    top = int(32 * L)
    shaft(g, -16, top, 1.25, 'wood', bands=(-6, 6, top - 14))
    pommel(g, -18, p, 1.6)
    grip(g, -5, 5)
    hy = top - 7
    double = p.lv >= 3 or 'reaver' in p.iid or 'geode' in p.iid

    def blade_mask(s):
        def m(u, v):
            x = u * s
            if x < 1:
                return False
            dy = v - hy
            # crescent: outer arc radius 10 centred inward, inner cut
            ox = x - 1
            reach = 12.5 if p.lv >= 4 else 10.0
            hh = 3.5 + ox * 0.95
            if ox > reach:
                return False
            if abs(dy) > hh:
                return False
            cut = (ox - reach - 4.5) ** 2 + dy * dy < 6.0 ** 2 and ox > reach - 1.5
            if 'reaver' in p.iid or p.theme in ('holy', 'storm', 'blood'):
                # wing-shaped: scalloped feather notches on the lower edge
                if dy < -hh + 1.6 and int(ox) % 3 == 2:
                    return False
            return not cut
        return m

    for s in ((-1, 1) if double else (1,)):
        g.slab(blade_mask(s), (-16, hy - 16), (16, hy + 16), 'xy', 0, max_half=1, slope=0.34, mat='blade',
               vfn=lambda u, v, w, d: ('edge', 0.72 + 0.1 * (w == 0)) if d <= 0 and abs(u) > 4 else
               0.38 + 0.07 * min(d, 4) + 0.03 * w)
        # inlay line
        if p.lv >= 2:
            for v in range(hy - 3, hy + 4):
                g.put(s * 3, v, 1, 'orn', 0.7, prio=2)
                g.put(s * 3, v, -1, 'orn', 0.7, prio=2)
    if not double:
        g.crystal((-1, hy, 0), (-1, -0.3, 0), 5.0, 1.2, 'metal', prio=2)  # back spike
    g.crystal((0, top, 0), (0, 1, 0), 6.0, 1.3, 'metal', prio=2)  # top spike
    g.ball((0, hy, 0), 2.2, 'metal', 0.55, prio=2)
    if p.lv >= 2:
        g.gem((0, hy, 2), 1.2, 'gem', glow=p.glow)
        g.gem((0, hy, -2), 1.2, 'gem', glow=p.glow)
    dress_shaft(g, p, -4, hy - 3, hy, top)


def mace(g, p):
    L = p.L
    top = int(16 * L)
    shaft(g, -6, top, 1.25, 'metal' if p.lv >= 2 else 'wood', bands=(top - 2,))
    grip(g, -6, 4)
    pommel(g, -8, p, 1.5)
    hy = top + 4
    g.ball((0, hy, 0), 3.6, 'metal', vfn=lambda i, j, k, d: 0.32 + 0.4 * (1 - d) + 0.1 * (j > hy))
    # flanges
    for k in range(6):
        a = 2 * math.pi * k / 6
        dx, dz = math.cos(a), math.sin(a)
        def m(u, v, dx=dx):
            return abs(v - hy) <= 4 - u * 0.4 and 0 <= u <= 5
        for u in range(0, 6):
            for v in range(hy - 5, hy + 6):
                if m(u, v):
                    g.put(round(dx * (u + 1.5)), v, round(dz * (u + 1.5)), 'blade' if p.theme != 'clock' else 'orn',
                          0.45 + 0.08 * u, prio=2)
    g.crystal((0, hy + 3, 0), (0, 1, 0), 4.0, 1.2, 'metal', prio=2)
    if p.lv >= 2:
        g.torus((0, hy - 4, 0), 2.6, 0.6, 'y', 'orn', 0.7)
    if p.theme == 'clock':
        gear(g, (0, hy, 0), 4.2, p, 10, 'xy', 'orn')
    if p.theme == 'water':
        for s in (-1, 1):
            shell(g, (s * 5, hy - 5, 0), p, 2.0)
    if p.lv >= 3:
        dress_shaft(g, p, -4, hy - 6, hy, hy + 5)


def dress_shaft(g, p: P, y0, y1, hy, top):
    """Motifs for hafted weapons (axes, staves): coils/vines/crystals climbing the shaft + head extras."""
    th, lv = p.theme, p.lv
    if lv < 3:
        return
    big = lv >= 4
    if th in ('vine', 'fungi'):
        vines(g, y0, y1, 1.8, p, n=2 if big else 1)
        if th == 'fungi':
            fungi(g, (-2, y0 + 6, 0), p, 1.8, up=(-0.5, 1, 0))
            fungi(g, (2, y0 + 12, 0), p, 1.6, up=(0.5, 1, 0))
    elif th == 'crystal':
        # crystals erupting along the haft (growth)
        for k, yy in enumerate(range(y0 + 2, y1, 5)):
            s = 1 if k % 2 else -1
            g.crystal((s * 1, yy, 0), (s, 1.3, (k % 3 - 1) * 0.4), 3.0 + (k % 2), 0.9, 'crystal', glow=big, prio=3)
        if big:
            crystal_cluster(g, (0, top + 1, 0), p, 4, 5.0, 1.3, glow=True)
    elif th in ('water',):
        serpent(g, y0, y1, 2.4, 2.2, p, rmax=1.3)
    elif th in ('abyss', 'blood'):
        if big or p.creature:
            serpent(g, y0, y1 + 2, 2.6, 2.4, p, rmax=1.5)
        tendrils(g, (0, hy - 6, 0), p, n=4, length=5, spread=4, up=-0.6)
    elif th == 'clock':
        pts = helix(y0, y1, 2.0, (y1 - y0) / 3.0, 0.0)
        g.tube(pts, 0.5, 0.5, 'orn', 0.75, prio=2)
        if big:
            gear(g, (0, hy, 2), 3.2, p, 8, 'xy', 'orn')
    elif th == 'forge':
        for k, yy in enumerate(range(y0 + 3, y1, 6)):
            g.put(0, yy, 2, 'glow', 0.8, glow=True, prio=3)
            g.put(0, yy, -2, 'glow', 0.8, glow=True, prio=3)
        if big:
            flames(g, hy - 4, hy + 4, lambda y: 3.0, p, n=3)
    elif th == 'frost':
        ice_spikes(g, [(s * 1.5, yy, 0, s, 1.0) for s, yy in ((1, y1 - 2), (-1, y1 - 6), (1, y1 - 10))], p, 3.0)
    elif th == 'ink':
        ribbon(g, y0, y1, 2.4, p, turns=2.4)
    elif th in ('holy', 'storm'):
        for s in (-1, 1):
            wing(g, (s * 2, hy - 2, 0), s, p, span=6 + 2 * big, rise=7 + 3 * big, n=5)
    if big:
        float_shards(g, [(-7, hy + 6, 0), (7, hy - 6, 0)] + ([(0, top + 8, 0)] if lv >= 5 else []), p, 3.0, 0.85)
    if lv >= 5:
        halo(g, (0, hy, 0), 9.0, 'z')


# staves & scepters ---------------------------------------------------------

def _staff_base(g, p, top, mat='wood'):
    shaft(g, -18, top, 1.25, mat, bands=(-10, 0, top - 2))
    g.crystal((0, -18, 0), (0, -1, 0), 3.0, 1.2, 'metal', prio=2)
    grip(g, -4, 4, mat='grip')


def staff_orb(g, p):
    top = int(28 * p.L)
    _staff_base(g, p, top)
    cy = top + 6
    R = 3.4 if p.lv < 4 else 4.0
    g.ball((0, cy, 0), R, 'glow' if p.lv >= 1 else 'gem', glow=True,
           vfn=lambda i, j, k, d: 0.35 + 0.55 * (1 - d) + (0.15 if (i + j) < cy - 2 else 0), prio=3)
    # cage prongs
    n = 4 if p.lv < 3 else 6
    for k in range(n):
        a = 2 * math.pi * k / n + 0.4
        dx, dz = math.cos(a), math.sin(a)
        pts = catmull([(0, top - 1, 0), (dx * (R + 1.2), cy - R + 0.5, dz * (R + 1.2)),
                       (dx * (R + 1.6), cy + 0.5, dz * (R + 1.6)), (dx * (R * 0.4), cy + R + 2.2, dz * (R * 0.4))], 6)
        g.tube(pts, 0.75, 0.55, 'orn' if p.lv >= 2 else 'wood', vfn=lambda t, d, q: 0.45 + 0.3 * (1 - d) + 0.1 * t, prio=2)
    if p.lv >= 2:
        g.crystal((0, cy + R + 1.6, 0), (0, 1, 0), 3.0, 0.9, 'gem', glow=p.glow, prio=4)
    if p.theme == 'clock':
        g.torus((0, cy, 0), R + 2.5, 0.5, 'y', 'orn', 0.7)
        g.torus((0, cy, 0), R + 3.5, 0.5, 'z', 'metal', 0.6)
        for k in range(3):
            a = 2 * math.pi * k / 3
            g.ball((math.cos(a) * (R + 2.5), cy, math.sin(a) * (R + 2.5)), 1.0, 'gem', 0.7, prio=4)
    if p.theme == 'abyss' and p.lv >= 4:
        for ax in ('y', 'z', 'x'):
            g.torus((0, cy, 0), R + 3.0, 0.5, ax, 'glow', 0.8, glow=True, prio=4)
        tendrils(g, (0, cy - R, 0), p, n=5, length=7, spread=6, up=-0.8)
    dress_shaft(g, p, -6, top - 4, cy, cy + R)


def staff_crystal(g, p):
    top = int(28 * p.L)
    _staff_base(g, p, top)
    cy = top + 2
    # claw holding the crystal
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.78
        dx, dz = math.cos(a), math.sin(a)
        pts = catmull([(0, top - 2, 0), (dx * 2.5, top + 1, dz * 2.5), (dx * 2.2, top + 5, dz * 2.2), (dx * 1.0, top + 7, dz)], 5)
        g.tube(pts, 0.8, 0.5, 'orn' if p.lv >= 2 else 'metal', vfn=lambda t, d, q: 0.5 + 0.3 * t, prio=2)
    mat = 'ice' if p.theme == 'frost' else 'crystal'
    g.crystal((0, cy, 0), (0, 1, 0), 11 + 2 * (p.lv >= 4), 2.1, mat, glow=p.glow, prio=3, tip=0.4)
    if p.lv >= 2:
        for k in range(3 + (p.lv >= 4) * 2):
            a = 2 * math.pi * k / (3 + (p.lv >= 4) * 2)
            g.crystal((math.cos(a) * 1.2, cy + 1, math.sin(a) * 0.8), (math.cos(a) * 0.6, 1, math.sin(a) * 0.4), 5.0, 1.0,
                      mat, glow=p.glow, prio=3)
    if p.theme == 'forge':
        flames(g, top - 1, top + 3, lambda y: 2.0, p, n=2)
    dress_shaft(g, p, -6, top - 4, cy + 5, cy + 12)


def staff_ring(g, p):
    top = int(26 * p.L)
    _staff_base(g, p, top)
    cy = top + 7
    R = 6.0
    g.torus((0, cy, 0), R, 1.1, 'z', 'orn' if p.lv >= 1 else 'wood', vfn=lambda t, d, q: 0.45 + 0.35 * (1 - d))
    g.ball((0, cy, 0), 1.9, 'gem', glow=True, vfn=lambda i, j, k, d: 0.5 + 0.45 * (1 - d), prio=3)
    for k in range(6 if p.lv >= 2 else 3):
        a = 2 * math.pi * k / (6 if p.lv >= 2 else 3) + math.pi / 2
        g.gem((math.cos(a) * R, cy + math.sin(a) * R, 1), 0.9, 'gem', glow=p.glow)
    if p.theme == 'clock' or 'tesla' in p.iid:
        pts = helix(top - 8, top, 2.3, 4.0, 0.0)
        g.tube(pts, 0.6, 0.6, 'orn', 0.7, prio=3)
        if p.lv >= 4:
            for k in range(4):
                a = 2 * math.pi * k / 4 + 0.4
                zigzag(g, (math.cos(a) * 2, cy + math.sin(a) * 2, 0), (math.cos(a) * (R - 1), cy + math.sin(a) * (R - 1), 0),
                       p, n=3, amp=0.8)
    if p.theme == 'fungi':
        for k in range(3):
            a = 2 * math.pi * k / 3 + 1.2
            fungi(g, (math.cos(a) * R, cy + math.sin(a) * R, 0), p, 1.7, up=(math.cos(a), math.sin(a), 0))
    if p.theme == 'crystal':
        for k in range(4):
            a = 2 * math.pi * k / 4 + 0.78
            g.crystal((math.cos(a) * R, cy + math.sin(a) * R, 0), (math.cos(a), math.sin(a), 0), 3.4, 0.9, 'crystal',
                      glow=p.glow, prio=3)
    dress_shaft(g, p, -6, top - 4, cy, cy + R)


def scepter(g, p):
    top = int(14 * p.L)
    shaft(g, -8, top, 1.25, 'orn' if p.lv >= 2 else 'wood', bands=(-2, top - 1))
    grip(g, -7, 2)
    pommel(g, -10, p, 1.4)
    cy = top + 4
    # flanged crown
    for k in range(5):
        a = 2 * math.pi * k / 5
        dx, dz = math.cos(a), math.sin(a)
        pts = catmull([(dx * 1.0, top, dz), (dx * 3.2, top + 2.5, dz * 3.2), (dx * 2.8, top + 6, dz * 2.8),
                       (dx * 1.0, top + 8, dz * 1.0)], 5)
        g.tube(pts, 0.8, 0.5, 'orn', vfn=lambda t, d, q: 0.5 + 0.3 * (1 - d), prio=2)
    g.gem((0, cy + 0.5, 0), 2.2, 'gem', glow=True)
    g.crystal((0, top + 7, 0), (0, 1, 0), 4.0, 1.0, 'gem', glow=p.glow, prio=4)
    if p.theme in ('forge', 'holy') and p.lv >= 3:
        flames(g, top + 2, top + 6, lambda y: 3.2, p, n=2)
    if p.theme == 'crystal' and p.lv >= 2:
        for s in (-1, 1):
            g.crystal((s * 3, cy, 0), (s * 0.8, 1, 0), 5.0, 1.0, 'crystal', glow=p.glow, prio=3)
            g.ball((s * 5, cy + 6, 0), 1.4, 'glow', 0.9, glow=True, prio=4)
    dress_shaft(g, p, -6, top - 2, cy, top + 11)


def sun_scepter(g, p):
    top = int(16 * p.L)
    shaft(g, -8, top, 1.25, 'orn', bands=(-2, top - 1))
    grip(g, -7, 2)
    pommel(g, -10, p, 1.4)
    cy = top + 6
    rays = 8 if p.lv < 4 else 12
    for k in range(rays):
        a = 2 * math.pi * k / rays + math.pi / 2
        ln = 6.5 if k % 2 == 0 else 4.5
        g.crystal((math.cos(a) * 2.5, cy + math.sin(a) * 2.5, 0), (math.cos(a), math.sin(a), 0), ln, 1.0,
                  'orn', prio=2, tip=0.7)
    g.torus((0, cy, 0), 3.4, 0.8, 'z', 'orn', 0.7)
    g.ball((0, cy, 0), 2.5, 'glow', glow=True, vfn=lambda i, j, k, d: 0.5 + 0.45 * (1 - d), prio=3)
    if 'seraph' in p.iid:
        for s in (-1, 1):
            for k, (sp, ri, dr) in enumerate(((9, 9, 0), (8, 4, 25), (6, -2, 50))):
                wing(g, (s * 2.5, cy - 2 - k * 1.5, -1 + k), s, p, span=sp, rise=ri + 3, n=5, droop=dr)
    elif 'aurora' in p.iid:
        for s in (-1, 1):
            pts = catmull([(s * 3, cy - 3, 0), (s * 7, cy + 1, 1), (s * 6, cy + 7, -1), (s * 9, cy + 11, 0)], 6)
            g.tube(pts, 1.2, 0.5, 'glow', glow=True, sq=(1, 1, 0.6), vfn=lambda t, d, q: 0.5 + 0.4 * t, prio=3)
    elif 'bloom' in p.iid:
        for k in range(6):
            a = 2 * math.pi * k / 6
            g.ball((math.cos(a) * 3.6, cy + math.sin(a) * 3.6, 1), 1.6, 'fungus', sq=(1, 1, 0.5),
                   vfn=lambda i, j, k_, d: 0.4 + 0.4 * (1 - d), prio=3)
    if p.theme == 'holy' and p.lv >= 3 and 'seraph' not in p.iid and 'aurora' not in p.iid:
        for s in (-1, 1):
            wing(g, (s * 2, cy - 3, 0), s, p, span=6, rise=6, n=4)
    if p.lv >= 4:
        float_shards(g, [(-8, cy - 6, 0), (8, cy - 4, 0)], p, 2.8, 0.8, 'glow')
    if p.lv >= 5:
        halo(g, (0, cy + 2, 0), 9.5, 'z')


def censer_staff(g, p):
    top = int(28 * p.L)
    _staff_base(g, p, top, 'metal' if p.lv >= 2 else 'wood')
    # hook arching over to the front (+x)
    hook = catmull([(0, top, 0), (1, top + 4, 0), (4, top + 6, 0), (7, top + 4, 0), (7.5, top + 1, 0)], 6)
    g.tube(hook, 1.1, 0.8, 'orn' if p.lv >= 1 else 'metal', vfn=lambda t, d, q: 0.45 + 0.3 * (1 - d))
    # chain links
    for k in range(3):
        y = top - k * 2
        g.torus((7.5, y, 0), 0.9, 0.5, 'z' if k % 2 else 'x', 'metal', 0.6)
    ly = top - 9
    # lantern / bell / pendulum cage
    if p.theme == 'water':
        g.ball((7.5, ly, 0), 3.2, 'metal', sq=(1, 1.1, 1), vfn=lambda i, j, k, d: None if d < 0.72 and j < ly - 1 else
               0.35 + 0.3 * (1 - d) + 0.15 * (j > ly), prio=2)
        g.ball((7.5, ly - 2.6, 0), 1.0, 'glow', 0.9, glow=True, prio=3)
    elif p.theme == 'clock':
        g.box((5, ly - 3, -2), (10, ly + 3, 2), 'metal', vfn=lambda i, j, k: 0.5 if abs(i - 7.5) > 2 or abs(k) == 2 else None)
        gear(g, (7.5, ly, 3), 2.4, p, 6, 'xy', 'orn')
        g.tube([(7.5, ly + 2, 0), (7.5 + 2, ly - 4, 0)], 0.5, 0.5, 'orn', 0.8, prio=3)
        g.ball((9.5, ly - 4.5, 0), 1.2, 'gem', 0.8, glow=True, prio=3)
    else:
        def cage(i, j, k):
            dx, dz = i - 7.5, k
            if abs(j - ly) >= 3:
                return 0.55
            return 0.5 if (abs(dx) >= 2.5 and abs(dz) >= 1.5) or (abs(dx) >= 2.5 and dz == 0 and False) else None
        g.box((5, ly - 3, -2), (10, ly + 3, 2), 'metal', vfn=lambda i, j, k: 0.55 if abs(j - ly) >= 3 or
              (abs(i - 7.5) >= 2.4 and abs(k) >= 2) else None)
        g.ball((7.5, ly, 0), 1.8, 'glow', glow=True, vfn=lambda i, j, k, d: 0.55 + 0.4 * (1 - d), prio=3)
        g.crystal((7.5, ly + 3, 0), (0, 1, 0), 2.2, 1.6, 'orn', prio=2)
    if p.theme == 'crystal':
        g.crystal((7.5, ly - 3, 0), (0, -1, 0), 3.5, 1.0, 'crystal', glow=p.glow, prio=3)
    if p.lv >= 3:
        for k in range(3):
            g.ball((7.5 + (k - 1) * 1.6, ly + 5 + k * 2, 0), 0.9 + 0.3 * k, 'glow' if p.glow else 'string', 0.6,
                   glow=p.glow, prio=1)
    dress_shaft(g, p, -6, top - 6, top, top + 6)


# bows ------------------------------------------------------------------------

def bow(g, p, kind, pull=-1):
    """Limbs along Y, tips toward +X (string side); grip at the origin.  pull −1 resting, 0..2 drawing."""
    L = p.L
    H = int(17 * L)
    f = (pull + 1) / 3.0 if pull >= 0 else 0.0
    curv = {'longbow': 3.0, 'recurve_bow': 4.0, 'composite_bow': 4.6}[kind] * (1 + 0.55 * f)
    th = 1.3 if kind != 'composite_bow' else 1.6
    tips = []
    for s in (1, -1):
        pts = []
        for k in range(0, 21):
            t = k / 20
            y = s * (2.5 + (H - 2.5) * t)
            x = curv * t * t * (1.0 + 0.2 * f) - 0.6
            if kind == 'recurve_bow' and t > 0.78:
                x -= (t - 0.78) * 14 * (1 - 0.4 * f)
            pts.append((x, y, 0))
        g.tube(pts, th, 0.6, 'wood' if p.theme not in ('crystal', 'storm', 'water') or p.lv < 2 else 'metal',
               sq=(1, 1, 0.8), vfn=lambda t, d, q: 0.38 + 0.3 * (1 - d) + 0.06 * math.sin(t * 30), prio=2)
        if kind == 'composite_bow':
            g.tube([(q[0] - 1.2, q[1], q[2]) for q in pts[2:15]], 0.6, 0.5, 'orn' if p.lv >= 1 else 'bone', 0.65, prio=2)
        tip = pts[-1]
        tips.append(tip)
        g.ball(tip, 1.1, 'orn' if p.lv >= 1 else 'metal', 0.6, prio=3)
        if p.lv >= 2:
            g.crystal(tip, (0.4, s, 0), 2.5, 0.8, 'gem', glow=p.glow, prio=3)
    # riser / grip
    g.box((-2, -3, -1), (0, 3, 1), 'grip', vfn=lambda i, j, k: 0.6 if (j + i) % 3 == 0 else 0.4, prio=3)
    g.box((-3, -1, -1), (-3, 1, 1), 'orn' if p.lv >= 1 else 'metal', 0.6, prio=3)
    if p.lv >= 2:
        g.gem((-3, 0, 1), 1.0, 'gem', glow=p.glow)
    # string
    (ux, uy, _), (lx, ly, _) = tips
    sx = max(ux, lx)
    if pull < 0:
        g.tube([(sx, uy, 0), (sx, ly, 0)], 0.5, 0.5, 'string', 0.7, prio=1)
    else:
        nx = sx + 3 + 2.5 * pull
        g.tube([(ux, uy, 0), (nx, 0, 0), (lx, ly, 0)], 0.5, 0.5, 'string', 0.7, prio=1)
        # arrow
        g.tube([(nx, 0, 0), (-8, 0, 0)], 0.5, 0.5, 'wood', 0.5, prio=4)
        g.crystal((-8, 0, 0), (-1, 0, 0), 2.6, 1.0, 'edge' if not p.glow else 'glow', glow=p.glow, prio=5)
        for s in (-1, 1):
            g.tube([(nx - 0.5, 0, 0), (nx - 3, s * 1.3, 0)], 0.5, 0.5, 'feather', 0.7, prio=4)
    dress_bow(g, p, H, curv, tips)


def dress_bow(g, p: P, H, curv, tips):
    th, lv = p.theme, p.lv
    if lv < 3:
        if lv == 2 and th in ('vine', 'fungi'):
            vines(g, 2, H - 4, 1.6, p, n=1, leaves=True, buds=False)
        return
    big = lv >= 4
    if th in ('vine', 'fungi'):
        for s in (1, -1):
            pts = [(curv * (k / 10) ** 2 - 0.6 + math.sin(k) * 0.9, s * (2.5 + (H - 2.5) * k / 10), math.cos(k * 1.3))
                   for k in range(1, 9)]
            g.tube(pts, 0.6, 0.5, 'vine', 0.5, prio=3)
        if th == 'fungi':
            fungi(g, (-2.0, 6, 0), p, 1.5, up=(-0.6, 1, 0))
            fungi(g, (-2.0, -7, 0), p, 1.5, up=(-0.6, -1, 0))
    elif th == 'water':
        for s in (1, -1):
            shell(g, (-2.5, s * 6.5, 0.5), p, 2.0)
            pts = [(curv * (k / 10) ** 2 - 2.0, s * (3 + (H - 3) * k / 10), 0) for k in range(1, 10)]
            g.tube(pts, 0.7, 0.4, 'gem', 0.6, prio=1)
        if big:
            serpent(g, -H + 4, H - 6, 2.0, 2.4, p, rmax=1.2)
    elif th == 'storm':
        for s in (1, -1):
            wing(g, (-1.5, s * 3, 0), -1, p, span=7 + 2 * big, rise=s * (H - 5), n=6)
        if big:
            zigzag(g, (-9, -H + 6, 0), (-9, H - 6, 0), p, n=7, amp=1.6)
    elif th == 'clock':
        gear(g, (-3, 0, 2), 3.0, p, 8, 'xy', 'orn')
        for s in (1, -1):
            pts = helix(s * 4, s * (H - 4), 1.8, 3.0, 0.0)
            g.tube([(q[0] + curv * 0.15, q[1], q[2]) for q in pts], 0.5, 0.5, 'orn', 0.7, prio=1)
    elif th == 'forge':
        for s in (1, -1):
            for k in range(3):
                y = s * (5 + k * 4)
                t = (abs(y) - 2.5) / (H - 2.5)
                g.put(round(curv * t * t - 0.6), y, 1, 'glow', 0.8, glow=True, prio=4)
        gear(g, (-3, 0, 2), 2.6, p, 6, 'xy', 'metal')
    elif th == 'crystal':
        for s in (1, -1):
            g.crystal((-1.5, s * 7, 0), (-1, s * 0.6, 0), 4.0, 1.0, 'crystal', glow=big, prio=3)
    elif th in ('abyss', 'blood'):
        tendrils(g, (-2, 0, 0), p, n=4, length=4, spread=6, up=0.2)
    elif th == 'holy':
        for s in (1, -1):
            wing(g, (-1.5, s * 3, 0), -1, p, span=6, rise=s * (H - 6), n=5)
    elif th == 'web':
        web(g, (-3, 0, 0), 5, p)
    if big:
        float_shards(g, [(-7, 8, 0), (-7, -8, 0)] + ([(-10, 0, 0)] if lv >= 5 else []), p, 2.8, 0.8,
                     'glow' if th == 'storm' else 'crystal')
    if lv >= 5:
        halo(g, (-2, 0, 0), 6.0, 'x')


TEMPLATES = {
    'longsword': longsword, 'broadsword': broadsword, 'greatsword': greatsword, 'cleaver': cleaver,
    'great_axe': great_axe, 'mace': mace, 'dagger': dagger, 'kris': kris, 'fang_blade': fang_blade,
    'staff_orb': staff_orb, 'staff_crystal': staff_crystal, 'staff_ring': staff_ring, 'scepter': scepter,
    'sun_scepter': sun_scepter, 'censer_staff': censer_staff,
}
BOWS = ('longbow', 'recurve_bow', 'composite_bow')
TWO_HANDED = {'greatsword', 'cleaver', 'great_axe'}
