#!/usr/bin/env python3
"""
블록 1층: 바닐라 블록 그림 전부의 색을 다크소울 쪽으로 옮긴다 (사용자 결정 2026-10-08, DESIGN 10.6·10.7).

  python3 pack/blocks_grade.py [팩 폴더]     그림만 쓴다 (gen_pack 은 build(OUT), blocks_core.build(OUT), finish(OUT) 차례로 부른다)
  python3 pack/blocks_grade.py --sheets     전후 비교판 (dist/screenshots/blocks/grade_*.png): 재료 갈래마다 바닐라 | 새 것 (4배,
                                            물드는 그림은 물들여서), 3×3 깔기, 색 지도, 제자리 (바탕 3×3 가운데에 광석 등, 최종 팩)

바닐라 그림은 사람이 16×16 에 한 점씩 찍은 것이라 꼴은 그대로 둔다. 바꾸는 것은 색뿐이다.
  - 그림의 색 하나하나 (바닐라 블록은 한 장에 4~10색) 를 색상으로 묶고 (회색, 빨강, 주황, 노랑·갈색, 초록, 청록, 파랑,
    보라, 자홍, 분홍), 재료 (RULES) 가 묶음마다 정한 팔레트 계단 (LADDERS) 의 한 칸으로 옮긴다.
  - 계단의 칸은 밝기로 고른다. 밝기는 재료마다 정한 곧은 식 (기준 밝기 → 목표 밝기, 대비) 으로 먼저 옮긴다.
    같은 재료의 그림 (돌벽돌과 금 간 돌벽돌, 광석의 돌 바탕과 돌) 은 같은 색이 늘 같은 색으로 가서 벽에 섞어 써도 이어진다.
  - 그래서 새 색은 팔레트 계단에만 있고 (부드러운 그라데이션·잡음이 생기지 않는다), 바닐라의 점 배치가 남는다.
  - 광석은 바탕 돌 (돌, 심층암, 네더랙) 과 다른 점만 광석 계단으로 옮긴다. 바탕은 바탕 돌 그림과 픽셀까지 같다.
  - 빛을 내는 블록 (palette.BLOCK_GLOW) 은 밝고 따뜻한 점만 불씨 계단으로 옮긴다 (횃불·랜턴·불·용암이 따뜻하게 읽힌다).
  - 바이옴 색으로 물드는 그림 (풀, 잎, 덩굴, 물) 은 회색 세 칸으로 두고 (가장 어두운 칸을 올려 검은 구멍이 없다) 색은
    바이옴이 낸다. 지역 바이옴 9개 (데이터팩 souls:*) 는 저마다 풀빛·잎빛·마른 잎빛을 effects 에 적었다 (사당 재 묻은
    올리브, 성벽 마른 황토 올리브, 교구 축축한 회녹 …). 색 지도 (colormap/grass·foliage·dry_foliage) 는 그 밖의 바이옴과
    아이템 그림만 쓴다. 가문비·자작 잎은 바닐라가 정한 초록으로 물드므로 바랜 장미색으로 그려 마른 올리브가 되게 한다.
  - 물은 데이터팩의 물 색을 9 지역 모두 옅은 무채색 (#c6c4bc) 으로 두고 탁한 회녹을 그림이 낸다 (WATER_TINT).
    교구의 어두운 물빛 (DESIGN 8.4 #22292a) 은 물속 안개 (water_fog_color) 다.
  - 애니메이션 띠와 .mcmeta (장면 순서, 밉맵 방식) 는 바닐라 그대로 옮긴다. 알파도 그대로다.

blocks_core.py (2층) 가 이 뒤에 맵의 핵심 블록을 손 규칙으로 새로 그려 덮는다. 그 뒤 finish() 가 바닐라에서 바탕 그림을
그대로 깔았던 그림 (광석, 풀·포드졸·균사체 블록 옆면, 진홍·뒤틀린 나일리움 옆면, 작업대 옆면 …, DERIVED) 의 바탕 픽셀을 팩의
최종 바탕 그림 (2층이 새로 그렸으면 그것) 의 같은 자리 픽셀로 맞춘다. 광석이 둘레 돌과 이어진다.
돌 갈래의 밝기와 쇠·녹청 구리의 결은 2층이 새로 그린 성벽 돌·쇠창살·녹슨 구리에 맞췄다 (castle, iron, patina 계단).
바닐라 그림은 클라이언트 jar 에서 읽는다 (SOULS_CLIENT_JAR, 없으면 ~/.cache/souls-client/versions/1.21.11.jar).
jar 가 없으면 블록을 옮기지 않은 팩이 나오므로 멈춘다.
"""
import io
import os
import re
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import palette  # noqa: E402

ROOT = os.path.dirname(HERE)
JAR_BLOCK = "assets/minecraft/textures/block/"
JAR_COLORMAP = "assets/minecraft/textures/colormap/"
OUT_BLOCK = ("assets", "minecraft", "textures", "block")
OUT_COLORMAP = ("assets", "minecraft", "textures", "colormap")
SHEETS = os.path.join(ROOT, "dist", "screenshots", "blocks")

GREY_CHROMA = 0.06      # 이보다 채도가 낮으면 회색 묶음


def client_jar():
    """바닐라 클라이언트 jar. SOULS_CLIENT_JAR, 없으면 점검 틀이 받아 둔 곳. 없으면 None."""
    for p in (os.environ.get("SOULS_CLIENT_JAR"), os.path.expanduser("~/.cache/souls-client/versions/1.21.11.jar")):
        if p and os.path.exists(p):
            return p
    return None


# ─────────────────────────── 계단 ───────────────────────────
# 어두움 → 밝음은 자동으로 정렬한다. 적은 순서는 '먼저 고를 색': 밝기가 0.025 안으로 겹치면 앞의 것만 남긴다.
LADDERS = {
    "stone":  ["ash0", "ash1", "stone0", "ash2", "stone1", "ash3", "stone2", "stone3", "bone2", "bone3"],
    "pale":   ["ash1", "ash2", "stone1", "bone0", "stone2", "bone1", "stone3", "bone2", "bone3"],
    "soot":   ["ash0", "ash1", "stone0", "ash2", "stone1"],
    "slate":  ["slate0", "slate1", "slate2", "slate3", "slate4", "slate5", "slate6"],
    "iron":   ["ash0", "ash1", "stone0", "ash2", "stone1", "ash3", "stone2"],
    # 성벽 돌: 밝은 면은 바랜 뼈빛, 줄눈은 재 (blocks_core 의 돌벽돌과 같은 결)
    "castle": ["ash0", "ash1", "stone0", "ash2", "bone0", "bone1", "stone3", "bone2"],
    # 녹청: 구리와 다른 회녹 (녹청 계열만. 이끼빛은 쓰지 않는다). 녹이 오를수록 이 계단의 몫이 커진다
    "patina": ["slate0", "verd0", "verd1", "verd2", "verd3", "verd4"],
    # 구리 (녹슬기 전): 탁한 녹빛 청동 (살구빛이 아니다)
    "copper": ["ash0", "rust0", "rust1", "rust2", "rust3", "parch1", "parch2"],
    # 참나무 계열 (작업대·책장·독서대·통·벌통의 바탕): 비바람에 바랜 회황토. 금빛 청동은 쓰지 않는다
    "oak":    ["rust0", "rust1", "rust2", "parch0", "rust3", "parch1", "parch2"],
    "spruce": ["ash0", "rust0", "rust1", "rust2", "rust3", "parch1"],
    "darkwood": ["ash0", "rust0", "bronze0", "rust1", "bronze1", "rust2"],
    "earth":  ["ash0", "rust0", "rust1", "rust2", "rust3"],
    "ochre":  ["bronze0", "bronze1", "parch0", "parch1", "parch2", "parch3", "bone3"],
    "gold":   ["bronze0", "bronze1", "bronze2", "bronze3", "parch2", "parch3", "bone3"],
    "clay":   ["clay0", "clay1", "clay2", "clay3", "clay4", "parch2"],
    "rose":   ["rose0", "rose1", "rose2", "rose3", "rose4", "bone2"],
    "blood":  ["blood0", "blood1", "blood2", "blood3", "rose2", "rose3"],
    "moss":   ["ash0", "moss0", "moss1", "moss2", "olive3", "olive4"],
    "olive":  ["ash0", "olive0", "olive1", "olive2", "olive3", "olive4", "parch3"],
    "verd":   ["slate0", "verd0", "verd1", "verd2", "verd3", "verd4", "bone3"],
    "diamond": ["verd2", "verd3", "verd4", "slate6", "bone3"],
    "woadonly": ["woad0", "woad1", "woad2", "woad3"],
    "mauvebone": ["mauve2", "mauve3", "mauve4", "mauve5", "bone1", "bone2"],
    # 꽃잎 넷 (FLOWERS): 뼈, 마른 황토, 엷은 자주, 시든 붉음. 가장 밝은 칸을 막아 모두 흰빛으로 모이지 않게
    "fl_bone": ["ash2", "stone1", "bone0", "bone1", "bone2"],
    "fl_ochre": ["rust1", "bronze1", "parch0", "bronze2", "parch1"],
    "fl_mauve": ["mauve1", "mauve2", "mauve3", "mauve4", "mauve5"],
    "fl_red": ["rose0", "rose1", "rose2", "rose3"],
    "blue":   ["slate0", "woad0", "woad1", "woad2", "woad3", "slate4", "slate5", "slate6"],
    "frost":  ["slate2", "slate3", "slate4", "slate5", "slate6", "bone3"],
    "mauve":  ["mauve0", "mauve1", "mauve2", "mauve3", "mauve4", "mauve5", "bone2"],
    "rust":   ["ash0", "rust0", "rust1", "rust2", "rust3", "parch1"],
    "nether": ["blood0", "blood1", "rose1", "rose2"],
    # 빛 (BLOCK_GLOW 그림에서만 쓴다)
    "ember":  ["blood0", "blood1", "ember0", "ember1", "ember2", "ember3", "bone3"],
    "lava":   ["blood0", "blood1", "ember0", "ember1", "ember2", "ember3"],
    "redglow": ["blood0", "blood1", "blood2", "blood3", "ember1", "ember2"],
    "ghost":  ["slate0", "verd0", "verd1", "verd2", "verd3", "verd4", "bone2", "bone3"],
    # 물든 그림: 물 (바닐라 기본 물 색으로 물들면 탁한 회청록), 가문비·자작 잎 (바닐라가 정한 초록으로 물들면 마른 올리브)
    # 물: 데이터팩 바이옴의 물 색을 옅은 무채색 (WATER_TINT) 으로 두고, 탁한 회녹은 그림이 낸다
    "water":  ["verd1", "slate2", "verd2", "slate3", "verd3", "slate4"],
    "tintrose": ["rose0", "rose1", "rose2", "rose3", "rose4", "bone2"],
}
LADDER_LUMA = {}


def _ladders():
    for k, names in LADDERS.items():
        keep = []
        for n in names:
            lu = palette.luma(palette.c(n))
            if all(abs(lu - l2) >= 0.025 for _, l2 in keep):
                keep.append((n, lu))
        LADDER_LUMA[k] = sorted(keep, key=lambda t: t[1])


_ladders()


# ─────────────────────────── 색상 묶음 ───────────────────────────

