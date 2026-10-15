#!/usr/bin/env python3
"""review2 — 직업 × 레벨대 빌드 선택지 (무기 효과 × 겉모습 × 획득처).
  알맞음 = 칭호 없이 초기화 뒤 포인트 안 · 세금 ≤ 15% (방어구 요구 = look_spec 표 + review2 고침 3개) · 피해 종류가 직업과 맞음
           (사냥꾼은 원거리만 — 매의 눈·거리 벌리기가 활에만 붙는다)
  가치 = Q × (1 + 상황 이득)  (unique_assign_all: Q = 레벨 뺀 무기 힘, 상황 P 무리 · E 정예 · B 보스 혼자 · T 보스 파티)
  쓸 만함 = 네 상황 중 하나라도 그 직업·띠 최고의 90% 이상. 강함 = 95% 이상.
  엄격 지배 = 다른 쓸 만한 무기 모두를 네 상황 모두에서 이김."""
import io, json, os, sys, contextlib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rv_lookfix  # noqa: F401 — look_spec 방어구 표 + 고침 3개
import lk_core as K
import g2_core as G
import g2_check as C2
D2 = os.path.dirname(HERE)
gs = json.load(open(os.path.join(D2, 'gear_spec.json')))
ua = json.load(open(os.path.join(D2, 'unique_assign_all.json')))
EFF_KO = {e: v['name'] for e, v in json.load(open(os.path.join(D2, 'unique_spec.json')))['effects'].items()}
SITS = ['P', 'E', 'B', 'T']
SIT_KO = {'P': '무리', 'E': '정예', 'B': '보스 혼자', 'T': '보스 파티'}
LOOK_KO = {'heavy': '판금', 'light': '가죽', 'cloth': '천', 'plain': '평상복', 'any': '아무'}
W = G.weapons_all()
WR = {w: dict(requires=(gs['weapons'][w] if w in gs['weapons'] else gs['existing_changes'][w])['requires']) for w in W}
A = G.armor_all()
AR = {aid: dict(requires=K.new_requires(aid)) for aid in A}
sets, shields = C2.armor_sets(A, AR)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    chk = C2.run(W, WR, A, AR, verbose=False)
BANDS = {'15–25': [4, 5], '35–45': [8, 9]}
out = {}
for c in G.CLS:
    for lab, bands in BANDS.items():
        for b in bands:
            ids = chk['by_class_band'][f'{c}|{b}']['good_ids']
            if c == 'hunter':
                ids = [i for i in ids if W[i]['style'] == 'ranged']
            rows = []
            P = 5 * b
            for wid in ids:
                u = ua[wid]
                vals = {s: u['power']['Q'] * (1 + u['situational_gain'][s]) for s in SITS}
                looks = []
                for lk in ('heavy', 'light', 'cloth'):
                    kit = C2.best_kit(c, P, WR[wid]['requires'], sets, shields, max(1, P - 15), lk)
                    if kit and kit['tax'] <= 0.15:
                        looks.append(lk)
                rows.append(dict(id=wid, name=W[wid]['name'], rar=W[wid]['rar'], L=W[wid]['L'], style=W[wid]['style'],
                                 interval=W[wid]['interval'], effect=u['effect'], eff_name=u['name'],
                                 src=u['weapon']['source_kinds'], vals=vals, looks=looks,
                                 req=WR[wid]['requires']))
            if not rows:
                out[f'{c}|{b}'] = dict(rows=[], note='없음'); continue
            best = {s: max(r['vals'][s] for r in rows) for s in SITS}
            for r in rows:
                r['rel'] = {s: round(r['vals'][s] / best[s], 3) for s in SITS}
                r['top'] = max(r['rel'].values())
            viable = [r for r in rows if r['top'] >= 0.90]
            strong_nonBF = [r for r in rows if r['top'] >= 0.95 and not set(r['src']) & {'B', 'F'}]
            dom = []
            for r in viable:
                if all(all(r['vals'][s] >= o['vals'][s] for s in SITS) for o in viable if o is not r):
                    dom.append(r['id'])
            out[f'{c}|{b}'] = dict(rows=sorted(rows, key=lambda r: -r['top']), n_viable=len(viable),
                                   viable_effects=sorted(set(r['effect'] for r in viable)),
                                   strong_nonBF=[r['id'] for r in strong_nonBF], dominant=dom,
                                   best_by_sit={s: max(rows, key=lambda r: r['vals'][s])['id'] for s in SITS})
json.dump(out, open(os.path.join(HERE, 'rv_builds.json'), 'w'), ensure_ascii=False, indent=1)
SRC_KO = G.SK_KO
for key, v in out.items():
    c, b = key.split('|')
    print(f"\n## {G.CLS_KO[c]} 띠 {G.blabel(int(b))}: 쓸 만함 {v.get('n_viable')} · 효과 {len(v.get('viable_effects', []))}종 · 보스·대장간 아닌 강한 것 {len(v.get('strong_nonBF', []))} · 엄격 지배 {v.get('dominant')}")
    for r in v['rows'][:9]:
        rel = ' '.join(f"{SIT_KO[s]} {r['rel'][s]:.0%}" for s in SITS)
        print(f"  {r['name']}({r['rar'][:4]} L{r['L']} {r['style']} {r['interval']}s) {EFF_KO.get(r['effect'], r['effect'])} · "
              f"{'/'.join(SRC_KO[x] for x in r['src'])} · 겉모습 {'·'.join(LOOK_KO[x] for x in r['looks']) or '-'} | {rel}")
