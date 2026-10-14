"""Procedural cuboid-model engine.

Builds Minecraft JSON models out of cuboid elements, packs every face into an
original UV atlas, paints each texel through a material shader and keeps a per-texel
record (3D position, role, ramp, value) so that animation effects can be evaluated in
model space and stay coherent across faces.  All geometry is generated here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image

FACES = ('north', 'south', 'east', 'west', 'up', 'down')
NORMALS = {
    'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0),
    'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0),
}
LIMIT_LO, LIMIT_HI = -16.0, 32.0


# ───────────────────────────── math helpers ─────────────────────────────

def _rx(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y, z = p
    return (x, y * c - z * s, y * s + z * c)


def _ry(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y, z = p
    return (x * c + z * s, y, -x * s + z * c)


def _rz(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y, z = p
    return (x * c - y * s, x * s + y * c, z)


def rot_axis(p, axis, deg, origin):
    q = (p[0] - origin[0], p[1] - origin[1], p[2] - origin[2])
    q = {'x': _rx, 'y': _ry, 'z': _rz}[axis](q, deg)
    return (q[0] + origin[0], q[1] + origin[1], q[2] + origin[2])


def rot_xyz(p, r):
    """Minecraft/JOML rotationXYZ: Z applied first, then Y, then X."""
    p = _rz(p, r[2])
    p = _ry(p, r[1])
    return _rx(p, r[0])


def display_apply(p, tr):
    """Apply an item display transform to a model-space point; result is relative to the slot centre."""
    rot = tr.get('rotation', [0, 0, 0])
    t = tr.get('translation', [0, 0, 0])
    s = tr.get('scale', [1, 1, 1])
    q = ((p[0] - 8) * s[0], (p[1] - 8) * s[1], (p[2] - 8) * s[2])
    q = rot_xyz(q, rot)
    return (q[0] + t[0], q[1] + t[1], q[2] + t[2])


def r4(v):
    v = round(float(v), 4)
    if v == int(v):
        return int(v)
    return v


# ───────────────────────────── elements ─────────────────────────────

@dataclass
class El:
    frm: tuple
    to: tuple
    role: str = 'body'
    mat: str | None = None          # material override (else model default for the role)
    rot: tuple | None = None        # (axis, angle, origin)
    faces: tuple = FACES
    glow: bool = False              # part of the animated effect region
    emission: int = 0               # light_emission 0..15
    shade: bool = True
    tag: str = ''                   # free label for shaders (e.g. 'tip', 'left')
    data: dict = field(default_factory=dict)

    def dims(self):
        return (self.to[0] - self.frm[0], self.to[1] - self.frm[1], self.to[2] - self.frm[2])

    def corners(self):
        (x1, y1, z1), (x2, y2, z2) = self.frm, self.to
        pts = [(x, y, z) for x in (x1, x2) for y in (y1, y2) for z in (z1, z2)]
        if self.rot:
            ax, ang, org = self.rot
            pts = [rot_axis(p, ax, ang, org) for p in pts]
        return pts

    def face_size(self, face):
        dx, dy, dz = self.dims()
        if face in ('north', 'south'):
            return dx, dy
        if face in ('east', 'west'):
            return dz, dy
        return dx, dz

    def texel_pos(self, face, a, b):
        """a,b ∈ [0,1] across the face texture (left→right, top→bottom) → model-space point."""
        (x1, y1, z1), (x2, y2, z2) = self.frm, self.to
        dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
        if face == 'north':
            return (x2 - a * dx, y2 - b * dy, z1)
        if face == 'south':
            return (x1 + a * dx, y2 - b * dy, z2)
        if face == 'east':
            return (x2, y2 - b * dy, z2 - a * dz)
        if face == 'west':
            return (x1, y2 - b * dy, z1 + a * dz)
        if face == 'up':
            return (x1 + a * dx, y2, z1 + b * dz)
        return (x1 + a * dx, y1, z2 - b * dz)


@dataclass
class Texel:
    x: int
    y: int
    ramp: list
    v: float
    role: str
    pos: tuple
    face: str
    el: int
    glow: bool
    alpha: int = 255
    color: tuple | None = None   # explicit colour (bypasses ramp)
    i: int = 0                   # local texel coords on its face
    j: int = 0
    w: int = 1
    h: int = 1


@dataclass
class TexCtx:
    el: El
    face: str
    i: int
    j: int
    w: int
    h: int
    pos: tuple
    model: 'Model'

    @property
    def a(self):
        return (self.i + 0.5) / self.w

    @property
    def b(self):
        return (self.j + 0.5) / self.h

    @property
    def border(self):
        return self.i == 0 or self.j == 0 or self.i == self.w - 1 or self.j == self.h - 1


class Model:
    """A cuboid model under construction."""

    def __init__(self, name: str, density: int = 2):
        self.name = name
        self.density = density
        self.els: list[El] = []
        self.display: dict = {}
        self.gui_light = 'side'
        self.meta: dict = {}

    # building helpers -------------------------------------------------
    def box(self, frm, to, role='body', **kw) -> El:
        frm = tuple(float(v) for v in frm)
        to = tuple(float(v) for v in to)
        lo = tuple(min(a, b) for a, b in zip(frm, to))
        hi = tuple(max(a, b) for a, b in zip(frm, to))
        e = El(lo, hi, role, **kw)
        self.els.append(e)
        return e

    def cbox(self, center, size, role='body', **kw) -> El:
        cx, cy, cz = center
        sx, sy, sz = size
        return self.box((cx - sx / 2, cy - sy / 2, cz - sz / 2), (cx + sx / 2, cy + sy / 2, cz + sz / 2), role, **kw)

    def bounds(self):
        pts = [p for e in self.els for p in e.corners()]
        lo = tuple(min(p[i] for p in pts) for i in range(3))
        hi = tuple(max(p[i] for p in pts) for i in range(3))
        return lo, hi

    def transform_all(self, fn):
        """Apply fn(point)->point to every element's from/to and rotation origin (axis-aligned maps only)."""
        for e in self.els:
            a, b = fn(e.frm), fn(e.to)
            e.frm = tuple(min(a[i], b[i]) for i in range(3))
            e.to = tuple(max(a[i], b[i]) for i in range(3))
            if e.rot:
                ax, ang, org = e.rot
                e.rot = (ax, ang, fn(org))

    def fit_into_limits(self, lo=LIMIT_LO + 0.5, hi=LIMIT_HI - 0.5, pivot=(8, 8, 8)):
        """Uniformly shrink around pivot if any corner leaves the legal −16..32 box. Returns the factor."""
        blo, bhi = self.bounds()
        s = 1.0
        for i in range(3):
            if bhi[i] > hi:
                s = min(s, (hi - pivot[i]) / (bhi[i] - pivot[i]))
            if blo[i] < lo:
                s = min(s, (pivot[i] - lo) / (pivot[i] - blo[i]))
        if s < 1.0:
            self.transform_all(lambda p: tuple(pivot[i] + (p[i] - pivot[i]) * s for i in range(3)))
        return s

    # baking ---------------------------------------------------------------
    def bake(self, shader, texture_ref: str):
        """Pack faces, paint texels through shader(ctx)->Texel-like tuple and return a BakedModel."""
        d = self.density
        rects = []  # (h, w, el_idx, face)
        for idx, e in enumerate(self.els):
            for f in e.faces:
                fu, fv = e.face_size(f)
                w = max(1, int(round(fu * d)))
                h = max(1, int(round(fv * d)))
                rects.append((h, w, idx, f))
        size, placed = _pack(rects)
        texels: list[Texel] = []
        faces_uv = {}
        for (x, y, w, h, idx, f) in placed:
            e = self.els[idx]
            faces_uv[(idx, f)] = (x, y, x + w, y + h)
            for j in range(h):
                for i in range(w):
                    pos = e.texel_pos(f, (i + 0.5) / w, (j + 0.5) / h)
                    ctx = TexCtx(e, f, i, j, w, h, pos, self)
                    res = shader(ctx)
                    if res is None:
                        continue
                    ramp, v, color, alpha = res
                    texels.append(Texel(x + i, y + j, ramp, v, e.role, pos, f, idx, e.glow, alpha, color, i, j, w, h))
        return BakedModel(self, size, texels, faces_uv, texture_ref)


