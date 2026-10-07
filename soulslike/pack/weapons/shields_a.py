"""
A 의 방패 셋 (SPEC.md 3.15, 3.17, 3.18): 오스윈 순례자의 버클러, 레딘 경비대 방패, 볼크 가의 대방패.

설계 축 (SPEC 1.2): +Y 위, +Z 앞면 (적을 보는 칠한 면), 손잡이는 뒤 (−Z) 에 있고 그 가운데가 쥐는 점 (설계 원점).
판의 뒷면은 Z = +5 에 둔다: 마인크래프트 팔은 쥐는 점에서 2 픽셀 (4 복셀) 까지 차 있으므로 판이 그보다 바깥에 있어야
3인칭에서 팔이 판을 뚫고 나오지 않는다. 손잡이는 쥐는 점을 지나는 X 방향 막대 (팔과 직각, 주먹이 감싼다).
아래팔은 쥐는 점에서 +Y 로 뻗으므로 (팔꿈치 쪽) 팔 끈은 그 둘레 (|X|, |Z| ≤ 4 밖) 를 감는다.

앞면은 글자 그림으로 꼴을 찍고 (_common.draw, 판 = 나무), 칠·문장·벗겨진 자리·베인 자국은 겉 칠 (_common.skin) 로 얹는다.
"""
import math

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


# ─────────────────────────── 손잡이 (네 방패가 같은 짜임) ───────────────────────────
# 판정 B 버클러 3: 손잡이가 판에서 뒤로 길게 뻗으면 옆에서 막대사탕처럼 보인다. 손잡이 막대는 판 바로 뒤 (Z 2.5..3.5) 에서 판과
# 나란히 가로지르고, 짧은 다리 둘 (X ±3.5) 이 판에 박힌다. 쥐는 점 (원점) 의 주먹은 Z −4..+4 를 차지하므로 막대는 주먹 안에
# 들어가 "쥔" 것으로 보인다. 팔 끈은 아래팔 둘레 (|X|, |Z| ≤ 4 밖) 를 감는다.

def _grip(w, bar="leather_dark", post="iron", back=4.5):
    put(w, [(X, Y, Z) for X in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5) for Y in (-0.5, 0.5) for Z in (2.5, 3.5)], bar)
    put(w, [(X, Y, Z) for X in (-3.5, 3.5) for Y in (-0.5, 0.5) for Z in (2.5, 3.5, back)], post)


# ─────────────────────────── 3.17 레딘 경비대 방패 ───────────────────────────
# 높이 26 × 폭 20 복셀 (0.81 × 0.63 블록). 다리미꼴: 위가 곧고 아래로 좁아져 둥근 뾰족끝. 쇠 테 한 칸.
# 앞면이 가로로 볼록하다: 바깥 세 줄 두께 2, 그 안 세 줄 3, 가운데 여섯 줄 4 (칠 위에서도 계단 그늘이 보인다).
# 쥐는 점 = 손잡이 가운데 = 판 가운데보다 한 칸 위.
# 낡음: 칠은 테 둘레, 아래 끝, 베인 자국 둘레에서 나뭇결을 따라 세로로 벗겨졌다. 테 찌그러짐 (오른쪽, Y 4).
# 베인 자국: 오른쪽 위에서 비스듬히 이어진 한 줄 (두 칸 폭 계단, 칠 아래 나무까지 두 칸 깊이), 테를 갈랐다.
# 하나뿐인 것: 앞면의 성문 문장. 아치 안에 닫힌 쇠살문 (세로살 넷, 끝이 아래로 뾰족, 가로보 둘), 40 % 남짓 벗겨져 나무가
# 드러났고 바랜 핏빛 두 단 (blood0, blood1) 만 쓴다.

