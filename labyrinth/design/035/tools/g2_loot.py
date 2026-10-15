# -*- coding: utf-8 -*-
"""획득처 다시 짜기 — 층 이름표 없음, '단계 풀'(tier pool)을 이웃 층이 나눠 쓴다.

단계(tier) N = 그 장비를 만든 레벨 구간 = N층 레벨 구간 Lv 5N−5~5N (items.yml floor → tier 로 이름만 바꿈).
장비의 레벨 창 = 단계 구간 앞뒤 5레벨 = Lv 5N−10 ~ 5N+5 → 레벨 구간이 겹치는 층 N−1 · N · N+1 이 그 장비를 준다.
층 f 의 몫: 단계 f−1 : f : f+1 = 2 : 7 : 1 (없는 단계는 빼고 다시 나눔).

새 루팅 항목 종류 PICK: {pick: [{table: id, weight: n}, ...], chance}  — chance 를 통과하면 무게대로 하위 표 하나를 골라 굴린다.
"""
import collections
import copy
import math
import statistics

import g2_core as G

BIAS = G.LOOT_SETTINGS.get('own_class_bias', 0.65)     # → own_build_bias (요구 능력치 편향)
TIER_W = {-1: 2, 0: 7, 1: 1}
TIER_W_SPECIAL = {-1: 1, 0: 8, 1: 1}     # 특별 시련은 자기 단계 쪽으로 더 (드문 보상이라)

# ── 1회 돌기 (보통 · 솔로 · LUK 0 · 층 끝까지) — 옛 판 gs_loot 와 같은 가정 ──
MOBS_RUN = {1: 24, 2: 28, 3: 28, 4: 36, 5: 40, 6: 45, 7: 45, 8: 55, 9: 55, 10: 60}
TREASURE_CHESTS = 2.7          # 보물방 하나에 3상자, 30% 로 하나가 미믹
ELITES = {f: (2 if f >= 9 else 1) for f in range(1, 11)}
GIMMICK_OK = 0.8               # 시련방 성공률
MIMIC = {1: 0.04, 2: 0.055, 3: 0.07, 4: 0.085, 5: 0.10, 6: 0.115, 7: 0.13, 8: 0.145, 9: 0.16, 10: 0.175}
SPECIAL_Q = 0.30               # 특별 시련이 나올 확률 (층 방문마다)
SPECIAL_PITY = 3               # 이만큼 연속으로 못 보면 다음 방문은 확정
SPECIAL_Q_EFF = SPECIAL_Q / (1 - (1 - SPECIAL_Q) ** (SPECIAL_PITY + 1))   # 확정 규칙을 넣은 실제 비율 0.395
SPECIAL_C = 0.65               # 조건까지 지킬 확률 (솔로 보통 추정)
SPECIAL_EXTRA = 0.5            # 특별 상자의 두 번째 무기 확률


def treasure_rooms(f):
    return FLOOR_ROOMS[f].get('treasure', 1)


FLOOR_ROOMS = {int(k): v['rooms'] for k, v in G.FLOORS.items()}


def maze(f):
    c = dict(wood=3.3, iron=1.3, gold=0.6, secret=1.0) if f <= 3 else dict(wood=4.4, iron=2.3, gold=1.2, secret=2.0)
    c['vault'] = 2.5 * 0.9          # 금고 금 상자 2~3개 × 열쇠를 찾을 확률
    c['mimic'] = (c['wood'] + c['iron']) * MIMIC[f]
    return c


# 몬스터·상자 기본 확률 (지금 값) × 층 배율 M_FACTOR (목표 회차에 맞게 풀어 냄)
M_BASE_MOB = {1: 0.03, 2: 0.025, 3: 0.025, 4: 0.02, 5: 0.02, 6: 0.016, 7: 0.016, 8: 0.013, 9: 0.013, 10: 0.012}
M_BASE = dict(treasure=0.07, wood=0.03, iron=0.06, gold=0.10)
TARGET = dict(M={1: 2.0, 2: 3.0, 3: 3.0, 4: 3.0, 5: 3.5, 6: 3.5, 7: 3.0, 8: 3.5, 9: 3.5, 10: 3.5},
              T=5.0, V=5.0, E=5.0)


