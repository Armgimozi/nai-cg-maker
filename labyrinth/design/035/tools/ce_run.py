#!/usr/bin/env python3
"""
전후 비교 실행기 — 직업 6개 솔로 + 3인 파티 2조 × 보통/어려움/악몽 × 1·3·5·7·10층 × 실력(보통·숙련, 보통 난이도는 초보도).

  python3 ce_run.py <tag> <runs_solo> <scenario>[;<scenario>...]
  scenario 이름: old | new | new:<json overrides>
결과: ce_results_<tag>.json (+ 표 출력)
"""
import json
import multiprocessing as mp
import os
import sys

import ce_sim as X

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSES = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]
FLOORS = (1, 3, 5, 7, 10)
DIFFS = ("normal", "hard", "nightmare")


def make(name):
    if name == "old":
        return X.scenario("old")
    if name == "new":
        return X.scenario("new")
    if name.startswith("new:") or name.startswith("old:"):
        model, js = name.split(":", 1)
        kw = json.loads(js)
        diffs = kw.pop("diffs", None)
        s = X.scenario(model, **kw)
        if diffs:
            for k, v in diffs.items():
                s["diffs"][k].update(v)
        return s
    raise SystemExit("unknown scenario " + name)


def work(task):
    name, kind, who, prof, diff, fl, runs, seed = task
    scn = make(name)
    if kind == "solo":
        r = X.solo_floor(scn, who, prof, diff, fl, runs, seed)
    else:
        r = X.party_floor(scn, who, prof, diff, fl, runs, seed)
    return task, r


def tasks_for(name, runs, seed0=1000):
    out, seed = [], seed0
    for d in DIFFS:
        for fl in FLOORS:
            profs = ("novice", "average", "skilled") if d == "normal" else ("average", "skilled")
            for p in profs:
                for c in CLASSES:
                    seed += 1
                    out.append((name, "solo", c, p, d, fl, runs, seed))
                for comp in ("A", "B"):
                    seed += 1
                    out.append((name, "party", comp, p, d, fl, max(10, runs // 2), seed))
    return out


def summarize(res, name):
    lines = []
    for d in DIFFS:
        lines.append(f"[{name}] {d}")
        for p in ("novice", "average", "skilled"):
            row = []
            for fl in FLOORS:
                cells = [r for (t, r) in res if t[0] == name and t[1] == "solo" and t[3] == p and t[4] == d and t[5] == fl]
                if not cells:
                    continue
                cl = [r["clear"] for r in cells]
                bt = [r["boss_t"] for r in cells if r["boss_t"]]
                rt = [r["room_t"] for r in cells if r["room_t"]]
                pa = [r for (t, r) in res if t[0] == name and t[1] == "party" and t[3] == p and t[4] == d and t[5] == fl]
                pc = "/".join(f"{x['clear']:.0%}" for x in pa)
                row.append(f"F{fl} {sum(cl)/len(cl):4.0%} ({min(cl):.0%}-{max(cl):.0%}) room {sum(rt)/max(1,len(rt)):4.0f}s boss {sum(bt)/max(1,len(bt)):4.0f}s | 3인 {pc}")
            if row:
                lines.append(f"  {p:7} " + " ‖ ".join(row))
    return "\n".join(lines)


if __name__ == "__main__":
    tag, runs = sys.argv[1], int(sys.argv[2])
    names = sys.argv[3].split(";")
    allt = []
    for i, nm in enumerate(names):
        allt += tasks_for(nm, runs, 1000 + i * 0)   # 같은 시드 → 시나리오끼리 같은 난수 흐름 (짝 비교)
    with mp.Pool(4) as pool:
        res = pool.map(work, allt, chunksize=2)
    out = [dict(task=list(t), result=r) for t, r in res]
    with open(os.path.join(HERE, f"ce_results_{tag}.json"), "w", encoding="utf-8") as f:
        json.dump(dict(names=names, runs=runs, rows=out), f, ensure_ascii=False)
    for nm in names:
        print(summarize(res, nm))
