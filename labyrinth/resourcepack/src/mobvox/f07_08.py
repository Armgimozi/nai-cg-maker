"""Voxel mob designs — floors 7–8 (수정 공명동 · 망각의 서고).  See README.md (tools: voxel/mob_kit.py).

Floor 7 (crystal resonance caves): shard_skitterer · prism_sentinel · echo_wisp · geode_brute ·
                                  resonance_tuner (elite)
Floor 8 (archive of oblivion):     ink_wraith · page_swarm · biting_tome · archive_sentinel ·
                                  forbidden_keeper (elite)
Shared helpers: _ramps (glow ramps resampled to 11 steps so the pulse survives coarse levels), _shard
(faceted crystal), _bipyr (vertical hexagonal bipyramid with facet / edge info), _robe (flaring cloak with
radial folds and a torn hem), _ering (elliptical band), _veins (glowing fissures on a region), _strata
(sedimentary rock bands), _vsheet (cylindrical page sheet), _sheet_xy (curved sheet extruded along z),
_tri (thin triangle), _scribble (handwriting lines), _drip (hanging ink drop), _strokes (2D inlay).
Part-local choices: biting_tome cover_top = hinge at its pivot, geometry forward (jaw anim lifts it); the
teeth part holds the upper fangs that poke out over the fore-edge.  Held parts: resonance_tuner staff
stands upright through the right fist (top above the head); archive_sentinel chain hangs from the right
fist and drags back (+Z) along the floor.
Coordinates: part px, origin = the part's pivot, front = −Z, model −X = the mob's left.
"""
from __future__ import annotations

import math

from ..util import h2, h3
from ..voxel.mob_kit import MobGrid, fbm3, vadd, vcross, vlen, vmul, vnorm, vsub  # noqa: F401
from ..voxel.palette import _r

GLOW_MATS = ('glow', 'eye', 'core', 'rune', 'lava')
TAU = 2 * math.pi


# ───────────────────────────── shared helpers ─────────────────────────────

def _ramps(ctx, table):
    """Mob-wide ramps.  Glow ramps are resampled to 11 steps so the atlas pulse (±0.16 along the ramp) still
    changes colour after the budget fitter halves the ramps."""
    for mat, cols in table.items():
        ctx.set_ramp(mat, _r(cols, 11) if mat in GLOW_MATS else cols)


def _box(g, lo, hi, mat, val=0.5, **kw):
    """g.rbox that never vanishes: an axis thinner than one voxel snaps to the nearest voxel layer (a plain
    rbox only keeps voxel centres inside [lo, hi], so a 0.2 px trim or a paper sheet would disappear)."""
    vs = g.vs
    lo, hi = list(lo), list(hi)
    for a in range(3):
        if lo[a] > hi[a]:
            lo[a], hi[a] = hi[a], lo[a]
        if hi[a] - lo[a] < vs:
            lo[a] = hi[a] = round((lo[a] + hi[a]) / 2 / vs) * vs
    g.rbox(tuple(lo), tuple(hi), mat, val, **kw)


def _shard(g, base, d, L, r, mat='crystal', glow=False, prio=3, tip=0.45, val=0.0):
    """One faceted crystal (hex prism + point) from base along d, length L px, radius r px.  Like
    core.Grid.crystal but with darker facet values (thin shards otherwise wash out to the ramp's white end
    once the rim highlight is added) and a `val` offset."""
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


FACETS = (0.64, 0.5, 0.34, 0.4, 0.54, 0.74)


def _bipyr(g, c, r, y0, y1, up, dn, mat='crystal', glow=False, prio=3, rot=0.0, vfn=None):
    """Vertical hexagonal bipyramid at c: straight column y0..y1 (relative to c), points `up` / `dn` px
    beyond.  vfn(x, y, z, facet 0..5, edge 0..1 (1 = on a vertical edge), tip −1/0/1) → value | (mat, v[, glow])."""
    vs = g.vs
    ca, sa = math.cos(rot), math.sin(rot)
    third = math.pi / 3
    for i in g._range(c[0] - r, c[0] + r):
        x = i * vs - c[0]
        for k in g._range(c[2] - r, c[2] + r):
            z = k * vs - c[2]
            u, w = x * ca + z * sa, -x * sa + z * ca
            hexd = max(abs(u), abs(u) * 0.5 + abs(w) * 0.866)
            if hexd > r + 1e-6:
                continue
            th = math.atan2(w, u)
            f = int(math.floor((th + third / 2) / third)) % 6
            q = (th + third / 2) % third
            edge = 1.0 - min(q, third - q) / (third / 2)
            for j in g._range(c[1] + y0 - dn, c[1] + y1 + up):
                y = j * vs - c[1]
                if y > y1:
                    rad, tp = r * (1 - (y - y1) / up), 1
                elif y < y0:
                    rad, tp = r * (1 - (y0 - y) / dn), -1
                else:
                    rad, tp = r, 0
                if rad <= 0 or hexd > max(vs * 0.45, rad):
                    continue
                if vfn:
                    res = vfn(x, y, z, f, edge if hexd > rad - vs * 1.1 else 0.0, tp)
                else:
                    res = FACETS[f] + (0.14 if tp > 0 else -0.06 if tp < 0 else 0.0)
                g._emit((i, j, k), res, mat, glow, prio)


def _robe(g, y_top, y_bot, rt, rb, mat='cloth', val=0.45, folds=7, amp=0.12, phase=0.0, zs=0.8, cz=0.0, hem=1.0,
          power=1.0, seed=0, prio=1, skip=None, vfn=None):
    """Flaring robe / cloak from y_top (radius rt) to y_bot (radius rb), elliptical (z radius × zs), radial
    folds (cos folds·θ, stronger toward the hem), torn hem: every angular bucket hangs up to `hem` px lower
    (longest on the fold ridges).  vfn(x, y, z, t 0..1 down the robe, fold −1..1) → value | (mat, v)."""
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


def _veins(g, mats, region=None, width=0.035, scale=4.0, mat='core', val=0.5, glow=True, seed=0):
    """Glowing fissures where 3D noise crosses 0.5 — only inside region(x, y, z)."""
    sd = g.seed + 83 + seed

    def f(x, y, z, n, m, v):
        if region and not region(x, y, z):
            return None
        q = fbm3(x / scale, y / scale, z / scale, sd)
        if abs(q - 0.5) < width:
            return (mat, val + 0.3 * (1 - abs(q - 0.5) / width), glow)
        return None
    g.paint(f, list(mats))


def _strata(g, mats=('stone',), period=2.4, amount=0.13, seed=0, groove=0.14, wave=1.0):
    """Sedimentary rock: gently waving horizontal layers, each its own tone, dark bedding lines."""
    sd = g.seed + 433 + seed

    def f(x, y, z, n, m, v):
        w = y + wave * (0.8 * math.sin(x * 0.3 + z * 0.17 + seed) + 0.9 * (fbm3(x / 5, 0.0, z / 5, sd) - 0.5))
        b = math.floor(w / period)
        dv = amount * (h2(b, 3, sd) - 0.5) * 2
        if (w / period) % 1.0 < 0.13:
            dv -= groove
        return v + dv
    g.paint(f, list(mats))


def _vsheet(g, R, a0, a1, ylo, yhi, mat='paper', vfn=None, dr=0.0, prio=2, thick=1):
    """Cylindrical sheet (a page caught in a whirlwind): arc of radius R (→ R + dr) from angle a0 to a1 around
    the vertical axis; at fraction t the sheet spans ylo(t)..yhi(t).  vfn(t, y, j_from_top, column) → value |
    (mat, v)."""
    vs = g.vs
    L = abs(a1 - a0) * (R + abs(dr))
    n = max(2, int(math.ceil(L / (vs * 0.45))))
    seen = set()
    for q in range(n + 1):
        t = q / n
        a = a0 + (a1 - a0) * t
        for w in range(thick):
            Rr = R + dr * t + w * vs
            i, k = int(round(math.cos(a) * Rr / vs)), int(round(math.sin(a) * Rr / vs))
            if (i, k) in seen:
                continue
            seen.add((i, k))
            lo, hi = ylo(t), yhi(t)
            jt = int(round(hi / vs))
            col = len(seen) - 1
            for j in range(int(round(lo / vs)), jt + 1):
                res = vfn(t, j * vs, jt - j, col) if vfn else 0.6
                g._emit((i, j, k), res, mat, False, prio)


def _sheet_xy(g, pts, z0, z1, mat='paper', vfn=None, prio=2):
    """Curved sheet: a polyline in the XY plane (px) extruded from z0 to z1.  vfn(t, z) → value | (mat, v)."""
    vs = g.vs
    path = []
    for a, b in zip(pts, pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(math.ceil(L / (vs * 0.45))))
        for q in range(n):
            path.append((a[0] + (b[0] - a[0]) * q / n, a[1] + (b[1] - a[1]) * q / n))
    path.append(pts[-1])
    cols = []
    for p in path:
        key = (int(round(p[0] / vs)), int(round(p[1] / vs)))
        if not cols or cols[-1] != key:
            cols.append(key)
    for ci, (i, j) in enumerate(cols):
        t = ci / max(1, len(cols) - 1)
        for k in g._range(min(z0, z1), max(z0, z1)):
            if not (min(z0, z1) - 1e-6 <= k * vs <= max(z0, z1) + 1e-6):
                continue
            res = vfn(t, k * vs) if vfn else 0.6
            g._emit((i, j, k), res, mat, False, prio)


def _tri(g, a, b, c, mat='paper', val=0.6, prio=2, vfn=None):
    """Thin triangle a-b-c (px), one voxel thick.  vfn(u, v) with barycentric u (toward b), v (toward c)."""
    L = max(vlen(vsub(b, a)), vlen(vsub(c, a)), vlen(vsub(c, b)))
    n = int(L / (g.vs * 0.4)) + 1
    for i in range(n + 1):
        for j in range(n + 1 - i):
            u, v = i / n, j / n
            p = vadd(a, vadd(vmul(vsub(b, a), u), vmul(vsub(c, a), v)))
            k = g.key(p)
            res = vfn(u, v) if vfn else val
            g._emit(k, res, mat, False, prio)


