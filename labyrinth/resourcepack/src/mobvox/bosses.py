"""Voxel boss designs (floor 1–10 bosses).  See README.md (tools: voxel/mob_kit.py).

Pilot design (reference for the boss designer): floor01_moss_warden.
Coordinates: part px, origin = the part's pivot, front = −Z, model −X = the boss's left.
Bosses: budget 3000 elements in total, ≤ 720 per part; the atlas pulses over 8 frames, so give every
boss glowing parts (core / eyes / runes / veins) — glow materials: glow, eye, core, rune, lava.
"""
from __future__ import annotations

import math

from ..voxel.mob_kit import MobGrid, fbm3  # noqa: F401

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


DESIGNS = {
    'floor01_moss_warden': floor01_moss_warden,
}
