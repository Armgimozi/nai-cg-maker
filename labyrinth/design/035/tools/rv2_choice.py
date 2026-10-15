#!/usr/bin/env python3
"""review2 (2차) — 직업 × 띠 '고를 수 있는가' 검사 + 가장 적은 데이터 고침 찾기.

알맞음  = g2_check 규칙 (칭호 없음, 초기화 뒤, 세금 ≤ 15%, 피해 종류가 직업과 맞음 — gear_spec attack.kind)
          사냥꾼은 원거리만 (매의 눈 +30% 가 끝까지 당긴 화살에만 붙어 근접 사냥꾼은 방 DPS 58~65%, rv_interval)
가치    = Q × (1 + 상황 이득)  (unique_assign_all, 상황 P 무리 · E 정예 · B 보스 혼자 · T 보스 파티)
칸 통과 = 쓸 만함(어느 상황이든 그 칸 최고의 90% 이상) 3개 이상 · 엄격 지배 없음 · 보스·대장간 아닌 '강함'(95% 이상) 1개 이상
고침 (보스·대장간 아닌 무기만):
  skill  무기 스킬 +1 (최대 2), 희귀면 영웅으로        — 무기 스킬 하나 새로 만드는 일
  pair   요구 짝을 같은 방향 틀(g2_req.TPL)의 다른 순서로 — 데이터만
  bow    새 근접 무기 하나를 원거리(활 모양)로             — 모양·간격·한 방 다시 (사냥꾼 칸만)
결과: rv2_choice.json"""
import copy, io, json, os, sys, contextlib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import rv2_kindfix as KF
import g2_core as G
import g2_req as Q
import g2_check as C2
D2 = os.path.dirname(HERE)
ua = json.load(open(os.path.join(D2, 'unique_assign_all.json')))
SITS = 'PEBT'
W, WR, A, AR = KF.load(True)
SETS, SHIELDS = C2.armor_sets(A, AR)
COST = {'skill': 1.0, 'pair': 0.4, 'bow': 1.5}
BF = {'B', 'F'}


def base_state():
    st = {}
    for k, v in ua.items():
        w = W[k]
        st[k] = dict(Q=v['power']['Q'], gain=dict(v['situational_gain']), B=v['budget'], sec=v['power']['secondary_value'],
                     sk=v['power']['weapon_skills'], rar=w['rar'], src=v['weapon']['source_kinds'], band=w['band'],
                     style=w['style'], kind=w['kind'], L=w['L'], req=dict(WR[k]['requires']), new=w['new'],
                     direction=w['direction'])
    return st


_good = {}


def good(st, wid, c):
    s = st[wid]
    key = (wid, c, tuple(sorted(s['req'].items())))
    if key not in _good:
        P = 5 * s['band']
        kit = C2.best_kit(c, P, s['req'], SETS, SHIELDS, max(1, P - 15))
        _good[key] = bool(kit and kit['tax'] <= C2.TAX_OK)
    return _good[key]


def cell(st, c, b):
    dk = 'magic' if c in ('arcanist', 'priest') else 'physical'
    ids = [k for k, s in st.items() if s['band'] == b and s['rar'] != 'mythic' and s['kind'] == dk
           and (c != 'hunter' or s['style'] == 'ranged') and good(st, k, c)]
    if not ids:
        return dict(ok=False, viable=[], dom=None, strong=[], ids=[])
    vals = {i: {x: st[i]['Q'] * (1 + st[i]['gain'][x]) for x in SITS} for i in ids}
    best = {x: max(v[x] for v in vals.values()) for x in SITS}
    rel = {i: {x: vals[i][x] / best[x] for x in SITS} for i in ids}
    viable = [i for i in ids if max(rel[i].values()) >= 0.90]
    dom = [i for i in viable if len(viable) > 1 and all(all(vals[i][x] >= vals[o][x] for x in SITS) for o in viable if o != i)]
    strong = [i for i in ids if max(rel[i].values()) >= 0.95 and not set(st[i]['src']) & BF]
    ok = len(viable) >= 3 and not dom and len(strong) >= 1
    return dict(ok=ok, viable=viable, dom=dom[0] if dom else None, strong=strong, ids=ids, rel=rel)


def band_best_Q(st, b):
    return max(s['Q'] for s in st.values() if s['band'] == b and s['rar'] != 'mythic')


def do_skill(st, wid):
    s = copy.deepcopy(st[wid])
    f = (1 + s['sec'] + 0.1 * (s['sk'] + 1)) / (1 + s['sec'] + 0.1 * s['sk'])
    s['sk'] += 1
    if s['rar'] == 'rare':
        f *= 1.21 / 1.13; s['rar'] = 'epic'
    s['Q'] *= f
    st2 = dict(st); st2[wid] = s
    gap = max(0.0, band_best_Q(st2, s['band']) / s['Q'] - 1)
    Bn = max(0.04, min(0.28, 0.08 + 0.6 * gap))
    if s['B'] > 0:
        r = Bn / s['B']; s['gain'] = {k: v * r for k, v in s['gain'].items()}; s['B'] = Bn
    return st2


def do_pair(st, wid, order):
    s = copy.deepcopy(st[wid]); s['req'] = Q.split(s['L'], order)
    st2 = dict(st); st2[wid] = s
    return st2