def bucket(rgb):
    """바닐라 색 하나 → 색상 묶음 이름."""
    if palette.chroma(rgb) < GREY_CHROMA:
        return "grey"
    h = palette.hue(rgb)
    if h >= 345 or h < 10:
        return "red"
    if h < 24:
        return "orange"
    if h < 66:
        return "yellow"
    if h < 160:
        return "green"
    if h < 200:
        return "cyan"
    if h < 255:
        return "blue"
    if h < 290:
        return "purple"
    if h < 325:
        return "magenta"
    return "pink"


def hot(rgb, kind):
    """빛 그림에서 빛나는 점인가. warm: 밝고 따뜻한 색 또는 하얗게 단 점, cyan: 밝은 청록 (영혼 불), red: 밝은 빨강."""
    lu, ch, h = palette.luma(rgb), palette.chroma(rgb), palette.hue(rgb)
    if kind == "warm":
        return (lu >= 0.42 and ch >= 0.18 and (h < 70 or h >= 345)) or (ch < 0.12 and lu >= 0.86)
    if kind == "cyan":
        return (lu >= 0.40 and ch >= 0.15 and 150 <= h < 215) or (ch < 0.12 and lu >= 0.86)
    if kind == "red":
        return lu >= 0.18 and ch >= 0.30 and (h < 25 or h >= 340)
    return False


GEN = {"grey": "stone", "red": "blood", "orange": "clay", "yellow": "oak", "green": "moss", "cyan": "verd",
       "blue": "blue", "purple": "mauve", "magenta": "mauve", "pink": "rose"}


class Recipe:
    """
    재료 하나의 색 옮기기.
      lad   계단 이름 하나 (모든 묶음) 또는 {묶음: 계단} (빠진 묶음은 GEN, '*' 는 빠진 묶음 모두)
      to    목표 밝기. mid 의 밝기가 to 로 간다
      mid   기준 밝기. None 이면 그림마다의 평균 (물들인 블록처럼 한 장으로 쓰는 것). 숫자면 같은 재료가 늘 같은 색으로 간다
      gain  대비 (기준을 가운데로 밝기 차이를 몇 배로)
      to_of None 이 아니면 (a, b): mid 가 그림 평균일 때 목표 밝기 = a + b × 평균
      hot   빛 그림: (계단, 종류, to, gain) 빛나는 점만 따로 옮긴다
      steps 한 장에 쓰는 팔레트 색의 수 한도 (잎·풀·이끼는 3, 콘크리트·양털·테라코타는 2). 밝기가 가까운 색끼리 합친다
      floor 가장 어두운 칸의 밝기 하한 (잎의 검은 구멍을 막는다)
    """
    __slots__ = ("lad", "to", "mid", "gain", "to_of", "hot", "label", "steps", "floor")

    def __init__(self, lad, to=None, mid=0.5, gain=1.0, to_of=None, hot=None, label=None, steps=None, floor=None):
        self.lad, self.to, self.mid, self.gain, self.to_of, self.hot, self.label = lad, to, mid, gain, to_of, hot, label
        self.steps, self.floor = steps, floor   # 쓰는 계단 수의 한도, 가장 어두운 칸의 밝기 하한 (limit_steps)
        if to is None and to_of is None:
            self.to_of = (0.03, 0.88)

    def ladder(self, b):
        if isinstance(self.lad, str):
            return self.lad
        if b in self.lad:
            return self.lad[b]
        if "*" in self.lad:
            return self.lad["*"]
        return GEN[b]


def R(lad, to=None, mid=0.5, gain=1.0, **kw):
    return Recipe(lad, to=to, mid=mid, gain=gain, **kw)


def per(lad, a=0.03, b=0.88, gain=1.1, **kw):
    """그림마다 평균을 기준으로 (한 장으로 쓰는 블록: 물들인 것, 꽃, 장치)."""
    return Recipe(lad, mid=None, gain=gain, to_of=(a, b), **kw)


def mix(**over):
    d = dict(GEN)
    d.update(over)
    return d


# ─────────────────────────── 재료 ───────────────────────────

DYES = ("white", "light_gray", "gray", "black", "brown", "red", "orange", "yellow", "lime", "green", "cyan",
        "light_blue", "blue", "purple", "magenta", "pink")
# 물감 → (계단, 밝기 a, b). 밝기는 그림 평균에서 a + b × 평균
DYE = {
    "white": ("pale", 0.06, 0.86), "light_gray": ("stone", 0.04, 0.86), "gray": ("stone", 0.03, 0.86),
    "black": ("soot", 0.02, 0.9), "brown": ("rust", 0.04, 0.9), "red": ("rose", 0.02, 0.7),
    "orange": ("rust", 0.04, 0.82), "yellow": ("ochre", 0.03, 0.75), "lime": ("olive", 0.03, 0.82),
    "green": ("moss", 0.03, 0.9), "cyan": ("verd", 0.04, 0.88), "light_blue": ("frost", 0.04, 0.82),
    "blue": ("blue", 0.02, 0.9), "purple": ("mauve", 0.0, 0.8), "magenta": ("mauve", 0.06, 0.86),
    "pink": ("mauvebone", 0.05, 0.84),
}
# 물들인 재료 → (대비, 밝기를 더 낮추는 양)
DYED_MAT = {"wool": (1.15, 0.0), "concrete": (1.0, 0.02), "concrete_powder": (1.05, 0.02), "terracotta": (1.1, 0.03),
            "glazed_terracotta": (1.05, 0.03), "stained_glass": (1.0, 0.0), "stained_glass_pane_top": (1.0, 0.0),
            "candle": (1.1, 0.0), "candle_lit": (1.1, 0.0), "shulker_box": (1.05, 0.02)}

WOOD = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "pale_oak", "bamboo",
        "crimson", "warped")
# 나무는 그림마다 평균을 기준으로 (통나무 껍질은 판자보다 어둡다). 밝기 = a + b × 평균
WOOD_RECIPE = {
    "oak": per(mix(grey="iron", yellow="oak", orange="oak", red="oak"), 0.0, 0.66, gain=1.1),
    "spruce": per(mix(grey="iron", yellow="spruce", orange="spruce", red="spruce"), 0.04, 0.82, gain=1.15),
    "birch": per(mix(grey="pale", yellow="pale", orange="pale", green="olive"), 0.04, 0.72, gain=1.0),
    "jungle": per(mix(grey="iron", yellow="clay", orange="clay", red="clay"), 0.0, 0.82, gain=1.1),
    "acacia": per(mix(grey="stone", yellow="rust", orange="rust", red="rust"), 0.02, 0.8, gain=1.1),
    "dark_oak": per(mix(grey="soot", yellow="darkwood", orange="darkwood", red="darkwood"), 0.05, 0.85, gain=1.15),
    "mangrove": per(mix(grey="stone", red="rose", orange="rose", yellow="rose", magenta="rose", pink="rose"),
                    0.02, 0.9, gain=1.1),
    "cherry": per(mix(grey="pale", red="mauve", orange="mauve", pink="mauve", yellow="mauve", magenta="mauve",
                      purple="mauve"), 0.03, 0.8, gain=1.05),
    "pale_oak": per(mix(grey="pale", yellow="pale", orange="pale", green="olive"), 0.05, 0.84, gain=1.05),
    "bamboo": per(mix(grey="stone", yellow="ochre", orange="ochre", green="olive"), 0.02, 0.82, gain=1.05),
    "crimson": per(mix(grey="soot", red="blood", orange="blood", pink="rose", magenta="mauve", purple="mauve",
                       yellow="clay"), 0.02, 0.85, gain=1.1),
    "warped": per(mix(grey="slate", cyan="verd", green="verd", blue="verd", purple="mauve", magenta="mauve",
                      orange="clay", yellow="clay"), 0.02, 0.85, gain=1.1),
}

# 돌 갈래의 밝기는 blocks_core 가 새로 그린 성벽 돌 (돌벽돌 평균 밝기 0.37, 안산암 0.45, 심층암 벽 0.29·바닥 0.36) 에 맞춘다
STONE = R(mix(grey="stone", green="moss", yellow="oak"), to=0.41, mid=0.49, gain=1.3, label="stone")
STONE_BRICKS = R(mix(grey="castle", green="moss", yellow="oak"), to=0.4, mid=0.48, gain=1.45, label="stone_bricks")
COBBLE = R(mix(grey="castle", green="moss", yellow="oak"), to=0.37, mid=0.50, gain=1.0, label="cobble")
DEEPSLATE = R(mix(grey="slate", yellow="rust", orange="rust"), to=0.29, mid=0.32, gain=1.0, label="deepslate")
NETHERRACK = R(mix(red="nether", orange="nether", pink="nether", magenta="nether", grey="soot", yellow="clay"),
               to=0.15, mid=0.22, gain=1.0, label="netherrack")
TINT = R("stone", to=0.50, mid=0.58, gain=0.7, label="tint", steps=3, floor=0.36)
TINT_LEAVES = R("stone", to=0.46, mid=0.55, gain=0.8, label="tint", steps=3, floor=0.34)
GLOWHOT = ("ember", "warm", 0.55, 1.2)

# 광석: 이름 → (바탕, 광석 점의 재료)
ORE_BASE = {"": ("stone", STONE), "deepslate_": ("deepslate", DEEPSLATE)}
ORE = {
    "coal": R(mix(grey="soot", yellow="soot", orange="soot"), to=0.13, mid=0.2, gain=1.0),
    "iron": R(mix(grey="stone", orange="rose", yellow="rose", red="rose", pink="rose"), to=0.55, mid=0.62, gain=1.2),
    "copper": R(mix(grey="stone", orange="clay", yellow="clay", red="clay", green="verd", cyan="verd"),
                to=0.43, mid=0.5, gain=1.25),
    "gold": R(mix(grey="stone", yellow="gold", orange="gold", red="gold"), to=0.52, mid=0.62, gain=1.25),
    # 광석은 바탕 돌보다 밝기 0.12 넘게 다르거나 색이 또렷이 달라야 읽힌다 (청금석은 쪽빛만, 에메랄드는 이끼가 아닌 녹청,
    # 다이아몬드는 옅은 녹청·흰빛)
    "redstone": R(mix(grey="blood", red="blood", orange="blood", pink="blood"), to=0.3, mid=0.35, gain=1.5),
    "lapis": R("woadonly", to=0.28, mid=0.38, gain=1.25),
    "diamond": R(mix(grey="diamond", cyan="diamond", green="diamond", blue="diamond"), to=0.62, mid=0.6, gain=1.2),
    "emerald": R(mix(grey="verd", green="verd", cyan="verd", yellow="verd"), to=0.4, mid=0.5, gain=1.3),
    "nether_gold": R(mix(yellow="gold", orange="gold", red="blood", grey="soot"), to=0.58, mid=0.62, gain=1.25),
    "nether_quartz": R(mix(grey="pale", yellow="pale", orange="pale", red="blood"), to=0.68, mid=0.78, gain=1.1),
}


def _dyed(name):
    for d in sorted(DYES, key=len, reverse=True):
        if name.startswith(d + "_"):
            mat = name[len(d) + 1:]
            if mat in DYED_MAT:
                return d, mat
    return None


