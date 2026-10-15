#!/usr/bin/env python3
"""장비별 강화 재료 생성기 → plugin/src/main/resources/content/enhance.yml (GDD §11.13).

강화 비용 = 골드 + 강화석(config.yml enhance: — 층 구간별 1종, 공용) + **그 장비만의 재료**(이 파일이 만드는 enhance.yml).
장비 재료는 '그 장비를 얻는 곳'과 이어진다:
  · 제작법이 있는 장비(recipes.yml 결과 = 장비) → 그 제작 재료
      low  (+1 ~ +3) : 주 재료 P   = 레시피에서 가장 많이 드는 재료
      mid  (+4 ~ +6) : P + 보조 S  = 레시피의 두 번째 재료
      high (+7 ~ +10): P + S + 귀한 재료 R = 레시피에서 가장 귀한 재료 (보스 핵 > 정예 재료 > 정수)
                       보스 핵이 든 레시피는 핵을 +9·+10 시도에만, +7·+8 에는 핵 다음으로 귀한 재료 —
                       시도 1번당 재료는 언제나 3종이라 보스 장비가 일반 장비보다 싼 단계가 없다.
      레시피에 귀한 재료가 없으면(일반 재료 2종짜리) 그 장비가 나오는 곳(몬스터·정예·보스·상자)의 귀한 드롭.
  · 제작법이 없는 장비 → 그 장비를 주는 루팅 테이블(그 층 몬스터·상자 / 정예 / 보스)이 떨어뜨리는 재료
      low = 장비 종류에 맞는 그 층 일반 재료 (근접 날붙이·흉갑·신발 = 단단한 재료, 활·마법 무기·투구·하의 = 부드러운 재료)
      mid = + 나오는 곳이 같이 주는 정수 (정예 장비는 정예 재료) · high = + 나오는 곳의 귀한 드롭 (보스 고유는 +9·+10 에 핵)
      보스 고유 = 그 보스 드롭 · 정예 장비 = 그 정예 드롭 · 층 공용 무기 = 그 층 몬스터·상자 드롭
      시작 지급 = 1층 몬스터·상자 드롭 · 칭호 보상 = 그 층 보스 드롭(핵 포함) · 대장간 전용 = 레시피 재료와 그 정제 정수만
같은 층에서 재료 구성(개수까지)이 똑같은 장비가 생기면 차례로: R 을 그 장비의 다른 귀한 재료(레시피 → 나오는 곳 드롭 →
정제한 윗 등급 정수)로 → (드롭 재료 장비) S 를 정예 재료·다른 일반 재료로 → P·S 순서 바꿈 → P 개수 +1.
(같은 레시피를 쓰는 같은 층 무기 6종도 서로 다르게. 겹침 수는 --report / 생성 결과에 찍힌다)
개수는 그 층 1회 클리어 공급량(loot.yml 를 펼쳐 계산)에 맞춘다 — 자세한 근거는 생성된 파일 머리 주석.

결과는 장비마다 명시적인 항목으로 쓰므로 사장님이 아무 장비나 직접 고쳐도 된다 (다시 생성하면 덮어씀).

사용:
  python3 tools/gen_enhance.py                       # 저장소 content/ 로 계산해 enhance.yml 쓰기
  python3 tools/gen_enhance.py --content DIR         # 다른 content 폴더로 계산
  python3 tools/gen_enhance.py --spec loot_spec.json # 루팅 명세(new_items·assignments·tables·recipes)를 덮어 계산
  python3 tools/gen_enhance.py --report              # 층별 공급량 · 예상 클리어 수 표 · 겹침 수만 출력
  python3 tools/gen_enhance.py --check               # 쓰지 않고, 지금 파일과 같으면 종료 코드 0
"""
import argparse
import collections
import json
import math
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

# ───────────────────────── 재료 분류 ─────────────────────────
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
# 귀한 순서: 보스 핵 > 정예 재료 > 그 층 정수 > 윗 등급 정수 (같은 등급이면 1회 공급이 적은 쪽)
CLASS_RANK = {'core': 0, 'elite': 1, 'ess': 2, 'next': 3, 'common': 4}
CLASS_NAME = {'core': '보스 핵', 'elite': '정예 재료', 'ess': '정수', 'next': '윗 등급 정수', 'common': '일반 재료'}

# ───────────────────────── 개수 (시도 1번당, 목표 단계 순) ─────────────────────────
BANDS = {'low': (1, 3), 'mid': (4, 6), 'high': (7, 10)}
# 주 재료 P · 보조 S (일반 재료) — × 그 재료 공급 배율 (아래 p_scale). 무기는 한 벌에 하나라 조금 비싸게, 방어구는 4부위라 조금 싸게
# (흉갑·하의는 제작에도 더 들어 투구·신발보다 조금 더). 상승폭이 커져서(+10 ×2.0) high 의 +8~+10 은 예전보다 1개씩 많다.
P_BASE = {'weapon': {'low': [2, 2, 3], 'mid': [3, 3, 4], 'high': [4, 5, 6, 7]},
          'shield': {'low': [2, 3, 3], 'mid': [3, 4, 4], 'high': [4, 5, 6, 7]},
          'armor_body': {'low': [2, 2, 3], 'mid': [3, 3, 4], 'high': [4, 4, 5, 6]},
          'armor': {'low': [2, 2, 2], 'mid': [2, 3, 3], 'high': [3, 4, 5, 6]}}
S_BASE = {'weapon': {'mid': [2, 2, 3], 'high': [3, 3, 4, 5]},
          'shield': {'mid': [2, 2, 3], 'high': [3, 3, 4, 5]},
          'armor_body': {'mid': [2, 2, 2], 'high': [2, 3, 3, 4]},
          'armor': {'mid': [1, 2, 2], 'high': [2, 2, 3, 4]}}
