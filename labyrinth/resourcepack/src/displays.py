"""Display transforms per item category.

Hand transforms are derived from the conventions of Minecraft's own handheld/bow/shield/block
items (rotation order XYZ with Z applied first; the client negates rot y/z and pos x for the left
hand), adjusted for our upright 3D geometry.  GUI / ground / item-frame transforms are fitted
automatically from the model's real bounding box so every model is centred and fills the slot.
"""
from __future__ import annotations

import math

from .model import Model, fit_transform, mirror_left


def _t(rot, tr, sc):
    return {'rotation': list(rot), 'translation': list(tr), 'scale': [sc, sc, sc]}


# ───────────────────────────── held weapons ─────────────────────────────
# Our weapons are upright 3D models: grip at model (8, 1, 8), the blade / head along +Y, and the working side —
# edge of a single-edged blade, axe bit, hammer face, scythe or sickle blade, censer hook, spiral hook — toward +X
# (voxel/weapons.py and shapes_weapons.py build every design that way).  Vanilla's flat tool sprites have their
# heads toward −X, which is why item/handheld turns y −90°.  We turn y +90° (and tilt z the other way so the haft
# leans exactly like vanilla's sword), which sends +X away from the camera in first person and in front of the
# player in third person — where vanilla's axe head goes — so the edge leads the attack swing.  Symmetric weapons
# look the same either way.  (Copying vanilla's y −90° turned edges toward the camera / behind the player and made
# every swing a hammer blow with the back of the blade.)  Check with tools/hold_preview.py.
WEAPON_GRIP = (8.0, 1.0, 8.0)
FP_REF = ((0, 90, 20), (1.13, 3.2, 1.13), 0.68)     # first person: rotation, translation, base scale
TP_REF = ((0, 90, -10), (0, 4.0, 0.5))               # third person (scale 0.85, two-handed 0.9)
FP_AREA_K = 6.5      # first-person scale ≤ FP_AREA_K / √(silhouette area above the hand), see _fp_scale


def _rot(rot, v):
    """Rx·Ry·Rz·v in degrees — the client's Quaternionf.rotationXYZ, Z applied first."""
    x, y, z = v
    rx, ry, rz = (math.radians(a) for a in rot)
    c, s = math.cos(rz), math.sin(rz)
    x, y = x * c - y * s, x * s + y * c
    c, s = math.cos(ry), math.sin(ry)
    x, z = x * c + z * s, -x * s + z * c
    c, s = math.cos(rx), math.sin(rx)
    y, z = y * c - z * s, y * s + z * c
    return x, y, z


def held(rot, scale, ref, grip=WEAPON_GRIP):
    """(right, left) hand transforms with `rot` and `scale` whose translation keeps the grip point exactly where
    the reference transform (rotation, translation, scale) puts it.  The client scales and rotates around the
    block centre (8, 8, 8), so without this a smaller scale or another yaw would slide the handle out of the hand.
    Left hand: the client negates rot y/z and pos x (mirror_left), which flips the sideways part of the shift."""
    rr, rt, rs = ref
    scale = round(scale, 3)
    g = [grip[i] - 8.0 for i in range(3)]
    a = _rot(rr, [rs * c for c in g])
    b = _rot(rot, [scale * c for c in g])
    d = [a[i] - b[i] for i in range(3)]
    tr = [round(rt[i] + d[i], 3) + 0.0 for i in range(3)]
    right = _t(rot, tr, scale)
    left = mirror_left(right)
    left['translation'] = [round(rt[0] - d[0], 3) + 0.0, tr[1], tr[2]]
    return right, left


def silhouette_area(m: Model, above=3.0, res=0.5):
    """Front (XY) + ½ side (ZY) silhouette area in px² of the part above y = `above` (blade / head, not the grip),
    from the elements' bounding boxes on a `res` grid.  Tracks how much screen the weapon covers in first person
    (at rest and through the swing) far better than the height alone: wings, halos, double axe bits, big guards."""
    front, side = set(), set()
    for e in m.els:
        pts = e.corners()
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        y0 = max(lo[1], above)
        if hi[1] <= y0:
            continue
        ys = range(math.floor(y0 / res), math.ceil(hi[1] / res))
        for a, cells in ((0, front), (2, side)):
            for i in range(math.floor(lo[a] / res), math.ceil(hi[a] / res)):
                cells.update((i, j) for j in ys)
    return (len(front) + 0.5 * len(side)) * res * res


