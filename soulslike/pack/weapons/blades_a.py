"""
A 의 칼 다섯 자루 (SPEC.md 3.1~3.4, 3.16): 레딘 경비대 직검, 볼크 가의 장검, 레딘 뒷골목 단도, 탑옥 간수의 대검, 레딘 결투 단검.

앞 (+Z) 에서 본 꼴을 글자 그림으로 한 칸씩 찍는다 (_common.draw). 그림의 한 글자 = 복셀 하나 (1/32 블록).
위 (끝, +Y) 에서 아래 (폼멜) 로, 왼쪽이 −X (아랫날·외날의 날), 오른쪽이 +X (윗날·등).
쥐는 점 (설계 원점) 은 가드 아래 5 복셀, 손잡이 가운데 (SPEC 1.2).

날 짜임 (모든 칼이 같은 말을 쓴다, 2026-10-07 판정 A3)
  - 날 몸은 이어진 판 하나: 두께 2 (설계 Z −0.5, +0.5 두 칸), 밑동에서 끝까지 끊기지 않는다.
  - 날 끝은 가장 바깥 한 줄, 두께 1 (Z −0.5 한 칸): 앞에서 보면 한 칸 물러난 턱이 날을 세운 비탈로 읽힌다. 뒤는 판과 같은 면.
  - 좁아짐은 한쪽에 두세 계단, 그다음 끝. 이 빠짐은 날 끝 줄에서 한 칸만 떼어 낸다 (판은 그대로).
  - 폭이 홀수인 칼 (직검, 쳐내기 단검, 뒷골목 단도) 은 가운데가 X −0.5, 짝수인 칼 (장검, 대검) 은 X 0 이다 (반 복셀 = 1/64 블록 차이).

재료 (B 의 _mats 칸): 날 몸 steel / steel_b / steel_dark, 날 끝 edge (bone0, 군데군데 끊김) / edge_dull, 쇠붙이 iron / iron_hi,
녹 rust, 가죽 leather / leather_dark, 쇠줄 tin, 넝마 rag, 그늘 dark.

글자 (칼마다 legend 를 따로 둔다. 같은 글자는 되도록 같은 뜻)
  E 날 끝 (밝게 간 줄)   e 날 끝인데 무뎌 밝은 줄이 없는 곳   S 날 몸   K 날 몸의 가운데 결   R 녹   F 홈 (앞이 한 칸 파였다)
  G 가드·폼멜 쇠   g 쇠의 빛 받는 모서리   L 가죽 손잡이   w 쇠줄   P 폼멜
"""
from weapons import _common as C
from weapons._common import draw, pmat, put, skin, weapon
from weapons._mats import mats

# 무딘 날 끝: 갈지 않은 모서리. 바탕 ash3, 이 빠진 자국 ash2 (세로 두 칸, 몇 곳)
EDGE_DULL = pmat([
    "................",
    "......,.........",
    "......,.........",
    "................",
    "..........,.....",
    "..........,.....",
    "................",
    "...,............",
    "...,............",
    "................",
    "...........,....",
    "...........,....",
    "................",
    "......,.........",
    "......,.........",
    "................",
], {".": "ash3", ",": "ash2"})

# 날 끝은 Z −0.5 한 칸, 날 몸은 Z −0.5..+0.5 두 칸
THIN = (-0.5, -0.5)
SLAB = (-0.5, 0.5)


def blade_mats(*names):
    m = mats(*[n for n in names if n != "edge_dull"])
    if "edge_dull" in names:
        m["edge_dull"] = EDGE_DULL
    return m


# ─────────────────────────── 3.1 레딘 경비대 직검 ───────────────────────────
# 41 복셀: 폼멜 −9..−5, 손잡이 −5..+5, 가드 +5..+7, 날 +7..+32. 다른 칼을 재는 기준 칼 (가장 깨끗하다).
# 날: 폭 5 로 곧게 오다가 끝 다섯 줄에서 폭 3, 마지막 한 줄이 뭉툭한 끝 (한쪽 두 계단).
# 이 빠짐 셋: 윗날 Y 16, 아랫날 Y 20, 끝 가까이 윗날 Y 28. 날 끝 밝은 줄은 두 곳에서 무뎌 끊긴다 (e).
# 하나뿐인 것: 가드의 −X 끝이 두 칸 아래로 휘었다 (3인칭에서도 보이게).

