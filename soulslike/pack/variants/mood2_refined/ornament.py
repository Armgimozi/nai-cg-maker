"""
mood2_refined 의 붓: 4배 해상도 (GUI 픽셀당 텍셀 RES) 그림판과 장식 꼴. 모든 그림 (HUD 그림 글자, GUI 그림) 이 이것으로 그린다.

규칙
  - 텍셀마다 팔레트 색 하나 + 알파 (RGB 는 늘 팔레트 그대로, artlint palette). 겹쳐 칠하면 나중 것이 이긴다 (under=True 면 빈
    텍셀에만). 반투명과 알파 계단만 쓴다 (UI 는 허락된다).
  - 텍셀 한 칸 = GUI 배율 4 의 화면 한 픽셀. 모양은 텍셀에 딱 맞춘 또렷한 꼴로 그리고, 배율 3·2 의 부드러움은 셰이더의 박스
    필터가 맡는다. 머리카락 선 (1 텍셀) 은 GUI 픽셀의 첫 텍셀 또는 마지막 텍셀 줄에 두어 (줄 % 4 == 0 또는 3) 배율 3 에서도 한
    화면 픽셀 안에 든다 (on_grid).

장식 꼴 (한 가족: 같은 비례, 크기만 다르다)
  rule      긴 머리카락 선, 양 끝은 알파가 고르게 줄어 사라진다 (fade)
  lozenge   작은 마름모 (반 대각선 r): 테는 밝은 금빛, 속은 그을린 청동, 꼭짓점 한 점은 가장 밝게
  whisker   마름모 양옆으로 뻗는 짧은 덩굴: 1 텍셀 선이 끝으로 갈수록 옅어진다
  terminal  lozenge + 양옆 whisker (막대 마구리, 단추 끝, 실선 가운데, 창 위 가운데)
  corner    창 귀: 두 겹 선의 귀에 작은 마름모, 바깥 선은 귀에서 짧게 넘쳐 꺾쇠를 이룬다
"""
import numpy as np
from PIL import Image

import palette
import style

RES = style.RES
_NAMES = sorted(palette.C)
_IDX = {n: i for i, n in enumerate(_NAMES)}
_RGB = np.array([palette.C[n][:3] for n in _NAMES], np.uint8)

# 금빛의 자리 (팔레트 이름, 알파)
GOLD = ("bronze3", 225)          # 긴 선: 낡은 금빛 (탁하게)
GOLD_SOFT = ("bronze2", 190)     # 둘째 선, 그늘
GOLD_PALE = ("parch2", 255)      # 장식의 테
GOLD_HI = ("parch3", 255)        # 장식 꼭짓점, 고른 칸
GEM_CORE = ("bronze1", 255)      # 마름모 속


