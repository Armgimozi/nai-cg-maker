#!/usr/bin/env python3
"""비전술사 10층: 기준 → 제 옷(천) 차이 나누기 + 마나 보호막 세기 (각 100판 = 시드 2 × 50) → lk_decomp.json"""
import json, multiprocessing as mp, os
import lk_core as K, lk_sim as LS
HERE = os.path.dirname(os.path.abspath(__file__))
def job(a):
    var, absorb, seed, prof, diff = a
    K.LOOKS["cloth"]["full"]["absorb"] = absorb
    g = LS.gear_table(10, "native")
    if var == "rules_old":
        g = {c: dict(v, looks=False, new_req=False) for c, v in g.items()}
    elif var == "req_only":
        g = {c: dict(v, looks=False, new_req=True) for c, v in g.items()}
    scn = LS.scenario(g)
    return a, LS.solo(scn, "arcanist", prof, diff, 10, 50, seed)["clear"]
steps = [("rules_old", 0.2), ("req_only", 0.2), ("looks", 0.0), ("looks", 0.10), ("looks", 0.15), ("looks", 0.20)]
jobs = [(v, ab, sd, p, d) for v, ab in steps for sd in (11, 22) for p, d in (("average", "normal"), ("skilled", "hard"))]
if __name__ == "__main__":
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs)
    agg = {}
    for (v, ab, sd, p, d), r in res:
        agg.setdefault(f"{v}|{ab}|{p}|{d}", []).append(r)
    out = {k: round(sum(v) / len(v), 3) for k, v in agg.items()}
    json.dump(out, open(os.path.join(HERE, "lk_decomp.json"), "w"), indent=1)
    for k, v in out.items():
        print(k, v)
