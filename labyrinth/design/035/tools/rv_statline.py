#!/usr/bin/env python3
"""review2 — 기존 활·단검의 DEX 주 스탯 줄을 (a) 그대로 (b) STR 로 이름만 바꿔 그림자·광전사·수호기사 10층·5층을 잰다 (요구 없음)."""
import os, sys, json, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
os.environ['RV_REQ'] = 'none'
import rv_interval as RI
import ce_simbase as S
import ce_core as C
MODE = os.environ.get('RV_LINE', 'keep')
if MODE == 'str':
    for wid, v in list(S.ITEMS.items()):
        if v.get('type') == 'weapon' and v.get('weapon_type') in ('dagger', 'bow') and 'DEX' in v['stats']:
            st = dict(v['stats']); st['STR'] = st.pop('DEX'); v['stats'] = st
            if wid in C.ITEMS: C.ITEMS[wid]['stats'] = st


def job(a):
    return RI.job(a)


if __name__ == '__main__':
    jobs = [(c, fl, w) for fl in (5, 10) for c in ('shadow', 'berserker', 'hunter') for w in RI.SETS[fl] if RI.M.weapon_kind(w) == 'physical']
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    for (c, fl, w), r in res:
        print(MODE, c, fl, f'{w:22s} {r["interval"]:.2f}s DPS {r["room_dps"]:7.1f} 받은 {r["taken"]:.2f} 보통 {r["clear_avg"]:.0%} 숙련 {r["clear_skilled"]:.0%}')