def col(c):
    return (c, 255) if isinstance(c, str) else c


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = int(w), int(h)
        self.ci = np.full((self.h, self.w), -1, np.int32)
        self.a = np.zeros((self.h, self.w), np.int32)

    # ── 기본 ──
    def put(self, x, y, c, a=None, under=False):
        x, y = int(x), int(y)
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        name, alpha = col(c)
        if a is not None:
            alpha = a
        alpha = int(max(0, min(255, round(alpha))))
        if alpha <= 0:
            return
        if under and self.a[y, x] > 0:
            return
        self.ci[y, x] = _IDX[name]
        self.a[y, x] = alpha

    def clear(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.ci[y, x] = -1
            self.a[y, x] = 0

    def rect(self, x0, y0, x1, y1, c, under=False):
        """x0..x1, y0..y1 포함."""
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.put(x, y, c, under=under)

    def hline(self, x0, x1, y, c, fade=(0, 0), under=False):
        """x0..x1 포함. fade = (왼쪽, 오른쪽) 텍셀 수: 그 끝에서 알파가 고르게 줄어 0 에 가깝게."""
        name, alpha = col(c)
        n = int(x1) - int(x0) + 1
        for i in range(n):
            k = 1.0
            if fade[0] and i < fade[0]:
                k = min(k, (i + 1) / (fade[0] + 1))
            if fade[1] and n - 1 - i < fade[1]:
                k = min(k, (n - i) / (fade[1] + 1))
            self.put(int(x0) + i, y, (name, alpha * k), under=under)

    def vline(self, x, y0, y1, c, fade=(0, 0), under=False):
        name, alpha = col(c)
        n = int(y1) - int(y0) + 1
        for i in range(n):
            k = 1.0
            if fade[0] and i < fade[0]:
                k = min(k, (i + 1) / (fade[0] + 1))
            if fade[1] and n - 1 - i < fade[1]:
                k = min(k, (n - i) / (fade[1] + 1))
            self.put(x, int(y0) + i, (name, alpha * k), under=under)

    def box(self, x0, y0, x1, y1, c):
        self.hline(x0, x1, y0, c)
        self.hline(x0, x1, y1, c)
        self.vline(x0, y0, y1, c)
        self.vline(x1, y0, y1, c)

    def blit(self, other, x0, y0, under=False):
        for y in range(other.h):
            for x in range(other.w):
                if other.a[y, x] > 0:
                    self.put(x0 + x, y0 + y, (_NAMES[other.ci[y, x]], other.a[y, x]), under=under)

    def scale_alpha(self, k):
        self.a = np.clip(np.round(self.a * k), 0, 255).astype(np.int32)

    def image(self):
        img = np.zeros((self.h, self.w, 4), np.uint8)
        m = self.a > 0
        img[m, :3] = _RGB[self.ci[m]]
        img[m, 3] = self.a[m]
        return Image.fromarray(img, "RGBA")

    # ── 장식 ──
    def lozenge(self, cx, cy, r, edge=GOLD_PALE, core=GEM_CORE, hi=GOLD_HI):
        """마름모 (반 대각선 r 텍셀, 가운데 (cx, cy)). r = 1 이면 다섯 점 십자."""
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                d = abs(x - cx) + abs(y - cy)
                if d > r:
                    continue
                if d == r:
                    self.put(x, y, edge)
                elif core:
                    self.put(x, y, core)
        if hi and r >= 2:
            self.put(cx, cy - r, hi)
            self.put(cx, cy, hi if r >= 3 else edge)

    def whisker(self, x, y, dx, n, c=GOLD_PALE, start=1.0):
        """(x, y) 에서 dx (+1 / -1) 쪽으로 n 텍셀, 알파가 start → 0 으로 줄어든다."""
        name, alpha = col(c)
        for i in range(n):
            self.put(x + dx * i, y, (name, alpha * start * (1 - i / n)))

    def terminal(self, cx, cy, r=3, arm=6, c=GOLD_PALE, both=True, side=1):
        """마름모 + 양옆 덩굴. both=False 면 side 쪽으로만."""
        if both or side < 0:
            self.whisker(cx - r - 1, cy, -1, arm, c)
        if both or side > 0:
            self.whisker(cx + r + 1, cy, 1, arm, c)
        self.lozenge(cx, cy, r)

    def rule(self, x0, x1, y, c=GOLD, fade=0, gem=None):
        """긴 머리카락 선 (양 끝 fade 텍셀에서 사라진다). gem = 가운데 마름모 반 대각선 (없으면 None)."""
        self.hline(x0, x1, y, c, fade=(fade, fade))
        if gem:
            cx = (x0 + x1) // 2
            self.terminal(cx, y, r=gem, arm=gem * 3)

    def corner(self, x, y, sx, sy, arm=10, gap=2, c=GOLD, c2=GOLD_SOFT, gem=2):
        """
        창 귀 (x, y = 바깥 선의 귀 텍셀, sx/sy = 안쪽 방향 +1/-1). 바깥 선과 gap 안쪽의 둘째 선이 귀를 이루고, 귀 바깥 대각선에
        작은 마름모, 바깥 선은 귀에서 arm 텍셀 동안 밝다 (나머지 선은 부르는 쪽이 그린다).
        """
        for i in range(arm):
            k = 1 - i / arm
            self.put(x + sx * i, y, (GOLD_PALE[0], 255 * (0.55 + 0.45 * k)))
            self.put(x, y + sy * i, (GOLD_PALE[0], 255 * (0.55 + 0.45 * k)))
        if gem:
            self.lozenge(x - sx * (gem + 1), y - sy * (gem + 1), gem)


def on_grid(row):
    """머리카락 선을 두기 좋은 텍셀 줄인가 (GUI 픽셀의 첫·마지막 텍셀)."""
    return row % RES in (0, RES - 1)


def gui_px(n):
    return int(round(n * RES))
