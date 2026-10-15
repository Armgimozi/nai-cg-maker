#!/usr/bin/env python3
"""겉모습 탐색: 직업 × Lv × 겉모습 → DPS/EHP (combat_spec 기준 대비).
   python3 lk_explore.py [--v '{"heavy": {"attack_speed": -0.015}}'] [--new] [Lv...]"""
import json
import sys

import lk_core as K
import lk_model as LM

args = sys.argv[1:]
inc_new = False
if "--new" in args:
    inc_new = True
    args.remove("--new")
if "--v" in args:
    i = args.index("--v")
    v = json.loads(args[i + 1])
    del args[i:i + 2]
    for lk, d in v.items():
        for k, x in d.items():
            if x is None:
                K.LOOKS[lk]["piece"].pop(k, None)
            else:
                K.LOOKS[lk]["piece"][k] = x
LVS = [int(a) for a in args] or [10, 25, 45]
print({k: v["piece"] for k, v in K.LOOKS.items()})

for L in LVS:
    print(f"── Lv{L}")
    for cls in LM.CLASSES:
        ref = LM.build(cls, L, "native", looks=False, new_req=False, sets=True)
        cells = []
        for lk in ("heavy", "light", "cloth"):
            b = LM.build(cls, L, lk, include_new=inc_new)
            b0 = LM.build(cls, L, lk, looks=False, include_new=inc_new)
            ms = f"(ms {b['ehp_ms']/ref['ehp']-1:+.0%})" if b["full"] == "cloth" else ""
            cells.append(f"{lk[0].upper()} {b['dps']/ref['dps']-1:+4.0%}/{b['ehp']/ref['ehp']-1:+4.0%}{ms}"
                         f" [{b0['dps']/ref['dps']-1:+.0%}/{b0['ehp']/ref['ehp']-1:+.0%}]")
        print(f"{cls:9} {ref['dps']:6.0f}/{ref['ehp']:6.0f} | " + " | ".join(cells))
