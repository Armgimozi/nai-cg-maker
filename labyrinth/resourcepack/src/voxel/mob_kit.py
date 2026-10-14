"""Creature voxel kit for mob / boss parts (all original code).

Designers (src/mobvox/*.py) paint one Grid per model part.  Unlike the item brushes in core.Grid
(voxel units), every MobGrid tool below takes **pixel units of the part** (16 = 1 block, the same
units as YAML `size`), origin = the part's pivot, front = model −Z, model −X = the mob's left.
The voxel size `vs` (px per voxel) is a property of the grid, so a design can be re-sampled finer or
coarser to fit the element budget without changing its numbers.

Value conventions: `val` 0..1 = position on the material's colour ramp (0 = darkest).  Many tools
accept `vfn` callbacks returning a value, `(mat, value)`, `(mat, value, glow)` or None (= skip voxel).
Glow materials (palette.MOB_GLOW_MATS: glow, eye, core, rune, lava) render emissive (alpha 252 rule)
and pulse on animated mob atlases.

Tool groups
  volumes   blob (lumpy ellipsoid) · rbox (bevelled box) · capsule · sweep (spline tube) · limb
            (tapered segments with knuckles) · cone · ring · slab2d (extruded outline)
  surface   exposed · paint · carve · carve_blob · mottle · gradient · bands · streaks · cracks · hit
  creature  eye · eyes · teeth · mouth · horn · spikes · plates (carapace) · scales · fur · moss · vine ·
            vine_wrap · branch (antlers / roots / coral) · mushroom · crystals · wing (bone + membrane) ·
            tentacle · cloth (tattered) · plate (+rivets) · rivets · gear · runes · chain · strands (web / hair)
            moss_paint · clumps · sprinkle (ferns / flowers / glow buds / hanging strands)
"""
from __future__ import annotations

import math
import random

from ..materials import rune_bit
from ..util import h2, h3
from .core import DIRS, Grid, bezier, catmull, resample

# ───────────────────────────── small vector helpers ─────────────────────────────


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vmul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vlen(a):
    return math.sqrt(vdot(a, a))


def vnorm(a):
    ln = vlen(a) or 1.0
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def frame_of(d):
    """Two unit vectors perpendicular to direction d (and to each other)."""
    d = vnorm(d)
    a = (0, 1, 0) if abs(d[1]) < 0.9 else (1, 0, 0)
    u = vnorm(vcross(d, a))
    w = vcross(d, u)
    return u, w


def mirror_pt(p):
    return (-p[0], p[1], p[2])


# ───────────────────────────── 3D noise ─────────────────────────────

def _sm(t):
    return t * t * (3 - 2 * t)


def noise3(x, y, z, seed=0):
    """Smooth value noise in [0,1) (trilinear, smoothstep)."""
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    xf, yf, zf = _sm(x - xi), _sm(y - yi), _sm(z - zi)

    def c(a, b, d):
        return h3(xi + a, yi + b, zi + d, seed)
    x00 = c(0, 0, 0) + (c(1, 0, 0) - c(0, 0, 0)) * xf
    x10 = c(0, 1, 0) + (c(1, 1, 0) - c(0, 1, 0)) * xf
    x01 = c(0, 0, 1) + (c(1, 0, 1) - c(0, 0, 1)) * xf
    x11 = c(0, 1, 1) + (c(1, 1, 1) - c(0, 1, 1)) * xf
    y0 = x00 + (x10 - x00) * yf
    y1 = x01 + (x11 - x01) * yf
    return y0 + (y1 - y0) * zf


def fbm3(x, y, z, seed=0, octaves=3):
    t, amp, f, norm = 0.0, 1.0, 1.0, 0.0
    for i in range(octaves):
        t += noise3(x * f, y * f, z * f, seed + i * 131) * amp
        norm += amp
        amp *= 0.5
        f *= 2.03
    return t / norm


# ───────────────────────────── grid ─────────────────────────────

