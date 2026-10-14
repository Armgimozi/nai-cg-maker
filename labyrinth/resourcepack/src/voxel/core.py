"""Voxel grid, brushes, shading and mesh conversion (all original code).

A design paints voxels (integer centres, 1 voxel = `vs` model units) with a *material* and a base
*value* (0..1 position on that material's colour ramp).  `shade()` adds normal/AO/edge lighting
and per-voxel noise, then quantises to ramp levels.  `mesh()` greedily merges equal-colour voxels
into cuboid elements (interior voxels are wildcards, so they may be shared by several boxes —
every *exposed* voxel belongs to exactly one box, so visible faces never z-fight), emits only
faces that touch air, and maps every face to one 2×2 cell of a small per-item palette texture.
Glow voxels get palette cells per spatial cell so animation effects flow across the model.
"""
from __future__ import annotations

import math

from ..model import El, Model, Texel, BakedModel, r4
from ..util import h3, clamp

DIRS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
FACE_OF = {(1, 0, 0): 'east', (-1, 0, 0): 'west', (0, 1, 0): 'up', (0, -1, 0): 'down',
           (0, 0, 1): 'south', (0, 0, -1): 'north'}


# ───────────────────────────── curves ─────────────────────────────

def lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def bezier(p0, p1, p2, p3, n=24):
    out = []
    for k in range(n + 1):
        t = k / n
        u = 1 - t
        out.append(tuple(u * u * u * p0[i] + 3 * u * u * t * p1[i] + 3 * u * t * t * p2[i] + t * t * t * p3[i]
                         for i in range(3)))
    return out


def catmull(pts, n=10):
    """Catmull-Rom spline through pts."""
    if len(pts) < 3:
        return [lerp3(pts[0], pts[-1], k / n) for k in range(n + 1)]
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for s in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[s - 1], P[s], P[s + 1], P[s + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[i]) + (-p0[i] + p2[i]) * t + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t2
                                    + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * t3) for i in range(3)))
    out.append(pts[-1])
    return out


def helix(y0, y1, R, turns, phase=0.0, cx=0.0, cz=0.0, zs=1.0, rfn=None, n=None):
    """Points of a helix around the Y axis (x = R cos, z = R sin · zs)."""
    n = n or max(16, int(abs(y1 - y0) * 3 + turns * 24))
    out = []
    for k in range(n + 1):
        t = k / n
        a = phase + turns * 2 * math.pi * t
        r = R * (rfn(t) if rfn else 1.0)
        out.append((cx + r * math.cos(a), y0 + (y1 - y0) * t, cz + r * math.sin(a) * zs))
    return out


def resample(pts, step=0.3):
    """Even arc-length samples → [(point, t∈0..1)]."""
    segs = [(a, b, math.dist(a, b)) for a, b in zip(pts, pts[1:])]
    total = sum(d for _, _, d in segs)
    if total <= 1e-9:
        return [(pts[0], 0.0)]
    out = []
    acc = 0.0
    for a, b, d in segs:
        n = max(1, int(math.ceil(d / step)))
        for q in range(n):
            t = q / n
            out.append((lerp3(a, b, t), (acc + d * t) / total))
        acc += d
    out.append((pts[-1], 1.0))
    return out


# ───────────────────────────── grid ─────────────────────────────

