"""Voxel boss designs (floor 1–10 bosses).  See README.md (tools: voxel/mob_kit.py).

Pilot design (reference for the boss designer): floor01_moss_warden.
Coordinates: part px, origin = the part's pivot, front = −Z, model −X = the boss's left.
Bosses: budget 3000 elements in total, ≤ 720 per part; the atlas pulses over 8 frames, so give every
boss glowing parts (core / eyes / runes / veins) — glow materials: glow, eye, core, rune, lava.
"""
from __future__ import annotations

import math

from ..util import h2, h3
from ..voxel.mob_kit import MobGrid, fbm3, vadd, vcross, vlen, vmul, vnorm, vsub  # noqa: F401

TAU = 2 * math.pi

# ───────────────────────────── floor01_moss_warden (이끼 파수꾼 그로브) ─────────────────────────────
# An ancient guardian statue the corridor grew over: fitted masonry blocks with chiselled bevels and
# cracks, weathered bronze bands carved with glowing runes, a lime crystal heart in a carved stone ring
# whose light runs out through root-veins, a heavy mantle of moss, ferns and glowcaps, and a branching
# antler crown of living wood.  Fists like boulders, root-feet gripping the floor.

WARDEN_BRONZE = [(26, 24, 14), (52, 48, 26), (88, 78, 40), (132, 114, 60), (178, 156, 90), (220, 204, 140),
                 (246, 238, 196)]
WARDEN_PATINA = [(18, 46, 38), (34, 84, 68), (60, 128, 102), (104, 172, 140), (160, 210, 180)]
WARDEN_GLOW = [(40, 70, 10), (96, 150, 24), (168, 214, 70), (214, 244, 140), (244, 255, 210), (255, 255, 255)]
GLOWCAP = [(10, 60, 66), (18, 120, 120), (40, 190, 176), (120, 236, 210), (200, 255, 236), (255, 255, 255)]
WARDEN_STONE = [(20, 22, 22), (38, 41, 40), (60, 64, 60), (86, 90, 84), (116, 120, 110), (148, 152, 138),
                (182, 184, 168), (214, 214, 198)]


def _warden_ramps(ctx):
    ctx.set_ramp('stone', WARDEN_STONE)
    ctx.set_ramp('brass', WARDEN_BRONZE)
    ctx.set_ramp('patina', WARDEN_PATINA)
    for m in ('core', 'eye', 'rune', 'glow'):
        ctx.set_ramp(m, WARDEN_GLOW)
    ctx.set_ramp('cap', GLOWCAP)


def _masonry(g: MobGrid, mats=('stone',), period=(4.6, 3.4), seed=0):
    """Chiselled block seams: darker mortar lines on a staggered block grid + broad weathering patches."""
    sd = g.seed + 17 + seed

    def f(x, y, z, n, m, v):
        row = math.floor(y / period[1])
        u = (x + z) / period[0] + 0.5 * (row % 2)
        if (y / period[1]) % 1.0 < 0.14 or u % 1.0 < 0.09:
            return v - 0.15
        return v + 0.12 * (fbm3(x / 5, y / 5, z / 5, sd) - 0.5)
    g.paint(f, list(mats))


def _patina(g: MobGrid, amount=0.35, scale=1.8, seed=0):
    sd = g.seed + 23 + seed

    def f(x, y, z, n, m, v):
        q = fbm3(x / scale, y / scale, z / scale, sd)
        return ('patina', 0.35 + (q - (1 - amount)) * 1.5) if q > 1 - amount else None
    g.paint(f, ['brass'])


def _warden_torso(g: MobGrid, ctx):
    # inverted-trapezoid stone torso: broad chest block, narrower abdomen, pectoral slabs
    g.rbox((-9.6, -0.6, -5.8), (9.6, 9.0, 6.0), 'stone', 0.52, bevel=2.2, top=0.12)
    g.rbox((-7.2, -9.0, -4.8), (7.2, 0.4, 5.0), 'stone', 0.46, bevel=1.6)
    for s in (-1, 1):
        g.rbox((s * 0.6, 2.2, -6.6), (s * 8.6, 8.0, -5.0), 'stone', 0.58, bevel=1.0)
    _masonry(g)
    # carved bronze ring (with a halo of small runes) around a cavity holding the crystal heart
    g.carve_blob((0, 3.8, -6.4), (3.3, 3.3, 2.8))
    g.blob((0, 3.8, -4.4), (3.0, 3.0, 1.4), 'void', 0.25, prio=2, top=0.0)
    g.ring((0, 3.8, -6.0), 3.7, 1.15, axis='z', mat='brass', val=0.58)
    g.crystals((0, 2.4, -4.6), (0, 0.55, -1), n=5, size=3.4, r=1.25, mat='core', glow=True, spread=0.75, seed=3)
    g.blob((0, 3.8, -5.0), 1.5, 'core', 0.42, glow=True, prio=4)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        g.dot((math.cos(a) * 3.7, 3.8 + math.sin(a) * 3.7, -7.2), 'rune', 0.4, glow=True, prio=6)
    # three root-veins of light creeping from the ring over the chest and down to the bronze band
    for k, (a, L) in enumerate(((0.45, 9), (2.7, 9), (4.71, 6))):
        g.branch((math.cos(a) * 4.4, 3.8 + math.sin(a) * 4.4, -6.2), (math.cos(a), math.sin(a), 0.12), L * 0.5,
                 0.45, depth=1, fork=2, spread=0.6, decay=0.75, mat='glow', val=0.22, prio=5, seed=k,
                 bend=(0, 0, 0.5))
    for v in list(g.vox.values()):
        if v[0] == 'glow':
            v[2] = True
    # weathered bronze band with glowing runes (boss trim) across the abdomen
    g.rbox((-7.6, -6.2, -5.3), (7.6, -4.4, 5.5), 'brass', 0.5, bevel=0.5)
    _patina(g, 0.4)
    g.runes((0, -5.3, -6.5), (0, 0, -1), w=12.0, h=1.6, mat='rune', val=0.3, density=0.7, seed=2)
    # moss only on the top ledges, a few hanging strands and vines, thin cracks
    g.moss_paint(coverage=0.6, mats=['stone'], scale=3.6, up_min=0.65, depth=1)
    g.clumps(3, 1.8, 'moss', 0.55, mats=['moss'])
    g.sprinkle(['moss'], sprouts=4, flowers=4, hang=6, hang_len=(1.5, 4.0))
    for x in (-6.4, 6.0):
        g.vine([(x, 8.6, -6.2), (x + 0.4, 4.0, -6.9), (x - 0.3, -1.0, -6.4), (x + 0.2, -3.8, -5.6)], r=0.42,
               leaves=0.45, leaf_size=0.9)
    g.cracks(['stone'], width=0.022, scale=6.0, dv=-0.25, seed=1)
    # roots creeping down the flanks
    for s in (-1, 1):
        g.branch((s * 6.8, -2.0, 4.4), (s * 0.3, -1, 0.2), 6.0, 0.9, depth=2, fork=2, spread=0.5, mat='bark',
                 val=0.42, seed=10 + s)


