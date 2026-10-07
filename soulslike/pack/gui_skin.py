"""
바닐라 HUD·GUI 그림을 식은 가마의 톤으로 다시 그린다 (DESIGN.md 10.2, 10.4, 10.5, ART_DIRECTION.md).
gen_pack.py 가 hud.build 다음에 부른다. 스태미나 막대(경험치 막대)는 여기서 다시 그려 hud 의 것을 덮어쓴다.

말씨 (2026-10-07 사용자: "아직 AI 티, 다 엇비슷한 느낌, 장비칸이 어긋났다" → 처음부터 다시 그렸다)
  흩뿌린 녹 점·긁힘·고른 마모로 낡음을 내던 방식을 버렸다. 그런 무작위 자국은 어느 판이든 같은 결이라
  AI 가 만든 것처럼 보이고, 칸 옆의 자국이 칸을 비뚤어 보이게 했다. 이제 낡음과 무게는 구조로 낸다:
    - 빛은 늘 왼쪽 위 하나. 튀어나온 것은 위·왼쪽이 밝고, 패인 것은 위·왼쪽이 그늘이다. 베벨은 1픽셀.
    - 층마다 제 얼굴이 있다 (테 > 판 > 칸):
        테      바깥 윤곽(재) → 쇠 테 → 가는 청동 줄 → 홈. 비스듬히 깎은 귀마다 청동 마름모 하나
        판      거의 검은 녹슨 쇠(rust0) 한 색. 넓고 조용하게 둔다. 자국이 없다
        칸      판보다 한 단 깊은 바닥(ash0). 위·왼쪽 그늘 줄, 아래·오른쪽 입술(rust1) 한 줄만 빛을 받는다
        결과 칸 청동 테를 두른 칸 (만들어져 나오는 자리). 제작대의 큰 결과 칸은 안쪽에 청동 고리를 하나 더
        이름판  청동 테를 두른 바랜 양피지 판 + 오른쪽으로 뻗는 가는 청동 머리줄 (바닐라 제목 글이 0x404040 이라
                어두운 판 위에서는 읽히지 않는다)
        나눔줄  판에 새긴 홈 (위 줄 그늘, 아래 줄 빛). 가운데에 작은 청동 마름모
        단추    쇠판 + 베벨. 가리키면 안쪽에 청동 줄이 드러난다
    - 장식은 몇 개뿐이고 다 뜻이 있는 자리에 둔다 (귀, 이름판, 나눔줄 가운데, 선택 테).
    - 부드러운 그라데이션, 흐림, 반투명은 없다. 모든 색은 palette.c(이름) 하나에서.

칸 자리 (사용자: "장비칸이 어긋났다")
  칸은 바닐라 jar 와 한 픽셀도 다르지 않다 (CONTAINER_LAYOUTS, write_previews 가 align_*.png 로 겹쳐 증명한다).
  18×18 칸의 (x, y) 에서: 위 줄 x..x+16 과 왼쪽 줄 y..y+16 이 그늘, 아래 줄 x+1..x+17 과 오른쪽 줄이 입술,
  가운데 16×16 (x+1..x+16) 이 아이템 자리. 예전 그림은 그늘을 3픽셀로 두껍게 그려 보이는 바닥이 아이템보다
  오른쪽 아래로 1.5픽셀 밀려 있었다 (아이템이 칸 왼쪽 위에 붙어 보였다). 지금은 어두운 17×17 의 가운데가
  아이템 가운데와 반 픽셀 안에서 맞는다. 빈 칸 그림(갑옷·방패)도 16×16 의 가운데에 둔다.

그리는 것 (크기·경로·9조각 값은 1.21.11 클라이언트 jar 와 같다)
  체력      gui/sprites/hud/heart/*  9×9. 하트 열 개를 마른 핏방울 열 개로 (10.2, M1~M3). 방울은 x 1..7 이고
            바닐라가 8픽셀마다 그리므로 방울 사이에 한 줄이 빈다. 체력이 4 이하일 때 바닐라는 칸마다 1픽셀씩 따로 흔들고
            재생 때는 하나씩 튀어 오르는데, 방울이 떨어져 있어 그대로 자연스럽다. 이어진 핏빛 막대는 M4 의 souls:hud 그림 글자.
            깜빡임(맞은 순간 잃은 몫)은 바랜 양피지빛, 독은 이끼, 시듦은 재, 얼음은 뼈·재, 흡수는 그을린 청동.
  갑옷      armor_* 투명 (방어 수치를 쓰지 않는다). 허기는 hud.py 가 이미 투명하게 한다.
  스태미나  experience_bar_background / _progress 182×5. 녹슨 쇠 테의 가는 홈 + 이끼 세 줄 채움.
            스태미나 막대 그림은 여기 하나뿐이다 (hud.py 는 그리지 않는다).
  단축 슬롯 hotbar 182×22 (윤곽 + 청동 줄 + 깊은 칸 아홉), hotbar_selection 24×23 (청동 테),
            hotbar_offhand_left/right 29×24, hotbar_attack_indicator_background/progress 18×18 (단검).
  창        container/inventory.png, generic_54.png, crafting_table.png (256×256).
            container/slot_highlight_back/front (마우스가 올라간 칸: 바닥이 한 단 밝아지고 네 귀에 청동 꺾쇠),
            container/slot/{갑옷·방패} 빈 칸 그림.
  단추      widget/button, button_highlighted, button_disabled 200×20 (+ 바닐라와 같은 .mcmeta 9조각).
            사망 화면의 "일어선다 / 그만둔다" 도 이 그림이다. recipe_book/button(_highlighted) 20×18.
  설명 칸   tooltip/background, tooltip/frame 100×100 (+ .mcmeta). 거의 검은 바탕 + 판과 같은 테 (청동 줄, 귀 마름모).
  Dialog    dialog/warning_button(_highlighted, _disabled) 20×20. 모든 서버 창 제목 옆의 바닐라 노란 세모를
            단추와 같은 쇠판에 새긴 "!" 로 (가리킴은 청동, 사용 못 함은 재).

  python3 pack/gui_skin.py [팩폴더] [미리보기폴더]
      그림만 다시 그리고 미리보기(gui_hud, gui_hearts, gui_containers, gui_widgets, align_*)를 쓴다 (팩은 묶지 않는다)
      align_*.png 는 바닐라 jar 가 있을 때만 (환경 변수 SOULS_CLIENT_JAR, 없으면 ~/.cache/souls-client/versions/1.21.11.jar)
"""
import json
import os
import sys
import zipfile

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