HEATER = [
    # x: -9.5 ... +9.5 (20 칸), 맨 윗줄 Y = 11.5.  O 테, W 판 (2), B 판 (3), C 가운데 판 (4)
    "OOOOOOOOOOOO  OOOOOO",   # 11.5  (베인 자국이 테를 갈랐다)
    "OWWWBBBCCCCCCBBBWWWO",   # 10.5
    "OWWWBBBCCCCCCBBBWWWO",
    "OWWWBBBCCCCCCBBBWWWO",
    "OWWWBBBCCCCCCBBBWWWO",
    "OWWWBBBCCCCCCBBBWWWO",
    "OWWWBBBCCCCCCBBBWWWO",   # 5.5
    "OWWWBBBCCCCCCBBBWWO ",   # 4.5   테 찌그러짐 (한 칸 안으로)
    "OWWWBBBCCCCCCBBBWWWO",
    "OWWWBBBCCCCCCBBBWWWO",
    "OWWWBBBCCCCCCBBBWWWO",
    "OWWWBBBCCCCCCBBBWWWO",   # 0.5
    "OWWWBBBCCCCCCBBBWWWO",   # -0.5
    "OWWWBBBCCCCCCBBBWWWO",   # -1.5
    " OWWBBBCCCCCCBBBWWO ",   # -2.5
    " OWWBBBCCCCCCBBBWWO ",
    "  OWBBBCCCCCCBBBWO  ",   # -4.5
    "  OWBBBCCCCCCBBBWO  ",
    "   OWBBCCCCCCBBWO   ",   # -6.5
    "   OWBBCCCCCCBBWO   ",
    "    OWBCCCCCCBWO    ",   # -8.5
    "     OWCCCCCCWO     ",   # -9.5
    "      OWCCCCWO      ",   # -10.5
    "       OWCCWO       ",   # -11.5
    "        OBBO        ",   # -12.5
    "         OO         ",   # -13.5
]
# 문장 (9 × 10, 앞면 칸 (6..14, 2..11) 에 얹는다): c 바랜 핏빛 (blood1), d 그늘진 핏빛 (blood0), w 칠이 벗겨진 나무, '.' 칠
PORTCULLIS = [
    "..cwccd..",   # 아치 (나뭇결을 따라 한 칸 벗겨졌다)
    ".c.....d.",   # 아치 어깨
    "ccccwcddd",   # 윗 가로보 (아치가 서는 줄)
    ".c.cwc.d.",   # 세로살 넷 (1, 3, 5, 7). 가운데로 나뭇결을 따라 세로로 벗겨진 줄 (w)
    ".c.cwc.d.",
    "cccdwd...",   # 둘째 가로보 (오른쪽은 칠째 떨어졌다)
    ".c.dw....",
    ".c.c.....",
    ".d.c.....",
    ".d.d.....",   # 살 끝 (아래로 뾰족한 끝, 그늘진 핏빛)
]
# 칠이 벗겨진 자리 (앞면 칸, 세로로 나뭇결을 따라): 테 둘레, 아래 끝, 베인 자국 둘레
HEATER_CHIPS = [(1, 2), (1, 3), (1, 4), (2, 3), (18, 7), (18, 8), (18, 9), (1, 12), (1, 13), (2, 13),
                (9, 20), (9, 21), (10, 21), (10, 22), (9, 23), (11, 18), (11, 19),
                (14, 1), (15, 2), (14, 3), (12, 4), (13, 5), (10, 6), (11, 7)]
# 베인 자국: 오른쪽 위 (테의 끊긴 곳) 에서 왼쪽 아래로 이어진 두 칸 폭 계단
HEATER_CUT = [(13, 1), (12, 1), (12, 2), (11, 2), (11, 3), (10, 3), (10, 4), (9, 4), (9, 5), (8, 5), (8, 6)]


def heater_front():
    rows = [[" "] * 20 for _ in HEATER]
    for j, row in enumerate(HEATER):
        for i, ch in enumerate(row):
            if ch in "WBC":
                rows[j][i] = "p"
    for dj, line in enumerate(PORTCULLIS):
        for di, ch in enumerate(line):
            if ch in "cdw":
                rows[2 + dj][6 + di] = ch
    for i, j in HEATER_CHIPS:
        if rows[j][i] != " ":
            rows[j][i] = "w"
    cut = [[" "] * 20 for _ in HEATER]
    for i, j in HEATER_CUT:
        rows[j][i] = "x"
        cut[j][i] = "x"
    return ["".join(r) for r in rows], ["".join(r) for r in cut]


def _heater_back(w):
    """뒷면: 손잡이 (판 바로 뒤, 판과 나란히), 팔을 끼우는 가죽 고리 하나, 판을 가로지른 멜끈 하나."""
    _grip(w)
    # 팔 고리 (Y 7..9): 기둥 X ±4.5, Z +4.5 → −4.5, 안쪽 가로대 Z −4.5
    loop = [(X, Y, Z) for X in (-4.5, 4.5) for Y in (7.5, 8.5) for Z in (4.5, 3.5, 2.5, 1.5, 0.5, -0.5, -1.5, -2.5, -3.5, -4.5)]
    loop += [(X, Y, -4.5) for X in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5) for Y in (7.5, 8.5)]
    put(w, loop, "leather")
    # 멜끈: 뒷면에 붙은 띠 (Y 10.5), 양 끝 리벳 (띠와 같은 높이)
    put(w, [(x + 0.5, 10.5, 4.5) for x in range(-8, 8)], "leather")
    put(w, [(-7.5, 10.5, 4.5), (6.5, 10.5, 4.5)], "iron_hi")