def _warden_mantle(g: MobGrid, ctx):
    # heavy horseshoe collar of moss: thickest on the shoulders, draping lower over the back, open at the
    # front for the head (mantle pivot sits 0.8 px behind and 7.2 px above the torso centre)
    pts = []
    for k in range(25):
        a = math.pi * (-0.12 + 1.24 * k / 24)          # from front-left, round the back, to front-right
        x = -math.cos(a) * 9.4
        z = math.sin(a) * 4.6 + 0.2
        pts.append((x, 0.4 * abs(math.cos(a)) - 0.9 * math.sin(a), z))
    for k, p in enumerate(pts):
        side = abs(p[0]) / 9.4
        r = 2.0 + 1.5 * side
        g.blob(p, (r, r * 0.7, r * 0.9), 'moss', 0.5, lump=0.3, lump_scale=1.8, seed=k, top=0.2)
    # moss drapes hanging over the chest edge and the back, ragged ends
    g.cloth([(-9.4, -1.4, -2.4), (-6.4, -1.8, -3.6)], 3.2, 'moss', 0.42, tatter=0.6, normal=(0, 0, -1), thick=2)
    g.cloth([(6.4, -1.8, -3.6), (9.4, -1.4, -2.4)], 3.2, 'moss', 0.42, tatter=0.6, normal=(0, 0, -1), thick=2,
            seed=2)
    g.cloth([(8.4, -2.4, 4.2), (0, -3.0, 5.6), (-8.4, -2.4, 4.2)], 5.4, 'moss', 0.4, tatter=0.55, normal=(0, 0, 1),
            thick=2, seed=3)
    g.mottle(['moss'], 0.1, 2.4)
    # big fern fronds, glowcap clusters (the spore burst), pale flowers, glowing buds
    for k, (x, z, d) in enumerate(((-9.0, 1.4, (-0.6, 1, 0.3)), (9.2, 0.8, (0.6, 1, 0.2)), (-4.6, 4.4, (-0.3, 1, 0.8)),
                                   (5.0, 4.2, (0.4, 1, 0.8)))):
        g.branch((x, 1.4, z), d, 3.4, 0.45, depth=1, fork=2, spread=0.9, mat='leaf', val=0.5, tip='leaf',
                 tip_mat='leaf', tip_size=0.9, seed=20 + k)
    for c, r, up in (((-7.6, 2.0, 2.2), 1.3, (-0.3, 1, 0)), ((-6.4, 1.6, 3.8), 0.9, (-0.2, 1, 0.3)),
                     ((7.4, 2.2, 2.6), 1.2, (0.3, 1, 0.1)), ((2.2, 1.0, 4.8), 1.0, (0.1, 1, 0.4))):
        g.mushroom(c, up, 1.4, r, mat='cap', val=0.4, spots=0.0, glow=True)
    g.sprinkle(['moss'], sprouts=10, flowers=10, glow_buds=8, up_min=0.55)


def _warden_head(g: MobGrid, ctx):
    # blocky carved stone head: heavy brow, deep-set glowing eyes, a stone jaw slot, moss beard
    g.rbox((-4.2, -4.0, -4.2), (4.2, 3.6, 4.2), 'stone', 0.5, bevel=1.4, top=0.14)
    g.rbox((-4.6, 0.6, -4.8), (4.6, 2.2, -3.2), 'stone', 0.6, bevel=0.6)              # brow ledge
    g.rbox((-3.4, -4.6, -4.6), (3.4, -2.2, -1.0), 'stone', 0.42, bevel=0.8)            # jaw
    _masonry(g, period=(2.6, 2.2), seed=4)
    for s in (-1, 1):
        g.eye((s * 1.8, -0.4, -4.1), 0.9, val=0.4, socket=0.6, facing=(0, 0, -1))
    g.carve(lambda x, y, z: abs(x) < 2.4 and -3.6 < y < -2.7 and z < -3.6)
    g.rbox((-2.4, -3.6, -3.9), (2.4, -2.7, -3.6), 'void', 0.15)
    g.rbox((-2.2, 2.2, -4.7), (2.2, 3.0, -4.0), 'brass', 0.5, bevel=0.3)               # bronze circlet front
    g.runes((0, 2.6, -5.2), (0, 0, -1), w=4.0, h=0.8, mat='rune', val=0.3, density=0.9, seed=5)
    g.cracks(['stone'], width=0.025, scale=4.0, dv=-0.25, seed=2)
    # moss beard hanging from the jaw
    g.cloth([(-3.0, -4.4, -4.2), (3.0, -4.4, -4.2)], 3.2, 'moss', 0.45, tatter=0.65, normal=(0, 0, -1), thick=2,
            seed=6)
    g.moss_paint(coverage=0.55, mats=['stone'], scale=2.6, up_min=0.7)
    # branching antler crown of living wood, leaves and glowing buds at the tips
    for s in (-1, 1):
        g.branch((s * 3.4, 2.4, 0.4), (s * 0.8, 1, 0.2), 7.0, 1.3, depth=2, fork=2, spread=0.6, decay=0.62,
                 mat='bark', val=0.5, tip='leaf', tip_mat='leaf', tip_size=1.2, seed=40 + s, bend=(s * 1.0, 0, 0.5))
        g.branch((s * 2.2, 3.4, 1.8), (s * 0.3, 1, 0.6), 3.4, 0.6, depth=1, fork=2, spread=0.7, mat='bark', val=0.5,
                 tip='bud', tip_mat='glow', glow_tip=True, seed=50 + s)


def _warden_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    # mossy shoulder boulder, stone upper arm, elbow block, heavy forearm, boulder fist with knuckles
    g.blob((o * 0.6, -1.4, 0.0), (5.0, 4.0, 4.8), 'stone', 0.52, lump=0.18, lump_scale=2.6, top=0.18)
    g.capsule((0, -3.0, 0.0), (0, -10.4, 0.2), 3.0, 2.8, 'stone', 0.48)
    g.rbox((-3.2, -12.6, -3.0), (3.2, -9.8, 3.2), 'stone', 0.55, bevel=1.0)
    g.capsule((0, -12.0, -0.2), (0, -17.6, -0.8), 3.3, 3.9, 'stone', 0.5)
    g.blob((0, -20.4, -0.8), (4.6, 3.4, 4.4), 'stone', 0.52, lump=0.14, lump_scale=2.4, top=0.16)
    for k in range(4):
        x = -3.3 + k * 2.2
        g.blob((x, -21.4 + 0.3 * (k % 2), -4.6), (1.2, 1.3, 1.1), 'stone', 0.62)          # knuckles
    g.blob((-o * 3.8, -19.8, -3.2), (1.1, 1.6, 1.1), 'stone', 0.58)                          # thumb
    _masonry(g, period=(3.0, 2.4), seed=6)
    # bronze cuff with runes on the forearm; roots wrapping the other forearm
    if right:
        g.rbox((-4.2, -16.6, -4.0), (4.2, -14.6, 3.4), 'brass', 0.5, bevel=0.6)
        _patina(g, 0.35, seed=1)
        g.runes((0, -15.6, -4.6), (0, 0, -1), w=6.0, h=1.4, mat='rune', val=0.3, density=0.8, seed=7)
    else:
        g.vine_wrap((0, -20.0, 0), (0, -9.0, 0), 4.0, turns=2.2, mat='bark', r=0.7, leaves=0.4, leaf_size=1.0)
        g.ring((0, -15.6, -0.4), 3.9, 0.7, axis='y', mat='brass', val=0.5)
        _patina(g, 0.5, seed=2)
    g.moss_paint(coverage=0.7, mats=['stone'], scale=3.0, up_min=0.6, depth=1)
    g.clumps(3, 1.6, 'moss', 0.55, mats=['moss'], region=lambda x, y, z: y > -6)
    g.sprinkle(['moss'], sprouts=3, flowers=2, hang=5, hang_len=(1.5, 3.5))
    g.cracks(['stone'], width=0.022, scale=5.0, dv=-0.25, seed=3)


