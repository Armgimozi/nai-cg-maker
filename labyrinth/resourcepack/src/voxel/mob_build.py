"""Voxel mob parts → shaded, greedily meshed boxes under an element budget, sharing one palette atlas.

Pipeline per mob (called from mobs.build_mob):
  1. every voxel part grid is shaded (core.shade, front-top key light) and meshed (core.mesh) in part px;
  2. fit_budget() lowers colour noise → coarser ramps → bigger glow cells on the largest parts until
     every part ≤ PER_PART elements and the whole mob ≤ its rank budget (old-style parts count too);
  3. Palette merges every part's colours (equal colours share one 2×2 cell; glow cells stay per part
     so the atlas pulse animation flows across the model) and compose() packs the old-style UV atlas
     (if any part still uses it) and the palette cells into one power-of-two texture.
Part sets (GDD §14.6 `set`): a design part cut into several display parts (one per leg / wing) is a SetMesh — shaded
on the whole design grid, budget-fitted uncut first (every part keeps the level it has without the cut), then cut by
fit_sets (the set pays any extra: no boxes on the cut faces, its own colour steps, then other parts' noise only).
"""
from __future__ import annotations

import math

from ..model import Texel
from ..util import clamp, h3
from .core import DIRS, GLOW_ALPHA, NOISE, NOISE_PASS2, _norm, mesh
from .palette import MOB_GLOW_MATS, coarse

MOB_LIGHT = _norm((-0.35, 0.8, -0.5))     # key light from the front-top-left of the mob (model −Z = front)
BUDGET = {'normal': 900, 'elite': 1400, 'add': 600, 'summon': 600, 'boss': 3000}
PER_PART = 720
NOISE_STEPS = (1.0, 0.55, 0.3, 0.12, 0.0, 0.0, 0.0)
MAX_LEVEL = len(NOISE_STEPS) - 1
NOISE_ONLY = 4          # levels 1..4 only lower the colour noise; 5 = coarser ramps, 6 = bigger glow cells


_OFFS = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) != (0, 0, 0)]
METAL_SHEEN = frozenset(('iron', 'brass', 'metal', 'orn', 'blade', 'plate'))


def shade_mob(grid, ramps, glow_mats=MOB_GLOW_MATS, noise_mul=1.0, light=MOB_LIGHT, light_amt=0.12, edge=0.07,
              crease=0.035):
    """Creature shading → {key: (mat, level, glow)} (only exposed voxels matter to the mesher).

    Differs from core.shade (items) so big curved bodies stay cheap: the normal is smoothed over the
    26-neighbourhood (curved surfaces get calm, broad light bands instead of a value per staircase
    step), the rim highlight goes only to real convex edges (≤ 12 of 26 neighbours filled), occlusion
    only to real creases (≥ 21), and glow voxels are left unlit so emissive areas merge."""
    vox = grid.vox
    out = {}
    seed = grid.seed
    L = light
    for key, (mat, val, glow, _p) in vox.items():
        i, j, k = key
        if all((i + d[0], j + d[1], k + d[2]) in vox for d in DIRS):
            out[key] = (mat, 0, glow or mat in glow_mats)
            continue
        is_glow = glow or mat in glow_mats
        v = val
        if not is_glow:
            nx = ny = nz = 0
            occ = 0
            for (a, b, c) in _OFFS:
                if (i + a, j + b, k + c) in vox:
                    occ += 1
                else:
                    nx += a
                    ny += b
                    nz += c
            ln = math.sqrt(nx * nx + ny * ny + nz * nz)
            dot = (nx * L[0] + ny * L[1] + nz * L[2]) / ln if ln else 0.0
            v += light_amt * dot
            if occ <= 12:
                v += edge if dot > -0.3 else edge * 0.4
            elif occ >= 21:
                v -= crease * (occ - 20)
            if mat in METAL_SHEEN and (i + j - k) % 9 in (0, 1):
                v += 0.06
        amp = NOISE.get(mat, 0.07) * noise_mul * NOISE_PASS2
        if amp:
            v += (h3(i, j, k, seed) - 0.5) * 2 * amp
        ramp = ramps.get(mat) or ramps['metal']
        out[key] = (mat, int(round(clamp(v) * (len(ramp) - 1))), is_glow)
    return out


def budget_for(rank, boss):
    return BUDGET['boss'] if boss else BUDGET.get(rank or 'normal', BUDGET['normal'])


