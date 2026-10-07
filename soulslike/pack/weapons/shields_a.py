"""
A 의 방패 셋 (SPEC.md 3.15, 3.17, 3.18): 오스윈 순례자의 버클러, 레딘 경비대 방패, 볼크 가의 대방패.

설계 축 (SPEC 1.2): +Y 위, +Z 앞면 (적을 보는 칠한 면), 손잡이는 뒤 (−Z) 에 있고 그 가운데가 쥐는 점 (설계 원점).
판의 뒷면은 Z = +5 에 둔다: 마인크래프트 팔은 쥐는 점에서 2 픽셀 (4 복셀) 까지 차 있으므로 판이 그보다 바깥에 있어야
3인칭에서 팔이 판을 뚫고 나오지 않는다. 손잡이는 쥐는 점을 지나는 X 방향 막대 (팔과 직각, 주먹이 감싼다).
아래팔은 쥐는 점에서 +Y 로 뻗으므로 (팔꿈치 쪽) 팔 끈은 그 둘레 (|X|, |Z| ≤ 4 밖) 를 감는다.

앞면은 글자 그림으로 꼴을 찍고 (_common.draw, 판 = 나무), 칠·문장·벗겨진 자리·베인 자국은 겉 칠 (_common.skin) 로 얹는다.
"""
from weapons import _common as C
from weapons._common import draw, pmat, put, skin, weapon
from weapons._mats import mats

# 칠한 면 (바랜 양피지색 칠, 붓 자국 몇 줄, 손때). A 몫의 칸
PAINT = [
    "................",
    "................",
    "............:...",
    "............:...",
    "................",
    "................",
    "..........,,....",
    "................",
    "................",
    "................",
    "................",
    "...:............",
    "...:............",
    "................",
    "................",
    "................",
]
CREST = [
    "................",
    "....:...........",
    "................",
    "..........:.....",
    "................",
    "................",
    ".:..............",
    "................",
    "........:.......",
    "................",
    "................",
    "...:............",
    "................",
    "...........:....",
    "................",
    "................",
]


# 넓은 쇠판: 바탕 ash1, 긁힌 자리 ash2 몇 줄, 움푹 팬 점 ash0 둘 (B 의 iron 칸은 작은 쇠붙이용이라 넓은 면에서 점이 많다)
IRON_PLATE = [
    "................",
    "................",
    "...+............",
    "....+...........",
    ".............,..",
    "................",
    "................",
    "..........++....",
    "................",
    "................",
    "................",
    ".,..............",
    "................",
    "......+.........",
    ".......+........",
    "................",
]


def shield_mats(*names):
    m = mats(*[n for n in names if n not in ("paint", "crest")])
    if "paint" in names:
        m["paint"] = pmat(PAINT, {".": "parch1", ",": "parch2", ":": "parch0"})
    if "crest" in names:
        m["crest"] = pmat(CREST, {".": "blood1", ":": "blood0"})
    return m


# ─────────────────────────── 3.17 레딘 경비대 방패 ───────────────────────────
# 높이 26 × 폭 20 복셀 (0.81 × 0.63 블록). 다리미꼴: 위가 곧고 아래로 좁아져 둥근 뾰족끝. 쇠 테 한 칸.
# 앞면 가운데 폭 12 가 한 칸 볼록 (B). 쥐는 점 = 손잡이 가운데 = 판 가운데보다 한 칸 위.
# 낡음: 칠이 벗겨져 나무가 드러난 자리 셋, 테 찌그러짐 (오른쪽, Y 4), 오른쪽 위에서 비스듬히 베인 자국 하나 (테까지 갈랐다).
# 하나뿐인 것: 앞면의 성문 문장, 닫힌 쇠살문 (8×9, 거의 벗겨졌다).

