"""Voxel mob designs — floors 9–10 (태엽 성소 · 심연의 핵).  See README.md (tools: voxel/mob_kit.py).

Every normal / elite / add mob of floors 9–10 (bosses live in bosses.py).
Floor 9 (clockwork sanctum): gear_hound · clockwork_sentry · spring_jumper · chrono_moth · grand_regulator (elite) ·
  cog_drone (add) — tarnished copper, bright brass, verdigris, ivory enamel dials, teal mainspring light.
Floor 10 (abyssal core): void_stalker · echo_colossus · abyss_eye · hollow_choir · abyss_gatekeeper (elite) ·
  abyss_spawn (add) — blue-black hide and obsidian, sculk-teal veins, pale bone / ivory, gate gold.
Coordinates: part px, origin = the part's pivot, front = −Z, model −X = the mob's left.
`spin` parts turn about the model Y axis (RigMath), so spinning gears / dials are built either lying flat
(mechanically true) or as gimbals that read well while they turn.
"""
from __future__ import annotations

import math

from ..util import h2, h3  # noqa: F401
from ..voxel.core import bezier, helix, resample
from ..voxel.mob_kit import MobGrid, fbm3, frame_of, vadd, vcross, vdot, vlen, vmul, vnorm, vsub  # noqa: F401
from ..voxel.palette import _r

GLOW_MATS = ('glow', 'eye', 'core', 'rune', 'lava')


# ───────────────────────────── shared helpers ─────────────────────────────

def _ramps(ctx, table):
    """Mob-wide ramps; glow ramps are resampled to 11 steps so the atlas pulse survives coarse levels."""
    for mat, cols in table.items():
        ctx.set_ramp(mat, _r(cols, 11) if mat in GLOW_MATS else cols)


def _stick(g: MobGrid, origin, direction, out=1.0, max_dist=30.0):
    """Point just outside the first surface hit along a ray (px)."""
    p = g.hit(origin, direction, max_dist)
    if p is None:
        return None
    d = vnorm(direction)
    return vadd(p, vmul(d, -g.vs * out))


def _swap(g: MobGrid, mats, to_mat, amount=0.35, scale=2.0, seed=0, v0=0.35, v1=0.8, glow=False, region=None):
    """fbm patches of the surface switch material (verdigris on copper, sculk on stone)."""
    sd = g.seed + 401 + seed

    def f(x, y, z, n, m, v):
        if region and not region(x, y, z):
            return None
        q = fbm3(x / scale, y / scale, z / scale, sd)
        if q > 1 - amount:
            return (to_mat, v0 + (v1 - v0) * (q - (1 - amount)) / amount, glow)
        return None
    g.paint(f, mats)


def _patina_drips(g: MobGrid, mats, density=0.12, seed=0):
    """Verdigris running down from seams (green streaks below rivets / plate edges)."""
    g.streaks('patina', mats, density=density, length=(1.0, 3.2), val=0.55, val_end=0.35, seed=seed)


_N18 = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)
        if (a, b, c) != (0, 0, 0) and abs(a) + abs(b) + abs(c) <= 2]


def _vein_walk(g: MobGrid, mats, n, steps=(6, 14), seed=0, bias=None, fork=0.15, region=None, val=(0.75, 0.4),
               starts=None, mat='glow', min_d=3.0, wiggle=0.55):
    """Thin branching glow veins crawling over the surface (sculk veins, fissures, eye veins).
    A walker steps voxel to voxel over exposed voxels of `mats` (face/edge neighbours), keeping its heading,
    drifting toward `bias` (vector or fn(p) → vector) with noise, forking now and then.  Brightness fades
    from val[0] at the source to val[1] at the tip.  starts = px points to begin from (else spread picks)."""
    surf = {k: nn for k, nn in g.exposed(mats)}
    if region:
        surf = {k: nn for k, nn in surf.items() if region(*g.px(k))}
    if not surf:
        return
    sd = g.seed + 571 + seed
    keys = sorted(surf, key=lambda q: h3(q[0], q[1], q[2], sd))
    if starts:
        picks = []
        for p in starts:
            kp = g.key(p)
            best = min(surf, key=lambda q: (q[0] - kp[0]) ** 2 + (q[1] - kp[1]) ** 2 + (q[2] - kp[2]) ** 2)
            picks.append(best)
    else:
        picks = []
        md = min_d / g.vs
        for k in keys:
            if all((k[0] - q[0]) ** 2 + (k[1] - q[1]) ** 2 + (k[2] - q[2]) ** 2 >= md * md for q in picks):
                picks.append(k)
            if len(picks) >= n:
                break
    done = set()
    stack = []
    for m_, k in enumerate(picks):
        L = int(steps[0] + (steps[1] - steps[0]) * h2(m_, 1, sd))
        a = h2(m_, 2, sd) * 2 * math.pi
        stack.append((k, (math.cos(a), math.sin(a) * 0.6, math.sin(a)), L, L, m_))
    guard = 0
    while stack and guard < 4000:
        guard += 1
        cur, d, left, total, tag = stack.pop()
        for step in range(left):
            t = 1 - (left - step) / max(1, total)
            if cur not in done:
                v = g.vox.get(cur)
                if v is not None:
                    v[0], v[1], v[2] = mat, val[0] + (val[1] - val[0]) * t, True
                done.add(cur)
            p = g.px(cur)
            bd = bias(p) if callable(bias) else bias
            best, bs = None, -9.0
            for o in _N18:
                nk = (cur[0] + o[0], cur[1] + o[1], cur[2] + o[2])
                if nk not in surf or nk in done:
                    continue
                on = vnorm(o)
                sc = vdot(on, d) + wiggle * (h3(nk[0], nk[1], nk[2], sd + tag) - 0.5)
                if bd:
                    sc += 0.5 * vdot(on, vnorm(bd))
                if abs(o[0]) + abs(o[1]) + abs(o[2]) == 1:
                    sc += 0.12           # prefer face steps (straighter runs merge better)
                if sc > bs:
                    best, bs = nk, sc
            if best is None:
                break
            step_d = vnorm(vsub(best, cur))
            d = vnorm(vadd(vmul(d, 0.65), vmul(step_d, 0.35)))
            if fork and h3(cur[0], cur[1], cur[2], sd + 7) < fork and left - step > 3:
                u, w = frame_of(d)
                nd = vnorm(vadd(d, vmul(u, 1.1 if h2(step, tag, sd) > 0.5 else -1.1)))
                stack.append((best, nd, (left - step) // 2, total, tag + 31))
            cur = best


def _plane_frame(normal):
    f = vnorm(normal)
    up = (0, 1, 0) if abs(f[1]) < 0.9 else (0, 0, 1)
    side = vnorm(vcross(up, f))
    upv = vcross(f, side)
    return f, side, upv


def _inlay(g: MobGrid, c, normal, strokes, mat='rune', val=0.6, glow=True, depth=8.0, prio=6, step=0.8):
    """Line strokes (2D (u, v) px around c; u sideways, v up as seen facing the surface) projected onto the
    surface that faces `normal`."""
    f, side, upv = _plane_frame(normal)
    for st in strokes:
        for (u0, v0), (u1, v1) in zip(st, st[1:]):
            n = max(1, int(math.hypot(u1 - u0, v1 - v0) / (g.vs * step)))
            for k in range(n + 1):
                u, v = u0 + (u1 - u0) * k / n, v0 + (v1 - v0) * k / n
                o = vadd(vadd(vadd(c, vmul(side, u)), vmul(upv, v)), vmul(f, depth))
                p = g.hit(o, vmul(f, -1), depth * 2)
                if p is not None:
                    g.dot(p, mat, val, glow=glow, prio=prio)


def _circle(r, n=16, a0=0.0, cx=0.0, cy=0.0):
    return [(cx + math.cos(a0 + 2 * math.pi * k / n) * r, cy + math.sin(a0 + 2 * math.pi * k / n) * r)
            for k in range(n + 1)]


def _gear_mask(R, teeth, hole=0.0, spokes=0, rim=1.2, tooth_h=0.9, spoke_w=0.55, hub=0.0):
    """2D gear outline mask(u, v): teeth beyond R, a rim ring, spokes and a hub (px)."""
    def m(u, v):
        d = math.hypot(u, v)
        if d > R + tooth_h:
            return False
        a = math.atan2(v, u)
        if d > R:
            return ((a * teeth / (2 * math.pi)) % 1.0) < 0.5
        if hole and d < hole:
            return False
        if spokes and hub < d < R - rim:
            for s in range(spokes):
                aa = s * 2 * math.pi / spokes
                du = abs(-math.sin(aa) * u + math.cos(aa) * v)
                along = math.cos(aa) * u + math.sin(aa) * v
                if du < spoke_w and along > 0:
                    return True
            return False
        return True
    return m


def _gear(g: MobGrid, c, R, teeth, plane='xy', thick=1.0, mat='brass', val=0.55, hole=0.0, spokes=0, rim=1.2,
          tooth_h=0.9, hub=0.0, prio=3, spoke_w=0.55, bevel_light=0.18):
    """Gear disc in a plane ('xy' faces Z, 'zy' faces X, 'xz' lies flat facing Y) centred at c."""
    m = _gear_mask(R, teeth, hole, spokes, rim, tooth_h, spoke_w, hub)
    if plane == 'xy':
        mk, lo, hi, depth = (lambda u, v: m(u - c[0], v - c[1])), (c[0] - R - 1.5, c[1] - R - 1.5), \
            (c[0] + R + 1.5, c[1] + R + 1.5), c[2]
    elif plane == 'zy':
        mk, lo, hi, depth = (lambda u, v: m(u - c[2], v - c[1])), (c[2] - R - 1.5, c[1] - R - 1.5), \
            (c[2] + R + 1.5, c[1] + R + 1.5), c[0]
    else:
        mk, lo, hi, depth = (lambda u, v: m(u - c[0], v - c[2])), (c[0] - R - 1.5, c[2] - R - 1.5), \
            (c[0] + R + 1.5, c[2] + R + 1.5), c[1]

    def vf(u, v, w, e):
        uu, vv = (u - c[0], v - c[1]) if plane == 'xy' else (u - c[2], v - c[1]) if plane == 'zy' else \
            (u - c[0], v - c[2])
        d = math.hypot(uu, vv)
        if d > R:
            return val + bevel_light
        if d > R - rim:
            return val + 0.08
        return val - 0.08
    g.slab2d(mk, lo, hi, plane, depth, thick / 2, mat, vfn=vf, prio=prio)


def _band(g: MobGrid, c, R, r, axis='y', mat='brass', val=0.55, glow=False, prio=2):
    """Flat ring band (an annulus of thickness 2r along the axis) — a cheaper, crisper stand-in for a torus."""
    d = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}[axis]
    a = vsub(c, vmul(d, r))
    b = vadd(c, vmul(d, r))
    g.cylinder(a, b, R + r, R + r, mat, val, glow=glow, prio=prio, hollow=max(0.0, R - r),
               vfn=lambda t, rad, p: val + 0.1 * (rad - 0.7))


def _spring(g: MobGrid, y0, y1, R, turns, r, mat='iron', val=0.55, cx=0.0, cz=0.0, phase=0.0, rfn=None, prio=2):
    """Coil spring around the Y axis from y0 to y1 (lit on the outside of each coil)."""
    pts = helix(y0, y1, R, turns, phase, cx, cz, rfn=rfn, n=int(turns * 28))
    g.sweep(pts, r, r, mat, val, prio=prio, smooth=False,
            vfn=lambda t, d, p: val + 0.18 * (1 - d))


# ═════════════════════════════ FLOOR 9 · 태엽 성소 ═════════════════════════════

COPPER = [(20, 11, 6), (42, 22, 11), (72, 38, 18), (110, 60, 28), (152, 88, 42), (194, 122, 62), (228, 162, 96),
          (248, 206, 150)]
BRASS = [(30, 21, 7), (64, 46, 15), (108, 80, 28), (156, 120, 46), (200, 162, 72), (232, 202, 116), (250, 234, 176)]
PATINA = [(14, 42, 36), (26, 76, 64), (46, 116, 96), (80, 160, 132), (130, 202, 172), (188, 234, 210)]
GUNMETAL = [(12, 13, 16), (24, 26, 30), (42, 45, 50), (66, 70, 76), (96, 100, 106), (134, 138, 142), (184, 186, 188)]
ENAMEL = [(70, 60, 44), (128, 116, 92), (184, 172, 146), (220, 212, 190), (240, 236, 220), (252, 250, 242)]
TEAL = [(14, 70, 58), (30, 136, 110), (70, 200, 162), (140, 238, 206), (206, 255, 236), (255, 255, 255)]
AMBER = [(110, 54, 10), (190, 110, 24), (240, 172, 56), (255, 216, 120), (255, 244, 206), (255, 255, 255)]
LACQUER = [(14, 6, 6), (30, 12, 12), (52, 20, 20), (80, 32, 30), (112, 48, 42), (146, 70, 58)]


def _f9_ramps(ctx, extra=None):
    t = {'copper': COPPER, 'brass': BRASS, 'patina': PATINA, 'iron': GUNMETAL, 'enamel': ENAMEL,
         'glow': TEAL, 'eye': TEAL, 'core': TEAL, 'rune': TEAL}
    if extra:
        t.update(extra)
    _ramps(ctx, t)


# ───────────────────────────── gear_hound (톱니 사냥개) ─────────────────────────────
# A lean copper automaton greyhound: a deep riveted keel chest caged in copper ribs around a teal-lit
# mainspring and a little gear train, a wasp waist with an exposed drive shaft, a riveted haunch; a long
# jackal muzzle with swept plate ears, slit teal eyes and saw teeth; digitigrade piston legs on brass
# gear joints; a whip tail of alternating links ending in a winding key.  On its back a flat crown gear
# and a flyball governor — the faster the gear spins, the further its brass balls fly out.

def _hound_body(g: MobGrid, ctx):
    # keel chest (front), haunch (back), wasp waist between
    g.blob((0, -0.3, -3.6), (3.1, 3.7, 3.5), 'copper', 0.46, top=0.16)
    g.blob((0, 0.9, 4.7), (2.8, 2.7, 3.0), 'copper', 0.46, top=0.16)
    g.capsule((0, 1.1, -1.6), (0, 1.5, 2.6), 1.4, 1.5, 'iron', 0.4)
    # back plates along the spine (overlapping, rear edge lit), brass ridge
    g.plates((0, 0.4, -3.4), (3.3, 3.5, 3.3), n=3, axis=2, mat='copper', val=0.52, lift=0.1, groove=-0.3,
             cut=lambda x, y, z: y < 0.8)
    g.plates((0, 1.4, 4.7), (3.0, 2.5, 3.1), n=2, axis=2, mat='copper', val=0.52, lift=0.1, groove=-0.3,
             cut=lambda x, y, z: y < 1.6)
    # spine: vertebra discs (steel) along the waist
    for z in (-0.8, 0.5, 1.8):
        g.cylinder((0, 2.6, z - 0.3), (0, 2.6, z + 0.3), 1.2, 1.2, 'brass', 0.5)
    # brass portholes on both flanks: teal-lit mainspring behind glass
    for s in (-1, 1):
        g.cylinder((s * 2.6, -0.4, -3.6), (s * 3.3, -0.4, -3.6), 1.9, 1.9, 'brass', 0.55)
        g.cylinder((s * 3.0, -0.4, -3.6), (s * 3.45, -0.4, -3.6), 1.3, 1.3, 'glow', 0.42, glow=True, prio=3)
        g.dot((s * 3.5, -0.4, -3.6), 'iron', 0.2, prio=5)
        for a in range(4):
            aa = a * math.pi / 2 + 0.6
            g.dot((s * 3.5, -0.4 + math.sin(aa) * 0.7, -3.6 + math.cos(aa) * 0.7), 'glow', 0.75, glow=True, prio=5)
    g.capsule((0, -3.7, -5.4), (0, -3.3, -1.8), 0.55, 0.45, 'brass', 0.55)          # sternum keel bar
    # exposed drive shaft and piston under the waist
    g.capsule((0, -0.8, -1.4), (0, -0.2, 3.2), 0.5, 0.5, 'iron', 0.62)
    # neck rising forward to the head, riveted collar
    g.capsule((0, 1.0, -5.4), (0, 2.4, -8.2), 1.9, 1.6, 'copper', 0.5)
    _band(g, (0, 1.8, -7.0), 1.95, 0.45, 'z', 'brass', 0.6)
    # gear axle housing on the back
    g.cylinder((0, 2.8, 0.8), (0, 4.2, 0.8), 1.3, 1.0, 'brass', 0.5)
    # hip / shoulder bosses
    for s in (-1, 1):
        for z, y in ((-4.4, 0.2), (5.0, 0.6)):
            g.cylinder((s * 2.8, y, z), (s * 3.4, y, z), 1.4, 1.2, 'iron', 0.45)
    # rivets along the plate seams
    for z in (-5.6, -1.8, 3.2, 6.0):
        for s in (-1, 1):
            p = _stick(g, (s * 6, 1.6, z), (-s, 0, 0), out=0.3)
            if p:
                g.dot(p, 'brass', 0.8, prio=5)
    _swap(g, ['copper'], 'patina', amount=0.2, scale=2.4, seed=1, v0=0.35, v1=0.65)
    _patina_drips(g, ['copper'], 0.05)


def _hound_head(g: MobGrid, ctx):
    # cranium + long tapering jackal muzzle (laid out to cover the jaw part, which sits ~3 px forward)
    g.blob((0, 0.9, 1.0), (2.6, 2.4, 2.7), 'copper', 0.5, top=0.2)
    g.sweep([(0, 0.7, 0.0), (0, 0.5, -3.0), (0, 0.1, -6.0)], 1.9, 0.95, 'copper', 0.5, sq=(1.0, 0.72, 1.0),
            vfn=lambda t, d, p: 0.48 + 0.12 * (1 - d))
    g.rbox((-0.6, 1.3, -5.4), (0.6, 1.9, -0.4), 'brass', 0.62, bevel=0.25)       # nose ridge plate
    g.blob((0, 0.4, -6.3), (0.8, 0.6, 0.6), 'iron', 0.3)                         # steel nose tip
    # brass visor brow over slit teal eyes
    for s in (-1, 1):
        g.capsule((s * 0.5, 2.5, -1.9), (s * 2.5, 2.1, -0.7), 0.5, 0.45, 'brass', 0.6)
        g.capsule((s * 1.3, 1.45, -2.25), (s * 2.35, 1.3, -1.0), 0.42, 0.36, 'eye', 0.7, glow=True, prio=5)
    # dark mouth line with upper saw teeth over the jaw part
    g.carve(lambda x, y, z: y < -0.2 and z < -0.8 and abs(x) < 1.2)
    g.teeth((-1.1, -0.2, -1.0), (-0.6, -0.3, -5.6), 4, 0.8, r=0.3, mat='iron', val=0.72, seed=1)
    g.teeth((1.1, -0.2, -1.0), (0.6, -0.3, -5.6), 4, 0.8, r=0.3, mat='iron', val=0.72, seed=2)
    # tall pointed ears swept back (copper plates, verdigris inner face)
    for s in (-1, 1):
        g.sweep([(s * 1.5, 2.4, 1.4), (s * 2.0, 4.8, 2.0), (s * 2.3, 7.0, 3.2)], 1.25, 0.25, 'copper', 0.56,
                sq=(0.42, 1, 1), vfn=lambda t, d, p: 0.5 + 0.22 * t)
        g.sweep([(s * 1.35, 2.9, 1.2), (s * 1.8, 4.8, 1.8)], 0.65, 0.3, 'patina', 0.45, sq=(0.4, 1, 1), prio=2)
        _gear(g, (s * 2.45, -0.1, 0.4), 1.15, 7, plane='zy', thick=0.5, mat='brass', val=0.55, tooth_h=0.45,
              rim=0.5, prio=4)
    g.rivets([(s * 1.9, 0.6, z) for s in (-1, 1) for z in (-3.2,)], 'brass')
    _swap(g, ['copper'], 'patina', amount=0.15, scale=2.0, seed=3)


def _hound_jaw(g: MobGrid, ctx):
    # lower jaw: copper underside, dark steel palate, saw teeth up
    g.sweep([(0, -0.2, 2.4), (0, -0.4, -0.4), (0, -0.2, -2.6)], 1.4, 0.8, 'copper', 0.42, sq=(1.0, 0.55, 1.0))
    g.rbox((-0.9, 0.0, -2.4), (0.9, 0.4, 2.0), 'iron', 0.22)
    g.teeth((-0.85, 0.3, 1.6), (-0.6, 0.3, -2.2), 3, 0.75, r=0.28, mat='iron', val=0.72, direction=(0, 1, 0), seed=3)
    g.teeth((0.85, 0.3, 1.6), (0.6, 0.3, -2.2), 3, 0.75, r=0.28, mat='iron', val=0.72, direction=(0, 1, 0), seed=4)


def _hound_legs(g: MobGrid, ctx):
    gy = -4.8
    for s in (-1, 1):
        # front leg: shoulder → elbow → wrist, a steel piston rod down the front of the forearm
        sh, el, wr = (s * 3.3, 4.4, -4.4), (s * 3.4, 0.6, -3.8), (s * 3.4, -3.4, -4.6)
        g.limb([sh, el, wr], [1.2, 0.7, 0.55], 'copper', 0.5, joint_mat='brass', joint_val=0.55, knob=1.3)
        g.capsule((s * 3.4, 0.0, -4.7), (s * 3.4, -3.0, -5.3), 0.3, 0.3, 'iron', 0.65)
        # hind leg: digitigrade (thigh forward, long hock back), piston behind the thigh
        hp, kn, hk = (s * 3.2, 4.8, 5.0), (s * 3.4, 1.6, 3.4), (s * 3.4, -1.8, 6.6)
        g.limb([hp, kn, hk], [1.45, 0.8, 0.55], 'copper', 0.5, joint_mat='brass', joint_val=0.55, knob=1.3)
        g.capsule(hk, (s * 3.4, -3.8, 6.0), 0.5, 0.45, 'copper', 0.48)
        g.capsule((s * 3.5, 4.0, 6.6), (s * 3.5, -1.0, 7.4), 0.32, 0.32, 'iron', 0.62)
        # gear joints at shoulder / hip
        for c in (sh, hp):
            _gear(g, (s * 4.4, c[1] - 0.2, c[2]), 1.3, 8, plane='zy', thick=0.5, mat='brass', val=0.5,
                  tooth_h=0.45, rim=0.5, prio=4)
            g.dot((s * 4.75, c[1] - 0.2, c[2]), 'patina', 0.7, prio=5)
        # paws: copper pad, three steel claws
        for pz, px in ((-5.0, s * 3.4), (5.6, s * 3.4)):
            g.rbox((px - 0.9, gy, pz - 1.1), (px + 0.9, gy + 0.9, pz + 0.7), 'copper', 0.42, bevel=0.35)
            for k in (-1, 0, 1):
                g.cone((px + k * 0.55, gy + 0.45, pz - 1.0), (0, -0.4, -1), 0.9, 0.28, 'iron', 0.45, 0.8)


def _hound_gear(g: MobGrid, ctx):
    # flat gear on the back (turns about Y = its own axle): 12 teeth, 4 spokes, brass hub
    _gear(g, (0, 0, 0), 3.0, 12, plane='xz', thick=0.9, mat='brass', val=0.4, spokes=4, rim=0.9,
          tooth_h=0.9, hub=1.0, spoke_w=0.45, bevel_light=0.3)
    g.cylinder((0, -2.6, 0), (0, 0.9, 0), 0.9, 0.9, 'iron', 0.5)                 # axle
    # flyball governor: spindle, sliding collar, two arms with brass balls flung outward
    g.cylinder((0, 0.6, 0), (0, 4.2, 0), 0.4, 0.4, 'iron', 0.62)
    g.cylinder((0, 1.4, 0), (0, 2.0, 0), 0.75, 0.75, 'copper', 0.62)
    for s in (-1, 1):
        g.capsule((0, 4.0, 0), (s * 2.6, 2.4, 0), 0.3, 0.3, 'iron', 0.65)
        g.capsule((0, 1.8, 0), (s * 1.4, 3.2, 0), 0.25, 0.25, 'iron', 0.55)
        g.blob((s * 2.8, 2.3, 0), 0.9, 'copper', 0.62, top=0.3)
    g.blob((0, 4.6, 0), 0.65, 'glow', 0.75, glow=True, prio=5)


def _hound_tail(g: MobGrid, ctx):
    path = bezier((0, 0, -0.4), (0, 0.8, 2.4), (0, 2.4, 4.8), (0, 4.2, 6.4), 12)
    for n_, (p, t) in enumerate(resample(path, 1.0)):
        r = 0.75 - 0.3 * t
        g.blob(p, r, 'copper' if n_ % 2 == 0 else 'iron', 0.55 if n_ % 2 == 0 else 0.45, top=0.2)
    # winding key bow at the tip
    _band(g, (0, 5.6, 7.2), 1.2, 0.35, 'x', 'brass', 0.62)
    _band(g, (0, 5.0, 8.0), 0.9, 0.32, 'x', 'brass', 0.58)
    g.blob((0, 4.4, 6.6), 0.6, 'brass', 0.6)


def gear_hound(look, name, part, ctx):
    _f9_ramps(ctx)
    fn = {'body': _hound_body, 'head': _hound_head, 'jaw': _hound_jaw, 'legs': _hound_legs, 'gear': _hound_gear,
          'tail': _hound_tail}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.6, 'legs': 0.55, 'gear': 0.6}.get(name, 0.5))
    if name == 'legs':
        g.light_mul = 0.6
    fn(g, ctx)
    return g


