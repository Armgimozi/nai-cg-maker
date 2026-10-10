"""
바닐라 HUD·GUI 그림을 다시 그린다 (DESIGN.md 10.2, 10.4, 10.5, 10.7, ART_DIRECTION.md). gen_pack.py 가 hud.build 다음에 부른다.

말씨: 촛불 아래의 고딕 (2026-10-08 사용자 결정: 시안 셋 가운데 B "고딕 촛불". 그 전의 반투명 검은 판 + 가는 금빛 줄 판은 버렸다.
다시 2026-10-08 사용자 결정: 초안 모양 (dist/screenshots/mood2/gothic_*) 이 더 낫다. 다듬기의 "장식 가볍게·단축바는 A 처럼" 은
취소하고 초안 그림으로 되돌렸다. 글을 가리거나 줄을 끊던 것을 고친 것 (밀대 가운데 홈·손잡이 기둥, 무기 칸 금실 끊김) 만 남긴다)
  판     깊은 검은 옻칠 (먹 88%). 윗날 밑에 촛불 기운이 고인다 (가운데가 가장 따뜻한 청동 → 녹 → 먹의 계단, 가장자리로 갈수록
         얕다). 가장자리 두 텍셀은 알파 계단.
  테     두 줄: 바깥 굵은 줄 (위는 촛불이 비친 금빛, 옆은 청동, 아래는 녹슨 쇠로 꺼진다) 과 안쪽 가는 청동 줄.
  장식   네 귀에 단조 꺾쇠 (꺾인 쇠, 안으로 말린 덩굴 고리, 바깥 대각선 창끝), 위 가운데에 마름모 꽃 장식. 모두 위가 밝다.
  칸     판보다 진한 우물: 위·왼쪽 안벽은 그늘 (먹), 아래 안벽은 촛불을 받은 녹빛 입술. 결과 칸은 금빛 테.
  반지 칸 인벤토리의 2×2 제작 칸 자리는 반지 칸 둘 (왼쪽 세로 두 칸, 9.4, 2026-10-08 사용자 결정 B 안): 다른 칸과 같은 우물에
         갑옷 칸의 빈 칸 그림과 같은 말씨의 흐린 반지 (icons.RING_PLACEHOLDER) 를 바탕에 그린다 (바닐라 클라이언트는 2×2 칸에 빈 칸
         그림을 주지 않는다. 반지 그림이 그것을 다 덮는다). 오른쪽 두 칸, 화살표, 결과 칸, "제작" 글은 지웠고 (글은 lang 의
         vanilla.container.crafting 을 비운다), 제작법 책 단추 그림은 투명하다 (누를 자리는 바닐라 그대로).
  단축 슬롯 칸마다 먹 받침과 창의 칸과 같은 쇠 테 우물, 칸 뒤로 지나가는 단조 쇠 띠, 칸 사이 띠 위에 금빛 마름모 못, 양 끝
         짧은 쇠 기둥 (마지막 칸의 개수 글자 위에서 끝난다). 고른 칸은 굵은 금빛 테와 네 귀 꼭지, 위 가운데 속 빈 마름모.
  단추   띠 위의 글: 위 금실 (가운데가 밝다)·아래 녹슨 줄이 양 끝으로 옅어진다. 가리키면 띠 윗부분에 촛불 기운, 금실이 밝아지고
         양 끝에 단조 마름모 장식.
  밀대   먹 띠에 위 금실·아래 녹슨 줄 (초안의 가운데 홈은 글 "시야 범위" 를 가로질러 뺐다). 손잡이는 초안의 단조 쇠 기둥에서
         글이 지나는 가운데 (텍셀 12..28) 를 비운 것: 위·아래 둥근 꼭지와 짧은 기둥 토막.
  모든 그림은 GUI 한 픽셀에 2 텍셀 (uidraw.py) 이고 GUI 그림 셰이더가 넓이 평균으로 읽는다 (shaders.py). 색은 팔레트 이름과
  알파만 (발광 알파 250~252 는 쓰지 않는다). 칸 자리는 바닐라와 픽셀까지 같다 (CONTAINER_LAYOUTS, write_previews 의 증명).

그리는 것 (크기·경로는 1.21.11 클라이언트 jar 와 같다. 9조각 값은 우리 그림에 맞춰 .mcmeta 를 같이 쓴다)
  숨기는 HUD  하트 (gui/sprites/hud/heart/* 모두), 방어 (armor_*), 경험치 막대 (experience_bar_*), 조준점 밑 공격 대기 표시를
              투명하게. 조준점 (crosshair) 은 가운데 어두운 작은 마름모만. 허기는 hud.py 가 투명하게 한다.
  보스 막대   boss_bar/white_* (HUD 막대 셋) 와 red_* (보스: 화면 아래 가운데의 그림 글자 막대, hud.py) 는 투명.
              나머지 색은 가는 진홍 막대 (이 게임은 쓰지 않는다, 1 배 그림)
  단축 슬롯   hotbar 182×22, hotbar_selection 24×23, hotbar_offhand_left/right 29×24, hotbar_attack_indicator_* 18×18 (1 배)
  창          container/inventory.png, generic_54.png, crafting_table.png (256×256 GUI = 512 텍셀)
              container/slot_highlight_back/front, container/slot/* 빈 칸 그림 (1 배)
  단추        widget/button, button_highlighted, button_disabled 200×20. 사망 화면·일시 정지·설정·Dialog 단추가 모두 이 그림.
              recipe_book/button(_highlighted) 20×18 (1 배): 투명 (인벤토리 2×2 자리가 반지 칸이 되었다. 제작대·화로의 단추도
              같은 그림이라 함께 사라진다: 그 창은 짓는 사람만 연다)
  설정 화면   widget/slider(_highlighted), slider_handle(_highlighted), checkbox(_selected)(_highlighted), text_field(_highlighted),
              tab* (1 배), scroller* (1 배, 초안 때 그림), textures/gui/(inworld_)header·footer_separator (금실과 그늘),
              inworld_menu_background
  설명 칸     tooltip/background, tooltip/frame 100×100 (9조각 14, 촛불 기운·두 색 테·귀 꺾쇠), 무기 설명 칸
              souls:tooltip/weapon_* (같은 판에 이름 밑 금빛 마름모 금실. 플러그인이 tooltip_style souls:weapon 을 단다)
  Dialog      dialog/warning_button(_highlighted, _disabled) 20×20 (작은 옻칠 판과 단조 테, 금빛 "!")
  그 밖       숨 거품 hud/air*, 효과 표시 (HUD·인벤토리 옆), 알림 toast/*, 제작법 책 (gui/recipe_book.png, recipe_book/*),
              발전 과제 창 (advancements/window.png, 안의 그림은 바닐라 꼴에 색만 팔레트로) — extra_sprites

  python3 pack/gui_skin.py [팩폴더] [미리보기폴더]
      그림만 다시 그리고 미리보기(gui_hud, gui_containers, gui_widgets, align_*)를 쓴다 (팩은 묶지 않는다)
      align_*.png 는 바닐라 jar 가 있을 때만 (환경 변수 SOULS_CLIENT_JAR, 없으면 ~/.cache/souls-client/versions/1.21.11.jar)
"""
import json
import math
import os
import sys
import zipfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from palette import c  # noqa: E402
import uidraw  # noqa: E402
from uidraw import Img, Mask  # noqa: E402

GUI = ("assets", "minecraft", "textures", "gui")


# ─────────────────────────── 그림판 ───────────────────────────

