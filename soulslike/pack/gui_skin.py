"""
바닐라 HUD·GUI 그림을 식은 가마의 톤으로 다시 그린다 (DESIGN.md 10.2, 10.4, 10.5, ART_DIRECTION.md).
gen_pack.py 가 hud.build 다음에 부른다. 스태미나 막대(경험치 막대)는 여기서 다시 그려 hud 의 것을 덮어쓴다.

그리는 것 (크기·경로·9조각 값은 1.21.11 클라이언트 jar 와 같다)
  체력      gui/sprites/hud/heart/*  9×9. 바닐라는 하트를 8픽셀마다 그리고 오른쪽 것부터 그려서,
            왼쪽 하트의 9번째 열(x=8)이 오른쪽 하트의 첫 열(x=0)을 덮는다. 그래서
              x=0      왼쪽 끝 테두리 (첫 하트에서만 보인다)
              x=1..7   한 칸의 속 (마른 피)
              x=8      칸 사이의 이음매 + 위 테의 못. 마지막 하트에서는 오른쪽 끝이 된다
            열 칸이 쇠 홈 하나로 이어진 막대가 된다 (y 1..8, 아래 한 줄을 비워 스태미나 막대와 한 줄 띈다).
            다 찬 칸은 이음매 자리(x=8)까지 가장 어두운 피로 덮어 칸 사이가 핏줄로 이어지고, 반 칸은 그 자리를 비운다.
            깜빡임(맞은 순간 잃은 몫)은 바랜 양피지빛, 독은 이끼, 시듦은 재, 얼음은 뼈·재, 흡수는 그을린 청동.
            체력이 4 이하일 때 바닐라는 칸마다 1픽셀씩 따로 흔든다 (팩으로는 못 막는다): 쇠 판이 덜컥거리는 것처럼 보인다.
  갑옷      armor_* 투명 (방어 수치를 쓰지 않는다). 허기는 hud.py 가 이미 투명하게 한다.
  스태미나  experience_bar_background / _progress 182×5. 체력 막대와 같은 녹슨 쇠 테 + 이끼와 청동이 섞인 채움.
  단축 슬롯 hotbar 182×22 (그을린 쇠틀, 그을음 칸), hotbar_selection 24×23 (그을린 청동 테),
            hotbar_offhand_left/right 29×24, hotbar_attack_indicator_background/progress 18×18 (단검).
  창        container/inventory.png, generic_54.png, crafting_table.png (256×256).
            칸과 테의 자리는 바닐라와 한 픽셀도 다르지 않다 (CONTAINER_LAYOUTS, 바닐라 jar 와 대조했다).
            칸은 깊은 쇠 구멍, 판은 그을린 쇠판 (이음매, 네 귀 꺾쇠, 못, 녹 꽃, 긁힘).
            바닐라는 창 제목을 어두운 회색(0x404040)으로 쓰므로, 제목 자리에 바랜 양피지 쪽지를 붙여 읽히게 한다.
            container/slot_highlight_back/front (마우스가 올라간 칸, 청동 꺾쇠), container/slot/{갑옷·방패} 빈 칸 그림.
  단추      widget/button, button_highlighted, button_disabled 200×20 (+ 바닐라와 같은 .mcmeta 9조각).
            사망 화면의 "일어선다 / 그만둔다" 도 이 그림이다. recipe_book/button(_highlighted) 20×18.
  설명 칸   tooltip/background, tooltip/frame 100×100 (+ .mcmeta). 그을음 바탕 + 녹슨 테, 모서리 하나는 닳았다.

손으로 찍은 것처럼
  모든 색은 palette.c(이름). 그림마다 씨앗(random.Random("gui_skin/<이름>"))이 달라 늘 같은 결과가 나온다.
  마모·못·녹은 손이 닿고 물이 고이는 자리(귀, 못 둘레, 아래 가장자리)에 몰아 두고, 같은 모양의 자국은 두 번까지만 쓴다.
  되풀이해야 하는 구조(칸 쉰여 개, 단축 슬롯 아홉 칸, 체력 열 칸)는 한 4×4 안에 색이 둘을 넘지 않게 단순하게 두고
  (artlint 의 반복 검사), 개성은 칸마다 다른 흠·띠마다 다른 줄로 낸다. 부드러운 그라데이션, 흐림, 반투명은 없다.
  남는 artlint 반복 경고는 칸 묶음의 바깥 가장자리처럼 바닐라 배치가 정한 구조에서만 나온다.

  python3 pack/gui_skin.py [팩폴더] [미리보기폴더]
      그림만 다시 그리고 미리보기(gui_hud, gui_hearts, gui_containers, gui_widgets)를 쓴다 (팩은 묶지 않는다)
"""
import json
import os
import random
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
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


def rng(name):
    return random.Random("gui_skin/" + name)


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


# ─────────────────────────── 체력: 한 줄로 이어지는 쇠 홈 ───────────────────────────

# K 재 테두리, R 빛 받은 위 테, r 닳은 위 테, h 아래 테, s 아래 테 그늘, o 못 머리, x 이음매·홈 그늘, g 빈 홈
# 막대는 y 1..8 (8줄): 테두리, 위 테, 속 넉 줄 (y 3..6), 아래 테, 테두리. 아래 테두리(y 8)와 스태미나 막대 사이는 한 줄 빈다.
HEART_INK = {"K": "ash0", "R": "rust2", "r": "rust1", "h": "rust1", "s": "rust0", "o": "rust3",
             "x": "ash0", "g": "rust0", "L": "rust3", "B": "parch0"}
