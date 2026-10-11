"""
무기 키트: 작은 정육면체(복셀)를 쌓아 무기를 만들고, 마인크래프트 3D 아이템 모델로 바꾼다.

좌표 (설계 좌표)
  - 무기는 세워서 만든다: 손잡이가 아래, 끝이 위(+Y). 앞면(인벤토리에서 보이는 면)은 +Z.
  - X 는 가운데 선에서 잰 거리, Z 는 가운데 면에서 잰 거리, Y 는 맨 아래에서 잰 높이. 단위는 복셀.
  - 1 복셀 = 0.5 모델 단위 = 블록의 1/32. 복셀 가운데의 좌표는 X, Z 가 ±0.5, ±1.5 ... (가운데 선이 복셀 사이)
    그래서 폭이 짝수(2, 4, 6 ...)인 부품이 좌우 대칭으로 깔끔하게 놓인다.
  - 크기 한도: X ±24, Y 0..72, Z ±16 복셀.

재료 (Mat): 색 4단계(어두움 → 밝음)와 무늬. glow=True 면 셰이더가 조명 없이 스스로 빛나게 그린다(알파 252),
  anim 무늬(flow, sparkle, pulse, fire, rainbow)는 애니메이션 텍스처가 된다.

부품 함수 (모두 Weapon 의 메서드, 재료는 이름 문자열)
  fill(fn, mat)                fn(X, Y, Z) -> bool 인 모든 복셀 (가장 자유로운 방법)
  box(x0, x1, y0, y1, z0, z1, mat)   설계 좌표 범위 (복셀 가운데가 범위 안에 들면 채움)
  cyl(y0, y1, r, mat, rz=None, cx=0, cz=0)   세로 원기둥 (rz 를 주면 타원)
  ball(cx, cy, cz, rx, ry, rz, mat)            타원체
  prism(mask, half_depth, mat)  mask(X, Y) -> bool 인 2D 모양을 앞뒤로 half_depth 만큼 (half_depth 는 숫자나 함수(X, Y))
  blade(y0, y1, width, mats=(edge, core, ridge), thick=(1, 2, 3), tip=0.25, curve=0)  곧은/휜 날 (width 는 숫자나 함수(t), t=0..1)
  tube(points, radius, mat, rz=None)   점들(X, Y, Z)을 잇는 굵은 선 (곡선 날개, 낫날, 덩굴, 활 시위 등)
                               복셀 가운데가 ±0.5 에 있으므로 가는 선도 radius 0.75 이상(2복셀 두께)이어야 보인다
  gem(cx, cy, r, mat, frame=None, depth=2, cz=0)   테두리 있는 보석 (앞뒤로 튀어나옴)
  clear(fn)                    fn 이 참인 복셀을 비운다 (구멍, 홈)
  mirror()                     오른쪽(X>0)을 왼쪽에 그대로 복사

build(name, assets_root) 는 텍스처와 모델(item/<name>.json), 아이템 정의(items/<name>.json)를 쓰고 Model 을 돌려준다.

보스 조각과 투구도 같은 방식으로 쌓는다 (맨 아래 '보스 조각, 투구' 참고)
  part(mats, size, vox)   보스 조각: 설계 원점 = 회전 중심 = 모델 (8,8,8). build("boss/<보스>_<조각>", ...)
  helmet(mats)            3D 투구: 1 복셀 = 스킨 1픽셀, 머리는 -4..4, 얼굴은 -Z. build("armor/<세트>_helmet", ...)
  helmet_preview(model, png), rig_preview(spec, {id: model}, png, 제목)  미리보기
"""
import colorsys
import json
import math
import os
import random

import numpy as np
from PIL import Image

from mc3d import Atlas, Model, hexc, mix, shade, hsv

VOX = 0.5                 # 1 복셀의 모델 단위 크기
W, H, D = 48, 72, 32      # 격자 크기 (X, Y, Z)
CX, CZ = W // 2, D // 2   # 가운데 선 (복셀 경계)
Y0 = -4.0                 # 설계 Y=0 의 모델 y
GLOW, GLOW_SOFT, GLOW_HALF = 252, 251, 250   # 스스로 빛나는 픽셀 표시 (pack/shaders)
ANIM_FRAMES = 16


# ─────────────────────────── 재료 ───────────────────────────

