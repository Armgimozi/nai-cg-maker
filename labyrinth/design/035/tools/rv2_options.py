#!/usr/bin/env python3
"""review2 (2차) — 직업 × (Lv15–25: 띠 16–20·21–25, Lv35–45: 띠 36–40·41–45) 빌드 선택지 표 (rv2_choice 고침 뒤).
칸마다 쓸 만한 무기(어느 상황이든 90% 이상): 효과 · 겉모습(세금 ≤ 15% 로 입는 것) · 획득처 · 이기는 상황."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rv2_choice as R
import g2_core as G
import g2_check as C2
EFF = {e: v['name'] for e, v in json.load(open(os.path.join(os.path.dirname(HERE), 'unique_spec.json')))['effects'].items()}
SRC = {'B': '보스', 'F': '대장간', 'M': '몬스터·상자', 'T': '시련방', 'S': '특별 시련', 'V': '금고·미믹', 'E': '정예', 'P': '상인'}
LK = {'heavy': '판금', 'light': '가죽', 'cloth': '천'}
SIT = {'P': '무리', 'E': '정예', 'B': '보스 혼자', 'T': '보스 파티'}
st0 = R.base_state()
st, fixes, stuck = R.solve(st0)
fixed_ids = {f['weapon'] for f in fixes}
out = {}
for c in G.CLS:
    for b in (4, 5, 8, 9):
        x = R.cell(st, c, b)
        rows = []
        for i in sorted(x['viable'], key=lambda i: -max(x['rel'][i].values())):
            s = st[i]; P = 5 * b
            looks = [LK[l] for l in ('heavy', 'light', 'cloth')
                     if (k := C2.best_kit(c, P, s['req'], R.SETS, R.SHIELDS, max(1, P - 15), l)) and k['tax'] <= 0.15]
            wins = [SIT[t] for t in 'PEBT' if x['rel'][i][t] >= 0.95]
            rows.append(dict(id=i, name=R.W[i]['name'], rar=s['rar'], eff=EFF.get(R.ua[i]['effect'], R.ua[i]['effect']),
                             src='/'.join(SRC[t] for t in s['src']), looks=looks, wins=wins,
                             top=round(max(x['rel'][i].values()), 2), fixed=i in fixed_ids, style=s['style']))
        out[f'{c}|{b}'] = dict(ok=x['ok'], dom=x['dom'], rows=rows)
        print(f"{G.CLS_KO[c]} {G.blabel(b)} {'✔' if x['ok'] else '✘'}{' 지배 '+R.W[x['dom']]['name'] if x['dom'] else ''}")
        for r in rows:
            print(f"   {r['name']}{'*' if r['fixed'] else ''} ({r['rar']}) {r['eff']} · {r['src']} · {'/'.join(r['looks']) or '-'} · 95%↑: {','.join(r['wins']) or '-'}")
json.dump(out, open(os.path.join(HERE, 'rv2_options.json'), 'w'), ensure_ascii=False, indent=1)