# 어느 그림이든 이 이름으로만 칠한다. 한 자리에 한 색이라 판·칸·테가 어디서나 같은 말로 읽힌다.
OUTLINE = "ash0"      # 판·단추·칸 묶음의 바깥 윤곽
PANEL = "rust0"       # 판: 조용한 거의 검은 녹슨 쇠
FLOOR = "ash0"        # 칸 바닥: 판보다 한 단 깊다
SHADOW = "ash0"       # 칸의 위·왼쪽 (그늘)
LIP = "rust1"         # 칸의 아래·오른쪽 입술 (빛을 받는다)
GROOVE = "ash0"       # 새긴 홈의 그늘 쪽
# 청동은 줄·장식·선택에만 쓴다
BR_DEEP, BR, BR_LIT, BR_GLINT = "bronze0", "bronze1", "bronze2", "bronze3"
# 이름판 (바랜 양피지): 위 한 줄은 빛
PLATE_HI, PLATE = "parch3", "parch2"

LIT, MID, DARK = 0, 1, 2      # 테의 쪽: 위·왼쪽, 비스듬한 귀(오른쪽 위·왼쪽 아래), 아래·오른쪽

# 창 판의 테 (바깥 → 안). 고리마다 (빛 받는 쪽, 비스듬한 귀, 그늘진 쪽)
PANEL_RINGS = (
    (OUTLINE, OUTLINE, OUTLINE),     # 윤곽
    ("rust1", "rust1", "rust0"),     # 쇠 테
    (BR_LIT, BR, BR),                # 가는 청동 줄
    (GROOVE, GROOVE, GROOVE),        # 판과 테 사이 홈
    ("rust1", PANEL, PANEL),         # 판의 위·왼쪽 가장자리가 빛을 받는다 (판이 홈 안에서 한 단 솟았다)
)
# 단축 슬롯·왼손 칸: 윤곽 + 청동 줄만 (화면 위에 떠 있어 판이 없다)
BAR_RINGS = (
    (OUTLINE, OUTLINE, OUTLINE),
    (BR_LIT, BR, BR_DEEP),
)


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


# 귀 꺾쇠: 판의 네 귀에서 쇠 테와 청동 줄 (고리 1, 2) 이 arm 칸 동안 두 줄 청동 꺾쇠가 된다.
# 꺾쇠 끝은 재 한 칸으로 끊기고 그 뒤로 보통 테가 이어진다. 빛 받는 귀(왼쪽 위)는 밝고, 오른쪽 아래 귀는 그늘이다.
BRACKET_TONES = ((BR_GLINT, BR_LIT, BR), (BR_LIT, BR, BR_DEEP))


def corner_brackets(cv, w, h, arm=12, chamfer=2):
    W, H = w - 1, h - 1
    for y in range(h):
        for x in range(w):
            k, side = ring_at(x, y, w, h, chamfer)
            if k not in (1, 2) or min(x, W - x) > arm or min(y, H - y) > arm:
                continue
            along = max(min(x, W - x), min(y, H - y))
            cv.put(x, y, OUTLINE if along == arm else BRACKET_TONES[k - 1][side])


