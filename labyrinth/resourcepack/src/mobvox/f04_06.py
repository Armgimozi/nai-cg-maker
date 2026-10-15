"""Voxel mob designs — floors 4–6 (잠긴 수로 · 용광로 심장부 · 서리 묘역).  See README.md.

Every normal / elite / add mob of floors 4–6 (bosses live in bosses.py).
Coordinates: part px, origin = the part's pivot, front = −Z, model −X = the mob's left.
Shared helpers at the top (barnacles, icicles, surface picks); one section per mob below.
"""
from __future__ import annotations

import math

from ..util import h2, h3
from ..voxel.mob_kit import MobGrid, fbm3, frame_of, vadd, vlen, vmul, vnorm, vsub  # noqa: F401

# ───────────────────────────── shared helpers ─────────────────────────────


def _surface(g: MobGrid, mats=None, n=8, seed=0, test=None, region=None, min_d=0.0):
    """Up to n spread-out surface points [(p_px, unit_normal)] of mats (hash order + minimum spacing).
    test(normal) / region(x, y, z) filter the candidates."""
    sd = g.seed + 977 + seed
    cands = []
    for key, nrm in g.exposed(mats):
        ln = vlen(nrm)
        if not ln:
            continue
        nn = (nrm[0] / ln, nrm[1] / ln, nrm[2] / ln)
        p = g.px(key)
        if test and not test(nn):
            continue
        if region and not region(*p):
            continue
        cands.append((key, p, nn))
    cands.sort(key=lambda q: h3(q[0][0], q[0][1], q[0][2], sd))
    picks = []
    for key, p, nn in cands:
        if all(vlen(vsub(p, q[0])) >= min_d for q in picks):
            picks.append((p, nn))
            if len(picks) >= n:
                break
    return picks


def _stick(g: MobGrid, origin, direction, out=1.0, max_dist=30.0):
    """Point just outside the first surface hit along a ray (px) — to stud details onto a body."""
    p = g.hit(origin, direction, max_dist)
    if p is None:
        return None
    d = vnorm(direction)
    return vadd(p, vmul(d, -g.vs * out))


def _barnacles(g: MobGrid, mats, n, r=0.8, seed=0, region=None, mat='barnacle', val=0.5, test=None):
    """Clusters of little volcano-shaped barnacles (pale cone + dark hole) on the surface."""
    for k, (p, nn) in enumerate(_surface(g, mats, n, 31 + seed, test=test, region=region, min_d=r * 1.9)):
        rr = r * (0.7 + 0.6 * h2(k, 3, g.seed + seed))
        c = vadd(p, vmul(nn, -rr * 0.2))
        g.cone(c, nn, rr * 1.25, rr, mat, val, val + 0.3, prio=4, r_tip=rr * 0.55)
        g.dot(vadd(c, vmul(nn, rr * 1.25)), 'void', 0.15, prio=6)


def _icicles(g: MobGrid, mats, n, length=(1.4, 3.4), r=0.55, seed=0, region=None, mat='ice', val=0.55,
             glow_tip=False):
    """Tapered icicles hanging from overhangs (exposed voxels with nothing below)."""
    sd = g.seed + 613 + seed
    cands = []
    for key, nrm in g.exposed(mats):
        if (key[0], key[1] - 1, key[2]) in g.vox:
            continue
        p = g.px(key)
        if region and not region(*p):
            continue
        cands.append((key, p))
    cands.sort(key=lambda q: h3(q[0][0], q[0][1], q[0][2], sd))
    picks = []
    for key, p in cands:
        if all(vlen(vsub(p, q)) >= r * 2.6 for q in picks):
            picks.append(p)
            if len(picks) >= n:
                break
    for k, p in enumerate(picks):
        L = length[0] + (length[1] - length[0]) * h2(k, 7, sd)
        base = (p[0], p[1] - g.vs * 0.4, p[2])
        g.cone(base, (0, -1, 0), L, r, mat, val, val + 0.35, prio=4)
        if glow_tip:
            g.dot((p[0], p[1] - L - g.vs * 0.2, p[2]), 'glow', 0.7, glow=True, prio=6)


def _noise_swap(g: MobGrid, mats, to_mat, amount=0.35, scale=2.0, seed=0, v0=0.35, v1=0.8, glow=False):
    """Patches (fbm noise above 1 − amount) of the surface switch to another material (rust, patina, frost)."""
    sd = g.seed + 401 + seed

    def f(x, y, z, n, m, v):
        q = fbm3(x / scale, y / scale, z / scale, sd)
        if q > 1 - amount:
            return (to_mat, v0 + (v1 - v0) * (q - (1 - amount)) / amount, glow)
        return None
    g.paint(f, mats)


def _zigzag(g: MobGrid, a, b, n=6, amp=0.6, r=None, mat='glow', val=0.6, glow=True, seed=0, prio=6, up=None):
    """Lightning-like jagged line from a to b (px)."""
    d = vsub(b, a)
    u, w = frame_of(d)
    if up is not None:
        u = vnorm(up)
    pts = [a]
    for k in range(1, n):
        t = k / n
        side = (1 if k % 2 else -1) * amp * (0.6 + 0.8 * h2(k, seed, 5))
        off = vadd(vmul(u, side), vmul(w, amp * 0.5 * (h2(k, seed, 6) - 0.5)))
        pts.append(vadd(vadd(a, vmul(d, t)), off))
    pts.append(b)
    rr = r or g.vs * 0.5
    g.sweep(pts, rr, rr, mat, val, glow=glow, prio=prio, smooth=False)


def _dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _long(ramp, n=11):
    """Resample a colour ramp to n steps.  Glow ramps need many steps: the budget fitter halves ramps on the
    coarsest levels, and a short glow ramp then stops changing between the pulse frames."""
    out = []
    for k in range(n):
        t = k / (n - 1) * (len(ramp) - 1)
        i = min(int(t), len(ramp) - 2)
        f = t - i
        out.append(tuple(int(round(ramp[i][c] + (ramp[i + 1][c] - ramp[i][c]) * f)) for c in range(3)))
    return out


def _set_glow(ctx, ramp, mats=('glow', 'eye', 'core', 'rune', 'lava')):
    for m in mats:
        ctx.set_ramp(m, _long(ramp))


def _seg_dist(p, a, b):
    ab = vsub(b, a)
    L2 = _dot3(ab, ab) or 1e-9
    t = max(0.0, min(1.0, _dot3(vsub(p, a), ab) / L2))
    return vlen(vsub(p, vadd(a, vmul(ab, t))))


