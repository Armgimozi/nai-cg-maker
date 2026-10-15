# -*- coding: utf-8 -*-
"""간격이 다른 무기에서 고유 효과 값이 공정한가 — 효과 피해(또는 가치) ÷ 무기 기본 초당 피해.
같은 강도(s=1)·같은 설계 초당 피해(DPS=1)인 무기를 간격만 바꿔 120초 몬테카를로.
기준: 간격 0.67초 근접 = 1.00. 1에 가까울수록 공정."""
import random, json, os
from ud_core import K_style, spm

def per_hit(style, iv):          # 설계 초당 피해 1 → 한 방
    return iv
def sp(style, iv):               # 스킬 위력 (같은 단계 → K 로 나눈 값, 기준 근접 0.67 에서 1.015)
    return (1 / K_style(style, iv)) * spm(style)

def run(style, iv, eff, basis, T=600.0, cc=0.30, seed=1, icd=None, chance=None, mobs_hp=None):
    rnd = random.Random(seed)
    W = per_hit(style, iv); S = sp(style, iv)
    base = {'W': W, 'SP': S}[basis] if basis in ('W', 'SP') else W
    t = 0.0; extra = 0.0; last = -99; stacks = []  # (expire)
    hits = 0
    # 처치 모델: 몹 HP = 6 × (0.67초 근접 한 방) — 무기와 상관없이 같은 몹
    hp0 = mobs_hp or 6 * 0.67
    hp = hp0; kills = 0; pending = 0.0
    while t < T:
        hits += 1
        dmg = W
        if eff == 'rend':
            stacks = [e for e in stacks if e > t]
            if rnd.random() < cc and t - last >= (icd or 0.4):
                last = t
                if len(stacks) >= 5: stacks.sort(); stacks.pop(0)
                stacks.append(t + 4)
            # 초당 피해 적분 (다음 타격까지)
            extra += sum(min(e, t + iv) - t for e in stacks if e > t) * 0.06 * base
        elif eff == 'chain':
            c = chance if chance is not None else 0.20
            if rnd.random() < c and t - last >= (icd if icd is not None else 1.0):
                last = t; extra += 0.45 * base
        elif eff == 'imbue':
            c = chance if chance is not None else 0.25
            stacks = [e for e in stacks if e > t]
            if rnd.random() < c and t - last >= 1.0:
                last = t
                stacks = [t + 3]   # 불태움: 새로 걸면 3초로
            extra += sum(min(e, t + iv) - t for e in stacks if e > t) * 0.10 * base
        elif eff == 'sanctify':
            if t - last >= (icd if icd is not None else 0.5):
                last = t; extra += 0.12 * base
        elif eff in ('first_strike', 'bloodrush', 'death_burst'):
            # 몹 사냥: 몹을 잡을 때마다 다음 몹 첫 타(또는 처치 직후 1회)
            if eff == 'first_strike' and hp == hp0:
                dmg = W * (1 + 0.8 * (g if basis == 'g' else 1))
            if eff == 'bloodrush' and pending:
                dmg = W * (1 + pending); pending = 0
            hp -= dmg
            if hp <= 0:
                kills += 1; hp = hp0
                if eff == 'bloodrush': pending = 0.6 * (g if basis == 'g' else 1)
                if eff == 'death_burst': extra += 0.8 * base
            extra += dmg - W
        t += iv
    return extra / T   # 기본 초당 피해 = 1

out = {}
cases = [('melee', 0.45), ('melee', 0.55), ('melee', 0.67), ('melee', 0.75), ('melee', 1.0), ('melee', 1.18), ('ranged', 1.0), ('ranged', 1.25), ('caster', 0.77), ('caster', 0.95)]
REF = 1 / (0.67 * K_style('melee', 0.67))
rows = []
for style, iv in cases:
    g = (1 / (iv * K_style(style, iv)) * spm(style)) / REF
    r = dict(style=style, iv=iv, g=round(g, 3))
    r['rend_W'] = run(style, iv, 'rend', 'W')
    r['rend_SP'] = run(style, iv, 'rend', 'SP')
    r['chain_W_icd1'] = run(style, iv, 'chain', 'W')
    r['chain_W_icd0.3'] = run(style, iv, 'chain', 'W', icd=0.3)
    r['imbue_SP_flat'] = run(style, iv, 'imbue', 'SP')
    r['imbue_SP_scaled'] = run(style, iv, 'imbue', 'SP', chance=0.25 * min(1.5, iv / 0.67))
    r['sanct_W_icd0.5'] = run(style, iv, 'sanctify', 'W')
    r['sanct_W_icd0.25'] = run(style, iv, 'sanctify', 'W', icd=0.25)
    r['first_W'] = run(style, iv, 'first_strike', 'W')
    r['first_g'] = run(style, iv, 'first_strike', 'g')
    r['rush_W'] = run(style, iv, 'bloodrush', 'W')
    r['rush_g'] = run(style, iv, 'bloodrush', 'g')
    r['burst_W'] = run(style, iv, 'death_burst', 'W')
    r['burst_SP'] = run(style, iv, 'death_burst', 'SP')
    rows.append(r)
ref = [r for r in rows if r['style'] == 'melee' and r['iv'] == 0.67][0]
keys = [k for k in rows[0] if k not in ('style', 'iv', 'g')]
print('style  iv    g   ' + ' '.join(f'{k:>14}' for k in keys))
for r in rows:
    print(f"{r['style']:6} {r['iv']:.2f} {r['g']:.2f} " + ' '.join(f"{r[k]/ref[k]:14.2f}" for k in keys))
json.dump(dict(rows=rows, ref=ref), open(os.path.join(os.path.dirname(__file__), 'ud_fair.json'), 'w'), indent=1)
