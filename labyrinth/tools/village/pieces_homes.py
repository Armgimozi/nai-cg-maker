"""집 구역 '등불 골목' 조각 (0.3.7 — design/037/PLAN.md §1·§2, review R1·R10).

집터 바닥 · 앞 울타리(대문·문패 기둥) · 생울타리 줄 · 모서리 기둥·등불 · 관리인 노점 · 골목 길잡이 · 골목 우물.
벤치·화단은 마을 조각(pieces_town)을 그대로 쓴다. 정방향: 정면은 z=0 쪽, 북쪽을 본다 (VILLAGE.md §2).
실제 자리·방향은 district_homes.py 가 정한다.

abut 조각 (집터·울타리 줄·모서리·노점·길잡이): 다른 abut 조각·길에 1칸 여유 없이 붙는다 (겹침만 안 됨). 보호 상자는 발자국 그대로라
집터 14×14 안은 보호 상자가 아니다. 울타리 줄은 바닥 층(floor_y)에 잔디, 그 위에 울타리·잎 — 옆 집터보다 높으면 그 아래는 계획기가
옹벽(구역 foundation_mix: 돌벽돌·이끼 돌벽돌)으로 채운다 (review R10).

지킬 것 (build_all 이 검사): 광산 광석·보석 블록 12종과 빈 광맥 블록(조약돌·이끼 낀 조약돌·조약돌 심층암·흑암)은 쓰지 않는다.
"""
from vlib import Piece, mix, slab, log, fence, fence_gate, leaves, lantern, trapdoor, flower_pot, B
from pieces_town import _hang, _trim, _gable_edges, _ring_box

HEDGE = mix((leaves("azalea"), 3), (leaves("flowering_azalea"), 1), seed=371)
FOUND = [("stone_bricks", 3), ("mossy_stone_bricks", 1)]   # 조각 기초 (구역은 조약돌을 쓰지 않음 — 실제 옹벽은 구역 foundation_mix)
POST_WOOD = "spruce"
SIZE = 14                 # 집터 한 변
BELOW = 8                 # 바닥 아래 정리 깊이 (흙 3 + 돌 5)
ABOVE = 24                # 바닥 위 비우는 높이 (짓기 높이 창 위 끝)

# 대문·문패 자리 (집터 서쪽 끝에서 +6 · +8 — 설계 그대로). 남쪽을 보는 집(180° 돌림)은 x 가 뒤집혀 6/8 → 7/5.
GATE_X, SIGN_X, LAMP_X = 6, 8, 5


