"""
무기 3D 모델.

gen_pack.render_weapon 이 그린 32x32 무기 그림을 픽셀 재료(날, 등줄, 금속, 손잡이, 보석 ...)마다
다른 두께로 뽑아내 3D 로 만든다. 그 위에 두 가지 움직이는 효과를 얹는다.

- 무기 텍스처 자체의 반짝임: 날 끝과 보석이 손잡이에서 끝 쪽으로 빛이 훑고 지나간다 (애니메이션 텍스처).
- 아우라: 무기 앞뒤와 가운데에 반투명 판을 겹쳐 두고, 속성마다 다른 움직이는 빛을 그린다.
  불꽃은 끝 쪽으로 타오르고, 서리는 반짝이고, 번개는 튀고, 공허는 소용돌이친다.
  아우라 판은 light_emission 15 라 어두운 곳에서도 빛난다.

섬 초반(basic) 무기는 아우라가 없다. 얻기 어려운 무기일수록 아우라가 크고 진하다.
"""
import math
import zlib
import random

import numpy as np

from mc3d import Atlas, Model, extrude, hexc, mix, shade, hsv

# 픽셀 재료별 두께 (모델 단위, 1 = 1/16 블록). 32px 그림이라 한 픽셀은 0.5 단위
DEPTH = {"edge": 0.5, "blade": 1.0, "ridge": 1.5, "metal": 2.0, "grip": 1.5, "grip2": 1.75,
         "pommel": 2.25, "gem": 2.75, "orb": 3.0, "glowcore": 3.25}
LIGHT = {"gem": 10, "glowcore": 15, "orb": 9}
# 아우라가 피어오르는 부분 (손잡이 쪽은 빼서 손 주변이 지저분하지 않게)
FOCUS = {"edge", "blade", "ridge", "orb", "glowcore", "gem"}

# 얻는 곳별 아우라 세기: (반지름 px, 최대 불투명도, 반짝임 수)
AURA_LEVEL = {"island": (3.3, 215, 0), "frost": (4.2, 235, 4), "flame": (4.2, 235, 4), "void": (4.2, 235, 4),
              "boss": (4.8, 235, 7), "prism": (5.2, 235, 9)}

# 속성별 아우라: (방식, 안쪽 색, 바깥 색)
AURA = {
    "flame": ("flame", "#fff2a0", "#ff3d0a"),
    "sun": ("flame", "#ffffff", "#ffa51a"),
    "frost": ("frost", "#ffffff", "#5ac8ff"),
    "crystal": ("frost", "#fff0ff", "#b070ff"),
    "star": ("frost", "#ffffff", "#7a8aff"),
    "storm": ("bolt", "#fffbd0", "#8a7aff"),
    "venom": ("flame", "#e8ffa0", "#3a9a1a"),
    "ocean": ("wave", "#e0ffff", "#1a9ac0"),
    "earth": ("pulse", "#fff0b0", "#a0782a"),
    "wind": ("swirl", "#ffffff", "#8ad8c0"),
    "holy": ("pulse", "#ffffff", "#ffd84d"),
    "nature": ("pulse", "#f0ffd0", "#3fb03f"),
    "blood": ("drip", "#ffb0c0", "#b00a28"),
    "abyss": ("void", "#ffd0ff", "#7a1ae0"),
    "ender": ("void", "#d0fff4", "#14a08a"),
    "doom": ("void", "#ffb0c4", "#c00a3a"),
    "shadow": ("smoke", "#c8c8ff", "#1a1a34"),
    "bone": ("pulse", "#ffffff", "#c8c0a0"),
    "prism": ("prism", "#ffffff", "#ffffff"),
}
AURA_FRAMES = 16
# 스스로 빛나는 픽셀의 알파 표시 (pack/shaders 의 셰이더가 알아본다): 불투명 / 75% / 50%
GLOW, GLOW_SOFT, GLOW_HALF = 252, 251, 250