# ───────────── 장비 → 획득처 종류 · 단계 ─────────────
def weapon_kinds(w):
    if w['new']:
        return [w['old_kind']]
    s = G.ITEMS[w['id']].get('sources') or []
    ks = []
    for x in s:
        k = G.SRC_SK[x]
        if k not in ks:
            ks.append(k)
    return ks


def item_kinds(iid, A):
    if iid in A and A[iid]['new']:
        s = A[iid]['sources']
    else:
        s = G.ITEMS[iid].get('sources') or []
    ks = []
    for x in s:
        k = G.SRC_SK[x]
        if k not in ks:
            ks.append(k)
    return ks


def tier_of_weapon(w):
    return w['floor_old']


def tier_of_item(iid, A):
    if iid in A and A[iid]['new']:
        return A[iid]['floor_old']
    return G.ITEMS[iid].get('floor')


def pool_id(t, kind):
    return f'band_t{t:02d}_{kind}'


def mix_weights(f, have, kind=None):
    """층 f 가 굴리는 단계별 무게 {tier: w} (have(tier) 가 참인 단계만)."""
    out = {}
    for d, w in (TIER_W_SPECIAL if kind == 'special' else TIER_W).items():
        t = f + d
        if 1 <= t <= 10 and have(t):
            out[t] = w
    return out


def pick_entry(f, kind, have, chance=None):
    ws = mix_weights(f, have, kind)
    e = {'pick': [{'table': pool_id(t, kind), 'weight': w} for t, w in sorted(ws.items())]}
    if chance is not None:
        e['chance'] = chance
    return e


# ───────────── 루팅 표 기대값 (재료·골드) — 옛 gs_loot 와 같은 방식 ─────────────
SKIP = ('potions_', 'scrolls', 'tonics', 'rare_consumables', 'enhance_', 'maze_enhance_')


def table_yield(tid, tables, depth=0):
    out = collections.Counter()
    t = tables.get(tid)
    if not t or depth > 6:
        return out
    rolls = max(1, t.get('rolls', 1))

    def amt(e):
        a = e.get('amount', 1)
        return G.mid(a) if isinstance(a, list) else a

    def add(e, mult):
        if 'item' in e:
            out[e['item']] += mult * amt(e)
        elif 'one_of' in e:
            for x in e['one_of']:
                out[x] += mult * amt(e) / len(e['one_of'])
        elif 'table' in e and not any(e['table'].startswith(s) for s in SKIP):
            for k, v in table_yield(e['table'], tables, depth + 1).items():
                out[k] += mult * v
        elif 'pick' in e:
            tot = sum(p['weight'] for p in e['pick'])
            for p in e['pick']:
                for k, v in table_yield(p['table'], tables, depth + 1).items():
                    out[k] += mult * v * p['weight'] / tot
    for e in t.get('guaranteed') or []:
        add(e, 1.0)
    for e in t.get('entries') or []:
        if e.get('min_difficulty') in ('hard', 'nightmare'):
            continue
        add(e, rolls * min(1.0, e.get('chance', 1.0)))
    return out


def floor_tables(f):
    normal = [m['drops'] for m in G.MOBS.values() if m.get('floor') == f and m.get('rank') != 'elite' and m.get('drops')
              and m.get('rank') != 'boss']
    elite = [m['drops'] for m in G.MOBS.values() if m.get('floor') == f and m.get('rank') == 'elite' and m.get('drops')]
    return normal, elite, G.BOSS_TABLE[f]