def plot_pad():
    """집터 바닥 14×14: 바닥 아래 8칸을 통째로 (−8..−4 돌 · −3..−1 흙 · 바닥 잔디) — 동굴·물·광석이 지하실에 나오지 않게,
    바닥 위 24칸은 비움 (나무·흙 덩어리 없이). 보호 상자 없음 (주인이 짓는 칸). 마을이 다듬은 칸은 겉 그대로 (계획기가 높이를 맞춤)."""
    H = BELOW + 1 + ABOVE
    p = Piece("plot_pad", "집터 바닥", SIZE, H, SIZE, floor_y=BELOW, anchor=(SIZE // 2, SIZE // 2), door=False, deco=False,
              slack=0, abut=True, pad=True, foundation_mix=[("stone", 1)])
    # 돌만 (묶음 B 비우기 틀 PlotResetPlan.template 와 같게 — 비운 뒤에도 구역 지우기가 '우리가 놓은 칸' 으로 알아봄)
    p.fill(0, 0, 0, SIZE - 1, BELOW - 4, SIZE - 1, B("stone"))
    p.fill(0, BELOW - 3, 0, SIZE - 1, BELOW - 1, SIZE - 1, B("dirt"))
    p.fill(0, BELOW, 0, SIZE - 1, BELOW, SIZE - 1, B("grass_block", snowy=False))
    p.clear(0, BELOW + 1, 0, SIZE - 1, H - 1, SIZE - 1)
    return p


def _plot_front(pid, gate_x, sign_x, lamp_x):
    """앞 울타리 줄 14칸: 가문비 울타리 + 울타리 문(대문, 정면 = 거리) + 문패 기둥(울타리 + 밀랍칠 표지판) + 대문 옆 기둥 등불.
    표지판 글·우클릭은 {plot} 자리에 집터 번호 (계획기가 layout tag 로 바꿈). 양 끝 울타리는 모서리 기둥 쪽으로 이어 둔다."""
    p = Piece(pid, "앞 울타리", SIZE, 3, 1, floor_y=0, anchor=(gate_x, 0), door=True, deco=False, slack=0, abut=True,
              foundation_mix=FOUND)
    for x in range(SIZE):
        p.set(x, 0, 0, B("dirt_path") if x == gate_x else B("grass_block", snowy=False))
        if x == gate_x:
            p.set(x, 1, 0, fence_gate(POST_WOOD, "north"))
        elif x in (0, SIZE - 1):
            # 모서리 기둥(다른 조각)과 이어지게 바깥쪽 연결을 직접 적는다 (finalize 는 조각 안만 본다)
            p.set(x, 1, 0, B(POST_WOOD + "_fence", north=False, south=False, east=True, west=True, waterlogged=False))
        else:
            p.set(x, 1, 0, fence(POST_WOOD))
    p.sign(sign_x, 2, 0, ["<b>[{plot}번지]</b>", "비어 있음", "", "<gray>/미궁 집</gray>"], wood=POST_WOOD, facing="north", wall=False,
           glow=True)
    p.interact("plot:{plot}", [(sign_x, 2, 0), (sign_x, 1, 0)])
    p.set(lamp_x, 2, 0, lantern(hanging=False))
    p.light(lamp_x, 2, 0)
    return p


def plot_front():
    """앞 울타리 (북쪽 거리를 보는 집 — 돌리지 않음: 대문 x+6, 문패 x+8)."""
    return _plot_front("plot_front", GATE_X, SIGN_X, LAMP_X)


def plot_front_m():
    """앞 울타리 (남쪽 거리를 보는 집 — 180° 돌려 놓으면 대문이 다시 서쪽 끝 +6, 문패 +8)."""
    return _plot_front("plot_front_m", SIZE - 1 - GATE_X, SIZE - 1 - SIGN_X, SIZE - 1 - LAMP_X)


def plot_hedge():
    """생울타리 줄 14칸 (집터 옆·뒤): 바닥 층 잔디 + 지속 진달래 잎 한 칸. 이웃 집터가 낮으면 그 아래는 옹벽 (계획기)."""
    p = Piece("plot_hedge", "생울타리", SIZE, 2, 1, floor_y=0, anchor=(SIZE // 2, 0), door=False, deco=False, slack=0, abut=True,
              foundation_mix=FOUND)
    for x in range(SIZE):
        p.set(x, 0, 0, B("grass_block", snowy=False))
        p.set(x, 1, 0, HEDGE)
    return p


def hedge_post():
    """생울타리 모서리 한 칸."""
    p = Piece("hedge_post", "생울타리 모서리", 1, 2, 1, floor_y=0, anchor=(0, 0), door=False, deco=False, slack=0, abut=True,
              foundation_mix=FOUND)
    p.set(0, 0, 0, B("grass_block", snowy=False))
    p.set(0, 1, 0, leaves("azalea"))
    return p


def _fence_props(east, west):
    return dict(north=False, south=False, east=bool(east), west=bool(west), waterlogged=False)


def _fence_post(pid, east, west):
    p = Piece(pid, "울타리 모서리 기둥", 1, 2, 1, floor_y=0, anchor=(0, 0), door=False, deco=False, slack=0, abut=True,
              foundation_mix=FOUND)
    p.set(0, 0, 0, B("grass_block", snowy=False))
    p.set(0, 1, 0, B(POST_WOOD + "_fence", **_fence_props(east, west)))
    return p


def fence_post_e():
    """앞 울타리 줄 서쪽 끝 기둥 (동쪽으로 이어짐)."""
    return _fence_post("fence_post_e", True, False)


def fence_post_w():
    """앞 울타리 줄 동쪽 끝 기둥 (서쪽으로 이어짐)."""
    return _fence_post("fence_post_w", False, True)


def _lamp(pid, east, west, name="울타리 등불"):
    """울타리 등불 (1칸): 깎은 돌벽돌 받침 → 가문비 울타리 두 칸 → 등불. 앞 울타리 줄 모서리면 양옆으로 이어진다."""
    p = Piece(pid, name, 1, 4, 1, floor_y=0, anchor=(0, 0), door=False, deco=True, slack=0, abut=True,
              foundation_mix=[("stone_bricks", 3), ("mossy_stone_bricks", 1)])
    p.set(0, 0, 0, B("chiseled_stone_bricks"))
    p.set(0, 1, 0, B(POST_WOOD + "_fence", **_fence_props(east, west)))
    p.set(0, 2, 0, B(POST_WOOD + "_fence", **_fence_props(False, False)))
    p.set(0, 3, 0, lantern(hanging=False))
    p.light(0, 3, 0)
    return p


def lamp_post_small():
    """등불 기둥 (1칸, 이어지지 않음 — 골목 마당)."""
    return _lamp("lamp_post_small", False, False, "작은 등불 기둥")


def lamp_post_small_e():
    return _lamp("lamp_post_small_e", True, False)


def lamp_post_small_w():
    return _lamp("lamp_post_small_w", False, True)


def lamp_post_small_ew():
    return _lamp("lamp_post_small_ew", True, True)


def keeper_stall():
    """마을 관리인 노점 (3×3): 가문비 바닥·네 기둥, 앞 계산대(우클릭 = 관리인 메뉴 estate), 뒤 통·꽃 화분, 빨강·흰 줄무늬 차양,
    지붕 등불. 관리인 모아는 계산대 뒤에서 거리(정면)를 본다. npcs.yml 에 정의가 없어도 계산대가 같은 메뉴를 연다 (R20)."""
    p = Piece("keeper_stall", "관리인 노점", 3, 5, 3, floor_y=0, anchor=(1, 1), door=False, deco=False, slack=0, abut=True,
              foundation_mix=[("stone_bricks", 3), ("mossy_stone_bricks", 1)])
    p.fill(0, 0, 0, 2, 0, 2, B("spruce_planks"))
    for (x, z) in ((0, 0), (2, 0), (0, 2), (2, 2)):
        p.fill(x, 1, z, x, 2, z, log("stripped_spruce"))
    p.set(1, 1, 0, slab("spruce", "top"))
    p.set(1, 2, 0, ".")
    p.set(0, 1, 1, trapdoor("spruce", "west", open=True))
    p.set(2, 1, 1, trapdoor("spruce", "east", open=True))
    p.set(0, 2, 1, ".")
    p.set(2, 2, 1, ".")
    p.set(1, 1, 2, B("barrel", facing="north"))
    p.set(1, 2, 2, flower_pot("flowering_azalea_bush"))
    p.clear(1, 1, 1, 1, 2, 1)
    for x in range(3):
        for z in range(3):
            p.set(x, 3, z, B("red_wool") if (x + z) % 2 == 0 else B("white_wool"))
    p.set(1, 4, 1, lantern(hanging=False))
    p.light(1, 4, 1)
    p.npc("estate_keeper", 1, 1, 1, "front")
    p.interact("estate", [(1, 1, 0), (1, 1, 2)])
    return p


def signpost_home():
    """골목 어귀 길잡이 (1칸): 이끼 돌벽돌 받침 → 벗긴 가문비 기둥 → 서 있는 표지판 (정면 = 큰길에서 오는 쪽)."""
    p = Piece("signpost_home", "등불 골목 길잡이", 1, 3, 1, floor_y=0, anchor=(0, 0), door=False, deco=True, slack=0, abut=True,
              foundation_mix=[("stone_bricks", 3), ("mossy_stone_bricks", 1)])
    p.set(0, 0, 0, B("mossy_stone_bricks"))
    p.set(0, 1, 0, log("stripped_spruce"))
    p.sign(0, 2, 0, ["<#ffd36b><b>등불 골목</b></#ffd36b>", "집 1~10번지", "마을 관리인", "<gray>이 골목으로</gray>"], wood="spruce",
           facing="north", wall=False, glow=True)
    return p


def well_home():
    """골목 우물: 마을 우물과 같은 모양 (땅속 돌 통 안 물, 두 기둥·가로대에 매단 등불, 가문비 박공 지붕) — 조약돌 대신 돌벽돌·안산암
    (구역 조각은 빈 광맥 블록을 쓰지 않음)."""
    p = Piece("well_home", "골목 우물", 5, 10, 5, floor_y=2, anchor=(2, 1), deco=True, slack=0,
              foundation_mix=[("stone_bricks", 3), ("mossy_stone_bricks", 2)])
    rim = mix(("stone_bricks", 3), ("mossy_stone_bricks", 2), seed=373)
    p.fill(1, 0, 1, 3, 1, 3, rim)
    p.set(2, 1, 2, B("water", level=0))
    for (x, z) in _ring_box(1, 1, 3, 3):
        p.set(x, 2, z, rim)
    p.set(2, 2, 2, ".")
    for (x, z) in ((0, 1), (0, 2), (0, 3), (4, 1), (4, 2), (4, 3), (1, 0), (2, 0), (3, 0), (1, 4), (2, 4), (3, 4)):
        p.set(x, 2, z, mix(("polished_andesite", 2), ("stone_bricks", 1), ("cracked_stone_bricks", 1), seed=374))
    for (x, z) in ((1, 1), (3, 1), (1, 3), (3, 3)):
        p.set(x, 3, z, B("mossy_stone_bricks"))
    for (x, z) in ((2, 1), (2, 3)):
        p.set(x, 3, z, slab("stone_brick"))
    p.clear(2, 3, 2, 2, 3, 2)
    for x in (1, 3):
        p.fill(x, 3, 2, x, 7, 2, log("spruce"))
    p.set(2, 7, 2, log("spruce", "x"))
    _hang(p, 2, 4, 2, chain_n=2)
    p.gable_roof(1, 1, 3, 3, 7, "spruce", axis="x", overhang=1, end_overhang=1, under="stairs", ridge="slab")
    _trim(p, _gable_edges("x", 1, 1, 3, 3, 7), {"spruce_stairs": "dark_oak_stairs", "spruce_slab": "dark_oak_slab"},
          {"spruce_stairs": "dark_oak_stairs", "spruce_slab": "dark_oak_slab"})
    p.set(3, 4, 3, flower_pot("fern"))
    p.set(1, 4, 1, flower_pot("blue_orchid"))
    return p


PIECES = [plot_pad, plot_front, plot_front_m, plot_hedge, hedge_post, fence_post_e, fence_post_w, lamp_post_small,
          lamp_post_small_e, lamp_post_small_w, lamp_post_small_ew, keeper_stall, signpost_home, well_home]
