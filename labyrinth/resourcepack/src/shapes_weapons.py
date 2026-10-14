"""3D weapon templates (GDD §14.1).  Original cuboid designs.

Convention: weapons are modelled upright along +Y, blade flat in the XY plane (width = X,
thickness = Z), hand hold point at (8, 1, 8).  Display transforms in displays.py tilt them
into the hand / slot.  Bows: limbs along Y, back of the bow toward −X, string toward +X,
grip at (4.5, 6, 8).
"""
from __future__ import annotations

import math

from .model import Model

HX, HZ = 8.0, 8.0


def _lv(spec):
    return spec['level']


def _floaters(m: Model, spec, ys, xoff=2.9, size=1.3, role='glow'):
    """Floating glowing diamond shards beside the blade (legendary+)."""
    lv = _lv(spec)
    if lv < 4:
        return
    em = 12 if lv >= 5 else 9
    for k, y in enumerate(ys):
        side = -1 if k % 2 == 0 else 1
        cx = HX + side * xoff
        e = m.cbox((cx, y, HZ), (size, size, size), role, glow=True, emission=em, shade=False,
                   rot=('z', 45, (cx, y, HZ)))
        e.tag = 'float'
        # tiny satellite spark
        if lv >= 5:
            sx = cx + side * 1.3
            m.cbox((sx, y + 1.4, HZ), (0.5, 0.5, 0.5), role, glow=True, emission=em, shade=False,
                   rot=('z', 45, (sx, y + 1.4, HZ)))


def _halo(m: Model, cy, r=3.0, n=8, size=0.6, axis_plane='xz'):
    """Ring of tiny glowing cubes (mythic)."""
    for k in range(n):
        a = 2 * math.pi * k / n
        x = HX + math.cos(a) * r
        z = HZ + math.sin(a) * r
        m.cbox((x, cy, z), (size, size, size), 'glow', glow=True, emission=13, shade=False,
               rot=('y', 45, (x, cy, z)))


def _pommel(m, spec, y, w=2.0, h=1.5):
    lv = _lv(spec)
    m.cbox((HX, y, HZ), (w, h, w), 'pommel')
    if lv >= 1:
        m.cbox((HX, y - h / 2 - 0.25, HZ), (w * 0.5, 0.5, w * 0.5), 'pommel')
    if lv >= 2:
        m.cbox((HX, y, HZ), (w * 0.5, h * 0.6, w + 0.3), 'gem', glow=lv >= 4, emission=7 if lv >= 4 else 0)


def _grip(m, y0, y1, w=1.5):
    m.box((HX - w / 2, y0, HZ - w / 2), (HX + w / 2, y1, HZ + w / 2), 'grip')


def _guard(m, spec, y, half=3.5, h=1.25, d=2.0, curl=True):
    lv = _lv(spec)
    m.box((HX - half, y, HZ - d / 2), (HX + half, y + h, HZ + d / 2), 'guard')
    if lv >= 1:
        m.box((HX - 1.25, y - 0.5, HZ - d / 2 - 0.25), (HX + 1.25, y + h + 0.5, HZ + d / 2 + 0.25), 'guard')
    if lv >= 2:
        m.cbox((HX, y + h / 2, HZ), (1.0, 1.0, d + 0.9), 'gem', glow=lv >= 4, emission=8 if lv >= 4 else 0)
    if lv >= 3 and curl:
        for side in (-1, 1):
            x = HX + side * (half + 0.5)
            m.cbox((x, y + h / 2 + 0.6, HZ), (1.0, 2.0, d * 0.75), 'orn',
                   rot=('z', -side * 22.5, (x, y + h / 2, HZ)))
            if lv >= 4:
                m.cbox((x + side * 0.4, y + h / 2 + 2.0, HZ), (0.6, 0.6, 0.6), 'gem', glow=True, emission=10,
                       shade=False)


def _straight_blade(m, spec, y0, length, width, thick=1.0, edge=0.5, fuller=True, tip=True):
    lv = _lv(spec)
    top = y0 + length
    core_half = width / 2 - edge
    m.box((HX - core_half, y0, HZ - thick / 2), (HX + core_half, top, HZ + thick / 2), 'blade', glow=True)
    et = max(0.5, thick / 2)
    m.box((HX - width / 2, y0, HZ - et / 2), (HX - core_half, top - 0.5, HZ + et / 2), 'edge', glow=True)
    m.box((HX + core_half, y0, HZ - et / 2), (HX + width / 2, top - 0.5, HZ + et / 2), 'edge', glow=True)
    if fuller and length > 6:
        fw = 1.5 if lv >= 3 and core_half * 2 >= 1.5 else 0.5
        m.box((HX - fw / 2, y0 + 0.5, HZ - thick / 2 - 0.05), (HX + fw / 2, top - length * 0.28, HZ + thick / 2 + 0.05),
              'fuller', glow=True)
    if tip:
        s = width / math.sqrt(2)
        m.cbox((HX, top, HZ), (s, s, thick * 0.9), 'edge', glow=True, rot=('z', 45, (HX, top, HZ)))
    return top