def _fissures(g: MobGrid, mats, n, seed=0, steps=6, step=1.3, r=None, mat='lava', val=0.3, glow=True, region=None,
              fork=0.35, bend=1.1):
    """A few deliberate glowing fissures (molten cracks, frost veins): n jagged lines that wander over the
    surface from spread-out starts, sometimes forking.  Much cheaper and calmer than noise cracks."""
    import random
    rnd = random.Random((g.seed * 13 + seed) & 0xFFFFFFFF)
    rr = r or g.vs * 0.62
    segs = []

    def walk(p, nn, ang, k_left):
        u, w = frame_of(nn)
        cur = p
        for k in range(k_left):
            ang += (rnd.random() - 0.5) * bend
            d = vadd(vmul(u, math.cos(ang)), vmul(w, math.sin(ang)))
            nxt = vadd(cur, vmul(d, step))
            h = g.hit(vadd(nxt, vmul(nn, 2.5)), vmul(nn, -1), 6.0)
            if h is None:
                return
            segs.append((cur, h))
            cur = h
            if k_left - k > 2 and rnd.random() < fork:
                walk(cur, nn, ang + (1.1 if rnd.random() < 0.5 else -1.1), (k_left - k) // 2)
    for p, nn in _surface(g, mats, n, 300 + seed, region=region, min_d=3.0):
        walk(p, nn, rnd.random() * 2 * math.pi, steps)
    if not segs:
        return

    def f(x, y, z, nrm, m, v):
        q = (x, y, z)
        for a, b in segs:
            if _seg_dist(q, a, b) <= rr:
                return (mat, val, glow)
        return None
    g.paint(f, mats)


BARNACLE = [(40, 42, 38), (84, 86, 78), (132, 132, 120), (178, 176, 160), (216, 214, 198), (242, 240, 228)]
KELP = [(12, 20, 10), (24, 40, 16), (42, 64, 22), (68, 92, 32), (100, 124, 48), (140, 158, 76)]

# ═══════════════════════════════ floor 4 · 잠긴 수로 ═══════════════════════════════

# ───────────────────────────── sluice_drowner (수문 익사자) ─────────────────────────────
# A sluice keeper the flood took: bloated grey-green skin, hollow sockets with a cold pinprick of light,
# a rotting oilskin hood and coat with brass buttons and a ring of sluice keys, barnacle crusts on the
# shoulders, kelp draped over everything and dripping water, bare webbed feet, and a rusted gaff hook
# on a chain for dragging prey under.

DROWNED_FLESH = [(18, 28, 30), (34, 50, 52), (56, 78, 78), (84, 110, 106), (118, 142, 132), (156, 176, 162),
                 (196, 210, 194)]
OILSKIN = [(24, 20, 9), (48, 40, 16), (84, 70, 28), (124, 104, 42), (162, 138, 60), (196, 174, 90), (226, 210, 140)]
STAIN = [(10, 22, 14), (20, 40, 24), (34, 62, 34), (56, 88, 46), (86, 116, 64)]
SODDEN = [(16, 16, 16), (30, 30, 28), (48, 46, 42), (70, 66, 58), (96, 90, 78), (126, 118, 102)]
HOLLOW_EYE = [(20, 96, 92), (40, 170, 156), (110, 230, 206), (190, 255, 236), (255, 255, 255)]


def _drowner_ramps(ctx):
    ctx.set_ramp('flesh', DROWNED_FLESH)
    ctx.set_ramp('cloth', OILSKIN)
    ctx.set_ramp('trousers', SODDEN)
    ctx.set_ramp('leaf', KELP)
    ctx.set_ramp('barnacle', BARNACLE)
    _set_glow(ctx, HOLLOW_EYE, ('eye', 'glow'))
    ctx.set_ramp('algae', STAIN)


def _drowner_torso(g: MobGrid, ctx):
    # hunched coat: body block, rounded hump, slumped shoulders, a thick neck
    g.rbox((-4.6, -6.0, -2.6), (4.6, 4.0, 2.6), 'cloth', 0.46, bevel=1.1, top=0.1)
    g.blob((0, 2.2, 1.3), (4.6, 3.6, 2.6), 'cloth', 0.5)
    for s in (-1, 1):
        g.blob((s * 4.3, 3.7, 0.3), (2.1, 1.9, 2.3), 'cloth', 0.52)
    g.capsule((0, 4.2, 0.2), (0, 7.4, -0.5), 1.7, 1.45, 'flesh', 0.42)
    g.blob((0, 4.6, 0.6), (3.2, 1.3, 2.6), 'cloth', 0.4)                       # turned-up collar
    g.mottle(['cloth'], 0.12, 3.0)
    _noise_swap(g, ['cloth'], 'algae', 0.26, 3.6, seed=1, v0=0.35, v1=0.6)
    # coat opening down the front (dark seam) and brass buttons either side
    g.paint(lambda x, y, z, n, m, v: v - 0.22 if abs(x) < 0.4 and z < -1.5 and y < 3.4 else None, ['cloth'])
    for y in (1.8, -0.4):
        for s in (-1, 1):
            p = _stick(g, (s * 1.3, y, -8), (0, 0, 1), out=0.4)
            if p:
                g.dot(p, 'brass', 0.75, prio=5)
    # torn hole over the chest: bloated skin and a barnacle show through
    g.carve_blob((-2.5, 1.0, -2.9), (1.4, 1.6, 1.0))
    g.blob((-2.5, 1.0, -1.9), (1.4, 1.6, 0.9), 'flesh', 0.56, prio=2)
    # belt, buckle, ring of sluice keys at the hip
    g.rbox((-4.8, -3.7, -2.9), (4.8, -2.5, 2.9), 'leather', 0.34)
    g.rbox((-0.8, -3.8, -3.3), (0.8, -2.4, -2.8), 'brass', 0.55)
    g.ring((3.9, -4.7, -2.0), 1.15, 0.35, axis='x', mat='iron', val=0.55)
    for k, (dz, dy) in enumerate(((-0.8, -1.6), (0.6, -2.0))):
        a = (4.0, -5.5, -2.0 + dz * 0.5)
        b = (4.0, -5.5 + dy, -2.0 + dz)
        g.capsule(a, b, 0.32, 0.32, 'brass', 0.55)
        g.rbox((3.7, b[1] - 0.3, b[2] - 0.8), (4.3, b[1] + 0.3, b[2] - 0.1), 'brass', 0.5)
    # sodden coat skirt hanging over the hips (front and back flaps)
    g.cloth([(-4.7, -3.6, -2.75), (4.7, -3.6, -2.75)], 3.4, 'cloth', 0.42, tatter=0.35, normal=(0, 0, -1), seed=1,
            holes=0.0, folds=0.1, fold_period=3.0)
    g.cloth([(4.7, -3.6, 2.75), (-4.7, -3.6, 2.75)], 4.0, 'cloth', 0.4, tatter=0.35, normal=(0, 0, 1), seed=2,
            holes=0.0, folds=0.1, fold_period=3.0)
    # barnacle crusts on the shoulders and hump, kelp draped over a shoulder and down the back
    _barnacles(g, ['cloth'], 8, 0.8, region=lambda x, y, z: y > 2.2)
    g.vine([(-3.4, 5.2, -0.6), (-4.4, 3.0, -2.6), (-3.8, -0.6, -3.1), (-4.2, -4.0, -3.1), (-3.8, -6.6, -3.0)],
           r=0.4, mat='leaf', val=0.42, leaves=0.45, leaf_size=0.9, seed=4)
    g.sprinkle(['cloth'], hang=6, mat='leaf', val=0.45, hang_len=(1.4, 3.4), seed=2)
    g.streaks('water', ['cloth'], density=0.08, length=(1.5, 4.5), val=0.62, val_end=0.45)
    for p, nn in _surface(g, ['algae'], 4, 3, min_d=2.5):        # glowing drowned-algae specks
        g.dot(vadd(p, vmul(nn, g.vs * 0.6)), 'glow', 0.45, glow=True, prio=6)


def _drowner_head(g: MobGrid, ctx):
    # bloated drooping face under a rotted oilskin hood; hollow sockets, slack open mouth
    g.blob((0, 0.7, 0.7), (3.95, 4.0, 3.8), 'cloth', 0.36,
           cut=lambda x, y, z: (z < -0.4 and y < 2.2 and abs(x) < 2.9) or y < -2.4)
    g.paint(lambda x, y, z, n, m, v: v + 0.16 if n[2] < 0 and z < -0.2 else None, ['cloth'])      # hood rim
    _noise_swap(g, ['cloth'], 'algae', 0.3, 2.0, seed=2, v0=0.3, v1=0.7)
    g.blob((0, -0.4, -0.7), (3.0, 3.2, 3.0), 'flesh', 0.6, prio=2)
    g.blob((0, -2.3, -1.4), (2.6, 1.6, 2.3), 'flesh', 0.54, prio=2)           # bloated jowls
    g.rbox((-2.7, 1.0, -3.6), (2.7, 1.8, -2.6), 'flesh', 0.46, bevel=0.4, prio=2)  # heavy sodden brow
    for s in (-1, 1):
        g.eye((s * 1.25, 0.1, -3.2), 0.45, val=0.3, socket=0.65, facing=(s * 0.2, 0, -1))
    g.mouth((0, -2.3, -3.4), 2.0, 1.3, depth=1.0, teeth=False)
    for x in (-0.6, 0.5):
        g.cone((x, -1.7, -3.3), (0, -1, 0), 0.6, 0.3, 'tooth', 0.5, 0.8, prio=4)
    g.dot((-0.35, -0.9, -3.6), 'void', 0.1, prio=6)
    g.dot((0.35, -0.9, -3.6), 'void', 0.1, prio=6)
    # seaweed hair hanging from under the hood, kelp strands off the hood rim
    for s in (-1, 1):
        g.sweep([(s * 2.5, 1.6, -2.2), (s * 3.0, -0.8, -2.6), (s * 2.7, -3.4, -2.5), (s * 3.0, -5.0, -2.1)],
                0.42, 0.3, 'leaf', 0.38)
    g.sprinkle(['cloth'], hang=4, mat='leaf', val=0.45, hang_len=(1.6, 3.6), seed=4)
    _barnacles(g, ['cloth'], 3, 0.65, region=lambda x, y, z: y > 1.5)
    g.streaks('water', ['flesh'], density=0.12, length=(1.0, 2.6), val=0.6, val_end=0.5)


def _drowner_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    # coat sleeve to the elbow with a torn cuff, bloated forearm, long webbed hand
    g.capsule((0, -0.4, 0.1), (0, -6.0, 0.0), 1.8, 1.6, 'cloth', 0.48)
    g.capsule((0, -5.4, 0.0), (0, -6.4, 0.0), 1.85, 1.85, 'cloth', 0.4)
    g.carve(lambda x, y, z: y < -6.0 and h2(int((math.atan2(z, x) + 4) * 3), 1, g.seed) < 0.5 and
            math.hypot(x, z) > 1.3)
    g.capsule((0, -6.2, 0.0), (0, -10.6, -0.3), 1.25, 1.05, 'flesh', 0.56)
    g.blob((0, -11.5, -0.4), (1.3, 1.25, 1.2), 'flesh', 0.56)
    if right:
        # fist closed round the gaff pole (pole runs along Z through the hand)
        for k, z in enumerate((-1.2, -0.4, 0.4)):
            g.capsule((-o * 1.1, -11.4, z), (o * 0.2, -12.9, z), 0.42, 0.38, 'flesh', 0.5 + 0.04 * k)
        g.capsule((o * 1.0, -11.2, -1.0), (o * 0.6, -12.4, -1.6), 0.4, 0.34, 'flesh', 0.56)
    else:
        for k, x in enumerate((-0.85, -0.28, 0.28, 0.85)):
            tip = (x * 1.25, -13.9 + 0.2 * (k % 2), -1.4)
            g.capsule((x, -12.1, -0.9), tip, 0.33, 0.26, 'flesh', 0.52)
            g.dot((tip[0], tip[1] - 0.4, tip[2] - 0.1), 'claw', 0.3, prio=4)
        g.rbox((-1.1, -13.1, -1.25), (1.1, -12.3, -1.05), 'membrane', 0.4)             # webbing
        g.capsule((o * 1.1, -11.0, -0.9), (o * 1.4, -12.4, -1.5), 0.36, 0.3, 'flesh', 0.56)
    _barnacles(g, ['flesh'], 2, 0.5, seed=9 + int(right), region=lambda x, y, z: -10 < y < -6.5)
    _barnacles(g, ['cloth'], 2, 0.6, seed=11, region=lambda x, y, z: y > -2.5)
    g.streaks('water', ['cloth'], density=0.08, length=(1.0, 3.0), val=0.6, val_end=0.45)


def _drowner_hook(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    # waterlogged wooden gaff pole forward from the fist, iron ferrule, big barbed J-hook, a chain
    g.capsule((hx, hy, hz + 2.4), (hx, hy - 0.35, hz - 8.6), 0.55, 0.5, 'wood', 0.42)
    g.bands(['wood'], axis=2, period=2.2, width=0.6, amount=-0.15)
    g.cylinder((hx, hy - 0.3, hz - 7.6), (hx, hy - 0.4, hz - 9.6), 0.85, 0.8, 'iron', 0.42)
    pts = [(hx, hy - 0.4, hz - 9.4), (hx, hy - 0.6, hz - 11.6), (hx, hy - 1.9, hz - 13.3), (hx, hy - 4.1, hz - 13.4),
           (hx, hy - 5.4, hz - 11.8), (hx, hy - 5.0, hz - 10.0), (hx, hy - 3.7, hz - 9.4)]
    g.sweep(pts, 0.85, 0.4, 'iron', 0.45, vfn=lambda t, d, p: ('blade', 0.8) if t > 0.86 else 0.4 + 0.18 * (1 - d))
    g.cone((hx, hy - 3.7, hz - 9.4), (0, 0.3, 1), 1.2, 0.45, 'blade', 0.6, 0.9)                  # barb
    _noise_swap(g, ['iron'], 'rust', 0.5, 1.8, seed=3)
    g.chain([(hx, hy - 0.9, hz - 8.8), (hx + 0.2, hy - 2.6, hz - 8.0), (hx, hy - 4.2, hz - 7.0),
             (hx - 0.2, hy - 5.4, hz - 5.8)], 0.85, 'iron', 0.45)
    g.sprinkle(['iron', 'rust'], hang=3, mat='leaf', val=0.45, hang_len=(1.0, 2.2), seed=7)


def _drowner_legs(g: MobGrid, ctx):
    # sodden torn trousers to the knee, bloated bare calves, wide webbed feet with long nails
    g.rbox((-3.8, -2.4, -2.0), (3.8, 0.6, 2.0), 'trousers', 0.42, bevel=0.7)
    for s in (-1, 1):
        x = s * 2.0
        g.capsule((x, -1.4, 0.0), (x + s * 0.1, -6.6, -0.2), 1.65, 1.5, 'trousers', 0.44)
        g.carve(lambda x_, y, z, x=x: y < -5.6 and abs(x_ - x) > 0.6 and
                h2(int((math.atan2(z, x_ - x) + 4) * 2.5), 2, g.seed) < 0.55 and math.hypot(x_ - x, z) > 1.2)
        g.capsule((x + s * 0.1, -6.4, -0.2), (x, -10.3, 0.1), 1.3, 1.1, 'flesh', 0.56)
        g.blob((x, -11.1, -0.7), (1.45, 0.9, 1.9), 'flesh', 0.52)
        for k, dx in enumerate((-0.9, 0.0, 0.9)):
            tip = (x + dx * 1.2, -11.6, -3.2)
            g.capsule((x + dx, -11.3, -1.6), tip, 0.36, 0.3, 'flesh', 0.5)
            g.dot((tip[0], tip[1] - 0.1, tip[2] - 0.5), 'claw', 0.3, prio=4)
        g.rbox((x - 1.2, -11.9, -2.9), (x + 1.2, -11.6, -1.8), 'membrane', 0.38)
        _barnacles(g, ['flesh'], 1, 0.5, seed=17 + s, region=lambda x_, y, z: -10 < y < -7)
    g.streaks('water', ['trousers'], density=0.12, length=(1.5, 4.0), val=0.58, val_end=0.42)
    g.mottle(['trousers'], 0.12, 2.6)


def sluice_drowner(look, name, part, ctx):
    _drowner_ramps(ctx)
    fn = {'torso': _drowner_torso, 'head': _drowner_head, 'arm_left': _drowner_arm, 'arm_right': _drowner_arm,
          'hook': _drowner_hook, 'legs': _drowner_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.75, 'head': 0.55, 'legs': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── brine_spitter (소금물 뿜개) ─────────────────────────────
# A wall-clinging whelk: a tall coiled shell (a real spiral tube, so the sutures read) with knobbed
# spines on every whorl, a pink-cream lip round the aperture, barnacles, salt crystals and dark algae;
# a glossy muscular foot, a ribbed siphon that spits glowing brine, eyes on long stalks.

SNAIL_SHELL = [(24, 28, 26), (50, 56, 48), (84, 92, 76), (122, 130, 106), (162, 166, 138), (198, 200, 170),
               (226, 228, 202), (246, 246, 232)]
SHELL_LIP = [(66, 36, 42), (124, 76, 78), (190, 128, 118), (228, 180, 160), (248, 224, 206)]
SNAIL_SKIN = [(12, 20, 24), (24, 38, 42), (38, 58, 62), (56, 84, 84), (80, 114, 108), (114, 150, 136),
              (160, 194, 176)]
BRINE_GLOW = [(16, 86, 84), (30, 150, 140), (80, 206, 186), (160, 246, 224), (226, 255, 246), (255, 255, 255)]
SALT = [(116, 128, 128), (176, 188, 184), (218, 226, 222), (244, 248, 246), (255, 255, 255)]
ALGAE = [(12, 28, 18), (22, 48, 28), (36, 72, 40), (58, 100, 56), (92, 132, 78)]


def _spitter_ramps(ctx):
    ctx.set_ramp('shell', SNAIL_SHELL)
    ctx.set_ramp('lip', SHELL_LIP)
    ctx.set_ramp('skin', SNAIL_SKIN)
    ctx.set_ramp('skin2', [(30, 40, 46), (54, 70, 76), (84, 104, 106), (120, 140, 136), (164, 182, 172)])
    _set_glow(ctx, BRINE_GLOW, ('glow', 'eye'))
    ctx.set_ramp('salt', SALT)
    ctx.set_ramp('band', [(20, 30, 32), (36, 56, 56), (56, 84, 80), (84, 116, 104), (118, 148, 128)])
    ctx.set_ramp('algae', ALGAE)
    ctx.set_ramp('barnacle', BARNACLE)


class _Coil:
    """Gastropod coil: a tube whose radius shrinks by q per turn, wound round axis A (aperture at th = 0)."""

    def __init__(self, B, A, u, r0=3.0, q=0.72, turns=4.3, h0=4.1):
        self.B, self.A, self.u = B, vnorm(A), u
        self.w = vnorm((u[1] * self.A[2] - u[2] * self.A[1], u[2] * self.A[0] - u[0] * self.A[2],
                        u[0] * self.A[1] - u[1] * self.A[0]))
        self.r0, self.q, self.turns, self.h0 = r0, q, turns, h0

    def at(self, t):
        th = 2 * math.pi * self.turns * t
        f = self.q ** (th / (2 * math.pi))
        r = self.r0 * f
        s = self.h0 * (1 - f) / (1 - self.q)
        rad = vadd(vmul(self.u, math.cos(th)), vmul(self.w, math.sin(th)))
        return vadd(vadd(self.B, vmul(self.A, s)), vmul(rad, r * 0.95)), rad, r


def _spitter_shell(g: MobGrid, ctx):
    co = _Coil((0.0, -2.8, -1.4), (0.0, 0.76, 0.65), (1.0, 0.0, 0.0))
    n = 90
    samples = [co.at(k / n) for k in range(n + 1)]
    pts = [q[0] for q in samples]

    def shade(t, d, p):
        c, rad, r = co.at(t)
        a = _dot3(vsub(p, c), co.A) / max(0.5, r)
        if 0.05 < a < 0.34:
            return ('band', 0.3 + 0.2 * (1 - d))              # dark spiral band below the shoulder
        rib = 0.07 if int(t * co.turns * 11) % 2 else 0.0      # growth lines
        return 0.5 + 0.22 * (1 - d) + 0.12 * a + rib
    g.sweep(pts, co.r0, 0.4, 'shell', 0.5, rfn=lambda t: co.at(t)[2] + 0.1, smooth=False, vfn=shade)
    # aperture: hollow the tube mouth, pink flared lip, dark mantle inside
    p0, rad0, r0 = samples[0]
    tang = vnorm(vsub(samples[1][0], p0))
    g.carve_blob(vadd(p0, vmul(tang, -0.4)), (2.5, 2.5, 2.5))
    g.ring(vadd(p0, vmul(tang, -0.6)), r0 * 0.92, 0.55, axis='z', mat='lip', val=0.6)
    g.blob(vadd(p0, vmul(tang, 1.2)), 2.1, 'skin2', 0.2, prio=2, top=0)
    # big knobbed spines on the shoulder of the first two whorls, a small apex knob
    for k in range(6):
        t = 0.08 + k * 0.075
        c, rad, r = co.at(t)
        base = vadd(vadd(c, vmul(rad, r * 0.6)), vmul(co.A, r * 0.55))
        L = 1.0 + 2.0 * (1 - t / 0.5)
        g.cone(base, vadd(rad, vmul(co.A, 0.8)), L, 0.45 + 0.45 * (1 - t / 0.5), 'shell', 0.5, 0.68, prio=3)
    g.blob(samples[-1][0], 0.6, 'shell', 0.85)
    # algae on the upper whorls, barnacles, a few salt crystals, glowing brine beads on the lip
    g.moss_paint(coverage=0.3, mat='algae', val=0.6, mats=['shell'], scale=3.0, up_min=0.6)
    _barnacles(g, ['shell', 'algae', 'band'], 4, 0.65, seed=1)
    for p, nn in _surface(g, ['lip'], 3, 9, min_d=1.8):
        g.dot(vadd(p, vmul(nn, g.vs)), 'glow', 0.45, glow=True, prio=6)


def _spitter_foot(g: MobGrid, ctx):
    # glossy muscular foot with a frilled skirt; head bulge at the front with sensory tentacles and the
    # ribbed brine siphon; the visceral hump rises into the shell aperture
    g.blob((0, -0.9, 0.6), (3.5, 1.5, 7.4), 'skin', 0.48, top=0.3)
    g.blob((0, -1.8, 0.6), (4.3, 0.7, 7.9), 'skin', 0.36)
    g.blob((0, 1.2, -1.6), (2.6, 2.0, 3.4), 'skin2', 0.42)
    g.blob((0, 0.3, -6.3), (2.5, 2.1, 2.6), 'skin', 0.5)
    for s in (-1, 1):
        g.tentacle((s * 1.1, -0.2, -8.2), (s * 1.8, -0.5, -9.4), (s * 2.5, -1.3, -10.0), (s * 2.9, -1.9, -10.2),
                   0.48, 0.24, 'skin', 0.52, suckers=False)
    g.sweep([(0, 1.6, -6.6), (0, 3.0, -8.2), (0, 3.6, -9.9)], 0.8, 0.62, 'skin2', 0.45,
            vfn=lambda t, d, p: 0.38 + 0.2 * (1 - d) + (0.16 if int(t * 7) % 2 else 0))
    g.ring((0, 3.7, -10.1), 0.65, 0.3, axis='z', mat='skin2', val=0.7)
    g.blob((0, 3.7, -10.5), 0.6, 'glow', 0.4, glow=True, prio=5)
    for k in range(3):
        g.dot((0.3 * (k - 1), 3.2 - 0.9 * k, -11.2 - 0.4 * k), 'glow', 0.5, glow=True, prio=6)
    g.mottle(['skin', 'skin2'], 0.1, 3.0)


def _spitter_eyes(g: MobGrid, ctx):
    # two long eye stalks with glowing eyes, and a shorter lower pair of feelers
    for s in (-1, 1):
        g.sweep([(s * 0.8, -2.4, 0.4), (s * 1.3, -0.4, 0.0), (s * 2.1, 1.4, -0.4), (s * 2.6, 2.4, -0.7)],
                0.5, 0.36, 'skin', 0.5)
        g.eye((s * 2.7, 2.8, -0.8), 0.7, val=0.32, facing=(s * 0.3, 0.2, -1), slit=False)
        g.ring((s * 2.6, 2.3, -0.7), 0.55, 0.22, axis='y', mat='skin', val=0.65)
        g.sweep([(s * 1.0, -2.6, -0.6), (s * 1.8, -2.8, -1.8), (s * 2.4, -3.4, -2.4)], 0.36, 0.22, 'skin', 0.55)


def brine_spitter(look, name, part, ctx):
    _spitter_ramps(ctx)
    fn = {'shell': _spitter_shell, 'foot': _spitter_foot, 'eyes': _spitter_eyes}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'shell': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── rust_eel (녹물 장어) ─────────────────────────────
# A rust-water eel: rust-brown hide with dark mottling and rust-iron scutes on the flanks, a pale belly,
# a jagged electric lateral line and rows of glowing electroplaques, glowing cyan eyes and gill slits,
# needle teeth, a spined dorsal frill with sparking tips and a leaf-shaped tail paddle.

EEL_SKIN = [(10, 8, 7), (22, 15, 11), (38, 24, 16), (60, 36, 22), (90, 54, 30), (128, 78, 40), (170, 110, 60),
            (210, 156, 100)]
EEL_BELLY = [(58, 40, 28), (106, 78, 56), (162, 128, 94), (206, 178, 138), (234, 212, 178)]
ELECTRIC = [(18, 66, 66), (36, 146, 146), (104, 222, 212), (186, 255, 244), (240, 255, 255), (255, 255, 255)]
EEL_FIN = [(28, 13, 9), (66, 30, 17), (114, 56, 29), (164, 90, 46), (208, 138, 82), (232, 184, 132)]


def _eel_ramps(ctx):
    ctx.set_ramp('skin', EEL_SKIN)
    ctx.set_ramp('belly', EEL_BELLY)
    _set_glow(ctx, ELECTRIC, ('glow', 'eye'))
    ctx.set_ramp('membrane', EEL_FIN)


def _eel_lateral(g: MobGrid, y0=0.3, amp=0.55, period=1.6, w=0.36, zr=(-99, 99)):
    """Electric lateral line: a jagged glowing band along both flanks."""
    def f(x, y, z, n, m, v):
        if n[0] == 0 or not (zr[0] < z < zr[1]):
            return None
        t = (z / period) % 2.0
        zig = amp * (t if t < 1 else 2 - t) * 2 - amp
        if abs(y - y0 - zig) < w:
            return ('glow', 0.3, True)
        return None
    g.paint(f, ['skin'])


def _eel_body_shade(x, y, z, r):
    if y < -r * 0.45:
        return ('belly', 0.45 + 0.2 * (y + r) / r)
    if y > r * 0.3:
        return 0.3 + 0.08 * (y / r)
    return 0.44 + 0.1 * (y / r)


def _eel_front(g: MobGrid, ctx):
    pts = [(0, 0.3, -7.6), (0, 0.0, -2.0), (0, -0.1, 3.0), (0, -0.2, 7.6)]
    g.sweep(pts, 2.75, 2.75, 'skin', 0.45, rfn=lambda t: 2.55 + 0.4 * math.sin(math.pi * t),
            vfn=lambda t, d, p: _eel_body_shade(p[0], p[1], p[2], 2.9))
    g.mottle(['skin'], 0.12, 2.4, seed=1)
    _noise_swap(g, ['skin'], 'rust', 0.28, 1.6, seed=7, v0=0.45, v1=0.8)
    # rust-iron scutes in a row on each flank above the lateral line
    for s in (-1, 1):
        for k in range(6):
            z = -6.0 + k * 2.3
            p = _stick(g, (s * 6, 1.6, z), (-s, 0, 0))
            if p:
                g.rbox((p[0] - 0.45, p[1] - 0.6, z - 0.9), (p[0] + 0.45, p[1] + 0.7, z + 0.9), 'iron', 0.42,
                       bevel=0.3, prio=3)
    _noise_swap(g, ['iron'], 'rust', 0.6, 1.2, seed=2, v0=0.3, v1=0.7)
    _eel_lateral(g)
    # electroplaque spots below the line
    for s in (-1, 1):
        for k in range(7):
            p = _stick(g, (s * 6, -1.0, -6.4 + k * 2.1), (-s, 0, 0), out=0.2)
            if p:
                g.dot(p, 'glow', 0.45, glow=True, prio=6)
    # pectoral fins
    for s in (-1, 1):
        g.sweep([(s * 2.4, -0.9, -5.4), (s * 3.8, -1.3, -4.6), (s * 4.8, -1.7, -3.2)], 1.1, 0.4, 'membrane', 0.5,
                sq=(1, 0.32, 1), vfn=lambda t, d, p: 0.4 + 0.3 * t + (0.15 if int(t * 6) % 2 else 0))
    g.streaks('rust', ['skin'], density=0.14, length=(1.0, 2.4), val=0.5, val_end=0.35)


def _eel_back(g: MobGrid, ctx):
    pts = [(0, 0.0, -1.2), (0, -0.1, 3.5), (1.3, 0.0, 8.0), (-1.3, 0.1, 12.6), (0.6, 0.3, 16.4), (-0.2, 0.4, 18.4)]

    def rfn(t):
        return 2.5 * (1 - t) ** 0.95 + 0.3
    g.sweep(pts, 2.5, 0.45, 'skin', 0.45, rfn=rfn,
            vfn=lambda t, d, p: _eel_body_shade(p[0], p[1], p[2], rfn(t) + 0.2))
    g.mottle(['skin'], 0.12, 2.4, seed=3)
    _noise_swap(g, ['skin'], 'rust', 0.28, 1.6, seed=8, v0=0.45, v1=0.8)
    _eel_lateral(g, y0=0.25, amp=0.45, zr=(-2, 13))

    # tail paddle (vertical leaf-shaped membrane) and a low ventral fin along the underside
    def paddle(z, y):
        if not 9.0 < z < 20.6:
            return False
        t = (z - 9.0) / 11.6
        hw = 0.6 + 1.9 * math.sin(math.pi * min(1.0, t * 1.1)) ** 0.9
        return abs(y - 0.3) < hw
    g.slab2d(paddle, (10, -3.5), (21, 3.8), plane='zy', depth=0.0, half=0.25, mat='membrane',
             vfn=lambda u, v, w_, e: 0.4 + 0.3 * min(1.0, e / 1.2) + (0.14 if int(u / 1.1) % 2 else 0))

    def ventral(z, y):
        if not 1.0 < z < 11.0:
            return False
        r = rfn((z + 1.2) / 18.6)
        return -r - 1.3 < y < -r + 0.6
    g.slab2d(ventral, (0, -4.5), (12, 0), plane='zy', depth=0.0, half=0.25, mat='membrane',
             vfn=lambda u, v, w_, e: 0.38 + 0.25 * min(1.0, e / 0.8))
    g.dot((0.0, 0.3, 20.0), 'glow', 0.5, glow=True, prio=6)
    g.streaks('rust', ['skin'], density=0.14, length=(1.0, 2.0), val=0.5, val_end=0.35, seed=2)


def _eel_fin(g: MobGrid, ctx):
    # dorsal frill (mostly behind its pivot so the tail sway keeps it on the back), spined rays
    def top(z):
        t = (z + 4.5) / 15.0
        return -1.3 + 3.4 * math.sin(math.pi * min(1.0, max(0.0, t))) ** 0.7

    def mask(z, y):
        if not -4.5 < z < 10.5:
            return False
        ray = (z + 4.5) % 2.0
        return -2.0 < y < top(z) - (0.5 if 0.8 < ray < 1.4 else 0)
    g.slab2d(mask, (-5, -2.5), (11, 3.5), plane='zy', depth=0.0, half=0.25, mat='membrane',
             vfn=lambda u, v, w_, e: 0.34 + 0.35 * (v + 2) / 5 + (0.12 if (u + 4.5) % 2.0 < 0.5 else 0))
    for k in range(8):
        z = -4.0 + k * 2.0
        h = top(z) + 0.9
        g.sweep([(0, -1.6, z + 0.4), (0, h * 0.5, z + 0.1), (0, h, z - 0.3)], 0.3, 0.25, 'skin', 0.6)
        g.dot((0, h + 0.4, z - 0.4), 'glow', 0.45, glow=True, prio=6)


def _eel_head(g: MobGrid, ctx):
    g.blob((0, 0.3, 0.6), (3.1, 2.6, 3.6), 'skin', 0.46)
    g.blob((0, 0.0, -2.8), (2.3, 1.6, 2.6), 'skin', 0.5)
    for s in (-1, 1):
        g.blob((s * 2.4, -0.5, 1.2), (1.3, 1.4, 1.8), 'skin', 0.5)                 # jaw muscles
        g.cone((s * 0.9, -1.0, -4.4), (0, -1, -0.25), 1.7, 0.42, 'tooth', 0.55, 0.85, prio=4)   # fangs
    g.carve(lambda x, y, z: y < -1.1 and z < 1.0 and abs(x) < 1.8)          # mouth roof (the jaw sits below)
    g.rbox((-1.7, -1.2, -4.6), (1.7, -0.9, 1.0), 'mouth', 0.2, prio=2)
    # armoured brow plates and a ridge running back over the skull
    for s in (-1, 1):
        g.capsule((s * 1.2, 1.9, -2.6), (s * 1.9, 2.0, 0.6), 0.6, 0.7, 'iron', 0.45)
    g.capsule((0, 2.4, -1.4), (0, 2.6, 3.0), 0.55, 0.6, 'iron', 0.5)
    _noise_swap(g, ['iron'], 'rust', 0.55, 1.0, seed=4, v0=0.3, v1=0.7)
    for s in (-1, 1):
        g.eye((s * 2.0, 0.9, -1.6), 0.65, val=0.35, socket=0.3, facing=(s * 0.8, 0.2, -0.6))
        g.teeth((s * 1.55, -1.0, 0.6), (s * 0.7, -1.0, -4.3), 5, 0.9, r=0.3, direction=(0, -1, 0), seed=s + 2)
        # glowing gill slits
        for k in range(3):
            z = 1.2 + k * 0.8
            g.paint(lambda x, y, zz, n, m, v, z=z, s=s: ('glow', 0.5, True)
                    if abs(zz - z) < 0.3 and -0.6 < y < 1.2 and x * s > 0 and n[0] * s > 0 else None, ['skin'])
        # electric barbels
        g.sweep([(s * 0.9, -0.4, -4.4), (s * 1.6, -0.9, -5.4), (s * 2.6, -0.6, -5.8)], 0.3, 0.25, 'skin', 0.6)
        g.dot((s * 2.9, -0.5, -5.9), 'glow', 0.5, glow=True, prio=6)
    g.mottle(['skin'], 0.14, 1.4, seed=5)


def _eel_jaw(g: MobGrid, ctx):
    g.blob((0, 0.0, 0.6), (1.85, 0.85, 3.2), 'skin', 0.45,
           vfn=lambda x, y, z, d: ('belly', 0.5) if y < -0.2 else 0.45)
    g.paint(lambda x, y, z, n, m, v: ('mouth', 0.3) if n[1] > 0 and abs(x) < 1.25 else None, ['skin', 'belly'])
    for s in (-1, 1):
        g.teeth((s * 1.4, 0.5, 2.4), (s * 0.6, 0.5, -2.2), 5, 0.8, r=0.3, direction=(0, 1, 0), seed=s + 7)
        g.cone((s * 0.5, 0.5, -2.6), (0, 1, -0.2), 1.4, 0.38, 'tooth', 0.55, 0.85, prio=4)


def rust_eel(look, name, part, ctx):
    _eel_ramps(ctx)
    fn = {'head': _eel_head, 'jaw': _eel_jaw, 'body_front': _eel_front, 'body_back': _eel_back,
          'fin': _eel_fin}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body_front': 0.55, 'body_back': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── bubble_jelly (거품 해파리) ─────────────────────────────
# A jellyfish floating in a skin of bubble film: a scalloped bell with glowing radial canals, a margin
# ring and four glowing horseshoe gonads, a fringe of short tentacles; the bubble is drawn as swirling
# iridescent film streaks, a bright highlight window and crackling sparks (it stays see-through);
# frilled oral arms and long thin tentacles beaded with stinging lights.

JELLY_BELL = [(18, 36, 66), (30, 66, 104), (54, 110, 152), (92, 160, 200), (142, 206, 232), (196, 238, 250)]
JELLY_GLOW = [(30, 90, 140), (60, 160, 220), (130, 220, 255), (200, 245, 255), (240, 255, 255), (255, 255, 255)]
FILM = [(96, 140, 176), (150, 196, 224), (196, 228, 246), (230, 248, 255), (255, 255, 255)]
FILM2 = [(120, 110, 170), (170, 156, 214), (212, 198, 240), (238, 228, 255), (255, 255, 255)]
FRILL = [(52, 50, 110), (86, 86, 160), (130, 134, 208), (178, 186, 238), (222, 228, 255)]


def _jelly_ramps(ctx):
    ctx.set_ramp('membrane', JELLY_BELL)
    _set_glow(ctx, JELLY_GLOW, ('glow', 'core', 'eye'))
    ctx.set_ramp('film', FILM)
    ctx.set_ramp('film2', FILM2)
    ctx.set_ramp('tendril', FRILL)


def _jelly_bell(g: MobGrid, ctx):
    def cut(x, y, z):
        a = math.atan2(z, x)
        yb = -2.2 - 1.5 * max(0.0, math.cos(a * 8)) ** 0.7
        return y < yb
    g.blob((0, -1.4, 0), (6.6, 6.2, 6.6), 'membrane', 0.5, cut=cut, top=0.25)
    g.carve_blob((0, -3.9, 0), (5.3, 4.0, 5.3))
    g.blob((0, 3.7, 0), (1.6, 0.8, 1.6), 'membrane', 0.7)

    def pattern(x, y, z, n, m, v):
        if n[1] < 0 and y < -1.0:
            return None
        r = math.hypot(x, z)
        a = math.atan2(z, x)
        # four glowing horseshoe gonads round the top
        if y > 1.0 and 1.3 < r < 2.9:
            q = ((a - math.pi / 4) % (math.pi / 2)) - math.pi / 4
            if abs(q) < 0.55 and not (abs(q) < 0.2 and r < 2.1):
                return ('core', 0.35, True)
        # 8 glowing radial canals + 8 faint ones between
        if r > 2.4:
            q = ((a + math.pi / 8) % (math.pi / 4)) - math.pi / 8
            if abs(q) * r < 0.32:
                return ('glow', 0.22, True)
        # margin ring canal
        if -2.6 < y < -2.0:
            return ('glow', 0.25, True)
        return None
    g.paint(pattern, ['membrane'])
    g.sprinkle(['membrane'], hang=16, mat='tendril', val=0.6, hang_len=(1.0, 2.6), seed=3)


def _jelly_bubble(g: MobGrid, ctx):
    R = 8.7
    L = vnorm((-0.75, 0.35, -0.55))
    sd = g.seed + 5
    vs = g.vs
    n = int(R / vs) + 2
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            for k in range(-n, n + 1):
                p = (i * vs, j * vs, k * vs)
                d = vlen(p)
                if abs(d - R) > vs * 0.55:
                    continue
                q = vmul(p, 1 / d)
                hl = _dot3(q, L)
                if hl > 0.972:
                    g.put(i, j, k, 'film', 0.95 if hl > 0.99 else 0.75, False, 3)
                    continue
                warp = 0.9 * fbm3(p[0] / 5, p[1] / 5, p[2] / 5, sd)
                qy = q[1] * 0.8 + q[0] * 0.48 + q[2] * 0.36                     # tilted swirl axis
                b = math.sin((qy * 2.2 + warp) * math.pi * 2)
                if b > 0.9:
                    band = int(math.floor(qy * 2.2 + warp))
                    g.put(i, j, k, 'film' if band % 2 else 'film2', 0.55 + 0.25 * q[1], False, 2)
                elif q[1] < -0.86:
                    g.put(i, j, k, 'film', 0.4, False, 2)
    # crackling sparks on the film
    for a0, y0, y1 in ((0.4, -3.0, 4.0), (2.6, 2.0, -5.0), (4.4, -1.0, 5.5)):
        pa = vmul(vnorm((math.cos(a0), y0 / R, math.sin(a0))), R)
        pb = vmul(vnorm((math.cos(a0 + 0.7), y1 / R, math.sin(a0 + 0.7))), R)
        _zigzag(g, pa, pb, n=7, amp=0.7, mat='glow', val=0.45, seed=int(a0 * 10))
    # little satellite bubbles
    for c, r in (((7.6, 6.8, -3.4), 1.0), ((-8.4, -5.0, 3.0), 0.8), ((3.6, -8.2, -6.4), 0.7)):
        g.ring(c, r, vs * 0.5, axis='z', mat='film', val=0.8)


def _jelly_tentacles(g: MobGrid, ctx):
    top = 5.0
    # four frilled oral arms twisting down from the bell centre
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        pts = []
        for j in range(7):
            t = j / 6
            r = 0.6 + 1.6 * t
            aa = a + 1.2 * t
            pts.append((math.cos(aa) * r, top - 9.5 * t, math.sin(aa) * r))
        g.sweep(pts, 1.0, 0.45, 'tendril', 0.5, vfn=lambda t, d, p: 0.42 + 0.3 * (1 - d) + 0.1 * t)
        for j in range(1, 7):
            p = pts[j]
            t = j / 6
            side = (math.cos(a + 1.2 * t + math.pi / 2), 0, math.sin(a + 1.2 * t + math.pi / 2))
            for s in (-1, 1):
                g.blob(vadd(p, vmul(side, s * (0.9 - 0.3 * t))), (0.7, 0.9, 0.7), 'tendril', 0.62, prio=2,
                       lump=0.25, lump_scale=0.8, seed=k * 9 + j * 2 + s)
    # long thin tentacles from the margin ring, beaded with stinging lights
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        R = 5.0
        x0, z0 = math.cos(a) * R, math.sin(a) * R
        L = 9.0 + 3.0 * h2(k, 1, g.seed)
        sway = 0.9 * (1 if k % 2 else -1)
        pts = [(x0, top - 0.2, z0), (x0 * 1.04 + sway * 0.3, top - L * 0.35, z0 * 1.04),
               (x0 * 0.98 - sway * 0.2, top - L * 0.7, z0 * 0.98 + sway * 0.3),
               (x0 * 0.95 + sway * 0.4, top - L, z0 * 0.95)]
        g.sweep(pts, 0.3, 0.25, 'tendril', 0.55)
        for j in range(1, 5):
            t = j / 5
            p = pts[0]
            q = (p[0] + (pts[-1][0] - p[0]) * t, p[1] + (pts[-1][1] - p[1]) * t, p[2] + (pts[-1][2] - p[2]) * t)
            hp = g.hit(vadd(q, (2, 0, 0)), (-1, 0, 0), 4) or g.hit(vadd(q, (-2, 0, 0)), (1, 0, 0), 4)
            if hp:
                g.dot(hp, 'glow', 0.4, glow=True, prio=6)
        g.dot(pts[-1], 'glow', 0.55, glow=True, prio=6)


def bubble_jelly(look, name, part, ctx):
    _jelly_ramps(ctx)
    fn = {'bell': _jelly_bell, 'bubble': _jelly_bubble, 'tentacles': _jelly_tentacles}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'bell': 0.62, 'bubble': 0.6}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── verdigris_crab (녹청 집게 파수꾼, elite) ─────────────────────────────
# A copper sluice-guardian built as a crab: a broad riveted carapace of overlapping copper plates eaten
# green by verdigris, gold trim and glowing teal runes on the rim (elite), a valve wheel and pipe on its
# back, serrated front margin and flank spines; brass telescope eyes with glowing lenses; an oversized
# crusher claw and a slimmer cutter claw with serrated fingers; eight jointed copper legs.

COPPER = [(20, 10, 6), (42, 20, 11), (74, 36, 18), (112, 58, 28), (152, 84, 42), (192, 118, 64), (226, 164, 106),
          (248, 214, 172)]
VERDIGRIS = [(12, 38, 32), (24, 70, 58), (44, 114, 92), (80, 162, 130), (134, 204, 172), (192, 236, 212)]
TEAL_GLOW = [(18, 86, 76), (38, 166, 146), (106, 228, 198), (188, 255, 234), (240, 255, 250), (255, 255, 255)]
GOLD_TRIM = [(58, 38, 10), (116, 80, 22), (186, 142, 50), (230, 194, 94), (250, 232, 158), (255, 250, 220)]


def _crab_ramps(ctx):
    ctx.set_ramp('brass', COPPER)
    ctx.set_ramp('patina', VERDIGRIS)
    _set_glow(ctx, TEAL_GLOW, ('glow', 'eye', 'rune', 'core'))
    ctx.set_ramp('orn', GOLD_TRIM)
    ctx.set_ramp('barnacle', BARNACLE)


def _crab_patina(g, amount=0.42, scale=2.4, seed=0):
    _noise_swap(g, ['brass'], 'patina', amount, scale, seed=seed, v0=0.3, v1=0.75)


def _crab_carapace(g: MobGrid, ctx):
    seams = (-4.6, 0.6, 5.8)

    def shade(x, y, z, d):
        v = 0.44 + 0.16 * (y + 2.4) / 8.0
        if any(abs(z - q) < 0.5 for q in seams) and y > -1.6:
            return v - 0.24                                         # plate seams
        if abs(x) < 0.9 and y > 2.0:
            return v + 0.14                                         # dorsal keel
        return v
    g.blob((0, -0.4, 0.8), (13.6, 6.0, 11.2), 'brass', 0.5, vfn=shade,
           cut=lambda x, y, z: y < -2.4 or z < -9.6)
    g.blob((0, -2.6, 0.6), (12.4, 1.4, 10.2), 'dark', 0.28, top=0.0)
    g.capsule((0, 3.6, -8.6), (0, 4.6, 8.0), 0.8, 0.6, 'brass', 0.62)             # raised keel ridge
    # serrated front margin with a rostrum between the eyes, three spines on each flank
    for k in range(6):
        x = -6.0 + k * 2.4
        g.cone((x, -0.9, -9.4), (x * 0.06, 0.1, -1), 1.4, 0.6, 'brass', 0.5, 0.85)
    g.cone((0, 0.6, -9.2), (0, 0.2, -1), 2.2, 0.9, 'brass', 0.55, 0.85)
    for s in (-1, 1):
        for k, (x, z, L) in enumerate(((9.6, -6.6, 2.2), (12.0, -3.6, 2.8), (13.2, 0.2, 3.8))):
            g.cone((s * x, -0.4, z), (s * 0.85, 0.3, -0.5 + 0.2 * k), L, 0.8, 'brass', 0.5, 0.88)
    # gold trim band round the rim, glowing runes on the front edge
    g.paint(lambda x, y, z, n, m, v: ('orn', 0.6) if -2.4 < y < -1.5 and (n[0] or n[2]) else None, ['brass'])
    sd = g.seed + 77

    def aged(x, y, z, n, m, v):
        q = fbm3(x / 4.0, y / 4.0, z / 4.0, sd)
        if any(abs(z - s_) < 1.1 for s_ in seams) or y < -0.4 + 3.6 * q or q > 0.7:
            return ('patina', 0.32 + 0.45 * q)
        return None
    g.paint(aged, ['brass'])
    # recessed mouth plate between the claws: dark maxilliped plates and a glowing vent
    g.rbox((-3.4, -2.0, -10.4), (3.4, 0.6, -9.0), 'dark', 0.3, bevel=0.4, prio=3)
    for x in (-2.2, -0.75, 0.75, 2.2):
        g.rbox((x - 0.55, -2.2, -10.9), (x + 0.55, 0.2, -10.2), 'brass', 0.62, bevel=0.2, prio=4)
    g.rbox((-2.8, 0.7, -10.0), (2.8, 1.3, -9.4), 'core', 0.3, glow=True, prio=4)
    for z in seams:
        for x in (-7.5, -4.0, 4.0, 7.5):
            p = _stick(g, (x, 12, z + 1.0), (0, -1, 0), out=0.4)
            if p:
                g.dot(p, 'orn', 0.7, prio=5)
    # valve wheel on a stem behind the keel, a pipe along the back, two glowing portholes
    g.cylinder((0, 4.6, 3.0), (0, 6.6, 3.0), 0.7, 0.7, 'iron', 0.45)
    g.gear((0, 6.9, 3.0), 2.4, teeth=8, axis='y', thick=0.8, mat='orn', val=0.5, spokes=4)
    g.sweep([(3.2, 5.0, -3.0), (3.8, 5.0, 2.0), (3.2, 4.0, 6.4), (2.4, 1.6, 9.8)], 0.65, 0.65, 'brass', 0.6)
    for s in (-1, 1):
        p = _stick(g, (s * 7.0, 12, 4.2), (0, -1, 0), out=0.3)
        if p:
            g.ring(p, 1.25, 0.38, axis='y', mat='orn', val=0.55)
            g.blob(p, (0.9, 0.55, 0.9), 'core', 0.35, glow=True, prio=5)
    _barnacles(g, ['brass', 'patina'], 6, 0.8, seed=1, region=lambda x, y, z: y > 1.0 and z > -4)


def _crab_eyes(g: MobGrid, ctx):
    # brass telescope eyes on jointed stalks, glowing lenses facing forward
    for s in (-1, 1):
        g.capsule((s * 1.5, -3.6, 0.6), (s * 2.2, -0.4, 0.2), 0.75, 0.65, 'brass', 0.5)
        g.blob((s * 2.2, -0.4, 0.2), 0.85, 'orn', 0.55)
        g.capsule((s * 2.2, -0.4, 0.2), (s * 3.0, 2.0, -0.2), 0.65, 0.6, 'brass', 0.55)
        g.cylinder((s * 3.0, 2.4, 0.9), (s * 3.0, 2.4, -1.3), 1.05, 1.15, 'brass', 0.45)
        g.ring((s * 3.0, 2.4, -1.3), 1.15, 0.32, axis='z', mat='orn', val=0.7)
        g.blob((s * 3.0, 2.4, -1.45), (0.85, 0.85, 0.45), 'eye', 0.35, glow=True, prio=5)
    _crab_patina(g, 0.3, 1.4, seed=2)


def _crab_claw(g: MobGrid, ctx):
    o = ctx.out
    big = ctx.name == 'claw_right'
    k = 1.0 if big else 0.82
    P = (lambda x, y, z: (o * x * k, y * k, z * k))
    # folded guard pose: merus out from under the carapace corner, carpus back in, and a big raised
    # palm held in front of the face with the open pincer pointing forward-inward
    lift = 2.4
    P = (lambda x, y, z: (o * x * k, (y + lift) * k if y > -1.0 else y * k, z * k))
    root, elbow, wrist = P(-1.0, -1.8, 2.6), P(1.6, 0.2, -1.4), P(-0.6, 1.6, -3.8)
    g.limb([root, elbow, wrist], [1.5 * k, 1.8 * k, 1.9 * k], 'brass', 0.48, joint_mat='orn', joint_val=0.55,
           knob=1.15)
    palm_a, palm_b = P(-1.4, 2.2, -4.8), P(-4.6, 2.6, -6.6)
    g.capsule(palm_a, palm_b, 2.6 * k, 3.0 * k, 'brass', 0.52, sq=(1.0, 1.05, 0.8))
    g.ring(P(-1.0, 2.1, -4.6), 2.3 * k, 0.42, axis='x', mat='orn', val=0.6)
    up = [P(-6.6, 4.2, -7.4), P(-8.8, 4.0, -8.0), P(-10.8, 2.4, -8.0)]
    lo = [P(-6.6, 0.8, -7.4), P(-8.6, 0.0, -7.9), P(-10.4, 1.2, -7.8)]
    g.sweep([P(-5.6, 3.6, -7.0)] + up, 1.55 * k, 0.4, 'brass', 0.55)
    g.sweep([P(-5.6, 1.4, -7.0)] + lo, 1.3 * k, 0.38, 'brass', 0.5)
    for j in range(3 if big else 4):
        t = (j + 0.5) / (3.5 if big else 4.5)
        pu = tuple(up[0][a] + (up[2][a] - up[0][a]) * t for a in range(3))
        pl = tuple(lo[0][a] + (lo[2][a] - lo[0][a]) * t for a in range(3))
        pu = (pu[0], pu[1] - 1.0 * k, pu[2])
        pl = (pl[0], pl[1] + 0.9 * k, pl[2])
        if big:
            g.blob(pu, 0.55, 'orn', 0.65, prio=4)
            g.blob(pl, 0.55, 'orn', 0.65, prio=4)
        else:
            g.cone(pu, (0, -1, -0.3), 0.8, 0.32, 'orn', 0.6, 0.9, prio=4)
            g.cone(pl, (0, 1, -0.3), 0.7, 0.3, 'orn', 0.6, 0.9, prio=4)
    # rivet row along the top of the palm, a glowing rune plate on its outer face
    for j in range(4):
        q = tuple(palm_a[a] + (palm_b[a] - palm_a[a]) * j / 3 for a in range(3))
        p = _stick(g, (q[0], q[1] + 8, q[2]), (0, -1, 0), out=0.4)
        if p:
            g.dot(p, 'orn', 0.75, prio=5)
    g.runes(P(-3.0, 2.4, -7.6), (0, 0, -1), w=3.2, h=2.6, mat='rune', val=0.3, density=0.9, seed=4 + int(big))
    _noise_swap(g, ['brass'], 'patina', 0.3, 2.4, seed=3 + int(big), v0=0.35, v1=0.7)
    g.paint(lambda x, y, z, n, m, v: ('patina', 0.4) if y < -0.4 * k and m == 'brass' else None, ['brass'])
    _barnacles(g, ['brass', 'patina'], 2, 0.6, seed=5 + int(big), region=lambda x, y, z: y > 3)


def _crab_legs(g: MobGrid, ctx):
    gy = -7.2
    for s in (-1, 1):
        for k, z in enumerate((-5.6, -1.9, 1.9, 5.6)):
            back = (k - 1.5) / 1.5
            R = (s * 9.0, 3.0, z)
            K = (s * 14.0, 6.4, z * 1.2 + back * 0.8)
            F = (s * 17.2, gy, z * 1.45 + back * 2.0)
            g.limb([R, K, F], [1.2, 0.95, 0.4], 'brass', 0.48, joint_mat='orn', joint_val=0.6, knob=1.2)
    _crab_patina(g, 0.38, 2.2, seed=6)


def verdigris_crab(look, name, part, ctx):
    _crab_ramps(ctx)
    fn = {'carapace': _crab_carapace, 'eyes': _crab_eyes, 'claw_left': _crab_claw, 'claw_right': _crab_claw,
          'legs': _crab_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'carapace': 0.8, 'legs': 0.75, 'claw_left': 0.55, 'claw_right': 0.6}.get(name, 0.5))
    if name == 'legs':
        g.light_mul = 0.5
    fn(g, ctx)
    return g


# ───────────────────────────── floodling (범람 정령, add) ─────────────────────────────
# A little flood spirit: a water-drop body with spiralling foam, glowing eyes and a heart-light, stubby
# splash arms, a whirlpool column to the floor with a splash crown, and a breaking-wave crest.

FLOOD_WATER = [(10, 28, 46), (16, 56, 92), (28, 96, 146), (56, 146, 198), (114, 196, 234), (186, 234, 252),
               (238, 252, 255)]
FOAM = [(150, 198, 220), (200, 232, 244), (236, 250, 255), (255, 255, 255)]
FLOOD_GLOW = [(40, 120, 170), (90, 190, 240), (160, 230, 255), (220, 250, 255), (255, 255, 255)]


def _flood_ramps(ctx):
    ctx.set_ramp('water', FLOOD_WATER)
    ctx.set_ramp('foam', FOAM)
    _set_glow(ctx, FLOOD_GLOW, ('glow', 'eye', 'core'))


def _swirl(g: MobGrid, mats, period=3.0, width=0.13, mat='foam', val=0.6, k=1.0):
    def f(x, y, z, n, m, v):
        a = math.atan2(z, x) / (2 * math.pi)
        t = (y / period + a * k) % 1.0
        if t < width:
            return (mat, val + 0.2 * (1 - t / width))
        return None
    g.paint(f, mats)


def _flood_body(g: MobGrid, ctx):
    g.blob((0, 0.6, 0), (4.6, 4.8, 4.6), 'water', 0.5, top=0.2, lump=0.08, lump_scale=2.0)
    # whirlpool column down to the floor (ground = y −9.6) and a splash crown round its foot
    g.sweep([(0, -2.6, 0), (0.7, -5.0, 0.3), (-0.6, -7.2, -0.3), (0.2, -9.0, 0.1), (0, -9.5, 0)], 2.6, 1.0, 'water',
            0.42, rfn=lambda t: 2.7 - 1.9 * t + 0.6 * t * t)
    g.blob((0, -9.3, 0), (3.4, 0.5, 3.4), 'water', 0.5)
    for k in range(9):
        a = 2 * math.pi * k / 9
        g.cone((math.cos(a) * 2.8, -9.2, math.sin(a) * 2.8), (math.cos(a), 1.6, math.sin(a)), 1.6 + 0.6 * (k % 2),
               0.5, 'foam', 0.5, 0.9)
    _swirl(g, ['water'], period=3.6, width=0.12, k=1.7)
    # face: two glowing eyes, a dark open mouth; a heart-light in the chest
    for s in (-1, 1):
        g.eye((s * 1.5, 1.6, -4.0), 0.75, val=0.35, socket=0.25, facing=(s * 0.2, 0.1, -1))
    g.carve_blob((0, -0.4, -4.4), (1.2, 0.6, 0.8))
    g.blob((0, -0.4, -3.6), (1.1, 0.5, 0.5), 'water', 0.1, prio=2)
    g.blob((0, -2.4, -3.0), 0.9, 'core', 0.3, glow=True, prio=4)
    # stubby splash arms curling up and out, foam tips
    for s in (-1, 1):
        g.sweep([(s * 3.6, 0.2, -0.4), (s * 5.4, -0.4, -0.8), (s * 6.6, 0.6, -1.2), (s * 6.9, 2.0, -1.0)], 1.2, 0.5,
                'water', 0.5)
        for j in range(3):
            g.cone((s * 6.7, 1.6, -1.0), (s * (0.6 - 0.4 * j), 1, -0.4 + 0.4 * j), 1.1, 0.4, 'foam', 0.6, 0.95)
    # droplets in the air
    for p in ((-5.2, 3.6, -2.0), (5.0, 4.4, 1.6), (-3.4, -5.2, -3.6), (4.2, -6.8, 2.6), (1.2, 5.6, -4.4)):
        g.blob(p, 0.45, 'water', 0.75)


def _flood_crest(g: MobGrid, ctx):
    # breaking-wave crest rising off the head and curling forward, foam along the lip
    def mask(z, y):
        if y < -3.8 or y > 4.4:
            return False
        t = (y + 3.8) / 8.2
        front = -2.6 - 3.0 * t ** 1.6
        back = 5.0 - 6.4 * t
        if t > 0.72:
            curl = (t - 0.72) / 0.28
            back = front + 2.6 - 1.2 * curl
            front -= 0.6 * curl
        return front < z < back
    g.slab2d(mask, (-7, -4), (6, 5), plane='zy', depth=0.0, half=0.75, mat='water', bevel=1.2,
             vfn=lambda u, v, w, e: 0.4 + 0.08 * (v + 4) + 0.12 * min(1.0, e))
    g.paint(lambda x, y, z, n, m, v: ('foam', 0.65) if (y > 2.6 or (n[2] < 0 and y > 0.5)) else None, ['water'])
    for p in ((0.2, 4.6, -6.6), (-0.3, 3.4, -7.4), (0.4, 2.0, -7.0), (0.0, 5.2, -4.6)):
        g.dot(p, 'foam', 0.9, prio=4)


def floodling(look, name, part, ctx):
    _flood_ramps(ctx)
    fn = {'body': _flood_body, 'crest': _flood_crest}.get(name)
    if fn is None:
        return None
    g = ctx.grid(0.5)
    fn(g, ctx)
    return g


# ═══════════════════════════════ floor 5 · 용광로 심장부 ═══════════════════════════════

EMBER = [(70, 14, 4), (130, 30, 6), (190, 58, 10), (236, 100, 20), (255, 150, 40), (255, 200, 96), (255, 236, 176),
         (255, 252, 236)]
SOOT_IRON = [(9, 9, 11), (20, 20, 24), (34, 34, 40), (52, 52, 58), (76, 74, 80), (106, 102, 104), (144, 138, 134),
             (190, 182, 172)]

# ───────────────────────────── slag_golem (슬래그 골렘) ─────────────────────────────
# Furnace slag that got up and walked: a hunched lumpy mass of black basalt-slag with a pale ash crust,
# molten cracks glowing through it, an open furnace-heart in the chest ringed by rebar stubs, scrap
# iron (a half-sunk cog, a riveted plate, bent rebar) stuck through the hide, molten metal dripping from
# the belly and the knuckles of its huge dragging fists.

SLAG = [(12, 9, 8), (26, 20, 17), (44, 34, 28), (66, 52, 42), (94, 74, 58), (126, 102, 80), (160, 134, 108)]
ASH_CRUST = [(64, 58, 54), (96, 88, 80), (130, 120, 108), (166, 154, 138), (202, 192, 174)]


def _slag_ramps(ctx):
    ctx.set_ramp('stone', SLAG)
    ctx.set_ramp('crust', ASH_CRUST)
    ctx.set_ramp('iron', SOOT_IRON)
    _set_glow(ctx, EMBER)


def _slag_skin(g: MobGrid, n=6, seed=0, crust=0.4, steps=8):
    """Pale ash crust on the upper surfaces + a few deliberate molten fissures."""
    sd = g.seed + 91 + seed
    g.paint(lambda x, y, z, nn, m, v: ('crust', 0.35 + 0.4 * fbm3(x / 2, y / 2, z / 2, sd))
            if nn[1] > 0 and fbm3(x / 3.6, y / 3.6, z / 3.6, sd) > 1 - crust else None, ['stone'])
    _fissures(g, ['stone', 'crust'], n, seed=seed, steps=steps, step=1.5, r=g.vs * 0.75, fork=0.45)


def _slag_drips(g: MobGrid, mats, n, seed=0, length=(1.2, 2.6), r=0.55, region=None):
    """Molten drops hanging off the undersides (glowing)."""
    sd = g.seed + 211 + seed
    cands = [(k, g.px(k)) for k, nrm in g.exposed(mats) if (k[0], k[1] - 1, k[2]) not in g.vox and
             (region is None or region(*g.px(k)))]
    cands.sort(key=lambda q: h3(q[0][0], q[0][1], q[0][2], sd))
    picks = []
    for k, p in cands:
        if all(vlen(vsub(p, q)) > 2.2 for q in picks):
            picks.append(p)
            if len(picks) >= n:
                break
    for j, p in enumerate(picks):
        L = length[0] + (length[1] - length[0]) * h2(j, 3, sd)
        g.cone((p[0], p[1] - g.vs * 0.3, p[2]), (0, -1, 0), L, r, 'lava', 0.35, 0.6, glow=True, prio=5)


def _slag_torso(g: MobGrid, ctx):
    g.blob((0, 0.2, 0.4), (8.4, 7.0, 5.6), 'stone', 0.45, lump=0.1, lump_scale=4.0, top=0.15)
    for s in (-1, 1):
        g.blob((s * 6.8, 4.4, 0.4), (4.0, 3.4, 4.0), 'stone', 0.5, lump=0.12, lump_scale=3.0, seed=2 + s)
    g.blob((0, 4.6, 2.8), (5.6, 3.8, 3.4), 'stone', 0.48, lump=0.12, lump_scale=3.0, seed=5)
    g.blob((0, -4.6, -1.4), (6.0, 2.8, 4.2), 'stone', 0.4, lump=0.1, lump_scale=3.0, seed=6)      # sagging gut
    _slag_skin(g, 7)
    # furnace heart in the chest, ringed by rebar stubs
    g.carve_blob((0, 1.0, -5.4), (2.9, 3.1, 2.2))
    g.blob((0, 1.0, -3.8), (2.7, 2.9, 1.7), 'lava', 0.5, glow=True, prio=2,
           vfn=lambda x, y, z, d: 0.75 - 0.45 * d)
    for k in range(6):
        a = 2 * math.pi * (k + 0.3) / 6
        b = (math.cos(a) * 3.2, 1.0 + math.sin(a) * 3.4, -4.6)
        g.cone(b, (math.cos(a) * 0.7, math.sin(a) * 0.7, -0.8), 1.4 + 0.5 * (k % 2), 0.42, 'rust', 0.4, 0.65, prio=4)
    # scrap stuck in the hide: a half-sunk cog on the left shoulder, a riveted plate, bent rebar on the hump
    g.gear((-7.6, 6.0, 0.6), 2.6, teeth=8, axis='x', thick=0.9, mat='iron', val=0.5, spokes=3)
    g.plate((3.0, 2.6, -5.8), (6.6, 6.0, -4.6), 'iron', 0.45, rivet_mat='iron', rivet_step=1.6)
    for k, (b, d) in enumerate((((-2.4, 7.6, 2.6), (-0.3, 1, 0.5)), ((1.2, 8.2, 3.4), (0.2, 1, 0.3)),
                                ((3.8, 7.0, 2.2), (0.6, 1, 0.6)))):
        tip = vadd(b, vmul(vnorm(d), 3.6 - 0.6 * k))
        bend = vadd(tip, (0.9 * (1 if k % 2 else -1), -0.6, 0.8))
        g.sweep([vadd(b, (0, -1.2, 0)), tip, bend], 0.42, 0.36, 'rust', 0.5)
    # molten metal pouring from the furnace heart down the gut, dripping off its underside
    g.paint(lambda x, y, z, n, m, v: ('lava', 0.35 + 0.1 * math.sin(y * 2), True)
            if n[2] < 0 and abs(x + 0.25 * math.sin(y * 1.3)) < 0.9 and -6.5 < y < -1.6 else None, ['stone', 'crust'])
    _slag_drips(g, ['stone', 'crust'], 4, seed=1, region=lambda x, y, z: y < -4)


def _slag_head(g: MobGrid, ctx):
    # small brutal slag skull sunk between the shoulders: heavy brow, one glowing slit for eyes, crack mouth
    g.blob((0, -0.4, 0.0), (3.6, 3.2, 3.6), 'stone', 0.45, lump=0.1, lump_scale=2.0, top=0.15)
    g.rbox((-3.8, 0.4, -3.9), (3.8, 2.0, -2.2), 'stone', 0.55, bevel=0.6)                 # brow ledge
    g.blob((0, -2.4, -1.6), (2.8, 1.4, 2.4), 'stone', 0.4)                              # jaw
    g.carve(lambda x, y, z: abs(x) < 2.6 and -0.6 < y < 0.4 and z < -2.6)
    g.rbox((-2.6, -0.6, -3.1), (2.6, 0.4, -2.6), 'lava', 0.5, glow=True, prio=4)
    g.dot((-1.4, -0.1, -3.2), 'lava', 0.9, glow=True, prio=5)
    g.dot((1.4, -0.1, -3.2), 'lava', 0.9, glow=True, prio=5)
    g.carve(lambda x, y, z: abs(x) < 1.6 and -2.9 < y < -2.3 and z < -3.0)
    g.rbox((-1.6, -2.9, -3.3), (1.6, -2.3, -3.0), 'lava', 0.3, glow=True, prio=4)
    for s in (-1, 1):
        g.cone((s * 2.4, 1.8, 0.6), (s * 0.5, 1, 0.3), 2.2, 0.8, 'crust', 0.5, 0.8)        # slag horns
    _slag_skin(g, 3, seed=2, steps=4)


def _slag_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    # shoulder lump, short thick upper arm, massive forearm, a huge lumpy fist close to the floor
    g.blob((o * 0.4, -1.2, 0.0), (4.2, 3.6, 4.0), 'stone', 0.5, lump=0.1, lump_scale=2.6, top=0.15)
    g.capsule((0, -2.6, 0.0), (0, -9.4, 0.2), 2.8, 2.6, 'stone', 0.46)
    g.capsule((0, -9.8, 0.2), (0, -16.6, -0.6), 3.0, 3.7, 'stone', 0.45)
    g.blob((0, -19.4, -0.8), (4.0, 3.2, 3.8), 'stone', 0.5, lump=0.1, lump_scale=2.4, top=0.15, seed=4)
    for k in range(4):
        x = -2.7 + k * 1.8
        g.blob((x, -20.6, -3.6), (1.0, 1.1, 1.0), 'stone', 0.55)
        g.dot((x, -20.2, -4.6), 'lava', 0.6, glow=True, prio=5)
    _slag_skin(g, 4, seed=4 + int(right), steps=5)
    if right:
        g.plate((o * 2.4 - 1.0, -15.0, -2.6), (o * 2.4 + 1.0, -11.0, 2.4), 'iron', 0.45, rivet_mat='iron',
                rivet_step=1.5, face=(o, 0, 0))
    else:
        for k in range(2):
            b = (o * (1.6 + k), -12.0 - 2.6 * k, -2.4 + k)
            g.sweep([b, vadd(b, (o * 1.6, 0.8, -1.2)), vadd(b, (o * 2.4, 2.2, -0.8))], 0.4, 0.34, 'rust', 0.5)
    _slag_drips(g, ['stone', 'crust'], 2, seed=7 + int(right), region=lambda x, y, z: y < -19)


def _slag_legs(g: MobGrid, ctx):
    # stumpy bowed pillars on wide slag-puddle feet (ground = y −14)
    g.blob((0, -1.2, 0.0), (6.4, 3.0, 3.6), 'stone', 0.44)
    for s in (-1, 1):
        x = s * 3.6
        g.capsule((x, -2.0, 0.0), (x + s * 0.6, -8.0, -0.2), 2.9, 2.7, 'stone', 0.46)
        g.capsule((x + s * 0.6, -8.0, -0.2), (x + s * 0.3, -12.0, -0.4), 2.7, 3.0, 'stone', 0.44)
        g.blob((x + s * 0.4, -13.0, -0.9), (3.4, 1.3, 3.8), 'stone', 0.42, lump=0.15, lump_scale=2.0, seed=s)
    _slag_skin(g, 4, seed=8, steps=5)
    g.paint(lambda x, y, z, n, m, v: ('lava', 0.3, True) if y < -13.6 and n[1] <= 0 and
            fbm3(x / 2.2, 0, z / 2.2, g.seed) > 0.55 else None, ['stone', 'crust'])


def slag_golem(look, name, part, ctx):
    _slag_ramps(ctx)
    fn = {'torso': _slag_torso, 'head': _slag_head, 'arm_left': _slag_arm, 'arm_right': _slag_arm,
          'legs': _slag_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 1.0, 'head': 0.65, 'legs': 0.95}.get(name, 0.9))
    fn(g, ctx)
    return g