# 청동 마름모: 테의 귀와 나눔줄 가운데에 박는다. 왼쪽 위 두 면이 빛을 받고 오른쪽 아래 두 면이 그늘이다.
JEWEL = [
    "..h..",
    ".hGm.",
    "hGmms",
    ".mms.",
    "..s..",
]
JEWEL_SMALL = [
    ".h.",
    "hGs",
    ".s.",
]
JEWEL_INK = {"h": BR_LIT, "G": BR_GLINT, "m": BR, "s": BR_DEEP}


def jewel(cv, cx, cy, rows=JEWEL, edge=(PANEL,)):
    """
    (cx, cy) 가운데에 마름모. 둘레에서 edge 색과 닿는 자리에는 재 윤곽을 둘러 또렷하게 한다
    (edge 가 비면 윤곽 없이: 홈 안에 앉는 작은 마름모는 윤곽이 칸의 그늘 줄에 붙어 칸 테가 두꺼워 보인다).
    """
    r = len(rows) // 2
    cells = {(cx - r + dx, cy - r + dy) for dy, row in enumerate(rows) for dx, ch in enumerate(row) if ch != "."}
    cv.stamp(cx - r, cy - r, [row.replace(".", " ") for row in rows], JEWEL_INK)
    for x, y in cells:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in cells and cv.get(nx, ny) in edge:
                cv.put(nx, ny, OUTLINE)


def well(cv, x, y, w=18, h=18, floor=FLOOR, shadow=SHADOW, lip=LIP):
    """
    패인 칸 (바닐라 칸과 같은 자리·같은 역할). 위 줄 x..x+w-2 와 왼쪽 줄 y..y+h-2 는 그늘,
    아래 줄 x+1..x+w-1 과 오른쪽 줄 y+1..y+h-1 은 입술, 가운데가 바닥. 두 꺾임 (오른쪽 위, 왼쪽 아래) 은 바닥색
    (바닐라도 그 두 점은 바닥색이다). 칸이 붙어 있으면 칸 사이는 입술 한 줄 + 그늘 한 줄로 갈린다.
    """
    cv.rect(x + 1, y + 1, x + w - 2, y + h - 2, floor)
    cv.hline(x, x + w - 2, y, shadow)
    cv.vline(x, y, y + h - 2, shadow)
    cv.hline(x + 1, x + w - 1, y + h - 1, lip)
    cv.vline(x + w - 1, y + 1, y + h - 1, lip)
    cv.put(x + w - 1, y, floor)
    cv.put(x, y + h - 1, floor)


def divider(cv, x0, x1, y, ornament=True):
    """
    판에 새긴 나눔줄: 위 줄은 홈의 그늘(ash0), 아래 줄은 빛 받는 홈 벽(rust1). 오른쪽 끝은 빛 줄이 한 칸 더 간다
    (홈의 오른쪽 벽이 빛을 받는다). ornament 면 가운데에 작은 청동 마름모가 홈을 끊는다.
    """
    # 홈의 왼쪽 끝 벽은 그늘 (두 줄 다 어둡다), 오른쪽 끝 벽은 빛 (두 줄 다 밝다)
    cv.hline(x0, x1, y, GROOVE)
    cv.hline(x0 + 1, x1 + 1, y + 1, LIP)
    cv.put(x0, y + 1, GROOVE)
    cv.put(x1 + 1, y, LIP)
    if ornament:
        mx = (x0 + x1 + 1) // 2
        for dx in range(-3, 4):
            cv.put(mx + dx, y, PANEL)
            cv.put(mx + dx, y + 1, PANEL)
        cv.put(mx - 4, y, LIP)            # 끊긴 홈: 왼쪽 토막의 오른쪽 끝 벽은 빛,
        cv.put(mx + 4, y + 1, GROOVE)     # 오른쪽 토막의 왼쪽 끝 벽은 그늘
        jewel(cv, mx, y, JEWEL_SMALL, edge=())


def plate_box(tx, ty, tw, top=2):
    """이름판이 차지하는 (x0, y0, x1, y1)."""
    return tx - 3, ty - top, tx + tw + 2, ty + 9