HEATER = [
    # x: -9.5 ... +9.5 (20 칸), 맨 윗줄 Y = 11.5.  O 테, W 판, B 볼록한 가운데 판
    "OOOOOOOOOOOOO OOOOOO",   # 11.5  (베인 자국이 테를 갈랐다)
    "OWWWBBBBBBBBBBBBWWWO",   # 10.5
    "OWWWBBBBBBBBBBBBWWWO",
    "OWWWBBBBBBBBBBBBWWWO",
    "OWWWBBBBBBBBBBBBWWWO",
    "OWWWBBBBBBBBBBBBWWWO",
    "OWWWBBBBBBBBBBBBWWWO",   # 5.5
    "OWWWBBBBBBBBBBBBWWO ",   # 4.5   테 찌그러짐 (한 칸 안으로)
    "OWWWBBBBBBBBBBBBWWWO",
    "OWWWBBBBBBBBBBBBWWWO",
    "OWWWBBBBBBBBBBBBWWWO",
    "OWWWBBBBBBBBBBBBWWWO",   # 0.5
    "OWWWBBBBBBBBBBBBWWWO",   # -0.5
    "OWWWBBBBBBBBBBBBWWWO",   # -1.5
    " OWWBBBBBBBBBBBBWWO ",   # -2.5
    " OWWBBBBBBBBBBBBWWO ",
    "  OWBBBBBBBBBBBBWO  ",   # -4.5
    "  OWBBBBBBBBBBBBWO  ",
    "   OWBBBBBBBBBBWO   ",   # -6.5
    "   OWBBBBBBBBBBWO   ",
    "    OWBBBBBBBBWO    ",   # -8.5
    "     OWBBBBBBWO     ",   # -9.5
    "      OWBBBBWO      ",   # -10.5
    "       OWBBWO       ",   # -11.5
    "        OBBO        ",   # -12.5
    "         OO         ",   # -13.5
]
# 앞면 겉 칠은 꼴 (HEATER) 에서 셈해 만든다: p 칠 (기본), c 문장 (바랜 핏빛), w 칠이 벗겨진 나무, x 베인 자국 (깊은 그늘)
# 문장: 닫힌 쇠살문 8×9 (세로살 넷, 가로보 셋, 살 끝의 뾰족). 지워진 칸은 '.' (칠만 남음)
PORTCULLIS = [
    # 닫힌 쇠살문: 세로살 넷, 가로보 셋, 살 끝의 뾰족. 칠이 군데군데 벗겨졌다 ('.' 로 지운 칸)
    "ccccc...",   # 9.5   윗보 (오른쪽 끝이 벗겨졌다)
    "c.c.c.c.",   # 8.5
    "c.c.c.c.",   # 7.5
    "ccccccc.",   # 6.5   가운데 보
    "c.c...c.",   # 5.5
    "c.c.c.c.",   # 4.5
    "cc.cccc.",   # 3.5   아랫보
    "c.c.c.c.",   # 2.5
    "c.c.c.c.",   # 1.5
    "c...c.c.",   # 0.5   살 끝
]
HEATER_CHIPS = [(1, 3), (2, 3), (1, 4), (17, 1), (17, 2), (14, 13), (15, 13),
                (9, 19), (10, 19), (9, 20), (10, 20), (11, 20), (10, 21), (11, 21)]
HEATER_CUT = [(13, 1), (12, 2), (11, 3), (10, 4), (9, 5), (8, 6)]


def heater_front():
    rows = [[" "] * 20 for _ in HEATER]
    for j, row in enumerate(HEATER):
        for i, ch in enumerate(row):
            if ch in "WB":
                rows[j][i] = "p"
    for dj, line in enumerate(PORTCULLIS):
        for di, ch in enumerate(line):
            if ch in "cv":
                rows[2 + dj][6 + di] = "c"
    for i, j in HEATER_CHIPS:
        rows[j][i] = "w"
    cut = [[" "] * 20 for _ in HEATER]
    for i, j in HEATER_CUT:
        rows[j][i] = "x"
        cut[j][i] = "x"
    return ["".join(r) for r in rows], ["".join(r) for r in cut]


