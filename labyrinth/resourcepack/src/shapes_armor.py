"""3D armour, shield and accessory templates (GDD §14.1).  Original cuboid designs.

Helmets are authored in head space for the identity HEAD transform: the wearer's head
occupies x,z,y ∈ [1.6, 14.4] and its face looks toward −Z (north).  Body-armour icons and
accessories are miniatures centred on (8, 8, 8) with their front toward −Z (armour) or +Z
(shields/trinkets, which face the GUI camera).
"""
from __future__ import annotations

import math

from .model import Model

C = 8.0


def _lv(spec):
    return spec['level']


def _glow_ring(m, cy, r, n, size=0.55, em=12, plane='xz', cx=C, cz=C):
    for k in range(n):
        a = 2 * math.pi * k / n
        if plane == 'xz':
            p = (cx + math.cos(a) * r, cy, cz + math.sin(a) * r)
            rot = ('y', 45, p)
        else:
            p = (cx + math.cos(a) * r, cy + math.sin(a) * r, cz)
            rot = ('z', 45, p)
        m.cbox(p, (size, size, size), 'glow', glow=True, emission=em, shade=False, rot=rot)


def _walls(m, y0, y1, lo=1.0, hi=15.0, t=0.8, role='plate', front=True, **kw):
    if front:
        m.box((lo, y0, lo - t / 2), (hi, y1, lo + t / 2), role, **kw)
    m.box((lo, y0, hi - t / 2), (hi, y1, hi + t / 2), role, **kw)
    m.box((lo - t / 2, y0, lo), (lo + t / 2, y1, hi), role, **kw)
    m.box((hi - t / 2, y0, lo), (hi + t / 2, y1, hi), role, **kw)


# ───────────────────────────── helmets ─────────────────────────────

def helm_knight(m: Model, spec):
    lv = _lv(spec)
    m.box((1.0, 8.6, 1.0), (15.0, 15.2, 15.0), 'plate', glow=lv >= 4)
    m.box((2.0, 15.2, 2.0), (14.0, 16.0, 14.0), 'plate', glow=lv >= 4)
    m.box((1.0, 1.4, 0.4), (15.0, 8.0, 1.4), 'plate', glow=lv >= 4)         # face plate
    slit_role = 'glow' if lv >= 4 else 'dark'
    m.box((2.2, 8.0, 0.5), (13.8, 8.9, 1.1), slit_role, glow=lv >= 4, emission=12 if lv >= 4 else 0, shade=lv < 4)
    m.box((0.5, 1.4, 1.0), (1.5, 8.6, 15.0), 'plate')
    m.box((14.5, 1.4, 1.0), (15.5, 8.6, 15.0), 'plate')
    m.box((1.0, 1.4, 14.5), (15.0, 8.6, 15.5), 'plate')
    m.box((0.6, 0.6, 0.6), (15.4, 1.6, 15.4), 'metal')                       # gorget rim
    m.box((7.3, 2.0, 0.0), (8.7, 8.0, 0.6), 'metal')                         # face ridge
    for k in range(3):
        y = 2.6 + k * 1.6
        for s in (-1, 1):
            m.box((C + s * 2.2 - 0.4, y, 0.2), (C + s * 2.2 + 0.4, y + 0.6, 0.45), 'dark')
    if lv >= 1:
        m.box((7.4, 14.6, 0.6), (8.6, 17.0, 15.0), 'orn')                    # crest ridge
    if lv >= 2:
        m.box((7.2, 16.4, 6.0), (8.8, 19.6, 15.0), 'cloth', glow=lv >= 4)     # plume
        m.box((7.2, 11.0, 14.8), (8.8, 18.2, 16.6), 'cloth', glow=lv >= 4)
    if lv >= 3:
        m.cbox((C, 11.4, 0.6), (1.8, 1.8, 0.8), 'gem', glow=lv >= 4, emission=10 if lv >= 4 else 0,
               rot=('z', 45, (C, 11.4, 0.6)))
        for s in (-1, 1):
            m.cbox((C + s * 7.3, 11.0, 7.0), (1.0, 3.0, 3.0), 'orn')
    if lv >= 5:
        _glow_ring(m, 18.5, 5.5, 10)


def _horn(m, side, spec, base_y=11.5):
    x, y = (15.2 if side > 0 else 0.8), base_y
    ang = 0.0
    segs = [(2.4, 2.0, -70), (2.2, 1.6, -40), (2.0, 1.2, -15), (1.6, 0.8, 10)]
    for (ln, w, a) in segs:
        a = a * side
        rad = math.radians(a)
        dx, dy = -math.sin(rad), math.cos(rad)
        cx, cy = x + dx * ln / 2, y + dy * ln / 2
        m.cbox((cx, cy, 6.5), (w, ln + 0.4, w), 'horn', glow=True, rot=('z', a, (cx, cy, 6.5)))
        x, y = x + dx * ln, y + dy * ln