# ───────────────────────────── cinder_imp (불씨 도깨비) ─────────────────────────────
# A cinder-born imp: charcoal hide split by ember cracks, a furnace-glow pot belly, a huge grinning head
# with yellow slit eyes and flame-tipped ears, obsidian ram horns burning at the tips, tattered bat
# wings whose membrane smoulders toward the edges, a fireball in one claw and a whip tail with a flame.

CHAR_SKIN = [(12, 6, 5), (28, 12, 9), (50, 20, 13), (80, 30, 17), (116, 44, 22), (156, 66, 30), (196, 100, 46)]
OBSIDIAN = [(12, 9, 12), (26, 20, 24), (46, 36, 40), (74, 58, 58), (112, 90, 82), (160, 132, 112)]
IMP_WING = [(34, 10, 8), (70, 20, 12), (118, 34, 16), (166, 56, 20), (212, 94, 32), (244, 150, 64)]
IMP_EYE = [(140, 90, 10), (220, 160, 20), (255, 214, 60), (255, 240, 150), (255, 252, 220), (255, 255, 255)]


def _imp_ramps(ctx):
    ctx.set_ramp('skin', CHAR_SKIN)
    ctx.set_ramp('horn', OBSIDIAN)
    ctx.set_ramp('membrane', IMP_WING)
    _set_glow(ctx, EMBER, ('glow', 'core', 'lava'))
    _set_glow(ctx, IMP_EYE, ('eye',))
    ctx.set_ramp('flame', _long([(150, 30, 6), (220, 70, 12), (255, 130, 30), (255, 190, 70), (255, 236, 150)]))