def _warden_legs(g: MobGrid, ctx):
    # stout pillar legs on a hip block; broad feet whose roots grip the floor (ground = y −14)
    gy = -14.0
    g.rbox((-6.8, -3.4, -3.4), (6.8, 0.8, 3.6), 'stone', 0.46, bevel=1.4)
    for s in (-1, 1):
        x = s * 4.0
        g.capsule((x, -2.0, 0.0), (x, -7.0, -0.2), 3.0, 2.9, 'stone', 0.48)
        g.rbox((x - 3.0, -9.0, -3.2), (x + 3.0, -6.0, 3.0), 'stone', 0.56, bevel=1.0)     # knee block
        g.capsule((x, -8.4, 0.0), (x, -11.6, 0.0), 2.7, 3.0, 'stone', 0.46)
        g.rbox((x - 3.4, gy, -4.6), (x + 3.4, gy + 2.6, 3.4), 'stone', 0.44, bevel=1.0)    # foot
        for k in range(3):
            tx = x - 2.2 + k * 2.2
            g.rbox((tx - 0.9, gy, -5.6), (tx + 0.9, gy + 1.6, -4.2), 'stone', 0.56, bevel=0.5)
        for k, (dx, dz) in enumerate(((s * 1.0, -0.4), (s * 0.7, 0.8), (s * 0.1, 1.0))):
            g.branch((x + s * 2.4, gy + 1.6, 0.8 * k - 0.8), (dx, -0.25, dz), 4.2, 0.85, depth=1, fork=2,
                     spread=0.6, mat='bark', val=0.42, floor_y=gy, seed=60 + k * 3 + s, bend=(0, -0.6, 0))
    _masonry(g, period=(3.0, 2.4), seed=8)
    g.moss_paint(coverage=0.55, mats=['stone'], scale=3.0, up_min=0.6, depth=1)
    g.sprinkle(['moss'], sprouts=4, flowers=3)
    g.cracks(['stone'], width=0.022, scale=5.0, dv=-0.25, seed=4)


def floor01_moss_warden(look, name, part, ctx):
    _warden_ramps(ctx)
    fn = {'torso': _warden_torso, 'mantle': _warden_mantle, 'head': _warden_head, 'arm_left': _warden_arm,
          'arm_right': _warden_arm, 'legs': _warden_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.8, 'mantle': 0.8, 'head': 0.6, 'legs': 0.8}.get(name, 0.8))
    fn(g, ctx)
    return g


# ───────────────────────────── shared helpers (floors 2–10) ─────────────────────────────

def _box(g, lo, hi, mat, val=0.5, **kw):
    """rbox that never vanishes: an axis thinner than one voxel snaps to the nearest voxel layer."""
    vs = g.vs
    lo, hi = list(lo), list(hi)
    for a in range(3):
        if lo[a] > hi[a]:
            lo[a], hi[a] = hi[a], lo[a]
        if hi[a] - lo[a] < vs:
            lo[a] = hi[a] = round((lo[a] + hi[a]) / 2 / vs) * vs
    g.rbox(tuple(lo), tuple(hi), mat, val, **kw)


def _shard(g, base, d, L, r, mat='crystal', glow=False, prio=3, tip=0.45, val=0.0):
    """Faceted crystal (hex prism + point) from base along d, length L px, radius r px (two-tone facets)."""
    vs = g.vs
    b = g.to_vox(base)
    length, rad = L / vs, r / vs
    dd = vnorm(d)
    a = (0, 0, 1) if abs(dd[2]) < 0.9 else (1, 0, 0)
    u = vnorm(vcross(dd, a))
    w = vcross(dd, u)
    ext = length + rad + 1
    for i in range(math.floor(b[0] - ext), math.ceil(b[0] + ext) + 1):
        for j in range(math.floor(b[1] - ext), math.ceil(b[1] + ext) + 1):
            for k in range(math.floor(b[2] - ext), math.ceil(b[2] + ext) + 1):
                p = (i - b[0], j - b[1], k - b[2])
                sp = p[0] * dd[0] + p[1] * dd[1] + p[2] * dd[2]
                if sp < -0.3 or sp > length:
                    continue
                pu = p[0] * u[0] + p[1] * u[1] + p[2] * u[2]
                pw = p[0] * w[0] + p[1] * w[1] + p[2] * w[2]
                tipped = sp > length * (1 - tip)
                rr = rad * (length - sp) / (length * tip) if tipped else rad
                if max(abs(pu), abs(pu) * 0.5 + abs(pw) * 0.87) <= max(0.45, rr):
                    v = (0.54 if pu > 0 else 0.32) + (0.1 if pw > 0 else -0.05) + (0.14 if tipped else 0.0) + val
                    g.put(i, j, k, mat, v, glow, prio)


def _robe(g, y_top, y_bot, rt, rb, mat='cloth', val=0.45, folds=7, amp=0.12, phase=0.0, zs=0.8, cz=0.0, hem=1.0,
          power=1.0, seed=0, prio=1, skip=None, vfn=None):
    """Flaring robe from y_top (radius rt) to y_bot (radius rb), elliptical (z × zs), radial folds, torn hem.
    vfn(x, y, z, t 0..1 down the robe, fold −1..1) → value | (mat, v)."""
    vs = g.vs
    sd = g.seed + 509 + seed
    R = max(rt, rb) * (1 + amp) + vs
    nb = folds * 3
    span = max(1e-6, y_top - y_bot)
    for i in g._range(-R, R):
        x = i * vs
        for k in g._range(cz - R * zs, cz + R * zs):
            z = k * vs
            dz = (z - cz) / zs
            rad = math.hypot(x, dz)
            if rad > R:
                continue
            th = math.atan2(dz, x)
            fold = math.cos(folds * th + phase)
            b = int((th + math.pi) / TAU * nb) % nb
            yb = y_bot - hem * (0.55 * h2(b, 1, sd) + 0.45 * (0.5 + 0.5 * fold))
            for j in g._range(yb, y_top):
                y = j * vs
                if y < yb - 1e-6 or y > y_top + 1e-6:
                    continue
                t = min(1.0, max(0.0, (y_top - y) / span))
                tt = t ** power
                r = (rt + (rb - rt) * tt) * (1 + amp * fold * (0.3 + 0.7 * tt))
                if rad > r:
                    continue
                if skip and skip(x, y, z):
                    continue
                v = vfn(x, y, z, t, fold) if vfn else val + 0.12 * fold * (0.4 + 0.6 * tt) - 0.08 * tt
                g._emit((i, j, k), v, mat, False, prio)


def _ering(g, c, rx, rz, r, mat='brass', val=0.6, n=48, glow=False, prio=3, yfn=None, arc=(0.0, 1.0), vfn=None):
    """Elliptical band (rx, rz) around the vertical axis through c; yfn(angle) lifts / tilts it."""
    pts = []
    for q in range(n + 1):
        a = TAU * (arc[0] + (arc[1] - arc[0]) * q / n)
        pts.append((c[0] + rx * math.cos(a), c[1] + (yfn(a) if yfn else 0.0), c[2] + rz * math.sin(a)))
    return g.sweep(pts, r, r, mat, val, vfn=vfn, glow=glow, prio=prio, smooth=False)


def _drip(g, top, L, r=0.42, mat='ink', val=0.5, drop=None, prio=4):
    """Hanging drip: a thin run from `top` down L px ending in a fat glossy drop."""
    x, y, z = top
    g.capsule((x, y, z), (x, y - L, z), r, r * 0.8, mat, val, prio=prio)
    g.blob((x, y - L - (drop or r * 1.4) * 0.6, z), drop or r * 1.45, mat, val + 0.25, prio=prio + 1, top=0.2)


def _surface_pts(g, mats, n, seed=0, region=None, up_min=None):
    """n deterministic exposed surface points [(px point, unit normal)] of mats (optionally filtered)."""
    sd = g.seed + 301 + seed
    surf = []
    for key, nn in g.exposed(mats):
        p = g.px(key)
        if region and not region(*p):
            continue
        if up_min is not None and nn[1] < up_min:
            continue
        surf.append((key, nn))
    if not surf:
        return []
    surf.sort()
    out = []
    for k in range(n):
        key, nn = surf[int(h2(k, 1, sd) * len(surf)) % len(surf)]
        ln = vlen(nn)
        out.append((g.px(key), vmul(nn, 1 / ln) if ln else (0, 1, 0)))
    return out


def _studs(g, mats, n, mat, val=0.55, r=(0.5, 1.0), seed=0, region=None, prio=4, hole=None):
    """Small domes stuck on a surface (barnacles, pustules, spore warts); hole = darker centre value."""
    for k, (p, nn) in enumerate(_surface_pts(g, mats, n, seed, region)):
        rr = r[0] + (r[1] - r[0]) * h2(k, 2, g.seed + seed)
        g.blob(p, (rr, rr * 0.85, rr), mat, val, prio=prio, top=0.2)
        if hole is not None:
            g.dot(vadd(p, vmul(nn, rr * 0.8)), mat, hole, prio=prio + 1)