class PartMesh:
    def __init__(self, name, grid, ramps):
        self.name = name
        self.grid = grid
        self.base_ramps = ramps
        self.level = 0
        self.vm = None
        self.ramps = ramps
        self.remesh()

    def remesh(self):
        lv = self.level
        self.ramps = coarse(self.base_ramps) if lv >= 5 else self.base_ramps
        cell = 8 if lv >= 6 else 4
        lm = getattr(self.grid, 'light_mul', 1.0)
        sh = shade_mob(self.grid, self.ramps, MOB_GLOW_MATS, noise_mul=NOISE_STEPS[lv], light_amt=0.12 * lm,
                       edge=0.07 * lm)
        self.vm = mesh(f'mob/{self.name}', sh, self.ramps, vs=self.grid.vs, origin=(0.0, 0.0, 0.0),
                       glow_cell=cell, emission=12, overlap=True)

    @property
    def count(self):
        return len(self.vm.boxes)

    @property
    def max_part(self):
        return self.count


# ───────────────────────────── part sets (one design cut into several display parts) ─────────────────────────────

class _SubGrid:
    """A subset of a grid's voxels (same vs/seed) — for shading the cut faces of one piece."""

    def __init__(self, grid, keys):
        self.vox = {k: grid.vox[k] for k in keys}
        self.vs = grid.vs
        self.seed = grid.seed
        self.light_mul = getattr(grid, 'light_mul', 1.0)


def _geodesic(kset, seeds):
    """Multi-source geodesic BFS (26-neighbours).  seeds = {key: (start distance, label)} → {key: label}."""
    import heapq
    dist = {k: d for k, (d, _) in seeds.items()}
    lab = {k: li for k, (_, li) in seeds.items()}
    h = [(d, li, k) for k, (d, li) in seeds.items()]
    heapq.heapify(h)
    while h:
        d, li, k = heapq.heappop(h)
        if d > dist.get(k, 1e18) + 1e-12 or lab.get(k) != li:
            continue
        for o in _OFFS:
            q = (k[0] + o[0], k[1] + o[1], k[2] + o[2])
            if q not in kset:
                continue
            nd = d + math.sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2])
            if nd < dist.get(q, 1e18) - 1e-9:
                dist[q] = nd
                lab[q] = li
                heapq.heappush(h, (nd, li, q))
    return lab


def split_labels(keys, seeds_px, vs, joints_px=None):
    """Assign every voxel of a set to one member.  → {key: member index}.

    A left/right pair (joints on both sides) is cut at the plane midway between its joints.  Otherwise:

    Pass 1: geodesic BFS (26-neighbours) from one seed point per member (part px, model axes like the voxel centres
    key·vs) — the foot for legs (feet lie far apart even where the roots crowd together), the joint for wings.  With
    joints, the seeds run along the limb (joint → foot, from a third of the way).  Seed voxels = those within 1.5
    voxels of a seed point (the nearer point wins), or the nearest voxel.
    Pass 2 (joints given): the shared root region — within the joints' radius (+1.5 voxels) around their centroid,
    a hip band or a spider's hub — goes to the nearest joint, so it splits around each limb's root instead of going to
    whichever limb's wave arrives first.
    Voxels no seed reaches go to the nearest point."""
    keys = list(keys)
    kset = set(keys)
    cs = [(j[0] / vs, j[1] / vs, j[2] / vs) for j in seeds_px]
    pair = joints_px if joints_px and len(joints_px) == 2 else seeds_px if len(seeds_px) == 2 else None
    if pair is not None and (pair[0][0] - pair[1][0]) * (seeds_px[0][0] - seeds_px[1][0]) > 0 \
            and abs(pair[0][0] - pair[1][0]) > 1e-3:
        # a left/right pair (two legs, two wings): the mid-plane between the two joints — a straight cut costs the
        # fewest extra boxes and no limb crosses the body's middle
        xm = (pair[0][0] + pair[1][0]) / 2 / vs
        first = 0 if pair[0][0] > pair[1][0] else 1
        return {k: (first if k[0] > xm else 1 - first) for k in keys}

    def d2(k, c):
        return (k[0] - c[0]) ** 2 + (k[1] - c[1]) ** 2 + (k[2] - c[2]) ** 2

    js = [(j[0] / vs, j[1] / vs, j[2] / vs) for j in joints_px] if joints_px and len(joints_px) == len(cs) else None
    seeds = {}
    for li, c in enumerate(cs):
        # along the limb (joint → seed point) from a third of the way down, so a foot cap or claw that is not joined
        # to the limb voxel-by-voxel cannot strand the seed
        pts = [c] if js is None else [tuple(js[li][a] + t * (c[a] - js[li][a]) for a in range(3))
                                      for t in (0.35, 0.5, 0.65, 0.8, 1.0)]
        near = [(k, math.sqrt(d2(k, q))) for q in pts for k in keys if d2(k, q) <= 2.25]
        if not near:
            k = min(keys, key=lambda k: d2(k, c))
            near = [(k, math.sqrt(d2(k, c)))]
        for k, d0 in near:
            if k not in seeds or d0 < seeds[k][0]:
                seeds[k] = (d0, li)
    lab = _geodesic(kset, seeds)
    if js is not None and len(cs) > 1:
        cen = tuple(sum(j[a] for j in js) / len(js) for a in range(3))
        r = max(math.sqrt(d2(j, cen)) for j in js) + 1.5
        for k in keys:
            if d2(k, cen) <= r * r:
                lab[k] = min(range(len(js)), key=lambda i: d2(k, js[i]))
    for k in keys:
        if k not in lab:
            lab[k] = min(range(len(cs)), key=lambda i: d2(k, cs[i]))
    return lab


