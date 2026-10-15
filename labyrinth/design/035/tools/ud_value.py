# -*- coding: utf-8 -*-
"""TASK D — 상황별 가치 모델: '대장간·보스가 언제나 정답'인가를 띠마다 본다.

가치 V(상황) = Q × (1 + 효과 이득(상황))
  Q = 무기 힘 P′ ÷ TP′(L)  (레벨을 뺀 무기 힘: 희귀도·부가 스탯·무기 스킬 수가 들어 있음, ud_assign)
  효과 이득 = 그 상황에서 고유 효과가 늘려 주는 '내 피해(또는 버팀을 피해로 바꾼 값)'의 비율

상황 4개
  P 무리 사냥   : 적 4마리가 3칸 안에 붙어 옴, 한 마리는 내 초당 피해 3초분에 죽음
  E 정예전     : 정예 1마리, 25초
  B 보스 혼자   : 보스 1마리, 90초 (기절 면역 → 받는 피해 증가, 마무리 60%)
  T 보스 파티   : 3인 파티 보스전 (탱커가 시선을 끔 → 등 뒤가 쉬움, 아군에게 주는 이득은 반값으로 더함)

가정 (모두 이 파일 맨 위 상수, combat_spec 의 Lv25 직업 모델에서 대충 맞춤):
  기본 공격 비중 α: 근접·원거리 0.7, 시전 0.5 (combat_spec class_det: 0.46~0.94)
  치명 확률 25%, 치명 피해 ×1.5,   내 초당 피해 ÷ 최대 HP = 0.15/s
  버팀 효과는 gear 가치표(ue_gen.WGT)와 같은 무게로 피해 값으로 바꾼다: 흡혈 0.4 · 피해 감소 0.8
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ud_core as U

ALPHA = {'melee': 0.7, 'ranged': 0.7, 'caster': 0.5}
CC, CD = 0.25, 1.5
CF = 1 + CC * (CD - 1)
R_DH = 0.15
T_KILL = 3.0
N_EXTRA = 3
W_LS, W_DR = 0.4, 0.8
SITS = ['P', 'E', 'B', 'T']
SIT_KO = {'P': '무리 사냥', 'E': '정예전', 'B': '보스 혼자', 'T': '보스 파티'}
BOSS_DEF = {1: 8, 2: 10, 3: 12, 4: 16, 5: 22, 6: 28, 7: 34, 8: 40, 9: 46, 10: 56}


def has_status_skill(w, keys):
    s = json.dumps(w.get('skills') or [], ensure_ascii=False)
    return any(k in s for k in keys)


def gain(w, sit):
    e = w['effect']; p = w['params']; iv = w['interval']; st = w['style']
    a = ALPHA[st]
    K = U.K_style(st, iv) / U.spm(st)
    b = w['band']
    if e == 'rend':
        stacks = min(p['max_stacks'], p['duration'] * CC * (1 / iv + 0.5))
        g = stacks * p['pct'] * iv * a / CF
        return g * (0.5 if sit == 'P' else 1.0)
    if e == 'hemorrhage':
        ub = 0.5 if has_status_skill(w, ['bleed']) else 0.15
        g = ub * ((1 + (CC + p['cc']) * (CD + p['cd'] - 1)) / CF - 1)
        return g * (0.7 if sit == 'P' else 1.0)
    if e == 'leech':
        return W_LS * p['pct'] * a * {'P': 1.2, 'E': 1.2, 'B': 1.0, 'T': 0.6}[sit]
    if e == 'feast':
        if sit == 'P':
            return W_LS * (p['heal'] / T_KILL / R_DH + p['ls'] * min(1, p['duration'] / T_KILL))
        return W_LS * p['heal'] * 0.03 / R_DH
    if e == 'thorns':
        return p['pct'] * {'P': 0.35, 'E': 0.2, 'B': 0.1, 'T': 0.1}[sit]
    if e == 'shield_bash':
        g = a * p['pct'] / (p['n'] * CF)
        period = p['n'] * iv
        if sit in ('P', 'E'):
            g += W_DR * p['stun'] / max(6.0, period)
        else:
            g += p['vuln'] * min(1.0, 3.0 / period)
        return g
    if e == 'steadfast':
        return W_DR * p['dr'] * {'P': 0.5, 'E': 0.6, 'B': 0.6, 'T': 0.8}[sit]
    if e == 'cleave':
        return a * p['pct'] * min(p['targets'], N_EXTRA) / CF if sit == 'P' else 0.0
    if e == 'chain_spark':
        return a * p['chance'] * p['pct'] * min(p['targets'], N_EXTRA) / CF if sit == 'P' else 0.0
    if e == 'death_burst':
        return p['pct'] * 1.5 * a / (K * CF * T_KILL) if sit == 'P' else 0.0
    if e == 'execute':
        return p['thr'] * p['pct'] * {'P': 0.8, 'E': 1.0, 'B': 0.6, 'T': 0.6}[sit]
    if e == 'bloodrush':
        return p['pct'] * iv * a / (CF * T_KILL) if sit == 'P' else 0.0
    if e == 'momentum':
        add = min(p['max_stacks'] * p['as'], 0.4)
        return add * (a + (1 - a) * 0.5) * {'P': 0.7, 'E': 0.9, 'B': 0.9, 'T': 0.9}[sit]
    if e == 'flurry':
        return a * p['pct'] / p['n']
    if e == 'counterstep':
        rate = {'P': 2.0, 'E': 0.8, 'B': 0.4, 'T': 0.2}[sit]
        procs = min(0.5, 0.12 * rate)
        return procs * iv * a * ((1 + p['pct']) * CD - CF) / CF
    if e == 'siphon':
        ws = min(0.3, 0.1 * w['n_skills'])
        g = ws * p['cdr'] / T_KILL + (1 - a) * 0.3 * (p['mp'] / 0.12)
        return g if sit == 'P' else g * 0.05
    if e == 'overcharge':
        n = 3 if sit == 'P' else 1
        return 0.25 * p['pct'] * a * n / (K * CF)
    if e == 'sanctify':
        g = W_LS * p['pct'] * a / CF
        return g if sit == 'T' else g * 0.5
    if e == 'ward_aura':
        g = W_LS * (p['pct'] / p['period']) / R_DH
        return g * 2 if sit == 'T' else g
    if e == 'imbue':
        if p['element'] == 'frost':
            per = 5 / (p['chance'] / iv)
            if sit in ('P', 'E'):
                return W_DR * 1.0 / per
            return 0.05 * min(1, 3 / per)
        g = 0.85 * p['pct'] * a / (K * CF)
        return g * (0.5 if sit == 'P' else 1.0)
    if e == 'exploit':
        u = 0.8 if has_status_skill(w, ['poison', 'venom', 'bleed', 'ignite', 'frost', 'slow', 'weak', 'blind', 'mark', 'freeze']) else 0.6
        g = p['pct'] * (u + 0.6 * 0.2)
        return g * (0.7 if sit == 'P' else 1.0)
    if e == 'first_strike':
        rate = {'P': 1 / T_KILL, 'E': 2 / 25, 'B': 1 / 30, 'T': 1 / 30}[sit]
        return rate * iv * a * (p['pct'] + p['cc'] * (CD - 1)) / CF
    if e == 'backstab':
        return p['pct'] * {'P': 0.2, 'E': 0.3, 'B': 0.3, 'T': 0.7}[sit]
    if e == 'longshot':
        g = p['pct'] * {'P': 0.3, 'E': 0.4, 'B': 0.4, 'T': 0.7}[sit]
        if sit == 'P':
            g += a * 0.8 * p['pierce'] * 0.3 / CF
        return g
    if e == 'berserk':
        m = {'P': 0.25, 'E': 0.35, 'B': 0.35, 'T': 0.15}[sit]
        low = {'P': 0.1, 'E': 0.15, 'B': 0.15, 'T': 0.05}[sit]
        return m * 10 * p['pct'] + W_LS * p['ls'] * low
    if e == 'armor_break':
        up = {'P': 0.3, 'E': 0.9, 'B': 0.95, 'T': 0.95}[sit]
        D = BOSS_DEF[b] * {'P': 0.3, 'E': 0.6, 'B': 1.0, 'T': 1.0}[sit]
        sh = min(0.4, p['max_stacks'] * p['pct']) * up
        g = (100 + D) / (100 + D * (1 - sh)) - 1
        return g * (2 if sit == 'T' else 1)
    raise KeyError(e)


def evaluate(W):
    """W: ud_state W (params 채워진 것). 반환: 무기별 상황 가치, 띠별 승자."""
    for w in W.values():
        w['gain'] = {s: gain(w, s) for s in SITS}
        w['V'] = {s: w['Q'] * (1 + w['gain'][s]) for s in SITS}
    bands = {}
    for b in range(1, 11):
        ws = [w for w in W.values() if w['band'] == b and w['rar'] != 'mythic']
        res = {}
        for s in SITS:
            ranked = sorted(ws, key=lambda w: -w['V'][s])
            top = ranked[0]
            def best_of(pred):
                c = [w for w in ranked if pred(w)]
                return c[0] if c else None
            bB = best_of(lambda w: 'B' in w['sk'])
            bF = best_of(lambda w: 'F' in w['sk'] and 'B' not in w['sk'])
            bO = best_of(lambda w: 'B' not in w['sk'] and 'F' not in w['sk'])
            per_style = {}
            for stl in ('melee', 'ranged', 'caster'):
                r2 = [w for w in ranked if w['style'] == stl]
                if r2:
                    o2 = [w for w in r2 if 'B' not in w['sk'] and 'F' not in w['sk']]
                    per_style[stl] = dict(top=r2[0]['id'], top_sk=r2[0]['sk'], V=r2[0]['V'][s],
                                          other=o2[0]['id'] if o2 else None, other_V=o2[0]['V'][s] if o2 else None)
            # 상위 10% 안(최고의 0.9 이상)에 드는 무기 수와 획득처
            near = [w for w in ranked if w['V'][s] >= 0.9 * top['V'][s]]
            res[s] = dict(top=top['id'], top_sk=top['sk'], top_V=top['V'][s],
                          bestB=bB['id'] if bB else None, bestB_V=bB['V'][s] if bB else None,
                          bestF=bF['id'] if bF else None, bestF_V=bF['V'][s] if bF else None,
                          bestO=bO['id'] if bO else None, bestO_V=bO['V'][s] if bO else None,
                          near=[w['id'] for w in near], near_sk=sorted(set(k for w in near for k in w['sk'])),
                          per_style=per_style)
        bands[b] = res
    return bands


if __name__ == '__main__':
    st = json.load(open(os.path.join(HERE, 'ud_state.json')))
    W = st['W']
    bands = evaluate(W)
    for b, res in bands.items():
        print('==', U.blabel(b))
        for s in SITS:
            r = res[s]
            o = r['bestO_V'] / r['top_V'] if r['bestO_V'] else 0
            print(f"  {SIT_KO[s]:6} top {r['top']:28} {''.join(r['top_sk']):3} {r['top_V']:.2f} | B {r['bestB']} {r['bestB_V'] and round(r['bestB_V'],2)} | F {r['bestF']} {r['bestF_V'] and round(r['bestF_V'],2)} | 그밖 {r['bestO']} {r['bestO_V'] and round(r['bestO_V'],2)} ({o:.2f}) near{len(r['near'])} {r['near_sk']}")