def _flame_tuft(g: MobGrid, base, up=(0, 1, 0), size=1.4, n=3, seed=0):
    """A little licking flame: glowing cones curling up from base."""
    u = vnorm(up)
    a_, b_ = frame_of(u)
    g.blob(base, size * 0.55, 'lava', 0.5, glow=True, prio=5)
    for k in range(n):
        ang = 2 * math.pi * k / n + seed
        side = vadd(vmul(a_, math.cos(ang) * 0.45), vmul(b_, math.sin(ang) * 0.45))
        L = size * (1.5 - 0.35 * k)
        g.cone(vadd(base, vmul(side, size * 0.4)), vadd(u, side), L, size * 0.42, 'flame', 0.3, 0.85,
               glow=True, prio=5, curl=vmul(side, -size * 0.4))


def _imp_body(g: MobGrid, ctx):
    # pot belly and narrow chest; belly glows through cracks; tiny clawed arms, one holding a fireball
    g.blob((0, -0.8, 0.2), (3.0, 3.2, 2.6), 'skin', 0.45, top=0.2)
    g.blob((0, 1.8, 0.0), (2.6, 1.8, 2.0), 'skin', 0.5)
    g.blob((0, -1.2, -1.6), (1.5, 1.7, 1.2), 'lava', 0.4, glow=True, prio=2,
           vfn=lambda x, y, z, d: 0.7 - 0.5 * d)
    _fissures(g, ['skin'], 4, seed=1, steps=4, step=0.9, r=0.3)
    for s in (-1, 1):
        sh = (s * 2.5, 2.2, 0.0)
        el = (s * 3.8, 0.2, -1.2 if s > 0 else 0.4)
        hd = (s * 4.0, 2.4, -2.4) if s > 0 else (s * 4.2, -1.4, -1.0)
        g.limb([sh, el, hd], [0.75, 0.6, 0.55], 'skin', 0.5)
        for k in range(3):
            g.cone(hd, (s * 0.3 + (k - 1) * 0.4, -0.6 if s < 0 else 0.8, -0.8), 1.0, 0.25, 'horn', 0.4, 0.75)
        if s > 0:
            g.blob((s * 4.0, 3.9, -2.6), 1.25, 'lava', 0.6, glow=True, prio=5, vfn=lambda x, y, z, d: 0.85 - 0.5 * d)
            _flame_tuft(g, (s * 4.0, 4.6, -2.6), (0, 1, 0.2), 1.2, seed=1)
    # dangling digitigrade legs, flame wisps trailing underneath
    for s in (-1, 1):
        hip = (s * 1.4, -3.4, 0.4)
        kn = (s * 1.9, -4.6, -1.0)
        an = (s * 1.8, -6.0, 0.6)
        g.limb([hip, kn, an], [0.8, 0.6, 0.45], 'skin', 0.45)
        g.cone(an, (0, -0.6, -1), 1.1, 0.35, 'horn', 0.4, 0.75)
    for k, x in enumerate((-0.8, 0.6)):
        g.cone((x, -3.6, 0.6), (x * 0.3, -1, 0.6), 2.6 - 0.6 * k, 0.7, 'flame', 0.35, 0.8, glow=True, prio=4)


def _imp_head(g: MobGrid, ctx):
    # oversized head: wide grin glowing inside, big yellow slit eyes, flame-tipped ears, brow ridges
    g.blob((0, 0.2, 0.0), (3.3, 2.8, 2.9), 'skin', 0.48, top=0.2)
    g.blob((0, -1.4, -1.0), (2.8, 1.4, 2.2), 'skin', 0.45)
    for s in (-1, 1):
        g.capsule((s * 0.6, 1.5, -2.6), (s * 2.6, 1.9, -2.1), 0.55, 0.45, 'skin', 0.62)
        g.eye((s * 1.4, 0.7, -2.5), 0.75, val=0.4, socket=0.25, facing=(s * 0.3, 0.05, -1), slit=True)
        ear = [(s * 2.9, 0.6, 0.2), (s * 4.0, 1.0, 0.6), (s * 5.2, 1.8, 1.2)]
        g.sweep(ear, 0.75, 0.3, 'skin', 0.5, sq=(1, 1, 0.55))
        _flame_tuft(g, (s * 5.3, 2.0, 1.2), (s * 0.6, 1, 0.3), 0.8, n=2, seed=s)
    g.carve(lambda x, y, z: abs(x) < 2.2 - 0.6 * abs(y + 1.3) and -2.0 < y < -0.8 and z < -2.0)
    g.rbox((-2.2, -2.0, -2.4), (2.2, -0.8, -1.8), 'lava', 0.5, glow=True, prio=3)
    g.teeth((-1.9, -0.8, -2.5), (1.9, -0.8, -2.5), 7, 0.6, r=0.25, direction=(0, -1, 0))
    g.teeth((-1.6, -2.0, -2.4), (1.6, -2.0, -2.4), 5, 0.5, r=0.22, direction=(0, 1, 0), seed=3)
    _fissures(g, ['skin'], 3, seed=2, steps=3, step=0.9, r=0.3)
    _flame_tuft(g, (0, 2.8, 0.4), (0, 1, 0.4), 1.0, n=3, seed=2)


def _imp_horns(g: MobGrid, ctx):
    for s in (-1, 1):
        g.sweep([(s * 1.4, -2.2, 0.2), (s * 2.6, -0.6, 0.6), (s * 3.8, 0.6, 0.2), (s * 4.2, 1.8, -0.6),
                 (s * 3.6, 2.6, -1.0)], 0.75, 0.25, 'horn', 0.45,
                vfn=lambda t, d, p: ('flame', 0.6, True) if t > 0.86 else
                0.35 + 0.35 * t + (0.12 if int(t * 9) % 2 else 0))
        _flame_tuft(g, (s * 3.6, 2.7, -1.0), (s * -0.2, 1, -0.3), 0.6, n=2, seed=s * 2)


def _imp_wings(g: MobGrid, ctx):
    for s in (-1, 1):
        g.wing((s * 0.8, -1.0), s, 8.8, 4.2, fingers=3, z=0.0, bone_mat='horn', membrane_mat='membrane',
               val=0.42, tatter=0.08, bone_r=0.42, droop=0.2, thick=2, seed=s + 2)
    # smouldering trailing edge: membrane voxels with open air below glow like embers
    g.paint(lambda x, y, z, n, m, v: ('lava', 0.3, True) if n[1] < 0 and abs(x) > 2.0 else None, ['membrane'])
    g.blob((0, -0.6, 0.0), 0.9, 'horn', 0.5)


def _imp_tail(g: MobGrid, ctx):
    g.sweep([(0, 0, -0.4), (0, -0.8, 3.0), (0.6, 0.2, 6.2), (0.2, 2.0, 8.4), (-0.2, 3.4, 9.4)], 0.6, 0.3, 'skin',
            0.45, vfn=lambda t, d, p: 0.4 + 0.12 * (1 - d) + (0.08 if int(t * 10) % 2 else 0))
    g.cone((-0.2, 3.4, 9.4), (0, 0.6, 1), 1.2, 0.8, 'horn', 0.45, 0.8, r_tip=0.25)        # arrowhead
    _flame_tuft(g, (-0.2, 4.2, 9.8), (0, 1, 0.3), 0.8, n=2, seed=4)


def cinder_imp(look, name, part, ctx):
    _imp_ramps(ctx)
    fn = {'body': _imp_body, 'head': _imp_head, 'horns': _imp_horns, 'wings': _imp_wings,
          'tail': _imp_tail}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'wings': 0.5}.get(name, 0.45))
    fn(g, ctx)
    return g