class Grid:
    def __init__(self, seed=0):
        self.vox: dict = {}   # (i, j, k) -> [mat, val, glow, prio]
        self.seed = seed & 0xFFFF

    def put(self, i, j, k, mat, val=0.5, glow=False, prio=1):
        key = (int(i), int(j), int(k))
        cur = self.vox.get(key)
        if cur is None or prio >= cur[3]:
            self.vox[key] = [mat, val, glow, prio]

    def erase(self, i, j, k):
        self.vox.pop((int(i), int(j), int(k)), None)

    def get(self, key):
        return self.vox.get(key)

    def __len__(self):
        return len(self.vox)

    def bounds(self):
        ks = list(self.vox)
        return (tuple(min(k[a] for k in ks) for a in range(3)), tuple(max(k[a] for k in ks) for a in range(3)))

    # ── brushes ──
    def ball(self, c, r, mat, val=0.5, glow=False, prio=1, vfn=None, sq=(1.0, 1.0, 1.0)):
        rx, ry, rz = r * sq[0], r * sq[1], r * sq[2]
        for i in range(math.floor(c[0] - rx), math.ceil(c[0] + rx) + 1):
            for j in range(math.floor(c[1] - ry), math.ceil(c[1] + ry) + 1):
                for k in range(math.floor(c[2] - rz), math.ceil(c[2] + rz) + 1):
                    dx, dy, dz = (i - c[0]) / max(rx, 1e-6), (j - c[1]) / max(ry, 1e-6), (k - c[2]) / max(rz, 1e-6)
                    d = dx * dx + dy * dy + dz * dz
                    if d <= 1.0:
                        v = vfn(i, j, k, math.sqrt(d)) if vfn else val
                        if v is None:
                            continue
                        self.put(i, j, k, mat, v, glow, prio)

    def box(self, lo, hi, mat, val=0.5, glow=False, prio=1, vfn=None):
        for i in range(int(lo[0]), int(hi[0]) + 1):
            for j in range(int(lo[1]), int(hi[1]) + 1):
                for k in range(int(lo[2]), int(hi[2]) + 1):
                    v = vfn(i, j, k) if vfn else val
                    if v is None:
                        continue
                    self.put(i, j, k, mat, v, glow, prio)

    def tube(self, pts, r0, r1=None, mat='metal', val=0.5, glow=False, prio=1, vfn=None, step=0.3, sq=(1, 1, 1)):
        """Sweep a sphere along a polyline; radius r0→r1; vfn(t, d) → value (None skips)."""
        r1 = r0 if r1 is None else r1
        seen = {}
        for p, t in resample(pts, step):
            r = r0 + (r1 - r0) * t
            rr = max(0.5, r)
            for i in range(math.floor(p[0] - rr), math.ceil(p[0] + rr) + 1):
                for j in range(math.floor(p[1] - rr), math.ceil(p[1] + rr) + 1):
                    for k in range(math.floor(p[2] - rr), math.ceil(p[2] + rr) + 1):
                        dx, dy, dz = (i - p[0]) / sq[0], (j - p[1]) / sq[1], (k - p[2]) / sq[2]
                        d = math.sqrt(dx * dx + dy * dy + dz * dz)
                        if d <= rr:
                            key = (i, j, k)
                            nd = d / rr
                            if key in seen and seen[key][1] <= nd:
                                continue
                            seen[key] = (t, nd)
        for (i, j, k), (t, nd) in seen.items():
            v = vfn(t, nd, (i, j, k)) if vfn else val
            if v is None:
                continue
            self.put(i, j, k, mat, v, glow, prio)
        return seen

    def slab(self, mask, lo, hi, plane='xy', depth=0, max_half=2, slope=0.5, mat='metal', vfn=None, glow=False,
             prio=1, base_half=0):
        """Extrude a 2D silhouette with bevel.  mask(u, v) → bool over integer cells in [lo, hi] (u, v ranges).
        Half-thickness = base_half + min(max_half, floor(dist·slope)); dist = steps to the outline.
        plane 'xy' extrudes along z around `depth`; 'zy' along x; 'xz' along y."""
        cells = {(u, v) for u in range(lo[0], hi[0] + 1) for v in range(lo[1], hi[1] + 1) if mask(u, v)}
        dist = {}
        frontier = []
        for (u, v) in cells:
            if any((u + du, v + dv) not in cells for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                dist[(u, v)] = 0
                frontier.append((u, v))
        while frontier:
            nxt = []
            for (u, v) in frontier:
                for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (u + du, v + dv)
                    if q in cells and q not in dist:
                        dist[q] = dist[(u, v)] + 1
                        nxt.append(q)
            frontier = nxt
        for (u, v), d in dist.items():
            h = base_half + min(max_half, int(d * slope))
            for w in range(-h, h + 1):
                val = vfn(u, v, w, d) if vfn else 0.5
                if val is None:
                    continue
                m = mat
                if isinstance(val, tuple):
                    m, val = val
                if plane == 'xy':
                    self.put(u, v, depth + w, m, val, glow, prio)
                elif plane == 'zy':
                    self.put(depth + w, v, u, m, val, glow, prio)
                else:
                    self.put(u, depth + w, v, m, val, glow, prio)
        return dist

    def crystal(self, base, direction, length, r, mat='crystal', glow=False, prio=2, tip=0.45):
        """Faceted crystal prism with pointed tip from base along direction."""
        dl = math.sqrt(sum(c * c for c in direction)) or 1.0
        d = tuple(c / dl for c in direction)
        # orthonormal frame
        a = (0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0)
        u = _norm(_cross(d, a))
        w = _cross(d, u)
        ext = length + r + 1
        for i in range(math.floor(base[0] - ext), math.ceil(base[0] + ext) + 1):
            for j in range(math.floor(base[1] - ext), math.ceil(base[1] + ext) + 1):
                for k in range(math.floor(base[2] - ext), math.ceil(base[2] + ext) + 1):
                    p = (i - base[0], j - base[1], k - base[2])
                    s = p[0] * d[0] + p[1] * d[1] + p[2] * d[2]
                    if s < -0.3 or s > length:
                        continue
                    pu = p[0] * u[0] + p[1] * u[1] + p[2] * u[2]
                    pw = p[0] * w[0] + p[1] * w[1] + p[2] * w[2]
                    rad = r if s < length * (1 - tip) else r * (length - s) / (length * tip)
                    hexd = max(abs(pu), abs(pu) * 0.5 + abs(pw) * 0.87)
                    if hexd <= max(0.45, rad):
                        facet = (0.62 if pu > 0 else 0.38) + (0.12 if pw > 0 else -0.06)
                        if s > length * (1 - tip):
                            facet += 0.18
                        self.put(i, j, k, mat, facet, glow, prio)

    def gem(self, c, r, mat='gem', glow=False, prio=3):
        for i in range(math.floor(c[0] - r), math.ceil(c[0] + r) + 1):
            for j in range(math.floor(c[1] - r), math.ceil(c[1] + r) + 1):
                for k in range(math.floor(c[2] - r), math.ceil(c[2] + r) + 1):
                    dx, dy, dz = i - c[0], j - c[1], k - c[2]
                    if abs(dx) + abs(dy) + abs(dz) <= r + 0.01:
                        v = 0.55 - 0.12 * (dx - dy) / max(r, 1) + (0.3 if (dx, dy) == (0, 0) and dz >= 0 else 0)
                        self.put(i, j, k, mat, v, glow, prio)

    def torus(self, c, R, r, axis='z', mat='orn', val=0.6, glow=False, prio=2, vfn=None, arc=(0.0, 1.0)):
        n = max(24, int(R * 10))
        pts = []
        for k in range(n + 1):
            a = 2 * math.pi * (arc[0] + (arc[1] - arc[0]) * k / n)
            ca, sa = math.cos(a) * R, math.sin(a) * R
            if axis == 'z':
                pts.append((c[0] + ca, c[1] + sa, c[2]))
            elif axis == 'y':
                pts.append((c[0] + ca, c[1], c[2] + sa))
            else:
                pts.append((c[0], c[1] + sa, c[2] + ca))
        return self.tube(pts, r, r, mat, val, glow, prio, vfn=vfn)

    def mirror_x(self, cx=0):
        for (i, j, k), v in list(self.vox.items()):
            mi = 2 * cx - i
            if (mi, j, k) not in self.vox:
                self.vox[(mi, j, k)] = list(v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    l = math.sqrt(sum(c * c for c in a)) or 1.0
    return tuple(c / l for c in a)


# ───────────────────────────── shading ─────────────────────────────

LIGHT = _norm((-0.45, 0.8, 0.45))
NOISE = {'metal': 0.05, 'blade': 0.05, 'edge': 0.04, 'orn': 0.06, 'grip': 0.08, 'wood': 0.1, 'scale': 0.1,
         'belly': 0.08, 'vine': 0.12, 'leaf': 0.14, 'crystal': 0.06, 'gem': 0.0, 'glow': 0.04, 'feather': 0.06,
         'bone': 0.1, 'dark': 0.06, 'cloth': 0.08, 'fungus': 0.1, 'shell': 0.1, 'ink': 0.06, 'paper': 0.06,
         'flame': 0.08, 'ice': 0.06, 'string': 0.0, 'eye': 0.0, 'tendril': 0.1}


def shade(grid: Grid, ramps: dict, glow_mats=(), noise_mul=1.0):
    """→ {key: (mat, level, glow)}.  Lighting by voxel normal, AO, edge highlight, hashed noise."""
    vox = grid.vox
    out = {}
    seed = grid.seed
    for key, (mat, val, glow, _p) in vox.items():
        i, j, k = key
        nx = ny = nz = 0
        for d in DIRS:
            if (i + d[0], j + d[1], k + d[2]) not in vox:
                nx += d[0]
                ny += d[1]
                nz += d[2]
        v = val
        exposed = (nx, ny, nz) != (0, 0, 0)
        if exposed:
            ln = math.sqrt(nx * nx + ny * ny + nz * nz)
            dot = (nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / ln
            v += 0.09 * dot
            comps = (nx != 0) + (ny != 0) + (nz != 0)
            if comps >= 2 and dot > 0.25:
                v += 0.08
            elif comps >= 2 and dot < -0.4:
                v -= 0.06
        # ambient occlusion: crowded neighbourhood (concave corners) → darker
        occ = 0
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for dk in (-1, 0, 1):
                    if (i + di, j + dj, k + dk) in vox:
                        occ += 1
        if exposed and occ > 17:
            v -= 0.022 * (occ - 17)
        amp = NOISE.get(mat, 0.07) * noise_mul
        if amp:
            v += (h3(i, j, k, seed) - 0.5) * 2 * amp
        ramp = ramps.get(mat) or ramps['metal']
        n = len(ramp)
        lvl = int(round(clamp(v) * (n - 1)))
        is_glow = glow or mat in glow_mats
        out[key] = (mat, lvl, is_glow)
    return out


# ───────────────────────────── meshing ─────────────────────────────

class VoxelMesh:
    """Result of meshing: elements, palette texels, a Model (for displays/previews) and faces_uv."""

    def __init__(self):
        self.model: Model | None = None
        self.size = 16
        self.texels: list[Texel] = []
        self.faces_uv = {}
        self.boxes = []          # (lo, hi, pal_index, faces, glow)
        self.elements_json = []


def mesh(name, shaded: dict, ramps: dict, vs=0.5, origin=(8, 8, 8), glow_cell=2, emission=12):
    vox = shaded
    exposed = {}
    for key in vox:
        i, j, k = key
        if any((i + d[0], j + d[1], k + d[2]) not in vox for d in DIRS):
            exposed[key] = True
    # palette keys
    pal = {}
    pal_info = []
    cell_pts = {}

    def pkey(key):
        mat, lvl, g = vox[key]
        if g:
            c = (key[0] // glow_cell, key[1] // glow_cell, key[2] // glow_cell)
            return (mat, lvl, True, c)
        return (mat, lvl, False, None)

    keyof = {}
    for key in exposed:
        pk = pkey(key)
        keyof[key] = pk
        if pk not in pal:
            pal[pk] = len(pal)
            pal_info.append(pk)
        if pk[2]:
            cell_pts.setdefault(pk, []).append(key)
    covered = set()
    order = sorted(exposed, key=lambda q: (q[1], q[2], q[0]))
    boxes = []

    def ok(q, pk):
        if q not in vox:
            return False
        if q in exposed:
            return q not in covered and keyof[q] == pk
        return True

    def grow(start, pk, axes):
        lo = list(start)
        hi = list(start)
        for ax in axes:
            while True:
                nh = list(hi)
                nh[ax] += 1
                rng = [range(lo[a], (nh[a] if a == ax else hi[a]) + 1) if a != ax else [nh[ax]] for a in range(3)]
                good = True
                for x in rng[0]:
                    for y in rng[1]:
                        for z in rng[2]:
                            if not ok((x, y, z), pk):
                                good = False
                                break
                        if not good:
                            break
                    if not good:
                        break
                if not good:
                    break
                hi = nh
            while True:
                nl = list(lo)
                nl[ax] -= 1
                rng = [range(lo[a], hi[a] + 1) if a != ax else [nl[ax]] for a in range(3)]
                good = True
                for x in rng[0]:
                    for y in rng[1]:
                        for z in rng[2]:
                            if not ok((x, y, z), pk):
                                good = False
                                break
                        if not good:
                            break
                    if not good:
                        break
                if not good:
                    break
                lo = nl
        return lo, hi

    AXES = ((1, 0, 2), (0, 1, 2), (2, 1, 0), (1, 2, 0), (0, 2, 1))
    for q in order:
        if q in covered:
            continue
        pk = keyof[q]
        best = None
        for axes in AXES:
            lo, hi = grow(q, pk, axes)
            cnt = 0
            for x in range(lo[0], hi[0] + 1):
                for y in range(lo[1], hi[1] + 1):
                    for z in range(lo[2], hi[2] + 1):
                        if (x, y, z) in exposed:
                            cnt += 1
            if best is None or cnt > best[0]:
                best = (cnt, lo, hi)
        _, lo, hi = best
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1):
                    if (x, y, z) in exposed:
                        covered.add((x, y, z))
        # faces touching air
        faces = []
        for d in DIRS:
            ax = 0 if d[0] else 1 if d[1] else 2
            plane = hi[ax] + 1 if (d[0] + d[1] + d[2]) > 0 else lo[ax] - 1
            o = [a for a in range(3) if a != ax]
            touch = False
            for a in range(lo[o[0]], hi[o[0]] + 1):
                for b in range(lo[o[1]], hi[o[1]] + 1):
                    p = [0, 0, 0]
                    p[ax] = plane
                    p[o[0]] = a
                    p[o[1]] = b
                    if tuple(p) not in vox:
                        touch = True
                        break
                if touch:
                    break
            if touch:
                faces.append(FACE_OF[d])
        boxes.append((tuple(lo), tuple(hi), pal[pk], tuple(faces), pk[2]))

    # palette texture layout: 2×2 texel cell per entry (mip-safe)
    n = len(pal_info)
    S = 16
    while (S // 2) * (S // 2) < n:
        S *= 2
    per_row = S // 2
    res = VoxelMesh()
    res.size = S
    m = Model(name)
    for idx, (lo, hi, pi, faces, g) in enumerate(boxes):
        frm = tuple(origin[a] + (lo[a] - 0.5) * vs for a in range(3))
        to = tuple(origin[a] + (hi[a] + 0.5) * vs for a in range(3))
        e = El(frm, to, 'vox', faces=faces, glow=g, emission=emission if g else 0, shade=not g)
        m.els.append(e)
        px, py = (pi % per_row) * 2, (pi // per_row) * 2
        for f in faces:
            res.faces_uv[(idx, f)] = (px, py, px + 2, py + 2)
    for pi, pk in enumerate(pal_info):
        mat, lvl, g, cell = pk
        ramp = ramps.get(mat) or ramps['metal']
        nlev = len(ramp)
        v = lvl / max(1, nlev - 1)
        if g:
            pts = cell_pts[pk]
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            cz = sum(p[2] for p in pts) / len(pts)
            pos = (origin[0] + cx * vs, origin[1] + cy * vs, origin[2] + cz * vs)
        else:
            pos = (0.0, 0.0, 0.0)
        px, py = (pi % per_row) * 2, (pi // per_row) * 2
        for dy in (0, 1):
            for dx in (0, 1):
                role = mat if mat in ('gem', 'crystal', 'edge') else 'glow'
                res.texels.append(Texel(px + dx, py + dy, ramp, v, role, pos, 'north', _stable_cell_id(cell, mat), g,
                                        255, None, 1, 1, 3, 3))
    res.model = m
    res.boxes = boxes
    return res


def _stable_cell_id(cell, mat):
    if not cell:
        return 0
    return (cell[0] * 73856093 ^ cell[1] * 19349663 ^ cell[2] * 83492791 ^ len(mat) * 2654435761) & 0xFFFF


def frame_fn(vm: VoxelMesh):
    baked = BakedModel(vm.model, vm.size, vm.texels, vm.faces_uv, '')
    return baked.frame


def elements_json(vm: VoxelMesh):
    S = vm.size
    out = []
    for idx, e in enumerate(vm.model.els):
        faces = {}
        for f in e.faces:
            x0, y0, x1, y1 = vm.faces_uv[(idx, f)]
            # sample the centre of the 2×2 cell only
            faces[f] = {'uv': [r4((x0 + 0.5) * 16 / S), r4((y0 + 0.5) * 16 / S), r4((x1 - 0.5) * 16 / S),
                               r4((y1 - 0.5) * 16 / S)], 'texture': '#0'}
        el = {'from': [r4(v) for v in e.frm], 'to': [r4(v) for v in e.to]}
        if not e.shade:
            el['shade'] = False
        if e.emission:
            el['light_emission'] = int(max(0, min(15, e.emission)))
        el['faces'] = faces
        out.append(el)
    return out


def model_json(vm: VoxelMesh, ref):
    m = vm.model
    j = {'textures': {'0': ref, 'particle': ref}, 'gui_light': m.gui_light, 'elements': elements_json(vm)}
    if m.display:
        j['display'] = {k: {kk: [r4(x) for x in vv] for kk, vv in v.items()} for k, v in m.display.items()}
    return j