REDIN_SWORD = [
    # x: -7.5 ... +6.5 (15 칸, 가운데 X −0.5 는 8번째 칸), 맨 윗줄 Y = 31.5
    #  -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6
    "       e       ",   # 31.5  뭉툭한 끝 (한 칸)
    "      eSe      ",   # 30.5
    "      ESe      ",   # 29.5
    "      ES       ",   # 28.5  끝 가까이 윗날 이 빠짐
    "      ESE      ",   # 27.5
    "     eSSSE     ",   # 26.5  폭 5
    "     eSSSE     ",   # 25.5
    "     ESSSE     ",   # 24.5
    "     ESSSe     ",   # 23.5
    "     ESSSe     ",   # 22.5
    "     ESSSE     ",   # 21.5
    "     ESSSE     ",   # 20.5
    "      SSSE     ",   # 19.5  아랫날 이 빠짐
    "     ESSSE     ",   # 18.5
    "     ESSSE     ",   # 17.5
    "     ESSS      ",   # 16.5  윗날 이 빠짐
    "     ESSSE     ",   # 15.5
    "     eSSSE     ",   # 14.5
    "     eSSSE     ",   # 13.5
    "     ESSSE     ",   # 12.5
    "     ESSSE     ",   # 11.5
    "     ESSSE     ",   # 10.5
    "     ESSSe     ",   # 9.5
    "     ESRSe     ",   # 8.5   가드 밑 녹 (세 칸 덩이)
    "     eRRSe     ",   # 7.5
    "  gggggggggggg ",   # 6.5   가드 윗줄 (빛 받는 모서리). −X 끝 한 칸은 아래로 휘어 비었다
    " GGGGGGGGGGGGG ",   # 5.5   가드 (13, 두께 3)
    " G             ",   # 4.5   휜 끝
    " G             ",   # 3.5
]
REDIN_GRIP = [
    #  -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6
    "      LLL      ",   # 4.5   손잡이 (10, 굵기 3)
    "      LLL      ",
    "      LLL      ",
    "      LLL      ",
    "      LLL      ",
    "      LLL      ",
    "      LLL      ",
    "      LLL      ",
    "      LLL      ",
    "      LLL      ",   # -4.5
    "      LGGG     ",   # -5.5  풀린 띠 끝이 한 칸 처진다, 폼멜 목
    "     gGGGG     ",   # -6.5  폼멜 (원반)
    "     GGGGG     ",   # -7.5
    "      GGG      ",   # -8.5
]


def redin_guard_sword():
    m = blade_mats("steel", "edge", "edge_dull", "iron", "iron_hi", "leather", "rust")
    w = weapon(m, kind="straight_sword", seed=301)
    legend = {
        "E": ("edge", *THIN), "e": ("edge_dull", *THIN), "S": ("steel", *SLAB), "R": ("rust", *SLAB),
        "G": ("iron", -1.5, 0.5), "g": ("iron_hi", -1.5, 0.5), "L": ("leather", -1.5, 0.5),
    }
    draw(w, REDIN_SWORD, legend, -7.5, 31.5)
    draw(w, REDIN_GRIP, legend, -7.5, 4.5)
    return w


