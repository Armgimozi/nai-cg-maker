#!/usr/bin/env python3
"""Held-weapon preview — offline emulation of the vanilla 26.3 client's held-item rendering.

    python tools/hold_preview.py [--shapes war_scythe,sickle] [--items rootbound_scythe] [--out DIR]
                                 [--tag before] [--override FILE.json] [--vanilla-dir DIR] [--jobs N]
                                 [--extra-items auto|off|FILE,...]
    python tools/hold_preview.py --selftest

For every weapon shape in items.yml it builds two real items (lowest and highest rarity) through the pack
pipeline (items.build_item → model JSON + texture, exactly what the client receives) and renders a sheet
`<tag>_<shape>.png`.  Rows: reference(s) first — a vanilla iron sword with vanilla's `item/handheld`
transforms, plus the vanilla iron axe for shapes with a sideways head (HEAD_SHAPES) and the vanilla bow
(`item/bow`) for bows — then the two items.  Columns: first person idle + 4 attack-swing frames (16:9,
hand FOV 70°; bows get a 6th "drawing" cell with the pulling_2 model), then third person on a Steve
mannequin (front 3/4, F5-style back 3/4, and the right side at swing t = 0.15 / 0.5).  Yellow = path of the
weapon's far end (point farthest from the grip) during one swing; magenta = grip point (where the hand
holds the handle: (8, 1, 8) for weapons, (4.5, 6, 8) for bows); green = fist centre.  `<tag>_metrics.json`
holds per item: screen coverage (idle / max over the swing / max inside the central third), grip and far
end on screen, and which way the sideways head points (head_fp_toward_camera: +1 = at the camera,
−1 = away like the vanilla axe; head_tp_forward: compare with the vanilla axe row).

--override FILE.json  {"<shape or item id>": {"firstperson_righthand": {...}, "thirdperson_righthand": {...}}}
                      replaces those display transforms before rendering (prototype a fix without regenerating).
--extra-items         like generate.py: auto (default) also offers the 0.3.5 gear of tools/data/035/gear_spec.json
                      while items.yml lacks it (src/extra_items.py), off = items.yml only, or FILE,...
--vanilla-dir DIR     DIR/iron_sword.png, iron_axe.png, bow.png (vanilla textures you extract locally from the
                      client jar; never committed) for the reference rows; without them original stand-in
                      sprites with the same pixel layout are drawn.

Formulas (26.3 client: ItemInHandRenderer, ItemTransform, ItemInHandLayer, HumanoidModel, PlayerModel,
Camera, GameRenderer; view space = camera at the origin looking down −Z, +X right, +Y up; v = model coords
in 1/16 block; Rx/Ry/Rz = right-handed rotations in degrees):

  item transform  D(t) = T(clamp(t.translation/16, ±5)) · Rx(rx)·Ry(ry)·Rz(rz) · S(clamp(t.scale, ±4))
                         · T(−½, −½, −½)
                  (JOML Quaternionf.rotationXYZ → Z is applied to the point first; for left-hand contexts
                  the client negates ry, rz and tx on top of whatever the JSON says)

  first person    M = Persp(fov_y 70°, 16:9, near 0.05)     # Camera.BASE_HUD_FOV; ignores the FOV option
     (right hand)     · T(0.56, −0.52 − 0.6·h, −0.72)                # applyItemArmTransform (h = 0: equipped)
                      · T(−0.4·sin(√p·π), 0.2·sin(√p·2π), −0.2·sin(p·π))      # swingArm (SwingAnimation WHACK)
                      · Ry(45 − 20·sin(p²·π)) · Rz(−20·sin(√p·π)) · Rx(−80·sin(√p·π)) · Ry(−45)
                                                                       # applyItemArmAttackTransform
                      · D(firstperson_righthand) · v/16
                  p = attack progress 0..1 over the swing (6 ticks by default); p = 1 equals p = 0, so the
                  sheet shows idle + p = 0.1, 0.25, 0.5, 0.75 (0.25 is the bottom of the chop: sin(√p·π) = 1).
     bow drawing  M = Persp · T(0.56, −0.52, −0.72) · T(−0.2786, 0.1834, 0.1573) · Rx(−13.935) · Ry(35.3)
                      · Rz(−9.785) · T(0, 0, 0.04·w) · S(1, 1, 1 + 0.2·w) · Ry(−45) · D(firstperson_righthand)
                  (ItemUseAnimation.BOW, full draw w = 1, shake ignored)

  third person    W = Ry(180° − bodyYaw) · S(−1, −1, 1) · S(0.9375) · T(0, −1.501, 0)   # LivingEntityRenderer
     (right hand)     · T(arm.x/16, arm.y/16, arm.z/16) · Rz(zRot)·Ry(yRot)·Rx(xRot)   # translateToHand
                      · Rx(−90°) · Ry(180°) · T(1/16, 2/16, −10/16)    # ItemInHandLayer.submitArmWithItem
                      · D(thirdperson_righthand) · v/16
                  idle: ArmPose.ITEM → right_arm.xRot = −π/10, pivot (−5, 2, 0), bodyYaw 0 (faces +Z).
                  swing (HumanoidModel.setupAttackAnimation, WHACK, head level), attackTime t:
                      body.yRot b = 0.2·sin(√t·2π); arm pivot (−5·cos b, 2, 5·sin b);
                      xRot = −π/10 − 1.2·sin(outQuart(t)·π) − 0.525·sin(t·π); yRot = 3b; zRot = −0.4·sin(t·π)
                      (outQuart(t) = 1 − (1 − t)⁴).

  shading         vanilla item lighting: 0.4 + 0.6·(max(0, n·L0) + max(0, n·L1)), L0 = (0.2, 1, −0.7),
                  L1 = (−0.2, 1, 0.7); faces with shade = false / light_emission are drawn full bright.

Checked against the owner's in-game footage (scythe idle + swing, longsword idle): the renders match.
Dev tool only: needs numpy (not a pack dependency).  Rendering: z-buffered, near-plane clipped,
perspective-correct nearest-neighbour textured quads, back-face culled, 2× supersampled.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

try:
    import numpy as np
except ImportError:  # pragma: no cover
    sys.exit('hold_preview.py needs numpy (dev tool): pip install numpy')
import yaml
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, PACK)

CONTENT = os.path.join(PACK, '..', 'plugin', 'src', 'main', 'resources', 'content', 'items.yml')
NS = 'labyrinth'

FP_W, FP_H = 448, 252          # one first-person cell (16:9)
TP_S = 252                     # one third-person cell
SS = 2                         # supersampling
SWING = (0.0, 0.1, 0.25, 0.5, 0.75)
HAND_FOV = 70.0
NEAR = 0.05

# vanilla item/handheld (sword/axe/hoe…) and item/bow display transforms (26.3 assets)
HANDHELD = {
    'thirdperson_righthand': {'rotation': [0, -90, 55], 'translation': [0, 4.0, 0.5], 'scale': [0.85] * 3},
    'firstperson_righthand': {'rotation': [0, -90, 25], 'translation': [1.13, 3.2, 1.13], 'scale': [0.68] * 3},
}
VANILLA_BOW = {
    'thirdperson_righthand': {'rotation': [-80, 260, -40], 'translation': [-1, -2, 2.5], 'scale': [0.9] * 3},
    'firstperson_righthand': {'rotation': [0, -90, 25], 'translation': [1.13, 3.2, 1.13], 'scale': [0.68] * 3},
}
REF_DISPLAY = {'iron_sword': HANDHELD, 'iron_axe': HANDHELD, 'bow': VANILLA_BOW}
LIGHT0 = np.array([0.2, 1.0, -0.7]) / np.linalg.norm([0.2, 1.0, -0.7])
LIGHT1 = np.array([-0.2, 1.0, 0.7]) / np.linalg.norm([-0.2, 1.0, 0.7])


# ───────────────────────────── matrices ─────────────────────────────

def T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def S(x, y=None, z=None):
    y = x if y is None else y
    z = x if z is None else z
    return np.diag([x, y, z, 1.0])


def Rx(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1.0]])


def Ry(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1.0]])


def Rz(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]])


def mm(*ms):
    out = np.eye(4)
    for m in ms:
        out = out @ m
    return out


def item_transform(t, left=False):
    """ItemTransform.apply (incl. the trailing translate(−0.5)) for a JSON display entry."""
    t = t or {}
    r = list(t.get('rotation', [0, 0, 0]))
    tr = [max(-5.0, min(5.0, v / 16.0)) for v in t.get('translation', [0, 0, 0])]
    sc = [max(-4.0, min(4.0, v)) for v in t.get('scale', [1, 1, 1])]
    if left:
        r[1], r[2], tr[0] = -r[1], -r[2], -tr[0]
    return mm(T(*tr), Rx(r[0]), Ry(r[1]), Rz(r[2]), S(*sc), T(-0.5, -0.5, -0.5))


def fp_matrix(display, p=0.0, h=0.0):
    """Model (block units) → view space, first person right hand, attack progress p."""
    sp = math.sin(math.sqrt(p) * math.pi)
    swing_t = T(-0.4 * sp, 0.2 * math.sin(math.sqrt(p) * 2 * math.pi), -0.2 * math.sin(p * math.pi))
    attack = mm(Ry(45 - 20 * math.sin(p * p * math.pi)), Rz(-20 * sp), Rx(-80 * sp), Ry(-45))
    return mm(T(0.56, -0.52 - 0.6 * h, -0.72), swing_t, attack,
              item_transform(display.get('firstperson_righthand')))


def fp_bow_draw_matrix(display, power=1.0, h=0.0):
    """First person right hand while drawing a bow (ItemUseAnimation.BOW, shake ignored)."""
    return mm(T(0.56, -0.52 - 0.6 * h, -0.72), T(-0.2785682, 0.18344387, 0.15731531),
              Rx(-13.935), Ry(35.3), Rz(-9.785), T(0, 0, 0.04 * power), S(1, 1, 1 + 0.2 * power), Ry(-45),
              item_transform(display.get('firstperson_righthand')))


def rot_zyx(xr, yr, zr):
    """ModelPart.translateAndRotate: Quaternionf.rotationZYX(z, y, x) (radians) → Rz·Ry·Rx."""
    return mm(Rz(math.degrees(zr)), Ry(math.degrees(yr)), Rx(math.degrees(xr)))


ENTITY = mm(Ry(180.0), S(-1, -1, 1), S(0.9375), T(0, -1.501, 0))
ARM_XROT = -math.pi / 10           # ArmPose.ITEM


def tp_pose(t=0.0):
    """HumanoidModel.poseRightArm(ITEM) + setupAttackAnimation(WHACK, right arm, head level) at attackTime t.
    Returns {part: (pivot px, (xRot, yRot, zRot) rad)} for body / right_arm / left_arm."""
    by = 0.2 * math.sin(math.sqrt(t) * 2 * math.pi) if t > 0 else 0.0
    xr, yr, zr = ARM_XROT, 0.0, 0.0
    if t > 0:
        aa = math.sin((1 - (1 - t) ** 4) * math.pi)            # Ease.outQuart
        bb = math.sin(t * math.pi) * 0.7 * 0.75                 # −(head.xRot − 0.7)·0.75, head.xRot = 0
        xr -= aa * 1.2 + bb
        yr = 3 * by                                             # += body.yRot, then += body.yRot·2
        zr = math.sin(t * math.pi) * -0.4
    return {'body': ((0, 0, 0), (0, by, 0)),
            'right_arm': ((-math.cos(by) * 5, 2, math.sin(by) * 5), (xr, yr, zr)),
            'left_arm': ((math.cos(by) * 5, 2, -math.sin(by) * 5), (by, by, 0))}


def right_arm_matrix(t=0.0):
    piv, rot = tp_pose(t)['right_arm']
    return mm(ENTITY, T(piv[0] / 16, piv[1] / 16, piv[2] / 16), rot_zyx(*rot))


def tp_matrix(display, t=0.0):
    return mm(right_arm_matrix(t), Rx(-90), Ry(180), T(1 / 16, 2 / 16, -10 / 16),
              item_transform(display.get('thirdperson_righthand')))


def look_at(eye, target):
    eye, target = np.asarray(eye, float), np.asarray(target, float)
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = r, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


# ───────────────────────────── geometry ─────────────────────────────

def _corners(face, frm, to):
    """Face corners at texture (a, b) = (0,0), (1,0), (1,1), (0,1) — same UV convention as src/model.py."""
    (x1, y1, z1), (x2, y2, z2) = frm, to

    def at(a, b):
        if face == 'north':
            return (x2 - a * (x2 - x1), y2 - b * (y2 - y1), z1)
        if face == 'south':
            return (x1 + a * (x2 - x1), y2 - b * (y2 - y1), z2)
        if face == 'east':
            return (x2, y2 - b * (y2 - y1), z2 - a * (z2 - z1))
        if face == 'west':
            return (x1, y2 - b * (y2 - y1), z1 + a * (z2 - z1))
        if face == 'up':
            return (x1 + a * (x2 - x1), y2, z1 + b * (z2 - z1))
        return (x1 + a * (x2 - x1), y1, z2 - b * (z2 - z1))
    return [at(0, 0), at(1, 0), at(1, 1), at(0, 1)]


def _rot_el(pts, rot):
    ax, ang = rot['axis'], math.radians(rot['angle'])
    o = np.asarray(rot['origin'], float)
    c, s = math.cos(ang), math.sin(ang)
    out = []
    for p in pts:
        x, y, z = np.asarray(p, float) - o
        if ax == 'x':
            q = (x, y * c - z * s, y * s + z * c)
        elif ax == 'y':
            q = (x * c + z * s, y, -x * s + z * c)
        else:
            q = (x * c - y * s, x * s + y * c, z)
        out.append(tuple(np.asarray(q) + o))
    return out


class Quad:
    __slots__ = ('pts', 'uv', 'tex', 'bright', 'blend', 'flat')

    def __init__(self, pts, uv, tex, bright, blend=False, flat=None):
        self.pts = np.asarray(pts, float)       # 4×3 model units
        self.uv = np.asarray(uv, float)         # 4×2 in 0..16
        self.tex = tex                          # texture key or None
        self.bright = bright                    # False → full bright
        self.blend = blend                      # alpha-blended overlay
        self.flat = flat                        # flat colour (mannequin)


def quads_from_json(mj):
    out = []
    for el in mj.get('elements', []):
        frm, to = el['from'], el['to']
        shade = el.get('shade', True) and not el.get('light_emission')
        for face, fd in el.get('faces', {}).items():
            pts = _corners(face, frm, to)
            if el.get('rotation'):
                pts = _rot_el(pts, el['rotation'])
            u0, v0, u1, v1 = fd.get('uv', [0, 0, 16, 16])
            uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            key = fd.get('texture', '#0').lstrip('#')
            out.append(Quad(pts, uv, key, shade, blend=(key != '0')))
    return out


_STANDIN = {
    # original stand-in sprites drawn with the vanilla layout (handle bottom-left → head top-right;
    # tool heads stick out on the upper-left side of the handle, i.e. toward model −X)
    'iron_sword': ('.............ggg', '............gwwg', '...........gwwwg', '..........gwwwg.', '.........gwwwg..',
                   '........gwwwg...', '..gg...gwwwg....', '..ggg.gwwwg.....', '...gggwgwg......', '...ggggwg.......',
                   '....gggg........', '...bbgggg.......', '..bbg.gggg......', 'ggbg....gg......', 'ggg.............',
                   'ggg.............'),
    'iron_axe': ('................', '.........gg.....', '........gwwg....', '.......gwwwg....', '......gwwwwbb...',
                 '......gwwwgwg...', '.......ggbwgwg..', '........bbgwwg..', '.......bbg.gg...', '......bbg.......',
                 '.....bbg........', '....bbg.........', '...bbg..........', '..bbg...........', '..gg............',
                 '................'),
    'bow': ('................', '...........bbbb.', '........bbbbbbbg', '......bbbbbgggg.', '.....bgbggg..g..',
            '....bggg....g...', '...bggg....g....', '...bbg....g.....', '..bbg....g......', '..bbg...g.......',
            '..bbg..g........', '.bbg..g.........', '.bbg.g..........', '.bbgg...........', '.bbg............',
            '..g.............'),
}
_STANDIN_COL = {'w': (225, 225, 232, 255), 'g': (120, 122, 130, 255), 'b': (110, 78, 48, 255)}
# where the third-person fist holds the vanilla sprite (inverse of the TP chain at the fist centre, see
# selftest()): texture pixel ≈ (2.5, 12.5) → model (2.5, 3.5, 8)
REF_GRIP = {'iron_sword': (2.5, 3.5, 8.0), 'iron_axe': (3.5, 3.5, 8.0), 'bow': (6.5, 9.0, 8.0)}


def vanilla_sprite(name='iron_sword', vanilla_dir=None):
    """Reference item: 16×16 sprite extruded like item/generated (1 texel thick, z 7.5..8.5)."""
    path = os.path.join(vanilla_dir, name + '.png') if vanilla_dir else ''
    if path and os.path.exists(path):
        img = Image.open(path).convert('RGBA')
        src = f'vanilla {name}.png'
    else:
        img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
        for y, row in enumerate(_STANDIN[name]):
            for x, ch in enumerate(row):
                if ch in _STANDIN_COL:
                    img.putpixel((x, y), _STANDIN_COL[ch])
        src = f'stand-in {name} (vanilla layout)'
    a = np.asarray(img)
    quads = []
    for py in range(16):
        for px in range(16):
            if a[py, px, 3] < 8:
                continue
            col = tuple(int(c) for c in a[py, px, :3])
            frm, to = (px, 15 - py, 7.5), (px + 1, 16 - py, 8.5)
            for face in ('north', 'south', 'east', 'west', 'up', 'down'):
                nx, ny = {'east': (1, 0), 'west': (-1, 0), 'up': (0, -1), 'down': (0, 1)}.get(face, (0, 0))
                if (nx or ny) and 0 <= px + nx < 16 and 0 <= py + ny < 16 and a[py + ny, px + nx, 3] >= 8:
                    continue
                quads.append(Quad(_corners(face, frm, to), [(0, 0)] * 4, None, True, flat=col))
    return quads, src


# ───────────────────────────── rasteriser ─────────────────────────────

class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.rgb = bg.astype(np.float32).copy()
        self.key = np.full((h, w), -np.inf)
        self.mask = np.zeros((h, w), bool)     # item pixels (coverage metric)

    def image(self):
        img = Image.fromarray(np.clip(self.rgb, 0, 255).astype(np.uint8), 'RGB')
        return img.resize((self.w // SS, self.h // SS), Image.LANCZOS)


def _clip_near(vs, uvs):
    """Sutherland–Hodgman against z = −NEAR (keep −z ≥ NEAR)."""
    out_v, out_uv = [], []
    n = len(vs)
    for i in range(n):
        a, b = vs[i], vs[(i + 1) % n]
        ua, ub = uvs[i], uvs[(i + 1) % n]
        ina, inb = -a[2] >= NEAR, -b[2] >= NEAR
        if ina:
            out_v.append(a)
            out_uv.append(ua)
        if ina != inb:
            t = (-NEAR - a[2]) / (b[2] - a[2])
            out_v.append(a + (b - a) * t)
            out_uv.append(ua + (ub - ua) * t)
    return out_v, out_uv


class Projector:
    def __init__(self, w, h, ortho=None):
        self.w, self.h = w, h
        self.ortho = ortho            # None (perspective, hand FOV) or (cx, cy, px_per_block)
        self.fy = 1.0 / math.tan(math.radians(HAND_FOV / 2))
        self.fx = self.fy / (w / h)

    def project(self, v):
        if self.ortho is None:
            d = -v[2]
            x = (self.fx * v[0] / d + 1) * 0.5 * self.w
            y = (1 - self.fy * v[1] / d) * 0.5 * self.h
            return x, y, 1.0 / d, 1.0 / d          # (x, y, depth key [bigger = nearer], perspective weight)
        cx, cy, k = self.ortho
        return self.w / 2 + (v[0] - cx) * k, self.h / 2 - (v[1] - cy) * k, v[2], 1.0


def draw_quads(cv: Canvas, proj: Projector, quads, M, textures, is_item=True):
    """M: model (block units) → view space."""
    R = M[:3, :3]
    blended = []
    for q in quads:
        pv = (np.c_[q.pts / 16.0, np.ones(4)] @ M.T)[:, :3]
        n = np.cross(pv[3] - pv[0], pv[1] - pv[0])      # outward (corner order of _corners is clockwise)
        nl = np.linalg.norm(n)
        if nl < 1e-12:
            continue
        n /= nl
        # back-face culling (vanilla item render types cull)
        view = pv[0] if proj.ortho is None else np.array([0, 0, -1.0])
        if np.dot(n, view) >= 0:
            continue
        if q.bright:
            b = min(1.0, 0.4 + 0.6 * (max(0.0, n @ LIGHT0) + max(0.0, n @ LIGHT1)))
        else:
            b = 1.0
        if q.blend:
            blended.append((q, pv, b))
            continue
        _raster_poly(cv, proj, q, pv, b, textures, is_item)
    for q, pv, b in blended:
        _raster_poly(cv, proj, q, pv, b, textures, is_item, blend=True)
    return R


def _raster_poly(cv, proj, q, pv, b, textures, is_item, blend=False):
    vs, uvs = list(pv), list(q.uv)
    if proj.ortho is None:
        vs, uvs = _clip_near(vs, uvs)
        if len(vs) < 3:
            return
    P = [proj.project(v) for v in vs]
    tex = textures.get(q.tex) if q.tex else None
    for i in range(1, len(P) - 1):
        _raster_tri(cv, (P[0], P[i], P[i + 1]), (uvs[0], uvs[i], uvs[i + 1]), tex, q.flat, b, is_item, blend)


def _raster_tri(cv, P, UV, tex, flat, b, is_item, blend):
    (x0, y0, k0, w0), (x1, y1, k1, w1), (x2, y2, k2, w2) = P
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-9:
        return
    bx0, bx1 = max(0, int(math.floor(min(x0, x1, x2)))), min(cv.w - 1, int(math.ceil(max(x0, x1, x2))))
    by0, by1 = max(0, int(math.floor(min(y0, y1, y2)))), min(cv.h - 1, int(math.ceil(max(y0, y1, y2))))
    if bx0 > bx1 or by0 > by1:
        return
    xs = np.arange(bx0, bx1 + 1) + 0.5
    ys = np.arange(by0, by1 + 1) + 0.5
    X, Y = np.meshgrid(xs, ys)
    e0 = ((x2 - x1) * (Y - y1) - (y2 - y1) * (X - x1)) / area
    e1 = ((x0 - x2) * (Y - y2) - (y0 - y2) * (X - x2)) / area
    e2 = 1.0 - e0 - e1
    inside = (e0 >= -1e-7) & (e1 >= -1e-7) & (e2 >= -1e-7)
    if not inside.any():
        return
    key = e0 * k0 + e1 * k1 + e2 * k2
    sub_key = cv.key[by0:by1 + 1, bx0:bx1 + 1]
    vis = inside & (key > sub_key)
    if not vis.any():
        return
    if flat is not None:
        col = np.broadcast_to(np.array(flat, np.float32), X.shape + (3,))
        alpha = np.ones(X.shape, np.float32)
    else:
        if tex is None:
            return
        ww = e0 * w0 + e1 * w1 + e2 * w2
        u = (e0 * w0 * UV[0][0] + e1 * w1 * UV[1][0] + e2 * w2 * UV[2][0]) / ww
        v = (e0 * w0 * UV[0][1] + e1 * w1 * UV[1][1] + e2 * w2 * UV[2][1]) / ww
        th, tw = tex.shape[:2]
        ti = np.clip((u * tw / 16.0).astype(int), 0, tw - 1)
        tj = np.clip((v * th / 16.0).astype(int), 0, th - 1)
        texel = tex[tj, ti].astype(np.float32)
        col, alpha = texel[..., :3], texel[..., 3] / 255.0
        if blend:
            vis &= alpha > 0.02
        else:
            vis &= alpha > 0.03
    if not vis.any():
        return
    sub = cv.rgb[by0:by1 + 1, bx0:bx1 + 1]
    c = col * b
    if blend:
        a = alpha[..., None] * 0.85
        sub[vis] = (sub * (1 - a) + c * a)[vis]
    else:
        sub[vis] = c[vis]
        sub_key[vis] = key[vis]
    if is_item:
        cv.mask[by0:by1 + 1, bx0:bx1 + 1] |= vis


# ───────────────────────────── scenes ─────────────────────────────

def fp_background(w, h):
    yy = np.linspace(0, 1, h)[:, None, None]
    sky = (1 - yy * 2).clip(0, 1) * np.array([110, 160, 250]) + (yy * 2).clip(0, 1) * np.array([185, 210, 250])
    ground = np.array([88, 132, 58]) * (0.85 + 0.3 * (yy - 0.5))
    img = np.where(yy < 0.5, sky, ground) * np.ones((1, w, 1))
    return img


def fp_overlay(img, metrics_txt=None):
    d = ImageDraw.Draw(img, 'RGBA')
    w, h = img.size
    cx, cy = w // 2, h // 2
    d.line([(cx - 6, cy), (cx + 6, cy)], fill=(255, 255, 255, 230))
    d.line([(cx, cy - 6), (cx, cy + 6)], fill=(255, 255, 255, 230))
    hw, hh = int(w * 0.42 / 2), int(h * 0.088)
    d.rectangle([cx - hw, h - hh - 2, cx + hw, h - 2], outline=(20, 20, 20, 150), fill=(0, 0, 0, 55))
    # central third of the screen (where targets are) — faint corner ticks
    x0, x1, y0, y1 = w // 3, 2 * w // 3, h // 3, 2 * h // 3
    for (x, y, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(x, y), (x + 10 * sx, y)], fill=(255, 255, 255, 90))
        d.line([(x, y), (x, y + 10 * sy)], fill=(255, 255, 255, 90))
    if metrics_txt:
        d.rectangle([2, 2, 8 + 6 * len(metrics_txt), 15], fill=(0, 0, 0, 120))
        d.text((5, 3), metrics_txt, fill=(255, 255, 255, 235))


def _proj_pt(proj, M, p):
    v = (M @ np.array([p[0] / 16, p[1] / 16, p[2] / 16, 1.0]))[:3]
    if proj.ortho is None and -v[2] < NEAR:
        return None, v
    x, y, _, _ = proj.project(v)
    return (x / SS, y / SS), v


def render_fp(quads, textures, display, p, grip, far_pt, M=None, label=None):
    W, H = FP_W * SS, FP_H * SS
    cv = Canvas(W, H, fp_background(W, H))
    proj = Projector(W, H)
    M = fp_matrix(display, p) if M is None else M
    draw_quads(cv, proj, quads, M, textures)
    img = cv.image()
    cov = float(cv.mask.mean())
    y0, y1, x0, x1 = H // 3, 2 * H // 3, W // 3, 2 * W // 3
    cov_c = float(cv.mask[y0:y1, x0:x1].mean())
    d = ImageDraw.Draw(img, 'RGBA')
    # swing path of the far end
    path = []
    for k in range(41):
        pt, _ = _proj_pt(proj, fp_matrix(display, k / 40), far_pt)
        path.append(pt)
    for a, c in zip(path, path[1:]):
        if a and c:
            d.line([a, c], fill=(255, 220, 40, 200), width=2)
    pt, _ = _proj_pt(proj, M, far_pt)
    if pt:
        d.ellipse([pt[0] - 3, pt[1] - 3, pt[0] + 3, pt[1] + 3], outline=(255, 220, 40, 255), width=2)
    gp, _ = _proj_pt(proj, M, grip)
    if gp:
        d.line([(gp[0] - 5, gp[1]), (gp[0] + 5, gp[1])], fill=(255, 0, 220, 255), width=2)
        d.line([(gp[0], gp[1] - 5), (gp[0], gp[1] + 5)], fill=(255, 0, 220, 255), width=2)
    fp_overlay(img, f'{label or f"p={p:g}"}  cover {cov * 100:.0f}%  centre {cov_c * 100:.0f}%')
    return img, cov, cov_c


# Steve mannequin (PlayerModel wide arms; px, entity model space with y down)
MANNEQUIN = [
    # (part, pivot, from, size, colour)
    ('head', (0, 0, 0), (-4, -8, -4), (8, 8, 8), (196, 146, 108)),
    ('body', (0, 0, 0), (-4, 0, -2), (8, 12, 4), (38, 156, 168)),
    ('right_arm', (-5, 2, 0), (-3, -2, -2), (4, 12, 4), (196, 146, 108)),
    ('left_arm', (5, 2, 0), (-1, -2, -2), (4, 12, 4), (196, 146, 108)),
    ('right_leg', (-1.9, 12, 0), (-2, 0, -2), (4, 12, 4), (58, 56, 140)),
    ('left_leg', (1.9, 12, 0), (-2, 0, -2), (4, 12, 4), (58, 56, 140)),
]


def _mannequin_quads(t=0.0):
    pose = tp_pose(t)
    out = []
    for part, piv, frm, size, col in MANNEQUIN:
        piv, rot = pose.get(part, (piv, (0, 0, 0)))
        M = mm(ENTITY, T(piv[0] / 16, piv[1] / 16, piv[2] / 16), rot_zyx(*rot))
        to = tuple(frm[i] + size[i] for i in range(3))
        qs = []
        for face in ('north', 'south', 'east', 'west', 'up', 'down'):
            c = col
            if face == 'north' and part == 'head':
                c = (150, 108, 80)      # face side a bit darker so the facing direction reads
            if face == 'down' and part == 'right_arm':
                c = (230, 180, 140)     # fist
            qs.append(Quad(_corners(face, frm, to), [(0, 0)] * 4, None, True, flat=c))
        out.append((M, qs))
    return out


# third-person cells: (camera eye, attackTime, label)
TP_VIEWS = {
    'front34': ((-1.55, 1.55, 2.25), 0.0, 'front 3/4'),
    'back34': ((-1.0, 2.2, -2.6), 0.0, 'back 3/4 (F5)'),
    'swing15': ((-3.0, 1.5, 0.5), 0.15, 'right side, swing t=0.15'),
    'swing50': ((-3.0, 1.5, 0.5), 0.5, 'right side, swing t=0.5'),
}


def render_tp(quads, textures, display, view, grip):
    W = H = TP_S * SS
    eye, t, label = TP_VIEWS[view]
    target = (-0.25, 1.2, 0.2)
    V = look_at(eye, target)
    bg = np.ones((H, W, 3)) * np.array([66, 70, 82])
    cv = Canvas(W, H, bg)
    proj = Projector(W, H, ortho=(0.0, 0.0, H / 3.3))
    for M, qs in _mannequin_quads(t):
        draw_quads(cv, proj, qs, V @ M, {}, is_item=False)
    M = V @ tp_matrix(display, t)
    draw_quads(cv, proj, quads, M, textures)
    img = cv.image()
    d = ImageDraw.Draw(img, 'RGBA')
    gp, _ = _proj_pt(proj, M, grip)
    if gp:
        d.line([(gp[0] - 5, gp[1]), (gp[0] + 5, gp[1])], fill=(255, 0, 220, 255), width=2)
        d.line([(gp[0], gp[1] - 5), (gp[0], gp[1] + 5)], fill=(255, 0, 220, 255), width=2)
    # fist centre (inside the bottom of the right arm cube) for comparison
    fist = (V @ right_arm_matrix(t) @ np.array([-1 / 16, 9 / 16, 0, 1.0]))[:3]
    fx, fy, _, _ = proj.project(fist)
    d.ellipse([fx / SS - 3, fy / SS - 3, fx / SS + 3, fy / SS + 3], outline=(0, 255, 120, 255), width=1)
    d.text((4, 3), label, fill=(230, 230, 235, 255))
    return img


# ───────────────────────────── items ─────────────────────────────

def _png(b):
    img = Image.open(io.BytesIO(b)).convert('RGBA')
    w, h = img.size
    if h > w:
        img = img.crop((0, 0, w, w))      # animated strip → frame 0
    return np.asarray(img)


def build(iid, it, extra=()):
    """→ {model name: (model json, textures)} for the item's own model and any `extra` sibling models."""
    from src import items  # noqa: E402  (heavy import; done in the worker)
    res = items.build_item(iid, it)
    out = {}
    for name in (iid, *extra):
        key = f'assets/{NS}/models/item/{name}.json'
        if key not in res.files:
            continue
        mj = json.loads(res.files[key])
        textures = {}
        for k, ref in mj.get('textures', {}).items():
            ns, path = ref.split(':', 1) if ':' in ref else ('minecraft', ref)
            b = res.files.get(f'assets/{ns}/textures/{path}.png')
            if b:
                textures[k] = _png(b)
        out[name] = (mj, textures)
    return out