def redin_guard_shield():
    m = shield_mats("wood", "paint", "crest", "iron", "iron_hi", "rust", "leather", "leather_dark", "dark", "plank")
    m["crest_dark"] = pmat(CREST, {".": "blood0", ":": "blood0"})
    w = weapon(m, kind="shield", seed=317)
    legend = {"O": ("iron", 5.5, 7.5), "W": ("plank", 5.5, 6.5), "B": ("plank", 5.5, 7.5), "C": ("plank", 5.5, 8.5)}
    draw(w, HEATER, legend, -9.5, 11.5)
    front, cut = heater_front()
    skin(w, front, {"p": "paint", "c": "crest", "d": "crest_dark", "w": "wood", "x": "dark"}, -9.5, 11.5, side=+1)
    # 베인 자국은 칠 한 겹 아래 나무까지 (두 칸)
    skin(w, cut, {"x": "dark"}, -9.5, 11.5, side=+1, depth=2)
    # 찌그러진 테 둘레와 테 밑의 녹
    put(w, [(8.5, 4.5, 7.5), (8.5, 4.5, 6.5)], "rust")
    put(w, [(-9.5, -1.5, 7.5), (-8.5, -2.5, 7.5), (2.5, -11.5, 7.5)], "rust")
    _heater_back(w)
    return w


# 방패 손 자세. 3인칭은 _common 의 공통 회전 (평소 [90, 90, 0], 막기 [−145, 40, −180]) 과 이동.
# 1인칭 (왼손): 평소는 화면 왼쪽 아래에 윗변과 앞면 귀퉁이, 막기는 십자선 아래 조금 왼쪽에 뒷면 (손잡이·끈) 이 보인다.
# 값은 _views 흉내 그림으로 맞추고 실제 클라이언트로 보았다 [확인 (클라)]
HEATER_FP = ([10, -35, 10], [-1.76, 0.0, -0.96], 0.62)
HEATER_FP_BLOCK = ([-40, 65, 120], [-0.53, 4.33, 0.4], 0.62)

# ─────────────────────────── 3.15 오스윈 순례자의 버클러 ───────────────────────────
# 지름 14 복셀 (0.44 블록), 판 두께 2, 가운데 쇠 징은 세 단 둥근 돔 (지름 8, 6, 4, 앞으로 세 칸). 가죽 씌운 나무 판에 쇠 테,
# 테 안쪽 둘레에 가죽을 붙든 못 여덟 (고르지 않게, 한 칸 나온다).
# 낡음: 테 한 곳이 찌그러져 원이 1 복셀 납작하다 (오른쪽 아래), 가죽 갈라짐.
# 하나뿐인 것: 징에 찍은 작은 종 (3×4 오목: 안은 ash0, 빛 받는 왼쪽 위 테두리만 ash3). 손종의 순례 패와 같은 표지.

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


# 찍은 종: 꼭지 1, 몸 3 (두 줄), 벌어진 입술 5. 동그란 징 한가운데의 어두운 네모는 눈동자로 읽혀서 (판정 B 버클러 1·2)
# 입술을 넓혀 종의 꼴이 먼저 읽히게 했다
BELL_STAMP = [(-0.5, 2.5), (-1.5, 1.5), (-0.5, 1.5), (0.5, 1.5), (-1.5, 0.5), (-0.5, 0.5), (0.5, 0.5),
              (-2.5, -0.5), (-1.5, -0.5), (-0.5, -0.5), (0.5, -0.5), (1.5, -0.5)]


