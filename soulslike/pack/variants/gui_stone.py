"""
변형 "돌" (stone): 축축한 지하 묘실의 돌로 다시 그린 HUD·GUI. gui_skin.py 를 바탕으로 하고, 칸 자리 (CONTAINER_LAYOUTS,
well, 미리보기·칸 자리 증명) 는 그대로 쓴다. 바꾼 것은 겉모습뿐이다.

말씨 (2026-10-07 사용자: "세련된다는게 그런 뜻이 아니었는데 뭔가 거무칙칙한 느낌을 원했던 것 같기도")
  깨끗한 쇠판과 가는 청동 대신, 오래 젖어 있던 묘실 벽. 쇠와 청동은 하나도 없다 (반짝이는 것이 없다).
  때와 물때는 흩뿌리지 않는다. 모든 자국에는 까닭이 있다:
    - 테는 돌을 쌓은 것이다. 돌마다 위·왼쪽 모서리에 빛 (ash2), 아래·오른쪽에 그늘 (moss0), 사이는 검은 줄눈 (ash0).
      돌의 길이는 창마다 손으로 정했고 (줄눈 자리 MASONRY), 이 빠진 귀는 돌의 모서리에만 난다.
      바깥 윤곽도 몇 군데 떨어져 나갔다 (notches).
    - 물은 위에서 스민다: 위 테의 줄눈 몇 곳에서 판으로 물때가 흘러내리고 (seeps), 옆 테에서는 줄눈 바로 아래 돌에
      젖은 줄이 진다. 아래쪽은 습기가 올라와 돌이 한 단 어둡다 (rising damp). 아래 테의 가운데는 손이 닿아 마른 채다.
    - 때는 고인다: 판의 귀, 턱 (나눔 돌) 위의 양 끝, 벽감 바닥.
  층마다 얼굴이 다르다 (테 > 판 > 칸):
    테     윤곽 + 4픽셀 돌 쌓기 + 판과의 줄눈 (ash0) 한 줄
    판     젖은 바닥돌 (moss0). 넓고 조용하다. 자국은 위의 까닭이 있는 곳에만
    칸     판에 판 홈: 위·왼쪽 그늘 (ash0), 아래·오른쪽 입술 (ash1), 바닥은 판과 같은 moss0 (석탄·부싯돌이 묻히지 않는다)
    인물   벽감: 반원 아치 (쐐기돌 고리와 이맛돌) 아래 가장 깊은 어둠, 발밑에 받침돌
    나눔   민 홈 대신 벽에 박힌 돌 턱 (위 빛, 앞면, 아래 그림자). 턱 위 양 끝에 때가 고였다
    결과   다듬은 돌 테를 두른 칸. 화살표는 판에 새겼다
  색은 재 (ash), 이끼 (moss), 녹슨 철의 가장 어두운 색 (rust0, 진흙·때) 이 거의 다다. 핏방울 체력, 이끼 스태미나,
  그리고 아이템만 색이 있다. 화면에서 가장 밝은 것은 아이템이다.

  python3 pack/variants/gui_stone.py [팩폴더] [미리보기폴더]
"""
import json
import os
import sys
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.dirname(HERE)
for _p in (PACK_DIR, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from palette import c  # noqa: E402

GUI = ("assets", "minecraft", "textures", "gui")


# ─────────────────────────── 그림판 ───────────────────────────

class Cv:
    """팔레트 이름으로만 칠하는 그림판. None 은 투명."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.names = [[None] * w for _ in range(h)]

    def put(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.names[y][x] = col

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.names[y][x]
        return None

    def hline(self, x0, x1, y, col):
        for x in range(x0, x1 + 1):
            self.put(x, y, col)

    def vline(self, x, y0, y1, col):
        for y in range(y0, y1 + 1):
            self.put(x, y, col)

    def rect(self, x0, y0, x1, y1, col):
        for y in range(y0, y1 + 1):
            self.hline(x0, x1, y, col)

    def stamp(self, x0, y0, rows, ink, flip_x=False, flip_y=False):
        """기호 그림을 찍는다. 빈칸은 그대로 두고, '.' 은 투명. flip 으로 뒤집어 찍는다."""
        if flip_y:
            rows = rows[::-1]
        for dy, row in enumerate(rows):
            if flip_x:
                row = row[::-1]
            for dx, ch in enumerate(row):
                if ch == " ":
                    continue
                self.put(x0 + dx, y0 + dy, None if ch == "." else ink[ch])

    def image(self):
        img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        px = img.load()
        for y in range(self.h):
            for x in range(self.w):
                n = self.names[y][x]
                if n:
                    px[x, y] = c(n)
        return img


def save(img, out, *parts):
    path = os.path.join(out, *GUI, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def save_mcmeta(out, scaling, *parts):
    path = os.path.join(out, *GUI, *parts) + ".mcmeta"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"gui": {"scaling": scaling}}, f, indent=2)
        f.write("\n")


# ─────────────────────────── 말씨: 색의 자리 ───────────────────────────

OUTLINE = "ash0"      # 바깥 윤곽
JOINT = "ash0"        # 돌 사이 줄눈, 판과 테 사이 줄눈
STONE_LIT = "ash1"    # 돌의 위·왼쪽 모서리 (빛을 받는다). 테에서 가장 밝은 색이 겨우 ash1 이다
STONE = "moss0"       # 돌 얼굴: 이끼 낀 잿빛 초록
STONE_DIM = "rust0"   # 돌의 아래·오른쪽 모서리, 젖은 얼굴
CHALK = "ash2"        # 고른 칸 테·가리킨 칸의 꺾쇠 (돌 가운데 가장 밝다)
STONE_TONES = (STONE_DIM, STONE, STONE_LIT)   # 젖으면 한 단 내려간다
PANEL = "rust0"       # 판: 그을고 젖은 바닥돌 (거의 검은 흙빛)
FLOOR = "rust0"       # 칸 바닥 = 판. 칸은 색이 아니라 베벨로 패인다
SHADOW = "ash0"       # 칸의 위·왼쪽 (그늘)
LIP = "moss0"         # 칸의 아래·오른쪽 입술: 홈에 낀 이끼빛. 칸 사이 홈은 이끼 한 줄 + 검은 줄
DEEP = "ash0"         # 벽감 속
SOOT = "ash0"         # 검은 때, 물때의 가운데
MUD = "moss0"         # 물때의 젖은 가장자리 (이끼가 번진다)
MOSS = "moss1"        # 살아 있는 이끼: 물이 나오는 줄눈 입, 젖은 귀, 습기 선에만
GROOVE = "ash0"

# 테 돌의 두께. 위 (상인방) 는 4: 바닐라 제목 글이 y 6 부터라 그 위까지만. 옆 기둥과 아래는 6: 칸 (x 7, 아래 입술은
# 끝에서 7번째 줄) 바로 앞까지 돌이 온다. 돌 안쪽은 줄눈 한 줄 (위 y 5, 옆 x 7 / 끝에서 8번째, 아래 끝에서 7번째) 이고
# 칸이 있는 곳에서는 그 줄이 곧 칸의 그늘 줄·입술 줄이다. 칸의 그늘 줄 바로 바깥 (x 6) 은 돌의 안쪽 모서리라
# 검은 줄눈·이 빠진 자리도 그 열에서는 진흙빛 (rust0) 으로 멈춘다 (칸의 어두운 줄이 꼭 1픽셀).
T = 4
TS = 6
TB = 6


class Lcg:
    """창마다 같은 씨앗이면 같은 결과 (이 빠진 귀, 젖은 줄의 자리). 무작위 자국을 흩뿌리는 데는 쓰지 않는다."""

    def __init__(self, seed):
        self.s = seed

    def __call__(self, n):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s >> 9) % n


def ring_of(x, y, w, h, cut=(2, 2, 2, 2)):
    """w×h 판의 가장자리에서 몇 번째 고리인지. 네 귀 (왼쪽 위, 오른쪽 위, 왼쪽 아래, 오른쪽 아래) 는 cut 만큼 깎였다."""
    W, H = w - 1, h - 1
    a, b, cc, d = cut
    return min(y, x, H - y, W - x, x + y - a, W - x + y - b, x + H - y - cc, W - x + H - y - d)


# ─────────────────────────── 돌 쌓기 ───────────────────────────

def course_rects(w, h, M):
    """
    테의 돌들 (x0, y0, x1, y1). 위·아래 줄은 가로로, 옆 기둥은 세로로 쌓는다. M["own"] 은 네 귀 (왼쪽 위, 오른쪽 위,
    왼쪽 아래, 오른쪽 아래) 를 어느 줄의 돌이 차지하는지 ('h' 위·아래 줄, 'v' 옆 기둥). 줄눈은 돌이 없는 자리다.
    """
    W, H = w - 1, h - 1
    own = M["own"]
    rects = []

    def course(a, b, joints, horiz, lo, hi):
        s = a
        for j in sorted(j for j in joints if a < j < b) + [b + 1]:
            if j - 1 >= s:
                rects.append((s, lo, j - 1, hi) if horiz else (lo, s, hi, j - 1))
            s = j + 1

    course(1 if own[0] == "h" else TS + 2, W - 1 if own[1] == "h" else W - TS - 2, M["top"], True, 1, T)
    course(1 if own[2] == "h" else TS + 2, W - 1 if own[3] == "h" else W - TS - 2, M["bottom"], True, H - TB, H - 1)
    course(T + 2 if own[0] == "h" else 1, H - TB - 2 if own[2] == "h" else H - 1, M["left"], False, 1, TS)
    course(T + 2 if own[1] == "h" else 1, H - TB - 2 if own[3] == "h" else H - 1, M["right"], False, W - TS, W - 1)
    return rects


# 돌빛의 사다리 (어두움 → 밝음). 보통 돌은 (그늘, 얼굴, 빛) = (rust0, moss0, ash1), 젖은 돌은 한 단 아래,
# 마른 돌은 한 단 위. 습기가 오른 곳은 또 한 단 아래.
TONE_CHAIN = ("ash0", "rust0", "moss0", "ash1", "ash2")


def tone_step(col, k):
    """사다리에서 k 단 옮긴 색 (사다리에 없는 색은 그대로)."""
    if col not in TONE_CHAIN:
        return col
    return TONE_CHAIN[max(0, min(len(TONE_CHAIN) - 1, TONE_CHAIN.index(col) + k))]


def shade_stones(cv, owner, damp=None, bias=None):
    """
    owner {(x, y): 돌 번호} 의 돌마다 1픽셀 베벨: 위·왼쪽이 다른 돌이면 빛, 아래·오른쪽이면 그늘,
    두 꺾임 (오른쪽 위, 왼쪽 아래) 은 얼굴. bias {돌 번호: -1 젖은 돌, +1 마른 돌} 로 돌마다 한 단씩 다르고,
    damp(x, y) 가 참인 곳은 습기가 올라 한 단 어둡다.
    """
    for (x, y), b in owner.items():
        up, lf = owner.get((x, y - 1)) == b, owner.get((x - 1, y)) == b
        dn, rt = owner.get((x, y + 1)) == b, owner.get((x + 1, y)) == b
        lit, dim = not up or not lf, not dn or not rt
        if lit and dim:
            tone = 2 if (not up and not lf) else (0 if (not dn and not rt) else 1)
        else:
            tone = 2 if lit else (0 if dim else 1)
        level = tone + 1 + (bias.get(b, 0) if bias else 0) - (1 if damp and damp(x, y) else 0)
        cv.put(x, y, TONE_CHAIN[max(0, min(len(TONE_CHAIN) - 1, level))])


def chip_stones(cv, rects, owner, rnd):
    """
    돌의 귀가 이 빠진다 (돌마다 0~2곳, 귀나 위 모서리). 떨어져 나간 자리는 줄눈처럼 검고, 그 안쪽 한 점은 새로 드러난
    면이라 빛을 받는다. 무늬가 아니라 돌의 모서리에만 난다.
    """
    for i, (x0, y0, x1, y1) in enumerate(rects):
        n = (0, 1, 1, 2)[rnd(4)]
        for _ in range(n):
            kind = rnd(6)
            long_x = x1 - x0 >= y1 - y0
            if kind < 4:      # 귀
                cx, sx = (x0, 1) if kind in (0, 2) else (x1, -1)
                cy, sy = (y0, 1) if kind in (0, 1) else (y1, -1)
                pts = [(cx, cy)] + ([(cx + sx, cy)] if long_x and rnd(2) else [(cx, cy + sy)] if rnd(2) else [])
                inner = (cx + sx, cy + sy)
            else:             # 긴 모서리의 작은 흠
                if long_x and x1 - x0 > 8:
                    px = x0 + 3 + rnd(x1 - x0 - 6)
                    py = y0 if kind == 4 else y1
                    pts = [(px, py)] + ([(px + 1, py)] if rnd(2) else [])
                    inner = (px, py + (1 if py == y0 else -1))
                elif not long_x and y1 - y0 > 8:
                    py = y0 + 3 + rnd(y1 - y0 - 6)
                    px = x0 if kind == 4 else x1
                    pts = [(px, py)] + ([(px, py + 1)] if rnd(2) else [])
                    inner = (px + (1 if px == x0 else -1), py)
                else:
                    continue
            for p in pts:
                if owner.get(p) == i:
                    cv.put(*p, JOINT)
            if owner.get(inner) == i and cv.get(*inner) not in (JOINT, MOSS):
                cv.put(*inner, tone_step(cv.get(*inner), 1))


def wet_streaks(cv, rects, owner, rnd, M, h):
    """
    옆 테: 가로 줄눈마다 그 아래 돌에 물이 스며 젖은 줄이 진다 (줄눈 바로 아래에서 시작해 2~5픽셀).
    위 테: M["seeps"] 의 줄눈 아래 돌에도 짧게. 젖은 줄은 돌 얼굴보다 한 단 어둡고, 빛 모서리를 끊는다.
    """
    for i, (x0, y0, x1, y1) in enumerate(rects):
        side = x1 - x0 < y1 - y0           # 옆 테의 돌 (세로로 길다)
        if not side or y0 <= T + 2:
            continue
        if rnd(5) == 0:
            continue
        sx = x0 + 1 + rnd(TS - 2)
        n = 2 + rnd(4)
        for k in range(n):
            if owner.get((sx, y0 + k)) == i:
                cv.put(sx, y0 + k, SOOT if k == 0 else tone_step(cv.get(sx, y0 + k), -2))
        if rnd(3) == 0 and owner.get((sx + 1, y0)) == i:
            cv.put(sx + 1, y0, tone_step(cv.get(sx + 1, y0), -2))
    for sx, _n in M.get("seeps", ()):
        # 위 테 줄눈의 양옆 돌 아래 모서리가 젖었다 (물이 줄눈을 타고 내려와 판으로 흐른다)
        for x in (sx - 1, sx + 1):
            if owner.get((x, T)) is not None:
                cv.put(x, T, SOOT)


def notch(cv, x, y, n, side):
    """바깥 윤곽이 떨어져 나간 자리: 윤곽 n 픽셀이 투명해지고 한 칸 안쪽이 윤곽이 된다."""
    dx, dy, ix, iy = {"top": (1, 0, 0, 1), "bottom": (1, 0, 0, -1), "left": (0, 1, 1, 0), "right": (0, 1, -1, 0)}[side]
    for k in range(n):
        px, py = x + dx * k, y + dy * k
        cv.put(px, py, None)
        cv.put(px + ix, py + iy, OUTLINE)


def masonry(cv, w, h, M):
    """창의 테: 윤곽, 돌 쌓기, 이 빠진 귀, 젖은 줄, 아래의 습기, 판과의 줄눈."""
    cut = M["cut"]
    rects = course_rects(w, h, M)
    H = h - 1
    W = w - 1
    owner = {}
    for i, (x0, y0, x1, y1) in enumerate(rects):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if ring_of(x, y, w, h, cut) >= 1:
                    owner[(x, y)] = i
    rise_l, rise_r = M.get("rise", (20, 14))
    dry0, dry1 = M.get("dry", (w // 3, 2 * w // 3))
    # 습기가 올라온 높이: 옆 테는 아래에서 rise 만큼 (열마다 한두 픽셀 계단), 아래 테는 가운데 (손 닿는 곳) 만 마른다
    steps = (0, 1, 1, 3, 2, 0)

    def damp(x, y):
        if y >= H - TB:                                 # 아래 테
            if dry0 <= x <= dry1:
                return False
            edge = min(abs(x - dry0), abs(x - dry1))
            return y >= H - 3 - (1 if edge > 6 else 0)
        if x <= TS:
            return y >= H - rise_l + steps[x % 6]
        if x >= W - TS:
            return y >= H - rise_r + steps[(W - x) % 6]
        return False

    for y in range(h):
        for x in range(w):
            k = ring_of(x, y, w, h, cut)
            if k < 0:
                continue
            frame_zone = y <= T + 1 or x <= TS + 1 or W - x <= TS + 1 or H - y <= TB + 1
            if k == 0:
                cv.put(x, y, OUTLINE)
            elif frame_zone:
                if (x, y) not in owner:
                    cv.put(x, y, JOINT)
            else:
                cv.put(x, y, PANEL)
    # 돌마다 한 단씩 다르다: 위쪽 돌은 마른 것이 많고, 아래로 갈수록 젖은 돌이 많다 (물은 아래로 모인다)
    brnd = Lcg(M["seed"] * 7 + 3)
    bias = {}
    for i, (x0, y0, x1, y1) in enumerate(rects):
        t = (y0 + y1) / 2 / h
        r = brnd(100)
        dry, wet = (22, 94) if t < 0.3 else (10, 80) if t < 0.7 else (3, 55)
        bias[i] = 1 if r < dry else -1 if r >= wet else 0
    shade_stones(cv, owner, damp, bias)
    # 습기 선: 옆 테에서 젖은 곳과 마른 곳의 경계에 이끼가 한 줄 자랐다 (열마다 계단)
    for x in range(1, TS + 1):
        for xx, rise in ((x, rise_l + 1 - steps[x % 6]), (W - x, rise_r + 1 - steps[(W - (W - x)) % 6])):
            p = (xx, H - rise)
            if p in owner and owner.get((xx, H - rise - 1)) == owner[p]:
                cv.put(*p, MOSS)
    rnd = Lcg(M["seed"])
    chip_stones(cv, rects, owner, rnd)
    wet_streaks(cv, rects, owner, rnd, M, h)
    for x, y, n, side in M.get("notches", ()):
        notch(cv, x, y, n, side)
    # 칸의 그늘 줄 바로 바깥 (왼쪽 기둥의 안쪽 모서리) 은 검지 않다: 줄눈·흠이 여기서 진흙빛으로 멈춘다
    for y in range(T + 2, H - TB):
        if cv.get(TS, y) == JOINT:
            cv.put(TS, y, "rust0")
    return rects


# ─────────────────────────── 판 위의 물때와 때 ───────────────────────────

# 위 테 줄눈에서 판으로 스며 흘러내린 물때. 줄눈 바로 아래 (판과의 줄눈 다음 줄) 에서 시작한다.
# M 물이 나오는 입에 낀 이끼 (moss1), K 검은 물때 (ash0), m 젖은 가장자리 (moss0). 가운데 열이 줄눈의 x 다.
# 입에서 넓게 배었다가 가늘어지고, 몇 번 끊기며 흘러 끝에 방울이 맺힌다.
SEEP = {
    # 물이 줄눈을 타고 길게 흘렀다: 입에서 넓게 배고 (가장자리에 이끼), 두 줄 굵기로 내려오다 가늘어지고,
    # 몇 번 끊긴 뒤 방울. 이끼 (M) 는 물이 늘 닿는 위쪽 가장자리에만, 아래쪽은 젖은 자국 (m) 뿐이다.
    "long": [
        "MMMKMMm",
        "MKKKKKM",
        ".MKKKKM",
        ".mKKKM.",
        "..KKKM.",
        "..MKKm.",
        "..mKK..",
        "...KKM.",
        "..mKKm.",
        "...KK..",
        "...KKm.",
        "...KK..",
        "..mKK..",
        "...KK..",
        "...KKm.",
        "...Km..",
        "...KK..",
        "...K...",
        "...Km..",
        "...K...",
        "...K...",
        "...K...",
        "...m...",
        "...K...",
        "...K...",
        "...K...",
        "...m...",
        ".......",
        "...m...",
        "...K...",
    ],
    "mid": [
        "MMKMm",
        "MKKKM",
        ".KKKM",
        ".mKK.",
        "..KKm",
        "..KK.",
        "..Km.",
        "..K..",
        "..K..",
        "..K..",
        "..m..",
        ".....",
        "..m..",
        "..K..",
    ],
    "short": [
        "MMKMm",
        "mKKKM",
        ".KKm.",
        ".mK..",
        "..K..",
        "..K..",
        "..m..",
    ],
    # 판의 줄눈 (상자의 두 돌판 사이) 에서 배어 나온 넓은 얼룩
    "wide": [
        "MKKKKM.",
        ".mKKKm.",
        "..KKm..",
        "..mK...",
        "..K....",
        "..K....",
        "..m....",
    ],
    # 칸 (물이 고이는 홈) 아래로 넘쳐 흐른 짧은 물때
    "drip": [
        "mKm",
        ".K.",
        ".K.",
        ".m.",
    ],
    # 흘러내린 물이 가로 줄눈 위에 고여 번진 자리
    "pool": [
        "..mKKm..",
        "MKKKKKKm",
    ],
}
# 판의 귀에 다져진 때와 이끼 (왼쪽 위 귀 기준, 뒤집어 다른 귀에). K 검은 때, M 이끼, m 젖은 가장자리
GRIME = {
    "corner": [
        "KKKKKm",
        "KKMMm.",
        "KMm...",
        "KKm...",
        "Km....",
        "m.....",
    ],
    "small": [
        "KKKm",
        "KMm.",
        "Km..",
        "m...",
    ],
}
STAIN_INK = {"K": SOOT, "m": MUD, "M": MOSS}


def field_joints(cv, joints):
    """
    판도 큰 돌을 쌓은 벽이다: 열린 판 (칸이 없는 곳) 에만 줄눈을 긋는다. ("v", x, y0, y1) 세로, ("h", y, x0, x1) 가로.
    줄눈은 검고, 그 오른쪽·아래 한 줄이 다음 돌의 빛 받는 모서리 (moss0). 칸의 그늘 줄 바로 바깥에는 긋지 않는다.
    """
    for kind, a, b0, b1 in joints:
        for t in range(b0, b1 + 1):
            x, y = (a, t) if kind == "v" else (t, a)
            cv.put(x, y, JOINT)
            lx, ly = (x + 1, y) if kind == "v" else (x, y + 1)
            if cv.get(lx, ly) == PANEL:
                cv.put(lx, ly, STONE)


def seep(cv, x, y, kind, cut=None):
    rows = SEEP[kind][:cut] if cut else SEEP[kind]
    half = len(rows[0]) // 2
    cv.stamp(x - half, y, [r.replace(".", " ") for r in rows], STAIN_INK)


def grime(cv, x, y, corner, kind="corner"):
    """corner: 'tl', 'tr', 'bl', 'br'. (x, y) 는 그 귀의 픽셀."""
    rows = [r.replace(".", " ") for r in GRIME[kind]]
    n = len(rows)
    fx, fy = corner[1] == "r", corner[0] == "b"
    cv.stamp(x - (n - 1 if fx else 0), y - (n - 1 if fy else 0), rows, STAIN_INK, flip_x=fx, flip_y=fy)


# ─────────────────────────── 칸 ───────────────────────────

def well(cv, x, y, w=18, h=18, floor=None, shadow=None, lip=None, corner=None):
    """
    패인 칸 (바닐라 칸과 같은 자리·같은 역할, gui_skin.well 과 같다). w×h 상자의 (x, y) 에서:
      위 줄 x..x+w-2 와 왼쪽 줄 y..y+h-2 는 그늘 (shadow), 아래 줄 x+1..x+w-1 과 오른쪽 줄 y+1..y+h-1 은 입술 (lip),
      가운데는 바닥 (floor). 18×18 칸이면 꼭 아이템 자리 16×16. 두 꺾임 (오른쪽 위, 왼쪽 아래) 은 corner.
    """
    floor, shadow, lip = floor or FLOOR, shadow or SHADOW, lip or LIP
    corner = corner or PANEL
    cv.rect(x + 1, y + 1, x + w - 2, y + h - 2, floor)
    cv.hline(x, x + w - 2, y, shadow)
    cv.vline(x, y, y + h - 2, shadow)
    cv.hline(x + 1, x + w - 1, y + h - 1, lip)
    cv.vline(x + w - 1, y + 1, y + h - 1, lip)
    cv.put(x + w - 1, y, corner)
    cv.put(x, y + h - 1, corner)


def ledge(cv, x0, x1, y, w, rnd, joints=()):
    """
    나눔줄 자리에 벽에 박힌 돌 턱 (네 줄, y-1 .. y+2):
      y-1  윗돌판과 턱 사이 줄눈 (검다)
      y    턱의 윗면 (빛). 양 끝 (벽에 닿는 귀) 에 때와 이끼가 고였다
      y+1  턱의 앞면
      y+2  판 (턱의 그림자는 바로 아래 칸의 그늘 줄이 맡는다. 이 줄이 검으면 그늘 줄이 2픽셀로 번진다)
    턱은 판과의 줄눈 (고리 5) 까지 닿아 벽에 박혔다. joints 의 x 에서 턱 돌이 나뉜다.
    """
    a, b = TS + 1, w - TS - 2
    cv.hline(a, b, y - 1, JOINT)
    owner = {}
    cuts = sorted(joints) + [b + 1]
    s, idx = a + 1, 0
    for j in cuts:
        for xx in range(s, j):
            owner[(xx, y)] = idx
            owner[(xx, y + 1)] = idx
        s, idx = j + 1, idx + 1
    for j in joints:
        cv.put(j, y, JOINT)
        cv.put(j, y + 1, JOINT)
    shade_stones(cv, owner)
    # 2줄짜리 돌이라 아랫줄이 그늘 (moss0) 이 되면 판에 묻힌다: 앞면은 얼굴, 오른쪽 끝만 그늘
    for (xx, yy), i in owner.items():
        if yy == y + 1 and cv.get(xx, yy) == STONE_DIM and owner.get((xx + 1, yy)) == i:
            cv.put(xx, yy, STONE)
    cv.put(a, y, JOINT)
    cv.put(a, y + 1, JOINT)
    # 턱 위 양 끝에 고인 때와 이끼 (벽에 닿는 귀가 가장 두껍다). 왼쪽 끝은 그늘이라 이끼가 더 자랐다
    for xx, col in ((a + 1, SOOT), (a + 2, MOSS), (a + 3, MOSS), (a + 4, MUD), (a + 6, MUD)):
        cv.put(xx, y, col)
    for xx, col in ((b, SOOT), (b - 1, SOOT), (b - 2, MUD), (b - 4, MUD)):
        cv.put(xx, y, col)
    cv.put(a + 1, y + 1, SOOT)


def carved_arrow(cv, x0, x1, ym, half):
    """제작 화살표 (바닐라 자리): 판에 새겼다. 새긴 홈 속은 검고, 아래·오른쪽 벽만 빛을 받는다 (ash1)."""
    cells = set()
    head = x1 - half
    for x in range(x0, head):
        cells.update({(x, ym - 1), (x, ym), (x, ym + 1)})
    for x in range(head, x1 + 1):
        k = x1 - x
        cells.update((x, y) for y in range(ym - k, ym + k + 1))
    for x, y in cells:
        top_left = (x, y - 1) not in cells or (x - 1, y) not in cells
        bottom_right = (x, y + 1) not in cells or (x + 1, y) not in cells
        cv.put(x, y, STONE_LIT if bottom_right and not top_left else SOOT)


# ─────────────────────────── 체력: 마른 핏방울 열 개 (gui_skin 과 같다) ───────────────────────────

HEART_INK = {"K": "ash0", "r": "rust1", "g": "rust0", "a": "ash1", "L": "rust3", "B": "parch0"}
HEART_CONTAINER = [
    "....K....",
    "...KgK...",
    "..rgggK..",
    "..rgggK..",
    ".KggaggK.",
    ".Kgggg...",
    ".KgggggK.",
    "..KgggK..",
    "...KKK...",
]
HEART_CONTAINER_BLINK = [
    "....B....",
    "...BgK...",
    "..LgggK..",
    "..LgggK..",
    ".BggaggK.",
    ".Bgggg...",
    ".KgggggK.",
    "..KgggK..",
    "...KKK...",
]
HEART_FULL = [
    "....2....",
    "...322...",
    "...321...",
    "..23221..",
    "..22220..",
    "..22210..",
    "...110...",
]
HEART_HALF = [
    ".........",
    ".........",
    ".........",
    ".........",
    "..32221..",
    "..22210..",
    "...110...",
]
HEART_TONES = {
    "":          ("blood0", "blood1", "blood2", "blood3"),
    "blinking":  ("parch0", "parch0", "parch1", "parch2"),
    "poisoned":  ("moss0", "moss1", "moss2", "moss2"),
    "withered":  ("ash0", "ash1", "ash2", "ash3"),
    "frozen":    ("ash2", "ash3", "bone0", "bone2"),
    "absorbing": ("rust1", "rust2", "parch0", "parch1"),     # 쇠·청동이 없는 말씨라 흡수는 바랜 흙빛
    "vehicle":   ("rust0", "rust1", "rust2", "rust3"),
}
HEART_TYPES = ("", "poisoned", "withered", "frozen", "absorbing")


def heart_container(blink=False):
    cv = Cv(9, 9)
    cv.stamp(0, 0, HEART_CONTAINER_BLINK if blink else HEART_CONTAINER, HEART_INK)
    return cv.image()


def heart_fill(tones, half=False):
    cv = Cv(9, 9)
    rows = HEART_HALF if half else HEART_FULL
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch != ".":
                cv.put(dx, 1 + dy, tones[int(ch)])
    return cv.image()


def hearts(out):
    d = ("sprites", "hud", "heart")
    c0, cb = heart_container(), heart_container(True)
    for suffix in ("", "_hardcore"):
        save(c0, out, *d, f"container{suffix}.png")
        save(cb, out, *d, f"container{suffix}_blinking.png")
    save(c0, out, *d, "vehicle_container.png")
    for t in HEART_TYPES:
        pre = t + "_" if t else ""
        for half in (False, True):
            part = "half" if half else "full"
            normal = heart_fill(HEART_TONES[t], half)
            blink = heart_fill(HEART_TONES["blinking"], half)
            for hc in ("", "hardcore_"):
                save(normal, out, *d, f"{pre}{hc}{part}.png")
                save(blink, out, *d, f"{pre}{hc}{part}_blinking.png")
    for half in (False, True):
        save(heart_fill(HEART_TONES["vehicle"], half), out, *d, "vehicle_" + ("half" if half else "full") + ".png")
    return [os.path.join(out, *GUI, *d, f) for f in sorted(os.listdir(os.path.join(out, *GUI, *d)))]


# ─────────────────────────── 스태미나 (경험치 막대 자리) ───────────────────────────

BAR_W, BAR_H = 182, 5


def stamina_bar():
    """
    배경: 돌에 판 가는 도랑. 위 테·왼쪽 끝은 빛 받는 돌 (ash1), 아래 테·오른쪽 끝은 젖은 그늘 (moss0), 도랑 바닥 ash0.
          위 테가 두 곳 이 빠졌다 (돌 테와 같은 까닭).
    채움: 도랑에 낀 이끼 세 줄 — 위 moss2, 가운데 moss1, 아래 moss0. 바닐라가 진행만큼 왼쪽부터 잘라 그린다.
    """
    W = BAR_W
    bg = Cv(W, BAR_H)
    bg.hline(1, W - 2, 0, "ash1")
    bg.hline(1, W - 2, BAR_H - 1, "moss0")
    bg.vline(0, 1, BAR_H - 2, "ash1")
    bg.vline(W - 1, 1, BAR_H - 2, "moss0")
    bg.rect(1, 1, W - 2, BAR_H - 2, "ash0")
    for x in (47, 48, 133):
        bg.put(x, 0, "ash0")

    fill = Cv(W, BAR_H)
    fill.hline(1, W - 2, 1, "moss2")
    fill.hline(1, W - 2, 2, "moss1")
    fill.hline(1, W - 2, 3, "moss0")
    return bg.image(), fill.image()


# ─────────────────────────── 단축 슬롯 ───────────────────────────

def bar_stone(cv, x0, y0, w, h, joints, seed, damp_rows=1):
    """
    단축 슬롯·왼손 칸의 띠: 윤곽 + 돌 (joints 의 x 에서 나뉜다) 에 칸을 판다. 돌 얼굴은 판보다 한 단 밝은 ash1 이지만
    칸이 거의 다 덮어 띠는 어둡게 읽힌다. 아래 damp_rows 줄은 젖었다.
    """
    cut = (1, 1, 1, 1)
    owner = {}
    for y in range(h):
        for x in range(w):
            k = ring_of(x, y, w, h, cut)
            if k < 0:
                continue
            if k == 0:
                cv.put(x0 + x, y0 + y, OUTLINE)
                continue
            if x in joints:
                cv.put(x0 + x, y0 + y, JOINT)
                continue
            owner[(x0 + x, y0 + y)] = sum(1 for j in joints if j < x)
    shade_stones(cv, owner, lambda x, y: y >= y0 + h - 1 - damp_rows)
    rnd = Lcg(seed)
    # 위 모서리의 흠 몇 곳 (칸 사이 돌기둥 위)
    for _ in range(3):
        k = 1 + rnd(max(1, w // 20 - 1))
        cv.put(x0 + 20 * k + rnd(2), y0 + 1, STONE)


def hotbar():
    """
    182×22. 돌 띠에 판 칸 아홉 (칸 x 2+20k..19+20k, 바닥 = 아이템 자리 3+20k..18+20k). 띠는 세 돌 (칸 사이 돌기둥에서
    나뉜다). 화면 아래에 늘 떠 있는 것이라 장식은 없다.
    """
    W, H = 182, 22
    cv = Cv(W, H)
    bar_stone(cv, 0, 0, W, H, joints=(60, 120), seed=7)
    for k in range(9):
        well(cv, 2 + 20 * k, 2, corner=STONE)
    return cv.image()


# 고른 칸의 테 (24×23): 가장 밝은 돌 (ash3) 로 다듬은 고리. 쇠·청동이 아니다. 귀 두 곳이 이 빠졌다.
# O 윤곽, G ash3 (빛 받는 바깥), L ash2, M ash1, D moss0 (그늘), K 안쪽 위·왼쪽 그늘 (ash0)
SELECTION = [
    ".OOOOOOOOOOOOOOOOOOOOO..",
    "OGGGGGGGGGGGGGGGGGGGGMO.",
    "OGLLLLLLLLLLLLLLLLLLLLDO",
    "OGLKKKKKKKKKKKKKKKKKLMDO",
] + ["OGLK" + "." * 16 + "LMDO"] * 16 + [
    "OGLLLLLLLLLLLLLLLLLLLMDO",
    "OMDDDDDDDDDDDDDDDDDDDDDO",
    "..OOOOOOOOOOOOOOOOOOOOO.",
]
SELECTION_INK = {"O": OUTLINE, "G": "ash3", "L": "ash2", "M": "ash1", "D": "moss0", "K": "ash0"}


def hotbar_selection():
    cv = Cv(24, 23)
    cv.stamp(0, 0, SELECTION, SELECTION_INK)
    # 이 빠진 자리: 왼쪽 아래 바깥 모서리 두 점, 위 모서리 한 점
    cv.put(1, 19, "ash1")
    cv.put(1, 20, OUTLINE)
    cv.put(15, 1, "ash2")
    return cv.image()


def offhand(right):
    """왼손 칸 29×24. 칸 상자는 22×22 (왼쪽: x 0..21, 오른쪽: x 7..28, y 1..22), 아이템은 y 4..19. 단축 슬롯과 같은 띠."""
    W, H = 29, 24
    cv = Cv(W, H)
    x0 = 7 if right else 0
    bar_stone(cv, x0, 1, 22, 22, joints=(), seed=11 + right)
    well(cv, x0 + 2, 3, corner=STONE)
    return cv.image()


# 공격 대기 표시 (단검 실루엣). 칼날은 무딘 쇠 (재), 손잡이는 녹
ATTACK_BG = [
    "..................",
    "..............KK..",
    ".............KxxK.",
    "............KxxxK.",
    "...........KxxxK..",
    "..........KxxxK...",
    ".........KxxxK....",
    "........KxxxK.....",
    "..KK...KxxxK......",
    "..KxK.KxxxK.......",
    "...KxKxxxK........",
    "....KxxxK.........",
    "....KxxK..........",
    "...KxKKxK.........",
    "..KxK..KxK........",
    ".KxK....KK........",
    ".KK...............",
    "..................",
]
ATTACK_FILL = [
    "..................",
    "..............KK..",
    ".............KbBK.",
    "............KbBnK.",
    "...........KbBnK..",
    "..........KbBnK...",
    ".........KbnnK....",
    "........KbBnK.....",
    "..KK...KbnnK......",
    "..KmK.KbBnK.......",
    "...KmKbnnK........",
    "....KmnmK.........",
    "....KmmK..........",
    "...KrKKmK.........",
    "..KrK..KrK........",
    ".KrK....KK........",
    ".KK...............",
    "..................",
]


def attack_indicator():
    ink = {"K": "ash0", "x": "moss0", "b": "ash1", "B": "ash3", "n": "ash2", "m": "rust1", "r": "rust0"}
    bg, fg = Cv(18, 18), Cv(18, 18)
    bg.stamp(0, 0, ATTACK_BG, ink)
    fg.stamp(0, 0, ATTACK_FILL, ink)
    return bg.image(), fg.image()


# ─────────────────────────── 창 (인벤토리, 상자, 제작대) ───────────────────────────

# 칸 자리는 gui_skin.CONTAINER_LAYOUTS 와 같다 (바닐라 jar 와 픽셀까지 대조한 값). 여기에 창마다 돌 쌓기를 더한다:
#   masonry  own (네 귀를 차지하는 줄), top/bottom (가로 줄눈 x), left/right (세로 줄눈 y), cut (네 귀 깎임),
#            seed (이 빠진 귀·젖은 줄의 자리), rise (옆 테에 습기가 올라온 높이 왼쪽, 오른쪽), dry (아래 테의 마른 가운데),
#            seeps (물이 스미는 위 테 줄눈 x 와 물때 모양), notches (떨어져 나간 윤곽)
#   grime    판의 귀에 다져진 때 (x, y, 귀, 크기)
#   ledges   나눔줄 자리의 돌 턱 (x0, x1, y, 턱 돌의 줄눈)
#   seams    돌판 사이 줄눈 (y, 그 아래 배어 나온 얼룩의 x 들). 상자의 위 판과 아래 판 (126 줄) 사이
# 옆 테의 줄눈은 턱과 돌판 줄눈의 높이에 맞춘다 (턱이 벽의 줄눈에 박혔다).
def _grid(x0, y0, cols, rows):
    return [(x0 + 18 * i, y0 + 18 * j) for j in range(rows) for i in range(cols)]


CONTAINER_LAYOUTS = {
    "inventory": {
        "size": (176, 166),
        "wells": [(7, 7 + 18 * i) for i in range(4)] + [(76, 61)] + _grid(97, 17, 2, 2)
                 + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(153, 27, 18, 18)],
        "alcove": (25, 7, 51, 72),
        "arrow": (135, 150, 35, 6),
        "titles": [(97, 6)],
        "dividers": [(7, 167, 80), (7, 167, 138)],
        "masonry": dict(own="hvvh", top=(23, 61, 88, 124, 150), bottom=(37, 79, 112, 141),
                        left=(18, 31, 49, 63, 79, 94, 109, 123, 137, 151), right=(9, 19, 35, 54, 66, 79, 91, 104, 117, 137, 148), cut=(2, 3, 2, 2), seed=29,
                        rise=(22, 15), dry=(64, 116), seeps=((88, "long"), (150, "mid")),
                        notches=((40, 0, 2, "top"), (0, 96, 3, "left"), (175, 41, 2, "right"), (128, 165, 3, "bottom"))),
        "grime": [(167, 6, "tr", "corner"), (167, 78, "br", "small"), (76, 6, "tl", "small"), (96, 6, "tr", "small"),
                  (167, 56, "br", "small"), (76, 56, "bl", "small")],
        "pools": [(88, 55)],
        "ledge_joints": {80: (58, 121), 138: (44, 103, 140)},
        "seams": [],
        "drips": [(100, 53), (127, 53), (161, 46)],
        # 판의 큰 돌: 위 테 줄눈 88 에서 내려오는 세로 줄눈 (물이 이 줄을 타고 흐른다), 57 줄의 가로 줄눈, 오른쪽 아래 세로
        "field_joints": [("v", 88, 6, 56), ("h", 57, 76, 167), ("v", 140, 58, 78), ("v", 150, 6, 25)],
    },
    "crafting_table": {
        "size": (176, 166),
        "wells": _grid(29, 16, 3, 3) + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(119, 30, 26, 26)],
        "alcove": None,
        "arrow": (90, 111, 42, 7),
        "titles": [(29, 6), (8, 72)],
        "dividers": [(7, 167, 138)],
        "masonry": dict(own="hhvv", top=(33, 69, 101, 128, 156), bottom=(28, 66, 99, 133),
                        left=(21, 42, 57, 73, 88, 104, 120, 137, 150), right=(14, 27, 47, 70, 86, 108, 122, 137, 152), cut=(3, 2, 2, 2), seed=41,
                        rise=(18, 21), dry=(58, 120), seeps=((101, "mid"), (156, "long")),
                        notches=((0, 58, 2, "left"), (88, 0, 3, "top"), (175, 120, 2, "right"))),
        "grime": [(167, 6, "tr", "small"), (8, 70, "bl", "small"), (167, 81, "br", "small")],
        "ledge_joints": {138: (52, 117)},
        "seams": [],
        "drips": [(64, 70), (79, 70), (131, 57)],
        "field_joints": [("v", 156, 6, 81), ("v", 101, 6, 33), ("h", 61, 113, 155)],
    },
    "generic_54": {
        "size": (176, 222),
        "wells": _grid(7, 17, 9, 6) + _grid(7, 139, 9, 3) + _grid(7, 197, 9, 1),
        "result": [],
        "alcove": None,
        "arrow": None,
        "titles": [(8, 6), (8, 129)],
        "dividers": [(7, 167, 194)],
        "masonry": dict(own="hvvh", top=(31, 70, 104, 141), bottom=(23, 57, 98, 129, 160),
                        left=(19, 33, 52, 70, 81, 99, 113, 126, 144, 160, 177, 193, 205),
                        right=(13, 29, 47, 60, 78, 92, 103, 117, 126, 139, 151, 168, 181, 193, 207), cut=(2, 2, 3, 2), seed=53,
                        rise=(26, 19), dry=(60, 118), seeps=((104, "short"), (141, "short")),
                        notches=((58, 0, 3, "top"), (175, 70, 2, "right"), (0, 150, 2, "left"), (110, 221, 2, "bottom"))),
        "grime": [(167, 6, "tr", "corner"), (167, 127, "tr", "small"), (8, 127, "tl", "small")],
        "ledge_joints": {194: (61, 126)},
        "seams": [(126, (97, 151))],
    },
}


def _alcove(cv, x, y, w, h):
    """
    인벤토리의 인물 자리: 묘실 벽감. 바깥 상자는 바닐라와 같은 칸 (그늘 줄·입술 줄) 이고, 그 안에 반원 아치를 세웠다:
    쐐기돌 고리 (3픽셀, 이맛돌이 가운데) 아래가 창에서 가장 깊은 어둠이다. 아치 위 두 귀는 판과 같은 돌벽.
    바닥에는 인물이 서는 받침돌 (윗면 빛, 앞면, 젖은 아래) 이 있고 받침돌 양 끝에 때가 고였다.
    """
    import math
    well(cv, x, y, w, h, floor=DEEP)
    x0, x1 = x + 1, x + w - 2          # 속 26..74
    cx = (x0 + x1) / 2                  # 50
    R = (x1 - x0) / 2 + 0.5             # 24.5
    ys = y + 4 + R                      # 이맛돌 아래 (아치 꼭대기 속) 가 y+4
    owner = {}
    # 쐐기돌: 각도 (도, 0 = 오른쪽 수평) 로 나눈다. 이맛돌은 90 둘레 넓게
    cuts = (12, 35, 58, 80, 100, 122, 145, 168)
    for py in range(y + 1, int(ys) + 1):
        for px in range(x0, x1 + 1):
            dx, dy = px - cx, ys - py
            d = math.hypot(dx, dy)
            if d <= R:
                continue
            if d <= R + 3:
                ang = math.degrees(math.atan2(dy, dx))
                seg = sum(1 for a in cuts if ang > a)
                on_joint = any(abs(ang - a) * math.pi / 180 * d < 0.55 for a in cuts)
                if on_joint:
                    cv.put(px, py, JOINT)
                else:
                    owner[(px, py)] = seg
            else:
                cv.put(px, py, PANEL)
    shade_stones(cv, owner)
    # 아치 속 가장자리 (쐐기돌 아랫면) 는 그늘: 고리 안쪽 한 줄을 어둡게
    for (px, py) in list(owner):
        if math.hypot(px - cx, ys - py) <= R + 1.0 and cv.get(px, py) == STONE_LIT:
            cv.put(px, py, STONE)
    # 받침돌 (y+h-5 .. y+h-2): 윗면 빛, 앞면, 아래는 젖었다. 가운데에서 한 번 나뉜다
    by = y + h - 5
    pl = {}
    for py in range(by, y + h - 1):
        for px in range(x0, x1 + 1):
            if px == 57:
                cv.put(px, py, JOINT)
            else:
                pl[(px, py)] = 0 if px < 57 else 1
    shade_stones(cv, pl, lambda px, py: py >= y + h - 2)
    cv.hline(x0, x1, by - 1, JOINT)
    for px, col in ((x0, SOOT), (x0 + 1, MOSS), (x0 + 2, MUD), (x0 + 4, MUD), (x1, SOOT), (x1 - 1, SOOT), (x1 - 2, MUD)):
        cv.put(px, by, col)


def _result(cv, x, y, w, h, frame_right):
    """결과 칸: 입술이 한 단 밝은 다듬은 돌 (ash2) 이고, 위·왼쪽 바깥에 돌 테 한 줄 (빛), 아래 바깥은 그 그림자."""
    well(cv, x, y, w, h, lip=STONE_LIT, corner=STONE)
    right = min(x + w, frame_right)
    cv.hline(x - 1, right, y - 1, STONE)
    cv.vline(x - 1, y - 1, y + h, STONE)
    cv.hline(x, right, y + h, JOINT)
    if w > 18:
        # 큰 결과 칸: 아이템 (x+5 .. x+20) 둘레 한 칸 밖에 새긴 고리 (위·왼쪽 그늘, 아래·오른쪽 빛)
        a, b = x + 3, x + w - 4
        cv.hline(a + 1, b - 1, y + 3, SHADOW)
        cv.vline(a, y + 4, y + h - 5, SHADOW)
        cv.hline(a + 1, b - 1, y + h - 4, STONE)
        cv.vline(b, y + 4, y + h - 5, STONE)


def container(name):
    L = CONTAINER_LAYOUTS[name]
    w, h = L["size"]
    M = L["masonry"]
    cv = Cv(256, 256)
    masonry(cv, w, h, M)
    field_joints(cv, L.get("field_joints", ()))
    # 위 테 줄눈에서 스민 물때 (판과의 줄눈 다음 줄부터)
    first_well_y = min(y for _, y in L["wells"])
    for sx, kind in M.get("seeps", ()):
        cut = None
        if name == "generic_54":
            cut = first_well_y - (T + 2) - 1      # 칸의 그늘 줄 바로 위 한 줄은 비운다
        seep(cv, sx, T + 2, kind, cut)
    for gx, gy, corner, kind in L["grime"]:
        grime(cv, gx, gy, corner, kind)
    if L["alcove"]:
        _alcove(cv, *L["alcove"])
    for x, y in L["wells"]:
        well(cv, x, y)
    for box in L["result"]:
        _result(cv, *box, frame_right=w - TS - 2)
    if L["arrow"]:
        carved_arrow(cv, *L["arrow"])
    rnd = Lcg(M["seed"] + 1)
    for x0, x1, y in L["dividers"]:
        ledge(cv, x0, x1, y, w, rnd, L["ledge_joints"].get(y, ()))
    for dx, dy in L.get("drips", ()):
        seep(cv, dx, dy, "drip")
    for px, py in L.get("pools", ()):
        seep(cv, px, py, "pool")
    for sy, xs in L["seams"]:
        cv.hline(TS + 1, w - TS - 2, sy, JOINT)
        for sx in xs:
            seep(cv, sx, sy + 1, "wide")
    return cv.image()


# ─────────────────────────── 칸 가리킴, 빈 칸 그림 ───────────────────────────

SLOT_HIGHLIGHT_SCALING = {"type": "nine_slice", "width": 24, "height": 24, "border": 4}


def slot_highlight():
    """
    마우스가 올라간 칸 (24×24, 칸 속은 4..19). 뒤: 바닥이 마른 돌빛 (ash1) 으로 한 단 밝아진다.
    앞: 칸 테두리 네 귀에 분필로 그은 듯한 꺾쇠 (ash3, 오른쪽 아래는 그늘이라 ash2). 반투명은 없다.
    """
    back, front = Cv(24, 24), Cv(24, 24)
    back.rect(4, 4, 19, 19, "ash1")
    for (x, y, sx, sy, col) in ((3, 3, 1, 1, CHALK), (20, 3, -1, 1, CHALK),
                                (3, 20, 1, -1, CHALK), (20, 20, -1, -1, "ash1")):
        for i in range(3):
            front.put(x + sx * i, y, col)
            front.put(x, y + sy * i, col)
    return back.image(), front.image()


# 빈 갑옷·방패 칸의 그림: 바닥돌에 새긴 선 (gui_skin 과 같은 모양). 새긴 홈은 검고 (ash0), 그 아래·오른쪽 벽이 빛을 받는다 (ash1).
SLOT_ICONS = {
    "helmet": [
        "................",
        "................",
        ".....oooooo.....",
        "....o......o....",
        "...o........o...",
        "...o........o...",
        "...o........o...",
        "...oooo..oooo...",
        "...o...oo...o...",
        "...o...oo...o...",
        "...o.o....o.o...",
        "...o.o....o.o...",
        "...o.o....o.o...",
        "....oo....oo....",
        "................",
        "................",
    ],
    "chestplate": [
        "................",
        "................",
        "................",
        "..ooo......ooo..",
        ".o...o....o...o.",
        ".o....oooo....o.",
        ".o............o.",
        "..oo........oo..",
        "...o........o...",
        "...o........o...",
        "...o........o...",
        "...o........o...",
        "....oooooooo....",
        "................",
        "................",
        "................",
    ],
    "leggings": [
        "................",
        "................",
        "...oooooooooo...",
        "...o........o...",
        "...o........o...",
        "...o...oo...o...",
        "...o..o..o..o...",
        "...o..o..o..o...",
        "...o..o..o..o...",
        "...o..o..o..o...",
        "...o..o..o..o...",
        "...o..o..o..o...",
        "...o..o..o..o...",
        "...oooo..oooo...",
        "................",
        "................",
    ],
    "boots": [
        "................",
        "................",
        "................",
        "....ooo..ooo....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "...o..o..o..o...",
        "..o...o..o...o..",
        "..o...o..o...o..",
        "..ooooo..ooooo..",
        "................",
        "................",
        "................",
    ],
    "shield": [
        "................",
        "................",
        "..oooooooooooo..",
        "..o..........o..",
        "..o....oo....o..",
        "..o..oooooo..o..",
        "..o....oo....o..",
        "..o....oo....o..",
        "...o...oo...o...",
        "...o........o...",
        "....o......o....",
        ".....o....o.....",
        "......o..o......",
        ".......oo.......",
        "................",
        "................",
    ],
}


def slot_icon(name):
    cv = Cv(16, 16)
    rows = SLOT_ICONS[name]
    on = {(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "o"}
    for x, y in on:
        cv.put(x, y, SHADOW)
    for x, y in on:
        for nx, ny in ((x + 1, y), (x, y + 1)):
            if (nx, ny) not in on and 0 <= nx < 16 and 0 <= ny < 16:
                cv.put(nx, ny, STONE_LIT)
    return cv.image()


# ─────────────────────────── 단추 ───────────────────────────

BUTTON_SCALING = {
    "button": {"type": "nine_slice", "width": 200, "height": 20, "border": 3},
    "button_highlighted": {"type": "nine_slice", "width": 200, "height": 20, "border": 3},
    "button_disabled": {"type": "nine_slice", "width": 200, "height": 20, "border": 1},
}


def _ring_frame(cv, x0, y0, w, h, rings, fill, cut=1):
    """고리 테 (고리마다 (위·왼쪽, 비스듬한 귀, 아래·오른쪽)). gui_skin.frame 과 같은 일을 귀 깎임 cut 으로."""
    W, H = w - 1, h - 1
    for y in range(h):
        for x in range(w):
            k = ring_of(x, y, w, h, (cut,) * 4)
            if k < 0:
                continue
            side = 0 if (y == k or x == k) else 2 if (H - y == k or W - x == k) else 1
            if x + y - cut == k:
                side = 0
            elif (W - x) + (H - y) - cut == k:
                side = 2
            elif (W - x) + y - cut == k or x + (H - y) - cut == k:
                side = 1
            if k < len(rings):
                cv.put(x0 + x, y0 + y, rings[k][side])
            elif fill:
                cv.put(x0 + x, y0 + y, fill)


BUTTON_RINGS = {
    "normal": (((OUTLINE,) * 3, (STONE_LIT, STONE, STONE_DIM)), STONE),
    # 가리킴: 돌이 마른 듯 한 단 밝아진다 (빛 모서리는 가장 밝은 돌)
    "highlighted": (((OUTLINE,) * 3, ("ash2", "ash1", STONE)), "ash1"),
    # 사용 못 함: 젖어 가라앉은 돌
    "disabled": (((OUTLINE,) * 3,), STONE_DIM),
}


def button(state):
    """
    200×20 돌 단추. 윤곽, 1픽셀 베벨 (위·왼쪽 빛, 아래·오른쪽 젖은 그늘), 돌 얼굴. 9조각의 가운데는 이어 붙이므로
    얼굴에는 자국을 두지 않는다. 아래 줄 (9조각 테 안) 의 양 끝에만 검은 때가 고였다.
    """
    W, H = 200, 20
    rings, fill = BUTTON_RINGS[state]
    cv = Cv(W, H)
    _ring_frame(cv, 0, 0, W, H, rings, fill)
    if state != "disabled":
        for x, y in ((1, H - 2), (2, H - 2), (W - 2, H - 3)):
            cv.put(x, y, SOOT)
    return cv.image()


# 제작법 책 단추 20×18: 돌 단추 위에 가죽 장정의 책 (녹빛 가죽, 바랜 책장, 뼈 걸쇠).
RECIPE_BUTTON = [
    ".OOOOOOOOOOOOOOOOOO.",
    "OiiiiiiiiiiiiiiiiiiO",
    "OifffffffffffffffffO",
    "OiffffffffffffffffsO",
    "OifffkkkkkkkkkffffsO",
    "OifffdBBBBBBBpkfffsO",
    "OifffdbbbbbbbpkfffsO",
    "OifffdbbbbbbbpkfffsO",
    "OifffdbbbbbbccdfffsO",
    "OifffdbbbbbbbpkfffsO",
    "OifffdbbbbbbbpkfffsO",
    "OifffdbbbbbbbpkfffsO",
    "OiffffkkkkkkkkkfffsO",
    "OiffffffffffffffffsO",
    "OimffffffffffffffmsO",
    "OissssssssssssssssOO",
    "OOOOOOOOOOOOOOOOOOOO",
    ".OOOOOOOOOOOOOOOOOO.",
]


def recipe_button(hi):
    ink = {"O": OUTLINE, "i": CHALK if hi else STONE_LIT, "f": "ash2" if hi else STONE, "s": STONE if hi else STONE_DIM,
           "k": OUTLINE, "b": "rust1", "B": "rust2", "d": "rust0", "p": "parch1", "c": "bone0", "m": MUD}
    cv = Cv(20, 18)
    cv.stamp(0, 0, [r.replace(".", " ") for r in RECIPE_BUTTON], ink)
    return cv.image()


# ─────────────────────────── 설정 창의 위젯 ───────────────────────────

WIDGET_SCALING = {
    "slider": {"type": "nine_slice", "width": 200, "height": 20, "border": 2},
    "slider_highlighted": {"type": "nine_slice", "width": 200, "height": 20, "border": 2},
    "slider_handle": {"type": "nine_slice", "width": 8, "height": 20,
                      "border": {"left": 2, "top": 2, "right": 2, "bottom": 3}},
    "slider_handle_highlighted": {"type": "nine_slice", "width": 8, "height": 20,
                                  "border": {"left": 2, "top": 2, "right": 2, "bottom": 3}},
    "text_field": {"type": "nine_slice", "width": 200, "height": 20, "border": 1},
    "text_field_highlighted": {"type": "nine_slice", "width": 200, "height": 20, "border": 1},
    "tab": {"type": "nine_slice", "width": 130, "height": 24, "border": {"left": 2, "top": 2, "right": 2, "bottom": 0}},
    "tab_highlighted": {"type": "nine_slice", "width": 130, "height": 24,
                        "border": {"left": 2, "top": 2, "right": 2, "bottom": 0}},
    "tab_selected": {"type": "nine_slice", "width": 130, "height": 24,
                     "border": {"left": 2, "top": 2, "right": 2, "bottom": 0}},
    "tab_selected_highlighted": {"type": "nine_slice", "width": 130, "height": 24,
                                 "border": {"left": 2, "top": 2, "right": 2, "bottom": 0}},
    "scroller": {"type": "nine_slice", "width": 6, "height": 32, "border": 1},
    "scroller_background": {"type": "nine_slice", "width": 6, "height": 32, "border": 1},
}
# 돌에 판 홈 (밀대 길, 고름 칸): 윤곽 → (위·왼쪽 그늘 / 아래·오른쪽 입술) → 젖은 바닥. 칸과 같은 얼굴
GROOVE_RINGS = {
    False: ((OUTLINE,) * 3, (SHADOW, SHADOW, LIP)),
    True: ((OUTLINE,) * 3, (SHADOW, SHADOW, CHALK)),
}


def slider_track(hi):
    cv = Cv(200, 20)
    _ring_frame(cv, 0, 0, 200, 20, GROOVE_RINGS[hi], FLOOR)
    return cv.image()


HANDLE = [
    ".OOOOOO.",
    "OiiiiiiO",
    "OiffffsO",
    "OiffffsO",
    "OiffffsO",
    "OiffffsO",
    "OiffffsO",
    "OiggggsO",
    "OillllsO",
    "OiffffsO",
    "OiggggsO",
    "OillllsO",
    "OiffffsO",
    "OiffffsO",
    "OiffffsO",
    "OiffffsO",
    "OiffffsO",
    "OissssOO",
    "OOOOOOOO",
    ".OOOOOO.",
]
HANDLE_TONES = {
    False: {"O": OUTLINE, "i": STONE_LIT, "f": STONE, "s": STONE_DIM, "g": OUTLINE, "l": STONE_LIT},
    True: {"O": OUTLINE, "i": CHALK, "f": "ash2", "s": STONE, "g": OUTLINE, "l": CHALK},
}


def slider_handle(hi):
    cv = Cv(8, 20)
    cv.stamp(0, 0, [r.replace(".", " ") for r in HANDLE], HANDLE_TONES[hi])
    return cv.image()


CHECK = [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..............CC....",
    ".............CCk....",
    "............CCk.....",
    "....CC.....CCk......",
    ".....CC...CCk.......",
    "......CC.CCk........",
    ".......CCCk.........",
    "........Ck..........",
    ".........k..........",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
]


def checkbox(selected, hi):
    cv = Cv(20, 20)
    _ring_frame(cv, 0, 0, 20, 20, GROOVE_RINGS[hi], FLOOR)
    if selected:
        cv.stamp(0, 0, [r.replace(".", " ") for r in CHECK], {"C": "bone1" if hi else "parch2", "k": OUTLINE})
    return cv.image()


def text_field(hi):
    """글 칸 200×20 (9조각 테 1): 가장 어두운 재 바탕에 돌 테 한 줄, 고르면 마른 돌빛 테."""
    cv = Cv(200, 20)
    cv.rect(0, 0, 199, 19, CHALK if hi else STONE)
    cv.rect(1, 1, 198, 18, "ash0")
    return cv.image()


def tab(selected, hi):
    W, H = 130, 24
    cv = Cv(W, H)
    lit, dark = (CHALK, "ash2") if hi else (STONE_LIT, STONE_DIM)
    top = 0 if selected else 4
    cv.hline(0, W - 1, top, OUTLINE)
    cv.hline(1, W - 2, top + 1, lit)
    cv.vline(0, top, H - 1, OUTLINE)
    cv.vline(W - 1, top, H - 1, OUTLINE)
    cv.vline(1, top + 1, H - 1 if selected else H - 2, lit)
    cv.vline(W - 2, top + 1, H - 1 if selected else H - 2, dark)
    if not selected:
        cv.rect(2, top + 2, W - 3, H - 3, STONE)
        cv.hline(0, W - 1, H - 2, lit)
        cv.hline(0, W - 1, H - 1, OUTLINE)
    return cv.image()


def scroller(background):
    cv = Cv(6, 32)
    if background:
        cv.rect(0, 0, 5, 31, "ash0")
    else:
        cv.rect(0, 0, 5, 31, STONE)
        cv.hline(0, 4, 0, STONE_LIT)
        cv.vline(0, 0, 30, STONE_LIT)
        cv.vline(5, 0, 31, STONE_DIM)
        cv.hline(0, 5, 31, STONE_DIM)
    return cv.image()


SEPARATORS = ("header_separator", "footer_separator", "inworld_header_separator", "inworld_footer_separator")


def separator():
    cv = Cv(32, 2)
    cv.hline(0, 31, 0, GROOVE)
    cv.hline(0, 31, 1, LIP)
    return cv.image()


def widgets():
    out = {}
    for hi in (False, True):
        sfx = "_highlighted" if hi else ""
        out["slider" + sfx] = slider_track(hi)
        out["slider_handle" + sfx] = slider_handle(hi)
        out["text_field" + sfx] = text_field(hi)
        out["checkbox" + sfx] = checkbox(False, hi)
        out["checkbox_selected" + sfx] = checkbox(True, hi)
        out["tab" + sfx] = tab(False, hi)
        out["tab_selected" + sfx] = tab(True, hi)
    out["scroller"] = scroller(False)
    out["scroller_background"] = scroller(True)
    return out


# ─────────────────────────── Dialog 경고 단추 ───────────────────────────

WARNING_BUTTON = [
    ".OOOOOOOOOOOOOOOOOO.",
    "OiiiiiiiiiiiiiiiiiiO",
    "OifffffffffffffffffO",
    "OiffffffffffffffffsO",
    "OifffffffPPkffffffsO",
    "OifffffffPpkffffffsO",
    "OifffffffPpkffffffsO",
    "OifffffffPpkffffffsO",
    "OifffffffPpkffffffsO",
    "OifffffffPpkffffffsO",
    "OifffffffPpkffffffsO",
    "OiffffffffkkffffffsO",
    "OiffffffffffffffffsO",
    "OifffffffPPkffffffsO",
    "OifffffffPpkffffffsO",
    "OiffffffffkkffffffsO",
    "OiffffffffffffffffsO",
    "OissssssssssssssssOO",
    "OOOOOOOOOOOOOOOOOOOO",
    ".OOOOOOOOOOOOOOOOOO.",
]
WARNING_TONES = {
    "normal":      {"O": OUTLINE, "i": STONE_LIT, "f": STONE, "s": STONE_DIM, "P": "parch2", "p": "parch1", "k": OUTLINE},
    "highlighted": {"O": OUTLINE, "i": CHALK, "f": "ash2", "s": STONE, "P": "bone1", "p": "parch2", "k": OUTLINE},
    "disabled":    {"O": OUTLINE, "i": STONE_DIM, "f": STONE_DIM, "s": OUTLINE, "P": "ash2", "p": "ash1", "k": "ash0"},
}


def warning_button(state):
    cv = Cv(20, 20)
    cv.stamp(0, 0, [r.replace(".", " ") for r in WARNING_BUTTON], WARNING_TONES[state])
    return cv.image()


# ─────────────────────────── 설명 칸 ───────────────────────────

TOOLTIP_SCALING = {
    "background": {"type": "nine_slice", "width": 100, "height": 100, "border": 9},
    "frame": {"type": "nine_slice", "width": 100, "height": 100, "border": 10, "stretch_inner": True},
}
TOOLTIP_RINGS = (
    (OUTLINE, OUTLINE, OUTLINE),
    (STONE_LIT, STONE, STONE_DIM),
    (OUTLINE, OUTLINE, OUTLINE),
)


def tooltip():
    """바탕: 가장 어두운 재. 테: 윤곽, 돌 한 줄 (위·왼쪽 빛, 아래·오른쪽 젖은 그늘), 안쪽 재. 장식은 없다."""
    N = 100
    bg = Cv(N, N)
    _ring_frame(bg, 4, 4, N - 8, N - 8, (), "ash0", cut=2)
    fr = Cv(N, N)
    _ring_frame(fr, 4, 4, N - 8, N - 8, TOOLTIP_RINGS, None, cut=2)
    return bg.image(), fr.image()


# ─────────────────────────── 빌드 ───────────────────────────

ARMOR_SPRITES = ("armor_empty", "armor_half", "armor_full")


def build(out):
    """out (팩 뿌리) 에 그림과 .mcmeta 를 쓴다. 쓴 그림 경로 목록을 돌려준다."""
    written = []
    hud = ("sprites", "hud")
    written += hearts(out)
    for name in ARMOR_SPRITES:
        written.append(save(Image.new("RGBA", (9, 9), (0, 0, 0, 0)), out, *hud, name + ".png"))
    bg, fill = stamina_bar()
    written.append(save(bg, out, *hud, "experience_bar_background.png"))
    written.append(save(fill, out, *hud, "experience_bar_progress.png"))
    written.append(save(hotbar(), out, *hud, "hotbar.png"))
    written.append(save(hotbar_selection(), out, *hud, "hotbar_selection.png"))
    written.append(save(offhand(False), out, *hud, "hotbar_offhand_left.png"))
    written.append(save(offhand(True), out, *hud, "hotbar_offhand_right.png"))
    abg, afg = attack_indicator()
    written.append(save(abg, out, *hud, "hotbar_attack_indicator_background.png"))
    written.append(save(afg, out, *hud, "hotbar_attack_indicator_progress.png"))
    for name in CONTAINER_LAYOUTS:
        written.append(save(container(name), out, "container", name + ".png"))
    for state, fname in (("normal", "button"), ("highlighted", "button_highlighted"), ("disabled", "button_disabled")):
        written.append(save(button(state), out, "sprites", "widget", fname + ".png"))
        save_mcmeta(out, BUTTON_SCALING[fname], "sprites", "widget", fname + ".png")
    hb, hf = slot_highlight()
    for img, n in ((hb, "slot_highlight_back"), (hf, "slot_highlight_front")):
        written.append(save(img, out, "sprites", "container", n + ".png"))
        save_mcmeta(out, SLOT_HIGHLIGHT_SCALING, "sprites", "container", n + ".png")
    for n in SLOT_ICONS:
        written.append(save(slot_icon(n), out, "sprites", "container", "slot", n + ".png"))
    written.append(save(recipe_button(False), out, "sprites", "recipe_book", "button.png"))
    written.append(save(recipe_button(True), out, "sprites", "recipe_book", "button_highlighted.png"))
    for state, fname in (("normal", "warning_button"), ("highlighted", "warning_button_highlighted"),
                         ("disabled", "warning_button_disabled")):
        written.append(save(warning_button(state), out, "sprites", "dialog", fname + ".png"))
    for fname, img in widgets().items():
        written.append(save(img, out, "sprites", "widget", fname + ".png"))
        if fname in WIDGET_SCALING:
            save_mcmeta(out, WIDGET_SCALING[fname], "sprites", "widget", fname + ".png")
    for n in SEPARATORS:
        written.append(save(separator(), out, n + ".png"))
    tbg, tfr = tooltip()
    written.append(save(tbg, out, "sprites", "tooltip", "background.png"))
    written.append(save(tfr, out, "sprites", "tooltip", "frame.png"))
    for n in ("background", "frame"):
        save_mcmeta(out, TOOLTIP_SCALING[n], "sprites", "tooltip", n + ".png")
    return written


# ─────────────────────────── 미리보기 ───────────────────────────

def _sprite(out, *parts):
    return Image.open(os.path.join(out, *GUI, *parts)).convert("RGBA")


def _big(img, k):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def nine_slice(sprite, w, h, b, stretch_inner=False):
    """1.21 GuiGraphics 처럼: 귀는 그대로, 가장자리와 가운데는 이어 붙인다 (stretch_inner 면 늘인다)."""
    sw, sh = sprite.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def seg(src_box, dst_x, dst_y, dw, dh):
        if dw <= 0 or dh <= 0:
            return
        src = sprite.crop(src_box)
        if stretch_inner:
            out.alpha_composite(src.resize((dw, dh), Image.NEAREST), (dst_x, dst_y))
            return
        for ty in range(0, dh, src.height):
            for tx in range(0, dw, src.width):
                piece = src.crop((0, 0, min(src.width, dw - tx), min(src.height, dh - ty)))
                out.alpha_composite(piece, (dst_x + tx, dst_y + ty))

    iw, ih = w - 2 * b, h - 2 * b
    for (sx, sy, dx, dy) in ((0, 0, 0, 0), (sw - b, 0, w - b, 0), (0, sh - b, 0, h - b), (sw - b, sh - b, w - b, h - b)):
        out.alpha_composite(sprite.crop((sx, sy, sx + b, sy + b)), (dx, dy))
    seg((b, 0, sw - b, b), b, 0, iw, b)
    seg((b, sh - b, sw - b, sh), b, h - b, iw, b)
    seg((0, b, b, sh - b), 0, b, b, ih)
    seg((sw - b, b, sw, sh - b), w - b, b, b, ih)
    seg((b, b, sw - b, sh - b), b, b, iw, ih)
    return out


def draw_hearts(canvas, out, x, y, health, display=None, blink=False, shake=None, kind="", absorb=0):
    """바닐라 renderHearts 와 같은 차례 (오른쪽 하트부터, 칸마다 그릇 → 깜빡임 → 채움)."""
    d = ("sprites", "hud", "heart")
    n = 10
    pre = kind + "_" if kind else ""
    for l in range(n + (absorb + 1) // 2 - 1, -1, -1):
        row, col = divmod(l, 10)
        hx, hy = x + col * 8, y - row * 10 + (shake[l] if shake else 0)
        canvas.alpha_composite(_sprite(out, *d, "container_blinking.png" if blink else "container.png"), (hx, hy))
        q = l * 2
        if l >= n:
            rr = q - n * 2
            if rr < absorb:
                part = "half" if rr + 1 == absorb else "full"
                canvas.alpha_composite(_sprite(out, *d, f"absorbing_{part}.png"), (hx, hy))
        if blink and display is not None and q < display:
            part = "half" if q + 1 == display else "full"
            canvas.alpha_composite(_sprite(out, *d, f"{pre}{part}_blinking.png"), (hx, hy))
        if q < health:
            part = "half" if q + 1 == health else "full"
            canvas.alpha_composite(_sprite(out, *d, f"{pre}{part}.png"), (hx, hy))


def hud_scene(out, w, h, health=20, stamina=0.7, sel=1, **kw):
    """GUI 픽셀 크기 w×h 의 화면 아래쪽 (단축 슬롯, 체력, 스태미나, 왼손 칸)."""
    small = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hud = ("sprites", "hud")
    cx = w // 2
    hx, hy = cx - 91, h - 22
    small.alpha_composite(_sprite(out, *hud, "hotbar.png"), (hx, hy))
    small.alpha_composite(_sprite(out, *hud, "hotbar_selection.png"), (hx - 1 + sel * 20, hy - 1))
    small.alpha_composite(_sprite(out, *hud, "hotbar_offhand_left.png"), (hx - 29, h - 23))
    small.alpha_composite(_sprite(out, *hud, "experience_bar_background.png"), (hx, h - 29))
    k = int(stamina * 183)
    if k:
        small.alpha_composite(_sprite(out, *hud, "experience_bar_progress.png").crop((0, 0, min(k, 182), 5)), (hx, h - 29))
    draw_hearts(small, out, hx, h - 39, health, **kw)
    return small



# ─────────────────────────── 칸 자리 증명 (바닐라와 겹쳐 보기) ───────────────────────────

VANILLA_SHADOW, VANILLA_FLOOR, VANILLA_LIP = (55, 55, 55), (139, 139, 139), (255, 255, 255)


def vanilla_jar():
    """바닐라 1.21.11 클라이언트 jar (환경 변수 SOULS_CLIENT_JAR, 없으면 실제 클라이언트 점검 틀이 받아 둔 것). 없으면 None."""
    for p in (os.environ.get("SOULS_CLIENT_JAR"), os.path.expanduser("~/.cache/souls-client/versions/1.21.11.jar")):
        if p and os.path.exists(p):
            return p
    return None


def _jar_png(z, path):
    try:
        return Image.open(z.open(path)).convert("RGBA")
    except KeyError:
        return None


def vanilla_wells(img):
    """
    바닐라 창 그림에서 칸을 찾는다: 왼쪽 위가 그늘(#373737)이고 그 안이 바닥(#8b8b8b, 인물 자리는 #000000)인 상자.
    (x, y, 폭, 높이) 목록. 폭·높이는 그늘 줄과 입술 줄까지 넣은 바깥 크기 (보통 칸 18×18).
    """
    px = img.load()
    W, H = img.size
    found = []
    for y in range(H - 2):
        for x in range(W - 2):
            if px[x, y][:3] != VANILLA_SHADOW or px[x + 1, y][:3] != VANILLA_SHADOW or px[x, y + 1][:3] != VANILLA_SHADOW:
                continue
            inner = px[x + 1, y + 1][:3]
            if inner not in (VANILLA_FLOOR, (0, 0, 0)) or px[x + 1, y + 1][3] == 0:
                continue
            fw = 0
            while px[x + 1 + fw, y + 1][:3] == inner:
                fw += 1
            fh = 0
            while px[x + 1, y + 1 + fh][:3] == inner:
                fh += 1
            if px[x + 1 + fw, y + 1][:3] == VANILLA_LIP and px[x + 1, y + 1 + fh][:3] == VANILLA_LIP:
                found.append((x, y, fw + 2, fh + 2))
    return found


def well_pixels(ours, wells, van=None):
    """
    칸마다 자리를 픽셀로 견준다. [(x, y, 맞음)] 과 어긋난 칸 목록을 돌려준다. 칸 (x, y, 폭, 높이) 에서 우리 그림의
    그늘색 S = (x, y), 입술색 L = (x+폭-1, y+높이-1), 바닥색 F = (x+1, y+1) 일 때:
      그늘 줄 (위 x..x+폭-2, 왼쪽 y..y+높이-2)        = S
      입술 줄 (아래 x+1..x+폭-1, 오른쪽 y+1..y+높이-1) = L  (L ≠ F, 불투명)
      아이템 자리 (가운데 16×16)                       = F 한 색 (S·L 이 아니다). 인물 자리 (16×16 이 아닌 큰 상자) 는 빼고
      그늘 줄 바로 바깥 (위 줄 위, 왼쪽 줄 왼쪽)        ≠ S  (어두운 줄이 꼭 1픽셀: 두껍게 번지지 않는다)
    van (바닐라 그림) 을 주면 바닐라가 그늘·입술로 칠한 픽셀만 그 줄로 보고 (인물 자리의 오른쪽 아래는 바닐라에서도
    왼손 칸이 덮는다), 바깥 줄은 바닐라에서 그늘·바닥·인물 자리 색인 픽셀 (이웃 칸의 꺾임 점) 을 뺀다.
    """
    px = ours.load()
    vx = van.load() if van is not None else None
    checks, bad = [], []
    for x, y, w, h in wells:
        S, L, F = px[x, y], px[x + w - 1, y + h - 1], px[x + 1, y + 1]
        edge = [(x + i, y) for i in range(w - 1)] + [(x, y + j) for j in range(h - 1)]
        lips = [(x + i, y + h - 1) for i in range(1, w)] + [(x + w - 1, y + j) for j in range(1, h)]
        outside = [(x + i, y - 1) for i in range(1, w - 1)] + [(x - 1, y + j) for j in range(1, h - 1)]
        if vx is not None:
            edge = [q for q in edge if vx[q][:3] == VANILLA_SHADOW]
            lips = [q for q in lips if vx[q][:3] == VANILLA_LIP]
            outside = [q for q in outside if vx[q][:3] not in (VANILLA_SHADOW, VANILLA_FLOOR, (0, 0, 0))]
        mine = [(q, px[q] == S) for q in edge]
        mine += [(q, px[q] == L and L != F and L[3] == 255) for q in lips]
        mine += [(q, px[q] != S) for q in outside]
        if w <= 26 and h <= 26:     # 칸 (18×18) 과 큰 결과 칸 (26×26): 가운데 16×16 이 아이템 자리
            ix, iy = x + (w - 16) // 2, y + (h - 16) // 2
            item = [(ix + i, iy + j) for j in range(16) for i in range(16)]
            F = px[item[0]]
            mine += [(q, px[q] == F and F not in (S, L)) for q in item]
        checks += [(q[0], q[1], ok) for q, ok in mine]
        if not all(ok for _, ok in mine):
            bad.append((x, y, w, h))
    return checks, bad


def check_wells(ours, wells, van=None):
    """어긋난 칸의 목록 (비면 모두 맞다). 무엇을 보는지는 well_pixels."""
    return well_pixels(ours, wells, van)[1]


def _outline(draw, x, y, w, h, k, col):
    draw.rectangle([x * k, y * k, (x + w) * k - 1, (y + h) * k - 1], outline=col)


def align_proof(out, preview_dir, jar):
    """
    align_<창>.png 다섯 칸: 바닐라, 우리 그림, 우리 그림 위에 바닐라 칸의 경계를 겹친 것 (청록 = 바닐라 아이템 자리 16×16
    의 바깥 경계, 자홍 = 바닐라 칸 18×18 의 바깥 경계), 두 그림을 반씩 섞은 것, 픽셀 견주기 (well_pixels 가 본 픽셀마다
    맞으면 초록 점, 어긋나면 빨간 칸). 어긋난 칸이 있으면 셋째 칸에서 그 칸을 빨갛게 칠하고 목록을 돌려준다.
    """
    from PIL import ImageDraw
    k = 4
    report = {}
    with zipfile.ZipFile(jar) as z:
        for name, L in CONTAINER_LAYOUTS.items():
            van = _jar_png(z, f"assets/minecraft/textures/gui/container/{name}.png")
            if van is None:
                continue
            ours = _sprite(out, "container", name + ".png")
            w, h = L["size"]
            wells = vanilla_wells(van)
            checks, bad = well_pixels(ours, wells, van)
            report[name] = (len(wells), bad, len(checks), sum(1 for c in checks if not c[2]))
            crop = (0, 0, w, h)
            a, b = _big(van.crop(crop), k), _big(ours.crop(crop), k)
            over = b.copy()
            d = ImageDraw.Draw(over)
            for x, y, ww, hh in wells:
                _outline(d, x, y, ww, hh, k, (255, 0, 255, 255))
                _outline(d, x + 1, y + 1, ww - 2, hh - 2, k, (0, 255, 255, 255))
            for x, y, ww, hh in bad:
                d.rectangle([x * k, y * k, (x + ww) * k - 1, (y + hh) * k - 1], fill=(255, 0, 0, 160))
            mix = Image.blend(a, b, 0.5)
            # 픽셀 견주기: 바닐라와 우리를 반씩 섞은 위에, 검사한 픽셀마다 맞으면 초록 점, 어긋나면 빨간 칸
            diff = Image.blend(a, b, 0.5).point(lambda v: v // 3)
            dd = ImageDraw.Draw(diff)
            for x, y, ok in checks:
                if ok:
                    dd.rectangle([x * k + 1, y * k + 1, x * k + k - 2, y * k + k - 2], fill=(40, 200, 90, 255))
                else:
                    dd.rectangle([x * k, y * k, x * k + k - 1, y * k + k - 1], fill=(255, 30, 30, 255))
            gap = 12
            panels = (a, b, over, mix, diff)
            sheet = Image.new("RGBA", (len(panels) * w * k + (len(panels) - 1) * gap, h * k), (12, 12, 12, 255))
            for i, im in enumerate(panels):
                sheet.alpha_composite(im, (i * (w * k + gap), 0))
            sheet.save(os.path.join(preview_dir, f"align_{name}.png"))
        # 빈 칸 그림: 16×16 안에서 테두리 상자의 가운데 (바닐라와 우리)
        icons = {}
        for n in SLOT_ICONS:
            v = _jar_png(z, f"assets/minecraft/textures/gui/sprites/container/slot/{n}.png")
            icons[n] = (_bbox_center(v), _bbox_center(slot_icon(n)))
        report["icons"] = icons
        # 단축 슬롯: 아이템 자리 (3+20k, 3) 16×16 이 우리 칸의 바닥과 같은지
        hb = _sprite(out, "sprites", "hud", "hotbar.png")
        hv = _jar_png(z, "assets/minecraft/textures/gui/sprites/hud/hotbar.png")
        hw = [(2 + 20 * i, 2, 18, 18) for i in range(9)]
        report["hotbar"] = (len(hw), check_wells(hb, hw))
        hs = _sprite(out, "sprites", "hud", "hotbar_selection.png")
        hole = [(x, y) for y in range(23) for x in range(24) if hs.getpixel((x, y))[3] == 0 and 1 <= x <= 22 and 1 <= y <= 21]
        report["selection_hole"] = (min(hole), max(hole))
        _hotbar_proof(preview_dir, hv, hb, hs, _jar_png(z, "assets/minecraft/textures/gui/sprites/hud/hotbar_selection.png"), k)
    return report


def _bbox_center(img):
    px = img.load()
    pts = [(x, y) for y in range(img.height) for x in range(img.width) if px[x, y][3]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def _hotbar_proof(preview_dir, hv, hb, hs, hsv, k):
    """align_hotbar.png: 바닐라·우리 단축 슬롯 (선택 테를 둘째 칸에), 아이템 자리 16×16 을 청록으로."""
    from PIL import ImageDraw
    rows = []
    for bar, sel in ((hv, hsv), (hb, hs)):
        im = Image.new("RGBA", (184, 24), (60, 64, 72, 255))
        im.alpha_composite(bar, (1, 1))
        im.alpha_composite(sel, (1 - 1 + 20, 0))
        big = _big(im, k)
        d = ImageDraw.Draw(big)
        for i in range(9):
            _outline(d, 1 + 3 + 20 * i, 1 + 3, 16, 16, k, (0, 255, 255, 255))
        rows.append(big)
    sheet = Image.new("RGBA", (rows[0].width, 2 * rows[0].height + 12), (12, 12, 12, 255))
    sheet.alpha_composite(rows[0], (0, 0))
    sheet.alpha_composite(rows[1], (0, rows[0].height + 12))
    sheet.save(os.path.join(preview_dir, "align_hotbar.png"))


# ─────────────────────────── 미리보기 그림 ───────────────────────────

# 창 미리보기에 놓을 바닐라 아이템 (칸 번호 → 그림, 개수). 어두운 아이템 (석탄, 부싯돌, 네더라이트) 이 칸 바닥에서
# 읽히는지도 본다
MOCK_ITEMS = {
    "inventory": {9: ("item/iron_helmet", 1), 13: ("item/bread", 24), 18: ("item/iron_sword", 1), 22: ("item/bone", 3),
                  36: ("item/flint", 5), 37: ("item/coal", 9), 38: ("item/netherite_ingot", 1), 40: ("item/rotten_flesh", 7),
                  41: ("item/stick", 2), 42: ("item/iron_axe", 1)},
    "crafting_table": {1: ("item/stick", 1), 4: ("item/stick", 1), 7: ("item/iron_ingot", 1), 14: ("item/bread", 24),
                       30: ("item/iron_sword", 1), 31: ("item/coal", 9), 32: ("item/flint", 3)},
    "generic_54": {3: ("item/rotten_flesh", 7), 13: ("item/bone", 2), 20: ("item/coal", 12), 21: ("item/flint", 4),
                   30: ("item/iron_axe", 1), 60: ("item/bread", 24), 82: ("item/iron_sword", 1), 83: ("item/netherite_ingot", 1)},
}
# 제목 글 (바닐라 언어 열쇠 container.* 를 lang 의 vanilla.container.* 가 덮는다). 미리보기는 그 글을 §7 회색으로 쓴다
TITLES = {
    "inventory": (("제작", "Crafting"),),
    "crafting_table": (("제작", "Crafting"), ("보관함", "Inventory")),
    "generic_54": (("큰 상자", "Large Chest"), ("보관함", "Inventory")),
    "generic_54/3": (("상자", "Chest"), ("보관함", "Inventory")),
}
TITLE_GRAY = (0xAA, 0xAA, 0xAA, 255)      # § 7


def chest_rows(img, rows):
    """바닐라 ContainerScreen 처럼 generic_54 를 줄 수에 맞춰 잇는다: 위 (0 .. 줄×18+16) + 아래 (126 .. 221)."""
    top = rows * 18 + 17
    out = Image.new("RGBA", (176, top + 96), (0, 0, 0, 0))
    out.alpha_composite(img.crop((0, 0, 176, top)), (0, 0))
    out.alpha_composite(img.crop((0, 126, 176, 222)), (0, top))
    return out


def _mock_container(out, name, lang, z, gui=3, rows=6):
    """
    창 하나를 GUI 배율 gui 로: 판, 아이템, 제목 글 (언어 파일이 §7 로 바꾼 회색), 인벤토리는 제작법 책 단추와 빈 칸 그림,
    고른 칸 가리킴. generic_54 는 rows 줄 상자 (3 이면 한 칸 상자).
    """
    import previews as pv
    L = CONTAINER_LAYOUTS[name]
    pw, ph = L["size"]
    panel = _sprite(out, "container", name + ".png").crop((0, 0, pw, ph))
    wells, titles, items = list(L["wells"]), list(L["titles"]), dict(MOCK_ITEMS[name])
    if name == "generic_54" and rows != 6:
        panel = chest_rows(panel, rows)
        shift = (6 - rows) * 18 + 1      # 아래 판: 그림 126 줄이 화면 rows×18+17 줄
        wells = [(x, y) for x, y in wells if y < 17 + rows * 18] + [(x, y - shift) for x, y in wells if y >= 126]
        titles = [titles[0], (titles[1][0], titles[1][1] - shift)]
        items = {(i if i < 54 else i - (6 - rows) * 9): v for i, v in items.items() if i < rows * 9 or i >= 54}
        ph = panel.height
    small = Image.new("RGBA", (pw + 8, ph + 8), (20, 19, 18, 255))
    small.alpha_composite(panel, (4, 4))
    slots = [(x + 1, y + 1) for x, y in wells]
    if L["result"]:
        rx, ry, rw, rh = L["result"][0]
        slots.append((rx + (rw - 16) // 2, ry + (rh - 16) // 2))
    if name == "inventory":
        small.alpha_composite(_sprite(out, "sprites", "recipe_book", "button.png"), (4 + 104, 4 + 61))
        icon_slots = {0: "helmet", 1: "chestplate", 2: "leggings", 3: "boots", 4: "shield"}
        for i, n in icon_slots.items():
            small.alpha_composite(_sprite(out, "sprites", "container", "slot", n + ".png"), (4 + slots[i][0], 4 + slots[i][1]))
    if name == "crafting_table":
        small.alpha_composite(_sprite(out, "sprites", "recipe_book", "button_highlighted.png"), (4 + 5, 4 + 34))
    hover = {"inventory": 20, "crafting_table": 20, "generic_54": 22}[name]
    hx, hy = slots[hover]
    small.alpha_composite(_sprite(out, "sprites", "container", "slot_highlight_back.png"), (4 + hx - 4, 4 + hy - 4))
    counts = []
    if z is not None:
        for i, (tex, n) in items.items():
            im = _jar_png(z, f"assets/minecraft/textures/{tex}.png")
            if im is not None and i < len(slots):
                small.alpha_composite(im.crop((0, 0, 16, 16)), (4 + slots[i][0], 4 + slots[i][1]))
                if n > 1:
                    counts.append((slots[i], str(n)))
    small.alpha_composite(_sprite(out, "sprites", "container", "slot_highlight_front.png"), (4 + hx - 4, 4 + hy - 4))
    big = _big(small, gui)
    key = name if rows == 6 else f"{name}/{rows}"
    for (tx, ty), text in zip(titles, TITLES[key]):
        m = pv.unifont_text(text[0 if lang == "ko" else 1], gui)
        if m is not None:
            big.paste(Image.new("RGBA", m.size, TITLE_GRAY), ((4 + tx) * gui, (4 + ty) * gui), m)
    for (sx, sy), n in counts:
        m = pv.unifont_text(n, gui)
        if m is not None:
            x, y = (4 + sx + 17) * gui - m.width, (4 + sy + 9) * gui
            big.paste(Image.new("RGBA", m.size, (63, 63, 63, 255)), (x + gui, y + gui), m)
            big.paste(Image.new("RGBA", m.size, (255, 255, 255, 255)), (x, y), m)
    return big


def write_previews(out, preview_dir):
    import previews as pv
    os.makedirs(preview_dir, exist_ok=True)
    gui = 3
    w, h = 427, 64
    states = [
        dict(health=20, stamina=1.0),
        dict(health=13, stamina=0.62, sel=3),
        dict(health=13, display=17, blink=True, stamina=0.35, sel=3),
        dict(health=3, stamina=0.08, shake=[0, 1, 1, 0, 1, 0, 0, 1, 1, 0], sel=0),
        dict(health=9, kind="poisoned", stamina=0.8, sel=5),
        dict(health=20, absorb=6, stamina=0.5, sel=8),
    ]
    rows = []
    for st in states:
        scene = pv.dusk_scene(w * gui, h * gui * 2).crop((0, h * gui, w * gui, h * gui * 2))
        scene.alpha_composite(_big(hud_scene(out, w, h, **st), gui))
        rows.append(scene)
    sheet = Image.new("RGBA", (w * gui, sum(r.height for r in rows) + 4 * (len(rows) - 1)), (12, 12, 12, 255))
    y = 0
    for rimg in rows:
        sheet.alpha_composite(rimg, (0, y))
        y += rimg.height + 4
    sheet.crop((w * gui // 2 - 330, 0, w * gui // 2 + 330, sheet.height)).save(os.path.join(preview_dir, "gui_hud.png"))

    # 확대: 체력 칸들
    zoom = Image.new("RGBA", (100, 40), (34, 33, 36, 255))
    draw_hearts(zoom, out, 4, 4, 13)
    draw_hearts(zoom, out, 4, 16, 13, display=17, blink=True)
    draw_hearts(zoom, out, 4, 28, 7, kind="poisoned")
    _big(zoom, 8).save(os.path.join(preview_dir, "gui_hearts.png"))

    # 창들 (위 줄 한국어, 아래 줄 영어 제목)
    jar = vanilla_jar()
    z = zipfile.ZipFile(jar) if jar else None
    lines = []
    for lang in ("ko", "en"):
        panels = [_mock_container(out, n, lang, z, gui) for n in CONTAINER_LAYOUTS]
        panels.append(_mock_container(out, "generic_54", lang, z, gui, rows=3))
        line = Image.new("RGBA", (sum(p.width for p in panels) + 8 * len(panels), max(p.height for p in panels)),
                         (12, 12, 12, 255))
        x = 0
        for p in panels:
            line.alpha_composite(p, (x, 0))
            x += p.width + 8
        lines.append(line)
    sheet = Image.new("RGBA", (lines[0].width, sum(l.height for l in lines) + 8), (12, 12, 12, 255))
    sheet.alpha_composite(lines[0], (0, 0))
    sheet.alpha_composite(lines[1], (0, lines[0].height + 8))
    sheet.save(os.path.join(preview_dir, "gui_containers.png"))
    if z is not None:
        z.close()

    # 단추 (사망 화면 크기 200, 일시정지 화면 크기 98·204), 설명 칸, Dialog 경고 단추
    W2, H2 = 427, 176
    canvas = pv.dusk_scene(W2 * gui, H2 * gui)
    canvas.alpha_composite(pv.death_overlay(W2 * gui, H2 * gui))
    small = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    btns = [("button", 200, 20, 3, 113, 10, "일어선다"), ("button_highlighted", 200, 20, 3, 113, 34, "그만둔다"),
            ("button_disabled", 200, 20, 1, 113, 58, "일어선다"), ("button", 98, 20, 3, 10, 90, "설정"),
            ("button_highlighted", 98, 20, 3, 112, 90, "통계"), ("button", 204, 20, 3, 214, 90, "게임으로 돌아가기")]
    for spr, bw, bh, b, bx, by, _ in btns:
        small.alpha_composite(nine_slice(_sprite(out, "sprites", "widget", spr + ".png"), bw, bh, b), (bx, by))
    for i, st in enumerate(("warning_button", "warning_button_highlighted", "warning_button_disabled")):
        small.alpha_composite(_sprite(out, "sprites", "dialog", st + ".png"), (10 + 24 * i, 120))
    # 설정 화면: 밀대 둘 (보통, 가리킴), 고름 칸 넷, 글 칸 둘, 두루마리
    wd = ("sprites", "widget")
    sliders = []
    for i, (hi, val) in enumerate(((False, 0.35), (True, 0.7))):
        sfx = "_highlighted" if hi else ""
        sx, sy = 214 + i * 104, 116
        small.alpha_composite(nine_slice(_sprite(out, *wd, "slider" + sfx + ".png"), 98, 20, 2), (sx, sy))
        small.alpha_composite(_sprite(out, *wd, "slider_handle" + sfx + ".png"), (sx + int(val * 90), sy))
        sliders.append((sx + 49, sy + 6, "시야: 70" if i == 0 else "밝기: 50%"))
    for i, n in enumerate(("checkbox", "checkbox_highlighted", "checkbox_selected", "checkbox_selected_highlighted")):
        small.alpha_composite(_sprite(out, *wd, n + ".png").resize((17, 17), Image.NEAREST), (90 + 20 * i, 121))
    small.alpha_composite(nine_slice(_sprite(out, *wd, "text_field.png"), 90, 20, 1), (10, 148))
    small.alpha_composite(nine_slice(_sprite(out, *wd, "text_field_highlighted.png"), 90, 20, 1), (110, 148))
    small.alpha_composite(_sprite(out, *wd, "scroller_background.png"), (412, 140))
    small.alpha_composite(nine_slice(_sprite(out, *wd, "scroller.png"), 6, 20, 1), (412, 146))
    tb = _sprite(out, "sprites", "tooltip", "background.png")
    tf = _sprite(out, "sprites", "tooltip", "frame.png")
    for tx, ty, tw, th in ((330, 14, 80, 30), (24, 14, 70, 60)):
        small.alpha_composite(nine_slice(tb, tw + 24, th + 24, 9), (tx - 12, ty - 12))
        small.alpha_composite(nine_slice(tf, tw + 24, th + 24, 10, True), (tx - 12, ty - 12))
    canvas.alpha_composite(_big(small, gui))
    for spr, bw, bh, b, bx, by, text in btns:
        col = (160, 160, 160) if spr == "button_disabled" else (224, 224, 224)
        pv.paste_text(canvas, text, (bx + bw // 2) * gui, (by + 6) * gui, gui, color=col)
    for cx, cy, text in sliders:
        pv.paste_text(canvas, text, cx * gui, cy * gui, gui, color=(224, 224, 224))
    pv.paste_text(canvas, "흐롤프의 미늘창", (330 + 32) * gui, 14 * gui, gui, color=(209, 195, 160))
    pv.paste_text(canvas, "녹슨 날", (330 + 20) * gui, 26 * gui, gui, color=(133, 128, 121))
    canvas.save(os.path.join(preview_dir, "gui_widgets.png"))

    # 칸 자리 증명 (바닐라 jar 가 있을 때만)
    if jar:
        report = align_proof(out, preview_dir, jar)
        for name in CONTAINER_LAYOUTS:
            n, bad, npx, badpx = report[name]
            print(f"  칸 자리 {name}: 바닐라 칸 {n}개 (인벤토리는 인물 자리 하나 포함), 어긋난 칸 {len(bad)}, "
                  f"견준 픽셀 {npx}개 중 어긋남 {badpx}" + (f" {bad}" if bad else ""))
        n, bad = report["hotbar"]
        print(f"  칸 자리 hotbar: 칸 {n}개, 어긋남 {len(bad)}, 선택 테 구멍 {report['selection_hole']}")
        for name, (v, o) in report["icons"].items():
            print(f"  빈 칸 그림 {name}: 가운데 바닐라 {v}, 우리 {o}")
        return report
    print("  (바닐라 jar 가 없어 align_*.png 를 건너뛴다)")
    return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("python3 pack/variants/gui_stone.py <팩폴더> <미리보기폴더>  (변형은 진짜 팩에 쓰지 않는다)")
    target = sys.argv[1]
    paths = build(target)
    write_previews(target, sys.argv[2])
    import artlint
    artlint.lint(paths, target)