def far_point(quads, grip):
    g = np.asarray(grip, float)
    best, bd = None, -1.0
    for q in quads:
        if q.blend:
            continue
        for p in q.pts:
            dd = float(np.sum((p - g) ** 2))
            if dd > bd:
                bd, best = dd, p
    return tuple(best)


def head_metrics(display, grip, far_pt):
    """Direction grip → far end at idle, in view space (z > 0 = toward the camera) and on screen."""
    M = fp_matrix(display, 0.0)
    g = (M @ np.array([*np.asarray(grip) / 16, 1.0]))[:3]
    f = (M @ np.array([*np.asarray(far_pt) / 16, 1.0]))[:3]
    d = f - g
    L = float(np.linalg.norm(d))
    d = d / max(L, 1e-9)
    proj = Projector(FP_W, FP_H)
    gs = proj.project(g) if -g[2] > NEAR else None
    fs = proj.project(f) if -f[2] > NEAR else None
    ang = None
    if gs and fs:
        ang = math.degrees(math.atan2(-(fs[1] - gs[1]), fs[0] - gs[0]))   # 90 = straight up, >90 = up-left
    return {'toward_camera': round(float(d[2]), 2), 'length_blocks': round(L, 2),
            'grip_screen': None if not gs else [round(float(gs[0]) / FP_W, 3), round(float(gs[1]) / FP_H, 3)],
            'far_screen': None if not fs else [round(float(fs[0]) / FP_W, 3), round(float(fs[1]) / FP_H, 3)],
            'screen_angle_deg': None if ang is None else round(ang), 'far_end_view': [round(float(v), 3) for v in f],
            'far_end_dist': round(float(np.linalg.norm(f)), 3)}