def _wood(name):
    n = name[len("stripped_"):] if name.startswith("stripped_") else name
    for sp in sorted(WOOD, key=len, reverse=True):
        if n.startswith(sp + "_"):
            part = n[len(sp) + 1:]
            if re.fullmatch(r"planks|log|log_top|stem|stem_top|door_bottom|door_top|trapdoor|shelf|fence|fence_gate|"
                            r"fence_particle|fence_gate_particle|mosaic|block|block_top", part):
                return sp
    return None


# 이름 규칙 (위에서부터 처음 맞는 것). (정규식, 묶음, 재료). 묶음은 비교판을 나누는 재료 갈래
RULES = [
    # 액체
    (r"water_(still|flow|overlay)", "liquid", R("water", to=0.4, mid=0.69, gain=1.1, label="water")),
    (r"lava_(still|flow)", "liquid", R("lava", to=0.55, mid=0.68, gain=1.35, label="lava")),
    # 빛
    (r"torch|copper_torch", "light", R(mix(grey="iron", yellow="oak", orange="oak", red="oak", green="verd"),
                                         to=0.40, mid=0.45, gain=1.1, hot=GLOWHOT)),
    (r"redstone_torch(_off)?", "light", R(mix(grey="iron", yellow="oak", orange="oak", red="blood"),
                                            to=0.40, mid=0.45, gain=1.1, hot=("redglow", "red", 0.3, 1.2))),
    (r"soul_(torch|lantern|fire_[01]|campfire_fire|campfire_log_lit)", "light",
     R(mix(grey="iron", yellow="oak", orange="oak", cyan="ghost", blue="ghost"), to=0.36, mid=0.45, gain=1.15,
       hot=("ghost", "cyan", 0.5, 1.2))),
    (r"fire_[01]|campfire_fire", "light", R("ember", to=0.55, mid=0.65, gain=1.35)),
    (r"lantern", "light", R(mix(grey="iron", blue="iron", yellow="oak", orange="oak"), to=0.27, mid=0.33, gain=1.15,
                            hot=GLOWHOT)),
    (r"campfire_log(_lit)?", "light", R(mix(grey="stone", yellow="spruce", orange="spruce", red="spruce"),
                                          to=0.28, mid=0.33, gain=1.25, hot=GLOWHOT)),
    (r"magma", "light", R("lava", to=0.28, mid=0.4, gain=1.3)),
    (r"glowstone", "light", R(mix(yellow="oak", orange="oak", red="oak", grey="stone"), to=0.4, mid=0.55, gain=0.9,
                              hot=("ember", "warm", 0.56, 0.75))),
    (r"shroomlight", "light", R(mix(yellow="clay", orange="clay", red="clay"), to=0.42, mid=0.55, gain=1.2,
                                hot=("ember", "warm", 0.55, 1.1))),
    (r"jack_o_lantern", "light", R(mix(yellow="clay", orange="clay", red="clay", green="olive", grey="stone"),
                                   to=0.36, mid=0.45, gain=1.15, hot=("ember", "warm", 0.6, 1.1))),
    (r"redstone_lamp_on", "light", per(mix(grey="stone", yellow="oak", orange="clay", red="blood"), 0.0, 0.8,
                                       hot=("ember", "warm", 0.55, 1.15))),
    (r"(furnace|smoker|blast_furnace)_front_on", "light", per(mix(grey="stone", yellow="oak", orange="clay"),
                                                              0.02, 0.86, hot=("ember", "warm", 0.55, 1.15))),
    (r"ochre_froglight_(side|top)", "light", R("ochre", to=0.44, mid=0.75, gain=1.2)),
    # 개구리불 셋은 색으로 갈린다: 황토 (ochre), 뼈 (verdant), 엷은 자주빛 뼈 (pearlescent)
    (r"verdant_froglight_(side|top)", "light", R("pale", to=0.6, mid=0.72, gain=1.15)),
    (r"pearlescent_froglight_(side|top)", "light", R("mauvebone", to=0.5, mid=0.75, gain=1.2)),
    (r"sea_lantern", "light", R(mix(grey="pale", cyan="verd", green="verd", blue="verd"), to=0.58, mid=0.7, gain=1.2)),
    (r"end_rod", "light", R(mix(grey="pale", yellow="pale", purple="mauve", magenta="mauve"), to=0.6, mid=0.7,
                            gain=1.15)),
    (r"beacon", "light", R(mix(grey="pale", cyan="verd", green="verd", blue="verd"), to=0.58, mid=0.72, gain=1.15)),
    (r"conduit", "light", per(mix(cyan="verd", blue="verd", yellow="oak", orange="oak", grey="stone"))),
    (r"respawn_anchor_(top|top_off|bottom|side[0-4])", "nether",
     R(mix(grey="soot", purple="mauve", blue="mauve", magenta="mauve", pink="mauve", cyan="mauve", red="blood",
           orange="clay", yellow="oak"), to=0.2, mid=0.2, gain=1.3)),
    (r"crying_obsidian|obsidian", "nether", R(mix(grey="soot", purple="mauve", blue="mauve", magenta="mauve",
                                                  pink="mauve", cyan="mauve"), to=0.13, mid=0.1, gain=1.5)),
    (r"nether_portal", "nether", R("mauve", to=0.36, mid=0.4, gain=1.3)),
    (r"glow_lichen", "light", R(mix(grey="stone", cyan="verd", green="olive", yellow="olive"), to=0.5, mid=0.6,
                                gain=1.15)),
    (r"cave_vines(_plant)?(_lit)?", "plant", R(mix(green="olive", yellow="olive", grey="stone"), to=0.36, mid=0.42,
                                                gain=1.2, hot=("ember", "warm", 0.55, 1.15))),
    (r"firefly_bush_emissive", "light", R("ember", to=0.62, mid=0.7, gain=1.0)),
    (r"open_eyeblossom_emissive", "light", R("ember", to=0.6, mid=0.7, gain=1.0)),
    (r"lightning_rod_on", "metal", R("pale", to=0.75, mid=0.85, gain=1.1)),
    # 물들인 블록과 초 (켠 초는 빛 그림)
    (r"terracotta", "dyed", R(mix(grey="clay", red="clay", orange="clay", yellow="clay", pink="clay"),
                              to=0.33, mid=0.4, gain=1.15)),
    (r"candle(_lit)?", "dyed", per(mix(grey="pale", yellow="ochre", orange="ochre", red="blood"), 0.05, 0.86,
                                    hot=GLOWHOT)),
    (r"shulker_box", "dyed", per("mauve", 0.03, 0.86)),
    # 광석과 원석 블록
    (r"(deepslate_)?(coal|iron|copper|gold|redstone|lapis|diamond|emerald)_ore", "ore", "ORE"),
    (r"nether_(gold|quartz)_ore", "ore", "ORE"),
    (r"ancient_debris_(side|top)", "ore", R(mix(grey="soot", yellow="rust", orange="rust", red="rust",
                                                purple="mauve", magenta="mauve", pink="rose"), to=0.25, mid=0.3,
                                            gain=1.3)),
    (r"gilded_blackstone", "ore", R(mix(grey="soot", yellow="gold", orange="gold", red="gold", purple="soot",
                                        magenta="soot"), to=0.17, mid=0.18, gain=1.3)),
    # 돌·벽돌·심층암
    (r"stone", "stone", STONE),
    (r"(chiseled_|cracked_|mossy_)?stone_bricks", "stone", STONE_BRICKS),
    (r"(mossy_)?cobblestone", "stone", COBBLE),
    (r"smooth_stone(_slab_side)?", "stone", R(mix(grey="stone"), to=0.47, mid=0.62, gain=1.35)),
    (r"(polished_)?andesite", "stone", R(mix(grey="stone"), to=0.45, mid=0.53, gain=0.95)),
    (r"(polished_)?diorite", "stone", R(mix(grey="pale"), to=0.66, mid=0.75, gain=1.0)),
    (r"(polished_)?granite", "stone", R(mix(grey="pale", red="rose", orange="rose", yellow="rose", pink="rose",
                                            magenta="rose"), to=0.45, mid=0.5, gain=1.2)),
    (r"(polished_|chiseled_)?tuff(_bricks)?(_top)?|chiseled_tuff(_bricks)?(_top)?", "stone",
     R(mix(grey="stone", green="olive", yellow="olive"), to=0.32, mid=0.42, gain=1.1)),
    (r"calcite", "stone", R(mix(grey="pale"), to=0.7, mid=0.85, gain=1.1)),
    (r"(pointed_dripstone_.*|dripstone_block)", "stone", R(mix(grey="stone", yellow="rust", orange="rust",
                                                               red="rust"), to=0.36, mid=0.45, gain=1.05)),
    (r"(cobbled_|polished_|chiseled_|cracked_)?deepslate(_bricks|_tiles|_top)?|cracked_deepslate_(bricks|tiles)",
     "stone", DEEPSLATE),
    (r"reinforced_deepslate_(bottom|side|top)", "stone", R(mix(grey="slate", cyan="verd", green="verd"),
                                                           to=0.26, mid=0.3, gain=1.3)),
    (r"(polished_|chiseled_polished_|cracked_polished_)?blackstone(_top|_bricks)?|"
     r"polished_blackstone_bricks|cracked_polished_blackstone_bricks", "stone",
     R(mix(grey="soot", purple="soot", magenta="soot", blue="soot", pink="soot"), to=0.17, mid=0.18, gain=1.35)),
    (r"(polished_)?basalt_(side|top)|smooth_basalt", "stone", R(mix(grey="slate"), to=0.28, mid=0.33, gain=1.3)),
    (r"bricks", "stone", R(mix(grey="stone", red="clay", orange="clay", yellow="clay", pink="clay"),
                           to=0.34, mid=0.4, gain=1.25)),
    (r"mud_bricks|packed_mud", "stone", R(mix(grey="stone", orange="oak", yellow="oak", red="oak"),
                                          to=0.38, mid=0.47, gain=1.25)),
    (r"(cut_|chiseled_)?sandstone(_top|_bottom)?", "stone", R(mix(grey="pale", yellow="ochre", orange="ochre"),
                                                              to=0.6, mid=0.78, gain=1.15)),
    (r"(cut_|chiseled_)?red_sandstone(_top|_bottom)?", "stone", R(mix(grey="stone", yellow="clay", orange="clay",
                                                                      red="clay"), to=0.42, mid=0.5, gain=1.3)),
    (r"(dark_)?prismarine(_bricks)?", "stone", R(mix(grey="slate", cyan="verd", green="verd", blue="verd",
                                                     purple="mauve"), to=0.38, mid=0.45, gain=1.25)),
    (r"quartz_(block_bottom|block_side|block_top|bricks|pillar|pillar_top)|chiseled_quartz_block(_top)?", "stone",
     R(mix(grey="pale", yellow="pale", orange="pale"), to=0.7, mid=0.88, gain=1.15)),
    (r"(cracked_|chiseled_)?nether_bricks", "nether", R(mix(grey="soot", red="blood", orange="blood", pink="blood",
                                                            magenta="blood", purple="mauve"),
                                                        to=0.14, mid=0.15, gain=1.1)),
    (r"red_nether_bricks", "nether", R(mix(grey="soot", red="blood", orange="blood", pink="blood", magenta="blood"),
                                       to=0.18, mid=0.2, gain=1.1)),
    (r"resin_(block|bricks|clump)|chiseled_resin_bricks", "stone", R(mix(orange="clay", yellow="clay", red="clay",
                                                                         grey="stone"), to=0.38, mid=0.5, gain=1.2)),
    (r"bedrock", "stone", R(mix(grey="stone"), to=0.3, mid=0.4, gain=1.15)),
    (r"bone_block_(side|top)", "stone", R(mix(grey="pale", yellow="pale", orange="pale"), to=0.64, mid=0.8, gain=1.1)),
    (r"amethyst_block|budding_amethyst|(small|medium|large)_amethyst_bud|amethyst_cluster", "stone",
     R(mix(grey="pale", purple="mauve", magenta="mauve", blue="mauve", pink="mauve"), to=0.42, mid=0.55, gain=1.25)),
    # 쇠·구리·광물 블록
    # 쇠: 바랜 회색 쇠에 녹 (blocks_core 의 쇠창살·쇠문과 같은 밝기, 0.3~0.4). 한 장마다 평균 기준
    (r"iron_(bars|door_bottom|door_top|trapdoor|chain|block)|chain|heavy_core|(chipped_|damaged_)?anvil(_top)?|"
     r"cauldron_(bottom|inner|side|top)|hopper_(inside|outside|top)", "metal",
     per(mix(grey="iron", blue="iron", yellow="rust", orange="rust", red="rust"), 0.18, 0.28, gain=1.35)),
    (r"(raw_)?gold_block|bell_(bottom|side|top)", "metal", R(mix(grey="gold", yellow="gold", orange="gold",
                                                                  red="gold"), to=0.47, mid=0.7, gain=1.3)),
    (r"raw_iron_block", "metal", R(mix(grey="stone", yellow="rose", orange="rose", red="rose", pink="rose"),
                                   to=0.48, mid=0.6, gain=1.2)),
    # 구리가 녹스는 차례 (DESIGN 10.6): 탁한 녹빛 청동 → 청동에 회녹 얼룩 → 거의 회녹 → 옅은 회녹. 이끼빛은 쓰지 않는다
    (r"(raw_copper_block|copper_block|cut_copper|chiseled_copper|copper_(bars|bulb|bulb_powered|chain|door_bottom|"
     r"door_top|grate|trapdoor)|lightning_rod)", "metal",
     R(mix(grey="stone", orange="copper", yellow="copper", red="copper", pink="copper", green="patina", cyan="patina"),
       to=0.36, mid=0.5, gain=1.2)),
    (r"exposed_.*", "metal", R(mix(grey="copper", orange="copper", yellow="copper", red="copper", pink="copper",
                                   green="patina", cyan="patina", purple="copper", magenta="copper"), to=0.36, mid=0.5,
                               gain=1.2, hot=GLOWHOT)),
    (r"weathered_.*", "metal", R(mix(grey="patina", orange="copper", yellow="copper", red="copper", green="patina",
                                     cyan="patina", blue="patina", pink="copper"), to=0.37, mid=0.5, gain=1.2,
                                 hot=GLOWHOT)),
    (r"oxidized_.*", "metal", R(mix(grey="patina", orange="patina", yellow="patina", red="patina", green="patina",
                                    cyan="patina", blue="patina"), to=0.47, mid=0.52, gain=1.15, hot=GLOWHOT)),
    (r"copper_.*", "metal", R(mix(grey="stone", orange="copper", yellow="copper", red="copper", pink="copper",
                                  green="patina", cyan="patina"), to=0.36, mid=0.5, gain=1.2, hot=GLOWHOT)),
    (r"netherite_block", "metal", R(mix(grey="soot", purple="soot", magenta="soot", red="soot"), to=0.2, mid=0.25,
                                    gain=1.3)),
    (r"diamond_block", "metal", R(mix(grey="verd", cyan="verd", blue="verd", green="verd"), to=0.56, mid=0.75,
                                  gain=1.2)),
    (r"emerald_block", "metal", R(mix(grey="moss", green="moss", cyan="moss"), to=0.4, mid=0.55, gain=1.2)),
    (r"lapis_block", "metal", R(mix(grey="blue", blue="blue", purple="blue", cyan="blue"), to=0.25, mid=0.33,
                                gain=1.2)),
    (r"redstone_block", "metal", R(mix(grey="blood", red="blood", orange="blood", pink="blood"), to=0.22, mid=0.3,
                                   gain=1.2)),
    (r"coal_block", "metal", R(mix(grey="soot"), to=0.12, mid=0.12, gain=1.3)),
    # 유리와 얼음
    (r"glass|glass_pane_top", "glass", R(mix(grey="frost"), to=0.62, mid=0.75, gain=1.2)),
    (r"tinted_glass", "glass", R("mauve", to=0.2, mid=0.2, gain=1.2)),
    (r"(packed_|blue_)?ice|frosted_ice_[0-3]", "glass", R(mix(grey="frost", blue="frost", cyan="frost", purple="frost"),
                                                          to=0.52, mid=0.62, gain=1.25)),
    # 흙·모래·자갈·눈
    (r"dirt|coarse_dirt|rooted_dirt|farmland(_moist)?|dirt_path_(side|top)|grass_block_side|podzol_side",
     "soil", R(mix(grey="stone", orange="earth", yellow="earth", red="earth", green="olive"), to=0.33, mid=0.41,
               gain=0.85)),
    (r"grass_block_snow", "soil", R(mix(grey="pale", orange="earth", yellow="earth", red="earth"), to=0.33, mid=0.41,
                                    gain=0.85)),
    (r"podzol_top", "soil", R(mix(grey="stone", orange="earth", yellow="oak", red="earth", green="olive"),
                              to=0.28, mid=0.35, gain=1.25)),
    (r"mycelium_(side|top)", "soil", R(mix(grey="mauve", purple="mauve", magenta="mauve", blue="mauve", pink="mauve",
                                           orange="earth", yellow="earth", red="earth"), to=0.3, mid=0.41, gain=1.2)),
    (r"mud", "soil", R(mix(grey="soot", orange="earth", yellow="earth", red="earth", blue="soot", purple="soot"),
                       to=0.2, mid=0.23, gain=1.3)),
    (r"(suspicious_)?gravel(_[0-3])?", "soil", R(mix(grey="stone", red="rose", orange="rust", yellow="rust",
                                                     pink="rose"), to=0.4, mid=0.5, gain=1.05)),
    (r"(suspicious_)?sand(_[0-3])?", "soil", R(mix(grey="pale", yellow="ochre", orange="ochre"), to=0.58, mid=0.81,
                                               gain=0.45, steps=2)),
    (r"red_sand", "soil", R(mix(grey="stone", orange="clay", yellow="clay", red="clay"), to=0.42, mid=0.55,
                            gain=1.3)),
    (r"clay", "soil", R(mix(grey="slate", blue="slate", purple="slate"), to=0.5, mid=0.62, gain=1.3)),
    (r"(powder_)?snow", "soil", R(mix(grey="pale", blue="frost", cyan="frost", purple="frost"), to=0.76, mid=0.95,
                                  gain=2.2)),
    (r"soul_(sand|soil)", "nether", R(mix(grey="soot", orange="earth", yellow="earth", red="earth"),
                                      to=0.22, mid=0.3, gain=1.25)),
    # 네더
    (r"netherrack", "nether", NETHERRACK),
    (r"crimson_nylium(_side)?", "nether", NETHERRACK),
    (r"warped_nylium(_side)?", "nether", R(mix(red="blood", orange="blood", pink="blood", magenta="blood",
                                               grey="soot", yellow="clay", cyan="verd", green="verd", blue="verd"),
                                           to=0.16, mid=0.22, gain=1.35)),
    (r"nether_wart_block|nether_wart_stage[0-2]|crimson_(fungus|roots|roots_pot)|weeping_vines(_plant)?", "nether",
     R(mix(red="blood", orange="blood", pink="blood", magenta="blood", yellow="clay", grey="soot", green="olive",
           purple="mauve"), to=0.24, mid=0.3, gain=1.3)),
    (r"warped_wart_block|warped_(fungus|roots|roots_pot)|nether_sprouts|twisting_vines(_plant)?", "nether",
     R(mix(cyan="verd", green="verd", blue="verd", grey="slate", orange="clay", yellow="clay", red="blood"),
       to=0.32, mid=0.4, gain=1.3)),
    (r"lodestone_(side|top)", "device", per(mix(grey="stone"))),
    # 엔드
    (r"end_stone(_bricks)?", "end", R(mix(grey="pale", yellow="ochre", orange="ochre", green="ochre"), to=0.6,
                                      mid=0.84, gain=1.15)),
    (r"purpur_(block|pillar|pillar_top)", "end", R(mix(grey="mauve", purple="mauve", magenta="mauve", pink="mauve",
                                                       blue="mauve"), to=0.42, mid=0.6, gain=1.25)),
    (r"chorus_(flower|flower_dead|plant)", "end", R(mix(grey="mauve", purple="mauve", magenta="mauve", pink="mauve",
                                                        blue="mauve", yellow="ochre"), to=0.38, mid=0.5, gain=1.2)),
    (r"end_portal_frame_(eye|side|top)", "end", R(mix(grey="pale", yellow="ochre", orange="ochre", green="verd",
                                                      cyan="verd", blue="verd"), to=0.55, mid=0.7, gain=1.3)),
    (r"dragon_egg", "end", R(mix(grey="soot", purple="mauve", magenta="mauve", blue="mauve"), to=0.12, mid=0.12,
                             gain=1.5)),
    # 바이옴 색으로 물드는 그림
    (r"grass_block_top|grass_block_side_overlay|short_grass|tall_grass_(top|bottom)|fern|large_fern_(top|bottom)|"
     r"bush|sugar_cane", "plant", TINT),
    (r"(oak|jungle|acacia|dark_oak|mangrove)_leaves|vine|lily_pad", "plant", TINT_LEAVES),
    (r"leaf_litter", "plant", R("stone", to=0.55, mid=0.67, gain=1.3)),
    (r"(spruce|birch)_leaves", "plant", R("tintrose", to=0.47, mid=0.5, gain=1.1, steps=3, floor=0.3)),
    (r"(attached_)?(melon|pumpkin)_stem|pink_petals_stem|wildflowers_stem", "plant", R("stone", to=0.5, mid=0.6,
                                                                                       gain=1.2)),
    (r"redstone_dust_(dot|line0|line1|overlay)", "device", R("stone", to=0.6, mid=0.94, gain=1.0)),
    # 식물 (물들지 않는 것)
    (r"moss_(block|carpet)", "plant", R(mix(grey="moss", green="moss", yellow="olive", cyan="moss"), to=0.32,
                                        mid=0.42, gain=0.9, steps=3, floor=0.26)),
    (r"pale_moss_(block|carpet|carpet_side_small|carpet_side_tall)|pale_hanging_moss(_tip)?", "plant",
     R(mix(grey="stone", green="olive", yellow="olive", cyan="stone"), to=0.48, mid=0.58, gain=1.2)),
    (r"pale_oak_leaves", "plant", R(mix(grey="stone", green="olive", yellow="olive", cyan="olive"), to=0.42,
                                    mid=0.5, gain=1.1, steps=3, floor=0.3)),
    (r"cherry_leaves", "plant", R(mix(pink="mauve", magenta="mauve", red="mauve", orange="mauve", yellow="mauve",
                                      purple="mauve", grey="pale"), to=0.46, mid=0.65, gain=1.1, steps=3, floor=0.3)),
    (r"(flowering_)?azalea_(leaves|top|side|plant)|potted_(flowering_)?azalea_bush_(plant|side|top)", "plant",
     R(mix(green="moss", yellow="olive", cyan="moss", grey="stone", pink="rose", magenta="rose", purple="mauve",
           orange="earth", red="rose"), to=0.33, mid=0.42, gain=1.25)),
    (r"dead_bush", "plant", R(mix(yellow="spruce", orange="spruce", red="spruce", grey="stone"), to=0.32, mid=0.4,
                              gain=1.2)),
    (r"(short|tall)_dry_grass", "plant", R(mix(yellow="ochre", orange="ochre", green="olive", grey="stone"),
                                           to=0.5, mid=0.65, gain=1.2)),
    (r"hay_block_(side|top)", "plant", R(mix(yellow="oak", orange="oak", red="oak", green="olive", grey="stone"),
                                         to=0.4, mid=0.55, gain=1.2)),
    (r"(dead_)?(tube|brain|bubble|fire|horn)_coral(_block|_fan)?", "plant", "CORAL"),
    (r"(carved_pumpkin|pumpkin_(side|top))", "plant", R(mix(yellow="clay", orange="clay", red="clay", green="olive",
                                                            grey="stone"), to=0.37, mid=0.48, gain=1.15)),
    (r"melon_(side|top)", "plant", R(mix(green="moss", yellow="olive", cyan="moss", grey="stone"), to=0.32, mid=0.42,
                                     gain=1.2)),
    (r"cactus_(bottom|side|top)|cactus_flower", "plant", R(mix(green="moss", yellow="olive", cyan="moss",
                                                               grey="stone", pink="rose", magenta="rose", red="rose"),
                                                           to=0.3, mid=0.38, gain=1.25)),
    (r"(kelp|kelp_plant|seagrass|tall_seagrass_(top|bottom)|sea_pickle)", "plant",
     R(mix(green="olive", yellow="olive", cyan="olive", grey="stone"), to=0.3, mid=0.42, gain=1.2)),
    (r"dried_kelp_(bottom|side|top)", "plant", R(mix(grey="soot", green="olive", yellow="olive", cyan="olive"),
                                                 to=0.2, mid=0.25, gain=1.3)),
    (r"(red|brown)_mushroom(_block)?|mushroom_(stem|block_inside)", "plant",
     per(mix(grey="pale", red="blood", orange="earth", yellow="oak", pink="rose"), 0.02, 0.85)),
    (r"(mangrove_roots|muddy_mangrove_roots)_(side|top)|hanging_roots", "plant",
     R(mix(grey="stone", orange="earth", yellow="earth", red="rose", pink="rose", magenta="rose"), to=0.3, mid=0.38,
       gain=1.2)),
    (r"wither_rose", "plant", per(mix(grey="soot", green="soot", yellow="soot", red="soot"), 0.0, 0.85)),
    (r"frogspawn", "plant", per(mix(grey="stone", cyan="verd", blue="verd", green="olive"))),
    # 장치·작업대·기타 (한 장씩 평균 기준, 묶음마다 일반 계단)
    (r"(chiseled_)?bookshelf.*", "device", per(mix(grey="stone", yellow="oak", orange="clay"), 0.02, 0.84)),
    (r"spawner", "device", per(mix(grey="iron", blue="iron", cyan="iron"), 0.0, 0.85, gain=1.2)),
    (r"sculk.*|calibrated_sculk_sensor_(input_side|top)", "device",
     R(mix(grey="slate", blue="slate", cyan="verd", green="verd", purple="mauve", yellow="ochre", orange="clay"),
       to=0.2, mid=0.22, gain=1.4)),
    (r"cobweb", "device", R(mix(grey="pale"), to=0.68, mid=0.85, gain=1.1)),
    (r"slime_block", "device", R(mix(green="olive", yellow="olive", cyan="olive", grey="stone"), to=0.45, mid=0.6,
                                 gain=1.2)),
    (r"honey_block_(bottom|side|top)|honeycomb_block", "device", R(mix(yellow="gold", orange="gold", red="clay",
                                                                       grey="stone"), to=0.48, mid=0.6, gain=1.2)),
    (r"(wet_)?sponge", "device", R(mix(yellow="ochre", orange="ochre", green="olive", grey="stone"), to=0.52,
                                   mid=0.65, gain=1.2)),
    (r"destroy_stage_[0-9]", "device", R("stone", to=0.5, mid=0.5, gain=1.0)),
]
CORAL = {"tube": "slate", "brain": "rose", "bubble": "mauve", "fire": "rose", "horn": "ochre"}

