"""Tiny software renderer for previews: orthographic, z-buffered, nearest-neighbour textured
cuboids, using the exact Minecraft display-transform math (so the preview shows what the GUI
slot will show)."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .model import NORMALS, display_apply, rot_axis, rot_xyz

_L0 = (0.2, 1.0, -0.7)
_L1 = (-0.2, 1.0, 0.7)


def _norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / l for c in v)


L0, L1 = _norm(_L0), _norm(_L1)


def render(model, faces_uv, atlas: Image.Image, transform: dict, ppu: int = 8, units: int = 16,
           bg=(0, 0, 0, 0), solids=()) -> Image.Image:
    """solids: extra flat-coloured boxes [(from, to, rgb)] drawn in the same z-buffer (e.g. a stand-in head)."""
    from .model import El
    W = H = units * ppu
    img = Image.new('RGBA', (W, H), bg)
    out = img.load()
    zbuf = [[-1e9] * W for _ in range(H)]
    tex = atlas.load()
    S = atlas.size[0]
    half = units / 2
    rot = transform.get('rotation', [0, 0, 0])
    items = [(idx, e, None) for idx, e in enumerate(model.els)]
    for k, (frm, to, rgb) in enumerate(solids):
        items.append((-1 - k, El(tuple(frm), tuple(to), 'solid'), rgb))
    for idx, e, solid in items:
        for f in e.faces:
            if solid is None and (idx, f) not in faces_uv:
                continue
            n = NORMALS[f]
            if e.rot:
                ax, ang, _ = e.rot
                n = rot_axis(n, ax, ang, (0, 0, 0))
            n = rot_xyz(n, rot)
            if n[2] <= 1e-6:
                continue
            p00 = e.texel_pos(f, 0, 0)
            p10 = e.texel_pos(f, 1, 0)
            p01 = e.texel_pos(f, 0, 1)
            pts = []
            for p in (p00, p10, p01):
                if e.rot:
                    ax, ang, org = e.rot
                    p = rot_axis(p, ax, ang, org)
                q = display_apply(p, transform)
                pts.append(((q[0] + half) * ppu, (half - q[1]) * ppu, q[2]))
            (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts
            ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
            vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
            det = ux * vy - uy * vx
            if abs(det) < 1e-9:
                continue
            if e.shade:
                b = 0.4 + 0.6 * (max(0.0, n[0] * L0[0] + n[1] * L0[1] + n[2] * L0[2]) +
                                 max(0.0, n[0] * L1[0] + n[1] * L1[1] + n[2] * L1[2]))
                b = min(1.0, b)
            else:
                b = 1.0
            u0, v0, u1, v1 = faces_uv[(idx, f)] if solid is None else (0, 0, 1, 1)
            fw, fh = u1 - u0, v1 - v0
            xs = [x0, x1, x2, x1 + vx]
            ys = [y0, y1, y2, y1 + vy]
            bx0, bx1 = max(0, int(math.floor(min(xs)))), min(W - 1, int(math.ceil(max(xs))))
            by0, by1 = max(0, int(math.floor(min(ys)))), min(H - 1, int(math.ceil(max(ys))))
            inv = 1.0 / det
            for py in range(by0, by1 + 1):
                cy = py + 0.5 - y0
                zrow = zbuf[py]
                for px in range(bx0, bx1 + 1):
                    cx = px + 0.5 - x0
                    s = (cx * vy - cy * vx) * inv
                    if s < 0 or s >= 1:
                        continue
                    t = (ux * cy - uy * cx) * inv
                    if t < 0 or t >= 1:
                        continue
                    z = z0 + s * uz + t * vz
                    if z <= zrow[px]:
                        continue
                    tx = u0 + min(fw - 1, int(s * fw))
                    ty = v0 + min(fh - 1, int(t * fh))
                    if solid is not None:
                        c = (solid[0], solid[1], solid[2], 255)
                        if (int(s * 8) + int(t * 8)) % 2 == 0:
                            c = (int(c[0] * 0.92), int(c[1] * 0.92), int(c[2] * 0.92), 255)
                    else:
                        c = tex[tx, ty % S] if ty < atlas.size[1] else (0, 0, 0, 0)
                    if c[3] < 8:
                        continue
                    zrow[px] = z
                    out[px, py] = (int(c[0] * b), int(c[1] * b), int(c[2] * b), 255)
    return img


def grid(cells, cols, cell_px, label_h=12, bg=(58, 60, 70), title=None):
    """cells: list of (image, label).  Returns one sheet image."""
    rows = (len(cells) + cols - 1) // cols
    top = 18 if title else 0
    sheet = Image.new('RGBA', (cols * cell_px, rows * (cell_px + label_h) + top), bg + (255,))
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((4, 3), title, fill=(235, 235, 235, 255))
    for k, (im, label) in enumerate(cells):
        cx, cy = (k % cols) * cell_px, (k // cols) * (cell_px + label_h) + top
        shade = (70, 72, 84, 255) if ((k % cols) + (k // cols)) % 2 == 0 else (64, 66, 77, 255)
        d.rectangle([cx, cy, cx + cell_px - 1, cy + cell_px - 1], fill=shade)
        if im.size[0] != cell_px:
            im = im.resize((cell_px, cell_px), Image.NEAREST)
        sheet.alpha_composite(im, (cx, cy))
        d.text((cx + 2, cy + cell_px), label[: max(4, cell_px // 6)], fill=(210, 210, 215, 255))
    return sheet
