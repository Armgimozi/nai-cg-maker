#!/usr/bin/env python3
"""Offline mob-rig animation preview: draws what the server rig shows, frame by frame, without a Minecraft server.

Pipeline
  1. Java dump (RigMath / BossRig math, exactly as the plugin computes it) → JSON of per-part Display Transformations:
       cd labyrinth/plugin && RIG_DUMP=/tmp/rig.json RIG_MOBS=a,b ./gradlew test --tests kr.labyrinth.mobs.RigPreviewDump --rerun -q
  2. this script: the generated part models (mobs.build_mob in-process, or an existing pack zip with --pack) are placed
     with those transforms — model px → (p − 8)·fixed.scale/16 → ItemDisplay 180° Y turn → left rotation · scale + translation —
     and rasterised (orthographic, z-buffer, nearest texels, two soft lights) into one sprite sheet per mob:
       walk full speed (side / three-quarter / front) · walk half speed (side) · foot-trace chart ·
       idle + attack · hurt + death (· boss slam overlay)
     ground line = y 0 (3/4 view: a 0.5-block floor grid) with markers scrolling backwards at the walk speed
     (a planted foot should move with them),
     dots = part joints = rotation centres (red legs, cyan arms, yellow head/neck/tail, white other).
     Foot-trace chart: every foot (lowest vertices of a leg part, split per leg when one part holds several legs) is
     tracked over the walk cycle — forward offset z and height y (0 = floor, below 0 = sinking through it) — plus
     numbers: stride, lift, sinking, slip (planted-foot speed mismatch) and the left/right phase correlation.
     Optional animated GIF of the walk cycle (--gif).

     /opt/packvenv/bin/python labyrinth/tools/rig_preview.py --dump /tmp/rig.json --out /tmp/rig_preview --prefix before

Only reads content / pack files; writes PNGs (and GIFs) into --out.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import zipfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
PACK_SRC = os.path.join(LAB, 'resourcepack')
CONTENT = os.path.join(LAB, 'plugin', 'src', 'main', 'resources', 'content')
NS = 'labyrinth'

FACE_N = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0), 'west': (-1, 0, 0), 'up': (0, 1, 0),
          'down': (0, -1, 0)}

# views: (yaw° of the camera from the mob's front toward its left (+X), pitch°)
VIEWS = {'side': (-90.0, 0.0), 'q34': (-38.0, 18.0), 'front': (0.0, 6.0)}

LIGHTS = [np.array(v) / np.linalg.norm(v) for v in ((0.35, 1.0, 0.7), (-0.4, 0.8, -0.6))]

BG = (64, 66, 78)
CELL_BG = ((72, 74, 87), (66, 68, 80))
LEG_FORMS = {'leg_pair': 2, 'leg_quad': 4, 'leg_six': 6, 'leg_eight': 8}


def _font(size):
    for path in ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/opentype/unifont/unifont.otf'):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


# ───────────────────────────── models ─────────────────────────────

def _texel_pos(frm, to, face, a, b):
    (x1, y1, z1), (x2, y2, z2) = frm, to
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    if face == 'north':
        return (x2 - a * dx, y2 - b * dy, z1)
    if face == 'south':
        return (x1 + a * dx, y2 - b * dy, z2)
    if face == 'east':
        return (x2, y2 - b * dy, z2 - a * dz)
    if face == 'west':
        return (x1, y2 - b * dy, z1 + a * dz)
    if face == 'up':
        return (x1 + a * dx, y2, z1 + b * dz)
    return (x1 + a * dx, y1, z2 - b * dz)


def _rot_axis(p, axis, deg, org):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y, z = p[0] - org[0], p[1] - org[1], p[2] - org[2]
    if axis == 'x':
        y, z = y * c - z * s, y * s + z * c
    elif axis == 'y':
        x, z = x * c + z * s, -x * s + z * c
    else:
        x, y = x * c - y * s, x * s + y * c
    return (x + org[0], y + org[1], z + org[2])


class PartGeo:
    """Faces of one part model in part-local blocks (after display.fixed scale and the ItemDisplay 180° turn)."""

    def __init__(self, mj, atlas: Image.Image):
        S = atlas.size[0]
        k = float(((mj.get('display') or {}).get('fixed') or {}).get('scale', [1, 1, 1])[0])
        P0, PU, PV, N, UV, SH = [], [], [], [], [], []
        for e in mj.get('elements') or []:
            frm, to = e['from'], e['to']
            rot = e.get('rotation')
            for face, fd in (e.get('faces') or {}).items():
                pts = [_texel_pos(frm, to, face, a, b) for a, b in ((0, 0), (1, 0), (0, 1))]
                n = FACE_N[face]
                if rot:
                    pts = [_rot_axis(p, rot['axis'], rot['angle'], rot['origin']) for p in pts]
                    n = _rot_axis(n, rot['axis'], rot['angle'], (0, 0, 0))
                # model px → blocks about the pivot (8,8,8), display.fixed scale, ItemDisplay 180° about Y
                q = [((8 - p[0]) * k / 16.0, (p[1] - 8) * k / 16.0, (8 - p[2]) * k / 16.0) for p in pts]
                P0.append(q[0])
                PU.append((q[1][0] - q[0][0], q[1][1] - q[0][1], q[1][2] - q[0][2]))
                PV.append((q[2][0] - q[0][0], q[2][1] - q[0][1], q[2][2] - q[0][2]))
                N.append((-n[0], n[1], -n[2]))
                u0, v0, u1, v1 = fd['uv']
                UV.append((u0 * S / 16.0, v0 * S / 16.0, u1 * S / 16.0, v1 * S / 16.0))
                SH.append(0.0 if e.get('shade') is False else 1.0)
        self.p0 = np.array(P0, dtype=np.float64).reshape(-1, 3)
        self.pu = np.array(PU, dtype=np.float64).reshape(-1, 3)
        self.pv = np.array(PV, dtype=np.float64).reshape(-1, 3)
        self.n = np.array(N, dtype=np.float64).reshape(-1, 3)
        self.uv = np.array(UV, dtype=np.float64).reshape(-1, 4)
        self.shade = np.array(SH, dtype=np.float64)

    def corners(self):
        """All face corners (part-local blocks) → (4F, 3)."""
        return np.concatenate([self.p0, self.p0 + self.pu, self.p0 + self.pv, self.p0 + self.pu + self.pv])


def quat_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def place(pts, t):
    """Part-local points → mob-local world blocks with one part transform t = [tx,ty,tz,qx,qy,qz,qw,s]."""
    return pts @ (quat_mat(t[3:7]) * t[7]).T + np.array(t[0:3])


def load_models(mid, boss, pack_zip=None, content=None):
    """→ ({part name: model json}, atlas frame 0 RGBA)."""
    if pack_zip:
        with zipfile.ZipFile(pack_zip) as z:
            names = set(z.namelist())
            pre = f'assets/{NS}/models/mob/{mid}/'
            models = {n[len(pre):-5]: json.loads(z.read(n)) for n in names if n.startswith(pre) and n.endswith('.json')}
            tex = Image.open(io.BytesIO(z.read(f'assets/{NS}/textures/mob/{mid}.png'))).convert('RGBA')
    else:
        sys.path.insert(0, PACK_SRC)
        from src import items, mobs  # noqa: E402
        coll = content['bosses' if boss else 'mobs']
        res = mobs.build_mob(mid, coll[mid], boss, items.jdump, items.png_bytes, items.strip)
        pre = f'assets/{NS}/models/mob/{mid}/'
        models = {p[len(pre):-5]: json.loads(b) for p, b in res.files.items() if p.startswith(pre)}
        tex = Image.open(io.BytesIO(res.files[f'assets/{NS}/textures/mob/{mid}.png'])).convert('RGBA')
    S = tex.size[0]
    return models, tex.crop((0, 0, S, S))


# ───────────────────────────── raster ─────────────────────────────

def view_basis(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    back = np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])
    right = np.cross(np.array([0.0, 1.0, 0.0]), back)
    right /= np.linalg.norm(right)
    up = np.cross(back, right)
    return right, up, back


def world_faces(geos, frame):
    """All faces of every part placed with this frame's transforms → (P0, PU, PV, N, UV, SH) world blocks."""
    out = [[], [], [], [], [], []]
    for geo, t in zip(geos, frame):
        if geo is None or not len(geo.p0):
            continue
        R = quat_mat(t[3:7]) * t[7]
        Rn = quat_mat(t[3:7])
        tr = np.array(t[0:3])
        out[0].append(geo.p0 @ R.T + tr)
        out[1].append(geo.pu @ R.T)
        out[2].append(geo.pv @ R.T)
        out[3].append(geo.n @ Rn.T)
        out[4].append(geo.uv)
        out[5].append(geo.shade)
    if not out[0]:
        z = np.zeros((0, 3))
        return z, z, z, z, np.zeros((0, 4)), np.zeros(0)
    return tuple(np.concatenate(a) for a in out)