def _ramps(ctx, table):
    for mats, ramp in table:
        for m in (mats if isinstance(mats, tuple) else (mats,)):
            ctx.set_ramp(m, ramp)


GLOWS = ('core', 'eye', 'rune', 'glow')


# ───────────────────────────── floor02_silk_queen (실잣는 여왕 베셀라) ─────────────────────────────
# Spider queen of the silver mine: a huge glossy black-slate abdomen banded with overlapping plates,
# silver chevrons down the back and a glowing violet hourglass sigil; violet lantern-spots along the
# flanks, spinnerets trailing silver silk to the floor.  Eight long arched legs with silver knee bands,
# the front pair raised in threat; an eight-eyed head under a silver tiara of violet crystal spires,
# curved silver fangs dripping violet venom.

QUEEN_CHITIN = [(8, 9, 13), (18, 20, 27), (32, 35, 46), (52, 56, 72), (82, 88, 110), (120, 128, 152), (170, 178, 200)]
QUEEN_SILVER = [(40, 42, 52), (84, 88, 104), (140, 146, 164), (192, 198, 216), (230, 234, 246), (250, 252, 255)]
QUEEN_VIOLET = [(48, 20, 88), (98, 50, 176), (156, 110, 238), (198, 168, 255), (234, 218, 255), (255, 255, 255)]
QUEEN_WEB = [(96, 98, 112), (150, 154, 170), (200, 204, 218), (232, 234, 244), (250, 250, 255)]


def _queen_abdomen(g: MobGrid, ctx):
    c = (0, 0.6, 0.8)
    g.plates(c, (11.6, 9.0, 13.0), n=6, axis=2, mat='chitin', val=0.4, lift=0.1, ridge=0.9, ridge_mat='metal')
    g.gradient(axis=1, lo=-9, hi=9, amount=0.12, mats=['chitin'])

    def mark(x, y, z, n, m, v):
        if n[1] < 0 or y < 1.5:
            return None
        dz = z - 5.4
        if abs(dz) < 4.4 and abs(x) < 0.6 + 0.75 * abs(dz) and y > 4.0:      # hourglass sigil
            return ('core', 0.4 + 0.15 * abs(dz) / 4.4)
        if abs(dz) < 5.4 and abs(x) < 1.4 + 0.75 * abs(dz) and y > 4.0:      # its silver outline
            return ('metal', 0.7)
        if abs(x) < 1.1 and z < 0.5:                                          # dorsal stripe
            return ('metal', 0.72)
        u = z + abs(x) * 1.0
        if abs(x) < 8.0 and (u % 4.4) < 1.5 and -11 < z < 0.6:               # silver chevrons
            return ('metal', 0.55 + 0.2 * (1 - abs(x) / 8.0))
        return None
    g.paint(mark, ['chitin'])
    # violet lantern-spots along both flanks
    for k in range(5):
        z = -7.5 + 3.8 * k
        for s in (-1, 1):
            p = g.hit((s * 16, 1.4 - 0.2 * k, z), (-s, 0, 0))
            if p:
                g.blob(p, 1.0 if k in (1, 2, 3) else 0.75, 'core', 0.5, prio=6)
    # petiole collar (boss trim): silver ring with runes where the waist meets the thorax
    g.ring((0, 0.2, -11.4), 5.0, 0.8, axis='z', mat='metal', val=0.6)
    g.runes((0, 3.0, -12.4), (0, 0, -1), w=6.0, h=1.6, mat='rune', val=0.4, density=0.8, seed=3)
    # spinnerets at the rear, glowing tips, silk trailing to the floor (ground = y −12)
    for x, y in ((-1.4, -2.2), (1.4, -2.2), (0.0, -3.6)):
        g.cone((x, y, 12.6), (x * 0.2, -0.3, 1), 2.8, 0.9, 'chitin', 0.4, tip_val=0.6)
        g.dot((x * 1.15, y - 0.8, 15.2), 'core', 0.6, prio=5)
    for tx, tz in ((-4.0, 19.0), (5.0, 20.0)):
        g.strands((0, -4.2, 15.0), (tx, -12.0, tz), sag=0.4, mat='web', val=0.85)
    for s in (-1, 1):
        g.strands((s * 9.0, 6.4, -7.0), (s * 11.6, -1.0, 6.0), sag=2.0, mat='web', val=0.8)
        g.strands((s * 6.0, 8.2, 2.0), (s * 10.8, 0.0, 10.0), sag=1.6, mat='web', val=0.75)
    pts = [(s * 10.4, -3.2 + 0.4 * (k % 2), -6 + 2.6 * k) for s in (-1, 1) for k in range(6)]
    g.spikes(pts, lambda i, p: (1 if p[0] > 0 else -1, -0.6, 0.3), 1.8, 0.4, mat='chitin', val=0.35)


def _queen_thorax(g: MobGrid, ctx):
    g.plates((0, 0, 0), (7.4, 4.4, 6.6), n=3, axis=2, mat='chitin', val=0.4, lift=0.12)
    g.blob((0, 2.4, -0.4), (5.4, 2.0, 5.0), 'chitin', 0.5, prio=2, top=0.25)
    g.ring((0, 2.9, -0.4), 4.8, 0.45, axis='y', mat='metal', val=0.62)
    g.runes((0, 8.0, -0.4), (0, 1, 0), w=3.6, h=3.6, mat='rune', val=0.45, density=0.9, seed=5)
    for z in (-3.6, -1.2, 1.2, 3.6):
        for s in (-1, 1):
            g.blob((s * 6.4, -0.6, z), (1.6, 1.5, 1.2), 'chitin', 0.55, prio=2)
            g.ring((s * 6.8, -0.6, z), 1.3, 0.35, axis='x', mat='metal', val=0.55)
    g.spikes([(x, 2.4, -5.2) for x in (-4.0, -2.0, 0.0, 2.0, 4.0)], (0, 1, -0.5), 2.6, 0.55, mat='metal', val=0.5,
             tip_val=0.95)


def _queen_head(g: MobGrid, ctx):
    g.blob((0, 0, 0), (4.4, 3.8, 4.2), 'chitin', 0.42, top=0.18)
    g.blob((0, 1.4, 0.8), (3.8, 2.4, 3.4), 'chitin', 0.5, prio=2)
    for s in (-1, 1):
        g.blob((s * 1.5, -2.2, -3.0), (1.5, 1.9, 1.5), 'chitin', 0.4, prio=2)

    def vm(x, y, z, n, m, v):
        if n[2] >= 0 or z > -1.5:
            return None
        if abs(y - 3.0 + abs(x) * 0.7) < 0.4 and abs(x) < 3.0:
            return ('metal', 0.75)
        return None
    g.paint(vm, ['chitin'])
    g.eyes((1.3, 0.5, -4.0), 1.0, 2.6, val=0.62, socket=0.3)
    g.eyes((1.0, 2.0, -3.6), 0.6, 2.0, val=0.55)
    g.eyes((2.6, 1.3, -3.2), 0.55, 5.2, val=0.5)
    g.eyes((3.1, -0.1, -2.6), 0.45, 6.4, val=0.5)


def _queen_crown(g: MobGrid, ctx):
    _ering(g, (0, -1.6, -0.6), 3.7, 3.1, 0.55, 'metal', 0.6)
    _ering(g, (0, -0.7, -0.6), 3.4, 2.8, 0.4, 'metal', 0.78)
    g.crystals((0, -1.0, -1.4), (0, 1, -0.12), n=3, size=5.8, r=0.95, mat='core', glow=True, spread=0.4, seed=4)
    for k in range(7):
        a = math.pi * (0.08 + 0.84 * k / 6)
        x, z = -math.cos(a) * 3.6, -0.6 - math.sin(a) * 3.0
        L = 2.0 + 1.8 * (1 - abs(k - 3) / 3)
        g.cone((x, -1.0, z), (x * 0.12, 1, -0.1), L, 0.45, 'metal', 0.55, tip_val=0.95)
    for x in (-2.2, 2.2):
        g.dot((x, -1.2, -3.4), 'core', 0.7, prio=5)