def _scribble(g, mats=('paper',), facing=(0, 0, -1), region=None, period=2, gap=0.3, mat='ink', val=0.3, seed=0,
              glow=False, word=5):
    """Handwriting on the surfaces facing `facing`: every `period`-th voxel row gets ink words (runs of up to
    word−1 voxels) broken by gaps; rows start at a random indent."""
    f = vnorm(facing)
    sd = g.seed + 601 + seed
    fa = max(range(3), key=lambda a: abs(f[a]))
    sgn = 1 if f[fa] > 0 else -1
    row_ax = 1 if fa != 1 else 2
    col_ax = [a for a in range(3) if a not in (fa, row_ax)][0]
    for key, n in g.exposed(mats):
        if n[fa] * sgn <= 0:
            continue
        if region and not region(*g.px(key)):
            continue
        r = key[row_ax]
        if r % period:
            continue
        c = key[col_ax] + int(h2(r, 7, sd) * 9)
        if c % word == word - 1 or h2(r, c // word, sd + 1) < gap:
            continue
        cur = g.vox[key]
        cur[0], cur[1], cur[2] = mat, val, glow


def _chain_lite(g, pts, link=1.3, mat='iron', val=0.5, prio=3):
    """Cheap chain for long loops (g.chain's round links cost ~8 elements each): a one-voxel strand whose
    links alternate a bright upright link (one voxel taller) and a dark flat link."""
    from ..voxel.core import resample
    vs = g.vs
    seen = set()
    path = resample(list(pts), vs * 0.5)
    total = 0.0
    prev = None
    for p, t in path:
        if prev is not None:
            total += vlen(vsub(p, prev))
        prev = p
        n = int(total / link)
        k = g.key(p)
        if k in seen:
            continue
        seen.add(k)
        if n % 2 == 0:
            g.put(k[0], k[1], k[2], mat, val + 0.14, False, prio)
            g.put(k[0], k[1] + 1, k[2], mat, val + 0.2, False, prio)
        else:
            g.put(k[0], k[1], k[2], mat, val - 0.16, False, prio)


def _drip(g, top, L, r=0.42, mat='ink', val=0.5, drop=None, prio=4):
    """Hanging drip: a thin run from `top` down L px ending in a fat glossy drop."""
    x, y, z = top
    g.capsule((x, y, z), (x, y - L, z), r, r * 0.8, mat, val, prio=prio)
    g.blob((x, y - L - (drop or r * 1.4) * 0.6, z), drop or r * 1.45, mat, val + 0.25, prio=prio + 1, top=0.2)


def _glint(g, mats, n=6, mat='spec', seed=0):
    """A few rainbow sparkle voxels (glowing spectrum colours) on the highest-facing crystal voxels."""
    sd = g.seed + 211 + seed
    cands = [key for key, nn in g.exposed(mats) if nn[1] > 0]
    cands.sort(key=lambda q: -q[1] - 3 * h3(q[0], q[1], q[2], sd))
    for k, key in enumerate(cands[:n]):
        cur = g.vox[key]
        cur[0], cur[1], cur[2] = mat, (k * 0.37) % 1.0, True


def _strokes(g, c, normal, strokes, mat, val, glow=False, depth=10.0, prio=6):
    """Inlay 2D strokes (u sideways, v up, px around c) onto the surface facing `normal`."""
    f = vnorm(normal)
    side = vnorm(vcross((0, 1, 0), f))
    for st in strokes:
        for (u0, v0), (u1, v1) in zip(st, st[1:]):
            n = max(1, int(math.hypot(u1 - u0, v1 - v0) / (g.vs * 0.8)))
            for k in range(n + 1):
                u, v = u0 + (u1 - u0) * k / n, v0 + (v1 - v0) * k / n
                o = vadd(vadd(vadd(c, vmul(side, u)), (0, v, 0)), vmul(f, depth))
                p = g.hit(o, vmul(f, -1), depth * 2)
                if p is not None:
                    g.dot(p, mat, val, glow=glow, prio=prio)


SPECTRUM = [(255, 86, 110), (255, 150, 70), (255, 226, 90), (120, 236, 140), (80, 200, 255), (120, 130, 255),
            (196, 110, 255)]


# ═════════════════════════════ FLOOR 7 · 수정 공명동 ═════════════════════════════

# ───────────────────────────── shard_skitterer (파편 갑충) ─────────────────────────────
# A glossy violet-black beetle whose wing cases split along a glowing resonant seam; amethyst shards it
# picked up in the caves are driven into its back like quills around a glowing core, a crystal horn on
# its brow, mandibles with crystal tips, faceted magenta eyes and antennae ending in humming crystal beads,
# and it walks on six legs whose lower segments are crystal stilts.

SK_CHITIN = [(6, 5, 12), (14, 10, 28), (28, 18, 50), (46, 28, 80), (66, 40, 114), (88, 58, 150), (110, 80, 184),
             (120, 150, 210), (150, 214, 230)]                          # violet with a teal iridescent sheen
SK_BELLY = [(8, 6, 12), (18, 12, 26), (30, 22, 42), (46, 34, 62), (66, 50, 86), (90, 70, 112)]
SK_CRYSTAL = [(40, 8, 56), (84, 20, 112), (132, 44, 170), (180, 80, 220), (214, 126, 246), (238, 178, 255),
              (252, 226, 255)]
SK_GLOW = [(110, 34, 160), (160, 70, 226), (204, 128, 255), (234, 188, 255), (250, 230, 255), (255, 255, 255)]
SK_EYE = [(130, 30, 110), (210, 70, 190), (252, 140, 236), (255, 204, 250), (255, 238, 255), (255, 255, 255)]
SK_STONE = [(16, 12, 22), (30, 24, 40), (48, 40, 62), (70, 60, 88), (96, 86, 116), (126, 116, 146)]


def _sk_body(g: MobGrid, ctx):
    g.blob((0, -1.8, 0.4), (4.8, 1.6, 6.2), 'skin', 0.24, top=0.0)                       # belly
    # pronotum: a wide shield over the neck, overhanging the head a little
    g.plates((0, 0.2, -4.2), (5.4, 2.7, 2.9), n=2, axis=2, mat='chitin', val=0.52, lift=0.1, groove=-0.3,
             reverse=True, cut=lambda x, y, z: y < -1.7)
    # elytra: two domed wing cases, three growth bands each, a glowing seam between them
    for s in (-1, 1):
        g.plates((s * 2.75, 0.7, 2.0), (3.3, 3.0, 5.6), n=3, axis=2, mat='chitin', val=0.46, lift=0.08, groove=-0.24,
                 lip=0.18, cut=lambda x, y, z, s=s: y < -1.7 or x * s < 0.7)
    _box(g, (-0.9, -1.0, -2.2), (0.9, 3.0, 7.0), 'core', 0.5, glow=True, prio=0)
    # flared rim over the leg roots with small crystal studs; glowing spiracles under it
    for s in (-1, 1):
        g.capsule((s * 4.9, -0.9, -5.4), (s * 5.7, -0.7, 6.2), 0.75, 0.7, 'chitin', 0.7)
        for z in (-3.2, 0.6, 4.2):
            _shard(g, (s * 5.5, -0.5, z), (s, 0.55, 0.35), 1.7, 0.5, 'crystal')
        for z in (-1.4, 2.4):
            g.dot((s * 5.9, -1.5, z), 'core', 0.6, glow=True, prio=5)
    # a crystal sting at the abdomen tip
    _shard(g, (0, 0.2, 7.0), (0, 0.15, 1), 2.6, 0.75, 'crystal')
    g.mottle(['chitin'], 0.07, 3.0)


def _sk_crystals(g: MobGrid, ctx):
    # the shell broken open where the shards went in: a dark rock matrix with a glowing core
    g.blob((0, -2.8, 0.2), (3.6, 1.3, 4.4), 'stone', 0.4, lump=0.25, lump_scale=1.6, top=0.25)
    g.blob((0, -2.2, -0.2), (1.5, 1.0, 1.7), 'core', 0.62, glow=True, prio=4)
    shards = [  # base, direction, length, radius — quills driven in at angles, leaning back
        ((0.0, -2.0, -0.4), (0.05, 1, 0.3), 7.4, 1.35),
        ((1.7, -2.2, 1.2), (0.55, 1, 0.55), 5.6, 1.05),
        ((-1.8, -2.2, 0.8), (-0.65, 1, 0.35), 6.0, 1.1),
        ((0.5, -2.3, 3.2), (0.15, 0.7, 1), 5.0, 0.95),
        ((-0.9, -2.2, -2.6), (-0.3, 1, -0.45), 4.0, 0.8),
        ((2.5, -2.4, -1.6), (0.95, 0.85, -0.15), 3.6, 0.72),
        ((-2.8, -2.4, 2.6), (-1, 0.6, 0.6), 3.4, 0.66),
        ((1.2, -2.6, -3.4), (0.4, 0.8, -0.7), 2.6, 0.6),
        ((-0.6, -2.5, 3.9), (-0.2, 0.35, 1), 3.2, 0.62),
    ]
    for base, d, L, r in shards:
        _shard(g, base, d, L, r, 'crystal')


def _sk_head(g: MobGrid, ctx):
    g.blob((0, 0.2, 0.5), (2.6, 2.0, 2.3), 'chitin', 0.5, top=0.2)
    g.blob((0, -0.9, -1.0), (2.0, 1.1, 1.6), 'skin', 0.3)                                # mouth plate
    g.capsule((-2.0, 1.35, -1.3), (2.0, 1.35, -1.3), 0.55, 0.55, 'chitin', 0.68)          # brow ridge
    for s in (-1, 1):
        g.eye((s * 1.75, 0.5, -1.2), 0.8, val=0.42, socket=0.3, facing=(s * 0.6, 0.1, -1))
        g.eye((s * 0.7, 0.95, -2.0), 0.42, val=0.5, facing=(0, 0.2, -1))
    _shard(g, (0, 1.4, -0.9), (0, 1, -0.75), 3.6, 0.72, 'crystal')                       # brow horn
    for s in (-1, 1):
        g.horn((s * 1.1, -1.2, -1.9), (s * 0.4, -0.2, -1), 2.9, 0.62, curl=(-s * 1.3, 0.2, 0), mat='chitin',
               val=0.36, tip_mat='crystal')
        pts = [(s * 1.2, 1.5, -1.6), (s * 2.3, 3.3, -2.5), (s * 3.5, 4.3, -1.6), (s * 4.2, 4.5, -0.2)]
        g.sweep(pts, 0.4, 0.32, 'chitin', 0.66)
        g.blob(pts[-1], 0.45, 'glow', 0.7, glow=True, prio=4)


def _sk_legs(g: MobGrid, ctx):
    gy = -2.88
    g.light_mul = 0.5
    plan = [  # root, knee, ankle, foot (+X side), front → back
        ((3.4, 0.9, -3.8), (7.0, 4.4, -6.2), (8.9, 1.6, -8.2), (9.6, gy, -9.4)),
        ((3.8, 0.7, -0.2), (8.0, 4.6, -0.6), (10.0, 1.4, -0.8), (10.8, gy, -0.9)),
        ((3.4, 0.9, 3.4), (7.2, 4.4, 5.6), (9.1, 1.6, 7.6), (9.8, gy, 8.8)),
    ]
    for s in (-1, 1):
        for R, K, A, F in plan:
            R, K, A, F = [(s * q[0], q[1], q[2]) for q in (R, K, A, F)]
            g.limb([R, K, A], [1.0, 0.74, 0.6], 'chitin', 0.46, joint_val=0.64, knob=1.2)
            d = vsub(F, A)
            _shard(g, A, d, vlen(d) + 0.3, 0.74, 'crystal', tip=0.6)                      # crystal stilt


def shard_skitterer(look, name, part, ctx):
    _ramps(ctx, {'chitin': SK_CHITIN, 'skin': SK_BELLY, 'crystal': SK_CRYSTAL, 'core': SK_GLOW, 'glow': SK_GLOW,
                 'eye': SK_EYE, 'stone': SK_STONE, 'spec': SPECTRUM})
    fn = {'body': _sk_body, 'crystals': _sk_crystals, 'head': _sk_head, 'legs': _sk_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.6, 'crystals': 0.6, 'head': 0.45, 'legs': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── prism_sentinel (프리즘 파수석) ─────────────────────────────
# A clear quartz prism hovering in the claws of an obsidian plinth.  The prism is a tall hexagonal
# bipyramid whose vertical edges burn in the colours of the spectrum, with a glowing lens band at its waist
# and satellite crystals; the stepped octagonal plinth carries silver bands and glowing glyphs, crystal
# rubble grows round its foot; a silver ring of floating prism shards orbits the waist.

PS_STONE = [(8, 7, 14), (16, 14, 26), (26, 23, 40), (40, 36, 58), (58, 52, 80), (80, 72, 106), (106, 98, 136),
            (140, 132, 170)]
PS_SILVER = [(28, 28, 40), (58, 58, 76), (98, 98, 120), (146, 146, 168), (196, 196, 214), (232, 232, 246),
             (252, 252, 255)]
PS_CRYSTAL = [(28, 24, 74), (52, 50, 124), (84, 86, 178), (126, 134, 222), (176, 186, 246), (218, 226, 255),
              (248, 250, 255)]
PS_CORE = [(120, 90, 210), (166, 138, 244), (208, 190, 255), (236, 228, 255), (250, 248, 255), (255, 255, 255)]
PS_AMETHYST = [(36, 14, 60), (70, 32, 112), (112, 62, 170), (156, 104, 224), (198, 158, 250), (232, 214, 255)]


def _octagon(r):
    return lambda u, v: max(abs(u), abs(v), (abs(u) + abs(v)) * 0.7071) <= r


def _ps_base(g: MobGrid, ctx):
    gy = -3.2
    g.slab2d(_octagon(6.4), (-7, -7), (7, 7), 'xz', gy + 0.7, 0.7, 'stone',
             vfn=lambda u, v, w, e: 0.4 + (0.2 if e < 0.7 else 0))
    g.slab2d(_octagon(5.0), (-6, -6), (6, 6), 'xz', -0.2, 1.6, 'stone',
             vfn=lambda u, v, w, e: 0.5 if e > 0.6 else 0.56)
    g.slab2d(_octagon(4.4), (-5, -5), (5, 5), 'xz', 2.0, 0.6, 'brass',
             vfn=lambda u, v, w, e: 0.7 if e < 0.7 else (0.3 if e > 2.2 else 0.44))
    g.slab2d(_octagon(2.6), (-3, -3), (3, 3), 'xz', 2.7, 0.2, 'core',
             vfn=lambda u, v, w, e: ('core', 0.25 + 0.1 * e, True))                    # glowing socket well
    for k in range(8):
        a = TAU * k / 8
        g.dot((math.cos(a) * 3.9, 2.75, math.sin(a) * 3.9), 'brass', 0.9, prio=4)       # rim studs
    # silver bands round the middle tier, glyphs on its four main faces
    for y in (-1.6, 1.2):
        g.slab2d(_octagon(5.25), (-6, -6), (6, 6), 'xz', y, 0.2, 'brass', vfn=lambda u, v, w, e: 0.56)
    for a in range(4):
        n = [(0, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 0)][a]
        g.runes(vadd(vmul(n, 4.6), (0, -0.2, 0)), n, w=2.4, h=3.0, mat='rune', val=0.5, density=1.0, seed=a,
                depth=4.0)
    # silver pilasters on the eight corners of the middle tier
    for k in range(8):
        a = TAU * (k + 0.5) / 8
        g.capsule((math.cos(a) * 5.25, -1.6, math.sin(a) * 5.25), (math.cos(a) * 5.25, 1.2, math.sin(a) * 5.25), 0.45,
                  0.45, 'brass', 0.62, prio=3)
    # four silver claws rising from the socket, curling in toward the floating prism
    for k in range(4):
        a = TAU * (k + 0.5) / 4
        ca, sa = math.cos(a), math.sin(a)
        g.sweep([(ca * 3.6, 2.4, sa * 3.6), (ca * 3.9, 4.0, sa * 3.9), (ca * 3.1, 5.6, sa * 3.1),
                 (ca * 2.3, 6.2, sa * 2.3)], 0.6, 0.3, 'brass', 0.6, smooth=True)
        _shard(g, (ca * 2.4, 6.1, sa * 2.4), (-ca * 0.6, 0.8, -sa * 0.6), 1.2, 0.35, 'amethyst', tip=0.8)
    # crystal rubble growing round the foot of the plinth (amethyst, not the prism's clear quartz)
    for k, (a, n, size) in enumerate(((0.3, 3, 2.6), (1.5, 2, 1.8), (2.6, 3, 2.9), (3.9, 2, 2.0), (5.1, 3, 2.4))):
        ca, sa = math.cos(a), math.sin(a)
        g.crystals((ca * 6.4, gy + 0.4, sa * 6.4), (ca * 0.8, 1, sa * 0.8), n=n, size=size, r=0.75, mat='amethyst',
                   spread=0.7, seed=10 + k)


def _ps_prism(g: MobGrid, ctx):
    def vfn(x, y, z, f, edge, tp):
        if edge > 0.8 and tp >= 0 and y > -3.0:
            return ('spec', f / 5.0, True)                     # spectral edges (the light it bends)
        if -0.9 < y < 0.9 and tp == 0:
            return ('core', 0.2 + 0.35 * (1 - edge) + 0.15 * (abs(y) < 0.3), True)   # the lens band it fires from
        v = (0.62, 0.46, 0.24, 0.32, 0.5, 0.74)[f] + (0.1 if tp > 0 else -0.1 if tp < 0 else 0.0)
        if 0.05 < edge < 0.3:
            v += 0.12                                          # glassy reflection streak down each facet
        return v
    _bipyr(g, (0, 0.6, 0), 2.7, -3.6, 4.0, 6.0, 5.6, 'crystal', vfn=vfn, prio=3)
    # satellite crystals at the waist: three leaning up, three leaning down (offset)
    for k in range(3):
        a = TAU * k / 3 + 0.4
        ca, sa = math.cos(a), math.sin(a)
        _shard(g, (ca * 2.0, 2.4, sa * 2.0), (ca * 0.55, 1, sa * 0.55), 3.4, 0.75, 'crystal')
        b = a + math.pi / 3
        cb, sb = math.cos(b), math.sin(b)
        _shard(g, (cb * 2.0, -2.0, sb * 2.0), (cb * 0.5, -1, sb * 0.5), 2.8, 0.66, 'crystal')
    g.dot((0, 10.6, 0), 'core', 0.9, glow=True, prio=6)


def _ps_ring(g: MobGrid, ctx):
    R = 7.4
    g.ring((0, 0, 0), R, 0.42, axis='y', mat='brass', val=0.55)
    for k in range(6):
        a = TAU * k / 6
        ca, sa = math.cos(a), math.sin(a)
        _bipyr(g, (ca * R, 0.0, sa * R), 0.85, -0.5, 0.5, 1.9, 1.4, 'crystal', rot=a)
        b = a + math.pi / 6
        g.dot((math.cos(b) * R, 0.4, math.sin(b) * R), 'rune', 0.6, glow=True, prio=6)
        g.blob((math.cos(b + math.pi / 6) * R, 0, math.sin(b + math.pi / 6) * R), (0.5, 0.65, 0.5), 'brass', 0.75,
               prio=4)
    _glint(g, ['crystal'], 4)


def prism_sentinel(look, name, part, ctx):
    _ramps(ctx, {'stone': PS_STONE, 'brass': PS_SILVER, 'crystal': PS_CRYSTAL, 'core': PS_CORE, 'rune': PS_CORE,
                 'glow': PS_CORE, 'spec': SPECTRUM, 'amethyst': PS_AMETHYST})
    fn = {'base': _ps_base, 'prism': _ps_prism, 'ring': _ps_ring}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'base': 0.5, 'prism': 0.45, 'ring': 0.45}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── echo_wisp (메아리 정령) ─────────────────────────────
# A resonance made visible: a singing lavender light-heart pierced by an eight-pointed crystal star, a
# hollow-eyed face with its mouth open in song; around it ripple arcs ((( ))) of glowing sound on a
# thin crystal hoop, crystal notes riding the hoop; behind it a ribbon of light with tiny crystal chimes.

EW_CORE = [(84, 40, 150), (134, 82, 226), (182, 142, 255), (222, 200, 255), (246, 236, 255), (255, 255, 255)]
EW_RIPPLE = [(70, 60, 170), (110, 110, 236), (160, 172, 255), (206, 220, 255), (236, 244, 255), (255, 255, 255)]
EW_CRYSTAL = [(44, 14, 82), (84, 36, 144), (126, 70, 204), (166, 110, 240), (200, 154, 254), (228, 198, 255),
              (248, 236, 255)]


def _ew_core(g: MobGrid, ctx):
    g.blob((0, 0, 0), 2.7, 'core', glow=True, prio=2,
           vfn=lambda x, y, z, d: 0.32 + 0.5 * max(0.0, (-z * 0.7 + y * 0.45) / 2.7) + 0.12 * (1 - d))
    star = [((0, 1, 0.1), 3.4, 0.9), ((0, -1, 0.2), 3.0, 0.8), ((1, 0.15, 0.3), 2.6, 0.75), ((-1, 0.15, 0.3), 2.6, 0.75),
            ((0.62, 0.72, 0.5), 2.2, 0.6), ((-0.62, 0.72, 0.5), 2.2, 0.6), ((0.55, -0.62, 0.6), 2.0, 0.55),
            ((-0.55, -0.62, 0.6), 2.0, 0.55), ((0, 0.25, 1), 2.6, 0.7)]
    for d, L, r in star:
        _shard(g, vmul(vnorm(d), 1.9), d, L, r, 'crystal', prio=3)
    # a white-hot nucleus showing through the front of the light, ringed by a darker halo band
    g.blob((0, 0.2, -2.0), (1.1, 1.1, 0.9), 'core', 1.0, glow=True, prio=4)
    g.ring((0, 0.2, -2.3), 1.75, 0.3, axis='z', mat='core', val=0.12, glow=True, prio=5)


def _ew_rings(g: MobGrid, ctx):
    g.ring((0, 0, 0.5), 6.7, 0.3, axis='z', mat='crystal', val=0.62)
    for s in (-1, 1):
        a0 = 0.0 if s > 0 else 0.5
        for k, R in enumerate((4.7, 5.7)):
            w = 0.1 - 0.015 * k
            g.ring((0, 0, -0.5 + k * 0.5), R, 0.3, axis='z', mat='rune', val=0.55 + 0.12 * k, glow=True,
                   arc=(a0 - w, a0 + w), prio=4)
    # crystal nodes on the hoop, and two crystal notes riding it (♪ top, ♫-ish bottom)
    for k in range(4):
        a = TAU * (k + 0.5) / 4
        _bipyr(g, (math.cos(a) * 6.7, math.sin(a) * 6.7, 0.5), 0.6, -0.4, 0.4, 0.9, 0.9, 'crystal', rot=a)
    for ang in (100, -38):
        a = math.radians(ang)
        x0, y0 = math.cos(a) * 7.9, math.sin(a) * 7.9 - 0.9
        g.blob((x0 - 0.8, y0, 0.0), (0.85, 0.62, 0.5), 'rune', 0.7, glow=True, prio=5)
        g.capsule((x0, y0 + 0.2, 0.0), (x0, y0 + 2.6, 0.0), 0.28, 0.28, 'rune', 0.75, glow=True, prio=5)
        g.sweep([(x0, y0 + 2.6, 0.0), (x0 + 0.9, y0 + 2.0, 0.0), (x0 + 1.4, y0 + 1.1, 0.0)], 0.3, 0.25, 'rune',
                0.8, glow=True, prio=5)


def _ew_tail(g: MobGrid, ctx):
    pts = [(0, 0.8, -1.2), (0, 0.1, 1.8), (0.7, -0.7, 4.4), (-0.5, -0.3, 6.8), (0.3, 0.7, 9.0), (0.0, 1.7, 10.4)]
    g.sweep(pts, 1.5, 0.3, 'glow', glow=True, vfn=lambda t, d, p: 0.82 - 0.55 * t)
    for s in (-1, 1):
        sp = [(0, 0.3, 0.2), (s * 1.4, -0.5, 2.6), (s * 2.1, 0.2, 4.8), (s * 2.4, 1.2, 6.4)]
        g.sweep(sp, 0.55, 0.25, 'glow', glow=True, vfn=lambda t, d, p: 0.62 - 0.4 * t)
        # a crystal chime hanging on a thread from each side strand
        top = sp[2]
        g.capsule(top, vadd(top, (0, -1.4, 0)), 0.2, 0.2, 'crystal', 0.8)
        _bipyr(g, vadd(top, (0, -2.6, 0)), 0.55, -0.4, 0.4, 0.8, 1.1, 'crystal')
    for p in ((1.6, 1.4, 3.2), (-1.8, 0.8, 5.0), (1.0, -1.2, 6.2), (-0.8, 2.4, 7.6), (0.6, 2.8, 10.6)):
        g.dot(p, 'glow', 0.92, glow=True, prio=4)


def echo_wisp(look, name, part, ctx):
    _ramps(ctx, {'core': EW_CORE, 'glow': EW_CORE, 'rune': EW_RIPPLE, 'eye': EW_CORE, 'crystal': EW_CRYSTAL})
    fn = {'core': _ew_core, 'rings': _ew_rings, 'tail': _ew_tail}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'core': 0.4, 'rings': 0.45, 'tail': 0.45}.get(name, 0.45))
    fn(g, ctx)
    return g


