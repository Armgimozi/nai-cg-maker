"""3D shoulder / back armour pieces worn over the equipment layer (labyrinth:armor_piece/<set>/<part>).

Vanilla clients cannot change armour geometry, so the plugin (kr.labyrinth.items.ArmorCosmetics) seats three
ItemDisplays on every player wearing a labyrinth chest piece: shoulder_l, shoulder_r and back.  All designs
are original voxel art styled by the set's `look` (heavy | light | cloth), colours (chest palette) and theme.

Model contract (ArmorPieceLayout.java — the plugin side reads nothing from here):
  * pivot (8, 8, 8) = the part's anchor on the body, 1 model unit = 1 player-skin pixel (Java scales by 0.9375),
    display.fixed = identity.
  * ItemDisplay turns the model 180° about Y → model −Z = the wearer's front, model −X = the wearer's left.
  * anchors (skin px from the feet, standing): shoulders = arm pivot height y 22 at the arm centre x ±6,
    back = top centre of the torso (neck) y 24, z 0 — the torso's back armour surface is 3 px behind it.

Designs are painted in the wearer's local frame (px relative to the anchor, +x = left, +y = up, +z = front;
1 voxel = 0.5 px) and flipped onto the model axes at the end.  Shoulders are authored as the LEFT piece
(outward = +x); the right piece is its mirror image.  Geometry that would sit inside the vanilla armour boxes
(chest/arm armour = skin boxes inflated by 1 px) is invisible anyway; a clearance rule keeps voxels out of
the head's space so turning the head never pushes through a pauldron or hood.
"""
from __future__ import annotations

import math
import re

from .materials import RARITY_LEVEL, Look, norm_style
from .model import fit_transform
from .util import stable_seed
from .voxel import weapons as W
from .voxel.core import Grid, catmull, frame_fn, mesh, model_json
from .voxel.palette import GLOW_MATS, ramps_for

NS = 'labyrinth'
PARTS = ('shoulder_l', 'shoulder_r', 'back')
LOOKS = ('heavy', 'light', 'cloth')
VS = 0.5                          # 1 voxel = half a skin pixel (same density as the helmets)
ORIGIN = (8.25, 8.25, 8.25)       # voxel 0 spans 8.0..8.5 → voxel faces land on the skin-pixel grid
PIXEL = 0.9375                    # Java Transformation scale (ArmorPieceLayout.PIXEL)
SHOULDER_ANCHOR = (6.0, 22.0, 0.0)    # skin px from the feet (left shoulder; right = mirrored x)
BACK_ANCHOR = (0.0, 24.0, 0.0)
BUDGET = {'shoulder_l': 170, 'shoulder_r': 170, 'back': 210}   # target: above it the top-face highlight is dropped
ELEMENT_LIMIT = 280               # hard cap per piece (validate.py) — three pieces ride every armoured player


def model_ref(set_id: str, part: str) -> str:
    return f'{NS}:armor_piece/{set_id}/{part}'


def set_specs(items: dict, sets: dict) -> dict:
    """items.yml → {set id: spec} for every set that has a CHEST piece (the plugin seats pieces from the chest slot).
    spec = dict(iid, kind, look, theme, level, name): colours/theme/rarity come from the chest item, like the
    equipment layer (generate.build_equipment)."""
    out = {}
    for iid, it in items.items():
        sid = (it or {}).get('armor_set')
        if not sid or it.get('armor_slot') != 'chest' or sid in out:
            continue
        tex = it.get('texture') or {}
        sd = sets.get(sid) or {}
        out[sid] = dict(iid=iid, kind=sd.get('look') or 'heavy',
                        look=Look(tex.get('palette'), tex.get('style'), it.get('rarity'), stable_seed('set', sid)),
                        theme=W.theme_of(iid, norm_style(tex.get('style'))),
                        level=RARITY_LEVEL.get(it.get('rarity') or 'common', 0), name=sd.get('name', sid))
    return dict(sorted(out.items()))


# ───────────────────────────── local-frame painter ─────────────────────────────

class Paint:
    """Voxel painter in the wearer's local frame: px relative to the anchor, +x left, +y up, +z front.
    Voxel (i, j, k) covers [i/2, i/2 + ½) × [j/2, …) × [k/2, …) px."""

    def __init__(self, seed: int, anchor):
        self.g = Grid(seed)
        self.anchor = anchor          # world skin-px of the pivot (for the head clearance rule)
        self.side = 1                 # mirroring is done on the finished grid

    @staticmethod
    def vi(v):
        return math.floor(v * 2)

    def cells(self, lo, hi):
        """Voxel centres (px) inside the box lo..hi."""
        for i in range(math.floor(lo[0] * 2), math.ceil(hi[0] * 2)):
            x = (i + 0.5) / 2
            if x < lo[0] or x > hi[0]:
                continue
            for j in range(math.floor(lo[1] * 2), math.ceil(hi[1] * 2)):
                y = (j + 0.5) / 2
                if y < lo[1] or y > hi[1]:
                    continue
                for k in range(math.floor(lo[2] * 2), math.ceil(hi[2] * 2)):
                    z = (k + 0.5) / 2
                    if lo[2] <= z <= hi[2]:
                        yield x, y, z

    def clear_of_head(self, x, y, z):
        """The head (8×8×8 above the neck, turning up to ~50° each way) must stay free."""
        wx, wy, wz = x + self.anchor[0], y + self.anchor[1], z + self.anchor[2]
        if abs(wx) < 4.4 and wy > 25.4 and wz > -4.6:
            return False
        if abs(wx) < 4.4 and wy > 24.6 and abs(wz) < 4.4:
            return False
        return True

    def put(self, x, y, z, mat, val=0.5, glow=False, prio=1):
        if not self.clear_of_head(x, y, z):
            return
        self.g.put(self.vi(x), self.vi(y), self.vi(z), mat, val, glow, prio)

    def fill(self, lo, hi, fn, prio=1):
        """fn(x, y, z) → None | (mat, val) | (mat, val, glow) for every voxel centre in the box."""
        for (x, y, z) in self.cells(lo, hi):
            r = fn(x, y, z)
            if r is None:
                continue
            self.put(x, y, z, r[0], r[1], r[2] if len(r) > 2 else False, prio)

    # voxel-unit brushes from voxel/core + voxel/weapons work directly on self.g (coordinates × 2)
    @staticmethod
    def v(p):
        return (p[0] * 2 - 0.5, p[1] * 2 - 0.5, p[2] * 2 - 0.5)

    def to_model(self, mirror=False) -> Grid:
        """Local voxels → model voxels: model x/z point the other way (ItemDisplay 180° about Y)."""
        out = Grid(self.g.seed)
        for (i, j, k), v in self.g.vox.items():
            if mirror:
                i = -i - 1
            out.vox[(-i - 1, j, -k - 1)] = list(v)
        return out


