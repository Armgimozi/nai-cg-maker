#!/usr/bin/env python3
"""review2 — 겉모습 시뮬레이터를 '방어구 요구 = gear_spec 표, 스탯 줄 이름 바꿈 없음' 으로 다시 돌려
look_spec 결과(lk_sim_full.json: look_spec 요구 짝 + 이름 바꿈)와 비교한다."""
import json, os, sys, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import lk_core as K
import lk_sim as LS
gs = json.load(open(os.path.join(os.path.dirname(HERE), 'gear_spec.json')))
GREQ = {k: v['requires'] for k, v in gs['armor_changes'].items()}
for s in gs['armor_sets'].values():
    for pid, p in s['pieces_items'].items():
        GREQ[pid] = p['requires']
_orig_new = K.new_requires
gs = json.load(open(os.path.join(os.path.dirname(HERE), 'gear_spec.json')))
MODE = os.environ.get('RV_MODE', 'gear')
if MODE in ('lookfix', 'final'):
    import rv_lookfix  # noqa: F401  (look_spec 표 + 고침 3개)
if MODE == 'final':
    # 무기 요구 = gear_spec 2판 (AND 나눔) — 최종 합친 판
    import ce_core as CC
    _orig_req_w = CC.requires_of
    def _req_w(wid):
        if wid in CC.WEAPONS or wid in CC.NEW_WEAPONS:
            src = gs['existing_changes'].get(wid) or gs['weapons'].get(wid) or {}
            return dict(src.get('requires') or {})
        return _orig_req_w(wid)
    CC.requires_of = _req_w


def new_requires(iid):
    if MODE in ('gear', 'gearren') and iid in GREQ:
        return dict(GREQ[iid])
    return _orig_new(iid)


def renamed_stats(iid):
    it = K.ALL_ITEMS[iid]
    return {k: (list(v) if isinstance(v, list) else v) for k, v in it['stats'].items()}


if MODE in ('gear', 'gearren'):
    K.new_requires = new_requires
if MODE == 'gear':
    K.renamed_stats = renamed_stats


def job(a):
    floor, variant, cls, prof, diff, runs = a
    scn = LS.scenario(LS.gear_table(floor, variant))
    return a, LS.solo(scn, cls, prof, diff, floor, runs, seed=1000 + floor)


if __name__ == '__main__':
    jobs = []
    for fl in (6, 10):
        for v in ('native', 'heavy'):
            for cls in ('guardian', 'berserker', 'hunter', 'arcanist', 'priest', 'shadow'):
                for prof, diff in (('average', 'normal'), ('skilled', 'normal'), ('skilled', 'hard')):
                    jobs.append((fl, v, cls, prof, diff, 40))
    with mp.Pool(4) as pool:
        res = pool.map(job, jobs, chunksize=1)
    old = json.load(open(os.path.join(HERE, 'lk_sim_full.json')))
    out = {}
    print('floor variant class | look_spec(보통실력·숙련·숙련어려움) → gear 요구·이름 바꿈 없음')
    rows = {}
    for a, r in res:
        fl, v, cls, prof, diff, _ = a
        key = f'solo|{fl}|{v}|{cls}|{prof}|{diff}'
        rows.setdefault((fl, v, cls), []).append((old.get(key, {}).get('clear'), r['clear']))
        out[key] = dict(look_spec=old.get(key), gear_req=r)
    for (fl, v, cls), xs in rows.items():
        print(f'F{fl:<2} {v:7s} {cls:9s} | ' + ' · '.join(f'{(o if o is not None else -1):.0%}' for o, _ in xs)
              + '  →  ' + ' · '.join(f'{n:.0%}' for _, n in xs))
    json.dump(out, open(os.path.join(HERE, f'rv_looksim_{MODE}.json'), 'w'), ensure_ascii=False, indent=0)