DEVICE = per(mix(grey="stone", yellow="oak", orange="clay"), 0.02, 0.86, gain=1.1)
DEVICE_GLOW = per(mix(grey="stone", yellow="oak", orange="clay"), 0.02, 0.86, gain=1.1, hot=GLOWHOT)
PLANT = per(mix(grey="pale", green="olive", yellow="gold", orange="clay", red="blood", cyan="verd", blue="blue",
                purple="mauve", magenta="mauve", pink="rose"), 0.03, 0.86, gain=1.15)
# 꽃잎: 넷의 바랜 갈래로 나눈다 (모두 뼈빛 흰색으로 모이지 않게). 줄기·잎은 마른 풀빛
FLOWERS = {
    "bone": ("oxeye_daisy", "lily_of_the_valley", "white_tulip", "azure_bluet"),
    "ochre": ("dandelion", "sunflower", "wildflowers", "golden_dandelion"),
    "mauve": ("allium", "lilac", "pink_tulip", "peony", "blue_orchid", "cornflower", "pink_petals", "closed_eyeblossom",
              "open_eyeblossom"),
    "withered": ("poppy", "red_tulip", "rose_bush", "orange_tulip", "torchflower"),
}
FLOWER_LADDER = {"bone": ("fl_bone", 0.5), "ochre": ("fl_ochre", 0.42), "mauve": ("fl_mauve", 0.38),
                 "withered": ("fl_red", 0.33)}