def _ell(x, y, z, c, r):
    return ((x - c[0]) / r[0]) ** 2 + ((y - c[1]) / r[1]) ** 2 + ((z - c[2]) / r[2]) ** 2


def _ell_top(x, z, c, r):
    """Height of an ellipsoid's upper surface over (x, z), or None outside it."""
    q = 1 - ((x - c[0]) / r[0]) ** 2 - ((z - c[2]) / r[2]) ** 2
    return None if q < 0 else c[1] + r[1] * math.sqrt(q)


def _trim_mat(p):
    return 'orn' if p.lv >= 1 else 'metal'


def _gear_disc(pt: Paint, c, R, teeth, normal='x', mat='orn', glow=False):
    """Flat cog in the plane perpendicular to `normal` ('x' → zy plane, 'z' → xy plane), 0.5 px thick."""
    for u in range(-int(R * 2) - 2, int(R * 2) + 3):
        for v in range(-int(R * 2) - 2, int(R * 2) + 3):
            a, b = u / 2, v / 2
            d = math.hypot(a, b)
            ang = math.atan2(b, a)
            inner = d <= R - 0.6 and not d < R * 0.3
            spoke_gap = R >= 2.5 and R * 0.38 < d < R - 1.2 and not any(
                abs(((ang - s * math.pi / 2) + math.pi) % (2 * math.pi) - math.pi) < 0.32 for s in range(4))
            tooth = R - 0.6 < d <= R + 0.5 and ((ang * teeth / (2 * math.pi)) % 1.0) < 0.5
            if (inner and not spoke_gap) or tooth:
                val = 0.45 + 0.25 * min(1.0, d / R)
                if normal == 'x':
                    pt.put(c[0], c[1] + b, c[2] + a, mat, val, glow, prio=3)
                else:
                    pt.put(c[0] + a, c[1] + b, c[2], mat, val, glow, prio=3)


# ───────────────────────────── shoulders (authored as the LEFT piece, outward = +x) ─────────────────────────────

def heavy_shoulder(pt: Paint, p):
    """Big layered pauldron: domed cap reaching 2.5 px past the arm armour, 2–3 lames down the outer arm."""
    lv, th = p.lv, p.theme
    c, r = (1.0, 1.0, 0.0), (4.9, 3.4, 4.7)
    trim = _trim_mat(p)

    def dome(x, y, z):
        if y < -0.9 or _ell(x, y, z, c, r) > 1.0:
            return None
        if y < -0.3:
            return (trim, 0.6)
        e = _ell(x, y, z, c, r)
        flute = 0.08 if (th == 'water' and int((z + 9) * 1.5) % 2 == 0) else 0.0
        band = 0.1 if 0.55 < e and y > c[1] + 1.4 else 0.0          # polished crown
        return ('plate', 0.34 + band + flute)

    pt.fill((c[0] - r[0], -0.9, -r[2]), (c[0] + r[0], c[1] + r[1], r[2]), dome)
    # lames: curved bands on the outer side only (x ≥ 3.1 — outside the swinging arm), each tucked under the last
    n = 3 if lv >= 2 else 2
    for k in range(n):
        top = -0.8 - 1.9 * k
        rx, rz = 4.5 - 0.3 * k, 4.1 - 0.3 * k

        def lame(x, y, z, top=top, rx=rx, rz=rz):
            if not (top - 2.1 <= y <= top) or x < 3.1:
                return None
            e = (x / rx) ** 2 + (z / rz) ** 2
            if e > 1.0 or e < 0.62:
                return None
            if y < top - 1.6:
                return (trim if lv >= 1 else 'plate', 0.58)
            return ('plate', 0.36 - 0.04 * k)

        pt.fill((3.1, top - 2.1, -rz), (rx, top, rz), lame)
    # rivets around the rim, a ridge over the crown (rare+)
    for a in (-1.1, -0.4, 0.4, 1.1):
        x, z = c[0] + math.cos(a) * r[0] * 0.92, math.sin(a) * r[2] * 0.92
        pt.put(x, 0.1, z, 'orn' if lv >= 1 else 'metal', 0.85, prio=3)
    if lv >= 2:
        for x in [c[0] - 2.5 + 0.5 * s for s in range(13)]:
            y = _ell_top(x, 0, c, r)
            if y is not None:
                pt.put(x, y + 0.25, 0.0, 'orn', 0.72, prio=3)
                pt.put(x, y + 0.25, -0.5, 'orn', 0.6, prio=3)
    # theme dressing
    if th == 'forge':
        for a in (-0.75, 0.0, 0.75) if lv >= 3 else ():
            x0, z0 = c[0] + 1.8, math.sin(a) * 2.6
            y0 = _ell_top(x0, z0, c, r) or c[1]
            pt.g.crystal(Paint.v((x0, y0 - 0.4, z0)), (0.9, 0.8, math.sin(a) * 0.6), 2.6 + (a == 0) * 1.2, 0.9,
                         'metal', prio=3)
        if lv >= 2:
            for k in range(n):                      # ember glowing between the lames
                y = -0.8 - 1.9 * k - 0.1
                for z in [-2.0 + 0.5 * s for s in range(9)]:
                    x = math.sqrt(max(0.0, 1 - (z / (4.1 - 0.3 * k)) ** 2)) * (4.5 - 0.3 * k) - 0.2
                    if x >= 3.1:
                        pt.put(x, y, z, 'glow', 0.8, glow=True, prio=4)
        else:
            for z in (-2.5, 2.5):                   # buckled leather strap (worn work armour)
                pt.fill((3.2, -4.5, z - 0.25), (4.8, 1.0, z + 0.25),
                        lambda x, y, z_: ('leather', 0.45) if _ell(x, 0, z_, (0, 0, 0), (4.85, 1, 4.6)) <= 1 else None,
                        prio=2)
    elif th == 'crystal':
        W.crystal_cluster(pt.g, Paint.v((c[0] + 1.0, c[1] + r[1] - 0.8, 0.6)), p, n=4, size=6.0, r=1.4,
                          up=(0.45, 1, 0.1), spread=0.6, glow=lv >= 4)
    elif th == 'clock':
        _gear_disc(pt, (c[0] + r[0] + 0.25, 0.9, 0.0), 2.9, 8, 'x', 'orn', glow=False)
        _gear_disc(pt, (c[0] + r[0] - 0.3, 3.6, 2.2), 1.5, 6, 'x', 'metal')
        if lv >= 4:
            for z in [-3.0 + 0.5 * s for s in range(13)]:
                pt.put(c[0] + math.sqrt(max(0, 1 - (z / r[2]) ** 2)) * r[0] - 0.1, 0.2, z, 'glow', 0.85, glow=True,
                       prio=4)
    elif th == 'water':
        W.shell(pt.g, Paint.v((c[0] + r[0] + 0.2, 1.4, 0.0)), p, R=4.0, turns=2.0, plane='zy')
    if lv >= 3 and th not in ('crystal', 'forge'):
        y0 = _ell_top(c[0] + 1.2, 0, c, r)
        pt.g.crystal(Paint.v((c[0] + 1.2, y0 - 0.3, 0)), (0.5, 1, 0), 3.6, 1.0, 'metal', prio=3)


