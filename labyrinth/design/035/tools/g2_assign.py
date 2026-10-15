# -*- coding: utf-8 -*-
"""무기 요구 능력치 고르기 (2단계).
 1) 무기마다 정체성 틀(TPL 첫째, 또는 WEAPON_FIX) 을 둔다.
 2) 고치기: 띠마다 직업별 '알맞은 무기(피해 종류 맞음 · 세금 ≤ 15%)' 가 목표보다 적으면, 손으로 정하지 않은 무기 중
    다른 후보 틀로 바꾸면 그 직업이 알맞아지고 다른 직업이 목표 밑으로 안 떨어지는 것을 정체성 손실이 적은 순으로 바꾼다.
    같은 띠 같은 모양은 다른 틀, 행운(LUK) 첫째는 띠마다 1~2개.
"""
import collections

import g2_core as G
import g2_req as Q
import g2_check as K

TARGET = {'guardian': 5, 'berserker': 5, 'hunter': 5, 'shadow': 5, 'arcanist': 4, 'priest': 4}


def norm(order, L):
    order = tuple(order)
    return order[:2] if (len(order) == 3 and L < 12) else order


def friendly_set(W, wid, order, sets, shields, b):
    P = 5 * b
    req = Q.split(W[wid]['L'], order) if order else {}
    out = set()
    for c in G.CLS:
        dk = 'magic' if c in ('arcanist', 'priest') else 'physical'
        if W[wid]['kind'] != dk:
            continue
        kit = K.best_kit(c, P, req, sets, shields, max(1, P - 15))
        if kit and kit['tax'] <= K.TAX_OK:
            out.add(c)
    return out


def assign(W, A, AR, log=None):
    for wid in Q.KIND_MAGIC:
        W[wid]['kind'] = 'magic'
    sets, shields = K.armor_sets(A, AR)
    out = {}
    for b in G.BANDS:
        ws = sorted([w for w in W.values() if w['band'] == b], key=lambda w: (w['L'], w['id']))
        cur = {}
        free = []
        pair_used = collections.Counter()
        prim = collections.Counter()
        for w in ws:
            if w['id'] in Q.WEAPON_FIX and Q.budget(w['L']) > 0:
                o = norm(Q.WEAPON_FIX[w['id']][0], w['L'])
                pair_used[frozenset(o[:2])] += 1
                prim[o[0]] += 1
        for w in ws:
            if Q.budget(w['L']) == 0:
                out[w['id']] = dict(order=None, requires={}, why='Lv1 — 요구 없음', auto=False)
                continue
            if w['id'] in Q.WEAPON_FIX:
                o, why = Q.WEAPON_FIX[w['id']]
                cur[w['id']] = (norm(o, w['L']), why, False)
            else:
                cands = [norm(o, w['L']) for o in Q.TPL[(w['direction'], w['kind'])]]
                # 1단계: 정체성(앞 순서) + 같은 띠 안 짝·주 능력치가 겹치지 않게
                best = None
                for i, o in enumerate(cands):
                    sc = 0.5 * i + 0.8 * pair_used[frozenset(o[:2])] + 0.4 * prim[o[0]]
                    if best is None or sc < best[0]:
                        best = (sc, i, o)
                _, i, o = best
                pair_used[frozenset(o[:2])] += 1
                prim[o[0]] += 1
                cur[w['id']] = (o, '자동 — ' + G.DIRS[w['direction']]['name'] + (' 정체성' if i == 0 else ' (같은 띠와 다르게)'), True)
                if w['rar'] != 'mythic':
                    free.append(w['id'])
        # 같은 모양 같은 틀 풀기 (자동만)
        seen = collections.defaultdict(list)
        for wid, (o, why, auto) in cur.items():
            seen[(W[wid]['shape'], o)].append(wid)
        for (shape, o), ids in seen.items():
            for wid in ids[1:]:
                if not cur[wid][2]:
                    continue
                cands = [norm(x, W[wid]['L']) for x in Q.TPL[(W[wid]['direction'], W[wid]['kind'])]]
                for x in cands:
                    if not any(cur[o2][0] == x and W[o2]['shape'] == shape for o2 in cur if o2 != wid):
                        cur[wid] = (x, '자동 — 같은 모양과 다르게', True)
                        break
        # 고치기
        for it in range(60):
            fr = {wid: friendly_set(W, wid, cur[wid][0], sets, shields, b) for wid in cur if W[wid]['rar'] != 'mythic'}
            cnt = collections.Counter(c for s in fr.values() for c in s)
            short = [c for c in G.CLS if cnt[c] < TARGET[c]]
            if not short:
                break
            c0 = min(short, key=lambda c: cnt[c] - TARGET[c])
            best = None
            for wid in free:
                if c0 in fr[wid]:
                    continue
                cands = [norm(x, W[wid]['L']) for x in Q.TPL[(W[wid]['direction'], W[wid]['kind'])]]
                for i, x in enumerate(cands):
                    if x == cur[wid][0]:
                        continue
                    if any(cur[o2][0] == x and W[o2]['shape'] == W[wid]['shape'] for o2 in cur if o2 != wid):
                        continue
                    nf = friendly_set(W, wid, x, sets, shields, b)
                    if c0 not in nf:
                        continue
                    lost = fr[wid] - nf
                    if any(cnt[c] - 1 < TARGET[c] for c in lost):
                        continue
                    cost = i + 0.5 * len(lost) - 0.2 * len(nf)
                    if best is None or cost < best[0]:
                        best = (cost, wid, x)
            if best is None:
                if log is not None:
                    log.append(f'띠 {b}: {c0} 를 더 채울 무기 없음 ({cnt[c0]}/{TARGET[c0]})')
                break
            _, wid, x = best
            cur[wid] = (x, f'자동 — {G.CLS_KO[c0]} 몫을 채우려 바꿈', True)
        for wid, (o, why, auto) in cur.items():
            out[wid] = dict(order=o, requires=Q.split(W[wid]['L'], o), why=why, auto=auto)
    return out


if __name__ == '__main__':
    W = G.weapons_all()
    A = G.armor_all()
    AR = Q.armor_requires(A)
    log = []
    WR = assign(W, A, AR, log)
    print('\n'.join(log))
    K.run(W, WR, A, AR)
    prim = collections.Counter()
    for b in G.BANDS:
        c = collections.Counter()
        for wid, r in WR.items():
            if W[wid]['band'] == b and r['order']:
                for s in r['order']:
                    c[s] += 1
        print(G.blabel(b), dict(c))
