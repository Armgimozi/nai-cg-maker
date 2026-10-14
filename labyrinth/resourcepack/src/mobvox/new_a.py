"""새 몬스터 복셀 설계 A — 드래곤 · 와이번 · 땅굴웜 · 하피 · 리치.  README.md · NEW_MOBS.md 참고.

drake (네 발 + 날개): moss_drakeling · bog_drake · ember_drake · void_drake
wyvern (두 발 + 날개): frost_wyvern · clockwork_wyvern
worm: tunnel_wyrm · harpy: spore_harpy · quill_harpy · lich: barrow_lich

공용 드래곤 도구(_d_*)를 몹마다 재질·장식만 바꿔 쓴다.  이음매 규칙(NEW_MOBS.md):
neck = pivot(목 뿌리)에서 앞(−Z)·위로, tail/segment = pivot(앞면)에서 뒤(+Z)로, wing = 어깨 pivot 에서 ctx.out 쪽
XZ 평면(앞전 −Z), jaw = pivot 바로 뒤 경첩에서 앞으로.  사슬 끝은 둥글게 겹쳐 휘어도 틈이 안 보이게 한다.
좌표: 부위 px, 원점 = 그 부위 pivot, 정면 = −Z, 모델 −X = 몹의 왼쪽.
"""
from __future__ import annotations

import math

from ..materials import rune_bit
from ..util import h2
from ..voxel.mob_kit import MobGrid, fbm3, vadd, vmul, vnorm  # noqa: F401
from ..voxel.palette import _r

GLOW_MATS = ('glow', 'eye', 'core', 'rune', 'lava')


def _hx(*cols):
    return [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in cols]


def _ramps(ctx, table):
    """몹 전체 램프.  발광 램프는 11단계로 늘려 예산 축소(램프 절반) 뒤에도 맥동 색이 바뀌게 한다."""
    for mat, cols in table.items():
        ctx.set_ramp(mat, _r(cols, 11) if mat in GLOW_MATS else cols)


def _size(ctx, name):
    p = ctx.part_def(name)
    return tuple(float(v) for v in (p.get('size') or (8, 8, 8))) if p else None


def _V(n, lo=0.4, of=None):
    """부위 크기에 맞춘 복셀 크기: max(size)/n px (of = 다른 부위 크기 기준 — 턱·뿔은 머리와 같은 결)."""
    return lambda ctx: max(lo, max(_size(ctx, of) or ctx.size if of else ctx.size) / n)


def _Vneck(n, lo=0.4):
    return lambda ctx: max(lo, math.hypot(ctx.size[1], ctx.size[2]) / n)


def _run(ctx, name, table):
    ent = table.get(name)
    if ent is None:
        return None
    fn, vs = ent
    g = ctx.grid(vs(ctx) if callable(vs) else vs)
    fn(g, ctx)
    return g


