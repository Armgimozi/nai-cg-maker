"""마을 배치 (VILLAGE.md §3·§5) — build_all.py 가 layout.json 으로 쓴다.

마을 좌표: 중심 (0, 0) = 광장 가운데, 마을의 앞(게이트)은 북쪽(−Z). at = 조각(회전 후) 발자국 가운데 칸 = 최소 모서리 + (폭 // 2, 깊이 // 2).
front = 조각 정면이 바라볼 방향. 조각끼리·조각과 길은 1칸 이상 떨어진다 (길 끝 2칸 안 조각만 붙은 길 — 문 앞까지 이어짐).
여기 좌표는 기준점이다: 짓는 쪽(Java Planner)이 조각마다 slack 칸 안에서 지형에 맞게 옮기고 단 높이를 원래 땅에 맞춘다(§0).
그래서 큰 건물 사이는 2~4칸, 장식은 건물·길에서 1칸 넘게 띄워 옮길 자리를 남겼다.

구성 — 언덕 쪽(북)에 게이트, 가운데 광장, 둘레에 전당·보관소·대장간·상점, 바깥에 여관·집:
  북: 미궁의 아가리 (광장보다 2칸 높은 단 — 길이 반블록 계단으로 오른다), 그 앞을 가로지르는 골목 양끝에 집·여관
  서: 전직의 전당 (광장 서쪽 입구를 본다)        동: 기록 보관소 (광장 동쪽 입구를 본다)
  남: 마을 밖으로 나가는 큰길, 양옆에 떠돌이 상점(서)·대장간(동), 그 바깥 모퉁이에 집 두 채, 큰길 끝에 우물·길잡이 표지판
"""
def P(piece, x, z, front="north", **kw):
    e = {"piece": piece, "at": [x, z], "front": front}
    e.update(kw)
    return e


LAYOUT = {
    "format": 1,
    "name": "등불 어귀 마을",
    "radius": 33,
    "blend": 16,
    "pieces": [
        # ── 가운데 (먼저 놓을수록 slack 자리를 먼저 고른다: 큰 것부터)
        P("plaza", 0, 0),
        P("labyrinth_gate", 0, -23, "south", dy=2),
        P("class_hall", -22, 0, "east"),
        P("archive", 21, 0, "west"),
        P("market", -10, 19, "east"),
        P("forge", 10, 19, "west"),
        # ── 바깥
        P("inn", 15, -14, "west"),
        P("house_a", -15, -15, "east"),
        P("house_b", 23, 13, "south"),
        P("house_c", -22, 14, "south"),
        # ── 장식 (slack 3 — 지형 따라 더 많이 옮겨진다)
        P("signpost_road", 4, 29),
        P("well", -5, 29),
        P("cart", -11, 29),
        P("tree_oak", -25, -15),
        P("tree_cherry", -16, -25),
        P("tree_cherry", 25, -16),
        P("tree_cherry", 20, 22),
        P("flower_bed", -14, -7),
        P("flower_bed", 15, -24),
        P("flower_bed", -20, 22),
        P("lamp_post_a", -3, 22),
        P("lamp_post_a", 3, 21),
        P("lamp_post_b", -5, -12),
        P("bench", 6, -12),
    ],
    "paths": [
        # 큰길: 광장 네 입구에서 게이트·전당·보관소, 그리고 마을 밖으로
        {"points": [[0, -10], [0, -17]], "width": 3, "style": "main"},
        {"points": [[-10, 0], [-15, 0]], "width": 3, "style": "main"},
        {"points": [[10, 0], [14, 0]], "width": 3, "style": "main"},
        {"points": [[0, 10], [0, 31]], "width": 3, "style": "main"},
        # 골목: 게이트 앞을 가로질러 집·여관으로, 큰길에서 상점·대장간 문 앞으로
        {"points": [[-10, -14], [-2, -14]], "width": 2, "style": "lane"},
        {"points": [[9, -14], [2, -14]], "width": 2, "style": "lane"},
        {"points": [[-5, 18], [-2, 18]], "width": 2, "style": "lane"},
        {"points": [[4, 15], [2, 15]], "width": 2, "style": "lane"},
    ],
    "path_styles": {
        "main": [["minecraft:stone_bricks", 4], ["minecraft:cracked_stone_bricks", 1],
                 ["minecraft:polished_andesite", 2], ["minecraft:mossy_stone_bricks", 1]],
        "lane": [["minecraft:dirt_path", 6], ["minecraft:coarse_dirt", 1], ["minecraft:gravel", 1]],
    },
}