def _queen_fangs(g: MobGrid, ctx):
    for s in (-1, 1):
        g.blob((s * 1.5, 1.0, 0.6), (1.4, 1.5, 1.4), 'chitin', 0.42)
        base, d, L, curl = (s * 1.5, 0.3, -0.3), (s * 0.15, -1, -0.45), 4.6, (-s * 0.9, 0.2, 1.4)
        g.horn(base, d, L, 0.85, curl=curl, mat='metal', val=0.42, tip_mat='core', r_tip=0.25)
        tip = vadd(vadd(base, vmul(vnorm(d), L)), curl)
        _drip(g, vadd(tip, (0, -0.3, 0)), 0.8, r=0.3, mat='core', val=0.45)
        g.limb([(s * 3.0, 1.4, 0.6), (s * 3.8, 0.4, -1.4), (s * 3.3, -1.4, -2.2)], [0.6, 0.5, 0.35], 'chitin', 0.45,
               joint_mat='metal', joint_val=0.6)


def _queen_legs(g: MobGrid, ctx):
    gy = -6.4                                   # legs pivot 0.4 blocks above the floor
    angs = (-0.95, -0.35, 0.3, 0.85)            # off the lateral axis; negative = forward (−Z)
    reach = (17.6, 17.0, 16.6, 18.0)
    for k in range(4):
        a = angs[k]
        for s in (-1, 1):
            dx, dz = s * math.cos(a), math.sin(a)
            root = (s * 6.2, 4.2, (-3.6, -1.2, 1.2, 3.6)[k] - 3.2)
            R = reach[k]
            if k == 0:     # front pair raised in threat
                knee = vadd(root, (dx * R * 0.34, 9.6, dz * R * 0.34))
                ankle = vadd(root, (dx * R * 0.72, 8.0, dz * R * 0.72))
                foot = vadd(root, (dx * R * 0.95, 2.0, dz * R * 0.95))
            else:
                knee = vadd(root, (dx * R * 0.4, 7.4, dz * R * 0.4))
                ankle = vadd(root, (dx * R * 0.8, 2.0, dz * R * 0.8))
                foot = vadd(root, (dx * R, gy - root[1], dz * R))

            def lv(t, d, p):
                if t > 0.9:
                    return ('metal', 0.72)
                return 0.36 + 0.16 * (1 - d) + (0.08 if t < 0.34 else 0.0)
            g.limb([root, knee, ankle, foot], [1.9, 1.45, 1.0, 0.4], 'chitin', 0.42, joint_mat='metal',
                   joint_val=0.6, knob=1.2, vfn=lv)
            if k == 0:
                g.dot(foot, 'core', 0.7, prio=6)
            mid = vadd(vmul(root, 0.4), vmul(knee, 0.6))
            g.spikes([mid, vadd(vmul(knee, 0.6), vmul(ankle, 0.4))], (dx * 0.3, 1, dz * 0.3), 1.6, 0.4, mat='chitin',
                     val=0.3)


def floor02_silk_queen(look, name, part, ctx):
    _ramps(ctx, [('chitin', QUEEN_CHITIN), ('metal', QUEEN_SILVER), ('web', QUEEN_WEB), (GLOWS, QUEEN_VIOLET)])
    fn = {'abdomen': _queen_abdomen, 'thorax': _queen_thorax, 'head': _queen_head, 'crown': _queen_crown,
          'fangs': _queen_fangs, 'legs': _queen_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'abdomen': 1.0, 'thorax': 0.7, 'head': 0.5, 'crown': 0.45, 'fangs': 0.45, 'legs': 0.9}[name])
    fn(g, ctx)
    return g


# ───────────────────────────── floor03_mycelium_king (균사의 왕 무르노크) ─────────────────────────────
# Every hypha of the cave knotted into one king: a plum-fleshed fungal trunk ribbed like gills, a royal
# ruff of pale gill frills, a glowing yellow spore heart in the chest webbed with white hyphae, shelf
# fungi stepping up the flanks.  A vast magenta cap studded with glowing spore warts and crowned with a
# ring of small luminous toadstools, hyphae hanging from its rolled lip.  Braided tendril arms ending in
# puffball fists, a root mass spreading over the floor dotted with glowing caps.

MYC_FLESH = [(18, 10, 18), (40, 22, 38), (66, 36, 60), (98, 56, 88), (134, 82, 120), (172, 118, 156), (210, 164, 194)]
MYC_CAP = [(36, 12, 32), (72, 26, 62), (116, 46, 98), (164, 76, 140), (206, 114, 174), (236, 160, 206),
           (252, 208, 232)]
MYC_GILL = [(84, 54, 74), (140, 100, 124), (190, 150, 172), (228, 198, 214), (250, 230, 240)]
MYC_GLOW = [(86, 66, 8), (164, 134, 18), (232, 206, 64), (248, 234, 136), (255, 248, 206), (255, 255, 255)]
MYC_HYPHA = [(120, 96, 112), (176, 150, 166), (220, 200, 212), (242, 230, 238), (255, 250, 252)]
MYC_ROOT = [(16, 10, 14), (34, 20, 30), (56, 34, 50), (82, 52, 74), (112, 76, 100), (146, 108, 132)]


def _myc_cap(g: MobGrid, ctx):
    g.blob((0, -2.6, 0), (17.0, 9.4, 17.0), 'cap', 0.5, lump=0.05, lump_scale=6, cut=lambda x, y, z: y < -2.6,
           vfn=lambda x, y, z, d: 0.36 + 0.36 * (y + 2.6) / 9.4)
    g.ring((0, -2.6, 0), 15.8, 1.7, axis='y', mat='cap', val=0.3)
    g.cylinder((0, -3.6, 0), (0, -2.8, 0), 14.6, mat='gill', val=0.45,
               vfn=lambda t, rad, p: 0.3 + (0.3 if rad > 0.8 and math.cos(36 * math.atan2(p[2], p[0])) > 0.3 else 0))
    g.mottle(['cap'], 0.08, 4.0)
    for k in range(13):
        a = TAU * k / 13 + 0.4 * h2(k, 3, g.seed)
        rr = (4.5 if k % 3 == 0 else 9.5 if k % 3 == 1 else 13.0) + 1.2 * h2(k, 4, g.seed)
        p = g.hit((math.cos(a) * rr, 12.0, math.sin(a) * rr), (0, -1, 0))
        if p:
            s = 1.0 + 0.9 * h2(k, 5, g.seed)
            g.blob(p, (s, 0.7, s), 'core', 0.5, prio=5)
    for k in range(6):
        a = TAU * (k + 0.5) / 6
        p = g.hit((math.cos(a) * 4.6, 12.0, math.sin(a) * 4.6), (0, -1, 0))
        if p:
            g.mushroom(p, (math.cos(a) * 0.35, 1, math.sin(a) * 0.35), stem=2.4 + 0.8 * (k % 2), cap_r=1.5,
                       mat='core', val=0.45, stem_mat='gill', spots=0.0)
    p = g.hit((0, 12.0, 0), (0, -1, 0))
    if p:
        g.mushroom(p, (0, 1, 0), stem=3.6, cap_r=1.9, mat='core', val=0.5, stem_mat='gill', spots=0.0)
    for k in range(12):
        a = TAU * (k + 0.3) / 12
        x, z = math.cos(a) * 15.2, math.sin(a) * 15.2
        L = 2.0 + 2.6 * h2(k, 6, g.seed)
        g.capsule((x, -3.8, z), (x, -3.8 - L, z), 0.4, 0.35, 'web', 0.6, prio=3)
        g.dot((x, -4.4 - L, z), 'core', 0.6, prio=4)