# ───────────────────────────── geode_brute (정동 거한) ─────────────────────────────
# A hunched giant of banded basalt: its chest is split open into a geode — an agate rind of white and
# lilac bands around a cavity packed with amethyst points and a glowing heart crystal — and violet light
# leaks out through fissures.  Amethyst clusters burst from its back and shoulders, its small sunken head
# wears a crest of crystals and stone tusks, and its gorilla fists are studded with crystal knuckles.

GB_STONE = [(16, 14, 22), (30, 27, 38), (46, 42, 58), (66, 61, 80), (90, 84, 106), (118, 111, 136), (150, 143, 168),
            (186, 180, 204)]
GB_RIND = [(80, 74, 104), (138, 132, 164), (190, 186, 210), (224, 222, 238), (246, 244, 252)]
GB_CRYSTAL = [(26, 4, 46), (56, 12, 100), (94, 30, 160), (136, 60, 214), (174, 100, 246), (208, 150, 255),
              (236, 206, 255)]
GB_CORE = [(110, 30, 170), (160, 70, 230), (204, 130, 255), (234, 190, 255), (250, 232, 255), (255, 255, 255)]


def _gb_torso(g: MobGrid, ctx):
    # hunched boulder torso: a broad chest mass, a narrower belly block, shoulder boulders, a back hump
    g.blob((0, 1.6, 0.8), (8.2, 6.6, 5.4), 'stone', 0.5, lump=0.05, lump_scale=5.0, top=0.12)
    _box(g, (-5.8, -7.8, -3.8), (5.8, -1.0, 4.6), 'stone', 0.44, bevel=1.8)
    for s in (-1, 1):
        _box(g, (s * 5.0, 2.0, -3.6), (s * 9.4, 8.6, 4.4), 'stone', 0.54, bevel=1.9)
        _box(g, (s * 6.8, -3.4, -2.4), (s * 8.8, 1.6, 2.6), 'stone', 0.4, bevel=0.9)          # flank chunk
    g.blob((0, 5.2, 3.0), (5.0, 2.8, 2.6), 'stone', 0.56)
    _strata(g, period=4.0, wave=0.2, groove=0.0, amount=0.08)
    # the geode: banded agate rind lip, then the hollow the geode part sits in
    g.blob((0, 0.6, -4.4), (5.2, 5.6, 2.5), 'rind', prio=2,
           vfn=lambda x, y, z, d: ('rind', 0.85) if d > 0.84 else ('rind', 0.42))
    g.carve_blob((0, 0.6, -6.3), (4.1, 4.5, 2.9))
    # violet light leaking through fissures round the cavity
    _veins(g, ['stone'], region=lambda x, y, z: z < -2.0 and math.hypot(x, y - 0.6) < 8.0, width=0.04, scale=4.2,
           mat='core', val=0.05)
    # amethyst clusters erupting from the back and shoulders (mostly upright: cheap and readable)
    for k, (base, up, n, size, r) in enumerate((((-5.6, 7.6, 1.6), (-0.3, 1, 0.3), 3, 5.0, 1.4),
                                                 ((5.4, 7.8, 1.4), (0.25, 1, 0.3), 3, 5.8, 1.6),
                                                 ((0.4, 6.6, 5.0), (0.0, 0.7, 1), 2, 3.6, 1.1))):
        g.crystals(base, up, n=n, size=size, r=r, mat='crystal', spread=0.6, seed=20 + k)


def _gb_geode(g: MobGrid, ctx):
    g.blob((0, 0.6, 1.5), (4.2, 4.6, 1.0), 'crystal', 0.1, top=0.0)                       # dark druzy wall
    for iy in range(-3, 4):
        for ix in range(-3, 4):
            x = ix * 1.8 + (0.9 if iy % 2 else 0.0)
            y = 0.6 + iy * 1.55
            rr = math.hypot(x / 4.0, (y - 0.6) / 4.4)
            if rr > 1.0 or rr < 0.25:
                continue
            base = (x, y, 1.4 - 2.4 * rr * rr)
            d = (0, 0, -1)                                     # axis-aligned points: a dense druzy bed, cheap
            L = 1.5 + 1.6 * (1 - rr) * (0.6 + 0.4 * h2(ix, iy, 5))
            _shard(g, base, d, L, 0.66 + 0.2 * h2(iy, ix, 6), 'crystal', tip=0.55)
    _shard(g, (0, 0.2, 1.0), (0, 0.2, -1), 3.8, 1.4, 'core', glow=True, prio=5)         # the heart crystal
    g.blob((0, 0.6, 0.5), 1.3, 'core', 0.7, glow=True, prio=5)


def _gb_head(g: MobGrid, ctx):
    _box(g, (-3.6, -2.4, -3.4), (3.6, 2.6, 3.8), 'stone', 0.5, bevel=1.4)
    _box(g, (-3.9, 0.5, -4.0), (3.9, 1.9, -2.2), 'stone', 0.64, bevel=0.6)                # heavy brow
    _box(g, (-3.0, -3.6, -3.9), (3.0, -1.6, 1.2), 'stone', 0.42, bevel=0.8)               # underbite jaw
    for s in (-1, 1):
        g.eye((s * 1.5, -0.4, -3.4), 0.75, val=0.6, socket=0.35, facing=(0, -0.1, -1))
        g.cone((s * 2.1, -2.0, -3.9), (s * 0.15, 1, -0.25), 2.0, 0.6, 'rind', 0.55, 0.92)   # stone tusks
    _strata(g, period=1.8, seed=2, wave=0.2, groove=0.0)
    g.crystals((0.6, 2.4, 0.8), (0.15, 1, 0.3), n=3, size=3.8, r=1.05, mat='crystal', spread=0.7, seed=31)


def _gb_arm(g: MobGrid, ctx):
    o = ctx.out
    g.blob((o * 0.6, -1.0, 0.2), (4.2, 3.6, 4.2), 'stone', 0.52, top=0.18)                 # shoulder boulder
    g.blob((0, -5.8, 0.0), (2.5, 3.6, 2.5), 'stone', 0.46, seed=6)                                       # upper arm
    g.blob((0, -9.8, 0.2), (2.9, 1.8, 3.0), 'stone', 0.56, lump=0.08, lump_scale=2.0, seed=7)            # elbow
    g.blob((0, -13.2, -0.3), (3.1, 3.0, 3.2), 'stone', 0.48, lump=0.08, lump_scale=2.5, seed=8)          # forearm
    g.blob((0, -17.6, -0.7), (3.9, 2.9, 3.8), 'stone', 0.52, lump=0.1, lump_scale=2.2, top=0.16, seed=2)   # fist
    _strata(g, seed=5, period=3.0, wave=0.2, groove=0.0)
    for x in (-2.4, -0.8, 0.8, 2.4):
        _shard(g, (x, -17.6, -3.9), (0, 0, -1), 1.9, 0.62, 'crystal')                      # crystal knuckles
    g.crystals((o * 2.4, 1.6, 0.6), (o * 0.4, 1, 0.1), n=3, size=4.4, r=1.15, mat='crystal', spread=0.6, seed=40)


def _gb_legs(g: MobGrid, ctx):
    gy = -14.4
    g.blob((0, -1.2, 0.2), (6.4, 2.6, 3.6), 'stone', 0.44, lump=0.06, lump_scale=3.0, seed=9)
    for s in (-1, 1):
        x = s * 3.4
        g.blob((x, -5.0, 0.0), (2.7, 2.8, 2.6), 'stone', 0.46, lump=0.08, lump_scale=2.5, seed=10 + s)   # thigh
        g.blob((x, -8.0, -0.4), (2.8, 1.6, 2.8), 'stone', 0.56, seed=12 + s)                              # knee
        g.blob((x, -10.6, 0.0), (2.2, 2.0, 2.1), 'stone', 0.44, seed=14 + s)                              # shin
        _box(g, (x - 3.0, gy, -3.6), (x + 3.0, gy + 2.8, 2.8), 'stone', 0.48, bevel=1.0)   # foot
        for tx in (-1.3, 1.3):
            _box(g, (x + tx - 1.0, gy, -5.0), (x + tx + 1.0, gy + 1.6, -3.2), 'stone', 0.56, bevel=0.5)
        g.crystals((x + s * 2.4, -8.4, -1.4), (s * 0.6, 0.6, -0.4), n=2, size=1.8, r=0.6, mat='crystal', seed=50 + s)
    _strata(g, seed=7, period=3.0, wave=0.2, groove=0.0)


