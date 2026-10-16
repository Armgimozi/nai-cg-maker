"""Voxel mob designs — mimics (미믹 · 금테 미믹 · 새끼 미믹), the treasure chests that bite.  See README.md.

A mimic must read at a glance as "a treasure chest with teeth": the vanilla-chest silhouette (14×10 body +
14×5 lid, warm plank wood with a darker frame, metal corner caps and a hanging latch), a zig-zag of
bone-white teeth standing just proud of the front and side faces of BOTH halves (so the bite shows even
with the lid shut), a dark red mouth inside with a long red tongue lolling over the front lip, two small
glowing eyes deep inside, and a few coins on the mouth floor.

  chest_mimic  — plank wood + iron (floors 1–5)
  gilded_mimic — dark mahogany + gold bands, a ruby on the latch, red eyes, more coins (floors 6–10)
  mimic_whelp  — the small companion: chest_mimic's look on coarser voxels (YAML scale 0.6)

Parts (YAML: body box pivot = its centre · lid slab pivot = the hinge at the body's top back edge · tongue
pivot = the front lip, hanging down): body = the lower jaw, lid = the upper jaw (RigMath anim `lid` lifts it
around the hinge), tongue = a pendulum (anim tail).  Coordinates: part px, origin = the part's pivot,
front = −Z, model −X = the mob's left (the tongue hangs on that side, clear of the centre latch).
"""
from __future__ import annotations

import math  # noqa: F401

from ..util import h2
from ..voxel.palette import _r

GLOW_MATS = ('glow', 'eye', 'core', 'rune', 'lava')

# ── colour ramps (dark → light) ──
CHEST_WOOD = [(28, 16, 7), (52, 31, 13), (82, 51, 21), (114, 74, 32), (146, 100, 46), (176, 126, 62), (204, 154, 86),
              (228, 184, 118)]
GILDED_WOOD = [(16, 6, 5), (34, 13, 9), (56, 22, 14), (82, 34, 21), (110, 48, 30), (138, 64, 40), (166, 84, 52)]
IRON = [(14, 14, 18), (30, 31, 36), (52, 53, 60), (80, 81, 90), (112, 113, 122), (150, 151, 160), (192, 193, 200)]
GOLD = [(58, 32, 8), (106, 66, 16), (160, 110, 30), (210, 160, 54), (240, 200, 96), (255, 232, 160), (255, 248, 214)]
TOOTH = [(118, 106, 82), (176, 166, 138), (216, 208, 184), (238, 234, 218), (252, 250, 242)]
MOUTH = [(6, 1, 3), (24, 4, 8), (52, 10, 16), (86, 22, 28), (122, 42, 46)]
FLESH = [(66, 8, 16), (118, 18, 30), (170, 36, 48), (210, 66, 76), (236, 112, 118), (250, 166, 166)]
EYE_AMBER = [(150, 84, 8), (232, 160, 30), (255, 212, 84), (255, 238, 160), (255, 252, 226), (255, 255, 255)]
EYE_RED = [(120, 16, 8), (206, 44, 20), (255, 98, 44), (255, 170, 110), (255, 224, 196), (255, 255, 255)]
RUBY = [(60, 4, 10), (120, 10, 24), (190, 24, 44), (236, 70, 86), (255, 150, 160), (255, 220, 224)]

W, H, D = 7.0, 5.0, 7.0          # body half extents (px): 14 × 10 × 14, like a vanilla chest
T = 1.5                          # wall thickness
LID_H, LID_D = 5.0, 14.0         # lid height / depth (px) — hinge at z = 0, front at z = −14
TONGUE_X = -2.5                  # tongue on the mob's left (model −X), clear of the latch at x = 0
OUT = 0.5                        # teeth stand this far proud of the faces (zig-zag shows with the lid shut)


def _ramps(ctx, table):
    for mat, cols in table.items():
        ctx.set_ramp(mat, _r(cols, 11) if mat in GLOW_MATS else cols)


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


def _variant(ctx):
    gilded = ctx.mid == 'gilded_mimic'
    return {
        'gilded': gilded,
        'metal': 'gold' if gilded else 'iron',
        'whelp': ctx.mid == 'mimic_whelp',
    }


