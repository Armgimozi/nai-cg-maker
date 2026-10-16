"""광산 마을 조각 (0.3.6, design/036/CONTRACT.md §2.13 · tools/data/036/district.json · visual.json district_style).

승강장 · 제련소 · 광부 숙소 · 광석 하치장 + 구리 가로등 · 광산 길잡이. 수레·벤치·참나무·화단은 마을 조각(pieces_town)을 그대로 쓴다.
정방향: 정면(문)은 z=0 쪽, 북쪽을 본다 (VILLAGE.md §2). 실제 방향은 district_mine.py 배치가 정한다.

지킬 것 (build_all 이 검사):
- 구리는 모두 waxed_* (오버월드에서 녹슬면 청사진·자가 진단과 어긋남).
- 광산 광석·보석 블록 12종과 빈 광맥 블록(조약돌·이끼 낀 조약돌·조약돌 심층암·흑암)은 쓰지 않는다 (CONTRACT §3.3).
  원석 블록(raw_*_block)은 된다.
"""
import math

from vlib import (Piece, mix, stairs, slab, log, wall, fence, pane, bars, trapdoor, lantern, chain, campfire, B)
from pieces_town import _hang, _corbel_lamp, _plant, make_signpost

COPPER_ROOF = "waxed_oxidized_cut_copper"   # 녹청 지붕
TRIM = "waxed_cut_copper"                   # 마을과 같은 구리 테두리
OLD_TRIM = "waxed_weathered_cut_copper"     # 녹슨 구리 테
CU_LANTERN = "waxed_copper_lantern"         # 초록 불꽃 — 광산 구역 표시


def _cu_hang(p, x, y, z, chain_n=0):
    """구리 사슬 + 매단 구리 등불."""
    for i in range(chain_n):
        p.set(x, y + 1 + i, z, B("waxed_copper_chain", axis="y"))
    p.set(x, y, z, lantern(hanging=True, kind=CU_LANTERN))
    p.light(x, y, z)


# ─────────────────────────────── 광산 승강장 ───────────────────────────────

