"""Original voxel weapon designs (swords, axes, maces, daggers, staves, scepters, censers, bows).

Voxel space: hold point at (0, 0, 0), +Y along the weapon, blade flat in the XY plane (width X,
thickness Z).  1 voxel = 0.5 model units (items.py maps the grid onto the model's hold point).
Rarity escalation (P.lv 0..5): common clean → rare trims+gem → epic organic motif → legendary /
mythic dramatic silhouettes (coiling creatures, wings, crystal growth, floating shards, glow).
"""
from __future__ import annotations

import math
import random

from ..materials import rune_bit
from .core import Grid, bezier, catmull, helix

# ───────────────────────────── design parameters ─────────────────────────────

# 아이템 id 부분 문자열 → 테마 (앞 묶음부터 확인). 맞는 키가 없으면 texture.style 로 정해진다
# (leather → vine, cloth → fungi …). 새 장비·세트가 그 층 테마로 안 잡히면 여기에 id 키를 더한다
# (세트 부위끼리 테마가 갈리면 validate 가 오류로 잡는다).
THEME_KEYS = (
    ('vine', ('moss', 'corridor', 'root', 'grove', 'wayfarer', 'lantern', 'acolyte', 'novice')),
    ('fungi', ('spore', 'mycel', 'glowcap', 'hypha', 'bloom', 'capsplit')),
    ('abyss', ('abyss', 'void', 'nightshade', 'eclipse', 'viper')),
    ('web', ('skitter', 'silk', 'fang', 'webrun')),
    ('water', ('brine', 'tide', 'eel', 'drowned', 'sluice', 'verdigris')),
    ('forge', ('ember', 'cinder', 'slag', 'anvil', 'bellows', 'forge', 'minewarden', 'miners', 'ore_', 'pit_',
               'comet')),
    ('frost', ('rime', 'frost', 'soulflame', 'waning')),
    ('crystal', ('crystal', 'geode', 'amethyst', 'prism', 'resonan', 'shardglass', 'twin_light',
                 'mountainheart', 'daybreak')),
    ('ink', ('ink', 'index', 'lore')),
    ('clock', ('clock', 'regulator', 'doomclock', 'mainspring', 'spring', 'orrery', 'pendulum', 'tesla')),
    ('blood', ('bloodmoon',)),
    ('storm', ('tempest', 'galewing', 'quicksilver')),
    ('holy', ('dawn', 'celestial', 'sanctum', 'seraph', 'aurora', 'embersong')),
)
STYLE_THEME = {'moss': 'vine', 'wood': 'vine', 'silver': 'storm', 'copper': 'water', 'ember': 'forge',
               'dark_iron': 'forge', 'rusted_iron': 'forge', 'frost': 'frost', 'crystal': 'crystal', 'ink': 'ink',
               'clockwork': 'clock', 'abyss': 'abyss', 'void': 'abyss', 'shadow': 'abyss', 'holy': 'holy',
               'gold': 'holy', 'bone': 'web', 'coral': 'water', 'leather': 'vine', 'cloth': 'fungi', 'silk': 'web',
               'obsidian': 'blood', 'steel': 'plain'}
CREATURE = ('viper', 'bloodmoon', 'abyss_sentinel', 'tidecaller', 'eel', 'drowned', 'celestial', 'nightshade')
# 0.3.7 신화 6 (myth-037): id 키 → 무기 틀 안의 표시 분기 (태산 봉우리·만조 파도 날·혜성 머리·도깨비불·해 원반 종·사슬과
# 초승달 추). 틀(실루엣)은 그대로 쓰고 머리 장식만 바꾼다 — 짝 신화·같은 틀 전설과 그림이 겹치지 않게.
SIGNATURES = ('mountainheart', 'hightide', 'comet', 'wisp', 'daybreak', 'waning')


def _key_in(k, iid):
    """Keys ending in '_' ('ore_') only match at a word start — 'lore_…' (금서) is ink, not ore (forge)."""
    if k.endswith('_'):
        return iid.startswith(k) or ('_' + k) in iid
    return k in iid


def theme_of(iid, style):
    for th, keys in THEME_KEYS:
        if any(_key_in(k, iid) for k in keys):
            return th
    return STYLE_THEME.get(style, 'plain')


class P:
    def __init__(self, iid, lv, theme, length, seed, animated, magic=False):
        self.iid = iid
        self.lv = lv
        self.theme = theme
        self.L = length
        self.rng = random.Random(seed)
        self.anim = animated
        self.creature = lv >= 3 and any(k in iid for k in CREATURE)
        self.sig = next((k for k in SIGNATURES if k in iid), None)
        # 보석이 빛남: 전설 이상, 또는 마법 피해 근접·원거리 무기(0.3.5 gear_spec §9.1 — 모델은 그대로, 보석만 한 단계 밝게)
        self.glow = lv >= 4 or (magic and lv >= 2)


# ───────────────────────────── common parts ─────────────────────────────

def grip(g: Grid, y0, y1, r=1.25, mat='grip'):
    for j in range(y0, y1 + 1):
        for i in range(-2, 3):
            for k in range(-2, 3):
                if i * i + k * k <= r * r + 0.3:
                    w = (j * 2 + i - k) % 4
                    g.put(i, j, k, mat, 0.66 if w == 0 else 0.28 if w == 2 else 0.46)
    for y in (y0, y1):
        for i in range(-1, 2):
            for k in range(-1, 2):
                g.put(i, y, k, 'metal', 0.55, prio=2)


def pommel(g: Grid, y, p: P, r=1.7):
    g.ball((0, y, 0), r, 'metal', vfn=lambda i, j, k, d: 0.35 + 0.35 * (1 - d) + (0.1 if j > y else 0))
    if p.lv >= 1:
        g.crystal((0, y - r + 0.5, 0), (0, -1, 0), 2.6, 0.9, 'metal', prio=2)
    if p.lv >= 2:
        for s in (-1, 1):
            g.gem((0, y, s * (r - 0.2)), 0.8, 'gem', glow=p.glow)
    if p.lv >= 4:
        g.torus((0, y, 0), r + 0.9, 0.5, 'y', 'orn', 0.65)


def crossguard(g: Grid, y, half, p: P, curl=None):
    """Cross-guard in the XY plane at height y (2 voxels tall), tips by rarity."""
    lv = p.lv

    def m(u, v):
        if abs(u) <= half and y <= v <= y + 1:
            return True
        if abs(u) <= 2 and y - 1 <= v <= y + 2:
            return True
        return False

    g.slab(m, (-half - 1, y - 2), (half + 1, y + 3), 'xy', 0, max_half=1, slope=1.0, mat='metal',
           vfn=lambda u, v, w, d: 0.5 + 0.18 * (v - y) / 2 - 0.1 * (abs(u) / max(1, half)) + (0.12 if d == 0 else 0))
    for s in (-1, 1):
        tip = (s * (half + 0.3), y + 0.5, 0)
        if lv >= 1 and (curl if curl is not None else True):
            pts = bezier(tip, (s * (half + 1.5), y + 1.0, 0), (s * (half + 1.8), y + 3.0, 0), (s * (half + 0.6), y + 4.2, 0), 12)
            g.tube(pts, 1.0, 0.6, 'orn' if lv >= 2 else 'metal', vfn=lambda t, d, q: 0.7 - 0.25 * d + 0.1 * t, prio=2)
        else:
            g.ball(tip, 1.2, 'metal', 0.6)
    if lv >= 2:
        g.gem((0, y + 0.5, 1), 1.2 if lv >= 3 else 1.0, 'gem', glow=p.glow)
        g.gem((0, y + 0.5, -1), 1.0, 'gem', glow=p.glow)
        for s in (-1, 1):
            g.box((s * 3, y, -1), (s * 3, y + 1, 1), 'orn', 0.75, prio=2)


def blade(g: Grid, y0, length, hw, p: P, tip=0.2, curve=0.0, wave=0.0, thick=1, fuller=True, edge_mat='edge',
          body_mat='blade', taper=0.12, wave_n=3.0, asym=0.0, rune=None):
    """Tapered blade with diamond cross-section, bevelled edges and a fuller (rune-lit at high rarity)."""
    rune = p.lv >= 3 if rune is None else rune
    top = y0 + length
    for j in range(y0, top + 1):
        t = (j - y0) / max(1, length)
        if t < 1 - tip:
            w = hw * (1 - taper * t)
        else:
            w = hw * (1 - taper * (1 - tip)) * ((1 - t) / tip) ** 0.85
        c = curve * t * t + wave * math.sin(t * math.pi * wave_n) * (1 - t * 0.5)
        lo = c - w - asym * w * 0.4
        hi = c + w
        for i in range(math.floor(lo) - 1, math.ceil(hi) + 2):
            if i < lo - 0.45 or i > hi + 0.45:
                continue
            dx = i - c
            e = min(1.0, abs(dx) / max(w, 0.8))
            dist_edge = min(i - lo, hi - i)
            th = thick if e < 0.55 else max(0, thick - 1)
            if thick >= 2 and e < 0.25:
                th = thick
            groove = fuller and abs(dx) < 0.6 and t < 0.72 and length >= 14 and w >= 2.2
            for k in range(-th, th + 1):
                if dist_edge < 0.9:
                    mat, v = edge_mat, 0.62 + 0.18 * (1 - t) * 0 + (0.12 if k == 0 else 0)
                elif groove:
                    if abs(k) == th and th > 0:
                        continue
                    if rune and (j % 5) in (1, 2, 3):
                        g.put(i, j, k, 'glow', 0.75, glow=True, prio=3)
                        continue
                    mat, v = 'fuller', 0.3
                else:
                    mat, v = body_mat, 0.42 + 0.22 * (1 - e) + (0.05 if k > 0 else -0.03 if k < 0 else 0)
                g.put(i, j, k, mat, v)
    return top


def shaft(g: Grid, y0, y1, r=1.25, mat='wood', bands=()):
    for j in range(y0, y1 + 1):
        for i in range(-2, 3):
            for k in range(-2, 3):
                if i * i + k * k <= r * r + 0.3:
                    g.put(i, j, k, mat, 0.45 + (0.12 if (j + i * 3) % 7 == 0 else 0) + 0.06 * (i - k) / 2)
    for y in bands:
        for i in range(-2, 3):
            for k in range(-2, 3):
                if i * i + k * k <= 2.3:
                    g.put(i, y, k, 'metal', 0.6, prio=2)


def float_shards(g: Grid, pts, p: P, size=3.0, r=0.9, mat='crystal'):
    for (x, y, z) in pts:
        g.crystal((x, y - size / 2, z), (0, 1, 0), size, r, mat, glow=True, prio=4, tip=0.5)
        g.crystal((x, y - size / 2 + 0.3, z), (0, -1, 0), size * 0.45, r * 0.9, mat, glow=True, prio=4, tip=0.9)


def halo(g: Grid, c, R, axis='y', p=None):
    g.torus(c, R, 0.5, axis, 'glow', 0.8, glow=True, prio=4)
    n = 8
    for k in range(n):
        a = 2 * math.pi * k / n
        if axis == 'y':
            q = (c[0] + math.cos(a) * R, c[1], c[2] + math.sin(a) * R)
        else:
            q = (c[0] + math.cos(a) * R, c[1] + math.sin(a) * R, c[2])
        g.gem(q, 1.0, 'glow', glow=True)


# ───────────────────────────── motifs ─────────────────────────────

def serpent(g: Grid, y0, y1, R, turns, p: P, phase=0.0, rmax=1.7, zs=1.0, head=True):
    rmax = rmax * 1.3
    """Coiling creature (serpent / dragon / eel) around the Y axis, head at the top end."""
    pts = helix(y0, y1, R, turns, phase, zs=zs)
    rr = random.Random(p.rng.random())

    def vfn(t, d, q):
        ax = math.hypot(q[0], q[2] / max(zs, 0.3))
        band = (t * 44) % 2 < 1
        if ax < R - 0.4 and d > 0.35:
            return ('belly', 0.45 + (0.15 if band else 0))
        return 0.3 + 0.32 * (1 - d) + (0.14 if band else 0)

    seen = g.tube(pts, 0.7, rmax, 'scale', step=0.28,
                  vfn=lambda t, d, q: (lambda r: r if not isinstance(r, tuple) else None)(vfn(t, d, q)))
    for q, (t, d) in seen.items():
        r = vfn(t, d, q)
        if isinstance(r, tuple):
            g.put(q[0], q[1], q[2], r[0], r[1])
    # dorsal fins
    n = len(pts)
    for s in range(4, n - 6, 5):
        x, y, z = pts[s]
        ln = math.hypot(x, z) or 1
        ox, oz = x / ln, z / ln
        t = s / n
        rad = 0.7 + (rmax - 0.7) * t
        a = (x + ox * rad, y, z + oz * rad)
        b = (x + ox * (rad + 1.6), y - 0.8, z + oz * (rad + 1.6))
        g.tube([a, b], 0.6, 0.45, 'fin', vfn=lambda t_, d_, q_: 0.55 + 0.25 * t_, prio=2)
    if not head:
        return
    # head along the final tangent
    (x1, y1_, z1), (x0, y0_, z0) = pts[-1], pts[-4]
    tx, ty, tz = x1 - x0, y1_ - y0_, z1 - z0
    tl = math.sqrt(tx * tx + ty * ty + tz * tz) or 1
    tx, ty, tz = tx / tl, ty / tl + 0.35, tz / tl
    tl = math.sqrt(tx * tx + ty * ty + tz * tz)
    tx, ty, tz = tx / tl, ty / tl, tz / tl
    h0 = (x1, y1_, z1)
    snout = (x1 + tx * 4.2, y1_ + ty * 4.2, z1 + tz * 4.2)
    g.tube([h0, snout], rmax + 0.4, 0.9, 'scale', vfn=lambda t, d, q: 0.42 + 0.3 * (1 - d) + 0.1 * t, prio=3)
    jaw0 = (x1, y1_ - 1.2, z1)
    jaw1 = (x1 + tx * 3.6, y1_ + ty * 3.6 - 1.8, z1 + tz * 3.6)
    g.tube([jaw0, jaw1], rmax * 0.7, 0.6, 'belly', 0.5, prio=3)
    # horns sweeping back
    for s in (-1, 1):
        side = (-tz * s, 0, tx * s)
        hb = (x1 + side[0] * 1.2, y1_ + 1.2, z1 + side[2] * 1.2)
        hm = (hb[0] - tx * 1.5 + side[0] * 0.8, hb[1] + 1.6, hb[2] - tz * 1.5 + side[2] * 0.8)
        he = (hb[0] - tx * 3.6 + side[0] * 1.2, hb[1] + 2.0, hb[2] - tz * 3.6 + side[2] * 1.2)
        g.tube(catmull([hb, hm, he], 6), 0.75, 0.45, 'bone', vfn=lambda t, d, q: 0.4 + 0.45 * t, prio=4)
        eye = (x1 + tx * 1.4 + side[0] * (rmax + 0.1), y1_ + 0.6, z1 + tz * 1.4 + side[2] * (rmax + 0.1))
        g.put(round(eye[0]), round(eye[1]), round(eye[2]), 'eye', 0.9, glow=True, prio=5)
    if p.lv >= 5:
        # breath wisps
        b0 = (snout[0] + tx, snout[1] + ty, snout[2] + tz)
        g.tube([b0, (b0[0] + tx * 2 + 0.8, b0[1] + 2.2, b0[2] + tz * 2)], 0.6, 0.5, 'glow', 0.8, glow=True, prio=4)


def vines(g: Grid, y0, y1, R, p: P, n=2, leaves=True, buds=True, zs=1.0, r=0.6):
    for v in range(n):
        ph = p.rng.random() * 6.28
        turns = (y1 - y0) / 11.0
        pts = helix(y0, y1, R, turns * (1 if v % 2 == 0 else -1), ph,
                    rfn=lambda t, v=v: 1.0 + 0.22 * math.sin(t * 17 + v), zs=zs)
        g.tube(pts, r + 0.25, r, 'vine', vfn=lambda t, d, q: 0.35 + 0.35 * (1 - d) + 0.1 * math.sin(t * 40), prio=2)
        for s in range(3, len(pts) - 2, 4):
            x, y, z = pts[s]
            ln = math.hypot(x, z) or 1
            ox, oz = x / ln, z / ln
            if leaves and s % 8 == 3:
                c = (x + ox * 1.4, y + 0.6, z + oz * 1.4)
                g.ball(c, 1.25, 'leaf', sq=(1.2, 0.65, 1.2) if abs(ox) > abs(oz) else (0.8, 0.65, 1.3),
                       vfn=lambda i, j, k, d: 0.35 + 0.4 * (1 - d) + (0.15 if j > c[1] else 0), prio=2)
            elif buds and s % 8 == 7 and p.lv >= 3:
                g.gem((round(x + ox * 1.3), round(y), round(z + oz * 1.3)), 0.6, 'glow', glow=True)


def tendrils(g: Grid, base, p: P, n=5, length=10, spread=6.0, up=1.0, r0=1.3, mat='tendril'):
    rr = p.rng
    for k in range(n):
        a = 2 * math.pi * k / n + rr.random() * 0.6
        dx, dz = math.cos(a), math.sin(a) * 0.55
        pts = [base]
        x, y, z = base
        for s in range(1, 5):
            f = s / 4
            x = base[0] + dx * spread * f + math.sin(f * 5 + k) * 1.4
            z = base[2] + dz * spread * f * 0.6
            y = base[1] + up * length * f + math.cos(f * 4 + k * 1.7) * 1.2
            pts.append((x, y, z))
        g.tube(catmull(pts, 6), r0, 0.45, mat, vfn=lambda t, d, q: 0.3 + 0.45 * (1 - d) * (1 - t * 0.5) + 0.25 * t,
               prio=2)
        g.put(round(pts[-1][0]), round(pts[-1][1]), round(pts[-1][2]), 'glow', 0.9, glow=True, prio=4)


def wing(g: Grid, root, side, p: P, span=9.0, rise=12.0, n=6, mat='feather', droop=0.0):
    """Feathered wing in the XY plane: a leading arm arcs up/out; feathers hang from it toward the tip."""
    rx, ry, rz = root
    arm = bezier(root, (rx + side * span * 0.35, ry + rise * 0.55, rz), (rx + side * span * 0.8, ry + rise * 0.95, rz),
                 (rx + side * span, ry + rise, rz), 20)
    g.tube(arm, 1.1, 0.6, 'orn', vfn=lambda t, d, q: 0.55 + 0.25 * (1 - d), prio=3)
    for f in range(n):
        t = 0.18 + 0.82 * f / max(1, n - 1)
        a = arm[min(len(arm) - 1, int(t * (len(arm) - 1)))]
        ln = 3.0 + 6.5 * t
        ang = math.radians(-90 + 55 * t - droop)   # pointing down-out, flaring outward toward tip
        tip = (a[0] + side * math.cos(ang) * ln * 0.55 + side * 0.8 * t, a[1] + math.sin(ang) * ln, rz)
        mid = ((a[0] + tip[0]) / 2 + side * 0.6, (a[1] + tip[1]) / 2, rz)
        alt = 0.08 if f % 2 == 0 else -0.06
        g.tube(catmull([a, mid, tip], 5), 1.15, 0.5, mat, sq=(1, 1, 0.7),
               vfn=lambda tt, d, q, alt=alt: 0.38 + 0.4 * tt + alt + 0.12 * (1 - d), prio=2)
        if p.lv >= 4 and f == n - 1:
            g.put(round(tip[0]), round(tip[1]), rz, 'glow', 0.9, glow=True, prio=4)