def run_sources(f):
    normal, elite, boss = floor_tables(f)
    c = maze(f)
    out = [(t, MOBS_RUN[f] / len(normal)) for t in normal]
    out += [(e, ELITES[f] / len(elite)) for e in elite]
    out += [(boss, 1.0), (f'treasure_floor_{f}', treasure_rooms(f) * TREASURE_CHESTS), (f'gimmick_floor_{f}', GIMMICK_OK),
            (f'maze_chest_wood_f{f}', c['wood']), (f'maze_chest_iron_f{f}', c['iron']),
            (f'maze_chest_gold_f{f}', c['gold'] + c['secret'] + c['vault'])]
    return out


def run_yield(f, tables):
    tot = collections.Counter()
    for t, n in run_sources(f):
        for k, v in table_yield(t, tables).items():
            tot[k] += n * v
    return tot


def run_gold(f):
    normal, elite, boss = floor_tables(f)
    mobs = [m for m in G.MOBS.values() if m.get('floor') == f and m.get('rank') == 'normal']
    g = MOBS_RUN[f] * sum(G.mid(m['gold']) for m in mobs) / len(mobs)
    els = [m for m in G.MOBS.values() if m.get('floor') == f and m.get('rank') == 'elite']
    g += ELITES[f] * sum(G.mid(m['gold']) for m in els) / len(els)
    g += G.mid([b for b in G.BOSSES.values() if b.get('floor') == f][0]['gold'])
    for t, n in run_sources(f):
        tt = G.LOOT.get(t) or {}
        if tt.get('gold') and not t.startswith('floor'):
            g += n * G.mid(tt['gold'])
    return g


