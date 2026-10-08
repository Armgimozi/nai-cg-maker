"""
mood2_refined 의 공통 값 (글꼴 크기, 글자색, 선의 색, 해상도). 다른 모듈은 여기서만 읽는다.

시각 언어 (방향: 정제된 명조. 조용하고 우아하게, 낡은 금빛 머리카락 선과 작은 덩굴 끝 장식)
  - 바탕은 반투명 먹 (흐린 세상이 비친다). 테는 "두 겹 머리카락 선": 바깥 1 GUI 픽셀 안쪽에 금빛 가는 선 (GUI 배율 4 에서 1 화면
    픽셀), 그 안쪽 1.25 GUI 픽셀에 더 흐린 둘째 선. 긴 선은 탁하게, 밝은 금빛은 끝 장식에만.
  - 끝 장식은 작은 마름모 + 양옆으로 짧게 뻗는 덩굴 (filigree). 같은 꼴을 크기만 바꿔 막대 마구리·창 귀·단추 끝·실선 가운데에
    쓴다 (한 무늬를 찍어 늘어놓지 않는다: 자리마다 한 번).
  - 글은 명조 (본문 Noto Serif KR · EB Garamond, 제목 Cinzel · 굵은 명조), 뼈빛·바랜 양피지빛.
  - 그림은 GUI 픽셀당 4 텍셀 (RES). 셰이더가 화면 픽셀마다 면적 평균을 내므로 배율 4 에서 1:1, 2 에서 정확히 2×2 평균, 3 에서
    면적 평균. 머리카락 선은 GUI 픽셀의 첫 텍셀이나 마지막 텍셀에 둔다 (배율 3 에서도 한 화면 픽셀에 들어가 고르게 보인다).
"""
RES = 4                     # 그림 해상도: GUI 픽셀당 텍셀
OVERSAMPLE = 12.0           # TTF 를 GUI 픽셀당 12 화면 텍셀로 그린다 (2·3·4·6 배율 모두 정수 텍셀 = 정확한 면적 평균)

# 글꼴 파일: 이름 → (원본 열쇠, wght, 글자 묶음, 이름 표의 글꼴 이름, 굵기 이름)
FILES = {
    "body_la": ("eb_garamond", 500, "latin", "Souls Refined Serif Latin", "Medium"),
    "body_kr": ("noto_serif_kr", 500, "hangul", "Souls Refined Serif KR", "Medium"),
    "title_la": ("cinzel", 600, "latin", "Souls Refined Title Latin", "SemiBold"),
    "title_kr": ("noto_serif_kr", 700, "hangul", "Souls Refined Title KR", "Bold"),
}
# 공급자 (파일, size, shift y). 바탕선 = 줄 위 + 7 (+ shift). size × 12 은 정수 (FreeType 픽셀 크기)
BODY = [("body_la", 10.0, 0.0), ("body_kr", 8.5, 0.0)]
TITLE = [("title_la", 10.0, 0.0), ("title_kr", 9.0, 0.0)]
SPACE = 3                   # 낱말 사이 (바닐라 4)

PUA_TITLE_LA = 0xF120       # ASCII → Cinzel (영어 창 제목)
PUA_TITLE_KR = 0xF200       # 창 제목의 한글 → 굵은 명조

# 글자색 (셰이더가 바닐라 색을 바꾼다)
TEXT = "bone2"              # 흰 글 (단추, 채팅, 설명 칸, 개수)
TEXT_GREY = "parch2"        # §7
TEXT_TITLE = "parch3"       # 창 제목 (바닐라 0x404040)
TEXT_OFF = "ash3"           # 꺼진 단추
TEXT_DARK = "parch0"        # §8
TEXT_GOLD = "bronze3"       # §e
SHADOW = ("ink0", 170)      # 그림자: 따뜻한 먹, 1/2 GUI 픽셀 오른쪽 아래
COVERAGE_GAMMA = 0.85       # 글자 면적의 곡선 (1 보다 작으면 밝은 글이 어두운 바탕에서 가늘어 보이지 않게 조금 굵게)

# 선과 장식 (팔레트 이름, 알파)
GOLD_LINE = ("parch1", 235)     # 긴 머리카락 선 (탁한 금빛)
GOLD_LINE2 = ("parch0", 170)    # 둘째 선 (더 흐리게)
GOLD_ORN = ("parch2", 255)      # 끝 장식
GOLD_HI = ("parch3", 255)       # 장식 꼭짓점, 고른 칸
GOLD_DIM = ("bronze2", 200)     # 덩굴의 그늘
INK = "ash0"                    # 판 바탕 (재 가장 어두운 것)
WELL = "ink0"                   # 칸 우물, 막대 홈