# ─────────────────────────── 3.2 볼크 가의 장검 ───────────────────────────
# 47 복셀: 폼멜 −11..−7, 손잡이 −7..+5 (한손 반), 가드 +5..+7, 날 +7..+36. 경비대 칼보다 길고 끝이 뾰족하다.
# 날: 폭 6 → 끝 여덟 줄에서 4 → 2 (한쪽 두 계단). 가운데 홈 (폭 2, 깊이 1) 은 가드 위에서 끝 1/3 앞까지 (Y 9..27).
# 기사가 갈아 둔 칼이라 이 빠짐은 둘뿐, 대신 날 밑동과 홈 안에 녹.
# 가드: 14 복셀 막대, 끝 두세 칸이 날 쪽으로 한 칸 들린다 (오른쪽이 조금 더 가파르다). 폼멜: 모서리를 깎은 납작한 팔각.
# 하나뿐인 것: 폼멜 앞면의 볼크 가 문장 (사슬 고리 셋) 을 칼로 긁어 지운 자국 (밝은 긁힘 두 줄, ash3).

VOLK_SWORD = [
    # x: -7.5 ... +7.5 (16 칸, 가운데 X 0), 맨 윗줄 Y = 35.5
    #   -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7
    "       EE       ",   # 35.5  뾰족한 끝 (얇다)
    "       EE       ",   # 34.5
    "       EE       ",   # 33.5
    "      eSSE      ",   # 32.5  폭 4
    "      eSSE      ",   # 31.5
    "      ESSE      ",   # 30.5
    "      ESSe      ",   # 29.5
    "      ESSe      ",   # 28.5
    "     ESSSSE     ",   # 27.5  폭 6
    "     ESFFSE     ",   # 26.5  홈 끝
    "     ESFFSE     ",   # 25.5
    "     ESFFSe     ",   # 24.5
    "      SFFSe     ",   # 23.5  아랫날 이 빠짐
    "     ESFFSe     ",   # 22.5
    "     ESFFSE     ",   # 21.5
    "     eSFFSE     ",   # 20.5
    "     eSFFSE     ",   # 19.5
    "     ESFFS      ",   # 18.5  윗날 이 빠짐
    "     ESFFSE     ",   # 17.5
    "     ESFFSE     ",   # 16.5
    "     ESFRSE     ",   # 15.5  홈 안의 녹
    "     ESFFSE     ",   # 14.5
    "     ESFFSE     ",   # 13.5
    "     ESFFSe     ",   # 12.5
    "     ESFFSe     ",   # 11.5
    "     ERFFSE     ",   # 10.5
    "     ERRFSE     ",   # 9.5   밑동 녹
    "     eSRRSe     ",   # 8.5
    "     eSSSSe     ",   # 7.5
]
VOLK_LOWER = [
    #   -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7
    " g            gg",   # 7.5   끝이 날 쪽으로 들린다 (오른쪽이 한 칸 더 길게)
    " ggggggggggggg  ",   # 6.5   가드 윗줄 (빛 받는 모서리)
    "  GGGGGGGGGGGG  ",   # 5.5
    "      lLLl      ",   # 4.5   손잡이 (12)
    "      wwww      ",   # 3.5   쇠줄 (손잡이 위끝)
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      wwww      ",   # -5.5  쇠줄 (손잡이 아래끝)
    "      lLLl      ",   # -6.5
    "      PPPP      ",   # -7.5  팔각 폼멜
    "     PPPPPP     ",   # -8.5
    "     PPPPPP     ",   # -9.5
    "      PPPP      ",   # -10.5
]
# 폼멜 앞면: 지운 문장. 밝은 긁힘 두 줄 (x, ash3) 이 반쯤 남은 고리 (o, 어두운 쇠) 를 비스듬히 가로지른다
POMMEL_FRONT = [
    #  -2.5 .. 2.5
    "    x ",   # -7.5
    " o x  ",   # -8.5
    "  xo x",   # -9.5
    "   x  ",   # -10.5
]


