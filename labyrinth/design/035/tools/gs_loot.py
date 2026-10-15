# -*- coding: utf-8 -*-
"""TASK C 루팅 — 새 테이블 · 바뀐 테이블 · 1회 기대값(재료·골드·굴림) · 획득처별 기대 회차."""
import copy, collections, math
from gs_core import (ITEMS, LOOT, RECIPES, MOBS, BOSSES, ELITE, KIND_KO, RAR, mid)

# ── 1회 돌기(보통·솔로·LUK 0) 상수 ──
MOBS_RUN = {1: 24, 2: 28, 3: 28, 4: 36, 5: 40, 6: 45, 7: 45, 8: 55, 9: 55, 10: 60}       # GDD §16.1
TREASURE_ROOMS = {f: (2 if f >= 7 else 1) for f in range(1, 11)}
TREASURE_CHESTS = 2.7          # 방마다 3상자, 30% 로 하나가 미믹(사라짐)
ELITES = {f: (2 if f >= 9 else 1) for f in range(1, 11)}
GIMMICK_OK = 0.8               # 시련방 성공률 (실패가 쌓이면 힌트가 또렷해진다)
MIMIC = {1: 0.04, 2: 0.055, 3: 0.07, 4: 0.085, 5: 0.10, 6: 0.115, 7: 0.13, 8: 0.145, 9: 0.16, 10: 0.175}
# 미로 상자 (0.3.4 자가 진단 10층: chests=113 vaults=10 secret_rooms=17 mimics=14 → 1~3층 8.7개, 4~10층 12.4개/층)
def maze(f):
    if f <= 3:
        c = dict(wood=3.3, iron=1.3, gold=0.6, secret=1.0)
    else:
        c = dict(wood=4.4, iron=2.3, gold=1.2, secret=2.0)
    c['vault'] = 2.5 * 0.9      # 금고 금 상자 2~3개 × 열쇠를 찾을 확률
    c['mimic'] = (c['wood'] + c['iron']) * MIMIC[f]
    return c
SPECIAL_Q = 0.30               # 특별 시련이 나올 확률 (층 방문마다)
SPECIAL_C = 0.65               # 특별 조건까지 지켜 성공할 확률 (솔로 보통 추정)
BIAS = 0.65                    # 장비 고르기 편향 (loot.yml own_class_bias → 능력치 편향으로)

# ── 테이블 기대값 ──
def table_yield(tid, tables, depth=0, skip=('potions_', 'scrolls', 'tonics', 'rare_consumables', 'enhance_', 'maze_enhance_')):
    out = collections.Counter()
    t = tables.get(tid)
    if not t or depth > 6:
        return out
    rolls = max(1, t.get('rolls', 1))
    def amt(e):
        a = e.get('amount', 1)
        return mid(a) if isinstance(a, list) else a
    def add(e, mult):
        if 'item' in e:
            out[e['item']] += mult * amt(e)
        elif 'one_of' in e:
            for x in e['one_of']:
                out[x] += mult * amt(e) / len(e['one_of'])
        elif 'table' in e and not any(e['table'].startswith(s) for s in skip):
            for k, v in table_yield(e['table'], tables, depth + 1).items():
                out[k] += mult * v
    for e in t.get('guaranteed') or []:
        add(e, 1.0)
    for e in t.get('entries') or []:
        if e.get('min_difficulty') in ('hard', 'nightmare'):
            continue
        add(e, rolls * min(1.0, e.get('chance', 1.0)))
    return out


def floor_tables(f):
    normal = [m['drops'] for k, m in MOBS.items() if m.get('floor') == f and m.get('rank') == 'normal' and m.get('drops')]
    elite = [m['drops'] for k, m in MOBS.items() if m.get('floor') == f and m.get('rank') == 'elite' and m.get('drops')]
    boss = [b['drops'] for b in BOSSES.values() if b.get('floor') == f][0]
    return normal, elite[0], boss


