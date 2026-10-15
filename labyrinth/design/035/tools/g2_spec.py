# -*- coding: utf-8 -*-
"""TASK C 2판 (gear-c2) — 데이터 만들기 → ../gear_spec.json (+ g2_state.json: 문서 만들기용 중간값)

  python3 tools/g2_spec.py   # 데이터
  python3 tools/g2_md.py     # 문서 (gear_spec.md)
"""
import collections
import copy
import json
import math
import os
import statistics

import g2_core as G
import g2_req as Q
import g2_assign as S
import g2_check as K
import g2_loot as L

OUT = os.path.join(G.D2, 'gear_spec.json')
STATE = os.path.join(G.HERE, 'g2_state.json')

# combat_spec 한 방 피해에서 1점 옮긴 새 무기 (같은 띠 대장간 기준 ±5% 규칙) — 전투 설계자와 맞출 목록
PER_HIT_FIX = {}

# 부가 스탯 가치 (효과 설계자 ue_gen.power 와 같은 가중치) — '자기 상황' 비교용
WGT = {'crit_chance': 0.5, 'crit_damage': 0.2, 'attack_speed': 0.7, 'lifesteal': 0.4, 'skill_damage': 0.35,
       'cooldown_reduction': 0.45, 'damage_reduction': 0.8, 'evasion': 0.6, 'move_speed': 0.15}
SEC_KO = {'crit_chance': '치명 확률', 'crit_damage': '치명 피해', 'attack_speed': '공격 속도', 'move_speed': '이동 속도',
          'lifesteal': '흡혈', 'hp': '최대 HP', 'hp_regen': 'HP 재생', 'damage_reduction': '피해 감소', 'defense': '방어',
          'skill_damage': '스킬 피해', 'cooldown_reduction': '재사용 감소', 'mp': '최대 MP', 'mana_regen': 'MP 재생',
          'heal_power': '치유력', 'evasion': '회피', 'block_chance': '막기'}
SEC_KO.update(G.STAT_KO)


def sec_value(L_, stats):
    Sp = 8 + 2.5 * (L_ - 1)
    v = 0
    for k, r in stats.items():
        if k == 'damage':
            continue
        m = G.mid(r)
        if k in G.STATS6:
            v += (0.01 * m / (1 + 0.01 * Sp)) if k in ('STR', 'INT') else m * 0.002
        elif k in WGT:
            v += WGT[k] * m
        elif k == 'heal_power':
            v += 0.4 * m / (1.5 * Sp)
        elif k == 'mana_regen':
            v += 0.2 * m / (1 + 0.05 * Sp)
        elif k == 'hp':
            v += m / (100 + 9 * L_) * 0.4
        elif k == 'defense':
            v += m * 0.004
        elif k == 'hp_regen':
            v += m * 0.01
        elif k == 'mp':
            v += m / (80 + 3 * L_) * 0.15
    return v


def main_secondary(stats):
    best = None
    for k, r in stats.items():
        if k == 'damage' or k in G.STATS6:
            continue
        w = WGT.get(k, 0.3)
        val = w * G.mid(r) if k in WGT else 0.01
        if best is None or val > best[0]:
            best = (val, k)
    return best[1] if best else None


def K_style(style, interval):
    if style == 'ranged':
        return 1.413
    if style == 'caster':
        return 1.22
    return 1.47 - 0.143 * max(0.0, 1.0 / interval - 1.5)


def base_power(w):
    """같은 단계 비교값 = 스킬 위력 ÷ 시전 배율 (= DPS 등가 ÷ K) — 한 방 피해 가운데값 기준."""
    return (G.mid(w['per_hit']) / w['interval']) / K_style(w['style'], w['interval'])


def fix_per_hit(W, ref, wid):
    """가장 작은 이동으로 비교값을 기준 ±4.5% 안에 넣는 정수 범위 (폭은 ±1 까지만 바꾼다)."""
    w = W[wid]
    lo, hi = w['per_hit']
    width = hi - lo
    best = None
    for a in range(lo - 3, lo + 4):
        for d in (width, width - 1, width + 1):
            b = a + d
            if b <= a:
                continue
            bp = ((a + b) / 2 / w['interval']) / K_style(w['style'], w['interval'])
            dev = bp / ref - 1
            if abs(dev) <= 0.045:
                cost = abs((a + b) / 2 - (lo + hi) / 2) + 0.3 * abs(d - width)
                if best is None or cost < best[0]:
                    best = (cost, [a, b], dev)
    return best


def weapon_skill_factor_new(w):
    """새 무기 스킬 피해 숫자 계수 = K(방식, 새 간격) ÷ (옛 판 기준 초당 횟수 × 시전 배율) — combat_spec §5.5 와 같은 식."""
    o = G.OLDW[w['id']]
    if w['style'] == 'ranged':
        rate = 1.25 / 1.15
    else:
        rate = o['attack']['speed']
    spm = 1.05 if w['style'] == 'caster' else 1.0
    return K_style(w['style'], w['interval']) / (rate * spm)