def helm_horned(m: Model, spec):
    lv = _lv(spec)
    m.box((1.0, 9.0, 1.0), (15.0, 15.2, 15.0), 'plate', glow=lv >= 4)
    m.box((2.2, 15.2, 2.2), (13.8, 16.2, 13.8), 'plate', glow=lv >= 4)
    m.box((0.5, 8.4, 0.5), (15.5, 9.8, 15.5), 'metal')
    for s in (-1, 1):
        x0, x1 = (0.5, 4.2) if s < 0 else (11.8, 15.5)
        m.box((x0, 2.6, 0.4), (x1, 8.4, 1.4), 'plate')
    m.box((0.5, 2.6, 1.0), (1.5, 8.4, 15.0), 'plate')
    m.box((14.5, 2.6, 1.0), (15.5, 8.4, 15.0), 'plate')
    m.box((1.0, 2.6, 14.5), (15.0, 8.4, 15.5), 'plate')
    m.box((7.3, 4.2, 0.0), (8.7, 9.6, 0.6), 'metal')                         # nose guard
    for s in (-1, 1):
        _horn(m, s, spec)
    if lv >= 2:
        for k in range(5):
            m.cbox((2.0 + k * 3.0, 9.1, 0.4), (0.7, 0.7, 0.5), 'orn')
    if lv >= 3:
        m.cbox((C, 12.0, 0.8), (1.6, 1.6, 0.6), 'gem', glow=lv >= 4, emission=10, rot=('z', 45, (C, 12.0, 0.8)))
    if lv >= 4:
        for s in (-1, 1):
            m.box((C + s * 3.4 - 1.0, 7.0, 0.3), (C + s * 3.4 + 1.0, 7.6, 0.6), 'glow', glow=True, emission=12, shade=False)


def helm_winged(m: Model, spec):
    lv = _lv(spec)
    m.box((1.0, 8.8, 1.0), (15.0, 15.2, 15.0), 'plate', glow=lv >= 4)
    m.box((2.0, 15.2, 2.0), (14.0, 16.0, 14.0), 'plate', glow=lv >= 4)
    m.box((0.5, 8.2, 0.5), (15.5, 9.6, 15.5), 'orn')
    m.box((0.5, 3.0, 1.0), (1.5, 8.2, 15.0), 'plate')
    m.box((14.5, 3.0, 1.0), (15.5, 8.2, 15.0), 'plate')
    m.box((1.0, 3.0, 14.5), (15.0, 8.2, 15.5), 'plate')
    m.box((7.3, 4.8, 0.0), (8.7, 9.4, 0.6), 'metal')
    for s in (-1, 1):
        x0 = 15.5 if s > 0 else -0.1
        for k, (ln, ang) in enumerate(((6.0, -15), (5.2, -38), (4.2, -60))):
            z0 = 6.0 + k * 1.2
            m.box((min(x0, x0 + s * 0.6), 9.5, z0), (max(x0, x0 + s * 0.6), 9.5 + ln, z0 + 1.6), 'blade', glow=True,
                  rot=('x', ang, (x0, 9.5, z0 + 0.8)))
    if lv >= 3:
        m.cbox((C, 11.6, 0.7), (1.6, 1.6, 0.6), 'gem', glow=lv >= 4, emission=10, rot=('z', 45, (C, 11.6, 0.7)))
    if lv >= 4:
        _glow_ring(m, 17.5, 4.5, 8)


def hood(m: Model, spec):
    lv = _lv(spec)
    m.box((0.6, 13.6, 0.4), (15.4, 15.8, 15.6), 'cloth', glow=lv >= 4)
    m.box((0.2, 0.6, 0.6), (1.4, 13.6, 15.4), 'cloth', glow=lv >= 4)
    m.box((14.6, 0.6, 0.6), (15.8, 13.6, 15.4), 'cloth', glow=lv >= 4)
    m.box((0.6, 0.6, 14.4), (15.4, 13.6, 15.8), 'cloth', glow=lv >= 4)
    m.box((1.0, 11.8, 0.0), (15.0, 14.2, 1.4), 'cloth')                     # brow edge
    m.box((1.0, 1.0, 0.0), (2.8, 11.8, 1.4), 'cloth')
    m.box((13.2, 1.0, 0.0), (15.0, 11.8, 1.4), 'cloth')
    m.box((1.2, 11.6, 0.0), (14.8, 12.2, 0.4), 'trim')
    m.box((4.0, 12.0, 15.0), (12.0, 15.2, 18.0), 'cloth', rot=('x', -22.5, (8.0, 13.6, 15.0)))   # point
    m.box((1.5, -3.0, 14.6), (14.5, 1.0, 16.2), 'cloth')                    # back drape
    m.box((2.6, 0.2, 1.2), (13.4, 1.2, 2.2), 'dark')                         # collar shadow
    if lv >= 2:
        m.cbox((C, 1.6, 0.4), (2.0, 2.0, 0.8), 'orn', rot=('z', 45, (C, 1.6, 0.4)))   # clasp
    if lv >= 3:
        m.box((1.0, 0.4, 0.0), (15.0, 1.0, 1.4), 'trim')
    if lv >= 4:
        for s in (-1, 1):
            m.cbox((C + s * 2.6, 8.4, 1.0), (1.0, 0.6, 0.4), 'glow', glow=True, emission=13, shade=False)