class _EmptyVM:
    boxes = []
    pal_info = []
    cell_pos = {}


class SetPiece:
    """One member of a SetMesh as the palette / model writer sees it (like a PartMesh)."""

    def __init__(self, name, vm, owner):
        self.name = name
        self.vm = vm
        self.owner = owner

    @property
    def grid(self):
        return self.owner.grid

    @property
    def ramps(self):
        return self.owner.ramps

    @property
    def count(self):
        return len(self.vm.boxes)


class SetMesh:
    """One voxel design (e.g. a whole leg set) cut into several display parts that each rotate about their own joint.

    Shading runs once on the whole design grid, so the standing look is the design's own (no light or rim change at
    the cuts); voxels that the cut exposes (hidden inside the design) are shaded as the piece's own surface.  Every
    piece is meshed on its own.  The set reduces as one unit in fit_budget (count = Σ pieces, max_part = largest);
    over budget, its first step is seal = False: no boxes on the cut faces (they face the neighbouring piece, so they
    only show while the pieces turn apart) — about the element count of the uncut design."""

    def __init__(self, name, grid, ramps, members):
        self.name = name
        self.grid = grid
        self.base_ramps = ramps
        self.members = list(members)        # [(part name, split seed px[, joint px])]
        self.level = 0
        self.vm = None
        self.whole = True                   # meshed uncut (the design's own count) until fit_sets cuts it
        self.seal = True                    # mesh the cut faces (False = no boxes on the cut: saves elements)
        self.ramps = ramps
        self.pieces = []
        self._lab = None
        self._lab_grid = None
        self.remesh()

    def labels(self):
        if self._lab_grid is not self.grid:
            self._lab = split_labels(self.grid.vox.keys(), [m[1] for m in self.members], self.grid.vs,
                                     [m[2] for m in self.members] if all(len(m) > 2 for m in self.members) else None)
            self._lab_grid = self.grid
        return self._lab

    def remesh(self):
        lv = self.level
        self.ramps = coarse(self.base_ramps) if lv >= 5 else self.base_ramps
        cell = 8 if lv >= 6 else 4
        lm = getattr(self.grid, 'light_mul', 1.0)
        kw = dict(noise_mul=NOISE_STEPS[lv], light_amt=0.12 * lm, edge=0.07 * lm)
        sh = shade_mob(self.grid, self.ramps, MOB_GLOW_MATS, **kw)
        self.pieces = []
        if self.whole:
            self.vm = mesh(f'mob/{self.name}', sh, self.ramps, vs=self.grid.vs, origin=(0.0, 0.0, 0.0),
                           glow_cell=cell, emission=12, overlap=True)
            return
        lab = self.labels()
        vox = self.grid.vox
        for li, pname in enumerate(m[0] for m in self.members):
            keys = [k for k in sh if lab[k] == li]
            sub = {k: sh[k] for k in keys}
            solid = None
            if self.seal:
                cut = [k for k in keys
                       if all((k[0] + d[0], k[1] + d[1], k[2] + d[2]) in vox for d in DIRS)
                       and not all((k[0] + d[0], k[1] + d[1], k[2] + d[2]) in sub for d in DIRS)]
                if cut:
                    psh = shade_mob(_SubGrid(self.grid, keys), self.ramps, MOB_GLOW_MATS, **kw)
                    for k in cut:
                        sub[k] = psh[k]
            else:
                solid = {k for k in vox if lab[k] != li}
            vm = mesh(f'mob/{pname}', sub, self.ramps, vs=self.grid.vs, origin=(0.0, 0.0, 0.0),
                      glow_cell=cell, emission=12, overlap=True, solid=solid) if sub else _EmptyVM()
            self.pieces.append(SetPiece(pname, vm, self))

    @property
    def count(self):
        return len(self.vm.boxes) if self.whole else sum(p.count for p in self.pieces)

    @property
    def max_part(self):
        return len(self.vm.boxes) if self.whole else max((p.count for p in self.pieces), default=0)


