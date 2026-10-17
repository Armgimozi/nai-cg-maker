#!/usr/bin/env python3
"""0.3.6 재료 시제품 — 계약 규칙(params.py)으로 0.3.5 content 를 바꿔 본다 (저장소 content 는 읽기만).

design036/tools/mat_proto.py (T) 를 고친 것:
  · 금속 6, 장비 레시피의 금속 = 힘(단계 + 희귀도 + 보스) 으로 고름, 이웃 두 금속 섞기 가능, ING_SHARE 0.20
  · 옛 광물 칸: 주괴 칸은 루팅에서 지움 · 몬스터 칸은 새 몬스터 재료로 이름만
  · 던전 광석은 모든 층에 같은 규칙 (그 층 장비가 쓰는 금속, 1회 목표량 = 한 벌 광석 수요 ÷ 던전 횟수 × 0.25)
  · 강화 S = 그 장비의 주 금속 주괴 (T §8 규칙, 금속만 힘으로)
결과 (실제 content 를 쓰는 것은 Q3 생성기 몫):
  out/proto/content/{items,loot,recipes,mobs,bosses,floors}.yml · out/proto/enhance.yml · out/proto036.json

  python3 -B proto036.py
"""
import collections
import copy
import json
import shutil
import statistics
import sys
from pathlib import Path

import yaml

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LAB = HERE.parents[3]                       # labyrinth/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / 'tools'))
import params as P  # noqa: E402
import mine6  # noqa: E402
import gen_enhance as GE  # noqa: E402

LIVE_CONTENT = LAB / 'plugin/src/main/resources/content'
# 시제품은 늘 0.3.5.1 content 위에서 돈다. Q3 가 content 를 0.3.6 으로 바꾼 뒤에는(옛 광물 id 가 없음) 계약 커밋의 content 를
# git 에서 꺼내 out/base_0351/ 에 둔다 (다시 돌려도 같은 결과).
BASE_REV = 'f0f731be'          # 0.3.6 Q0 계약 커밋 — content = 0.3.5.1
BASE_FILES = ('items', 'loot', 'recipes', 'mobs', 'bosses', 'floors', 'npcs', 'enhance', 'titles')


