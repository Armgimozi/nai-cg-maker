"""
UI 그림판 (gui_skin.py 의 창·단추·단축 슬롯, hud.py 의 HUD 그림 글자): GUI 한 픽셀에 2 텍셀 (S2) 로 그린다. 색은 팔레트 이름만
(pack/palette.py, artlint 가 본다), 가장자리의 매끈함은 알파로만 낸다 (UI 그림은 반투명이 허락된다, 10.7). 두 색이 겹친 가장자리는
덮임이 큰 쪽 색을 그대로 쓴다 (사이 색을 만들지 않는다). 팩의 GUI 그림 셰이더 (shaders.py position_tex_color.fsh) 가 텍셀을 화면
픽셀이 덮는 넓이만큼 섞어 읽으므로 2 배 그림이 GUI 배율 3 에서도 고르게 보인다.

  Mask       S 배 덮임 (0..1) 을 슈퍼샘플 (SS × SS) 로 그려 텍셀 덮임으로 줄인다: 원·고리·다각형·굵은 선·네모
  Img        (H, W) 텍셀의 팔레트 이름 + 알파. over() 로 겹친다, lit() 은 위에서 비친 쇠 (윗날 밝게, 아랫날 어둡게)
"""
import math

import numpy as np
from PIL import Image

from palette import c

SS = 6          # 슈퍼샘플 (텍셀마다 SS × SS)


class Mask:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h * SS, w * SS), np.float32)
        ys, xs = np.mgrid[0:h * SS, 0:w * SS]
        self.X = (xs + 0.5) / SS
        self.Y = (ys + 0.5) / SS

    def _put(self, m, add=True):
        if add:
            np.maximum(self.a, m.astype(np.float32), out=self.a)
        else:
            self.a[m] = 0.0
        return self

    def disc(self, cx, cy, r, add=True):
        return self._put((self.X - cx) ** 2 + (self.Y - cy) ** 2 <= r * r, add)

    def ellipse(self, cx, cy, rx, ry, add=True):
        return self._put(((self.X - cx) / rx) ** 2 + ((self.Y - cy) / ry) ** 2 <= 1.0, add)

    def ring(self, cx, cy, r0, r1, a0=0.0, a1=360.0, add=True):
        """반지름 r0..r1 고리, 각 a0..a1 (도, 0 = 오른쪽, 90 = 아래, 시계 방향)."""
        d = np.sqrt((self.X - cx) ** 2 + (self.Y - cy) ** 2)
        ang = (np.degrees(np.arctan2(self.Y - cy, self.X - cx)) + 360.0) % 360.0
        a0 %= 360.0
        a1 = a0 + ((a1 - a0) % 360.0 or 360.0) if a1 != a0 + 360 else a0 + 360
        inside = ((ang - a0) % 360.0) <= (a1 - a0)
        return self._put((d >= r0) & (d <= r1) & inside, add)

    def poly(self, pts, add=True):
        x, y = self.X, self.Y
        inside = np.zeros_like(x, dtype=bool)
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            cond = ((y0 > y) != (y1 > y))
            xi = (x1 - x0) * (y - y0) / ((y1 - y0) if y1 != y0 else 1e-9) + x0
            inside ^= cond & (x < xi)
        return self._put(inside, add)

    def line(self, x0, y0, x1, y1, wdt, add=True, cap=True):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy or 1e-9
        t = ((self.X - x0) * dx + (self.Y - y0) * dy) / L2
        if cap:
            t = np.clip(t, 0, 1)
        px, py = x0 + t * dx, y0 + t * dy
        d = np.sqrt((self.X - px) ** 2 + (self.Y - py) ** 2)
        m = d <= wdt / 2.0
        if not cap:
            m &= (t >= 0) & (t <= 1)
        return self._put(m, add)

    def rect(self, x0, y0, x1, y1, add=True):
        """[x0, x1) × [y0, y1) 텍셀."""
        return self._put((self.X >= x0) & (self.X < x1) & (self.Y >= y0) & (self.Y < y1), add)

    def cov(self):
        return self.a.reshape(self.h, SS, self.w, SS).mean(axis=(1, 3))