# ───────────────────────────── bellows_hound (풀무 사냥개) ─────────────────────────────
# A forge hound of soot-black iron: an open rib cage around a glowing firebox, riveted back plates and a
# belly grille; a leather-and-wood bellows on its back breathing through a brass nozzle into its throat;
# a long riveted muzzle with ember eyes, swept blade ears and a glowing maw; piston legs and an exhaust
# tail that smokes.

BELLOWS_LEATHER = [(22, 13, 8), (42, 26, 15), (68, 42, 24), (98, 62, 36), (132, 88, 54), (166, 118, 76)]


def _hound_ramps(ctx):
    ctx.set_ramp('iron', SOOT_IRON)
    ctx.set_ramp('leather', BELLOWS_LEATHER)
    _set_glow(ctx, EMBER)


def _hound_body(g: MobGrid, ctx):
    # spine and back plates
    g.capsule((0, 2.6, -7.4), (0, 2.8, 7.6), 1.05, 0.9, 'iron', 0.5)
    g.blob((0, 0.8, 3.8), (2.9, 2.9, 4.2), 'iron', 0.42, top=0.2)                     # haunch / waist
    g.blob((0, 1.0, -6.2), (3.2, 3.0, 2.0), 'iron', 0.45, top=0.2)                    # shoulder yoke
    g.plates((0, 1.2, 3.6), (3.1, 2.8, 4.4), n=3, axis=2, mat='iron', val=0.5, lift=0.08, groove=-0.25,
             cut=lambda x, y, z: y < 0.6)
    # open rib cage round a glowing firebox
    g.blob((0, -0.4, -3.4), (2.4, 2.5, 2.6), 'lava', 0.5, glow=True, prio=2, vfn=lambda x, y, z, d: 0.8 - 0.55 * d)
    for k in range(4):
        z = -5.4 + k * 1.35
        g.ring((0, -0.2, z), 3.3 - 0.15 * k, 0.42, axis='z', mat='iron', val=0.55, arc=(-0.1, 0.6))
    g.capsule((0, -3.2, -5.6), (0, -3.0, -0.6), 0.6, 0.5, 'iron', 0.4)                 # sternum bar
    # belly grille with ember light between the bars
    for x in (-1.2, 0.0, 1.2):
        g.capsule((x, -2.4, 0.4), (x, -2.2, 6.2), 0.32, 0.32, 'iron', 0.45)
    g.rbox((-1.6, -2.0, 0.6), (1.6, -1.7, 6.0), 'lava', 0.35, glow=True, prio=1)
    # neck: riveted collar running forward to the head
    g.capsule((0, 1.2, -6.6), (0, 2.0, -9.6), 1.9, 1.7, 'iron', 0.48)
    g.ring((0, 1.6, -8.2), 2.0, 0.42, axis='z', mat='brass', val=0.55)
    for z in (5.8, 1.6, -6.8):
        for s in (-1, 1):
            p = _stick(g, (s * 6, 1.2, z), (-s, 0, 0), out=0.4)
            if p:
                g.dot(p, 'brass', 0.7, prio=5)
    # brass joint discs where the legs meet the body
    for s in (-1, 1):
        for z in (-5.2, 5.2):
            g.cylinder((s * 2.8, -1.0, z), (s * 3.3, -1.0, z), 1.3, 1.3, 'brass', 0.5)
    g.streaks('dark', ['iron'], density=0.1, length=(1.0, 3.0), val=0.2, val_end=0.25)


def _hound_bellows(g: MobGrid, ctx):
    # classic forge bellows lying on the back: teardrop boards hinged at the nozzle end, the top board
    # raised at the back, accordion-pleated leather between, handles, brass studs, nozzle and a pipe
    vs = g.vs

    def hw(z):
        t = (z + 4.2) / 8.2
        if t < 0 or t > 1:
            return -1.0
        return 0.8 + 2.9 * math.sin(math.pi * min(1.0, t * 0.82 + 0.18)) ** 0.8

    def y_top(z):
        return -1.5 + 3.3 * (z + 4.2) / 8.2

    yb = -2.0
    for i in range(int(-4.2 / vs) - 1, int(4.2 / vs) + 2):
        x = i * vs
        for k in range(int(-4.4 / vs) - 1, int(4.2 / vs) + 2):
            z = k * vs
            w = hw(z)
            if w < 0 or abs(x) > w:
                continue
            edge = w - abs(x)
            yt = y_top(z)
            for j in range(int(math.floor((yb - 0.35) / vs)), int(math.ceil((yt + 0.35) / vs)) + 1):
                y = j * vs
                if y <= yb + 0.3:
                    g.put(i, j, k, 'wood', 0.42 + 0.15 * min(1.0, edge), False, 2)
                elif y >= yt - 0.3:
                    g.put(i, j, k, 'wood', 0.55 + 0.15 * min(1.0, edge), False, 2)
                else:
                    pleat = int((y - yb) / 0.75) % 2
                    if edge >= (0.65 if pleat else 0.0):
                        g.put(i, j, k, 'leather', 0.32 if pleat else 0.55, False, 1)
    for s_ in (-1, 1):
        g.capsule((s_ * 0.9, yb, 3.6), (s_ * 0.8, yb - 0.2, 5.6), 0.34, 0.3, 'wood', 0.55)
        g.capsule((s_ * 0.9, y_top(3.6), 3.6), (s_ * 0.8, y_top(3.6) + 0.8, 5.4), 0.34, 0.3, 'wood', 0.6)
    for z in (-2.2, 0.2, 2.4):
        for s_ in (-1, 1):
            g.dot((s_ * (hw(z) - 0.4), y_top(z) + 0.4, z), 'brass', 0.75, prio=4)
    g.cylinder((0, -1.75, -4.0), (0, -1.9, -6.0), 0.75, 0.5, 'brass', 0.5)
    g.sweep([(0, -1.9, -5.8), (0, -2.6, -7.2), (0, -3.8, -8.2), (0, -4.4, -9.2)], 0.48, 0.48, 'brass', 0.45,
            vfn=lambda t, d, p: 0.4 + 0.2 * (1 - d) + (0.12 if int(t * 8) % 2 else 0))


def _hound_head(g: MobGrid, ctx):
    # long riveted iron muzzle, heavy brow over ember eyes, swept blade ears, glowing nostrils and maw
    g.blob((0, 0.8, 1.0), (3.0, 2.8, 3.0), 'iron', 0.45, top=0.2)
    g.rbox((-2.0, -1.2, -4.6), (2.0, 1.6, 0.4), 'iron', 0.5, bevel=0.9, top=0.15)
    g.rbox((-1.5, 1.4, -4.4), (1.5, 1.9, -0.4), 'iron', 0.6, bevel=0.3)              # nose bridge plate
    g.carve(lambda x, y, z: y < -0.7 and z < 0.4 and abs(x) < 1.6)
    g.rbox((-1.6, -0.8, -4.4), (1.6, -0.5, 0.4), 'lava', 0.45, glow=True, prio=3)       # glowing palate
    g.teeth((-1.7, -0.7, -0.4), (-1.3, -0.7, -4.2), 4, 0.8, r=0.28, seed=1)
    g.teeth((1.7, -0.7, -0.4), (1.3, -0.7, -4.2), 4, 0.8, r=0.28, seed=2)
    for s in (-1, 1):
        g.capsule((s * 0.7, 2.6, -1.2), (s * 2.7, 2.3, -0.6), 0.6, 0.55, 'iron', 0.6)     # brow
        g.eye((s * 1.85, 1.5, -1.4), 0.55, val=0.4, socket=0.35, facing=(s * 0.6, 0.1, -1))
        g.dot((s * 0.6, 0.6, -4.8), 'lava', 0.6, glow=True, prio=5)                       # nostril vents
        g.sweep([(s * 1.8, 2.8, 1.4), (s * 2.6, 3.8, 3.0), (s * 2.9, 4.4, 4.6)], 0.7, 0.25, 'iron', 0.55,
                sq=(0.5, 1, 1))                                                             # blade ears
    g.rivets([(s * 2.05, 0.4, z) for s in (-1, 1) for z in (-3.6, -2.0)], 'brass')
    g.streaks('dark', ['iron'], density=0.1, length=(0.8, 2.0), val=0.2, val_end=0.25)


def _hound_jaw(g: MobGrid, ctx):
    g.rbox((-1.8, -0.8, -2.4), (1.8, 0.4, 3.0), 'iron', 0.42, bevel=0.5)
    g.rbox((-1.3, 0.2, -2.2), (1.3, 0.5, 2.6), 'lava', 0.4, glow=True, prio=3)
    g.teeth((-1.5, 0.4, 2.2), (-1.2, 0.4, -2.0), 4, 0.7, r=0.26, direction=(0, 1, 0), seed=3)
    g.teeth((1.5, 0.4, 2.2), (1.2, 0.4, -2.0), 4, 0.7, r=0.26, direction=(0, 1, 0), seed=4)


def _hound_legs(g: MobGrid, ctx):
    gy = -4.8
    for s in (-1, 1):
        for front in (True, False):
            z0 = -5.2 if front else 5.2
            hip = (s * 3.0, 3.2, z0)
            if front:
                knee = (s * 3.2, -0.6, z0 - 0.6)
                ank = (s * 3.1, -3.6, z0 - 0.2)
            else:
                knee = (s * 3.3, -0.2, z0 + 1.4)
                ank = (s * 3.2, -3.0, z0 - 0.4)
            g.limb([hip, knee, ank], [1.25, 0.8, 0.65], 'iron', 0.48, joint_mat='brass', joint_val=0.5, knob=1.2)
            g.capsule(vadd(hip, (s * 0.9, -0.6, 0.6)), vadd(knee, (s * 0.8, 0.2, 0.4)), 0.38, 0.38, 'brass', 0.6)
            g.rbox((ank[0] - 1.0, gy, ank[2] - 1.8), (ank[0] + 1.0, gy + 1.1, ank[2] + 0.6), 'iron', 0.45, bevel=0.4)
            for k in (-1, 0, 1):
                g.cone((ank[0] + k * 0.6, gy + 0.5, ank[2] - 1.7), (0, -0.4, -1), 0.9, 0.3, 'claw', 0.3, 0.7)


def _hound_tail(g: MobGrid, ctx):
    # segmented exhaust pipe curling up, glowing ember tip and a soot puff
    pts = [(0, 0, -0.6), (0, 0.6, 2.4), (0, 2.4, 4.6), (0, 4.8, 5.6), (0, 6.6, 5.4)]
    g.sweep(pts, 0.7, 0.85, 'iron', 0.45, vfn=lambda t, d, p: 0.38 + 0.2 * (1 - d) + (0.14 if int(t * 7) % 2 else 0))
    g.cylinder((0, 6.4, 5.4), (0, 7.6, 5.4), 1.0, 1.1, 'iron', 0.55, hollow=0.5)
    g.blob((0, 7.2, 5.4), 0.55, 'lava', 0.6, glow=True, prio=5)
    for p, r in (((0.2, 8.6, 5.6), 0.8), ((-0.4, 9.6, 6.2), 0.65)):
        g.blob(p, r, 'dark', 0.35, lump=0.2, lump_scale=0.8)


def bellows_hound(look, name, part, ctx):
    _hound_ramps(ctx)
    fn = {'body': _hound_body, 'bellows': _hound_bellows, 'head': _hound_head, 'jaw': _hound_jaw,
          'legs': _hound_legs, 'tail': _hound_tail}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.6, 'legs': 0.55}.get(name, 0.5))
    if name == 'legs':
        g.light_mul = 0.6
    fn(g, ctx)
    return g


# ───────────────────────────── forge_acolyte (용광로 시종) ─────────────────────────────
# A servant of the Anvil King: a long crimson robe gone black with soot toward its singed, ember-lit hem,
# a heavy smith's apron stitched with glowing runes, an iron chain belt hung with tongs, an iron scale
# mantle; a deep cowl over a riveted iron mask with burning eye slits and a grille mouth; wide sleeves;
# a censer on a chain holding a ball of molten iron.

ACOLYTE_ROBE = [(14, 5, 5), (30, 10, 9), (52, 17, 13), (80, 27, 18), (112, 40, 25), (148, 60, 36), (186, 92, 58)]
MASK_IRON = [(14, 14, 16), (30, 30, 34), (52, 52, 58), (80, 80, 88), (112, 112, 120), (150, 150, 156),
             (192, 192, 196), (232, 232, 236)]


def _acolyte_ramps(ctx):
    ctx.set_ramp('cloth', ACOLYTE_ROBE)
    ctx.set_ramp('iron', MASK_IRON)
    ctx.set_ramp('orn', GOLD_TRIM)
    _set_glow(ctx, EMBER)


def _acolyte_robe(g: MobGrid, ctx):
    # long robe flaring to the floor (ground = y −15.2), soot darkening toward the hem
    def vf(t, d, p):
        return 0.52 - 0.32 * max(0.0, (-p[1] - 5) / 10.0) + 0.08 * (1 - d)
    g.sweep([(0, 8.4, 0.3), (0, 2.0, 0.3), (0, -6.0, 0.5), (0, -14.6, 0.8)], 3.4, 6.0, 'cloth', 0.5,
            rfn=lambda t: 3.3 + 2.8 * t ** 1.4, sq=(1.0, 1.0, 0.74), vfn=vf, smooth=False)
    g.carve(lambda x, y, z: y < -15.2)
    # four deep folds down the skirt
    g.paint(lambda x, y, z, n, m, v: v - 0.14 if y < -2 and abs(((math.atan2(z, x) + 0.4) % (math.pi / 2))
            - math.pi / 4) < 0.16 else None, ['cloth'])
    # singed hem: ember-lit tatters
    g.carve(lambda x, y, z: y < -13.8 and h2(int((math.atan2(z, x) + 4) * 4), 1, g.seed) < 0.45)
    g.paint(lambda x, y, z, n, m, v: ('lava', 0.3, True) if y < -13.4 and n[1] <= 0 and
            h2(int((math.atan2(z, x) + 4) * 4), 1, g.seed) >= 0.45 and y < -14.4 else None, ['cloth'])

    # smith's apron painted onto the robe front, gold-edged, with a glowing anvil-and-hammer brand
    def apron(x, y, z, n, m, v):
        if n[2] >= 0 or z > -1.0 or not -12.6 < y < 3.0:
            return None
        hw = 2.4 + 0.12 * max(0.0, -y)
        if abs(x) > hw:
            return None
        if abs(x) > hw - 0.55 or y < -12.0:
            return ('orn', 0.55)
        ex, ey = x, y + 3.2
        if (abs(ey - 1.0) < 0.45 and abs(ex) < 1.7) or (abs(ey) < 0.6 and abs(ex) < 0.6) or \
                (abs(ey + 0.9) < 0.4 and abs(ex) < 1.2) or (abs(ex - 0.6) < 0.32 and 1.4 < ey < 3.6) or \
                (abs(ey - 3.4) < 0.4 and -0.6 < ex < 1.8):
            return ('rune', 0.3, True)
        return ('leather', 0.42 + 0.06 * (y / 12))
    g.paint(apron, ['cloth'])
    # chain belt with hanging tongs, iron scale mantle on the shoulders, stiff collar
    g.ring((0, -1.0, 0.4), 4.5, 0.4, axis='y', mat='iron', val=0.55)
    g.sweep([(3.8, -1.4, -2.4), (4.0, -4.6, -2.8), (3.8, -7.0, -2.6)], 0.32, 0.32, 'iron', 0.55)
    g.sweep([(3.6, -1.4, -2.2), (3.2, -4.6, -2.6), (3.4, -7.0, -2.4)], 0.32, 0.32, 'iron', 0.5)
    g.blob((0, 6.8, 0.3), (5.0, 2.5, 3.6), 'iron', 0.45, cut=lambda x, y, z: y < 5.2)
    g.bands(['iron'], axis=1, period=1.0, width=0.45, amount=-0.18)
    g.cylinder((0, 7.2, 0.3), (0, 9.0, 0.5), 2.6, 2.4, 'cloth', 0.4, hollow=1.6)
    # glowing anvil emblem on the back
    g.runes((0, 1.6, 4.4), (0, 0, 1), w=3.0, h=3.0, mat='rune', val=0.3, density=1.0, seed=5)


def _acolyte_head(g: MobGrid, ctx):
    # deep cowl; the face inside is shadow (the mask part covers the front); iron circlet and chain
    g.blob((0, 0.4, 0.6), (4.0, 4.1, 4.0), 'cloth', 0.45, cut=lambda x, y, z: z < -2.0 and abs(x) < 3.0 and y < 2.4)
    g.cone((0, 3.0, 1.4), (0, 0.8, 0.6), 3.8, 2.2, 'cloth', 0.45, 0.55, curl=(0, -0.4, 1.4))  # peaked cowl
    g.blob((0, -0.4, -1.0), (3.0, 3.2, 2.6), 'void', 0.2, prio=0)
    g.ring((0, 2.6, 0.4), 3.6, 0.35, axis='y', mat='brass', val=0.55)
    g.chain([(3.4, 2.4, -0.8), (3.8, 0.6, -0.4), (3.4, -1.4, 0.2)], 0.7, 'iron', 0.5)
    g.paint(lambda x, y, z, n, m, v: v + 0.15 if n[2] < 0 and z < -1.6 else None, ['cloth'])


def _acolyte_mask(g: MobGrid, ctx):
    def oval(x, y):
        return (x / 3.3) ** 2 + ((y + 0.2) / 3.6) ** 2 <= 1.0
    g.slab2d(oval, (-3.6, -4.0), (3.6, 3.6), plane='xy', depth=-0.2, half=0.6, mat='iron', bevel=1.2,
             vfn=lambda u, v, w, e: 0.5 + 0.18 * min(1.0, e / 1.5) + (0.08 if w < 0 else 0))
    g.rbox((-3.0, 0.6, -1.4), (3.0, 1.4, -0.4), 'iron', 0.62, bevel=0.3)               # brow ridge
    for s in (-1, 1):
        g.carve(lambda x, y, z, s=s: 0.6 < x * s < 2.4 and -0.2 < y + 0.25 * (x * s - 0.6) < 0.4)
        g.rbox((s * 0.6, -0.5, -0.1), (s * 2.4, 0.4, 0.3), 'lava', 0.55, glow=True, prio=3)
    for x in (-1.0, 0.0, 1.0):
        g.carve(lambda x_, y, z, x=x: abs(x_ - x) < 0.22 and -2.8 < y < -1.4)
        g.rbox((x - 0.25, -2.8, -0.1), (x + 0.25, -1.4, 0.3), 'lava', 0.35, glow=True, prio=3)
    g.rivets([(math.cos(a) * 2.9, -0.2 + math.sin(a) * 3.2, -0.6) for a in [k * math.pi / 5 for k in range(10)]],
             'brass')
    g.cone((0, 2.2, -0.4), (0, 1, -0.2), 2.4, 0.9, 'brass', 0.5, 0.85)                  # flame crest
    for s in (-1, 1):
        g.cone((s * 0.9, 2.0, -0.3), (s * 0.5, 1, -0.1), 1.6, 0.55, 'brass', 0.5, 0.8)
    g.streaks('dark', ['iron'], density=0.18, length=(0.8, 2.4), val=0.2, val_end=0.25)


def _acolyte_arm(g: MobGrid, ctx):
    # wide bell sleeve with a brass cuff band, iron bracer, dark gloved hand
    g.sweep([(0, -0.4, 0.2), (0, -5.0, 0.0), (0, -9.4, -0.4)], 1.7, 2.4, 'cloth', 0.48,
            rfn=lambda t: 1.6 + 0.9 * t ** 1.5)
    g.carve(lambda x, y, z: y < -8.6 and math.hypot(x, z + 0.4) < 1.6)
    g.ring((0, -9.0, -0.4), 2.35, 0.35, axis='y', mat='brass', val=0.55)
    g.capsule((0, -8.4, -0.4), (0, -10.4, -0.6), 1.05, 1.0, 'iron', 0.5)
    g.blob((0, -11.2, -0.6), (1.1, 1.0, 1.1), 'leather', 0.32)
    for k in range(3):
        g.capsule((-0.6 + 0.6 * k, -11.6, -1.3), (-0.6 + 0.6 * k, -12.4, -1.1), 0.3, 0.28, 'leather', 0.3)