def light_shoulder(pt: Paint, p):
    """Smaller shoulder guard: quilted leather pad, a metal cap plate, a buckled strap on the outer arm."""
    lv, th = p.lv, p.theme
    c, r = (0.6, 2.1, 0.0), (4.1, 2.3, 4.0)
    plate_c, plate_r = (2.3, 2.5, 0.0), (2.7, 1.9, 2.9)

    def pad(x, y, z):
        if y < 0.3 or _ell(x, y, z, c, r) > 1.0:
            return None
        quilt = 0.08 if (math.floor(x + 9) + math.floor(z + 9)) % 2 == 0 else -0.04
        if y < 0.8:
            return ('leather', 0.36)
        return ('leather', 0.48 + quilt)

    pt.fill((c[0] - r[0], 0.3, -r[2]), (c[0] + r[0], c[1] + r[1], r[2]), pad)
    if lv >= 1 or th not in ('vine',):
        def cap(x, y, z):
            if x < 1.0 or _ell(x, y, z, plate_c, plate_r) > 1.0 or _ell(x, y, z, c, r) < 0.8:
                return None
            edge = _ell(x, y, z, plate_c, plate_r) > 0.78
            return (_trim_mat(p) if edge else 'metal', 0.66 if edge else 0.45)

        pt.fill((1.0, 0.6, -plate_r[2]), (plate_c[0] + plate_r[0] + 0.6, plate_c[1] + plate_r[1] + 0.6, plate_r[2]),
                cap, prio=2)
    # strap + buckle on the outer face of the arm
    pt.fill((3.0, -1.4, -2.6), (3.6, -0.5, 2.6), lambda x, y, z: ('leather', 0.38), prio=2)
    pt.fill((3.4, -1.6, -0.6), (3.9, -0.3, 0.6), lambda x, y, z: ('metal', 0.72 if abs(z) > 0.3 else 0.4), prio=3)
    # theme dressing
    if th == 'web':
        if 'rime' in p.iid:
            for z in (-2.2, 0.0, 2.2):
                pt.g.crystal(Paint.v((c[0] + r[0] - 0.4, 1.0, z)), (1, -0.35, 0), 2.6, 0.75, 'ice', prio=3)
        else:
            for k in range(4):
                a = -0.9 + 0.6 * k
                pts = [Paint.v((c[0] + 0.6, c[1] + r[1] - 0.2, 0)),
                       Paint.v((c[0] + math.cos(a) * r[0] * 0.95, 0.9, math.sin(a) * r[2] * 0.95))]
                pt.g.tube(pts, 0.5, 0.5, 'string', 0.85, prio=3)
    elif th == 'fungi':
        W.fungi(pt.g, Paint.v((c[0] + 1.0, c[1] + r[1] - 0.6, -1.2)), p, size=2.3, up=(0.2, 1, 0))
        W.fungi(pt.g, Paint.v((c[0] + 2.4, c[1] + 0.6, 1.6)), p, size=1.6, up=(0.6, 1, 0.2))
    elif th == 'abyss':
        W.tendrils(pt.g, Paint.v((c[0] + r[0] - 0.8, 1.2, 0)), p, n=3, length=4, spread=4.0, up=-0.9, r0=0.9)
        pt.put(c[0] + 2.6, 3.0, 0.0, 'eye', 0.95, glow=True, prio=5)
        pt.put(c[0] + 2.6, 3.0, 0.5, 'eye', 0.85, glow=True, prio=5)
    elif th == 'ink':
        pts = [Paint.v((c[0] + 0.8, c[1] + 1.4, 1.2)), Paint.v((c[0] + 2.2, c[1] + 4.0, -0.6)),
               Paint.v((c[0] + 3.4, c[1] + 6.2, -3.0))]
        pt.g.tube(catmull(pts, 8), 1.1, 0.5, 'feather', sq=(1, 1, 0.6),
                  vfn=lambda t, d, q: 0.4 + 0.45 * t + 0.1 * (1 - d), prio=3)
        W.drips(pt.g, [Paint.v((c[0] + r[0] - 0.4, 0.6, -1.5)), Paint.v((c[0] + r[0] - 0.4, 0.6, 1.5))], p)
    elif th == 'vine':
        if 'shard' in p.iid:
            pt.g.crystal(Paint.v((c[0] + 1.6, c[1] + r[1] - 0.5, 0.0)), (0.6, 1, 0.15), 4.2, 1.0, 'crystal',
                         glow=lv >= 4, prio=3)
            pt.g.crystal(Paint.v((c[0] + 2.4, c[1] + 0.8, 1.6)), (0.9, 0.7, 0.4), 2.6, 0.8, 'crystal', prio=3)
        elif lv >= 1:
            for (x, y, z) in ((c[0] + 2.2, c[1] + 1.2, -1.4), (c[0] + 3.0, c[1] - 0.2, 1.2)):
                pt.g.ball(Paint.v((x, y, z)), 1.4, 'leaf', sq=(1.2, 0.6, 1.1),
                          vfn=lambda i, j, k, d: 0.38 + 0.4 * (1 - d), prio=3)
    if lv >= 4:
        for z in [-3.0 + 0.5 * s for s in range(13)]:
            y = 0.55
            x = c[0] + math.sqrt(max(0, 1 - (z / r[2]) ** 2)) * r[0] - 0.2
            if x > 0:
                pt.put(x, y, z, 'glow', 0.85, glow=True, prio=4)


