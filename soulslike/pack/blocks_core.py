#!/usr/bin/env python3
"""
핵심 블록 다시 그리기 (블록 2층). 시험 방과 맛보기판 지도 (DESIGN 8.4) 가 실제로 쓰는 블록만 손 규칙으로 새로 그린다.
나머지 모든 블록은 blocks_grade.py (1층, 바닐라 그림의 색만 옮긴다) 가 맡고, 여기서 그린 것이 그 위를 덮는다.

  python3 pack/blocks_core.py [팩 폴더]        그림만 쓴다 (gen_pack 이 build(OUT) 로 부른다)
  python3 pack/blocks_core.py --sheets        전후 비교판과 3×3 이음매 판 (dist/screenshots/blocks/)

그리는 법 (ART_DIRECTION, DESIGN 10.7)
  - 색은 palette.py 의 이름으로만. 명암은 계단 3~4단, 빛은 왼쪽 위 하나.
  - 돌·판자·나무껍질·기와는 손으로 적은 16×16 배치도 (글자 하나 = 돌 하나, '.' = 줄눈) 로 모양을 정하고,
    masonry() 가 이웃만 보고 윗면·왼쪽 빛, 아랫면·오른쪽 그늘을 넣는다. 배치도는 가장자리를 넘으면 반대쪽으로 이어진다
    (그래서 블록을 이어 놓아도 이음매가 없다).
  - 이 빠짐·금·이끼·얼룩은 덧그림 (overlay) 으로 손으로 찍는다. 흩뿌린 잡음은 없다. 이끼와 물때는 줄눈에서 아래로 흐른다.
  - 같은 무늬를 복사하지 않는다: 블록마다 배치도가 다르다. 금 간·이끼 낀 변형만 바탕 배치를 같이 쓴다 (벽에서 섞어 쓰므로).
  - 모형이 그림의 자리를 정하는 블록 (랜턴, 초, 사슬, 모닥불 통나무, 쇠창살, 비계) 은 바닐라와 같은 자리에 그린다.
"""
import io
import json
import os
import sys
import zipfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import palette  # noqa: E402

ROOT = os.path.dirname(HERE)
BLOCK = ("assets", "minecraft", "textures", "block")

# ─────────────────────────── 쓰는 곳 ───────────────────────────
# 그림 파일 (textures/block/<이름>.png) → 그 블록이 쓰이는 곳. 시험 방은 plugin/.../world/TestRoom.java, 지역은 DESIGN 8.4.
USED = {
    "deepslate_tiles": "시험 방 바닥 58% · 턱 윗면 · 판석 길 (심층암 타일 반 블록), 탑옥 (P), 교구 지붕 (R2)",
    "cracked_deepslate_tiles": "시험 방 바닥 16% · 턱 윗면",
    "polished_deepslate": "시험 방 바닥 16% · 구르기 길 · 판석 길 (윤낸 심층암 반 블록)",
    "deepslate_bricks": "시험 방 벽 · 랜턴 기둥 (심층암 벽돌 담) · 구르기 길 눈금 · 턱 모서리",
    "cracked_deepslate_bricks": "시험 방 벽 28% · 턱 모서리",
    "cobbled_deepslate": "시험 방 바닥 아래 받침 80% · 바닥 10% · 턱 속",
    "deepslate": "시험 방 바닥 아래 받침 20% (옆면)",
    "deepslate_top": "시험 방 바닥 아래 받침 20% (윗면)",
    "chiseled_deepslate": "구르기 길 시작 칸",
    "ladder": "시험 방 턱 사다리, 걷어찬 사다리 지름길 (r1.s.ladder)",
    "lantern": "시험 방 기둥 위·턱 위 랜턴, 모든 지역의 빛 (8.4)",
    "stone_bricks": "레딘 성벽 (R1)",
    "cracked_stone_bricks": "오다의 사당 (H), 레딘 성벽 (R1)",
    "mossy_stone_bricks": "오다의 사당 (H), 레딘 성벽 (R1)",
    "cobblestone": "레딘 성벽 (R1), 레버 받침",
    "mossy_cobblestone": "볼크 탑옥 (P) 의 이끼 돌",
    "andesite": "레딘 성벽 (R1)",
    "stone": "지형 덩어리 (8.10 절벽·바위), 효과 기본 블록 (util/Fx)",
    "tuff": "오다의 사당 (H)",
    "tuff_bricks": "오스윈 교구 (R2)",
    "calcite": "오스윈 교구 (R2) 의 바랜 방해석",
    "smooth_stone": "오스윈 교구 (R2)",
    "smooth_stone_slab_side": "오스윈 교구 (R2) 반 블록 옆면",
    "mud_bricks": "레딘 성벽 (R1), 마른 피 얼룩",
    "brown_terracotta": "레딘 성벽 (R1), 마른 피 얼룩",
    "spruce_planks": "레딘 성벽 (R1) 가문비",
    "spruce_log": "레딘 성벽 (R1) 가문비",
    "spruce_log_top": "레딘 성벽 (R1) 가문비",
    "dark_oak_planks": "레딘 성벽 (R1) 짙은 참나무",
    "dark_oak_log": "레딘 성벽 (R1) 짙은 참나무",
    "dark_oak_log_top": "레딘 성벽 (R1) 짙은 참나무",
    "iron_bars": "볼크 탑옥 (P), 레딘 성벽 (R1), 병영 쇠창살문 (r1.s.barracks)",
    "iron_chain": "오다의 사당 (H), 볼크 탑옥 (P)",
    "iron_door_top": "탑옥 마당 쇠문 (p.gate)",
    "iron_door_bottom": "탑옥 마당 쇠문 (p.gate)",
    "lever": "지름길·승강기 부르는 레버 (8.6)",
    "candle": "오다의 사당 (H) 의 꺼진 초",
    "candle_lit": "켠 초 (8.4 의 빛)",
    "light_gray_concrete_powder": "오다의 사당 (H) 의 재",
    "dead_bush": "오다의 사당 (H) 의 마른 덤불",
    "hay_block_side": "볼크 탑옥 (P) 의 썩은 건초",
    "hay_block_top": "볼크 탑옥 (P) 의 썩은 건초",
    "cobweb": "레딘 성벽 (R1)",
    "scaffolding_side": "레딘 성벽 (R1) 비계",
    "scaffolding_top": "레딘 성벽 (R1) 비계",
    "scaffolding_bottom": "레딘 성벽 (R1) 비계",
    "oxidized_copper": "오스윈 교구 (R2) 의 녹청 낀 구리 (아주 조금)",
    "gray_stained_glass": "오스윈 교구 (R2) 색유리",
    "brown_stained_glass": "오스윈 교구 (R2) 색유리",
    "black_stained_glass": "오스윈 교구 (R2) 색유리",
    "gray_stained_glass_pane_top": "오스윈 교구 (R2) 색유리 판 테",
    "brown_stained_glass_pane_top": "오스윈 교구 (R2) 색유리 판 테",
    "black_stained_glass_pane_top": "오스윈 교구 (R2) 색유리 판 테",
    "netherrack": "꺼지지 않는 불의 받침 (8.4 의 빛)",
    "campfire_log": "화톳불 자리 (8.11 bonfire: CAMPFIRE=1), 꺼진 모닥불",
    "campfire_log_lit": "화톳불 자리, 켠 모닥불",
}