def _acolyte_censer(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    c = (hx, hy - 5.0, hz - 1.0)
    g.chain([(hx, hy - 0.6, hz - 1.0), (hx, hy - 2.0, hz - 1.0), (hx, hy - 3.2, hz - 1.0)], 0.75, 'iron', 0.5)
    # openwork iron sphere (bands) round a ball of molten iron, a lid with a finial
    g.blob(c, 1.6, 'lava', 0.6, glow=True, prio=2, vfn=lambda x, y, z, d: 0.85 - 0.45 * d)
    for k in range(3):
        g.ring(c, 2.1, 0.32, axis=('x', 'y', 'z')[k], mat='iron', val=0.5)
    g.blob((c[0], c[1] + 1.9, c[2]), (1.6, 0.7, 1.6), 'iron', 0.55)
    g.cone((c[0], c[1] + 2.4, c[2]), (0, 1, 0), 1.0, 0.45, 'brass', 0.55, 0.85)
    g.blob((c[0], c[1] - 2.2, c[2]), (0.8, 0.5, 0.8), 'iron', 0.45)
    for p in ((0.8, 2.6, -1.4), (-0.6, 3.6, -0.8), (0.2, 4.6, -1.2)):
        g.dot(vadd(c, p), 'lava', 0.7, glow=True, prio=5)


def forge_acolyte(look, name, part, ctx):
    _acolyte_ramps(ctx)
    fn = {'robe': _acolyte_robe, 'head': _acolyte_head, 'mask': _acolyte_mask, 'arm_left': _acolyte_arm,
          'arm_right': _acolyte_arm, 'censer': _acolyte_censer}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'robe': 0.75, 'head': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── forge_executioner (단조 집행관, elite) ─────────────────────────────
# The executioner of failed smiths: a hulking soot-grey brute with burn scars that still glow, a thick
# leather apron branded with gold-edged glowing runes, a spiked iron pauldron hung with chains, a tall
# pointed hood with burning eye holes, chain-wrapped and studded bracers, and a huge crescent axe whose
# edge glows molten.

EXEC_SKIN = [(16, 15, 16), (32, 30, 31), (54, 50, 50), (80, 74, 72), (110, 102, 98), (144, 134, 126), (182, 172, 160)]
EXEC_LEATHER = [(18, 10, 6), (38, 20, 11), (64, 34, 18), (94, 52, 28), (126, 72, 40), (160, 98, 58)]
EXEC_HOOD = [(6, 4, 5), (16, 7, 8), (30, 10, 11), (52, 14, 14), (80, 20, 18), (114, 32, 26)]
AXE_STEEL = [(26, 26, 30), (50, 50, 56), (84, 84, 92), (124, 124, 132), (168, 168, 174), (210, 210, 214),
             (244, 244, 246)]


def _exec_ramps(ctx):
    ctx.set_ramp('flesh', EXEC_SKIN)
    ctx.set_ramp('leather', EXEC_LEATHER)
    ctx.set_ramp('cloth', EXEC_HOOD)
    ctx.set_ramp('iron', SOOT_IRON)
    ctx.set_ramp('blade', AXE_STEEL)
    ctx.set_ramp('orn', GOLD_TRIM)
    _set_glow(ctx, EMBER)


def _burns(g: MobGrid, n=3, seed=0, steps=5):
    _fissures(g, ['flesh'], n, seed=seed, steps=steps, step=1.2, fork=0.3)


def _exec_torso(g: MobGrid, ctx):
    # barrel chest and gut, hunched trapezius
    g.blob((0, 1.0, 0.2), (6.2, 5.6, 3.8), 'flesh', 0.5, top=0.15)
    g.blob((0, -3.6, -0.4), (5.2, 3.2, 3.6), 'flesh', 0.46)
    g.blob((0, 5.0, 1.0), (4.6, 1.8, 2.6), 'flesh', 0.52)
    for s in (-1, 1):
        g.blob((s * 2.6, 2.4, -2.8), (2.4, 1.8, 1.2), 'flesh', 0.55)                 # pecs
    _burns(g, 4, seed=1)
    # heavy bib apron with shoulder straps, branded runes framed in gold
    g.rbox((-4.4, -7.4, -4.4), (4.4, 2.6, -3.4), 'leather', 0.42, bevel=0.5)
    g.paint(lambda x, y, z, n, m, v: ('orn', 0.6) if n[2] < 0 and (abs(abs(x) - 3.9) < 0.5 or abs(y + 6.9) < 0.5
            or abs(y - 2.1) < 0.5) else None, ['leather'])
    g.ring((0, -2.4, -4.55), 1.9, 0.36, axis='z', mat='rune', val=0.3, glow=True, prio=5)          # brand seal
    g.capsule((0.6, -0.6, -4.6), (-0.6, -4.2, -4.6), 0.34, 0.34, 'rune', 0.3, glow=True, prio=5)
    g.cloth([(-4.4, -7.0, -4.0), (4.4, -7.0, -4.0)], 3.0, 'leather', 0.4, tatter=0.3, seed=3, holes=0.0)
    for s in (-1, 1):
        g.sweep([(s * 3.4, 2.6, -3.8), (s * 3.4, 5.8, -1.0), (s * 2.6, 5.6, 2.6), (s * 2.0, 0.0, 4.0)], 0.5, 0.5,
                'leather', 0.35)
    # belt with hooks and branding irons
    g.rbox((-5.4, -5.4, -4.0), (5.4, -4.2, 3.6), 'leather', 0.3)
    g.rbox((-1.0, -5.6, -4.6), (1.0, -4.0, -4.0), 'orn', 0.55)
    for k, x in enumerate((4.6, 5.4)):
        g.capsule((x, -4.8, -2.0 + k * 1.2), (x + 0.4, -9.6, -2.4 + k * 1.2), 0.32, 0.32, 'iron', 0.5)
        g.blob((x + 0.4, -9.9, -2.4 + k * 1.2), 0.55, 'lava', 0.55, glow=True, prio=5)
    # spiked iron pauldron on the left shoulder, a chain across the chest
    g.blob((-5.6, 4.4, 0.2), (3.4, 2.4, 3.6), 'iron', 0.5, top=0.25)
    g.ring((-5.6, 3.4, 0.2), 3.3, 0.45, axis='y', mat='orn', val=0.6)
    for k, (dx, dz) in enumerate(((-0.6, -1.4), (0.0, 0.2), (-0.4, 1.8))):
        g.cone((-6.0 + dx, 6.2, dz), (-0.4, 1, 0.1 * dz), 2.8 - 0.5 * abs(k - 1), 0.7, 'iron', 0.5, 0.85)
    g.chain([(-4.8, 3.2, -3.6), (-1.6, 0.6, -4.8), (1.6, -1.6, -4.8), (4.6, -3.6, -3.6)], 1.0, 'iron', 0.5)


def _exec_head(g: MobGrid, ctx):
    # heavy jaw and neck below the hood; stubble, grim slit mouth; the skull top is hood shadow
    g.capsule((0, -4.2, 0.6), (0, -1.0, 0.4), 2.6, 2.4, 'flesh', 0.45)
    g.blob((0, -1.4, -0.8), (3.0, 2.6, 3.0), 'flesh', 0.5)
    g.rbox((-2.6, -3.6, -3.6), (2.6, -1.4, -1.2), 'flesh', 0.46, bevel=0.8)
    g.paint(lambda x, y, z, n, m, v: v - 0.16 if y < -1.9 and z < -1.0 else None, ['flesh'])          # stubble
    g.carve(lambda x, y, z: abs(x) < 1.4 and -2.5 < y < -2.1 and z < -3.4)
    g.blob((0, 1.6, 0.0), (3.4, 2.6, 3.4), 'cloth', 0.3)
    _burns(g, 1, seed=3, steps=4)


def _exec_hood(g: MobGrid, ctx):
    # tall pointed hood bent back at the tip, mantle flaring over the shoulders, glowing eye holes
    g.sweep([(0, -2.6, 0.2), (0, 0.4, 0.4), (0, 3.2, 1.2), (0, 5.4, 2.6), (0, 6.6, 4.2)], 4.4, 0.4, 'cloth',
            0.42, rfn=lambda t: 4.4 * (1 - t) ** 0.9 + 0.35)
    g.blob((0, -4.0, 0.4), (5.6, 1.8, 5.0), 'cloth', 0.4, cut=lambda x, y, z: y > -3.0)
    g.cloth([(-5.4, -4.4, -2.2), (0, -4.6, -4.8), (5.4, -4.4, -2.2)], 2.6, 'cloth', 0.36, tatter=0.5, seed=4,
            normal=(0, 0, -1))
    for s in (-1, 1):
        g.carve_blob((s * 1.5, -0.8, -4.2), (0.8, 0.65, 1.4))
        g.blob((s * 1.5, -0.8, -3.2), (0.65, 0.5, 0.4), 'eye', 0.5, glow=True, prio=4)
    g.paint(lambda x, y, z, n, m, v: v + 0.14 if abs(x) < 0.3 and n[2] < 0 else None, ['cloth'])      # seam
    g.mottle(['cloth'], 0.12, 2.0)


def _exec_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    # huge bare arm: bulging shoulder and bicep, thick forearm, studded leather bracer, big fist
    g.blob((o * 0.6, -1.4, 0.0), (3.0, 2.8, 2.9), 'flesh', 0.52, top=0.15)
    g.capsule((0, -2.4, 0.0), (0, -6.4, 0.2), 2.4, 2.1, 'flesh', 0.5)
    g.blob((0, -4.0, -0.9), (1.9, 2.0, 1.6), 'flesh', 0.56)                          # bicep
    g.capsule((0, -6.8, 0.2), (0, -11.2, -0.3), 2.2, 2.0, 'flesh', 0.48)
    g.rbox((-2.4, -11.0, -2.3), (2.4, -8.0, 2.0), 'leather', 0.38, bevel=0.6)
    g.rivets([(x, y, -2.45) for x in (-1.4, 0.0, 1.4) for y in (-8.8, -10.2)], 'iron', 0.7)
    g.blob((0, -12.2, -0.6), (1.9, 1.6, 1.8), 'flesh', 0.5)
    for k in range(4):
        g.blob((-1.35 + 0.9 * k, -12.6, -2.1), (0.5, 0.6, 0.5), 'flesh', 0.56)
    _burns(g, 3, seed=5 + int(right), steps=6)
    if not right:
        for y in (-6.9, -7.9):
            g.ring((0, y, 0.2), 2.3, 0.42, axis='y', mat='iron', val=0.5)
        g.chain([(o * 2.0, -10.6, -0.8), (o * 2.4, -13.0, -0.4), (o * 2.0, -15.4, 0.2)], 1.0, 'iron', 0.5)


def _exec_axe(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    # haft forward from the fist with iron bands and a leather grip, pommel spike behind
    g.capsule((hx, hy, hz + 3.0), (hx, hy, hz - 19.0), 0.75, 0.7, 'wood', 0.38)
    g.bands(['wood'], axis=2, period=3.0, width=0.8, amount=-0.15)
    g.capsule((hx, hy, hz + 1.6), (hx, hy, hz - 2.6), 0.9, 0.9, 'leather', 0.4)
    for z in (-6.0, -11.0):
        g.cylinder((hx, hy, hz + z + 0.4), (hx, hy, hz + z - 0.4), 0.95, 0.95, 'iron', 0.55)
    g.cone((hx, hy, hz + 3.0), (0, 0, 1), 1.8, 0.7, 'iron', 0.5, 0.8)
    # crescent blade hanging below the end of the haft (edge down and forward), back spike up
    zc = hz - 16.5

    def crescent(z, y):
        u = (z - zc) / 5.6
        yy = y - hy
        if abs(u) > 1.0 or yy > 1.0:
            return False
        bottom = -10.0 + 2.4 * u * u
        inner = -1.0 - 3.4 * (1 - u * u) if abs(u) < 0.55 else 99
        return bottom < yy < 1.0 and not (yy > inner and abs(u) > 0.28 and yy < -0.8)
    g.slab2d(crescent, (zc - 6.0, hy - 10.4), (zc + 6.0, hy + 1.2), plane='zy', depth=hx, half=0.75, mat='blade',
             bevel=2.2, vfn=lambda u, v, w, e: ('lava', 0.35, True) if e < 0.6 and v < hy - 3.0 else
             0.4 + 0.3 * min(1.0, e / 2.0) + (0.1 if w < 0 else 0))
    g.runes((hx + 1.2, hy - 4.4, zc), (1, 0, 0), w=4.0, h=3.0, mat='rune', val=0.3, density=0.8, seed=6)
    g.rbox((hx - 1.1, hy - 1.4, zc - 2.2), (hx + 1.1, hy + 1.4, zc + 2.2), 'iron', 0.45, bevel=0.4)
    g.cone((hx, hy + 1.2, zc), (0, 1, 0.3), 3.0, 0.8, 'blade', 0.5, 0.85)
    g.cone((hx, hy, hz - 19.0), (0, 0, -1), 2.0, 0.65, 'iron', 0.5, 0.85)
    g.rivets([(hx + 1.15, hy + 0.6, zc + dz) for dz in (-1.4, 0.0, 1.4)], 'orn')


def _exec_legs(g: MobGrid, ctx):
    g.rbox((-4.8, -2.6, -2.4), (4.8, 0.6, 2.4), 'leather', 0.4, bevel=0.9)
    for s in (-1, 1):
        x = s * 2.5
        g.capsule((x, -1.4, 0.0), (x + s * 0.2, -6.2, -0.2), 2.1, 1.8, 'leather', 0.42)
        g.capsule((x + s * 0.2, -6.4, -0.2), (x, -9.4, 0.1), 1.7, 1.6, 'leather', 0.4)
        g.blob((x, -6.4, -1.4), (1.6, 1.4, 1.0), 'iron', 0.55, top=0.25)                  # knee cop
        g.cone((x, -6.2, -2.2), (0, 0.2, -1), 1.2, 0.5, 'iron', 0.5, 0.8)
        g.rbox((x - 1.9, -10.6, -2.2), (x + 1.9, -8.6, 2.0), 'leather', 0.32, bevel=0.6)
        g.rbox((x - 2.0, -12.0, -3.6), (x + 2.0, -10.2, 2.1), 'leather', 0.3, bevel=0.7)
        g.blob((x, -10.9, -3.0), (1.9, 1.1, 1.0), 'iron', 0.55, cut=lambda x_, y, z: y < -11.7)
        g.rbox((x - 2.1, -12.0, -3.7), (x + 2.1, -11.6, 2.2), 'dark', 0.2)
        g.rbox((x - 2.0, -9.8, -2.3), (x + 2.0, -9.2, 2.1), 'orn', 0.5)                     # boot buckle band
    g.mottle(['leather'], 0.1, 2.0)


def forge_executioner(look, name, part, ctx):
    _exec_ramps(ctx)
    fn = {'torso': _exec_torso, 'head': _exec_head, 'hood': _exec_hood, 'arm_left': _exec_arm,
          'arm_right': _exec_arm, 'axe': _exec_axe, 'legs': _exec_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.65, 'head': 0.55, 'axe': 0.55, 'legs': 0.65, 'hood': 0.6}.get(name, 0.55))
    fn(g, ctx)
    return g


# ═══════════════════════════════ floor 6 · 서리 묘역 ═══════════════════════════════

FROST_GLOW = [(24, 60, 110), (50, 118, 190), (110, 182, 246), (180, 226, 255), (232, 248, 255), (255, 255, 255)]
SILVER = [(52, 58, 72), (100, 108, 124), (156, 164, 180), (204, 210, 222), (236, 240, 248), (255, 255, 255)]
GRAVE_BONE = [(26, 28, 36), (54, 58, 70), (92, 98, 112), (136, 142, 154), (180, 186, 196), (220, 224, 230)]


def _frost(g: MobGrid, mats, coverage=0.5, up_min=0.5, scale=2.6, seed=0, region=None):
    """Rime on the upward surfaces (paints the surface — no extra geometry); region(x, y, z) limits it."""
    sd = g.seed + 307 + seed
    thr = 1.0 - coverage

    def f(x, y, z, n, m, v):
        ln = vlen(n)
        if not ln or n[1] / ln < up_min or (region and not region(x, y, z)):
            return None
        if fbm3(x / scale, y / (scale * 1.5), z / scale, sd) < thr:
            return None
        return ('frost', 0.7 if fbm3(x / (scale * 0.6), y / scale, z / (scale * 0.6), sd + 1) > 0.5 else 0.55)
    g.paint(f, list(mats))


# ───────────────────────────── rime_mourner (서리 곡하는 자) ─────────────────────────────
# A veiled mourner drifting over the graves: a long pale-blue gown and bridal veil that trail into
# tatters behind her, frost on the shoulders and icicles at the hem, a silver funeral band down the front;
# under the veil only two cold lights and frozen tears that run down into icicles; a frost-flower
# tiara; thin pale arms in long trailing sleeves, one hand trailing a rosary of ice beads.

MOURN_CLOTH = [(22, 30, 52), (40, 54, 86), (66, 86, 126), (100, 124, 166), (142, 166, 206), (190, 208, 238),
               (232, 242, 255)]
MOURN_SKIN = [(40, 48, 66), (74, 86, 108), (116, 128, 150), (160, 172, 192), (204, 214, 230), (236, 242, 250)]


def _mourner_ramps(ctx):
    ctx.set_ramp('cloth', MOURN_CLOTH)
    ctx.set_ramp('flesh', MOURN_SKIN)
    ctx.set_ramp('orn', SILVER)
    _set_glow(ctx, FROST_GLOW)


def _mourner_veil(g: MobGrid, ctx):
    # bell-shaped gown: narrow at the waist, flaring and trailing back into long pointed tatters; it pales
    # toward the hem like mist (she floats: no feet)
    knots = ((0.0, 3.1), (0.18, 2.7), (0.38, 2.9), (0.62, 3.9), (1.0, 6.0))

    def rfn(t):
        for (t0, r0), (t1, r1) in zip(knots, knots[1:]):
            if t <= t1:
                f = (t - t0) / (t1 - t0)
                return r0 + (r1 - r0) * (f * f * (3 - 2 * f))
        return knots[-1][1]
    g.sweep([(0, 8.6, 0.0), (0, 4.0, 0.1), (0, -1.0, 0.4), (0, -6.0, 1.4), (0, -11.6, 3.2)], 3.0, 6.0, 'cloth', 0.5,
            rfn=rfn, sq=(1.0, 1.0, 0.82), vfn=lambda t, d, p: 0.48 + 0.34 * t ** 1.5 + 0.08 * (1 - d), smooth=True)
    g.carve_blob((0, -13.2, 3.2), (5.2, 3.6, 4.4))                                      # hollow hem

    def tatter(x, y, z):
        a = math.atan2(z - 2.6, x)
        cut = -7.0 - 4.6 * h2(int((a + 4) * 3.2), 3, g.seed)
        return y < cut
    g.carve(tatter)
    # six soft folds, a silver funeral band down the front with pale glowing beads
    g.paint(lambda x, y, z, n, m, v: v - 0.12 if y < 3 and abs(((math.atan2(z, x) + 0.3) % (math.pi / 3))
            - math.pi / 6) < 0.14 else None, ['cloth'])
    g.paint(lambda x, y, z, n, m, v: ('orn', 0.5 + 0.1 * (y / 9)) if n[2] < 0 and abs(x) < 0.7 and y > -8 else None,
            ['cloth'])
    for y in (4.0, 0.6, -2.8, -6.2):
        p = _stick(g, (0, y, -9), (0, 0, 1), out=0.3)
        if p:
            g.dot(p, 'glow', 0.35, glow=True, prio=6)
    # shoulder cape, frost on the shoulders, a few icicles, cold motes drifting under the hem
    g.blob((0, 7.4, 0.0), (4.4, 1.6, 3.0), 'cloth', 0.6, cut=lambda x, y, z: y < 6.6)
    _frost(g, ['cloth'], 0.7, 0.45, region=lambda x, y, z: y > 5.0)
    _icicles(g, ['cloth'], 4, length=(1.2, 2.6), r=0.45, region=lambda x, y, z: -6 < y < 7)
    for p in ((-3.6, -10.8, 1.0), (3.2, -12.0, 3.4), (0.8, -13.2, 5.8), (-2.2, -12.6, 6.4)):
        g.dot(p, 'glow', 0.4, glow=True, prio=6)


def _mourner_head(g: MobGrid, ctx):
    # veil over the head and face, falling down the back; two lights shine through; frozen tears
    g.blob((0, 0.2, 0.3), (3.6, 4.0, 3.7), 'cloth', 0.62, top=0.15)
    g.paint(lambda x, y, z, n, m, v: v - 0.3 if n[2] < 0 and abs(x) < 2.4 and -3 < y < 1.6 else None, ['cloth'])
    drape = [(math.cos(a) * 3.85, 1.4, 0.3 + math.sin(a) * 3.85) for a in
             [math.pi * (-0.15 + 1.3 * k / 20) for k in range(21)]]
    g.cloth(drape, (lambda u: 3.6 + 3.4 * math.sin(math.pi * u)), 'cloth', 0.64, tatter=0.35, normal=(0, 0, 1),
            seed=5, holes=0.0, folds=0.12, fold_period=1.6)
    for s in (-1, 1):
        p = _stick(g, (s * 1.25, 0.2, -8), (0, 0, 1), out=0.2)
        if p:
            g.blob(p, (0.5, 0.35, 0.3), 'eye', 0.4, glow=True, prio=6)
            g.cone((p[0] + s * 0.3, p[1] - 0.8, p[2] - 0.1), (0, -1, -0.1), 3.4, 0.36, 'ice', 0.6, 0.95, prio=5)
    # frost-flower tiara: silver band with ice crystals
    g.ring((0, 2.0, 0.2), 3.6, 0.32, axis='y', mat='orn', val=0.6)
    for k, a in enumerate((-1.57, -2.1, -1.04, -2.6, -0.52)):
        c = (math.cos(a) * 3.6, 2.2, math.sin(a) * 3.6)
        L = 2.2 if k == 0 else 1.4
        g.cone(c, (math.cos(a) * 0.3, 1, math.sin(a) * 0.3), L, 0.45, 'ice', 0.6, 0.95, prio=4)
    g.dot((0, 2.4, -3.8), 'glow', 0.5, glow=True, prio=6)
    _frost(g, ['cloth'], 0.35, 0.8)


def _mourner_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    # long trailing sleeve, thin pale forearm, long fingers; left hand trails a rosary of ice beads
    g.capsule((0, -0.4, 0.0), (0, -6.4, -0.2), 1.3, 1.2, 'cloth', 0.56)
    g.cloth([(math.cos(a) * 1.2, -6.2, math.sin(a) * 1.2 - 0.2) for a in [math.pi * 2 * k / 12 for k in range(13)]],
            (lambda u: 1.4 + 3.2 * max(0.0, math.sin(math.pi * u * 2 + 0.6))), 'cloth', 0.56, tatter=0.5,
            sway=(0, 0.25), seed=8 + int(right), holes=0.0)
    g.capsule((0, -6.8, -0.2), (0, -10.4, -0.8), 0.75, 0.6, 'flesh', 0.6)
    g.blob((0, -10.9, -1.0), (0.75, 0.65, 0.65), 'flesh', 0.6)
    for k in range(4):
        x = -0.5 + k * 0.33
        g.capsule((x, -11.2, -1.2), (x * 1.3, -12.8, -1.6 + 0.2 * (k % 2)), 0.22, 0.2, 'flesh', 0.62)
    if not right:
        pts = [(o * 0.2, -12.0, -1.4), (o * 0.6, -13.6, -1.2), (o * 0.4, -15.2, -0.6), (o * 0.1, -16.4, 0.0)]
        for k, q in enumerate(pts + [(o * 0.25, -17.4, 0.2)]):
            g.blob(q, 0.42, 'ice', 0.7, prio=4)
        g.cone((o * 0.25, -17.6, 0.2), (0, -1, 0), 1.4, 0.4, 'ice', 0.65, 0.95, prio=4)
        g.dot((o * 0.25, -19.1, 0.2), 'glow', 0.4, glow=True, prio=6)
    _frost(g, ['cloth'], 0.5, 0.6)


def rime_mourner(look, name, part, ctx):
    _mourner_ramps(ctx)
    fn = {'veil': _mourner_veil, 'head': _mourner_head, 'arm_left': _mourner_arm,
          'arm_right': _mourner_arm}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'veil': 0.6, 'head': 0.5}.get(name, 0.45))
    fn(g, ctx)
    return g