def wizard_hat(m: Model, spec):
    lv = _lv(spec)
    m.box((-2.0, 12.4, -2.0), (18.0, 13.4, 18.0), 'cloth', glow=lv >= 4)
    m.cbox((C, 12.9, C), (16.5, 0.98, 16.5), 'cloth', rot=('y', 45, (C, 12.9, C)))
    m.box((1.2, 13.4, 1.2), (14.8, 15.2, 14.8), 'trim')
    m.box((2.0, 15.2, 2.0), (14.0, 18.2, 14.0), 'cloth', glow=lv >= 4)
    m.box((3.4, 18.2, 3.6), (12.6, 21.2, 12.8), 'cloth', glow=lv >= 4, rot=('x', -8, (8, 18.2, 8)))
    m.box((4.9, 20.8, 5.6), (11.1, 24.2, 11.8), 'cloth', glow=lv >= 4, rot=('x', -18, (8, 20.8, 8.6)))
    m.box((6.2, 23.4, 7.6), (9.8, 26.6, 11.2), 'cloth', glow=lv >= 4, rot=('x', -32, (8, 23.4, 9.4)))
    m.box((7.0, 25.0, 10.2), (9.0, 28.0, 12.2), 'cloth', glow=lv >= 4, rot=('x', -45, (8, 25.0, 11.2)))
    m.cbox((C, 14.3, 0.9), (1.8, 1.8, 0.6), 'gem', glow=lv >= 3, emission=10 if lv >= 4 else 0,
           rot=('z', 45, (C, 14.3, 0.9)))
    if lv >= 2:
        for s in (-1, 1):
            m.cbox((C + s * 3.0, 16.8, 1.8), (0.8, 0.8, 0.5), 'orn', rot=('z', 45, (C + s * 3.0, 16.8, 1.8)))
    if lv >= 4:
        _glow_ring(m, 19.5, 6.0, 8)


def circlet(m: Model, spec):
    lv = _lv(spec)
    _walls(m, 10.2, 11.4, lo=1.2, hi=14.8, t=0.6, role='orn')
    m.cbox((C, 11.0, 0.6), (2.0, 2.0, 0.8), 'gem', glow=True, emission=11 if lv >= 4 else 3, rot=('z', 45, (C, 11.0, 0.6)))
    m.box((7.5, 11.4, 0.6), (8.5, 13.4, 1.2), 'orn')
    for s in (-1, 1):
        m.cbox((C + s * 3.5, 10.8, 0.7), (0.9, 0.9, 0.5), 'gem', glow=lv >= 4, emission=9)
        m.cbox((C + s * 5.6, 11.6, 0.9), (0.7, 1.6, 0.6), 'orn', rot=('z', s * 22.5, (C + s * 5.6, 11.0, 0.9)))
    if lv >= 4:
        _glow_ring(m, 15.5, 4.0, 8, size=0.5)


def crown(m: Model, spec):
    lv = _lv(spec)
    _walls(m, 13.0, 15.4, lo=1.0, hi=15.0, t=0.9, role='orn', glow=True)
    _walls(m, 12.6, 13.2, lo=0.8, hi=15.2, t=1.1, role='metal')
    pts = [1.2, 4.6, 8.0, 11.4, 14.8]
    for k, p in enumerate(pts):
        h = 2.4 if k % 2 == 0 else 1.6
        for (x, z) in ((p, 1.0), (p, 15.0), (1.0, p), (15.0, p)):
            m.cbox((x, 15.4 + h / 2, z), (1.0, h, 1.0), 'orn', glow=True)
            if k % 2 == 0:
                m.cbox((x, 15.6 + h, z), (0.8, 0.8, 0.8), 'gem', glow=True, emission=11 if lv >= 4 else 0,
                       rot=('y', 45, (x, 15.6 + h, z)))
    m.cbox((C, 14.2, 0.4), (1.8, 1.8, 0.7), 'gem', glow=True, emission=12 if lv >= 4 else 2, rot=('z', 45, (C, 14.2, 0.4)))
    for s in (-1, 1):
        m.cbox((C + s * 3.8, 14.2, 0.5), (1.0, 1.0, 0.5), 'gem', glow=True, emission=10 if lv >= 4 else 0)
    if lv >= 5:
        for k in range(6):
            a = 2 * math.pi * k / 6
            x, z = C + math.cos(a) * 6.5, C + math.sin(a) * 6.5
            m.cbox((x, 20.0 + (k % 2) * 1.0, z), (0.9, 1.8, 0.9), 'crystal', glow=True, emission=13, shade=False,
                   rot=('y', 45, (x, 20.0, z)))


