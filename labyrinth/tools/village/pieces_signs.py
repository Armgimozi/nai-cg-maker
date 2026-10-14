"""마을 배치에 맞춘 길잡이 표지판 변형 (조립 담당) — pieces_town.make_signpost 로 만든다.

면 이름은 조각 정방향 기준(front = 마을 북쪽 = 게이트 쪽, left = 서, right = 동, back = 남)이고 마을을 회전하면 같이 돈다.
마을이 실제로 어느 방위로 지어질지는 시드·지형(survey)이 정하므로 글에는 동서남북 대신 '광장 왼편/오른편'을 쓴다
(광장에서 게이트를 바라볼 때의 왼쪽·오른쪽 — layout.py 배치 기준: 왼편 = 전당·상점, 오른편 = 보관소·대장간).
"""
from pieces_town import make_signpost

# 남쪽 어귀(큰길 끝) — 마을로 들어오는 사람이 처음 보는 판
ROAD_SIGNS = {
    "front": ["<gold><b>등불 광장</b></gold>", "<light_purple>미궁의 아가리</light_purple>", "<gray>이 길로 곧장</gray>"],
    "left": ["<aqua>전직의 전당</aqua>", "<yellow>떠돌이 상점</yellow>", "<gray>광장 왼편</gray>"],
    "right": ["<#c9a0ff>기록 보관소</#c9a0ff>", "<#ff9a4d>두르간의 대장간</#ff9a4d>", "<gray>광장 오른편</gray>"],
    "back": ["<gold><b>등불 어귀 마을</b></gold>", "<gray>미궁 라비린스</gray>", "<gray>입구 마을</gray>"],
}


def signpost_road():
    """남쪽 어귀 표지판 (큰길 끝 동쪽 길가)."""
    return make_signpost("signpost_road", ROAD_SIGNS, "어귀 길잡이 표지판")


PIECES = [signpost_road]
