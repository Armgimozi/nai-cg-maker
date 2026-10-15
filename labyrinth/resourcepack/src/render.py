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


# ───────────────────────────── world-space scene (armour preview mannequin) ─────────────────────────────

class Quad:
    """One textured parallelogram in world space (blocks): texel (u0, v0) at p00, u grows toward p10, v toward p01.
    tex: PIL image (or None → flat `color`), uv: (u0, v0, u1, v1) in texels, normal: outward unit normal."""
    __slots__ = ('p00', 'p10', 'p01', 'normal', 'tex', 'uv', 'shade', 'color')

    def __init__(self, p00, p10, p01, normal, tex=None, uv=(0, 0, 1, 1), shade=True, color=(160, 160, 160)):
        self.p00, self.p10, self.p01, self.normal = p00, p10, p01, normal
        self.tex, self.uv, self.shade, self.color = tex, uv, shade, color


def _view(p, center, yaw, pitch):
    q = (p[0] - center[0], p[1] - center[1], p[2] - center[2])
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    q = (q[0] * c + q[2] * s, q[1], -q[0] * s + q[2] * c)
    c, s = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    return (q[0], q[1] * c - q[2] * s, q[1] * s + q[2] * c)


def render_scene(quads, yaw=0.0, pitch=0.0, size=(256, 320), scale=120.0, center=(0, 0.95, 0), bg=(0, 0, 0, 0)):
    """Orthographic z-buffered render of world quads.  yaw 0 = camera in front of a +Z-facing figure (its left on
    the right of the image), 180 = from behind, −90 = from the figure's left side; pitch > 0 = camera above.
    scale = pixels per block.  Lighting = Minecraft's two fixed world lights (entity shading)."""
    W, H = size
    img = Image.new('RGBA', (W, H), bg)
    out = img.load()
    zbuf = [[-1e9] * W for _ in range(H)]
    for q in quads:
        nv = _view((q.normal[0], q.normal[1], q.normal[2]), (0, 0, 0), yaw, pitch)
        if nv[2] <= 1e-6:
            continue                                   # back-face culling (as the game does)
        pts = []
        for p in (q.p00, q.p10, q.p01):
            v = _view(p, center, yaw, pitch)
            pts.append((W / 2 + v[0] * scale, H / 2 - v[1] * scale, v[2]))
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts
        ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
        vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
        det = ux * vy - uy * vx
        if abs(det) < 1e-9:
            continue
        n = q.normal
        if q.shade:
            b = 0.4 + 0.6 * (max(0.0, n[0] * L0[0] + n[1] * L0[1] + n[2] * L0[2]) +
                             max(0.0, n[0] * L1[0] + n[1] * L1[1] + n[2] * L1[2]))
            b = min(1.0, b)
        else:
            b = 1.0
        u0, v0, u1, v1 = q.uv
        fw, fh = u1 - u0, v1 - v0
        tex = q.tex.load() if q.tex is not None else None
        tw, th = (q.tex.size if q.tex is not None else (1, 1))
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
                if tex is not None:
                    tx = int(math.floor(u0 + s * fw))
                    ty = int(math.floor(v0 + t * fh))
                    if fw < 0:
                        tx = int(math.ceil(u0 + s * fw)) - 1
                    if not (0 <= tx < tw and 0 <= ty < th):
                        continue
                    c = tex[tx, ty]
                    if len(c) < 4:
                        c = (c[0], c[1], c[2], 255)
                else:
                    c = q.color + (255,)
                if c[3] < 8:
                    continue
                zrow[px] = z
                out[px, py] = (int(c[0] * b), int(c[1] * b), int(c[2] * b), 255)
    return img


def element_quads(model, faces_uv, atlas, world_fn, normal_fn):
    """Quads of a baked model's elements; world_fn(model point) → world point, normal_fn(model normal) → world."""
    quads = []
    for idx, e in enumerate(model.els):
        for f in e.faces:
            if (idx, f) not in faces_uv:
                continue
            ps = []
            for (a, b_) in ((0, 0), (1, 0), (0, 1)):
                p = e.texel_pos(f, a, b_)
                if e.rot:
                    ax, ang, org = e.rot
                    p = rot_axis(p, ax, ang, org)
                ps.append(world_fn(p))
            n = NORMALS[f]
            if e.rot:
                n = rot_axis(n, e.rot[0], e.rot[1], (0, 0, 0))
            x0, y0, x1, y1 = faces_uv[(idx, f)]
            quads.append(Quad(ps[0], ps[1], ps[2], normal_fn(n), atlas, (x0, y0, x1, y1), e.shade))
    return quads