def _heater_back(w):
    """뒷면: 손잡이 (가죽 감은 쇠 막대, 기둥 둘), 팔을 끼우는 가죽 고리 하나, 판을 가로지른 멜끈 하나."""
    cells = []
    for X in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5):
        for Y in (-0.5, 0.5):
            for Z in (-0.5, 0.5):
                cells.append((X, Y, Z))
    put(w, cells, "leather_dark")
    posts = [(X, Y, Z) for X in (-3.5, 3.5) for Y in (-0.5, 0.5) for Z in (-0.5, 0.5, 1.5, 2.5, 3.5, 4.5)]
    put(w, posts, "iron")
    # 팔 고리 (Y 7..9): 기둥 X ±4.5, Z +4.5 → −4.5, 안쪽 가로대 Z −4.5
    loop = [(X, Y, Z) for X in (-4.5, 4.5) for Y in (7.5, 8.5) for Z in (4.5, 3.5, 2.5, 1.5, 0.5, -0.5, -1.5, -2.5, -3.5, -4.5)]
    loop += [(X, Y, -4.5) for X in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5) for Y in (7.5, 8.5)]
    put(w, loop, "leather")
    # 멜끈: 뒷면에 붙은 띠 (Y 10.5), 양 끝 리벳
    put(w, [(x + 0.5, 10.5, 4.5) for x in range(-8, 8)], "leather")
    put(w, [(-7.5, 10.5, 4.5), (6.5, 10.5, 4.5)], "iron_hi")


def redin_guard_shield():
    m = shield_mats("wood", "paint", "crest", "iron", "iron_hi", "rust", "leather", "leather_dark", "dark", "plank")
    w = weapon(m, kind="shield", seed=317)
    legend = {"O": ("iron", 5.5, 7.5), "W": ("plank", 5.5, 6.5), "B": ("plank", 5.5, 7.5)}
    draw(w, HEATER, legend, -9.5, 11.5)
    front, cut = heater_front()
    skin(w, front, {"p": "paint", "c": "crest", "w": "wood", "x": "dark"}, -9.5, 11.5, side=+1)
    # 베인 자국은 칠 한 겹 아래 나무까지 (두 칸)
    skin(w, cut, {"x": "dark"}, -9.5, 11.5, side=+1, depth=2)
    # 찌그러진 테 둘레와 테 밑의 녹
    put(w, [(8.5, 4.5, 7.5), (8.5, 4.5, 6.5)], "rust")
    put(w, [(-9.5, -1.5, 7.5), (-8.5, -2.5, 7.5), (2.5, -11.5, 7.5)], "rust")
    _heater_back(w)
    return w


# 방패 손 자세. 3인칭은 _common 의 공통 회전 (평소 [90, 90, 0], 막기 [−90, 0, 180]) 과 이동.
# 1인칭 (왼손): 평소는 화면 왼쪽 아래에 윗변과 앞면 귀퉁이, 막기는 십자선 아래 조금 왼쪽에 뒷면 (손잡이·끈) 이 보인다.
# 값은 _views 흉내 그림으로 맞췄다 [미확인 (클라)]
HEATER_FP = ([10, -35, 10], [-1.76, 0.0, -0.96], 0.62)
HEATER_FP_BLOCK = ([-40, 65, 120], [-0.53, 4.33, 0.4], 0.62)

# ─────────────────────────── 3.15 오스윈 순례자의 버클러 ───────────────────────────
# 지름 14 복셀 (0.44 블록), 판 두께 2, 가운데 쇠 징 (지름 6) 이 앞으로 2 복셀 나온다. 가죽 씌운 나무 판에 쇠 테.
# 낡음: 테 한 곳이 찌그러져 원이 1 복셀 납작하다 (오른쪽 아래), 가죽 갈라짐.
# 하나뿐인 것: 징에 찍은 작은 종 모양 (3×4 오목, ash0 오목과 ash3 테두리). 손종의 순례 패와 같은 표지.

HIDE = [
    "................",
    "......,.........",
    ".......,........",
    "................",
    "..:.............",
    "...........;;...",
    "................",
    "................",
    ".....,..........",
    "....,...........",
    "................",
    "..........:.....",
    "................",
    "..;.............",
    "..;.............",
    "................",
]


def _disc(r, cx=0.0, cy=0.0, flat=None):
    """반지름 r 의 원 안에 드는 복셀 가운데 (X, Y). flat = (각도 범위 함수) 로 테를 납작하게."""
    out = []
    n = int(r) + 1
    for i in range(-n, n):
        for j in range(-n, n):
            X, Y = i + 0.5, j + 0.5
            if (X - cx) ** 2 + (Y - cy) ** 2 <= r * r + 0.01:
                if flat and flat(X, Y):
                    continue
                out.append((X, Y))
    return out