def raster(faces, tex, basis, center, ppb, W, H):
    """Orthographic z-buffered textured parallelograms → RGBA image W×H.  ppb = pixels per block."""
    P0, PU, PV, N, UV, SH = faces
    right, up, back = basis
    img = np.zeros((H, W, 4), dtype=np.uint8)
    zbuf = np.full((H, W), -1e9)
    if not len(P0):
        return img
    vis = N @ back > 1e-6
    b = 0.42 + 0.58 * np.clip(sum(np.clip(N @ L, 0, None) for L in LIGHTS), 0, 1)
    b = np.where(SH > 0, np.minimum(1.0, b), 1.0)
    rel = P0 - center
    x0 = (rel @ right) * ppb + W / 2
    y0 = H / 2 - (rel @ up) * ppb
    z0 = rel @ back
    ux, uy, uz = (PU @ right) * ppb, -(PU @ up) * ppb, PU @ back
    vx, vy, vz = (PV @ right) * ppb, -(PV @ up) * ppb, PV @ back
    texa = np.asarray(tex)
    TS = texa.shape[0]
    for i in np.nonzero(vis)[0]:
        det = ux[i] * vy[i] - uy[i] * vx[i]
        if abs(det) < 1e-9:
            continue
        xs = (x0[i], x0[i] + ux[i], x0[i] + vx[i], x0[i] + ux[i] + vx[i])
        ys = (y0[i], y0[i] + uy[i], y0[i] + vy[i], y0[i] + uy[i] + vy[i])
        bx0, bx1 = max(0, int(math.floor(min(xs)))), min(W - 1, int(math.ceil(max(xs))))
        by0, by1 = max(0, int(math.floor(min(ys)))), min(H - 1, int(math.ceil(max(ys))))
        if bx1 < bx0 or by1 < by0:
            continue
        gx, gy = np.meshgrid(np.arange(bx0, bx1 + 1) + 0.5 - x0[i], np.arange(by0, by1 + 1) + 0.5 - y0[i])
        inv = 1.0 / det
        s = (gx * vy[i] - gy * vx[i]) * inv
        t = (ux[i] * gy - uy[i] * gx) * inv
        m = (s >= 0) & (s < 1) & (t >= 0) & (t < 1)
        if not m.any():
            continue
        z = z0[i] + s * uz[i] + t * vz[i]
        zb = zbuf[by0:by1 + 1, bx0:bx1 + 1]
        m &= z > zb
        if not m.any():
            continue
        u0, v0, u1, v1 = UV[i]
        tu = np.floor(u0 + s * (u1 - u0)).astype(int).clip(0, TS - 1)
        tv = np.floor(v0 + t * (v1 - v0)).astype(int).clip(0, TS - 1)
        col = texa[tv, tu]
        m &= col[..., 3] >= 8
        if not m.any():
            continue
        zb[m] = z[m]
        sub = img[by0:by1 + 1, bx0:bx1 + 1]
        c = col[..., :3].astype(np.float64) * b[i]
        sub[m, 0:3] = c[m].astype(np.uint8)
        sub[m, 3] = 255
    return img