def flower_recipe(name):
    for fam, keys in FLOWERS.items():
        if any(name.startswith(k) or name.startswith("potted_" + k) for k in keys):
            lad, to = FLOWER_LADDER[fam]
            petals = {b: lad for b in ("grey", "red", "orange", "yellow", "cyan", "blue", "purple", "magenta", "pink")}
            # 그림마다 평균 밝기 기준: 평균이 0.5 인 꽃이 목표 밝기 to 로 간다
            return per(mix(green="olive", **petals), to - 0.25, 0.5, gain=1.1)
    return None


# 꽃·작물·묘목으로 보이는 이름 (규칙에 없으면 PLANT)
PLANT_NAMES = re.compile(
    r".*(sapling|tulip|orchid|allium|azure_bluet|dandelion|poppy|cornflower|oxeye|lily_of_the_valley|lilac|peony|"
    r"rose_bush|sunflower|torchflower|eyeblossom|pink_petals|wildflowers|spore_blossom|dripleaf|bamboo_(stage0|stalk|"
    r"large_leaves|small_leaves|singleleaf)|wheat_stage|carrots_stage|potatoes_stage|beetroots_stage|cocoa_stage|"
    r"sweet_berry_bush|pitcher_crop|mangrove_propagule|firefly_bush|crimson_roots|warped_roots|flower_pot).*")

_COMPILED = [(re.compile(rx), cls, rec) for rx, cls, rec in RULES]
TRANSLUCENT = re.compile(r"glass|ice|water_|nether_portal|respawn_anchor_top|slime_block|honey_block|tripwire|"
                         r"frogspawn|destroy_stage_")


def classify(name):
    """그림 이름 → (묶음, 재료 또는 'ORE'/'CORAL'/'DYED'/'WOOD')."""
    for rx, cls, rec in _COMPILED[:2]:
        if rx.fullmatch(name):
            return cls, rec
    glow = palette.is_glow_path(JAR_BLOCK + name + ".png")
    if glow:
        for rx, cls, rec in _COMPILED:
            if rx.fullmatch(name):
                return cls, rec
    d = _dyed(name)
    if d:
        return "dyed", ("DYED",) + d
    w = _wood(name)
    if w:
        return ("nether" if w in ("crimson", "warped") else "wood"), ("WOOD", w)
    for rx, cls, rec in _COMPILED:
        if rx.fullmatch(name):
            return cls, rec
    fr = flower_recipe(name)
    if fr is not None:
        return "plant", fr
    if PLANT_NAMES.fullmatch(name):
        return "plant", PLANT
    return ("light", DEVICE_GLOW) if glow else ("device", DEVICE)


# ─────────────────────────── 옮기기 ───────────────────────────

def _rgba(im):
    return np.array(im.convert("RGBA"))


def _target(lu, rec, mean):
    if rec.mid is None:
        a, b = rec.to_of
        mid, to = mean, a + b * mean
    else:
        mid = rec.mid
        to = rec.to if rec.to is not None else rec.to_of[0] + rec.to_of[1] * mid
    return to + rec.gain * (lu - mid)


def _nearest(ladder, t):
    lad = LADDER_LUMA[ladder]
    return min(lad, key=lambda e: abs(e[1] - t))[0]


def color_map(colors, weights, rec, mean=None, glow=False):
    """바닐라 색 목록 → 팔레트 이름 목록 (재료 rec). 빛나는 점 (rec.hot) 은 빛 그림 (glow) 에서만 따로 옮긴다."""
    if mean is None:
        w = np.asarray(weights, dtype=float)
        lus = np.array([palette.luma(c) for c in colors]) if colors else np.zeros(0)
        mean = float((lus * w).sum() / w.sum()) if w.sum() else 0.5
    out = []
    for c in colors:
        lu = palette.luma(c)
        if glow and rec.hot and hot(c, rec.hot[1]):
            lad, kind, to, gain = rec.hot
            t = to + gain * (lu - 0.6)
            out.append(_nearest(lad, t))
            continue
        out.append(_nearest(rec.ladder(bucket(c)), _target(lu, rec, mean)))
    if rec.steps or rec.floor:
        out = limit_steps(out, weights, rec.steps or 99, rec.floor)
    return out


def limit_steps(names, weights, n, floor=None):
    """
    한 장에 쓰는 팔레트 색을 n 개 이하로: 밝기로 늘어놓고 이웃한 두 색 가운데 (밝기 차 × 작은 쪽 무게) 가 가장 작은 짝을
    무거운 쪽으로 합친다 (바닐라 색 분포의 골짜기에서 갈린다). floor: 남은 가장 어두운 색이 이보다 어두우면 같은 계열에서
    floor 에 가장 가까운 색으로 올린다 (잎의 검은 구멍).
    """
    w = {}
    for nm, wt in zip(names, weights):
        w[nm] = w.get(nm, 0) + float(wt)
    lum = {nm: palette.luma(palette.c(nm)) for nm in w}
    order = sorted(w, key=lambda k: lum[k])
    to = {k: k for k in w}
    while len(order) > n:
        i = min(range(len(order) - 1),
                key=lambda j: (lum[order[j + 1]] - lum[order[j]]) * min(w[order[j]], w[order[j + 1]]))
        a, b = order[i], order[i + 1]
        keep, drop = (a, b) if w[a] >= w[b] else (b, a)
        w[keep] += w[drop]
        for k, v in to.items():
            if v == drop:
                to[k] = keep
        order.remove(drop)
    if floor is not None and order and lum[order[0]] < floor:
        dark = order[0]
        fam = palette.family(dark)
        cands = [f"{fam}{i}" for i in range(len(palette.FAMILIES[fam]))]
        up = min((c for c in cands if palette.luma(palette.c(c)) >= floor),
                 key=lambda c: palette.luma(palette.c(c)), default=None)
        if up:
            for k, v in to.items():
                if v == dark:
                    to[k] = up
    return [to[nm] for nm in names]