def head_side(quads, grip, display, spine=(0.0, 1.0, 0.0)):
    """Which way the head sticks out sideways from the haft.  Takes the vertices in the top 35 % along the
    spine axis, averages their offset perpendicular to the spine (model XY plane) and maps that direction
    into first-person view space (fp_*: +z = toward the camera, +x = right) and into the world for the
    third-person idle pose (tp_forward: +1 = in front of the player, −1 = back toward the player)."""
    g = np.asarray(grip, float)
    a = np.asarray(spine, float) / np.linalg.norm(spine)
    pts = np.array([p for q in quads if not q.blend for p in q.pts], float)
    if not len(pts):
        return {}
    t = (pts - g) @ a
    top = pts[t >= t.max() * 0.65]
    off = (top - g) - np.outer((top - g) @ a, a)
    off[:, 2] = 0.0
    m = off.mean(axis=0)
    mag = float(np.linalg.norm(m))
    if mag < 1e-6:
        return {'head_offset': 0.0}
    u = m / mag
    v = fp_matrix(display, 0.0)[:3, :3] @ u
    w = tp_matrix(display, 0.0)[:3, :3] @ u
    v, w = v / np.linalg.norm(v), w / np.linalg.norm(w)
    return {'head_offset': round(mag, 2), 'head_fp_toward_camera': round(float(v[2]), 2),
            'head_fp_right': round(float(v[0]), 2), 'head_tp_forward': round(float(w[2]), 2)}


