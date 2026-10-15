#!/usr/bin/env python3
"""review2 — 요구 능력치 합치기 검사.
무기 요구 = gear_spec(JSON) 값, 방어구 요구 = (a) gear_spec 3.3 값 (b) look_spec 3.2 값.
두 경우 모두 g2_check.run 으로 직업 × 띠 '알맞은 무기 수'를 다시 센다 (칭호 없음, 초기화 뒤)."""
import io, json, os, sys, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import g2_core as G
import g2_req as Q
import g2_check as K
D2 = os.path.dirname(HERE)
gs = json.load(open(os.path.join(D2, 'gear_spec.json')))
lk = json.load(open(os.path.join(D2, 'look_spec.json')))
W = G.weapons_all()
WR = {}
for wid in W:
    if wid in gs['weapons']:
        WR[wid] = dict(requires=gs['weapons'][wid]['requires'])
    else:
        WR[wid] = dict(requires=gs['existing_changes'][wid]['requires'])
A = G.armor_all()
AR_gear = {}
for aid in A:
    if aid in gs['armor_changes']:
        AR_gear[aid] = dict(requires=gs['armor_changes'][aid]['requires'])
    else:
        for s in gs['armor_sets'].values():
            if aid in s['pieces_items']:
                AR_gear[aid] = dict(requires=s['pieces_items'][aid]['requires'])
lkreq = {a['id']: (a.get('requires') or {}) for a in lk['armor_items']}
AR_look = {aid: dict(requires=lkreq[aid]) for aid in A}
res = {}
for tag, AR in (('gear', AR_gear), ('look', AR_look)):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = K.run(W, WR, A, AR, verbose=False)
    tab = {c: [out['by_class_band'][f'{c}|{b}']['good_kind'] for b in G.BANDS] for c in G.CLS}
    nat = {c: [out['by_class_band'][f'{c}|{b}']['good_natural_look'] for b in G.BANDS] for c in G.CLS}
    res[tag] = dict(good=tab, natural=nat, short=out['short'], orphans=out['orphans'])
    print(f'== 방어구 요구 = {tag} ==  (알맞은 무기 수 / 제 겉모습으로만)')
    for c in G.CLS:
        print(f'{c:10s}', ' '.join(f'{a:2d}/{b:<2d}' for a, b in zip(tab[c], nat[c])))
    print('short', out['short'], 'orphans', out['orphans'])
json.dump(res, open(os.path.join(HERE, 'rv_reqmerge.json'), 'w'), ensure_ascii=False, indent=1)