def pilgrim_buckler():
    m = mats("iron", "iron_hi", "rust", "dark", "tin", "leather_dark", "wood_dark")
    m["hide"] = pmat(HIDE, {".": "rust2", ",": "rust1", ":": "rust3", ";": "rust1"})
    w = weapon(m, kind="small_shield", seed=315)
    dent = lambda X, Y: X + Y < -9.0 and False
    flat = lambda X, Y: (X - Y) > 9.6          # 오른쪽 아래 테가 한 칸 납작
    disc = _disc(7.0, flat=flat)
    inner = set(_disc(6.0, flat=lambda X, Y: (X - Y) > 8.2))
    cells = []
    for X, Y in disc:
        if (X, Y) in inner:
            cells += [(X, Y, 5.5, "wood_dark"), (X, Y, 6.5, "hide")]
        else:
            cells += [(X, Y, Z, "iron") for Z in (5.5, 6.5, 7.5)]
    for X, Y, Z, mat in cells:
        put(w, [(X, Y, Z)], mat)
    # 가운데 징: 지름 6, 두 칸 (가운데는 한 칸 더). 빛 받는 왼쪽 위가 밝다
    for X, Y in _disc(3.0):
        put(w, [(X, Y, 7.5)], "iron_hi" if X + Y > -0.1 else "iron")
        if X * X + Y * Y <= 4.6:
            put(w, [(X, Y, 8.5)], "iron_hi")
    put(w, [(-1.5, 1.5, 8.5), (-0.5, 1.5, 8.5), (-1.5, 0.5, 8.5)], "tin")      # 빛 받는 어깨
    # 찍은 종 (징 앞면을 한 칸 파낸다): 오목은 ash0, 둘레는 ash3 (tin)
    bell = [(0.5, 1.5), (-0.5, 0.5), (0.5, 0.5), (1.5, 0.5), (-0.5, -0.5), (0.5, -0.5), (1.5, -0.5),
            (-0.5, -1.5), (0.5, -1.5), (1.5, -1.5)]
    for X, Y in bell:
        put(w, [(X, Y, 8.5)], None)
        put(w, [(X, Y, 7.5)], "iron")
    put(w, [(0.5, 2.5, 7.5), (-1.5, -1.5, 7.5), (2.5, -1.5, 7.5)], "dark")   # 종 꼭지와 입술 끝의 그늘
    put(w, [(-0.5, 1.5, 8.5), (1.5, 1.5, 8.5), (-1.5, 0.5, 8.5)], "tin")    # 찍힌 테두리의 밝은 턱
    # 테 녹 (찌그러진 곳 둘레), 가죽 갈라짐은 칸 무늬
    put(w, [(5.5, -4.5, 7.5), (4.5, -5.5, 7.5), (-6.5, 2.5, 7.5)], "rust")
    # 손잡이: 징 뒤를 가로지르는 쇠 막대 (주먹 하나), 기둥은 주먹 밖 (X ±4.5)
    put(w, [(X, Y, Z) for X in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5) for Y in (-0.5, 0.5) for Z in (-0.5, 0.5)],
        "leather_dark")
    put(w, [(X, Y, Z) for X in (-4.5, 4.5) for Y in (-0.5, 0.5) for Z in (-0.5, 0.5, 1.5, 2.5, 3.5, 4.5)], "iron")
    return w


# ─────────────────────────── 3.18 볼크 가의 대방패 ───────────────────────────
# 높이 48 × 폭 28 복셀 (1.5 × 0.88 블록), 판 두께 3 + 쇠 1. 쥐는 점은 아래 끝에서 26 위 (위로 22, 아래로 26).
# 키 높은 연꼴: 위가 곧고 아래 끝은 둥근 뾰족. 앞면 위 절반을 쇠판이 덮고, 아래 판자 위에 가로 쇠띠 하나.
# 낡음: 아래 끝 쪼개짐, 쇠판 가장자리 녹, 큰 베인 자국 둘, 화살 박혔던 구멍 셋.
# 하나뿐인 것: 앞면을 비스듬히 가로질러 리벳으로 박은 진짜 쇠사슬 한 줄 (볼크 가 문장 "사슬", 장검 폼멜에서 지운 문장).

