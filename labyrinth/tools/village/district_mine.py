"""광산 마을 배치 (0.3.6 — design/036/CONTRACT.md §2.13, tools/data/036/district.json) — build_all.py 가
plugin/src/main/resources/village/districts/mine.json 으로 쓴다.

여기 좌표는 **배포 월드 좌표**다 (시드 24680, 마을 중심 (-136, 16), 마을 회전 COUNTERCLOCKWISE_90 → 게이트 서쪽, 큰길 동쪽).
build_all 이 마을 좌표(layout.json 과 같은 틀: 중심 (0,0), 앞 = 북)로 바꿔 쓴다 — 그래서 다른 시드·방향의 마을에도
'큰길 끝에 붙여서' 같은 모양으로 놓인다. 조각 = 발자국 최소 모서리 (x0, z0) + 정면 방향, 길 = 꺾은선 + 폭 + 스타일.

자리 (sites): east = 이 좌표 그대로. south_east = 같은 배치를 z +42 로 옮기고 큰길(길 0)을 마을 큰길 끝에서 남쪽으로 돌린 길로
바꾼다 (그 길과 겹치는 장식은 뺀다). 그다음은 관리자 명령 (/labadmin village district build mine here [방향]).
"""

# 조각 (배포 월드): piece, 발자국 최소 모서리 [x0, z0], 정면, slack (계획기가 옮길 수 있는 칸 — 승강장은 계약 자리 그대로,
# 제련소·숙소는 NPC 자리가 계약 ±2 안에 남게 1, 참나무는 마을이 다듬은 칸(x ≤ −101)에 닿지 않게 2)
PIECES = [
    {"piece": "mine_headframe", "w": [-72, 9], "front": "west", "slack": 0},   # 0 승강장 (13×24×13) x -72..-60 z 9..21
    {"piece": "smelter", "w": [-88, 23], "front": "north", "slack": 1},       # 1 제련소 (13×18×12) x -88..-76 z 23..34
    {"piece": "miners_lodge", "w": [-85, 4], "front": "south", "slack": 1},   # 2 광부 숙소 (11×12×9) x -85..-75 z 4..12
    {"piece": "ore_yard", "w": [-68, 26], "front": "north"},            # 3 광석 하치장 (9×5×7) x -68..-60 z 26..32
    {"piece": "signpost_mine", "w": [-99, 11], "front": "south"},       # 4 광산 길잡이 (큰길 북쪽 길가)
    {"piece": "lamp_post_copper", "w": [-95, 11], "front": "south"},    # 5 가로등 (큰길 북쪽)
    {"piece": "lamp_post_copper", "w": [-91, 19], "front": "north"},    # 6 가로등 (큰길 남쪽)
    {"piece": "lamp_post_copper", "w": [-79, 20], "front": "north"},    # 7 가로등 (마당 남쪽, 제련소 길 옆)
    {"piece": "cart", "w": [-93, 24], "front": "north"},                # 8 수레
    {"piece": "bench", "w": [-72, 5], "front": "south"},                # 9 벤치 (승강장 북쪽)
    {"piece": "tree_oak", "w": [-98, -1], "front": "north", "slack": 2},      # 10 참나무
    {"piece": "flower_bed", "w": [-93, 9], "front": "north"},           # 11 화단
    # 0.3.6.1 놀이 리뷰: 밤에 어두운 곳 — 마당 서쪽 끝(숙소 앞)·하치장 골목에 가로등
    {"piece": "lamp_post_copper", "w": [-87, 11], "front": "south"},    # 12 가로등 (마당 서쪽 끝 북쪽)
    {"piece": "lamp_post_copper", "w": [-70, 24], "front": "west"},     # 13 가로등 (하치장 골목 동쪽)
    # south_east 자리에만 (east 는 drop) — 좌표는 z −42 해 둔 것 (그 자리가 z +42 로 옮기므로 실제 = 큰길 끝·남쪽 길가)
    # 14 갈림길 길잡이 — 꺾는 곳 안쪽(남동) 실제 x −93..−91 z 18..20. 큰길 북쪽에 두면 south_east 영역이 east 자리 북쪽(숙소 자리)까지
    #    넓어져, east 를 막은 흔적이 south_east 까지 막는다 (c-A 시험) — 그래서 남쪽에 둔다.
    {"piece": "signpost_mine_turn", "w": [-93, 18 - 42], "front": "west", "slack": 1},
    {"piece": "lamp_post_copper", "w": [-93, 24 - 42], "front": "west"},     # 15 남쪽 길 가로등 (실제 z 24)
    {"piece": "lamp_post_copper", "w": [-93, 34 - 42], "front": "west"},     # 16 (실제 z 34)
    {"piece": "lamp_post_copper", "w": [-93, 44 - 42], "front": "west"},     # 17 (실제 z 44)
]