def volk_longsword():
    m = blade_mats("steel_b", "steel_dark", "edge_dull", "dark", "iron", "iron_hi", "iron_edge", "leather_dark", "rust")
    m["edge"] = mats("edge")["edge"]
    w = weapon(m, kind="longsword", seed=302)
    legend = {
        "E": ("edge", *THIN), "e": ("edge_dull", *THIN), "S": ("steel_b", *SLAB), "F": ("steel_dark", *THIN),
        "R": ("rust", *THIN), "G": ("iron", -1.5, 0.5), "g": ("iron_hi", -1.5, 0.5),
        "L": ("leather_dark", -1.5, 1.5), "l": ("leather_dark", *SLAB), "w": ("iron", -1.5, 1.5),
        "P": ("iron", -1.5, 1.5),
    }
    # 홈 (F, R) 은 판의 뒤 칸 (Z −0.5) 만 남겨 앞이 한 칸 파였다. 녹 R 도 홈 안이라 같은 깊이
    draw(w, VOLK_SWORD, legend, -7.5, 35.5)
    draw(w, VOLK_LOWER, legend, -7.5, 7.5)
    # 쇠줄 두 줄의 가장자리 칸은 손잡이 꼴을 따라 얇게
    put(w, [(X, Y, Z) for X in (-1.5, 1.5) for Y in (3.5, -5.5) for Z in (-1.5, 1.5)], None)
    skin(w, POMMEL_FRONT, {"o": "dark", "x": "iron_edge"}, -2.5, -7.5, side=+1)
    return w


# ─────────────────────────── 3.3 레딘 뒷골목 단도 ───────────────────────────
# 21 복셀: 슴베 끝 −4..−3, 손잡이 −3..+4 (7, 주먹이 다 덮는다), 가드 +4..+5, 날 +5..+17 (12).
# 외날: 등 (+X) 은 곧고 날 (−X) 은 배처럼 불룩하다가 끝에서 등 쪽으로 올라붙는다. 끝에서 내려오며 계단 길이가 1, 2, 3, 3 으로
# 늘어나는 볼록한 곡선. 밑동이 손잡이보다 넓다. 부러진 칼의 끝을 갈아 만든 날이라 밑동에 옛 칼의 홈 끝 (1×2, 한 칸 파임).
# 하나뿐인 것: 넝마를 감고 쇠줄로 두 곳 묶은 손잡이 (쇠줄은 넝마와 같은 높이) 와 늘어진 천 끝.

ALLEY_KNIFE = [
    # x: -3.5 ... +2.5 (7 칸, 가운데 X −0.5), 맨 윗줄 Y = 16.5.  B 등 (빛 받는 쪽, 판과 같은 두께)
    #  -3 -2 -1  0  1  2
    "     E ",   # 16.5  날카로운 끝 (등 쪽)
    "    EB ",   # 15.5
    "   ESB ",   # 14.5
    "   ESB ",   # 13.5
    "  ESSB ",   # 12.5
    "   SSB ",   # 11.5  이 빠짐
    "  ESSB ",   # 10.5
    " eSSSB ",   # 9.5   불룩한 배
    "  SSSB ",   # 8.5   이 빠짐
    " ESSSB ",   # 7.5
    "  ESFB ",   # 6.5   밑동 (옛 칼의 홈 끝 1×2)
    "  eSFB ",   # 5.5
    " GGGGG ",   # 4.5   쇠 고리 가드 (손잡이보다 한 칸씩 넓다)
    "  rrr  ",   # 3.5   넝마 손잡이 (7)
    "  www  ",   # 2.5   쇠줄 (넝마와 같은 높이)
    "  rrr  ",
    "  rrr  ",
    "  rrr  ",
    "  www  ",   # -1.5  쇠줄
    "  rrr  ",   # -2.5
    "  rT   ",   # -3.5  슴베 끝, 천 끝이 늘어진다
    " rr    ",   # -4.5
]


