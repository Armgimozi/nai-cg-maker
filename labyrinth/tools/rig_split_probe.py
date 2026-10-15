#!/usr/bin/env python3
"""Leg-set split probe (rig preview tooling): for every leg set (leg_pair/quad/six/eight + legs_walk) and wing pair,
find where the single legs separate ("peel": hanging legs from the hip downwards, splayed legs from the body outwards),
propose a hip / shoulder joint and a foot point per leg, assign every voxel to one leg (multi-source geodesic BFS from the
separated legs), count the elements of the pieces meshed separately but shaded from the parent grid (= identical standing
look) against the model budget, and draw split-check images (voxels coloured per leg, joints marked).

Analysis only — reads content + designs, writes JSON and PNGs:
  JOBS=2 /opt/packvenv/bin/python labyrinth/tools/rig_split_probe.py OUT.json OUT_DIR [mob,mob,…]
Coordinates in the JSON: mob-local blocks at scale 1 (+X = mob left, +Y up, +Z front), like YAML pivots.
"""
import heapq
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LAB, 'resourcepack'))
import yaml  # noqa: E402

C = os.path.join(LAB, 'plugin/src/main/resources/content')
M = yaml.safe_load(open(f'{C}/mobs.yml'))['mobs']
B = yaml.safe_load(open(f'{C}/bosses.yml'))['bosses']
LEG_N = {'leg_pair': 2, 'leg_quad': 4, 'leg_six': 6, 'leg_eight': 8}
OFFS26 = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) != (0, 0, 0)]
COLS = [(255, 90, 80), (255, 180, 60), (240, 235, 90), (255, 120, 200), (80, 160, 255), (90, 235, 210), (170, 140, 255),
        (130, 230, 120)]


def ent(k, vs, piv):
    """voxel key → entity-local absolute blocks (+X mob left, +Z front)."""
    return (piv[0] - k[0] * vs / 16.0, piv[1] + k[1] * vs / 16.0, piv[2] - k[2] * vs / 16.0)


def components(keys):
    keys = set(keys)
    seen = set()
    out = []
    for k in keys:
        if k in seen:
            continue
        comp = [k]
        seen.add(k)
        i = 0
        while i < len(comp):
            c = comp[i]
            i += 1
            for o in OFFS26:
                q = (c[0] + o[0], c[1] + o[1], c[2] + o[2])
                if q in keys and q not in seen:
                    seen.add(q)
                    comp.append(q)
        out.append(comp)
    return sorted(out, key=len, reverse=True)


def geodesic(allkeys, seeds):
    """seeds {label: [keys]} → {key: label}; unreachable keys → nearest seed centroid."""
    allset = set(allkeys)
    dist, lab, h = {}, {}, []
    for li, ks in seeds.items():
        for k in ks:
            dist[k] = 0.0
            lab[k] = li
            h.append((0.0, li, k))
    heapq.heapify(h)
    while h:
        d, li, k = heapq.heappop(h)
        if d > dist.get(k, 1e18) or lab.get(k) != li:
            continue
        for o in OFFS26:
            q = (k[0] + o[0], k[1] + o[1], k[2] + o[2])
            if q not in allset:
                continue
            nd = d + math.sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2])
            if nd < dist.get(q, 1e18) - 1e-9:
                dist[q] = nd
                lab[q] = li
                heapq.heappush(h, (nd, li, q))
    cent = {li: tuple(sum(k[a] for k in ks) / len(ks) for a in range(3)) for li, ks in seeds.items() if ks}
    for k in allkeys:
        if k not in lab:
            lab[k] = min(cent, key=lambda li: sum((k[a] - cent[li][a]) ** 2 for a in range(3)))
    return lab


