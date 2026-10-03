#!/usr/bin/env python3
"""Tiny software rasterizer for Roblox part dumps (JSON from dump.luau).

python3 preview.py parts.json out.png --eye x,y,z --at x,y,z [--size 900x600] [--fov 50]
Shapes: Block, Wedge, CornerWedge, Cylinder, Ball (engine-verified geometry:
Wedge high edge at +Z top; CornerWedge apex at (+X,+Y,-Z); Cylinder axis = X).
Flat shading + sun shadow map + sky/ground ambient. Good enough to judge silhouettes.
"""
import argparse, json, math
import numpy as np
from PIL import Image

def box_tris():
    v = [(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
    idx = lambda x, y, z: ((x > 0) * 4 + (y > 0) * 2 + (z > 0))
    faces = []
    # each face as quad (ccw seen from outside not required: we use two-sided)
    for axis in range(3):
        for s in (-.5, .5):
            quad = []
            for a in (-.5, .5):
                for b in (-.5, .5):
                    p = [0, 0, 0]
                    p[axis] = s
                    o = [i for i in range(3) if i != axis]
                    p[o[0]] = a
                    p[o[1]] = b
                    quad.append(tuple(p))
            q = [quad[0], quad[1], quad[3], quad[2]]
            faces += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    return faces

BOX = box_tris()

def wedge_tris():
    A = (-.5, -.5, -.5); B = (.5, -.5, -.5); C = (.5, -.5, .5); D = (-.5, -.5, .5)
    E = (-.5, .5, .5); F = (.5, .5, .5)
    return [(A, B, C), (A, C, D),  # bottom
            (D, C, F), (D, F, E),  # back
            (A, B, F), (A, F, E),  # slope
            (A, D, E), (B, C, F)]  # sides

def cwedge_tris():
    A = (-.5, -.5, -.5); B = (.5, -.5, -.5); C = (.5, -.5, .5); D = (-.5, -.5, .5)
    P = (.5, .5, -.5)
    return [(A, B, C), (A, C, D), (B, C, P), (A, B, P), (A, D, P), (D, C, P)]

def cyl_tris(n=18):
    t = []
    for i in range(n):
        a0 = 2 * math.pi * i / n; a1 = 2 * math.pi * (i + 1) / n
        p0 = (math.cos(a0) * .5, math.sin(a0) * .5); p1 = (math.cos(a1) * .5, math.sin(a1) * .5)
        l0 = (-.5, p0[0], p0[1]); l1 = (-.5, p1[0], p1[1]); r0 = (.5, p0[0], p0[1]); r1 = (.5, p1[0], p1[1])
        t += [(l0, r0, r1), (l0, r1, l1), ((-.5, 0, 0), l0, l1), ((.5, 0, 0), r0, r1)]
    return t

def ball_tris(nu=16, nv=10):
    t = []
    def P(u, v):
        th = 2 * math.pi * u / nu; ph = math.pi * v / nv
        return (.5 * math.sin(ph) * math.cos(th), .5 * math.cos(ph), .5 * math.sin(ph) * math.sin(th))
    for u in range(nu):
        for v in range(nv):
            a, b, c, d = P(u, v), P(u + 1, v), P(u + 1, v + 1), P(u, v + 1)
            t += [(a, b, c), (a, c, d)]
    return t

SHAPES = {"Block": np.array(BOX), "Wedge": np.array(wedge_tris()), "CornerWedge": np.array(cwedge_tris()),
          "Cylinder": np.array(cyl_tris()), "Ball": np.array(ball_tris())}

def part_tris(p):
    shape = p["shape"]
    sx, sy, sz = p["size"]
    if shape == "Cylinder":
        d = min(sy, sz)
        scale = np.array([sx, d, d])
    elif shape == "Ball":
        d = min(sx, sy, sz)
        scale = np.array([d, d, d])
    else:
        scale = np.array([sx, sy, sz])
    T = SHAPES.get(shape, SHAPES["Block"]) * scale
    c = p["cf"]
    pos = np.array(c[0:3]); R = np.array(c[3:12]).reshape(3, 3)
    return T @ R.T + pos

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json"); ap.add_argument("out")
    ap.add_argument("--eye", required=True); ap.add_argument("--at", required=True)
    ap.add_argument("--size", default="900x600"); ap.add_argument("--fov", type=float, default=50)
    ap.add_argument("--sun", default="-0.45,0.8,-0.35")
    ap.add_argument("--ground", type=float, default=None, help="draw ground plane at this y")
    a = ap.parse_args()
    parts = json.load(open(a.json))
    W, H = [int(v) for v in a.size.split("x")]
    eye = np.array([float(v) for v in a.eye.split(",")]); at = np.array([float(v) for v in a.at.split(",")])
    sun = np.array([float(v) for v in a.sun.split(",")]); sun /= np.linalg.norm(sun)

    tris, cols = [], []
    for p in parts:
        if p.get("transparency", 0) >= 0.99:
            continue
        t = part_tris(p)
        tris.append(t)
        cols.append(np.repeat([p["color"]], len(t), axis=0))
    ntris_parts = sum(len(t) for t in tris)
    if a.ground is not None:
        g = a.ground; N = 40; R = 300.0
        xs = np.linspace(at[0] - R, at[0] + R, N + 1); zs = np.linspace(at[2] - R, at[2] + R, N + 1)
        gt = []
        for i in range(N):
            for j in range(N):
                x0, x1, z0, z1 = xs[i], xs[i + 1], zs[j], zs[j + 1]
                gt += [[(x0, g, z0), (x1, g, z0), (x1, g, z1)], [(x0, g, z0), (x1, g, z1), (x0, g, z1)]]
        tris.append(np.array(gt)); cols.append(np.array([[104, 150, 82]] * len(gt)))
    tris = np.concatenate(tris).astype(np.float64)
    cols = np.concatenate(cols).astype(np.float64) / 255.0
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1); keep = ln > 1e-9
    ntris_parts = int(keep[:ntris_parts].sum())
    tris, cols, nrm = tris[keep], cols[keep], nrm[keep] / ln[keep][:, None]

    def raster(V, w, h, persp):
        # V: (n,3,3) in clip-ish space: x,y in pixels, z depth (smaller = nearer)
        depth = np.full((h, w), np.inf); tid = np.full((h, w), -1, dtype=np.int64)
        bary = np.zeros((h, w, 3))
        for i in range(len(V)):
            v = V[i]
            if np.any(~np.isfinite(v)) or np.any(v[:, 2] <= 0.05 if persp else False):
                continue
            x0 = max(int(math.floor(v[:, 0].min())), 0); x1 = min(int(math.ceil(v[:, 0].max())), w - 1)
            y0 = max(int(math.floor(v[:, 1].min())), 0); y1 = min(int(math.ceil(v[:, 1].max())), h - 1)
            if x0 > x1 or y0 > y1:
                continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
            (ax, ay), (bx, by), (cx, cy) = v[0, :2], v[1, :2], v[2, :2]
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-12:
                continue
            l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
            l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            if not inside.any():
                continue
            if persp:  # perspective-correct depth: interpolate 1/z
                iz = l0 / v[0, 2] + l1 / v[1, 2] + l2 / v[2, 2]
                z = 1 / iz
            else:
                z = l0 * v[0, 2] + l1 * v[1, 2] + l2 * v[2, 2]
            sub = depth[y0:y1 + 1, x0:x1 + 1]
            m = inside & (z < sub)
            sub[m] = z[m]
            tid[y0:y1 + 1, x0:x1 + 1][m] = i
            if persp:
                w0 = l0 / v[0, 2] / iz; w1 = l1 / v[1, 2] / iz; w2 = l2 / v[2, 2] / iz
            else:
                w0, w1, w2 = l0, l1, l2
            bsub = bary[y0:y1 + 1, x0:x1 + 1]
            bsub[m] = np.stack([w0[m], w1[m], w2[m]], axis=-1)
        return depth, tid, bary

    # camera
    fwd = at - eye; fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    f = (H / 2) / math.tan(math.radians(a.fov) / 2)
    rel = tris - eye
    cz = rel @ fwd; cx = rel @ right; cy = rel @ up
    V = np.stack([W / 2 + f * cx / cz, H / 2 - f * cy / cz, cz], axis=-1)
    depth, tid, bary = raster(V, W, H, True)

    # shadow map (orthographic from sun)
    S = 1400
    lf = -sun; lr = np.cross(lf, [0, 1, 0]); lr /= np.linalg.norm(lr); lu = np.cross(lr, lf)
    allp = tris[:ntris_parts].reshape(-1, 3)
    px, py, pz = allp @ lr, allp @ lu, allp @ lf
    mnx, mxx, mny, mxy = px.min(), px.max(), py.min(), py.max()
    sc = (S - 2) / max(mxx - mnx, mxy - mny)
    def to_light(P):
        return np.stack([(P @ lr - mnx) * sc + 1, (mxy - P @ lu) * sc + 1, P @ lf - pz.min() + 1], axis=-1)
    LV = to_light(tris)
    sdepth, _, _ = raster(LV, S, S, False)

    img = np.zeros((H, W, 3))
    # sky gradient
    yy = np.linspace(0, 1, H)[:, None]
    img[:] = (np.array([0.62, 0.74, 0.86]) * (1 - yy) + np.array([0.85, 0.88, 0.9]) * yy)[:, None, :]
    hit = tid >= 0
    ids = tid[hit]
    b = bary[hit]
    wp = (tris[ids] * b[:, :, None]).sum(axis=1)
    n = nrm[ids].copy()
    view = eye - wp
    flip = (n * view).sum(axis=1) < 0
    n[flip] *= -1
    lam = np.clip(n @ sun, 0, 1)
    texel = 1.0 / sc
    L = to_light(wp + n * (1.5 * texel + 0.05))
    inb = (L[:, 0] >= 0) & (L[:, 0] < S) & (L[:, 1] >= 0) & (L[:, 1] < S)
    sx = np.clip(L[:, 0].astype(int), 0, S - 1); sy = np.clip(L[:, 1].astype(int), 0, S - 1)
    # 3x3 min filter on the depth to kill acne from shared triangle edges
    sd = sdepth
    lit = np.where(inb, (L[:, 2] <= sd[sy, sx] + 0.15 + 2 * texel).astype(float), 1.0)
    sky = 0.5 + 0.5 * n[:, 1]
    shade = 0.32 + 0.18 * sky + 0.62 * lam * lit
    c = cols[ids] * shade[:, None]
    # distance fog
    d = np.linalg.norm(view, axis=1)
    fog = np.clip((d - 150) / 900, 0, 0.6)[:, None]
    c = c * (1 - fog) + np.array([0.78, 0.83, 0.88]) * fog
    img[hit] = c
    # edge darkening (depth discontinuity) for readability
    dd = np.where(hit, depth, 1e6)
    edge = np.zeros_like(dd, dtype=bool)
    edge[1:, :] |= np.abs(dd[1:, :] - dd[:-1, :]) > 0.04 * np.minimum(dd[1:, :], dd[:-1, :])
    edge[:, 1:] |= np.abs(dd[:, 1:] - dd[:, :-1]) > 0.04 * np.minimum(dd[:, 1:], dd[:, :-1])
    img[edge & hit] *= 0.7
    Image.fromarray((np.clip(img, 0, 1) ** (1 / 1.1) * 255).astype(np.uint8)).save(a.out)
    print("wrote", a.out, "tris", len(tris), "parts", len(parts))

if __name__ == "__main__":
    main()