def alley_dagger():
    rag = pmat([
        "....,...........",
        "....,......:....",
        "...,,......:....",
        "...,.......:....",
        "...,......::....",
        "...,......:.....",
        "..,,......:.....",
        "..,......::..kk.",
        "..,......:...kk.",
        "..,......:....k.",
        ".,,.....::......",
        ".,......:.......",
        ".,......:.......",
        ".,.....::.......",
        ",,.....:........",
        ",......:........",
    ], {".": "parch0", ",": "parch1", ":": "rust1", "k": "blood0"})
    m = blade_mats("steel", "steel_dark", "edge", "edge_dull", "iron", "iron_hi")
    m["rag"] = rag
    w = weapon(m, kind="dagger", seed=303)
    legend = {
        "E": ("edge", *THIN), "e": ("edge_dull", *THIN), "S": ("steel", *SLAB), "B": ("iron_hi", *SLAB),
        "F": ("steel_dark", *THIN), "G": ("iron", -1.5, 0.5), "r": ("rag", -1.5, 0.5), "w": ("iron_hi", -1.5, 0.5),
        "T": ("iron", *THIN),
    }
    draw(w, ALLEY_KNIFE, legend, -3.5, 16.5)
    # 늘어진 천 끝은 얇다 (한 칸)
    put(w, [(-1.5, -4.5, -1.5), (-1.5, -4.5, 0.5), (-2.5, -4.5, -1.5), (-2.5, -4.5, 0.5)], None)
    return w


# ─────────────────────────── 3.16 레딘 결투 단검 ───────────────────────────
# 22 복셀: 폼멜 −4..−3, 손잡이 −3..+4, 가드 +4..+6, 날 +6..+18 (12). 왼손에 든다.
# 좁은 양날 (폭 3: 가운데 등줄은 판 두께, 양쪽 날 끝은 얇다), 끝이 날카롭다.
# 가드: 가로대 (9) 양 끝에서 곁가지 둘이 날 쪽으로 곧게 서다가 끝에서 안으로 굽는다 (칼을 받는 U). 오른쪽 곁가지 끝은 받아 넘긴
# 칼에 밀려 바깥으로 꺾였다. 곁가지 앞면에 bone0 긁힘 몇 줄 (날보다 가드에 상처가 많다).
# 하나뿐인 것: 가드 가운데에서 몸 바깥 (−Z) 으로 나온 손가락 고리 (바깥 4×4, 구멍 2×2).

PARRY = [
    # x: -6.5 ... +5.5 (13 칸, 가운데 X −0.5), 맨 윗줄 Y = 17.5
    #  -6 -5 -4 -3 -2 -1  0  1  2  3  4  5
    "      E      ",   # 17.5  날카로운 끝
    "      S      ",   # 16.5
    "     ESE     ",   # 15.5
    "     ESE     ",   # 14.5
    "     ESE     ",   # 13.5
    "     ESe     ",   # 12.5
    "     ESe     ",   # 11.5
    "     ESE     ",   # 10.5
    "    QESE  QQ ",   # 9.5   곁가지 끝: 왼쪽은 안으로 굽고, 오른쪽은 바깥으로 꺾였다
    "   QQeSE  Q  ",   # 8.5
    "   Q eSE  Q  ",   # 7.5
    "   Q eRE  Q  ",   # 6.5   가드 밑 녹
    "   QQQCQQQQ  ",   # 5.5   가로대
    "    qqCqqq   ",   # 4.5
    "     LLL     ",   # 3.5   손잡이 (7)
    "     LLL     ",
    "     LLL     ",
    "     LLL     ",
    "     LLL     ",
    "     LLL     ",
    "     LLL     ",   # -2.5
    "     PPP     ",   # -3.5  폼멜
]
# 곁가지 앞면: 받아 넘긴 칼의 긁힘 (밝은 줄, 곁가지를 따라)
QUILLON_FRONT = [
    #  -6.5 .. 5.5
    "             ",   # 9.5
    "   x         ",   # 8.5
    "   x       x ",   # 7.5
    "           x ",   # 6.5
    "    x    x   ",   # 5.5
]