def render_row(label, quads, textures, display, grip, spine=(0.0, 1.0, 0.0), draw=None):
    """draw: (quads, textures, display) of the fully drawn bow model → extra first-person cell."""
    fp = far_point(quads, grip)
    cells, covs = [], []
    for p in SWING:
        img, cov, cov_c = render_fp(quads, textures, display, p, grip, fp)
        cells.append(img)
        covs.append((round(cov * 100, 1), round(cov_c * 100, 1)))
    if draw:
        dq, dt, dd = draw
        img, _, _ = render_fp(dq, dt, dd, 0.0, grip, far_point(dq, grip), M=fp_bow_draw_matrix(dd),
                              label='drawing (pulling_2)')
        cells.append(img)
    tps = [render_tp(quads, textures, display, v, grip) for v in TP_VIEWS]
    met = head_metrics(display, grip, fp)
    met.update(head_side(quads, grip, display, spine))
    met.update({'coverage_pct': covs[0][0], 'centre_coverage_pct': covs[0][1],
                'max_coverage_pct': max(c[0] for c in covs), 'max_centre_coverage_pct': max(c[1] for c in covs),
                'fp': display.get('firstperson_righthand'), 'tp': display.get('thirdperson_righthand')})
    return label, cells, tps, met


def _fmt(t):
    if not t:
        return '-'
    s = t.get('scale', [1])[0]
    return f"r{[round(v, 1) for v in t.get('rotation', [0, 0, 0])]} t{[round(v, 2) for v in t.get('translation', [0, 0, 0])]} s{s:g}"