def mine_headframe():
    """광산 승강장: 돌 아래층(승강기 홀, 앞 둥근 아치) + 벗긴 짙은 참나무 탑(엇갈린 버팀) + 꼭대기 권양 바퀴 + 쇠사슬.
    승강기 칸 = 구리 창살 + 구리 격자 바닥 + 구리 문 (우클릭 mine_lift). 광산에서 돌아오는 자리 mine_exit 는 승강기 앞."""
    W, H, D, F = 13, 24, 13, 1
    p = Piece("mine_headframe", "광산 승강장", W, H, D, floor_y=F, anchor=(6, 1),
              foundation_mix=[("stone_bricks", 4), ("mossy_stone_bricks", 1), ("deepslate_bricks", 2)])
    stone = mix(("stone_bricks", 4), ("cracked_stone_bricks", 1), ("mossy_stone_bricks", 1), ("deepslate_bricks", 2), seed=31)
    pave = mix(("polished_andesite", 3), ("stone_bricks", 2), ("tuff_bricks", 1), seed=32)
    quoin = B("polished_deepslate")
    frame = "stripped_dark_oak_log"
    glass = "orange_stained_glass_pane"

    # 기초 · 바닥 · 앞 돌판 (z=0 줄 = 현관)
    p.fill(1, 0, 1, 11, 1, 11, stone)
    p.fill(2, 1, 2, 10, 1, 10, pave)
    p.fill(2, 0, 0, 10, 0, 0, stone)
    p.fill(2, 1, 0, 10, 1, 0, pave)
    # 아래층 벽 (y 2..6) + 모서리 깎은 심층암
    for x in range(1, 12):
        for z in (1, 11):
            p.fill(x, 2, z, x, 6, z, stone)
    for z in range(1, 12):
        for x in (1, 11):
            p.fill(x, 2, z, x, 6, z, stone)
    for (x, z) in ((1, 1), (11, 1), (1, 11), (11, 11)):
        p.fill(x, 1, z, x, 6, z, quoin)
    p.clear(2, 2, 2, 10, 6, 10)
    # 앞 큰 아치 (x 4..8, 높이 4) · 왼쪽 창 · 오른쪽 벽 등불
    p.arch(4, 8, 2, 4, 1, 1, mat="deepslate_brick", axis="x", style="round", frame=B("polished_deepslate"))
    p.window(2, 3, 1, "north", glass=glass, shutter="dark_oak")
    _corbel_lamp(p, 10, 4, 0, "south")
    # 옆·뒤 창
    for z in (4, 8):
        p.window(1, 3, z, "west", glass=glass, sill=stairs("stone_brick", "east", "top"))
        p.window(11, 3, z, "east", glass=glass, sill=stairs("stone_brick", "west", "top"))
    for x in (3, 9):
        p.window(x, 3, 11, "south", glass=glass, sill=stairs("stone_brick", "north", "top"))

    # 승강기 칸 (x 5..7, z 6..8): 구리 격자 바닥 · 구리 창살 · 앞 구리 문 · 위 구리 지붕
    p.fill(5, 1, 6, 7, 1, 8, B("waxed_copper_grate"))
    for (x, z) in ((5, 6), (7, 6), (5, 7), (7, 7), (5, 8), (6, 8), (7, 8)):
        p.fill(x, 2, z, x, 4, z, B("waxed_copper_bars"))
    p.door("waxed_copper", 6, 2, 6, "north")
    p.set(6, 4, 6, B("waxed_copper_bars"))
    p.clear(6, 2, 7, 6, 4, 7)
    p.fill(5, 5, 6, 7, 5, 8, slab(TRIM, "top"))
    p.set(6, 5, 7, B("waxed_copper_block"))
    p.interact("mine_lift", [(6, 2, 6), (6, 3, 6), (5, 3, 6), (7, 3, 6)])
    p.ambient(6, 2, 7, "dust")
    p.point("mine_exit", 6, 2, 4, "front")
    # 홀: 들보 + 매단 등불, 승강기 뒤 레일 토막 + 짐
    for x in range(2, 11):
        p.set(x, 6, 4, log(frame, "x"))
        p.set(x, 6, 9, log(frame, "x"))
    _hang(p, 3, 5, 4)
    _hang(p, 9, 5, 4)
    _cu_hang(p, 6, 5, 9)
    for z in (9, 10):
        p.set(6, 2, z, B("rail", shape="north_south"))
    p.set(3, 2, 10, B("barrel", facing="up"))
    p.set(4, 2, 10, B("barrel", facing="north"))
    p.set(3, 3, 10, B("raw_iron_block"))
    p.set(9, 2, 10, B("barrel", facing="up"))
    p.set(10, 2, 10, B("raw_copper_block"))
    p.set(10, 2, 2, B("grindstone", face="floor", facing="north"))
    p.set(2, 2, 6, B("dark_oak_shelf", facing="east"))
    p.set(2, 2, 7, B("dark_oak_shelf", facing="east"))

    # 아래층 지붕: 심층암 기와 박공 + 구리 용마루 (탑이 뚫고 올라감)
    p.gable_roof(1, 1, 11, 11, 7, "deepslate_tile", axis="x", overhang=1, end_overhang=1,
                 gable=mix(("white_terracotta", 3), ("light_gray_terracotta", 1), seed=33), ridge=slab(TRIM))
    # 탑 (y 7..18): 네 기둥 + 가로보 + 엇갈린 버팀(울타리)
    posts = ((3, 4), (9, 4), (3, 9), (9, 9))
    for (x, z) in posts:
        p.fill(x, 7, z, x, 18, z, log(frame))
    for y in (10, 14, 18):
        for x in range(4, 9):
            p.set(x, y, 4, log(frame, "x"))
            p.set(x, y, 9, log(frame, "x"))
        for z in range(5, 9):
            p.set(3, y, z, log(frame, "z"))
            p.set(9, y, z, log(frame, "z"))
    for y0 in (11, 15):
        for k in range(3):
            p.set(4 + k, y0 + k, 4, fence("dark_oak"))
            p.set(8 - k, y0 + k, 9, fence("dark_oak"))
            p.set(3, y0 + k, 5 + k, fence("dark_oak"))
            p.set(9, y0 + k, 8 - k, fence("dark_oak"))
    # 바퀴 받침 들보 + 기둥 머리 구리 갓
    for x in range(4, 9):
        p.set(x, 18, 5, log(frame, "x"))
        p.set(x, 18, 8, log(frame, "x"))
    for (x, z) in posts:
        p.set(x, 19, z, B("waxed_copper_block"))
        p.set(x, 20, z, slab(TRIM))
    # 권양 바퀴 (XY 평면, z 6..7) + A자 받침
    cx, cy, R = 6, 21, 2
    for a in range(0, 360, 10):
        x = cx + round(R * math.cos(math.radians(a)))
        y = cy + round(R * math.sin(math.radians(a)))
        for z in (6, 7):
            p.set(x, y, z, B("stripped_spruce_wood", axis="z"))
    for z in (6, 7):
        p.set(cx, cy, z, B("waxed_copper_block"))
    for (x, y) in ((4, 19), (8, 19), (5, 20), (7, 20)):
        p.set(x, y, 5, fence("dark_oak"))
        p.set(x, y, 8, fence("dark_oak"))
    # 쇠사슬: 바퀴에서 승강기 칸 지붕까지 (지붕을 뚫고 내려감)
    for y in range(6, 19):
        if p.get(6, y, 7) in (" ", ".") or "deepslate_tile" in p.get(6, y, 7) or "cut_copper" in p.get(6, y, 7):
            p.set(6, y, 7, chain())
    # 앞 표지판 · 깃발 · 광부
    p.sign(6, 6, 0, ["<#3fb090><b>광산 승강장</b></#3fb090>", "<gray>아래로 내려가는 곳</gray>"],
           wood="dark_oak", facing="north", glow=True)
    for bx in (1, 11):
        p.banner(bx, 6, 0, "black", [("stripe_bottom", "orange"), ("rhombus", "cyan"), ("border", "black")], facing="north")
    p.npc("miner", 9, 2, 0, "front")
    return p