# ───────────────────────────── clockwork_sentry (태엽 보초) ─────────────────────────────
# A sanctum gun-post on three jointed spider legs: a bronze hub with a toothed yaw ring, a domed riveted
# turret with an amber range-finder lens, a side magazine of saw-toothed gear rounds and a hand crank, a
# quad-barrel rotary gun clamped in brass, and a big wind-up key on its back that runs down as it fires.

SENTRY_BRONZE = [(18, 12, 8), (38, 25, 15), (64, 42, 24), (98, 66, 38), (136, 94, 54), (176, 128, 76), (214, 170, 110),
                 (240, 210, 160)]


def _sentry_tripod(g: MobGrid, ctx):
    gy = -4.8
    # hub column with a toothed yaw ring on top and a hanging counterweight
    g.cylinder((0, -0.6, 0), (0, 4.6, 0), 2.1, 2.4, 'copper', 0.45)
    _gear(g, (0, 5.0, 0), 3.4, 16, plane='xz', thick=0.8, mat='brass', val=0.5, tooth_h=0.6, rim=0.9)
    g.cylinder((0, 2.0, 0), (0, 2.8, 0), 2.7, 2.7, 'brass', 0.55)
    g.cone((0, -0.6, 0), (0, -1, 0), 2.4, 1.5, 'iron', 0.4, 0.6)
    for a in (0.0, 2.0944, 4.1888):
        g.dot((math.sin(a) * 2.75, 2.4, math.cos(a) * 2.75), 'brass', 0.85, prio=5)
    # three legs: one behind, two forward-out (front = −Z)
    for ang in (0.0, 2.0944, -2.0944):
        dx, dz = math.sin(ang), math.cos(ang)

        def P(r, y):
            return (dx * r, y, dz * r)
        hip, knee, ank, foot = P(1.8, 3.4), P(5.4, 7.4), P(7.0, -1.2), P(7.4, gy + 0.6)
        g.limb([hip, knee, ank, foot], [1.35, 1.0, 0.7, 0.55], 'copper', 0.5, joint_mat='brass', joint_val=0.55,
               knob=1.25)
        g.blob(knee, 1.25, 'brass', 0.6)
        g.dot(vadd(knee, (0, 1.3, 0)), 'glow', 0.7, glow=True, prio=6)
        # armoured thigh plate on top of the upper leg
        g.capsule(vadd(P(2.6, 4.8), (0, 0.8, 0)), vadd(P(5.0, 7.6), (0, 0.7, 0)), 0.7, 0.55, 'brass', 0.62)
        # piston from the hub to the shin
        g.capsule(P(2.0, 0.6), P(6.2, 2.4), 0.4, 0.35, 'iron', 0.62)
        g.cylinder(P(2.0, 0.6), P(3.8, 1.4), 0.7, 0.7, 'iron', 0.42)
        # clawed foot: three toes
        for k in (-1, 0, 1):
            ta = ang + k * 0.55
            g.cone(foot, (math.sin(ta), -0.5, math.cos(ta)), 1.4, 0.4, 'iron', 0.4, 0.75)


