"""
레딘 성벽 단궁 (SPEC.md 3.13). 쉬는 모양과 당김 셋 (_3d, _3d_pulling_0..2).

설계 축 (SPEC 1.2): 활대가 ±Y, 시위가 +X 쪽, 화살은 −X 로 난다. 쥐는 점 (설계 원점) = 화살 받침 (손잡이 가운데).
높이 40 복셀 (1.25 블록), 쥐는 점에서 위아래 20. 나무 하나로 깎은 짧은 활: 가운데 손잡이가 두껍고 끝으로 가늘어진다.
쉬는 활은 끝이 시위 쪽 (+X) 으로 5 복셀 휜다 (시위 높이 5 복셀 ≈ 14 cm). 끝에 뿔 고자.
낡음: 활대 결 갈라짐 (어두운 줄), 손잡이 가죽 닳음.
하나뿐인 것: 아래 활대에 덧댄 부목을 끈으로 감은 자리 (6 복셀). 한 번 부러진 활.
당긴 모양: 시위 가운데가 +X 로 (당김 0 / 1 / 2 = 9 / 14 / 18 복셀), 끝이 조금 더 휘고 안쪽으로 온다. 화살을 메긴다.
"""
import math

import numpy as np

from weapons import _common as C
from weapons._common import pmat, put, weapon
from weapons._mats import mats

HALF = 20.0          # 쥐는 점에서 고자 끝까지 (복셀)
PULLS = (0.0, 9.0, 14.0, 18.0)


def _stave_x(Y, bend):
    """활대 가운데 선의 X (쉬는 활 bend = 5): 손잡이 (|Y| ≤ 3) 는 곧고 그 밖은 끝으로 갈수록 +X 로."""
    a = max(0.0, abs(Y) - 3.0) / (HALF - 3.0)
    return bend * a ** 1.6


