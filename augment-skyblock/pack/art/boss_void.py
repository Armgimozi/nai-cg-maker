"""
공허의 군주 (Void Sovereign) — boss id "void_sovereign".

키 약 6 블록의 공허 사신 군주. 바닥 위를 살짝 떠서 미끄러지듯 움직인다.
  - 팔각 단으로 퍼지는 긴 로브: 소용돌이치는 공허 텍스처(별이 반짝임, 애니메이션) + 빛나는 보라 룬 테
  - 등 뒤로 늘어진 너덜너덜한 공허 망토, 등에 군주의 문장
  - 갈비뼈 사이로 공허 핵이 빛나는 복부, 흑요 흉갑과 공허 심장석, 뼈 가시가 솟은 견갑, 높은 깃
  - 깊은 두건 속 해골 얼굴과 자홍색으로 타는 눈
  - 두건 위에 떠서 천천히 도는 검은 가시 왕관 (보라 보석, 빛나는 고리)
  - 오른손: 공허 날(빛나는 날끝)이 달린 거대한 낫 (별도 파트, 팔과 같은 피벗/스윙)
  - 왼손: 앞으로 내민 뼈 손바닥 위 공허 불꽃
  - 주위를 도는 공허 구슬 3개

작성 단위: 각 파트는 "월드 픽셀"(1 블록 = 16) 절대 좌표로 그린다 (보스 발 = 원점).
Kit 이 파트 피벗/스케일에 맞춰 모델 좌표(8 + (p - pivot)/scale)로 바꿔 준다.
앞은 +Z, 위는 +Y. 보스의 오른쪽 = -X (남쪽을 볼 때 오른손이 서쪽).
"""
import json
import math
import os
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from mc3d import (FACE_LIGHT, FACES, Atlas, Model, Region, _face_corners, _homography,  # noqa: E402
                  _rot_matrix, extrude, mat)

BOSS = "void_sovereign"
MODULE = "boss_void"
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
PREVIEW_DIR = os.path.join(HERE, "preview")

F = 16            # 애니메이션 프레임 수
FRAMETIME = 4     # 틱/프레임 → 64틱(3.2초) 주기

# ─────────────────────────────── 팔레트 ───────────────────────────────
VOID0 = (7, 3, 14)          # 가장 깊은 공허
ROBE = (38, 18, 60)
ROBE_D = (20, 9, 34)
ROBE_L = (86, 44, 130)
OBS = (40, 32, 58)          # 흑요 금속
OBS_HI = (150, 120, 210)
OBS_LO = (8, 4, 16)
SILV = (186, 172, 214)      # 영혼 은(트림)
SILV_D = (96, 82, 128)
BONE = (226, 218, 230)
BONE_D = (126, 112, 146)
V_D = (74, 18, 150)         # 짙은 보라 빛
V = (170, 72, 255)          # 보라 빛
MAG = (255, 64, 222)        # 자홍
V_W = (255, 222, 255)       # 하얀 빛


def _c(t):
    return np.array(t[:3], dtype=float)


def _seed(*k):
    return zlib.crc32(repr(k).encode()) & 0xFFFFFFFF


def _rng(*k):
    return np.random.default_rng(_seed(*k))


def _finish(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def _base(w, h, col, face, grad=0.22, noise=0.12, seed=0):
    """그라데이션 + 노이즈 바탕. 윗면은 밝게, 아랫면은 어둡게."""
    rng = _rng("base", w, h, face, seed)
    a = np.zeros((h, w, 4))
    a[..., 3] = 255
    yy = np.linspace(0, 1, h)[:, None] if h > 1 else np.zeros((1, 1))
    if face == "up":
        g = np.full((h, 1), 1.12)
    elif face == "down":
        g = np.full((h, 1), 0.7)
    else:
        g = 1.1 - grad * yy
    n = 1 - noise / 2 + noise * rng.random((h, w))
    a[..., :3] = _c(col)[None, None, :] * (g * n)[..., None]
    return a, rng


def _bevel(a, hi=OBS_HI, lo=OBS_LO, k=0.5):
    h, w = a.shape[:2]
    if w > 2 and h > 2:
        a[0, :, :3] = a[0, :, :3] * (1 - k) + _c(hi) * k
        a[:, 0, :3] = a[:, 0, :3] * (1 - k * 0.6) + _c(hi) * k * 0.6
        a[-1, :, :3] = a[-1, :, :3] * 0.45 + _c(lo) * 0.55
        a[:, -1, :3] = a[:, -1, :3] * 0.6 + _c(lo) * 0.4
    return a


def _speck(a, rng, p=0.05, col=V, k=0.55):
    m = rng.random(a.shape[:2]) < p
    a[m, :3] = a[m, :3] * (1 - k) + _c(col) * k
    return a


def _ramp(v):
    """0..1 → 짙은 보라 → 보라 → 자홍 → 흰빛. (…, 3) 배열."""
    stops = [(0.0, _c(V_D) * 0.55), (0.35, _c(V_D)), (0.6, _c(V)), (0.82, _c(MAG)), (1.0, _c(V_W))]
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        m = (v >= t0) & (v <= t1)
        k = ((v - t0) / (t1 - t0))[..., None]
        out[m] = (c0 + (c1 - c0) * k)[m]
    return out


# 주기적(이음매 없는) 노이즈: FFT 로 거른 무작위 잡음. 평균 0, 표준편차 1.
_NOISE = {}


def pnoise(seed, T=64, beta=1.7, cutoff=0.14):
    k = (seed, T, beta, cutoff)
    if k not in _NOISE:
        rng = np.random.default_rng(seed)
        w = rng.standard_normal((T, T))
        fx = np.fft.fftfreq(T)[:, None]
        fy = np.fft.fftfreq(T)[None, :]
        r = np.sqrt(fx ** 2 + fy ** 2)
        r[0, 0] = 1
        filt = 1.0 / r ** beta
        filt[0, 0] = 0
        filt[r > cutoff] = 0         # 너무 잘게 부서지지 않게
        n = np.real(np.fft.ifft2(np.fft.fft2(w) * filt))
        _NOISE[k] = (n - n.mean()) / n.std()
    return _NOISE[k]


# ─────────────────────────────── 정적 페인터 ───────────────────────────────
# painter(w, h, face) -> RGBA Image

def P_plate(col=OBS, speck=0.02, seed=0):
    """흑요 판금: 안쪽 홈선, 보라빛 모서리 반사, 은 리벳."""
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.3, noise=0.08, seed=seed)
        if w >= 8 and h >= 8:
            i = 2
            a[i, i:w - i, :3] *= 0.5
            a[h - 1 - i, i:w - i, :3] *= 0.5
            a[i:h - i, i, :3] *= 0.5
            a[i:h - i, w - 1 - i, :3] *= 0.5
            a[i + 1, i + 1:w - i - 1, :3] = a[i + 1, i + 1:w - i - 1, :3] * 0.6 + _c(OBS_HI) * 0.4
            for (yy, xx) in ((1, 1), (1, w - 2), (h - 2, 1), (h - 2, w - 2)):
                a[yy, xx, :3] = _c(SILV)
        _speck(a, rng, speck, OBS_HI, 0.4)
        return _finish(_bevel(a, k=0.6))
    return paint


def P_metal(col=SILV, lo=SILV_D):
    """은 트림: 대각선 광택 줄무늬."""
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.15, noise=0.06)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        k = ((x + y * 2) % 7) / 6.0
        a[..., :3] *= (0.8 + 0.32 * (1 - np.abs(k - 0.4) * 1.6)).clip(0.72, 1.15)[..., None]
        return _finish(_bevel(a, hi=(255, 255, 255), lo=lo, k=0.45))
    return paint


def P_cloth(col=ROBE, fold=True):
    """두꺼운 천: 세로 주름 음영과 가로 결."""
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.25, noise=0.16)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        a[..., :3] *= np.where(y % 2 == 0, 1.06, 0.95)[..., None]
        if fold and face not in ("up", "down") and w >= 4:
            f = 0.86 + 0.2 * np.sin(x / max(2.0, w / 3.0) * math.pi) ** 2
            a[..., :3] *= f[..., None]
        return _finish(a)
    return paint


def P_bone(col=BONE):
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.3, noise=0.1)
        _speck(a, rng, 0.06, BONE_D, 0.5)
        return _finish(_bevel(a, hi=(255, 255, 255), lo=BONE_D, k=0.35))
    return paint


def P_dark():
    """두건 안쪽 같은 깊은 어둠."""
    def paint(w, h, face):
        a, rng = _base(w, h, VOID0, face, grad=0.1, noise=0.3)
        return _finish(a)
    return paint


def P_chest():
    """흉갑 앞면 (밀도 2): 가슴판 곡선, 가운데 능선, 은 테, 아래로 갈라지는 홈."""
    def paint(w, h, face):
        a, rng = _base(w, h, OBS, face, grad=0.35, noise=0.08)
        img = _finish(a)
        d = ImageDraw.Draw(img)
        cx = w / 2
        hi = OBS_HI + (255,)
        lo = OBS_LO + (255,)
        for s in (-1, 1):
            pts = [(cx + s * 2, h * 0.08), (cx + s * w * 0.16, h * 0.7), (cx + s * w * 0.42, h * 0.8),
                   (cx + s * w * 0.5, h * 0.5)]
            d.line(pts, fill=lo, width=2)
            d.line([(x, y - 2) for x, y in pts], fill=hi, width=1)
            # 어깨 쪽 겹판 선
            d.line([(cx + s * w * 0.3, 0), (cx + s * w * 0.5, h * 0.3)], fill=lo, width=1)
        d.line([(cx - 1, 0), (cx - 1, h)], fill=hi, width=1)
        d.line([(cx, 0), (cx, h)], fill=lo, width=1)
        d.rectangle((0, 0, w, 1), fill=SILV + (255,))
        d.rectangle((0, h - 2, w, h), fill=SILV_D + (255,))
        a = np.array(img).astype(float)
        _speck(a, rng, 0.025, OBS_HI, 0.4)
        return _finish(a)
    return paint


