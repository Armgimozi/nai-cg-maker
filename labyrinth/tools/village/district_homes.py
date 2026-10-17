"""집 구역 '등불 골목' 배치 (0.3.7 — design/037/PLAN.md §1, plots10_spec.json) — build_all.py 가
plugin/src/main/resources/village/districts/homes.json 으로 쓴다.

여기 좌표는 **배포 월드 좌표**다 (시드 24680, 마을 중심 (-136, 16), 마을 회전 COUNTERCLOCKWISE_90). build_all 이 마을 좌표로 바꿔
쓴다 (district_mine.py 와 같은 틀). 조각 = 발자국 최소 모서리 (x0, z0) + 정면 방향, 길 = 꺾은선 + 폭 + 스타일.

- 집 10채 (14×14, 옛 3번·옛 9번을 뺀 10채 — 1..10 다시 번호). 조각 순서: 집터 바닥 10 → 앞 울타리 10 → 생울타리 줄 → 모서리 → 장식.
- 조각 손잡이 (0.3.7): max_fill = 그 조각 깎기·메우기 한도 (집터 12 — 구덩이 메움), floor_ref = 그 조각들(집터) 바닥 가운데 가장 높은 것을
  바닥으로 (울타리 줄 — 낮은 쪽 집터 앞은 옹벽, review R10), floor_near = [조각, 차] 그 조각 바닥에서 차 안 (거리 건너 마주 보는 집 —
  두 대문이 같은 거리 높이에서 한 칸 안), tag = 집터 번호 (표지판 글·우클릭 plot:<번지>·구역 기록 plots:).
- 길: 0 이음 칸+골목 (마을 길 1 첫 칸 (-137, 26..27) 에 붙음 — 길 0 첫 점이 here 기준) · 1 등불길 · 2 우물길 · 3·4 가운데 골목.
  거리는 땅을 따라가고(follow 8) 대문 앞 칸에서 그 집 바닥 ±1 (계획기 — abut 문 조각).
"""

# 집터 (설계 plots10_spec.json): 번호 → (x0, z0, x1, z1, 앞)
PLOTS = {
    1: (-178, 48, -165, 61, "S"), 2: (-163, 48, -150, 61, "S"), 3: (-129, 48, -116, 61, "S"),
    4: (-178, 69, -165, 82, "N"), 5: (-163, 69, -150, 82, "N"), 6: (-144, 69, -131, 82, "N"), 7: (-129, 69, -116, 82, "N"),
    8: (-163, 84, -150, 97, "S"), 9: (-144, 84, -131, 97, "S"), 10: (-129, 84, -116, 97, "S"),
}
# 거리 건너 마주 보는 집 (뒤 집 → 앞 집, 바닥 차 ≤ 2 — 대문 둘이 같은 거리 칸에서 한 칸 안)
FACING = {4: 1, 5: 2, 7: 3}
# 설계 울타리 등불 자리 (앞 울타리 줄 모서리)
LAMPS = {(-164, 62), (-149, 62), (-130, 62), (-164, 68), (-145, 68), (-130, 68), (-164, 98), (-149, 98), (-130, 98)}
FILL = 12                  # 집터·울타리 줄 깎기·메우기 한도 (8번 싱크홀 11칸)


def _front_z(p):
    x0, z0, x1, z1, f = p
    return z1 + 1 if f == "S" else z0 - 1


