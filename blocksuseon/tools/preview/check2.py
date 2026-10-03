#!/usr/bin/env python3
"""Per-building closure checks on solo_*.json (built at origin by solo.luau).

1) roof coverage: vertical rays over the eave outline (inset 0.3): first hit must be a roof part
2) roof continuity: neighbouring first-hit heights on Giwa differ < 0.6 at 0.25 spacing
3) closure: horizontal rays from outside toward the centre inside the wall footprint, from wall
   bottom up to the ridge: must hit something before reaching the centre (no see-through, no
   gap between walls, beams and roof). Open pavilions skip the lower band (railings).
4) floating parts: every part must touch another (AABB of OBB grown by 0.05), except the first.
"""
import json, math, sys
import numpy as np
sys.path.insert(0, '.')
from preview import part_tris
from check import raycast

ROOF = {'Giwa', 'Maru', 'Mangwa', 'Yangseong', 'Jeolbyeong', 'Hapgak'}
meta = json.load(open('solo_meta.json'))

def obb(p):
    c = p['cf']; pos = np.array(c[:3]); R = np.array(c[3:]).reshape(3, 3); s = np.array(p['size']) / 2
    return pos, R, s

def obb_overlap(a, b, grow=0.06):
    pa, Ra, sa = a; pb, Rb, sb = b
    sa = sa + grow; sb = sb + grow
    A = [Ra[:, i] for i in range(3)]; B = [Rb[:, i] for i in range(3)]
    axes = A + B + [np.cross(u, v) for u in A for v in B]
    d = pb - pa
    for L in axes:
        n = np.linalg.norm(L)
        if n < 1e-6: continue
        L = L / n
        ra = sum(sa[i] * abs(A[i] @ L) for i in range(3)); rb = sum(sb[i] * abs(B[i] @ L) for i in range(3))
        if abs(d @ L) > ra + rb: return False
    return True

for name, mt in meta.items():
    parts = json.load(open(f'solo_{name}.json'))
    T, names = [], []
    for p in parts:
        t = part_tris(p); T.append(t); names += [p['name']] * len(t)
    T = np.concatenate(T); names = np.array(names)
    W, D, eaveY, top = mt['W'], mt['D'], mt['eaveY'], mt['top']
    giwa = np.concatenate([part_tris(p) for p in parts if p['name'] == 'Giwa']).reshape(-1, 3)
    ex = (giwa[:, 0].max() - giwa[:, 0].min()) / 2; ez = (giwa[:, 2].max() - giwa[:, 2].min()) / 2
    # the flared corners make the bbox larger than the straight eave line; use W/2+eave
    eave = ex - W / 2  # approx incl. flare
    exs, ezs = W / 2 + 3.2, D / 2 + 3.2  # safely inside eave (eave >= 3.6)
    ytop = top + 6
    miss = nonroof = 0; H = {}
    xs = np.arange(-exs, exs + 1e-6, 0.25); zs = np.arange(-ezs, ezs + 1e-6, 0.25)
    for i, x in enumerate(xs):
        for j, z in enumerate(zs):
            t, k = raycast(T, np.array([x, ytop, z]), np.array([0, -1.0, 0]))
            if k < 0:
                miss += 1; continue
            if names[k] not in ROOF:
                nonroof += 1
                if nonroof <= 3: print(f'  [{name}] non-roof first hit {names[k]} at ({x:.2f},{z:.2f})')
            if names[k] == 'Giwa': H[(i, j)] = ytop - t
    jumps = 0
    for (i, j), h in H.items():
        for di, dj in ((1, 0), (0, 1)):
            q = H.get((i + di, j + dj))
            if q is not None and abs(q - h) > 0.6:
                jumps += 1
                if jumps <= 3: print(f'  [{name}] height jump {h:.2f}->{q:.2f} at ({xs[i]:.2f},{zs[j]:.2f})')
    # closure rays
    see = tot = 0
    open_ = any(p['name'] == 'Nangan' for p in parts)
    floor = [p for p in parts if p['name'] == 'Floor']
    y0 = floor[0]['cf'][1] + 0.4 if floor else 1
    ylo = (eaveY - 0.5) if open_ else y0
    def surf(x, z):
        t, k = raycast(T, np.array([x, ytop, z]), np.array([0, -1.0, 0]))
        return ytop - t if k >= 0 else -1e9
    for z in np.arange(-D / 2 + 0.4, D / 2 - 0.39, 0.5):
        for sgn in (1, -1):
            ceil = surf(sgn * (W / 2 - 0.3), z) - 0.8
            for y in np.arange(ylo, ceil, 0.3):
                tot += 1
                o = np.array([sgn * (W / 2 + 8), y, z]); d = np.array([-sgn * 1.0, 0, 0])
                t, k = raycast(T, o, d)
                if k < 0 or t > W / 2 + 8:
                    see += 1
                    if see <= 3: print(f'  [{name}] see-through x-ray y={y:.2f} z={z:.2f}')
    for x in np.arange(-W / 2 + 0.4, W / 2 - 0.39, 0.5):
        for sgn in (1, -1):
            ceil = surf(x, sgn * (D / 2 - 0.3)) - 0.8
            for y in np.arange(ylo, ceil, 0.3):
                tot += 1
                o = np.array([x, y, sgn * (D / 2 + 8)]); d = np.array([0, 0, -sgn * 1.0])
                t, k = raycast(T, o, d)
                if k < 0 or t > D / 2 + 8:
                    see += 1
                    if see <= 3: print(f'  [{name}] see-through z-ray y={y:.2f} x={x:.2f}')
    # floating parts
    boxes = [obb(p) for p in parts]
    lone = []
    for i, b in enumerate(boxes):
        if not any(obb_overlap(b, boxes[j]) for j in range(len(boxes)) if j != i):
            lone.append(parts[i]['name'])
    print(f'{name:9s} parts {len(parts):4d} | roof rays {len(xs)*len(zs)}: miss {miss}, non-roof {nonroof}, jumps {jumps} | closure rays {tot}: through {see} | floating {len(lone)} {lone[:6]}')