def half_mask(m: Model, spec):
    lv = _lv(spec)
    m.box((2.0, 1.6, 0.4), (14.0, 7.6, 1.4), 'plate', glow=lv >= 4)
    m.box((7.2, 4.8, 0.0), (8.8, 8.6, 0.6), 'plate', glow=lv >= 4)
    for s in (-1, 1):
        x0, x1 = (0.6, 2.2) if s < 0 else (13.8, 15.4)
        m.box((x0, 2.4, 0.8), (x1, 7.0, 6.5), 'plate')
        m.box((x0, 7.0, 0.8), (x1, 7.8, 15.2), 'leather')
    m.box((0.8, 7.0, 14.6), (15.2, 7.8, 15.4), 'leather')
    for k in range(4):
        y = 2.4 + k * 1.2
        m.box((4.0, y, 0.2), (6.6, y + 0.5, 0.45), 'dark')
        m.box((9.4, y, 0.2), (12.0, y + 0.5, 0.45), 'dark')
    if spec.get('style') in ('ink', 'shadow', 'silk', 'cloth', 'void'):
        m.box((2.4, -2.2, 0.7), (13.6, 1.6, 1.1), 'cloth', glow=lv >= 4)      # veil
    if lv >= 2:
        m.box((2.0, 7.2, 0.2), (14.0, 7.8, 0.5), 'trim')
    if lv >= 3:
        m.cbox((C, 6.6, 0.1), (1.2, 1.2, 0.5), 'gem', glow=lv >= 4, emission=10, rot=('z', 45, (C, 6.6, 0.1)))
    if lv >= 4:
        for s in (-1, 1):
            m.cbox((C + s * 3.0, 9.2, 0.6), (1.4, 0.5, 0.4), 'glow', glow=True, emission=13, shade=False)


# ───────────────────────────── body armour miniatures ─────────────────────────────

def chestplate(m: Model, spec):
    lv = _lv(spec)
    m.box((4.0, 3.0, 6.0), (12.0, 13.0, 10.0), 'plate', glow=lv >= 4)
    m.box((4.6, 6.0, 5.4), (11.4, 12.4, 6.0), 'plate', glow=lv >= 4)        # chest bulge
    for s in (-1, 1):
        cx = C + s * 4.6
        m.cbox((cx, 12.2, C), (3.6, 2.6, 5.0), 'plate', rot=('z', -s * 15, (cx, 12.2, C)))
        m.cbox((cx + s * 0.4, 10.9, C), (3.2, 1.0, 4.6), 'metal', rot=('z', -s * 15, (cx, 12.2, C)))
    m.box((5.2, 12.6, 5.6), (10.8, 14.0, 10.4), 'metal')
    m.box((3.8, 3.0, 5.6), (12.2, 4.4, 10.4), 'leather')
    m.box((7.2, 2.4, 5.4), (8.8, 4.8, 5.8), 'orn')
    if lv >= 1:
        m.box((7.4, 5.0, 5.2), (8.6, 12.2, 5.6), 'orn')
    if lv >= 2:
        m.cbox((C, 9.4, 5.1), (1.8, 1.8, 0.6), 'gem', glow=lv >= 4, emission=10 if lv >= 4 else 0, rot=('z', 45, (C, 9.4, 5.1)))
    if lv >= 3:
        for s in (-1, 1):
            m.cbox((C + s * 2.6, 7.4, 5.3), (0.7, 0.7, 0.4), 'orn')


def robe_top(m: Model, spec):
    lv = _lv(spec)
    m.box((4.6, 4.5, 6.2), (11.4, 13.0, 9.8), 'cloth', glow=lv >= 4)
    m.box((3.6, 1.0, 5.6), (12.4, 4.8, 10.4), 'cloth', glow=lv >= 4)
    for s in (-1, 1):
        cx = C + s * 4.8
        m.cbox((cx, 9.6, C), (2.6, 6.4, 3.4), 'cloth', rot=('z', -s * 18, (cx, 12.6, C)))
        m.cbox((cx + s * 1.5, 6.9, C), (3.0, 1.4, 3.8), 'trim', rot=('z', -s * 18, (cx, 12.6, C)))
    m.box((5.4, 12.4, 5.8), (10.6, 13.8, 10.2), 'trim')
    m.box((7.3, 1.0, 5.4), (8.7, 12.6, 5.8), 'trim')
    m.box((3.6, 1.0, 5.4), (12.4, 1.8, 5.7), 'trim')
    m.box((4.6, 6.0, 5.9), (11.4, 6.8, 10.1), 'leather')
    if lv >= 2:
        m.cbox((C, 6.4, 5.4), (1.6, 1.6, 0.6), 'gem', glow=lv >= 4, emission=10 if lv >= 4 else 0, rot=('z', 45, (C, 6.4, 5.4)))
    if lv >= 3:
        m.box((5.0, 13.6, 9.6), (11.0, 14.6, 11.6), 'cloth')   # collar hood fold