def _pieces():
    pads = {}
    out = []
    for n, p in PLOTS.items():
        x0, z0, x1, z1, f = p
        e = {"piece": "plot_pad", "w": [x0, z0], "front": "north", "slack": 0, "max_fill": FILL, "tag": str(n)}
        pads[n] = len(out)
        out.append(e)
    for n, back in FACING.items():
        out[pads[n]]["floor_near"] = [pads[back], 2]
    fronts = {}
    for n, p in PLOTS.items():
        x0, z0, x1, z1, f = p
        fz = _front_z(p)
        fronts[(n)] = fz
        out.append({"piece": "plot_front_m" if f == "S" else "plot_front", "w": [x0, fz], "front": "south" if f == "S" else "north",
                    "slack": 0, "max_fill": FILL, "floor_ref": [pads[n]], "tag": str(n)})
    front_cells = set()
    for n, p in PLOTS.items():
        for x in range(p[0], p[2] + 1):
            front_cells.add((x, _front_z(p)))
    pad_cells = {}
    for n, p in PLOTS.items():
        for x in range(p[0], p[2] + 1):
            for z in range(p[1], p[3] + 1):
                pad_cells[(x, z)] = n

    def refs(cells):
        """칸들에 (8방향으로) 닿은 집터 조각 순번."""
        s = set()
        for (x, z) in cells:
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = pad_cells.get((x + dx, z + dz))
                    if n is not None:
                        s.add(pads[n])
        return sorted(s)

    used = set(front_cells)
    # 생울타리 줄 (옆·뒤 — 앞 울타리 줄이 아닌 쪽, 같은 줄은 한 번만)
    for n, p in PLOTS.items():
        x0, z0, x1, z1, f = p
        sides = [("v", x0 - 1, z0), ("v", x1 + 1, z0)]
        sides.append(("h", x0, z0 - 1) if f == "S" else ("h", x0, z1 + 1))
        for kind, sx, sz in sides:
            cells = [(sx, sz + i) for i in range(14)] if kind == "v" else [(sx + i, sz) for i in range(14)]
            if any(c in used for c in cells):
                continue
            used.update(cells)
            out.append({"piece": "plot_hedge", "w": [sx, sz], "front": "east" if kind == "v" else "north", "slack": 0, "max_fill": FILL,
                        "floor_ref": refs(cells)})
    # 모서리
    corners = set()
    for n, p in PLOTS.items():
        x0, z0, x1, z1, f = p
        for c in ((x0 - 1, z0 - 1), (x1 + 1, z0 - 1), (x0 - 1, z1 + 1), (x1 + 1, z1 + 1)):
            corners.add(c)
    for (x, z) in sorted(corners, key=lambda c: (c[1], c[0])):
        if (x, z) in used:
            continue
        used.add((x, z))
        east, west = (x + 1, z) in front_cells, (x - 1, z) in front_cells
        if (x, z) in LAMPS:
            piece = "lamp_post_small_" + ("ew" if east and west else "e" if east else "w")
        elif east or west:
            piece = "fence_post_" + ("e" if east else "w")
        else:
            piece = "hedge_post"
        out.append({"piece": piece, "w": [x, z], "front": "north", "slack": 0, "max_fill": FILL, "floor_ref": refs([(x, z)])})
    # 장식 (거리·골목 옆 — abut 이 아닌 것은 길과 한 칸 띄움)
    out += [
        {"piece": "keeper_stall", "w": [-145, 60], "front": "south", "slack": 0},      # 관리인 노점 (등불길 북쪽 길가, 골목 동쪽)
        {"piece": "signpost_home", "w": [-146, 26], "front": "east", "slack": 0},      # 골목 어귀 길잡이 (큰길에서 오는 쪽을 봄)
        {"piece": "well_home", "w": [-149, 105], "front": "north", "slack": 1},        # 골목 끝 우물 (우물길 남쪽)
        {"piece": "bench", "w": [-143, 105], "front": "north", "slack": 1},            # 우물 옆 벤치
        {"piece": "bench", "w": [-141, 58], "front": "south", "slack": 1},             # 골목 마당 (옛 3번 자리 — 땅 그대로)
        {"piece": "flower_bed", "w": [-136, 53], "front": "north", "slack": 1},
        {"piece": "lamp_post_small", "w": [-133, 60], "front": "north", "slack": 0},
    ]
    return out


PIECES = _pieces()

# 길 (배포 월드)
PATHS = [
    # 0 이음 칸 + 골목 (폭 2 — 짝수 폭은 점이 칸 모서리): 마을 길 1 첫 칸 (-137, 26..27) 옆에서 서쪽, 집A·화단 사이로 남쪽 받는 칸까지
    {"points": [[-138, 27], [-144, 27], [-144, 47]], "width": 2, "style": "home_lane"},
    # 1 등불길 (폭 5, z 63..67) — 1~7번 대문
    {"points": [[-177, 65], [-117, 65]], "width": 5, "style": "home_street", "follow": 8},
    # 2 우물길 (폭 5, z 99..103) — 8~10번 대문
    {"points": [[-162, 101], [-117, 101]], "width": 5, "style": "home_street", "follow": 8},
    # 3 가운데 골목 북쪽 (폭 3, x -148..-146): 받는 칸 → 등불길
    {"points": [[-147, 47], [-147, 63]], "width": 3, "style": "home_lane"},
    # 4 가운데 골목 남쪽: 등불길 → 우물길
    {"points": [[-147, 67], [-147, 99]], "width": 3, "style": "home_lane"},
]

DISTRICT = {
    "format": 1,
    "id": "homes",
    "name": "집 구역",
    # 짓는 차례 (광산 10 다음)
    "order": 20,
    # 마스크: 조각·길 + R 2 = 다듬는 칸, + B 4 더 = 섞는 띠
    "mask": {"R": 1, "B": 2},
    # 깎기·메우기 한도 4 (조각별 max_fill 이 덮음 — 집터·울타리 줄 12), 집터 밑 기초 깊이 8, 메울 수 있는 닫힌 작은 물 8칸 (우물길 2×2)
    "options": {"max_fill": 4, "foundation_depth": 8, "fill_small_water_max": 8},
    "safe_margin": 8,
    # 옹벽·기초 (단 사이 벽 — 돌벽돌 + 이끼 돌벽돌, review R10)
    "foundation_mix": [["minecraft:stone_bricks", 4], ["minecraft:mossy_stone_bricks", 2], ["minecraft:cracked_stone_bricks", 1]],
    "npcs": {"estate_keeper": "마을 관리인 모아"},
    "fingerprint": "homes.fp",
    "path_styles": {
        "home_street": [["minecraft:stone_bricks", 3], ["minecraft:polished_andesite", 2], ["minecraft:mossy_stone_bricks", 1],
                        ["minecraft:polished_tuff", 1]],
        # 맨 앞 진흙 벽돌 = 한 칸 턱에 놓는 반블록 (흙길은 반블록이 없음)
        "home_lane": [["minecraft:mud_bricks", 1], ["minecraft:dirt_path", 6], ["minecraft:coarse_dirt", 1], ["minecraft:packed_mud", 1]],
    },
    "shipped": {"center": [-136, 16], "rotation": "COUNTERCLOCKWISE_90", "turns": 3, "seed": 24680,
                "build_ids": ["c99c3fb3-4621-4037-b7dd-26f71e3edfce", "a06800d8-7a5d-452d-b3eb-79364ebfac99"]},
    "pieces": PIECES,
    "paths": PATHS,
    "sites": [
        {"id": "south_west", "shift": [0, 0]},
    ],
}
