#!/usr/bin/env python3
"""manifest.json 의 무기 GLB 에서 Combat.MESH 의 tip/grip 값을 구한다.

    python3 tools/meshy/grips.py   (tools/meshy/models 의 GLB 를 읽는다)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import glb_stats, weapon_axis

HERE = os.path.dirname(os.path.abspath(__file__))
manifest = json.load(open(os.path.join(HERE, "manifest.json")))

# 기본 규칙이 손잡이를 벗어나는 모델은 손으로 정한 grip (단면 그림과 썸네일로 확인한 값)
GRIP = {
    "saber_5": 0.36,  # 손잡이가 짧다 (코등이 0.25~0.28, 손잡이 0.28~0.44, 고리 0.44~). 기본 규칙(0.334)은 코등이에 붙는다. 손잡이 가운데를 쥔다
    # 부채는 사북(갓대가 모이는 곳) 바로 아래를 쥔다. 아래로 늘어진 끈·술까지 상자에 들어가서 기본 규칙은 술을 쥔다
    "fan_1": -0.235,
    "fan_2": -0.21,  # 자루가 비스듬히 옆으로 나 있다. 사북을 쥔다
    "fan_4": -0.15,
    "fan_5": -0.10,
}


def width_centroid(V, lo, hi, n=40):
    """세로 단면 너비(X)로 가중한 Y 평균. 부채는 넓은 갓 쪽으로 치우친다."""
    step = (hi[1] - lo[1]) / n
    total = moment = 0
    for i in range(n):
        y0 = lo[1] + step * i
        xs = [v[0] for v in V if y0 <= v[1] < y0 + step]
        w = (max(xs) - min(xs)) if xs else 0
        total += w
        moment += w * (y0 + step / 2)
    return moment / total if total else (lo[1] + hi[1]) / 2

for key, entry in manifest.items():
    if entry["kind"] != "weapon":
        continue
    V, tris, lo, hi = glb_stats(os.path.join(HERE, "models", key + ".glb"))
    axis = weapon_axis(V, lo, hi)
    tip, guard = axis["tipDir"], axis["guardY"]
    kind = key.split("_")[0]  # "spear_3" -> spear (종류_등급)
    if kind == "spear":
        # 창은 날(창끝)이 가장 넓다: 넓은 쪽이 날 끝이다
        tip = 1 if guard > (hi[1] + lo[1]) / 2 else -1
    elif kind == "fan":
        # 부채는 갓이 넓은 쪽이 위(tip=1). 가장 넓은 단면은 갓 가운데쯤이라 guard 로는 못 가린다
        tip = 1 if width_centroid(V, lo, hi) > (hi[1] + lo[1]) / 2 else -1
    length = hi[1] - lo[1]
    center = (hi[1] + lo[1]) / 2
    butt = lo[1] if tip == 1 else hi[1]
    point = hi[1] if tip == 1 else lo[1]
    if kind == "spear":
        grip = butt + 0.38 * (point - butt)
    elif kind == "fan":
        grip = butt + 0.1 * (point - butt)
    else:
        grip = guard + 0.3 * (butt - guard)
    size = [round(hi[i] - lo[i], 3) for i in range(3)]
    longest = max(size)
    g = GRIP.get(key, round((grip - center) / longest, 3))
    print(f"{key}: asset={entry['assetId']} tip={tip} grip={g} size={size} guard={guard}")
