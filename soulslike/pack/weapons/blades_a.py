"""
A 의 칼 다섯 자루 (SPEC.md 3.1~3.4, 3.16): 레딘 경비대 직검, 볼크 가의 장검, 레딘 뒷골목 단도, 탑옥 간수의 대검, 레딘 결투 단검.

앞 (+Z) 에서 본 꼴을 글자 그림으로 한 칸씩 찍는다 (_common.draw). 그림의 한 글자 = 복셀 하나 (1/32 블록).
위 (끝, +Y) 에서 아래 (폼멜) 로, 왼쪽이 −X (아랫날·외날의 날), 오른쪽이 +X (윗날·등).
쥐는 점 (설계 원점) 은 가드 아래 5 복셀, 손잡이 가운데 (SPEC 1.2).

재료 (B 의 _mats 칸): 날 몸 steel / steel_dark, 날 끝 edge (bone0, 군데군데 끊김), 쇠붙이 iron / iron_hi, 녹 rust,
가죽 leather / leather_dark, 쇠줄 tin, 넝마 cloth (parch), 그늘 dark.

글자 (칼마다 legend 를 따로 둔다. 같은 글자는 되도록 같은 뜻)
  E 날 끝 (밝게 간 줄)   e 날 끝인데 무뎌 밝은 줄이 없는 곳   S 날 몸   s 날 몸 그늘 쪽   R 녹   F 홈 (얇게)
  G 가드·폼멜 쇠 (두껍게)  g 쇠의 빛 받는 모서리   L 가죽 (가운데, 두껍게)   l 가죽 (가장자리, 얇게)   w 쇠줄
"""
from weapons._common import draw, pmat, put, skin, weapon
from weapons._mats import mats

# 무딘 날 끝: 갈지 않은 모서리. 바탕 ash3, 이 빠진 자국 ash2 몇 점 (A 몫의 칸, 나머지는 B 의 _mats)
EDGE_DULL = pmat([
    "................",
    "......,.........",
    "................",
    "................",
    "..........,.....",
    "................",
    "................",
    "...,............",
    "................",
    "................",
    "...........,....",
    "................",
    "................",
    "......,.........",
    "................",
    "................",
], {".": "ash3", ",": "ash2"})


def blade_mats(*names):
    m = mats(*[n for n in names if n != "edge_dull"])
    if "edge_dull" in names:
        m["edge_dull"] = EDGE_DULL
    return m


# ─────────────────────────── 3.1 레딘 경비대 직검 ───────────────────────────
# 40 복셀: 폼멜 −9..−5, 손잡이 −5..+5, 가드 +5..+7, 날 +7..+32. 다른 칼을 재는 기준 칼.
# 하나뿐인 것: 가드의 −X 끝이 아래로 휘었다 (16 픽셀 그림에서도 1 픽셀 처진다).
# 이 빠짐 셋: 윗날 Y 16, 아랫날 Y 19~20 (둘), 끝 가까이 윗날 Y 25. 날 끝 밝은 줄은 두 곳에서 끊긴다.

REDIN_SWORD = [
    # x: -6.5 ... +6.5 (14 칸), 맨 윗줄 Y = 31.5
    #  -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6
    "      e       ",   # 31.5  뭉툭한 끝 (1 복셀)
    "      ee      ",   # 30.5
    "     eSe      ",   # 29.5
    "     eSSe     ",   # 28.5
    "     eSSe     ",   # 27.5
    "     eSSe     ",   # 26.5
    "     eSS      ",   # 25.5  끝 가까이 윗날 이 빠짐
    "     ESSE     ",   # 24.5
    "     ESSe     ",   # 23.5
    "     ESSe     ",   # 22.5
    "     ESSe     ",   # 21.5
    "     ESSE     ",   # 20.5
    "      SSE     ",   # 19.5  아랫날 이 빠짐 (둘)
    "      SSE     ",   # 18.5
    "     eSSE     ",   # 17.5
    "     eSS      ",   # 16.5  윗날 이 빠짐
    "     eSSE     ",   # 15.5
    "     eSSE     ",   # 14.5
    "     eSSE     ",   # 13.5
    "     ESSE     ",   # 12.5
    "     ESSE     ",   # 11.5
    "     ESSE     ",   # 10.5
    "     ESSe     ",   # 9.5
    "     ESRe     ",   # 8.5   가드 밑 녹
    "     eRRe     ",   # 7.5
    "  ggggggggggg ",   # 6.5   가드 윗줄 (−X 끝 하나 없음: 휜 끝)
    " GGGGGGGGGGGG ",   # 5.5
    " G            ",   # 4.5   휜 끝
    "     lLLl     ",   # 4.5   손잡이 (10)
    "     lLLl     ",
    "     lLLl     ",
    "     lLLl     ",
    "     lLLl     ",
    "     lLLl     ",
    "     lLLl     ",
    "     lLLl     ",
    "     lLLl     ",
    "     lLLl     ",   # -4.5
    "     lGG      ",   # -5.5  풀린 띠 끝 (손잡이 아래로 한 칸 처진다), 폼멜 목
    "     GGGg     ",   # -6.5  폼멜 (원반)
    "     GGGG     ",   # -7.5
    "      GG      ",   # -8.5
]


def redin_guard_sword():
    m = blade_mats("steel", "edge", "edge_dull", "iron", "iron_hi", "leather", "rust")
    w = weapon(m, kind="straight_sword", seed=301)
    legend = {
        "E": ("edge", 1), "e": ("edge_dull", 1), "S": ("steel", 1), "R": ("rust", 1),
        "G": ("iron", 1.5), "g": ("iron_hi", 1.5), "L": ("leather", 2), "l": ("leather", 1),
    }
    rows = list(REDIN_SWORD)
    # 가드 휜 끝 줄과 손잡이 첫 줄이 같은 Y (4.5) 라 두 번에 나눠 찍는다
    draw(w, rows[:28], legend, -6.5, 31.5)
    draw(w, rows[28:], legend, -6.5, 4.5)
    return w


ITEMS = {
    "redin_guard_sword": (redin_guard_sword, "straight_sword"),
}
