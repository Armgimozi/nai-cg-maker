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
from weapons import _common as C
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


# ─────────────────────────── 3.2 볼크 가의 장검 ───────────────────────────
# 47 복셀: 폼멜 −11..−7, 손잡이 −7..+5 (한손 반), 가드 +5..+7, 날 +7..+36. 경비대 칼보다 길고 가늘고 끝이 뾰족하다.
# 날 가운데 2/3 에 홈 (어둡게). 기사가 갈아 둔 칼이라 이 빠짐은 둘뿐, 대신 날 밑동과 홈 안에 녹.
# 가드는 끝이 날 쪽으로 굽은 14 복셀 막대 (오른쪽 끝이 한 칸 더 굽었다). 폼멜은 모서리를 깎은 납작한 팔각.
# 하나뿐인 것: 폼멜 앞면의 볼크 가 문장 (사슬 고리 셋) 을 칼로 긁어 지운 자국 (POMMEL_FRONT).

VOLK_SWORD = [
    # x: -7.5 ... +7.5 (16 칸), 맨 윗줄 Y = 35.5
    #   -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7
    "       E        ",   # 35.5  뾰족한 끝
    "       E        ",   # 34.5
    "       EH       ",   # 33.5
    "       HE       ",   # 32.5
    "       HE       ",   # 31.5
    "       HSH      ",   # 30.5
    "      HSSH      ",   # 29.5
    "      HSSH      ",   # 28.5
    "      HSSE      ",   # 27.5
    "      HFFE      ",   # 26.5  홈 시작
    "      HFFE      ",   # 25.5
    "      EFFE      ",   # 24.5
    "       FFH      ",   # 23.5  아랫날 이 빠짐
    "      EFFH      ",   # 22.5
    "      EFFH      ",   # 21.5
    "      EFFH      ",   # 20.5
    "      HFFH      ",   # 19.5
    "      HFF       ",   # 18.5  윗날 이 빠짐
    "      HFFH      ",   # 17.5
    "      HFFH      ",   # 16.5
    "      HFRH      ",   # 15.5  홈 안의 녹
    "      HFFH      ",   # 14.5
    "      HFFH      ",   # 13.5
    "      EFFH      ",   # 12.5
    "      EFFH      ",   # 11.5
    "      ERFE      ",   # 10.5
    "      ERRE      ",   # 9.5
    "      ESRE      ",   # 8.5   밑동 녹
]
VOLK_LOWER = [
    #   -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7
    "              G ",   # 8.5   오른쪽 가드 끝이 한 칸 더 굽었다
    " G    ESRE    G ",   # 7.5   가드 끝이 날 쪽으로
    " gggggCCCCggggg ",   # 6.5   가드 윗줄 (빛 받는 모서리)
    "  GGGGCCCCGGGG  ",   # 5.5
    "      lLLl      ",   # 4.5   손잡이 (12)
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",
    "      lLLl      ",   # -6.5
    "      PPPP      ",   # -7.5  팔각 폼멜
    "     PPPPPP     ",   # -8.5
    "     PPPPPP     ",   # -9.5
    "      PPPP      ",   # -10.5
]
# 손잡이 앞·뒤의 쇠줄 두 가닥 (비스듬히 감긴 자리만 겉에 칠한다). 앞은 왼쪽 아래 → 오른쪽 위, 뒤는 반대
WIRE_FRONT = [
    #  -1.5 .. 1.5
    "   w",   # 4.5
    "  w ",
    " w  ",
    "w   ",
    "    ",
    "    ",
    "   w",   # -1.5
    "  w ",
    " w  ",
    "w   ",
    "    ",
    "    ",   # -6.5
]
WIRE_BACK = [
    "w   ",
    " w  ",
    "  w ",
    "   w",
    "    ",
    "    ",
    "w   ",
    " w  ",
    "  w ",
    "   w",
    "    ",
    "    ",
]
# 폼멜 앞면: 지운 문장. 반쯤 남은 고리 (어두운 쇠 o) 와 그 위를 가로지른 밝은 긁힘 두 줄 (x)
POMMEL_FRONT = [
    #  -2.5 .. 2.5
    "  ox  ",   # -7.5
    " o x  ",   # -8.5
    "  xo. ",   # -9.5
    "      ",   # -10.5
]


