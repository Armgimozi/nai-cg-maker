"""
mood_gothic ("촛불 아래의 고딕") 의 값 한 곳. build·art·lang·shaders·java_hook 이 읽는다.

글꼴 크기·자리는 GUI 픽셀. 마인크래프트 TTF 공급자는 FreeType 으로 size × oversample 픽셀 em 에 그려 1/oversample 로
줄여 놓는다. 바탕선은 shift 0 에서 줄 위 + 7 (바닐라 글자와 같다). oversample 4 = GUI 배율 4 에서 한 텍셀이 한 화면 픽셀.

글자색은 팔레트 이름 (pack/palette.py). 셰이더 (shaders.py) 가 바닐라가 정한 색 (흰 글, §7 회색, 꺼진 단추, 그림자) 을
이 색으로 옮기고, 플러그인이 정한 색 (아이템 이름·수치·설명) 은 사본 YAML (java_hook) 에서 바꾼다.
"""

OVERSAMPLE = 4.0

# 이름: (글꼴 열쇠, wght, 글자 묶음, 이름 표의 글꼴 이름, 숫자 바꿔 끼우기)
FILES = {
    "body_la": ("cormorant", 600, "latin", "Souls Gothic Body Latin", ".tf"),
    "body_kr": ("nanum_myeongjo_b", None, "hangul", "Souls Gothic Body KR", None),
    "title_la": ("marcellus_sc", None, "latin", "Souls Gothic Title Latin", None),
    "title_kr": ("song_myung", None, "hangul", "Souls Gothic Title KR", None),
}

# 공급자: (파일, size, shift y). 바닐라 줄 높이 9 (설명 칸 10), 바탕선 7
BODY = [("body_la", 10.5, 0.0), ("body_kr", 8.0, 0.0)]
TITLE = [("title_la", 9.5, 0.0), ("title_kr", 10.0, 0.0)]
LORE = [("body_la", 10.0, 0.0), ("body_kr", 7.5, 0.0)]

# 기본 글꼴 (minecraft:default) 개인 영역 (바닐라·기본 팩과 겹치지 않는 곳)
PUA_TITLE_LA = 0xF120         # 제목 로마자 (Marcellus SC) 를 ASCII 0x20..0x7E 순서로
PUA_TITLE_KR = 0xF200         # 제목 한글 (Song Myung): 언어 파일의 창 제목에 나오는 음절만 차례로
PUA_ORN = 0xE300              # 장식 그림 글자 (제목 밑 금실, 설명 칸 실선)
PUA_SPACE = 0xE380            # 자리 맞춤 빈칸 (수치 칸 열, 제목 밑 금실의 가운데 맞춤)

# 글꼴 이름공간 (플러그인 사본이 아이템 이름·설명에 입힌다)
FONT_TITLE = "souls:gothic_title"
FONT_LORE = "souls:gothic_lore"

# 글자색: 바닐라가 정한 색 → 팔레트
TEXT = "bone2"                # 흰 글 (단추, 화면 제목, 채팅, 개수): 뼈빛
TEXT_GREY = "parch2"          # §7 (#AAAAAA): 창 제목·사망 화면 단추·부제 → 흐린 옛 금빛
TEXT_OFF = "ash3"             # 꺼진 단추 (#A0A0A0)
TEXT_DARK = "parch0"          # §8 (#555555)
TEXT_YELLOW = "parch3"        # §e (들어옴/나감 알림) → 바랜 양피지
VIGNETTE_MIN = 0.62           # 게임 화면 비네트의 가장 옅은 세기 (바닐라는 선 자리가 어두운 만큼만)
SHADOW_ALPHA = 0.72           # 그림자 (바닐라는 글자색 × 0.25): 먹빛, 반 픽셀만 내린다

# 플러그인 사본의 아이템 설명 칸 색
NAME = "parch3"               # 아이템 이름 (제목 글꼴)
CLASS = "bronze3"             # 분류 줄 (직검 · 베기/찌르기): 흐린 옛 금빛
LABEL = "ash3"                # 수치 이름
VALUE = "bone2"               # 수치 값
LORE_INK = "parch1"           # 설명 (조용한 톤)

# 수치 칸 (GUI 픽셀): 이름 열 폭은 언어마다 lang.py 가 가장 긴 이름 + LABEL_GAP 으로 정하고, 값 열 폭 VALUE_COL
# (값은 오른쪽 맞춤), 두 칸 사이 COL_GAP
LABEL_GAP = 6.0
VALUE_COL = 18.0
COL_GAP = 14.0