def _fp_scale(m: Model):
    """(first-person scale, width factor ≤ 1).  Height rule: 0.68 like vanilla's handheld; long models (greatswords,
    staves, top > 22) smaller by height.  Width rule: broad silhouettes (wings, halos, huge axe bits) smaller so the
    weapon covers ≤ ~9 % of the screen at rest and ≤ ~19 % of the screen centre while swinging (vanilla iron sword:
    8.6 % / 16.6 %).  FP_AREA_K was fitted on every weapon with tools/hold_preview.py (conservative: no weapon over)."""
    top = m.bounds()[1][1]
    s_h = 0.68 if top <= 22 else max(0.5, 0.68 * 22.0 / top)
    area = silhouette_area(m)
    s_w = FP_AREA_K / math.sqrt(area) if area > 0 else s_h
    s = max(0.4, min(s_h, s_w))
    return s, s / s_h


def weapon(m: Model, two_handed=False, gui_rot=(18, 22, -45), fp_yaw=90, fp_mul=1.0):
    """Upright melee weapon held by its grip (8, 1, 8).  fp_yaw: first-person y rotation — 90 = vanilla's axe angle
    (edge seen from behind); crescent blades turn further so their face shows while swinging (voxel/weapons.HOLD).
    fp_mul: extra first-person scale for a shape whose bulk sits where the swing crosses the screen centre (a big
    block head sweeps more of the centre than its silhouette area says) — voxel/weapons.HOLD[shape]['fp_mul']."""
    fp, wide = _fp_scale(m)
    fp = max(0.4, fp * fp_mul)
    tp0 = 0.9 if two_handed else 0.85
    # third person shrinks with the width rule too, at most 20 % (it never blocks the view)
    r3, l3 = held(TP_REF[0], tp0 * max(0.8, wide), (TP_REF[0], TP_REF[1], tp0))
    r1, l1 = held((0, fp_yaw, 20), fp, FP_REF)
    m.display = {
        'thirdperson_righthand': r3, 'thirdperson_lefthand': l3,
        'firstperson_righthand': r1, 'firstperson_lefthand': l1,
        'gui': fit_transform(m, gui_rot, target=15.5, max_scale=1.6),
        'ground': fit_transform(m, (0, 0, -45), target=9.0, max_scale=1.0, offset=(0, 1.5, 0)),
        'fixed': fit_transform(m, (0, 180, -45), target=15.0, max_scale=1.6),
    }


def bow(m: Model, gui_rot=(12, 18, -45)):
    r3 = _t((-80, 260, -85), (-1, -2, 2.5), 0.9)
    l3 = _t((-80, -280, 85), (-1, -2, 2.5), 0.9)
    r1 = _t((0, -90, -20), (1.13, 3.2, 1.13), 0.68)
    m.display = {
        'thirdperson_righthand': r3, 'thirdperson_lefthand': l3,
        'firstperson_righthand': r1, 'firstperson_lefthand': mirror_left(r1),
        'gui': fit_transform(m, gui_rot, target=15.5, max_scale=1.6),
        'ground': fit_transform(m, (0, 0, -45), target=9.0, max_scale=1.0, offset=(0, 1.5, 0)),
        'fixed': fit_transform(m, (0, 180, -45), target=15.0, max_scale=1.6),
    }


def shield(m: Model):
    r3 = _t((0, 90, 0), (3.5, -2.0, 4.0), 0.9)
    r1 = _t((0, 180, 5), (-0.9, -8.0, -1.9), 1.0)
    m.display = {
        'thirdperson_righthand': r3, 'thirdperson_lefthand': dict(r3),
        'firstperson_righthand': r1, 'firstperson_lefthand': dict(r1),
        'gui': fit_transform(m, (12, -25, -4), target=14.5, max_scale=1.6),
        'ground': fit_transform(m, (0, 0, 0), target=8.0, max_scale=1.0, offset=(0, 1.5, 0)),
        'fixed': fit_transform(m, (0, 180, 0), target=14.0, max_scale=1.6),
    }