def volk_longsword():
    m = blade_mats("steel", "steel_dark", "edge_dull", "dark", "iron", "iron_hi", "leather_dark", "tin", "rust")
    w = weapon(m, kind="longsword", seed=302)
    legend = {
        "E": ("steel", 1), "H": ("edge_dull", 1), "S": ("steel", 1), "F": ("steel_dark", 1), "R": ("rust", 1),
        "G": ("iron", 1), "g": ("iron_hi", 1), "C": ("iron", 1.5), "L": ("leather_dark", 2), "l": ("leather_dark", 1),
        "P": ("iron", 1.5),
    }
    draw(w, VOLK_SWORD, legend, -7.5, 35.5)
    draw(w, VOLK_LOWER, legend, -7.5, 8.5)
    skin(w, WIRE_FRONT, {"w": "tin"}, -1.5, 4.5, side=+1)
    skin(w, WIRE_BACK, {"w": "tin"}, -1.5, 4.5, side=-1)
    skin(w, POMMEL_FRONT, {"o": "dark", "x": "iron_hi"}, -2.5, -7.5, side=+1)
    return w


# ─────────────────────────── 3.3 레딘 뒷골목 단도 ───────────────────────────
# 18 복셀: 슴베 끝 −4..−3, 손잡이 −3..+4 (주먹이 다 덮는다), 가드 +4..+5, 날 +5..+14.
# 외날: 등 (+X) 은 곧고 날 (−X) 은 배처럼 불룩하다가 끝에서 등 쪽으로 올라붙는다. 밑동이 손잡이보다 넓다.
# 부러진 칼의 끝을 갈아 만든 날이라 밑동에 옛 칼의 홈 끝이 한 칸 남았다 (F). 날 끝은 거칠게 간 bone0 한 줄.
# 하나뿐인 것: 넝마를 감고 쇠줄로 두 곳 묶은 손잡이와 늘어진 천 끝.

ALLEY_KNIFE = [
    # x: -3.5 ... +2.5 (7 칸), 맨 윗줄 Y = 13.5
    #  -3 -2 -1  0  1  2
    "     E ",   # 13.5  날카로운 끝 (등 쪽)
    "    EB ",   # 12.5
    "   EBB ",   # 11.5
    "    BB ",   # 10.5  이 빠짐
    "  EBBB ",   # 9.5   불룩한 배
    "  EBBB ",   # 8.5
    "  eBBB ",   # 7.5   이 빠짐 자리 (무딤)
    "   EBB ",   # 6.5
    "   EFB ",   # 5.5   밑동 (손잡이보다 넓다), 옛 칼의 홈 끝
    "  GGGGG",   # 4.5   쇠 고리 가드
    "  rRRr ",   # 3.5   넝마 손잡이
    "  wwww ",   # 2.5   쇠줄
    "  rRRr ",
    "  rRRr ",
    "  rRRr ",
    "  wwww ",   # -1.5  쇠줄
    "  rRRr ",   # -2.5
    "  r TT ",   # -3.5  슴베 끝이 나온다, 천 끝이 늘어진다
    "  r    ",   # -4.5
]


RAG = None  # alley_dagger 안에서 만든다 (pmat 는 import 때 팔레트를 읽는다)


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
    m = blade_mats("steel", "edge", "edge_dull", "dark", "iron", "iron_hi")
    m["rag"] = rag
    w = weapon(m, kind="dagger", seed=303)
    legend = {
        "E": ("edge", 1), "e": ("edge_dull", 1), "B": ("steel", 1), "F": ("dark", 1),
        "G": ("iron", 1.5), "r": ("rag", 1), "R": ("rag", 2), "w": ("iron_hi", 2), "T": ("iron", 0.5),
    }
    draw(w, ALLEY_KNIFE, legend, -3.5, 13.5)
    return w


# ─────────────────────────── 3.16 레딘 결투 단검 ───────────────────────────
# 18 복셀: 폼멜 −4..−3, 손잡이 −3..+4, 가드 +4..+6, 날 +6..+14. 왼손에 든다.
# 좁고 두꺼운 양날 (가운데 등줄은 앞뒤로 한 칸 두껍다), 끝이 날카롭다. 가드는 날 쪽으로 휜 긴 곁가지 (폭 10): 칼을 받는 곳.
# 날보다 가드에 상처가 많다 (곁가지 앞면의 bone0 긁힘, QUILLON_FRONT).
# 하나뿐인 것: 가드 가운데에서 몸 바깥 (−Z) 으로 나온 손가락 고리 (지름 4).