def cloth_shoulder(pt: Paint, p):
    """Draped mantle: a soft cap over the shoulder and a pleated drape falling down the outer arm."""
    lv, th = p.lv, p.theme
    c, r = (0.2, 1.0, 0.0), (4.7, 3.0, 4.6)
    trim = 'orn'
    drop = 4.0 + 0.4 * min(lv, 3)

    def cap(x, y, z):
        if y < -0.4 or _ell(x, y, z, c, r) > 1.0:
            return None
        fold = 0.07 * math.sin(z * 1.7 + x * 0.6)
        if y < 0.1:
            return (trim, 0.6) if lv >= 1 else ('cloth', 0.4)
        return ('cloth', 0.5 + fold + 0.12 * (y - c[1]) / r[1])

    pt.fill((c[0] - r[0], -0.4, -r[2]), (c[0] + r[0], c[1] + r[1], r[2]), cap)

    def drape(x, y, z):
        if y > -0.2 or y < -drop or abs(z) > 3.2 + 0.25 * (-y):
            return None
        wave = 0.35 * math.sin(z * 1.9)
        surf = 3.45 + 0.18 * (-y) + wave
        if not (surf - 0.75 <= x <= surf):
            return None
        if y < -drop + 0.55:
            return (trim, 0.66) if lv >= 1 else ('cloth', 0.36)
        return ('cloth', 0.44 + 0.12 * math.sin(z * 1.9 + 0.8))

    pt.fill((2.6, -drop, -4.5), (5.2, -0.2, 4.5), drape)
    if lv >= 2:     # clasp joining the mantle at the front
        pt.fill((-0.6, 0.6, r[2] - 0.6), (0.6, 1.8, r[2] + 0.2),
                lambda x, y, z: ('orn', 0.72 if abs(x) + abs(y - 1.2) < 0.7 else 0.55), prio=3)
        pt.g.gem(Paint.v((0.0, 1.2, r[2] + 0.4)), 1.0, 'gem', glow=lv >= 4)
    # theme dressing
    if th == 'fungi':
        for (x, y, z, s) in ((c[0] + 1.8, c[1] + r[1] - 0.6, -1.6, 1.8), (c[0] + 3.0, c[1] + 0.8, 1.4, 1.3)):
            W.fungi(pt.g, Paint.v((x, y, z)), p, size=s, up=(0.3, 1, 0))
    elif th == 'frost':
        for z in (-2.4, 0.0, 2.4):
            pt.g.crystal(Paint.v((c[0] + 2.0, c[1] + r[1] - 1.0 - abs(z) * 0.3, z)), (0.7, 1, z * 0.12),
                         3.2 if z == 0 else 2.4, 0.8, 'ice', glow=lv >= 4, prio=3)
    elif th == 'ink':
        pts = [Paint.v((c[0] + 3.0, -0.4, -2.0)), Paint.v((c[0] + 3.9, -2.8, -2.6)), Paint.v((c[0] + 3.7, -5.2, -2.2))]
        pt.g.tube(catmull(pts, 6), 0.7, 0.7, 'paper', sq=(0.5, 1, 1.6), vfn=lambda t, d, q: 0.7 - 0.2 * t, prio=3)
    elif th == 'web':
        if 'crypt' in p.iid:
            for z in [-2.4 + 1.2 * s for s in range(5)]:      # mourning tassels on the hem
                y0 = -drop - 0.2
                pt.fill((3.6 + 0.18 * drop - 0.4, y0 - 1.4, z - 0.25), (3.6 + 0.18 * drop + 0.2, y0, z + 0.25),
                        lambda x, y, z_: ('string', 0.6), prio=3)
        elif lv >= 4:
            for (y, z) in ((2.2, -2.0), (1.4, 1.6), (-1.6, -0.8), (-3.0, 1.4)):   # starlight specks
                x = c[0] + (r[0] - 0.4 if y > 0 else 3.5 + 0.18 * (-y))
                pt.put(x, y, z, 'glow', 0.9, glow=True, prio=4)
        else:
            for k in range(3):
                a = -0.8 + 0.8 * k
                pt.g.tube([Paint.v((c[0] + 1.0, c[1] + r[1] - 0.3, 0)),
                           Paint.v((c[0] + math.cos(a) * r[0], 0.4, math.sin(a) * r[2]))], 0.5, 0.5, 'string', 0.85,
                          prio=3)
    if lv >= 4:
        for z in [-3.0 + 0.5 * s for s in range(13)]:
            pt.put(3.5 + 0.18 * drop + 0.35 * math.sin(z * 1.9) + 0.05, -drop + 0.8, z, 'glow', 0.85, glow=True,
                   prio=4)


