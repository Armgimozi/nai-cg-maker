#!/usr/bin/env python3
"""review2 — 전투 명세 시뮬레이터(ce_sim) 다시 돌리기. 설계자와 다른 시드(5000~)로.
  직업 6 솔로 × 보통(초보·보통 실력·숙련) · 악몽(보통 실력·숙련) × 1·5·10층 + 3인 파티 A/B, 0.3.4(old) vs 새(new)
  + 새 모델 '어려움 HP 1.45' 재조정판(new_hard145)
결과: rv_sim.json, 표 출력."""
import json, os, sys, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import ce_sim as X
CLASSES = ["guardian", "berserker", "hunter", "arcanist", "priest", "shadow"]
FLOORS = (1, 5, 10)
RUNS = int(os.environ.get('RV_RUNS', 40))


def make(name):
    if name == 'old':
        return X.scenario('old')
    s = X.scenario('new')
    if name == 'new_hard145':
        s['diffs']['hard'] = dict(s['diffs']['hard'], hp=1.45)
    return s


def work(t):
    name, kind, who, prof, diff, fl, runs, seed = t
    scn = make(name)
    if kind == 'solo':
        r = X.solo_floor(scn, who, prof, diff, fl, runs, seed)
    else:
        r = X.party_floor(scn, who, prof, diff, fl, runs, seed)
    return t, r


def tasks():
    out = []
    for name in ('old', 'new'):
        seed = 5000
        for d in ('normal', 'nightmare', 'hard'):
            for fl in FLOORS:
                profs = ('novice', 'average', 'skilled') if d == 'normal' else ('average', 'skilled')
                for p in profs:
                    for c in CLASSES:
                        seed += 1
                        out.append((name, 'solo', c, p, d, fl, RUNS, seed))
                    for comp in ('A', 'B'):
                        seed += 1
                        out.append((name, 'party', comp, p, d, fl, max(10, RUNS // 2), seed))
    seed = 5000
    for d in ('hard',):
        for fl in FLOORS:
            for p in ('average', 'skilled'):
                for c in CLASSES:
                    seed += 1
                    out.append(('new_hard145', 'solo', c, p, d, fl, RUNS, seed))
    return out


if __name__ == '__main__':
    with mp.Pool(4) as pool:
        res = pool.map(work, tasks(), chunksize=2)
    rows = [dict(task=list(t), result=r) for t, r in res]
    json.dump(dict(runs=RUNS, rows=rows), open(os.path.join(HERE, 'rv_sim.json'), 'w'), ensure_ascii=False)
    idx = {tuple(t): r for t, r in res}
    for d in ('normal', 'hard', 'nightmare'):
        print(f'== {d} ==')
        profs = ('novice', 'average', 'skilled') if d == 'normal' else ('average', 'skilled')
        for p in profs:
            for fl in FLOORS:
                line = f'{p:8s} F{fl:<2} '
                for name in (('old', 'new', 'new_hard145') if d == 'hard' else ('old', 'new')):
                    cells = [idx.get((name, 'solo', c, p, d, fl, RUNS, s)) for (n2, k, c, p2, d2, f2, r2, s) in tasks()
                             if n2 == name and k == 'solo' and p2 == p and d2 == d and f2 == fl]
                    cells = [c for c in cells if c]
                    if not cells:
                        continue
                    cl = [c['clear'] for c in cells]
                    bt = [c['boss_t'] for c in cells if c['boss_t']]
                    per = ' '.join(f'{x:.0%}' for x in cl)
                    pa = [idx.get((name, 'party', comp, p, d, fl, max(10, RUNS // 2), s)) for (n2, k, comp, p2, d2, f2, r2, s) in tasks()
                          if n2 == name and k == 'party' and p2 == p and d2 == d and f2 == fl]
                    pa = '/'.join(f"{x['clear']:.0%}" for x in pa if x)
                    line += f"| {name}: 평균 {sum(cl)/len(cl):.0%} [{per}] 보스 {sum(bt)/max(1,len(bt)):.0f}s 파티A/B {pa} "
                print(line)
