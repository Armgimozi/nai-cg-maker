"""바닐라 GUI 덮어쓰기 — 미궁 테마(어두운 돌 + 금장)로 전부 새로 그린다 (assets/minecraft/textures/gui/...).

원본 그림은 한 픽셀도 읽거나 복사하지 않는다. 26.3 클라이언트에서 가져온 것은 **치수와 좌표**뿐이다
(그림 크기·nine_slice 테두리 폭·슬롯 위치는 클라이언트 바이트코드 / 메뉴 클래스의 상수로 확인):

- 상자(generic_54): 256×256 중 위 176×(17+18·줄) 은 v=0 부터, 아래 176×96 은 v=126 부터 잘라 이어 붙인다.
  슬롯 아이템 (8+18c, 18+18r) · 플레이어 인벤토리 아래 조각 기준 +14 · 핫바 +72 · "인벤토리" 글자 (8, 높이−94).
- 166 높이 화면(작업대·화로·발사기·셜커): 인벤토리 (8, 84) · 핫바 (8, 142) · "인벤토리" 글자 (8, 72).
- 플레이어 인벤토리: 갑옷 (8, 8+18i) · 보조손 (77, 62) · 조합 2×2 (98, 18) · 결과 (154, 28) · 인물 창 (26..75, 8..78) · 제목 (97, 6).
- 작업대: 조합 3×3 (30, 17) · 결과 (124, 35) · 제목 (29, 6). 화로: 재료 (56, 17) · 연료 (56, 53) · 결과 (116, 35) ·
  불꽃 lit_progress 14×14 @ (56, 36) · 화살표 burn_progress 24×16 @ (79, 34) · 제목 가운데.
- 핫바 182×22 (아이템 3+20i, 3) · 선택 24×23 · 보조손 29×24 · 십자선 15×15 · 보스바 182×5 ·
  툴팁 100×100 (background border 9 / frame border 10 stretch_inner, 글자 = 바깥에서 12px 안쪽) ·
  버튼 200×20 (border 3) · 스크롤 6×32 (border 1) · 효과 칸 24×24 / 32×32(border 4).

바닐라 화면의 제목·"인벤토리" 글자는 진회색(#404040)이므로 글자 자리에 밝은 양피지 명판을 깐다.
등급별 툴팁: 아이템 tooltip_style = labyrinth:<등급> → labyrinth:tooltip/<등급>_background / _frame.
"""
from __future__ import annotations

import io
import json

from PIL import Image, ImageDraw

from .ui import GOLD, INK, PARCHMENT, STONE, Canvas, _stone, socket
from .util import clamp8, darken, h2, hex2rgb, lighten, mix

MC = 'assets/minecraft/textures/gui/'
LAB = 'assets/labyrinth/textures/gui/'

# 등급 색 (plugin content/Rarity.java 와 같은 순서·색 계열) — 툴팁 테두리용 밝기 단계 [어두움 … 밝음]
RARITY = {
    'common': ['#3a3a44', '#6c6c78', '#a8a8b4', '#d8d8e0', '#f4f4f8'],
    'uncommon': ['#16381c', '#2e7a36', '#4fbf58', '#8fe896', '#d0ffd4'],
    'rare': ['#10264e', '#2456a8', '#4f8fff', '#93bfff', '#d8e8ff'],
    'epic': ['#2a1046', '#5a2a96', '#9a52e6', '#c896ff', '#eedcff'],
    'legendary': ['#4a2a06', '#9a5c10', '#f0a028', '#ffd27a', '#fff2c8'],
    'mythic': ['#460a10', '#9a1a24', '#ff3b3b', '#ff8a7a', '#ffe0d0'],
}
RARITY_ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic']

BOSS_COLORS = {
    'pink': ('#ff7ac8', '#c23a8c'), 'blue': ('#6ab4ff', '#2a5ec8'), 'red': ('#ff5a5a', '#b01a2a'),
    'green': ('#7ee06a', '#2e8a3a'), 'yellow': ('#ffe060', '#c08a10'), 'purple': ('#c88aff', '#6a2ab8'),
    'white': ('#ffffff', '#a8a8bc'),
}


def _rgb(h):
    return hex2rgb(h) if isinstance(h, str) else tuple(h[:3])


def png(img) -> bytes:
    b = io.BytesIO()
    img.save(b, 'PNG', optimize=True)
    return b.getvalue()


def nine_slice_meta(w, h, border, stretch_inner=False) -> bytes:
    sc = {'type': 'nine_slice', 'width': w, 'height': h, 'border': border}
    if stretch_inner:
        sc['stretch_inner'] = True
    return (json.dumps({'gui': {'scaling': sc}}, indent=2) + '\n').encode('utf-8')


# ───────────────────────────── 공통 부품 ─────────────────────────────
def frame(cv: Canvas, x0, y0, x1, y1, top=True, bottom=True, ramp=None):
    """금장 액자 테두리 (2px 금 + 바깥·안쪽 먹선). top/bottom=False 면 그 변을 열어 둔다(조각 이어 붙이기용)."""
    g = ramp or GOLD
    ya = y0 if top else y0 - 4
    yb = y1 if bottom else y1 + 4
    # 옆변 (열린 변 쪽으로는 끝까지 이어 그림)
    for y in range(max(y0, ya), min(y1, yb) + 1):
        cv.set(x0, y, INK)
        cv.set(x1, y, INK)
        if ya + 1 <= y <= yb - 1:
            cv.set(x0 + 1, y, g[4])
            cv.set(x1 - 1, y, g[1])
        if ya + 2 <= y <= yb - 2:
            cv.set(x0 + 2, y, g[3])
            cv.set(x1 - 2, y, g[2])
        if ya + 3 <= y <= yb - 3:
            cv.set(x0 + 3, y, INK)
            cv.set(x1 - 3, y, INK)
    if top:
        cv.hline(x0, x1, y0, INK)
        cv.hline(x0 + 1, x1 - 1, y0 + 1, g[4])
        cv.hline(x0 + 2, x1 - 2, y0 + 2, g[3])
        cv.hline(x0 + 3, x1 - 3, y0 + 3, INK)
        cv.set(x1 - 1, y0 + 1, g[3])
        for (x, y) in ((x0, y0), (x1, y0)):
            cv.set(x, y, (0, 0, 0), 0)
    if bottom:
        cv.hline(x0, x1, y1, INK)
        cv.hline(x0 + 1, x1 - 1, y1 - 1, g[1])
        cv.hline(x0 + 2, x1 - 2, y1 - 2, g[2])
        cv.hline(x0 + 3, x1 - 3, y1 - 3, INK)
        cv.set(x0 + 1, y1 - 1, g[3])
        for (x, y) in ((x0, y1), (x1, y1)):
            cv.set(x, y, (0, 0, 0), 0)