def compose(shape, tag, rows, path):
    lab_h = 30
    nfp = max(len(r[1]) for r in rows)
    W = FP_W * nfp + TP_S * len(TP_VIEWS)
    row_h = FP_H + lab_h
    top = 26
    sheet = Image.new('RGB', (W, top + row_h * len(rows)), (34, 36, 44))
    d = ImageDraw.Draw(sheet)
    d.text((6, 6), f'{shape}  [{tag}]   first person (hand FOV 70, 16:9): idle, attack swing p=0.1/0.25/0.5/0.75 '
                   f'(p=1 = idle)   |   third person (ITEM arm pose; idle front/back, WHACK swing t=0.15/0.5)   '
                   f'yellow = far-end swing path, magenta = grip point, green = fist centre', fill=(235, 235, 240))
    for r, (label, cells, tps, met) in enumerate(rows):
        y = top + r * row_h
        for k, im in enumerate(cells):
            sheet.paste(im, (k * FP_W, y))
        for k, im in enumerate(tps):
            sheet.paste(im, (FP_W * nfp + k * TP_S, y))
        d.text((6, y + FP_H + 3), label, fill=(250, 220, 120))
        d.text((6, y + FP_H + 16),
               f"FP {_fmt(met['fp'])}   TP {_fmt(met['tp'])}   far end->camera {met['toward_camera']:+.2f}  "
               f"screen angle {met['screen_angle_deg']}  grip@{met.get('grip_screen')}  cover idle "
               f"{met['coverage_pct']}% (centre {met['centre_coverage_pct']}%) max {met['max_coverage_pct']}%   "
               f"side head {met.get('head_offset', 0)}px: FP->camera {met.get('head_fp_toward_camera', '-')} "
               f"TP forward {met.get('head_tp_forward', '-')}", fill=(200, 200, 210))
    sheet.save(path, optimize=True)