def helmet(m: Model):
    """Model is authored in head space: identity HEAD transform puts it on the wearer's head."""
    m.display = {
        'head': _t((0, 0, 0), (0, 0, 0), 1.0),
        'thirdperson_righthand': _t((75, 45, 0), (0, 2.5, 0), 0.375),
        'thirdperson_lefthand': _t((75, 45, 0), (0, 2.5, 0), 0.375),
        'firstperson_righthand': _t((0, 45, 0), (0, 0, 0), 0.4),
        'firstperson_lefthand': _t((0, 225, 0), (0, 0, 0), 0.4),
        'gui': fit_transform(m, (24, 200, 0), target=15.0, max_scale=1.8),
        'ground': fit_transform(m, (0, 0, 0), target=7.0, max_scale=1.0, offset=(0, 1.5, 0)),
        'fixed': fit_transform(m, (0, 180, 0), target=13.0, max_scale=1.6),
    }


def miniature(m: Model, gui_rot=(22, 200, 0)):
    """3D armour icons / trinkets held like small blocks."""
    m.display = {
        'thirdperson_righthand': _t((75, 45, 0), (0, 2.5, 0), 0.4),
        'thirdperson_lefthand': _t((75, 45, 0), (0, 2.5, 0), 0.4),
        'firstperson_righthand': _t((0, 45, 0), (0, 0, 0), 0.45),
        'firstperson_lefthand': _t((0, 225, 0), (0, 0, 0), 0.45),
        'gui': fit_transform(m, gui_rot, target=14.5, max_scale=2.2),
        'ground': fit_transform(m, (0, 0, 0), target=7.0, max_scale=1.2, offset=(0, 1.5, 0)),
        'fixed': fit_transform(m, (0, 180, 0), target=13.0, max_scale=2.0),
        'head': _t((0, 180, 0), (0, 10, 0), 0.6),
    }


def trinket(m: Model, gui_rot=(15, 25, 0)):
    """Accessories: held like a flat item, shown large in the slot."""
    r3 = _t((0, 0, 0), (0, 3, 1), 0.55)
    r1 = _t((0, -90, 25), (1.13, 3.2, 1.13), 0.68)
    m.display = {
        'thirdperson_righthand': r3, 'thirdperson_lefthand': mirror_left(r3),
        'firstperson_righthand': r1, 'firstperson_lefthand': mirror_left(r1),
        'gui': fit_transform(m, gui_rot, target=14.0, max_scale=3.0),
        'ground': fit_transform(m, (0, 0, 0), target=7.0, max_scale=1.5, offset=(0, 1.5, 0)),
        'fixed': fit_transform(m, (0, 180, 0), target=12.0, max_scale=3.0),
        'head': _t((0, 180, 0), (0, 10, 0), 0.6),
    }


# ───────────────────────────── voxel models ─────────────────────────────
# Voxel weapons keep the hold point of the cuboid generation (8, 1, 8) / bow grip (4.5, 6, 8) and the
# same hand transforms, so they sit in the hand exactly like before; GUI views are refitted to the
# (larger, more detailed) voxel silhouettes.

def voxel_weapon(m: Model, two_handed=False):
    from .voxel import weapons as VW      # per-shape hold angle of the template that built this item
    hold = VW.hold_of(m.name)
    weapon(m, two_handed=two_handed, gui_rot=(20, 24, -45), fp_yaw=hold.get('fp_yaw', 90), fp_mul=hold.get('fp_mul', 1.0))
    # pass 2: leave a margin in the slot like the owner's reference pack (silhouette reads, aura fits)
    m.display['gui'] = fit_transform(m, (20, 24, -45), target=14.5, max_scale=1.6)
    m.display['fixed'] = fit_transform(m, (0, 180, -45), target=14.5, max_scale=1.6)


def voxel_bow(m: Model):
    bow(m, gui_rot=(14, 20, -45))
    m.display['gui'] = fit_transform(m, (14, 20, -45), target=14.5, max_scale=1.6)