# ─────────────────────────────── 제련소 ───────────────────────────────

def smelter():
    """제련소: 흑암 벽돌 작업장(앞 둥근 아치, 용암 화덕·용광로·모루·대장장이 작업대·주괴 더미) + 짙은 참나무 뼈대·회반죽 2층 +
    녹청 구리 지붕(주황 테라코타 박공) + 오른쪽 뒤 벽돌 굴뚝(구리 띠, 모닥불 연기). 크기 13×18×12 (visual.json)."""
    W, H, D, F = 13, 18, 12, 1
    p = Piece("smelter", "제련소", W, H, D, floor_y=F, anchor=(6, 1),
              foundation_mix=[("deepslate_bricks", 3), ("polished_blackstone_bricks", 2), ("tuff_bricks", 1)])
    stone = mix(("polished_blackstone_bricks", 4), ("cracked_polished_blackstone_bricks", 1), ("deepslate_bricks", 2),
                ("polished_blackstone", 1), seed=41)
    pave = mix(("polished_blackstone_bricks", 3), ("deepslate_tiles", 2), ("polished_tuff", 1), seed=42)
    plaster = mix(("white_terracotta", 4), ("light_gray_terracotta", 1), seed=43)
    frame = "dark_oak_log"
    glass = "orange_stained_glass_pane"

    p.fill(0, 0, 1, 10, 1, 10, stone)
    p.fill(1, 1, 2, 9, 1, 9, pave)
    p.fill(1, 0, 0, 9, 0, 0, stone)            # 앞 돌판 (z=0 줄)
    p.fill(1, 1, 0, 9, 1, 0, pave)
    for x in range(0, 11):
        for z in (1, 10):
            p.fill(x, 2, z, x, 5, z, stone)
    for z in range(1, 11):
        for x in (0, 10):
            p.fill(x, 2, z, x, 5, z, stone)
    for (x, z) in ((0, 1), (10, 1), (0, 10), (10, 10)):
        p.fill(x, 1, z, x, 5, z, B("polished_blackstone"))
    p.clear(1, 2, 2, 9, 5, 9)
    p.arch(4, 8, 2, 4, 1, 1, mat="polished_blackstone_brick", axis="x", style="round", frame=B("chiseled_polished_blackstone"))
    for x in (2, 9):
        p.window(x, 3, 1, "north", glass=glass, sill=stairs("polished_blackstone_brick", "south", "top"))
    for z in (4, 7):
        p.window(0, 3, z, "west", glass=glass)
    p.window(5, 3, 10, "south", glass=glass, sill=stairs("polished_blackstone_brick", "north", "top"))
    # 2층 (y 6 바닥 들보, y 7..9 뼈대 벽)
    for x in range(0, 11):
        p.set(x, 6, 1, log(frame, "x"))
        p.set(x, 6, 10, log(frame, "x"))
    for z in range(2, 10):
        p.set(0, 6, z, log(frame, "z"))
        p.set(10, 6, z, log(frame, "z"))
    p.fill(1, 6, 2, 9, 6, 9, B("spruce_planks"))
    for (x0, z0, x1, z1) in ((0, 1, 10, 1), (0, 10, 10, 10), (0, 1, 0, 10), (10, 1, 10, 10)):
        p.timber_wall(x0, 7, z0, x1, 9, z1, frame=frame, infill=plaster, post_every=3, beams=False, mid_beam=9)
    p.clear(1, 7, 2, 9, 9, 9)
    for x in (2, 5, 8):
        p.window(x, 7, 1, "north", glass=glass, shutter="spruce")
    for z in (4, 7):
        p.window(0, 7, z, "west", glass=glass)
    # 녹청 구리 지붕 + 주황 테라코타 박공 + 구리 용마루
    p.gable_roof(0, 1, 10, 10, 10, COPPER_ROOF, axis="x", overhang=1, end_overhang=0,
                 gable=mix(("orange_terracotta", 3), ("terracotta", 1), seed=44), ridge=slab(TRIM))
    # 굴뚝 (x 11..12, z 6..7) — 땅에서 지붕 위로, 구리 띠, 꼭대기 모닥불 연기
    for (x, z) in ((11, 6), (12, 6), (11, 7), (12, 7)):
        p.set(x, 0, z, B("deepslate_bricks"))
        for y in range(1, 17):
            if y in (6, 12):
                p.set(x, y, z, B("waxed_copper_block"))
            else:
                p.set(x, y, z, B("bricks") if (x + y + z) % 5 else B("mud_bricks"))
    p.set(11, 17, 6, campfire())
    p.set(12, 17, 7, campfire())
    p.set(11, 17, 7, slab("brick"))
    p.set(12, 17, 6, slab("brick"))
    p.light(11, 17, 6)
    p.ambient(11, 17, 6, "smoke")
    # 작업장 안: 용암 화덕(창살 뒤) · 용광로 · 모루 · 대장장이 작업대 · 주괴 더미 · 통
    p.set(9, 2, 9, B("lava_cauldron"))
    p.set(8, 2, 9, B("lava_cauldron"))
    p.set(9, 3, 9, bars())
    p.set(8, 3, 9, bars())
    p.set(9, 4, 9, B("chiseled_polished_blackstone"))
    p.set(8, 4, 9, B("chiseled_polished_blackstone"))
    p.light(9, 2, 9)
    p.set(9, 2, 8, B("blast_furnace", facing="west", lit=False))
    p.set(9, 2, 7, B("blast_furnace", facing="west", lit=False))
    p.ambient(8, 3, 8, "embers")
    p.set(5, 2, 6, B("anvil", facing="east"))
    p.set(6, 2, 9, B("smithing_table"))
    p.set(2, 2, 8, B("waxed_copper_block"))
    p.set(2, 2, 9, B("iron_block"))
    p.set(3, 2, 9, B("raw_iron_block"))
    p.set(2, 3, 9, B("waxed_copper_block"))
    p.set(4, 2, 9, B("raw_gold_block"))
    p.set(1, 2, 5, B("barrel", facing="up"))
    p.set(1, 2, 6, B("barrel", facing="east"))
    p.set(1, 3, 5, slab(TRIM))
    p.interact("smelter", [(9, 2, 8), (9, 2, 7), (6, 2, 9), (5, 2, 6)])
    _hang(p, 3, 5, 4)
    _cu_hang(p, 7, 5, 4)
    # 2층 살림
    p.set(2, 7, 8, B("barrel", facing="up"))
    p.set(3, 7, 9, B("chest", facing="north"))
    p.bed("orange", 8, 7, 8, "south")
    _hang(p, 5, 11, 5, chain_n=3)
    # 앞 표지판 · 깃발 · 제련공
    p.sign(6, 6, 0, ["<#ff9a5a><b>제련소</b></#ff9a5a>", "<gray>광석을 주괴로</gray>"], wood="dark_oak", facing="north", glow=True)
    p.banner(1, 5, 0, "black", [("gradient_up", "orange"), ("flower", "cyan"), ("border", "black")], facing="north")
    p.npc("smelter", 3, 2, 0, "front")
    return p