def parrying_dagger():
    m = blade_mats("steel", "edge_dull", "rust", "iron", "iron_hi", "leather_dark", "bone")
    m["edge"] = mats("edge")["edge"]
    w = weapon(m, kind="parrying_dagger", seed=304)
    legend = {
        "E": ("edge", *THIN), "e": ("edge_dull", *THIN), "S": ("steel", *SLAB), "R": ("rust", *SLAB),
        "Q": ("iron_hi", *SLAB), "q": ("iron", *SLAB), "C": ("iron", -1.5, 0.5),
        "L": ("leather_dark", -1.5, 0.5), "P": ("iron", -1.5, 0.5),
    }
    draw(w, PARRY, legend, -6.5, 17.5)
    skin(w, QUILLON_FRONT, {"x": "bone"}, -6.5, 9.5, side=+1)
    # 손가락 고리: 가드 가운데 (X −0.5, 한 칸 두께) 에서 −Z 로. YZ 면의 고리 (바깥 4×4, 구멍 2×2), 가드 뒷면에 붙는다
    ring = []
    for Y in (3.5, 4.5, 5.5, 6.5):
        for Z in (-2.5, -3.5, -4.5, -5.5):
            inner = Y in (4.5, 5.5) and Z in (-3.5, -4.5)
            if not inner:
                ring.append((-0.5, Y, Z))
    put(w, ring, "iron")
    put(w, [(-0.5, 3.5, -5.5)], None)          # 바깥 귀퉁이 하나가 닳았다 (대칭을 깬다)
    return w


# ─────────────────────────── 3.4 탑옥 간수의 대검 ───────────────────────────
# 53 복셀: 폼멜 −14..−9, 손잡이 −9..+4 (두 손, 13), 가드 +4..+7 (높이 3), 날 +7..+40.
# 넓고 곧은 날 (폭 6, 위 1/3 은 오른쪽 날을 갈아 내 폭 5). 가운데 두 줄은 어두운 결 (16 픽셀 그림의 가운데 어두운 줄).
# 날 밑 네 줄은 날을 세우지 않은 리카소 (가죽 한 줄을 감았다). 날 끝 밝은 줄은 거의 없고, 이 빠짐 대신 날 끝 줄이 한 칸 안으로
# 찌그러진 자리 셋, 넓은 면에 녹 얼룩 두 덩이 (3~5 칸).
# 가드: 두꺼운 곧은 쇠막대 18 × 3, 끝이 네모. 폼멜: 모서리를 깎은 무거운 덩이 6 × 5 × 4.
# 하나뿐인 것: 네모나게 갈아 뭉툭하게 만든 칼끝 (왼쪽 모서리만 조금 닳았다).

GAOL = [
    # x: -9.5 ... +9.5 (20 칸, 가운데 X 0), 맨 윗줄 Y = 39.5
    #  -9 -8 -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7  8  9
    "        SKKS        ",   # 39.5  네모난 끝 (왼쪽 모서리 닳음, 갈아 내 날 끝 줄이 없다)
    "       eSKKS        ",   # 38.5
    "       eSKKe        ",   # 37.5
    "       eSKKe        ",   # 36.5
    "       eSKK         ",   # 35.5  찌그러짐 (오른쪽)
    "       eSKKe        ",   # 34.5
    "       eSKKe        ",   # 33.5
    "       ESKKe        ",   # 32.5
    "       eSKRe        ",   # 31.5  녹 얼룩 (넷)
    "       eSRRe        ",   # 30.5
    "       eSKRe        ",   # 29.5
    "       eSKKSe       ",   # 28.5  여기서 아래는 폭 6
    "       eSKKSe       ",   # 27.5
    "        SKKSe       ",   # 26.5  찌그러짐 (왼쪽)
    "       eSKKSe       ",   # 25.5
    "       eSKKSe       ",   # 24.5
    "       eSKKSE       ",   # 23.5
    "       eSKKSe       ",   # 22.5
    "       eSKKS        ",   # 21.5  찌그러짐 (오른쪽)
    "       eSKKSe       ",   # 20.5
    "       eSKKSe       ",   # 19.5
    "       ESKKSe       ",   # 18.5
    "       eRKKSe       ",   # 17.5  녹 얼룩 (넷)
    "       eRRKSe       ",   # 16.5
    "       eSRKSe       ",   # 15.5
    "       eSKKSe       ",   # 14.5
    "       eSKKSe       ",   # 13.5
    "       eSKKSe       ",   # 12.5
    "       eSKKSe       ",   # 11.5
    "       sSKKSs       ",   # 10.5  리카소 (날을 세우지 않음: 날 끝 줄도 판 두께)
    "       wWWWWw       ",   # 9.5   리카소에 감은 가죽 한 줄
    "       sSKKSs       ",   # 8.5
    "       sSKKSs       ",   # 7.5
    " GGGggggggggggggGGG ",   # 6.5   가드 (18 × 3), 빛 받는 모서리는 가운데만
    " GGGGGGGGGGGGGGGGGG ",   # 5.5
    " GGGGGGGGGGGGGGGGGG ",   # 4.5
]
GAOL_LOWER = [
    #  -9 -8 -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7  8  9
    "        lLLl        ",   # 3.5   손잡이 (13)
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",
    "        lLLl        ",   # -8.5
    "        pPPP        ",   # -9.5  무거운 폼멜 (모서리를 깎았다)
    "       pPPPPP       ",   # -10.5
    "       PPPPPP       ",   # -11.5
    "       PPPPPP       ",   # -12.5
    "        PPP         ",   # -13.5 (아래 모서리 하나는 더 닳았다)
]