# ───────────── 표 만들기 ─────────────
def build(W, WR, A, AR):
    """반환: (새 표 전체 dict, 바뀐 표 {id: {op, note, table}}, 풀 내용 {kind: {tier: [ids]}})."""
    T = copy.deepcopy(G.LOOT)
    changes = {}
    pools = {k: collections.defaultdict(list) for k in ('drop', 'trial', 'special', 'hoard', 'elite_w', 'elite_a', 'elite_s', 'elite_c',
                                                       'trial_a', 'special_a', 'hoard_a')}
    for wid, w in W.items():
        ks = weapon_kinds(w)
        t = tier_of_weapon(w)
        for k in ks:
            if k == 'M':
                pools['drop'][t].append(wid)
            elif k == 'T':
                pools['trial'][t].append(wid)
            elif k == 'S':
                pools['special'][t].append(wid)
            elif k == 'V':
                pools['hoard'][t].append(wid)
            elif k == 'E':
                pools['elite_w'][t].append(wid)
    for aid in list(A) + [k for k, v in G.ITEMS.items() if v.get('type') == 'accessory']:
        ks = item_kinds(aid, A)
        t = tier_of_item(aid, A)
        typ = 'accessory' if aid not in A else ('shield' if A[aid]['slot'] == 'offhand' else 'armor')
        for k in ks:
            if k == 'E':
                pools['elite_a' if typ == 'armor' else 'elite_s' if typ == 'shield' else 'elite_c'][t].append(aid)
            elif k == 'T':
                pools['trial_a'][t].append(aid)
            elif k == 'S':
                pools['special_a'][t].append(aid)
            elif k == 'V':
                pools['hoard_a'][t].append(aid)
    # 기존 정예 표에서 장비 항목 확률을 단계 풀로 옮긴다
    elite_ch = {}
    for f in range(1, 11):
        _, elites, _ = floor_tables(f)
        ch = dict(a=None, s=None, c=None)
        for e in G.LOOT[elites[0]]['entries']:
            ids = e.get('one_of') or ([e['item']] if 'item' in e else [])
            if not ids:
                continue
            d = G.ITEMS.get(ids[0], {})
            if d.get('type') == 'armor' and d.get('armor_slot') != 'offhand':
                ch['a'] = e['chance']
            elif d.get('armor_slot') == 'offhand':
                ch['s'] = e['chance']
            elif d.get('type') == 'accessory':
                ch['c'] = e['chance']
        elite_ch[f] = ch
    new_tables = {}
    for t in range(1, 11):
        if pools['drop'][t]:
            new_tables[pool_id(t, 'drop')] = {'rolls': 1, 'entries': [{'one_of': pools['drop'][t], 'chance': 1.0}]}
        if pools['trial'][t] or pools['trial_a'][t]:
            es = []
            if pools['trial'][t]:
                es.append({'one_of': pools['trial'][t], 'chance': 1.0 if not pools['trial_a'][t] else 0.6})
            if pools['trial_a'][t]:
                es.append({'one_of': pools['trial_a'][t], 'chance': 0.5})
            new_tables[pool_id(t, 'trial')] = {'rolls': 1, 'entries': es}
        if pools['special'][t]:
            # 무기 하나 확정 + 50% 로 하나 더 (특별 시련은 드물어서 — 같은 것이 두 번 나올 수 있음)
            st = {'rolls': 1, 'guaranteed': [{'one_of': pools['special'][t]}],
                  'entries': [{'one_of': pools['special'][t], 'chance': SPECIAL_EXTRA}]}
            if pools['special_a'][t]:
                st['entries'].append({'one_of': pools['special_a'][t], 'chance': 0.5})
            new_tables[pool_id(t, 'special')] = st
        if pools['hoard'][t] or pools['hoard_a'][t]:
            es = []
            if pools['hoard'][t]:
                es.append({'one_of': pools['hoard'][t], 'chance': 0.6 if pools['hoard_a'][t] else 1.0})
            if pools['hoard_a'][t]:
                es.append({'one_of': pools['hoard_a'][t], 'chance': 0.4 if pools['hoard'][t] else 1.0})
            new_tables[pool_id(t, 'hoard')] = {'rolls': 1, 'entries': es}
        es = []
        ch = elite_ch[t]
        if pools['elite_a'][t]:
            es.append({'one_of': pools['elite_a'][t], 'chance': ch['a'] or 0.6})
        if pools['elite_s'][t]:
            ids = pools['elite_s'][t]
            es.append({'item': ids[0], 'chance': ch['s'] or 0.15} if len(ids) == 1 else {'one_of': ids, 'chance': ch['s'] or 0.15})
        if pools['elite_c'][t]:
            ids = pools['elite_c'][t]
            es.append({'item': ids[0], 'chance': ch['c'] or 0.2} if len(ids) == 1 else {'one_of': ids, 'chance': ch['c'] or 0.2})
        if pools['elite_w'][t]:
            es.append({'one_of': pools['elite_w'][t], 'chance': None})     # 아래에서 풀어 냄
        if es:
            new_tables[pool_id(t, 'elite')] = {'rolls': 1, 'entries': es}
    for k, v in new_tables.items():
        T[k] = v
    has = lambda kind: (lambda t: pool_id(t, kind) in new_tables)
    # 층마다
    for f in range(1, 11):
        normal, elites, boss = floor_tables(f)
        # M: mix_fNN_drop + 몹·보물방·미로 상자 항목
        mid_ = f'mix_f{f:02d}_drop'
        T[mid_] = {'rolls': 1, 'entries': [pick_entry(f, 'drop', has('drop'), 1.0)]}
        new_tables[mid_] = T[mid_]
        # T: gimmick_floor_N
        # V: hoard_fNN · S: special_trial_fNN
        # E: 정예 표
    return T, new_tables, pools, elite_ch