# S 가 일반 재료가 아닐 때(레시피 두 번째 재료가 귀한 재료인 경우 — 지금 데이터엔 없음)
S_RARE = {'elite': {'mid': [1, 1, 2], 'high': [1, 1, 1, 2]}, 'ess': {'mid': [2, 2, 3], 'high': [2, 2, 3, 3]},
          'next': {'mid': [1, 1, 1], 'high': [1, 1, 1, 1]}, 'core': {'mid': [1, 1, 1], 'high': [1, 1, 1, 1]}}
# 귀한 재료 R (+7 ~ +10). 일반 장비 / 보스 장비(+7 · +8 만 — +9 · +10 은 핵이 대신)
R_COUNT = {'elite': [1, 1, 2, 2], 'ess': [2, 3, 3, 4], 'next': [1, 1, 1, 2], 'common': [3, 4, 5, 6]}
R_BOSS = {'elite': [1, 1, 0, 0], 'ess': [2, 3, 0, 0], 'next': [1, 1, 0, 0], 'common': [3, 4, 0, 0]}
K_COUNT = [0, 0, 1, 2]                                                # 보스 핵: +9 · +10 시도만 (근거는 머리 주석)
REF_SUPPLY = 40.0                                                     # 1~3층 일반 재료 1회 공급량 ≈ 기준 배율 1.0


def p_scale(supply):
    """일반 재료 공급이 많은 깊은 층은 개수도 늘린다 (0.25 단위, 1.0 ~ 2.0)."""
    return max(1.0, min(2.0, half_up(supply / REF_SUPPLY * 4) / 4))


def half_up(x):
    """.5 는 언제나 올림 (파이썬 round() 는 짝수 쪽으로 반올림해 ×1.25 · ×1.5 층 개수가 고르지 않게 뛴다: 4.5 → 4, 2.5 → 2)."""
    return int(x + 0.5)


# ───────────────────────── 콘텐츠 읽기 ─────────────────────────
def load_yaml(p):
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_content(content_dir, spec_path=None):
    c = {n: load_yaml(Path(content_dir) / f'{n}.yml') for n in ('items', 'loot', 'mobs', 'bosses', 'floors', 'recipes')}
    items = c['items'].get('items') or {}
    tables = c['loot'].get('tables') or {}
    recipes = c['recipes'].get('recipes') or {}
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
        recipes.update(spec.get('recipes') or {})
    return {'items': items, 'tables': tables, 'mobs': c['mobs'].get('mobs') or {}, 'bosses': c['bosses'].get('bosses') or {},
            'floors': c['floors'].get('floors') or {}, 'recipes': recipes}


def enhance_config():
    cfg = (load_yaml(RES / 'config.yml').get('enhance') or {})
    max_level = int(cfg.get('max_level', 10))
    chances = list(cfg.get('chances') or [1.0, 1.0, 1.0, 1.0, 0.90, 0.80, 0.65, 0.50, 0.35, 0.20])
    stone_counts = list(cfg.get('stone_counts') or [1, 1, 1, 1, 2, 2, 2, 3, 3, 4])
    stones = cfg.get('stones') or [{'item': 'lesser_enhance_stone', 'max_floor': 3}, {'item': 'greater_enhance_stone', 'max_floor': 7},
                                   {'item': 'supreme_enhance_stone', 'max_floor': 10}]
    bonus = list(cfg.get('stat_bonus') or [0.04, 0.08, 0.13, 0.19, 0.26, 0.35, 0.46, 0.60, 0.78, 1.00])
    at = lambda lst, t: lst[max(0, min(len(lst) - 1, t - 1))]
    return {'max': max_level, 'chance': [at(chances, t) for t in range(1, max_level + 1)],
            'stones': [at(stone_counts, t) for t in range(1, max_level + 1)], 'bonus': [at(bonus, t) for t in range(1, max_level + 1)],
            'down': int(cfg.get('downgrade_from', 7)), 'stone_items': sorted(stones, key=lambda s: s['max_floor'])}


# ───────────────────────── 루팅 펼치기 ─────────────────────────
def amount(a):
    if a is None:
        return 1.0
    if isinstance(a, list):
        return (a[0] + a[-1]) / 2
    return float(a)


def expect(tables, tid, depth=0):
    """테이블 1번 굴림의 아이템별 기대 개수 (하위 테이블 포함)."""
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


def floor_roots(f, fd, tables, mobs, bosses):
    """그 층 1회 클리어에서 굴리는 루팅 테이블 → [(테이블, 1회 횟수, 집)]. 집 = mob | elite | boss | chest."""
    roots = []
    normal = [m for m in (fd.get('mobs') or []) if m in mobs and mobs[m].get('drops')]
    for m in normal:
        roots.append((mobs[m]['drops'], MOBS_RUN.get(f, 40) / len(normal), 'mob'))
    rooms = fd.get('rooms') or {}
    if fd.get('elite') in mobs and mobs[fd['elite']].get('drops'):
        roots.append((mobs[fd['elite']]['drops'], rooms.get('elite', 1), 'elite'))
    if fd.get('boss') in bosses and bosses[fd['boss']].get('drops'):
        roots.append((bosses[fd['boss']]['drops'], 1, 'boss'))
    roots.append((f'treasure_floor_{f}', 3 * rooms.get('treasure', 1), 'chest'))
    roots.append((f'gimmick_floor_{f}', 1, 'chest'))
    br = 1 if f <= 3 else 2 if f <= 6 else 3 if f <= 9 else 4
    for tier, n in maze_chests(f).items():
        tid = f'maze_chest_{tier}_f{f}' if f'maze_chest_{tier}_f{f}' in tables else f'maze_chest_{tier}_{br}'
        roots.append((tid, n, 'chest'))
        if tier != 'wood':
            roots.append((f'maze_enhance_{tier}_t{stone_tier(f)}', n, 'enhance'))
    return [r for r in roots if r[0] in tables]