def corner_flourish(cv: Canvas, x, y, fx, fy, accent):
    """모서리 금 꽃장식 (frame 안쪽 모서리에 붙임). fx/fy = ±1 방향."""
    pat = ['####..', '#++#..', '#+#...', '##..#.', '....#.', '...##.']
    for j, row in enumerate(pat):
        for i, ch in enumerate(row):
            if ch == '.':
                continue
            cv.set(x + i * fx, y + j * fy, GOLD[4] if ch == '#' else accent)


def plaque(cv: Canvas, x0, y0, x1, y1, seed=0):
    """밝은 양피지 명판 — 바닐라 진회색(#404040) 제목 글자가 잘 읽히는 자리."""
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, y1 - y0)
        for x in range(x0, x1 + 1):
            c = mix(PARCHMENT[3], PARCHMENT[2], t * 0.8)
            n = (h2(x, y, seed + 31) - 0.5) * 8
            if h2(x // 3, y, seed + 37) > 0.93:
                n -= 10
            cv.set(x, y, tuple(clamp8(v + n) for v in c))
    cv.hline(x0, x1, y0, PARCHMENT[0])
    cv.hline(x0, x1, y1, PARCHMENT[0])
    cv.vline(x0, y0, y1, PARCHMENT[0])
    cv.vline(x1, y0, y1, PARCHMENT[0])
    cv.hline(x0 + 1, x1 - 1, y0 + 1, lighten(PARCHMENT[3], 0.25))
    cv.hline(x0 + 1, x1 - 1, y1 - 1, PARCHMENT[1])
    # 양 끝 금 장식 못
    for x in (x0, x1):
        my = (y0 + y1) // 2
        cv.set(x, my - 1, GOLD[3])
        cv.set(x, my, GOLD[4])
        cv.set(x, my + 1, GOLD[2])
    for (x, y) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        cv.set(x, y, STONE[1])


def recess(cv: Canvas, x0, y0, x1, y1, fill=None, seed=0, top=True, bottom=True):
    """움푹 팬 판 (어두운 위·왼쪽, 밝은 아래·오른쪽). top/bottom=False 면 그 변의 선을 생략."""
    base = fill or STONE[1]
    for y in range(y0 + (1 if top else 0), y1 + (0 if bottom else 1)):
        for x in range(x0 + 1, x1):
            n = (h2(x, y, seed) - 0.5) * 5
            cv.set(x, y, tuple(clamp8(v + n) for v in base))
    if top:
        cv.hline(x0, x1, y0, STONE[0])
    if bottom:
        cv.hline(x0, x1, y1, STONE[4])
    cv.vline(x0, y0, y1, STONE[0])
    cv.vline(x1, y0, y1, STONE[4])


def rule(cv: Canvas, x0, x1, y):
    """금 줄 + 못 장식 (명판 옆 빈자리)."""
    cv.hline(x0, x1, y, GOLD[2])
    cv.hline(x0, x1, y + 1, GOLD[0])
    cv.set(x0, y, GOLD[4])
    for x in range(x0 + 6, x1 - 2, 12):
        cv.set(x, y - 1, GOLD[4])
        cv.set(x + 1, y - 1, GOLD[3])
        cv.set(x, y, GOLD[3])
        cv.set(x + 1, y, GOLD[1])


def result_socket(cv: Canvas, x, y, accent=(255, 210, 122)):
    """결과 칸: 아이템 (x+1, y+1) 의 18×18 소켓 + 바깥 2px 금 액자 + 모서리 보석."""
    x0, y0, x1, y1 = x - 3, y - 3, x + 20, y + 20
    cv.box(x0, y0, x1, y1, INK)
    cv.hline(x0 + 1, x1 - 1, y0 + 1, GOLD[4])
    cv.vline(x0 + 1, y0 + 1, y1 - 1, GOLD[4])
    cv.hline(x0 + 1, x1 - 1, y1 - 1, GOLD[1])
    cv.vline(x1 - 1, y0 + 1, y1 - 1, GOLD[1])
    cv.box(x0 + 2, y0 + 2, x1 - 2, y1 - 2, GOLD[2])
    socket(cv, x, y, 'gem', accent)
    for (cx, cy) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        cv.set(cx, cy, (0, 0, 0), 0)
        cv.set(cx + (1 if cx == x0 else -1), cy + (1 if cy == y0 else -1), accent)


ARROW = ['..........#.........', '..........##........', '..........###.......', '#############.......',
         '##############......', '#############.......', '..........###.......', '..........##........',
         '..........#.........']


def arrow(cv: Canvas, x, y, fill=None, outline=None):
    """오른쪽 화살표 (22×9 정도) — 조합 → 결과 사이 장식."""
    fill = fill or STONE[0]
    outline = outline or GOLD[2]
    rows = ARROW
    body = {(i, j) for j, r in enumerate(rows) for i, ch in enumerate(r) if ch == '#'}
    for (i, j) in body:
        for (dx, dy) in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (i + dx, j + dy) not in body:
                cv.set(x + i + dx, y + j + dy, outline)
    for (i, j) in body:
        cv.set(x + i, y + j, fill)


def player_inventory(cv: Canvas, inv_item_y, label_y, seed, accent=None):
    """플레이어 인벤토리 3×9 + 핫바 9칸 + "인벤토리" 명판. inv_item_y = 첫 줄 아이템 y, label_y = 글자 y."""
    acc = accent or GOLD[3]
    plaque(cv, 5, label_y - 2, 74, label_y + 9, seed + 1)
    rule(cv, 77, 168, label_y + 3)
    sy = inv_item_y - 1
    recess(cv, 5, sy - 1, 170, sy + 54, fill=STONE[1], seed=seed + 2)
    for r in range(3):
        for c in range(9):
            vsocket(cv, 7 + 18 * c, sy + 18 * r)
    hy = inv_item_y + 58 - 1
    recess(cv, 5, hy - 1, 170, hy + 18, fill=mix(STONE[1], acc, 0.06), seed=seed + 3)
    for c in range(9):
        vsocket(cv, 7 + 18 * c, hy)
    cv.hline(7, 168, hy + 18, mix(GOLD[2], acc, 0.3))


def vsocket(cv: Canvas, x, y, accent=None):
    """바닐라 화면용 18×18 소켓: 깊게 팬 칸 + 모서리 금 못(격자로 붙이면 교차점마다 금 못이 모인다)."""
    for j in range(16):
        for i in range(16):
            d = max(abs(i - 7.5), abs(j - 7.5)) / 7.5
            c = mix((13, 11, 18), (30, 26, 40), d ** 2 * 0.9)
            if j < 2 or i < 2:
                c = darken(c, 0.25)
            cv.set(x + 1 + i, y + 1 + j, c)
    cv.hline(x, x + 17, y, STONE[0])
    cv.vline(x, y, y + 17, STONE[0])
    cv.hline(x + 1, x + 17, y + 17, STONE[5])
    cv.vline(x + 17, y + 1, y + 17, STONE[5])
    g = accent or GOLD[2]
    for (cx, cy) in ((x, y), (x + 17, y), (x, y + 17), (x + 17, y + 17)):
        cv.set(cx, cy, g)


def base_panel(w, h, seed, top=True, bottom=True, flourish=True, accent=(230, 170, 80)):
    cv = Canvas(w, h)
    _stone(cv, 0, 0, w - 1, h - 1, seed, base=3)
    frame(cv, 0, 0, w - 1, h - 1, top, bottom)
    if flourish:
        if top:
            corner_flourish(cv, 4, 4, 1, 1, accent)
            corner_flourish(cv, w - 5, 4, -1, 1, accent)
        if bottom:
            corner_flourish(cv, 4, h - 5, 1, -1, accent)
            corner_flourish(cv, w - 5, h - 5, -1, -1, accent)
    return cv


def _on256(*parts):
    """[(이미지, x, y)] 를 256×256 투명 판에 붙인다 (바닐라 컨테이너 텍스처 규격)."""
    img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    for (p, x, y) in parts:
        img.alpha_composite(p, (x, y))
    return img


# ───────────────────────────── 컨테이너 화면 ─────────────────────────────
def chest_parts(seed=541):
    """generic_54 의 위 조각(176×125: 제목 + 6줄)과 아래 조각(176×96: 인벤토리)."""
    top = base_panel(176, 125, seed, bottom=False)
    plaque(top, 5, 3, 170, 15, seed + 4)
    recess(top, 5, 16, 170, 124, fill=STONE[1], seed=seed + 5, bottom=False)
    top.hline(6, 169, 17, mix(STONE[1], GOLD[2], 0.18))
    for r in range(6):
        for c in range(9):
            vsocket(top, 7 + 18 * c, 17 + 18 * r)
    bot = base_panel(176, 96, seed + 50, top=False)
    # 위 조각 상자 판의 아래 변(밝은 선)이 이 조각 첫 줄에 온다
    bot.hline(5, 170, 0, STONE[4])
    bot.set(5, 0, STONE[0])
    player_inventory(bot, 14, 3, seed + 60)
    return top.img, bot.img


def paint_generic_54():
    top, bot = chest_parts()
    return _on256((top, 0, 0), (bot, 0, 126))


def screen166(seed, title='left', title_x=8, accent=(230, 170, 80)):
    """166 높이 화면 바탕 (위 70px 은 화면별 내용, 아래는 플레이어 인벤토리)."""
    cv = base_panel(176, 166, seed, accent=accent)
    if title == 'center':
        plaque(cv, 5, 3, 170, 15, seed + 4)
    elif title == 'left':
        plaque(cv, title_x - 3, 3, min(170, title_x + 92), 15, seed + 4)
    player_inventory(cv, 84, 72, seed + 60)
    return cv


def paint_shulker():
    cv = screen166(601)
    recess(cv, 5, 16, 170, 71, fill=STONE[1], seed=606)
    for r in range(3):
        for c in range(9):
            vsocket(cv, 7 + 18 * c, 17 + 18 * r)
    return _on256((cv.img, 0, 0))


def paint_dispenser():
    cv = screen166(611, title='center')
    recess(cv, 57, 13, 118, 72 - 2, fill=STONE[1], seed=612)
    for r in range(3):
        for c in range(3):
            vsocket(cv, 61 + 18 * c, 16 + 18 * r)
    for (x, y) in ((57, 13), (118, 13), (57, 70), (118, 70)):
        cv.set(x, y, GOLD[3])
    return _on256((cv.img, 0, 0))


def paint_crafting_table():
    cv = screen166(621, title='left', title_x=29)
    recess(cv, 26, 16 - 1 + 0, 85, 70, fill=STONE[1], seed=622)
    for r in range(3):
        for c in range(3):
            vsocket(cv, 29 + 18 * c, 16 + 18 * r)
    arrow(cv, 89, 38)
    result_socket(cv, 123, 34)
    return _on256((cv.img, 0, 0))


def flame_shape():
    """14×14 불꽃 실루엣 (화로 연료 표시) — '#' 몸통, '+' 안쪽 심지."""
    return ['......#.......', '......##......', '.....###......', '.....####.....', '....#####.#...',
            '...######.##..', '...#######.#..', '..####+####...', '..###+++####..', '.###++++####..',
            '.###+++++###..', '.####+++####..', '..##########..', '...########...']


def paint_flame(lit):
    cv = Canvas(14, 14)
    pat = flame_shape()
    for j, row in enumerate(pat):
        for i, ch in enumerate(row):
            if ch == '.':
                continue
            if lit:
                t = j / 13
                c = mix((255, 236, 140), (240, 90, 30), t) if ch == '#' else (255, 252, 220)
                if ch == '#' and (i + j) % 5 == 0:
                    c = lighten(c, 0.2)
            else:
                c = STONE[0] if ch == '#' else STONE[1]
            cv.set(i, j, c)
    return cv.img


BURN = ['..............#.........', '..............##........', '..............###.......', '..............####......',
        '#################.....', '##################....', '###################...', '####################..',
        '###################...', '##################....', '#################.....', '..............####......',
        '..............###.......', '..............##........', '..............#.........', '........................']


def paint_burn(lit):
    """24×16 화살표 (제련 진행) — lit=True 는 진행분 그림(왼쪽부터 잘려 그려짐)."""
    cv = Canvas(24, 16)
    for j, row in enumerate(BURN):
        for i, ch in enumerate(row):
            if ch != '#':
                continue
            if lit:
                t = i / 22
                c = mix((255, 214, 120), (255, 120, 40), t)
                if j in (6, 7):
                    c = lighten(c, 0.3)
            else:
                c = STONE[0]
            cv.set(i, j, c)
    if not lit:   # 빈 화살표 테두리
        body = {(i, j) for j, r in enumerate(BURN) for i, ch in enumerate(r) if ch == '#'}
        for (i, j) in body:
            for (dx, dy) in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if (i + dx, j + dy) not in body and 0 <= i + dx < 24 and 0 <= j + dy < 16:
                    cv.set(i + dx, j + dy, GOLD[1])
    return cv.img


def paint_furnace():
    cv = screen166(631, title='center')
    recess(cv, 44, 15, 140, 72 - 2, fill=mix(STONE[1], (60, 24, 12), 0.25), seed=632)
    # 노 안쪽 붉은 기운
    for y in range(16, 70):
        for x in range(45, 140):
            d = ((x - 63) ** 2 + (y - 43) ** 2) ** 0.5 / 34
            if d < 1:
                cv.blend(x, y, (200, 80, 30), 0.22 * (1 - d) ** 1.5)
    vsocket(cv, 55, 16)
    vsocket(cv, 55, 52)
    cv.img.alpha_composite(paint_flame(False), (56, 36))
    cv.img.alpha_composite(paint_burn(False), (79, 34))
    result_socket(cv, 115, 34)
    return _on256((cv.img, 0, 0))


def paint_inventory():
    cv = base_panel(176, 166, 641)
    # 갑옷 4칸 + 인물 창 + 보조손
    recess(cv, 5, 5, 23, 80, fill=STONE[1], seed=642)
    for i in range(4):
        vsocket(cv, 7, 7 + 18 * i)
    # 인물 창 (엔티티는 26..75 × 8..78 에 그려짐)
    wx0, wy0, wx1, wy1 = 25, 7, 75, 78
    for y in range(wy0 + 1, wy1):
        for x in range(wx0 + 1, wx1):
            dx, dy = (x - 50) / 26, (y - 62) / 44
            d = (dx * dx + dy * dy) ** 0.5
            c = mix((14, 10, 22), (58, 36, 92), max(0.0, 1 - d) ** 1.4)
            if (x + y) % 23 == 0 and y > 60:
                c = lighten(c, 0.08)
            cv.set(x, y, c)
    # 바닥 원판 (인물 발 아래)
    for x in range(wx0 + 6, wx1 - 5):
        t = abs(x - 50) / 20
        if t < 1:
            cv.set(x, 73, mix(GOLD[1], STONE[2], t))
            cv.set(x, 74, mix(GOLD[2], STONE[1], t))
    cv.box(wx0, wy0, wx1, wy1, GOLD[2])
    cv.hline(wx0, wx1, wy0, GOLD[3])
    cv.vline(wx0, wy0, wy1, GOLD[3])
    for (x, y) in ((wx0, wy0), (wx1, wy0), (wx0, wy1), (wx1, wy1)):
        cv.set(x, y, GOLD[4])
    # 아치 꼭대기 장식
    for k in range(-3, 4):
        cv.set(50 + k, wy0 + 1, GOLD[1])
    cv.set(50, wy0 + 2, (180, 120, 255))
    vsocket(cv, 76, 61)
    # 조합 2×2 + 결과
    plaque(cv, 94, 3, 170, 14, 643)
    recess(cv, 94, 15, 134, 52, fill=STONE[1], seed=644)
    for r in range(2):
        for c in range(2):
            vsocket(cv, 97 + 18 * c, 17 + 18 * r)
    arrow(cv, 135, 31, fill=STONE[0])
    result_socket(cv, 153, 27)
    player_inventory_166(cv, 645)
    return _on256((cv.img, 0, 0))


def player_inventory_166(cv, seed):
    """플레이어 인벤토리 화면 아래쪽 (제목 글자가 없으므로 명판 대신 금 줄)."""
    rule(cv, 7, 168, 80)
    sy = 83
    recess(cv, 5, sy - 1, 170, sy + 54, fill=STONE[1], seed=seed + 2)
    for r in range(3):
        for c in range(9):
            vsocket(cv, 7 + 18 * c, sy + 18 * r)
    hy = 141
    recess(cv, 5, hy - 1, 170, hy + 18, fill=mix(STONE[1], GOLD[3], 0.06), seed=seed + 3)
    for c in range(9):
        vsocket(cv, 7 + 18 * c, hy)
    cv.hline(7, 168, hy + 18, GOLD[2])


# ───────────────────────────── HUD (핫바·십자선·효과 칸) ─────────────────────────────
def paint_hotbar():
    cv = Canvas(182, 22)
    _stone(cv, 0, 0, 181, 21, 711, base=1)
    cv.box(0, 0, 181, 21, INK)
    cv.hline(1, 180, 1, GOLD[3])
    cv.hline(1, 180, 20, GOLD[1])
    cv.vline(1, 1, 20, GOLD[3])
    cv.vline(180, 1, 20, GOLD[1])
    for (x, y) in ((0, 0), (181, 0), (0, 21), (181, 21)):
        cv.set(x, y, (0, 0, 0), 0)
    for i in range(9):
        x = 2 + 20 * i
        vsocket(cv, x, 2)
        if i < 8:   # 칸 사이 금 기둥
            cv.vline(x + 18, 3, 18, STONE[0])
            cv.vline(x + 19, 3, 18, STONE[3])
            cv.set(x + 18, 10, GOLD[2])
            cv.set(x + 19, 10, GOLD[3])
            cv.set(x + 18, 11, GOLD[1])
            cv.set(x + 19, 11, GOLD[2])
    return cv.img


def paint_hotbar_selection():
    cv = Canvas(24, 23)
    # 바깥 금테 2px + 모서리 보석, 안쪽은 비움(아이템·핫바 칸이 보이게)
    for y in range(23):
        for x in range(24):
            edge = min(x, y, 23 - x, 22 - y)
            if edge == 0:
                c = INK
            elif edge == 1:
                c = GOLD[5] if (x + y) % 2 == 0 else GOLD[4]
            elif edge == 2:
                c = GOLD[3]
            else:
                continue
            cv.set(x, y, c)
    for (x, y) in ((0, 0), (23, 0), (0, 22), (23, 22)):
        cv.set(x, y, (0, 0, 0), 0)
    for (x, y) in ((1, 1), (22, 1), (1, 21), (22, 21)):
        cv.set(x, y, (120, 220, 255))
    # 안쪽 빛 (반투명)
    for x in range(3, 21):
        cv.set(x, 3, GOLD[5], 110)
        cv.set(x, 19, GOLD[4], 70)
    cv.set(11, 0, GOLD[5])
    cv.set(12, 0, GOLD[5])
    return cv.img


def paint_offhand(side):
    cv = Canvas(29, 24)
    x0 = 0 if side == 'left' else 7
    x1 = x0 + 21
    _stone(cv, x0, 1, x1, 23, 721, base=1)
    cv.box(x0, 1, x1, 23, INK)
    cv.hline(x0 + 1, x1 - 1, 2, GOLD[3])
    cv.vline(x0 + 1, 2, 22, GOLD[3])
    cv.hline(x0 + 1, x1 - 1, 22, GOLD[1])
    cv.vline(x1 - 1, 2, 22, GOLD[1])
    for (x, y) in ((x0, 1), (x1, 1), (x0, 23), (x1, 23)):
        cv.set(x, y, (0, 0, 0), 0)
    vsocket(cv, x0 + 2, 3)
    return cv.img


CROSS = ['.......#.......', '.......#.......', '.......#.......', '...............', '...............',
         '.....#...#.....', '...............', '###....#....###', '...............', '.....#...#.....',
         '...............', '...............', '.......#.......', '.......#.......', '.......#.......']


def paint_crosshair():
    """룬 십자선 — 바닐라처럼 반전 합성으로 그려지므로 흰색만 쓴다."""
    cv = Canvas(15, 15)
    for j, row in enumerate(CROSS):
        for i, ch in enumerate(row):
            if ch == '#':
                cv.set(i, j, (255, 255, 255))
    return cv.img


def paint_effect_bg(size, ambient, border=None):
    cv = Canvas(size, size)
    ramp = [(30, 36, 52), (60, 80, 110), (110, 150, 190), (160, 200, 230), (220, 240, 255)] if ambient else GOLD
    for y in range(size):
        for x in range(size):
            t = y / (size - 1)
            cv.set(x, y, mix(STONE[3], STONE[1], t), 235)
    cv.box(0, 0, size - 1, size - 1, INK)
    cv.hline(1, size - 2, 1, ramp[4])
    cv.vline(1, 1, size - 2, ramp[4])
    cv.hline(1, size - 2, size - 2, ramp[1])
    cv.vline(size - 2, 1, size - 2, ramp[1])
    cv.box(2, 2, size - 3, size - 3, ramp[2])
    for (x, y) in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
        cv.set(x, y, (0, 0, 0), 0)
    return cv.img


# ───────────────────────────── 보스바 ─────────────────────────────
def paint_boss_background():
    cv = Canvas(182, 5)
    for x in range(182):
        cv.set(x, 0, GOLD[2] if 0 < x < 181 else INK)
        cv.set(x, 4, GOLD[0] if 0 < x < 181 else INK)
        for y in (1, 2, 3):
            cv.set(x, y, mix((26, 20, 34), (14, 10, 20), (y - 1) / 2))
    for y in range(5):
        cv.set(0, y, INK)
        cv.set(181, y, INK)
    cv.set(1, 2, GOLD[3])
    cv.set(180, 2, GOLD[3])
    return cv.img


def paint_boss_progress(color):
    hi, lo = (_rgb(c) for c in BOSS_COLORS[color])
    cv = Canvas(182, 5)
    for x in range(1, 181):
        for y in (1, 2, 3):
            c = {1: lighten(hi, 0.35), 2: hi, 3: lo}[y]
            if (x // 3) % 7 == 0 and y == 1:
                c = lighten(c, 0.25)
            cv.set(x, y, c)
    return cv.img


def paint_boss_notches(n, progress):
    cv = Canvas(182, 5)
    for k in range(1, n):
        x = round(182 * k / n)
        for y in (1, 2, 3):
            cv.set(x, y, GOLD[4] if progress else STONE[0], 230 if progress else 255)
        if progress:
            cv.set(x - 1, 2, GOLD[2], 160)
    return cv.img


# ───────────────────────────── 툴팁 ─────────────────────────────
def paint_tooltip_background(tint=None):
    """100×100, nine_slice border 9. 글자 영역 = 12..87, 판 = 8..91 (바깥 8px 은 여백)."""
    cv = Canvas(100, 100)
    base = (18, 14, 26)
    if tint:
        base = mix(base, _rgb(tint), 0.10)
    for y in range(8, 92):
        for x in range(8, 92):
            n = (h2(x, y, 905) - 0.5) * 4
            cv.set(x, y, tuple(clamp8(v + n) for v in base), 238)
    for (x, y) in ((8, 8), (91, 8), (8, 91), (91, 91)):
        cv.set(x, y, (0, 0, 0), 0)
    return cv.img


def paint_tooltip_frame(ramp=None, gem=None, ornate=False):
    """100×100, nine_slice border 10 + stretch_inner. 금(또는 등급 색) 테두리 2줄 + 모서리 꽃장식(여백까지)."""
    g = [_rgb(c) for c in ramp] if ramp else [GOLD[1], GOLD[2], GOLD[3], GOLD[4], GOLD[5]]
    cv = Canvas(100, 100)
    # 바깥 테 (판 가장자리 8..91): 위·왼쪽 밝게, 아래·오른쪽 어둡게
    for i in range(9, 91):
        cv.set(i, 8, g[3])
        cv.set(8, i, g[3])
        cv.set(i, 91, g[1])
        cv.set(91, i, g[1])
        cv.set(i, 9, g[1], 150)
        cv.set(9, i, g[1], 150)
        cv.set(i, 90, g[0], 150)
        cv.set(90, i, g[0], 150)
    # 모서리 꽃장식 — 여백(0..8)으로 살짝 뻗음
    gemc = _rgb(gem) if gem else g[4]
    for (cx, cy, fx, fy) in ((8, 8, 1, 1), (91, 8, -1, 1), (8, 91, 1, -1), (91, 91, -1, -1)):
        pts_hi = [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (-1, -1), (-2, -1), (-1, -2), (-3, -1), (-1, -3)]
        for (dx, dy) in pts_hi:
            cv.set(cx + dx * fx, cy + dy * fy, g[4])
        cv.set(cx + 1 * fx, cy + 1 * fy, gemc)
        cv.set(cx - 2 * fx, cy - 2 * fy, gemc if ornate else g[3])
        if ornate:
            for (dx, dy) in ((-4, -1), (-1, -4), (-3, -3)):
                cv.set(cx + dx * fx, cy + dy * fy, g[2])
    # 위·아래 변 가운데 쪽 점선 무늬 (타일링돼도 자연스럽게 4px 주기)
    for x in range(12, 88, 4):
        cv.set(x, 7, g[2], 200)
        cv.set(x, 92, g[1], 160)
    return cv.img


# ───────────────────────────── 위젯 ─────────────────────────────
def paint_button(state):
    """200×20 (nine_slice border 3) — 어두운 돌 + 금 테두리. state = normal | highlighted | disabled."""
    cv = Canvas(200, 20)
    if state == 'disabled':
        top, bot, fill0, fill1 = STONE[4], STONE[2], STONE[2], STONE[1]
    elif state == 'highlighted':
        top, bot, fill0, fill1 = GOLD[5], GOLD[2], (84, 64, 110), (52, 38, 70)
    else:
        top, bot, fill0, fill1 = GOLD[4], GOLD[1], STONE[4], STONE[2]
    for y in range(20):
        for x in range(200):
            if x in (0, 199) or y in (0, 19):
                c = INK
            elif y == 1 or x == 1:
                c = top
            elif y == 18 or x == 198:
                c = bot
            elif y == 2 or x == 2:
                c = mix(top, fill0, 0.55)
            else:
                t = (y - 3) / 14
                c = mix(fill0, fill1, t)
                n = (h2(x % 97, y, 931) - 0.5) * 5
                c = tuple(clamp8(v + n) for v in c)
            cv.set(x, y, c)
    for (x, y) in ((0, 0), (199, 0), (0, 19), (199, 19)):
        cv.set(x, y, (0, 0, 0), 0)
    if state == 'highlighted':
        for (x, y) in ((1, 1), (198, 1), (1, 18), (198, 18)):
            cv.set(x, y, (255, 250, 220))
    return cv.img


def paint_scroller(bg):
    cv = Canvas(6, 32)
    for y in range(32):
        for x in range(6):
            if bg:
                c = STONE[0] if x in (0, 5) else mix(STONE[1], STONE[0], 0.3)
            else:
                c = INK if x in (0, 5) or y in (0, 31) else (GOLD[4] if x == 1 or y == 1 else GOLD[1] if x == 4 or y == 30
                                                             else GOLD[3])
            cv.set(x, y, c)
    return cv.img


# ───────────────────────────── 조립 ─────────────────────────────
def build():
    """반환: ({팩 경로: bytes}, 미리보기용 {이름: Image})."""
    files, imgs = {}, {}

    def put(path, img, meta=None):
        files[path] = png(img)
        imgs[path] = img
        if meta is not None:
            files[path + '.mcmeta'] = meta

    put(MC + 'container/generic_54.png', paint_generic_54())
    put(MC + 'container/shulker_box.png', paint_shulker())
    put(MC + 'container/dispenser.png', paint_dispenser())
    put(MC + 'container/crafting_table.png', paint_crafting_table())
    fur = paint_furnace()
    for n in ('furnace', 'blast_furnace', 'smoker'):
        put(MC + f'container/{n}.png', fur)
        put(MC + f'sprites/container/{n}/lit_progress.png', paint_flame(True))
        put(MC + f'sprites/container/{n}/burn_progress.png', paint_burn(True))
    put(MC + 'container/inventory.png', paint_inventory())
    put(MC + 'sprites/hud/hotbar.png', paint_hotbar())
    put(MC + 'sprites/hud/hotbar_selection.png', paint_hotbar_selection())
    put(MC + 'sprites/hud/hotbar_offhand_left.png', paint_offhand('left'))
    put(MC + 'sprites/hud/hotbar_offhand_right.png', paint_offhand('right'))
    put(MC + 'sprites/hud/crosshair.png', paint_crosshair())
    put(MC + 'sprites/hud/effect_background.png', paint_effect_bg(24, False))
    put(MC + 'sprites/hud/effect_background_ambient.png', paint_effect_bg(24, True))
    put(MC + 'sprites/container/inventory/effect_background.png', paint_effect_bg(32, False), nine_slice_meta(32, 32, 4))
    put(MC + 'sprites/container/inventory/effect_background_ambient.png', paint_effect_bg(32, True),
        nine_slice_meta(32, 32, 4))
    bg = paint_boss_background()
    for c in BOSS_COLORS:
        put(MC + f'sprites/boss_bar/{c}_background.png', bg)
        put(MC + f'sprites/boss_bar/{c}_progress.png', paint_boss_progress(c))
    for n in (6, 10, 12, 20):
        put(MC + f'sprites/boss_bar/notched_{n}_background.png', paint_boss_notches(n, False))
        put(MC + f'sprites/boss_bar/notched_{n}_progress.png', paint_boss_notches(n, True))
    put(MC + 'sprites/tooltip/background.png', paint_tooltip_background(), nine_slice_meta(100, 100, 9))
    put(MC + 'sprites/tooltip/frame.png', paint_tooltip_frame(), nine_slice_meta(100, 100, 10, True))
    for k, r in enumerate(RARITY_ORDER):
        ramp = RARITY[r]
        put(LAB + f'sprites/tooltip/{r}_background.png', paint_tooltip_background(ramp[2]), nine_slice_meta(100, 100, 9))
        put(LAB + f'sprites/tooltip/{r}_frame.png',
            paint_tooltip_frame(ramp, gem=ramp[4] if k >= 3 else None, ornate=k >= 3),
            nine_slice_meta(100, 100, 10, True))
    put(MC + 'sprites/widget/button.png', paint_button('normal'), nine_slice_meta(200, 20, 3))
    put(MC + 'sprites/widget/button_highlighted.png', paint_button('highlighted'), nine_slice_meta(200, 20, 3))
    put(MC + 'sprites/widget/button_disabled.png', paint_button('disabled'), nine_slice_meta(200, 20, 3))
    put(MC + 'sprites/widget/scroller.png', paint_scroller(False), nine_slice_meta(6, 32, 1))
    put(MC + 'sprites/widget/scroller_background.png', paint_scroller(True), nine_slice_meta(6, 32, 1))
    return files, imgs


# ───────────────────────────── 미리보기 ─────────────────────────────
def nine_slice(img, border, w, h, stretch_inner=False):
    """클라이언트 nine_slice 흉내 (모서리 고정, 변·가운데 타일링 / stretch_inner 면 가운데 늘림)."""
    W, H = img.size
    b = border
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))

    def tile(src, dx, dy, dw, dh, stretch=False):
        if dw <= 0 or dh <= 0 or src.size[0] <= 0 or src.size[1] <= 0:
            return
        if stretch:
            out.alpha_composite(src.resize((dw, dh), Image.NEAREST), (dx, dy))
            return
        for yy in range(0, dh, src.size[1]):
            for xx in range(0, dw, src.size[0]):
                part = src.crop((0, 0, min(src.size[0], dw - xx), min(src.size[1], dh - yy)))
                out.alpha_composite(part, (dx + xx, dy + yy))

    c = lambda x0, y0, x1, y1: img.crop((x0, y0, x1, y1))
    tile(c(0, 0, b, b), 0, 0, b, b)
    tile(c(W - b, 0, W, b), w - b, 0, b, b)
    tile(c(0, H - b, b, H), 0, h - b, b, b)
    tile(c(W - b, H - b, W, H), w - b, h - b, b, b)
    tile(c(b, 0, W - b, b), b, 0, w - 2 * b, b)
    tile(c(b, H - b, W - b, H), b, h - b, w - 2 * b, b)
    tile(c(0, b, b, H - b), 0, b, b, h - 2 * b)
    tile(c(W - b, b, W, H - b), w - b, b, b, h - 2 * b)
    tile(c(b, b, W - b, H - b), b, b, w - 2 * b, h - 2 * b, stretch_inner)
    return out