def run_sources(f):
    """(테이블, 1회 굴림 수) 목록 — 1회 돌기에서 각 테이블을 몇 번 굴리나."""
    normal, elite, boss = floor_tables(f)
    c = maze(f)
    out = [(t, MOBS_RUN[f] / len(normal)) for t in normal]
    out += [(elite, ELITES[f]), (boss, 1.0), (f'treasure_floor_{f}', TREASURE_ROOMS[f] * TREASURE_CHESTS),
            (f'gimmick_floor_{f}', GIMMICK_OK), (f'maze_chest_wood_f{f}', c['wood']), (f'maze_chest_iron_f{f}', c['iron']),
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
    g = 0.0
    mobs = [m for m in MOBS.values() if m.get('floor') == f and m.get('rank') == 'normal']
    g += MOBS_RUN[f] * sum(mid(m['gold']) for m in mobs) / len(mobs)
    el = [m for m in MOBS.values() if m.get('floor') == f and m.get('rank') == 'elite'][0]
    g += ELITES[f] * mid(el['gold'])
    g += mid([b for b in BOSSES.values() if b.get('floor') == f][0]['gold'])
    for t, n in run_sources(f)[len(normal) + 2:]:
        tt = LOOT.get(t) or {}
        if tt.get('gold'):
            g += n * mid(tt['gold'])
    return g


# ── 새 테이블 이름 ──
def tid_trial(f): return f'trial_gear_f{f:02d}'
def tid_special(f): return f'special_trial_f{f:02d}'
def tid_hoard(f): return f'hoard_gear_f{f:02d}'
def tid_common(f): return f'gear_f{f:02d}_common'


# 획득처별 확률 (항목 chance). M(몬스터·상자) = 기준 × 층 배율 — 배율은 내 능력치 무기 하나 기대 회차가 목표가 되게 (gs_build 가 맞춤)
M_BASE_MOB = {1: 0.03, 2: 0.025, 3: 0.025, 4: 0.02, 5: 0.02, 6: 0.016, 7: 0.016, 8: 0.013, 9: 0.013, 10: 0.012}
M_BASE = dict(treasure=0.07, wood=0.03, iron=0.06, gold=0.10)
M_TARGET = {1: 2.0, 2: 2.5, 3: 2.5, 4: 3.0, 5: 4.5, 6: 4.5, 7: 3.0, 8: 4.5, 9: 4.5, 10: 4.5}
T_RATE = 0.15                  # 시련방 성공 상자(2번 굴림) → trial_gear_fNN
E_RATE = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25, 5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25, 9: 0.13, 10: 0.13}
def H_RATE(f):                 # 금고 금 상자·길들인 미믹 상자 1개당 hoard_gear_fNN 무기 항목
    c = maze(f)
    return round(1.0 / (5.0 * (c['vault'] + c['mimic']) * 0.8), 3)


def is_epic_floor(f):
    return f in (5, 6, 8, 9, 10)