def P_face():
    """해골 얼굴 (밀도 2): 치켜 올라간 눈구멍, 코 구멍, 광대, 금."""
    def paint(w, h, face):
        a, rng = _base(w, h, BONE, face, grad=0.4, noise=0.08)
        img = _finish(a)
        d = ImageDraw.Draw(img)
        dark = (14, 4, 22, 255)
        sh = BONE_D + (255,)
        s = w / 24.0
        # 이마 아래 눈썹 뼈 그림자
        d.polygon([(0, 6 * s), (10 * s, 9 * s), (14 * s, 9 * s), (24 * s, 6 * s), (24 * s, 9 * s),
                   (14 * s, 12 * s), (10 * s, 12 * s), (0, 9 * s)], fill=sh)
        for side in (-1, 1):
            cx = 12 + side * 5.5
            pts = [(cx - 4 * side, 9.5), (cx + 4 * side, 7.5), (cx + 3.5 * side, 14), (cx - 2.5 * side, 14)]
            d.polygon([(x * s, y * s) for x, y in pts], fill=dark)
        d.polygon([(11 * s, 15.5 * s), (13 * s, 15.5 * s), (12.6 * s, 19 * s), (11.4 * s, 19 * s)], fill=dark)
        for side in (-1, 1):
            d.line([((12 + side * 10) * s, 15 * s), ((12 + side * 6) * s, 17.5 * s)], fill=(255, 255, 255, 255))
            d.line([((12 + side * 10) * s, 17 * s), ((12 + side * 7) * s, 20 * s)], fill=sh)
        d.rectangle((0, 21 * s, w, h), fill=BONE_D + (255,))
        # 이마의 금과 보라 룬 자국
        d.line([(15 * s, 0), (14 * s, 3 * s), (16 * s, 6 * s)], fill=(60, 30, 80, 255))
        d.line([(4 * s, 2 * s), (6 * s, 4 * s)], fill=(60, 30, 80, 255))
        return img
    return paint


def P_jaw():
    """아래턱 앞면: 이빨 줄."""
    def paint(w, h, face):
        a, rng = _base(w, h, BONE_D, face, grad=0.2, noise=0.08)
        img = _finish(a)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, w, h * 0.5), fill=(14, 4, 22, 255))
        for i in range(0, w, 2):
            d.rectangle((i, 0, i, h * 0.45), fill=BONE + (255,))
            d.point((i, 0), fill=(255, 255, 255, 255))
        return img
    return paint


def P_grip():
    """낫 손잡이: 감긴 가죽 끈."""
    def paint(w, h, face):
        a, rng = _base(w, h, (44, 30, 52), face, grad=0.1, noise=0.15)
        y = np.arange(h)[:, None]
        x = np.arange(w)[None, :]
        wrap = ((y + x) % 3) == 0
        a[wrap, :3] = _c(SILV_D)
        return _finish(a)
    return paint


