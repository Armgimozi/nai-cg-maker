"""
바닐라 HUD·GUI 그림을 다크 소울 3 의 말씨로 다시 그린다 (DESIGN.md 10.2, 10.4, 10.5, ART_DIRECTION.md).
gen_pack.py 가 hud.build 다음에 부른다.

말씨 (2026-10-07 사용자 결정: 거무칙칙한 시안 넷이 다 마음에 들지 않았다. "보자마자 다크 소울" 인 UI)
  창·단추·설명 칸은 다크 소울 3 의 메뉴처럼: 흐리게 한 세상 위에 반투명한 검은 판 (알파 72%), 판 가장자리 두 줄은
  알파 두 단 (35% · 60%) 으로 옅어지고, 그 안쪽 (가장자리에서 2) 에 1픽셀 탁한 금빛 (바랜 양피지·청동 베이지) 줄 (긴 줄은 탁하게,
  밝은 금빛은 귀와 장식에만), 장식은 절제해서 네 귀의 꺾쇠와 위 가운데의 작은 마름모 하나뿐. 칸은 따뜻하고 어두운 가는 테를
  두른 먹빛 우물 (판보다 진해 꺼져 보인다),
  가리키면 칸 둘레에 밝은 금빛 테가 또렷이 선다. 글은 바닐라 글 (흰색·회색) 그대로. 깔끔하고 단정하게, 거칠거나
  시끄럽지 않게: 녹 점·긁힘·마모·베벨은 모두 뺐다.
  모든 색은 palette.c(이름, 알파) 하나에서 (RGB 는 팔레트, 알파만 자유. 발광 알파 250~252 는 쓰지 않는다).

  층과 색 (모두 이름 하나에 한 자리)
    판     재 (ash0) 알파 PANEL_A. 가장자리 FADE 두 단. 그 안쪽 (가장자리에서 2) 에 금빛 줄 (LINE)
    칸     아이템 자리 16×16 이 곧 보이는 네모다: 가장자리 한 줄이 칸 테 (CELL_EDGE), 속 14×14 가 칸 바닥 (CELL_FLOOR,
           판보다 진하다). 바닐라 칸의 그늘·입술 줄 (아이템 자리 바깥 한 줄) 은 판 그대로라, 이웃 칸 사이에 판이 2픽셀
           비친다 (다크 소울 3 의 칸처럼 떨어진 네모). 아이템은 네모 한가운데에 꼭 맞는다
    결과 칸 테가 금빛 (만들어져 나오는 자리). 제작대의 큰 결과 칸 (26×26) 은 속 24×24 가 네모
    인물 자리 인벤토리의 인물 자리도 같은 네모 (속 50×70), 바닥은 가장 진하다
    나눔줄 1픽셀 금빛 줄, 양 끝은 알파 계단으로 사라진다
    화살표 1픽셀 금빛 줄과 꺾쇠 촉

칸 자리 (사용자: "장비칸이 어긋났다". 지금도 바닐라와 픽셀까지 같다)
  칸은 바닐라 jar 와 한 픽셀도 다르지 않다 (CONTAINER_LAYOUTS). 바닐라 칸 (x, y, 18×18) 에서 아이템 자리는 x+1..x+16 이고
  우리 칸 네모가 꼭 그 자리다: 네모의 가장자리 한 줄 (x+1, x+16 열과 y+1, y+16 줄) 이 칸 테, 속 (x+2..x+15) 이 바닥.
  바닐라의 그늘 줄 (위·왼쪽, x 와 y) 과 입술 줄 (아래·오른쪽, x+17 과 y+17) 자리는 칸 색이 아니다 (판).
  write_previews 가 cell_pixels 로 칸마다 견주고 align_*.png 다섯째 칸에 초록 (맞음) / 빨강 (어긋남) 으로 보인다.

그리는 것 (크기·경로는 1.21.11 클라이언트 jar 와 같다. 9조각 값은 우리 그림에 맞춰 .mcmeta 를 같이 쓴다)
  숨기는 HUD  하트 (gui/sprites/hud/heart/* 모두), 방어 (armor_*), 경험치 막대 (experience_bar_*), 조준점 밑 공격 대기 표시를
              투명하게. 조준점 (crosshair) 은 가운데 어두운 한 점만. 허기는 hud.py 가 투명하게 한다.
              체력·온기·스태미나는 왼쪽 위의 막대 셋 (hud.py 의 그림 글자, 플러그인 Hud)
  보스 막대   boss_bar/white_* (HUD 막대 셋) 와 red_* (보스: 화면 아래 가운데의 그림 글자 막대, hud.py) 는 투명.
              나머지 색은 같은 말씨의 가는 진홍 막대 (이 게임은 쓰지 않는다)
  단축 슬롯   hotbar 182×22 (테 없는 반투명 먹 우물 아홉), hotbar_selection 24×23 (밝은 금빛 테: 고른 칸만 테),
              hotbar_offhand_left/right 29×24, hotbar_attack_indicator_background/progress 18×18 (단검)
  창          container/inventory.png, generic_54.png, crafting_table.png (256×256)
              container/slot_highlight_back/front (가리킨 칸: 바닥이 데워지고 둘레에 금빛 테), container/slot/* 빈 칸 그림
  단추        widget/button, button_highlighted, button_disabled 200×20: 상자가 아니라 위·아래 가는 줄의 띠 (가리키면 따뜻한
              회색 띠와 양 끝 마름모). 사망 화면 "일어선다 / 그만둔다" 도 이 그림
              recipe_book/button(_highlighted) 20×18
  설정 화면   widget/slider(_highlighted), slider_handle(_highlighted), checkbox(_selected)(_highlighted), text_field(_highlighted),
              tab(_selected)(_highlighted), scroller(_background), textures/gui/(inworld_)header·footer_separator,
              textures/gui/inworld_menu_background (게임 중 메뉴 뒤의 반투명 검정. 바닐라보다 진하게)
  설명 칸     tooltip/background, tooltip/frame 100×100: 반투명 검정 + 계단 가장자리 + 금빛 줄 + 귀 꺾쇠
  Dialog      dialog/warning_button(_highlighted, _disabled) 20×20

  python3 pack/gui_skin.py [팩폴더] [미리보기폴더]
      그림만 다시 그리고 미리보기(gui_hud, gui_containers, gui_widgets, align_*)를 쓴다 (팩은 묶지 않는다)
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


# ─────────────────────────── 말씨: 색의 자리 ───────────────────────────

INK = "ash0"                       # 검정 (재): 판·단추의 바탕은 이 색에 알파만 다르다
WELL = "ink0"                      # 더 진한 검정 (먹, UI 전용): 칸 우물 바닥, 인물 자리
PANEL_A = 185                      # 판 몸 (72%: 흐린 세상이 비친다. 2026-10-08 비평: 78% 는 어두운 세상과 같은 색이라 딱딱한 상자로 읽혔다)
FADE = (89, 153)                   # 판 가장자리 두 단 (바깥 → 안, 35% · 60%). 그 안쪽 (가장자리에서 2) 이 금빛 줄
PANEL = (INK, PANEL_A)
LINE = ("parch0", 255)             # 가는 금빛 줄의 긴 몫: 탁하게 (긴 줄이 밝으면 GUI 배율 3 에서 3픽셀 굵기로 무겁다)
LINE_DIM = ("parch0", 200)         # 나눔줄, 꺾쇠 끝
ORN = ("parch2", 255)              # 장식 (귀 꺾쇠, 위 가운데 마름모) 의 밝은 금빛: 밝은 값은 귀와 장식에만
ORN_HI = ("parch3", 255)           # 가리킨 칸의 테, 마름모 꼭짓점 한 점
CELL_EDGE = ("ink1", 255)          # 칸 테: 따뜻하고 어두운 갈색 (회색 테 쉰 개가 화면에서 가장 시끄러웠다)
CELL_FLOOR = (WELL, 204)           # 칸 바닥: 판보다 진한 먹 (80%) 이라 칸이 우물처럼 꺼져 보인다
ALCOVE_FLOOR = (WELL, 225)         # 인물 자리 바닥: 창에서 가장 진하다 (250~252 는 발광 알파라 쓰지 않는다)
RESULT_EDGE = ("bronze3", 255)     # 결과 칸 테: 금빛
ICON = ("parch0", 170)             # 빈 갑옷·방패 칸에 비치는 흐린 그림


def panel(cv, w, h, x0=0, y0=0, inset=2, line=LINE, fill=PANEL, fade=FADE):
    """
    반투명 검은 판 (w×h, (x0, y0) 에서). 가장자리 len(fade) 줄은 알파 계단, 그 안쪽 inset 자리에 1픽셀 줄, 안은 fill.
    네 귀는 한 칸 깎아 (가장 바깥 귀 점을 비운다) 딱딱한 모서리를 누그러뜨린다.
    """
    for y in range(h):
        for x in range(w):
            d = min(x, y, w - 1 - x, h - 1 - y)
            corner = min(x, w - 1 - x) + min(y, h - 1 - y)
            if corner == 0:
                continue
            if d < len(fade):
                a = fade[d] if corner > 1 else fade[0] // 2
                cv.put(x0 + x, y0 + y, (INK, a))
            elif d == inset and line:
                cv.put(x0 + x, y0 + y, line)
            else:
                cv.put(x0 + x, y0 + y, fill)


def corner_ornaments(cv, w, h, inset=2, arm=4):
    """
    네 귀의 꺾쇠: 금빛 줄의 귀에서 양쪽으로 arm 칸이 밝은 금빛 (ORN), 그 끝 한 칸은 다시 보통 줄. 안쪽 대각선 두 칸 자리에
    점 하나 (LINE_DIM). 네 귀가 서로 거울상이다 (다크 소울 3 의 창 귀처럼 단정하게).
    """
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx = inset if sx > 0 else w - 1 - inset
        cy = inset if sy > 0 else h - 1 - inset
        for i in range(arm):
            cv.put(cx + sx * i, cy, ORN)
            cv.put(cx, cy + sy * i, ORN)
        cv.put(cx + sx * 2, cy + sy * 2, LINE_DIM)


# 위 가운데 마름모 (금빛 줄 위에 걸친다). 짝수 폭이라 판 폭이 짝수여도 꼭 가운데다. A 밝은 금빛, H 가장 밝은 점,
# L 보통 줄, k 판보다 진한 속
FLOURISH = [
    "..HA..",
    ".AkkA.",
    "AkkkkA",
    ".AkkA.",
    "..AA..",
]


def flourish(cv, w, y_line=2):
    cx = w // 2 - 3
    cv.stamp(cx, y_line - 2, FLOURISH, {"A": ORN, "H": ORN_HI, "k": CELL_FLOOR, "L": LINE})
    # 마름모 양옆 세 칸은 줄이 한 단 밝다 (마름모에서 번지는 빛이 아니라 장식의 일부인 짧은 날개)
    for i in range(1, 4):
        cv.put(cx - i, y_line, ORN if i < 3 else LINE)
        cv.put(cx + 5 + i, y_line, ORN if i < 3 else LINE)


def cell(cv, x, y, w=18, h=18, edge=CELL_EDGE, floor=CELL_FLOOR):
    """
    바닐라 칸 상자 (x, y, w×h) 안의 우리 칸: 바닐라의 그늘·입술 줄 (상자 가장자리 한 줄) 은 건드리지 않고 (판),
    그 안 (x+1..x+w-2) 가 보이는 네모다. 네모의 가장자리 한 줄이 테, 속이 바닥. 18×18 이면 네모가 꼭 아이템 자리 16×16.
    """
    cv.rect(x + 1, y + 1, x + w - 2, y + h - 2, floor)
    cv.box(x + 1, y + 1, x + w - 2, y + h - 2, edge)


def divider(cv, x0, x1, y, col=LINE_DIM, steps=(60, 110, 160, 210)):
    """1픽셀 금빛 나눔줄 (x0..x1+1), 양 끝은 알파 계단으로 사라진다."""
    n = x1 + 1 - x0
    for i in range(n + 1):
        d = min(i, n - i)
        a = steps[d] if d < len(steps) else 255
        cv.put(x0 + i, y, (col[0], a))


def arrow(cv, x0, x1, ym, half):
    """제작 화살표 (바닐라 자리): 1픽셀 금빛 자루 (꼬리는 알파 계단) 와 꺾쇠 촉 (두 갈래 45°)."""
    for x in range(x0, x1 + 1):
        d = x - x0
        cv.put(x, ym, LINE if d >= 3 else (LINE[0], (90, 150, 210)[d]))
    for k in range(1, half + 1):
        a = ORN if k < half - 1 else LINE
        cv.put(x1 - k, ym - k, a)
        cv.put(x1 - k, ym + k, a)


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


def crosshair():
    """
    조준점 15×15 (2026-10-08 비평: 다크 소울에는 조준점이 없다. 굵은 + 가 YOU DIED 밑과 반투명 창 뒤에도 비쳤다).
    가운데 한 점만 어두운 재로 남긴다 (바닐라는 조준점을 뒤 색을 뒤집어 섞어 그린다: 어두운 바탕에서는 조금 밝은 점,
    밝은 하늘에서는 조금 어두운 점이 되어 겨눌 자리만 겨우 보인다).
    """
    cv = Cv(15, 15)
    cv.put(7, 7, ("ash1", 255))
    return cv.image()


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


# ─────────────────────────── 단축 슬롯 ───────────────────────────

HOTBAR_WELL = (WELL, 100)           # 고르지 않은 칸: 테 없이 40% 먹 우물 (다크 소울에는 단축 슬롯이 없다. 고른 칸만 테를 두른다)
HOTBAR_RIM = (WELL, 130)            # 우물 가장자리 한 줄은 조금 더 진하다 (테가 아니라 우물의 그늘)


def hotbar():
    """
    182×22. 따로 떨어진 반투명 먹 우물 아홉 (2026-10-08 비평: 테 두른 칸 아홉이 시끄러웠다): 칸 상자 (2+20k .. 19+20k, 2..19)
    의 가장자리 한 줄이 조금 진한 그늘, 속 16×16 이 꼭 아이템 자리 (3+20k, 3). 칸 사이와 둘레는 비운다. 고른 칸의 금빛 테는
    hotbar_selection 이 그린다.
    """
    W, H = 182, 22
    cv = Cv(W, H)
    for k in range(9):
        x = 2 + 20 * k
        cv.rect(x + 1, 3, x + 16, 18, HOTBAR_WELL)
        cv.box(x, 2, x + 17, 19, HOTBAR_RIM)
    return cv.image()


def hotbar_selection():
    """
    24×23. 바닐라처럼 단축 슬롯보다 한 칸 왼쪽 위에서 그린다: 고른 칸의 테 (3..20) 가 밝은 금빛, 그 바깥 한 줄 (2..21) 은
    옅은 금빛, 네 귀 바깥에 꺾쇠 점. 속 (4..19) 은 비운다 (아이템 자리).
    """
    cv = Cv(24, 23)
    cv.box(2, 2, 21, 21, ("parch1", 140))
    cv.box(3, 3, 20, 20, ORN)
    for x, y in ((3, 3), (20, 3), (3, 20), (20, 20)):
        cv.put(x, y, ORN_HI)
    for (x, y, sx, sy) in ((1, 1, 1, 1), (22, 1, -1, 1), (1, 22, 1, -1), (22, 22, -1, -1)):
        cv.put(x, y, LINE)
        cv.put(x + sx, y, LINE)
        cv.put(x, y + sy, LINE)
    return cv.image()


def offhand(right):
    """왼손 칸 29×24. 칸 상자는 (x0+2, 3) 18×18 (왼쪽 x0 = 0, 오른쪽 7), 아이템은 (x0+3, 4). 단축 슬롯 칸과 같은 얼굴."""
    cv = Cv(29, 24)
    x0 = 7 if right else 0
    cv.rect(x0 + 3, 4, x0 + 18, 19, HOTBAR_WELL)
    cv.box(x0 + 2, 3, x0 + 19, 20, HOTBAR_RIM)
    return cv.image()


# 단축 슬롯 옆 공격 대기 표시 (설정에서 "단축 슬롯" 을 고른 사람만 본다): 가는 금빛 단검 윤곽
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
        "wells": [(7, 7 + 18 * i) for i in range(4)] + [(76, 61)] + _grid(97, 17, 2, 2)
                 + _grid(7, 83, 9, 3) + _grid(7, 141, 9, 1),
        "result": [(153, 27, 18, 18)],
        "alcove": (25, 7, 51, 72),
        "arrow": (135, 150, 35, 6),
        "titles": [(97, 6)],
        "dividers": [(7, 167, 80), (7, 167, 138)],
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


def container(name):
    L = CONTAINER_LAYOUTS[name]
    w, h = L["size"]
    cv = Cv(256, 256)
    panel(cv, w, h)
    corner_ornaments(cv, w, h)
    flourish(cv, w)
    if L["alcove"]:          # 칸보다 먼저: 왼손 칸 네모가 인물 자리 오른쪽 아래 귀 옆에 붙는다 (바닐라와 같은 자리)
        x, y, aw, ah = L["alcove"]
        cell(cv, x, y, aw, ah, floor=ALCOVE_FLOOR)
    for x, y in L["wells"]:
        cell(cv, x, y)
    for x, y, rw, rh in L["result"]:
        cell(cv, x, y, rw, rh, edge=RESULT_EDGE)
    if L["arrow"]:
        arrow(cv, *L["arrow"])
    for x0, x1, y in L["dividers"]:
        divider(cv, x0, x1, y)
    return cv.image()


# ─────────────────────────── 칸 가리킴, 빈 칸 그림 ───────────────────────────

SLOT_HIGHLIGHT_SCALING = {"type": "nine_slice", "width": 24, "height": 24, "border": 4}


def slot_highlight():
    """
    마우스가 올라간 칸 (24×24, 아이템 자리는 4..19). 뒤 (아이템 아래): 칸 속 (5..18) 이 옅은 금빛으로 데워진다.
    앞 (아이템 위): 칸 네모 바로 바깥 (3..20, 바닐라의 그늘·입술 자리라 아이템을 가리지 않는다) 에 밝은 금빛 테,
    네 귀는 가장 밝은 점. 또렷하되 칸 하나만큼만.
    """
    back, front = Cv(24, 24), Cv(24, 24)
    back.rect(5, 5, 18, 18, ("parch0", 70))
    front.box(3, 3, 20, 20, ORN)
    for x, y in ((3, 3), (20, 3), (3, 20), (20, 20)):
        front.put(x, y, ORN_HI)
    return back.image(), front.image()


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


# ─────────────────────────── 단추 ───────────────────────────

# 단추 200×20. 9조각: 위·아래 3, 양옆 6 (양 끝의 작은 마름모가 늘어나지 않게). 단추는 거의 늘 높이 20 이라 양옆 조각이
# 그대로 찍힌다.
BUTTON_BORDER = {"left": 6, "top": 3, "right": 6, "bottom": 3}
BUTTON_SCALING = {n: {"type": "nine_slice", "width": 200, "height": 20, "border": BUTTON_BORDER}
                  for n in ("button", "button_highlighted", "button_disabled")}
# 단추 (2026-10-08 비평: 테를 두른 상자 단추와 갈색 "널빤지" 가리킴은 마인크래프트로 보였다). 다크 소울 3 의 메뉴 줄처럼
# 띠 위의 글: 테의 세로 변이 없고, 위·아래 가는 줄 (단추 안쪽 1줄) 만 양 끝으로 옅어진다. 가리키면 따뜻한 회색 띠가 양 끝으로
# 옅어지며 깔리고, 줄이 밝아지고, 양 끝에 작은 마름모가 선다. 끝의 옅어짐은 9조각의 양옆 조각 (6) 안에 있어 늘어나지 않는다.
BUTTON_TONES = {
    #               바탕 띠 (색, 알파)     위·아래 줄             양 끝 마름모
    "normal":      ((INK, 55),          ("parch1", 90),       None),
    "highlighted": (("ash3", 72),       ("parch2", 200),      ORN_HI),
    "disabled":    ((INK, 30),          ("ash2", 70),         None),
}
BUTTON_ENDS = (0.15, 0.3, 0.5, 0.7, 0.85, 1.0)   # 양 끝 여섯 열의 알파 몫 (바깥 → 안)
# 제작법 책·Dialog 경고처럼 그림이 든 작은 네모 단추: 상자 꼴 그대로 (띠 위의 그림은 읽히지 않는다)
SQUARE_TONES = {
    "normal":      ((INK, 165), ("parch0", 200), None),
    "highlighted": (("ash3", 90), ORN, ORN_HI),
    "disabled":    ((INK, 110), ("ash1", 220), None),
}


def button(state):
    """200×20 띠 단추 (위 말씨). 위·아래 줄은 1·18 줄, 띠는 2..17 줄, 양 끝 여섯 열은 BUTTON_ENDS 로 옅어진다."""
    W, H = 200, 20
    (fc, fa), (lc, la), gem = BUTTON_TONES[state]
    cv = Cv(W, H)
    for x in range(W):
        d = min(x, W - 1 - x)
        k = BUTTON_ENDS[d] if d < len(BUTTON_ENDS) else 1.0
        if int(fa * k):
            cv.vline(x, 2, H - 3, (fc, int(fa * k)))
        cv.put(x, 1, (lc, int(la * k)))
        cv.put(x, H - 2, (lc, int(la * k)))
    if gem:
        for gx in (3, W - 4):
            cv.put(gx, 9, gem)
            cv.put(gx, 10, gem)
            cv.put(gx - 1, 9, ORN)
            cv.put(gx + 1, 9, ORN)
            cv.put(gx - 1, 10, ORN)
            cv.put(gx + 1, 10, ORN)
            cv.put(gx, 8, ORN)
            cv.put(gx, 11, ORN)
    return cv.image()


# 제작법 책 단추 20×18: 단추와 같은 반투명 판에 금빛 선으로 그린 작은 책 (책 x 6..13, y 4..13)
RECIPE_BOOK = [
    "......LLLLLLL.",
    "......L.....LL",
    "......L.....LL",
    "......L.HHH.LL",
    "......L.....LL",
    "......L.HHH.LL",
    "......L.....LL",
    "......L.....LL",
    "......LLLLLLLL",
    ".......LLLLLLL",
]


def recipe_button(hi):
    cv = Cv(20, 18)
    fill, edge, _ = SQUARE_TONES["highlighted" if hi else "normal"]
    panel(cv, 20, 18, inset=1, line=edge, fill=fill, fade=(fill[1] // 3,))
    cv.stamp(0, 4, [r.replace(".", " ") for r in RECIPE_BOOK], {"L": ORN if hi else LINE, "H": LINE_DIM})
    return cv.image()


# ─────────────────────────── 설정 창의 위젯 (밀대, 고름 칸, 글 칸, 탭, 두루마리) ───────────────────────────

WIDGET_SCALING = {
    "slider": {"type": "nine_slice", "width": 200, "height": 20, "border": 2},
    "slider_highlighted": {"type": "nine_slice", "width": 200, "height": 20, "border": 2},
    "slider_handle": {"type": "nine_slice", "width": 8, "height": 20, "border": 2},
    "slider_handle_highlighted": {"type": "nine_slice", "width": 8, "height": 20, "border": 2},
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


def slider_track(hi):
    """밀대 길 200×20 (9조각 테 2): 진한 반투명 홈 + 1픽셀 테 (가리키면 금빛)."""
    cv = Cv(200, 20)
    panel(cv, 200, 20, inset=1, line=LINE if hi else ("parch0", 170), fill=(INK, 185), fade=(70,))
    return cv.image()


def slider_handle(hi):
    """
    밀대 손잡이 8×20: 진한 먹 손잡이에 1픽셀 베이지 테 (2026-10-08 비평: 꽉 찬 베이지 막대가 가운데 글 ("시야 범위") 밑에서
    글을 지웠다). 가리키면 테가 밝은 금빛. 위·아래 끝 가운데에 작은 눈금 (테에서 안으로 한 칸).
    """
    cv = Cv(8, 20)
    edge = ORN_HI if hi else ("parch1", 255)
    cv.rect(1, 1, 6, 18, (WELL, 210))
    cv.box(1, 1, 6, 18, edge)
    for y in (2, 17):
        cv.put(3, y, edge)
        cv.put(4, y, edge)
    return cv.image()


# 고름 칸 표시: 2픽셀 굵기의 꺾인 획
CHECK = [
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..............CC....",
    ".............CC.....",
    "............CC......",
    "....CC.....CC.......",
    ".....CC...CC........",
    "......CC.CC.........",
    ".......CCC..........",
    "........C...........",
    "....................",
]


def checkbox(selected, hi):
    cv = Cv(20, 20)
    panel(cv, 20, 20, inset=1, line=ORN if hi else ("parch0", 200), fill=(INK, 185), fade=(70,))
    if selected:
        cv.stamp(0, 0, [r.replace(".", " ") for r in CHECK], {"C": ORN_HI if hi else ORN})
    return cv.image()


def text_field(hi):
    """글 칸 200×20 (9조각 테 1): 가장 진한 반투명 검정에 1픽셀 테 (고르면 금빛). 흰 글이 가장 잘 읽히는 바탕."""
    cv = Cv(200, 20)
    cv.rect(1, 1, 198, 18, (INK, 225))
    cv.box(0, 0, 199, 19, LINE if hi else ("ash2", 255))
    return cv.image()


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
    """두루마리 6×32 (9조각 테 1). 막대: 바랜 양피지빛 (테는 금빛). 길: 반투명 검정."""
    cv = Cv(6, 32)
    if background:
        cv.rect(0, 0, 5, 31, (INK, 150))
    else:
        cv.rect(0, 0, 5, 31, LINE)
        cv.rect(1, 1, 4, 30, ("parch0", 255))
    return cv.image()


# 설정 화면의 머리·발 나눔줄 (textures/gui/*_separator.png 32×2, 가로로 이어 붙인다): 1픽셀 금빛 줄 + 그 밑 옅은 그늘
SEPARATORS = ("header_separator", "footer_separator", "inworld_header_separator", "inworld_footer_separator")


def separator():
    cv = Cv(32, 2)
    cv.hline(0, 31, 0, ("parch0", 200))
    cv.hline(0, 31, 1, (INK, 120))
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

# 서버 창(Dialog)마다 제목 옆에 바닐라가 그리는 20×20 단추 (gui/sprites/dialog/warning_button*). 단추와 같은 반투명 판에
# 금빛 "!" 하나.
WARNING_MARK = [
    "....................",
    "....................",
    "....................",
    "....................",
    ".........PP.........",
    ".........PP.........",
    ".........PP.........",
    ".........PP.........",
    ".........PP.........",
    ".........PP.........",
    "....................",
    "....................",
    ".........PP.........",
    ".........PP.........",
]


def warning_button(state):
    fill, edge, _ = SQUARE_TONES[state]
    cv = Cv(20, 20)
    panel(cv, 20, 20, inset=1, line=edge, fill=fill, fade=(fill[1] // 3,))
    mark = {"normal": LINE, "highlighted": ORN_HI, "disabled": ("ash2", 255)}[state]
    cv.stamp(0, 0, [r.replace(".", " ") for r in WARNING_MARK], {"P": mark})
    return cv.image()


# ─────────────────────────── 설명 칸 ───────────────────────────

TOOLTIP_SCALING = {
    "background": {"type": "nine_slice", "width": 100, "height": 100, "border": 9},
    "frame": {"type": "nine_slice", "width": 100, "height": 100, "border": 10, "stretch_inner": True},
}


def tooltip():
    """
    바닐라는 글 둘레 (x-12, y-12, 폭+24, 높이+24) 에 바탕과 테를 그린다. 글은 12픽셀 안쪽.
    바탕: 3..96 의 92% 검정 (가장자리 두 단 계단). 가운데 (9..90) 는 이어 붙여지므로 한 색.
    테: 가장자리에서 5 에 1픽셀 금빛 줄 (글과 6픽셀 띈다), 네 귀에 밝은 금빛 꺾쇠 (세 칸). 가장자리 가운데 (10..89) 는
    늘여지므로 고른 줄.
    """
    N = 100
    bg = Cv(N, N)
    # 92% (2026-10-08 비평: 89% 에서는 뒤의 아이템 그림과 개수가 글 밑에 비쳤다). 테는 가장자리에서 5 (글과 6 띈다)
    panel(bg, N - 6, N - 6, x0=3, y0=3, inset=99, line=None, fill=(INK, 235), fade=(110, 190))
    fr = Cv(N, N)
    fr.box(5, 5, N - 6, N - 6, ("parch1", 255))
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx = 5 if sx > 0 else N - 6
        cy = 5 if sy > 0 else N - 6
        for i in range(3):
            fr.put(cx + sx * i, cy, ORN)
            fr.put(cx, cy + sy * i, ORN)
    return bg.image(), fr.image()


# ─────────────────────────── 빌드 ───────────────────────────

def build(out):
    """out (팩 뿌리) 에 그림과 .mcmeta 를 쓴다. 쓴 그림 경로 목록을 돌려준다."""
    written = []
    hud = ("sprites", "hud")
    for n in heart_names():
        written.append(save(clear(9, 9), out, *hud, "heart", n + ".png"))
    for n, (w, h) in HIDDEN_HUD.items():
        written.append(save(clear(w, h), out, *hud, n + ".png"))
    written.append(save(crosshair(), out, *hud, "crosshair.png"))
    for kind in BOSS_COLORS:
        bg, fill = boss_bar(kind)
        written.append(save(bg, out, "sprites", "boss_bar", kind + "_background.png"))
        written.append(save(fill, out, "sprites", "boss_bar", kind + "_progress.png"))
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
    # 게임 중 메뉴 (일시정지·설정) 뒤의 반투명 검정 (바닐라는 검정 알파 64). 흐린 세상이 더 깊이 가라앉는다
    menu = Image.new("RGBA", (16, 16), c(INK, 120))
    written.append(save(menu, out, "inworld_menu_background.png"))
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
    """GUI 픽셀 크기 w×h 의 화면 아래쪽 (단축 슬롯, 왼손 칸). 하트·허기·경험치 막대는 투명이라 그리지 않는다."""
    small = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hud = ("sprites", "hud")
    hx, hy = w // 2 - 91, h - 22
    small.alpha_composite(_sprite(out, *hud, "hotbar.png"), (hx, hy))
    small.alpha_composite(_sprite(out, *hud, "hotbar_selection.png"), (hx - 1 + sel * 20, hy - 1))
    small.alpha_composite(_sprite(out, *hud, "hotbar_offhand_left.png"), (hx - 29, h - 23))
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


def cell_pixels(ours, wells, van=None):
    """
    칸마다 자리를 픽셀로 견준다. [(x, y, 맞음)] 과 어긋난 칸 목록을 돌려준다. 바닐라 칸 상자 (x, y, 폭, 높이) 에서
    네모 = (x+1 .. x+폭-2, y+1 .. y+높이-2) (18×18 칸이면 꼭 아이템 자리 16×16) 일 때 우리 그림의 테색 E = (x+1, y+1),
    바닥색 F = (x+2, y+2):
      네모 가장자리 한 줄 = E (불투명), 네모 속 = F 한 색 (F ≠ E)
      바닐라 상자의 가장자리 (그늘·입술 줄, 아이템 자리 바로 바깥) 는 E 도 F 도 아니다: 보이는 네모가 아이템 자리보다
      한 픽셀도 크지 않다
    van (바닐라 그림) 을 주면 바깥 줄은 바닐라가 그늘·입술로 칠한 픽셀만 본다 (인물 자리의 오른쪽 아래 귀는 바닐라에서도
    왼손 칸이 덮는다).
    """
    px = ours.load()
    vx = van.load() if van is not None else None
    checks, bad = [], []
    for x, y, w, h in wells:
        E, F = px[x + 1, y + 1], px[x + 2, y + 2]
        x0, y0, x1, y1 = x + 1, y + 1, x + w - 2, y + h - 2
        edge = [(i, y0) for i in range(x0, x1 + 1)] + [(i, y1) for i in range(x0, x1 + 1)]
        edge += [(x0, j) for j in range(y0 + 1, y1)] + [(x1, j) for j in range(y0 + 1, y1)]
        floor = [(i, j) for j in range(y0 + 1, y1) for i in range(x0 + 1, x1)]
        ring = [(i, y) for i in range(x, x + w)] + [(i, y + h - 1) for i in range(x, x + w)]
        ring += [(x, j) for j in range(y + 1, y + h - 1)] + [(x + w - 1, j) for j in range(y + 1, y + h - 1)]
        if vx is not None:
            ring = [q for q in ring if vx[q][:3] in (VANILLA_SHADOW, VANILLA_LIP)]
        mine = [(q, px[q] == E and E[3] > 0) for q in edge]
        mine += [(q, px[q] == F and F != E) for q in floor]
        mine += [(q, px[q] not in (E, F)) for q in ring]
        checks += [(q[0], q[1], ok) for q, ok in mine]
        if not all(ok for _, ok in mine):
            bad.append((x, y, w, h))
    return checks, bad


def check_cells(ours, wells, van=None):
    """어긋난 칸의 목록 (비면 모두 맞다). 무엇을 보는지는 cell_pixels."""
    return cell_pixels(ours, wells, van)[1]


def _outline(draw, x, y, w, h, k, col):
    draw.rectangle([x * k, y * k, (x + w) * k - 1, (y + h) * k - 1], outline=col)


def align_proof(out, preview_dir, jar):
    """
    align_<창>.png 다섯 칸: 바닐라, 우리 그림, 우리 그림 위에 바닐라 칸의 경계를 겹친 것 (청록 = 바닐라 아이템 자리 16×16
    의 바깥 경계, 자홍 = 바닐라 칸 18×18 의 바깥 경계), 두 그림을 반씩 섞은 것, 픽셀 견주기 (cell_pixels 가 본 픽셀마다
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
            checks, bad = cell_pixels(ours, wells, van)
            report[name] = (len(wells), bad, len(checks), sum(1 for c_ in checks if not c_[2]))
            crop = (0, 0, w, h)
            back = Image.new("RGBA", (w, h), (40, 40, 44, 255))
            ours_c = back.copy()
            ours_c.alpha_composite(ours.crop(crop))
            a, b = _big(van.crop(crop), k), _big(ours_c, k)
            over = b.copy()
            d = ImageDraw.Draw(over)
            for x, y, ww, hh in wells:
                _outline(d, x, y, ww, hh, k, (255, 0, 255, 255))
                _outline(d, x + 1, y + 1, ww - 2, hh - 2, k, (0, 255, 255, 255))
            for x, y, ww, hh in bad:
                d.rectangle([x * k, y * k, (x + ww) * k - 1, (y + hh) * k - 1], fill=(255, 0, 0, 160))
            mix = Image.blend(a, b, 0.5)
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
        # 단축 슬롯: 칸 상자 (2+20k, 2) 18×18 의 가장자리가 테, 속 16×16 (3+20k, 3) 이 바닥 (= 아이템 자리)
        hb = _sprite(out, "sprites", "hud", "hotbar.png")
        hv = _jar_png(z, "assets/minecraft/textures/gui/sprites/hud/hotbar.png")
        hw = [(1 + 20 * i, 1, 20, 20) for i in range(9)]
        report["hotbar"] = (len(hw), check_cells(hb, hw))
        hs = _sprite(out, "sprites", "hud", "hotbar_selection.png")
        hole = [(x, y) for y in range(23) for x in range(24) if hs.getpixel((x, y))[3] == 0 and 4 <= x <= 19 and 4 <= y <= 19]
        report["selection_hole"] = (min(hole), max(hole), len(hole))
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
    panel_img = _sprite(out, "container", name + ".png").crop((0, 0, pw, ph))
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
        small.alpha_composite(_sprite(out, "sprites", "recipe_book", "button.png"), (pad + 104, pad + 61))
        icon_slots = {0: "helmet", 1: "chestplate", 2: "leggings", 3: "boots", 4: "shield"}
        for i, n in icon_slots.items():
            small.alpha_composite(_sprite(out, "sprites", "container", "slot", n + ".png"), (pad + slots[i][0], pad + slots[i][1]))
    if name == "crafting_table":
        small.alpha_composite(_sprite(out, "sprites", "recipe_book", "button_highlighted.png"), (pad + 5, pad + 34))
    hover = {"inventory": 20, "crafting_table": 20, "generic_54": 22}[name]
    hx, hy = slots[hover]
    small.alpha_composite(_sprite(out, "sprites", "container", "slot_highlight_back.png"), (pad + hx - 4, pad + hy - 4))
    counts = []
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
        small.alpha_composite(nine_slice(_sprite(out, "sprites", "widget", spr + ".png"), bw, bh, BUTTON_BORDER), (bx, by))
    for i, st in enumerate(("warning_button", "warning_button_highlighted", "warning_button_disabled")):
        small.alpha_composite(_sprite(out, "sprites", "dialog", st + ".png"), (10 + 24 * i, 120))
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
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "resourcepack")
    paths = build(target)
    write_previews(target, sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "preview"))
    import artlint
    artlint.lint(paths, target)