# ───────────────────────────── swords ─────────────────────────────

def longsword(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    _pommel(m, spec, -2.0)
    _grip(m, -1.25, 3.5)
    _guard(m, spec, 3.5, half=3.5)
    top = _straight_blade(m, spec, 4.75, 13.5 * L, 2.5)
    if lv >= 3:
        # ricasso collar
        m.box((HX - 1.0, 4.75, HZ - 0.65), (HX + 1.0, 6.25, HZ + 0.65), 'orn')
    _floaters(m, spec, [top - 3, top - 8, top - 5.5][: 2 + (lv >= 5)])
    if lv >= 5:
        _halo(m, 5.6, r=2.6, n=8)


def broadsword(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    m.cbox((HX, -2.0, HZ), (2.5, 2.5, 2.5), 'pommel')
    m.cbox((HX, -2.0, HZ), (1.5, 3.1, 1.5), 'pommel')
    if lv >= 2:
        m.cbox((HX, -2.0, HZ), (1.2, 1.2, 2.9), 'gem', glow=lv >= 4, emission=8 if lv >= 4 else 0)
    _grip(m, -0.75, 3.25, 1.75)
    m.box((HX - 3.25, 3.25, HZ - 1.25), (HX + 3.25, 4.75, HZ + 1.25), 'guard')
    m.box((HX - 4.25, 3.5, HZ - 0.75), (HX + 4.25, 4.5, HZ + 0.75), 'guard')
    if lv >= 3:
        for s in (-1, 1):
            m.cbox((HX + s * 4.5, 4.0, HZ), (1.0, 1.0, 1.75), 'orn')
    top = _straight_blade(m, spec, 4.75, 12.0 * L, 3.5, thick=1.0, edge=0.5)
    if lv >= 2:
        m.box((HX - 1.75, 4.75, HZ - 0.6), (HX + 1.75, 6.0, HZ + 0.6), 'guard')
    _floaters(m, spec, [top - 2.5, top - 7.5, top - 5][: 2 + (lv >= 5)], xoff=3.0)
    if lv >= 5:
        _halo(m, 6.4, r=3.0)


def greatsword(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    m.cbox((HX, -5.0, HZ), (2.5, 2.0, 2.5), 'pommel')
    if lv >= 1:
        m.cbox((HX, -6.25, HZ), (1.25, 0.75, 1.25), 'pommel')
    if lv >= 2:
        m.cbox((HX, -5.0, HZ), (1.25, 1.25, 2.9), 'gem', glow=lv >= 4, emission=8 if lv >= 4 else 0)
    _grip(m, -4.0, 4.0, 1.75)
    m.box((HX - 5.0, 4.0, HZ - 1.25), (HX + 5.0, 5.5, HZ + 1.25), 'guard')
    m.box((HX - 1.75, 3.5, HZ - 1.5), (HX + 1.75, 6.0, HZ + 1.5), 'guard')
    if lv >= 2:
        m.cbox((HX, 4.75, HZ), (1.2, 1.2, 3.3), 'gem', glow=lv >= 4, emission=9 if lv >= 4 else 0)
    if lv >= 3:
        for s in (-1, 1):
            x = HX + s * 5.25
            m.cbox((x, 5.6, HZ), (1.25, 2.5, 1.75), 'orn', rot=('z', -s * 22.5, (x, 4.75, HZ)))
    # ricasso (wrapped)
    m.box((HX - 1.25, 5.5, HZ - 0.75), (HX + 1.25, 8.5, HZ + 0.75), 'grip')
    m.box((HX - 2.25, 8.5, HZ - 0.6), (HX + 2.25, 9.25, HZ + 0.6), 'guard')
    length = min(19.5 * L, 30.5 - 9.25)
    top = _straight_blade(m, spec, 9.25, length, 4.0, thick=1.0, edge=0.75)
    _floaters(m, spec, [top - 4, top - 10, top - 7][: 2 + (lv >= 5)], xoff=3.4, size=1.3)
    if lv >= 5:
        _halo(m, 10.0, r=3.4, n=10)


def cleaver(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    m.cbox((HX, -4.0, HZ), (2.25, 1.75, 2.25), 'pommel')
    _grip(m, -3.25, 4.25, 1.75)
    m.box((HX - 2.5, 4.25, HZ - 1.25), (HX + 2.5, 5.5, HZ + 1.25), 'guard')
    top = 5.5 + min(16 * L, 25)
    # spine on −X, wide blade toward +X
    m.box((HX - 1.75, 5.5, HZ - 0.75), (HX - 0.75, top, HZ + 0.75), 'metal', glow=False)
    m.box((HX - 0.75, 5.5, HZ - 0.5), (HX + 3.25, top - 0.5, HZ + 0.5), 'blade', glow=True)
    m.box((HX + 3.25, 7.0, HZ - 0.25), (HX + 4.25, top - 1.5, HZ + 0.25), 'edge', glow=True)
    # angular chopped tip
    m.cbox((HX + 1.5, top - 0.6, HZ), (5.0, 1.0, 0.9), 'blade', glow=True, rot=('z', 22.5, (HX + 1.5, top - 0.6, HZ)))
    m.cbox((HX + 3.6, 6.4, HZ), (1.0, 2.0, 0.5), 'edge', glow=True, rot=('z', -22.5, (HX + 3.6, 6.4, HZ)))
    # hole near the spine top
    m.cbox((HX + 0.4, top - 3.0, HZ), (1.0, 1.0, 1.1), 'dark')
    if lv >= 2:
        for k in range(3 + lv // 2):
            m.cbox((HX - 1.25, 7.0 + k * 2.6, HZ), (0.6, 0.6, 1.7), 'orn')
    if lv >= 3:
        m.box((HX - 0.5, 9.0, HZ - 0.55), (HX + 0.25, top - 4, HZ + 0.55), 'fuller', glow=True)
    _floaters(m, spec, [top - 3, top - 9, top - 6][: 2 + (lv >= 5)], xoff=4.0, size=1.3)
    if lv >= 5:
        _halo(m, 6.5, r=3.2)


def great_axe(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    top = min(20.0 + 6 * L, 29)
    m.cbox((HX, -6.5, HZ), (2.0, 1.5, 2.0), 'pommel')
    m.box((HX - 0.75, -5.75, HZ - 0.75), (HX + 0.75, top, HZ + 0.75), 'shaft')
    _grip(m, -3.0, 3.0, 1.75)
    for y in (top - 9.0, top - 1.5):
        m.box((HX - 1.0, y, HZ - 1.0), (HX + 1.0, y + 0.75, HZ + 1.0), 'metal')
    hy = top - 4.5   # head centre
    m.box((HX - 1.25, hy - 3.0, HZ - 1.0), (HX + 1.25, hy + 3.0, HZ + 1.0), 'metal')
    for s in (-1, 1):
        # stacked crescent bit: neck → widening blade → bright edge
        x0 = HX + s * 1.25
        m.box(*sorted_x(x0, x0 + s * 2.0, hy - 2.0, hy + 2.0), 'blade', glow=True)
        m.box(*sorted_x(x0 + s * 2.0, x0 + s * 3.5, hy - 3.5, hy + 3.5), 'blade', glow=True)
        m.box(*sorted_x(x0 + s * 3.5, x0 + s * 4.25, hy - 4.75, hy + 4.75, dz=0.25), 'edge', glow=True)
        for sy in (-1, 1):
            cx, cy = x0 + s * 3.9, hy + sy * 4.9
            m.cbox((cx, cy, HZ), (0.75, 1.75, 0.5), 'edge', glow=True, rot=('z', s * sy * 30, (cx, cy, HZ)))
        if lv >= 3:
            m.cbox((x0 + s * 1.2, hy, HZ), (0.8, 0.8, 2.2), 'gem', glow=lv >= 4, emission=9 if lv >= 4 else 0)
    # top spike
    m.cbox((HX, top + 0.8, HZ), (1.2, 1.2, 1.2), 'edge', glow=True, rot=('z', 45, (HX, top + 0.8, HZ)))
    if lv >= 2:
        m.box((HX - 0.9, hy + 3.0, HZ - 0.9), (HX + 0.9, hy + 3.75, HZ + 0.9), 'orn')
    _floaters(m, spec, [hy + 6.5, hy - 7.5, hy][: 2 + (lv >= 5)], xoff=5.4, size=1.2)
    if lv >= 5:
        _halo(m, hy, r=4.0, n=10)


def sorted_x(xa, xb, y0, y1, dz=0.5):
    """helper: box tuple (frm, to) spanning xa..xb (any order), y0..y1, thickness 2*dz around HZ."""
    return (min(xa, xb), y0, HZ - dz), (max(xa, xb), y1, HZ + dz)


def mace(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    m.cbox((HX, -2.0, HZ), (2.0, 1.25, 2.0), 'pommel')
    _grip(m, -1.5, 4.0, 1.5)
    top = 4.0 + 8.5 * L
    m.box((HX - 0.6, 4.0, HZ - 0.6), (HX + 0.6, top, HZ + 0.6), 'metal')
    m.box((HX - 1.0, 4.0, HZ - 1.0), (HX + 1.0, 4.75, HZ + 1.0), 'guard')
    hy = top + 2.5
    m.cbox((HX, hy, HZ), (3.0, 4.0, 3.0), 'head', glow=True)
    m.cbox((HX, top - 0.1, HZ), (2.0, 0.8, 2.0), 'guard')
    flange_h = 4.6
    for (dx, dz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if dx:
            m.box((HX + dx * 1.5 if dx > 0 else HX - 3.25, hy - flange_h / 2, HZ - 0.35),
                  (HX + 3.25 if dx > 0 else HX - 1.5, hy + flange_h / 2, HZ + 0.35), 'edge', glow=True)
        else:
            m.box((HX - 0.35, hy - flange_h / 2, HZ + 1.5 if dz > 0 else HZ - 3.25),
                  (HX + 0.35, hy + flange_h / 2, HZ + 3.25 if dz > 0 else HZ - 1.5), 'edge', glow=True)
    m.cbox((HX, hy + 2.6, HZ), (1.2, 1.2, 1.2), 'edge', glow=True, rot=('y', 45, (HX, hy + 2.6, HZ)))
    if lv >= 2:
        m.cbox((HX, hy, HZ), (3.3, 1.0, 3.3), 'orn')
    if lv >= 3:
        for (dx, dz) in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            m.cbox((HX + dx * 1.7, hy, HZ + dz * 1.7), (0.8, 0.8, 0.8), 'gem', glow=lv >= 4, emission=9 if lv >= 4 else 0)
    _floaters(m, spec, [hy + 4.5, hy - 1, hy + 2][: 2 + (lv >= 5)], xoff=4.0)
    if lv >= 5:
        _halo(m, hy, r=4.2, n=10)


# ───────────────────────────── daggers ─────────────────────────────

def dagger(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    m.cbox((HX, -1.5, HZ), (1.5, 1.0, 1.5), 'pommel')
    _grip(m, -1.0, 2.75, 1.25)
    m.box((HX - 2.0, 2.75, HZ - 0.75), (HX + 2.0, 3.75, HZ + 0.75), 'guard')
    if lv >= 2:
        m.cbox((HX, 3.25, HZ), (0.8, 0.8, 1.8), 'gem', glow=lv >= 4, emission=8 if lv >= 4 else 0)
    top = _straight_blade(m, spec, 3.75, 7.5 * L, 2.0, thick=0.75, edge=0.5, fuller=lv >= 1)
    if lv >= 3:
        for s in (-1, 1):
            m.cbox((HX + s * 2.3, 3.6, HZ), (0.75, 1.5, 0.75), 'orn', rot=('z', -s * 30, (HX + s * 2.3, 3.25, HZ)))
    _floaters(m, spec, [top - 1.5, top - 5, top - 3][: 2 + (lv >= 5)], xoff=2.2, size=0.9)
    if lv >= 5:
        _halo(m, 4.2, r=2.0, n=6, size=0.5)


def kris(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    m.cbox((HX, -1.6, HZ), (1.75, 1.25, 1.75), 'pommel')
    _grip(m, -1.0, 2.75, 1.25)
    m.box((HX - 1.75, 2.75, HZ - 1.0), (HX + 2.5, 3.75, HZ + 1.0), 'guard')
    y = 3.75
    seg = 1.5 * L
    n = 6
    for k in range(n):
        off = 0.6 if k % 2 == 0 else -0.6
        w = 2.0 - k * 0.18
        m.box((HX + off - w / 2, y, HZ - 0.375), (HX + off + w / 2, y + seg, HZ + 0.375), 'blade', glow=True)
        m.box((HX + off - 0.25, y, HZ - 0.45), (HX + off + 0.25, y + seg, HZ + 0.45), 'fuller', glow=True)
        y += seg
    m.cbox((HX + 0.6 * (1 if n % 2 == 0 else -1), y, HZ), (1.0, 1.0, 0.7), 'edge', glow=True,
           rot=('z', 45, (HX, y, HZ)))
    if lv >= 3:
        m.cbox((HX + 2.2, 3.25, HZ), (0.8, 0.8, 2.2), 'gem', glow=lv >= 4, emission=8 if lv >= 4 else 0)
    _floaters(m, spec, [y - 1, y - 5, y - 3][: 2 + (lv >= 5)], xoff=2.4, size=0.9)


def fang_blade(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    m.cbox((HX, -1.6, HZ), (1.75, 1.25, 1.75), 'pommel')
    _grip(m, -1.0, 2.75, 1.4)
    m.box((HX - 1.5, 2.75, HZ - 0.9), (HX + 1.5, 3.75, HZ + 0.9), 'guard')
    # curved fang: segments rotated progressively around z, walking along the curve
    x, y = HX, 3.75
    ang = 0.0
    seg = 2.0 * L
    widths = [2.4, 2.2, 1.9, 1.5, 1.1]
    for k, w in enumerate(widths):
        rad = math.radians(ang)
        cx = x - math.sin(rad) * seg / 2
        cy = y + math.cos(rad) * seg / 2
        m.cbox((cx, cy, HZ), (w, seg + 0.4, 0.75), 'blade', glow=True, rot=('z', ang, (cx, cy, HZ)))
        ex = cx + math.cos(rad) * (w / 2) - 0.0
        ey = cy + math.sin(rad) * (w / 2)
        m.cbox((ex, ey, HZ), (0.5, seg + 0.4, 0.5), 'edge', glow=True, rot=('z', ang, (ex, ey, HZ)))
        x = x - math.sin(rad) * seg
        y = y + math.cos(rad) * seg
        ang -= 11.0
    m.cbox((x, y, HZ), (0.8, 0.8, 0.6), 'edge', glow=True, rot=('z', 45 + ang, (x, y, HZ)))
    if lv >= 2:
        m.cbox((HX, 3.25, HZ), (0.8, 0.8, 2.0), 'gem', glow=lv >= 4, emission=8 if lv >= 4 else 0)
    _floaters(m, spec, [y - 1.5, y - 5.5, y - 3.5][: 2 + (lv >= 5)], xoff=1.9, size=0.9)


# ───────────────────────────── staves & scepters ─────────────────────────────

def _shaft(m, spec, y0, y1, w=1.25, metal=False):
    m.box((HX - w / 2, y0, HZ - w / 2), (HX + w / 2, y1, HZ + w / 2), 'metal' if metal else 'shaft')
    m.cbox((HX, y0, HZ), (w + 0.5, 1.0, w + 0.5), 'metal')
    _grip(m, -1.5, 3.0, w + 0.25)
    lv = _lv(spec)
    if lv >= 2:
        for y in (y1 - 0.5, (y0 + y1) / 2 + 2):
            m.cbox((HX, y, HZ), (w + 0.5, 0.75, w + 0.5), 'orn')


def staff_orb(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    top = min(16.5 * L, 19.5)
    _shaft(m, spec, -4.5, top)
    oy = top + 3.2
    r = 2.6 + 0.3 * (lv >= 3)
    # stepped sphere orb
    m.cbox((HX, oy, HZ), (r * 2, r * 1.3, r * 2), 'crystal', glow=True, emission=10 if lv >= 4 else 4, shade=lv < 4)
    m.cbox((HX, oy, HZ), (r * 1.3, r * 2, r * 1.3), 'crystal', glow=True, emission=10 if lv >= 4 else 4, shade=lv < 4)
    m.cbox((HX, oy, HZ), (r * 1.6, r * 1.6, r * 1.6), 'crystal', glow=True, emission=10 if lv >= 4 else 4, shade=lv < 4)
    # claw prongs
    for k, (dx, dz) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
        if dx:
            x = HX + dx * (r + 0.3)
            m.cbox((x, oy - 0.8, HZ), (0.6, 4.0, 0.6), 'metal', rot=('z', dx * 18, (x, top, HZ)))
            m.cbox((HX + dx * (r - 0.2), oy + 1.6, HZ), (0.5, 1.2, 0.5), 'orn', rot=('z', -dx * 30, (HX + dx * (r - 0.2), oy + 1.6, HZ)))
        else:
            z = HZ + dz * (r + 0.3)
            m.cbox((HX, oy - 0.8, z), (0.6, 4.0, 0.6), 'metal', rot=('x', -dz * 18, (HX, top, z)))
            m.cbox((HX, oy + 1.6, HZ + dz * (r - 0.2)), (0.5, 1.2, 0.5), 'orn', rot=('x', dz * 30, (HX, oy + 1.6, HZ + dz * (r - 0.2))))
    m.cbox((HX, top + 0.3, HZ), (2.4, 1.0, 2.4), 'metal')
    if lv >= 3:
        for s in (-1, 1):
            m.cbox((HX + s * 1.0, top - 3.5, HZ), (0.8, 3.0, 0.8), 'orn', rot=('z', -s * 22.5, (HX, top - 2, HZ)))
    if lv >= 4:
        _halo(m, oy, r=r + 2.2, n=8 if lv == 4 else 12, size=0.6)
    if lv >= 5:
        for s in (-1, 1):
            m.cbox((HX + s * 5.0, oy + 2.0, HZ), (0.9, 0.9, 0.9), 'glow', glow=True, emission=13, shade=False,
                   rot=('z', 45, (HX + s * 5.0, oy + 2.0, HZ)))


def staff_crystal(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    top = min(16.0 * L, 19.0)
    _shaft(m, spec, -4.5, top)
    m.cbox((HX, top + 0.3, HZ), (2.6, 1.2, 2.6), 'metal')
    em = 10 if lv >= 4 else 3
    shards = [(0, 0, 0, 2.2, 8.0), (-1.6, 0, -22.5, 1.5, 5.5), (1.6, 0, 22.5, 1.5, 5.0), (0, 1.5, 15, 1.3, 4.4),
              (0, -1.5, -15, 1.3, 4.6)]
    if lv >= 3:
        shards += [(-2.8, 0, -40, 1.1, 3.4), (2.8, 0, 40, 1.1, 3.6)]
    for (dx, dz, ang, w, h) in shards:
        cx, cz = HX + dx, HZ + dz
        cy = top + 0.8 + h / 2
        axis = 'z' if dz == 0 else 'x'
        m.cbox((cx, cy, cz), (w, h, w), 'crystal', glow=True, emission=em, shade=lv < 4,
               rot=(axis, ang if axis == 'z' else -ang, (cx, top + 0.8, cz)))
        tip_y = top + 0.8 + h
        if ang == 0 and dz == 0:
            m.cbox((cx, tip_y, cz), (w * 0.7, w * 0.7, w * 0.7), 'crystal', glow=True, emission=em, shade=lv < 4,
                   rot=('y', 45, (cx, tip_y, cz)))
    for s in (-1, 1):
        m.cbox((HX + s * 1.5, top - 0.4, HZ), (0.6, 2.4, 0.6), 'orn', rot=('z', -s * 30, (HX + s * 1.0, top, HZ)))
    if lv >= 4:
        for k, y in enumerate((top + 3, top + 6.5)):
            s = -1 if k % 2 == 0 else 1
            m.cbox((HX + s * 4.0, y, HZ), (1.0, 1.6, 1.0), 'crystal', glow=True, emission=12, shade=False,
                   rot=('z', s * 20, (HX + s * 4.0, y, HZ)))
    if lv >= 5:
        _halo(m, top + 3.5, r=4.5, n=12, size=0.6)


def staff_ring(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    top = min(15.5 * L, 18.5)
    _shaft(m, spec, -4.5, top)
    cy = top + 4.4
    R = 3.6
    # diamond-oriented square ring (rotated 45° around z)
    for (dx, dy, w, h) in ((0, R, 2 * R + 0.8, 0.8), (0, -R, 2 * R + 0.8, 0.8), (R, 0, 0.8, 2 * R), (-R, 0, 0.8, 2 * R)):
        m.cbox((HX + dx, cy + dy, HZ), (w, h, 0.9), 'metal', rot=('z', 45, (HX, cy, HZ)))
    m.cbox((HX, cy, HZ), (1.6, 1.6, 1.6), 'crystal', glow=True, emission=10 if lv >= 4 else 4, shade=lv < 4,
           rot=('z', 45, (HX, cy, HZ)))
    # dangling charms from the ring sides
    for s in (-1, 1):
        x = HX + s * 3.2
        m.box((x - 0.2, cy - 3.0, HZ - 0.2), (x + 0.2, cy - 0.6, HZ + 0.2), 'chain')
        m.cbox((x, cy - 3.6, HZ), (0.9, 1.2, 0.9), 'gem', glow=lv >= 4, emission=8 if lv >= 4 else 0)
    m.cbox((HX, top + 0.3, HZ), (2.0, 1.0, 2.0), 'orn')
    if lv >= 3:
        m.cbox((HX, cy + R * 1.42 + 0.6, HZ), (0.9, 0.9, 0.9), 'gem', glow=lv >= 4, emission=9,
               rot=('z', 45, (HX, cy + R * 1.42 + 0.6, HZ)))
    if lv >= 4:
        _halo(m, cy, r=5.4, n=10, size=0.55)


def scepter(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    top = 4.0 + 7.5 * L
    m.cbox((HX, -2.0, HZ), (1.8, 1.2, 1.8), 'pommel')
    _grip(m, -1.5, 3.5, 1.4)
    m.box((HX - 0.6, 3.5, HZ - 0.6), (HX + 0.6, top, HZ + 0.6), 'metal')
    for y in (3.5, top - 2.5):
        m.cbox((HX, y, HZ), (1.8, 0.8, 1.8), 'orn')
    m.cbox((HX, top + 0.4, HZ), (2.6, 1.0, 2.6), 'metal')
    gy = top + 2.8
    m.cbox((HX, gy, HZ), (2.4, 2.4, 2.4), 'gem', glow=True, emission=10 if lv >= 4 else 3, shade=lv < 4,
           rot=('y', 45, (HX, gy, HZ)))
    m.cbox((HX, gy, HZ), (1.7, 3.4, 1.7), 'gem', glow=True, emission=10 if lv >= 4 else 3, shade=lv < 4,
           rot=('y', 45, (HX, gy, HZ)))
    for (dx, dz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if dx:
            m.cbox((HX + dx * 1.6, gy - 0.4, HZ), (0.5, 2.6, 0.5), 'orn', rot=('z', dx * 15, (HX + dx * 1.6, top, HZ)))
        else:
            m.cbox((HX, gy - 0.4, HZ + dz * 1.6), (0.5, 2.6, 0.5), 'orn', rot=('x', -dz * 15, (HX, top, HZ + dz * 1.6)))
    if lv >= 4:
        _halo(m, gy, r=3.2, n=8, size=0.5)
    if lv >= 5:
        _floaters(m, spec, [gy + 3.0, gy - 1.0], xoff=3.4, size=0.9)


def sun_scepter(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    top = 4.0 + 8.0 * L
    m.cbox((HX, -2.0, HZ), (1.8, 1.2, 1.8), 'pommel')
    _grip(m, -1.5, 3.5, 1.4)
    m.box((HX - 0.6, 3.5, HZ - 0.6), (HX + 0.6, top, HZ + 0.6), 'metal')
    m.cbox((HX, top, HZ), (2.2, 1.0, 2.2), 'orn')
    cy = top + 3.6
    R = 2.6
    n = 8
    for k in range(n):
        ang = 360.0 * k / n
        rad = math.radians(ang)
        cx, cyy = HX + math.cos(rad) * R, cy + math.sin(rad) * R
        m.cbox((cx, cyy, HZ), (0.8, 2.2, 0.8), 'metal', rot=('z', ang + 90, (cx, cyy, HZ)))
    rays = 8 if lv < 3 else 12
    for k in range(rays):
        ang = 360.0 * k / rays + 22.5 / 2
        rad = math.radians(ang)
        ln = 1.6 if k % 2 else 2.4
        rr = R + 0.6 + ln / 2
        cx, cyy = HX + math.cos(rad) * rr, cy + math.sin(rad) * rr
        if ang % 360 > 200 and ang % 360 < 340:
            continue  # leave the lower arc open toward the shaft
        m.cbox((cx, cyy, HZ), (0.6, ln, 0.5), 'glow' if lv >= 4 else 'orn', glow=True,
               emission=11 if lv >= 4 else 0, shade=lv < 4, rot=('z', ang - 90, (cx, cyy, HZ)))
    m.cbox((HX, cy, HZ), (1.8, 1.8, 1.2), 'gem', glow=True, emission=11 if lv >= 4 else 4, shade=lv < 4,
           rot=('z', 45, (HX, cy, HZ)))
    if lv >= 5:
        _halo(m, cy, r=5.5, n=12, size=0.5)


def censer_staff(m: Model, spec):
    L, lv = spec['length'], _lv(spec)
    top = min(15.5 * L, 18.5)
    _shaft(m, spec, -4.5, top)
    # crook hook bending toward +X
    m.box((HX - 0.6, top, HZ - 0.6), (HX + 0.6, top + 2.5, HZ + 0.6), 'metal')
    m.box((HX - 0.6, top + 2.5, HZ - 0.6), (HX + 4.0, top + 3.5, HZ + 0.6), 'metal')
    m.box((HX + 3.0, top + 0.6, HZ - 0.5), (HX + 4.0, top + 2.5, HZ + 0.5), 'metal')
    # chain + censer
    cx = HX + 3.5
    for k in range(3):
        y = top + 0.2 - k * 1.2
        m.cbox((cx, y, HZ), (0.5, 0.9, 0.5) if k % 2 == 0 else (0.9, 0.5, 0.5), 'chain')
    py = top - 5.0
    m.cbox((cx, py, HZ), (2.8, 2.6, 2.8), 'metal')
    m.cbox((cx, py + 1.6, HZ), (2.0, 0.8, 2.0), 'orn')
    m.cbox((cx, py + 2.3, HZ), (0.9, 0.9, 0.9), 'orn', rot=('y', 45, (cx, py + 2.3, HZ)))
    # glowing vents on all four sides
    for (dx, dz) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        m.cbox((cx + dx * 1.45, py, HZ + dz * 1.45), (0.8 if dz else 0.2, 1.2, 0.8 if dx else 0.2), 'glow',
               glow=True, emission=12, shade=False)
    m.cbox((cx, py - 1.6, HZ), (1.6, 0.6, 1.6), 'metal')
    if lv >= 3:
        m.cbox((HX + 2.0, top + 4.2, HZ), (0.9, 0.9, 0.9), 'gem', glow=lv >= 4, emission=9,
               rot=('z', 45, (HX + 2.0, top + 4.2, HZ)))
    if lv >= 4:
        for k in range(3):
            m.cbox((cx + (k - 1) * 0.9, py + 3.4 + k * 1.1, HZ), (0.5, 0.5, 0.5), 'glow', glow=True, emission=12,
                   shade=False, rot=('z', 45, (cx + (k - 1) * 0.9, py + 3.4 + k * 1.1, HZ)))


# ───────────────────────────── bows ─────────────────────────────

BOW_GX, BOW_GY = 4.5, 6.0


def _limb_path(kind, pull):
    """Return list of (angle_deg_from_vertical, seg_len) for the upper limb (lower = mirror)."""
    bend = 1.0 + pull * 0.35
    if kind == 'longbow':
        return [(-8 * bend, 2.6), (-16 * bend, 2.6), (-25 * bend, 2.6)]
    if kind == 'recurve_bow':
        return [(-12 * bend, 2.4), (-30 * bend, 2.2), (-10 * bend, 1.6), (25, 1.4)]
    return [(-10 * bend, 2.2), (-24 * bend, 2.4), (-38 * bend, 2.0)]


def bow(m: Model, spec, kind, pull=-1):
    """pull = -1 (resting) or 0..2 pulling stage."""
    lv = _lv(spec)
    L = spec['length']
    p = max(0, pull + 1) / 3.0 if pull >= 0 else 0.0
    gx, gy = BOW_GX, BOW_GY
    thick = 1.0 if kind != 'composite_bow' else 1.25
    # grip
    m.box((gx - 0.9, gy - 1.75, HZ - 0.9), (gx + 0.9, gy + 1.75, HZ + 0.9), 'grip')
    tips = []
    for sgn in (1, -1):  # upper, lower
        x, y = gx, gy + sgn * 1.75
        for k, (ang, ln) in enumerate(_limb_path(kind, p)):
            ln *= L
            a = ang * sgn
            rad = math.radians(a)
            # walk direction for upper: (−sin a, cos a); lower mirrored in y
            dx, dy = -math.sin(rad) * sgn, math.cos(rad) * sgn
            cx, cy = x + dx * ln / 2, y + dy * ln / 2
            w = thick - k * 0.15
            m.cbox((cx, cy, HZ), (w, ln + 0.3, w * 0.8), 'limb', glow=True, rot=('z', a, (cx, cy, HZ)))
            if kind == 'composite_bow' and k < 2:
                m.cbox((cx - 0.55, cy, HZ), (0.5, ln * 0.8, w * 0.9), 'orn', rot=('z', a, (cx, cy, HZ)))
            x, y = x + dx * ln, y + dy * ln
        tips.append((x, y))
        # tip ornament
        m.cbox((x, y, HZ), (0.9, 0.9, 0.9), 'orn' if lv >= 1 else 'metal', rot=('z', 45, (x, y, HZ)))
        if lv >= 3:
            m.cbox((x + 0.3, y + sgn * 0.8, HZ), (0.5, 1.0, 0.5), 'gem', glow=lv >= 4, emission=9 if lv >= 4 else 0)
    # string
    (ux, uy), (lx, ly) = tips
    if pull < 0:
        sx = max(ux, lx) + 0.1
        m.box((sx - 0.2, ly, HZ - 0.2), (sx + 0.2, uy, HZ + 0.2), 'string')
    else:
        px_, py_ = max(ux, lx) + 1.4 + 1.6 * pull, gy
        for (tx, ty) in tips:
            mx, my = (tx + px_) / 2, (ty + py_) / 2
            ln = math.hypot(px_ - tx, py_ - ty)
            ang = math.degrees(math.atan2(px_ - tx, py_ - ty))  # from vertical
            m.cbox((mx, my, HZ), (0.4, ln, 0.4), 'string', rot=('z', -ang, (mx, my, HZ)))
        # nocked arrow along −X
        ax0 = px_
        ax1 = gx - 3.5
        m.box((ax1, gy - 0.25, HZ - 0.25), (ax0, gy + 0.25, HZ + 0.25), 'wood')
        m.cbox((ax1 - 0.5, gy, HZ), (1.2, 1.2, 0.5), 'edge', glow=True, rot=('z', 45, (ax1 - 0.5, gy, HZ)))
        for s in (-1, 1):
            m.box((ax0 - 2.0, gy + (0.25 if s > 0 else -0.85), HZ - 0.1), (ax0 - 0.5, gy + (0.85 if s > 0 else -0.25), HZ + 0.1), 'cloth')
    # riser decoration
    if lv >= 2:
        m.cbox((gx - 0.95, gy, HZ), (0.5, 2.6, 1.1), 'orn')
    if lv >= 2:
        m.cbox((gx - 1.15, gy, HZ), (0.6, 0.9, 0.9), 'gem', glow=lv >= 4, emission=10 if lv >= 4 else 0)
    if lv >= 4:
        for k, yy in enumerate((gy + 6.5, gy - 6.5)):
            m.cbox((gx - 3.0, yy, HZ), (0.9, 0.9, 0.9), 'glow', glow=True, emission=12, shade=False,
                   rot=('z', 45, (gx - 3.0, yy, HZ)))
    if lv >= 5:
        _halo_bow(m, gx, gy)


def _halo_bow(m, gx, gy):
    for k in range(10):
        a = 2 * math.pi * k / 10
        y = gy + math.sin(a) * 3.0
        z = HZ + math.cos(a) * 3.0
        m.cbox((gx - 0.4, y, z), (0.5, 0.5, 0.5), 'glow', glow=True, emission=13, shade=False)


TEMPLATES = {
    'longsword': longsword, 'broadsword': broadsword, 'mace': mace,
    'greatsword': greatsword, 'cleaver': cleaver, 'great_axe': great_axe,
    'staff_orb': staff_orb, 'staff_crystal': staff_crystal, 'staff_ring': staff_ring,
    'scepter': scepter, 'sun_scepter': sun_scepter, 'censer_staff': censer_staff,
    'dagger': dagger, 'kris': kris, 'fang_blade': fang_blade,
}
BOWS = ('longbow', 'recurve_bow', 'composite_bow')
ONE_HANDED = {'longsword', 'broadsword', 'mace', 'dagger', 'kris', 'fang_blade', 'scepter', 'sun_scepter'}
TWO_HANDED = {'greatsword', 'cleaver', 'great_axe'}
STAVES = {'staff_orb', 'staff_crystal', 'staff_ring', 'censer_staff'}