def fit_sets(pms: list, budget, fixed=0, per_part=PER_PART):
    """After fit_budget ran with every set uncut (so every part keeps the reduction level it has without the cut —
    same look), cut the sets.  Over budget, the sets pay first: no boxes on the cuts, then the sets' own colour steps;
    then the other parts give up colour noise only.  → still over budget?  (mobs.build_mob then re-runs the set's
    design on coarser voxels before the usual fit_budget over every part.)"""
    sets = [pm for pm in pms if isinstance(pm, SetMesh)]
    for pm in sets:
        if pm.whole:
            pm.whole = False
            pm.remesh()

    def total():
        return sum(pm.count for pm in pms) + fixed
    if total() > budget:
        for pm in sets:
            pm.seal = False
            pm.remesh()
    while total() > budget:
        cand = [pm for pm in sets if pm.level < MAX_LEVEL]
        if not cand:
            break
        pm = max(cand, key=lambda q: q.count)
        pm.level += 1
        pm.remesh()
    # still over: the other parts give up colour noise only (levels ≤ NOISE_ONLY — ramps and glow cells stay)
    while total() > budget:
        cand = [pm for pm in pms if pm not in sets and pm.level < NOISE_ONLY]
        if not cand:
            break
        pm = max(cand, key=lambda q: q.count)
        pm.level += 1
        pm.remesh()
    return total() > budget or any(pm.max_part > per_part for pm in pms)


def fit_budget(pms: list, budget, fixed=0, per_part=PER_PART):
    """Raise reduction levels until each part ≤ per_part and Σ ≤ budget − fixed.  → list of warnings.
    (A SetMesh counts as one unit; its largest piece is what the per-part limit sees.)"""
    warns = []
    for _ in range(64):
        over = [pm for pm in pms if pm.max_part > per_part and pm.level < MAX_LEVEL]
        if over:
            for pm in over:
                pm.level += 1
                pm.remesh()
            continue
        total = sum(pm.count for pm in pms) + fixed
        if total <= budget:
            break
        sealed = [pm for pm in pms if getattr(pm, 'seal', False) and not pm.whole]
        if sealed:          # first drop the boxes on set cuts (hidden while standing) before any colour detail
            for pm in sealed:
                pm.seal = False
                pm.remesh()
            continue
        cand = [pm for pm in pms if pm.level < MAX_LEVEL]
        if not cand:
            break
        pm = max(cand, key=lambda q: q.count)
        pm.level += 1
        pm.remesh()
    for pm in pms:
        if pm.max_part > per_part:
            warns.append(f'part {pm.name}: {pm.max_part} elements > {per_part} even at the coarsest level')
    total = sum(pm.count for pm in pms) + fixed
    if total > budget:
        warns.append(f'{total} elements > budget {budget} even at the coarsest level')
    return warns


class Palette:
    """Global palette of 2×2 cells: key → index; entries keep what the atlas frames need."""

    def __init__(self):
        self.index = {}
        self.entries = []    # (colour, ramp, v, glow, pos, mat)

    def add_part(self, pi, pm: PartMesh):
        """→ list mapping the part's local palette index → global index."""
        vm = pm.vm
        out = []
        vs = pm.grid.vs
        for pk in vm.pal_info:
            mat, lvl, g, cell = pk
            ramp = pm.ramps.get(mat) or pm.ramps['metal']
            col = tuple(ramp[min(lvl, len(ramp) - 1)])
            if g:
                key = ('g', pi, mat, lvl, cell)
                cp = vm.cell_pos.get(pk, (0, 0, 0))
                pos = (cp[0] * vs, cp[1] * vs, cp[2] * vs)
            else:
                key = ('c', col)
                pos = (0.0, 0.0, 0.0)
            idx = self.index.get(key)
            if idx is None:
                idx = len(self.entries)
                self.index[key] = idx
                self.entries.append((col, ramp, lvl / max(1, len(ramp) - 1), g, pos, mat))
            out.append(idx)
        return out


def compose(old_size, n_cells):
    """Atlas size S and the (x, y) of every 2×2 palette cell; the old UV atlas (old_size², may be 0) sits at
    the top-left corner untouched."""
    S = max(16, old_size)
    while True:
        cells = []
        for y in range(0, S, 2):
            for x in range(0, S, 2):
                if old_size and x < old_size and y < old_size:
                    continue
                cells.append((x, y))
                if len(cells) >= n_cells:
                    return S, cells
        if n_cells == 0:
            return S, []
        S *= 2


def palette_texels(pal: Palette, cells):
    out = []
    for idx, (col, ramp, v, g, pos, mat) in enumerate(pal.entries):
        x, y = cells[idx]
        role = 'glow' if g else 'vox'
        for dy in (0, 1):
            for dx in (0, 1):
                out.append(Texel(x + dx, y + dy, ramp, v, role, pos, 'north', idx, g,
                                 GLOW_ALPHA if g else 255, None if g else col, 1, 1, 3, 3))
    return out
