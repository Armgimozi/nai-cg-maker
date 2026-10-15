#!/usr/bin/env python3
"""review2 — look_spec 방어구 요구 표에 고침 3개를 넣어 (abyss_walker DEX/STR · starless_choir INT/VIT · cinder_cantor INT/VIT)
g2_check 직업 검사와 겉모습 시뮬레이터를 다시 돌린다."""
import io, json, os, sys, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lk_core as K
FIX = {'abyss_walker': ({'DEX': 0.6, 'STR': 0.4}, {'LUK': 'STR'}),
       'starless_choir': ({'INT': 0.6, 'VIT': 0.4}, {'WIS': 'VIT'}),
       'cinder_cantor': ({'INT': 0.6, 'VIT': 0.4}, {'WIS': 'VIT'})}
for sid, (sh, ren) in FIX.items():
    old = K.SET_REQ[sid]
    K.SET_REQ[sid] = (sh, old[1], old[2] + ' (review2 고침)')
    K.STATS_RENAME[sid] = ren


def look_req_table(A):
    return {aid: dict(requires=K.new_requires(aid)) for aid in A}


if __name__ == '__main__':
    import g2_core as G, g2_check as C2
    gs = json.load(open(os.path.join(os.path.dirname(HERE), 'gear_spec.json')))
    W = G.weapons_all()
    WR = {w: dict(requires=(gs['weapons'][w] if w in gs['weapons'] else gs['existing_changes'][w])['requires']) for w in W}
    A = G.armor_all()
    AR = look_req_table(A)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = C2.run(W, WR, A, AR, verbose=False)
    print('look_spec 표 + 고침 3개: 알맞은 무기 수 / 제 겉모습으로만')
    res = {}
    for c in G.CLS:
        a = [out['by_class_band'][f'{c}|{b}']['good_kind'] for b in G.BANDS]
        n = [out['by_class_band'][f'{c}|{b}']['good_natural_look'] for b in G.BANDS]
        res[c] = dict(good=a, natural=n)
        print(f'{c:10s}', ' '.join(f'{x:2d}/{y:<2d}' for x, y in zip(a, n)))
    print('short', out['short'], 'orphans', out['orphans'])
    for sid in FIX:
        pid = [k for k, v in K.ALL_ITEMS.items() if v.get('set_bonus') == sid][0]
        print(sid, K.new_requires(pid))
    json.dump(dict(fix={k: v[0] for k, v in FIX.items()}, check=res, short=out['short']),
              open(os.path.join(HERE, 'rv_lookfix.json'), 'w'), ensure_ascii=False, indent=1)