def apply_rates(T, new_tables, factors):
    """factors = dict(M={f: fac}, T={f: chance}, V={f: chance}, E={t: chance}) → 표에 써 넣고 바뀐 표 목록을 돌려준다."""
    changes = {}
    has = lambda kind: (lambda t: f'band_t{t:02d}_{kind}' in new_tables)
    for t in range(1, 11):
        pid = pool_id(t, 'elite')
        if pid in T:
            for e in T[pid]['entries']:
                first = (e.get('one_of') or [e.get('item')])[0]
                if first in factors['_weapons']:
                    e['chance'] = round(factors['E'][t], 3)
    for f in range(1, 11):
        normal, elites, boss = floor_tables(f)
        fac = factors['M'][f]
        mid_ = f'mix_f{f:02d}_drop'
        old_id = f'gear_f{f:02d}_common'
        for tid in normal + [f'treasure_floor_{f}', f'maze_chest_wood_f{f}', f'maze_chest_iron_f{f}', f'maze_chest_gold_f{f}']:
            tt = copy.deepcopy(T[tid])
            es = [e for e in tt.get('entries', []) if e.get('table') != old_id]
            old = [e for e in tt.get('entries', []) if e.get('table') == old_id]
            if tid in normal:
                oldc = old[0]['chance'] if old else None
                swarm = 0.7 if (oldc and abs(oldc / M_BASE_MOB[f] - 0.7) < 0.01) else 1.0
                ch = M_BASE_MOB[f] * swarm * fac
            else:
                ch = M_BASE['treasure' if tid.startswith('treasure') else tid.split('_')[2]] * fac
            ne = {'table': mid_, 'chance': round(ch, 4 if ch >= 0.001 else 5)}
            idx = next((i for i, e in enumerate(es) if str(e.get('table', '')).startswith('enhance_')), len(es))
            es.insert(idx, ne)
            tt['entries'] = es
            T[tid] = tt
            changes[tid] = dict(op='replace_entries', note=f"{old_id} {old[0]['chance'] if old else '없음'} → {mid_} {ne['chance']}", table=tt)
        if old_id in T:
            del T[old_id]
            changes[old_id] = dict(op='delete', note=f'{mid_} + 단계 풀(band_tNN_drop)로 바뀜', table=None)
        # 시련방
        g = copy.deepcopy(T[f'gimmick_floor_{f}'])
        es = [e for e in g.get('entries', []) if e.get('table') != old_id]
        if mix_weights(f, has('trial')):
            es.append(pick_entry(f, 'trial', has('trial'), round(factors['T'][f], 3)))
        g['entries'] = es
        T[f'gimmick_floor_{f}'] = g
        changes[f'gimmick_floor_{f}'] = dict(op='replace_entries', note='몬스터·상자 무기를 빼고 시련 단계 풀(PICK)', table=g)
        # 금고·미믹
        hid = f'hoard_f{f:02d}'
        T[hid] = {'rolls': 1, 'entries': [pick_entry(f, 'hoard', has('hoard'), round(factors['V'][f], 3))]}
        changes[hid] = dict(op='new', note=f'{f}층 금고 금 상자·길들인 미믹 상자를 열 때 한 번 더 (코드: Treasures.open)', table=T[hid])
        # 특별 시련
        gold0 = G.LOOT[f'gimmick_floor_{f}']['gold']
        ess = {1: 'dim_essence', 2: 'dim_essence', 3: 'dim_essence', 4: 'labyrinth_essence', 5: 'labyrinth_essence',
               6: 'labyrinth_essence', 7: 'radiant_essence', 8: 'radiant_essence', 9: 'primordial_essence', 10: 'primordial_essence'}[f]
        sid = f'special_trial_f{f:02d}'
        T[sid] = {'rolls': 1, 'gold': [int(G.mid(gold0) * 0.5), int(G.mid(gold0))],
                  'guaranteed': [pick_entry(f, 'special', has('special')), {'item': ess, 'amount': 1}], 'entries': []}
        changes[sid] = dict(op='new', note=f'{f}층 특별 시련 성공 상자 (시련방 상자에 더해서, 개인 루팅)', table=T[sid])
        # 정예
        for el in elites:
            et = copy.deepcopy(T[el])
            es = []
            for e in et['entries']:
                ids = e.get('one_of') or ([e['item']] if 'item' in e else [])
                d = G.ITEMS.get(ids[0], {}) if ids else {}
                if d.get('type') in ('armor', 'accessory', 'weapon'):
                    continue
                es.append(e)
            idx = next((i for i, e in enumerate(es) if str(e.get('table', '')).startswith('potions_')), len(es))
            es.insert(idx, pick_entry(f, 'elite', has('elite'), 1.0))
            et['entries'] = es
            T[el] = et
            changes[el] = dict(op='replace_entries', note='층 장비 항목(방어구·방패·장신구) → 정예 단계 풀(PICK, 무기 포함)', table=et)
    for k, v in new_tables.items():
        changes[k] = dict(op='new', note=('단계 풀' if k.startswith('band_') else '층 섞음 표'), table=T[k])
    return T, changes


