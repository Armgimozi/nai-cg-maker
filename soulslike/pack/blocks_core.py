#!/usr/bin/env python3
"""
핵심 블록 다시 그리기 (블록 2층). 시험 방과 맛보기판 지도 (DESIGN 8.4) 가 실제로 쓰는 블록만 손 규칙으로 새로 그린다.
나머지 모든 블록은 blocks_grade.py (1층, 바닐라 그림의 색만 옮긴다) 가 맡고, 여기서 그린 것이 그 위를 덮는다.

  python3 pack/blocks_core.py [팩 폴더]        그림만 쓴다 (gen_pack 이 build(OUT) 로 부른다)
  python3 pack/blocks_core.py --sheets        전후 비교판, 3×3 이음매 판, 섞어 쓴 모습 (dist/screenshots/blocks/core_*.png)

1층에 남긴 것: 돌·심층암 (자연석: 광석 그림이 이 바탕을 픽셀까지 같이 써서, 따로 그리면 광석과 어긋난다),
불·모닥불 불꽃 (바닐라가 손으로 움직인 장면 띠라 색만 옮긴다).

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
    "chiseled_deepslate": "구르기 길 시작 칸",
    "ladder": "시험 방 턱 사다리, 걷어찬 사다리 지름길 (r1.s.ladder)",
    "lantern": "시험 방 기둥 위·턱 위 랜턴, 모든 지역의 빛 (8.4)",
    "stone_bricks": "레딘 성벽 (R1)",
    "cracked_stone_bricks": "오다의 사당 (H), 레딘 성벽 (R1)",
    "mossy_stone_bricks": "오다의 사당 (H), 레딘 성벽 (R1)",
    "cobblestone": "레딘 성벽 (R1), 레버 받침",
    "mossy_cobblestone": "볼크 탑옥 (P) 의 이끼 돌",
    "andesite": "레딘 성벽 (R1)",
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
    # 소문자는 같은 돌의 한 칸을 한 단 밝게 (쪼갠 면의 턱, 결). 모양은 대문자로 본다
    lit = {(x, y) for y in range(h) for x in range(w) if g[y][x].islower()}
    g = [[c.upper() for c in r] for r in g]
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
            if (x, y) in lit:
                k = min(3, k + 1)
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


# ─────────────────────────── 램프 ───────────────────────────
# [깊은 그늘, 그늘, 바탕, 빛]. 밝기 (luma): ash0 .11 rust0 .15 ash1 .22 rust1 .26 ash2 .35 parch0 .38 ash3 .50 bone0 .51
# parch1 .51 bone1 .65 parch2 .64 bone2 .79

PALE = ["ash1", "ash2", "ash3", "bone1"]          # 바랜 회색 돌 (레딘 성벽)
WARM = ["ash1", "ash2", "bone0", "bone1"]         # 따뜻한 회색
OCHRE = ["rust1", "parch0", "parch1", "parch2"]   # 황토 돌 (Undead Burg)
SOOT = ["ash0", "ash1", "ash2", "ash3"]           # 그을린 돌
# 심층암 (탑옥, 시험 방): 블록 전용 점판암 계열의 찬 회색. 1층 (blocks_grade) 이 옮긴 심층암 광석·계단의 바탕과 같은 계열이다
SLATE = ["slate0", "slate1", "slate2", "slate3"]

# ─────────────────────────── 심층암 (시험 방, 탑옥) ───────────────────────────
# 찬 묘실 돌 (점판암 계열). 레딘의 바랜 마름돌 (돌 계열) 과 색온도로 갈린다. 시험 방이 이 돌로 지어져 있어 가장 자주 보인다.
# 명암은 낮게 (바탕 slate2, 빛 slate3 을 윗모서리 몇 칸에만): 어두운 방에서 줄눈만 또렷하다.

SLATE_DK = ["slate0", "slate0", "slate1", "slate2"]   # 그을음이 더 앉은 돌

DSB_ROWS = [  # 심층암 벽돌: 3픽셀 켜 넷, 이음줄은 켜마다 다른 자리. 소문자는 쪼갠 면의 턱
    "AAA.BBBBBBB.AAAA",
    "AAA.BBBbbBB.AAAA",
    "AAAA.BBBBBB.AAAA",
    "................",
    "CCCCCCC.DDDDDDD.",
    "CccCCCC.DDDDDDD.",
    "CCCCCC.DDDDDDDD.",
    "................",
    "F.EEEEEEEE.FFFFF",
    "F.EeEEEEEE.FFffF",
    "F.EEEEEEEE.FFFFF",
    "................",
    "HHHHH.GGGGGGG.HH",
    "HHHHH.GGGggGG.HH",
    "HHHHHH.GGGGGG.HH",
    "................",
]
DSB_RAMP = {"*": SLATE, "D": SLATE_DK, "H": SLATE_DK}
DSB_ARRIS = {"A": 3, "B": 5, "C": 2, "D": 4, "E": 6, "F": 3, "G": 2, "H": 4}


def deepslate_bricks():
    return masonry(DSB_ROWS, DSB_RAMP, ["slate0", "slate0"], arris=DSB_ARRIS)


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
        "  kk      x     ",
        "  k        xx   ",
        "             x  ",
        "                ",
        "                ",
        "    x           ",
        "     xx         ",
        "                ",
    ], {"x": "slate0", "k": "slate0"})


DST_ROWS = [  # 심층암 타일: 바닥과 지붕. 켜 셋 (4·4·5 픽셀), 이음줄은 켜마다 다르다
    "AA.BBBB.CCCC.AAA",
    "Aa.BBBB.CCcC.AAA",
    "AA.BbBB.CCCC.AAA",
    "AA.BBBB.CCCC.AaA",
    "................",
    ".DDDD.EEEE.FFFFF",
    ".DdDD.EEEE.FFFfF",
    ".DDDD.EEeE.FFFFF",
    ".DDDD.EEEE.FFFFF",
    "................",
    "III.GGGGG.HHH.II",
    "IiI.GGGGG.HHH.II",
    "III.GGgGG.HhH.II",
    "III.GGGGG.HHH.II",
    "III.GGGGG.HHH.iI",
    "................",
]
DST_RAMP = {"*": SLATE, "E": SLATE_DK, "I": SLATE_DK}  # 소문자: 타일마다 다른 자리의 닳은 턱
DST_ARRIS = {"A": 4, "B": 2, "C": 3, "D": 3, "E": 4, "F": 2, "G": 3, "H": 2, "I": 4}


def deepslate_tiles():
    return masonry(DST_ROWS, DST_RAMP, ["slate0", "slate0"], arris=DST_ARRIS)


def cracked_deepslate_tiles():
    t = deepslate_tiles()
    # 타일 하나는 귀가 깨져 아래 받침이 보이고 (깊은 그늘), 하나는 금이 가로질렀다
    return overlay(t, [
        "                ",
        "    x           ",
        "     x          ",
        "     xx         ",
        "                ",
        "             kk ",
        "              k ",
        "                ",
        "                ",
        "                ",
        "      x         ",
        "      x         ",
        "       x        ",
        "       x        ",
        "        x       ",
        "                ",
    ], {"x": "slate0", "k": "slate0"})


def polished_deepslate():
    # 한 장짜리 윤낸 판석. 윗모서리 왼쪽 반만 빛을 받고 (작은 타일 사이에서 네모 틀처럼 튀지 않게), 아래·오른쪽은 그늘.
    # 돌결 하나가 비스듬히 지나간다 (한 단 밝게, 끊기며)
    rows = ["PPPPPPPPPPPPPPP."] * 15 + ["................"]
    t = masonry(rows, {"P": SLATE}, ["slate0", "slate0"], arris={"P": 8})
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "              + ",
        "            ++  ",
        "          +     ",
        "        ++      ",
        "                ",
        "     ++         ",
        "   ++           ",
        "  +             ",
        "                ",
        "                ",
        "      -         ",
        "           +    ",
        "                ",
    ])


def chiseled_deepslate():
    # 구르기 길의 시작 칸: 판석에 새긴 고리와 그 안의 칼 한 자루 (화톳불의 말린 칼).
    # 홈은 왼쪽 위 벽이 그늘 (x), 오른쪽 아래 벽이 빛 (h). 고리 오른쪽 위는 닳아 끊겼다
    rows = ["PPPPPPPPPPPPPPP."] * 15 + ["................"]
    t = masonry(rows, {"P": SLATE}, ["slate0", "slate0"], mode="full")
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
        "   x    h   xh  ",
        "    x      xh   ",
        "     xxxxxxh    ",
        "      hhhhh     ",
        "                ",
        "                ",
    ], {"x": "slate0", "h": "slate3"})


CDS_ROWS = [  # 조각난 심층암: 판처럼 쪼개진 모난 조각 아홉. 소문자는 쪼갠 면의 턱
    "AAAA.BBBBBB.CCC.",
    "AaAA.BBBBBBB.CC.",
    "AAA.BBbbBBBB.CCA",
    "AAA.BBBBBBB..CAA",
    "AA..BBBBBB..DD.A",
    ".EEE.BBBB..DDDD.",
    "EEEEE....DDdDDD.",
    "EEeeEE.F.DDDDD.E",
    "EEEEE.FFF..DDD.E",
    ".EEE.FFFFF....GG",
    "H...FFfFFFF.GGGG",
    "HHH.FFFFFF.GGgGG",
    "HHhH..FFF.GGGGG.",
    "HHHHH.....GGGG.H",
    "HHHH.IIIIII...HH",
    ".HH.IIIiiIII...H",
]
CDS_RAMP = {"*": SLATE, "D": SLATE_DK, "H": SLATE_DK}
CDS_ARRIS = {"A": 3, "B": 4, "C": 2, "D": 3, "E": 4, "F": 3, "G": 4, "H": 3, "I": 5}


def cobbled_deepslate():
    return masonry(CDS_ROWS, CDS_RAMP, ["slate0", "slate0"], arris=CDS_ARRIS)


# ─────────────────────────── 돌벽돌 (레딘 성벽, 오다의 사당) ───────────────────────────
# 바랜 회색 마름돌. 켜 높이가 다르고 (5·4·4), 이음줄이 켜마다 다른 자리에 있다. 돌마다 바탕은 같은 밝기에
# 차고 따뜻한 회색만 다르다 (한 돌만 튀면 이어 놓았을 때 격자가 보인다). 물때는 윗줄눈에서 아래로 흐른다.

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
    # 이 빠진 귀 (c: 줄눈만큼 깊다), 물때 (-: 윗줄눈에서 두세 칸 흘러내리다 끊긴다), 황토 얼룩 (o: 돌 아래쪽에 고인 흙물)
    return overlay(t, [
        "               c",
        "        --      ",
        "         -      ",
        "         -      ",
        "c              c",
        "                ",
        " c   o          ",
        "            --  ",
        "             -  ",
        "    oo   c      ",
        "                ",
        "  -       oo    ",
        "  --       o    ",
        "   -            ",
        "c             c ",
        "                ",
    ], {"c": "rust0", "o": "parch0"})


def cracked_stone_bricks():
    t = stone_bricks()
    # 위 켜에서 시작해 아래 켜로 건너가는 긴 금 하나 (x), 가운데 켜의 돌 하나는 오른쪽 아래 귀가 떨어져 나갔다
    # (속 k, 깨진 면의 빛 h). 아래 켜에 짧은 금
    return overlay(t, [
        "         x      ",
        "        x       ",
        "        x       ",
        "       x        ",
        "       x        ",
        "      x         ",
        "      x         ",
        "     x      kk  ",
        "     x     kkh  ",
        "    x     kkkh  ",
        "                ",
        "             x  ",
        "            xx  ",
        "           x    ",
        "                ",
        "                ",
    ], {"x": "ash1", "k": "rust0", "h": "bone1"})


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


CB_ROWS = [  # 조약돌: 크기가 다른 둥근 돌 열. 모서리는 줄눈에 먹혀 둥글다. A·D·I 는 가장자리를 넘어 이어진다
    "AAAA...BBBBB..AA",
    "AAAAA.BBBBBBB.AA",
    ".AAAA.BBBBBBB..A",
    "D.AA..BBbBBB.DD.",
    "DD....F.BBB.DDDD",
    "DDD.FFFF...DDDDD",
    "DdD.FFfFF.DDDDdD",
    "DD.FFFFFF..DDDD.",
    "D..FFFFF.G..DD.I",
    ".I..FFF.GGGG...I",
    "III....GGgGGG.II",
    "IiII.J.GGGGGG.II",
    "IIII.JJ.GGGG..II",
    ".II.JJjJ....KK.I",
    "A..JJJJJ.KKKKKK.",
    "AA.JJJJ.KKKkKK.A",
]
CB_RAMP = {"A": PALE, "B": WARM, "D": WARM, "F": PALE, "G": WARM, "I": SOOT, "J": PALE, "K": OCHRE}
CB_MODES = {"B": "full", "F": "full", "J": "full"}


def cobblestone():
    return masonry(CB_ROWS, CB_RAMP, ["ash1", "rust0"], modes=CB_MODES, arris={"A": 3, "D": 4, "G": 3, "I": 2, "K": 4})


def mossy_cobblestone():
    # 탑옥의 이끼 돌: 같은 돌이 더 어둡고 젖었다 (황토 돌도 회색으로 바래고). 이끼는 틈 세 곳에 모여 아래로 흐른다
    t = masonry(CB_ROWS, {"A": SOOT, "B": PALE, "D": SOOT, "F": PALE, "G": SOOT, "I": SOOT, "J": PALE, "K": WARM},
                ["ash0", "rust0"], modes=CB_MODES, arris={"A": 3, "D": 4, "G": 3, "I": 2, "K": 4})
    return overlay(t, [
        "    mMM         ",
        "     MM         ",
        "     M          ",
        "     -          ",
        " MmMM           ",
        "  MMMm          ",
        "   M            ",
        "   -       mm   ",
        "          MMMM  ",
        "           MM   ",
        "      mm    -   ",
        "     MMM        ",
        "      M         ",
        "      -         ",
        "                ",
        "                ",
    ], {"m": "moss2", "M": "moss1"})


# 바위 (절벽, 안산암, 응회암, 방해석): 덩어리 배치도에 "soft" 명암 (덩어리 윗줄 빛, 아랫줄 그늘). 덩어리끼리 맞닿은 곳이
# 바위의 턱이 된다. 잡음 없이 덩어리 크기로만 결을 낸다. 소문자는 덩어리 안의 턱

ANDE_ROWS = [  # 안산암: 비스듬히 눌린 덩어리
    "AAAAABBBBBBBCCCC",
    "AAAABBBBBBBBCCCA",
    "AAAABBBbbBBCCCAA",
    "DDAAABBBBBCCCAAA",
    "DDDDAAAEEEECCAAA",
    "DDDDDEEEEEEEFFFD",
    "DDDDEEEeeEEFFFDD",
    "GDDDEEEEEFFFFFDD",
    "GGGDDDEEFFFFFFGG",
    "GGGGGHHHHFFFFGGG",
    "GGGGHHHHHHHIIGGG",
    "IGGHHHhhHHIIIIGI",
    "IIIIHHHHIIIIIIII",
    "IIIIIJJJJJIIIIII",
    "AAIIJJJJJJJJIAAA",
    "AAAAJJJJJJJAAAAA",
]


def andesite():
    t = masonry(ANDE_ROWS, {"*": PALE, "B": WARM, "E": WARM, "G": WARM, "J": WARM}, "ash2", mode="drop")
    # 작은 구멍 둘 (x, 아래 가장자리가 빛 l)
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "           x    ",
        "           l    ",
        "                ",
        "                ",
        "                ",
        "                ",
        "  x             ",
        "  l             ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
    ], {"x": "ash1", "l": "bone1"})


TUFF_ROWS = [  # 응회암: 크기가 다른 둥근 덩어리 다섯 (맞닿은 곳 아래만 엷은 그늘). 가로로 길게 이어지지 않게 엇갈렸다
    "AAAAAABBBBBBBAAA",
    "AAAAABBBBBBBBBAA",
    "AAAAABBBBBBBBBAA",
    "CCAAAABBBBBBBAAC",
    "CCCCAAABBBBBDDCC",
    "CCCCCCAAABBDDDDC",
    "CCCCCCCAADDDDDDD",
    "CCCCCCCEEDDDDDDD",
    "ECCCCCEEEEDDDDDE",
    "EEECCEEEEEEDDDEE",
    "EEEEEEEEEEEEDDEE",
    "AEEEEEEEEEEEEAAA",
    "AAEEEEEEEEEAAAAA",
    "AAAEEEEEEAAAAAAA",
    "AAAAAEEAAAAAAAAA",
    "AAAAAAAAAAAAAAAA",
]


def tuff():
    t = masonry(TUFF_ROWS, {"*": ["ash1", "stone0", "ash2", "stone1"]}, "ash1", mode="drop")
    # 숨구멍: 네 무리 (x 구멍, 바로 아래 l 은 구멍 아랫벽이 받은 빛), 바랜 자리 둘 (m)
    return overlay(t, [
        "                ",
        "  x x           ",
        "  l l     mm    ",
        "   x     mmm    ",
        "   l            ",
        "            x   ",
        "           xlx  ",
        "            l   ",
        "                ",
        " mm   x         ",
        "  m   lx        ",
        "       l        ",
        "              x ",
        "              l ",
        "       x        ",
        "       l        ",
    ], {"x": "ash1", "l": "ash3", "m": "parch0"})


CALC_ROWS = [  # 방해석: 큰 덩어리 넷, 그 사이를 가는 결 하나가 감아 돈다
    "AAAAAAAAAAAAAAAA",
    "AAAAAAAAAAAAAAAA",
    "AAAAAAAAAaaAAAAA",
    "AAAAAAAAAAAAAAAA",
    "BBBAAAAAAAAAABBB",
    "BBBBBBAAAAAABBBB",
    "BBBBBBBBBBBBBBBB",
    "BBbbBBBBBBBBBBBB",
    "BBBBBBBBBBBBBCCC",
    "CCCBBBBBBBBCCCCC",
    "CCCCCCCBBCCCCCCC",
    "CCCCCCCCCCCCCcCC",
    "CCCCCCCCCCCCCCCC",
    "DDDCCCCCCCCDDDDD",
    "DDDDDDCCDDDDDDDD",
    "DDDDDDDDDDDDDDDD",
]
CALC = ["parch0", "parch1", "bone0", "bone1"]     # 바랜 방해석: 회녹빛 교구 벽 사이에서 튀지 않게 한 단 낮췄다


def calcite():
    t = masonry(CALC_ROWS, {"*": CALC}, "bone0", mode="drop")
    # 회색 결 (v) 하나가 위에서 비스듬히 내려와 두 덩어리를 가로지른다
    return overlay(t, [
        "    v           ",
        "    v           ",
        "     v          ",
        "     v          ",
        "      v         ",
        "       vv       ",
        "                ",
        "                ",
        "                ",
        "                ",
        "           v    ",
        "           v    ",
        "            v   ",
        "                ",
        "                ",
        "    v           ",
    ], {"v": "ash3"})


TB_ROWS = [  # 응회암 벽돌 (교구): 두 켜의 길쭉한 돌, 아래 켜는 짧은 돌이 끼었다
    "AAAAAAAAA.BBBBB.",
    "AAAAAAAAA.BBBBB.",
    "AAAAAAAAa.BBBBB.",
    "AAAAAAAAA.BBBBB.",
    "AAAAAAAAA.BBBBB.",
    "AAAAAAAAA.BBBBB.",
    "AAAAAAAAA.BBBBB.",
    "................",
    "DDD.CCCCCCCC.DDD",
    "DDD.CCCCCCcC.DDD",
    "DDD.cCCCCCCC.DDD",
    "DDD.CCCCCCCC.DDD",
    "DDD.CCCCCCCC.DDD",
    "DDD.CCCCCCCC.DDD",
    "DDD.CCCCCCCC.DDD",
    "................",
]
TUFF = ["moss0", "ash1", "ash2", "ash3"]        # 축축한 회녹: 깊은 그늘만 이끼빛이다


def tuff_bricks():
    t = masonry(TB_ROWS, {"*": TUFF}, ["moss0", "ash1"], arris={"A": 5, "B": 2, "C": 4, "D": 2})
    # 젖은 아래쪽: 돌마다 아래 두세 줄에 물이 차오른 자국 (m, 높이가 고르지 않다)
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "                ",
        "            -   ",
        " --  ---   --   ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "      --     -  ",
        "    --  ---     ",
        "                ",
        "                ",
    ])



def smooth_stone():
    # 매끈하게 다듬은 판석 (교구): 테두리 베벨, 판 가운데는 조용하다. 정 자국 둘
    rows = ["PPPPPPPPPPPPPPP."] * 15 + ["................"]
    t = masonry(rows, {"P": ["ash1", "ash2", "ash3", "bone0"]}, ["ash2", "ash2"], mode="full")
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "                ",
        "    -           ",
        "     -          ",
        "                ",
        "                ",
        "                ",
        "           -    ",
        "            -   ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
    ])


def smooth_stone_slab_side():
    # 반 블록 둘을 포갠 옆면: 위아래 판마다 베벨, 가운데 이음줄. 모서리 두 곳이 닳았다
    rows = ["PPPPPPPPPPPPPPP."] * 7 + ["................"] + ["QQQQQQQQQQQQQQQ."] * 7 + ["................"]
    t = masonry(rows, {"*": ["ash1", "ash2", "ash3", "bone0"]}, ["ash2", "ash2"], mode="full")
    return overlay(t, [
        "                ",
        "                ",
        "         -      ",
        "                ",
        "                ",
        "      -         ",
        "                ",
        "                ",
        "                ",
        "   -            ",
        "                ",
        "                ",
        "                ",
        "           +    ",
        "                ",
        "                ",
    ])



# ─────────────────────────── 나무 (레딘 성벽: 가문비·짙은 참나무, 사다리, 비계, 탑옥의 썩은 건초) ───────────────────────────
# 비바람에 바랜 목재. 가문비는 회갈색 (녹슨 철 계열에 은빛으로 바랜 결 ash2), 짙은 참나무는 그을린 청동처럼 검다.
# 판자는 켜마다 이음매 자리가 다르고, 이음매 옆에 못. 결은 길게 흐르다 끊긴다. 판자는 그림 글자로 직접 찍는다.


def spruce_planks():
    # d 틈·못, a 그늘 결, b 바탕, c 밝은 결, g 은빛으로 바랜 결
    return paint([
        "bbcccbbbbbbadcbb",
        "bbbbbbbaaabbdbbb",
        "aaaabaaaaaaadaaa",
        "dddddddddddddddd",
        "bbbadcbbbccccbbb",
        "bggbdbbbbbbbbaab",
        "aaaadaaabaaaaaaa",
        "dddddddddddddddd",
        "bccbbbbbadbbbbbb",
        "bbbbaaabbdbbgggb",
        "aaaaaaaaadaabaaa",
        "dddddddddddddddd",
        "bbbbbbcccccbbbbb",
        "bdabbbbbbbbbaabb",
        "aaaaaaaaaaabaaaa",
        "dddddddddddddddd",
    ], {"d": "rust0", "a": "rust1", "b": "rust2", "c": "rust3", "g": "ash2"})


def dark_oak_planks():
    # 넓은 판 셋 (가문비와 다른 폭). d 틈, a 그늘 결, b 바탕, c 밝은 결, n 못 머리
    return paint([
        "bbbcccbbbbbbbbbb",
        "bbbbbbbbaaabbbbb",
        "baaabbbbbbbbcccb",
        "aaaaabaabaaaaaab",
        "dddddddddddddddd",
        "bbbbbbbbbndcbbbb",
        "bccbbbbbbbdbbaab",
        "bbbbaabcbbdbbbcb",
        "bbbbbbbbccdbbbbb",
        "aaaaaaaaandaaaaa",
        "dddddddddddddddd",
        "bbbdcbbbbbbbbbbb",
        "bbndbbbbbaaabccb",
        "bccdbbbbbbbbbbbb",
        "aaadaaaaaaaaaaaa",
        "dddddddddddddddd",
    ], {"d": "ash0", "a": "rust0", "b": "bronze0", "c": "rust1", "n": "ash0"})


def bark(furrows, breaks, ink, silver=(), pits=()):
    """
    나무껍질 (옆면). furrows: 홈마다 16줄의 x 자리 (손으로 정한 굽이). 홈과 홈 사이가 껍질 판 하나.
    판의 왼쪽 열은 빛 (b), 나머지는 바탕 (a), 홈은 d. breaks: (판 번호, y) = 판이 가로로 갈라진 자리 (e 줄, 바로 아래 줄은 빛).
    silver: 은빛으로 바랜 칸 (g). pits: 판에 패인 자리 (e).
    """
    t = Tex()
    for y in range(16):
        xs = sorted(f[y] % 16 for f in furrows)
        for x in range(16):
            t[x, y] = ink["a"]
        for i, fx in enumerate(xs):
            t[fx, y] = ink["d"]
            t[fx + 1, y] = ink["b"]
    for i, y in breaks:
        xs = sorted(f[y] % 16 for f in furrows)
        x0, x1 = xs[i] + 1, xs[(i + 1) % len(xs)]
        if x1 <= x0:
            x1 += 16
        for x in range(x0, x1):
            t[x, y] = ink["e"]
            if t[x, y + 1] == ink["a"]:
                t[x, y + 1] = ink["b"]
    for x, y in silver:
        if t[x, y] in (ink["a"], ink["b"]):
            t[x, y] = ink["g"]
    for x, y in pits:
        if t[x, y] in (ink["a"], ink["b"], ink["g"]):
            t[x, y] = ink["e"]
    return t


def spruce_log():
    # 가문비 껍질: 좁은 판이 굽이진 세로 홈 넷 사이에 있다. 판 끝이 가로로 갈라졌고, 볕 쪽 몇 칸은 은빛으로 바랬다
    f = [[3, 3, 3, 3, 4, 4, 4, 4, 4, 3, 3, 3, 3, 3, 3, 3],
         [6, 6, 6, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6],
         [11, 11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 11, 11, 11, 11],
         [15, 15, 15, 15, 15, 15, 15, 15, 0, 0, 0, 0, 0, 15, 15, 15]]
    return bark(f, [(0, 5), (1, 11), (2, 2), (3, 8), (2, 13)],
                {"a": "rust1", "b": "rust2", "d": "ash0", "e": "rust0", "g": "ash2"},
                silver=[(8, 5), (8, 6), (9, 9), (1, 12), (13, 2), (13, 3), (13, 9)],
                pits=[(1, 7), (9, 3), (13, 11), (5, 14), (10, 12), (12, 8)])


def dark_oak_log():
    # 짙은 참나무 껍질: 판이 넓고 (홈 셋), 가로로 자주 갈라져 네모난 덩어리가 된다
    f = [[2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2],
         [8, 8, 8, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 8],
         [13, 13, 13, 13, 13, 13, 13, 12, 12, 12, 12, 12, 13, 13, 13, 13]]
    return bark(f, [(0, 3), (0, 10), (1, 6), (1, 14), (2, 1), (2, 8)],
                {"a": "bronze0", "b": "rust1", "d": "ash0", "e": "rust0", "g": "rust2"},
                silver=[(4, 12), (10, 3), (6, 7), (5, 9), (11, 13)],
                pits=[(5, 2), (10, 6), (4, 13), (15, 10), (9, 14), (1, 7), (7, 10)])


def spruce_log_top():
    # 잘린 면: 껍질 테 (b, k), 한쪽으로 쏠린 나이테 (r 어두운 테, l 밝은 테, 군데군데 겹친다), 가운데에서 위로 갈라진 틈 (x)
    return paint([
        "bbbbbbbbbbbbbbbb",
        "bkkkkkkkkkkkkkkb",
        "bklllllllllxlllb",
        "bklrrrrrrrrxrrkb",
        "bkrlllllllxllrkb",
        "bkrlrrrrrrxrrlkb",
        "bkrlrllllxllrlkb",
        "bkrlrlrrrxrlrlkb",
        "bkrlrlrlxlrlrlkb",
        "bkrlrlrrrrrlrlkb",
        "bkrlrllllllrrlkb",
        "bkrlrrrrrrrrllkb",
        "bkrllllllllllrkb",
        "bklrrrrrrrrrrlkb",
        "bkkllllllllllkkb",
        "bbbbbbbbbbbbbbbb",
    ], {"b": "rust0", "k": "rust1", "l": "rust3", "r": "rust2", "x": "rust0"})


def dark_oak_log_top():
    # 짙은 참나무 잘린 면: 껍질이 두껍고 (b, k 두 겹), 나이테가 가운데로 몰렸다. 틈은 왼쪽 아래로
    return paint([
        "bbbbbbbbbbbbbbbb",
        "bkkkkkkkkkkkkkkb",
        "bkkllllllllllkkb",
        "bklrrrrrrrrrrlkb",
        "bklrllllllllrlkb",
        "bklrlrrrrrrlrlkb",
        "bklrlrllllrlrlkb",
        "bklrlrlrrlrlrlkb",
        "bklrlrlrlrrlrlkb",
        "bklrlrxlllrlrlkb",
        "bklrlxrrrrrlrlkb",
        "bklrxllllllrrlkb",
        "bklxrrrrrrrrlkkb",
        "bkxlllllllllkkkb",
        "bkkkkkkkkkkkkkkb",
        "bbbbbbbbbbbbbbbb",
    ], {"b": "ash0", "k": "rust0", "l": "rust1", "r": "bronze0", "x": "ash0"})


def ladder():
    # 걷어찬 사다리: 거친 기둥 둘 (x=2..3, 12..13) 과 가로대 넷. 가로대와 기둥이 만나는 곳은 밧줄로 감았다 (o)
    ink = {"a": "rust1", "b": "rust2", "c": "rust3", "d": "rust0", "o": "parch0", "p": "parch1"}
    return paint([
        "..bd........bd..",
        ".coccbcbcbcboco.",
        ".dodaaaaaaadaod.",
        "..bd........bd..",
        "..bd........ad..",
        ".cpcbccbcbccpcb.",
        ".dodaadaaaaaodd.",
        "..bd........bd..",
        "..ad........bd..",
        ".bocbcbcccbcocb.",
        ".dodaaaaadaaodd.",
        "..bd........bd..",
        "..bd........bd..",
        ".cpccbcbcbccpcc.",
        ".dodaaadaaaaodd.",
        "..bd........ad..",
    ], ink)


def scaffolding_side():
    # 비계 옆면: 바닐라와 같은 자리 (위 4줄, 아래 2줄, 양옆 2열). 거친 각목, 귀마다 밧줄 (o)
    ink = {"a": "rust1", "b": "rust2", "c": "rust3", "d": "rust0", "o": "parch0", "p": "parch1"}
    return paint([
        "cbbcbbbcbbbbcbbc",
        "opbaabaaabaabapo",
        "ddddddddddddddda",
        "obddbdddbddbddbo",
        "cb............cb",
        "ba............ba",
        "bd............bd",
        "cb............ca",
        "ba............bd",
        "bd............ba",
        "ca............cb",
        "bd............bd",
        "ba............ba",
        "cb............cd",
        "opbcbbbbbcbbbcpo",
        "ddadddaddadddado",
    ], ink)


def scaffolding_top():
    # 비계 윗면: 테두리 각목 위에 판자 넷을 깔았다. 판 사이 틈 (투명), 판 끝에 못 (n), 바랜 결 (g)
    ink = {"a": "rust1", "b": "rust2", "c": "rust3", "d": "rust0", "o": "parch0", "n": "rust0", "g": "ash2"}
    return paint([
        "ocbbcbbbcbbbcbbo",
        "cbaabaaabaaabadb",
        "badbn.bnb.nbb.db",
        "bacbb.bbb.cbb.ab",
        "dabbb.cbb.bbb.db",
        "bacgb.bbb.bgb.ab",
        "dabgb.bbc.bgb.db",
        "babbb.bbb.bbb.ab",
        "dabbb.gbb.bbc.db",
        "bacbb.gbb.bbb.ab",
        "dabbb.bbb.bbb.db",
        "babcb.bab.bbb.ab",
        "dabbn.bnb.nbb.db",
        "bdaddaddaddadddb",
        "cbdbbdbbdbbdbbdb",
        "ocddaddaddaddado",
    ], ink)


def scaffolding_bottom():
    # 비계 밑면: 테두리 각목만
    ink = {"a": "rust1", "b": "rust2", "c": "rust3", "d": "rust0", "o": "parch0"}
    return paint([
        "ocbbcbbbcbbbcbbo",
        "cbaabaaabaabbadb",
        "ba............db",
        "ca............db",
        "ba............da",
        "cb............db",
        "ba............da",
        "ca............db",
        "ba............da",
        "cb............db",
        "ba............da",
        "ca............db",
        "ba............da",
        "cb............db",
        "bddaddaddadaddab",
        "oddaddaddaddaddo",
    ], ink)


def hay_block_side():
    # 탑옥의 썩은 건초: 젖어 검게 바랜 짚단. 굵기와 길이가 다른 짚 (밝은 짚 l, 바탕 a, 그늘 d, 꺾인 짚 끝 k),
    # 묶은 끈 두 줄 (r 끈, s 끈 아래 그늘), 곰팡이 (m) 는 끈 위에 고여 아래로 번졌다
    return paint([
        "adlaldaadlaldada",
        "dlaaldadlaaldaal",
        "aadlakdaldaladla",
        "rrrrrrrrrrrrrrrr",
        "ssrsssrsssrssrss",
        "dlaaldaldmmldadl",
        "laaldaaladmaldal",
        "aldadlaaldaalada",
        "ldaaldlaadklaadl",
        "daldaalddaalaldl",
        "aldaldaaldlaadla",
        "rrrrrrrrrrrrrrrr",
        "srssrsssrsssrsss",
        "mmlaldadlaldalda",
        "amdaldalaadlaald",
        "aldlaadlaldaldla",
    ], {"a": "bronze1", "l": "bronze2", "d": "bronze0", "k": "parch0", "r": "rust0", "s": "rust1", "m": "moss1"})


def hay_block_top():
    # 짚단 윗면: 잘린 짚 끝이 다발로 모였다 (다발마다 밝은 끝 l 과 그늘 d), 오른쪽 아래 다발은 썩어 내려앉았다 (m, k)
    return paint([
        "aldaaldaldaaldal",
        "dlaldalaldladala",
        "aaldaaldaaldaald",
        "ldalldaldalldala",
        "aaldaalaaldaaald",
        "dlaaldaldlaaldla",
        "aldaaldaaaldaaal",
        "daldalaldaldalda",
        "aaaldaaldaakkdda",
        "ldaaaldaakmmkdla",
        "aldldaaldkmmmkal",
        "daaaldaaaakmkdla",
        "alddaaldaaakdaal",
        "daaldaaldlaaaald",
        "aldaaldaaaldaala",
        "ldaldaaldaalddal",
    ], {"a": "bronze1", "l": "bronze2", "d": "bronze0", "m": "moss0", "k": "rust0"})



# ─────────────────────────── 쇠와 구리 (탑옥 쇠창살, 사슬, 쇠문, 레버, 교구의 구리) ───────────────────────────
# 무딘 쇠: 재 계열 (빛 ash3, 바탕 ash2, 그늘 ash1), 녹은 녹슨 철 계열이 아래쪽으로 흘러내린다.


def iron_bars():
    # 벼린 네모 창살 셋 (바닐라와 같은 x=2..3, 7..8, 12..13: 기둥·옆 모형이 이 열을 쓴다) 을 가로 띠쇠 둘이 묶는다.
    # 창살: 왼쪽 열 빛 (c), 오른쪽 열 그늘 (a). 띠쇠: 윗줄 빛, 아랫줄 그늘, 창살과 만나는 곳에 징 (o).
    # 녹 (r, s) 은 띠쇠 아래와 창살 밑동에 고였다
    return paint([
        "..ca....ca...ca.",
        "..ca....ca...ca.",
        "..ca....ca...ca.",
        "cccccccccccccccc",
        "bbobbbbbobbbbobb",
        "aasaaaaaaaaaraaa",
        "..cr....ca...ca.",
        "..ca....cr...ca.",
        "..ca....ca...cr.",
        "..ca....ca...ca.",
        "cccccccccccccccc",
        "bobbbbbbobbbbbob",
        "aaaraaaaasaaaaaa",
        "..cr....ca...cr.",
        "..ra....cr...ca.",
        "..rs....rs...rs.",
    ], {"a": "ash1", "b": "ash2", "c": "ash3", "o": "bone1", "r": "rust2", "s": "rust1"})


def iron_chain():
    # 사슬 (바닐라와 같은 자리: x 0..2 와 3..5 두 면). 고리 바깥 빛 (c), 바탕 (b), 그늘 (a), 아래 고리에 녹 (r)
    return paint([
        "...a.a..........",
        "cbbaab..........",
        "b.a.............",
        "aabcbb..........",
        "...b.a..........",
        "...a.a..........",
        "cbbaab..........",
        "b.r.............",
        "a.a.............",
        "aabbbb..........",
        "...b.a..........",
        "...a.r..........",
        "cbraab..........",
        "b.r.............",
        "aarcbb..........",
        "...r.a..........",
    ], {"a": "ash1", "b": "ash2", "c": "ash3", "r": "rust2"})


def iron_door_top():
    # 탑옥 마당 쇠문 윗짝: 테 (빛 c, 그늘 a), 판에 징 (o 와 그늘 k), 창살 낀 작은 창 하나 (투명 칸 사이 창살)
    return paint([
        "cccccccccccccccc",
        "cbbbbbbbbbbbbbba",
        "cbokbbbbbbbbokba",
        "cbbbaaaaaaaabbba",
        "cbbba.c..c.cbbba",
        "cbbba.c..c.cbbba",
        "cbbba.c..c.cbbba",
        "cbbba.c..c.cbbba",
        "cbbbccccccccbbba",
        "cbbbbbbbbbbbbbba",
        "cccccccccccccccc",
        "bbokbbbbbbbbokba",
        "abbbbbbbbbbbbbba",
        "cbbbbbbbbbbbbbba",
        "cbokbbbbbbbbbrba",
        "cbbbbbbbbbbbbrra",
    ], {"a": "ash1", "b": "ash2", "c": "ash3", "o": "bone0", "k": "ash1", "r": "rust2"})


def iron_door_bottom():
    # 아랫짝: 띠쇠 둘과 징, 바닥 쪽으로 녹이 흘러 번졌다 (r, s). 아래 가장자리는 땅에 끌려 긁혔다 (l)
    return paint([
        "cbbbbbbbbbbbbbba",
        "cbokbbbbbbbbokra",
        "cbbbbbbbbbbbbbra",
        "cccccccccccccccc",
        "bbokbbbbbbbbokba",
        "abbbbbbbbbrbbbba",
        "cbbbbbbbbbrbbbba",
        "cbbbbbbbbbbbbbba",
        "cbbbrbbbbbbbbbba",
        "cccccccccccccccc",
        "bbokbbbbbrbbokba",
        "abbbbbbbbrbbbbra",
        "cbbbrbbbbsbbbbra",
        "cbbbrbbbrsbbbrsa",
        "crbrsbbbssrbrssa",
        "aalsaalasaalaasa",
    ], {"a": "ash1", "b": "ash2", "c": "ash3", "o": "bone0", "k": "ash1", "r": "rust2", "s": "rust1", "l": "bone0"})


def lever():
    # 레버 손잡이 (바닐라와 같은 자리 x=7..8, y=6..15): 쇠 고리 머리, 손때 묻은 나무 자루
    return paint([
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        ".......ca.......",
        ".......ba.......",
        ".......ed.......",
        ".......fd.......",
        ".......ed.......",
        ".......ed.......",
        ".......fd.......",
        ".......ed.......",
        ".......eg.......",
        ".......dg.......",
    ], {"a": "ash1", "b": "ash2", "c": "ash3", "d": "rust1", "e": "rust2", "f": "rust3", "g": "rust0"})


def oxidized_copper():
    # 교구의 녹청 낀 구리판: 그을린 청동 바탕 (b), 판 이음 (a 그늘, c 빛), 이음의 징 (o). 녹청 (m, n) 은 윗 이음에서 생겨
    # 아래로 흘렀고, 한 줄은 이음을 넘어 아래 판까지 내려갔다
    return paint([
        "ccoccccccocccccc",
        "bmmnbbmbbbnmmbba",
        "bmnbbbmbbbbnbbba",
        "bnbbbbnbbbbmbbba",
        "bmbbbbnbbbbnbbba",
        "bnbbbbnbbbbbbbba",
        "bbbbbbnbbbbbbbba",
        "aaaaaanaaaaaaaaa",
        "cccoccnccccocccc",
        "bbbnmmbbbbbbmnbb",
        "bbbbnmbbbbbbbmbb",
        "bbbbbnbbbbbbbnbb",
        "bbbbbmbbbbbbbbbb",
        "bbbbbnbbbbbbbbbb",
        "bbbbbbbbbbbbbbbb",
        "aaaaaaaaaaaaaaaa",
    ], {"a": "bronze0", "b": "bronze1", "c": "bronze2", "m": "moss2", "n": "moss1", "o": "bronze3"})


# ─────────────────────────── 빛 (랜턴, 초, 모닥불) ───────────────────────────
# 빛은 불씨 계열 (빛 허용 그림: 팩의 블록 빛 목록, palette.BLOCK_GLOW). 쇠 틀은 그을린 쇠, 유리는 그을음이 앉았다.

LANTERN_FRAME = [
    ".abba...........",
    ".cddc......baa..",
    "abbbba.....a.e..",
    "d1111d.....a.e..",
    "c1111c.....eae..",
    "c1111c..........",
    "c1111c.....a.e..",
    "d1111d.....eae..",
    "abbbba..........",
    "aakkaa..........",
    "akbbka.....baa..",
    "kbbbbk.....a.e..",
    "kbbbbk..........",
    "akbbka..........",
    "aakkaa..........",
    "................",
]
# 불꽃 세 프레임 (유리 4×5 칸). 1 바깥 불, 2 불, 3 속불, 4 심지 위 가장 밝은 곳
LANTERN_FLAME = [
    ["1221", "2332", "2343", "3432", "2332"],
    ["1211", "2332", "3342", "2433", "2322"],
    ["1121", "2323", "2433", "3342", "2332"],
]


def lantern():
    ink = {"a": "ash1", "b": "rust1", "c": "rust2", "d": "rust0", "e": "ash0", "k": "ash0"}
    flame = {"1": "ember1", "2": "ember2", "3": "ember3", "4": "bone3"}
    out = Tex(16, 48)
    for f, fl in enumerate(LANTERN_FLAME):
        rows = []
        gy = 0
        for r in LANTERN_FRAME:
            if "1111" in r:
                r = r.replace("1111", fl[gy])
                gy += 1
            rows.append(r)
        t = paint(rows, {**ink, **flame})
        out.paste(t, 0, f * 16)
    return out


def candle():
    # 오래된 누런 초 (모형: 심지 x0 y5, 윗면 y6..7, 옆면 y8..13, 밑면 y14..15). 촛농이 한쪽으로 흘러내렸다
    return paint([
        "................",
        "................",
        "................",
        "................",
        "................",
        "a...............",
        "bc..............",
        "cb..............",
        "bd..............",
        "cd..............",
        "bc..............",
        "bd..............",
        "cd..............",
        "dd..............",
        "dd..............",
        "dd..............",
    ], {"a": "ash0", "b": "bone2", "c": "bone1", "d": "bone0"})


def candle_lit():
    # 켠 초: 불꽃에 녹은 윗면이 밝고 (뼈 3), 심지 끝이 탄다 (불씨 0)
    return paint([
        "................",
        "................",
        "................",
        "................",
        "................",
        "e...............",
        "fb..............",
        "bf..............",
        "bc..............",
        "cb..............",
        "bd..............",
        "cd..............",
        "cd..............",
        "dd..............",
        "dd..............",
        "dd..............",
    ], {"e": "ember0", "f": "bone3", "b": "bone2", "c": "bone1", "d": "bone0"})


CAMPFIRE = [  # 위 4줄: 숯이 된 통나무 옆면, x0..3 y4..7: 잘린 끝, 아래 8줄: 재 바닥 (모형이 y8..15 를 쓴다)
    "aadaawaadaaadwaa",
    "dabddaddbaddaabd",
    "aaddaaadaaabdaad",
    "ddaddddaddaddadd",
    "ewwe............",
    "wrrw............",
    "wrxw............",
    "ewwe............",
    "gggghhhggggggggg",
    "gkkggggggggghhhg",
    "gkdggggkkggggggg",
    "ggggggggkdgggggg",
    "ghhhggggggggkkgg",
    "gggggkkgggggkdgg",
    "ggggggkdgghhhggg",
    "gggggggggggggggg",
]
CAMPFIRE_INK = {"a": "ash1", "d": "ash0", "b": "rust1", "w": "rust2", "e": "rust0", "r": "rust3", "x": "rust1",
                "g": "ash2", "h": "ash3", "k": "ash1"}
# 켠 화톳불의 불씨 자리 (프레임마다): e 불씨 1 (어두운 불), f 불씨 2 (밝은 불). 숯 조각 가장자리와 통나무 틈을 따라 달아오른다
CAMPFIRE_EMBERS = [
    {"e": [(2, 1), (9, 2), (13, 2), (3, 4), (4, 4), (10, 4), (11, 5), (2, 9), (3, 10), (7, 10), (8, 10), (9, 11),
           (12, 12), (13, 13), (6, 13)],
     "f": [(4, 5), (11, 4), (8, 11), (7, 13)]},
    {"e": [(2, 1), (10, 1), (13, 2), (4, 4), (5, 4), (10, 4), (12, 5), (1, 9), (2, 10), (7, 10), (9, 11), (12, 13),
           (13, 12), (6, 13), (7, 14)],
     "f": [(3, 5), (10, 5), (8, 10), (13, 13)]},
    {"e": [(3, 1), (9, 2), (12, 1), (3, 4), (4, 5), (11, 4), (10, 5), (2, 9), (3, 10), (8, 10), (8, 11), (12, 12),
           (6, 13), (7, 14)],
     "f": [(4, 4), (11, 5), (9, 11), (12, 13), (2, 10)]},
    {"e": [(2, 1), (9, 1), (14, 2), (4, 4), (3, 5), (10, 5), (11, 4), (1, 9), (2, 9), (7, 10), (9, 11), (13, 12),
           (12, 13), (7, 13), (6, 14)],
     "f": [(4, 5), (8, 10), (6, 13), (13, 13)]},
]


def campfire_log():
    # 꺼진 화톳불: 숯이 된 통나무 (껍질 a·d, 덜 탄 나무 w), 잘린 끝의 나이테, 재 바닥 (재 g, 쌓인 재의 턱 h, 숯 조각 k·d)
    return paint(CAMPFIRE, CAMPFIRE_INK)


# 켠 화톳불의 y4..7 은 엇갈린 통나무의 아랫면이다 (모형이 [0,4,16,8] 을 쓴다): 숯이 된 아랫면
CAMPFIRE_UNDER = [
    "dadaadaaddadaaad",
    "adddaddadaadddaa",
    "daadadddaddaaadd",
    "ddaddaddaddaddad",
]


def campfire_log_lit():
    # 켠 화톳불 (바닐라와 같이 4 프레임, 섞어 넘긴다): 같은 숯과 재에서 불씨 자리만 프레임마다 옮겨 간다
    out = Tex(16, 64)
    lit_rows = CAMPFIRE[:4] + CAMPFIRE_UNDER + CAMPFIRE[8:]
    for i, em in enumerate(CAMPFIRE_EMBERS):
        t = paint(lit_rows, CAMPFIRE_INK)
        for x, y in em["e"]:
            t[x, y] = "ember1"
        for x, y in em["f"]:
            t[x, y] = "ember2"
        out.paste(t, 0, i * 16)
    return out


# ─────────────────────────── 흙 (레딘의 진흙 벽돌·갈색 테라코타는 마른 피 얼룩), 재, 불 받침 ───────────────────────────

MUD_ROWS = [  # 진흙 벽돌: 켜 셋, 벽돌이 고르지 않게 길다
    "AAAAAAA.BBBBBBB.",
    "AAaAAAA.BBBBBBB.",
    "AAAAAAA.BBBbbBB.",
    "AAAAAAA.BBBBBBB.",
    "................",
    "CCC.DDDDDDDD.CCC",
    "CCC.DDDDDDDD.CcC",
    "CCC.DDDdDDDD.CCC",
    "CCC.DDDDDDDD.CCC",
    "................",
    "EEEEEEEEE.FFFFF.",
    "EEEEeEEEE.FFFFF.",
    "EEEEEEEEE.FFfFF.",
    "EEEEEEEeE.FFFFF.",
    "EEeEEEEEE.FFFFF.",
    "................",
]
MUD = ["rust0", "rust1", "rust2", "rust3"]


def mud_bricks():
    t = masonry(MUD_ROWS, {"*": MUD, "D": ["rust0", "rust1", "parch0", "rust3"]}, ["parch0", "parch0"],
                arris={"A": 3, "B": 5, "C": 2, "D": 6, "E": 4, "F": 2})
    # 검게 마른 얼룩: 윗켜 벽돌 하나에 손바닥만 하게 묻어 (k 진한 곳, l 마른 가장자리) 아래로 한 줄 흘렀다.
    # 붉은 핏자국은 갈색 테라코타가 맡는다 (벽돌마다 붉은 자국이 찍히면 벽에 도장처럼 늘어선다)
    return overlay(t, [
        "                ",
        "        ll      ",
        "        lkl     ",
        "        lkkl    ",
        "         k      ",
        "                ",
        "         l      ",
        "         l      ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
    ], {"k": "rust0", "l": "rust1"})


def brown_terracotta():
    # 갈색 테라코타 = 마른 피가 스며 굳은 흙 (레딘 성벽의 핏자국 자리). 말라 갈라진 껍질: 조각 (a 바탕, b 조각 윗가장자리의 빛)
    # 사이로 틈 (k). 조각 몇은 피가 덜 말라 더 붉다 (r). 틈은 가장자리를 넘어 이어진다
    return paint([
        "aaaakaaaaaaaakaa",
        "baaakaaaarraakaa",
        "baaakkaarrraakaa",
        "aaaaakkaaaaakaaa",
        "kkkaaakkkkkkkaaa",
        "aakkaaaakbaaaakk",
        "aaakaaaaakbaaaaa",
        "araakaaaakaaaaaa",
        "arraakaaakaarraa",
        "aaaaakkkkkaarrra",
        "kkaaakaaaaakkaaa",
        "aakkkaaaaaaakkkk",
        "aaaakaaaaaaaakba",
        "aaaakaaaarraakaa",
        "aaaaakaaaaaaakaa",
        "aaaaakaaaaaakaaa",
    ], {"a": "rust1", "b": "rust2", "k": "blood0", "r": "blood0"})


def light_gray_concrete_powder():
    # 사당의 재: 고운 재가 바람에 쓸린 결. 길이가 다른 낮은 턱 (b 빛 받은 윗면, 바로 아래 d 그늘) 이 비스듬히 흩어졌고,
    # 덜 탄 숯 조각 (k) 둘
    return paint([
        "aaaaaaaaaaaaaaaa",
        "aaabbbbbaaaaaaaa",
        "aaadddddddaaaaaa",
        "aaaaaaaaaaaaaaaa",
        "aaaaaaaaaabbbbaa",
        "aaaaaaaaaaaadddd",
        "aaaaaaaaaaaaaaaa",
        "bbaaaaaaaaaaaabb",
        "ddaaaaaaaaaaaaad",
        "aaaaaabbbbbbbaaa",
        "aaaaaabbbbbbbbaa",
        "aaaaaaaddddddaaa",
        "aaaaaaaaaaaaaaaa",
        "aaabbbaaaaaakaaa",
        "aaaaaddaaaaaaaaa",
        "aaaaaaaaaaaaaaaa",
    ], {"a": "ash3", "b": "bone0", "d": "ash2", "k": "ash1"})


NR_ROWS = [  # 불 받침 바위: 그을린 덩어리
    "AAAAAABBBBBBBBAA",
    "AAAAABBBBBBBBBAA",
    "AAAAABBBBBBBBAAA",
    "CCAAAABBBBBDDDAA",
    "CCCCAAAABBDDDDDC",
    "CCCCCCAAADDDDDCC",
    "CCCCCCCEEDDDDCCC",
    "CCCCCCEEEEEDDCCC",
    "FFCCCEEEEEEEGGGF",
    "FFFFEEEEEEEGGGGF",
    "FFFFFEEEEEGGGGGF",
    "FFFFFFHHHHGGGGGF",
    "AFFFFHHHHHHGGGAA",
    "AAFFHHHHHHHHGAAA",
    "AAAAHHHHHHHHAAAA",
    "AAAAAHHHHHHAAAAA",
]


def netherrack():
    t = masonry(NR_ROWS, {"*": ["ash0", "rust0", "blood0", "blood1"]}, "ash0", mode="drop")
    # 불에 터진 틈 (x)
    return overlay(t, [
        "                ",
        "   x            ",
        "    x           ",
        "                ",
        "                ",
        "            x   ",
        "           x    ",
        "                ",
        "                ",
        "  x             ",
        "                ",
        "                ",
        "         x      ",
        "          x     ",
        "                ",
        "                ",
    ], {"x": "ash0"})


# ─────────────────────────── 색유리 (교구: 회색·갈색·검은색), 거미줄, 마른 덤불 ───────────────────────────
# 교구의 창: 납 테 (불투명) 가 비스듬한 마름모로 유리를 나눈다. 유리는 반투명 (알파 GLASS_A), 아래쪽 칸에는 먼지가 앉았다.

GLASS_A = 150
GLASS = [  # L 납 테, g 유리, d 먼지 앉은 유리 (아래쪽), x 금 간 칸
    "LLLLLLLLLLLLLLLL",
    "LgggLgggggggLggL",
    "LggLgLgggggLgLgL",
    "LgLgggLgggLgggLL",
    "LLgggggLgLgggggL",
    "LgLgggggLgggggLL",
    "LggLgggLgLgggLgL",
    "LgggLgLgggLgLggL",
    "LggggLgggggLgggL",
    "LgggLgLgggLgLggL",
    "LggLgxxLgLgggLgL",
    "LgLgggggLgggggLL",
    "LLdggggLdLgggddL",
    "LdLdgdLddddLdLdL",
    "LddLdLddddddLdLL",
    "LLLLLLLLLLLLLLLL",
]


def _glass(lead, glass, dust, crack):
    t = Tex()
    g, _, _ = grid(GLASS)
    for y in range(16):
        for x in range(16):
            ch = g[y][x]
            if ch == "L":
                t[x, y] = lead if (x in (0, 15) or y in (0, 15)) else step(lead, 1 if (x + y) % 5 == 0 else 0)
            elif ch == "g":
                t[x, y] = (glass, GLASS_A)
            elif ch == "d":
                t[x, y] = (dust, GLASS_A)
            else:
                t[x, y] = (crack, GLASS_A)
    return t


def gray_stained_glass():
    return _glass("ash1", "ash2", "ash3", "ash3")


def brown_stained_glass():
    return _glass("ash0", "rust1", "rust2", "rust2")


def black_stained_glass():
    return _glass("ash1", "ash0", "rust0", "ash2")


def _pane_top(lead):
    # 판유리 윗면·옆면 (x 7..8 두 줄만 모형이 쓴다): 납 테
    t = Tex()
    for y in range(16):
        t[7, y] = step(lead, 1) if y % 5 == 2 else lead
        t[8, y] = step(lead, -1) if y % 7 == 4 else lead
    return t


def gray_stained_glass_pane_top():
    return _pane_top("ash1")


def brown_stained_glass_pane_top():
    return _pane_top("ash1")


def black_stained_glass_pane_top():
    return _pane_top("ash1")


def cobweb():
    # 먼지 앉은 거미줄: 위 세 곳에 걸린 날줄 (a) 사이로 씨줄 (b) 이 아래로 처졌다. 가운데 먼지 뭉치 (c), 한 줄은 끊겨 늘어졌다
    return paint([
        "a......a.......a",
        ".a.....a......a.",
        "..a....a.....a..",
        "..bbb..a...bba..",
        "...a.bbbbbb..a..",
        "....a..a...ab...",
        "....ab.a..b.a...",
        ".....abbbbba....",
        "......a.a.a.....",
        "......acccb.....",
        ".......bcb......",
        "........a.......",
        "........a.......",
        ".........a......",
        "................",
        "................",
    ], {"a": "ash3", "b": "bone0", "c": "bone1"})


def dead_bush():
    # 사당의 마른 덤불: 밑동에서 갈라진 굽은 가지, 끝은 바래 밝다 (c). 바탕 가지 b, 그늘 a
    return paint([
        "................",
        "...c.......c....",
        "...b......cb....",
        "....b....bb..c..",
        "....b...b...b...",
        ".c..ab..b..ba...",
        "..b..ba.b.ba....",
        "...b..baab.a..c.",
        "....b..bab..bb..",
        ".....aa.ba.ba...",
        ".......bbaa.....",
        "........ba......",
        ".......aba......",
        ".......aab......",
        "......aaba......",
        "......aaaa......",
    ], {"a": "rust1", "b": "rust2", "c": "parch0"})



# ═══════════════════════════ 묶기 ═══════════════════════════
# 비교판의 재료 묶음 (그림 이름 순서대로)
GROUPS = [
    ("deepslate", "심층암 (시험 방, 탑옥)", ["deepslate_tiles", "cracked_deepslate_tiles", "polished_deepslate",
                                         "deepslate_bricks", "cracked_deepslate_bricks", "cobbled_deepslate",
                                         "chiseled_deepslate"]),
    ("stone", "돌 (성벽, 사당, 교구)", ["stone_bricks", "cracked_stone_bricks", "mossy_stone_bricks", "cobblestone",
                                    "mossy_cobblestone", "andesite", "tuff", "tuff_bricks", "calcite",
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
    if not only:
        written.append(write_context(out_dir, scale=max(2, scale - 1)))
    return written


def _java_hash(x, y, z):
    """plugin/.../world/TestRoom.Builder.hash 와 같은 값 (32비트 정수 넘침까지)."""
    def i32(v):
        v &= 0xFFFFFFFF
        return v - (1 << 32) if v >= 1 << 31 else v
    h = i32(i32(x * 73856093) ^ i32(y * 19349663) ^ i32(z * 83492791) ^ 0x5f3759df)
    h = i32(h ^ ((h & 0xFFFFFFFF) >> 13))
    h = i32(h * 0x5bd1e995)
    h = i32(h ^ ((h & 0xFFFFFFFF) >> 15))
    return h & 0x7fffffff


def _room_floor(x, z):
    """TestRoom.floor 와 같은 섞음 (바닥 그림 이름)."""
    if 6 <= z <= 8 and -10 <= x <= 10:
        if x == -10 and z == 7:
            return "chiseled_deepslate"
        if z != 7 and (x + 10) % 2 == 0:
            return "deepslate_bricks"
        return "polished_deepslate"
    h = _java_hash(x, 0, z) % 100
    return ("deepslate_tiles" if h < 58 else "cracked_deepslate_tiles" if h < 74 else "polished_deepslate"
            if h < 90 else "cobbled_deepslate")


def _mix(table, x, y, salt):
    """위치 해시로 고른 그림 이름 (맛보기 벽). table: [(이름, 무게)]"""
    h = _java_hash(x, y, salt) % sum(w for _, w in table)
    for n, w in table:
        if h < w:
            return n
        h -= w
    return table[-1][0]


def write_context(out_dir, scale=3):
    """
    섞어 쓴 모습: 시험 방 바닥 (TestRoom.floor 의 해시 그대로, 구르기 길 포함) 과 벽 (심층암 벽돌 72 : 금 간 28),
    지역 팔레트 (DESIGN 8.4) 로 섞은 벽 넷. 이음매와 섞었을 때 튀는 그림을 본다.
    """
    texs = {n: _frame0(t.image()) for n, t in textures().items()}
    cell = 16 * scale

    def block(n):
        return texs[n].resize((cell, cell), Image.NEAREST)

    panels = []
    # 시험 방 바닥 (위에서 본 x -12..3, z 0..9)
    rows = [[_room_floor(x, z) for x in range(-12, 4)] for z in range(0, 10)]
    panels.append(("test room floor (TestRoom.floor hash, roll lane z=6..8)", rows))
    rows = [[_mix([("deepslate_bricks", 72), ("cracked_deepslate_bricks", 28)], x, y, 13) for x in range(16)]
            for y in range(4)]
    panels.append(("test room wall (deepslate_bricks 72 : cracked 28)", rows))
    rows = [[_mix([("stone_bricks", 55), ("cracked_stone_bricks", 25), ("mossy_stone_bricks", 20)], x, y, 1)
             for x in range(16)] for y in range(5)]
    rows.append(["cobblestone" if _java_hash(x, 9, 9) % 3 else "andesite" for x in range(16)])
    panels.append(("R1 Redin rampart (stone bricks / cracked / mossy, cobble & andesite footing)", rows))
    rows = [[_mix([("mossy_stone_bricks", 45), ("cracked_stone_bricks", 35), ("tuff", 20)], x, y, 2) for x in range(16)]
            for y in range(4)]
    rows.append(["light_gray_concrete_powder" if _java_hash(x, 3, 3) % 4 else "tuff" for x in range(16)])
    panels.append(("H Oda's shrine (mossy / cracked stone bricks, tuff, ash)", rows))
    rows = [["tuff_bricks"] * 16, ["tuff_bricks"] * 16, ["smooth_stone_slab_side"] * 16,
            [_mix([("calcite", 1), ("tuff_bricks", 2)], x, 3, 4) for x in range(16)], ["deepslate_tiles"] * 16]
    panels.append(("R2 Oswin parish (tuff bricks, smooth stone band, calcite, deepslate tile roof)", rows))
    rows = [[_mix([("spruce_planks", 3), ("dark_oak_planks", 1)], x, y, 5) if x % 5 else
             ("spruce_log" if x % 10 else "dark_oak_log") for x in range(16)] for y in range(3)]
    rows.append([_mix([("mud_bricks", 2), ("brown_terracotta", 1)], x, 3, 6) for x in range(16)])
    rows.append(["mossy_cobblestone" if _java_hash(x, 4, 7) % 2 else "hay_block_side" for x in range(16)])
    panels.append(("R1 barracks timber, mud brick with dried blood; P prison mossy cobble & rotten hay", rows))

    w = 16 * cell + 32
    h = sum(len(r) * cell + 26 for _, r in panels) + 16
    sheet = Image.new("RGBA", (w, h), (28, 27, 26, 255))
    d = ImageDraw.Draw(sheet)
    y = 8
    for title, rows in panels:
        d.text((16, y), title, fill=(209, 195, 160, 255))
        y += 18
        for r in rows:
            for x, n in enumerate(r):
                sheet.paste(block(n), (16 + x * cell, y))
            y += cell
        y += 8
    p = os.path.join(out_dir, "core_context.png")
    sheet.save(p)
    return p


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