def geode_brute(look, name, part, ctx):
    _ramps(ctx, {'stone': GB_STONE, 'rind': GB_RIND, 'crystal': GB_CRYSTAL, 'core': GB_CORE, 'eye': GB_CORE,
                 'glow': GB_CORE, 'spec': SPECTRUM})
    fn = {'torso': _gb_torso, 'geode': _gb_geode, 'head': _gb_head, 'arm_left': _gb_arm, 'arm_right': _gb_arm,
          'legs': _gb_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 1.1, 'geode': 0.6, 'head': 0.65, 'arm_left': 0.9, 'arm_right': 0.9,
                  'legs': 0.9}.get(name, 0.9))
    fn(g, ctx)
    return g


# ───────────────────────────── resonance_tuner (공명 조율자) ─────────────────────────────
# The crystal priest who tuned the caves: a violet hooded robe over a white tabard edged in gold, a glowing
# chest gem and a column of glowing glyphs, crystal pauldrons and a fan of shards standing behind the neck;
# the skirt breaks into hanging crystal shards over floating fragments (no feet).  A faceted crystal mask
# with slit eyes and a third-eye gem under the hood, a tuning-fork crown; in the right hand a tall gold
# tuning-fork staff cradling a glowing crystal; a gold sun-wheel of crystal shards orbits the waist.

RT_CLOTH = [(12, 7, 24), (24, 14, 46), (40, 24, 74), (60, 38, 106), (84, 56, 140), (112, 80, 176), (146, 112, 208)]
RT_SILK = [(64, 60, 84), (112, 108, 140), (162, 158, 192), (204, 202, 228), (234, 232, 248), (250, 250, 255)]
RT_GOLD = [(44, 30, 12), (94, 66, 26), (150, 112, 46), (202, 162, 80), (236, 206, 132), (252, 238, 196)]
RT_CRYSTAL = [(36, 22, 72), (66, 46, 128), (104, 84, 186), (146, 128, 232), (186, 170, 252), (218, 208, 255),
              (244, 240, 255)]
RT_GLOW = [(104, 62, 204), (152, 112, 242), (198, 172, 255), (230, 218, 255), (248, 244, 255), (255, 255, 255)]


def _rt_body(g: MobGrid, ctx):
    g.blob((0, 4.2, 0.2), (3.8, 3.8, 2.6), 'cloth', 0.5, top=0.12)                        # chest
    g.blob((0, 6.4, 0.2), (4.6, 1.6, 2.6), 'cloth', 0.55)                                 # shoulders
    _robe(g, 2.4, -5.4, 3.5, 5.2, 'cloth', 0.44, folds=8, amp=0.1, zs=0.72, hem=0.8, power=0.9)

    # white tabard down the front with a gold border, glowing glyph column, chest gem
    def tabard(x, y, z, n, m, v):
        if z > -0.8 or n[2] >= 0 or y > 6.6:
            return None
        ax = abs(x)
        if ax < 0.45 and -4.0 < y < 2.6 and int(round(y / g.vs)) % 3:
            return ('rune', 0.35 + 0.1 * math.sin(y), True)
        if ax < 1.5:
            return ('silk', 0.6 + 0.05 * y / 6)
        if ax < 2.0:
            return ('brass', 0.6)
        return None
    g.paint(tabard, ['cloth'])
    g.blob((0, 4.5, -2.9), (0.95, 1.2, 0.6), 'core', 0.6, glow=True, prio=6)
    g.ring((0, 4.5, -2.7), 1.25, 0.3, axis='z', mat='brass', val=0.7, prio=5)
    _ering(g, (0, 1.9, 0.2), 3.75, 2.75, 0.42, 'brass', 0.55)                                # gold sash
    # hem breaking into hanging crystal shards; a few floating fragments below
    for k in range(9):
        a = TAU * (k + 0.5) / 9
        ca, sa = math.cos(a), math.sin(a)
        L = 3.2 + 3.6 * h2(k, 1, 7) + (1.6 if k % 3 == 0 else 0)
        _shard(g, (ca * 4.4, -4.8, sa * 3.2), (ca * 0.22, -1, sa * 0.18), L, 0.78, 'crystal', tip=0.6)
    for p, r in (((0.6, -12.2, -0.6), 0.6), ((-1.8, -11.0, 1.0), 0.5), ((2.0, -10.6, 1.4), 0.45)):
        _bipyr(g, p, r, -0.3, 0.3, 0.9, 1.1, 'crystal', rot=p[0])
    # crystal pauldrons
    for s in (-1, 1):
        g.crystals((s * 4.2, 6.6, 0.2), (s * 0.75, 1, 0.0), n=2, size=3.0, r=0.85, mat='crystal', spread=0.6,
                   seed=60 + s)


def _rt_head(g: MobGrid, ctx):
    g.blob((0, 0.6, 0.5), (3.4, 3.9, 3.4), 'cloth', 0.5, top=0.15)
    g.carve_blob((0, -0.4, -3.0), (2.4, 2.8, 2.2))
    g.blob((0, -0.4, -1.3), (2.4, 2.9, 1.6), 'void', 0.2, prio=0, top=0.0)
    # gold trim on the hood's front rim
    g.paint(lambda x, y, z, n, m, v: ('brass', 0.62) if z < -2.0 else None, ['cloth'])
    g.blob((0, -2.3, 1.7), (2.8, 1.9, 2.0), 'cloth', 0.42)                               # drape behind the neck
    # faceted crystal mask: slit eyes, a third-eye gem
    g.blob((0, -0.6, -1.7), (1.9, 2.4, 1.15), 'crystal', 0.7, prio=2,
           vfn=lambda x, y, z, d: 0.72 + (0.12 if x > 0 else -0.06) - 0.15 * d)
    for s in (-1, 1):
        _box(g, (s * 0.4, -0.35, -3.0), (s * 1.35, 0.0, -2.55), 'eye', 0.62, glow=True, prio=6)
    g.blob((0, 1.0, -2.75), 0.42, 'core', 0.8, glow=True, prio=6)
    g.capsule((0, -2.0, -2.6), (0, -2.9, -2.3), 0.3, 0.3, 'crystal', 0.5, prio=6)          # chin ridge


def _rt_fork(g: MobGrid, ctx):
    g.cylinder((0, -3.6, 0.2), (0, -1.8, 0.2), 0.55, 0.45, 'brass', 0.5)
    g.ring((0, 0.0, 0.0), 1.9, 0.45, axis='z', mat='brass', val=0.58, arc=(0.5, 1.0))
    for s in (-1, 1):
        _box(g, (s * 1.9 - 0.42, 0.0, -0.42), (s * 1.9 + 0.42, 4.2, 0.42), 'brass', 0.62)
        g.blob((s * 1.9, 4.3, 0.0), 0.5, 'brass', 0.8)
        g.ring((s * 2.6, 3.6, 0.0), 1.1, 0.22, axis='z', mat='rune', val=0.6, glow=True,
               arc=((0.88, 1.12) if s > 0 else (0.38, 0.62)), prio=4)
    _bipyr(g, (0, 2.0, 0), 0.75, -0.3, 0.3, 1.3, 1.1, 'core', glow=True, prio=5)
    # a radiant halo of crystal rays standing behind the head (it turns with the head)
    c = (0, -5.2, 4.3)
    g.ring(c, 4.6, 0.32, axis='z', mat='brass', val=0.62, arc=(0.0, 0.5))
    for ang in (8, 34, 58, 122, 146, 172):
        a = math.radians(ang)
        d = (math.cos(a), math.sin(a), 0.1)
        _shard(g, vadd(c, (math.cos(a) * 4.3, math.sin(a) * 4.3, 0)), d, 4.4 - 1.2 * (ang in (8, 172)), 0.55,
               'crystal', tip=0.6, val=0.12)


def _rt_arm(g: MobGrid, ctx):
    right = ctx.name == 'arm_right'
    g.blob((0, -0.5, 0.0), (1.6, 1.3, 1.6), 'brass', 0.55)                                # gold shoulder cap
    g.capsule((0, -0.8, 0.0), (0, -5.6, 0.0), 1.3, 1.3, 'cloth', 0.5)
    g.cylinder((0, -5.2, 0.0), (0, -8.6, -0.2), 1.35, 2.0, 'cloth', 0.46, hollow=1.2)      # bell sleeve
    g.ring((0, -8.4, -0.2), 1.95, 0.32, axis='y', mat='brass', val=0.62)
    g.blob((0, -9.4, -0.4), (0.8, 1.0, 0.7), 'crystal', 0.6)                              # crystal hand
    if right:
        for k, x in enumerate((-0.5, 0.0, 0.5)):                                           # curled round the staff
            g.capsule((x, -10.0, -0.8), (x, -10.6, -2.0), 0.3, 0.26, 'crystal', 0.66)
        g.capsule((0.7, -9.4, -1.0), (0.4, -10.0, -2.4), 0.3, 0.26, 'crystal', 0.7)
    else:
        for k, x in enumerate((-0.5, 0.0, 0.5)):
            g.capsule((x, -10.0, -0.6), (x * 1.3, -11.6, -1.0 - 0.2 * k), 0.28, 0.22, 'crystal', 0.66)
        g.blob((0, -12.2, -1.4), 0.45, 'glow', 0.7, glow=True, prio=5)                    # mote between fingers


def _rt_staff(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    z0 = hz - 2.3
    top = hy + 13.0
    bot = -22.6
    g.cylinder((hx, bot + 1.8, z0), (hx, top, z0), 0.42, 0.42, 'brass', 0.5)
    for y in (hy - 8.0, hy - 3.0, hy + 4.5, hy + 9.0):
        g.blob((hx, y, z0), (0.7, 0.45, 0.7), 'crystal', 0.65, prio=3)
    g.cylinder((hx, hy - 1.5, z0), (hx, hy + 1.5, z0), 0.55, 0.55, 'cloth', 0.45, prio=2)   # grip wrap
    _shard(g, (hx, bot + 2.0, z0), (0, -1, 0), 2.2, 0.55, 'crystal', tip=0.7)            # crystal ferrule
    # tuning-fork head with a glowing crystal floating between the prongs
    g.blob((hx, top, z0), (0.8, 0.6, 0.8), 'brass', 0.6)
    g.ring((hx, top + 1.7, z0), 1.7, 0.42, axis='z', mat='brass', val=0.6, arc=(0.5, 1.0))
    for s in (-1, 1):
        _box(g, (hx + s * 1.7 - 0.4, top + 1.7, z0 - 0.4), (hx + s * 1.7 + 0.4, top + 6.6, z0 + 0.4), 'brass', 0.62)
        g.blob((hx + s * 1.7, top + 6.8, z0), 0.48, 'brass', 0.82)
    _bipyr(g, (hx, top + 4.0, z0), 0.85, -0.5, 0.5, 1.6, 1.3, 'core', glow=True, prio=5)
    for s in (-1, 1):
        g.ring((hx + s * 2.6, top + 5.4, z0), 1.2, 0.22, axis='z', mat='rune', val=0.6, glow=True,
               arc=((0.88, 1.12) if s > 0 else (0.38, 0.62)), prio=4)


def _rt_halo(g: MobGrid, ctx):
    R = 8.6
    g.ring((0, 0, 0), R, 0.42, axis='y', mat='brass', val=0.58)
    for k in range(8):
        a = TAU * k / 8
        ca, sa = math.cos(a), math.sin(a)
        _shard(g, (ca * (R - 0.2), 0.0, sa * (R - 0.2)), (ca, 0.22, sa), 2.6, 0.62, 'crystal')
        b = a + math.pi / 8
        g.dot((math.cos(b) * R, 0.45, math.sin(b) * R), 'rune', 0.7, glow=True, prio=6)
    _glint(g, ['crystal'], 4)


def resonance_tuner(look, name, part, ctx):
    _ramps(ctx, {'cloth': RT_CLOTH, 'silk': RT_SILK, 'brass': RT_GOLD, 'crystal': RT_CRYSTAL, 'core': RT_GLOW,
                 'eye': RT_GLOW, 'rune': RT_GLOW, 'glow': RT_GLOW, 'spec': SPECTRUM})
    fn = {'body': _rt_body, 'head': _rt_head, 'fork': _rt_fork, 'arm_left': _rt_arm, 'arm_right': _rt_arm,
          'staff': _rt_staff, 'halo': _rt_halo}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.55, 'head': 0.42, 'fork': 0.4, 'arm_left': 0.4, 'arm_right': 0.4, 'staff': 0.42,
                  'halo': 0.45}.get(name, 0.45))
    fn(g, ctx)
    return g


# ═════════════════════════════ FLOOR 8 · 망각의 서고 ═════════════════════════════

# ───────────────────────────── ink_wraith (먹물 원령) ─────────────────────────────
# Erased names pooled into a ghost: a hooded cloak of wet ink, glossy runs streaking down its folds, the
# hem torn into dripping tendrils; scraps of the pages it was written on cling to it and faint letters of
# lost names glow on its chest.  The hood holds only darkness, two hollow pale eyes weeping light; long
# ragged sleeves end in thin ink hands whose fingers are pen nibs.

IW_INK = [(3, 3, 8), (8, 10, 22), (14, 19, 38), (22, 30, 58), (34, 46, 86), (52, 70, 122), (80, 104, 160),
          (124, 150, 200)]
IW_PAPER = [(84, 72, 52), (136, 120, 90), (186, 170, 136), (220, 208, 176), (240, 232, 210)]
IW_EYE = [(120, 104, 60), (200, 186, 130), (240, 230, 186), (252, 248, 224), (255, 255, 246), (255, 255, 255)]
IW_RUNE = [(60, 90, 150), (110, 150, 214), (170, 204, 246), (214, 232, 255), (240, 248, 255)]
IW_NIB = [(36, 28, 14), (78, 62, 30), (130, 106, 56), (178, 152, 92), (214, 194, 136), (240, 228, 186)]


