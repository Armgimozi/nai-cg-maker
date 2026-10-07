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


def masonry(rows, ramps, mortar, *, gap=".", mode="arris", modes=None, arris=None, tail=None):
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
                "lip"    판석·벽돌: 윗모서리 왼쪽 몇 칸 (arris) 과 왼쪽 열 바로 아래 한 칸만 빛, 아랫줄은 오른쪽 끝에서
                         tail={글자: 칸 수} 만큼만 그늘 (없으면 3), 오른쪽 열 그늘, 오른쪽 아래 귀 깊은 그늘.
                         3픽셀 켜의 벽돌도 얼굴이 납작하게 남는다 (아랫줄 전체를 그늘로 칠하면 2픽셀 띠처럼 보인다)
    빛은 왼쪽 위 하나다.
    """
    g, w, h = grid(rows)
    tail = tail or {}
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
            elif m == "lip":
                n_lit = arris.get(s, 2 + (ord(s) * 7) % 4)
                # 오른쪽으로 같은 돌이 몇 칸 더 있나 (아랫줄 그늘은 오른쪽 끝에서 tail 칸)
                to_right = 0
                while to_right < w and at(x + to_right + 1, y) == s:
                    to_right += 1
                if dn and rt:
                    k = 0
                elif rt and not up:
                    k = 1
                elif dn and to_right < tail.get(s, 3):
                    k = 1
                elif up and run.get((x % w, y), 99) < n_lit:
                    k = 3
                elif lf and not up and at(x, y - 2) != s:
                    k = 3
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

PALE = ["ash1", "ash2", "ash3", "stone2"]         # 바랜 회색 돌 (레딘 성벽). 가장 밝은 뼈빛 (bone1) 은 깨진 입술 몇 곳에만
WARM = ["ash1", "ash2", "bone0", "stone2"]        # 따뜻한 회색
OCHRE = ["rust1", "parch0", "parch1", "parch2"]   # 황토 돌 (Undead Burg)
SOOT = ["ash0", "ash1", "ash2", "ash3"]           # 그을린 돌
# 심층암 (탑옥, 시험 방): 블록 전용 점판암 계열 (채도 0.08~0.10 의 찬 회색). 1층 (blocks_grade) 이 옮긴 심층암 광석·계단의
# 바탕과 같은 계열이다. 벽 (벽돌) 은 바탕 slate2 (밝기 .29), 바닥 (타일·윤낸 판석) 은 한 단 밝은 slate3 (.36):
# 랜턴 빛 7 과 지역 안개 아래에서 턱 윗면과 바닥 모서리가 벽에서 갈린다. 아주 어두운 줄눈 (slate0) 은 세로 이음과 금에만
SLATE = ["slate0", "slate1", "slate2", "slate3"]            # 벽돌
SLATE_LT = ["slate1", "slate2", "slate3", "slate4"]         # 바닥, 볕을 더 받는 벽돌
SLATE_DK = ["slate0", "slate1", "slate1", "slate2"]         # 그을음이 앉은 벽돌 (한 장에 하나)

# ─────────────────────────── 심층암 (시험 방, 탑옥) ───────────────────────────
# 찬 묘실 돌. 레딘의 바랜 마름돌 (돌 계열) 과 색온도로 갈린다. 시험 방이 이 돌로 지어져 있어 가장 자주 보인다.

DSB_ROWS = [  # 심층암 벽돌: 3픽셀 켜 넷 + 1픽셀 줄눈, 벽돌 길이 5~9 (켜마다 다르다), 이음줄은 켜마다 다른 자리
    "AAAAAA.BBBBBBBB.",
    "AAAAAA.BBBBbBBB.",
    "AAAAAA.BBBBBBBB.",
    "................",
    "DDD.CCCCCCCC.DDD",
    "DDD.CCCCCCCC.DDD",
    "DDD.CCCCCCCC.DDD",
    "................",
    ".EEEEEEEEE.FFFFF",
    ".EEEEEEEEE.FfFFF",
    ".EEEEEEEEE.FFFFF",
    "................",
    "HHHHH.GGGGGGG.HH",
    "HHHHH.GGgGGGG.HH",
    "HHHhH.GGGGGGG.HH",
    "................",
]
DSB_RAMP = {"*": SLATE, "B": SLATE_LT, "D": SLATE_DK}
DSB_ARRIS = {"A": 3, "B": 5, "C": 2, "D": 2, "E": 6, "F": 3, "G": 4, "H": 2}
DSB_TAIL = {"A": 2, "B": 4, "C": 3, "D": 2, "E": 5, "F": 2, "G": 1, "H": 2}


def deepslate_bricks():
    # 가로 줄눈은 slate1 (벽돌 그늘과 같은 밝기), 세로 이음만 slate0. 벽돌 하나는 윗모서리가 이 빠졌고 (c), 하나는 귀가 닳았다
    t = masonry(DSB_ROWS, DSB_RAMP, ["slate1", "slate0"], mode="lip", arris=DSB_ARRIS, tail=DSB_TAIL)
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "                ",
        "        cc      ",
        "         c      ",
        "                ",
        "                ",
        "                ",
        "                ",
        "               c",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
    ], {"c": "slate1"})


def cracked_deepslate_bricks():
    t = deepslate_bricks()
    # 금은 위 켜에서 내려와 줄눈을 건너 세 켜를 지난다 (x 금, 금 아래 오른쪽 h 는 깨진 면이 받은 빛).
    # 아래 켜의 벽돌 하나는 왼쪽 귀가 떨어져 속이 보인다 (k 속, l 떨어진 자리 아랫가장자리의 빛)
    return overlay(t, [
        "          x     ",
        "          xh    ",
        "         x      ",
        "         x      ",
        "        xh      ",
        "        x       ",
        "       xh       ",
        "       x        ",
        "      x         ",
        "     xh         ",
        "                ",
        "                ",
        "      kk        ",
        "      kkk       ",
        "       ll       ",
        "                ",
    ], {"x": "slate0", "h": "slate3", "k": "slate0", "l": "slate3"})


DST_ROWS = [  # 심층암 타일 (바닥, 턱, 지붕): 세 켜 (4·4·5 픽셀), 켜마다 이음 자리가 다르고 가운데 켜의 D 는 두 칸 길이.
    # 소문자는 타일마다 다른 자리의 닳은 턱 (한 단 밝게)
    "AAA.BBBB.CCCC.AA",
    "AAA.BBBB.CcCC.AA",
    "AAA.BBBB.CCCC.AA",
    "AAA.BBBB.CCCC.AA",
    "................",
    "E.DDDDDDDDD.EEEE",
    "E.DDDDDDDDD.EEEE",
    "E.DDDDDDDDD.EEEE",
    "E.DdDDDDDDD.EEEE",
    "................",
    "FFFFF.GGGG.HHHH.",
    "FFFFF.GGGG.HHHH.",
    "FFFFF.GGGG.HHHH.",
    "FFFFF.GGGG.HHHH.",
    "FFFFF.GGGG.HHHH.",
    "................",
]
DST_ARRIS = {"A": 4, "B": 2, "C": 3, "D": 6, "E": 5, "F": 3, "G": 2, "H": 1}
DST_TAIL = {"A": 1, "B": 2, "C": 2, "D": 4, "E": 3, "F": 2, "G": 2, "H": 2}


def _tiles_base():
    return masonry(DST_ROWS, {"*": SLATE_LT}, ["slate1", "slate1"], mode="lip", arris=DST_ARRIS, tail=DST_TAIL)


def deepslate_tiles():
    # 타일마다 납작한 얼굴 (왼쪽 위 1픽셀 빛, 오른쪽 아래 그늘). 고르지 않게: B 는 내려앉아 윗모서리가 그늘 (s) 이고
    # 아랫모서리가 빛 (u), G 는 겉이 떨어져 나가 속 (p) 과 그 아랫입술 (u) 이 보인다. 귀 두 곳이 깨졌다 (c 줄눈 빛깔, k 깊은 곳)
    t = _tiles_base()
    return overlay(t, [
        "    ssss    c   ",
        "    -       c   ",
        "                ",
        "    uuu         ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "       pp       ",
        "      ppp       ",
        "       uu       ",
        "c               ",
        "ck              ",
        "                ",
    ], {"s": "slate2", "u": "slate4", "p": "slate2", "c": "slate1", "k": "slate0"})


def cracked_deepslate_tiles():
    t = _tiles_base()
    # 금 둘이 타일 이음을 건너 이어진다 (x 얼굴 위의 금, 줄눈 위에서는 o 더 깊다). 금 아래 오른쪽은 h (깨진 면의 빛).
    # 오른쪽 아래 타일은 한 귀가 떨어져 속이 보인다 (k)
    return overlay(t, [
        "                ",
        "   x            ",
        "   ox           ",
        "    xh          ",
        "     o          ",
        "      xx        ",
        "        xh      ",
        "         x      ",
        "         xh     ",
        "          o     ",
        "          o     ",
        "           x    ",
        "            xh  ",
        "             k  ",
        "            kk  ",
        "                ",
    ], {"x": "slate1", "o": "slate0", "h": "slate4", "k": "slate0"})


def polished_deepslate():
    # 판석 두 장 (위 큰 장, 아래 장은 이음이 x=4 로 엇갈린다). 이음은 오른쪽과 아랫줄에만 있어 이어 놓으면 1픽셀 줄이다.
    # 발에 닳은 자리 몇 군데가 한 단 밝다 (+, 크기와 자리가 다르게, 이어진 띠는 아니다), 긁힌 자국 둘 (-),
    # 아래 장 왼쪽 위 귀가 깨졌다 (c, k)
    rows = ["AAAAAAAAAAAAAAA."] * 9 + ["................"] + ["BBBB.BBBBBBBBBBB"] * 5 + ["................"]
    t = masonry(rows, {"*": SLATE_LT}, ["slate1", "slate1"], mode="lip", arris={"A": 7, "B": 5}, tail={"A": 6, "B": 4})
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "         ++     ",
        "  ++    +++     ",
        "   +            ",
        "            -   ",
        "             -  ",
        "                ",
        "                ",
        "     cc         ",
        "     k          ",
        "          ++    ",
        "  -        +    ",
        "   -            ",
        "                ",
    ], {"c": "slate1", "k": "slate0"})


def chiseled_deepslate():
    # 구르기 길의 시작 칸: 판석에 새긴 고리와 그 안의 칼 한 자루 (화톳불의 말린 칼).
    # 홈은 왼쪽 위 벽이 그늘 (x), 오른쪽 아래 벽이 빛 (h). 고리 오른쪽 위는 닳아 끊겼다
    rows = ["PPPPPPPPPPPPPPP."] * 15 + ["................"]
    t = masonry(rows, {"P": SLATE_LT}, ["slate1", "slate1"], mode="lip", arris={"P": 9}, tail={"P": 7})
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
    ], {"x": "slate1", "h": "slate4"})


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
CDS_RAMP = {"*": SLATE, "D": SLATE_DK, "B": SLATE_LT, "G": SLATE_LT}
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
    t = masonry(SB_ROWS, SB_RAMP, ["ash1", "ash1"], arris=SB_ARRIS)
    # 이 빠진 벽돌은 셋뿐 (자리·크기가 다르다): B 오른쪽 위 귀 (c 깊은 곳 한 칸, e 깨진 면, h 깨진 바닥이 받은 빛),
    # E 왼쪽 아래 귀, C 윗모서리의 얕은 홈 (s). 물때 (-: 윗줄눈에서 두세 칸 흘러내리다 끊긴다), 황토 얼룩 (o: 돌 아래쪽에 고인 흙물)
    return overlay(t, [
        "           ec   ",
        "        --  e   ",
        "         -  h   ",
        "         -      ",
        "                ",
        "                ",
        "    ss          ",
        "            --  ",
        "             -  ",
        "    oo          ",
        "                ",
        "  -       oo    ",
        "  --       o    ",
        "h  -            ",
        "cc              ",
        "                ",
    ], {"c": "ash1", "e": "ash2", "h": "bone1", "o": "parch0", "s": "ash2"})


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
    # 응회암: 차분한 두 색 바탕 (재 ash2, 넓은 얼룩 둘 stone0). 숨구멍 다섯 (x 2~3 픽셀 구멍, 바로 아래 l 은 구멍
    # 아랫입술이 받은 빛). 흩뿌린 점은 없다
    t = Tex(fill="ash2")
    return overlay(t, [
        "oooo        o oo",
        "ooooo   xx   ooo",
        "oooooo  ll    oo",
        "ooooo          o",
        " ooo            ",
        "  oo    x       ",
        "        x       ",
        "        l       ",
        "   x            ",
        "   xx           ",
        "    ll     ooo  ",
        "          ooooo ",
        "         oooo   ",
        "      xx   oo   ",
        "       l        ",
        "o              o",
    ], {"o": "stone0", "x": "ash1", "l": "stone1"})


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
    # 바랜 방해석 (교구): 차고 하얗게 바랜 뼈빛 (slate5 바탕, 평균 밝기 약 0.58, 채도 0.05 아래). 길고 고르지 않은 퇴적 결 둘
    # (v, 계단처럼 오르내리고 군데군데 끊긴다), 비에 씻겨 더 바랜 자리 (s, 하나뿐) 와 위에서 흘러내린 빗물 자국 (w, 길이가 다르다)
    t = Tex(fill="slate5")
    return overlay(t, [
        " w      w       ",
        " w      w    ss ",
        " w      w   ssss",
        "        w  sssss",
        "vvv        sssss",
        "   vv v     ssv ",
        "       vvv   vv ",
        "  w       v     ",
        "  w             ",
        "  w             ",
        "         w      ",
        "         w      ",
        "      vvv       ",
        "   w     vv v   ",
        "   w         v  ",
        " w w           v",
    ], {"w": "slate6", "s": "slate6", "v": "slate4"})


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
TUFF = ["ash0", "ash1", "ash2", "ash3"]        # 교구의 응회암 벽돌: 축축한 회색


def tuff_bricks():
    t = masonry(TB_ROWS, {"*": TUFF}, ["ash0", "ash1"], arris={"A": 5, "B": 2, "C": 4, "D": 2})
    # 젖은 아래쪽: 돌마다 아래 두세 줄에 물이 차오른 자국 (-, 높이가 고르지 않다). 이끼 (m) 는 줄눈 몇 마디에만 끼었다
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "                ",
        "            -   ",
        " --  ---   --   ",
        "                ",
        "  mm        m   ",
        "                ",
        "                ",
        "                ",
        "                ",
        "      --     -  ",
        "    --  ---     ",
        "                ",
        "        mmm     ",
    ], {"m": "moss0"})



def smooth_stone():
    # 매끄러운 판석 (교구): 옅은 베벨 (윗모서리 왼쪽만 빛, 아래·오른쪽 끝만 그늘). 윗모서리에서 흘러내린 넓은 물때 둘
    # (두 단: 바깥 s 한 단 어둡게, 속 S 두 단, 아래 끝은 가는 줄로 끊긴다), 머리카락 같은 금 하나 (x), 긁힘 셋 (k)
    rows = ["PPPPPPPPPPPPPPP."] * 15 + ["................"]
    t = masonry(rows, {"P": ["ash2", "stone1", "ash3", "stone2"]}, ["stone1", "stone1"], mode="lip", arris={"P": 10},
                tail={"P": 8})
    return overlay(t, [
        "ssSSSs    sSSs  ",
        " sSSSs    sSs   ",
        " sSSs     sSs   ",
        "  sSs      s    ",
        "  sSs      s    ",
        "  ss            ",
        "   s        x   ",
        "   s       x    ",
        "           x    ",
        "          x     ",
        "  kk     x      ",
        "          x     ",
        "                ",
        "     k      kk  ",
        "      k         ",
        "                ",
    ], {"x": "ash2", "k": "stone1", "s": "stone1", "S": "ash2"})


def smooth_stone_slab_side():
    # 반 블록 둘을 포갠 옆면: 판마다 옅은 베벨, 가운데 이음줄. 물때는 윗판에서 시작해 이음 아래 판까지 흘렀고, 귀 하나가 닳았다
    rows = ["PPPPPPPPPPPPPPP."] * 7 + ["................"] + ["QQQQQQQQQQQQQQQ."] * 7 + ["................"]
    t = masonry(rows, {"*": ["ash2", "stone1", "ash3", "stone2"]}, ["stone1", "stone1"], mode="lip",
                arris={"P": 9, "Q": 6}, tail={"P": 7, "Q": 9})
    return overlay(t, [
        "  sSSSs         ",
        "   sSSs         ",
        "   sSs       k  ",
        "    ss      k   ",
        "    s           ",
        "    s           ",
        "                ",
        "                ",
        "    s    sSs    ",
        "    s    sSs    ",
        "          s     ",
        "  kk      s     ",
        "                ",
        "                ",
        "c               ",
        "                ",
    ], {"k": "stone1", "c": "stone1", "s": "stone1", "S": "ash2"})



# ─────────────────────────── 나무 (레딘 성벽: 가문비·짙은 참나무, 사다리, 비계, 탑옥의 썩은 건초) ───────────────────────────
# 비바람에 바랜 목재. 가문비는 회갈색 (녹슨 철 계열에 은빛으로 바랜 결 ash2), 짙은 참나무는 그을린 청동처럼 검다.
# 판자는 켜마다 이음매 자리가 다르고, 이음매 옆에 못. 결은 길게 흐르다 끊긴다. 판자는 그림 글자로 직접 찍는다.


def spruce_planks():
    # 가문비 판자: 바탕 b, 결 a (어둡게) 와 c (밝게), 틈 g, 이음 d, 못 n
    return planks([10, 3, 13, 6], [
        (1, 1, 5, "a"), (12, 2, 4, "a"), (4, 2, 3, "c"), (8, 5, 6, "a"), (0, 6, 2, "a"), (14, 4, 3, "c"),
        (2, 9, 4, "a"), (8, 10, 3, "a"), (5, 8, 2, "c"), (9, 13, 5, "a"), (0, 14, 4, "a"), (11, 12, 2, "c"),
    ], {"b": "rust2", "a": "rust1", "c": "rust3", "g": "rust1", "d": "rust0", "n": "ash1"},
        [((-2, 1), (2, 2)), ((-2, 2), (2, 1)), ((-2, 1), (3, 1)), ((-3, 2), (2, 0))])


def dark_oak_planks():
    # 짙은 참나무 판자: 이음 자리와 결이 가문비와 다르다. 바탕 b, 결 a, 밝은 결 c, 틈 g, 이음 d, 녹슨 못 n
    return planks([5, 12, 1, 9], [
        (7, 1, 4, "a"), (0, 2, 3, "a"), (13, 1, 2, "c"), (2, 5, 5, "a"), (13, 6, 3, "a"), (6, 4, 2, "c"),
        (3, 9, 3, "a"), (10, 10, 5, "a"), (11, 8, 2, "c"), (0, 13, 6, "a"), (11, 14, 3, "a"), (4, 12, 2, "c"),
    ], {"b": "bronze0", "a": "rust0", "c": "rust1", "g": "rust0", "d": "ash0", "n": "rust2"},
        [((-2, 2), (2, 1)), ((-3, 1), (2, 1)), ((-2, 0), (2, 2)), ((-2, 1), (3, 2))])


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
    # 가문비 잘린 면: 고갱이가 왼쪽 아래로 비켰고, 나이테가 고르지 않게 휜다. 마른 틈 둘 (긴 것 하나, 짧은 것 하나),
    # 껍질 테는 아래·왼쪽이 두껍다
    return log_top((6.6, 9.2), [(0.10, 0.6), (0.07, 2.1), (0.05, 4.0)], 1.45,
                   [(-62, 1.2, 6.5), (160, 2.0, 4.6)],
                   ("1112111111211111", "1121111211111211", "2222122222221222", "2212222122222122"),
                   {"b": "rust0", "k": "rust1", "l": "rust3", "r": "rust2", "c": "rust1", "x": "rust0"})


def dark_oak_log_top():
    # 짙은 참나무 잘린 면: 고갱이가 오른쪽 위로 비켰고 껍질이 두껍다 (두 겹이 많다). 틈 하나가 고갱이에서 왼쪽 아래로
    return log_top((9.3, 6.4), [(0.12, 2.3), (0.06, 0.4), (0.04, 1.3)], 1.6,
                   [(128, 1.0, 7.5), (20, 2.5, 4.5)],
                   ("2222122222212222", "2212222221222222", "1222222122222221", "2222212222122222"),
                   {"b": "ash0", "k": "rust0", "l": "rust1", "r": "bronze0", "c": "ash0", "x": "ash0"})


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


def strokes(t, marks, ink, axis="v"):
    """
    손으로 놓은 짧은 결 (짚, 나뭇결). marks: (x, y, 길이, 글자) 목록, axis "v" 면 아래로, "h" 면 오른쪽으로 긋는다.
    가장자리를 넘으면 반대쪽으로 이어진다 (Tex 가 감는다). 글자는 ink[글자] 색.
    """
    for x, y, n, ch in marks:
        for i in range(n):
            if axis == "v":
                t[x, y + i] = ink[ch]
            else:
                t[x + i, y] = ink[ch]
    return t


def planks(joints, grain, ink, nails):
    """
    판자 넷 (4픽셀: 판 3줄 + 틈 1줄) 이 블록을 가로지른다. joints: 판마다 맞댄 이음의 x (판마다 다른 자리).
    grain: (x, y, 길이, 글자) 가로 나뭇결 (2~6 픽셀). 판의 윗줄은 이음 바로 오른쪽 몇 칸만 빛 (c), 틈 (g) 은 너무 검지 않게.
    nails: 판마다 맞댄 이음 양쪽의 못 둘 ((왼쪽 dx, 줄), (오른쪽 dx, 줄)). 이음에 붙이지 않고 한 칸 띄워, 판마다 줄을 달리 한다
    """
    t = Tex(fill=ink["b"])
    for i, jx in enumerate(joints):
        y0 = i * 4
        for x in range(16):
            t[x, y0 + 3] = ink["g"]
        for dy in range(3):
            t[jx, y0 + dy] = ink["d"]
        for k in range(1, 3 + (i * 3) % 4):
            t[jx + k, y0] = ink["c"]
    for x, y, n, ch in grain:
        for k in range(n):
            if t[x + k, y] == ink["b"]:
                t[x + k, y] = ink[ch]
    for i, jx in enumerate(joints):
        for dx, row in nails[i]:
            t[jx + dx, i * 4 + row] = ink["n"]
    return t


def _line(t, x0, y0, x1, y1, v):
    """1픽셀 곧은 금 (끝점 포함)."""
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(n + 1):
        t[round(x0 + (x1 - x0) * i / max(1, n)), round(y0 + (y1 - y0) * i / max(1, n))] = v


def log_top(pith, wobble, spacing, cracks, rim, ink):
    """
    잘린 통나무 면. pith: 고갱이 자리 (가운데에서 비켜 있다). 나이테는 고갱이에서의 거리에 각도마다 다른 들쭉날쭉
    (wobble: (배율, 위상) 목록) 을 곱해 spacing 픽셀마다 밝은 테 (l) 와 어두운 테 (r) 가 번갈아 온다.
    cracks: (각도°, 시작 거리, 끝 거리) 마른 틈 (x, 1픽셀). rim: 테두리 네 변 (위, 오른쪽, 아래, 왼쪽) 의 칸별 껍질 두께 문자열.
    """
    import math
    t = Tex()
    px, py = pith
    for y in range(16):
        for x in range(16):
            dx, dy = x + 0.5 - px, y + 0.5 - py
            a = math.atan2(dy, dx)
            f = 1.0 + sum(k * math.sin(n * a + ph) for n, (k, ph) in enumerate(wobble, start=2))
            r = math.hypot(dx, dy) * f
            band = int(r / spacing)
            t[x, y] = ink["c"] if r < 0.9 else (ink["r"] if band % 2 else ink["l"])
    for ang, r0, r1 in cracks:
        a = math.radians(ang)
        _line(t, int(px + math.cos(a) * r0), int(py + math.sin(a) * r0),
              int(px + math.cos(a) * r1), int(py + math.sin(a) * r1), ink["x"])
    top, right, bottom, left = rim
    for i in range(16):
        for d in range(int(top[i])):
            t[i, d] = ink["b"] if d == 0 else ink["k"]
        for d in range(int(bottom[i])):
            t[i, 15 - d] = ink["b"] if d == 0 else ink["k"]
        for d in range(int(left[i])):
            t[d, i] = ink["b"] if d == 0 else ink["k"]
        for d in range(int(right[i])):
            t[15 - d, i] = ink["b"] if d == 0 else ink["k"]
    return t


def hay_block_side():
    # 탑옥의 썩은 건초: 젖어 검게 바랜 짚단. 짚은 2~4 픽셀 세로 결 (밝은 짚 l, 바탕 a, 그늘 d) 을 손으로 놓았고,
    # 묶은 끈 두 줄 (t 끈의 윗면, r 끈, s 끈 아래 그늘). 밑의 세 줄은 젖어 한 단 어둡고 (썩음), 곰팡이 (m, n) 는 크기가 다른 두 자리
    t = Tex(fill="bronze1")
    ink = {"l": "bronze2", "d": "bronze0", "k": "parch0"}
    strokes(t, [
        (1, 0, 3, "l"), (5, 1, 2, "l"), (8, 0, 3, "l"), (12, 1, 2, "l"), (14, 13, 4, "l"), (2, 5, 4, "l"),
        (6, 6, 3, "l"), (9, 5, 2, "l"), (13, 7, 3, "l"), (4, 9, 2, "l"), (11, 8, 3, "l"), (0, 13, 3, "l"),
        (7, 13, 2, "l"), (15, 5, 3, "l"), (3, 0, 2, "d"), (10, 0, 3, "d"), (15, 1, 2, "d"), (0, 6, 3, "d"),
        (4, 5, 3, "d"), (8, 7, 3, "d"), (12, 5, 3, "d"), (14, 9, 2, "d"), (2, 9, 2, "d"), (6, 13, 3, "d"),
        (11, 13, 2, "d"), (7, 0, 2, "k"), (10, 6, 2, "k"),
    ], ink)
    # 젖은 아래쪽: 13~15 줄을 한 단 어둡게 (끝이 고르지 않다)
    for x in range(16):
        top = 13 if x % 5 not in (1, 2) else 14
        for y in range(top, 16):
            t[x, y] = step(t[x, y], -1) if t[x, y] != "bronze0" else "rust1"
    for y, row in ((3, "tttrtttttrtttttt"), (4, "rrrrrrrrrrrrrrrr"), (5, "ssssssssssssssss"),
                   (10, "ttttttrttttttttr"), (11, "rrrrrrrrrrrrrrrr"), (12, "ssssssssssssssss")):
        for x, ch in enumerate(row):
            if ch == "s":
                t[x, y] = "rust1" if t[x, y] == "bronze2" else "bronze0"
            else:
                t[x, y] = {"t": "parch0", "r": "rust1"}[ch]
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "         mm     ",
        "        mnnm    ",
        "         nm     ",
        "          m     ",
        "                ",
        "                ",
        "                ",
        "                ",
        "  mn            ",
        "   m            ",
    ], {"m": "moss1", "n": "moss0"})


def hay_block_top():
    # 짚단 윗면: 눕힌 짚의 2~4 픽셀 가로 결 (l 밝은 짚, d 그늘). 오른쪽 아래가 젖어 내려앉았고 (w 젖은 짚, 가장자리가
    # 고르지 않고 오른쪽 끝을 넘어 이어진다), 그 위쪽 가장자리에 곰팡이 (m, n) 가 길게 앉았다
    t = Tex(fill="bronze1")
    ink = {"l": "bronze2", "d": "bronze0", "k": "parch0"}
    strokes(t, [
        (0, 0, 3, "l"), (6, 0, 4, "d"), (12, 1, 3, "l"), (2, 2, 4, "d"), (9, 2, 2, "l"), (14, 3, 3, "d"),
        (4, 4, 3, "l"), (10, 4, 4, "d"), (0, 5, 2, "d"), (7, 6, 3, "l"), (13, 6, 2, "l"), (1, 7, 4, "l"),
        (9, 8, 2, "d"), (4, 9, 3, "d"), (14, 9, 3, "l"), (0, 11, 3, "d"), (6, 11, 2, "l"), (2, 13, 4, "l"),
        (8, 14, 3, "d"), (13, 15, 3, "l"), (11, 0, 2, "k"), (3, 10, 2, "k"),
    ], ink, axis="h")
    return overlay(t, [
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "                ",
        "            nmm ",
        "w        mmnwwww",
        "ww     wwwwwwwww",
        "www   wwwww wwww",
        "w       www  www",
        "             ww ",
        "                ",
        "                ",
    ], {"w": "rust1", "m": "moss1", "n": "moss0"})



# ─────────────────────────── 쇠와 구리 (탑옥 쇠창살, 사슬, 쇠문, 레버, 교구의 구리) ───────────────────────────
# 무딘 쇠: 재 계열 (빛 ash3, 바탕 ash2, 그늘 ash1), 녹은 녹슨 철 계열이 아래쪽으로 흘러내린다.


def iron_bars():
    # 벼린 네모 창살 셋. 바닐라와 같은 열 x=2..3, 7..8, 12..13 (기둥·옆 모형이 uv x 7..9 를 쓰고, 위아래 마구리가 그 열의
    # y 0..8 을 쓴다. 그래서 알파는 바닐라의 창살 열 그대로다). 창살: 왼쪽 열 빛 (c), 오른쪽 열 바탕 (b), 군데군데 그늘 (a).
    # 가로 띠쇠 하나 (2줄: 윗줄 빛, 아랫줄 그늘) 가 온 폭을 묶고, 창살과 만나는 곳에만 징 (o). 녹 (r, s) 은 띠쇠에서
    # 창살을 따라 길이가 다르게 흘러내리고, 밑동에도 조금 고였다
    return paint([
        "..cb...cb...cb..",
        "..cb...ca...cb..",
        "..cb...cb...cb..",
        "..cb...cb...ca..",
        "ccoccccoccccoccc",
        "aasaaaaaraaaaaaa",
        "..cr...cs...cb..",
        "..cs...cr...cb..",
        "..cb...cr...cb..",
        "..ca...cs...cb..",
        "..cb...cb...cb..",
        "..cb...cb...ca..",
        "..cb...cb...cb..",
        "..cb...ca...cb..",
        "..cb...cb...cr..",
        "..rs...cs...rs..",
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
    # 교구의 녹청 낀 구리판: 블록마다 짙은 청동 판 한 장 (b 바탕), 윗줄과 왼쪽 열 위쪽에 1픽셀 빛 (c),
    # 오른쪽 열과 아랫줄은 다음 판과의 이음 (a). 징 다섯 (o 머리, k 오른쪽 아래 그늘). 녹청은 구리와 다른 회녹 (w 짙은 녹청,
    # v 녹청, V 가장 옅은 회색 몇 칸): 징 아래와 아래 이음 위에 고이고 아래로 흘러내렸다. 이끼빛은 쓰지 않는다
    return paint([
        "ccccccccccccccca",
        "cokbbbbbbbbbbbka",
        "cwvbbbbbokbbbbva",
        "bwvbbbbbwvbbbbwa",
        "bbwbbbdbwvbbbbwa",
        "bbwbbbbbbwbbbbba",
        "bbbbbbbbbwbbdbba",
        "bbbdbbbbbbbbbbba",
        "bbbbbbbbbbbbbbba",
        "bokbbbbbbbbbokba",
        "bwVbbbbdbbbbwvba",
        "bwvwbbbbbbbbwvba",
        "bbwvbbbbbwbbbwba",
        "wbwvwbbbwvwbbwvw",
        "vwvVvwbwvVvwwvVv",
        "aaaaaaaaaaaaaaaa",
    ], {"a": "bronze0", "b": "bronze1", "c": "bronze2", "d": "bronze1", "o": "bronze3", "k": "bronze0",
        "w": "verd2", "v": "verd3", "V": "slate5"})


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
    # 불꽃: 끝은 어두운 녹빛 (1), 녹슨 주황 (2), 호박빛 (3), 속에만 옅은 금빛 두 칸 (4). 흰빛·살구빛은 쓰지 않는다
    flame = {"1": "ember0", "2": "ember1", "3": "ember2", "4": "ember3"}
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


# 모닥불 그림 (모형 template_campfire 가 쓰는 자리)
#   y0..3   통나무 옆면 (껍질). 켠 그림은 위 통나무들의 옆면
#   y4..7   x0..3 통나무 잘린 끝 (꺼진 그림). 켠 그림은 온 폭이 위 통나무의 아랫면 (불이 비춘다)
#   y8..13  화톳불 바닥 (윗면, 90° 돌려 깐다: 그림의 x 가 세상의 z). 위 통나무 둘 (z 1..5, 11..15) 사이 x 5..11 이 트여 보인다
#   y15     바닥 판의 북·남쪽 옆 가장자리 (x 0..5, 10..15)
CAMPFIRE_BARK = [   # 숯이 된 껍질: 위는 재가 앉아 밝고 (b), 거북등처럼 갈라진 틈 (x) 이 길이 방향으로 이어진다, 아랫줄 그늘 (d)
    "bbabbbbxbbbabbab",
    "aaaxaaaxaaaawxaa",
    "axxxwaaaxxxaaxxa",
    "dddddxdddddddxdd",
]
CAMPFIRE_END = ["ewwe", "wrxw", "wxrw", "ewwe"]   # 잘린 끝: 숯 테 (e), 덜 탄 나무 (w), 나이테 (r, x)
CAMPFIRE_UNDER = [  # 켠 모닥불의 위 통나무 아랫면: 숯 (a, d) 사이로 갈라진 틈 (x)
    "adaaxaaadaaxaada",
    "aaxxxaadaxxxaaaa",
    "daaaaxxaaaaaxxad",
    "ddaddaddaddaddad",
]
CAMPFIRE_BED = [    # 재 바닥: 고운 재 (g), 쌓인 재의 턱 (h), 뼛조각 (n, m), 숯 덩이 (k)
    "gghhgggggggghhgg",
    "ghgggkkgggggggng",
    "gggnggggggmggggg",
    "hgggggggggggkghg",
    "gggkgggngggggggg",
    "gmgggghhgggggnhg",
    "gggggggggggggggg",
    "kkgkkkgkkgkkgkkg",
]
CAMPFIRE_INK = {"a": "ash1", "d": "ash0", "b": "ash2", "w": "rust1", "x": "ash0", "e": "ash0", "r": "rust2",
                "g": "ash2", "h": "ash3", "n": "bone0", "m": "bone1", "k": "ash1"}


def _campfire_rows(lit):
    end = [r + "." * 12 for r in CAMPFIRE_END] if not lit else CAMPFIRE_UNDER
    return CAMPFIRE_BARK + end + CAMPFIRE_BED


def campfire_log():
    # 꺼진 화톳불: 숯이 된 통나무와 식은 재 바닥 (불빛이 없다)
    return paint(_campfire_rows(False), CAMPFIRE_INK)


# 켠 화톳불의 불씨 (바닐라와 같이 4 프레임, 섞어 넘긴다. 점이 옮겨 다니지 않고 같은 자리의 세기만 바뀐다).
#   통나무: 불씨는 껍질 틈 (x) 을 따라서만. 틈 칸마다 프레임별 세기 (0 숯, 1 어두운 불씨, 2 불씨)
#   바닥: 통나무 아래 한가운데의 달아오른 속 하나. 세 단 (바깥 ember0, 속 ember1, 한가운데 ember2), 가끔 옅은 금빛 한 칸
CAMPFIRE_CRACK_GLOW = {   # (x, y) → 프레임 넷의 세기
    (7, 0): "1210", (3, 1): "0121", (7, 1): "2121", (12, 1): "1011", (13, 1): "1121", (1, 2): "0110",
    (2, 2): "1221", (3, 2): "1112", (8, 2): "1012", (9, 2): "2121", (10, 2): "1210", (13, 2): "1101",
    (14, 2): "0121", (5, 3): "1011", (13, 3): "0110",
    (4, 4): "1211", (2, 5): "1111", (3, 5): "2122", (4, 5): "2212", (9, 5): "1210", (10, 5): "2121",
    (11, 5): "1221", (5, 6): "2112", (6, 6): "1221", (12, 6): "1112", (13, 6): "2121",
}
CAMPFIRE_CORE = [  # 바닥 y8..13 가운데. 프레임마다 (0 ember0, 1 ember1, 2 ember2, 3 ember3, ' ' 재 그대로)
    ["                ",
     "      000       ",
     "     01110      ",
     "     01210      ",
     "      0110      ",
     "       0        "],
    ["       0        ",
     "     00100      ",
     "    0112100     ",
     "    0123210     ",
     "     01110      ",
     "      000       "],
    ["                ",
     "       00       ",
     "      0110      ",
     "      0110      ",
     "       00       ",
     "                "],
    ["                ",
     "      000       ",
     "     01110      ",
     "     01221      ",
     "      0110      ",
     "      00        "],
]


def campfire_log_lit():
    out = Tex(16, 64)
    glow = {"0": "ember0", "1": "ember1", "2": "ember2", "3": "ember3"}
    for f in range(4):
        t = paint(_campfire_rows(True), CAMPFIRE_INK)
        for (x, y), seq in CAMPFIRE_CRACK_GLOW.items():
            t[x, y] = {"0": "ash0", "1": "ember0", "2": "ember1"}[seq[f]]
        for dy, row in enumerate(CAMPFIRE_CORE[f]):
            for x, ch in enumerate(row):
                if ch != " ":
                    t[x, 8 + dy] = glow[ch]
        out.paste(t, 0, f * 16)
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
    # 갈색 테라코타 = 마른 피가 스며 굳은 흙 (레딘 성벽의 핏자국 자리). 밤빛 갈색 딱지 (a 바탕, l 마른 윗가장자리, b 짙은
    # 밤빛), 더 검게 엉긴 덩이 셋 (k, 가장자리 몇 칸만 붉다 r), 위에서 흘러내린 자국 (위 가장자리의 k·b 세로 줄),
    # 말라 터진 금은 짙은 갈색 (x, 몇 줄뿐)
    return paint([
        "aakaaaaaaabkaaaa",
        "aakaaaaaaabkaaal",
        "abkaaxaaaaakaaaa",
        "aakaaaxaaaabaaaa",
        "aabaaaaxxaaaaaaa",
        "aaaaaaaaaxaakkaa",
        "aallaaaaaaakkkra",
        "aaaaaaaaaaakkkka",
        "aaaaaxaaaaaabkaa",
        "akkaaaxxaaaaaaaa",
        "kkkraaaaxaaalaaa",
        "kkkkaaaaaxaaaaab",
        "bkkaaaaaaaxaaaab",
        "aaaallaaaaaaaaab",
        "aaaaaaaaaaxxaaaa",
        "aaaaaaaaaaaaxaaa",
    ], {"a": "clay1", "b": "rose0", "k": "blood0", "r": "blood1", "x": "rust0", "l": "clay2"})


def light_gray_concrete_powder():
    # 사당의 재: 바람에 쌓인 고운 재. 굽은 둔덕 셋의 마루 (c, 1픽셀) 와 그 아래 바람그늘 (d, 한두 줄, 끝으로 갈수록 좁다),
    # 바탕 (a). 덜 탄 숯 조각 (k) 둘과 뼛조각 (n) 하나
    t = Tex(fill="ash3")
    for pts, lee in ((((0, 3), (3, 2), (8, 2), (11, 4)), ((1, 4), (3, 3), (8, 3), (10, 5), (4, 4), (7, 4))),
                     (((5, 8), (8, 7), (13, 7), (16, 9)), ((6, 9), (8, 8), (13, 8), (15, 9), (9, 9), (12, 9))),
                     (((-3, 13), (2, 12), (6, 13)), ((-2, 14), (2, 13), (5, 14), (0, 14)))):
        for a, b in zip(pts, pts[1:]):
            _line(t, a[0], a[1], b[0], b[1], "stone2")
        for a, b in zip(lee[:-2], lee[1:-2]):
            _line(t, a[0], a[1], b[0], b[1], "stone1")
        _line(t, lee[-2][0], lee[-2][1], lee[-1][0], lee[-1][1], "stone1")
    for x, y, v in ((12, 13, "ash1"), (13, 13, "ash1"), (3, 7, "ash1"), (14, 3, "bone1"), (15, 3, "bone0")):
        t[x, y] = v
    return t


NR_ROWS = [  # 불 받침 바위: 고르지 않은 그을린 덩어리 (크기·모양이 다르다). 덩어리 윗면에 재가 앉았다
    "AAAAABBBBBBBBCCA",
    "AAAABBBBBBBBCCCA",
    "DDAABBBBBBBCCCCA",
    "DDDDDBBBBEECCCCD",
    "DDDDDDDEEEEEECCD",
    "FDDDDDEEEEEEEEGG",
    "FFFDDEEEEEEEGGGG",
    "FFFFFFFEEEEGGGGG",
    "FFFFFFFFHHHGGGGF",
    "IFFFFFHHHHHHHGFF",
    "IIIFFHHHHHHHHHII",
    "IIIIJJJHHHHHIIII",
    "IIIJJJJJJHHIIIII",
    "AIJJJJJJJJJIIIIA",
    "AAAJJJJJJJAAAAAA",
    "AAAAAJJJJAAAAAAA",
]


def netherrack():
    # 꺼지지 않는 불의 받침: 그을린 덩어리 (바탕 ash1), 덩어리 윗면에 재 (ash2, + 는 더 쌓인 곳), 아랫면 그늘 (rust0),
    # 덩어리 사이 깊은 틈은 마른 핏빛 (blood0). 붉은 빛은 틈 몇 칸 (r) 뿐
    t = masonry(NR_ROWS, {"*": ["blood0", "rust0", "ash1", "ash2"]}, "ash0", mode="soft")
    return overlay(t, [
        "      +++       ",
        "                ",
        "  ++            ",
        "          ++    ",
        "                ",
        "              ++",
        "                ",
        "                ",
        "         ++     ",
        "                ",
        "                ",
        "    r           ",
        "                ",
        "           r    ",
        "                ",
        "                ",
    ], {"r": "blood1"})


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
    # 교구의 창: 납 테 (불투명) 가 마름모 둘씩으로 유리를 나눈다 (8픽셀 간격, 이어 놓으면 두 블록 사이에 1픽셀 납 테:
    # 테는 위와 왼쪽에만 있다). 유리는 반투명 (GLASS_A). 마름모 몇 개만 아래쪽에 먼지 (d), 한 칸은 금 (x). 납 테의 윗면
    # 몇 곳만 빛을 받는다 (g)
    t = Tex()
    dusty = {(4, 6), (5, 6), (3, 6), (12, 14), (11, 14), (13, 14), (12, 13), (4, 14), (5, 13)}
    cracked = {(10, 3), (11, 4), (11, 5)}
    shine = {(3, 5), (9, 0), (2, 0), (14, 6), (7, 9), (13, 3)}
    for y in range(16):
        for x in range(16):
            if x == 0 or y == 0 or (x + y) % 8 == 0 or (x - y) % 8 == 0:
                t[x, y] = step(lead, 1) if (x, y) in shine else lead
            elif (x, y) in cracked:
                t[x, y] = (crack, GLASS_A)
            elif (x, y) in dusty:
                t[x, y] = (dust, GLASS_A)
            else:
                t[x, y] = (glass, GLASS_A)
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
    # 먼지 앉은 거미줄: 왼쪽 위 귀에 걸려 위 가장자리와 왼쪽 가장자리에 매였다 (좌우 대칭이 아니다). 날줄 넷 (a) 이 귀에서
    # 퍼지고, 씨줄 (b) 은 두 바퀴만 날줄 사이에 처졌는데 바깥 바퀴는 한 마디가 끊겼다. 끊긴 줄 하나가 아래로 늘어졌고,
    # 귀 가까이에 먼지 뭉치 (c)
    t = Tex()
    hub = (1, 1)
    for end in ((15, 0), (14, 7), (8, 13), (0, 15)):
        _line(t, hub[0], hub[1], end[0], end[1], "ash3")
    for pts in (((6, 1), (6, 3), (5, 5), (3, 6), (1, 6)),
                ((11, 1), (11, 4), (11, 6)),
                ((8, 10), (5, 11), (1, 11))):
        for a, b in zip(pts, pts[1:]):
            _line(t, a[0], a[1], b[0], b[1], "bone0")
    _line(t, 11, 6, 12, 13, "ash3")      # 끊겨 늘어진 줄
    for x, y in ((2, 2), (3, 2), (2, 3)):
        t[x, y] = "bone1"
    return t


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