def _sentry_turret(g: MobGrid, ctx):
    # drum + riveted dome
    g.cylinder((0, -4.0, 0), (0, 1.2, 0), 4.4, 4.6, 'copper', 0.48)
    g.blob((0, 1.0, 0), (4.4, 2.9, 4.4), 'copper', 0.5, cut=lambda x, y, z: y < 1.0, top=0.25)
    _band(g, (0, 1.1, 0), 4.6, 0.45, 'y', 'brass', 0.6)
    _band(g, (0, -3.6, 0), 4.6, 0.45, 'y', 'brass', 0.5)
    g.rivets([(math.sin(a) * 4.75, -1.4, math.cos(a) * 4.75) for a in [k * math.pi / 6 for k in range(12)]], 'brass')
    g.cylinder((0, 3.6, 0), (0, 4.5, 0), 1.0, 0.7, 'brass', 0.6)                  # dome finial
    # front mantlet + amber range-finder lens above the gun
    g.rbox((-2.6, -2.2, -5.0), (2.6, 1.8, -3.8), 'iron', 0.4, bevel=0.5)
    g.cylinder((0, 2.6, -3.0), (0, 2.6, -4.6), 1.3, 1.3, 'brass', 0.55)
    g.eye((0, 2.6, -4.5), 0.85, val=0.5, facing=(0, 0, -1))
    # spring-barrel housing on the back (the key sits in its socket)
    g.rbox((-2.4, -3.0, 3.4), (2.4, 2.6, 6.0), 'copper', 0.44, bevel=0.8)
    g.cylinder((0, 2.4, 4.8), (0, 3.2, 4.8), 0.9, 0.9, 'brass', 0.62)
    for y in (-1.6, 0.6):
        g.rbox((-2.5, y, 3.3), (2.5, y + 0.4, 6.1), 'brass', 0.55)
    # magazine drum of saw-toothed gear rounds (mob's right = +X), feed chute to the gun
    g.cylinder((4.2, -0.8, 0.6), (6.0, -0.8, 0.6), 2.5, 2.5, 'iron', 0.42)
    for k, x in enumerate((4.6, 5.3, 6.0)):
        _gear(g, (x, -0.8, 0.6), 2.4, 9, plane='zy', thick=0.4, mat='brass', val=0.5 + 0.06 * k, tooth_h=0.6, rim=0.7)
    g.dot((6.4, -0.8, 0.6), 'brass', 0.8, prio=5)
    g.capsule((4.4, -1.6, -1.4), (2.0, -1.4, -4.2), 0.7, 0.6, 'iron', 0.5)
    # hand crank on the left side
    g.cylinder((-4.4, -0.6, 0.4), (-5.6, -0.6, 0.4), 0.55, 0.55, 'iron', 0.55)
    g.capsule((-5.6, -0.6, 0.4), (-5.6, -2.6, 1.4), 0.4, 0.4, 'brass', 0.6)
    g.capsule((-5.6, -2.6, 1.4), (-6.6, -2.6, 1.4), 0.45, 0.45, 'lacquer', 0.5)
    _swap(g, ['copper'], 'patina', amount=0.16, scale=2.2, seed=2)
    _patina_drips(g, ['copper'], 0.07)


def _sentry_barrel(g: MobGrid, ctx):
    # quad-barrel rotary gun along −Z, brass clamps, dark bores
    for a in range(4):
        aa = a * math.pi / 2 + math.pi / 4
        x, y = math.cos(aa) * 1.0, math.sin(aa) * 1.0
        g.cylinder((x, y, 2.0), (x, y, -6.4), 0.55, 0.55, 'iron', 0.55)
        g.dot((x, y, -6.5), 'void', 0.1, prio=6)
    g.cylinder((0, 0, 2.0), (0, 0, -5.8), 0.45, 0.45, 'iron', 0.3)
    for z0, z1, r in ((-1.6, -0.8, 1.9), (-5.2, -4.6, 1.85), (0.6, 2.4, 2.2)):
        g.cylinder((0, 0, z0), (0, 0, z1), r, r, 'brass', 0.55)
    _band(g, (0, 0, -6.0), 1.75, 0.3, 'z', 'brass', 0.7)
    g.rbox((-1.2, 1.6, 0.4), (1.2, 2.6, 3.2), 'copper', 0.5, bevel=0.3)            # feed housing


def _sentry_key(g: MobGrid, ctx):
    # wind-up key: shaft down into the socket, collar, figure-eight bow (turns about Y like a real key)
    g.cylinder((0, -2.6, 0), (0, 0.8, 0), 0.55, 0.55, 'iron', 0.55)
    g.cylinder((0, 0.4, 0), (0, 1.2, 0), 1.0, 1.0, 'brass', 0.6)

    def bow(u, v):
        d1, d2 = math.hypot(u - 1.9, v - 3.1), math.hypot(u + 1.9, v - 3.1)
        inside = d1 < 2.0 or d2 < 2.0 or (abs(u) < 1.0 and 1.0 < v < 4.6)
        return inside and not (d1 < 0.8 or d2 < 0.8)
    g.slab2d(bow, (-4.2, 0.8), (4.2, 5.4), 'xy', 0.0, 0.5, 'brass',
             vfn=lambda u, v, w, e: 0.48 + 0.22 * min(1.0, e / 1.2) + (0.08 if w < 0 else 0))
    g.dot((0, 3.1, -0.8), 'glow', 0.7, glow=True, prio=6)
    for s in (-1, 1):
        g.dot((s * 1.9, 5.0, -0.6), 'brass', 0.85, prio=6)


def clockwork_sentry(look, name, part, ctx):
    _f9_ramps(ctx, {'copper': SENTRY_BRONZE, 'eye': AMBER, 'glow': AMBER, 'lacquer': LACQUER})
    fn = {'tripod': _sentry_tripod, 'turret': _sentry_turret, 'barrel': _sentry_barrel,
          'key': _sentry_key}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'tripod': 0.55, 'turret': 0.6}.get(name, 0.5))
    if name == 'tripod':
        g.light_mul = 0.7
    fn(g, ctx)
    return g


# ───────────────────────────── spring_jumper (용수철 도약병) ─────────────────────────────
# A lacquered toy-soldier construct riding one giant coil spring: oxblood coat under a polished steel
# breastplate, cream cross-belts and brass buttons, fringed epaulettes, a mainspring barrel on its back;
# a round steel helm with a T-visor of amber light and a tall brass crest; telescoping piston arms with
# studded iron fists; the coil ends in a heavy studded stomping pad.

JUMPER_STEEL = [(20, 24, 30), (40, 48, 58), (66, 78, 92), (100, 116, 130), (140, 156, 168), (180, 194, 204),
                (214, 224, 232), (240, 246, 250)]
CREAM = [(80, 70, 54), (138, 124, 98), (190, 178, 150), (226, 218, 196), (246, 242, 228)]
JUMPER_SPRING = [(10, 14, 22), (20, 28, 42), (34, 46, 66), (54, 70, 96), (84, 104, 130), (128, 148, 170),
                 (184, 200, 214), (232, 240, 246)]
JUMPER_LACQUER = [(16, 6, 6), (36, 12, 11), (62, 20, 17), (94, 32, 24), (128, 48, 34), (160, 70, 48), (190, 100, 70)]


def _jumper_torso(g: MobGrid, ctx):
    # oxblood coat: broad chest, narrow waist, steel breastplate in front
    g.rbox((-4.4, -1.4, -2.6), (4.4, 5.2, 2.6), 'lacquer', 0.5, bevel=1.6, top=0.15)
    g.rbox((-3.3, -5.6, -2.1), (3.3, -0.8, 2.1), 'lacquer', 0.42, bevel=1.0)
    g.blob((0, 2.2, -2.2), (3.6, 3.2, 1.3), 'steel', 0.55, top=0.25)
    g.rbox((-0.4, -0.6, -3.4), (0.4, 5.0, -2.9), 'steel', 0.72, bevel=0.2)          # breastplate ridge
    # cream cross-belts, brass buttons, belt with a buckle
    for s in (-1, 1):
        g.sweep([(s * 3.8, 4.8, -2.4), (0, 1.2, -3.4), (-s * 3.0, -1.6, -2.2)], 0.45, 0.45, 'cream', 0.6, smooth=False)
        for y in (-2.6, -4.2):
            g.dot((s * 1.2, y, -2.6), 'brass', 0.8, prio=5)
    g.rbox((-3.5, -1.6, -2.4), (3.5, -0.6, 2.4), 'brass', 0.45, bevel=0.3)
    g.rbox((-0.9, -1.8, -2.8), (0.9, -0.4, -2.3), 'brass', 0.75, bevel=0.2)
    # fringed brass epaulettes
    for s in (-1, 1):
        g.blob((s * 4.4, 5.0, 0), (1.9, 0.7, 2.2), 'brass', 0.6, top=0.3)
        g.rbox((s * 5.4, 2.8, -1.8), (s * 6.0, 4.6, 1.8), 'brass', 0.48)
        g.bands(['brass'], axis=2, period=0.9, width=0.4, amount=-0.2)
    # mainspring barrel on the back with a ratchet wheel
    g.cylinder((0, 1.6, 2.4), (0, 1.6, 4.4), 3.0, 3.0, 'brass', 0.45)
    _gear(g, (0, 1.6, 4.6), 2.4, 12, plane='xy', thick=0.5, mat='steel', val=0.5, tooth_h=0.55, rim=0.7, spokes=3,
          hub=0.7)
    g.dot((0, 1.6, 5.0), 'brass', 0.8, prio=6)
    # coupling ring where the spring is bolted on
    g.cylinder((0, -6.6, 0), (0, -5.2, 0), 2.9, 2.6, 'steel', 0.45)
    g.rivets([(math.cos(a) * 2.95, -5.9, math.sin(a) * 2.95) for a in [k * math.pi / 4 for k in range(8)]], 'brass')
    # neck stub
    g.cylinder((0, 5.0, 0), (0, 6.4, 0), 1.3, 1.3, 'steel', 0.4)


def _jumper_head(g: MobGrid, ctx):
    # round steel helm, T-visor glowing amber, cheek bolts, brass crest rail with a lacquer-red plume
    g.blob((0, -0.2, 0), (3.4, 3.5, 3.5), 'steel', 0.52, top=0.22)
    g.carve(lambda x, y, z: z < -1.5 and ((abs(x) < 2.5 and -0.4 < y < 0.6) or (abs(x) < 0.6 and -2.6 < y < 0.6)))
    g.rbox((-2.5, -0.4, -2.2), (2.5, 0.6, -1.4), 'glow', 0.55, glow=True, prio=2)
    g.rbox((-0.6, -2.6, -2.2), (0.6, -0.4, -1.4), 'glow', 0.4, glow=True, prio=2)
    for s in (-1, 1):
        g.eye((s * 1.4, 0.1, -2.0), 0.5, val=0.75, facing=(0, 0, -1), prio=6)
    _band(g, (0, -1.6, 0), 3.35, 0.4, 'y', 'brass', 0.55)
    for s in (-1, 1):
        g.cylinder((s * 3.2, -0.6, 0.2), (s * 3.8, -0.6, 0.2), 0.75, 0.75, 'brass', 0.6)

    def rail(u, v):          # u = z, v = y
        d = math.hypot(u - 0.2, v + 0.2)
        return 3.2 < d < 4.3 and v > 0.4
    g.slab2d(rail, (-4.6, 0.2), (4.6, 4.4), 'zy', 0.0, 0.5, 'brass',
             vfn=lambda u, v, w, e: 0.5 + 0.2 * min(1.0, e / 0.6))

    def plume(u, v):
        d = math.hypot(u - 0.6, v + 0.2)
        if u > 3.4:          # tail of the plume falling down the back
            return 4.0 < d < 5.6 and v > -2.6
        return 4.1 < d < 6.0 + 0.5 * math.sin(u * 1.3) and v > 1.0
    g.slab2d(plume, (-4.6, -2.8), (6.8, 6.4), 'zy', 0.0, 0.8, 'lacquer', bevel=0.6,
             vfn=lambda u, v, w, e: 0.42 + 0.3 * min(1.0, e / 1.2))


def _jumper_arm(g: MobGrid, ctx):
    o = ctx.out
    g.blob((0, -0.4, 0), 1.7, 'brass', 0.55, top=0.3)                              # shoulder ball
    g.capsule((0, -0.8, 0), (0, -4.8, 0), 1.45, 1.25, 'lacquer', 0.5)
    _band(g, (0, -4.4, 0), 1.3, 0.35, 'y', 'cream', 0.6)
    g.blob((0, -5.6, 0), 1.2, 'brass', 0.6)                                        # elbow
    g.cylinder((0, -6.2, 0), (0, -8.0, 0), 1.05, 1.05, 'steel', 0.55)              # telescoping piston
    g.cylinder((0, -8.0, 0), (0, -9.4, 0), 0.75, 0.75, 'steel', 0.7)
    g.blob((0, -10.6, -0.2), (1.8, 1.6, 1.8), 'iron', 0.5, top=0.25)               # studded iron fist
    for k, x in enumerate((-0.9, -0.3, 0.3, 0.9)):
        g.dot((x, -10.4 + 0.1 * (k % 2), -2.0), 'steel', 0.85, prio=5)
    g.cylinder((o * 1.8, -10.4, -0.2), (o * 2.2, -10.4, -0.2), 0.6, 0.6, 'brass', 0.6)


def _jumper_spring(g: MobGrid, ctx):
    # the coil: blued steel round a guide piston, brass top cap, studded stomp pad
    g.cylinder((0, 5.6, 0), (0, 7.0, 0), 3.5, 3.5, 'brass', 0.5)
    g.cylinder((0, -6.0, 0), (0, 6.0, 0), 1.0, 1.0, 'iron', 0.5)
    _spring(g, -5.6, 5.6, 3.1, 3.0, 0.9, 'spring', 0.45)
    g.cylinder((0, -8.0, 0), (0, -6.0, 0), 3.9, 3.9, 'iron', 0.45)
    _band(g, (0, -6.3, 0), 3.7, 0.45, 'y', 'brass', 0.55)
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        g.dot((math.cos(a) * 4.1, -7.2, math.sin(a) * 4.1), 'steel', 0.85, prio=5)


def spring_jumper(look, name, part, ctx):
    _f9_ramps(ctx, {'steel': JUMPER_STEEL, 'cream': CREAM, 'lacquer': JUMPER_LACQUER, 'glow': AMBER, 'eye': AMBER,
                    'spring': JUMPER_SPRING})
    fn = {'torso': _jumper_torso, 'head': _jumper_head, 'arm_left': _jumper_arm, 'arm_right': _jumper_arm,
          'spring': _jumper_spring}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.65, 'spring': 0.6, 'head': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── chrono_moth (시간 나방) ─────────────────────────────
# A great umber moth whose forewings carry clock dials — gilded bezels, teal hour marks and two hands —
# and whose hind wings end in swallow tails with geared eyespots; brass wing veins over gold dust, pale
# scalloped margins; a furry thorax with a ruff, a little watch-glass of teal light on its back, a
# brass-banded abdomen, big glowing compound eyes and feathered antennae.

MOTH_WING = [(10, 7, 5), (22, 15, 9), (38, 27, 15), (60, 44, 24), (92, 70, 38), (136, 106, 58), (186, 152, 90),
             (232, 210, 150)]
MOTH_FUR = [(36, 28, 20), (70, 56, 40), (110, 92, 68), (152, 132, 100), (192, 174, 138), (224, 210, 176),
            (244, 236, 210)]