# ─────────────────────────────── 광부 숙소 ───────────────────────────────

def miners_lodge():
    """광부 숙소: 돌 아래층 + 가문비 뼈대·회반죽 다락(지붕 속 2층) + 심층암 기와 박공(앞뒤 박공, 녹슨 구리 테).
    앞 현관 벽에 광부 게시판(우클릭 mine_info)과 광산 관리소 표지판(우클릭 mine_office), 옆에 곡괭이 걸이·광석 바구니."""
    W, H, D, F = 11, 12, 9, 1
    p = Piece("miners_lodge", "광부 숙소", W, H, D, floor_y=F, anchor=(5, 1),
              foundation_mix=[("stone_bricks", 3), ("tuff_bricks", 2), ("mossy_stone_bricks", 1)])
    stone = mix(("stone_bricks", 4), ("mossy_stone_bricks", 1), ("tuff_bricks", 2), ("cracked_stone_bricks", 1), seed=51)
    plaster = mix(("white_terracotta", 4), ("light_gray_terracotta", 1), seed=52)
    frame = "spruce_log"
    glass = "light_blue_stained_glass_pane"

    p.fill(1, 0, 1, 9, 1, 8, stone)
    p.fill(2, 1, 2, 8, 1, 7, mix(("spruce_planks", 4), ("stripped_spruce_wood", 1), seed=53))
    p.fill(2, 0, 0, 8, 0, 0, stone)              # 현관 돌판
    p.fill(2, 1, 0, 8, 1, 0, mix(("polished_andesite", 2), ("stone_bricks", 1), seed=54))
    # 아래층 벽 (y 2..4): 돌 + 모서리 가문비 기둥
    for x in range(1, 10):
        for z in (1, 8):
            p.fill(x, 2, z, x, 4, z, stone)
    for z in range(1, 9):
        for x in (1, 9):
            p.fill(x, 2, z, x, 4, z, stone)
    for (x, z) in ((1, 1), (9, 1), (1, 8), (9, 8)):
        p.fill(x, 1, z, x, 4, z, log(frame))
    p.clear(2, 2, 2, 8, 4, 7)
    # 다락 바닥 (y 5) — 둘레 가로보
    for x in range(1, 10):
        p.set(x, 5, 1, log(frame, "x"))
        p.set(x, 5, 8, log(frame, "x"))
    for z in range(2, 8):
        p.set(1, 5, z, log(frame, "z"))
        p.set(9, 5, z, log(frame, "z"))
    p.fill(2, 5, 2, 8, 5, 7, B("spruce_planks"))
    for y in range(2, 6):
        p.set(8, y, 7, B("ladder", facing="north"))
    # 지붕: 용마루 z 방향 (앞뒤 박공) — 박공벽 = 가문비 뼈대 + 회반죽
    p.gable_roof(1, 1, 9, 8, 6, "deepslate_tile", axis="z", overhang=1, end_overhang=0, gable=plaster, ridge=slab(OLD_TRIM))
    for z in (1, 8):
        for y in range(6, 10):
            p.set(5, y, z, log(frame))
        p.set(3, 6, z, log(frame))
        p.set(7, 6, z, log(frame))
    p.window(4, 7, 1, "north", w=1, h=1, glass=glass)
    p.window(6, 7, 1, "north", w=1, h=1, glass=glass)
    p.window(5, 7, 8, "south", w=1, h=1, glass=glass)
    # 앞문 · 창
    p.door("spruce", 5, 2, 1, "north")
    p.set(5, 4, 1, B("chiseled_tuff_bricks"))
    p.window(3, 3, 1, "north", glass=glass)
    for z in (3, 6):
        p.window(1, 3, z, "west", glass=glass, sill=stairs("spruce", "east", "top"))
        p.window(9, 3, z, "east", glass=glass, sill=stairs("spruce", "west", "top"))
    p.window(4, 3, 8, "south", glass=glass)
    _corbel_lamp(p, 4, 3, 0, "south", mat="spruce", kind=CU_LANTERN)
    # 광부 게시판 (현관 벽, 문 오른쪽)
    p.sign(7, 3, 0, ["<#e8843f><b>광부 게시판</b></#e8843f>", "<gray>광맥 현황</gray>", "<gray>우클릭</gray>"],
           wood="dark_oak", facing="north", glow=True)
    p.interact("mine_info", [(7, 3, 0)])
    # 광산 관리소 (곡괭이·제련·새기기·벼리기·팔기) — 광부 브론 NPC 가 없어도(npcs.yml 을 고친 서버) 여기서 열린다
    p.sign(8, 3, 0, ["<#e8c58a><b>광산 관리소</b></#e8c58a>", "<gray>곡괭이 · 제련 · 팔기</gray>", "<gray>우클릭</gray>"],
           wood="dark_oak", facing="north", glow=True)
    p.interact("mine_office", [(8, 3, 0)])
    # 현관 옆: 곡괭이 걸이(다락문) · 광석 바구니(통 + 원석)
    p.set(2, 2, 0, B("barrel", facing="up"))
    p.set(2, 3, 0, B("raw_copper_block"))
    p.set(8, 2, 0, B("spruce_trapdoor", facing="north", half="bottom", open=True))
    # 안: 침대 둘, 상자, 작업대, 화로 대신 매단 등불, 다락 통
    p.bed("brown", 2, 2, 6, "south")
    p.bed("gray", 3, 2, 6, "south")
    p.set(2, 2, 2, B("crafting_table"))
    p.set(6, 2, 7, B("chest", facing="north"))
    p.set(7, 2, 2, B("barrel", facing="up"))
    p.set(7, 3, 2, lantern(hanging=False))
    p.light(7, 3, 2)
    _hang(p, 5, 4, 4)
    p.set(3, 6, 4, B("barrel", facing="up"))
    p.set(4, 6, 5, B("brown_carpet"))
    p.set(6, 6, 5, B("white_wool"))
    p.set(6, 7, 5, slab("white_wool"))
    _hang(p, 5, 8, 4, chain_n=2)
    return p