# ───────────────────────────── crypt_hound (얼음 묘지견) ─────────────────────────────
# The skeleton of a royal tomb hound: a vertebral chain, an open rib cage round a glowing frost heart,
# a pelvis and shoulder blades, scraps of dark hide, a broken iron collar with a grave tag; a row of
# icicles growing from the spine; a long canine skull with burning-blue sockets and fangs; bone legs;
# a vertebra tail ending in ice shards.

HOUND_HIDE = [(10, 10, 14), (20, 20, 28), (34, 34, 46), (52, 52, 66), (74, 74, 90)]


def _ghound_ramps(ctx):
    ctx.set_ramp('bone', GRAVE_BONE)
    ctx.set_ramp('cloth', HOUND_HIDE)
    _set_glow(ctx, FROST_GLOW)


def _vertebrae(g: MobGrid, a, b, n, r, proc=0.0, mat='bone', val=0.55):
    for k in range(n):
        t = k / max(1, n - 1)
        p = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
        rr = r[0] + (r[1] - r[0]) * t
        g.blob(p, (rr, rr * 0.9, rr * 0.7), mat, val + (0.08 if k % 2 else 0))
        if proc:
            g.cone(p, (0, 1, 0.5), proc * (1 - 0.4 * t), rr * 0.45, mat, val, val + 0.2)


def _ghound_body(g: MobGrid, ctx):
    _vertebrae(g, (0, 2.6, -7.6), (0, 2.4, 7.4), 11, (0.95, 0.8), proc=1.4)
    # rib cage (open below) round a glowing frost heart
    g.crystals((0, -1.6, -3.2), (0, 1, 0.2), n=4, size=2.6, r=0.7, mat='core', glow=True, spread=0.6, seed=2)
    g.blob((0, -0.4, -3.2), 1.3, 'core', 0.4, glow=True, prio=4)
    for k in range(5):
        z = -5.8 + k * 1.3
        R = 3.1 - 0.12 * abs(k - 1.5)
        g.ring((0, 0.0, z), R, 0.34, axis='z', mat='bone', val=0.6, arc=(-0.12, 0.62))
    g.capsule((0, -3.0, -6.0), (0, -2.4, -1.2), 0.45, 0.4, 'bone', 0.5)                # sternum
    # shoulder blades, pelvis with hip sockets
    for s in (-1, 1):
        g.slab2d(lambda z, y: ((z + 5.6) / 1.7) ** 2 + ((y - 1.2) / 2.0) ** 2 <= 1.0, (-7.5, -1.0), (-3.5, 3.4),
                 plane='zy', depth=s * 2.6, half=0.3, mat='bone', vfn=lambda u, v, w, e: 0.5 + 0.15 * min(1.0, e))
        g.blob((s * 2.2, 0.8, 5.6), (0.9, 0.9, 0.9), 'bone', 0.5)
    g.blob((0, 1.6, 5.2), (2.4, 1.3, 2.0), 'bone', 0.52, cut=lambda x, y, z: abs(x) < 0.7 and y < 1.4)
    # a broken iron collar with a grave tag
    g.ring((0, 1.4, -7.6), 2.2, 0.42, axis='z', mat='iron', val=0.45, arc=(0.08, 0.82))
    g.capsule((0, -0.8, -8.2), (0, -2.0, -8.4), 0.18, 0.18, 'iron', 0.5)
    g.rbox((-0.6, -3.2, -8.6), (0.6, -2.0, -8.3), 'orn', 0.55)
    _frost(g, ['bone'], 0.55, 0.55)
    g.ramp_over['orn'] = SILVER


def _ghound_spines(g: MobGrid, ctx):
    # icicle crest growing from the spine, raked back, tallest over the shoulders
    for k in range(7):
        z = -6.0 + k * 1.9
        h = 3.6 * math.sin(math.pi * (k + 0.8) / 7.6) + 1.0
        g.crystals((0, -2.8, z), (0, 1, 0.55), n=2 if k % 2 else 1, size=h, r=0.62, mat='ice', spread=0.35, seed=k)
    for v in g.vox.values():
        if v[0] == 'ice' and v[1] > 0.85:
            v[0], v[2] = 'glow', True


def _ghound_head(g: MobGrid, ctx):
    g.blob((0, 1.0, 1.6), (2.8, 2.4, 3.0), 'bone', 0.55, top=0.2)
    g.capsule((0, 0.4, -0.8), (0, -0.2, -4.6), 1.7, 1.25, 'bone', 0.55, sq=(1.0, 0.8, 1.0))
    for s in (-1, 1):
        g.capsule((s * 2.4, -0.4, 1.8), (s * 1.8, -0.6, -1.4), 0.55, 0.45, 'bone', 0.6)      # cheekbones
        g.carve_blob((s * 1.3, 1.1, -1.2), (0.9, 0.85, 1.0))
        g.blob((s * 1.3, 1.1, -0.7), (0.85, 0.8, 0.6), 'void', 0.15, prio=2)
        g.eye((s * 1.3, 1.1, -1.0), 0.5, val=0.45, facing=(s * 0.3, 0.1, -1))
        g.cone((s * 0.6, -0.9, -4.0), (0, -1, -0.2), 1.5, 0.36, 'tooth', 0.55, 0.85, prio=4)    # fangs
        g.crystals((s * 1.2, 2.6, -0.4), (s * 0.4, 1, 0.6), n=2, size=1.6, r=0.4, mat='ice', seed=3 + s)
    g.carve_blob((0, 0.6, -4.8), (0.6, 0.5, 0.6))                                        # nasal opening
    g.teeth((-1.2, -0.8, 0.2), (-0.8, -0.8, -3.6), 4, 0.6, r=0.24, seed=1)
    g.teeth((1.2, -0.8, 0.2), (0.8, -0.8, -3.6), 4, 0.6, r=0.24, seed=2)
    g.cracks(['bone'], width=0.025, scale=3.0, dv=-0.22, seed=4)
    _frost(g, ['bone'], 0.5, 0.6)


def _ghound_jaw(g: MobGrid, ctx):
    for s in (-1, 1):
        g.capsule((s * 1.6, 0.0, 2.6), (s * 0.5, 0.0, -2.6), 0.55, 0.45, 'bone', 0.52)
        g.cone((s * 0.5, 0.3, -2.2), (0, 1, -0.2), 1.3, 0.34, 'tooth', 0.55, 0.85, prio=4)
        g.teeth((s * 1.4, 0.4, 1.8), (s * 0.7, 0.4, -1.6), 3, 0.5, r=0.22, direction=(0, 1, 0), seed=s + 5)
    g.blob((0, -0.1, -2.6), (0.7, 0.45, 0.5), 'bone', 0.55)


def _ghound_legs(g: MobGrid, ctx):
    gy = -4.8
    for s in (-1, 1):
        for front in (True, False):
            z0 = -5.0 if front else 5.0
            hip = (s * 2.6, 3.4, z0)
            knee = (s * 2.9, -0.4, z0 + (-0.8 if front else 1.6))
            ank = (s * 2.8, -3.4, z0 + (-0.2 if front else 0.2))
            g.limb([hip, knee, ank], [0.75, 0.55, 0.45], 'bone', 0.55, knob=1.6)
            for k in (-1, 0, 1):
                tip = (ank[0] + k * 0.55, gy + 0.3, ank[2] - 1.6)
                g.capsule(ank, tip, 0.3, 0.26, 'bone', 0.6)
                g.cone(tip, (0, -0.3, -1), 0.7, 0.24, 'claw', 0.3, 0.7)
    _frost(g, ['bone'], 0.6, 0.5)
    g.light_mul = 0.6


def _ghound_tail(g: MobGrid, ctx):
    pts = [(0, 0, 0), (0, -0.6, 2.6), (0.4, -1.8, 5.0), (0.2, -3.4, 7.0), (0, -4.2, 8.8)]
    for k in range(9):
        t = k / 8
        idx = min(3, int(t * 4))
        f = t * 4 - idx
        p = tuple(pts[idx][i] + (pts[idx + 1][i] - pts[idx][i]) * f for i in range(3))
        g.blob(p, 0.62 - 0.25 * t, 'bone', 0.55 + (0.1 if k % 2 else 0))
    g.crystals((0, -4.2, 8.8), (0, -0.4, 1), n=3, size=2.0, r=0.4, mat='ice', spread=0.6, seed=5)


def crypt_hound(look, name, part, ctx):
    _ghound_ramps(ctx)
    fn = {'body': _ghound_body, 'spines': _ghound_spines, 'head': _ghound_head, 'jaw': _ghound_jaw,
          'legs': _ghound_legs, 'tail': _ghound_tail}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.5, 'legs': 0.5, 'head': 0.5}.get(name, 0.45))
    fn(g, ctx)
    return g


# ───────────────────────────── frozen_knight (얼어붙은 묘지기사) ─────────────────────────────
# A dead knight still keeping his oath: blackened blue steel plate under a crust of ice, layered
# pauldrons with icicles, a torn royal-blue tabard with a silver star, a crack in the breastplate where
# frost glows; a closed great helm with a dark T-visor and two faint lights; a crown of ice crystals;
# a heater shield whose face is half swallowed by ice; a longsword of frozen steel with a glowing fuller.

KNIGHT_STEEL = [(12, 14, 20), (24, 28, 38), (40, 46, 60), (62, 70, 88), (90, 100, 120), (126, 138, 158),
                (168, 180, 198), (214, 224, 236)]
ROYAL_BLUE = [(10, 14, 30), (18, 26, 52), (30, 42, 80), (46, 62, 110), (70, 90, 144), (104, 124, 180)]
ICE_STEEL = [(40, 60, 90), (76, 104, 140), (120, 152, 190), (166, 196, 228), (206, 228, 248), (236, 246, 255),
             (255, 255, 255)]


def _knight_ramps(ctx):
    ctx.set_ramp('iron', KNIGHT_STEEL)
    ctx.set_ramp('cloth', ROYAL_BLUE)
    ctx.set_ramp('orn', SILVER)
    ctx.set_ramp('blade', ICE_STEEL)
    _set_glow(ctx, FROST_GLOW)


def _ice_crust(g: MobGrid, mats, n, seed=0, region=None, size=1.4):
    """Little clusters of ice crystals growing out of the surface."""
    for k, (p, nn) in enumerate(_surface(g, mats, n, 500 + seed, region=region, min_d=2.4)):
        g.crystals(p, vadd(nn, (0, 0.6, 0)), n=2, size=size, r=0.42, mat='ice', spread=0.7, seed=k + seed)


def _knight_torso(g: MobGrid, ctx):
    # cuirass with a centre ridge, gorget, faulds; layered pauldrons
    g.rbox((-4.4, -4.6, -2.8), (4.4, 5.6, 2.8), 'iron', 0.45, bevel=0.8, top=0.15)
    g.capsule((0, 5.2, -2.9), (0, -3.0, -3.1), 0.55, 0.45, 'iron', 0.62)
    g.cylinder((0, 5.0, 0.0), (0, 6.6, 0.0), 2.4, 2.2, 'iron', 0.55)
    for k in range(2):
        y = -4.6 - 1.2 * k
        g.rbox((-4.5 + 0.2 * k, y - 1.2, -3.0 + 0.1 * k), (4.5 - 0.2 * k, y, 3.0 - 0.1 * k), 'iron', 0.5 - 0.05 * k,
               bevel=0.4)
    for s in (-1, 1):
        for k in range(3):
            g.blob((s * (4.4 + 0.3 * k), 5.0 - 1.1 * k, 0.0), (2.6 - 0.2 * k, 1.3, 3.0 - 0.2 * k), 'iron',
                   0.5 + 0.05 * k, cut=lambda x, y, z, k=k: y < 4.2 - 1.1 * k)
        g.ring((s * 4.4, 4.4, 0.0), 2.6, 0.3, axis='x', mat='orn', val=0.55, arc=(0.0, 0.5))
    # torn tabard front and back with a silver star; a frost-glowing crack in the breastplate
    g.rbox((-2.6, -8.6, -3.5), (2.6, 3.4, -3.0), 'cloth', 0.45)
    g.cloth([(-2.6, -8.4, -3.25), (2.6, -8.4, -3.25)], 2.4, 'cloth', 0.4, tatter=0.6, seed=4)
    g.rbox((-2.6, -8.6, 3.0), (2.6, 3.4, 3.5), 'cloth', 0.42)
    g.cloth([(2.6, -8.4, 3.25), (-2.6, -8.4, 3.25)], 2.8, 'cloth', 0.38, tatter=0.6, normal=(0, 0, 1), seed=5)

    def flake(x, y, z, n, m, v):
        if n[2] >= 0:
            return None
        dx, dy = x, y + 0.8
        r = math.hypot(dx, dy)
        if r > 2.0:
            return None
        a = (math.atan2(dy, dx) + math.pi / 2) % (math.pi / 3)
        arm = min(a, math.pi / 3 - a) * r                  # distance to the nearest of the six arms
        return ('orn', 0.7) if arm < 0.32 or r < 0.5 else None
    g.paint(flake, ['cloth'])
    g.paint(lambda x, y, z, n, m, v: ('orn', 0.5) if n[2] < 0 and abs(abs(x) - 2.35) < 0.3 else None, ['cloth'])
    _fissures(g, ['iron'], 1, seed=2, steps=4, step=1.0, region=lambda x, y, z: x > 2 and y > 0 and z < -2)
    # frost and ice on the shoulders, icicles off the pauldrons
    _frost(g, ['iron', 'cloth'], 0.6, 0.5)
    _ice_crust(g, ['iron', 'frost'], 2, region=lambda x, y, z: abs(x) > 3.6 and y > 4)
    _icicles(g, ['iron'], 3, length=(1.0, 2.2), r=0.42, region=lambda x, y, z: abs(x) > 3.5 and y > 1.5)


def _knight_head(g: MobGrid, ctx):
    # great helm: T-visor into darkness with two faint lights, breaths holes, a crest ridge
    g.rbox((-3.4, -4.2, -3.6), (3.4, 3.4, 3.6), 'iron', 0.48, bevel=1.3, top=0.15)
    g.capsule((0, 3.4, -3.4), (0, 3.9, 3.2), 0.6, 0.55, 'iron', 0.62)
    g.carve(lambda x, y, z: z < -2.4 and ((abs(x) < 2.6 and 0.1 < y < 0.9) or (abs(x) < 0.5 and -2.6 < y < 0.9)))
    g.rbox((-2.6, -2.6, -2.8), (2.6, 0.9, -2.3), 'void', 0.1, prio=2)
    for s in (-1, 1):
        g.dot((s * 1.3, 0.5, -2.4), 'eye', 0.45, glow=True, prio=4)
    for x, y in ((1.6, -1.4), (2.3, -1.4), (1.6, -2.3), (2.3, -2.3)):
        p = _stick(g, (x, y, -8), (0, 0, 1), out=0.0)
        if p:
            g.dot(p, 'void', 0.1, prio=5)
    g.paint(lambda x, y, z, n, m, v: ('orn', 0.55) if n[2] < 0 and abs(y - 1.4) < 0.35 else None, ['iron'])  # brow
    _frost(g, ['iron'], 0.65, 0.5)
    _icicles(g, ['iron', 'frost'], 3, length=(0.8, 1.6), r=0.36, region=lambda x, y, z: y < -3.5)


def _knight_crown(g: MobGrid, ctx):
    g.ring((0, -2.0, 0.0), 3.0, 0.42, axis='y', mat='orn', val=0.55)
    for k in range(6):
        a = -math.pi / 2 + 2 * math.pi * k / 6
        c = (math.cos(a) * 3.0, -1.8, math.sin(a) * 3.0)
        L = 3.8 if k == 0 else 2.6 if k in (1, 5) else 1.9
        g.crystals(c, (math.cos(a) * 0.35, 1, math.sin(a) * 0.35), n=1, size=L, r=0.55, mat='ice', seed=k)
    for v in g.vox.values():
        if v[0] == 'ice' and v[1] > 0.85:
            v[0], v[2] = 'glow', True
    g.blob((0, -1.6, -3.1), (0.6, 0.6, 0.4), 'glow', 0.5, glow=True, prio=5)


def _knight_arm(g: MobGrid, ctx):
    o = ctx.out
    g.capsule((0, -1.0, 0.0), (0, -5.6, 0.1), 1.65, 1.5, 'iron', 0.48)
    g.blob((0, -6.0, 0.0), (1.75, 1.4, 1.75), 'iron', 0.58)                            # couter
    g.slab2d(lambda z, y: (z / 1.4) ** 2 + ((y + 6.0) / 1.2) ** 2 <= 1.0, (-1.6, -7.4), (1.6, -4.6), plane='zy',
             depth=o * 1.7, half=0.3, mat='iron', vfn=lambda u, v, w, e: 0.6)
    g.capsule((0, -6.6, 0.0), (0, -10.0, -0.3), 1.45, 1.35, 'iron', 0.5)
    g.rbox((-1.5, -12.4, -1.7), (1.5, -10.2, 1.2), 'iron', 0.45, bevel=0.5)            # gauntlet
    for k in range(3):
        g.rbox((-1.4, -12.9 - 0.25 * k, -1.8 + 0.4 * k), (1.4, -12.2 - 0.25 * k, -1.1 + 0.4 * k), 'iron', 0.55)
    g.ring((0, -10.1, -0.3), 1.5, 0.3, axis='y', mat='orn', val=0.55)
    _frost(g, ['iron'], 0.6, 0.5)
    _icicles(g, ['iron'], 2, length=(0.8, 1.6), r=0.36, region=lambda x, y, z: -7 < y < -5.5)


def _knight_shield(g: MobGrid, ctx):
    o = ctx.out
    hx, hy, hz = ctx.hand
    xc, yc, zc = o * 3.0, hy + 4.4, -0.6

    def heater(z, y):
        u, v = (z - zc) / 5.0, (y - yc) / 7.0
        if v > 1.0 or abs(u) > 1.0:
            return False
        if v > 0.25:
            return v < 1.0 - 0.06 * u * u
        return abs(u) < math.sqrt(max(0.0, 1 - ((0.25 - v) / 1.25) ** 2)) * (1 - 0.15 * (0.25 - v))
    g.slab2d(heater, (zc - 5.2, yc - 7.4), (zc + 5.2, yc + 7.2), plane='zy', depth=xc, half=0.6, mat='cloth',
             vfn=lambda u, v, w, e: ('orn', 0.62) if e < 0.7 else ('cloth', 0.45 + 0.1 * (v - yc) / 7))
    # convex boss / silver star emblem on the outer face, ice swallowing the lower corner, icicles
    g.blob((xc + o * 0.6, yc + 1.0, zc), (0.6, 1.0, 1.0), 'orn', 0.6, prio=3)

    def star(x, y, z, n, m, v):
        if n[0] * o <= 0:
            return None
        dz, dy = z - zc, y - (yc + 1.0)
        r = math.hypot(dz, dy)
        a = math.atan2(dy, dz)
        return ('orn', 0.7) if r < 2.8 * (0.35 + 0.65 * abs(math.cos(a * 2)) ** 4) else None
    g.paint(star, ['cloth'])
    g.blob((xc + o * 0.4, yc - 4.6, zc + 2.2), (1.4, 2.8, 2.6), 'ice', 0.55, lump=0.3, lump_scale=1.0, prio=3)
    g.crystals((xc + o * 0.8, yc - 3.4, zc + 2.6), (o, 0.4, 0.3), n=3, size=2.0, r=0.5, mat='ice', seed=2)
    _icicles(g, ['cloth', 'orn', 'ice'], 4, length=(1.0, 2.4), r=0.4, region=lambda x, y, z: y < yc - 3)
    _frost(g, ['cloth', 'orn'], 0.45, 0.4)
    # grip: strap to the forearm
    g.rbox((o * 1.0, hy + 2.0, -1.0), (xc, hy + 3.0, 0.0), 'leather', 0.4)