def leather_vest(m: Model, spec):
    lv = _lv(spec)
    m.box((4.4, 3.4, 6.0), (11.6, 12.6, 10.0), 'leather', glow=lv >= 4)
    m.box((4.0, 11.6, 5.6), (12.0, 13.2, 10.4), 'cloth')              # fur collar
    for s in (-1, 1):
        m.cbox((C + s * 4.6, 11.4, C), (2.2, 2.0, 4.4), 'leather')
    m.box((4.2, 3.4, 5.6), (11.8, 4.6, 10.4), 'plate')
    m.box((5.0, 5.0, 5.6), (11.0, 5.8, 5.9), 'plate', rot=('z', 22.5, (8, 5.4, 5.75)))
    m.box((5.0, 8.0, 5.6), (11.0, 8.8, 5.9), 'plate', rot=('z', -22.5, (8, 8.4, 5.75)))
    m.box((9.0, 4.0, 5.2), (11.0, 6.0, 5.8), 'leather')             # pouch
    m.box((7.4, 3.0, 5.4), (8.6, 4.8, 5.7), 'metal')
    if lv >= 2:
        for k in range(3):
            m.cbox((6.0, 6.0 + k * 1.8, 5.5), (0.6, 0.6, 0.4), 'metal')
    if lv >= 3:
        m.cbox((C, 10.4, 5.4), (1.4, 1.4, 0.6), 'gem', glow=lv >= 4, emission=10, rot=('z', 45, (C, 10.4, 5.4)))


def leggings(m: Model, spec):
    lv = _lv(spec)
    m.box((4.0, 12.6, 6.0), (12.0, 14.2, 10.0), 'leather')
    m.box((7.3, 12.4, 5.6), (8.7, 14.4, 6.0), 'metal')
    m.box((4.0, 9.6, 6.2), (12.0, 12.6, 9.8), 'plate', glow=lv >= 4)
    for s in (-1, 1):
        x0 = 4.2 if s < 0 else 8.2
        m.box((x0, 1.4, 6.4), (x0 + 3.6, 9.6, 9.6), 'plate', glow=lv >= 4)
        m.box((x0 + 0.4, 5.0, 6.0), (x0 + 3.2, 7.0, 6.4), 'metal')        # knee guard
        if lv >= 2:
            m.box((x0 + 0.2, 9.6, 5.8), (x0 + 3.4, 11.8, 6.2), 'trim')
        if lv >= 3:
            m.cbox((x0 + 1.8, 6.0, 5.9), (0.8, 0.8, 0.4), 'gem', glow=lv >= 4, emission=10)


def boots(m: Model, spec):
    lv = _lv(spec)
    for s in (-1, 1):
        x0 = 3.0 if s < 0 else 9.0
        m.box((x0, 3.0, 6.6), (x0 + 4.0, 10.0, 9.8), 'plate', glow=lv >= 4)
        m.box((x0, 1.0, 4.2), (x0 + 4.0, 3.4, 9.8), 'plate', glow=lv >= 4)
        m.box((x0 - 0.1, 0.6, 4.0), (x0 + 4.1, 1.2, 10.0), 'dark')
        m.box((x0 - 0.3, 9.0, 6.3), (x0 + 4.3, 10.6, 10.1), 'trim' if lv >= 1 else 'leather')
        m.box((x0 + 0.4, 3.4, 6.3), (x0 + 3.6, 4.2, 6.7), 'leather')
        if lv >= 2:
            m.box((x0 + 0.8, 1.4, 3.9), (x0 + 3.2, 3.0, 4.3), 'metal')
        if lv >= 3:
            m.cbox((x0 + 2.0, 7.0, 6.3), (0.8, 0.8, 0.5), 'gem', glow=lv >= 4, emission=10)
        if lv >= 4:
            for k in range(2):
                m.cbox((x0 + 4.4, 8.0 - k * 1.6, 9.0 - k * 1.2), (0.4, 1.4, 1.4), 'glow', glow=True, emission=12, shade=False)


# ───────────────────────────── shields (front faces +Z) ─────────────────────────────

def _shield_rows(m, rows, spec, zf=8.6):
    """rows: [(y0, y1, half_width)] → rim layer + inset face layer."""
    lv = _lv(spec)
    face = 'wood' if spec.get('style') == 'wood' else 'plate'
    for (y0, y1, hw) in rows:
        m.box((C - hw, y0, zf - 1.6), (C + hw, y1, zf - 0.8), 'metal')
    inner = rows[1:-1]
    for (y0, y1, hw) in inner:
        if hw > 0.9:
            m.box((C - hw + 0.8, y0, zf - 0.8), (C + hw - 0.8, y1, zf), face, glow=lv >= 4)
    m.box((C - 1.0, 5.0, zf - 2.6), (C + 1.0, 11.0, zf - 1.6), 'leather')   # handle


def round_shield(m: Model, spec):
    lv = _lv(spec)
    R = 7.2
    rows = []
    y = C - R
    while y < C + R - 0.01:
        ym = y + 0.5
        hw = math.sqrt(max(0.0, R * R - (ym - C) ** 2))
        rows.append((y, y + 1.0, max(0.75, round(hw * 2) / 2)))
        y += 1.0
    _shield_rows(m, rows, spec)
    if lv >= 1:
        m.box((7.4, 1.6, 8.6), (8.6, 14.4, 8.9), 'metal')
        m.box((1.6, 7.4, 8.6), (14.4, 8.6, 8.9), 'metal')
    m.box((6.0, 6.0, 8.6), (10.0, 10.0, 9.6), 'metal')
    m.box((6.6, 6.6, 9.6), (9.4, 9.4, 10.2), 'gem' if lv >= 2 else 'metal', glow=lv >= 4, emission=11 if lv >= 4 else 0)
    if lv >= 3:
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            m.cbox((C + math.cos(a) * 5.6, C + math.sin(a) * 5.6, 8.75), (0.8, 0.8, 0.5), 'orn')
    if lv >= 4:
        _glow_ring(m, C, 4.0, 8, size=0.6, plane='xy', cz=9.0)