# ───────────────────────────── driver ─────────────────────────────

GRIP = (8.0, 1.0, 8.0)
BOW_GRIP = (4.5, 6.0, 8.0)
# one source for the hold tables: the pack's own voxel/weapons.py (bows; shapes whose working part sticks out
# sideways from the haft — compared against the vanilla axe as well)
from src.voxel.weapons import BOWS, HEAD_SHAPES  # noqa: E402


def weapon_shapes(items_doc):
    from src.materials import RARITY_LEVEL
    from src.voxel import weapons as VW
    from src import shapes_weapons as Wc
    known = set(VW.TEMPLATES) | set(VW.BOWS) | set(Wc.TEMPLATES) | set(Wc.BOWS)
    by = {}
    for iid, it in items_doc.items():
        if not isinstance(it, dict):
            continue
        sh = (it.get('model') or {}).get('shape')
        if sh in known:
            by.setdefault(sh, []).append((RARITY_LEVEL.get(it.get('rarity') or 'common', 0), iid))
    return {sh: sorted(v) for sh, v in by.items()}


def _apply_override(display, overrides, shape, iid):
    disp = dict(display)
    for key in (shape, iid):
        for k, v in (overrides.get(key) or {}).items():
            disp[k] = v
    return disp


def job(args):
    shape, picks, items_doc, tag, out, overrides, vanilla_dir = args
    rows = []
    metrics = {}
    refs = ['iron_sword'] + (['iron_axe'] if shape in HEAD_SHAPES else []) + (['bow'] if shape in BOWS else [])
    for ref in refs:
        vq, vsrc = vanilla_sprite(ref, vanilla_dir)
        disp = REF_DISPLAY[ref]
        row = render_row(f"reference: {vsrc} + vanilla item/{'bow' if ref == 'bow' else 'handheld'} transforms",
                         vq, {}, disp, REF_GRIP[ref], spine=(1.0, 1.0, 0.0),
                         draw=(vq, {}, disp) if ref == 'bow' else None)
        rows.append(row)
        metrics['reference_' + ref] = row[3]
    grip = BOW_GRIP if shape in BOWS else GRIP
    for iid in picks:
        it = items_doc[iid]
        models = build(iid, it, extra=(f'{iid}_pulling_2',) if shape in BOWS else ())
        mj, textures = models[iid]
        display = _apply_override(mj.get('display', {}), overrides, shape, iid)
        quads = quads_from_json(mj)
        draw = None
        if f'{iid}_pulling_2' in models:
            dj, dt = models[f'{iid}_pulling_2']
            draw = (quads_from_json(dj), dt, _apply_override(dj.get('display', {}), overrides, shape, iid))
        row = render_row(f"{iid}  ({it.get('rarity')}, {len(mj.get('elements', []))} elements)", quads, textures,
                         display, grip, draw=draw)
        rows.append(row)
        metrics[iid] = row[3]
    path = os.path.join(out, f'{tag}_{shape}.png')
    compose(shape, tag, rows, path)
    return shape, path, metrics