# 길 (배포 월드)
PATHS = [
    {"points": [[-103, 16], [-87, 16]], "width": 3, "style": "main"},                  # 0 큰길 — 마을 큰길 끝(-104,16)에 붙음
    # 1 광산 마당 (승강장 정문) — follow 0: 양 끝(큰길 끝 · 승강장 바닥) 사이를 곧게 (지형을 따라 불룩 솟아 숙소 앞이 도랑이 되지 않게)
    {"points": [[-87, 16], [-73, 16]], "width": 5, "style": "mine_yard", "follow": 0},
    {"points": [[-82, 19], [-82, 22]], "width": 3, "style": "mine_yard"},              # 2 제련소 문 앞
    {"points": [[-73, 19], [-73, 27], [-69, 28]], "width": 2, "style": "mine_lane"},  # 3 하치장 골목 (흙길 + 한 칸 턱은 응회암 반블록)
    # 4 숙소 문 앞 (0.3.6.1 놀이 리뷰 — 숙소 문 앞 칸이 마당과 한 칸 차이로 이어지게: 반블록 계단). 양 끝 모두 숙소에 붙음.
    {"points": [[-80, 13], [-80, 14]], "width": 3, "style": "mine_yard"},
]

DISTRICT = {
    "format": 1,
    "id": "mine",
    "name": "광산 마을",
    # 짓는 차례 (작은 것부터 — 0.3.7 집 구역은 광산 다음)
    "order": 10,
    # 마스크: 조각·길 상자 + R = 다듬는 칸, + B 더 = 섞는 띠 (원으로 하지 않는다 — 북쪽 싱크홀)
    "mask": {"R": 4, "B": 6},
    # 계획기 손잡이 (기본 = 마을과 같음): 깎기·메우기 한도, 조각 밑 기초 깊이, 메울 수 있는 작은 물 칸 수
    "options": {"max_fill": 4, "foundation_depth": 6, "fill_small_water_max": 0},
    # 짓는 동안·지은 뒤 안전지대·경계에 더하는 여유 (상자 + 이 칸)
    "safe_margin": 8,
    # 구역 옹벽·기초 블록 (조각 foundation_mix 대신 — 마을 장식 조각의 조약돌 기초를 쓰지 않게)
    "foundation_mix": [["minecraft:stone_bricks", 4], ["minecraft:mossy_stone_bricks", 1], ["minecraft:tuff_bricks", 2],
                       ["minecraft:polished_andesite", 1]],
    "npcs": {"miner": "광부 브론", "smelter": "제련공 이그나"},
    "fingerprint": "mine.fp",
    "path_styles": {
        "mine_yard": [["minecraft:andesite", 3], ["minecraft:polished_andesite", 2], ["minecraft:tuff", 2],
                      ["minecraft:gravel", 1], ["minecraft:stone", 1]],
        # 마을 lane(흙길)과 같은 느낌 + 맨 앞 응회암 = 높이 한 칸 턱에 놓는 반블록 (흙길은 반블록이 없어 턱이 그대로 남던 것, 0.3.6.1 놀이 리뷰 #7)
        "mine_lane": [["minecraft:tuff", 1], ["minecraft:dirt_path", 5], ["minecraft:coarse_dirt", 1], ["minecraft:gravel", 1]],
    },
    # 배포 월드 (좌표 바꾸기 기준)
    "shipped": {"center": [-136, 16], "rotation": "COUNTERCLOCKWISE_90", "turns": 3, "seed": 24680,
                "build_ids": ["c99c3fb3-4621-4037-b7dd-26f71e3edfce", "a06800d8-7a5d-452d-b3eb-79364ebfac99"]},
    "pieces": PIECES,
    "paths": PATHS,
    "sites": [
        {"id": "east", "shift": [0, 0],
         # south_east 에만 쓰는 갈림길 길잡이·남쪽 길 가로등
         "drop": [14, 15, 16, 17]},
        {"id": "south_east", "shift": [0, 42],
         # 큰길을 마을 큰길 끝에서 남쪽으로 (옮기지 않은 배포 월드 좌표)
         "replace_paths": {"0": [[-103, 16], [-96, 16], [-96, 50], [-87, 58]]},
         # 돌린 큰길과 겹치는 장식 (참나무·화단·가로등 하나) + 하치장 골목 가로등 (이 자리는 골목이 짧고 하치장에 붙어 자리가 없음)
         "drop": [5, 10, 11, 13]},
    ],
}