# ───────────── 기대 회차 ─────────────
def primary_of(req):
    if not req:
        return None
    return max(req.items(), key=lambda kv: (kv[1], kv[0]))[0]


def pick_p(target, pool, REQ):
    """one_of 에서 target 이 나올 확률. 줍는 사람 능력치 상위 2개 = target 요구의 1·2위 (그 무기를 노리는 빌드). 편향 BIAS."""
    n = len(pool)
    r = REQ.get(target) or {}
    top2 = [s for s, _ in sorted(r.items(), key=lambda kv: -kv[1])[:2]]
    if not top2:
        return 1.0 / n
    nfit = sum(1 for x in pool if primary_of(REQ.get(x) or {}) in top2)
    if nfit == 0:
        return 1.0 / n
    return BIAS / nfit + (1 - BIAS) / n


def rolls_into(tid, f, T):
    """1회 돌기에서 표 tid 를 곧바로 굴리는 기대 횟수."""
    tot = 0.0
    for t, n in run_sources(f):
        tt = T.get(t) or {}
        r = max(1, tt.get('rolls', 1))
        for e in tt.get('entries') or []:
            if e.get('table') == tid:
                tot += n * r * min(1.0, e['chance'])
    return tot


def weapon_rate(wid, f, W, T, REQ, kind):
    """층 f 1회에 무기 wid 를 얻을 확률 (그 무기 요구에 맞춘 빌드, 기하분포 근사)."""
    w = W.get(wid)
    t = tier_of_weapon(w)
    if kind == 'M':
        pid = pool_id(t, 'drop')
        if pid not in T:
            return 0.0
        R = rolls_into(f'mix_f{f:02d}_drop', f, T)
        ws = mix_weights(f, lambda x: pool_id(x, 'drop') in T)
        if t not in ws:
            return 0.0
        pool = T[pid]['entries'][0]['one_of']
        return R * ws[t] / sum(ws.values()) * pick_p(wid, pool, REQ)
    if kind in ('T', 'V', 'S', 'E'):
        k = dict(T='trial', V='hoard', S='special', E='elite')[kind]
        pid = pool_id(t, k)
        if pid not in T:
            return 0.0
        ws = mix_weights(f, lambda x: pool_id(x, k) in T, k)
        if t not in ws:
            return 0.0
        frac = ws[t] / sum(ws.values())
        if kind == 'T':
            g = T[f'gimmick_floor_{f}']
            e = next(e for e in g['entries'] if 'pick' in e)
            R = GIMMICK_OK * max(1, g.get('rolls', 1)) * e['chance']
        elif kind == 'V':
            c = maze(f)
            R = (c['vault'] + c['mimic']) * T[f'hoard_f{f:02d}']['entries'][0]['chance']
        elif kind == 'S':
            R = SPECIAL_Q_EFF * SPECIAL_C
        else:
            R = ELITES[f]
        p = 0.0
        pt = T[pid]
        for e in (pt.get('entries') or []):
            if wid in (e.get('one_of') or []):
                p += min(1.0, e['chance']) * pick_p(wid, e['one_of'], REQ)
        for e in (pt.get('guaranteed') or []):
            if wid in (e.get('one_of') or []):
                p += pick_p(wid, e['one_of'], REQ)
        return R * frac * p
    return 0.0


