#!/usr/bin/env python3
"""review2 — 직업 × 띠 빌드 검사(rv_builds 규칙)를 띠 10개 모두에 돌리고, 못 넘는 칸을 메우는 가장 작은 데이터 고침을 고른다.
고침 후보 (보스·대장간 아닌 무기만): 무기 스킬 +1 (Q × (1+sec+0.1(n+1))/(1+sec+0.1n)) · 희귀→영웅이면 Q × 1.21/1.13 도.
고친 무기의 강도 s 는 D 식(B = clamp(0.08+0.6·gap, 0.04, 0.28))으로 다시 셈하고 상황 이득은 B 비율로 줄인다.
목표 (칸마다): 쓸 만함(어느 상황 ≥ 90%) 3개 이상 · 엄격 지배 없음 · 보스·대장간 아닌 '강함'(≥ 95%) 1개 이상."""
import io, json, os, sys, contextlib, copy
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rv_lookfix  # noqa
import lk_core as K
import g2_core as G
import g2_check as C2
D2 = os.path.dirname(HERE)
gs = json.load(open(os.path.join(D2, 'gear_spec.json')))
ua = json.load(open(os.path.join(D2, 'unique_assign_all.json')))
SITS = 'PEBT'
W = G.weapons_all()
WR = {w: dict(requires=(gs['weapons'][w] if w in gs['weapons'] else gs['existing_changes'][w])['requires']) for w in W}
A = G.armor_all()
AR = {aid: dict(requires=K.new_requires(aid)) for aid in A}
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    chk = C2.run(W, WR, A, AR, verbose=False)
base = {k: dict(Q=v['power']['Q'], gain=dict(v['situational_gain']), B=v['budget'], sec=v['power']['secondary_value'],
                sk=v['power']['weapon_skills'], rar=v['weapon']['rarity'], src=v['weapon']['source_kinds'],
                band=v['weapon']['band'], style=v['weapon']['style']) for k, v in ua.items()}


def band_best_Q(state, band):
    return max(s['Q'] for k, s in state.items() if s['band'] == band and s['rar'] != 'mythic')


def cell(state, c, b):
    ids = chk['by_class_band'][f'{c}|{b}']['good_ids']
    if c == 'hunter':
        ids = [i for i in ids if W[i]['style'] == 'ranged']
    if not ids:
        return dict(ok=False, viable=0, dom=None, strong=0, ids=[])
    vals = {i: {s: state[i]['Q'] * (1 + state[i]['gain'][s]) for s in SITS} for i in ids}
    best = {s: max(v[s] for v in vals.values()) for s in SITS}
    rel = {i: {s: vals[i][s] / best[s] for s in SITS} for i in ids}
    viable = [i for i in ids if max(rel[i].values()) >= 0.90]
    dom = [i for i in viable if all(all(vals[i][s] >= vals[o][s] for s in SITS) for o in viable if o != i)]
    strong = [i for i in ids if max(rel[i].values()) >= 0.95 and not set(state[i]['src']) & {'B', 'F'}]
    MINV = int(os.environ.get('RV_MINV', 3)); STRONG = float(os.environ.get('RV_STRONG', 0.95))
    strong = [i for i in ids if max(rel[i].values()) >= STRONG and not set(state[i]['src']) & {'B', 'F'}]
    ok = len(viable) >= MINV and not dom and len(strong) >= 1
    return dict(ok=ok, viable=len(viable), dom=dom[0] if dom else None, strong=len(strong), ids=ids, rel=rel)


def buff(state, wid):
    s = copy.deepcopy(state[wid])
    f = (1 + s['sec'] + 0.1 * (s['sk'] + 1)) / (1 + s['sec'] + 0.1 * s['sk'])
    s['sk'] += 1
    if s['rar'] == 'rare':
        f *= 1.21 / 1.13
        s['rar'] = 'epic'
    s['Q'] *= f
    st = dict(state); st[wid] = s
    bb = band_best_Q(st, s['band'])
    gap = max(0.0, bb / s['Q'] - 1)
    Bn = max(0.04, min(0.28, 0.08 + 0.6 * gap))
    if 'F' in s['src']:
        Bn *= 0.8
    if s['B'] > 0:
        r = Bn / s['B']
        s['gain'] = {k: v * r for k, v in s['gain'].items()}
        s['B'] = Bn
    return st


