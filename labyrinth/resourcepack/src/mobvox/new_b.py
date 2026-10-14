"""새 몬스터 복셀 설계 B — 용인족 5 · 켄타우로스 2 · 나가 2 · 미노타우로스 1.  README.md · NEW_MOBS.md 참고.

용인족: thorn_kobold(1) · kobold_sapper(2) · forge_dragonkin(5) · crystal_dragonkin(7) · abyss_dragonkin(10)
켄타우로스: myconid_centaur(3) · prism_centaur(7)   나가: tide_naga(4) · ink_naga(8)   미노타우로스: brass_minotaur(9)
몸 형태가 같은 몹은 공통 부위 함수(_dk_* · _ct_* · _ng_*)를 쓰고, 몹마다 재질 램프와 장식(_FX)만 바꾼다.
좌표: 부위 px, 원점 = 그 부위 pivot, 정면 = −Z, 모델 −X = 몹의 왼쪽.  머리 무리(뿔·볏·고글·후드·코뚜레)는
ctx.offset_to('head') 로 머리 좌표에서 그린다(_At).  사슬 꼬리·목 끝은 다음 마디 pivot 까지 둥글게 잇는다.
날개(wing form)는 XZ 평면(폭 = 바깥 X, 앞전 = −Z)의 뼈대+막 — _xz_wing.
"""
from __future__ import annotations

import math

from ..util import h2, h3
from ..voxel.mob_kit import MobGrid, fbm3, vadd, vlen, vmul, vnorm, vsub  # noqa: F401
from ..voxel.palette import _r

GLOW_MATS = ('glow', 'eye', 'core', 'rune', 'lava')


# 몹별 복셀 크기 배율(덩치 큰 몹은 굵게 — 900 요소 예산) · 구운 빛 세기(곡면이 덜 쪼개짐)
_VS_MUL = {'kobold_sapper': 1.05, 'forge_dragonkin': 1.35, 'crystal_dragonkin': 1.28, 'abyss_dragonkin': 1.5,
           'myconid_centaur': 1.1, 'prism_centaur': 1.05, 'tide_naga': 1.15, 'ink_naga': 1.2, 'brass_minotaur': 1.08}
_LIGHT = 0.7


def _grid(ctx, vs):
    g = ctx.grid(vs * _VS_MUL.get(ctx.mid, 1.0))
    g.light_mul = _LIGHT
    return g


def _ramps(ctx, table):
    """몹 전체 램프.  발광 램프는 11단계로 늘려 아틀라스 맥동이 거친 단계에서도 남게 한다."""
    for mat, cols in table.items():
        ctx.set_ramp(mat, _r(cols, 11) if mat in GLOW_MATS else cols)


class _At:
    """다른 부위(보통 머리) 좌표 → 이 부위 좌표.  p(x, y, z) = 그 부위 pivot 기준 점."""

    def __init__(self, ctx, name='head'):
        self.o = ctx.offset_to(name) or (0.0, 0.0, 0.0)

    def __call__(self, x, y, z):
        return (x + self.o[0], y + self.o[1], z + self.o[2])


def _size(ctx, name, default):
    p = ctx.part_def(name)
    return tuple(float(v) for v in (p.get('size') if p else None) or default)


def _loft(g, z0, z1, sec, mat, val=0.5, vfn=None, p=2.0, prio=1, glow=False):
    """Z 방향 단면 채우기: sec(z) → (cx, cy, rx, ry) | None, 초타원 지수 p(2 = 타원, 클수록 각짐).
    vfn(x, y, z, q) — q = 단면 안 정규 거리(0 중심 … 1 가장자리)."""
    vs = g.vs
    a, b = min(z0, z1), max(z0, z1)
    for k in g._range(a, b):
        z = k * vs
        if z < a - 1e-6 or z > b + 1e-6:
            continue
        s = sec(z)
        if not s:
            continue
        cx, cy, rx, ry = s
        for i in g._range(cx - rx, cx + rx):
            u = abs(i * vs - cx) / max(rx, 1e-6)
            if u > 1:
                continue
            for j in g._range(cy - ry, cy + ry):
                y = j * vs
                v = abs(y - cy) / max(ry, 1e-6)
                q = u ** p + v ** p
                if q > 1:
                    continue
                res = vfn(i * vs, y, z, q) if vfn else val + 0.12 * (y - cy) / max(ry, 1e-6)
                g._emit((i, j, k), res, mat, glow, prio)


