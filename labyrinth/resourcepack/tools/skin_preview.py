#!/usr/bin/env python3
"""NPC skin preview — renders the 64×64 player-layout NPC skins (src/npc_skins.py) on the player model.

    python tools/skin_preview.py --out DIR [--tag after] [--skins guide,blacksmith] [--png-dir DIR] [--jobs N]

For every npcs.yml skin it writes `<tag>_<skin>.png`, a sheet with
  row 1: orthographic front · back · right side · left side (8 px per skin pixel, true colours, no lighting)
  row 2: in-game-like 3/4 front and 3/4 back (entity lighting = Minecraft's two fixed lights), a head
         close-up (16 px per skin pixel), the "distance check" (front + 3/4 at 2 px per skin pixel), and the
         raw 64×64 texture at 4×
and `<tag>_overview.png` with every skin side by side (3/4 front at 6 px per skin pixel + front at 2 px).

Model = the vanilla player model with classic (4 px) arms, standing, facing +Z: head 8³ at y 24..32, body
8×12×4, arms 4×12×4 at x ±(4..8), legs 4×12×4.  The outer layer (hat / jacket / sleeves / pants) is the same
box inflated by 0.5 px (head) or 0.25 px (the rest) and drawn without back-face culling, like the client's
translucent entity render type, so the inside of a hat brim shows through its holes.  UV mapping = the
standard skin layout (vanilla ModelPart.Cube): top/bottom rows run back → front, side strips wrap
right · front · left · back.

--png-dir DIR   read DIR/<skin>.png (e.g. an unzipped pack's assets/labyrinth/textures/entity/npc) instead of
                painting the skins with the current src/npc_skins.py.
--styles        also write `<tag>_styles.png`: every closed-list hair style (head from three sides) and outfit
                (GDD §14.5) on one neutral palette, and every accessory on a plain traveller (front + back), to check
                that each value is drawn and distinct.
--compare TAG   also write `compare_overview.png`: the overview of an earlier run (`<TAG>_overview.png` in --out,
                e.g. before) stacked above this run's overview.
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import yaml
from PIL import Image, ImageDraw, ImageFont

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PACK)

from src.render import Quad, render_scene  # noqa: E402

NPCS = os.path.join(PACK, '..', 'plugin', 'src', 'main', 'resources', 'content', 'npcs.yml')
BG = (92, 96, 104)            # neutral grey background
BG2 = (74, 77, 84)
INK = (236, 236, 240)

# part: (base uv, outer uv, w, h, d, model origin (min corner, px), outer inflation px)
PARTS = {
    'head': ((0, 0), (32, 0), 8, 8, 8, (-4, 24, -4), 0.5),
    'body': ((16, 16), (16, 32), 8, 12, 4, (-4, 12, -2), 0.25),
    'rarm': ((40, 16), (40, 32), 4, 12, 4, (-8, 12, -2), 0.25),
    'larm': ((32, 48), (48, 48), 4, 12, 4, (4, 12, -2), 0.25),
    'rleg': ((0, 16), (0, 32), 4, 12, 4, (-4, 0, -2), 0.25),
    'lleg': ((16, 48), (0, 48), 4, 12, 4, (0, 0, -2), 0.25),
}


def box_quads(tex, uv, w, h, d, origin, grow=0.0, shade=True, two_sided=False, only=None):
    """The six textured faces of one skin box (world blocks, 1 block = 16 px)."""
    u, v = uv
    x0, y0, z0 = (origin[0] - grow, origin[1] - grow, origin[2] - grow)
    x1, y1, z1 = (origin[0] + w + grow, origin[1] + h + grow, origin[2] + d + grow)
    s = 1 / 16.0
    P = lambda x, y, z: (x * s, y * s, z * s)  # noqa: E731
    faces = {
        'front': (P(x0, y1, z1), P(x1, y1, z1), P(x0, y0, z1), (0, 0, 1), (u + d, v + d, u + d + w, v + d + h)),
        'back': (P(x1, y1, z0), P(x0, y1, z0), P(x1, y0, z0), (0, 0, -1), (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h)),
        'right': (P(x0, y1, z0), P(x0, y1, z1), P(x0, y0, z0), (-1, 0, 0), (u, v + d, u + d, v + d + h)),
        'left': (P(x1, y1, z1), P(x1, y1, z0), P(x1, y0, z1), (1, 0, 0), (u + d + w, v + d, u + 2 * d + w, v + d + h)),
        'top': (P(x0, y1, z0), P(x1, y1, z0), P(x0, y1, z1), (0, 1, 0), (u + d, v, u + d + w, v + d)),
        'bottom': (P(x0, y0, z0), P(x1, y0, z0), P(x0, y0, z1), (0, -1, 0), (u + d + w, v, u + d + 2 * w, v + d)),
    }
    out = []
    for name, (p00, p10, p01, n, r) in faces.items():
        if only and name not in only:
            continue
        out.append(Quad(p00, p10, p01, n, tex, r, shade))
        if two_sided:
            out.append(Quad(p00, p10, p01, (-n[0], -n[1], -n[2]), tex, r, shade))
    return out


def figure_quads(skin, shade=True, parts=None, outer=True):
    tex = skin.convert('RGBA')
    qs = []
    for name, (buv, ouv, w, h, d, org, grow) in PARTS.items():
        if parts and name not in parts:
            continue
        qs += box_quads(tex, buv, w, h, d, org, 0.0, shade)
        if outer:
            qs += box_quads(tex, ouv, w, h, d, org, grow, shade, two_sided=True)
    return qs


def view(skin, yaw, pitch, ppx, shade, parts=None, center=None, size=None):
    """ppx = screen pixels per skin pixel."""
    scale = 16.0 * ppx
    if parts == ('head',):
        center = center or (0, 28.0 / 16, 0)
        size = size or (int(13 * ppx), int(13 * ppx))
    center = center or (0, 16.25 / 16, 0)
    size = size or (int(23 * ppx), int(35 * ppx))
    return render_scene(figure_quads(skin, shade, parts), yaw, pitch, size, scale, center, BG + (255,))


def _font(px):
    for p in ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(p, px)
        except OSError:
            continue
    return ImageFont.load_default()


def _caption(img, text, px=14):
    out = Image.new('RGBA', (img.size[0], img.size[1] + px + 8), BG2 + (255,))
    out.alpha_composite(img, (0, 0))
    ImageDraw.Draw(out).text((4, img.size[1] + 3), text, fill=INK + (255,), font=_font(px))
    return out


def _row(images, gap=10, bg=BG2):
    W = sum(i.size[0] for i in images) + gap * (len(images) + 1)
    H = max(i.size[1] for i in images) + 2 * gap
    out = Image.new('RGBA', (W, H), bg + (255,))
    x = gap
    for i in images:
        out.alpha_composite(i, (x, gap + (H - 2 * gap - i.size[1]) // 2 if i.size[1] < H - 2 * gap else gap))
        x += i.size[0] + gap
    return out


def _stack(rows, title, gap=6, bg=BG2):
    head = 30 if title else 0
    W = max(r.size[0] for r in rows)
    H = sum(r.size[1] for r in rows) + gap * (len(rows) - 1) + head
    out = Image.new('RGBA', (W, H), bg + (255,))
    if title:
        ImageDraw.Draw(out).text((10, 6), title, fill=INK + (255,), font=_font(18))
    y = head
    for r in rows:
        out.alpha_composite(r, (0, y))
        y += r.size[1] + gap
    return out


def sheet(sid, label, skin):
    p = 8
    row1 = [_caption(view(skin, 0, 0, p, False), 'front'), _caption(view(skin, 180, 0, p, False), 'back'),
            _caption(view(skin, 90, 0, p, False), 'right side'), _caption(view(skin, -90, 0, p, False), 'left side')]
    small = _row([view(skin, 0, 0, 2, True), view(skin, 30, 8, 2, True), view(skin, 0, 0, 1, True)], gap=6, bg=BG)
    tex = Image.new('RGBA', (256, 256), BG + (255,))
    tex.alpha_composite(skin.convert('RGBA').resize((256, 256), Image.NEAREST))
    row2 = [_caption(view(skin, 32, 10, p, True), '3/4 front (lit)'), _caption(view(skin, 212, 10, p, True), '3/4 back (lit)'),
            _caption(_row([view(skin, 0, 0, 16, True, ('head',)), view(skin, 35, 8, 16, True, ('head',))], gap=6, bg=BG),
                     'head 16x (front, 3/4)'),
            _caption(small, 'distance check 2x / 1x'), _caption(tex, '64x64 texture')]
    return _stack([_row(row1), _row(row2)], f'{label}  ({sid})')


def overview(items, tag):
    cells = []
    for sid, label, skin in items:
        a = view(skin, 30, 8, 6, True)
        b = view(skin, 0, 0, 2, True)
        c = Image.new('RGBA', (a.size[0], a.size[1] + b.size[1] + 6), BG + (255,))
        c.alpha_composite(a, (0, 0))
        c.alpha_composite(b, ((a.size[0] - b.size[0]) // 2, a.size[1] + 6))
        cells.append(_caption(c, label.split(' ')[-1] + ' · ' + sid, 12))
    per = (len(cells) + 1) // 2
    rows = [_row(cells[:per]), _row(cells[per:])]
    return _stack(rows, f'{tag}: NPC skins ({len(items)}) — 3/4 front 6x + front 2x')


STYLE_PALETTE = ['#e8c0a0', '#5a3a22', '#4a5a7a', '#c8b48a', '#c8a060', '#3a7a5a']


def styles_sheet(tag):
    from src import npc_skins as N
    rows = []
    hair = []
    for h in N.HAIRS:
        sk = N.paint_skin('style_' + h, {'palette': STYLE_PALETTE, 'outfit': 'traveler', 'hair': h})[0]
        hair.append(_caption(_row([view(sk, yaw, 10, 10, True, ('head',)) for yaw in (30, 110, 200)], gap=2, bg=BG), h, 12))
    outfit = [_caption(view(N.paint_skin('style_' + o, {'palette': STYLE_PALETTE, 'outfit': o, 'hair': 'short_bob'})[0],
                            30, 8, 4, True), o, 12) for o in N.OUTFITS]
    acc = []
    for a in N.ACCESSORIES:
        sk = N.paint_skin('style_' + a, {'palette': STYLE_PALETTE, 'outfit': 'traveler', 'hair': 'messy_short',
                                         'accessories': [a]})[0]
        acc.append(_caption(_row([view(sk, 30, 8, 3, True), view(sk, 210, 8, 3, True)], gap=2, bg=BG), a, 12))
    for chunk in (hair[:4], hair[4:8], hair[8:], outfit):
        rows.append(_row(chunk))
    for i in range(0, len(acc), 6):
        rows.append(_row(acc[i:i + 6]))
    return _stack(rows, f'{tag}: closed lists — hair (12: head 3/4 front, side, 3/4 back), outfit (8), accessories (30: 3/4 front + back)')


def load_npcs(path):
    with open(path, encoding='utf-8') as f:
        doc = yaml.safe_load(f) or {}
    seen, out = set(), []
    for nid, d in (doc.get('npcs') or {}).items():
        d = d or {}
        sid = d.get('skin') or nid
        if sid in seen:
            continue
        seen.add(sid)
        out.append((sid, d.get('name') or nid, d.get('skin_style'), d.get('role')))
    return out


def _work(args):
    sid, label, style, role, png_dir, out, tag = args
    if png_dir:
        skin = Image.open(os.path.join(png_dir, f'{sid}.png')).convert('RGBA')
    else:
        from src import npc_skins
        skin, warns = npc_skins.paint_skin(sid, style, role)
        for w in warns:
            print('warning:', w)
    sheet(sid, label, skin).convert('RGB').save(os.path.join(out, f'{tag}_{sid}.png'))
    buf = skin.copy()
    return sid, label, buf.tobytes()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True)
    ap.add_argument('--tag', default='after')
    ap.add_argument('--skins', default='')
    ap.add_argument('--png-dir', default='')
    ap.add_argument('--npcs', default=NPCS)
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--compare', default='')
    ap.add_argument('--styles', action='store_true')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    want = {s for s in a.skins.split(',') if s}
    todo = [(sid, label, style, role, a.png_dir, a.out, a.tag) for (sid, label, style, role) in load_npcs(a.npcs)
            if not want or sid in want]
    with ProcessPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        done = list(ex.map(_work, todo))
    items = [(sid, label, Image.frombytes('RGBA', (64, 64), raw)) for (sid, label, raw) in done]
    if not want:
        ov = overview(items, a.tag)
        ov.convert('RGB').save(os.path.join(a.out, f'{a.tag}_overview.png'))
        old = os.path.join(a.out, f'{a.compare}_overview.png')
        if a.compare and os.path.exists(old):
            prev = Image.open(old).convert('RGBA')
            out = Image.new('RGBA', (max(prev.size[0], ov.size[0]), prev.size[1] + ov.size[1] + 8), BG2 + (255,))
            out.alpha_composite(prev, (0, 0))
            out.alpha_composite(ov, (0, prev.size[1] + 8))
            out.convert('RGB').save(os.path.join(a.out, 'compare_overview.png'))
            print(os.path.join(a.out, 'compare_overview.png'))
    if a.styles:
        styles_sheet(a.tag).convert('RGB').save(os.path.join(a.out, f'{a.tag}_styles.png'))
        print(os.path.join(a.out, f'{a.tag}_styles.png'))
    for sid, _, _ in items:
        print(os.path.join(a.out, f'{a.tag}_{sid}.png'))
    if not want:
        print(os.path.join(a.out, f'{a.tag}_overview.png'))


if __name__ == '__main__':
    main()