def _lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _poly_in(poly, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _bites(poly, chain, sag):
    """가장자리 물어뜯기 원: chain 의 이웃 점 사이마다 깊이 sag·현 길이의 얕은 호(바깥쪽 중심)."""
    cx = sum(q[0] for q in poly) / len(poly)
    cy = sum(q[1] for q in poly) / len(poly)
    out = []
    for a_, b_ in zip(chain, chain[1:]):
        mx, my = (a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2
        c = math.hypot(b_[0] - a_[0], b_[1] - a_[1]) or 1e-6
        sg = max(0.05, sag * c)
        R = (c * c / 4 + sg * sg) / (2 * sg)
        nx, ny = -(b_[1] - a_[1]) / c, (b_[0] - a_[0]) / c
        if nx * (mx - cx) + ny * (my - cy) < 0:
            nx, ny = -nx, -ny
        out.append((mx + nx * (R - sg), my + ny * (R - sg), R))
    return out


def _feathers(g, feathers, plane='xz', depth=0.0, mat='feather', vfn=None, prio=2):
    """겹친 깃털 한 겹(평면 2D): feathers = [((u, v) 뿌리, (u, v) 끝, 반폭)], 뒤에 적은 깃이 위에 덮인다.
    plane 'xz' = 날개·꽁지(두께 Y), 'zy' = 세로 볏(두께 X).  vfn(n, t, e) → 값 | (재질, 값[, 발광])."""
    def which(u, v):
        hit = None
        for n, ((au, av), (bu, bv), hw) in enumerate(feathers):
            du, dv = bu - au, bv - av
            L2 = du * du + dv * dv or 1e-6
            t = max(0.0, min(1.0, ((u - au) * du + (v - av) * dv) / L2))
            dist = math.hypot(u - au - du * t, v - av - dv * t)
            wid = hw * min(1.0, (1.04 - t) * 4.0) * (0.55 + 0.45 * min(1.0, t * 3.0))
            if dist <= wid:
                hit = (n, t)
        return hit
    us = [p[0] for f in feathers for p in f[:2]]
    vs_ = [p[1] for f in feathers for p in f[:2]]
    pad = max(f[2] for f in feathers) + 0.5

    def vf(u, v, w, e):
        h = which(u, v)
        if h is None:
            return None
        if vfn:
            return vfn(h[0], h[1], e)
        return 0.48 + (0.08 if h[0] % 2 else 0.0) - (0.12 if h[1] > 0.82 else 0.0)
    g.slab2d(lambda u, v: which(u, v) is not None, (min(us) - pad, min(vs_) - pad), (max(us) + pad, max(vs_) + pad),
             plane, depth=depth, half=0.0, mat=mat, vfn=vf, prio=prio)


def _frustum(g, y0, y1, r0, r1, mat, val=0.5, vfn=None, prio=1):
    """타원 단면 원뿔대(y0 → y1, 반지름 (rx, rz) r0 → r1, 평평한 끝).  vfn(x, y, z, t, a) (a = 둘레 각)."""
    vs = g.vs
    lo, hi = min(y0, y1), max(y0, y1)
    R = max(r0[0], r0[1], r1[0], r1[1])
    for j in g._range(lo, hi):
        y = j * vs
        t = (y - y0) / ((y1 - y0) or 1e-6)
        if t < -1e-6 or t > 1 + 1e-6:
            continue
        rx = r0[0] + (r1[0] - r0[0]) * t
        rz = r0[1] + (r1[1] - r0[1]) * t
        for i in g._range(-R, R):
            x = i * vs
            for k in g._range(-R, R):
                z = k * vs
                if (x / rx) ** 2 + (z / rz) ** 2 > 1.0:
                    continue
                res = vfn(x, y, z, t, math.atan2(z, x)) if vfn else val
                g._emit((i, j, k), res, mat, False, prio)


def _spots(g, pts, r, res, mats=None):
    """점들 둘레 r 안의 표면을 칠한다(발광 점·눈알 무늬·광석 박힘).  res = (재질, 값[, 발광])."""
    def f(x, y, z, n, m, v):
        for p in pts:
            if (x - p[0]) ** 2 + (y - p[1]) ** 2 + (z - p[2]) ** 2 <= r * r:
                return res
        return None
    g.paint(f, mats)


# ───────────────────────────── 공용 드래곤 도구 ─────────────────────────────

def _d_body(g, ctx, plates=5, spine=0.8, spikes=4, spike_len=None, flat=1.0, mat='scale', belly_val=0.5,
            spike_mat='horn'):
    """몸통(pivot 중심): 가슴·엉덩이 두 덩이 배, 겹친 등비늘판 + 등줄기, 날개 뿌리 어깨 혹, 등가시."""
    w, h, d = ctx.size
    rx, ry, rz = w / 2, h / 2 * flat, d / 2
    g.blob((0, -ry * 0.12, -rz * 0.3), (rx * 0.95, ry * 0.9, rz * 0.62), 'belly', belly_val, top=0.06)
    g.blob((0, -ry * 0.08, rz * 0.32), (rx * 0.88, ry * 0.84, rz * 0.64), 'belly', belly_val, top=0.06)
    g.plates((0, ry * 0.06, 0), (rx, ry * 0.94, rz), n=plates, axis=2, mat=mat, val=0.5, lift=0.08, groove=-0.2,
             ridge=spine, cut=lambda x, y, z: y < -ry * 0.3, prio=2)
    wl = ctx.offset_to('wing_left')
    if wl:
        for s in (-1, 1):
            g.blob((s * abs(wl[0]) * 0.85, wl[1] - 0.3, wl[2]), (rx * 0.34, ry * 0.34, rz * 0.2), mat, 0.56, prio=3)
    if spikes:
        L = spike_len or ry * 0.55
        pts = []
        for k in range(spikes):
            z = -rz * 0.62 + rz * 1.3 * k / max(1, spikes - 1)
            y = ry * 0.06 + ry * 0.94 * math.sqrt(max(0.0, 1 - (z / rz) ** 2)) + spine * 0.5
            pts.append((0, y, z))
        g.spikes(pts, (0, 1, 0.6), L, max(0.45, rx * 0.13), spike_mat, 0.35, 0.85, vary=0.25)
    return rx, ry, rz


def _d_neck(g, ctx, mat='scale', spikes=2, spike_mat='horn', belly=True):
    """목: 뿌리(pivot, 몸 안쪽으로 조금 묻힘) → 앞 d · 위 h.  목구멍 쪽은 고리 비늘."""
    w, h, d = ctx.size
    r0, r1 = w / 2 * 1.1, w / 2 * 0.88
    pts = [(0, -h * 0.15, w * 0.3), (0, h * 0.45, -d * 0.42), (0, h, -d)]
    g.sweep(pts, r0, r1, mat, 0.5, vfn=lambda t, dd, p: 0.44 + 0.12 * t + 0.08 * (1 - dd))
    if belly:
        g.paint(lambda x, y, z, n, m, v: ('belly', 0.52) if (n[1] < 0 or (n[2] < 0 and n[1] == 0)) else None, [mat])
    for t in (0.3, 0.62, 0.92)[:spikes]:
        p = _lerp3(pts[0], pts[1], t * 2) if t < 0.5 else _lerp3(pts[1], pts[2], t * 2 - 1)
        r = r0 + (r1 - r0) * t
        g.cone((0, p[1] + r * 0.8, p[2] + r * 0.4), (0, 0.8, 1), r * 0.9, max(0.4, r * 0.28), spike_mat, 0.35, 0.85)
    return pts[-1], r1


def _d_head(g, ctx, mat='scale', snout=1.0, flat=1.0, eye_r=None, eye_val=0.5, eye_at=None, slit=True,
            nostril=('mouth', 0.2, False), throat='core', cheeks=True, brow=True, fangs=True, cranium=1.0):
    """드래곤 머리: 뒤통수(목 끝을 덮음) + 턱 끝까지 뻗은 납작한 주둥이, 입천장(턱이 벌어지면 보임)과 목구멍 빛,
    윗니·송곳니, 눈두덩·발광 눈, 콧구멍, 볼 가시.  돌려주는 값 = (주둥이 끝 z, 입천장 y, 끝 반지름)."""
    w, h, d = ctx.size
    J = ctx.offset_to('jaw') or (0.0, -h * 0.4, -d * 0.25)
    js = _size(ctx, 'jaw') or (w * 0.8, 2.0, d * 0.5)
    rx, ry, rz = w / 2, h / 2 * flat, d / 2
    tip_z = J[2] - js[2] - 0.4
    palate = J[1] + js[1] * 0.5
    cz = rz * 0.25
    g.blob((0, ry * 0.12, cz), (rx * 0.92 * cranium, ry * 0.86, rz * 0.6), mat, 0.5)
    rt = max(0.9, rx * 0.42 * snout)
    sq = 0.72
    tip = (0, palate + rt * sq, tip_z + rt)
    mid = (0, (ry * 0.1 + tip[1]) / 2 + ry * 0.06, (cz - rz * 0.1 + tip[2]) / 2)
    g.sweep([(0, ry * 0.1, cz - rz * 0.1), mid, tip], rx * 0.76, rt, mat, 0.5, sq=(1.0, sq, 1.0),
            vfn=lambda t, dd, p: 0.48 + 0.06 * t + 0.08 * (1 - dd))
    # 목 끝을 덮는 뒷덜미
    for nk in ('neck_2', 'neck'):
        ns = _size(ctx, nk)
        if ns:
            o = ctx.offset_to(nk)
            g.blob((o[0], o[1] + ns[1], o[2] - ns[2]), ns[0] / 2 * 0.95, mat, 0.46)
            break
    # 입천장 + 목구멍
    g.rbox((-rt * 0.8, palate - 0.1, tip_z + 0.7), (rt * 0.8, palate + 0.4, J[2] + 1.2), 'mouth', 0.25, prio=3)
    if throat:
        g.blob((0, palate + 0.3, J[2] + 1.0), max(0.7, rt * 0.6), throat, 0.6, glow=True, prio=4)
    # 윗니
    n_t = max(2, int(abs(J[2] - tip_z) / 1.7))
    for s in (-1, 1):
        g.teeth((s * rt * 0.8, palate + 0.1, tip_z + 0.9), (s * rx * 0.55, palate + 0.1, J[2] + 0.4), n_t,
                0.5 + js[1] * 0.25, r=0.3, direction=(0, -1, 0))
        if fangs:
            g.cone((s * rt * 0.62, palate + 0.2, tip_z + 1.0), (0, -1, -0.15), js[1] * 0.85 + 0.4, 0.38, 'tooth', 0.55,
                   0.9, prio=4)
    # 눈
    er = eye_r or max(0.55, min(w, h) * 0.13)
    ex, ey, ez = eye_at or (rx * 0.66, ry * 0.32, cz - rz * 0.42)
    for s in (-1, 1):
        if brow:
            g.capsule((s * rx * 0.28, ey + er * 1.3, ez - er * 0.6), (s * (ex + er * 0.4), ey + er * 1.0, ez + er * 1.4),
                      max(0.45, er * 0.6), max(0.4, er * 0.5), mat, 0.66, prio=3)
        g.eye((s * ex, ey, ez), er, val=eye_val, socket=0.25, facing=(s * 0.75, 0.1, -0.65), slit=slit)
    # 콧구멍
    for s in (-1, 1):
        g.dot((s * rt * 0.45, tip[1] + rt * sq * 0.65, tip_z + 0.5), nostril[0], nostril[1], glow=nostril[2], prio=5)
    if cheeks:
        for s in (-1, 1):
            g.cone((s * rx * 0.8, -ry * 0.15, cz + rz * 0.3), (s * 0.8, 0.1, 1), rx * 0.55, max(0.4, rx * 0.16), 'horn',
                   0.38, 0.85, prio=3)
    return tip_z, palate, rt


def _d_jaw(g, ctx, mat='scale', snout=1.0, throat='core', chin=0, teeth=True):
    """아래턱: 경첩(pivot 바로 뒤) → 앞 d.  위가 파인 입바닥(어두운 입 + 목구멍 빛), 아랫니가 위로."""
    w, h, d = ctx.size
    hs = _size(ctx, 'head') or (w, h * 3, d * 2)
    L = d + 0.4
    r0 = min(w / 2, hs[0] * 0.4)
    r1 = max(0.85, hs[0] / 2 * 0.42 * snout * 0.95)
    sq = max(0.35, min(1.0, (h / 2 + 0.2) / r0))
    cy = -h * 0.12
    g.sweep([(0, cy, 1.0), (0, cy - h * 0.12, -L * 0.45), (0, cy, -L + r1)], r0, r1, mat, 0.45, sq=(1, sq, 1),
            vfn=lambda t, dd, p: 0.42 + 0.06 * t + 0.08 * (1 - dd))
    top = cy + r0 * sq

    def rr(z):
        t = max(0.0, min(1.0, (1.0 - z) / (L + 1.0)))
        return r0 + (r1 - r0) * t
    g.carve(lambda x, y, z: y > top - 0.55 and abs(x) < rr(z) * 0.62 and -L + 0.9 < z < 0.8)
    g.paint(lambda x, y, z, n, m, v: ('mouth', 0.25) if (n[1] > 0 and abs(x) < rr(z) * 0.66 and z < 0.9 and
                                                         y > top - 1.4) else None, [mat])
    g.paint(lambda x, y, z, n, m, v: ('belly', 0.5) if n[1] < 0 else None, [mat])
    if throat:
        g.dot((0, top - 0.7, 0.4), throat, 0.6, glow=True, prio=5)
    if teeth:
        n_t = max(2, int(L / 1.7))
        for s in (-1, 1):
            g.teeth((s * r0 * 0.72, top - 0.25, 0.0), (s * r1 * 0.7, top - 0.25, -L + 0.9), n_t, 0.45 + h * 0.15,
                    r=0.28, direction=(0, 1, 0))
    for k in range(chin):
        z = -L * (0.25 + 0.5 * k / max(1, chin - 1)) if chin > 1 else -L * 0.4
        g.cone((0, cy - r0 * sq * 0.9, z), (0, -1, 0.6), 1.0 + h * 0.3, 0.4, 'horn', 0.35, 0.85, prio=3)
    return top, L, r0, r1


def _d_horns(g, ctx, length=None, r=None, spread=0.45, rise=0.55, curl=(0.3, -0.25, 0.15), mat='horn', rings=0.0,
             tip_mat=None, small=0):
    """뿔 한 쌍: 머리 꼭대기 뒤쪽에서 뒤(+Z)·위로 휘어 나간다.  뿌리 혹은 두개골에 박힘."""
    w, h, d = ctx.size
    L = length or max(w * 0.55, h * 1.2)
    rr = r or max(0.55, w * 0.1)
    for s in (-1, 1):
        base = (s * w * 0.22, -h * 0.3, 0.0)
        g.blob(base, rr * 1.25, mat, 0.32)
        g.horn(base, (s * spread, rise, 1.0), L, rr, curl=(s * curl[0] * L, curl[1] * L, curl[2] * L), mat=mat,
               val=0.38, rings=rings, tip_mat=tip_mat)
        for k in range(small):
            b = (s * w * (0.36 + 0.1 * k), -h * 0.45, d * 0.2 + k * 0.6)
            g.cone(b, (s * 0.7, 0.5, 1), L * (0.35 - 0.08 * k), rr * 0.55, mat, 0.4, 0.85)


def _d_wing(g, ctx, bone='bone', mem='membrane', br=None, sag=0.18, tatter=0, mem_fn=None, claw='claw',
            spur=None):
    """날개(XZ 평면): 어깨(pivot) → 팔꿈치 → 손목이 앞전(−Z)을 따라 ctx.out 쪽으로, 손가락뼈 3개가 뒤로 부채꼴,
    그 사이 막은 한 겹(가장자리는 얕게 물어뜯긴 호).  돌려주는 값 = (wrist, tips, lead)."""
    w, h, d = ctx.size
    o = ctx.out
    br = br or max(0.45, 0.3 + 0.035 * w + 0.12 * h)
    lead = -d * 0.32
    root = (0.0, 0.2, lead * 0.4)
    elbow = (o * w * 0.24, 0.55, lead - d * 0.06)
    wrist = (o * w * 0.48, 0.75, lead)
    g.limb([root, elbow, wrist], [br * 1.55, br * 1.25, br], bone, 0.5, knob=1.18)
    tips = [(o * w * 1.0, lead + d * 0.12), (o * w * 0.84, lead + d * 0.78), (o * w * 0.56, lead + d * 1.05)]
    hip = (o * w * 0.1, lead + d * 0.92)
    for k, (tx, tz) in enumerate(tips):
        mid = ((wrist[0] + tx) / 2, 0.95, (wrist[2] + tz) / 2)
        g.sweep([wrist, mid, (tx, 0.25, tz)], br * 0.85, br * 0.42, bone, 0.56 - 0.04 * k)
    if claw:
        g.cone(wrist, (o * 0.25, 0.35, -1), 0.9 + w * 0.06, br * 0.75, claw, 0.3, 0.8, prio=3)
    if spur:
        for (tx, tz) in tips[:1]:
            g.cone((tx, 0.25, tz), (o * 1, 0.1, -0.2), 0.8 + w * 0.04, br * 0.45, spur, 0.35, 0.85, prio=3)
    poly = [(root[0], root[2] - 0.3), (wrist[0], wrist[2] - br * 0.4)] + tips + [hip, (0.0, hip[1] * 0.85)]
    chain = tips + [hip]
    bites = _bites(poly, chain, sag)
    for k in range(tatter):
        a_, b_ = chain[k % (len(chain) - 1)], chain[k % (len(chain) - 1) + 1]
        t = 0.2 + 0.6 * h2(k, 3, g.seed + 71)
        p = (a_[0] + (b_[0] - a_[0]) * t, a_[1] + (b_[1] - a_[1]) * t)
        rad = 0.5 + 0.5 * h2(k, 5, g.seed + 71) * (1 + w * 0.05)
        bites.append((p[0], p[1], rad))

    def inside(x, z):
        return _poly_in(poly, x, z) and all(math.hypot(x - bx, z - bz) > R for bx, bz, R in bites)
    xs, zs = [q[0] for q in poly], [q[1] for q in poly]

    def vf(u, v, w_, e):
        if mem_fn:
            r_ = mem_fn(u, v, e)
            if r_ is not None:
                return r_
        return 0.44 + 0.2 * abs(u) / w - (0.12 if e < 0.6 else 0.0)
    g.slab2d(inside, (min(xs), min(zs)), (max(xs), max(zs)), 'xz', depth=0.0, half=0.0, mat=mem, vfn=vf, prio=1)
    return wrist, tips, lead


def _chain_k(name):
    try:
        return int(name.rsplit('_', 1)[1])
    except (IndexError, ValueError):
        return 0


def _d_tail(g, ctx, mat='scale', spikes=1, spike_mat='horn', tip=None, belly=True, sq=1.0, spike_at=(0.6,)):
    """꼬리 마디: 앞면(pivot)에서 다음 마디 pivot 까지(마지막은 끝으로 가늘게).  앞 끝은 앞 마디 안으로 둥글게 겹침."""
    w, h, d = ctx.size
    k = _chain_k(ctx.name)
    nxt = f'tail_{k + 1}'
    r0 = (w + h) / 4 * 1.08
    if ctx.part_def(nxt):
        ns = _size(ctx, nxt)
        end = ctx.offset_to(nxt)
        r1 = (ns[0] + ns[1]) / 4 * 1.08
        last = False
    else:
        end = (0.0, -0.3, d)
        r1 = max(0.45, r0 * 0.32)
        last = True
    pts = [(0, 0, -0.5), (end[0] * 0.5, end[1] * 0.4, end[2] * 0.5), end]
    g.sweep(pts, r0, r1, mat, 0.5, sq=(1, sq, 1), vfn=lambda t, dd, p: 0.46 + 0.1 * (1 - dd))
    if belly:
        g.paint(lambda x, y, z, n, m, v: ('belly', 0.5) if n[1] < 0 else None, [mat])
    for t in spike_at[:spikes]:
        r = r0 + (r1 - r0) * t
        p = _lerp3((0, 0, 0), end, t)
        g.cone((0, p[1] + r * sq * 0.8, p[2]), (0, 1, 1.1), r * 1.0 + 0.4, max(0.4, r * 0.3), spike_mat, 0.35, 0.85,
               prio=3)
    if last and tip:
        tip(g, end, r1)
    return end, r0, r1


def _paw(g, c, R, mat, claw, toes=3):
    g.blob(c, (R * 1.0, R * 0.55, R * 1.15), mat, 0.42)
    for k in range(toes):
        t = k - (toes - 1) / 2
        g.cone((c[0] + t * R * 0.6, c[1] - R * 0.1, c[2] - R * 0.8), (t * 0.3, -0.4, -1), R * 0.9 + 0.3,
               max(0.28, R * 0.32), claw, 0.3, 0.8, prio=3)


def _d_legs4(g, ctx, mat='scale', claw='claw', R=None, splay=1.0, toes=3):
    """네 발(pivot 중심, 땅 = y −pivot): 앞다리(팔꿈치 뒤로), 뒷다리(굵은 허벅지, 무릎 앞 · 발목 뒤), 발톱은 앞으로."""
    w, h, d = ctx.size
    gy = -ctx.pivot[1] * 16
    B = ctx.offset_to('body') or (0, h / 2, 0)
    bs = _size(ctx, 'body') or (w, h, d)
    bx, by, bz = bs[0] / 2, bs[1] / 2, bs[2] / 2
    R = R or max(0.7, bs[0] * 0.11)
    ay = B[1] - by * 0.15
    for s in (-1, 1):
        zf = B[2] - bz * 0.5
        S0 = (s * bx * 0.6, ay, zf)
        E = (s * bx * 0.86 * splay, ay + (gy - ay) * 0.5, zf + R * 1.1)
        W = (s * bx * 0.8 * splay, gy + R * 1.0, zf - R * 0.2)
        g.blob(S0, (R * 1.3, R * 1.6, R * 1.4), mat, 0.5)
        g.limb([S0, E, W], [R * 1.3, R * 0.95, R * 0.75], mat, 0.48, knob=1.12)
        _paw(g, (W[0], gy + R * 0.5, W[2] - R * 0.5), R, mat, claw, toes)
        zh = B[2] + bz * 0.5
        H0 = (s * bx * 0.62, ay + by * 0.1, zh)
        K = (s * bx * 0.92 * splay, ay + (gy - ay) * 0.38, zh - R * 1.4)
        A = (s * bx * 0.86 * splay, gy + (ay - gy) * 0.3, zh + R * 1.1)
        F = (s * bx * 0.82 * splay, gy + R * 0.8, zh - R * 0.1)
        g.blob((H0[0], H0[1] - R * 0.6, H0[2] - R * 0.3), (R * 1.55, R * 2.0, R * 1.8), mat, 0.5)
        g.limb([H0, K, A, F], [R * 1.45, R * 1.0, R * 0.75, R * 0.7], mat, 0.48, knob=1.12)
        _paw(g, (F[0], gy + R * 0.5, F[2] - R * 0.5), R, mat, claw, toes)


def _d_legs2(g, ctx, mat='scale', claw='claw', R=None, thigh=None):
    """두 발(엉덩이 pivot 에서 아래로, 발바닥 = y −h): 허벅지 · 앞으로 꺾인 무릎 · 뒤로 꺾인 발목 · 맹금 발톱."""
    w, h, d = ctx.size
    R = R or max(0.5, w * 0.11)
    for s in (-1, 1):
        x = s * w * 0.3
        Hp = (x, -0.2, 0.3)
        K = (x + s * 0.3, -h * 0.38, -R * 1.2)
        A = (x + s * 0.2, -h * 0.75, R * 0.9)
        F = (x, -h + R * 0.5, -R * 0.2)
        g.blob((x, -h * 0.14, 0.1), (R * 1.4, R * 1.8, R * 1.5), thigh or mat, 0.5)
        g.limb([Hp, K, A, F], [R * 1.3, R * 0.9, R * 0.65, R * 0.6], mat, 0.48, knob=1.1)
        for k in (-1, 0, 1):
            g.horn((F[0] + k * R * 0.55, F[1], F[2] - R * 0.3), (k * 0.35, -0.2, -1), R * 1.6 + 0.3, max(0.28, R * 0.38),
                   curl=(0, -R * 0.9, 0), mat=claw, val=0.3)
        g.horn((F[0], F[1], F[2] + R * 0.4), (0, -0.2, 1), R * 1.2 + 0.2, max(0.26, R * 0.32), curl=(0, -R * 0.7, 0),
               mat=claw, val=0.3)


# ───────────────────────────── moss_drakeling (이끼 새끼용) ─────────────────────────────
# 갓 깬 새끼용: 큰 머리 · 큰 호박색 눈, 등의 이끼 쿠션(고사리 · 꽃 · 발광 봉오리), 반투명 연두 날개막, 짧은 뿔, 꼬리 끝 이끼 술.

def _mossling_body(g, ctx):
    _d_body(g, ctx, plates=4, spine=0.45, spikes=0)
    g.moss_paint(coverage=0.72, mats=['scale'], scale=3.0, up_min=0.3, depth=2)
    g.clumps(5, 1.2, 'moss', 0.56, mats=['moss'])
    g.sprinkle(['moss'], sprouts=4, flowers=3, glow_buds=3, hang=4, hang_len=(0.8, 2.0))


def _mossling_head(g, ctx):
    _d_head(g, ctx, snout=0.85, eye_r=1.05, eye_val=0.48, cheeks=False, cranium=1.06)
    g.moss_paint(coverage=0.35, mats=['scale'], scale=2.0, up_min=0.65, depth=1)


def _moss_tuft(g, end, r):
    g.blob((end[0], end[1] + 0.2, end[2] + 0.4), (1.5, 1.2, 1.6), 'moss', 0.55, lump=0.3, lump_scale=0.9)
    g.sprinkle(['moss'], sprouts=2, flowers=1, glow_buds=1, hang=3, hang_len=(0.8, 1.8))


def _mossling_wing(g, ctx):
    _d_wing(g, ctx, bone='horn', sag=0.2, mem_fn=lambda u, v, e: 0.52 + 0.18 * abs(u) / ctx.size[0] -
            (0.14 if e < 0.6 else 0.0))


def moss_drakeling(look, name, part, ctx):
    _ramps(ctx, {
        'scale': _hx('#0f1a0b', '#1c2e12', '#2f4a1e', '#45682a', '#5f8a33', '#80a84a', '#a6c96a', '#cfe39a'),
        'belly': _hx('#3a3a1c', '#5c5a2c', '#857f42', '#aaa25c', '#c9c27e', '#e2dca6'),
        'membrane': _hx('#2a3e16', '#4a6a24', '#6f9638', '#97bd56', '#bede82', '#dff2b2'),
        'horn': _hx('#2c2418', '#54452c', '#7e6a44', '#a8946a', '#cfc096', '#ece2c4'),
        'eye': _hx('#6e3208', '#c47012', '#f8b02c', '#ffc24a', '#ffe8a8', '#ffffff'),
        'core': _hx('#6e3208', '#c47012', '#f8b02c', '#ffd27a', '#fff0c8'),
        'glow': _hx('#4a6a08', '#8ab814', '#c8e83a', '#eaff8a', '#faffd8'),
    })
    return _run(ctx, name, {
        'body': (_mossling_body, _V(15)),
        'neck': (lambda g, c: _d_neck(g, c, spikes=0), _Vneck(9)),
        'head': (_mossling_head, _V(12)),
        'jaw': (lambda g, c: _d_jaw(g, c, snout=0.85), _V(13, of='head')),
        'horns': (lambda g, c: _d_horns(g, c, length=3.0, r=0.6, curl=(0.2, -0.15, 0.2)), _V(13, of='head')),
        'wing_left': (_mossling_wing, _V(17)), 'wing_right': (_mossling_wing, _V(17)),
        'tail_1': (lambda g, c: _d_tail(g, c, spikes=0), _V(10, of='tail_1')),
        'tail_2': (lambda g, c: _d_tail(g, c, spikes=0, tip=_moss_tuft), _V(10, of='tail_1')),
        'legs': (lambda g, c: _d_legs4(g, c), _V(14)),
    })


# ───────────────────────────── bog_drake (늪 드레이크) ─────────────────────────────
# 낮고 넓은 악어형 드레이크: 등의 골판(세 줄), 따개비 무리, 늪 이끼 · 늘어진 수초, 납작한 주둥이에서 맺히는 산성 침(연두 발광),
# 작고 찢어진 날개.

def _barnacles(g, pts, r=0.7):
    for p in pts:
        g.cylinder(p, (p[0], p[1] + r * 0.9, p[2]), r, r * 0.65, 'barnacle', 0.6, prio=4, hollow=r * 0.3)
        g.dot((p[0], p[1] + r * 0.3, p[2]), 'mouth', 0.2, prio=5)


def _bog_body(g, ctx):
    rx, ry, rz = _d_body(g, ctx, plates=6, spine=0.0, spikes=0, flat=0.85)
    top = ry * 0.06 + ry * 0.94
    for x in (-rx * 0.38, 0.0, rx * 0.38):
        for k in range(5):
            z = -rz * 0.6 + rz * 1.2 * k / 4
            y = ry * 0.06 + ry * 0.94 * math.sqrt(max(0.0, 1 - (x / rx) ** 2 - (z / rz) ** 2))
            g.blob((x, y + 0.1, z), (0.75, 0.6, 0.95), 'scale', 0.7, prio=3)
    g.moss_paint(coverage=0.45, mats=['scale'], scale=3.5, up_min=0.4, depth=1)
    g.sprinkle(['moss'], hang=7, hang_len=(1.2, 3.2), flowers=2)
    _barnacles(g, [(rx * 0.6, top * 0.62, -rz * 0.3), (rx * 0.7, top * 0.45, rz * 0.1), (-rx * 0.55, top * 0.68, rz * 0.35),
                   (-rx * 0.72, top * 0.4, -rz * 0.15), (rx * 0.2, top * 0.95, rz * 0.55)])


def _bog_head(g, ctx):
    w, h, d = ctx.size
    tip_z, palate, rt = _d_head(g, ctx, snout=1.15, flat=0.8, eye_r=0.85, eye_val=0.5, cheeks=False,
                                eye_at=(w / 2 * 0.48, h / 2 * 0.8 * 0.95, d / 2 * 0.05), brow=True,
                                nostril=('glow', 0.5, True))
    # 주둥이 위 골판 혹 두 줄
    for s in (-1, 1):
        for k in range(3):
            z = tip_z + 1.5 + k * 1.6
            g.blob((s * rt * 0.45, palate + rt * 1.35, z), (0.5, 0.4, 0.6), 'scale', 0.7, prio=3)
    _barnacles(g, [(w / 2 * 0.6, h * 0.25, d * 0.3)], 0.55)
    g.moss_paint(coverage=0.3, mats=['scale'], scale=2.5, up_min=0.6)


def _drool(g, top, L, r0, r1, n=3):
    for k in range(n):
        z = -L * (0.25 + 0.55 * k / max(1, n - 1))
        x = (1 if k % 2 else -1) * (r0 + (r1 - r0) * (k / max(1, n - 1))) * 0.8
        y0 = top - 1.6
        g.capsule((x, y0, z), (x, y0 - 1.2 - 0.6 * (k % 2), z), 0.32, 0.26, 'glow', 0.55, glow=True, prio=5)
        g.dot((x, y0 - 1.6 - 0.6 * (k % 2), z), 'glow', 0.8, glow=True, prio=6)


def _bog_jaw(g, ctx):
    top, L, r0, r1 = _d_jaw(g, ctx, snout=1.15, throat='glow')
    _drool(g, top, L, r0, r1)
    g.streaks('glow', ['scale', 'belly'], density=0.18, length=(0.6, 1.6), val=0.55, glow=True)


def _bog_wing(g, ctx):
    _d_wing(g, ctx, bone='horn', sag=0.28, tatter=5,
            mem_fn=lambda u, v, e: 0.38 + 0.18 * abs(u) / ctx.size[0] - (0.12 if e < 0.6 else 0.0))


def _bog_tail(g, ctx):
    w, h, d = ctx.size
    last = not ctx.part_def(f'tail_{_chain_k(ctx.name) + 1}')
    _d_tail(g, ctx, spikes=0 if last else 2, spike_mat='scale', spike_at=(0.3, 0.75), sq=0.9)
    if not last:
        g.moss_paint(coverage=0.35, mats=['scale'], scale=2.5, up_min=0.5)


def bog_drake(look, name, part, ctx):
    _ramps(ctx, {
        'scale': _hx('#081210', '#0e1a14', '#16281e', '#1f3a2c', '#2d5038', '#3f6a4a', '#5a8a5e', '#86a86a'),
        'belly': _hx('#2a2a16', '#44422a', '#62603c', '#80804e', '#a0a068', '#c0c088'),
        'membrane': _hx('#0c1a14', '#183024', '#28483a', '#3c6450', '#5a8668', '#86a86a'),
        'horn': _hx('#14140e', '#2a2a1e', '#46442e', '#646044', '#86805e', '#aaa480'),
        'barnacle': _hx('#4a4438', '#7a7262', '#a8a08c', '#cec8b4', '#ece8dc'),
        'eye': _hx('#3a5a08', '#6a9a12', '#9ac828', '#b6e04a', '#d6f48a', '#f2ffd0'),
        'glow': _hx('#3a5a08', '#6a9a12', '#9ac828', '#b6e04a', '#d6f48a', '#f2ffd0'),
        'core': _hx('#3a5a08', '#6a9a12', '#9ac828', '#b6e04a', '#d6f48a'),
    })
    return _run(ctx, name, {
        'body': (_bog_body, _V(15)),
        'neck': (lambda g, c: _d_neck(g, c, spikes=0), _Vneck(10)),
        'head': (_bog_head, _V(13)),
        'jaw': (_bog_jaw, _V(13, of='head')),
        'horns': (lambda g, c: _d_horns(g, c, length=3.4, r=0.65, spread=0.8, rise=0.2, curl=(0.15, 0.1, 0.1)),
                  _V(13, of='head')),
        'wing_left': (_bog_wing, _V(17)), 'wing_right': (_bog_wing, _V(17)),
        'tail_1': (_bog_tail, _V(10, of='tail_1')), 'tail_2': (_bog_tail, _V(10, of='tail_1')),
        'tail_3': (_bog_tail, _V(10, of='tail_1')),
        'legs': (lambda g, c: _d_legs4(g, c, splay=1.25, R=1.25), _V(14)),
    })


# ───────────────────────────── ember_drake (잿불 드레이크) ─────────────────────────────
# 현무암 비늘 사이 갈라진 틈으로 쇳물이 빛난다.  뒤로 휜 흑요석 뿔, 불씨가 맺힌 막 가장자리, 쇳물 목구멍, 꼬리 끝 잿불 덩어리.

def _lava_cracks(g, mats=('scale',), width=0.035, scale=4.0, seed=0):
    g.cracks(list(mats), mat='lava', width=width, scale=scale, val=0.62, glow=True, seed=seed)


def _ember_body(g, ctx):
    _d_body(g, ctx, plates=6, spine=0.9, spikes=5)
    _lava_cracks(g, ('scale', 'belly'), 0.03, 7.0)


def _ember_head(g, ctx):
    _d_head(g, ctx, snout=1.0, eye_val=0.55, nostril=('lava', 0.7, True), throat='lava')


def _ember_jaw(g, ctx):
    _d_jaw(g, ctx, throat='lava', chin=2)
    _lava_cracks(g, ('scale',), 0.035, 4.0, seed=5)


def _ember_wing(g, ctx):
    w = ctx.size[0]
    _d_wing(g, ctx, bone='scale', sag=0.2, tatter=3, spur='horn',
            mem_fn=lambda u, v, e: ('lava', 0.55, True) if e < 0.6 else 0.36 + 0.2 * abs(u) / w)


def _ember_lump(g, end, r):
    c = (end[0], end[1], end[2] + 0.6)
    g.blob(c, 1.8, 'lava', 0.6, glow=True, lump=0.25, lump_scale=1.0, prio=3)
    for k, dvec in enumerate(((0, 1, 0.3), (1, 0.2, 0.6), (-1, 0.2, 0.6), (0, -0.6, 1), (0, 0.4, 1))):
        g.cone(vadd(c, vmul(vnorm(dvec), 1.2)), dvec, 1.6 + 0.4 * (k % 2), 0.55, 'horn', 0.35, 0.7, prio=4)


def _ember_tail(g, ctx):
    _d_tail(g, ctx, spikes=1, tip=_ember_lump)


def _ember_legs(g, ctx):
    _d_legs4(g, ctx, claw='horn')


def ember_drake(look, name, part, ctx):
    _ramps(ctx, {
        'scale': _hx('#0a0606', '#140c0a', '#1e1410', '#2e1e18', '#3e2a22', '#52382c', '#6a4a3a', '#8a6450'),
        'belly': _hx('#2e1410', '#4a2016', '#6a301c', '#8a4424', '#a0522a', '#c07040'),
        'membrane': _hx('#1a0806', '#34100a', '#5a1a10', '#7e2a16', '#a0401e', '#c86028'),
        'horn': _hx('#050407', '#0e0b12', '#1a1520', '#2a2232', '#3e3448', '#5a4c66', '#8070a0'),
        'eye': _hx('#7a2a06', '#d05a0e', '#ff8a2a', '#ffc070', '#fff0c8', '#ffffff'),
    })
    return _run(ctx, name, {
        'body': (_ember_body, _V(15)),
        'neck': (lambda g, c: _d_neck(g, c, spikes=2), _Vneck(9)),
        'head': (_ember_head, _V(12)),
        'jaw': (_ember_jaw, _V(13, of='head')),
        'horns': (lambda g, c: _d_horns(g, c, length=8.5, r=1.1, spread=0.5, rise=0.35, curl=(0.15, -0.35, 0.1),
                                        rings=1.6, small=1), _V(13, of='head')),
        'wing_left': (_ember_wing, _V(17)), 'wing_right': (_ember_wing, _V(17)),
        'tail_1': (_ember_tail, _V(10, of='tail_1')), 'tail_2': (_ember_tail, _V(10, of='tail_1')),
        'tail_3': (_ember_tail, _V(10, of='tail_1')),
        'legs': (_ember_legs, _V(12.5)),
    })


# ───────────────────────────── frost_wyvern (서리 와이번) ─────────────────────────────
# 두 발 와이번: 하늘색 비늘에 서리, 등줄기의 얼음 수정, 몸의 3배인 얼음 막 날개(서리 낀 가장자리 · 고드름), 얼음 송곳 꼬리 끝.

def _frost(g, mats, coverage=0.55, up_min=0.45, scale=2.5):
    g.moss_paint(coverage=coverage, mat='frost', val=0.6, mats=list(mats), scale=scale, up_min=up_min, depth=1)


def _fw_body(g, ctx):
    rx, ry, rz = _d_body(g, ctx, plates=4, spine=0.45, spikes=0)
    _frost(g, ['scale'])
    for k, (z, s) in enumerate(((-rz * 0.35, 1.0), (rz * 0.15, 0.8), (rz * 0.55, 0.6))):
        y = ry * 0.06 + ry * 0.94 * math.sqrt(max(0.0, 1 - (z / rz) ** 2))
        g.crystals((0, y - 0.3, z), (0, 1, 0.45), n=2, size=2.2 * s, r=0.55, mat='ice', seed=k)


def _fw_head(g, ctx):
    _d_head(g, ctx, snout=0.9, eye_val=0.55, throat='core', cheeks=True)
    _frost(g, ['scale'], 0.45, 0.6, 2.0)


def _fw_wing(g, ctx):
    w = ctx.size[0]
    wrist, tips, lead = _d_wing(g, ctx, bone='bone', sag=0.2,
                                mem_fn=lambda u, v, e: ('ice', 0.55) if e < 0.6 else 0.36 + 0.22 * abs(u) / w)
    for (tx, tz) in tips:
        g.cone((tx, 0.0, tz), (0, -1, 0.2), 1.2, 0.35, 'ice', 0.6, 0.95, prio=3)
    g.cone((wrist[0], wrist[1] - 0.4, wrist[2]), (0, -1, 0), 1.4, 0.4, 'ice', 0.6, 0.95, prio=3)


def _icicle_tip(g, end, r):
    g.cone((end[0], end[1], end[2] - 0.2), (0, -0.05, 1), 4.0, 0.9, 'ice', 0.45, 0.95, prio=3)
    for s in (-1, 1):
        g.cone((end[0], end[1], end[2] + 0.4), (s, 0.15, 0.7), 1.8, 0.45, 'ice', 0.5, 0.95, prio=3)


def _fw_tail(g, ctx):
    _d_tail(g, ctx, spikes=1, spike_mat='ice', tip=_icicle_tip)
    _frost(g, ['scale'], 0.5, 0.5, 1.6)


def frost_wyvern(look, name, part, ctx):
    _ramps(ctx, {
        'scale': _hx('#101824', '#16202e', '#22364c', '#2e4a66', '#4a7296', '#6a9ac0', '#9cc4e0', '#cfe8f8'),
        'belly': _hx('#5a7088', '#7e96ac', '#a2bad0', '#c4d8e8', '#e0eef8', '#f6fbff'),
        'membrane': _hx('#2e5a7a', '#4a80a4', '#6aa6c8', '#92cae2', '#bce6f4', '#e4f8ff'),
        'ice': _hx('#3a7aa0', '#5aa0c4', '#80c6e2', '#a8e2f4', '#d2f4ff', '#ffffff'),
        'bone': _hx('#22324a', '#344c6a', '#4a6a8c', '#6a8cb0', '#94b4d2', '#c4dcf0'),
        'horn': _hx('#3a4a5e', '#5a7090', '#7e98b8', '#a6c0dc', '#cce0f2', '#eef8ff'),
        'eye': _hx('#1a6a80', '#2aa8c0', '#5ad8ec', '#8af0ff', '#c8faff', '#ffffff'),
        'core': _hx('#1a6a80', '#2aa8c0', '#5ad8ec', '#8af0ff', '#c8faff', '#ffffff'),
    })
    return _run(ctx, name, {
        'body': (_fw_body, _V(14)),
        'neck': (lambda g, c: (_d_neck(g, c, spikes=1, spike_mat='ice'), _frost(g, ['scale'], 0.5, 0.5, 1.6)),
                 _Vneck(10)),
        'head': (_fw_head, _V(11)),
        'jaw': (lambda g, c: _d_jaw(g, c, snout=0.9), _V(13, of='head')),
        'horns': (lambda g, c: _d_horns(g, c, length=3.6, r=0.55, curl=(0.2, -0.2, 0.15), tip_mat='ice'),
                  _V(13, of='head')),
        'wing_left': (_fw_wing, _V(20)), 'wing_right': (_fw_wing, _V(20)),
        'tail_1': (_fw_tail, _V(10, of='tail_1')), 'tail_2': (_fw_tail, _V(10, of='tail_1')),
        'tail_3': (_fw_tail, _V(10, of='tail_1')),
        'legs': (lambda g, c: _d_legs2(g, c, claw='ice'), _V(12)),
    })


# ───────────────────────────── clockwork_wyvern (태엽 와이번) ─────────────────────────────
# 놋쇠 판 + 리벳의 기계 와이번: 등의 수평 태엽 톱니(spin), 머리 앞 렌즈 눈(광선 발사구), 시계판 무늬 금속 날개,
# 청록 전기 맥, 사슬 같은 꼬리 마디와 꼬리 끝 칼날, 피스톤 다리.

def _cw_body(g, ctx):
    w, h, d = ctx.size
    hx, hy, hz = w / 2, h / 2, d / 2
    g.rbox((-hx + 0.4, -hy + 0.3, -hz + 0.4), (hx - 0.4, hy - 0.3, hz - 0.4), 'iron', 0.32, bevel=1.0)
    g.plate((-hx + 0.6, hy - 1.6, -hz + 0.5), (hx - 0.6, hy + 0.1, hz - 1.2), 'brass', 0.55, rivet_mat='brass',
            rivet_step=2.6, face=(0, 1, 0), bevel=0.6)
    for s in (-1, 1):
        g.plate((s * (hx - 0.9), -hy + 0.9, -hz + 1.0), (s * (hx + 0.1), hy - 1.1, hz - 1.6), 'brass', 0.48,
                rivet_mat='brass', rivet_step=2.6, face=(s, 0, 0), bevel=0.5)
        g.gear((s * (hx + 0.25), -0.2, 1.0), 1.5, teeth=8, axis='x', thick=0.5, mat='copper', val=0.6)
        g.capsule((s * (hx + 0.15), -hy + 0.7, -hz + 1.2), (s * (hx + 0.15), -hy + 0.7, hz - 1.6), 0.25, 0.25, 'rune',
                  0.7, glow=True, prio=4)
    g.rbox((-1.4, -hy - 0.4, -hz + 1.2), (1.4, -hy + 0.6, hz - 1.0), 'copper', 0.45, bevel=0.4)       # 용골
    g.rbox((-1.8, -1.2, -hz - 0.1), (1.8, 1.4, -hz + 0.6), 'rune', 0.6, glow=True, prio=3)             # 가슴 화로
    for x in (-0.8, 0.8):
        g.rbox((x - 0.2, -1.3, -hz - 0.4), (x + 0.2, 1.5, -hz + 0.2), 'iron', 0.5, prio=4)
    wl = ctx.offset_to('wing_left')
    if wl:
        for s in (-1, 1):
            g.blob((s * abs(wl[0]) * 0.9, wl[1] - 0.2, wl[2]), 1.2, 'brass', 0.65, prio=4)
    g.ring((0, 0, hz - 0.2), 1.4, 0.4, axis='z', mat='brass', val=0.6)


def _cw_spring(g, ctx):
    g.gear((0, 0, 0), 3.0, teeth=10, axis='y', thick=1.0, mat='brass', val=0.55, hole=0.0, spokes=0)
    pts = []
    for k in range(17):
        a = k / 16 * 3 * math.pi
        r = 0.8 + 1.5 * k / 16
        pts.append((math.cos(a) * r, 0.75, math.sin(a) * r))
    g.sweep(pts, 0.28, 0.28, 'iron', 0.6, smooth=False, prio=3)
    g.cylinder((0, -1.6, 0), (0, 1.0, 0), 0.6, 0.6, 'copper', 0.6, prio=4)
    g.rbox((-0.3, 1.0, -1.6), (0.3, 1.5, 1.6), 'brass', 0.7, prio=4)                                  # 감개 손잡이


def _cw_neck(g, ctx):
    w, h, d = ctx.size
    pts = [(0, -h * 0.15, w * 0.3), (0, h * 0.45, -d * 0.42), (0, h, -d)]
    g.sweep(pts, w * 0.32, w * 0.28, 'iron', 0.4)
    g.capsule((0, -h * 0.15 - w * 0.3, w * 0.2), (0, h - w * 0.32, -d), 0.25, 0.25, 'rune', 0.7, glow=True, prio=3)
    for k in range(4):
        t = (k + 0.5) / 4
        p = _lerp3(pts[0], pts[1], t * 2) if t < 0.5 else _lerp3(pts[1], pts[2], t * 2 - 1)
        g.blob(p, (w * 0.5, w * 0.46, w * 0.36), 'brass', 0.52 + 0.08 * (k % 2), prio=2)
        g.dot((0, p[1] + w * 0.5, p[2]), 'brass', 0.85, prio=4)


def _cw_head(g, ctx):
    w, h, d = ctx.size
    J = ctx.offset_to('jaw') or (0.0, -1.5, -1.0)
    js = _size(ctx, 'jaw') or (4, 2, 3)
    tip_z = J[2] - js[2] - 0.3
    palate = J[1] + js[1] * 0.5
    g.rbox((-w / 2, palate, -d * 0.2), (w / 2, h / 2, d / 2), 'brass', 0.55, bevel=0.8)
    g.rbox((-w * 0.32, palate, tip_z), (w * 0.32, h * 0.28, -d * 0.1), 'brass', 0.5, bevel=0.5)
    g.rbox((-w * 0.3, palate - 0.2, tip_z + 0.5), (w * 0.3, palate + 0.3, J[2] + 0.8), 'mouth', 0.2, prio=3)
    g.dot((0, palate + 0.2, J[2] + 0.9), 'rune', 0.7, glow=True, prio=4)
    for s in (-1, 1):
        g.plate((s * w * 0.18, h * 0.3, -d * 0.25), (s * (w / 2 + 0.2), h / 2 + 0.25, d * 0.3), 'iron', 0.45,
                rivet_mat='brass', rivet_step=1.2, face=(0, 1, 0), bevel=0.3)
        g.rbox((s * (w / 2 - 0.1), -0.2, -d * 0.15), (s * (w / 2 + 0.3), 0.4, d * 0.15), 'rune', 0.7, glow=True, prio=4)
        g.cone((s * w * 0.35, h / 2, d * 0.35), (s * 0.4, 0.5, 1), 2.4, 0.45, 'iron', 0.45, 0.8, prio=3)   # 안테나 뿔
        g.teeth((s * w * 0.28, palate, tip_z + 0.5), (s * w * 0.28, palate, J[2] + 0.4), 3, 0.6, r=0.3,
                mat='blade', direction=(0, -1, 0))
    g.slab2d(lambda u, v: 0 <= v <= 1.6 - u * 0.25 and -d * 0.3 <= u <= d * 0.55, (-d * 0.3, 0), (d * 0.55, 1.8),
             'zy', depth=0.0, half=0.25, mat='iron', vfn=lambda u, v, w_, e: 0.5 + 0.15 * min(1.0, e))
    g.paint(lambda x, y, z, n, m, v: v - 0.18 if (n[1] > 0 and abs(z) < d * 0.25 and int(z / 0.8) % 2 == 0 and
                                                   abs(x) > 0.6) else None, ['brass'])


def _cw_jaw(g, ctx):
    w, h, d = ctx.size
    L = d + 0.4
    g.rbox((-w * 0.42, -h * 0.6, -L), (w * 0.42, h * 0.3, 1.0), 'iron', 0.45, bevel=0.4)
    g.carve(lambda x, y, z: y > -0.1 and abs(x) < w * 0.24 and -L + 0.6 < z < 0.4)
    g.paint(lambda x, y, z, n, m, v: ('mouth', 0.2) if n[1] > 0 and abs(x) < w * 0.26 else None, ['iron'])
    for s in (-1, 1):
        g.teeth((s * w * 0.32, h * 0.3, -L + 0.5), (s * w * 0.32, h * 0.3, 0.3), 3, 0.6, r=0.3, mat='blade',
                direction=(0, 1, 0))
        g.cylinder((s * w * 0.45, 0, 0.6), (s * (w * 0.45 + 0.5), 0, 0.6), 0.6, 0.6, 'brass', 0.65, prio=3)


def _cw_lens(g, ctx):
    g.cylinder((0, 0, 1.6), (0, 0, -0.6), 1.5, 1.5, 'brass', 0.55, hollow=0.95)
    g.cylinder((0, 0, 0.4), (0, 0, -0.2), 1.0, 1.0, 'eye', 0.6, prio=3)
    g.ring((0, 0, -0.7), 1.25, 0.3, axis='z', mat='copper', val=0.7)
    g.dot((0, 0, -0.4), 'eye', 0.95, glow=True, prio=5)


def _clockface(ctx, w, d, o):
    lead = -d * 0.32
    cx, cz = o * w * 0.55, lead + d * 0.45
    R = min(w * 0.22, d * 0.36)

    def f(u, v, e):
        if e < 0.6:
            return ('rune', 0.6, True)
        du, dv = u - cx, v - cz
        r = math.hypot(du, dv)
        if abs(r - R) < 0.4:
            return ('brass', 0.72)
        if r < R:
            a = math.atan2(dv, du)
            if r > R - 1.0 and abs(((a / (2 * math.pi) * 12) + 0.5) % 1.0 - 0.5) < 0.12:
                return ('brass', 0.82)
            hand1 = abs(math.sin(a - 0.7)) * r < 0.3 and math.cos(a - 0.7) > 0 and r < R * 0.85
            hand2 = abs(math.sin(a + 2.0)) * r < 0.3 and math.cos(a + 2.0) > 0 and r < R * 0.55
            if hand1 or hand2 or r < 0.5:
                return ('iron', 0.2)
            return 0.62
        return 0.4 + 0.15 * abs(u) / w
    return f


def _cw_wing(g, ctx):
    w, h, d = ctx.size
    _d_wing(g, ctx, bone='brass', claw='blade', br=0.55, sag=0.12, mem_fn=_clockface(ctx, w, d, ctx.out))


def _cw_blade_tip(g, end, r):
    c = (end[0], end[1], end[2])
    g.slab2d(lambda u, v: abs(u) <= 1.6 * (1 - abs(v - 2.2) / 2.2) and 0 <= v <= 4.4,
             (-1.8, c[2]), (1.8, c[2] + 4.6), 'xz', depth=c[1], half=0.25, mat='blade',
             vfn=lambda u, v, w_, e: ('rune', 0.65, True) if e < 0.5 else 0.6)


def _cw_tail(g, ctx):
    w, h, d = ctx.size
    k = _chain_k(ctx.name)
    nxt = f'tail_{k + 1}'
    end = ctx.offset_to(nxt) if ctx.part_def(nxt) else (0.0, -0.3, d)
    g.capsule((0, 0, -0.4), end, (w + h) / 4 * 0.6, (w + h) / 4 * 0.5, 'iron', 0.42)
    n = max(3, int(d / 1.2))
    for j in range(n):
        p = _lerp3((0, 0, 0.3), end, j / n)
        r = (w + h) / 4 * (1.05 - 0.2 * j / n)
        g.blob(p, (r, r, 0.55), 'brass' if j % 2 == 0 else 'copper', 0.55, prio=2)
    g.capsule((0, -0.5, 0), (end[0], end[1] - 0.5, end[2]), 0.2, 0.2, 'rune', 0.7, glow=True, prio=3)
    if not ctx.part_def(nxt):
        _cw_blade_tip(g, end, 0.5)


def _cw_legs(g, ctx):
    w, h, d = ctx.size
    R = 0.5
    for s in (-1, 1):
        x = s * w * 0.3
        Hp, K, A, F = (x, -0.2, 0.3), (x + s * 0.2, -h * 0.38, -0.8), (x + s * 0.1, -h * 0.75, 0.6), (x, -h + 0.3, 0)
        g.limb([Hp, K, A, F], [0.55, 0.45, 0.4, 0.4], 'iron', 0.45, knob=0)
        for J in (Hp, K, A):
            g.cylinder((J[0] - 0.55, J[1], J[2]), (J[0] + 0.55, J[1], J[2]), 0.75, 0.75, 'brass', 0.62, prio=3)
        g.capsule((x + s * 0.55, -h * 0.12, 0.6), (x + s * 0.5, -h * 0.55, -0.2), 0.32, 0.32, 'copper', 0.6, prio=3)
        for kk in (-1, 0, 1):
            g.cone((F[0] + kk * R * 0.6, F[1], F[2] - 0.3), (kk * 0.35, -0.25, -1), 1.3, 0.3, 'blade', 0.5, 0.85)
        g.cone((F[0], F[1], F[2] + 0.3), (0, -0.2, 1), 0.9, 0.28, 'blade', 0.5, 0.85)


def clockwork_wyvern(look, name, part, ctx):
    _ramps(ctx, {
        'brass': _hx('#2a1a08', '#4a3018', '#6e4a22', '#8a5a2a', '#b07c3a', '#d8a85a', '#ecc880', '#fae8b8'),
        'iron': _hx('#0e0c0a', '#1a1612', '#2a241e', '#3c342c', '#524840', '#6c6258', '#8c8478'),
        'copper': _hx('#2a120a', '#4e2414', '#76381e', '#9a4e2a', '#c06a3a', '#e09060'),
        'membrane': _hx('#2a1c10', '#3e2a18', '#5a3e22', '#76542e', '#94703e', '#b48e56'),
        'blade': _hx('#3a3e42', '#5e646a', '#868e96', '#b0b8c0', '#d8dee4', '#f4f8fa'),
        'rune': _hx('#0a4a44', '#14806e', '#2ab8a0', '#5ae0d0', '#a0f4ea', '#e6fffb'),
        'eye': _hx('#0a4a44', '#14806e', '#2ab8a0', '#5ae0d0', '#a0f4ea', '#e6fffb'),
    })
    return _run(ctx, name, {
        'body': (_cw_body, 0.7), 'mainspring': (_cw_spring, 0.55), 'neck': (_cw_neck, 0.6),
        'head': (_cw_head, 0.55), 'jaw': (_cw_jaw, 0.55), 'lens': (_cw_lens, 0.5),
        'wing_left': (_cw_wing, 0.8), 'wing_right': (_cw_wing, 0.8),
        'tail_1': (_cw_tail, 0.55), 'tail_2': (_cw_tail, 0.55), 'tail_3': (_cw_tail, 0.55),
        'legs': (_cw_legs, 0.55),
    })


# ───────────────────────────── void_drake (심연 고룡) ─────────────────────────────
# 가장 큰 네 발 고룡: 검은 비늘에 청록 스컬크 맥, 길게 휜 두 마디 목, 큰 뿔(발광 고리), 별빛 점 날개막,
# 꼬리 네 마디 끝마다 등가시.

def _sculk(g, mats=('scale',), width=0.03, scale=5.0, seed=0):
    g.cracks(list(mats), mat='core', width=width, scale=scale, val=0.6, glow=True, seed=seed)


def _void_body(g, ctx):
    _d_body(g, ctx, plates=7, spine=1.2, spikes=6, spike_len=4.0)
    _sculk(g, ('scale', 'belly'), 0.028, 9.0)


def _void_head(g, ctx):
    _d_head(g, ctx, snout=1.0, eye_r=1.3, eye_val=0.55, nostril=('core', 0.7, True), throat='core')


def _void_wing(g, ctx):
    w = ctx.size[0]

    def f(u, v, e):
        if e < 0.7:
            return ('core', 0.45, True)
        if h2(int(u * 1.3), int(v * 1.3), 919) < 0.03:
            return ('core', 0.8, True)
        return 0.38 + 0.22 * abs(u) / w
    _d_wing(g, ctx, bone='scale', sag=0.2, spur='horn', mem_fn=f)


def _void_tail(g, ctx):
    last = not ctx.part_def(f'tail_{_chain_k(ctx.name) + 1}')
    _d_tail(g, ctx, spikes=2 if last else 1, spike_at=(0.88, 0.45) if not last else (0.3, 0.65),
            tip=lambda g_, end, r: g_.cone(end, (0, 0.1, 1), 3.0, 1.0, 'horn', 0.35, 0.85, prio=3))


def _void_horns(g, ctx):
    _d_horns(g, ctx, length=11.0, r=1.5, spread=0.5, rise=0.45, curl=(0.1, -0.3, 0.05), rings=1.6, small=2)
    g.cracks(['horn'], mat='core', width=0.03, scale=2.2, val=0.6, glow=True)


def void_drake(look, name, part, ctx):
    _ramps(ctx, {
        'scale': _hx('#010203', '#020306', '#05090e', '#08121a', '#0c1c26', '#123842', '#1c4e58', '#2a6a72'),
        'belly': _hx('#04080c', '#08121a', '#0e1e28', '#163038', '#1e4048', '#2a5a62'),
        'membrane': _hx('#020407', '#050c12', '#0a1820', '#10262e', '#18363e', '#244a52'),
        'horn': _hx('#020304', '#06090c', '#0c1418', '#142228', '#1e343a', '#2e4c52', '#46706e'),
        'core': _hx('#0a3a38', '#127a72', '#1cb0a4', '#2fe0d0', '#8af6ec', '#e0fffb'),
        'eye': _hx('#0a3a38', '#127a72', '#1cb0a4', '#2fe0d0', '#8af6ec', '#e0fffb'),
    })
    neck = (lambda g, c: _d_neck(g, c, spikes=2), _Vneck(8.5))
    return _run(ctx, name, {
        'body': (_void_body, _V(13)),
        'neck_1': neck, 'neck_2': neck,
        'head': (_void_head, _V(11.5)),
        'jaw': (lambda g, c: _d_jaw(g, c, throat='core', chin=2), _V(11.5, of='head')),
        'horns': (_void_horns, _V(11.5, of='head')),
        'wing_left': (_void_wing, _V(15)), 'wing_right': (_void_wing, _V(15)),
        'tail_1': (_void_tail, _V(8, of='tail_1')), 'tail_2': (_void_tail, _V(8, of='tail_1')),
        'tail_3': (_void_tail, _V(8, of='tail_1')), 'tail_4': (_void_tail, _V(8, of='tail_1')),
        'legs': (lambda g, c: _d_legs4(g, c, claw='horn'), _V(12)),
    })


# ───────────────────────────── tunnel_wyrm (갱도 땅굴웜) ─────────────────────────────
# 돌 갑각 띠를 두른 원통 마디 몸, 광석 박힘, 갈라진 돌.  머리 앞면 전체가 이빨 고리로 둘러싼 둥근 아가리,
# 아래턱 집게 두 쌍, 퇴화한 작은 눈 두 점.

def _ore(g, mats=('stone',), seed=0, amount=0.8):
    sd = g.seed + 401 + seed
    g.paint(lambda x, y, z, n, m, v: ('ore', 0.75) if fbm3(x / 1.3, y / 1.3, z / 1.3, sd) > amount else None,
            list(mats))


def _wyrm_head(g, ctx):
    w, h, d = ctx.size
    R = w / 2
    g.blob((0, 0, 0.3), (R, h / 2, d / 2 + 0.3), 'skin', 0.45)
    g.plates((0, 0.3, 0.4), (R + 0.3, h / 2 + 0.2, d / 2), n=2, axis=2, mat='stone', val=0.55, lift=0.1,
             reverse=True, cut=lambda x, y, z: y < -h * 0.22)
    mr = R * 0.66
    zf = -d / 2
    g.carve(lambda x, y, z: x * x + y * y < mr * mr and z < zf + 2.6)
    g.paint(lambda x, y, z, n, m, v: ('mouth', 0.18 + 0.1 * math.hypot(x, y) / mr)
            if x * x + y * y < (mr + 0.5) ** 2 and z < zf + 3.2 else None)
    g.dot((0, 0, zf + 2.4), 'glow', 0.4, glow=True, prio=6)
    g.ring((0, 0, zf + 0.3), mr + 0.35, 0.6, axis='z', mat='flesh', val=0.45, prio=3)
    for k in range(10):
        a = 2 * math.pi * k / 10
        c, s = math.cos(a), math.sin(a)
        g.cone((c * (mr - 0.1), s * (mr - 0.1), zf + 0.6), (-c, -s, 0.55), mr * 0.62, 0.42, 'tooth', 0.55, 0.92, prio=4)
    for k in range(7):
        a = 2 * math.pi * (k + 0.5) / 7
        c, s = math.cos(a), math.sin(a)
        g.cone((c * (mr - 0.2), s * (mr - 0.2), zf + 1.9), (-c, -s, 0.4), mr * 0.45, 0.35, 'tooth', 0.5, 0.88, prio=4)
    for s in (-1, 1):
        g.dot((s * R * 0.62, h / 2 * 0.62, zf + 1.0), 'eye', 0.6, glow=True, prio=6)
    _ore(g)


def _wyrm_jaw(g, ctx):
    H = ctx.offset_to('head') or (0, 1.0, 5.0)
    hs = _size(ctx, 'head') or (10, 10, 8)
    mr = hs[0] / 2 * 0.66
    my, mz = H[1], H[2] - hs[2] / 2 + 0.3
    g.ring((0, my, mz), mr + 0.7, 0.85, axis='z', mat='stone', val=0.5, arc=(0.58, 0.92))
    for s in (-1, 1):
        g.horn((s * 2.0, my - mr - 0.3, mz), (s * 0.15, -0.15, -1), 4.2, 0.85, curl=(-s * 1.9, 1.0, 0), mat='claw',
               val=0.35, tip_mat='tooth')
        g.horn((s * (mr + 0.6), my - 0.8, mz + 0.2), (s * 0.3, 0, -1), 3.6, 0.75, curl=(-s * 1.7, 0.2, 0), mat='claw',
               val=0.38, tip_mat='tooth')
        g.spikes([(s * 1.6, my - mr - 0.1, mz - 2.0), (s * (mr + 0.1), my - 0.7, mz - 1.8)], (-s, 0.3, -0.3), 0.8, 0.28,
                 'tooth', 0.5, 0.85)


def _wyrm_seg(g, ctx):
    w, h, d = ctx.size
    rx, ry = w / 2, h / 2
    c = (0, 0, d / 2)
    g.blob(c, (rx, ry, d / 2 + 0.9), 'skin', 0.45)
    g.plates(c, (rx + 0.35, ry + 0.3, d / 2), n=2, axis=2, mat='stone', val=0.52, lift=0.12, groove=-0.28,
             cut=lambda x, y, z: y < -ry * 0.4)
    g.ring((0, 0, 0.35), (rx + ry) / 2 * 0.95, 0.5, axis='z', mat='stone', val=0.18)
    for s in (-1, 1):
        g.cone((s * rx * 0.9, ry * 0.25, d * 0.55), (s, 0.3, 0.4), 1.2, 0.5, 'stone', 0.45, 0.7, prio=3)
    g.cracks(['stone'], width=0.04, scale=4.0, dv=-0.3, seed=_chain_k(ctx.name))
    _ore(g, seed=_chain_k(ctx.name))


def _wyrm_tail(g, ctx):
    w, h, d = ctx.size
    g.sweep([(0, 0, -0.8), (0, -0.2, d * 0.5), (0, -0.4, d)], (w + h) / 4 * 1.05, 0.6, 'stone', 0.5,
            sq=(1, h / w, 1))
    g.paint(lambda x, y, z, n, m, v: ('skin', 0.45) if n[1] < 0 else None, ['stone'])
    g.bands(['stone'], axis=2, period=2.2, width=0.5, amount=-0.2)
    g.cone((0, -0.4, d - 0.2), (0, 0.05, 1), 2.6, 0.75, 'horn', 0.4, 0.85, prio=3)
    _ore(g, seed=11)


def tunnel_wyrm(look, name, part, ctx):
    _ramps(ctx, {
        'stone': _hx('#141010', '#1e1a1a', '#2e2826', '#463c38', '#5e524a', '#7a6a5e', '#988670', '#b8a48e'),
        'skin': _hx('#2a1a1a', '#442a28', '#62403a', '#80584e', '#9e7262', '#bc8e7a'),
        'flesh': _hx('#3a1414', '#622424', '#8a3a36', '#a8564e', '#c47a6c'),
        'ore': _hx('#5a6470', '#8a98a8', '#b4c2d0', '#d7e3ef', '#f2f8ff'),
        'claw': _hx('#1a1614', '#3a322c', '#5e5246', '#8a7a68', '#b8a48e', '#e0d2bc'),
        'eye': _hx('#6a5a30', '#a89050', '#d7c890', '#f2ecd0'),
        'glow': _hx('#5a2a10', '#9a4a1a', '#d07a30', '#f0b060', '#ffe0a8'),
    })
    return _run(ctx, name, {
        'head': (_wyrm_head, 0.7), 'jaw': (_wyrm_jaw, 0.6),
        'seg_1': (_wyrm_seg, 0.85), 'seg_2': (_wyrm_seg, 0.85), 'seg_3': (_wyrm_seg, 0.85),
        'tail': (_wyrm_tail, 0.8),
    })


# ───────────────────────────── 하피 공용 ─────────────────────────────

def _h_torso(g, ctx, kind):
    w, h, d = ctx.size
    g.blob((0, 1.2, 0), (2.9, 2.6, 2.0), 'skin', 0.5)
    g.blob((0, -1.4, 0.1), (2.3, 2.3, 1.75), 'skin', 0.48)
    g.blob((0, 1.1, -0.45), (2.85, 1.9, 1.75), 'down', 0.55, lump=0.15, lump_scale=1.0, prio=2,
           cut=lambda x, y, z: z > 0.4)
    g.blob((0, 3.3, 0.45), (3.9, 1.35, 2.5), 'feather', 0.5, prio=2)
    g.blob((0, -3.3, 0.25), (2.6, 1.3, 2.05), 'feather', 0.45, prio=2)
    for k in range(9):
        a = math.pi * (0.1 + 1.8 * k / 8) + math.pi / 2
        c, s = math.cos(a), math.sin(a)
        g.cone((c * 2.2, -3.8, 0.25 + s * 1.7), (c * 0.2, -1, s * 0.2 + 0.25), 1.6 + 0.5 * (k % 2), 0.6, 'feather',
               0.4 + 0.1 * (k % 2), 0.62, prio=3)
    wl = ctx.offset_to('wing_left')
    if wl:
        for s in (-1, 1):
            g.blob((s * abs(wl[0]), wl[1] - 0.2, wl[2]), (1.5, 1.3, 1.4), 'feather', 0.55, prio=3)
    if kind == 'spore':
        for k in range(7):
            a = math.pi * (0.15 + 0.7 * k / 6)
            g.dot((-math.cos(a) * 2.2, 2.1 - math.sin(a) * 1.0, -1.9 + math.sin(a) * 0.2), 'glow', 0.75, glow=True,
                  prio=5)
        for s, p in ((1, (2.8, 3.9, 0.8)), (-1, (-2.4, 4.1, 1.4))):
            g.mushroom(p, (s * 0.4, 1, 0.1), 0.8, 0.85, mat='cap', val=0.45, spots=0.0, glow=False, stem_r=0.35)
    else:
        g.sweep([(-1.8, 3.0, -1.6), (0, 1.4, -2.3), (1.8, 3.0, -1.6)], 0.22, 0.22, 'ink', 0.5, prio=4)
        g.rbox((-0.6, 0.0, -2.8), (0.6, 1.2, -2.0), 'ink', 0.4, bevel=0.3, prio=5)
        g.dot((0, 0.6, -2.85), 'glow', 0.7, glow=True, prio=6)
        for k, (x, y, z) in enumerate(((2.2, -3.4, -2.2), (-2.6, -3.0, -1.4), (0.6, -4.2, -2.4))):
            g.rbox((x - 0.7, y - 1.0, z - 0.1), (x + 0.7, y + 0.6, z + 0.2), 'paper', 0.7 - 0.08 * k, prio=5)
            g.dot((x, y + 0.2, z - 0.15), 'ink', 0.3, prio=6)


def _h_head(g, ctx, kind):
    hair = 'plume' if kind == 'quill' else 'feather'
    g.blob((0, -0.3, -0.3), (2.3, 2.6, 2.3), 'skin', 0.52)
    g.blob((0, 0.8, 0.55), (2.7, 2.4, 2.6), hair, 0.45, cut=lambda x, y, z: z < -1.2 and y < 1.5)
    g.sweep([(0, 0.6, 2.0), (0, -2.0, 3.0), (0, -4.2, 2.6)], 1.7, 0.7, hair, 0.42)
    for s in (-1, 1):
        g.eye((s * 0.95, 0.0, -2.25), 0.5, val=0.5, socket=0.15, facing=(s * 0.3, 0, -1))
        g.capsule((s * 0.4, 0.75, -2.45), (s * 1.6, 0.95, -2.1), 0.22, 0.2, hair, 0.25, prio=5)
        g.cone((s * 2.2, 0.8, 0.2), (s * 1, 0.9, 0.7), 2.4, 0.6, hair, 0.5, 0.65, prio=3)
    g.cone((0, -0.4, -2.45), (0, -0.4, -1), 0.7, 0.35, 'skin', 0.55, 0.6, prio=4)
    g.rbox((-0.6, -1.65, -2.55), (0.6, -1.4, -2.3), 'mouth', 0.3, prio=5)
    if kind == 'quill':
        for s in (-1, 1):
            g.capsule((s * 0.95, -0.5, -2.3), (s * 1.0, -1.9, -2.1), 0.2, 0.18, 'ink', 0.35, prio=6)
    else:
        for p in ((1.6, 2.4, 1.2), (-1.4, 2.6, 1.8), (2.0, 0.6, 2.2)):
            g.dot(p, 'glow', 0.7, glow=True, prio=5)


def _h_wing(g, ctx, kind):
    w, h, d = ctx.size
    o = ctx.out
    lead = -d * 0.3
    root = (0.0, 0.3, lead * 0.3)
    wrist = (o * w * 0.42, 0.5, lead - 0.4)
    hand = (o * w * 0.72, 0.35, lead - 0.2)
    g.sweep([root, (o * w * 0.2, 0.7, lead - 0.3), wrist, hand], 1.25, 0.6, 'feather', 0.55, sq=(1, 0.7, 1))
    prim = [((o * w * (0.72 - 0.065 * k), lead), (o * w * (1.0 - 0.07 * k), lead + d * (0.05 + 0.2 * k)), 0.9)
            for k in range(5)]
    sec = [((o * w * (0.4 - 0.08 * k), lead + 0.3), (o * w * (0.44 - 0.08 * k), lead + d * (1.0 - 0.04 * k)), 0.95)
           for k in range(5)]
    cov = [((o * w * (0.08 + 0.12 * k), lead + 0.2), (o * w * (0.1 + 0.12 * k), lead + d * 0.45), 0.85)
           for k in range(5)]
    if kind == 'quill':
        def vf(n, t, e):
            if t > 0.84:
                return ('ink', 0.3 + 0.2 * (t - 0.84) / 0.16)
            return 0.55 + (0.1 if n % 2 else 0.0) - 0.15 * t
        _feathers(g, sec + prim, 'xz', 0.0, 'feather', vf)
        _feathers(g, cov, 'xz', g.vs, 'feather', lambda n, t, e: 0.72 - (0.1 if n % 2 else 0.0))
        spots = [(o * w * 0.28, lead + d * 0.7), (o * w * 0.82, lead + d * 0.35)]
        _spots(g, [(u, g.vs * 0.5, v) for u, v in spots], 0.55, ('glow', 0.75, True))
        g.streaks('ink', ['feather'], density=0.25, length=(0.6, 1.4), val=0.3)
    else:
        def vf(n, t, e):
            return 0.42 + (0.08 if n % 2 else 0.0) + 0.12 * t - (0.14 if t > 0.86 else 0.0)
        _feathers(g, sec + prim, 'xz', 0.0, 'feather', vf)
        _feathers(g, cov, 'xz', g.vs, 'down', lambda n, t, e: 0.55 - (0.08 if n % 2 else 0.0))
        for (u, v) in ((o * w * 0.26, lead + d * 0.68), (o * w * 0.8, lead + d * 0.38)):
            _spots(g, [(u, g.vs * 0.5, v)], 1.25, ('glow', 0.7, True))
            _spots(g, [(u, g.vs * 0.5, v)], 0.6, ('feather', 0.1))


def _h_tail(g, ctx, kind):
    w, h, d = ctx.size
    fan = [((0, 0.0), ((k - 2) * w * 0.26, d * 0.95 - abs(k - 2) * 0.6), 0.95) for k in range(5)]
    fan = [fan[0], fan[4], fan[1], fan[3], fan[2]]
    if kind == 'quill':
        _feathers(g, fan, 'xz', 0.0, 'feather',
                  lambda n, t, e: ('ink', 0.35) if t > 0.84 else 0.6 - 0.15 * t + (0.08 if n % 2 else 0))
    else:
        _feathers(g, fan, 'xz', 0.0, 'feather', lambda n, t, e: 0.44 + 0.1 * t + (0.08 if n % 2 else 0))
        _spots(g, [(0, 0.2, d * 0.7)], 0.7, ('glow', 0.7, True))
    g.blob((0, 0.2, 0.2), (1.6, 1.0, 1.4), 'feather', 0.5, prio=3)


def _h_legs(g, ctx, kind):
    w, h, d = ctx.size
    for s in (-1, 1):
        x = s * w * 0.27
        g.blob((x * 0.9, -1.6, 0.1), (1.2, 2.1, 1.3), 'feather', 0.48)
        g.cone((x * 0.9, -2.6, 0.2), (0, -1, 0.15), 1.6, 0.9, 'feather', 0.42, 0.55)
        g.capsule((x, -4.0, 0.3), (x * 0.95, -8.9, 0.6), 0.6, 0.48, 'scale', 0.5)
        F = (x * 0.95, -9.3, 0.4)
        g.blob(F, (0.8, 0.5, 0.8), 'scale', 0.45)
        for k in (-1, 0, 1):
            g.horn((F[0] + k * 0.5, F[1], F[2] - 0.4), (k * 0.4, -0.15, -1), 1.9, 0.38, curl=(0, -0.8, 0), mat='claw',
                   val=0.25)
        g.horn((F[0], F[1], F[2] + 0.4), (0, -0.2, 1), 1.3, 0.34, curl=(0, -0.6, 0), mat='claw', val=0.25)


def _spore_cap(g, ctx):
    yc = -1.1
    g.blob((0, yc, 0), (4.0, 1.8, 4.0), 'cap', 0.5, cut=lambda x, y, z: y < yc - 0.5,
           vfn=lambda x, y, z, d_: 0.4 + 0.3 * (1 - d_) + 0.1 * (y - yc))
    g.rbox((-3.6, yc - 0.8, -3.6), (3.6, yc - 0.45, 3.6), 'gill', 0.4)
    g.carve(lambda x, y, z: y < yc - 0.4 and x * x + z * z > 3.7 ** 2)
    g.paint(lambda x, y, z, n, m, v: v - 0.15 if (n[1] < 0 and int(math.atan2(z, x) / 0.35) % 2 == 0) else None,
            ['gill'])
    pts = [(math.cos(a) * r, yc + 1.8 * math.sqrt(max(0.0, 1 - (r / 4.0) ** 2)), math.sin(a) * r)
           for a, r in ((0.3, 2.6), (1.6, 3.0), (2.7, 2.2), (3.9, 3.1), (5.0, 2.5), (0.0, 0.0), (2.0, 1.2))]
    _spots(g, pts, 0.75, ('glow', 0.75, True), ['cap'])
    g.mushroom((2.9, yc - 0.2, 2.4), (0.6, 1, 0.3), 0.8, 0.9, mat='cap', val=0.45, spots=0.0, stem_r=0.35)


def _quill_crest(g, ctx):
    quills = [((0.9 * k - 1.2, -2.2), (1.4 * k - 0.6, 3.0 - 0.45 * abs(k - 1.5) * 1.6), 0.75) for k in range(4)]
    _feathers(g, quills, 'zy', 0.0, 'feather',
              lambda n, t, e: ('ink', 0.35) if t > 0.82 else 0.62 - 0.1 * t + (0.08 if n % 2 else 0))
    g.blob((0, -2.0, 0.6), (0.9, 0.8, 1.6), 'plume', 0.4, prio=3)


def spore_harpy(look, name, part, ctx):
    _ramps(ctx, {
        'feather': _hx('#140c16', '#1e1420', '#30203a', '#432a46', '#5e3c5e', '#7a5276', '#9e7496', '#c49ab8'),
        'down': _hx('#5e4660', '#7e6280', '#9e82a0', '#c4a6c0', '#e0c8dc', '#f4e6f2'),
        'skin': _hx('#3a2c34', '#5a4650', '#7c626c', '#9c8088', '#bca0a6', '#dcc4c6'),
        'cap': _hx('#2a1430', '#4a2450', '#6a3a6e', '#8a5a8a', '#ae80aa', '#d0a8cc'),
        'scale': _hx('#2a2420', '#4a4038', '#6a5c50', '#8a7a68', '#ac9a84', '#cebca4'),
        'glow': _hx('#0e4a40', '#1a8070', '#2ab8a0', '#5ee0c0', '#a8f4e0', '#e8fff8'),
        'eye': _hx('#0e4a40', '#1a8070', '#2ab8a0', '#5ee0c0', '#a8f4e0', '#e8fff8'),
    })
    return _run(ctx, name, {
        'torso': (lambda g, c: _h_torso(g, c, 'spore'), 0.55), 'head': (lambda g, c: _h_head(g, c, 'spore'), 0.55),
        'crest': (_spore_cap, 0.6),
        'wing_left': (lambda g, c: _h_wing(g, c, 'spore'), 0.6), 'wing_right': (lambda g, c: _h_wing(g, c, 'spore'), 0.6),
        'tail_feathers': (lambda g, c: _h_tail(g, c, 'spore'), 0.45), 'legs': (lambda g, c: _h_legs(g, c, 'spore'), 0.5),
    })


def quill_harpy(look, name, part, ctx):
    _ramps(ctx, {
        'feather': _hx('#4a4234', '#6e6450', '#948870', '#b8ac90', '#d4caae', '#e8e0c8', '#f6f0e0'),
        'paper': _hx('#6e6450', '#948870', '#b8ac90', '#d4caae', '#e8e0c8', '#f6f0e0'),
        'down': _hx('#6e6450', '#948870', '#b8ac90', '#d4caae', '#e8e0c8', '#f6f0e0'),
        'ink': _hx('#04040a', '#0a0a12', '#141826', '#1e2236', '#2c3450', '#3a4468'),
        'plume': _hx('#06060c', '#0e1018', '#181c2a', '#22283c', '#30384e', '#424c66'),
        'skin': _hx('#1e2232', '#2e3448', '#444c64', '#5e6880', '#7a849c', '#9aa4b8'),
        'scale': _hx('#16161e', '#262834', '#3a3e4c', '#525868', '#6e7486', '#8e94a6'),
        'glow': _hx('#18285a', '#28468e', '#4a6cc4', '#7a9ae0', '#b4caf6', '#eaf2ff'),
        'eye': _hx('#18285a', '#28468e', '#4a6cc4', '#7a9ae0', '#b4caf6', '#eaf2ff'),
    })
    return _run(ctx, name, {
        'torso': (lambda g, c: _h_torso(g, c, 'quill'), 0.55), 'head': (lambda g, c: _h_head(g, c, 'quill'), 0.5),
        'crest': (_quill_crest, 0.4),
        'wing_left': (lambda g, c: _h_wing(g, c, 'quill'), 0.6), 'wing_right': (lambda g, c: _h_wing(g, c, 'quill'), 0.6),
        'tail_feathers': (lambda g, c: _h_tail(g, c, 'quill'), 0.45), 'legs': (lambda g, c: _h_legs(g, c, 'quill'), 0.5),
    })


# ───────────────────────────── barrow_lich (고분의 리치) ─────────────────────────────
# 땅에서 떠 있는 해골 마법사: 해진 로브 자락(바닥에 안 닿음)과 룬 수놓은 앞판, 갈비뼈가 드러난 가슴 속 차가운 심장,
# 높은 깃 망토, 깊은 눈구멍 속 냉기 점, 얼음 수정 왕관, 냉기 수정 지팡이, 허리 앞 영혼 등불, 허리를 도는 룬 석판.

def _lich_robe(g, ctx):
    rb = (5.2, 3.9)
    _frustum(g, 6.8, -4.8, (3.0, 2.4), rb, 'cloth', 0.45,
             vfn=lambda x, y, z, t, a: 0.42 + (0.08 if math.sin(a * 4) > 0.3 else 0.0))
    top = [(math.cos(a) * rb[0], -4.6, math.sin(a) * rb[1]) for a in [2 * math.pi * k / 40 for k in range(41)]]
    g.cloth(top, 3.0, 'cloth', 0.36, tatter=0.45, holes=0.0, seed=3)
    g.paint(lambda x, y, z, n, m, v: ('cloth2', 0.45) if (n[2] < 0 and abs(x) < 1.1 + (6.8 - y) * 0.06) else None,
            ['cloth'])
    g.runes((0, 0.2, -3.4), normal=(0, 0, -1), w=2.2, h=9.0, mat='rune', val=0.75, density=0.55)
    g.ring((0, 6.0, 0), 3.0, 0.5, axis='y', mat='cloth2', val=0.55)
    g.blob((0, 6.0, -2.6), (0.8, 0.8, 0.5), 'bone', 0.7, prio=4)
    sd = g.seed + 5
    g.paint(lambda x, y, z, n, m, v: ('frost', 0.55) if (y < -5.0 and fbm3(x / 1.4, y / 1.4, z / 1.4, sd) > 0.56)
            else None, ['cloth'])


def _lich_ribs(g, ctx):
    g.blob((0, 0.4, 0.4), (2.7, 3.0, 1.6), 'void', 0.12, prio=0)
    for k in range(6):
        g.blob((0, -3.6 + k * 1.35, 1.9), (0.75, 0.55, 0.65), 'bone', 0.55)
    for k, y in enumerate((2.2, 0.6, -1.0)):
        rx = 3.4 - 0.22 * k
        for s in (-1, 1):
            pts = [(s * 0.6, y + 0.2, 1.9), (s * rx * 0.9, y, 1.2), (s * rx, y - 0.4, -0.4), (s * rx * 0.6, y - 0.7, -1.9),
                   (s * 0.55, y - 0.6, -2.2)]
            g.sweep(pts, 0.45, 0.38, 'bone', 0.6)
    g.capsule((0, 2.6, -2.3), (0, -0.4, -2.3), 0.55, 0.45, 'bone', 0.62)
    g.blob((0.3, 0.8, -0.2), 0.95, 'core', 0.7, glow=True, prio=3)
    for s in (-1, 1):
        g.capsule((s * 0.6, 3.4, -1.8), (s * 3.6, 3.3, -0.2), 0.5, 0.45, 'bone', 0.65)
    g.blob((0, 3.6, 1.1), (4.4, 1.5, 2.5), 'cloth', 0.48, cut=lambda x, y, z: z < -0.5 and abs(x) < 2.8)
    for y in (4.6, 5.8, 7.0):
        g.ring((0, y, -0.3), 4.2, 0.45, axis='y', mat='cloth' if y < 6.5 else 'cloth2', val=0.42,
               arc=(0.03, 0.47))
    for a in (0.08, 0.25, 0.42):
        ang = 2 * math.pi * a
        g.cone((math.cos(ang) * 4.2, 7.9, -0.3 + math.sin(ang) * 4.2), (0, 1, 0.2), 1.6, 0.45, 'cloth2', 0.5, 0.6)
    g.cloth([(-4.0, 3.2, 2.6), (4.0, 3.2, 2.6)], 10.0, 'cloth', 0.4, tatter=0.3, normal=(0, 0, 1), seed=7)


def _lich_skull(g, ctx):
    g.blob((0, 0.7, 0.3), (3.1, 2.9, 3.2), 'bone', 0.55)
    g.blob((0, -1.2, -1.0), (2.4, 1.7, 2.2), 'bone', 0.5)
    for s in (-1, 1):
        g.capsule((s * 1.6, -0.7, -2.3), (s * 2.7, -0.4, -0.6), 0.6, 0.5, 'bone', 0.62)
        g.carve_blob((s * 1.15, 0.1, -2.8), (0.95, 0.85, 1.25))
        g.blob((s * 1.15, 0.1, -2.0), 1.0, 'void', 0.1, prio=0)
        g.eye((s * 1.15, 0.1, -2.15), 0.38, val=0.85)
    g.carve(lambda x, y, z: z < -2.3 and -1.5 < y < -0.5 and abs(x) < 0.55 * (y + 1.5))
    g.blob((0, -1.0, -2.2), 0.6, 'void', 0.1, prio=0)
    g.carve(lambda x, y, z: z < -1.6 and -2.9 < y < -2.4 and abs(x) < 1.6)
    g.rbox((-1.5, -2.9, -2.3), (1.5, -2.4, -1.4), 'void', 0.1, prio=0)
    g.blob((0, -3.1, -1.1), (2.0, 0.75, 1.8), 'bone', 0.5)
    g.teeth((-1.2, -2.35, -2.8), (1.2, -2.35, -2.8), 6, 0.5, r=0.28, direction=(0, -1, 0))
    g.teeth((-1.0, -2.9, -2.6), (1.0, -2.9, -2.6), 5, 0.45, r=0.26, direction=(0, 1, 0))
    g.moss_paint(coverage=0.5, mat='frost', val=0.65, mats=['bone'], scale=1.6, up_min=0.55)


def _lich_crown(g, ctx):
    g.ring((0, -3.4, 0), 3.0, 0.5, axis='y', mat='iron', val=0.55)
    for k in range(5):
        a = -math.pi / 2 + 2 * math.pi * k / 5
        c, s = math.cos(a), math.sin(a)
        size = 3.4 if k == 0 else 2.0 + 0.6 * (k % 2)
        g.crystals((c * 2.9, -3.2, s * 2.9), (c * 0.3, 1, s * 0.3), n=1, size=size, r=0.55 if k else 0.75, mat='ice',
                   seed=k)
    g.blob((0, -3.4, -3.15), 0.55, 'core', 0.7, glow=True, prio=4)


def _lich_arm(g, ctx):
    o = ctx.out
    right = ctx.name == 'arm_right'
    g.capsule((0, -0.3, 0.1), (0, -5.0, 0.2), 1.5, 1.9, 'cloth', 0.45)
    hem = [(math.cos(a) * 1.9, -5.2, 0.2 + math.sin(a) * 1.9) for a in [2 * math.pi * k / 16 for k in range(17)]]
    g.cloth(hem, 2.2, 'cloth', 0.36, tatter=0.4, seed=9 if right else 13)
    for x in (-0.4, 0.4):
        g.capsule((x, -5.2, 0.1), (x * 0.8, -9.6, -0.3), 0.36, 0.32, 'bone', 0.6)
    g.blob((0, -9.9, -0.3), (0.85, 0.55, 0.6), 'bone', 0.62)
    g.blob((0, -10.5, -0.5), (0.9, 0.7, 0.5), 'bone', 0.56)
    if right:
        for k, x in enumerate((-0.6, -0.2, 0.2, 0.6)):
            g.sweep([(x, -10.9, -0.8), (x, -11.6, -1.3), (x, -12.0, -0.4), (x, -11.4, 0.4)], 0.24, 0.2, 'bone', 0.6)
        g.capsule((o * 0.8, -10.6, -0.6), (o * 0.6, -11.3, -1.4), 0.24, 0.2, 'bone', 0.62)
    else:
        for k, x in enumerate((-0.65, -0.22, 0.22, 0.65)):
            g.sweep([(x, -10.9, -0.6), (x * 1.3, -12.2, -1.2), (x * 1.5, -13.2, -1.0)], 0.24, 0.18, 'bone', 0.6)
        g.capsule((o * 0.8, -10.5, -0.6), (o * 1.4, -11.3, -1.4), 0.24, 0.2, 'bone', 0.62)
        g.blob((0, -12.6, -2.0), 0.7, 'core', 0.75, glow=True, prio=4)
        for k, p in enumerate(((0.9, -12.0, -2.6), (-0.8, -13.2, -2.4), (0.2, -13.6, -1.6))):
            g.crystals(p, (0.2 * (k - 1), 1, -0.3), n=1, size=0.9, r=0.3, mat='ice', seed=k + 3)


def _lich_staff(g, ctx):
    hx, hy, hz = ctx.hand
    z0, z1 = hz + 4.0, hz - 21.0
    pts = [(hx, hy, z0), (hx + 0.3, hy + 0.2, hz - 6), (hx - 0.3, hy + 0.5, hz - 14), (hx, hy + 0.9, z1)]
    g.sweep(pts, 0.6, 0.5, 'wood', 0.45)
    for z in (hz - 2.5, hz - 9.0, hz - 16.0):
        g.ring((hx, hy + 0.2, z), 0.75, 0.3, axis='z', mat='bone', val=0.65)
    g.cylinder((hx, hy, z0 + 0.6), (hx, hy, z0 - 0.8), 0.75, 0.6, 'iron', 0.5, prio=3)
    hc = (hx, hy + 1.2, z1 - 1.6)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        c, s = math.cos(a), math.sin(a)
        g.sweep([(hx, hy + 0.9, z1 + 0.6), (hx + c * 1.6, hy + 0.9 + s * 1.6, z1 - 0.6),
                 (hx + c * 1.1, hy + 1.2 + s * 1.1, z1 - 2.8)], 0.35, 0.2, 'bone', 0.62)
    g.crystals(hc, (0, 0.2, -1), n=3, size=2.6, r=0.85, mat='ice', spread=0.5)
    g.blob(hc, 0.8, 'core', 0.75, glow=True, prio=5)


def _lich_lantern(g, ctx):
    g.rbox((-1.6, 1.8, -1.6), (1.6, 2.5, 1.6), 'iron', 0.5, bevel=0.3)
    g.rbox((-1.4, -2.5, -1.4), (1.4, -1.9, 1.4), 'iron', 0.45, bevel=0.3)
    for x in (-1.3, 1.3):
        for z in (-1.3, 1.3):
            g.capsule((x, -2.0, z), (x, 1.9, z), 0.3, 0.3, 'bone', 0.6)
    g.blob((0, 0, 0), (1.05, 1.4, 1.05), 'core', 0.7, glow=True, prio=3)
    g.dot((0, 0.2, 0), 'core', 0.95, glow=True, prio=4)
    g.ring((0, 3.1, 0), 0.6, 0.25, axis='x', mat='iron', val=0.6)
    g.chain([(0, 3.6, 0), (0, 5.6, 0.4)], 0.8, 'iron', 0.5)


def _lich_runes(g, ctx):
    R = 8.6
    for k in range(6):
        a = 2 * math.pi * k / 6
        n = (math.cos(a), 0.0, math.sin(a))
        t = (-math.sin(a), 0.0, math.cos(a))
        y0 = 0.6 * math.sin(a * 2)
        c = (n[0] * R, y0, n[2] * R)
        g.rbox(vadd(c, (-0.9 * abs(t[0]) - 0.3 * abs(n[0]), -1.6, -0.9 * abs(t[2]) - 0.3 * abs(n[2]))),
               vadd(c, (0.9 * abs(t[0]) + 0.3 * abs(n[0]), 1.6, 0.9 * abs(t[2]) + 0.3 * abs(n[2]))),
               'stone', 0.35, bevel=0.2)
        for bx in range(3):
            for by in range(5):
                if not rune_bit(k * 3 + 1, bx, by):
                    continue
                p = vadd(vadd(c, vmul(t, (bx - 1) * 0.5)), vmul(n, 0.5))
                g.dot((p[0], y0 + (2 - by) * 0.55, p[2]), 'rune', 0.75, glow=True, prio=5)


def barrow_lich(look, name, part, ctx):
    _ramps(ctx, {
        'cloth': _hx('#06070c', '#0e1018', '#161a26', '#1e2232', '#262a3a', '#343a4e', '#4a5268'),
        'cloth2': _hx('#0a1420', '#122436', '#1c364c', '#284a62', '#365e78', '#4a7690'),
        'bone': _hx('#4a4c52', '#6c7078', '#8e949c', '#aeb6be', '#c8d4e0', '#e2eaf2', '#f6faff'),
        'ice': _hx('#3a7aa0', '#5aa0c4', '#80c6e2', '#a8e2f4', '#d2f4ff', '#ffffff'),
        'wood': _hx('#0c0a0c', '#1a161a', '#2a2428', '#3c3438', '#504648', '#6a5e5e'),
        'stone': _hx('#141620', '#22263a', '#30364e', '#424a66', '#566080'),
        'void': _hx('#020205', '#06060c', '#0c0c16', '#141420'),
        'rune': _hx('#1a5a7a', '#2a8ab0', '#4ab4dc', '#7ad8ff', '#bceeff', '#f0fcff'),
        'core': _hx('#1a5a7a', '#2a8ab0', '#4ab4dc', '#7ad8ff', '#bceeff', '#f0fcff'),
        'eye': _hx('#1a5a7a', '#2a8ab0', '#4ab4dc', '#7ad8ff', '#bceeff', '#f0fcff'),
    })
    return _run(ctx, name, {
        'robe': (_lich_robe, 0.9), 'ribcage': (_lich_ribs, 0.7), 'head': (_lich_skull, 0.62),
        'crown': (_lich_crown, 0.65), 'arm_left': (_lich_arm, 0.65), 'arm_right': (_lich_arm, 0.65),
        'staff': (_lich_staff, 0.65), 'phylactery': (_lich_lantern, 0.55), 'runes': (_lich_runes, 0.55),
    })


DESIGNS = {
    'moss_drakeling': moss_drakeling,
    'bog_drake': bog_drake,
    'ember_drake': ember_drake,
    'frost_wyvern': frost_wyvern,
    'clockwork_wyvern': clockwork_wyvern,
    'void_drake': void_drake,
    'tunnel_wyrm': tunnel_wyrm,
    'spore_harpy': spore_harpy,
    'quill_harpy': quill_harpy,
    'barrow_lich': barrow_lich,
}
