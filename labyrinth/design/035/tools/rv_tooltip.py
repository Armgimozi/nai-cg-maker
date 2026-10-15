#!/usr/bin/env python3
"""review2 — ue_tooltip2 의 줄 세기에 '공격 속도 초당 N회' 한 줄을 더해 무기 237개를 다시 센다 (강화 줄 0·1·2)."""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from ue_tooltip import wrap, it, MAX
D2 = os.path.dirname(HERE)
gs = json.load(open(os.path.join(D2, 'gear_spec.json')))


def count(v, U=2, E=2, extra=1):
    head = 1 + (1 if v.get('requires') else 0)
    n = len(v['stats']); stats = 1 + math.ceil((n - 1) / 2) + extra
    sk = v.get('weapon_skills') or []
    descs = [len(wrap(s.get('description', ''))) for s in sk]
    flavor = len(wrap(v.get('lore', ''))) if v.get('lore') else 0
    boss = 'boss' in (v.get('sources') or [])
    for tier in range(5):
        if boss: keep = tier <= 3; blanks = tier <= 1; short = tier >= 3
        else: keep = tier <= 1; blanks = tier <= 2; short = tier >= 4
        o = head + (1 if blanks else 0) + stats + E
        o += (1 if blanks else 0) + len(sk) + sum((1 if short and d > 1 else d) for d in descs) + (1 if short else U)
        if tier == 0 and flavor: o += 1 + flavor
        if keep: o += 1
        if o <= MAX: return o, tier, keep
    return o, tier, keep


ws = {k: v for k, v in it.items() if v.get('type') == 'weapon'}
for k, ch in gs['existing_changes'].items():
    v = dict(ws[k]); v['requires'] = ch['requires']; v['sources'] = ch['sources']; ws[k] = v
for k, v in gs['weapons'].items():
    ws[k] = v
res = {}
for extra in (0, 1):
    bad, worst, folded = [], (0, ''), 0
    for k, v in ws.items():
        for E in (2, 1, 0):
            o, t, keep = count(v, 2, E, extra)
            if o > MAX or ('boss' in v['sources'] and not keep):
                bad.append((k, E, o, t))
            if E == 2 and t >= 4: folded += 1
            worst = max(worst, (o, k))
    res[extra] = dict(bad=bad, worst=worst, folded_tier4=folded)
    print(f'공격 속도 줄 {"있음" if extra else "없음"}: 넘침·보스 획득처 잃음 {len(bad)} {sorted(set(b[0] for b in bad))} · 가장 긴 것 {worst} · 4단계 접힘 {folded}')
json.dump({str(k): v for k, v in res.items()}, open(os.path.join(HERE, 'rv_tooltip.json'), 'w'), ensure_ascii=False, indent=1)