# ─────────────────────────── 그림판 ───────────────────────────


class Tex:
    """
    팔레트 이름으로 칠하는 그림판. 칸 값은 None (투명), "ash2" (불투명), ("ash2", 알파) 중 하나.
    좌표는 가장자리를 넘으면 반대쪽으로 감긴다 (이어 붙는 블록 그림이라서).
    """

    def __init__(self, w=16, h=16, fill=None):
        self.w, self.h = w, h
        self.px = [[fill] * w for _ in range(h)]

    def __getitem__(self, xy):
        x, y = xy
        return self.px[y % self.h][x % self.w]

    def __setitem__(self, xy, v):
        x, y = xy
        if v is not None:
            n = v[0] if isinstance(v, tuple) else v
            palette.c(n)   # 팔레트 밖이면 여기서 멈춘다
        self.px[y % self.h][x % self.w] = v

    def copy(self):
        t = Tex(self.w, self.h)
        t.px = [r[:] for r in self.px]
        return t

    def paste(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                self.px[oy + y][ox + x] = other.px[y][x]

    def image(self):
        im = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        for y in range(self.h):
            for x in range(self.w):
                v = self.px[y][x]
                if v is None:
                    continue
                if isinstance(v, tuple):
                    im.putpixel((x, y), palette.c(v[0], v[1]))
                else:
                    im.putpixel((x, y), palette.c(v))
        return im


def step(name, k):
    """같은 계열 안에서 k 단 밝게 (음수면 어둡게). 끝에서 멈춘다."""
    if name is None:
        return None
    a = None
    if isinstance(name, tuple):
        name, a = name
    fam = palette.family(name)
    n = len(palette.FAMILIES[fam])
    i = max(0, min(n - 1, int(name[len(fam):]) + k))
    out = f"{fam}{i}"
    return (out, a) if a is not None else out


def grid(rows):
    """ASCII 배치도 → 2차원 글자 표. 줄 수와 폭을 확인한다."""
    h = len(rows)
    w = len(rows[0])
    for r in rows:
        if len(r) != w:
            raise ValueError(f"배치도 줄 폭이 다르다: {r!r}")
    return [list(r) for r in rows], w, h


def masonry(rows, ramps, mortar, *, gap=".", mode="arris", modes=None, arris=None):
    """
    손으로 적은 배치도로 돌·판자를 칠한다.
      rows    16 줄 문자열. gap 글자 = 줄눈, ' ' = 투명, 그 밖의 글자 = 돌 하나 (같은 글자는 같은 돌.
              가장자리를 넘으면 반대쪽으로 이어진다)
      ramps   {돌 글자: [깊은 그늘, 그늘, 바탕, 빛]}, "*" 는 기본
      mortar  [돌 바로 아래 줄눈 (그늘), 그 밖의 줄눈] 또는 줄눈 색 하나
      mode    돌의 명암 (modes={글자: 방식} 으로 돌마다 바꾼다)
                "arris"  윗모서리의 왼쪽 몇 칸만 빛 (arris={글자: 칸 수}, 없으면 글자로 2~5), 아랫줄과 오른쪽 열은
                         그늘, 오른쪽 아래 귀는 깊은 그늘. 손으로 찍은 돌처럼 모서리 빛이 고르지 않다
                "full"   윗줄·왼쪽 열 모두 빛, 아랫줄·오른쪽 열 그늘
                "soft"   윗줄 빛, 아랫줄 그늘만 (기와, 판자)
                "drop"   아랫줄 그늘만 (빛 없는 돌)
                "flat"   바탕만
    빛은 왼쪽 위 하나다.
    """
    g, w, h = grid(rows)
    if isinstance(mortar, str):
        mortar = [mortar, mortar]
    modes = modes or {}
    arris = arris or {}
    t = Tex(w, h)

    def at(x, y):
        return g[y % h][x % w]

    # arris: 돌마다 윗모서리에서 빛이 드는 칸 수 (돌의 왼쪽 위 끝부터 센다)
    run = {}
    for y in range(h):
        for x in range(w):
            s = at(x, y)
            if s in (gap, " ") or at(x, y - 1) == s:
                continue
            # 윗모서리 칸: 왼쪽으로 이어진 윗모서리 칸 수
            n = 0
            xx = x - 1
            while n < w and at(xx, y) == s and at(xx, y - 1) != s:
                n += 1
                xx -= 1
            run[(x % w, y)] = n
    for y in range(h):
        for x in range(w):
            s = at(x, y)
            if s == gap:
                t[x, y] = mortar[0] if at(x, y - 1) not in (gap, " ") else mortar[1]
                continue
            if s == " ":
                t[x, y] = None
                continue
            r = ramps.get(s, ramps.get("*"))
            up, dn = at(x, y - 1) != s, at(x, y + 1) != s
            lf, rt = at(x - 1, y) != s, at(x + 1, y) != s
            m = modes.get(s, mode)
            k = 2
            if m == "flat":
                k = 2
            elif m == "drop":
                k = 1 if dn else 2
            elif m == "soft":
                k = 1 if dn else (3 if up else 2)
            elif m == "full":
                if dn and rt:
                    k = 0
                elif dn:
                    k = 1
                elif up or lf:
                    k = 3
                elif rt:
                    k = 1
            else:  # arris
                n_lit = arris.get(s, 2 + (ord(s) * 7) % 4)
                if dn and rt:
                    k = 0
                elif dn or rt:
                    k = 1
                elif up and run.get((x % w, y), 99) < n_lit:
                    k = 3
            t[x, y] = r[k]
    return t


def overlay(t, rows, ink=None):
    """
    덧그림. 글자마다:
      ' ' 아무것도   '-' 한 단 어둡게   '=' 두 단 어둡게   '+' 한 단 밝게   '#' 두 단 밝게
      그 밖의 글자는 ink[글자] (팔레트 이름, None 이면 투명)
    """
    ink = ink or {}
    g, w, h = grid(rows)
    for y in range(h):
        for x in range(w):
            ch = g[y][x]
            if ch == " ":
                continue
            if ch == "-":
                t[x, y] = step(t[x, y], -1)
            elif ch == "=":
                t[x, y] = step(t[x, y], -2)
            elif ch == "+":
                t[x, y] = step(t[x, y], 1)
            elif ch == "#":
                t[x, y] = step(t[x, y], 2)
            else:
                if ch not in ink:
                    raise KeyError(f"덧그림 글자 {ch!r} 의 색이 없다")
                t[x, y] = ink[ch]
    return t


def paint(rows, ink):
    """글자마다 색을 적은 그림 (작은 물건용). '.' 는 투명."""
    g, w, h = grid(rows)
    t = Tex(w, h)
    for y in range(h):
        for x in range(w):
            ch = g[y][x]
            t[x, y] = None if ch == "." else ink[ch]
    return t


def recolor(t, table):
    """색 바꾸기 (같은 그림에서 다른 판을 만들 때)."""
    out = t.copy()
    for y in range(t.h):
        for x in range(t.w):
            v = t.px[y][x]
            if v is None:
                continue
            n, a = (v if isinstance(v, tuple) else (v, None))
            if n in table:
                n = table[n]
                out.px[y][x] = (n, a) if a is not None else n
    return out


# ─────────────────────────── 램프 ───────────────────────────
# [깊은 그늘, 그늘, 바탕, 빛]. 밝기 (luma): ash0 .11 rust0 .15 ash1 .22 rust1 .26 ash2 .35 parch0 .38 ash3 .50 bone0 .51
# parch1 .51 bone1 .65 parch2 .64 bone2 .79

PALE = ["ash1", "ash2", "ash3", "bone1"]          # 바랜 회색 돌 (레딘 성벽)
WARM = ["ash1", "ash2", "bone0", "bone1"]         # 따뜻한 회색
OCHRE = ["rust1", "parch0", "parch1", "parch2"]   # 황토 돌 (Undead Burg)
SOOT = ["ash0", "ash1", "ash2", "ash3"]           # 그을린 돌
SLATE = ["ash0", "rust0", "ash1", "ash2"]         # 심층암 (탑옥, 시험 방)
SLATE_LT = ["rust0", "ash1", "ash2", "ash3"]      # 밝은 쪽 심층암

# ─────────────────────────── 심층암 (시험 방, 탑옥) ───────────────────────────
# 그을린 묘실 돌. 회색은 재 계열, 따뜻한 그늘은 녹슨 철. 시험 방이 이 돌로 지어져 있어 가장 자주 보인다.
# 명암은 낮게 (바탕 ash1, 빛 ash2 를 모서리 몇 칸에만): 어두운 방에서 줄눈만 또렷하다.

SLATE_W = ["ash0", "rust0", "rust1", "ash2"]      # 따뜻한 쪽 심층암

DSB_ROWS = [  # 심층암 벽돌: 3픽셀 켜 넷, 이음줄은 켜마다 다른 자리
    "AAA.BBBBBBB.AAAA",
    "AAA.BBBBBBB.AAAA",
    "AAAA.BBBBBB.AAAA",
    "................",
    "CCCCCCC.DDDDDDD.",
    "CCCCCCC.DDDDDDD.",
    "CCCCCC.DDDDDDDD.",
    "................",
    "F.EEEEEEEE.FFFFF",
    "F.EEEEEEEE.FFFFF",
    "F.EEEEEEEE.FFFFF",
    "................",
    "HHHHH.GGGGGGG.HH",
    "HHHHH.GGGGGGG.HH",
    "HHHHHH.GGGGGG.HH",
    "................",
]
DSB_RAMP = {"A": SLATE, "B": SLATE_W, "C": SLATE, "D": SLATE, "E": SLATE_W, "F": SLATE, "G": SLATE, "H": SLATE_W}
DSB_ARRIS = {"A": 3, "B": 5, "C": 2, "D": 4, "E": 6, "F": 3, "G": 2, "H": 4}


def deepslate_bricks():
    t = masonry(DSB_ROWS, DSB_RAMP, ["ash0", "ash0"], arris=DSB_ARRIS)
    # 쪼갠 면의 결: 벽돌마다 다른 자리에 짧은 턱 하나 (밝은 칸 + 그 아래 그늘)
    return overlay(t, [
        "                ",
        "      +         ",
        "      -      +  ",
        "                ",
        "  +             ",
        "  -        +    ",
        "                ",
        "                ",
        "             +  ",
        "    +           ",
        "    -           ",
        "                ",
        "         +      ",
        "  +      -      ",
        "                ",
        "                ",
    ])


def cracked_deepslate_bricks():
    t = deepslate_bricks()
    # 금은 위에서 내려와 켜를 건너간다 (줄눈에서 끊기지 않는다). 벽돌 하나는 귀가 떨어져 속이 보인다
    return overlay(t, [
        "         x      ",
        "        x       ",
        "        x       ",
        "        x       ",
        "       x        ",
        "       xx       ",
        "         x      ",
        "         x      ",
        " kkk      x     ",
        " kk        xx   ",
        " k           x  ",
        "                ",
        "                ",
        "    x           ",
        "     xx         ",
        "                ",
    ], {"x": "ash0", "k": "ash0"})


DST_ROWS = [  # 심층암 타일: 바닥과 지붕. 켜 셋 (4·4·5 픽셀), 이음줄은 켜마다 다르다
    "AA.BBBB.CCCC.AAA",
    "AA.BBBB.CCCC.AAA",
    "AA.BBBB.CCCC.AAA",
    "AA.BBBB.CCCC.AAA",
    "................",
    ".DDDD.EEEE.FFFFF",
    ".DDDD.EEEE.FFFFF",
    ".DDDD.EEEE.FFFFF",
    ".DDDD.EEEE.FFFFF",
    "................",
    "III.GGGGG.HHH.II",
    "III.GGGGG.HHH.II",
    "III.GGGGG.HHH.II",
    "III.GGGGG.HHH.II",
    "III.GGGGG.HHH.II",
    "................",
]
DST_RAMP = {"A": SLATE, "B": SLATE_W, "C": SLATE, "D": SLATE, "E": SLATE, "F": SLATE_W, "G": SLATE_W,
            "H": SLATE, "I": SLATE}
DST_ARRIS = {"A": 4, "B": 2, "C": 3, "D": 3, "E": 4, "F": 2, "G": 3, "H": 2, "I": 4}


def deepslate_tiles():
    t = masonry(DST_ROWS, DST_RAMP, ["ash0", "ash0"], arris=DST_ARRIS)
    # 닳은 자리 두엇 (한 단 밝게), 패인 자리 하나
    return overlay(t, [
        "                ",
        "     +          ",
        "          -     ",
        "                ",
        "                ",
        "                ",
        "  -        +    ",
        "                ",
        "                ",
        "                ",
        "                ",
        "       +      - ",
        "  +             ",
        "                ",
        "                ",
        "                ",
    ])


def cracked_deepslate_tiles():
    t = deepslate_tiles()
    # 타일 하나는 귀가 깨져 아래 받침이 보이고 (깊은 그늘), 하나는 금이 가로질렀다
    return overlay(t, [
        "                ",
        "    x           ",
        "     x          ",
        "     xx         ",
        "                ",
        "            kkk ",
        "             kk ",
        "              k ",
        "                ",
        "                ",
        "      x         ",
        "      x         ",
        "       x        ",
        "       x        ",
        "        x       ",
        "                ",
    ], {"x": "ash0", "k": "ash0"})


def polished_deepslate():
    # 한 장짜리 윤낸 판석. 테두리 1픽셀 베벨, 왼쪽 위에 짧은 윤 둘 (빛을 받은 결), 긁힌 자국 하나
    rows = ["PPPPPPPPPPPPPPP."] * 15 + ["................"]
    t = masonry(rows, {"P": ["ash0", "rust0", "ash1", "ash2"]}, ["ash0", "ash0"], mode="full")
    return overlay(t, [
        "                ",
        "                ",
        "    +           ",
        "   +            ",
        "  +     +       ",
        "       +        ",
        "                ",
        "                ",
        "                ",
        "                ",
        "          -     ",
        "         -      ",
        "        -       ",
        "                ",
        "                ",
        "                ",
    ])


def chiseled_deepslate():
    # 구르기 길의 시작 칸: 판석에 새긴 고리와 그 안의 칼 한 자루 (화톳불의 말린 칼).
    # 홈은 왼쪽 위 벽이 그늘 (x), 오른쪽 아래 벽이 빛 (h). 고리 오른쪽 위는 닳아 끊겼다
    rows = ["PPPPPPPPPPPPPPP."] * 15 + ["................"]
    t = masonry(rows, {"P": ["ash0", "rust0", "ash1", "ash2"]}, ["ash0", "ash0"], mode="full")
    return overlay(t, [
        "                ",
        "                ",
        "     xxxx       ",
        "    x   h  x    ",
        "   x   xh   x   ",
        "   x  xxxh  xh  ",
        "   x   xh   xh  ",
        "   x   xh   xh  ",
        "   x   xh   xh  ",
        "   x   xh   xh  ",
        "   x   xh   xh  ",
        "    x   h  xh   ",
        "     xxxxxxh    ",
        "      hhhhh     ",
        "                ",
        "                ",
    ], {"x": "ash0", "h": "ash2"})


CDS_ROWS = [  # 조각난 심층암: 판처럼 쪼개진 모난 조각 아홉
    "AAAA.BBBBBB.CCC.",
    "AAAA.BBBBBBB.CC.",
    "AAA.BBBBBBBB.CCA",
    "AAA.BBBBBBB..CAA",
    "AA..BBBBBB..DD.A",
    ".EEE.BBBB..DDDD.",
    "EEEEE....DDDDDD.",
    "EEEEEE.F.DDDDD.E",
    "EEEEE.FFF..DDD.E",
    ".EEE.FFFFF....GG",
    "H...FFFFFFF.GGGG",
    "HHH.FFFFFF.GGGGG",
    "HHHH..FFF.GGGGG.",
    "HHHHH.....GGGG.H",
    "HHHH.IIIIII...HH",
    ".HH.IIIIIIII...H",
]
CDS_RAMP = {"A": SLATE, "B": SLATE_W, "C": SLATE, "D": SLATE, "E": SLATE_W, "F": SLATE, "G": SLATE_W,
            "H": SLATE, "I": SLATE}
CDS_ARRIS = {"A": 3, "B": 4, "C": 2, "D": 3, "E": 4, "F": 3, "G": 4, "H": 3, "I": 5}


def cobbled_deepslate():
    t = masonry(CDS_ROWS, CDS_RAMP, ["ash0", "ash0"], arris=CDS_ARRIS)
    # 쪼개진 면의 턱 몇 개
    return overlay(t, [
        "                ",
        "       +        ",
        "       -        ",
        "                ",
        "                ",
        "            +   ",
        "  +             ",
        "                ",
        "                ",
        "       +        ",
        "                ",
        "             +  ",
        " +              ",
        "                ",
        "                ",
        "       +        ",
    ])


def deepslate():
    # 심층암 옆면: 세로로 눌린 결. 바탕 ash1 에 따뜻한 결 (b), 빛 받은 결 (c), 갈라진 틈 (d, x)
    return paint([
        "aaacaaabaaadaaab",
        "aaacaaabaaadaaab",
        "aacaaaabaaaadaab",
        "aacaaabaacaadaaa",
        "aacaaabaacaaadaa",
        "aaaaaabaacaaadaa",
        "caaabaaaacaaaaaa",
        "caaabaaxxaaaacaa",
        "caaabaadaaaaacaa",
        "aaaabaadaabaacaa",
        "aadabaadaabaaaca",
        "aadaaaadaabaaaca",
        "aadaacaaaabaaaca",
        "aadaacaaaaaabaaa",
        "aaaaacaaaaaabaad",
        "aaaaacaabaaabaad",
    ], {"a": "ash1", "b": "rust1", "c": "ash2", "d": "rust0", "x": "ash0"})


def deepslate_top():
    # 잘린 면: 결이 비스듬한 켜로 쌓였다 (옆면과 다른 모양)
    return paint([
        "aaaaaaaabbbaaaaa",
        "aaaabbbbaaaaaaaa",
        "bbbbaaaaaaaacccc",
        "aaaaaaaccccaaaaa",
        "aaacccaaaaaaaaaa",
        "ccaaaaaaaaadddda",
        "aaaaaaadddaaaaaa",
        "aaaddddaaaaaaaab",
        "ddaaaaaaaaabbbba",
        "aaaaaaabbbbaaaaa",
        "aaabbbbaaaaaaaaa",
        "bbaaaaaaaaaxxaaa",
        "aaaaaaaaccccaaaa",
        "aaaacccaaaaaaaaa",
        "cccaaaaaaaaaaaab",
        "aaaaaaaaaaaabbba",
    ], {"a": "ash1", "b": "rust1", "c": "ash2", "d": "rust0", "x": "ash0"})


# ─────────────────────────── 돌벽돌 (레딘 성벽, 오다의 사당) ───────────────────────────
# 바랜 회색 마름돌. 켜 높이가 다르고 (5·4·4), 이음줄이 켜마다 다른 자리에 있다. 돌마다 바탕은 같은 밝기에
# 차고 따뜻한 회색만 다르다 (한 돌만 튀면 이어 놓았을 때 격자가 보인다). 황토 물때와 그을음은 덧그림으로 아래로 흐른다.

SB_ROWS = [
    "AAAA.BBBBBBBB.AA",
    "AAAA.BBBBBBBB.AA",
    "AAAAA.BBBBBBB.AA",
    "AAAAA.BBBBBBB.AA",
    "AAAAA.BBBBBBB.AA",
    "................",
    "D.CCCCCCCC.DDDDD",
    "D.CCCCCCCC.DDDDD",
    "D.CCCCCCCCC.DDDD",
    "D.CCCCCCCCC.DDDD",
    "................",
    "EEEEEE.FFFFFFFF.",
    "EEEEEE.FFFFFFFF.",
    "EEEEEE.FFFFFFFF.",
    "EEEEEE.FFFFFFFF.",
    "................",
]
SB_RAMP = {"A": WARM, "B": PALE, "C": WARM, "D": PALE, "E": PALE, "F": WARM}
SB_ARRIS = {"A": 4, "B": 3, "C": 6, "D": 2, "E": 3, "F": 5}


def stone_bricks():
    t = masonry(SB_ROWS, SB_RAMP, ["ash1", "rust0"], arris=SB_ARRIS)
    # 이 빠진 귀 (c), 황토 물때 (o: 윗줄눈에서 아래로 흐르다 끊긴다), 그을음 (-)
    return overlay(t, [
        "               c",
        "         o      ",
        "         o      ",
        "  -       o     ",
        "c -            c",
        "                ",
        " c     o        ",
        "       o    -   ",
        "            -   ",
        "         c      ",
        "                ",
        "  o       -     ",
        "  o       -     ",
        "   o            ",
        "c             c ",
        "                ",
    ], {"c": "rust0", "o": "parch1"})


def cracked_stone_bricks():
    t = stone_bricks()
    # 위 켜에서 시작해 아래 켜로 건너가는 긴 금 하나, 가운데 켜의 돌 하나는 오른쪽 아래 귀가 크게 떨어져 나갔다
    # (깊은 그늘 k, 깨진 면의 빛 h). 아래 켜에 짧은 금
    return overlay(t, [
        "         x      ",
        "        x       ",
        "        x       ",
        "       x        ",
        "       x        ",
        "      x         ",
        "      x         ",
        "     x     kk   ",
        "     x    kkkh  ",
        "    x    kkkkh  ",
        "                ",
        "             x  ",
        "            xx  ",
        "           x    ",
        "                ",
        "                ",
    ], {"x": "ash1", "k": "ash0", "h": "bone1"})


def mossy_stone_bricks():
    t = stone_bricks()
    # 마른 이끼: 줄눈에 붙어 아래로 늘어진다. 이끼 아래 돌은 젖어 한 단 어둡다 (-)
    return overlay(t, [
        "        m       ",
        "        M       ",
        "        -       ",
        "                ",
        "             MM ",
        "   MmmMMM  mMMMm",
        "   MMM MM   M MM",
        "   M    -   -  M",
        "   -           -",
        "                ",
        "mmM       MMm   ",
        "MMMM      mMMM  ",
        "M MM       M M  ",
        "-  M       -    ",
        "   -            ",
        "  M       MmM   ",
    ], {"m": "moss2", "M": "moss1"})



# ═══════════════════════════ 묶기 ═══════════════════════════
# 비교판의 재료 묶음 (그림 이름 순서대로)
GROUPS = [
    ("deepslate", "심층암 (시험 방, 탑옥)", ["deepslate_tiles", "cracked_deepslate_tiles", "polished_deepslate",
                                         "deepslate_bricks", "cracked_deepslate_bricks", "cobbled_deepslate",
                                         "deepslate", "deepslate_top", "chiseled_deepslate"]),
    ("stone", "돌 (성벽, 사당, 교구)", ["stone_bricks", "cracked_stone_bricks", "mossy_stone_bricks", "cobblestone",
                                    "mossy_cobblestone", "andesite", "stone", "tuff", "tuff_bricks", "calcite",
                                    "smooth_stone", "smooth_stone_slab_side"]),
    ("earth", "흙과 진흙 (마른 피 얼룩), 재, 불 받침", ["mud_bricks", "brown_terracotta", "light_gray_concrete_powder",
                                               "netherrack"]),
    ("wood", "나무 (가문비, 짙은 참나무, 사다리, 비계, 건초)", ["spruce_planks", "spruce_log", "spruce_log_top",
                                                    "dark_oak_planks", "dark_oak_log", "dark_oak_log_top", "ladder",
                                                    "scaffolding_side", "scaffolding_top", "scaffolding_bottom",
                                                    "hay_block_side", "hay_block_top"]),
    ("metal", "쇠와 구리", ["iron_bars", "iron_chain", "iron_door_top", "iron_door_bottom", "lever", "oxidized_copper"]),
    ("light", "빛 (랜턴, 초, 모닥불)", ["lantern", "candle", "candle_lit", "campfire_log", "campfire_log_lit"]),
    ("misc", "색유리, 거미줄, 마른 덤불", ["gray_stained_glass", "brown_stained_glass", "black_stained_glass",
                                    "gray_stained_glass_pane_top", "brown_stained_glass_pane_top",
                                    "black_stained_glass_pane_top", "cobweb", "dead_bush"]),
]
# 이어 붙여 쓰는 온 블록 (3×3 이음매 판에 넣는다). 모형이 그림 일부만 쓰는 것은 뺀다
TILED = {"lantern", "candle", "candle_lit", "campfire_log", "campfire_log_lit", "iron_chain", "lever", "dead_bush",
         "iron_door_top", "iron_door_bottom", "gray_stained_glass_pane_top", "brown_stained_glass_pane_top",
         "black_stained_glass_pane_top"}
# 움직이는 그림의 .mcmeta (바닐라와 같은 프레임 수와 빠르기)
ANIM = {"lantern": {"animation": {"frametime": 8}},
        "campfire_log_lit": {"animation": {"interpolate": True, "frametime": 20}}}


def textures():
    """그림 이름 → Tex (움직이는 그림은 프레임을 세로로 이은 Tex). USED 에 있고 함수가 있는 것만."""
    out = {}
    for name in USED:
        fn = globals().get(name)
        if callable(fn):
            out[name] = fn()
    return out


def build(out_root):
    """팩 폴더에 핵심 블록 그림을 쓴다 (blocks_grade 가 쓴 같은 이름의 그림을 덮는다). 쓴 파일 수를 돌려준다."""
    folder = os.path.join(out_root, *BLOCK)
    os.makedirs(folder, exist_ok=True)
    n = 0
    for name, tex in textures().items():
        tex.image().save(os.path.join(folder, name + ".png"), optimize=True)
        n += 1
        if name in ANIM:
            with open(os.path.join(folder, name + ".png.mcmeta"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(ANIM[name], f, ensure_ascii=True, indent=2)
                f.write("\n")
    return n


# ─────────────────────────── 비교판 ───────────────────────────

def client_jar():
    for p in (os.environ.get("SOULS_CLIENT_JAR"), os.path.expanduser("~/.cache/souls-client/versions/1.21.11.jar")):
        if p and os.path.exists(p):
            return p
    return None


def _vanilla(jar, name):
    if not jar:
        return None
    try:
        with zipfile.ZipFile(jar) as z:
            return Image.open(io.BytesIO(z.read("/".join(BLOCK) + f"/{name}.png"))).convert("RGBA")
    except KeyError:
        return None


def _checker(w, h, s):
    bg = Image.new("RGBA", (w, h), (52, 50, 48, 255))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, s):
        for x in range(0, w, s):
            if (x // s + y // s) % 2:
                d.rectangle([x, y, x + s - 1, y + s - 1], fill=(64, 62, 59, 255))
    return bg


def _frame0(im):
    return im.crop((0, 0, im.width, im.width)) if im.height > im.width else im


def write_sheets(out_dir, scale=4, only=None):
    """재료 묶음마다 전후 비교판 (바닐라 | 새 그림, scale 배) 과 3×3 이음매 판. 쓴 파일 목록을 돌려준다."""
    os.makedirs(out_dir, exist_ok=True)
    jar = client_jar()
    texs = textures()
    written = []
    cell = 16 * scale
    for key, title, names in GROUPS:
        if only and key not in only:
            continue
        names = [n for n in names if n in texs]
        if not names:
            continue
        # 전후 비교: 한 줄에 셋 (이름, 바닐라, 새 그림)
        cols = 3
        cw, chh = cell * 2 + 12, cell + 18
        rows = (len(names) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * (cw + 16) + 16, rows * chh + 30), (28, 27, 26, 255))
        d = ImageDraw.Draw(sheet)
        d.text((16, 8), f"{key}: before (vanilla) | after", fill=(209, 195, 160, 255))
        for i, n in enumerate(names):
            x = 16 + (i % cols) * (cw + 16)
            y = 30 + (i // cols) * chh
            van = _vanilla(jar, n)
            new = _frame0(texs[n].image())
            for j, im in enumerate((van, new)):
                bg = _checker(cell, cell, scale * 2)
                if im is not None:
                    bg.alpha_composite(_frame0(im).resize((cell, cell), Image.NEAREST))
                sheet.paste(bg, (x + j * (cell + 12), y))
            d.text((x, y + cell + 2), n, fill=(179, 163, 127, 255))
        p = os.path.join(out_dir, f"core_{key}_before_after.png")
        sheet.save(p)
        written.append(p)
        # 3×3 이음매
        tiled = [n for n in names if n not in TILED]
        if not tiled:
            continue
        tcols = 3
        tw = cell * 3
        rows = (len(tiled) + tcols - 1) // tcols
        sheet = Image.new("RGBA", (tcols * (tw + 16) + 16, rows * (tw + 18) + 30), (28, 27, 26, 255))
        d = ImageDraw.Draw(sheet)
        d.text((16, 8), f"{key}: 3x3 tiling", fill=(209, 195, 160, 255))
        for i, n in enumerate(tiled):
            x = 16 + (i % tcols) * (tw + 16)
            y = 30 + (i // tcols) * (tw + 18)
            im = _frame0(texs[n].image()).resize((cell, cell), Image.NEAREST)
            bg = _checker(tw, tw, scale * 2)
            for ty in range(3):
                for tx in range(3):
                    bg.alpha_composite(im, (tx * cell, ty * cell))
            sheet.paste(bg, (x, y))
            d.text((x, y + tw + 2), n, fill=(179, 163, 127, 255))
        p = os.path.join(out_dir, f"core_{key}_tiled_3x3.png")
        sheet.save(p)
        written.append(p)
    return written


def main(argv):
    if "--sheets" in argv:
        scale = 4
        for a in argv:
            if a.startswith("--scale="):
                scale = int(a.split("=", 1)[1])
        out = os.path.join(ROOT, "dist", "screenshots", "blocks")
        for a in argv:
            if a.startswith("--out="):
                out = a.split("=", 1)[1]
        only = [a.split("=", 1)[1] for a in argv if a.startswith("--only=")]
        for p in write_sheets(out, scale, only or None):
            print(p)
        return 0
    out = argv[0] if argv else os.path.join(HERE, "resourcepack")
    n = build(out)
    print(f"핵심 블록 그림 {n}개 → {os.path.join(out, *BLOCK)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