def grade_array(a, rec, mask=None, glow=False):
    """RGBA 배열을 옮긴다. mask 가 있으면 그 픽셀만 (나머지는 그대로). 알파는 그대로."""
    h, w = a.shape[:2]
    flat = a.reshape(-1, 4)
    sel = np.ones(len(flat), bool) if mask is None else mask.reshape(-1)
    rgb = flat[:, :3]
    uniq, inv = np.unique(rgb, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    vis = (flat[:, 3] > 0) & sel
    weights = np.bincount(inv[vis], minlength=len(uniq))
    cols = [tuple(int(v) for v in u) for u in uniq]
    lus = np.array([palette.luma(c) for c in cols])
    mean = float((lus * weights).sum() / weights.sum()) if weights.sum() else 0.5
    names = color_map(cols, weights, rec, mean, glow)
    lut = np.array([palette.c(n)[:3] for n in names], dtype=np.uint8)
    out = flat.copy()
    out[sel, :3] = lut[inv[sel]]
    return out.reshape(h, w, 4)


# 불 (불 블록, 모닥불 불꽃): 바닐라 불은 400 가지 넘는 색의 매끈한 노랑·흰빛이라 밝기 계단으로 옮기면 뼈빛·살구빛이 불 몸통을
# 덮는다. 바닐라 점의 밝기 차례 (전체 장면 띠에서 같은 색은 같은 칸) 로 다섯 칸에 나눈다: 끝은 어두운 핏빛, 녹빛, 녹슨 주황,
# 몸통은 호박빛. 장면마다 가장 뜨거운 자리 가운데 세 칸만 옅은 금빛 속불 (FIRE_CORE)
FIRE = ("fire_0", "fire_1", "campfire_fire")
FIRE_STEPS = [(0.12, "blood2"), (0.28, "ember0"), (0.55, "ember1"), (1.01, "ember2")]
FIRE_CORE = 3


def grade_fire(a):
    h, w = a.shape[:2]
    vis = a[..., 3] > 0
    lu = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) / 255.0
    vals = np.sort(lu[vis])
    n = len(vals)
    out = a.copy()
    rank = np.searchsorted(vals, lu, side="left") / max(1, n)      # 이 점보다 어두운 점의 몫
    for y in range(h):
        for x in range(w):
            if not vis[y, x]:
                continue
            for f, name in FIRE_STEPS:
                if rank[y, x] < f:
                    out[y, x, :3] = palette.c(name)[:3]
                    break
    for fy in range(0, h, w):
        fl, fv = lu[fy:fy + w], vis[fy:fy + w]
        if not fv.any():
            continue
        cut = np.quantile(fl[fv], 0.93)
        ys, xs = np.nonzero(fv & (fl >= cut))
        cy, cx = ys.mean(), xs.mean()
        order = sorted(zip(ys, xs), key=lambda p: ((p[0] - cy) ** 2 + (p[1] - cx) ** 2, -fl[p]))
        for y, x in order[:FIRE_CORE]:
            out[fy + y, x, :3] = palette.c("ember3")[:3]
    return out


def _ore_parts(name):
    m = re.fullmatch(r"(deepslate_)?(\w+?)_ore", name)
    if name.startswith("nether_"):
        return "netherrack", NETHERRACK, ORE[name[:-4]]
    pre = m.group(1) or ""
    base, brec = ORE_BASE[pre]
    return base, brec, ORE[m.group(2)]


# 옮긴 뒤의 손질 (DESPECKLE, CLAMP): 바닐라에서 매끈하던 곳이 계단 경계에 걸려 생긴 외톨이 점을 이웃 색으로 되돌리고,
# 아직 바닐라 색이 비쳐 보이는 진한 색 (빨강·주황·청록·분홍) 을 묶음마다 정한 채도 아래로 누른다.
# 빛 그림·레드스톤·용암은 누르지 않는다 (불씨와 신호는 붉어야 읽힌다)
CLAMP = [  # (색상 시작°, 끝°, 채도 한도 (HSV S, 밝기 0.25 넘는 색만), 대신 쓸 계단)
    (345, 360, 0.45, "rose"), (0, 15, 0.45, "rose"),        # 빨강 → 바랜 장미 (시든 붉음)
    (15, 33, 0.45, "rust"),                                 # 주황 → 녹빛
    (150, 200, 0.25, "verd"),                               # 청록 → 회녹
    (290, 345, 0.30, "mauve"),                              # 분홍·자홍 → 엷은 자주
]
DESPECKLE_VAN = 0.10   # 바닐라에서 이만큼 안으로 이웃과 비슷했던 점만 (바닐라 콘크리트 가루·양털의 잔결은 0.1 아래)
DESPECKLE_VAN2 = 0.16  # 바닐라의 잔결 (자갈·모래·균사체) 이 계단으로 뭉쳐 외톨이가 된 점
CLAMP_EXEMPT = re.compile(r"redstone.*|lava_.*|magma|.*fire.*")


def despeckle(out, van):
    """
    외톨이 점 지우기 (계단 경계가 만든 점만). 옮긴 그림의 한 점이
      1) 불투명한 이웃 넷 가운데 셋 이상과 다르고, 그 이웃의 가장 흔한 색이 두 번 넘게 있고, 바닐라에서는 그 점과 그 이웃들의
         밝기 차가 DESPECKLE_VAN 아래였거나,
      2) 여덟 이웃 어디에도 같은 색이 없고 네 이웃이 모두 한 색인데, 바닐라에서는 네 이웃이 한 색이 아니었고 (바닐라의 고른 잔결이
         계단으로 뭉친 것) 그 점과 이웃의 밝기 차가 DESPECKLE_VAN2 아래였으면
    이웃 색으로 바꾼다. 바닐라가 일부러 찍은 점 (광석, 꽃술, 바닐라에서도 한 색 바탕 위의 점) 은 그대로 남는다.
    움직이는 그림은 장면마다 감아서 본다.
    """
    h, w = out.shape[:2]
    if h % w:
        return out
    lu = (0.299 * van[..., 0] + 0.587 * van[..., 1] + 0.114 * van[..., 2]) / 255.0
    vkey = van[..., 0].astype(np.int64) * 65536 + van[..., 1].astype(np.int64) * 256 + van[..., 2]
    res = out.copy()
    n4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
    n8 = n4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))
    for fy in range(0, h, w):
        for y in range(w):
            for x in range(w):
                Y = fy + y
                if out[Y, x, 3] == 0:
                    continue
                p = tuple(out[Y, x])
                nb = []
                for dx, dy in n4:
                    yy, xx = fy + (y + dy) % w, (x + dx) % w
                    if out[yy, xx, 3] > 0:
                        nb.append((tuple(out[yy, xx]), lu[yy, xx], vkey[yy, xx]))
                diff = [c for c, _, _ in nb if c != p]
                if len(nb) < 3 or len(diff) < 3:
                    continue
                best = max(set(diff), key=diff.count)
                vl = [l for c, l, _ in nb if c == best]
                vmean = sum(vl) / len(vl)
                if diff.count(best) >= 2 and abs(lu[Y, x] - vmean) < DESPECKLE_VAN:
                    res[Y, x] = best
                    continue
                if len(nb) == 4 and diff.count(best) == 4 and len({k for _, _, k in nb}) > 1 \
                        and abs(lu[Y, x] - vmean) < DESPECKLE_VAN2 \
                        and all(tuple(out[fy + (y + dy) % w, (x + dx) % w]) != p for dx, dy in n8):
                    res[Y, x] = best
    return res


def clamp(out, name):
    if CLAMP_EXEMPT.fullmatch(name) or palette.is_glow_path(JAR_BLOCK + name + ".png"):
        return out
    import colorsys
    flat = out.reshape(-1, 4)
    res = flat.copy()
    for c in {tuple(int(v) for v in px[:3]) for px in flat[flat[:, 3] > 0]}:
        h, sat, val = colorsys.rgb_to_hsv(*(v / 255.0 for v in c))
        h *= 360
        for h0, h1, lim, lad in CLAMP:
            if h0 <= h < h1 and sat > lim and val > 0.25:
                rgb = palette.c(_nearest(lad, palette.luma(c)))[:3]
                m = (flat[:, :3] == c).all(-1)
                res[m, :3] = rgb
                break
    return res.reshape(out.shape)


def grade(name, im, vanilla):
    """그림 하나를 옮긴다 (색 옮기기 → 외톨이 점 지우기 → 진한 색 누르기). vanilla(이름) 는 다른 바닐라 그림을 읽는 함수."""
    cls, out = _grade_raw(name, im, vanilla)
    if name in FIRE:
        return cls, out
    van = _rgba(im)
    if out.shape == van.shape and cls != "ore":
        out = despeckle(out, van)
    return cls, clamp(out, name)


def _grade_raw(name, im, vanilla):
    cls, rec = classify(name)
    glow = palette.is_glow_path(JAR_BLOCK + name + ".png")
    a = _rgba(im)
    # 바닐라가 흘린 거의 보이지 않는 반투명 점 (화분의 진홍 뿌리 알파 2) 은 비우고, 비치는 블록의 알파는 그대로 둔다
    stray = (a[..., 3] > 0) & (a[..., 3] < 8)
    if stray.any() and not TRANSLUCENT.search(name):
        a[stray, 3] = 0
    if name in FIRE:
        return cls, grade_fire(a)
    if rec == "ORE":
        base_name, brec, orec = _ore_parts(name)
        b = _rgba(vanilla(base_name))
        if b.shape == a.shape:
            same = (a[..., :3] == b[..., :3]).all(-1) & (a[..., 3] == b[..., 3])
            out = grade_array(a, brec, same)
            return cls, grade_array(out, orec, ~same) if (~same).any() else out
        return cls, grade_array(a, orec)
    if rec == "CORAL":
        m = re.fullmatch(r"(dead_)?(\w+?)_coral(_block|_fan)?", name)
        if m.group(1):
            rec = R("stone", to=0.45, mid=0.62, gain=1.25)
        else:
            lad = CORAL[m.group(2)]
            rec = per({"*": lad, "grey": "pale"}, 0.03, 0.82, gain=1.15, steps=3)
        return cls, grade_array(a, rec)
    if isinstance(rec, tuple) and rec[0] == "DYED":
        _, dye, mat = rec
        lad, ka, kb = DYE[dye]
        gain, dark = DYED_MAT[mat]
        # 테라코타처럼 채도가 낮은 물들임도 그 물감의 계단으로 (회색 묶음까지). 유약 테라코타의 흰 무늬만 돌 회색으로
        grey = "stone" if mat == "glazed_terracotta" and dye not in ("white", "light_gray", "gray", "black") else lad
        hotspec = GLOWHOT if mat == "candle_lit" else None
        # 양털·콘크리트·가루·테라코타는 한두 칸 (바닐라의 고른 결이 점으로 흩어지지 않게)
        steps = 2 if mat in ("wool", "concrete", "concrete_powder", "terracotta") else None
        r = per({"*": lad, "grey": grey}, ka - dark, kb, gain=gain, hot=hotspec, steps=steps)
        return cls, grade_array(a, r, glow=glow)
    if isinstance(rec, tuple) and rec[0] == "WOOD":
        return cls, grade_array(a, WOOD_RECIPE[rec[1]])
    return cls, grade_array(a, rec, glow=glow)