# ───────────────────────────── roles / feet ─────────────────────────────

ROLE_COL = {'leg': (255, 70, 70), 'arm': (70, 230, 255), 'head': (255, 220, 60), 'other': (235, 235, 235)}
FOOT_COLS_L = [(255, 96, 80), (255, 170, 60), (240, 230, 90), (255, 120, 190)]
FOOT_COLS_R = [(90, 170, 255), (90, 235, 210), (170, 140, 255), (120, 220, 120)]


def part_role(p):
    a, f = p.get('anim') or '', p.get('form') or ''
    if a == 'legs_walk' or f.startswith('leg'):
        return 'leg'
    if a in ('arm_left', 'arm_right'):
        return 'arm'
    if a in ('head', 'neck', 'jaw', 'tail_chain', 'tail'):
        return 'head'
    return 'other'


def _kmeans1d(v, k, iters=20):
    if k <= 1 or len(v) <= k:
        return np.zeros(len(v), dtype=int) if k <= 1 else np.arange(len(v)) % max(1, k)
    c = np.quantile(v, np.linspace(0.08, 0.92, k))
    lab = np.zeros(len(v), dtype=int)
    for _ in range(iters):
        lab = np.abs(v[:, None] - c[None, :]).argmin(axis=1)
        for j in range(k):
            if (lab == j).any():
                c[j] = v[lab == j].mean()
    return lab


