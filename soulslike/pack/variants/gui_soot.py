"""
변형 "soot" (그을린 쇠): gui_skin.py 를 바탕으로 창·HUD 를 다시 칠한 시안. gui_skin.py 와 같은 build(out) 를 쓴다.

말씨 (2026-10-07 사용자: "세련된다는게 그런 뜻이 아니었는데, 뭔가 거무칙칙한 느낌을 원했던 것 같기도")
  v1 은 흩뿌린 녹 점, v2 는 깨끗한 회갈색 판에 가는 청동 줄이었다. 이 시안은 대장간 연기에 그을린 무거운 쇠 상자다.
  거의 검고, 탁하고, 무겁다. 때는 아무 데나 뿌리지 않고 까닭이 있는 자리에만 앉는다:
    - 그을음 (ash0): 연기는 위로 오르므로 위 테와 위 귀가 가장 검고, 위 테 밑에 고인 그을음이 물기에 실려 줄줄이
      흘러내렸다 (손으로 길이를 정한 줄). 판 가장자리·귀는 검다. 나머지 판에는 그을음이 엷게 앉았다
      (ash0·rust0 체크 무늬: 팔레트 두 색 사이의 탁한 쇠빛). 단계는 그을음 / 엷은 그을음 둘뿐, 부드러운 그라데이션은 없다.
    - 녹물 (bronze0): 징 아래로 흘러내린 줄, 단축 줄 칸에서 새어 나와 아래 테를 타고 내린 자국, 녹슨 징.
    - 닳음: 손이 잡는 자리 (양옆 테의 가운데, 아래 테 가운데) 와 부딪히는 네 귀 덮개의 바깥 모서리만 쇠빛이 드러나고,
      가장 많이 닳은 몇 점에만 희미한 불씨빛 갈색 (bronze1). 칸 입술 (아이템을 넣고 빼는 자리) 은 닳은 갈색 (bronze0).
  층 (테 > 판 > 칸)
    테   네 변 모두 6픽셀 + 검은 홈 1픽셀. 둥글게 솟은 쇠 띠: 빛을 보는 쪽 (위·왼쪽 테의 바깥, 아래·오른쪽 테의 안쪽)
         이 두 줄 밝고 (ash1·rust1), 가운데 rust0, 빛을 등진 쪽이 검다. 귀에는 L 자 쇠 덮개 (끝이 검은 이음매로 끊긴다).
         징 (4×4) 은 손으로 자리와 상태를 골랐다: 멀쩡함, 닳아 납작함, 그을음에 덮임, 녹 번짐 둘, 빠진 구멍.
    판   엷은 그을음 막. 가장자리·귀·위쪽·흘러내린 줄은 검다
    칸   깊은 구멍: 바닥 ash0 (가장 검다), 위·왼쪽 벽 rust0, 아래·오른쪽 입술 bronze0.
         칸 묶음 둘레는 검은 홈이라 칸 격자가 판에 박힌 쇠살 (화덕 쇠살대) 처럼 보인다. 결과 칸은 입술이 더 닳았다 (bronze1)
    띠   칸 묶음 사이는 새긴 홈 대신 쇠 띠 (양 끝을 옆 테에 징으로 박았다. 띠마다 닳은 구간이 다르다)
  칸 자리는 gui_skin 과 한 픽셀도 다르지 않다 (CONTAINER_LAYOUTS, well, well_pixels 를 그대로 쓴다. 바닥 = 아이템 자리 16×16
  한 색이고, 위·왼쪽 벽 바로 바깥은 늘 검은 홈이라 벽이 꼭 한 줄로 보인다). generic_54 는 위·아래를 따로 그려 붙이므로
  옆 테의 그을음·징·닳음은 맨 위 (y < 17) 와 아래 판 (y ≥ 126) 에만 둔다.
  모든 색은 palette.c(이름) 하나에서. 하트 (마른 핏방울) 는 gui_skin 그대로.

  python3 pack/variants/gui_soot.py [팩폴더] [미리보기폴더]
"""
import json
import os
import sys
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
if PACK not in sys.path:
    sys.path.insert(0, PACK)
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

    def stamp(self, x0, y0, rows, ink):
        """기호 그림을 찍는다. 빈칸은 그대로 두고, '.' 은 투명."""
        for dy, row in enumerate(rows):
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
SOOT = "ash0"         # 그을음 (가장 검다)
PANEL = "rust0"       # 덜 그을린 쇠: 판·테 면의 바탕
FLOOR = "ash0"        # 칸 바닥: 깊은 구멍 (아이템 자리 16×16 한 색)
SHADOW = "rust0"      # 칸의 위·왼쪽 벽 (빛을 등진 벽. 바닥보다는 밝고 입술보다 어둡다)
LIP = "bronze0"       # 칸의 아래·오른쪽 입술: 아이템을 넣고 빼며 닳은 갈색
DEEP = "ash0"         # 인물 자리 바닥
GROOVE = "ash0"       # 홈 (칸 묶음 둘레, 테 안쪽)
SHEEN = "ash1"        # 닳아 드러난 쇠 모서리
EDGE_LIT = "rust1"    # 빛 받는 안쪽 모서리, 징 몸
WORN = "bronze1"      # 가장 많이 닳은 몇 점: 희미한 불씨빛 갈색 (창에서 하나뿐인 따뜻함)
RUST = "bronze0"      # 녹물, 고인 녹
# 청동 이름은 단추·선택 테 같은 작은 곳에만 남긴다
BR_DEEP, BR, BR_LIT, BR_GLINT = "bronze0", "bronze1", "bronze2", "bronze3"

LIT, MID, DARK = 0, 1, 2      # 테의 쪽: 위·왼쪽, 비스듬한 귀(오른쪽 위·왼쪽 아래), 아래·오른쪽


def ring_at(x, y, w, h, chamfer):
    """
    (x, y) 가 w×h 판의 가장자리에서 몇 번째 고리인지와 그 쪽. 귀는 chamfer 만큼 비스듬히 깎였다
    (고리마다 깎인 귀를 따라 돈다). 판 밖이면 고리 번호가 음수.
    """
    W, H = w - 1, h - 1
    return min(((y, LIT), (x, LIT), (H - y, DARK), (W - x, DARK),
                (x + y - chamfer, LIT), (W - x + y - chamfer, MID),
                (x + H - y - chamfer, MID), (W - x + H - y - chamfer, DARK)), key=lambda t: t[0])


def frame(cv, x0, y0, w, h, rings, fill, chamfer=2):
    """고리 테를 두른 판. fill 이 None 이면 고리만 그린다."""
    for y in range(h):
        for x in range(w):
            k, side = ring_at(x, y, w, h, chamfer)
            if k < 0:
                continue
            if k < len(rings):
                cv.put(x0 + x, y0 + y, rings[k][side])
            elif fill:
                cv.put(x0 + x, y0 + y, fill)