def _pack(rects):
    """Shelf packer → (atlas_size, [(x, y, w, h, el_idx, face)]). Atlas is a power-of-two square."""
    rects = sorted(rects, key=lambda r: (-r[0], -r[1], r[2], r[3]))
    area = sum(r[0] * r[1] for r in rects)
    size = 16
    while size * size < area * 1.15 or size < max(max(r[0], r[1]) for r in rects):
        size *= 2
    while True:
        placed = []
        x = y = shelf = 0
        ok = True
        for (h, w, idx, f) in rects:
            if x + w > size:
                y += shelf
                x = shelf = 0
            if y + h > size or w > size:
                ok = False
                break
            placed.append((x, y, w, h, idx, f))
            x += w
            shelf = max(shelf, h)
        if ok:
            return size, placed
        size *= 2


def value_to_color(ramp, v):
    n = len(ramp)
    k = int(round(max(0.0, min(1.0, v)) * (n - 1)))
    return ramp[k]


class BakedModel:
    def __init__(self, model: Model, size: int, texels, faces_uv, texture_ref):
        self.model = model
        self.size = size
        self.texels = texels
        self.faces_uv = faces_uv
        self.texture_ref = texture_ref

    def frame(self, vfn=None) -> Image.Image:
        """Render one atlas frame. vfn(texel) may return (color|None, value_delta) overrides."""
        img = Image.new('RGBA', (self.size, self.size), (0, 0, 0, 0))
        px = img.load()
        for t in self.texels:
            color, dv, alpha = t.color, 0.0, t.alpha
            if vfn is not None:
                r = vfn(t)
                if r is not None:
                    oc, dv = r[0], r[1]
                    if oc is not None:
                        color = oc
                    if len(r) > 2 and r[2] is not None:
                        alpha = r[2]
            if color is None:
                color = value_to_color(t.ramp, t.v + dv)
            elif dv:
                # explicit colours brighten/darken toward white/black
                from .util import lighten, darken
                color = lighten(color, min(0.9, dv)) if dv > 0 else darken(color, min(0.9, -dv))
            px[t.x, t.y] = (color[0], color[1], color[2], alpha)
        return img

    def elements_json(self):
        S = self.size
        out = []
        for idx, e in enumerate(self.model.els):
            faces = {}
            for f in e.faces:
                x0, y0, x1, y1 = self.faces_uv[(idx, f)]
                faces[f] = {'uv': [r4(x0 * 16 / S), r4(y0 * 16 / S), r4(x1 * 16 / S), r4(y1 * 16 / S)], 'texture': '#0'}
            el = {'from': [r4(v) for v in e.frm], 'to': [r4(v) for v in e.to]}
            if e.rot:
                ax, ang, org = e.rot
                el['rotation'] = {'angle': r4(ang), 'axis': ax, 'origin': [r4(v) for v in org]}
            if not e.shade:
                el['shade'] = False
            if e.emission:
                el['light_emission'] = int(max(0, min(15, e.emission)))
            el['faces'] = faces
            out.append(el)
        return out

    def model_json(self):
        m = self.model
        j = {
            'textures': {'0': self.texture_ref, 'particle': self.texture_ref},
            'gui_light': m.gui_light,
            'elements': self.elements_json(),
        }
        if m.display:
            j['display'] = {k: {kk: [r4(x) for x in vv] for kk, vv in v.items()} for k, v in m.display.items()}
        return j