def peel(g, piv, n, kind):
    """→ (labels {key: leg}, legs [dict], method)."""
    vs = g.vs
    keys = list(g.vox)
    P = {k: ent(k, vs, piv) for k in keys}
    tot = len(keys)
    minc = max(4, int(0.015 * tot))
    if kind == 'wing':
        seeds = {0: [k for k in keys if P[k][0] > piv[0] + 1e-6], 1: [k for k in keys if P[k][0] < piv[0] - 1e-6]}
        lab = geodesic(keys, seeds)
        legs = []
        for li, sd in ((0, 1), (1, -1)):
            ks = [k for k in keys if lab[k] == li]
            dmin = min(abs(P[k][0] - piv[0]) for k in ks)
            inner = [k for k in ks if abs(P[k][0] - piv[0]) <= dmin + 1.5 / 16]
            legs.append({'side': sd, 'joint': [round(piv[0] + sd * dmin, 3), round(sum(P[k][1] for k in inner) / len(inner), 3),
                                               round(sum(P[k][2] for k in inner) / len(inner), 3)], 'vox': len(ks)})
        return lab, legs, 'side'
    if kind == 'hang':
        ys = sorted({P[k][1] for k in keys}, reverse=True)
        y1, y0 = ys[0], ys[-1]
        halfw = max(abs(P[k][0] - piv[0]) for k in keys)
        found = None
        def layout_ok(cs):
            """one leg per side (pair) / two per side, one front + one back (quad)."""
            cxs = [sum(P[k][0] for k in c) / len(c) - piv[0] for c in cs]
            sides = [1 if x >= 0 else -1 for x in cxs]
            if sides.count(1) != n // 2 or sides.count(-1) != n // 2:
                return False
            if min(len(c) for c in cs) < 0.3 * max(len(c) for c in cs):      # a stray bit is not a leg
                return False
            if min(abs(x) for x in cxs) < 0.15 * halfw:
                return False
            if n == 4:
                for sd in (1, -1):
                    zs = sorted(sum(P[k][2] for k in c) / len(c) for c, q in zip(cs, sides) if q == sd)
                    if zs[1] - zs[0] < 1.0 / 16:
                        return False
            return True

        for t in ys:
            sub = [k for k in keys if P[k][1] <= t + 1e-9]
            comps = [c for c in components(sub) if len(c) >= minc]
            if len(comps) >= n and layout_ok(comps[:n]):
                found = (t, comps[:n])
                break
            if t < y0 + 0.35 * (y1 - y0):
                break
        if found is None:
            method = 'fallback-quadrant'
            seeds = {}
            for k in keys:
                if P[k][1] > y0 + 0.4 * (y1 - y0):
                    continue
                sx = 0 if P[k][0] >= piv[0] else 1
                sz = 0 if (n <= 2 or P[k][2] >= piv[2]) else 1
                seeds.setdefault(sx * (2 if n > 2 else 1) + sz if n > 2 else sx, []).append(k)
            sep = y1
            comps = list(seeds.values())
        else:
            method = 'peel'
            sep, comps = found
        # order: front→back per side; label index = side-major (L front … , R front …)
        info = []
        for c in comps:
            cx = sum(P[k][0] for k in c) / len(c)
            cz = sum(P[k][2] for k in c) / len(c)
            info.append((1 if cx >= piv[0] else -1, cz, c))
        info.sort(key=lambda q: (-q[0], -q[1]))
        seeds = {i: q[2] for i, q in enumerate(info)}
        lab = geodesic(keys, seeds)
        legs = []
        for i, (sd, _, c) in enumerate(info):
            slab = [k for k in c if P[k][1] >= sep - 3.0 / 16 - 1e-9] or c
            jx = sum(P[k][0] for k in slab) / len(slab)
            jz = sum(P[k][2] for k in slab) / len(slab)
            jy = sep + max(0.0, (y1 - sep)) / 2 if y1 - sep > 1.5 / 16 else y1 - 1.5 / 16
            ks = [k for k in keys if lab[k] == i]
            low = min(P[k][1] for k in ks)
            sole = [k for k in ks if P[k][1] <= low + 1.0 / 16]
            fz = [P[k][2] for k in sole]
            legs.append({'side': sd, 'joint': [round(jx, 3), round(jy, 3), round(jz, 3)], 'vox': len(ks),
                         'foot': [round(sum(P[k][0] for k in sole) / len(sole) - jx, 3), round(low - jy, 3),
                                  round((max(fz) + min(fz)) / 2 - jz, 3), round((max(fz) - min(fz)) / 2, 3)]})
        return lab, legs, method + f' sep={sep:.3f}'
    # splayed: peel outward from the mid-plane
    ds = sorted({abs(P[k][0] - piv[0]) for k in keys})
    dmax = ds[-1]
    per = n // 2
    found = None
    for t in ds:
        ok = True
        res = []
        for sd in (1, -1):
            sub = [k for k in keys if (P[k][0] - piv[0]) * sd >= t - 1e-9]
            comps = [c for c in components(sub) if len(c) >= max(3, minc // 2)]
            if len(comps) < per:
                ok = False
                break
            res.append((sd, comps[:per]))
        if ok:
            found = (t, res)
            break
        if t > 0.7 * dmax:
            break
    if found is None:
        return None, None, 'fail'
    t, res = found
    info = []
    for sd, comps in res:
        for c in comps:
            info.append((sd, sum(P[k][2] for k in c) / len(c), c))
    info.sort(key=lambda q: (-q[0], -q[1]))
    seeds = {i: q[2] for i, q in enumerate(info)}
    lab = geodesic(keys, seeds)
    legs = []
    for i, (sd, _, c) in enumerate(info):
        ks = [k for k in keys if lab[k] == i]
        dmin = min(abs(P[k][0] - piv[0]) for k in ks)          # the leg's own region reaches back to its root
        slab = [k for k in ks if abs(P[k][0] - piv[0]) <= dmin + 2.0 / 16 + 1e-9]
        jy = sum(P[k][1] for k in slab) / len(slab)
        jz = sum(P[k][2] for k in slab) / len(slab)
        jx = piv[0] + sd * (dmin + 1.0 / 16)
        low = min(P[k][1] for k in ks)
        sole = [k for k in ks if P[k][1] <= low + 1.0 / 16]
        legs.append({'side': sd, 'joint': [round(jx, 3), round(jy, 3), round(jz, 3)], 'vox': len(ks),
                     'foot': [round(sum(P[k][0] for k in sole) / len(sole) - jx, 3), round(low - jy, 3),
                              round(sum(P[k][2] for k in sole) / len(sole) - jz, 3), 0.0]})
    return lab, legs, f'peel t={t:.3f}'


def draw(mid, name, g, piv, lab, legs, out_png):
    from PIL import Image, ImageDraw, ImageFont
    vs = g.vs
    P = {k: ent(k, vs, piv) for k in g.vox}
    xs = [p[0] for p in P.values()]
    ys = [p[1] for p in P.values()]
    zs = [p[2] for p in P.values()]
    views = [('정면 (x→왼쪽이 화면 오른쪽, y↑)', 0, 1, 2, 1), ('위 (x, z↑=앞)', 0, 2, 1, 1), ('옆 (z→앞, y↑)', 2, 1, 0, -1)]
    ext = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.3)
    S = 260
    ppb = (S - 30) / ext
    img = Image.new('RGB', (S * 3, S + 40), (50, 52, 62))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 12)
    except OSError:
        f = ImageFont.load_default()
    d.text((4, 2), f'{mid} / {name}: {len(legs)} pieces', fill=(240, 240, 240), font=f)
    for vi, (title, a, b, depth, _) in enumerate(views):
        ox = vi * S
        d.text((ox + 4, 18), title, fill=(200, 200, 160), font=f)
        ca = (max(p[a] for p in P.values()) + min(p[a] for p in P.values())) / 2
        cb = (max(p[b] for p in P.values()) + min(p[b] for p in P.values())) / 2
        order = sorted(P, key=lambda k: P[k][depth] * (1 if vi != 2 else -1))
        r = max(1, int(vs / 16 * ppb / 2 + 0.5))
        for k in order:
            p = P[k]
            sx = ox + S / 2 + (p[a] - ca) * ppb * (1 if a != 0 or vi == 1 else 1)
            sy = 40 + S / 2 - (p[b] - cb) * ppb
            col = COLS[lab[k] % len(COLS)]
            sh = 0.55 + 0.45 * ((p[depth] - min(q[depth] for q in (P[order[0]], P[order[-1]]))) /
                                max(1e-6, abs(P[order[-1]][depth] - P[order[0]][depth])))
            d.rectangle([sx - r, sy - r, sx + r, sy + r], fill=tuple(int(c * sh) for c in col))
        for i, L in enumerate(legs):
            j = L['joint']
            sx = ox + S / 2 + (j[a] - ca) * ppb
            sy = 40 + S / 2 - (j[b] - cb) * ppb
            d.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], outline=(255, 255, 255), width=2)
            d.text((sx + 5, sy - 6), str(i), fill=(255, 255, 255), font=f)
    img.save(out_png)