def supply_of(tables, roots):
    tot = collections.Counter()
    for tid, n, _ in roots:
        for k, v in expect(tables, tid).items():
            tot[k] += v * n
    return tot


def expand_items(tables, tid, seen=frozenset()):
    """테이블에서 나올 수 있는 아이템 id 전부 (하위 테이블 포함)."""
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
            s |= expand_items(tables, e['table'], seen | {tid})
    return s


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


# ───────────────────────── 층 재료 · 장비 집 ─────────────────────────
class Floor:
    """한 층의 재료 분류와 공급량."""

    def __init__(self, f, items, supply, roots, tables):
        self.f, self.supply, self.roots = f, supply, roots
        mats = [i for i, v in items.items() if v.get('type') == 'material' and v.get('floor') == f and i not in NOT_FLOOR_MATERIAL]
        self.cores = [i for i in mats if (items[i].get('sources') or []) == ['boss']]
        self.elites = [i for i in mats if i not in self.cores and items[i].get('rarity') == 'rare']
        self.commons = sorted([i for i in mats if i not in self.cores and i not in self.elites], key=lambda i: -supply[i])
        self.ess = max(ESS_ORDER, key=lambda e: supply[e])
        self.hard = HARD.get(f) if HARD.get(f) in self.commons else (self.commons[-1] if self.commons else None)
        self.soft = next((i for i in self.commons if i != self.hard), self.hard)
        self.boss_root = next((t for t, _, h in roots if h == 'boss'), None)
        boss_items = expand_items(tables, self.boss_root) if self.boss_root else set()
        self.core = next((c for c in self.cores if c in boss_items), self.cores[0] if self.cores else None)

    def cls(self, m):
        if m in self.cores:
            return 'core'
        if m in self.elites:
            return 'elite'
        if m in ESS_ORDER:
            return 'next' if ESS_ORDER.index(m) > ESS_ORDER.index(self.ess) else 'ess'
        return 'common'

    def rank(self, m):
        return (CLASS_RANK[self.cls(m)], self.supply.get(m, 0), m)


def gear_floor(v):
    if v.get('floor'):
        return int(v['floor'])
    return max(1, min(10, math.ceil(max(1, v.get('level_req', 1)) / 5.0)))


def kind_of(v):
    return v.get('weapon_type') or v.get('armor_slot') or 'sword_shield'


def category(v):
    if v.get('type') == 'weapon':
        return 'weapon'
    slot = v.get('armor_slot')
    return 'shield' if slot == 'offhand' else 'armor_body' if slot in ('chest', 'legs') else 'armor'


def refined_from(recipes):
    """정제 레시피: 결과 정수 → 재료 정수 (대장간 5:1)."""
    out = {}
    for r in recipes.values():
        res = r.get('result')
        mats = r.get('materials') or {}
        if res in ESS_ORDER and len(mats) == 1:
            out[res] = next(iter(mats))
    return out


def homes_of(i, v, fl, tables):
    """장비가 나오는 루팅 테이블 (그 층 루트 중 펼치면 그 장비가 있는 것). 시작 지급·칭호 보상은 정해진 곳."""
    src = set(v.get('sources') or [])
    found = [(t, n, h) for t, n, h in fl.roots if h != 'enhance' and i in expand_items(tables, t)]
    if found:
        return found, '·'.join(sorted({h for _, _, h in found}, key=['mob', 'chest', 'elite', 'boss'].index))
    if 'reward' in src and fl.boss_root:
        return [r for r in fl.roots if r[0] == fl.boss_root], 'reward'
    if 'starter' in src:
        return [r for r in fl.roots if r[2] in ('mob', 'chest')], 'starter'
    if 'craft' in src:
        return [], 'craft'  # 대장간에서만 — 드롭 집 없음 (레시피 재료와 그 정제 정수만)
    return [r for r in fl.roots if r[2] in ('mob', 'chest')], 'none'


def home_text(v, label):
    src = v.get('sources') or []
    parts = []
    if 'boss' in src:
        parts.append('보스 고유')
    if 'drop' in src or 'chest' in src:
        parts.append('몬스터·상자')
    if 'elite' in src:
        parts.append('정예')
    if 'starter' in src:
        parts.append('시작 지급')
    if 'reward' in src:
        parts.append('칭호 보상')
    if 'craft' in src:
        parts.append('대장간')
    return ' · '.join(parts) or '기타'


# ───────────────────────── 생성 ─────────────────────────
def band_counts(cat, role, cls, scale, bump, boss):
    """역할(P/S/R/K) · 재료 분류 → {low, mid, high} 개수 목록."""
    if role == 'P':
        return {b: [max(1, half_up(x * scale)) + bump for x in P_BASE[cat][b]] for b in BANDS}
    if role == 'S':
        if cls == 'common':
            return {b: [max(1, half_up(x * scale)) for x in S_BASE[cat][b]] for b in ('mid', 'high')}
        return dict(S_RARE.get(cls, S_RARE['ess']))
    if role == 'R':
        return {'high': list((R_BOSS if boss else R_COUNT).get(cls, R_COUNT['ess']))}
    return {'high': list(K_COUNT)}