# ─────────────────────────────── 광석 하치장 (장식) ───────────────────────────────

def ore_yard():
    """광석 하치장 (장식): 다진 흙 마당 + 레일 + 원석 더미(철·구리·금) + 울타리 기중기(사슬·구리 등불) + 통 더미.
    광산 광석 블록은 쓰지 않는다 (원석 블록만)."""
    W, H, D = 9, 5, 7
    p = Piece("ore_yard", "광석 하치장", W, H, D, floor_y=0, anchor=(4, 0), deco=True, door=False,
              foundation_mix=[("stone_bricks", 3), ("tuff_bricks", 1), ("polished_andesite", 1)])
    ground = mix(("packed_mud", 3), ("coarse_dirt", 2), ("polished_andesite", 1), ("tuff", 1), seed=61)
    p.fill(0, 0, 0, 8, 0, 6, ground)
    # 레일 (동서) + 끝 멈춤 통
    for x in range(0, 8):
        p.set(x, 1, 1, B("rail", shape="east_west"))
    p.set(8, 1, 1, B("barrel", facing="west"))
    # 원석 더미
    for (x, z) in ((1, 4), (2, 4), (1, 5), (2, 5)):
        p.set(x, 1, z, B("raw_iron_block"))
    p.set(1, 2, 5, B("raw_iron_block"))
    p.set(2, 2, 5, slab("polished_andesite"))
    for (x, z) in ((5, 5), (6, 5), (6, 4)):
        p.set(x, 1, z, B("raw_copper_block"))
    p.set(6, 2, 5, B("raw_copper_block"))
    p.set(4, 1, 5, B("raw_gold_block"))
    p.set(3, 1, 3, B("barrel", facing="up"))
    # 기중기: 짙은 참나무 기둥 + 팔 + 사슬 + 구리 등불
    p.fill(8, 1, 5, 8, 3, 5, log("dark_oak"))
    p.set(8, 4, 5, fence("dark_oak"))
    p.set(8, 4, 4, fence("dark_oak"))
    p.set(7, 4, 4, fence("dark_oak"))
    p.set(7, 3, 4, chain())
    p.set(7, 2, 4, lantern(hanging=True, kind=CU_LANTERN))
    p.light(7, 2, 4)
    # 통 더미 · 숫돌
    p.set(0, 1, 6, B("barrel", facing="up"))
    p.set(1, 1, 6, B("barrel", facing="north"))
    p.set(0, 2, 6, B("barrel", facing="up"))
    p.set(4, 1, 3, B("grindstone", face="floor", facing="east"))
    _plant(p, 0, 1, 3, B("short_grass"))
    _plant(p, 8, 1, 0, B("fern"))
    return p