class Cv:
    """팔레트 이름과 알파로만 칠하는 그림판. None 은 투명. 색은 (이름, 알파) 또는 이름 (알파 255)."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def put(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = (col, 255) if isinstance(col, str) else col

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
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

    def box(self, x0, y0, x1, y1, col):
        """테두리만 (1픽셀)."""
        self.hline(x0, x1, y0, col)
        self.hline(x0, x1, y1, col)
        self.vline(x0, y0, y1, col)
        self.vline(x1, y0, y1, col)

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
                v = self.px[y][x]
                if v:
                    px[x, y] = c(v[0], v[1])
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


def clear(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))



# ─────────────────────────── 1 배 그림의 색 (고딕 그림이 덮지 않는 작은 그림: 보스 막대 색, 공격 대기, 칸 가리킴, 빈 칸 그림,
# 제작법 책 단추, 탭, 두루마리) ───────────────────────────

INK = "ash0"                       # 검정 (재)
WELL = "ink0"                      # 더 진한 검정 (먹, UI 전용)
LINE = ("parch0", 255)             # 가는 금빛 줄
LINE_DIM = ("parch0", 200)
ORN = ("parch2", 255)              # 밝은 금빛
ORN_HI = ("parch3", 255)
ICON = ("parch0", 170)             # 빈 갑옷·방패 칸에 비치는 흐린 그림
FADE = (89, 153)
# 그림이 든 작은 네모 단추 (제작법 책): 반투명 판에 금빛 테
SQUARE_TONES = {
    "normal":      ((INK, 165), ("parch0", 200), None),
    "highlighted": (("ash3", 90), ORN, ORN_HI),
}


def _cv_panel(cv, w, h, inset=1, line=LINE, fill=(INK, 185), fade=FADE):
    """1 배 반투명 판 (제작법 책 단추): 가장자리 len(fade) 줄은 알파 계단, inset 자리에 1픽셀 줄, 네 귀는 한 칸 깎는다."""
    for y in range(h):
        for x in range(w):
            d = min(x, y, w - 1 - x, h - 1 - y)
            corner = min(x, w - 1 - x) + min(y, h - 1 - y)
            if corner == 0:
                continue
            if d < len(fade):
                cv.put(x, y, (INK, fade[d] if corner > 1 else fade[0] // 2))
            elif d == inset and line:
                cv.put(x, y, line)
            else:
                cv.put(x, y, fill)


# ─────────────────────────── 숨기는 HUD ───────────────────────────

# 하트 그림 이름 (1.21.11 gui/sprites/hud/heart/). 모두 투명하게 한다 (체력은 왼쪽 위 막대)
HEART_TYPES = ("", "poisoned", "withered", "frozen", "absorbing")


def heart_names():
    names = []
    for suffix in ("", "_hardcore"):
        names += [f"container{suffix}", f"container{suffix}_blinking"]
    names.append("vehicle_container")
    for t in HEART_TYPES:
        pre = t + "_" if t else ""
        for part in ("full", "half"):
            for hc in ("", "hardcore_"):
                names += [f"{pre}{hc}{part}", f"{pre}{hc}{part}_blinking"]
    names += ["vehicle_full", "vehicle_half"]
    return names


HIDDEN_HUD = {
    # 이름: 크기 (바닐라와 같게)
    "armor_empty": (9, 9), "armor_half": (9, 9), "armor_full": (9, 9),
    "experience_bar_background": (182, 5), "experience_bar_progress": (182, 5),
    # 조준점 밑 공격 대기 표시 (설정 "조준점" 이 기본). 다크 소울에는 없다
    "crosshair_attack_indicator_full": (16, 16), "crosshair_attack_indicator_background": (16, 4),
    "crosshair_attack_indicator_progress": (16, 4),
}



# ─────────────────────────── 보스 막대 ───────────────────────────

BOSS_W, BOSS_H = 182, 5


BOSS_COLORS = ("white", "red", "pink", "blue", "green", "yellow", "purple")
GLYPH_BOSS_BARS = ("white", "red")   # 막대를 그림 글자로 그리는 색 (white = HUD 막대 셋, red = 보스): 막대 그림은 투명


def boss_bar(kind):
    """
    (배경, 채움) 182×5. white (HUD 막대 셋) 와 red (보스: 화면 아래 가운데에 그림 글자로 그린다, hud.py) 는 둘 다 투명.
    나머지 색 (이 게임은 쓰지 않는다) 은 같은 말씨의 가는 막대: 위·아래 검은 테, 85% 홈, 양 끝 탁한 금빛 마구리, 진홍 세 줄.
    """
    if kind in GLYPH_BOSS_BARS:
        return clear(BOSS_W, BOSS_H), clear(BOSS_W, BOSS_H)
    bg = Cv(BOSS_W, BOSS_H)
    bg.hline(1, BOSS_W - 2, 0, (WELL, 230))
    bg.hline(1, BOSS_W - 2, BOSS_H - 1, (WELL, 230))
    bg.rect(1, 1, BOSS_W - 2, BOSS_H - 2, (WELL, 217))
    for x in (0, BOSS_W - 1):
        bg.vline(x, 0, BOSS_H - 1, LINE)
    fill = Cv(BOSS_W, BOSS_H)
    for i, col in enumerate(("crimson2", "crimson2", "crimson1")):
        fill.hline(1, BOSS_W - 2, 1 + i, col)
    return bg.image(), fill.image()



# ─────────────────────────── 공격 대기 표시 (1 배) ───────────────────────────

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


def attack_indicator():
    bg, fg = Cv(18, 18), Cv(18, 18)
    bg.stamp(0, 0, ATTACK_BG, {"K": (INK, 200), "x": (INK, 120)})
    fg.stamp(0, 0, ATTACK_BG, {"K": LINE, "x": ("parch0", 200)})
    return bg.image(), fg.image()



# ─────────────────────────── 창 (인벤토리, 상자, 제작대) ───────────────────────────

# 바닐라 jar 의 그림과 한 픽셀씩 대조한 배치 (write_previews 의 align_*.png 가 겹쳐 보인다).
#   wells   바닐라 18×18 칸 상자의 왼쪽 위 (아이템은 +1, +1 에 16×16 = 우리 칸 네모)
#   result  결과 칸 상자 (x, y, 폭, 높이): 인벤토리의 18×18, 제작대의 26×26
#   alcove  인벤토리의 인물 자리 상자
#   arrow   (자루 시작 x, 촉 끝 x, 가운데 y, 촉 반높이) — 바닐라 화살표와 같은 자리
#   erased  바닐라 그림에 있지만 우리 그림에서 지운 칸 상자 (인벤토리 2×2 의 오른쪽 두 칸과 결과 칸: 반지 칸 B 안, 9.4).
#           칸 자리 증명은 이 상자에 우물이 없는지 본다
#   rings   반지 칸의 아이템 자리 (GUI x, y): 우물 바닥에 흐린 반지 (icons.RING_PLACEHOLDER) 를 그린다
#   titles  바닐라가 제목 글을 쓰는 (x, y) (AbstractContainerScreen 의 titleLabelY 6, 인벤토리는 titleLabelX 97,
#           제작대 29, "보관함" 은 inventoryLabelY = 창 높이 - 94, 상자 그림에서는 아래 판이 126 줄부터라 129).
#           그림에는 아무것도 그리지 않는다: 글은 언어 파일이 회색 (§7) 으로 바꾼다 (lang 의 vanilla.container.*, 10.4)
#   dividers 1픽셀 금빛 나눔줄 (x0, x1, y): 장비와 보관함 사이, 보관함과 단축 줄 사이
#   generic_54 는 바닐라가 위 (0 .. 17+줄×18-1) 와 아래 (126..221) 를 따로 그려 붙이므로, 양옆 가장자리는 위아래로 고르고
#   (귀 꺾쇠와 위 가운데 마름모는 맨 위와 맨 아래에만), 아래쪽 판은 126 줄부터 그 자체로 완결된다.
def _grid(x0, y0, cols, rows):
    return [(x0 + 18 * i, y0 + 18 * j) for j in range(rows) for i in range(cols)]


CONTAINER_LAYOUTS = {
    "inventory": {
        "size": (176, 166),
        # 갑옷 넷, 왼손, 반지 칸 둘 (바닐라 2×2 의 왼쪽 위·왼쪽 아래 칸 상자 (97, 17)·(97, 35)), 가방, 단축 줄
        "wells": [(7, 7 + 18 * i) for i in range(4)] + [(76, 61)] + _grid(97, 17, 1, 2)
                 + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [],
        "alcove": (25, 7, 51, 72),
        "arrow": None,
        "titles": [],
        "dividers": [(7, 167, 80), (7, 167, 138)],
        "erased": [(115, 17, 18, 18), (115, 35, 18, 18), (153, 27, 18, 18)],
        "rings": [(98, 18), (98, 36)],
    },
    "crafting_table": {
        "size": (176, 166),
        "wells": _grid(29, 16, 3, 3) + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(119, 30, 26, 26)],
        "alcove": None,
        "arrow": (90, 111, 42, 7),
        "titles": [(29, 6), (8, 72)],
        "dividers": [(7, 167, 138)],
    },
    "generic_54": {
        "size": (176, 222),
        "wells": _grid(7, 17, 9, 6) + _grid(7, 139, 9, 3) + _grid(7, 197, 9, 1),
        "result": [],
        "alcove": None,
        "arrow": None,
        "titles": [(8, 6), (8, 129)],
        "dividers": [(7, 167, 194)],
    },
}



# ─────────────────────────── 칸 가리킴, 빈 칸 그림 ───────────────────────────

SLOT_HIGHLIGHT_SCALING = {"type": "nine_slice", "width": 24, "height": 24, "border": 4}
# 칸 가리킴 그림의 네 귀 표식 (알파 1 이라 보이지 않는다): 귀마다 다른 색. GUI 그림 셰이더 (shaders.py position_tex_color.vsh) 가
# 꼭짓점마다 안쪽 대각선의 텍셀을 읽어 이 표식이면 그 꼭짓점이 가리킴 네모의 어느 귀인지 알고, 네모의 자리가 인벤토리에서 지운
# 칸 (2×2 의 오른쪽 두 칸과 결과 칸, 9.4) 이면 네모를 그리지 않는다 (바닐라 클라이언트는 그 칸을 여전히 가리킨다).
# 바닐라는 24×24 그림을 24×24 로 그릴 때 9 조각으로 나누지 않고 네모 하나로 그린다 (GuiGraphics.blitNineSlicedSprite).
# 다른 그림이 같은 표식을 쓰면 안 된다 (highlight_marks_unique 가 본다)
HIGHLIGHT_MARKS = {(0, 0): "ash0", (23, 0): "ash1", (0, 23): "ash2", (23, 23): "ash3"}
HIGHLIGHT_MARK_ALPHA = 1


def slot_highlight():
    """
    마우스가 올라간 칸 (24×24, 아이템 자리는 4..19). 뒤 (아이템 아래): 칸 속 (5..18) 이 옅은 금빛으로 데워진다.
    앞 (아이템 위): 칸 네모 바로 바깥 (3..20, 바닐라의 그늘·입술 자리라 아이템을 가리지 않는다) 에 밝은 금빛 테,
    네 귀는 가장 밝은 점. 또렷하되 칸 하나만큼만. 둘 다 네 귀 텍셀에 셰이더가 읽는 표식 (HIGHLIGHT_MARKS).
    """
    back, front = Cv(24, 24), Cv(24, 24)
    back.rect(5, 5, 18, 18, ("parch0", 70))
    front.box(3, 3, 20, 20, ORN)
    for x, y in ((3, 3), (20, 3), (3, 20), (20, 20)):
        front.put(x, y, ORN_HI)
    for cv in (back, front):
        for (x, y), name in HIGHLIGHT_MARKS.items():
            cv.put(x, y, (name, HIGHLIGHT_MARK_ALPHA))
    return back.image(), front.image()


def highlight_marks_unique(out):
    """팩의 GUI 그림 가운데 칸 가리킴 표식 (HIGHLIGHT_MARKS 의 색과 알파) 을 쓰는 다른 그림 [(경로, 개수)]. 비어야 한다."""
    marks = {tuple(c(n, HIGHLIGHT_MARK_ALPHA)) for n in HIGHLIGHT_MARKS.values()}
    own = {os.path.join(out, *GUI, "sprites", "container", n + ".png") for n in ("slot_highlight_back", "slot_highlight_front")}
    bad = []
    for ns in ("minecraft", "souls"):
        root = os.path.join(out, "assets", ns, "textures", "gui")
        for dp, _, fs in os.walk(root):
            for f in fs:
                p = os.path.join(dp, f)
                if not f.endswith(".png") or p in own:
                    continue
                a = np.asarray(Image.open(p).convert("RGBA"))
                hit = a[..., 3] == HIGHLIGHT_MARK_ALPHA
                if hit.any():
                    n = sum(1 for rgba in a[hit] if tuple(int(v) for v in rgba) in marks)
                    if n:
                        bad.append((os.path.relpath(p, out), n))
    return bad


# 빈 갑옷·방패 칸에 비치는 흐린 그림 (16×16): 한 색 (ICON) 윤곽. 모두 16×16 의 가운데에 둔다 (바닐라 그림과 같은 자리).
# 칸 테 (가장자리 한 줄) 에 닿지 않게 안쪽 2..13 에 그린다.
SLOT_ICONS = {
    "helmet": [
        "................",
        "................",
        "................",
        "................",
        ".....oooooo.....",
        "....o......o....",
        "....o......o....",
        "....ooo..ooo....",
        "....o..oo..o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....oo....oo....",
        "................",
        "................",
        "................",
        "................",
    ],
    "chestplate": [
        "................",
        "................",
        "................",
        "...ooo....ooo...",
        "..o...oooo...o..",
        "..o..........o..",
        "...oo......oo...",
        "....o......o....",
        "....o......o....",
        "....o......o....",
        "....o......o....",
        ".....oooooo.....",
        "................",
        "................",
        "................",
        "................",
    ],
    "leggings": [
        "................",
        "................",
        "................",
        "....oooooooo....",
        "....o......o....",
        "....o..oo..o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....o.o..o.o....",
        "....ooo..ooo....",
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
        ".....oo..oo.....",
        ".....oo..oo.....",
        ".....oo..oo.....",
        ".....oo..oo.....",
        "....o.o..o.o....",
        "...o..o..o..o...",
        "...oooo..oooo...",
        "................",
        "................",
        "................",
        "................",
        "................",
    ],
    "shield": [
        "................",
        "................",
        "................",
        "...oooooooooo...",
        "...o........o...",
        "...o...oo...o...",
        "...o.oooooo.o...",
        "...o...oo...o...",
        "....o..oo..o....",
        "....o......o....",
        ".....o....o.....",
        "......o..o......",
        ".......oo.......",
        "................",
        "................",
        "................",
    ],
}


def slot_icon(name):
    cv = Cv(16, 16)
    cv.stamp(0, 0, [r.replace(".", " ") for r in SLOT_ICONS[name]], {"o": ICON})
    return cv.image()



# ─────────────────────────── 탭, 두루마리 (1 배. 제작법 책 단추는 build 에서 투명하게) ───────────────────────────

def tab(selected, hi):
    """
    탭 130×24 (세계 만들기 화면). 고르지 않은 탭은 4줄 낮고 아래가 닫혔고, 고른 탭은 위로 솟고 아래가 트였다.
    반투명 검정에 1픽셀 테, 고른 탭은 금빛, 가리키면 밝은 금빛.
    """
    W, H = 130, 24
    cv = Cv(W, H)
    edge = ORN if hi else (LINE if selected else ("parch0", 200))
    top = 0 if selected else 4
    cv.rect(1, top + 1, W - 2, H - 1, (INK, 180 if selected else 140))
    cv.hline(1, W - 2, top, edge)
    cv.vline(0, top + 1, H - 1, edge)
    cv.vline(W - 1, top + 1, H - 1, edge)
    if not selected:
        cv.hline(0, W - 1, H - 1, ("parch0", 200))
    return cv.image()


def scroller(background):
    """
    두루마리 6×32 GUI (1 배 그림, 9 조각 테 1. 고딕 촛불 초안 때의 그림 그대로: 초안은 두루마리를 다시 그리지 않았다).
    막대: 바랜 양피지빛 네모. 길: 반투명 재.
    """
    cv = Cv(6, 32)
    if background:
        cv.rect(0, 0, 5, 31, (INK, 150))
    else:
        cv.rect(0, 0, 5, 31, LINE)
        cv.rect(1, 1, 4, 30, ("parch0", 255))
    return cv.image()


# 탭·두루마리 (세계 만들기·목록 화면, 1 배 그림) 의 9 조각
WIDGET_SCALING = {
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
SEPARATORS = ("header_separator", "footer_separator", "inworld_header_separator", "inworld_footer_separator")


def small_widgets():
    """{파일 이름: 그림} (gui/sprites/widget/ 의 1 배 그림: 탭)."""
    out = {}
    for hi in (False, True):
        sfx = "_highlighted" if hi else ""
        out["tab" + sfx] = tab(False, hi)
        out["tab_selected" + sfx] = tab(True, hi)
    return out


# ─────────────────────────── 고딕 그림 (2 텍셀 / GUI 픽셀): 판·테·장식 ───────────────────────────

S = 2                               # 텍셀 / GUI 픽셀
IRON = ["ink0", "rust1", "bronze2", "parch3"]    # 단조 쇠: 아랫날 → 몸 → 윗날 밑 → 윗날 (촛불이 위에서)
GOLD = ["rust1", "bronze3", "parch2", "glim0"]
PANEL_A = 0.88


def gsave(img, out, *parts):
    """uidraw.Img → PNG (textures/gui/ 아래)."""
    return save(img.image(), out, *parts)


def candle(dx, dy, depth):
    """촛불 기운의 색 (없으면 None): dx = 가운데에서 가로 거리 (0..1), dy = 윗날에서 텍셀, depth = 기운이 닿는 깊이."""
    r = math.sqrt((dx * 1.05) ** 2 + (dy / max(depth, 1)) ** 2)
    if r < 0.30:
        return "bronze1"
    if r < 0.55:
        return "bronze0"
    if r < 0.82:
        return "rust0"
    return None


def panel(img, x0, y0, w, h, alpha=PANEL_A, glow=12, fade=(0.35, 0.65), uniform=False):
    """
    판 (텍셀 네모). 가장자리 len(fade) 줄은 알파 계단, 귀는 한 텍셀 깎는다. 윗날 밑 glow 텍셀에 촛불 기운.
    uniform: 9 조각 그림 (가운데가 이어 붙여진다) 이면 촛불 기운을 가로로 고르게 (위에서 아래로만 옅어진다).
    """
    for y in range(h):
        for x in range(w):
            d = min(x, y, w - 1 - x, h - 1 - y)
            corner = min(x, w - 1 - x) + min(y, h - 1 - y)
            if corner == 0:
                continue
            a = alpha * (fade[d] if d < len(fade) else 1.0)
            name = "ash0"
            if glow and y >= len(fade):
                cn = candle(0.0 if uniform else abs(x + 0.5 - w / 2.0) / (w / 2.0), y - len(fade), glow)
                if cn:
                    name = cn
            img.put(x0 + x, y0 + y, name, a)


def frame(img, x0, y0, w, h, inset=5, inner=True, uniform=False):
    """두 줄 테: 바깥 줄 (inset, 2 텍셀 굵기) 은 위 금빛·옆 청동·아래 녹, 안쪽 줄 (inset+4, 1 텍셀) 은 흐린 청동."""
    L, T, R, B = x0 + inset, y0 + inset, x0 + w - 1 - inset, y0 + h - 1 - inset
    for x in range(L, R + 1):
        dx = 0.4 if uniform else abs(x + 0.5 - (x0 + w / 2.0)) / (w / 2.0)
        img.put(x, T, "parch3" if dx < 0.25 else ("parch2" if dx < 0.6 else "parch1"), 1.0)
        img.put(x, T + 1, "bronze2", 1.0)
        img.put(x, B - 1, "rust1", 1.0)
        img.put(x, B, "ink0", 0.9)
    for y in range(T + 2, B - 1):
        t = (y - T) / max(1, B - T)
        img.put(L, y, "bronze2" if t < 0.5 else "rust2", 1.0)
        img.put(L + 1, y, "ink0", 0.9)
        img.put(R, y, "bronze2" if t < 0.5 else "rust2", 1.0)
        img.put(R - 1, y, "ink0", 0.9)
    if inner:
        i = inset + 4
        L2, T2, R2, B2 = x0 + i, y0 + i, x0 + w - 1 - i, y0 + h - 1 - i
        for x in range(L2 + 6, R2 - 5):
            img.put(x, T2, "bronze1", 0.9)
            img.put(x, B2, "rust0", 0.8)
        for y in range(T2 + 6, B2 - 5):
            img.put(L2, y, "bronze0", 0.8)
            img.put(R2, y, "bronze0", 0.8)


def corner_orn(size=16):
    """왼쪽 위 귀 장식 (size×size 텍셀): 꺾인 쇠 (L), 안쪽 덩굴 고리, 귀 대각선 창끝. 다른 귀는 뒤집어 쓴다."""
    m = Mask(size, size)
    m.rect(2, 2, size, 4.5)
    m.rect(2, 2, 4.5, size)
    m.ring(7.5, 7.5, 2.0, 3.8, 0, 360)
    m.line(3.2, 3.2, 5.0, 5.0, 2.2)
    m.poly([(0.0, 0.0), (4.6, 1.6), (1.6, 4.6)])
    m.disc(size - 2.2, 3.2, 1.7)
    m.disc(3.2, size - 2.2, 1.7)
    hole = Mask(size, size).disc(7.5, 7.5, 1.0)
    return uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), IRON)


def crest(w=34, h=16):
    """위 가운데 꽃 장식: 가운데 마름모 (속이 빈) 와 양옆으로 말린 덩굴."""
    m = Mask(w, h)
    cx, cy = w / 2.0, 7.0
    m.poly([(cx - 6.0, cy), (cx, cy - 6.6), (cx + 6.0, cy), (cx, cy + 6.6)])
    for sx in (-1, 1):
        m.ring(cx + sx * 10.5, cy + 1.0, 2.2, 4.0, 180 if sx < 0 else 0, 360 if sx < 0 else 180)
        m.ring(cx + sx * 10.5, cy + 1.0, 2.2, 4.0, 270 if sx < 0 else 180, 360 if sx < 0 else 270)
        m.disc(cx + sx * 15.2, cy + 1.2, 1.5)
        m.line(cx + sx * 5.0, cy, cx + sx * 7.5, cy, 2.0)
    hole = Mask(w, h).poly([(cx - 2.6, cy), (cx, cy - 3.0), (cx + 2.6, cy), (cx, cy + 3.0)])
    out = uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), GOLD)
    out.fill(Mask(w, h).disc(cx, cy, 1.2).cov(), "glim0", 1.0)
    return out


def flip(img, fx, fy):
    out = Img(img.w, img.h)
    n, a = img.name, img.alpha
    if fx:
        n, a = n[:, ::-1], a[:, ::-1]
    if fy:
        n, a = n[::-1], a[::-1]
    out.name, out.alpha = n.copy(), a.copy()
    return out


def corners(img, x0, y0, w, h, inset=3, size=16):
    o = corner_orn(size)
    img.over(o, x0 + inset, y0 + inset)
    img.over(flip(o, True, False), x0 + w - inset - size, y0 + inset)
    # 아래 귀는 위아래를 뒤집어도 빛은 위에서: 다시 비춘다
    relit = uidraw.lit(flip(o, False, True).alpha, IRON)
    img.over(relit, x0 + inset, y0 + h - inset - size)
    img.over(flip(relit, True, False), x0 + w - inset - size, y0 + h - inset - size)


def well(img, x, y, w=18, h=18, rim=None, floor=0.93):
    """
    바닐라 칸 상자 (GUI x, y, w×h) 안의 우물: 아이템 자리 (x+1..x+w-2) 가 텍셀 [2(x+1), 2(x+w-1)). 그 바로 바깥 한 텍셀 (바닐라
    그늘·입술 자리의 안쪽 반) 에 쇠 테 (위는 촛불을 받은 청동, 옆·아래는 녹), 안쪽 위·왼쪽 벽은 그늘, 아래 벽은 녹빛 입술.
    바깥 반 텍셀은 판 그대로라 이웃 칸 사이에 판이 비친다.
    """
    X0, Y0, X1, Y1 = 2 * (x + 1), 2 * (y + 1), 2 * (x + w - 1), 2 * (y + h - 1)
    for yy in range(Y0, Y1):
        for xx in range(X0, X1):
            img.put(xx, yy, "ink0", floor)
    for xx in range(X0, X1):
        img.put(xx, Y0, "ink0", 1.0)
        img.put(xx, Y0 + 1, "ink0", 0.97)
        img.put(xx, Y1 - 1, "rust0", 0.95)
    for yy in range(Y0 + 1, Y1 - 1):
        img.put(X0, yy, "ink0", 1.0)
        img.put(X1 - 1, yy, "ink0", 0.97)
    top, bot, side = rim or ("bronze1", "rust1", "rust1")
    for xx in range(X0 - 1, X1 + 1):
        img.put(xx, Y0 - 1, top, 0.95)
        img.put(xx, Y1, bot, 0.9)
    for yy in range(Y0, Y1):
        img.put(X0 - 1, yy, side, 0.85)
        img.put(X1, yy, side, 0.85)


WELL_COLOURS = ("ink0", "rust0")                        # 우물 속 (바닥·안벽·입술): 칸 자리 증명이 본다
RIM_COLOURS = ("bronze1", "rust1", "parch3", "bronze2", "bronze3")


def divider(img, x0, x1, y, gem=True):
    """나눔줄 (텍셀): 금실 한 줄과 밑의 그늘, 양 끝 12 텍셀 알파 계단, 가운데 작은 마름모."""
    n = x1 - x0
    for i in range(n):
        d = min(i, n - 1 - i)
        k = 1.0 if d >= 12 else (d + 1) / 13.0
        img.put(x0 + i, y, "parch1", 0.9 * k)
        img.put(x0 + i, y + 1, "ink0", 0.6 * k)
    if gem:
        cx = (x0 + x1) / 2.0
        m = Mask(img.w, 8)
        m.poly([(cx - 4.0, 4.0), (cx, 0.5), (cx + 4.0, 4.0), (cx, 7.5)])
        img.over(uidraw.lit(m.cov(), GOLD), 0, y - 4)


def arrow(img, x0, x1, ym, half):
    """제작 화살표 (GUI 자리, 바닐라와 같은 자리): 단조 쇠 자루와 두 갈래 촉, 위가 밝다."""
    m = Mask(img.w, 2 * (2 * half + 3))
    oy = 2 * (ym - half - 1)
    yc = 2 * ym + 1 - oy
    m.line(2 * x0 + 1, yc, 2 * x1 - 2, yc, 2.2)
    m.line(2 * x1 - 1.5, yc, 2 * (x1 - half) + 0.5, yc - 2 * half + 0.5, 2.2)
    m.line(2 * x1 - 1.5, yc, 2 * (x1 - half) + 0.5, yc + 2 * half - 0.5, 2.2)
    m.disc(2 * x0 + 1.5, yc, 1.8)
    img.over(uidraw.lit(m.cov(), IRON), 0, oy)


# 반지 칸 바닥의 흐린 반지 색: 갑옷 칸의 빈 칸 그림 (ICON = 바랜 양피지 parch0 의 알파 170 을 먹 우물 위에 겹친 것, 약 #4b4335)
# 과 같게 보이는 팔레트 색을 우물 바닥과 같은 알파로 (창 그림은 칸 바닥에 직접 그리므로 겹칠 수 없다)
RING_ICON = ("rust1", 0.93)


def ring_placeholder(img, x, y):
    """
    반지 칸 (아이템 자리 GUI x, y 의 16×16) 바닥의 흐린 반지: icons.RING_PLACEHOLDER 의 점마다 GUI 한 픽셀 (2×2 텍셀) 을 RING_ICON
    으로. 아이템 그림과 같은 GUI 픽셀 격자라 반지를 끼면 반지 그림의 불투명한 점이 이것을 다 덮는다 (icons.ring_cover).
    """
    for i, j in ring_placeholder_pixels():
        for dy in (0, 1):
            for dx in (0, 1):
                img.put(2 * (x + i) + dx, 2 * (y + j) + dy, *RING_ICON)


def ring_placeholder_pixels():
    """흐린 반지의 점 (16×16 안의 GUI 픽셀 i, j)."""
    import icons
    return [(i, j) for j, row in enumerate(icons.RING_PLACEHOLDER) for i, ch in enumerate(row) if ch != "."]


def container(name):
    """창 256×256 GUI (512 텍셀): 판, 두 줄 테, 네 귀 꺾쇠, 위 가운데 꽃 장식, 칸 우물, 결과 칸, 반지 칸의 흐린 반지, 화살표, 나눔줄."""
    L = CONTAINER_LAYOUTS[name]
    w, h = L["size"]
    img = Img(512, 512)
    panel(img, 0, 0, 2 * w, 2 * h, glow=22)
    frame(img, 0, 0, 2 * w, 2 * h)
    corners(img, 0, 0, 2 * w, 2 * h)
    c_ = crest()
    img.over(c_, w - c_.w // 2, 0)
    if L["alcove"]:          # 칸보다 먼저: 왼손 칸이 인물 자리 오른쪽 아래 귀 옆에 붙는다 (바닐라와 같은 자리)
        x, y, aw, ah = L["alcove"]
        well(img, x, y, aw, ah, floor=0.97)
    for x, y in L["wells"]:
        well(img, x, y)
    for x, y, rw, rh in L["result"]:
        well(img, x, y, rw, rh, rim=("parch3", "bronze2", "bronze3"))
    for x, y in L.get("rings", ()):
        ring_placeholder(img, x, y)
    if L["arrow"]:
        arrow(img, *L["arrow"])
    for x0, x1, y in L["dividers"]:
        divider(img, 2 * x0, 2 * (x1 + 1), 2 * y + 1, gem=True)
    return img


# ─────────────────────────── 단축 슬롯 (고딕 촛불 초안 그대로, 2026-10-08 사용자 결정) ───────────────────────────

def lozenge(img, cx, cy, r, ramp=GOLD):
    m = Mask(img.w, img.h).poly([(cx - r, cy), (cx, cy - r), (cx + r, cy), (cx, cy + r)])
    img.over(uidraw.lit(m.cov(), ramp))


# 단축 슬롯 양 끝 기둥의 아래 끝 (텍셀): 마지막 칸 개수 글자 (GUI y 12.. = 텍셀 24..) 보다 위에서 끝난다
HOTBAR_POST_BOTTOM = 18


def hotbar():
    """
    182×22 GUI (364×44 텍셀). 칸 상자 (2+20k, 2) 18×18, 아이템 (3+20k, 3) 16×16 = 텍셀 [2(3+20k), 2(19+20k)) × [6, 38).
    칸마다 먹 받침 (텍셀 4..40) 과 쇠 테 우물 (well), 칸 뒤로 지나가는 단조 쇠 띠 (텍셀 19..23, 윗날 청동), 칸 사이 띠 위에
    금빛 마름모 못 여덟, 양 끝에 둥근 꼭지의 기둥. 기둥은 초안보다 짧다 (텍셀 8..18, 띠 위에 선다): 초안은 36 까지 내려와
    마지막 칸의 개수 글자 ("5") 에 붙었다.
    """
    img = Img(364, 44)
    for x in range(2, 362):
        img.put(x, 19, "bronze2", 0.9)
        img.put(x, 20, "rust1", 0.95)
        img.put(x, 21, "rust1", 0.95)
        img.put(x, 22, "ink0", 0.9)
        img.put(x, 23, "ink0", 0.5)
    for k in range(9):
        x = 2 + 20 * k
        X0 = 2 * x
        for yy in range(4, 40):
            for xx in range(X0, X0 + 36):
                img.put(xx, yy, "ink0", 0.62)
        well(img, x, 2, floor=0.80)
    for k in range(8):
        cx = 2 * (2 + 20 * k + 19) + 0.0
        m = Mask(364, 44).poly([(cx - 3.2, 21), (cx, 16.6), (cx + 3.2, 21), (cx, 25.4)])
        img.over(uidraw.lit(m.cov(), GOLD))
    for ex in (0, 360):
        m = Mask(4, 44)
        m.rect(0.5, 8, 3.5, HOTBAR_POST_BOTTOM)
        m.disc(2, 8, 1.8)
        m.disc(2, HOTBAR_POST_BOTTOM, 1.8)
        img.over(uidraw.lit(m.cov(), IRON), ex, 0)
    return img


def selection():
    """24×23 GUI (바닐라는 고른 칸보다 한 칸 왼쪽 위에서 그린다): 금빛 테 (텍셀 4..7 / 40..43), 네 귀 꼭지, 위 가운데 속 빈 마름모."""
    W, H = 48, 46
    m = Mask(W, H)
    m.rect(4, 4, 44, 7)
    m.rect(4, 40, 44, 43)
    m.rect(4, 4, 7, 43)
    m.rect(41, 4, 44, 43)
    for cx, cy in ((5.5, 5.5), (42.5, 5.5), (5.5, 41.5), (42.5, 41.5)):
        m.disc(cx, cy, 2.8)
    m.poly([(24 - 5, 5.5), (24, 0.3), (24 + 5, 5.5), (24, 10.5)])
    hole = Mask(W, H).poly([(24 - 2, 5.5), (24, 3.2), (24 + 2, 5.5), (24, 7.8)])
    return uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), GOLD)


def offhand(right):
    """29×24 GUI: 칸 상자 (x0+2, 3) 18×18 (왼쪽 x0 = 0, 오른쪽 7). 단축 슬롯 칸과 같은 먹 받침과 쇠 테 우물."""
    img = Img(58, 48)
    x0 = 7 if right else 0
    for yy in range(6, 42):
        for xx in range(2 * (x0 + 2), 2 * (x0 + 20)):
            img.put(xx, yy, "ink0", 0.62)
    well(img, x0 + 2, 3, floor=0.80)
    return img


def crosshair():
    """15×15 GUI: 가운데 작은 마름모 하나 (바닐라는 조준점을 뒤 색을 뒤집어 섞는다: 겨눌 자리만 겨우 보인다)."""
    img = Img(30, 30)
    m = Mask(30, 30).poly([(13.2, 15), (15, 13.2), (16.8, 15), (15, 16.8)])
    img.fill(m.cov(), "ash2", 1.0)
    return img


# ─────────────────────────── 단추·위젯 ───────────────────────────

def finial(h=24, flip_x=False):
    """단추 양 끝의 단조 마름모 장식 (14×h 텍셀)."""
    w = 14
    cy = h / 2.0
    m = Mask(w, h)
    m.poly([(1.0, cy), (6.0, cy - 5.0), (11.0, cy), (6.0, cy + 5.0)])
    m.line(10.0, cy, 13.5, cy, 1.8)
    m.ring(6.0, cy - 7.5, 1.4, 2.8, 90, 270)
    m.ring(6.0, cy + 7.5, 1.4, 2.8, 90, 270)
    hole = Mask(w, h).poly([(3.6, cy), (6.0, cy - 2.4), (8.4, cy), (6.0, cy + 2.4)])
    cov = np.clip(m.cov() - hole.cov(), 0, 1)
    if flip_x:
        cov = cov[:, ::-1]
    out = uidraw.lit(cov, GOLD)
    out.fill(Mask(w, h).disc(6.0 if not flip_x else w - 6.0, cy, 1.0).cov(), "glim0", 1.0)
    return out


def button(state, W=400, H=40):
    """200×20 GUI 띠 단추. 9 조각 (양옆 14, 위·아래 4): 가운데는 이어 붙여지므로 가로로 고르다."""
    img = Img(W, H)
    ends = 28
    for x in range(W):
        d = min(x, W - 1 - x)
        k = 1.0 if d >= ends else (d + 1) / (ends + 1.0)
        for y in range(4, H - 4):
            if state == "highlighted":
                dy = y - 4
                name = "ink0"
                if dy < 4:
                    name = "bronze1"
                elif dy < 9:
                    name = "bronze0"
                elif dy < 14:
                    name = "rust0"
                img.put(x, y, name, 0.78 * k)
            elif state == "disabled":
                img.put(x, y, "ink0", 0.30 * k)
            else:
                img.put(x, y, "ink0", 0.58 * k)
        if state == "highlighted":
            img.put(x, 2, "parch2", 1.0 * k)
            img.put(x, 3, "bronze2", 0.9 * k)
            img.put(x, H - 4, "bronze2", 0.9 * k)
            img.put(x, H - 3, "rust1", 0.9 * k)
        elif state == "disabled":
            img.put(x, 3, "ash1", 0.6 * k)
            img.put(x, H - 4, "ash1", 0.5 * k)
        else:
            img.put(x, 3, "parch1", 0.85 * k)
            img.put(x, H - 4, "rust1", 0.8 * k)
    if state == "highlighted":
        f = finial(H - 12)
        img.over(f, 6, 6)
        img.over(finial(H - 12, flip_x=True), W - 6 - f.w, 6)
    return img


BUTTON_SCALING = {"type": "nine_slice", "width": 200, "height": 20, "border": {"left": 14, "top": 4, "right": 14, "bottom": 4}}
HANDLE_SCALING = {"type": "nine_slice", "width": 8, "height": 20, "border": {"left": 2, "top": 6, "right": 2, "bottom": 6}}


def slider_track(hi):
    """
    밀대 길 200×20 GUI (고딕 촛불 초안): 먹 62% 띠 (양 끝 20 텍셀 알파 계단), 위 (텍셀 3) 금실 (가리키면 밝다), 아래 (36) 녹슨 줄.
    초안의 가운데 홈 (텍셀 19·20) 은 뺐다 (2026-10-08: 밀대 글 "시야 범위: 보통" 을 가로질렀다. 글은 텍셀 12..28 에 놓인다).
    """
    img = Img(400, 40)
    for x in range(400):
        d = min(x, 399 - x)
        k = 1.0 if d >= 20 else (d + 1) / 21.0
        for y in range(4, 36):
            img.put(x, y, "ink0", 0.62 * k)
        img.put(x, 3, ("parch2" if hi else "parch0"), 0.85 * k)
        img.put(x, 36, "rust1", 0.8 * k)
    return img


# 밀대 손잡이에서 비우는 텍셀 줄 (밀대 글이 지나는 자리, 위 꼭지 끝과 글 머리 사이에 반 GUI 틈)
HANDLE_CLEAR = (11, 29)


def slider_handle(hi):
    """
    8×20 GUI 손잡이 (16×40 텍셀): 고딕 촛불 초안의 단조 쇠 기둥 (위·아래 둥근 꼭지, 가운데 고리와 구멍, 가리키면 금빛) 을 초안
    그대로 빛을 입힌 뒤 글이 지나는 텍셀 HANDLE_CLEAR 만 비운다. 그래서 남은 위·아래 꼭지는 초안 그림과 한 텍셀도 다르지 않고
    (한 쇠 기둥의 두 끝으로 읽힌다) 글은 한 텍셀도 가려지지 않는다 (2026-10-08: 초안의 기둥과 가운데 고리가 "범위", "밝기:" 를
    가렸다. 비평: 비운 뒤 빛을 입히면 꼭지에 초안에 없던 밝은 윗날·검은 아랫날이 생긴다).
    """
    W, H = 16, 40
    m = Mask(W, H)
    m.rect(5, 5, 11, 35)
    m.disc(8, 5, 3.6)
    m.disc(8, 35, 3.6)
    m.ellipse(8, 20, 4.4, 5.5)
    hole = Mask(W, H).ellipse(8, 20, 1.6, 2.6)
    img = uidraw.lit(np.clip(m.cov() - hole.cov(), 0, 1), GOLD if hi else IRON)
    img.alpha[HANDLE_CLEAR[0]:HANDLE_CLEAR[1]] = 0.0
    img.name[HANDLE_CLEAR[0]:HANDLE_CLEAR[1]] = ""
    return img


def checkbox(selected, hi):
    img = Img(40, 40)
    panel(img, 2, 2, 36, 36, alpha=0.8, glow=0, fade=(0.5,))
    m = Mask(40, 40)
    m.rect(4, 4, 36, 6)
    m.rect(4, 34, 36, 36)
    m.rect(4, 4, 6, 36)
    m.rect(34, 4, 36, 36)
    img.over(uidraw.lit(m.cov(), GOLD if hi else IRON))
    if selected:
        g = Mask(40, 40).poly([(20, 9), (31, 20), (20, 31), (9, 20)])
        hole = Mask(40, 40).poly([(20, 15), (25, 20), (20, 25), (15, 20)])
        img.over(uidraw.lit(np.clip(g.cov() - hole.cov(), 0, 1), GOLD))
        img.fill(Mask(40, 40).disc(20, 20, 2.0).cov(), "glim0", 1.0)
    return img


def text_field(hi):
    img = Img(400, 40)
    for y in range(2, 38):
        for x in range(2, 398):
            img.put(x, y, "ink0", 0.9)
    for x in range(400):
        img.put(x, 0, "parch1" if hi else "rust1", 1.0)
        img.put(x, 1, "ink0", 1.0)
        img.put(x, 39, "bronze2" if hi else "rust0", 1.0)
    for y in range(40):
        img.put(0, y, "parch0" if hi else "rust1", 1.0)
        img.put(399, y, "parch0" if hi else "rust1", 1.0)
    return img


def warning_button(state):
    """Dialog 경고 단추 20×20 GUI (고딕 촛불 초안): 작은 옻칠 판과 단조 테 (가리키면 금빛), 가운데 금빛 "!" (창끝 모양)."""
    img = Img(40, 40)
    panel(img, 1, 1, 38, 38, alpha={"normal": 0.75, "highlighted": 0.85, "disabled": 0.45}[state],
          glow=10 if state == "highlighted" else 0, fade=(0.5,))
    m = Mask(40, 40)
    m.rect(3, 3, 37, 5)
    m.rect(3, 35, 37, 37)
    m.rect(3, 3, 5, 37)
    m.rect(35, 3, 37, 37)
    img.over(uidraw.lit(m.cov(), GOLD if state == "highlighted" else IRON))
    ex = Mask(40, 40)
    ex.poly([(17.4, 9), (22.6, 9), (21.0, 24), (19.0, 24)])
    ex.disc(20, 29.5, 2.4)
    ramp = GOLD if state != "disabled" else ["ink0", "ash1", "ash2", "ash3"]
    img.over(uidraw.lit(ex.cov(), ramp))
    return img


# ─────────────────────────── 설명 칸 ───────────────────────────

TT = 100            # GUI (텍셀 200)
RULE_ALPHA = 0.9    # 무기 설명 칸 바탕 그림의 이름 밑 금실의 덮임 (수치 밑 실선은 초안의 청동 줄, fonts.RULE_LINE)


def rule_gem(w, h, cx, cy):
    """이름 밑 금실 왼쪽 끝의 금빛 마름모 (반폭 4, 반높이 3.4 텍셀, 위에서 비친 금). 무기 설명 칸 바탕 (tooltip_bg) 이 쓴다."""
    m = Mask(w, h).poly([(cx - 4.0, cy), (cx, cy - 3.4), (cx + 4.0, cy), (cx, cy + 3.4)])
    return uidraw.lit(m.cov(), GOLD)


def tooltip_bg(divider_at=None, top_border=12):
    """
    설명 칸 바탕 (고딕 촛불 초안. 바닐라는 글 둘레 12 GUI 밖까지 그린다). 판 3..96 GUI, 윗날 밑 촛불 기운, 두 색 테 (가장자리에서 5),
    네 귀 단조 꺾쇠. 9 조각 (가장자리 14) 이라 가운데·변은 이어 붙여진다: 장식은 귀 조각 안에만, 촛불 기운과 테 색은 가로로 고르다.
    divider_at (GUI y) 면 그 줄에 이름 밑 금실 (무기 설명 칸): 글 열 (GUI 12 .. 폭 - 12) 을 한 알파로 끝까지 (2026-10-08 비평:
    초안은 끝 20 텍셀이 옅어졌는데 그 끝이 이어 깔리는 가운데 조각 안이라 조각마다 되풀이되어 줄이 끊겨 보였다), 왼쪽 끝 금빛
    마름모는 왼쪽 조각 안 (글 열 밖). 둘째 실선 (수치와 설명 사이) 은 이것과 다른 초안의 설명 실선이다: 글 열 왼쪽 끝 작은
    금빛 마름모와 1 텍셀 청동 줄의 그림 글자 (fonts.rule_sheet), 글 열 끝까지 한 알파.
    """
    W = H = TT * S
    img = Img(W, H)
    panel(img, 6, 6, W - 12, H - 12, alpha=0.97, glow=min(2 * top_border - 10, 22), uniform=True)
    frame(img, 6, 6, W - 12, H - 12, inset=4, inner=False, uniform=True)
    corners(img, 6, 6, W - 12, H - 12, inset=1, size=14)
    if divider_at is not None:
        y = 2 * divider_at
        for x in range(24, W - 24):
            img.put(x, y, "parch1", RULE_ALPHA)
            img.put(x, y + 1, "ink0", 0.6)
        img.over(rule_gem(W, 8, 22.0, 4.0), 0, y - 4)
    return img


TOOLTIP_SCALING = {"type": "nine_slice", "width": TT, "height": TT, "border": 14}
# 무기 설명 칸 (플러그인 item/ItemFactory 의 tooltip_style souls:weapon): 이름 (글 위 12) 밑 금실 (GUI 22), 위 조각 26
WEAPON_TOOLTIP = "weapon"
WEAPON_TOOLTIP_SCALING = {"type": "nine_slice", "width": TT, "height": TT,
                          "border": {"left": 14, "right": 14, "top": 26, "bottom": 14}}


def menu_background():
    """게임 중 메뉴 뒤 (inworld_menu_background, 이어 깐다): 먹 30% (흐림 효과 menu_dim 이 더 어둡게 한다)."""
    img = Img(32, 32)
    img.fill(1.0, "ink0", 0.30)
    return img


def separator():
    """설정 화면의 머리·발 나눔줄 (32×2 GUI, 이어 깐다, 고딕 촛불 초안): 금실 한 줄 (85%) 과 그 밑 먹 그늘 (50%)."""
    img = Img(64, 4)
    img.hline(0, 64, 0, "parch0", 0.85)
    img.hline(0, 64, 1, "ink0", 0.5)
    return img


# ─────────────────────────── 그 밖의 바닐라 그림 (2026-10-08 비평: 팩이 덮지 않아 바닐라 그대로 보이던 것) ───────────────────────────
#   숨 거품 hud/air·air_empty·air_bursting (물속에서 단축 슬롯 위), 효과 표시 hud/effect_background(_ambient) 와 인벤토리 옆
#   container/inventory/effect_background(_ambient), 알림 toast/* (발전 과제·제작법·안내·시스템·음악), 제작법 책
#   (gui/recipe_book.png 와 sprites/recipe_book/*), 발전 과제 창 (gui/advancements/window.png). 크기와 9 조각 값은 1.21.11 jar 와 같다.

CLAMP = 12          # 작은 판 귀 꺾쇠 (텍셀): 9 조각이면 테두리가 GUI 6 이상이어야 귀 조각 안에 든다 (SMALL_BORDER)
SMALL_BORDER = 6


def small_panel(img, x0, y0, w, h, alpha=0.9, line=1.0, glow=0, clamps=True):
    """
    작은 옻칠 판 (텍셀, 창과 같은 말씨를 줄인 것): 판, 두 색 테 (위 금빛·옆 청동·아래 녹, 가장자리에서 2, frame 한 줄), 네 귀 작은
    단조 꺾쇠 (corner_orn CLAMP). line 은 테·꺾쇠의 덮임 배율 (주변 효과처럼 흐린 판).
    """
    panel(img, x0, y0, w, h, alpha=alpha, glow=glow, fade=(0.45,), uniform=True)
    deco = Img(img.w, img.h)
    frame(deco, x0, y0, w, h, inset=2, inner=False, uniform=True)
    if clamps:
        corners(deco, x0, y0, w, h, inset=0, size=CLAMP)
    deco.alpha *= line
    img.over(deco)


def air(kind):
    """숨 거품 9×9 GUI (18 텍셀): 가는 뼈빛 고리와 윗왼쪽 작은 빛. 빈 것은 흐린 녹 고리, 터지는 것은 끊긴 고리."""
    img = Img(18, 18)
    if kind == "air":
        img.fill(Mask(18, 18).disc(9, 9, 5.6).cov(), "ink0", 0.35)
        img.fill(Mask(18, 18).ring(9, 9, 5.2, 7.0).cov(), "bone1", 0.9)
        img.fill(Mask(18, 18).disc(6.6, 6.4, 1.3).cov(), "bone3", 0.95)
    elif kind == "air_empty":
        img.fill(Mask(18, 18).ring(9, 9, 5.4, 6.8).cov(), "rust1", 0.55)
    else:
        m = Mask(18, 18)
        for a0 in (20, 110, 200, 290):
            m.ring(9, 9, 5.6, 7.4, a0, a0 + 50)
        img.fill(m.cov(), "bone0", 0.8)
    return img


def effect_bg(w, h, ambient):
    """효과 표시 판 (GUI w×h, 텍셀 2배). 주변 효과 (봉화 …) 는 흐리게."""
    img = Img(2 * w, 2 * h)
    small_panel(img, 0, 0, 2 * w, 2 * h, alpha=0.62 if ambient else 0.86, line=0.55 if ambient else 1.0)
    return img


def toast(w, h, light=False, mark=False):
    """
    알림 (GUI w×h, 텍셀 2배). 바닐라 글자색이 밝은 알림 (발전 과제·시스템·음악) 은 옻칠 판, 어두운 글자 (제작법 0x500050·검정,
    안내) 를 쓰는 알림은 바랜 양피지 쪽지 (어두운 판에서는 글이 읽히지 않는다). mark 면 왼쪽 위에 작은 금빛 마름모 (시스템 알림).
    """
    W, H = 2 * w, 2 * h
    img = Img(W, H)
    if light:
        for y in range(H):
            for x in range(W):
                d = min(x, y, W - 1 - x, H - 1 - y)
                if min(x, W - 1 - x) + min(y, H - 1 - y) == 0:
                    continue
                img.put(x, y, "bone1" if d >= 3 else ("rust2" if d >= 1 else "rust1"), 0.97 if d >= 1 else 0.6)
        for x in range(4, W - 4):
            img.put(x, 3, "bone2", 0.9)
            img.put(x, H - 4, "parch1", 0.9)
    else:
        small_panel(img, 0, 0, W, H, alpha=0.93, glow=10)
    if mark:
        lozenge(img, 16.0, 16.0, 4.0)
    return img


def recipe_book_panel():
    """제작법 책 판 (gui/recipe_book.png 256×256 → 512): 바닐라 판 자리 (1,1)~(148,167) 에 창과 같은 판·테·귀 꺾쇠, 돋보기."""
    img = Img(512, 512)
    x0, y0, w, h = 2, 2, 2 * 147, 2 * 166
    panel(img, x0, y0, w, h, glow=18)
    frame(img, x0, y0, w, h)
    corners(img, x0, y0, w, h)
    m = Mask(512, 512)
    m.ring(2 * 15.5, 2 * 19.0, 4.2, 6.6)
    m.line(2 * 13.0, 2 * 21.6, 2 * 10.2, 2 * 24.4, 3.0)
    img.over(uidraw.lit(m.cov(), IRON))
    return img


def recipe_well(img, X0, Y0, X1, Y1, rim, floor=0.9):
    """
    텍셀 [X0, X1) × [Y0, Y1) 우물 (창의 well 과 같은 말씨): 먹 바닥, 위·왼쪽 안벽 그늘, 아래 녹빛 입술 (rust0), 바로 바깥 한 텍셀
    테 rim = (위, 아래, 옆): 쇠는 (bronze1, rust1, rust1).
    """
    for yy in range(Y0, Y1):
        for xx in range(X0, X1):
            img.put(xx, yy, "ink0", floor)
    for xx in range(X0, X1):
        img.put(xx, Y0, "ink0", 1.0)
        img.put(xx, Y0 + 1, "ink0", 0.97)
        img.put(xx, Y1 - 1, "rust0", 0.95)
    for yy in range(Y0 + 1, Y1 - 1):
        img.put(X0, yy, "ink0", 1.0)
        img.put(X1 - 1, yy, "ink0", 0.97)
    top, bot, side = rim
    for xx in range(X0 - 1, X1 + 1):
        img.put(xx, Y0 - 1, top, 0.95)
        img.put(xx, Y1, bot, 0.9)
    for yy in range(Y0, Y1):
        img.put(X0 - 1, yy, side, 0.85)
        img.put(X1, yy, side, 0.85)


RIM_IRON = ("bronze1", "rust1", "rust1")            # 창의 칸 우물과 같은 쇠 테
RIM_GOLD = ("parch3", "bronze2", "bronze3")         # 결과 칸·가리킨 칸의 금빛 테
RIM_BLOOD = ("blood2", "blood0", "blood1")          # 만들 수 없는 제작법 (바닐라의 붉은 칸)


def recipe_slot(craftable, many):
    """제작법 칸 25×25 (텍셀 50): 쇠 테 우물 (만들 수 없으면 마른 핏빛 테). 여럿이면 오른쪽 아래에 겹친 둘째 테."""
    img = Img(50, 50)
    rim = RIM_IRON if craftable else RIM_BLOOD
    if many:
        for i in range(8, 49):
            for (x, y) in ((i, 48), (48, i)):
                img.put(x, y, rim[1], 0.7)
    recipe_well(img, 4, 4, 46, 46, rim, floor=0.88 if craftable else 0.8)
    return img


def recipe_tab(selected):
    """제작법 책 탭 35×27 (텍셀 70×54): 판 왼쪽에 붙는 탭. 고른 탭은 금빛 테에 오른쪽이 트였다 (판과 이어진다)."""
    img = Img(70, 54)
    x0 = 0 if selected else 8
    panel(img, x0, 2, 70 - x0, 50, alpha=0.92 if selected else 0.8, glow=0, fade=(0.5,), uniform=True)
    top, side = ("parch2", "bronze2") if selected else ("parch0", "bronze1")
    for x in range(x0 + 2, 70 if selected else 68):
        img.put(x, 3, top, 1.0)
        img.put(x, 50, "rust1", 0.9)
    for y in range(4, 50):
        img.put(x0 + 2, y, side, 1.0)
        if not selected:
            img.put(67, y, "rust1", 0.8)
    return img


def recipe_filter(enabled, hi):
    """'만들 수 있는 것만' 단추 26×16 (텍셀 52×32): 작은 판에 십자 창살의 쇠 네모 (작업대) 와 켜짐은 금빛 마름모, 꺼짐은 흐린 빈 마름모."""
    img = Img(52, 32)
    small_panel(img, 0, 0, 52, 32, alpha=0.85, line=1.0 if hi else 0.8, clamps=False)
    g = Mask(52, 32)
    g.rect(30, 8, 46, 24)
    hole = Mask(52, 32).rect(32, 10, 44, 22)
    g2 = Mask(52, 32).rect(37.3, 9, 38.7, 23).rect(31, 15.3, 45, 16.7)
    img.over(uidraw.lit(np.clip(np.maximum(g.cov() - hole.cov(), g2.cov()), 0, 1), IRON))
    if enabled:
        lozenge(img, 15.0, 16.0, 6.0)
    else:
        m = Mask(52, 32)
        m.poly([(9, 16), (15, 10), (21, 16), (15, 22)])
        h_ = Mask(52, 32).poly([(11.5, 16), (15, 12.5), (18.5, 16), (15, 19.5)])
        img.fill(np.clip(m.cov() - h_.cov(), 0, 1), "rust2", 0.85)
    if hi:
        for x in range(4, 48):
            img.put(x, 2, "parch2", 1.0)
    return img


def page_arrow(forward, hi):
    """제작법 책 쪽 넘김 12×17 (텍셀 24×34): 단조 쇠 화살촉, 가리키면 금빛."""
    m = Mask(24, 34)
    pts = [(6, 6), (19, 17), (6, 28), (6, 22), (12, 17), (6, 12)]
    if not forward:
        pts = [(24 - x, y) for x, y in pts]
    m.poly(pts)
    img = Img(24, 34)
    img.over(uidraw.lit(m.cov(), GOLD if hi else IRON))
    return img


def recipe_overlay_button(enabled, hi):
    """다른 제작법 고르기 칸 24×24 (텍셀 48): 쇠 테 우물 (가리키면 금빛 테), 만들 수 없으면 마른 핏빛 테."""
    img = Img(48, 48)
    rim = (RIM_GOLD if hi else RIM_IRON) if enabled else RIM_BLOOD
    recipe_well(img, 4, 4, 44, 44, rim, floor=0.85)
    return img


def advancement_window(van):
    """발전 과제 창 (252×140 GUI, 256×256 → 512): 창 판·테·귀 꺾쇠, 바닐라가 비운 가운데 (탭 그림 자리) 는 그대로 비운다."""
    img = Img(512, 512)
    w, h = 2 * 252, 2 * 140
    panel(img, 0, 0, w, h, glow=16)
    frame(img, 0, 0, w, h)
    corners(img, 0, 0, w, h)
    if van is not None:
        a = np.asarray(van.convert("RGBA"))[..., 3]
        hole = np.repeat(np.repeat(a == 0, 2, 0), 2, 1)
        img.alpha[hole] = 0.0
        img.name[hole] = ""
    return img


def remap(img, ramp):
    """
    바닐라 그림의 꼴 (알파) 은 두고 색만 팔레트 계단으로: 밝기 단계를 어두운 차례로 세어 ramp (어둠 → 밝음) 에 고르게 나눈다.
    발전 과제 창 안의 작은 그림 (탭 바탕 돌, 칸 테, 이름 상자, 탭) 처럼 모양은 바닐라 그대로 두고 밝은 회색·파랑·노랑만 걷어낼 때.
    """
    a = np.asarray(img.convert("RGBA")).astype(np.int32)
    lum = (a[..., 0] * 299 + a[..., 1] * 587 + a[..., 2] * 114) // 1000
    on = a[..., 3] > 0
    levels = sorted(set(lum[on].tolist()))
    out = Img(img.width, img.height)
    for y in range(img.height):
        for x in range(img.width):
            if on[y, x]:
                i = levels.index(lum[y, x])
                out.put(x, y, ramp[min(len(ramp) - 1, i * len(ramp) // max(1, len(levels)))], a[y, x, 3] / 255.0)
    return out


ADV_GOLD = ["ink0", "rust1", "bronze2", "bronze3", "parch2"]   # 얻은 것 (이름 상자·탭)
ADV_IRON = ["ink0", "ash1", "rust1", "ash2", "ash3"]            # 얻지 못한 것
ADV_BG = ("ash0", "ink0")                                        # 탭 바탕 돌: (돌 낯, 줄눈)
ADV_FRAMES = ("task", "goal", "challenge")
ADV_POINTS_GOLD = ["rust1", "bronze2", "bronze3", "parch2"]    # 얻은 도전 칸의 뾰족한 테 (GOLD 보다 한 단 눌러: 몸이 청동)


def advancement_bg():
    """
    발전 과제 탭 바탕 (16×16 GUI 를 이어 깐다, 텍셀 32): 손으로 놓은 성벽 돌 쌓기. 돌 낯 한 색 (재) 과 반 GUI 줄눈 (먹) 두 색뿐이고,
    돌은 16×8 GUI 로 줄마다 반 장 엇갈린다. 깔면 이음매 없이 이어진다 (바닐라 돌·네더 … 의 잔 점 무늬는 쓰지 않는다:
    2026-10-08 비평, 사용자가 싫어한 흩뿌린 점).
    """
    face, joint = ADV_BG
    img = Img(32, 32)
    img.fill(1.0, face, 1.0)
    for x in range(32):
        img.put(x, 15, joint, 1.0)
        img.put(x, 31, joint, 1.0)
    for y in range(0, 15):
        img.put(0, y, joint, 1.0)
    for y in range(16, 31):
        img.put(16, y, joint, 1.0)
    return img


def _shaped_well(img, inside, rim, floor=0.9):
    """
    덮임 inside (bool 텍셀 배열) 꼴의 우물 (recipe_well 과 같은 말씨): 먹 바닥, 위·왼쪽 안벽 그늘, 아래 녹빛 입술, 바로 바깥 한
    텍셀 테 rim = (위, 아래, 옆).
    """
    h, w = inside.shape

    def at(y, x):
        return 0 <= y < h and 0 <= x < w and inside[y, x]
    top, bot, side = rim
    for y in range(h):
        for x in range(w):
            if inside[y, x]:
                if not at(y - 1, x) or not at(y, x - 1):
                    img.put(x, y, "ink0", 1.0)
                elif not at(y - 2, x) or not at(y, x + 1):
                    img.put(x, y, "ink0", 0.97)
                elif not at(y + 1, x):
                    img.put(x, y, "rust0", 0.95)
                else:
                    img.put(x, y, "ink0", floor)
                if not at(y + 1, x):
                    img.put(x, y, "rust0", 0.95)
            elif at(y + 1, x) or at(y + 1, x - 1) or at(y + 1, x + 1):
                img.put(x, y, top, 0.95)
            elif at(y - 1, x) or at(y - 1, x - 1) or at(y - 1, x + 1):
                img.put(x, y, bot, 0.9)
            elif at(y, x - 1) or at(y, x + 1):
                img.put(x, y, side, 0.85)


def advancement_frame(kind, obtained, van=None):
    """
    발전 과제 칸 26×26 GUI (텍셀 52): 창의 칸과 같은 먹 우물과 한 텍셀 테 (얻은 것은 금빛 테 RIM_GOLD, 못 얻은 것은 쇠 테
    RIM_IRON). 바닐라의 밝은 노랑·회색 판 대신 (2026-10-08 비평: 얻은 칸이 갈색 판에 갈색 곡괭이로 가장 시끄럽고 흐렸다).
    꼴은 바닐라를 따른다: 할 일 (task) 은 네모, 목표 (goal) 는 귀를 둥글게 깎은 네모, 도전 (challenge) 은 바닐라 알파의
    뾰족한 테두리를 단조 쇠 (얻으면 금) 로 두르고 안에 우물. 아이템 (GUI 5..21) 둘레에 우물 바닥이 4 텍셀 이상 남는다.
    """
    W = 52
    img = Img(W, W)
    rim = RIM_GOLD if obtained else RIM_IRON
    ys, xs = np.mgrid[0:W, 0:W] + 0.5
    if kind == "challenge":
        lo, hi = 7, 45
        if van is not None:
            a = np.asarray(van.convert("RGBA"))[..., 3] > 0
            sil = np.repeat(np.repeat(a, 2, 0), 2, 1).astype(np.float32)
            sil[lo - 1:hi + 1, lo - 1:hi + 1] = 0.0
            img.over(uidraw.lit(sil, ADV_POINTS_GOLD if obtained else IRON))
        inside = (xs >= lo) & (xs < hi) & (ys >= lo) & (ys < hi)
    else:
        lo, hi = 4, 48
        inside = (xs >= lo) & (xs < hi) & (ys >= lo) & (ys < hi)
        if kind == "goal":
            r = 11.0
            cx = np.clip(xs, lo + r, hi - r)
            cy = np.clip(ys, lo + r, hi - r)
            inside &= (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
    _shaped_well(img, inside, rim)
    return img


def advancement_sprites(z, out):
    """
    발전 과제 창 안의 그림: 탭 바탕 다섯은 손으로 놓은 돌 쌓기 (advancement_bg), 칸 여섯은 창의 칸 우물 (advancement_frame),
    이름 상자 셋과 탭 스물넷은 바닐라 꼴에 색만 팔레트로 (remap).
    """
    written = []
    base = "assets/minecraft/textures/gui/"
    bg = advancement_bg()
    for n in ("adventure", "end", "husbandry", "nether", "stone"):
        written.append(gsave(bg, out, "advancements", "backgrounds", n + ".png"))
    names = [n[len(base + "sprites/advancements/"):-4] for n in z.namelist()
             if n.startswith(base + "sprites/advancements/") and n.endswith(".png")]
    for n in sorted(names):
        v = _jar_png(z, base + f"sprites/advancements/{n}.png")
        obtained = ("obtained" in n and "unobtained" not in n) or n.endswith("_selected")
        kind = n.split("_frame_")[0] if "_frame_" in n else None
        if kind in ADV_FRAMES:
            written.append(gsave(advancement_frame(kind, obtained, v), out, "sprites", "advancements", n + ".png"))
        else:
            written.append(gsave(remap(v, ADV_GOLD if obtained else ADV_IRON), out, "sprites", "advancements", n + ".png"))
        meta = base + f"sprites/advancements/{n}.png.mcmeta"
        if meta in z.namelist():
            path = os.path.join(out, *GUI, "sprites", "advancements", n + ".png.mcmeta")
            with open(path, "wb") as f:
                f.write(z.read(meta))
    return written


# 효과 그림 (textures/mob_effect, 바닐라 18×18): 꼴은 바닐라, 색은 이로운 것은 그을린 청동, 해로운 것은 녹슨 쇠 (remap).
# 바닐라의 파란 방패 (저항)·푸른 구슬 (구속) 은 마나만 쓰는 파랑이라 효과 판 안에서 튀었다 (2026-10-08 비평).
# UI 전용 계열 (먹 …) 은 textures/gui·font 밖이라 쓰지 않는다
EFFECT_GOOD = ["rust0", "bronze1", "bronze2", "bronze3", "parch2"]
EFFECT_BAD = ["ash0", "rust0", "rust1", "rust2", "rust3"]
EFFECT_HARMFUL = ("bad_omen", "blindness", "darkness", "hunger", "infested", "instant_damage", "levitation", "mining_fatigue",
                  "nausea", "oozing", "poison", "raid_omen", "slowness", "trial_omen", "unluck", "weakness", "weaving",
                  "wind_charged", "wither")


def effect_sprites(z, out):
    """바닐라 효과 그림 40 장을 팔레트로 (꼴은 그대로). 쓴 경로 목록."""
    written = []
    pre = "assets/minecraft/textures/mob_effect/"
    for n in sorted(z.namelist()):
        if not (n.startswith(pre) and n.endswith(".png")):
            continue
        name = n[len(pre):-4]
        v = _jar_png(z, n)
        if v is None:
            continue
        img = remap(v, EFFECT_BAD if name in EFFECT_HARMFUL else EFFECT_GOOD)
        path = os.path.join(out, "assets", "minecraft", "textures", "mob_effect", name + ".png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.image().save(path)
        written.append(path)
    return written


def extra_sprites(out):
    """그 밖의 바닐라 그림을 쓴다. 쓴 경로 목록."""
    written = []
    hud = ("sprites", "hud")
    for k in ("air", "air_empty", "air_bursting"):
        written.append(gsave(air(k), out, *hud, k + ".png"))
    written.append(gsave(effect_bg(24, 24, False), out, *hud, "effect_background.png"))
    written.append(gsave(effect_bg(24, 24, True), out, *hud, "effect_background_ambient.png"))
    inv = ("sprites", "container", "inventory")
    for n, amb in (("effect_background", False), ("effect_background_ambient", True)):
        written.append(gsave(effect_bg(32, 32, amb), out, *inv, n + ".png"))
        save_mcmeta(out, {"type": "nine_slice", "width": 32, "height": 32, "border": SMALL_BORDER}, *inv, n + ".png")
    t = ("sprites", "toast")
    written.append(gsave(toast(160, 32), out, *t, "advancement.png"))
    written.append(gsave(toast(160, 32, light=True), out, *t, "recipe.png"))
    written.append(gsave(toast(160, 32, light=True), out, *t, "tutorial.png"))
    save_mcmeta(out, {"type": "nine_slice", "width": 160, "height": 32, "border": 3}, *t, "tutorial.png")
    written.append(gsave(toast(160, 32), out, *t, "now_playing.png"))
    save_mcmeta(out, {"type": "nine_slice", "width": 160, "height": 32, "border": SMALL_BORDER}, *t, "now_playing.png")
    written.append(gsave(toast(160, 64, mark=True), out, *t, "system.png"))
    save_mcmeta(out, {"type": "nine_slice", "width": 160, "height": 64,
                      "border": {"left": 17, "top": 30, "right": SMALL_BORDER, "bottom": SMALL_BORDER}}, *t, "system.png")
    jar = vanilla_jar()
    van = {}
    if jar:
        with zipfile.ZipFile(jar) as z:
            van["window"] = _jar_png(z, "assets/minecraft/textures/gui/advancements/window.png")
            written += advancement_sprites(z, out)
            written += effect_sprites(z, out)
    written.append(gsave(recipe_book_panel(), out, "recipe_book.png"))
    written.append(gsave(advancement_window(van.get("window")), out, "advancements", "window.png"))
    rb = ("sprites", "recipe_book")
    for craft in (True, False):
        for many in (False, True):
            n = "slot_" + ("many_" if many else "") + ("craftable" if craft else "uncraftable")
            written.append(gsave(recipe_slot(craft, many), out, *rb, n + ".png"))
    written.append(gsave(recipe_tab(False), out, *rb, "tab.png"))
    written.append(gsave(recipe_tab(True), out, *rb, "tab_selected.png"))
    for pre in ("", "furnace_"):
        for en in (True, False):
            for hi in (False, True):
                n = f"{pre}filter_{'enabled' if en else 'disabled'}{'_highlighted' if hi else ''}"
                written.append(gsave(recipe_filter(en, hi), out, *rb, n + ".png"))
                n = f"{pre or 'crafting_'}overlay{'' if en else '_disabled'}{'_highlighted' if hi else ''}"
                written.append(gsave(recipe_overlay_button(en, hi), out, *rb, n + ".png"))
    for fw in (True, False):
        for hi in (False, True):
            n = f"page_{'forward' if fw else 'backward'}{'_highlighted' if hi else ''}"
            written.append(gsave(page_arrow(fw, hi), out, *rb, n + ".png"))
    ov = Img(64, 64)
    small_panel(ov, 0, 0, 64, 64, alpha=0.94)
    written.append(gsave(ov, out, *rb, "overlay_recipe.png"))
    save_mcmeta(out, {"type": "nine_slice", "width": 32, "height": 32, "border": SMALL_BORDER}, *rb, "overlay_recipe.png")
    return written


# ─────────────────────────── 빌드 ───────────────────────────

def build(out):
    """out (팩 뿌리) 에 그림과 .mcmeta 를 쓴다. 쓴 그림 경로 목록을 돌려준다."""
    written = []
    hud = ("sprites", "hud")
    for n in heart_names():
        written.append(save(clear(9, 9), out, *hud, "heart", n + ".png"))
    for n, (w, h) in HIDDEN_HUD.items():
        written.append(save(clear(w, h), out, *hud, n + ".png"))
    written.append(gsave(crosshair(), out, *hud, "crosshair.png"))
    for kind in BOSS_COLORS:
        bg, fill = boss_bar(kind)
        written.append(save(bg, out, "sprites", "boss_bar", kind + "_background.png"))
        written.append(save(fill, out, "sprites", "boss_bar", kind + "_progress.png"))
    written.append(gsave(hotbar(), out, *hud, "hotbar.png"))
    written.append(gsave(selection(), out, *hud, "hotbar_selection.png"))
    written.append(gsave(offhand(False), out, *hud, "hotbar_offhand_left.png"))
    written.append(gsave(offhand(True), out, *hud, "hotbar_offhand_right.png"))
    abg, afg = attack_indicator()
    written.append(save(abg, out, *hud, "hotbar_attack_indicator_background.png"))
    written.append(save(afg, out, *hud, "hotbar_attack_indicator_progress.png"))
    for name in CONTAINER_LAYOUTS:
        written.append(gsave(container(name), out, "container", name + ".png"))
    for state, fname in (("normal", "button"), ("highlighted", "button_highlighted"), ("disabled", "button_disabled")):
        written.append(gsave(button(state), out, "sprites", "widget", fname + ".png"))
        save_mcmeta(out, BUTTON_SCALING, "sprites", "widget", fname + ".png")
    hb, hf = slot_highlight()
    for img, n in ((hb, "slot_highlight_back"), (hf, "slot_highlight_front")):
        written.append(save(img, out, "sprites", "container", n + ".png"))
        save_mcmeta(out, SLOT_HIGHLIGHT_SCALING, "sprites", "container", n + ".png")
    for n in SLOT_ICONS:
        written.append(save(slot_icon(n), out, "sprites", "container", "slot", n + ".png"))
    # 제작법 책 단추: 그림만 지운다 (인벤토리 2×2 자리가 반지 칸이 되었다, 9.4). 누를 자리는 바닐라 그대로라 그 자리를 누르면
    # 빈 제작법 책이 열린다 (이 게임의 플레이어는 제작법을 얻지 않는다: Protection 이 막는다)
    written.append(save(clear(20, 18), out, "sprites", "recipe_book", "button.png"))
    written.append(save(clear(20, 18), out, "sprites", "recipe_book", "button_highlighted.png"))
    for state, fname in (("normal", "warning_button"), ("highlighted", "warning_button_highlighted"),
                         ("disabled", "warning_button_disabled")):
        written.append(gsave(warning_button(state), out, "sprites", "dialog", fname + ".png"))
    wd = ("sprites", "widget")
    for hi in (False, True):
        sfx = "_highlighted" if hi else ""
        written.append(gsave(slider_track(hi), out, *wd, "slider" + sfx + ".png"))
        save_mcmeta(out, BUTTON_SCALING, *wd, "slider" + sfx + ".png")
        written.append(gsave(slider_handle(hi), out, *wd, "slider_handle" + sfx + ".png"))
        save_mcmeta(out, HANDLE_SCALING, *wd, "slider_handle" + sfx + ".png")
        written.append(gsave(checkbox(False, hi), out, *wd, "checkbox" + sfx + ".png"))
        written.append(gsave(checkbox(True, hi), out, *wd, "checkbox_selected" + sfx + ".png"))
        written.append(gsave(text_field(hi), out, *wd, "text_field" + sfx + ".png"))
        save_mcmeta(out, {"type": "nine_slice", "width": 200, "height": 20, "border": 1}, *wd, "text_field" + sfx + ".png")
    for fname, img in small_widgets().items():
        written.append(save(img, out, *wd, fname + ".png"))
        save_mcmeta(out, WIDGET_SCALING[fname], *wd, fname + ".png")
    for fname, bg in (("scroller", False), ("scroller_background", True)):
        written.append(save(scroller(bg), out, *wd, fname + ".png"))
        save_mcmeta(out, WIDGET_SCALING[fname], *wd, fname + ".png")
    for n in SEPARATORS:
        written.append(gsave(separator(), out, n + ".png"))
    written.append(gsave(menu_background(), out, "inworld_menu_background.png"))
    written += extra_sprites(out)
    clash = highlight_marks_unique(out)
    if clash:
        raise ValueError(f"칸 가리킴 표식 (HIGHLIGHT_MARKS) 을 다른 GUI 그림이 쓴다: {clash[:4]}")
    empty = Img(TT * S, TT * S)
    written.append(gsave(tooltip_bg(), out, "sprites", "tooltip", "background.png"))
    written.append(gsave(empty, out, "sprites", "tooltip", "frame.png"))
    for n in ("background", "frame"):
        save_mcmeta(out, TOOLTIP_SCALING, "sprites", "tooltip", n + ".png")
    souls_gui = os.path.join(out, "assets", "souls", "textures", "gui", "sprites", "tooltip")
    for n, img in (("background", tooltip_bg(divider_at=22, top_border=26)), ("frame", empty)):
        p = os.path.join(souls_gui, f"{WEAPON_TOOLTIP}_{n}.png")
        uidraw.save(img.image(), p)
        with open(p + ".mcmeta", "w", encoding="utf-8", newline="\n") as f:
            json.dump({"gui": {"scaling": WEAPON_TOOLTIP_SCALING}}, f, indent=2)
            f.write("\n")
        written.append(p)
    return written


# ─────────────────────────── 미리보기 ───────────────────────────

def _sprite(out, *parts):
    return Image.open(os.path.join(out, *GUI, *parts)).convert("RGBA")


def _big(img, k):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def _down(img, k):
    """k 텍셀 / GUI 그림 → GUI 1 픽셀 (알파를 곱한 넓이 평균, GUI 그림 셰이더와 같은 읽기)."""
    if k == 1:
        return img
    a = np.asarray(img).astype(np.float32) / 255.0
    h, w = a.shape[0] // k, a.shape[1] // k
    a = a[:h * k, :w * k].reshape(h, k, w, k, 4)
    prem = (a[..., :3] * a[..., 3:4]).mean(axis=(1, 3))
    al = a[..., 3].mean(axis=(1, 3))
    rgb = np.where(al[..., None] > 0, prem / np.maximum(al[..., None], 1e-6), 0)
    out = np.concatenate([rgb, al[..., None]], -1)
    return Image.fromarray(np.clip(np.rint(out * 255), 0, 255).astype(np.uint8), "RGBA")


def _gui(out, *parts, gui_w=None):
    """GUI 크기로 읽은 그림 (2 배 그림이면 줄인다). gui_w 를 주면 그 폭이 되는 배율, 없으면 그림 크기로 짐작 (256·512 창)."""
    img = _sprite(out, *parts)
    k = img.width // gui_w if gui_w else (2 if img.width >= 512 else 1)
    return _down(img, max(1, k))


def nine_slice(sprite, w, h, b, stretch_inner=False):
    """1.21 GuiGraphics 처럼: 귀는 그대로, 가장자리와 가운데는 이어 붙인다 (stretch_inner 면 늘인다). b 는 수 또는 dict."""
    if isinstance(b, dict):
        bl, bt, br, bb = b.get("left", 0), b.get("top", 0), b.get("right", 0), b.get("bottom", 0)
    else:
        bl = bt = br = bb = b
    sw, sh = sprite.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def seg(src_box, dst_x, dst_y, dw, dh):
        if dw <= 0 or dh <= 0 or src_box[2] <= src_box[0] or src_box[3] <= src_box[1]:
            return
        src = sprite.crop(src_box)
        if stretch_inner:
            out.alpha_composite(src.resize((dw, dh), Image.NEAREST), (dst_x, dst_y))
            return
        for ty in range(0, dh, src.height):
            for tx in range(0, dw, src.width):
                piece = src.crop((0, 0, min(src.width, dw - tx), min(src.height, dh - ty)))
                out.alpha_composite(piece, (dst_x + tx, dst_y + ty))

    iw, ih = w - bl - br, h - bt - bb
    seg((0, 0, bl, bt), 0, 0, bl, bt)
    seg((sw - br, 0, sw, bt), w - br, 0, br, bt)
    seg((0, sh - bb, bl, sh), 0, h - bb, bl, bb)
    seg((sw - br, sh - bb, sw, sh), w - br, h - bb, br, bb)
    seg((bl, 0, sw - br, bt), bl, 0, iw, bt)
    seg((bl, sh - bb, sw - br, sh), bl, h - bb, iw, bb)
    seg((0, bt, bl, sh - bb), 0, bt, bl, ih)
    seg((sw - br, bt, sw, sh - bb), w - br, bt, br, ih)
    seg((bl, bt, sw - br, sh - bb), bl, bt, iw, ih)
    return out


def hud_scene(out, w, h, sel=1):
    """GUI 픽셀 크기 w×h 의 화면 아래쪽 (단축 슬롯, 왼손 칸)."""
    small = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hud = ("sprites", "hud")
    hx, hy = w // 2 - 91, h - 22
    small.alpha_composite(_gui(out, *hud, "hotbar.png", gui_w=182), (hx, hy))
    small.alpha_composite(_gui(out, *hud, "hotbar_selection.png", gui_w=24), (hx - 1 + sel * 20, hy - 1))
    small.alpha_composite(_gui(out, *hud, "hotbar_offhand_left.png", gui_w=29), (hx - 29, h - 23))
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


def _names(img):
    """2 배 그림의 텍셀마다 (팔레트 이름 또는 None, 알파 0..1)."""
    from palette import name_of
    a = np.asarray(img)
    names = np.empty(a.shape[:2], dtype=object)
    cache = {}
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x, 3] == 0:
                names[y, x] = None
                continue
            key = tuple(int(v) for v in a[y, x, :3])
            if key not in cache:
                cache[key] = name_of(key)
            names[y, x] = cache[key]
    return names, a[..., 3].astype(np.float32) / 255.0


def cell_texels(ours, wells, van=None, marks=()):
    """
    칸마다 자리를 텍셀로 견준다 (ours = 2 배 창 그림). [(텍셀 x, 텍셀 y, 맞음)] 과 어긋난 칸 목록을 돌려준다. 바닐라 칸 상자
    (x, y, 폭, 높이) 에서 아이템 자리 (네모) = GUI (x+1 .. x+폭-2) = 텍셀 [2(x+1), 2(x+폭-1)):
      네모 속 텍셀은 모두 우물 색 (WELL_COLOURS, 알파 0.85 넘게): 보이는 우물이 아이템 자리를 꼭 채운다
      네모 바로 바깥 한 텍셀 (바닐라 그늘·입술 줄의 안쪽 반) 은 칸 테 (RIM_COLOURS)
      바닐라 상자의 가장자리 줄의 바깥 반 텍셀은 우물이 아니다 (보이는 우물이 아이템 자리보다 반 픽셀 넘게 크지 않다)
    van (바닐라 그림) 을 주면 바깥 줄은 바닐라가 그늘·입술로 칠한 픽셀만 본다 (인물 자리의 오른쪽 아래 귀는 왼손 칸이 덮는다).
    marks: 우물 바닥에 그린 흐린 그림의 텍셀 (반지 칸의 흐린 반지): 그 텍셀은 RING_ICON 이면 맞다.
    """
    marks = set(marks)
    names, alpha = _names(ours)
    vx = van.load() if van is not None else None
    checks, bad = [], []
    for x, y, w, h in wells:
        X0, Y0, X1, Y1 = 2 * (x + 1), 2 * (y + 1), 2 * (x + w - 1), 2 * (y + h - 1)
        mine = []
        for yy in range(Y0, Y1):
            for xx in range(X0, X1):
                if (xx, yy) in marks:
                    mine.append(((xx, yy), names[yy, xx] == RING_ICON[0] and alpha[yy, xx] > 0.85))
                else:
                    mine.append(((xx, yy), names[yy, xx] in WELL_COLOURS and alpha[yy, xx] > 0.85))
        rim = [(xx, Y0 - 1) for xx in range(X0 - 1, X1 + 1)] + [(xx, Y1) for xx in range(X0 - 1, X1 + 1)]
        rim += [(X0 - 1, yy) for yy in range(Y0, Y1)] + [(X1, yy) for yy in range(Y0, Y1)]
        mine += [((xx, yy), names[yy, xx] in RIM_COLOURS) for xx, yy in rim]
        outer = [(xx, 2 * y) for xx in range(2 * x, 2 * (x + w))] + [(xx, 2 * (y + h) - 1) for xx in range(2 * x, 2 * (x + w))]
        outer += [(2 * x, yy) for yy in range(2 * y, 2 * (y + h))] + [(2 * (x + w) - 1, yy) for yy in range(2 * y, 2 * (y + h))]
        if vx is not None:
            outer = [(xx, yy) for xx, yy in outer if vx[xx // 2, yy // 2][:3] in (VANILLA_SHADOW, VANILLA_LIP)]
        mine += [((xx, yy), not (names[yy, xx] == "ink0" and alpha[yy, xx] > 0.85)) for xx, yy in outer]
        checks += [(q[0], q[1], ok) for q, ok in mine]
        if not all(ok for _, ok in mine):
            bad.append((x, y, w, h))
    return checks, bad


def _outline(draw, x, y, w, h, k, col):
    draw.rectangle([x * k, y * k, (x + w) * k - 1, (y + h) * k - 1], outline=col)


def align_proof(out, preview_dir, jar):
    """
    align_<창>.png 넷: 바닐라, 우리 그림 (GUI 로 줄인 것), 우리 그림 (2 배 그대로) 위에 바닐라 칸의 경계를 겹친 것 (청록 = 바닐라
    아이템 자리 16×16, 자홍 = 바닐라 칸 18×18), 텍셀 견주기 (cell_texels 가 본 텍셀마다 맞으면 초록, 어긋나면 빨강).
    어긋난 칸이 있으면 셋째 칸에서 그 칸을 빨갛게 칠하고 목록을 돌려준다.
    """
    from PIL import ImageDraw
    k = 4
    report = {}
    with zipfile.ZipFile(jar) as z:
        for name, L in CONTAINER_LAYOUTS.items():
            van = _jar_png(z, f"assets/minecraft/textures/gui/container/{name}.png")
            if van is None:
                continue
            ours2 = _sprite(out, "container", name + ".png")
            w, h = L["size"]
            wells = vanilla_wells(van)
            erased = [b for b in wells if b in L.get("erased", ())]
            wells = [b for b in wells if b not in erased]
            marks = [(2 * (x + i) + dx, 2 * (y + j) + dy) for x, y in L.get("rings", ()) for i, j in ring_placeholder_pixels()
                     for dy in (0, 1) for dx in (0, 1)]
            checks, bad = cell_texels(ours2, wells, van, marks)
            # 지운 칸 (반지 칸 B 안의 오른쪽 두 칸과 결과 칸): 바닐라 칸 상자 안에 우물·칸 테 색이 하나도 없다
            names2, _ = _names(ours2)
            for x, y, ww, hh in erased:
                box = [(xx, yy) for yy in range(2 * y, 2 * (y + hh)) for xx in range(2 * x, 2 * (x + ww))]
                gone = [((xx, yy), names2[yy, xx] not in WELL_COLOURS + RIM_COLOURS) for xx, yy in box]
                checks += [(q[0], q[1], ok) for q, ok in gone]
                if not all(ok for _, ok in gone):
                    bad.append((x, y, ww, hh))
            report[name] = (len(wells), bad, len(checks), sum(1 for c_ in checks if not c_[2]), len(erased))
            back = Image.new("RGBA", (w * k, h * k), (40, 40, 44, 255))
            a = back.copy()
            a.alpha_composite(_big(van.crop((0, 0, w, h)), k))
            b = back.copy()
            b.alpha_composite(_big(_down(ours2, 2).crop((0, 0, w, h)), k))
            over = back.copy()
            over.alpha_composite(_big(ours2.crop((0, 0, 2 * w, 2 * h)), k // 2))
            d = ImageDraw.Draw(over)
            for x, y, ww, hh in wells:
                _outline(d, x, y, ww, hh, k, (255, 0, 255, 255))
                _outline(d, x + 1, y + 1, ww - 2, hh - 2, k, (0, 255, 255, 255))
            for x, y, ww, hh in bad:
                d.rectangle([x * k, y * k, (x + ww) * k - 1, (y + hh) * k - 1], fill=(255, 0, 0, 160))
            diff = Image.blend(a, b, 0.5).point(lambda v: v // 3)
            dd = ImageDraw.Draw(diff)
            hk = k // 2
            for x, y, ok in checks:
                dd.rectangle([x * hk, y * hk, x * hk + hk - 1, y * hk + hk - 1], fill=(40, 200, 90, 255) if ok else (255, 30, 30, 255))
            gap = 12
            panels = (a, b, over, diff)
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
        # 단축 슬롯: 칸 상자 (2+20k, 2) 18×18 의 아이템 자리 (3+20k, 3) 16×16 이 우물, 바로 바깥 한 텍셀이 쇠 테. 고른 칸 테의 속
        # (4..19) 에 들어온 그림 텍셀 수도 센다 (초안 그대로: 네 귀 꼭지와 위 가운데 마름모 끝이 반 픽셀 남짓 들어온다)
        hb = _sprite(out, "sprites", "hud", "hotbar.png")
        names, alpha = _names(hb)
        bad = []
        for i in range(9):
            X0 = 2 * (3 + 20 * i)
            ok = all(names[yy, xx] in WELL_COLOURS for yy in range(6, 38) for xx in range(X0, X0 + 32))
            ok = ok and all(names[yy, xx] in RIM_COLOURS for xx, yy in ((X0 - 1, 20), (X0 + 32, 20), (X0 + 10, 5), (X0 + 10, 38)))
            if not ok:
                bad.append(i)
        report["hotbar"] = (9, bad)
        hs = _sprite(out, "sprites", "hud", "hotbar_selection.png")
        ha = np.asarray(hs)[..., 3]
        report["selection_hole"] = int((ha[8:40, 8:40] > 0).sum())
        _hotbar_proof(preview_dir, _jar_png(z, "assets/minecraft/textures/gui/sprites/hud/hotbar.png"),
                      _down(hb, 2), _down(hs, 2), _jar_png(z, "assets/minecraft/textures/gui/sprites/hud/hotbar_selection.png"), k)
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
    # 인벤토리 칸 차례: 갑옷 0..3, 왼손 4, 반지 칸 5·6, 가방 7..33, 단축 줄 34..42. 반지 칸 5 에는 팩의 시험 반지 (MOCK_RINGS)
    "inventory": {7: ("item/iron_helmet", 1), 11: ("item/bread", 24), 16: ("item/iron_sword", 1), 20: ("item/bone", 3),
                  34: ("item/flint", 5), 35: ("item/coal", 9), 36: ("item/netherite_ingot", 1), 38: ("item/rotten_flesh", 7),
                  39: ("item/stick", 2), 40: ("item/iron_axe", 1)},
    "crafting_table": {1: ("item/stick", 1), 4: ("item/stick", 1), 7: ("item/iron_ingot", 1), 14: ("item/bread", 24),
                       30: ("item/iron_sword", 1), 31: ("item/coal", 9), 32: ("item/flint", 3)},
    "generic_54": {3: ("item/rotten_flesh", 7), 13: ("item/bone", 2), 20: ("item/coal", 12), 21: ("item/flint", 4),
                   30: ("item/iron_axe", 1), 60: ("item/bread", 24), 82: ("item/iron_sword", 1), 83: ("item/netherite_ingot", 1)},
}
# 미리보기의 반지 칸에 끼울 팩의 반지 그림 (칸 차례 → 모형 이름): 흐린 반지를 덮는지 본다
MOCK_RINGS = {"inventory": {5: "ring_test_stamina"}}
# 제목 글 (바닐라 언어 열쇠 container.* 를 lang 의 vanilla.container.* 가 덮는다). 미리보기는 그 글을 §7 회색으로 쓴다.
# 인벤토리의 "제작" 은 반지 칸이 되며 비웠다 (9.4)
TITLES = {
    "inventory": (),
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


def _backdrop(w, h, gui):
    """게임 중 창 뒤: 저녁 세상을 바닐라 창 덧칠 (위 0xC0101010 → 아래 0xD0101010) 로 가라앉힌 것."""
    import previews as pv
    from PIL import ImageDraw
    im = pv.dusk_scene(w * gui, h * gui)
    ov = Image.new("RGBA", im.size)
    d = ImageDraw.Draw(ov)
    for y in range(im.height):
        a = int(0xC0 + (0xD0 - 0xC0) * y / max(1, im.height - 1))
        d.line([(0, y), (im.width, y)], fill=(16, 16, 16, a))
    im.alpha_composite(ov)
    return im


def _mock_container(out, name, lang, z, gui=3, rows=6):
    """
    창 하나를 GUI 배율 gui 로: 판, 아이템, 제목 글 (언어 파일이 §7 로 바꾼 회색), 인벤토리는 제작법 책 단추와 빈 칸 그림,
    고른 칸 가리킴. generic_54 는 rows 줄 상자 (3 이면 한 칸 상자).
    """
    import previews as pv
    L = CONTAINER_LAYOUTS[name]
    pw, ph = L["size"]
    panel_img = _gui(out, "container", name + ".png").crop((0, 0, pw, ph))
    wells, titles, items = list(L["wells"]), list(L["titles"]), dict(MOCK_ITEMS[name])
    if name == "generic_54" and rows != 6:
        panel_img = chest_rows(panel_img, rows)
        shift = (6 - rows) * 18 + 1      # 아래 판: 그림 126 줄이 화면 rows×18+17 줄
        wells = [(x, y) for x, y in wells if y < 17 + rows * 18] + [(x, y - shift) for x, y in wells if y >= 126]
        titles = [titles[0], (titles[1][0], titles[1][1] - shift)]
        items = {(i if i < 54 else i - (6 - rows) * 9): v for i, v in items.items() if i < rows * 9 or i >= 54}
        ph = panel_img.height
    pad = 10
    big = _backdrop(pw + 2 * pad, ph + 2 * pad, gui)
    small = Image.new("RGBA", (pw + 2 * pad, ph + 2 * pad), (0, 0, 0, 0))
    small.alpha_composite(panel_img, (pad, pad))
    slots = [(x + 1, y + 1) for x, y in wells]
    if L["result"]:
        rx, ry, rw, rh = L["result"][0]
        slots.append((rx + (rw - 16) // 2, ry + (rh - 16) // 2))
    if name == "inventory":
        small.alpha_composite(_sprite(out, "sprites", "recipe_book", "button.png"), (pad + 104, pad + 61))   # 투명 (9.4)
        icon_slots = {0: "helmet", 1: "chestplate", 2: "leggings", 3: "boots", 4: "shield"}
        for i, n in icon_slots.items():
            small.alpha_composite(_sprite(out, "sprites", "container", "slot", n + ".png"), (pad + slots[i][0], pad + slots[i][1]))
    if name == "crafting_table":
        small.alpha_composite(_sprite(out, "sprites", "recipe_book", "button_highlighted.png"), (pad + 5, pad + 34))
    hover = {"inventory": 18, "crafting_table": 20, "generic_54": 22}[name]
    hx, hy = slots[hover]
    small.alpha_composite(_sprite(out, "sprites", "container", "slot_highlight_back.png"), (pad + hx - 4, pad + hy - 4))
    counts = []
    for i, model in MOCK_RINGS.get(name, {}).items():
        p = os.path.join(out, "assets", "souls", "textures", "item", model + ".png")
        if os.path.exists(p) and i < len(slots):
            small.alpha_composite(Image.open(p).convert("RGBA"), (pad + slots[i][0], pad + slots[i][1]))
    if z is not None:
        for i, (tex, n) in items.items():
            im = _jar_png(z, f"assets/minecraft/textures/{tex}.png")
            if im is not None and i < len(slots):
                small.alpha_composite(im.crop((0, 0, 16, 16)), (pad + slots[i][0], pad + slots[i][1]))
                if n > 1:
                    counts.append((slots[i], str(n)))
    small.alpha_composite(_sprite(out, "sprites", "container", "slot_highlight_front.png"), (pad + hx - 4, pad + hy - 4))
    big.alpha_composite(_big(small, gui))
    key = name if rows == 6 else f"{name}/{rows}"
    for (tx, ty), text in zip(titles, TITLES[key]):
        m = pv.unifont_text(text[0 if lang == "ko" else 1], gui)
        if m is not None:
            big.paste(Image.new("RGBA", m.size, TITLE_GRAY), ((pad + tx) * gui, (pad + ty) * gui), m)
    for (sx, sy), n in counts:
        m = pv.unifont_text(n, gui)
        if m is not None:
            x, y = (pad + sx + 17) * gui - m.width, (pad + sy + 9) * gui
            big.paste(Image.new("RGBA", m.size, (63, 63, 63, 255)), (x + gui, y + gui), m)
            big.paste(Image.new("RGBA", m.size, (255, 255, 255, 255)), (x, y), m)
    return big


def write_previews(out, preview_dir):
    import previews as pv
    os.makedirs(preview_dir, exist_ok=True)
    gui = 3
    w, h = 427, 40
    rows = []
    for sel in (1, 4):
        scene = pv.dusk_scene(w * gui, h * gui * 3).crop((0, h * gui * 2, w * gui, h * gui * 3))
        scene.alpha_composite(_big(hud_scene(out, w, h, sel=sel), gui))
        rows.append(scene)
    sheet = Image.new("RGBA", (w * gui, sum(r.height for r in rows) + 4), (12, 12, 12, 255))
    sheet.alpha_composite(rows[0], (0, 0))
    sheet.alpha_composite(rows[1], (0, rows[0].height + 4))
    sheet.crop((w * gui // 2 - 330, 0, w * gui // 2 + 330, sheet.height)).save(os.path.join(preview_dir, "gui_hud.png"))

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

    # 단추 (사망 화면 크기 200, 일시정지 화면 크기 98·204), 설명 칸, Dialog 경고 단추, 설정 위젯, 보스 막대
    W2, H2 = 427, 200
    canvas = pv.dusk_scene(W2 * gui, H2 * gui)
    canvas.alpha_composite(pv.death_overlay(W2 * gui, H2 * gui))
    small = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    btns = [("button", 200, 20, 113, 10, "일어선다"), ("button_highlighted", 200, 20, 113, 34, "그만둔다"),
            ("button_disabled", 200, 20, 113, 58, "일어선다"), ("button", 98, 20, 10, 90, "설정"),
            ("button_highlighted", 98, 20, 112, 90, "통계"), ("button", 204, 20, 214, 90, "게임으로 돌아가기")]
    for spr, bw, bh, bx, by, _ in btns:
        small.alpha_composite(nine_slice(_gui(out, "sprites", "widget", spr + ".png", gui_w=200), bw, bh,
                                         BUTTON_SCALING["border"]), (bx, by))
    for i, st in enumerate(("warning_button", "warning_button_highlighted", "warning_button_disabled")):
        small.alpha_composite(_gui(out, "sprites", "dialog", st + ".png", gui_w=20), (10 + 24 * i, 120))
    wd = ("sprites", "widget")
    sliders = []
    for i, (hi, val) in enumerate(((False, 0.35), (True, 0.7))):
        sfx = "_highlighted" if hi else ""
        sx, sy = 214 + i * 104, 116
        small.alpha_composite(nine_slice(_gui(out, *wd, "slider" + sfx + ".png", gui_w=200), 98, 20, BUTTON_SCALING["border"]), (sx, sy))
        small.alpha_composite(_gui(out, *wd, "slider_handle" + sfx + ".png", gui_w=8), (sx + int(val * 90), sy))
        sliders.append((sx + 49, sy + 6, "시야: 70" if i == 0 else "밝기: 50%"))
    for i, n in enumerate(("checkbox", "checkbox_highlighted", "checkbox_selected", "checkbox_selected_highlighted")):
        small.alpha_composite(_gui(out, *wd, n + ".png", gui_w=20).resize((17, 17), Image.NEAREST), (90 + 20 * i, 121))
    small.alpha_composite(nine_slice(_gui(out, *wd, "text_field.png", gui_w=200), 90, 20, 1), (10, 148))
    small.alpha_composite(nine_slice(_gui(out, *wd, "text_field_highlighted.png", gui_w=200), 90, 20, 1), (110, 148))
    small.alpha_composite(nine_slice(_gui(out, *wd, "scroller_background.png", gui_w=6), 6, 50,
                                     WIDGET_SCALING["scroller_background"]["border"]), (412, 130))
    small.alpha_composite(nine_slice(_gui(out, *wd, "scroller.png", gui_w=6), 6, 20, WIDGET_SCALING["scroller"]["border"]),
                          (412, 146))
    tb = _gui(out, "sprites", "tooltip", "background.png", gui_w=TT)
    for tx, ty, tw, th in ((330, 14, 80, 30), (24, 14, 70, 60)):
        small.alpha_composite(nine_slice(tb, tw + 24, th + 24, 14), (tx - 12, ty - 12))
    for i, kind in enumerate(("yellow",)):     # 보스 체력 (red) 은 그림 글자 막대라 hud.png 에 있다. 이것은 쓰지 않는 색의 막대
        bx, by = 122, 176 + 8 * i
        small.alpha_composite(_sprite(out, "sprites", "boss_bar", kind + "_background.png"), (bx, by))
        small.alpha_composite(_sprite(out, "sprites", "boss_bar", kind + "_progress.png").crop((0, 0, 120, 5)), (bx, by))
    canvas.alpha_composite(_big(small, gui))
    for spr, bw, bh, bx, by, text in btns:
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
            n, bad, npx, badpx, nerased = report[name]
            print(f"  칸 자리 {name}: 바닐라 칸 {n}개 (인벤토리는 인물 자리 하나 포함), 지운 칸 {nerased}개, 어긋난 칸 {len(bad)}, "
                  f"견준 텍셀 {npx}개 중 어긋남 {badpx}" + (f" {bad}" if bad else ""))
        n, bad = report["hotbar"]
        print(f"  칸 자리 hotbar: 칸 {n}개, 어긋남 {len(bad)}, 선택 테 구멍 안의 그림 텍셀 {report['selection_hole']}")
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