# 손에 들었을 때 크기 (바닐라 handheld 기준 배율)와 손에 쥐는 곳(축을 따라 잰 거리, px)
TYPE_SCALE = {"greatsword": 1.4, "scythe": 1.4, "hammer": 1.25, "spear": 1.35, "staff": 1.25,
              "axe": 1.18, "katana": 1.18, "sword": 1.08, "dagger": 0.95, "wand": 1.0}
GRIP_AT = {"sword": 5, "greatsword": 4.5, "dagger": 10, "katana": 5.5, "axe": 6, "hammer": 6, "spear": 8,
           "scythe": 8, "staff": 9, "wand": 9}


def _rot(rx, ry, rz):
    """마인크래프트 디스플레이 회전 (JOML rotationXYZ = Rx·Ry·Rz)."""
    def m(axis, deg):
        t = math.radians(deg)
        c, s_ = math.cos(t), math.sin(t)
        if axis == "x":
            return np.array([[1, 0, 0], [0, c, -s_], [0, s_, c]])
        if axis == "y":
            return np.array([[c, 0, s_], [0, 1, 0], [-s_, 0, c]])
        return np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
    return m("x", rx) @ m("y", ry) @ m("z", rz)


def _hold(rot, trans, s0, s1, grip):
    """크기를 s0 → s1 로 바꿔도 손잡이가 손에 그대로 있도록 위치를 보정한다."""
    g = np.array([grip[0] - 8, grip[1] - 8, 0.0])
    t = np.array(trans, dtype=float) + _rot(*rot) @ ((s0 - s1) * g)
    t = np.clip(t, -80, 80)
    return [round(float(v), 3) for v in t]


def _display(wtype):
    k = TYPE_SCALE.get(wtype, 1.0)
    k1 = 1 + (k - 1) * 0.45  # 1인칭은 화면을 너무 가리지 않게 덜 키운다
    grip = _axis_point(GRIP_AT.get(wtype, 5))
    tp, fp = round(0.85 * k, 3), round(0.68 * k1, 3)
    d = {}
    for name, rot, trans, s0, s1 in [
        ("thirdperson_righthand", [0, -90, 55], [0, 4.0, 0.5], 0.85, tp),
        ("thirdperson_lefthand", [0, 90, -55], [0, 4.0, 0.5], 0.85, tp),
        ("firstperson_righthand", [0, -90, 25], [1.13, 3.2, 1.13], 0.68, fp),
        ("firstperson_lefthand", [0, 90, -25], [1.13, 3.2, 1.13], 0.68, fp),
    ]:
        d[name] = {"rotation": rot, "translation": _hold(rot, trans, s0, s1, grip), "scale": [s1, s1, s1]}
    d.update({
        "ground": {"rotation": [0, 0, 0], "translation": [0, 2, 0], "scale": [0.5, 0.5, 0.5]},
        "gui": {"rotation": [0, 0, 0], "translation": [0, 0, 0], "scale": [1, 1, 1]},
        "head": {"rotation": [0, 180, 0], "translation": [0, 13, 7], "scale": [1, 1, 1]},
        "fixed": {"rotation": [0, 180, 0], "translation": [0, 0, 0], "scale": [1, 1, 1]},
    })
    return d


# ─────────────────────────── 잡음 ───────────────────────────

class Noise:
    """u 방향으로 주기(period)가 있는 값 잡음. 시간에 따라 u 를 한 주기 밀면 애니메이션이 끊김 없이 돈다."""

    def __init__(self, seed, period=8, rows=16):
        r = random.Random(seed)
        self.p, self.rows = period, rows
        self.g = [[r.random() for _ in range(period)] for _ in range(rows)]

    def __call__(self, u, v):
        u %= self.p
        v %= self.rows
        i0, j0 = int(u), int(v)
        fu, fv = u - i0, v - j0
        i0, j0 = i0 % self.p, j0 % self.rows  # 아주 작은 음수의 나머지가 주기와 같아지는 경우
        i1, j1 = (i0 + 1) % self.p, (j0 + 1) % self.rows
        fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
        a = self.g[j0][i0] + (self.g[j0][i1] - self.g[j0][i0]) * fu
        b = self.g[j1][i0] + (self.g[j1][i1] - self.g[j1][i0]) * fu
        return a + (b - a) * fv