def _wood_faces(g, x0, x1, y0, y1, z0, z1, grooves_y=(), grooves_x=(), frame=1.0):
    """Plank look on the outer faces of a box: a darker frame round every face, plank grooves, grain."""
    def f(x, y, z, n, m, v):
        if m != 'wood':
            return None
        on_x = abs(x - x0) < 0.3 or abs(x - x1) < 0.3
        on_z = abs(z - z0) < 0.3 or abs(z - z1) < 0.3
        on_y = abs(y - y0) < 0.3 or abs(y - y1) < 0.3
        if not (on_x or on_z or on_y):
            return None
        near = 0
        if not on_x and (x - x0 < frame or x1 - x < frame):
            near += 1
        if not on_y and (y - y0 < frame or y1 - y < frame):
            near += 1
        if not on_z and (z - z0 < frame or z1 - z < frame):
            near += 1
        if near:
            return 0.26
        if (on_x or on_z) and any(abs(y - gy) < 0.3 for gy in grooves_y):
            return v - 0.17
        if on_y and any(abs(x - gx) < 0.3 for gx in grooves_x):
            return v - 0.15
        return None
    g.paint(f, ['wood'])
    g.mottle(['wood'], amount=0.07, scale=2.5)


def _rivets(g, pts, mat, val=0.75):
    for p in pts:
        g.dot(p, mat, val, prio=5)


# ───────────────────────────── body (lower jaw) ─────────────────────────────

def _body(g, ctx, v):
    metal = v['metal']
    g.rbox((-W, -H, -D), (W, H, D), 'wood', 0.52, bevel=0.5)
    # the mouth: hollow from the rim down to y = −1, inner walls + floor lined with dark flesh
    g.carve(lambda x, y, z: abs(x) <= W - T and abs(z) <= D - T and y >= -1.0)
    g.paint(lambda x, y, z, n, m, val: ('mouth', 0.28 + 0.12 * max(0.0, (y + 1) / 6))
            if (abs(x) <= W - T + 0.6 and abs(z) <= D - T + 0.6 and y < H - 0.2) else None, ['wood'])
    # gullet: a dark hole at the back of the mouth floor
    g.carve_blob((0.8, -1.3, 2.6), (2.6, 1.3, 2.1))
    g.blob((0.8, -1.5, 2.6), (2.8, 1.4, 2.3), 'mouth', 0.06, prio=0, top=0.0, cut=lambda x, y, z: y > -1.0)
    _wood_faces(g, -W, W, -H, H, -D, D, grooves_y=(-1.7, 1.6))
    # metal: corner caps on the four vertical edges, a band round the foot, rivets
    for sx in (-1, 1):
        for sz in (-1, 1):
            _box(g, (sx * (W - 1.6), -H - 0.2, sz * (D + 0.5)), (sx * (W + 0.5), H - 0.2, sz * D), metal, 0.55, prio=3)
            _box(g, (sx * (W + 0.5), -H - 0.2, sz * (D - 1.6)), (sx * W, H - 0.2, sz * (D + 0.5)), metal, 0.55, prio=3)
    band_y = (-H + 0.6, -H + 1.6)
    _box(g, (-W - 0.5, band_y[0], -D - 0.5), (W + 0.5, band_y[1], -D), metal, 0.48, prio=3)
    _box(g, (-W - 0.5, band_y[0], D), (W + 0.5, band_y[1], D + 0.5), metal, 0.48, prio=3)
    for sx in (-1, 1):
        _box(g, (sx * W, band_y[0], -D - 0.5), (sx * (W + 0.5), band_y[1], D + 0.5), metal, 0.48, prio=3)
    if not v['whelp']:
        _rivets(g, [(x, -H + 1.0, -D - 0.5) for x in (-4.0, -1.5, 1.5, 4.0)], metal)
        _rivets(g, [(s * (W + 0.5), -H + 1.0, z) for s in (-1, 1) for z in (-3.5, 0.0, 3.5)], metal)
    # lower teeth: a row standing just proud of the front face (gap on the left for the tongue) + the sides
    for k, x in enumerate((-6.3, -4.7, 1.5, 3.1, 4.7, 6.3)):
        fang = abs(x) > 6
        g.cone((x, H - 0.6, -D - OUT), (0, 1, -0.12), 3.3 if fang else 2.5 + 0.3 * h2(k, 1, 7), 0.75 if fang else 0.65,
               'tooth', 0.55, 0.95, prio=4)
    for s in (-1, 1):
        for k, z in enumerate((-4.6, -2.0, 0.6, 3.0)):
            g.cone((s * (W + OUT), H - 0.6, z), (s * 0.12, 1, 0), 2.3 - 0.3 * k, 0.6, 'tooth', 0.55, 0.95, prio=4)
    # two small glowing eyes deep inside, on the back wall under the hinge, with dark brows
    eye_r = 1.1 if not v['whelp'] else 1.3
    for s in (-1, 1):
        g.eye((s * 2.5, 2.6, D - T - 0.2), eye_r, val=0.5, socket=0.45, socket_mat='mouth', facing=(0, -0.2, -1),
              slit=not v['whelp'])
        _box(g, (s * 1.0, 4.0, D - T - 0.8), (s * 3.9, 4.4, D - T), 'mouth', 0.02, prio=6)      # scowling brow
    # tongue root: from the gullet along the floor, up over the front lip (the hanging tongue part goes on)
    g.sweep([(0.4, -0.7, 2.4), (-1.2, -0.6, -1.4), (TONGUE_X, 0.6, -4.8), (TONGUE_X, 3.6, -6.6), (TONGUE_X, 4.7, -7.5)],
            1.7, 1.5, 'flesh', 0.5, sq=(1.0, 0.5, 1.0), prio=3,
            vfn=lambda t, d, p: 0.4 + 0.16 * t - (0.16 if abs(p[0] - TONGUE_X) < 0.3 and d > 0.4 else 0.0))
    # treasure in the mouth: coins (and a gem on the gilded one)
    coins = [(3.0, -0.75, 1.2), (3.6, -0.25, 1.4), (3.4, -0.75, -1.6), (1.8, -0.75, -3.4)]
    if v['gilded']:
        coins += [(-3.6, -0.75, 2.6), (-4.0, -0.25, 2.2), (-3.2, -0.75, -0.4), (3.2, 0.25, 1.0)]
    for k, c in enumerate(coins):
        g.cylinder((c[0], c[1] - 0.25, c[2]), (c[0], c[1] + 0.25, c[2]), 1.05, None, 'gold', 0.38 + 0.1 * (k % 2), prio=4)
    if v['gilded']:
        g.blob((-3.0, 0.0, -3.2), (0.9, 0.9, 0.9), 'ruby', 0.6, prio=5)
    if v['whelp']:
        g.light_mul = 0.85