def _make(pull):
    m = mats("wood", "wood_dark", "wood_worn", "leather", "leather_dark", "bone", "string", "cord", "iron", "iron_hi")
    m["fletch"] = pmat("a", {"a": "ash2"})
    w = weapon(m, kind="bow", seed=313)
    bend = 5.0 + 3.5 * (pull / 18.0)
    shrink = 1.0 - 0.06 * (pull / 18.0)          # 당기면 끝이 조금 안쪽으로
    tip = HALF * shrink
    # 활대: 줄마다 X 두께 (손잡이 3 → 끝 2), Z 폭 2. 손잡이 (가죽) 는 활대 폭의 1.5 배쯤 (판정 B 활 3)
    for j in range(-21, 21):
        Y = j + 0.5
        if abs(Y) > tip:
            continue
        x0 = _stave_x(Y / shrink, bend)
        t = abs(Y) / tip
        thick = 3 if abs(Y) <= 3 else (3 if t < 0.55 else 2)
        zz = (-0.5, 0.5)
        xs = [round(x0 - 0.5) + 0.5 - k for k in range(thick)]   # 배 (시위 쪽) 에서 등 (−X) 으로
        if abs(Y) <= 3:
            xs = [1.5, 0.5, -0.5]
        mat = "leather" if abs(Y) <= 3 else "wood"
        for X in xs:
            for Z in zz:
                put(w, [(X, Y, Z)], mat)
        # 결 갈라짐: 위 활대 등 쪽에 어두운 줄 셋
        if Y in (8.5, 9.5, 10.5) or Y in (-12.5,):
            put(w, [(xs[-1], Y, 0.5)], "wood_dark")
        # 손때: 손잡이 바로 위아래 한 칸 밝게
        if 3 < abs(Y) <= 5:
            for X in xs:
                put(w, [(X, Y, Z) for Z in zz], "wood_worn")
    # 손잡이 가죽 닳은 자리 (아래 끝 앞면)
    put(w, [(-0.5, -2.5, 0.5), (0.5, -2.5, 0.5)], "leather_dark")
    # 뿔 고자 (끝 2 복셀)
    for sgn in (1, -1):
        Yt = sgn * (tip - 0.5)
        x0 = _stave_x(Yt / shrink, bend)
        Xc = round(x0 - 0.5) + 0.5
        for k in range(2):
            Y = Yt - sgn * k
            put(w, [(Xc, Y, -0.5), (Xc, Y, 0.5), (Xc - 1, Y, -0.5), (Xc - 1, Y, 0.5)], "bone")
    # 부목: 아래 활대 등 (−X) 에 덧댄 짧은 막대 (Y −13..−7) 를 끈으로 세 번 감았다. 감은 끈은 부목·활대와 같은 높이
    # (끈 칠만, 튀어나오지 않는다. 판정 B 활 1)
    for j in range(-13, -7):
        Y = j + 0.5
        x0 = _stave_x(Y / shrink, bend)
        Xb = round(x0 - 0.5) + 0.5 - 2
        put(w, [(Xb, Y, -0.5), (Xb, Y, 0.5)], "wood_dark")
        if Y in (-12.5, -10.5, -8.5):
            put(w, [(Xb + dx, Y, Z) for dx in (0, 1, 2) for Z in (-0.5, 0.5)], "cord")
    # 시위: 고자에서 고자로, 당기면 가운데 (쥐는 점 높이) 가 +X 로
    tipx = _stave_x(tip / shrink, bend) + 0.5
    nock = max(tipx, pull + 1.0) if pull else tipx
    pts = []
    for j in range(-int(tip) + 1, int(tip)):
        Y = j + 0.5 if j < int(tip) - 1 else j + 0.5
        f = abs(Y) / tip
        X = nock + (tipx - nock) * f
        pts.append((X, Y))
    for X, Y in pts:
        put(w, [(round(X - 0.5) + 0.5, Y, 0.5)], "string")
    # 화살 (당긴 모양만): 오늬는 시위 가운데, 촉은 활대 앞 (−X)
    if pull:
        Xn = round(nock - 0.5) + 0.5
        length = 26
        for k in range(length):
            X = Xn - k
            if X < -23.5:
                break
            put(w, [(X, 0.5, 0.5)], "wood_worn")
            if k < 4:      # 깃 (위아래로 한 칸씩, 회색 깃 둘)
                put(w, [(X - 1, 1.5, 0.5), (X - 1, -0.5, 0.5)], "fletch")
        Xh = max(-23.5, Xn - length + 1)
        put(w, [(Xh, 0.5, 0.5), (Xh + 1, 1.5, 0.5), (Xh + 1, -0.5, 0.5)], "iron_hi")
        put(w, [(Xh - 1, 0.5, 0.5)], "iron") if Xh - 1 >= -23.5 else None
    return w


def wall_shortbow():
    return [_make(p) for p in PULLS]


# 손 자세 (_views 흉내 그림으로 맞추고 실제 클라이언트로 보았다) [확인 (클라)]
# 평소: 3인칭은 활대가 서고 화살 쪽 (−X) 이 앞 (팔을 내린 채 옆에 든다), 1인칭은 화면 오른쪽 아래에 비스듬히.
# 당김 (팔을 앞으로 든 BOW_AND_ARROW 자세 + 바닐라 1인칭 활 몸짓): 활대가 거의 서고 화살이 십자선 쪽을 본다.
# 평소 1인칭: 활을 옆모습으로 세워 (시위가 오른쪽, 활대가 위로 조금 왼쪽) 화면 오른쪽에 거의 다 보이게. 바닐라 활처럼
# 비스듬히 눕히면 위 활대 한 줄만 보여 막대로 읽혔다 (실제 클라이언트, 2026-10-07)
_IDLE_FP = C.fp_frame((1, 0.2, 0.6), (-0.5, 1, -0.2), (0.80, 0.64, -0.85))
IDLE = C.bow_display(tp_rot=C.BOW_TP_ROT, fp_rot=_IDLE_FP[0], fp_t=_IDLE_FP[1])
PULL = C.bow_display(tp_rot=C.BOW_PULL_TP_ROT, fp_rot=[0, -75, -20], fp_t=[-3.13, 5.02, -3.93], fp_s=0.6)

ITEMS = {
    "wall_shortbow": {"make": wall_shortbow, "kind": "bow", "use": "bow", "display": IDLE, "pull_display": PULL},
}