def checker(x, y, a, b):
    """반반 체크 무늬 (그을음이 엷게 앉은 자리). 늘 같은 위상이라 이웃한 자리끼리 무늬가 이어진다."""
    return a if (x + y) % 2 == 0 else b


def well(cv, x, y, w=18, h=18, floor=FLOOR, shadow=SHADOW, lip=LIP, corner=None):
    """
    패인 칸 (바닐라 칸과 같은 자리·같은 역할, 세 색). w×h 상자의 (x, y) 에서:
      위 줄 x..x+w-2 와 왼쪽 줄 y..y+h-2 는 빛을 등진 벽 (shadow)
      아래 줄 x+1..x+w-1 과 오른쪽 줄 y+1..y+h-1 은 빛 받는 입술 (lip)
      가운데 x+1..x+w-2 × y+1..y+h-2 는 바닥 (floor). 18×18 칸이면 꼭 아이템 자리 16×16 이다
    두 꺾임 (오른쪽 위, 왼쪽 아래) 은 벽과 같은 색. 칸이 붙으면 입술 한 줄 + 벽 한 줄이 2픽셀 쇠살이 된다.
    """
    corner = shadow if corner is None else corner
    cv.rect(x + 1, y + 1, x + w - 2, y + h - 2, floor)
    cv.hline(x, x + w - 2, y, shadow)
    cv.vline(x, y, y + h - 2, shadow)
    cv.hline(x + 1, x + w - 1, y + h - 1, lip)
    cv.vline(x + w - 1, y + 1, y + h - 1, lip)
    cv.put(x + w - 1, y, corner)
    cv.put(x, y + h - 1, corner)


# 징 (4×4 둥근 머리: 쇠 rust1, 왼쪽 위에 빛 한 점 ash2, 오른쪽 아래는 그늘 rust0 과 검은 그림자).
# 상태마다 다르다: 멀쩡함, 손에 닳아 납작해짐 (빛 점 없음), 그을음에 덮임 (빛 점 하나만), 녹이 번짐 (bronze0, 두 가지),
# 빠져서 검은 구멍과 녹 자국만 남음. 한 띠에 같은 징을 줄줄이 찍지 않는다.
RIVET = {
    "whole":  [".ss.", "shsK", "ssdK", ".KK."],
    "worn":   [".ss.", "sssK", "sddK", ".KK."],
    "sooted": [".dd.", "dhdK", "ddKK", ".KK."],
    "rusty":  [".sr.", "shrK", "rrdK", ".KK."],
    "rusty2": [".ss.", "shrK", "srrK", ".rK."],
    "gone":   ["....", ".KK.", ".KKr", "..r."],
}
RIVET_INK = {"h": "ash2", "s": EDGE_LIT, "d": PANEL, "K": SOOT, "r": RUST}


def rivet(cv, x, y, state="whole"):
    """(x, y) 가 4×4 의 왼쪽 위."""
    for dy, row in enumerate(RIVET[state]):
        for dx, ch in enumerate(row):
            if ch != ".":
                cv.put(x + dx, y + dy, RIVET_INK[ch])


def drip(cv, x, y, n, ok=None):
    """
    녹물 자국: (x, y) 에서 아래로 n 픽셀. 머리 두 픽셀은 녹 (RUST), 꼬리는 한 칸 걸러 녹 (마르며 끊긴다).
    ok(x, y) 가 거짓인 자리 (칸, 글) 는 건너뛴다.
    """
    for i in range(n):
        if ok and not ok(x, y + i):
            continue
        if i < 2 or (i < n - 1 and i % 2 == 0):
            cv.put(x, y + i, RUST)


def arrow(cv, x0, x1, ym, half):
    """제작 화살표 (바닐라 자리): 판에 덧댄 쇠. 위·왼쪽 가장자리는 닳은 쇠, 몸은 rust1, 아래·오른쪽은 그을음 그림자."""
    cells = set()
    head = x1 - half
    for x in range(x0, head):
        cells.update({(x, ym - 1), (x, ym), (x, ym + 1)})
    for x in range(head, x1 + 1):
        k = x1 - x
        cells.update((x, y) for y in range(ym - k, ym + k + 1))
    for x, y in cells:
        if (x, y - 1) not in cells or (x - 1, y) not in cells:
            col = SHEEN
        elif (x, y + 1) not in cells or (x + 1, y) not in cells:
            col = PANEL
        else:
            col = "rust1"
        cv.put(x, y, col)
    for x, y in cells:
        for nx, ny in ((x + 1, y), (x, y + 1), (x + 1, y + 1)):
            if (nx, ny) not in cells:
                cv.put(nx, ny, SOOT)


# ─────────────────────────── 체력: 마른 핏방울 열 개 ───────────────────────────