def candidates(i, v, fl, tables, recipe, refine):
    """장비 하나의 (P, S) 후보 · R 후보 · 핵 · 설명."""
    homes, label = homes_of(i, v, fl, tables)
    home_sup = supply_of(tables, homes)
    home_mats = [m for m, n in home_sup.items() if n > 0 and m not in NOT_FLOOR_MATERIAL
                 and (m in fl.commons or m in fl.elites or m in fl.cores or m in ESS_ORDER)]
    src = set(v.get('sources') or [])
    boss = 'boss' in src or label == 'reward'
    kind = kind_of(v)
    if recipe:
        mats = list(recipe.items())
        order = sorted(range(len(mats)), key=lambda k: (-mats[k][1], k))  # 많이 드는 순 (같으면 레시피 순서)
        ranked = [mats[k][0] for k in order]
        bulk = ranked[:2]
        if len(bulk) < 2:
            bulk.append(next(m for m in fl.commons if m not in bulk))
        rest = [m for m in ranked[2:]]
        core = next((m for m in rest if fl.cls(m) == 'core'), None)
        if boss and not core:
            core = fl.core
        r_list = sorted([m for m in rest if m != core], key=fl.rank)
        how = 'recipe'
    else:
        commons = [m for m in fl.commons if m in home_mats] or list(fl.commons)
        hard = fl.hard if fl.hard in commons else commons[0]
        soft = next((m for m in commons if m != hard), hard)
        bulk = [hard, soft] if KIND_HARD.get(kind, True) else [soft, hard]
        core = fl.core if boss else None
        r_list = []
        how = 'drop'
    # 제작법이 없는 장비의 S = 그 장비가 나오는 곳이 같이 떨어뜨리는 정수 (정예 장비는 정예 재료) — 같은 층 제작 장비(S = 두 번째
    # 제작 재료)와 갈린다. 겹치면 정예 재료 / 정수 → 다른 일반 재료 순.
    ess_home = fl.ess if fl.ess in home_mats else max((m for m in home_mats if m in ESS_ORDER), key=lambda m: home_sup[m], default=None)
    elite_home = next((m for m in sorted(home_mats, key=fl.rank) if fl.cls(m) == 'elite'), None)
    if how == 'recipe':
        ps = [(bulk[0], bulk[1], ''), (bulk[1], bulk[0], 'swap')]
    else:
        alt = [m for m in ((elite_home, ess_home) if label == 'elite' else (ess_home, elite_home)) if m] + [bulk[1]]
        ps = [(bulk[0], m, '' if k == 0 else 'S') for k, m in enumerate(alt)] + [(bulk[1], m, 'swap') for m in alt if m != bulk[1]] \
            + [(bulk[1], bulk[0], 'swap')]
    # 레시피에 없으면 그 장비가 나오는 곳의 귀한 드롭 → 레시피·드롭 정수를 정제한 윗 등급 정수
    extra_home = sorted([m for m in home_mats if m not in bulk and m != core and m not in r_list and fl.cls(m) != 'common'
                         and fl.cls(m) != 'core'], key=fl.rank)
    r_all = r_list + extra_home
    # 정제는 한 등급 위까지만 (그 층 정수 → 윗 등급 정수). 이미 윗 등급인 정수는 더 올리지 않는다.
    refined = []
    for m in list(r_all):
        nxt = next((e for e, base in refine.items() if base == m), None)
        if nxt and fl.cls(m) == 'ess' and nxt not in r_all and nxt not in refined and fl.supply.get(m, 0) > 0:
            refined.append(nxt)
    r_all += refined
    if not r_all:
        r_all = [fl.ess]
    return {'bulk': bulk, 'ps': ps, 'R': r_all, 'R_recipe': r_list, 'R_home': extra_home, 'R_refined': refined, 'K': core,
            'boss': boss, 'how': how, 'label': label, 'kind': kind, 'cat': category(v), 'home_sup': home_sup}


def recipe_of(cand, fl, P, S, R, bump):
    cat, boss = cand['cat'], cand['boss']
    sc = lambda m: p_scale(fl.supply.get(m, REF_SUPPLY))
    pc = band_counts(cat, 'P', 'common', sc(P), bump, boss)
    sc_s = band_counts(cat, 'S', fl.cls(S), sc(S), 0, boss)
    r = {'low': {P: pc['low']}, 'mid': {P: pc['mid'], S: sc_s['mid']}, 'high': {P: pc['high'], S: sc_s['high']}}
    K = cand['K']
    if boss and K:
        if R and R != K:
            r['high'][R] = band_counts(cat, 'R', fl.cls(R), 1, 0, True)['high']
        r['high'][K] = list(K_COUNT)
    else:
        r['high'][R] = band_counts(cat, 'R', fl.cls(R), 1, 0, False)['high']
    return r


def signature(r):
    return json.dumps(r, sort_keys=True)