# ───────────────────────────── back pieces (anchor = neck; back armour surface at z = −3) ─────────────────────────────

def heavy_back(pt: Paint, p):
    """Curved back plate over the armour with a spine ridge, lames, a raised collar and set emblem."""
    lv, th = p.lv, p.theme
    hw, top, bot = 4.7, 0.6, -11.6
    trim = _trim_mat(p)

    def plate(x, y, z):
        if not (bot <= y <= top) or abs(x) > hw:
            return None
        if y < bot + 1.2 and abs(x) > hw - (bot + 1.2 - y) * 1.4:
            return None                                       # rounded lower corners
        back = -4.4 - 0.45 * (1 - (x / hw) ** 2)
        if not (back <= z <= -3.15):
            return None
        if y > top - 0.55 or y < bot + 0.5:
            return (trim, 0.62)
        if abs(x) > hw - 0.55:
            return ('plate', 0.26)
        groove = y < -3.0 and int((y - bot) / 0.5) % 5 == 0
        return ('plate', 0.22 if groove else 0.36)

    pt.fill((-hw, bot, -5.0), (hw, top, -3.1), plate)
    # spine ridge
    pt.fill((-0.5, bot + 0.6, -5.3), (0.5, top - 0.6, -4.4),
            lambda x, y, z: ('metal', 0.62 if x > 0 else 0.5) if z <= -4.4 - 0.45 * (1 - (x / hw) ** 2) + 0.01 else None,
            prio=2)
    # raised collar behind the neck (kept clear of the head)
    pt.fill((-4.2, top - 0.2, -5.4), (4.2, top + 1.8, -4.6),
            lambda x, y, z: (trim, 0.66) if y > top + 1.2 else ('plate', 0.55), prio=2)
    for (x, y) in ((-hw + 1.0, top - 1.2), (hw - 1.0, top - 1.2), (-hw + 1.2, bot + 1.4), (hw - 1.2, bot + 1.4)):
        pt.put(x, y, -4.75, 'orn' if lv >= 1 else 'metal', 0.85, prio=3)
    if lv >= 2:
        cy = -3.0
        for (x, y, z) in pt.cells((-1.6, cy - 1.6, -5.3), (1.6, cy + 1.6, -4.6)):
            if abs(x) + abs(y - cy) <= 1.6:
                pt.put(x, y, z, 'orn', 0.7, prio=3)
        pt.g.gem(Paint.v((0, cy, -5.4)), 1.2, 'gem', glow=lv >= 4)
    # theme dressing
    if th == 'forge':
        if lv >= 2:
            for s in (-1, 1):                               # exhaust vents with glowing throats
                x0 = s * 2.6
                pt.fill((x0 - 0.9, -2.4, -6.4), (x0 + 0.9, 1.4, -4.4),
                        lambda x, y, z, x0=x0: ('metal', 0.52 + 0.1 * (x > x0)) if math.hypot(x - x0, z + 5.4) <= 0.95 else None,
                        prio=3)
                pt.fill((x0 - 0.45, 1.0, -5.85), (x0 + 0.45, 1.45, -4.95), lambda x, y, z: ('glow', 0.9, True), prio=4)
            for y in [-10.5 + 0.5 * s for s in range(14)]:
                pt.put(0.25 * math.sin(y * 2.3), y, -5.35, 'glow', 0.8, glow=True, prio=4)
        else:
            for s in (-1, 1):                               # leather cross straps
                pt.g.tube([Paint.v((s * 4.2, top - 0.3, -4.75)), Paint.v((-s * 4.0, bot + 1.0, -4.75))], 0.55, 0.55,
                          'leather', 0.42, sq=(1, 1, 0.6), prio=2)
    elif th == 'crystal':
        W.crystal_cluster(pt.g, Paint.v((-2.0, -1.0, -5.0)), p, n=4, size=7.0, r=1.5, up=(-0.35, 1, -0.6), spread=0.6,
                          glow=lv >= 4)
        W.crystal_cluster(pt.g, Paint.v((2.6, -6.0, -4.8)), p, n=3, size=4.5, r=1.1, up=(0.5, 0.6, -0.8), spread=0.5)
    elif th == 'clock':
        _gear_disc(pt, (0.0, -4.2, -5.6), 3.6, 10, 'z', 'orn', glow=False)
        _gear_disc(pt, (-2.9, -0.4, -5.3), 1.8, 7, 'z', 'metal')
        _gear_disc(pt, (3.0, -8.4, -5.3), 1.6, 6, 'z', 'metal')
        if lv >= 4:
            pt.g.gem(Paint.v((0.0, -4.2, -6.2)), 1.3, 'glow', glow=True)
    elif th == 'water':
        W.shell(pt.g, Paint.v((0.0, -6.5, -5.0)), p, R=5.0, turns=2.2, plane='xy')