PARRY = [
    # x: -5.5 ... +5.5 (12 칸), 맨 윗줄 Y = 14.5. 날은 왼쪽 줄이 빛 받는 비탈 (E), 오른쪽 줄이 그늘 비탈 (e)
    #  -5 -4 -3 -2 -1  0  1  2  3  4  5
    "      E     ",   # 14.5  날카로운 끝
    "     Ee     ",   # 13.5
    "     Ee     ",   # 12.5
    "     Ee     ",   # 11.5
    "     Ee     ",   # 10.5
    "     Ee     ",   # 9.5
    "    EEee    ",   # 8.5   밑동이 넓어진다
    " Q  EEee   Q",   # 7.5   곁가지 끝 (날 쪽으로 휜다. 오른쪽은 받아 넘긴 칼에 밀려 조금 벌어졌다)
    " Q  eEeR  Q ",   # 6.5   가드 밑 녹
    " Q  qCCq Q  ",   # 5.5
    " QQQQCCQQQ  ",   # 4.5   곁가지 (폭 10)
    "     lLLl   ",   # 3.5   손잡이 (7)
    "     lLLl   ",
    "     lLLl   ",
    "     lLLl   ",
    "     lLLl   ",
    "     lLLl   ",
    "     lLLl   ",   # -2.5
    "     PPPP   ",   # -3.5  폼멜
]
# 곁가지 앞면: 받아 넘긴 칼의 긁힘 (밝은 줄 몇 개, 비스듬히)
QUILLON_FRONT = [
    #  -5.5 .. 5.5
    "           x",   # 7.5
    " x         ",   # 6.5
    "         x  ",   # 5.5
    "  x.x  x.  ",   # 4.5
]
GRIP_WIRE = [
    "w   ",
    " w  ",
    "  w ",
    "   w",
    "w   ",
    " w  ",
    "  w ",
]


def parrying_dagger():
    m = blade_mats("steel", "edge_dull", "rust", "iron", "iron_hi", "leather_dark", "tin", "bone")
    w = weapon(m, kind="parrying_dagger", seed=304)
    legend = {
        "E": ("edge_dull", 1.5), "e": ("steel", 1.5), "R": ("rust", 1.5),
        "Q": ("iron", 1), "q": ("iron_hi", 1), "C": ("iron", 1.5),
        "L": ("leather_dark", 2), "l": ("leather_dark", 1), "P": ("iron", 1.5),
    }
    draw(w, PARRY, legend, -5.5, 14.5)
    skin(w, QUILLON_FRONT, {"x": "bone"}, -5.5, 7.5, side=+1)
    skin(w, GRIP_WIRE, {"w": "tin"}, -1.5, 3.5, side=+1)
    # 손가락 고리: 가드 가운데에서 −Z 로. YZ 면의 고리 (바깥 4×4, 안 2×2), X 두 칸
    ring = []
    for Y in (3.5, 4.5, 5.5, 6.5):
        for Z in (-2.5, -3.5, -4.5, -5.5):
            inner = Y in (4.5, 5.5) and Z in (-3.5, -4.5)
            corner = Y in (3.5, 6.5) and Z in (-2.5, -5.5)
            if not inner and not (corner and Z == -5.5):
                for X in (-0.5, 0.5):
                    ring.append((X, Y, Z))
    put(w, ring, "iron")
    put(w, [(-0.5, 5.5, -1.5), (0.5, 5.5, -1.5), (-0.5, 4.5, -1.5), (0.5, 4.5, -1.5)], "iron")
    return w


# ─────────────────────────── 3.4 탑옥 간수의 대검 ───────────────────────────
# 52 복셀: 폼멜 −12..−8, 손잡이 −8..+5 (두 손), 가드 +5..+7, 날 +7..+40.
# 넓고 두꺼운 곧은 날 (밑동 6, 끝 쪽 5: 오른쪽을 갈아 낸 자리), 가운데 두 줄은 앞뒤로 한 칸 두껍다.
# 날 밑 4 복셀은 날을 세우지 않은 리카소 (가죽 한 줄). 날 끝 밝은 줄은 거의 없고, 이 빠짐 대신 가장자리가 한 칸 안으로
# 찌그러진 자리 셋 (d), 넓은 면에 녹 얼룩 두 덩이.
# 하나뿐인 것: 네모나게 갈아 뭉툭하게 만든 칼끝 (왼쪽 모서리만 조금 닳았다).