# ─────────────────────────── 색 지도 ───────────────────────────
# x = (1 − 기온) × 255 (왼쪽이 덥다), y = (1 − 강수 × 기온) × 255 (아래가 마르다). 지역 바이옴은 기온 0.5, 강수 0 → (127, 255)
GRASS_AT = (127, 255)
VANILLA_WATER = (0x3f, 0x76, 0xe4)   # 바닐라 기본 물 색 (비교판의 바닐라 쪽)
WATER_TINT = (0xc6, 0xc4, 0xbc)      # 데이터팩 지역 바이옴의 물 색 (9 지역 같다). 비교판에서 물을 물들여 본다
BIOMES = os.path.join(ROOT, "plugin", "src", "main", "resources", "datapack", "soulsdp", "data", "souls", "worldgen",
                      "biome")
SHEET_REGION = "redin"                # 비교판에서 물들여 보는 지역 (시험 방이 있는 성벽)


def region_tint(kind, region=SHEET_REGION):
    """데이터팩 지역 바이옴의 effects 색 (grass, foliage, dry_foliage). 없으면 색 지도의 (127, 255)."""
    import json
    try:
        with open(os.path.join(BIOMES, region + ".json"), encoding="utf-8") as f:
            h = json.load(f)["effects"][kind + "_color"].lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (OSError, KeyError, ValueError):
        return None

# 띠: (오른쪽 끝 x, 색) — 덥고 마른 곳에서 춥고 젖은 곳으로. 위쪽 (젖은 곳) 은 한 단씩 짙어진다
COLORMAP_BANDS = {
    "grass":   [(56, ["parch2", "olive4", "olive3", "moss2"]), (168, ["olive4", "olive3", "moss2", "moss1"]),
                (256, ["stone2", "olive3", "moss2", "moss1"])],
    "foliage": [(56, ["bronze3", "olive3", "olive2", "moss1"]), (168, ["olive3", "olive2", "moss2", "moss1"]),
                (256, ["stone1", "olive2", "moss1", "moss0"])],
    "dry_foliage": [(56, ["parch1", "bronze3", "rust3", "rust2"]), (168, ["rust3", "bronze3", "rust2", "rust1"]),
                    (256, ["stone1", "rust3", "rust2", "rust1"])],
}


