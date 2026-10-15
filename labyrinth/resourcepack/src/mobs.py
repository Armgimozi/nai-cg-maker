"""Mob & boss models (`labyrinth:mob/<id>/<part>`): original procedural cuboid geometry for every
`model.parts[]` entry of mobs.yml / bosses.yml, one shared UV atlas per mob (`textures/mob/<id>.png`).

Contract (ARCHITECTURE §2, GDD §14.3/§14.6):
  * model units: 16 = 1 block; each part's pivot is model (8, 8, 8); elements stay inside −16..32 —
    parts that would not fit are shrunk by s and `display.fixed.scale = 1/s` restores the real size.
  * ItemDisplay renders the item turned 180° about Y, so the entity's FRONT is model −Z and the
    entity's LEFT (+X) is model −X.  Every builder here models faces/claws/blades toward −Z.
  * placement: geometry centre = pivot; arms/tentacles (arm anim) and legs (legs_walk) hang from the
    pivot (top-face centre = pivot); tails start at the pivot and extend backwards (model +Z) or hang
    down when taller than long; parts sharing pivot+anim with an arm are held in that arm's hand.
    Joint forms (new body shapes): `wing` = one wing whose root (shoulder) is the pivot, span along X away
    from the body (out); `neck` = base at the pivot, rising forward (model −Z) and up; `segment` = body
    segment (worm · naga) whose front face is the pivot, extending backwards — the plugin chains
    neck/tail_chain parts and flaps wings about these pivots, so the geometry must start there.
  * part sets: parts with `set: <name>` (leg_l / leg_r …, GDD §14.6) are cut from the ONE design part <name> — the
    design runs for that part exactly as before, then mob_build.SetMesh splits its voxels per member (mid-plane for a
    left/right pair, else geodesic from each foot + nearest joint at the shared root) and each member gets its own
    model with the same origin (= the set pivot), so the standing mob looks the same and every leg turns at its joint.
All shapes, textures and colours are generated here from the YAML style hints (no copied assets).
"""
from __future__ import annotations

import math

from PIL import Image

from .model import El, Model, fit_transform, r4
from .util import (Palette, clamp, darken, fbm, h2, h3, hue_shift, lighten, lum, mix, saturate, stable_seed,
                   vnoise)
from .materials import rune_bit

NS = 'labyrinth'

SHAPE_MATERIAL = {
    'crawler': 'chitin', 'insect': 'chitin', 'humanoid': 'flesh', 'floating': 'ethereal', 'blob': 'gloss',
    'turret': 'stone', 'beast': 'fur', 'serpent': 'scale', 'golem': 'stone', 'wraith': 'cloth',
    'construct': 'metal', 'swarm': 'ethereal', 'colossus': 'stone',
    # new body shapes (dragons · dragonkin · hybrids) — box fallback until the voxel designs land
    'drake': 'scale', 'wyvern': 'scale', 'dragonkin': 'scale', 'naga': 'scale', 'worm': 'chitin',
    'centaur': 'fur', 'harpy': 'fur', 'minotaur': 'fur', 'lich': 'cloth',
}
GLOW_ROLES = {'glow', 'eye', 'core'}


# ───────────────────────────── look / palette ─────────────────────────────

class MobLook:
    def __init__(self, mid, style, boss=False, rank='normal'):
        style = style or {}
        self.mid = mid
        self.pal = Palette(style.get('palette'))
        self.shape = style.get('shape') or 'humanoid'
        self.material = SHAPE_MATERIAL.get(self.shape, 'flesh')
        self.features = set(style.get('features') or [])
        self.boss = boss
        self.rank = rank
        self.seed = stable_seed('mob', mid) & 0xFFFF
        p = self.pal
        main = p.ramp_n(6)
        self.main = main
        a = p.accent
        if lum(a) < 0.35:
            a = lighten(saturate(a, 1.3), 0.35)
        dark = [darken(main[0], 0.55), darken(main[0], 0.3), main[0], main[1], mix(main[1], main[2], 0.5)]
        light = [main[2], main[3], main[4], main[5], lighten(main[5], 0.35)]
        import colorsys
        hue = colorsys.rgb_to_hsv(*(v / 255 for v in a))[0] * 360
        if hue < 75 or hue > 330 or boss is False:
            gold = [(58, 36, 12), (122, 80, 26), (196, 142, 52), (236, 196, 96), (255, 236, 170)]
            gold = [mix(g, a, 0.18) for g in gold]
        else:   # cold palettes get an accent-tinted silver trim instead of gold
            gold = [(34, 38, 48), (84, 92, 110), (150, 160, 178), (206, 214, 228), (250, 252, 255)]
            gold = [mix(g, a, 0.32) for g in gold]
        mid_c = p.ramp[len(p.ramp) // 2]
        metal = [darken(mid_c, 0.7), mix(darken(mid_c, 0.45), (70, 72, 80), 0.6), mix(mid_c, (140, 142, 150), 0.6),
                 mix(lighten(mid_c, 0.3), (190, 192, 200), 0.6), (236, 238, 244)]
        moss = [(26, 40, 16), (48, 74, 26), (86, 122, 44), (138, 170, 72), (196, 216, 132)]
        moss = [mix(m, main[3], 0.25) for m in moss]
        bone = [(70, 60, 46), (128, 114, 92), (184, 170, 142), (222, 212, 186), (246, 240, 222)]
        bone = [mix(b, main[4], 0.2) for b in bone]
        glow = [darken(a, 0.55), darken(a, 0.25), a, lighten(a, 0.3), lighten(a, 0.6), lighten(a, 0.85)]
        paper = [(96, 82, 60), (160, 142, 110), (206, 192, 160), (232, 222, 196), (250, 246, 232)]
        void = [(4, 3, 8), (12, 10, 20), (26, 22, 40), (44, 38, 64), (70, 62, 96)]
        self.ramps = {
            'skin': main, 'dark': p.ramp_n(6, dark), 'light': p.ramp_n(6, light), 'trim': p.ramp_n(6, gold),
            'metal': p.ramp_n(6, metal), 'leaf': p.ramp_n(6, moss), 'bone': p.ramp_n(6, bone),
            'glow': glow, 'eye': glow, 'core': glow, 'paper': p.ramp_n(6, paper), 'void': p.ramp_n(6, void),
            'cloth': main, 'crystal': p.ramp_n(6, [main[1], main[3], a, lighten(a, 0.5), (255, 255, 255)]),
        }
        # second tone (Dyad / dual_tone): hue-rotated copy of the main ramp
        self.alt = [hue_shift(c, 180, 1.0, 1.0) for c in main]
        self.accent = a


# ───────────────────────────── part builder ─────────────────────────────

class PB:
    """Collects elements for one part in pivot-relative real units (origin = pivot, front = −Z)."""

    def __init__(self, part_name):
        self.els: list[El] = []
        self.part = part_name

    def box(self, frm, to, role='skin', rot=None, **kw):
        lo = tuple(float(min(a, b)) for a, b in zip(frm, to))
        hi = tuple(float(max(a, b)) for a, b in zip(frm, to))
        hi = tuple(max(h, l + 0.1) for l, h in zip(lo, hi))
        if rot is not None and len(rot) == 2:
            rot = (rot[0], rot[1], tuple((l + h) / 2 for l, h in zip(lo, hi)))
        if role in GLOW_ROLES:
            kw.setdefault('shade', False)
            kw.setdefault('emission', 15 if role == 'eye' else 12)
            kw.setdefault('glow', True)
        e = El(lo, hi, role, rot=rot, **kw)
        e.data['part'] = self.part
        self.els.append(e)
        return e

    def cbox(self, c, s, role='skin', rot=None, **kw):
        s = [max(0.1, float(v)) for v in s]
        return self.box((c[0] - s[0] / 2, c[1] - s[1] / 2, c[2] - s[2] / 2),
                        (c[0] + s[0] / 2, c[1] + s[1] / 2, c[2] + s[2] / 2), role, rot, **kw)

    def seg(self, p0, p1, t, role='skin', **kw):
        """Bar from p0 to p1 lying in an XY plane (same z) — rotated about Z."""
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = max(0.2, math.hypot(dx, dy))
        c = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, p0[2])
        ang = math.degrees(math.atan2(dy, dx))
        return self.cbox(c, (L, t, t), role, rot=('z', ang, c), **kw)

    def segz(self, p0, p1, t, role='skin', **kw):
        """Bar from p0 to p1 lying in a YZ plane (same x) — rotated about X."""
        dz, dy = p1[2] - p0[2], p1[1] - p0[1]
        L = max(0.2, math.hypot(dz, dy))
        c = (p0[0], (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2)
        ang = -math.degrees(math.atan2(dy, dz))
        return self.cbox(c, (t, t, L), role, rot=('x', ang, c), **kw)

    def bounds(self):
        pts = [p for e in self.els for p in e.corners()]
        if not pts:
            return (0, 0, 0), (0, 0, 0)
        return (tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3)))

    def translate(self, d, start=0):
        for e in self.els[start:]:
            e.frm = tuple(e.frm[i] + d[i] for i in range(3))
            e.to = tuple(e.to[i] + d[i] for i in range(3))
            if e.rot:
                ax, ang, org = e.rot
                e.rot = (ax, ang, tuple(org[i] + d[i] for i in range(3)))

    def remap(self, perm, start=0):
        """Proper axis permutation: perm = ((src_axis, sign) for new x, y, z)."""
        names = 'xyz'

        def mp(p):
            return tuple(p[a] * s for (a, s) in perm)
        for e in self.els[start:]:
            a, b = mp(e.frm), mp(e.to)
            e.frm = tuple(min(a[i], b[i]) for i in range(3))
            e.to = tuple(max(a[i], b[i]) for i in range(3))
            if e.rot:
                ax, ang, org = e.rot
                src = names.index(ax)
                for k, (a_, s_) in enumerate(perm):
                    if a_ == src:
                        e.rot = (names[k], ang * s_, mp(org))
                        break


def _cross(pb, c, w, h, d, role='skin', k=0.7, **kw):
    """Chamfered column: two crossed boxes (second 0.1 taller so caps never z-fight)."""
    pb.cbox(c, (w, h, d * k), role, **kw)
    pb.cbox(c, (w * k, h + 0.1, d), role, **kw)


# ───────────────────────────── forms ─────────────────────────────

class PC:
    """Part context handed to form builders."""

    def __init__(self, part, look, boss, out, hang, arm_h=None, arm_w=None):
        self.part = part
        self.name = part.get('name', 'part')
        self.anim = part.get('anim', 'static')
        self.look = look
        self.boss = boss
        self.out = out            # model-space X sign pointing away from the body centre (+1/−1)
        self.hang = hang
        self.arm_h = arm_h        # set when held in a hand
        self.arm_w = arm_w
        self.seed = stable_seed(look.mid, self.name) & 0xFFFF

    def r(self, k):
        return h2(self.seed, k, 77)


def f_box(pb, w, h, d, c):
    pb.cbox((0, 0, 0), (w, h, d), 'skin')
    if min(w, h) >= 6 and c.look.material in ('stone', 'metal'):
        # chiselled top lip
        pb.cbox((0, h / 2 - 0.6, 0), (w + 0.6, 1.2, d + 0.6), 'dark' if c.look.material == 'stone' else 'metal')