def _myc_torso(g: MobGrid, ctx):
    g.blob((0, 2.0, 0), (9.6, 7.8, 6.8), 'skin', 0.52, lump=0.12, lump_scale=4)
    g.blob((0, -5.0, 0.2), (7.6, 6.0, 6.0), 'skin', 0.48, lump=0.12, lump_scale=4, seed=2)
    g.bands(['skin'], axis=0, period=2.4, width=0.8, amount=-0.12)
    g.carve_blob((0, 2.2, -6.6), (3.4, 3.4, 2.6))
    g.blob((0, 2.2, -4.6), 2.7, 'core', 0.45, prio=4)
    g.blob((0, 2.2, -5.6), 1.2, 'core', 0.9, prio=5)
    g.ring((0, 2.2, -5.8), 3.6, 0.9, axis='z', mat='gill', val=0.55)
    for k in range(5):
        a = TAU * k / 5 + 0.5
        g.branch((math.cos(a) * 4.2, 2.2 + math.sin(a) * 4.2, -5.6), (math.cos(a), math.sin(a), 0.2), 4.0, 0.4,
                 depth=1, fork=2, spread=0.7, mat='core', val=0.3, seed=k)
    g.cracks(['skin'], mat='gill', width=0.016, scale=4.0, val=0.62)
    for k, (x, y, z) in enumerate(((-8.4, -3.0, 1.0), (-9.2, 1.4, 0.4), (8.6, -1.4, 0.8), (7.2, -5.6, 2.2),
                                   (-4.0, -6.0, 5.4))):
        s = 1 if x > 0 else -1
        g.blob((x + s * 1.2, y, z), (2.6, 0.75, 2.2), 'cap', 0.55, prio=3, top=0.3)
        g.blob((x + s * 1.2, y - 0.6, z), (2.2, 0.4, 1.8), 'gill', 0.5, prio=2)
    for k in range(16):
        a = TAU * k / 16
        if math.sin(a) < -0.55:
            continue
        p = (math.cos(a) * 8.6, 7.8 + 0.6 * (k % 2), math.sin(a) * 6.0)
        g.blob(p, (2.3, 1.5, 2.3), 'gill', 0.45 + 0.15 * (k % 2), prio=3)
    _studs(g, ['skin'], 9, 'core', 0.55, r=(0.5, 0.9), seed=1, region=lambda x, y, z: y < 6)


def _myc_head(g: MobGrid, ctx):
    g.blob((0, 0, 0), (4.3, 4.2, 4.0), 'skin', 0.45, lump=0.08)
    g.blob((0, 1.5, -3.0), (3.8, 1.0, 1.5), 'cap', 0.5, prio=2)
    g.eyes((1.5, 0.0, -3.7), 1.0, 3.2, val=0.72, socket=0.45)
    g.carve(lambda x, y, z: abs(x) < 1.8 and -2.6 < y < -1.8 and z < -3.0)
    g.rbox((-1.8, -2.6, -3.4), (1.8, -1.8, -3.0), 'void', 0.1)
    g.cloth([(-3.0, -2.8, -3.4), (3.0, -2.8, -3.4)], 3.4, 'gill', 0.5, tatter=0.6, normal=(0, 0, -1), thick=1)
    for x in (-2.2, -0.6, 1.0, 2.4):
        L = 1.4 + 1.2 * h2(int(x * 10), 7, g.seed)
        g.capsule((x, -5.8, -3.5), (x, -5.8 - L, -3.5), 0.3, 0.3, 'web', 0.6)
        g.dot((x, -6.2 - L, -3.5), 'core', 0.6, prio=4)
    for p in ((-2.8, -0.8, -3.0), (2.6, -1.0, -3.1), (-3.4, 1.0, -2.0), (3.2, 0.6, -2.2)):
        g.dot(p, 'core', 0.5, prio=5)


def _myc_arm(g: MobGrid, ctx):
    o = ctx.out
    g.blob((o * 0.4, -1.6, 0), (4.0, 3.6, 3.8), 'skin', 0.45, lump=0.15)
    for k in range(3):
        ph = TAU * k / 3
        pts = [(math.cos(ph + t * 2.6) * 1.6, -2.0 - t * 15.5, math.sin(ph + t * 2.6) * 1.6)
               for t in (i / 6 for i in range(7))]
        g.sweep(pts, 1.5, 1.2, 'skin', 0.4 + 0.06 * k)
    g.blob((0, -19.4, -0.4), (3.4, 3.2, 3.2), 'skin', 0.45, lump=0.2)
    for k, (x, y, z, r) in enumerate(((-1.8, -18.0, -2.4, 1.4), (1.9, -19.8, -2.0, 1.2), (0.2, -21.6, -1.6, 1.3),
                                      (o * 2.6, -17.4, 1.0, 1.1))):
        g.blob((x, y, z), r, 'gill', 0.6, prio=3, top=0.25)
        g.dot((x, y + r * 0.6, z - r * 0.6), 'core', 0.7, prio=4)
    for k in range(3):
        a = -0.8 + 0.8 * k
        p0 = (math.sin(a) * 2.0, -21.4, -1.0)
        g.tentacle(p0, vadd(p0, (math.sin(a) * 1.6, -1.8, -1.2)), vadd(p0, (math.sin(a) * 2.6, -2.4, -2.8)),
                   vadd(p0, (math.sin(a) * 2.2, -1.2, -4.0)), 0.8, 0.3, 'skin', 0.45, suckers=False, tip_mat='core',
                   glow_tip=True)
    for y in (-6.0, -10.5):
        g.blob((o * 2.6, y, 0.6), (1.8, 0.6, 2.0), 'cap', 0.55, prio=3, top=0.3)
    g.cracks(['skin'], mat='gill', width=0.016, scale=3.6, val=0.62)


def _myc_roots(g: MobGrid, ctx):
    gy = -9.6
    g.blob((0, 2.0, 0.2), (7.4, 6.4, 6.2), 'skin', 0.42, lump=0.15)
    for k in range(8):
        a = TAU * (k + 0.5) / 8 + 0.25 * (h2(k, 1, g.seed) - 0.5)
        dx, dz = math.cos(a), math.sin(a)
        R = 13.2 + 1.6 * h2(k, 2, g.seed)
        pts = [(dx * 3.0, 1.0, dz * 3.0), (dx * 7.0, -3.8, dz * 7.0), (dx * 10.4, gy + 1.2, dz * 10.4),
               (dx * R, gy + 0.5, dz * R)]
        g.sweep(pts, 2.3, 0.6, 'bark', 0.42)
        if k % 2 == 0:
            g.mushroom((dx * (R - 2.6), gy + 1.0, dz * (R - 2.6)), (dx * 0.3, 1, dz * 0.3), stem=1.6, cap_r=1.2,
                       mat='core', val=0.45, stem_mat='gill', spots=0.0)
    g.cracks(['bark', 'skin'], mat='core', width=0.014, scale=4.4, val=0.4)
    g.cracks(['bark', 'skin'], mat='gill', width=0.016, scale=3.4, val=0.55, seed=3)


def floor03_mycelium_king(look, name, part, ctx):
    _ramps(ctx, [(('skin', 'flesh'), MYC_FLESH), ('cap', MYC_CAP), ('gill', MYC_GILL), (GLOWS, MYC_GLOW),
                 ('web', MYC_HYPHA), ('bark', MYC_ROOT)])
    fn = {'torso': _myc_torso, 'cap': _myc_cap, 'head': _myc_head, 'arm_left': _myc_arm, 'arm_right': _myc_arm,
          'roots': _myc_roots}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.8, 'cap': 1.1, 'head': 0.5, 'roots': 1.0}.get(name, 0.75))
    fn(g, ctx)
    return g