# ───────────────────────────── lid (upper jaw) ─────────────────────────────

def _lid(g, ctx, v):
    metal = v['metal']
    zf = -LID_D
    g.rbox((-W, 0.0, zf), (W, LID_H, 0.0), 'wood', 0.56, bevel=0.5)
    # the palate: hollow underneath, lined with dark flesh
    g.carve(lambda x, y, z: abs(x) <= W - T and zf + T <= z <= -T and y <= 2.0)
    g.paint(lambda x, y, z, n, m, val: ('mouth', 0.26 + 0.06 * (y / 2.0))
            if (abs(x) <= W - T + 0.6 and zf + T - 0.6 <= z <= -T + 0.6 and y <= 2.6) else None, ['wood'])
    _wood_faces(g, -W, W, 0.0, LID_H, zf, 0.0, grooves_y=(), grooves_x=(-2.4, 2.4))
    # metal straps over the top and down the front, corner caps, rivets
    for sx in (-1, 1):
        x0, x1 = sx * 3.6, sx * 5.0
        _box(g, (x0, LID_H, zf - 0.5), (x1, LID_H + 0.5, 0.3), metal, 0.56, prio=3)          # over the top
        _box(g, (x0, 0.6, zf - 0.5), (x1, LID_H + 0.5, zf), metal, 0.52, prio=3)            # down the front
        _box(g, (x0, 1.0, 0.0), (x1, LID_H + 0.5, 0.5), metal, 0.46, prio=3)                # down the back
        if not v['whelp']:      # coarse whelp voxels would turn rivets into spikes
            _rivets(g, [((x0 + x1) / 2, LID_H + 0.6, z) for z in (-12.0, -7.0, -2.0)], metal)
            _rivets(g, [((x0 + x1) / 2, 2.4, zf - 0.6)], metal)
        for sz, z0, z1 in ((-1, zf - 0.5, zf + 1.6), (1, -1.6, 0.5)):
            _box(g, (sx * (W - 1.6), 0.2, z0), (sx * (W + 0.5), LID_H + 0.5, z1), metal, 0.55, prio=3)
            if not v['whelp']:
                g.dot((sx * (W + 0.5), LID_H + 0.5, z0 if sz < 0 else z1), metal, 0.88, prio=5)
    # the latch hanging over the seam, keyhole (gilded: a ruby set in gold)
    _box(g, (-1.3, -2.6, zf - 1.0), (1.3, 2.8, zf - 0.5), metal, 0.62, bevel=0.3, prio=4)
    g.dot((0, -0.4, zf - 1.1), 'mouth', 0.02, prio=6)
    g.dot((0, -1.0, zf - 1.1), 'mouth', 0.02, prio=6)
    if v['gilded']:
        g.blob((0, 1.4, zf - 1.2), (0.85, 0.85, 0.5), 'ruby', 0.62, prio=6)
        # a gold rim line round the lid foot and a gold boss on the top
        _box(g, (-W - 0.5, 0.0, zf - 0.5), (W + 0.5, 0.5, zf), 'gold', 0.5, prio=3)
        g.cylinder((0, LID_H, -7.0), (0, LID_H + 0.6, -7.0), 1.6, None, 'gold', 0.6, prio=4)
        g.dot((0, LID_H + 0.9, -7.0), 'ruby', 0.7, prio=5)
    # upper teeth hanging just proud of the front (interleaved with the lower row) and the sides
    for k, x in enumerate((-5.5, 2.3, 3.9, 5.5)):
        g.cone((x, 0.6, zf - OUT), (0, -1, -0.12), 2.6 + 0.3 * h2(k, 2, 7), 0.65, 'tooth', 0.55, 0.95, prio=4)
    for s in (-1, 1):
        g.cone((s * (W + OUT - 0.2), 0.6, zf + 0.3), (s * 0.1, -1, -0.1), 3.2, 0.75, 'tooth', 0.55, 0.95, prio=4)
        for k, z in enumerate((-10.3, -7.7, -5.1)):
            g.cone((s * (W + OUT), 0.6, z), (s * 0.12, -1, 0), 2.2 - 0.3 * k, 0.58, 'tooth', 0.55, 0.95, prio=4)