def _poly_in(poly, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _poly_edge(poly, x, y, edges=None):
    best = 1e9
    segs = list(zip(poly, poly[1:] + poly[:1]))
    for n_, ((x1, y1), (x2, y2)) in enumerate(segs):
        if edges is not None and n_ not in edges:
            continue
        ax, ay = x2 - x1, y2 - y1
        L2 = ax * ax + ay * ay or 1e-9
        t = max(0.0, min(1.0, ((x - x1) * ax + (y - y1) * ay) / L2))
        best = min(best, math.hypot(x - x1 - ax * t, y - y1 - ay * t))
    return best


# +X wing outlines in (x, z); front = −z.  Forewing swept forward (hawk-moth), hind wing with a long
# swallow tail that ends in a pendulum bob.
FORE = [(1.0, -2.2), (4.6, -4.8), (8.8, -6.6), (12.8, -7.4), (15.0, -6.8), (15.6, -4.6), (14.6, -1.8), (12.2, 0.2),
        (8.6, 0.8), (4.6, 0.6), (1.2, 0.0)]
FORE_OUTER = {4, 5, 6, 7}
HIND = [(1.0, 0.0), (4.4, 0.6), (8.4, 1.6), (10.6, 3.6), (10.2, 5.8), (8.6, 7.0), (7.6, 9.6), (6.6, 9.8), (5.8, 7.6),
        (3.4, 5.8), (1.4, 2.6)]
HIND_OUTER = {2, 3, 4, 5, 6, 7}
DIAL_C, DIAL_R = (9.4, -3.2), 3.5
SPOT_C = (6.6, 4.0)


def _moth_wing_cell(x, z, fore, sd):
    """(mat, value[, glow]) of one wing cell (+X side coordinates)."""
    poly, outer = (FORE, FORE_OUTER) if fore else (HIND, HIND_OUTER)
    e = _poly_edge(poly, x, z, outer)
    if e < 0.95:
        # pale scalloped margin with dark spots between the scallops
        cx, cz = (8.0, -2.0) if fore else (5.0, 3.6)
        ang = math.atan2(z - cz, x - cx)
        return ('wing', 0.86) if math.sin(ang * (16 if fore else 12)) < 0.45 else ('wing', 0.2)
    if fore:
        d = math.hypot(x - DIAL_C[0], z - DIAL_C[1])
        if d < DIAL_R + 0.75:
            ang = math.atan2(z - DIAL_C[1], x - DIAL_C[0])
            if d > DIAL_R:
                return ('brass', 0.66)
            if d > DIAL_R - 1.0 and ((ang / (2 * math.pi) * 12 + 0.5) % 1.0) < 0.28:
                return ('rune', 0.62, True)
            if d < 0.65:
                return ('rune', 0.85, True)
            for a, L, w in ((math.atan2(-1.0, -0.4), DIAL_R * 0.55, 0.5), (math.atan2(-0.15, 1.0), DIAL_R * 0.85, 0.4)):
                px_, pz_ = math.cos(a), math.sin(a)
                along = (x - DIAL_C[0]) * px_ + (z - DIAL_C[1]) * pz_
                perp = abs(-(x - DIAL_C[0]) * pz_ + (z - DIAL_C[1]) * px_)
                if 0 < along < L and perp < w:
                    return ('iron', 0.22)
            return ('enamel', 0.62 - 0.06 * d / DIAL_R)
    else:
        d = math.hypot(x - SPOT_C[0], z - SPOT_C[1])
        if d < 2.4:
            ang = math.atan2(z - SPOT_C[1], x - SPOT_C[0])
            if d > 1.7:
                return ('brass', 0.58) if ((ang / (2 * math.pi) * 8) % 1.0) < 0.5 else ('wing', 0.12)
            if d > 1.0:
                return ('brass', 0.42)
            return ('rune', 0.72, True)
        if z > 7.6:
            return ('brass', 0.5)
    # body of the wing: dark root, a band of gold dust, dark outer field
    r = math.hypot(x - 1.0, z * 1.2)
    v = 0.2 + 0.05 * min(1.0, r / 3.0)
    band = (7.0, 9.6) if fore else (4.6, 6.6)
    if band[0] < r < band[1]:
        v = 0.52 + 0.08 * fbm3(x / 1.4, 0, z / 1.4, sd)
    elif fbm3(x / 1.8, 0, z / 1.8, sd + 3) > 0.66:
        v += 0.1
    # brass veins fanning from the root
    for va in ((-0.5, -0.2, 0.15) if fore else (0.45, 0.9)):
        ax, az = math.cos(va), math.sin(va)
        perp = abs(-(x - 1.0) * az + (z - (-0.8 if fore else 0.8)) * ax)
        if perp < 0.32 and x > 2.0:
            return ('brass', 0.4 + 0.015 * x)
    return ('wing', v)


def _moth_wings(g: MobGrid, ctx):
    vs = g.vs
    sd = g.seed
    for fore, poly in ((True, FORE), (False, HIND)):
        j = 0 if fore else -1
        xs = [p[0] for p in poly]
        zs = [p[1] for p in poly]
        for i in g._range(min(xs), max(xs)):
            x = i * vs
            for k in g._range(min(zs), max(zs)):
                z = k * vs
                if not _poly_in(poly, x, z):
                    continue
                res = _moth_wing_cell(x, z, fore, sd)
                gl = len(res) > 2 and res[2]
                for s in (-1, 1):
                    g.put(s * i, j, k, res[0], res[1], gl, 2)
    # raised brass leading edge (costa) on the forewings, pendulum bobs on the swallow tails
    for s in (-1, 1):
        g.sweep([(s * 1.2, vs, -2.2), (s * 4.6, vs, -4.8), (s * 8.8, vs, -6.6), (s * 12.8, vs, -7.4)], 0.3, 0.3,
                'brass', 0.62, smooth=True)
        g.cylinder((s * 7.1, -vs * 1.5, 10.4), (s * 7.1, vs * 0.5, 10.4), 1.05, 1.05, 'brass', 0.6)
        g.dot((s * 7.1, vs, 10.4), 'rune', 0.7, glow=True, prio=4)


def _moth_body(g: MobGrid, ctx):
    # thorax (furry) + ruff, small head with glowing compound eyes, brass-banded abdomen
    g.blob((0, 0.3, -1.4), (2.4, 2.4, 2.7), 'fur', 0.55, top=0.2)
    g.blob((0, -0.2, -3.6), (2.6, 2.0, 1.1), 'fur', 0.75, lump=0.25, lump_scale=0.8)         # ruff collar
    g.blob((0, -0.3, -4.7), (1.4, 1.3, 1.2), 'fur', 0.35)
    for s in (-1, 1):
        g.eye((s * 1.15, -0.1, -5.1), 0.9, val=0.5, facing=(s * 0.6, 0.1, -1))
    g.sweep([(0, 0.0, 0.8), (0, -0.2, 3.6), (0, -0.7, 7.2)], 2.0, 0.6, 'fur', 0.5,
            vfn=lambda t, d, p: 0.46 + 0.14 * (1 - d) + (-0.18 if int(t * 7) % 2 else 0.0))
    for z in (1.4, 3.0, 4.6):
        _band(g, (0, -0.2 - 0.06 * z, z), 1.95 - 0.13 * z, 0.32, 'z', 'brass', 0.6)
    g.dot((0, -0.7, 7.6), 'core', 0.8, glow=True, prio=5)
    # watch-glass of teal light on the thorax back, brass bezel
    g.cylinder((0, 2.1, -1.2), (0, 2.8, -1.2), 1.35, 1.35, 'brass', 0.55)
    g.cylinder((0, 2.6, -1.2), (0, 3.0, -1.2), 0.9, 0.9, 'core', 0.6, glow=True, prio=4)
    # six thin legs folded under
    for s in (-1, 1):
        for z, dz in ((-3.0, -1.0), (-1.6, 0.0), (-0.2, 1.0)):
            g.sweep([(s * 1.0, -1.6, z), (s * 2.3, -2.4, z + dz * 0.5), (s * 2.1, -3.8, z + dz)], 0.3, 0.25,
                    'iron', 0.45)
    g.fur(['fur'], direction=(0, -0.3, 1), length=0.8, density=0.14)


def _moth_antennae(g: MobGrid, ctx):
    # feathered (bipectinate) antennae sweeping up and out, teal tips
    for s in (-1, 1):
        pts = [(s * 0.5, -1.4, 0.2), (s * 1.4, 0.6, -0.4), (s * 2.8, 2.6, -0.6), (s * 3.8, 4.0, 0.0)]
        path = bezier(pts[0], pts[1], pts[2], pts[3], 14)
        g.sweep(path, 0.32, 0.25, 'brass', 0.55, smooth=False)
        for p, t in resample(path, 0.55)[2:-1]:
            L = 0.9 * math.sin(math.pi * t) + 0.25
            for side in (-1, 1):
                g.dot((p[0] - s * 0.15, p[1] + 0.1, p[2] + side * L), 'fur', 0.55 + 0.2 * t, prio=2)
        g.dot(pts[-1], 'core', 0.8, glow=True, prio=5)


def chrono_moth(look, name, part, ctx):
    _f9_ramps(ctx, {'wing': MOTH_WING, 'fur': MOTH_FUR})
    fn = {'body': _moth_body, 'antennae': _moth_antennae, 'wings': _moth_wings}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'wings': 0.6}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── grand_regulator (대시계 집행관) ─────────────────────────────
# The sanctum's magistrate of time: a bronze clock-tower body whose chest is an open arched clock case
# (the dial turns inside it on its spindle, gilt hands on ivory enamel; the movement shows on its back),
# spired bell-tower pauldrons, organ pipes rising behind the shoulders, a teal tabard; a bell helm with a
# visor of teal light under a sunburst of clock hands; one forearm carries a long minute-hand blade, the
# other a geared buckler; a long pendulum swings on its back; plinth-like greaves.

REG_BRONZE = [(14, 9, 6), (30, 19, 11), (52, 33, 18), (80, 50, 26), (114, 72, 36), (152, 98, 50), (192, 132, 72),
              (226, 172, 108)]
REG_GOLD = [(40, 26, 8), (84, 56, 16), (136, 96, 32), (190, 142, 56), (232, 186, 92), (250, 220, 140), (255, 244, 200)]
REG_TABARD = [(6, 22, 20), (12, 40, 36), (20, 62, 56), (32, 88, 78), (50, 118, 104), (78, 150, 132)]


def _reg_torso(g: MobGrid, ctx):
    # tower body: chest widening to the shoulders (x ±9), narrower waist, dark bronze with gilt edges
    g.slab2d(lambda u, v: -2.4 < v < 7.8 and abs(u) < 6.6 + 2.2 * (v + 2.4) / 10.2, (-9.0, -2.6), (9.0, 8.0), 'xy',
             0.0, 5.0, 'copper', bevel=1.4, vfn=lambda u, v, w, e: 0.44 + 0.1 * (v + 2.4) / 10.2 + 0.06 * min(1.0, e))
    g.rbox((-6.4, -8.2, -4.2), (6.4, -1.0, 4.2), 'copper', 0.4, bevel=1.0)
    # the clock case: a vertical cylinder carved out of the chest so the turning dial never clips
    g.carve(lambda x, y, z: x * x + (z + 5.6) ** 2 < 6.3 ** 2 and -6.4 < y < 6.4)
    g.cylinder((0, -6.4, -5.6), (0, 6.4, -5.6), 6.3, 6.3, 'iron', 0.12, hollow=5.6, prio=1)
    g.carve(lambda x, y, z: z < -5.3 and abs(x) < 6.3 and -6.4 < y < 6.4)
    # back wall of the case: a dark movement with brass wheels
    for c, R in (((-2.2, -2.4, -0.3), 2.2), ((2.4, 2.2, -0.2), 2.4)):
        _gear(g, c, R, 9, plane='xy', thick=0.5, mat='brass', val=0.36, tooth_h=0.55, rim=0.55)

    # gilt frame round the case with a shallow arched hood
    def frame(u, v):
        inner = abs(u) < 6.3 and -6.4 < v < 6.4
        outer = abs(u) < 7.4 and -7.4 < v < 7.2 + 0.6 * math.cos(u / 7.4 * math.pi / 2)
        return outer and not inner
    g.slab2d(frame, (-7.6, -7.6), (7.6, 8.0), 'xy', -5.2, 0.5, 'gold',
             vfn=lambda u, v, w, e: 0.46 + 0.22 * min(1.0, e / 0.8))
    g.dot((0, 7.4, -5.9), 'rune', 0.8, glow=True, prio=6)
    for s in (-1, 1):
        g.dot((s * 6.9, 6.8, -5.9), 'rune', 0.6, glow=True, prio=6)
    # spindle pins the dial turns on
    g.cylinder((0, 6.0, -5.6), (0, 6.6, -5.6), 0.5, 0.5, 'gold', 0.7)
    g.cylinder((0, -6.6, -5.6), (0, -6.0, -5.6), 0.5, 0.5, 'gold', 0.7)
    # gilt belt, teal tabard in front of the hips, tassets
    g.rbox((-6.8, -2.2, -4.5), (6.8, -1.0, 4.5), 'gold', 0.45, bevel=0.3)
    g.cloth([(-2.8, -2.4, -4.6), (2.8, -2.4, -4.6)], 7.6, 'tabard', 0.5, tatter=0.12, normal=(0, 0, -1), folds=0.08)
    g.rbox((-0.9, -5.8, -5.0), (0.9, -4.4, -4.6), 'gold', 0.7)
    g.dot((0, -5.1, -5.3), 'rune', 0.7, glow=True, prio=6)
    for s in (-1, 1):
        g.rbox((s * 3.4, -7.6, -4.6), (s * 6.8, -2.6, 4.6), 'copper', 0.5, bevel=0.6)
    # organ pipes rising behind the shoulders (mid-back left clear for the pendulum)
    for s in (-1, 1):
        for k, (x, h) in enumerate(((3.6, 3.0), (5.2, 4.2), (6.8, 3.4))):
            g.cylinder((s * x, 5.0, 5.0), (s * x, 8.0 + h, 5.0), 0.75, 0.75, 'gold', 0.5 + 0.05 * k)
            g.cylinder((s * x, 8.0 + h, 5.0), (s * x, 8.7 + h, 5.0), 0.95, 0.95, 'gold', 0.72)
            g.dot((s * x, 7.2 + h, 4.2), 'void', 0.1, prio=6)
    for s in (-1, 1):
        for y in (0.4, 4.4):
            g.dot((s * 8.2, y, -5.4), 'gold', 0.85, prio=5)


def _reg_clock(g: MobGrid, ctx):
    R = 5.5
    # front: ivory enamel face, gilt bezel, hour marks, two ornate hands; back: brass movement
    g.cylinder((0, 0, -0.2), (0, 0, 0.4), R, R, 'enamel', 0.62)
    _band(g, (0, 0, -0.2), R, 0.55, 'z', 'gold', 0.62)
    for k in range(12):
        a = k * math.pi / 6
        if k % 3 == 0:
            g.capsule((math.cos(a) * (R - 1.8), math.sin(a) * (R - 1.8), -0.5),
                      (math.cos(a) * (R - 0.7), math.sin(a) * (R - 0.7), -0.5), 0.34, 0.3, 'iron', 0.28)
        else:
            g.dot((math.cos(a) * (R - 1.0), math.sin(a) * (R - 1.0), -0.5), 'iron', 0.3, prio=4)
    for a, L, w in ((math.radians(60), 2.9, 0.42), (math.radians(160), 4.3, 0.32)):
        tip = (math.cos(a) * L, math.sin(a) * L, -0.75)
        g.capsule((0, 0, -0.75), tip, w, 0.25, 'gold', 0.5)
        g.blob(vmul(tip, 0.72), 0.55, 'gold', 0.72)
    g.cylinder((0, 0, -1.1), (0, 0, -0.4), 0.8, 0.8, 'rune', 0.7, glow=True)
    # back: brass wheel train
    _gear(g, (0, 0, 0.8), 4.6, 12, plane='xy', thick=0.5, mat='brass', val=0.48, spokes=4, rim=0.8, tooth_h=0.6,
          hub=1.0)
    g.dot((0, 0, 1.3), 'rune', 0.7, glow=True, prio=5)