def plate(cv, tx, ty, tw, rule_to=None, top=2):
    """
    이름판. 바닐라는 제목 글(0x404040)을 (tx, ty) 에 쓴다. tw 는 영어 글 폭 (한국어는 더 짧다).
    실제 클라이언트에서 한글(unifont)은 ty+1 .. ty+7, 라틴 대문자는 ty .. ty+6 (꼬리 ty+7) 에 찍힌다.
    판 x tx-3 .. tx+tw+2, y ty-top .. ty+9: 테 한 줄 (위·왼쪽 빛 받는 청동, 오른쪽 청동 그늘, 아래는 가장 짙은 청동),
    바랜 양피지 얼굴 (top 2 면 맨 위 한 줄이 빛). 얼굴 ty-1 .. ty+8 의 가운데가 두 글씨의 가운데 (ty+3.5) 와 맞는다.
    top 1 은 위가 좁은 자리 (제작대의 "보관함": 바로 위가 3×3 칸) 에서만. 네 귀는 깎였고, 오른쪽과 (판 바닥과 닿는
    곳만) 아래에 그림자 한 줄. 판은 칸 다음에 그리되 칸의 그늘 줄(ash0)은 덮지 않는다: 인벤토리의 "제작" 판 아래 테는
    2×2 칸의 그늘 줄과 겹치고, 거기서는 칸의 그늘 줄이 판의 아래 테가 된다.
    rule_to 가 있으면 판 오른쪽에서 그 x 까지 가는 청동 머리줄이 뻗고 끝에 작은 마름모가 앉는다.
    """
    x0, y0, x1, y1 = plate_box(tx, ty, tw, top)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            t, b, l, r = y == y0, y == y1, x == x0, x == x1
            if (t or b) and (l or r):
                continue
            if t or l:
                col = BR_LIT
            elif b:
                col = BR_DEEP
            elif r:
                col = BR
            elif y == y0 + 1 and top == 2:
                col = PLATE_HI
            else:
                col = PLATE
            if cv.get(x, y) != SHADOW:
                cv.put(x, y, col)
    cv.put(x0 + 1, y0 + 1, BR_LIT)            # 깎인 귀 안쪽
    cv.put(x1 - 1, y1 - 1, BR)
    for x in range(x0 + 1, x1 + 1):            # 아래 그림자는 판 바닥 위에만 (칸 바로 위면 칸 테가 두꺼워 보인다)
        if cv.get(x, y1 + 1) == cv.get(x + 1, y1 + 1) == cv.get(x, y1 + 2) == PANEL:
            cv.put(x, y1 + 1, OUTLINE)
    for y in range(y0 + 1, y1):
        if cv.get(x1 + 1, y) == PANEL:
            cv.put(x1 + 1, y, OUTLINE)
    if rule_to:
        ry = ty + 3
        cv.hline(x1 + 3, rule_to - 3, ry, BR)
        cv.hline(x1 + 3, rule_to - 3, ry + 1, OUTLINE)
        jewel(cv, rule_to, ry, JEWEL_SMALL, edge=())