def crystal_cluster(g: Grid, base, p: P, n=4, size=4.0, r=1.1, up=(0, 1, 0), spread=0.7, glow=False):
    rr = p.rng
    g.crystal(base, up, size * 1.25, r * 1.15, 'crystal', glow=glow, prio=3)
    for k in range(n - 1):
        a = 2 * math.pi * k / (n - 1) + rr.random()
        d = (up[0] + math.cos(a) * spread, up[1] + 0.2, up[2] + math.sin(a) * spread * 0.7)
        g.crystal((base[0] + math.cos(a) * 0.8, base[1], base[2] + math.sin(a) * 0.5), d,
                  size * (0.55 + rr.random() * 0.35), r * 0.8, 'crystal', glow=glow, prio=3)


def gear(g: Grid, c, R, p: P, teeth=8, plane='xy', mat='orn', hole=True, glow=False):
    def m(u, v):
        x, y = u - c[0], v - (c[1] if plane == 'xy' else c[2])
        d = math.hypot(x, y)
        a = math.atan2(y, x)
        if hole and d < R * 0.32:
            return False
        if d <= R - 0.8:
            if R >= 4 and R * 0.38 < d < R - 1.6:
                return any(abs(((a - s * math.pi / 2) + math.pi) % (2 * math.pi) - math.pi) < 0.3 for s in range(4))
            return True
        return d <= R + 0.6 and ((a * teeth / (2 * math.pi)) % 1.0) < 0.5
    R2 = int(R + 2)
    if plane == 'xy':
        g.slab(m, (int(c[0]) - R2, int(c[1]) - R2), (int(c[0]) + R2, int(c[1]) + R2), 'xy', int(c[2]), max_half=0,
               mat=mat, glow=glow, prio=3, vfn=lambda u, v, w, d: 0.45 + 0.25 * min(1, d / 2))
    else:
        g.slab(lambda u, v: m(u, v), (int(c[0]) - R2, int(c[2]) - R2), (int(c[0]) + R2, int(c[2]) + R2), 'xz',
               int(c[1]), max_half=0, mat=mat, glow=glow, prio=3, vfn=lambda u, v, w, d: 0.45 + 0.25 * min(1, d / 2))


def flames(g: Grid, y0, y1, xfn, p: P, n=6):
    """Flame tongues licking up from both blade edges; xfn(y) → half width at y."""
    for s in (-1, 1):
        for k in range(n):
            y = y0 + (y1 - y0) * (k + 0.5 * (s > 0)) / n
            x = s * (xfn(y) + 0.3)
            h = 3.5 + (k % 3) * 1.2
            pts = catmull([(x, y, 0), (x + s * 1.6, y + h * 0.4, 0), (x + s * 0.6, y + h * 0.8, 0),
                           (x + s * 1.2, y + h, 0)], 5)
            g.tube(pts, 1.1, 0.5, 'flame', glow=True, vfn=lambda t, d, q: 0.85 - 0.5 * t + 0.15 * (1 - d), prio=2)


def fungi(g: Grid, c, p: P, size=2.2, up=(0, 1, 0)):
    x, y, z = c
    top = (x + up[0] * 1.8, y + up[1] * 1.8, z + up[2] * 1.8)
    g.tube([c, top], 0.7, 0.6, 'belly', 0.55, prio=2)
    g.ball(top, size, 'fungus', sq=(1, 0.5, 1), prio=3,
           vfn=lambda i, j, k, d: (0.85 if (i * 7 + k * 3 + j) % 5 == 0 and d > 0.6 else 0.42 + 0.3 * (1 - d)))
    if p.lv >= 3:
        g.put(round(top[0]), round(top[1] + size * 0.5 + 0.6), round(top[2]), 'glow', 0.9, glow=True, prio=4)


def shell(g: Grid, c, p: P, R=2.6, turns=2.2, plane='xy'):
    pts = []
    n = 36
    for k in range(n + 1):
        t = k / n
        a = turns * 2 * math.pi * t
        r = R * (1 - 0.82 * t)
        if plane == 'xy':
            pts.append((c[0] + math.cos(a) * r, c[1] + math.sin(a) * r, c[2] + t * 1.2))
        else:
            pts.append((c[0] + t * 1.2, c[1] + math.sin(a) * r, c[2] + math.cos(a) * r))
    g.tube(pts, 1.2, 0.45, 'shell', vfn=lambda t, d, q: 0.35 + 0.45 * (1 - d) + (0.12 if int(t * 18) % 2 else 0), prio=3)


def ribbon(g: Grid, y0, y1, R, p: P, turns=2.0, phase=0.0, mat='paper'):
    pts = helix(y0, y1, R, turns, phase, zs=0.9)
    g.tube(pts, 0.55, 0.55, mat, sq=(1, 2.6, 1), step=0.25,
           vfn=lambda t, d, q: 0.72 if int(t * 60) % 3 else 0.35, prio=3)
    # ink glyph dots on the ribbon
    for s in range(2, len(pts), 6):
        x, y, z = pts[s]
        g.put(round(x), round(y), round(z), 'glow' if p.glow else 'ink', 0.8, glow=p.glow, prio=4)


def drips(g: Grid, pts, p: P, mat='ink'):
    for (x, y, z) in pts:
        ln = 2 + int(abs(x * 13 + y * 7) % 3)
        g.tube([(x, y, z), (x, y - ln, z)], 0.65, 0.55, mat, 0.4, prio=2)
        g.ball((x, y - ln - 0.6, z), 0.85, 'glow' if p.glow else mat, 0.8, glow=p.glow, prio=3)


def web(g: Grid, c, R, p: P, z=0):
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.3
        g.tube([(c[0], c[1], z), (c[0] + math.cos(a) * R, c[1] + math.sin(a) * R, z)], 0.5, 0.5, 'string', 0.8, prio=1)
    for rr in (R * 0.45, R * 0.8):
        pts = [(c[0] + math.cos(2 * math.pi * k / 6 + 0.3) * rr, c[1] + math.sin(2 * math.pi * k / 6 + 0.3) * rr, z)
               for k in range(7)]
        g.tube(pts, 0.5, 0.5, 'string', 0.6, prio=1)