def _reg_head(g: MobGrid, ctx):
    # bell helm (flared gilt rim), visor slit of teal light, sunburst of clock hands behind
    g.blob((0, 0.8, 0), (3.4, 3.7, 3.4), 'copper', 0.5, top=0.25, cut=lambda x, y, z: y < -2.2)
    g.cylinder((0, -3.2, 0), (0, -1.8, 0), 3.9, 3.9, 'gold', 0.5)
    g.carve(lambda x, y, z: z < -2.0 and abs(x) < 2.6 and 0.0 < y < 1.0)
    g.rbox((-2.6, 0.0, -2.6), (2.6, 1.0, -1.8), 'glow', 0.5, glow=True, prio=2)
    for s in (-1, 1):
        g.eye((s * 1.3, 0.5, -2.7), 0.45, val=0.8, facing=(0, 0, -1), prio=6)
    g.rbox((-0.35, 1.0, -3.6), (0.35, 3.6, -2.8), 'gold', 0.62, bevel=0.2)            # crest ridge
    g.rbox((-0.35, -1.8, -3.6), (0.35, 0.0, -2.9), 'gold', 0.55, bevel=0.2)           # nasal

    # sunburst of clock hands in a plane behind the head
    def rays(u, v):
        d = math.hypot(u, v - 0.6)
        if d < 3.0:
            return False
        if d < 3.7:
            return v > 0.2
        a = math.atan2(v - 0.6, u)
        for k in range(5):
            ak = math.radians(30 + 30 * k)
            L = 8.6 if k == 2 else 7.4 if k in (1, 3) else 6.4
            da = abs(a - ak)
            perp = d * math.sin(da)
            if math.cos(da) <= 0 or d > L:
                continue
            w = 0.45 if d < L - 1.8 else (L - d) * 0.6
            if d < L - 1.8 and d > L - 2.4:
                w = 0.25
            if perp < max(0.3, w):
                return True
        return False
    g.slab2d(rays, (-8.0, 0.0), (8.0, 9.6), 'xy', 2.4, 0.4, 'gold',
             vfn=lambda u, v, w, e: 0.45 + 0.25 * min(1.0, e / 0.6))
    for k in range(5):
        ak = math.radians(30 + 30 * k)
        L = 8.6 if k == 2 else 7.4 if k in (1, 3) else 6.4
        g.dot((math.cos(ak) * (L - 1.2), 0.6 + math.sin(ak) * (L - 1.2), 1.9), 'rune', 0.75, glow=True, prio=6)


def _reg_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    # spired bell-tower pauldron
    g.blob((0, 0.4, 0), (3.6, 2.6, 3.6), 'copper', 0.5, top=0.3, cut=lambda x, y, z: y < -0.6)
    _band(g, (0, -0.4, 0), 3.5, 0.45, 'y', 'gold', 0.55)
    g.cone((-o * 0.6, 2.4, 0), (-o * 0.15, 1, 0), 4.2, 1.4, 'gold', 0.5, 0.8)
    g.dot((-o * 1.25, 6.7, 0), 'rune', 0.8, glow=True, prio=6)
    # upper arm, gear elbow, heavy forearm, gauntlet
    g.capsule((0, -1.0, 0), (0, -8.4, 0), 2.3, 2.0, 'copper', 0.46)
    _band(g, (0, -5.0, 0), 2.25, 0.4, 'y', 'gold', 0.5)
    _gear(g, (-o * 2.3, -9.4, 0), 1.7, 9, plane='zy', thick=0.7, mat='gold', val=0.5, tooth_h=0.55, rim=0.6)
    g.blob((0, -9.4, 0), 2.1, 'iron', 0.45)
    g.capsule((0, -10.4, 0), (0, -16.0, -0.3), 2.5, 2.7, 'copper', 0.5)
    g.rbox((-2.8, -12.4, -2.9), (2.8, -11.6, 2.6), 'gold', 0.5)
    g.blob((0, -18.0, -0.4), (2.8, 2.2, 2.7), 'copper', 0.46, top=0.25)            # gauntlet fist
    for x in (-1.4, -0.45, 0.45, 1.4):
        g.dot((x, -18.4, -3.0), 'gold', 0.75, prio=5)
    if right:
        # minute-hand blade along the outer forearm, arrowhead past the fist
        def blade(u, v):
            if v > -11.0 or v < -26.5:
                return False
            if v < -22.6:
                return abs(u) < (v + 26.5) * 0.5
            if -21.8 < v < -20.4:
                return abs(u) < 1.1
            return abs(u) < 0.5
        g.slab2d(blade, (-2.2, -26.8), (2.2, -10.6), 'zy', o * 3.0, 0.35, 'blade',
                 vfn=lambda u, v, w, e: 0.45 + 0.3 * min(1.0, e / 0.7))
        g.cylinder((o * 2.5, -12.0, 0), (o * 3.4, -12.0, 0), 0.9, 0.9, 'gold', 0.6)
        g.dot((o * 3.5, -12.0, 0), 'rune', 0.8, glow=True, prio=6)
    else:
        # geared buckler on the outside of the forearm
        _gear(g, (o * 3.2, -13.6, 0), 3.4, 12, plane='zy', thick=0.9, mat='gold', val=0.45, spokes=4, rim=0.9,
              tooth_h=0.75, hub=1.0)
        g.cylinder((o * 3.0, -13.6, 0), (o * 4.0, -13.6, 0), 1.1, 0.8, 'copper', 0.6)
        g.dot((o * 4.1, -13.6, 0), 'rune', 0.8, glow=True, prio=6)


def _reg_pendulum(g: MobGrid, ctx):
    # suspension block, long gilt rod with a lyre ornament, big disc bob with a teal sun
    g.rbox((-1.2, -1.2, -0.4), (1.2, 1.2, 1.2), 'copper', 0.5, bevel=0.4)
    g.cylinder((0, -1.0, 0.4), (0, -13.0, 0.9), 0.4, 0.4, 'gold', 0.55)
    _band(g, (0, -6.0, 0.6), 1.3, 0.3, 'z', 'gold', 0.65)
    g.cylinder((0, -15.4, 0.4), (0, -15.4, 1.6), 3.4, 3.4, 'gold', 0.5)
    _band(g, (0, -15.4, 1.6), 3.4, 0.45, 'z', 'gold', 0.7)
    g.cylinder((0, -15.4, 1.6), (0, -15.4, 2.0), 1.4, 1.4, 'rune', 0.6, glow=True)
    for k in range(8):
        a = k * math.pi / 4
        g.capsule((math.cos(a) * 1.6, -15.4 + math.sin(a) * 1.6, 1.9), (math.cos(a) * 2.6, -15.4 + math.sin(a) * 2.6, 1.9),
                  0.25, 0.25, 'rune', 0.5, glow=True)


def _reg_legs(g: MobGrid, ctx):
    for s in (-1, 1):
        x = s * 3.4
        g.blob((x, -1.0, 0), (3.0, 2.6, 2.9), 'copper', 0.45)                      # hip
        g.capsule((x, -1.6, 0), (x, -6.6, -0.2), 2.4, 2.2, 'copper', 0.46)
        g.blob((x, -7.2, -1.2), (2.0, 1.8, 1.4), 'gold', 0.55, top=0.3)            # knee guard
        g.dot((x, -7.2, -2.7), 'rune', 0.8, glow=True, prio=6)
        g.rbox((x - 2.6, -12.0, -2.8), (x + 2.6, -7.8, 2.4), 'copper', 0.48, bevel=0.8)   # plinth greave
        g.rbox((x - 2.8, -9.0, -3.0), (x + 2.8, -8.4, 2.6), 'gold', 0.5)
        g.rbox((x - 3.0, -14.4, -4.2), (x + 3.0, -12.0, 2.8), 'iron', 0.42, bevel=0.6)    # foot
        g.rbox((x - 3.1, -13.0, -4.4), (x + 3.1, -12.6, 2.9), 'gold', 0.5)


