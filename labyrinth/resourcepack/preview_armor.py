#!/usr/bin/env python3
"""Armour look preview without a game client.

A Steve-proportioned mannequin (head 8×8×8, body 8×12×4, arms/legs 4×12×4 px; vanilla player model scale 0.9375,
HumanoidModel crouch pose) wears the set's current equipment layers (src/equipment.py, vanilla 64×32 UV layout,
armour boxes inflated 1.0 / 0.5 px) plus the 3D shoulder/back pieces (src/armor_pieces.py) placed with EXACTLY
the plugin's transforms — the numbers are read from ArmorPieceLayout.java's @layout-table at run time.

    python3 preview_armor.py [--out DIR] [--sets emberforged,wayfarer,silkweaver] [--overview]

Writes pieces_<look>_<set>.png (rows: before / after standing / after sneaking; columns: front, left side, back,
3/4 back) and, with --overview, pieces_all_sets.png.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import yaml
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src import armor_pieces as AP  # noqa: E402
from src import equipment, render  # noqa: E402
from src.util import stable_seed  # noqa: E402

CONTENT = os.path.join(HERE, '..', 'plugin', 'src', 'main', 'resources', 'content')
JAVA = os.path.join(HERE, '..', 'plugin', 'src', 'main', 'java', 'kr', 'labyrinth', 'items', 'ArmorPieceLayout.java')
K = 0.9375 / 16.0                 # one skin pixel in blocks
NECK_Y = 1.501 * 0.9375           # LivingEntityRenderer translate(0, -1.501, 0) under the 0.9375 scale

# ───────────────────────────── mannequin ─────────────────────────────


def _base_skin():
    """Plain 64×64 mannequin skin (original): skin-tone head with a face, grey tunic, dark trousers."""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    px = img.load()

    def box(u, v, w, h, d, col):
        for (x0, y0, ww, hh) in ((u + d, v, w, d), (u + d + w, v, w, d), (u, v + d, d, h), (u + d, v + d, w, h),
                                 (u + d + w, v + d, d, h), (u + 2 * d + w, v + d, w, h)):
            for y in range(y0, y0 + hh):
                for x in range(x0, x0 + ww):
                    c = col(x - x0, y - y0, ww, hh)
                    px[x, y] = c + (255,)

    skin = (198, 152, 118)
    box(0, 0, 8, 8, 8, lambda i, j, w, h: skin)
    for (x, y, c) in ((9, 12, (40, 40, 52)), (10, 12, (240, 240, 240)), (13, 12, (240, 240, 240)), (14, 12, (40, 40, 52)),
                      (11, 14, (170, 120, 92)), (12, 14, (170, 120, 92)), (10, 15, (120, 70, 60)), (13, 15, (120, 70, 60))):
        px[x, y] = c + (255,)
    for x in range(8, 16):
        px[x, 8] = (70, 52, 40, 255)
        px[x, 9] = (70, 52, 40, 255)
    box(16, 16, 8, 12, 4, lambda i, j, w, h: (118, 120, 128) if (i + j) % 7 else (104, 106, 114))
    box(40, 16, 4, 12, 4, lambda i, j, w, h: skin if j >= 8 else (118, 120, 128))
    box(32, 48, 4, 12, 4, lambda i, j, w, h: skin if j >= 8 else (118, 120, 128))
    box(0, 16, 4, 12, 4, lambda i, j, w, h: (58, 62, 80) if j < 10 else (40, 34, 30))
    box(16, 48, 4, 12, 4, lambda i, j, w, h: (58, 62, 80) if j < 10 else (40, 34, 30))
    return img


def _rx(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c)


def _box_faces(mn, mx, u, v, size, mirror):
    """Vanilla ModelPart.Cube faces in model space (y down): [(dir, p00, p10, p01, (u0, v0, u1, v1))]."""
    w, h, d = size
    X0, Y0, Z0 = mn
    X1, Y1, Z1 = mx
    if mirror:
        X0, X1 = X1, X0
    f4, f5, f6, f7, f8, f9 = u, u + d, u + d + w, u + d + 2 * w, u + 2 * d + w, u + 2 * d + 2 * w
    f10, f11, f12 = v, v + d, v + d + h
    faces = [
        ('down', (X0, Y0, Z1), (X1, Y0, Z1), (X0, Y0, Z0), (f5, f10, f6, f11)),     # world top
        ('up', (X0, Y1, Z1), (X1, Y1, Z1), (X0, Y1, Z0), (f6, f10, f7, f11)),       # world bottom
        ('west', (X0, Y0, Z1), (X0, Y0, Z0), (X0, Y1, Z1), (f4, f11, f5, f12)),
        ('north', (X0, Y0, Z0), (X1, Y0, Z0), (X0, Y1, Z0), (f5, f11, f6, f12)),
        ('east', (X1, Y0, Z0), (X1, Y0, Z1), (X1, Y1, Z0), (f6, f11, f8, f12)),
        ('south', (X1, Y0, Z1), (X0, Y0, Z1), (X1, Y1, Z1), (f8, f11, f9, f12)),
    ]
    return faces


# model-space outward normals (y down, x = figure's left, z = figure's back)
_MN = {'down': (0, -1, 0), 'up': (0, 1, 0), 'west': (-1, 0, 0), 'east': (1, 0, 0), 'north': (0, 0, -1), 'south': (0, 0, 1)}


def _parts(crouch):
    """HumanoidModel parts: name → (pivot, box min, size, xRot)."""
    dy = 3.2 if crouch else 0.0
    return {
        'head': ((0, 4.2 if crouch else 0, 0), (-4, -8, -4), (8, 8, 8), 0.0),
        'body': ((0, dy, 0), (-4, 0, -2), (8, 12, 4), 0.5 if crouch else 0.0),
        'right_arm': ((-5, 2 + dy, 0), (-3, -2, -2), (4, 12, 4), 0.4 if crouch else 0.0),
        'left_arm': ((5, 2 + dy, 0), (-1, -2, -2), (4, 12, 4), 0.4 if crouch else 0.0),
        'right_leg': ((-1.9, 12.2 if crouch else 12, 4 if crouch else 0), (-2, 0, -2), (4, 12, 4), 0.0),
        'left_leg': ((1.9, 12.2 if crouch else 12, 4 if crouch else 0), (-2, 0, -2), (4, 12, 4), 0.0),
    }


SKIN_UV = {'head': (0, 0, False), 'body': (16, 16, False), 'right_arm': (40, 16, False), 'left_arm': (32, 48, False),
           'right_leg': (0, 16, False), 'left_leg': (16, 48, False)}
ARMOR_UV = {'body': (16, 16, False), 'right_arm': (40, 16, False), 'left_arm': (40, 16, True),
            'right_leg': (0, 16, False), 'left_leg': (0, 16, True)}


def _part_quads(parts, name, tex, uvmap, grow, crouch):
    pivot, mn, size, xrot = parts[name]
    u, v, mirror = uvmap[name]
    lo = (mn[0] - grow, mn[1] - grow, mn[2] - grow)
    hi = (mn[0] + size[0] + grow, mn[1] + size[1] + grow, mn[2] + size[2] + grow)
    top = NECK_Y + (-0.125 if crouch else 0.0)

    def world(p):
        q = _rx(p, xrot)
        q = (q[0] + pivot[0], q[1] + pivot[1], q[2] + pivot[2])
        return (q[0] * K, top - q[1] * K, -q[2] * K)

    def wn(n):
        q = _rx(n, xrot)
        return (q[0], -q[1], -q[2])

    out = []
    for (fname, p00, p10, p01, uv) in _box_faces(lo, hi, u, v, size, mirror):
        n = _MN[fname]
        if mirror and fname in ('west', 'east'):
            n = (-n[0], n[1], n[2])
        out.append(render.Quad(world(p00), world(p10), world(p01), wn(n), tex, uv, True))
    return out


def mannequin_quads(hum, leg, crouch):
    parts = _parts(crouch)
    skin = _base_skin()
    quads = []
    for name in parts:
        quads += _part_quads(parts, name, skin, SKIN_UV, 0.0, crouch)
    if leg is not None:
        for name in ('body', 'right_leg', 'left_leg'):
            quads += _part_quads(parts, name, leg, ARMOR_UV, 0.5, crouch)
    if hum is not None:
        for name in ('body', 'right_arm', 'left_arm', 'right_leg', 'left_leg'):
            quads += _part_quads(parts, name, hum, ARMOR_UV, 1.0, crouch)
    return quads


# ───────────────────────────── pieces with the plugin transforms ─────────────────────────────

def piece_quads(piece, row, pixel, stance):
    """ItemDisplay riding the figure (yaw 0 = facing +Z): world = seat + T + Rx(pitch)·S·R180y·((m − 8)/16)."""
    x, y, z, pitch = row
    seat = AP.seat_height(stance)

    def world(m):
        q = (-(m[0] - 8) / 16 * pixel, (m[1] - 8) / 16 * pixel, -(m[2] - 8) / 16 * pixel)
        q = _rx(q, pitch)
        return (q[0] + x, q[1] + y + seat, q[2] + z)

    def wn(n):
        return _rx((-n[0], n[1], -n[2]), pitch)

    return render.element_quads(piece.model, piece.faces_uv, piece.frame, world, wn)


# ───────────────────────────── sets & sheets ─────────────────────────────

def load_sets():
    """Same set → (kind, look, theme, level) mapping as the pack build (armor_pieces.set_specs)."""
    with open(os.path.join(CONTENT, 'items.yml'), encoding='utf-8') as f:
        doc = yaml.safe_load(f)
    return AP.set_specs(doc.get('items') or {}, doc.get('sets') or {})


# (label, yaw, pitch, zoom, centre height offset) — zoomed columns frame the shoulders
VIEWS = (('front', 0, 6, 1.0, 0.0), ('left side', -90, 6, 1.0, 0.0), ('back', 180, 6, 1.0, 0.0),
         ('3/4 back', 145, 14, 1.0, 0.0), ('close-up 3/4 front', 32, 16, 1.75, 0.34), ('close-up 3/4 back', 212, 16, 1.75, 0.34))
BG = (104, 108, 120, 255)


def _label(img, text, xy, fill=(230, 230, 235)):
    ImageDraw.Draw(img).text(xy, text, fill=fill)


def set_sheet(sid, info, layout, cell=(230, 300), scale=128.0):
    hum, leg = equipment.paint_set(info['look'], info['kind'], stable_seed('set', sid))
    pieces = {part: AP.build_part(sid, part, info['kind'], info['look'], info['theme'], info['level'])
              for part in AP.PARTS}
    rows = [('BEFORE (equipment layer only)', 'STAND', False), ('AFTER standing', 'STAND', True),
            ('AFTER sneaking', 'SNEAK', True)]
    W, H = cell
    head = 34
    sheet = Image.new('RGBA', (W * len(VIEWS) + 150, head + H * len(rows)), (52, 54, 62, 255))
    els = ' / '.join(f'{p} {pieces[p].elements}el' for p in AP.PARTS)
    _label(sheet, f'{sid} - look {info["kind"]}, theme {info["theme"]}, lv {info["level"]} - {els}', (6, 4))
    _label(sheet, 'transforms = ArmorPieceLayout.java @layout-table (seat 1.8 / 1.5, pixel %.4f)' % layout['pixel'],
           (6, 18), (170, 175, 190))
    for r, (title, stance, with_pieces) in enumerate(rows):
        crouch = stance == 'SNEAK'
        base = mannequin_quads(hum, leg, crouch)
        extra = []
        if with_pieces:
            for part in AP.PARTS:
                extra += piece_quads(pieces[part], layout['rows'][(part, stance)], layout['pixel'], stance)
        for c, (vname, yaw, pitch, zoom, dy) in enumerate(VIEWS):
            cy = (0.92 if not crouch else 0.8) + dy * (0.93 if crouch else 1.0)
            img = render.render_scene(base + extra, yaw=yaw, pitch=pitch, size=(W, H), scale=scale * zoom,
                                      center=(0, cy, 0 if zoom == 1.0 else (-0.05 if crouch else 0)), bg=BG)
            sheet.alpha_composite(img, (150 + c * W, head + r * H))
            if r == 0:
                _label(sheet, vname, (150 + c * W + 6, head + 4), (200, 205, 215))
        _label(sheet, title, (6, head + r * H + H // 2 - 6))
    return sheet.convert('RGB'), pieces


def overview(sets, layout, cell=(170, 230), scale=100.0):
    ids = list(sets)
    cols = 5
    W, H = cell
    rows = (len(ids) + cols - 1) // cols
    sheet = Image.new('RGBA', (cols * W * 2, rows * (H + 14) + 20), (52, 54, 62, 255))
    _label(sheet, f'All {len(ids)} armour sets with 3D shoulder/back pieces (front 3/4 and back 3/4, standing)', (6, 4))
    for n, sid in enumerate(ids):
        info = sets[sid]
        hum, leg = equipment.paint_set(info['look'], info['kind'], stable_seed('set', sid))
        q = mannequin_quads(hum, leg, False)
        for part in AP.PARTS:
            pc = AP.build_part(sid, part, info['kind'], info['look'], info['theme'], info['level'])
            q += piece_quads(pc, layout['rows'][(part, 'STAND')], layout['pixel'], 'STAND')
        x0, y0 = (n % cols) * W * 2, 20 + (n // cols) * (H + 14)
        for k, yaw in enumerate((35, 150)):
            img = render.render_scene(q, yaw=yaw, pitch=12, size=(W, H), scale=scale, center=(0, 0.95, 0),
                                      bg=BG if (n + k) % 2 == 0 else (96, 100, 112, 255))
            sheet.alpha_composite(img, (x0 + k * W, y0))
        _label(sheet, f'{sid} [{info["kind"]}]', (x0 + 4, y0 + H))
    return sheet.convert('RGB')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(HERE, 'dist', 'armor_preview'))
    ap.add_argument('--sets', default='emberforged,wayfarer,silkweaver')
    ap.add_argument('--overview', action='store_true')
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    with open(JAVA, encoding='utf-8') as f:
        layout = AP.read_java_layout(f.read())
    sets = load_sets()
    for sid in [s.strip() for s in args.sets.split(',') if s.strip()]:
        if sid not in sets:
            print('unknown set', sid)
            return 2
        sheet, pieces = set_sheet(sid, sets[sid], layout)
        path = os.path.join(args.out, f'pieces_{sets[sid]["kind"]}_{sid}.png')
        sheet.save(path)
        print(path, ' '.join(f'{p}={pieces[p].elements}' for p in AP.PARTS))
    if args.overview:
        path = os.path.join(args.out, 'pieces_all_sets.png')
        overview(sets, layout).save(path)
        print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
