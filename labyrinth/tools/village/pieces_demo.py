"""예제 조각 — vlib 사용법 보기용 작은 오두막 (id 'demo_hut', 최종 layout 에는 쓰지 않음).

정방향: 정면(문)은 z=0 쪽, 북쪽을 본다. x 증가 = 동쪽. 바닥 층 y=1 (사람은 y=2 에 섬), y=0 은 땅속 기초.
조각 설계 파일 규칙: 모듈 끝에 PIECES = [인자 없는 함수, ...] — 각 함수는 Piece 를 돌려준다 (build_all.py 가 부름).
"""
from vlib import (Piece, mix, log, stairs, lantern, candle, flower_pot, B)


def demo_hut():
    p = Piece("demo_hut", "예제 오두막", 7, 9, 7, floor_y=1, anchor=(3, 2),
              foundation_mix=[("cobblestone", 3), ("mossy_cobblestone", 1), ("andesite", 1)])
    stone = mix(("cobblestone", 3), ("mossy_cobblestone", 1), ("andesite", 1))
    plaster = mix(("calcite", 3), ("white_terracotta", 1))

    # 기초(땅속) + 바닥: 벽 자리는 돌 띠, 안은 가문비 판자
    p.fill(1, 0, 1, 5, 0, 5, stone)
    p.fill(1, 1, 1, 5, 1, 5, stone)
    p.fill(2, 1, 2, 4, 1, 4, mix(("spruce_planks", 4), ("stripped_spruce_wood", 1)))
    p.set(3, 1, 0, B("stone_bricks"))                  # 문 앞 디딤돌
    p.clear(2, 2, 2, 4, 4, 4)                          # 실내는 반드시 '.'

    # 원목 뼈대 벽: 모서리 기둥 + 위 가로보, 사이는 회반죽
    for x0, z0, x1, z1 in ((1, 1, 5, 1), (1, 5, 5, 5), (1, 1, 1, 5), (5, 1, 5, 5)):
        p.timber_wall(x0, 2, z0, x1, 4, z1, frame="dark_oak_log", infill=plaster, post_every=4,
                      beams=False, mid_beam=4)

    # 문 (정면 가운데, 밖 = 북쪽) — 문 위 칸은 가로보가 그대로 상인방이 된다
    p.door("spruce", 3, 2, 1, "north")

    # 창: 옆벽·뒷벽에 색유리판 + 열린 다락문 덧문 + 창턱
    p.window(1, 3, 3, "west", glass="light_blue_stained_glass_pane", shutter="spruce", sill=True)
    p.window(5, 3, 3, "east", glass="light_blue_stained_glass_pane", shutter="spruce", sill=True)
    p.window(3, 3, 5, "south", glass="light_blue_stained_glass_pane", shutter="spruce", sill=True)

    # 박공 지붕: 벽 바깥 테두리 (1,1)-(5,5), 처마 줄 y=5, 용마루 x 방향 → 박공벽은 동·서
    p.gable_roof(1, 1, 5, 5, 5, "deepslate_tile", axis="x", gable=mix(("spruce_planks", 3), ("stripped_spruce_wood", 1)))

    # 굴뚝은 지붕 다음에 (지붕을 뚫고 올라감), 꼭대기 모닥불 연기
    p.chimney(4, 4, 2, 7, mix(("bricks", 3), ("mud_bricks", 1)))
    p.ambient(4, 8, 4, "smoke")

    # 처마 밑 매단 등불 두 개 + 실내 등불 (용마루 밑)
    for x in (2, 4):
        p.set(x, 4, 0, lantern(hanging=True))
        p.light(x, 4, 0)
    p.set(3, 6, 3, lantern(hanging=True))

    # 살림: 침대, 통, 화분, 촛불, 카펫
    p.bed("red", 2, 2, 3, "south")
    p.set(4, 2, 2, B("barrel", facing="up"))
    p.set(4, 3, 2, flower_pot("poppy"))
    p.set(2, 2, 2, candle("white", 3))
    p.set(3, 2, 3, B("red_carpet"))

    # 정면 장식: 표지판, 꽃
    p.sign(2, 3, 0, ["<gold>예제 오두막</gold>", "<gray>vlib 사용법</gray>"], wood="spruce", facing="north")
    p.tall_plant("rose_bush", 5, 2, 0)
    p.set(1, 2, 0, B("poppy"))

    # 마커 (예제 — 임시 layout 이 검증을 통과하도록 spawn/entrance 도 둠)
    p.spawn(3, 2, 0, "front")
    p.npc("guide", 3, 2, 2, "front")
    p.entrance(3, 2, 3, "front")
    p.interact("main", [(4, 2, 2)])
    return p


PIECES = [demo_hut]
