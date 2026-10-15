#!/usr/bin/env python3
"""review2 — '무기 스킬 수 맞춤' 규칙(보스·대장간 아닌 무기: 희귀 ≥1 · 영웅 ≥2, 31–35 띠 새 희귀 → 영웅)과
'대장간 효과 × 0.8 → × 0.6' 을 넣었을 때 직업 × 띠 판정 (rv_fixsolve 의 cell 규칙)."""
import os, sys, copy, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault('RV_MINV', '3'); os.environ.setdefault('RV_STRONG', '0.95')
import importlib.util
spec = importlib.util.spec_from_file_location('fx', os.path.join(HERE, 'rv_fixsolve.py'))
src = open(os.path.join(HERE, 'rv_fixsolve.py')).read().split("state = dict(base)\nfixes = []")[0]
ns = {'__file__': os.path.join(HERE, 'rv_fixsolve.py'), '__name__': 'fx'}
exec(compile(src, 'rv_fixsolve_head', 'exec'), ns)
G, cell, buff, base, W = ns['G'], ns['cell'], ns['buff'], ns['base'], ns['W']
ua = ns['ua']


def apply(rule_forge=0.6, parity=True, promote_3135=True):
    st = dict(base)
    n_sk = 0; n_prom = 0
    for k in list(st):
        s = st[k]
        if set(s['src']) & {'B', 'F'} or s['rar'] in ('mythic', 'legendary', 'common', 'uncommon'):
            continue
        if promote_3135 and s['band'] == '31–35' and s['rar'] == 'rare' and ua[k]['weapon']['new']:
            st = buff(st, k); n_sk += 1; n_prom += 1
            continue
        want = 1 if st[k]['rar'] == 'rare' else 2
        while parity and st[k]['sk'] < want:
            st = buff(st, k); n_sk += 1
    if rule_forge != 0.8:
        for k in list(st):
            s = st[k]
            if s['src'] == ['F'] and s['B'] > 0:
                s = copy.deepcopy(s); r = rule_forge / 0.8
                s['gain'] = {kk: v * r for kk, v in s['gain'].items()}; st[k] = s
    return st, n_sk, n_prom


for label, kw in (('지금', dict(rule_forge=0.8, parity=False, promote_3135=False)),
                  ('대장간 ×0.6 만', dict(rule_forge=0.6, parity=False, promote_3135=False)),
                  ('스킬 수 맞춤 + 31–35 승격', dict(rule_forge=0.8, parity=True, promote_3135=True)),
                  ('스킬 수 맞춤 + 31–35 승격 + 대장간 ×0.6', dict(rule_forge=0.6, parity=True, promote_3135=True))):
    st, n, p = apply(**kw)
    res = {f'{c}|{b}': cell(st, c, b) for b in G.BANDS for c in G.CLS}
    ok = sum(v['ok'] for v in res.values()); dom = sum(1 for v in res.values() if v['dom'])
    v2 = sum(1 for v in res.values() if v['viable'] >= 2 and not v['dom'] and v['strong'] >= 1)
    print(f'{label}: 스킬 추가 {n} (승격 {p}) · 칸 통과(3·95%) {ok}/60 · 지배 있는 칸 {dom} · (2·95%·지배 없음) {v2}/60')
    bad = [k for k, v in res.items() if v['dom']]
    print('   지배 칸:', ', '.join(f"{G.CLS_KO[k.split('|')[0]]}{G.blabel(int(k.split('|')[1]))}:{W[res[k]['dom']]['name']}" for k in bad))