def _knight_sword(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    # wrapped grip, silver crossguard, long frozen blade with a glowing fuller, frost crystals at the guard
    g.capsule((hx, hy, hz + 1.8), (hx, hy, hz - 1.4), 0.5, 0.5, 'leather', 0.4)
    g.blob((hx, hy, hz + 2.4), 0.75, 'orn', 0.6)
    g.dot((hx, hy, hz + 3.1), 'glow', 0.5, glow=True, prio=5)
    g.rbox((hx - 0.5, hy - 2.2, hz - 2.4), (hx + 0.5, hy + 2.2, hz - 1.6), 'orn', 0.55, bevel=0.2)
    for s in (-1, 1):
        g.cone((hx, hy + s * 2.2, hz - 2.0), (0, s, -0.4), 0.9, 0.4, 'orn', 0.6, 0.85)
    L = 17.0
    z0 = hz - 2.4

    def blade(z, y):
        t = (z0 - z) / L
        if not 0 <= t <= 1:
            return False
        hw = 0.95 * (1 - t ** 3) + 0.1 if t < 0.9 else 0.95 * (1 - 0.9 ** 3) * (1 - t) / 0.1 + 0.1
        return abs(y - hy) <= hw
    g.slab2d(blade, (z0 - L - 0.5, hy - 1.2), (z0 + 0.3, hy + 1.2), plane='zy', depth=hx, half=0.3, mat='blade',
             vfn=lambda u, v, w, e: ('glow', 0.3, True) if abs(v - hy) < 0.2 and z0 - L * 0.8 < u < z0 - 0.6 else
             0.5 + 0.25 * min(1.0, e / 0.6))
    g.crystals((hx, hy + 0.6, hz - 3.0), (0, 1, -0.3), n=3, size=1.4, r=0.35, mat='ice', seed=4)
    g.crystals((hx, hy - 0.6, hz - 3.4), (0, -1, -0.4), n=2, size=1.1, r=0.32, mat='ice', seed=5)


def _knight_legs(g: MobGrid, ctx):
    g.rbox((-3.6, -2.4, -2.0), (3.6, 0.6, 2.0), 'iron', 0.42, bevel=0.8)
    for s in (-1, 1):
        x = s * 1.9
        g.capsule((x, -1.4, 0.0), (x, -5.8, -0.1), 1.6, 1.45, 'iron', 0.46)
        g.blob((x, -6.2, -0.7), (1.55, 1.3, 1.2), 'iron', 0.6)                             # poleyn
        g.cone((x, -6.2, -1.7), (0, 0.1, -1), 0.9, 0.5, 'iron', 0.55, 0.8)
        g.capsule((x, -6.8, 0.0), (x, -10.2, 0.1), 1.4, 1.35, 'iron', 0.46)
        for k in range(3):
            g.rbox((x - 1.5, -11.0 - 0.4 * k, -1.8 - 0.5 * k), (x + 1.5, -10.4 - 0.4 * k, 1.6), 'iron', 0.5 - 0.04 * k,
                   bevel=0.3)
        g.rbox((x - 1.6, -12.0, -3.3), (x + 1.6, -11.6, 1.7), 'dark', 0.2)
        g.ring((x, -6.9, 0.0), 1.45, 0.25, axis='y', mat='orn', val=0.5)
    _frost(g, ['iron'], 0.55, 0.5)


def frozen_knight(look, name, part, ctx):
    _knight_ramps(ctx)
    fn = {'torso': _knight_torso, 'head': _knight_head, 'crown': _knight_crown, 'arm_left': _knight_arm,
          'arm_right': _knight_arm, 'shield': _knight_shield, 'sword': _knight_sword, 'legs': _knight_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.7, 'head': 0.6, 'legs': 0.7, 'shield': 0.6, 'crown': 0.55, 'arm_left': 0.6,
                  'arm_right': 0.6}.get(name, 0.55))
    fn(g, ctx)
    return g


# ───────────────────────────── icicle_wraith (고드름 원령) ─────────────────────────────
# A grudge frozen into a shattered icicle: an inverted chandelier of icicles round a glowing heart,
# a wailing face of rime in the middle, a crown of upward shards; a ring of orbiting ice shards and
# cold motes; a tail of frost mist trailing below.

WRAITH_ICE = [(16, 34, 72), (30, 64, 124), (56, 108, 182), (100, 162, 228), (160, 208, 250), (214, 238, 255),
              (250, 254, 255)]
WRAITH_RIME = [(62, 84, 128), (110, 136, 182), (164, 190, 226), (210, 228, 250), (242, 248, 255)]


def _wraith_ramps(ctx):
    ctx.set_ramp('ice', WRAITH_ICE)
    ctx.set_ramp('frost', WRAITH_RIME)
    _set_glow(ctx, FROST_GLOW)


def _glow_tips(g: MobGrid, mats=('ice',), above=0.85):
    for v in g.vox.values():
        if v[0] in mats and v[1] > above:
            v[0], v[2] = 'glow', True


def _wraith_core(g: MobGrid, ctx):
    # a rime skull-mask on top: deep dark sockets with cold pupils, a gaping wail, swept-back crown shards
    g.blob((0, 2.6, -0.4), (2.6, 2.6, 2.4), 'frost', 0.6, top=0.25)
    g.blob((0, 0.9, -1.0), (1.9, 1.4, 1.7), 'frost', 0.5)
    g.rbox((-2.4, 3.2, -3.0), (2.4, 3.9, -2.2), 'frost', 0.75, bevel=0.3)               # brow ridge
    for s_ in (-1, 1):
        g.carve_blob((s_ * 1.05, 2.6, -3.0), (0.95, 1.05, 1.2))
        g.blob((s_ * 1.05, 2.6, -2.0), (0.95, 1.0, 0.7), 'void', 0.12, prio=3, top=0.0)
        g.blob((s_ * 1.05, 2.5, -2.3), (0.55, 0.6, 0.4), 'eye', 0.6, glow=True, prio=5)
        g.cone((s_ * 1.1, 1.5, -2.5), (s_ * 0.05, -1, -0.12), 2.8, 0.3, 'ice', 0.75, 0.95, prio=5)  # frozen tears
    g.carve(lambda x, y, z: (x / 0.85) ** 2 + ((y - 0.7) / 1.05) ** 2 <= 1.0 and z < -1.6)
    g.blob((0, 0.7, -1.4), (0.8, 1.0, 0.45), 'glow', 0.25, glow=True, prio=5)
    for k, x in enumerate((-1.7, -0.7, 0.7, 1.7, 0.0)):
        L = 3.8 if k == 4 else 2.6 + 0.5 * (k % 2)
        g.crystals((x, 4.2, 0.6), (x * 0.25, 0.8, 1.2), n=1, size=L, r=0.6, mat='ice', seed=k + 9)
    # the body: a skirt of icicles hanging round a glowing heart
    g.blob((0, -0.9, 0.8), 1.7, 'core', 0.45, glow=True, prio=2, vfn=lambda x, y, z, d: 0.75 - 0.5 * d)
    g.crystals((0, -0.6, 1.0), (0, -1, 0.1), n=1, size=5.2, r=1.0, mat='ice', seed=1)
    for k in range(7):
        a = 2 * math.pi * k / 7 + 0.45
        b = (math.cos(a) * 2.2, 0.2, 0.9 + math.sin(a) * 2.0)
        g.crystals(b, (math.cos(a) * 0.55, -1, math.sin(a) * 0.45), n=1, size=3.0 + 1.8 * (k % 2), r=0.7, mat='ice',
                   seed=k + 2)
    _glow_tips(g)
    for p in ((-3.8, 2.6, -1.2), (3.6, -0.8, -1.8), (-3.0, -4.0, 1.6), (2.8, 4.2, 1.2), (0.2, -6.0, -1.6)):
        g.dot(p, 'glow', 0.4, glow=True, prio=6)


def _wraith_shards(g: MobGrid, ctx):
    for k in range(9):
        a = 2 * math.pi * k / 9
        R = 8.2 + 0.6 * (k % 2)
        c = (math.cos(a) * R, 0.9 * math.sin(k * 1.7), math.sin(a) * R)
        tang = (-math.sin(a), 0.25 * math.cos(k * 1.3), math.cos(a))
        g.crystals(vsub(c, vmul(tang, 1.4)), tang, n=1, size=3.0 + 0.8 * (k % 3 == 0), r=0.6, mat='ice', seed=k)
        a2 = a + math.pi / 9
        g.dot((math.cos(a2) * 8.0, -0.6 * math.cos(k), math.sin(a2) * 8.0), 'glow', 0.4, glow=True, prio=6)
    _glow_tips(g, above=0.75)


def _wraith_tail(g: MobGrid, ctx):
    # a curling tail of frost mist: pale rim, glowing core streak, shards caught in it
    g.sweep([(0, 1.2, -0.4), (0, -1.6, 1.2), (1.0, -4.2, 2.4), (-0.6, -6.6, 3.2), (0.4, -8.6, 2.6)], 1.5, 0.3,
            'ice', 0.4, vfn=lambda t, d, p: ('glow', 0.2 + 0.2 * (1 - t), True) if d < 0.45 else 0.42 - 0.22 * t)
    for k, (p, d) in enumerate((((1.0, -2.8, 2.0), (0.6, -1, 0.3)), ((-0.9, -5.0, 3.0), (-0.6, -1, 0.2)),
                                ((0.6, -7.2, 3.0), (0.3, -1, 0)))):
        g.crystals(p, d, n=1, size=1.8, r=0.42, mat='ice', seed=k)
    _glow_tips(g)


def icicle_wraith(look, name, part, ctx):
    _wraith_ramps(ctx)
    fn = {'core': _wraith_core, 'shards': _wraith_shards, 'tail': _wraith_tail}.get(name)
    if fn is None:
        return None
    g = ctx.grid(0.5)
    fn(g, ctx)
    return g


# ───────────────────────────── crypt_bellringer (묘역의 종지기, elite) ─────────────────────────────
# A hunched bell-ringer of the crypts: layered tattered funeral robes edged in gold, a rope harness and a
# wooden yoke carrying an enormous bronze funeral bell — ringed with glowing frost runes, a skull relief,
# rime on its shoulder, icicles along its lip and the clapper hanging inside; a deep frosted hood over a
# gaunt face with pale burning eyes and a frozen beard; long bony arms, a bronze-capped bell mallet in
# one hand and a small hand-bell in the other.

RINGER_ROBE = [(10, 11, 16), (20, 22, 30), (34, 38, 50), (52, 58, 74), (76, 84, 102), (106, 114, 134),
               (144, 152, 170)]
BELL_BRONZE = [(26, 18, 8), (54, 38, 16), (94, 68, 30), (138, 104, 48), (180, 144, 72), (214, 182, 104),
               (240, 220, 156), (255, 246, 210)]
RINGER_SKIN = [(36, 40, 50), (66, 72, 86), (102, 110, 124), (142, 150, 162), (184, 190, 198), (220, 224, 230)]


def _ringer_ramps(ctx):
    ctx.set_ramp('cloth', RINGER_ROBE)
    ctx.set_ramp('brass', BELL_BRONZE)
    ctx.set_ramp('flesh', RINGER_SKIN)
    ctx.set_ramp('orn', GOLD_TRIM)
    _set_glow(ctx, FROST_GLOW)


def _ringer_torso(g: MobGrid, ctx):
    # hunched robed body: forward-leaning chest, humped back under the yoke
    g.blob((0, 0.0, -0.4), (5.0, 5.8, 3.8), 'cloth', 0.45, top=0.15)
    g.blob((0, 3.0, 1.6), (4.8, 3.6, 3.2), 'cloth', 0.5)
    for s in (-1, 1):
        g.blob((s * 4.4, 3.6, -0.6), (2.0, 1.8, 2.2), 'cloth', 0.52)
    # tattered robe skirt, gold-edged hem
    ring = [(math.cos(a) * 5.1, -3.6, math.sin(a) * 4.0 - 0.4) for a in [math.pi * 2 * j / 18 for j in range(19)]]
    g.cloth(ring, 4.6, 'cloth', 0.4, tatter=0.5, seed=3, holes=0.0, folds=0.06)
    g.paint(lambda x, y, z, n, m, v: ('orn', 0.55) if n[1] < 0 and y < -3 else None, ['cloth'])
    # gold-edged stole hanging down the front with a few frost runes
    for s in (-1, 1):
        g.rbox((s * 1.1 - 0.65, -6.4, -4.6), (s * 1.1 + 0.65, 4.6, -4.0), 'orn', 0.5)
        g.rbox((s * 1.1 - 0.4, -6.2, -4.75), (s * 1.1 + 0.4, 4.4, -4.5), 'cloth', 0.6)
        for y in (2.4, -0.6, -3.6):
            g.dot((s * 1.1, y, -4.95), 'rune', 0.35, glow=True, prio=6)
    # rope harness crossing the chest up to the yoke, a belt with two small hand-bells
    for s in (-1, 1):
        g.sweep([(s * 3.8, 5.0, -1.6), (s * 1.0, 1.6, -4.2), (-s * 2.6, -2.6, -3.8)], 0.4, 0.4, 'bark', 0.55)
    g.ring((0, -2.8, -0.4), 4.9, 0.4, axis='y', mat='leather', val=0.4)
    for x in (-3.2, 3.6):
        g.capsule((x, -3.0, -3.6), (x, -4.0, -3.8), 0.2, 0.2, 'iron', 0.5)
        g.cone((x, -5.4, -3.8), (0, 1, 0), 1.4, 0.75, 'brass', 0.5, 0.75, r_tip=0.4)
    # wooden yoke frame rising behind the shoulders
    for s in (-1, 1):
        g.capsule((s * 3.0, 3.4, 3.2), (s * 2.2, 8.8, 4.6), 0.55, 0.5, 'wood', 0.45)
    _frost(g, ['cloth'], 0.6, 0.55, region=lambda x, y, z: y > 1.5)
    _icicles(g, ['cloth'], 3, length=(0.8, 1.8), r=0.38, region=lambda x, y, z: y > 1.5)


def _ringer_head(g: MobGrid, ctx):
    # deep hood pulled forward; gaunt face, sunken cheeks, pale burning eyes, a frozen beard
    g.blob((0, 0.6, 0.8), (3.9, 3.9, 3.8), 'cloth', 0.42, cut=lambda x, y, z: z < -1.6 and abs(x) < 2.7 and y < 2.0)
    g.cone((0, 2.6, 2.6), (0, 0.4, 1), 2.8, 1.8, 'cloth', 0.42, 0.45, curl=(0, -0.8, 0.6))
    g.paint(lambda x, y, z, n, m, v: v + 0.16 if n[2] < 0 and z < -1.4 else None, ['cloth'])
    g.blob((0, -0.6, -0.8), (2.6, 3.0, 2.6), 'flesh', 0.42, prio=2)
    g.rbox((-2.4, 0.4, -3.4), (2.4, 1.1, -2.6), 'flesh', 0.38, bevel=0.3, prio=2)
    for s in (-1, 1):
        g.carve_blob((s * 1.9, -1.4, -2.9), (0.8, 0.9, 0.7))
        g.eye((s * 1.05, -0.1, -3.0), 0.45, val=0.45, socket=0.45, facing=(0, 0, -1))
    g.capsule((0, -0.2, -3.3), (0, -1.6, -3.8), 0.4, 0.45, 'flesh', 0.5)                      # long nose
    for k, x in enumerate((-1.1, -0.35, 0.4, 1.1)):
        g.cone((x, -2.4, -2.9), (x * 0.1, -1, -0.15), 2.4 + 0.8 * (k % 2), 0.42, 'frost', 0.6, 0.9, prio=3)
    _frost(g, ['cloth'], 0.6, 0.5)


def _ringer_bell(g: MobGrid, ctx):
    # funeral bell (mouth down) hanging from a yoke beam behind the shoulders: narrow waist, strong flare,
    # thick lip; frost runes round the waist, a skull relief on the back, rime on its shoulder, icicles
    cz, yt, yb = 2.0, 5.6, -6.2

    def r_of(t):        # t 0 = shoulder, 1 = lip
        return 2.9 + 0.7 * t + 3.3 * t ** 3.4

    g.sweep([(0, yt, cz), (0, yb, cz)], 2.9, 6.9, 'brass', 0.5, rfn=r_of, smooth=False,
            vfn=lambda t, d, p: 0.32 + 0.16 * (1 - t) + 0.1 * (1 - d))
    g.carve(lambda x, y, z: y < yt - 1.3 and math.hypot(x, z - cz) < r_of((yt - y) / (yt - yb)) - 0.9)
    g.blob((0, yt + 0.1, cz), (2.9, 1.0, 2.9), 'brass', 0.55)
    g.ring((0, yt + 1.4, cz), 1.2, 0.42, axis='x', mat='brass', val=0.6)                        # crown loop
    g.capsule((-4.2, yt + 2.2, cz), (4.2, yt + 2.2, cz), 0.6, 0.6, 'wood', 0.45)               # yoke beam
    for y, t in ((yt - 1.0, 0.08), (yb + 1.6, 0.87), (yb + 0.3, 0.97)):
        g.ring((0, y, cz), r_of(t) + 0.2, 0.38, axis='y', mat='brass', val=0.75)
    tm = 0.42
    ym = yt - tm * (yt - yb)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        R = r_of(tm) + 0.4
        g.dot((math.cos(a) * R, ym, cz + math.sin(a) * R), 'rune', 0.35, glow=True, prio=6)
        g.dot((math.cos(a) * R, ym - 0.7, cz + math.sin(a) * R), 'rune', 0.3, glow=True, prio=6)
    zb = cz + r_of(0.72) + 0.3
    g.blob((0, yb + 3.2, zb), (1.3, 1.4, 0.55), 'brass', 0.75, prio=3)                        # skull relief
    for s in (-1, 1):
        g.dot((s * 0.5, yb + 3.4, zb + 0.5), 'void', 0.1, prio=5)
    _noise_swap(g, ['brass'], 'patina', 0.22, 2.4, seed=3, v0=0.35, v1=0.6)
    _frost(g, ['brass', 'patina'], 0.75, 0.62)
    _icicles(g, ['brass', 'patina'], 8, length=(1.0, 2.6), r=0.45, region=lambda x, y, z: y < yb + 0.6)
    g.capsule((0, yt - 1.6, cz), (0, yb + 0.6, cz), 0.35, 0.35, 'iron', 0.45)                  # clapper
    g.blob((0, yb + 0.4, cz), 1.0, 'iron', 0.5)
    g.ramp_over['patina'] = VERDIGRIS


def _ringer_arm(g: MobGrid, ctx):
    right = ctx.name == 'arm_right'
    g.capsule((0, -0.4, 0.0), (0, -7.0, -0.2), 1.6, 1.5, 'cloth', 0.46)
    g.cloth([(math.cos(a) * 1.5, -6.6, math.sin(a) * 1.5 - 0.2) for a in [math.pi * 2 * k / 12 for k in range(13)]],
            2.4, 'cloth', 0.42, tatter=0.6, seed=9 + int(right), holes=0.0)
    g.capsule((0, -7.4, -0.2), (0, -12.0, -0.6), 0.85, 0.7, 'flesh', 0.52)
    g.blob((0, -12.8, -0.8), (0.95, 0.85, 0.9), 'flesh', 0.5)
    for k in range(3):
        g.capsule((-0.5 + 0.5 * k, -13.4, -1.5), (-0.5 + 0.5 * k, -14.2, -1.1), 0.26, 0.24, 'flesh', 0.5)
    if right:
        # bell mallet: wooden handle forward, bronze-capped head
        g.capsule((0, -13.2, 0.8), (0, -13.4, -6.6), 0.36, 0.36, 'wood', 0.5)
        g.cylinder((-1.2, -13.4, -7.2), (1.2, -13.4, -7.2), 1.0, 1.0, 'wood', 0.42)
        for x in (-1.3, 1.3):
            g.cylinder((x, -13.4, -7.2), (x * 1.15, -13.4, -7.2), 1.05, 1.05, 'brass', 0.65)
    else:
        # small hand-bell
        g.capsule((0, -13.6, -1.0), (0, -15.2, -1.0), 0.3, 0.3, 'wood', 0.5)
        g.cone((0, -17.4, -1.0), (0, 1, 0), 2.2, 1.2, 'brass', 0.5, 0.75, r_tip=0.5)
        g.ring((0, -17.3, -1.0), 1.2, 0.25, axis='y', mat='brass', val=0.75)
    _frost(g, ['cloth'], 0.55, 0.55)


def _ringer_legs(g: MobGrid, ctx):
    g.rbox((-3.6, -2.4, -2.2), (3.6, 0.6, 2.2), 'cloth', 0.4, bevel=0.8)
    for s in (-1, 1):
        x = s * 1.9
        g.capsule((x, -1.4, 0.0), (x, -6.4, -0.3), 1.6, 1.3, 'cloth', 0.42)
        g.capsule((x, -6.4, -0.3), (x, -10.4, 0.1), 1.05, 0.95, 'leather', 0.38)
        g.bands(['leather'], axis=1, period=0.9, width=0.4, amount=-0.15)
        g.blob((x, -11.2, -0.8), (1.25, 0.8, 1.8), 'flesh', 0.42)
        for k in (-1, 0, 1):
            g.capsule((x + k * 0.5, -11.4, -1.8), (x + k * 0.6, -11.7, -2.8), 0.26, 0.22, 'flesh', 0.48)
    _frost(g, ['cloth', 'leather', 'flesh'], 0.5, 0.5)


def crypt_bellringer(look, name, part, ctx):
    _ringer_ramps(ctx)
    fn = {'torso': _ringer_torso, 'head': _ringer_head, 'bell': _ringer_bell, 'arm_left': _ringer_arm,
          'arm_right': _ringer_arm, 'legs': _ringer_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.65, 'head': 0.55, 'bell': 0.7, 'legs': 0.6}.get(name, 0.5))
    fn(g, ctx)
    return g


DESIGNS = {
    'sluice_drowner': sluice_drowner,
    'brine_spitter': brine_spitter,
    'rust_eel': rust_eel,
    'bubble_jelly': bubble_jelly,
    'verdigris_crab': verdigris_crab,
    'floodling': floodling,
    'slag_golem': slag_golem,
    'cinder_imp': cinder_imp,
    'bellows_hound': bellows_hound,
    'forge_acolyte': forge_acolyte,
    'forge_executioner': forge_executioner,
    'rime_mourner': rime_mourner,
    'crypt_hound': crypt_hound,
    'frozen_knight': frozen_knight,
    'icicle_wraith': icicle_wraith,
    'crypt_bellringer': crypt_bellringer,
}