def kite_shield(m: Model, spec):
    lv = _lv(spec)
    rows = []
    for k in range(17):
        y0 = -0.5 + k
        if y0 >= 9.5:
            hw = 6.5 if y0 < 15.5 else 5.5
        else:
            hw = 1.0 + (y0 + 0.5) * 0.55
        rows.append((y0, y0 + 1.0, round(hw * 2) / 2))
    _shield_rows(m, rows, spec)
    m.box((7.4, 1.0, 8.6), (8.6, 15.0, 8.9), 'orn' if lv >= 1 else 'metal')
    m.box((2.4, 11.0, 8.6), (13.6, 12.2, 8.9), 'orn' if lv >= 1 else 'metal')
    if lv >= 2:
        m.cbox((C, 11.6, 9.1), (2.0, 2.0, 0.8), 'gem', glow=lv >= 4, emission=11 if lv >= 4 else 0, rot=('z', 45, (C, 11.6, 9.1)))
    if lv >= 3:
        for (x, y) in ((3.2, 14.6), (12.8, 14.6), (C, 2.0)):
            m.cbox((x, y, 8.75), (0.8, 0.8, 0.5), 'orn')
    if lv >= 4:
        _glow_ring(m, 11.6, 3.2, 8, size=0.5, plane='xy', cz=9.2)


def tower_shield(m: Model, spec):
    lv = _lv(spec)
    rows = [(-1.0 + k, 0.0 + k, 6.0 if 0 < k < 17 else 5.0) for k in range(18)]
    _shield_rows(m, rows, spec)
    m.box((7.2, 0.0, 8.6), (8.8, 16.0, 9.2), 'metal')
    for y in (2.0, 13.0):
        m.box((2.6, y, 8.6), (13.4, y + 1.0, 8.9), 'orn' if lv >= 1 else 'metal')
    for (x, y) in ((3.2, 0.6), (12.8, 0.6), (3.2, 15.4), (12.8, 15.4)):
        m.cbox((x, y, 8.7), (0.7, 0.7, 0.4), 'metal')
    if lv >= 2:
        m.cbox((C, 8.0, 9.3), (2.4, 2.4, 0.8), 'gem', glow=lv >= 4, emission=11 if lv >= 4 else 0, rot=('z', 45, (C, 8.0, 9.3)))
    if lv >= 3:
        for s in (-1, 1):
            m.cbox((C + s * 3.2, 8.0, 8.75), (1.0, 3.0, 0.5), 'orn')
    if lv >= 4:
        _glow_ring(m, 8.0, 3.6, 8, size=0.55, plane='xy', cz=9.4)


# ───────────────────────────── accessories (face +Z) ─────────────────────────────

def _ring_band(m, cy, R, seg, w, d, n=8, role='orn', cz=C, glow=False):
    for k in range(n):
        ang = 360.0 * k / n
        rad = math.radians(ang)
        cx, y = C + math.cos(rad) * R, cy + math.sin(rad) * R
        m.cbox((cx, y, cz), (w, seg, d), role, glow=glow, rot=('z', ang, (cx, y, cz)))


def ring(m: Model, spec):
    lv = _lv(spec)
    _ring_band(m, 7.0, 2.6, 2.3, 0.9, 1.5, role='orn', glow=lv >= 4)
    m.box((6.8, 9.2, 7.0), (9.2, 10.2, 9.0), 'metal')
    m.cbox((C, 10.9, C), (1.7, 1.7, 1.7), 'gem', glow=True, emission=10 if lv >= 4 else 0, rot=('y', 45, (C, 10.9, C)))
    for s in (-1, 1):
        m.cbox((C + s * 1.0, 10.4, C), (0.4, 1.4, 0.4), 'orn', rot=('z', -s * 25, (C + s * 1.0, 10.0, C)))
    if lv >= 3:
        for s in (-1, 1):
            m.cbox((C + s * 1.9, 9.2, C), (0.7, 0.7, 0.7), 'gem', glow=lv >= 4, emission=9)
    if lv >= 4:
        _glow_ring(m, 7.0, 4.2, 8, size=0.45, plane='xy')