def f_rounded(pb, w, h, d, c, role='skin'):
    b = clamp(min(w, h, d) * 0.18, 0.5, 3.0)
    pb.cbox((0, 0, 0), (w, h - 2 * b, d - 2 * b), role)
    pb.cbox((0, 0, 0), (w - 2 * b, h, d - 2 * b), role)
    pb.cbox((0, 0, 0), (w - 2 * b, h - 2 * b, d), role)


def f_sphere(pb, w, h, d, c, role='skin'):
    n = 3 if h < 6 else 4 if h < 10 else 6 if h < 22 else 8
    for k in range(n):
        y0 = -h / 2 + h * k / n
        t = ((k + 0.5) / n) * 2 - 1
        r = math.sqrt(max(0.08, 1 - t * t))
        _cross(pb, (0, y0 + h / n / 2, 0), max(1, w * r), h / n, max(1, d * r), role, k=0.72)


def f_cylinder(pb, w, h, d, c, role='skin'):
    _cross(pb, (0, 0, 0), w, h, d, role, k=0.6)
    if h >= 8:
        pb.cbox((0, h / 2 - 0.75, 0), (w * 0.9 + 0.6, 1.5, d * 0.9 + 0.6), 'dark')
        pb.cbox((0, -h / 2 + 0.75, 0), (w * 0.9 + 0.6, 1.5, d * 0.9 + 0.6), 'dark')


def f_cone(pb, w, h, d, c, role='skin'):
    n = max(3, min(6, int(h / 2)))
    for k in range(n):
        f = 1 - k / n
        pb.cbox((0, -h / 2 + h * (k + 0.5) / n, -k * 0.25), (max(0.6, w * f), h / n, max(0.6, d * f)), role)


def _spike(pb, base, axis, length, thick, role='bone', segs=3):
    # tapered spike along axis ('y' up, '-z' forward, 'x'/'-x' sideways)
    vec = {'y': (0, 1, 0), '-z': (0, 0, -1), 'z': (0, 0, 1), 'x': (1, 0, 0), '-x': (-1, 0, 0), '-y': (0, -1, 0)}[axis]
    seg_l = length / segs
    for k in range(segs):
        t = thick * (1 - k / (segs + 0.6))
        cpos = tuple(base[i] + vec[i] * seg_l * (k + 0.5) for i in range(3))
        size = tuple(seg_l + 0.05 if vec[i] else max(0.4, t) for i in range(3))
        pb.cbox(cpos, size, role)


def f_spike(pb, w, h, d, c):
    axis = '-z' if d >= h and d >= w else 'y'
    n = 1 if min(w, h, d) <= 3 and max(w, h, d) < 10 else 3 + int(c.r(1) * 3)
    if n == 1:
        L = d if axis == '-z' else h
        base = (0, 0, L / 2) if axis == '-z' else (0, -L / 2, 0)
        _spike(pb, base, axis, L, min(w, h if axis == '-z' else d))
        return
    pb.cbox((0, -h / 2 + 1, 0), (w * 0.6, 2, d * 0.6), 'dark')
    for k in range(n):
        a = 2 * math.pi * k / n + c.r(k) * 0.6
        x, z = math.cos(a) * w * 0.28, math.sin(a) * d * 0.28
        L = h * (0.6 + 0.4 * c.r(k + 9))
        _spike(pb, (x, -h / 2 + 1.5, z), 'y', L, max(1.0, min(w, d) * 0.22))


def f_slab(pb, w, h, d, c, role='skin'):
    t = max(0.6, d)
    pb.cbox((0, 0, 0), (w, h, t), role)
    if w >= 6 and h >= 6:
        rim = 'trim' if (c.boss or 'elite_trim' in c.look.features) else 'dark'
        for sx in (-1, 1):
            pb.cbox((sx * (w / 2 - 0.5), 0, -t / 2 - 0.25), (1, h, 0.5), rim)
        for sy in (-1, 1):
            pb.cbox((0, sy * (h / 2 - 0.5), -t / 2 - 0.25), (w - 2, 1, 0.5), rim)
        pb.cbox((0, 0, -t / 2 - 0.5), (min(w, h) * 0.3, min(w, h) * 0.3, 1.0), rim)


def f_shell(pb, w, h, d, c, role='skin'):
    n = 4 if h < 10 else 5
    pb.cbox((0, -h / 2 + 0.5, 0), (w + 1, 1, d + 1), 'dark')
    for k in range(n):
        t = k / n
        r = math.sqrt(max(0.05, 1 - t * t))
        pb.cbox((0, -h / 2 + 1 + (h - 1) * (k + 0.5) / n, 0), (max(1, w * r), (h - 1) / n, max(1, d * r)), role)
    # dorsal ridge plates
    for k in range(3):
        z = -d * 0.3 + k * d * 0.3
        pb.cbox((0, h / 2 + 0.3, z), (max(1, w * 0.18), 1.2, d * 0.22), 'light')


def f_cap(pb, w, h, d, c, role='skin'):
    pb.cbox((0, -h / 2 + 0.4, 0), (w * 0.86, 0.8, d * 0.86), 'dark')            # gills underside
    pb.cbox((0, -h / 2 + h * 0.2, 0), (w, h * 0.3, d), role)
    pb.cbox((0, -h / 2 + h * 0.5, 0), (w * 0.8, h * 0.3, d * 0.8), role)
    pb.cbox((0, -h / 2 + h * 0.8, 0), (w * 0.5, h * 0.36, d * 0.5), role)
    if w >= 10:
        for k in range(6):   # drooping rim lobes
            a = 2 * math.pi * k / 6
            pb.cbox((math.cos(a) * w * 0.44, -h / 2 + h * 0.08, math.sin(a) * d * 0.44), (w * 0.16, h * 0.16, d * 0.16), role)


def f_cloak(pb, w, h, d, c, role='cloth'):
    n = 4
    for k in range(n):
        f = 0.62 + 0.38 * (k + 1) / n
        y = h / 2 - h * (k + 0.5) / n
        pb.cbox((0, y, 0), (w * f, h / n + 0.05, d * f), role)
    tatter = 'tattered_cloth' in c.look.features or c.look.shape == 'wraith' or 'veil' in c.look.features
    if tatter:
        for k in range(7):
            x = -w / 2 + w * (k + 0.5) / 7
            L = 1.5 + c.r(k) * 3
            pb.cbox((x, -h / 2 - L / 2, -d / 2 + 0.4), (w / 7 * 0.8, L, 0.6), role)
            pb.cbox((x, -h / 2 - L / 2 + 0.5, d / 2 - 0.4), (w / 7 * 0.8, L - 1, 0.6), role)
    # collar
    pb.cbox((0, h / 2 + 0.5, 0), (w * 0.7, 1.2, d * 0.72), 'trim' if c.boss else 'dark')


def f_arm(pb, w, h, d, c):
    shape = c.look.shape
    role = 'cloth' if shape == 'wraith' else 'skin'
    upper = h * 0.48
    pb.cbox((0, -upper / 2, 0), (w, upper, d), role)
    fw = w * (1.15 if shape in ('golem', 'colossus') else 0.88)
    pb.cbox((0, -upper - h * 0.36 / 2, 0), (fw, h * 0.36 + 0.05, fw * d / w), role)
    hand = 'dark' if shape in ('golem', 'construct', 'colossus') else 'skin'
    pb.cbox((0, -h + h * 0.08, -0.2), (w * 1.05, h * 0.16 + 0.05, d * 1.1), hand)
    if shape == 'wraith':
        # wide tattered sleeve cuff
        pb.cbox((0, -upper - h * 0.2, 0), (w * 1.5, h * 0.18, d * 1.5), 'cloth')
    if c.boss or shape in ('golem', 'colossus', 'construct') and w >= 6:
        pr = 'trim' if c.boss else 'dark'
        pb.cbox((c.out * 0.4, -h * 0.08, 0), (w * 1.45, h * 0.2, d * 1.35), pr)
        if c.boss:
            _spike(pb, (c.out * w * 0.45, h * 0.02, 0), 'y', h * 0.18, w * 0.3, 'trim', segs=2)
            pb.cbox((0, -upper - h * 0.14, 0), (fw * 1.12, h * 0.07, fw * d / w * 1.12), 'trim')


def f_claw(pb, w, h, d, c, role='bone'):
    pb.cbox((0, 0, d * 0.35), (w * 0.6, h * 0.8, d * 0.3), 'dark')
    for s in (-1, 1):
        x0 = s * w * 0.28
        pb.cbox((x0, 0, d * 0.05), (max(0.8, w * 0.22), h * 0.7, d * 0.45), role, rot=('y', -s * 18))
        pb.cbox((x0 * 0.55, -h * 0.05, -d * 0.36), (max(0.6, w * 0.16), h * 0.5, d * 0.32), role, rot=('y', s * 30))


def _blade_kind(name):
    n = name.lower()
    for key, kind in (('hammer', 'hammer'), ('mace', 'hammer'), ('scepter', 'staff'), ('staff', 'staff'),
                      ('wand', 'staff'), ('quill', 'quill'), ('anchor', 'anchor'), ('key', 'anchor'),
                      ('pick', 'pick'), ('hand_blade', 'pointer'), ('hook', 'hook'), ('ladle', 'staff'),
                      ('scythe', 'scythe'), ('axe', 'axe'), ('spear', 'spear'), ('lance', 'spear'),
                      ('pike', 'spear'), ('bow', 'bow')):
        if key in n:
            return kind
    return 'sword'