class Mat:
    """
    ramp: 어두운 색 → 밝은 색 4개 (hex)
    style: metal(세로 광택), stone(거친 잡음), wood(나뭇결), grip(감은 끈), cloth, gem(가운데가 밝은 보석),
           scale(비늘), crystal(각진 결정), flat
           움직이는 무늬: flow(빛이 위로 흐름), sparkle(반짝이는 점), pulse(숨쉬듯 밝아짐), fire(불꽃), rainbow(무지개)
    glow: True 면 조명을 받지 않고 스스로 빛남
    """
    ANIM = ("flow", "sparkle", "pulse", "fire", "rainbow")

    def __init__(self, ramp, style="metal", glow=False, seed=0):
        self.ramp = [hexc(c) if isinstance(c, str) else tuple(c) for c in ramp]
        while len(self.ramp) < 4:
            self.ramp.append(self.ramp[-1])
        self.style = style
        self.glow = glow
        self.seed = seed

    @property
    def animated(self):
        return self.style in self.ANIM

    def _ramp(self, t):
        t = max(0.0, min(1.0, t)) * 3
        i = min(2, int(t))
        return mix(self.ramp[i], self.ramp[i + 1], t - i)

    def cell(self, frame=0, frames=1):
        """16x16 무늬 칸 한 장."""
        r = random.Random(self.seed * 7919 + 17)
        n = [[r.random() for _ in range(16)] for _ in range(16)]
        img = Image.new("RGBA", (16, 16))
        px = img.load()
        t = frame / max(1, frames)
        for v in range(16):
            for u in range(16):
                k = n[v][u]
                s = self.style
                if s == "metal":
                    val = 0.45 + 0.25 * math.sin(u * 0.9 + v * 0.15) + 0.18 * (k - 0.5)
                    if (u + v * 3) % 11 == 0:
                        val += 0.3
                elif s == "stone":
                    val = 0.25 + 0.6 * k
                elif s == "wood":
                    val = 0.35 + 0.25 * math.sin(u * 1.7 + math.sin(v * 0.6) * 2) + 0.15 * (k - 0.5)
                elif s == "grip":
                    band = (v + (u // 4)) % 4
                    val = [0.2, 0.55, 0.75, 0.45][band] + 0.1 * (k - 0.5)
                elif s == "cloth":
                    val = 0.4 + 0.2 * ((u + v) % 2) + 0.2 * (k - 0.5)
                elif s == "gem":
                    d = math.hypot(u - 6.5, v - 6.5) / 9
                    val = 1.0 - d + 0.12 * (k - 0.5)
                    if (u, v) in ((5, 4), (6, 4), (5, 5)):
                        val = 1.3
                elif s == "scale":
                    val = 0.35 + 0.45 * ((u % 4 + (v // 2 % 2) * 2) % 4 < 2) + 0.1 * (k - 0.5)
                elif s == "crystal":
                    val = 0.45 + 0.4 * (((u + v) // 3) % 2) + 0.15 * (k - 0.5)
                elif s == "flow":
                    w = 0.5 + 0.5 * math.sin(2 * math.pi * ((v / 16) + t) * 2 + u * 0.7)
                    val = 0.35 + 0.55 * w ** 2 + 0.1 * k
                    if k > 0.93:
                        val = 1.25
                elif s == "sparkle":
                    val = 0.35 + 0.2 * k
                    ph = (k * 7.3) % 1.0
                    b = max(0.0, math.sin(2 * math.pi * (t * 2 + ph))) ** 6
                    if k > 0.72:
                        val += 0.9 * b
                elif s == "pulse":
                    val = 0.45 + 0.35 * math.sin(2 * math.pi * t) + 0.15 * (k - 0.5)
                elif s == "fire":
                    w = 0.5 + 0.5 * math.sin(2 * math.pi * (v / 8 + t * 2) + n[v][(u + 3) % 16] * 3)
                    val = 0.3 + 0.7 * w * (0.6 + 0.4 * k)
                elif s == "rainbow":
                    c = hsv(u / 16 * 0.5 + v / 16 * 0.5 + t, 0.55, 0.95 + 0.05 * k)
                    px[u, v] = (c[0], c[1], c[2], GLOW if self.glow else 255)
                    continue
                else:
                    val = 0.5 + 0.1 * (k - 0.5)
                c = self._ramp(val) if val <= 1.0 else mix(self._ramp(1.0), (255, 255, 255, 255), min(1, val - 1))
                px[u, v] = (c[0], c[1], c[2], GLOW if self.glow else 255)
        return img


class AuraMat(Mat):
    """아우라 막 재료: 반투명(알파 251/250 = 75%/50%)으로 스스로 빛나고, 프레임마다 일렁인다. 빈 픽셀은 뚫려 보인다."""

    def __init__(self, style, inner, outer, inner_layer=True, strength=1.0, seed=0):
        super().__init__([outer, outer, inner, inner], style="aura", glow=True, seed=seed)
        self.aura_style = style
        self.inner_c, self.outer_c = hexc(inner), hexc(outer)
        self.inner_layer = inner_layer
        self.strength = strength

    @property
    def animated(self):
        return True

    def cell(self, frame=0, frames=1):
        from weapons3d import Noise, _fbm
        r = random.Random(self.seed * 31 + 7)
        n1, n2 = Noise(self.seed * 13 + 1, period=16, rows=16), Noise(self.seed * 13 + 2, period=16, rows=16)
        t = frame / max(1, frames)
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = img.load()
        st = self.aura_style
        dens = (0.62 if self.inner_layer else 0.38) * self.strength
        for v in range(16):
            for u in range(16):
                y = 15 - v  # 위쪽이 y 가 큼
                if st == "flame":
                    val = _fbm(n1, n2, u * 0.7, y * 0.45 - t * 16)
                elif st == "drip":
                    val = _fbm(n1, n2, u * 0.7, y * 0.45 + t * 16)
                elif st == "void":
                    val = _fbm(n1, n2, u * 0.5 + math.sin(y * 0.4 + t * 6.283) * 1.5, y * 0.35 - t * 16)
                elif st == "smoke":
                    val = _fbm(n1, n2, u * 0.4, y * 0.3 - t * 16)
                elif st == "swirl":
                    val = _fbm(n1, n2, u * 0.6 + y * 0.6 - t * 16, y * 0.2)
                elif st == "wave":
                    val = 0.5 + 0.5 * math.sin(2 * math.pi * (y / 8 - t * 2) + u * 0.5)
                elif st == "frost":
                    val = 0.45 + 0.2 * math.sin(2 * math.pi * (t + (u + y) / 16)) + 0.25 * (r.random() - 0.5)
                elif st == "bolt":
                    val = 0.35 + 0.15 * r.random()
                elif st == "prism":
                    val = _fbm(n1, n2, u * 0.6, y * 0.45 - t * 16)
                else:  # pulse
                    val = 0.45 + 0.3 * math.sin(2 * math.pi * t + (u + y) * 0.2) + 0.15 * (r.random() - 0.5)
                if val < 1 - dens:
                    continue
                k = min(1.0, (val - (1 - dens)) / max(dens, 1e-3))
                if st == "prism":
                    col = hsv(u / 32 + y / 24 + t, 0.5, 1.0)
                else:
                    col = mix(self.outer_c, self.inner_c, k ** 0.8 if self.inner_layer else k * 0.6)
                a = GLOW_SOFT if (self.inner_layer and k > 0.45) else GLOW_HALF
                px[u, v] = (col[0], col[1], col[2], a)
        # 반짝임 / 번개 점
        if st in ("frost", "bolt", "prism", "void") or not self.inner_layer:
            for _ in range(3 if self.inner_layer else 2):
                u, v, ph = r.randrange(16), r.randrange(16), r.random()
                b = max(0.0, math.sin(2 * math.pi * (t * 2 + ph))) ** 4
                if b > 0.3:
                    px[u, v] = (255, 255, 255, GLOW if st == "bolt" else GLOW_SOFT)
        if st == "bolt" and self.inner_layer:
            br = random.Random(self.seed * 100 + frame)
            u, v = br.randrange(16), br.randrange(16)
            for _ in range(br.randint(4, 9)):
                u = (u + br.choice((-1, 0, 1))) % 16
                v = (v + 1) % 16
                px[u, v] = (self.inner_c[0], self.inner_c[1], self.inner_c[2], GLOW)
        return img


# ─────────────────────────── 무기 ───────────────────────────

class Weapon:
    def __init__(self, mats, grip_y=6.0, kind="sword", seed=0, grip_x=0.0, grid=None, pivot=None, vox=None):
        """
        mats: {"이름": Mat}
        grip_y: 손에 쥐는 높이 (설계 Y, 손잡이 가운데)
        kind: 손에 들었을 때의 크기 기준 (sword, greatsword, dagger, katana, axe, hammer, spear, scythe, staff, wand, pickaxe)
        """
        self.mats = dict(mats)
        self.names = list(self.mats)
        # 격자 크기와 원점. 무기는 기본값(가운데 선, 맨 아래가 Y=0). 부품은 pivot(회전 중심)이 설계 원점이 된다
        self.W, self.H, self.D = grid or (W, H, D)
        self.VOX = vox or VOX
        if pivot is None:
            self.CX, self.CY, self.CZ, self.Y0 = self.W // 2, 0, self.D // 2, Y0
        else:
            self.CX, self.CY, self.CZ = pivot
            self.Y0 = 8.0   # 설계 원점(pivot)이 모델 (8, 8, 8)
        xs = np.arange(self.W) + 0.5 - self.CX
        ys = np.arange(self.H) + 0.5 - self.CY
        zs = np.arange(self.D) + 0.5 - self.CZ
        self._X, self._Y, self._Z = np.meshgrid(xs, ys, zs, indexing="ij")
        self.grid = np.zeros((self.W, self.H, self.D), dtype=np.int16)
        self.grip_y = grip_y
        self.grip_x = grip_x
        self.kind = kind
        self.seed = seed
        self.focus = set()   # 아우라가 피어오르는 재료 이름 (기본: glow 재료)
        self.aura = None     # (방식, 안쪽 색, 바깥 색, 반지름, 반짝임 수) — set_aura() 로

    # ---- 기본 ----
    def _id(self, mat):
        if mat is None:
            return 0
        if mat not in self.mats:
            raise KeyError(f"재료 '{mat}' 가 없습니다: {list(self.mats)}")
        return self.names.index(mat) + 1

    def fill(self, fn, mat):
        m = fn(self._X, self._Y, self._Z)
        self.grid[np.asarray(m, dtype=bool)] = self._id(mat)
        return self

    def clear(self, fn):
        self.grid[np.asarray(fn(self._X, self._Y, self._Z), dtype=bool)] = 0
        return self

    def box(self, x0, x1, y0, y1, z0, z1, mat):
        return self.fill(lambda X, Y, Z: (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1) & (Z >= z0) & (Z <= z1), mat)

    def cyl(self, y0, y1, r, mat, rz=None, cx=0.0, cz=0.0):
        rz = r if rz is None else rz
        return self.fill(lambda X, Y, Z: (((X - cx) / r) ** 2 + ((Z - cz) / rz) ** 2 <= 1.0) & (Y >= y0) & (Y <= y1), mat)

    def ball(self, cx, cy, cz, rx, ry, rz, mat):
        return self.fill(lambda X, Y, Z: ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2 <= 1.0, mat)

    def prism(self, mask, half_depth, mat):
        def fn(X, Y, Z):
            m = np.asarray(mask(X, Y), dtype=bool)
            hd = half_depth(X, Y) if callable(half_depth) else half_depth
            return m & (np.abs(Z) <= hd)
        return self.fill(fn, mat)

    def blade(self, y0, y1, width, mats=("edge", "core", "ridge"), thick=(1, 2, 3), tip=0.25, curve=0.0,
              edge_w=1.0, ridge_w=1.0, cx=0.0):
        """
        곧은(또는 휜) 날. width: 반폭(복셀) 숫자 또는 함수(t) (t = 0 밑동 → 1 끝).
        끝 tip 비율 구간에서 뾰족해진다. curve: 끝으로 갈수록 X 로 휘는 정도(복셀).
        mats = (날 가장자리, 날 몸통, 가운데 등줄). 어느 것이든 None 이면 그 부분은 앞 재료로.
        thick = (가장자리, 몸통, 등줄)의 반두께(복셀).
        """
        e_mat, c_mat, r_mat = mats
        c_mat = c_mat or e_mat
        r_mat = r_mat or c_mat

        def half(t):
            w = width(t) if callable(width) else width
            if t > 1 - tip:
                w = w * max(0.0, (1 - t) / tip) ** 0.85 + 0.35
            return w

        def fn_for(part):
            def fn(X, Y, Z):
                t = (Y - y0) / max(1e-6, (y1 - y0))
                inside_y = (t >= 0) & (t <= 1)
                tc = np.clip(t, 0, 1)
                off = curve * tc ** 2 + cx
                hw = np.vectorize(half)(tc)
                ax = np.abs(X - off)
                body = inside_y & (ax <= hw)
                if part == "edge":
                    return body & (ax > hw - edge_w) & (np.abs(Z) <= thick[0])
                if part == "core":
                    return body & (ax <= hw - edge_w) & (np.abs(Z) <= thick[1])
                return body & (ax <= ridge_w) & (np.abs(Z) <= thick[2])
            return fn

        self.fill(fn_for("edge"), e_mat)
        self.fill(fn_for("core"), c_mat)
        if thick[2] > thick[1] or r_mat != c_mat:
            self.fill(fn_for("ridge"), r_mat)
        return self

    def tube(self, points, radius, mat, rz=None, steps=None):
        """points 를 잇는 굵은 선. radius 는 숫자나 함수(t)."""
        pts = np.array(points, dtype=float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        total = seg.sum() or 1
        n = steps or int(total * 3) + 2
        rz_ = rz
        mask = np.zeros_like(self.grid, dtype=bool)
        acc = np.concatenate([[0], np.cumsum(seg)])
        for i in range(n + 1):
            d = total * i / n
            j = min(len(seg) - 1, np.searchsorted(acc, d, side="right") - 1)
            f = (d - acc[j]) / (seg[j] or 1)
            p = pts[j] + (pts[j + 1] - pts[j]) * f
            t = i / n
            r = radius(t) if callable(radius) else radius
            rzz = (rz_(t) if callable(rz_) else rz_) if rz_ is not None else r
            mask |= ((self._X - p[0]) / max(r, 0.3)) ** 2 + ((self._Y - p[1]) / max(r, 0.3)) ** 2 + ((self._Z - p[2]) / max(rzz, 0.3)) ** 2 <= 1
        self.grid[mask] = self._id(mat)
        return self

    def gem(self, cx, cy, r, mat, frame=None, depth=2.0, cz=0.0, frame_w=1.0):
        """테두리(frame) 있는 둥근 보석. 앞뒤로 depth 만큼 튀어나온다."""
        if frame:
            self.fill(lambda X, Y, Z: (np.hypot(X - cx, Y - cy) <= r + frame_w) & (np.abs(Z - cz) <= depth - 0.5), frame)
        self.fill(lambda X, Y, Z: (np.hypot(X - cx, Y - cy) <= r) & (np.abs(Z - cz) <= depth), mat)
        return self

    def mirror(self):
        """오른쪽(X>0)을 왼쪽으로 복사한다."""
        for i in range(min(self.CX, self.W - self.CX)):
            self.grid[self.CX - 1 - i, :, :] = self.grid[self.CX + i, :, :]
        return self

    def set_aura(self, colors, style="flame", size=1.0, focus=None, shell=False):
        """
        아우라 (마크에이지식): 무기 축을 따라 엇갈린 불꽃 판 4장(앞뒤, 옆, 대각선 둘)에 크고 진한 픽셀 불꽃이
        실시간으로 타오른다. 스스로 빛나서(조명 무시) 어두운 곳이든 낮이든 선명하다.
        colors: 바깥 → 안쪽 4색, 예) ["#1a2a8a", "#2a6ae0", "#5ad0ff", "#e8ffff"].  "prism" 이면 무지개.
        style: flame(위로 타오름) frost(뾰족한 서리 결정) bolt(전기가 튐) wave(물결) swirl(휘감김)
               void(소용돌이) drip(아래로 흐름) holy(빛줄기)
        size: 불꽃 크기 배율 (0.5 작게 ~ 1.6 크게). 1 이면 날에서 약 4~6픽셀(1/16 블록) 뻗는다.
        focus: 불꽃이 피어오를 재료 이름들 (기본: glow 재료, 없으면 무기 전체)
        shell: True 면 표면에 얇은 반투명 빛 막도 두른다
        """
        self.aura = {"colors": colors, "style": style, "size": size, "shell": shell}
        if focus:
            self.focus = set(focus)
        return self

    # ---- 굽기 ----
    def bounds(self):
        idx = np.argwhere(self.grid > 0)
        if len(idx) == 0:
            return None
        return idx.min(axis=0), idx.max(axis=0)

    def build(self, name, assets_root, display=None):
        """텍스처와 모델을 쓰고 mc3d.Model 을 돌려준다. name 예: "item/flame_sword" """
        aura_grid = self._aura_shell() if (self.aura and self.aura.get("shell")) else None
        static = [n for n in self.names if not self.mats[n].animated]
        anim = [n for n in self.names if self.mats[n].animated and not isinstance(self.mats[n], AuraMat)]
        auras = [n for n in self.names if isinstance(self.mats[n], AuraMat)]
        if len(static) > 16 or len(anim) > 4:
            raise ValueError("재료가 너무 많습니다 (고정 재료 16, 움직이는 재료 4 까지)")
        model = Model(name)
        cells = {}
        tex_root = os.path.join(assets_root, "textures")
        if static:
            at = Atlas(name, size=64, frames=1)
            for n in static:
                reg = at.alloc(16, 16)
                reg.paste(self.mats[n].cell())
                cells[n] = ("s", reg)
            model.use("s", at)
            at.save(tex_root)
        # 움직이는 재료: 불투명한 빛(흐르는 심지 등)은 프레임 사이를 부드럽게 섞고,
        # 반투명 아우라 막은 표시용 알파(251/250)가 섞이면 안 되므로 섞지 않는다
        for key, group, interp in (("m", anim, True), ("a", auras, False)):
            if not group:
                continue
            aa = Atlas(name + ("_anim" if key == "m" else "_aura"), size=32, frames=ANIM_FRAMES, frametime=2, interpolate=interp)
            for n in group:
                reg = aa.alloc(16, 16)
                for f in range(ANIM_FRAMES):
                    reg.paste(self.mats[n].cell(f, ANIM_FRAMES), f)
                cells[n] = (key, reg)
            model.use(key, aa)
            aa.save(tex_root)
        self._mesh(model, cells, self.grid, opaque=self.grid > 0)
        if aura_grid is not None:
            # 반투명 막은 불투명한 무기를 다 그린 뒤에 그려야 뒤가 비친다 (모델 안 순서대로 그려짐)
            self._mesh(model, cells, aura_grid, opaque=(self.grid > 0) | (aura_grid > 0))
        if self.aura:
            self._flames(model, name, assets_root)
        model.display = self._display() if display is None else display
        model.write(assets_root)
        return model

    def _mesh(self, model, cells, g, opaque):
        used = np.zeros_like(g, dtype=bool)
        filled = opaque
        for z in range(self.D):
            for y in range(self.H):
                for x in range(self.W):
                    m = g[x, y, z]
                    if m == 0 or used[x, y, z]:
                        continue
                    # 16 경계를 넘지 않게 (텍스처 픽셀을 복셀에 딱 맞추려고)
                    xe, ye, ze = (x // 16 + 1) * 16, (y // 16 + 1) * 16, (z // 16 + 1) * 16
                    x1 = x
                    while x1 + 1 < min(self.W, xe) and g[x1 + 1, y, z] == m and not used[x1 + 1, y, z]:
                        x1 += 1
                    y1 = y
                    while y1 + 1 < min(self.H, ye) and np.all(g[x:x1 + 1, y1 + 1, z] == m) and not used[x:x1 + 1, y1 + 1, z].any():
                        y1 += 1
                    z1 = z
                    while z1 + 1 < min(self.D, ze) and np.all(g[x:x1 + 1, y:y1 + 1, z1 + 1] == m) and not used[x:x1 + 1, y:y1 + 1, z1 + 1].any():
                        z1 += 1
                    used[x:x1 + 1, y:y1 + 1, z:z1 + 1] = True
                    self._emit(model, cells, m, x, y, z, x1, y1, z1, filled)

    def _emit(self, model, cells, m, x0, y0, z0, x1, y1, z1, filled):
        name = self.names[m - 1]
        key, reg = cells[name]
        mat = self.mats[name]

        def exposed(sl):
            part = filled[sl]
            return part.size == 0 or not part.all()

        faces = {}
        bx, by, bz = slice(x0, x1 + 1), slice(y0, y1 + 1), slice(z0, z1 + 1)
        if z1 + 1 >= self.D or exposed((bx, by, z1 + 1)):
            faces["south"] = (x0, x1 + 1, y0, y1 + 1, "xy", False)
        if z0 - 1 < 0 or exposed((bx, by, z0 - 1)):
            faces["north"] = (x0, x1 + 1, y0, y1 + 1, "xy", True)
        if x1 + 1 >= self.W or exposed((x1 + 1, by, bz)):
            faces["east"] = (z0, z1 + 1, y0, y1 + 1, "zy", True)
        if x0 - 1 < 0 or exposed((x0 - 1, by, bz)):
            faces["west"] = (z0, z1 + 1, y0, y1 + 1, "zy", False)
        if y1 + 1 >= self.H or exposed((bx, y1 + 1, bz)):
            faces["up"] = (x0, x1 + 1, z0, z1 + 1, "xz", False)
        if y0 - 1 < 0 or exposed((bx, y0 - 1, bz)):
            faces["down"] = (x0, x1 + 1, z0, z1 + 1, "xz", False)
        if not faces:
            return
        s = 16.0 / reg.atlas.size
        out = {}
        for f, (a0, a1, b0, b1, plane, flip) in faces.items():
            u0, u1 = a0 % 16, a0 % 16 + (a1 - a0)
            if plane in ("xy", "zy"):
                v0 = 16 - ((b1 - 1) % 16) - 1
                v1 = v0 + (b1 - b0)
            else:
                v0, v1 = b0 % 16, b0 % 16 + (b1 - b0)
            if flip:
                u0, u1 = u1, u0
            uv = [round((reg.x + u0) * s, 4), round((reg.y + v0) * s, 4), round((reg.x + u1) * s, 4), round((reg.y + v1) * s, 4)]
            out[f] = (key, uv)
        frm = (8 + (x0 - self.CX) * self.VOX, self.Y0 + (y0 - self.CY) * self.VOX, 8 + (z0 - self.CZ) * self.VOX)
        to = (8 + (x1 + 1 - self.CX) * self.VOX, self.Y0 + (y1 + 1 - self.CY) * self.VOX, 8 + (z1 + 1 - self.CZ) * self.VOX)
        model.box(frm, to, out, light=15 if mat.glow else 0, shade=not mat.glow)

    # ---- 아우라 ----
    def _aura_shell(self):
        """초점 재료 둘레 1~3 복셀에 아우라 재료를 깐다 (별도 격자). 재료 _aura1(안), _aura2(바깥)를 추가한다."""
        cols = self.aura["colors"]
        style = self.aura["style"]
        inner, outer = (cols[3], cols[1]) if isinstance(cols, list) else ("#ffffff", "#ffffff")
        if style not in ("flame", "frost", "bolt", "wave", "swirl", "drip", "void"):
            style = "pulse"
        layers, strength = 1, 0.8
        names = self.focus or {n for n in self.names if self.mats[n].glow}
        ids = [self.names.index(n) + 1 for n in names if n in self.names]
        src = np.isin(self.grid, ids) if ids else self.grid > 0
        solid = self.grid > 0
        aura = np.zeros_like(self.grid)
        grown = src.copy()
        for layer in range(1, layers + 1):
            nxt = grown.copy()
            # 한 칸씩 6방향으로 넓힌다 (가장자리에서 반대편으로 넘어가지 않게 잘라서)
            nxt[1:, :, :] |= grown[:-1, :, :]
            nxt[:-1, :, :] |= grown[1:, :, :]
            nxt[:, 1:, :] |= grown[:, :-1, :]
            nxt[:, :-1, :] |= grown[:, 1:, :]
            nxt[:, :, 1:] |= grown[:, :, :-1]
            nxt[:, :, :-1] |= grown[:, :, 1:]
            ring = nxt & ~grown & ~solid
            mat_name = "_aura1" if layer == 1 else "_aura2"
            if mat_name not in self.mats:
                self.mats[mat_name] = AuraMat(style, inner, outer, inner_layer=(layer == 1), strength=strength,
                                              seed=self.seed + layer)
                self.names.append(mat_name)
            aura[ring] = self.names.index(mat_name) + 1
            grown = nxt
        return aura

    def _focus_mask(self):
        names = self.focus or {n for n in self.names if self.mats[n].glow and not isinstance(self.mats[n], AuraMat)}
        ids = [self.names.index(n) + 1 for n in names if n in self.names]
        return np.isin(self.grid, ids) if ids else self.grid > 0

    def _flames(self, model, name, assets_root):
        """엇갈린 불꽃 판 4장. 텍스처 1픽셀 = 모델 1단위(1/16 블록) — 마크 픽셀 크기와 같다."""
        from weapons3d import Noise, _fbm
        cfg = self.aura
        size = cfg["size"]
        style = cfg["style"]
        rainbow = cfg["colors"] == "prism"
        ramp = [hexc(c) for c in (cfg["colors"] if not rainbow else ["#000000"] * 4)]
        fm = self._focus_mask()
        if not fm.any():
            return
        # 앞에서 본 초점 모양을 2복셀 = 1픽셀로 줄인다
        front = fm.any(axis=2)                               # (self.W, self.H)
        fw, fh = self.W // 2, self.H // 2
        small = front.reshape(fw, 2, fh, 2).any(axis=(1, 3))  # (fw, fh), 1칸 = 1 모델 단위
        pts = np.argwhere(small)
        reach_max = 5.0 * size
        x_lo, x_hi = pts[:, 0].min(), pts[:, 0].max()
        y_lo, y_hi = pts[:, 1].min(), pts[:, 1].max()
        pad = int(math.ceil(reach_max)) + 1
        u0, u1 = max(0, x_lo - pad), min(fw - 1, x_hi + pad)
        v0, v1 = max(0, y_lo - 2), min(fh - 1, y_hi + pad + 2)
        u0, u1, v0, v1 = int(u0), int(u1), int(v0), int(v1)
        pw, ph = u1 - u0 + 1, v1 - v0 + 1
        # 거리장
        Dm = np.zeros((pw, ph))
        for i in range(pw):
            for j in range(ph):
                Dm[i, j] = np.min(np.hypot(pts[:, 0] - (u0 + i), (pts[:, 1] - (v0 + j)) * 0.85))
        frames = []
        for k in range(ANIM_FRAMES):
            t = k / ANIM_FRAMES
            sheet = Image.new("RGBA", (pw * 2, ph), (0, 0, 0, 0))
            for side in range(2):
                n1, n2 = Noise(self.seed * 7 + side * 3 + 1), Noise(self.seed * 7 + side * 3 + 2)
                px = sheet.load()
                for i in range(pw):
                    for j in range(ph):
                        d = Dm[i, j]
                        if d > reach_max + 0.5:
                            continue
                        X = (u0 + i) - fw / 2 + 0.5
                        Y = v0 + j
                        rise = 0.55 + 0.55 * min(1.0, max(0.0, (Y - y_lo) / max(1, (y_hi - y_lo))))
                        if style in ("flame", "holy", "drip", "void", "swirl"):
                            sgn = 1 if style == "drip" else -1
                            sx = (X * 0.5 + (math.sin(Y * 0.3 + t * 6.283) if style in ("void", "swirl") else 0))
                            n = _fbm(n1, n2, Y * 0.42 + sgn * t * 8, sx)
                        elif style == "frost":
                            n = 0.35 + 0.45 * _fbm(n1, n2, Y * 0.2 - t * 8, X * 1.3) + 0.2 * math.sin(2 * math.pi * (t * 2 + X * 0.3))
                        elif style == "wave":
                            n = 0.5 + 0.45 * math.sin(2 * math.pi * (Y / 9 - t * 2) + X * 0.4)
                        elif style == "bolt":
                            n = 0.3 + 0.35 * _fbm(n1, n2, Y * 0.5 - t * 8, X * 0.9)
                        else:
                            n = _fbm(n1, n2, Y * 0.4 - t * 8, X * 0.5)
                        if d < 0.9:
                            continue  # 무기 자체는 가리지 않는다 (불꽃은 테두리에서 바깥으로)
                        reach = reach_max * rise * (0.1 + 1.25 * n ** 1.6)
                        if reach < 1.2:
                            continue
                        inten = max(0.0, 1 - (d - 0.9) / reach)
                        if inten <= 0.0:
                            continue
                        lvl = 3 if inten > 0.8 else 2 if inten > 0.55 else 1 if inten > 0.28 else 0
                        if rainbow:
                            c = hsv(Y / 18 + t + side * 0.25, 0.65 - lvl * 0.12, 0.7 + lvl * 0.1)
                        else:
                            c = ramp[lvl]
                        a = GLOW if lvl >= 1 else GLOW_SOFT
                        px[side * pw + i, ph - 1 - j] = (c[0], c[1], c[2], a)
                # 불티: 불꽃 위로 떠오르는 점
                er = random.Random(self.seed * 1000 + side)
                for e in range(6):
                    ex = er.randrange(pw)
                    base = er.random()
                    ey = int(((base + t * 1.5) % 1.0) * ph)
                    if Dm[ex, min(ph - 1, ey)] < reach_max * 1.1:
                        c = (255, 255, 255) if not rainbow else hsv(base + t, 0.4, 1.0)[:3]
                        px[side * pw + ex, ph - 1 - ey] = (c[0], c[1], c[2], GLOW)
                if style == "bolt":
                    br = random.Random(self.seed * 50 + k * 2 + side)
                    for _ in range(3):
                        x, y = map(int, pts[br.randrange(len(pts))])
                        dx = br.choice((-1, 1))
                        for step in range(br.randint(3, 6)):
                            x += dx
                            y += br.choice((-1, 0, 1, 1))
                            i, j = x - u0, y - v0
                            if 0 <= i < pw and 0 <= j < ph:
                                px[side * pw + i, ph - 1 - j] = (ramp[3][0], ramp[3][1], ramp[3][2], GLOW)
            frames.append(sheet)
        tex = os.path.join(assets_root, "textures", name + "_flame.png")
        os.makedirs(os.path.dirname(tex), exist_ok=True)
        anim = Image.new("RGBA", (pw * 2, ph * ANIM_FRAMES))
        for k, fr in enumerate(frames):
            anim.paste(fr, (0, k * ph))
        anim.save(tex)
        with open(tex + ".mcmeta", "w", encoding="utf-8") as f:
            json.dump({"animation": {"frametime": 2, "interpolate": False, "width": pw * 2, "height": ph}}, f)
        model.textures["f"] = "augsky:" + name + "_flame"
        model.atlases["f"] = _Frame(frames[0])   # 미리보기용 (첫 프레임)
        # 판 좌표 (모델 단위): 가로 u0..u1+1, 세로 v0..v1+1 (설계 1칸 = 1 모델 단위)
        xa, xb = float(8 + (u0 - fw / 2)), float(8 + (u1 + 1 - fw / 2))
        ya, yb = float(self.Y0 + v0), float(self.Y0 + v1 + 1)
        uvA, uvA_r = [0, 0, 8, 16], [8, 0, 0, 16]
        uvB, uvB_r = [8, 0, 16, 16], [16, 0, 8, 16]
        # 1) 앞뒤 판 (z=8)  2) 옆 판 (x=8)  3) 4) 대각선 판 (y축으로 ±45도)
        model.box((xa, ya, 8), (xb, yb, 8), {"south": ("f", uvA), "north": ("f", uvA_r)}, light=15, shade=False)
        model.box((8, ya, 8 - (xb - 8)), (8, yb, 8 + (xb - 8)), {"east": ("f", uvB_r), "west": ("f", uvB)}, light=15, shade=False)
        for ang, uv, uvr in ((45, uvB, uvB_r), (-45, uvA, uvA_r)):
            model.box((xa, ya, 8), (xb, yb, 8), {"south": ("f", uv), "north": ("f", uvr)}, light=15, shade=False,
                      rotation={"origin": [8, 8, 8], "axis": "y", "angle": ang})

    def _helmet_display(self):
        lo, hi = self.bounds()
        lo_m = [8 + (lo[0] - self.CX) * self.VOX, self.Y0 + (lo[1] - self.CY) * self.VOX, 8 + (lo[2] - self.CZ) * self.VOX]
        hi_m = [8 + (hi[0] + 1 - self.CX) * self.VOX, self.Y0 + (hi[1] + 1 - self.CY) * self.VOX, 8 + (hi[2] + 1 - self.CZ) * self.VOX]
        return _helmet_display_for(lo_m, hi_m)

    # ---- 손에 든 자세 ----
    def _display(self):
        if self.kind == "part":
            return {}   # 보스 조각: ItemDisplay 의 NONE 자세 그대로 (모델 (8,8,8) = 조각 위치)
        if self.kind == "helmet":
            return self._helmet_display()
        lo, hi = self.bounds()
        length = (hi[1] + 1 - lo[1]) * self.VOX                        # 모델 단위 길이
        width = (hi[0] + 1 - lo[0]) * self.VOX
        want = {"greatsword": 26, "scythe": 26, "spear": 27, "staff": 24, "hammer": 22, "axe": 21, "katana": 22,
                "sword": 19, "dagger": 14, "wand": 16, "bow": 23, "pickaxe": 20}.get(self.kind, 19)
        s_hand = want / max(length, 1)
        grip = np.array([8.0 + self.grip_x * self.VOX, self.Y0 + self.grip_y * self.VOX, 8.0])
        c = np.array([8.0, 8.0, 8.0])
        # 바닐라 그림에서 손이 쥐는 곳: 칼은 왼쪽 아래, 활은 왼쪽 위 모서리
        gv = np.array([3.0, 13.0, 8.0]) if self.kind == "bow" else np.array([3.0, 3.0, 8.0])

        def hold(rot_v, trans_v, s0, s1, tilt=0.0, shift=(0.0, 0.0, 0.0)):
            # 세운 모델을 바닐라 대각선 그림과 같은 방향으로: R_new = R_vanilla · Rz(-45)
            # tilt: 손을 축으로 화면 안쪽으로 더 기울이기, shift: 손 위치를 조금 옮기기 (1인칭에서 잘 보이게)
            rv = _rot(*rot_v)
            r_new = _rot(0, 0, tilt) @ rv @ _rot(0, 0, -45)
            t = np.array(trans_v) + rv @ (s0 * (gv - c)) + np.array(shift) - r_new @ (s1 * (grip - c))
            t = np.clip(t, -80, 80)
            return {"rotation": [round(v, 3) for v in _euler_xyz(r_new)], "translation": [round(float(v), 3) for v in t],
                    "scale": [round(s1, 3)] * 3}

        # 손에 든 자세는 바닐라 칼·활과 같은 각도와 자리 (손잡이가 바닐라 칼의 손잡이 자리에 온다).
        # 크기만 무기 종류별 길이(want)로 맞춘다. 아우라가 큰 망치·활은 1인칭에서 화면을 덮지 않게 조금 작게
        fp_mul = 1.0
        if self.aura and self.kind == "hammer":
            fp_mul = 0.85
        if self.aura and self.kind == "bow":
            fp_mul = 0.8     # 당길 때 활이 화면 가운데로 오므로 아우라가 조준을 가리지 않게
        if self.kind == "bow":
            d = {
                "thirdperson_righthand": hold([-80, 260, -40], [-1, -2, 2.5], 0.9, 0.9 * s_hand),
                "firstperson_righthand": hold([0, -90, 25], [1.13, 3.2, 1.13], 0.68, 0.68 * s_hand * fp_mul),
            }
        else:
            d = {
                "thirdperson_righthand": hold([0, -90, 55], [0, 4.0, 0.5], 0.85, 0.85 * s_hand),
                "firstperson_righthand": hold([0, -90, 25], [1.13, 3.2, 1.13], 0.68, 0.68 * s_hand * fp_mul),
            }
        # 왼손: 게임이 왼손일 때 x 위치와 y·z 회전을 뒤집어 그리므로 오른손 값을 그대로 쓰면 거울처럼 대칭이 된다
        d["thirdperson_lefthand"] = dict(d["thirdperson_righthand"])
        d["firstperson_lefthand"] = dict(d["firstperson_righthand"])
        # 인벤토리: 45도 눕혀 칸에 꽉 차게
        mid = np.array([8 + ((lo[0] + hi[0] + 1) / 2 - self.CX) * self.VOX, self.Y0 + (lo[1] + hi[1] + 1) / 2 * self.VOX, 8.0])
        diag = (length + width) * 0.7071
        s_gui = min(1.6, 15.5 / max(diag, 1))
        r = _rot(0, 0, -45)
        t = -(r @ (s_gui * (mid - c)))
        d["gui"] = {"rotation": [0, 0, -45], "translation": [round(float(v), 3) for v in t], "scale": [round(s_gui, 3)] * 3}
        d["fixed"] = {"rotation": [0, 180, 45], "translation": [round(float(-t[0]), 3), round(float(t[1]), 3), 0],
                      "scale": [round(s_gui, 3)] * 3}
        sg = s_gui * 0.55
        d["ground"] = {"rotation": [0, 0, -45], "translation": [round(float(v * 0.55), 3) for v in t[:2]] + [0],
                       "scale": [round(sg, 3)] * 3}
        d["ground"]["translation"][1] += 2
        return d


def _helmet_display_for(lo_m, hi_m):
    """인벤토리/땅/액자/손에 들었을 때 투구가 칸에 맞게. 머리에 쓸 때(head)는 그대로(바닐라 호박과 같은 방식)."""
    span = max(hi_m[i] - lo_m[i] for i in range(3))
    mid = [(lo_m[i] + hi_m[i]) / 2 for i in range(3)]
    s = float(round(min(1.0, 15.0 / max(span, 1) * 0.72), 3))
    def tr(scale, rot):
        r = _rot(*rot)
        c = np.array([8.0, 8.0, 8.0])
        t = -(r @ (scale * (np.array(mid) - c)))
        return [round(float(v), 3) for v in t]
    gui_rot = [25, 145, 0]
    return {
        "gui": {"rotation": gui_rot, "translation": tr(s, gui_rot), "scale": [float(s)] * 3},
        "ground": {"rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [round(s * 0.55, 3)] * 3},
        "fixed": {"rotation": [0, 180, 0], "translation": tr(s * 1.1, [0, 180, 0]), "scale": [round(s * 1.1, 3)] * 3},
        "thirdperson_righthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [round(s * 0.6, 3)] * 3},
        "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 0, 0], "scale": [round(s * 0.65, 3)] * 3},
    }


def _euler_xyz(R):
    """R = Rx(a)·Ry(b)·Rz(c) 인 (a, b, c) 도."""
    b = math.asin(max(-1.0, min(1.0, R[0, 2])))
    if abs(math.cos(b)) > 1e-6:
        a = math.atan2(-R[1, 2], R[2, 2])
        c = math.atan2(-R[0, 1], R[0, 0])
    else:
        a = math.atan2(R[2, 1], R[1, 1])
        c = 0.0
    return [math.degrees(a), math.degrees(b), math.degrees(c)]


def build_bow(name, assets_root, states):
    """
    활: states = [평소, 당김1, 당김2, 당김3] 네 개의 Weapon (kind="bow").
    모델 item/<name>, item/<name>_pulling_0..2 와 당기는 정도에 따라 모델을 바꾸는 아이템 정의를 쓴다.
    손에 든 크기와 자세는 평소 모양 기준으로 네 모델 모두 같게 한다.
    """
    disp = states[0]._display()
    models = [states[0].build(name, assets_root, display=disp)]
    for i, st in enumerate(states[1:4]):
        models.append(st.build(f"{name}_pulling_{i}", assets_root, display=disp))
    item_name = name[len("item/"):] if name.startswith("item/") else name

    def ref(n):
        return {"type": "minecraft:model", "model": "augsky:" + n}

    definition = {"model": {
        "type": "minecraft:condition", "property": "minecraft:using_item",
        "on_false": ref(name),
        "on_true": {
            "type": "minecraft:range_dispatch", "property": "minecraft:use_duration", "scale": 0.05,
            "entries": [{"threshold": 0.65, "model": ref(name + "_pulling_1")},
                        {"threshold": 0.9, "model": ref(name + "_pulling_2")}],
            "fallback": ref(name + "_pulling_0"),
        },
    }}
    path = os.path.join(assets_root, "items", item_name + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(definition, f)
    # 당긴 모양의 아이템 정의는 필요 없으니 지운다
    for i in range(3):
        extra = os.path.join(assets_root, "items", f"{item_name}_pulling_{i}.json")
        if os.path.exists(extra):
            os.remove(extra)
    return models


class _Frame:
    """미리보기 렌더러가 쓰는 텍스처 한 장 (정사각형이 아니어도 된다)."""

    def __init__(self, img):
        self.img = img

    def frame0(self):
        return self.img


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


# ─────────────────────────── 미리보기 ───────────────────────────

def preview(model, size=320):
    """인벤토리처럼(대각선, 정면) + 비스듬히 + 손잡이 쪽 확대, 세 장."""
    from mc3d import render, mat
    a = render([(model, mat(roll=-45))], size=size, yaw=0, pitch=0, bg=(28, 26, 36, 255))
    b = render([(model, None)], size=size, yaw=-35, pitch=18, bg=(28, 26, 36, 255))
    c = render([(model, None)], size=size, yaw=25, pitch=-12, bg=(28, 26, 36, 255))
    return [a, b, c]


def preview_sheet(weapons, out_png, names=None, scratch=None, font="/tmp/claude-0/work/fonts/ng.ttf"):
    """
    WEAPONS 사전을 모두 지어 보고 미리보기 한 장을 만든다.
    무기마다 [인벤토리(대각선) | 비스듬히 | 반대쪽] 세 칸, 활은 [평소 | 끝까지 당김] 도 함께.
    element 수도 이름 옆에 적는다 (220 이하 권장).
    """
    from mc3d import contact_sheet
    from wkit import build_bow
    scratch = scratch or os.path.join(os.path.dirname(out_png), "_scratch", "assets", "augsky")
    imgs, labels = [], []
    for wid, fn in weapons.items():
        made = fn()
        label = (names or {}).get(wid, wid)
        if isinstance(made, (list, tuple)):
            models = build_bow("item/" + wid, scratch, list(made))
            views = preview(models[0], 300)[:2] + [preview(models[3], 300)[1]]
            n = max(len(m.elements) for m in models)
            tags = ["인벤토리", "평소", "당김"]
        else:
            aura = made.aura
            model = made.build("item/" + wid, scratch)
            views = preview(model, 300)
            n = len(model.elements)
            tags = ["인벤토리", "비스듬히", "반대쪽"]
            if aura:
                # 미리보기 렌더러는 깊이 처리가 단순해 아우라가 무기를 덮어 보이므로, 무기만 따로 한 장 더
                made.aura = None
                bare = made.build("item/" + wid + "_bare", scratch)
                made.aura = aura
                views[2] = preview(bare, 300)[1]
                tags[2] = "아우라 없이"
        for v, tg in zip(views, tags):
            imgs.append(v)
            labels.append(f"{label} · {tg} ({n})")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    contact_sheet(imgs, labels, cols=3, cell=300, font=font if os.path.exists(font) else None).save(out_png)
    return out_png



# ─────────────────────────── 보스 조각, 투구 ───────────────────────────

def part(mats, size=48, vox=1.0, seed=0):
    """
    보스 조각 (ItemDisplay 하나에 실리는 모델). 설계 원점이 회전 중심(pivot) = 모델 (8, 8, 8).
    size: 격자 한 변(복셀). 회전 중심이 격자 가운데. vox: 1 복셀의 모델 단위 (1.0 이면 rig scale 1 에서 1/16 블록).
    모델 좌표 한도(-16..32) 때문에 회전 중심에서 각 방향으로 24/vox 복셀까지만 쓸 수 있다.
    """
    half = size // 2
    return Weapon(mats, kind="part", seed=seed, grid=(size, size, size), pivot=(half, half, half), vox=vox)


_FONT = "/tmp/claude-0/work/fonts/ng.ttf"
HELMET_VOX = 1.6   # 투구 1 복셀 = 플레이어 스킨 1픽셀 (머리에 쓸 때 0.625 배로 그려지므로 1.6 모델 단위)


def helmet(mats, seed=0):
    """
    3D 투구. 설계 원점 = 머리 가운데. 1 복셀 = 스킨 1픽셀, 머리는 X,Y,Z 모두 -4..4 (8x8x8).
    얼굴(앞)은 -Z 쪽이다 (투구는 머리에 쓸 때 뒤집혀 그려진다). 머리를 덮는 껍데기는 보통 -5..5.
    가운데에서 각 방향으로 15 복셀까지 쓸 수 있다 (왕관, 뿔, 후광 등).
    """
    return Weapon(mats, kind="helmet", seed=seed, grid=(30, 30, 30), pivot=(15, 15, 15), vox=HELMET_VOX)


def helmet_preview(model, out_png=None, skin="#c8946a", size=300):
    """마네킹 머리(8x8x8 픽셀)에 씌운 모습: 앞(얼굴 쪽), 옆, 뒤 세 장."""
    from mc3d import render, contact_sheet
    head = Model("preview/head")
    at = Atlas("preview/head", size=16)
    reg = at.alloc(16, 16)
    img = Image.new("RGBA", (16, 16), hexc(skin))
    face = Image.new("RGBA", (16, 16), hexc(skin))
    for (x, y) in ((4, 7), (5, 7), (10, 7), (11, 7)):
        face.putpixel((x, y), (40, 30, 60, 255))
    reg.paste(img)
    head.use("h", at)
    r = 4 * HELMET_VOX
    head.box((8 - r, 8 - r, 8 - r), (8 + r, 8 + r, 8 + r), ("h", reg))
    views = [render([(head, None), (model, None)], size=size, yaw=y, pitch=12, bg=(28, 26, 36, 255)) for y in (180 - 25, 90 + 20, 25)]
    if out_png:
        contact_sheet(views, ["앞(얼굴)", "옆", "뒤"], cols=3, cell=size, font=_FONT if os.path.exists(_FONT) else None).save(out_png)
    return views


def rig_preview(spec, models, out_png=None, title="", size=360):
    """
    보스 조립 미리보기. spec = {"parts": [{"id", "offset", "scale", "rotation", ...}]}, models = {id: Model}.
    앞 3/4, 옆, 뒤 3/4. 1 블록 = 16 모델 단위 × scale.
    """
    from mc3d import render, mat, contact_sheet
    parts = []
    for p in spec["parts"]:
        m = models.get(p["id"])
        if m is None:
            continue
        rx, ry, rz = p.get("rotation", [0, 0, 0])
        parts.append((m, mat(translate=p.get("offset", [0, 0, 0]), scale=p.get("scale", 1.0), yaw=ry, pitch=rx, roll=rz)))
    views = [render(parts, size=size, yaw=y, pitch=p, bg=(28, 26, 36, 255)) for (y, p) in ((-35, 12), (-90, 6), (150, 12))]
    if out_png:
        contact_sheet(views, [f"{title} 앞", f"{title} 옆", f"{title} 뒤"], cols=3, cell=size, font=_FONT if os.path.exists(_FONT) else None).save(out_png)
    return views
