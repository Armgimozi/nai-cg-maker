"""
mood2_gothic ("촛불 아래의 고딕") 의 값 한 곳. build·fonts·art·lang·shaders·java_hook 이 읽는다.
글자색은 팔레트 이름 (pack/palette.py). 크기는 텍셀 (fonts.K = 4 텍셀이 GUI 한 픽셀).
"""

# ── 글꼴 역할: (글꼴 열쇠, em 텍셀, wght) 목록. 앞에서부터 그 글자를 가진 글꼴을 쓴다
BODY_LA = ("eb_garamond", 38, 600)
BODY_KR = ("noto_serif_kr", 34, 600)
TITLE_LA = ("cinzel", 39, 700)
TITLE_KR = ("nanum_myeongjo_eb", 36, None)
TITLE_TRACK = 0.5               # 제목 로마자 자간 (GUI 픽셀): 비문 대문자는 넉넉하게
BODY_SPACE = 3                  # 빈칸 진행 폭 (GUI 픽셀)
TITLE_SPACE = 4
TEXT_GAMMA = 0.86               # 덮임 ** GAMMA (1 보다 작으면 가는 획이 조금 짙게. 밝은 글을 어두운 바탕에 sRGB 로 섞으면 가늘어 보인다)

# ── 기본 글꼴 (minecraft:default) 개인 영역
PUA_TITLE_LA = 0xF120           # 제목 로마자를 ASCII 0x20..0x7E 순서로 (창 제목을 언어 파일만으로 제목 글꼴로)
PUA_TITLE_KR = 0xF200           # 제목 한글: 언어 파일의 창 제목에 나오는 음절만 차례로
PUA_ORN = 0xE300                # 장식 그림 글자 (제목 밑 금실, 설명 칸 실선)
PUA_SPACE = 0xE380              # 자리 맞춤 빈칸

FONT_TITLE = "souls:gothic_title"

# ── 글자색: 바닐라가 정한 색 → 팔레트 (셰이더)
TEXT = "bone2"                  # 흰 글 (단추, 화면 제목, 채팅, 개수)
TEXT_GREY = "parch2"            # §7 (#AAAAAA): 창 제목·부제 → 흐린 옛 금빛
TEXT_OFF = "ash3"               # 꺼진 단추 (#A0A0A0)
TEXT_DARK = "parch0"            # §8 (#555555)
TEXT_TITLE = "parch2"           # 바닐라 창 제목 (#404040)
TEXT_YELLOW = "parch3"          # §e (들어옴/나감 알림)
TEXT_HOVER = "glim0"            # 가리킨 단추 글 (#FFFFA0)

# ── 플러그인 사본의 아이템 설명 칸 색
NAME = "parch3"
CLASS = "bronze3"
LABEL = "ash3"
VALUE = "bone2"
LORE_INK = "parch1"
LABEL_GAP = 6.0
VALUE_COL = 18.0
COL_GAP = 14.0