def arrow(cv, x0, x1, ym, half):
    """제작 화살표 (바닐라 자리): 청동 상감. 자루 세 줄, 촉은 45도 계단. 위·왼쪽 가장자리는 빛, 아래·오른쪽은 그늘."""
    cells = set()
    head = x1 - half
    for x in range(x0, head):
        cells.update({(x, ym - 1), (x, ym), (x, ym + 1)})
    for x in range(head, x1 + 1):
        k = x1 - x
        cells.update((x, y) for y in range(ym - k, ym + k + 1))
    for x, y in cells:
        if (x, y - 1) not in cells or (x - 1, y) not in cells:
            col = BR_LIT
        elif (x, y + 1) not in cells or (x + 1, y) not in cells:
            col = BR_DEEP
        else:
            col = BR
        cv.put(x, y, col)
    for x, y in cells:
        for nx, ny in ((x + 1, y), (x, y + 1)):
            if (nx, ny) not in cells and cv.get(nx, ny) == PANEL:
                cv.put(nx, ny, OUTLINE)


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
    배경: 칸과 같은 말씨의 가는 홈. 위 테와 왼쪽 끝은 빛(rust1), 아래 테와 오른쪽 끝은 그늘(rust0), 홈 바닥은 ash0.
          네 귀는 깎였다. 자국은 없다 (늘 화면에 떠 있는 것이라 가장 조용해야 한다).
    채움: 이끼 세 줄 — 위 moss2 (빛을 받는 겉), 가운데 moss1, 아래 moss0. 바닐라가 진행만큼 왼쪽부터 잘라 그린다.
    """
    W = BAR_W
    bg = Cv(W, BAR_H)
    bg.hline(1, W - 2, 0, "rust1")
    bg.hline(1, W - 2, BAR_H - 1, "rust0")
    bg.vline(0, 1, BAR_H - 2, "rust1")
    bg.vline(W - 1, 1, BAR_H - 2, "rust0")
    bg.rect(1, 1, W - 2, BAR_H - 2, FLOOR)

    fill = Cv(W, BAR_H)
    fill.hline(1, W - 2, 1, "moss2")
    fill.hline(1, W - 2, 2, "moss1")
    fill.hline(1, W - 2, 3, "moss0")
    return bg.image(), fill.image()


# ─────────────────────────── 단축 슬롯 ───────────────────────────

def hotbar():
    """
    182×22. 윤곽 + 가는 청동 줄 하나를 두른 띠에 깊은 칸 아홉 (칸 x 2+20k..19+20k, 아이템 3+20k..18+20k).
    칸 사이 두 줄은 판(rust0). 장식은 없다: 화면 아래에 늘 떠 있는 것이라 가장 조용해야 한다.
    """
    W, H = 182, 22
    cv = Cv(W, H)
    frame(cv, 0, 0, W, H, BAR_RINGS, PANEL, chamfer=1)
    for k in range(9):
        well(cv, 2 + 20 * k, 2)
    return cv.image()


# 고른 칸의 청동 테 (24×23). 바닐라처럼 단축 슬롯보다 한 칸 왼쪽 위에서 그린다. 안쪽 4..19 는 비운다 (아이템 자리).
# O 윤곽, G bronze3 (빛 받는 바깥 줄), L bronze2, M bronze1, D bronze0 (그늘), K 안쪽 위·왼쪽 그늘 (ash0),
# P 빛이 맺힌 두 점 (parch2): 왼쪽 위 귀에만. 아래·오른쪽 안쪽 줄(L)은 위·왼쪽을 보는 비탈이라 밝다.
SELECTION = [
    ".OOOOOOOOOOOOOOOOOOOOOO.",
    "OGPPGGGGGGGGGGGGGGGGGGMO",
    "OPLLLLLLLLLLLLLLLLLLLLDO",
    "OGLKKKKKKKKKKKKKKKKKLMDO",
] + ["OGLK" + "." * 16 + "LMDO"] * 16 + [
    "OGLLLLLLLLLLLLLLLLLLLMDO",
    "OMDDDDDDDDDDDDDDDDDDDDDO",
    ".OOOOOOOOOOOOOOOOOOOOOO.",
]
SELECTION_INK = {"O": OUTLINE, "G": BR_GLINT, "L": BR_LIT, "M": BR, "D": BR_DEEP, "K": "ash0", "P": "parch2"}


def hotbar_selection():
    cv = Cv(24, 23)
    cv.stamp(0, 0, SELECTION, SELECTION_INK)
    return cv.image()


def offhand(right):
    """왼손 칸 29×24. 칸 상자는 22×22 (왼쪽: x 0..21, 오른쪽: x 7..28, y 1..22), 아이템은 y 4..19. 단축 슬롯과 같은 띠."""
    W, H = 29, 24
    cv = Cv(W, H)
    x0 = 7 if right else 0
    frame(cv, x0, 1, 22, 22, BAR_RINGS, PANEL, chamfer=1)
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
#   plates  바닐라가 제목 글을 쓰는 (x, y), 영어 글 폭, 머리줄 끝 x (None 이면 줄 없음), 판 위 여백 (2 또는 1)
#   dividers 새긴 나눔줄 (x0, x1, y)
#   jewels  귀 마름모 가운데 (이름판이 귀를 차지한 곳은 뺀다)
#   generic_54 는 바닐라가 위 (0 .. 17+줄×18-1) 와 아래 (126..221) 를 따로 그려 붙이므로, 양옆 테는 y 17..138 에서
#   위아래로 고르고 (귀 장식·마름모가 없다), 아래쪽 판은 126 줄부터 그 자체로 완결된다.
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
        "plates": [(97, 8, 41, 165, 2)],
        "dividers": [(7, 167, 80), (7, 167, 138)],
        "jewels": [(4, 4), (171, 4), (4, 161), (171, 161)],
    },
    "crafting_table": {
        "size": (176, 166),
        "wells": _grid(29, 16, 3, 3) + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(119, 30, 26, 26)],
        "alcove": None,
        "arrow": (90, 111, 42, 7),
        "plates": [(29, 6, 41, 165, 2), (8, 72, 50, 165, 1)],
        "dividers": [(7, 167, 138)],
        "jewels": [(4, 4), (171, 4), (4, 161), (171, 161)],
    },
    "generic_54": {
        "size": (176, 222),
        "wells": _grid(7, 17, 9, 6) + _grid(7, 139, 9, 3) + _grid(7, 197, 9, 1),
        "result": [],
        "alcove": None,
        "arrow": None,
        "plates": [(8, 6, 62, 165, 2), (8, 129, 50, 165, 2)],
        "dividers": [(7, 167, 194)],
        "jewels": [(171, 4), (4, 217), (171, 217)],
    },
}


def _alcove(cv, x, y, w, h):
    """
    인벤토리의 인물 자리: 칸과 같은 말씨로 패인 벽감 (위·왼쪽 그늘, 아래·오른쪽 입술). 안은 비워 둔다:
    인물이 이 자리의 그림이고, 창에서 가장 넓고 조용한 어둠이다.
    """
    well(cv, x, y, w, h)


def _result(cv, x, y, w, h):
    """결과 칸: 그늘·입술이 청동이다. 26×26 큰 칸은 안쪽에 아이템을 두르는 청동 고리가 하나 더 있다."""
    well(cv, x, y, w, h, shadow=BR_DEEP, lip=BR_LIT)
    cv.put(x + w - 1, y, BR)
    cv.put(x, y + h - 1, BR)
    if w > 18:
        # 아이템 (x+5 .. x+20) 둘레 한 칸 밖에 고리: 위·왼쪽 빛, 아래·오른쪽 그늘, 귀는 깎였다
        a, b = x + 3, x + w - 4
        cv.hline(a + 1, b - 1, y + 3, BR_LIT)
        cv.vline(a, y + 4, y + h - 5, BR_LIT)
        cv.hline(a + 1, b - 1, y + h - 4, BR)
        cv.vline(b, y + 4, y + h - 5, BR)


def container(name):
    L = CONTAINER_LAYOUTS[name]
    w, h = L["size"]
    cv = Cv(256, 256)
    frame(cv, 0, 0, w, h, PANEL_RINGS, PANEL)
    corner_brackets(cv, w, h)
    if L["alcove"]:          # 칸보다 먼저: 바닐라처럼 왼손 칸이 인물 자리의 오른쪽 아래 귀를 덮는다
        _alcove(cv, *L["alcove"])
    for x, y in L["wells"]:
        well(cv, x, y)
    for box in L["result"]:
        _result(cv, *box)
    if L["arrow"]:
        arrow(cv, *L["arrow"])
    for x0, x1, y in L["dividers"]:
        divider(cv, x0, x1, y)
    for tx, ty, tw, rule_to, top in L["plates"]:
        plate(cv, tx, ty, tw, rule_to, top)
    for cx, cy in L["jewels"]:
        jewel(cv, cx, cy, edge=(PANEL, GROOVE))
    return cv.image()


# ─────────────────────────── 칸 가리킴, 빈 칸 그림 ───────────────────────────

SLOT_HIGHLIGHT_SCALING = {"type": "nine_slice", "width": 24, "height": 24, "border": 4}


def slot_highlight():
    """
    마우스가 올라간 칸 (24×24, 칸 속은 4..19). 바닐라는 반투명 흰 칠이라 어두운 창에서 튄다.
    뒤 (아이템 아래): 바닥이 한 단 밝아진다 (rust0). 앞 (아이템 위): 칸 테두리(3, 20) 네 귀에 청동 꺾쇠.
    왼쪽 위 꺾쇠만 빛을 받아 bronze3, 오른쪽 아래는 그늘이라 bronze1.
    """
    back, front = Cv(24, 24), Cv(24, 24)
    back.rect(4, 4, 19, 19, PANEL)
    for (x, y, sx, sy, col) in ((3, 3, 1, 1, BR_GLINT), (20, 3, -1, 1, BR_LIT),
                                (3, 20, 1, -1, BR_LIT), (20, 20, -1, -1, BR)):
        for i in range(3):
            front.put(x + sx * i, y, col)
            front.put(x, y + sy * i, col)
    return back.image(), front.image()


# 빈 갑옷·방패 칸에 비치는 흐린 그림 (16×16). 녹슨 쇠빛 윤곽 한 색(rust1) 으로 손으로 그렸고,
# 모두 16×16 의 가운데에 둔다 (테두리 상자의 가운데가 x 7.5, y 7.5~8.0 — 바닐라 그림과 같다).
SLOT_ICONS = {
    # 큰 투구: 평평한 정수리, 곧은 옆판, 가로 눈구멍과 콧대
    "helmet": [
        "................",
        "................",
        "................",
        "....oooooooo....",
        "...o........o...",
        "...o........o...",
        "...oooo..oooo...",
        "...o...oo...o...",
        "...o...oo...o...",
        "...o........o...",
        "...o........o...",
        "...o........o...",
        "....oooooooo....",
        "................",
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
    "normal": (((OUTLINE,) * 3, ("rust1", "rust1", OUTLINE)), PANEL),
    # 가리킴: 쇠 테가 밝아지고 안쪽에 청동 줄이 드러난다
    "highlighted": (((OUTLINE,) * 3, ("rust2", "rust1", OUTLINE), (BR_GLINT, BR_LIT, BR)), PANEL),
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
# O 윤곽, i 쇠 베벨(빛), f 판, s 그늘 베벨, k 책 그늘, b 표지 (bronze1), B 표지 윗면 빛 (bronze2),
# d 등 (bronze0), p 책장 (parch1), c 걸쇠 (bronze3)
RECIPE_BUTTON = [
    ".OOOOOOOOOOOOOOOOOO.",
    "OiiiiiiiiiiiiiiiiiiO",
    "OifffffffffffffffffO",
    "OiffffffffffffffffsO",
    "OifffffkkkkkkkkfffsO",
    "OifffffdBBBBBBpkffsO",
    "OifffffdbbbbbbpkffsO",
    "OifffffdbbbbbbpkffsO",
    "OifffffdbbbbbccdffsO",
    "OifffffdbbbbbbpkffsO",
    "OifffffdbbbbbbpkffsO",
    "OifffffdbbbbbbpkffsO",
    "OifffffdbbbbbbpkffsO",
    "OiffffffkkkkkkkkffsO",
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
    (BR_LIT, BR, BR),
    (OUTLINE, OUTLINE, OUTLINE),
)


def tooltip():
    """
    바닐라는 글 둘레 (x-12, y-12, 폭+24, 높이+24) 에 바탕과 테를 그린다. 글은 12픽셀 안쪽.
    바탕: 4..95 를 가장 어두운 재(ash0)로, 귀는 깎였다. 가운데(9..90)는 이어 붙여지므로 한 색.
    테: 판의 테를 줄인 것 — 윤곽 (4), 가는 청동 줄 (5), 홈 (6). 귀(0..9, 늘이지 않는다)마다 청동 마름모.
        가장자리 가운데(10..89)는 늘여지므로 고른 줄이다.
    """
    N = 100
    bg = Cv(N, N)
    frame(bg, 4, 4, N - 8, N - 8, (), "ash0", chamfer=2)
    fr = Cv(N, N)
    frame(fr, 4, 4, N - 8, N - 8, TOOLTIP_RINGS, None, chamfer=2)
    for cx, cy in ((6, 6), (N - 7, 6), (6, N - 7), (N - 7, N - 7)):
        jewel(fr, cx, cy, edge=(None,))
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


def check_wells(ours, wells, van=None):
    """
    우리 그림이 바닐라 칸과 같은 자리인지 본다. 칸마다:
      그늘 줄 (위 x..x+w-2, 왼쪽 y..y+h-2) 이 한 색이고, 그 바로 바깥 (위 줄 위, 왼쪽 줄 왼쪽) 은 그 색이 아니며,
      입술 줄 (아래, 오른쪽) 은 바닥과 다른 한 색. 18×18 칸은 가운데 16×16 이 한 색 (아이템 자리).
    van (바닐라 그림) 을 주면 바닐라가 그 자리를 그늘·입술로 칠한 픽셀만 견준다 (인물 자리의 오른쪽 아래는
    바닐라에서도 왼손 칸이 덮는다). 어긋난 칸의 목록을 돌려준다 (비면 모두 맞다).
    """
    px = ours.load()
    vx = van.load() if van is not None else None
    bad = []
    for x, y, w, h in wells:
        dark = px[x, y]
        lip = px[x + w - 1, y + h - 1]
        edge = [(x + i, y) for i in range(w - 1)] + [(x, y + j) for j in range(h - 1)]
        lips = [(x + i, y + h - 1) for i in range(1, w)] + [(x + w - 1, y + j) for j in range(1, h)]
        outside = [(x + i, y - 1) for i in range(1, w - 1)] + [(x - 1, y + j) for j in range(1, h - 1)]
        if vx is not None:
            edge = [p for p in edge if vx[p][:3] == VANILLA_SHADOW]
            lips = [p for p in lips if vx[p][:3] == VANILLA_LIP]
            outside = [p for p in outside if vx[p][:3] not in (VANILLA_SHADOW, VANILLA_FLOOR, (0, 0, 0))]
        floor = px[x + 1, y + 1]
        ok = (all(px[p] == dark for p in edge) and all(px[p] == lip for p in lips) and lip != floor
              and lip[3] == 255 and all(px[p] != dark for p in outside))
        if w == 18 and h == 18:
            ok = ok and all(px[x + 1 + i, y + 1 + j] == floor for i in range(16) for j in range(16))
        if not ok:
            bad.append((x, y, w, h))
    return bad


def _outline(draw, x, y, w, h, k, col):
    draw.rectangle([x * k, y * k, (x + w) * k - 1, (y + h) * k - 1], outline=col)


def align_proof(out, preview_dir, jar):
    """
    align_<창>.png: 왼쪽 바닐라, 가운데 우리 그림, 오른쪽 우리 그림 위에 바닐라 칸의 경계를 겹친 것
    (청록 = 바닐라 아이템 자리 16×16 의 바깥 경계, 자홍 = 바닐라 칸 18×18 의 바깥 경계), 맨 오른쪽은 두 그림을 반씩 섞은 것.
    그리고 칸마다 자리 검사 (check_wells). 어긋난 칸이 있으면 그 칸을 빨갛게 칠하고 목록을 돌려준다.
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
            bad = check_wells(ours, wells, van)
            report[name] = (len(wells), bad)
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
            gap = 12
            sheet = Image.new("RGBA", (4 * w * k + 3 * gap, h * k), (12, 12, 12, 255))
            for i, im in enumerate((a, b, over, mix)):
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