# ───────────────────────────── display fitting ─────────────────────────────

def projected_extent(model: Model, rotation, scale=1.0):
    tr = {'rotation': rotation, 'translation': [0, 0, 0], 'scale': [scale] * 3}
    pts = [display_apply(p, tr) for e in model.els for p in e.corners()]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def fit_transform(model: Model, rotation, target=15.0, max_scale=2.5, min_scale=0.1, offset=(0, 0, 0), dims=(0, 1)):
    lo, hi = projected_extent(model, rotation)
    ext = max(hi[i] - lo[i] for i in dims)
    s = max(min_scale, min(max_scale, target / ext if ext > 0 else 1.0))
    cx = [(lo[i] + hi[i]) / 2 * s for i in range(3)]
    t = [-cx[0] + offset[0], -cx[1] + offset[1], -cx[2] * 0 + offset[2]]
    t = [max(-80, min(80, v)) for v in t]
    return {'rotation': list(rotation), 'translation': t, 'scale': [s, s, s]}


def mirror_left(tr):
    """Left-hand JSON values for a right-hand transform (Minecraft negates rot y/z and pos x itself)."""
    r = tr['rotation']
    return {'rotation': [r[0], -r[1], -r[2]], 'translation': list(tr['translation']), 'scale': list(tr['scale'])}