def traveller_back(pt: Paint, p):
    """Starter kit for every class (novice, 공용): rolled bedroll across the shoulders over a small leather satchel."""
    # bedroll: horizontal roll (axis x) resting on the upper back, two straps
    c, R = (0.0, -0.9, -5.0), 1.55

    def roll(x, y, z):
        if abs(x) > 4.6 or math.hypot(y - c[1], z - c[2]) > R:
            return None
        if abs(abs(x) - 2.7) < 0.35:
            return ('leather', 0.3)
        if abs(x) > 4.15:
            return ('cloth', 0.62)                       # rolled ends show the lighter lining
        swirl = 0.08 if int((math.atan2(y - c[1], z - c[2]) + 4) * 2.2) % 2 else 0.0
        return ('cloth', 0.44 + swirl)

    pt.fill((-4.6, c[1] - R, c[2] - R), (4.6, c[1] + R, -3.15), roll)
    # satchel: flat pack below the roll with a flap and buckle
    def bag(x, y, z):
        if not (-8.8 <= y <= -2.6) or abs(x) > 3.0 or not (-5.0 <= z <= -3.15):
            return None
        if y < -8.8 + 0.5 and abs(x) > 2.5:
            return None                                  # rounded bottom corners
        if y > -4.6 and z < -4.5:
            return ('leather', 0.3)                      # flap
        if abs(x) > 2.55:
            return ('leather', 0.36)
        return ('leather', 0.48 + (0.06 if int((y + 9) * 2) % 3 == 0 else 0.0))

    pt.fill((-3.0, -8.8, -5.0), (3.0, -2.6, -3.15), bag)
    pt.fill((-0.5, -5.4, -5.4), (0.5, -4.4, -4.9), lambda x, y, z: ('metal', 0.72 if abs(x) > 0.2 else 0.45), prio=3)
    for s_ in (-1, 1):                                   # strap from the roll down to the satchel
        pt.fill((s_ * 2.7 - 0.3, -2.8, -5.1), (s_ * 2.7 + 0.3, c[1] - R + 0.2, -4.6), lambda x, y, z: ('leather', 0.3),
                prio=2)


def light_back(pt: Paint, p):
    """Quiver slung diagonally across the back: mouth over the right shoulder, arrows and fletching showing."""
    lv, th = p.lv, p.theme
    if 'novice' in p.iid:
        traveller_back(pt, p)
        return
    a, b = (3.6, -10.6, -5.1), (-3.5, 0.8, -5.1)            # bottom (left hip) → mouth (right shoulder)
    R = 1.75
    ax = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    L = math.sqrt(sum(v * v for v in ax))
    u = tuple(v / L for v in ax)

    def quiver(x, y, z):
        q = (x - a[0], y - a[1], z - a[2])
        t = q[0] * u[0] + q[1] * u[1] + q[2] * u[2]
        if t < -0.3 or t > L:
            return None
        rad = math.sqrt(max(0.0, sum(c * c for c in q) - t * t))
        rr = R + (0.25 if t > L - 0.9 else 0.0)
        if rad > rr:
            return None
        f = t / L
        if t > L - 0.9:
            return (_trim_mat(p), 0.68)                     # rim
        if t < 0.3:
            return ('metal', 0.5)                           # cap
        if abs(f - 0.28) < 0.05 or abs(f - 0.72) < 0.05:
            return ('leather', 0.36)                        # binding straps
        stitch = 0.08 if int(t * 2) % 4 == 0 else 0.0
        return ('leather', 0.5 + stitch)

    pt.fill((-6.0, -11.5, -7.2), (5.8, 2.0, -3.2), quiver)
    # arrows: shafts with fletching sticking out of the mouth
    n = 4 if lv < 2 else 5
    for k in range(n):
        off = (k - (n - 1) / 2) * 0.7
        perp = (u[1], -u[0], 0)
        base = (b[0] + perp[0] * off, b[1] + perp[1] * off, b[2] + (0.6 if k % 2 else -0.5))
        tip = (base[0] + u[0] * (2.6 + 0.4 * (k % 2)), base[1] + u[1] * (2.6 + 0.4 * (k % 2)), base[2] - 0.2)
        pt.g.tube([Paint.v(base), Paint.v(tip)], 0.5, 0.5, 'wood', 0.55, prio=3)
        fl = (tip[0] + u[0] * 1.6, tip[1] + u[1] * 1.6, tip[2])
        mat = 'crystal' if ('shard' in p.iid and k % 2 == 0) else 'feather'
        pt.g.tube([Paint.v(tip), Paint.v(fl)], 1.0, 0.6, mat, sq=(1, 1, 0.55),
                  vfn=lambda t, d, q: 0.45 + 0.35 * t + 0.1 * (1 - d), prio=4, glow=(mat == 'crystal' and lv >= 4))
    # theme dressing
    if th == 'fungi':
        for f, s in ((0.42, 1.6), (0.15, 1.2)):
            q = (a[0] + ax[0] * f - 1.2, a[1] + ax[1] * f, a[2] - R)
            W.fungi(pt.g, Paint.v(q), p, size=s, up=(-0.4, 0.3, -1))
    elif th == 'abyss':
        W.tendrils(pt.g, Paint.v((a[0], a[1] + 0.5, a[2])), p, n=3, length=4, spread=3.5, up=-0.8, r0=0.9)
        pt.put(a[0] + ax[0] * 0.5, a[1] + ax[1] * 0.5, a[2] - R - 0.25, 'eye', 0.95, glow=True, prio=5)
    elif th == 'web':
        if 'rime' in p.iid:
            for f in (0.2, 0.5, 0.8):
                q = (a[0] + ax[0] * f, a[1] + ax[1] * f, a[2] - R + 0.2)
                pt.g.crystal(Paint.v(q), (0.3, 0.2, -1), 2.2, 0.7, 'ice', prio=3)
        else:
            q = (a[0] + ax[0] * 0.5, a[1] + ax[1] * 0.5, a[2] - R - 0.2)
            W.web(pt.g, Paint.v(q)[:2], 3.0 * 2, p, z=Paint.v(q)[2])
    elif th == 'ink':
        W.drips(pt.g, [Paint.v((a[0] + 0.4, a[1] + 0.2, a[2] - 0.6)), Paint.v((a[0] - 0.6, a[1] + 1.2, a[2] - 1.0))], p)
    elif th == 'vine' and lv >= 1 and 'shard' not in p.iid:
        for f in (0.3, 0.65):
            q = (a[0] + ax[0] * f - 1.4, a[1] + ax[1] * f, a[2] - 0.8)
            pt.g.ball(Paint.v(q), 1.3, 'leaf', sq=(1.2, 0.7, 1.0), vfn=lambda i, j, k, d: 0.38 + 0.4 * (1 - d), prio=3)
    if lv >= 4:
        for f in (0.28, 0.72):
            q = (a[0] + ax[0] * f, a[1] + ax[1] * f, a[2] - R - 0.1)
            pt.put(q[0], q[1], q[2], 'glow', 0.9, glow=True, prio=4)