def grand_regulator(look, name, part, ctx):
    _f9_ramps(ctx, {'copper': REG_BRONZE, 'gold': REG_GOLD, 'tabard': REG_TABARD, 'blade': BRASS})
    fn = {'torso': _reg_torso, 'clockface': _reg_clock, 'head': _reg_head, 'arm_left': _reg_arm,
          'arm_right': _reg_arm, 'pendulum': _reg_pendulum, 'legs': _reg_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.75, 'arm_left': 0.72, 'arm_right': 0.72, 'legs': 0.72, 'pendulum': 0.55,
                  'head': 0.6, 'clockface': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── cog_drone (톱니 드론) ─────────────────────────────
# A flying saw-toothed cog the regulator lets loose: a thick copper wheel with brass teeth and six spokes
# around a hollow hub (its amber lens-eye floats inside), a little rotor turning on top, glowing cracks of
# the unstable spring core it bursts with, rivets and exhaust vents.

DRONE_COPPER = [(24, 12, 6), (50, 26, 12), (84, 44, 20), (124, 68, 32), (166, 98, 48), (204, 134, 72), (236, 178, 112),
                (252, 220, 170)]


def _drone_gear(g: MobGrid, ctx):
    _gear(g, (0, 0, 0), 4.0, 12, plane='xy', thick=2.0, mat='copper', val=0.48, hole=2.3, spokes=0, rim=1.0,
          tooth_h=1.0, bevel_light=0.2)
    # brass teeth caps and a bevelled rim on the faces
    _band(g, (0, 0, -1.1), 3.2, 0.42, 'z', 'brass', 0.6)
    _band(g, (0, 0, 1.1), 3.2, 0.42, 'z', 'brass', 0.5)
    _band(g, (0, 0, 0), 2.4, 0.5, 'z', 'brass', 0.45)
    # glowing cracks of the core between the spokes, rivets
    for k in range(6):
        a = k * math.pi / 3 + math.pi / 6
        g.dot((math.cos(a) * 3.2, math.sin(a) * 3.2, -1.3), 'brass', 0.85, prio=5)
    for a in (0.5, 2.3, 4.0):
        p0 = (math.cos(a) * 2.6, math.sin(a) * 2.6, -1.1)
        p1 = (math.cos(a + 0.3) * 3.6, math.sin(a + 0.3) * 3.6, -1.1)
        g.capsule(p0, p1, 0.25, 0.25, 'glow', 0.7, glow=True, prio=6)
    # rotor on top (turns with the part about Y — a real rotor)
    g.cylinder((0, 4.6, 0), (0, 6.2, 0), 0.45, 0.45, 'iron', 0.55)
    for s in (-1, 1):
        g.rbox((s * 0.6, 5.9, -0.7), (s * 4.4, 6.3, 0.7), 'brass', 0.55, bevel=0.2)
        g.rbox((s * 3.4, 5.9, -0.7), (s * 4.4, 6.3, 0.7), 'copper', 0.7)
    g.blob((0, 6.5, 0), 0.6, 'brass', 0.72)
    # exhaust vent underneath
    g.cylinder((0, -4.4, 0.6), (0, -5.6, 0.8), 0.8, 0.55, 'iron', 0.45)
    g.dot((0, -5.9, 0.8), 'glow', 0.8, glow=True, prio=6)


def _drone_eye(g: MobGrid, ctx):
    # amber lens in a brass housing, dark iris ring, slit
    g.blob((0, 0, 0), 1.9, 'iron', 0.35)
    _band(g, (0, 0, -1.2), 1.6, 0.4, 'z', 'brass', 0.65)
    g.eye((0, 0, -0.9), 1.2, val=0.55, facing=(0, 0, -1), slit=True, pupil_mat='iron')


def cog_drone(look, name, part, ctx):
    _f9_ramps(ctx, {'copper': DRONE_COPPER, 'glow': AMBER, 'eye': AMBER})
    fn = {'gear': _drone_gear, 'eye': _drone_eye}.get(name)
    if fn is None:
        return None
    g = ctx.grid(0.5)
    fn(g, ctx)
    return g


# ═════════════════════════════ FLOOR 10 · 심연의 핵 ═════════════════════════════

ABYSS_HIDE = [(3, 6, 9), (8, 14, 20), (14, 25, 34), (22, 38, 50), (32, 56, 70), (48, 80, 94), (72, 110, 122)]
OBSIDIAN = [(3, 4, 7), (8, 12, 17), (15, 22, 29), (25, 36, 45), (40, 55, 66), (62, 82, 94), (96, 120, 132)]
DEEPSTONE = [(12, 16, 20), (24, 30, 36), (38, 46, 54), (54, 64, 72), (74, 86, 94), (98, 112, 118), (130, 144, 148)]
SCULK = [(3, 18, 22), (7, 34, 40), (12, 54, 60), (20, 78, 84), (34, 108, 110), (58, 140, 138)]
ABYSS_GLOW = [(8, 62, 62), (16, 124, 120), (40, 204, 190), (110, 240, 226), (190, 255, 246), (255, 255, 255)]
IVORY = [(52, 48, 40), (98, 92, 78), (148, 142, 124), (194, 188, 170), (226, 222, 206), (246, 244, 234)]
GATE_GOLD = [(40, 30, 12), (84, 64, 26), (136, 108, 50), (188, 160, 90), (228, 204, 140), (250, 234, 186),
             (255, 250, 228)]
DEEP_VOID = [(0, 0, 2), (2, 4, 7), (5, 8, 13), (9, 14, 21), (14, 21, 30)]


def _f10_ramps(ctx, extra=None):
    t = {'skin': ABYSS_HIDE, 'obsidian': OBSIDIAN, 'stone': DEEPSTONE, 'sculk': SCULK, 'bone': IVORY,
         'gold': GATE_GOLD, 'void': DEEP_VOID, 'glow': ABYSS_GLOW, 'eye': ABYSS_GLOW, 'core': ABYSS_GLOW,
         'rune': ABYSS_GLOW}
    if extra:
        t.update(extra)
    _ramps(ctx, t)


def _sculk_tufts(g: MobGrid, mats, n, r=1.1, seed=0, region=None, sensors=0):
    """Dark sculk cushions on upward surfaces, a few with glowing sensor stalks."""
    picks = g.clumps(n, r, 'sculk', 0.45, mats=mats, lump=0.2, seed=seed, region=region, up_min=0.35)
    for k, p in enumerate(picks[:sensors]):
        top = (p[0], p[1] + r * 0.6, p[2])
        g.cylinder(top, vadd(top, (0, 1.6, 0)), 0.3, 0.3, 'sculk', 0.6)
        g.dot(vadd(top, (0, 1.9, 0)), 'glow', 0.8, glow=True, prio=6)
    return picks


# ───────────────────────────── void_stalker (심연 추적자) ─────────────────────────────
# A gaunt hunter of the abyss, hunched and stretched: blue-black hide over a ribcage that lets a teal
# heart show through, a ridge of bone spines down its back; an eyeless elongated skull with a needle-toothed
# slit maw and two great listening fans of membrane on bone rays (it hunts by heartbeat); its forearms are
# long scythe blades of black bone with glowing edges; digitigrade legs on clawed toes; sculk veins pulse.

STALKER_MEMBRANE = [(4, 16, 22), (10, 34, 44), (20, 60, 70), (36, 92, 100), (64, 130, 134), (100, 168, 168)]


def _stalker_torso(g: MobGrid, ctx):
    # hunched torso: deep chest leaning forward over a thin waist
    g.blob((0, 2.0, -0.6), (3.4, 3.8, 2.4), 'skin', 0.45, top=0.15)
    g.capsule((0, -6.0, 0.4), (0, 0.0, 0.0), 1.9, 2.1, 'skin', 0.4)
    g.blob((0, -5.6, 0.3), (2.6, 1.4, 1.8), 'skin', 0.38)
    # ribcage: dark slots between bone ribs let the teal heart-light through
    g.blob((0, 2.0, -0.8), (2.2, 2.4, 1.4), 'core', 0.55, glow=True, prio=1, vfn=lambda x, y, z, d: 0.8 - 0.4 * d)
    for y in (0.2, 1.5, 2.8, 4.1):
        g.carve(lambda x, y_, z, y=y: abs(y_ - y - 0.62) < 0.3 and z < -1.2 and abs(x) < 2.6)
        g.rbox((-2.8, y - 0.25, -3.1), (2.8, y + 0.3, -1.6), 'bone', 0.45 + 0.03 * y, bevel=0.25, prio=2)
    g.rbox((-0.4, -0.2, -3.2), (0.4, 5.2, -2.6), 'bone', 0.55)                      # sternum
    # high bony shoulders, collarbones
    for s in (-1, 1):
        g.blob((s * 3.4, 4.8, -0.6), (1.6, 1.4, 1.6), 'skin', 0.5, top=0.25)
        g.capsule((s * 0.6, 5.6, -2.0), (s * 3.2, 5.2, -1.4), 0.4, 0.4, 'bone', 0.55)
    # spine ridge with bone spikes swept back
    for k in range(6):
        y = -4.4 + k * 1.8
        z = 1.6 - 0.2 * k
        g.cone((0, y, z), (0, 0.6, 1), 1.6 + 0.4 * (k % 3), 0.5, 'bone', 0.4, 0.8)
    _vein_walk(g, ['skin'], 5, steps=(6, 12), seed=1, bias=(0, -1, 0), fork=0.12)


def _stalker_head(g: MobGrid, ctx):
    # long eyeless skull tilted forward, smooth bone brow plate
    g.capsule((0, 1.0, 2.2), (0, 0.4, -1.8), 2.4, 2.0, 'skin', 0.45)
    g.capsule((0, 0.0, -1.8), (0, -1.4, -3.6), 2.0, 1.3, 'skin', 0.42)
    g.blob((0, 1.7, -0.4), (2.0, 1.5, 2.6), 'bone', 0.5, top=0.25, cut=lambda x, y, z: y < 1.3)
    # vertical slit maw with needle teeth, glowing throat
    g.carve(lambda x, y, z: z < -2.0 and abs(x) < 0.7 and -3.6 < y < 0.0)
    g.rbox((-0.6, -3.4, -2.8), (0.6, -0.2, -2.2), 'core', 0.55, glow=True, prio=2)
    for s in (-1, 1):
        for k in range(4):
            y = -0.4 - k * 0.85
            g.cone((s * 0.95, y, -3.0 + 0.25 * k), (-s, -0.25, -0.2), 0.8, 0.25, 'bone', 0.6, 0.9)

    # listening fans: flat membranes (zy plane) on bone rays, out at the sides, a glowing nerve arc
    def fan(u, v):        # u = z, v = y relative to the ear root
        d = math.hypot(u, v)
        a = math.atan2(v, u)
        return 0.8 < d < 4.6 and -1.1 < a < 1.45
    for s in (-1, 1):
        root = (s * 2.4, 0.6, 0.8)
        g.slab2d(lambda u, v: fan(u - root[2], v - root[1]), (root[2] - 5, root[1] - 5), (root[2] + 5, root[1] + 5),
                 'zy', root[0] + s * 0.5, 0.25, 'membrane',
                 vfn=lambda u, v, w, e: 0.3 + 0.08 * math.hypot(u - root[2], v - root[1]))
        for a in (-0.95, -0.2, 0.55, 1.3):
            tip = (root[0] + s * 0.6, root[1] + math.sin(a) * 4.9, root[2] + math.cos(a) * 4.9)
            g.capsule((root[0] + s * 0.3, root[1], root[2]), tip, 0.35, 0.25, 'bone', 0.55)
        for k in range(7):
            a = -0.9 + 2.2 * k / 6
            g.dot((root[0] + s * 0.85, root[1] + math.sin(a) * 3.0, root[2] + math.cos(a) * 3.0), 'glow', 0.7,
                  glow=True, prio=5)
    _vein_walk(g, ['skin'], 3, steps=(5, 9), seed=2, bias=(0, 0, 1), fork=0.1)


def _stalker_arm(g: MobGrid, ctx):
    o = ctx.out
    # thin arm hanging from the shoulder, forearm turning into a long scythe of black bone
    g.blob((0, -0.6, 0), 1.4, 'skin', 0.5)
    g.capsule((0, -0.8, 0), (0, -6.4, 0.4), 1.05, 0.8, 'skin', 0.45)
    g.blob((0, -6.8, 0.4), 0.95, 'bone', 0.45)
    g.capsule((0, -7.2, 0.4), (0, -10.6, -0.2), 0.85, 1.0, 'skin', 0.45)
    for k in (-1, 0, 1):
        g.cone((k * 0.45, -10.6, -0.6), (k * 0.2, -0.6, -1), 1.3, 0.25, 'bone', 0.5, 0.85)

    def blade(u, v):        # u = z, v = y (blade grows down and curls forward)
        if v > -9.6 or v < -21.0:
            return False
        t = (-9.6 - v) / 11.4
        zc = 0.6 - 3.6 * t * t
        w = 1.25 * (1 - t) ** 0.7 + 0.12
        return abs(u - zc) < w

    def bval(u, v, w, e):
        t = (-9.6 - v) / 11.4
        zc = 0.6 - 3.6 * t * t
        if u < zc - 0.3 and e < 0.45:
            return ('glow', 0.55 + 0.3 * t, True)
        return ('obsidian', 0.42 + 0.22 * min(1.0, e / 0.8) + 0.1 * t)
    g.slab2d(blade, (-4.2, -21.4), (2.2, -9.2), 'zy', 0.0, 0.4, 'obsidian', vfn=bval, bevel=0.6)
    g.cone((0, -9.8, 1.0), (0, 0.6, 1), 2.0, 0.5, 'bone', 0.4, 0.8)               # elbow spur


def _stalker_legs(g: MobGrid, ctx):
    gy = -12.5
    g.blob((0, -0.6, 0.2), (3.0, 1.8, 1.9), 'skin', 0.4)
    for s in (-1, 1):
        x = s * 1.8
        hip, knee, hock, ball = (x, -1.0, 0.0), (x + s * 0.3, -5.4, -1.8), (x + s * 0.2, -9.4, 1.4), (x, gy + 0.8, -0.6)
        g.limb([hip, knee, hock, ball], [1.35, 0.85, 0.6, 0.5], 'skin', 0.45, joint_mat='bone', joint_val=0.45,
               knob=1.2)
        for k in (-1, 0, 1):
            g.cone(ball, (k * 0.45, -0.25, -1), 1.8, 0.35, 'bone', 0.45, 0.85)
        g.cone((x, -9.4, 1.6), (0, 0.4, 1), 1.4, 0.4, 'bone', 0.45, 0.8)             # hock spur
    _vein_walk(g, ['skin'], 4, steps=(5, 10), seed=5, bias=(0, -1, 0), fork=0.0)


def void_stalker(look, name, part, ctx):
    _f10_ramps(ctx, {'membrane': STALKER_MEMBRANE})
    fn = {'torso': _stalker_torso, 'head': _stalker_head, 'arm_left': _stalker_arm, 'arm_right': _stalker_arm,
          'legs': _stalker_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.55, 'legs': 0.55}.get(name, 0.5))
    if name == 'legs':
        g.light_mul = 0.7
    fn(g, ctx)
    return g


# ───────────────────────────── echo_colossus (울림 거상) ─────────────────────────────
# A hunched giant of abyssal deepstone: a great shoulder hump split by glowing teal fissures, sculk
# cushions with sensor stalks on its shoulders; in its chest a horn-mouthed resonator of concentric stone
# rings around a pulsing core; a small blunt head with a tusked underbite and a glowing seam, crowned by
# wide branching sculk-coral antlers; long gorilla arms with boulder fists; short pillar legs.

def _colossus_torso(g: MobGrid, ctx):
    # massive rounded slabs: chest, a hump rising behind the (low-set) head, belly
    g.rbox((-8.6, -3.2, -5.6), (8.6, 6.4, 5.2), 'stone', 0.46, bevel=2.8, top=0.12)
    g.rbox((-7.0, 3.4, -0.6), (7.0, 10.6, 6.4), 'stone', 0.56, bevel=3.0, top=0.12)
    g.rbox((-6.2, -8.2, -4.2), (6.2, -2.4, 4.4), 'stone', 0.38, bevel=1.8)
    # shoulder slabs (layered stone armour)
    for s_ in (-1, 1):
        g.rbox((s_ * 5.4, 5.0, -3.6), (s_ * 9.2, 7.4, 3.8), 'stone', 0.6, bevel=1.0)
    # horn-mouthed chest socket for the resonator
    g.carve(lambda x, y, z: x * x + y * y < 5.4 ** 2 and z < -3.4)
    g.cylinder((0, 0, -3.6), (0, 0, -2.6), 5.4, 5.4, 'void', 0.2, prio=1)
    _band(g, (0, 0, -5.5), 5.8, 0.6, 'z', 'stone', 0.62)
    # glowing fissures running out from the socket and over the hump; sculk with sensor stalks on top
    _vein_walk(g, ['stone'], 7, steps=(7, 13), seed=1, fork=0.1,
               starts=[(math.cos(a) * 6.6, math.sin(a) * 6.6, -5.4) for a in (0.5, 2.6, 3.6, 5.5)] +
               [(4.0, 10.6, 2.0), (-4.4, 10.6, 3.0), (0.6, 8.0, 6.4)])
    _sculk_tufts(g, ['stone'], 5, 1.6, seed=2, region=lambda x, y, z: y > 6.0, sensors=4)


def _colossus_resonator(g: MobGrid, ctx):
    # concentric annuli stepping back like a horn mouth: stone rim, glow ring, stone, pulsing core
    for k, (R, r_in, z, mat, v) in enumerate(((4.9, 3.6, -0.8, 'stone', 0.58), (3.6, 2.5, -0.1, 'glow', 0.5),
                                             (2.5, 1.5, 0.4, 'stone', 0.4))):
        g.cylinder((0, 0, z - 0.6), (0, 0, z + 0.6), R, R, mat, v, glow=(mat == 'glow'), hollow=r_in, prio=k + 1)
    g.cylinder((0, 0, 0.6), (0, 0, 1.6), 3.0, 3.0, 'void', 0.2, prio=0)
    g.blob((0, 0, 0.6), (1.5, 1.5, 1.1), 'core', 0.85, glow=True, prio=7)
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        g.dot((math.cos(a) * 4.3, math.sin(a) * 4.3, -1.5), 'glow', 0.7, glow=True, prio=6)


def _colossus_head(g: MobGrid, ctx):
    # sunk low and forward between the shoulders (geometry below / ahead of the pivot = hunched neck)
    o = (0, -2.2, -1.6)
    P = lambda p: vadd(p, o)  # noqa: E731
    g.blob(P((0, 0.6, 0.4)), (3.4, 3.2, 3.4), 'stone', 0.5, top=0.2)
    g.rbox(P((-3.8, 1.0, -3.6)), P((3.8, 2.8, -1.0)), 'stone', 0.62, bevel=0.8)          # heavy brow
    g.rbox(P((-3.0, -3.6, -3.9)), P((3.0, -1.0, 1.0)), 'stone', 0.42, bevel=0.9)         # jutting jaw
    g.carve(lambda x, y, z: z < -2.6 + o[2] and abs(x) < 2.2 and -1.7 + o[1] < y < -0.8 + o[1])
    g.rbox(P((-2.2, -1.7, -3.0)), P((2.2, -0.8, -2.4)), 'core', 0.6, glow=True, prio=2)
    for s in (-1, 1):
        g.cone(P((s * 2.3, -1.4, -3.7)), (s * 0.3, 1, -0.2), 2.8, 0.6, 'bone', 0.5, 0.9)  # tusks
        g.eye(P((s * 1.5, 0.3, -3.1)), 0.55, val=0.75, socket=0.4, facing=(0, 0, -1))
    g.capsule(P((0, 2.8, -3.4)), P((0, 0.2, -3.5)), 0.25, 0.25, 'glow', 0.7, glow=True, prio=5)   # glowing seam
    _vein_walk(g, ['stone'], 2, steps=(4, 8), seed=4, bias=(0, -1, 0), fork=0.0)


def _colossus_antlers(g: MobGrid, ctx):
    for s in (-1, 1):
        g.branch((s * 1.6, -3.6, -1.4), (s * 0.9, 1.0, 0), 5.0, 0.95, depth=2, fork=2, spread=0.7, decay=0.68,
                 mat='sculk', val=0.45, bend=(s * 1.2, 0.6, 0), tip='bud', tip_mat='glow', glow_tip=True, seed=3 + s)
        g.cone((s * 1.0, -3.4, -1.6), (s * 0.3, 1.0, 0.1), 3.0, 0.55, 'bone', 0.5, 0.85)


def _colossus_arm(g: MobGrid, ctx):
    o = ctx.out
    g.rbox((-3.4, -3.8, -3.4), (3.4, 1.8, 3.4), 'stone', 0.56, bevel=1.6, top=0.15)        # shoulder boulder
    g.cylinder((0, -9.0, 0.3), (0, -3.0, 0), 2.1, 2.5, 'stone', 0.44)
    g.rbox((-2.6, -10.8, -2.4), (2.6, -8.2, 3.0), 'stone', 0.5, bevel=1.2)                 # elbow
    g.cylinder((0, -17.6, -0.4), (0, -10.6, 0.3), 3.5, 2.6, 'stone', 0.48)                # massive forearm
    g.rbox((-3.8, -23.6, -4.2), (3.8, -17.6, 2.8), 'stone', 0.46, bevel=1.8, top=0.15)     # boulder fist
    for x in (-2.0, -0.7, 0.7, 2.0):
        g.rbox((x - 0.55, -23.0, -4.8), (x + 0.55, -21.4, -4.0), 'stone', 0.64)
    g.crystals((o * 2.6, -12.6, 1.4), (o * 0.7, 0.4, 0.6), n=3, size=2.6, r=0.65, mat='glow', glow=True, seed=7)
    _vein_walk(g, ['stone'], 2, steps=(8, 12), seed=6 + (o > 0), bias=(0, -1, 0), fork=0.1)
    _sculk_tufts(g, ['stone'], 2, 1.3, seed=8 + (o > 0), region=lambda x, y, z: y > -1.0, sensors=1)