# ───────────────────────────── tongue (hangs over the front lip) ─────────────────────────────

def _tongue(g, ctx, v):
    # a broad, flat tongue lolling over the lip: up out of the mouth, over the teeth, down the front, tip curling out
    pts = [(0.0, 0.8, 1.2), (0.0, 0.9, -0.6), (0.0, -0.8, -1.3), (0.0, -4.0, -1.4), (0.0, -6.2, -1.2), (0.0, -7.3, -0.4)]
    g.sweep(pts, 1.75, 1.55, 'flesh', 0.5, sq=(1.0, 1.0, 0.42),
            vfn=lambda t, d, p: 0.5 + 0.14 * t - (0.2 if abs(p[0]) < 0.3 and p[2] < -1.0 and t > 0.15 else 0.0))


def mimic(look, name, part, ctx):
    v = _variant(ctx)
    table = {'wood': GILDED_WOOD if v['gilded'] else CHEST_WOOD, 'iron': IRON, 'gold': GOLD, 'tooth': TOOTH,
             'mouth': MOUTH, 'flesh': FLESH, 'eye': EYE_RED if v['gilded'] else EYE_AMBER, 'ruby': RUBY}
    _ramps(ctx, table)
    fn = {'body': _body, 'lid': _lid, 'tongue': _tongue}.get(name)
    if fn is None:
        return None
    vs = {'body': 0.5, 'lid': 0.5, 'tongue': 0.5}.get(name, 0.5)
    if v['whelp']:
        vs = {'body': 0.7, 'lid': 0.7, 'tongue': 0.6}.get(name, 0.7)
    g = ctx.grid(vs)
    fn(g, ctx, v)
    return g


DESIGNS = {
    'chest_mimic': mimic,
    'gilded_mimic': mimic,
    'mimic_whelp': mimic,
}