def build(c):
    items, tables, mobs, bosses, floors, recipes = c['items'], c['tables'], c['mobs'], c['bosses'], c['floors'], c['recipes']
    fls = {}
    for f, fd in floors.items():
        f = int(f)
        roots = floor_roots(f, fd, tables, mobs, bosses)
        fls[f] = Floor(f, items, supply_of(tables, roots), roots, tables)
    refine = refined_from(recipes)
    by_result = {}
    for r in recipes.values():
        if r.get('result') in items and items[r['result']].get('type') in ('weapon', 'armor'):
            by_result.setdefault(r['result'], r.get('materials') or {})
    gear = [i for i, v in items.items() if v.get('type') in ('weapon', 'armor')]
    out, meta = {}, {}
    used = collections.defaultdict(dict)  # 층 → 서명 → 장비
    collisions = []

    def order_key(i):
        v = items[i]
        cand = cands[i]
        # 레시피 장비 먼저(원칙 그대로 받을 차례), 종류에 맞는 재료가 주 재료인 장비 먼저 → 어긋나는 장비가 순서 바꿈을 받는다
        affinity = fls[gear_floor(v)].hard if KIND_HARD.get(cand['kind'], True) else fls[gear_floor(v)].soft
        return (gear_floor(v), 0 if cand['how'] == 'recipe' else 1, 0 if cand['bulk'][0] == affinity else 1,
                KIND_ORDER.index(cand['kind']) if cand['kind'] in KIND_ORDER else 99, v.get('level_req', 1),
                RARITY_ORDER.index(v.get('rarity')) if v.get('rarity') in RARITY_ORDER else 0, i)

    cands = {}
    for i in gear:
        fl = fls.get(gear_floor(items[i])) or fls[min(fls, key=lambda x: abs(x - gear_floor(items[i])))]
        cands[i] = candidates(i, items[i], fl, tables, by_result.get(i), refine)
    for i in sorted(gear, key=order_key):
        v = items[i]
        f = gear_floor(v)
        fl = fls.get(f) or fls[min(fls, key=lambda x: abs(x - f))]
        cand = cands[i]
        variants = []
        for bump in range(0, 4):
            for (P, S, tag) in cand['ps']:
                for R in cand['R']:
                    # S 정수를 정제한 윗 정수는 R 로 쓰지 않는다 (같은 정수를 두 번 걷어 가서 +10 이 너무 길어짐)
                    if R not in (P, S) and refine.get(R) != S:
                        variants.append((P, S, R, tag, bump))
        if not variants:
            raise SystemExit(f'{i}: 고를 수 있는 귀한 재료(R)가 없다 — 후보 {cand}')
        chosen = None
        for (P, S, R, tag, bump) in variants:
            r = recipe_of(cand, fl, P, S, R, bump)
            if signature(r) not in used[f]:
                chosen = (P, S, R, tag, bump, r)
                break
        if chosen is None:
            P, S, R, tag, bump = variants[0]
            chosen = (P, S, R, tag, bump, recipe_of(cand, fl, P, S, R, bump))
            collisions.append((i, used[f][signature(chosen[5])]))
        P, S, R, tag, bump, r = chosen
        used[f].setdefault(signature(r), i)
        out[i] = r
        first_r = next(x for x in cand['R'] if x not in (P, S) and refine.get(x) != S)
        meta[i] = dict(cand, floor=f, P=P, S=S, Rm=R, swapped=(tag == 'swap'), s_alt=(tag == 'S'), bump=bump,
                       canonical=(tag == '' and bump == 0 and R == first_r), r_rot=(R != first_r))
    return out, meta, fls, collisions


def costs_for(recipe, target):
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
        for m, c in costs_for(recipe, t).items():
            tot[m] += n * c
        tot[st] += n * cfg['stones'][t - 1]
    return tot


def runs_needed(need, sup, refine=None, ignore=()):
    """need 를 모으는 데 드는 클리어 수 (가장 모자란 재료 기준). 윗 정수는 아래 정수를 5:1 로 정제해 채울 수 있다."""
    worst, which = 0.0, None
    for m, n in need.items():
        if m in ignore or n <= 0:
            continue
        base = (refine or {}).get(m)
        if base and sup.get(base, 0) > 0:
            r = (n + need.get(base, 0) / 5) / (sup.get(m, 0) + sup.get(base, 0) / 5)
        else:
            s = sup.get(m, 0)
            r = n / s if s > 0 else float('inf')
        if r > worst:
            worst, which = r, m
    return worst, which


def obtainable_problems(items, recipes_out, meta, fls, refine):
    """참조한 재료가 모두 있고, 그 장비 층에서 얻을 수 있는가 (그 층 드롭 또는 그 층 정수를 정제)."""
    bad = []
    for i, r in recipes_out.items():
        fl = fls[meta[i]['floor']]
        for b in r.values():
            for m in b:
                if m not in items or items[m].get('type') != 'material':
                    bad.append(f'{i}: 없는 재료 {m}')
                elif fl.supply.get(m, 0) <= 0 and not (refine.get(m) and fl.supply.get(refine[m], 0) > 0):
                    bad.append(f'{i}: {m} 는 {fl.f}층에서 얻을 수 없음')
    return bad


# ───────────────────────── 출력 ─────────────────────────
def fmt_counts(c):
    return '[' + ', '.join(str(x) for x in c) + ']'


def name(items, i):
    return (items.get(i) or {}).get('name', i)


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


def report_rows(cfg, items, recipes_out, meta, fls, refine):
    rows = []
    for f in sorted(fls):
        sup = fls[f].supply
        st = stone_for(cfg, f)
        kit = kit_for_floor(items, meta, f)
        kit5 = collections.Counter()
        for i in kit:
            kit5.update(needs(cfg, recipes_out[i], f, 5))
        one5 = [runs_needed(needs(cfg, recipes_out[i], f, 5), sup, refine)[0] for i in kit]
        ten = collections.defaultdict(list)
        for i, m in meta.items():
            if m['floor'] != f:
                continue
            key = 'boss' if m['boss'] and m['K'] else fls[f].cls(m['Rm'])
            need = needs(cfg, recipes_out[i], f, 10)
            r, which = runs_needed(need, sup, refine, ignore=(st,))
            ten[key].append((r, which))
        need10 = needs(cfg, recipes_out[kit[0]], f, 10) if kit else collections.Counter()
        stone10, _ = runs_needed({st: need10[st]}, sup)
        k5, k5w = runs_needed(kit5, sup, refine)
        rows.append({'floor': f, 'kit': kit, 'kit5': (k5, k5w), 'one5': max(one5) if one5 else 0, 'ten': ten, 'stone10': stone10})
    return rows