def _fbm(n1, n2, u, v):
    return 0.65 * n1(u, v) + 0.35 * n2(u * 2, v * 2)


# ─────────────────────────── 무기 텍스처 (반짝임) ───────────────────────────

def weapon_frames(base, mats, element, pool, frames):
    """날 끝/보석이 손잡이 → 끝으로 빛이 훑고 지나가는 프레임들."""
    out = []
    emissive = pool in ("frost", "flame", "void", "boss", "prism")
    amp = {"island": 0.28, "frost": 0.42, "flame": 0.42, "void": 0.42, "boss": 0.55, "prism": 0.6}.get(pool, 0)
    for k in range(frames):
        img = base.copy()
        if amp > 0:
            pos = -8 + 52 * k / frames
            for (x, y), (m, l, s) in mats.items():
                if m not in ("edge", "ridge", "glowcore", "gem", "orb"):
                    continue
                c = img.getpixel((x, y))
                if element == "prism" and m in ("edge", "ridge", "orb", "glowcore"):
                    import colorsys
                    h, sat, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
                    r, g, b = colorsys.hsv_to_rgb((h + k / frames) % 1.0, sat, v)
                    c = (int(r * 255), int(g * 255), int(b * 255), 255)
                f = amp * math.exp(-((l - pos) / 3.2) ** 2)
                if m == "glowcore":
                    f += 0.25 * (0.5 + 0.5 * math.sin(2 * math.pi * k / frames))
                c = shade(c, 1 + f) if f > 0 else c
                if emissive and m in ("edge", "glowcore", "gem", "orb"):
                    c = (c[0], c[1], c[2], GLOW)
                img.putpixel((x, y), c)
        out.append(img)
    return out


# ─────────────────────────── 아우라 텍스처 ───────────────────────────