def build_tables(new, armor_items, mfactor=None):
    mfactor = mfactor or {}
    """새·바뀐 테이블 (전체 entries 를 다시 적는다)."""
    T = copy.deepcopy(LOOT)
    changes = {}
    byk = collections.defaultdict(lambda: collections.defaultdict(list))
    for w in new.values():
        byk[w['F']][w['kind']].append(w['id'])
    arm = collections.defaultdict(lambda: collections.defaultdict(list))
    for a in armor_items.values():
        arm[a['floor']][a['_kind']].append(a['_id'])
    for f in range(1, 11):
        normal, elite, boss = floor_tables(f)
        # M: gear_fNN_common
        cid = tid_common(f)
        old_list = (LOOT.get(cid) or {}).get('entries', [{}])[0].get('one_of', [])
        mlist = old_list + byk[f]['M']
        if mlist:
            T[cid] = {'rolls': 1, 'entries': [{'one_of': mlist, 'chance': 1.0}]}
            if byk[f]['M'] or cid not in LOOT:
                changes[cid] = dict(op='new' if cid not in LOOT else 'replace', note=f'{f}층 몬스터·상자 무기 {len(mlist)}개', table=T[cid])
            fac = mfactor.get(f, 1.0)
            # 몹·보물방·미로 상자: gear 항목을 넣거나 확률을 바꾼다
            for t in normal + [f'treasure_floor_{f}', f'maze_chest_wood_f{f}', f'maze_chest_iron_f{f}', f'maze_chest_gold_f{f}']:
                tt = T[t]
                es = [e for e in tt.get('entries', []) if e.get('table') != cid]
                old = [e for e in tt.get('entries', []) if e.get('table') == cid]
                if t in normal:
                    oldc = old[0]['chance'] if old else None
                    swarm = 0.7 if (oldc and abs(oldc / M_BASE_MOB[f] - 0.7) < 0.01) else 1.0
                    ch = M_BASE_MOB[f] * swarm * fac
                else:
                    ch = M_BASE['treasure' if t.startswith('treasure') else t.split('_')[2]] * fac
                new_e = {'table': cid, 'chance': round(ch, 4 if ch >= 0.001 else 5)}
                # 강화 재료 항목 앞에 끼운다
                idx = next((i for i, e in enumerate(es) if str(e.get('table', '')).startswith('enhance_')), len(es))
                es.insert(idx, new_e)
                if not old or abs(old[0]['chance'] - new_e['chance']) > 1e-9:
                    tt = dict(tt)
                    tt['entries'] = es
                    T[t] = tt
                    changes[t] = dict(op='replace_entries', note=f'gear_f{f:02d}_common {old[0]["chance"] if old else "없음"} → {new_e["chance"]}', table=tt)
        # T: gimmick_floor_N → trial_gear_fNN (몬스터·상자 무기를 빼고 시련 전용 표를 굴린다)
        g = dict(T[f'gimmick_floor_{f}'])
        es = [e for e in g.get('entries', []) if e.get('table') != cid]
        tw, ta = byk[f]['T'], arm[f]['T']
        if tw or ta:
            es.append({'table': tid_trial(f), 'chance': 0.25 if ta else T_RATE})
            ent = []
            if tw:
                ent.append({'one_of': tw, 'chance': 0.6 if ta else 1.0})
            if ta:
                ent.append({'one_of': ta, 'chance': 0.5})
            T[tid_trial(f)] = {'rolls': 1, 'entries': ent}
            changes[tid_trial(f)] = dict(op='new', note=f'{f}층 시련방 성공 상자 전용', table=T[tid_trial(f)])
        g['entries'] = es
        T[f'gimmick_floor_{f}'] = g
        changes[f'gimmick_floor_{f}'] = dict(op='replace_entries', note='몬스터·상자 무기 항목을 빼고 시련 전용 표', table=g)
        # S: special_trial_fNN
        sw, sa = byk[f]['S'], arm[f]['S']
        ess = {1: 'dim_essence', 2: 'dim_essence', 3: 'dim_essence', 4: 'labyrinth_essence', 5: 'labyrinth_essence',
               6: 'labyrinth_essence', 7: 'radiant_essence', 8: 'radiant_essence', 9: 'primordial_essence', 10: 'primordial_essence'}[f]
        st = {'rolls': 1, 'gold': [int(mid(LOOT[f'gimmick_floor_{f}']['gold']) * 0.5), int(mid(LOOT[f'gimmick_floor_{f}']['gold']))],
              'guaranteed': [{'one_of': sw}, {'item': ess, 'amount': 1}], 'entries': []}
        if sa:
            st['entries'].append({'one_of': sa, 'chance': 0.5})
        T[tid_special(f)] = st
        changes[tid_special(f)] = dict(op='new', note=f'{f}층 특별 시련 성공 상자 (시련방 보상에 더해서)', table=st)
        # V: hoard_gear_fNN
        vw, va = byk[f]['V'], arm[f]['V']
        h = H_RATE(f)
        ht = {'rolls': 1, 'entries': [{'one_of': vw, 'chance': h}]}
        if va:
            ht['entries'].append({'one_of': va, 'chance': round(h * 1.5, 3)})
        T[tid_hoard(f)] = ht
        changes[tid_hoard(f)] = dict(op='new', note=f'{f}층 금고 금 상자·길들인 미믹 상자마다 한 번 더 굴림', table=ht)
        # E: 정예 테이블에 무기 항목 (+ 새 방어구 세트는 기존 방어구 묶음에 합침)
        ew, ea = byk[f]['E'], arm[f]['E']
        if ew or ea:
            et = dict(T[elite])
            es = list(et['entries'])
            if ea:
                for i, e in enumerate(es):
                    if 'one_of' in e and all(ITEMS.get(x, {}).get('type') == 'armor' and ITEMS[x].get('armor_slot') != 'offhand' for x in e['one_of']):
                        es[i] = dict(e, one_of=e['one_of'] + ea)
                        break
            if ew:
                idx = next((i for i, e in enumerate(es) if str(e.get('table', '')).startswith('enhance_')), len(es))
                es.insert(idx, {'one_of': ew, 'chance': E_RATE[f]})
            et['entries'] = es
            T[elite] = et
            changes[elite] = dict(op='replace_entries', note=f'{f}층 정예 무기 {len(ew)}개' + (f' · 새 방어구 세트 묶음에 합침' if ea else ''), table=et)
    return T, changes