def pilgrim_buckler():
    m = mats("iron", "iron_hi", "rust", "dark", "tin", "leather_dark", "wood_dark")
    m["hide"] = pmat(HIDE, {".": "rust2", ",": "rust1", ":": "rust3", ";": "rust1"})
    w = weapon(m, kind="small_shield", seed=315)
    flat = lambda X, Y: (X - Y) > 9.6          # 오른쪽 아래 테가 한 칸 납작
    disc = _disc(7.0, flat=flat)
    inner = set(_disc(6.0, flat=lambda X, Y: (X - Y) > 8.2))
    for X, Y in disc:
        if (X, Y) in inner:
            put(w, [(X, Y, 5.5)], "wood_dark")
            put(w, [(X, Y, 6.5)], "hide")
        else:
            put(w, [(X, Y, Z) for Z in (5.5, 6.5, 7.5)], "iron")
    # 테 안쪽 둘레의 못 여덟 (가죽 위로 한 칸, 고르지 않은 간격)
    for a in (8, 52, 97, 140, 188, 231, 279, 322):
        t = math.radians(a)
        X = round(5.0 * math.cos(t) - 0.5) + 0.5
        Y = round(5.0 * math.sin(t) - 0.5) + 0.5
        put(w, [(X, Y, 7.5)], "iron_hi")
    # 가운데 징: 세 단 돔 (지름 8 → 6 → 4, 앞으로 세 칸). 빛 받는 왼쪽 위가 밝다
    for r, Z in ((4.0, 7.5), (3.0, 8.5), (2.0, 9.5)):
        for X, Y in _disc(r):
            put(w, [(X, Y, Z)], "iron_hi" if Y - X > -0.5 else "iron")
    # 찍은 종: 가장 앞 칸을 한 칸 파내고 바닥을 ash0 으로, 빛 받는 왼쪽 위 테두리만 ash3 (tin)
    for X, Y in BELL_STAMP:
        col = [Z for Z in (10.5, 9.5, 8.5, 7.5) if w.grid[int(round(X + w.CX - 0.5)), int(round(Y + w.CY - 0.5)),
                                                    int(round(Z + w.CZ - 0.5))]]
        if col:
            put(w, [(X, Y, col[0])], None)
            put(w, [(X, Y, col[0] - 1)], "dark")
    put(w, [(-1.5, 2.5, 9.5), (-2.5, 1.5, 9.5), (-3.5, 0.5, 8.5), (-0.5, 3.5, 8.5)], "tin")
    # 테 녹 (찌그러진 곳 둘레)
    put(w, [(5.5, -4.5, 7.5), (4.5, -5.5, 7.5), (-6.5, 2.5, 7.5)], "rust")
    _grip(w)
    return w


# ─────────────────────────── 3.18 볼크 가의 대방패 ───────────────────────────
# 높이 48 × 폭 26 복셀 (1.5 × 0.81 블록), 판 두께 3 + 쇠 1. 쥐는 점은 아래 끝에서 26 위 (위로 22, 아래로 26).
# 연꼴 한 줄: 위 가장자리는 곧고 옆은 거의 곧게 내려오다 아래 절반에서 뾰족하게 모인다. 위 절반은 쇠판이 같은 꼴을 따라 덮고,
# 쇠판 가장자리를 따라 고른 간격의 리벳 줄. 아래 판자 위에 가로 쇠띠 하나.
# 낡음: 아래 끝 쪼개짐, 쇠판 가장자리 녹, 큰 베인 자국 둘, 화살 박혔던 구멍 셋 (고르지 않게).
# 하나뿐인 것: 앞면을 20° 남짓 비스듬히 가로질러 리벳으로 박은 진짜 쇠사슬 한 줄 (누운 고리와 선 고리가 번갈아, 끝은 꼴 안).

def _kite_halfwidth(Y):
    """연꼴 반폭 (복셀 가운데까지). 위 (Y 21.5) 12.6, 옆은 Y −2 까지 거의 곧게, 그 아래로 뾰족하게 모여 Y −26 에서 끝."""
    if Y >= 21:
        return 12.6
    if Y >= -2:
        return 13.4 - 0.035 * (21.5 - Y)
    t = (2 + Y) / -24.5
    return max(0.0, 12.6 * (1 - t) ** 0.62)