def _iw_body(g: MobGrid, ctx):
    g.blob((0, 6.2, 0.3), (3.6, 2.2, 2.8), 'ink', 0.5, top=0.2)                          # narrow shoulders

    def cloak(x, y, z, t, fold):
        v = 0.5 + 0.16 * fold * (0.4 + 0.6 * t) - 0.06 * t
        if t > 0.78:
            v += 0.22 * (t - 0.78) / 0.22                                               # thinning, see-through hem
        return v
    _robe(g, 7.0, -3.4, 3.4, 6.6, 'ink', folds=7, amp=0.2, zs=0.74, hem=3.6, power=1.5, vfn=cloak)
    # below the torn cloak the wraith has no legs: its ink pours down into a twisting, thinning tail
    tail = [(0, -1.0, 0.4), (0.9, -5.0, 1.0), (-0.8, -8.6, 0.6), (0.4, -11.4, -0.6), (1.8, -12.8, -2.0),
            (2.6, -12.6, -3.4)]
    g.sweep(tail, 3.3, 0.35, 'ink', vfn=lambda t, d, p: 0.42 + 0.14 * (1 - d) + 0.3 * t * t)
    for k, (pts, r0) in enumerate((([(-2.0, -3.0, 0.0), (-3.2, -6.2, 0.6), (-3.0, -8.4, 1.8), (-3.8, -9.6, 2.6)], 0.9),
                                   ([(2.2, -3.4, 1.2), (3.4, -6.0, 2.2), (3.0, -7.6, 3.4)], 0.8),
                                   ([(0.4, -3.6, -2.4), (1.0, -6.4, -3.2), (0.2, -8.0, -4.0)], 0.7))):
        g.sweep(pts, r0, 0.3, 'ink', vfn=lambda t, d, p: 0.48 + 0.12 * (1 - d) + 0.3 * t)   # trailing wisps
    # a wide torn mantle over the shoulders that covers the arm roots (arms hang from beneath it)
    g.blob((0, 6.6, 0.4), (6.0, 1.5, 3.4), 'ink', 0.56, top=0.25)
    pts = [(math.cos(a) * 6.2, 6.0, 0.4 + math.sin(a) * 3.6) for a in [math.pi + TAU * q / 26 for q in range(27)]]
    g.cloth(pts[:14], lambda u: 2.6 + 1.8 * abs(math.cos(u * math.pi)), 'ink', 0.6, tatter=0.45, normal=(0, 0, -1),
            thick=1, seed=1, holes=0.0)
    g.cloth(pts[13:], 4.6, 'ink', 0.56, tatter=0.5, normal=(0, 0, 1), thick=1, seed=2, holes=0.0)
    # glossy runs down the folds
    g.streaks('ink', ['ink'], density=0.07, length=(3.0, 7.0), val=0.85, val_end=0.6)
    # faint glowing letters of erased names drifting over the chest
    g.runes((0, -0.6, -6.0), (0, 0, -1), w=9.6, h=9.6, mat='rune', val=0.4, density=0.6, seed=3, depth=6.0)
    # page scraps stuck to the cloak, written on
    for c, n, (w, h) in (((-2.4, -2.6, 0), (0, 0, -1), (2.4, 3.0)), ((2.8, 2.4, 0), (0, 0, -1), (1.8, 2.2)),
                         ((0, -4.4, 0), (1, 0, 0), (2.6, 2.6)), ((0, 0.6, 0), (-1, 0, 0), (2.0, 2.4))):
        p = g.hit(vadd(c, vmul(n, 9.0)), vmul(n, -1), 14.0)
        if p is None:
            continue
        fa = max(range(3), key=lambda a: abs(n[a]))
        lo, hi = list(p), list(p)
        for a in range(3):
            if a == fa:
                lo[a] = hi[a] = p[a] + n[a] * g.vs
            elif a == 1:
                lo[a], hi[a] = p[a] - h / 2, p[a] + h / 2
            else:
                lo[a], hi[a] = p[a] - w / 2, p[a] + w / 2
        _box(g, lo, hi, 'paper', 0.6, prio=4)
    for f in ((0, 0, -1), (1, 0, 0), (-1, 0, 0)):
        _scribble(g, ['paper'], f, period=2, gap=0.3, mat='ink', val=0.2, word=4)
    # ink dripping from the hem's lowest points into long drops
    for k, (x, z, L) in enumerate(((-5.2, -1.8, 2.0), (2.2, -4.6, 2.6), (5.6, 1.0, 1.8), (-1.6, 4.4, 2.2))):
        p = g.hit((x, -14.0, z), (0, 1, 0), 12.0)
        if p:
            _drip(g, p, L, 0.4, 'ink', 0.6)


def _iw_head(g: MobGrid, ctx):
    g.blob((0, 0.6, 0.6), (3.9, 4.3, 3.9), 'ink', 0.5, top=0.18)
    g.cone((0, 3.4, 1.6), (0, 1, 0.55), 4.2, 2.1, 'ink', 0.48, 0.6, curl=(0, -1.2, 2.6))     # tall hood point
    g.carve_blob((0, -0.8, -3.7), (2.7, 3.2, 2.7))
    g.blob((0, -0.6, -1.2), (2.8, 3.4, 2.0), 'void', 0.1, prio=0, top=0.0)
    g.paint(lambda x, y, z, n, m, v: v + 0.26 if z < -2.5 else None, ['ink'])                # folded rim catches light
    for s in (-1, 1):
        g.eye((s * 1.15, 0.1, -2.3), 0.7, val=0.6, facing=(0, 0, -1))
        for k in range(1, 5):
            g.dot((s * 1.15, -0.3 - k * 0.5, -2.4), 'eye', 0.5 - 0.09 * k, glow=True, prio=6)  # weeping light
    for k, (x, L) in enumerate(((-2.3, 2.6), (-0.9, 1.5), (0.8, 2.2), (2.2, 1.3))):
        p = g.hit((x, -7.0, -3.2), (0, 1, 0), 8.0)
        if p:
            _drip(g, p, L, 0.34, 'ink', 0.62)
    g.streaks('ink', ['ink'], density=0.12, length=(1.0, 3.0), val=0.85, val_end=0.55, seed=4)


def _iw_arm(g: MobGrid, ctx):
    # the sleeve leans in from the shoulder seam (the pivot sits outside the narrow shoulders), flares into
    # a long ragged bell; a bony ink hand with pen-nib claws reaches out of it
    i = -ctx.out
    g.capsule((i * 0.6, -0.6, 0.2), (i * 0.2, -4.0, 0.1), 1.05, 1.3, 'ink', 0.52)
    g.cylinder((i * 0.2, -3.6, 0.1), (0, -6.8, 0.2), 1.35, 2.1, 'ink', 0.5, hollow=1.1)
    cuff = [(math.cos(a) * 2.05, -6.6, 0.2 + math.sin(a) * 2.05) for a in [TAU * q / 14 for q in range(15)]]
    g.cloth(cuff, 3.0, 'ink', 0.62, tatter=0.75, normal=(0, 0, -1), seed=3)
    g.capsule((0, -6.0, -0.2), (0, -8.4, -0.4), 0.55, 0.5, 'ink', 0.36)                      # wrist
    g.blob((0, -8.9, -0.5), (0.85, 0.85, 0.75), 'ink', 0.4)
    for k, x in enumerate((-0.55, 0.0, 0.55)):
        A = (x, -9.4, -0.8)
        B = (x * 1.5, -11.0, -1.7)
        C = (x * 1.6, -12.3, -1.3)
        g.limb([A, B, C], [0.28, 0.24, 0.2], 'ink', 0.42, knob=1.25)
        g.cone(C, (0, -1, 0.2), 1.1, 0.32, 'nib', 0.5, 0.88)                               # pen-nib finger tip
    g.limb([(0.8 * ctx.out, -8.7, -0.8), (1.2 * ctx.out, -10.0, -1.6)], [0.26, 0.22], 'ink', 0.42)
    _drip(g, (0.0, -13.2, -1.1), 1.0, 0.25, 'ink', 0.6)


def ink_wraith(look, name, part, ctx):
    _ramps(ctx, {'ink': IW_INK, 'paper': IW_PAPER, 'eye': IW_EYE, 'rune': IW_RUNE, 'nib': IW_NIB})
    fn = {'body': _iw_body, 'head': _iw_head, 'arm_left': _iw_arm, 'arm_right': _iw_arm}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'body': 0.8, 'head': 0.5, 'arm_left': 0.5, 'arm_right': 0.5}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── page_swarm (흩날리는 책장 떼) ─────────────────────────────
# A whirlwind of torn-out pages: at its heart a small open book whose pages flutter up, letters of gold
# light lifting off them and a red ribbon trailing; around it a vortex of curling pages covered in
# handwriting, and on the outer orbit blood-edged paper blades and three folded paper cranes.

PG_PAPER = [(72, 58, 38), (122, 104, 74), (174, 154, 114), (212, 196, 158), (234, 224, 196), (250, 246, 230)]
PG_INK = [(34, 24, 18), (60, 44, 32), (86, 66, 48), (112, 90, 66)]                     # faded sepia ink
PG_COVER = [(24, 10, 8), (44, 18, 14), (70, 30, 22), (100, 46, 32), (130, 66, 44), (160, 92, 62)]
PG_GOLD = [(120, 80, 20), (200, 150, 50), (250, 210, 110), (255, 240, 190), (255, 252, 236), (255, 255, 255)]
PG_RIBBON = [(60, 6, 12), (110, 16, 26), (160, 32, 40), (200, 60, 62), (230, 100, 96)]
PG_BLOOD = [(56, 4, 8), (100, 12, 16), (150, 26, 28), (192, 50, 48)]
PG_BRASS = [(50, 32, 10), (100, 70, 24), (160, 116, 44), (212, 170, 78), (242, 214, 136)]