def _kite_halfwidth(Y):
    """연꼴 반폭 (복셀). 위 (Y 22) 에서 14, 옆이 아주 조금씩 좁아져 Y 0 에서 13, 그 아래로 둥글게 좁아져 Y −26 에서 끝."""
    if Y >= 0:
        hw = 13.0 + (Y / 22.0)
        if Y > 21:
            hw -= 0.6            # 위 모서리를 한 칸 깎는다
        return hw
    k = -Y / 26.0
    return max(0.6, 13.0 * (1 - k ** 1.5) ** 0.75)


def volk_greatshield():
    m = mats("wood_dark", "iron", "iron_hi", "tin", "rust", "dark", "leather", "leather_dark")
    m["plate"] = pmat(IRON_PLATE, {".": "ash1", "+": "ash2", ",": "ash0"})
    w = weapon(m, kind="greatshield", seed=318)
    rows = []
    for j in range(48):
        Y = 21.5 - j
        hw = _kite_halfwidth(Y)
        rows.append("".join("P" if abs(-13.5 + i) <= hw else " " for i in range(28)))
    # 아래 끝 쪼개짐: 끝의 가운데 한 줄을 비운다
    for Y in (-23.5, -22.5, -21.5):
        r = list(rows[int(21.5 - Y)])
        r[14] = " "
        rows[int(21.5 - Y)] = "".join(r)
    draw(w, rows, {"P": ("wood_dark", 5.5, 7.5)}, -13.5, 21.5)
    # 위 절반 쇠판 (Z 8.5), 가장자리 녹, 아래 판자 위 가로 쇠띠 (Y −6..−8)
    plate, band = [], []
    for j in range(48):
        Y = 21.5 - j
        hw = _kite_halfwidth(Y)
        for i in range(28):
            X = -13.5 + i
            if abs(X) > hw:
                continue
            if Y >= -0.5:
                plate.append((X, Y, "plate"))
            elif -7.5 <= Y <= -5.5:
                band.append((X, Y, "plate"))
    for X, Y, mat in plate + band:
        put(w, [(X, Y, 8.5)], mat)
    # 쇠판 윗모서리 빛, 쇠판 아랫단의 그늘
    put(w, [(X, 21.5, 8.5) for X in [x + 0.5 for x in range(-13, 6)]], "iron_hi")
    put(w, [(X, -0.5, 8.5) for X in [x + 0.5 for x in range(-14, 14)] if abs(X) <= 14], "iron")   # 쇠판 아랫단
    # 쇠판 가장자리의 녹 (덩어리 몇 개, 고르지 않게)
    put(w, [(X, Y, 8.5) for X, Y in [(-13.5, 12.5), (-13.5, 11.5), (-12.5, 11.5), (13.5, 3.5), (12.5, 2.5), (13.5, 2.5),
                                      (2.5, 0.5), (3.5, 0.5), (3.5, -0.5), (-7.5, -0.5), (-13.5, 20.5)]], "rust")
    # 리벳 (쇠판 가장자리, 고르지 않게)
    rivets = [(-12.5, 19.5), (-4.5, 20.5), (5.5, 19.5), (12.5, 18.5), (-12.5, 9.5), (12.5, 7.5), (-12.5, 1.5), (11.5, 0.5),
              (-10.5, -6.5), (0.5, -6.5), (10.5, -6.5)]
    put(w, [(X, Y, 9.5) for X, Y in rivets], "iron_hi")
    # 큰 베인 자국 둘 (쇠판을 갈랐다: 앞 한 칸을 그늘로), 화살 구멍 셋 (판자에 1 복셀, 앞 두 칸)
    cut1 = [(-8.5 + k, 15.5 - k * 0.5) for k in range(9)]
    cut2 = [(6.5 - k, 6.5 - k) for k in range(5)]
    for X, Y in cut1 + cut2:
        put(w, [(X, float(int(Y)) + 0.5, 8.5)], "dark")
    for X, Y in [(-6.5, -10.5), (4.5, -13.5), (-2.5, -17.5)]:
        put(w, [(X, Y, 7.5), (X, Y, 6.5)], "dark")
    # 아래 판자: 판자 사이 틈 (세로 그늘선 둘)
    for X in (-4.5, 5.5):
        for j in range(48):
            Y = 21.5 - j
            if Y < -8 and abs(X) <= _kite_halfwidth(Y) - 1:
                put(w, [(X, Y, 7.5)], "dark")
    # 사슬: 왼쪽 위 → 오른쪽 아래로 비스듬히. 누운 고리 (속이 빈 3×3, Z 9.5) 와 선 고리 (한 줄, Z 9.5..10.5) 가 번갈아
    # 맞물린다 (선 고리가 누운 고리의 구멍에 걸친다). 고리 하나에 쇠 빛 한 점, 녹 슨 고리 하나
    p0, p1 = (-11.0, 17.0), (10.0, -8.0)
    n = 15
    for k in range(n):
        t = k / (n - 1)
        cx = round(p0[0] + (p1[0] - p0[0]) * t - 0.5) + 0.5
        cy = round(p0[1] + (p1[1] - p0[1]) * t - 0.5) + 0.5
        if k % 2 == 0:
            ring = [(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]
            put(w, [(X, Y, 9.5) for X, Y in ring], "rust" if k == 8 else "iron_hi")
            put(w, [(cx, cy, 9.5)], None)
            put(w, [(cx - 1, cy + 1, 9.5)], "tin")
        else:
            put(w, [(cx, cy, 10.5), (cx, cy, 9.5)], "iron_hi")
            put(w, [(cx, cy, 10.5)], "tin" if k % 4 == 1 else "iron_hi")
    put(w, [(-12.5, 18.5, 9.5), (-12.5, 18.5, 10.5), (11.5, -9.5, 9.5), (11.5, -9.5, 10.5)], "iron_hi")  # 끝 리벳
    # 뒷면: 손잡이 (Y 0), 팔 고리 (Y 7..9), 위쪽 가죽 끈 (Y 14)
    put(w, [(X, Y, Z) for X in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5) for Y in (-0.5, 0.5) for Z in (-0.5, 0.5)], "leather_dark")
    put(w, [(X, Y, Z) for X in (-3.5, 3.5) for Y in (-0.5, 0.5) for Z in (-0.5, 0.5, 1.5, 2.5, 3.5, 4.5)], "iron")
    loop = [(X, Y, Z) for X in (-4.5, 4.5) for Y in (8.5, 9.5) for Z in (4.5, 3.5, 2.5, 1.5, 0.5, -0.5, -1.5, -2.5, -3.5, -4.5)]
    loop += [(X, Y, -4.5) for X in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5) for Y in (8.5, 9.5)]
    put(w, loop, "leather")
    put(w, [(x + 0.5, 15.5, 4.5) for x in range(-10, 10)], "leather")
    return w