def scale_skill(skill, f):
    s = copy.deepcopy(skill)

    def walk(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k == 'damage' and isinstance(v, (int, float)) and not isinstance(v, bool):
                    o[k] = round(v * f, 2)
                elif k == 'execute' and isinstance(v, dict):
                    for kk in ('amount', 'boss_amount'):
                        if kk in v:
                            v[kk] = round(v[kk] * f, 2)
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(s.get('mechanics'))
    if isinstance(s.get('params', {}).get('damage'), (int, float)):
        s['params']['damage'] = round(s['params']['damage'] * f, 2)
    return s


def main():
    W = G.weapons_all()
    A = G.armor_all()
    AR = Q.armor_requires(A)
    log = []
    WR = S.assign(W, A, AR, log)

    # ── 띠별 대장간 기준 (가장 높은 단계 대장간 무기들의 비교값 가운데값) ──
    forge_ref = {}
    for b in G.BANDS:
        ws = [w for w in W.values() if w['band'] == b and w['rar'] != 'mythic']
        F = [w for w in ws if 'F' in L.weapon_kinds(w)]
        topL = max(w['L'] for w in F)
        refw = sorted([w for w in F if w['L'] == topL], key=base_power)
        ref = statistics.median([base_power(w) for w in refw])
        forge_ref[b] = dict(ref=ref, level=topL, rarity=refw[0]['rar'], ids=[w['id'] for w in refw])
    # ±5% 밖 새 옆길 무기 → 한 방 피해 1점 안팎 다시 반올림
    for wid, w in W.items():
        if not w['new'] or L.weapon_kinds(w)[0] not in 'MTSVE':
            continue
        ref = forge_ref[w['band']]['ref']
        dev = base_power(w) / ref - 1
        if abs(dev) > 0.05:
            fx = fix_per_hit(W, ref, wid)
            if fx:
                PER_HIT_FIX[wid] = dict(old=list(w['per_hit']), new=fx[1], dev_old=round(dev, 3), dev_new=round(fx[2], 3))
                w['per_hit'] = fx[1]
                w['stats']['damage'] = fx[1]
                spm = 1.05 if w['style'] == 'caster' else 1.0
                w['sp'] = round(base_power(w) * spm, 2)
                w['dps'] = round(G.mid(fx[1]) / w['interval'], 2)

    # ── 루팅 ──
    T, changes, pools, fac, REQ = L.solve(W, WR, A, AR)

    # ── 요구 능력치 검사 ──
    chk = K.run(W, WR, A, AR, verbose=False)

    # ── 무기마다 획득처 · 회차 ──
    src = {}
    for wid, w in W.items():
        ks = L.weapon_kinds(w)
        t = L.tier_of_weapon(w)
        info = dict(kinds=ks, tier=t, window=[max(1, 5 * t - 10), min(50, 5 * t + 5)], floors=[f for f in (t - 1, t, t + 1) if 1 <= f <= 10],
                    homes=[])
        for k in ks:
            if k == 'B':
                p = L.boss_rate(wid, W, REQ)
                info['homes'].append(dict(kind='B', table=G.BOSS_TABLE[t], per_kill=round(p, 3), runs=round(1 / p, 1) if p else None))
            elif k == 'F':
                rid = next((r for r, v in G.RECIPES.items() if v['result'] == wid), None)
                rc = G.RECIPES[rid]
                mr, gr, det, gpr = L.forge_cost(t, rc, T)
                info['homes'].append(dict(kind='F', recipe=rid, gold=rc.get('gold', 0), materials=rc['materials'],
                                          mat_runs=round(mr, 2), gold_runs=round(gr, 2), runs=round(max(mr, gr), 2)))
            elif k == 'P':
                shop = SHOP[wid]
                g = L.run_gold(max(1, t))
                info['homes'].append(dict(kind='P', npc='merchant', price=shop['price'], level_req=shop['level_req'],
                                          gold_runs=round(shop['price'] / g, 2), runs=round(shop['price'] / g, 2)))
            else:
                own = L.weapon_rate(wid, t, W, T, REQ, k)
                nxt = L.weapon_rate(wid, t + 1, W, T, REQ, k) if t < 10 else 0.0
                prv = L.weapon_rate(wid, t - 1, W, T, REQ, k) if t > 1 else 0.0
                tab = {'M': L.pool_id(t, 'drop'), 'T': L.pool_id(t, 'trial'), 'S': L.pool_id(t, 'special'),
                       'V': L.pool_id(t, 'hoard'), 'E': L.pool_id(t, 'elite')}[k]
                ch = None
                for e in (T[tab].get('entries') or []) + (T[tab].get('guaranteed') or []):
                    if wid in (e.get('one_of') or []):
                        ch = e.get('chance', 'guaranteed')
                        n = len(e['one_of'])
                info['homes'].append(dict(kind=k, table=tab, chance=ch, pool_size=n,
                                          runs=round(L.runs(own), 1) if own else None,
                                          runs_next_floor=round(L.runs(nxt), 1) if nxt else None,
                                          runs_prev_floor=round(L.runs(prv), 1) if prv else None))
        src[wid] = info

    # ── 띠별 표 ──
    bands = {}
    for b in G.BANDS:
        ws = sorted([w for w in W.values() if w['band'] == b], key=lambda w: (w['L'], w['id']))
        nm = [w for w in ws if w['rar'] != 'mythic']
        styles = collections.Counter(w['style'] for w in nm)
        kinds_ = collections.Counter(w['kind'] for w in nm)
        stats = collections.Counter()
        prim = collections.Counter()
        for w in nm:
            for s in (WR[w['id']]['order'] or ()):
                stats[s] += 1
            if WR[w['id']]['order']:
                prim[WR[w['id']]['order'][0]] += 1
        dirs = collections.Counter(w['direction'] for w in nm)
        sk = collections.Counter()
        for w in nm:
            for k in L.weapon_kinds(w):
                sk[k] += 1
        # 증명 표
        rows = []
        Pp = {}
        for w in nm:
            Pp[w['id']] = base_power(w) * (1 + sec_value(w['L'], w['stats']) + 0.1 * len(w['skills']))
        best = max(nm, key=lambda w: Pp[w['id']])
        Bbest = (best['strength'] or 0.8) * 0.10
        for w in nm:
            s_ = (w['strength'] or 0.8)
            B = s_ * 0.10
            situ = Pp[w['id']] * (1 + 2 * B) >= Pp[best['id']] * (1 + Bbest)
            rows.append(dict(id=w['id'], name=w['name'], new=w['new'], L=w['L'], rar=w['rar'], style=w['style'], kind=w['kind'],
                             interval=w['interval'], rate=round(1 / w['interval'], 1), per_hit=w['per_hit'], dps=round(G.mid(w['per_hit']) / w['interval'], 1),
                             sp=round(w['sp'], 1), vs_forge=round(base_power(w) / forge_ref[b]['ref'] - 1, 3),
                             secondary=main_secondary(w['stats']), direction=w['direction'], req=WR[w['id']]['requires'],
                             kinds=L.weapon_kinds(w), strength=s_, situational=('best' if w['id'] == best['id'] else situ)))
        bands[b] = dict(total=len(ws), non_mythic=len(nm), new=sum(1 for w in nm if w['new']), styles=dict(styles), kinds=dict(kinds_),
                        req_stats=dict(stats), primary=dict(prim), directions=len(dirs), dir_counts=dict(dirs), source_kinds=dict(sk),
                        n_source_kinds=len(sk), forge_ref=forge_ref[b], rows=rows, best=best['id'])

    # ── 띠 × 획득처 기대 회차 ──
    rates = {}
    for b in G.BANDS:
        r = {}
        for k in ('B', 'F', 'M', 'T', 'S', 'V', 'E', 'P'):
            vals = []
            for w in W.values():
                if w['band'] != b or w['rar'] == 'mythic':
                    continue
                for h in src[w['id']]['homes']:
                    if h['kind'] == k and h.get('runs'):
                        if k == 'M' and w['L'] == 1:
                            continue
                        vals.append(h['runs'])
            if vals:
                vals.sort()
                r[k] = dict(n=len(vals), median=round(statistics.median(vals), 1), lo=round(vals[0], 1), hi=round(vals[-1], 1))
        rates[b] = r

    # ── 1회 돌기 장비 수 (보통·솔로·LUK0) — 전과 후 ──
    def gear_per_run(tables, f):
        tot = collections.Counter()
        for t, n in L.run_sources(f):
            for k, v in L.table_yield(t, tables).items():
                if k in G.ITEMS and G.ITEMS[k].get('type') in ('weapon', 'armor', 'accessory') or k in W or k in A:
                    typ = 'weapon' if k in W else 'armor'
                    tot[typ] += n * v
        # 특별 시련 · 금고·미믹 (코드가 굴리는 새 표)
        if f'special_trial_f{f:02d}' in tables:
            for k, v in L.table_yield(f'special_trial_f{f:02d}', tables).items():
                if k in W or k in A:
                    tot['weapon' if k in W else 'armor'] += L.SPECIAL_Q_EFF * L.SPECIAL_C * v
        if f'hoard_f{f:02d}' in tables:
            c = L.maze(f)
            for k, v in L.table_yield(f'hoard_f{f:02d}', tables).items():
                if k in W or k in A:
                    tot['weapon' if k in W else 'armor'] += (c['vault'] + c['mimic']) * v
        return {k: round(v, 2) for k, v in tot.items()}
    per_run = {f: dict(before=gear_per_run(G.LOOT, f), after=gear_per_run(T, f)) for f in range(1, 11)}

    # ── 대장간 기준 (띠마다 대표 레시피 하나) ──
    forge = {}
    for b in G.BANDS:
        rid = forge_ref[b]['ids'][0]
        h = next(h for h in src[rid]['homes'] if h['kind'] == 'F')
        forge[b] = dict(weapon=rid, recipe=h['recipe'], gold=h['gold'], mat_runs=h['mat_runs'], gold_runs=h['gold_runs'],
                        materials=h['materials'], level=forge_ref[b]['level'], rarity=forge_ref[b]['rarity'])

    # 대장간 무기 골드 ×1.5 (단계 2~10) — '바닥값'이 거의 공짜가 되지 않게
    recipe_gold = {}
    for rid, r in G.RECIPES.items():
        it = G.ITEMS.get(r['result'], {})
        if it.get('type') == 'weapon' and it.get('floor', 1) >= 2:
            recipe_gold[rid] = dict(old=r['gold'], new=int(round(r['gold'] * 1.5 / 50.0) * 50))
    for b, fv in forge.items():
        g = recipe_gold.get(fv['recipe'])
        if g:
            fv['gold_new'] = g['new']
            fv['gold_runs_new'] = round(fv['gold_runs'] * g['new'] / g['old'], 2)
        else:
            fv['gold_new'] = fv['gold']
            fv['gold_runs_new'] = fv['gold_runs']
    state = dict(W=W, WR=WR, AR=AR, A=A, src=src, recipe_gold=recipe_gold, bands=bands, rates=rates, per_run=per_run, forge=forge, fac=fac,
                 check=chk, assign_log=log, per_hit_fix=PER_HIT_FIX, pools={k: dict(v) for k, v in pools.items()},
                 changes=changes)
    spec = build_json(state, T)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    state['fac'] = {k: v for k, v in fac.items() if k != '_weapons'}
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    print('ok', len(spec['weapons']), 'new weapons;', len(spec['existing_changes']), 'existing;', len(spec['loot_changes']), 'tables')
    print('per_hit_fix', PER_HIT_FIX)
    print('assign log', log)
    print('short', chk['short'], 'orphans', chk['orphans'])


SHOP = {'wayfarer_sabre': dict(price=1500, level_req=3), 'silk_antler_staff': dict(price=2000, level_req=8),
        'glowcap_rapier': dict(price=2500, level_req=11)}


def items_sources(kinds):
    out = []
    for k in kinds:
        for s in G.SK_SRC[k]:
            if s not in out:
                out.append(s)
    return out


def build_json(st, T):
    W, WR, AR, A, src = st['W'], st['WR'], st['AR'], st['A'], st['src']
    weapons = {}
    for wid, w in W.items():
        if not w['new']:
            continue
        o = G.OLDW[wid]
        req = WR[wid]['requires']
        prim = WR[wid]['order'][0] if WR[wid]['order'] else None
        stats = {}
        old_line = next((k for k in o['stats'] if k in G.STATS6), None)
        for k, v in o['stats'].items():
            if k == 'damage':
                stats['damage'] = list(w['per_hit'])
            elif k == old_line and prim and prim != k and prim not in o['stats']:
                stats[prim] = v
            else:
                stats[k] = v
        f = weapon_skill_factor_new(w)
        skills = [scale_skill(s, f) for s in (o.get('weapon_skills') or [])]
        s = src[wid]
        h = s['homes'][0]
        e = dict(name=o['name'], type='weapon',
                 attack=dict(style=w['style'], interval=w['interval'], kind=w['kind']),
                 rarity=o['rarity'], level_req=o['level_req'], tier=s['tier'], requires=req, stats=stats, pool=False,
                 sources=items_sources(s['kinds']), unique=o['unique'])
        if skills:
            e['weapon_skills'] = skills
        e.update(model=o['model'], texture=o['texture'], lore=o['lore'])
        # 명세용 (items.yml 에 넣을 때 뺀다)
        e['_spec'] = dict(direction=w['direction'], level_band=G.blabel(w['band']), level_window=s['window'], floors=s['floors'],
                          source=h, per_hit_from_combat_spec=G.CW[wid]['per_hit'], per_hit_fixed=wid in PER_HIT_FIX,
                          dps_equiv=round(G.mid(w['per_hit']) / w['interval'], 2), skill_power=round(w['sp'], 2),
                          rate_per_s=round(1 / w['interval'], 2), weapon_skill_factor=round(f, 3) if skills else None,
                          unique_strength=o.get('unique_strength'), unique_tooltip=o.get('unique_tooltip'),
                          requires_why=WR[wid]['why'], requires_order=WR[wid]['order'])
        e['direction'] = w['direction']
        mr = o.get('model_recipe') or {}
        # model: items.yml 의 {shape, length} + 명세용 palette · notes · hold · new_silhouette (넣을 때 shape·length 만 남긴다)
        e['model'] = dict(o['model'], palette=o['texture']['palette'], style=o['texture'].get('style'),
                          new_silhouette=mr.get('new_silhouette', False),
                          hold=G.OLD['new_shapes'].get(o['model']['shape'], {}).get('hold', {}),
                          notes=mr.get('notes'))
        e['source'] = [{k: v for k, v in hh.items() if k in ('kind', 'table', 'chance', 'pool_size', 'recipe', 'price', 'level_req', 'runs')}
                       for hh in s['homes']]
        weapons[wid] = e
    existing = {}
    for wid, w in W.items():
        if w['new']:
            continue
        c = G.CW[wid]
        v = G.ITEMS[wid]
        ch = dict(remove=['weapon_type', 'floor', 'classes', 'requires_any'], tier=v['floor'],
                  attack=dict(style=w['style'], interval=w['interval'], kind=w['kind']),
                  stats_damage=list(c['per_hit']), requires=WR[wid]['requires'], requires_old=v.get('requires') or {},
                  requires_why=WR[wid]['why'], weapon_skill_factor=c.get('weapon_skill_factor'),
                  sources=v.get('sources'), direction=w['direction'])
        if w['kind'] != c['kind']:
            ch['kind_changed'] = f"{c['kind']} → {w['kind']}"
        existing[wid] = ch
    armor_changes = {}
    for aid, a in A.items():
        if a['new']:
            continue
        v = G.ITEMS[aid]
        armor_changes[aid] = dict(remove=['floor', 'classes', 'requires_any'], tier=v.get('floor'), requires=AR[aid]['requires'],
                                  requires_old=dict(v.get('requires') or {}, **({'any': v['requires_any']} if v.get('requires_any') else {})),
                                  look=a['look'], why=AR[aid]['why'])
    sets = {}
    for sid, s in G.OLD['armor_sets'].items():
        s2 = copy.deepcopy(s)
        for pid, p in s2['pieces_items'].items():
            p.pop('requires_any', None)
            p['requires'] = AR[pid]['requires']
            p['tier'] = p.pop('floor')
            p.pop('classes', None)
        dz = s2.get('design', {})
        if 'floor' in dz:
            dz['tier'] = dz.pop('floor')
        dz.pop('kind', None)
        s2['requires'] = Q.ARMOR_FIX[sid][0]
        s2['requires_why'] = Q.ARMOR_FIX[sid][1]
        s2['tier'] = next(iter(s2['pieces_items'].values()))['tier']
        s2['sources'] = next(iter(s2['pieces_items'].values()))['sources']
        sets[sid] = s2
    loot = {}
    for tid, c in st['changes'].items():
        loot[tid] = dict(op=c['op'], note=c['note'], **({} if c['table'] is None else c['table']))
    shapes = {}
    for k, v in G.OLD['new_shapes'].items():
        v2 = copy.deepcopy(v)
        v2.pop('speed', None)
        v2['interval'] = G.COMBAT['shape_interval'][k]
        v2['rate_per_s'] = round(1 / v2['interval'], 2)
        v2['weapons'] = sorted(wid for wid, w in W.items() if w['shape'] == k)
        shapes[k] = v2
    spec = dict(version='gear-c2 (labyrinth 0.3.4 → 0.3.5 안: 종류 없음 · 무기마다 간격 · 요구 능력치 AND 나눔 · 층 이름표 없음)',
                summary=dict(weapons_before=131, weapons_new=len(weapons), weapons_after=131 + len(weapons),
                             armor_sets_new=len(sets), armor_pieces_new=sum(len(s['pieces']) for s in sets.values()),
                             new_silhouettes=len(shapes), requires_rewritten=len(existing) + len(armor_changes) + len(weapons) + 24,
                             per_hit_fixed=len(PER_HIT_FIX), short_class_bands=st['check']['short'], orphans=st['check']['orphans']),
                formulas=dict(
                    requirement_budget='T(L) = ceil(2.75 × (L − 1)), L ≤ 2 이면 요구 없음 (지금 한 능력치 ceil(2.5×(L−1)) 의 1.1배)',
                    requirement_split='두 능력치 60/40 (a = round(0.6T), b = T − a) · 세 능력치 50/30/20 (L ≥ 12 부터, a = round(0.5T), b = round(0.3T), c = 나머지)',
                    requirement_pick='무기: (방향 pairs_stats + 피해 능력치 물리 STR / 마법 INT) 후보 틀 → 같은 띠 짝·주 능력치 덜 겹치게 → 직업별 알맞은 무기 목표(수호·광전·사냥·그림자 5, 비전·사제 4) 채우기. 방어구: 세트마다 손으로 (겉모습 + 정체성)',
                    tier='단계 N = Lv 5N−5~5N (옛 floor 값). 레벨 창 = Lv 5N−10~5N+5 → N−1·N·N+1 층이 준다',
                    floor_mix='층 f 의 단계 무게 f−1 : f : f+1 = 2 : 7 : 1 (없는 단계는 빼고 다시 나눔)',
                    pick='새 루팅 항목 {pick: [{table, weight}], chance} — chance 를 통과하면 무게대로 하위 표 하나를 굴린다 (guaranteed 에도 둘 수 있음)',
                    build_bias='own_class_bias → own_build_bias 0.65: one_of 에서 65% 확률로 "요구치 가장 큰 능력치가 줍는 사람 능력치(직업 기본+분배+칭호) 상위 2개 안" 인 장비만 후보 (없으면 전체)',
                    sidegrade='같은 띠 대장간 기준 비교값 = (한 방 가운데값 ÷ 간격) ÷ K(방식, 간격) (= 스킬 위력 ÷ 시전 배율). 새 옆길 무기는 ±5% 안',
                    per_hit='combat_spec.json per_hit 그대로 (§5.7 식) — 아래 per_hit_fix 만 1점 안팎 다시 반올림',
                    new_weapon_skill_factor='K(방식, 새 간격) ÷ (옛 판 초당 횟수 × 시전 1.05) — combat_spec §5.5 와 같은 식, 새 무기 스킬 피해 숫자에 이미 곱함'),
                per_hit_fix=PER_HIT_FIX,
                weapons=weapons, existing_changes=existing, armor_changes=armor_changes, armor_sets=sets,
                recipes_new=G.OLD['recipes_new'],
                recipes_changes={rid: dict(gold=v['new'], gold_old=v['old']) for rid, v in st['recipe_gold'].items()},
                shop=dict(npc='merchant', entries=[dict(item=k, **v) for k, v in SHOP.items()],
                          note='npcs.yml ShopEntry 의 level_req(이미 있음) — 그 레벨이 돼야 진열. 코드 변경 없음'),
                loot_settings=dict(own_class_bias='삭제 → own_build_bias: 0.65'),
                loot_changes=loot, special_trial=special_trial(st), new_shapes=shapes,
                rates={G.blabel(b): v for b, v in st['rates'].items()},
                forge={G.blabel(b): v for b, v in st['forge'].items()},
                gear_per_run=st['per_run'],
                class_check=dict(rule='직업 기본+시작 5+레벨당 5, 칭호 없음, 초기화 뒤 · 무기(그 띠)+방어구 세트(+수호기사 방패) · 세금 ≤ 15%',
                                 table={k: dict(good=v['good_kind'], wearable=v['wearable'], styles=v['styles'], example=v['example'])
                                        for k, v in st['check']['by_class_band'].items()},
                                 sets=st['check']['per_set'], other_builds=st['check']['per_weapon_arch']),
                tests=tests(st))
    return spec


def special_trial(st):
    o = copy.deepcopy(G.OLD['special_trial'])
    blk = o['config']['block']['special_trial']
    blk['chance'] = L.SPECIAL_Q
    blk['pity_visits'] = L.SPECIAL_PITY
    o['config']['effective_rate'] = round(L.SPECIAL_Q_EFF, 3)
    o['config']['chest'] = '무기 1 확정 + 50% 로 1 더 (band_tNN_special) + 방어구 50% (단계 6·9) + 그 층 정수 1 + 골드 (시련방 골드의 0.5~1배)'
    per = {}
    for f, v in o['per_floor'].items():
        f = int(f)
        per[f] = dict(gimmick=v['gimmick'], conditions=v['conditions'], swift_seconds=v['swift_seconds'],
                      table=f'special_trial_f{f:02d}',
                      tiers={t: w for t, w in L.mix_weights(f, lambda x: L.pool_id(x, 'special') in st['changes'], 'special').items()},
                      tier_pool_weapons={t: st['pools']['special'].get(t, []) for t in (f - 1, f, f + 1) if 1 <= t <= 10},
                      tier_pool_armor={t: st['pools']['special_a'].get(t, []) for t in (f - 1, f, f + 1) if 1 <= t <= 10 and st['pools']['special_a'].get(t)})
    o['per_floor'] = per
    o['tables'] = {f: f'special_trial_f{f:02d}' for f in range(1, 11)}
    o['pools'] = {t: L.pool_id(t, 'special') for t in range(1, 11)}
    o['code'] = [
        'dungeon/rooms/SpecialTrial (새, 순수): record SpecialTrial(Condition cond, int seconds, int hits) · enum Condition {SWIFT, UNSCATHED, ABSTAIN, FLAWLESS} · static pick(long seed, int floor, FloorDef def, DungeonConfig.Special cfg, int pity) · boolean kept(Counters c, int party)',
        'dungeon/DungeonConfig · dungeon.yml: special_trial 블록 (record Special(enabled, chance, pityVisits, xpBonus, swift, unscathed, abstain))',
        'content/FloorDef · ContentParser: floors.yml special_trial 덮어쓰기 (conditions, seconds) — 선택',
        'dungeon/FloorState.createRoom (115행 case GIMMICK): GimmickRoom.create 뒤 room.special(SpecialTrial.pick(seed ^ 방 번호, …, pity))',
        'dungeon/rooms/GimmickRoom: 필드 special · broken · hits/consumes/mistakes. onReady 글자판, onEnter 제목·채팅, tick 에서 swift 남은 초·깨짐, succeed() 에서 special 이면 fs.loot("special_trial_f%02d") + 경험치 ×1.5 + 문구 (gimmick_floor_N 은 그대로). protected noteMistake() · public onPlayerHurt(Player, double ratio) · onConsume(Player, ItemDef)',
        'gimmicks/LeverSequence 151행 · ResonanceTune 157행 · BookCipher 183행 · GearTiming 192행: 기회를 잃는(또는 틀린) 자리에 noteMistake() 한 줄',
        '피해 훅: 플레이어가 미궁 피해를 받는 곳(DamageService 몹→플레이어 경로)에서 진행 중 GimmickRoom 안이면 room.onPlayerHurt(p, 피해 ÷ 최대 HP)',
        'items/ConsumableListener.onConsume (103행)·주문서 사용: services.dungeon().onConsume(p, def) → 그 방',
        'data/PlayerData: 층별 special_miss 카운터 (pity, 파티원 중 가장 큰 값) — 특별 시련을 보면 0',
        'dungeon/SelfTest: 층마다 특별 시련 하나 강제 → 조건 4종 판정 · special_trial_fNN 지급 확인',
        'ItemTooltip · CodexMenu: 획득처 "특별 시련" (층 번호 없음)']
    return o


def tests(st):
    return [
        dict(name='WeaponTypeGoneTest (새)', file='plugin/src/test/java/kr/labyrinth/WeaponTypeGoneTest.java', checks=[
            'items.yml 무기에 weapon_type · classes 키가 없다 · 모든 무기에 attack{style: melee|ranged|caster, interval 0.35~1.30, kind: physical|magic}',
            '활 모양(BOWS 7종) ⇔ ranged · 시전 모양 14종 ⇔ caster · caster ⇒ kind magic',
            '툴팁(ItemTooltip.lines)·도감·대장간 목록 어디에도 "대검/한손검/활/지팡이/홀/단검" 이 없다',
            'classes.yml 에 weapon_types 없음 · content/WeaponTypes 사용처 0']),
        dict(name='GearRequirementsDataTest (다시 씀)', file='plugin/src/test/java/kr/labyrinth/GearRequirementsDataTest.java', checks=[
            'items.yml 어디에도 requires_any 가 없다 (파서도 경고)',
            '무기·방어구·방패: L ≤ 2 → 요구 없음, 그 밖 → 능력치 2~3개, 합 = ceil(2.75×(L−1)), 나눔 60/40 또는 50/30/20 (반올림 ±1), 세 개는 L ≥ 12 만',
            '물리 무기는 STR 또는 DEX, 마법 무기는 INT 또는 WIS 가 요구에 하나 이상 (무기와 상관없는 능력치만 요구하는 무기 금지) · 피해 능력치(물리 STR · 마법 INT)를 요구하지 않는 무기는 띠 3~10 에서 띠마다 3개 이하 (1·2 띠는 요구 합 ≤ 25 라 제외)',
            '세트 네 부위는 같은 요구 · 장신구·재료·소모품은 요구 없음 · 시작 지급(novice)은 요구 없음',
            'starterWeaponsFree: classes.yml starter_weapon 6개는 요구 없음 (Lv1)',
            'topWeaponsHaveExactlyOneSourceKind: 영웅 이상 무기는 획득처 종류(boss·craft·drop/chest·trial·special·hoard·elite) 1개 — 종류별 수 {보스 32 · 대장간 36 · 몬스터·상자 21 · 금고·미믹 16 · 특별 시련 15 · 시련방 11 · 정예 10}. 보스 무기는 레시피 없음, 대장간 무기는 드롭 없음',
            'bossUniqueWeaponsDropOftenEnough: 처치 1번당 "그 무기 요구에 맞춘 빌드" 확률(own_build_bias) — 영웅 ≥ 0.30 · 전설 ≥ 0.15 · ≤ 0.5 (지금 직업 편향 판과 같은 숫자)',
            'bandOneEarly: Lv3(포인트 15)에 직업마다 띠 1(1–5) 무기 3개 이상 + wayfarer 한 벌을 함께 낀다',
            'everyClassHasAKitEveryBand: 직업마다 띠마다 (포인트 = 5 × 띠 끝 레벨, 칭호 없음) 그 띠 무기 + 방어구 세트 (+수호기사 방패) 를 세금 ≤ 15% 로 끼는 무기가 3개 이상 (g2_check 와 같은 계산: 세금 = combat_spec 알맞은 분배 밖으로 더 찍는 포인트 ÷ 받은 포인트)',
            'noOrphanWeapon: 모든 무기는 직업 기본 분배 또는 다른 빌드 5종(치명·마검사·전투 사제·민첩 시전·방벽 시전) 중 하나로 자기 레벨+2 에서 세금 ≤ 15%']),
        dict(name='BandDiversityTest (새)', file='plugin/src/test/java/kr/labyrinth/BandDiversityTest.java', checks=[
            '5레벨 띠마다 (신화 제외) 무기 ≥ 14 (지금 데이터 22~25)',
            '근접 ≥ 5 · 원거리 ≥ 3 · 시전 ≥ 3 · 마법 피해 근접·원거리 무기가 띠 3~10 에서 1개 이상 (1·2·9 띠 제외 가능)',
            '요구 능력치 STR·DEX·INT·WIS·VIT·LUK 각각 띠마다 ≥ 2 번 나온다 (1–5 띠는 LUK ≥ 1)',
            '방향 ≥ 10 (directions.json 12개 중) · 획득처 종류 ≥ 5',
            '같은 띠 같은 모양 두 무기는 요구 능력치 순서가 다르다']),
        dict(name='SidegradeBandTest (새)', file='plugin/src/test/java/kr/labyrinth/SidegradeBandTest.java', checks=[
            '비교값 = (한 방 가운데값 ÷ attack.interval) ÷ K(방식, 간격) — K 는 CombatMath (combat_spec)',
            '띠 대장간 기준 = 그 띠 가장 높은 레벨 대장간 무기들의 비교값 가운데값',
            'sources 가 trial·special·hoard·elite 이거나 0.3.5 에 새로 넣은 drop 무기는 기준 ±5% 안',
            '상인 무기는 기준 이하 · 보스 전설은 기준 +5~+30%']),
        dict(name='LootHomesTest (다시 씀)', file='plugin/src/test/java/kr/labyrinth/LootHomesTest.java', checks=[
            'expand() 가 PICK 항목을 따라간다 (하위 표 전부)',
            '집 표: 몹·보물방·미로 상자 → mix_fNN_drop(drop/chest) · gimmick_floor_N → trial · special_trial_fNN → special · hoard_fNN → hoard · 정예 → elite · 보스 → boss',
            'everyGearHasOneOrTwoHomes: 집(종류) 1~2 · items.yml sources 와 같음 · 영웅 이상 무기는 1 종류',
            'gearComesFromItsTierWindowOnly (everyGearHasOneOrTwoHomesOnItsOwnFloor 대신): 보스가 아닌 장비는 tier−1·tier·tier+1 층 표에서만 나온다, 그리고 그 셋 중 최소 둘에서 나온다(1·10 단계는 하나도 됨)',
            'bossGearComesOnlyFromItsBoss: 보스 장비는 그 보스 표에만 (bossOfFloor(tier) — 표시에는 층 없음)',
            'bandPoolsShared: band_tNN_* 표는 둘 이상의 층 표(또는 PICK)가 부른다 (1·10 은 하나도 됨)',
            'gearLevelReqFitsItsTier: level_req ≤ 5×tier · 레시피 level_req = 장비 level_req',
            'perFloorMazeChestTablesHaveNoDirectGear: maze_chest_*_fN 에 장비 one_of 직접 금지 (mix_fNN_drop 으로만)',
            'gear >= 250 → >= 380']),
        dict(name='TooltipFitTest (고침)', file='plugin/src/test/java/kr/labyrinth/items/TooltipFitTest.java', checks=[
            '모든 장비 +0·+8·+10 에서 20줄·330px 이하 (새 무기 106·방어구 24 포함, "공격 속도 초당 N회" 줄 포함)',
            '어느 줄에도 "층" 글자·"지하 N" 이 없다 (머리 줄 "· 지하 N층" 삭제)',
            'sourceLine: 보스 = "획득처: 보스 테오라" (괄호 층 없음) · 정예 = "정예 대시계 집행관" · 몬스터·상자 = "몬스터·상자" · trial "시련방" · special "특별 시련" · hoard "금고·미믹" · shop "상인 핀"',
            '요구 줄에 "또는" 이 없다 ("요구 민첩 24 · 힘 16" 처럼 · 로만 잇는다)',
            '고정 예: clockwork_bastion = "획득처: 보스 테오라 · 대장간", doomclock_executioner = "획득처: 보스 테오라"']),
        dict(name='CodexSourceTextTest (새)', file='plugin/src/test/java/kr/labyrinth/ui/CodexSourceTextTest.java', checks=[
            'CodexMenu.sourceLines(item) 에 숫자+"층" 이 없다 (몬스터 도감·보스 도감의 층 정보는 그대로 — 장비 줄만)',
            '"몬스터·상자" 무기는 한 줄 "몬스터·상자" (지하 N층 무기 묶음 줄 삭제)',
            'SOURCE_GROUPS 에 "시련방" · "특별 시련" · "금고·미믹" 이 있다']),
        dict(name='StatRequirementTest (고침)', file='plugin/src/test/java/kr/labyrinth/items/StatRequirementTest.java', checks=[
            'StatRequirement.of(Map) 하나만 (any 삭제) · met = 모두 · pointsNeeded = 모자란 합',
            'text(): "요구 민첩 24 · 힘 16" (요구치 큰 순) · 색은 능력치마다 충족/미달',
            'ContentParser: requires_any 가 있으면 문제(problem) 로 알리고 무시']),
        dict(name='PickEntryTest (새, 순수)', file='plugin/src/test/java/kr/labyrinth/LootRollerTest.java', checks=[
            'PICK: 무게 7:2:1 → 1만 번에 ±2% · chance 0 이면 안 굴림 · guaranteed 의 PICK 은 늘 하나',
            '하위 표가 없으면 ContentValidator 오류 · 무게 ≤ 0 오류 · 순환 금지',
            'own_build_bias: 요구치 가장 큰 능력치가 줍는 사람 상위 2개 안인 후보만 65% (없으면 전체)']),
        dict(name='DropRateWindowTest (새)', file='plugin/src/test/java/kr/labyrinth/DropRateWindowTest.java', checks=[
            '순수 계산 (LootRoller 규칙 + 1회 상수: 몹 수, 미로 상자 1~3층 8.7·4~10층 12.4, 금고 2.25, 시련 성공 0.8, 특별 0.395(확정 규칙 포함)×0.65)',
            '그 무기 요구에 맞춘 빌드가 자기 단계 층을 돌 때 기대 회차: 몬스터·상자 1~5.5 · 시련방 2.5~7 · 금고·미믹 2.5~9 · 정예 3~7 · 특별 시련 2.5~9 · 각 종류 가운데값은 몬스터·상자 2~4 · 나머지 3.5~7.5',
            '대장간 기준 레시피 = max(재료 회차, 골드 회차) 0.3~2.5 (무기 레시피 골드 ×1.5 뒤)',
            '1회 돌기 장비(무기+방어구) 수가 0.3.4 의 0.8~1.6배 (층마다)']),
        dict(name='SpecialTrialTest (새, 순수)', file='plugin/src/test/java/kr/labyrinth/dungeon/SpecialTrialTest.java', checks=[
            'pick: 같은 시드 → 같은 결과 · 1만 번에 chance ±2% · pity_visits 연속으로 못 보면 다음은 확정',
            '층마다 조건이 그 기믹이 지원하는 것만 (flawless 는 lever_sequence·resonance_tune·book_cipher·gear_timing, swift 는 시간 제한 없는 기믹 또는 제한 시간 × 0.7)',
            'kept: swift(경과 ≤ 초) · unscathed(최대 HP 3% 이상 맞은 횟수 ≤ hits + per_member×(인원−1)) · abstain(물약·주문서 0) · flawless(실수 0)',
            '조건이 깨져도 기믹 성공이면 gimmick_floor_N 은 그대로 지급, special_trial_fNN 만 안 굴린다']),
        dict(name='TierMigrationTest (새)', file='plugin/src/test/java/kr/labyrinth/content/TierMigrationTest.java', checks=[
            'items.yml 장비는 tier 를 갖고 floor 키가 없다 (ContentParser 는 floor 를 tier 로 읽고 경고 — 옮기는 동안)',
            'ItemDef.tier() 1~10 · level_req ∈ [5×tier − 5, 5×tier] (Lv1 장비는 tier 1)']),
        dict(name='validate.py / hold_preview (리소스팩)', file='resourcepack/src/validate.py · resourcepack/tools/hold_preview.py', checks=[
            '새 모양 15개가 voxel/weapons._TEMPLATES 또는 BOWS 에 있고 HOLD·TWO_HANDED·HEAD_SHAPES 가 new_shapes 명세와 같다',
            'hold_preview metrics: 1인칭 화면 덮는 비율이 같은 무게 기존 모양 ±25% 안, 손잡이 (8,1,8) / 활 (4.5,6,8) 고정',
            '새 방어구 6세트가 equipment.paint_set(look) · voxel/armor 투구 · armor_pieces(look·back) 에 모두 잡힌다']),
    ]


if __name__ == '__main__':
    main()