def _colossus_legs(g: MobGrid, ctx):
    g.rbox((-5.6, -2.6, -3.0), (5.6, 0.4, 3.4), 'stone', 0.4, bevel=1.0)
    for s in (-1, 1):
        x = s * 3.4
        g.cylinder((x, -11.2, 0), (x, -1.4, 0), 2.7, 2.7, 'stone', 0.45)
        g.rbox((x - 2.2, -7.2, -3.2), (x + 2.2, -4.8, -1.6), 'stone', 0.6, bevel=0.6)      # knee slab
        g.rbox((x - 3.0, -14.4, -4.0), (x + 3.0, -11.2, 2.6), 'stone', 0.42, bevel=1.0)    # flat foot
        for k in (-1, 0, 1):
            g.rbox((x + k * 1.8 - 0.6, -14.4, -4.6), (x + k * 1.8 + 0.6, -12.8, -3.6), 'stone', 0.58)
    _vein_walk(g, ['stone'], 2, steps=(6, 10), seed=9, bias=(0, -1, 0), fork=0.0)


def echo_colossus(look, name, part, ctx):
    _f10_ramps(ctx)
    fn = {'torso': _colossus_torso, 'resonator': _colossus_resonator, 'head': _colossus_head,
          'antlers': _colossus_antlers, 'arm_left': _colossus_arm, 'arm_right': _colossus_arm,
          'legs': _colossus_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.9, 'arm_left': 0.85, 'arm_right': 0.85, 'legs': 0.85, 'head': 0.7, 'resonator': 0.75,
                  'antlers': 0.65}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── abyss_eye (심연의 눈) ─────────────────────────────
# A great eyeball torn from the abyssal heart: ivory sclera webbed with dark veins, a luminous teal iris
# with a void star-pupil; it turns inside armoured lids of black chitin whose rims bristle with bone thorns
# and whose back fans out in a crown of spines; a nerve-root of tentacles trails beneath it.

EYE_VEIN = [(48, 10, 34), (90, 24, 64), (130, 44, 96), (160, 74, 124), (190, 110, 150)]


def _eye_eye(g: MobGrid, ctx):
    R = 5.6

    def sclera(x, y, z, d):
        if z > 2.4:
            return None               # hidden inside the lids (cheaper)
        n = vnorm((x, y, z)) if (x, y, z) != (0, 0, 0) else (0, 0, -1)
        f = -n[2]
        if f > 0.8:                   # iris + star pupil
            ang = math.atan2(n[1], n[0])
            rr = math.sqrt(max(0.0, 1 - f * f))
            star = 0.15 + 0.08 * math.cos(ang * 4)
            if rr < star:
                return ('void', 0.1)
            return ('eye', 0.35 + 0.6 * (rr - star) / 0.45, True)
        if f > 0.74:
            return ('glow', 0.88, True)  # bright limbal ring
        return ('bone', 0.55 + 0.25 * f)
    g.blob((0, 0, 0), R, 'bone', vfn=sclera)
    _vein_walk(g, ['bone'], 7, steps=(5, 9), seed=1, bias=(0, 0, -1), fork=0.2, mat='vein', val=(0.3, 0.7),
               region=lambda x, y, z: z > -3.6)
    for k, v in g.vox.items():
        if v[0] == 'vein':
            v[2] = False


def _eye_lids(g: MobGrid, ctx):
    R0, R1 = 6.3, 7.5
    c = (0, 0, -0.8)        # eye centre in lid coordinates

    def keep(x, y, z):
        q = vsub((x, y, z), c)
        d = vlen(q)
        if d < R0 or d > R1:
            return False
        n = vmul(q, 1 / d)
        if n[2] < 0.15 and (n[0] / 1.0) ** 2 + (n[1] / 0.58) ** 2 < 1.0:
            return False      # almond opening at the front
        return True
    g.blob(c, R1, 'obsidian', 0.45, cut=lambda x, y, z: not keep(x, y, z), top=0.2)
    # bone thorn lashes along the upper and lower lid rims
    for k in range(5):
        t = (k - 2) / 2.6
        for sgn in (1, -1):
            nx = t * 0.9
            ny = sgn * 0.6 * math.sqrt(max(0.0, 1 - t * t))
            nz = -math.sqrt(max(0.0, 1 - nx * nx - ny * ny))
            base = vadd(c, vmul((nx, ny, nz), R0 + 0.5))
            g.cone(base, (nx * 0.3, sgn * 0.9, -0.6), 1.7 - 0.6 * abs(t), 0.4, 'bone', 0.45, 0.85)
    # crown of spines fanning from the back
    for k in range(7):
        a = math.pi * (0.12 + 0.76 * k / 6)
        d = (math.cos(a), math.sin(a), 0.65)
        base = vadd(c, vmul(vnorm(d), R1 - 0.7))
        g.cone(base, d, 4.0 - 1.2 * abs(k - 3) / 3, 0.8, 'obsidian', 0.5, 0.82, curl=(0, 0, 0.9))
    g.capsule(vadd(c, (0, 0, R1 - 0.6)), vadd(c, (0, -0.6, R1 + 2.2)), 1.8, 1.0, 'skin', 0.4)   # nerve root
    _vein_walk(g, ['obsidian'], 5, steps=(6, 12), seed=2, fork=0.15)


def _eye_tendrils(g: MobGrid, ctx):
    n = 6
    for k in range(n):
        a = 2 * math.pi * k / n + 0.3
        ca, sa = math.cos(a), math.sin(a)
        r0 = 2.4
        p0 = (ca * r0, 6.4, sa * r0 + 0.6)
        p1 = (ca * (r0 + 1.6), 2.0, sa * (r0 + 1.6))
        p2 = (ca * (r0 + 0.6), -3.0, sa * (r0 + 0.8) + 1.0)
        p3 = (ca * (r0 + 2.2 * h2(k, 1, 7)), -6.6 + 1.4 * h2(k, 2, 7), sa * (r0 + 1.6) + 1.6)
        g.tentacle(p0, p1, p2, p3, 1.0, 0.35, 'skin', 0.45, suckers=True, sucker_mat='glow',
                   under=(-ca, 0, -sa), tip_mat='glow', glow_tip=True)
    g.blob((0, 6.0, 0.6), (3.0, 1.3, 3.0), 'skin', 0.35)


def abyss_eye(look, name, part, ctx):
    _f10_ramps(ctx, {'vein': EYE_VEIN})
    fn = {'eye': _eye_eye, 'lids': _eye_lids, 'tendrils': _eye_tendrils}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'eye': 0.55, 'lids': 0.75, 'tendrils': 0.55}.get(name, 0.5))
    if name == 'tendrils':
        g.light_mul = 0.7
    fn(g, ctx)
    return g


# ───────────────────────────── hollow_choir (공허 성가대) ─────────────────────────────
# An abyssal chorister floating above the floor: a dark cassock flaring to a hem that frays into smoke-like
# strips, a pale tattered surplice over it and a stole embroidered with glowing sculk notes; a deep hood
# with nothing inside but dark; a cracked porcelain mask with hollow eyes and an O-shaped singing mouth that
# glow from within; long bell sleeves with thin bone-white hands; a broken halo of teal shards turning above.

SURPLICE = [(56, 60, 62), (104, 110, 110), (156, 162, 160), (200, 206, 202), (228, 234, 230), (246, 250, 248)]
CASSOCK = [(3, 6, 9), (7, 13, 18), (11, 22, 29), (17, 34, 42), (25, 49, 58), (38, 68, 78), (56, 92, 100)]


def _choir_robe(g: MobGrid, ctx):
    # cassock: bell-shaped (a frustum), flaring toward the hem; the hem frays into strips
    g.cylinder((0, -9.0, 0.2), (0, 5.6, 0.2), 5.4, 2.7, 'cassock', 0.42)
    g.blob((0, 5.8, 0.2), (3.2, 1.4, 2.4), 'cassock', 0.5)
    for k in range(12):
        a = 2 * math.pi * k / 12 + 0.2
        L = 2.2 + 2.8 * h2(k, 3, g.seed)
        p = (math.cos(a) * 4.9, -8.6, 0.2 + math.sin(a) * 4.9)
        g.capsule(p, vadd(p, (math.cos(a) * 0.7, -L, math.sin(a) * 0.7)), 0.7, 0.35, 'cassock', 0.3)
    # surplice: pale over-robe from the shoulders to the knee, its hem torn into points
    def sur_len(u):
        return 9.0 - 3.2 * h2(int(u * 14), 5, g.seed) - 1.2 * (0.5 + 0.5 * math.sin(u * 37))
    for s_ in range(2):
        pts = [(math.cos(a) * (3.0 + 0.2), 5.4, 0.2 + math.sin(a) * (3.0 + 0.2))
               for a in [math.pi * (s_ + k / 24) for k in range(25)]]
        g.cloth(pts, sur_len, 'surplice', 0.6, tatter=0.0, normal=(0, 0, -1), thick=1, folds=0.08, seed=s_,
                sway=None, prio=3)
    # the cloth columns hang straight; push the lower surplice out over the flare
    g.cylinder((0, -3.4, 0.2), (0, 5.4, 0.2), 4.2, 3.05, 'surplice', 0.58, hollow=2.9, prio=2)
    g.carve(lambda x, y, z: y < -3.4 + 2.4 * h2(int(math.atan2(z - 0.2, x) * 4 + 9), 2, g.seed) and
            g.vox.get(g.key((x, y, z)), ('x',))[0] == 'surplice')
    # stole with glowing notes hanging from the neck in front
    for s in (-1, 1):
        g.rbox((s * 0.95 - 0.55, -7.4, -4.6 + 0.0), (s * 0.95 + 0.55, 5.6, -3.0), 'cassock', 0.62, prio=4)
        for k in range(4):
            g.dot((s * 0.95, 3.8 - k * 2.8, -4.7), 'rune', 0.72, glow=True, prio=6)
    _band(g, (0, 5.6, 0.2), 2.9, 0.45, 'y', 'surplice', 0.72)
    _vein_walk(g, ['cassock'], 5, steps=(5, 10), seed=1, bias=(0, 1, 0), fork=0.1,
               region=lambda x, y, z: y < -6.0)


def _choir_head(g: MobGrid, ctx):
    # deep hood, dark inside
    g.blob((0, 0.4, 0.6), (3.8, 4.4, 3.8), 'cassock', 0.5, top=0.2)
    g.cone((0, 3.4, 2.6), (0, 0.4, 1), 2.6, 1.4, 'cassock', 0.5, 0.62)               # hood point
    g.carve(lambda x, y, z: z < -0.6 and (x / 2.8) ** 2 + (y / 3.4) ** 2 < 1.0)
    g.blob((0, 0.0, 0.4), (2.6, 3.2, 2.2), 'void', 0.15, prio=0, top=0.0)
    _band(g, (0, 0.0, -2.6), 3.2, 0.5, 'z', 'surplice', 0.55)


def _choir_mask(g: MobGrid, ctx):
    # cracked porcelain mask, slightly domed toward −Z, hollow eyes and an O-mouth glowing from within
    g.blob((0, 0, 0.6), (3.0, 3.7, 1.6), 'bone', 0.62, cut=lambda x, y, z: z > 0.4, top=0.15)
    for s in (-1, 1):
        g.carve_blob((s * 1.2, 0.8, -0.6), (0.75, 0.55, 1.6))
        g.dot((s * 1.2, 0.8, 0.2), 'glow', 0.75, glow=True, prio=6)
        g.capsule((s * 1.2, 0.2, -0.95), (s * 1.3, -1.3, -0.85), 0.22, 0.22, 'glow', 0.5, glow=True, prio=5)  # tears
    g.carve_blob((0, -1.8, -0.6), (0.75, 0.95, 1.6))
    g.dot((0, -1.8, 0.2), 'glow', 0.85, glow=True, prio=6)
    _vein_walk(g, ['bone'], 2, steps=(4, 7), seed=3, fork=0.3, val=(0.6, 0.4),
               starts=[(1.6, 3.0, -0.6), (-2.0, -0.6, -0.4)])
    g.rbox((-0.25, 2.2, -1.2), (0.25, 3.4, -0.6), 'gold', 0.6)


def _choir_arm(g: MobGrid, ctx):
    # long bell sleeve, torn, a thin bone-white hand
    g.capsule((0, -0.3, 0), (0, -6.0, -0.2), 1.3, 1.6, 'cassock', 0.44)
    g.cylinder((0, -9.0, -0.5), (0, -6.0, -0.3), 2.2, 1.7, 'cassock', 0.4, hollow=1.0)
    _band(g, (0, -8.7, -0.5), 2.15, 0.4, 'y', 'surplice', 0.62)
    g.cloth([(-2.0, -9.0, 0.2), (0.0, -9.0, 1.6), (2.0, -9.0, 0.2)], 2.6, 'cassock', 0.32, tatter=0.6,
            normal=(0, 0, 1))
    g.capsule((0, -8.0, -0.6), (0, -10.4, -0.9), 0.5, 0.4, 'bone', 0.6)
    for k, x in enumerate((-0.45, 0.0, 0.45)):
        g.capsule((x, -10.4, -0.9), (x * 1.3, -12.2 + 0.2 * k, -1.2), 0.22, 0.2, 'bone', 0.65)


def _choir_halo(g: MobGrid, ctx):
    # broken halo: dark ring in three arcs, teal shards standing on it (turns about Y)
    for a0 in (0.0, 0.34, 0.67):
        g.ring((0, 0, 0), 5.0, 0.38, axis='y', mat='obsidian', val=0.6, arc=(a0 + 0.02, a0 + 0.28))
    for k in range(9):
        a = 2 * math.pi * k / 9 + 0.2
        p = (math.cos(a) * 5.0, 0.2, math.sin(a) * 5.0)
        g.crystal(g.to_vox(p), (math.cos(a) * 0.35, 1, math.sin(a) * 0.35), (1.6 + 0.9 * (k % 2)) / g.vs, 0.45 / g.vs,
                  'glow', glow=True, prio=3)


def hollow_choir(look, name, part, ctx):
    _f10_ramps(ctx, {'cassock': CASSOCK, 'surplice': SURPLICE})
    fn = {'robe': _choir_robe, 'head': _choir_head, 'mask': _choir_mask, 'arm_left': _choir_arm,
          'arm_right': _choir_arm, 'halo': _choir_halo}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'robe': 0.65, 'head': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── abyss_gatekeeper (심연의 문지기) ─────────────────────────────
# A titan bearing the last door to the heart: obsidian fortress plate edged in pale gold, a gorget and a
# belt of chains; its chest is an arched double door inlaid with gold gate-runes, ajar on a seam of teal
# light, ring knockers and studs; a great helm whose visor is a glowing keyhole, ivory ram horns banded in
# gold; bastion pauldrons with crenellations and a lit arrow-slit; rune-banded gauntlets, a broken shackle.