def _page_text(t, jt, col, rows, seed, gap=0.22):
    """vfn body for written pages: a margin round the edge, ink lines on every other row (words of 2–4
    voxels with single gaps, ragged line ends), a darker torn top row."""
    if jt == 0:
        return 0.44
    if jt == 1 or jt >= rows - 1 or t < 0.1 or t > 0.9:
        return 0.64 + 0.06 * t
    if jt % 2 == 1:
        line = jt // 2
        end = 0.62 + 0.3 * h2(line, 3, seed)
        c = col + int(h2(line, 1, seed) * 5)
        if t < end and c % 4 != 3 and h2(c // 4, line, seed) > gap:
            return ('ink', 0.22)
    return 0.68 + 0.06 * t


def _pg_core(g: MobGrid, ctx):
    # the heart of the swarm: a grimoire hanging open in the air, its boards bent back in a V, page blocks
    # with ruled fore-edges, a gilt clasp dangling, sheets fluttering up from the spine, a crown of gold
    # letters of light circling above it and a red ribbon trailing below
    for s in (-1, 1):
        for q in range(4):                                                           # boards rise to the edge
            x0, x1 = s * (0.3 + q * 1.0), s * (1.3 + q * 1.0)
            y = -1.3 + 0.25 * q
            _box(g, (x0, y, -4.6), (x1, y + 0.45, 4.6), 'leather', 0.42 + 0.03 * q)
        _box(g, (s * 0.4, -0.9, -4.1), (s * 3.6, 0.3, 4.1), 'paper', 0.62)                   # page blocks
        for z in (-4.6, 4.2):
            _box(g, (s * 3.6, -0.6, z), (s * 4.3, 0.4, z + 0.4), 'brass', 0.7, prio=3)          # gilt corners
    g.bands(['paper'], axis=1, period=0.9, width=0.45, amount=-0.1)
    g.capsule((0, -1.3, -4.6), (0, -1.3, 4.6), 0.6, 0.6, 'leather', 0.35)                    # spine
    _scribble(g, ['paper'], (0, 1, 0), period=2, gap=0.25, mat='ink', val=0.35, word=4)
    g.sweep([(-4.2, -0.2, -1.0), (-4.6, -1.4, -1.2), (-4.4, -2.4, -0.8)], 0.32, 0.3, 'brass', 0.62)   # clasp strap
    _box(g, (-4.9, -3.2, -1.4), (-3.9, -2.4, -0.4), 'brass', 0.7, prio=4)
    # fluttering sheets rising from the spine and curling over
    for k, (ang, curl) in enumerate(((1.0, 0.45), (1.9, 0.4))):
        pts = []
        for q in range(7):
            t = q / 6
            a = ang + curl * t
            L = 3.4 * t
            pts.append((math.cos(a) * L, 0.3 + math.sin(a) * L, 0))
        z0 = -3.0 + 0.6 * k

        def vfn(t, z, k=k):
            row = int(round(z / g.vs))
            if 0.25 < t < 0.85 and row % 2 == 0 and h2(int(t * 6), row, k) > 0.3:
                return ('ink', 0.35)
            return 0.66 + 0.12 * t
        _sheet_xy(g, pts, z0, -z0, 'paper', vfn=vfn)
    for q in range(10):                                                              # crown of letters of light
        a = TAU * q / 10
        g.dot((math.cos(a) * 3.2, 5.2 + 0.4 * math.sin(a * 3), math.sin(a) * 3.2), 'glow', 0.55 + 0.3 * (q % 2),
              glow=True, prio=6)
    g.sweep([(0.2, -1.6, 4.4), (0.6, -3.0, 5.2), (-0.2, -4.6, 4.8), (0.4, -6.0, 5.4)], 0.45, 0.45, 'ribbon', 0.5,
            sq=(1.0, 1.0, 0.45))
    # the binding spell that keeps the swarm together: a glowing gold circle of script under the book
    g.ring((0, -2.4, 0), 5.0, 0.25, axis='y', mat='glow', val=0.45, glow=True, prio=4)
    g.ring((0, -2.4, 0), 3.9, 0.22, axis='y', mat='glow', val=0.3, glow=True, prio=4)
    for q in range(12):
        a = TAU * (q + 0.5) / 12
        g.dot((math.cos(a) * 4.45, -2.4, math.sin(a) * 4.45), 'glow', 0.75, glow=True, prio=5)


def _page(g, c, w, h, normal, text=True, curl=0, seed=0, prio=2, tone=0.0, initial=False):
    """One written page as a crisp axis-aligned sheet centred at c: w along its width axis, h along its height
    axis.  normal 'x' / 'z' = standing page (height = y), 'y' = page lying flat (height = z).  A margin, ink
    lines on every other row (2–4 voxel words, ragged ends), a torn darker top edge; curl > 0 lifts the far
    end of a flat page / bends the top of a standing one by that many voxels."""
    vs = g.vs
    wa = {'x': 2, 'z': 0, 'y': 0}[normal]                 # width axis
    ha = 1 if normal != 'y' else 2                        # height axis
    na = {'x': 0, 'z': 2, 'y': 1}[normal]
    nw, nh = int(round(w / vs)), int(round(h / vs))
    base = [int(round(c[a] / vs)) for a in range(3)]
    for i in range(nw):
        for j in range(nh):
            jt = nh - 1 - j                               # rows from the top edge
            if jt == 0 and h2(i, 1, seed) < 0.35:
                continue                                  # torn top edge
            v = 0.58 + 0.1 * (i / nw) + tone
            if i == 0 or i == nw - 1 or jt == nh - 1:
                v -= 0.14                                 # aged, darker border
            if (i == nw - 1 or i == nw - 2) and jt >= nh - 2 - int(3 * h2(seed, 5, 1)):
                v = ('burn', 0.3 + 0.3 * h2(i, j, seed))   # scorched corner
            if jt == 0:
                v = 0.42 + tone
            elif text and 1 < jt < nh - 1 and 0 < i < nw - 1 and jt % 2 == 0:
                line = jt // 2
                cc = i + int(h2(line, 1, seed) * 5)
                if i < nw * (0.6 + 0.35 * h2(line, 3, seed)) and cc % 4 != 3 and h2(cc // 4, line, seed) > 0.2:
                    v = None
            key = [0, 0, 0]
            key[wa] = base[wa] + i - nw // 2
            key[ha] = base[ha] + j - nh // 2
            lift = 0
            if curl:
                f = (j / nh) if normal == 'y' else (i / nw)
                lift = int(curl * max(0.0, f - 0.6) / 0.4 + 0.5) if f > 0.6 else 0
            key[na] = base[na] + lift
            if initial and 1 <= i <= 2 and 2 <= jt <= 3:
                g.put(key[0], key[1], key[2], 'glow', 0.55, True, prio + 1)     # illuminated gold initial
            elif v is None:
                g.put(key[0], key[1], key[2], 'ink', 0.45, False, prio + 1)
            elif isinstance(v, tuple):
                g.put(key[0], key[1], key[2], v[0], v[1], False, prio + 1)
            else:
                g.put(key[0], key[1], key[2], 'paper', v, False, prio)


def _pg_pages(g: MobGrid, ctx):
    # a rising spiral of loose pages: standing pages where the whirl runs along an axis (crisp sheets), flat
    # pages with curling ends between them, each a step higher
    R = 7.2
    for k in range(8):
        a = TAU * k / 8
        y = -3.0 + 0.8 * k
        if k % 2 == 0 and k != 6:                         # (no standing sheet right in front of the book)
            normal = 'x' if k % 4 == 0 else 'z'
            c = (math.cos(a) * R, y, math.sin(a) * R)
            _page(g, c, 4.2, 4.6, normal, text=k != 6, curl=1, seed=40 + k, tone=(-0.12, 0.06, 0.0, -0.06)[k // 2],
                  initial=k == 2)
        else:
            c = (math.cos(a) * (R - 0.6), y, math.sin(a) * (R - 0.6))
            _page(g, c, 3.8, 4.6, 'y', text=True, curl=2, seed=40 + k, tone=(0.04, -0.1, 0.08, -0.04)[k // 2 % 4],
                  initial=k == 5)


def _crane(g, c, fwd, s=1.0):
    """Folded paper crane at c flying along fwd: diamond body, raised triangular wings, neck + head, tail."""
    f = vnorm(fwd)
    up = (0, 1, 0)
    side = vnorm(vcross(up, f))

    def P(a, b, cc):
        return vadd(c, vadd(vmul(f, a * s), vadd(vmul(side, b * s), vmul(up, cc * s))))
    g.capsule(P(-1.0, 0, 0), P(0.9, 0, 0), 0.45 * s, 0.4 * s, 'paper', 0.66, prio=3)
    for sd in (-1, 1):
        _tri(g, P(0.6, 0, 0.2), P(-0.8, 0, 0.2), P(-0.2, sd * 2.7, 1.5), 'paper', vfn=lambda u, v: 0.58 + 0.25 * v)
    g.cone(P(0.8, 0, 0.1), vadd(f, (0, 1.3, 0)), 1.9 * s, 0.32 * s, 'paper', 0.62, 0.8, prio=3)
    g.cone(P(1.5, 0, 1.6), vadd(f, (0, -0.7, 0)), 0.7 * s, 0.3 * s, 'paper', 0.7, 0.85, prio=4)
    g.cone(P(-0.9, 0, 0.1), vadd(vmul(f, -1), (0, 1.0, 0)), 1.9 * s, 0.32 * s, 'paper', 0.6, 0.78, prio=3)


def _pg_outer(g: MobGrid, ctx):
    # paper blades: narrow strips with blood-stained edges
    for k in range(3):
        a0 = TAU * k / 3 + 1.2
        R = 11.2 + 1.2 * h2(k, 1, 9)
        yc = -0.6 + 1.2 * h2(k, 2, 9)
        span = (2.4 + 1.0 * h2(k, 3, 9)) / R

        def vfn(t, y, jt, col):
            if t > 0.8:
                return ('blood', 0.55 - 0.25 * (t - 0.8) / 0.2)
            return 0.62 + 0.08 * t - (0.12 if jt == 0 else 0)
        _vsheet(g, R, a0, a0 + span, lambda t, yc=yc: yc - 0.9 + 0.8 * t, lambda t, yc=yc: yc + 0.9 + 0.3 * t,
                'paper', vfn=vfn)
    # three folded paper cranes riding the orbit (flying tangentially)
    for k in range(3):
        a = TAU * k / 3 + 0.15
        c = (math.cos(a) * 11.6, 0.4 * (k - 1), math.sin(a) * 11.6)
        _crane(g, c, (-math.sin(a), 0.0, math.cos(a)), 1.25)


def page_swarm(look, name, part, ctx):
    _ramps(ctx, {'paper': PG_PAPER, 'ink': PG_INK, 'leather': PG_COVER, 'glow': PG_GOLD, 'ribbon': PG_RIBBON,
                 'blood': PG_BLOOD, 'brass': PG_BRASS,
                 'burn': [(20, 12, 8), (48, 30, 18), (84, 56, 32), (118, 84, 50)]})
    fn = {'core': _pg_core, 'pages': _pg_pages, 'pages_outer': _pg_outer}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'core': 0.45, 'pages': 0.5, 'pages_outer': 0.5}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── biting_tome (물어뜯는 고서) ─────────────────────────────
# An oxblood grimoire that waits on the floor like any book — until it grins: gilt corner caps, a tooled
# gold frame and raised spine bands, two slit amber eyes bulging out of the cover under scowling leather
# brows, a gold clasp like a lip ring; a row of ivory fangs pokes out all round the fore-edge, the
# pages part into a dark red maw with a ribbon-bookmark tongue, and it scuttles on four leather legs with
# brass knuckles and ivory claws.

BT_LEATHER = [(16, 5, 5), (32, 10, 9), (52, 18, 14), (76, 28, 20), (104, 42, 28), (136, 60, 38), (170, 86, 56)]
BT_GOLD = [(54, 32, 10), (104, 70, 22), (162, 116, 42), (214, 170, 76), (244, 214, 132), (255, 244, 200)]
BT_PAPER = [(96, 78, 52), (150, 130, 96), (198, 182, 146), (228, 218, 190), (246, 240, 222)]
BT_MOUTH = [(10, 2, 4), (34, 6, 10), (66, 14, 20), (104, 28, 34), (140, 48, 52)]
BT_TONGUE = [(60, 10, 20), (110, 24, 38), (160, 48, 60), (200, 84, 92), (230, 130, 136)]
BT_EYE = [(130, 70, 10), (220, 140, 30), (255, 200, 80), (255, 236, 160), (255, 252, 230), (255, 255, 255)]
BT_TOOTH = [(110, 96, 70), (170, 158, 126), (214, 206, 178), (238, 234, 214), (252, 250, 240)]

BT_W, BT_D = 5.7, 6.7          # page block half width / front z of the fore-edge


def _rim_points(step=1.15, back=4.6):
    """Points (x, z) along the fore-edge U (front + both sides) of the page block."""
    pts = []
    n = int(2 * BT_W / step)
    for q in range(n + 1):
        pts.append((-BT_W + 2 * BT_W * q / n, -BT_D))
    for s in (-1, 1):
        m = int((back + BT_D) / step)
        for q in range(1, m + 1):
            pts.append((s * BT_W, -BT_D + (back + BT_D) * q / m))
    return pts


def _fang_pos(x, z, y, out=0.4):
    """A fang root just outside the fore-edge at rim point (x, z)."""
    if abs(z + BT_D) < 1e-6:
        return (x, y, z - out)
    return (x + math.copysign(out, x), y, z)


def _gilt_corner(g, x, z, y0, y1, sx, sz, size=1.8):
    _box(g, (x - sx * size, y0, z - sz * 0.5), (x + sx * 0.25, y1, z + sz * 0.25), 'brass', 0.62, prio=4)
    _box(g, (x - sx * 0.5, y0, z - sz * size), (x + sx * 0.25, y1, z + sz * 0.25), 'brass', 0.62, prio=4)
    g.dot((x - sx * 0.7, y1 + g.vs * 0.5, z - sz * 0.7), 'brass', 0.9, prio=5)


def _bt_bottom(g: MobGrid, ctx):
    _box(g, (-6.3, -1.6, -7.3), (6.3, -0.8, 7.0), 'leather', 0.45, bevel=0.3)
    _box(g, (-BT_W, -0.8, -BT_D + 0.1), (BT_W, 1.5, 6.0), 'paper', 0.62)
    g.bands(['paper'], axis=1, period=1.0, width=0.5, amount=-0.1)
    g.carve_blob((0, 1.7, -1.4), (4.2, 1.4, 4.6))
    g.blob((0, 1.6, -1.4), (4.4, 1.6, 4.8), 'mouth', 0.3, prio=0, top=0.0, cut=lambda x, y, z: y > 1.5)
    _box(g, (-BT_W, 1.0, -BT_D + 0.1), (BT_W, 1.5, 4.4), 'mouth', 0.25, prio=2)            # dark lip of the seam
    g.sweep([(0, 0.9, 1.6), (0.3, 1.2, -2.6), (0.0, 1.4, -6.4), (-0.3, 0.5, -7.5), (0.2, -0.9, -7.9)], 0.95, 0.6,
            'flesh', 0.5, sq=(1.0, 0.45, 1.0),
            vfn=lambda t, d, p: 0.45 + 0.15 * t - (0.18 if abs(p[0]) < 0.3 and d > 0.5 else 0.0))   # ribbon tongue
    for k, (x, z) in enumerate(_rim_points()):
        if k % 2:
            continue
        L = 1.6 + 0.5 * h2(k, 2, 4)
        g.cone(_fang_pos(x, z, 0.5), (0, 1, 0), L, 0.45, 'tooth', 0.5, 0.92, prio=4)
    g.capsule((-6.0, -0.4, 6.6), (6.0, -0.4, 6.6), 1.2, 1.2, 'leather', 0.5)              # spine (lower)
    for sx in (-1, 1):
        _gilt_corner(g, sx * 6.3, -7.3, -1.7, -0.7, sx, -1)


def _bt_top(g: MobGrid, ctx):
    zc = -6.4
    _box(g, (-6.3, 0.8, zc - 7.2), (6.3, 1.7, zc + 6.8), 'leather', 0.5, bevel=0.35)
    _box(g, (-BT_W, -1.6, zc - BT_D + 0.1), (BT_W, 0.8, zc + 6.0), 'paper', 0.62)
    g.bands(['paper'], axis=1, period=1.0, width=0.5, amount=-0.1)
    g.carve_blob((0, -1.8, zc - 1.4), (4.2, 1.3, 4.6))
    g.blob((0, -1.7, zc - 1.4), (4.4, 1.5, 4.8), 'mouth', 0.3, prio=0, top=0.0, cut=lambda x, y, z: y < -1.6)
    _box(g, (-BT_W, -1.6, zc - BT_D + 0.1), (BT_W, -1.1, zc + 4.4), 'mouth', 0.25, prio=2)  # upper lip
    # spine at the hinge with raised gold bands
    g.capsule((-6.0, 0.6, 0.2), (6.0, 0.6, 0.2), 1.4, 1.4, 'leather', 0.52)
    for x in (-3.6, -1.2, 1.2, 3.6):
        g.ring((x, 0.6, 0.2), 1.45, 0.32, axis='x', mat='brass', val=0.62, arc=(0.0, 0.5))
    # tooled gold frame on the cover
    for (lo, hi) in (((-5.2, 1.7, zc - 6.2), (5.2, 1.9, zc - 5.8)), ((-5.2, 1.7, zc + 5.0), (5.2, 1.9, zc + 5.4)),
                     ((-5.2, 1.7, zc - 6.2), (-4.8, 1.9, zc + 5.4)), ((4.8, 1.7, zc - 6.2), (5.2, 1.9, zc + 5.4))):
        _box(g, lo, hi, 'brass', 0.58, prio=3)
    for sx in (-1, 1):
        for sz, z in ((-1, zc - 7.2), (1, zc + 6.8)):
            _gilt_corner(g, sx * 6.3, z, 0.7, 1.9, sx, sz)
    # bulging slit eyes under scowling leather brows
    for s in (-1, 1):
        g.eye((s * 2.3, 1.75, zc - 2.6), 0.95, val=0.45, facing=(0, 0.6, -1), slit=True)
        g.capsule((s * 1.0, 2.6, zc - 1.8), (s * 3.8, 2.4, zc - 2.7), 0.55, 0.45, 'leather', 0.66, prio=6)
    # gold sun-boss behind the eyes, gold clasp hanging over the fore-edge like a lip ring
    g.blob((0, 1.9, zc + 2.0), (1.6, 0.45, 1.6), 'brass', 0.6, prio=3)
    g.dot((0, 2.3, zc + 2.0), 'eye', 0.6, glow=True, prio=6)
    _box(g, (-1.0, -1.4, zc - 7.6), (1.0, 1.7, zc - 7.1), 'brass', 0.55, prio=4)
    g.dot((0, -0.6, zc - 7.7), 'mouth', 0.05, prio=6)


def _bt_teeth(g: MobGrid, ctx):
    for k, (x, z) in enumerate(_rim_points()):
        if k % 2 == 0:
            continue
        big = k in (1, 9, 11)
        L = (2.3 if big else 1.7) + 0.4 * h2(k, 3, 4)
        g.cone(_fang_pos(x, z, 0.4), (0, -1, 0), L, 0.52 if big else 0.45, 'tooth', 0.5, 0.92, prio=4)
    pts = [(x, 0.5, z) for (x, z) in _rim_points(0.6)]
    g.sweep(pts[: len(pts) // 3 + 1], 0.42, 0.42, 'mouth', 0.45, smooth=False)


def _bt_legs(g: MobGrid, ctx):
    gy = -1.6
    g.light_mul = 0.6
    for sx in (-1, 1):
        for sz in (-1, 1):
            R = (sx * 4.2, 0.3, sz * 4.6)
            K = (sx * 7.0, 1.7, sz * 6.2)
            F = (sx * 7.6, gy + 0.35, sz * 7.0)
            g.limb([R, K, F], [0.9, 0.72, 0.55], 'leather', 0.42, joint_mat='brass', joint_val=0.62, knob=1.25)
            for k in range(3):
                a = -0.7 + 0.7 * k
                d = (sx * (0.6 + 0.3 * math.cos(a)), -0.55, sz * 0.5 + math.sin(a) * 0.5)
                g.cone(F, d, 1.2, 0.36, 'tooth', 0.45, 0.85)


def biting_tome(look, name, part, ctx):
    _ramps(ctx, {'leather': BT_LEATHER, 'brass': BT_GOLD, 'paper': BT_PAPER, 'mouth': BT_MOUTH, 'flesh': BT_TONGUE,
                 'eye': BT_EYE, 'tooth': BT_TOOTH})
    fn = {'cover_bottom': _bt_bottom, 'cover_top': _bt_top, 'teeth': _bt_teeth, 'legs': _bt_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'cover_bottom': 0.5, 'cover_top': 0.5, 'teeth': 0.45, 'legs': 0.5}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── archive_sentinel (서고 감시자) ─────────────────────────────
# A walking bookcase: a walnut cabinet with three shelves of gold-banded book spines (one of them smouldering
# with ember runes), brass corner brackets and rivets, iron straps on its back and a candle stub burning on
# its crown; its head is a brass lantern whose ember shows through the panes as two eyes under an iron
# brow; wooden arms in brass bands end in riveted iron gauntlets, the right fist dragging a heavy chain
# with a hook; it stands on turned furniture legs with brass ball-and-claw feet.

AS_WOOD = [(14, 8, 5), (28, 16, 10), (46, 28, 16), (68, 42, 24), (92, 60, 34), (120, 80, 46), (152, 106, 64)]
AS_BRASS = [(40, 24, 8), (86, 56, 18), (138, 96, 36), (188, 142, 62), (228, 190, 108), (252, 232, 172)]
AS_IRON = [(12, 12, 14), (26, 26, 30), (44, 44, 50), (66, 66, 74), (94, 94, 102), (128, 128, 136), (168, 168, 176)]
AS_EMBER = [(120, 34, 6), (196, 76, 12), (244, 136, 32), (255, 192, 84), (255, 232, 160), (255, 252, 232)]
BOOKS = {
    'book_r': [(40, 8, 8), (80, 18, 16), (124, 32, 26), (160, 52, 40), (196, 80, 60)],
    'book_g': [(10, 26, 16), (20, 48, 30), (34, 74, 46), (54, 104, 66), (82, 136, 92)],
    'book_b': [(10, 14, 34), (20, 28, 62), (34, 46, 96), (54, 70, 130), (84, 102, 164)],
    'book_t': [(50, 36, 20), (90, 66, 38), (134, 102, 62), (176, 140, 90), (210, 178, 128)],
    'book_p': [(28, 12, 34), (52, 24, 62), (80, 40, 94), (110, 62, 126), (144, 92, 160)],
}


def _as_torso(g: MobGrid, ctx):
    W, H, D = 6.0, 6.5, 4.0
    _box(g, (-W, -H, -D), (W, H, D), 'wood', 0.42, bevel=0.4)
    _box(g, (-W - 0.6, H - 1.0, -D - 0.6), (W + 0.6, H + 0.3, D + 0.6), 'wood', 0.56, bevel=0.3)   # crown moulding
    _box(g, (-W - 0.4, -H, -D - 0.4), (W + 0.4, -H + 0.9, D + 0.4), 'wood', 0.34, bevel=0.3)       # plinth
    rows = ((1.6, 5.0), (-2.0, 1.0), (-5.2, -2.6))
    mats = list(BOOKS)
    for ri, (y0, y1) in enumerate(rows):
        g.carve(lambda x, y, z, y0=y0, y1=y1: abs(x) < W - 0.8 and y0 < y < y1 and z < -D + 2.6)
        _box(g, (-W + 0.8, y0, -D + 2.4), (W - 0.8, y1, -D + 2.8), 'wood', 0.12, prio=2)       # shadowed back
        x = -W + 0.9
        bi = 0
        while x < W - 1.2:
            w = 0.6 + 0.4 * int(h2(ri, bi, 11) * 3)
            if x + w > W - 0.8:
                break
            ht = (y1 - y0) * (0.68 + 0.3 * h2(ri, bi, 12))
            m = mats[int(h2(bi, ri, 13) * len(mats))]
            zf = -D + 0.3 + 0.5 * h2(bi, ri, 14)
            _box(g, (x, y0, zf), (x + w - 0.25, y0 + ht, -D + 2.4), m, 0.5, prio=3)
            for yb in (y0 + 0.5, y0 + ht - 0.6):
                _box(g, (x, yb, zf - 0.05), (x + w - 0.25, yb + 0.25, zf), 'brass', 0.6, prio=4)
            if ri == 1 and bi == 4:                                                            # smouldering book
                for yy in (y0 + 1.1, y0 + 1.6, y0 + 2.1):
                    g.dot((x + w / 2 - 0.1, yy, zf - 0.1), 'lava', 0.6, glow=True, prio=5)
            x += w
            bi += 1
    # brass corner brackets with rivets on the front, vertical stiles
    for sx in (-1, 1):
        _box(g, (sx * W - sx * 0.9, -H + 0.9, -D - 0.25), (sx * W + sx * 0.1, H - 1.0, -D + 0.2), 'wood', 0.6, prio=3)
        for sy in (-1, 1):
            y = sy * (H - 1.6)
            _box(g, (sx * W - sx * 2.0, y - 0.9, -D - 0.45), (sx * W + sx * 0.15, y + 0.9, -D - 0.1), 'brass', 0.55,
                   prio=4)
            g.rivets([(sx * W - sx * 0.5, y, -D - 0.6), (sx * W - sx * 1.5, y, -D - 0.6)], 'brass', 0.85)
    # iron straps on the back
    for y in (-2.8, 2.6):
        _box(g, (-W - 0.15, y - 0.5, D - 0.3), (W + 0.15, y + 0.5, D + 0.3), 'iron', 0.45, prio=3)
        g.rivets([(x, y, D + 0.5) for x in (-4.4, -1.5, 1.5, 4.4)], 'iron', 0.8)
    # a candle stub burning on the crown, a loose page sticking out of the top shelf
    g.cylinder((-4.4, H + 0.3, -1.6), (-4.4, H + 2.0, -1.6), 0.6, 0.55, 'wax', 0.7)
    g.blob((-4.4, H + 2.7, -1.6), (0.35, 0.7, 0.35), 'lava', 0.8, glow=True, prio=5)
    _box(g, (1.6, 4.6, -D - 0.2), (2.7, 5.9, -D + 0.6), 'paper', 0.65, prio=4)


def _as_head(g: MobGrid, ctx):
    _box(g, (-3.6, -4.4, -3.6), (3.6, -3.2, 3.6), 'brass', 0.45, bevel=0.4)
    for sx in (-1, 1):
        for sz in (-1, 1):
            _box(g, (sx * 3.1 - 0.5, -3.2, sz * 3.1 - 0.5), (sx * 3.1 + 0.5, 2.3, sz * 3.1 + 0.5), 'iron', 0.5, prio=3)

    # ember-lit panes: brightest round the flame; two hotter eyes on the front pane
    def pane(x, y, z):
        d = math.sqrt(x * x + (y + 0.6) ** 2 + z * z)
        v = 0.55 - 0.08 * d
        if z < -2.4 and abs(abs(x) - 1.25) < 0.55 and abs(y + 0.2) < 0.55:
            v = 0.95
        return ('lava', v, True)
    _box(g, (-2.7, -3.2, -2.7), (2.7, 2.3, 2.7), 'lava', vfn=pane, prio=1)
    # iron grille: brow bar, nose bar, side bars, mouth bar
    _box(g, (-3.0, 0.7, -3.0), (3.0, 1.2, -2.6), 'iron', 0.55, prio=4)
    _box(g, (-0.25, -3.2, -3.0), (0.25, 0.7, -2.6), 'iron', 0.5, prio=4)
    for sx in (-1, 1):
        _box(g, (sx * 2.7, -3.2, -0.25), (sx * 3.0, 2.3, 0.25), 'iron', 0.5, prio=4)
    _box(g, (-0.25, -3.2, 2.6), (0.25, 2.3, 3.0), 'iron', 0.5, prio=4)
    _box(g, (-3.0, -2.0, -3.0), (3.0, -1.6, -2.6), 'iron', 0.45, prio=4)
    # stepped brass roof, finial and ring handle
    _box(g, (-3.9, 2.3, -3.9), (3.9, 3.0, 3.9), 'brass', 0.5, bevel=0.3)
    _box(g, (-2.8, 3.0, -2.8), (2.8, 3.7, 2.8), 'brass', 0.56, bevel=0.3)
    _box(g, (-1.6, 3.7, -1.6), (1.6, 4.3, 1.6), 'brass', 0.62, bevel=0.3)
    g.ring((0, 5.3, 0), 0.9, 0.3, axis='z', mat='iron', val=0.55)
    g.rivets([(x, 2.65, -4.0) for x in (-3.0, -1.0, 1.0, 3.0)], 'brass', 0.85)


def _as_arm(g: MobGrid, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    g.blob((o * 0.4, -0.3, 0.0), (2.9, 2.1, 2.9), 'brass', 0.5, cut=lambda x, y, z: y < -1.5)    # pauldron
    g.rivets([(o * 0.4 + 2.2 * math.cos(a), -1.0, 2.2 * math.sin(a)) for a in (0.6, 2.0, 3.6, 5.0)], 'brass', 0.85)
    g.capsule((0, -1.4, 0.0), (0, -6.0, 0.0), 1.7, 1.6, 'wood', 0.46)
    for y in (-2.8, -4.8):
        g.ring((0, y, 0), 1.72, 0.32, axis='y', mat='brass', val=0.6)
    g.blob((0, -6.4, 0.0), 1.6, 'iron', 0.52)
    _box(g, (-2.0, -10.4, -2.0), (2.0, -6.9, 2.0), 'iron', 0.45, bevel=0.6)                  # gauntlet
    g.rivets([(x, y, -2.1) for x in (-1.2, 1.2) for y in (-7.6, -9.6)], 'brass', 0.85)
    _box(g, (-1.6, -12.2, -1.5), (1.6, -10.4, 1.5), 'iron', 0.5, bevel=0.4)                  # hand
    if right:
        _box(g, (-1.7, -13.0, -1.9), (1.7, -11.6, -0.4), 'iron', 0.42, bevel=0.5)            # closed fist
        g.blob((o * 1.5, -11.4, -1.4), (0.6, 0.8, 0.6), 'iron', 0.55)
    else:
        for x in (-1.0, 0.0, 1.0):
            g.limb([(x, -12.0, -1.0), (x, -13.2, -1.8), (x, -13.8, -1.2)], [0.42, 0.38, 0.32], 'iron', 0.5,
                   knob=1.2)
        g.limb([(o * 1.6, -11.2, -1.0), (o * 1.9, -12.6, -1.8)], [0.42, 0.36], 'iron', 0.5)


def _as_chain(g: MobGrid, ctx):
    hx, hy, hz = ctx.hand
    pts = [(hx, hy - 0.8, hz - 1.2), (hx + 0.4, hy - 4.6, hz - 0.6), (hx + 0.2, hy - 8.4, hz + 1.0),
           (hx, -22.3, hz + 3.6), (hx - 0.4, -22.5, hz + 7.0), (hx + 0.4, -22.4, hz + 10.0)]
    g.chain(pts, link=1.3, mat='iron', val=0.5)
    end = pts[-1]
    g.ring(vadd(end, (0, 0, 0.9)), 0.8, 0.32, axis='x', mat='iron', val=0.6)
    g.horn(vadd(end, (0, 0, 1.6)), (0, 0.3, 1), 3.2, 0.62, curl=(0, 2.4, -1.6), mat='iron', val=0.42,
           tip_mat='blade')


def _as_legs(g: MobGrid, ctx):
    gy = -12.0
    _box(g, (-5.2, -2.0, -2.6), (5.2, 0.6, 2.6), 'wood', 0.42, bevel=0.5)
    _box(g, (-5.3, -2.0, -2.7), (5.3, -1.5, 2.7), 'brass', 0.55, prio=2)
    profile = ((-1.8, -3.0, 1.9, 'wood', 0.5), (-3.0, -5.4, 1.35, 'wood', 0.44), (-5.4, -6.5, 1.85, 'brass', 0.56),
               (-6.5, -8.6, 1.3, 'wood', 0.44), (-8.6, -9.5, 1.6, 'brass', 0.58))
    for s in (-1, 1):
        x = s * 2.8
        for (y0, y1, r, m, v) in profile:
            g.cylinder((x, y0, 0.0), (x, y1, 0.0), r, r * 0.92, m, v)
        g.blob((x, gy + 1.2, -0.3), 1.25, 'brass', 0.5)                                   # ball
        for k, dx in enumerate((-0.85, 0.0, 0.85)):
            g.horn((x + dx, -9.4, -0.6), (dx * 0.25, -0.45, -1), 2.0, 0.5, curl=(0, -1.6, 0.6), mat='brass', val=0.5)


def archive_sentinel(look, name, part, ctx):
    tab = {'wood': AS_WOOD, 'brass': AS_BRASS, 'iron': AS_IRON, 'lava': AS_EMBER, 'eye': AS_EMBER,
           'wax': [(120, 104, 80), (176, 160, 130), (222, 210, 182), (244, 238, 220)],
           'paper': [(120, 104, 74), (176, 160, 124), (220, 206, 170), (240, 232, 208)]}
    tab.update(BOOKS)
    _ramps(ctx, tab)
    fn = {'torso': _as_torso, 'head': _as_head, 'arm_left': _as_arm, 'arm_right': _as_arm, 'chain': _as_chain,
          'legs': _as_legs}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'torso': 0.5, 'head': 0.45, 'arm_left': 0.5, 'arm_right': 0.5, 'chain': 0.5,
                  'legs': 0.55}.get(name, 0.5))
    fn(g, ctx)
    return g


# ───────────────────────────── forbidden_keeper (금서의 수호자) ─────────────────────────────
# Keeper of the sealed books: a tall plum-black robe with gold-embroidered edges, open down the front on an
# inner robe where a column of forbidden script glows; a gold-trimmed capelet, a belt hung with paper seal
# talismans and keys, a hem dissolving into pooled, dripping ink, a gold eye-sigil on the back.  The deep
# pointed hood hides a face behind a hanging seal talisman — only two violet eyes show.  Gaunt grey hands
# in shackles; a chained grimoire with a glowing eye and a padlock floats before it; two chains hung with
# seals and padlocks circle it.

FK_ROBE = [(8, 5, 12), (16, 10, 24), (28, 17, 40), (42, 26, 58), (60, 38, 80), (82, 54, 106), (110, 76, 136),
           (146, 108, 170)]
FK_DARK = [(4, 3, 6), (10, 7, 14), (18, 12, 24), (28, 20, 36), (40, 30, 50)]
FK_GOLD = [(48, 30, 10), (98, 66, 22), (156, 112, 42), (208, 164, 74), (240, 210, 128), (255, 242, 196)]
FK_IRON = [(12, 12, 16), (28, 28, 36), (50, 50, 60), (78, 78, 90), (110, 110, 122), (150, 150, 162), (196, 196, 206)]
FK_PAPER = [(110, 96, 70), (164, 148, 114), (208, 194, 160), (234, 226, 200), (250, 246, 232)]
FK_SEAL = [(70, 8, 12), (130, 20, 26), (186, 40, 40), (224, 82, 70)]
FK_CURSE = [(70, 20, 110), (124, 52, 190), (178, 104, 244), (216, 168, 255), (242, 224, 255), (255, 255, 255)]
FK_SKIN = [(30, 26, 34), (56, 50, 62), (86, 80, 94), (118, 112, 126), (152, 146, 160), (186, 182, 194)]
FK_HIDE = [(10, 6, 14), (22, 14, 30), (38, 24, 50), (58, 38, 74), (82, 56, 100), (110, 80, 130)]


def _seal_strip(g, top, w=1.1, L=3.6, z_face=-1, seed=0):
    """Paper talisman hanging from `top` (centre of its top edge), facing ±Z, with red seal strokes."""
    x, y, z = top
    _box(g, (x - w / 2, y - L, z - 0.12), (x + w / 2, y, z + 0.12), 'paper', 0.62, prio=5)
    for k in range(3):
        yy = y - 0.8 - k * 1.0
        if h2(k, 1, seed) < 0.8:
            _box(g, (x - w / 2 + 0.25, yy - 0.15, z + z_face * 0.25), (x + w / 2 - 0.25, yy + 0.15, z + z_face * 0.2),
                   'seal', 0.55, prio=6)
    g.dot((x, y - L + 0.5, z + z_face * 0.25), 'seal', 0.7, prio=6)


def _fk_robe(g: MobGrid, ctx):
    g.blob((0, 7.4, 0.3), (5.6, 2.6, 3.6), 'cloth', 0.5, top=0.2)                         # shoulders
    _robe(g, 8.2, -14.6, 4.9, 7.0, 'cloth', 0.42, folds=9, amp=0.08, zs=0.72, hem=0.9, power=1.2)

    # open front: dark inner robe with a glowing column of forbidden script, gold edges; ink-soaked hem
    def front(x, y, z, n, m, v):
        if y < -12.2:
            return ('ink', 0.35 + 0.25 * (y + 15) / 3)
        if z > -1.0 or n[2] >= 0 or y > 6.8:
            return None
        ax = abs(x) + 0.12 * (6.8 - y) * 0.15
        if ax < 0.55 and int(round(y / g.vs)) % 3 and y < 5.5:
            return ('rune', 0.3 + 0.08 * math.sin(y * 1.3), True)
        if ax < 1.7:
            return ('dark', 0.35)
        if ax < 2.3:
            return ('brass', 0.6)
        return None
    g.paint(front, ['cloth'])
    # capelet with a gold hem line
    cap = [(math.cos(a) * 6.0, 5.4, 0.3 + math.sin(a) * 4.2) for a in [math.pi + TAU * q / 28 for q in range(29)]]
    g.cloth(cap[:15], 2.4, 'cloth', 0.54, tatter=0.0, normal=(0, 0, -1), thick=1, seed=1)
    g.cloth(cap[14:], 3.2, 'cloth', 0.5, tatter=0.0, normal=(0, 0, 1), thick=1, seed=2)
    g.cloth([(p[0], p[1] - 2.2, p[2]) for p in cap[:15]], 0.5, 'brass', 0.62, tatter=0.0, normal=(0, 0, -1), seed=3,
            prio=3)
    g.cloth([(p[0], p[1] - 3.0, p[2]) for p in cap[14:]], 0.5, 'brass', 0.58, tatter=0.0, normal=(0, 0, 1), seed=4,
            prio=3)
    # belt, talismans, keys
    _ering(g, (0, 0.4, 0.2), 5.6, 4.1, 0.5, 'brass', 0.5, n=40)
    _box(g, (-0.9, -0.5, -4.4), (0.9, 1.3, -3.8), 'brass', 0.7, prio=5)
    g.dot((0, 0.4, -4.5), 'rune', 0.7, glow=True, prio=6)
    for x, L, sd in ((-3.4, 4.2, 1), (2.8, 3.4, 2)):
        p = g.hit((x, -0.4, -9), (0, 0, 1), 14)
        if p:
            _seal_strip(g, (p[0], 0.0, p[2] - 0.35), 1.1, L, -1, sd)
    p = g.hit((4.6, -1.0, -9), (0, 0, 1), 14)
    if p:
        g.ring((p[0], -1.6, p[2] - 0.3), 0.6, 0.18, axis='z', mat='brass', val=0.7, prio=5)
        for k, dx in enumerate((-0.4, 0.3)):
            g.capsule((p[0] + dx, -2.0, p[2] - 0.4), (p[0] + dx * 1.6, -3.6, p[2] - 0.4), 0.2, 0.2, 'brass', 0.62,
                      prio=5)
            _box(g, (p[0] + dx * 1.6 - 0.3, -4.0, p[2] - 0.5), (p[0] + dx * 1.6 + 0.3, -3.5, p[2] - 0.3), 'brass',
                   0.7, prio=5)
    # ink drips under the hem
    for k, (x, z, L) in enumerate(((-5.0, -2.4, 1.6), (2.4, -4.8, 2.2), (6.0, 1.6, 1.4), (-2.0, 4.6, 2.0))):
        p = g.hit((x, -22.0, z), (0, 1, 0), 10.0)
        if p:
            _drip(g, p, L, 0.4, 'ink', 0.4)
    # gold eye-sigil on the back
    cy = -6.4
    circle = [(math.cos(TAU * q / 20) * 2.9, cy + math.sin(TAU * q / 20) * 2.9) for q in range(21)]
    eye = [(-2.0, cy), (-1.0, cy + 0.8), (0.0, cy + 1.0), (1.0, cy + 0.8), (2.0, cy), (1.0, cy - 0.8), (0.0, cy - 1.0),
           (-1.0, cy - 0.8), (-2.0, cy)]
    _strokes(g, (0, 0, 0), (0, 0, 1), [circle, eye], 'brass', 0.7, depth=10.0)
    for x in (0.0, 0.4, -0.4):
        q = g.hit((x, cy, 10.0), (0, 0, -1), 14)
        if q:
            g.dot(q, 'rune', 0.7, glow=True, prio=7)


def _fk_head(g: MobGrid, ctx):
    g.blob((0, 0.4, 0.6), (3.8, 4.2, 3.9), 'cloth', 0.5, top=0.18)
    g.cone((0, 3.2, 1.2), (0, 1, 0.55), 4.2, 2.2, 'cloth', 0.48, 0.56, curl=(0, -0.6, 2.0))     # tall hood point
    g.carve_blob((0, -0.6, -3.6), (2.6, 3.2, 2.5))
    g.blob((0, -0.5, -1.2), (2.7, 3.3, 2.0), 'void', 0.1, prio=0, top=0.0)
    g.paint(lambda x, y, z, n, m, v: ('brass', 0.62) if z < -2.5 else None, ['cloth'])        # gold hood rim
    for s in (-1, 1):
        _box(g, (s * 0.9, -0.1, -2.6), (s * 1.9, 0.35, -2.2), 'eye', 0.6, glow=True, prio=6)
        g.dot((s * 1.9, 0.5, -2.4), 'eye', 0.5, glow=True, prio=6)
    _seal_strip(g, (0, 2.0, -3.4), 1.1, 5.0, -1, 7)
    g.blob((0, 2.8, -3.9), (0.5, 0.5, 0.35), 'rune', 0.65, glow=True, prio=7)


def _fk_arm(g: MobGrid, ctx):
    o = ctx.out
    g.capsule((-o * 0.8, -0.2, 0.0), (0, -3.6, 0.0), 1.3, 1.5, 'cloth', 0.5)
    g.cylinder((0, -3.2, 0.0), (0, -8.8, -0.4), 1.5, 2.9, 'cloth', 0.46, hollow=1.4)          # bell sleeve
    g.ring((0, -8.5, -0.4), 2.85, 0.42, axis='y', mat='brass', val=0.6)
    g.blob((0, -9.6, -0.6), (1.0, 1.1, 0.9), 'skin', 0.5)
    for k, x in enumerate((-0.6, -0.2, 0.2, 0.6)):
        g.limb([(x, -10.3, -1.0), (x * 1.4, -11.8, -1.8), (x * 1.5, -12.9, -1.4)], [0.3, 0.26, 0.2], 'skin', 0.5,
               knob=1.3)
    g.limb([(o * 0.9, -9.6, -1.0), (o * 1.4, -10.8, -1.9)], [0.3, 0.24], 'skin', 0.5)
    g.ring((0, -9.0, -0.6), 1.25, 0.35, axis='y', mat='iron', val=0.5)                      # shackle
    g.chain([(o * 1.0, -9.2, 0.2), (o * 1.4, -10.4, 0.8), (o * 1.2, -11.8, 0.6)], 0.9, 'iron', 0.5)


def _fk_tome(g: MobGrid, ctx):
    for y0, y1 in ((-2.0, -1.3), (1.3, 2.0)):
        _box(g, (-5.0, y0, -6.0), (5.0, y1, 6.0), 'hide', 0.45, bevel=0.25)
    _box(g, (-4.6, -1.3, -5.6), (4.6, 1.3, 5.6), 'paper', 0.62)
    g.bands(['paper'], axis=1, period=0.9, width=0.45, amount=-0.12)
    g.capsule((-5.0, 0.0, -5.8), (-5.0, 0.0, 5.8), 2.0, 2.0, 'hide', 0.5)
    for z in (-3.6, 0.0, 3.6):
        g.ring((-5.0, 0.0, z), 2.05, 0.3, axis='z', mat='brass', val=0.62, arc=(0.25, 0.75))
    for sx in (-1, 1):
        for sz in (-1, 1):
            for y0, y1 in ((-2.1, -1.2), (1.2, 2.1)):
                _gilt_corner(g, sx * 5.0, sz * 6.0, y0, y1, sx, sz, 1.6)
    # glowing eye in a gold circle on the cover
    g.ring((0.4, 2.1, 0.0), 2.6, 0.3, axis='y', mat='brass', val=0.65)
    g.eye((0.4, 1.9, 0.0), 1.0, val=0.5, facing=(0, 1, -0.3), slit=True)
    # two crossing chains binding it, a padlock at the front
    pts_a = [(0.6, 2.3, -6.4), (0.6, 2.3, 6.4), (0.6, -2.3, 6.4), (0.6, -2.3, -6.4), (0.6, 2.3, -6.4)]
    pts_b = [(-5.6, 2.3, -1.6), (5.4, 2.3, -1.6), (5.4, -2.3, -1.6), (-5.6, -2.3, -1.6), (-5.6, 2.3, -1.6)]
    for pts in (pts_a, pts_b):
        path = []
        for a, b in zip(pts, pts[1:]):
            for q in range(8):
                t = q / 8
                path.append(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))
        g.chain(path + [pts[-1]], 1.15, 'iron', 0.52)
    _box(g, (-0.5, -1.4, -7.4), (1.7, 0.6, -6.6), 'brass', 0.55, bevel=0.2, prio=6)
    g.ring((0.6, 0.9, -7.0), 0.75, 0.25, axis='z', mat='iron', val=0.6, arc=(0.0, 0.5), prio=6)
    g.dot((0.6, -0.5, -7.5), 'void', 0.1, prio=7)
    for x, L in ((-2.6, 1.8), (1.8, 1.2), (3.8, 2.2)):
        _drip(g, (x, -2.2, -5.4), L, 0.32, 'ink', 0.4)


def _fk_chains(g: MobGrid, ctx):
    loop1 = [(math.cos(a) * 8.6, 2.4 * math.sin(a + 0.6), math.sin(a) * 8.6) for a in [TAU * q / 40 for q in range(41)]]
    loop2 = [(math.cos(a) * 8.0, -1.4 - 2.0 * math.sin(a - 1.2), math.sin(a) * 8.0) for a in
             [TAU * q / 40 for q in range(41)]]
    _chain_lite(g, loop1, 1.2, 'iron', 0.5)
    _chain_lite(g, loop2, 1.2, 'iron', 0.44)
    for k in range(4):
        a = TAU * k / 4 + 0.3
        top = (math.cos(a) * 8.6, 2.4 * math.sin(a + 0.6) - 0.6, math.sin(a) * 8.6)
        _seal_strip(g, top, 1.0, 3.0, -1, 20 + k)
    for k in range(2):
        a = TAU * k / 2 + 1.9
        p = (math.cos(a) * 8.0, -1.4 - 2.0 * math.sin(a - 1.2), math.sin(a) * 8.0)
        g.ring(vadd(p, (0, -0.8, 0)), 0.6, 0.22, axis='z', mat='iron', val=0.6, arc=(0.0, 0.5))
        _box(g, vadd(p, (-0.8, -2.6, -0.4)), vadd(p, (0.8, -1.0, 0.4)), 'brass', 0.55, bevel=0.2)


def forbidden_keeper(look, name, part, ctx):
    _ramps(ctx, {'cloth': FK_ROBE, 'dark': FK_DARK, 'brass': FK_GOLD, 'iron': FK_IRON, 'paper': FK_PAPER,
                 'seal': FK_SEAL, 'rune': FK_CURSE, 'eye': FK_CURSE, 'glow': FK_CURSE, 'skin': FK_SKIN,
                 'hide': FK_HIDE, 'ink': IW_INK})
    fn = {'robe': _fk_robe, 'head': _fk_head, 'arm_left': _fk_arm, 'arm_right': _fk_arm, 'tome': _fk_tome,
          'chains': _fk_chains}.get(name)
    if fn is None:
        return None
    g = ctx.grid({'robe': 0.8, 'head': 0.5, 'arm_left': 0.5, 'arm_right': 0.5, 'tome': 0.5,
                  'chains': 0.5}.get(name, 0.5))
    fn(g, ctx)
    return g


DESIGNS = {
    'shard_skitterer': shard_skitterer,
    'prism_sentinel': prism_sentinel,
    'echo_wisp': echo_wisp,
    'geode_brute': geode_brute,
    'resonance_tuner': resonance_tuner,
    'ink_wraith': ink_wraith,
    'page_swarm': page_swarm,
    'biting_tome': biting_tome,
    'archive_sentinel': archive_sentinel,
    'forbidden_keeper': forbidden_keeper,
}