def zigzag(g: Grid, a, b, p: P, n=5, amp=1.8):
    pts = [a]
    for k in range(1, n):
        t = k / n
        q = (a[0] + (b[0] - a[0]) * t + (amp if k % 2 else -amp), a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
        pts.append(q)
    pts.append(b)
    g.tube(pts, 0.6, 0.5, 'glow', 0.9, glow=True, step=0.25, prio=4)


def ice_spikes(g: Grid, pts, p: P, size=3.5):
    for (x, y, z, dx, dy) in pts:
        g.crystal((x, y, z), (dx, dy, 0), size, 0.9, 'ice', glow=p.glow and p.lv >= 4, prio=3)


# ───────────────────────────── theme dressing ─────────────────────────────

def dress_blade(g: Grid, p: P, A):
    """Theme motifs on bladed weapons. A: y0/y1 blade span, hw, guard y/half, top."""
    th, lv = p.theme, p.lv
    y0, y1, hw, gy, gh = A['y0'], A['y1'], A['hw'], A['gy'], A['gh']
    span = y1 - y0
    if lv < 3:
        if lv == 2 and th in ('vine', 'fungi', 'water'):
            vines(g, gy - 1, gy + 5, hw + 1.2, p, n=1, leaves=True, buds=False)
        return
    big = lv >= 4
    if th == 'vine':
        vines(g, gy, y0 + int(span * (0.75 if big else 0.45)), hw + 1.3, p, n=2 if big else 1)
        if big:
            for s in (-1, 1):
                fungi(g, (s * (gh + 1), gy + 2, 0), p, 1.6)
    elif th == 'fungi':
        for k, (x, y) in enumerate(((-gh, gy + 2), (gh, gy + 1), (-hw - 1, y0 + 6), (hw + 1, y0 + 10))):
            fungi(g, (x, y, 0), p, 2.0 if k < 2 else 1.6, up=(0.4 if x > 0 else -0.4, 1, 0))
        if big:
            vines(g, gy, y0 + int(span * 0.6), hw + 1.2, p, n=1, leaves=False)
    elif th == 'web':
        for s in (-1, 1):
            pts = bezier((s * gh, gy, 0), (s * (gh + 2), gy - 2, 0), (s * (gh + 2), gy - 5, 0), (s * (gh - 1), gy - 7, 0), 10)
            g.tube(pts, 1.1, 0.4, 'bone', vfn=lambda t, d, q: 0.45 + 0.45 * t, prio=3)
        if big:
            web(g, (0, y0 + 4, 0), hw + 4, p, z=0)
    elif th == 'water':
        for s in (-1, 1):
            shell(g, (s * (gh + 1), gy + 2, 0.5), p, 2.3)
        if big or p.creature:
            serpent(g, gy - 1, y0 + int(span * 0.72), hw + 1.6, 1.6, p, phase=0.6, rmax=1.5)
        else:
            vines(g, gy, y0 + int(span * 0.4), hw + 1.2, p, n=1, leaves=False)
    elif th == 'forge':
        # glowing cracks across the blade + spikes on the guard
        for s in (-1, 1):
            g.crystal((s * gh, gy + 1, 0), (s, 0.6, 0), 3.5, 0.9, 'metal', prio=3)
        rr = p.rng
        for k in range(5 if big else 3):
            yy = y0 + 3 + rr.randint(0, max(1, span - 8))
            xx = rr.randint(-int(hw) + 1, int(hw) - 1)
            pts = [(xx, yy, 1.2), (xx + rr.choice((-1, 1)), yy + 2, 1.2), (xx, yy + 4, 1.2)]
            g.tube(pts, 0.5, 0.5, 'glow', 0.8, glow=True, prio=4)
            g.tube([(q[0], q[1], -1.2) for q in pts], 0.5, 0.5, 'glow', 0.8, glow=True, prio=4)
        if big:
            flames(g, y0 + 2, y1 - 6, lambda y: A['wfn'](y), p, n=4)
    elif th == 'frost' and p.sig == 'waning':
        _waning_frost(g, p, A)                       # 그믐달: 초승달 등에 옅은 달빛 얼음 조각 (손잡이는 비워 둔다)
    elif th == 'frost':
        ice_spikes(g, [(s * gh, gy + 1, 0, s, 0.9) for s in (-1, 1)] + [(0, gy - 1, 0, 0, -1)], p, 3.2)
        if big:
            for k in range(4):
                yy = y0 + 4 + k * (span - 8) // 4
                s = -1 if k % 2 else 1
                ice_spikes(g, [(s * (A['wfn'](yy) - 0.5), yy, 0, s, 1.1)], p, 3.0)
    elif th == 'crystal':
        for s in (-1, 1):
            crystal_cluster(g, (s * (gh - 1), gy + 1, 0), p, 3, 3.2, 0.9, up=(s * 0.6, 1, 0), glow=big)
        if big:
            for k in range(3):
                yy = y0 + 3 + k * (span // 4)
                s = 1 if k % 2 else -1
                g.crystal((s * A['wfn'](yy), yy, 0), (s, 1.2, 0), 3.4, 0.9, 'crystal', glow=True, prio=3)
    elif th == 'ink':
        ribbon(g, gy - 2, y0 + int(span * (0.7 if big else 0.4)), hw + 1.4, p, turns=1.6 if big else 1.0)
        for s in (-1, 1):
            q = bezier((s * gh, gy + 1, 0), (s * (gh + 2), gy + 3, 0), (s * (gh + 3), gy + 6, 0), (s * (gh + 2), gy + 9, 0), 12)
            g.tube(q, 1.0, 0.45, 'feather', vfn=lambda t, d, q_: 0.5 + 0.35 * t, prio=3)
        if big:
            drips(g, [(-hw, y0 + 8, 0), (hw, y0 + 13, 0), (-hw, y0 + 18, 0)], p)
    elif th == 'clock':
        gear(g, (0, gy + 0.5, 2), 3.6 if big else 3.0, p, 8, mat='orn')
        if big:
            gear(g, (-gh - 1, gy + 3, 0), 2.6, p, 6, mat='metal')
            gear(g, (gh + 1, gy - 1, 0), 2.2, p, 6, mat='metal')
            pts = helix(y0, y0 + int(span * 0.55), hw + 1.2, 3.0, 0.0, zs=0.9)
            g.tube(pts, 0.5, 0.5, 'orn', 0.7, prio=2)
    elif th == 'abyss':
        tendrils(g, (0, gy, 0), p, n=4 if big else 3, length=6, spread=gh + 2, up=-0.5 if not big else 0.8)
        if big or p.creature:
            serpent(g, gy - 2, y0 + int(span * 0.78), hw + 1.6, 1.8, p, phase=2.0, rmax=1.5)
        g.ball((0, gy + 0.5, 1.6), 1.3, 'eye', 0.8, glow=True, prio=5)
    elif th == 'holy':
        for s in (-1, 1):
            wing(g, (s * (gh - 1), gy + 1, 0), s, p, span=7 + 3 * big, rise=10 + 6 * big, n=5 + 2 * big)
    elif th == 'storm':
        for s in (-1, 1):
            wing(g, (s * (gh - 1), gy + 1, 0), s, p, span=6 + 2 * big, rise=8 + 4 * big, n=5)
        if big:
            zigzag(g, (hw + 3, y0 + 4, 0), (hw + 2, y1 - 6, 0), p)
    elif th == 'blood':
        serpent(g, gy - 2, y0 + int(span * 0.8), hw + 1.8, 1.7, p, rmax=1.6)
    if p.creature and th not in ('water', 'abyss', 'blood'):
        serpent(g, gy - 2, y0 + int(span * 0.7), hw + 1.8, 1.6, p, phase=1.2, rmax=1.5)
    if big:
        side = [(-(hw + 5), y0 + span * 0.55, 0), (hw + 5, y0 + span * 0.35, 0)]
        if lv >= 5:
            side.append((hw + 4, y0 + span * 0.8, 0))
            side.append((-(hw + 4), y0 + span * 0.2, 0))
        float_shards(g, side, p, 3.2, 0.85, 'crystal' if th not in ('frost',) else 'ice')
    if lv >= 5:
        for k in range(5):
            a = 2 * math.pi * k / 5 + 0.3
            g.gem((math.cos(a) * (hw + 6), y1 + 2 - k * 1.5, math.sin(a) * 2), 1.0, 'glow', glow=True)


# ───────────────────────────── weapon templates ─────────────────────────────

def _sword(g, p: P, hw, length, grip_len, guard_half, two=False, **bk):
    L = p.L
    length = int(length * L)
    gl = grip_len
    grip(g, -gl // 2, gl // 2)
    pommel(g, -gl // 2 - 2, p, 1.9 if two else 1.6)
    gy = gl // 2 + 1
    crossguard(g, gy, guard_half, p)
    y0 = gy + 2
    blade(g, y0, length, hw, p, **bk)
    tip = bk.get('tip', 0.2)
    taper = bk.get('taper', 0.12)
    wfn = lambda y: hw * (1 - taper * min(1 - tip, (y - y0) / length)) * (
        1 if (y - y0) / length < 1 - tip else max(0.0, (1 - (y - y0) / length) / tip))
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': hw, 'gy': gy, 'gh': guard_half, 'wfn': wfn})


def longsword(g, p):
    _sword(g, p, 3.0 if p.lv < 4 else 3.4, 30, 9, 7 + (p.lv >= 3), tip=0.2)


def broadsword(g, p):
    _sword(g, p, 4.2, 26, 9, 8 + (p.lv >= 3), tip=0.16, taper=0.05, thick=1)


def greatsword(g, p):
    _sword(g, p, 4.6, 40, 15, 10 + (p.lv >= 3), two=True, tip=0.15, thick=2, taper=0.08)


def dagger(g, p):
    _sword(g, p, 2.2, 17, 7, 4 + (p.lv >= 3), tip=0.32, fuller=p.lv >= 2, taper=0.15)


def kris(g, p):
    _sword(g, p, 2.3, 20, 7, 4 + (p.lv >= 3), tip=0.28, wave=1.1, wave_n=5.0, fuller=False, taper=0.25)


def fang_blade(g, p):
    _sword(g, p, 2.6, 19, 7, 3 + (p.lv >= 3), tip=0.45, curve=4.0, fuller=False, taper=0.3, edge_mat='bone'
           if p.theme == 'web' else 'edge')
    if p.lv >= 2:  # serrations along the back edge
        for j in range(8, 20, 3):
            t = (j - 6) / 19
            x = -2.6 * (1 - 0.3 * t) + 4.0 * t * t - 0.6
            g.put(round(x) - 1, j, 0, 'edge', 0.8, prio=2)


def cleaver(g, p):
    L = p.L
    gl = 14
    grip(g, -gl // 2, gl // 2)
    pommel(g, -gl // 2 - 2, p, 1.8)
    gy = gl // 2 + 1
    length = int(30 * L)
    y0 = gy + 1
    # broad asymmetric slab: straight back on −x, bellied edge on +x, chisel tip
    def m(u, v):
        t = (v - y0) / length
        if t < 0 or t > 1:
            return False
        back = -2.5
        edge = 3.5 + 3.2 * math.sin(min(1.0, t * 1.15) * math.pi * 0.85)
        top = 1 - 0.25 * max(0.0, (u - back) / (edge - back + 1e-6))
        if t > top:
            return False
        if p.lv >= 2 and 0.15 < t < 0.3 and abs(u - 1.5) < 1.0:
            return False  # hanging hole
        return back <= u <= edge
    g.slab(m, (-4, y0), (8, y0 + length), 'xy', 0, max_half=1, slope=0.5, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.7) if d == 0 and u > 0 else 0.4 + 0.08 * min(d, 3) + 0.04 * w)
    # spine
    g.box((-3, y0, -1), (-3, y0 + int(length * 0.82), 1), 'metal', 0.6, prio=2)
    g.box((-2, gy - 1, -1), (2, gy, 1), 'metal', 0.5)
    hw = 4
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': hw, 'gy': gy, 'gh': 3, 'wfn': lambda y: 5.0})


def great_axe(g, p):
    L = p.L
    top = int(32 * L)
    shaft(g, -16, top, 1.25, 'wood', bands=(-6, 6, top - 14))
    pommel(g, -18, p, 1.6)
    grip(g, -5, 5)
    hy = top - 7
    double = p.lv >= 3 or 'reaver' in p.iid or 'geode' in p.iid

    def blade_mask(s):
        def m(u, v):
            x = u * s
            if x < 1:
                return False
            dy = v - hy
            # crescent: outer arc radius 10 centred inward, inner cut
            ox = x - 1
            reach = 12.5 if p.lv >= 4 else 10.0
            hh = 3.5 + ox * 0.95
            if ox > reach:
                return False
            if abs(dy) > hh:
                return False
            cut = (ox - reach - 4.5) ** 2 + dy * dy < 6.0 ** 2 and ox > reach - 1.5
            if 'reaver' in p.iid or p.theme in ('holy', 'storm', 'blood'):
                # wing-shaped: scalloped feather notches on the lower edge
                if dy < -hh + 1.6 and int(ox) % 3 == 2:
                    return False
            return not cut
        return m

    for s in ((-1, 1) if double else (1,)):
        g.slab(blade_mask(s), (-16, hy - 16), (16, hy + 16), 'xy', 0, max_half=1, slope=0.34, mat='blade',
               vfn=lambda u, v, w, d: ('edge', 0.72 + 0.1 * (w == 0)) if d <= 0 and abs(u) > 4 else
               0.38 + 0.07 * min(d, 4) + 0.03 * w)
        # inlay line
        if p.lv >= 2:
            for v in range(hy - 3, hy + 4):
                g.put(s * 3, v, 1, 'orn', 0.7, prio=2)
                g.put(s * 3, v, -1, 'orn', 0.7, prio=2)
    if not double:
        g.crystal((-1, hy, 0), (-1, -0.3, 0), 5.0, 1.2, 'metal', prio=2)  # back spike
    g.crystal((0, top, 0), (0, 1, 0), 6.0, 1.3, 'metal', prio=2)  # top spike
    g.ball((0, hy, 0), 2.2, 'metal', 0.55, prio=2)
    if p.lv >= 2:
        g.gem((0, hy, 2), 1.2, 'gem', glow=p.glow)
        g.gem((0, hy, -2), 1.2, 'gem', glow=p.glow)
    dress_shaft(g, p, -4, hy - 3, hy, top)


def mace(g, p):
    L = p.L
    top = int(16 * L)
    shaft(g, -6, top, 1.25, 'metal' if p.lv >= 2 else 'wood', bands=(top - 2,))
    grip(g, -6, 4)
    pommel(g, -8, p, 1.5)
    hy = top + 4
    g.ball((0, hy, 0), 3.6, 'metal', vfn=lambda i, j, k, d: 0.32 + 0.4 * (1 - d) + 0.1 * (j > hy))
    # flanges
    for k in range(6):
        a = 2 * math.pi * k / 6
        dx, dz = math.cos(a), math.sin(a)
        def m(u, v, dx=dx):
            return abs(v - hy) <= 4 - u * 0.4 and 0 <= u <= 5
        for u in range(0, 6):
            for v in range(hy - 5, hy + 6):
                if m(u, v):
                    g.put(round(dx * (u + 1.5)), v, round(dz * (u + 1.5)), 'blade' if p.theme != 'clock' else 'orn',
                          0.45 + 0.08 * u, prio=2)
    g.crystal((0, hy + 3, 0), (0, 1, 0), 4.0, 1.2, 'metal', prio=2)
    if p.lv >= 2:
        g.torus((0, hy - 4, 0), 2.6, 0.6, 'y', 'orn', 0.7)
    if p.theme == 'clock':
        gear(g, (0, hy, 0), 4.2, p, 10, 'xy', 'orn')
    if p.theme == 'water':
        for s in (-1, 1):
            shell(g, (s * 5, hy - 5, 0), p, 2.0)
    if p.lv >= 3:
        dress_shaft(g, p, -4, hy - 6, hy, hy + 5)


def dress_shaft(g, p: P, y0, y1, hy, top):
    """Motifs for hafted weapons (axes, staves): coils/vines/crystals climbing the shaft + head extras."""
    th, lv = p.theme, p.lv
    if lv < 3:
        return
    big = lv >= 4
    if th in ('vine', 'fungi'):
        vines(g, y0, y1, 1.8, p, n=2 if big else 1)
        if th == 'fungi':
            fungi(g, (-2, y0 + 6, 0), p, 1.8, up=(-0.5, 1, 0))
            fungi(g, (2, y0 + 12, 0), p, 1.6, up=(0.5, 1, 0))
    elif th == 'crystal':
        # crystals erupting along the haft (growth)
        rr = p.rng
        for k, yy in enumerate(range(y0 + 1, y1, 3 if big else 5)):
            for s in ((-1, 1) if big else (1 if k % 2 else -1,)):
                a = rr.random() * 6.28
                d = (s * (0.6 + rr.random()), 1.0 + rr.random() * 0.6, math.sin(a) * 0.7)
                g.crystal((s * 1, yy + rr.randint(0, 1), math.cos(a) * 0.8), d, 2.2 + rr.random() * 2.2, 0.75 + 0.3 * rr.random(),
                          'crystal', glow=big and rr.random() < 0.5, prio=3)
        # 태산·새벽 종(0.3.7): 머리 위는 봉우리·종 고리 자리, 결정 테마의 보라 덩굴은 짝 색과 안 맞아 뺀다
        if big and p.sig not in ('mountainheart', 'daybreak'):
            vines(g, y0, y1, 1.9, p, n=1, leaves=False, buds=True)
            crystal_cluster(g, (0, top + 1, 0), p, 4, 5.0, 1.3, glow=True)
    elif th in ('water',):
        serpent(g, y0, y1, 2.4, 2.2, p, rmax=1.3)
    elif th in ('abyss', 'blood'):
        if big or p.creature:
            serpent(g, y0, y1 + 2, 2.6, 2.4, p, rmax=1.5)
        tendrils(g, (0, hy - 6, 0), p, n=4, length=5, spread=4, up=-0.6)
    elif th == 'clock':
        pts = helix(y0, y1, 2.0, (y1 - y0) / 3.0, 0.0)
        g.tube(pts, 0.5, 0.5, 'orn', 0.75, prio=2)
        if big:
            gear(g, (0, hy, 2), 3.2, p, 8, 'xy', 'orn')
    elif th == 'forge':
        for k, yy in enumerate(range(y0 + 3, y1, 6)):
            g.put(0, yy, 2, 'glow', 0.8, glow=True, prio=3)
            g.put(0, yy, -2, 'glow', 0.8, glow=True, prio=3)
        if big:
            flames(g, hy - 4, hy + 4, lambda y: 3.0, p, n=3)
    elif th == 'frost':
        ice_spikes(g, [(s * 1.5, yy, 0, s, 1.0) for s, yy in ((1, y1 - 2), (-1, y1 - 6), (1, y1 - 10))], p, 3.0)
    elif th == 'ink':
        ribbon(g, y0, y1, 2.4, p, turns=2.4)
    elif th in ('holy', 'storm'):
        for s in (-1, 1):
            wing(g, (s * 2, hy - 2, 0), s, p, span=6 + 2 * big, rise=7 + 3 * big, n=5)
    own_halo = False
    if big and p.sig in SIG_FLOATERS:
        own_halo = SIG_FLOATERS[p.sig](g, p, hy, top)
    elif big:
        float_shards(g, [(-7, hy + 6, 0), (7, hy - 6, 0)] + ([(0, top + 8, 0)] if lv >= 5 else []), p, 3.0, 0.85)
    if lv >= 5 and not own_halo:
        dy, hr = SIG_HALO.get(p.sig, (0, 9.0))
        halo(g, (0, hy + dy, 0), hr, 'z')


# staves & scepters ---------------------------------------------------------

def _staff_base(g, p, top, mat='wood'):
    shaft(g, -18, top, 1.25, mat, bands=(-10, 0, top - 2))
    g.crystal((0, -18, 0), (0, -1, 0), 3.0, 1.2, 'metal', prio=2)
    grip(g, -4, 4, mat='grip')


def staff_orb(g, p):
    top = int(28 * p.L)
    _staff_base(g, p, top)
    cy = top + 6
    R = 3.4 if p.lv < 4 else 4.0
    g.ball((0, cy, 0), R, 'glow' if p.lv >= 1 else 'gem', glow=True,
           vfn=lambda i, j, k, d: 0.35 + 0.55 * (1 - d) + (0.15 if (i + j) < cy - 2 else 0), prio=3)
    # cage prongs
    n = 4 if p.lv < 3 else 6
    for k in range(n):
        a = 2 * math.pi * k / n + 0.4
        dx, dz = math.cos(a), math.sin(a)
        pts = catmull([(0, top - 1, 0), (dx * (R + 1.2), cy - R + 0.5, dz * (R + 1.2)),
                       (dx * (R + 1.6), cy + 0.5, dz * (R + 1.6)), (dx * (R * 0.4), cy + R + 2.2, dz * (R * 0.4))], 6)
        g.tube(pts, 0.75, 0.55, 'orn' if p.lv >= 2 else 'wood', vfn=lambda t, d, q: 0.45 + 0.3 * (1 - d) + 0.1 * t, prio=2)
    if p.lv >= 2:
        g.crystal((0, cy + R + 1.6, 0), (0, 1, 0), 3.0, 0.9, 'gem', glow=p.glow, prio=4)
    if p.theme == 'clock':
        g.torus((0, cy, 0), R + 2.5, 0.5, 'y', 'orn', 0.7)
        g.torus((0, cy, 0), R + 3.5, 0.5, 'z', 'metal', 0.6)
        for k in range(3):
            a = 2 * math.pi * k / 3
            g.ball((math.cos(a) * (R + 2.5), cy, math.sin(a) * (R + 2.5)), 1.0, 'gem', 0.7, prio=4)
    if p.theme == 'abyss' and p.lv >= 4:
        for ax in ('y', 'z', 'x'):
            g.torus((0, cy, 0), R + 3.0, 0.5, ax, 'glow', 0.8, glow=True, prio=4)
        tendrils(g, (0, cy - R, 0), p, n=5, length=7, spread=6, up=-0.8)
    dress_shaft(g, p, -6, top - 4, cy, cy + R)


def staff_crystal(g, p):
    top = int(28 * p.L)
    _staff_base(g, p, top)
    cy = top + 2
    # claw holding the crystal
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.78
        dx, dz = math.cos(a), math.sin(a)
        pts = catmull([(0, top - 2, 0), (dx * 2.5, top + 1, dz * 2.5), (dx * 2.2, top + 5, dz * 2.2), (dx * 1.0, top + 7, dz)], 5)
        g.tube(pts, 0.8, 0.5, 'orn' if p.lv >= 2 else 'metal', vfn=lambda t, d, q: 0.5 + 0.3 * t, prio=2)
    mat = 'ice' if p.theme == 'frost' else 'crystal'
    g.crystal((0, cy, 0), (0, 1, 0), 11 + 2 * (p.lv >= 4), 2.1, mat, glow=p.glow, prio=3, tip=0.4)
    if p.lv >= 2:
        for k in range(3 + (p.lv >= 4) * 2):
            a = 2 * math.pi * k / (3 + (p.lv >= 4) * 2)
            g.crystal((math.cos(a) * 1.2, cy + 1, math.sin(a) * 0.8), (math.cos(a) * 0.6, 1, math.sin(a) * 0.4), 5.0, 1.0,
                      mat, glow=p.glow, prio=3)
    if p.theme == 'forge':
        flames(g, top - 1, top + 3, lambda y: 2.0, p, n=2)
    dress_shaft(g, p, -6, top - 4, cy + 5, cy + 12)


def staff_ring(g, p):
    top = int(26 * p.L)
    _staff_base(g, p, top)
    cy = top + 7
    R = 6.0
    g.torus((0, cy, 0), R, 1.1, 'z', 'orn' if p.lv >= 1 else 'wood', vfn=lambda t, d, q: 0.45 + 0.35 * (1 - d))
    g.ball((0, cy, 0), 1.9, 'gem', glow=True, vfn=lambda i, j, k, d: 0.5 + 0.45 * (1 - d), prio=3)
    for k in range(6 if p.lv >= 2 else 3):
        a = 2 * math.pi * k / (6 if p.lv >= 2 else 3) + math.pi / 2
        g.gem((math.cos(a) * R, cy + math.sin(a) * R, 1), 0.9, 'gem', glow=p.glow)
    if p.theme == 'clock' or 'tesla' in p.iid:
        pts = helix(top - 8, top, 2.3, 4.0, 0.0)
        g.tube(pts, 0.6, 0.6, 'orn', 0.7, prio=3)
        if p.lv >= 4:
            for k in range(4):
                a = 2 * math.pi * k / 4 + 0.4
                zigzag(g, (math.cos(a) * 2, cy + math.sin(a) * 2, 0), (math.cos(a) * (R - 1), cy + math.sin(a) * (R - 1), 0),
                       p, n=3, amp=0.8)
    if p.theme == 'fungi':
        for k in range(3):
            a = 2 * math.pi * k / 3 + 1.2
            fungi(g, (math.cos(a) * R, cy + math.sin(a) * R, 0), p, 1.7, up=(math.cos(a), math.sin(a), 0))
    if p.theme == 'crystal':
        for k in range(4):
            a = 2 * math.pi * k / 4 + 0.78
            g.crystal((math.cos(a) * R, cy + math.sin(a) * R, 0), (math.cos(a), math.sin(a), 0), 3.4, 0.9, 'crystal',
                      glow=p.glow, prio=3)
    dress_shaft(g, p, -6, top - 4, cy, cy + R)


def scepter(g, p):
    top = int(14 * p.L)
    shaft(g, -8, top, 1.25, 'orn' if p.lv >= 2 else 'wood', bands=(-2, top - 1))
    grip(g, -7, 2)
    pommel(g, -10, p, 1.4)
    cy = top + 4
    # flanged crown
    for k in range(5):
        a = 2 * math.pi * k / 5
        dx, dz = math.cos(a), math.sin(a)
        pts = catmull([(dx * 1.0, top, dz), (dx * 3.2, top + 2.5, dz * 3.2), (dx * 2.8, top + 6, dz * 2.8),
                       (dx * 1.0, top + 8, dz * 1.0)], 5)
        g.tube(pts, 0.8, 0.5, 'orn', vfn=lambda t, d, q: 0.5 + 0.3 * (1 - d), prio=2)
    g.gem((0, cy + 0.5, 0), 2.2, 'gem', glow=True)
    g.crystal((0, top + 7, 0), (0, 1, 0), 4.0, 1.0, 'gem', glow=p.glow, prio=4)
    if p.theme in ('forge', 'holy') and p.lv >= 3:
        flames(g, top + 2, top + 6, lambda y: 3.2, p, n=2)
    if p.theme == 'crystal' and p.lv >= 2:
        for s in (-1, 1):
            g.crystal((s * 3, cy, 0), (s * 0.8, 1, 0), 5.0, 1.0, 'crystal', glow=p.glow, prio=3)
            g.ball((s * 5, cy + 6, 0), 1.4, 'glow', 0.9, glow=True, prio=4)
    dress_shaft(g, p, -6, top - 2, cy, top + 11)


def sun_scepter(g, p):
    top = int(16 * p.L)
    shaft(g, -8, top, 1.25, 'orn', bands=(-2, top - 1))
    grip(g, -7, 2)
    pommel(g, -10, p, 1.4)
    cy = top + 6
    rays = 8 if p.lv < 4 else 12
    for k in range(rays):
        a = 2 * math.pi * k / rays + math.pi / 2
        ln = 6.5 if k % 2 == 0 else 4.5
        g.crystal((math.cos(a) * 2.5, cy + math.sin(a) * 2.5, 0), (math.cos(a), math.sin(a), 0), ln, 1.0,
                  'orn', prio=2, tip=0.7)
    g.torus((0, cy, 0), 3.4, 0.8, 'z', 'orn', 0.7)
    g.ball((0, cy, 0), 2.5, 'glow', glow=True, vfn=lambda i, j, k, d: 0.5 + 0.45 * (1 - d), prio=3)
    if 'seraph' in p.iid:
        for s in (-1, 1):
            for k, (sp, ri, dr) in enumerate(((9, 9, 0), (8, 4, 25), (6, -2, 50))):
                wing(g, (s * 2.5, cy - 2 - k * 1.5, -1 + k), s, p, span=sp, rise=ri + 3, n=5, droop=dr)
    elif 'aurora' in p.iid:
        for s in (-1, 1):
            pts = catmull([(s * 3, cy - 3, 0), (s * 7, cy + 1, 1), (s * 6, cy + 7, -1), (s * 9, cy + 11, 0)], 6)
            g.tube(pts, 1.2, 0.5, 'glow', glow=True, sq=(1, 1, 0.6), vfn=lambda t, d, q: 0.5 + 0.4 * t, prio=3)
    elif 'bloom' in p.iid:
        for k in range(6):
            a = 2 * math.pi * k / 6
            g.ball((math.cos(a) * 3.6, cy + math.sin(a) * 3.6, 1), 1.6, 'fungus', sq=(1, 1, 0.5),
                   vfn=lambda i, j, k_, d: 0.4 + 0.4 * (1 - d), prio=3)
    if p.theme == 'holy' and p.lv >= 3 and 'seraph' not in p.iid and 'aurora' not in p.iid:
        for s in (-1, 1):
            wing(g, (s * 2, cy - 3, 0), s, p, span=6, rise=6, n=4)
    if p.lv >= 4:
        float_shards(g, [(-8, cy - 6, 0), (8, cy - 4, 0)], p, 2.8, 0.8, 'glow')
    if p.lv >= 5:
        halo(g, (0, cy + 2, 0), 9.5, 'z')


def censer_staff(g, p):
    top = int(28 * p.L)
    _staff_base(g, p, top, 'metal' if p.lv >= 2 else 'wood')
    # hook arching over to the front (+x)
    hook = catmull([(0, top, 0), (1, top + 4, 0), (4, top + 6, 0), (7, top + 4, 0), (7.5, top + 1, 0)], 6)
    g.tube(hook, 1.1, 0.8, 'orn' if p.lv >= 1 else 'metal', vfn=lambda t, d, q: 0.45 + 0.3 * (1 - d))
    # chain links
    for k in range(3):
        y = top - k * 2
        g.torus((7.5, y, 0), 0.9, 0.5, 'z' if k % 2 else 'x', 'metal', 0.6)
    ly = top - 9
    # lantern / bell / pendulum cage
    if p.theme == 'water':
        g.ball((7.5, ly, 0), 3.2, 'metal', sq=(1, 1.1, 1), vfn=lambda i, j, k, d: None if d < 0.72 and j < ly - 1 else
               0.35 + 0.3 * (1 - d) + 0.15 * (j > ly), prio=2)
        g.ball((7.5, ly - 2.6, 0), 1.0, 'glow', 0.9, glow=True, prio=3)
    elif p.theme == 'clock':
        g.box((5, ly - 3, -2), (10, ly + 3, 2), 'metal', vfn=lambda i, j, k: 0.5 if abs(i - 7.5) > 2 or abs(k) == 2 else None)
        gear(g, (7.5, ly, 3), 2.4, p, 6, 'xy', 'orn')
        g.tube([(7.5, ly + 2, 0), (7.5 + 2, ly - 4, 0)], 0.5, 0.5, 'orn', 0.8, prio=3)
        g.ball((9.5, ly - 4.5, 0), 1.2, 'gem', 0.8, glow=True, prio=3)
    else:
        def cage(i, j, k):
            dx, dz = i - 7.5, k
            if abs(j - ly) >= 3:
                return 0.55
            return 0.5 if (abs(dx) >= 2.5 and abs(dz) >= 1.5) or (abs(dx) >= 2.5 and dz == 0 and False) else None
        g.box((5, ly - 3, -2), (10, ly + 3, 2), 'metal', vfn=lambda i, j, k: 0.55 if abs(j - ly) >= 3 or
              (abs(i - 7.5) >= 2.4 and abs(k) >= 2) else None)
        g.ball((7.5, ly, 0), 1.8, 'glow', glow=True, vfn=lambda i, j, k, d: 0.55 + 0.4 * (1 - d), prio=3)
        g.crystal((7.5, ly + 3, 0), (0, 1, 0), 2.2, 1.6, 'orn', prio=2)
    if p.theme == 'crystal':
        g.crystal((7.5, ly - 3, 0), (0, -1, 0), 3.5, 1.0, 'crystal', glow=p.glow, prio=3)
    if p.lv >= 3:
        for k in range(3):
            g.ball((7.5 + (k - 1) * 1.6, ly + 5 + k * 2, 0), 0.9 + 0.3 * k, 'glow' if p.glow else 'string', 0.6,
                   glow=p.glow, prio=1)
    dress_shaft(g, p, -6, top - 6, top, top + 6)


# bows ------------------------------------------------------------------------

BOW_CURV = {'longbow': 3.0, 'recurve_bow': 4.0, 'composite_bow': 4.6, 'horn_bow': 3.6, 'blade_bow': 3.0,
            'bone_bow': 3.4, 'twin_bow': 3.2}


def _bone_limb(g, p, pts, s):
    """뼈 활 팔: 매끈한 관 대신 등뼈 마디 (t 0.08 간격 마디 + 가는 이음), lv≥2 마디 뒤로 힘줄 한 줄."""
    n = len(pts) - 1
    g.tube(pts, 0.8, 0.7, 'bone', vfn=lambda t, d, q: 0.3 + 0.2 * (1 - d), prio=2)            # thin core between joints
    t = 0.05
    while t <= 0.97:
        q = pts[min(n, int(round(t * n)))]
        g.ball(q, 1.7 - 0.4 * t, 'bone', sq=(1.15, 0.55, 1.0), prio=3,
               vfn=lambda i, j, kk, d, q=q: 0.46 + 0.35 * (1 - d) + (0.1 if j > q[1] else 0))
        t += 0.13
    if p.lv >= 2:
        g.tube([(q[0] - 1.3, q[1], 0) for q in pts[1:19]], 0.5, 0.4, 'string', 0.55, prio=2)


def _twin_limbs(g, p, pts, s, th, mat):
    """쌍현 활 팔: 같은 곡선을 z = +1.6 (긴 쪽) · −1.6 (y × 0.88, 활 등 쪽으로 1.8) 두 겹으로, 끝·손잡이 위아래를 다리로 잇는다.
    → 안쪽 겹의 점 목록."""
    a = [(q[0], q[1], 1.6) for q in pts]
    b = [(q[0] - 1.8, q[1] * 0.88, -1.6) for q in pts]          # inner pair: shorter, set back → two arcs side by side
    for lay in (a, b):
        g.tube(lay, th, 0.55, mat, sq=(1, 1, 0.8), vfn=lambda t, d, q: 0.38 + 0.3 * (1 - d) + 0.06 * math.sin(t * 30),
               prio=2)
    for k in (3, 20):                  # bridges: above the riser and at the tips
        qa, qb = a[k], b[k]
        g.tube([qa, qb], 0.9, 0.9, 'orn' if p.lv >= 1 else 'metal', 0.6, prio=3)
    g.ball(a[-1], 1.0, 'orn' if p.lv >= 1 else 'metal', 0.6, prio=3)
    g.ball(b[-1], 0.9, 'orn' if p.lv >= 1 else 'metal', 0.6, prio=3)
    if p.lv >= 3:                      # light thread between the layers
        g.tube([((qa[0] + qb[0]) / 2, (qa[1] + qb[1]) / 2, 0) for qa, qb in zip(a[4:19], b[4:19])], 0.5, 0.5, 'glow', 0.8,
               glow=True, prio=2)
    return b


def bow(g, p, kind, pull=-1):
    """Limbs along Y, tips toward +X (string side); grip at the origin.  pull −1 resting, 0..2 drawing."""
    L = p.L
    H = int(17 * L)
    f = (pull + 1) / 3.0 if pull >= 0 else 0.0
    curv = BOW_CURV[kind] * (1 + 0.55 * f)
    th = {'composite_bow': 1.6, 'horn_bow': 1.6, 'bone_bow': 1.4, 'twin_bow': 1.1}.get(kind, 1.3)
    if kind == 'horn_bow':
        H = int(15 * L)
    limb_mat = 'wood' if p.theme not in ('crystal', 'storm', 'water') or p.lv < 2 else 'metal'
    if p.sig == 'comet':
        limb_mat = 'dark'                             # 꼬리별: 밤하늘 남색 팔 (빛 줄이 위에서 읽힌다)
    tips = []
    tips_b = []                       # twin_bow: the second (inner, shorter) pair of limbs at z = −1.6
    for s in (1, -1):
        pts = []
        for k in range(0, 21):
            t = k / 20
            y = s * (2.5 + (H - 2.5) * t)
            x = curv * t * t * (1.0 + 0.2 * f) - 0.6
            if kind == 'recurve_bow' and t > 0.78:
                x -= (t - 0.78) * 14 * (1 - 0.4 * f)
            if kind == 'horn_bow':
                # 각궁: limbs dip back toward the archer near the grip (reflex), ears snap sharply back at the tips
                x -= 1.8 * math.sin(math.pi * min(1.0, t / 0.7)) * (1 - 0.5 * f)
                if t > 0.8:
                    x -= (t - 0.8) * 22 * (1 - 0.35 * f)
            pts.append((x, y, 0))
        if kind == 'bone_bow':
            _bone_limb(g, p, pts, s)
        elif kind == 'twin_bow':
            pts_b = _twin_limbs(g, p, pts, s, th, limb_mat)
            pts = [(q[0], q[1], 1.6) for q in pts]
            tips_b.append(pts_b[-1])
        else:
            g.tube(pts, th, 0.6, limb_mat, sq=(1, 1, 0.8),
                   vfn=lambda t, d, q: 0.38 + 0.3 * (1 - d) + 0.06 * math.sin(t * 30), prio=2)
        if kind == 'composite_bow':
            g.tube([(q[0] - 1.2, q[1], q[2]) for q in pts[2:15]], 0.6, 0.5, 'orn' if p.lv >= 1 else 'bone', 0.65, prio=2)
        if kind == 'horn_bow':
            # horn belly strip + bone ears (siyah)
            g.tube([(q[0] + 1.0, q[1], q[2]) for q in pts[2:16]], 0.6, 0.5, 'bone', 0.6, prio=2)
            g.tube(pts[16:], 1.2, 0.8, 'bone', 0.7, prio=3)
        if kind == 'blade_bow':
            # blade fins along the back of each limb, edge facing away from the string
            for k in range(5, 18):
                t = k / 20
                fw = 3.4 * math.sin(math.pi * (t - 0.25) / 0.65) * (1 - 0.3 * f)
                if fw <= 0.4:
                    continue
                qx, qy, _ = pts[k]
                for d in range(1, int(round(fw)) + 1):
                    edge = d == int(round(fw))
                    g.put(round(qx - 1 - d), round(qy), 0, 'edge' if edge else 'blade', 0.75 if edge else 0.45 + 0.05 * d, prio=2)
            g.crystal(pts[-1], (-0.3, s, 0), 3.2, 0.9, 'edge', prio=3)
        tip = pts[-1]
        tips.append(tip)
        if kind == 'bone_bow':
            # rib hook: the limb end curls back in toward the string like a rib
            g.crystal(tip, (0.6, s, 0), 3.0, 0.8, 'bone', prio=3, tip=0.6)
            if p.lv >= 2:
                g.gem((tip[0] - 0.6, tip[1] - s * 1.2, 1), 0.8, 'gem', glow=p.glow)
            continue
        g.ball(tip, 1.1, 'orn' if p.lv >= 1 else 'metal', 0.6, prio=3)
        if p.lv >= 2 and kind != 'twin_bow':
            g.crystal(tip, (0.4, s, 0), 2.5, 0.8, 'gem', glow=p.glow, prio=3)
    # riser / grip
    zr = 2 if kind == 'twin_bow' else 1
    g.box((-2, -3, -zr), (0, 3, zr), 'grip', vfn=lambda i, j, k: 0.6 if (j + i) % 3 == 0 else 0.4, prio=3)
    g.box((-3, -1, -zr), (-3, 1, zr), 'orn' if p.lv >= 1 else 'metal', 0.6, prio=3)
    if kind == 'bone_bow':
        g.box((-2, -2, -1), (0, 2, 1), 'leather', vfn=lambda i, j, k: 0.55 if j % 2 else 0.4, prio=4)   # hide wrap
        if p.lv >= 3:                  # little skull on the back of the riser
            g.ball((-4.2, 0, 0), 2.0, 'bone', vfn=lambda i, j, k, d: 0.4 + 0.35 * (1 - d) + 0.1 * (j > 0), prio=4)
            for sz in (-1, 1):
                g.put(-6, 0, sz, 'eye' if p.theme in ('abyss', 'forge') else 'dark', 0.8, glow=p.theme in ('abyss', 'forge'),
                      prio=5)
    if kind == 'blade_bow':
        g.crystal((-3, 0, 0), (-1, 0, 0), 4.0, 1.4, 'edge', prio=3, tip=0.7)   # knuckle blade
    if kind == 'horn_bow':
        g.box((-2, -2, -1), (0, 2, 1), 'leather', 0.5, prio=4)                 # wrapped grip
    if p.sig == 'comet':
        _comet_head(g, p, H, curv)                    # 혜성 머리 보석 + 두 팔을 따라 곧은 빛 줄 셋
    elif p.lv >= 2:
        g.gem((-3, 0, 1), 1.0, 'gem', glow=p.glow)
    smat, sval = ('orn', 0.78) if p.sig == 'comet' else ('string', 0.7)     # 꼬리별: 옅은 금빛 시위
    # string (twin_bow: one per limb pair, z = ±1)
    (ux, uy, _), (lx, ly, _) = tips
    sx = max(ux, lx)
    strings = [((ux, uy), (lx, ly), 0.0)]
    if kind == 'twin_bow':
        (bux, buy, _), (blx, bly, _) = tips_b
        strings = [((ux, uy), (lx, ly), 1.0), ((bux, buy), (blx, bly), -1.0)]
        sx = max(sx, bux, blx)
    nx = sx + 3 + 2.5 * pull
    for (a, b, z) in strings:
        if pull < 0:
            g.tube([(sx, a[1], z), (sx, b[1], z)], 0.5, 0.5, smat, sval, prio=1)
        else:
            g.tube([(a[0], a[1], z), (nx, 0, z), (b[0], b[1], z)], 0.5, 0.5, smat, sval, prio=1)
    if kind == 'twin_bow' and p.lv >= 2:
        g.torus((sx if pull < 0 else nx, 0, 0), 1.1, 0.5, 'y', 'orn', 0.7, prio=3)       # jewel ring between the strings
        g.gem((sx if pull < 0 else nx, 0, 0), 0.8, 'gem', glow=p.glow)
    if pull >= 0:
        # arrow
        g.tube([(nx, 0, 0), (-8, 0, 0)], 0.5, 0.5, 'wood', 0.5, prio=4)
        g.crystal((-8, 0, 0), (-1, 0, 0), 2.6, 1.0, 'edge' if not p.glow else 'glow', glow=p.glow, prio=5)
        for s in (-1, 1):
            g.tube([(nx - 0.5, 0, 0), (nx - 3, s * 1.3, 0)], 0.5, 0.5, 'feather', 0.7, prio=4)
    dress_bow(g, p, H, curv, tips)


def dress_bow(g, p: P, H, curv, tips):
    th, lv = p.theme, p.lv
    if lv < 3:
        if lv == 2 and th in ('vine', 'fungi'):
            vines(g, 2, H - 4, 1.6, p, n=1, leaves=True, buds=False)
        return
    big = lv >= 4
    if th in ('vine', 'fungi'):
        for s in (1, -1):
            pts = [(curv * (k / 10) ** 2 - 0.6 + math.sin(k) * 0.9, s * (2.5 + (H - 2.5) * k / 10), math.cos(k * 1.3))
                   for k in range(1, 9)]
            g.tube(pts, 0.6, 0.5, 'vine', 0.5, prio=3)
        if th == 'fungi':
            fungi(g, (-2.0, 6, 0), p, 1.5, up=(-0.6, 1, 0))
            fungi(g, (-2.0, -7, 0), p, 1.5, up=(-0.6, -1, 0))
    elif th == 'water':
        for s in (1, -1):
            shell(g, (-2.5, s * 6.5, 0.5), p, 2.0)
            pts = [(curv * (k / 10) ** 2 - 2.0, s * (3 + (H - 3) * k / 10), 0) for k in range(1, 10)]
            g.tube(pts, 0.7, 0.4, 'gem', 0.6, prio=1)
        if big:
            serpent(g, -H + 4, H - 6, 2.0, 2.4, p, rmax=1.2)
    elif th == 'storm':
        for s in (1, -1):
            wing(g, (-1.5, s * 3, 0), -1, p, span=7 + 2 * big, rise=s * (H - 5), n=6)
        if big:
            zigzag(g, (-9, -H + 6, 0), (-9, H - 6, 0), p, n=7, amp=1.6)
    elif th == 'clock':
        gear(g, (-3, 0, 2), 3.0, p, 8, 'xy', 'orn')
        for s in (1, -1):
            pts = helix(s * 4, s * (H - 4), 1.8, 3.0, 0.0)
            g.tube([(q[0] + curv * 0.15, q[1], q[2]) for q in pts], 0.5, 0.5, 'orn', 0.7, prio=1)
    elif th == 'forge':
        for s in (1, -1):
            for k in range(3):
                y = s * (5 + k * 4)
                t = (abs(y) - 2.5) / (H - 2.5)
                g.put(round(curv * t * t - 0.6), y, 1, 'glow', 0.8, glow=True, prio=4)
        if p.sig != 'comet':                          # 꼬리별은 손잡이 앞이 혜성 머리 자리
            gear(g, (-3, 0, 2), 2.6, p, 6, 'xy', 'metal')
    elif th == 'crystal':
        for s in (1, -1):
            g.crystal((-1.5, s * 7, 0), (-1, s * 0.6, 0), 4.0, 1.0, 'crystal', glow=big, prio=3)
    elif th in ('abyss', 'blood'):
        tendrils(g, (-2, 0, 0), p, n=4, length=4, spread=6, up=0.2)
    elif th == 'holy':
        for s in (1, -1):
            wing(g, (-1.5, s * 3, 0), -1, p, span=6, rise=s * (H - 6), n=5)
    elif th == 'web':
        web(g, (-3, 0, 0), 5, p)
    if big and p.sig == 'comet':
        _star_glints(g, [(-10, 8, 0), (-10, -8, 0)] + ([(-13, 0, 0)] if lv >= 5 else []))
    elif big:
        float_shards(g, [(-7, 8, 0), (-7, -8, 0)] + ([(-10, 0, 0)] if lv >= 5 else []), p, 2.8, 0.8,
                     'glow' if th == 'storm' else 'crystal')
    if lv >= 5:
        halo(g, (-2, 0, 0), 6.0, 'x')


# second wave (5층 + 층마다 하나 더) -------------------------------------------
# 새 실루엣 12종: 무기 종류마다 2개. 기존 15종과 겹치지 않는 윤곽(망치 머리·외날·낫·언월도·각궁·날활·
# 소용돌이·갈래·종·성배·낫단검·주먹칼)이 먼저 읽히고, 테마 장식(dress_*)은 영웅부터 얹힌다.

def _face_cracks(g, p, x, y0, y1, z):
    """Glowing forge cracks on a flat face (forge theme)."""
    rr = p.rng
    for _ in range(2 + (p.lv >= 3)):
        yy = rr.randint(y0, max(y0, y1 - 3))
        pts = [(x, yy, z), (x, yy + 1, z + rr.choice((-1, 1))), (x, yy + 3, z)]
        g.tube(pts, 0.5, 0.5, 'glow', 0.85, glow=True, prio=4)


def warhammer(g, p):
    """One-handed war hammer: bevelled block head (striking face +x, pick −x), top spike."""
    L, th = p.L, p.theme
    top = int(17 * L)
    shaft(g, -6, top, 1.25, 'metal' if p.lv >= 2 else 'wood', bands=(top - 3,))
    grip(g, -6, 4)
    pommel(g, -8, p, 1.5)
    hy = top + 3
    if th == 'fungi':
        # mushroom-cap head with gills underneath and pale spots
        g.ball((0, hy + 1, 0), 5.4, 'fungus', sq=(1, 0.62, 1),
               vfn=lambda i, j, k, d: None if j < hy - 0.5 else 0.32 + 0.45 * (1 - d) + 0.1 * (j > hy + 2))
        g.torus((0, hy - 0.5, 0), 3.6, 0.7, 'y', 'bone', 0.45)
        for (a, b) in ((2, 3), (-3, 2), (0, -3), (3, -2)):
            g.put(a, hy + 3, b, 'bone', 0.85, prio=4)
    elif th == 'ink':
        # seal stamp: drum head, engraved glowing face on +x
        for j in range(hy - 3, hy + 4):
            for i in range(-3, 7):
                for k in range(-3, 4):
                    if (j - hy) ** 2 + k * k <= 10.5:
                        g.put(i, j, k, 'metal' if i < 5 else 'blade', 0.36 + 0.1 * (j > hy) + 0.12 * (i >= 5), prio=2)
        for (j, k) in ((hy - 1, -1), (hy, 0), (hy + 1, 1), (hy + 1, -1), (hy - 1, 1)):
            g.put(7, j, k, 'ink' if p.lv < 3 else 'glow', 0.8, glow=p.lv >= 3, prio=4)
        g.torus((2, hy, 0), 3.6, 0.6, 'x', 'orn', 0.7)
    else:
        def head(u, v):
            if -3 <= u <= 5 and abs(v - hy) <= 3:
                return True
            return 5 <= u <= 7 and abs(v - hy) <= 4      # flared striking face
        g.slab(head, (-4, hy - 5), (8, hy + 5), 'xy', 0, max_half=3, slope=1.0, mat='metal',
               vfn=lambda u, v, w, d: ('blade', 0.62) if u >= 6 else 0.34 + 0.09 * min(d, 3) + 0.05 * (v > hy))
        g.crystal((-3, hy, 0), (-1, -0.3, 0), 7.5 if p.lv >= 2 else 6.0, 1.5, 'blade', prio=3, tip=0.6)
        if p.lv >= 1:
            g.box((1, hy - 4, -3), (2, hy + 4, 3), 'orn', 0.7, prio=3)
        if th == 'forge':
            _face_cracks(g, p, 7, hy - 3, hy + 3, 0)
        if th == 'water':
            shell(g, (2, hy + 3, 2.5), p, 1.8)
    g.crystal((0, hy + 3, 0), (0, 1, 0), 4.5, 1.1, 'metal', prio=2)
    if p.lv >= 2:
        for s in (-1, 1):
            g.gem((1, hy, s * 3.5), 1.0, 'gem', glow=p.glow)
    if th == 'abyss' and p.lv >= 3:
        g.ball((2, hy, 3.4), 1.3, 'eye', 0.8, glow=True, prio=5)
    dress_shaft(g, p, -4, hy - 5, hy, hy + 6)


def falchion(g, p):
    """Single-edged falchion: straight back (−x), bellied edge (+x) widening toward a clipped tip."""
    L = p.L
    gl = 9
    grip(g, -gl // 2, gl // 2)
    pommel(g, -gl // 2 - 2, p, 1.6)
    gy = gl // 2 + 1
    crossguard(g, gy, 5 + (p.lv >= 3), p)
    y0 = gy + 2
    length = int(27 * L)

    def prof(t):
        back = -2.0
        edge = 1.8 + 4.6 * t ** 1.3
        if t > 0.8:
            k = (t - 0.8) / 0.2
            edge -= k ** 1.5 * (edge - back + 0.5) * 0.85
            back += k * 1.6      # clip
        return back, edge

    def m(u, v):
        t = (v - y0) / length
        if t < 0 or t > 1:
            return False
        b, e = prof(t)
        return b <= u <= e
    g.slab(m, (-4, y0), (9, y0 + length), 'xy', 0, max_half=1, slope=0.5, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.74) if d == 0 and u > -1 else 0.4 + 0.08 * min(d, 3) + 0.04 * w)
    # thick spine + fuller line
    for v in range(y0, y0 + int(length * 0.78)):
        g.put(-2, v, 0, 'metal', 0.62, prio=2)
        if p.lv >= 1 and (v - y0) % 2 == 0 and v < y0 + int(length * 0.6):
            g.put(0, v, 1, 'fuller', 0.3, prio=2)
            g.put(0, v, -1, 'fuller', 0.3, prio=2)
    if p.lv >= 2:     # back notches near the guard
        for v in range(y0 + 2, y0 + 8, 3):
            g.put(-3, v, 0, 'edge', 0.8, prio=3)
    if p.theme == 'crystal' and p.lv >= 2:
        for k, t in enumerate((0.35, 0.6)):
            b, e = prof(t)
            g.crystal((e, y0 + int(length * t), 0), (1, 0.8, 0), 3.0, 0.8, 'crystal', glow=p.glow, prio=3)
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': 3.0, 'gy': gy, 'gh': 5,
                       'wfn': lambda y: max(1.0, prof(min(1.0, max(0.0, (y - y0) / length)))[1])})


def war_scythe(g, p):
    """Two-handed war scythe: long snath with a side handle, crescent blade sweeping out to +x and down."""
    L = p.L
    top = int(27 * L)
    shaft(g, -14, top, 1.25, 'wood' if p.lv < 2 else 'metal', bands=(-6, 6, top - 3))
    pommel(g, -16, p, 1.6)
    grip(g, -5, 5)
    g.tube([(0, 10, 0), (3, 11, 0), (4.5, 10.5, 0)], 0.9, 0.9, 'grip', 0.5, prio=2)   # nib
    hy = top - 1
    R = 23 if p.lv < 3 else 25

    def m(u, v):
        if u < 0 or u > R:
            return False
        t = u / R
        yu = hy + 5.5 * math.sin(math.pi * min(1.0, t * 1.1) * 0.75) - 12.0 * t ** 2.2
        w = 7.0 * (1 - t) ** 0.7 + 0.6
        return yu - w <= v <= yu
    g.slab(m, (0, hy - 18), (R, hy + 7), 'xy', 0, max_half=1, slope=0.45, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.74) if d == 0 and v < hy + 5.5 * math.sin(math.pi * min(1.0, u / R * 1.1) * 0.75)
           - 12.0 * (u / R) ** 2.2 - 1.2 else 0.38 + 0.08 * min(d, 3) + 0.04 * w)
    g.box((-2, hy - 3, -2), (2, hy + 2, 2), 'metal', 0.55, prio=2)            # collar
    g.crystal((0, hy + 2, 0), (-0.5, 1, 0), 4.5, 1.0, 'metal', prio=2)       # back spike
    if p.lv >= 1:
        g.torus((0, hy - 3, 0), 2.4, 0.6, 'y', 'orn', 0.7)
    if p.lv >= 2:
        g.gem((0, hy, 2.2), 1.1, 'gem', glow=p.glow)
        for k in range(3):   # spine studs along the back
            u = 4 + k * 4
            t = u / R
            g.put(u, round(hy + 5.5 * math.sin(math.pi * min(1.0, t * 1.1) * 0.75) - 12.0 * t ** 2.2), 1, 'orn', 0.75, prio=3)
    if p.theme == 'abyss' and p.lv >= 3:
        tendrils(g, (R * 0.7, hy - 4, 0), p, n=3, length=5, spread=3, up=-0.9)
    if p.sig == 'hightide':
        _hightide_blade(g, p, hy, R)                                        # 파도 머리 날 끝 + 거품 + 조개
    dress_shaft(g, p, -4, hy - 4, hy, top + 4)


def glaive(g, p):
    """Two-handed glaive: long haft topped by a single-edged knife blade with a back spur."""
    L = p.L
    top = int(24 * L)
    shaft(g, -16, top, 1.25, 'wood' if p.lv < 2 else 'metal', bands=(-6, 6, top - 2))
    pommel(g, -18, p, 1.6)
    grip(g, -5, 5)
    y0 = top + 1
    length = int(21 * L)

    def prof(t):
        back = -1.6 - 0.6 * math.sin(t * math.pi)
        edge = 1.8 + 4.0 * math.sin(min(1.0, t * 1.25) * math.pi * 0.7)
        if t > 0.72:
            k = (t - 0.72) / 0.28
            edge -= k ** 1.4 * (edge + 1.4)
            back -= k * 1.8
        return back, edge

    def m(u, v):
        t = (v - y0) / length
        if t < 0 or t > 1:
            return False
        b, e = prof(t)
        return b <= u <= e
    g.slab(m, (-5, y0), (6, y0 + length), 'xy', 0, max_half=1, slope=0.5, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.74) if d == 0 and u > 0 else 0.4 + 0.08 * min(d, 3) + 0.04 * w)
    g.crystal((-2, y0 + 3, 0), (-1, 0.7, 0), 5.0 if p.lv >= 2 else 4.0, 1.0, 'blade', prio=3, tip=0.6)   # spur
    g.box((-2, y0 - 3, -2), (2, y0, 2), 'metal', 0.55, prio=2)
    if p.lv >= 1:
        for k in range(3):    # tassel under the collar
            g.ball((1.5 + k * 0.4, y0 - 5 - k * 1.6, 0), 0.9, 'cloth' if p.theme not in ('forge',) else 'flame', 0.55,
                   glow=p.theme == 'forge', prio=1)
    if p.lv >= 2:
        g.gem((0, y0 + 2, 1.5), 1.0, 'gem', glow=p.glow)
        g.gem((0, y0 + 2, -1.5), 1.0, 'gem', glow=p.glow)
    if p.theme == 'forge' and p.lv >= 3:
        _face_cracks(g, p, 1, y0 + 2, y0 + length - 6, 1.2)
    dress_shaft(g, p, -4, y0 - 4, y0 + 3, y0 + length)


def sickle(g, p):
    """Sickle dagger: short grip, crescent blade curving up and out over the hand (edge inside)."""
    gl = 7
    grip(g, -gl // 2, gl // 2)
    pommel(g, -gl // 2 - 2, p, 1.4)
    gy = gl // 2 + 1
    g.box((-2, gy, -1), (2, gy + 1, 1), 'metal', 0.55, prio=2)
    C = (5.5, gy + 4.0)
    R = 7.5 if p.lv < 3 else 8.5
    a0, a1 = math.pi, math.radians(-25)
    wane = p.sig == 'waning'
    W0, W1 = (3.4, 0.4) if not wane else (2.5, 0.3)          # 그믐달: 날이 더 가늘고
    if wane:
        R, a1 = 9.5, math.radians(-42)                       # … 더 길게 (끝이 아래로 더 감긴다)

    def m(u, v):
        dx, dy = u - C[0], v - C[1]
        r = math.hypot(dx, dy)
        a = math.atan2(dy, dx)
        if a < -math.pi / 2:
            a += 2 * math.pi
        if not (a1 <= a <= a0):
            return False
        s = (a0 - a) / (a0 - a1)          # 0 at the grip → 1 at the tip
        w = W0 * (1 - s) ** 0.8 + W1
        return R - w <= r <= R + 0.6
    cells = g.slab(m, (-6, gy - 6), (17, gy + 16), 'xy', 0, max_half=1, slope=0.5, mat='blade',
                   vfn=lambda u, v, w, d: ('edge', 0.76) if d == 0 and math.hypot(u - C[0], v - C[1]) < R - 0.6 else
                   0.42 + 0.08 * min(d, 3) + 0.04 * w)
    if wane:
        _waning_sickle(g, p, cells, C, R, gl)              # 빛나는 안쪽 날 + 사슬 + 초승달 추
    if p.lv >= 1:
        g.torus((0, -gl // 2 - 3.5, 0), 1.6, 0.5, 'z', 'orn', 0.7)    # finger ring on the pommel
    if p.lv >= 2:
        g.gem((0.5, gy + 1, 1), 1.0, 'gem', glow=p.glow)
        g.crystal((C[0] - R - 0.5, gy + 3, 0), (-1, -0.4, 0), 3.0, 0.8, 'edge', prio=3)   # back thorn
    if p.theme == 'water':
        g.tube([(C[0] - R + 1, gy + 2, 0), (C[0] - R - 1.5, gy - 1, 0), (C[0] - R - 0.5, gy - 3, 0)], 0.8, 0.4, 'fin', 0.6, prio=2)
    dress_blade(g, p, {'y0': gy + 2, 'y1': gy + 12, 'hw': 2.5, 'gy': gy, 'gh': 3, 'wfn': lambda y: 3.0,
                       'C': C, 'R': R})


def katar(g, p):
    """Katar (punch dagger): H-frame grip with two cross bars, broad triangular blade on top."""
    for s in (-1, 1):   # side bars (protect the wrist)
        g.box((s * 3, -6, -1), (s * 3, 4, 1), 'metal', vfn=lambda i, j, k: 0.42 + 0.1 * (j > 0) + 0.05 * k)
        g.crystal((s * 3, -6, 0), (0, -1, 0), 2.0 if p.lv < 2 else 3.0, 0.9, 'metal', prio=2)
    for y in (-2, 1):   # the hand grips these
        for i in range(-2, 3):
            for k in range(-1, 2):
                if abs(k) + (abs(i) == 2) < 2:
                    g.put(i, y, k, 'grip', 0.45 + 0.1 * ((i + y) % 2), prio=2)
    gy = 4
    g.box((-4, gy, -1), (4, gy + 1, 1), 'metal' if p.lv < 1 else 'orn', 0.6, prio=2)
    y0 = gy + 2
    length = 17

    def m(u, v):
        t = (v - y0) / length
        if t < 0 or t > 1:
            return False
        hw = 3.2 * (1 - t) ** 0.9 + 0.3 if t > 0.12 else 3.2
        return abs(u) <= hw
    g.slab(m, (-4, y0), (4, y0 + length), 'xy', 0, max_half=2, slope=0.6, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.74) if d == 0 else 0.4 + 0.07 * min(d, 4) + 0.05 * (u > 0))
    if p.lv >= 1:     # thickened armour-piercing tip
        g.crystal((0, y0 + length - 4, 0), (0, 1, 0), 4.5, 1.0, 'edge', prio=3, tip=0.7)
    if p.lv >= 2:
        g.gem((0, y0 + 2, 1.6), 1.1, 'gem', glow=p.glow)
        g.gem((0, y0 + 2, -1.6), 1.0, 'gem', glow=p.glow)
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': 3.0, 'gy': gy, 'gh': 4,
                       'wfn': lambda y: 3.2 * (1 - min(1.0, max(0.0, (y - y0) / length))) + 0.3})


def staff_spiral(g, p):
    """Staff whose head curls into a crook spiral around a floating focus."""
    top = int(26 * p.L)
    _staff_base(g, p, top)
    R0 = 6.5
    C = (R0, top + 4)
    turns = 1.35
    pts = []
    for k in range(41):
        t = k / 40
        a = math.pi - t * turns * 2 * math.pi
        r = R0 * (1 - 0.72 * t)
        pts.append((C[0] + math.cos(a) * r, C[1] + math.sin(a) * r, 0))
    pts = [(0, top - 1, 0), (0, top + 2, 0)] + pts
    g.tube(pts, 1.5, 0.7, 'wood' if p.lv < 2 else 'orn', vfn=lambda t, d, q: 0.42 + 0.3 * (1 - d) + 0.08 * t, prio=2)
    focus = (C[0], C[1], 0)
    th = p.theme
    if th == 'forge':
        flames(g, C[1] - 1, C[1] + 2, lambda y: 0.8, p, n=2)
        g.ball(focus, 1.6, 'flame', glow=True, vfn=lambda i, j, k, d: 0.6 + 0.35 * (1 - d), prio=4)
    elif th == 'ink':
        g.ball(focus, 1.7, 'ink', vfn=lambda i, j, k, d: 0.3 + 0.4 * (1 - d), prio=4)
        drips(g, [(C[0] - 1, C[1] - 2, 0), (C[0] + 1, C[1] - 3, 0)], p)
    else:
        g.ball(focus, 1.6, 'glow' if p.lv >= 1 else 'gem', glow=True, vfn=lambda i, j, k, d: 0.5 + 0.45 * (1 - d), prio=4)
    if th == 'vine':
        vines(g, top - 6, top + 2, 1.8, p, n=1, leaves=True, buds=p.lv >= 1)
        for q in pts[8:30:7]:
            g.ball((q[0], q[1], 1.2), 0.9, 'leaf', 0.6, sq=(1.3, 0.8, 0.5), prio=3)
    if th == 'fungi':
        for q in (pts[12], pts[24]):
            fungi(g, (q[0], q[1] + 1, 0), p, 1.5)
    if th == 'water':
        for q in pts[5:35:10]:
            g.ball((q[0], q[1] - 1.5, 0), 0.8, 'glow', 0.7, glow=True, prio=3)
    if p.lv >= 2:
        g.torus((0, top - 2, 0), 2.0, 0.55, 'y', 'orn', 0.7)
    dress_shaft(g, p, -6, top - 4, C[1], C[1] + R0)


def staff_fork(g, p):
    """Forked staff (tuning fork / trident): two prongs rising from a yoke, a charge held between them."""
    top = int(26 * p.L)
    _staff_base(g, p, top, 'wood' if p.lv < 2 else 'metal')
    th = p.theme
    yk = top + 1
    W = 4.5
    g.tube([(-W, yk + 2, 0), (-W * 0.6, yk, 0), (0, yk - 1, 0), (W * 0.6, yk, 0), (W, yk + 2, 0)], 1.2, 1.2,
           'metal' if th != 'crystal' else 'orn', 0.55, prio=2)
    H = 13 if p.lv < 3 else 15
    for s in (-1, 1):
        pts = catmull([(s * W, yk + 2, 0), (s * (W + 0.8), yk + H * 0.45, 0), (s * (W - 0.2), yk + H * 0.8, 0),
                       (s * (W - 1.2), yk + H, 0)], 6)
        g.tube(pts, 1.1, 0.7, 'metal' if th != 'crystal' else 'crystal', vfn=lambda t, d, q: 0.45 + 0.3 * (1 - d) + 0.1 * t,
               prio=2)
        if th == 'water' or p.lv >= 2:
            g.crystal((s * (W - 1.2), yk + H, 0), (-s * 0.25, 1, 0), 3.0, 0.9, 'edge' if th == 'water' else 'gem',
                      glow=p.glow and th != 'water', prio=3)
    if th == 'water':     # trident: middle tine
        g.tube([(0, yk - 1, 0), (0, yk + H - 1, 0)], 1.0, 0.8, 'metal', 0.55, prio=2)
        g.crystal((0, yk + H - 1, 0), (0, 1, 0), 4.0, 1.1, 'edge', prio=3)
    cy = yk + H * 0.55
    if th == 'abyss':
        g.ball((0, cy, 0), 2.0, 'eye', glow=True, vfn=lambda i, j, k, d: 0.45 + 0.5 * (1 - d), prio=4)
    elif th != 'water':
        g.ball((0, cy, 0), 1.7, 'glow', glow=True, vfn=lambda i, j, k, d: 0.5 + 0.45 * (1 - d), prio=4)
        if p.lv >= 1:
            for s in (-1, 1):
                zigzag(g, (s * (W - 1), cy + s * 1.5, 0), (0, cy, 0), p, n=3, amp=0.7)
    if th == 'crystal' and p.lv >= 2:
        for s in (-1, 1):
            g.ball((s * 6.5, cy + 2, 0), 0.8, 'glow', 0.8, glow=True, prio=3)    # resonance motes
    dress_shaft(g, p, -6, top - 4, cy, yk + H)


def bell_scepter(g, p):
    """Scepter carrying a bell hung inside an arched yoke, clapper below."""
    top = int(14 * p.L)
    shaft(g, -8, top, 1.25, 'orn' if p.lv >= 2 else 'wood', bands=(-2, top - 1))
    grip(g, -7, 2)
    pommel(g, -10, p, 1.4)
    yb = top + 2
    W = 5.0
    g.tube([(-W, yb, 0), (W, yb, 0)], 0.9, 0.9, 'metal', 0.55, prio=2)
    g.torus((0, yb + 1, 0), W, 0.9, 'z', 'orn' if p.lv >= 1 else 'metal', 0.6, arc=(0.0, 0.5))
    apex = yb + 1 + int(W)
    bt, bb = apex - 1, yb + 1          # bell spans bt (crown) .. bb (mouth)
    h = bt - bb
    for j in range(bb, bt + 1):
        t = (bt - j) / max(1, h)
        r = 1.2 + 2.6 * t ** 1.7
        for i in range(-5, 6):
            for k in range(-5, 6):
                d = math.hypot(i, k)
                if d <= r and (d >= r - 1.3 or j >= bt - 1):
                    g.put(i, j, k, 'orn' if th_bell(p) else 'metal', 0.4 + 0.3 * (1 - t) + 0.1 * (i > 0), prio=3)
    if p.sig == 'daybreak':
        _daybreak_bell(g, p, bb, bt, h, apex)        # 장밋빛 청동 종 + 빛나는 띠 둘 + 꼭대기 고리·보석
    else:
        g.torus((0, bb, 0), 3.6, 0.6, 'y', 'orn', 0.75, prio=3)       # lip
        g.ball((0, bb - 1.2, 0), 1.1, 'glow' if p.lv >= 1 else 'metal', 0.7, glow=p.lv >= 1, prio=4)   # clapper
        g.ball((0, apex + 0.5, 0), 1.0, 'gem', 0.7, glow=p.glow, prio=4)
    if p.theme == 'crystal':
        for s in (-1, 1):
            g.crystal((s * W, yb + 1, 0), (s * 0.5, 1, 0), 4.0, 0.9, 'crystal', glow=p.glow, prio=3)
    if p.theme == 'water':
        for s in (-1, 1):
            g.tube([(s * W, yb, 0), (s * (W + 1.5), yb - 2, 0)], 0.6, 0.6, 'vine', 0.5, prio=2)   # weed strands
    dress_shaft(g, p, -6, top - 2, yb + 3, apex + 2)


def th_bell(p):
    return p.lv >= 2 or p.theme in ('holy', 'crystal')


def chalice_scepter(g, p):
    """Scepter topped by a chalice: knop, stem and a flared cup holding a glowing (themed) liquid."""
    top = int(13 * p.L)
    shaft(g, -8, top, 1.25, 'orn' if p.lv >= 2 else 'wood', bands=(-2,))
    grip(g, -7, 2)
    pommel(g, -10, p, 1.4)
    g.ball((0, top + 1, 0), 2.0, 'orn' if p.lv >= 1 else 'metal', 0.55, prio=2)    # knop
    c0, c1 = top + 3, top + 10
    for j in range(c0, c1 + 1):
        t = (j - c0) / (c1 - c0)
        r = 1.0 + 3.6 * t ** 0.7
        for i in range(-6, 7):
            for k in range(-6, 7):
                d = math.hypot(i, k)
                if d <= r and (d >= r - 1.2 or j <= c0 + 1):
                    g.put(i, j, k, 'orn' if p.lv >= 1 else 'metal', 0.38 + 0.3 * t + 0.08 * (i > 0), prio=3)
    th = p.theme
    liquid = {'forge': 'flame', 'ink': 'ink', 'abyss': 'eye'}.get(th, 'glow')
    for i in range(-4, 5):
        for k in range(-4, 5):
            if math.hypot(i, k) <= 3.2:
                g.put(i, c1 - 1, k, liquid, 0.7, glow=liquid in ('flame', 'glow', 'eye'), prio=4)
    g.torus((0, c1, 0), 4.4, 0.6, 'y', 'orn', 0.75, prio=3)       # rim
    if th == 'forge':
        flames(g, c1, c1 + 3, lambda y: 1.2, p, n=2)
    elif th == 'fungi':
        for k in range(5):
            a = 2 * math.pi * k / 5
            g.ball((math.cos(a) * 4.6, c1 + 1, math.sin(a) * 4.6), 1.5, 'fungus', sq=(1, 0.5, 1), prio=3)
    elif th == 'vine':
        for k in range(4):
            a = 2 * math.pi * k / 4 + 0.4
            g.ball((math.cos(a) * 4.6, c1 + 0.5, math.sin(a) * 4.6), 1.1, 'leaf', 0.6, sq=(1.3, 0.6, 1.3), prio=3)
    elif th == 'ink':
        drips(g, [(4.2, c1 - 1, 0), (-4.2, c1 - 2, 1)], p)
    if p.lv >= 2:
        g.ball((0, c1 + 2.5, 0), 1.1, 'glow', 0.8, glow=True, prio=4)
    dress_shaft(g, p, -6, top - 2, c1, c1 + 4)


# third wave (0.3.5) ----------------------------------------------------------
# 새 실루엣 13종 + 활 2종(bone_bow·twin_bow, bow() 안). 무기 종류는 없어졌지만 모양마다 손에 드는 방식(HOLD·
# TWO_HANDED·HEAD_SHAPES)은 그대로 모양이 정한다. 새 무기는 영웅까지라 테마 장식은 dress_* 의 lv 3 단계만 얹힌다.

def _rune(g, p, a0, y0, depth, gi, mat='orn', glow=False, flip=False, plane='xy'):
    """3×5 rune glyph (materials.RUNES) on a face, lower-left (a0, y0): plane 'xy' at z = depth, 'zy' at x = depth
    (a0 then runs along z).  flip = mirrored (seen from the other side, or cut in reverse like a seal)."""
    for yy in range(5):
        for xx in range(3):
            if rune_bit(gi, 2 - xx if flip else xx, 4 - yy):
                q = (a0 + xx, y0 + yy, depth) if plane == 'xy' else (depth, y0 + yy, a0 + xx)
                g.put(q[0], q[1], q[2], mat, 0.82, glow=glow, prio=4)


def executioner_axe(g, p):
    """Two-handed executioner's axe: one broad square bit (+x) with a dropped beard, square hammer back (−x)."""
    L, th = p.L, p.theme
    top = int(34 * L)
    shaft(g, -18, top, 1.35, 'wood', bands=(-8, 4, top - 12))
    grip(g, -6, 6)
    pommel(g, -20, p, 1.7)
    hy = top - 6

    R = 15

    def lo_of(x):
        return -5 - 9.0 * max(0.0, (x - 3) / (R - 3)) ** 1.6     # the beard sweeps down toward the far corner

    def m(u, v):
        if u < 1:
            return False
        dy = v - hy
        if u > R - 0.02 * (dy + 3) ** 2:                     # slightly convex cutting edge
            return False
        if u <= 3:                                           # neck where the bit leaves the socket
            return -5 <= dy <= 5
        hi = 5 + 3.0 * (u - 3) / (R - 3) - max(0, u - (R - 4)) * 1.0   # rising top line, clipped corner
        return lo_of(u) <= dy <= hi
    g.slab(m, (0, hy - 16), (R + 1, hy + 10), 'xy', 0, max_half=1, slope=0.34, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.74 + 0.08 * (w == 0)) if u >= R - 3 and d <= 1 else
           0.38 + 0.07 * min(d, 4) + 0.03 * w)
    g.box((-2, hy - 6, -2), (1, hy + 6, 2), 'metal', vfn=lambda i, j, k: 0.5 + 0.1 * (j > hy) - 0.06 * (abs(k) == 2),
          prio=2)                                            # socket
    g.box((-5, hy - 2, -2), (-3, hy + 2, 2), 'metal', vfn=lambda i, j, k: 0.62 if i == -5 else 0.46, prio=2)  # hammer back
    g.crystal((0, top, 0), (0, 1, 0), 3.0, 1.1, 'metal', prio=2)
    if p.lv >= 2:
        _rune(g, p, 7, hy - 3, 1, 6, 'glow' if p.lv >= 3 else 'orn', glow=p.lv >= 3)
        _rune(g, p, 7, hy - 3, -1, 6, 'glow' if p.lv >= 3 else 'orn', glow=p.lv >= 3, flip=True)
        for sz in (-1, 1):
            g.gem((0, 4, sz * 1.6), 0.9, 'gem', glow=p.glow)
    if p.lv >= 3:                                            # chain rings hanging from the beard
        yb = hy + lo_of(6)
        g.torus((6, yb - 1.4, 0), 1.2, 0.5, 'z', 'orn', 0.7, prio=3)
        g.torus((6, yb - 3.5, 0), 1.0, 0.5, 'x', 'orn', 0.65, prio=3)
    if th == 'forge':
        _face_cracks(g, p, 9, hy - 8, hy + 3, 1.2)
    elif th == 'frost':
        ice_spikes(g, [(x, hy + lo_of(x) - 0.5, 0, 0.2, -1) for x in (6, 10, 13)], p, 2.6)
    elif th == 'abyss':
        g.ball((8, hy, 1.6), 1.3, 'eye', 0.8, glow=True, prio=5)
    elif th == 'crystal' and p.lv >= 2:
        crystal_cluster(g, (-5, hy + 2, 0), p, 3, 3.0, 0.9, up=(-0.8, 1, 0))
    dress_shaft(g, p, -4, hy - 8, hy, top)


def flamberge(g, p):
    """Two-handed flamberge: waved blade above a plain ricasso with parrying lugs (a second, small guard)."""
    hw, gl, gh = 4.0, 15, 11 + (p.lv >= 3)
    total = int(40 * p.L)
    grip(g, -gl // 2, gl // 2)
    pommel(g, -gl // 2 - 2, p, 1.9)
    gy = gl // 2 + 1
    crossguard(g, gy, gh, p)
    y0 = gy + 2
    ric = 6
    g.box((-2, y0, -1), (2, y0 + ric - 1, 1), 'metal',
          vfn=lambda i, j, k: None if abs(i) == 2 and abs(k) == 1 else 0.48 + 0.12 * (k == 0) + 0.06 * (i > 0), prio=2)
    for s in (-1, 1):                                        # parrying lugs
        g.crystal((s * 2.2, y0 + ric - 1, 0), (s, 0.45, 0), 3.4, 0.9, 'metal', prio=3, tip=0.5)
    b0 = y0 + ric
    length = total - ric
    tip, taper, wave = 0.14, 0.06, 1.2
    blade(g, b0, length, hw, p, tip=tip, wave=wave, wave_n=6.0, thick=2, taper=taper, fuller=False)
    wfn = lambda y: wave + hw * (1 - taper * min(1 - tip, (y - b0) / length)) * (
        1 if (y - b0) / length < 1 - tip else max(0.0, (1 - (y - b0) / length) / tip))
    dress_blade(g, p, {'y0': b0, 'y1': b0 + length, 'hw': hw, 'gy': gy, 'gh': gh, 'wfn': wfn})


def great_maul(g, p):
    """Two-handed great maul: long haft, a big bevelled block head with two framed striking faces (±x)."""
    th = p.theme
    top = int(26 * p.L)
    shaft(g, -18, top, 1.4, 'metal' if p.lv >= 2 else 'wood', bands=(-8, 6, top - 6))
    grip(g, -6, 6)
    pommel(g, -20, p, 1.6)
    HX, HY, HZ = 7, 5, 4
    hy = top + HY
    cells = set()
    for i in range(-HX, HX + 1):
        for j in range(hy - HY, hy + HY + 1):
            for k in range(-HZ, HZ + 1):
                if (abs(i) == HX) + (abs(j - hy) == HY) + (abs(k) == HZ) >= 2:
                    continue                                 # chamfered edges
                cells.add((i, j, k))
    for (i, j, k) in cells:
        if abs(i) == HX:
            rim = abs(j - hy) == HY - 1 or abs(k) == HZ - 1
            g.put(i, j, k, 'blade', 0.62 if rim else 0.44, prio=2)
        else:
            g.put(i, j, k, 'metal', 0.34 + 0.1 * (j > hy) + 0.05 * (k > 0) - 0.04 * (abs(i) == HX - 1), prio=2)
    for (i, j, k) in cells:                                  # two bands ringing the head near the faces
        if abs(i) == HX - 3 and (abs(j - hy) == HY or abs(k) == HZ):
            g.put(i, j, k, 'orn', 0.72, prio=3)
    g.box((-2, hy - HY - 2, -2), (2, hy - HY - 1, 2), 'metal', 0.55, prio=2)    # collar
    if p.sig == 'mountainheart':
        _mountain_head(g, p, hy, HX, HY, HZ)                                    # 봉우리 셋 + 호박빛 갈라짐
    else:
        g.crystal((0, hy + HY, 0), (0, 1, 0), 3.0, 1.0, 'metal', prio=2)        # knob
    if p.lv >= 2:
        for sz in (-1, 1):
            g.gem((0, hy, sz * (HZ + 0.4)), 1.1, 'gem', glow=p.glow)
    if th == 'crystal':
        if p.sig != 'mountainheart':                         # 태산은 _mountain_head 가 +x 면 한쪽에만 작게 얹는다
            crystal_cluster(g, (HX + 0.5, hy, 0), p, 4, 3.6, 0.9, up=(1, 0.3, 0), glow=p.lv >= 3)
    elif th == 'clock':
        gear(g, (0, hy, HZ + 1), 3.8, p, 8, 'xy', 'orn')
    elif th == 'ink':
        for sx in (-1, 1):                                   # a seal cut in reverse into each striking face
            _rune(g, p, -1, hy - 2, sx * HX, 5, 'glow' if p.lv >= 3 else 'ink', glow=p.lv >= 3, flip=sx > 0,
                  plane='zy')
    elif th == 'abyss':
        g.ball((0, hy, HZ + 0.6), 1.5, 'eye', 0.8, glow=True, prio=5)
    elif th == 'forge':
        _face_cracks(g, p, 3, hy - 4, hy + 2, HZ)
    elif th == 'frost':
        ice_spikes(g, [(s * HX, hy + HY - 1, 0, s * 0.6, 1.0) for s in (-1, 1)], p, 3.0)
    dress_shaft(g, p, -4, hy - HY - 3, hy, hy + HY)


def sabre(g, p):
    """One-handed sabre: single-edged blade curving back (edge +x convex, spine −x), knuckle bow over the grip."""
    gy = 6
    grip(g, -5, 5)
    pommel(g, -7, p, 1.3)
    y0 = gy + 1
    length = int(28 * p.L)
    cv = 4.6

    def prof(t):
        c = -cv * t * t
        w = 2.6 * (1 - 0.22 * t)
        back, edge = c - w * 0.75, c + w * 1.0
        if t > 0.74:                                         # the edge sweeps up into a point on the spine line
            k = (t - 0.74) / 0.26
            edge -= k ** 1.2 * (edge - back) * 0.95
        return back, edge

    def m(u, v):
        t = (v - y0) / length
        if t < 0 or t > 1:
            return False
        b, e = prof(t)
        return b - 0.45 <= u <= e + 0.45
    g.slab(m, (-8, y0), (4, y0 + length), 'xy', 0, max_half=1, slope=0.5, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.74) if d == 0 and u > -cv * ((v - y0) / length) ** 2 else
           0.4 + 0.08 * min(d, 3) + 0.04 * w)
    for v in range(y0, y0 + int(length * 0.8)):              # thick spine
        t = (v - y0) / length
        b, _ = prof(t)
        g.put(round(b), v, 0, 'metal', 0.6, prio=2)
        if p.lv >= 1 and 0.05 < t < 0.6:
            g.put(round(b) + 1, v, 1, 'fuller', 0.3, prio=2)
            g.put(round(b) + 1, v, -1, 'fuller', 0.3, prio=2)
        if p.lv >= 3 and (v - y0) % 3 == 1 and t < 0.7:
            g.put(round(b) - 1, v, 0, 'orn', 0.75, prio=3)   # spine pattern
    g.box((-3, gy, -1), (3, gy, 1), 'metal', 0.55, prio=2)   # short cross bar
    g.ball((-3.5, gy + 0.5, 0), 1.0, 'metal', 0.6, prio=2)   # back quillon
    bow_pts = bezier((2.8, gy, 0), (4.8, gy - 4, 0), (4.4, -4, 0), (1.5, -6, 0), 16)
    g.tube(bow_pts, 0.7, 0.7, 'orn' if p.lv >= 1 else 'metal', vfn=lambda t, d, q: 0.45 + 0.3 * (1 - d), prio=2)
    if p.lv >= 2:
        g.gem((4.6, 0, 0), 0.9, 'gem', glow=p.glow)
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': 2.4, 'gy': gy, 'gh': 3,
                       'wfn': lambda y: max(1.0, prof(min(1.0, max(0.0, (y - y0) / length)))[1])})


def morning_star(g, p):
    """One-handed morning star: a spiked iron ball on a short haft (spikes on every axis and diagonal)."""
    th = p.theme
    top = int(15 * p.L)
    shaft(g, -6, top, 1.25, 'wood' if p.lv < 2 else 'metal', bands=(top - 2,))
    grip(g, -6, 4)
    pommel(g, -8, p, 1.5)
    hy = top + 4
    hr = 3.9
    hy += 1
    g.ball((0, hy, 0), hr, 'metal', vfn=lambda i, j, k, d: 0.32 + 0.4 * (1 - d) + 0.1 * (j > hy))
    g.torus((0, hy - hr, 0), 1.6, 0.6, 'y', 'metal', 0.55)                      # collar
    mat = {'frost': 'ice', 'crystal': 'crystal'}.get(th, 'edge')
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1)] + \
           [(sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    if th == 'clock':
        gear(g, (0, hy, 0), hr + 1.2, p, 10, 'xy', 'orn')
        gear(g, (0, hy, 0), hr + 0.8, p, 9, 'xz', 'metal')
        dirs = [(0, 1, 0)]
    for d in dirs:
        n = math.sqrt(sum(c * c for c in d))
        u = tuple(c / n for c in d)
        g.crystal(tuple(hy * (a == 1) + u[a] * (hr - 0.4) for a in range(3)), u, 3.3, 0.9, mat,
                  glow=mat == 'crystal' and p.lv >= 3, prio=3, tip=0.55)
    if p.lv >= 2:
        g.torus((0, hy, 0), hr + 0.1, 0.55, 'y', 'orn', 0.7, prio=3)
    if th == 'water':
        for s in (-1, 1):
            shell(g, (s * hr, hy - hr - 0.2, 0.5), p, 1.8)
    if p.lv >= 3:
        dress_shaft(g, p, -4, hy - 6, hy, hy + 5)


def rapier(g, p):
    """One-handed rapier: a very thin long blade, swept hilt — cup, long cross bar with ball ends, three rings."""
    y0 = 8
    length = int(34 * p.L)
    grip(g, -5, 5)
    pommel(g, -7, p, 1.5)
    blade(g, y0, length, 1.0, p, tip=0.12, taper=0.25, fuller=False, thick=1, rune=False)
    g.tube([(-5, 6.5, 0), (5, 6.5, 0)], 0.7, 0.7, 'metal', 0.55, prio=2)       # cross bar
    for s in (-1, 1):
        g.ball((s * 5.6, 6.5, 0), 1.0, 'orn' if p.lv >= 1 else 'metal', 0.65, prio=3)
    g.ball((0, 7.2, 0), 2.1, 'metal', sq=(1, 0.4, 1), vfn=lambda i, j, k, d: 0.45 + 0.3 * (1 - d) + 0.1 * (j > 7), prio=3)
    rings = (('z', (-1.8, 3.6, 0), (0.25, 0.75)), ('x', (0, 3.6, 1.8), (-0.25, 0.25)), ('x', (0, 3.6, -1.8), (0.25, 0.75)))
    for ax, c, arc in rings:
        g.torus(c, 2.6, 0.5, ax, 'metal', 0.55, arc=arc, prio=2)
    if p.lv >= 2:
        for k in range(6):                                   # engraved cup rim
            a = 2 * math.pi * k / 6 + 0.3
            g.put(round(math.cos(a) * 2), 8, round(math.sin(a) * 2), 'orn', 0.8, prio=4)
    if p.lv >= 3:
        for j in range(y0 + 1, y0 + 4):
            for sz in (-1, 1):
                g.put(0, j, sz, 'glow', 0.8, glow=True, prio=4)
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': 1.0, 'gy': 6, 'gh': 5,
                       'wfn': lambda y: max(0.6, 1.0 - 0.25 * (y - y0) / length)})


