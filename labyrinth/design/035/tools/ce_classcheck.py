#!/usr/bin/env python3
"""직업별 전후 비교 묶음 → ce_classcheck.json
  det  : 기대값 모델 (ce_model) L1/10/25/45 — DPS·EHP·HP·치유력, 초기화 안 한 경우도
  sim  : 시뮬레이터 방 전투 100판 (같은 시드) F1/F3/F6/F10 — 방 DPS·받은 피해(최대 HP 비율)
  ttk  : 층 일반 몹 한 마리 처치 시간(초) — 진입 레벨·흔한 장비, 보통·솔로
"""
import json
import multiprocessing as mp
import os

import ce_core as C
import ce_diag2 as D
import ce_model as M
import ce_sim as X

HERE = os.path.dirname(os.path.abspath(__file__))
CL = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]


def det():
    C.USE_GEAR_REQUIRES = False
    C.REQ_SPLIT = X.REQ_SPLIT_FINAL
    P = X.P_FINAL
    out = {}
    for cls in CL:
        for L in (1, 10, 25, 45):
            o = M.old_player(cls, L)
            n = M.new_player(cls, L, P, "sensible", o["weapon"])
            # 초기화 안 함: 0.3.4 분배 그대로 새 공식
            a_old = M.plan_v2(cls, L, [o["weapon"]] + M.gear_for(cls, L)[1], "old")[0]
            nr = M.new_player(cls, L, P, "sensible", o["weapon"], alloc=a_old)
            out[f"{cls}|{L}"] = dict(weapon=o["weapon"], old_dps=round(o["dps"], 1), new_dps=round(n["dps"], 1),
                                    dps=round(n["dps"] / o["dps"] - 1, 3), old_ehp=round(o["ehp"]), new_ehp=round(n["ehp"]),
                                    ehp=round(n["ehp"] / o["ehp"] - 1, 3), old_hp=round(o["hp"]), new_hp=round(n["hp"]),
                                    old_heal_power=round(o["heal_power"]), new_heal_power=round(n["heal_power"]),
                                    old_stats=o["stats"], new_stats=n["stats"], new_alloc={k: v for k, v in n["alloc"].items() if v},
                                    noreset_dps=round(nr["dps"] / o["dps"] - 1, 3), noreset_ehp=round(nr["ehp"] / o["ehp"] - 1, 3),
                                    old_basic=round(o["basic"], 1), old_skill=round(o["skill"], 1),
                                    new_basic=round(n["basic"], 1), new_skill=round(n["skill"], 1),
                                    speed_old=round(o["speed"], 3), speed_new=round(n["speed"], 3),
                                    crit_old=round(o["crit"], 3), crit_new=round(n["crit"], 3),
                                    evasion_new=round(n["d"]["evasion"], 3), interval=n["interval"], per_hit=n["per_hit"])
    return out


def simjob(a):
    cls, fl = a
    o = D.run(cls, fl, "old", n=100, seed=31)
    n = D.run(cls, fl, "new", n=100, seed=31)
    return a, dict(old_dps=round(o[0], 1), new_dps=round(n[0], 1), dps=round(n[0] / o[0] - 1, 3),
                   old_taken=round(o[1], 3), new_taken=round(n[1], 3), taken=round(n[1] / max(1e-9, o[1]) - 1, 3))


def ttk():
    C.USE_GEAR_REQUIRES = False
    C.REQ_SPLIT = X.REQ_SPLIT_FINAL
    P = X.P_FINAL
    out = {}
    for fl in (1, 3, 5, 7, 10):
        L = X.entry_level(fl)
        ms = C.FLOORS[fl]["mobs"]
        hp = sum(C.MOBS[m]["hp"] for m in ms) / len(ms)
        de = sum(C.MOBS[m].get("defense", 0) for m in ms) / len(ms)
        boss = next(v for v in C.BOSSES.values() if v.get("floor") == fl)
        solo = C.CONFIG["party"]["solo_hp"]
        for cls in CL:
            o = M.old_player(cls, max(1, L))
            n = M.new_player(cls, max(1, L), P, "sensible", o["weapon"])
            f_m = 100 / (100 + de)
            f_b = 100 / (100 + boss["defense"])
            out[f"F{fl}|{cls}"] = dict(level=L, mob_hp=round(hp * solo), boss_hp=round(boss["hp"] * solo),
                                      mob_old=round(hp * solo / (o["dps"] * f_m), 1), mob_new=round(hp * solo / (n["dps"] * f_m), 1),
                                      boss_old=round(boss["hp"] * solo / (o["dps"] * f_b)), boss_new=round(boss["hp"] * solo / (n["dps"] * f_b)))
    return out


if __name__ == "__main__":
    res = dict(det=det(), ttk=ttk())
    with mp.Pool(4) as pool:
        sim = pool.map(simjob, [(c, fl) for c in CL for fl in (1, 3, 6, 10)])
    res["sim"] = {f"{c}|F{fl}": r for (c, fl), r in sim}
    with open(os.path.join(HERE, "ce_classcheck.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for k, v in res["sim"].items():
        print(k, v)
