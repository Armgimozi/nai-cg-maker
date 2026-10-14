"""마을 배치 (VILLAGE.md §3) — build_all.py 가 layout.json 으로 쓴다.

임시 배치: 예제 조각 demo_hut 하나뿐. 조립 담당이 실제 마을 배치로 덮어쓴다.
마을 좌표: 중심 (0, 0), 마을의 앞(게이트)은 북쪽(−Z). at = 조각(회전 후) 발자국 가운데 칸 = (폭 // 2, 깊이 // 2).
front = 조각 정면이 바라볼 방향. 조각끼리·조각과 길은 1칸 이상 떨어져야 한다 (길 끝 근처는 예외 — 문 앞까지 이어짐).
"""

LAYOUT = {
    "format": 1,
    "name": "등불 어귀 마을",
    "radius": 32,
    "pieces": [
        {"piece": "demo_hut", "at": [0, 0], "front": "north"},
    ],
    "paths": [
        {"points": [[0, -4], [0, -12], [6, -18]], "width": 3, "style": "main"},
    ],
    "path_styles": {
        "main": [["minecraft:stone_bricks", 4], ["minecraft:cracked_stone_bricks", 1],
                 ["minecraft:polished_andesite", 2], ["minecraft:mossy_stone_bricks", 1]],
        "lane": [["minecraft:dirt_path", 6], ["minecraft:coarse_dirt", 1], ["minecraft:gravel", 1]],
    },
}