def stiletto(g, p):
    """Stiletto: a four-edged needle blade (diamond section) over a small ring guard."""
    grip(g, -4, 4, r=1.1)
    g.ball((0, -5.6, 0), 1.3, 'metal', vfn=lambda i, j, k, d: 0.4 + 0.35 * (1 - d))
    g.tube([(-4, 5, 0), (4, 5, 0)], 0.6, 0.6, 'metal', 0.55, prio=2)          # small straight quillons …
    for s in (-1, 1):
        g.ball((s * 4.4, 5, 0), 0.9, 'orn' if p.lv >= 1 else 'metal', 0.65, prio=3)
    g.torus((0, 5, 0), 1.3, 0.5, 'y', 'metal', 0.6, prio=2)                   # … round collar
    y0 = 6
    length = int(24 * p.L)

    def m(u, v):                                             # needle: a long slender spike …
        t = (v - y0) / length
        return 0 <= t <= 1 and abs(u) <= 2.6 * (1 - t) ** 0.8 + 0.1
    g.slab(m, (-3, y0), (3, y0 + length), 'xy', 0, max_half=1, slope=1.0, mat='blade',   # … with a diamond section
           vfn=lambda u, v, w, d: ('edge', 0.74) if d == 0 and (u != 0 or v > y0 + length * 0.7) else
           0.44 + 0.1 * min(d, 2) - 0.05 * abs(w) + 0.04 * (u > 0))
    if p.lv >= 3:                                            # glowing groove down the middle of both faces
        for j in range(y0 + 2, y0 + int(length * 0.6)):
            for k in (-1, 1):
                if g.get((0, j, k)):
                    g.put(0, j, k, 'glow', 0.8, glow=True, prio=3)
    if p.lv >= 2:
        g.gem((0, 5, 1.4), 0.8, 'gem', glow=p.glow)
        g.gem((0, 5, -1.4), 0.8, 'gem', glow=p.glow)
    dress_blade(g, p, {'y0': y0, 'y1': y0 + length, 'hw': 1.4, 'gy': 4, 'gh': 2,
                       'wfn': lambda y: max(0.5, 1.6 * (1 - (y - y0) / length))})


