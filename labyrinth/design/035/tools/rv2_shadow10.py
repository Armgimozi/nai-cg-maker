#!/usr/bin/env python3
"""review2 (2차) — 그림자·사냥꾼·비전술사 10층 솔로(보통) 0.3.4 vs 새 모델, 판 100번 × 시드 3벌."""
import os, sys, json, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import ce_sim as X
def job(a):
    model, cls, prof, seed = a
    return a, X.solo_floor(X.scenario(model), cls, prof, 'normal', 10, 100, seed)
if __name__ == '__main__':
    jobs = [(m, c, p, s) for m in ('old', 'new') for c in ('shadow', 'hunter', 'arcanist') for p in ('average', 'skilled') for s in (101, 202, 303)]
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    agg = {}
    for (m, c, p, s), r in res:
        agg.setdefault((c, p, m), []).append(r['clear'])
    out = {}
    for (c, p, m), v in sorted(agg.items()):
        out[f'{c}|{p}|{m}'] = v
        print(c, p, m, ' '.join(f'{x:.0%}' for x in v), f'평균 {sum(v)/len(v):.0%}')
    json.dump(out, open(os.path.join(HERE, 'rv2_shadow10.json'), 'w'), indent=1)
