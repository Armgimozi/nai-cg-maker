"""광산 마을(구역) 배치 — M (mine_spec §1·§2, design036/district_plan.json) + R §2-1·2-2·2-5·3-20 고침.

좌표는 배포 월드 (시드 24680, 마을 중심 (-136,16), 회전 COUNTERCLOCKWISE_90 — 게이트 서쪽, 큰길 동쪽).
마을 좌표(vx, vz) ↔ 월드: wx = cx + vz, wz = cz − vx. 큰길 끝 (-104,16).
"""

WORLD = {'seed': 24680, 'village_center': [-136, 16], 'rotation': 'COUNTERCLOCKWISE_90', 'main_road_end': [-104, 16],
         'known_builds': ['c99c3fb3-4621-4037-b7dd-26f71e3edfce (0.2.0)', 'a06800d8-7a5d-452d-b3eb-79364ebfac99 (0.3.0~0.3.5)'],
         'village_protect_max_x': -101}

# (조각 id, 이름, 크기 W×H×D (정방향), 월드 상자 [x0, z0, x1, z1], 월드 정면, 종류, 마커)
PIECES = [
    ('mine_headframe', '광산 승강장', [13, 24, 13], [-72, 9, -60, 21], 'west', 'building',
     ['interact mine_lift (승강기 칸 문·레버)', 'npc miner (앞 현관)', 'mine_exit (승강기 앞 바닥, face west)', "sign '광산 승강장'", 'ambient dust (갱구)']),
    ('smelter', '제련소', [13, 18, 12], [-88, 23, -76, 34], 'north', 'building',
     ['interact smelter (용광로·작업대)', 'npc smelter (문 옆)', 'ambient embers (화덕)', 'ambient smoke (굴뚝)', "sign '제련소'"]),
    ('miners_lodge', '광부 숙소', [11, 12, 9], [-85, 4, -75, 12], 'south', 'building',
     ["interact mine_info (게시판)", "sign '광부 게시판'"]),
    ('ore_yard', '광석 하치장', [9, 5, 7], [-68, 26, -60, 32], 'north', 'deco', []),
    ('signpost_mine', '광산 길잡이', [3, 4, 1], [-100, 12, -98, 12], 'south', 'deco', ["sign '광산 마을 →' · '← 등불 광장'"]),
    ('lamp_post_a', '가로등', [3, 6, 3], [-96, 12, -94, 14], 'south', 'deco', []),
    ('lamp_post_a', '가로등', [3, 6, 3], [-90, 18, -88, 20], 'north', 'deco', []),
    ('lamp_post_b', '가로등', [3, 6, 3], [-73, 25, -71, 27], 'north', 'deco', []),
    ('cart', '수레', [3, 3, 4], [-92, 24, -90, 27], 'north', 'deco', []),
    ('bench', '벤치', [3, 2, 1], [-72, 5, -70, 5], 'south', 'deco', []),
    ('tree_oak', '참나무', [7, 9, 7], [-97, 1, -91, 7], 'north', 'deco', []),
    ('flower_bed', '화단', [3, 2, 3], [-89, 8, -87, 10], 'north', 'deco', []),
]

PATHS = [
    {'points': [[-103, 16], [-87, 16]], 'width': 3, 'style': 'main', 'note': '마을 큰길 끝(-104,16)에 붙음'},
    {'points': [[-87, 16], [-73, 16]], 'width': 7, 'style': 'mine_yard', 'note': '광산 마당 (승강장 정문에 붙음)'},
    {'points': [[-82, 19], [-82, 22]], 'width': 3, 'style': 'mine_yard', 'note': '제련소 문 앞'},
    {'points': [[-69, 23], [-66, 25]], 'width': 2, 'style': 'lane', 'note': '하치장'},
]

NPCS = {
    'miner': {'role': 'miner', 'piece': 'mine_headframe', 'spot_east': [-74, 13], 'face': 'west'},
    'smelter': {'role': 'smelter', 'piece': 'smelter', 'spot_east': [-85, 21], 'face': 'north'},
}

SITES = [
    {'id': 'east', 'primary': True, 'shift': [0, 0], 'extra_road': [],
     'note': '마을 큰길 끝 (-104,16) 에 그대로 붙여 동쪽으로 (위 좌표)'},
    {'id': 'south_east', 'primary': False, 'shift': [0, 42], 'extra_road': [[-103, 16], [-96, 16], [-96, 50], [-87, 58]],
     'note': 'east 가 막히면: 같은 배치를 z +42 로 옮기고 큰길 끝에서 남쪽으로 길을 더 낸다 (땅 62~68, 동굴 없음)'},
    {'id': 'admin_here', 'primary': False, 'shift': None, 'extra_road': [],
     'note': '/labadmin village district build mine here [방향] — 관리자가 고른 자리 (같은 검사·계획기·백업)'},
]

MASK = {'R': 4, 'B': 6, 'note': '조각·길 상자 + R = 다듬는 칸, + B 더 = 섞는 띠. 원(반경)으로 하지 않는다 (북쪽 싱크홀)'}