def f_blade(pb, w, h, d, c):
    """Built along +Y with the grip at y=0 (rotated/placed later)."""
    kind = _blade_kind(c.name)
    g = 'dark'
    if kind == 'hammer':
        pb.cbox((0, h * 0.4, 0), (1.6, h * 0.8, 1.6), g)
        pb.cbox((0, h * 0.84, 0), (w, h * 0.3, d), 'metal')
        pb.cbox((0, h * 0.84, 0), (w + 0.4, h * 0.06, d + 0.4), 'trim')
        pb.cbox((0, h * 0.72, 0), (w * 0.7, h * 0.05, d * 0.7), 'trim')
        if c.boss:
            pb.cbox((0, h * 0.84, -d / 2 - 0.3), (w * 0.4, h * 0.14, 0.6), 'glow')
    elif kind == 'staff':
        pb.cbox((0, h * 0.42, 0), (min(2, w * 0.5), h * 0.84, min(2, d * 0.5)), g)
        pb.cbox((0, h * 0.86, 0), (w, 1.2, d), 'trim')
        pb.cbox((0, h * 0.93, 0), (w * 0.7, w * 0.7, d * 0.7), 'glow', rot=('y', 45))
        for s in (-1, 1):
            pb.cbox((s * w * 0.45, h * 0.94, 0), (0.6, h * 0.1, 0.6), 'trim')
    elif kind == 'quill':
        pb.cbox((0, h * 0.5, 0), (0.6, h, 0.6), 'light')
        pb.cbox((0, h * 0.62, 0), (0.3, h * 0.7, d), 'light')
        pb.cbox((0, h * 0.62, 0), (w * 0.6, h * 0.6, 0.3), 'paper')
        pb.cbox((0, h * 0.04, 0), (0.8, h * 0.1, 0.8), 'void')
    elif kind == 'anchor':
        pb.cbox((0, h * 0.5, 0), (2, h, min(2, d)), 'metal')
        pb.cbox((0, h * 0.95, 0), (w * 0.4, w * 0.4, d), 'trim')
        pb.cbox((0, h * 0.75, 0), (w * 0.6, 1.4, d), 'metal')
        for s in (-1, 1):
            pb.cbox((s * w * 0.3, h * 0.1, 0), (w * 0.45, 1.8, d), 'metal', rot=('z', -s * 30))
            pb.cbox((s * w * 0.46, h * 0.2, 0), (1.6, h * 0.12, d), 'metal')
        pb.cbox((0, h * 0.55, -d / 2 - 0.2), (0.8, h * 0.5, 0.4), 'glow')
    elif kind == 'spear':
        # held a third of the way up the shaft (butt behind the hand), leaf blade at the tip
        pb.cbox((0, h * 0.2, 0), (1.2, h, 1.2), g)                                        # shaft −0.3h … 0.7h
        pb.cbox((0, h * 0.68, 0), (max(1.4, w * 0.5), 1.0, max(1.4, d * 0.5)), 'trim')
        pb.cbox((0, h * 0.8, 0), (max(1.2, w * 0.8), h * 0.2, max(0.6, d * 0.35)), 'metal')
        pb.cbox((0, h * 0.93, 0), (max(0.6, w * 0.4), h * 0.08, max(0.4, d * 0.25)), 'metal')
        pb.cbox((0, h * 0.8, -max(0.6, d * 0.35) / 2 - 0.1), (0.3, h * 0.16, 0.2), 'light')
    elif kind == 'bow':
        # built along Z (the hand remap turns it upright): grip at the origin, limbs curving back
        # toward the archer (+Y here = forward after the remap), string between the tips
        t = max(0.8, min(1.6, w * 0.45))
        L = h
        bulge = max(1.5, d * 0.45)
        pb.cbox((0, 0, 0), (t * 1.3, t * 1.3, 2.4), 'dark')
        for s_ in (-1, 1):
            mid = (0, -bulge * 0.25, s_ * L * 0.28)
            tip = (0, -bulge, s_ * L * 0.5)
            pb.segz((0, 0, s_ * 1.0), mid, t, 'skin')
            pb.segz(mid, tip, t * 0.8, 'skin')
            pb.cbox(tip, (t * 0.9, t * 0.9, t * 0.9), 'trim')
        pb.cbox((0, -bulge, 0), (0.3, 0.3, L * 0.98), 'light')
    elif kind == 'pick':
        pb.cbox((0, h * 0.45, 0), (1.4, h * 0.9, 1.4), g)
        for s in (-1, 1):
            pb.cbox((s * w * 0.25, h * 0.88, 0), (w * 0.5, 1.6, 1.4), 'metal', rot=('z', -s * 14))
    elif kind == 'pointer':
        pb.cbox((0, h * 0.06, 0), (w * 0.6, h * 0.12, max(0.6, d)), 'trim')
        pb.cbox((0, h * 0.5, 0), (w * 0.35, h * 0.8, max(0.4, d * 0.6)), 'metal')
        pb.cbox((0, h * 0.86, 0), (w, w, max(0.4, d * 0.6)), 'trim', rot=('z', 45))
        pb.cbox((0, h * 0.5, -max(0.4, d * 0.6) / 2 - 0.15), (w * 0.15, h * 0.7, 0.3), 'glow')
    else:
        bw = max(1.0, w * 0.6)
        pb.cbox((0, h * 0.09, 0), (1.4, h * 0.18, 1.4), g)
        pb.cbox((0, h * 0.2, 0), (w, 1.4, max(1.4, d + 0.6)), 'trim')
        pb.cbox((0, h * 0.58, 0), (bw, h * 0.72, max(0.6, d * 0.45)), 'metal')
        pb.cbox((0, h * 0.95, 0), (bw * 0.5, h * 0.06, max(0.5, d * 0.35)), 'metal')
        pb.cbox((0, h * 0.58, -max(0.6, d * 0.45) / 2 - 0.1), (bw * 0.22, h * 0.6, 0.2), 'light')


def f_leg_pair(pb, w, h, d, c):
    lw = w * 0.4
    for s in (-1, 1):
        x = s * w / 4
        pb.cbox((x, -h * 0.25, 0), (lw, h * 0.5, d), 'dark')
        pb.cbox((x, -h * 0.66, 0), (lw * 0.86, h * 0.34, d * 0.86), 'dark')
        pb.cbox((x, -h * 0.92, -d * 0.12), (lw * 1.06, h * 0.16, d * 1.25), 'skin' if c.look.material != 'stone' else 'dark')
        if c.boss:
            pb.cbox((x, -h * 0.5, -d / 2 - 0.3), (lw * 0.8, h * 0.16, 0.6), 'trim')
    pb.box((-w / 2, 0, -d / 2), (w / 2, -h * 0.12, d / 2), 'dark')   # hip band
    pb.translate((0, h / 2, 0))   # centred; caller re-hangs when legs_walk


def f_leg_quad(pb, w, h, d, c):
    lw = max(1.5, min(w, d) * 0.24)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = sx * (w / 2 - lw / 2), sz * (d / 2 - lw / 2)
            pb.cbox((x, h * 0.18, z), (lw, h * 0.64, lw), 'skin')
            pb.cbox((x, -h * 0.28, z), (lw * 0.82, h * 0.36, lw * 0.82), 'dark')
            pb.cbox((x, -h / 2 + h * 0.06, z - 0.3), (lw * 1.1, h * 0.12, lw * 1.3), 'dark')


def f_leg_many(pb, w, h, d, c, n_side):
    t = max(0.9, min(2.2, w * 0.06))
    for s in (-1, 1):
        for k in range(n_side):
            z = -d * 0.36 + d * 0.72 * k / max(1, n_side - 1)
            root = (s * w * 0.1, h * 0.05, z)
            knee = (s * w * 0.32, h * 0.5, z * 1.1)
            foot = (s * w * 0.5, -h * 0.5, z * 1.25)
            pb.seg(root, knee, t, 'skin')
            pb.seg(knee, foot, t * 0.8, 'dark')
            pb.cbox(knee, (t * 1.25, t * 1.25, t * 1.25), 'light')


def f_wing_pair(pb, w, h, d, c):
    role = 'cloth' if c.look.shape in ('wraith',) else 'skin'
    eyespots = 'wing_eyespots' in c.look.features or 'clockface_wings' in c.look.features
    for s in (-1, 1):
        x = s * w * 0.27
        pb.cbox((x, h * 0.1, 0), (w * 0.44, h * 0.7, max(0.4, d * 0.3)), role)
        pb.cbox((s * w * 0.4, -h * 0.25, 0), (w * 0.2, h * 0.4, max(0.4, d * 0.3)), role)
        pb.cbox((s * w * 0.25, h * 0.42, -0.1), (w * 0.5, 0.8, max(0.6, d * 0.5)), 'dark')   # leading bone
        if eyespots:
            pb.cbox((x, h * 0.1, -max(0.4, d * 0.3) / 2 - 0.1), (w * 0.14, w * 0.14, 0.2), 'glow')


def f_wing(pb, w, h, d, c):
    """One wing: root (shoulder) at the pivot, span w along X away from the body (c.out), chord d along Z
    (leading edge = front, model −Z), thin in Y.  Arm bone along the leading edge, three finger bones fanning
    back, a stepped membrane between them and a small wrist claw."""
    o = c.out
    t = max(0.5, min(h, 1.4))
    role = 'cloth' if c.look.shape in ('wraith', 'lich') else 'skin'
    lead = -d * 0.4
    pb.cbox((o * w * 0.25, 0, lead), (w * 0.5, t * 1.5, t * 1.5), 'dark')            # upper arm
    pb.cbox((o * w * 0.68, t * 0.2, lead + 0.2), (w * 0.38, t * 1.3, t * 1.3), 'dark')  # forearm
    pb.cbox((o * w * 0.86, t * 0.6, lead - 0.3), (t * 1.2, t * 1.4, t * 1.6), 'bone')  # wrist claw
    for k, (f, L) in enumerate(((0.98, 0.55), (0.78, 0.8), (0.52, 0.9))):
        pb.cbox((o * w * f, -t * 0.1, lead + d * L / 2), (t, t, d * L), 'dark')        # finger bones
    for k, (x0, x1, L) in enumerate(((0.0, 0.55, 0.85), (0.5, 0.8, 0.75), (0.76, 1.0, 0.5))):
        cx = o * w * (x0 + x1) / 2
        pb.cbox((cx, -t * 0.25, lead + d * L / 2), (w * (x1 - x0), max(0.3, t * 0.4), d * L), role)
    if 'wing_eyespots' in c.look.features or 'clockface_wings' in c.look.features:
        pb.cbox((o * w * 0.6, -t * 0.25 - 0.25, lead + d * 0.4), (w * 0.14, 0.2, w * 0.14), 'glow')


def f_neck(pb, w, h, d, c):
    """Neck: base at the pivot, rising forward (model −Z) by d and up by h, thinning toward the head."""
    n = 4
    step = math.hypot(d, h) / n
    for k in range(n):
        f = (k + 0.5) / n
        s = 1 - 0.22 * f
        pb.cbox((0, h * f, -d * f), (w * s, w * s, step + w * 0.5), 'skin' if k % 2 == 0 else 'dark')
        pb.cbox((0, h * f - w * s * 0.45, -d * f), (w * s * 0.6, 0.5, step), 'light')   # throat plates


def f_segment(pb, w, h, d, c):
    """Body segment (worm · naga coil): front face centre at the pivot, extending backwards (model +Z)."""
    pb.cbox((0, 0, d * 0.5), (w, h * 0.84, d * 0.94), 'skin')
    pb.cbox((0, 0, d * 0.5), (w * 0.84, h, d * 0.86), 'skin')
    pb.cbox((0, -h * 0.4, d * 0.5), (w * 0.66, h * 0.22, d * 0.96), 'light')          # belly scutes
    pb.cbox((0, 0, 0.4), (w * 1.04, h * 0.9, 0.8), 'dark')                             # joint ring


def f_tail(pb, w, h, d, c):
    hang = h > d * 1.4
    n = 5 if max(h, d) >= 12 else 3
    L = h if hang else d
    for k in range(n):
        f = 1 - 0.55 * k / n
        if hang:
            pb.cbox((0, -L * (k + 0.5) / n, 0), (w * f, L / n + 0.05, d * f), 'skin' if k % 2 == 0 else 'dark')
        else:
            pb.cbox((0, -k * 0.2, L * (k + 0.5) / n), (w * f, h * f, L / n + 0.05), 'skin' if k % 2 == 0 else 'dark')
    if hang:   # pendulum weight / tail tip
        pb.cbox((0, -L - w * 0.4, 0), (w * 1.4, w * 1.0, max(1, d * 1.0)), 'trim' if c.boss else 'light')
    else:
        pb.cbox((0, -n * 0.2, L + 0.6), (w * 0.4, h * 0.4, 1.2), 'glow' if c.look.shape == 'floating' else 'light')


def f_fin(pb, w, h, d, c):
    # crest: stepped triangle along Z
    n = 4
    for k in range(n):
        f = 1 - k / n
        pb.cbox((0, -h / 2 + h * (k + 0.5) / n, d * 0.1 * k), (max(0.4, w), h / n + 0.05, max(0.6, d * f)), 'light')