# ─────────────────────────────── 거리 장식 ───────────────────────────────

def lamp_post_copper():
    """구리 가로등: 응회암 받침 → 응회암 담장 → 짙은 참나무 원목 → 울타리 기둥, 앞 팔 끝에 매단 구리 등불 + 꼭대기 구리 등불
    (초록 불꽃 — 마을 등불과 달라 광산 구역임이 보인다, visual.json district_style.street)."""
    p = Piece("lamp_post_copper", "구리 가로등", 1, 6, 2, floor_y=0, anchor=(0, 1),
              foundation_mix=[("stone_bricks", 3), ("tuff_bricks", 1), ("polished_andesite", 1)])
    p.set(0, 0, 1, B("chiseled_tuff_bricks"))
    p.set(0, 1, 1, wall("tuff_brick"))
    p.set(0, 2, 1, log("dark_oak"))
    p.set(0, 3, 1, fence("dark_oak"))
    p.set(0, 4, 1, fence("dark_oak"))
    p.set(0, 4, 0, fence("dark_oak"))
    p.set(0, 3, 0, lantern(hanging=True, kind=CU_LANTERN))
    p.light(0, 3, 0)
    p.set(0, 5, 1, lantern(hanging=False, kind=CU_LANTERN))
    p.light(0, 5, 1)
    return p


# 큰길가 길잡이 (정면 = 큰길 쪽). 면 이름은 조각 정방향 기준 — 배치(정면 남)에서 left = 동, right = 서.
MINE_SIGNS = {
    "front": ["<#3fb090><b>광산 마을 →</b></#3fb090>", "<gray>승강장 · 제련소</gray>", "<gold>← 등불 광장</gold>"],
    "left": ["<gold><b>등불 광장</b></gold>", "<gray>이 길로 곧장</gray>"],
    "right": ["<#3fb090><b>광산 마을</b></#3fb090>", "<gray>이 길로 곧장</gray>"],
}


def signpost_mine():
    """광산 길잡이 (마을 큰길 끝에서 광산 마을로)."""
    p = make_signpost("signpost_mine", MINE_SIGNS, "광산 길잡이", base="chiseled_tuff_bricks",
                      foundation_mix=[("stone_bricks", 3), ("tuff_bricks", 1), ("polished_andesite", 1)])
    return p


PIECES = [mine_headframe, smelter, miners_lodge, ore_yard, lamp_post_copper, signpost_mine]
