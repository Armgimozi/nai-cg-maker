"""
가마지기의 쇠단지 (SPEC.md 3.19). 촉매 (가마 술).

놓는 법 (SPEC): 들손은 꼭대기를 Y 방향으로 6 복셀 곧게 편 반원이고, 그 곧은 곳이 주먹을 지나며 가운데가 쥐는 점이다.
단지는 −X 로 매달린다 (설계에서 단지의 위 = +X, 들손의 면 = XY 면). X 로 재어 들손 0..−5, 입술 −5..−6, 목 −6..−8,
몸통 −8..−16 (지름 9). 3인칭에서 −X 가 땅 쪽이라 단지가 주먹 아래로 매달린다.
배가 부른 작은 무쇠 단지, 좁은 목, 두꺼운 입술, 반원 들손 (굵기 2). 뚜껑 없음.
재료: 무쇠 (iron), 그을음 (dark: 입술 위와 몸통 윗부분, 곧은 경계), 바닥 둘레 녹 (rust), 불씨 (ember0).
낡음: 입술 한쪽 이 빠짐, 몸통 찌그러짐 하나, 들손 귀 한쪽을 철사로 고친 자리 (tin).
하나뿐인 것: 입 안 바닥에 눌어붙은 불씨 세 복셀. 스무 개 가운데 유일하게 빛을 허락한다 (SPEC 1.8): 요소의 light_emission 6,
  색은 ember0 (채도 제한 안의 가장 어두운 불씨) 한 가지. 셰이더 발광 알파는 쓰지 않는다.
"""
import math

from weapons import _common as C
from weapons._common import pmat, put, weapon
from weapons._mats import mats

EMBER = [
    "................",
    "....,...........",
    "................",
    "..........,.....",
    "................",
    "................",
    ".......,........",
    "................",
    "..,.............",
    "................",
    "...........,....",
    "................",
    "................",
    "....,...........",
    "................",
    "................",
]


def _radius(X):
    """단지 축 (X) 을 따라 바깥 반지름 (복셀)."""
    if X > -6:
        return 3.6            # 입술 (두껍다)
    if X > -8:
        return 2.9            # 좁은 목
    t = (X + 8) / -8.0        # 몸통 0 (어깨) → 1 (바닥)
    return 3.2 + 1.5 * math.sin(math.pi * min(1.0, t * 0.95 + 0.05)) ** 0.7 if t < 0.97 else 3.4


def kiln_pot():
    m = mats("iron", "iron_hi", "dark", "rust", "tin")
    m["ember"] = pmat(EMBER, {".": "ember0", ",": "rust0"}, light=6)
    w = weapon(m, kind="catalyst", seed=319)
    cells = {}
    for i in range(-16, -4):
        X = i + 0.5
        r = _radius(X)
        inner = r - 1.0 if X > -15 else -1      # 바닥 한 칸
        if X > -6:
            inner = 2.3                         # 입: 안지름 5 쯤
        for a in range(-5, 5):
            for b in range(-5, 5):
                Y, Z = a + 0.5, b + 0.5
                d = math.hypot(Y, Z)
                if d <= r + 0.05 and d > inner:
                    cells[(X, Y, Z)] = "iron_hi" if (d > r - 1.0 or X < -15) else "dark"
    # 찌그러짐: 몸통 앞 (+Z) 아래 한 곳을 한 칸 눌렀다
    for X in (-11.5, -12.5):
        for Y in (-1.5, -0.5):
            cells.pop((X, Y, 4.5), None)
            cells[(X, Y, 3.5)] = "iron_hi"
    # 입술 이 빠짐 (−Y 쪽 한 칸)
    for X in (-5.5,):
        for Y, Z in ((-3.5, 0.5), (-3.5, -0.5)):
            cells.pop((X, Y, Z), None)
    # 그을음: 입술 위 (X > −6) 와 몸통 윗부분 (X > −10) 의 바깥 겉. 경계는 곧은 한 줄 (X = −10)
    for (X, Y, Z), mat in list(cells.items()):
        if X > -10 and math.hypot(Y, Z) > _radius(X) - 1.0:
            cells[(X, Y, Z)] = "iron"
        if X < -14 and math.hypot(Y, Z) > _radius(X) - 1.2:
            cells[(X, Y, Z)] = "rust"
    # 빛 받는 어깨 (왼쪽 위 = +Y 앞쪽) 한 줄
    for X in (-8.5, -9.5):
        for Y, Z in ((3.5, 2.5), (2.5, 3.5)):
            if (X, Y, Z) in cells:
                cells[(X, Y, Z)] = "tin"
    for (X, Y, Z), mat in cells.items():
        put(w, [(X, Y, Z)], mat)
    # 불씨: 입 안 바닥 (X −14.5) 세 칸, 고르지 않게
    put(w, [(-14.5, 1.5, 1.5), (-14.5, 0.5, 1.5), (-14.5, -1.5, -0.5)], "ember")
    # 들손: 반원 (XY 면, Z −0.5..0.5) 의 꼭대기를 X 0 에서 Y −3..3 곧게. 귀는 입술 (X −5) 의 ±Y 에
    handle = set()
    for k in range(0, 181, 3):
        a = math.radians(k)
        Y = 5.0 * math.cos(a)
        X = -5.0 + 5.0 * math.sin(a)
        if abs(Y) < 3.0:
            X = 0.0
        handle.add((round(X - 0.5) + 0.5 if X < 0 else 0.5, round(Y - 0.5) + 0.5))
        handle.add((round(X - 0.5) + 0.5 if X < 0 else -0.5, round(Y - 0.5) + 0.5))
    for X, Y in handle:
        if X < -5.0:
            continue
        put(w, [(X, Y, -0.5), (X, Y, 0.5)], "iron_hi")
    put(w, [(0.5, Y, 0.5) for Y in (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)], "tin")   # 손에 닳은 꼭대기
    # 들손 귀 (입술 양옆의 고리) 와 한쪽을 철사로 고친 자리
    put(w, [(-5.5, 4.5, -0.5), (-5.5, 4.5, 0.5), (-4.5, 4.5, -0.5), (-4.5, 4.5, 0.5)], "iron")
    put(w, [(-5.5, -4.5, -0.5), (-5.5, -4.5, 0.5), (-4.5, -4.5, -0.5), (-4.5, -4.5, 0.5)], "iron")
    put(w, [(-3.5, -4.5, 1.5), (-3.5, -4.5, -1.5), (-4.5, -5.5, 0.5), (-3.5, -5.5, -0.5)], "tin")
    return w


# 1인칭: 단지가 주먹 아래로 매달리고 입이 조금 화면 쪽으로 기울어 입 안 (불씨) 이 보인다. 화면 오른쪽 아래 [미확인 (클라)]
FP = ([-180, 80, -60], [-3.2, 6.72, 0.32])

ITEMS = {
    "kiln_pot": {"make": kiln_pot, "kind": "catalyst", "use": "same", "display": C.catalyst_display(*FP)},
}