def one(task):
    mid, boss, out_dir = task
    from src import items, mobs
    from src.voxel import mob_build as MB
    from src.voxel.core import mesh as vmesh
    from src.voxel.palette import MOB_GLOW_MATS, coarse
    cap = {}
    orig = MB.fit_budget

    def spy(pms, budget, fixed=0, per_part=MB.PER_PART):
        r = orig(pms, budget, fixed, per_part)
        cap.update(pms=list(pms), budget=budget, fixed=fixed)
        return r
    MB.fit_budget = spy
    try:
        d = (B if boss else M)[mid]
        res = mobs.build_mob(mid, d, boss, items.jdump, items.png_bytes, items.strip)
    finally:
        MB.fit_budget = orig
    parts = (d.get('model') or {}).get('parts') or []
    pms = {pm.name: pm for pm in cap.get('pms', [])}
    sets = []
    for p in parts:
        form, anim = p.get('form'), p.get('anim')
        if not ((form in LEG_N and anim == 'legs_walk') or form == 'wing_pair'):
            continue
        name = p['name']
        piv = [float(v) for v in p.get('pivot') or [0, 0, 0]]
        st = {'part': name, 'form': form, 'anim': anim, 'pivot': piv, 'size': p.get('size'),
              'el_before': res.part_elements.get(name)}
        pm = pms.get(name)
        if pm is None:
            st['method'] = 'old-box'
            sets.append(st)
            continue
        kind = 'wing' if form == 'wing_pair' else ('hang' if form in ('leg_pair', 'leg_quad') else 'splay')
        lab, legs, method = peel(pm.grid, piv, LEG_N.get(form, 2), kind)
        st.update(kind=kind, method=method, legs=legs)
        if lab is None:
            sets.append(st)
            continue
        # same-level element count of the pieces (shaded on the parent grid)
        lv = pm.level
        ramps = coarse(pm.base_ramps) if lv >= 5 else pm.base_ramps
        lm = getattr(pm.grid, 'light_mul', 1.0)
        sh = MB.shade_mob(pm.grid, ramps, MOB_GLOW_MATS, noise_mul=MB.NOISE_STEPS[lv], light_amt=0.12 * lm, edge=0.07 * lm)
        counts = []
        for li in range(len(legs)):
            sub = {k: v for k, v in sh.items() if lab[k] == li}
            vm = vmesh(f'mob/{name}{li}', sub, ramps, vs=pm.grid.vs, origin=(0.0, 0.0, 0.0),
                       glow_cell=8 if lv >= 6 else 4, emission=12, overlap=True)
            counts.append(len(vm.boxes))
        st['level'] = lv
        st['el_pieces'] = counts
        st['total_before'] = sum(q.count for q in cap['pms']) + cap['fixed']
        st['total_split_same_level'] = st['total_before'] - pm.count + sum(counts)
        st['budget'] = cap['budget']
        os.makedirs(out_dir, exist_ok=True)
        draw(mid, name, pm.grid, piv, lab, legs, os.path.join(out_dir, f'split_{mid}_{name}.png'))
        sets.append(st)
    return mid, sets


if __name__ == '__main__':
    out_json, out_dir = sys.argv[1], sys.argv[2]
    only = set(sys.argv[3].split(',')) if len(sys.argv) > 3 and sys.argv[3] else None

    def has(dd):
        return any((p.get('form') in LEG_N and p.get('anim') == 'legs_walk') or p.get('form') == 'wing_pair'
                   for p in ((dd.get('model') or {}).get('parts') or []))
    tasks = [(k, False, out_dir) for k, v in M.items() if has(v) and (not only or k in only)] + \
            [(k, True, out_dir) for k, v in B.items() if has(v) and (not only or k in only)]
    res = {}
    with ProcessPoolExecutor(int(os.environ.get('JOBS', '2'))) as ex:
        for mid, sets in ex.map(one, tasks):
            res[mid] = sets
            print(mid, [(s['part'], s.get('method'), s.get('el_pieces'), s.get('total_split_same_level'), s.get('budget'))
                        for s in sets], flush=True)
    json.dump(res, open(out_json, 'w'), indent=1, ensure_ascii=False)
