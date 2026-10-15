#!/usr/bin/env python3
"""review2 (2차) — 그림자 10층 회귀 고치기 후보 (ce_sim 새 모델, 겉모습 없음): 0.3.4 · 새 · 새+스킬 배율 0.70 ·
새+치명 피해 +0.55 · 새+체력 몫(분배 DEX2:STR1.2:VIT1.8). 판 100번 × 시드 2벌, 1·5·10층, 보통 실력·숙련 (보통)."""
import os, sys, json, copy, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import ce_sim as X


def scn(v):
    if v == 'old':
        return X.scenario('old')
    P = copy.deepcopy(X.P_FINAL)
    if v == 'ss70':
        P.setdefault('skill_scale', {})['shadow'] = 0.70
    if v == 'cd55':
        P['shadow_crit_dmg'] = 0.55
    if v == 'both':
        P.setdefault('skill_scale', {})['shadow'] = 0.70
        P['shadow_crit_dmg'] = 0.50
    return X.scenario('new', P=P)


def job(a):
    v, fl, prof, seed = a
    return a, X.solo_floor(scn(v), 'shadow', prof, 'normal', fl, 100, seed)['clear']


if __name__ == '__main__':
    print('P_FINAL target shadow =', (X.P_FINAL.get('target') or {}).get('shadow'))
    jobs = [(v, fl, p, s) for v in ('old', 'new', 'both') for fl in (1, 5, 10) for p in ('average', 'skilled') for s in (11, 22)]
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    agg = {}
    for (v, fl, p, s), r in res:
        agg.setdefault((v, fl, p), []).append(r)
    for fl in (1, 5, 10):
        for p in ('average', 'skilled'):
            print(f'F{fl:<2} {p:8s} ' + ' | '.join(f"{v} {sum(agg[(v, fl, p)])/2:.0%}" for v in ('old', 'new', 'both')))
    json.dump({'|'.join(map(str, k)): v for k, v in agg.items()}, open(os.path.join(HERE, 'rv2_shadowtune.json'), 'w'), indent=0)