def _wobble(i, seed, amp):
    """띠 경계가 곧은 줄이 되지 않게: 줄 번호마다 정해진 들쭉날쭉 (위치 해시, 계단 모양)."""
    v = (i // 8 * 2654435761 + seed * 40503) & 0xffffffff
    return int(v % (2 * amp + 1)) - amp


def colormap(kind):
    """256×256 색 지도. 계단 띠만 쓴다 (부드러운 그라데이션 없음)."""
    bands = COLORMAP_BANDS[kind]
    a = np.zeros((256, 256, 4), np.uint8)
    for y in range(256):
        wet = 255 - y                      # 0 = 마름 (아래), 255 = 젖음 (위)
        for x in range(256):
            xe = x + _wobble(y, 3, 6)
            for edge, cols in bands:
                if xe < edge:
                    break
            k = min(3, max(0, (wet + _wobble(x, 7, 10)) // 64))
            a[y, x] = palette.c(cols[k])
    return a


# ─────────────────────────── 짓기 ───────────────────────────

def save_png(arr, path):
    """색이 256 개 이하면 색표 PNG (팩을 작게, 바닐라처럼). 색은 그대로다."""
    h, w = arr.shape[:2]
    flat = arr.reshape(-1, 4)
    uniq, inv = np.unique(flat, axis=0, return_inverse=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if len(uniq) <= 256:
        p = Image.fromarray(inv.reshape(h, w).astype(np.uint8), "P")
        pal = uniq[:, :3].astype(np.uint8).flatten().tolist()
        p.putpalette(pal + [0] * (768 - len(pal)))
        if (uniq[:, 3] < 255).any():
            p.save(path, optimize=True, transparency=bytes(uniq[:, 3].tolist()))
        else:
            p.save(path, optimize=True)
    else:
        Image.fromarray(arr, "RGBA").save(path, optimize=True)


class Vanilla:
    def __init__(self, jar):
        self.z = zipfile.ZipFile(jar)
        self.cache = {}

    def names(self):
        return sorted(n[len(JAR_BLOCK):-4] for n in self.z.namelist()
                      if n.startswith(JAR_BLOCK) and n.endswith(".png") and "/" not in n[len(JAR_BLOCK):])

    def metas(self):
        return sorted(n for n in self.z.namelist() if n.startswith(JAR_BLOCK) and n.endswith(".png.mcmeta"))

    def block(self, name):
        if name not in self.cache:
            self.cache[name] = Image.open(io.BytesIO(self.z.read(JAR_BLOCK + name + ".png"))).convert("RGBA")
        return self.cache[name]

    def colormap(self, kind):
        return Image.open(io.BytesIO(self.z.read(JAR_COLORMAP + kind + ".png"))).convert("RGBA")


def grade_all(van):
    """이름 → (묶음, 옮긴 RGBA 배열)."""
    return {n: grade(n, van.block(n), van.block) for n in van.names()}


def build(out_root, jar=None):
    """팩 폴더에 블록 그림 전부와 .mcmeta, 색 지도 셋을 쓴다. 묶음별 수를 돌려준다."""
    jar = jar or client_jar()
    if not jar:
        raise SystemExit("블록 그림을 옮기려면 바닐라 1.21.11 클라이언트 jar 가 있어야 한다 "
                         "(SOULS_CLIENT_JAR 또는 ~/.cache/souls-client/versions/1.21.11.jar)")
    van = Vanilla(jar)
    bdir = os.path.join(out_root, *OUT_BLOCK)
    counts = {}
    for name, (cls, arr) in grade_all(van).items():
        save_png(arr, os.path.join(bdir, name + ".png"))
        counts[cls] = counts.get(cls, 0) + 1
    for m in van.metas():
        with open(os.path.join(bdir, m[len(JAR_BLOCK):]), "wb") as f:
            f.write(van.z.read(m))
    cdir = os.path.join(out_root, *OUT_COLORMAP)
    for kind in COLORMAP_BANDS:
        save_png(colormap(kind), os.path.join(cdir, kind + ".png"))
    return counts


# 바닐라가 바탕 그림을 그대로 깔고 그 위에 무늬를 더한 그림 → 바탕 (같은 자리 픽셀이 30% 넘게 같은 것, 1.21.11 jar 에서 쟀다).
# 바탕 픽셀은 팩의 최종 바탕 그림 (2층이 새로 그렸으면 그것) 을 따른다: 광석이 둘레 돌과, 풀 블록 옆면이 흙과, 작업대 옆면이
# 판자와 이어진다
DERIVED = {
    **{f"{o}_ore": "stone" for o in ("coal", "iron", "copper", "gold", "redstone", "lapis", "diamond", "emerald")},
    **{f"deepslate_{o}_ore": "deepslate" for o in ("coal", "iron", "copper", "gold", "redstone", "lapis", "diamond",
                                                   "emerald")},
    "nether_gold_ore": "netherrack", "nether_quartz_ore": "netherrack", "crimson_nylium_side": "netherrack",
    "warped_nylium_side": "netherrack",
    "grass_block_side": "dirt", "grass_block_snow": "dirt", "podzol_side": "dirt", "mycelium_side": "dirt",
    "dirt_path_side": "dirt", "rooted_dirt": "dirt",
    **{f"suspicious_gravel_{i}": "gravel" for i in range(4)}, **{f"suspicious_sand_{i}": "sand" for i in range(4)},
    "cracked_stone_bricks": "stone_bricks", "mossy_stone_bricks": "stone_bricks", "mossy_cobblestone": "cobblestone",
    "cracked_deepslate_bricks": "deepslate_bricks", "cracked_deepslate_tiles": "deepslate_tiles",
    "cracked_polished_blackstone_bricks": "polished_blackstone_bricks", "gilded_blackstone": "blackstone",
    "smooth_stone_slab_side": "smooth_stone", "sandstone_bottom": "sandstone", "red_sandstone_bottom": "red_sandstone",
    "reinforced_deepslate_side": "deepslate", "stonecutter_top": "stone",
    "crafting_table_front": "oak_planks", "crafting_table_side": "oak_planks", "lectern_base": "oak_planks",
    "barrel_bottom": "spruce_planks", "cartography_table_top": "dark_oak_planks",
    "muddy_mangrove_roots_side": "mud",
}


def finish(out_root, jar=None):
    """
    2층 (blocks_core) 이 쓴 뒤에 부른다. DERIVED 의 그림 가운데 2층이 새로 그리지 않은 것은 바닐라에서 바탕과 같던 픽셀을
    팩의 최종 바탕 그림의 같은 자리 픽셀로 바꾼다. 맞춘 그림 수를 돌려준다.
    """
    jar = jar or client_jar()
    van = Vanilla(jar)
    bdir = os.path.join(out_root, *OUT_BLOCK)
    done = 0
    for name, base in sorted(DERIVED.items()):
        p, bp = os.path.join(bdir, name + ".png"), os.path.join(bdir, base + ".png")
        if not (os.path.exists(p) and os.path.exists(bp)):
            continue
        cur = _rgba(Image.open(p))
        mine = grade(name, van.block(name), van.block)[1]
        if not np.array_equal(cur, mine):
            continue                      # 2층이 새로 그린 그림은 그대로 둔다
        fb = _rgba(Image.open(bp))
        va, vb = _rgba(van.block(name)), _rgba(van.block(base))
        if fb.shape != cur.shape or va.shape != vb.shape:
            continue
        same = (va == vb).all(-1)
        out = cur.copy()
        out[same] = fb[same]
        if not np.array_equal(out, cur):
            save_png(out, p)
            done += 1
    return done


# ─────────────────────────── 비교판 ───────────────────────────
# 물드는 그림은 비교판에서 물들여 보인다: 바닐라는 바닐라 평원 색, 새 것은 지역 바이옴 자리 (127, 255) 의 색
FOLIAGE_TINTED = re.compile(r"(oak|jungle|acacia|dark_oak|mangrove)_leaves|vine")
GRASS_TINTED = re.compile(r"grass_block_top|grass_block_side_overlay|short_grass|tall_grass_(top|bottom)|fern|"
                          r"large_fern_(top|bottom)|bush|sugar_cane|(attached_)?(melon|pumpkin)_stem|pink_petals_stem|"
                          r"wildflowers_stem")
FIXED_TINT = {"spruce_leaves": (0x61, 0x99, 0x61), "birch_leaves": (0x80, 0xa7, 0x55), "lily_pad": (0x20, 0x80, 0x30),
              "redstone_dust_dot": (0xc8, 0x1c, 0x00), "redstone_dust_line0": (0xc8, 0x1c, 0x00),
              "redstone_dust_line1": (0xc8, 0x1c, 0x00)}
WATER = re.compile(r"water_(still|flow|overlay)")
CLASS_ORDER = ["stone", "ore", "wood", "plant", "soil", "metal", "glass", "dyed", "nether", "end", "light",
               "liquid", "device"]
CLASS_KO = {"stone": "돌·벽돌·심층암", "ore": "광석", "wood": "나무·판자·통나무", "plant": "잎·풀·식물",
            "soil": "흙·모래·자갈·눈", "metal": "쇠·구리·광물 블록", "glass": "유리·얼음",
            "dyed": "양털·콘크리트·테라코타·초", "nether": "네더", "end": "엔드", "light": "빛을 내는 블록",
            "liquid": "물·용암", "device": "장치·작업대·그 밖"}


def tint_of(name, new, maps):
    if WATER.fullmatch(name):
        return WATER_TINT if new else VANILLA_WATER
    if name in FIXED_TINT:
        return FIXED_TINT[name]
    if name == "leaf_litter":
        return maps["dry_foliage"][1 if new else 0]
    if FOLIAGE_TINTED.fullmatch(name):
        return maps["foliage"][1 if new else 0]
    if GRASS_TINTED.fullmatch(name):
        return maps["grass"][1 if new else 0]
    return None


def _show(arr, tint):
    a = arr.astype(float)
    if tint is not None:
        a[..., :3] *= np.array(tint, float) / 255.0
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


def _frame0(im):
    w, h = im.size
    return im.crop((0, 0, w, w)) if h > w else im


def _checker(w, h, s=8):
    bg = Image.new("RGBA", (w, h), (104, 100, 94, 255))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, s):
        for x in range(0, w, s):
            if (x // s + y // s) % 2:
                d.rectangle([x, y, x + s - 1, y + s - 1], fill=(118, 114, 108, 255))
    return bg


def _cell(im, size):
    im = _frame0(im)
    c = _checker(size, size)
    c.alpha_composite(im.resize((size, size), Image.NEAREST))
    return c


def tint_maps(van, new_maps):
    """(바닐라 평원 색, 새 지역 바이옴 색 (SHEET_REGION 의 effects, 없으면 색 지도)) 묶음 이름마다."""
    out = {}
    for kind in COLORMAP_BANDS:
        old = van.colormap(kind).getpixel((51, 173))[:3]    # 바닐라 평원 (기온 0.8, 강수 0.4)
        new = region_tint(kind) or tuple(int(v) for v in new_maps[kind][GRASS_AT[1], GRASS_AT[0], :3])
        out[kind] = (old, new)
    return out


def final_pack(jar=None):
    """
    팩에 들어가는 최종 블록 그림 (1층 build → 2층 blocks_core.build → finish) 을 임시 폴더에 지어 읽는다.
    이름 → RGBA 배열. 비교판은 이것으로 그린다 (2층이 덮은 그림과 바탕 맞춤까지 함께 본다).
    """
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="blocks_final_")
    try:
        build(tmp, jar)
        import blocks_core
        blocks_core.build(tmp)
        finish(tmp, jar)
        bdir = os.path.join(tmp, *OUT_BLOCK)
        return {f[:-4]: _rgba(Image.open(os.path.join(bdir, f))) for f in os.listdir(bdir) if f.endswith(".png")}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def write_sheets(out_dir=SHEETS, jar=None, scale=4, cols=8, rows=9):
    """
    묶음마다 바닐라 | 최종 그림 (1층 → 2층 → 바탕 맞춤, final_pack) 쌍을 4배로 늘어놓은 비교판. 물드는 그림은 물들여 보인다.
    2층 (blocks_core) 이 새로 그린 그림은 이름 뒤에 * 를 붙인다.
    """
    jar = jar or client_jar()
    van = Vanilla(jar)
    graded = grade_all(van)
    final = final_pack(jar)
    import blocks_core
    core = set(blocks_core.textures())
    graded = {n: (cls, final.get(n, arr)) for n, (cls, arr) in graded.items()}
    new_maps = {k: colormap(k) for k in COLORMAP_BANDS}
    maps = tint_maps(van, new_maps)
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        if old.startswith("grade_") and old.endswith(".png"):
            os.remove(os.path.join(out_dir, old))
    by = {}
    for n, (cls, arr) in graded.items():
        by.setdefault(cls, []).append(n)
    size = 16 * scale
    cw, ch = size * 2 + 14, size + 18
    written = []
    for cls in CLASS_ORDER:
        names = sorted(by.get(cls, []))
        per_page = cols * rows
        for page in range((len(names) + per_page - 1) // per_page):
            chunk = names[page * per_page:(page + 1) * per_page]
            r = (len(chunk) + cols - 1) // cols
            sheet = Image.new("RGBA", (cols * cw + 8, r * ch + 30), (24, 23, 22, 255))
            d = ImageDraw.Draw(sheet)
            d.text((8, 8), f"{cls}  ({len(names)})  vanilla | final pack (* = redrawn in blocks_core)  — tinted "
                           f"textures shown tinted (vanilla plains / souls:{SHEET_REGION} biome)",
                   fill=(200, 192, 170, 255))
            for i, n in enumerate(chunk):
                x, y = 8 + (i % cols) * cw, 26 + (i // cols) * ch
                va = _rgba(van.block(n))
                na = graded[n][1]
                sheet.paste(_cell(_show(va, tint_of(n, False, maps)), size), (x, y))
                sheet.paste(_cell(_show(na, tint_of(n, True, maps)), size), (x + size + 2, y))
                d.text((x, y + size + 2), n[:23] + ("*" if n in core else ""), fill=(170, 164, 150, 255))
            p = os.path.join(out_dir, f"grade_{CLASS_ORDER.index(cls):02d}_{cls}_{page + 1}.png")
            sheet.convert("RGB").save(p, optimize=True)
            written.append(p)
    written.append(write_tiles(van, graded, maps, out_dir))
    written.append(write_colormaps(van, new_maps, out_dir))
    written.append(write_in_place(van, maps, out_dir, final))
    return written


def write_in_place(van, maps, out_dir, final, scale=3, cols=6):
    """
    팩에 들어가는 최종 모습 (final_pack: 1층 → 2층 blocks_core → finish) 으로, 바탕을 깐 그림 (DERIVED) 을 그 바탕 3×3 의
    가운데에 놓아 본다 (바닐라 | 최종). 광석이 둘레 돌에서 읽히는지, 이음매가 보이는지 본다.
    """
    names = sorted(DERIVED, key=lambda n: (DERIVED[n], n))
    t16 = 16 * scale
    size = t16 * 3
    cw, ch = size * 2 + 16, size + 20
    r = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + 8, r * ch + 30), (24, 23, 22))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), "in place: texture in the middle of its base, 3x3   vanilla | final pack (grade -> blocks_core -> finish)",
           fill=(200, 192, 170))
    for i, n in enumerate(names):
        x, y = 8 + (i % cols) * cw, 26 + (i // cols) * ch
        b = DERIVED[n]
        for k, (mid, ring, new) in enumerate(((_rgba(van.block(n)), _rgba(van.block(b)), False),
                                              (final[n], final[b], True))):
            tile = Image.new("RGBA", (size, size), (24, 23, 22, 255))
            for ty in range(3):
                for tx in range(3):
                    arr = mid if (tx, ty) == (1, 1) else ring
                    im = _frame0(_show(arr, tint_of(n if (tx, ty) == (1, 1) else b, new, maps)))
                    tile.alpha_composite(im.resize((t16, t16), Image.NEAREST), (tx * t16, ty * t16))
            sheet.paste(tile.convert("RGB"), (x + k * (size + 2), y))
        d.text((x, y + size + 2), f"{n} on {b}", fill=(170, 164, 150))
    p = os.path.join(out_dir, "grade_in_place.png")
    sheet.save(p, optimize=True)
    return p


TILE_SET = ["stone", "cobblestone", "stone_bricks", "mossy_stone_bricks", "andesite", "tuff", "deepslate",
            "deepslate_bricks", "blackstone", "bricks", "sandstone", "gravel", "dirt", "coarse_dirt", "grass_block_top",
            "sand", "oak_planks", "spruce_planks", "dark_oak_planks", "oak_log", "spruce_log", "birch_log",
            "oak_leaves", "spruce_leaves", "netherrack", "nether_bricks", "end_stone", "iron_ore", "coal_ore",
            "diamond_ore", "gold_ore", "redstone_ore", "lapis_ore", "copper_ore", "emerald_ore", "deepslate_iron_ore",
            "water_still", "lava_still", "moss_block", "terracotta", "white_wool", "red_wool", "iron_block",
            "copper_block", "oxidized_copper", "glowstone", "obsidian", "quartz_block_side"]


def write_tiles(van, graded, maps, out_dir, scale=3, cols=6):
    """3×3 으로 깔아 이음매와 반복을 본다 (바닐라 | 새 것)."""
    size = 16 * scale * 3
    cw, ch = size * 2 + 16, size + 20
    names = [n for n in TILE_SET if n in graded]
    r = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + 8, r * ch + 30), (24, 23, 22))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), "3x3 tiling  vanilla | final pack (grade -> blocks_core -> finish)", fill=(200, 192, 170))
    for i, n in enumerate(names):
        x, y = 8 + (i % cols) * cw, 26 + (i // cols) * ch
        for k, (arr, new) in enumerate(((_rgba(van.block(n)), False), (graded[n][1], True))):
            t = _frame0(_show(arr, tint_of(n, new, maps)))
            t = t.resize((16 * scale, 16 * scale), Image.NEAREST)
            tile = Image.new("RGBA", (size, size), (24, 23, 22, 255))
            for ty in range(3):
                for tx in range(3):
                    tile.alpha_composite(t, (tx * 16 * scale, ty * 16 * scale))
            sheet.paste(tile.convert("RGB"), (x + k * (size + 2), y))
        d.text((x, y + size + 2), n, fill=(170, 164, 150))
    p = os.path.join(out_dir, "grade_tiles_3x3.png")
    sheet.save(p, optimize=True)
    return p


def write_colormaps(van, new_maps, out_dir):
    sheet = Image.new("RGB", (3 * (256 * 2 + 24) + 8, 256 + 40), (24, 23, 22))
    d = ImageDraw.Draw(sheet)
    for i, kind in enumerate(COLORMAP_BANDS):
        x = 8 + i * (256 * 2 + 24)
        sheet.paste(van.colormap(kind).convert("RGB"), (x, 24))
        sheet.paste(Image.fromarray(new_maps[kind], "RGBA").convert("RGB"), (x + 260, 24))
        gx, gy = GRASS_AT
        d.rectangle([x + 260 + gx - 3, 24 + gy - 3, x + 260 + gx + 3, 24 + gy + 3], outline=(240, 176, 96))
        d.text((x, 6), f"{kind}: vanilla | graded (box = souls biomes at 127,255)", fill=(200, 192, 170))
    p = os.path.join(out_dir, "grade_colormaps.png")
    sheet.save(p, optimize=True)
    return p


def main(argv):
    if "--sheets" in argv:
        for p in write_sheets():
            print(os.path.relpath(p, ROOT))
        return 0
    out = argv[0] if argv else os.path.join(HERE, "resourcepack")
    counts = build(out)
    print("블록 그림:", sum(counts.values()), dict(sorted(counts.items())), "바탕 맞춤:", finish(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
