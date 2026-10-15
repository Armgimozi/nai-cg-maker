#!/usr/bin/env python3
"""장비별 강화 재료 생성기 → plugin/src/main/resources/content/enhance.yml (GDD §11.13).

강화 비용 = 골드 + 강화석(config.yml enhance: — 층 구간별 1종) + **그 장비만의 재료**(이 파일이 만드는 enhance.yml).
재료는 단계 구간마다 다르다 (목표 단계 기준):
  low  (+1 ~ +3) : 주 재료 P            — 그 층 일반 재료 2종 중 무기 종류 / 방어구 부위로 고른 1종
  mid  (+4 ~ +6) : P + 보조 S           — 그 층 정예급 재료(정예 재료 E 또는 그 층 등급 정수)
  high (+7 ~ +10): P + S + 희귀 R        — 보스 고유 장비는 R 대신 그 보스의 핵 K(+9·+10 시도만)
같은 층 · 같은 종류(부위) 안에서는 (S, R) 짝을 번갈아 써서 재료 구성이 겹치지 않게 한다.
개수는 그 층 1회 클리어 공급량(loot.yml 를 펼쳐 계산)에 맞춘다 — 자세한 근거는 생성된 파일 머리 주석.

결과는 장비마다 명시적인 항목으로 쓰므로 사장님이 아무 장비나 직접 고쳐도 된다 (다시 생성하면 덮어씀).

사용:
  python3 tools/gen_enhance.py                       # 저장소 content/ 로 계산해 enhance.yml 쓰기
  python3 tools/gen_enhance.py --content DIR         # 다른 content 폴더로 계산 (예: 루팅 재구성 브랜치)
  python3 tools/gen_enhance.py --spec loot_spec.json # 루팅 명세(new_items·assignments·tables)를 덮어 계산
  python3 tools/gen_enhance.py --report              # 층별 공급량 · 예상 클리어 수 표만 출력
  python3 tools/gen_enhance.py --check               # 쓰지 않고, 지금 파일과 같으면 종료 코드 0
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "plugin/src/main/resources"

# ───────────────────────── 1회 클리어 가정 (보통·솔로·1인, LUK 0) ─────────────────────────
# 몹 수 = GDD §16.1 표, 미로 상자 수는 층 크기로 추정 (loot_spec §3 과 같은 값).
# 솔로 몹 수 감소(party_mob_count)는 보상 보정(WP4 B2·B3)으로 드롭 총량이 같다고 본다.
MOBS_RUN = {1: 24, 2: 28, 3: 28, 4: 36, 5: 40, 6: 45, 7: 45, 8: 55, 9: 55, 10: 60}
def maze_chests(f):
    return {'wood': 4, 'iron': 2, 'gold': 3} if f <= 3 else {'wood': 5, 'iron': 2, 'gold': 3} if f <= 7 else {'wood': 6, 'iron': 3, 'gold': 4}
def stone_tier(f):  # ChestTier.stoneTier 와 같은 구간
    return 1 if f <= 3 else 2 if f <= 7 else 3

# ───────────────────────── 재료 고르기 규칙 ─────────────────────────
# 층마다 일반 재료가 2종 — '단단한' 쪽(껍질·금속·뼈·비늘·톱니)과 '부드러운/마법' 쪽(섬유·실·진주·결정·체액).
HARD = {1: 'beetle_shell', 2: 'rusted_iron', 3: 'spore_cap', 4: 'eel_scale', 5: 'slag_ingot',
        6: 'grave_bone', 7: 'amethyst_shard', 8: 'old_page', 9: 'brass_gear', 10: 'sculk_tendril'}
# 종류 → 단단한 재료(True) / 부드러운 재료(False). 근접 날붙이·몸통·신발·방패 = 단단, 활 시위·마법 무기·투구·다리 = 부드러움.
KIND_HARD = {'sword_shield': True, 'greatsword': True, 'dagger': True, 'bow': False, 'staff': False, 'scepter': False,
             'chest': True, 'feet': True, 'offhand': True, 'head': False, 'legs': False}
KIND_ORDER = ['sword_shield', 'greatsword', 'bow', 'staff', 'scepter', 'dagger', 'head', 'chest', 'legs', 'feet', 'offhand']
KIND_NAME = {'sword_shield': '검방', 'greatsword': '대검', 'bow': '활', 'staff': '지팡이', 'scepter': '홀', 'dagger': '단검',
             'head': '투구', 'chest': '흉갑', 'legs': '하의', 'feet': '신발', 'offhand': '방패'}
ESS_ORDER = ['dim_essence', 'labyrinth_essence', 'radiant_essence', 'primordial_essence']
NOT_FLOOR_MATERIAL = {'lesser_enhance_stone', 'greater_enhance_stone', 'supreme_enhance_stone', 'enhance_protection_scroll'}
RARITY_ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic']

# ───────────────────────── 개수 (시도 1번당, 목표 단계 순) ─────────────────────────
BANDS = {'low': (1, 3), 'mid': (4, 6), 'high': (7, 10)}
# 주 재료 P — × 그 재료 공급 배율 (아래 p_scale). 무기는 한 벌에 하나라 조금 비싸게, 방어구는 4부위라 조금 싸게.
P_BASE = {'weapon': {'low': [2, 2, 3], 'mid': [3, 3, 4], 'high': [4, 4, 5, 6]},
          'shield': {'low': [2, 3, 3], 'mid': [3, 4, 4], 'high': [4, 5, 5, 6]},
          'armor': {'low': [2, 2, 2], 'mid': [2, 3, 3], 'high': [3, 4, 4, 5]}}
S_COUNT = {'E': {'mid': [1, 1, 2], 'high': [1, 1, 1, 2]},             # 정예 재료는 1회 3~5개뿐
           'ess': {'mid': [2, 2, 3], 'high': [2, 2, 3, 3]}}          # 정수는 1회 9~12개
R_COUNT = {'E': [1, 1, 1, 2], 'ess': [1, 1, 2, 2], 'next': [1, 1, 1, 1]}
K_COUNT = [0, 0, 1, 1]                                                # 보스 핵: +9 · +10 시도만 (근거는 머리 주석)
PAIRS = [('E', 'ess'), ('ess', 'E'), ('E', 'next')]  # 같은 층·종류 안 n번째 장비의 (S, R) — 보스 고유는 S 만 E ↔ 정수
# 같은 주 재료를 쓰는 종류끼리 시작 짝을 엇갈려(검방 0 · 대검 1 · 단검 2 …) 층 안에서 똑같은 구성을 줄인다
KIND_OFFSET = {'sword_shield': 0, 'greatsword': 1, 'dagger': 2, 'bow': 0, 'staff': 1, 'scepter': 2,
               'chest': 0, 'feet': 1, 'offhand': 2, 'head': 0, 'legs': 1}
REF_SUPPLY = 40.0                                                      # 1~3층 일반 재료 1회 공급량 ≈ 기준 배율 1.0


def p_scale(supply):
    """일반 재료 공급이 많은 깊은 층은 개수도 늘린다 (0.25 단위, 1.0 ~ 2.0)."""
    return max(1.0, min(2.0, round(supply / REF_SUPPLY * 4) / 4))


# ───────────────────────── 콘텐츠 읽기 ─────────────────────────
def load_yaml(p):
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_content(content_dir, spec_path=None):
    c = {n: load_yaml(Path(content_dir) / f'{n}.yml') for n in ('items', 'loot', 'mobs', 'bosses', 'floors')}
    items = c['items'].get('items') or {}
    tables = c['loot'].get('tables') or {}
    if spec_path:
        spec = json.load(open(spec_path, encoding='utf-8'))
        for i, v in (spec.get('new_items') or {}).items():
            items.setdefault(i, v)
        for i, a in (spec.get('assignments') or {}).items():
            if i in items:
                items[i]['floor'] = a.get('floor', items[i].get('floor'))
                if a.get('sources'):
                    items[i]['sources'] = a['sources']
        tables.update(spec.get('tables') or {})
    return items, tables, c['mobs'].get('mobs') or {}, c['bosses'].get('bosses') or {}, c['floors'].get('floors') or {}


def enhance_config():
    cfg = (load_yaml(RES / 'config.yml').get('enhance') or {})
    max_level = int(cfg.get('max_level', 10))
    chances = list(cfg.get('chances') or [1.0, 1.0, 1.0, 1.0, 0.90, 0.80, 0.65, 0.50, 0.35, 0.20])
    stone_counts = list(cfg.get('stone_counts') or [1, 1, 1, 1, 2, 2, 2, 3, 3, 4])
    stones = cfg.get('stones') or [{'item': 'lesser_enhance_stone', 'max_floor': 3}, {'item': 'greater_enhance_stone', 'max_floor': 7},
                                   {'item': 'supreme_enhance_stone', 'max_floor': 10}]
    at = lambda lst, t: lst[max(0, min(len(lst) - 1, t - 1))]
    return {'max': max_level, 'chance': [at(chances, t) for t in range(1, max_level + 1)],
            'stones': [at(stone_counts, t) for t in range(1, max_level + 1)],
            'down': int(cfg.get('downgrade_from', 7)), 'stone_items': sorted(stones, key=lambda s: s['max_floor'])}


# ───────────────────────── 공급량 (1회 클리어 기대 개수) ─────────────────────────
def amount(a):
    if a is None:
        return 1.0
    if isinstance(a, list):
        return (a[0] + a[-1]) / 2
    return float(a)


def expect(tables, tid, depth=0):
    out = collections.Counter()
    t = tables.get(tid)
    if not t or depth > 8:
        return out
    rolls = max(1, t.get('rolls', 1))

    def add(e, mult):
        if 'item' in e:
            out[e['item']] += mult * amount(e.get('amount'))
        elif 'one_of' in e:
            for i in e['one_of']:
                out[i] += mult * amount(e.get('amount')) / len(e['one_of'])
        elif 'table' in e:
            for k, v in expect(tables, e['table'], depth + 1).items():
                out[k] += mult * v
    for e in t.get('guaranteed') or []:
        add(e, min(1.0, e.get('chance', 1.0)))
    for e in t.get('entries') or []:
        add(e, rolls * min(1.0, e.get('chance', 1.0)))
    return out


def floor_supply(f, fd, tables, mobs, bosses):
    tot = collections.Counter()
    normal = fd.get('mobs') or []
    for m in normal:
        for k, v in expect(tables, mobs[m]['drops']).items():
            tot[k] += v * MOBS_RUN.get(f, 40) / len(normal)
    rooms = fd.get('rooms') or {}
    if fd.get('elite') in mobs:
        for k, v in expect(tables, mobs[fd['elite']]['drops']).items():
            tot[k] += v * rooms.get('elite', 1)
    if fd.get('boss') in bosses:
        tot.update(expect(tables, bosses[fd['boss']]['drops']))
    for k, v in expect(tables, f'treasure_floor_{f}').items():
        tot[k] += v * 3 * rooms.get('treasure', 1)
    tot.update(expect(tables, f'gimmick_floor_{f}'))
    br = 1 if f <= 3 else 2 if f <= 6 else 3 if f <= 9 else 4
    for tier, n in maze_chests(f).items():
        tid = f'maze_chest_{tier}_f{f}' if f'maze_chest_{tier}_f{f}' in tables else f'maze_chest_{tier}_{br}'
        for k, v in expect(tables, tid).items():
            tot[k] += v * n
        if tier != 'wood':
            for k, v in expect(tables, f'maze_enhance_{tier}_t{stone_tier(f)}').items():
                tot[k] += v * n
    return tot


# ───────────────────────── 강화 횟수 (정확한 기대값) ─────────────────────────
def attempts(cfg, goal, protect=False):
    """0 → goal 까지 목표 단계별 기대 시도 수 (흡수 마르코프 사슬의 기본 행렬, 가우스 소거)."""
    n = goal  # 상태 0..goal-1
    a = [[0.0] * n for _ in range(n)]
    for lv in range(n):
        p = cfg['chance'][lv]
        a[lv][lv] += 1.0
        if lv + 1 < n:
            a[lv][lv + 1] -= p
        fail = 1 - p
        if fail > 0:
            if lv >= cfg['down'] and lv > 0 and not protect:
                a[lv][lv - 1] -= fail
            else:
                a[lv][lv] -= fail
    # N = (I − Q)^−1, 0 행: x·(I − Q) = e0 → (I − Q)^T x = e0
    m = [[a[j][i] for j in range(n)] + [1.0 if i == 0 else 0.0] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[r][col]:
                k = m[r][col] / m[col][col]
                for cc in range(col, n + 1):
                    m[r][cc] -= k * m[col][cc]
    visits = [m[i][n] / m[i][i] for i in range(n)]
    return {lv + 1: visits[lv] for lv in range(n)}  # 목표 단계 → 시도 수


# ───────────────────────── 생성 ─────────────────────────
def classify(items, supply_by_floor):
    """층 → {commons, hard, soft, E, K, ess, next}."""
    out = {}
    for f, sup in supply_by_floor.items():
        mats = [i for i, v in items.items() if v.get('type') == 'material' and v.get('floor') == f and i not in NOT_FLOOR_MATERIAL]
        core = [i for i in mats if (items[i].get('sources') or []) == ['boss']]
        elite = [i for i in mats if i not in core and items[i].get('rarity') == 'rare']
        commons = sorted([i for i in mats if i not in core and i not in elite], key=lambda i: -sup[i])
        ess = max(ESS_ORDER, key=lambda e: sup[e])
        nxt = ESS_ORDER[min(len(ESS_ORDER) - 1, ESS_ORDER.index(ess) + 1)]
        hard = HARD.get(f) if HARD.get(f) in commons else commons[-1]
        soft = next(i for i in commons if i != hard) if len(commons) > 1 else hard
        out[f] = {'commons': commons, 'hard': hard, 'soft': soft, 'E': elite[0] if elite else ess,
                  'K': core[0] if core else None, 'ess': ess, 'next': nxt if nxt != ess else None}
    return out


def boss_only_items(items, tables, mobs, bosses, floors):
    """보스 테이블에서만 나오는 장비 → 그 보스의 층."""
    def expand(tid, seen=frozenset()):
        if tid in seen or tid not in tables:
            return set()
        t = tables[tid]
        s = set()
        for e in (t.get('entries') or []) + (t.get('guaranteed') or []):
            if 'item' in e:
                s.add(e['item'])
            elif 'one_of' in e:
                s |= set(e['one_of'])
            elif 'table' in e:
                s |= expand(e['table'], seen | {tid})
        return s
    boss_tables = {b['drops']: b.get('floor') for b in bosses.values() if b.get('drops')}
    in_boss, elsewhere = {}, set()
    for tid in tables:
        got = expand(tid)
        if tid in boss_tables:
            for i in got:
                in_boss[i] = boss_tables[tid]
        elif not any(tid == b for b in boss_tables):
            # 보스 테이블이 부르는 하위 테이블(potions·enhance_*)도 여기서 같이 펼쳐지지만 장비는 없다
            elsewhere |= got
    # 장비가 보스 테이블의 하위 테이블에만 있는 경우는 없다고 보고, sources 로 한 번 더 확인
    out = {}
    for i, f in in_boss.items():
        v = items.get(i) or {}
        src = set(v.get('sources') or [])
        if v.get('type') in ('weapon', 'armor') and i not in elsewhere and not (src & {'drop', 'chest', 'elite'}):
            out[i] = f
    return out


def gear_floor(v):
    if v.get('floor'):
        return int(v['floor'])
    import math
    return max(1, min(10, math.ceil(max(1, v.get('level_req', 1)) / 5.0)))


def home_text(v, boss):
    if boss:
        return '보스 고유'
    src = v.get('sources') or []
    if 'drop' in src or 'chest' in src:
        return '몬스터·상자'
    if 'elite' in src:
        return '정예'
    if 'starter' in src:
        return '시작 지급'
    if 'reward' in src:
        return '칭호 보상'
    if 'craft' in src:
        return '대장간'
    return '기타'


def band_lists(n, values):
    return [values[min(len(values) - 1, k)] for k in range(n)]


def build(items, tables, mobs, bosses, floors):
    supply = {int(f): floor_supply(int(f), fd, tables, mobs, bosses) for f, fd in floors.items()}
    mats = classify(items, supply)
    boss_only = boss_only_items(items, tables, mobs, bosses, floors)
    gear = [i for i, v in items.items() if v.get('type') in ('weapon', 'armor')]
    groups = collections.defaultdict(list)
    for i in gear:
        v = items[i]
        kind = v.get('weapon_type') or v.get('armor_slot') or 'sword_shield'
        groups[(gear_floor(v), kind, i in boss_only)].append(i)
    rk = lambda i: (items[i].get('level_req', 1), RARITY_ORDER.index(items[i].get('rarity', 'common')) if items[i].get('rarity') in RARITY_ORDER else 0, i)
    recipes = {}
    meta = {}
    for (f, kind, boss), ids in groups.items():
        fm = mats.get(f) or mats[min(mats, key=lambda x: abs(x - f))]
        P = fm['hard'] if KIND_HARD.get(kind, True) else fm['soft']
        sc = p_scale(supply[f][P] if f in supply else REF_SUPPLY)
        for n, i in enumerate(sorted(ids, key=rk)):
            pairs = [(x, y) for x, y in PAIRS if fm.get(x) and fm.get(y) and fm[x] != fm[y]]
            if boss:
                pairs = [(x, 'K') for x in ('E', 'ess') if fm.get(x)]
            k = n + KIND_OFFSET.get(kind, 0)
            s_key, r_key = pairs[k % len(pairs)]
            bump = n // len(pairs)  # 짝이 바닥나면 주 재료를 1개씩 더 (같은 종류 안에서 겹치지 않게)
            cat = 'weapon' if items[i].get('type') == 'weapon' else 'shield' if kind == 'offhand' else 'armor'
            p_counts = {b: [max(1, round(x * sc)) + bump for x in P_BASE[cat][b]] for b in BANDS}
            S = fm[s_key]
            r = {'low': {P: p_counts['low']},
                 'mid': {P: p_counts['mid'], S: S_COUNT[s_key]['mid']}}
            if boss:
                K = mats[boss_only[i]]['K'] if boss_only[i] in mats and mats[boss_only[i]]['K'] else fm['K']
                r['high'] = {P: p_counts['high'], S: S_COUNT[s_key]['high'], K: K_COUNT}
            else:
                R = fm[r_key]
                r['high'] = {P: p_counts['high'], S: S_COUNT[s_key]['high'], R: R_COUNT[r_key]}
            recipes[i] = r
            meta[i] = {'floor': f, 'kind': kind, 'boss': boss, 'P': P, 'S': S, 'variant': (s_key, r_key), 'scale': sc}
    return recipes, meta, supply, mats


def costs_for(cfg, recipe, target):
    for b, (lo, hi) in BANDS.items():
        if lo <= target <= hi or (b == 'high' and target > hi):
            k = min(target, hi) - lo
            return {m: c[min(len(c) - 1, k)] for m, c in recipe.get(b, {}).items() if c[min(len(c) - 1, k)] > 0}
    return {}


def stone_for(cfg, f):
    for s in cfg['stone_items']:
        if f <= s['max_floor']:
            return s['item']
    return cfg['stone_items'][-1]['item']


def needs(cfg, recipe, f, goal, protect=False):
    tot = collections.Counter()
    att = attempts(cfg, goal, protect)
    st = stone_for(cfg, f)
    for t, n in att.items():
        for m, c in costs_for(cfg, recipe, t).items():
            tot[m] += n * c
        tot[st] += n * cfg['stones'][t - 1]
    return tot


def runs_needed(need, sup, fm=None, ignore=()):
    """need 를 모으는 데 드는 클리어 수 (가장 모자란 재료 기준). 윗 정수는 그 층 정수를 5:1 로 정제해 채울 수 있다."""
    worst, which = 0.0, None
    nxt = fm.get('next') if fm else None
    ess = fm.get('ess') if fm else None
    for m, n in need.items():
        if m in ignore or n <= 0:
            continue
        if m == nxt and ess:
            r = (n + need.get(ess, 0) / 5) / (sup.get(m, 0) + sup.get(ess, 0) / 5)
        else:
            s = sup.get(m, 0)
            r = n / s if s > 0 else float('inf')
        if r > worst:
            worst, which = r, m
    return worst, which


# ───────────────────────── 출력 ─────────────────────────
def fmt_counts(c):
    return '[' + ', '.join(str(x) for x in c) + ']'


def kit_for_floor(items, meta, f):
    """그 층 대표 한 벌: 무기 1 + 방어구 4부위(같은 세트 우선) + 방패 1 — 보스 고유 제외."""
    pick = []
    weap = sorted([i for i, m in meta.items() if m['floor'] == f and not m['boss'] and items[i].get('type') == 'weapon'])
    if weap:
        pick.append(weap[0])
    sets = collections.defaultdict(list)
    for i, m in meta.items():
        v = items[i]
        if m['floor'] == f and not m['boss'] and v.get('type') == 'armor' and v.get('armor_slot') != 'offhand' \
                and 'starter' not in (v.get('sources') or []):
            sets[v.get('set_bonus') or v.get('armor_set') or i].append(i)
    full = sorted((s for s in sets.values() if len(s) >= 4), key=lambda s: s[0])
    if full:
        pick += full[0][:4]
    sh = sorted(i for i, m in meta.items() if m['floor'] == f and not m['boss'] and items[i].get('armor_slot') == 'offhand')
    if sh:
        pick.append(sh[0])
    return pick


def report_rows(cfg, items, recipes, meta, supply, mats):
    rows = []
    for f in sorted(supply):
        sup = supply[f]
        kit = kit_for_floor(items, meta, f)
        kit5 = collections.Counter()
        for i in kit:
            kit5.update(needs(cfg, recipes[i], f, 5))
        fm = mats[f]
        one5 = [runs_needed(needs(cfg, recipes[i], f, 5), sup, fm)[0] for i in kit]
        ten = {}
        for i, m in meta.items():
            if m['floor'] != f:
                continue
            key = m['variant'][0] + '/' + m['variant'][1]
            need = needs(cfg, recipes[i], f, 10)
            r, which = runs_needed(need, sup, fm, ignore=(stone_for(cfg, f),))
            rs, _ = runs_needed({stone_for(cfg, f): need[stone_for(cfg, f)]}, sup)
            ten.setdefault(key, (r, which, rs))
        k5, k5w = runs_needed(kit5, sup, fm)
        rows.append({'floor': f, 'mats': mats[f], 'sup': sup, 'kit': kit, 'kit5': (k5, k5w), 'one5': max(one5) if one5 else 0, 'ten': ten})
    return rows


def name(items, i):
    return (items.get(i) or {}).get('name', i)


def write_yaml(cfg, items, recipes, meta, supply, mats, rows, source_note):
    att10 = attempts(cfg, 10)
    att10p = attempts(cfg, 10, protect=True)
    att5 = attempts(cfg, 5)
    L = []
    w = L.append
    w('# ─────────────────────────────────────────────────────────────────────────────')
    w('# enhance.yml — 장비별 강화 재료 (GDD §11.13). tools/gen_enhance.py 가 만든 파일 — 손으로 고쳐도 된다.')
    w('#')
    w('# 강화 한 번 비용 = 골드 + 강화석(config.yml enhance: — 장비 층 구간별 1종) + 아래 그 장비만의 재료.')
    w('# 실패해도 셋 다 사라진다 (보호 주문서는 하락만 막는다). 가방에 전부 있어야 시작하고, 하나라도 모자라면 아무것도 안 가져간다.')
    w('#')
    w('# 형식: <장비 id>: {low: {재료: 개수}, mid: {...}, high: {...}}   — 구간은 아래 bands (목표 단계 기준).')
    w('#   개수 = 숫자 하나(구간 전체 같은 개수) 또는 목록(구간 안 목표 단계 순: low [+1, +2, +3]). 모자란 목록은 마지막 값, 0 = 그 단계엔 필요 없음.')
    w('#   재료 순서 = 강화 창 표시 순서이고, 툴팁에는 첫 재료만 보인다. 여기 없는 장비(새로 넣은 장비)는 강화석·골드만 든다(시작 때 경고).')
    w('#   없는 재료 id 는 시작 때 경고하고 그 줄만 무시한다.')
    w('#')
    w('# ── 재료를 고르는 규칙 (생성기) ─────────────────────────────────────────────')
    w('#   low  (+1~+3) : 주 재료 P = 그 장비 층의 일반 재료 2종 중 하나 — 근접 날붙이(검방·대검·단검)·흉갑·신발·방패는 단단한 쪽')
    w('#                  (껍질·금속·뼈·비늘·톱니), 활·지팡이·홀·투구·하의는 부드러운/마법 쪽(섬유·실·진주·결정·체액).')
    w('#   mid  (+4~+6) : P + 보조 S = 그 층 정예급 재료 — 정예 재료 E(볏·휘장·핵…) 또는 그 층 등급 정수.')
    w('#   high (+7~+10): P + S + 희귀 R = E·정수·한 등급 위 정수 중 S 와 다른 것. 보스 고유 장비는 R 대신 그 보스의 핵(+9·+10 시도).')
    w('#   같은 층·같은 종류(부위) 장비는 (S, R) 짝을 (E, 정수) → (정수, E) → (E, 윗 정수) 순으로 번갈아 써서 구성이 겹치지 않는다.')
    w('#   P 개수는 그 재료 1회 공급량 ÷ 40 (0.25 단위, ×1.0 ~ ×2.0) 을 곱한다 — 깊은 층일수록 많이 떨어지고 많이 든다.')
    w('#')
    w('# ── 근거: 1회 클리어 공급량 (보통·솔로·1인, LUK 0 — loot.yml 을 펼쳐 계산) ──────────')
    w(f'#   가정: 몹 수 GDD §16.1 (1층 24 … 10층 60), 미로 상자 나무 4~6 · 철 2~3 · 금 3~4, 보물방 상자 3개 × 방 수, 기믹방 1, 정예 1~2, 보스 1.')
    w(f'#   계산한 콘텐츠: {source_note}')
    for r in rows:
        m = r['mats']
        s = r['sup']
        w(f"#   {r['floor']:>2}층  P {name(items, m['hard'])} {s[m['hard']]:.0f} · {name(items, m['soft'])} {s[m['soft']]:.0f}"
          f"  | E {name(items, m['E'])} {s[m['E']]:.1f}  | 정수 {name(items, m['ess'])} {s[m['ess']]:.1f}"
          + (f" · 윗 정수 {s[m['next']]:.1f}" if m.get('next') else '')
          + (f"  | 핵 {name(items, m['K'])} {s[m['K']]:.0f}" if m.get('K') else ''))
    w('#   (정수는 대장간에서 5:1 로 윗 등급으로 정제할 수 있다. 일반 재료는 대장간 제작에도 10~24개씩 든다.)')
    w('#')
    w('# ── 근거: 시도 수 (config chances · downgrade_from 그대로, 정확한 기대값) ─────────')
    w('#   +5 까지 ' + ' + '.join(f'{att5[t]:.2f}' for t in sorted(att5)) + f' = {sum(att5.values()):.1f}회 (하락 없음)')
    w('#   +10 까지 (주문서 없이) ' + ' · '.join(f'+{t} {att10[t]:.1f}' for t in range(7, 11)) + f'  합 {sum(att10.values()):.1f}회 — 대부분 +7·+8 하락 고리')
    w(f'#   +10 까지 (하락을 전부 주문서로 막으면) {sum(att10p.values()):.1f}회 · 주문서 {sum(att10p[t] * (1 - cfg["chance"][t - 1]) for t in att10p if t - 1 >= cfg["down"]):.1f}장')
    w('#   보스 핵을 high 구간 모든 시도에 넣으면 +10 까지 핵 ' + f"{sum(att10[t] for t in range(7, 11)):.0f}개(= 그 보스 {sum(att10[t] for t in range(7, 11)):.0f}번)"
      + f" — 강화석 병목(장비 하나 +10 ≈ 강화석 {sum(att10[t] * cfg['stones'][t - 1] for t in att10):.0f}개)의 3배라서, +9·+10 시도에만 1개씩"
      + f" (+10 까지 핵 {sum(att10[t] * K_COUNT[min(len(K_COUNT) - 1, t - 7)] for t in range(7, 11)):.0f}개) 로 맞췄다.")
    w('#')
    w('# ── 결과: 예상 클리어 수 (그 층만 돌고, 그 재료를 강화에만 쓸 때) ─────────────────')
    w('#   층  | 장비 1개 +5 | 대표 한 벌(무기+방어구 4+방패) +5 (병목) | +10 장비 1개 (재료 병목 / 강화석)')
    for r in rows:
        ten = r['ten']
        parts = []
        for key in ('E/ess', 'ess/E', 'E/next', 'E/K', 'ess/K'):
            if key in ten:
                rr, which, rs = ten[key]
                label = {'E/ess': 'E+정수', 'ess/E': '정수+E', 'E/next': 'E+윗정수', 'E/K': '보스(E)', 'ess/K': '보스(정수)'}[key]
                parts.append(f'{label} {rr:.0f}회({name(items, which)})')
        stone_runs = max((v[2] for v in ten.values()), default=0)
        w(f"#   {r['floor']:>2}층 | {r['one5']:.1f}회 | {r['kit5'][0]:.1f}회 ({name(items, r['kit5'][1])}) | " + ' · '.join(parts)
          + f' / 강화석 {stone_runs:.0f}회')
    w('#   → +5 는 장비 하나가 1회 안팎, 한 벌이 3~5회 (강화석·정예 재료가 병목 — 제작에도 쓰므로 실제로는 조금 더).')
    w('#   → +10 은 장기 목표: 일반 장비 15~25회, 보스 장비는 핵 때문에 그 보스 20회 안팎 (보호 주문서를 쓰면 크게 준다).')
    w('#   1~3층 하급 강화석은 떠돌이 상인 핀에게서 살 수 있어 병목이 아니다.')
    w('# ─────────────────────────────────────────────────────────────────────────────')
    w('version: 1')
    w('')
    w('# 단계 구간 (목표 단계 기준). 마지막 구간 너머(max_level 을 올렸을 때)는 마지막 구간의 마지막 개수.')
    w('bands:')
    for b, (lo, hi) in BANDS.items():
        w(f'  {b}: [{lo}, {hi}]')
    w('')
    w('items:')
    order = sorted(recipes, key=lambda i: (meta[i]['floor'], KIND_ORDER.index(meta[i]['kind']) if meta[i]['kind'] in KIND_ORDER else 99,
                                          meta[i]['boss'], items[i].get('level_req', 1), i))
    last_floor = None
    for i in order:
        m = meta[i]
        f = m['floor']
        if f != last_floor:
            fm = mats[f]
            w('')
            w(f"  # ════ 지하 {f}층 — 단단 {name(items, fm['hard'])} · 부드러움 {name(items, fm['soft'])} · 정예 {name(items, fm['E'])}"
              f" · 정수 {name(items, fm['ess'])}" + (f" · 핵 {name(items, fm['K'])}" if fm.get('K') else '') + ' ════')
            last_floor = f
        v = items[i]
        w(f"  {i}:  # {v.get('name', i)} · {KIND_NAME.get(m['kind'], m['kind'])} · {home_text(v, m['boss'])}")
        r = recipes[i]
        for b in ('low', 'mid', 'high'):
            body = ', '.join(f'{k}: {fmt_counts(c)}' for k, c in r[b].items())
            w(f'    {b}:{" " * (5 - len(b))}{{{body}}}')
    w('')
    return '\n'.join(L)


def check_unique(recipes, meta):
    """같은 층에서 재료 구성까지 똑같은 장비 쌍 → (같은 종류 안, 다른 종류끼리)."""
    seen = collections.defaultdict(list)
    for i, r in recipes.items():
        seen[(meta[i]['floor'], json.dumps(r, sort_keys=True))].append(i)
    same_kind, cross = [], []
    for ids in seen.values():
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                (same_kind if meta[ids[a]]['kind'] == meta[ids[b]]['kind'] else cross).append((ids[a], ids[b]))
    return same_kind, cross


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default=str(RES / 'content'))
    ap.add_argument('--spec')
    ap.add_argument('--out', default=str(RES / 'content/enhance.yml'))
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--note', help='머리 주석의 "계산한 콘텐츠" 설명')
    a = ap.parse_args()
    cfg = enhance_config()
    items, tables, mobs, bosses, floors = load_content(a.content, a.spec)
    recipes, meta, supply, mats = build(items, tables, mobs, bosses, floors)
    rows = report_rows(cfg, items, recipes, meta, supply, mats)
    dup, cross = check_unique(recipes, meta)
    note = a.note or (f'content/ — 장비 {len(recipes)}종 · 루팅 테이블 {len(tables)}개'
                      + (' + 루팅 명세 ' + Path(a.spec).name if a.spec else ''))
    text = write_yaml(cfg, items, recipes, meta, supply, mats, rows, note)
    if a.report:
        print('\n'.join(l for l in text.splitlines() if l.startswith('#')))
        print(f'장비 {len(recipes)}개 · 같은 층·같은 종류 똑같은 구성 {len(dup)}쌍 {dup[:5]} · 다른 종류끼리 {len(cross)}쌍')
        return 0
    if a.check:
        cur = Path(a.out).read_text(encoding='utf-8') if Path(a.out).exists() else ''
        same = cur == text
        print('같음' if same else '다름 — python3 tools/gen_enhance.py 로 다시 만드세요')
        return 0 if same else 1
    Path(a.out).write_text(text, encoding='utf-8')
    print(f'{a.out}: 장비 {len(recipes)}개 · 같은 층·같은 종류 똑같은 구성 {len(dup)}쌍 · 다른 종류끼리 {len(cross)}쌍')
    if dup:
        print('경고: 같은 종류 안에서 겹침', dup)
    return 0


if __name__ == '__main__':
    sys.exit(main())