def write_yaml(cfg, items, recipes_out, meta, fls, rows, collisions, source_note):
    att10 = attempts(cfg, 10)
    att10p = attempts(cfg, 10, protect=True)
    att5 = attempts(cfg, 5)
    n_recipe = sum(1 for m in meta.values() if m['how'] == 'recipe')
    n_drop = len(meta) - n_recipe
    n_canon = sum(1 for m in meta.values() if m['canonical'])
    n_swap = sum(1 for m in meta.values() if m['swapped'] and not m['bump'])
    n_salt = sum(1 for m in meta.values() if m['s_alt'] and not m['bump'])
    n_bump = sum(1 for m in meta.values() if m['bump'])
    n_rrot = len(meta) - n_canon - n_swap - n_salt - n_bump
    k10 = sum(att10[t] * K_COUNT[min(len(K_COUNT) - 1, t - 7)] for t in range(7, 11))
    L = []
    w = L.append
    w('# ─────────────────────────────────────────────────────────────────────────────')
    w('# enhance.yml — 장비별 강화 재료 (GDD §11.13). tools/gen_enhance.py 가 만든 파일 — 손으로 고쳐도 된다.')
    w('#')
    w('# 강화 한 번 비용 = 골드 + 강화석(config.yml enhance: — 장비 층 구간별 1종, 모든 장비 공용) + 아래 그 장비만의 재료.')
    w('# 실패해도 셋 다 사라진다 (보호 주문서는 하락만 막는다). 가방에 전부 있어야 시작하고, 하나라도 모자라면 아무것도 안 가져간다.')
    w('#')
    w('# 형식: <장비 id>: {low: {재료: 개수}, mid: {...}, high: {...}}   — 구간은 아래 bands (목표 단계 기준).')
    w('#   개수 = 숫자 하나(구간 전체 같은 개수) 또는 목록(구간 안 목표 단계 순: low [+1, +2, +3]). 모자란 목록은 마지막 값, 0 = 그 단계엔 필요 없음.')
    w('#   재료 순서 = 강화 창 표시 순서이고, 툴팁에는 첫 재료만 보인다. 여기 없는 장비(새로 넣은 장비)는 강화석·골드만 든다(시작 때 경고).')
    w('#   없는 재료 id 는 시작 때 경고하고 그 줄만 무시한다.')
    w('#')
    w('# ── 재료를 고르는 규칙 — "그 장비를 얻는 곳에서 강화 재료도 얻는다" ─────────────────')
    w('#   ① 제작법이 있는 장비 (recipes.yml 결과 = 그 장비) → 그 제작 재료로 강화한다.')
    w('#      low  (+1~+3) : 주 재료 P = 레시피에서 가장 많이 드는 재료')
    w('#      mid  (+4~+6) : P + 보조 S = 레시피의 두 번째 재료')
    w('#      high (+7~+10): P + S + 귀한 재료 R = 레시피에서 가장 귀한 재료 (보스 핵 > 정예 재료 > 정수)')
    w('#                     보스 핵이 든 레시피는 핵을 +9·+10 시도에만, +7·+8 에는 핵 다음으로 귀한 재료를 쓴다 —')
    w('#                     시도 1번당 재료는 언제나 3종이라 보스 장비가 같은 층 일반 장비보다 싼 단계가 없다.')
    w('#      레시피가 일반 재료 2종뿐이면 R 은 그 장비가 나오는 곳(정예·몬스터·상자)의 귀한 드롭.')
    w('#   ② 제작법이 없는 장비 → 그 장비를 떨어뜨리는 곳의 드롭 재료로 강화한다.')
    w('#      low = 그 층 일반 재료 중 장비 종류에 맞는 쪽 (검방·대검·단검·흉갑·신발 = 단단한 재료, 활·지팡이·홀·투구·하의 = 부드러운 재료)')
    w('#      mid = + 그 장비가 나오는 곳이 같이 떨어뜨리는 정수 (정예 장비는 정예 재료) — 같은 층 제작 장비와 구성이 갈린다')
    w('#      high = + 나오는 곳의 귀한 드롭 (정예 재료 > 윗 등급 정수). 보스 고유는 +7·+8 에 귀한 드롭, +9·+10 에 그 보스의 핵.')
    w('#      집: 층 공용 무기 = 그 층 몬스터·상자 · 정예 장비 = 그 정예 · 보스 고유 = 그 보스 ·')
    w('#          시작 지급(수련생) = 1층 몬스터·상자 · 칭호 보상(악몽의 왕관) = 그 칭호를 주는 10층 보스 (핵 포함)')
    w('#   ③ 같은 층에 재료 구성(개수까지)이 똑같은 장비가 생기면 차례로 바꾼다:')
    w('#      R 을 그 장비의 다른 귀한 재료로 → 나오는 곳의 귀한 드롭 → 레시피·드롭 정수를 대장간에서 정제한 윗 등급 정수')
    w('#      → (드롭 재료 장비) S 를 정예 재료·다른 일반 재료로 → P·S 순서 바꿈 → 마지막으로 P 개수 +1.')
    w('#      (같은 레시피를 쓰는 같은 층 무기 6종도 서로 다르다. 귀한 재료가 2종뿐인 9·10층만 몇 개가 P +1)')
    w(f'#   결과: 장비 {len(meta)}종 (제작 재료 {n_recipe} · 드롭 재료 {n_drop}) — 원칙 그대로 {n_canon}종 · R 바꿈 {n_rrot}종 ·'
      f' S 바꿈 {n_salt}종 · P·S 순서 바꿈 {n_swap}종 · P +1 {n_bump}종. 같은 층에서 구성이 똑같은 장비 {len(collisions)}쌍.')
    w('#   강화석(하급·상급·최상급)은 그대로 모든 장비에 공용으로 든다 — 장비 재료는 그 위에 더하는 몫.')
    w('#')
    w('# ── 개수 (시도 1번당) ─────────────────────────────────────────────────────────')
    fb = lambda cat, bands=BANDS: ' · '.join(fmt_counts(P_BASE[cat][b]) for b in bands)
    fs = lambda cat: fmt_counts(S_BASE[cat]['mid']) + ' · ' + fmt_counts(S_BASE[cat]['high'])
    w('#   P (일반 재료, low · mid · high)  무기 ' + fb('weapon') + ' | 방패 ' + fb('shield'))
    w('#                                    흉갑·하의 ' + fb('armor_body') + ' | 투구·신발 ' + fb('armor'))
    w('#   S (mid · high)  일반 재료: 무기·방패 ' + fs('weapon') + ' | 흉갑·하의 ' + fs('armor_body') + ' | 투구·신발 ' + fs('armor'))
    w('#                   정수: ' + fmt_counts(S_RARE['ess']['mid']) + ' · ' + fmt_counts(S_RARE['ess']['high'])
      + ' | 정예 재료: ' + fmt_counts(S_RARE['elite']['mid']) + ' · ' + fmt_counts(S_RARE['elite']['high']) + '  (드롭 재료 장비)')
    w('#                   일반 재료 P·S 는 그 재료 1회 공급량 ÷ 40 (0.25 단위, ×1.0 ~ ×2.0) 을 곱하고 .5 는 올린다 — 깊은 층일수록 많이 떨어지고 많이 든다.')
    w('#   R (+7~+10)      정예 재료 ' + fmt_counts(R_COUNT['elite']) + ' · 정수 ' + fmt_counts(R_COUNT['ess'])
      + ' · 윗 등급 정수 ' + fmt_counts(R_COUNT['next']) + '   (보스 장비는 +7·+8 만: 정예 ' + fmt_counts(R_BOSS['elite'])
      + ' · 정수 ' + fmt_counts(R_BOSS['ess']) + ')')
    w('#   보스 핵 K       ' + fmt_counts(K_COUNT) + ' (+9·+10 시도만)   — 상승폭이 커져(+10 ×' + f"{1 + cfg['bonus'][-1]:.2f}".rstrip('0').rstrip('.')
      + ') +8~+10 개수를 예전보다 조금 올렸다.')
    w('#')
    w('# ── 근거: 1회 클리어 공급량 (보통·솔로·1인, LUK 0 — loot.yml 을 펼쳐 계산) ──────────')
    w('#   가정: 몹 수 GDD §16.1 (1층 24 … 10층 60), 미로 상자 나무 4~6 · 철 2~3 · 금 3~4, 보물방 상자 3개 × 방 수, 기믹방 1, 정예 1~2, 보스 1.')
    w(f'#   계산한 콘텐츠: {source_note}')
    for f in sorted(fls):
        fl = fls[f]
        s = fl.supply
        nxt = ESS_ORDER[ESS_ORDER.index(fl.ess) + 1] if ESS_ORDER.index(fl.ess) + 1 < len(ESS_ORDER) else None
        w(f"#   {f:>2}층  {name(items, fl.hard)} {s[fl.hard]:.0f} · {name(items, fl.soft)} {s[fl.soft]:.0f}"
          + ''.join(f"  | 정예 {name(items, e)} {s[e]:.1f}" for e in fl.elites)
          + f"  | 정수 {name(items, fl.ess)} {s[fl.ess]:.1f}" + (f" · 윗 정수 {s[nxt]:.1f}" if nxt else '')
          + (f"  | 핵 {name(items, fl.core)} {s[fl.core]:.0f}" if fl.core else ''))
    w('#   (정수는 대장간에서 5:1 로 윗 등급으로 정제할 수 있다. 일반 재료는 대장간 제작에도 10~24개씩 든다.)')
    w('#')
    w('# ── 근거: 시도 수 (config chances · downgrade_from 그대로, 정확한 기대값) ─────────')
    w('#   +5 까지 ' + ' + '.join(f'{att5[t]:.2f}' for t in sorted(att5)) + f' = {sum(att5.values()):.1f}회 (하락 없음)')
    w('#   +10 까지 (주문서 없이) ' + ' · '.join(f'+{t} {att10[t]:.1f}' for t in range(7, 11)) + f'  합 {sum(att10.values()):.1f}회 — 대부분 +7·+8 하락 고리')
    w(f'#   +10 까지 (하락을 전부 주문서로 막으면) {sum(att10p.values()):.1f}회 · 주문서 {sum(att10p[t] * (1 - cfg["chance"][t - 1]) for t in att10p if t - 1 >= cfg["down"]):.1f}장')
    w(f'#   보스 핵을 high 모든 시도에 넣으면 +10 까지 핵 {sum(att10[t] for t in range(7, 11)):.0f}개(= 그 보스 {sum(att10[t] for t in range(7, 11)):.0f}번) — 너무 많아서'
      f' +9·+10 시도에만 넣는다 (+10 까지 핵 {k10:.0f}개). 대신 +7·+8 에는 핵 다음으로 귀한 재료.')
    w('#')
    w('# ── 결과: 예상 클리어 수 (그 층만 돌고, 그 재료를 강화에만 쓸 때) ─────────────────')
    w('#   층  | 장비 1개 +5 | 대표 한 벌(무기+방어구 4+방패) +5 (병목) | +10 장비 1개 — R 종류별 (병목 재료) / 강화석')
    label = {'elite': '정예 재료', 'ess': '정수', 'next': '윗 정수', 'common': '일반', 'boss': '보스 장비'}
    for r in rows:
        parts = []
        for key in ('elite', 'ess', 'next', 'common', 'boss'):
            if r['ten'].get(key):
                vals = sorted(x for x, _ in r['ten'][key])
                lo, hi = vals[0], vals[-1]
                which = max(r['ten'][key])[1]
                rng = f'{lo:.0f}' if round(lo) == round(hi) else f'{lo:.0f}~{hi:.0f}'
                parts.append(f'{label[key]} {rng}회({name(items, which)})')
        w(f"#   {r['floor']:>2}층 | {r['one5']:.1f}회 | {r['kit5'][0]:.1f}회 ({name(items, r['kit5'][1])}) | " + ' · '.join(parts)
          + f" / 강화석 {r['stone10']:.0f}회")
    w('#   → +5 는 장비 하나가 1회 안팎, 한 벌이 1~6층 3~4회 · 7~10층 2~3회 (강화석이 병목 — mid 까지는 제작 재료라 제작과 같이 모인다).')
    w('#   → +10 은 장기 목표: 일반 장비 13~26회, 보스 장비는 핵 때문에 그 보스 24회 안팎 (보호 주문서를 쓰면 크게 준다).')
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
    order = sorted(recipes_out, key=lambda i: (meta[i]['floor'], KIND_ORDER.index(meta[i]['kind']) if meta[i]['kind'] in KIND_ORDER else 99,
                                              meta[i]['boss'], items[i].get('level_req', 1), i))
    last_floor = None
    for i in order:
        m = meta[i]
        f = m['floor']
        if f != last_floor:
            fl = fls[f]
            w('')
            w(f"  # ════ 지하 {f}층 — 일반 {name(items, fl.hard)} · {name(items, fl.soft)}"
              + ''.join(f" · 정예 {name(items, e)}" for e in fl.elites) + f" · 정수 {name(items, fl.ess)}"
              + (f" · 핵 {name(items, fl.core)}" if fl.core else '') + ' ════')
            last_floor = f
        v = items[i]
        why = '제작 재료' if m['how'] == 'recipe' else {'mob·chest': '몬스터·상자 드롭', 'mob': '몬스터 드롭', 'chest': '상자 드롭',
                                                        'elite': '정예 드롭', 'boss': '보스 드롭', 'reward': '칭호를 주는 보스 드롭',
                                                        'starter': '1층 몬스터·상자 드롭'}.get(m['label'], '드롭 재료')
        if m['how'] == 'recipe' and m['Rm'] in m['R_home']:
            why += ' + 나오는 곳 드롭'
        if m['Rm'] in m['R_refined']:
            why += ' + 정제 정수'
        notes = []
        if m['r_rot']:
            notes.append('R 바꿈')
        if m['s_alt']:
            notes.append('S 바꿈')
        if m['swapped']:
            notes.append('P·S 바꿈')
        if m['bump']:
            notes.append(f"P +{m['bump']}")
        w(f"  {i}:  # {v.get('name', i)} · {KIND_NAME.get(m['kind'], m['kind'])} · {home_text(v, m['label'])} → {why}"
          + (f" ({', '.join(notes)} — 겹침 피함)" if notes else ''))
        r = recipes_out[i]
        for b in ('low', 'mid', 'high'):
            body = ', '.join(f'{k}: {fmt_counts(c)}' for k, c in r[b].items())
            w(f'    {b}:{" " * (5 - len(b))}{{{body}}}')
    w('')
    return '\n'.join(L)


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
    c = load_content(a.content, a.spec)
    items = c['items']
    recipes_out, meta, fls, collisions = build(c)
    refine = refined_from(c['recipes'])
    rows = report_rows(cfg, items, recipes_out, meta, fls, refine)
    problems = obtainable_problems(items, recipes_out, meta, fls, refine)
    note = a.note or (f'content/ — 장비 {len(recipes_out)}종 · 레시피 {len(c["recipes"])}개 · 루팅 테이블 {len(c["tables"])}개'
                      + (' + 루팅 명세 ' + Path(a.spec).name if a.spec else ''))
    text = write_yaml(cfg, items, recipes_out, meta, fls, rows, collisions, note)
    summary = (f'장비 {len(recipes_out)}개 · 같은 층 똑같은 구성 {len(collisions)}쌍 {collisions[:5]}'
               f" · 원칙 그대로 {sum(1 for m in meta.values() if m['canonical'])} · P·S 바꿈 {sum(1 for m in meta.values() if m['swapped'])}"
               f" · 개수 +1 {sum(1 for m in meta.values() if m['bump'])} · 재료 문제 {len(problems)}")
    if problems:
        print('재료 문제:', *problems, sep='\n  ', file=sys.stderr)
    if a.report:
        print('\n'.join(l for l in text.splitlines() if l.startswith('#')))
        print(summary)
        return 0
    if a.check:
        cur = Path(a.out).read_text(encoding='utf-8') if Path(a.out).exists() else ''
        same = cur == text
        print('같음' if same else '다름 — python3 tools/gen_enhance.py 로 다시 만드세요')
        return 0 if same and not problems else 1
    Path(a.out).write_text(text, encoding='utf-8')
    print(f'{a.out}: {summary}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