def _poly_in(poly, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _xz_wing(g, ctx, bone='bone', mem='membrane', val=0.5, vein=None, claw='claw', fingers=3, tatter=0.0, lift=0.9,
             thick=1):
    """날개(wing form): 뿌리 = 원점, ctx.out 쪽으로 폭 w, 앞전 = −Z, 막은 y≈0 의 얇은 판.
    앞전 팔뼈(어깨 → 팔꿈치 → 손목) + 손가락뼈가 뒤로 부채꼴, 손가락 사이 가장자리는 둥글게 파였다."""
    o = ctx.out
    W, H, D = ctx.size
    elbow = (o * W * 0.24, lift * 0.7, -D * 0.28)
    wrist = (o * W * 0.48, lift, -D * 0.42)
    tips = []
    for f in range(fingers):
        t = f / max(1, fingers - 1)
        tips.append((o * W * (1.0 - 0.42 * t), lift * 0.4 * (1 - t), -D * 0.3 + D * 1.05 * t))
    back = (o * W * 0.1, 0.0, D * 0.62)
    g.limb([(0, 0, 0), elbow, wrist], [1.0, 0.8, 0.62], bone, val + 0.1, knob=1.15, prio=3)
    for tip in tips:
        mid = ((wrist[0] + tip[0]) / 2, (wrist[1] + tip[1]) / 2 + 0.3, (wrist[2] + tip[2]) / 2)
        g.sweep([wrist, mid, tip], 0.5, 0.3, bone, val + 0.05, prio=3)
    g.cone(wrist, (o * 0.3, 0.5, -1), 1.6, 0.45, claw, 0.45, 0.85, prio=4)          # 엄지 발톱
    poly = [(0.0, -D * 0.12), (elbow[0], elbow[2]), (wrist[0], wrist[2])] + [(t[0], t[2]) for t in tips] + \
           [(back[0], back[2])]
    edge = [(t[0], t[2]) for t in tips] + [(back[0], back[2])]
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    vs = g.vs
    sd = g.seed + 19
    for i in g._range(min(xs), max(xs)):
        x = i * vs
        for k in g._range(min(zs), max(zs)):
            z = k * vs
            if not _poly_in(poly, x, z):
                continue
            bite = False
            for (x1, z1), (x2, z2) in zip(edge, edge[1:]):
                mx, mz = (x1 + x2) / 2, (z1 + z2) / 2
                L = math.hypot(x2 - x1, z2 - z1)
                cx, cz = mx + (wrist[0] - mx) * 0.1, mz + (wrist[2] - mz) * 0.1
                if math.hypot(x - cx, z - cz) < L * 0.3:
                    bite = True
                    break
            if bite or (tatter and h2(i, k, sd) < tatter * 0.12):
                continue
            v = val + 0.16 * (abs(x) / max(1.0, W) - 0.5)
            m = mem
            for tip in tips:
                ax, az = tip[0] - wrist[0], tip[2] - wrist[2]
                L2 = ax * ax + az * az
                s = ((x - wrist[0]) * ax + (z - wrist[2]) * az) / max(1e-6, L2)
                if 0.1 < s < 1 and abs((x - wrist[0]) * az - (z - wrist[2]) * ax) / math.sqrt(L2) < vs * 0.8:
                    if vein:
                        m, v = vein, 0.6
                    else:
                        v -= 0.12
            y = lift * 0.35 * max(0.0, 1 - abs(x) / max(1.0, W))
            for w_ in range(int(thick)):
                g.put(i, int(round(y / vs)) - w_, k, m, v, m in GLOW_MATS, 2)


def _gem(g, c, r, mat='glow', setting='orn', glow=True):
    g.blob(c, r + 0.45, setting, 0.55, prio=4)
    g.blob(vadd(c, (0, 0, -0.35)), r, mat, 0.7, glow=glow, prio=5,
           vfn=lambda x, y, z, d: 0.85 - 0.3 * d)


# ═════════════════════════════════ 용인족 (dragonkin) 공통 ═════════════════════════════════
# 머리 = 두개골 + 긴 윗주둥이(끝이 턱 끝에 맞음) · 턱 = pivot 뒤 1.5px(닫히면 머리 안)부터 앞으로 · 팔 = 어깨에서 아래로,
# 주먹 = ctx.hand · 다리 = 엉덩이에서 아래로 디지티그레이드(무릎 앞, 발목 뒤, 발가락 앞) · 꼬리 = 뒤(+Z)로 처짐.

def _dk_snout(ctx):
    """머리 좌표의 주둥이 끝 z 와 입 선 y (턱 pivot·크기에서)."""
    w, h, d = ctx.size
    jo = ctx.offset_to('jaw') if ctx.part_def('jaw') else None
    if jo is None:
        return -d * 0.75, -h * 0.3
    jd = _size(ctx, 'jaw', (5, 2, 4))[2]
    return jo[2] - jd * 0.8, jo[1] + 0.25


def _dk_head(g, ctx):
    w, h, d = ctx.size
    tip, mb = _dk_snout(ctx)
    cz = d * 0.1
    g.blob((0, h * 0.1, cz), (w * 0.47, h * 0.44, d * 0.34), 'skin', 0.5, top=0.16)            # 두개골
    zb = cz - d * 0.05

    def sec(z):
        t = max(0.0, min(1.0, (z - tip) / (zb - tip)))
        yt = mb + h * 0.32 + h * 0.3 * t
        return (0.0, (mb + yt) / 2, w * 0.24 + w * 0.17 * t, (yt - mb) / 2)
    _loft(g, tip + 0.4, zb, sec, 'skin', p=2.4,
          vfn=lambda x, y, z, q: ('skin2', 0.55) if y < mb + 0.55 else 0.5 + 0.1 * (y - mb) / h)
    g.blob((0, mb + h * 0.17, tip + 0.75), (w * 0.25, h * 0.17, 0.8), 'skin', 0.56)               # 콧등 끝
    for s in (-1, 1):
        g.dot((s * w * 0.12, mb + h * 0.26, tip + 0.1), 'mouth', 0.1, prio=6)                   # 콧구멍
        g.capsule((s * w * 0.18, h * 0.3, cz - d * 0.3), (s * w * 0.45, h * 0.22, cz + d * 0.02), h * 0.09,
                  h * 0.08, 'skin', 0.62, prio=2)                                                 # 눈두덩
        g.eye((s * w * 0.37, h * 0.12, cz - d * 0.2), max(0.55, h * 0.11), val=0.62, socket=h * 0.05,
              facing=(s * 0.55, 0.05, -1), slit=True)
        g.teeth((s * w * 0.18, mb, tip + 0.9), (s * w * 0.33, mb, cz - d * 0.22), 3, max(0.7, h * 0.14),
                r=0.4, direction=(0, -1, 0))
    g.scales(['skin'], size=1.8, amount=0.12)


def _dk_jaw(g, ctx):
    w, h, d = ctx.size
    zt, zb = -d * 0.8, d * 0.4 + 0.8

    def sec(z):
        t = max(0.0, min(1.0, (z - zt) / (zb - zt)))
        yb = -h * 0.72 - h * 0.28 * t
        return (0.0, (0.15 + yb) / 2, w * 0.3 + w * 0.2 * t, (0.15 - yb) / 2)
    _loft(g, zt, zb, sec, 'skin', p=2.2,
          vfn=lambda x, y, z, q: ('skin2', 0.55) if y < -h * 0.55 else 0.48)
    g.paint(lambda x, y, z, n, m, v: ('mouth', 0.25) if (n[1] > 0 and y > -0.2 and abs(x) < w * 0.26) else None,
            ['skin', 'skin2'])
    for s in (-1, 1):
        g.teeth((s * w * 0.2, 0.1, zt + 0.7), (s * w * 0.36, 0.1, zb - 1.6), 3, max(0.6, h * 0.35), r=0.38,
                direction=(0, 1, 0), seed=s + 2)


def _dk_torso(g, ctx):
    w, h, d = ctx.size
    g.blob((0, h * 0.16, 0.1), (w * 0.5, h * 0.38, d * 0.52), 'skin', 0.5, top=0.12)               # 가슴
    g.capsule((0, h * 0.02, 0.2), (0, -h * 0.4, 0.1), w * 0.36, w * 0.39, 'skin', 0.46,
              sq=(1.0, 1.0, min(1.0, d / w * 1.2)))                                               # 허리·골반
    g.rbox((-w * 0.24, -h * 0.44, -d * 0.5 - 0.15), (w * 0.24, h * 0.28, -d * 0.2), 'skin2', 0.55, bevel=0.6)
    g.bands(['skin2'], axis=1, period=1.6, width=0.5, amount=-0.16)                               # 배 비늘판
    for s in (-1, 1):
        g.blob((s * w * 0.45, h * 0.36, 0.1), (w * 0.2, h * 0.17, d * 0.42), 'skin', 0.56)         # 어깨
    H = ctx.offset_to('head')
    hh = _size(ctx, 'head', (7, 6, 9))[1]
    g.capsule((0, h * 0.36, 0.4), (H[0], H[1] - hh * 0.32, H[2] + 1.0), w * 0.2, w * 0.17, 'skin', 0.5)  # 목
    g.spikes([(0, h * (0.42 - 0.2 * k), d * 0.5 + 0.1) for k in range(4)], (0, 0.35, 1), max(1.0, d * 0.22),
             0.5, 'horn', 0.45)
    g.mottle(['skin'], 0.07, 4.0)


def _dk_arm(g, ctx):
    w, h, d = ctx.size
    g.blob((0, -0.5, 0), (w * 0.58, w * 0.55, w * 0.58), 'skin', 0.52)
    g.capsule((0, -0.6, 0), (0, -h * 0.47, 0.3), w * 0.42, w * 0.36, 'skin', 0.5)
    g.blob((0, -h * 0.48, 0.35), w * 0.38, 'skin', 0.56)
    g.capsule((0, -h * 0.5, 0.3), (0, -h * 0.84, -0.2), w * 0.37, w * 0.32, 'skin', 0.47)
    hy = -h + 1.0
    g.blob((0, hy, -0.3), (w * 0.42, w * 0.44, w * 0.46), 'skin', 0.5)                             # 주먹
    for k in (-1, 0, 1):
        g.cone((k * w * 0.22, hy - w * 0.15, -w * 0.42), (0, -0.7, -1), max(0.8, w * 0.32), 0.35, 'claw',
               0.45, 0.85, prio=4)


def _dk_legs(g, ctx, toe=1.0):
    w, h, d = ctx.size
    g.rbox((-w * 0.42, -2.0, -d * 0.42), (w * 0.42, 0.8, d * 0.45), 'skin', 0.46, bevel=0.8)      # 골반
    for s in (-1, 1):
        x = s * w * 0.27
        hip, knee = (x, -0.8, 0.2), (x * 1.06, -h * 0.42, -1.5)
        ank, foot = (x * 1.06, -h * 0.79, 1.0), (x, -h + 0.75, -0.2)
        g.limb([hip, knee, ank, foot], [w * 0.2, w * 0.15, w * 0.1, w * 0.11], 'skin', 0.48, knob=1.12)
        for k in (-1, 0, 1):
            a = (x + k * w * 0.06, -h + 0.6, -0.4)
            b = (x + k * w * 0.13, -h + 0.45, -d * 0.45 - 1.3 * toe)
            g.capsule(a, b, w * 0.075, w * 0.06, 'skin', 0.5)
            g.cone(b, (0, -0.5, -1), 0.9 * toe, 0.35, 'claw', 0.45, 0.85, prio=4)
        g.cone((x, -h + 0.9, 0.6), (0, -0.4, 1), 0.9, 0.35, 'claw', 0.45, 0.8, prio=4)              # 며느리발톱


def _dk_tail(g, ctx, droop=0.45, spikes=True):
    """tail(한 덩이) 또는 tail_1 → tail_2 사슬.  다음 마디가 있으면 그 pivot 까지 같은 굵기로 잇는다."""
    w, h, d = ctx.size
    nxt = {'tail_1': 'tail_2'}.get(ctx.name)
    r0 = min(w, h) * 0.5
    if nxt and ctx.part_def(nxt):
        e = ctx.offset_to(nxt)
        end = (e[0], e[1], e[2] + 0.5)
        r1 = min(_size(ctx, nxt, (3, 3, 9))[:2]) * 0.5
    else:
        end = (0.0, -h * droop * 1.6, d)
        r1 = 0.35
    mid = (end[0] * 0.5, end[1] * 0.45, end[2] * 0.5)
    g.sweep([(0, 0, -0.6), mid, end], r0, r1, 'skin', 0.5,
            vfn=lambda t, dd, p: ('skin2', 0.52) if p[1] < (t * end[1]) - r0 * (1 - 0.5 * t) * 0.55 else 0.48)
    if spikes:
        pts = []
        for k in range(1, 4):
            t = k / 4
            pts.append((end[0] * t, end[1] * t * (0.9 + 0.1 * t) + (r0 + (r1 - r0) * t) * 0.85, end[2] * t))
        g.spikes(pts, (0, 1, 0.6), max(0.8, r0 * 0.7), 0.4, 'horn', 0.45)
    return end


def _dk_strap(g, a, b, c, mat='leather', r=0.5, val=0.42):
    g.sweep([a, b, c], r, r, mat, val)


# ── 1층 가시덩굴 코볼트 thorn_kobold ── 작은 도마뱀 창병: 가죽끈 갑옷, 어깨·팔뚝의 가시덩굴, 이끼 술, 뿌리 자루 창 + 돌 촉

KOBOLD_RAMPS = {
    'skin': [(14, 22, 10), (28, 42, 16), (46, 66, 24), (70, 96, 36), (102, 128, 52), (140, 164, 80), (186, 204, 124)],
    'skin2': [(40, 44, 20), (80, 86, 40), (126, 132, 66), (170, 176, 100), (208, 210, 142), (236, 236, 186)],
    'eye': [(110, 50, 8), (196, 112, 18), (248, 176, 44), (255, 222, 120), (255, 246, 210), (255, 255, 255)],
    'leather': [(22, 14, 8), (42, 28, 16), (68, 46, 26), (98, 68, 40), (132, 94, 58), (168, 124, 82)],
    'bark': [(20, 14, 8), (40, 28, 16), (64, 46, 26), (92, 68, 40), (124, 94, 58), (158, 124, 82)],
    'stone': [(30, 32, 30), (52, 54, 50), (78, 80, 74), (108, 110, 100), (140, 142, 130), (176, 176, 162)],
    'vine': [(18, 26, 10), (34, 48, 18), (54, 72, 28), (80, 100, 40), (110, 132, 58)],
    'horn': [(30, 24, 14), (62, 50, 30), (100, 84, 52), (146, 128, 86), (192, 176, 130), (228, 218, 180)],
}


def _thorns(g, a, b, R, turns=1.6, phase=0.0, n=4):
    """가시덩굴 감기 + 바깥으로 뻗은 가시."""
    g.vine_wrap(a, b, R, turns=turns, phase=phase, r=0.34, leaves=0.3, leaf_size=0.7)
    ax = vsub(b, a)
    for k in range(n):
        t = (k + 0.5) / n
        ang = phase + turns * 2 * math.pi * t
        p = vadd(a, vmul(ax, t))
        out = (math.cos(ang), 0.15, math.sin(ang))
        g.cone(vadd(p, vmul(out, R)), out, 0.9, 0.3, 'horn', 0.5, 0.85, prio=4)


def _kobold_fx(g, ctx, part):
    w, h, d = ctx.size
    if part == 'torso':
        for s in (-1, 1):                                                                         # 엇갈린 가죽끈
            _dk_strap(g, (s * w * 0.42, h * 0.46, -0.6), (0, h * 0.02, -d * 0.62), (-s * w * 0.4, -h * 0.34, -d * 0.4))
        g.rbox((-w * 0.46, -h * 0.5, -d * 0.6), (w * 0.46, -h * 0.36, d * 0.6), 'leather', 0.36, bevel=0.4)
        g.rbox((w * 0.18, -h * 0.62, -d * 0.66), (w * 0.4, -h * 0.4, -d * 0.3), 'leather', 0.5, bevel=0.3)
        g.rbox((-w * 0.08, -h * 0.5, -d * 0.66), (w * 0.08, -h * 0.36, -d * 0.58), 'stone', 0.7)  # 돌 버클
        g.blob((w * 0.46, h * 0.44, 0.2), (w * 0.24, h * 0.1, d * 0.46), 'leather', 0.48, prio=3)  # 왼 어깨 가죽
        _thorns(g, (-w * 0.6, h * 0.5, -0.6), (-w * 0.3, h * 0.2, 1.0), w * 0.18, phase=0.6, n=3)
        g.clumps(3, 1.0, 'moss', 0.55, mats=['skin', 'leather'], region=lambda x, y, z: y > h * 0.3)
    elif part == 'head':
        g.spikes([(0, h * 0.52, d * 0.1 + k * 1.1) for k in range(3)], (0, 1, 0.5), 1.1, 0.4, 'horn', 0.45)
        g.clumps(2, 0.8, 'moss', 0.55, mats=['skin'], region=lambda x, y, z: z > 0)
    elif part == 'arm':
        g.rbox((-w * 0.44, -h * 0.8, -w * 0.44), (w * 0.44, -h * 0.6, w * 0.44), 'leather', 0.42, bevel=0.4)
        _thorns(g, (0, -h * 0.2, 0), (0, -h * 0.55, 0.3), w * 0.42, turns=1.3, phase=ctx.out, n=3)
    elif part == 'legs':
        g.cloth([(-w * 0.32, -0.6, -d * 0.5), (w * 0.32, -0.6, -d * 0.5)], 4.0, 'leather', 0.45, tatter=0.5)
        g.rbox((-w * 0.45, -1.2, -d * 0.5), (w * 0.45, 0.2, d * 0.5), 'leather', 0.36, bevel=0.3)
        g.branch((w * 0.3, -1.4, d * 0.4), (0.4, -1, 0.3), 2.6, 0.3, depth=1, fork=2, mat='bark', val=0.4)
    elif part == 'tail':
        g.clumps(2, 0.7, 'moss', 0.55, mats=['skin'])


def _kobold_horns(g, ctx):
    A = _At(ctx)
    hw, hh, hd = _size(ctx, 'head', (7, 6, 9))
    for s in (-1, 1):
        b = A(s * hw * 0.26, hh * 0.42, hd * 0.16)
        g.horn(b, (s * 0.25, 0.45, 1), 4.2, 0.7, curl=(s * 0.3, 1.2, 0.4), mat='horn', val=0.42, rings=0.8)
        g.blob(A(s * hw * 0.26, hh * 0.36, hd * 0.12), 0.85, 'horn', 0.35)


def _kobold_spear(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    zb, zt = hz + L / 3, hz - L * 2 / 3
    g.sweep([(hx, hy, zb), (hx + 0.25, hy + 0.15, (zb + zt) / 2), (hx, hy, zt + 3.6)], 0.62, 0.5, 'bark', 0.5,
            vfn=lambda t, dd, p: 0.42 + 0.14 * (1 - dd) + (0.1 if (int(t * 17) % 5 == 0) else 0))
    g.capsule((hx, hy, hz + 1.5), (hx, hy, hz - 1.5), 0.8, 0.8, 'leather', 0.45)
    g.vine_wrap((hx, hy, zt + 4.4), (hx, hy, zt + 2.8), 0.7, turns=2.0, r=0.3, leaves=0.0)
    g.sweep([(hx, hy, zt + 3.4), (hx, hy, zt + 1.6), (hx, hy, zt)], 1.0, 0.3, 'stone', 0.55, sq=(0.5, 1.0, 1.0),
            rfn=lambda t: max(0.3, 1.6 * math.sin(math.pi * (0.18 + 0.82 * t)) ** 0.8),
            vfn=lambda t, dd, p: 0.42 + 0.3 * (1 - dd) + 0.12 * t)
    for k, z in enumerate((zb - 2.0, hz - 4.0, hz - 8.0)):                                        # 남은 가시
        s = 1 if k % 2 else -1
        g.cone((hx + s * 0.5, hy + 0.3, z), (s, 0.6, -0.4), 1.0, 0.3, 'horn', 0.5, 0.85, prio=3)
    g.branch((hx, hy, zb - 0.2), (0.2, -0.6, 1), 2.2, 0.35, depth=1, fork=2, mat='bark', val=0.38)  # 뿌리 끝


# ── 2층 코볼트 폭파병 kobold_sapper ── 코볼트 머리 + 이마 고글, 그을린 가죽 조끼와 폭탄 띠, 등의 화약통, 왼손 폭탄(불붙은 심지)

SAPPER_RAMPS = {
    'skin': [(22, 14, 10), (42, 26, 16), (68, 42, 24), (98, 62, 34), (132, 86, 48), (168, 116, 68), (206, 154, 100)],
    'skin2': [(52, 36, 22), (96, 70, 44), (142, 108, 70), (184, 148, 102), (218, 186, 140), (240, 218, 182)],
    'eye': [(120, 36, 6), (200, 84, 14), (250, 146, 38), (255, 206, 104), (255, 242, 196), (255, 255, 255)],
    'leather': [(18, 12, 8), (34, 22, 14), (56, 36, 22), (82, 54, 32), (110, 74, 46), (142, 100, 64)],
    'iron': [(14, 14, 16), (30, 30, 34), (52, 52, 56), (80, 80, 84), (112, 112, 114), (150, 148, 146), (190, 188, 182)],
    'brass': [(40, 26, 8), (80, 56, 18), (130, 96, 36), (180, 140, 64), (222, 186, 104), (246, 224, 160)],
    'glow': [(140, 50, 10), (220, 100, 20), (255, 160, 50), (255, 214, 120), (255, 246, 210), (255, 255, 255)],
    'horn': [(26, 20, 14), (52, 42, 30), (86, 72, 52), (128, 110, 82), (172, 154, 120), (212, 200, 166)],
    'cloth': [(30, 24, 18), (54, 44, 32), (82, 68, 50), (112, 96, 72), (146, 128, 98)],
    'lens': [(40, 20, 6), (90, 50, 14), (150, 96, 30), (210, 160, 70), (250, 226, 160)],
}


def _soot(g, mats, amount=0.35, scale=2.0, seed=0):
    """그을음: 잡음 덩어리를 어둡게."""
    sd = g.seed + 503 + seed
    g.paint(lambda x, y, z, n, m, v: v - 0.22 if fbm3(x / scale, y / scale, z / scale, sd) > 1 - amount else None,
            mats)


def _sapper_fx(g, ctx, part):
    w, h, d = ctx.size
    if part == 'torso':
        g.rbox((-w * 0.46, -h * 0.42, -d * 0.6), (w * 0.46, h * 0.36, -d * 0.1), 'leather', 0.45, bevel=0.8)  # 조끼
        g.rbox((-w * 0.4, h * 0.0, -d * 0.66), (-w * 0.08, h * 0.22, -d * 0.5), 'leather', 0.55, bevel=0.3)
        g.rbox((-w * 0.47, -h * 0.5, -d * 0.62), (w * 0.47, -h * 0.36, d * 0.6), 'leather', 0.32, bevel=0.4)
        g.rbox((-w * 0.08, -h * 0.5, -d * 0.68), (w * 0.08, -h * 0.36, -d * 0.6), 'brass', 0.6)
        pts = [(w * 0.42, h * 0.44, -0.4), (0, h * 0.1, -d * 0.72), (-w * 0.42, -h * 0.3, -d * 0.5)]
        _dk_strap(g, *pts, r=0.55, val=0.38)                                                       # 폭탄 띠
        for t in (0.25, 0.5, 0.75):
            p = (pts[0][0] + (pts[2][0] - pts[0][0]) * t, pts[0][1] + (pts[2][1] - pts[0][1]) * t, -d * 0.82)
            g.blob(p, 0.85, 'iron', 0.45, prio=4)
            g.dot(vadd(p, (0, 0.9, 0)), 'brass', 0.7, prio=5)
        _soot(g, ['leather', 'skin2'], 0.3)
        g.streaks('rust', ['iron', 'leather'], density=0.15, length=(1.0, 2.5), val=0.4)
    elif part == 'head':
        for s in (-1, 1):
            g.cone((s * w * 0.3, h * 0.4, d * 0.22), (s * 0.3, 0.6, 1), 1.6, 0.6, 'horn', 0.4, 0.75)
        _soot(g, ['skin'], 0.25, 1.6)
    elif part == 'arm':
        g.rbox((-w * 0.5, -h * 0.86, -w * 0.5), (w * 0.5, -h * 0.58, w * 0.5), 'leather', 0.4, bevel=0.5)  # 장갑
        g.ring((0, -h * 0.6, 0), w * 0.5, 0.3, axis='y', mat='brass', val=0.6)
        _soot(g, ['leather', 'skin'], 0.3, 1.4, seed=ctx.out > 0)
    elif part == 'legs':
        g.rbox((-w * 0.47, -3.4, -d * 0.52), (w * 0.47, 0.4, d * 0.52), 'cloth', 0.42, bevel=0.6)  # 짧은 바지
        g.rbox((-w * 0.47, -0.4, -d * 0.55), (w * 0.47, 0.6, d * 0.55), 'leather', 0.35, bevel=0.3)
        g.rbox((w * 0.3, -2.6, -d * 0.6), (w * 0.52, -0.6, d * 0.1), 'leather', 0.5, bevel=0.3)    # 도구 주머니
        _soot(g, ['cloth'], 0.3, 1.6)


def _sapper_goggles(g, ctx):
    A = _At(ctx)
    hw, hh, hd = _size(ctx, 'head', (7, 6, 9))
    y, z = hh * 0.42, hd * 0.1 - hd * 0.28
    for s in (-1, 1):
        c = A(s * hw * 0.2, y + 0.2, z - 0.2)
        g.cylinder(c, vadd(c, (0, 0.4, -1.0)), 1.0, 0.95, 'brass', 0.55)
        g.blob(vadd(c, (0, 0.35, -0.95)), (0.75, 0.75, 0.3), 'lens', 0.5, prio=5,
               vfn=lambda x, y_, z_, d_: 0.85 - 0.5 * d_)
        g.sweep([A(s * hw * 0.34, y, z + 0.2), A(s * hw * 0.5, y - 0.2, hd * 0.12),
                 A(s * hw * 0.4, y - 0.1, hd * 0.42)], 0.45, 0.45, 'leather', 0.36)
    g.capsule(A(-hw * 0.08, y + 0.2, z - 0.2), A(hw * 0.08, y + 0.2, z - 0.2), 0.4, 0.4, 'brass', 0.45)


def _sapper_satchel(g, ctx):
    w, h, d = ctx.size
    g.cylinder((0, -h * 0.5, 0.2), (0, h * 0.42, 0.2), w * 0.36, w * 0.34, 'leather', 0.45)     # 화약통
    for y in (-h * 0.36, h * 0.3):
        g.ring((0, y, 0.2), w * 0.37, 0.35, axis='y', mat='brass', val=0.55)
    for s in (-1, 1):
        g.cylinder((s * w * 0.42, -h * 0.45, 0.6), (s * w * 0.42, h * 0.18, 0.6), w * 0.16, w * 0.16, 'cloth', 0.45)
        g.ring((s * w * 0.42, -h * 0.1, 0.6), w * 0.17, 0.25, axis='y', mat='leather', val=0.35)
    g.cylinder((0, h * 0.42, 0.2), (0, h * 0.5, 0.2), w * 0.24, w * 0.22, 'iron', 0.5)
    g.sweep([(0, h * 0.5, 0.2), (0.6, h * 0.62, 0.4), (1.4, h * 0.7, -0.2), (1.9, h * 0.62, -0.8)], 0.3, 0.25,
            'cloth', 0.6)                                                                          # 도화선
    g.dot((1.9, h * 0.66, -0.9), 'glow', 0.9, glow=True, prio=6)
    g.rbox((-w * 0.5, h * 0.05, -d * 0.62), (w * 0.5, h * 0.18, -d * 0.4), 'leather', 0.32)         # 멜빵 고리
    _soot(g, ['leather', 'cloth'], 0.3, 1.5)
    g.streaks('rust', ['iron', 'brass'], density=0.2, length=(0.8, 2.0), val=0.4)


def _sapper_bomb(g, ctx):
    hx, hy, hz = ctx.hand
    r = ctx.size[0] * 0.46
    c = (hx, hy - 0.6, hz - r - 0.4)
    g.blob(c, r, 'iron', 0.42, top=0.2)
    g.ring(c, r * 1.01, 0.3, axis='z', mat='iron', val=0.6)
    g.rivets([vadd(c, (r * math.cos(a), r * math.sin(a), 0)) for a in (0.4, 1.4, 2.4, 3.4, 4.4, 5.4)], 'iron', 0.75)
    top = vadd(c, (0, r * 0.95, 0))
    g.cylinder(top, vadd(top, (0, 0.8, 0)), 0.8, 0.7, 'brass', 0.55)
    fuse = [vadd(top, (0, 0.8, 0)), vadd(top, (0.5, 1.8, -0.3)), vadd(top, (0.2, 2.6, -1.0))]
    g.sweep(fuse, 0.3, 0.25, 'cloth', 0.55)
    g.blob(fuse[-1], 0.5, 'glow', 0.85, glow=True, prio=6)
    g.dot(vadd(fuse[-1], (0.4, 0.5, 0)), 'glow', 0.95, glow=True, prio=6)
    g.streaks('rust', ['iron'], density=0.25, length=(0.8, 2.2), val=0.42)


# ── 5층 용인 대장장이 forge_dragonkin ── 덩치 큰 대장장이: 가죽 앞치마, 그을린 토시, 목덜미 비늘 사이 불빛, 모루 쇠머리 망치

FORGE_RAMPS = {
    'skin': [(20, 8, 6), (40, 14, 10), (64, 24, 16), (94, 36, 24), (126, 54, 34), (160, 80, 50), (196, 114, 74)],
    'skin2': [(54, 24, 14), (96, 46, 26), (140, 74, 42), (180, 108, 64), (214, 146, 96), (238, 188, 140)],
    'eye': [(130, 50, 6), (220, 110, 16), (255, 170, 50), (255, 222, 120), (255, 248, 210), (255, 255, 255)],
    'leather': [(18, 10, 6), (36, 20, 12), (58, 34, 20), (84, 52, 30), (112, 72, 44), (144, 98, 62)],
    'iron': [(10, 10, 12), (24, 24, 28), (42, 42, 46), (66, 66, 70), (96, 96, 98), (132, 130, 128), (176, 172, 166)],
    'horn': [(14, 10, 8), (30, 24, 20), (54, 44, 36), (84, 70, 58), (122, 104, 86), (166, 146, 124)],
    'brass': [(44, 24, 8), (90, 56, 18), (144, 98, 36), (196, 146, 64), (232, 192, 108), (250, 230, 170)],
    'lava': [(90, 20, 6), (170, 44, 10), (232, 96, 18), (255, 160, 40), (255, 214, 110), (255, 248, 210)],
}


def _forge_fx(g, ctx, part):
    w, h, d = ctx.size
    if part == 'torso':
        g.cracks(['skin'], 'lava', width=0.018, scale=3.6, val=0.55, glow=True)                    # 녹은 균열
        for k in range(4):                                                                         # 목덜미 불빛
            g.dot((-1.2 + 0.8 * k, h * 0.42, d * 0.42), 'lava', 0.7, glow=True, prio=5)
        for s in (-1, 1):
            _dk_strap(g, (s * w * 0.3, h * 0.48, -d * 0.3), (s * w * 0.42, h * 0.1, d * 0.45),
                      (s * w * 0.2, -h * 0.28, d * 0.56), r=0.55)
        g.rbox((-w * 0.47, -h * 0.5, -d * 0.58), (w * 0.47, -h * 0.34, d * 0.58), 'leather', 0.32, bevel=0.5)
        g.rbox((-w * 0.1, -h * 0.5, -d * 0.62), (w * 0.1, -h * 0.34, -d * 0.55), 'brass', 0.6)
    elif part == 'head':
        g.spikes([(0, h * 0.52, d * 0.05 + k * 1.4) for k in range(3)], (0, 1, 0.6), 1.3, 0.5, 'horn', 0.4)
        for s in (-1, 1):
            g.dot((s * w * 0.3, -h * 0.05, d * 0.3), 'lava', 0.6, glow=True, prio=5)            # 볼 비늘 틈 불빛
    elif part == 'arm':
        g.capsule((0, -h * 0.55, 0.25), (0, -h * 0.86, -0.2), w * 0.44, w * 0.42, 'leather', 0.36)  # 토시
        g.ring((0, -h * 0.6, 0.2), w * 0.45, 0.4, axis='y', mat='iron', val=0.5)
        g.blob((0, -0.2, 0.1), (w * 0.62, w * 0.42, w * 0.6), 'leather', 0.45, prio=2,
               cut=lambda x, y, z: y < -0.8)
        _soot(g, ['leather'], 0.35, 1.4, seed=1)
        g.cracks(['skin'], 'lava', width=0.02, scale=2.6, val=0.5, glow=True, seed=5)
    elif part == 'legs':
        g.rbox((-w * 0.47, -4.2, -d * 0.55), (w * 0.47, 0.6, d * 0.55), 'leather', 0.4, bevel=0.7)  # 가죽 바지
        for s in (-1, 1):
            g.rbox((s * w * 0.27 - 1.5, -h * 0.82, -1.2), (s * w * 0.27 + 1.5, -h * 0.66, 2.2), 'iron', 0.42,
                   bevel=0.4)                                                                      # 발목 쇠고리
    elif part == 'tail':
        g.cracks(['skin'], 'lava', width=0.02, scale=2.6, val=0.5, glow=True, seed=7)


def _forge_horns(g, ctx):
    A = _At(ctx)
    hw, hh, hd = _size(ctx, 'head', (8, 8, 11))
    for s in (-1, 1):
        b = A(s * hw * 0.3, hh * 0.36, hd * 0.12)
        g.horn(b, (s * 0.7, 0.35, 0.8), 5.6, 1.15, curl=(s * 0.2, 1.4, 1.2), mat='horn', val=0.38, rings=0.9)
        g.blob(b, 1.3, 'horn', 0.32)


def _forge_apron(g, ctx):
    T = _At(ctx, 'torso')
    tw, th, td = _size(ctx, 'torso', (12, 13, 7))
    w, h, d = ctx.size
    z = T(0, 0, -td * 0.5)[2] - 0.5
    top = T(0, th * 0.3, 0)[1]
    L = top - (-h * 0.62)
    g.cloth([(-w * 0.4, top, z + 0.2), (-w * 0.2, top, z - 0.1), (w * 0.2, top, z - 0.1), (w * 0.4, top, z + 0.2)],
            lambda u: L * (1.0 + 0.08 * abs(u - 0.5)), 'leather', 0.5, tatter=0.15, holes=0.0, thick=2,
            folds=0.1, sway=(0.0, -0.06))
    for s in (-1, 1):
        g.sweep([(s * w * 0.36, top, z + 0.4), T(s * tw * 0.22, th * 0.48, -td * 0.2), T(s * tw * 0.06, th * 0.5, 0)],
                0.4, 0.4, 'leather', 0.36)
        g.dot((s * w * 0.36, top - 0.4, z - 0.4), 'brass', 0.7, prio=5)
    g.rbox((-w * 0.24, top - L * 0.48, z - 0.7), (w * 0.24, top - L * 0.3, z - 0.2), 'leather', 0.38, bevel=0.3)
    g.paint(lambda x, y, z_, n, m, v: ('lava', 0.4, True) if (h3(int(x * 2), int(y * 2), 7, g.seed) < 0.025 and
                                                              n[2] < 0) else None, ['leather'])  # 튄 불똥 자국


def _forge_hammer(g, ctx):
    hx, hy, hz = ctx.hand
    zh = hz - 14.5
    g.capsule((hx, hy, hz + 3.0), (hx, hy, zh + 1.5), 0.75, 0.7, 'bark', 0.45)
    g.capsule((hx, hy, hz + 1.8), (hx, hy, hz - 1.8), 0.9, 0.9, 'leather', 0.4)
    for z in (hz - 5.0, zh + 2.2):
        g.ring((hx, hy, z), 0.85, 0.35, axis='z', mat='iron', val=0.55)
    # 모루 쇠머리: 세로로 긴 쇳덩이, 위 = 뿔(원뿔), 아래 = 내려찍는 면(달아오름)
    g.rbox((hx - 2.4, hy - 5.0, zh - 2.4), (hx + 2.4, hy + 2.4, zh + 2.0), 'iron', 0.45, bevel=0.6, top=0.15)
    g.rbox((hx - 2.8, hy - 6.2, zh - 2.8), (hx + 2.8, hy - 4.6, zh + 2.4), 'iron', 0.5, bevel=0.4)
    g.cone((hx, hy + 2.2, zh - 0.2), (0, 1, 0.15), 3.2, 1.7, 'iron', 0.42, 0.7)
    g.rbox((hx - 2.6, hy - 6.4, zh - 2.6), (hx + 2.6, hy - 6.0, zh + 2.2), 'lava', 0.6, glow=True, prio=4)
    g.rbox((hx - 2.5, hy - 1.2, zh - 2.5), (hx + 2.5, hy - 0.4, zh + 2.1), 'brass', 0.55, prio=3)


# ── 7층 수정 용인 창기사 crystal_dragonkin ── 자수정 비늘 판갑, 수정 다발 볏, 육각 수정 방패, 수정 촉 긴 창, 꼬리 끝 수정

CRYSTAL_RAMPS = {
    'skin': [(18, 12, 30), (34, 22, 56), (54, 36, 88), (80, 56, 124), (110, 82, 160), (146, 116, 196), (190, 164, 230)],
    'skin2': [(40, 30, 64), (74, 58, 110), (112, 92, 156), (152, 132, 198), (194, 178, 232), (230, 222, 252)],
    'iron': [(18, 12, 30), (38, 28, 62), (64, 50, 100), (96, 80, 138), (132, 116, 176), (172, 160, 210), (214, 206, 240)],
    'crystal': [(60, 30, 110), (110, 64, 180), (160, 110, 230), (200, 160, 255), (232, 212, 255), (250, 244, 255)],
    'eye': [(90, 60, 160), (150, 110, 230), (200, 170, 255), (236, 220, 255), (250, 246, 255), (255, 255, 255)],
    'glow': [(120, 60, 200), (180, 120, 255), (220, 180, 255), (244, 226, 255), (255, 250, 255), (255, 255, 255)],
    'horn': [(30, 22, 44), (60, 46, 84), (100, 80, 130), (146, 124, 176), (196, 180, 222)],
}


def _crystal_fx(g, ctx, part):
    w, h, d = ctx.size
    if part == 'torso':
        g.plate((-w * 0.44, -h * 0.1, -d * 0.62), (w * 0.44, h * 0.42, -d * 0.2), 'iron', 0.5, rivet_mat='iron',
                rivet_step=2.2, bevel=0.8)                                                         # 흉갑
        g.plates((0, -h * 0.3, -d * 0.3), (w * 0.4, h * 0.2, d * 0.3), n=3, axis=1, mat='iron', val=0.45,
                 lift=0.08, cut=lambda x, y, z: z > -d * 0.05)                                   # 배 판
        _gem(g, (0, h * 0.18, -d * 0.66), 1.0, 'glow', 'iron')
        g.crystals((-w * 0.45, h * 0.45, 0.4), (-0.6, 1, 0.3), n=3, size=2.4, r=0.6, mat='crystal', seed=1)
        g.crystals((w * 0.2, h * 0.3, d * 0.5), (0.2, 0.7, 1), n=2, size=1.8, r=0.5, mat='crystal', seed=2)
    elif part == 'head':
        g.rbox((-w * 0.36, h * 0.2, -d * 0.1), (w * 0.36, h * 0.5, d * 0.36), 'iron', 0.5, bevel=0.8, prio=2)
        g.paint(lambda x, y, z, n, m, v: ('crystal', 0.7, True) if (h3(int(x * 3), int(y * 3), int(z * 3), 7) < 0.04)
                else None, ['skin'])                                                              # 비늘 반짝임
    elif part == 'arm':
        g.blob((0, -0.1, 0), (w * 0.72, w * 0.55, w * 0.72), 'iron', 0.52, prio=2,
               cut=lambda x, y, z: y < -1.4)                                                      # 어깨 판
        g.rbox((-w * 0.48, -h * 0.84, -w * 0.48), (w * 0.48, -h * 0.56, w * 0.48), 'iron', 0.46, bevel=0.6)
        g.crystals((ctx.out * w * 0.5, 0.6, 0), (ctx.out * 0.7, 1, 0), n=2, size=2.2, r=0.55, mat='crystal',
                   seed=3)
    elif part == 'legs':
        for s in (-1, 1):
            x = s * w * 0.27
            g.plate((x - 1.6, -h * 0.48, -2.9), (x + 1.6, -h * 0.34, -1.6), 'iron', 0.5, rivets=False, bevel=0.5)
            g.rbox((x - 1.3, -h * 0.75, 0.1), (x + 1.3, -h * 0.52, 1.6), 'iron', 0.45, bevel=0.4)
        g.rbox((-w * 0.5, -3.6, -d * 0.6), (w * 0.5, 0.6, d * 0.6), 'iron', 0.45, bevel=0.8)       # 허리 판
    elif part == 'tail' and ctx.name == 'tail_2':
        g.crystals((0, -ctx.size[1] * 0.7, d - 0.4), (0, 0.4, 1), n=3, size=3.0, r=0.8, mat='crystal', seed=4)


def _crystal_crest(g, ctx):
    A = _At(ctx)
    hw, hh, hd = _size(ctx, 'head', (7, 8, 10))
    g.crystals(A(0, hh * 0.48, hd * 0.1), (0, 1, 0.55), n=4, size=4.4, r=1.0, mat='crystal', seed=5, spread=0.5)
    for s in (-1, 1):
        g.crystals(A(s * hw * 0.32, hh * 0.38, hd * 0.2), (s * 0.5, 0.6, 1), n=2, size=3.2, r=0.7, mat='crystal',
                   seed=6 + s)
    g.blob(A(0, hh * 0.44, hd * 0.12), (hw * 0.3, 0.9, hd * 0.2), 'iron', 0.5)


def _crystal_shield(g, ctx):
    hx, hy, hz = ctx.hand
    o = ctx.out
    aw = _size(ctx, 'arm_left', (4, 13, 4))[0]
    W, H, _ = ctx.size
    cx, cy = hx + o * (aw * 0.5 + 1.1), hy + 3.0
    hz_, hy_ = W * 0.5, H * 0.5

    def mask(u, v):
        return abs(u) <= hz_ and abs(v) + abs(u) * (hy_ * 0.5 / hz_) <= hy_

    def vfn(u, v, w_, e):
        if e < 0.9:
            return ('iron', 0.55 + 0.1 * (v / hy_))
        sector = int((math.atan2(v, u) + math.pi) / (math.pi / 3)) % 6
        return ('crystal', 0.38 + 0.1 * sector + (0.12 if w_ * o > 0 else 0))
    g.slab2d(lambda u, v: mask(u - hz, v - cy), (hz - hz_, cy - hy_), (hz + hz_, cy + hy_), plane='zy', depth=cx,
             half=0.6, mat='crystal', vfn=vfn, bevel=1.4)
    g.crystals((cx + o * 0.6, cy, hz), (o, 0, 0), n=3, size=2.6, r=0.9, mat='glow', glow=True, seed=8, spread=0.4)
    for a in range(6):
        ang = a * math.pi / 3 + math.pi / 6
        p = (cx + o * 0.7, cy + math.sin(ang) * hy_ * 0.62, hz + math.cos(ang) * hz_ * 0.62)
        g.dot(p, 'glow', 0.75, glow=True, prio=5)


def _crystal_lance(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    zt = hz - L * 0.82
    g.capsule((hx, hy, hz + 5.5), (hx, hy, hz), 0.75, 0.75, 'leather', 0.4)
    g.blob((hx, hy, hz + 5.8), 0.95, 'iron', 0.55)
    g.cone((hx, hy, hz + 0.4), (0, 0, -1), 4.5, 2.4, 'iron', 0.45, 0.6, r_tip=0.8)                # 손 가리개
    g.capsule((hx, hy, hz - 3.5), (hx, hy, zt + 0.5), 0.8, 0.6, 'iron', 0.55,
              vfn=lambda t, dd, p: 0.45 + 0.2 * (1 - dd) + (0.15 if int(t * 12) % 3 == 0 else 0))
    g.crystal(g.to_vox((hx, hy, zt + 1.0)), (0, 0, -1), 6.0 / g.vs, 1.3 / g.vs, 'crystal', prio=4)
    g.ring((hx, hy, zt + 1.2), 1.0, 0.35, axis='z', mat='iron', val=0.65)
    g.dot((hx, hy, zt - 3.8), 'glow', 0.9, glow=True, prio=6)


# ── 10층 심연 용인 기사 abyss_dragonkin ── 심연 판갑 + 청록 스컬크 맥, 투구형 머리와 뿔, 등의 접힌 날개, 해진 망토, 룬 대검

ABYSS_RAMPS = {
    'skin': [(4, 4, 10), (10, 12, 24), (20, 24, 42), (32, 40, 62), (48, 60, 84), (70, 86, 110)],
    'skin2': [(12, 14, 26), (24, 30, 48), (40, 50, 72), (60, 74, 98), (86, 102, 126)],
    'iron': [(6, 6, 10), (14, 16, 24), (26, 30, 42), (42, 48, 64), (62, 72, 90), (90, 104, 122), (130, 146, 162)],
    'glow': [(10, 70, 70), (20, 140, 130), (47, 224, 208), (140, 248, 236), (220, 255, 250), (255, 255, 255)],
    'eye': [(10, 70, 70), (20, 140, 130), (47, 224, 208), (140, 248, 236), (220, 255, 250), (255, 255, 255)],
    'rune': [(10, 70, 70), (20, 140, 130), (47, 224, 208), (140, 248, 236), (220, 255, 250), (255, 255, 255)],
    'cloth': [(6, 6, 12), (12, 14, 24), (20, 24, 40), (30, 36, 56), (44, 52, 74)],
    'membrane': [(6, 10, 16), (12, 20, 30), (20, 34, 46), (30, 50, 62), (44, 70, 82)],
    'horn': [(8, 8, 12), (20, 20, 28), (36, 38, 50), (58, 62, 78), (88, 94, 112), (130, 138, 156)],
    'bone': [(14, 16, 24), (30, 34, 46), (50, 56, 72), (76, 84, 102), (108, 118, 136)],
    'blade': [(20, 24, 34), (40, 48, 64), (70, 82, 100), (110, 124, 142), (160, 172, 186), (210, 220, 230)],
}


def _sculk(g, mats, seed=0, width=0.016, scale=3.2):
    g.cracks(mats, 'glow', width=width, scale=scale, val=0.55, glow=True, seed=seed)


def _abyss_fx(g, ctx, part):
    w, h, d = ctx.size
    if part == 'torso':
        g.plate((-w * 0.46, -h * 0.06, -d * 0.62), (w * 0.46, h * 0.44, d * 0.6), 'iron', 0.45, rivets=False,
                bevel=1.0)                                                                        # 흉갑 (앞뒤)
        g.rbox((-w * 0.06, -h * 0.02, -d * 0.66), (w * 0.06, h * 0.4, -d * 0.6), 'glow', 0.6, glow=True, prio=4)
        g.cylinder((0, h * 0.42, 0.3), (0, h * 0.54, 0.3), w * 0.28, w * 0.24, 'iron', 0.5)        # 목가리개
        _sculk(g, ['iron'], 1, 0.012)
    elif part == 'head':
        # 투구: 정수리·콧등을 덮는 판, 눈구멍 틈만 열림, 이마 가운데 볏
        g.blob((0, h * 0.2, d * 0.1), (w * 0.52, h * 0.38, d * 0.38), 'iron', 0.5, prio=2,
               cut=lambda x, y, z: y < h * 0.02 and z < d * 0.25)
        g.rbox((-w * 0.3, h * 0.05, -d * 0.62), (w * 0.3, h * 0.36, -d * 0.1), 'iron', 0.55, bevel=0.6, prio=2)
        g.capsule((0, h * 0.58, -d * 0.4), (0, h * 0.55, d * 0.4), 0.6, 0.5, 'iron', 0.65, prio=3)
        for s in (-1, 1):
            g.cone((s * w * 0.4, -h * 0.25, d * 0.15), (s * 0.5, -0.4, 1), 2.0, 0.6, 'horn', 0.4, 0.75)  # 턱 가시
    elif part == 'arm':
        g.blob((0, 0.0, 0), (w * 0.72, w * 0.58, w * 0.72), 'iron', 0.48, prio=2, cut=lambda x, y, z: y < -1.6)
        g.cone((ctx.out * w * 0.45, 1.2, 0.3), (ctx.out * 0.5, 1, 0.3), 2.4, 0.8, 'horn', 0.4, 0.75)
        g.rbox((-w * 0.5, -h * 0.88, -w * 0.5), (w * 0.5, -h * 0.55, w * 0.5), 'iron', 0.45, bevel=0.7)
        _sculk(g, ['iron'], 3)
    elif part == 'legs':
        g.rbox((-w * 0.5, -4.2, -d * 0.62), (w * 0.5, 0.6, d * 0.62), 'iron', 0.42, bevel=0.9)     # 허리 판
        for s in (-1, 1):
            x = s * w * 0.27
            g.plate((x - 1.7, -h * 0.5, -3.0), (x + 1.7, -h * 0.34, -1.6), 'iron', 0.5, rivets=False, bevel=0.5)
            g.rbox((x - 1.4, -h * 0.76, 0.1), (x + 1.4, -h * 0.52, 1.8), 'iron', 0.45, bevel=0.4)
            g.dot((x, -h * 0.42, -3.1), 'glow', 0.7, glow=True, prio=5)


def _abyss_horns(g, ctx):
    A = _At(ctx)
    hw, hh, hd = _size(ctx, 'head', (8, 8, 11))
    for s in (-1, 1):
        b = A(s * hw * 0.34, hh * 0.42, hd * 0.05)
        g.horn(b, (s * 0.45, 0.5, 1), 6.6, 1.1, curl=(s * 0.6, 2.4, 0.6), mat='horn', val=0.38, rings=1.0,
               tip_mat='glow')
        g.horn(A(s * hw * 0.44, hh * 0.18, hd * 0.12), (s * 0.8, 0.1, 1), 3.0, 0.6, curl=(0, 0.6, 0.4),
               mat='horn', val=0.4)


def _abyss_cape(g, ctx):
    T = _At(ctx, 'torso')
    tw, th, td = _size(ctx, 'torso', (12, 14, 7))
    w, h, d = ctx.size
    y0 = T(0, th * 0.42, 0)[1]
    z0 = T(0, 0, td * 0.6)[2] + 0.8                                                               # 흉갑 등판 바깥
    top = [(-w * 0.5, y0, z0 - 1.6), (-w * 0.3, y0 + 0.2, z0), (w * 0.3, y0 + 0.2, z0), (w * 0.5, y0, z0 - 1.6)]
    g.cloth(top, lambda u: h + 1.0 - 2.0 * abs(u - 0.5), 'cloth', 0.5, tatter=0.5, holes=0.06, thick=1,
            normal=(0, 0, 1), sway=(0.0, 0.1))
    for s in (-1, 1):                                                                              # 어깨 고정쇠
        g.blob((s * w * 0.42, y0 + 0.3, z0 - 1.2), 1.1, 'iron', 0.55, prio=4)
        g.dot((s * w * 0.42, y0 + 0.3, z0 - 2.2), 'glow', 0.8, glow=True, prio=5)
    g.paint(lambda x, y, z, n, m, v: ('glow', 0.45, True) if y < y0 - h * 0.8 and h2(int(x * 2), 3, 9) < 0.3
            else None, ['cloth'])                                                                  # 해진 끝단 빛


def _abyss_wing(g, ctx):
    _xz_wing(g, ctx, bone='iron', mem='membrane', val=0.5, vein='glow', claw='horn', fingers=3, tatter=0.6)


def _abyss_sword(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    zt = hz - L * 0.86
    _gem(g, (hx, hy, hz + 3.6), 0.6, 'glow', 'iron')
    g.capsule((hx, hy, hz + 3.0), (hx, hy, hz - 0.6), 0.6, 0.6, 'leather', 0.35)
    g.rbox((hx - 0.9, hy - 3.2, hz - 1.6), (hx + 0.9, hy + 3.2, hz - 0.7), 'iron', 0.5, bevel=0.4)    # 십자 날밑
    for s in (-1, 1):
        g.cone((hx, hy + s * 3.0, hz - 1.1), (0, s, -0.6), 1.6, 0.6, 'iron', 0.5, 0.7)

    def blade(x, y, z):
        t = (hz - 1.6 - z) / (hz - 1.6 - zt)
        hw = 1.5 * (1 - max(0.0, t - 0.8) / 0.2 * 0.95)
        if abs(y - hy) > hw:
            return None
        if abs(y - hy) < 0.3 and 0.05 < t < 0.85:
            return ('rune', 0.6, True)
        return ('blade', 0.5 + 0.35 * abs(y - hy) / max(0.3, hw))
    g.rbox((hx - 0.4, hy - 1.6, zt), (hx + 0.4, hy + 1.6, hz - 1.6), 'blade', 0.5, vfn=blade)


# ── 용인족 조립 ──
_DK = {
    'thorn_kobold': (KOBOLD_RAMPS, _kobold_fx, {'horns': _kobold_horns, 'spear': _kobold_spear}),
    'kobold_sapper': (SAPPER_RAMPS, _sapper_fx, {'goggles': _sapper_goggles, 'satchel': _sapper_satchel,
                                                 'bomb': _sapper_bomb}),
    'forge_dragonkin': (FORGE_RAMPS, _forge_fx, {'horns': _forge_horns, 'apron': _forge_apron,
                                                 'hammer': _forge_hammer}),
    'crystal_dragonkin': (CRYSTAL_RAMPS, _crystal_fx, {'crest': _crystal_crest, 'shield': _crystal_shield,
                                                       'lance': _crystal_lance}),
    'abyss_dragonkin': (ABYSS_RAMPS, _abyss_fx, {'horns': _abyss_horns, 'cape': _abyss_cape,
                                                 'wing_left': _abyss_wing, 'wing_right': _abyss_wing,
                                                 'greatsword': _abyss_sword}),
}
_DK_BASE = {'torso': (_dk_torso, 'torso'), 'head': (_dk_head, 'head'), 'jaw': (_dk_jaw, None),
            'arm_left': (_dk_arm, 'arm'), 'arm_right': (_dk_arm, 'arm'), 'legs': (_dk_legs, 'legs'),
            'tail': (_dk_tail, 'tail'), 'tail_1': (_dk_tail, 'tail'), 'tail_2': (_dk_tail, 'tail')}
_DK_VS = {'torso': 0.75, 'legs': 0.65, 'cape': 0.65, 'apron': 0.65, 'wing_left': 0.6, 'wing_right': 0.6,
          'lance': 0.55, 'greatsword': 0.5, 'hammer': 0.6, 'shield': 0.6, 'head': 0.55, 'arm_left': 0.6,
          'arm_right': 0.6, 'tail_1': 0.6}


def dragonkin(look, name, part, ctx):
    ramps, fx, extra = _DK[ctx.mid]
    _ramps(ctx, ramps)
    g = _grid(ctx, _DK_VS.get(name, 0.5) if max(ctx.size) > 9 else 0.5)
    if name in extra:
        extra[name](g, ctx)
        return g
    base = _DK_BASE.get(name)
    if base is None:
        return None
    base[0](g, ctx)
    if base[1]:
        fx(g, ctx, base[1])
    return g


# ═════════════════════════════════ 켄타우로스 (centaur) 공통 ═════════════════════════════════
# horse_body = 말 몸통(앞 가슴이 사람 허리로 솟음) · legs(leg_quad) = pivot 중심, 땅 = y −h/2 · torso·head·팔 = 사람형.

def _ct_horse(g, ctx):
    w, h, d = ctx.size
    T = _At(ctx, 'torso')
    g.blob((0, 0.3, -d * 0.3), (w * 0.46, h * 0.48, d * 0.24), 'skin', 0.5)                         # 가슴
    g.capsule((0, 0.2, -d * 0.24), (0, 0.5, d * 0.26), h * 0.46, h * 0.48, 'skin', 0.48, sq=(w / h, 1.0, 1.0))
    g.blob((0, 0.7, d * 0.32), (w * 0.48, h * 0.5, d * 0.2), 'skin', 0.5)                          # 엉덩이
    tb = _size(ctx, 'torso', (9, 11, 5))
    g.capsule((0, h * 0.3, -d * 0.36), T(0, -tb[1] * 0.3, 0.2), w * 0.36, tb[0] * 0.36, 'skin', 0.5,
              sq=(1.0, 1.0, 0.85))                                                                 # 허리 이음
    g.gradient(1, -h * 0.5, h * 0.5, 0.12)
    g.mottle(['skin'], 0.08, 3.0)


def _ct_legs(g, ctx, hoof='horn'):
    w, h, d = ctx.size
    y0 = -h * 0.5
    for s in (-1, 1):
        x = s * w * 0.32
        for front in (True, False):
            z = -d * 0.38 if front else d * 0.38
            if front:
                j = [(x, h * 0.42, z), (x, h * 0.0, z - 0.3), (x, y0 + 2.4, z - 0.1)]
                rr = [w * 0.15, w * 0.11, w * 0.085]
            else:
                j = [(x, h * 0.42, z - 0.4), (x, h * 0.02, z + 1.6), (x, y0 + 2.4, z + 0.6)]
                rr = [w * 0.18, w * 0.11, w * 0.085]
            g.limb(j, rr, 'skin', 0.48, knob=1.18)
            g.blob((x, y0 + 2.0, j[2][2] - 0.1), w * 0.11, 'skin2', 0.55)                         # 발목 털
            g.rbox((x - w * 0.1, y0, j[2][2] - w * 0.12 - 0.2), (x + w * 0.1, y0 + 1.3, j[2][2] + w * 0.1),
                   hoof, 0.42, bevel=0.35)                                                         # 발굽
    g.gradient(1, -h * 0.5, h * 0.5, 0.1)


def _ct_torso(g, ctx):
    w, h, d = ctx.size
    g.blob((0, h * 0.18, 0), (w * 0.5, h * 0.34, d * 0.52), 'skin', 0.5, top=0.12)
    g.capsule((0, h * 0.05, 0.1), (0, -h * 0.48, 0.1), w * 0.36, w * 0.4, 'skin', 0.47,
              sq=(1.0, 1.0, min(1.0, d / w * 1.2)))
    for s in (-1, 1):
        g.blob((s * w * 0.46, h * 0.36, 0), (w * 0.2, h * 0.16, d * 0.42), 'skin', 0.55)
    H = ctx.offset_to('head')
    hh = _size(ctx, 'head', (6, 6, 6))[1]
    g.capsule((0, h * 0.4, 0.2), (H[0], H[1] - hh * 0.3, H[2] + 0.4), w * 0.17, w * 0.15, 'skin', 0.5)
    g.mottle(['skin'], 0.08, 2.6)


def _ct_arm(g, ctx):
    w, h, d = ctx.size
    g.blob((0, -0.5, 0), (w * 0.56, w * 0.52, w * 0.56), 'skin', 0.52)
    g.capsule((0, -0.6, 0), (0, -h * 0.48, 0.2), w * 0.4, w * 0.35, 'skin', 0.5)
    g.blob((0, -h * 0.49, 0.2), w * 0.36, 'skin', 0.56)
    g.capsule((0, -h * 0.5, 0.2), (0, -h * 0.86, -0.2), w * 0.35, w * 0.3, 'skin', 0.47)
    g.blob((0, -h + 1.0, -0.3), (w * 0.38, w * 0.42, w * 0.42), 'skin', 0.5)


# ── 3층 균사 켄타우로스 myconid_centaur ── 버섯살 말 몸통 + 사람 상반신, 눈 없는 균사 머리 위 큰 붉은 갓(흰 점), 균사망, 버섯 낫

MYCO_RAMPS = {
    'skin': [(35, 24, 20), (62, 46, 34), (98, 76, 56), (140, 112, 84), (182, 154, 120), (216, 196, 160), (238, 226, 200)],
    'skin2': [(80, 70, 58), (130, 118, 100), (176, 166, 146), (212, 204, 186), (236, 232, 220)],
    'cap': [(60, 10, 10), (110, 20, 18), (170, 40, 32), (224, 68, 58), (244, 118, 100), (252, 170, 150)],
    'gill': [(70, 52, 40), (120, 96, 76), (170, 146, 120), (210, 192, 166), (236, 224, 204)],
    'web': [(110, 104, 96), (160, 154, 144), (200, 196, 186), (230, 228, 220), (250, 250, 246)],
    'lichen': [(180, 170, 160), (220, 214, 204), (244, 240, 232), (255, 252, 246)],
    'eye': [(80, 60, 20), (150, 120, 40), (210, 180, 80), (240, 220, 140), (255, 246, 210), (255, 255, 255)],
    'glow': [(110, 30, 20), (200, 70, 50), (240, 120, 90), (255, 180, 150), (255, 230, 214), (255, 255, 255)],
    'horn': [(26, 20, 16), (48, 38, 30), (76, 62, 48), (108, 90, 70), (144, 124, 98)],
    'bark': [(60, 48, 36), (100, 84, 64), (140, 122, 96), (180, 162, 132), (214, 200, 172)],
}


def _hyphae(g, mats, n, seed=0, region=None):
    """균사망: 표면 두 점 사이의 가는 흰 실(표면 위로 살짝 뜸)."""
    surf = [(g.px(k), nn) for k, nn in g.exposed(mats) if (region is None or region(*g.px(k)))]
    if len(surf) < 4:
        return
    sd = g.seed + 601 + seed
    surf.sort(key=lambda q: h3(int(q[0][0] * 4), int(q[0][1] * 4), int(q[0][2] * 4), sd))
    for k in range(n):
        a, na = surf[k]
        best = None
        for b, nb in surf[n:n + 40]:
            dd = vlen(vsub(a, b))
            if 2.0 < dd < 5.0 and (best is None or dd < best[0]):
                best = (dd, b)
        if best:
            g.strands(a, best[1], sag=0.5, mat='web', val=0.75, prio=3)


def _myco_horse(g, ctx):
    _ct_horse(g, ctx)
    w, h, d = ctx.size
    g.paint(lambda x, y, z, n, m, v: ('skin2', 0.5) if y < -h * 0.25 else None, ['skin'])
    for c, r, up in (((1.8, h * 0.5, -1.0), 1.3, (0.2, 1, 0)), ((-2.2, h * 0.46, 3.2), 1.0, (-0.3, 1, 0.2)),
                     ((0.6, h * 0.55, 5.8), 1.5, (0, 1, 0.3)), ((-0.4, h * 0.42, -5.6), 0.8, (0, 1, -0.2))):
        g.mushroom(c, up, 1.1, r, mat='cap', val=0.5, spots=0.3)
    for s in (-1, 1):                                                                              # 옆구리 선반 버섯
        for z, y in ((-1.0, 0.6), (3.4, -0.4)):
            g.blob((s * w * 0.5, y, z), (1.0, 0.45, 1.6), 'gill', 0.6, prio=3,
                   cut=lambda x_, y_, z_, s=s: x_ * s < w * 0.42)
    _hyphae(g, ['skin', 'skin2'], 4)


def _myco_legs(g, ctx):
    _ct_legs(g, ctx, hoof='horn')
    w, h, d = ctx.size
    g.paint(lambda x, y, z, n, m, v: ('web', 0.6) if (y < -h * 0.2 and m == 'skin2') else None, ['skin2'])
    _hyphae(g, ['skin'], 2, region=lambda x, y, z: y < 0)


def _myco_torso(g, ctx):
    _ct_torso(g, ctx)
    w, h, d = ctx.size
    g.paint(lambda x, y, z, n, m, v: ('skin2', 0.55) if (n[2] < 0 and abs(x) < w * 0.25 and y < h * 0.2) else None,
            ['skin'])
    for s in (-1, 1):                                                                              # 어깨 선반 버섯
        g.blob((s * w * 0.52, h * 0.44, 0), (w * 0.24, 0.6, d * 0.5), 'cap', 0.5, prio=3)
        g.blob((s * w * 0.52, h * 0.4, 0), (w * 0.22, 0.4, d * 0.46), 'gill', 0.5, prio=2)
    g.mushroom((-w * 0.2, h * 0.1, -d * 0.48), (-0.3, 0.6, -1), 0.6, 0.9, mat='cap', val=0.5, spots=0.0)
    g.sweep([(-w * 0.45, -h * 0.4, -d * 0.55), (0, -h * 0.47, -d * 0.62), (w * 0.45, -h * 0.4, -d * 0.55)],
            0.5, 0.5, 'bark', 0.4)                                                                 # 덩굴 띠
    _hyphae(g, ['skin', 'skin2'], 3, seed=2)


def _myco_head(g, ctx):
    w, h, d = ctx.size
    g.blob((0, -0.2, 0), (w * 0.56, h * 0.56, d * 0.54), 'skin2', 0.5, lump=0.22, lump_scale=1.6)  # 균사 덩어리
    g.paint(lambda x, y, z, n, m, v: ('web', 0.7) if fbm3(x / 2.0, y / 2.0, z / 2.0, 3) > 0.66 else None, ['skin2'])
    for s in (-1, 1):
        g.eye((s * w * 0.18, h * 0.05, -d * 0.42), 0.45, val=0.4, socket=0.25, facing=(s * 0.2, 0, -1))
    g.capsule((0, h * 0.3, 0), (0, h * 0.62, 0), w * 0.3, w * 0.26, 'gill', 0.65)                   # 갓 대


def _myco_cap(g, ctx):
    w, h, d = ctx.size
    g.blob((0, -h * 0.2, 0), (w * 0.5, h * 0.72, d * 0.5), 'cap', 0.5, lump=0.06,
           cut=lambda x, y, z: y < -h * 0.42,
           vfn=lambda x, y, z, dd: ('gill', 0.35 + 0.15 * (math.hypot(x, z) / (w * 0.5))) if y < -h * 0.3
           else 0.36 + 0.3 * (y + h * 0.42) / h)
    sd = g.seed + 7
    g.paint(lambda x, y, z, n, m, v: ('lichen', 0.7) if (n[1] > 0 and h3(int(x / 1.5), int(z / 1.5), 1, sd) < 0.18
                                                         and y > -h * 0.05) else None, ['cap'])
    g.paint(lambda x, y, z, n, m, v: ('glow', 0.4, True) if (n[1] < 0 and h3(int(x * 2), int(z * 2), 2, sd) < 0.08)
            else None, ['gill'])                                                                  # 주름 사이 포자빛
    g.capsule((0, -h * 0.4, 0), (0, -h * 0.9, 0), 1.4, 1.2, 'gill', 0.62)


def _myco_scythe(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    ze = hz - L * 0.72
    shaft = [(hx, hy, hz + 4.0), (hx, hy + 0.6, hz - 4.0), (hx, hy + 0.4, ze + 3.0), (hx, hy - 0.4, ze)]
    g.sweep(shaft, 0.65, 0.55, 'bark', 0.5, vfn=lambda t, dd, p: 0.42 + 0.18 * (1 - dd) + 0.08 * math.sin(t * 40))
    g.capsule((hx, hy, hz + 1.6), (hx, hy, hz - 1.6), 0.8, 0.8, 'gill', 0.4)
    blade = [(hx, hy - 0.2, ze - 0.4), (hx, hy - 3.0, ze - 0.8), (hx, hy - 6.0, ze + 0.8), (hx, hy - 8.2, ze + 3.8)]
    g.sweep(blade, 2.0, 0.3, 'cap', 0.5, sq=(0.4, 1.0, 1.0), rfn=lambda t: 0.4 + 2.0 * math.sin(math.pi * (0.2 + 0.8 * t)),
            vfn=lambda t, dd, p: ('gill', 0.55) if p[2] > ze + 0.3 + (p[1] - hy) * -0.45 + 1.2 else 0.45 + 0.25 * (1 - dd))
    g.paint(lambda x, y, z, n, m, v: ('lichen', 0.75) if h3(int(y * 1.2), int(z * 1.2), 3, g.seed) < 0.12 else None,
            ['cap'])
    g.mushroom((hx, hy + 0.8, ze + 0.6), (0, 1, 0.2), 0.8, 1.1, mat='cap', val=0.5, spots=0.3)


def _myco_tail(g, ctx):
    w, h, d = ctx.size
    for k, (x, y) in enumerate(((0, 0), (-0.8, -0.4), (0.8, -0.3), (0, -0.9))):
        g.sweep([(x * 0.5, y, -0.5), (x, y - 1.6, d * 0.45), (x * 1.3, y - 4.2 - 0.6 * k, d * 0.8),
                 (x * 1.4, y - 6.0 - 0.4 * k, d * 0.9)], 0.75, 0.3, 'web' if k % 2 else 'gill', 0.6)


# ── 7층 프리즘 켄타우로스 prism_centaur ── 하얀 수정 말 + 궁수 상반신, 갈기 대신 프리즘 결정, 무지개 하이라이트, 수정 활·화살통

PRISM_RAMPS = {
    'skin': [(40, 42, 70), (80, 84, 124), (130, 134, 180), (180, 186, 224), (220, 226, 250), (244, 248, 255),
             (255, 255, 255)],
    'skin2': [(58, 58, 106), (98, 98, 160), (140, 140, 208), (186, 188, 236), (226, 230, 252)],
    'crystal': [(70, 60, 140), (120, 110, 210), (170, 170, 245), (214, 226, 255), (240, 246, 255), (255, 255, 255)],
    'glow': [(120, 30, 100), (200, 60, 170), (255, 122, 224), (255, 180, 240), (255, 230, 250), (255, 255, 255)],
    'eye': [(120, 30, 100), (200, 60, 170), (255, 122, 224), (255, 180, 240), (255, 230, 250), (255, 255, 255)],
    'core': [(30, 90, 140), (60, 170, 220), (120, 230, 255), (190, 248, 255), (236, 255, 255), (255, 255, 255)],
    'iron': [(30, 30, 48), (56, 58, 84), (90, 94, 126), (132, 136, 170), (176, 180, 210), (220, 224, 244)],
    'leather': [(14, 14, 26), (28, 28, 48), (46, 46, 74), (68, 68, 104), (96, 96, 136)],
    'horn': [(50, 50, 90), (90, 92, 150), (140, 144, 200), (196, 200, 240), (236, 240, 255)],
    'feather': [(120, 40, 110), (190, 80, 170), (240, 140, 220), (255, 200, 240), (255, 236, 252)],
}


def _prism_glints(g, mats, amount=0.035, seed=0):
    """프리즘 반짝임: 표면 몇 칸을 분홍·하늘 발광으로."""
    sd = g.seed + 701 + seed
    g.paint(lambda x, y, z, n, m, v: (('glow' if h3(int(x * 2), int(y * 2), 5, sd) < 0.5 else 'core'), 0.6, True)
            if h3(int(x * 2), int(y * 2), int(z * 2), sd) < amount else None, mats)


def _facets(g, mats, scale=3.0, seed=0):
    """수정 면: 잡음 칸마다 밝기를 크게 달리해 깎은 면처럼."""
    sd = g.seed + 709 + seed
    g.paint(lambda x, y, z, n, m, v: v + 0.22 * (h3(int(x // scale), int(y // scale), int(z // scale), sd) - 0.5),
            mats)


def _prism_horse(g, ctx):
    _ct_horse(g, ctx)
    w, h, d = ctx.size
    for s in (-1, 1):                                                                              # 옆구리 분홍 결정
        g.crystals((s * w * 0.42, -0.6, -1.5 + s * 2.0), (s, 0.5, 0.2), n=3, size=2.0, r=0.6, mat='glow', glow=True,
                   seed=20 + s)
    for k in range(5):                                                                             # 등줄기 결정
        z = -d * 0.32 + k * d * 0.15
        g.crystals((0, h * 0.5 - 0.3 * abs(k - 2), z), (0, 1, 0.5), n=2, size=2.6 - 0.25 * k, r=0.7,
                   mat='crystal', seed=k)
    for s in (-1, 1):
        g.crystal(g.to_vox((s * w * 0.46, 0.2, 1.0)), (s, 0.4, 0.3), 2.2 / g.vs, 0.7 / g.vs, 'crystal', prio=3)
    _prism_glints(g, ['skin', 'crystal'], 0.05)


def _prism_legs(g, ctx):
    _ct_legs(g, ctx, hoof='crystal')
    w, h, d = ctx.size
    for s in (-1, 1):
        for z in (-d * 0.38, d * 0.38):
            g.crystal(g.to_vox((s * w * 0.32, 0.4, z - 0.8)), (s * 0.3, 0.3, -1), 1.5 / g.vs, 0.5 / g.vs,
                      'crystal', prio=3)
    _prism_glints(g, ['skin'], 0.03, 1)


def _prism_torso(g, ctx):
    _ct_torso(g, ctx)
    w, h, d = ctx.size
    g.plate((-w * 0.44, h * 0.0, -d * 0.6), (w * 0.44, h * 0.42, -d * 0.18), 'iron', 0.55, rivet_mat='crystal',
            rivet_step=2.0, bevel=0.8)                                                            # 은빛 흉갑
    _gem(g, (0, h * 0.2, -d * 0.64), 0.8, 'glow', 'iron')
    _dk_strap(g, (w * 0.42, h * 0.46, -0.4), (0, h * 0.0, -d * 0.66), (-w * 0.42, -h * 0.36, -d * 0.4), r=0.45,
              val=0.45)                                                                            # 화살통 끈
    for s in (-1, 1):
        g.crystals((s * w * 0.48, h * 0.44, 0), (s * 0.5, 1, 0), n=3, size=2.0, r=0.55, mat='crystal', seed=3 + s)
    _prism_glints(g, ['skin', 'iron'], 0.03, 2)


def _prism_head(g, ctx):
    w, h, d = ctx.size
    g.rbox((-w * 0.42, -h * 0.44, -d * 0.42), (w * 0.42, h * 0.4, d * 0.42), 'skin', 0.55, bevel=1.4, top=0.12)
    g.rbox((-w * 0.28, -h * 0.5, -d * 0.48), (w * 0.28, -h * 0.1, -d * 0.1), 'skin', 0.5, bevel=0.8)  # 턱
    g.rbox((-w * 0.45, -0.1, -d * 0.5), (w * 0.45, h * 0.32, -d * 0.2), 'crystal', 0.55, bevel=0.5, prio=2)  # 수정 가면
    for s in (-1, 1):
        g.eye((s * w * 0.2, h * 0.1, -d * 0.52), 0.55, val=0.6, socket=0.0, facing=(s * 0.2, 0, -1))
    g.dot((0, h * 0.0, -d * 0.52), 'crystal', 0.9, prio=5)
    _facets(g, ['crystal'], 2.0)


def _prism_crest(g, ctx):
    A = _At(ctx)
    hw, hh, hd = _size(ctx, 'head', (7, 7, 7))
    g.crystals(A(0, hh * 0.4, 0), (0, 1, 0.3), n=4, size=4.0, r=0.9, mat='crystal', seed=11, spread=0.45)
    for k in range(3):                                                                             # 뒤로 흐르는 갈기 결정
        g.crystal(g.to_vox(A(0, hh * 0.3 - k * 1.4, hd * 0.4 + k * 0.4)), (0, 0.4, 1), (2.6 - 0.4 * k) / g.vs,
                  0.6 / g.vs, 'crystal', prio=3)
    _prism_glints(g, ['crystal'], 0.06, 3)


def _prism_arm(g, ctx):
    _ct_arm(g, ctx)
    w, h, d = ctx.size
    g.rbox((-w * 0.5, -h * 0.84, -w * 0.5), (w * 0.5, -h * 0.58, w * 0.5), 'leather', 0.45, bevel=0.5)  # 활 팔찌
    g.ring((0, -h * 0.6, 0), w * 0.5, 0.3, axis='y', mat='iron', val=0.65)
    g.crystals((ctx.out * w * 0.4, 0.4, 0), (ctx.out * 0.6, 1, 0), n=2, size=1.8, r=0.5, mat='crystal', seed=7)


def _prism_bow(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    bul = ctx.size[2] * 0.42
    c = (hx, hy, hz - 1.2)
    g.capsule(vadd(c, (0, -1.6, 0)), vadd(c, (0, 1.6, 0)), 0.75, 0.75, 'leather', 0.45)             # 손잡이
    tips = []
    for s in (-1, 1):
        pts = [vadd(c, (0, s * 1.4, 0)), vadd(c, (0, s * L * 0.28, -bul * 0.15)), vadd(c, (0, s * L * 0.46, bul * 0.5)),
               vadd(c, (0, s * L * 0.5, bul))]
        g.sweep(pts, 0.95, 0.45, 'iron', 0.55, vfn=lambda t, dd, p: ('crystal', 0.6) if t > 0.6 else 0.5 + 0.2 * (1 - dd))
        g.crystal(g.to_vox(pts[-1]), (0, s, 0.4), 1.6 / g.vs, 0.5 / g.vs, 'glow', glow=True, prio=4)
        tips.append(pts[-1])
    g.sweep([tips[0], vadd(c, (0, 0, bul)), tips[1]], 0.25, 0.25, 'glow', 0.75, glow=True, smooth=False)  # 빛 시위


def _prism_quiver(g, ctx):
    w, h, d = ctx.size
    a, b = (-0.8, -h * 0.5, 0.3), (0.9, h * 0.42, 0.0)
    g.cylinder(a, b, w * 0.55, w * 0.6, 'leather', 0.45)
    for t in (0.12, 0.88):
        g.ring(vadd(a, vmul(vsub(b, a), t)), w * 0.62, 0.3, axis='y', mat='iron', val=0.6)
    for k, (dx, dz) in enumerate(((-0.6, 0.3), (0.5, -0.3), (0.2, 0.6))):                         # 화살 깃
        base = vadd(b, (dx, 0, dz))
        g.capsule(base, vadd(base, (0.3, 1.6, 0)), 0.25, 0.25, 'iron', 0.6)
        g.blob(vadd(base, (0.3, 2.4, 0)), (0.3, 1.0, 0.65), 'feather', 0.55 + 0.1 * k)


def _prism_tail(g, ctx):
    w, h, d = ctx.size
    for k in range(4):
        z = k * d * 0.24
        g.crystal(g.to_vox((0.4 * (k % 2) - 0.2, -k * 1.0, z)), (0, -0.5 - 0.2 * k, 1), (4.0 - 0.5 * k) / g.vs,
                  (1.0 - 0.15 * k) / g.vs, 'crystal', prio=3)
    _prism_glints(g, ['crystal'], 0.08, 4)


_CT = {
    'myconid_centaur': (MYCO_RAMPS, {'horse_body': _myco_horse, 'legs': _myco_legs, 'torso': _myco_torso,
                                     'head': _myco_head, 'cap': _myco_cap, 'arm_left': _ct_arm, 'arm_right': _ct_arm,
                                     'scythe': _myco_scythe, 'tail': _myco_tail}),
    'prism_centaur': (PRISM_RAMPS, {'horse_body': _prism_horse, 'legs': _prism_legs, 'torso': _prism_torso,
                                    'head': _prism_head, 'crest': _prism_crest, 'arm_left': _prism_arm,
                                    'arm_right': _prism_arm, 'bow': _prism_bow, 'quiver': _prism_quiver,
                                    'tail': _prism_tail}),
}
_CT_VS = {'horse_body': 0.85, 'legs': 0.7, 'torso': 0.65, 'cap': 0.65, 'scythe': 0.55, 'bow': 0.5, 'tail': 0.55,
          'head': 0.55, 'arm_left': 0.55, 'arm_right': 0.55}


def centaur(look, name, part, ctx):
    ramps, fns = _CT[ctx.mid]
    _ramps(ctx, ramps)
    fn = fns.get(name)
    if fn is None:
        return None
    g = _grid(ctx, _CT_VS.get(name, 0.5))
    fn(g, ctx)
    return g


# ═════════════════════════════════ 나가 (naga) 공통 ═════════════════════════════════
# coil = 바닥 똬리(고리) → waist 로 솟음 · tail_1·tail_2(segment)·tail_3(tail) = 바닥 따라 뒤로, 앞 끝 둥글게.
# 등 = 어두운 비늘 무늬(줄), 배 = 밝은 배판.  hood = 머리 뒤 얇은 코브라 후드(앞면에 무늬).

def _ng_scales(g, mats=('skin',), stripe=1.6, seed=0):
    sd = g.seed + 801 + seed
    g.paint(lambda x, y, z, n, m, v: v - 0.18 if (n[1] >= 0 and fbm3(x / 2.2, y / 2.2, z / 2.2, sd) > 0.62) else None,
            list(mats))                                                                            # 등 반점 무늬


def _ng_coil(g, ctx):
    w, h, d = ctx.size
    R, r = w * 0.3, h * 0.42
    g.ring((0, -h * 0.5 + r, 0.4), R, r, axis='y', mat='skin', val=0.48, arc=(0.0, 1.0))
    W = ctx.offset_to('waist')
    wr = _size(ctx, 'waist', (7, 9, 6))
    g.sweep([(-R * 0.6, -h * 0.5 + r, -R * 0.75), (-R * 0.2, -h * 0.5 + r * 1.6, -R * 0.4),
             (W[0], W[1] - wr[1] * 0.4, W[2])], r * 1.02, wr[0] * 0.46, 'skin', 0.5)                # 솟는 고리
    T1 = ctx.offset_to('tail_1')
    t1 = _size(ctx, 'tail_1', (8, 6, 9))
    g.sweep([(R * 0.5, -h * 0.5 + r, R * 0.6), (T1[0] * 0.5, T1[1], (T1[2] + R) * 0.5), (T1[0], T1[1], T1[2] + 0.6)],
            r, min(t1[0], t1[1]) * 0.5, 'skin', 0.48, sq=(1.0, 0.95, 1.0))
    g.paint(lambda x, y, z, n, m, v: ('skin2', 0.5) if (math.hypot(x, z - 0.4) < R * 0.92 and n[1] <= 0) else None,
            ['skin'])                                                                              # 안쪽 배판
    _ng_scales(g)


def _ng_waist(g, ctx):
    w, h, d = ctx.size
    T = ctx.offset_to('torso')
    tb = _size(ctx, 'torso', (9, 11, 5))
    g.sweep([(0, -h * 0.6, 0.3), (0, 0, 0), (T[0], T[1] - tb[1] * 0.38, T[2] + 0.2)], w * 0.46, w * 0.42, 'skin', 0.5,
            sq=(1.0, 1.0, d / w))
    g.rbox((-w * 0.3, -h * 0.62, -d * 0.52), (w * 0.3, h * 0.5, -d * 0.2), 'skin2', 0.55, bevel=0.8)  # 배판
    g.bands(['skin2'], axis=1, period=1.4, width=0.45, amount=-0.18)
    g.plates((0, h * 0.4, 0.1), (w * 0.56, 1.6, d * 0.56), n=2, axis=1, mat='skin', val=0.5, reverse=True)  # 비늘 치마
    _ng_scales(g)


def _ng_torso(g, ctx):
    w, h, d = ctx.size
    g.blob((0, h * 0.16, 0), (w * 0.5, h * 0.36, d * 0.52), 'skin', 0.5, top=0.12)
    g.capsule((0, h * 0.0, 0.1), (0, -h * 0.48, 0.1), w * 0.36, w * 0.38, 'skin', 0.47,
              sq=(1.0, 1.0, min(1.0, d / w * 1.2)))
    g.paint(lambda x, y, z, n, m, v: ('skin2', 0.55) if (n[2] < 0 and abs(x) < w * 0.26 and y < h * 0.15) else None,
            ['skin'])
    for s in (-1, 1):
        g.blob((s * w * 0.46, h * 0.36, 0), (w * 0.2, h * 0.16, d * 0.42), 'skin', 0.55)
    H = ctx.offset_to('head')
    hh = _size(ctx, 'head', (7, 7, 7))[1]
    g.capsule((0, h * 0.4, 0.2), (H[0], H[1] - hh * 0.32, H[2] + 0.6), w * 0.18, w * 0.16, 'skin', 0.5)
    g.mottle(['skin'], 0.07, 3.0)


def _ng_head(g, ctx):
    w, h, d = ctx.size
    g.blob((0, h * 0.08, 0.2), (w * 0.44, h * 0.44, d * 0.44), 'skin', 0.52, top=0.14)
    g.rbox((-w * 0.3, -h * 0.42, -d * 0.62), (w * 0.3, h * 0.1, -d * 0.1), 'skin', 0.5, bevel=1.0)    # 뱀 주둥이
    g.rbox((-w * 0.26, -h * 0.46, -d * 0.58), (w * 0.26, -h * 0.3, -d * 0.12), 'skin2', 0.55, bevel=0.5)
    g.carve(lambda x, y, z: abs(y + h * 0.28) < 0.25 and z < -d * 0.3 and abs(x) < w * 0.3)       # 입 선
    for s in (-1, 1):
        g.eye((s * w * 0.3, h * 0.12, -d * 0.38), 0.6, val=0.62, socket=0.3, facing=(s * 0.4, 0, -1), slit=True)
        g.capsule((s * w * 0.14, h * 0.32, -d * 0.48), (s * w * 0.42, h * 0.3, -d * 0.12), 0.45, 0.4, 'skin', 0.62)
        g.dot((s * w * 0.1, -h * 0.05, -d * 0.66), 'mouth', 0.1, prio=6)
        g.cone((s * w * 0.1, -h * 0.3, -d * 0.55), (0, -1, -0.1), 1.0, 0.3, 'tooth', 0.6, 0.9, prio=5)  # 송곳니
    g.scales(['skin'], size=1.6, amount=0.1)


def _ng_hood(g, ctx):
    A = _At(ctx)
    w, h, d = ctx.size
    hd = _size(ctx, 'head', (7, 7, 7))[2]
    z0 = A(0, 0, hd * 0.25)[2]
    yc = A(0, -1.0, 0)[1]
    yt, yb = yc + h * 0.5, yc - h * 0.62

    def mask(x, y):
        if y > yt or y < yb:
            return False
        t = (y - yb) / (yt - yb)
        half = w * 0.5 * math.sin(math.pi * min(1.0, 0.12 + t * 0.95)) ** 0.7
        return abs(x) <= max(1.2, half)

    def vfn(u, v, w_, e):
        front = w_ < 0
        if not front:
            return ('skin', 0.4 + 0.1 * (h2(int(u), int(v), 3) - 0.5))
        return ctx.shared['hood_front'](u, v, e)
    g.slab2d(mask, (-w * 0.5, yb), (w * 0.5, yt), plane='xy', depth=z0, half=0.6, mat='skin', vfn=vfn, bevel=1.6)


def _ng_tail(g, ctx, tip_fn=None):
    w, h, d = ctx.size
    nxt = {'tail_1': 'tail_2', 'tail_2': 'tail_3'}.get(ctx.name)
    r0 = min(w, h) * 0.5
    sq = (w / h, 1.0, 1.0) if w > h else (1.0, 1.0, 1.0)
    if nxt and ctx.part_def(nxt):
        e = ctx.offset_to(nxt)
        end = (e[0], e[1], e[2] + 0.4)
        ns = _size(ctx, nxt, (4, 3, 9))
        r1 = min(ns[0], ns[1]) * 0.5
    else:
        end = (0.0, -h * 0.2, d)
        r1 = 0.4
    g.sweep([(0, 0, -0.8), (end[0] * 0.5 + 0.4 * (1 if ctx.name == 'tail_2' else -1), end[1] * 0.5, end[2] * 0.5), end],
            r0, r1, 'skin', 0.48, sq=sq,
            vfn=lambda t, dd, p: ('skin2', 0.52) if p[1] < (end[1] * t) - r0 * 0.5 else 0.48 + 0.1 * (1 - dd))
    _ng_scales(g, seed=len(ctx.name))
    if tip_fn and not nxt:
        tip_fn(g, ctx, end)


def _ng_arm(g, ctx):
    _ct_arm(g, ctx)


# ── 4층 조류의 나가 tide_naga ── 청록 뱀 하반신 똬리, 금빛 무늬 코브라 후드, 조개·진주 장신구와 따개비, 물방울 구슬 산호 지팡이

TIDE_RAMPS = {
    'skin': [(8, 22, 28), (16, 40, 50), (26, 62, 74), (40, 90, 102), (62, 122, 130), (96, 160, 160), (140, 200, 192)],
    'skin2': [(40, 64, 60), (76, 110, 100), (118, 156, 140), (164, 198, 176), (206, 232, 210)],
    'orn': [(60, 40, 8), (120, 86, 20), (186, 140, 40), (236, 190, 80), (255, 226, 140), (255, 246, 210)],
    'eye': [(130, 90, 10), (210, 160, 30), (255, 213, 106), (255, 236, 170), (255, 250, 226), (255, 255, 255)],
    'glow': [(130, 90, 10), (210, 160, 30), (255, 213, 106), (255, 236, 170), (255, 250, 226), (255, 255, 255)],
    'core': [(10, 60, 90), (20, 120, 160), (60, 190, 220), (150, 236, 250), (220, 252, 255), (255, 255, 255)],
    'shell': [(60, 64, 60), (110, 112, 102), (160, 160, 146), (204, 202, 186), (236, 234, 220)],
    'bark': [(30, 26, 22), (58, 50, 42), (90, 80, 66), (124, 112, 94), (160, 148, 126)],
    'flesh': [(80, 30, 30), (150, 60, 56), (210, 110, 90), (240, 160, 130), (252, 204, 180)],
}


def _barnacles(g, mats, n, seed=0, region=None):
    surf = [k for k, nn in g.exposed(mats) if nn[1] > 0 and (region is None or region(*g.px(k)))]
    sd = g.seed + 811 + seed
    for k in sorted(surf, key=lambda q: h3(q[0], q[1], q[2], sd))[:n]:
        p = g.px(k)
        g.cylinder(p, vadd(p, (0, 0.8, 0)), 0.75, 0.45, 'shell', 0.6, prio=4)
        g.dot(vadd(p, (0, 0.9, 0)), 'shell', 0.2, prio=5)


def _tide_hood_front(u, v, e):
    if e < 0.7:
        return ('orn', 0.55)
    q = (abs(u) - 2.4) ** 2 + (v + 1.0) ** 2
    if q < 1.6:
        return ('glow', 0.6, True)
    if q < 2.8:
        return ('orn', 0.5)
    return ('skin2', 0.45 + 0.1 * math.sin(v * 1.6))


def _tide_fx(g, ctx):
    w, h, d = ctx.size
    n = ctx.name
    if n == 'coil':
        _barnacles(g, ['skin'], 6)
        g.streaks('water', ['skin', 'skin2'], density=0.15, length=(1.0, 3.0), val=0.5)
    elif n == 'waist':
        g.ring((0, h * 0.42, 0.1), w * 0.52, 0.45, axis='y', mat='orn', val=0.55)                 # 금 허리띠
        for k in range(4):
            a = -0.6 + 0.4 * k
            g.blob((math.sin(a) * w * 0.55, h * 0.36, -math.cos(a) * d * 0.6), 0.6, 'shell', 0.7, prio=4)
    elif n == 'torso':
        g.sweep([(-w * 0.32, h * 0.44, -d * 0.3), (0, h * 0.18, -d * 0.62), (w * 0.32, h * 0.44, -d * 0.3)], 0.35,
                0.35, 'orn', 0.6)                                                                  # 진주 목걸이
        _gem(g, (0, h * 0.15, -d * 0.7), 0.7, 'core', 'orn')
        g.blob((w * 0.5, h * 0.44, 0), (w * 0.26, 1.1, d * 0.5), 'shell', 0.55, prio=3)           # 조개 견갑
        g.bands(['shell'], axis=2, period=1.0, width=0.4, amount=-0.15)
        _barnacles(g, ['skin'], 3, region=lambda x, y, z: x < 0)
        g.streaks('water', ['skin'], density=0.12, length=(1.0, 3.0), val=0.55)
    elif n == 'head':
        for s in (-1, 1):                                                                          # 지느러미 귀
            g.sweep([(s * w * 0.4, h * 0.1, 0.2), (s * w * 0.62, h * 0.32, 1.2), (s * w * 0.66, h * 0.55, 2.4)],
                    0.9, 0.3, 'skin2', 0.5, sq=(0.45, 1.0, 1.0))
        g.ring((0, h * 0.42, 0.3), w * 0.32, 0.3, axis='y', mat='orn', val=0.6)                   # 금관 띠
        _gem(g, (0, h * 0.44, -w * 0.33), 0.5, 'core', 'orn')


def _tide_staff(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    ze = hz - L * 0.7
    g.sweep([(hx, hy, hz + 4.0), (hx + 0.3, hy - 0.2, hz - 4.0), (hx - 0.2, hy + 0.2, ze + 2.0)], 0.6, 0.5, 'bark',
            0.5, vfn=lambda t, dd, p: 0.42 + 0.16 * (1 - dd) + 0.08 * math.sin(t * 30))
    g.capsule((hx, hy, hz + 1.5), (hx, hy, hz - 1.5), 0.75, 0.75, 'orn', 0.45)
    c = (hx, hy + 0.4, ze - 1.6)
    for k in range(4):                                                                             # 구슬을 받친 산호
        a = k * math.pi / 2 + 0.4
        g.branch((hx, hy, ze + 1.8), (math.cos(a) * 0.6, math.sin(a) * 0.6, -1), 3.6, 0.4, depth=1, fork=2,
                 spread=0.5, mat='flesh', val=0.5, seed=k)
    g.blob(c, 1.9, 'core', 0.6, glow=True, prio=5, vfn=lambda x, y, z, dd: 0.85 - 0.4 * dd)        # 물방울 구슬
    g.dot(vadd(c, (-0.6, 0.7, -1.2)), 'core', 1.0, glow=True, prio=6)
    _barnacles(g, ['bark'], 2)


def _tide_tail_tip(g, ctx, end):
    g.slab2d(lambda u, v: abs(v) <= 2.2 * max(0.0, (u - end[2] + 3.5) / 3.5) and end[2] - 3.5 <= u <= end[2] + 0.6,
             (end[2] - 3.5, -2.4), (end[2] + 0.6, 2.4), plane='zy', depth=0.0, half=0.3, mat='skin2',
             vfn=lambda u, v, w_, e: 0.4 + 0.2 * (int(v * 2) % 2))                                 # 꼬리 지느러미


# ── 8층 먹물 나가 ink_naga ── 먹물 웅덩이 같은 검푸른 뱀 하반신, 후드 안쪽 잉크 글씨, 펼친 책과 커다란 깃펜, 흘러내리는 먹물

INK_RAMPS = {
    'skin': [(4, 4, 8), (10, 12, 20), (18, 22, 38), (30, 38, 62), (48, 60, 92), (74, 90, 128), (110, 126, 166)],
    'skin2': [(16, 18, 30), (30, 36, 58), (50, 60, 92), (80, 92, 128), (120, 132, 166)],
    'ink': [(2, 2, 6), (8, 10, 18), (16, 20, 34), (28, 34, 56)],
    'paper': [(92, 84, 66), (150, 140, 114), (196, 188, 160), (232, 224, 200), (248, 244, 228)],
    'eye': [(40, 60, 120), (80, 120, 200), (150, 190, 250), (210, 230, 255), (244, 250, 255), (255, 255, 255)],
    'rune': [(40, 60, 120), (80, 120, 200), (150, 190, 250), (210, 230, 255), (244, 250, 255), (255, 255, 255)],
    'glow': [(40, 60, 120), (80, 120, 200), (150, 190, 250), (210, 230, 255), (244, 250, 255), (255, 255, 255)],
    'leather': [(10, 12, 24), (20, 24, 44), (34, 40, 70), (52, 60, 100), (76, 86, 130)],
    'orn': [(60, 44, 14), (120, 92, 34), (180, 146, 70), (224, 196, 120), (246, 230, 180)],
    'feather': [(90, 84, 70), (150, 142, 120), (204, 196, 172), (236, 230, 210), (250, 248, 238)],
}


def _ink_hood_front(u, v, e):
    if e < 0.6:
        return ('skin', 0.3)
    row = int((v + 20) / 1.2)
    if (row % 2 == 0) and h2(int(u * 1.6), row, 77) < 0.55:
        return ('ink', 0.3)
    if h2(int(u * 1.3), row, 79) < 0.06:
        return ('rune', 0.6, True)
    return ('paper', 0.5 + 0.1 * math.sin(u))


def _ink_drips(g, mats, density=0.18):
    g.streaks('ink', mats, density=density, length=(1.5, 4.5), val=0.3, val_end=0.05)


def _ink_fx(g, ctx):
    w, h, d = ctx.size
    n = ctx.name
    if n in ('coil', 'waist'):
        g.paint(lambda x, y, z, n_, m, v: ('ink', 0.2) if (n_[1] > 0 and fbm3(x / 2.0, y / 2.0, z / 2.0, 5) > 0.6)
                else None, ['skin'])                                                               # 먹물 웅덩이 얼룩
    if n == 'waist':
        g.cloth([(-w * 0.5, h * 0.4, -d * 0.4), (0, h * 0.42, -d * 0.62), (w * 0.5, h * 0.4, -d * 0.4)], 4.0,
                'paper', 0.5, tatter=0.4)                                                          # 두루마리 띠
        g.bands(['paper'], axis=1, period=1.0, width=0.3, amount=-0.3)
    elif n == 'torso':
        g.cloth([(-w * 0.46, h * 0.46, -d * 0.2), (-w * 0.2, h * 0.3, -d * 0.62), (w * 0.2, h * 0.3, -d * 0.62),
                 (w * 0.46, h * 0.46, -d * 0.2)], lambda u: 3.5 + 6.0 * abs(u - 0.5), 'paper', 0.5, tatter=0.3)  # 학자 목도리
        g.paint(lambda x, y, z, n_, m, v: ('ink', 0.25) if int((y + 20) / 0.9) % 2 == 0 and h2(int(x * 2), int(y), 3) < 0.5
                else None, ['paper'])
        _gem(g, (0, h * 0.34, -d * 0.7), 0.6, 'rune', 'orn')
    elif n == 'head':
        g.capsule((-w * 0.46, h * 0.36, 0.2), (w * 0.46, h * 0.36, 0.2), 0.35, 0.35, 'orn', 0.6)
        g.blob((0, h * 0.5, 0.6), (w * 0.3, 0.6, d * 0.3), 'ink', 0.3, prio=2)
    if n in ('torso', 'head', 'coil', 'waist'):
        _ink_drips(g, ['skin', 'skin2', 'paper'])


def _ink_book(g, ctx):
    hx, hy, hz = ctx.hand
    W, H, _ = ctx.size
    c = (hx, hy + 0.4, hz - 1.6)
    g.capsule(vadd(c, (0, -H * 0.5, 0.4)), vadd(c, (0, H * 0.5, 0.4)), 0.55, 0.55, 'leather', 0.4)   # 책등
    for s in (-1, 1):
        a = vadd(c, (0, 0, 0.2))
        b = vadd(c, (s * W * 0.48, 0, -W * 0.26))
        lo, hi = (min(a[0], b[0]), c[1] - H * 0.5, min(a[2], b[2])), (max(a[0], b[0]), c[1] + H * 0.5, max(a[2], b[2]))
        nrm = vnorm((W * 0.26, 0, s * W * 0.48))

        def page(x, y, z, a=a, nrm=nrm, s=s):
            dd = (x - a[0]) * nrm[0] * s + (z - a[2]) * nrm[2]
            if abs(dd) > 0.55:
                return None
            if abs(y - c[1]) > H * 0.47 or dd > 0.25:
                return ('leather', 0.45)
            return ('ink', 0.3) if (int((y - c[1] + 10) / 0.9) % 2 == 0 and h2(int(x * 3), int(y * 2), 5) < 0.6) else \
                ('paper', 0.6)
        g.rbox(lo, hi, 'paper', 0.6, vfn=page)
    for k in range(3):                                                                             # 떠오르는 글자
        g.dot(vadd(c, (0.6 * (k - 1), H * 0.55 + 0.7 * k, -1.5 - 0.3 * k)), 'rune', 0.7, glow=True, prio=6)


def _ink_quill(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    zt = hz - L * 0.82
    g.capsule((hx, hy, hz + 3.0), (hx, hy, zt + 1.2), 0.35, 0.3, 'feather', 0.7)                   # 깃대
    g.cone((hx, hy, zt + 1.4), (0, -0.2, -1), 2.2, 0.55, 'orn', 0.5, 0.8)                        # 금 펜촉
    g.blob((hx, hy - 0.6, zt - 0.6), 0.5, 'rune', 0.7, glow=True, prio=6)                          # 맺힌 먹물빛

    def vane(u, v, w_, e):
        t = (hz + 3.0 - u) / (hz + 3.0 - zt)
        return ('ink', 0.3) if t > 0.72 else ('feather', 0.45 + 0.25 * (1 - t) + (0.1 if int(v * 2 + u) % 3 == 0 else 0))

    def mask(u, v):
        t = (hz + 3.0 - u) / (hz + 3.0 - zt)
        if t < 0.0 or t > 0.82:
            return False
        top = 3.2 * math.sin(math.pi * min(1.0, t / 0.82)) ** 0.6
        return -top * 0.45 <= v - hy <= top
    g.slab2d(mask, (zt, hy - 2.0), (hz + 3.0, hy + 3.4), plane='zy', depth=hx, half=0.25, mat='feather', vfn=vane,
             prio=2)
    _ink_drips(g, ['ink'], 0.3)


def _ink_tail_tip(g, ctx, end):
    for k in (-1, 1):                                                                              # 먹물 가닥
        g.sweep([vadd(end, (0, 0, -0.6)), vadd(end, (k * 1.0, -0.4, 1.6)), vadd(end, (k * 1.6, -0.6, 3.0))], 0.5, 0.25,
                'ink', 0.3)


_NG = {
    'tide_naga': (TIDE_RAMPS, _tide_fx, _tide_hood_front, {'staff': _tide_staff}, _tide_tail_tip),
    'ink_naga': (INK_RAMPS, _ink_fx, _ink_hood_front, {'book': _ink_book, 'quill': _ink_quill}, _ink_tail_tip),
}
_NG_BASE = {'coil': _ng_coil, 'waist': _ng_waist, 'torso': _ng_torso, 'head': _ng_head, 'hood': _ng_hood,
            'arm_left': _ng_arm, 'arm_right': _ng_arm}
_NG_VS = {'coil': 0.8, 'waist': 0.7, 'torso': 0.65, 'tail_1': 0.75, 'tail_2': 0.7, 'tail_3': 0.6, 'hood': 0.55,
          'staff': 0.55, 'quill': 0.5, 'head': 0.55}


def naga(look, name, part, ctx):
    ramps, fx, hood_front, extra, tip = _NG[ctx.mid]
    _ramps(ctx, ramps)
    ctx.shared['hood_front'] = hood_front
    g = _grid(ctx, _NG_VS.get(name, 0.5))
    if name in extra:
        extra[name](g, ctx)
        return g
    if name.startswith('tail_'):
        _ng_tail(g, ctx, tip)
    elif name in _NG_BASE:
        _NG_BASE[name](g, ctx)
    else:
        return None
    fx(g, ctx)
    return g


# ═════════════════════════════════ 9층 황동 미노타우로스 brass_minotaur ═════════════════════════════════
# 황동으로 다시 빚은 소머리 거인: 짙은 청동빛 가죽 + 리벳 박은 황동 판, 가슴 창 안의 달아오른 태엽 용수철, 큰 뿔(황동 고리·끝),
# 코뚜레, 굽 달린 다리와 황동 정강이받이, 양날 도끼.

MINO_RAMPS = {
    'fur': [(14, 10, 6), (30, 20, 12), (50, 34, 20), (76, 52, 30), (106, 74, 44), (140, 100, 62)],
    'skin': [(14, 10, 6), (30, 20, 12), (50, 34, 20), (76, 52, 30), (106, 74, 44), (140, 100, 62)],
    'brass': [(40, 24, 8), (84, 54, 18), (136, 92, 34), (190, 138, 62), (226, 180, 100), (248, 222, 160),
              (255, 244, 210)],
    'iron': [(14, 12, 12), (30, 28, 28), (52, 50, 48), (80, 76, 72), (112, 106, 100), (150, 144, 136)],
    'core': [(120, 30, 6), (200, 70, 14), (255, 106, 42), (255, 170, 100), (255, 224, 180), (255, 255, 255)],
    'eye': [(120, 30, 6), (200, 70, 14), (255, 106, 42), (255, 170, 100), (255, 224, 180), (255, 255, 255)],
    'horn': [(40, 32, 22), (80, 66, 46), (126, 108, 78), (172, 154, 118), (212, 198, 164), (240, 232, 206)],
    'leather': [(16, 10, 6), (32, 20, 12), (54, 34, 20), (80, 52, 30), (108, 72, 44)],
    'blade': [(40, 40, 44), (80, 80, 86), (130, 130, 136), (180, 180, 184), (222, 222, 224), (250, 250, 250)],
}


def _mino_torso(g, ctx):
    w, h, d = ctx.size
    g.blob((0, h * 0.12, 0), (w * 0.5, h * 0.4, d * 0.5), 'fur', 0.5, top=0.12)                      # 가슴
    g.capsule((0, -h * 0.05, 0.2), (0, -h * 0.42, 0.2), w * 0.36, w * 0.38, 'fur', 0.46, sq=(1.0, 1.0, d / w * 1.1))
    H = ctx.offset_to('head')
    g.blob((0, h * 0.42, 0.8), (w * 0.36, h * 0.2, d * 0.42), 'fur', 0.52)                          # 목 혹
    g.capsule((0, h * 0.4, 0), (H[0], H[1] - 3.0, H[2] + 1.0), w * 0.24, w * 0.22, 'fur', 0.5)
    g.mottle(['fur'], 0.08, 3.0)
    # 가슴판: 리벳 박은 황동 판 두 장 + 가운데 둥근 창(태엽 용수철, 뒤에서 달아오름)
    for s in (-1, 1):
        g.plate((s * 0.6, h * 0.0, -d * 0.6), (s * w * 0.44, h * 0.4, -d * 0.24), 'brass', 0.5, rivet_mat='brass',
                rivet_step=2.0, bevel=0.8)
    c = (0, h * 0.17, -d * 0.56)
    g.carve_blob(c, (2.4, 2.4, 1.6))
    g.blob(vadd(c, (0, 0, 1.2)), (2.2, 2.2, 0.8), 'core', 0.55, glow=True, prio=3)
    g.ring(c, 2.5, 0.55, axis='z', mat='brass', val=0.65)
    pts = [(c[0] + 1.5 * math.cos(a), c[1] - 2.0 + 4.0 * a / (8 * math.pi), c[2] + 0.2 + 1.5 * math.sin(a) * 0.4)
           for a in [k * 0.4 for k in range(int(8 * math.pi / 0.4) + 1)]]
    g.sweep(pts, 0.32, 0.32, 'brass', 0.62, smooth=False, prio=4)                                  # 용수철
    g.plates((0, -h * 0.28, -d * 0.2), (w * 0.4, h * 0.18, d * 0.42), n=3, axis=1, mat='brass', val=0.42,
             lift=0.08, cut=lambda x, y, z: z > -d * 0.1)                                          # 배 판
    g.rbox((-w * 0.46, -h * 0.5, -d * 0.56), (w * 0.46, -h * 0.38, d * 0.56), 'leather', 0.35, bevel=0.5)
    g.rbox((-1.4, -h * 0.52, -d * 0.62), (1.4, -h * 0.36, -d * 0.54), 'brass', 0.6, bevel=0.3)
    g.streaks('rust', ['brass'], density=0.1, length=(1.0, 2.5), val=0.35)


def _mino_head(g, ctx):
    w, h, d = ctx.size
    g.rbox((-w * 0.46, -h * 0.2, -d * 0.12), (w * 0.46, h * 0.48, d * 0.5), 'fur', 0.5, bevel=1.6, top=0.12)
    g.rbox((-w * 0.36, -h * 0.5, -d * 0.6), (w * 0.36, h * 0.1, -d * 0.05), 'fur', 0.46, bevel=1.4)  # 주둥이
    g.rbox((-w * 0.38, -h * 0.5, -d * 0.62), (w * 0.38, -h * 0.12, -d * 0.4), 'skin', 0.62, bevel=1.0, prio=2)
    for s in (-1, 1):
        g.carve_blob((s * w * 0.18, -h * 0.25, -d * 0.62), (0.6, 0.7, 0.6))                         # 콧구멍
        g.blob((s * w * 0.18, -h * 0.25, -d * 0.55), 0.55, 'mouth', 0.1, prio=1)
        g.eye((s * w * 0.4, h * 0.14, -d * 0.12), 0.65, val=0.6, socket=0.35, facing=(s * 0.6, 0, -1))
        g.cone((s * w * 0.5, h * 0.22, d * 0.2), (s, -0.1, 0.3), 2.2, 0.9, 'fur', 0.45, 0.55)        # 귀
    g.plate((-w * 0.3, h * 0.12, -d * 0.2), (w * 0.3, h * 0.5, -d * 0.1), 'brass', 0.5, rivet_mat='brass',
            rivet_step=1.6, bevel=0.5, face=(0, 0, -1))                                             # 이마 판
    g.rbox((-w * 0.5, h * 0.24, -d * 0.16), (w * 0.5, h * 0.36, -d * 0.06), 'brass', 0.4, prio=3)   # 눈썹 띠


def _mino_horns(g, ctx):
    A = _At(ctx)
    hw, hh, hd = _size(ctx, 'head', (9, 9, 10))
    for s in (-1, 1):
        b = A(s * hw * 0.42, hh * 0.36, hd * 0.1)
        g.blob(b, 1.6, 'brass', 0.5)
        g.horn(b, (s, 0.12, -0.05), 7.6, 1.45, curl=(s * 0.4, 2.6, -2.6), mat='horn', val=0.45, rings=1.0,
               tip_mat='brass')
        for t in (0.3,):
            p = vadd(b, (s * 7.6 * t, 0.5 * t, -0.5 * t * t))
            g.ring(p, 1.45 * (1 - 0.5 * t) + 0.2, 0.3, axis='x', mat='brass', val=0.6)


def _mino_ring(g, ctx):
    w, h, d = ctx.size
    g.ring((0, -h * 0.25, 0), w * 0.38, 0.4, axis='z', mat='brass', val=0.65)
    g.dot((0, -h * 0.25 - w * 0.38, 0), 'brass', 0.85, prio=4)


def _mino_arm(g, ctx):
    w, h, d = ctx.size
    o = ctx.out
    g.capsule((0, -0.6, 0), (0, -h * 0.46, 0.3), w * 0.44, w * 0.38, 'fur', 0.5)
    g.blob((0, -h * 0.47, 0.3), w * 0.38, 'fur', 0.55)
    g.capsule((0, -h * 0.5, 0.3), (0, -h * 0.82, 0.0), w * 0.38, w * 0.34, 'fur', 0.47)
    g.blob((0, -h + 1.2, -0.3), (w * 0.42, w * 0.42, w * 0.44), 'fur', 0.5)                         # 주먹
    for k in (-1, 0, 1):
        g.blob((k * w * 0.2, -h + 1.0, -w * 0.4), 0.6, 'brass', 0.6, prio=3)                       # 손마디 징
    g.plates((0, 0.2, 0), (w * 0.62, w * 0.5, w * 0.62), n=3, axis=1, mat='brass', val=0.5, lift=0.12,
             reverse=True, cut=lambda x, y, z: y < -1.6)                                          # 어깨 판
    g.rivets([(o * w * 0.6, -0.6, z) for z in (-1.6, 0, 1.6)], 'brass', 0.8)
    g.cylinder((0, -h * 0.56, 0.25), (0, -h * 0.84, 0.0), w * 0.42, w * 0.4, 'brass', 0.48)        # 팔뚝 토시
    for y in (-h * 0.6, -h * 0.8):
        g.ring((0, y, 0.15), w * 0.43, 0.3, axis='y', mat='brass', val=0.7)


def _mino_axe(g, ctx):
    hx, hy, hz = ctx.hand
    L = ctx.size[1]
    ze = hz - L * 0.66
    g.capsule((hx, hy, hz + 5.0), (hx, hy, ze - 1.6), 0.8, 0.75, 'bark', 0.42)
    g.blob((hx, hy, hz + 5.3), 1.1, 'brass', 0.55)
    for z in (hz - 3.0, ze + 3.0):
        g.ring((hx, hy, z), 0.85, 0.3, axis='z', mat='brass', val=0.6)
    g.capsule((hx, hy, hz + 1.8), (hx, hy, hz - 1.8), 0.95, 0.95, 'leather', 0.4)
    W = ctx.size[0] * 0.5
    for s in (-1, 1):                                                                              # 초승달 날 두 장
        def mask(u, v, s=s):
            dv = (v - hy) * s
            if dv < 0.6 or dv > W:
                return False
            half = 1.4 + 3.2 * (dv / W) ** 1.4
            return abs(u - ze) <= half and not (dv < W * 0.55 and abs(u - ze) > 1.4 + 1.2 * (dv / W))

        def vfn(u, v, w_, e, s=s):
            dv = (v - hy) * s
            return ('blade', 0.7) if dv > W - 1.0 else ('brass', 0.45 + 0.25 * dv / W)
        g.slab2d(mask, (ze - 5.0, hy - W - 0.5), (ze + 5.0, hy + W + 0.5), plane='zy', depth=hx, half=0.6,
                 mat='brass', vfn=vfn, bevel=1.2)
    g.gear((hx, hy, ze), 1.6, teeth=8, axis='x', thick=1.6, mat='brass', val=0.6)
    g.dot((hx - 0.9, hy, ze), 'core', 0.7, glow=True, prio=6)
    g.dot((hx + 0.9, hy, ze), 'core', 0.7, glow=True, prio=6)


def _mino_tail(g, ctx):
    w, h, d = ctx.size
    pts = [(0, 0, -0.4), (0, -2.0, 1.6), (0, -6.0, 2.6), (0, -h + 1.6, 2.2)]
    g.sweep(pts, 0.8, 0.6, 'fur', 0.5)
    for k in range(1, 4):
        g.ring(pts[k] if k < 3 else vadd(pts[3], (0, 0.6, 0)), 0.85, 0.3, axis='y', mat='brass', val=0.6)
    g.blob(vadd(pts[-1], (0, -0.9, 0)), (0.9, 1.6, 0.9), 'fur', 0.35, lump=0.3, lump_scale=0.8)   # 꼬리 술


def _mino_legs(g, ctx):
    w, h, d = ctx.size
    g.plates((0, -3.2, 0), (w * 0.5, 3.6, d * 0.62), n=3, axis=1, mat='brass', val=0.45, reverse=True,
             cut=lambda x, y, z: y > 0.4)                                                         # 허리 판 치마
    g.rbox((-w * 0.46, -0.6, -d * 0.56), (w * 0.46, 0.6, d * 0.56), 'leather', 0.35, bevel=0.4)
    for s in (-1, 1):
        x = s * w * 0.27
        hip, knee = (x, -1.0, 0.3), (x * 1.04, -h * 0.4, -1.6)
        ank, foot = (x * 1.04, -h * 0.76, 1.2), (x, -h + 1.4, 0.0)
        g.limb([hip, knee, ank, foot], [w * 0.2, w * 0.15, w * 0.11, w * 0.11], 'fur', 0.48, knob=1.12)
        g.blob(knee, w * 0.17, 'brass', 0.55, prio=3, cut=lambda x_, y, z: z > knee[2] + 0.4)      # 무릎 판
        g.capsule(vadd(ank, (0, -0.4, -0.2)), vadd(foot, (0, 0.6, -0.2)), w * 0.14, w * 0.13, 'brass', 0.5,
                  prio=2)                                                                          # 정강이받이
        g.rbox((x - w * 0.15, -h, -1.6), (x + w * 0.15, -h + 1.6, 1.2), 'horn', 0.3, bevel=0.5)    # 굽
        g.carve(lambda x_, y, z, x=x: abs(x_ - x) < 0.3 and y < -h + 1.4 and z < -0.6)            # 갈라진 굽
        g.blob((x, -h + 2.0, 0.0), (w * 0.15, 0.8, 1.4), 'fur', 0.4, lump=0.3, lump_scale=0.8)     # 발목 털


_MINO = {'torso': _mino_torso, 'head': _mino_head, 'horns': _mino_horns, 'nose_ring': _mino_ring,
         'arm_left': _mino_arm, 'arm_right': _mino_arm, 'axe': _mino_axe, 'tail': _mino_tail, 'legs': _mino_legs}
_MINO_VS = {'torso': 0.8, 'head': 0.65, 'legs': 0.8, 'arm_left': 0.7, 'arm_right': 0.7, 'axe': 0.6, 'horns': 0.6}


def brass_minotaur(look, name, part, ctx):
    _ramps(ctx, MINO_RAMPS)
    fn = _MINO.get(name)
    if fn is None:
        return None
    g = _grid(ctx, _MINO_VS.get(name, 0.5))
    fn(g, ctx)
    return g


DESIGNS = {
    'thorn_kobold': dragonkin, 'kobold_sapper': dragonkin, 'forge_dragonkin': dragonkin,
    'crystal_dragonkin': dragonkin, 'abyss_dragonkin': dragonkin,
    'myconid_centaur': centaur, 'prism_centaur': centaur,
    'tide_naga': naga, 'ink_naga': naga,
    'brass_minotaur': brass_minotaur,
}