def f_tentacles(pb, w, h, d, c):
    if c.hang:
        n = 3
        for k in range(n):
            x = (k - 1) * w * 0.3
            for j in range(4):
                f = 1 - j * 0.18
                pb.cbox((x + math.sin(j + k) * 0.6, -h * (j + 0.5) / 4, (k - 1) * 0.6),
                        (w * 0.34 * f, h / 4 + 0.05, d * 0.34 * f), 'skin' if j % 2 == 0 else 'dark')
        pb.cbox((0, -0.8, 0), (w * 0.9, 1.6, d * 0.9), 'dark')
        return
    # spread roots / veins radiating from the centre and arching down to the floor
    n = 8
    t = max(1.2, min(w, d) * 0.07)
    hub_y = h * 0.3
    pb.cbox((0, hub_y, 0), (w * 0.22, h * 0.4, d * 0.22), 'dark')
    role_tip = 'glow' if ({'sculk_veins', 'heartbeat_glow', 'emissive_core'} & c.look.features) else 'dark'
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        L = 0.42 + 0.06 * c.r(k)
        mid = (ca * w * L * 0.55, hub_y + h * 0.12, sa * d * L * 0.55)
        end = (ca * w * L, -h / 2 + t / 2, sa * d * L)
        if k % 2 == 0:
            if abs(ca) > 0.5:
                pb.seg((0, hub_y, 0), (mid[0], mid[1], 0), t, 'skin')
                pb.seg((mid[0], mid[1], 0), (end[0], end[1], 0), t * 0.8, 'skin')
            else:
                pb.segz((0, hub_y, 0), (0, mid[1], mid[2]), t, 'skin')
                pb.segz((0, mid[1], mid[2]), (0, end[1], end[2]), t * 0.8, 'skin')
        else:
            Lh = math.hypot(mid[0], mid[2])
            pb.cbox((mid[0] / 2, mid[1], mid[2] / 2), (Lh, t, t), 'skin', rot=('y', -math.degrees(a)))
            pb.box((mid[0] - t / 2, end[1], mid[2] - t / 2), (mid[0] + t / 2, mid[1], mid[2] + t / 2), 'skin')
            end = (mid[0], end[1], mid[2])
        pb.cbox(end, (t * 1.4, t * 0.8, t * 1.4), role_tip)


def f_horn_pair(pb, w, h, d, c):
    t = max(1.0, min(d, w * 0.12))
    for s in (-1, 1):
        base = (s * w * 0.18, -h / 2 + t, 0)
        mid = (s * w * 0.36, h * 0.05, 0)
        tip = (s * w * 0.48, h / 2, -d * 0.2)
        pb.seg(base, mid, t * 1.2, 'bone')
        pb.seg(mid, tip, t * 0.8, 'bone')
        pb.cbox(tip, (t * 0.7, t * 0.7, t * 0.7), 'glow' if c.boss else 'light')


def f_ring(pb, w, h, d, c, role=None):
    role = role or ('trim' if c.boss else 'metal')
    if min(w, h, d) == d and d < h * 0.6 and h > 4:   # vertical ring (XY plane)
        if w > h * 1.8:   # spectacles: two small rings
            for s in (-1, 1):
                _ring_xy(pb, s * w / 4, w / 2 * 0.9, h, max(0.4, d), role, n=8)
            pb.cbox((0, 0, 0), (w * 0.12, 0.5, max(0.4, d)), role)
            return
        _ring_xy(pb, 0, w, h, max(0.6, d), role)
        return
    n = 12 if max(w, d) < 24 else 16
    R = max(w, d) / 2
    th = max(0.8, min(R * 0.18, 3))
    seg_len = 2 * math.pi * R / n * 1.08
    for k in range(n):
        a = 360.0 * k / n
        ra = math.radians(a)
        cx, cz = math.cos(ra) * (R - th / 2) * (w / max(w, d)), math.sin(ra) * (R - th / 2) * (d / max(w, d))
        ang_raw = -a
        ang = ((ang_raw + 45) % 90) - 45
        swap = (round((ang_raw - ang) / 90) % 2) != 0
        sz = (seg_len, max(0.4, h), th) if swap else (th, max(0.4, h), seg_len)
        pb.cbox((cx, 0, cz), sz, role, rot=('y', ang))
        if k % 4 == 0:
            pb.cbox((cx, h / 2 + 0.6, cz), (th * 0.9, 1.2, th * 0.9), 'glow' if c.boss else 'light', rot=('y', ang))


def _ring_xy(pb, x0, w, h, t, role, n=10):
    R = min(w, h) / 2
    th = max(0.6, R * 0.22)
    seg_len = 2 * math.pi * R / n * 1.1
    for k in range(n):
        a = 360.0 * k / n
        ra = math.radians(a)
        cx, cy = x0 + math.cos(ra) * (R - th / 2) * (w / min(w, h)), math.sin(ra) * (R - th / 2) * (h / min(w, h))
        ang = ((a + 90 + 45) % 90) - 45
        swap = (round((a + 90 - ang) / 90) % 2) != 0
        sz = (th, seg_len, t) if swap else (seg_len, th, t)
        pb.cbox((cx, cy, 0), sz, role, rot=('z', ang))


def f_crystal_cluster(pb, w, h, d, c, role='crystal'):
    n = 5 if max(w, h) >= 10 else 3
    pb.cbox((0, -h / 2 + 0.6, 0), (w * 0.7, 1.2, d * 0.7), 'dark')
    for k in range(n):
        if k == 0:
            x = z = 0.0
            L = h
            tilt = 0
        else:
            a = 2 * math.pi * k / (n - 1) + c.r(k)
            x, z = math.cos(a) * w * 0.28, math.sin(a) * d * 0.28
            L = h * (0.45 + 0.35 * c.r(k + 5))
            tilt = -25 if x > 0 else 25
        t = max(1.0, min(w, d) * (0.36 if k == 0 else 0.22))
        base_y = -h / 2 + 1
        cy = base_y + L * 0.42
        pb.cbox((x, cy, z), (t, L * 0.84, t), role, rot=('z', tilt, (x, base_y, z)), emission=8, shade=True)
        pb.cbox((x, base_y + L * 0.9, z), (t * 0.55, L * 0.16, t * 0.55), 'glow', rot=('z', tilt, (x, base_y, z)))


def f_leaf_cluster(pb, w, h, d, c):
    pb.cbox((0, -h * 0.1, 0), (w * 0.8, h * 0.6, d * 0.8), 'leaf')
    n = 10
    for k in range(n):
        a = 2 * math.pi * k / n + c.r(k)
        r = 0.32 + 0.12 * c.r(k + 3)
        x, z = math.cos(a) * w * r, math.sin(a) * d * r
        y = -h / 2 + h * (0.25 + 0.55 * c.r(k + 7))
        s = (w * 0.24, h * 0.32, d * 0.24)
        pb.cbox((x, y, z), s, 'leaf', rot=('y', 45 * c.r(k + 11)))
    for k in range(5):   # hanging fronds
        a = 2 * math.pi * k / 5 + 0.3
        pb.cbox((math.cos(a) * w * 0.42, -h / 2 - 1.2, math.sin(a) * d * 0.42), (1.2, 2.6, 1.2), 'leaf')


def f_eye(pb, w, h, d, c):
    f_sphere(pb, w, h, d, c, role='eye')
    for e in pb.els:
        e.role = 'eyeball'
        e.glow = True
        e.emission = 10
        e.shade = False
    pb.cbox((0, 0, -d / 2 - 0.6), (w * 0.42, h * 0.42, 1.2), 'core', emission=15)
    pb.cbox((0, 0, -d / 2 - 1.25), (w * 0.16, h * 0.3, 0.2), 'void')


def f_skull(pb, w, h, d, c):
    pb.cbox((0, h * 0.12, 0), (w, h * 0.76, d), 'bone')
    pb.cbox((0, -h * 0.34, -d * 0.08), (w * 0.72, h * 0.3, d * 0.8), 'bone')
    for s in (-1, 1):
        pb.cbox((s * w * 0.22, h * 0.12, -d / 2 - 0.1), (w * 0.26, h * 0.24, 0.2), 'void')
        pb.cbox((s * w * 0.22, h * 0.1, -d / 2 - 0.2), (w * 0.08, h * 0.08, 0.2), 'eye')
    for k in range(4):
        pb.cbox((-w * 0.24 + k * w * 0.16, -h * 0.22, -d * 0.48 - 0.1), (w * 0.08, h * 0.1, 0.4), 'light')


def f_book(pb, w, h, d, c):
    # an open floating tome: two cover boards in a shallow V + page block; extra small tomes when wide
    for s in (-1, 1):
        pb.cbox((s * w * 0.25, 0, 0), (w * 0.5, max(0.6, h * 0.25), d), 'skin', rot=('z', s * 12, (0, 0, 0)))
        pb.cbox((s * w * 0.23, h * 0.25, 0), (w * 0.44, max(0.6, h * 0.35), d * 0.9), 'paper',
                rot=('z', s * 12, (0, 0, 0)))
        pb.cbox((s * w * 0.48, 0, -d / 2 + 0.6), (0.5, max(0.6, h * 0.3), 1.2), 'trim', rot=('z', s * 12, (0, 0, 0)))
    pb.cbox((0, -h * 0.05, 0), (1.2, max(0.6, h * 0.35), d), 'dark')
    pb.cbox((0, h * 0.5, 0), (w * 0.12, 0.3, d * 0.6), 'glow')


def f_gear(pb, w, h, d, c):
    vertical = d <= min(w, h)
    t = max(0.8, min(w, h, d)) if vertical else max(0.8, h)
    R = (min(w, h) if vertical else min(w, d)) / 2
    role = 'trim' if c.boss or 'brass_trim' in c.look.features else 'metal'
    if vertical:
        _cross(pb, (0, 0, 0), R * 1.6, R * 1.6, t, role, k=0.62)
        pb.cbox((0, 0, -t / 2 - 0.15), (R * 1.1, R * 1.1, 0.3), 'paper' if 'clockface' in c.name or 'clock' in c.look.mid else 'dark')
        n = 10
        for k in range(n):
            a = 360.0 * k / n
            ra = math.radians(a)
            ang = ((a + 45) % 90) - 45
            pb.cbox((math.cos(ra) * R * 0.88, math.sin(ra) * R * 0.88, 0), (R * 0.3, R * 0.3, t * 0.9), role, rot=('z', ang))
        pb.cbox((0, R * 0.25, -t / 2 - 0.35), (0.6, R * 0.6, 0.3), 'void')
        pb.cbox((R * 0.18, 0, -t / 2 - 0.4), (R * 0.45, 0.6, 0.3), 'void')
        pb.cbox((0, 0, -t / 2 - 0.5), (1.2, 1.2, 0.4), 'glow')
    else:
        _cross(pb, (0, 0, 0), R * 1.6, t, R * 1.6, role, k=0.62)
        for k in range(10):
            a = 360.0 * k / 10
            ra = math.radians(a)
            ang = ((a + 45) % 90) - 45
            pb.cbox((math.cos(ra) * R * 0.88, 0, math.sin(ra) * R * 0.88), (R * 0.3, t * 0.9, R * 0.3), role, rot=('y', ang))