def amulet(m: Model, spec):
    lv = _lv(spec)
    for s in (-1, 1):
        for k in range(5):
            x = C + s * (4.6 - k * 0.85)
            y = 14.0 - k * 1.25
            m.cbox((x, y, C), (0.6, 0.9, 0.6) if k % 2 == 0 else (0.9, 0.6, 0.6), 'chain')
    m.cbox((C, 8.3, C), (1.0, 1.0, 1.0), 'orn')
    m.box((5.6, 3.4, 7.4), (10.4, 7.6, 8.6), 'orn', glow=lv >= 4)
    m.cbox((C, 2.8, C), (1.6, 1.6, 1.1), 'orn', rot=('z', 45, (C, 2.8, C)))
    m.cbox((C, 5.5, 8.6), (2.4, 2.4, 0.8), 'gem', glow=True, emission=11 if lv >= 4 else 0, rot=('z', 45, (C, 5.5, 8.6)))
    if lv >= 2:
        for s in (-1, 1):
            m.cbox((C + s * 2.8, 5.5, C), (0.9, 0.9, 0.9), 'gem', glow=lv >= 4, emission=9)
    if lv >= 4:
        _glow_ring(m, 5.5, 4.0, 8, size=0.45, plane='xy')


def bracelet(m: Model, spec):
    lv = _lv(spec)
    _ring_band(m, C, 3.6, 3.2, 1.2, 3.0, role='orn', glow=lv >= 4)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        m.cbox((C + math.cos(a) * 4.3, C + math.sin(a) * 4.3, C), (0.8, 0.8, 0.8), 'gem' if k % 2 == 0 else 'metal',
               glow=lv >= 4 and k % 2 == 0, emission=9 if lv >= 4 else 0)
    if lv >= 3:
        m.cbox((C, C + 4.6, C), (1.8, 1.8, 1.8), 'gem', glow=True, emission=10 if lv >= 4 else 0, rot=('z', 45, (C, C + 4.6, C)))


def charm(m: Model, spec):
    lv = _lv(spec)
    _ring_band(m, 13.0, 1.3, 1.2, 0.5, 0.5, role='metal')
    m.box((7.7, 9.6, 7.7), (8.3, 11.8, 8.3), 'chain')
    m.cbox((C, 9.4, C), (1.4, 1.0, 1.4), 'orn')
    m.box((6.0, 4.0, 6.6), (10.0, 9.0, 9.4), 'plate', glow=lv >= 4)
    m.box((5.4, 3.4, 6.2), (10.6, 4.4, 9.8), 'orn')
    m.cbox((C, 2.6, C), (1.2, 1.2, 1.2), 'orn', rot=('y', 45, (C, 2.6, C)))
    m.cbox((C, 6.5, 9.5), (1.6, 1.6, 0.6), 'gem', glow=True, emission=10 if lv >= 4 else 0, rot=('z', 45, (C, 6.5, 9.5)))
    if lv >= 2:
        for s in (-1, 1):
            m.cbox((C + s * 2.4, 8.0, C), (0.7, 2.0, 0.7), 'orn', rot=('z', -s * 22.5, (C + s * 2.0, 9.0, C)))
    if lv >= 4:
        _glow_ring(m, 6.5, 3.8, 8, size=0.45, plane='xy')


def emblem(m: Model, spec):
    lv = _lv(spec)
    R = 5.6
    y = C - R
    while y < C + R - 0.01:
        ym = y + 0.5
        hw = math.sqrt(max(0.0, R * R - (ym - C) ** 2))
        hw = max(0.75, round(hw * 2) / 2)
        m.box((C - hw, y, 7.2), (C + hw, y + 1.0, 8.0), 'metal')
        if hw > 1.5 and C - R + 0.9 < ym < C + R - 0.9:
            m.box((C - hw + 0.8, y, 8.0), (C + hw - 0.8, y + 1.0, 8.5), 'field', glow=lv >= 4)
        y += 1.0
    _emblem_relief(m, spec.get('motif') or 'cross', lv)
    for s in (-1, 1):
        m.cbox((C + s * 4.6, 12.2, 7.6), (1.4, 2.6, 0.8), 'orn', rot=('z', -s * 35, (C + s * 4.6, 12.2, 7.6)))
    if lv >= 3:
        for k in range(6):
            a = 2 * math.pi * k / 6 + math.pi / 6
            m.cbox((C + math.cos(a) * 4.0, C + math.sin(a) * 4.0, 8.6), (0.6, 0.6, 0.4), 'orn')


