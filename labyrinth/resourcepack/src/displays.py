"""Display transforms per item category.

Hand transforms are derived from the conventions of Minecraft's own handheld/bow/shield/block
items (rotation order XYZ with Z applied first; the client negates rot y/z and pos x for the left
hand), adjusted for our upright 3D geometry.  GUI / ground / item-frame transforms are fitted
automatically from the model's real bounding box so every model is centred and fills the slot.
"""
from __future__ import annotations

from .model import Model, fit_transform, mirror_left


def _t(rot, tr, sc):
    return {'rotation': list(rot), 'translation': list(tr), 'scale': [sc, sc, sc]}


def weapon(m: Model, two_handed=False, gui_rot=(18, 22, -45)):
    # long models (greatswords, staves) are scaled down a little in first person so they don't fill the screen
    top = m.bounds()[1][1]
    fp = 0.68 if top <= 22 else max(0.5, 0.68 * 22.0 / top)
    r3 = _t((0, -90, 10), (0, 4.0, 0.5), 0.9 if two_handed else 0.85)
    r1 = _t((0, -90, -20), (1.13, 3.2, 1.13), round(fp, 3))
    m.display = {
        'thirdperson_righthand': r3, 'thirdperson_lefthand': mirror_left(r3),
        'firstperson_righthand': r1, 'firstperson_lefthand': mirror_left(r1),
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
    weapon(m, two_handed=two_handed, gui_rot=(20, 24, -45))
    m.display['gui'] = fit_transform(m, (20, 24, -45), target=16.5, max_scale=1.6)
    m.display['fixed'] = fit_transform(m, (0, 180, -45), target=15.5, max_scale=1.6)


def voxel_bow(m: Model):
    bow(m, gui_rot=(14, 20, -45))
    m.display['gui'] = fit_transform(m, (14, 20, -45), target=16.0, max_scale=1.6)