class Img:
    """팔레트 이름 (문자열 배열) 과 알파 (0..1)."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.name = np.full((h, w), "", dtype=object)
        self.alpha = np.zeros((h, w), np.float32)

    def fill(self, cov, name, alpha=1.0):
        """덮임 cov 배열 (또는 상수) 만큼 한 색으로."""
        if np.isscalar(cov):
            cov = np.full((self.h, self.w), cov, np.float32)
        a = np.clip(cov * alpha, 0, 1)
        self.over_layer(np.full((self.h, self.w), name, dtype=object), a)
        return self

    def over_layer(self, names, a):
        top = a
        bot = self.alpha
        out_a = top + bot * (1 - top)
        take = (top >= 0.5) | (bot <= 0.0) | (self.name == "")
        self.name = np.where(take & (top > 0), names, self.name)
        self.alpha = out_a
        return self

    def over(self, other, x0=0, y0=0):
        """other (Img) 를 (x0, y0) 에 겹친다."""
        h, w = other.h, other.w
        sub = Img(w, h)
        sub.name = self.name[y0:y0 + h, x0:x0 + w].copy()
        sub.alpha = self.alpha[y0:y0 + h, x0:x0 + w].copy()
        sub.over_layer(other.name, other.alpha)
        self.name[y0:y0 + h, x0:x0 + w] = sub.name
        self.alpha[y0:y0 + h, x0:x0 + w] = sub.alpha
        return self

    def put(self, x, y, name, alpha=1.0):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.name[y, x] = name
            self.alpha[y, x] = alpha

    def hline(self, x0, x1, y, name, alpha=1.0):
        for x in range(x0, x1):
            self.put(x, y, name, alpha)

    def vline(self, x, y0, y1, name, alpha=1.0):
        for y in range(y0, y1):
            self.put(x, y, name, alpha)

    def image(self, min_alpha=1.0 / 255):
        img = np.zeros((self.h, self.w, 4), np.uint8)
        for y in range(self.h):
            for x in range(self.w):
                a = self.alpha[y, x]
                n = self.name[y, x]
                if a < min_alpha or not n:
                    continue
                r, g, b, _ = c(n)
                img[y, x] = (r, g, b, int(round(min(1.0, a) * 255)))
        # 발광 알파 (250~252) 는 빛 허용 그림만 쓴다: 249 로
        al = img[..., 3]
        al[(al >= 250) & (al <= 252)] = 249
        return Image.fromarray(img, "RGBA")


def lit(cov, ramp, light_rows=1, dark_rows=1):
    """
    위에서 비친 쇠: 덮임 cov 의 각 텍셀 색을 ramp (어둠 → 밝음 팔레트 이름 목록) 에서 고른다. 위쪽 이웃이 비었으면 (윗날)
    가장 밝은 색, 그 아래 light_rows 줄은 한 단 밝게, 아래쪽 이웃이 비었으면 (아랫날) 가장 어두운 색, 나머지는 가운데.
    돌려주는 값: Img.
    """
    h, w = cov.shape
    on = cov > 0.02
    up = np.zeros_like(on)
    up[1:] = on[:-1]
    down = np.zeros_like(on)
    down[:-1] = on[1:]
    # 위쪽으로 몇 텍셀 안에 빈 곳이 있는가
    top_d = np.full((h, w), 99, np.int32)
    run = np.zeros(w, np.int32)
    for y in range(h):
        run = np.where(on[y], run + 1, 0)
        top_d[y] = run
    bot_d = np.full((h, w), 99, np.int32)
    run = np.zeros(w, np.int32)
    for y in range(h - 1, -1, -1):
        run = np.where(on[y], run + 1, 0)
        bot_d[y] = run
    out = Img(w, h)
    n = len(ramp)
    mid = ramp[max(0, n // 2 - 1)]
    names = np.full((h, w), mid, dtype=object)
    names[(top_d == 1)] = ramp[-1]
    for k in range(1, light_rows + 1):
        names[(top_d == 1 + k) & (bot_d > dark_rows)] = ramp[max(0, n - 1 - k)]
    names[(bot_d <= dark_rows) & (top_d > 1)] = ramp[0]
    out.over_layer(names, np.clip(cov, 0, 1))
    return out


def save(img, path):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path