HEART_CONTAINER = [
    ".........",
    ".KKKKKKKK",
    "KRRRRrRRo",
    "Kxxxxxxxx",
    "Kgggggggx",
    "Kgggggggx",
    "Kgggggggx",
    "Khhhhshhs",
    ".KKKKKKKK",
]
# 맞은 순간 (바닐라의 흰 테 대신) 테가 잠깐 밝아진다
HEART_CONTAINER_BLINK = [
    ".........",
    ".KKKKKKKK",
    "KLLLLRLLB",
    "Kxxxxxxxx",
    "Kgggggggx",
    "Kgggggggx",
    "Kgggggggx",
    "KRRRRhRRh",
    ".KKKKKKKK",
]
# 속 (x=1..8, y=3..6). 숫자는 밝기 단계 0(가장 어두움)..3. 칸마다 같은 무늬가 되풀이되므로 튀는 밝은 점은 두지 않는다.
# x=8 은 이음매 자리: 다 찬 칸은 그 줄을 가장 어두운 피로 덮어, 칸 사이가 끊기지 않고 핏줄 하나로 이어진다.
# 반 칸은 x=8 을 비워 두어 그릇의 재빛 이음매가 끝을 막는다.
HEART_FULL = [
    "11211110",
    "22222120",
    "21222210",
    "11101110",
]
HEART_HALF = [
    "1120",
    "2220",
    "211.",
    "110.",
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
                cv.put(1 + dx, 3 + dy, tones[int(ch)])
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


def _spans(cv, y, spans, col):
    for x, n in spans:
        cv.hline(x, x + n - 1, y, col)


def stamina_bar():
    """
    배경: 체력 막대와 같은 말씨. 위 테 rust2 (닳은 곳 rust1), 빈 홈 ash0 (그을음 몇 점 rust0), 아래 테 rust1 (그늘 rust0).
          양 끝은 재 테두리. 못은 고르지 않은 간격에 다섯, 하나는 빠져 구멍만 남았다.
    채움: 이끼에 그을린 청동이 섞인 세 줄. 위 줄은 청동 빛이 군데군데, 가운데는 이끼, 아래는 짙은 이끼.
    """
    W = BAR_W
    bg = Cv(W, BAR_H)
    bg.hline(1, W - 2, 0, "rust2")
    bg.hline(1, W - 2, 1, "ash0")
    bg.hline(1, W - 2, 2, "ash0")
    bg.hline(1, W - 2, 3, "ash0")
    bg.hline(1, W - 2, 4, "rust1")
    _spans(bg, 0, [(5, 3), (23, 6), (51, 2), (70, 9), (104, 4), (131, 2), (149, 7), (171, 3)], "rust1")
    _spans(bg, 2, [(38, 1), (140, 2)], "rust0")
    _spans(bg, 3, [(61, 3)], "rust0")
    _spans(bg, 4, [(8, 5), (33, 2), (57, 8), (86, 3), (112, 6), (144, 2), (157, 9), (176, 3)], "rust0")
    # 못: (x, 모양). 같은 모양을 두 번 쓰지 않는다
    for x, kind in ((14, "round"), (49, "flat"), (93, "hole"), (126, "bleed"), (166, "round2")):
        if kind == "round":
            bg.put(x, 0, "rust3"); bg.put(x + 1, 0, "rust1"); bg.put(x, 1, "rust0")
        elif kind == "round2":
            bg.put(x, 0, "rust3"); bg.put(x - 1, 0, "rust3"); bg.put(x + 1, 0, "rust0")
        elif kind == "flat":
            bg.put(x, 0, "rust3"); bg.put(x, 4, "rust2")
        elif kind == "hole":
            bg.put(x, 0, "ash0"); bg.put(x + 1, 0, "rust1")
        elif kind == "bleed":
            bg.put(x, 0, "rust3"); bg.put(x, 1, "rust1"); bg.put(x, 2, "rust1"); bg.put(x + 1, 2, "rust0")
    # 양 끝: 왼쪽은 둥글게, 오른쪽은 위 귀가 떨어져 나갔다
    for y, col in enumerate((None, "ash0", "ash0", "ash0", None)):
        bg.put(0, y, col)
    for y, col in enumerate((None, "ash0", "ash0", "ash0", "ash0")):
        bg.put(W - 1, y, col)
    bg.put(W - 2, 0, None)

    fill = Cv(W, BAR_H)
    fill.hline(1, W - 2, 1, "moss2")
    fill.hline(1, W - 2, 2, "moss1")
    fill.hline(1, W - 2, 3, "moss0")
    _spans(fill, 1, [(9, 6), (33, 3), (61, 9), (97, 4), (128, 7), (158, 5)], "moss1")
    _spans(fill, 1, [(44, 3), (113, 2), (171, 3)], "bronze2")
    _spans(fill, 2, [(18, 9), (52, 6), (84, 11), (139, 8)], "moss2")
    _spans(fill, 2, [(70, 3), (150, 2)], "bronze1")
    _spans(fill, 3, [(26, 5), (105, 7), (165, 6)], "moss1")
    return bg.image(), fill.image()


# ─────────────────────────── 단축 슬롯 ───────────────────────────

def rivet(cv, x, y, kind):
    """2×2 못 머리 (빛은 왼쪽 위)."""
    if kind == "round":
        cv.put(x, y, "rust3"); cv.put(x + 1, y, "rust2"); cv.put(x, y + 1, "rust2"); cv.put(x + 1, y + 1, "rust0")
    elif kind == "flat":
        cv.put(x, y, "rust2"); cv.put(x + 1, y, "rust2"); cv.put(x, y + 1, "rust1"); cv.put(x + 1, y + 1, "rust0")
    elif kind == "hole":
        cv.put(x, y, "ash0"); cv.put(x + 1, y, "rust0"); cv.put(x, y + 1, "rust0")
    elif kind == "bleed":
        cv.put(x, y, "rust3"); cv.put(x + 1, y, "rust1"); cv.put(x, y + 1, "rust1"); cv.put(x + 1, y + 1, "bronze0")
    elif kind == "small":
        cv.put(x, y, "rust3"); cv.put(x + 1, y + 1, "rust0")
    elif kind == "sunk":
        cv.put(x, y, "rust0"); cv.put(x + 1, y, "rust2"); cv.put(x, y + 1, "rust2"); cv.put(x + 1, y + 1, "rust2")
    elif kind == "bright":
        cv.put(x, y, "rust3"); cv.put(x + 1, y, "rust3"); cv.put(x, y + 1, "rust2"); cv.put(x + 1, y + 1, "rust0")
    elif kind == "split":
        cv.put(x, y, "rust3"); cv.put(x + 1, y, "ash0"); cv.put(x, y + 1, "rust2"); cv.put(x + 1, y + 1, "rust0")


def hotbar():
    """
    182×22. 그을린 쇠틀(rust1) 하나에 아홉 칸이 뚫렸고 칸 속은 가장 어두운 재(ash0).
    틀의 모양은 길게 이어지는 빛 줄 대신 띠마다 다른 짧은 빛·그늘 줄, 모양이 다 다른 못, 고르지 않은 닳음으로 낸다.
    (같은 무늬를 복사하지 않는다: 같은 못·같은 자국은 두 번까지)
    """
    W, H = 182, 22
    r = rng("hotbar")
    cv = Cv(W, H)
    cv.rect(1, 1, W - 2, H - 2, "rust1")
    cv.hline(1, W - 2, 0, "ash0")
    cv.hline(1, W - 2, H - 1, "ash0")
    cv.vline(0, 1, H - 2, "ash0")
    cv.vline(W - 1, 1, H - 2, "ash0")
    for k in range(9):
        cv.rect(3 + 20 * k, 3, 18 + 20 * k, 18, "ash0")
    # 띠마다 다른 줄 하나: (띠 안의 열, 시작 줄, 길이, 색). 열과 색의 짝이 다 다르다
    strokes = [(1, 4, 6, "rust2"), (0, 9, 7, "rust2"), (2, 3, 5, "rust0"), (3, 11, 6, "rust0"),
               (1, 12, 5, "rust3"), (0, 3, 4, "rust0"), (2, 8, 7, "rust2"), (3, 5, 5, "bronze0")]
    order = list(range(8))
    r.shuffle(order)
    for k, i in enumerate(order):
        col, y0, n, c_ = strokes[i]
        cv.vline(19 + 20 * k + col, y0, y0 + n - 1, c_)
    # 못: 띠마다 있기도 없기도 하다. 같은 모양은 두 번까지
    rivets = [(20, 1, "round"), (40, 17, "flat"), (61, 1, "bleed"), (80, 1, "small"), (100, 17, "round"),
              (121, 1, "sunk"), (140, 17, "split"), (160, 1, "bright"), (1, 1, "flat"), (W - 3, 17, "hole"),
              (100, 1, "small")]
    for x, y, kind in rivets:
        rivet(cv, x, y, kind)
    # 위 테의 닳은 자리와 아래 테의 그을음 (같은 색은 두 번까지, 길이는 다 다르다)
    top = [(5, "rust2"), (9, "rust2"), (2, "rust0"), (3, "rust0"), (1, "rust3"), (4, "bronze0")]
    for x, (n, c_) in zip(r.sample(range(5, W - 12), len(top)), top):
        cv.hline(x, x + n - 1, 1, c_)
    low = [(6, "rust0"), (3, "rust0"), (2, "ash0"), (5, "ash0")]
    for x, (n, c_) in zip(r.sample(range(5, W - 10), len(low)), low):
        cv.hline(x, x + n - 1, H - 2, c_)
    # 칸 몇 곳의 흠: 안벽 귀퉁이가 깨져 쇠가 드러났다
    for k, (dx, dy, c_) in zip(r.sample(range(9), 4), ((0, 0, "rust0"), (15, 15, "rust0"), (0, 15, "bronze0"), (15, 0, "rust2"))):
        cv.put(3 + 20 * k + dx, 3 + dy, c_)
    # 이 빠진 테두리 (안쪽 쇠가 드러난다)
    for x, y in ((37, 0), (38, 0), (116, H - 1), (0, 13)):
        cv.put(x, y, "rust0")
    return cv.image()


def hotbar_selection():
    """
    그을린 청동 테 (24×23). 안쪽 16×16 은 비운다.
    바깥 bronze1, 가운데 빛 줄 (위·왼쪽 bronze2 에 닳아 드러난 bronze3 몇 점, 아래·오른쪽 bronze1), 안쪽 그늘 bronze0.
    청동 녹(이끼색)이 오른쪽 아래 귀와 왼쪽 띠 아래에 피었다. 왼쪽 위 테두리 한 칸은 떨어져 나갔다.
    """
    W, H = 24, 23
    cv = Cv(W, H)
    cv.hline(1, W - 2, 0, "ash0")
    cv.hline(1, W - 2, H - 1, "ash0")
    cv.vline(0, 1, H - 2, "ash0")
    cv.vline(W - 1, 1, H - 2, "ash0")
    # 바깥 줄
    cv.hline(1, W - 2, 1, "bronze1")
    cv.vline(1, 1, H - 2, "bronze1")
    cv.vline(W - 2, 1, H - 2, "bronze1")
    cv.hline(1, W - 2, H - 2, "bronze0")
    # 가운데 빛 줄
    cv.hline(2, W - 3, 2, "bronze2")
    cv.vline(2, 2, H - 3, "bronze2")
    cv.vline(W - 3, 3, H - 3, "bronze1")
    cv.hline(3, W - 3, H - 3, "bronze1")
    # 안쪽 그늘 (아래는 두 줄뿐이라 안쪽 줄이 없다)
    cv.hline(3, W - 4, 3, "bronze0")
    cv.vline(3, 3, H - 4, "bronze0")
    cv.vline(W - 4, 4, H - 4, "bronze0")
    # 닳아 드러난 밝은 청동: 손가락이 닿는 위 가운데와 왼쪽 위 귀
    for x, y in ((3, 2), (4, 2), (9, 2), (10, 2), (11, 2), (16, 2), (2, 4), (2, 5), (2, 11)):
        cv.put(x, y, "bronze3")
    cv.put(2, 2, "parch1")
    # 녹
    for x, y, col in ((W - 2, H - 3, "moss0"), (W - 3, H - 3, "moss1"), (W - 3, H - 2, "moss0"),
                      (W - 4, H - 3, "moss0"), (W - 2, H - 4, "moss1"), (W - 3, H - 4, "moss0"),
                      (1, 14, "moss0"), (2, 15, "moss1"), (1, 15, "moss1"), (2, 16, "moss0"),
                      (8, 1, "moss0"), (13, H - 3, "moss0")):
        cv.put(x, y, col)
    # 찍힌 자국: 위 띠 가운데 한 곳이 눌려 그늘졌다
    cv.put(14, 1, "bronze0"); cv.put(14, 2, "bronze1")
    # 이 빠진 귀
    cv.put(1, 0, None)
    cv.put(1, 1, "ash0")
    cv.put(W - 1, H - 2, "bronze0")
    cv.put(W - 2, H - 1, None)
    return cv.image()


def offhand(right):
    """왼손 칸 29×24. 칸 상자는 22×22 (왼쪽: x 0..21, 오른쪽: x 7..28), 아이템은 y 4..19. 단축 슬롯과 같은 쇠틀."""
    W, H = 29, 24
    cv = Cv(W, H)
    x0 = 7 if right else 0
    x1 = x0 + 21
    cv.rect(x0 + 1, 2, x1 - 1, H - 3, "rust1")
    cv.hline(x0 + 1, x1 - 1, 1, "ash0")
    cv.hline(x0 + 1, x1 - 1, H - 2, "ash0")
    cv.vline(x0, 2, H - 3, "ash0")
    cv.vline(x1, 2, H - 3, "ash0")
    cv.rect(x0 + 3, 4, x0 + 18, 19, "ash0")
    if right:
        rivet(cv, x0 + 1, 2, "round")
        rivet(cv, x1 - 2, H - 5, "hole")
        cv.vline(x0 + 1, 8, 12, "rust2")
        cv.hline(x0 + 9, x0 + 12, 2, "rust2")
        cv.put(x1, 9, "rust0")
    else:
        rivet(cv, x0 + 1, 2, "flat")
        rivet(cv, x1 - 2, H - 5, "bleed")
        cv.vline(x0 + 1, 10, 15, "rust2")
        cv.hline(x0 + 6, x0 + 8, 2, "rust2")
        cv.put(x0 + 16, 2, "rust3")
        cv.put(x0 + 11, H - 2, "rust0")
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

# 바닐라 jar 의 그림과 역할(테두리, 빛, 그늘, 칸)을 한 픽셀씩 대조해 맞춘 배치.
#   slots: 18×18 칸 상자의 왼쪽 위, boxes: (x, y, 폭, 높이, 속) 큰 상자, arrow: (화살촉 x, 가운데 y, 반높이)
#   labels: 바닐라가 제목 글(0x404040)을 쓰는 자리 (x, y) 와 쪽지의 폭
def _grid(x0, y0, cols, rows):
    return [(x0 + 18 * i, y0 + 18 * j) for j in range(rows) for i in range(cols)]


CONTAINER_LAYOUTS = {
    "inventory": {
        "size": (176, 166),
        "slots": [(7, 7 + 18 * i) for i in range(4)] + [(76, 61)] + _grid(97, 17, 2, 2) + [(153, 27)]
                 + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "boxes": [(25, 7, 51, 72, "model")],
        "arrow": (144, 35, 6),
        "labels": [(97, 8, 42)],
        "seams": [80, 138],
        "rivets": [((4, 4), "round"), ((170, 4), "flat"), ((4, 160), "hole"), ((170, 160), "bleed"),
                   ((60, 80), "small"), ((141, 81), "round"), ((95, 138), "flat")],
    },
    "crafting_table": {
        "size": (176, 166),
        "slots": _grid(29, 16, 3, 3) + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "boxes": [(119, 30, 26, 26, "well")],
        "arrow": (104, 42, 7),
        "labels": [(29, 6, 42), (8, 72, 48)],
        "seams": [138],
        "rivets": [((4, 4), "flat"), ((170, 4), "round"), ((4, 160), "bleed"), ((170, 160), "round"),
                   ((159, 70), "small"), ((88, 138), "round")],
    },
    "generic_54": {
        "size": (176, 222),
        "slots": _grid(7, 17, 9, 6) + _grid(7, 139, 9, 3) + _grid(7, 197, 9, 1),
        "boxes": [],
        "arrow": None,
        "labels": [(8, 6, 62), (8, 129, 48)],
        "seams": [134, 194],
        "rivets": [((170, 5), "round"), ((4, 216), "flat"), ((170, 216), "hole"),
                   ((150, 131), "round"), ((118, 194), "bleed")],
    },
}


def _panel(cv, w, h, base):
    """
    바닐라 창 판의 바깥 모양(둥근 귀)을 따른다. 빛 받은 위·왼쪽 테는 한 줄(rust2), 그늘진 아래·오른쪽은 재 두 줄.
    긴 테가 한 4×4 안에 세 색을 넘지 않게 단순하게 둔다 (artlint 되풀이 검사, 마모는 따로 얹는다).
    """
    K = "ash0"
    cv.hline(2, w - 4, 0, K)
    cv.put(1, 1, K); cv.hline(2, w - 4, 1, "rust2"); cv.put(w - 3, 1, K)
    cv.put(0, 2, K); cv.put(1, 2, "rust2"); cv.hline(2, w - 4, 2, base); cv.put(w - 3, 2, K); cv.put(w - 2, 2, K)
    for y in range(3, h - 3):
        cv.put(0, y, K); cv.put(1, y, "rust2")
        cv.hline(2, w - 4, y, base)
        cv.put(w - 3, y, K); cv.put(w - 2, y, K); cv.put(w - 1, y, K)
    cv.put(1, h - 3, K); cv.hline(2, w - 2, h - 3, K); cv.put(w - 1, h - 3, K)
    cv.put(2, h - 2, K); cv.hline(3, w - 3, h - 2, K); cv.put(w - 2, h - 2, K)
    cv.hline(3, w - 3, h - 1, K)


def _inset(cv, x, y, w, h, kind="well"):
    """
    움푹 팬 칸 (바닐라 칸과 같은 자리). 깊은 쇠 구멍: 바닥은 rust0, 빛이 왼쪽 위에서 들어 위·왼쪽 안벽 세 줄은 그늘(ash0).
    아래·오른쪽 입술은 바닥과 같은 색이라 칸 사이가 그늘 줄로만 갈린다.
    (한 4×4 안에 색이 둘뿐이게 해 칸이 쉰 개 넘게 되풀이되어도 무늬 복사로 세지 않는다)
    """
    cv.rect(x, y, x + w - 1, y + h - 1, "rust0")
    cv.rect(x, y, x + w - 1, y + 2, "ash0")
    cv.rect(x, y, x + 2, y + h - 1, "ash0")
    if kind == "model":
        _niche(cv, x + 1, y + 1, x + w - 2, y + h - 2)


# 칸마다 하나씩 얹는 흠 (입술 위의 자리 i, 모양). 같은 모양은 두 번까지만 쓴다 (세 번이면 복사한 무늬로 보인다)
SLOT_FLAWS = (
    ("chip", ("ash0",)), ("chip", ("ash0", "ash0")), ("glint", ("rust2",)), ("glint", ("rust3", "rust2")),
    ("stain", ("bronze0",)), ("stain", ("bronze0", "rust0")), ("chip", ("rust0", "ash0", "ash0")),
    ("glint", ("rust2", "rust2", "rust3")), ("stain", ("rust0",)), ("chip", ("rust0",)),
)


def _slot_flaws(cv, slots, r):
    """칸 몇 개에만 흠을 하나씩: 아래 입술이나 오른쪽 입술의 한 자리. 모양마다 두 번까지."""
    picks = r.sample(range(len(slots)), min(len(slots), 2 * len(SLOT_FLAWS)))
    for n, i in enumerate(picks):
        _, cols = SLOT_FLAWS[n % len(SLOT_FLAWS)]
        x, y = slots[i]
        along = r.randint(3, 17 - len(cols) - 2)
        if n % 2:
            for k, col in enumerate(cols):
                cv.put(x + along + k, y + 17, col)
        else:
            for k, col in enumerate(cols):
                cv.put(x + 17, y + along + k, col)


def _niche(cv, x0, y0, x1, y1):
    """인물 그림 자리: 위가 둥근 돌 벽감. 둥근 귀 바깥은 벽(rust0), 안은 가장 어두운 재."""
    cv.rect(x0, y0, x1, y1, "ash0")
    R = 9
    for y in range(y0, y0 + R):
        for x in range(x0, x1 + 1):
            dx = max(x0 + R - x, x - (x1 - R), 0)
            dy = y0 + R - y
            d2 = dx * dx + dy * dy
            if dx > 0 and d2 > R * R:
                cv.put(x, y, "rust0")
            elif dx > 0 and d2 > (R - 1) * (R - 1) + 2:
                cv.put(x, y, "rust1" if x < (x0 + x1) // 2 else "ash1")
    # 바닥 돌 (가장 아래 두 줄) 과 금 하나
    cv.hline(x0, x1, y1, "rust0")
    cv.hline(x0 + 3, x1 - 6, y1 - 1, "ash1")
    cv.hline(x0 + 9, x0 + 12, y1 - 1, "rust0")


def _arrow(cv, xh, ym, half):
    """제작 화살표 (바닐라와 같은 자리). 몸은 rust2, 윗면 rust3, 아랫면 그늘 rust0."""
    cells = set()
    shaft_start = {6: 135, 7: 90}[half]
    for y in range(ym - half, ym + half + 1):
        dy = abs(y - ym)
        if dy <= 1:
            end = xh + half - (1 if dy else 0)
            for x in range(shaft_start, end + 1):
                cells.add((x, y))
        else:
            for x in range(xh, xh + half + 1 - dy):
                cells.add((x, y))
    for x, y in cells:
        above, below = (x, y - 1) in cells, (x, y + 1) in cells
        cv.put(x, y, "rust3" if not above else ("rust0" if not below else "rust2"))
    # 녹 한 점, 이 빠진 화살촉 끝
    cv.put(shaft_start + 3, ym, "rust1")
    cv.put(shaft_start + 4, ym + 1, "bronze0")


def _plaque(cv, x, y, w, r, base="parch1"):
    """
    제목 쪽지: 바랜 양피지 한 장을 녹슨 못 하나로 박았다. 바닐라가 제목을 어두운 회색(0x404040)으로 쓰므로
    어두운 판 위에서도 읽히게 하는 자리다. 글자는 y..y+7 에 쓰이므로 쪽지는 y-2..y+8.
    오른쪽 끝은 찢겨 줄마다 길이가 다르고 찢긴 결(parch0)이 남았다. 아래 가장자리는 군데군데 들떠 그늘이 진다.
    얼룩은 글이 오지 않는 오른쪽 꼬리에만 둔다.
    """
    edge = "parch0"
    x0, y0, y1 = x - 3, y - 2, y + 8
    tear = [0, 0, 1, 1, 0, 2, 2, 1, 0, 1, 1]
    r.shuffle(tear)
    ends = [x + w - t for t in tear]
    for i, yy in enumerate(range(y0, y1 + 1)):
        cv.hline(x0, ends[i], yy, base)
        cv.put(ends[i], yy, edge)
        if i % 3 != 1:
            cv.put(ends[i] + 1, yy, "ash0")          # 찢긴 끝 뒤의 그늘 (군데군데)
    cv.put(x0, y0, None)
    cv.put(x0, y1, edge)
    # 들뜬 아래 가장자리: 그늘 몇 토막 (길이가 다 다르다)
    gx = x0 + 2
    for n in r.sample((2, 3, 5, 6, 8), 5):
        if gx + n >= ends[-1]:
            break
        cv.hline(gx, gx + n - 1, y1 + 1, "ash0")
        gx += n + r.randint(3, 7)
    nx = x0 + r.randint(8, max(9, w // 2))
    cv.put(nx, y1, None)
    # 꼬리 쪽 얼룩 하나 (손때)
    sx = ends[3] - r.randint(4, 7)
    cv.put(sx, y0 + 3, edge); cv.put(sx + 1, y0 + 3, edge); cv.put(sx, y0 + 4, edge)
    # 못과 녹물
    cv.put(x0 + 1, y0 + 1, "rust3"); cv.put(x0 + 2, y0 + 1, "rust1"); cv.put(x0 + 1, y0 + 2, "rust0")
    cv.put(x0 + 1, y0 + 3, "bronze1")


def _scratch(cv, x, y, n, dx, slope, ok, deep=False):
    """
    긁힘: 거의 가로로 길게 그은 금. slope 칸마다 한 줄 내려간다. 얕은 금은 rust1 (판보다 조금 따뜻할 뿐),
    깊은 금은 밝은 쇠(ash2)가 드러나고 그 아래 한두 점 그늘이 진다. ok(x, y) 가 참인 자리에만.
    """
    for i in range(n):
        px, py = x + i * dx, y + i // slope
        if not ok(px, py):
            continue
        cv.put(px, py, "ash2" if deep and 1 < i < n - 2 else "rust1")
        if deep and i % 4 == 2 and ok(px, py + 1):
            cv.put(px, py + 1, "ash0")


def _bloom(cv, x, y, n, r, ok, col="rust1", core="bronze0"):
    """녹 꽃: 한 점에서 n 걸음 걷는 덩어리. 가운데는 더 짙다."""
    cells = [(x, y)]
    for _ in range(n):
        bx, by = r.choice(cells)
        nx, ny = bx + r.choice((-1, 0, 1)), by + r.choice((-1, 0, 0, 1))
        if ok(nx, ny):
            cells.append((nx, ny))
    for px, py in cells:
        if ok(px, py):
            cv.put(px, py, col)
    if ok(x, y):
        cv.put(x, y, core)


def _corner_strap(cv, x, y, sx, sy, arm_x, arm_y, ok, kind):
    """
    판 귀의 쇠 꺾쇠: 귀 (x, y) 에서 가로로 arm_x, 세로로 arm_y 칸 뻗는 두 줄 띠.
    바깥 줄은 빛(rust2), 안쪽 줄은 rust1, 띠 끝은 그늘(rust0). 귀에 못 하나 (kind).
    """
    for i in range(arm_x):
        for j, col in ((0, "rust2"), (1, "rust1")):
            px, py = x + sx * i, y + sy * j
            if ok(px, py):
                cv.put(px, py, col if i < arm_x - 1 else "rust0")
    for i in range(arm_y):
        for j, col in ((0, "rust2"), (1, "rust1")):
            px, py = x + sx * j, y + sy * i
            if ok(px, py):
                cv.put(px, py, col if i < arm_y - 1 else "rust0")
    rx, ry = (x if sx > 0 else x - 1), (y if sy > 0 else y - 1)
    rivet(cv, rx, ry, kind)


def container(name):
    L = CONTAINER_LAYOUTS[name]
    r = rng("container/" + name)
    w, h = L["size"]
    base = "ash1"
    cv = Cv(256, 256)
    _panel(cv, w, h, base)

    def free(x, y):
        return cv.get(x, y) == base

    # 판의 이음매: 두 쇠판이 맞닿은 홈 한 줄 (ash0). 홈이 끝나는 곳은 조금 벌어졌다
    for sy in L["seams"]:
        for x in range(2, w - 3):
            if free(x, sy):
                cv.put(x, sy, "ash0")
        cv.put(2, sy + 1, "ash0")
    # 칸과 상자
    for x, y in L["slots"]:
        _inset(cv, x, y, 18, 18)
    for x, y, bw, bh, kind in L["boxes"]:
        _inset(cv, x, y, bw, bh, kind)
    _slot_flaws(cv, L["slots"], r)
    if L["arrow"]:
        _arrow(cv, *L["arrow"])

    # 녹 꽃, 긁힘: 빈 판 자리에만. 상자 화면은 줄 수에 따라 판이 잘려 이어지므로 (y 17..138 의 양옆)
    # 그 사이 양옆 가장자리에는 아무것도 두지 않는다.
    def plain(x, y):
        if not free(x, y):
            return False
        if name == "generic_54" and 17 <= y <= 138 and (x < 7 or x > 168):
            return False
        return True

    spots = [(x, y) for y in range(3, h - 3) for x in range(3, w - 3) if plain(x, y)]
    for _ in range(9):
        x, y = r.choice(spots)
        _bloom(cv, x, y, r.randint(4, 10), r, plain)
    for i in range(6):
        x, y = r.choice(spots)
        _scratch(cv, x, y, r.randint(7, 15), r.choice((1, -1)), r.choice((3, 4, 6)), plain, deep=i < 2)
    # 아래 가장자리 그을음: 길이가 다 다른 얼룩 (재가 판 위로 번졌다)
    for x, n in zip(r.sample(range(6, w - 14), 6), (2, 3, 5, 7, 4, 6)):
        for i in range(n):
            if plain(x + i, h - 4):
                cv.put(x + i, h - 4, "ash0")
        if plain(x + n // 2, h - 5):
            cv.put(x + n // 2, h - 5, "ash0")
    # 빛 받은 테가 닳아 끊긴 자리: 길이와 색이 다 다르다
    # (같은 색 자국은 두 번까지: 고른 테 위에서는 길이가 달라도 끝자락이 같은 무늬로 보인다)
    wear = [(1, "rust1"), (3, "rust1"), (2, "rust0"), (4, "rust0"), (1, "rust3"), (2, "ash1"), (1, "bronze1")]
    for x, (n, col) in zip(r.sample(range(8, w - 14), len(wear)), wear):
        cv.hline(x, x + n - 1, 1, col)
    side = [(2, "rust1"), (3, "rust0"), (1, "rust3")]
    rows = [y for y in range(8, h - 14) if not (name == "generic_54" and 14 <= y <= 141)]
    for y, (n, col) in zip(r.sample(rows, len(side)), side):
        cv.vline(1, y, y + n - 1, col)
    # 네 귀의 쇠 꺾쇠 (귀마다 길이와 못이 다르다. 왼쪽 아래는 한 팔이 부러져 짧다)
    strap_ok = lambda x, y: cv.get(x, y) in (base, "rust1", "ash0", "ash2", "bronze0") and 2 <= x <= w - 4 and 2 <= y <= h - 4
    for (cx, cy, sx, sy, ax, ay, kind) in ((2, 2, 1, 1, 11, 9, "round"), (w - 4, 2, -1, 1, 8, 12, "flat"),
                                           (2, h - 4, 1, -1, 5, 10, "hole"), (w - 4, h - 4, -1, -1, 12, 7, "bleed")):
        _corner_strap(cv, cx, cy, sx, sy, ax, ay, strap_ok, kind)
    # 못
    for (x, y), kind in L["rivets"]:
        if not (x < 8 or x > w - 9) or not (y < 8 or y > h - 9):
            rivet(cv, x, y, kind)
    # 제목 쪽지 (맨 나중에, 그 위에는 아무것도 그리지 않는다)
    for x, y, lw in L["labels"]:
        _plaque(cv, x, y, lw, r)
    return cv.image()


# ─────────────────────────── 칸 가리킴, 빈 칸 그림 ───────────────────────────

def slot_highlight():
    """
    마우스가 올라간 칸 (24×24, 9조각 테 4, 가운데 16×16 이 칸 속). 바닐라는 반투명 흰 칠이라 어두운 창에서 튄다.
    뒤 (아이템 아래): 칸 속을 조금 밝은 쇠(rust1)로, 가장자리에 그을린 청동 한 줄.
    앞 (아이템 위): 네 귀에 청동 꺾쇠만. 단축 슬롯의 선택 테와 같은 말씨.
    """
    back, front = Cv(24, 24), Cv(24, 24)
    back.rect(4, 4, 19, 19, "rust1")
    back.hline(4, 19, 4, "bronze1")
    back.vline(4, 4, 19, "bronze1")
    back.hline(5, 19, 19, "bronze0")
    back.vline(19, 5, 19, "bronze0")
    back.put(4, 4, "bronze2")
    back.put(11, 4, "bronze0")
    for (x, y, sx, sy, glint) in ((4, 4, 1, 1, True), (19, 4, -1, 1, False), (4, 19, 1, -1, False), (19, 19, -1, -1, False)):
        front.put(x, y, "bronze3" if glint else "bronze2")
        front.put(x + sx, y, "bronze2")
        front.put(x + 2 * sx, y, "bronze1")
        front.put(x, y + sy, "bronze2")
        front.put(x, y + 2 * sy, "bronze1")
    front.put(18, 19, "moss0")
    return back.image(), front.image()


SLOT_HIGHLIGHT_SCALING = {"type": "nine_slice", "width": 24, "height": 24, "border": 4}

# 빈 갑옷·방패 칸에 비치는 흐린 그림 (16×16). 바닐라의 회색 윤곽 대신 녹슨 쇠빛으로 손으로 다시 그렸다.
# h 빛 받은 윤곽 (rust2), o 그늘진 윤곽 (rust1), d 깊은 홈 (ash0, 칸 바닥 rust0 보다 어둡다)
SLOT_ICONS = {
    "helmet": [
        "................",
        "................",
        "....hhhhhhoo....",
        "...h........o...",
        "...h........o...",
        "...h........o...",
        "...hdddd.dddo...",
        "...h........o...",
        "...h..d.d...o...",
        "...h.......o....",
        "...h........o...",
        "....h......o....",
        ".....hoooooo....",
        "................",
        "................",
        "................",
    ],
    "chestplate": [
        "................",
        "................",
        "...hhh....ooo...",
        "..h...hooo...o..",
        "..h..........o..",
        "...h........o...",
        "...h...d....o...",
        "...h...d....o...",
        "...h...d....o...",
        "...h...d...o....",
        "...h........o...",
        "....h......o....",
        "....hooooooo....",
        "................",
        "................",
        "................",
    ],
    "leggings": [
        "................",
        "................",
        "....hhhhhhhoo...",
        "....h........o..",
        "....h...dd...o..",
        "....h..o..h..o..",
        "....h..o..h..o..",
        "....h..o..h..o..",
        "....h..o..h..o..",
        "....h..o..h..o..",
        "....h..o..h.o...",
        "....hooo..hoo...",
        "................",
        "................",
        "................",
        "................",
    ],
    "boots": [
        "................",
        "................",
        "................",
        "................",
        "....hh.....hh...",
        "....h.o....h.o..",
        "....h.o....h.o..",
        "....h.o....h.o..",
        "...h..o...h..o..",
        "..h...o..h...o..",
        "..hoooo..hoooo..",
        "................",
        "................",
        "................",
        "................",
        "................",
    ],
    "shield": [
        "................",
        "................",
        "..hhhhhhhhhhoo..",
        "..h..........o..",
        "..h....d.....o..",
        "..h....d.....o..",
        "..h..ddddd...o..",
        "..h....d.....o..",
        "...h...d....o...",
        "...h.......o....",
        "....h.....o.....",
        ".....h...o......",
        "......hoo.......",
        "................",
        "................",
        "................",
    ],
}


def slot_icon(name):
    cv = Cv(16, 16)
    cv.stamp(0, 0, SLOT_ICONS[name], {"h": "rust2", "o": "rust1", "d": "ash0"})
    return cv.image()


# ─────────────────────────── 단추 ───────────────────────────

def button(state):
    """
    200×20, 9조각 테 3 (사용 못 함은 1). 그을린 쇠판(ash1)에 못 둘.
      보통       빛 받은 위·왼쪽 테 rust2 (군데군데 닳아 끊김), 아래 두 줄 그늘
      가리킴     같은 판, 테만 그을린 청동으로 (bronze2, 닳은 곳은 bronze3 이 드러난다). 흠집 자리는 보통과 같다
      사용 못 함 판 ash0, 테 ash1, 못은 녹으로 뭉개졌다
    흠집은 판 끝 쪽(못 둘레와 아래 가장자리)에 몰렸다: 손이 닿고 물이 고이는 자리.
    폭이 200 보다 좁으면 가운데가 왼쪽부터 잘려 나가므로, 오른쪽 못은 오른쪽 귀 3픽셀 안(x=197)에 둔다.
    """
    W, H = 200, 20
    hi = state == "highlighted"
    off = state == "disabled"
    r = rng("button/disabled" if off else "button")      # 보통과 가리킴은 같은 흠집
    cv = Cv(W, H)
    face = "ash0" if off else "ash1"
    cv.rect(1, 1, W - 2, H - 2, face)
    cv.hline(1, W - 2, 0, "ash0")
    cv.hline(1, W - 2, H - 1, "ash0")
    cv.vline(0, 1, H - 2, "ash0")
    cv.vline(W - 1, 1, H - 2, "ash0")
    if off:
        cv.hline(1, W - 2, 1, "ash1")
        cv.vline(1, 1, H - 2, "ash1")
        cv.put(2, 9, "rust0"); cv.put(2, 10, "rust0")
        cv.put(W - 3, 9, "rust0")
        cv.put(0, 0, None)
        cv.put(W - 1, H - 1, None)
        return cv.image()

    lit, worn = ("bronze2", "bronze3") if hi else ("rust2", "rust1")
    low, lowest = ("bronze1", "bronze0") if hi else ("rust0", "ash0")
    cv.hline(1, W - 2, 1, lit)
    cv.vline(1, 1, H - 3, lit)
    cv.hline(2, W - 2, H - 3, low)
    cv.hline(1, W - 2, H - 2, lowest)
    cv.vline(W - 2, 2, H - 2, lowest)
    cv.vline(W - 3, 2, H - 3, low)
    cv.put(1, H - 2, low)
    # 위 테가 닳아 끊긴 자리 (가리킴에서는 그 자리에 밝은 청동이 드러난다)
    # (같은 색 자국은 두 번까지)
    marks = ([(2, "bronze3"), (1, "bronze3"), (3, "bronze1"), (1, "bronze1"), (2, "bronze0")] if hi else
             [(2, "rust1"), (1, "rust1"), (3, "rust0"), (1, "rust0"), (2, "ash1")])
    for x, (n, col) in zip(r.sample(range(6, W - 8), len(marks)), marks):
        cv.hline(x, x + n - 1, 1, col)
    # 녹 꽃: 못 둘레와 아래 가장자리에 몰렸다
    ok = lambda x, y: 2 <= x <= W - 4 and 2 <= y <= H - 4 and cv.get(x, y) == face
    for x, y, n in ((4, 13, 5), (8, 14, 4), (W - 7, 13, 7), (W - 12, 15, 3),
                    (r.randint(40, 80), 15, 5), (r.randint(110, 150), 14, 6), (r.randint(60, 140), 3, 3)):
        _bloom(cv, x, y, n, r, ok)
    # 긴 긁힘: 거의 가로로 길게 그은 얕은 금 (rust1), 하나만 깊어 밝은 쇠(ash2)가 드러났다
    for j, x0 in enumerate((r.randint(14, 40), r.randint(70, 100), r.randint(125, 160))):
        y0 = r.randint(4, 12)
        n = r.randint(12, 22)
        slope = r.choice((6, 7, 9))
        for i in range(n):
            x, y = x0 + i, y0 + i // slope
            if ok(x, y):
                cv.put(x, y, "ash2" if j == 1 and 3 < i < n - 4 else "rust1")
    # 아래 테가 이 빠진 곳 둘 (부딪힌 자리)
    for x in (r.randint(30, 70), r.randint(120, 170)):
        cv.put(x, H - 3, "ash0"); cv.put(x + 1, H - 3, "ash0"); cv.put(x, H - 2, "ash1")
    # 못: 9조각의 귀 3픽셀 안 (왼쪽 x=2, 오른쪽 x=197). 가운데는 폭에 따라 잘리거나 이어 붙여지므로 못을 두지 않는다
    cv.put(2, 8, "rust3"); cv.put(2, 9, "rust1"); cv.put(2, 10, "rust0"); cv.put(2, 11, "bronze0")
    cv.put(W - 3, 8, "rust3"); cv.put(W - 3, 9, "rust1"); cv.put(W - 3, 10, "rust0")
    if hi:
        cv.put(2, 8, "bronze3"); cv.put(W - 3, 8, "bronze3")
    # 이 빠진 귀: 왼쪽 위와 오른쪽 위·아래 귀 한 칸씩 (바닐라는 네 귀가 다 검다)
    cv.put(0, 0, None)
    cv.put(W - 1, 0, None)
    cv.put(W - 1, H - 1, None)
    cv.put(1, 1, worn)
    return cv.image()


BUTTON_SCALING = {
    "button": {"type": "nine_slice", "width": 200, "height": 20, "border": 3},
    "button_highlighted": {"type": "nine_slice", "width": 200, "height": 20, "border": 3},
    "button_disabled": {"type": "nine_slice", "width": 200, "height": 20, "border": 1},
}


# 제작법 책 단추 20×18: 쇠 단추 위에 걸쇠 채운 낡은 책 (왼쪽 등, 오른쪽 책장, 표지에 바랜 마름모 문양)
RECIPE_BUTTON = [
    "..KKKKKKKKKKKKKKKK..",
    ".KHHHHHHHHHHHHHHHHK.",
    "KHffffffffffffffffsK",
    "KHfffKKKKKKKKKKKffsK",
    "KHfffKdCCCCCCCpKzfsK",
    "KHfffKDCBBBBBBPKzfsK",
    "KHfffKdCBBBBBBpKzfsK",
    "KHfffKdCBBBeBBPKzfsK",
    "KHfffKdCBBeBecccKfsK",
    "KHfffKdCBBBeBBqqKfsK",
    "KHfffKdCBBBBBBpKzfsK",
    "KHfffKDCBBBBBBPKzfsK",
    "KHfffKdCBBBBBBpKzfsK",
    "KHfffKdbbbbbbbPKzfsK",
    "KHfffKKKKKKKKKKKzfsK",
    "KHffffzzzzzzzzzzzfsK",
    ".KssssssssssssssssK.",
    "..KKKKKKKKKKKKKKKK..",
]


def recipe_button(hi):
    ink = {"K": "ash0", "H": "bronze2" if hi else "rust2", "f": "ash1", "s": "bronze0" if hi else "rust0",
           "z": "rust0", "d": "bronze0", "D": "bronze2", "C": "bronze2", "B": "bronze1", "b": "bronze0",
           "p": "parch1", "P": "parch0", "e": "bronze3", "c": "bronze3", "q": "rust1"}
    cv = Cv(20, 18)
    cv.stamp(0, 0, RECIPE_BUTTON, ink)
    # 닳은 곳: 표지 왼쪽 위 귀가 해졌고, 단추 테 한 곳이 깨졌다
    cv.put(7, 4, "bronze1")
    cv.put(12, 13, "rust0")
    cv.put(9, 1, "bronze3" if hi else "rust1")
    if hi:
        cv.put(4, 1, "bronze3"); cv.put(1, 5, "bronze3")
    return cv.image()


# ─────────────────────────── 설명 칸 ───────────────────────────

TOOLTIP_SCALING = {
    "background": {"type": "nine_slice", "width": 100, "height": 100, "border": 9},
    "frame": {"type": "nine_slice", "width": 100, "height": 100, "border": 10, "stretch_inner": True},
}


def tooltip():
    """
    바닐라는 글 둘레 (x-12, y-12, 폭+24, 높이+24) 에 바탕과 테를 그린다. 글은 12픽셀 안쪽.
    바탕: 7..92 를 그을린 가죽빛(rust0)으로, 귀는 둥글게. 가운데는 바둑판처럼 이어 붙여지므로 얼룩은 가장자리에만.
    테: 7 재 테두리, 8 녹슨 쇠(위·왼쪽 rust2, 아래·오른쪽 rust1), 9 안쪽 그늘. 네 귀에 쇠 귀싸개.
        왼쪽 아래 귀는 귀싸개가 떨어져 나가 못 구멍만 남았다 (10.5: 모서리 하나는 일부러 닳게).
        가장자리 가운데(10..89)는 늘여지거나 이어 붙여지므로 고른 줄로 둔다.
    """
    N = 100
    bg = Cv(N, N)
    bg.rect(7, 7, N - 8, N - 8, "rust0")
    for x, y in ((7, 7), (N - 8, 7), (7, N - 8), (N - 8, N - 8)):
        bg.put(x, y, None)
    # 가운데(9..90)는 이어 붙여지므로 얼룩을 두지 않는다. 귀 쪽 한두 점만 그을렸다
    bg.put(8, 8, "ash0"); bg.put(N - 9, N - 9, "ash0"); bg.put(N - 9, 8, "bronze0")

    fr = Cv(N, N)
    a, b = 7, N - 8          # 바깥 테두리 줄
    fr.hline(a + 1, b - 1, a, "ash0"); fr.hline(a + 1, b - 1, b, "ash0")
    fr.vline(a, a + 1, b - 1, "ash0"); fr.vline(b, a + 1, b - 1, "ash0")
    fr.hline(a + 1, b - 1, a + 1, "rust2"); fr.vline(a + 1, a + 1, b - 1, "rust2")
    fr.hline(a + 2, b - 1, b - 1, "rust1"); fr.vline(b - 1, a + 2, b - 1, "rust1")
    fr.hline(a + 2, b - 2, a + 2, "ash0"); fr.vline(a + 2, a + 2, b - 2, "ash0")
    # 귀싸개 (5×5 꺾쇠, 바깥으로 한 칸 튀어나온다). 모양을 귀마다 조금씩 다르게
    def bracket(x0, y0, sx, sy, worn=False):
        if worn:
            fr.put(x0 + sx * 1, y0 + sy * 1, "rust0")
            fr.put(x0 + sx * 2, y0 + sy * 2, "ash0")
            fr.put(x0, y0 + sy * 3, "rust0")
            return
        for i in range(5):
            fr.put(x0 + sx * i, y0 - sy, "ash0")
            fr.put(x0 - sx, y0 + sy * i, "ash0")
            fr.put(x0 + sx * i, y0, "rust2" if i < 4 else "rust1")
            fr.put(x0, y0 + sy * i, "rust2" if i < 4 else "rust1")
            fr.put(x0 + sx * i, y0 + sy, "rust1")
            fr.put(x0 + sx, y0 + sy * i, "rust1")
        fr.put(x0 - sx, y0 - sy, None)
        fr.put(x0 + sx, y0 + sy, "rust3")
        fr.put(x0 + sx * 2, y0 + sy * 2, "rust0")
    bracket(a - 1, a - 1, 1, 1)
    bracket(b + 1, a - 1, -1, 1)
    bracket(a - 1, b + 1, 1, -1, worn=True)
    bracket(b + 1, b + 1, -1, -1)
    fr.put(b + 1, b - 3, "bronze0")          # 오른쪽 아래 귀싸개의 녹물
    fr.put(b + 1, b - 4, "rust0")
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

    # 확대: 체력 칸들, 스태미나, 선택 테
    zoom = Image.new("RGBA", (100, 40), (34, 33, 36, 255))
    draw_hearts(zoom, out, 4, 4, 13)
    draw_hearts(zoom, out, 4, 16, 13, display=17, blink=True)
    draw_hearts(zoom, out, 4, 28, 7, kind="poisoned")
    _big(zoom, 8).save(os.path.join(preview_dir, "gui_hearts.png"))

    # 창들
    panels = []
    for name, (pw, ph) in ((n, CONTAINER_LAYOUTS[n]["size"]) for n in CONTAINER_LAYOUTS):
        img = _sprite(out, "container", name + ".png").crop((0, 0, pw, ph))
        cvs = Image.new("RGBA", (pw + 8, ph + 8), (20, 18, 18, 255))
        cvs.alpha_composite(img, (4, 4))
        big = _big(cvs, gui)
        for lx, ly, _ in CONTAINER_LAYOUTS[name]["labels"]:
            text = {"inventory": "제작", "crafting_table": "제작", "generic_54": "큰 상자"}[name] if (lx, ly) in (
                (97, 8), (29, 6), (8, 6)) else "인벤토리"
            m = pv.unifont_text(text, gui)
            if m is not None:
                big.paste(Image.new("RGBA", m.size, (0x40, 0x40, 0x40, 255)), ((4 + lx) * gui, (4 + ly) * gui), m)
        if name == "inventory":
            rb = _sprite(out, "sprites", "recipe_book", "button.png")
            big.alpha_composite(_big(rb, gui), ((4 + 104) * gui, (4 + 61) * gui))
        panels.append(big)
    sheet = Image.new("RGBA", (sum(p.width for p in panels) + 8 * len(panels), max(p.height for p in panels)), (12, 12, 12, 255))
    x = 0
    for p in panels:
        sheet.alpha_composite(p, (x, 0))
        x += p.width + 8
    sheet.save(os.path.join(preview_dir, "gui_containers.png"))

    # 단추 (사망 화면 크기 200, 일시정지 화면 크기 98·204) 와 설명 칸
    W2, H2 = 427, 150
    canvas = pv.dusk_scene(W2 * gui, H2 * gui)
    canvas.alpha_composite(pv.death_overlay(W2 * gui, H2 * gui))
    small = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    btns = [("button", 200, 20, 3, 113, 10, "일어선다"), ("button_highlighted", 200, 20, 3, 113, 34, "그만둔다"),
            ("button_disabled", 200, 20, 1, 113, 58, "일어선다"), ("button", 98, 20, 3, 10, 90, "설정"),
            ("button_highlighted", 98, 20, 3, 112, 90, "통계"), ("button", 204, 20, 3, 214, 90, "게임으로 돌아가기")]
    for spr, bw, bh, b, bx, by, _ in btns:
        small.alpha_composite(nine_slice(_sprite(out, "sprites", "widget", spr + ".png"), bw, bh, b), (bx, by))
    tb = _sprite(out, "sprites", "tooltip", "background.png")
    tf = _sprite(out, "sprites", "tooltip", "frame.png")
    for tx, ty, tw, th in ((330, 10, 80, 30), (20, 10, 70, 60)):
        small.alpha_composite(nine_slice(tb, tw + 24, th + 24, 9), (tx - 12, ty - 12))
        small.alpha_composite(nine_slice(tf, tw + 24, th + 24, 10, True), (tx - 12, ty - 12))
    canvas.alpha_composite(_big(small, gui))
    for spr, bw, bh, b, bx, by, text in btns:
        col = (160, 160, 160) if spr == "button_disabled" else (224, 224, 224)
        pv.paste_text(canvas, text, (bx + bw // 2) * gui, (by + 6) * gui, gui, color=col)
    pv.paste_text(canvas, "흐롤프의 미늘창", (330 + 30) * gui, 10 * gui, gui, color=(209, 195, 160))
    pv.paste_text(canvas, "녹슨 날", (330 + 20) * gui, 22 * gui, gui, color=(133, 128, 121))
    canvas.save(os.path.join(preview_dir, "gui_widgets.png"))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "resourcepack")
    paths = build(target)
    write_previews(target, sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "preview"))
    import artlint
    artlint.lint(paths, target)