def base_content():
    if 'rusted_iron:' in (LIVE_CONTENT / 'items.yml').read_text(encoding='utf-8'):
        return LIVE_CONTENT
    out = HERE / 'out/base_0351/content'
    if all((out / f'{n}.yml').exists() for n in BASE_FILES):
        return out
    import subprocess
    top = subprocess.run(['git', '-C', str(LAB), 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True).stdout.strip()
    rel = (LIVE_CONTENT.resolve()).relative_to(Path(top).resolve()).as_posix()
    out.mkdir(parents=True, exist_ok=True)
    for n in BASE_FILES:
        r = subprocess.run(['git', '-C', top, 'show', f'{BASE_REV}:{rel}/{n}.yml'], capture_output=True, check=True)
        (out / f'{n}.yml').write_bytes(r.stdout)
    return out


CONTENT = base_content()
OUT = HERE / 'out/proto'
STONES = {'lesser_enhance_stone', 'greater_enhance_stone', 'supreme_enhance_stone', 'enhance_protection_scroll'}
GEAR = ('weapon', 'armor', 'accessory')
ORES = {m['ore']: m for m in P.METALS}
INGOTS = {m['ingot']: m for m in P.METALS}
GEM_IDS = {g['id'] for g in P.GEMS}


def load(n, root=CONTENT):
    return yaml.safe_load(open(root / f'{n}.yml', encoding='utf-8')) or {}


def is_boss_gear(v):
    return 'boss' in (v.get('sources') or [])


def floor_commons(items):
    out = collections.defaultdict(list)
    for i, v in items.items():
        if v.get('type') != 'material' or not v.get('floor') or i in STONES:
            continue
        if (v.get('sources') or []) == ['boss'] or v.get('rarity') == 'rare':
            continue
        out[int(v['floor'])].append(i)
    return out


# ───────────────────────── items ─────────────────────────
def tool_block(m):
    r = m['rank']
    return {'kind': 'pickaxe', 'tier': r, 'speed': P.pick_speed(r), 'bonus': P.PICK_BONUS[r]}


def build_items(items0):
    items = {}
    for i, v in items0.items():
        if i in P.RETIRED:
            continue
        v = copy.deepcopy(v)
        if i in ('lesser_enhance_stone', 'greater_enhance_stone', 'supreme_enhance_stone'):
            v['sources'] = list(v.get('sources') or []) + ['smelt']
        items[i] = v
    for i, d in P.MONSTER_NEW.items():
        items[i] = {'name': d['name'], 'type': 'material', 'rarity': d['rarity'], 'floor': d['floor'],
                    'sources': list(items0[d['old']].get('sources') or []), 'model': {'shape': 'icon'}, 'lore': d['lore']}
    for m in P.METALS:
        items[m['ore']] = {'name': m['ore_name'], 'type': 'material', 'rarity': m['ore_rarity'], 'mine_level': m['rank'],
                           'mine_kind': 'ore', 'sources': ['mine'], 'model': {'shape': 'icon'}, 'lore': m['ore_lore']}
        items[m['ingot']] = {'name': m['ingot_name'], 'type': 'material', 'rarity': m['ingot_rarity'], 'mine_level': m['rank'],
                             'mine_kind': 'ingot', 'sources': ['smelt'], 'model': {'shape': 'icon'}, 'lore': m['ingot_lore']}
    for g in P.GEMS:
        items[g['id']] = {'name': g['ko'], 'type': 'material', 'rarity': g['rarity'], 'mine_level': g['rank'], 'mine_kind': 'gem',
                          'sources': ['mine'], 'model': {'shape': 'icon'}, 'lore': g['lore']}
    for m in P.METALS:
        src = ['starter', 'shop'] if m['rank'] == 1 else ['craft']
        items[m['pickaxe']] = {'name': m['pick_name'], 'type': 'tool', 'rarity': m['pick_rarity'], 'tool': tool_block(m),
                               'sources': src, 'model': {'shape': 'pickaxe'}, 'lore': m['pick_lore']}
    return items


# ───────────────────────── recipes ─────────────────────────
def build_recipes(items0, recipes0, commons0):
    common_set = {m for ms in commons0.values() for m in ms}
    out, log = {}, []
    for rid, r in recipes0.items():
        r2 = copy.deepcopy(r)
        res = items0.get(r['result']) or {}
        if res.get('type') in GEAR:
            t = GE.gear_floor(res)
            mats = list((r.get('materials') or {}).items())
            B = sum(n for m, n in mats if m in common_set)
            n_ing = max(P.MIN_ING, P.half_up(P.ING_SHARE * B))
            split = P.metals_for(t, res.get('rarity', 'common'), is_boss_gear(res), n_ing)
            new, last_common, removed = [], -1, {}
            for m, n in mats:
                rr = P.RETIRED.get(m)
                if rr and rr['slot'] == 'ingot':
                    removed[m] = n
                    continue
                m2 = rr['to'] if rr else m
                new.append((m2, n))
                if m in common_set or rr:
                    last_common = len(new) - 1
            ins = [(P.METAL[k]['ingot'], n) for k, n in split]
            new[last_common + 1:last_common + 1] = ins
            r2['materials'] = dict(new)
            log.append({'id': rid, 'result': r['result'], 'tier': t, 'rarity': res.get('rarity'), 'boss': is_boss_gear(res),
                        'cat': r.get('category'), 'B': B, 'n': n_ing, 'split': split,
                        'pos': P.power_pos(t, res.get('rarity', 'common'), is_boss_gear(res)), 'removed': removed,
                        'old': dict(mats), 'new': r2['materials']})
        out[rid] = r2
    for m in P.METALS:
        out[m['ingot']] = {'result': m['ingot'], 'category': 'material', 'station': 'smelter',
                           'materials': {m['ore']: P.ORE_PER_INGOT}, 'gold': m['smelt_gold'], 'amount': 1}
    for s in P.STONE_RECIPES:
        out[s['id']] = {'result': s['result'], 'category': 'material', 'station': 'smelter',
                        'materials': {s['gem']: 1, s['essence']: 1}, 'gold': s['gold'], 'amount': P.STONE_YIELD}
    for pid, d in P.PICK_RECIPES.items():
        out[pid] = {'result': pid, 'category': 'tool', 'station': 'smelter',
                    'materials': {d['prev']: 1, d['ingot'][0]: d['ingot'][1], d['gem'][0]: d['gem'][1], d['essence'][0]: d['essence'][1]},
                    'gold': d['gold']}
    return out, log


def demand_by_tier(log):
    d = collections.defaultdict(collections.Counter)
    for x in log:
        for k, n in x['split']:
            d[x['tier']][k] += n
    return d


def floor_metal_shares(demand):
    """층 f 던전이 주는 금속 = 그 단계 장비 레시피의 주괴 수요 비율 (15% 미만은 빼고 다시 나눔, 최대 2종)."""
    out = {}
    for f in range(1, 11):
        c = demand[f]
        tot = sum(c.values())
        top = [(k, n / tot) for k, n in c.most_common() if n / tot >= 0.15][:2]
        s = sum(w for _, w in top)
        out[f] = {k: round(w / s, 3) for k, w in top}
    return out


def conversion_map(demand):
    conv = {}
    for old, r in P.RETIRED.items():
        if r['slot'] == 'monster':
            conv[old] = r['to']
        else:
            k = demand[r['floor']].most_common(1)[0][0]
            conv[old] = P.METAL[k]['ore']
    return conv


# ───────────────────────── loot ─────────────────────────
def strip_loot(loot0):
    """옛 광물: 주괴 칸은 지움 (one_of 에서는 빼서 남은 재료가 몫을 나눔), 몬스터 칸은 새 몬스터 재료로."""
    tables, logc = {}, collections.Counter()

    def fix(e):
        e = dict(e)
        if e.get('item') in P.RETIRED:
            r = P.RETIRED[e['item']]
            if r['slot'] == 'monster':
                logc['rename'] += 1
                e['item'] = r['to']
                return [e]
            logc['removed'] += 1
            return []
        if e.get('one_of') and set(e['one_of']) & set(P.RETIRED):
            logc['one_of'] += 1
            new = []
            for x in e['one_of']:
                r = P.RETIRED.get(x)
                if r and r['slot'] == 'ingot':
                    continue
                y = r['to'] if r else x
                if y not in new:
                    new.append(y)
            if not new:
                return []
            if len(new) == 1:
                e.pop('one_of')
                return [{'item': new[0], **e}]
            e['one_of'] = new
        return [e]

    for tid, t in loot0.items():
        t2 = copy.deepcopy(t)
        if t.get('guaranteed'):
            t2['guaranteed'] = [y for e in t['guaranteed'] for y in fix(e)]
        t2['entries'] = [y for e in (t.get('entries') or []) for y in fix(e)]
        tables[tid] = t2
    return tables, logc


def add_ore_drops(tables, c, targets, shares):
    """층마다 1회(솔로) 기대 광석 = targets[f], 금속 비율 shares[f], 집 비율 DUNGEON_ORE_SPLIT. 'guaranteed' 에 확률 항목으로."""
    added = collections.Counter()
    for f in range(1, 11):
        fd = c['floors'][f] if f in c['floors'] else c['floors'][str(f)]
        roots = GE.floor_roots(f, fd, tables, c['mobs'], c['bosses'])
        by_home = collections.defaultdict(list)
        for tid, n, home in roots:
            h = {'mob': 'mob', 'elite': 'elite', 'boss': 'boss'}.get(home)
            if h is None and tid in (f'treasure_floor_{f}', f'gimmick_floor_{f}'):
                h = 'chest'
            if h:
                by_home[h].append((tid, n))
        for h, share in P.DUNGEON_ORE_SPLIT.items():
            lst = by_home.get(h) or by_home['mob']
            tot_n = sum(n for _, n in lst)
            for tid, n in lst:
                for k, w in shares[f].items():
                    exp = targets[f] * share * w / tot_n        # 이 테이블 한 번에 기대 개수
                    amt = 1 if exp <= 0.6 else max(1, round(exp / 0.6))
                    chance = round(min(1.0, exp / amt), 4)
                    e = {'item': P.METAL[k]['ore'], 'chance': chance}
                    if amt > 1:
                        e['amount'] = amt
                    tables[tid].setdefault('guaranteed', []).append(e)
                    added[f] += 1
    return added


def ore_sources(items, tables, c):
    kinds = {}
    for m in c['mobs'].values():
        if m.get('drops'):
            kinds[m['drops']] = 'elite' if m.get('rank') == 'elite' else 'drop'
    for b in c['bosses'].values():
        if b.get('drops'):
            kinds[b['drops']] = 'boss'
    found = collections.defaultdict(set)
    for tid, t in tables.items():
        k = kinds.get(tid, 'chest' if tid.startswith(('treasure_', 'gimmick_', 'maze_chest_')) else None)
        if not k:
            continue
        for e in (t.get('guaranteed') or []) + (t.get('entries') or []):
            for x in ([e['item']] if 'item' in e else e.get('one_of') or []):
                if x in ORES:
                    found[x].add(k)
    for x, ks in found.items():
        items[x]['sources'] = ['mine'] + [k for k in ('drop', 'elite', 'boss', 'chest') if k in ks]


# ───────────────────────── 대표 한 벌 · 던전 횟수 (economy 와 같이 씀) ─────────────────────────
def content_dict(items, tables, recipes, base=CONTENT):
    return {'items': items, 'tables': tables, 'recipes': recipes, 'mobs': load('mobs', base)['mobs'],
            'bosses': load('bosses', base)['bosses'], 'floors': {int(k): v for k, v in load('floors', base)['floors'].items()}}


def supplies(c, party=False):
    sup = {}
    for f, fd in c['floors'].items():
        roots = GE.floor_roots(int(f), fd, c['tables'], c['mobs'], c['bosses'])
        s = GE.supply_of(c['tables'], roots)
        if party:
            cores = {i for i, v in c['items'].items() if v.get('type') == 'material' and (v.get('sources') or []) == ['boss']}
            s = collections.Counter({m: (n if m in cores else n * (1 + P.PARTY_BONUS)) for m, n in s.items()})
        sup[int(f)] = s
    return sup


def pick_kit(c, t):
    items, recipes = c['items'], c['recipes']
    rec = {r['result']: r for r in recipes.values() if r.get('result') in items and items[r['result']].get('type') in GEAR}
    total = lambda i: sum(rec[i]['materials'].values())
    weap = sorted([i for i in rec if items[i].get('type') == 'weapon' and GE.gear_floor(items[i]) == t
                   and not is_boss_gear(items[i])], key=lambda i: (total(i), i))
    sets = collections.defaultdict(list)
    for i in rec:
        v = items[i]
        if v.get('type') == 'armor' and GE.gear_floor(v) == t and v.get('armor_slot') in ('head', 'chest', 'legs', 'feet') \
                and not is_boss_gear(v) and v.get('set_bonus'):
            sets[v['set_bonus']].append(i)
    full = sorted([s for s in sets.values() if len(s) == 4], key=lambda s: (sum(total(i) for i in s), s[0]))
    kit = []
    if weap:
        kit.append(weap[len(weap) // 2])
    if full:
        kit += full[len(full) // 2]
    return kit, rec


def normalize(e):
    return {b: {m: (v if isinstance(v, list) else [v]) for m, v in (d or {}).items()} for b, d in e.items()}


def kit_need(c, enh, cfg, t, goal=None):
    kit, rec = pick_kit(c, t)
    need = collections.Counter()
    for i in kit:
        need.update(rec[i]['materials'])
    if goal:
        for i in kit:
            if i in enh:
                need.update(GE.needs(cfg, normalize(enh[i]), t, goal))
    return kit, need


def split_need(need):
    ing = {m: n for m, n in need.items() if m in INGOTS}
    gem = {m: n for m, n in need.items() if m in GEM_IDS}
    dun = {m: n for m, n in need.items() if m not in INGOTS and m not in GEM_IDS and m not in ORES}
    return dun, ing, gem


def dungeon_runs(dun, sup, refine):
    stones = {m for m in dun if m.endswith('enhance_stone')}
    runs, which = GE.runs_needed({m: n for m, n in dun.items() if m not in stones}, sup, refine)
    rs, _ = GE.runs_needed({m: n for m, n in dun.items() if m in stones}, sup, refine) if stones else (0, None)
    return runs, which, rs


# ───────────────────────── 강화 (gen_enhance 규칙 고침) ─────────────────────────
def patched_enhance(proto_dir, recipes):
    GE.MODE036 = False       # 시제품이 아래에서 0.3.6 규칙을 직접 덧씌운다 (gen_enhance 의 드롭 단계 규칙은 쓰지 않음)
    GE.HARD.clear()
    GE.HARD.update({1: 'beetle_shell', 2: 'spider_silk', 3: 'spore_cap', 4: 'eel_scale', 5: 'ember_soul', 6: 'grave_bone',
                    7: 'resonant_sinew', 8: 'old_page', 9: 'clock_oil', 10: 'sculk_tendril'})
    rec_by_result = {r['result']: r for r in recipes.values()}
    orig_cand = GE.candidates
    orig_floor_init = GE.Floor.__init__
    rate = dict(P.ENHANCE_INGOT_RATE)   # 0.3.6.1 표 B 값 고정 (gen_enhance 와 같음 — mine.json economy.enhance_ingot_rate)

    def floor_init(self, f, items, supply, roots, tables):
        orig_floor_init(self, f, items, supply, roots, tables)
        self.supply = collections.Counter(self.supply)
        for m in P.METALS:   # 주괴 '1회 공급량' = 그 금속 곡괭이로 노려 캘 때 1회 클리어 시간 동안 캐는 주괴 (환산 비교용)
            self.supply[m['ingot']] = rate[m['key']] * P.RUN_MINUTES[f] / P.ORE_PER_INGOT

    def item_ingot(i, v):
        r = rec_by_result.get(i)
        if r:
            ings = [(n, P.METAL[INGOTS[m]['key']]['rank'], m) for m, n in r['materials'].items() if m in INGOTS]
            if ings:
                return max(ings)[2]
        return P.METAL[P.primary_metal(GE.gear_floor(v), v.get('rarity', 'common'), is_boss_gear(v))]['ingot']

    def cand(i, v, fl, tables, recipe, refine):
        c = orig_cand(i, v, fl, tables, recipe, refine)
        ing = item_ingot(i, v)
        mons = list(fl.commons)
        if recipe:
            inr = sorted([(n, k) for k, (m, n) in enumerate(recipe.items()) if m in mons], key=lambda x: (-x[0], x[1]))
            Pm = list(recipe)[inr[0][1]] if inr else (fl.hard if GE.KIND_HARD.get(c['kind'], True) else fl.soft)
        else:
            Pm = fl.hard if GE.KIND_HARD.get(c['kind'], True) else fl.soft
        P2 = next((m for m in mons if m != Pm), None)
        c['bulk'] = [Pm, ing]
        c['ps'] = [(Pm, ing, '')] + ([(P2, ing, 'swap')] if P2 else [(ing, Pm, 'swap')])
        return c

    orig_recipe_of = GE.recipe_of

    def recipe_of(cand, fl, Pm, S_, R, dp=0, ds=0):
        r = orig_recipe_of(cand, fl, Pm, S_, R, dp, ds)
        if S_ in INGOTS:
            scale = GE.p_scale(fl.supply.get(Pm, GE.REF_SUPPLY)) * P.INGOT_UNIT
            sc = GE.band_counts(cand['cat'], 'S', 'common', scale, ds, cand['boss'])
            for b in ('mid', 'high'):
                if S_ in r[b]:
                    r[b][S_] = sc[b]
        if Pm in INGOTS:
            scale = GE.p_scale(fl.supply.get(S_, GE.REF_SUPPLY))
            pc = GE.band_counts(cand['cat'], 'P', 'common', scale * P.INGOT_UNIT, dp, cand['boss'])
            sc = GE.band_counts(cand['cat'], 'S', 'common', scale, ds, cand['boss'])
            for b in ('low', 'mid', 'high'):
                r[b][Pm] = pc[b]
            for b in ('mid', 'high'):
                if S_ in r[b]:
                    r[b][S_] = sc[b]
        return r

    GE.Floor.__init__ = floor_init
    GE.candidates = cand
    GE.recipe_of = recipe_of
    try:
        cfg = GE.enhance_config()
        c = GE.load_content(proto_dir)
        out, meta, fls, collisions, unfair = GE.build(c, cfg)
        refine = GE.refined_from(c['recipes'])
        rows = GE.report_rows(cfg, c['items'], out, meta, fls, refine)
        fair = GE.fairness(cfg, out, meta, fls, refine)
        problems = GE.obtainable_problems(c['items'], out, meta, fls, refine)
        text = GE.write_yaml(cfg, c['items'], out, meta, fls, rows, collisions, fair, '0.3.6 계약 시제품 (tools/data/036/model/out/proto)')
        (OUT / 'enhance.yml').write_text(text, encoding='utf-8')
    finally:
        GE.Floor.__init__ = orig_floor_init
        GE.candidates = orig_cand
        GE.recipe_of = orig_recipe_of
    ing_as_p = sorted(k for k, m in meta.items() if m['P'] in INGOTS)
    no_ingot = sorted(k for k, e in out.items() if not any(m in INGOTS for b in ('mid', 'high') for m in e.get(b, {})))
    return {'out': out, 'meta': meta, 'collisions': len(collisions), 'unfair': unfair, 'problems': problems[:20],
            'cheaper': {t: len(v) for t, v in fair['cheaper'].items()}, 'grade_bad': len(fair['grade_bad']), 'r_bad': len(fair['r_bad']),
            'ingot_as_P': len(ing_as_p), 'no_ingot_mid_high': no_ingot}


def dump(name, key, data):
    with open(OUT / 'content' / f'{name}.yml', 'w', encoding='utf-8') as f:
        yaml.safe_dump({'version': 1, key: data}, f, allow_unicode=True, sort_keys=False, width=200)


def main():
    (OUT / 'content').mkdir(parents=True, exist_ok=True)
    items0 = load('items')['items']
    loot0 = load('loot')['tables']
    recipes0 = load('recipes')['recipes']
    commons0 = floor_commons(items0)
    items = build_items(items0)
    recipes, rlog = build_recipes(items0, recipes0, commons0)
    demand = demand_by_tier(rlog)
    shares = floor_metal_shares(demand)
    conv = conversion_map(demand)
    tables, llog = strip_loot(loot0)

    # 던전 광석 목표 = 그 층 대표 한 벌의 광석 수요 ÷ 던전 횟수(솔로) × 0.25
    c = content_dict(items, tables, recipes)
    sup = supplies(c)
    refine = GE.refined_from(recipes)
    targets, kit_info = {}, {}
    for t in range(1, 11):
        kit, need = kit_need(c, {}, None, t)
        dun, ing, _ = split_need(need)
        runs, which, _ = dungeon_runs(dun, sup[t], refine)
        ore_need = sum(ing.values()) * P.ORE_PER_INGOT
        targets[t] = max(4, P.half_up(P.DUNGEON_ORE_SHARE * ore_need / max(0.5, runs)))
        kit_info[t] = {'kit': kit, 'runs': round(runs, 2), 'ore_need': ore_need, 'ingots': ing}
    added = add_ore_drops(tables, c, targets, shares)
    ore_sources(items, tables, c)
    dump('items', 'items', items)
    dump('loot', 'tables', tables)
    dump('recipes', 'recipes', recipes)
    for n in ('mobs', 'bosses', 'floors'):
        shutil.copy(CONTENT / f'{n}.yml', OUT / 'content' / f'{n}.yml')
    enh = patched_enhance(OUT / 'content', recipes)
    # 실제 1회 던전 광석 (검산)
    c2 = content_dict(items, tables, recipes)
    sup2 = supplies(c2)
    got = {t: {m: round(sup2[t].get(P.METAL[m]['ore'], 0), 1) for m in shares[t]} for t in range(1, 11)}
    mix = collections.Counter(len(x['split']) for x in rlog)
    by_tier = {t: {'recipes': sum(1 for x in rlog if x['tier'] == t), 'ingots': dict(demand[t]),
                   'pos': sorted({x['pos'] for x in rlog if x['tier'] == t})} for t in range(1, 11)}
    res = {'recipes_changed': len(rlog), 'mixed_recipes': mix.get(2, 0), 'single_metal_recipes': mix.get(1, 0),
           'by_tier': by_tier, 'floor_metals': shares, 'conversion': conv, 'dungeon_ore_target': targets,
           'dungeon_ore_check': got, 'loot': dict(llog), 'ore_entries_added': dict(added), 'kits': kit_info,
           'enhance': {k: v for k, v in enh.items() if k not in ('out', 'meta')}, 'examples': [x for x in rlog if x['id'] in (
               'mossback_warhammer', 'silkguard_falchion', 'sporecap_warhammer', 'anvil_oath_broadsword', 'frostgrave_mace',
               'amethyst_falchion', 'inkseal_warhammer', 'clockguard_mace', 'void_falchion', 'forge_warden_chest')],
           'ingots_all_recipes_once': {k: sum(demand[t][k] for t in demand) for k in P.OWNER['metal_order']}}
    (HERE / 'out/proto036.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=list), encoding='utf-8')
    print('recipes', len(rlog), 'mixed', mix.get(2, 0), 'loot', dict(llog))
    for t in range(1, 11):
        print(f' t{t}', dict(demand[t]), 'floor metals', shares[t], 'ore target/run', targets[t], 'got', got[t])
    print('conversion', conv)
    print('enhance', {k: v for k, v in res['enhance'].items() if k != 'problems'}, 'problems', len(enh['problems']))


if __name__ == '__main__':
    main()