def _emblem_relief(m, motif, lv):
    z0, z1 = 8.5, 9.2
    em = 10 if lv >= 4 else 0
    if motif == 'shield':
        for k, hw in enumerate((3.0, 3.0, 3.0, 2.6, 2.0, 1.2, 0.5)):
            y = 11.5 - k * 1.0
            m.box((C - hw, y - 1.0, z0), (C + hw, y, z1), 'orn')
        m.box((C - 0.4, 5.2, z1), (C + 0.4, 10.8, z1 + 0.3), 'metal')
        m.box((C - 2.4, 9.0, z1), (C + 2.4, 9.8, z1 + 0.3), 'metal')
    elif motif == 'axes':
        for s_ in (-1, 1):
            m.cbox((C, 8.0, z0 + 0.35), (0.9, 8.5, 0.7), 'orn', rot=('z', s_ * 40, (C, 8.0, z0)))
            hx, hy = C - s_ * 2.6, 11.2
            m.cbox((hx, hy, z0 + 0.4), (2.4, 2.0, 0.8), 'metal', rot=('z', s_ * 40, (hx, hy, z0)))
    elif motif == 'arrow':
        m.cbox((C, 8.0, z0 + 0.35), (0.8, 9.0, 0.7), 'orn', rot=('z', -45, (C, 8.0, z0)))
        m.cbox((C + 3.1, 11.1, z0 + 0.4), (2.2, 2.2, 0.8), 'metal', rot=('z', 45, (C + 3.1, 11.1, z0)))
        for d in (0, 1):
            m.cbox((C - 2.6 + d * 0.9, 5.4 + d * 0.9, z0 + 0.35), (2.2, 0.6, 0.6), 'cloth', rot=('z', 45, (C - 2.6 + d * 0.9, 5.4 + d * 0.9, z0)))
    elif motif == 'star':
        for ang in (0, 90):
            m.cbox((C, 8.4, z0 + 0.35), (1.0, 8.0, 0.7), 'orn', rot=('z', ang, (C, 8.4, z0)) if ang else None)
        for ang in (45, -45):
            m.cbox((C, 8.4, z0 + 0.3), (0.7, 4.6, 0.6), 'orn', rot=('z', ang, (C, 8.4, z0)))
    elif motif == 'sun':
        for k in range(8):
            a = 2 * math.pi * k / 8
            m.cbox((C + math.cos(a) * 3.4, 8.4 + math.sin(a) * 3.4, z0 + 0.35), (1.0, 1.0, 0.7), 'orn',
                   rot=('z', 45, (C + math.cos(a) * 3.4, 8.4 + math.sin(a) * 3.4, z0)))
    elif motif == 'dagger':
        m.box((C - 0.6, 6.0, z0), (C + 0.6, 12.6, z1), 'metal')
        m.box((C - 2.2, 5.4, z0), (C + 2.2, 6.2, z1), 'orn')
        m.box((C - 0.5, 3.6, z0), (C + 0.5, 5.4, z1), 'leather')
        for k in range(4):
            a = math.radians(200 + k * 25)
            m.cbox((C + 3.6 + math.cos(a) * 1.2, 9.4 + math.sin(a) * 2.6, z0 + 0.3), (0.8, 1.6, 0.6), 'orn',
                   rot=('z', 200 + k * 25 - 180, (C + 3.6 + math.cos(a) * 1.2, 9.4 + math.sin(a) * 2.6, z0)))
    else:
        m.box((7.2, 4.0, z0), (8.8, 12.0, z1), 'orn')
        m.box((5.0, 7.6, z0), (11.0, 9.2, z1), 'orn')
    if motif not in ('shield', 'dagger'):
        m.cbox((C, 8.4, 9.4), (1.6, 1.6, 0.7), 'gem', glow=True, emission=em, rot=('z', 45, (C, 8.4, 9.4)))
    else:
        m.cbox((C, 11.6 if motif == 'dagger' else 8.0, 9.6), (1.2, 1.2, 0.6), 'gem', glow=True, emission=em,
               rot=('z', 45, (C, 11.6 if motif == 'dagger' else 8.0, 9.6)))


EMBLEM_MOTIFS = (('guardian', 'shield'), ('berserk', 'axes'), ('hunter', 'arrow'), ('arcan', 'star'),
                 ('priest', 'sun'), ('shadow', 'dagger'))


def relic_orb(m: Model, spec):
    lv = _lv(spec)
    cy = 9.0
    r = 3.4
    for size in ((r * 2, r * 1.3, r * 2), (r * 1.3, r * 2, r * 1.3), (r * 1.65, r * 1.65, r * 1.65)):
        m.cbox((C, cy, C), size, 'crystal', glow=True, emission=11 if lv >= 4 else 3, shade=lv < 4)
    for ang in (0, 60, 120):
        m.cbox((C, cy, C), (0.5, r * 2.3, r * 2.3 - 1.6), 'orn', rot=('y', ang, (C, cy, C)))
    m.box((5.4, 3.0, 5.4), (10.6, 4.4, 10.6), 'metal')
    m.box((6.4, 4.4, 6.4), (9.6, 5.8, 9.6), 'orn')
    for s in (-1, 1):
        m.cbox((C + s * 2.4, 5.2, C), (0.6, 2.0, 0.6), 'orn', rot=('z', -s * 30, (C + s * 2.4, 4.4, C)))
    if lv >= 3:
        _glow_ring(m, cy, r + 2.0, 10, size=0.5, plane='xz')
    if lv >= 5:
        _glow_ring(m, cy, r + 2.8, 10, size=0.45, plane='xy')


HELMETS = {'helm_knight': helm_knight, 'helm_horned': helm_horned, 'helm_winged': helm_winged, 'hood': hood,
           'wizard_hat': wizard_hat, 'circlet': circlet, 'crown': crown, 'half_mask': half_mask}
BODY = {'chestplate': chestplate, 'robe_top': robe_top, 'leather_vest': leather_vest, 'leggings': leggings,
        'boots': boots}
SHIELDS = {'kite_shield': kite_shield, 'round_shield': round_shield, 'tower_shield': tower_shield}
ACCESSORIES = {'ring': ring, 'amulet': amulet, 'bracelet': bracelet, 'charm': charm, 'emblem': emblem,
               'relic_orb': relic_orb}