def cloth_back(pt: Paint, p):
    """Cape / capelet from the shoulders to the waist with vertical pleats, trimmed hem and a folded hood."""
    lv, th = p.lv, p.theme
    top, bot = 0.7, -11.6
    trim = 'orn'

    def hw(y):
        return 5.6 + 0.5 * (top - y) / (top - bot)

    def cape(x, y, z):
        if not (bot <= y <= top) or abs(x) > hw(y):
            return None
        if th == 'web' and 'crypt' in p.iid and y < bot + 1.4:   # tattered mourning hem
            if (math.floor((x + 9) * 1.3) * 7) % 5 < 2 and y < bot + 0.6 + 0.5 * ((math.floor((x + 9) * 1.3) * 3) % 3):
                return None
        f = (top - y) / (top - bot)
        pleat = 0.42 * (1 + math.sin(x * 1.75))
        back = -3.3 - 1.3 * f - pleat * (0.4 + f)
        if not (back - 0.8 <= z <= back + 0.05):
            return None
        if y < bot + 0.6 or abs(x) > hw(y) - 0.5:
            return (trim, 0.64) if lv >= 1 else ('cloth', 0.36)
        return ('cloth', 0.42 + 0.12 * math.sin(x * 1.75 + 1.2) + 0.08 * (1 - f))

    pt.fill((-6.3, bot, -7.4), (6.3, top, -3.1), cape)
    # folded hood resting on the upper back
    hc, hr = (0.0, -0.4, -5.1), (3.9, 2.6, 2.1)

    def hood(x, y, z):
        e = _ell(x, y, z, hc, hr)
        if e > 1.0 or z > -3.2:
            return None
        if e < 0.55 and y > hc[1]:
            return ('dark', 0.25)
        if y > hc[1] + 1.4 and e > 0.75:
            return (trim if lv >= 2 else 'cloth', 0.62)
        return ('cloth', 0.5 + 0.08 * math.sin(x * 2.1))

    pt.fill((hc[0] - hr[0], hc[1] - hr[1], hc[2] - hr[2]), (hc[0] + hr[0], hc[1] + hr[1], -3.2), hood, prio=2)
    if lv >= 2:     # embroidered emblem in the middle of the cape
        cy = -6.0
        for (x, y, z) in pt.cells((-2.0, cy - 2.0, -7.2), (2.0, cy + 2.0, -3.4)):
            dd = abs(x) + abs(y - cy)
            if 1.2 <= dd <= 2.0 or (dd < 0.6):
                f = (top - y) / (top - bot)
                back = -3.3 - 1.3 * f - 0.42 * (1 + math.sin(x * 1.75)) * (0.4 + f)
                if back - 0.3 <= z <= back + 0.05:
                    pt.put(x, y, z - 0.45, 'orn', 0.72, prio=3)
    # theme dressing
    if th == 'fungi':
        for (x, y, s) in ((-2.4, 0.9, 1.7), (2.2, 0.6, 1.3), (0.4, 1.4, 1.1)):
            W.fungi(pt.g, Paint.v((x, y, -6.2)), p, size=s, up=(0, 1, -0.4))
    elif th == 'ink':
        for x in (-2.6, 2.2):      # ribbon bookmarks hanging from the collar
            pts = [Paint.v((x, 0.0, -6.6)), Paint.v((x + 0.6, -4.0, -6.0)), Paint.v((x - 0.2, -8.5, -6.4))]
            pt.g.tube(catmull(pts, 8), 0.6, 0.6, 'paper', sq=(1.6, 1, 0.5), vfn=lambda t, d, q: 0.72 - 0.25 * t, prio=3)
    elif th == 'frost':
        for x in [-4.5 + 1.5 * s for s in range(7)]:
            pt.g.crystal(Paint.v((x, hc[1] + 1.4 - abs(x) * 0.25, -5.4 - 0.2 * abs(x))), (x * 0.08, 1, -0.5),
                         2.2 + (abs(x) < 1) * 1.2, 0.7, 'ice', glow=lv >= 4, prio=3)
    elif th == 'web' and 'crypt' not in p.iid:
        if lv >= 4:
            for (x, y) in ((-3.0, -2.5), (2.4, -4.0), (-1.2, -8.6), (3.4, -9.4), (-4.0, -7.0), (0.6, -1.8)):
                f = (top - y) / (top - bot)
                back = -3.3 - 1.3 * f - 0.42 * (1 + math.sin(x * 1.75)) * (0.4 + f)
                pt.put(x, y, back - 0.5, 'glow', 0.95, glow=True, prio=4)
        else:
            cy = -6.0
            for k in range(6):
                ang = 2 * math.pi * k / 6 + 0.3
                pts = [(0.0, cy), (math.cos(ang) * 3.4, cy + math.sin(ang) * 3.4)]
                for s in range(8):
                    t = s / 7
                    x = pts[0][0] + (pts[1][0] - pts[0][0]) * t
                    y = pts[0][1] + (pts[1][1] - pts[0][1]) * t
                    f = (top - y) / (top - bot)
                    back = -3.3 - 1.3 * f - 0.42 * (1 + math.sin(x * 1.75)) * (0.4 + f)
                    pt.put(x, y, back - 0.45, 'string', 0.85, prio=3)
    if lv >= 4:
        for x in [-5.5 + 0.5 * s for s in range(23)]:
            y = bot + 1.0
            f = (top - y) / (top - bot)
            back = -3.3 - 1.3 * f - 0.42 * (1 + math.sin(x * 1.75)) * (0.4 + f)
            if (int((x + 9) * 2) % 3) == 0:
                pt.put(x, y, back - 0.45, 'glow', 0.9, glow=True, prio=4)