GAOL = [
    # x: -9.5 ... +9.5 (20 칸), 맨 윗줄 Y = 39.5
    #  -9 -8 -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7  8  9
    "        SKKS        ",   # 39.5  네모난 끝 (왼쪽 모서리 닳음)
    "       eSKKS        ",   # 38.5
    "       eSKKe        ",   # 37.5
    "       eSKKe        ",   # 36.5
    "       eSKKS        ",   # 35.5  찌그러짐 (오른쪽)
    "       eSKKe        ",   # 34.5
    "       eSKKe        ",   # 33.5
    "       hSKKe        ",   # 32.5
    "       eSKRe        ",   # 31.5  녹 얼룩
    "       eSRRe        ",   # 30.5
    "       eSKKe        ",   # 29.5
    "       eSKKSe       ",   # 28.5  여기서 아래는 폭 6
    "       eSKKSe       ",   # 27.5
    "        SKKSe       ",   # 26.5  찌그러짐 (왼쪽)
    "       eSKKSe       ",   # 25.5
    "       eSKKSe       ",   # 24.5
    "       eSKKSh       ",   # 23.5
    "       eSKKSe       ",   # 22.5
    "       eSKKS        ",   # 21.5  찌그러짐 (오른쪽)
    "       eSKKSe       ",   # 20.5
    "       eSKKSe       ",   # 19.5
    "       hSKKSe       ",   # 18.5
    "       eRKKSe       ",   # 17.5  녹 얼룩
    "       eRRKSe       ",   # 16.5
    "       eSRKSe       ",   # 15.5
    "       eSKKSe       ",   # 14.5
    "       eSKKSe       ",   # 13.5
    "       eSKKSe       ",   # 12.5
    "       eSKKSe       ",   # 11.5
    "       sSKKSs       ",   # 10.5  리카소 (날을 세우지 않음)
    "       wWWWWw       ",   # 9.5   리카소에 감은 가죽 한 줄
    "       sSKKSs       ",   # 8.5
    "       sRKKRs       ",   # 7.5   가드 밑 녹
    " GGGggggggggggGGGG  ",   # 6.5   가드 (18), 빛 받는 모서리는 가운데만
    " GGGGGGGGGGGGGGGGGG ",   # 5.5
]
GAOL_LOWER = [
    #  -9 -8 -7 -6 -5 -4 -3 -2 -1  0  1  2  3  4  5  6  7  8  9
    "        lLLl        ",   # 4.5   손잡이 (13)
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
    "        lLLl        ",   # -7.5
    "        PPPP        ",   # -8.5  무거운 네모 폼멜
    "       PPPPPP       ",   # -9.5
    "       PPPPPp       ",   # -10.5
    "       PPPPPP       ",   # -11.5
    "        PPP         ",   # -12.5 (아래 모서리 하나 닳음)
]


def gaoler_greatsword():
    m = blade_mats("steel", "steel_b", "steel_dark", "edge_dull", "iron", "iron_hi", "leather", "rust")
    w = weapon(m, kind="greatsword", seed=305)
    legend = {
        "e": ("steel", 1), "h": ("edge_dull", 1), "s": ("steel_dark", 1), "S": ("steel_dark", 1),
        "K": ("steel_b", 1.5), "R": ("rust", 1), "W": ("leather", 2), "w": ("leather", 1.5),
        "G": ("iron", 2), "g": ("iron_hi", 2), "L": ("leather", 2), "l": ("leather", 1),
        "P": ("iron", 2), "p": ("iron_hi", 2),
    }
    draw(w, GAOL, legend, -9.5, 39.5)
    draw(w, GAOL_LOWER, legend, -9.5, 4.5)
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
    # 쳐내기 단검은 방패 칸 (왼손): 평소는 무기 자세, 막기는 _block (날을 세우고 곁가지로 받는다)
    "parrying_dagger": {"make": parrying_dagger, "kind": "parrying_dagger", "use": "block",
                        "display": C.hand_display("parrying_dagger"), "use_display": PARRY_BLOCK},
}