# ───────────────────────────── floor04_floodwarden (수문의 망령 오스릭) ─────────────────────────────
# The lock-keeper drowned with his sluice gate: a verdigris-eaten brass diving helmet with a barred front
# porthole where two teal eyes burn, a sodden keeper's longcoat with brass buttons and fringed epaulettes,
# a ring of keys at the belt; the coat skirt rots into ghostly teal tatters that drip.  Barnacles crust
# everything, kelp hangs off him.  Left hand: a brass storm lantern with a gold flame; right hand: a huge
# anchor-shaped sluice key.

FLOOD_COAT = [(6, 16, 18), (12, 30, 34), (22, 48, 52), (36, 72, 74), (56, 100, 98), (86, 136, 130), (130, 178, 168)]
FLOOD_PATINA = [(18, 56, 50), (36, 98, 86), (68, 146, 126), (112, 192, 168), (176, 230, 210)]
FLOOD_BRASS = [(28, 22, 10), (60, 46, 22), (100, 80, 38), (146, 118, 60), (192, 162, 94), (228, 204, 140),
               (248, 236, 196)]
FLOOD_TEAL = [(16, 56, 56), (34, 130, 122), (84, 204, 184), (160, 242, 226), (226, 255, 248), (255, 255, 255)]
FLOOD_GOLD = [(96, 64, 12), (176, 126, 32), (234, 200, 110), (250, 228, 160), (255, 246, 214), (255, 255, 255)]
FLOOD_BARNACLE = [(46, 50, 48), (92, 96, 90), (142, 144, 134), (192, 192, 178), (228, 226, 212)]
FLOOD_SKIN = [(30, 48, 52), (58, 84, 86), (92, 122, 120), (130, 160, 154), (172, 198, 190)]
FLOOD_KELP = [(12, 24, 12), (24, 46, 22), (40, 72, 34), (62, 100, 48), (92, 132, 66)]


def _kelp(g, top, L, seed=0, r=0.35):
    sd = g.seed % 97 + seed
    x, y, z = top
    pts = [(x + 0.6 * math.sin(k * 1.7 + sd), y - L * k / 4, z + 0.4 * math.cos(k * 1.3 + sd)) for k in range(5)]
    g.vine(pts, r=r, mat='leaf', val=0.4, leaves=0.5, leaf_mat='leaf', leaf_size=0.8, seed=seed)


def _flood_head(g: MobGrid, ctx):
    g.blob((0, 0.6, 0), (4.2, 4.2, 4.2), 'brass', 0.5, top=0.22)
    g.cylinder((0, -4.4, 0), (0, -2.8, 0), 4.6, 4.3, 'brass', 0.42)
    g.rivets([(math.cos(TAU * k / 10) * 4.6, -3.6, math.sin(TAU * k / 10) * 4.5) for k in range(10)], 'brass', 0.8)
    # barred front porthole, teal eyes in the murk behind the glass
    g.carve_blob((0, 0.4, -4.4), (2.6, 2.6, 1.8))
    g.cylinder((0, 0.4, -3.2), (0, 0.4, -2.8), 2.4, mat='water', val=0.25)
    g.eyes((0.0, 0.7, -3.3), 0.6, 1.9, val=0.75)
    g.ring((0, 0.4, -3.9), 2.6, 0.6, axis='z', mat='brass', val=0.7)
    _box(g, (-0.25, -1.9, -3.9), (0.25, 2.7, -3.6), 'brass', 0.62)
    _box(g, (-2.2, 0.15, -3.9), (2.2, 0.65, -3.6), 'brass', 0.62)
    for s in (-1, 1):
        g.ring((s * 4.0, 0.6, 0.0), 1.4, 0.45, axis='x', mat='brass', val=0.66)
        g.blob((s * 4.0, 0.6, 0.0), (0.4, 1.0, 1.0), 'eye', 0.3, prio=4)
    g.cylinder((0, 4.4, 0.6), (0, 5.6, 0.6), 0.8, mat='brass', val=0.6)
    g.ring((0, 5.6, 0.6), 0.9, 0.35, axis='y', mat='brass', val=0.75)
    g.capsule((2.0, 4.0, 2.4), (3.0, 4.8, 4.2), 0.5, 0.5, 'brass', 0.5)
    g.mottle(['brass'], 0.1, 1.6)
    _patina(g, 0.45)
    _studs(g, ['brass', 'patina'], 9, 'stone', 0.55, r=(0.45, 0.85), seed=2, hole=0.12,
           region=lambda x, y, z: z > -2.6 or y < -2.0)
    for x, z in ((-3.4, -2.0), (3.0, 1.6), (-1.2, 3.8)):
        _kelp(g, (x, -4.2, z), 3.2, seed=int(x * 7) % 13)


def _flood_torso(g: MobGrid, ctx):
    # hunched, sunken-chested coat: broad bowed shoulders over a narrow waist, standing collar behind
    g.blob((0, 1.4, 0.3), (5.6, 5.0, 3.8), 'cloth', 0.45)
    g.blob((0, -4.0, 0.2), (4.2, 3.6, 3.2), 'cloth', 0.42)
    for s in (-1, 1):
        g.blob((s * 4.6, 4.4, -0.2), (2.9, 2.4, 3.2), 'cloth', 0.5)
    for k in range(5):
        y = 5.2 + 0.8 * k
        _ering(g, (0, y, 0.6), 5.4 + 0.18 * k, 4.4 + 0.25 * k, 0.5, 'cloth', 0.5 + 0.03 * k, arc=(0.0, 0.5), n=36)

    def lapel(x, y, z, n, m, v):
        if n[2] < 0 and z < -2.8 and y > -1.0 and abs(x) < 3.4 and abs(x) > (y + 1.0) * 0.45:
            return v + 0.14
        return None
    g.paint(lapel, ['cloth'])
    for y in (3.2, 0.8, -1.6, -4.0):
        for s in (-1, 1):
            p = g.hit((s * 1.7, y, -9), (0, 0, 1))
            if p:
                g.blob(p, 0.55, 'brass', 0.72, prio=4)
    # fringed brass epaulettes (boss trim)
    for s in (-1, 1):
        g.rbox((s * 3.4, 5.4, -2.6), (s * 7.4, 6.6, 2.6), 'brass', 0.58, bevel=0.5)
        for k in range(6):
            x = s * (3.8 + 0.7 * k)
            g.capsule((x, 5.4, -2.4), (x, 3.4 - 0.3 * (k % 2), -2.6), 0.3, 0.3, 'brass', 0.55)
    # belt and the ring of sluice keys
    _ering(g, (0, -5.0, 0.2), 4.2, 3.3, 0.75, 'leather', 0.38, n=40)
    g.rbox((-1.0, -5.9, -3.9), (1.0, -4.1, -3.3), 'brass', 0.7, bevel=0.2)
    g.ring((2.6, -6.4, -3.6), 1.0, 0.3, axis='z', mat='brass', val=0.65)
    for k, dx in enumerate((-0.7, 0.0, 0.8)):
        x = 2.6 + dx
        g.capsule((x, -7.0, -3.7), (x + dx * 0.4, -9.4, -3.8), 0.3, 0.3, 'brass', 0.6)
        _box(g, (x + dx * 0.4, -9.6, -3.9), (x + dx * 0.4 + 0.8, -8.8, -3.7), 'brass', 0.55)
    g.cloth([(-6.6, 5.8, 0.8), (0, 6.2, 3.8), (6.6, 5.8, 0.8)], 5.2, 'cloth', 0.38, tatter=0.6, normal=(0, 0, 1),
            thick=1, seed=3)
    _patina(g, 0.35, seed=1)
    g.streaks('water', ['cloth'], density=0.18, length=(1.5, 4.0), val=0.55)
    _studs(g, ['cloth'], 7, 'stone', 0.55, r=(0.45, 0.8), seed=4, hole=0.12)
    _kelp(g, (-4.6, 3.8, -3.4), 5.0, seed=5)


