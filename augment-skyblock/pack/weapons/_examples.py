"""
wkit 사용 예시 (API 를 보여 주는 용도일 뿐, 디자인의 기준이 아니다 — 실제 무기는 각자 새로 디자인할 것).

모듈 규칙 (pack/weapons/<그룹>.py)
  WEAPONS = {"무기id": 함수}  함수는 인자 없이 Weapon 하나를 돌려준다. 활은 [평소, 당김1, 당김2, 당김3] 네 개의 리스트.
  python3 <모듈>.py 로 실행하면 미리보기를 pack/weapons/preview/<그룹>.png 로 만든다 (아래 main 참고).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wkit import Mat, Weapon, preview_sheet  # noqa: E402


def example_sword():
    m = {
        "rim": Mat(["#4a4660", "#8e8aa8", "#c9c6dc", "#f4f2ff"], "metal", seed=1),
        "core": Mat(["#2a0a5a", "#6a2ad8", "#a86bff", "#e8d0ff"], "flow", glow=True, seed=2),   # 움직이는 빛 심지
        "gold": Mat(["#6a4410", "#b07a1c", "#e8b840", "#fff0a0"], "metal", seed=3),
        "gem": Mat(["#3a0a6a", "#7a2ae0", "#c08aff", "#ffffff"], "sparkle", glow=True, seed=4),
        "grip": Mat(["#2a0f14", "#4a1a24", "#6e2a36", "#8a3a48"], "grip", seed=5),
    }
    w = Weapon(m, grip_y=8, kind="sword", seed=11)
    w.cyl(2, 14, 1.6, "grip")                                   # 손잡이 (반지름 1.6 → 4복셀 굵기)
    w.ball(0, 1.5, 0, 2.6, 2.2, 2.6, "gold")                    # 폼멜
    w.fill(lambda X, Y, Z: (np.abs(X) <= 7.5) & (Y >= 14) & (Y <= 16.5) & (np.abs(Z) <= 1.6), "gold")   # 가드
    w.gem(0, 15.5, 1.6, "gem", frame="gold", depth=2.6)
    w.blade(17, 58, lambda t: 3.6 - 0.8 * t, mats=("rim", "core", None), thick=(0.6, 1.6, 1.6), tip=0.22)
    return w


def example_boss_greatsword():
    """보스/프리즘 무기만 아우라를 쓴다."""
    m = {
        "steel": Mat(["#2a1a14", "#5a3a2a", "#8a5a3a", "#c08a5a"], "metal", seed=21),
        "magma": Mat(["#6a1000", "#d84a0a", "#ffa020", "#fff2a0"], "fire", glow=True, seed=22),
        "black": Mat(["#120c0a", "#2a1c18", "#43302a", "#5a4438"], "stone", seed=23),
        "grip": Mat(["#1a0c08", "#3a1a10", "#5a2a18", "#7a3a20"], "grip", seed=25),
    }
    w = Weapon(m, grip_y=9, kind="greatsword", seed=12)
    w.cyl(2, 16, 1.6, "grip")
    w.box(-9.5, 9.5, 16, 19, -2.1, 2.1, "black")
    w.blade(19, 64, 5.5, mats=("steel", "magma", "black"), thick=(0.6, 1.6, 2.1), tip=0.2, ridge_w=0.6)
    w.set_aura(["#8a1000", "#ff4a0a", "#ffa020", "#fff4b0"], "flame", size=1.1, focus=["magma"])
    return w


def example_bow(pull):
    """pull: 0 평소, 1~3 당긴 정도. 활은 세워서, 손잡이가 -X 로 볼록, 화살은 -X 로 날아간다. 시위는 +X 쪽."""
    m = {
        "wood": Mat(["#3a220e", "#6a421c", "#9a6a34", "#c89a5a"], "wood", seed=1),
        "wrap": Mat(["#1e1410", "#3a2a1e", "#5a4430", "#7a6048"], "grip", seed=2),
        "string": Mat(["#c8c8c8", "#e8e8e8", "#f8f8f8", "#ffffff"], "flat", seed=3),
        "tip": Mat(["#5a5a60", "#9aa0a8", "#d0d8e0", "#ffffff"], "metal", seed=4),
        "arrow": Mat(["#4a3a2a", "#7a6040", "#a08060", "#c0a080"], "wood", seed=5),
    }
    w = Weapon(m, grip_y=28, grip_x=-3, kind="bow", seed=7)
    bend = 1 + pull * 0.25
    top = [(-3, 28, 0), (-2, 36, 0), (0, 44, 0), (3 * bend, 50, 0), (6 * bend, 54, 0)]
    w.tube(top, lambda t: 1.6 - 0.8 * t, "wood")
    w.tube([(x, 56 - y, z) for (x, y, z) in top], lambda t: 1.6 - 0.8 * t, "wood")
    w.cyl(24, 32, 1.9, "wrap", cx=-3)
    sx = 6 * bend + pull * 5                                     # 당길수록 시위가 +X 로
    # 1복셀 굵기 선: Z=0.5 (복셀 가운데)에 반지름 0.6
    w.tube([(6 * bend, 54, 0.5), (sx, 28, 0.5), (6 * bend, 2, 0.5)], 0.6, "string")
    if pull > 0:
        w.tube([(sx, 28.5, 0.5), (-9, 28.5, 0.5)], 0.6, "arrow")
        w.fill(lambda X, Y, Z: (X <= -9) & (X >= -12) & (np.abs(Y - 28.5) <= (X + 12) * 0.5 + 0.1) & (np.abs(Z) <= 1), "tip")
    return w


WEAPONS = {
    "example_sword": example_sword,
    "example_boss_greatsword": example_boss_greatsword,
    "example_bow": lambda: [example_bow(i) for i in range(4)],
}

if __name__ == "__main__":
    preview_sheet(WEAPONS, os.path.join(HERE, "preview", "_examples.png"), names={k: k for k in WEAPONS})