def _txt(d, xy, s, fill=(64, 64, 64, 255)):
    d.text(xy, s, fill=fill)


def preview_screens(imgs, hud_img=None):
    """원본 크기(1배)로 화면을 나란히 그린 뒤 2배 확대. 글자(PIL 기본 글꼴)는 바닐라 글자 자리 표시용."""
    S = 2
    W, H = 6 + 4 * 182, 6 + 228 + 172 + 150 + (hud_img.size[1] + 10 if hud_img is not None else 0)
    sheet = Image.new('RGBA', (W, H), (54, 72, 52, 255))
    for y in range(H):
        for x in range(0, W, 2):
            if h2(x // 6, y // 6, 3) > 0.72:
                sheet.putpixel((x, y), (48, 64, 46, 255))
    d = ImageDraw.Draw(sheet)

    def g(path):
        return imgs[MC + path] if (MC + path) in imgs else imgs[LAB + path]

    col = [6 + 182 * k for k in range(4)]
    chest = g('container/generic_54.png')
    # ── 1줄: 큰 상자(6줄) · 상자(3줄) · 플레이어 인벤토리 · 작업대
    y0 = 6
    sheet.alpha_composite(chest.crop((0, 0, 176, 125)), (col[0], y0))
    sheet.alpha_composite(chest.crop((0, 126, 176, 222)), (col[0], y0 + 125))
    _txt(d, (col[0] + 8, y0 + 5), 'Large Chest')
    _txt(d, (col[0] + 8, y0 + 222 - 94), 'Inventory')
    sheet.alpha_composite(chest.crop((0, 0, 176, 71)), (col[1], y0))
    sheet.alpha_composite(chest.crop((0, 126, 176, 222)), (col[1], y0 + 71))
    _txt(d, (col[1] + 8, y0 + 5), 'Chest')
    _txt(d, (col[1] + 8, y0 + 168 - 94), 'Inventory')
    sheet.alpha_composite(g('container/inventory.png').crop((0, 0, 176, 166)), (col[2], y0))
    _txt(d, (col[2] + 97, y0 + 5), 'Crafting')
    sheet.alpha_composite(g('container/crafting_table.png').crop((0, 0, 176, 166)), (col[3], y0))
    _txt(d, (col[3] + 29, y0 + 5), 'Crafting')
    _txt(d, (col[3] + 8, y0 + 71), 'Inventory')
    # ── 2줄: 화로(진행 중) · 발사기 · 셜커 상자 · 툴팁 7종
    y1 = y0 + 228
    fu = g('container/furnace.png').crop((0, 0, 176, 166)).copy()
    fu.alpha_composite(g('sprites/container/furnace/lit_progress.png').crop((0, 5, 14, 14)), (56, 41))
    fu.alpha_composite(g('sprites/container/furnace/burn_progress.png').crop((0, 0, 15, 16)), (79, 34))
    sheet.alpha_composite(fu, (col[0], y1))
    _txt(d, (col[0] + 70, y1 + 5), 'Furnace')
    _txt(d, (col[0] + 8, y1 + 71), 'Inventory')
    sheet.alpha_composite(g('container/dispenser.png').crop((0, 0, 176, 166)), (col[1], y1))
    _txt(d, (col[1] + 64, y1 + 5), 'Dispenser')
    _txt(d, (col[1] + 8, y1 + 71), 'Inventory')
    sheet.alpha_composite(g('container/shulker_box.png').crop((0, 0, 176, 166)), (col[2], y1))
    _txt(d, (col[2] + 8, y1 + 5), 'Shulker Box')
    _txt(d, (col[2] + 8, y1 + 71), 'Inventory')
    tips = [('tooltip/background.png', 'tooltip/frame.png', 'Vanilla item')] + [
        (f'tooltip/{r}_background.png', f'tooltip/{r}_frame.png', r) for r in RARITY_ORDER]
    names = {'common': (232, 232, 232), 'uncommon': (95, 211, 95), 'rare': (79, 155, 255), 'epic': (180, 92, 255),
             'legendary': (255, 181, 46), 'mythic': (255, 59, 59)}
    for k, (bgp, frp, label) in enumerate(tips):
        w, h = 64, 20
        bgi = nine_slice(g('sprites/' + bgp), 9, w + 24, h + 24)
        fri = nine_slice(g('sprites/' + frp), 10, w + 24, h + 24, True)
        px, py = col[3] - 6 + (k % 2) * 92, y1 - 4 + (k // 2) * 42
        sheet.alpha_composite(bgi, (px, py))
        sheet.alpha_composite(fri, (px, py))
        d.text((px + 12, py + 11), label, fill=names.get(label, (255, 255, 255)) + (255,))
        d.text((px + 12, py + 22), 'Lv.12 +34 ATK', fill=(170, 170, 170, 255))
    # ── 3줄: 버튼 · 보스바 · 십자선 · 효과 칸 · 스크롤
    y2 = y1 + 172
    for k, st in enumerate(('button', 'button_highlighted', 'button_disabled')):
        b = nine_slice(g(f'sprites/widget/{st}.png'), 3, 150, 20)
        sheet.alpha_composite(b, (col[0] + k * 156, y2))
        d.text((col[0] + k * 156 + 52, y2 + 5), ['Done', 'Hover', 'Disabled'][k], fill=(255, 255, 255, 255))
    for k, (cname, prog, notch) in enumerate((('red', 0.6, 10), ('purple', 0.35, 6), ('yellow', 0.85, None),
                                               ('green', 0.5, 20))):
        bx, by = col[0] + (k % 2) * 200, y2 + 40 + (k // 2) * 22
        sheet.alpha_composite(g(f'sprites/boss_bar/{cname}_background.png'), (bx, by + 10))
        if notch:
            sheet.alpha_composite(g(f'sprites/boss_bar/notched_{notch}_background.png'), (bx, by + 10))
        pw = int(182 * prog)
        sheet.alpha_composite(g(f'sprites/boss_bar/{cname}_progress.png').crop((0, 0, pw, 5)), (bx, by + 10))
        if notch:
            sheet.alpha_composite(g(f'sprites/boss_bar/notched_{notch}_progress.png').crop((0, 0, pw, 5)), (bx, by + 10))
        d.text((bx + 62, by), 'Boss name', fill=(255, 255, 255, 255))
    sheet.alpha_composite(g('sprites/hud/crosshair.png'), (col[2] + 40, y2 + 46))
    sheet.alpha_composite(g('sprites/hud/effect_background.png'), (col[2] + 70, y2 + 42))
    sheet.alpha_composite(g('sprites/hud/effect_background_ambient.png'), (col[2] + 98, y2 + 42))
    sheet.alpha_composite(nine_slice(g('sprites/container/inventory/effect_background.png'), 4, 120, 32),
                          (col[2] + 40, y2 + 76))
    sheet.alpha_composite(nine_slice(g('sprites/widget/scroller_background.png'), 1, 6, 90), (col[3] + 140, y2 + 30))
    sheet.alpha_composite(nine_slice(g('sprites/widget/scroller.png'), 1, 6, 24), (col[3] + 140, y2 + 50))
    # 핫바 단독 (선택 3번 칸, 보조손 왼쪽)
    hx, hy = col[3] - 40, y2 + 120
    sheet.alpha_composite(g('sprites/hud/hotbar_offhand_left.png'), (hx - 29, hy - 1))
    sheet.alpha_composite(g('sprites/hud/hotbar.png'), (hx, hy))
    sheet.alpha_composite(g('sprites/hud/hotbar_selection.png'), (hx - 1 + 20 * 2, hy - 1))
    sheet.alpha_composite(g('sprites/hud/hotbar_offhand_right.png'), (hx + 182, hy - 1))
    if hud_img is not None:
        sheet.alpha_composite(hud_img, (6, y2 + 150))
    return sheet.resize((W * S, H * S), Image.NEAREST)