def gaoler_greatsword():
    m = blade_mats("steel_b", "steel_dark", "edge_dull", "iron", "iron_hi", "leather", "rust")
    m["edge"] = mats("edge")["edge"]
    w = weapon(m, kind="greatsword", seed=305)
    legend = {
        "e": ("edge_dull", *THIN), "E": ("edge", *THIN), "s": ("steel_dark", *SLAB), "S": ("steel_b", *SLAB),
        "K": ("steel_dark", *SLAB), "R": ("rust", *SLAB), "W": ("leather", -1.5, 1.5), "w": ("leather", *SLAB),
        "G": ("iron", -1.5, 1.5), "g": ("iron_hi", -1.5, 1.5), "L": ("leather", -1.5, 1.5), "l": ("leather", *SLAB),
        "P": ("iron", -1.5, 1.5), "p": ("iron_hi", -1.5, 1.5),
    }
    draw(w, GAOL, legend, -9.5, 39.5)
    draw(w, GAOL_LOWER, legend, -9.5, 3.5)
    # 폼멜 모서리 깎기: 앞뒤 위 귀퉁이 한 칸씩
    put(w, [(X, -9.5, Z) for X in (-1.5, -0.5, 0.5, 1.5) for Z in (-1.5, 1.5)], None)
    put(w, [(X, -13.5, Z) for X in (-1.5, -0.5, 0.5) for Z in (-1.5, 1.5)], None)
    return w


# 쳐내기 단검 막기 (_block, 왼손): 날을 위로 세우고 곁가지를 앞으로 내밀어 받는다. 3인칭은 들어 올린 팔 앞에서 날이 서고
# 날 면이 앞을 본다. 1인칭은 화면 왼쪽, 십자선 아래에 날이 서고 면이 화면을 본다. 이동은 3인칭 정한 값 그대로 [미확인 (클라)]
PARRY_BLOCK = {
    "thirdperson_righthand": C._t([-160, 30, -170], C.TP_T, 1.0),
    "firstperson_righthand": C._t([135, -70, 60], [-0.73, 3.95, 1.76], C.FP_SCALE["parrying_dagger"]),
}

ITEMS = {
    "redin_guard_sword": (redin_guard_sword, "straight_sword"),
    "volk_longsword": (volk_longsword, "longsword"),
    "alley_dagger": (alley_dagger, "dagger"),
    "gaoler_greatsword": (gaoler_greatsword, "greatsword"),
    # 쳐내기 단검은 방패 칸 (왼손): 평소는 무기 자세 (길이로 셈), 막기는 _block (날을 세우고 곁가지로 받는다)
    "parrying_dagger": {"make": parrying_dagger, "kind": "parrying_dagger", "use": "block",
                        "display": None, "use_display": PARRY_BLOCK},
}