def aura_frames(mats, outline, element, pool, wtype, seed):
    from gen_pack import to_ls  # 순환 참조를 피하려고 여기서
    style, core_hex, outer_hex = AURA.get(element, ("pulse", "#ffffff", "#c0c0c0"))
    radius, amax, nspark = AURA_LEVEL[pool]
    core, outer = hexc(core_hex), hexc(outer_hex)
    S = 32
    focus = [(x, y) for (x, y), (m, _, _) in mats.items() if m in FOCUS]
    if not focus:
        focus = list(mats.keys())
    fx = np.array([p[0] for p in focus], dtype=float)
    fy = np.array([p[1] for p in focus], dtype=float)
    solid = set(mats.keys()) | set(outline)
    D = np.zeros((S, S))
    L = np.zeros((S, S))
    Sx = np.zeros((S, S))
    for y in range(S):
        for x in range(S):
            D[y, x] = float(np.min(np.hypot(fx - x, fy - y)))
            L[y, x], Sx[y, x] = to_ls(x, y)
    rnd = random.Random(seed)
    n1, n2 = Noise(seed), Noise(seed + 1)
    # 반짝임 위치 (아우라 안쪽)
    near = [(x, y) for y in range(S) for x in range(S) if 0.5 < D[y, x] <= radius - 0.5]
    rnd.shuffle(near)
    sparks = [(x, y, rnd.random()) for (x, y) in near[: nspark + (6 if style in ("frost", "void") else 0)]]
    frames = []
    from PIL import Image
    for k in range(AURA_FRAMES):
        t = k / AURA_FRAMES
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        px = img.load()
        for y in range(S):
            for x in range(S):
                d, l, s = D[y, x], L[y, x], Sx[y, x]
                if d > radius * 1.3:
                    continue
                inside = (x, y) in solid
                tip = 0.55 + 0.45 * min(1.0, max(0.0, l / 34))
                # reach: 그 자리에서 빛(불꽃)이 뻗는 길이. 잡음으로 흔들려 혀처럼 날름거린다
                if style == "flame":
                    n = _fbm(n1, n2, l * 0.28 - t * 8, s * 0.7)
                    reach = radius * tip * (0.25 + 1.05 * n)
                elif style == "frost":
                    reach = radius * (0.62 + 0.25 * math.sin(2 * math.pi * (t + l / 18)))
                elif style == "bolt":
                    reach = radius * (0.5 + 0.25 * n1(l * 0.3 + t * 8, s))
                elif style == "wave":
                    wv = 0.5 + 0.5 * math.sin(2 * math.pi * (l / 11 - t * 2) + s * 0.6)
                    reach = radius * tip * (0.3 + 0.8 * wv)
                elif style == "swirl":
                    n = _fbm(n1, n2, l * 0.35 - t * 16, s * 0.9 + l * 0.2)
                    reach = radius * (0.15 + 1.2 * n * n)
                elif style == "drip":
                    n = _fbm(n1, n2, l * 0.3 + t * 8, s * 0.8)
                    reach = radius * (0.25 + 0.95 * n)
                elif style == "void":
                    n = _fbm(n1, n2, l * 0.25 - t * 8 + math.sin(s * 0.8) * 0.8, s * 0.6 + t * 4)
                    reach = radius * tip * (0.25 + 1.05 * n)
                elif style == "smoke":
                    n = _fbm(n1, n2, l * 0.22 - t * 8, s * 0.5)
                    reach = radius * (0.3 + 0.95 * n)
                elif style == "prism":
                    n = _fbm(n1, n2, l * 0.3 - t * 8, s * 0.7)
                    reach = radius * tip * (0.4 + 0.8 * n)
                else:  # pulse
                    reach = radius * tip * (0.65 + 0.35 * math.sin(2 * math.pi * t + l * 0.15))
                if reach <= 0.3:
                    continue
                inten = max(0.0, 1 - d / reach)
                if style == "prism":
                    col = hsv(l / 30 + t + d * 0.05, 0.55, 1.0)
                elif style == "smoke":
                    col = mix(outer, core, inten * 0.7)
                else:
                    col = mix(outer, core, inten ** 1.2)
                if inside:
                    continue  # 무기 위는 덮지 않는다
                # 마인크래프트 그림처럼 또렷하게: 세 단계로만 칠한다
                # 알파 252/251 = 셰이더가 조명 없이 스스로 빛나게 그리는 픽셀 (pack/shaders)
                if inten > 0.6:
                    c2, a = mix(col, core, 0.5), GLOW
                elif inten > 0.3:
                    c2, a = col, GLOW
                elif inten > 0.04:
                    c2, a = mix(col, outer, 0.5), GLOW_SOFT
                else:
                    continue
                px[x, y] = (c2[0], c2[1], c2[2], a)
        # 반짝임
        for (x, y, ph) in sparks:
            b = max(0.0, math.sin(2 * math.pi * (t * 2 + ph))) ** 4
            if b > 0.15:
                c = (255, 255, 255) if style != "prism" else hsv(ph + t, 0.4, 1.0)[:3]
                px[x, y] = (c[0], c[1], c[2], GLOW if b > 0.5 else GLOW_SOFT)
        # 번개: 프레임마다 다른 곳에서 튄다
        if style == "bolt":
            br = random.Random(seed * 100 + k)
            edge = [(x, y) for (x, y) in focus if mats[(x, y)][0] in ("edge", "orb", "glowcore")] or focus
            for _ in range(2 if pool in ("island",) else 3):
                x, y = br.choice(edge)
                dx, dy = br.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, -1), (1, 1), (-1, 1)])
                for step in range(br.randint(3, 6)):
                    x += dx if br.random() < 0.7 else 0
                    y += dy if br.random() < 0.7 else br.choice((-1, 1))
                    if not (0 <= x < S and 0 <= y < S):
                        break
                    px[x, y] = (core[0], core[1], core[2], GLOW if step < 4 else GLOW_SOFT)
        frames.append(img)
    return frames, style != "bolt"