# 창 미리보기에 놓을 바닐라 아이템 (칸 번호 → 그림, 개수)
MOCK_ITEMS = {
    "inventory": {9: ("item/iron_helmet", 1), 13: ("item/bread", 24), 18: ("item/iron_sword", 1), 22: ("item/bone", 3),
                  36: ("item/flint", 5), 40: ("item/rotten_flesh", 7), 41: ("item/stick", 2), 42: ("item/iron_axe", 1)},
    "crafting_table": {1: ("item/stick", 1), 4: ("item/stick", 1), 7: ("item/iron_ingot", 1), 14: ("item/bread", 24),
                       30: ("item/iron_sword", 1), 31: ("item/coal", 9)},
    "generic_54": {3: ("item/rotten_flesh", 7), 13: ("item/bone", 2), 30: ("item/iron_axe", 1), 60: ("item/bread", 24),
                   82: ("item/iron_sword", 1), 83: ("item/flint", 5)},
}
TITLES = {
    "inventory": (("제작", "Crafting"),),
    "crafting_table": (("제작", "Crafting"), ("보관함", "Inventory")),
    "generic_54": (("큰 상자", "Large Chest"), ("보관함", "Inventory")),
}


def _mock_container(out, name, lang, z, gui=3):
    """창 하나를 GUI 배율 gui 로: 판, 아이템, 제목 글 (바닐라 0x404040), 인벤토리는 제작법 책 단추와 고른 칸 가리킴."""
    import previews as pv
    L = CONTAINER_LAYOUTS[name]
    pw, ph = L["size"]
    small = Image.new("RGBA", (pw + 8, ph + 8), (20, 19, 18, 255))
    small.alpha_composite(_sprite(out, "container", name + ".png").crop((0, 0, pw, ph)), (4, 4))
    slots = [(x + 1, y + 1) for x, y in L["wells"]]
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
    hover = {"inventory": 20, "crafting_table": 20, "generic_54": 30}[name]
    hx, hy = slots[hover]
    small.alpha_composite(_sprite(out, "sprites", "container", "slot_highlight_back.png"), (4 + hx - 4, 4 + hy - 4))
    counts = []
    if z is not None:
        for i, (tex, n) in MOCK_ITEMS[name].items():
            im = _jar_png(z, f"assets/minecraft/textures/{tex}.png")
            if im is not None and i < len(slots):
                small.alpha_composite(im.crop((0, 0, 16, 16)), (4 + slots[i][0], 4 + slots[i][1]))
                if n > 1:
                    counts.append((slots[i], str(n)))
    small.alpha_composite(_sprite(out, "sprites", "container", "slot_highlight_front.png"), (4 + hx - 4, 4 + hy - 4))
    big = _big(small, gui)
    for (tx, ty, *_), text in zip(L["plates"], TITLES[name]):
        m = pv.unifont_text(text[0 if lang == "ko" else 1], gui)
        if m is not None:
            big.paste(Image.new("RGBA", m.size, (0x40, 0x40, 0x40, 255)), ((4 + tx) * gui, (4 + ty) * gui), m)
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
    W2, H2 = 427, 150
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
    tb = _sprite(out, "sprites", "tooltip", "background.png")
    tf = _sprite(out, "sprites", "tooltip", "frame.png")
    for tx, ty, tw, th in ((330, 14, 80, 30), (24, 14, 70, 60)):
        small.alpha_composite(nine_slice(tb, tw + 24, th + 24, 9), (tx - 12, ty - 12))
        small.alpha_composite(nine_slice(tf, tw + 24, th + 24, 10, True), (tx - 12, ty - 12))
    canvas.alpha_composite(_big(small, gui))
    for spr, bw, bh, b, bx, by, text in btns:
        col = (160, 160, 160) if spr == "button_disabled" else (224, 224, 224)
        pv.paste_text(canvas, text, (bx + bw // 2) * gui, (by + 6) * gui, gui, color=col)
    pv.paste_text(canvas, "흐롤프의 미늘창", (330 + 32) * gui, 14 * gui, gui, color=(209, 195, 160))
    pv.paste_text(canvas, "녹슨 날", (330 + 20) * gui, 26 * gui, gui, color=(133, 128, 121))
    canvas.save(os.path.join(preview_dir, "gui_widgets.png"))

    # 칸 자리 증명 (바닐라 jar 가 있을 때만)
    if jar:
        report = align_proof(out, preview_dir, jar)
        for name in CONTAINER_LAYOUTS:
            n, bad = report[name]
            print(f"  칸 자리 {name}: 바닐라 칸 {n}개, 어긋남 {len(bad)}" + (f" {bad}" if bad else ""))
        n, bad = report["hotbar"]
        print(f"  칸 자리 hotbar: 칸 {n}개, 어긋남 {len(bad)}, 선택 테 구멍 {report['selection_hole']}")
        for name, (v, o) in report["icons"].items():
            print(f"  빈 칸 그림 {name}: 가운데 바닐라 {v}, 우리 {o}")
        return report
    print("  (바닐라 jar 가 없어 align_*.png 를 건너뛴다)")
    return None


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "resourcepack")
    paths = build(target)
    write_previews(target, sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "preview"))
    import artlint
    artlint.lint(paths, target)