def volk_greatshield():
    m = mats("wood_dark", "iron", "iron_hi", "tin", "rust", "dark", "leather", "leather_dark")
    m["plate"] = pmat(IRON_PLATE, {".": "ash1", "+": "ash2", ",": "ash0"})
    w = weapon(m, kind="greatshield", seed=318)
    inside = lambda X, Y: abs(X) <= _kite_halfwidth(Y)
    rows = []
    for j in range(48):
        Y = 21.5 - j
        rows.append("".join("P" if inside(-13.5 + i, Y) else " " for i in range(28)))
    for Y in (-23.5, -22.5, -21.5):                               # 아래 끝 쪼개짐
        r = list(rows[int(21.5 - Y)])
        r[14] = " "
        rows[int(21.5 - Y)] = "".join(r)
    draw(w, rows, {"P": ("wood_dark", 5.5, 7.5)}, -13.5, 21.5)
    # 위 절반 쇠판 (Z 8.5, 꼴을 그대로 따른다) 과 아래 판자 위 가로 쇠띠 (Y −6..−8)
    for j in range(48):
        Y = 21.5 - j
        for i in range(28):
            X = -13.5 + i
            if not inside(X, Y):
                continue
            if Y >= -0.5 or -7.5 <= Y <= -5.5:
                put(w, [(X, Y, 8.5)], "plate")
    put(w, [(X, 21.5, 8.5) for X in [x + 0.5 for x in range(-12, 6)]], "iron_hi")          # 윗모서리 빛
    put(w, [(X, -0.5, 8.5) for X in [x + 0.5 for x in range(-13, 13)] if inside(X, -0.5)], "iron")   # 쇠판 아랫단
    put(w, [(X, Y, 8.5) for X, Y in [(-12.5, 12.5), (-12.5, 11.5), (12.5, 3.5), (12.5, 2.5), (2.5, 0.5), (3.5, 0.5),
                                      (-7.5, -0.5), (-11.5, 20.5)]], "rust")
    # 리벳: 쇠판 가장자리를 따라 고른 간격 (세 칸마다, 한 칸 나온다). 아랫단과 쇠띠에도
    rivets = [(-11.5, Y) for Y in (19.5, 16.5, 13.5, 10.5, 7.5, 4.5, 1.5)] + \
             [(11.5, Y) for Y in (19.5, 16.5, 13.5, 10.5, 7.5, 4.5, 1.5)] + \
             [(X, 20.5) for X in (-8.5, -5.5, -2.5, 0.5, 3.5, 6.5, 9.5)] + \
             [(X, -0.5) for X in (-9.5, -6.5, -3.5, 2.5, 5.5, 8.5)] + [(X, -6.5) for X in (-10.5, -0.5, 9.5)]
    put(w, [(X, Y, 9.5) for X, Y in rivets], "iron_hi")
    # 큰 베인 자국 둘 (쇠판을 갈랐다: 앞 한 칸을 그늘로, 두 칸 폭 계단으로 이어진다)
    for k in range(8):
        put(w, [(-8.5 + k, 15.5 - k * 0.5 // 1, 8.5)], "dark")
    for k in range(5):
        put(w, [(6.5 - k, 6.5 - k, 8.5), (5.5 - k, 6.5 - k, 8.5)], "dark")
    # 화살 박혔던 구멍 셋 (판자, 크기와 자리가 고르지 않다)
    for X, Y in [(-6.5, -10.5), (-5.5, -10.5), (4.5, -13.5), (-2.5, -17.5), (-2.5, -18.5)]:
        put(w, [(X, Y, 7.5), (X, Y, 6.5)], "dark")
    # 아래 판자: 판자 사이 틈 (세로 그늘선 둘)
    for X in (-4.5, 5.5):
        for j in range(48):
            Y = 21.5 - j
            if Y < -8 and abs(X) <= _kite_halfwidth(Y) - 1:
                put(w, [(X, Y, 7.5)], "dark")
    # 사슬: 왼쪽 위 → 오른쪽 아래로 20° (끝 리벳 둘은 꼴 안). 누운 고리 (속이 빈 3×3, Z 9.5) 와 선 고리 (세로 한 줄,
    # Z 9.5..10.5) 가 번갈아 맞물린다. 고리 하나에 쇠 빛 한 점, 녹 슨 고리 하나
    p0, p1 = (-10.0, 15.0), (10.0, 7.5)
    n = 11
    for k in range(n):
        t = k / (n - 1)
        cx = round(p0[0] + (p1[0] - p0[0]) * t - 0.5) + 0.5
        cy = round(p0[1] + (p1[1] - p0[1]) * t - 0.5) + 0.5
        if k % 2 == 0:
            ring = [(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]
            put(w, [(X, Y, 9.5) for X, Y in ring], "rust" if k == 6 else "iron_hi")
            put(w, [(cx, cy, 9.5)], None)
            put(w, [(cx - 1, cy + 1, 9.5)], "tin")
        else:
            put(w, [(cx - 1, cy, 10.5), (cx, cy, 10.5), (cx + 1, cy, 10.5)], "iron_hi")
            put(w, [(cx, cy, 10.5)], "tin" if k % 4 == 1 else "iron_hi")
    put(w, [(-11.5, 15.5, 9.5), (-11.5, 15.5, 10.5), (11.5, 7.5, 9.5), (11.5, 7.5, 10.5)], "iron_hi")  # 끝 리벳
    # 뒷면: 손잡이 (Y 0, 판과 나란히), 팔 고리 (Y 8..10), 위쪽 가죽 끈 (Y 15)
    _grip(w)
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