# 버클러는 작아서 조금 더 위·가운데로, 대방패는 커서 아래·왼쪽으로 (막기에서 화면 왼쪽 아래 절반을 가린다)
BUCKLER_FP = ([10, -35, 10], [-2.56, 1.92, 0.0], 0.8)
BUCKLER_FP_BLOCK = ([-40, 65, 120], [-0.84, 4.81, 1.24], 0.8)
GREAT_FP = ([10, -35, 10], [-1.28, 0.96, -1.28], 0.5)
GREAT_FP_BLOCK = ([-40, 65, 120], [0.66, 3.05, -0.39], 0.5)

ITEMS = {
    "pilgrim_buckler": {
        "make": pilgrim_buckler, "kind": "small_shield", "use": "block",
        "display": C.shield_display(*BUCKLER_FP), "use_display": C.shield_block_display(*BUCKLER_FP_BLOCK),
    },
    "volk_greatshield": {
        "make": volk_greatshield, "kind": "greatshield", "use": "block",
        "display": C.shield_display(*GREAT_FP), "use_display": C.shield_block_display(*GREAT_FP_BLOCK),
    },
    "redin_guard_shield": {
        "make": redin_guard_shield, "kind": "shield", "use": "block",
        "display": C.shield_display(*HEATER_FP), "use_display": C.shield_block_display(*HEATER_FP_BLOCK),
    },
}