SHOULDERS = {'heavy': heavy_shoulder, 'light': light_shoulder, 'cloth': cloth_shoulder}
BACKS = {'heavy': heavy_back, 'light': light_back, 'cloth': cloth_back}


# ───────────────────────────── bake ─────────────────────────────

class PieceOut:
    def __init__(self, part, model, faces_uv, frame, model_json, elements):
        self.part = part
        self.model = model
        self.faces_uv = faces_uv
        self.frame = frame
        self.model_json = model_json
        self.elements = elements


def _display(m):
    ident = {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [1, 1, 1]}
    m.display = {'fixed': ident, 'head': dict(ident),
                 'gui': fit_transform(m, (20, 150, 0), target=14.0, max_scale=2.0),
                 'ground': fit_transform(m, (0, 0, 0), target=7.0, max_scale=1.0, offset=(0, 1.5, 0))}


def _shade_flat(grid, ramps, top_lift):
    """Palette level straight from the painted value — no baked light/AO/noise: the game already shades faces
    (top 1.0, sides 0.6–0.8), and flat colours merge into far fewer, larger elements.  Optional `top_lift` brightens
    exposed upper faces a little (terrace edges on domes read like pixel-art highlights)."""
    vox = grid.vox
    out = {}
    for key, (mat, val, glow, _p) in vox.items():
        i, j, k = key
        v = val
        if top_lift and (i, j + 1, k) not in vox and mat not in GLOW_MATS:
            v += top_lift
        ramp = ramps.get(mat) or ramps['metal']
        lvl = int(round(max(0.0, min(1.0, v)) * (len(ramp) - 1)))
        out[key] = (mat, lvl, bool(glow) or mat in GLOW_MATS)
    return out


def _finish(name, grid, look, theme, ref, budget, seed):
    ramps = ramps_for(look, theme)
    for key in list(grid.vox):                      # stay inside the legal −16..32 model box
        for a_ in range(3):
            lo = ORIGIN[a_] + (key[a_] - 0.5) * VS
            hi = ORIGIN[a_] + (key[a_] + 0.5) * VS
            if lo < -15.9 or hi > 31.9:
                grid.vox.pop(key, None)
                break
    vm = None
    for lift in (0.06, 0.0):
        sh = _shade_flat(grid, ramps, lift)
        vm = mesh(name, sh, ramps, vs=VS, origin=ORIGIN, glow_cell=999, emission=12)
        if len(vm.model.els) <= budget:
            break
    _display(vm.model)
    frame = frame_fn(vm)()
    return vm, frame, model_json(vm, ref)


def build_part(set_id: str, part: str, kind: str, look, theme: str, level: int) -> PieceOut:
    kind = kind if kind in LOOKS else 'heavy'
    seed = stable_seed('armor_piece', set_id, 'shoulder' if part != 'back' else 'back')
    p = W.P(f'{set_id}_{part}', level, theme, 1.0, seed, False)
    if part == 'back':
        pt = Paint(seed, BACK_ANCHOR)
        BACKS[kind](pt, p)
        g = pt.to_model()
    else:
        pt = Paint(seed, SHOULDER_ANCHOR)
        SHOULDERS[kind](pt, p)
        g = pt.to_model(mirror=part == 'shoulder_r')
    ref = model_ref(set_id, part)
    vm, frame, mj = _finish(f'{set_id}_{part}', g, look, theme, ref, BUDGET[part], seed)
    return PieceOut(part, vm.model, vm.faces_uv, frame, mj, len(vm.model.els))


def build_set(set_id: str, kind: str, look, theme: str, level: int, jdump, png_bytes):
    """→ (files, pieces).  Paths: items/ + models/ + textures/armor_piece/<set>/<part>."""
    files, pieces = {}, {}
    for part in PARTS:
        out = build_part(set_id, part, kind, look, theme, level)
        base = f'armor_piece/{set_id}/{part}'
        files[f'assets/{NS}/textures/{base}.png'] = png_bytes(out.frame)
        files[f'assets/{NS}/models/{base}.json'] = jdump(out.model_json)
        files[f'assets/{NS}/items/{base}.json'] = jdump({'model': {'type': 'minecraft:model', 'model': f'{NS}:{base}'}})
        pieces[part] = out
    return files, pieces


# ───────────────────────────── plugin layout (the exact numbers ArmorCosmetics uses) ─────────────────────────────

_ROW = re.compile(r'row\(Part\.(\w+), Stance\.(\w+), (-?[\d.]+)f, (-?[\d.]+)f, (-?[\d.]+)f, (-?[\d.]+)f\)')
_PIXEL = re.compile(r'PIXEL\s*=\s*([\d.]+)f')
_PART = re.compile(r'(SHOULDER_L|SHOULDER_R|BACK)\("([a-z_]+)"\)')


def read_java_layout(java_src: str):
    """ArmorPieceLayout.java → {'pixel': s, 'parts': {ENUM: id}, 'rows': {(part_id, stance): (x, y, z, pitch)}}.
    The @layout-table block is the single source of truth for the server transforms."""
    a, b = java_src.find('// @layout-table'), java_src.find('// @layout-end')
    if a < 0 or b < a:
        raise ValueError('ArmorPieceLayout.java: @layout-table block not found')
    parts = dict(_PART.findall(java_src))
    rows = {}
    for (pe, st, x, y, z, pitch) in _ROW.findall(java_src[a:b]):
        rows[(parts.get(pe, pe.lower()), st)] = (float(x), float(y), float(z), float(pitch))
    m = _PIXEL.search(java_src)
    return {'pixel': float(m.group(1)) if m else PIXEL, 'parts': parts, 'rows': rows}


def seat_height(stance: str) -> float:
    return 1.5 if stance == 'SNEAK' else 1.8
