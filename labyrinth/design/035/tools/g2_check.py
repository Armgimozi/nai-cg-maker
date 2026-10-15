# -*- coding: utf-8 -*-
"""요구 능력치 검사 — 직업마다(직업 기본 + 시작 5 + 레벨당 5, 칭호 없음 = 가장 나쁜 경우, 초기화 뒤) 띠마다 알맞은 한 벌을 낄 수 있는가.

  한 벌 = 무기 1 (그 띠) + 방어구 네 부위 (그 레벨까지 나온 세트 중 하나, 겉모습 무엇이든) (+ 수호기사는 방패 1)
  세금  = 요구치를 채우려고 '알맞은 분배'(combat_spec sensible_spread new) 밖으로 더 찍는 포인트 ÷ 받은 포인트
  알맞음 = 낄 수 있고(포인트 안) 세금 ≤ 15%
결과: g2_check.json · 화면 표
"""
import collections
import json
import os

import g2_core as G
import g2_req as Q

TAX_OK = 0.15


def armor_sets(A, AR):
    """세트(또는 단품 투구 세트 대신) → {look, L, requires}. 세트 네 부위 요구가 같으므로 하나로."""
    sets = {}
    for aid, a in A.items():
        if a['slot'] == 'offhand' or not a['set']:
            continue
        s = sets.setdefault(a['set'], dict(look=a['look'], L=a['L'], requires=AR[aid]['requires'], src=a['sources'], new=a['new']))
        s['L'] = max(s['L'], a['L'])
    shields = {aid: dict(L=a['L'], requires=AR[aid]['requires']) for aid, a in A.items() if a['slot'] == 'offhand'}
    return sets, shields


def best_kit(cls, P, weapon_req, sets, shields, lo_level, look=None):
    """그 직업이 P 레벨에 weapon 과 함께 낄 수 있는 가장 좋은 방어구(세금 가장 적고 레벨 높은 것). 없으면 None.
    look 을 주면 그 겉모습 세트만."""
    best = None
    for sid, s in sets.items():
        if s['L'] > P or s['L'] < lo_level:
            continue
        if look and s['look'] != look:
            continue
        reqs = [weapon_req, s['requires']]
        sh = None
        if cls == 'guardian':
            cands = [(k, v) for k, v in shields.items() if v['L'] <= P and v['L'] >= lo_level]
            if cands:
                # 세금 가장 적은 방패
                sh = min(cands, key=lambda kv: (Q.tax_points(cls, P, Q.kit_req(reqs + [kv[1]['requires']]))[0], -kv[1]['L']))
                reqs = reqs + [sh[1]['requires']]
        req = Q.kit_req(reqs)
        extra, ok, need = Q.tax_points(cls, P, req)
        if not ok:
            continue
        tax = extra / G.points_at(P)
        key = (tax > TAX_OK, round(tax, 3), -s['L'])
        if best is None or key < best[0]:
            best = (key, dict(set=sid, look=s['look'], set_L=s['L'], shield=sh[0] if sh else None, tax=round(tax, 3),
                              need=need, req=req))
    return best[1] if best else None