def P_shaft():
    """낫 자루: 흑요 나뭇결 + 가는 보라 결."""
    def paint(w, h, face):
        a, rng = _base(w, h, (34, 24, 46), face, grad=0.05, noise=0.12)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        grain = np.broadcast_to(((x * 5 + y // 3) % 4) == 0, (h, w))
        a[grain, :3] *= 0.7
        vein = np.broadcast_to(((y + x * 7) % 11) == 0, (h, w))
        a[vein, :3] = _c(V_D)
        return _finish(_bevel(a, k=0.3))
    return paint


# ─────────────────────────────── 애니메이션 페인터 ───────────────────────────────
# painter(frame, w, h, face) -> RGBA Image

def _void_field(f, w, h, seed, warp=5.0, zoom=1.0):
    """끓어오르며 소용돌이치는 공허 장(field). 프레임이 이음매 없이 돈다. (h, w) 표준정규."""
    T = 64
    n1, n2, n3 = pnoise(seed), pnoise(seed + 1), pnoise(seed + 2, beta=2.2)
    ph = 2 * math.pi * f / F
    rng = _rng("off", seed)
    ox, oy = rng.integers(0, T, 2)
    yy, xx = np.mgrid[0:h, 0:w]
    X = (np.round(xx * zoom).astype(int) + ox) % T
    Y = (np.round(yy * zoom).astype(int) + oy) % T
    # 소용돌이 왜곡: 느린 장을 따라 좌표를 비튼다 (시간에 따라 각도가 돈다)
    ang = n3[Y, X] * 1.6 + ph
    X2 = np.round(X + warp * np.cos(ang)).astype(int) % T
    Y2 = np.round(Y + warp * np.sin(ang)).astype(int) % T
    return n1[Y2, X2] * math.cos(ph) + n2[Y2, X2] * math.sin(ph)


def G_void(seed=0, hem=0.0, stars=0.035, light=1.0):
    """
    공허 로브 천: 아주 어두운 보라 바탕 위로 소용돌이 성운과 가는 보라 실(등고선),
    반짝이는 별. hem>0 이면 아래쪽이 보라 불꽃처럼 밝아진다.
    """
    def paint(f, w, h, face):
        v = _void_field(f, w, h, seed + (7 if face in ("up", "down") else 0))
        t = 1 / (1 + np.exp(-v * 1.4))
        a = np.zeros((h, w, 4))
        a[..., 3] = 255
        base = _c((12, 5, 22)) + (_c(ROBE) * 1.25 - _c((12, 5, 22))) * (t ** 1.1)[..., None]
        cloud = np.clip((v - 0.7) / 1.2, 0, 1) ** 1.3
        base = base + (_c(ROBE_L) * 1.3 - base) * cloud[..., None] * 0.75
        # 성운 실: 장의 등고선 두 겹 (굵은 보라 + 가는 자홍)
        fil = np.exp(-(np.abs(v - 0.35) / 0.13) ** 2)
        fil2 = np.exp(-(np.abs(v + 0.6) / 0.07) ** 2)
        base = base + (_c(V) - base) * (fil * 0.7 * light)[..., None]
        base = base + (_c(MAG) * 0.8 - base) * (fil2 * 0.45 * light)[..., None]
        # 세로 주름 음영
        if face not in ("up", "down") and w >= 4:
            x = np.arange(w)[None, :]
            base *= (0.82 + 0.25 * np.sin(x / max(2.0, w / 3.0) * math.pi) ** 2)[..., None]
        # 아랫단 빛
        if hem > 0 and face not in ("up", "down"):
            y = np.arange(h)[:, None] / max(1, h - 1)
            g = np.clip((y - (1 - hem)) / hem, 0, 1) ** 1.6
            flick = 0.75 + 0.25 * np.sin(2 * math.pi * f / F * 2 + np.arange(w)[None, :] * 0.9)
            k = (g * flick)[..., None]
            base = base * (1 - k * 0.8) + _ramp(0.45 + 0.3 * g + 0.15 * v.clip(-1, 1))[..., :] * k
        # 별: 픽셀마다 정해진 위상으로 깜박
        rng = _rng("stars", w, h, seed, face)
        sm = rng.random((h, w)) < stars
        ph = rng.random((h, w))
        tw = np.clip(np.cos(2 * math.pi * (f / F + ph)), 0, 1) ** 3
        sc = np.where(rng.random((h, w)) < 0.3, 1.0, 0.0)[..., None]
        star_col = _c(V_W) * (1 - sc) + _c((255, 255, 255)) * sc
        k = (sm * (0.25 + 0.75 * tw))[..., None]
        base = base * (1 - k) + star_col * k
        a[..., :3] = base
        return _finish(a)
    return paint


def _glow_rgb(f, w, h, speed=1, k=0.45, seed=0, axis="y", lo=0.25):
    """보라 → 자홍 → 흰빛으로 흐르는 에너지 색. (h, w, 3)."""
    x = np.arange(w)[None, :].repeat(h, 0)
    y = np.arange(h)[:, None].repeat(w, 1)
    pos = (y if axis == "y" else x) + (x if axis == "y" else y) * 0.35
    v = 0.5 + 0.5 * np.sin(2 * math.pi * speed * f / F - pos * k + seed)
    out = _ramp(lo + (1 - lo) * v ** 1.4)
    rng = _rng("spark", w, h, seed)
    phs = rng.integers(0, F, size=(h, w))
    sel = (rng.random((h, w)) < 0.1) & (phs == f)
    out[sel] = 255
    return out


def G_glow(speed=1, k=0.45, seed=0, axis="y", lo=0.3):
    def paint(f, w, h, face):
        a = np.zeros((h, w, 4))
        a[..., :3] = _glow_rgb(f, w, h, speed, k, seed, axis, lo)
        a[..., 3] = 255
        return _finish(a)
    return paint


def G_voidglow(seed=0, lo=0.0, hi=1.0, cut=None, zoom=None):
    """
    빛나는 공허 소용돌이: 공허 장을 보라→자홍→흰빛 램프로 (복부 핵, 깃 안감, 구슬 껍질).
    cut 이 있으면 장이 그 값보다 낮은 곳을 뚫어 안쪽이 비쳐 보이는 '에너지 우리'가 된다.
    """
    def paint(f, w, h, face):
        z = zoom or max(1.0, 24.0 / max(w, h))     # 작은 면도 소용돌이가 보이게 확대 샘플
        v = _void_field(f, w, h, seed + 100, warp=4, zoom=z)
        t = np.clip(0.5 + v * 0.45, 0, 1) ** 1.6
        fil = np.exp(-(np.abs(v - 0.3) / 0.14) ** 2)
        a = np.zeros((h, w, 4))
        a[..., :3] = _ramp(lo + (hi - lo) * np.clip(t * 0.85 + fil * 0.45, 0, 1))
        a[..., 3] = 255 if cut is None else np.where(v > cut, 255, 0)
        return _finish(a)
    return paint


def G_gem(col_lo=V_D, col_hi=V_W, mid=MAG, phase=0.0):
    """보석: 가운데가 밝고 테두리가 짙은, 맥동하는 면."""
    def paint(f, w, h, face):
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * (f / F + phase))
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        r = np.sqrt(((x - (w - 1) / 2) / max(1, w / 2)) ** 2 + ((y - (h - 1) / 2) / max(1, h / 2)) ** 2)
        t = np.clip(1.1 - r + 0.3 * pulse, 0, 1)
        c = np.where((t < 0.6)[..., None], _c(col_lo) + (_c(mid) - _c(col_lo)) * (t / 0.6)[..., None],
                     _c(mid) + (_c(col_hi) - _c(mid)) * ((t - 0.6) / 0.4)[..., None])
        a = np.zeros((h, w, 4))
        a[..., :3] = c
        if w > 1 and h > 1:
            a[0, 0, :3] = 255   # 반짝 하이라이트
        a[..., 3] = 255
        return _finish(a)
    return paint


def _glyph_mask(n_len, n_thick, seed):
    """룬 글자 줄 마스크 (n_thick 줄, n_len 칸). 글자 3칸 + 틈 1칸."""
    rng = _rng("glyph", seed, n_len, n_thick)
    m = np.zeros((n_thick, n_len), dtype=bool)
    x = 1
    while x + 3 <= n_len:
        g = rng.random((n_thick, 3)) < 0.45
        g[:, rng.integers(0, 3)] = True          # 세로 획 하나는 꼭
        if rng.random() < 0.5:
            g[rng.integers(0, n_thick), :] = True  # 가로 획
        m[:, x:x + 3] = g
        x += 4 + (1 if rng.random() < 0.25 else 0)
    return m


def G_runeband(seed=0, vertical=False, trim=True):
    """
    룬 띠: 짙은 보라 바탕, 은 테두리, 가운데에 흐르듯 빛나는 룬 글자.
    vertical=True 면 글자가 세로로 쌓인다 (앞자락, 망토 가장자리).
    """
    def paint(f, w, h, face):
        L, Tn = (h, w) if vertical else (w, h)
        a = np.zeros((Tn, L, 4))
        a[..., 3] = 255
        a[..., :3] = _c((22, 8, 38))
        x = np.arange(L)[None, :]
        tt = np.arange(Tn)[:, None]
        inner0, inner1 = (1, Tn - 1) if (trim and Tn >= 4) else (0, Tn)
        if face in ("up", "down"):
            a[..., :3] = _c(SILV_D)
            img = a
        else:
            gm = np.zeros((Tn, L), dtype=bool)
            if inner1 - inner0 >= 2:
                gm[inner0:inner1] = _glyph_mask(L, inner1 - inner0, seed)
            wave = 0.5 + 0.5 * np.sin(2 * math.pi * f / F - x * 0.35 + seed)
            col = _ramp(0.42 + 0.42 * wave ** 1.5)
            col = np.broadcast_to(col, (Tn, L, 3))
            # 글자 주변 은은한 빛
            halo = np.array(Image.fromarray((gm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
            halo &= ~gm
            a[halo, :3] = _c(V_D) * (0.55 + 0.35 * np.broadcast_to(wave, (Tn, L))[halo])[..., None]
            a[gm, :3] = col[gm]
            if trim and Tn >= 4:
                a[0, :, :3] = _c(SILV)
                a[-1, :, :3] = _c(SILV_D)
            img = a
        if vertical:
            img = np.transpose(img, (1, 0, 2))
        return _finish(img)
    return paint


def _mask_img(w, h, draw_fn):
    m = Image.new("L", (w, h), 0)
    draw_fn(ImageDraw.Draw(m), w, h)
    return np.array(m) > 0


def G_sigil(draw_fn, speed=1, k=0.3):
    """투명 바탕 위의 문장. 선은 흐르듯 빛나고 바깥에 짙은 보라 테."""
    def paint(f, w, h, face):
        m = _mask_img(w, h, draw_fn)
        a = np.zeros((h, w, 4))
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2)
        v = 0.5 + 0.5 * np.sin(2 * math.pi * speed * f / F - r * k)
        a[..., :3] = _ramp(0.5 + 0.5 * v)
        a[..., 3] = np.where(m, 255, 0)
        mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
        hm = (np.array(mi) > 0) & ~m
        a[hm, :3] = _c(V_D) * 0.6
        a[hm, 3] = 255
        return _finish(a)
    return paint


def sigil_eye(d, w, h):
    """군주의 문장: 원 안의 세로 동공 눈 + 사방으로 뻗는 가시."""
    cx, cy = (w - 1) / 2, (h - 1) / 2
    R = min(w, h) / 2 - 1.5
    d.ellipse((cx - R * 0.62, cy - R * 0.62, cx + R * 0.62, cy + R * 0.62), outline=255, width=1)
    # 눈 (아몬드) + 세로 동공
    d.polygon([(cx - R * 0.5, cy), (cx, cy - R * 0.28), (cx + R * 0.5, cy), (cx, cy + R * 0.28)], outline=255)
    d.line([(cx, cy - R * 0.22), (cx, cy + R * 0.22)], fill=255, width=2)
    for i in range(8):
        ang = i * math.pi / 4 + math.pi / 8
        r0, r1 = R * 0.7, R * (1.0 if i % 2 == 0 else 0.85)
        d.line([(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0),
                (cx + math.cos(ang) * r1, cy + math.sin(ang) * r1)], fill=255, width=1)
    for i in range(4):
        ang = i * math.pi / 2
        d.line([(cx + math.cos(ang) * R * 0.66, cy + math.sin(ang) * R * 0.66),
                (cx + math.cos(ang) * R, cy + math.sin(ang) * R)], fill=255, width=2)


def G_eye():
    """자홍 눈: 가운데 하얀 점, 맥동."""
    def paint(f, w, h, face):
        p = 0.5 + 0.5 * math.sin(2 * math.pi * f / F)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        r = np.sqrt(((x - (w - 1) / 2) / max(1, w / 2)) ** 2 + ((y - (h - 1) / 2) / max(1, h / 2)) ** 2)
        t = np.clip(1.25 - r + 0.2 * p, 0, 1)
        a = np.zeros((h, w, 4))
        a[..., :3] = _c(MAG) + (_c(V_W) - _c(MAG)) * (t ** 2)[..., None]
        a[..., 3] = 255
        return _finish(a)
    return paint


def G_flame(seed=0):
    """공허 불꽃 (손바닥 위): 아래는 하얗고 위로 갈수록 보라, 흔들리는 혀 모양 컷아웃."""
    def paint(f, w, h, face):
        n = pnoise(seed + 50, T=32, beta=1.3)
        yy, xx = np.mgrid[0:h, 0:w]
        ph = 2 * math.pi * f / F
        sx = (xx * 32 // max(1, w) + 3 * math.sin(ph)).astype(int) % 32
        sy = (yy * 32 // max(1, h) + f * 2).astype(int) % 32
        v = n[sy, sx]
        hgt = yy / max(1, h - 1)                   # 이미지 y 는 아래로: 아래쪽이 1 (가장 뜨거움)
        heat = hgt * 1.1 + 0.25 * v
        a = np.zeros((h, w, 4))
        a[..., :3] = _ramp(np.clip(heat, 0, 1))
        a[..., 3] = np.where(heat > 0.22, 255, 0)
        return _finish(a)
    return paint


# ─────────────────────────────── 배치 / 재질 / Kit ───────────────────────────────

class Packer:
    """영역 요청을 모아 높이순으로 한 번에 배치한 뒤 그림을 그린다. (Kit 은 나중에 UV 를 고친다.)"""

    def __init__(self, atlas):
        self.atlas = atlas
        self.items = []

    def request(self, w, h, paint):
        r = Region(self.atlas, 0, 0, int(w), int(h))
        self.items.append((r, paint))
        return r

    def pack(self):
        S = self.atlas.size
        x = y = row = 0
        for r, _ in sorted(self.items, key=lambda it: (-it[0].h, -it[0].w)):
            if x + r.w > S:
                x, y, row = 0, y + row, 0
            if y + r.h > S:
                raise ValueError(f"아틀라스 {self.atlas.name} 가 가득 찼습니다")
            r.x, r.y = x, y
            x += r.w
            row = max(row, r.h)
        for r, paint in self.items:
            paint(r)
        return y + row


class Skin:
    """면 크기에 맞춰 영역을 받아 그리는 재질. 같은 크기 면은 영역을 공유한다."""

    def __init__(self, packer, painter, density=1.0, anim=False, maxpx=48, share=True):
        self.packer, self.painter, self.density, self.anim = packer, painter, density, anim
        self.atlas = packer.atlas
        self.maxpx = maxpx
        self.share = share
        self.cache = {}

    @staticmethod
    def _bucket(v):
        p = 1
        while p * 1.45 < v:
            p *= 2
        return p

    def region(self, w, h, face):
        pw = max(1, min(self.maxpx, w * self.density))
        ph = max(1, min(self.maxpx, h * self.density))
        if self.share:
            pw, ph = self._bucket(pw), self._bucket(ph)
        pw, ph = int(max(1, round(pw))), int(max(1, round(ph)))
        group = "side" if (self.share and face in ("north", "south", "east", "west")) else face
        k = (pw, ph, group)
        if k not in self.cache:
            frames = self.atlas.frames

            def paint(r, pw=pw, ph=ph, face=face):
                if self.anim:
                    for f in range(frames):
                        r.paste(self.painter(f, pw, ph, face), f)
                else:
                    im = self.painter(pw, ph, face)
                    for f in range(frames):
                        r.paste(im, f)
            self.cache[k] = self.packer.request(pw, ph, paint)
        return self.cache[k]


class Kit:
    """파트 하나 (= 모델 하나). 좌표는 보스 발 기준 절대 월드 픽셀, pivot 이 모델 (8,8,8)."""

    def __init__(self, part, scale, pivot):
        self.part = part
        self.m = Model(f"boss/{BOSS}_{part}")
        self.s = scale
        self.pv = list(pivot)
        self.fix = []

    def key(self, atlas):
        k = atlas.name.split("/")[-1].replace(BOSS + "_", "")
        if k not in self.m.textures:
            self.m.use(k, atlas)
        return k

    def U(self, p):
        return [8 + (p[i] - self.pv[i]) / self.s for i in range(3)]

    def box(self, frm, to, skin, rot=None, light=0, faces=None, over=None, shade=None):
        frm, to = list(frm), list(to)
        for i in range(3):
            if frm[i] > to[i]:
                frm[i], to[i] = to[i], frm[i]
        dx, dy, dz = (to[i] - frm[i] for i in range(3))
        dims = {"north": (dx, dy), "south": (dx, dy), "east": (dz, dy), "west": (dz, dy),
                "up": (dx, dz), "down": (dx, dz)}
        fd = {}
        for f in (faces or FACES):
            sk = (over or {}).get(f, skin)
            if sk is None:
                continue
            fd[f] = (self.key(sk.atlas), sk.region(*dims[f], f))
        rotation = None
        if rot and rot[1]:
            rotation = {"origin": [round(v, 4) for v in self.U(rot[2])], "axis": rot[0], "angle": rot[1]}
        if shade is None:
            shade = not (light >= 8)
        el = self.m.box(self.U(frm), self.U(to), dict(fd), light=light, shade=shade, rotation=rotation)
        for f, v in fd.items():
            self.fix.append((el, f, v[1]))
        return el

    def cbox(self, c, size, skin, **kw):
        """중심/크기로 박스."""
        sx, sy, sz = size
        return self.box((c[0] - sx / 2, c[1] - sy / 2, c[2] - sz / 2), (c[0] + sx / 2, c[1] + sy / 2, c[2] + sz / 2),
                        skin, **kw)

    def ring(self, center, phi, r, width, y0, y1, thick, skin, light=0, faces=None, over=None):
        """
        중심축 둘레 각도 phi(도, 22.5 배수, 0 = +Z 앞) 위치에 접선 방향 판을 놓는다.
        가까운 정방향(0/90/180/270)에 놓은 뒤 중심축 기준 y 회전(-45..45) 으로 돌린다.
        """
        base = int(round(phi / 90.0)) * 90
        d = phi - base
        if d > 45:
            base, d = base + 90, d - 90
        cx, _, cz = center
        b = base % 360
        if b == 0:
            frm, to = (cx - width / 2, y0, cz + r - thick / 2), (cx + width / 2, y1, cz + r + thick / 2)
        elif b == 180:
            frm, to = (cx - width / 2, y0, cz - r - thick / 2), (cx + width / 2, y1, cz - r + thick / 2)
        elif b == 90:
            frm, to = (cx + r - thick / 2, y0, cz - width / 2), (cx + r + thick / 2, y1, cz + width / 2)
        else:
            frm, to = (cx - r - thick / 2, y0, cz - width / 2), (cx - r + thick / 2, y1, cz + width / 2)
        # 오른손 좌표계 y 회전: +Z 를 +X 쪽으로 돌리는 것이 양의 각도
        rot = ("y", d, (cx, (y0 + y1) / 2, cz)) if abs(d) > 1e-6 else None
        return self.box(frm, to, skin, rot=rot, light=light, faces=faces, over=over)

    def spike(self, base, length, width, skin, axis="z", angle=0, steps=3, down=False, light=0,
              depth=None, taper=0.78, origin=None):
        """끝이 가늘어지는 가시. 회전 전에는 +Y(또는 -Y) 로 뻗고, base(또는 origin) 기준 한 축 회전."""
        bx, by, bz = base
        d = -1 if down else 1
        seg = length / steps
        dep = depth or width
        for i in range(steps):
            t = i / steps
            wi, di = width * (1 - taper * t), dep * (1 - taper * t)
            y0 = by + d * seg * i
            y1 = by + d * seg * (i + 1) + (d * 0.3 if i < steps - 1 else 0)
            sk = skin[min(len(skin) - 1, int(i * len(skin) / steps))] if isinstance(skin, list) else skin
            self.box((bx - wi / 2, y0, bz - di / 2), (bx + wi / 2, y1, bz + di / 2), sk,
                     rot=(axis, angle, origin or base), light=light)
        return tip_of(base, length * d, axis, angle)

    def chain(self, base, segs, skin, light=0, down=False):
        """구부러진 뿔/가시: segs = [(길이, 굵기, 축, 각도), ...] 를 이어 붙인다."""
        p = list(base)
        for length, width, axis, angle in segs:
            self.spike(p, length + width * 0.25, width, skin, axis, angle, steps=1, down=down, light=light,
                       taper=0)
            p = tip_of(p, length * (-1 if down else 1), axis, angle)
        return p

    def fix_uvs(self):
        for el, f, reg in self.fix:
            el["faces"][f]["uv"] = reg.uv()

    def write(self, assets_root):
        self.m.write(assets_root)
        return "augsky:" + self.m.name


def tip_of(base, length, axis, angle):
    v = _rot_matrix(axis, angle) @ np.array([0.0, length, 0.0])
    return [base[0] + v[0], base[1] + v[1], base[2] + v[2]]


# ─────────────────────────────── 재질 묶음 ───────────────────────────────
BLADE_W, BLADE_H = 54, 34   # 낫 날 스프라이트 크기 (1 픽셀 = 월드 1 픽셀)


class Mats:
    def __init__(self):
        self.A_body = Atlas(f"boss/{BOSS}_body", 128, seed=21)
        self.A_head = Atlas(f"boss/{BOSS}_head", 64, seed=22)
        self.A_void = Atlas(f"boss/{BOSS}_void", 128, frames=F, frametime=FRAMETIME, seed=23)
        self.A_glow = Atlas(f"boss/{BOSS}_glow", 128, frames=F, frametime=FRAMETIME, seed=24)
        self.A_blade = Atlas(f"boss/{BOSS}_blade", 64, frames=F, frametime=FRAMETIME, seed=25)
        self.packers = [Packer(a) for a in (self.A_body, self.A_head, self.A_void, self.A_glow)]
        B, H, Vd, G = self.packers
        # 몸 (정적)
        self.plate = Skin(B, P_plate(OBS), maxpx=32)
        self.plate_d = Skin(B, P_plate((26, 20, 40), seed=3), maxpx=32)
        self.silver = Skin(B, P_metal(SILV), maxpx=16)
        self.bone = Skin(B, P_bone())
        self.cloth = Skin(B, P_cloth(ROBE))
        self.cloth_d = Skin(B, P_cloth(ROBE_D))
        self.chest = Skin(B, P_chest(), density=2, share=False)
        self.shaft = Skin(B, P_shaft(), maxpx=64)
        self.grip = Skin(B, P_grip())
        # 머리 (정적)
        self.dark = Skin(H, P_dark())
        self.face = Skin(H, P_face(), density=2.4, share=False)
        self.jaw = Skin(H, P_jaw(), density=2, share=False)
        self.h_bone = Skin(H, P_bone())
        # 공허 천 (애니메이션)
        self.void = Skin(Vd, G_void(seed=1, stars=0.025), anim=True, maxpx=40)
        self.void2 = Skin(Vd, G_void(seed=31, stars=0.02), anim=True, maxpx=40)
        self.void_hem = Skin(Vd, G_void(seed=2, hem=0.5), anim=True, maxpx=40)
        # 빛 (애니메이션)
        self.glow = Skin(G, G_glow(), anim=True, maxpx=16)
        self.core = Skin(G, G_voidglow(seed=1, lo=0.0, hi=0.95), anim=True, maxpx=16)
        self.lining = Skin(G, G_voidglow(seed=2, lo=0.0, hi=0.75), anim=True, maxpx=24)
        self.cage = Skin(G, G_voidglow(seed=3, lo=0.05, hi=0.92, cut=-0.35, zoom=3.0), anim=True, maxpx=8)
        self.gem = Skin(G, G_gem(), anim=True, maxpx=6)
        self.gem2 = Skin(G, G_gem(phase=0.5), anim=True, maxpx=6)
        self.eye = Skin(G, G_eye(), anim=True, maxpx=4)
        self.rune = Skin(G, G_runeband(seed=3), anim=True, maxpx=64, share=False)
        self.rune_v = Skin(G, G_runeband(seed=5, vertical=True), anim=True, maxpx=48, share=False)
        self.rune_thin = Skin(G, G_runeband(seed=7, trim=False), anim=True, maxpx=32, share=False)
        self.sig_eye = Skin(G, G_sigil(sigil_eye), density=2, anim=True, maxpx=40, share=False)
        self.flame = Skin(G, G_flame(), anim=True, maxpx=8)

    def atlases(self):
        return [self.A_body, self.A_head, self.A_void, self.A_glow, self.A_blade]


# ─────────────────────────────── 기준 위치 (월드 픽셀) ───────────────────────────────
WAIST_Y = 46
SR = (-17, 70, 0)        # 오른 어깨 (보스 오른쪽 = -X)
SL = (17, 70, 0)         # 왼 어깨
NECK = (0, 74, 0)
CROWN = (0, 108, 0)
CAPE = (0, 72, -11)
SHAFT_X, SHAFT_Z = -17.0, 11.0


def rot_pt(p, axis, angle, origin):
    """점 p 를 origin 기준으로 axis 축 angle 도 회전."""
    v = _rot_matrix(axis, angle) @ (np.array(p, dtype=float) - np.array(origin, dtype=float))
    return list(v + np.array(origin, dtype=float))


def stepped_round(k, y0, y1, D, skin, light=0, over=None, grow=0.0):
    """세 박스로 만든 '계단식 원' 단면 (마크 스타일 둥근 몸통)."""
    D = D + grow
    k.box((-D / 2, y0, -0.27 * D), (D / 2, y1, 0.27 * D), skin, light=light, over=over)
    k.box((-0.27 * D, y0, -D / 2), (0.27 * D, y1, D / 2), skin, light=light, over=over)
    k.box((-0.42 * D, y0, -0.42 * D), (0.42 * D, y1, 0.42 * D), skin, light=light, over=over)


# ─────────────────────────────── 파트: 로브 (허리 아래) ───────────────────────────────
ROBE_TIERS = [(34, 44, 22), (26, 35, 25.5), (19, 27, 29.5), (12, 20, 34), (6, 13, 38.5)]   # (y0, y1, 지름)


def build_robe(M):
    k = Kit("robe", 2.5, (0, WAIST_Y, 0))
    last = len(ROBE_TIERS) - 1
    for i, (y0, y1, D) in enumerate(ROBE_TIERS):
        side = M.void_hem if i == last else (M.void if i % 2 == 0 else M.void2)
        stepped_round(k, y0, y1, D, side, light=4, over={"up": M.void, "down": M.void})
        # 앞자락: 은 테두리의 가는 세로 룬 띠
        k.box((-2.5, y0, D / 2 - 0.4), (2.5, y1, D / 2 + 0.7), M.rune_v, light=15,
              over={"east": M.silver, "west": M.silver, "up": M.silver, "down": M.silver})
        if i in (1, 3):
            stepped_round(k, y0 - 0.2, y0 + 0.9, D, M.silver, grow=0.5)
    # 허리띠 + 버클 보석
    stepped_round(k, 40, 47, 21, M.plate)
    stepped_round(k, 46.2, 47.4, 21, M.silver, grow=0.5)
    k.box((-3.6, 40.5, 10.6), (3.6, 47.4, 11.6), M.silver, rot=("z", 45, (0, 44, 11)))
    k.box((-2.4, 41.7, 11.2), (2.4, 46.2, 12.4), M.gem, light=15, rot=("z", 45, (0, 44, 11)))
    # 밑단 룬 띠 (빛남)
    stepped_round(k, 6.2, 9.4, 38.5, M.rune, light=15, grow=0.7, over={"up": M.silver, "down": M.silver})
    # 너덜너덜한 밑단 자락 (16 방향)
    rng = _rng("tatter", 1)
    for j in range(16):
        phi = j * 22.5
        L = 2.5 + rng.random() * 3.0
        r = 38.5 * (0.46 if j % 2 == 0 else 0.5)
        k.ring((0, 0, 0), phi, r, 3.6 if j % 2 == 0 else 2.6, 6.4 - L, 6.6, 1.0, M.void_hem, light=6)
    return k


# ─────────────────────────────── 파트: 몸통 ───────────────────────────────

def build_torso(M):
    k = Kit("torso", 2.5, (0, WAIST_Y, 0))
    # 복부: 갈비뼈 사이로 빛나는 공허 핵
    k.box((-8, 45, -6.5), (8, 58, 1.5), M.cloth_d)
    k.box((-6.5, 46.5, -4), (6.5, 57.5, 3.4), M.core, light=13)
    k.box((-1.5, 45, -7.5), (1.5, 58, -5), M.bone)                    # 등뼈
    k.box((-1.1, 46.5, 3.2), (1.1, 58, 5.2), M.bone)                  # 흉골
    for y in (48.0, 51.2, 54.4):
        for s in (-1, 1):
            k.box((s * 1.0, y, 3.4), (s * 7.4, y + 1.6, 5.0), M.bone)          # 앞 갈비
            k.box((s * 7.0, y - 0.4, -5.5), (s * 8.6, y + 1.4, 5.0), M.bone)   # 옆 갈비
    # 흉갑
    k.box((-11, 57, -7.5), (11, 65, 6.5), M.plate)
    k.box((-14, 63, -8.5), (14, 73, 7.5), M.plate, over={"south": M.chest})
    k.box((-11.3, 57, -7.8), (11.3, 58.8, 6.9), M.rune_thin, light=15,
          over={"up": M.silver, "down": M.silver})
    # 공허 심장석 (마름모) + 은 받침
    k.box((-3.6, 64.4, 7.2), (3.6, 71.6, 8.4), M.silver, rot=("z", 45, (0, 68, 8)))
    k.box((-2.4, 65.6, 7.8), (2.4, 70.4, 9.6), M.gem, light=15, rot=("z", 45, (0, 68, 8)))
    k.box((-0.6, 59, 7.2), (0.6, 64.5, 8.2), M.glow, light=15)      # 심장석에서 흘러내리는 빛줄기
    # 목
    k.box((-3.5, 72, -4), (3.5, 76, 2.5), M.dark)
    # 높은 깃: 머리 뒤로 솟아 양옆으로 벌어진다. 안쪽은 소용돌이치는 빛.
    k.box((-9, 70, -11.5), (9, 92, -8.5), M.void, light=6, over={"south": M.lining})
    for s in (-1, 1):
        o = (s * 9, 68, -9.5)
        r = ("z", -s * 22.5, o)
        k.box((s * 7.5, 68, -11.5), (s * 15.5, 95, -7.5), M.void, light=6, over={"south": M.lining}, rot=r)
        k.box((s * 15.5, 68, -11.8), (s * 16.6, 95, -7.2), M.silver, rot=r)
        top = rot_pt((s * 12.5, 94.5, -9.5), "z", -s * 22.5, o)
        k.spike(top, 11, 2.8, [M.plate, M.plate, M.bone], axis="z", angle=-s * 22.5, steps=3, taper=0.85)
    for x, hgt in ((-5.5, 7), (-2, 11), (2, 11), (5.5, 7)):
        k.spike((x, 91.5, -10), hgt, 2.4, [M.plate, M.plate, M.bone], steps=3, taper=0.85)
    # 견갑: 둥근 윗단 + 겹판 두 장, 은 테, 보석, 뼈 가시
    for s in (-1, 1):
        k.box((s * 12, 66, -8.5), (s * 24, 75, 8.5), M.plate)
        k.box((s * 13, 74.5, -7.5), (s * 23, 78, 7.5), M.plate_d)
        k.box((s * 12.2, 74.4, -8.7), (s * 24.2, 75.4, 8.7), M.silver)
        k.box((s * 13.5, 61.5, -8), (s * 26, 67, 8), M.plate_d)
        k.box((s * 15, 57, -7), (s * 27, 62, 7), M.plate)
        k.box((s * 13.5, 61.3, -8.2), (s * 26.2, 62.3, 8.2), M.silver)
        k.box((s * 15, 56.8, -7.2), (s * 27.2, 57.8, 7.2), M.silver)
        k.box((s * 24.0, 69.2, -2.2), (s * 24.8, 73.6, 2.2), M.gem2, light=15)
        k.box((s * 26.0, 63.2, -1.5), (s * 26.8, 65.8, 1.5), M.gem, light=15)
        k.chain((s * 18, 77.5, 0), [(5, 3.2, "z", -s * 22.5), (5, 2.4, "z", -s * 45), (4, 1.5, "z", -s * 45)],
                M.plate)
        k.spike(tip_of(tip_of(tip_of((s * 18, 77.5, 0), 5, "z", -s * 22.5), 5, "z", -s * 45), 4, "z", -s * 45),
                3, 1.2, M.bone, axis="z", angle=-s * 45, steps=1)
        for zs in (-1, 1):
            k.chain((s * 18.5, 77.5, zs * 5), [(4, 2.6, "x", zs * 22.5), (4, 1.6, "x", zs * 45)], M.plate)
            k.spike(tip_of(tip_of((s * 18.5, 77.5, zs * 5), 4, "x", zs * 22.5), 4, "x", zs * 45), 2.5, 1.0,
                    M.bone, axis="x", angle=zs * 45, steps=1)
    return k


# ─────────────────────────────── 파트: 머리 (두건 + 해골) ───────────────────────────────

def build_head(M):
    k = Kit("head", 1.75, NECK)
    # 두건: 위로 갈수록 좁아지는 둥근 모양, 앞챙이 앞으로 나와 얼굴을 그늘지게 한다
    k.box((-8.5, 75, -9), (8.5, 90, 4), M.void, light=4)
    for s in (-1, 1):
        k.box((s * 7, 74, -7), (s * 9.8, 89, 9.6), M.void, light=4)
    k.box((-8.6, 88, -8), (8.6, 92, 10.6), M.void, light=4)
    k.box((-6.6, 91.5, -7), (6.6, 95, 7.5), M.void, light=4)
    k.box((-4.2, 94.5, -6.5), (4.2, 98, 3), M.void, light=4)
    k.box((-2.2, 97, -8), (2.2, 103, -1.5), M.void, light=4, rot=("x", -22.5, (0, 97, -4)))
    # 어깨에 얹힌 두건 자락
    k.box((-12.5, 72, -10.5), (12.5, 77, 8.5), M.void, light=4)
    k.box((-12.8, 72, -10.8), (12.8, 73, 8.8), M.silver)
    # 두건 앞 테두리: 가는 룬 선
    k.box((-8.7, 88, 10.5), (8.7, 89.3, 11.1), M.rune_thin, light=12)
    for s in (-1, 1):   # 챙 양 끝에서 늘어진 짧은 은 장식
        k.box((s * 8.1, 84.5, 9.8), (s * 9.3, 88.2, 11.0), M.silver)
        k.box((s * 8.2, 83.3, 10.0), (s * 9.2, 84.6, 10.9), M.gem2, light=15)
    # 안쪽 어둠
    k.box((-7.2, 75, -5), (7.2, 88.5, 3), M.dark)
    # 해골
    k.box((-5, 78, 0.5), (5, 88, 7.5), M.h_bone, over={"south": M.face})
    k.box((-4, 74.6, 1), (4, 78.6, 7), M.h_bone, over={"south": M.jaw})
    k.box((-5.6, 79.5, 2), (5.6, 81.5, 6.8), M.h_bone)                     # 광대
    # 눈: 빛 테 + 하얀 심
    for s in (-1, 1):
        k.box((s * 0.9, 82.0, 7.55), (s * 4.0, 84.6, 7.62), M.gem, light=15, faces=["south"])
        k.box((s * 1.7, 82.7, 7.62), (s * 3.2, 83.9, 7.7), M.eye, light=15, faces=["south"])
        k.box((s * 3.6, 83.6, 4.0), (s * 4.4, 84.4, 7.5), M.glow, light=15)   # 눈에서 흩날리는 빛 꼬리
    return k


# ─────────────────────────────── 파트: 떠 있는 왕관 ───────────────────────────────

def build_crown(M):
    k = Kit("crown", 1.5, CROWN)
    c = CROWN
    cy = c[1]
    R = 9.5
    for j in range(8):
        phi = j * 45
        gem = M.gem if j % 2 == 0 else M.gem2
        k.ring(c, phi, R, 8.2, cy - 3.5, cy + 0.5, 1.8, M.plate)                 # 띠
        k.ring(c, phi, R + 0.3, 8.4, cy - 4.0, cy - 3.0, 2.0, M.silver)          # 아래 은 테
        k.ring(c, phi, R + 0.3, 8.4, cy + 0.2, cy + 0.9, 2.0, M.silver)          # 위 은 테
        k.ring(c, phi, R + 1.0, 2.2, cy - 2.6, cy - 0.4, 0.6, gem, light=15)     # 보석
        k.ring(c, phi, 7.2, 6.0, cy - 5.6, cy - 4.8, 0.8, M.glow, light=15)      # 아래 빛 고리
    # 큰 가시 8 개 (정방향 높게, 대각 낮게) — 대각 가시는 중심축 기준 45° 회전
    for j in range(8):
        phi = j * 45
        base = int(round(phi / 90.0)) * 90
        d = phi - base
        b = math.radians(base)
        p = (c[0] + R * math.sin(b), cy + 0.6, c[2] + R * math.cos(b))
        hgt = 15 if j % 2 == 0 else 10
        k.spike(p, hgt, 2.4, [M.plate, M.plate_d, M.plate, M.plate_d], axis="y", angle=d, steps=4, taper=0.85,
                origin=(c[0], cy, c[2]))
        tip = (p[0], cy + 0.6 + hgt - 1.0, p[2])
        k.box((tip[0] - 0.45, tip[1], tip[2] - 0.45), (tip[0] + 0.45, tip[1] + 1.5, tip[2] + 0.45), M.glow,
              light=15, rot=("y", d, (c[0], cy, c[2])) if d else None)
    # 작은 가시 8 개 (22.5° 사이)
    for j in range(8):
        k.ring(c, 22.5 + j * 45, R, 1.5, cy + 0.5, cy + 5.5, 1.5, M.plate_d)
    # 가운데 떠 있는 보석
    k.box((-1.6, cy + 1.4, -1.6), (1.6, cy + 4.6, 1.6), M.gem, light=15, rot=("y", 45, (0, cy + 3, 0)))
    return k


# ─────────────────────────────── 파트: 팔 ───────────────────────────────

def _sleeve(k, M, s, elbow, angle):
    """팔꿈치 아래 종 모양 소매 (회전된 그룹)."""
    ex = elbow[0]
    rot = ("x", angle, elbow)
    k.box((ex - 7.5, 39, -7), (ex + 7.5, 57, 7), M.void_hem, light=5, rot=rot)
    k.box((ex - 7.8, 38.6, -7.3), (ex + 7.8, 41.2, 7.3), M.rune, light=15, rot=rot)
    rng = _rng("cuff", s)
    for i, x in enumerate((-6.5, -3.0, 0.5, 4.0, 6.6)):
        L = 3 + rng.random() * 4
        for z in ((-6.6,) if i % 2 else (6.6,)):
            k.box((ex + x - 1.2, 38.8 - L, z - 0.5), (ex + x + 1.2, 39.2, z + 0.5), M.void_hem, light=6, rot=rot)
    for z in (-3, 2):
        L = 3 + rng.random() * 3
        k.box((ex - s * 7.0 - 0.5, 38.8 - L, z - 1.2), (ex - s * 7.0 + 0.5, 39.2, z + 1.2), M.void_hem, light=6, rot=rot)


def build_right_arm(M):
    k = Kit("right_arm", 2.0, SR)
    k.box((-23, 55, -5.5), (-11, 71, 5.5), M.void, light=4)
    k.box((-23.3, 55, -5.8), (-10.7, 56.6, 5.8), M.silver)
    elbow = (-17, 56, 0)
    _sleeve(k, M, -1, elbow, -22.5)
    # 뼈 손: 손바닥은 자루 뒤, 손가락은 자루 앞을 감싼다
    x0, x1 = SHAFT_X - 2.6, SHAFT_X + 2.6
    k.box((x0, 33.5, 7.4), (x1, 40, 9.6), M.bone)                       # 손바닥/손등
    k.box((x0 - 0.6, 37.5, 6.5), (x1 + 0.6, 40.8, 9.8), M.bone)          # 손목
    for i, y in enumerate((33.4, 35.0, 36.6, 38.2)):
        k.box((x0 - 0.2, y, 12.4), (x1 + 0.2, y + 1.2, 13.8), M.bone)    # 손가락 마디 (앞)
        k.box((x0 - 0.2, y, 9.4), (x0 + 1.0, y + 1.2, 13.8), M.bone)     # 손가락 옆
    k.box((x1 - 0.8, 38.5, 9.4), (x1 + 0.6, 42.5, 13.0), M.bone)         # 엄지
    return k


def build_left_arm(M):
    k = Kit("left_arm", 2.0, SL)
    k.box((11, 55, -5.5), (23, 71, 5.5), M.void, light=4)
    k.box((10.7, 55, -5.8), (23.3, 56.6, 5.8), M.silver)
    elbow = (17, 56, 0)
    ang = -45
    _sleeve(k, M, 1, elbow, ang)
    rot = ("x", ang, elbow)
    # 앞으로 내민 뼈 손 (매달린 좌표로 만든 뒤 소매와 같이 회전)
    k.box((14.2, 33.5, -2.6), (19.8, 39.4, 2.6), M.bone, rot=rot)
    k.box((13.6, 37.6, -3.2), (20.4, 40.6, 3.2), M.bone, rot=rot)
    for i, x in enumerate((14.6, 16.4, 18.2, 20.0)):
        L = 5.5 if i in (1, 2) else 4.5
        k.box((x - 0.7, 33.6 - L, -0.7 + 1.6), (x + 0.7, 33.8, 0.7 + 1.6), M.bone, rot=rot)
        k.box((x - 0.5, 33.6 - L - 2.4, -0.5 + 2.6), (x + 0.5, 33.6 - L + 0.2, 0.5 + 2.6), M.bone, rot=rot)
    k.box((12.6, 34.5, 0.5), (14.0, 38.5, 4.0), M.bone, rot=rot)         # 엄지
    # 손 위의 공허 불꽃 (회전하지 않음, 위로 타오름)
    hc = tip_of(elbow, -21, "x", ang)
    fx, fy, fz = hc[0], hc[1] + 4.5, hc[2] + 3.5
    k.cbox((fx, fy - 0.6, fz), (2.6, 2.6, 2.6), M.gem, light=15, rot=("y", 45, (fx, fy, fz)))
    k.cbox((fx, fy, fz), (4.4, 4.0, 4.4), M.flame, light=15)
    k.cbox((fx, fy + 3.2, fz), (3.4, 3.6, 3.4), M.flame, light=15, rot=("y", 45, (fx, fy, fz)))
    k.cbox((fx, fy + 6.2, fz), (2.2, 3.4, 2.2), M.flame, light=15)
    k.cbox((fx, fy + 8.8, fz), (1.2, 2.6, 1.2), M.flame, light=15, rot=("y", 45, (fx, fy, fz)))
    k.cbox((fx + 2.6, fy + 6.5, fz - 1), (1, 1, 1), M.glow, light=15)
    k.cbox((fx - 2.0, fy + 8.0, fz + 1.5), (0.8, 0.8, 0.8), M.glow, light=15)
    return k


# ─────────────────────────────── 파트: 낫 ───────────────────────────────

def blade_masks():
    """
    낫 날 스프라이트의 영역 마스크 (body=몸, spine=등, edge=날끝). (H, W) bool 세 개.
    등(위, 볼록)은 2차 베지어 곡선, 날(아래, 오목)은 그 곡선을 안쪽으로 밀어낸 선. 끝으로 갈수록 가늘다.
    """
    W, H = BLADE_W, BLADE_H
    ss = 4
    t = np.linspace(0, 1, 240)
    P0, P1, P2 = np.array((W - 1.0, 7.0)), np.array((W * 0.25, -4.0)), np.array((2.0, H - 1.0))
    spine = ((1 - t) ** 2)[:, None] * P0 + (2 * (1 - t) * t)[:, None] * P1 + (t ** 2)[:, None] * P2
    dv = np.gradient(spine, axis=0)
    dv /= np.linalg.norm(dv, axis=1, keepdims=True)
    nrm = np.stack([-dv[:, 1], dv[:, 0]], 1)
    if nrm[len(nrm) // 2, 1] < 0:
        nrm = -nrm
    thick = 14.0 * (1 - t) ** 0.85 + 0.3
    edge = spine + nrm * thick[:, None]
    S = lambda pts: [tuple(p * ss) for p in pts]

    def draw(fn):
        im = Image.new("L", (W * ss, H * ss), 0)
        fn(ImageDraw.Draw(im))
        return np.array(im) > 0
    full = draw(lambda d: d.polygon(S(spine) + S(edge[::-1]), fill=255))
    sp = draw(lambda d: d.line(S(spine), fill=255, width=int(2.2 * ss * 2))) & full
    ed = draw(lambda d: d.line(S(edge), fill=255, width=int(2.8 * ss * 2))) & full & ~sp
    down = lambda m: m.reshape(H, ss, W, ss).mean(axis=(1, 3)) > 0.5
    f, s, e = down(full), down(sp), down(ed)
    return f & ~s & ~e, s & f, e & f


def paint_blade(atlas):
    """날을 아틀라스에 그린다 (프레임마다 날끝 빛이 뿌리에서 끝으로 흐른다)."""
    body, spine, edge = blade_masks()
    H, W = body.shape
    reg = atlas.alloc(W, H)
    yy, xx = np.mgrid[0:H, 0:W]
    along = (W - xx) + (H - yy) * 0.6          # 뿌리에서 끝으로
    for f in range(F):
        a = np.zeros((H, W, 4))
        v = _void_field(f, W, H, 77, warp=3)
        base = _c((16, 6, 28)) + (_c((52, 20, 90)) - _c((16, 6, 28))) * np.clip(0.5 + v * 0.35, 0, 1)[..., None]
        vein = np.exp(-(np.abs(v - 0.3) / 0.12) ** 2)
        base = base + (_c(V) - base) * vein[..., None] * 0.8
        a[body, :3] = base[body]
        wave = 0.5 + 0.5 * np.sin(2 * math.pi * f / F * 2 - along * 0.28)
        a[edge, :3] = _ramp(0.55 + 0.45 * wave)[edge]
        # 날끝 맨 바깥 줄은 늘 하얗게
        a[spine, :3] = _c(OBS)
        sp_top = spine & ~np.roll(spine, 1, axis=0)
        a[sp_top, :3] = _c(SILV)
        a[spine & (xx % 6 == 0), :3] = _c(SILV_D)
        a[..., 3] = np.where(body | spine | edge, 255, 0)
        reg.paste(_finish(a), f)
    return reg, (body, spine, edge)


def build_scythe(M):
    k = Kit("scythe", 3.2, SR)
    x, z = SHAFT_X, SHAFT_Z
    hw = 1.4
    k.box((x - hw, 3, z - hw), (x + hw, 31, z + hw), M.shaft)
    k.box((x - hw, 31, z - hw), (x + hw, 45, z + hw), M.grip)
    k.box((x - hw, 45, z - hw), (x + hw, 96, z + hw), M.shaft)
    for y in (30.2, 44.2, 62, 80):
        k.box((x - 1.9, y, z - 1.9), (x + 1.9, y + 1.6, z + 1.9), M.silver)
    for y in (54, 71, 88):
        k.box((x - 1.75, y, z - 1.75), (x + 1.75, y + 2.4, z + 1.75), M.rune_thin, light=15)
    # 아래 끝: 가시 물미 + 보석
    k.box((x - 2.2, 2.2, z - 2.2), (x + 2.2, 4.4, z + 2.2), M.silver)
    k.spike((x, 2.4, z), 6.5, 3.2, [M.plate, M.plate, M.glow], down=True, steps=3)
    # 머리: 은 고리 + 해골 장식 (눈이 빛남)
    k.box((x - 2.6, 94, z - 2.6), (x + 2.6, 96.6, z + 2.6), M.silver)
    k.box((x - 3.2, 96.4, z - 3.2), (x + 3.2, 102.4, z + 3.2), M.h_bone, over={"south": M.face})
    for s in (-1, 1):
        k.box((x + s * 0.5, 99.0, z + 3.25), (x + s * 2.3, 100.3, z + 3.32), M.eye, light=15, faces=["south"])
    k.box((x - 2.4, 102.2, z - 2.4), (x + 2.4, 103.6, z + 2.4), M.silver)
    k.spike((x, 103.4, z), 9, 2.6, [M.plate, M.plate_d, M.glow], steps=3)
    # 반대쪽(안쪽) 갈고리 가시
    k.chain((x + 3, 99.0, z), [(4.5, 2.4, "z", -45), (4.5, 1.6, "z", -22.5)], M.plate)
    # 날: 픽셀 그림을 두께 있게 뽑아낸다 (등은 두껍고 어둡게, 몸과 날끝은 빛남)
    reg, (body, spine, edge) = paint_blade(M.A_blade)
    key = k.key(M.A_blade)
    root_x, top_y = x - 2.6, 110.0       # 날 뿌리(오른쪽 위) 위치
    ox = root_x - BLADE_W
    oy = top_y - BLADE_H
    sprite = M.A_blade.img.crop((reg.x, reg.y, reg.x + reg.w, reg.y + reg.h))
    u = k.U((ox, oy, z))
    extrude(k.m, key, reg, sprite,
            depth_of=lambda px_, py_: (3.0 if spine[py_, px_] else (2.0 if body[py_, px_] else 1.2)) / k.s,
            px=1.0 / k.s, origin=(u[0], u[1]), zc=u[2],
            light_of=lambda px_, py_: 0 if spine[py_, px_] else 15)
    return k


# ─────────────────────────────── 파트: 망토 ───────────────────────────────

def build_cape(M):
    k = Kit("cape", 3.2, CAPE)
    k.box((-15, 64, -13), (15, 74, -8), M.void, light=4)
    panels = [(46, 66, 31, -13.4, -11.2), (30, 48, 35, -15.2, -13.0), (16, 32, 39, -18.0, -15.8),
              (6, 18, 43, -21.0, -18.8)]
    for i, (y0, y1, w, z0, z1) in enumerate(panels):
        sk = M.void_hem if i == 3 else (M.void2 if i % 2 else M.void)
        k.box((-w / 2, y0, z0), (w / 2, y1, z1), sk, light=4)
    # 등 문장
    k.box((-8.5, 31, -15.3), (8.5, 47.5, -15.25), M.sig_eye, light=15, faces=["north"])
    # 가장자리 룬 줄
    for (y0, y1, w, z0, z1) in panels[1:]:
        for s in (-1, 1):
            k.box((s * (w / 2 - 2.4), y0 + 0.5, z0 - 0.3), (s * (w / 2 - 0.6), y1 - 0.5, z0), M.rune_v, light=15,
                  faces=["north"])
    y0, y1, w, z0, z1 = panels[3]
    k.box((-w / 2 - 0.3, 6, z0 - 0.3), (w / 2 + 0.3, 9.2, z1 + 0.3), M.rune, light=15,
          over={"up": M.silver, "down": M.silver})
    # 너덜너덜한 끝자락
    rng = _rng("cape", 2)
    xs = np.linspace(-19.5, 19.5, 11)
    for i, xx in enumerate(xs):
        L = 2.5 + rng.random() * 3.5
        k.box((xx - 1.7, 6.2 - L, -20.6), (xx + 1.7, 6.4, -19.2), M.void_hem, light=6)
    return k


# ─────────────────────────────── 파트: 공허 구슬 ───────────────────────────────

def build_orb(M):
    k = Kit("orb", 1.0, (0, 0, 0))
    o = (0, 0, 0)
    # 하얗게 타는 심 + 그 둘레를 감싼 구멍 뚫린 공허 에너지 우리 (계단식 구)
    k.cbox(o, (3.2, 3.2, 3.2), M.gem, light=15, rot=("y", 45, o))
    for size in ((6.4, 4.2, 4.2), (4.2, 6.4, 4.2), (4.2, 4.2, 6.4)):
        k.cbox(o, size, M.cage, light=15)
    # 적도 빛 고리 (8 조각)
    for j in range(8):
        k.ring(o, j * 45, 5.4, 4.6, -0.35, 0.35, 0.7, M.glow, light=15)
    # 위아래 수정 가시
    for s in (-1, 1):
        k.spike((0, s * 3.0, 0), 4.0, 1.6, M.glow, steps=2, down=s < 0, light=15, taper=0.6)
    return k


# ─────────────────────────────── 리그 스펙 ───────────────────────────────

def px(v):
    return [round(c / 16.0, 4) for c in v]


BODY_BOB = {"type": "bob", "amplitude": 0.08, "period": 80, "phase": 0.0}


def rig_spec(models):
    parts = []

    def add(pid, model, off, scale, frame="body", anims=()):
        parts.append({"id": pid, "model": model, "offset": px(off), "scale": scale,
                      "rotation": [0, 0, 0], "frame": frame, "anims": list(anims)})

    add("robe", models["robe"], (0, WAIST_Y, 0), 2.5, anims=[
        BODY_BOB, {"type": "sway", "axis": "x", "angle": 2.5, "period": 70, "phase": 0.0},
        {"type": "sway", "axis": "z", "angle": 1.5, "period": 95, "phase": 0.25}])
    add("torso", models["torso"], (0, WAIST_Y, 0), 2.5, anims=[BODY_BOB])
    add("cape", models["cape"], CAPE, 3.2, anims=[
        BODY_BOB, {"type": "sway", "axis": "x", "angle": 5, "period": 60, "phase": 0.1}])
    add("head", models["head"], NECK, 1.75, anims=[
        BODY_BOB, {"type": "sway", "axis": "y", "angle": 8, "period": 140, "phase": 0.0}])
    add("crown", models["crown"], CROWN, 1.5, anims=[
        BODY_BOB, {"type": "bob", "amplitude": 0.1, "period": 50, "phase": 0.3},
        {"type": "spin", "axis": "y", "speed": 1.5}])
    arm_idle = {"type": "sway", "axis": "x", "angle": 3, "period": 80, "phase": 0.0}
    reap = {"type": "swing", "axis": "x", "angle": -110, "ticks": 16}
    add("right_arm", models["right_arm"], SR, 2.0, anims=[BODY_BOB, arm_idle, reap])
    add("scythe", models["scythe"], SR, 3.2, anims=[BODY_BOB, arm_idle, reap])
    add("left_arm", models["left_arm"], SL, 2.0, anims=[
        BODY_BOB, {"type": "sway", "axis": "x", "angle": 4, "period": 70, "phase": 0.5},
        {"type": "swing", "axis": "x", "angle": -60, "ticks": 12}])
    for i in range(3):
        add(f"orb_{i + 1}", models["orb"], (0, 0, 0), 1.2, frame="world", anims=[
            {"type": "orbit", "radius": 2.6, "speed": 2.0, "phase": i * 120.0, "height": 2.4 + 0.9 * i},
            {"type": "spin", "axis": "y", "speed": 5.0},
            {"type": "bob", "amplitude": 0.22, "period": 46, "phase": i / 3.0},
        ])
    notes = ("공허의 군주. 보스 오른손 = -X 쪽(낫), 왼손 = +X 쪽(공허 불꽃). 앞 = +Z. "
             "모든 포즈는 모델에 구워 넣어 rotation 은 [0,0,0]. "
             "낫(scythe)은 오른팔과 같은 피벗(오른 어깨)·같은 애니메이션을 써야 손에 붙어 있다. "
             "swing angle 이 음수면 팔이 앞으로 들려 올라간다(서리 군주와 같은 규약). "
             "로브는 허리 피벗에서 살짝 흔들리고, 몸 전체가 같은 bob(BODY_BOB)으로 떠 있다. "
             "왕관은 두건 위에 떠서 y 축으로 천천히 돈다. 구슬은 world 프레임 orbit, offset y=0, 높이는 orbit.height. "
             "텍스처: augsky:boss/void_sovereign_{body,head,void,glow,blade}; void/glow/blade 는 16프레임(4틱) 애니메이션.")
    return {"parts": parts, "notes": notes}


# ─────────────────────────────── 미리보기 (z-버퍼 렌더러) ───────────────────────────────
# mc3d.render 는 면 단위 정렬이라 박스가 겹치면 틀리게 보일 수 있어, 같은 투영/UV 규칙에
# 픽셀 단위 z-버퍼를 쓴다. night=True 면 어둠 속 발광(light_emission)과 색 번짐(블룸)을 흉내 낸다.

def zrender(parts, size=512, yaw=-35, pitch=20, bg=(18, 14, 28), night=False, frame=0, ss=2, fit=None):
    view = _rot_matrix("x", pitch) @ _rot_matrix("y", yaw)
    faces = []
    for model, M4 in parts:
        M4 = np.eye(4) if M4 is None else np.array(M4, dtype=float)
        texs = {}
        for key, a in model.atlases.items():
            fr = min(frame, a.frames - 1)
            texs[key] = a.img.crop((0, fr * a.size, a.size, (fr + 1) * a.size))
        for el in model.elements:
            cbf = _face_corners(el["from"], el["to"])
            rot = el.get("rotation")
            for fname, fd in el["faces"].items():
                tex = texs.get(fd["texture"].lstrip("#"))
                if tex is None:
                    continue
                pts = []
                for p in cbf[fname]:
                    v = np.array(p, dtype=float)
                    if rot:
                        o = np.array(rot["origin"], dtype=float)
                        v = _rot_matrix(rot["axis"], rot["angle"]) @ (v - o) + o
                    v = (v - 8.0) / 16.0
                    w4 = M4 @ np.append(v, 1.0)
                    pts.append(view @ w4[:3])
                pts = np.array(pts)
                n = np.cross(pts[1] - pts[0], pts[3] - pts[0])
                if n[2] >= -1e-9:
                    continue
                lv = el.get("light_emission", 0)
                faces.append((pts, tex, fd["uv"], fd.get("rotation", 0), FACE_LIGHT[fname], lv))
    S = size * ss
    img = np.zeros((S, S, 3))
    img[...] = bg
    glow = np.zeros((S, S, 3))
    if not faces:
        return Image.fromarray(img.astype(np.uint8))
    if fit is None:
        allp = np.concatenate([f[0] for f in faces])
        lo, hi = allp.min(axis=0), allp.max(axis=0)
        span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    else:
        cx, cy, span = fit
    sc = S * 0.9 / span
    zb = np.full((S, S), -1e9)
    for pts, tex, uv, frot, fl, lv in faces:
        scr = np.array([((p[0] - cx) * sc + S / 2, -(p[1] - cy) * sc + S / 2) for p in pts])
        tw, th = tex.size
        u0, v0, u1, v1 = uv[0] / 16 * tw, uv[1] / 16 * th, uv[2] / 16 * tw, uv[3] / 16 * th
        src = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for _ in range(int(frot) // 90):
            src = src[1:] + src[:1]
        bx0, by0 = int(max(0, math.floor(scr[:, 0].min()))), int(max(0, math.floor(scr[:, 1].min())))
        bx1, by1 = int(min(S, math.ceil(scr[:, 0].max()) + 1)), int(min(S, math.ceil(scr[:, 1].max()) + 1))
        if bx1 - bx0 < 1 or by1 - by0 < 1:
            continue
        local = [(x - bx0, y - by0) for x, y in scr]
        co = _homography(src, local)
        if co is None:
            continue
        patch = np.array(tex.transform((bx1 - bx0, by1 - by0), Image.PERSPECTIVE, co, Image.NEAREST)).astype(float)
        mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        ImageDraw.Draw(mask).polygon(local, fill=255)
        m = (np.array(mask) > 0) & (patch[..., 3] >= 128)
        A3 = np.array([[scr[i][0], scr[i][1], 1] for i in (0, 1, 3)])
        try:
            abc = np.linalg.solve(A3, np.array([pts[0][2], pts[1][2], pts[3][2]]))
        except np.linalg.LinAlgError:
            continue
        X, Y = np.meshgrid(np.arange(bx0, bx1) + 0.5, np.arange(by0, by1) + 0.5)
        Z = abc[0] * X + abc[1] * Y + abc[2]
        if lv >= 8:   # 면 위에 붙은 빛 판(데칼)이 이기도록 아주 조금 앞으로
            Z = Z + 1e-4
        zsub = zb[by0:by1, bx0:bx1]
        sel = m & (Z > zsub)
        if not sel.any():
            continue
        if night:
            kk = max(0.16, lv / 15.0) if lv else 0.16 * fl / 0.8
        else:
            kk = 1.0 if lv >= 8 else fl
        col = patch[..., :3] * kk
        img[by0:by1, bx0:bx1][sel] = col[sel]
        zsub[sel] = Z[sel]
        gsub = glow[by0:by1, bx0:bx1]
        if lv >= 8:
            gsub[sel] = patch[..., :3][sel] * (lv / 15.0)
        else:
            gsub[sel] = 0
    out = img
    # 빛 번짐(블룸) — 미리보기 연출용. 밤에는 강하게, 낮에는 은은하게.
    gimg = Image.fromarray(glow.clip(0, 255).astype(np.uint8))
    b1 = np.array(gimg.filter(ImageFilter.GaussianBlur(S / 160))).astype(float)
    b2 = np.array(gimg.filter(ImageFilter.GaussianBlur(S / 50))).astype(float)
    k1, k2 = (0.9, 0.9) if night else (0.25, 0.3)
    out = out + b1 * k1 + b2 * k2
    out = Image.fromarray(out.clip(0, 255).astype(np.uint8))
    return out.resize((size, size), Image.LANCZOS)


def rig_parts(kits, spec, swing=0.0, t=0):
    """리그 스펙대로 파트를 배치한 (model, mat) 목록. swing 0..1 = 공격 동작, t = 틱 (회전/궤도)."""
    out = []
    for p in spec["parts"]:
        kit = kits["orb" if p["id"].startswith("orb") else p["id"]]
        off = list(p["offset"])
        pitch = yaw = 0.0
        for a in p["anims"]:
            if a["type"] == "swing" and a["axis"] == "x":
                pitch += a["angle"] * swing
            if a["type"] == "spin" and a["axis"] == "y":
                yaw += a["speed"] * t
            if a["type"] == "orbit":
                th = math.radians(a["phase"] + a["speed"] * t)
                off = [a["radius"] * math.cos(th), p["offset"][1] + a["height"], a["radius"] * math.sin(th)]
        out.append((kit.m, mat(translate=off, scale=p["scale"], pitch=pitch, yaw=yaw)))
    return out


HIT_W, HIT_H = 1.68, 5.76


def hitbox_model():
    """히트박스 외곽선 (미리보기 전용, 파일로 쓰지 않는다)."""
    m = Model("preview/hitbox")
    a = Atlas("preview_hit", 16)
    m.use("h", a)
    c = ("h", a.cell((255, 80, 80, 255), "flat"))
    w, H, t = HIT_W * 8, HIT_H * 16, 0.3
    for x in (-w, w):
        for z in (-w, w):
            m.box((8 + x - t, 8, 8 + z - t), (8 + x + t, 8 + H, 8 + z + t), c)
    for y in (0, H):
        for z in (-w, w):
            m.box((8 - w, 8 + y - t, 8 + z - t), (8 + w, 8 + y + t, 8 + z + t), c)
        for x in (-w, w):
            m.box((8 + x - t, 8 + y - t, 8 - w), (8 + x + t, 8 + y + t, 8 + w), c)
    return (m, mat())


def ref_block():
    """1 블록 기준 큐브 (미리보기 전용)."""
    m = Model("preview/block")
    a = Atlas("preview_block", 16)
    m.use("b", a)
    m.box((0, 0, 0), (16, 16, 16), ("b", a.cell((90, 96, 110, 255), "noise")))
    return (m, mat(translate=(2.6, 0.5, -0.6)))


def labeled_sheet(images, labels, cols, cell, title=None):
    rows = (len(images) + cols - 1) // cols
    top = 40 if title else 0
    sheet = Image.new("RGB", (cols * cell, top + rows * (cell + 26)), (12, 10, 20))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 18)
    if title:
        d.text((10, 8), title, font=ImageFont.truetype(FONT, 22), fill=(236, 200, 255))
    for i, im in enumerate(images):
        x, y = (i % cols) * cell, top + (i // cols) * (cell + 26)
        sheet.paste(im.convert("RGB").resize((cell, cell), Image.LANCZOS), (x, y))
        d.text((x + 8, y + cell + 3), labels[i], font=f, fill=(225, 220, 240))
    return sheet


def make_previews(M, kits, spec):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    parts = rig_parts(kits, spec, t=20)
    fit = (0.0, 3.6, 8.4)
    # 이 렌더러에서 yaw=0 이 정면(+Z 쪽에서 봄)
    ims, labels = [], []
    for name, yaw, pitch in (("앞 3/4", -35, 10), ("옆 (오른쪽)", 90, 6), ("뒤 3/4", 180 - 35, 10)):
        ims.append(zrender(parts, 640, yaw=yaw, pitch=pitch, fit=fit, frame=3))
        labels.append(name)
    ims.append(zrender(parts + [hitbox_model(), ref_block()], 640, yaw=-20, pitch=8, fit=fit))
    labels.append(f"히트박스 {HIT_W}×{HIT_H} + 1블록")
    ims.append(zrender(parts, 640, yaw=-30, pitch=10, night=True, fit=fit, frame=6))
    labels.append("밤 (발광)")
    ims.append(zrender(rig_parts(kits, spec, swing=1.0, t=20), 640, yaw=-70, pitch=8, fit=fit, frame=9))
    labels.append("공격 스윙 최고점")
    sheet = labeled_sheet(ims, labels, 3, 480, "공허의 군주 (void_sovereign) — 리그")
    p1 = os.path.join(PREVIEW_DIR, f"{BOSS}.png")
    sheet.save(p1)
    # 대표 이미지 (크게, 밤)
    hero = zrender(parts, 900, yaw=-28, pitch=8, night=True, fit=(0.0, 3.7, 7.6), frame=10, bg=(10, 6, 18))
    p_hero = os.path.join(PREVIEW_DIR, f"{BOSS}_hero.png")
    hero.save(p_hero)
    # 파트 클로즈업
    ims, labels = [], []
    for pid, kit in kits.items():
        for yaw in (-35, 180 - 35):
            ims.append(zrender([(kit.m, None)], 360, yaw=yaw, pitch=18, frame=4))
            labels.append(f"{pid} ({len(kit.m.elements)})")
    sheet2 = labeled_sheet(ims, labels, 4, 300, "공허의 군주 — 파트 (요소 수)")
    p2 = os.path.join(PREVIEW_DIR, f"{BOSS}_parts.png")
    sheet2.save(p2)
    # 텍스처 아틀라스 (첫 프레임) 확인용
    tex = [a.frame0().resize((256, 256), Image.NEAREST) for a in M.atlases()]
    p3 = os.path.join(PREVIEW_DIR, f"{BOSS}_textures.png")
    labeled_sheet(tex, [a.name.split("/")[-1] for a in M.atlases()], 5, 256).save(p3)
    return [p1, p_hero, p2, p3]


# ─────────────────────────────── 진입점 ───────────────────────────────

def _build(assets_root):
    M = Mats()
    kits = {
        "robe": build_robe(M),
        "torso": build_torso(M),
        "cape": build_cape(M),
        "head": build_head(M),
        "crown": build_crown(M),
        "right_arm": build_right_arm(M),
        "scythe": build_scythe(M),
        "left_arm": build_left_arm(M),
        "orb": build_orb(M),
    }
    for pk in M.packers:
        used = pk.pack()
        print(f"  {pk.atlas.name}: {len(pk.items)} 영역, 높이 {used}/{pk.atlas.size}")
    for kit in kits.values():
        kit.fix_uvs()
    models = {}
    for pid, kit in kits.items():
        n = len(kit.m.elements)
        assert n <= 160, f"{pid}: 요소 {n} 개 (160 초과)"
        models[pid] = kit.write(assets_root)
    for a in M.atlases():
        a.save(os.path.join(assets_root, "textures"))
    spec = rig_spec(models)
    with open(os.path.join(HERE, f"{MODULE}.rig.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    return M, kits, spec


def build(assets_root):
    """모델/텍스처를 assets_root 에 쓰고, 미리보기를 만들고, 리그 스펙을 돌려준다."""
    M, kits, spec = _build(assets_root)
    make_previews(M, kits, spec)
    return spec


if __name__ == "__main__":
    root = os.path.join(HERE, "_scratch", "boss_void", "assets", "augsky")
    spec = build(root)
    for p in spec["parts"]:
        print(p["id"], p["model"], p["offset"], p["scale"])
