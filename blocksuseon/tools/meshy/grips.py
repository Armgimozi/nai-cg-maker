#!/usr/bin/env python3
"""manifest.json 의 무기 GLB 에서 Combat.MESH 의 tip/grip 값을 구한다.

    python3 tools/meshy/grips.py   (tools/meshy/models 의 GLB 를 읽는다)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import glb_stats, weapon_axis

HERE = os.path.dirname(os.path.abspath(__file__))
manifest = json.load(open(os.path.join(HERE, "manifest.json")))
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
    print(f"{key}: asset={entry['assetId']} tip={tip} grip={round((grip - center) / longest, 3)} size={size} guard={guard}")