def foot_clusters(parts, geos, rest):
    """Feet to track → [(label, part index, part-local corner points)].  A leg part that holds a whole leg set
    (before the split) is cut into one foot per leg by side (±X) and front-to-back order."""
    leg_idx = [i for i, p in enumerate(parts) if part_role(p) == 'leg' and geos[i] is not None and len(geos[i].p0)]
    forms = Counter(parts[i].get('form') for i in leg_idx)
    out = []
    for i in leg_idx:
        geo = geos[i]
        loc = geo.corners()
        w = place(loc, rest[i])
        y = w[:, 1]
        lo, hi = y.min(), y.max()
        low = y <= lo + max(0.06, 0.2 * (hi - lo))
        form = parts[i].get('form')
        n = LEG_FORMS.get(form, 1) if forms[form] == 1 else 1
        side_of = np.where(w[:, 0] >= 0, 1, -1)
        if n == 1:
            jx = (parts[i].get('joint') or parts[i]['pivot'])[0]
            sd = 1 if jx > 1e-4 else -1 if jx < -1e-4 else 0
            out.append(((('L' if sd > 0 else 'R' if sd < 0 else 'C'), i, loc[low], sd, float(w[low, 2].mean()))))
            continue
        per = max(1, n // 2)
        for sd in (1, -1):
            m = low & (side_of == sd)
            if not m.any():
                continue
            zs = w[m, 2]
            lab = _kmeans1d(zs, per) if per > 1 else np.zeros(len(zs), dtype=int)
            idx = np.nonzero(m)[0]
            for j in range(per):
                sel = idx[lab == j]
                if len(sel):
                    out.append((('L' if sd > 0 else 'R'), i, loc[sel], sd, float(w[sel, 2].mean())))
    # label front → back per side: L1 L2 … / R1 R2 …
    res = []
    for sd in (1, -1, 0):
        group = sorted([f for f in out if f[3] == sd], key=lambda f: -f[4])
        for k, (s, i, pts, _, _) in enumerate(group):
            res.append((f'{s}{k + 1}' if len(group) > 1 else s, i, pts, sd))
    return res


def foot_traces(feet, clip):
    """→ {label: (z[], ymin[])} over the clip frames."""
    tr = {}
    for (lab, i, pts, sd) in feet:
        zs, ys = [], []
        for fr in clip:
            w = place(pts, fr['t'][i])
            zs.append(float(w[:, 2].mean()))
            ys.append(float(w[:, 1].min()))
        tr[lab] = (np.array(zs), np.array(ys))
    return tr


def gait_metrics(traces, speed, dt):
    """Stride, lift, sinking and slip per foot + left/right phase correlation."""
    m = {}
    gmin = min((float(y.min()) for _, y in traces.values()), default=0.0)
    for lab, (z, y) in traces.items():
        stride = float(z.max() - z.min())
        planted = y <= gmin + 0.03
        slip = float('nan')
        if speed > 0 and planted.sum() >= 2:
            dz = (np.roll(z, -1) - z) / max(1e-6, dt)        # cyclic clip
            pl = planted & np.roll(planted, -1)
            if pl.any():
                slip = float(np.abs(dz[pl] + speed).mean())     # a planted foot should move back at the walk speed
        m[lab] = {'stride': stride, 'lift': float(y.max() - y.min()), 'min_y': float(y.min()), 'slip': slip}
    pairs = []

    def corr(a, b, kind):
        if a in traces and b in traces:
            x, y = traces[a][0], traces[b][0]
            r = float(np.corrcoef(x, y)[0, 1]) if x.std() > 1e-6 and y.std() > 1e-6 else float('nan')
            pairs.append((a, b, r, kind))
    for lab in traces:                       # left ↔ right of the same row
        if lab.startswith('L'):
            corr(lab, 'R' + lab[1:], '좌우')
    for s in ('L', 'R'):                     # neighbours on the same side (front → back)
        k = 1
        while f'{s}{k + 1}' in traces:
            corr(f'{s}{k}', f'{s}{k + 1}', '같은 쪽')
            k += 1
    k = 1
    while f'L{k}' in traces and f'R{k + 1}' in traces:   # diagonals
        corr(f'L{k}', f'R{k + 1}', '대각')
        k += 1
    return m, pairs


# ───────────────────────────── sheet ─────────────────────────────

def render_cell(task):
    """task = (mid, view, frame transforms, center, ppb, cell, roles, ground) → (image, pivot points, ground y, marks)."""
    mid, view, frame, center, ppb, cell, roles, ground = task
    geos = _GEOS[mid]
    faces = world_faces(geos, frame)
    basis = view_basis(*VIEWS[view])
    c = np.array(center)
    img = raster(faces, _TEX[mid], basis, c, ppb, cell, cell)
    right, up, back = basis
    pts = []
    for t, (role, jrel) in zip(frame, roles):
        # dot = the part's joint (rotation centre) where it is now: joint − pivot placed with the part transform
        rel = place(np.array([jrel]), t)[0] - c
        pts.append(((rel @ right) * ppb + cell / 2, cell / 2 - (rel @ up) * ppb, role))
    gy = cell / 2 - ((np.zeros(3) - c) @ up) * ppb
    def scr(p):
        rel = np.array(p) - c
        return ((rel @ right) * ppb + cell / 2, cell / 2 - (rel @ up) * ppb)
    marks = []
    if ground is not None:    # scrolling ground markers (mob-local z, moving backwards at the walk speed)
        off, step = ground
        for k in range(-40, 41):
            marks.append(scr((0.0, 0.0, k * step - off)))
    grid = []
    if view == 'q34':         # ground plane grid (0.5 block) instead of a screen-horizontal line
        R = cell / ppb
        n = int(R / 0.5) + 1
        for k in range(-n, n + 1):
            grid.append((scr((k * 0.5, 0.0, -R)), scr((k * 0.5, 0.0, R))))
            grid.append((scr((-R, 0.0, k * 0.5)), scr((R, 0.0, k * 0.5))))
    return img, pts, (gy if view != 'q34' else None), marks, grid


_GEOS = {}
_TEX = {}


def _init(geos, tex):
    _GEOS.update(geos)
    _TEX.update(tex)


def framing(geos, rest, cell, views, fill=0.58):
    """Centre + pixels-per-block from the rest pose only (same for before/after when the standing silhouette is the
    same); other poses may leave the cell."""
    P0, PU, PV, *_ = world_faces(geos, rest)
    if not len(P0):
        return np.array([0.0, 0.5, 0.0]), cell * fill
    pts = np.concatenate([P0, P0 + PU, P0 + PV, P0 + PU + PV])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    lo[1] = min(lo[1], 0.0)
    center = (lo + hi) / 2
    center[0] = 0.0
    ext = 0.3
    for v in views:
        r, u, _ = view_basis(*VIEWS[v])
        rel = pts - center
        ext = max(ext, float(np.abs(rel @ r).max()), float(np.abs(rel @ u).max()))
    return center, (cell * fill / 2) / ext


def draw_chart(d, x0, y0, W, H, traces, metrics, pairs, speed, dt, fonts, title):
    """Two panels: foot forward offset z and foot height y over the walk cycle."""
    f_small, f_tiny = fonts
    d.rectangle([x0, y0, x0 + W - 1, y0 + H - 1], fill=(56, 58, 70, 255))
    d.text((x0 + 6, y0 + 3), title, fill=(230, 230, 160), font=f_small)
    labs = list(traces)
    n = len(next(iter(traces.values()))[0]) if traces else 0
    pw = (W - 30) // 2
    ph = H - 60
    for k, (key, name) in enumerate((('z', '발 앞뒤 위치 z (블록, + = 앞)'), ('y', '발 높이 y (블록, 0 = 땅, 음수 = 바닥 뚫음)'))):
        px = x0 + 10 + k * (pw + 10)
        py = y0 + 22
        d.rectangle([px, py, px + pw, py + ph], outline=(110, 112, 126, 255))
        d.text((px + 4, py + 2), name, fill=(200, 200, 210), font=f_tiny)
        if not traces or n < 2:
            continue
        vals = np.concatenate([traces[l][0 if key == 'z' else 1] for l in labs])
        vmin, vmax = float(vals.min()), float(vals.max())
        if key == 'y':
            vmin, vmax = min(vmin, -0.05), max(vmax, 0.15)
        pad = max(0.05, (vmax - vmin) * 0.12)
        vmin, vmax = vmin - pad, vmax + pad

        def Y(v):
            return py + 16 + (ph - 22) * (1 - (v - vmin) / (vmax - vmin))

        def X(i):
            return px + 6 + (pw - 12) * i / (n - 1)
        if vmin < 0 < vmax:
            d.line([px + 1, Y(0), px + pw - 1, Y(0)], fill=(110, 200, 110, 255) if key == 'y' else (120, 120, 135, 255))
        d.text((px + pw - 64, py + 2), f'{vmax:+.2f}', fill=(150, 150, 160), font=f_tiny)
        d.text((px + pw - 64, py + ph - 14), f'{vmin:+.2f}', fill=(150, 150, 160), font=f_tiny)
        cl = cr = 0
        for li, l in enumerate(labs):
            if l.startswith('L'):
                col = FOOT_COLS_L[cl % len(FOOT_COLS_L)]
                cl += 1
            else:
                col = FOOT_COLS_R[cr % len(FOOT_COLS_R)]
                cr += 1
            v = traces[l][0 if key == 'z' else 1]
            d.line([(X(i), Y(v[i])) for i in range(n)], fill=col + (255,), width=2)
            if key == 'z':
                d.text((px + 8 + 30 * li, py + ph - 14), l, fill=col, font=f_tiny)
    # numbers
    ty = y0 + H - 34
    parts = []
    for l in labs:
        mm = metrics[l]
        slip = '-' if math.isnan(mm['slip']) else f'{mm["slip"]:.3f}'
        parts.append(f'{l}: 보폭 {mm["stride"]:.2f} · 들림 {mm["lift"]:.2f} · 최저 {mm["min_y"]:+.2f} · 미끄럼 {slip}')
    line1 = '   '.join(parts)
    d.text((x0 + 8, ty), line1[:400], fill=(215, 215, 220), font=f_tiny)
    if pairs:
        s = '  '.join(f'{kind} {a}/{b} r={r:+.2f}' + ('(같이)' if r > 0.8 else '(반대)' if r < -0.8 else '')
                      for a, b, r, kind in pairs if not math.isnan(r))
        nan = [f'{a}/{b}' for a, b, r, _ in pairs if math.isnan(r)]
        if nan:
            s += '  ' + ' '.join(nan) + ': 안 움직임'
    else:
        s = '짝 없음'
    d.text((x0 + 8, ty + 15), f'발 앞뒤 위상 상관 r (+1 = 같이 움직임, -1 = 번갈아): {s}'[:260], fill=(215, 215, 220),
           font=f_tiny)
    d.text((x0 + W - 330, y0 + 3), f'걷기 속도 {speed:.3f} 블록/틱 · 프레임 간격 {dt:.2f}틱', fill=(180, 180, 190), font=f_tiny)


def pick(n, k, cyclic=True):
    """k frame indices spread over n frames (a cycle: k evenly spaced phases; a clip: first … last)."""
    if n <= k:
        return list(range(n))
    if cyclic:
        return [int(math.floor(i * n / k)) for i in range(k)]
    return sorted({int(round(i * (n - 1) / (k - 1))) for i in range(k)})


def build_sheet(mid, info, models, atlas, out_png, prefix, cell=240, jobs=4, title_note='', gif=False, cols=8):
    parts = info['parts']
    geos = [PartGeo(models[p['name']], atlas) if p['name'] in models else None for p in parts]
    roles = [(part_role(p), [(p.get('joint') or p['pivot'])[a] - p['pivot'][a] for a in range(3)]) for p in parts]
    clips = info['clips']
    meta = info.get('clip_meta') or {}
    rest = clips['idle'][0]['t']
    center, ppb = framing(geos, rest, cell, ('side', 'q34', 'front'), fill=0.66)

    def ground(clip, k):
        cm = meta.get(clip) or {}
        v = float(cm.get('speed', 0.0))
        if v <= 0:
            return (0.0, 0.5)
        return ((v * float(cm.get('dt', 1.0)) * k) % 0.5, 0.5)

    rows = [('walk', 'side', '걷기 (최대 속도) · 옆 (오른쪽 면, 앞 = →) · 땅 눈금은 걷기 속도로 뒤로 흐름 — 디딘 발은 눈금과 같이 가야 함'),
            ('walk', 'q34', '걷기 (최대 속도) · 3/4'), ('walk', 'front', '걷기 (최대 속도) · 정면')]
    if 'walk_slow' in clips:
        rows.append(('walk_slow', 'side', '걷기 (절반 속도) · 옆'))
    rows += [('chart', None, None), ('idle+attack', 'q34', '대기 | 공격 · 3/4'), ('hurt_death', 'q34', '피격 → 사망 · 3/4')]
    if 'slam' in clips:
        rows.append(('slam', 'side', '보스 내려찍기(SLAM) 오버레이 · 옆'))
    row_frames = []
    for clip, view, label in rows:
        if clip == 'chart':
            row_frames.append((None, None, None, []))
            continue
        if clip == 'idle+attack':
            idle = clips['idle']
            frs = [('idle ' + idle[k]['label'], idle[k]['t'], None) for k in pick(len(idle), 2, cyclic=False)] + \
                  [('atk ' + clips['attack'][k]['label'], clips['attack'][k]['t'], None)
                   for k in pick(len(clips['attack']), cols - 2, cyclic=False)]
        else:
            fl = clips[clip]
            cyc = clip.startswith('walk')
            frs = [(fl[k]['label'], fl[k]['t'], ground(clip, k) if cyc and view != 'front' else None)
                   for k in pick(len(fl), cols, cyclic=cyc)]
        row_frames.append((clip, view, label, frs))
    tasks = []
    for clip, view, label, frs in row_frames:
        for lab, t, g in frs:
            tasks.append((mid, view, t, center.tolist(), ppb, cell, roles, g))
    if jobs > 1:
        with ProcessPoolExecutor(jobs, initializer=_init, initargs=({mid: geos}, {mid: atlas})) as ex:
            results = list(ex.map(render_cell, tasks, chunksize=2))
    else:
        _init({mid: geos}, {mid: atlas})
        results = [render_cell(t) for t in tasks]
    # foot traces (walk, full speed)
    feet = foot_clusters(parts, geos, rest)
    wm = meta.get('walk') or {}
    speed, dt = float(wm.get('speed', info.get('full_speed', 0.18))), float(wm.get('dt', 1.0))
    traces = foot_traces(feet, clips['walk'])
    metrics, pairs = gait_metrics(traces, speed, dt) if traces else ({}, [])
    head_h, lab_h, row_lab, chart_h = 48, 14, 20, 230
    W = max(cols * cell, 1100)
    H = head_h + sum((chart_h + 6) if clip is None else (row_lab + cell + lab_h) for clip, *_ in row_frames)
    sheet = Image.new('RGBA', (W, H), BG + (255,))
    d = ImageDraw.Draw(sheet)
    f_big, f_small, f_tiny = _font(18), _font(12), _font(11)
    d.text((6, 4), f'{prefix.upper()}  {mid}', fill=(245, 245, 245), font=f_big)
    legs = sum(1 for r, _ in roles if r == 'leg')
    d.text((6, 27), f'scale {info["scale"]} · {"보스" if info["boss"] else "몹"} · {"비행" if info["flying"] else "지상"} · '
                    f'파트 {len(parts)} (다리 파트 {legs}) · 점: 빨강 다리 · 하늘 팔 · 노랑 머리/목/꼬리 · 흰색 기타 (관절 = 회전 중심) · '
                    f'초록 선 = 땅 {title_note}', fill=(200, 200, 210), font=f_small)
    k = 0
    y = head_h
    gif_frames = []
    walk_cells = {}
    for clip, view, label, frs in row_frames:
        if clip is None:
            draw_chart(d, 0, y, W, chart_h, traces, metrics, pairs, speed, dt, (f_small, f_tiny),
                       '발 궤적 (걷기 최대 속도 한 주기) — 다리 하나에 발 여러 개가 붙어 있으면 옆(±X)·앞뒤 순서로 나눠서 추적')
            y += chart_h + 6
            continue
        d.text((6, y + 2), label, fill=(230, 230, 160), font=f_small)
        y += row_lab
        for ci, (lab, _, _) in enumerate(frs):
            img, pts, gy, marks, grid = results[k]
            k += 1
            x = ci * cell
            cellimg = Image.new('RGBA', (cell, cell), CELL_BG[ci % 2] + (255,))
            cd = ImageDraw.Draw(cellimg)
            for (a, b) in grid:
                cd.line([a, b], fill=(84, 104, 92, 255))
            if gy is not None and 0 <= gy < cell:
                cd.line([0, gy, cell - 1, gy], fill=(90, 170, 90, 255))
            for (mx, my) in marks:
                if 0 <= mx < cell and 0 <= my < cell:
                    cd.line([mx, my - 2, mx, my + 2], fill=(150, 220, 150, 255))
            cellimg.alpha_composite(Image.fromarray(img, 'RGBA'))
            for (px, py, role) in pts:
                if 0 <= px < cell and 0 <= py < cell:
                    c = ROLE_COL[role]
                    cd.ellipse([px - 2, py - 2, px + 2, py + 2], fill=c + (255,), outline=(0, 0, 0, 255))
            if gy is not None and 0 <= gy < cell:   # ground drawn again on top, thin: shows feet sinking below it
                cd.line([0, gy, cell - 1, gy], fill=(110, 220, 110, 120))
            sheet.alpha_composite(cellimg, (x, y))
            d.text((x + 3, y + cell), lab, fill=(200, 200, 205), font=f_small)

        y += cell + lab_h
    sheet.convert('RGB').save(out_png)
    if gif:
        wf = clips['walk']
        gt = [(mid, v, wf[k]['t'], center.tolist(), ppb, cell, roles, ground('walk', k) if v != 'front' else None)
              for k in range(len(wf)) for v in ('side', 'q34', 'front')]
        if jobs > 1:
            with ProcessPoolExecutor(jobs, initializer=_init, initargs=({mid: geos}, {mid: atlas})) as ex:
                gr = list(ex.map(render_cell, gt, chunksize=3))
        else:
            gr = [render_cell(t) for t in gt]
        for j, (img, pts, gy, marks, grid) in enumerate(gr):
            ci = Image.new('RGBA', (cell, cell), CELL_BG[0] + (255,))
            cd = ImageDraw.Draw(ci)
            for (a, b) in grid:
                cd.line([a, b], fill=(84, 104, 92, 255))
            if gy is not None and 0 <= gy < cell:
                cd.line([0, gy, cell - 1, gy], fill=(90, 170, 90, 255))
            for (mx, my) in marks:
                if 0 <= mx < cell and 0 <= my < cell:
                    cd.line([mx, my - 2, mx, my + 2], fill=(150, 220, 150, 255))
            ci.alpha_composite(Image.fromarray(img, 'RGBA'))
            walk_cells.setdefault(j // 3, {})[gt[j][1]] = ci
    if gif and walk_cells:
        for ci in sorted(walk_cells):
            vs = walk_cells[ci]
            fr = Image.new('RGB', (cell * len(vs), cell + 18), BG)
            for j, v in enumerate(('side', 'q34', 'front')):
                if v in vs:
                    fr.paste(vs[v].convert('RGB'), (j * cell, 18))
            ImageDraw.Draw(fr).text((4, 2), f'{prefix} {mid} walk {ci}', fill=(230, 230, 230), font=f_small)
            gif_frames.append(fr)
        gif_frames[0].save(out_png[:-4] + '_walk.gif', save_all=True, append_images=gif_frames[1:],
                           duration=int(50 * dt), loop=0)
    return out_png, metrics, pairs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dump', required=True, help='JSON from RigPreviewDump')
    ap.add_argument('--out', required=True)
    ap.add_argument('--prefix', default='before')
    ap.add_argument('--mobs', default='', help='comma list (default: every mob in the dump)')
    ap.add_argument('--pack', default=None, help='use the models in this pack zip instead of building in-process')
    ap.add_argument('--content', default=CONTENT)
    ap.add_argument('--cell', type=int, default=240)
    ap.add_argument('--cols', type=int, default=8, help='frames per row (sheet width = cols × cell)')
    ap.add_argument('--jobs', type=int, default=max(1, min(4, os.cpu_count() or 1)))
    ap.add_argument('--gif', action='store_true', help='also write <prefix>_<mob>_walk.gif')
    ap.add_argument('--metrics', default=None, help='write per-mob gait numbers to this JSON')
    ap.add_argument('--metrics-only', action='store_true', help='no pictures, only the --metrics numbers')
    args = ap.parse_args(argv)
    dump = json.load(open(args.dump, encoding='utf-8'))
    want = [s.strip() for s in args.mobs.split(',') if s.strip()] or list(dump['mobs'])
    content = None
    if not args.pack:
        import yaml
        content = {'mobs': yaml.safe_load(open(os.path.join(args.content, 'mobs.yml'), encoding='utf-8'))['mobs'],
                   'bosses': yaml.safe_load(open(os.path.join(args.content, 'bosses.yml'), encoding='utf-8'))['bosses']}
    os.makedirs(args.out, exist_ok=True)
    allm = {}
    for mid in want:
        info = dump['mobs'].get(mid)
        if info is None:
            print(f'{mid}: not in dump — skipped')
            continue
        info.setdefault('full_speed', (dump.get('meta') or {}).get('full_speed', 0.18))
        models, atlas = load_models(mid, info['boss'], args.pack, content)
        missing = [p['name'] for p in info['parts'] if p['name'] not in models]
        if args.metrics_only:
            parts = info['parts']
            geos = [PartGeo(models[p['name']], atlas) if p['name'] in models else None for p in parts]
            wm = (info.get('clip_meta') or {}).get('walk') or {}
            feet = foot_clusters(parts, geos, info['clips']['idle'][0]['t'])
            tr = foot_traces(feet, info['clips']['walk'])
            metrics, pairs = gait_metrics(tr, float(wm.get('speed', info['full_speed'])), float(wm.get('dt', 1.0))) \
                if tr else ({}, [])
            allm[mid] = {'feet': metrics, 'pairs': pairs}
            print(mid, flush=True)
            continue
        out = os.path.join(args.out, f'{args.prefix}_{mid}.png')
        _, metrics, pairs = build_sheet(mid, info, models, atlas, out, args.prefix, args.cell, args.jobs,
                                        title_note=(f'· 모델 없음: {",".join(missing)}' if missing else ''), gif=args.gif,
                                        cols=args.cols)
        allm[mid] = {'feet': metrics, 'pairs': pairs}
        print(out, flush=True)
    if args.metrics:
        json.dump(allm, open(args.metrics, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
