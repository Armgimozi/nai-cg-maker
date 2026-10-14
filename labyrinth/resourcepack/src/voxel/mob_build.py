"""Voxel mob parts → shaded, greedily meshed boxes under an element budget, sharing one palette atlas.

Pipeline per mob (called from mobs.build_mob):
  1. every voxel part grid is shaded (core.shade, front-top key light) and meshed (core.mesh) in part px;
  2. fit_budget() lowers colour noise → coarser ramps → bigger glow cells on the largest parts until
     every part ≤ PER_PART elements and the whole mob ≤ its rank budget (old-style parts count too);
  3. Palette merges every part's colours (equal colours share one 2×2 cell; glow cells stay per part
     so the atlas pulse animation flows across the model) and compose() packs the old-style UV atlas
     (if any part still uses it) and the palette cells into one power-of-two texture.
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


def fit_budget(pms: list, budget, fixed=0, per_part=PER_PART):
    """Raise reduction levels until each part ≤ per_part and Σ ≤ budget − fixed.  → list of warnings."""
    warns = []
    for _ in range(64):
        over = [pm for pm in pms if pm.count > per_part and pm.level < MAX_LEVEL]
        if over:
            for pm in over:
                pm.level += 1
                pm.remesh()
            continue
        total = sum(pm.count for pm in pms) + fixed
        if total <= budget:
            break
        cand = [pm for pm in pms if pm.level < MAX_LEVEL]
        if not cand:
            break
        pm = max(cand, key=lambda q: q.count)
        pm.level += 1
        pm.remesh()
    for pm in pms:
        if pm.count > per_part:
            warns.append(f'part {pm.name}: {pm.count} elements > {per_part} even at the coarsest level')
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
