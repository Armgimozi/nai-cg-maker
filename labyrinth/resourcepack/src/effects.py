"""Animation effect presets (GDD §14.2): evaluated per texel in model space for every frame,
so runes, flames and lightning flow coherently across all faces of a 3D model.

Only texels flagged `glow` (blade, gems, crystals, ornaments chosen by the template) animate;
grips/guards stay fixed.
"""
from __future__ import annotations

import math

from .materials import rune_bit, _voronoi
from .model import value_to_color
from .util import clamp, darken, fbm, h2, h3, hue_shift, lighten, lum, mix, vnoise

INTERPOLATE = {'sun_glow', 'holy_pulse', 'blood_pulse', 'aurora_wave', 'prism_cycle', 'sculk_pulse',
               'eclipse_corona', 'tide_ripple', 'mercury_flow', 'feather_glint',
               'geode_heart', 'tide_surge', 'bell_toll', 'moon_phase'}

KNOWN = {'sun_glow', 'ember_flicker', 'wind_streak', 'frost_shimmer', 'holy_pulse', 'shadow_smoke', 'tide_ripple',
         'prism_cycle', 'gear_tick', 'star_twinkle', 'blood_pulse', 'lightning_arc', 'void_swirl', 'feather_glint',
         'eclipse_corona', 'rune_flow', 'soul_flicker', 'crystal_glint', 'ink_bleed', 'sculk_pulse', 'spark_crackle',
         'mercury_flow', 'aurora_wave', 'venom_drip', 'ember_glow',
         # 0.3.7 신화 6 (myth-037)
         'geode_heart', 'tide_surge', 'comet_trail', 'wisp_flicker', 'bell_toll', 'moon_phase'}

# 0.3.7 새 효과가 (모델이 바뀌어) 움직이는 칸을 하나도 못 찾으면 대신 쓸 기존 효과 — animate() 가 고른다
FALLBACK = {'geode_heart': 'crystal_glint', 'tide_surge': 'tide_ripple', 'comet_trail': 'wind_streak',
            'wisp_flicker': 'ember_glow', 'bell_toll': 'holy_pulse', 'moon_phase': 'frost_shimmer'}

# wisp_flicker: 16 박자 밝기 — 두 번 밝게(2·6), 한 번 꺼질 듯(9–11), 나머지는 잔잔하게
FLICKER = (0.05, 0.18, 0.36, 0.3, 0.08, 0.22, 0.38, 0.2, -0.05, -0.38, -0.45, -0.25, 0.0, 0.1, 0.06, 0.02)
# bell_toll: (울린 때, 세기) — 한 번 크게, 두 번 작게, 쉬고
TOLLS = ((0.0, 1.0), (0.3, 0.55), (0.45, 0.5))

WHITE = (255, 255, 255)


class FxCtx:
    def __init__(self, texels, look, n, seed):
        g = [t for t in texels if t.glow] or list(texels)
        self.look = look
        self.n = n
        self.seed = seed & 0xFFFF
        xs = [t.pos[0] for t in g]
        ys = [t.pos[1] for t in g]
        zs = [t.pos[2] for t in g]
        self.x0, self.x1 = min(xs), max(xs) + 1e-6
        self.y0, self.y1 = min(ys), max(ys) + 1e-6
        self.z0, self.z1 = min(zs), max(zs) + 1e-6
        self.cx = (self.x0 + self.x1) / 2
        self.cy = (self.y0 + self.y1) / 2
        self.cz = (self.z0 + self.z1) / 2
        self.A = look.accent
        self.top = look.pal.light
        self.wcol = lighten(look.pal.accent, 0.75)
        self.glow_texels = g
        self._spans = {}

    def span(self, roles, axis=1):
        """(min, max) of the glow texels of these materials along axis — anchors a part (bell lip, comet head,
        sickle edge) inside the whole item's glow box.  No such texel → the whole glow box."""
        key = (tuple(roles), axis)
        if key not in self._spans:
            vs = [t.pos[axis] for t in self.glow_texels if t.role in roles]
            lo = (self.x0, self.y0, self.z0)[axis]
            hi = (self.x1, self.y1, self.z1)[axis]
            self._spans[key] = (min(vs), max(vs) + 1e-6) if vs else (lo, hi)
        return self._spans[key]

    def anchor_above(self, role):
        """Lowest glow texel of `role` above the glow box's middle height (e.g. a bell's lip, not the pommel gem)."""
        key = ('above', role)
        if key not in self._spans:
            vs = [t.pos[1] for t in self.glow_texels if t.role == role and t.pos[1] > self.cy]
            self._spans[key] = min(vs) if vs else self.cy
        return self._spans[key]

    def T(self, t):
        return (t.pos[1] - self.y0) / (self.y1 - self.y0)

    def S(self, t):
        if t.face in ('east', 'west'):
            return (t.pos[2] - self.z0) / (self.z1 - self.z0)
        return (t.pos[0] - self.x0) / (self.x1 - self.x0)

    def planar(self, t):
        """in-plane horizontal coordinate (x on front/back/top faces, z on side faces)."""
        if t.face in ('east', 'west'):
            return t.pos[2] - self.cz + self.cx
        return t.pos[0]

    @staticmethod
    def g(t):
        return int(math.floor(t.pos[0] * 2 + 1e-6)), int(math.floor(t.pos[1] * 2 + 1e-6)), int(math.floor(t.pos[2] * 2 + 1e-6))


