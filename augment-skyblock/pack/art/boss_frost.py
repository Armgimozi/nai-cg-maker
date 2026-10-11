"""
서리 군주 (Frost Tyrant) — boss id "frost_tyrant".

고대의 얼음 왕. 키 약 5.5 블록.
  - 빙하색 판금 흉갑 + 빛나는 서리 룬(애니메이션)
  - 얼음 가시가 솟은 견갑, 뿔 달린 얼음 왕관과 청록 보석
  - 창백한 해골 얼굴, 빛나는 눈, 고드름 수염
  - 뒤로 휘날리는 너덜너덜한 서리 망토
  - 얼음 정강이받이를 두른 다리
  - 오른손: 청록 날이 빛나는 거대한 얼음 대검 (별도 파트, 팔과 같은 피벗/스윙)
  - 왼손: 얼음 발톱 건틀릿
  - 주위를 도는 얼음 파편 3개

작성 단위: 각 파트는 "월드 픽셀"(1 블록 = 16) 로, 파트 피벗 기준 좌표로 그린다.
Kit 가 파트 스케일에 맞춰 모델 좌표(8 + 픽셀/scale)로 바꿔 준다.
앞은 +Z, 위는 +Y. 보스의 오른쪽 = -X (남쪽을 볼 때 오른손이 서쪽).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from mc3d import (FACE_LIGHT, FACES, Atlas, Model, Region, _face_corners, _homography,  # noqa: E402
                  _rot_matrix, mat)

BOSS = "frost_tyrant"
MODULE = "boss_frost"
FONT = "/tmp/claude-0/work/fonts/ng.ttf"
PREVIEW_DIR = os.path.join(HERE, "preview")

F = 16            # 애니메이션 프레임 수
FRAMETIME = 3     # 틱/프레임 → 48틱 주기
SWORD_TILT = 22.5  # 대검이 앞으로 기운 각도 (element 회전, x축)

# ─────────────────────────────── 팔레트 ───────────────────────────────
ARMOR = (52, 108, 170)      # 빙하색 판금
ARMOR2 = (30, 62, 114)      # 어두운 판금 (교차 배치)
ARMOR_HI = (170, 226, 255)
ARMOR_LO = (8, 20, 46)
DARKSTEEL = (24, 34, 60)
SILVER = (198, 216, 234)
SILVER_D = (98, 118, 146)
CLOTH = (22, 30, 58)
ROYAL = (34, 56, 128)
ICE = (150, 214, 246)
ICE_L = (232, 250, 255)
ICE_D = (64, 132, 196)
BONE = (222, 230, 234)
BONE_D = (140, 158, 172)
CY_D = (10, 120, 210)
CY = (90, 230, 255)
CY_W = (235, 255, 255)


def _c(t):
    return np.array(t[:3], dtype=float)


def _rng(*k):
    return np.random.default_rng(abs(hash(k)) % (2 ** 32))


def _finish(a):
    a = np.clip(a, 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def _base(w, h, col, face, grad=0.22, noise=0.12, seed=0):
    """그라데이션 + 노이즈 바탕. 윗면은 밝게, 아랫면은 어둡게."""
    rng = _rng("base", w, h, face, seed)
    a = np.zeros((h, w, 4))
    a[..., 3] = 255
    yy = np.linspace(0, 1, h)[:, None] if h > 1 else np.zeros((1, 1))
    if face == "up":
        g = np.full((h, 1), 1.12)
    elif face == "down":
        g = np.full((h, 1), 0.72)
    else:
        g = 1.1 - grad * yy
    n = 1 - noise / 2 + noise * rng.random((h, w))
    a[..., :3] = _c(col)[None, None, :] * (g * n)[..., None]
    return a, rng


def _bevel(a, hi=ARMOR_HI, lo=ARMOR_LO, k=0.5):
    h, w = a.shape[:2]
    if w > 2 and h > 2:
        a[0, :, :3] = a[0, :, :3] * (1 - k) + _c(hi) * k
        a[:, 0, :3] = a[:, 0, :3] * (1 - k * 0.6) + _c(hi) * k * 0.6
        a[-1, :, :3] = a[-1, :, :3] * 0.45 + _c(lo) * 0.55
        a[:, -1, :3] = a[:, -1, :3] * 0.6 + _c(lo) * 0.4
    return a


def _speck(a, rng, p=0.05, col=ICE_L, k=0.55):
    m = rng.random(a.shape[:2]) < p
    a[m, :3] = a[m, :3] * (1 - k) + _c(col) * k
    return a


# ─────────────────────────────── 정적 페인터 ───────────────────────────────
# painter(w, h, face) -> RGBA Image

def P_plate(col=ARMOR, speck=0.015, seed=0):
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.28, noise=0.07, seed=seed)
        # 큰 면에는 안쪽 홈선(판금 패널) — 어두운 선 + 바로 아래 밝은 선
        if w >= 12 and h >= 12:
            i = 2
            a[i, i:w - i, :3] *= 0.55
            a[h - 1 - i, i:w - i, :3] *= 0.55
            a[i:h - i, i, :3] *= 0.55
            a[i:h - i, w - 1 - i, :3] *= 0.55
            a[i + 1, i + 1:w - i - 1, :3] = a[i + 1, i + 1:w - i - 1, :3] * 0.6 + _c(ARMOR_HI) * 0.4
            # 리벳
            for (yy, xx) in ((1, 1), (1, w - 2), (h - 2, 1), (h - 2, w - 2)):
                a[yy, xx, :3] = _c(SILVER)
        # 위쪽 가장자리에 낀 서리
        if h > 4 and face not in ("up", "down"):
            a[1, :, :3] = a[1, :, :3] * 0.75 + _c(ICE_L) * 0.25
        _speck(a, rng, speck)
        return _finish(_bevel(a, k=0.6))
    return paint


def P_metal(col=SILVER):
    """은빛 금속: 대각선 광택 줄무늬."""
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.15, noise=0.06)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        k = ((x + y * 2) % 7) / 6.0
        a[..., :3] *= (0.82 + 0.3 * (1 - np.abs(k - 0.4) * 1.6)).clip(0.75, 1.15)[..., None]
        return _finish(_bevel(a, hi=(255, 255, 255), lo=SILVER_D, k=0.45))
    return paint


def P_ice(col=ICE, seed=0):  # noqa: C901
    """얼음 결정: 대각 광택선, 안쪽의 푸른 결, 흰 모서리."""
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.3, noise=0.1, seed=seed)
        x = np.arange(w)[None, :] + seed
        y = np.arange(h)[:, None]
        streak = ((x * 2 + y * 3) % 9) == 0
        vein = ((x * 3 - y * 2) % 11) == 0
        a[streak, :3] = a[streak, :3] * 0.3 + _c(ICE_L) * 0.7
        a[vein, :3] = a[vein, :3] * 0.6 + _c(ICE_D) * 0.4
        _speck(a, rng, 0.06, (255, 255, 255), 0.8)
        return _finish(_bevel(a, hi=(255, 255, 255), lo=ICE_D, k=0.6))
    return paint


def P_cloth(col=CLOTH):
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.2, noise=0.2)
        y = np.arange(h)[:, None]
        a[..., :3] *= np.where(y % 2 == 0, 1.08, 0.94)[..., None]
        return _finish(a)
    return paint


def P_chain():
    """사슬 갑옷: 어두운 바탕에 강철 고리 점."""
    def paint(w, h, face):
        a, rng = _base(w, h, CLOTH, face, noise=0.1)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        ring = ((x + (y % 2)) % 2 == 0)
        a[ring, :3] = a[ring, :3] * 0.3 + _c(SILVER_D) * 0.7
        hl = ring & (y % 2 == 0) & ((x // 2 + y) % 3 == 0)
        a[hl, :3] = _c(SILVER)
        return _finish(a)
    return paint


def P_bone(col=BONE):
    def paint(w, h, face):
        a, rng = _base(w, h, col, face, grad=0.3, noise=0.1)
        _speck(a, rng, 0.05, BONE_D, 0.5)
        return _finish(_bevel(a, hi=(255, 255, 255), lo=BONE_D, k=0.35))
    return paint


def P_fur():
    """망토 깃: 서리 낀 흰-푸른 털."""
    def paint(w, h, face):
        a, rng = _base(w, h, (196, 222, 240), face, grad=0.35, noise=0.25)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        tuft = ((x * 5 + y * 3 + (x // 3) * 7) % 6) == 0
        a[tuft, :3] *= 0.72
        tip = rng.random((h, w)) < 0.08
        a[tip, :3] = 255
        return _finish(a)
    return paint


def P_chest():
    """흉갑 앞면: 가슴 판 곡선, 가운데 능선, 룬 홈, 은 테두리. (밀도 2 로 쓴다)"""
    def paint(w, h, face):
        a, rng = _base(w, h, ARMOR, face, grad=0.3, noise=0.08)
        img = _finish(a)
        d = ImageDraw.Draw(img)
        cx = w / 2
        hi = ARMOR_HI + (255,)
        lo = ARMOR_LO + (255,)
        # 가슴 판 두 개의 아랫선 (어둡게) + 바로 위 하이라이트
        for s in (-1, 1):
            pts = [(cx + s * 1, h * 0.12), (cx + s * w * 0.18, h * 0.72), (cx + s * w * 0.42, h * 0.78),
                   (cx + s * w * 0.5, h * 0.55)]
            d.line(pts, fill=lo, width=2)
            pts2 = [(x, y - 2) for x, y in pts]
            d.line(pts2, fill=hi, width=1)
        # 가운데 능선
        d.line([(cx - 1, 0), (cx - 1, h)], fill=hi, width=1)
        d.line([(cx, 0), (cx, h)], fill=lo, width=1)
        # 룬이 박힐 홈 (원형)
        r = h * 0.36
        d.ellipse((cx - r, h * 0.45 - r, cx + r, h * 0.45 + r), fill=(10, 24, 52, 255), outline=SILVER + (255,))
        # 은 테두리 (위/아래)
        d.rectangle((0, 0, w, 1), fill=SILVER + (255,))
        d.rectangle((0, h - 2, w, h), fill=SILVER_D + (255,))
        a = np.array(img).astype(float)
        _speck(a, rng, 0.03)
        return _finish(a)
    return paint


def P_abs():
    """복부 판: 가로로 겹친 세 장."""
    def paint(w, h, face):
        a, rng = _base(w, h, ARMOR2, face, grad=0.1, noise=0.1)
        n = 3
        for i in range(n):
            y0 = int(i * h / n)
            a[y0, :, :3] = a[y0, :, :3] * 0.3 + _c(ARMOR_HI) * 0.7
            if y0 + 1 < h:
                a[y0 + 1, :, :3] = a[y0 + 1, :, :3] * 0.7 + _c(ARMOR_HI) * 0.3
            yb = int((i + 1) * h / n) - 1
            a[yb, :, :3] *= 0.45
        return _finish(_bevel(a))
    return paint


def P_face():
    """해골 얼굴 (밀도 2): 깊은 눈구멍, 코 구멍, 광대뼈, 서리 균열."""
    def paint(w, h, face):
        a, rng = _base(w, h, BONE, face, grad=0.45, noise=0.08)
        # 가장자리로 갈수록 푸른 그늘 (둥근 두개골 느낌)
        x4 = (np.linspace(-1, 1, w)[None, :] ** 4)[..., None]
        a[..., :3] = a[..., :3] * (1 - 0.35 * x4) + _c(ICE_D)[None, None] * 0.35 * x4
        img = _finish(a)
        d = ImageDraw.Draw(img)
        dark = (6, 10, 26, 255)
        sh = BONE_D + (255,)
        s = w / 24.0
        P = lambda pts: [(px * s, py * s) for px, py in pts]
        # 눈썹 뼈 아래 그림자
        d.polygon(P([(1, 9), (11, 11), (13, 11), (23, 9), (23, 11.5), (13, 13), (11, 13), (1, 11.5)]), fill=sh)
        # 크고 각진 눈구멍
        for side in (-1, 1):
            cx = 12 + side * 6
            d.polygon(P([(cx - 4.5 * side, 10.5), (cx + 4 * side, 9.5), (cx + 3.5 * side, 15),
                         (cx - 3 * side, 15.5)]), fill=dark)
        # 코 구멍
        d.polygon(P([(10.5, 17), (13.5, 17), (12.6, 20.5), (11.4, 20.5)]), fill=dark)
        # 광대뼈 하이라이트 + 그늘
        for side in (-1, 1):
            d.line(P([(12 + side * 10, 17), (12 + side * 6.5, 18.5)]), fill=(255, 255, 255, 255), width=1)
            d.line(P([(12 + side * 10, 19), (12 + side * 6, 21)]), fill=sh, width=1)
        d.rectangle((0, 21.5 * s, w, h), fill=BONE_D + (255,))
        # 서리 균열 (이마)
        d.line(P([(4, 1), (6, 4), (5, 7)]), fill=ICE_D + (255,), width=1)
        d.line(P([(19, 2), (18, 5)]), fill=ICE_D + (255,), width=1)
        return img
    return paint


def P_jaw():
    """아래턱 앞면: 어두운 입 + 날카로운 이빨 몇 개."""
    def paint(w, h, face):
        a, rng = _base(w, h, BONE_D, face, grad=0.2, noise=0.08)
        img = _finish(a)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, w, h * 0.6), fill=(6, 10, 24, 255))
        n = 5
        for i in range(n):
            x0 = (i + 0.5) * w / n - 1.2
            d.polygon([(x0, 0), (x0 + 2.4, 0), (x0 + 1.2, h * 0.5)], fill=BONE + (255,))
        d.line([(0, h - 1), (w, h - 1)], fill=(90, 104, 120, 255))
        return img
    return paint


def P_crownband():
    """왕관 띠 (밀도 2): 은 바탕, 위아래 테, 보석 받침."""
    def paint(w, h, face):
        a = np.array(P_metal(SILVER)(w, h, face)).astype(float)
        img = _finish(a)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, w, 0), fill=(255, 255, 255, 255))
        d.rectangle((0, h - 1, w, h), fill=SILVER_D + (255,))
        # 지그재그 각인
        for x in range(0, w, 4):
            d.line([(x, h - 2), (x + 2, 2), (x + 4, h - 2)], fill=SILVER_D + (255,), width=1)
        return img
    return paint


def P_tabard():
    """앞 허리에 늘어진 왕의 휘장: 짙은 청색 천, 은 테두리, 눈꽃 문장."""
    def paint(w, h, face):
        a, rng = _base(w, h, ROYAL, face, grad=0.3, noise=0.15)
        img = _finish(a)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 0, h), fill=SILVER + (255,))
        d.rectangle((w - 1, 0, w - 1, h), fill=SILVER + (255,))
        cx, cy = (w - 1) / 2, h * 0.35
        for ang in range(0, 180, 60):
            dx, dy = math.cos(math.radians(ang)) * w * 0.35, math.sin(math.radians(ang)) * w * 0.35
            d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=ICE_L + (255,), width=1)
        # 아래 끝은 V 자로 잘라 낸다
        arr = np.array(img)
        for y in range(h):
            for x in range(w):
                if y > h - 1 - (w / 2 - abs(x - (w - 1) / 2)) * 0.9:
                    arr[y, x, 3] = 0
        arr[-3:, :, :3] = (arr[-3:, :, :3] * 0.5 + np.array(ICE_L) * 0.5).astype(np.uint8)
        return Image.fromarray(arr, "RGBA")
    return paint


def P_blade():
    """대검 날 면: 창백한 얼음, 가운데 홈은 짙게, 결정 결."""
    def paint(w, h, face):
        a, rng = _base(w, h, (178, 226, 250), face, grad=0.25, noise=0.08, seed=3)
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        cx = (w - 1) / 2
        dist = np.abs(x - cx) / max(1, w / 2)
        a[..., :3] *= (1.05 - 0.25 * dist)[..., None] * np.ones((h, 1, 1))
        fuller = np.abs(x - cx) <= max(1, w * 0.18)
        a[fuller.repeat(h, 0), :3] = a[fuller.repeat(h, 0), :3] * 0.35 + _c((20, 60, 120)) * 0.65
        streak = ((x * 3 + y) % 13) == 0
        a[streak, :3] = a[streak, :3] * 0.3 + 255 * 0.7
        _speck(a, rng, 0.04, (255, 255, 255), 0.9)
        return _finish(a)
    return paint


def P_grip():
    def paint(w, h, face):
        a, rng = _base(w, h, (40, 34, 52), face, grad=0.1, noise=0.15)
        y = np.arange(h)[:, None]
        x = np.arange(w)[None, :]
        wrap = ((y + x) % 3) == 0
        a[wrap, :3] = _c(SILVER_D)
        return _finish(a)
    return paint


# ─────────────────────────────── 애니메이션 페인터 (빛) ───────────────────────────────
# painter(frame, w, h, face) -> RGBA Image

def _glow_rgb(f, w, h, speed=1, k=0.45, seed=0, axis="y"):
    """청록 → 흰빛으로 물결치는 색. (h, w, 3) 배열."""
    x = np.arange(w)[None, :].repeat(h, 0)
    y = np.arange(h)[:, None].repeat(w, 1)
    pos = (y if axis == "y" else x) + (x if axis == "y" else y) * 0.35
    v = 0.5 + 0.5 * np.sin(2 * math.pi * speed * f / F - pos * k + seed)
    c1, c2, c3 = _c(CY_D), _c(CY), _c(CY_W)
    lo = c1[None, None, :] + (c2 - c1)[None, None, :] * np.clip(v * 1.6, 0, 1)[..., None]
    out = lo + (c3 - c2)[None, None, :] * np.clip((v - 0.62) * 2.6, 0, 1)[..., None]
    # 반짝임: 픽셀마다 정해진 프레임에 하얗게 번쩍
    rng = _rng("spark", w, h, seed)
    ph = rng.integers(0, F, size=(h, w))
    sel = (rng.random((h, w)) < 0.12) & (ph == f)
    out[sel] = 255
    return out


def G_glow(speed=1, k=0.45, seed=0, axis="y"):
    def paint(f, w, h, face):
        a = np.zeros((h, w, 4))
        a[..., :3] = _glow_rgb(f, w, h, speed, k, seed, axis)
        a[..., 3] = 255
        return _finish(a)
    return paint


def G_gem():
    """보석: 가운데가 밝고 테두리가 깊은 청록, 맥동."""
    def paint(f, w, h, face):
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * f / F)
        a = np.zeros((h, w, 4))
        x = np.arange(w)[None, :]
        y = np.arange(h)[:, None]
        r = np.sqrt(((x - (w - 1) / 2) / max(1, w / 2)) ** 2 + ((y - (h - 1) / 2) / max(1, h / 2)) ** 2)
        t = np.clip(1.15 - r + 0.25 * pulse, 0, 1)
        a[..., :3] = _c(CY_D)[None, None] + (_c(CY_W) - _c(CY_D))[None, None] * t[..., None]
        a[0, 0, :3] = 255
        a[..., 3] = 255
        return _finish(a)
    return paint


def G_ice_glow(seed=0):
    """빛나는 얼음 결정 (파편, 대검 장식): 얼음 결 위로 밝은 띠가 흐른다."""
    def paint(f, w, h, face):
        base = np.array(P_ice((120, 205, 245), seed=seed)(w, h, face)).astype(float)
        g = _glow_rgb(f, w, h, speed=1, k=0.5, seed=seed)
        y = np.arange(h)[:, None].repeat(w, 1)
        band = 0.5 + 0.5 * np.sin(2 * math.pi * f / F - y * 0.6 + seed)
        t = (band ** 3)[..., None] * 0.7
        base[..., :3] = base[..., :3] * (1 - t) + g * t
        return _finish(base)
    return paint


def G_eye():
    """눈: 가운데 흰 핵 + 바깥 청록, 천천히 맥동."""
    def paint(f, w, h, face):
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * f / F)
        x = np.abs(np.linspace(-1, 1, w))[None, :].repeat(h, 0)
        t = np.clip(1.2 - x * (1.1 - 0.3 * pulse), 0, 1)
        a = np.zeros((h, w, 4))
        a[..., :3] = _c(CY)[None, None] + (_c(CY_W) - _c(CY))[None, None] * t[..., None]
        a[..., 3] = 255
        return _finish(a)
    return paint


def _mask_img(w, h, draw_fn):
    m = Image.new("L", (w, h), 0)
    draw_fn(ImageDraw.Draw(m), w, h)
    return np.array(m) > 0


def G_rune(draw_fn, speed=1, k=0.35, halo=True):
    """투명 바탕 위 룬 문양. 문양은 물결치며 빛나고, 옆에 옅은 후광."""
    def paint(f, w, h, face):
        m = _mask_img(w, h, draw_fn)
        a = np.zeros((h, w, 4))
        a[..., :3] = _glow_rgb(f, w, h, speed, k)
        a[..., 3] = np.where(m, 255, 0)
        if halo:
            mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
            hm = (np.array(mi) > 0) & ~m
            a[hm, :3] = _c(CY_D) * 0.7
            a[hm, 3] = 160 if False else 255
            # 후광은 짙은 청록 (테두리 효과)
        return _finish(a)
    return paint


# ── 룬 모양들 (w, h 크기에 맞춰 정규화 좌표로 그린다) ──

def rune_sigil(d, w, h):
    """흉갑 중앙: 서리 문장 (마름모 + 세로선 + 가지)."""
    cx, cy = (w - 1) / 2, (h - 1) / 2
    X = lambda u: cx + u * (w - 2) / 2
    Y = lambda v: cy + v * (h - 2) / 2
    d.line([(X(0), Y(-1)), (X(0), Y(1))], fill=255)
    d.polygon([(X(0), Y(-0.75)), (X(0.6), Y(0)), (X(0), Y(0.75)), (X(-0.6), Y(0))], outline=255)
    for s in (-1, 1):
        d.line([(X(0), Y(-0.35)), (X(s * 0.95), Y(-0.85))], fill=255)
        d.line([(X(0), Y(0.35)), (X(s * 0.95), Y(0.85))], fill=255)
        d.line([(X(s * 0.6), Y(0)), (X(s * 1.0), Y(0))], fill=255)
    d.point((X(0) + 0, Y(0)), fill=255)


def rune_flake(d, w, h):
    """눈꽃 (견갑, 건틀릿)."""
    cx, cy = (w - 1) / 2, (h - 1) / 2
    r = min(w, h) / 2 - 0.5
    for ang in (90, 30, -30):
        dx, dy = math.cos(math.radians(ang)) * r, math.sin(math.radians(ang)) * r
        d.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], fill=255)
    for ang in range(0, 360, 60):
        px, py = cx + math.cos(math.radians(ang)) * r * 0.6, cy + math.sin(math.radians(ang)) * r * 0.6
        d.point((px, py), fill=255)


def rune_bigflake(d, w, h):
    """큰 눈꽃 문장 (망토 등): 6갈래 + 가지 + 가운데 고리."""
    cx, cy = (w - 1) / 2, (h - 1) / 2
    r = min(w, h) / 2 - 1
    for ang in range(0, 360, 60):
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        d.line([(cx + ca * r * 0.22, cy + sa * r * 0.22), (cx + ca * r, cy + sa * r)], fill=255, width=2)
        for t, ln in ((0.45, 0.3), (0.72, 0.22)):
            px_, py_ = cx + ca * r * t, cy + sa * r * t
            for b in (-55, 55):
                a2 = math.radians(ang + b)
                d.line([(px_, py_), (px_ + math.cos(a2) * r * ln, py_ + math.sin(a2) * r * ln)], fill=255, width=1)
    d.ellipse((cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2), outline=255, width=1)


def rune_strip(d, w, h):
    """세로 룬 띠 (대검 홈, 정강이): 가운데 선 + 반복 글리프."""
    cx = (w - 1) / 2
    d.line([(cx, 0), (cx, h)], fill=255)
    step = max(6, w * 2)
    i = 0
    for y in range(2, h - 2, step):
        kind = i % 4
        if kind == 0:
            d.line([(0, y), (cx, y + step * 0.3), (w - 1, y)], fill=255)
        elif kind == 1:
            d.polygon([(cx, y), (w - 1, y + step * 0.3), (cx, y + step * 0.6), (0, y + step * 0.3)], outline=255)
        elif kind == 2:
            d.line([(0, y), (w - 1, y + step * 0.5)], fill=255)
            d.line([(w - 1, y), (0, y + step * 0.5)], fill=255)
        else:
            d.line([(0, y + step * 0.5), (cx, y), (w - 1, y + step * 0.5)], fill=255)
        i += 1


# ─────────────────────────────── 재질(스킨) / 파트 키트 ───────────────────────────────

class Packer:
    """
    mc3d.Atlas.alloc 은 요청 순서대로 선반에 쌓아 빈 공간이 많이 남는다.
    그래서 영역 요청을 모아 두었다가 높이순으로 정렬해 한 번에 배치하고, 그 뒤에 그림을 그린다.
    (Kit 이 기록해 둔 면 UV 는 배치 후 fix_uvs 로 고친다.)
    """

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
        return y + row   # 사용한 높이


class Skin:
    """
    면 크기에 맞춰 아틀라스에 영역을 받아 그림을 그리는 재질.
    같은 크기의 면은 영역을 재사용한다(옆면끼리, 위/아래 따로).
    """

    def __init__(self, packer, painter, density=1.0, anim=False, maxpx=48, share=True):
        self.packer, self.painter, self.density, self.anim = packer, painter, density, anim
        self.atlas = packer.atlas
        self.maxpx = maxpx
        self.share = share
        self.cache = {}

    @staticmethod
    def _bucket(v):
        # 아틀라스 절약: 반복 재질은 2 의 거듭제곱 크기로 맞춰 재사용 (조금 늘어나도 티가 안 남)
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
    """파트 하나 (= 모델 하나). 좌표는 피벗 기준 월드 픽셀."""

    def __init__(self, part, scale):
        self.part = part
        self.m = Model(f"boss/{BOSS}_{part}")
        self.s = scale
        self.fix = []   # (element, face, Region, sub) — 배치 후 UV 갱신

    def key(self, atlas):
        k = atlas.name.split("/")[-1].replace(BOSS + "_", "")
        if k not in self.m.textures:
            self.m.use(k, atlas)
        return k

    def U(self, p):
        return [8 + v / self.s for v in p]

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
            if isinstance(sk, Skin):
                fd[f] = (self.key(sk.atlas), sk.region(*dims[f], f), None)
            else:  # (Region, sub 사각형 또는 None)
                fd[f] = (self.key(sk[0].atlas), sk[0], sk[1])
        rotation = None
        if rot and rot[1]:
            rotation = {"origin": [round(v, 4) for v in self.U(rot[2])], "axis": rot[0], "angle": rot[1]}
        if shade is None:
            shade = not (light >= 8)
        el = self.m.box(self.U(frm), self.U(to), {f: v[:2] for f, v in fd.items()}, light=light, shade=shade,
                        rotation=rotation)
        for f, v in fd.items():
            self.fix.append((el, f, v[1], v[2]))
        return el

    def fix_uvs(self):
        for el, f, reg, sub in self.fix:
            el["faces"][f]["uv"] = reg.uv(sub)

    def decal(self, face, rect, at, skin, light=15, rot=None):
        """면 위에 붙는 두께 0 판 (룬, 눈 등). rect=(a0,b0,a1,b1) 은 그 면의 평면 좌표, at 은 면 위치."""
        a0, b0, a1, b1 = rect
        if face in ("south", "north"):
            frm, to = (a0, b0, at), (a1, b1, at)
        elif face in ("east", "west"):
            frm, to = (at, b0, a0), (at, b1, a1)
        else:
            frm, to = (a0, at, b0), (a1, at, b1)
        return self.box(frm, to, skin, light=light, faces=[face], rot=rot)

    def spike(self, base, length, width, skin, axis="z", angle=0, steps=3, down=False, light=0,
              depth=None, taper=0.78):
        """끝이 가늘어지는 가시. 회전 전에는 +Y(또는 -Y) 로 뻗고, base 를 중심으로 한 축 회전."""
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
                     rot=(axis, angle, base), light=light)
        return tip_of(base, length * d, axis, angle)

    def chain(self, base, segs, skin, light=0, down=False):
        """구부러진 뿔/발톱: segs = [(길이, 굵기, 축, 각도), ...] 를 끝과 끝을 이어 붙인다."""
        p = list(base)
        for i, (length, width, axis, angle) in enumerate(segs):
            sk = skin[min(len(skin) - 1, int(i * len(skin) / len(segs)))] if isinstance(skin, list) else skin
            self.spike(p, length + width * 0.25, width, sk, axis, angle, steps=1, down=down, light=light,
                       taper=0)
            p = tip_of(p, length * (-1 if down else 1), axis, angle)
        return p

    def write(self, assets_root):
        self.m.write(assets_root)
        return "augsky:" + self.m.name


def tip_of(base, length, axis, angle):
    v = _rot_matrix(axis, angle) @ np.array([0.0, length, 0.0])
    return [base[0] + v[0], base[1] + v[1], base[2] + v[2]]


# ─────────────────────────────── 재질 묶음 ───────────────────────────────

class Mats:
    def __init__(self):
        self.A_body = Atlas(f"boss/{BOSS}_body", 128, seed=11)
        self.A_head = Atlas(f"boss/{BOSS}_head", 128, seed=12)
        self.A_cape = Atlas(f"boss/{BOSS}_cape", 128, seed=13)
        self.A_sword = Atlas(f"boss/{BOSS}_sword", 64, seed=14)
        self.A_glow = Atlas(f"boss/{BOSS}_glow", 128, frames=F, frametime=FRAMETIME, seed=15)
        self.packers = [Packer(a) for a in self.atlases()]
        B, H, C, S, G = self.packers
        self.P_cape = C
        self.plate = Skin(B, P_plate(ARMOR))
        self.plate2 = Skin(B, P_plate(ARMOR2, seed=2))
        self.dark = Skin(B, P_plate(DARKSTEEL, speck=0.03, seed=3))
        self.silver = Skin(B, P_metal(SILVER))
        self.ice = Skin(B, P_ice(ICE))
        self.ice_d = Skin(B, P_ice((84, 156, 214), seed=1))
        self.ice_l = Skin(B, P_ice((200, 240, 255), seed=2))
        self.ices = [self.ice_d, self.ice, self.ice_l]
        self.cloth = Skin(B, P_cloth(CLOTH))
        self.chain = Skin(B, P_chain())
        self.chest = Skin(B, P_chest(), density=2, share=False)
        self.abs = Skin(B, P_abs(), share=False)
        self.tabard = Skin(B, P_tabard(), share=False)
        # 머리
        self.h_bone = Skin(H, P_bone())
        self.h_face = Skin(H, P_face(), density=2, share=False)
        self.h_jaw = Skin(H, P_jaw(), density=2, share=False)
        self.h_plate = Skin(H, P_plate(ARMOR2, seed=5))
        self.h_band = Skin(H, P_crownband(), density=1, share=False)
        self.h_silver = Skin(H, P_metal(SILVER))
        self.h_ice = Skin(H, P_ice(ICE, seed=4))
        self.h_ices = [Skin(H, P_ice((84, 156, 214), seed=5)), self.h_ice, Skin(H, P_ice((200, 240, 255), seed=6))]
        self.h_cloth = Skin(H, P_cloth(CLOTH))
        self.h_dark = Skin(H, P_plate(DARKSTEEL, seed=9))
        # 대검
        self.s_blade = Skin(S, P_blade(), density=1, maxpx=64, share=False)
        self.s_silver = Skin(S, P_metal(SILVER))
        self.s_grip = Skin(S, P_grip())
        self.s_ice = Skin(S, P_ice(ICE, seed=7))
        self.s_ice_l = Skin(S, P_ice((205, 242, 255), seed=8))
        # 빛 (애니메이션)
        self.glow = Skin(G, G_glow(), anim=True, maxpx=32)
        self.glow_v = Skin(G, G_glow(speed=1, k=0.25), anim=True, maxpx=40, share=False)
        self.gem = Skin(G, G_gem(), anim=True, maxpx=8)
        self.ice_glow = Skin(G, G_ice_glow(), anim=True, maxpx=16)
        self.r_sigil = Skin(G, G_rune(rune_sigil), density=2, anim=True, share=False)
        self.r_flake = Skin(G, G_rune(rune_flake), density=2, anim=True, share=False)
        self.r_strip = Skin(G, G_rune(rune_strip, halo=False), density=2, anim=True, maxpx=64, share=False)
        self.r_bigflake = Skin(G, G_rune(rune_bigflake, k=0.12), density=2, anim=True, maxpx=64, share=False)
        self.r_strip2 = Skin(G, G_rune(rune_strip, halo=False, k=0.2), density=2, anim=True, maxpx=64,
                             share=False)
        self.eye = Skin(G, G_eye(), anim=True, share=False, density=2)

    def atlases(self):
        return [self.A_body, self.A_head, self.A_cape, self.A_sword, self.A_glow]


# ─────────────────────────────── 파트: 다리 ───────────────────────────────
HIP_Y = 34      # 엉덩이 높이 (월드 픽셀)
SHOULDER = (17, 60, 0)
NECK_Y = 64
ARM_SCALE = 2.5
HEAD_SCALE = 1.6   # 모델 작성 스케일
HEAD_GROW = 1.18   # 표시할 때 머리를 조금 키워 존재감을 준다


def build_legs(M):
    k = Kit("legs", 2.0)
    for sx in (-1, 1):
        cx = sx * 6.5
        o = lambda v: cx + sx * v   # 바깥쪽이 + 인 x
        # 허벅지 (사슬) + 허벅지 판
        k.box((cx - 4.5, -16, -4.5), (cx + 4.5, 0, 4.5), M.chain)
        k.box((cx - 5, -15, -5), (cx + 5, -6, 5), M.plate2)
        # 무릎 보호대 + 앞으로 솟은 얼음 가시
        k.box((cx - 3.5, -20, 3), (cx + 3.5, -13, 6.5), M.silver)
        k.box((cx - 1.2, -19, 6.5), (cx + 1.2, -16.6, 7.2), M.gem, light=15)
        k.spike((cx, -17, 5.5), 7, 3, M.ices, axis="x", angle=45, steps=3)
        # 정강이받이
        k.box((cx - 4.5, -30, -4.5), (cx + 4.5, -17, 4.5), M.plate)
        k.box((cx - 1.5, -29, 4.5), (cx + 1.5, -18, 6), M.ice)
        k.decal("south", (cx - 0.6, -28, cx + 0.6, -19), 6.05, M.glow_v)
        # 장딴지 바깥 얼음 가시 (바깥, 뒤)
        k.spike((o(4.5), -22, -1), 8, 3, M.ices, axis="z", angle=-sx * 45, steps=3)
        k.spike((cx, -25, -4.5), 6, 2.5, M.ices, axis="x", angle=-45, steps=2)
        # 쇠 신발
        k.box((cx - 5, -34, -5.5), (cx + 5, -30, 6), M.dark)
        k.box((cx - 4, -34, 6), (cx + 4, -31, 9), M.dark)
        k.box((cx - 3, -34, 9), (cx + 3, -32.5, 10.5), M.silver)
        # 앞 허리 판 (tasset)
        k.box((cx - 4.5, -14, 5), (cx + 5.5, -1, 7), M.plate, )
        k.box((cx - 4.5, -15, 5.2), (cx + 5.5, -13.5, 7.2), M.silver)
        # 옆 허리 판
        k.box((o(5), -16, -5.5), (o(7), -1, 5.5), M.plate2)
    # 가운데 휘장 (앞) + 뒤 판
    k.box((-3.2, -24, 6.6), (3.2, 0, 7.1), M.cloth, over={"south": M.tabard, "north": M.tabard})
    k.box((-11, -14, -7), (11, -1, -5), M.plate2)
    return k


# ─────────────────────────────── 파트: 몸통 ───────────────────────────────

def build_torso(M):
    k = Kit("torso", 2.0)
    # 배 (사슬) + 복부 판
    k.box((-9, 0, -6), (9, 14, 6), M.chain)
    k.box((-7, 1.5, 6), (7, 13, 7.5), M.plate2, over={"south": M.abs})
    # 허리띠 + 버클 + 보석
    k.box((-10, -1, -7), (10, 4, 7.5), M.silver)
    k.box((-3, -1.5, 7.5), (3, 4.5, 8.5), M.silver)
    k.box((-1.5, -0.5, 8.5), (1.5, 3.5, 9.3), M.gem, light=15)
    # 아래 가슴 단 + 흉갑
    k.box((-12, 12, -7), (12, 17, 7.2), M.plate2)
    k.box((-11.5, 15.2, 7.2), (11.5, 16, 7.45), M.glow, light=15, faces=["south"])  # 흉갑 아래 빛선
    k.box((-14, 16, -7.5), (14, 28.5, 7.6), M.plate, over={"south": M.chest})
    # 흉갑 룬 (빛나는 문장)
    k.decal("south", (-5.5, 17.5, 5.5, 27.5), 7.8, M.r_sigil)
    # 목 가리개 + 높은 깃
    k.box((-8, 27, -6), (8, 32, 6), M.silver)
    for sx in (-1, 1):
        k.box((sx * 7, 26, -6.5), (sx * 11, 35, 3), M.plate2)
        k.box((sx * 7, 34, -6.5), (sx * 11, 35.5, 3), M.silver)
        # 어깨 뒤로 솟은 얼음 결정 (머리를 감싸는 서리 왕좌 느낌)
        k.spike((sx * 9, 30, -5), 17, 5, M.ices, axis="z", angle=-sx * 22.5, steps=4)
        k.spike((sx * 12.5, 28, -4), 11, 3.5, M.ices, axis="z", angle=-sx * 45, steps=3)
    # 등판
    k.box((-12, 14, -8.5), (12, 27, -7.5), M.plate2)
    return k


# ─────────────────────────────── 파트: 머리 + 왕관 ───────────────────────────────

def build_head(M):
    k = Kit("head", HEAD_SCALE)
    I = M.h_ices
    k.box((-3.5, -2, -3), (3.5, 4, 3), M.h_cloth)                             # 목
    k.box((-6.5, 3, -6.5), (6.5, 16, 6.5), M.h_bone, over={"south": M.h_face})  # 해골
    k.box((-4.5, -0.5, -2), (4.5, 4, 6), M.h_bone, over={"south": M.h_jaw})    # 아래턱
    for sx in (-1, 1):
        k.spike((sx * 2.6, 4.3, 6.2), 3.5, 1.5, [I[2], I[1]], steps=2, down=True)  # 송곳니
        # 투구: 얼굴을 감싸는 옆판 + 앞으로 나온 볼가리개 + 아래로 뾰족한 끝
        k.box((sx * 6.5, 3, -7), (sx * 8, 15, 5), M.h_plate)
        k.box((sx * 5.6, 1.5, 2.5), (sx * 8, 8, 7.2), M.h_plate)
        k.spike((sx * 7, 2, 6), 4, 2.2, I, steps=2, down=True)
        # 화난 눈썹 (짙은 강철, 안쪽이 낮게 기울어짐 — 눈 위로 그늘)
        k.box((sx * 0.3, 10.0, 6.2), (sx * 6.8, 11.8, 8.4), M.h_dark, rot=("z", sx * 22.5, (sx * 0.3, 10.6, 7)))
        # 빛나는 눈 (눈구멍 안쪽, 같은 각도로 치켜 올라감)
        k.box((sx * 1.6, 8.4, 6.35), (sx * 4.6, 9.6, 6.75), M.eye, light=15,
              rot=("z", sx * 22.5, (sx * 1.6, 8.4, 6.5)))
    k.box((-8, 3, -8), (8, 15, -6.5), M.h_plate)                              # 뒤통수 판
    # 왕관 띠 + 보석
    k.box((-8.3, 12, -8.4), (8.3, 16.5, 7.8), M.h_silver, over={"south": M.h_band})
    k.box((-2, 12.4, 7.8), (2, 16.4, 8.9), M.gem, light=15)
    for sx in (-1, 1):
        k.box((sx * 5.2 - 1, 13, 7.8), (sx * 5.2 + 1, 15.5, 8.5), M.gem, light=15)
    # 왕관 얼음 가지 (크게, 개수는 적게)
    k.spike((0, 16.5, 6), 16, 4.4, I, steps=4)
    for sx in (-1, 1):
        k.spike((sx * 4.6, 16.5, 5.5), 10, 3.2, I, axis="z", angle=-sx * 22.5, steps=3)
        k.spike((sx * 4.5, 16.5, -5), 9, 3, I, axis="x", angle=-22.5, steps=3)
        # 큰 뿔: 바깥으로 뻗었다가 위로, 끝은 안쪽으로 굽는다
        k.chain((sx * 8, 13, -1), [(6, 4.4, "z", -sx * 45), (5, 3.8, "z", -sx * 22.5), (6, 3.2, "z", 0),
                                   (5, 2.5, "z", sx * 22.5), (4, 1.7, "z", sx * 45)], I)
    # 고드름 수염
    for x, ln in ((-3.2, 5), (-1.6, 8), (0, 11), (1.6, 8), (3.2, 5)):
        k.spike((x, 0, 4.2), ln, 2.2, I[::-1], steps=2, down=True)
    return k


# ─────────────────────────────── 파트: 망토 ───────────────────────────────
CAPE_W, CAPE_H, CAPE_SPLIT = 34, 58, 26
CAPE_EMBLEM_Y = -13.5   # 망토 문장 중심 (피벗 기준 월드 픽셀)


def paint_cape(M):
    """망토 겉(뒤에서 보이는 면)과 안감을 한 장씩 그린다 (밀도 2)."""
    W, H = CAPE_W * 2, CAPE_H * 2
    rng = np.random.default_rng(7)
    # 너덜너덜한 아래 끝 (열마다 길이가 다름)
    cut = np.zeros(W, dtype=int)
    for x in range(W):
        cut[x] = H - int(abs(math.sin(x * 0.45)) * 10 + abs(math.sin(x * 0.17 + 1)) * 12 + rng.integers(0, 5))
    out = np.zeros((H, W, 4))
    inn = np.zeros((H, W, 4))
    yy = np.linspace(0, 1, H)[:, None]
    n = 0.92 + 0.16 * rng.random((H, W))
    top, bot = _c((36, 64, 140)), _c((16, 28, 70))
    col = top[None, None] + (bot - top)[None, None] * yy[..., None]
    out[..., :3] = col * n[..., None]
    inn[..., :3] = _c((14, 18, 40))[None, None] * n[..., None]
    # 세로 주름
    x = np.arange(W)[None, :]
    fold = 0.85 + 0.15 * np.sin(x * 0.55)
    out[..., :3] *= fold[..., None]
    inn[..., :3] *= fold[..., None]
    # 은 자수 테두리
    out[:, :3, :3] = _c(SILVER)
    out[:, -3:, :3] = _c(SILVER)
    out[:, 3:4, :3] = _c(SILVER_D)
    out[:, -4:-3, :3] = _c(SILVER_D)
    # 아래쪽은 서리가 끼어 하얗게
    for xx in range(W):
        for y in range(cut[xx] - 14, cut[xx]):
            t = (y - (cut[xx] - 14)) / 14
            out[y, xx, :3] = out[y, xx, :3] * (1 - t * 0.8) + _c(ICE_L) * t * 0.8
            inn[y, xx, :3] = inn[y, xx, :3] * (1 - t * 0.6) + _c(ICE) * t * 0.6
        out[cut[xx]:, xx, 3] = 0
        inn[cut[xx]:, xx, 3] = 0
        out[:cut[xx], xx, 3] = 255
        inn[:cut[xx], xx, 3] = 255
    img = _finish(out)
    d = ImageDraw.Draw(img)
    # 문장 받침: 짙은 원판 + 은 테 (빛나는 눈꽃 데칼이 위에 붙는다)
    cx, cy, r = W / 2 - 0.5, -CAPE_EMBLEM_Y * 2, 23
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(10, 16, 40, 255), outline=SILVER + (255,), width=2)
    d.ellipse((cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), outline=SILVER_D + (255,), width=1)
    for ang in range(0, 360, 30):
        px_, py_ = cx + math.cos(math.radians(ang)) * (r + 2), cy + math.sin(math.radians(ang)) * (r + 2)
        d.point((px_, py_), fill=ICE_L + (255,))
    # 위 깃 아래 띠
    d.rectangle((0, 0, W, 3), fill=SILVER_D + (255,))
    # 안감은 잘 안 보이므로 절반 해상도
    return img, _finish(inn).resize((W // 2, H // 2), Image.NEAREST)


def build_cape(M):
    k = Kit("cape", 3.0)
    out, inn = paint_cape(M)
    A = M.P_cape
    W, H = out.size
    r_out = A.request(W, H, lambda r: r.paste(out))
    r_in = A.request(W // 2, H // 2, lambda r: r.paste(inn))
    edge = Skin(A, P_cloth((20, 30, 70)))
    hw = CAPE_W / 2
    fur = Skin(A, P_fur())
    silver = Skin(A, P_metal(SILVER))

    def seg(y0, y1, rot=None):
        # 망토 판 하나. 겉=north(뒤에서 보임), 안=south. 위쪽 기준 y0>y1 (아래로)
        v0 = (-y0) * 2
        v1 = (-y1) * 2
        so = (r_out, (0, v0, W, v1))
        si = (r_in, (0, v0 / 2, W / 2, v1 / 2))
        k.box((-hw, y1, -0.5), (hw, y0, 0.5), edge, rot=rot,
              over={"north": so, "south": si, "down": None})

    seg(-1, -CAPE_SPLIT - 0.5)
    rot_lo = ("x", 22.5, (0, -CAPE_SPLIT, 0))
    seg(-CAPE_SPLIT, -CAPE_H, rot=rot_lo)
    # 등에 빛나는 눈꽃 문장 + 양쪽 가장자리 룬 띠 (겉면 = north)
    e = 10
    k.decal("north", (-e, CAPE_EMBLEM_Y - e, e, CAPE_EMBLEM_Y + e), -0.56, M.r_bigflake)
    for sx in (-1, 1):
        x0 = sx * (hw - 5)
        k.decal("north", (min(x0, x0 + sx * 1.5), -24, max(x0, x0 + sx * 1.5), -3), -0.56, M.r_strip2)
        k.decal("north", (min(x0, x0 + sx * 1.5), -44, max(x0, x0 + sx * 1.5), -27), -0.56, M.r_strip2,
                rot=rot_lo)
    # 털 깃 (어깨를 감쌈) + 은 걸쇠
    k.box((-17, -6, -1), (17, 2, 6), fur)
    k.box((-15, 1.5, 0), (15, 4, 6), fur)
    for sx in (-1, 1):
        k.box((sx * 13 - 2, -5, 5.5), (sx * 13 + 2, -1, 7.5), silver)
        k.box((sx * 13 - 1, -4, 7.5), (sx * 13 + 1, -2, 8.2), M.gem, light=15)
    return k


# ─────────────────────────────── 파트: 팔 ───────────────────────────────

def build_arm(M, side):
    """side = 'right' (-x, 대검) / 'left' (+x, 발톱). 피벗 = 어깨."""
    sx = -1 if side == "right" else 1
    k = Kit(f"{side}_arm", ARM_SCALE)
    O = lambda v: sx * v   # 바깥쪽 + 좌표 → 실제 x
    out_face = "east" if sx > 0 else "west"
    # ── 견갑 (층층이 겹친 판 + 얼음 가시) ──
    k.box((O(-6), -4, -8.5), (O(10), 6, 8.5), M.plate)
    k.box((O(-4), 6, -7), (O(8), 9, 7), M.plate2)
    k.box((O(-2), 9, -4.5), (O(6), 10.5, 4.5), M.silver)
    k.box((O(-6.5), -5.5, -9), (O(10.5), -3.5, 9), M.silver)
    k.box((O(-6), -6.1, -8.6), (O(10.2), -5.5, 8.6), M.glow, light=15)          # 테 아래 빛나는 선
    k.box((O(-5), -9.5, -7.5), (O(10), -5.5, 7.5), M.plate2)
    k.box((O(-4), -12.5, -6.5), (O(9.5), -9.5, 6.5), M.plate)
    k.decal(out_face, (-5.5, -2.5, 5.5, 5.5), O(10.05), M.r_flake)
    k.spike((O(2), 10, 0), 17, 5, M.ices, axis="z", angle=-sx * 22.5, steps=4)
    k.spike((O(5), 8, -5.5), 11, 3.5, M.ices, axis="z", angle=-sx * 45, steps=3)
    k.spike((O(5), 8, 5.5), 11, 3.5, M.ices, axis="z", angle=-sx * 45, steps=3)
    k.spike((O(0), 8, -7), 9, 3, M.ices, axis="x", angle=-45, steps=3)
    # ── 위팔 ──
    k.box((O(-4), -20, -4), (O(4), -10, 4), M.chain)
    k.box((O(-4.5), -17, -4.5), (O(4.5), -14, 4.5), M.plate2)
    # ── 팔꿈치 ──
    k.box((O(-5), -24, -5.5), (O(5), -18, 5), M.plate)
    k.spike((O(0), -21, -5), 8, 3, M.ices, axis="x", angle=-45, steps=3)
    if side == "right":
        # 앞으로 내민 아래팔 + 주먹 (대검 손잡이를 쥠)
        k.box((O(-5), -26, -3), (O(5), -16, 11), M.plate)
        k.box((O(-6), -27.5, 4), (O(6), -14.5, 8), M.silver)
        k.decal(out_face, (-2.5, -25, 3.5, -17), O(5.05), M.r_flake)
        k.box((O(-4.5), -28, 10.5), (O(4.5), -16, 18.5), M.dark)
        k.box((O(-4.7), -20, 16.5), (O(4.7), -17, 19), M.silver)   # 손가락 마디
        k.spike((O(5), -21, 2), 7, 2.6, M.ices, axis="z", angle=-sx * 45, steps=2)  # 팔뚝 바깥 가시
    else:
        # 아래로 늘어뜨린 거대한 발톱 건틀릿
        k.box((O(-5.5), -34, -5.5), (O(5.5), -21, 5.5), M.plate)
        k.box((O(-6.5), -27, -6.5), (O(6.5), -22, 6.5), M.silver)
        k.decal("south", (-3, -33, 3, -28), 5.55, M.r_flake)
        k.spike((O(5.5), -27, 0), 9, 3, M.ices, axis="z", angle=-sx * 45, steps=3)  # 팔뚝 바깥 가시
        k.box((O(-5.5), -41, -4.5), (O(5.5), -33, 5.5), M.dark)                      # 손등
        k.box((O(-5.8), -40, 4.5), (O(5.8), -35, 6.5), M.silver)                     # 너클
        for xo in (-3.6, -1.2, 1.2, 3.6):
            k.spike((O(xo), -35, 6), 4, 1.8, M.ices, axis="x", angle=45, steps=2)    # 너클 가시
        # 손가락 발톱 4개: 아래로 → 앞으로 크게 휘어짐 (빛나는 얼음)
        for i, xo in enumerate((-4, -1.35, 1.35, 4)):
            ln = 1.0 if i in (1, 2) else 0.82
            k.chain((O(xo), -40, 4.5), [(6 * ln, 3.0, "x", -22.5), (6 * ln, 2.4, "x", -45),
                                        (5 * ln, 1.6, "x", -45)], M.ice_glow, light=10, down=True)
        # 엄지 (안쪽)
        k.chain((O(-5.5), -37, 3), [(5, 2.6, "z", sx * 22.5), (5, 1.8, "z", sx * 45)], M.ice_glow,
                light=10, down=True)
    return k


# ─────────────────────────────── 파트: 대검 ───────────────────────────────
HAND = (0, -22, 14.5)   # 오른 어깨 피벗 기준 주먹 위치


def build_sword(M):
    k = Kit("sword", 3.0)
    hx, hy, hz = HAND
    R = ("x", SWORD_TILT, HAND)

    def sb(frm, to, skin, light=0, **kw):
        k.box((hx + frm[0], hy + frm[1], hz + frm[2]), (hx + to[0], hy + to[1], hz + to[2]), skin,
              rot=R, light=light, **kw)

    # 폼멜: 빛나는 얼음 결정
    sb((-2.6, -17, -2.6), (2.6, -12, 2.6), M.ice_glow, light=12)
    sb((-1.4, -21, -1.4), (1.4, -17, 1.4), M.ice_glow, light=12)
    sb((-3.2, -13, -1), (3.2, -12, 1), M.s_silver)
    # 손잡이
    sb((-1.7, -12, -1.7), (1.7, 3, 1.7), M.s_grip)
    # 코등이: 가운데 + 날개 + 위로 솟는 얼음 날개
    sb((-5, 2.5, -2.8), (5, 9, 2.8), M.s_silver)
    sb((-3.5, 9, -2.2), (3.5, 10.5, 2.2), M.s_silver)
    for s in (-1, 1):
        sb((s * 5, 3.5, -1.8), (s * 12, 7.5, 1.8), M.s_silver)
        sb((s * 12, 2.5, -1.5), (s * 14.5, 12, 1.5), M.s_ice)
        sb((s * 12.6, 12, -1.0), (s * 14.2, 17, 1.0), M.s_ice_l)
        sb((s * 13, 17, -0.6), (s * 14, 20, 0.6), M.s_ice_l)
        sb((s * 8, -1, -1.2), (s * 10, 3.5, 1.2), M.s_ice)
        sb((s * 8.5, -4, -0.7), (s * 9.5, -1, 0.7), M.s_ice_l)
    sb((-1.8, 4, 2.8), (1.8, 8, 3.7), M.gem, light=15)
    sb((-1.8, 4, -3.7), (1.8, 8, -2.8), M.gem, light=15)
    # 날: 가운데 몸체 (점점 가늘어짐) + 빛나는 날 가장자리
    tiers = [(10.5, 46, 5), (46, 56, 4), (56, 62, 3), (62, 66, 2), (66, 69.5, 1)]
    for y0, y1, w in tiers:
        sb((-w, y0, -1.2), (w, y1, 1.2), M.s_blade)
        if w > 1:
            sb((-w - 1.6, y0, -0.6), (-w, y1, 0.6), M.glow_v, light=15)
            sb((w, y0, -0.6), (w + 1.6, y1, 0.6), M.glow_v, light=15)
    sb((-0.7, 66, -0.6), (0.7, 72, 0.6), M.glow_v, light=15)
    # 홈의 룬 (양면)
    sb((-1.3, 13, 1.25), (1.3, 44, 1.25), M.r_strip, light=15, faces=["south"])
    sb((-1.3, 13, -1.25), (1.3, 44, -1.25), M.r_strip, light=15, faces=["north"])
    # 날 밑동의 얼음 결정 + 날 따라 톱니처럼 솟은 얼음 (계단식)
    for s in (-1, 1):
        sb((s * 6.6, 10.5, -1.7), (s * 9, 17, 1.7), M.s_ice)
        sb((s * 6.6, 17, -1.2), (s * 8, 21, 1.2), M.s_ice_l)
        for y in ((25, 35) if s < 0 else (30, 40)):
            sb((s * 6.6, y, -0.9), (s * 8.2, y + 4, 0.9), M.s_ice)
            sb((s * 6.6, y + 4, -0.6), (s * 7.4, y + 6.5, 0.6), M.s_ice_l)
    return k


# ─────────────────────────────── 파트: 얼음 파편 ───────────────────────────────

def build_shard(M):
    """떠다니는 얼음 파편: 0°/45° 단을 번갈아 쌓은 별모양 단면의 쌍뿔 결정."""
    k = Kit("shard", 1.0)
    G = M.ice_glow
    tiers = [(0, 4, 6.0), (4, 8, 5.0), (8, 11, 3.8), (11, 14, 2.6), (14, 17, 1.4)]
    for i, (y0, y1, w) in enumerate(tiers):
        for d in (1, -1):
            f = 1.0 if d > 0 else 0.75          # 아래쪽 뿔은 조금 짧게
            lo, hi = (y0 * f, y1 * f) if d > 0 else (-y1 * f, -y0 * f)
            k.box((-w / 2, lo, -w / 2), (w / 2, hi, w / 2), G, light=12)
            k.box((-w * 0.42, lo, -w * 0.42), (w * 0.42, hi, w * 0.42), G, light=12, rot=("y", 45, (0, 0, 0)))
    # 옆에 붙은 작은 결정 셋
    k.spike((2.5, -4, 0), 9, 2.6, G, axis="z", angle=-45, steps=3, light=12)
    k.spike((-2.5, 0, 0), 7, 2.2, G, axis="z", angle=45, steps=3, light=12)
    k.spike((0, -6, 2.5), 6, 2.0, G, axis="x", angle=45, steps=2, light=12)
    return k


# ─────────────────────────────── 리그 ───────────────────────────────

def px(v):
    return [round(c / 16.0, 4) for c in v]


BODY_BOB = {"type": "bob", "amplitude": 0.04, "period": 60, "phase": 0.0}


def rig_spec(models):
    parts = []

    def add(pid, model, off, scale, frame="body", anims=()):
        parts.append({"id": pid, "model": model, "offset": px(off), "scale": scale,
                      "rotation": [0, 0, 0], "frame": frame, "anims": list(anims)})

    add("legs", models["legs"], (0, HIP_Y, 0), 2.0)
    add("torso", models["torso"], (0, HIP_Y, 0), 2.0, anims=[BODY_BOB])
    add("cape", models["cape"], (0, 63, -8), 3.0,
        anims=[BODY_BOB, {"type": "sway", "axis": "x", "angle": 4, "period": 50, "phase": 0.0}])
    add("head", models["head"], (0, NECK_Y, 0), round(HEAD_SCALE * HEAD_GROW, 4),
        anims=[BODY_BOB, {"type": "sway", "axis": "y", "angle": 9, "period": 120, "phase": 0.0}])
    rs = (-SHOULDER[0], SHOULDER[1], SHOULDER[2])
    ls = SHOULDER
    arm_idle = {"type": "sway", "axis": "x", "angle": 4, "period": 60, "phase": 0.0}
    add("right_arm", models["right_arm"], rs, ARM_SCALE,
        anims=[BODY_BOB, arm_idle, {"type": "swing", "axis": "x", "angle": -100, "ticks": 14}])
    add("sword", models["sword"], rs, 3.0,
        anims=[BODY_BOB, arm_idle, {"type": "swing", "axis": "x", "angle": -100, "ticks": 14}])
    add("left_arm", models["left_arm"], ls, ARM_SCALE,
        anims=[BODY_BOB, {"type": "sway", "axis": "x", "angle": 5, "period": 60, "phase": 0.5},
               {"type": "swing", "axis": "x", "angle": -75, "ticks": 10}])
    for i in range(3):
        add(f"shard_{i + 1}", models["shard"], (0, 0, 0), 0.9, frame="world", anims=[
            {"type": "orbit", "radius": 2.3, "speed": 3.0, "phase": i * 120.0, "height": 3.4 + 0.5 * (i % 2)},
            {"type": "spin", "axis": "y", "speed": 6.0},
            {"type": "bob", "amplitude": 0.25, "period": 50, "phase": i / 3.0},
        ])
    notes = ("서리 군주 (키 약 5.5블록, 대검 끝까지 약 6.4블록). 보스 오른손 = -X 쪽(대검), 왼손 = +X 쪽(발톱), 앞 = +Z. "
             "모든 포즈는 모델에 구워 넣었으므로 rotation 은 전부 [0,0,0]. "
             "sword 파트는 right_arm 과 같은 피벗(오른 어깨)·같은 anims 를 써야 손에 붙어 있다(둘이 함께 swing). "
             "swing angle 음수 = 팔이 앞으로 들려 올라감(+Y 를 +Z 쪽으로 돌리는 방향이 양수; mc3d.mat/JOML rotateX 와 동일). "
             "-100° 스윙은 대검을 머리 위 뒤로 치켜올렸다가 제자리로 내려치는 동작이 된다. "
             "다리를 뺀 몸 위쪽 파트(torso/head/cape/arms/sword)는 같은 bob 으로 숨쉬기를 맞춘다; legs 는 고정. "
             "head 는 모델 작성 스케일 1.6 을 1.18 배 키운 1.888 로 표시한다. "
             "shard 3개는 frame=world orbit (offset 0, 높이는 orbit.height), spin+bob 추가. "
             "텍스처: augsky:boss/frost_tyrant_{body,head,cape,sword}(정적) + frost_tyrant_glow(128x128, 16프레임, frametime 3). "
             "발광: 눈/보석/룬/대검 날/발톱/파편에 light_emission 10~15.")
    return {"parts": parts, "notes": notes}


# ─────────────────────────────── 미리보기 (z-버퍼 렌더러) ───────────────────────────────
# mc3d.render 는 면 정렬 순서가 뒤집혀 있어(가까운 면을 먼저 그림) 여러 박스가 겹치면 틀리게 보인다.
# 여기서는 같은 투영/UV 규칙을 쓰되 픽셀 단위 z-버퍼로 그린다.

def zrender(parts, size=512, yaw=-35, pitch=20, bg=(20, 22, 34), night=False, frame=0, ss=2, fit=None):
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
    glow = np.zeros((S, S))
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
        # 평면 깊이: z = a*x + b*y + c
        A3 = np.array([[scr[i][0], scr[i][1], 1] for i in (0, 1, 3)])
        try:
            abc = np.linalg.solve(A3, np.array([pts[0][2], pts[1][2], pts[3][2]]))
        except np.linalg.LinAlgError:
            continue
        X, Y = np.meshgrid(np.arange(bx0, bx1) + 0.5, np.arange(by0, by1) + 0.5)
        Z = abc[0] * X + abc[1] * Y + abc[2]
        if lv:   # 면 위에 붙은 판(데칼)이 이기도록 아주 조금 앞으로
            Z = Z + 1e-4
        zsub = zb[by0:by1, bx0:bx1]
        sel = m & (Z > zsub)
        if not sel.any():
            continue
        if night:
            k = max(0.18, lv / 15.0) if lv else 0.18 * fl / 0.8
        else:
            k = 1.0 if lv >= 8 else fl
        col = patch[..., :3] * k
        img[by0:by1, bx0:bx1][sel] = col[sel]
        zsub[sel] = Z[sel]
        if lv:
            glow[by0:by1, bx0:bx1][sel] = lv / 15.0
        else:
            glow[by0:by1, bx0:bx1][sel] = 0
    out = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    if night:
        # 빛나는 부분 번짐(블룸) — 미리보기 연출용
        gl = Image.fromarray((glow * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(S / 60))
        g = np.array(gl).astype(float)[..., None] / 255.0
        o = np.array(out).astype(float) + g * _c(CY)[None, None] * 0.8
        out = Image.fromarray(o.clip(0, 255).astype(np.uint8))
    return out.resize((size, size), Image.LANCZOS)


def rig_parts(kits, spec, swing=0.0):
    """리그 스펙대로 파트를 배치한 (model, mat) 목록. swing 은 0..1 (공격 동작 미리보기)."""
    by_id = {}
    out = []
    shard_k = 0
    for p in spec["parts"]:
        kit = kits[p["id"].split("_")[0] if p["id"].startswith("shard") else p["id"]]
        off = list(p["offset"])
        pitch = 0.0
        for a in p["anims"]:
            if a["type"] == "swing" and a["axis"] == "x":
                pitch += a["angle"] * swing
            if a["type"] == "orbit":
                ang = math.radians(a["phase"] + 100)
                off = [math.sin(ang) * a["radius"], a["height"], math.cos(ang) * a["radius"]]
        yaw = 0.0
        if p["id"].startswith("shard"):
            yaw = 30 * shard_k
            shard_k += 1
        out.append((kit.m, mat(translate=off, scale=p["scale"], pitch=pitch, yaw=yaw)))
        by_id[p["id"]] = out[-1]
    return out


def hitbox_model(M):
    """1.56 x 5.2 히트박스 외곽선 (미리보기 전용, 파일로 쓰지 않으므로 범위 제한 없음)."""
    m = Model("preview/hitbox")
    a = Atlas("preview_hit", 16)
    m.use("h", a)
    c = ("h", a.cell((255, 80, 80, 255), "flat"))
    w, H, t = 1.56 * 8, 5.2 * 16, 0.35
    for x in (-w, w):
        for z in (-w, w):
            m.box((8 + x - t, 8, 8 + z - t), (8 + x + t, 8 + H, 8 + z + t), c)
    for y in (0, H):
        for z in (-w, w):
            m.box((8 - w, 8 + y - t, 8 + z - t), (8 + w, 8 + y + t, 8 + z + t), c)
        for x in (-w, w):
            m.box((8 + x - t, 8 + y - t, 8 - w), (8 + x + t, 8 + y + t, 8 + w), c)
    return (m, mat())


def labeled_sheet(images, labels, cols, cell, title=None):
    rows = (len(images) + cols - 1) // cols
    top = 40 if title else 0
    sheet = Image.new("RGB", (cols * cell, top + rows * (cell + 26)), (14, 14, 22))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 18)
    if title:
        d.text((10, 8), title, font=ImageFont.truetype(FONT, 22), fill=(200, 240, 255))
    for i, im in enumerate(images):
        x, y = (i % cols) * cell, top + (i // cols) * (cell + 26)
        sheet.paste(im.convert("RGB").resize((cell, cell), Image.LANCZOS), (x, y))
        d.text((x + 8, y + cell + 3), labels[i], font=f, fill=(225, 230, 240))
    return sheet


def make_previews(M, kits, spec):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    parts = rig_parts(kits, spec)
    hb = hitbox_model(M)
    # 전체 뷰 공통 프레이밍 (가장 큰 뷰 기준)
    fit = (0.0, 3.2, 8.0)
    # 이 렌더러에서 yaw=0 이 정면(+Z 쪽에서 봄)
    views = [("앞 3/4", -35, 12), ("옆 (오른쪽)", 90, 6), ("뒤 3/4", 180 - 35, 12)]
    ims, labels = [], []
    for name, yaw, pitch in views:
        ims.append(zrender(parts, 640, yaw=yaw, pitch=pitch, fit=fit))
        labels.append(name)
    ims.append(zrender(parts + [hb], 640, yaw=-20, pitch=10, fit=fit))
    labels.append("히트박스 1.56×5.2")
    ims.append(zrender(parts, 640, yaw=-35, pitch=12, night=True, fit=fit, frame=5))
    labels.append("밤 (발광)")
    ims.append(zrender(rig_parts(kits, spec, swing=1.0), 640, yaw=-70, pitch=8, fit=fit))
    labels.append("공격 스윙 최고점")
    sheet = labeled_sheet(ims, labels, 3, 480, "서리 군주 (frost_tyrant) — 리그")
    p1 = os.path.join(PREVIEW_DIR, f"{BOSS}.png")
    sheet.save(p1)
    # 파트 클로즈업
    ims, labels = [], []
    for pid, kit in kits.items():
        for yaw in (-35, 180 - 35):
            ims.append(zrender([(kit.m, None)], 360, yaw=yaw, pitch=18))
            labels.append(f"{pid} ({len(kit.m.elements)})")
    sheet2 = labeled_sheet(ims, labels, 4, 300, "서리 군주 — 파트 (요소 수)")
    p2 = os.path.join(PREVIEW_DIR, f"{BOSS}_parts.png")
    sheet2.save(p2)
    # 대표 이미지 (낮 정면 3/4 + 밤 뒤 3/4)
    fit2 = (0.0, 3.2, 7.4)
    hero = [zrender(parts, 760, yaw=-25, pitch=10, fit=fit2),
            zrender(parts, 760, yaw=160, pitch=12, night=True, fit=fit2, frame=3)]
    p4 = os.path.join(PREVIEW_DIR, f"{BOSS}_hero.png")
    labeled_sheet(hero, ["서리 군주 — 낮", "서리 군주 — 밤 (발광 + 애니메이션 룬)"], 2, 760).save(p4)
    # 텍스처 아틀라스 확인용
    tex = [a.frame0().resize((256, 256), Image.NEAREST) for a in M.atlases()]
    p3 = os.path.join(PREVIEW_DIR, f"{BOSS}_textures.png")
    labeled_sheet(tex, [a.name.split("/")[-1] for a in M.atlases()], 5, 256).save(p3)
    return [p1, p2, p3, p4]


# ─────────────────────────────── 진입점 ───────────────────────────────

def _build(assets_root):
    M = Mats()
    kits = {
        "legs": build_legs(M),
        "torso": build_torso(M),
        "head": build_head(M),
        "cape": build_cape(M),
        "right_arm": build_arm(M, "right"),
        "sword": build_sword(M),
        "left_arm": build_arm(M, "left"),
        "shard": build_shard(M),
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
    root = os.path.join(HERE, "_scratch", "boss_frost", "assets", "augsky")
    spec = build(root)
    for p in spec["parts"]:
        print(p["id"], p["model"], p["offset"], p["scale"])
