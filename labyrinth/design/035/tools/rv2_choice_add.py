#!/usr/bin/env python3
"""review2 (2차) — rv2_choice 고침 뒤에도 못 넘는 칸에 '새 무기 1개'를 넣으면 몇 개로 다 넘는가.
새 무기 = 그 띠 보스·대장간 아닌 영웅 무기의 가운데 Q × (스킬 1개 기준), 상황 이득 = 그 띠 보스·대장간 아닌 무기 중
그 칸에서 가장 쓸모 있는 것의 이득(다른 효과 방향을 가정), 요구 = 그 직업 알맞은 분배의 앞 두 능력치 60/40,
방식 = 사냥꾼 원거리 · 비전술사/사제 시전 · 그 밖 근접, 획득처 = 시련방·특별 시련·금고·정예 중 하나."""
import copy, json, os, sys, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rv2_choice as R
import g2_core as G
import g2_req as Q
st0 = R.base_state()
st, fixes, stuck = R.solve(st0)
adds = []
skip = set()
NAT = {c: [s for s, _ in sorted(Q.RATIO[c].items(), key=lambda kv: -kv[1])] for c in G.CLS}
for it in range(40):
    bad = [(c, b) for b in G.BANDS for c in G.CLS if not R.cell(st, c, b)['ok'] and (c, b) not in skip]
    if not bad:
        break
    c, b = bad[0]
    pool = [s for s in st.values() if s['band'] == b and s['rar'] == 'epic' and not set(s['src']) & R.BF]
    if not pool:
        pool = [s for s in st.values() if s['band'] == b and not set(s['src']) & R.BF and s['rar'] != 'mythic']
    qmed = statistics.median(s['Q'] for s in pool)
    best = None
    for donor in pool:
        nid = f'__new_{c}_{b}_{it}'
        L = max(s['L'] for s in pool)
        style = 'ranged' if c == 'hunter' else 'caster' if c in ('arcanist', 'priest') else 'melee'
        kind = 'magic' if c in ('arcanist', 'priest') else 'physical'
        order = NAT[c][:2]
        if kind == 'physical' and 'STR' not in order and 'DEX' not in order: order = [order[0], 'STR']
        s = dict(Q=qmed * max(1.0, (1 + donor['sec'] + 0.1 * max(1, donor['sk'])) / (1 + donor['sec'] + 0.1 * donor['sk'])) if donor['sk'] < 1 else qmed,
                 gain=dict(donor['gain']), B=donor['B'], sec=donor['sec'], sk=max(1, donor['sk']), rar='epic', src=['T'], band=b,
                 style=style, kind=kind, L=L, req=Q.split(L, order), new=True, direction=donor['direction'])
        st2 = dict(st); st2[nid] = s
        sc = (R.band_ok(st2, b), R.cell(st2, c, b)['ok'])
        if best is None or sc > best[0]:
            best = (sc, nid, st2, donor)
    if best is None or best[0][0] <= R.band_ok(st, b):
        adds.append(dict(cell=f'{c}|{b}', added=None)); skip.add((c, b)); continue
    _, nid, st, donor = best
    adds.append(dict(cell=f'{c}|{b}', band=G.blabel(b), style=st[nid]['style'], req=st[nid]['req'], like=donor['direction']))
ok = sum(R.cell(st, c, b)['ok'] for b in G.BANDS for c in G.CLS)
print('고침', len(fixes), '+ 새 무기', len([a for a in adds if a.get('style')]), '→ 칸 통과', ok, '/60')
for a in adds: print(a)
json.dump(dict(fixes=len(fixes), adds=adds, pass_cells=ok), open(os.path.join(HERE, 'rv2_choice_add.json'), 'w'), ensure_ascii=False, indent=1)