# 10.2: M1~M3 은 하트 10개를 마른 핏방울로 바꾼다 (이어진 막대는 M4 의 souls:hud 그림 글자 막대).
# 9×9 칸에 7×9 방울 (x 1..7). 바닐라는 하트를 8픽셀마다 그리므로 방울 사이에 한 줄(x=8, 다음 칸의 x=0)이 빈다.
# 그래서 바닐라가 칸마다 따로 흔들고(체력 4 이하) 재생 때 하나씩 튀어 올라도 방울이 떨리는 것처럼 자연스럽다.
# 그릇: 재 테두리(K), 빛을 받는 왼쪽 위 테 두 점(r), 속은 녹슨 그늘(g)에 긁힌 점 하나(a).
#       오른쪽 테 한 점이 이 빠졌다(.) — 방울 열 개가 같은 그림이라 흠은 하나만 둔다.
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
# 맞은 순간 (바닐라의 흰 테 대신) 왼쪽 위 테가 바랜 양피지빛으로 잠깐 밝아진다
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
# 속 (그릇 안쪽만). 숫자는 밝기 단계 0(가장 어두움)..3. 빛은 왼쪽 위에서 온다:
# 몸은 2, 왼쪽 위에 3 두 점 (가운데에서 비켜 난 빛), 오른쪽 아래 가장자리는 1·0 으로 한 단씩 어둡다.
# 반 칸은 아래쪽만 찬다 (병에 반쯤 남은 피처럼). 위 표면은 한 단 밝다.
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
    "blinking":  ("parch0", "parch0", "parch1", "parch2"),    # 잃은 몫: 바랜 뼈빛
    "poisoned":  ("moss0", "moss1", "moss2", "moss2"),
    "withered":  ("ash0", "ash1", "ash2", "ash3"),
    "frozen":    ("ash2", "ash3", "bone0", "bone2"),
    "absorbing": ("bronze0", "bronze1", "bronze2", "bronze3"),
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
    배경: 칸과 같은 구멍. 위 줄과 왼쪽 끝은 빛을 등진 벽 (rust0), 아래 줄과 오른쪽 끝은 닳은 입술 (bronze0),
          속은 그을음 (ash0). 네 귀는 깎였다. 자국은 없다 (늘 화면에 떠 있는 것이라 가장 조용해야 한다).
    채움: 이끼 세 줄 — 위 moss2 (빛을 받는 겉), 가운데 moss1, 아래 moss0. 바닐라가 진행만큼 왼쪽부터 잘라 그린다.
    """
    W = BAR_W
    bg = Cv(W, BAR_H)
    bg.hline(1, W - 2, 0, SHADOW)
    bg.hline(1, W - 2, BAR_H - 1, LIP)
    bg.vline(0, 1, BAR_H - 2, SHADOW)
    bg.vline(W - 1, 1, BAR_H - 2, LIP)
    bg.rect(1, 1, W - 2, BAR_H - 2, SOOT)

    fill = Cv(W, BAR_H)
    fill.hline(1, W - 2, 1, "moss2")
    fill.hline(1, W - 2, 2, "moss1")
    fill.hline(1, W - 2, 3, "moss0")
    return bg.image(), fill.image()


# ─────────────────────────── 단축 슬롯 ───────────────────────────

def hotbar():
    """
    182×22: 그을린 쇠 띠에 창과 같은 구멍 아홉 (칸 x 2+20k..19+20k, 바닥 = 아이템 자리 3+20k..18+20k).
    윗모서리는 가운데만 닳아 쇠빛 (ash1), 그 바깥은 rust1, 양 끝 스무 칸은 그을음 (칸 벽 rust0 바로 위라 rust0 은 쓰지
    않는다: 칸의 위 벽이 꼭 한 줄로 보이게). 아랫모서리는 그늘 (rust0) 이고
    물기가 고이는 양 끝에 녹 (bronze0). 칸 사이 두 줄은 쇠 기둥 (rust0) 과 그 옆 그을린 틈 (ash0).
    """
    W, H = 182, 22
    cv = Cv(W, H)
    for y in range(H):
        for x in range(W):
            k, side = ring_at(x, y, W, H, 1)
            if k < 0:
                continue
            if k == 0:
                cv.put(x, y, OUTLINE)
            elif y == 1:
                d = min(x, W - 1 - x)
                cv.put(x, y, SHEEN if d >= 46 else "rust1" if d >= 20 else SOOT)
            elif x == 1:
                cv.put(x, y, SOOT)
            elif y == H - 2:
                cv.put(x, y, RUST if (x < 12 or x > W - 13) and x % 3 != 0 else PANEL)
            elif x == W - 2:
                cv.put(x, y, PANEL)
            else:
                cv.put(x, y, PANEL if (x - 20) % 20 == 0 else SOOT)
    for k in range(9):
        well(cv, 2 + 20 * k, 2)
    return cv.image()


# 고른 칸 (24×23): 무거운 쇠 목테. 바닐라처럼 단축 슬롯보다 한 칸 왼쪽 위에서 그린다. 안쪽 4..19 는 비운다.
# O 윤곽, G 빛 받는 바깥 모서리 (rust2), g 왼쪽 위 귀의 닳은 점 (bronze2), F 면 (rust1), K 안쪽 위·왼쪽 그늘 (ash0),
# E 안쪽 아래·오른쪽 입술 (bronze1: 손이 가장 자주 닿는 테라 불씨빛으로 닳았다), d 그늘진 바깥 모서리 (rust0)
SELECTION = [
    ".OOOOOOOOOOOOOOOOOOOOOO.",
    "OggGGGGGGGGGGGGGGGGGGGdO",
    "OgFFFFFFFFFFFFFFFFFFFFdO",
    "OGFK" + "K" * 16 + "EFdO",
] + ["OGFK" + "." * 16 + "EFdO"] * 16 + [
    "OGF" + "E" * 18 + "FdO",
    "O" + "d" * 22 + "O",
    ".OOOOOOOOOOOOOOOOOOOOOO.",
]
SELECTION_INK = {"O": OUTLINE, "G": "rust2", "g": BR_LIT, "F": "rust1", "K": SOOT, "E": BR, "d": PANEL}


def hotbar_selection():
    cv = Cv(24, 23)
    cv.stamp(0, 0, SELECTION, SELECTION_INK)
    return cv.image()


def offhand(right):
    """왼손 칸 29×24. 칸 상자는 22×22 (왼쪽: x 0..21, 오른쪽: x 7..28, y 1..22), 아이템은 y 4..19. 단축 슬롯과 같은 띠."""
    W, H = 29, 24
    cv = Cv(W, H)
    x0 = 7 if right else 0
    for y in range(22):
        for x in range(22):
            k, side = ring_at(x, y, 22, 22, 1)
            if k < 0:
                continue
            col = OUTLINE if k == 0 else (SHEEN if y == 1 and 5 <= x <= 16 else SOOT) if side == LIT and k == 1 \
                else PANEL
            cv.put(x0 + x, 1 + y, col)
    well(cv, x0 + 2, 3)
    return cv.image()


# 단축 슬롯 옆 공격 대기 표시 (설정에서 "단축 슬롯" 을 고른 사람만 본다): 단검 실루엣
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
    ink = {"K": "ash0", "x": "rust0", "b": "bronze1", "B": "bronze3", "n": "bronze2", "m": "rust2", "r": "rust1"}
    bg, fg = Cv(18, 18), Cv(18, 18)
    bg.stamp(0, 0, ATTACK_BG, ink)
    fg.stamp(0, 0, ATTACK_FILL, ink)
    return bg.image(), fg.image()


# ─────────────────────────── 창 (인벤토리, 상자, 제작대) ───────────────────────────

# 바닐라 jar 의 그림과 한 픽셀씩 대조한 배치 (write_previews 의 align_*.png 가 겹쳐 보인다).
#   wells   18×18 칸의 왼쪽 위 (아이템은 +1, +1 에 16×16)
#   result  청동 테 칸 (x, y, 폭, 높이): 인벤토리의 18×18 결과 칸, 제작대의 26×26 큰 결과 칸
#   alcove  인벤토리의 인물 자리 (패인 벽감)
#   arrow   (자루 시작 x, 촉 끝 x, 가운데 y, 촉 반높이) — 바닐라 화살표와 같은 자리
#   titles  바닐라가 제목 글을 쓰는 (x, y) (AbstractContainerScreen 의 titleLabelY 6, 인벤토리는 titleLabelX 97,
#           제작대 29, "보관함" 은 inventoryLabelY = 창 높이 - 94, 상자 그림에서는 아래 판이 126 줄부터라 129).
#           그림에는 아무것도 그리지 않는다: 글은 언어 파일이 회색 (§7) 으로 바꾼다 (lang 의 vanilla.container.*, 10.4).
#           미리보기만 이 자리에 글을 쓴다
#   dividers, studs  gui_skin 의 나눔줄·귀 징 자리. 배치를 gui_skin 과 똑같이 두려고 남겼고, 이 변형은 쓰지 않는다
#           (쇠 띠·징·녹물 자리는 아래 SOOT_SPECS)
#   generic_54 는 바닐라가 위 (0 .. 17+줄×18-1) 와 아래 (126..221) 를 따로 그려 붙이므로, 양옆 테는 위아래로 고르고
#   (귀 장식은 맨 위와 맨 아래에만), 아래쪽 판은 126 줄부터 그 자체로 완결된다.
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
        "studs": [(4, 4), (171, 4), (4, 161), (171, 161)],
    },
    "crafting_table": {
        "size": (176, 166),
        "wells": _grid(29, 16, 3, 3) + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(119, 30, 26, 26)],
        "alcove": None,
        "arrow": (90, 111, 42, 7),
        "titles": [(29, 6), (8, 72)],
        "dividers": [(7, 167, 138)],
        "studs": [(4, 4), (171, 4), (4, 161), (171, 161)],
    },
    "generic_54": {
        "size": (176, 222),
        "wells": _grid(7, 17, 9, 6) + _grid(7, 139, 9, 3) + _grid(7, 197, 9, 1),
        "result": [],
        "alcove": None,
        "arrow": None,
        "titles": [(8, 6), (8, 129)],
        "dividers": [(7, 167, 194)],
        "studs": [(4, 4), (171, 4), (4, 217), (171, 217)],
    },
}


# 그을음·녹·닳음을 놓는 자리 (창마다 손으로 골랐다. 무작위가 아니다).
#   rivets  테의 징 4×4 (왼쪽 위 x, y, 상태). 위 테 y 2, 아래 테 y h-6, 왼쪽 테 x 2, 오른쪽 테 x w-6
#   drips   녹물 (x, 시작 y, 길이): 징 아래에서 판으로 흘러내린다 (칸·글 자리는 건너뛴다)
#   streaks 위 테 밑에 고인 그을음 (5줄) 에서 물기에 실려 흘러내린 검은 줄 (x, 폭, 길이). 끝 두 칸은 반반으로 끊긴다
#   seeps   칸에서 새어 나와 아래 테를 타고 흘러내린 녹물 (x, 길이)
#   wear    손이 잡아 닳은 테 구간: 변 → (시작, 끝)
#   straps  칸 묶음 사이의 쇠 띠 (빛 받는 윗줄 y, 닳아 쇠빛이 드러난 구간 x0..x1). 양 끝은 옆 테의 징에 박혔다
#   plates  가로 쇠판 (위 y, 아래 y): 상자 아래쪽 "보관함" 글이 앉는 판
# generic_54 는 위·아래를 따로 그려 붙이므로 옆 테의 징·닳음은 맨 위 (y < 17) 와 아래 판 (y ≥ 126) 에만 둔다.
SOOT_SPECS = {
    "inventory": {
        "rivets": [(2, 2, "sooted"), (30, 2, "sooted"), (58, 2, "gone"), (87, 2, "whole"), (118, 2, "rusty"),
                   (146, 2, "rusty2"), (170, 2, "sooted"),
                   (2, 79, "whole"), (170, 79, "rusty"), (2, 137, "worn"), (170, 137, "gone"),
                   (2, 160, "rusty"), (44, 160, "whole"), (95, 160, "rusty2"), (133, 160, "worn"), (170, 160, "rusty")],
        "drips": [(120, 6, 9), (148, 6, 16), (149, 6, 6), (171, 83, 9), (172, 6, 5)],
        "streaks": [(77, 2, 4), (82, 1, 9), (85, 3, 3), (92, 1, 6), (94, 2, 2), (133, 1, 17), (135, 2, 6),
                    (139, 1, 3), (143, 2, 11), (147, 1, 4), (150, 3, 2), (157, 1, 8), (161, 2, 4), (165, 3, 12)],
        "wear": {"L": (92, 126), "R": (98, 128), "B": (62, 112)},
        "seeps": [(16, 3), (53, 1), (90, 4), (126, 2), (160, 5)],
        "straps": [(80, 30, 96), (138, 58, 150)],
        "plates": [],
    },
    "crafting_table": {
        "rivets": [(2, 2, "sooted"), (31, 2, "rusty2"), (60, 2, "whole"), (88, 2, "gone"), (117, 2, "worn"),
                   (147, 2, "rusty"), (170, 2, "sooted"),
                   (2, 137, "whole"), (170, 137, "rusty"),
                   (2, 160, "rusty"), (44, 160, "worn"), (95, 160, "gone"), (133, 160, "whole"), (170, 160, "rusty2")],
        "drips": [(32, 6, 9), (148, 6, 22), (149, 6, 7), (171, 141, 8)],
        "streaks": [(7, 2, 7), (11, 1, 3), (14, 3, 12), (19, 1, 5), (23, 2, 2), (27, 1, 9),
                    (84, 2, 5), (89, 1, 13), (93, 3, 3), (100, 1, 8), (104, 2, 16), (110, 1, 4), (115, 2, 7),
                    (146, 1, 18), (149, 2, 5), (155, 1, 10), (159, 3, 3), (164, 2, 14)],
        "wear": {"L": (92, 126), "R": (98, 128), "B": (62, 112)},
        "seeps": [(15, 2), (54, 4), (91, 1), (125, 3), (161, 5)],
        "straps": [(138, 44, 128)],
        "plates": [],
    },
    "generic_54": {
        "rivets": [(2, 2, "sooted"), (31, 2, "sooted"), (60, 2, "rusty"), (88, 2, "whole"), (117, 2, "gone"),
                   (146, 2, "rusty2"), (170, 2, "sooted"),
                   (2, 130, "worn"), (170, 130, "rusty"), (2, 193, "whole"), (170, 193, "rusty2"),
                   (2, 216, "rusty"), (44, 216, "whole"), (95, 216, "rusty2"), (133, 216, "worn"), (170, 216, "rusty")],
        "drips": [(61, 6, 11), (147, 6, 11), (148, 6, 5), (171, 134, 9)],
        "streaks": [(7, 3, 4), (13, 1, 2), (29, 1, 4), (33, 2, 2), (41, 1, 3), (52, 2, 4), (57, 1, 2),
                    (70, 1, 4), (77, 3, 2), (98, 1, 3), (106, 2, 4), (121, 1, 2), (128, 2, 3), (139, 1, 4),
                    (152, 2, 2), (158, 1, 4), (163, 3, 3)],
        "wear": {"L": (148, 186), "R": (152, 188), "B": (62, 112)},
        "seeps": [(17, 2), (52, 3), (88, 5), (127, 4), (162, 1)],
        "straps": [(194, 36, 118)],
        "plates": [(127, 137)],
    },
}

BAND = 6        # 테: 고리 0 윤곽, 1..5 쇠 띠 (BAND_PROFILE). 고리 6 은 검은 홈, 7 부터 판


def _side(x, y, w, h):
    """테 위의 픽셀이 어느 변인지 ('T', 'B', 'L', 'R')."""
    d = ((y, "T"), (h - 1 - y, "B"), (x, "L"), (w - 1 - x, "R"))
    return min(d)[1]


# 변마다 그을음이 귀에서 얼마나 멀리 퍼지는지 (짙은 그을음, 반반). 연기는 위로 오르므로 위가 가장 멀다.
# 테는 솟은 쇠 띠라 판보다 덜 그을렸다 (rust0). 귀에만 그을음이 앉았고 위 귀가 가장 멀리까지 검다.
# 양옆 테의 그을음은 위 16줄, 아래 12줄 안에만 둔다 (generic_54 를 줄 수대로 잘라 붙여도 이음매가 없다).
BAND_SOOT = {"T": (30, 33), "B": (14, 16), "L": ((14, 16), (8, 10)), "R": ((14, 16), (8, 10))}
CAP = 15        # 귀 덮개: 네 귀를 감싼 무거운 쇠 덮개의 팔 길이 (테를 따라). 끝은 검은 이음매로 끊긴다
WEAR_FADE = 6


def _band_level(side, x, y, w, h):
    if side in "TB":
        heavy, half = BAND_SOOT[side]
        d = min(x, w - 1 - x)
        return 2 if d < heavy else 1 if d < half else 0
    (th, tf), (bh, bf) = BAND_SOOT[side]
    dt, db = y, h - 1 - y
    lt = 2 if dt < th else 1 if dt < tf else 0
    lb = 2 if db < bh else 1 if db < bf else 0
    return max(lt, lb)


def _wear(spec, side, x, y):
    """손이 잡는 구간이면 2, 그 둘레 WEAR_FADE 칸이면 1, 아니면 0."""
    span = spec["wear"].get(side)
    if not span:
        return 0
    a = x if side in "TB" else y
    if span[0] <= a <= span[1]:
        return 2
    return 1 if span[0] - WEAR_FADE <= a <= span[1] + WEAR_FADE else 0


def _tone(level, x, y):
    return SOOT if level == 2 else checker(x, y, SOOT, PANEL) if level == 1 else PANEL


def _plate_level(x, y, w, h, spec):
    """
    판 위의 그을음 단계 (2 그을음, 1 반반). 판 전체에 그을음이 엷게 (체크 무늬 반반: 팔레트 두 색 사이의 탁한 쇠빛)
    앉았고, 까닭 있는 자리는 검다:
      위: 연기가 올라 위 테 밑에 5줄 고였고, 거기서 그을음 물이 줄줄이 흘러내렸다 (streaks).
      옆: 3줄. 아래: 1줄. 귀: 두 변 거리의 합이 위 귀 22, 아래 귀 8 안쪽 (비스듬한 계단).
    부드러운 그라데이션은 없다. 맨 쇠 (rust0 한 색) 는 판에 없다: 닳은 쇠빛은 테의 손 닿는 자리와 칸 입술에만.
    """
    i = BAND + 1
    dl, dr, dt, db = x - i, (w - 1 - i) - x, y - i, (h - 1 - i) - y
    side = min(dl, dr)
    for sx, sw, n in spec["streaks"]:
        if sx <= x < sx + sw and dt < 5 + n:
            return 2
    reach = min(dt - 5, side - 3, db - 1, side + dt - 22, side + db - 8)
    return 2 if reach < 0 else 1


def _caps(cv, w, h):
    """
    네 귀의 쇠 덮개: 테 위에 한 겹 더 씌운 L 자 덮개. 팔 끝 (테를 따라 CAP 칸) 은 검은 이음매 한 줄로 끊기고,
    덮개 끝면이 빛 (왼쪽·위) 을 보면 그 안쪽 한 줄이 rust1 로 밝다. 덮개 면은 귀라서 그을음 그대로지만, 바깥 모서리는
    부딪히고 손에 잡혀 닳았다: 빛 쪽 (위·왼쪽) 모서리는 rust1, 그늘 쪽은 rust0, 빛을 바로 받는 왼쪽 위 귀의 깎인 면에만
    불씨빛 갈색 (bronze1).
    """
    W, H = w - 1, h - 1
    for y in range(h):
        for x in range(w):
            k, rside = ring_at(x, y, w, h, 2)
            if not 1 <= k <= BAND - 1:
                continue
            side = _side(x, y, w, h)
            if side in "TB":
                along, far = (x, W - x)
            else:
                along, far = (y, H - y)
            a = min(along, far)
            if k == 1 and a < CAP:
                corner_cut = min(x, W - x) + min(y, H - y) <= 3
                if corner_cut:
                    cv.put(x, y, WORN if rside == LIT else EDGE_LIT if rside == MID else PANEL)
                else:
                    cv.put(x, y, EDGE_LIT if side in "TL" else PANEL)
                continue
            if a == CAP:
                cv.put(x, y, OUTLINE)
            elif a == CAP - 1:
                # 덮개 끝면이 왼쪽 (오른쪽 위 덮개) 이나 위 (왼쪽 아래 덮개) 를 보면 빛을 받는다
                faces_light = (side in "TB" and far < along) or (side in "LR" and far < along)
                if faces_light:
                    cv.put(x, y, EDGE_LIT)


# 테의 단면 (고리 1..5, 바깥 → 안). 둥글게 솟은 쇠 띠: 빛을 보는 쪽 (위·왼쪽 테의 바깥, 아래·오른쪽 테의 안쪽) 이
# 두 줄 밝고 (ash1·rust1 또는 rust1), 가운데 rust0, 빛을 등진 쪽이 검다. 그을린 자리는 한 줄만 남기고 다 검다.
BAND_PROFILE = {"T": (SHEEN, EDGE_LIT, PANEL, PANEL, SOOT), "L": (SHEEN, EDGE_LIT, PANEL, PANEL, SOOT),
                "B": (SOOT, SOOT, PANEL, PANEL, EDGE_LIT), "R": (SOOT, SOOT, PANEL, PANEL, EDGE_LIT)}
BAND_SOOTY = {"T": (PANEL, SOOT, SOOT, SOOT, SOOT), "L": (PANEL, SOOT, SOOT, SOOT, SOOT),
              "B": (SOOT, SOOT, SOOT, SOOT, PANEL), "R": (SOOT, SOOT, SOOT, SOOT, PANEL)}


def _band(cv, w, h, spec):
    """테와 홈, 그리고 판 바탕 (그을음 지도)."""
    for y in range(h):
        for x in range(w):
            k, _ = ring_at(x, y, w, h, 2)
            if k < 0:
                continue
            if k == 0:
                cv.put(x, y, OUTLINE)
                continue
            if k == BAND:
                cv.put(x, y, GROOVE)
                continue
            if k > BAND:
                cv.put(x, y, _tone(_plate_level(x, y, w, h, spec), x, y))
                continue
            side = _side(x, y, w, h)
            lvl = _band_level(side, x, y, w, h)
            wear = _wear(spec, side, x, y)
            lvl = min(lvl, 2 - wear)
            clean, sooty = BAND_PROFILE[side], BAND_SOOTY[side]
            col = clean[k - 1] if lvl == 0 else sooty[k - 1] if lvl == 2 else checker(x, y, clean[k - 1], sooty[k - 1])
            if wear == 2 and k == 1 and side == "L":
                col = EDGE_LIT
            cv.put(x, y, col)
    _caps(cv, w, h)
    # 아래 테: 칸에서 새어 나온 물기가 테를 타고 흘러내린 녹 자국 (어느 칸 아래인지는 손으로 골랐다)
    for x, n in spec["seeps"]:
        for i in range(n):
            cv.put(x, h - 1 - (BAND - 1) + i, RUST if i < n - 1 or n < 3 else PANEL)
    # 가장 닳은 몇 점 (손끝이 닿는 자리의 가운데): 희미한 불씨빛
    for side, (a0, a1) in spec["wear"].items():
        mid = (a0 + a1) // 2
        for off in (-3, 0, 1, 5):
            a = mid + off
            if side == "L":
                cv.put(1, a, WORN if off in (0, 1) else EDGE_LIT)
            elif side == "R":
                cv.put(w - 1 - (BAND - 1), a, WORN if off in (0, 1) else EDGE_LIT)
            elif side == "B":
                cv.put(a, h - 1 - (BAND - 1), WORN if off in (0, 5) else EDGE_LIT)


def _strap(cv, w, y, x0, x1):
    """
    칸 묶음 사이의 쇠 띠: 위아래 검은 홈 사이에 두 줄. 윗줄은 손이 지나다니는 x0..x1 만 닳아 쇠빛 (ash1), 그 바깥은
    rust0, 양 끝 여섯 칸은 그을음. 아랫줄은 rust0 (양 끝은 그을음). 띠마다 닳은 구간이 다르다.
    """
    for x in range(BAND - 1, w - BAND + 1):
        d = min(x, w - 1 - x) - BAND
        lvl = 2 if d < 6 else 0 if x0 <= x <= x1 else 1
        cv.put(x, y - 1, GROOVE)
        cv.put(x, y, SHEEN if lvl == 0 else PANEL if lvl == 1 else SOOT)
        cv.put(x, y + 1, PANEL if lvl < 2 else SOOT)
        cv.put(x, y + 2, GROOVE)


def _plate(cv, w, y0, y1):
    """
    가로 쇠판 (상자의 "보관함" 판): 윗모서리 한 줄 (rust0, 양 끝은 그을음), 면은 판과 같은 그을음 막 (반반, 양 끝 네 칸은
    검다), 아랫줄은 그늘 (ash0). 글이 앉는 자리라 밝은 이름판처럼 보이지 않게 판보다 밝은 색을 쓰지 않는다.
    """
    for x in range(BAND - 1, w - BAND + 1):
        d = min(x, w - 1 - x) - BAND
        cv.put(x, y0, PANEL if d >= 4 else SOOT)
        for y in range(y0 + 1, y1):
            cv.put(x, y, _tone(2 if d < 4 else 1, x, y))
        cv.put(x, y1, SOOT)


def _alcove(cv, x, y, w, h):
    """인벤토리의 인물 자리: 칸과 같은 구멍이고 가장 넓다. 안은 비워 둔다 (인물이 이 자리의 그림이다)."""
    well(cv, x, y, w, h, floor=DEEP)


def _result(cv, x, y, w, h):
    """
    결과 칸: 만들어진 것이 나오는 자리라 입술이 가장 많이 닳았다 (불씨빛 갈색 bronze1), 위·왼쪽 벽도 갈색 (bronze0).
    26×26 큰 칸은 아이템 둘레에 쇠 고리를 하나 더 박았다.
    """
    well(cv, x, y, w, h, shadow=RUST, lip=WORN, corner=RUST)
    if w > 18:
        a, b = x + 3, x + w - 4
        cv.hline(a + 1, b - 1, y + 3, SHEEN)
        cv.vline(a, y + 4, y + h - 5, SHEEN)
        cv.hline(a + 1, b - 1, y + h - 4, PANEL)
        cv.vline(b, y + 4, y + h - 5, PANEL)


def _well_boxes(L):
    boxes = [(x, y, 18, 18) for x, y in L["wells"]] + list(L["result"])
    if L["alcove"]:
        boxes.append(L["alcove"])
    return boxes


def container(name):
    L = CONTAINER_LAYOUTS[name]
    spec = SOOT_SPECS[name]
    w, h = L["size"]
    cv = Cv(256, 256)
    _band(cv, w, h, spec)
    for y, x0, x1 in spec["straps"]:
        _strap(cv, w, y, x0, x1)
    for y0, y1 in spec["plates"]:
        _plate(cv, w, y0, y1)
    boxes = _well_boxes(L)
    inside = {(x + i, y + j) for x, y, bw, bh in boxes for i in range(bw) for j in range(bh)}
    # 칸 묶음 둘레의 검은 홈 (그을음과 때가 칸 가장자리에 모였다)
    for (px, py) in list(inside):
        for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1),
                       (px - 1, py - 1), (px + 1, py + 1), (px - 1, py + 1), (px + 1, py - 1)):
            if (nx, ny) not in inside and ring_at(nx, ny, w, h, 2)[0] > BAND:
                cv.put(nx, ny, GROOVE)
    if L["arrow"]:
        arrow(cv, *L["arrow"])
    # 녹물: 칸·홈·화살표·글 자리는 건너뛴다 (판과 테의 홈 위에만)
    titles = [(tx, ty, tx + 40, ty + 8) for tx, ty in L["titles"]]

    def ok(x, y):
        if (x, y) in inside or any(a <= x <= c_ and b <= y <= d for a, b, c_, d in titles):
            return False
        return cv.get(x, y) in (SOOT, PANEL, GROOVE)
    for x, y, n in spec["drips"]:
        drip(cv, x, y, n, ok)
    for x, y, st in spec["rivets"]:
        rivet(cv, x, y, st)
    if L["alcove"]:          # 칸보다 먼저: 바닐라처럼 왼손 칸이 인물 자리의 오른쪽 아래 귀를 덮는다
        _alcove(cv, *L["alcove"])
    for x, y in L["wells"]:
        well(cv, x, y)
    for box in L["result"]:
        _result(cv, *box)
    return cv.image()


# ─────────────────────────── 칸 가리킴, 빈 칸 그림 ───────────────────────────

SLOT_HIGHLIGHT_SCALING = {"type": "nine_slice", "width": 24, "height": 24, "border": 4}


def slot_highlight():
    """
    마우스가 올라간 칸 (24×24, 칸 속은 4..19). 바닐라는 반투명 흰 칠이라 어두운 창에서 튄다.
    뒤 (아이템 아래): 손이 그을음을 닦아 낸 바닥 16×16 이 쇠빛 (ash1) 으로 드러난다. 벽 (rust0) 과 입술 (bronze0) 과
    다른 색이라 드러난 네모가 꼭 아이템 자리다. 앞 (아이템 위): 칸 테두리 (3, 20) 네 귀에 쇠 꺾쇠.
    왼쪽 위만 빛을 받아 ash2, 오른쪽 위·왼쪽 아래는 rust2, 오른쪽 아래는 손때 묻은 불씨빛 갈색 (bronze1).
    """
    back, front = Cv(24, 24), Cv(24, 24)
    back.rect(4, 4, 19, 19, SHEEN)
    for (x, y, sx, sy, col) in ((3, 3, 1, 1, "ash2"), (20, 3, -1, 1, "rust2"),
                                (3, 20, 1, -1, "rust2"), (20, 20, -1, -1, WORN)):
        for i in range(3):
            front.put(x + sx * i, y, col)
            front.put(x, y + sy * i, col)
    return back.image(), front.image()


# 빈 갑옷·방패 칸에 비치는 흐린 그림 (16×16). 녹슨 쇠빛 윤곽 한 색(rust1) 으로 손으로 그렸고,
# 모두 16×16 의 가운데에 둔다 (테두리 상자의 가운데가 x 7.5, y 7.5~8.0 — 바닐라 그림과 같다).
SLOT_ICONS = {
    # 큰 투구: 둥근 정수리 (계단 귀), 눈구멍 줄, 2픽셀 콧대, 아래가 트인 볼가리개. 12줄이라 세로 가운데가 7.5
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
    # 흉갑: 어깨받이, 목 둘레, 허리로 좁아진다
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
    # 다리 갑옷: 허리띠, 갈라지는 두 다리
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
    # 장화 한 켤레: 발끝이 바깥을 본다
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
    # 방패: 위가 곧은 연 모양, 가운데 십자 띠
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
    cv.stamp(0, 0, [r.replace(".", " ") for r in SLOT_ICONS[name]], {"o": LIP})
    return cv.image()


# ─────────────────────────── 단추 ───────────────────────────

BUTTON_SCALING = {
    "button": {"type": "nine_slice", "width": 200, "height": 20, "border": 3},
    "button_highlighted": {"type": "nine_slice", "width": 200, "height": 20, "border": 3},
    "button_disabled": {"type": "nine_slice", "width": 200, "height": 20, "border": 1},
}
# 단추의 고리 (바깥 → 안). 9조각 테 3 안에 다 들어간다 (가운데는 이어 붙이거나 잘리므로 고른 판)
BUTTON_RINGS = {
    "normal": (((OUTLINE,) * 3, (SHEEN, SHEEN, SOOT)), PANEL),
    # 가리킴: 쇠 모서리가 밝아지고 안쪽에 닳은 갈색 줄이 드러난다
    "highlighted": (((OUTLINE,) * 3, ("rust2", "rust1", SOOT), (BR, BR_DEEP, BR_DEEP)), PANEL),
    # 사용 못 함: 빛도 청동도 없이 가라앉은 판
    "disabled": (((OUTLINE,) * 3,), "ash0"),
}


def button(state):
    """
    200×20 쇠판 단추. 윤곽, 베벨 한 줄 (위·왼쪽 빛, 아래·오른쪽은 윤곽과 겹쳐 두 줄 그늘), 조용한 판.
    가리키면 그 안쪽에 청동 줄이 한 바퀴 드러난다 (판의 테와 같은 말씨). 사용 못 함은 판이 한 단 가라앉는다.
    """
    W, H = 200, 20
    rings, fill = BUTTON_RINGS[state]
    cv = Cv(W, H)
    frame(cv, 0, 0, W, H, rings, fill, chamfer=1)
    return cv.image()


# 제작법 책 단추 20×18: 단추와 같은 쇠판 위에 걸쇠 채운 작은 책. 책 둘레는 단추 판보다 한 단 깊다.
# 단추 얼굴은 x 1..18, y 1..15 (가운데 9.5, 8) 이고 책은 x 5..14, y 4..12 (가운데 9.5, 8) 로 한가운데에 앉는다.
# O 윤곽, i 쇠 베벨(빛), f 판, s 그늘 베벨, k 책 그늘, b 표지 (bronze1), B 표지 윗면 빛 (bronze2),
# d 등 (bronze0), p 책장 (parch1), c 걸쇠 (bronze3)
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
    "OiffffffffffffffffsO",
    "OissssssssssssssssOO",
    "OOOOOOOOOOOOOOOOOOOO",
    ".OOOOOOOOOOOOOOOOOO.",
]


def recipe_button(hi):
    ink = {"O": OUTLINE, "i": BR_LIT if hi else "rust1", "f": PANEL, "s": BR if hi else OUTLINE, "k": OUTLINE,
           "b": BR, "B": BR_LIT, "d": BR_DEEP, "p": "parch1", "c": BR_GLINT}
    cv = Cv(20, 18)
    cv.stamp(0, 0, [r.replace(".", " ") for r in RECIPE_BUTTON], ink)
    return cv.image()


# ─────────────────────────── 설정 창의 위젯 (밀대, 고름 칸, 글 칸, 탭, 두루마리) ───────────────────────────

# 일시정지 → 설정 화면은 단추 사이에 바닐라 회색 밀대가 섞여 있었다. 같은 말씨로: 단추·손잡이는 솟은 쇠판 (위·왼쪽 빛),
# 밀대 길·고름 칸·글 칸은 판에 판 홈 (위·왼쪽 그늘, 아래·오른쪽 입술). 가리키거나 고르면 청동이 드러난다.
# 9조각 값은 우리 그림에 맞춰 우리가 정한다 (바닐라는 그림과 같은 팩의 .mcmeta 를 읽는다).
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
# 판 홈 (밀대 길, 고름 칸): 윤곽 → (위·왼쪽 그늘 / 아래·오른쪽 입술) → 판 색 바닥. 칸과 같은 얼굴이다
GROOVE_RINGS = {
    False: ((OUTLINE,) * 3, (SHADOW, SHADOW, LIP)),
    True: ((OUTLINE,) * 3, (BR_DEEP, BR_DEEP, BR_LIT)),       # 가리킴: 홈의 테가 청동으로
}


def slider_track(hi):
    """밀대 길 200×20 (9조각 테 2): 판에 판 홈. 그 위에 바닐라가 흰 글 (예: "시야: 70") 을 쓴다."""
    cv = Cv(200, 20)
    frame(cv, 0, 0, 200, 20, GROOVE_RINGS[hi], FLOOR, chamfer=1)
    return cv.image()


# 밀대 손잡이 8×20: 솟은 쇠 손잡이, 가운데에 손가락이 걸리는 홈 두 줄 (그늘 한 줄 + 빛 한 줄).
# O 윤곽, i 빛 베벨, f 얼굴, s 그늘 베벨, g 홈 그늘, l 홈 아래 빛
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
    False: {"O": OUTLINE, "i": "rust2", "f": "rust1", "s": PANEL, "g": OUTLINE, "l": "rust2"},
    True: {"O": OUTLINE, "i": BR_GLINT, "f": BR, "s": BR_DEEP, "g": OUTLINE, "l": BR_LIT},
}


def slider_handle(hi):
    cv = Cv(8, 20)
    cv.stamp(0, 0, [r.replace(".", " ") for r in HANDLE], HANDLE_TONES[hi])
    return cv.image()


# 고름 칸 20×20 (늘여 그린다: 바닐라는 글 높이에 맞춰 17×17 안팎으로 줄인다). 판 홈 + 고르면 바랜 양피지 표시.
# 표시는 2픽셀 굵기의 꺾인 획 (x 4..15, y 5..14), 아래·오른쪽에 그림자 한 줄 (k).
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
    frame(cv, 0, 0, 20, 20, GROOVE_RINGS[hi], FLOOR, chamfer=1)
    if selected:
        cv.stamp(0, 0, [r.replace(".", " ") for r in CHECK], {"C": BR_GLINT if hi else "parch2", "k": OUTLINE})
    return cv.image()


def text_field(hi):
    """글 칸 200×20 (9조각 테 1): 가장 어두운 재 바탕에 쇠 테 한 줄, 고르면 청동 테. 글 (흰색) 이 가장 잘 읽히는 바탕."""
    cv = Cv(200, 20)
    cv.rect(0, 0, 199, 19, BR_LIT if hi else "rust1")
    cv.rect(1, 1, 198, 18, "ash0")
    return cv.image()


def tab(selected, hi):
    """
    탭 130×24 (세계 만들기 화면). 바닐라처럼 고르지 않은 탭은 4줄 낮고 아래가 닫혔고, 고른 탭은 위로 솟고 아래가 트였다
    (속은 비워 아래 판이 비친다). 솟은 쇠판의 말씨: 위·왼쪽 빛, 오른쪽 그늘. 가리키면 빛 줄이 청동이 된다.
    """
    W, H = 130, 24
    cv = Cv(W, H)
    lit, dark = (BR_LIT, BR) if hi else ("rust1", PANEL)
    top = 0 if selected else 4
    cv.hline(0, W - 1, top, OUTLINE)
    cv.hline(1, W - 2, top + 1, lit)
    cv.vline(0, top, H - 1, OUTLINE)
    cv.vline(W - 1, top, H - 1, OUTLINE)
    cv.vline(1, top + 1, H - 1 if selected else H - 2, lit)
    cv.vline(W - 2, top + 1, H - 1 if selected else H - 2, dark)
    if not selected:
        cv.rect(2, top + 2, W - 3, H - 3, PANEL)
        cv.hline(0, W - 1, H - 2, lit)
        cv.hline(0, W - 1, H - 1, OUTLINE)
    return cv.image()


def scroller(background):
    """두루마리 6×32 (9조각 테 1). 막대: 솟은 쇠 (왼쪽·위 빛, 오른쪽·아래 그늘). 길: 가장 어두운 재 한 색."""
    cv = Cv(6, 32)
    if background:
        cv.rect(0, 0, 5, 31, "ash0")
    else:
        cv.rect(0, 0, 5, 31, "rust1")
        cv.hline(0, 4, 0, "rust2")
        cv.vline(0, 0, 30, "rust2")
        cv.vline(5, 0, 31, PANEL)
        cv.hline(0, 5, 31, PANEL)
    return cv.image()


# 설정 화면의 머리·발 나눔줄 (textures/gui/*_separator.png 32×2, 가로로 이어 붙인다). 바닐라는 반투명 흰 줄 + 검은 줄이라
# 쇠 단추 사이에서 회색 띠로 떴다. 창의 나눔줄과 같은 새긴 홈: 위 줄 그늘, 아래 줄 빛 받는 홈 벽.
SEPARATORS = ("header_separator", "footer_separator", "inworld_header_separator", "inworld_footer_separator")


def separator():
    cv = Cv(32, 2)
    cv.hline(0, 31, 0, GROOVE)
    cv.hline(0, 31, 1, LIP)
    return cv.image()


def widgets():
    """{파일 이름: 그림} (gui/sprites/widget/)."""
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

# 서버 창(Dialog)마다 제목 옆에 바닐라가 그리는 20×20 단추 (gui/sprites/dialog/warning_button*). 바닐라는 회색 돌 단추에
# 채도 높은 노란 세모라 창에서 가장 튀었다. 단추와 같은 쇠판에 "!" 를 새긴다 (빛 받는 왼쪽 위 획은 밝고 오른쪽 그늘).
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
    "normal":      {"O": OUTLINE, "i": "rust1", "f": PANEL, "s": OUTLINE, "P": "parch2", "p": "parch1", "k": OUTLINE},
    "highlighted": {"O": OUTLINE, "i": BR_LIT, "f": PANEL, "s": BR, "P": BR_GLINT, "p": BR_LIT, "k": OUTLINE},
    "disabled":    {"O": OUTLINE, "i": "ash0", "f": "ash0", "s": OUTLINE, "P": "ash2", "p": "ash1", "k": "ash0"},
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
    (EDGE_LIT, PANEL, PANEL),
    (OUTLINE, OUTLINE, OUTLINE),
)


def tooltip():
    """
    바닐라는 글 둘레 (x-12, y-12, 폭+24, 높이+24) 에 바탕과 테를 그린다. 글은 12픽셀 안쪽.
    바탕: 4..95 를 가장 어두운 재(ash0)로, 귀는 깎였다. 가운데(9..90)는 이어 붙여지므로 한 색.
    테: 윤곽 (4), 가는 청동 줄 (5), 안쪽 재 (6) 뿐. 장식은 빛이 닿는 왼쪽 위 귀의 청동 반짝임 한 점뿐이다
        (한 글자 설명 칸에서도 귀 장식이 칸을 차지하지 않는다). 가장자리 가운데(10..89)는 늘여지므로 고른 줄이다.
    """
    N = 100
    bg = Cv(N, N)
    frame(bg, 4, 4, N - 8, N - 8, (), "ash0", chamfer=2)
    fr = Cv(N, N)
    frame(fr, 4, 4, N - 8, N - 8, TOOLTIP_RINGS, None, chamfer=2)
    fr.put(6, 6, WORN)
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
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PACK, "resourcepack")
    paths = build(target)
    write_previews(target, sys.argv[2] if len(sys.argv) > 2 else os.path.join(target, "_preview"))
    import artlint
    artlint.lint(paths, target)