def f_lantern(pb, w, h, d, c):
    pb.cbox((0, 0, 0), (w * 0.62, h * 0.6, d * 0.62), 'core')
    for sx in (-1, 1):
        for sz in (-1, 1):
            pb.cbox((sx * w * 0.42, 0, sz * d * 0.42), (w * 0.16, h * 0.66, d * 0.16), 'metal')
    pb.cbox((0, h * 0.38, 0), (w, h * 0.14, d), 'metal')
    pb.cbox((0, -h * 0.38, 0), (w, h * 0.14, d), 'metal')
    pb.cbox((0, h * 0.5, 0), (w * 0.5, h * 0.1, d * 0.5), 'trim' if c.boss else 'dark')
    pb.cbox((0, h * 0.56, 0), (w * 0.15, h * 0.12, 0.5), 'metal')


FORMS = {
    'box': f_box, 'rounded': f_rounded, 'sphere': f_sphere, 'cylinder': f_cylinder, 'cone': f_cone,
    'spike': f_spike, 'slab': f_slab, 'shell': f_shell, 'cap': f_cap, 'cloak': f_cloak, 'arm': f_arm,
    'claw': f_claw, 'blade': f_blade, 'leg_pair': f_leg_pair, 'leg_quad': f_leg_quad,
    'leg_six': lambda pb, w, h, d, c: f_leg_many(pb, w, h, d, c, 3),
    'leg_eight': lambda pb, w, h, d, c: f_leg_many(pb, w, h, d, c, 4),
    'wing_pair': f_wing_pair, 'tail': f_tail, 'fin': f_fin, 'tentacle_cluster': f_tentacles,
    'horn_pair': f_horn_pair, 'ring': f_ring, 'crystal_cluster': f_crystal_cluster, 'leaf_cluster': f_leaf_cluster,
    'eye': f_eye, 'skull': f_skull, 'book': f_book, 'gear': f_gear, 'lantern': f_lantern,
    'wing': f_wing, 'neck': f_neck, 'segment': f_segment,
}


# ───────────────────────────── feature geometry ─────────────────────────────

def _is_head(p):
    return p.get('name') == 'head' or (p.get('anim') == 'head' and p.get('form') in ('box', 'rounded', 'sphere', 'skull', 'lantern', 'cone'))


def _is_body(p):
    return p.get('anim') == 'body' or p.get('name') in ('body', 'torso', 'shell', 'abdomen')


def add_features(pb, part, c, w, h, d, primary_head, primary_body):
    F = c.look.features
    name = part.get('name')
    form = part.get('form')
    top = pb.bounds()[1][1]
    front = pb.bounds()[0][2]
    if primary_head:
        ey = h * 0.12
        es = max(0.8, min(2.4, w * 0.14))
        ex = w * 0.22
        if 'hollow_eyes' in F or 'hollow_mask' in F:
            for s in (-1, 1):
                pb.cbox((s * ex, ey, front - 0.1), (es * 1.5, es * 1.3, 0.2), 'void')
                pb.cbox((s * ex, ey, front - 0.25), (es * 0.5, es * 0.5, 0.2), 'eye')
        elif 'eyeless' not in F and form not in ('eye', 'lantern'):
            for s in (-1, 1):
                pb.cbox((s * ex, ey, front - 0.15), (es, es * 0.8, 0.3), 'eye' if ('glowing_eyes' in F or c.boss) else 'void')
        if 'teeth_ring' in F:
            for k in range(5):
                pb.cbox((-w * 0.3 + k * w * 0.15, -h * 0.3, front - 0.2), (w * 0.08, h * 0.16, 0.4), 'bone')
        if 'big_ears' in F:
            for s in (-1, 1):
                pb.cbox((s * (w / 2 + w * 0.2), h * 0.35, 0), (w * 0.4, h * 0.6, 0.6), 'skin', rot=('z', -s * 20))
        if 'helmet_lamp' in F:
            pb.cbox((0, h * 0.42, front - 0.4), (w * 0.3, h * 0.24, 0.8), 'eye')
            pb.cbox((0, h / 2 + 0.3, 0), (w * 1.05, 0.8, d * 1.05), 'metal')
        if 'iron_mask' in F:
            pb.cbox((0, -h * 0.05, front - 0.2), (w * 0.9, h * 0.6, 0.4), 'metal')
            for s in (-1, 1):
                pb.cbox((s * ex, ey, front - 0.45), (es, es * 0.5, 0.2), 'eye')
        if 'executioner_hood' in F:
            pb.cbox((0, h * 0.15, d * 0.05), (w * 1.12, h * 0.85, d * 1.1), 'dark')
            pb.cbox((0, h * 0.62, d * 0.15), (w * 0.6, h * 0.35, d * 0.6), 'dark')
            for s in (-1, 1):
                pb.cbox((s * ex, ey, front - 0.5), (es, es * 0.6, 0.2), 'eye')
        if 'flame_tips' in F or 'ember_glow' in F:
            for k in range(3):
                pb.cbox(((k - 1) * w * 0.28, top + h * 0.15 * (1 + (k == 1)), 0), (w * 0.18, h * 0.3 * (1 + (k == 1)), d * 0.18), 'glow')
        if c.boss and form in ('box', 'rounded'):
            # brow ridge / crown band so boss heads read from afar
            pb.cbox((0, h * 0.32, front - 0.2), (w * 1.02, h * 0.12, 0.6), 'trim')
    if primary_body:
        if 'emissive_core' in F or 'heartbeat_glow' in F or c.boss:
            if form not in ('sphere', 'eye', 'crystal_cluster', 'ring', 'cloak') or c.boss:
                s = max(1.2, min(w, h) * 0.22)
                pb.cbox((0, h * 0.08, front - 0.2), (s, s, 0.5), 'core', rot=('z', 45))
                if c.boss:
                    pb.cbox((0, h * 0.08, front - 0.1), (s * 1.9, s * 1.9, 0.3), 'trim')
        if 'clockface_chest' in F:
            R = min(w, h) * 0.28
            pb.cbox((0, h * 0.05, front - 0.25), (R * 2, R * 2, 0.5), 'paper')
            pb.cbox((0, h * 0.05 + R * 0.4, front - 0.55), (0.5, R * 0.8, 0.2), 'void')
            pb.cbox((R * 0.3, h * 0.05, front - 0.55), (R * 0.6, 0.5, 0.2), 'void')
            pb.cbox((0, h * 0.05, front - 0.1), (R * 2.3, R * 2.3, 0.3), 'trim')
        if 'boss_trim' in F or 'elite_trim' in F:
            band = 'trim'
            if form in ('box', 'rounded', 'cylinder'):
                pb.cbox((0, -h * 0.3, 0), (w + 0.5, max(1.0, h * 0.1), d + 0.5), band)
        if 'crystal_growth' in F:
            for k in range(3):
                x = (k - 1) * w * 0.3
                pb.cbox((x, top + 1.2 + (k == 1), d * 0.1), (1.4, 3 + 2 * (k == 1), 1.4), 'crystal', rot=('z', (k - 1) * -20))
        if 'moss_tufts' in F:
            for k in range(4):
                a = c.r(k * 3)
                pb.cbox((-w * 0.35 + w * 0.7 * a, top + 0.6, -d * 0.35 + d * 0.7 * c.r(k * 3 + 1)), (2.2, 1.4, 2.2), 'leaf')
        if 'root_tendrils' in F:
            for k in range(4):
                pb.cbox((-w * 0.35 + k * w * 0.23, -h / 2 - 1.5, d * 0.3 * (c.r(k) - 0.5)), (0.8, 3, 0.8), 'dark')
        if 'coil_spring' in F:
            for k in range(4):
                pb.cbox((0, -h / 2 - 0.8 - k * 1.3, 0), (w * 0.5, 0.7, d * 0.5), 'trim')
        if 'funeral_bell' in F:
            pb.cbox((0, -h * 0.05, d / 2 + 2), (w * 0.4, h * 0.4, w * 0.4), 'trim')
            pb.cbox((0, -h * 0.25 - 0.4, d / 2 + 2), (w * 0.5, 0.8, w * 0.5), 'trim')
        if 'chained_book' in F:
            pb.cbox((w * 0.35, -h * 0.35, front - 1.2), (w * 0.3, h * 0.3, 1.6), 'skin')
            pb.cbox((w * 0.35, -h * 0.35, front - 1.2), (w * 0.27, h * 0.25, 1.65), 'paper')
        if 'spiral_shell' in F:
            for k in range(4):
                s = (4 - k) * min(w, h) * 0.12
                pb.cbox((0, h * 0.1 + k * s * 0.35, d / 2 + s * 0.5), (s, s, s), 'light', rot=('z', k * 22.5))
        if 'barnacles' in F:
            for k in range(4):
                pb.cbox((-w * 0.35 + w * 0.7 * c.r(k + 40), top + 0.4, -d * 0.3 + d * 0.6 * c.r(k + 50)), (1.2, 0.8, 1.2), 'light')


def boss_embellish(pb, part, c, w, h, d):
    """Extra detail elements that make bosses read as unique set pieces."""
    form = part.get('form')
    lo, hi = pb.bounds()
    if form in ('box', 'rounded') and _is_body(part):
        # layered chest armour + spine ridge
        pb.cbox((0, h * 0.25, lo[2] - 0.3), (w * 0.8, h * 0.3, 0.7), 'metal')
        pb.cbox((0, h * 0.25, lo[2] - 0.55), (w * 0.82, 0.7, 0.4), 'trim')
        for k in range(4):
            pb.cbox((0, hi[1] - 1 - k * h * 0.22, hi[2] + 0.5), (w * 0.14, h * 0.12, 1.2), 'trim')
        for s in (-1, 1):
            pb.cbox((s * w * 0.42, -h * 0.05, lo[2] - 0.25), (w * 0.08, h * 0.6, 0.5), 'glow')
    if form == 'cloak':
        for k in range(5):
            x = -w * 0.4 + k * w * 0.2
            pb.cbox((x, -h * 0.42, lo[2] - 0.2), (w * 0.06, h * 0.16, 0.4), 'glow')
        pb.cbox((0, 0, lo[2] - 0.15), (w * 0.12, h * 0.8, 0.3), 'trim')
    if form == 'sphere':
        # veins / ribs wrapping the sphere + glowing seams
        for k in range(4):
            a = 45 * k
            pb.cbox((0, 0, 0), (w * 1.03, h * 0.08, d * 0.5), 'dark', rot=('y', a if a <= 45 else a - 90))
        pb.cbox((0, 0, lo[2] - 0.1), (w * 0.3, h * 0.5, 0.3), 'glow')
    if form == 'crystal_cluster':
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.4
            pb.cbox((math.cos(a) * w * 0.55, -h * 0.2, math.sin(a) * d * 0.55), (1.6, h * 0.35, 1.6), 'crystal',
                    rot=('z', 30 if math.cos(a) > 0 else -30), emission=8)


# ───────────────────────────── shader ─────────────────────────────

def _face_light(face):
    return {'up': 0.12, 'down': -0.14, 'north': 0.02, 'south': -0.02, 'east': -0.04, 'west': -0.04}[face]