# ─────────────────────────── 마법진 고리 ───────────────────────────

# 무기 종류별로 고리를 두를 자리 (손잡이 끝에서 축을 따라 잰 거리, px)
RING_AT = {"sword": [17, 27], "greatsword": [15, 25], "dagger": [19, 24], "katana": [19, 28], "axe": [17, 13],
           "hammer": [22, 16], "spear": [21, 30], "scythe": [24, 18], "staff": [31.5, 25], "wand": [28, 22]}
RING_COUNT = {"frost": 1, "flame": 1, "void": 1, "boss": 2, "prism": 2}


def ring_frames(element, pool, seed):
    """천천히 도는 룬 고리 (8방향 대칭이라 45도 돌면 처음과 같아져 끊김 없이 돈다)."""
    from PIL import Image
    style, core_hex, outer_hex = AURA.get(element, ("pulse", "#ffffff", "#c0c0c0"))
    core, outer = hexc(core_hex), hexc(outer_hex)
    r = random.Random(seed)
    # 45도 한 칸 안의 룬 무늬: (시작각, 끝각, 안쪽 반지름, 바깥 반지름)
    marks = []
    a = 2.0
    while a < 43:
        wdt = r.choice([2.5, 4, 6, 9])
        if a + wdt > 43:
            break
        kind = r.random()
        if kind < 0.45:
            marks.append((a, a + wdt, 11.4, 13.6))
        elif kind < 0.75:
            marks.append((a, a + wdt * 0.5, 11.4, 12.4))
            marks.append((a + wdt * 0.5, a + wdt, 12.6, 13.6))
        else:
            marks.append((a, a + 1.5, 10.8, 14.2))
        a += wdt + r.choice([1.5, 2.5, 3.5])
    frames = []
    N, SS = AURA_FRAMES, 3
    for k in range(N):
        rot = 45.0 * k / N
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        px = img.load()
        for y in range(32):
            for x in range(32):
                acc = [0.0, 0.0]  # (밝기 가중 합, 덮인 비율)
                for sy in range(SS):
                    for sx in range(SS):
                        dx = x + (sx + 0.5) / SS - 16
                        dy = y + (sy + 0.5) / SS - 16
                        rr = math.hypot(dx, dy)
                        th = (math.degrees(math.atan2(dy, dx)) - rot) % 45.0
                        v = 0.0
                        if 14.6 <= rr <= 15.4:
                            v = 0.9
                        elif 9.8 <= rr <= 10.4:
                            v = 0.6
                        else:
                            for (a0, a1, r0, r1) in marks:
                                if a0 <= th <= a1 and r0 <= rr <= r1:
                                    v = 1.0
                                    break
                        acc[0] += v
                cov = acc[0] / (SS * SS)
                if cov <= 0.02:
                    continue
                if style == "prism":
                    c = hsv((math.atan2(y - 16, x - 16) / (2 * math.pi)) + k / N, 0.5, 1.0)
                else:
                    c = mix(outer, core, 0.55 + 0.45 * cov)
                if cov < 0.15:
                    continue
                px[x, y] = (c[0], c[1], c[2], GLOW if cov > 0.45 else GLOW_HALF)
        frames.append(img)
    return frames


def _axis_point(l):
    from gen_pack import AX0, U
    x = AX0[0] + U[0] * l
    y = AX0[1] + U[1] * l
    return x * 0.5, (32 - y) * 0.5  # 모델 좌표 (그림 아래쪽이 y 가 작다)


# ─────────────────────────── 모델 ───────────────────────────