def tanto(g, p):
    """Tanto: straight single-edged short blade with an angled chisel point, round tsuba, diamond-wrapped grip."""
    for j in range(-5, 4):                                   # wrapped grip (diamond pattern)
        for i in range(-1, 2):
            for k in range(-1, 2):
                if abs(i) + abs(k) <= 1 or (abs(i) == 1 and abs(k) == 1 and j % 2 == 0):
                    g.put(i, j, k, 'grip', 0.62 if (j + abs(i - k)) % 3 == 0 else 0.36, prio=1)
    g.ball((0, -6.2, 0), 1.2, 'metal', 0.55)
    for i in range(-4, 5):                                   # tsuba (disc in the xz plane), lv≥2 openwork
        for k in range(-4, 5):
            if math.hypot(i, k) <= 3.6 and not (p.lv >= 2 and abs(i) == 2 and abs(k) == 2):
                g.put(i, 4, k, 'metal' if p.lv < 1 else 'orn', 0.5 + 0.12 * (math.hypot(i, k) > 2.9), prio=2)
    g.box((-2, 5, -1), (2, 5, 1), 'metal', 0.62, prio=2)    # habaki
    y0 = 6
    length = int(21 * p.L)
    top = y0 + length
    cut = 6

    def m(u, v):
        if v < y0 or v > top:
            return False
        edge = 2.4
        if v > top - cut:
            edge = 2.4 - (v - (top - cut)) * 4.0 / cut       # chisel point: edge climbs to the spine
        return -1.5 <= u <= edge + 0.2
    g.slab(m, (-2, y0), (3, top), 'xy', 0, max_half=1, slope=0.6, mat='blade',
           vfn=lambda u, v, w, d: ('edge', 0.72 + (0.1 if p.lv >= 3 and (v // 2) % 2 else 0)) if d == 0 and u > -1
           else 0.42 + 0.08 * min(d, 2) + 0.04 * w)
    for v in range(y0, top):
        g.put(-2, v, 0, 'metal', 0.58, prio=2)               # spine
    if p.lv >= 2:
        g.gem((0, -3, 1.4), 0.8, 'gem', glow=p.glow)
    dress_blade(g, p, {'y0': y0, 'y1': top, 'hw': 2.0, 'gy': 4, 'gh': 3, 'wfn': lambda y: 2.0})


def war_spear(g, p):
    """Two-handed war spear: the longest haft, leaf blade on a socket, butt spike; cross wings at rare+."""
    top = int(36 * p.L)
    shaft(g, -14, top, 1.15, 'wood' if p.lv < 3 else 'metal', bands=(-4, 6, top - 2))
    grip(g, -6, 6)
    g.crystal((0, -14, 0), (0, -1, 0), 3.0, 1.0, 'metal', prio=2)              # butt spike
    g.torus((0, top - 1, 0), 1.5, 0.6, 'y', 'metal', 0.6, prio=2)              # socket ring
    g.box((-1, top - 3, -1), (1, top, 1), 'metal', 0.55, prio=2)
    blade(g, top + 1, int(18 * max(1.0, p.L)), 3.4, p, tip=0.45, taper=0.0, fuller=False, rune=False)
    for s in (-1, 1):                                        # winged spear: lugs under the head (longer at rare+)
        g.crystal((s * 1.4, top + 1, 0), (s, 0.35, 0), 5.0 + 1.5 * (p.lv >= 2), 0.9, 'blade', prio=3, tip=0.6)
    if p.lv >= 1:
        for s in (-1, 1):                                    # tassel
            g.tube([(s * 1.2, top - 2, 0), (s * 2.2, top - 5, 0.5), (s * 2.6, top - 8, 0)], 0.8, 0.5, 'cloth', 0.55,
                   prio=1)
    if p.lv >= 2:
        g.gem((0, top - 2, 1.4), 0.9, 'gem', glow=p.glow)
    dress_shaft(g, p, -4, top - 6, top + 2, top + 18)


def antler_staff(g, p):
    """Staff crowned by two antler beams with tines, a floating orb held between them."""
    th = p.theme
    top = int(27 * p.L)
    _staff_base(g, p, top, 'wood')
    tines = []
    for s in (-1, 1):
        beam = catmull([(0, top, 0), (s * 4, top + 6, 0), (s * 7, top + 12, s * 1.0), (s * 6, top + 19, 0)], 6)
        g.tube(beam, 1.4, 0.7, 'bone', vfn=lambda t, d, q: 0.38 + 0.35 * (1 - d) + 0.12 * t, prio=2)
        n = len(beam) - 1
        for t, ln, up in ((0.22, 4.0, (1.0, 0.7)), (0.5, 5.0, (0.7, 1.0)), (0.75, 4.5, (-0.2, 1.0)),
                          (0.9, 3.0, (-0.8, 0.8))):
            q = beam[int(t * n)]
            e = (q[0] + s * up[0] * ln * 0.75, q[1] + up[1] * ln, q[2])
            mid = ((q[0] + e[0]) / 2 + s * 0.4, (q[1] + e[1]) / 2 - 0.3, q[2])
            g.tube(catmull([q, mid, e], 4), 0.9, 0.5, 'bone', vfn=lambda tt, d, qq: 0.45 + 0.35 * tt, prio=2)
            tines.append(e)
        tines.append(beam[-1])
    g.ball((0, top + 10, 0), 1.8, 'glow' if p.lv >= 1 else 'gem', glow=True,
           vfn=lambda i, j, k, d: 0.5 + 0.45 * (1 - d), prio=3)
    if p.lv >= 2:
        g.torus((0, top + 1, 0), 1.8, 0.55, 'y', 'orn', 0.7, prio=3)
    if p.lv >= 3:
        for e in tines:
            if th == 'frost':
                g.crystal(e, (0, 1, 0), 2.2, 0.7, 'ice', prio=4)
            elif th in ('crystal', 'clock'):
                g.crystal(e, (0, 1, 0), 2.0, 0.7, 'crystal' if th == 'crystal' else 'orn', prio=4)
            elif th in ('vine', 'fungi'):
                g.ball(e, 1.0, 'leaf', 0.6, sq=(1.2, 0.7, 1.2), prio=4)
            else:
                g.put(round(e[0]), round(e[1]) + 1, round(e[2]), 'glow', 0.85, glow=True, prio=4)
    dress_shaft(g, p, -6, top - 4, top + 10, top + 19)


def lamp_crook(g, p):
    """Shepherd's crook staff: the head curls forward (+x) and carries a hanging lantern on two chain links."""
    top = int(32 * p.L)
    _staff_base(g, p, top)
    hook = bezier((0, top, 0), (0, top + 6, 0), (5, top + 9, 0), (6.5, top + 4.5, 0), 16)
    g.tube(hook, 1.15, 0.9, 'metal' if p.lv < 2 else 'orn', vfn=lambda t, d, q: 0.45 + 0.3 * (1 - d) + 0.06 * t, prio=2)
    lx = 6.5
    for k in range(2):
        g.torus((lx, top + 3 - k * 1.8, 0), 0.8, 0.45, 'z' if k % 2 else 'x', 'metal', 0.6, prio=2)
    ly0, ly1 = top - 4, top + 0
    wisp = p.sig == 'wisp'                                   # 도깨비불 등롱: 우리를 키우고 불을 크게
    cx0, cx1, cz = (4, 9, 3) if wisp else (5, 8, 2)
    if wisp:
        ly0 = top - 6

    def frame(i, j, k):                                      # lantern cage: only the edges of the box
        ex = (i in (cx0, cx1)) + (j in (ly0, ly1)) + (k in (-cz, cz))
        return 0.58 if ex >= 2 else None
    g.box((cx0, ly0, -cz), (cx1, ly1, cz), 'metal' if p.lv < 2 else 'orn', vfn=frame, prio=3)
    if wisp:
        _wisp_flame(g, p, lx, ly0, ly1, top)
    else:
        g.ball((lx, (ly0 + ly1) / 2, 0), 1.4, 'glow' if p.lv >= 1 else 'gem', glow=p.lv >= 1,
               vfn=lambda i, j, k, d: 0.55 + 0.4 * (1 - d), prio=4)
    g.crystal((lx, ly1 + 0.5, 0), (0, 1, 0), 2.0, 2.0 if wisp else 1.4, 'metal' if p.lv < 2 else 'orn', prio=3,
              tip=0.8)   # roof
    g.crystal((lx, ly0 - 0.5, 0), (0, -1, 0), 1.6, 0.8, 'metal', prio=3)
    if p.theme == 'water':
        shell(g, (1.5, top + 6, 1.0), p, 1.6)
    if p.theme == 'crystal' and p.lv >= 2:
        g.crystal((lx, ly0 - 1, 0), (0, -1, 0), 3.0, 0.9, 'crystal', glow=p.glow, prio=4)
    dress_shaft(g, p, -6, top - 4, top + 4, top + 9)


def thurible_rod(g, p):
    """Short censer rod: a cross arm at the top, a perforated censer hanging on a short chain in front (+x)."""
    top = int(18 * p.L)
    shaft(g, -6, top, 1.1, 'metal' if p.lv >= 1 else 'wood', bands=(-1, top - 1))
    grip(g, -6, 3)
    pommel(g, -8, p, 1.3)
    g.box((-1, top, -1), (6, top + 1, 1), 'orn' if p.lv >= 1 else 'metal', 0.6, prio=2)    # cross arm
    g.crystal((0, top + 1, 0), (0, 1, 0), 3.0, 1.0, 'metal', prio=2)                      # finial
    cx = 6
    for k in range(3):
        g.torus((cx, top - 0.8 - k * 1.6, 0), 0.7, 0.45, 'x' if k % 2 else 'z', 'orn', 0.65, prio=2)
    cy = top - 8
    holes = {(1, 0), (-1, 0), (0, 1), (0, -1)}

    def shell_v(i, j, k, d):
        if d < 0.66:
            return None
        if (j - cy) in (-1, 0, 1) and (round((i - cx) / 2.0), round(k / 2.0)) in holes and abs(j - cy) < 1:
            return None                                       # vents
        return 0.35 + 0.35 * (1 - d) + 0.12 * (j > cy)
    g.ball((cx, cy, 0), 3.3, 'metal', vfn=shell_v, prio=3)
    g.ball((cx, cy, 0), 2.0, 'glow' if p.lv >= 1 else 'flame', glow=True, vfn=lambda i, j, k, d: 0.55 + 0.4 * (1 - d), prio=2)
    g.box((cx - 1, cy + 3, -1), (cx + 1, cy + 4, 1), 'orn', 0.65, prio=3)                   # lid knob
    g.torus((cx, cy + 1.2, 0), 2.9, 0.5, 'y', 'orn', 0.7, prio=3)                           # lid seam
    if p.lv >= 2:
        g.gem((cx, cy - 3.2, 0), 0.9, 'gem', glow=p.glow)
    if p.theme == 'clock':
        gear(g, (0, top - 3, 1.8), 2.4, p, 6, 'xy', 'orn')
    if p.theme == 'fungi':
        fungi(g, (cx, cy + 3.8, 0), p, 1.4)
    if p.theme == 'frost':
        ice_spikes(g, [(cx, cy - 3.0, 0, 0, -1)], p, 2.4)
    dress_shaft(g, p, -6, top - 2, cy, top + 4)


def chime_rod(g, p):
    """Wind-chime rod: a ring held above the rod on curved spokes, five tubes of different length hanging from it."""
    top = int(20 * p.L)
    shaft(g, -6, top, 1.1, 'wood' if p.lv < 2 else 'metal', bands=(-1, top - 1))
    grip(g, -6, 3)
    pommel(g, -8, p, 1.3)
    ry = top + 5
    R = 4.0
    g.torus((0, ry, 0), R, 0.6, 'y', 'metal' if p.lv < 1 else 'orn', 0.6, prio=2)
    for k in range(3):                                       # three thin spokes up from the rod to the ring
        a = 2 * math.pi * (k + 0.25) / 3
        g.tube(bezier((0, top, 0), (math.cos(a) * 1.5, top + 3, math.sin(a) * 1.5),
                      (math.cos(a) * (R - 1), ry - 1, math.sin(a) * (R - 1)), (math.cos(a) * R, ry, math.sin(a) * R), 8),
               0.5, 0.5, 'metal', 0.5, prio=2)
    for k in range(5):                                       # 18° offset → five distinct columns seen from the front
        a = math.radians(18 + 72 * k)
        x, z = math.cos(a) * R, math.sin(a) * R
        ln = (5, 8, 4, 9, 6)[k]
        g.tube([(x, ry - 0.5, z), (x, ry - 2, z)], 0.5, 0.5, 'string', 0.7, prio=1)
        g.tube([(x, ry - 2, z), (x, ry - 2 - ln, z)], 0.6, 0.6, 'metal',
               vfn=lambda t, d, q: 0.4 + 0.3 * (1 - d) + 0.1 * (q[0] > 0), prio=3)
        if p.lv >= 3:
            g.put(round(x), round(ry - 2 - ln), round(z), 'glow', 0.85, glow=True, prio=4)
    g.tube([(0, ry, 0), (0, ry - 2.4, 0)], 0.5, 0.5, 'string', 0.7, prio=1)
    g.ball((0, ry - 3.2, 0), 1.05, 'gem', 0.7, glow=p.glow, prio=4)                          # clapper weight
    if p.lv >= 2:
        g.crystal((0, ry + 0.4, 0), (0, 1, 0), 3.0, 2.4, 'orn', prio=3, tip=0.9)              # little roof
    if p.theme == 'crystal':
        for s in (-1, 1):
            g.crystal((s * R, ry, 0), (s * 0.4, 1, 0), 3.0, 0.8, 'crystal', glow=p.glow, prio=4)
    dress_shaft(g, p, -6, top - 2, ry, ry + 3)


# ───────────────────────────── 0.3.7 신화 6 (myth-037) ─────────────────────────────
# 틀 함수가 p.sig(SIGNATURES)로 부르는 표시 분기. 실루엣은 틀 그대로, 머리 장식만 바꾼다. 붓은 모두 기존 것
# (ball·tube·slab·crystal·torus). 메시가 빛나는 칸의 역할(role)을 'gem'·'crystal'·'edge'·'glow' 넷으로만 남기므로
# effects.py 의 새 효과 6개가 부위별로 다르게 움직이게 부위 표시는 'gem' 으로 한다 (사슬 고리 반짝이, 도깨비불, 종 테·띠),
# 그믐달의 안쪽 날은 'edge' + 빛남.

def _mountain_head(g, p, hy, HX, HY, HZ):
    """태산의 대망치: 손잡이 꼭지 대신 머리 위 봉우리 셋(가운데가 높은 톱니 능선, 바위색 + 밝은 끝), 골짜기에 작은
    호박 결정, 두 타격면(±x)과 옆면(±z)에 호박빛 갈라짐(빛남), 결정 무더기는 +x 타격면 위쪽 한쪽에만."""
    base = hy + HY
    peaks = ((-4.8, 6.0), (0.0, 10.0), (4.8, 7.0))          # (x, 높이) — 가운데가 가장 높다, 골은 깊게

    def ridge(u):
        return max(h - abs(u - x) * 2.0 for x, h in peaks)

    def m(u, v):
        return abs(u) <= HX - 1 and base - 1 <= v <= base + ridge(u)

    g.slab(m, (-HX, base - 1), (HX, base + 11), 'xy', 0, max_half=3, slope=0.8, mat='metal', prio=3, base_half=1,
           vfn=lambda u, v, w, d: ('bone', 0.6) if v >= base + ridge(u) - 0.6 and v > base + 2 else
           0.24 + 0.045 * (v - base) + 0.06 * min(d, 2) - 0.03 * abs(w))
    for (x, y, z, dx) in ((-3.4, base + 2.0, 1.4, -0.2), (3.2, base + 2.5, -1.4, 0.2)):     # 골짜기 결정
        g.crystal((x, y, z), (dx, 1, 0.3 if z > 0 else -0.3), 2.4, 0.7, 'crystal', glow=True, prio=4)
    crack = ((-3.2, -1.0), (-1.4, 0.6), (-0.2, -0.6), (1.6, 1.0), (3.2, 0.2))           # (dy, dz) 지그재그
    for s in (-1, 1):                                        # 타격면 갈라짐 (+ 가지 하나)
        g.tube([(s * HX, hy + a, b) for a, b in crack], 0.5, 0.5, 'glow', 0.45, glow=True, prio=4)
        g.tube([(s * HX, hy - 0.2, -0.6), (s * HX, hy + 1.2, -2.4)], 0.5, 0.5, 'glow', 0.4, glow=True, prio=4)
    for sz in (-1, 1):                                       # 옆면: 보석에서 양쪽 타격면으로 번지는 금
        for sx in (-1, 1):
            pts = [(sx * 1.6, hy + 0.6, sz * HZ), (sx * 3.0, hy - 0.8, sz * HZ), (sx * 4.6, hy + 0.8, sz * HZ),
                   (sx * (HX - 0.6), hy - 1.4, sz * HZ)]
            g.tube(pts, 0.5, 0.5, 'glow', 0.42, glow=True, prio=4)
    crystal_cluster(g, (HX + 0.5, hy + 2, 1), p, 3, 3.0, 0.85, up=(1, 0.55, 0.2), glow=True)


def _mountain_floaters(g, p, hy, top):
    """떠 있는 돌 조각 (바위 덩이 + 호박 결정 끝) — lv4 둘, lv5 셋."""
    pts = [(-13.5, hy + 4, 1), (13.5, hy - 3, -1)] + ([(-9, hy - 10, 0)] if p.lv >= 5 else [])
    for (x, y, z) in pts:
        g.ball((x, y, z), 1.7, 'metal', sq=(1.15, 0.8, 1.0), prio=4,
               vfn=lambda i, j, k, d, y=y: 0.28 + 0.28 * (1 - d) + 0.1 * (j > y))
        g.crystal((x, y + 0.6, z), (-0.3 if x > 0 else 0.3, 1, 0), 2.3, 0.6, 'crystal', glow=True, prio=5)
    return False


def _hightide_blade(g, p, hy, R):
    """만조의 큰낫: 날 끝이 파도 머리처럼 안쪽(자루 쪽 아래)으로 한 번 말리고, 칼등을 따라 흰 거품 줄, 칼등에 조개."""
    def yu(u):
        t = u / R
        return hy + 5.5 * math.sin(math.pi * min(1.0, t * 1.1) * 0.75) - 12.0 * t ** 2.2

    tx, ty = R, yu(R)
    r0 = 3.8
    cx, cy = tx - r0, ty + 0.4                               # 말림의 가운데 = 끝의 안쪽(−x)
    curl, foam = [], []
    for k in range(25):
        t = k / 24
        a = -t * 0.9 * 2 * math.pi                           # 시계 방향: 아래 → 안쪽 → 위로 말려 든다
        r = r0 * (1 - 0.6 * t)
        curl.append((cx + math.cos(a) * r, cy + math.sin(a) * r, 0))
        if t <= 0.62:
            foam.append((cx + math.cos(a) * (r + 1.3), cy + math.sin(a) * (r + 1.3), 0))
    g.tube(curl, 1.5, 0.6, 'blade', prio=3, vfn=lambda t, d, q: 0.42 + 0.2 * (1 - d) + 0.1 * t)
    g.tube(foam, 0.55, 0.5, 'glow', 0.9, glow=True, prio=4)
    for u in range(2, R):                                    # 칼등 거품: 한 줄 + 군데군데 방울
        v = round(yu(u)) + 1
        g.put(u, v, 0, 'glow', 0.86, glow=True, prio=4)
        if u % 3 == 0:
            g.ball((u + 0.4, v + 0.6, 0), 1.1 if u % 2 else 0.8, 'glow', 0.95, glow=True, prio=4)
    shell(g, (9.0, yu(9.0) + 2.2, 1.2), p, 1.45)


def _tide_floaters(g, p, hy, top):
    """물방울 (빛나는 공 + 위로 뾰족한 꼭지) — 기본 떠 있는 결정 대신."""
    pts = [(-7, hy + 5), (8, hy + 10)] + ([(-6, hy - 9)] if p.lv >= 5 else [])
    for (x, y) in pts:
        g.ball((x, y, 0), 1.3, 'glow', glow=True, vfn=lambda i, j, k, d: 0.55 + 0.4 * (1 - d), prio=4)
        g.crystal((x, y + 0.8, 0), (0, 1, 0), 2.0, 0.9, 'glow', glow=True, prio=4, tip=0.9)
    return False


def _comet_head(g, p, H, curv):
    """꼬리별 장궁: 손잡이 앞(−x, 쏘는 쪽)에 빛나는 혜성 머리, 그 뒤로 두 팔을 따라 곧은 빛 줄 셋 (주황 → 흰빛,
    끝으로 가늘게). 줄은 팔보다 앞쪽에 떠서 팔과 겹치지 않는다."""
    hx = -5.2
    g.ball((hx, 0, 0), 2.0, 'flame', glow=True, vfn=lambda i, j, k, d: 0.42 + 0.35 * (1 - d), prio=4)   # 주황 테
    g.ball((hx - 0.8, 0, 0), 1.45, 'glow', glow=True, vfn=lambda i, j, k, d: 0.78 + 0.22 * (1 - d), prio=5)  # 흰 핵
    for s in (1, -1):
        for k, (dx, shorter) in enumerate(((0.0, 0.0), (-3.4, 5.0), (-6.6, 10.0))):
            ey = s * (H - 2 - shorter)
            t = (abs(ey) - 2.5) / (H - 2.5)
            ex = curv * t * t - 0.6 - 1.8 + dx
            g.tube([(hx + 0.6 - 0.8 * k, s * (1.4 + 0.4 * k), 0), (ex, ey, 0)], 0.5, 0.5, 'glow', glow=True, prio=3,
                   vfn=lambda tt, d, q: 0.2 + 0.6 * tt)


def _star_glints(g, pts):
    """작은 네 갈래 별 (XY 면, 한 칸 두께)."""
    for (x, y, z) in pts:
        g.put(x, y, z, 'glow', 0.95, glow=True, prio=5)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            g.put(x + dx, y + dy, z, 'glow', 0.72, glow=True, prio=5)
        for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            g.put(x + dx, y + dy, z, 'glow', 0.45, glow=True, prio=4)


def _wisp_flame(g, p, lx, ly0, ly1, top):
    """도깨비불 등롱: 키운 우리 안의 큰 연두 불(공 + 위로 뾰족한 불꽃), 갈고리 끝 작은 불씨."""
    cy = (ly0 + ly1) / 2
    g.ball((lx, cy - 0.4, 0), 2.2, 'glow', glow=True, vfn=lambda i, j, k, d: 0.3 + 0.4 * (1 - d), prio=4)
    g.crystal((lx, cy + 1.0, 0), (0, 1, 0), 2.6, 1.4, 'glow', glow=True, prio=4, tip=0.8)
    g.ball((lx + 1.1, top + 5.6, 0), 0.95, 'glow', 0.7, glow=True, prio=4)


def _wisp_floaters(g, p, hy, top):
    """등롱 둘레를 도는 도깨비불 셋 ('gem' — wisp_flicker 가 따로 반짝이게) + 꼬리, lv5 는 등롱에 맞춘 halo."""
    lx, cy = 6.5, hy - 7                                     # lamp_crook: hy = top + 4, 등롱 가운데 = top − 3
    Rw = 7.0
    for k, deg in enumerate((35, 155, 275)):
        a = math.radians(deg)
        q = (lx + math.cos(a) * Rw, cy + math.sin(a) * Rw, 1.0 - k)
        g.ball(q, 1.15, 'gem', glow=True, vfn=lambda i, j, kk, d: 0.4 + 0.4 * (1 - d), prio=5)
        tail = [(lx + math.cos(a - b) * Rw, cy + math.sin(a - b) * Rw, q[2]) for b in (0.18, 0.36, 0.52)]
        g.tube([q] + tail, 0.7, 0.5, 'glow', glow=True, prio=4, vfn=lambda t, d, qq: 0.5 - 0.3 * t)
    if p.lv >= 5:
        halo(g, (lx, cy, 0), 9.5, 'z')
        return True
    return False


def _daybreak_bell(g, p, bb, bt, h, apex):
    """새벽의 종: 종 몸에 장밋빛으로 빛나는 가로 띠 둘 + 입구 테('gem' — 울림 고리가 지나가는 자리), 밝은 추,
    종 꼭대기에 작은 고리와 장밋빛 보석, 종 양옆에 울림 물결(짧은 호). 해 원반·햇살·후광은 없다 (치천사의 홀의 해·후광과 갈리게)."""
    for j in (bb + 1, bb + 3):
        t = (bt - j) / max(1, h)
        g.torus((0, j, 0), 1.35 + 2.6 * t ** 1.7, 0.5, 'y', 'gem', 0.5, glow=True, prio=4)
    g.torus((0, bb, 0), 3.6, 0.6, 'y', 'gem', 0.42, glow=True, prio=4)        # lip (bell_toll 의 울림이 여기서 시작)
    g.ball((0, bb - 1.4, 0), 1.35, 'glow', 0.62, glow=True, prio=4)            # clapper
    g.torus((0, apex + 1.2, 0), 1.2, 0.45, 'z', 'orn', 0.62, prio=4)          # 매다는 고리
    g.ball((0, apex + 0.2, 0), 0.95, 'gem', 0.66, glow=True, prio=4)
    if p.lv >= 4:                                                              # 종 양옆 울림 물결 (짧은 호 둘씩, 원 아님)
        cy = (bb + bt) / 2
        for R, w in ((5.4, 0.12), (7.2, 0.09)):
            for mid in (0.0, 0.5):
                g.torus((0, cy, 0), R, 0.42, 'z', 'glow', 0.7, glow=True, prio=3, arc=(mid - w, mid + w))


def _daybreak_floaters(g, p, hy, top):
    """작은 반짝임 둘(lv5 셋). True = halo 를 그리지 않는다 (후광은 치천사의 홀 몫)."""
    _star_glints(g, [(-7, hy + 5, 0), (7, hy - 4, 0)] + ([(-6, hy - 8, 0)] if p.lv >= 5 else []))
    return True


def _waning_sickle(g, p, cells, C, R, gl):
    """그믐달 사슬낫: 안쪽 날 줄을 빛나게(moon_phase 가 이 줄을 따라 밝은 곳을 옮긴다), 손잡이 끝 고리에서 사슬
    여섯 고리가 아래로 휘어 늘어지고 끝에 작은 초승달 추, lv5 는 날 바깥을 감싸는 반달 halo."""
    for (u, v), d in cells.items():
        if d == 0 and math.hypot(u - C[0], v - C[1]) < R - 0.6:
            for w in (-1, 0, 1):
                cur = g.vox.get((u, v, w))
                if cur and cur[0] == 'edge':
                    cur[2] = True
    ring_y = -gl // 2 - 3.5                                  # sickle(): lv≥1 손가락 고리 (R 1.6)
    if p.lv < 1:
        g.torus((0, ring_y, 0), 1.6, 0.5, 'z', 'orn', 0.7)
    path = bezier((0, ring_y - 2.2, 0), (0.4, ring_y - 5.5, 0), (2.2, ring_y - 8.6, 0), (4.8, ring_y - 10.2, 0), 60)
    n = 6
    for k in range(n):
        q = path[int(k / (n - 1) * (len(path) - 1))]
        g.torus(q, 0.95, 0.45, 'z' if k % 2 == 0 else 'x', 'metal', 0.62, prio=3)
        g.put(round(q[0]), round(q[1] + 1), 0, 'gem', 0.8, glow=True, prio=4)       # 고리마다 반짝일 한 칸
    e = path[-1]
    w0 = (e[0] + 0.6, e[1] - 2.0)

    def moon(u, v):
        return math.hypot(u - w0[0], v - w0[1]) <= 2.4 and math.hypot(u - w0[0] - 1.0, v - w0[1] - 0.8) > 2.0
    g.slab(moon, (int(w0[0]) - 3, int(w0[1]) - 3), (int(w0[0]) + 3, int(w0[1]) + 3), 'xy', 0, max_half=1, slope=0.8,
           mat='ice', glow=True, prio=4, vfn=lambda u, v, w, d: 0.62 + 0.12 * min(d, 2))
    g.tube([e, (w0[0] - 0.4, w0[1] + 1.9, 0)], 0.5, 0.5, 'metal', 0.6, prio=3)
    if p.lv >= 5:
        g.torus((C[0], C[1], 0), R + 2.4, 0.5, 'z', 'glow', 0.5, glow=True, prio=4, arc=(-0.08, 0.58))
        for k in range(3):
            a = 2 * math.pi * (-0.08 + 0.66 * k / 2)
            g.gem((C[0] + math.cos(a) * (R + 2.4), C[1] + math.sin(a) * (R + 2.4), 0), 1.0, 'glow', glow=True)


def _waning_frost(g, p, A):
    """초승달 등에 작은 달빛 얼음 조각 셋 (frost 테마 기본 장식인 손잡이 아래 고드름은 사슬 자리라 뺀다)."""
    C, R = A['C'], A['R']
    for deg, size in ((150, 2.0), (95, 2.6), (40, 1.8)):
        a = math.radians(deg)
        g.crystal((C[0] + math.cos(a) * (R + 0.3), C[1] + math.sin(a) * (R + 0.3), 0), (math.cos(a), math.sin(a), 0),
                  size, 0.7, 'ice', glow=p.glow and p.lv >= 4, prio=3)


SIG_FLOATERS = {'mountainheart': _mountain_floaters, 'hightide': _tide_floaters, 'wisp': _wisp_floaters,
                'daybreak': _daybreak_floaters}     # dress_shaft lv≥4 — True 를 돌려주면 halo 도 직접 그렸다
SIG_HALO = {'mountainheart': (3, 11.5)}             # (머리 가운데에서 위로, 반지름) — 태산은 봉우리까지 감싼다


# ───────────────────────────── 0.3.6 곡괭이 (도구, 계약 visual.json pickaxes) ─────────────────────────────
# 등급 = 금속 (구리 < 철 < 은 < 금 < 미스릴 < 오리하르콘). 희귀도(p.lv)가 아니라 id 의 금속 이름으로 고른다 —
# 은·금 곡괭이는 둘 다 rare 라서. 모르는 id 는 희귀도로 (0 구리 · 1 철 · 2 은 · 3 미스릴 · 4+ 오리하르콘).
PICKAXE_KINDS = ('copper', 'iron', 'silver', 'gold', 'mithril', 'orichalcum')
PICKAXE_BY_LV = (0, 1, 2, 4, 5, 5)


def pickaxe_kind(iid, lv=0):
    for k, name in enumerate(PICKAXE_KINDS):
        if iid.startswith(name + '_') or ('_' + name + '_') in iid:
            return k
    return PICKAXE_BY_LV[max(0, min(5, lv))]


def pickaxe(g, p):
    """곡괭이: 자루 + 소켓 + 양쪽 곡괭이 날 (+x 쪽이 '일하는 쪽' — 바닐라 도끼 머리 자리, HEAD_SHAPES).
    구리 = 한쪽 뾰족·한쪽 끌, 녹청 점, 나무 자루 / 철 = 양날 대칭·쇠띠·리벳, 가죽 손잡이 /
    은 = 긴 양날·은 테두리·월장석 / 금 = 넓은 양날·금 테두리·황옥, 짙은 나무 자루에 금 고리 /
    미스릴 = 결정 날끝(빛남)·룬 띠·쇠 자루 / 오리하르콘 = 초승달 양날·붉은 금 테·용혈석·떠다니는 불티 조각(빛남)."""
    L = p.L
    t = pickaxe_kind(p.iid, p.lv)
    top = int(15 * L)
    shaft_mat = 'metal' if t >= 4 else 'wood'
    bands = (top - 2, 5) if t in (1, 2) else ()
    shaft(g, -7, top + 1, 1.25, shaft_mat, bands=bands)
    if t == 3:                                         # 금: 짙은 나무 자루에 금 고리 셋
        for y in (top - 2, 9, 5):
            for i in range(-2, 3):
                for k in range(-2, 3):
                    if i * i + k * k <= 2.3:
                        g.put(i, y, k, 'orn', 0.72 if y == top - 2 else 0.6, prio=2)
    grip(g, -6, 3, mat='grip')
    if t == 0:
        g.box((-1, -8, -1), (1, -8, 1), 'metal', 0.45)
    else:
        pommel(g, -8, p, 1.4 if t < 4 else 1.6)
    hy = top + 2

    # 날 재료: 은 = 밝은 'edge' 램프 (철의 어두운 강철과 갈리게), 오리하르콘 = 붉은 금 ('flame' 램프의 아래쪽: 진홍 → 금)
    blade_mat, bright = {2: ('edge', -0.12), 5: ('flame', -0.2)}.get(t, ('blade', -0.06 if t == 1 else 0.0))

    def arm(sign, length, droop, r0, r1, mat=None, lift=1.2):
        mat = mat or blade_mat
        pts = bezier((0, hy, 0), (sign * length * 0.45, hy + lift, 0), (sign * length * 0.82, hy - droop * 0.35, 0),
                     (sign * length, hy - droop, 0), 18)
        g.tube(pts, r0, r1, mat, prio=2, sq=(1, 1, 0.7),
               vfn=lambda tt, d, q: bright + 0.62 - 0.24 * d + 0.12 * tt - (0.1 if q[1] < hy - 0.6 - droop * tt * tt else 0))
        return pts

    if t == 0:
        pa = arm(1, 11.5, 4.5, 2.6, 0.7)
        pb = arm(-1, 6.5, 1.2, 2.5, 1.9, lift=0.6)
        tip = pb[-1]
        # 끌 날 (0.3.6.1): 구리 팔레트에서 가장 밝은 구리 ('blade' 램프 위쪽). 흰 강철 'edge' 램프는 손에서 흰 덩이로 보였다.
        g.box((tip[0] - 1, tip[1] - 2, -1), (tip[0], tip[1] + 1, 1), 'blade', 0.7, prio=3)
        g.box((tip[0], tip[1] - 2, -1), (tip[0], tip[1] + 1, 1), 'blade', 0.76, prio=3)    # 끝 한 줄만 조금 더 밝게
        rr = random.Random(7)
        for _ in range(9):                                                               # 녹청 점
            q = pa[rr.randrange(2, 14)] if rr.random() < 0.7 else pb[rr.randrange(1, 12)]
            g.put(round(q[0]), round(q[1] + rr.choice((-1, 1))), rr.choice((-1, 1)), 'gem', 0.45, prio=4)
    elif t == 1:
        for s in (1, -1):
            pa = arm(s, 11.0, 4.0, 2.6, 0.7)
            g.put(round(pa[-1][0]), round(pa[-1][1]), 0, 'edge', 0.9, prio=4)
    elif t == 2:
        for s in (1, -1):
            pa = arm(s, 12.0, 4.3, 2.7, 0.7)
            g.tube([(q[0], q[1] + 2.2, q[2]) for q in pa[1:13]], 0.7, 0.5, 'orn', 0.7, prio=3)
    elif t == 3:
        for s in (1, -1):
            pa = arm(s, 12.0, 3.4, 3.3, 1.0, lift=1.0)
            g.tube([(q[0], q[1] + 2.6, q[2]) for q in pa[1:14]], 0.8, 0.55, 'orn', 0.8, prio=3)
            g.tube([(q[0], q[1] - 2.4, q[2]) for q in pa[2:11]], 0.6, 0.5, 'orn', 0.55, prio=3)
            g.put(round(pa[-1][0]), round(pa[-1][1]), 0, 'edge', 0.95, prio=4)
    elif t == 4:
        for s in (1, -1):
            pa = arm(s, 11.5, 3.8, 2.7, 1.0)
            tip, prev = pa[-1], pa[-3]
            d = (tip[0] - prev[0], tip[1] - prev[1], 0)
            g.crystal(tip, d, 4.5, 1.1, 'crystal', glow=True, prio=4, tip=0.6)
            g.crystal((pa[8][0], pa[8][1] + 1.5, 0), (s * 0.3, 1, 0), 2.6, 0.7, 'crystal', glow=True, prio=4)
    else:
        for s in (1, -1):
            pa = arm(s, 12.5, 6.0, 2.8, 0.6, lift=2.2)
            # 붉은 금 테 — 빛나는 칸이라 ember_glow 가 숨쉬듯 달아오르게 한다
            g.tube([(q[0], q[1] + 2.3, q[2]) for q in pa[1:15]], 0.7, 0.5, 'orn', 0.75, glow=True, prio=3)
            g.gem((pa[7][0], pa[7][1], 1.5), 0.9, 'glow', glow=True, prio=5)
            g.gem((pa[7][0], pa[7][1], -1.5), 0.9, 'glow', glow=True, prio=5)
        float_shards(g, [(0, hy + 7, 0), (-5, hy + 5.5, 0.5), (5, hy + 5.5, -0.5)], p, size=2.6, r=0.8, mat='flame')
    # 소켓 (날 위에 덮어 그림)
    g.box((-2, hy - 3, -2), (2, hy + 2, 2), 'metal', 0.5, prio=3,
          vfn=lambda i, j, k: 0.4 + 0.08 * (j > hy) + (0.14 if abs(i) == 2 and abs(k) == 2 else 0))
    if t >= 1:
        for s in (-1, 1):                                                                # 리벳
            g.put(0, hy, s * 2, 'orn' if t >= 2 else 'metal', 0.8, prio=4)
            g.put(-1, hy + 1, s * 2, 'metal', 0.75, prio=4)
            g.put(1, hy - 1, s * 2, 'metal', 0.75, prio=4)
    if t >= 2:                                                                           # 소켓 보석
        mat = 'flame' if t == 5 else 'gem'
        for s in (-1, 1):
            g.gem((0, hy, s * 2.6), 1.2 if t in (2, 5) else 1.0, mat, glow=t >= 4 or t == 2, prio=5)
        g.box((-2, hy + 3, -2), (2, hy + 3, 2), 'orn', 0.65, prio=3)
    if t >= 4:
        for i in range(-2, 3):                                                           # 빛나는 룬 띠
            for k in (-2, 2):
                g.put(i, hy - 2, k, 'glow', 0.85, glow=True, prio=5)
        g.crystal((0, hy + 3, 0), (0, 1, 0), 3.5 if t == 4 else 4.5, 1.0, 'crystal' if t == 4 else 'orn',
                  glow=t == 4, prio=4, tip=0.7)


_TEMPLATES = {
    'longsword': longsword, 'broadsword': broadsword, 'greatsword': greatsword, 'cleaver': cleaver,
    'great_axe': great_axe, 'mace': mace, 'dagger': dagger, 'kris': kris, 'fang_blade': fang_blade,
    'staff_orb': staff_orb, 'staff_crystal': staff_crystal, 'staff_ring': staff_ring, 'scepter': scepter,
    'sun_scepter': sun_scepter, 'censer_staff': censer_staff,
    'warhammer': warhammer, 'falchion': falchion, 'war_scythe': war_scythe, 'glaive': glaive,
    'staff_spiral': staff_spiral, 'staff_fork': staff_fork, 'bell_scepter': bell_scepter,
    'chalice_scepter': chalice_scepter, 'sickle': sickle, 'katar': katar,
    # 0.3.5 (gear_spec §9)
    'executioner_axe': executioner_axe, 'flamberge': flamberge, 'great_maul': great_maul, 'sabre': sabre,
    'morning_star': morning_star, 'rapier': rapier, 'stiletto': stiletto, 'tanto': tanto, 'war_spear': war_spear,
    'antler_staff': antler_staff, 'lamp_crook': lamp_crook, 'thurible_rod': thurible_rod, 'chime_rod': chime_rod,
    # 0.3.6 도구 (곡괭이 — type tool, 손 모습은 무기와 같은 displays.voxel_weapon)
    'pickaxe': pickaxe,
}
BOWS = ('longbow', 'recurve_bow', 'composite_bow', 'horn_bow', 'blade_bow', 'bone_bow', 'twin_bow')
TWO_HANDED = {'greatsword', 'cleaver', 'great_axe', 'war_scythe', 'glaive',
              'executioner_axe', 'flamberge', 'great_maul', 'war_spear'}
# 머리(날·망치·등롱·향로)가 자루 옆으로 튀어나온 모양 — tools/hold_preview.py 가 바닐라 도끼 행과 함께 비교한다
HEAD_SHAPES = ('war_scythe', 'sickle', 'great_axe', 'cleaver', 'warhammer', 'mace', 'glaive', 'falchion',
               'executioner_axe', 'great_maul', 'morning_star', 'lamp_crook', 'thurible_rod', 'pickaxe')

# 손에 드는 각도 (displays.weapon). 모든 무기는 날·머리(+x)가 1인칭 화면 안쪽·3인칭 몸 앞쪽을 향하고,
# 1인칭 y 회전 기본값은 90° (바닐라 도끼와 같은 각도: 날을 뒤에서 봄). 초승달 날(낫·낫단검)은 90° 면 날을
# 끝에서 봐서 휘두를 때 거의 안 보이므로 125° 로 더 돌려 초승달 면이 비스듬히 보이게 한다 → 내려벨 때 날이
# 아래로 휘감아 들어가는 모습. 손잡이 위치는 displays.held 가 각도와 상관없이 그대로 맞춘다.
# 사브르(0.3.5)는 100°: 곡도 휨이 1인칭에서 살짝 보이게 (낫보다 적게). fp_mul = 1인칭 크기 배율 — 대형 망치의
# 큰 머리는 휘두를 때 화면 가운데를 넓이 규칙보다 많이 덮어서 0.85 (hold_preview: 가운데 덮음 21% → 16%, 바닐라 검 17%).
HOLD = {'war_scythe': {'fp_yaw': 125}, 'sickle': {'fp_yaw': 125}, 'sabre': {'fp_yaw': 100},
        'great_maul': {'fp_mul': 0.85}}
_BUILT: dict[str, str] = {}      # item id → shape of the template that last built it


def hold_of(name):
    """Hold parameters for the item `name` built by one of TEMPLATES ({} = defaults)."""
    return HOLD.get(_BUILT.get(name, ''), {})


def _recorded(shape, fn):
    def build(g, p):
        _BUILT[p.iid] = shape        # read back by displays.voxel_weapon(m) via m.name == p.iid
        return fn(g, p)
    build.__name__, build.__doc__ = fn.__name__, fn.__doc__
    return build


TEMPLATES = {shape: _recorded(shape, fn) for shape, fn in _TEMPLATES.items()}