def best_score_guard(c, b, cands, state):
    # 후보가 없거나, 후보를 모두 고쳐도(스킬 2개까지) 이 칸이 안 넘으면 True
    if not cands:
        return True
    st = state
    for i in cands:
        while st[i]['sk'] < 2:
            st = buff(st, i)
    return not cell(st, c, b)['ok']


state = dict(base)
fixes = []
report_before = {}
for b in G.BANDS:
    for c in G.CLS:
        report_before[f'{c}|{b}'] = cell(state, c, b)
SKIP = set()
for it in range(200):
    bad = [(c, b) for b in G.BANDS for c in G.CLS if not cell(state, c, b)['ok'] and (c, b) not in SKIP]
    if not bad:
        break
    c, b = bad[0]
    cur = cell(state, c, b)
    cands = [i for i in cur['ids'] if not set(state[i]['src']) & {'B', 'F'} and state[i]['sk'] < 2]
    if best_score_guard(c, b, cands, state):
        SKIP.add((c, b)); fixes.append(dict(cell=f'{c}|{b}', weapon=None, note='고쳐도 못 넘음 — 무기 추가·요구 짝 바꿈 필요')); continue
    best_choice, best_score = None, None
    for i in cands:
        st2 = buff(state, i)
        oks = sum(cell(st2, c2, b2)['ok'] for b2 in G.BANDS for c2 in G.CLS)
        cc = cell(st2, c, b)
        score = (cc['ok'], oks, cc['viable'], cc['strong'], -int(cc['dom'] is not None))
        if best_score is None or score > best_score:
            best_choice, best_score = i, score
    if best_choice is None:
        fixes.append(dict(cell=f'{c}|{b}', weapon=None, note='보스·대장간 아닌 알맞은 무기가 없음 — 무기 추가·요구 짝 바꿈 필요'))
        SKIP.add((c, b))
        continue
    state = buff(state, best_choice)
    fixes.append(dict(cell=f'{c}|{b}', weapon=best_choice, name=W[best_choice]['name'], src=state[best_choice]['src'],
                      rar_after=state[best_choice]['rar'], skills_after=state[best_choice]['sk']))
state = {k: v for k, v in state.items() if v is not None and not k.startswith('__')}
after = {f'{c}|{b}': cell(state, c, b) for b in G.BANDS for c in G.CLS}
print('칸 판정 (전 → 후): 쓸 만함 · 지배 · 보스·대장간 아닌 강함')
for b in G.BANDS:
    row = []
    for c in G.CLS:
        x, y = report_before[f'{c}|{b}'], after[f'{c}|{b}']
        row.append(f"{G.CLS_KO[c]} {x['viable']}{'D' if x['dom'] else ''}{x['strong']}{'✔' if x['ok'] else '✘'}→{y['viable']}{'D' if y['dom'] else ''}{y['strong']}{'✔' if y['ok'] else '✘'}")
    print(G.blabel(b), ' | '.join(row))
print('\n고침', len([f for f in fixes if f['weapon']]))
for f in fixes:
    print(f)
json.dump(dict(fixes=fixes, before={k: {kk: vv for kk, vv in v.items() if kk != 'rel'} for k, v in report_before.items()},
               after={k: {kk: vv for kk, vv in v.items() if kk != 'rel'} for k, v in after.items()}),
          open(os.path.join(HERE, f"rv_fixsolve_{os.environ.get('RV_MINV', 3)}_{os.environ.get('RV_STRONG', 0.95)}.json"), 'w'), ensure_ascii=False, indent=1)