def build_weapon(wid, w, assets_root, look_of_pool):
    """무기 하나의 3D 모델, 텍스처, 아이템 정의를 쓴다. (모델 이름 item/<wid>, 미리보기용 Model 을 돌려준다)"""
    import gen_pack as gp
    pool = w.get("pool", "basic")
    element = w.get("element", "iron")
    wtype = w.get("type", "sword")
    look = w.get("look", look_of_pool.get(pool, 0))
    layers = {}
    base = gp.render_weapon(wtype, element, look, wid, halo=False, layers=layers)
    mats, outline = layers["mats"], layers["outline"]

    nfr = 1 if pool == "basic" else 12
    atlas = Atlas("item/" + wid, size=32, frames=nfr, frametime=2, interpolate=True)
    reg = atlas.alloc(32, 32)
    for k, fr in enumerate(weapon_frames(base, mats, element, pool, nfr)):
        reg.paste(fr, k)

    m = Model("item/" + wid)
    m.use("w", atlas)

    def depth_of(x, y):
        if (x, y) in mats:
            return DEPTH.get(mats[(x, y)][0], 1.0)
        # 외곽선: 붙어 있는 재료 중 가장 얇은 두께
        ds = [DEPTH.get(mats[(x + dx, y + dy)][0], 1.0) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (x + dx, y + dy) in mats]
        return min(ds) if ds else 0.5

    edge_glow = {"basic": 0, "island": 6}.get(pool, 12)

    def light_of(x, y):
        if (x, y) in mats:
            m_ = mats[(x, y)][0]
            if m_ == "edge":
                return edge_glow
            return LIGHT.get(m_, 0)
        return 0

    extrude(m, "w", reg, base, depth_of, px=0.5, origin=(0.0, 0.0), zc=8.0, light_of=light_of)

    aura = None
    if pool != "basic":
        frames, interp = aura_frames(mats, outline, element, pool, wtype, zlib.crc32(wid.encode()) % 100000)
        # 또렷한 픽셀 불꽃이 흐려지지 않게 프레임 사이를 섞지 않는다
        aura = Atlas("item/" + wid + "_aura", size=32, frames=AURA_FRAMES, frametime=2, interpolate=False)
        ar = aura.alloc(32, 32)
        for k, fr in enumerate(frames):
            ar.paste(fr, k)
        m.use("a", aura)
        full = [0, 0, 16, 16]
        maxd = max(DEPTH.get(v[0], 1.0) for v in mats.values())
        zf, zb = 8 + maxd / 2 + 0.3, 8 - maxd / 2 - 0.3
        both = {"south": ("a", full), "north": ("a", [16, 0, 0, 16])}
        m.box((0, 0, zf), (16, 16, zf), both, light=15, shade=False)
        m.box((0, 0, zb), (16, 16, zb), both, light=15, shade=False)

    rings = None
    nring = RING_COUNT.get(pool, 0)
    if nring:
        rings = Atlas("item/" + wid + "_ring", size=32, frames=AURA_FRAMES, frametime=2, interpolate=True)
        rr = rings.alloc(32, 32)
        for k, fr in enumerate(ring_frames(element, pool, zlib.crc32(wid.encode()) % 100000)):
            rr.paste(fr, k)
        m.use("r", rings)
        for i, l in enumerate(RING_AT.get(wtype, [18, 26])[:nring]):
            cx, cy = _axis_point(l)
            half = (3.6 if wtype in ("staff", "wand", "hammer") else 3.1) * (1.0 if i == 0 else 0.8)
            face = {"up": ("r", [0, 0, 16, 16]), "down": ("r", [0, 16, 16, 0])}
            # 수평 판을 z 축으로 -45도 기울이면 판의 법선이 무기 축(오른쪽 위)과 나란해진다
            m.box((cx - half, cy, 8 - half), (cx + half, cy, 8 + half), face, light=15, shade=False,
                  rotation={"origin": [round(cx, 4), round(cy, 4), 8], "axis": "z", "angle": -45})

    m.display = _display(wtype)
    tex_root = assets_root + "/textures"
    atlas.save(tex_root)
    if aura:
        aura.save(tex_root)
    if rings:
        rings.save(tex_root)
    m.write(assets_root)
    return m, base, (aura.frame0() if aura else None)