def make_shader(look: MobLook):
    F = look.features
    mat = look.material
    seed = look.seed
    R = look.ramps

    def shader(tc):
        e = tc.el
        role = e.role
        i, j, w, h = tc.i, tc.j, tc.w, tc.h
        x, y, z = tc.pos
        face = tc.face
        alpha = 255
        color = None
        if role == 'eyeball':
            # pale sclera, iris ring and pupil facing model −Z (entity front)
            lo, hi = e.frm, e.to
            ln = math.sqrt(x * x + y * y + z * z) or 1
            fwd = -z / ln
            sclera = [(70, 60, 64), (150, 138, 140), (214, 204, 200), (238, 232, 226), (255, 252, 248), (255, 255, 255)]
            if fwd > 0.86:
                return R['void'], 0.1, None, 255
            if fwd > 0.6:
                return R['glow'], 0.55 + 0.3 * (fwd - 0.6) / 0.26, None, 255
            v = 0.62 + _face_light(face)
            if 'veined_eye' in F and abs(fbm(x * 0.4, y * 0.4 + z * 0.3, seed) - 0.5) < 0.035:
                return R['glow'], 0.25, None, 255
            return sclera, v, None, 255
        ramp = R.get(role, R['skin'])
        base = {'skin': 0.5, 'dark': 0.45, 'light': 0.55, 'trim': 0.55, 'metal': 0.5, 'leaf': 0.5, 'bone': 0.55,
                'glow': 0.62, 'eye': 0.85, 'core': 0.7, 'paper': 0.6, 'void': 0.25, 'cloth': 0.45, 'crystal': 0.55}.get(role, 0.5)
        v = base
        if role not in GLOW_ROLES:
            v += _face_light(face)
            if face not in ('up', 'down'):
                v += (0.5 - tc.b) * 0.16
            border = (i == 0 or j == 0 or i == w - 1 or j == h - 1) and w > 2 and h > 2
            if border and role not in ('void',):
                v -= 0.14
            v += (h3(int(x * 2), int(y * 2), int(z * 2), seed) - 0.5) * 0.12
        else:
            # glow: hot centre, cooler rim
            cx = abs(tc.a - 0.5) * 2
            cy = abs(tc.b - 0.5) * 2
            v += 0.25 * (1 - max(cx, cy)) - 0.1
        dual = 'dual_tone' in F and x < 0 and role in ('skin', 'crystal', 'light')
        if dual:
            ramp = look.alt if role == 'skin' else [hue_shift(cc, 180) for cc in ramp]
        if role in ('skin', 'cloth'):
            m = 'cloth' if role == 'cloth' else mat
            if m == 'stone':
                bx = (i + (j // 4) * 3) % 7
                if j % 4 == 0 or bx == 0:
                    v -= 0.16
                v += (fbm(x * 0.25, y * 0.25 + z * 0.2, seed) - 0.5) * 0.3
            elif m == 'chitin':
                if face == 'up':
                    v += 0.18 * (1 - abs(tc.a - 0.5) * 2)
                if (int(z * 2) % 5) == 0 and face != 'down':
                    v -= 0.15
            elif m == 'fur':
                v += (h2(i, j // 2, seed) - 0.5) * 0.32
            elif m == 'scale':
                if (i + (j // 2) % 2) % 2 == 0 and j % 2 == 0:
                    v -= 0.13
                if face == 'up':
                    v += 0.08
            elif m == 'cloth':
                v += math.sin(i * 1.4 + x * 0.3) * 0.08
                if face not in ('up', 'down') and tc.b > 0.92:
                    v -= 0.12
            elif m == 'metal':
                if i % 6 == 0 or j % 6 == 0:
                    v -= 0.14
                elif i % 6 == 3 and j % 6 == 3:
                    v += 0.28
            elif m == 'gloss':
                if face == 'up' or (face in ('north', 'east') and tc.b < 0.3 and tc.a < 0.4):
                    v += 0.2
                v += (fbm(x * 0.3, y * 0.3, seed) - 0.5) * 0.15
            elif m == 'ethereal':
                v += (0.5 - tc.b) * 0.2
                if h2(int(x * 3), int(y * 3) + int(z * 3) * 7, seed) > 0.96:
                    return R['glow'], 0.9, None, 255
            else:   # flesh
                v += (fbm(x * 0.35, y * 0.35 + z * 0.25, seed) - 0.5) * 0.22
        if role == 'paper':
            if face not in ('up', 'down') and j % 2 == 1 and 1 < i < w - 2:
                v -= 0.18
        if role == 'crystal':
            cell = h3(int(x), int(y * 0.7), int(z), seed)
            v += (cell - 0.5) * 0.35
            if (i + j) % 5 == 0:
                v += 0.15
        # ── feature overlays (body materials only)
        if role in ('skin', 'dark', 'cloth', 'light', 'metal'):
            n = fbm(x * 0.3 + 11, y * 0.3 + z * 0.17, seed + 5)
            if 'moss_tufts' in F and (face == 'up' or (face != 'down' and tc.b < 0.25)) and n > 0.47:
                return R['leaf'], 0.45 + (n - 0.47) * 1.4, None, alpha
            if ('cracked_stone' in F or 'molten_cracks' in F) and abs(vnoise(x * 0.45 + z * 0.3, y * 0.45, seed + 9) - 0.5) < 0.035:
                if 'molten_cracks' in F:
                    return R['glow'], 0.75, None, 255
                v -= 0.3
            if 'rust_streaks' in F and face not in ('up', 'down') and h2(int(x * 2 + z * 2), 0, seed) > 0.8 and \
                    vnoise(x, y * 0.4, seed) > 0.45:
                return R['skin'], 0.2, mix((150, 70, 30), ramp[2], 0.35), alpha
            if 'verdigris_patina' in F and n < 0.36:
                return R['skin'], 0.5, mix((70, 170, 140), ramp[3], 0.35 + n), alpha
            if 'frost_rime' in F and (face == 'up' or tc.b < 0.15) and h2(i, j, seed + 3) > 0.35:
                return R['skin'], 0.5, mix((220, 240, 255), ramp[-1], 0.3), alpha
            if ('sculk_veins' in F or 'electric_veins' in F or 'hyphae_web' in F) and \
                    abs(fbm(x * 0.22, y * 0.22 + z * 0.18, seed + 21) - 0.5) < 0.03:
                return R['glow'], 0.8, None, 255
            if ('spore_glow' in F or 'firefly_specks' in F or 'ore_flecks' in F or 'prism_glint' in F) and \
                    h3(int(x * 2), int(y * 2), int(z * 2), seed + 31) > 0.955:
                return R['glow'], 0.9, None, 255
            if 'cap_spots' in F and face in ('up', 'north', 'south', 'east', 'west') and \
                    vnoise(x * 0.5, z * 0.5 + y * 0.3, seed + 41) > 0.72:
                return R['light'], 0.85, None, alpha
            if 'silk_strands' in F and (int(x * 1.5 + y * 1.5 + z) % 9 == 0) and h2(i, j, seed) > 0.4:
                return R['light'], 0.9, None, alpha
            if ('dripping' in F or 'ink_drips' in F) and face not in ('up', 'down') and tc.b > 0.6 and \
                    h2(int(x * 2 + z * 2), 1, seed) > 0.78 and tc.b - 0.6 < h2(int(x * 2 + z * 2), 2, seed) * 0.4:
                return (R['void'] if 'ink_drips' in F else R['glow']), 0.4, None, alpha
            if ('ink_scribbles' in F or 'gate_runes' in F or 'silver_markings' in F) and face not in ('up', 'down') \
                    and w >= 6 and h >= 6:
                gi = int(h2(i // 4, j // 6, seed) * 8)
                if rune_bit(gi, i % 4, j % 6) and h2(i // 4, j // 6, seed + 1) > 0.45:
                    if 'gate_runes' in F:
                        return R['glow'], 0.75, None, 255
                    return (R['light'] if 'silver_markings' in F else R['void']), 0.8 if 'silver_markings' in F else 0.3, None, alpha
            if 'rivets' in F and role in ('skin', 'metal') and (i % 4 == 1 and (j == 1 or j == h - 2)) and w >= 5:
                return R['metal'], 0.85, None, alpha
            if 'bone_ribs' in F and face == 'north' and j % 3 == 1 and 0.15 < tc.a < 0.85:
                return R['bone'], 0.7, None, alpha
            if 'plate_armor' in F and face not in ('up', 'down') and j % 5 == 0:
                v -= 0.2
            if 'leather_straps' in F and face not in ('up', 'down') and (i + j) % 11 < 2:
                return R['dark'], 0.25, mix((90, 56, 30), ramp[1], 0.4), alpha
            if 'bookshelf_chest' in F and face == 'north' and role == 'skin':
                col = (i // 2) % 5
                tint = [(130, 40, 40), (40, 70, 120), (60, 100, 50), (140, 110, 40), (90, 50, 110)][col]
                return R['skin'], 0.5, mix(tint, ramp[2], 0.3 + 0.15 * (j % 4 == 0)), alpha
            if 'paper_scraps' in F and h2(i // 2, j // 2, seed + 61) > 0.9:
                return R['paper'], 0.7, None, alpha
            if 'sound_ripples' in F and face not in ('up', 'down') and int(math.hypot(tc.a - 0.5, tc.b - 0.5) * 12) % 3 == 0:
                v += 0.15
            if ('elite_trim' in F or 'boss_trim' in F or 'brass_trim' in F or 'gilded_corners' in F) and role == 'skin' \
                    and face not in ('up', 'down') and w >= 4 and h >= 4:
                tw = 2 if ('boss_trim' in F and h >= 16) else 1
                corner = (i < 2 or i >= w - 2) and (j < 2 or j >= h - 2)
                if (h >= 10 and (j < tw or j >= h - tw)) or ('gilded_corners' in F and corner):
                    return R['trim'], 0.6 + (0.2 if j == 0 else 0), None, alpha
            if 'boss_trim' in F and role == 'skin' and face == 'north' and w >= 8 and h >= 8:
                gi = int(h2(i // 4, j // 6, seed + 7) * 8)
                if 0.2 < tc.b < 0.8 and rune_bit(gi, i % 4, j % 6) and h2(i // 4, j // 6, seed + 8) > 0.6:
                    return R['glow'], 0.7, None, 255
            if 'translucent' in F and role in ('skin', 'cloth'):
                alpha = 205
            if ('tattered_cloth' in F or 'veil' in F) and role == 'cloth' and face not in ('up', 'down') and tc.b > 0.8 \
                    and h2(i, j, seed + 71) > 0.6:
                return ramp, v, None, 0
        if 'translucent' in F and role == 'light':
            alpha = 215
        return ramp, clamp(v), color, alpha
    return shader


# ───────────────────────────── assembly ─────────────────────────────

class MobResult:
    def __init__(self, mid):
        self.mid = mid
        self.files: dict[str, bytes] = {}
        self.warnings: list[str] = []
        self.preview = None          # (Model in assembled model space, faces_uv, frame0)
        self.parts: list[str] = []
        self.frames = 1
        self.texture_path = ''
        self.elements = 0              # model elements over every part
        self.part_elements: dict[str, int] = {}
        self.voxel_parts: list[str] = []


def _el_json(e, uvs, S):
    faces = {}
    for f in e.faces:
        x0, y0, x1, y1 = uvs[f]
        faces[f] = {'uv': [r4(x0 * 16 / S), r4(y0 * 16 / S), r4(x1 * 16 / S), r4(y1 * 16 / S)], 'texture': '#0'}
    j = {'from': [r4(v) for v in e.frm], 'to': [r4(v) for v in e.to]}
    if e.rot:
        ax, ang, org = e.rot
        j['rotation'] = {'angle': r4(ang), 'axis': ax, 'origin': [r4(v) for v in org]}
    if not e.shade:
        j['shade'] = False
    if e.emission:
        j['light_emission'] = int(max(0, min(15, e.emission)))
    j['faces'] = faces
    return j


def _copy_el(e, fn_point, scale=1.0):
    a, b = fn_point(e.frm), fn_point(e.to)
    rot = None
    if e.rot:
        ax, ang, org = e.rot
        rot = (ax, ang, fn_point(org))
    n = El(tuple(min(a[i], b[i]) for i in range(3)), tuple(max(a[i], b[i]) for i in range(3)), e.role, e.mat, rot,
           e.faces, e.glow, e.emission, e.shade, e.tag, dict(e.data))
    return n


def _voxel_ctx_vs(size, boss):
    """Suggested voxel size (px per voxel) from the part's YAML size: fine for small parts, coarser for big."""
    m = max(size)
    if m <= 10:
        return 0.5
    if m <= 18:
        return 0.6667 if not boss else 0.75
    return 0.8 if not boss else 1.0


def _try_design(fn, look, p, vctx, res):
    """Run a voxel design function; any failure falls back to the old part (with a warning)."""
    import traceback
    try:
        g = fn(look, vctx.name, p, vctx)
    except Exception:  # noqa: BLE001
        res.warnings.append(f'mob {look.mid}/{vctx.name}: voxel design failed — old box model used:\n'
                            + traceback.format_exc(limit=3))
        return None
    if g is None or not len(g):
        return None
    if not hasattr(g, 'vs'):
        res.warnings.append(f'mob {look.mid}/{vctx.name}: design returned a Grid without vs — use ctx.grid()')
        return None
    return g


SET_KEYS = ('set', 'joint', 'foot')


def group_sets(yparts):
    """YAML parts → (design parts, {set name: [member parts]}).

    Members of one set (`set: legs` on leg_l / leg_r …) collapse back into the original part (name = set, the
    members' form / size / pivot / anim) at the place of the first member, so designs, seeds and budgets see exactly
    the part they were written for.  Parts without `set` pass through unchanged."""
    parts, sets = [], {}
    for p in yparts:
        sname = p.get('set')
        if not sname:
            parts.append(p)
            continue
        if sname not in sets:
            sets[sname] = []
            v = {k: val for k, val in p.items() if k not in SET_KEYS}
            v['name'] = sname
            parts.append(v)
        sets[sname].append(p)
    return parts, sets


def joint_px(p, at_foot=False):
    """A part's `joint` (entity-local blocks, like the pivot) → part px in model axes (pivot = 0; model −X = mob
    left, model −Z = front — the 180° ItemDisplay turn).  No joint → the pivot.  at_foot: the sole point
    joint + foot[0:3] instead (the split seed — feet lie far apart even where the leg roots crowd together)."""
    piv = [float(v) for v in (p.get('pivot') or [0, 0, 0])]
    j = [float(v) for v in (p.get('joint') or piv)]
    if at_foot and p.get('foot'):
        j = [j[a] + float(p['foot'][a]) for a in range(3)]
    return (-(j[0] - piv[0]) * 16, (j[1] - piv[1]) * 16, -(j[2] - piv[2]) * 16)


def _cut_el_x(e, uv, xm):
    """Cut an unrotated element at the model plane x = xm → [(El, uv)] (1 or 2 pieces; the cut faces are dropped)."""
    x1, x2 = e.frm[0], e.to[0]
    if e.rot or not (x1 + 1e-6 < xm < x2 - 1e-6):
        return [(e, uv)]
    out = []
    for a, b, drop in ((x1, xm, 'east'), (xm, x2, 'west')):
        faces = tuple(f for f in e.faces if f != drop)
        nuv = {}
        for f in faces:
            u0, v0, u1, v1 = uv[f]
            if f in ('south', 'up', 'down'):
                nuv[f] = (u0 + (a - x1) / (x2 - x1) * (u1 - u0), v0, u0 + (b - x1) / (x2 - x1) * (u1 - u0), v1)
            elif f == 'north':
                nuv[f] = (u0 + (x2 - b) / (x2 - x1) * (u1 - u0), v0, u0 + (x2 - a) / (x2 - x1) * (u1 - u0), v1)
            else:
                nuv[f] = uv[f]
        n = El((a, e.frm[1], e.frm[2]), (b, e.to[1], e.to[2]), e.role, e.mat, None, faces, e.glow, e.emission, e.shade,
               e.tag, dict(e.data))
        out.append((n, nuv))
    return out


def split_old_elements(els, uvs, members):
    """Old box-model set (no voxel design): every element goes to the member whose joint is nearest to its centre;
    with two members side by side, elements spanning the plane between their joints (a hip band) are cut there.
    members = [(name, joint px)] → {name: (elements, uvs)}."""
    out = {name: ([], []) for name, _ in members}
    pieces = list(zip(els, uvs))
    if len(members) == 2 and abs(members[0][1][0] - members[1][1][0]) > 1e-3:
        xm = (members[0][1][0] + members[1][1][0]) / 2
        pieces = [q for e, uv in pieces for q in _cut_el_x(e, uv, xm)]
    for e, uv in pieces:
        c = [(e.frm[a] + e.to[a]) / 2 for a in range(3)]
        name = min(members, key=lambda m: sum((c[a] - m[1][a]) ** 2 for a in range(3)))[0]
        out[name][0].append(e)
        out[name][1].append(uv)
    return out


def build_mob(mid, d, boss=False, jdump=None, png_bytes=None, strip=None, mode='auto'):
    """mode: 'auto' = voxel design (src/mobvox) where one exists, old box model elsewhere; 'old' = box only."""
    from . import mobvox
    from .voxel import mob_build as MB
    from .voxel import mob_kit as MK
    from .voxel import palette as VP
    res = MobResult(mid)
    m = d.get('model') or {}
    style = m.get('style') or {}
    yparts = m.get('parts') or []
    rank = d.get('rank') or ('boss' if boss else 'normal')
    look = MobLook(mid, style, boss, rank)
    if not yparts:
        res.warnings.append(f'mob {mid}: no model parts')
        return res
    # part sets (GDD §14.6): YAML parts with `set: <name>` are cut from ONE design part named <name> (same form /
    # size / pivot / anim) — the designs and the budget see that original part, the pack writes one model per member
    parts, sets = group_sets(yparts)
    floor = int(d.get('floor') or 1)
    design = mobvox.design_for(mid) if mode != 'old' else None
    if mode != 'old' and mobvox.ERRORS and not getattr(build_mob, '_reported', False):
        res.warnings.extend(mobvox.ERRORS)
        build_mob._reported = True
    shared = {}
    vgrids = {}      # part name → MobGrid
    vctxs = {}       # part name → PartCtx (re-run on coarser voxels when over budget)
    # arms for hand-held detection
    arms = [p for p in parts if p.get('form') in ('arm', 'tentacle_cluster') and p.get('anim') in ('arm_left', 'arm_right')]
    head_part = next((p for p in parts if p.get('name') == 'head'), None) or next((p for p in parts if _is_head(p)), None)
    body_part = next((p for p in parts if _is_body(p) and p.get('form') not in ('leg_pair', 'leg_quad')), None) or parts[0]
    built = []   # (part, PB, s)
    for p in parts:
        form = p.get('form') or 'box'
        if form not in FORMS:
            res.warnings.append(f'mob {mid}: unknown form {form!r} on part {p.get("name")} — using box')
            form = 'box'
        size = [float(v) for v in (p.get('size') or [8, 8, 8])]
        w, h, dd = size
        pivot = p.get('pivot') or [0, 0, 0]
        out = -1.0 if float(pivot[0]) > 0 else 1.0 if float(pivot[0]) < 0 else 1.0
        anim = p.get('anim') or 'static'
        holder = None
        if p not in arms:
            for a in arms:
                if a.get('pivot') == p.get('pivot') and a.get('anim') == p.get('anim'):
                    holder = a
                    break
        hang = (form in ('arm', 'tentacle_cluster') and anim in ('arm_left', 'arm_right')) or \
               (form == 'leg_pair' and anim == 'legs_walk')
        if design is not None:
            hand = None
            if holder is not None:
                arm_size = [float(v) for v in (holder.get('size') or [4, 12, 4])]
                hand = (0.0, -arm_size[1] + 1.0, 0.0)
            vctx = MK.PartCtx(mid, look, p, parts, boss, rank, floor, VP.FLOOR_THEME.get(floor, 'plain'), out, hang,
                              holder, hand, _voxel_ctx_vs(size, boss), MB.PER_PART, shared,
                              stable_seed(mid, p.get('name', 'part')))
            g = _try_design(design, look, p, vctx, res)
            if g is not None:
                vgrids[p.get('name', 'part')] = g
                vctxs[p.get('name', 'part')] = vctx
                continue
        c = PC(p, look, boss, out, hang)
        pb = PB(p.get('name', 'part'))
        if holder is not None:
            arm_size = [float(v) for v in (holder.get('size') or [4, 12, 4])]
            c.arm_h, c.arm_w = arm_size[1], arm_size[0]
        FORMS[form](pb, w, h, dd, c)
        # placement (GDD §14.6)
        if holder is not None:
            hand_y = -c.arm_h + 1.0
            if form in ('blade', 'claw'):
                if form == 'blade':
                    pb.remap(((0, 1), (2, 1), (1, -1)))      # +Y (blade up) → −Z (forward)
                else:
                    lo, hi = pb.bounds()
                    pb.translate((0, 0, -lo[2]))           # claw base at the hand, opening forward
                    pb.translate((0, 0, -(hi[2] - lo[2])))
                pb.translate((0, hand_y, -1.0))
            elif form == 'slab':
                pb.remap(((2, -1), (1, 1), (0, 1)))           # plate normal → X
                pb.translate((-out * 0 + out * (c.arm_w / 2 + max(0.6, dd) / 2 + 0.2), hand_y + 1, 0))
            else:
                lo, hi = pb.bounds()
                pb.translate((-(lo[0] + hi[0]) / 2, hand_y - hi[1], -(lo[2] + hi[2]) / 2 - 1.0))
        elif hang and form in ('arm', 'tentacle_cluster'):
            pass     # already built hanging from y=0
        elif hang and form == 'leg_pair':
            pb.translate((0, -h / 2, 0))
        elif form == 'blade':
            pb.translate((0, -h / 2, 0))
        elif form in ('tail', 'wing', 'neck', 'segment'):
            pass     # joint forms start at the pivot (see module docstring)
        else:
            lo, hi = pb.bounds()
            # centre the main volume on the pivot (decor added later may stick out)
            pb.translate((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -(lo[2] + hi[2]) / 2))
        n0 = len(pb.els)
        add_features(pb, p, c, w, h, dd, p is head_part, p is body_part)
        if boss:
            boss_embellish(pb, p, c, w, h, dd)
        if form == 'tentacle_cluster' and not hang:
            pass
        built.append((p, pb, c, n0))
    # combined model for UV packing (real geometry, part-local coordinates) — old-style parts only
    total_area = 0.0
    cm = Model(f'mob/{mid}', density=1)
    ranges = {}
    for (p, pb, c, n0) in built:
        start = len(cm.els)
        cm.els.extend(pb.els)
        ranges[p.get('name', 'part')] = (start, len(cm.els))
    for e in cm.els:
        for f in e.faces:
            fu, fv = e.face_size(f)
            total_area += max(1, round(fu)) * max(1, round(fv))
    cm.density = 2 if total_area < 2600 else 1
    tex_ref = f'{NS}:mob/{mid}'
    baked = cm.bake(make_shader(look), tex_ref) if cm.els else None
    # voxel parts: shade + mesh under the element budget, one shared palette
    pms = {}
    vpal = MB.Palette()
    pal_map = {}
    if vgrids:
        base = VP.mob_ramps(look, VP.FLOOR_THEME.get(floor, 'plain'), floor)
        base.update(shared.get('ramps') or {})
        plist = []
        for name, g in vgrids.items():
            rp = dict(base)
            rp.update(g.ramp_over)
            if name in sets:
                pm = MB.SetMesh(name, g, rp, [(q.get('name'), joint_px(q, at_foot=True))
                                               + ((joint_px(q),) if q.get('foot') else ()) for q in sets[name]])
            else:
                pm = MB.PartMesh(name, g, rp)
            pms[name] = pm
            plist.append(pm)
        budget = MB.budget_for(rank, boss)
        warns = MB.fit_budget(plist, budget, fixed=len(cm.els))
        over = MB.fit_sets(plist, budget, fixed=len(cm.els))
        # a cut set that still does not fit: re-run its own design on coarser voxels before any other part pays more
        for _ in range(5):
            cut = [q for q in plist if isinstance(q, MB.SetMesh) and vctxs[q.name].vs_mul < 1.6]
            if not over or not cut:
                break
            pm = max(cut, key=lambda q: q.count)
            vctx = vctxs[pm.name]
            vctx.vs_mul *= 1.1          # small steps: the legs stay as close to the design as the budget allows
            g = _try_design(design, look, vctx.part, vctx, res)
            if g is None:
                break
            res.warnings.append(f'mob {mid}/{pm.name}: cut set over budget ({pm.count} el) — rebuilt at voxel size '
                                f'{g.vs:.2f} px')
            pm.grid = g
            pm.base_ramps = dict(base, **g.ramp_over)
            pm.level = 0
            pm.seal = True
            pm.remesh()
            over = MB.fit_sets(plist, budget, fixed=len(cm.els))
        if over:
            warns = MB.fit_budget(plist, budget, fixed=len(cm.els))
        # safety net: still over budget → re-run the largest part's design on coarser voxels (≤ 3 times each)
        for _ in range(8):
            over_total = sum(pm.count for pm in plist) + len(cm.els) > budget
            over_part = [pm for pm in plist if pm.max_part > MB.PER_PART]
            if not (over_total or over_part):
                break
            pm = max(over_part or plist, key=lambda q: q.count)
            vctx = vctxs[pm.name]
            if vctx.vs_mul >= 1.7:
                break
            vctx.vs_mul *= 1.2
            g = _try_design(design, look, vctx.part, vctx, res)
            if g is None:
                break
            res.warnings.append(f'mob {mid}/{pm.name}: over budget ({pm.count} el) — rebuilt at voxel size '
                                f'{g.vs:.2f} px (design for the budget instead)')
            pm.grid = g
            pm.base_ramps = dict(base, **g.ramp_over)
            pm.level = 0
            pm.remesh()
            warns = MB.fit_budget(plist, budget, fixed=len(cm.els))
        for wmsg in warns:
            res.warnings.append(f'mob {mid}: {wmsg}')
        outs = {}
        for name, pm in pms.items():
            if isinstance(pm, MB.SetMesh):
                for pc in pm.pieces:
                    outs[pc.name] = pc
            else:
                outs[name] = pm
        pms = outs
        for pi, (name, pm) in enumerate(pms.items()):
            pal_map[name] = vpal.add_part(pi, pm)
    S, cells = MB.compose(baked.size if baked else 0, len(vpal.entries))
    texels = (list(baked.texels) if baked else []) + MB.palette_texels(vpal, cells)
    from .model import BakedModel
    atlas = BakedModel(cm, S, texels, baked.faces_uv if baked else {}, tex_ref)
    # animation: glowing texels pulse (bosses 8 frames, emissive mobs 4 frames)
    has_glow = any(t.glow or t.role in GLOW_ROLES or t.role == 'eyeball' for t in texels)
    frames_n = 8 if boss else (4 if has_glow and ({'emissive_core', 'heartbeat_glow', 'spore_glow', 'sculk_veins',
                                                    'molten_cracks', 'electric_veins'} & look.features) else 1)

    def pulse(f):
        def vfn(t):
            if t.role in GLOW_ROLES or (t.ramp is look.ramps['glow']):
                ph = 2 * math.pi * (f / frames_n) - t.pos[1] * 0.12
                return (None, 0.16 * math.sin(ph))
            return None
        return vfn
    frames = [atlas.frame(pulse(f) if frames_n > 1 else None) for f in range(frames_n)]
    if frames_n > 1 and all(fr.tobytes() == frames[0].tobytes() for fr in frames[1:]):
        res.warnings.append(f'mob {mid}: no glowing texel changes between frames — static atlas')
        frames_n = 1
        frames = frames[:1]
    tp = f'assets/{NS}/textures/mob/{mid}.png'
    if frames_n > 1:
        res.files[tp] = png_bytes(strip(frames))
        res.files[tp + '.mcmeta'] = jdump({'animation': {'frametime': 3 if boss else 4, 'interpolate': False}})
        res.frames = frames_n
    else:
        res.files[tp] = png_bytes(frames[0])
    res.texture_path = tp
    # per-part model JSON (pivot → 8,8,8; shrink to the legal box when needed)
    prev_els = []
    prev_uv = {}
    old_split = {}
    for sname, members in sets.items():
        if sname in ranges and sname not in vgrids:
            start, end = ranges[sname]
            uvs = [{f: baked.faces_uv[(start + k, f)] for f in e.faces} for k, e in enumerate(cm.els[start:end])]
            old_split.update(split_old_elements(cm.els[start:end], uvs, [(q.get('name'), joint_px(q)) for q in members]))
    for p in yparts:
        name = p.get('name', 'part')
        if name in old_split:
            els, uvs_list = old_split[name]
            prev_uv_list = uvs_list
            res.part_elements[name] = len(els)
        elif name in pms:
            pm = pms[name]
            gmap = pal_map[name]
            els, uvs_list = [], []
            for (lo, hi, pi, faces, g) in pm.vm.boxes:
                vs = pm.grid.vs
                frm = tuple((lo[a] - 0.5) * vs for a in range(3))
                to = tuple((hi[a] + 0.5) * vs for a in range(3))
                gi = gmap[pi]
                mat = vpal.entries[gi][5]
                e = El(frm, to, 'vox', faces=faces, glow=g, emission=(15 if mat == 'eye' else 12) if g else 0, shade=not g)
                x, y = cells[gi]
                els.append(e)
                uvs_list.append({f: (x + 0.5, y + 0.5, x + 1.5, y + 1.5) for f in faces})
            prev_uv_list = [{f: (cells[gmap[b[2]]][0], cells[gmap[b[2]]][1], cells[gmap[b[2]]][0] + 2,
                                 cells[gmap[b[2]]][1] + 2) for f in b[3]} for b in pm.vm.boxes]
            res.part_elements[name] = len(els)
            res.voxel_parts.append(name)
        else:
            start, end = ranges[name]
            els = cm.els[start:end]
            uvs_list = [{f: baked.faces_uv[(start + k, f)] for f in e.faces} for k, e in enumerate(els)]
            prev_uv_list = uvs_list
            res.part_elements[name] = len(els)
        pts = [q for e in els for q in e.corners()] + [q for e in els for q in (e.frm, e.to)]
        lo = [min(q[i] for q in pts) for i in range(3)]
        hi = [max(q[i] for q in pts) for i in range(3)]
        s = 1.0
        for i in range(3):
            if hi[i] > 23.5:
                s = min(s, 23.5 / hi[i])
            if lo[i] < -23.5:
                s = min(s, 23.5 / -lo[i])
        if s < 1.0 / 4.0:
            res.warnings.append(f'mob {mid}/{name}: part too large even at 4x restore')
            s = 0.25
        conv = (lambda q, s=s: (8 + q[0] * s, 8 + q[1] * s, 8 + q[2] * s))
        out_els = []
        for k, e in enumerate(els):
            ne = _copy_el(e, conv)
            out_els.append(_el_json(ne, uvs_list[k], S))
        inv = r4(1.0 / s)
        pm_ = Model('tmp')
        pm_.els = [_copy_el(e, conv) for e in els]
        display = {
            'fixed': {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [inv, inv, inv]},
            'head': {'rotation': [0, 0, 0], 'translation': [0, 0, 0], 'scale': [inv, inv, inv]},
            'gui': fit_transform(pm_, (25, 160, 0), target=14.0, max_scale=4.0),
            'ground': fit_transform(pm_, (0, 180, 0), target=8.0, max_scale=2.0),
        }
        mj = {
            'textures': {'0': tex_ref, 'particle': tex_ref},
            'gui_light': 'side',
            'elements': out_els,
            'display': {k: {kk: [r4(x) for x in vv] for kk, vv in v.items()} for k, v in display.items()},
        }
        res.files[f'assets/{NS}/models/mob/{mid}/{name}.json'] = jdump(mj)
        res.files[f'assets/{NS}/items/mob/{mid}/{name}.json'] = jdump(
            {'model': {'type': 'minecraft:model', 'model': f'{NS}:mob/{mid}/{name}'}})
        res.parts.append(name)
        # assembled preview (model space: entity offset (x,y,z) ↦ model (−x, y, −z) because of the 180° turn)
        piv = [float(v) * 16 for v in (p.get('pivot') or [0, 0, 0])]
        off = (-piv[0], piv[1], -piv[2])
        for k, e in enumerate(els):
            idx = len(prev_els)
            prev_els.append(_copy_el(e, lambda q, off=off: (q[0] + off[0], q[1] + off[1], q[2] + off[2])))
            for f in e.faces:
                prev_uv[(idx, f)] = prev_uv_list[k][f]
    pmodel = Model(f'preview/{mid}')
    pmodel.els = prev_els
    res.preview = (pmodel, prev_uv, frames[0])
    res.elements = len(prev_els)
    return res


def preview_cell(pmodel, uv, frame, px=160, rot=(18, 205, 0)):
    """Render an assembled mob (front three-quarter view) into a px×px image."""
    from . import render
    from .model import display_apply
    tr0 = {'rotation': list(rot), 'translation': [0, 0, 0], 'scale': [1, 1, 1]}
    pts = [display_apply(q, tr0) for e in pmodel.els for q in e.corners()]
    lo = [min(q[i] for q in pts) for i in range(2)]
    hi = [max(q[i] for q in pts) for i in range(2)]
    ext = max(hi[0] - lo[0], hi[1] - lo[1], 1)
    units = 16
    sc = (units * 0.92) / ext
    cx, cy = (lo[0] + hi[0]) / 2 * sc, (lo[1] + hi[1]) / 2 * sc
    tr = {'rotation': list(rot), 'translation': [-cx, -cy, 0], 'scale': [sc, sc, sc]}
    ppu = max(2, px // units)
    return render.render(pmodel, uv, frame, tr, ppu=ppu)
