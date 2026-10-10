"""
heavy_blades: 단검과 대검 13 자루.

python3 heavy_blades.py            -> preview/heavy_blades.png
python3 heavy_blades.py id1 id2    -> 그 무기만 _scratch 미리보기
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, Weapon, preview_sheet  # noqa: E402


# ─────────────────────────── 작은 도구 ───────────────────────────

def poly(pts):
    """XY 다각형 마스크 (짝홀 규칙)."""
    P = np.array(pts, float)

    def m(X, Y):
        inside = np.zeros(np.shape(X), bool)
        for i in range(len(P)):
            x1, y1 = P[i]
            x2, y2 = P[(i + 1) % len(P)]
            if y1 == y2:
                continue
            cond = (y1 > Y) != (y2 > Y)
            xi = (x2 - x1) * (Y - y1) / (y2 - y1) + x1
            inside ^= cond & (X < xi)
        return inside
    return m


def disc(w, cx, cy, r, hz, mat, cz=0.0):
    """앞을 보는 원판 (XY 평면)."""
    return w.fill(lambda X, Y, Z: (np.hypot(X - cx, Y - cy) <= r) & (np.abs(Z - cz) <= hz), mat)


def helix(w, y0, y1, R, turns, r, mat, phase=0.0, cx=0.0):
    """손잡이를 감는 나선 (끈, 뱀, 코일)."""
    pts = []
    n = int(turns * 16) + 2
    for i in range(n + 1):
        t = i / n
        a = phase + t * turns * 2 * math.pi
        pts.append((cx + R * math.cos(a), y0 + (y1 - y0) * t, R * math.sin(a)))
    return w.tube(pts, r, mat)


def rot180(w, y_mid):
    """Z 축으로 180도 돌린 사본을 빈 칸에 더한다 (y_mid 기준). 쌍검용."""
    g = w.grid
    H = g.shape[1]
    shift = int(round(2 * y_mid)) - H        # Y -> 2*y_mid - Y
    g2 = g[::-1, ::-1, :]
    g2 = np.roll(g2, shift, axis=1)
    if shift > 0:
        g2[:, :shift, :] = 0
    elif shift < 0:
        g2[:, shift:, :] = 0
    w.grid = np.where(g > 0, g, g2).astype(g.dtype)
    return w



def paint_obsidian(w, h, seed):
    """숯빛-진홍 유리 흑요석 (보라 X). 대각 광택 + 드문 주황 불티."""
    rng = np.random.default_rng(seed)
    v = fbm(w, h, rng, ((6, .6), (3, .4)))
    lo, hi = np.array(_hx("#0a0606"), float), np.array(_hx("#2a1210"), float)
    rgb = lo + (hi - lo) * v[..., None]
    ys, xs = np.mgrid[0:h, 0:w]
    sheen = np.clip(1 - np.abs(((xs + ys) % 12) - 3) / 2.0, 0, 1)  # 대각 광택
    rgb += sheen[..., None] * np.array([50, 20, 10])
    gl = rng.random((h, w)) < 0.03
    rgb[gl] = _hx("#ff7a2a")
    return to_img(rgb)


def paint_horn(w, h, seed):
    """뿔/엄니: 아래(밑동) 숯빛 흑요석 → 위로 갈수록 붉게 달아오름 + 고리 마디.
    세 마디가 v 범위를 나눠 쓰므로 전체가 한 줄기 그라데이션이 된다."""
    rng = np.random.default_rng(seed)
    ys, xs = np.mgrid[0:h, 0:w]
    t = 1 - ys / (h - 1)  # 위가 1
    base = np.array(_hx("#120807"), float) + np.array([30, 10, 6]) * (xs % 5 == 2)[..., None]  # 결
    k = np.clip((t - 0.50) / 0.50, 0, 1)[..., None]                   # 위쪽 50% 가 달아오름
    rgb = base * (1 - k) + palette(0.28 + 0.62 * k[..., 0] ** 1.3) * k
    ring = (ys % 6) == 0
    rgb[ring] *= 0.55
    ridge = (xs == 1) | (xs == w // 2)
    rgb[ridge] = rgb[ridge] * 1.3 + 8
    rgb *= (0.9 + 0.2 * rng.random((h, w)))[..., None]
    return to_img(rgb)

# ─────────────────────────────── 애니메이션 용암/불꽃 텍스처 ───────────────────────────────

def lava_frame(w, h, f, bright=0.0):
    """흐르는 용암. 공간/시간 모두 주기적이라 프레임이 끊김 없이 반복된다."""
    t = 2 * math.pi * f / NF
    ys, xs = np.mgrid[0:h, 0:w]
    u, v = 2 * math.pi * xs / w, 2 * math.pi * ys / h
    warp = 0.9 * np.sin(u + 2 * v - t) + 0.5 * np.sin(3 * u - v + t)
    r1 = 1 - np.abs(np.sin(2 * u + warp + 0.5 * np.sin(2 * v - t)))
    r2 = 1 - np.abs(np.sin(3 * v - u + 1.3 * warp - 2 * t))
    base = 0.5 + 0.25 * np.sin(u + 3 * v - t) * np.cos(2 * u - v + t)
    val = 0.22 + 0.55 * np.maximum(r1 ** 4, r2 ** 5) + 0.30 * base + bright
    return to_img(palette(val))


def core_frame(w, h, f):
    """가슴 코어: 백열 중심이 맥동, 소용돌이 광선."""
    t = 2 * math.pi * f / NF
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    dx, dy = (xs - w / 2) / (w / 2), (ys - h / 2) / (h / 2)
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)
    pulse = 0.5 + 0.5 * math.sin(t)
    val = 1.08 - r * (0.75 - 0.2 * pulse) + 0.12 * np.sin(5 * ang + 3 * r * 4 - t) * r
    val += 0.06 * np.sin(2 * t) * (1 - r)
    rgb = palette(val)
    rim = (np.maximum(np.abs(dx), np.abs(dy)) > 0.86)
    rgb[rim] = rgb[rim] * 0.6
    return to_img(rgb)


def eye_frame(w, h, f):
    t = 2 * math.pi * f / NF
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    dx, dy = (xs - w / 2) / (w / 2), (ys - h / 2) / (h / 2)
    r = np.sqrt(dx * dx * 0.6 + dy * dy)
    val = 1.05 - 0.45 * r + 0.06 * math.sin(3 * t) + 0.04 * np.sin(4 * xs - 2 * t)
    return to_img(palette(val))


def flame_frame(w, h, f, tongues=3, seed=0):
    """
    불꽃 혀: 아래가 백열, 위로 갈수록 주황→빨강, 바깥은 투명.
    시간 성분이 정수배라 루프가 매끄럽다.
    """
    t = 2 * math.pi * f / NF
    rnd = random.Random(seed)
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    nx = xs / w * 2 - 1           # -1..1
    ny = 1 - ys / h               # 아래 0 → 위 1
    shape = np.zeros_like(nx)
    for k in range(tongues):
        c = (k + 0.5) / tongues * 1.7 - 0.85 + rnd.uniform(-.1, .1)
        hgt = 0.62 + 0.3 * (1 - abs(c)) + 0.12 * math.sin(t * (1 + k % 2) + k * 2.1)
        wid = 0.32 + 0.08 * math.sin(t + k)
        sway = 0.12 * math.sin(t + k * 1.7) * ny
        shape = np.maximum(shape, hgt * np.exp(-((nx - c - sway) / wid) ** 2))
    turb = 0.10 * np.sin(6 * nx + 7 * ny * 3.14 - 2 * t) + 0.07 * np.sin(11 * nx - 9 * ny * 3.14 - 3 * t)
    inten = shape - ny + turb * ny
    vis = inten > 0
    val = np.clip(0.36 + inten * 0.95 + (1 - ny) ** 2 * 0.22, 0, 1)
    rgb = palette(val)
    alpha = np.where(vis, 255, 0).astype(float)
    # 위로 튀는 불씨
    for k in range(5):
        ex = int((rnd.random() * w + 3 * math.sin(t + k)) % w)
        ey = int(((rnd.random() - f / NF * 2) % 1.0) * h * 0.45)
        if 0 <= ey < h:
            rgb[ey, ex] = _hx("#ffd04a")
            alpha[ey, ex] = 255
    return to_img(rgb, alpha)


# ─────────────────────────────── 아틀라스 구성 ───────────────────────────────

def make_atlases():
    rock = Atlas(f"boss/{BOSS}", size=128, frames=1)
    lava = Atlas(f"boss/{BOSS}_lava", size=64, frames=NF, frametime=3, interpolate=True)
    R = {}

    def put_static(name, img):
        reg = rock.alloc(*img.size)
        reg.paste(img)
        R[name] = ("r", reg)

    # 바위 (32x32 이 기본 크기). 차가운 청회색 현무암이 유일한 '차가운' 색.
    put_static("basalt", paint_basalt(32, 32, 11, base=("#141319", "#45404c"), n_cells=6))
    put_static("basalt2", paint_basalt(32, 32, 12, base=("#1a181f", "#544e5a"), n_cells=9, warm=0.012))
    put_static("hot", paint_basalt(32, 32, 13, base=("#1e1412", "#4a3530"), hot=1.0, n_cells=8))
    put_static("obsidian", paint_obsidian(32, 32, 14))
    put_static("dark", paint_basalt(32, 32, 15, base=("#0d0c10", "#28252d"), n_cells=5))
    put_static("horn", paint_horn(16, 32, 17))

    def put_anim(name, w, h, fn):
        reg = lava.alloc(w, h)
        for f in range(NF):
            reg.paste(fn(w, h, f), frame=f)
        R[name] = ("l", reg)

    put_anim("lava", 32, 32, lava_frame)
    put_anim("flame", 16, 32, lambda w, h, f: flame_frame(w, h, f, 3, 1))
    put_anim("core", 16, 16, core_frame)
    put_anim("ember", 16, 16, lambda w, h, f: lava_frame(w, h, f, bright=0.16))
    put_anim("flame_big", 32, 32, lambda w, h, f: flame_frame(w, h, f, 4, 2))
    put_anim("eye", 8, 8, eye_frame)
    return rock, lava, R


# 발광 재질은 light 15, 나머지는 0 (어중간한 6 같은 값은 쓰지 않는다)
GLOW = {"lava", "core", "ember", "eye", "flame", "flame_big"}


class Builder:
    """모델에 '재질' 이름으로 박스를 쌓는다. 면마다 텍셀 밀도가 일정하도록 UV 를 잘라 쓴다."""

    def __init__(self, name, atlases, regs, dens, seed=0):
        self.m = Model(name)
        rock, lava = atlases
        self.m.use("r", rock)
        self.m.use("l", lava)
        self.R = regs
        self.dens = dens
        self.rng = random.Random(seed)

    def _uv(self, reg, a, b):
        pw = min(reg.w, max(1.0, a * self.dens))
        ph = min(reg.h, max(1.0, b * self.dens))
        ox = self.rng.uniform(0, reg.w - pw)
        oy = self.rng.uniform(0, reg.h - ph)
        return reg.uv(sub=(ox, oy, ox + pw, oy + ph))

    def box(self, frm, to, mat_, rot=None, faces=FACES, full=False, vrange=None):
        """rot = (axis, angle[, origin]). vrange=(v0,v1) 이면 모든 면이 그 세로 구간을 쓴다 (뿔 그라데이션)."""
        key, reg = self.R[mat_]
        light = 15 if mat_ in GLOW else 0
        dx, dy, dz = (abs(to[i] - frm[i]) for i in range(3))
        dims = {"north": (dx, dy), "south": (dx, dy), "east": (dz, dy), "west": (dz, dy),
                "up": (dx, dz), "down": (dx, dz)}
        fd = {}
        for f in faces:
            if vrange:
                fd[f] = (key, reg.uv(sub=(0, vrange[0] * reg.h, reg.w, vrange[1] * reg.h)))
            else:
                fd[f] = (key, reg.uv() if full else self._uv(reg, *dims[f]))
        rotation = None
        if rot:
            axis, ang = rot[0], rot[1]
            origin = rot[2] if len(rot) > 2 and rot[2] is not None else [(frm[i] + to[i]) / 2 for i in range(3)]
            rotation = {"origin": [round(o, 4) for o in origin], "axis": axis, "angle": ang}
        return self.m.box(frm, to, fd, light=light, rotation=rotation, shade=light < 8)

    def crack(self, pts, face, w0=1.0, w1=0.4, depth=0.35, mat_="ember", axis="z"):
        """빛나는 용암 균열. pts 를 잇는 토막(가로/세로/45도)으로 만들고 폭이 w0→w1 로 가늘어진다.
        axis="z": 앞/뒷면(face=z) 위의 (x,y) 점. axis="x": 옆면(face=x) 위의 (z,y) 점."""
        sgn = 1 if face > 8 else -1
        lo, hi = sorted((face - 0.05 * sgn, face + depth * sgn))
        n = len(pts) - 1
        for i, (p0, p1) in enumerate(zip(pts, pts[1:])):
            w = w0 + (w1 - w0) * (i / (n - 1) if n > 1 else 0.0)
            da, db = p1[0] - p0[0], p1[1] - p0[1]
            L = math.hypot(da, db)
            if L < 1e-6:
                continue
            ang = round(math.degrees(math.atan2(db, da)), 3)
            if ang >= 90:
                ang -= 180
            if ang < -90:
                ang += 180
            ma, mb = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            half = L / 2 + w * 0.45                         # 이음매가 비지 않게 살짝 겹침
            if abs(abs(ang) - 90) < 1e-3:
                ra, rb, r_ang = (ma - w / 2, ma + w / 2), (mb - half, mb + half), 0
            elif abs(ang) < 1e-3 or abs(abs(ang) - 45) < 1e-3:
                ra, rb, r_ang = (ma - half, ma + half), (mb - w / 2, mb + w / 2), ang
            else:
                raise ValueError(f"crack 토막 각도 {ang} 는 0/45/90 만 됩니다")
            if axis == "z":
                frm, to = (ra[0], rb[0], lo), (ra[1], rb[1], hi)
                rot = ("z", r_ang, (ma, mb, (lo + hi) / 2)) if r_ang else None
            else:
                frm, to = (lo, rb[0], ra[0]), (hi, rb[1], ra[1])
                rot = ("x", -r_ang, ((lo + hi) / 2, mb, ma)) if r_ang else None
            self.box(frm, to, mat_, rot=rot)

    def flame(self, cx, cz, y0, y1, w, mat_="flame_big", diag=True):
        """십자 불꽃 평면 2장 (대각선으로 돌려 어느 방향에서나 보이게)."""
        key, reg = self.R[mat_]
        hw = w / 2
        rot = {"origin": [cx, y0, cz], "axis": "y", "angle": 45 if diag else 0}
        for plane in ("z", "x"):
            if plane == "z":
                frm, to = (cx - hw, y0, cz), (cx + hw, y1, cz)
                fd = {"north": (key, reg.uv()), "south": (key, reg.uv())}
            else:
                frm, to = (cx, y0, cz - hw), (cx, y1, cz + hw)
                fd = {"east": (key, reg.uv()), "west": (key, reg.uv())}
            self.m.box(frm, to, fd, light=15, shade=False, rotation=dict(rot) if diag else None)

    def flame_tilt(self, cx, cy, cz, length, w, angle=-45, mat_="flame_big"):
        """x 축으로 기울인 십자 불꽃 (angle<0 → 뒤(-z)로 눕는 혜성 꼬리)."""
        key, reg = self.R[mat_]
        hw = w / 2
        rot = {"origin": [cx, cy, cz], "axis": "x", "angle": angle}
        self.m.box((cx - hw, cy, cz), (cx + hw, cy + length, cz),
                   {"north": (key, reg.uv()), "south": (key, reg.uv())}, light=15, shade=False, rotation=dict(rot))
        self.m.box((cx, cy, cz - hw), (cx, cy + length, cz + hw),
                   {"east": (key, reg.uv()), "west": (key, reg.uv())}, light=15, shade=False, rotation=dict(rot))


def mbox(b, mir, frm, to, m, rot=None, **kw):
    """x=8 기준 거울상 박스 (mir=True 면 뒤집는다). y/z 축 회전은 각도 부호도 뒤집는다."""
    if mir:
        frm, to = (16 - to[0], frm[1], frm[2]), (16 - frm[0], to[1], to[2])
        if rot:
            ax, ang = rot[0], rot[1]
            o = rot[2] if len(rot) > 2 else None
            if ax in ("y", "z"):
                ang = -ang
            if o is not None:
                o = (16 - o[0], o[1], o[2])
            rot = (ax, ang, o)
    return b.box(frm, to, m, rot=rot, **kw)


def _rot(axis, deg, v):
    from mc3d import _rot_matrix
    return _rot_matrix(axis, deg) @ np.array(v, dtype=float)


# ─────────────────────────────── 파트 모델 ───────────────────────────────

CORE_C = (8.0, 7.2)  # 가슴 코어 중심 (x, y)


def build_torso(at, R):
    """scale 2.0 (1칸 = 0.125블록). 피벗 (8,8,8) = 가슴 중심. 리그에서 8도 앞으로 숙인다."""
    b = Builder(f"boss/{BOSS}_torso", at, R, dens=2.0, seed=1)
    cx, cy = CORE_C
    # ── 안쪽 용암 몸통 (판 사이 틈으로만 보인다; 앞면은 소켓 바닥보다 뒤) ──
    b.box((1.2, 3.4, 4.2), (14.8, 16.8, 11.6), "lava")
    b.box((3.6, -1.6, 5.0), (12.4, 3.6, 11.0), "lava")
    # ── 가슴판 2장 (가운데 세로 용암 이음매) + 앞 돌출판 ──
    for mir in (False, True):
        mbox(b, mir, (0.4, 11.0, 3.0), (7.6, 17.2, 13.8), "basalt")
        mbox(b, mir, (1.2, 11.2, 13.6), (7.5, 16.4, 14.6), "basalt2")
        # 옆구리 덩이 (코어 양옆)
        mbox(b, mir, (0.6, 3.4, 3.4), (4.4, 10.8, 13.4), "basalt2")
        # 등 쪽 옆구리 판
        mbox(b, mir, (1.0, 3.6, 2.8), (6.8, 10.6, 3.6), "dark")
    # ── 코어 소켓: 어두운 바닥 + 8각 별(22.5도 엇갈린 두 사각) + 다이아몬드 코어 ──
    b.box((4.4, 3.2, 10.8), (11.6, 11.2, 11.8), "dark")
    for a in (22.5, -22.5):
        b.box((cx - 3.0, cy - 3.0, 11.6), (cx + 3.0, cy + 3.0, 12.8), "ember", rot=("z", a, (cx, cy, 12.2)))
    b.box((cx - 2.6, cy - 2.6, 12.0), (cx + 2.6, cy + 2.6, 15.0), "core", rot=("z", 45, (cx, cy, 13.5)))
    # 코어로 모여드는 흑요석 발톱 4개 (대각선) + 달아오른 발톱 끝
    for (sx, sy) in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        ang = 45 if sx * sy > 0 else -45
        d = 5.6 / math.sqrt(2)
        mx, my = cx + sx * d, cy + sy * d
        b.box((mx - 2.4, my - 0.9, 13.2), (mx + 2.4, my + 0.9, 15.0), "obsidian", rot=("z", ang, (mx, my, 14.1)))
        d2 = 3.2 / math.sqrt(2)
        tx, ty = cx + sx * d2, cy + sy * d2
        b.box((tx - 0.7, ty - 0.5, 13.6), (tx + 0.7, ty + 0.5, 15.2), "ember", rot=("z", ang, (tx, ty, 14.4)))
    # ── 코어 끝(위/아래/좌/우)에서 뻗어 나가는 용암 균열 (폭 1.0 → 0.4, 45도 토막 섞음) ──
    for mir in (False, True):
        def m(x):
            return 16 - x if mir else x
        # 위 끝 → 가슴판으로 Y 자
        b.crack([(m(7.2), 11.6), (m(5.8), 13.0), (m(5.8), 14.2), (m(4.0), 16.0)], 14.6)
        b.crack([(m(5.8), 13.6), (m(3.0), 13.6), (m(1.8), 14.8)], 14.6, w0=0.6, w1=0.4)
        # 옆 끝 → 옆구리
        b.crack([(m(4.4), cy), (m(3.2), cy), (m(1.6), cy + 1.6), (m(1.6), 10.2)], 13.4)
        b.crack([(m(3.2), cy), (m(2.0), cy - 1.2), (m(2.0), 4.2)], 13.4, w0=0.7, w1=0.4)
        # 아래 끝 → 복부
        b.crack([(m(7.6), 3.0), (m(6.8), 2.2), (m(6.8), 1.0), (m(5.6), -0.2)], 12.8, w0=0.9)
    # ── 복부 (아래로 좁아지는 V): 열 균열 바위 + 어두운 아랫배 ──
    b.box((2.8, -0.4, 4.0), (13.2, 3.4, 12.8), "hot")
    b.box((4.4, -2.6, 4.8), (11.6, -0.2, 11.6), "dark")
    # 쇄골 흑요석 테 + 목(용암)
    for mir in (False, True):
        mbox(b, mir, (1.6, 17.0, 4.0), (7.0, 18.2, 12.6), "obsidian")
    b.box((5.2, 16.6, 5.2), (10.8, 18.8, 10.8), "lava")
    # ── 등: 척추 가시 (뒤로 비스듬히) ──
    for i, y in enumerate((15.4, 12.0, 8.6, 5.2)):
        ln = 5.0 - i * 0.8
        b.box((7.2, y - 0.9, 3.4 - ln), (8.8, y + 0.9, 3.6), "obsidian", rot=("x", -22.5, (8, y, 3.4)))
        b.box((7.5, y - 0.6, 3.0 - ln), (8.5, y + 0.6, 3.4 - ln + 1.0), "ember", rot=("x", -22.5, (8, y, 3.4)))
    # 등판 균열 (굴뚝 아래, 가시 옆) — 판 표면 위에만
    for mir in (False, True):
        def m(x):
            return 16 - x if mir else x
        b.crack([(m(9.2), 13.0), (m(10.6), 13.0), (m(12.0), 11.6), (m(14.8), 11.6)], 3.0, w0=0.8)
        b.crack([(m(9.4), 9.4), (m(10.4), 8.4), (m(12.2), 8.4), (m(13.6), 7.0), (m(13.6), 4.4)], 2.8, w0=0.8)
    # ── 등의 화산 굴뚝 2개 + 불꽃 ──
    for gx in (3.8, 12.2):
        b.box((gx - 2.2, 14.0, 0.8), (gx + 2.2, 17.6, 4.6), "dark")
        b.box((gx - 1.6, 17.4, 1.4), (gx + 1.6, 19.4, 4.0), "hot")
        b.box((gx - 1.0, 18.8, 2.0), (gx + 1.0, 19.6, 3.4), "lava")
        b.flame(gx, 2.7, 19.4, 25.6, 5.0)
    # ── 어깨: +X 쪽을 만들고 거울로 -X 쪽 (바깥 갑판 x=22 → 어깨폭 3.5블록) ──
    for mir in (False, True):
        def m(x):
            return 16 - x if mir else x
        mbox(b, mir, (15.0, 8.6, 3.8), (20.6, 17.6, 12.6), "lava")       # 어깨 속 용암
        mbox(b, mir, (15.4, 14.0, 2.6), (21.0, 18.4, 13.6), "hot")       # 어깨 윗덩이 (열 균열)
        mbox(b, mir, (15.8, 8.2, 3.2), (21.2, 13.0, 13.0), "basalt2")    # 어깨 아랫덩이
        mbox(b, mir, (20.6, 9.0, 4.2), (22.0, 16.8, 12.0), "dark")       # 바깥 갑판
        mbox(b, mir, (16.0, 18.2, 3.6), (21.0, 19.2, 12.6), "obsidian")  # 견갑 테
        mbox(b, mir, (17.0, 7.4, 5.0), (20.4, 8.4, 11.2), "ember")       # 겨드랑이 아래 용암 방울
        b.crack([(m(16.0), 17.8), (m(17.2), 16.6), (m(18.8), 16.6), (m(20.4), 15.0)], 13.6, w0=0.9)
        b.crack([(m(20.4), 12.6), (m(20.4), 11.4), (m(19.0), 10.0), (m(19.0), 8.8)], 13.0, w0=0.8)
        b.crack([(5.0, 16.2), (6.4, 14.8), (8.6, 14.8), (10.0, 13.4), (10.0, 10.0)], m(22.0), w0=0.9, axis="x")
        # 불타는 견갑 (가시 대신 불꽃)
        b.flame(m(18.4), 8.2, 19.0, 26.0, 6.4)
    return b.m


def build_head(at, R):
    """scale 1.9 (1칸 ≈ 0.119블록). 피벗 = 목 밑동, 위로 자란다."""
    b = Builder(f"boss/{BOSS}_head", at, R, dens=1.9, seed=2)
    b.box((3.8, 6.0, 4.2), (12.2, 18.6, 12.2), "lava")                 # 안쪽 용암
    b.box((3.0, 15.0, 3.0), (13.0, 20.4, 12.0), "basalt")              # 두개골 윗덩이
    b.box((3.4, 9.8, 2.6), (12.6, 15.4, 6.6), "dark")                  # 뒤통수
    b.box((3.2, 10.2, 7.6), (12.8, 14.6, 12.4), "basalt2")             # 얼굴 덩이
    b.box((7.2, 10.6, 12.2), (8.8, 14.6, 13.8), "basalt")              # 콧등
    for mir in (False, True):
        # 화난 V 눈썹: 안쪽 끝(x=7.5)을 축으로 바깥이 올라감, 가운데에서 교차하지 않음
        mbox(b, mir, (2.2, 14.4, 11.4), (7.5, 16.2, 14.4), "obsidian", rot=("z", -22.5, (7.5, 15.3, 12.9)))
        # 눈도 눈썹을 따라 안쪽으로 기울임
        mbox(b, mir, (3.6, 12.3, 12.2), (7.2, 13.9, 13.3), "eye", rot=("z", -22.5, (5.4, 13.1, 12.75)))
        mbox(b, mir, (2.6, 10.2, 9.0), (4.6, 12.6, 13.4), "basalt")     # 광대
        # 엄니: 아래턱에서 위-바깥으로 솟는 긴 뿔 재질 (밑동 검고 끝이 달아오름)
        mbox(b, mir, (4.2, 5.4, 12.8), (5.6, 12.2, 14.2), "horn", rot=("z", 22.5, (4.9, 5.4, 13.5)),
             vrange=(0.0, 1.0))
    # 벌린 입: 턱을 1.5 내려 백열 아가리가 보인다
    b.box((4.2, 7.4, 9.0), (11.8, 10.4, 12.6), "ember")
    b.box((3.4, 4.5, 4.6), (12.6, 7.7, 13.8), "basalt")                # 아래턱
    b.box((4.6, 7.0, 12.8), (11.4, 7.6, 14.2), "obsidian")             # 아랫입술 테
    # 정수리 볏 (뒤로 솟은 흑요석 가시)
    b.box((7.0, 19.0, 4.6), (9.0, 23.6, 7.6), "obsidian", rot=("x", -22.5, (8, 19, 6.1)))
    b.box((7.4, 23.2, 5.0), (8.6, 25.0, 7.2), "ember", rot=("x", -22.5, (8, 19, 6.1)))
    # 뿔: ① 옆으로 나오며 앞으로 22.5 쓸림(y) ② 바깥으로 기울며 위로(z) ③ 앞으로 꺾임(x)
    for mir in (False, True):
        o1 = np.array([11.6, 17.6, 7.4])
        mbox(b, mir, (11.6, 15.2, 4.4), (17.0, 20.0, 10.4), "horn", rot=("y", -22.5, tuple(o1)), vrange=(0.70, 1.0))
        e1 = o1 + _rot("y", -22.5, (5.4, 0, 0))                          # ① 끝
        o2 = e1 + np.array([-0.4, 0, -0.2])
        L2 = 4.8
        mbox(b, mir, (o2[0] - 1.9, o2[1], o2[2] - 1.8), (o2[0] + 1.9, o2[1] + L2, o2[2] + 1.8), "horn",
             rot=("z", -22.5, tuple(o2)), vrange=(0.38, 0.72))
        e2 = o2 + _rot("z", -22.5, (0, L2, 0))
        o3 = e2 + np.array([-0.2, -0.4, 0])
        L3 = 4.0
        mbox(b, mir, (o3[0] - 1.25, o3[1], o3[2] - 1.2), (o3[0] + 1.25, o3[1] + L3, o3[2] + 1.2), "horn",
             rot=("x", 22.5, tuple(o3)), vrange=(0.0, 0.40))
        mbox(b, mir, (o3[0] - 0.65, o3[1] + L3 - 0.3, o3[2] - 0.6), (o3[0] + 0.65, o3[1] + L3 + 1.6, o3[2] + 0.6),
             "ember", rot=("x", 22.5, tuple(o3)))
    # 머리 위 불꽃 왕관
    b.flame(8.0, 6.0, 20.2, 26.0, 6.4)
    return b.m


FIST_SHIFT = (0.0, -6.0, 4.0)  # 주먹을 피벗 아래-앞으로 → 휘두르면 크게 호를 그린다


def build_fist(at, R, side):
    """scale 1.9 (1칸 ≈ 0.12블록). side=+1 → +X(왼손), -1 → -X(오른손).
    -X 쪽(몸 안쪽)에 엄지를 두고 작성한 뒤 오른손은 거울. 모든 좌표를 FIST_SHIFT 만큼 옮겨
    피벗(손목 위 1.2블록)에서 멀리 떨어뜨린다."""
    name = "left_fist" if side > 0 else "right_fist"
    b = Builder(f"boss/{BOSS}_{name}", at, R, dens=1.9, seed=3 if side > 0 else 4)
    mir = side < 0
    sx, sy, sz = FIST_SHIFT

    def bx(frm, to, m, rot=None, **kw):
        frm = (frm[0] + sx, frm[1] + sy, frm[2] + sz)
        to = (to[0] + sx, to[1] + sy, to[2] + sz)
        if rot and len(rot) > 2:
            o = rot[2]
            rot = (rot[0], rot[1], (o[0] + sx, o[1] + sy, o[2] + sz))
        mbox(b, mir, frm, to, m, rot=rot, **kw)

    bx((3.6, 1.8, 4.6), (13.4, 10.6, 16.6), "lava")                    # 안쪽 용암 (틈으로 보임)
    # 손등: 열 균열 바위 2조각 (가운데 용암 이음매) + 힘줄 판
    bx((3.0, 9.4, 3.8), (8.2, 12.6, 13.0), "hot")
    bx((8.8, 9.4, 3.8), (14.0, 12.6, 13.0), "hot")
    bx((5.0, 12.4, 5.0), (12.0, 13.4, 11.0), "obsidian")
    bx((3.2, 1.0, 4.2), (13.8, 9.0, 12.2), "basalt2")                  # 손바닥
    # 손가락 4개: 검지·중지가 1.0 앞으로 나온 계단형 너클, 둘째마디는 22.5도 말려 들어감
    step = (0.8, 1.0, 0.4, 0.0)
    for i in range(4):
        x0 = 3.0 + i * 2.8
        hx = step[i]
        zf = 17.6 + hx
        bx((x0, 5.0, 12.0), (x0 + 2.4, 10.4, zf), "basalt")             # 너클 (첫마디)
        bx((x0 + 0.15, 0.4, 12.4), (x0 + 2.25, 5.4, 16.6 + hx), "dark",
           rot=("x", 22.5, (x0 + 1.2, 5.4, 16.6 + hx)))                 # 말린 둘째마디
        # 너클 앞면을 가로지르는 한 줄 지그재그 균열 (V 를 이어 붙임)
        for (a, c) in ((x0, x0 + 1.2), (x0 + 1.2, x0 + 2.4)):
            up = a == x0
            ya, yc = (8.6, 7.4) if up else (7.4, 8.6)
            mx, my = (a + c) / 2, (ya + yc) / 2
            ang = -45 if up else 45
            bx((mx - 0.95, my - 0.4, zf - 0.05), (mx + 0.95, my + 0.4, zf + 0.35), "ember",
               rot=("z", ang, (mx, my, zf + 0.15)))
    # 너클 스파이크: 검지·중지에 굵은 가시 2개, 약지·새끼는 낮은 돌기
    for i, (big) in enumerate((True, True, False, False)):
        x0 = 3.0 + i * 2.8
        zc = 15.6 + step[i]
        o = (x0 + 1.2, 10.2, zc)
        if big:
            bx((x0 + 0.25, 10.0, zc - 1.0), (x0 + 2.15, 13.6, zc + 1.0), "obsidian", rot=("x", 22.5, o))
            bx((x0 + 0.65, 13.4, zc - 0.55), (x0 + 1.75, 15.4, zc + 0.55), "ember", rot=("x", 22.5, o))
        else:
            bx((x0 + 0.5, 10.0, zc - 0.7), (x0 + 1.9, 11.6, zc + 0.7), "obsidian", rot=("x", 22.5, o))
    # 엄지: 옆면 + 앞으로 감싸는 끝마디
    bx((0.6, 1.6, 7.0), (3.4, 6.6, 14.6), "basalt")
    bx((1.0, 1.4, 14.2), (8.0, 4.4, 18.6), "basalt2")
    bx((1.4, 3.9, 17.6), (3.2, 4.8, 18.8), "ember")
    # 손목: 깨진 흑요석 팔찌 4조각 사이 틈으로만 보이는 용암 고리 + 뒤 마개(열 바위)
    bx((4.6, 3.6, 0.8), (12.4, 9.6, 4.2), "lava")
    bx((5.2, 4.2, 0.0), (11.8, 9.0, 1.2), "hot")
    bx((3.2, 9.6, 1.0), (13.8, 11.4, 4.0), "obsidian")
    bx((3.6, 1.8, 1.0), (13.4, 3.4, 4.0), "obsidian")
    bx((2.6, 3.8, 1.2), (4.2, 9.0, 3.8), "obsidian")
    bx((12.8, 3.8, 1.2), (14.4, 9.0, 3.8), "obsidian")
    # 혜성 꼬리 불꽃 (손목 뒤로 눕는다)
    bx_fl = (8.0 + sx, 6.4 + sy, 0.4 + sz)
    b.flame_tilt(bx_fl[0], bx_fl[1], bx_fl[2], 11.0, 7.0, angle=-45)
    # 뒤로 흩어지는 파편
    bx((5.4, 7.4, -2.4), (8.0, 10.0, 0.2), "hot", rot=("y", 22.5, (6.7, 8.7, -1.1)))
    bx((9.8, 9.6, -4.4), (11.4, 11.2, -2.8), "ember")
    bx((6.6, 10.8, -6.2), (7.8, 12.0, -5.0), "ember")
    return b.m


def build_tail(at, R):
    """scale 1.2. 피벗 = 꼬리 맨 위. 위쪽 두 덩이 (아래 두 덩이는 tail_low 파트)."""
    b = Builder(f"boss/{BOSS}_tail", at, R, dens=1.2, seed=5)
    b.box((6.8, -6.6, 6.8), (9.2, 9.0, 9.2), "lava")                   # 용암 사슬 (척추)
    # 덩이1: x 22.5 기울임, 덩이2: z -22.5 기울임 → 틈 1.6~2 로 용암이 보인다
    b.box((2.8, 2.6, 2.8), (13.2, 8.8, 13.2), "basalt", rot=("x", 22.5, (8, 5.7, 8)))
    b.box((3.6, 2.0, 3.6), (12.4, 2.8, 12.4), "hot", rot=("x", 22.5, (8, 5.7, 8)))
    b.box((7.4, 3.6, 13.0), (8.6, 7.8, 13.6), "ember", rot=("x", 22.5, (8, 5.7, 8)))
    b.box((3.6, -4.0, 3.6), (12.4, 0.8, 12.4), "basalt2", rot=("z", -22.5, (8, -1.6, 8)))
    b.box((4.4, -4.6, 4.4), (11.6, -3.8, 11.6), "hot", rot=("z", -22.5, (8, -1.6, 8)))
    # 주변을 떠도는 작은 파편
    for (x, y, z, s, m) in ((0.4, 0.6, 9.6, 2.0, "dark"), (13.8, 1.2, 4.4, 1.8, "hot"),
                            (12.2, -3.4, 11.6, 1.4, "ember"), (2.2, -4.6, 3.4, 1.4, "obsidian")):
        b.box((x, y, z), (x + s, y + s, z + s), m, rot=("y", 45))
    return b.m


TAIL_JOINT = -5.0  # tail 모델에서 tail_low 피벗이 붙는 y


def build_tail_low(at, R):
    """scale 1.2. 피벗 = 위 꼬리와 이어지는 마디. 따로 흔들려 따라오는 느낌."""
    b = Builder(f"boss/{BOSS}_tail_low", at, R, dens=1.2, seed=9)
    b.box((7.0, -1.8, 7.0), (9.0, 10.6, 9.0), "lava")                  # 용암 사슬 (위로 겹쳐 틈 메움)
    b.box((4.6, 3.0, 4.6), (11.4, 6.6, 11.4), "dark", rot=("x", -22.5, (8, 4.8, 8)))
    b.box((5.2, 2.4, 5.2), (10.8, 3.2, 10.8), "hot", rot=("x", -22.5, (8, 4.8, 8)))
    b.box((5.6, -1.0, 5.6), (10.4, 1.6, 10.4), "basalt", rot=("z", 22.5, (8, 0.3, 8)))
    b.box((7.1, -4.0, 7.1), (8.9, -1.6, 8.9), "ember")                 # 떨어지는 용암 방울
    b.box((7.5, -5.6, 7.5), (8.5, -4.6, 8.5), "ember")
    for (x, y, z, s, m) in ((3.0, 1.0, 10.2, 1.2, "ember"), (11.6, 2.6, 4.4, 1.4, "hot")):
        b.box((x, y, z), (x + s, y + s, z + s), m, rot=("y", 45))
    return b.m


def build_rock(at, R, variant):
    """scale ~2. 던져진 유성: 용암 심 + 엇갈려 기울인 열균열 바위 3~4덩이 + 불씨 위성 2개. 피벗 = 중심."""
    b = Builder(f"boss/{BOSS}_rock_{variant}", at, R, dens=2.0, seed=6 + (variant == "b"))
    if variant == "a":
        b.box((5.4, 5.4, 5.4), (10.6, 10.6, 10.6), "lava")
        b.box((4.0, 6.6, 4.4), (10.4, 11.2, 10.8), "hot", rot=("x", 22.5))
        b.box((6.6, 4.0, 5.2), (12.0, 9.0, 11.2), "basalt", rot=("z", -22.5))
        b.box((4.6, 4.2, 7.4), (9.4, 8.4, 11.8), "hot", rot=("y", 45))
        b.box((7.2, 7.6, 3.6), (11.0, 10.8, 7.0), "dark", rot=("x", -45))
        b.box((11.8, 10.2, 4.4), (13.2, 11.6, 5.8), "ember", rot=("y", 45))
        b.box((2.6, 4.2, 10.6), (3.8, 5.4, 11.8), "ember", rot=("y", 45))
        b.flame(8, 8, 10.2, 15.6, 5.0, "flame")
    else:
        b.box((5.6, 5.6, 5.6), (10.4, 10.4, 10.4), "lava")
        b.box((3.8, 5.2, 5.0), (11.0, 9.8, 11.0), "hot", rot=("z", 22.5))
        b.box((5.2, 7.6, 4.2), (10.8, 11.4, 9.8), "basalt2", rot=("x", -22.5))
        b.box((6.4, 4.0, 7.6), (11.4, 8.0, 12.0), "hot", rot=("y", -45))
        b.box((11.4, 4.4, 9.6), (12.8, 5.8, 11.0), "ember", rot=("y", 45))
        b.box((3.0, 10.4, 4.0), (4.2, 11.6, 5.2), "ember", rot=("y", 45))
        b.flame(8, 8, 10.6, 15.2, 4.6, "flame")
    return b.m


def build_halo(at, R):
    """scale 2.4. 머리 뒤 태양 코로나: 용암 16각 고리 + 위아래좌우 가시 4 + 대각 불꽃 4 (z 축 회전)."""
    b = Builder(f"boss/{BOSS}_halo", at, R, dens=2.4, seed=8)
    c = 8.0
    rr = 7.4
    # 고리 몸체: 22.5도씩 돌린 얇은 용암 막대 = 16각형
    seg = 2 * rr * math.tan(math.radians(11.25)) + 0.3
    for ang in (0, 22.5, 45, -22.5):
        rot = ("z", ang, (c, c, c)) if ang else None
        b.box((c - seg / 2, c + rr - 0.6, c - 0.5), (c + seg / 2, c + rr + 0.6, c + 0.5), "lava", rot=rot)
        b.box((c - seg / 2, c - rr - 0.6, c - 0.5), (c + seg / 2, c - rr + 0.6, c + 0.5), "lava", rot=rot)
        b.box((c + rr - 0.6, c - seg / 2, c - 0.5), (c + rr + 0.6, c + seg / 2, c + 0.5), "lava", rot=rot)
        b.box((c - rr - 0.6, c - seg / 2, c - 0.5), (c - rr + 0.6, c + seg / 2, c + 0.5), "lava", rot=rot)
    # 축 방향 가시 4 (흑요석 + 달아오른 끝)
    r0, r1, w, d = rr + 0.4, rr + 2.4, 1.8, 1.2
    b.box((c - w / 2, c + r0, c - d / 2), (c + w / 2, c + r1, c + d / 2), "obsidian")
    b.box((c - w / 2, c - r1, c - d / 2), (c + w / 2, c - r0, c + d / 2), "obsidian")
    b.box((c + r0, c - w / 2, c - d / 2), (c + r1, c + w / 2, c + d / 2), "obsidian")
    b.box((c - r1, c - w / 2, c - d / 2), (c - r0, c + w / 2, c + d / 2), "obsidian")
    e, t = 0.45, 1.6
    b.box((c - w / 2 + e, c + r1 - .2, c - .4), (c + w / 2 - e, c + r1 + t, c + .4), "ember")
    b.box((c - w / 2 + e, c - r1 - t, c - .4), (c + w / 2 - e, c - r1 + .2, c + .4), "ember")
    b.box((c + r1 - .2, c - w / 2 + e, c - .4), (c + r1 + t, c + w / 2 - e, c + .4), "ember")
    b.box((c - r1 - t, c - w / 2 + e, c - .4), (c - r1 + .2, c + w / 2 - e, c + .4), "ember")
    # 대각 불꽃 4: 바깥을 향해 타오르는 평면 (아래쪽은 텍스처를 뒤집어 끝이 바깥으로)
    key, reg = R["flame_big"]
    u0, v0, u1, v1 = reg.uv()
    fw, fr0, fr1 = 3.6, rr - 0.2, rr + 4.4
    for up in (True, False):
        uv = [u0, v0, u1, v1] if up else [u0, v1, u1, v0]
        if up:
            frm, to = (c - fw / 2, c + fr0, c), (c + fw / 2, c + fr1, c)
        else:
            frm, to = (c - fw / 2, c - fr1, c), (c + fw / 2, c - fr0, c)
        for ang in (45, -45):
            b.m.box(frm, to, {"north": (key, uv), "south": (key, uv)}, light=15, shade=False,
                    rotation={"origin": [c, c, c], "axis": "z", "angle": ang})
    return b.m


# ─────────────────────────────── z-버퍼 미리보기 렌더러 ───────────────────────────────
# mc3d.render 는 면 평균 깊이로 정렬하는 화가 알고리즘이라 큰 안쪽 용암 상자가 바깥 판 위로 그려지는
# 일이 잦다. 미리보기 정확도를 위해 픽셀 단위 z-버퍼 렌더러를 따로 둔다 (같은 좌표 규칙).
# lair=True: 어두운 둥지 조명 — 발광하지 않는 면은 0.3 배 (실제 전투 환경에서의 실루엣 판단용).

def zrender(parts, size=512, yaw=-35, pitch=25, bg=(24, 22, 32), pad=0.06, ss=2, lair=False, frame=0):
    from mc3d import _face_corners, _rot_matrix, FACE_LIGHT
    S = size * ss
    view = _rot_matrix("x", pitch) @ _rot_matrix("y", yaw)
    faces = []
    for model, M in parts:
        M = np.eye(4) if M is None else np.array(M, dtype=float)
        texs = {}
        for k, a in model.atlases.items():
            f = min(frame, a.frames - 1)
            texs[k] = np.array(a.img.crop((0, f * a.size, a.size, (f + 1) * a.size))).astype(float)
        for el in model.elements:
            cbf = _face_corners(el["from"], el["to"])
            rot = el.get("rotation")
            for fname, fd in el["faces"].items():
                tex = texs.get(fd["texture"].lstrip("#"))
                if tex is None:
                    continue
                pts = []
                for q in cbf[fname]:
                    v = np.array(q, dtype=float)
                    if rot:
                        o = np.array(rot["origin"], dtype=float)
                        v = _rot_matrix(rot["axis"], rot["angle"]) @ (v - o) + o
                    w4 = M @ np.append((v - 8.0) / 16.0, 1.0)
                    pts.append(view @ w4[:3])
                pts = np.array(pts)
                n = np.cross(pts[1] - pts[0], pts[3] - pts[0])
                if n[2] >= 0 or np.linalg.norm(n) < 1e-12:
                    continue
                if el.get("light_emission", 0) >= 8:
                    lit = 1.0
                else:
                    lit = FACE_LIGHT[fname] * (0.3 if lair else 1.0)
                faces.append((pts, tex, fd["uv"], fd.get("rotation", 0), lit))
    img = np.zeros((S, S, 3)) + np.array(bg[:3], float)
    if not faces:
        return Image.fromarray(img.astype("uint8"))
    allp = np.concatenate([f[0] for f in faces])
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1
    sc = S * (1 - 2 * pad) / span
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    zbuf = np.full((S, S), -np.inf)  # 뷰 공간에서 z 가 클수록 카메라에 가깝다
    for pts, tex, uv, frot, lit in faces:
        sp = np.array([((q[0] - cx) * sc + S / 2, -(q[1] - cy) * sc + S / 2, q[2]) for q in pts])
        th, tw = tex.shape[:2]
        u0, v0, u1, v1 = uv[0] / 16 * tw, uv[1] / 16 * th, uv[2] / 16 * tw, uv[3] / 16 * th
        src = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for _ in range(int(frot) // 90):
            src = src[1:] + src[:1]
        p0, e1, e3 = sp[0], sp[1] - sp[0], sp[3] - sp[0]
        det = e1[0] * e3[1] - e1[1] * e3[0]
        if abs(det) < 1e-9:
            continue
        x0, x1 = int(max(0, np.floor(sp[:, 0].min()))), int(min(S, np.ceil(sp[:, 0].max()) + 1))
        y0, y1 = int(max(0, np.floor(sp[:, 1].min()))), int(min(S, np.ceil(sp[:, 1].max()) + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1] + 0.5
        dx, dy = xs - p0[0], ys - p0[1]
        s_ = (dx * e3[1] - dy * e3[0]) / det
        t_ = (e1[0] * dy - e1[1] * dx) / det
        inside = (s_ >= 0) & (s_ <= 1) & (t_ >= 0) & (t_ <= 1)
        if not inside.any():
            continue
        z = p0[2] + s_ * e1[2] + t_ * e3[2]
        a, b_, c, d = [np.array(q) for q in src]
        uvx = a + s_[..., None] * (b_ - a) + t_[..., None] * (d - a)
        ui = np.clip(np.floor(uvx[..., 0] - 1e-6 * np.sign(b_[0] - a[0])), 0, tw - 1).astype(int)
        vi = np.clip(np.floor(uvx[..., 1] - 1e-6 * np.sign(d[1] - a[1])), 0, th - 1).astype(int)
        col = tex[vi, ui]
        sub_z = zbuf[y0:y1, x0:x1]
        ok = inside & (col[..., 3] > 100) & (z > sub_z + 1e-7)
        sub_z[ok] = z[ok]
        img[y0:y1, x0:x1][ok] = col[..., :3][ok] * lit
    out = Image.fromarray(np.clip(img, 0, 255).astype("uint8"))
    return out.resize((size, size), Image.LANCZOS) if ss > 1 else out


# ─────────────────────────────── 리그 ───────────────────────────────

CLEARANCE = {}       # 마지막 build 의 스윕 충돌 검사 결과
BODY_BOB = 0.2       # 5.5블록 거인이 떠 있는 게 보이도록 크게
BODY_PERIOD = 60
TAIL_SCALE = 1.2
TAIL_OFF = (0.0, 1.95, -0.15)


def rig_spec():
    def bob(a, p, ph=0.0):
        return {"type": "bob", "amplitude": a, "period": p, "phase": ph}

    def sway(axis, ang, period, ph=0.0):
        return {"type": "sway", "axis": axis, "angle": ang, "period": period, "phase": ph}

    def swing(axis, ang, ticks):
        return {"type": "swing", "axis": axis, "angle": ang, "ticks": ticks}

    body_bob = bob(BODY_BOB, BODY_PERIOD, 0.0)
    low_y = round(TAIL_OFF[1] + (TAIL_JOINT - 8) * TAIL_SCALE / 16, 4)
    parts = [
        {"id": "tail", "model": "tail", "offset": list(TAIL_OFF), "scale": TAIL_SCALE, "rotation": [0, 0, 0],
         "frame": "body", "anims": [bob(BODY_BOB, BODY_PERIOD, 0.04), sway("z", 7, 80, 0.0), sway("x", 5, 110, 0.3)]},
        # 아래 꼬리: 위 꼬리보다 늦게(+0.15), 크게(12도) 흔들려 따라오는 느낌
        {"id": "tail_low", "model": "tail_low", "offset": [0, low_y, TAIL_OFF[2]], "scale": TAIL_SCALE,
         "rotation": [0, 0, 0], "frame": "body",
         "anims": [bob(BODY_BOB, BODY_PERIOD, 0.08), sway("z", 12, 80, 0.15), sway("x", 8, 110, 0.45)]},
        {"id": "torso", "model": "torso", "offset": [0, 3.0, 0], "scale": 2.0, "rotation": [8, 0, 0], "frame": "body",
         "anims": [body_bob]},
        {"id": "halo", "model": "halo", "offset": [0, 4.85, -1.1], "scale": 2.4, "rotation": [0, 0, 0],
         "frame": "body", "anims": [body_bob, {"type": "spin", "axis": "z", "speed": 1.5}]},
        {"id": "head", "model": "head", "offset": [0, 4.45, 0.55], "scale": 1.9, "rotation": [0, 0, 0],
         "frame": "body", "anims": [body_bob, sway("y", 9, 120, 0.0), swing("x", 10, 12)]},
        # 주먹: 피벗이 주먹 위-뒤 1.2블록 → 휘두르면 앞-위로 들렸다가 내리찍는다. 좌우 각도/길이 다르게.
        {"id": "right_fist", "model": "right_fist", "offset": [-2.45, 3.11, 0.1], "scale": 1.9,
         "rotation": [0, 8, 0], "frame": "body",
         "anims": [bob(0.22, 50, 0.25), sway("x", 7, 70, 0.1), swing("x", -75, 12)]},
        {"id": "left_fist", "model": "left_fist", "offset": [2.45, 3.11, 0.1], "scale": 1.9,
         "rotation": [0, -8, 0], "frame": "body",
         "anims": [bob(0.22, 50, 0.75), sway("x", 7, 70, 0.6), swing("x", -60, 16)]},
    ]
    # 도는 유성 4개: 위 2개는 어깨 위, 아래 2개는 주먹 아래로 (스윕 충돌 검사로 확인)
    for i, (rad, h, sc, model) in enumerate(((3.4, 0.55, 2.1, "rock_a"), (3.5, 4.75, 1.9, "rock_b"),
                                            (3.4, 0.55, 2.1, "rock_a"), (3.5, 4.75, 1.9, "rock_b"))):
        parts.append({"id": f"rock{i + 1}", "model": model, "offset": [0, 0, 0], "scale": sc,
                      "rotation": [0, 0, 0], "frame": "world",
                      "anims": [{"type": "orbit", "radius": rad, "speed": 2.4, "phase": i * 90 + (0 if i % 2 else 45),
                                 "height": h},
                                {"type": "spin", "axis": "y", "speed": 5.0 if i % 2 else -4.0},
                                bob(0.25, 40, i * 0.25)]})
    for p in parts:
        p["model"] = f"augsky:boss/{BOSS}_{p['model']}"
    return parts


def part_pose(p, t=0.0, swing_s=None):
    """Rigs.transform 과 같은 계산: 이동(bob/orbit) + 회전(anim * base). 블록 단위 4x4 행렬."""
    from mc3d import _rot_matrix
    x, y, z = p["offset"]
    A = np.eye(3)
    for a in p["anims"]:
        ty = a["type"]
        if ty == "bob":
            y += a["amplitude"] * math.sin(2 * math.pi * (t / a["period"] + a["phase"]))
        elif ty == "sway":
            A = A @ _rot_matrix(a["axis"], a["angle"] * math.sin(2 * math.pi * (t / a["period"] + a["phase"])))
        elif ty == "spin":
            A = A @ _rot_matrix(a["axis"], a["speed"] * t)
        elif ty == "orbit":
            th = math.radians(a["phase"] + a["speed"] * t)
            x, z = a["radius"] * math.cos(th), a["radius"] * math.sin(th)
            y = p["offset"][1] + a["height"]
        elif ty == "swing" and swing_s is not None and 0 <= swing_s < a["ticks"]:
            A = A @ _rot_matrix(a["axis"], a["angle"] * math.sin(math.pi * swing_s / a["ticks"]))
    pitch, yaw, roll = p["rotation"]
    base = _rot_matrix("y", yaw) @ _rot_matrix("x", pitch) @ _rot_matrix("z", roll)
    M = np.eye(4)
    M[:3, :3] = A @ base * p["scale"]
    M[:3, 3] = (x, y, z)
    return M


def model_points(model):
    """모든 element 의 꼭짓점 (element 회전 적용, 블록 단위, 피벗 원점)."""
    from mc3d import _rot_matrix
    pts = []
    for el in model.elements:
        f, t = el["from"], el["to"]
        cs = np.array([[a, b, c] for a in (f[0], t[0]) for b in (f[1], t[1]) for c in (f[2], t[2])], float)
        r = el.get("rotation")
        if r:
            o = np.array(r["origin"], float)
            cs = (cs - o) @ _rot_matrix(r["axis"], r["angle"]).T + o
        pts.append(cs)
    return (np.concatenate(pts) - 8.0) / 16.0


def clearance_test(parts, models, step_deg=5):
    """도는 바위(원기둥으로 근사) vs 몸 파트(포즈마다 AABB) 스윕 검사.
    몸 방향과 무관하게 '상대 각도'를 5도마다 돌린다. 몸 파트 포즈는 bob/sway 시간 샘플 × swing 진행 샘플."""
    rocks = [p for p in parts if p["frame"] == "world"]
    body = [p for p in parts if p["frame"] == "body"]
    report = []
    worst = {}
    for bp in body:
        key = bp["model"].split(f"{BOSS}_")[1]
        P = model_points(models[key])
        swing_ticks = [a["ticks"] for a in bp["anims"] if a["type"] == "swing"]
        ss = [None] + (list(range(0, swing_ticks[0] + 1)) if swing_ticks else [])
        boxes = []
        for t in range(0, 840, 7):
            for s in ss:
                M = part_pose(bp, t, s)
                W = P @ M[:3, :3].T + M[:3, 3]
                boxes.append((W.min(axis=0), W.max(axis=0)))
        for rp in rocks:
            rkey = rp["model"].split(f"{BOSS}_")[1]
            RP = model_points(models[rkey]) * rp["scale"]
            r_xz = float(np.sqrt(RP[:, 0] ** 2 + RP[:, 2] ** 2).max())
            ry0, ry1 = float(RP[:, 1].min()), float(RP[:, 1].max())
            orb = next(a for a in rp["anims"] if a["type"] == "orbit")
            amp = sum(a["amplitude"] for a in rp["anims"] if a["type"] == "bob")
            rad, h = orb["radius"], rp["offset"][1] + orb["height"]
            hits = 0
            gap = 1e9
            for deg in range(0, 360, step_deg):
                th = math.radians(deg)
                cxz = np.array([rad * math.cos(th), rad * math.sin(th)])
                for lo, hi in boxes:
                    # xz: 원과 상자 사이 거리, y: 구간 겹침
                    dx = max(lo[0] - cxz[0], 0, cxz[0] - hi[0])
                    dz = max(lo[2] - cxz[1], 0, cxz[1] - hi[2])
                    dxz = math.hypot(dx, dz) - r_xz
                    dy = max(lo[1] - (h + ry1 + amp), (h + ry0 - amp) - hi[1], 0)
                    sep = max(dxz, dy)
                    gap = min(gap, sep)
                    if dxz < 0 and dy <= 0:
                        hits += 1
            worst[(bp["id"], rp["id"])] = gap
            if hits:
                report.append(f"{rp['id']} x {bp['id']}: {hits} 충돌 샘플")
    return report, worst


def hitbox_model(w=1.8, h=5.4):
    """미리보기 전용: 히트박스 와이어프레임 (게임에 쓰지 않음)."""
    a = Atlas("preview/hitbox", size=16)
    reg = a.cell((90, 220, 255, 255), "flat")
    m = Model("preview/hitbox")
    m.use("c", a)
    W, H, t = w * 16, h * 16, 0.25
    x0, x1 = 8 - W / 2, 8 + W / 2
    y0, y1 = 8, 8 + H
    z0, z1 = 8 - W / 2, 8 + W / 2
    for (xa, xb) in ((x0, x0 + t), (x1 - t, x1)):
        for (za, zb) in ((z0, z0 + t), (z1 - t, z1)):
            m.box((xa, y0, za), (xb, y1, zb), ("c", reg), light=15)
    for (ya, yb) in ((y0, y0 + t), (y1 - t, y1)):
        for (za, zb) in ((z0, z0 + t), (z1 - t, z1)):
            m.box((x0, ya, za), (x1, yb, zb), ("c", reg), light=15)
        for (xa, xb) in ((x0, x0 + t), (x1 - t, x1)):
            m.box((xa, ya, z0), (xb, yb, z1), ("c", reg), light=15)
    return m


def label(img, text, font=FONT, size=22):
    from PIL import ImageDraw, ImageFont
    img = img.convert("RGB")
    ImageDraw.Draw(img).text((10, 8), text, font=ImageFont.truetype(font, size), fill=(235, 230, 220))
    return img


def build(assets_root):
    at_rock, at_lava, R = make_atlases()
    at = (at_rock, at_lava)
    models = {
        "torso": build_torso(at, R),
        "head": build_head(at, R),
        "left_fist": build_fist(at, R, +1),
        "right_fist": build_fist(at, R, -1),
        "tail": build_tail(at, R),
        "tail_low": build_tail_low(at, R),
        "rock_a": build_rock(at, R, "a"),
        "rock_b": build_rock(at, R, "b"),
        "halo": build_halo(at, R),
    }
    tex_root = os.path.join(assets_root, "textures")
    at_rock.save(tex_root)
    at_lava.save(tex_root)
    for m in models.values():
        m.write(assets_root)

    parts = rig_spec()
    report, worst = clearance_test(parts, models)
    min_gap = min(v for (b, r), v in worst.items() if b in ("left_fist", "right_fist"))
    spec = {
        "boss": BOSS,
        "parts": parts,
        "notes": ("화염 거신: 떠다니는 용암 바위 거인. 피벗 (8,8,8). torso=가슴 중심(발 기준 3.0블록, 8도 앞으로 숙임), "
                  "head=목 밑동, fists=주먹 위-뒤 약 1.2블록(손목 위)에 피벗 → swing 이 앞-위로 큰 호를 그린 뒤 내리찍음 "
                  "(오른손 -75도/12틱, 왼손 -60도/16틱으로 어긋나게), tail=꼬리 윗끝, tail_low=꼬리 마디(늦게 따라 흔들림), "
                  "halo=머리 뒤 코로나 중심(z축 회전), rocks=world 프레임 orbit (offset 0, height=발 기준 높이). "
                  "앞=+Z, 오른손=-X. 용암/불꽃은 애니메이션 텍스처(boss/inferno_colossus_lava, 16프레임x3틱), "
                  "light_emission 15; 바위는 0. "
                  f"유성-몸 스윕 충돌 검사(5도 간격, swing/bob/sway 포함): {'통과' if not report else '; '.join(report)}, "
                  f"주먹과의 최소 간격 {min_gap:.2f}블록. "
                  "주의: 어깨폭 3.5블록, 주먹 바깥 끝 약 ±3.3블록으로 1.8폭 히트박스보다 넓다 → "
                  "주먹 위치에 Interaction 히트 프록시를 두는 것을 권장. 뿔/불꽃 꼭대기 약 6.6블록."),
    }
    os.makedirs(HERE, exist_ok=True)
    with open(os.path.join(HERE, f"{MODULE}.rig.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)

    # ── 미리보기 ──
    os.makedirs(PREVIEW, exist_ok=True)

    def scene(t=0.0, swing_s=None, with_hitbox=False):
        out = []
        for p in parts:
            key = p["model"].split(f"{BOSS}_")[1]
            out.append((models[key], part_pose(p, t, swing_s)))
        if with_hitbox:
            out.append((hitbox_model(), mat(translate=(0, 0, 0))))
        return out

    T0 = 15.0  # 미리보기 시각 (bob 이 위쪽 정점 근처)
    views = [(35, 12, "앞 3/4"), (0, 4, "정면"), (90, 6, "옆"), (180 + 35, 15, "뒤 3/4")]
    imgs = [zrender(scene(T0), size=640, yaw=y, pitch=pt) for y, pt, _ in views]
    imgs.append(zrender(scene(T0, with_hitbox=True), size=640, yaw=35, pitch=12))
    labels = [v[2] for v in views] + ["히트박스 1.8x5.4"]
    imgs += [zrender(scene(T0), size=640, yaw=y, pitch=pt, lair=True, frame=5) for y, pt, _ in views]
    imgs.append(zrender(scene(T0, swing_s=6), size=640, yaw=90, pitch=6, lair=True))
    labels += [v[2] + " (어두운 둥지)" for v in views] + ["휘두르기 정점 (옆, 둥지)"]
    contact_sheet(imgs, labels, cols=5, cell=420, font=FONT).save(os.path.join(PREVIEW, f"{BOSS}.png"))
    # 크게: 낮 조명 / 어두운 둥지
    hero = zrender(scene(T0), size=900, yaw=28, pitch=10)
    hero_l = zrender(scene(T0), size=900, yaw=28, pitch=10, lair=True, frame=8)
    hero.save(os.path.join(PREVIEW, f"{BOSS}_hero.png"))
    hero_l.save(os.path.join(PREVIEW, f"{BOSS}_hero_lair.png"))
    # 휘두르기 시퀀스 (옆)
    seq = [label(zrender(scene(T0, swing_s=s), size=420, yaw=70, pitch=6), f"swing {s}틱") for s in (0, 3, 6, 9, 12)]
    contact_sheet(seq, None, cols=5, cell=360).save(os.path.join(PREVIEW, f"{BOSS}_swing.png"))

    pi, pl = [], []
    for k, m in models.items():
        pi.append(zrender([(m, None)], size=400, yaw=35, pitch=20))
        pl.append(f"{k} 앞")
        pi.append(zrender([(m, None)], size=400, yaw=180 + 35, pitch=20))
        pl.append(f"{k} 뒤")
    contact_sheet(pi, pl, cols=6, cell=300, font=FONT).save(os.path.join(PREVIEW, f"{BOSS}_parts.png"))
    # 텍스처 확인용
    tex = Image.new("RGBA", (128 + 64 * 4, 128), (18, 16, 26, 255))
    tex.alpha_composite(at_rock.img)
    for i in range(4):
        tex.alpha_composite(at_lava.img.crop((0, i * 4 * 64, 64, i * 4 * 64 + 64)), (128 + 64 * i, 0))
    tex.resize((tex.width * 3, tex.height * 3), Image.NEAREST).save(os.path.join(PREVIEW, f"{BOSS}_tex.png"))
    CLEARANCE.update({"collisions": report, "gaps": {f"{b}/{r}": round(v, 3) for (b, r), v in worst.items()}})
    return spec


if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", MODULE, "assets", "augsky")
    s = build(root)
    for m in sorted(os.listdir(os.path.join(root, "models", "boss"))):
        with open(os.path.join(root, "models", "boss", m)) as f:
            print(m, len(json.load(f)["elements"]), "elements")
    print("parts:", [p["id"] for p in s["parts"]])
    print("collisions:", CLEARANCE["collisions"] or "none")
    gaps = CLEARANCE["gaps"]
    for k in sorted(gaps, key=gaps.get)[:8]:
        print("  gap", k, gaps[k])
