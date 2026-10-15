#!/usr/bin/env python3
"""review2 — 직업 × 띠: 알맞은 무기 수 (사냥꾼은 원거리만) 와 그 가운데 보스·대장간 아닌 영웅 이상 수."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ns = {'__file__': os.path.join(HERE, 'rv_fixsolve.py'), '__name__': 'fx'}
src = open(os.path.join(HERE, 'rv_fixsolve.py')).read().split("state = dict(base)\nfixes = []")[0]
exec(compile(src, 'h', 'exec'), ns)
G, chk, W, base = ns['G'], ns['chk'], ns['W'], ns['base']
out = {}
print('직업    ' + ' '.join(f'{G.blabel(b):>9s}' for b in G.BANDS) + '   (알맞은 수 / 보스·대장간 아닌 영웅↑)')
for c in G.CLS:
    row = []
    for b in G.BANDS:
        ids = chk['by_class_band'][f'{c}|{b}']['good_ids']
        if c == 'hunter':
            ids = [i for i in ids if W[i]['style'] == 'ranged']
        nb = [i for i in ids if not set(base[i]['src']) & {'B', 'F'} and base[i]['rar'] in ('epic', 'legendary')]
        row.append(f'{len(ids):>4d}/{len(nb):<4d}')
        out[f'{c}|{b}'] = dict(n=len(ids), nonBF_epic=len(nb))
    print(f'{G.CLS_KO[c]:6s} ' + ' '.join(row))
json.dump(out, open(os.path.join(HERE, 'rv_suitcount.json'), 'w'), ensure_ascii=False, indent=1)
