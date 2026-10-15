#!/usr/bin/env python3
"""review2 (2차) — 겉모습 손잡이 시험: 그림자·사냥꾼 가죽이 판금에 눌리는가, 고치면 다른 직업이 어떻게 되나.
변형: base(look_spec) · ev25(가죽 부위 회피 +2.5%p) · cd5(구르기 5초) · hvas(판금 부위 공속 −2%) · mix(ev25+hvas)
판 = 층마다 60번, 같은 시드. 겉모습 요구 = look_spec 표 + review2 고침 3개."""
import os, sys, json, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import rv_lookfix  # noqa
import lk_core as K
import lk_sim as LS

VAR = {'base': {}, 'ev25': {('light', 'evasion'): 0.025}, 'cd5': {('light', 'cd'): 5.0},
       'hvas': {('heavy', 'attack_speed'): -0.02}, 'mix': {('light', 'evasion'): 0.025, ('heavy', 'attack_speed'): -0.02}}


def setv(v):
    for (lk, key), val in VAR[v].items():
        if key == 'cd':
            K.LOOKS[lk]['full']['cooldown'] = val
        else:
            K.LOOKS[lk]['piece'][key] = val


def job(a):
    v, fl, look, cls, prof, diff = a
    setv(v)
    scn = LS.scenario(LS.gear_table(fl, look))
    return a, LS.solo(scn, cls, prof, diff, fl, 60, seed=1000 + fl)['clear']


if __name__ == '__main__':
    jobs = [(v, fl, look, cls, prof, diff) for v in VAR for fl in (6, 10) for look in ('native', 'heavy')
            for cls in ('shadow', 'hunter', 'berserker', 'guardian') for prof, diff in (('average', 'normal'), ('skilled', 'normal'), ('skilled', 'hard'))]
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=2)
    out = {'|'.join(map(str, a)): r for a, r in res}
    json.dump(out, open(os.path.join(HERE, 'rv2_looktune.json'), 'w'), indent=0)
    for cls in ('shadow', 'hunter', 'berserker', 'guardian'):
        for fl in (6, 10):
            for look in ('native', 'heavy'):
                row = ' | '.join(f"{v}: " + '·'.join(f"{out[f'{v}|{fl}|{look}|{cls}|{p}|{d}']:.0%}" for p, d in (('average', 'normal'), ('skilled', 'normal'), ('skilled', 'hard'))) for v in VAR)
                print(f'{cls:9s} F{fl:<2} {look:6s} {row}')