def runs(p):
    return None if p <= 0 else 1.0 / min(0.999, p)


def boss_rate(wid, W, REQ):
    f = tier_of_weapon(W[wid])
    tt = G.LOOT[G.BOSS_TABLE[f]]
    p = 0.0
    for e in tt.get('entries') or []:
        if e.get('min_difficulty'):
            continue
        ids = e.get('one_of') or ([e['item']] if 'item' in e else [])
        if wid in ids:
            p += min(1, e['chance']) * (pick_p(wid, ids, REQ) if len(ids) > 1 else 1.0)
    for e in tt.get('guaranteed') or []:
        ids = e.get('one_of') or []
        if wid in ids:
            p += pick_p(wid, ids, REQ)
    return p


def forge_cost(f, recipe, T):
    y = run_yield(f, T)
    g = run_gold(f)
    worst = 0.0
    detail = {}
    for m, n in recipe['materials'].items():
        per = y.get(m, 0)
        r = n / per if per > 0 else float('inf')
        detail[m] = (n, round(per, 2), round(r, 2))
        worst = max(worst, r)
    return worst, recipe.get('gold', 0) / g, detail, g


# ───────────── 확률 풀어 내기 (목표 회차) ─────────────
def solve(W, WR, A, AR, verbose=False):
    T0, new_tables, pools, elite_ch = build(W, WR, A, AR)
    REQ = {wid: r['requires'] for wid, r in WR.items()}
    REQ.update({aid: r['requires'] for aid, r in AR.items()})
    fac = dict(M={f: 1.0 for f in range(1, 11)}, T={f: 0.15 for f in range(1, 11)}, V={f: 0.08 for f in range(1, 11)},
               E={t: 0.25 for t in range(1, 11)}, _weapons=set(W))

    def med(xs):
        return statistics.median(xs) if xs else None

    for it in range(8):
        T, ch = apply_rates(copy.deepcopy(T0), new_tables, fac)
        for f in range(1, 11):
            # M: 그 층 단계 무기 가운데값이 목표
            ids = pools['drop'][f]
            if ids:
                rs = [runs(weapon_rate(w, f, W, T, REQ, 'M')) for w in ids if W[w]['L'] > 1]
                r = med([x for x in rs if x]) if rs else None
                if r:
                    fac['M'][f] *= r / TARGET['M'][f]
            for k, key in (('T', 'trial'), ('V', 'hoard')):
                ids = pools[key][f]
                if not ids:
                    continue
                rs = [runs(weapon_rate(w, f, W, T, REQ, k)) for w in ids]
                r = med([x for x in rs if x])
                if r:
                    fac[k][f] = min(1.0, fac[k][f] * r / TARGET[k])
            ids = pools['elite_w'][f]
            if ids:
                rs = [runs(weapon_rate(w, f, W, T, REQ, 'E')) for w in ids]
                r = med([x for x in rs if x])
                if r:
                    fac['E'][f] = min(0.45, fac['E'][f] * r / TARGET['E'])
    T, ch = apply_rates(copy.deepcopy(T0), new_tables, fac)
    return T, ch, pools, fac, REQ


if __name__ == '__main__':
    import g2_req as Q
    import g2_assign as S
    W = G.weapons_all()
    A = G.armor_all()
    AR = Q.armor_requires(A)
    WR = S.assign(W, A, AR)
    T, ch, pools, fac, REQ = solve(W, WR, A, AR)
    print({k: {f: round(v, 3) for f, v in d.items()} for k, d in fac.items() if k != '_weapons'})
    for f in range(1, 11):
        print(f, 'M', [round(runs(weapon_rate(w, f, W, T, REQ, 'M')) or 0, 1) for w in pools['drop'][f]])