# ── 기대 회차 ──
def fits(w, stat):
    return stat in w['req'].split('|')


def pick_p(target, pool, allw):
    """one_of 에서 target 이 나올 확률 — 줍는 사람 주 능력치 = target 요구 능력치 (편향 BIAS, 맞는 것이 없으면 전체)."""
    n = len(pool)
    stat = allw[target]['req'].split('|')[0] if target in allw else None
    nfit = sum(1 for x in pool if x in allw and stat and fits(allw[x], stat)) if stat else 0
    if nfit == 0:
        return 1.0 / n
    return BIAS / nfit + (1 - BIAS) / n


def rolls_per_run(tid, f, tables):
    """1회 돌기에 tid 를 '바로' 굴리는 기대 횟수 (부모 테이블 항목 chance × 부모 굴림 수 × 부모 횟수)."""
    tot = 0.0
    srcs = run_sources(f)
    c = maze(f)
    if tid == tid_hoard(f):
        return c['vault'] + c['mimic']
    if tid == tid_special(f):
        return SPECIAL_Q * SPECIAL_C
    for t, n in srcs:
        tt = tables.get(t) or {}
        r = max(1, tt.get('rolls', 1))
        for e in tt.get('entries') or []:
            if e.get('table') == tid:
                tot += n * r * min(1.0, e['chance'])
        for e in tt.get('guaranteed') or []:
            if e.get('table') == tid:
                tot += n
    return tot


def runs_for(wid, allw, tables, homes):
    """그 무기 하나(내 주 능력치에 맞는 것)를 얻기까지 기대 회차."""
    w = allw[wid]
    f = w['F']
    home = homes.get(wid)
    if home is None:
        return None
    tid, entry = home
    if tid.startswith('recipe:') or tid.startswith('shop:'):
        return None
    tt = tables[tid]
    p = 0.0
    if tid in (tid_common(f), tid_trial(f), tid_hoard(f), tid_special(f)):
        R = rolls_per_run(tid, f, tables)
        r = max(1, tt.get('rolls', 1))
        for e in (tt.get('entries') or []):
            if 'one_of' in e and wid in e['one_of']:
                p += R * r * min(1, e.get('chance', 1)) * pick_p(wid, e['one_of'], allw)
        for e in (tt.get('guaranteed') or []):
            if 'one_of' in e and wid in e['one_of']:
                p += R * pick_p(wid, e['one_of'], allw)
    else:   # 정예·보스 테이블 직접
        n = ELITES[f] if tid == floor_tables(f)[1] else 1.0
        r = max(1, tt.get('rolls', 1))
        for e in (tt.get('entries') or []):
            if 'one_of' in e and wid in e['one_of'] and not e.get('min_difficulty'):
                p += n * r * min(1, e['chance']) * pick_p(wid, e['one_of'], allw)
            elif e.get('item') == wid and not e.get('min_difficulty'):
                p += n * r * min(1, e['chance'])
        for e in (tt.get('guaranteed') or []):
            if 'one_of' in e and wid in e['one_of']:
                p += n * pick_p(wid, e['one_of'], allw)
    if p <= 0:
        return None
    return 1.0 / min(0.999, p)     # 기하분포 기대값


def homes_of(tables, allw):
    """무기 → (테이블, 항목) — 직접 들어 있는 테이블(gear_fNN_common 은 그 표 자체)."""
    out = {}
    for tid, t in tables.items():
        for e in (t.get('entries') or []) + (t.get('guaranteed') or []):
            for x in (e.get('one_of') or ([e['item']] if 'item' in e else [])):
                if x in allw:
                    out.setdefault(x, (tid, e))
    for rid, r in RECIPES.items():
        if r['result'] in allw:
            out.setdefault(r['result'], ('recipe:' + rid, None))
    return out


def forge_cost(f, tables, recipe):
    """레시피 하나를 재료로 모으는 회차 (재료별 필요/1회 수확의 최대) + 골드 회차."""
    y = run_yield(f, tables)
    g = run_gold(f)
    worst = 0.0
    detail = {}
    for m, n in recipe['materials'].items():
        per = y.get(m, 0)
        runs = n / per if per > 0 else float('inf')
        detail[m] = (n, round(per, 2), round(runs, 2))
        worst = max(worst, runs)
    return worst, recipe.get('gold', 0) / g, detail, g