def do_bow(st, wid):
    s = copy.deepcopy(st[wid]); s['style'] = 'ranged'
    st2 = dict(st); st2[wid] = s
    return st2


def actions(st, wid, hunter_cell):
    s = st[wid]
    if set(s['src']) & BF or s['rar'] in ('mythic', 'legendary') or s['L'] <= 2:
        return
    if s['sk'] < 2 and s['rar'] in ('rare', 'epic', 'uncommon'):
        yield 'skill', None
    for order in Q.TPL.get((s['direction'], s['kind']), []):
        req = Q.split(s['L'], order)
        if req != s['req']:
            yield 'pair', order
    if hunter_cell and s['new'] and s['style'] == 'melee' and s['kind'] == 'physical':
        yield 'bow', None


def apply(st, wid, act, arg):
    return do_skill(st, wid) if act == 'skill' else do_pair(st, wid, arg) if act == 'pair' else do_bow(st, wid)


def band_ok(st, b):
    return sum(cell(st, c, b)['ok'] for c in G.CLS)


def solve(st, max_iter=200, topk=12):
    """욕심쟁이: 띠 통과 수가 늘어나는 고침만 받는다. 한 걸음으로 안 되면 좋은 한 걸음 topk 개에서 두 걸음을 본다.
    한 무기의 요구 짝은 한 번만 바꾼다(되돌림 왕복 방지)."""
    fixes = []
    stuck = set()
    paired = set()
    for _ in range(max_iter):
        bad = [(c, b) for b in G.BANDS for c in G.CLS if not cell(st, c, b)['ok'] and (c, b) not in stuck]
        if not bad:
            break
        c, b = bad[0]
        cur = band_ok(st, b)
        singles = []
        for wid in [k for k, s in st.items() if s['band'] == b]:
            for act, arg in actions(st, wid, c == 'hunter'):
                if act == 'pair' and wid in paired:
                    continue
                st2 = apply(st, wid, act, arg)
                x = cell(st2, c, b)
                singles.append(((band_ok(st2, b), x['ok'], len(x['viable']), len(x['strong']), -COST[act]), wid, act, arg, st2))
        singles.sort(key=lambda t: t[0], reverse=True)
        chosen = None
        if singles and singles[0][0][0] > cur:
            chosen = [singles[0]]
        else:
            best2 = None
            for s1 in singles[:topk]:
                _, w1, a1, g1, st1 = s1
                for wid in [k for k, s in st1.items() if s['band'] == b]:
                    for act, arg in actions(st1, wid, c == 'hunter'):
                        if act == 'pair' and (wid in paired or wid == w1 and a1 == 'pair'):
                            continue
                        st2 = apply(st1, wid, act, arg)
                        sc = (band_ok(st2, b), -(COST[a1] + COST[act]))
                        if sc[0] > cur and (best2 is None or sc > best2[0]):
                            best2 = (sc, [s1, (None, wid, act, arg, st2)])
            if best2:
                chosen = best2[1]
        if not chosen:
            stuck.add((c, b)); continue
        for _, wid, act, arg, st2 in chosen:
            st = st2
            if act == 'pair':
                paired.add(wid)
            fixes.append(dict(cell=f'{c}|{b}', weapon=wid, name=W[wid]['name'], act=act,
                              arg=list(arg) if arg else None, req=st[wid]['req'], rar=st[wid]['rar'], sk=st[wid]['sk'],
                              src=st[wid]['src'], style=st[wid]['style']))
    return st, fixes, stuck


def table(st):
    out = {}
    for b in G.BANDS:
        for c in G.CLS:
            x = cell(st, c, b)
            out[f'{c}|{b}'] = dict(ok=x['ok'], n=len(x['ids']), viable=len(x['viable']), dom=x['dom'],
                                   strong=len(x['strong']), viable_ids=x['viable'])
    return out


if __name__ == '__main__':
    st0 = base_state()
    before = table(st0)
    st1, fixes, stuck = solve(st0)
    after = table(st1)
    nb = sum(v['ok'] for v in before.values()); na = sum(v['ok'] for v in after.values())
    print(f'칸 통과 {nb}/60 → {na}/60 · 고침 {len(fixes)} (skill {sum(f["act"]=="skill" for f in fixes)}, '
          f'pair {sum(f["act"]=="pair" for f in fixes)}, bow {sum(f["act"]=="bow" for f in fixes)})')
    for b in G.BANDS:
        row = []
        for c in G.CLS:
            x, y = before[f'{c}|{b}'], after[f'{c}|{b}']
            fmt = lambda v: f"{v['viable']}{'D' if v['dom'] else ''}{v['strong']}{'✔' if v['ok'] else '✘'}"
            row.append(f"{G.CLS_KO[c]} {fmt(x)}→{fmt(y)}")
        print(G.blabel(b), ' | '.join(row))
    print('못 고친 칸:', sorted(stuck, key=lambda x: (x[1], x[0])))
    for f in fixes:
        print(f)
    json.dump(dict(before=before, after=after, fixes=fixes, stuck=sorted([list(x) for x in stuck])),
              open(os.path.join(HERE, 'rv2_choice.json'), 'w'), ensure_ascii=False, indent=1)