def run(W, WR, A, AR, verbose=True):
    sets, shields = armor_sets(A, AR)
    res = {}
    lock = []
    for b in G.BANDS:
        P = 5 * b
        lo = max(1, P - 15)
        ws = [w for w in W.values() if w['band'] == b and w['rar'] != 'mythic']
        for c in G.CLS:
            good, ok_any = [], []
            for w in ws:
                kit = best_kit(c, P, WR[w['id']]['requires'], sets, shields, lo)
                if kit is None:
                    continue
                ok_any.append(w['id'])
                if kit['tax'] <= TAX_OK:
                    good.append((w['id'], kit))
            # 직업 피해 종류가 맞는 것 (물리 직업 = physical, 비전술사 = magic, 사제 = magic 또는 지원)
            dk = 'magic' if c in ('arcanist', 'priest') else 'physical'
            good_kind = [g for g in good if W[g[0]]['kind'] == dk]
            # 보기: 직업 겉모습(판금·가죽·천) 한 벌 중 세금 가장 적은 것
            nat = []
            for g in good_kind:
                kn = best_kit(c, P, WR[g[0]]['requires'], sets, shields, lo, Q.NATURAL_LOOK[c])
                if kn is not None:
                    nat.append((kn['tax'], -W[g[0]]['L'], g[0], kn))
            nat.sort()
            natural = dict(weapon=nat[0][2], **nat[0][3]) if nat else None
            n_nat = sum(1 for x in nat if x[0] <= TAX_OK)
            srcs = collections.Counter()
            res[f'{c}|{b}'] = dict(P=P, wearable=len(ok_any), good=len(good), good_kind=len(good_kind),
                                   good_ids=[g[0] for g in good_kind], styles=dict(collections.Counter(W[g[0]]['style'] for g in good_kind)),
                                   example=(good_kind[0][1] if good_kind else (good[0][1] if good else None)),
                                   natural=natural, good_natural_look=n_nat)
            if len(good_kind) < 3:
                lock.append((c, b, len(good_kind)))
    # 무기마다: 자기 레벨에서 그 무기를 '알맞게' 낄 수 있는 직업
    per_weapon = {}
    for wid, w in W.items():
        P = max(1, w['L'])
        cl = []
        for c in G.CLS:
            kit = best_kit(c, P + 2, WR[wid]['requires'], sets, shields, max(1, P - 15))
            if kit and kit['tax'] <= 0.25:
                cl.append(c)
        per_weapon[wid] = cl
    # 직업 기본 분배로 못 끼는 무기는 다른 빌드(ARCH)로 끼는가
    per_weapon_arch = {}
    for wid, cl in per_weapon.items():
        if cl or Q.budget(W[wid]['L']) == 0:
            continue
        P = W[wid]['L'] + 2
        got = []
        for an, ratio in Q.ARCH.items():
            for c in G.CLS:
                req = Q.kit_req([WR[wid]['requires']])
                extra, ok, need = Q.tax_points(c, P, req, ratio)
                if ok and extra / G.points_at(P) <= 0.15:
                    got.append(an)
                    break
        per_weapon_arch[wid] = got
    orphans = [wid for wid, a in per_weapon_arch.items() if not a]
    # 방어구 세트마다: 그 세트 레벨에서 알맞게 입는 직업
    per_set = {}
    singles = {aid: dict(L=a['L'], requires=AR[aid]['requires']) for aid, a in A.items() if not a['set']}
    for sid, s in list(sets.items()) + list(singles.items()):
        cl = []
        for c in G.CLS:
            extra, ok, need = Q.tax_points(c, s['L'] + 2, s['requires'])
            if ok and extra / G.points_at(s['L'] + 2) <= 0.15:
                cl.append(c)
        per_set[sid] = cl
    if verbose:
        print('직업 × 띠 : 알맞은 무기 수 (피해 종류 맞음) / 낄 수 있는 무기 수')
        print('      ' + ' '.join(f'{G.blabel(b):>7s}' for b in G.BANDS))
        for c in G.CLS:
            print(f'{c:10s}' + ' '.join(f"{res[f'{c}|{b}']['good_kind']:3d}/{res[f'{c}|{b}']['wearable']:<3d}" for b in G.BANDS))
        print('부족 (<3):', lock)
        print('직업 기본 분배로는 안 맞고 다른 빌드로 맞는 무기:', per_weapon_arch)
        print('어떤 빌드로도 알맞게 못 끼는 무기:', orphans)
        print('세트 → 알맞게 입는 직업:', {k: v for k, v in per_set.items()})
    return dict(by_class_band=res, short=lock, per_weapon=per_weapon, per_weapon_arch=per_weapon_arch, orphans=orphans, per_set=per_set)


if __name__ == '__main__':
    W = G.weapons_all()
    WR = Q.assign_weapons(W)
    A = G.armor_all()
    AR = Q.armor_requires(A)
    out = run(W, WR, A, AR)
    with open(os.path.join(G.HERE, 'g2_check.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