def _gauss(x, w):
    return math.exp(-(x / w) ** 2)


def _wrapd(a, b):
    d = abs(a - b) % 1.0
    return min(d, 1 - d)


def make_vfn(effect, ctx: FxCtx, f):
    N = ctx.n
    p = f / N
    A = ctx.A
    seed = ctx.seed
    eff = effect if effect in KNOWN else 'rune_flow'

    def base(t):
        return t.color if t.color is not None else value_to_color(t.ramp, t.v)

    def vfn(t):
        if not t.glow:
            return None
        gx, gy, gz = FxCtx.g(t)
        T = ctx.T(t)
        S = ctx.S(t)
        if eff == 'sun_glow':
            c = p * 1.5 - 0.25
            band = _gauss(T - c, 0.14)
            if band > 0.75 and (gx + gy) % 2 == 0:
                return lighten(ctx.top, 0.6), 0
            if p >= 0.75 and T > 0.9 and ((gx + gy + f) % 3 == 0):
                return WHITE, 0
            return None, 0.5 * band - 0.05
        if eff == 'ember_glow':
            # 0.3.6 오리하르콘 곡괭이: 붉은 금 날이 천천히 달아오르고(숨쉬듯), 불티가 날을 따라 올라간다
            rise = h3(gx, gy - f, gz, seed)
            if rise > 0.86:
                return (A[5] if rise > 0.93 else A[4]), 0
            return None, 0.22 * math.sin(2 * math.pi * (p - 0.35 * T)) + 0.04
        if eff in ('ember_flicker', 'soul_flicker'):
            rise = h3(gx, gy - f, gz, seed)
            thr = 0.72 if t.role in ('edge', 'glow', 'gem', 'crystal', 'head') else 0.82
            if rise > thr:
                c = A[5] if rise > thr + 0.08 else A[4]
                if eff == 'soul_flicker' and rise > 0.985 and f % 4 == 0:
                    c = WHITE
                return c, 0
            return None, (h3(gx, gy, f, seed + 3) - 0.5) * 0.22
        if eff == 'wind_streak':
            d = (T + S * 0.5 - p * 2.0) % 1.0
            if d < 0.06:
                return lighten(ctx.top, 0.55), 0
            if d < 0.13:
                return None, 0.3
            return None, 0
        if eff == 'frost_shimmer':
            if h3(gx, gy, gz, f * 7 + seed) > 0.94:
                return WHITE, 0
            rim = 0.18 if (t.i == 0 or t.j == 0 or T > 0.88) else 0
            return None, rim + 0.08 * math.sin(2 * math.pi * (p + T))
        if eff == 'holy_pulse':
            dv = 0.3 * math.sin(2 * math.pi * p)
            if t.role in ('gem', 'glow') and abs(p - 0.25) < 0.13 and (gx % 2 == 0 or gy % 2 == 0):
                return WHITE, 0
            return None, dv
        if eff == 'shadow_smoke':
            n = vnoise(gx * 0.33, (gy - f * 1.5) * 0.33, seed)
            if n > 0.74:
                return A[2], 0
            if n > 0.6:
                return None, -0.4
            return None, 0.05
        if eff == 'tide_ripple':
            if h3(gx, gy, gz, f + seed) > 0.965:
                return WHITE, 0
            return None, 0.3 * math.sin(2 * math.pi * (T * 2.5 - p))
        if eff == 'prism_cycle':
            side = (S + 0.15 * math.sin(T * 6.0)) < 0.5
            dv = 0.3 * math.sin(2 * math.pi * p) * (1 if side else -1)
            if _wrapd(T, p) < 0.06:
                return hue_shift((255, 120, 120), (T * 2 + p) * 360, 0.6, 1.0), 0
            return None, dv
        if eff == 'gear_tick':
            x = ctx.planar(t)
            a = math.atan2(t.pos[1] - ctx.cy, x - ctx.cx)
            hand = (f / N) * 2 * math.pi
            da = abs((a - hand + math.pi) % (2 * math.pi) - math.pi)
            if da < 0.22:
                return A[5], 0
            teeth = math.sin(6 * (a - math.radians(60.0 / N * f)))
            return None, 0.22 if teeth > 0.55 else -0.08
        if eff == 'star_twinkle':
            if h3(gx, gy, gz, seed) > 0.84:
                ph = h3(gx, gy, gz, seed + 1)
                b = max(0.0, math.cos(2 * math.pi * (p - ph))) ** 4
                if b > 0.6:
                    return WHITE, 0
                if b > 0.25:
                    return A[4], 0
            return None, 0.12 * _gauss(_wrapd(T, p), 0.1)
        if eff == 'blood_pulse':
            beat = _gauss(min(p, 1 - p), 0.06) + 0.75 * _gauss(p - 0.2, 0.06)
            col = h2(gx, 0, seed)
            if col > 0.78:
                head = 1 - ((p + h2(gx, 1, seed)) % 1.0)
                if 0 <= T - head < 0.07:
                    return A[4], 0
            return None, 0.48 * beat - 0.12
        if eff == 'lightning_arc':
            if f % 4 == 3:
                return None, -0.15
            # each frame a different subset of parts carries a zigzag bolt in face-local space
            if h2(t.el, f, seed) < 0.45:
                return None, -0.05
            seg = max(1, t.h // 3) if t.h >= t.w else max(1, t.w // 3)
            if t.h >= t.w:
                k = t.j // 2
                path = int(h2(k, f + t.el * 31, seed) * t.w)
                d = abs(t.i - path)
            else:
                k = t.i // 2
                path = int(h2(k, f + t.el * 31, seed) * t.h)
                d = abs(t.j - path)
            if d == 0:
                return WHITE, 0
            if d == 1:
                return A[4], 0
            return None, 0.08
        if eff == 'void_swirl':
            x = ctx.planar(t)
            dx, dy = x - ctx.cx, t.pos[1] - ctx.cy
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx)
            if h3(gx, gy, gz, seed + f) > 0.975:
                return A[5], 0
            s = math.sin(3 * a + r * 0.9 + 2 * math.pi * p)
            return None, (-0.35 if s > 0.35 else 0.12)
        if eff == 'feather_glint':
            d = abs(T - (p * 1.3 - 0.15))
            if d < 0.05:
                return lighten(ctx.top, 0.5), 0
            if p > 0.85 and T > 0.92:
                return WHITE, 0
            return None, 0.35 * _gauss(d, 0.12)
        if eff == 'eclipse_corona':
            x = ctx.planar(t)
            dx, dy = x - ctx.cx, t.pos[1] - ctx.cy
            r = math.hypot(dx, dy) / max(1e-3, (ctx.y1 - ctx.y0) / 2)
            a = math.atan2(dy, dx)
            L = 0.55 + 0.3 * math.sin(2 * math.pi * p)
            ray = math.cos(8 * (a - p * 2 * math.pi / 8))
            if r < 0.18:
                return darken(ctx.look.pal.dark, 0.6), 0
            if ray > 0.8 and r < 0.18 + L:
                return A[5] if ray > 0.93 else A[4], 0
            return None, -0.1
        if eff == 'rune_flow':
            k = max(1, N // 8)
            sh = int(round(f * 8 * k / N))
            yy = gy - sh
            col = gx // 4
            row = (yy // 8) % k
            gi = int(h2(col, row, seed) * 8)
            if t.role in ('blade', 'fuller', 'head', 'crystal', 'plate', 'gem', 'glow', 'limb', 'orn', 'cloth') and \
                    rune_bit(gi, gx % 4, yy % 8):
                return A[5], 0
            return None, 0.08 * math.sin(2 * math.pi * (p - T))
        if eff == 'crystal_glint':
            cell = _voronoi(t.pos[0] * 0.6, t.pos[1] * 0.45, t.pos[2] * 0.6, seed)
            cid = int(cell[0] * N)
            if cid == f:
                return WHITE if cell[1] > 0.1 else A[5], 0
            if (cid + 1) % N == f:
                return None, 0.25
            return None, 0.06 * math.sin(2 * math.pi * (p + cell[0]))
        if eff == 'ink_bleed':
            n = fbm(gx * 0.18, gy * 0.18, seed)
            r = 0.38 + 0.22 * math.sin(2 * math.pi * p)
            if n < r:
                return None, -0.45
            if r < 0.3 and rune_bit(int(h2(gx // 4, gy // 8, seed) * 8), gx % 4, gy % 8):
                return A[5], 0
            return None, 0.05
        if eff == 'sculk_pulse':
            vein = abs(fbm(gx * 0.22, gy * 0.22, seed + 4) - 0.5) < 0.07
            band = _gauss(_wrapd(T, p), 0.12)
            if vein:
                return (A[5] if band > 0.6 else A[4] if band > 0.25 else A[3]), 0
            return None, 0.15 * band
        if eff == 'spark_crackle':
            hh = h3(gx, gy, gz, f * 13 + seed)
            if hh > 0.965:
                return WHITE, 0
            if hh > 0.925:
                return A[4], 0
            return None, (h3(gx, gy, f, seed) - 0.5) * 0.12
        if eff == 'mercury_flow':
            off = h2(gx, 7, seed)
            c = 1 - ((p + off) % 1.0)
            d = T - c
            if 0 <= d < 0.05:
                return WHITE, 0
            if 0 <= d < 0.12:
                return None, 0.35
            return None, -0.02
        if eff == 'aurora_wave':
            w = math.sin(2 * math.pi * (T * 1.4 + S * 0.5 - p))
            green = A[4] if A[4][1] > A[4][0] else (110, 255, 180)
            pink = (255, 140, 215)
            band = mix(green, pink, (w + 1) / 2)
            return mix(base(t), band, 0.65), 0
        if eff == 'venom_drip':
            col = h2(gx, 3, seed)
            if col > 0.72:
                head = 1 - ((p * 1.0 + h2(gx, 4, seed)) % 1.0)
                if 0 <= T - head < 0.06:
                    return A[5], 0
                if 0 <= T - head < 0.16:
                    return A[4], 0
            return None, 0.22 * math.sin(2 * math.pi * (T * 2 - p))
        # ── 0.3.7 신화 6 (myth-037) ──
        if eff == 'geode_heart':
            # 태산: 갈라진 틈의 호박빛이 자루 → 머리로 한 바퀴(16프레임)에 걸쳐 차오르고, 결정 끝이 한 번씩 반짝
            if t.role in ('crystal', 'gem'):
                cell = _voronoi(t.pos[0] * 0.6, t.pos[1] * 0.45, t.pos[2] * 0.6, seed)
                cid = int(cell[0] * N)
                if cid == f and cell[1] > 0.1:
                    return WHITE, 0
                if (cid + 1) % N == f:
                    return None, 0.22
            level = p * 1.15
            if T <= level:
                front = _gauss(T - level, 0.07)
                if front > 0.7 and (gx + gy + gz) % 2 == 0:
                    return A[5], 0
                return None, 0.06 + 0.3 * front
            return None, -0.12
        if eff == 'tide_surge':
            # 만조: 밝은 물결 띠가 날 끝(+x) → 자루로 밀려왔다가 빠진다 (두 박자), 빠질 때 거품(빛나는 칸)이 반짝
            q = (2 * p) % 1.0
            c = 1.0 - 0.85 * math.sin(math.pi * q)
            X = (t.pos[0] - ctx.x0) / (ctx.x1 - ctx.x0)
            band = _gauss(X - c, 0.09)
            if q > 0.5 and t.role == 'glow' and h3(gx, gy, gz, f + seed) > 0.93:
                return WHITE, 0
            if band > 0.75 and (gx + gy) % 2 == 0:
                return lighten(ctx.top, 0.5), 0
            return None, 0.38 * band - 0.08
        if eff == 'comet_trail':
            # 꼬리별: 혜성 머리(손잡이 = 활의 가운데 높이)가 맥박치고, 밝은 띠가 머리에서 팔 끝으로 흘러가며
            # 주황 → 흰빛으로 식는다
            half = max(1e-3, (ctx.y1 - ctx.y0) / 2)
            Y = abs(t.pos[1] - ctx.cy) / half
            if Y < 0.12:
                return None, 0.3 * math.sin(2 * math.pi * p * 2)
            d = Y - p
            if abs(d) < 0.07:
                return mix(A[3], WHITE, clamp(p * 1.2)), 0
            if -0.22 < d < 0:
                return None, 0.18 * (1 + d / 0.22)
            return None, -0.05
        if eff == 'wisp_flicker':
            # 도깨비불: 등롱 속 불이 고르지 않게 깜빡이고(두 번 밝게, 한 번 꺼질 듯), 둘레 도깨비불('gem')은 프레임마다
            # 반짝이는 자리가 바뀐다
            if t.role == 'gem':
                if h3(gx, gy, gz, f * 7 + seed) > 0.8:
                    return A[5], 0
                return None, 0.12 * math.sin(2 * math.pi * (p + h2(gx, gy, seed)))
            k = int(p * len(FLICKER)) % len(FLICKER)
            return None, FLICKER[k] + (h3(gx, gy, f, seed + 5) - 0.5) * 0.12
        if eff == 'bell_toll':
            # 새벽 종: 종 입구(빛남 가운데 높이보다 위의 'gem' 테 중 가장 낮은 곳 — 손잡이 끝 보석은 빼고)에서 밝은
            # 고리가 위로 번져 오른다 — 한 번 크게, 두 번 작게, 쉬고
            m0 = ctx.anchor_above('gem')
            Ty = (t.pos[1] - m0) / max(1e-3, ctx.y1 - m0)
            sv = 0.0
            for t0, amp in TOLLS:
                age = p - t0
                if 0 <= age < 0.32:
                    sv = max(sv, amp * _gauss(Ty - age * 3.2, 0.08) * (1 - age / 0.32))
            if sv > 0.6:
                return (WHITE if sv > 0.85 else A[4]), 0
            return None, 0.45 * sv - 0.06
        if eff == 'moon_phase':
            # 그믐달: 안쪽 날('edge' + 빛남)의 밝은 곳이 끝 → 손잡이 → 끝으로 옮겨 가며 초승달 → 그믐 → 초승달,
            # 사슬 고리('gem')는 한 칸씩 반짝, 나머지(얼음·추·halo)는 천천히 숨쉰다
            if t.role == 'gem':
                if (gy // 2) % 6 == int(p * 12) % 6:
                    return WHITE, 0
                return None, -0.1
            if t.role == 'edge':
                e0, e1 = ctx.span(('edge',), 0)
                sx = (t.pos[0] - e0) / (e1 - e0)
                c = 0.5 + 0.5 * math.cos(2 * math.pi * p)
                lit = abs(math.cos(math.pi * p))
                b = _gauss(sx - c, 0.22) * lit
                if b > 0.7:
                    return WHITE, 0
                return None, 0.35 * b - 0.3 * (1 - lit) - 0.05
            return None, 0.1 * math.cos(2 * math.pi * p)
        return None

    return vfn


def animate(baked_or_texels, effect, frames, look, seed, frame_fn):
    """frame_fn(vfn)->Image.  Returns list of frames for the effect."""
    texels = baked_or_texels
    ctx = FxCtx(texels, look, frames, seed)
    out = [frame_fn(make_vfn(effect, ctx, f)) for f in range(frames)]
    if effect in FALLBACK and all(fr.tobytes() == out[0].tobytes() for fr in out[1:]):
        out = [frame_fn(make_vfn(FALLBACK[effect], ctx, f)) for f in range(frames)]
    return out