class MobGrid(Grid):
    """Voxel grid in part pixel units.  Voxel (i, j, k) is centred at (i·vs, j·vs, k·vs) px."""

    def __init__(self, vs=0.5, seed=0):
        super().__init__(seed)
        self.vs = float(vs)
        self.ramp_over = {}          # material → custom colour ramp for this part only
        self.light_mul = 1.0         # baked light strength (thin limbs: 0.5–0.7 saves elements)

    # ── coordinates ──
    def to_vox(self, p):
        return (p[0] / self.vs, p[1] / self.vs, p[2] / self.vs)

    def px(self, key):
        return (key[0] * self.vs, key[1] * self.vs, key[2] * self.vs)

    def key(self, p):
        return (int(round(p[0] / self.vs)), int(round(p[1] / self.vs)), int(round(p[2] / self.vs)))

    def _range(self, lo, hi):
        vs = self.vs
        return range(math.floor(lo / vs), math.ceil(hi / vs) + 1)

    def _emit(self, key, res, mat, glow, prio):
        """Write a vfn result: value | (mat, value) | (mat, value, glow) | None."""
        if res is None:
            return
        if isinstance(res, tuple):
            if len(res) == 3:
                mat, res, glow = res
            else:
                mat, res = res
            if res is None:
                return
        self.put(key[0], key[1], key[2], mat, res, glow, prio)

    def dot(self, p, mat, val=0.5, glow=False, prio=3):
        k = self.key(p)
        self.put(k[0], k[1], k[2], mat, val, glow, prio)

    def set_ramp(self, mat, colours):
        """Custom colour ramp (dark → light, any length ≥ 2) for a material in this part."""
        self.ramp_over[mat] = [tuple(int(c) for c in col[:3]) for col in colours]

    # ── volumes ──
    def blob(self, c, r, mat, val=0.5, vfn=None, glow=False, prio=1, lump=0.0, lump_scale=3.0, cut=None, top=0.12,
             seed=0):
        """Ellipsoid (r = radius or (rx, ry, rz) px).  lump 0..0.4 displaces the outline with 3D noise
        (organic rocks, moss clumps).  cut(x, y, z) → True skips a voxel.  Default value: val + top·(height
        within the blob) so forms read lighter on top.  vfn(x, y, z, d) with d = normalised radius."""
        rx, ry, rz = (r, r, r) if not isinstance(r, (tuple, list)) else r
        ext = 1.0 + lump
        sd = self.seed + 17 + seed
        for i in self._range(c[0] - rx * ext, c[0] + rx * ext):
            x = i * self.vs
            dx = (x - c[0]) / max(rx, 1e-6)
            for j in self._range(c[1] - ry * ext, c[1] + ry * ext):
                y = j * self.vs
                dy = (y - c[1]) / max(ry, 1e-6)
                for k in self._range(c[2] - rz * ext, c[2] + rz * ext):
                    z = k * self.vs
                    dz = (z - c[2]) / max(rz, 1e-6)
                    d = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if lump:
                        d -= lump * (fbm3(x / lump_scale, y / lump_scale, z / lump_scale, sd) - 0.5) * 2.4
                    if d > 1.0:
                        continue
                    if cut and cut(x, y, z):
                        continue
                    res = vfn(x, y, z, max(0.0, d)) if vfn else val + top * dy
                    self._emit((i, j, k), res, mat, glow, prio)

    def rbox(self, lo, hi, mat, val=0.5, bevel=0.0, vfn=None, glow=False, prio=1, top=0.0):
        """Box from lo to hi (px, inclusive) with rounded/bevelled edges of radius `bevel`."""
        c = tuple((lo[a] + hi[a]) / 2 for a in range(3))
        half = tuple(abs(hi[a] - lo[a]) / 2 for a in range(3))
        b = min(bevel, *half) if bevel else 0.0
        for i in self._range(min(lo[0], hi[0]), max(lo[0], hi[0])):
            x = i * self.vs
            for j in self._range(min(lo[1], hi[1]), max(lo[1], hi[1])):
                y = j * self.vs
                for k in self._range(min(lo[2], hi[2]), max(lo[2], hi[2])):
                    z = k * self.vs
                    q = [abs(p - cc) - (hh - b) for p, cc, hh in zip((x, y, z), c, half)]
                    if any(qq > b + 1e-6 for qq in q):
                        continue
                    if b:
                        out = math.sqrt(sum(max(qq, 0.0) ** 2 for qq in q))
                        if out > b + 1e-6:
                            continue
                    if vfn:
                        res = vfn(x, y, z)
                    else:
                        res = val + (top * (y - c[1]) / max(half[1], 1e-6) if top else 0.0)
                    self._emit((i, j, k), res, mat, glow, prio)

    def sweep(self, pts, r0, r1=None, mat='skin', val=0.5, vfn=None, glow=False, prio=1, sq=(1.0, 1.0, 1.0),
              smooth=True, rfn=None):
        """Tube through px points (Catmull-Rom when smooth and ≥3 points); radius r0 → r1 (or rfn(t)).
        vfn(t, d, (x, y, z)) with t 0..1 along the tube and d = normalised distance from its axis."""
        r1 = r0 if r1 is None else r1
        path = catmull(list(pts), 8) if (smooth and len(pts) >= 3) else list(pts)
        step = max(0.15, self.vs * 0.5)
        seen = {}
        vs = self.vs
        for p, t in resample(path, step):
            r = rfn(t) if rfn else r0 + (r1 - r0) * t
            rr = max(vs * 0.5, r)
            for i in self._range(p[0] - rr * sq[0], p[0] + rr * sq[0]):
                dx = (i * vs - p[0]) / sq[0]
                for j in self._range(p[1] - rr * sq[1], p[1] + rr * sq[1]):
                    dy = (j * vs - p[1]) / sq[1]
                    for k in self._range(p[2] - rr * sq[2], p[2] + rr * sq[2]):
                        dz = (k * vs - p[2]) / sq[2]
                        d = math.sqrt(dx * dx + dy * dy + dz * dz)
                        if d <= rr:
                            nd = d / rr
                            key = (i, j, k)
                            old = seen.get(key)
                            if old is None or nd < old[1]:
                                seen[key] = (t, nd)
        for key, (t, nd) in seen.items():
            res = vfn(t, nd, self.px(key)) if vfn else val
            self._emit(key, res, mat, glow, prio)
        return seen

    def capsule(self, a, b, ra, rb=None, mat='skin', val=0.5, vfn=None, glow=False, prio=1, sq=(1.0, 1.0, 1.0)):
        return self.sweep([a, b], ra, rb, mat, val, vfn, glow, prio, sq, smooth=False)

    def limb(self, joints, radii, mat='skin', val=0.5, joint_mat=None, knob=1.15, vfn=None, glow=False, prio=1,
             joint_val=None, smooth=False):
        """Tapered limb through joint points (px); radii per joint.  Inner joints get a knuckle bulge
        (radius·knob) in joint_mat.  vfn(t, d, p) with t along the whole limb."""
        n = len(joints) - 1
        for s in range(n):
            t0, t1 = s / n, (s + 1) / n
            f = None
            if vfn:
                f = (lambda t, d, p, t0=t0, t1=t1: vfn(t0 + (t1 - t0) * t, d, p))
            self.sweep([joints[s], joints[s + 1]], radii[s], radii[s + 1], mat, val, f, glow, prio, smooth=False)
        if knob:
            for s in range(1, n):
                self.blob(joints[s], radii[s] * knob, joint_mat or mat,
                          joint_val if joint_val is not None else val + 0.06, glow=glow, prio=prio + 1)

    def cone(self, base, direction, length, r, mat='horn', val=0.5, tip_val=None, curl=None, prio=2, glow=False,
             r_tip=None, vfn=None):
        """Tapered spike from base along direction; curl (px vector) bends the tip."""
        d = vnorm(direction)
        tip = vadd(base, vmul(d, length))
        if curl:
            mid = vadd(vadd(base, vmul(d, length * 0.55)), vmul(curl, 0.35))
            tip = vadd(tip, curl)
            pts = bezier(base, vadd(base, vmul(d, length * 0.3)), mid, tip, 10)
        else:
            pts = [base, tip]
        tv = val + 0.3 if tip_val is None else tip_val
        rt = self.vs * 0.45 if r_tip is None else r_tip
        f = vfn or (lambda t, dd, p: val + (tv - val) * t + 0.08 * (1 - dd))
        return self.sweep(pts, r, rt, mat, val, f, glow, prio, smooth=False)

    def ring(self, c, R, r, axis='y', mat='brass', val=0.6, glow=False, prio=2, arc=(0.0, 1.0), vfn=None):
        n = max(16, int(R * 6))
        pts = []
        for k in range(n + 1):
            a = 2 * math.pi * (arc[0] + (arc[1] - arc[0]) * k / n)
            ca, sa = math.cos(a) * R, math.sin(a) * R
            pts.append((c[0] + ca, c[1] + sa, c[2]) if axis == 'z' else
                       (c[0] + ca, c[1], c[2] + sa) if axis == 'y' else (c[0], c[1] + sa, c[2] + ca))
        return self.sweep(pts, r, r, mat, val, vfn, glow, prio, smooth=False)

    def slab2d(self, mask, lo, hi, plane='xy', depth=0.0, half=0.5, mat='iron', vfn=None, glow=False, prio=1,
               bevel=0.0):
        """Extrude a 2D outline.  mask(u, v) over px coords of the plane ('xy': u=x, v=y, extruded along z
        around `depth`; 'zy': u=z, v=y along x; 'xz': u=x, v=z along y).  half = half thickness px; bevel
        thins the slab toward its outline.  vfn(u, v, w, edge_dist_px)."""
        vs = self.vs
        cells = {}
        for a in self._range(lo[0], hi[0]):
            for b in self._range(lo[1], hi[1]):
                if mask(a * vs, b * vs):
                    cells[(a, b)] = True
        dist = {}
        frontier = []
        for (a, b) in cells:
            if any((a + da, b + db) not in cells for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                dist[(a, b)] = 0
                frontier.append((a, b))
        while frontier:
            nxt = []
            for (a, b) in frontier:
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (a + da, b + db)
                    if q in cells and q not in dist:
                        dist[q] = dist[(a, b)] + 1
                        nxt.append(q)
            frontier = nxt
        d0 = round(depth / vs)
        for (a, b), dd in dist.items():
            edge = dd * vs
            hh = half if not bevel else min(half, max(vs * 0.5, half * (0.35 + edge / max(bevel, 1e-6))))
            nh = int(round(hh / vs))
            for w in range(-nh, nh + 1):
                res = vfn(a * vs, b * vs, w * vs, edge) if vfn else 0.5
                key = (a, b, d0 + w) if plane == 'xy' else (d0 + w, b, a) if plane == 'zy' else (a, d0 + w, b)
                self._emit(key, res, mat, glow, prio)

    # ── surface operations ──
    def exposed(self, mats=None):
        """[(key, normal)] of voxels touching air (normal = sum of open directions)."""
        vox = self.vox
        out = []
        for key, v in vox.items():
            if mats and v[0] not in mats:
                continue
            i, j, k = key
            n = [0, 0, 0]
            open_ = False
            for d in DIRS:
                if (i + d[0], j + d[1], k + d[2]) not in vox:
                    n[0] += d[0]
                    n[1] += d[1]
                    n[2] += d[2]
                    open_ = True
            if open_:
                out.append((key, tuple(n)))
        return out

    def paint(self, fn, mats=None, exposed_only=True):
        """fn(x, y, z, normal, mat, val) → None (keep) | value | (mat, value) | (mat, value, glow)."""
        items = self.exposed(mats) if exposed_only else [(k, (0, 0, 0)) for k, v in self.vox.items()
                                                         if not mats or v[0] in mats]
        for key, n in items:
            cur = self.vox.get(key)
            if cur is None:
                continue
            res = fn(*self.px(key), n, cur[0], cur[1])
            if res is None:
                continue
            if isinstance(res, tuple):
                if len(res) == 3:
                    cur[0], cur[1], cur[2] = res
                else:
                    cur[0], cur[1] = res
            else:
                cur[1] = res

    def carve(self, fn):
        for key in list(self.vox):
            if fn(*self.px(key)):
                del self.vox[key]

    def carve_blob(self, c, r):
        rx, ry, rz = (r, r, r) if not isinstance(r, (tuple, list)) else r
        self.carve(lambda x, y, z: ((x - c[0]) / rx) ** 2 + ((y - c[1]) / ry) ** 2 + ((z - c[2]) / rz) ** 2 <= 1.0)

    def mottle(self, mats=None, amount=0.1, scale=4.0, seed=0, exposed_only=True):
        """Coherent value patches (merge-friendly, unlike per-voxel noise)."""
        sd = self.seed + 41 + seed
        self.paint(lambda x, y, z, n, m, v: v + amount * (fbm3(x / scale, y / scale, z / scale, sd) - 0.5) * 2.2,
                   mats, exposed_only)

    def gradient(self, axis=1, lo=-8.0, hi=8.0, amount=0.15, mats=None):
        """Darken toward lo / lighten toward hi along an axis (ambient fall-off, e.g. belly shadow)."""
        span = (hi - lo) or 1.0
        self.paint(lambda x, y, z, n, m, v: v + amount * (((x, y, z)[axis] - lo) / span - 0.5) * 2, mats, False)

    def bands(self, mats=None, axis=2, period=3.0, width=0.5, amount=-0.18, phase=0.0):
        """Periodic stripes (segment grooves / fur banding) along an axis."""
        def f(x, y, z, n, m, v):
            t = (((x, y, z)[axis] + phase) / period) % 1.0
            return v + amount if t < width / period else None
        self.paint(f, mats)

    def streaks(self, mat='rust', mats=None, density=0.2, length=(1.5, 5.0), val=0.4, val_end=None, seed=0,
                glow=False):
        """Drip streaks running down the side surfaces from random starts (rust water, ink, slime)."""
        sd = self.seed + 61 + seed
        side = {}
        for key, n in self.exposed(mats):
            if n[1] > 0 or (n[0] == 0 and n[2] == 0):
                continue
            side.setdefault((key[0], key[2]), []).append(key[1])
        ve = val - 0.12 if val_end is None else val_end
        for (i, k), js in side.items():
            if h2(i * 7 + k * 131, 3, sd) >= density:
                continue
            top = max(js)
            js_set = set(js)
            start = top - int(h2(i, k, sd + 1) * 0.5 * (top - min(js) + 1))
            L = (length[0] + (length[1] - length[0]) * h2(i, k, sd + 2)) / self.vs
            for j in range(start, int(start - L) - 1, -1):
                if j not in js_set:
                    continue
                t = (start - j) / max(1.0, L)
                self.put(i, j, k, mat, val + (ve - val) * t, glow, prio=self.vox[(i, j, k)][3])

    def cracks(self, mats=None, mat=None, width=0.05, scale=5.0, dv=-0.32, val=0.8, glow=False, seed=0):
        """Crack / vein lines where 3D noise crosses 0.5.  mat=None darkens; else sets mat (e.g. 'lava')."""
        sd = self.seed + 83 + seed

        def f(x, y, z, n, m, v):
            q = fbm3(x / scale, y / scale, z / scale, sd)
            if abs(q - 0.5) < width:
                return (mat, val, glow) if mat else v + dv
            return None
        self.paint(f, mats)

    def hit(self, origin, direction, max_dist=40.0):
        """First voxel (px centre) along a ray from origin (px) — to stick details onto a surface."""
        d = vnorm(direction)
        step = self.vs * 0.5
        t = 0.0
        while t <= max_dist:
            p = vadd(origin, vmul(d, t))
            k = self.key(p)
            if k in self.vox:
                return self.px(k)
            t += step
        return None

    # ── creature details ──
    def eye(self, c, r, mat='eye', val=0.72, socket=0.0, socket_mat='void', facing=(0, 0, -1), slit=False,
            pupil_mat=None, glow=True, prio=5, carve=True):
        """Glowing eye: bright front-centre, darker rim.  socket > 0 carves the surface around the eye and
        lines the hollow (behind / around the eye only) with socket_mat; slit adds a vertical dark pupil."""
        f = vnorm(facing)
        if socket:
            R = r + socket
            if carve:
                self.carve(lambda x, y, z: vlen(vsub((x, y, z), c)) <= R and vdot(vsub((x, y, z), c), f) > -r * 0.2)
            self.blob(c, R, socket_mat, 0.18, prio=prio - 1, top=0.0,
                      cut=lambda x, y, z: vdot(vsub((x, y, z), c), f) > -r * 0.35)
        self.blob(c, r, mat, prio=prio, glow=glow,
                  vfn=lambda x, y, z, d: val + 0.24 * max(0.0, vdot(vnorm(vsub((x, y, z), c)), f)) - 0.12 * d)
        if slit:
            pm = pupil_mat or 'void'
            for t in range(-int(r * 0.8 / self.vs), int(r * 0.8 / self.vs) + 1):
                p = vadd(vadd(c, vmul(f, r * 0.9)), (0, t * self.vs, 0))
                self.dot(p, pm, 0.1, glow=False, prio=prio + 1)

    def eyes(self, c, r, spacing, **kw):
        """A mirrored pair of eyes around x = 0 (c = the right-hand one, x > 0 or < 0)."""
        self.eye((abs(spacing) / 2, c[1], c[2]), r, **kw)
        self.eye((-abs(spacing) / 2, c[1], c[2]), r, **kw)

    def teeth(self, a, b, n, length, r=0.45, mat='tooth', direction=(0, -1, 0), val=0.6, jitter=0.25, prio=4,
              seed=0):
        for k in range(n):
            t = (k + 0.5) / n
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
            L = length * (1 - jitter * h2(k, 5, self.seed + seed))
            self.cone(p, direction, L, r, mat, val - 0.1, val + 0.3, prio=prio)

    def mouth(self, c, w, h, depth=1.5, mat='mouth', teeth=True, tooth_len=None, facing_z=-1):
        """Carve a mouth slot (front at c, opening toward −Z) and line it with teeth."""
        self.carve(lambda x, y, z: abs(x - c[0]) <= w / 2 and abs(y - c[1]) <= h / 2 and
                   (z - c[2]) * -facing_z >= -depth and (z - c[2]) * -facing_z <= 3)
        self.rbox((c[0] - w / 2, c[1] - h / 2, c[2] - facing_z * depth), (c[0] + w / 2, c[1] + h / 2,
                  c[2] - facing_z * (depth + self.vs)), mat, 0.2, prio=3)
        if teeth:
            L = tooth_len or h * 0.45
            n = max(2, int(w / 1.2))
            z = c[2] - facing_z * (depth * 0.4)
            self.teeth((c[0] - w / 2 + 0.3, c[1] + h / 2, z), (c[0] + w / 2 - 0.3, c[1] + h / 2, z), n, L,
                       r=min(0.6, w / n * 0.4), direction=(0, -1, 0))
            self.teeth((c[0] - w / 2 + 0.6, c[1] - h / 2, z), (c[0] + w / 2 - 0.6, c[1] - h / 2, z), max(2, n - 1),
                       L * 0.8, r=min(0.55, w / n * 0.36), direction=(0, 1, 0), seed=3)

    def horn(self, base, direction, length, r0, curl=(0, 0, 0), mat='horn', val=0.4, rings=0.0, tip_mat=None,
             prio=3, r_tip=None):
        """Curved horn: bezier from base along direction, tip bent by curl; rings = groove spacing (px)."""
        d = vnorm(direction)
        p3 = vadd(vadd(base, vmul(d, length)), curl)
        p1 = vadd(base, vmul(d, length * 0.4))
        p2 = vadd(vadd(base, vmul(d, length * 0.75)), vmul(curl, 0.55))
        pts = bezier(base, p1, p2, p3, 14)
        total = length

        def f(t, dd, p):
            v = val + 0.35 * t + 0.08 * (1 - dd)
            if rings and t < 0.8 and int(t * total / rings) % 2 == 0 and dd > 0.6:
                v -= 0.14
            if tip_mat and t > 0.82:
                return (tip_mat, 0.45 + 0.4 * (t - 0.82) / 0.18)
            return v
        rt = self.vs * 0.45 if r_tip is None else r_tip
        return self.sweep(pts, r0, rt, mat, val, f, prio=prio, smooth=False)

    def spikes(self, pts, direction, length, r, mat='horn', val=0.45, tip_val=None, prio=3, curl=None,
               vary=0.25):
        """Row of spikes; direction = vector or fn(index, point) → vector; length/r scalars."""
        for n_, p in enumerate(pts):
            d = direction(n_, p) if callable(direction) else direction
            L = length * (1 - vary * h2(n_, 9, self.seed))
            self.cone(p, d, L, r, mat, val, tip_val, curl=curl, prio=prio)

    def plates(self, c, r, n=4, axis=2, mat='chitin', val=0.5, lift=0.12, groove=-0.24, ridge=0.0,
               ridge_mat=None, cut=None, prio=1, lip=0.14, seed=0, reverse=False):
        """Carapace of n overlapping plates along an axis of an ellipsoid (c, r=(rx, ry, rz)).  Each
        plate swells toward its rear edge (lift), catches light on the lip and leaves a dark groove where
        the next plate starts.  ridge > 0 adds a raised spine along the top (+Y) centre line."""
        rx, ry, rz = r
        ra = (rx, ry, rz)[axis]
        lo = c[axis] - ra

        def seg(p):
            u = (p[axis] - lo) / (2 * ra)
            if reverse:
                u = 1 - u
            s = min(n - 1, max(0, int(u * n)))
            return s, u * n - s

        ext = 1 + lift
        for i in self._range(c[0] - rx * ext, c[0] + rx * ext):
            x = i * self.vs
            for j in self._range(c[1] - ry * ext, c[1] + ry * ext):
                y = j * self.vs
                for k in self._range(c[2] - rz * ext, c[2] + rz * ext):
                    z = k * self.vs
                    p = (x, y, z)
                    s, t = seg(p)
                    sw = 1 + lift * t
                    dx, dy, dz = (x - c[0]) / (rx * sw), (y - c[1]) / (ry * sw), (z - c[2]) / (rz * (1 if axis == 2 else sw))
                    if axis == 0:
                        dx = (x - c[0]) / rx
                    elif axis == 1:
                        dy = (y - c[1]) / ry
                    d = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if d > 1.0:
                        continue
                    if cut and cut(x, y, z):
                        continue
                    v = val + lip * t + 0.1 * dy
                    if t < 0.16:
                        v += groove
                    self.put(i, j, k, mat, v, False, prio)
        if ridge:
            rm = ridge_mat or mat
            pts = []
            for q in range(25):
                u = q / 24
                a = lo + 2 * ra * u
                p = [c[0], c[1], c[2]]
                p[axis] = a
                rr = 1 - ((a - c[axis]) / ra) ** 2
                if rr <= 0:
                    continue
                if axis != 1:
                    p[1] = c[1] + ry * math.sqrt(rr) * (1 + lift * 0.5)
                pts.append(tuple(p))
            if len(pts) >= 2:
                self.sweep(pts, ridge, ridge * 0.6, rm, val + 0.12, prio=prio + 1, smooth=False,
                           vfn=lambda t, dd, p: val + 0.16 + 0.1 * (1 - dd) - (0.2 if (seg(p)[1] < 0.16) else 0))

    def scales(self, mats=None, size=1.6, amount=0.16, rim=-0.2, seed=0):
        """Overlapping scale pattern on the surface (rows offset by half a scale; top of each scale lit)."""
        def f(x, y, z, n, m, v):
            u = (x + z * 0.7) / size
            w = y / (size * 0.8)
            row = math.floor(w)
            u += 0.5 * (row % 2)
            fu, fw = u - math.floor(u) - 0.5, w - row
            d = math.sqrt(fu * fu * 1.6 + (fw - 0.9) ** 2)
            if d > 0.92:
                return v + rim
            return v + amount * (fw - 0.3)
        self.paint(f, mats)

    def fur(self, mats=None, direction=(0, -1, 0), length=1.2, density=0.25, mat=None, val=None, streak=0.14,
            seed=0, prio=2):
        """Fur: strand-wise value streaks on the surface + tufts combed along direction."""
        sd = self.seed + 97 + seed
        dirn = vnorm(direction)
        u_ax, w_ax = frame_of(dirn)
        surf = self.exposed(mats)

        def strand(p):
            a = vdot(p, u_ax) / 0.9
            b = vdot(p, w_ax) / 0.9
            return h2(int(math.floor(a)), int(math.floor(b)), sd)
        for key, n in surf:
            cur = self.vox[key]
            p = self.px(key)
            cur[1] += streak * (strand(p) - 0.5) * 2
        for key, n in surf:
            if h3(key[0], key[1], key[2], sd + 1) >= density:
                continue
            nn = vnorm(n) if n != (0, 0, 0) else (0, 1, 0)
            if nn[1] < -0.5:
                continue
            p = self.px(key)
            cur = self.vox[key]
            d = vnorm(vadd(vmul(nn, 0.55), vmul(dirn, 0.8)))
            v0 = cur[1] if val is None else val
            self.cone(p, d, length * (0.6 + 0.6 * h3(key[0], key[2], key[1], sd + 2)), self.vs * 0.55,
                      mat or cur[0], v0, v0 + 0.15, prio=prio, r_tip=self.vs * 0.4)

    def _pick(self, cands, amount, sd):
        """amount: int = exactly that many (hash-ordered), float = probability per candidate."""
        if not amount or not cands:
            return []
        if isinstance(amount, int):
            return sorted(cands, key=lambda q: h3(q[0], q[1], q[2], sd))[:amount]
        return [q for q in cands if h3(q[0], q[1], q[2], sd) < amount]

    def moss(self, coverage=0.55, thick=1.0, mat='moss', val=0.5, mats=None, scale=4.0, up_min=0.35, hang=0,
             hang_len=(1.0, 3.5), sprouts=0, sprout_mat='leaf', flowers=0, flower_mat='lichen', glow_buds=0,
             bud_mat='glow', seed=0, prio=2, base_layer=True):
        """Moss cushions on upward surfaces.  A smooth noise height field (scale px) gates the cover and
        sets the cushion height (up to `thick` px), so neighbouring voxels share layers and merge into
        calm, readable clumps.  Decorations take a count (int) or a probability (float): hanging strands
        from overhangs, fern sprouts, pale flowers, glowing spore buds."""
        sd = self.seed + 113 + seed
        vs = self.vs
        thr = 1.0 - coverage
        tops = []
        nmax = max(1, int(round(thick / vs)))
        for key, n in self.exposed(mats):
            if n[1] <= 0:
                continue
            if n[1] / vlen(n) < up_min:
                continue
            x, y, z = self.px(key)
            q = fbm3(x / scale, y / (scale * 2.0), z / scale, sd)
            if q < thr:
                continue
            k = min(1.0, (q - thr) / max(1e-6, coverage * 0.6))
            hgt = int(round(k * nmax))
            if base_layer:
                cur = self.vox[key]
                cur[0], cur[1] = mat, val - 0.1
            top = key
            for s_ in range(1, hgt + 1):
                kk = (key[0], key[1] + s_, key[2])
                if kk in self.vox:
                    break
                self.put(kk[0], kk[1], kk[2], mat, val - 0.04, False, prio)
                top = kk
            if top != key:
                self.vox[top][1] = val + 0.08      # sunlit cushion top, calm sides (no strata)
            tops.append(top)
        self._decorate(tops, sd, mat, val, sprouts, sprout_mat, flowers, flower_mat, glow_buds, bud_mat, hang,
                       hang_len, prio)

    def sprinkle(self, mats, sprouts=0, flowers=0, glow_buds=0, hang=0, up_min=0.5, mat='moss', val=0.5,
                 sprout_mat='leaf', flower_mat='lichen', bud_mat='glow', hang_len=(1.0, 3.0), seed=0, prio=3):
        """Ferns, flowers, glowing buds (count or probability) on the upward voxels of mats, and hanging
        strands (of `mat`) from their overhangs."""
        tops = []
        for key, n in self.exposed(mats):
            ln = vlen(n)
            if ln and n[1] / ln >= up_min:
                tops.append(key)
        self._decorate(tops, self.seed + 359 + seed, mat, val, sprouts, sprout_mat, flowers, flower_mat, glow_buds,
                       bud_mat, hang, hang_len, prio, hang_mats=mats)

    def _decorate(self, tops, sd, mat, val, sprouts, sprout_mat, flowers, flower_mat, glow_buds, bud_mat, hang,
                  hang_len, prio, hang_mats=None):
        vs = self.vs
        for t in self._pick(tops, sprouts, sd + 3):
            L = max(2, int((1.0 + 1.2 * h3(t[0], 1, t[2], sd)) / vs))
            lean = 1 if h3(t[0], 2, t[2], sd) > 0.5 else -1
            for s_ in range(1, L + 1):
                off = lean if (s_ == L and L > 2) else 0
                self.put(t[0] + off, t[1] + s_, t[2], sprout_mat, 0.4 + 0.45 * s_ / L, False, prio + 1)
            m_ = t[1] + max(1, L // 2)
            self.put(t[0] - lean, m_, t[2], sprout_mat, 0.6, False, prio + 1)
        for t in self._pick(tops, flowers, sd + 4):
            self.put(t[0], t[1] + 1, t[2], flower_mat, 0.92, False, prio + 1)
        for t in self._pick(tops, glow_buds, sd + 5):
            self.put(t[0], t[1] + 1, t[2], bud_mat, 0.85, True, prio + 1)
        if hang:
            cands = []
            for key, n in self.exposed(hang_mats or [mat]):
                below = (key[0], key[1] - 1, key[2])
                if below in self.vox or n[1] > 0:
                    continue
                cands.append(key)
            for key in self._pick(cands, hang, sd + 7):
                L = (hang_len[0] + (hang_len[1] - hang_len[0]) * h3(key[2], key[0], key[1], sd + 8)) / vs
                for s_ in range(1, int(L) + 1):
                    kk = (key[0], key[1] - s_, key[2])
                    if kk in self.vox:
                        break
                    self.put(kk[0], kk[1], kk[2], mat, val - 0.08 - 0.06 * s_, False, prio)

    def moss_paint(self, coverage=0.7, mat='moss', val=0.5, mats=None, scale=4.0, up_min=0.2, patch=0.14, seed=0,
                   depth=1):
        """Turn the upper surface itself into moss (no added geometry — cheap on big curved bodies): a smooth
        noise mask picks the covered area, a second noise splits it into light/dark patches.  depth = how
        many voxels below the surface are recoloured too (so rims and sides read mossy)."""
        sd = self.seed + 307 + seed
        thr = 1.0 - coverage
        hit_keys = []
        for key, n in self.exposed(mats):
            ln = vlen(n)
            if ln == 0 or n[1] / ln < up_min:
                continue
            x, y, z = self.px(key)
            q = fbm3(x / scale, y / (scale * 1.5), z / scale, sd)
            if q < thr:
                continue
            tone = patch if fbm3(x / (scale * 0.6), y / scale, z / (scale * 0.6), sd + 1) > 0.5 else -patch * 0.5
            hit_keys.append((key, val + tone))
        for key, v in hit_keys:
            for dd in range(depth):
                kk = (key[0], key[1] - dd, key[2])
                cur = self.vox.get(kk)
                if cur is None or (mats and cur[0] not in mats and cur[0] != mat):
                    break
                cur[0], cur[1] = mat, v - 0.05 * dd
        return [k for k, _ in hit_keys]

    def clumps(self, n, r=1.4, mat='moss', val=0.55, mats=None, lump=0.3, seed=0, up_min=0.5, squash=0.6,
               region=None, prio=2):
        """n lumpy cushions (moss / lichen / fungus) sitting on upward surfaces; region(x, y, z) filters spots."""
        sd = self.seed + 331 + seed
        cands = []
        for key, nrm in self.exposed(mats):
            ln = vlen(nrm)
            if ln == 0 or nrm[1] / ln < up_min:
                continue
            p = self.px(key)
            if region and not region(*p):
                continue
            cands.append(key)
        picks = []
        min_d = r * 1.6
        for key in sorted(cands, key=lambda q: h3(q[0], q[1], q[2], sd)):
            p = self.px(key)
            if all(vlen(vsub(p, q)) >= min_d for q in picks):
                picks.append(p)
            if len(picks) >= n:
                break
        for k, p in enumerate(picks):
            rr = r * (0.7 + 0.5 * h2(k, 1, sd))
            c = (p[0], p[1] + rr * squash * 0.35, p[2])
            self.blob(c, (rr, rr * squash, rr), mat, val, lump=lump, lump_scale=max(1.0, rr * 0.8), prio=prio,
                      seed=seed + k, top=0.16)
        return picks

    def vine(self, pts, r=0.45, mat='vine', val=0.45, leaves=0.35, leaf_mat='leaf', leaf_size=1.1, buds=0.0,
             bud_mat='glow', prio=2, seed=0, smooth=True):
        """Thin vine along px points with alternating leaves (and optional glowing buds)."""
        path = catmull(list(pts), 8) if (smooth and len(pts) >= 3) else list(pts)
        self.sweep(path, r * 1.15, r * 0.8, mat, val, smooth=False, prio=prio,
                   vfn=lambda t, d, p: val + 0.12 * (1 - d) + 0.06 * math.sin(t * 30))
        sd = self.seed + 151 + seed
        samples = resample(path, 1.6)
        side = 1
        for n_, (p, t) in enumerate(samples[1:-1], 1):
            a, b = samples[n_ - 1][0], samples[n_ + 1][0]
            tang = vnorm(vsub(b, a))
            u, w = frame_of(tang)
            hv = h2(n_, 1, sd)
            if hv < leaves:
                off = vmul(vnorm(vadd(vmul(u, side), (0, 0.6, 0))), leaf_size * 0.9)
                c = vadd(p, off)
                self.blob(c, (leaf_size, leaf_size * 0.5, leaf_size), leaf_mat, prio=prio + 1,
                          vfn=lambda x, y, z, d, c=c: 0.4 + 0.3 * (1 - d) + (0.12 if y > c[1] else -0.05))
                side = -side
            elif hv < leaves + buds:
                self.dot(vadd(p, vmul(u, r + self.vs)), bud_mat, 0.85, glow=True, prio=prio + 2)

    def vine_wrap(self, a, b, R, turns=1.5, phase=0.0, **kw):
        """Vine spiralling around the segment a→b at radius R (px)."""
        axis = vsub(b, a)
        u, w = frame_of(axis)
        pts = []
        n = max(12, int(turns * 16))
        for k in range(n + 1):
            t = k / n
            ang = phase + turns * 2 * math.pi * t
            off = vadd(vmul(u, math.cos(ang) * R), vmul(w, math.sin(ang) * R))
            pts.append(vadd(vadd(a, vmul(axis, t)), off))
        self.vine(pts, smooth=False, **kw)

    def branch(self, base, direction, length, r, depth=2, fork=2, spread=0.55, decay=0.62, mat='bark', val=0.45,
               bend=(0, 0, 0), tip=None, tip_mat='leaf', tip_size=0.9, seed=0, prio=2, floor_y=None, glow_tip=False):
        """Recursive branching limb (antlers, roots, coral, dead trees): a gently curved tapered segment, then
        `fork` children rotated by `spread` around it, `depth` levels.  bend (px vector) curves each segment;
        floor_y clamps points to stay above a ground plane (roots crawl along it).  tip: 'leaf' | 'bud' | None."""
        rr = random.Random((self.seed * 31 + seed) & 0xFFFFFFFF)

        def seg(p0, d, L, rad, lvl):
            d = vnorm(d)
            p3 = vadd(vadd(p0, vmul(d, L)), vmul(bend, L / max(1.0, length)))
            if floor_y is not None:
                p3 = (p3[0], max(floor_y + rad, p3[1]), p3[2])
            p1 = vadd(p0, vmul(d, L * 0.4))
            p2 = vadd(vmul(vadd(p1, p3), 0.5), vmul(bend, 0.3 * L / max(1.0, length)))
            pts = bezier(p0, p1, p2, p3, 8)
            r_end = max(self.vs * 0.5, rad * decay)
            self.sweep(pts, rad, r_end, mat, val, prio=prio, smooth=False,
                       vfn=lambda t, dd, p: val + 0.1 * (1 - dd) + 0.08 * lvl)
            if lvl >= depth:
                if tip == 'leaf':
                    self.blob(p3, (tip_size, tip_size * 0.6, tip_size), tip_mat, 0.55, prio=prio + 1, lump=0.25,
                              lump_scale=0.8, seed=lvl * 7 + int(p3[0] * 3))
                elif tip == 'bud':
                    self.dot(p3, tip_mat, 0.85, glow=glow_tip, prio=prio + 2)
                return
            nd = vnorm(vsub(p3, p2))
            u, w = frame_of(nd)
            for c in range(fork):
                ang = 2 * math.pi * c / fork + rr.random() * 1.2
                side = vadd(vmul(u, math.cos(ang)), vmul(w, math.sin(ang)))
                cd = vnorm(vadd(nd, vmul(side, spread * (0.7 + 0.6 * rr.random()))))
                seg(p3, cd, L * (0.55 + 0.25 * rr.random()), r_end, lvl + 1)
        seg(base, direction, length, r, 0)

    def mushroom(self, base, up=(0, 1, 0), stem=2.0, cap_r=2.0, cap_h=None, mat='cap', val=0.55, stem_mat='gill',
                 gill_mat='gill', spots=0.25, spot_mat='lichen', glow=False, prio=3, stem_r=None):
        """Mushroom: stem along up, domed cap with darker gill underside and pale spots."""
        u = vnorm(up)
        top = vadd(base, vmul(u, stem))
        sr = stem_r or max(self.vs * 0.6, cap_r * 0.28)
        self.capsule(base, top, sr * 1.1, sr * 0.9, stem_mat, 0.7, prio=prio)
        ch = cap_h or cap_r * 0.6
        sd = self.seed + 171
        self.blob(top, (cap_r, ch, cap_r), mat, prio=prio + 1, glow=glow,
                  cut=lambda x, y, z: vdot(vsub((x, y, z), top), u) < -ch * 0.15,
                  vfn=lambda x, y, z, d: (spot_mat, 0.85) if (spots and d > 0.72 and
                                                             h3(round(x / 0.8), round(y / 0.8), round(z / 0.8), sd)
                                                             < spots) else
                  (gill_mat, 0.35) if vdot(vsub((x, y, z), top), u) < ch * 0.05 else val + 0.25 * (1 - d))

    def crystals(self, base, up=(0, 1, 0), n=4, size=4.0, r=1.0, mat='crystal', glow=False, spread=0.6, seed=0,
                 prio=3):
        """Crystal cluster (one tall prism + n−1 leaning ones) — wraps core.Grid.crystal in px."""
        rr = random.Random(self.seed * 7 + seed)
        vs = self.vs
        u = vnorm(up)
        a_, b_ = frame_of(u)
        bq = self.to_vox(base)
        self.crystal(bq, u, size * 1.2 / vs, r * 1.1 / vs, mat, glow=glow, prio=prio)
        for k in range(max(0, n - 1)):
            ang = 2 * math.pi * k / max(1, n - 1) + rr.random() * 0.8
            side = vadd(vmul(a_, math.cos(ang)), vmul(b_, math.sin(ang)))
            d = vnorm(vadd(u, vmul(side, spread)))
            p = vadd(base, vmul(side, r * 0.9))
            self.crystal(self.to_vox(p), d, size * (0.5 + rr.random() * 0.35) / vs, r * 0.8 / vs, mat, glow=glow,
                         prio=prio)

    def wing(self, root, side, span, rise, fingers=4, z=0.0, bone_mat='bone', membrane_mat='membrane', val=0.5,
             tatter=0.2, bone_r=0.6, droop=0.35, thick=1, seed=0, prio=2):
        """Bat/dragon wing in the XY plane at depth z: an arm rises from root to the wrist, finger bones
        fan from the wrist, membrane spans fingers (scalloped, tattered trailing edge).  side = ±1 (model X)."""
        rx, ry = root[0], root[1]
        wrist = (rx + side * span * 0.45, ry + rise, z)
        elbow = (rx + side * span * 0.22, ry + rise * 0.75, z)
        self.limb([(rx, ry, z), elbow, wrist], [bone_r * 1.4, bone_r * 1.2, bone_r], bone_mat, val + 0.1, prio=prio + 1)
        tips = []
        for f in range(fingers):
            t = f / max(1, fingers - 1)
            ang = math.radians(80 - 125 * t - droop * 30)
            L = span * (0.62 - 0.18 * t) + span * 0.05
            tip = (wrist[0] + side * math.cos(ang) * L, wrist[1] + math.sin(ang) * L * 0.85 - span * 0.12 * t, z)
            mid = ((wrist[0] + tip[0]) / 2 + side * 0.3, (wrist[1] + tip[1]) / 2 + 0.6 * (1 - t), z)
            self.sweep([wrist, mid, tip], bone_r, bone_r * 0.5, bone_mat, val + 0.05, prio=prio + 1)
            tips.append(tip)
        # membrane polygon: root → wrist fingers … → back to the body below the root
        poly = [(rx, ry + rise * 0.6), (wrist[0], wrist[1])] + [(t[0], t[1]) for t in tips] + \
               [(rx + side * span * 0.08, ry - rise * 0.25)]
        sd = self.seed + 191 + seed
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        vs = self.vs
        edges = list(zip(poly, poly[1:] + poly[:1]))
        trailing = edges[2:]   # edges between finger tips + back to the body

        def inside(x, y):
            c = False
            for (x1, y1), (x2, y2) in edges:
                if (y1 > y) != (y2 > y):
                    if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                        c = not c
            return c

        def scallop(x, y):
            """Distance-based bite out of the trailing edge between neighbouring finger tips."""
            for (x1, y1), (x2, y2) in zip([(t[0], t[1]) for t in tips], [(t[0], t[1]) for t in tips[1:]] +
                                          [(rx + side * span * 0.08, ry - rise * 0.25)]):
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                L = math.hypot(x2 - x1, y2 - y1)
                # bite centre pushed toward the wrist
                cx, cy = mx + (wrist[0] - mx) * 0.08, my + (wrist[1] - my) * 0.08
                if math.hypot(x - cx, y - cy) < L * 0.32:
                    return True
            return False
        nz = max(0, int(thick) - 1)
        for i in self._range(min(xs), max(xs)):
            x = i * vs
            for j in self._range(min(ys), max(ys)):
                y = j * vs
                if not inside(x, y) or scallop(x, y):
                    continue
                if tatter and h2(i, j, sd) < tatter * 0.12:
                    continue
                vein = 0.0
                for tip in tips:
                    # darker vein lines toward each finger
                    ax, ay = tip[0] - wrist[0], tip[1] - wrist[1]
                    L2 = ax * ax + ay * ay
                    s = ((x - wrist[0]) * ax + (y - wrist[1]) * ay) / max(1e-6, L2)
                    if 0 < s < 1:
                        dd = abs((x - wrist[0]) * ay - (y - wrist[1]) * ax) / math.sqrt(L2)
                        if dd < vs * 0.9:
                            vein = -0.12
                v = val + 0.2 * (y - ry) / max(1.0, rise) + vein
                for w in range(-nz, nz + 1):
                    self.put(i, j, int(round(z / vs)) + w, membrane_mat, v, False, prio)

    def tentacle(self, p0, p1, p2, p3, r0, r1, mat='skin', val=0.5, suckers=True, sucker_mat='skin2',
                 under=(0, -1, 0), prio=2, tip_mat=None, glow_tip=False):
        """Bezier tentacle with sucker dots along its underside."""
        pts = bezier(p0, p1, p2, p3, 20)
        self.sweep(pts, r0, r1, mat, val, prio=prio, smooth=False,
                   vfn=lambda t, d, p: (tip_mat, 0.8, glow_tip) if (tip_mat and t > 0.9) else val + 0.1 * (1 - d))
        if suckers:
            un = vnorm(under)
            for p, t in resample(pts, max(0.9, r0 * 0.9))[1:-1]:
                rr = r0 + (r1 - r0) * t
                if rr < self.vs:
                    continue
                self.dot(vadd(p, vmul(un, rr * 0.95)), sucker_mat, 0.75, prio=prio + 1)

    def cloth(self, top, length, mat='cloth', val=0.5, tatter=0.35, normal=(0, 0, -1), thick=1, folds=0.14,
              fold_period=2.2, holes=0.04, seed=0, sway=None, prio=2):
        """Hanging cloth from a top polyline (px points, left → right): columns hang `length` px (float
        or fn(u) with u 0..1 along the top), the bottom edge is torn into points, a few holes near the hem;
        vertical fold shading.  sway=(dx, dz) per px of drop drifts the hem (wind / motion)."""
        sd = self.seed + 211 + seed
        vs = self.vs
        samples = resample(list(top), vs * 0.9)
        nn = vnorm(normal)
        for n_, (p, u) in enumerate(samples):
            L = length(u) if callable(length) else length
            col = int(math.floor(n_ * 0.9 / max(1, round(0.9 / vs))))
            L *= 1 - tatter * (0.55 * h2(col // 2, 1, sd) + 0.45 * h2(col, 2, sd))
            steps = max(1, int(L / vs))
            fold = folds * math.sin(n_ * vs / fold_period * 2 * math.pi)
            for s in range(steps + 1):
                drop = s * vs
                q = (p[0] + (sway[0] * drop if sway else 0), p[1] - drop, p[2] + (sway[1] * drop if sway else 0))
                if holes and s > steps * 0.55 and h2(int(q[0] / vs) // 2, int(q[1] / vs) // 2, sd + 3) < holes:
                    continue
                v = val + fold - 0.18 * (drop / max(1.0, L)) + (0.06 if s == 0 else 0)
                for w in range(int(thick)):
                    qq = vadd(q, vmul(nn, -w * vs))
                    k = self.key(qq)
                    self.put(k[0], k[1], k[2], mat, v, False, prio)

    def rivets(self, pts, mat='brass', val=0.72, r=None, prio=4):
        for p in pts:
            if r and r > self.vs * 0.6:
                self.blob(p, r, mat, val, prio=prio)
            else:
                self.dot(p, mat, val, prio=prio)

    def plate(self, lo, hi, mat='iron', val=0.5, rivet_mat='brass', bevel=0.5, rivet_step=2.5, face=(0, 0, -1),
              rivets=True, prio=3, inset=0.6, dent=0.0, seed=0):
        """Metal plate (bevelled box) with rivets along the border of its `face` side."""
        sd = self.seed + 223 + seed
        self.rbox(lo, hi, mat, val, bevel=bevel, prio=prio,
                  vfn=(lambda x, y, z: val + dent * (noise3(x / 2.0, y / 2.0, z / 2.0, sd) - 0.5) * 2) if dent else None)
        if not rivets:
            return
        f = vnorm(face)
        ax = max(range(3), key=lambda a: abs(f[a]))
        o = [a for a in range(3) if a != ax]
        surf = (hi[ax] if f[ax] > 0 else lo[ax]) + f[ax] * self.vs * 0.6
        a0, a1 = sorted((lo[o[0]], hi[o[0]]))
        b0, b1 = sorted((lo[o[1]], hi[o[1]]))
        a0, a1, b0, b1 = a0 + inset, a1 - inset, b0 + inset, b1 - inset
        pts = []

        def P(a, b):
            q = [0.0, 0.0, 0.0]
            q[ax] = surf
            q[o[0]] = a
            q[o[1]] = b
            return tuple(q)
        na = max(1, int((a1 - a0) / rivet_step))
        nb = max(1, int((b1 - b0) / rivet_step))
        for s in range(na + 1):
            a = a0 + (a1 - a0) * s / na
            pts += [P(a, b0), P(a, b1)]
        for s in range(1, nb):
            b = b0 + (b1 - b0) * s / nb
            pts += [P(a0, b), P(a1, b)]
        self.rivets(pts, rivet_mat, prio=prio + 1)

    def gear(self, c, R, teeth=8, axis='z', thick=1.0, mat='brass', val=0.55, hole=0.3, spokes=4, prio=3):
        """Gear disc (teeth, spokes, axle hole) facing along axis."""
        def m(u, v):
            d = math.hypot(u, v)
            a = math.atan2(v, u)
            if hole and d < R * hole:
                return False
            if d <= R - 0.8:
                if spokes and R >= 3 and R * 0.42 < d < R - 1.4:
                    return any(abs(((a - s * 2 * math.pi / spokes) + math.pi) % (2 * math.pi) - math.pi) < 0.32
                               for s in range(spokes))
                return True
            return d <= R + 0.5 and ((a * teeth / (2 * math.pi)) % 1.0) < 0.5
        plane = {'z': 'xy', 'x': 'zy', 'y': 'xz'}[axis]
        if plane == 'xy':
            mk = (lambda u, v: m(u - c[0], v - c[1]))
            lo, hi, depth = (c[0] - R - 1, c[1] - R - 1), (c[0] + R + 1, c[1] + R + 1), c[2]
        elif plane == 'zy':
            mk = (lambda u, v: m(u - c[2], v - c[1]))
            lo, hi, depth = (c[2] - R - 1, c[1] - R - 1), (c[2] + R + 1, c[1] + R + 1), c[0]
        else:
            mk = (lambda u, v: m(u - c[0], v - c[2]))
            lo, hi, depth = (c[0] - R - 1, c[2] - R - 1), (c[0] + R + 1, c[2] + R + 1), c[1]
        self.slab2d(mk, lo, hi, plane, depth, thick / 2, mat, prio=prio,
                    vfn=lambda u, v, w, e: val + 0.2 * min(1.0, e / 1.5) + (0.1 if w < 0 else 0))

    def runes(self, c, normal=(0, 0, -1), w=6.0, h=5.0, mat='rune', val=0.8, glow=True, seed=0, density=0.75,
              depth=12.0, prio=6):
        """Stamp rune glyphs (3×5 voxel bit-glyphs) onto the surface facing `normal` around c (px)."""
        f = vnorm(normal)
        up = (0, 1, 0) if abs(f[1]) < 0.9 else (0, 0, 1)
        side = vnorm(vcross(up, f))
        upv = vcross(f, side)
        vs = self.vs
        cols = max(1, int(w / vs / 4))
        rows = max(1, int(h / vs / 6))
        sd = self.seed + 233 + seed
        for gr in range(rows):
            for gc in range(cols):
                if h2(gc, gr, sd) > density:
                    continue
                gi = int(h2(gc, gr, sd + 1) * 8)
                for bx in range(3):
                    for by in range(5):
                        if not rune_bit(gi, bx, by):
                            continue
                        su = (gc * 4 + bx - cols * 2 + 0.5) * vs
                        sv = (-(gr * 6 + by) + rows * 3 - 0.5) * vs
                        o = vadd(vadd(vadd(c, vmul(side, su)), vmul(upv, sv)), vmul(f, depth))
                        p = self.hit(o, vmul(f, -1), depth * 2)
                        if p is not None:
                            self.dot(p, mat, val, glow=glow, prio=prio)

    def chain(self, pts, link=1.2, mat='iron', val=0.5, prio=3):
        """Chain of alternating links along px points."""
        path = catmull(list(pts), 8) if len(pts) >= 3 else list(pts)
        for n_, (p, t) in enumerate(resample(path, link)):
            if n_ % 2:
                self.blob(p, (link * 0.55, link * 0.35, link * 0.35), mat, val + 0.1, prio=prio,
                          cut=lambda x, y, z, p=p: abs(y - p[1]) < self.vs * 0.4 and abs(z - p[2]) < self.vs * 0.4)
            else:
                self.blob(p, (link * 0.35, link * 0.55, link * 0.35), mat, val, prio=prio)

    def strands(self, a, b, sag=1.0, mat='web', val=0.8, r=None, prio=1):
        """A thin sagging line (web silk, hair, wire) between two px points."""
        mid = vadd(vmul(vadd(a, b), 0.5), (0, -sag, 0))
        pts = bezier(a, vadd(vmul(vadd(a, mid), 0.5), (0, -sag * 0.3, 0)),
                     vadd(vmul(vadd(b, mid), 0.5), (0, -sag * 0.3, 0)), b, 16)
        rr = r or self.vs * 0.5
        self.sweep(pts, rr, rr, mat, val, prio=prio, smooth=False)


# ───────────────────────────── design context ─────────────────────────────

class PartCtx:
    """What a design function receives for one part (built by mobs.build_mob).

    mid, boss, rank, floor, theme · name, form, anim, size (w, h, d px), pivot (blocks, YAML) ·
    out: model-X sign pointing away from the body centre (+1 / −1) · hang: arm/leg hanging from the pivot ·
    holder/hand: the holding arm (part dict) and the hand position in this part's px coords (held items) ·
    parts: every part dict · features, palette · vs: suggested voxel size · budget: element hint ·
    shared: dict shared by every part of this mob (e.g. ramps, random choices) · rng: seeded Random.
    """

    def __init__(self, mid, look, part, parts, boss, rank, floor, theme, out, hang, holder=None, hand=None,
                 vs=0.5, budget=720, shared=None, seed=0):
        self.mid = mid
        self.look = look
        self.part = part
        self.parts = parts
        self.name = part.get('name', 'part')
        self.form = part.get('form') or 'box'
        self.anim = part.get('anim') or 'static'
        self.size = tuple(float(v) for v in (part.get('size') or [8, 8, 8]))
        self.pivot = tuple(float(v) for v in (part.get('pivot') or [0, 0, 0]))
        self.boss = boss
        self.rank = rank
        self.floor = floor
        self.theme = theme
        self.out = out
        self.hang = hang
        self.holder = holder
        self.hand = hand
        self.vs = vs
        self.budget = budget
        self.shared = shared if shared is not None else {}
        self.features = set(look.features)
        self.seed = seed & 0xFFFF
        self.rng = random.Random(seed)
        self.vs_mul = 1.0

    def grid(self, vs=None):
        """New MobGrid at vs px per voxel (default: the suggested ctx.vs).  When a mob is over budget at the
        coarsest colour level the builder re-runs the design with vs_mul > 1 (coarser voxels)."""
        return MobGrid((vs or self.vs) * self.vs_mul, self.seed)

    def part_def(self, name):
        return next((p for p in self.parts if p.get('name') == name), None)

    def offset_to(self, name):
        """Model-space px vector from this part's pivot to another part's pivot (front = −Z)."""
        p = self.part_def(name)
        if p is None:
            return None
        q = [float(v) for v in (p.get('pivot') or [0, 0, 0])]
        a = self.pivot
        return (-(q[0] - a[0]) * 16, (q[1] - a[1]) * 16, -(q[2] - a[2]) * 16)

    def set_ramp(self, mat, colours):
        """Mob-wide custom colour ramp for a material (every part of this mob)."""
        self.shared.setdefault('ramps', {})[mat] = [tuple(int(c) for c in col[:3]) for col in colours]