def _gk_torso(g: MobGrid, ctx):
    g.slab2d(lambda u, v: -3.0 < v < 8.6 and abs(u) < 7.6 + 2.4 * (v + 3.0) / 11.6, (-10.2, -3.2), (10.2, 8.8), 'xy',
             0.0, 5.6, 'obsidian', bevel=1.6, vfn=lambda u, v, w, e: 0.42 + 0.08 * (v + 3) / 11.6 + 0.08 * min(1.0, e))
    g.rbox((-7.2, -9.2, -4.8), (7.2, -2.4, 4.8), 'obsidian', 0.36, bevel=1.2)
    # gate recess with a gold arch frame (the door itself is the `gate` part)
    g.carve(lambda x, y, z: z < -4.4 and abs(x) < 6.2 and -7.8 < y < 5.8)
    g.rbox((-6.2, -7.8, -4.8), (6.2, 5.8, -4.2), 'void', 0.15, prio=1)

    def arch(u, v):
        inner = abs(u) < 6.2 and -7.8 < v < 5.8
        outer = abs(u) < 7.4 and -8.8 < v < 6.4 + 1.6 * math.cos(min(1.0, abs(u) / 7.4) * math.pi / 2)
        return outer and not inner
    g.slab2d(arch, (-7.6, -9.0), (7.6, 8.2), 'xy', -5.4, 0.5, 'gold', vfn=lambda u, v, w, e: 0.45 + 0.22 * min(1.0, e))
    g.dot((0, 7.6, -6.0), 'rune', 0.85, glow=True, prio=6)
    # gorget and collar
    g.cylinder((0, 7.4, -0.6), (0, 9.0, -0.6), 4.2, 3.6, 'obsidian', 0.5)
    _band(g, (0, 8.9, -0.6), 3.6, 0.45, 'y', 'gold', 0.6)
    # belt with a hanging chain
    g.rbox((-7.4, -3.4, -5.2), (7.4, -2.0, 5.2), 'gold', 0.42, bevel=0.4)
    g.chain([(6.6, -3.0, -5.4), (3.6, -6.0, -5.9), (-0.4, -4.4, -5.7)], 1.1, 'iron', 0.5)
    # tassets
    for s in (-1, 1):
        g.rbox((s * 3.6, -9.0, -5.0), (s * 7.4, -3.2, 5.0), 'obsidian', 0.46, bevel=0.6)
        g.rbox((s * 3.6, -9.2, -5.1), (s * 7.4, -8.6, 5.1), 'gold', 0.5)
    # gold trim along the shoulder line, rune studs
    g.paint(lambda x, y, z, n, m, v: ('gold', 0.55) if (y > 7.6 and abs(x) > 4.6) else None, ['obsidian'])
    for s in (-1, 1):
        for y in (-0.6, 3.4):
            g.dot((s * 8.6, y, -5.6), 'rune', 0.65, glow=True, prio=6)
    _vein_walk(g, ['obsidian'], 6, steps=(6, 12), seed=1, fork=0.15,
               region=lambda x, y, z: abs(x) > 7.0 or z > 0)


def _gk_gate(g: MobGrid, ctx):
    # arched double door (front = −Z), ajar on a glowing seam
    def door(u, v):
        return abs(u) < 6.0 and -7.0 < v < 4.6 + 1.6 * math.cos(min(1.0, abs(u) / 6.0) * math.pi / 2) and abs(u) > 0.3

    def dval(u, v, w, e):
        side = 1 if u > 0 else -1
        uu = abs(u)
        if 0.9 < e < 1.4:
            return ('gold', 0.5)
        if 2.0 < uu < 4.6 and any(abs(v - y0) < 0.35 for y0 in (-4.4, -1.4, 1.6)):
            return ('rune', 0.6, True)
        if abs(uu - 3.3) < 0.35 and -5.0 < v < 2.8:
            return ('gold', 0.42)
        return ('obsidian', 0.4 + 0.08 * (v + 7) / 13.2 - 0.06 * side)
    g.slab2d(door, (-6.2, -7.2), (6.2, 6.4), 'xy', 0.0, 0.75, 'obsidian', vfn=dval)
    g.rbox((-0.3, -7.0, -0.2), (0.3, 5.8, 0.6), 'glow', 0.75, glow=True, prio=1)          # light through the seam
    for s in (-1, 1):
        _band(g, (s * 1.6, -1.6, -1.1), 0.9, 0.25, 'z', 'gold', 0.7)          # ring knockers
        g.blob((s * 1.6, -0.6, -1.0), 0.45, 'gold', 0.8)
        for y in (-5.8, 3.6):
            g.dot((s * 5.0, y, -1.0), 'gold', 0.85, prio=5)
    g.dot((0, 6.0, -1.0), 'rune', 0.9, glow=True, prio=6)


def _gk_head(g: MobGrid, ctx):
    # great helm, keyhole visor glowing teal, gold crest band and cheek plates
    g.rbox((-3.8, -4.0, -3.8), (3.8, 3.0, 3.8), 'obsidian', 0.48, bevel=1.4, top=0.15)
    g.blob((0, 2.6, 0), (3.6, 1.6, 3.6), 'obsidian', 0.55, cut=lambda x, y, z: y < 2.2)

    def keyhole(x, y):
        return math.hypot(x, y - 0.6) < 1.25 or (abs(x) < 0.55 + 0.3 * (0.6 - y) / 3.0 and -2.8 < y < 0.6)
    g.carve(lambda x, y, z: z < -2.6 and keyhole(x, y))
    g.slab2d(keyhole, (-1.6, -3.0), (1.6, 2.0), 'xy', -2.9, 0.3, 'glow', glow=True,
             vfn=lambda u, v, w, e: 0.5 + 0.35 * min(1.0, e / 0.8))
    g.slab2d(lambda u, v: (math.hypot(u, v - 0.6) < 1.9 or (abs(u) < 1.2 and -3.4 < v < 0.6)) and not keyhole(u, v),
             (-2.2, -3.6), (2.2, 2.8), 'xy', -4.0, 0.3, 'gold', vfn=lambda u, v, w, e: 0.5 + 0.2 * min(1.0, e))
    g.rbox((-0.5, 2.4, -4.2), (0.5, 4.4, 3.6), 'gold', 0.58, bevel=0.3)                    # crest band
    for s in (-1, 1):
        g.rbox((s * 3.0, -4.2, -4.0), (s * 4.0, -0.4, 1.0), 'gold', 0.45, bevel=0.3)       # cheek plates


def _gk_horns(g: MobGrid, ctx):
    # ivory ram horns sweeping out and up, curling forward at the tips, gold bands at the base
    for s in (-1, 1):
        base = (s * 3.4, -3.4, -0.8)
        g.horn(base, (s * 1, 0.25, 0.0), 7.6, 1.5, curl=(s * 0.6, 5.2, -1.6), mat='bone', val=0.42, rings=0.9,
               r_tip=0.35)
        for t in (0.6, 1.4):
            p = vadd(base, (s * t, 0.15 * t, 0))
            g.cylinder(vsub(p, (s * 0.25, 0, 0)), vadd(p, (s * 0.25, 0, 0)), 1.75, 1.7, 'gold', 0.55)


def _gk_arm(g: MobGrid, ctx):
    o = ctx.out
    # bastion pauldron: square tower with corner merlons and lit arrow-slits
    g.rbox((-4.0, -2.4, -4.0), (4.0, 2.0, 4.0), 'obsidian', 0.5, bevel=0.8, top=0.15)
    for cx in (-3.0, 3.0):
        for cz in (-3.0, 3.0):
            g.rbox((cx - 1.0, 2.0, cz - 1.0), (cx + 1.0, 3.6, cz + 1.0), 'obsidian', 0.6)
    g.rbox((-4.1, 1.6, -4.1), (4.1, 2.0, 4.1), 'gold', 0.55)
    g.rbox((-o * 4.2, -1.2, -0.45), (-o * 4.0, 0.9, 0.45), 'glow', 0.7, glow=True, prio=4)
    g.rbox((-0.45, -1.2, -4.2), (0.45, 0.9, -4.0), 'glow', 0.7, glow=True, prio=4)
    # upper arm, elbow, gauntlet with rune bands, fist
    g.capsule((0, -2.4, 0), (0, -9.6, 0), 2.5, 2.3, 'obsidian', 0.44)
    g.blob((0, -10.4, 0), 2.6, 'obsidian', 0.5)
    g.blob((0, -10.6, -2.0), (1.6, 1.5, 1.2), 'gold', 0.55)
    g.cylinder((0, -17.4, -0.3), (0, -11.4, 0), 3.0, 2.7, 'obsidian', 0.48)
    for y in (-13.0, -15.6):
        g.cylinder((0, y - 0.35, -0.2), (0, y + 0.35, -0.2), 3.2, 3.2, 'gold', 0.5)
    g.dot((0, -14.3, -3.3), 'rune', 0.8, glow=True, prio=6)
    g.rbox((-3.2, -21.8, -3.4), (3.2, -17.4, 2.8), 'obsidian', 0.46, bevel=1.2, top=0.2)
    for x in (-1.6, -0.55, 0.55, 1.6):
        g.rbox((x - 0.45, -21.2, -3.9), (x + 0.45, -19.8, -3.2), 'gold', 0.55)
    if o > 0:
        # broken shackle with a dangling chain on the left wrist
        _band(g, (0, -17.0, -0.3), 3.3, 0.5, 'y', 'iron', 0.5)
        g.chain([(o * 3.4, -17.4, -1.0), (o * 3.9, -19.6, -1.6), (o * 3.5, -21.6, -1.2)], 1.1, 'iron', 0.45)
    _vein_walk(g, ['obsidian'], 3, steps=(6, 10), seed=3 + (o > 0), bias=(0, -1, 0), fork=0.1)


def _gk_legs(g: MobGrid, ctx):
    g.rbox((-6.4, -2.6, -3.4), (6.4, 0.6, 3.4), 'obsidian', 0.4, bevel=1.0)
    for s in (-1, 1):
        x = s * 3.6
        g.cylinder((x, -7.6, 0), (x, -1.6, 0), 2.8, 3.0, 'obsidian', 0.44)
        g.blob((x, -7.6, -1.6), (2.4, 2.0, 1.6), 'obsidian', 0.56, top=0.3)            # knee cop
        g.dot((x, -7.6, -3.3), 'rune', 0.85, glow=True, prio=6)
        g.rbox((x - 2.8, -12.4, -2.8), (x + 2.8, -7.8, 2.6), 'obsidian', 0.46, bevel=0.9)
        g.rbox((x - 2.9, -9.2, -2.9), (x + 2.9, -8.6, 2.7), 'gold', 0.5)
        g.rbox((x - 3.0, -14.4, -4.8), (x + 3.0, -12.2, 2.8), 'obsidian', 0.4, bevel=0.7)  # sabaton
        g.rbox((x - 3.1, -13.0, -5.0), (x + 3.1, -12.6, 2.9), 'gold', 0.5)
    _vein_walk(g, ['obsidian'], 3, steps=(5, 9), seed=5, bias=(0, -1, 0), fork=0.0)


def abyss_gatekeeper(look, name, part, ctx):
    _f10_ramps(ctx, {'iron': GUNMETAL})
    fn = {'torso': _gk_torso, 'gate': _gk_gate, 'head': _gk_head, 'horns': _gk_horns, 'arm_left': _gk_arm,
          'arm_right': _gk_arm, 'legs': _gk_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.8, 'arm_left': 0.75, 'arm_right': 0.75, 'legs': 0.75, 'head': 0.6, 'horns': 0.6,
                  'gate': 0.6}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── abyss_spawn (심연의 자식) ─────────────────────────────
# A crawling clot of the abyss: a glossy black tar blob with a crown of nubs and teal fissures, a cluster of
# glowing eyes of every size and a toothed maw; seven short tentacles splay out along the floor.

def _spawn_body(g: MobGrid, ctx):
    g.blob((0, 0.2, 0), (4.8, 4.2, 4.8), 'skin', 0.42, lump=0.1, lump_scale=2.6, top=0.25)
    g.blob((0, -2.6, 0), (4.4, 1.8, 4.4), 'skin', 0.3)
    # eye cluster on the front: different sizes
    for (x, y, r) in ((0.0, 1.0, 1.0), (-2.1, 0.4, 0.7), (2.0, 1.4, 0.75), (-1.0, 2.6, 0.5), (1.3, -0.4, 0.5),
                      (-2.6, 2.0, 0.4), (2.8, -0.2, 0.4)):
        p = g.hit((x, y, -8.0), (0, 0, 1))
        if p:
            g.eye(vadd(p, (0, 0, 0.2)), r, val=0.55, socket=0.3, facing=(x * 0.15, y * 0.1, -1))
    # toothed maw under the eyes
    g.mouth((0, -1.8, -4.2), 3.4, 1.0, depth=1.0, tooth_len=0.6)
    # crown of nubs and fissures
    for k in range(6):
        a = 2 * math.pi * k / 6
        base = (math.cos(a) * 2.2, 3.6, math.sin(a) * 2.2 + 0.4)
        g.cone(base, (math.cos(a) * 0.5, 1, math.sin(a) * 0.5), 1.6 + 0.6 * (k % 2), 0.55, 'obsidian', 0.4, 0.75)
    _vein_walk(g, ['skin'], 6, steps=(5, 10), seed=2, fork=0.2, region=lambda x, y, z: z > -2.5)


def _spawn_tendrils(g: MobGrid, ctx):
    gy = -2.4
    n = 7
    for k in range(n):
        a = 2 * math.pi * k / n + 0.25
        ca, sa = math.cos(a), math.sin(a)
        p0 = (ca * 2.4, 1.6, sa * 2.4)
        p1 = (ca * 4.0, gy + 0.6, sa * 4.0)
        p2 = (ca * 5.6, gy + 0.4, sa * 5.6)
        p3 = (ca * 6.4 - sa * 0.8, gy + 1.6, sa * 6.4 + ca * 0.8)
        g.tentacle(p0, p1, p2, p3, 0.95, 0.35, 'skin', 0.4, suckers=True, sucker_mat='glow', under=(0, -1, 0),
                   tip_mat='glow', glow_tip=True)
    g.blob((0, 1.6, 0), (3.0, 1.2, 3.0), 'skin', 0.32)


def abyss_spawn(look, name, part, ctx):
    _f10_ramps(ctx)
    fn = {'body': _spawn_body, 'tendrils': _spawn_tendrils}.get(name)
    if fn is None:
        return None
    g = ctx.grid(0.55)
    if name == 'tendrils':
        g.light_mul = 0.7
    fn(g, ctx)
    return g


DESIGNS = {
    'gear_hound': gear_hound,
    'clockwork_sentry': clockwork_sentry,
    'spring_jumper': spring_jumper,
    'chrono_moth': chrono_moth,
    'grand_regulator': grand_regulator,
    'cog_drone': cog_drone,
    'void_stalker': void_stalker,
    'echo_colossus': echo_colossus,
    'abyss_eye': abyss_eye,
    'hollow_choir': hollow_choir,
    'abyss_gatekeeper': abyss_gatekeeper,
    'abyss_spawn': abyss_spawn,
}