def _flood_coat(g: MobGrid, ctx):
    def cv(x, y, z, t, fold):
        if y < -11.6:
            return ('eye', 0.05)                               # ghostly glowing tatter tips
        if t > 0.6:
            return 0.6 + 0.3 * (t - 0.6) / 0.4 + 0.1 * fold     # thinning, translucent-looking lower coat
        return 0.46 + 0.13 * fold - 0.1 * t
    _robe(g, 3.6, -8.4, 3.6, 6.6, 'cloth', folds=7, amp=0.26, zs=0.76, hem=5.2, seed=1, power=1.4,

          skip=lambda x, y, z: z < -2.0 and abs(x) < 0.6 + (3.6 - y) * 0.11, vfn=cv)
    for k, y in enumerate((2.0, -0.8, -3.6)):
        for s in (-1, 1):
            p = g.hit((s * (0.9 + (3.6 - y) * 0.11 + 0.7), y, -12), (0, 0, 1))
            if p:
                g.blob(p, 0.5, 'brass', 0.7, prio=4)
    g.streaks('water', ['cloth'], density=0.16, length=(2.0, 5.0), val=0.55, seed=2)
    _studs(g, ['cloth'], 10, 'stone', 0.55, r=(0.5, 0.95), seed=6, hole=0.12, region=lambda x, y, z: y < -2)
    for k, a in enumerate((0.6, 1.9, 2.9, 4.1, 5.3)):
        p = (math.cos(a) * 6.6, -10.4 - 0.8 * (k % 2), math.sin(a) * 4.8)
        _drip(g, p, 1.2 + 0.6 * (k % 2), r=0.35, mat='eye', val=0.12)

    for x, z in ((-5.2, 2.0), (4.6, 3.0), (5.6, -2.2)):
        _kelp(g, (x, 1.0, z), 7.0, seed=int(abs(x) * 5) % 11)


def _flood_arm(g: MobGrid, ctx):
    g.capsule((0, -0.6, 0), (0, -6.6, 0.2), 1.9, 1.7, 'cloth', 0.45)
    g.capsule((0, -6.6, 0.2), (0, -10.2, -0.4), 1.7, 1.6, 'cloth', 0.42)
    g.rbox((-1.9, -10.8, -2.0), (1.9, -9.4, 1.6), 'brass', 0.52, bevel=0.4)
    g.cloth([(-1.9, -10.8, -2.1), (1.9, -10.8, -2.1)], 1.4, 'cloth', 0.36, tatter=0.7, seed=1 if ctx.out > 0 else 2)
    g.blob((0, -12.2, -0.4), (1.3, 1.4, 1.2), 'skin', 0.45)
    for x in (-0.7, 0.0, 0.7):
        g.capsule((x, -12.8, -0.9), (x, -13.8, -1.2), 0.35, 0.3, 'skin', 0.5)
    _patina(g, 0.5, seed=3)
    _studs(g, ['cloth'], 3, 'stone', 0.55, r=(0.4, 0.6), seed=7, hole=0.12)
    g.streaks('water', ['cloth'], density=0.2, length=(1.0, 3.0), val=0.55, seed=4)


def _flood_lantern(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    top = hy - 0.4
    g.ring((hx, top + 0.6, hz), 1.1, 0.3, axis='x', mat='brass', val=0.62)
    g.cone((hx, top - 1.8, hz), (0, 1, 0), 1.6, 2.3, 'brass', 0.5, tip_val=0.7)
    g.cylinder((hx, top - 2.3, hz), (hx, top - 1.7, hz), 2.6, mat='brass', val=0.55)
    g.cylinder((hx, top - 6.8, hz), (hx, top - 2.3, hz), 1.9, mat='core',
               vfn=lambda t, rad, p: 0.85 - 0.45 * rad + 0.1 * (1 - abs(t - 0.45) * 2))
    for k in range(4):
        a = TAU * (k + 0.5) / 4
        x, z = hx + math.cos(a) * 2.05, hz + math.sin(a) * 2.05
        g.capsule((x, top - 6.8, z), (x, top - 2.3, z), 0.35, 0.35, 'brass', 0.5)
    g.ring((hx, top - 4.6, hz), 2.05, 0.3, axis='y', mat='brass', val=0.55)
    g.cylinder((hx, top - 7.6, hz), (hx, top - 6.6, hz), 2.5, mat='brass', val=0.45)
    _patina(g, 0.4, seed=4)
    _drip(g, (hx + 1.2, top - 7.8, hz - 0.6), 1.0, r=0.3, mat='water', val=0.6)


def _flood_anchor(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    g.ring((hx, hy, hz + 3.6), 2.4, 0.7, axis='x', mat='brass', val=0.56)          # key bow behind the fist
    g.cylinder((hx, hy, hz + 1.2), (hx, hy, hz - 19.6), 0.95, mat='brass', val=0.5)
    for z in (hz - 1.6, hz - 9.0):
        g.ring((hx, hy, z), 1.25, 0.45, axis='z', mat='brass', val=0.68)
    _box(g, (hx + 0.6, hy - 0.7, hz - 14.6), (hx + 3.8, hy + 0.7, hz - 10.6), 'brass', 0.55, bevel=0.2)
    g.carve(lambda x, y, z: x > hx + 2.0 and abs(z - (hz - 12.6)) < 0.6)
    g.carve(lambda x, y, z: x > hx + 3.0 and abs(z - (hz - 11.2)) < 0.5)
    C = (hx, hy, hz - 20.4)
    g.blob(C, (1.4, 1.6, 1.4), 'brass', 0.5)
    for s in (-1, 1):
        pts = [C, (hx, hy + s * 3.4, hz - 21.2), (hx, hy + s * 5.4, hz - 18.4), (hx, hy + s * 5.6, hz - 15.4)]
        g.sweep(pts, 1.0, 0.6, 'brass', 0.5, sq=(0.8, 1, 1))
        g.blob((hx, hy + s * 5.4, hz - 15.4), (0.7, 1.6, 1.3), 'brass', 0.6, prio=3)
        g.cone((hx, hy + s * 5.6, hz - 14.8), (0, s * 0.3, 1), 1.8, 0.7, 'brass', 0.55, tip_val=0.8)
    g.mottle(['brass'], 0.1, 1.4)
    _patina(g, 0.55, seed=5)
    _studs(g, ['brass', 'patina'], 10, 'stone', 0.55, r=(0.4, 0.75), seed=8, hole=0.12)
    g.chain([(hx, hy - 2.0, hz + 3.6), (hx + 0.6, hy - 3.6, hz + 0.6), (hx + 0.4, hy - 2.0, hz - 5.0),
             (hx, hy - 1.2, hz - 8.0)], 1.0, 'iron', 0.45)
    _kelp(g, (hx, hy - 1.4, hz - 20.4), 3.6, seed=9)
    g.rbox((hx - 0.4, hy - 0.4, hz - 2.0), (hx + 0.4, hy + 0.4, hz - 1.0), 'eye', 0.4, prio=5)


def floor04_floodwarden(look, name, part, ctx):
    _ramps(ctx, [('cloth', FLOOD_COAT), ('brass', FLOOD_BRASS), ('patina', FLOOD_PATINA),
                 (('eye', 'rune', 'glow'), FLOOD_TEAL), ('core', FLOOD_GOLD), ('stone', FLOOD_BARNACLE),
                 ('skin', FLOOD_SKIN), ('leaf', FLOOD_KELP)])
    fn = {'torso': _flood_torso, 'coat': _flood_coat, 'head': _flood_head, 'lantern': _flood_lantern,
          'arm_left': _flood_arm, 'arm_right': _flood_arm, 'anchor_key': _flood_anchor}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.55, 'coat': 0.7, 'head': 0.5, 'lantern': 0.45, 'anchor_key': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


#@@NEXT@@

DESIGNS = {
    'floor01_moss_warden': floor01_moss_warden,
    'floor02_silk_queen': floor02_silk_queen,
    'floor03_mycelium_king': floor03_mycelium_king,
    'floor04_floodwarden': floor04_floodwarden,
}