def selftest():
    """Sanity checks of the transform chain against facts about the vanilla client."""
    ok = True

    def check(name, cond, info=''):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'ok ' if cond else 'FAIL'} {name} {info}")

    check('swing p=1 equals idle', np.allclose(fp_matrix(HANDHELD, 1.0), fp_matrix(HANDHELD, 0.0), atol=1e-6))
    # rotationXYZ: Z first — rotating (1,0,0) by r=(0,90,90) must give Rx·Ry·Rz·x = Ry(90)·(0,1,0) = (0,1,0)
    v = item_transform({'rotation': [0, 90, 90], 'translation': [0, 0, 0], 'scale': [1, 1, 1]})
    v = (v @ np.array([1.5, 0.5, 0.5, 1.0]))[:3]
    check('ItemTransform order Rx·Ry·Rz (Z first)', np.allclose(v, (0, 1, 0), atol=1e-9), np.round(v, 3))
    # third person: the vanilla sword handle (texture px (2.5, 12.5)) sits in the fist
    A = np.linalg.inv(tp_matrix(HANDHELD)) @ right_arm_matrix()
    g = (A @ np.array([-1 / 16, 9 / 16, 0, 1.0]))[:3] * 16
    check('TP fist holds the vanilla sword handle', np.linalg.norm(g - REF_GRIP['iron_sword']) < 1.0, np.round(g, 2))
    # first person: vanilla sword sits in the lower right, blade rising (tip toward the camera)
    q, _ = vanilla_sprite('iron_sword')
    met = head_metrics(HANDHELD, REF_GRIP['iron_sword'], far_point(q, REF_GRIP['iron_sword']))
    gx, gy = met['grip_screen']
    check('FP vanilla sword grip in the lower right', gx > 0.75 and gy > 0.9, met['grip_screen'])
    check('FP vanilla sword blade rises steeply', 45 <= met['screen_angle_deg'] <= 85, met['screen_angle_deg'])
    # the vanilla axe head points away from the camera (FP) — the convention our heads must follow
    q, _ = vanilla_sprite('iron_axe')
    hs = head_side(q, REF_GRIP['iron_axe'], HANDHELD, spine=(1, 1, 0))
    check('FP vanilla axe head points away from the camera', hs['head_fp_toward_camera'] < -0.5, hs)
    # chop: at p = 0.25 the far end of the sword is left of and below where it was at idle
    fp0 = (fp_matrix(HANDHELD, 0.0) @ np.array([15 / 16, 15 / 16, 0.5, 1]))[:3]
    fp1 = (fp_matrix(HANDHELD, 0.25) @ np.array([15 / 16, 15 / 16, 0.5, 1]))[:3]
    check('swing chops toward the lower left', fp1[0] < fp0[0] and fp1[1] < fp0[1], (np.round(fp0, 2), np.round(fp1, 2)))
    # our weapons (src/displays.py): the working side +X goes where the vanilla axe head goes
    from src import displays as D
    r1, _ = D.held((0, 90, 20), D.FP_REF[2], D.FP_REF)
    r3, _ = D.held(D.TP_REF[0], 0.85, (D.TP_REF[0], D.TP_REF[1], 0.85))
    ours = {'firstperson_righthand': r1, 'thirdperson_righthand': r3}
    vx = fp_matrix(ours)[:3, :3] @ np.array([1.0, 0, 0])
    wx = tp_matrix(ours)[:3, :3] @ np.array([1.0, 0, 0])
    check('our +X edge points away from the camera (FP)', vx[2] / np.linalg.norm(vx) < -0.5, np.round(vx, 2))
    check('our +X edge points the same way as the vanilla axe head (TP)',
          np.sign(wx[2]) == np.sign(hs['head_tp_forward']), (np.round(wx, 2), hs['head_tp_forward']))
    # displays.held keeps the grip in the hand for any scale / yaw, both hands (client: left = mirrored arm chain)
    Fx = np.diag([-1.0, 1, 1, 1])
    g = np.array([*np.asarray(GRIP) / 16, 1.0])
    ref_r, ref_l = D.held(D.FP_REF[0], D.FP_REF[2], D.FP_REF)
    arm = fp_matrix({}, 0.25) @ np.linalg.inv(item_transform(None))      # arm chain without the item transform
    err = 0.0
    for rot, s in (((0, 125, 20), 0.6), ((0, 90, 20), 0.45)):
        r, lft = D.held(rot, s, D.FP_REF)
        err = max(err, np.abs(arm @ item_transform(r) @ g - arm @ item_transform(ref_r) @ g).max(),
                  np.abs(Fx @ arm @ Fx @ item_transform(lft, True) @ g
                         - Fx @ arm @ Fx @ item_transform(ref_l, True) @ g).max())
    check('displays.held keeps the grip point (right + left hand)', err < 1e-3, f'max {err:.1e} block')
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--content', default=CONTENT)
    ap.add_argument('--shapes', default='', help='comma list (default: every weapon shape in items.yml)')
    ap.add_argument('--items', default='', help='comma list of item ids (rendered under their shape)')
    ap.add_argument('--out', default=os.path.join(PACK, 'dist', 'hold_preview'))
    ap.add_argument('--tag', default='preview')
    ap.add_argument('--override', default='')
    ap.add_argument('--vanilla-dir', default='')
    ap.add_argument('--jobs', type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    ap.add_argument('--selftest', action='store_true', help='check the transform chain and exit')
    ap.add_argument('--extra-items', default='auto', help='auto | off | FILE,... (see src/extra_items.py)')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    with open(a.content, encoding='utf-8') as f:
        doc = yaml.safe_load(f) or {}
    items_doc = doc.get('items', doc)
    from src import extra_items
    ex = extra_items.merge(items_doc, dict(doc.get('sets') or {}), a.extra_items)
    if ex['added']:
        print(f"extra items: {len(ex['added'])} from {ex['source']}")
    shapes = weapon_shapes(items_doc)
    overrides = {}
    if a.override:
        with open(a.override, encoding='utf-8') as f:
            overrides = json.load(f)
    want = [s for s in a.shapes.split(',') if s] or sorted(shapes)
    tasks = []
    if a.items:
        ids = [i for i in a.items.split(',') if i]
        by_shape = {}
        for iid in ids:
            sh = (items_doc[iid].get('model') or {}).get('shape')
            by_shape.setdefault(sh, []).append(iid)
        for sh, picks in by_shape.items():
            tasks.append((sh, picks))
    else:
        for sh in want:
            lst = shapes.get(sh)
            if not lst:
                print(f'skip {sh}: no items')
                continue
            picks = [lst[0][1]] + ([lst[-1][1]] if lst[-1][1] != lst[0][1] else [])
            tasks.append((sh, picks))
    os.makedirs(a.out, exist_ok=True)
    allm = {}
    jobs = [(sh, picks, items_doc, a.tag, a.out, overrides, a.vanilla_dir or None) for sh, picks in tasks]
    if a.jobs > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(a.jobs) as ex:
            results = list(ex.map(job, jobs))
    else:
        results = [job(j) for j in jobs]
    for shape, path, met in results:
        allm[shape] = met
        print(path)
    mpath = os.path.join(a.out, f'{a.tag}_metrics.json')
    old = {}
    if os.path.exists(mpath):
        with open(mpath, encoding='utf-8') as f:
            old = json.load(f)
    old.update(allm)
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(old, f, ensure_ascii=False, indent=1)
    print(mpath)


if __name__ == '__main__':
    main()
