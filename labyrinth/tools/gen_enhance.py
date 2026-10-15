#!/usr/bin/env python3
"""장비별 강화 재료 생성기 → plugin/src/main/resources/content/enhance.yml (GDD §11.13).

강화 비용 = 골드 + 강화석(config.yml enhance: — 층 구간별 1종, 공용) + **그 장비만의 재료**(이 파일이 만드는 enhance.yml).
장비 재료는 '그 장비를 얻는 곳'과 이어진다:
  · 제작법이 있는 장비(recipes.yml 결과 = 장비) → 그 제작 재료
      low  (+1 ~ +3) : 주 재료 P   = 레시피에서 가장 많이 드는 재료
      mid  (+4 ~ +6) : P + 보조 S  = 레시피의 두 번째 재료
      high (+7 ~ +10): P + S + 귀한 재료 R = 레시피에서 가장 귀한 재료 (정예 재료 > 정수)
      레시피에 귀한 재료가 없으면(일반 재료 2종짜리) 그 장비가 나오는 곳(몬스터·정예·보스·상자)의 귀한 드롭.
  · 제작법이 없는 장비 → 그 장비를 주는 루팅 테이블(그 층 몬스터·상자 / 보스)이 떨어뜨리는 재료
      low = 장비 종류에 맞는 그 층 일반 재료 (근접 날붙이·흉갑·신발 = 단단한 재료, 활·마법 무기·투구·하의 = 부드러운 재료)
      mid = + 나오는 곳이 같이 주는 다른 일반 재료 · high = + 나오는 곳의 귀한 드롭 (정예 재료 > 정수)
      보스 고유 = 그 보스 드롭 · 층 공용 무기 = 그 층 몬스터·상자 드롭
      시작 지급 = 1층 몬스터·상자 드롭 · 칭호 보상 = 그 층 보스 드롭(핵 포함) · 대장간 전용 = 레시피 재료와 그 정제 정수만
  → mid 까지는 어느 장비든 일반 재료 2종. 정수·정예 재료는 high 의 R 에만 둔다.
  · 보스 장비(보스 고유 · 보스가 주는 칭호 보상): +7·+8 의 R 은 정예 재료만 (레시피의 정예 재료, 없으면 그 보스 드롭의 정예 재료),
    +9·+10 은 R 대신 그 보스의 핵. 그리고 단계마다 같은 층·같은 분류(무기 / 방패 / 흉갑·하의 / 투구·신발) 일반 장비 중 가장 비싼
    것보다 싸지 않게(1회 공급량 환산) P·S 개수를 가장 적게 더한다 — 일반 장비를 먼저 다 정한 뒤 보스 장비를 정한다.
같은 층에서 재료 구성(개수까지)이 똑같은 장비가 생기면, 원칙에서 덜 벗어나는 것부터:
  1단계 원칙 재료 그대로 — R 을 같은 원칙 안의 다른 귀한 재료로(환산해 싼 쪽부터) → P·S 순서 바꿈 → S +1 → S +2 → P +1 …
  2단계 (1단계로 안 될 때만) 레시피 밖 = 나오는 곳의 다른 귀한 드롭·윗 등급 정수 → 3단계 그 정수를 정제한 윗 등급 정수
  (일반 장비는 낮은 레벨·등급부터 원칙 그대로 받는다. 겹침 수 · 보스 장비 검사는 --report / 생성 결과에 찍힌다)
개수는 그 층 1회 클리어 공급량(loot.yml 를 펼쳐 계산)에 맞춘다 — 자세한 근거는 생성된 파일 머리 주석.

결과는 장비마다 명시적인 항목으로 쓰므로 사장님이 아무 장비나 직접 고쳐도 된다 (다시 생성하면 덮어씀).

사용:
  python3 tools/gen_enhance.py                       # 저장소 content/ 로 계산해 enhance.yml 쓰기
  python3 tools/gen_enhance.py --content DIR         # 다른 content 폴더로 계산
  python3 tools/gen_enhance.py --spec loot_spec.json # 루팅 명세(new_items·assignments·tables·recipes)를 덮어 계산
  python3 tools/gen_enhance.py --report              # 층별 공급량 · 예상 클리어 수 표 · 보스 장비 검사 · 겹침 수만 출력
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
R_BOSS = {'elite': [1, 2, 0, 0]}                                      # 보스 장비 +7·+8 = 정예 재료만 (정수로 내려가지 않음)
#   +8 이 2개인 것은 일반 장비 +8 의 정수 3개(환산하면 정예 재료 1개보다 조금 비쌈)보다 싸지 않게
K_COUNT = [0, 0, 1, 2]                                                # 보스 핵: +9 · +10 시도만 (근거는 머리 주석)
REF_SUPPLY = 40.0                                                     # 1~3층 일반 재료 1회 공급량 ≈ 기준 배율 1.0
# 겹침을 피할 때 더하는 개수 (P +dp, S +ds). 일반 장비는 S 먼저 — S 는 mid·high 7단계에만 들어 P +1 보다 싸고, low(+1~+3)는 그대로.
# 단계(원칙 R → 나오는 곳 드롭 → 정제 정수)마다 STAGE_BUMPS 를 다 써 본 뒤에야 다음 단계, 그래도 겹치면 MORE_BUMPS.
STAGE_BUMPS = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
MORE_BUMPS = [(2, 0), (2, 1), (2, 2), (0, 3), (1, 3), (2, 3), (3, 0), (3, 1), (3, 2), (3, 3)]
# 보스 장비: 같은 층·같은 분류 일반 장비 중 가장 비싼 것보다 싸지 않은(1회 공급량 환산, 모든 단계) 가장 작은 개수 더하기
BOSS_BUMPS = sorted([(dp, ds) for dp in range(5) for ds in range(5)], key=lambda b: (b[0] + b[1], b[0]))
# 등급 (보스 장비 ≥ 같은 층·같은 분류 일반 장비 검사): 일반 < 정수 < 정예 < 핵
GRADE = {'common': 0, 'ess': 1, 'next': 1, 'elite': 2, 'core': 3}
GRADE_NAME = ['일반', '정수', '정예', '핵']
GROUP = {'weapon': '무기', 'shield': '방패', 'armor_body': '흉갑·하의', 'armor': '투구·신발'}


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
    """역할(P/S/R/K) · 재료 분류 → {low, mid, high} 개수 목록. bump = 겹침을 피하려고 더하는 개수."""
    if role == 'P':
        return {b: [max(1, half_up(x * scale)) + bump for x in P_BASE[cat][b]] for b in BANDS}
    if role == 'S':
        if cls == 'common':
            return {b: [max(1, half_up(x * scale)) + bump for x in S_BASE[cat][b]] for b in ('mid', 'high')}
        return {b: [x + bump for x in c] for b, c in S_RARE.get(cls, S_RARE['ess']).items()}
    if role == 'R':
        if boss and cls not in R_BOSS:
            raise SystemExit(f'보스 장비의 +7·+8 귀한 재료는 정예 재료만 — {cls}')
        return {'high': list((R_BOSS if boss else R_COUNT).get(cls, R_COUNT['ess']))}
    return {'high': list(K_COUNT)}


def candidates(i, v, fl, tables, recipe, refine):
    """장비 하나의 (P, S) 후보 · R 후보(단계 A·B·C) · 핵 · 설명.

    P·S 는 언제나 그 층 일반 재료 2종 (제작 장비 = 레시피에서 가장 많이 드는 두 재료, 드롭 장비 = 나오는 곳이 같이 주는 두 일반 재료).
    R 단계  A = 원칙: 레시피의 귀한 재료 (레시피가 일반 재료뿐이거나 제작법이 없으면 나오는 곳의 귀한 드롭)
            B = 레시피 밖: 나오는 곳의 다른 귀한 드롭 (A 가 레시피 재료일 때만)
            C = 레시피 밖: A·B 의 정수를 대장간에서 한 등급 정제한 윗 등급 정수
    보스 장비(보스 고유·칭호 보상)의 R 은 정예 재료만 — 레시피의 정예 재료, 없으면 그 보스 드롭의 정예 재료 (B·C 없음).
    """
    homes, label = homes_of(i, v, fl, tables)
    home_sup = supply_of(tables, homes)
    home_mats = [m for m, n in home_sup.items() if n > 0 and m not in NOT_FLOOR_MATERIAL
                 and (m in fl.commons or m in fl.elites or m in fl.cores or m in ESS_ORDER)]
    src = set(v.get('sources') or [])
    boss = 'boss' in src or label == 'reward'
    kind = kind_of(v)
    rare = lambda ms: sorted({m for m in ms if fl.cls(m) in ('elite', 'ess', 'next')}, key=fl.rank)
    home_rare = rare(home_mats)
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
        recipe_rare = rare(m for m in rest if m != core)
        how = 'recipe'
    else:
        commons = [m for m in fl.commons if m in home_mats] or list(fl.commons)
        hard = fl.hard if fl.hard in commons else commons[0]
        soft = next((m for m in commons if m != hard), hard)
        bulk = [hard, soft] if KIND_HARD.get(kind, True) else [soft, hard]
        core = fl.core if boss else None
        recipe_rare = []
        how = 'drop'
    # P·S 는 둘 다 일반 재료 — 정수·정예 재료는 high 의 R 에만 (드롭 장비의 mid 가 제작 장비·보스 장비보다 귀해지지 않게)
    ps = [(bulk[0], bulk[1], ''), (bulk[1], bulk[0], 'swap')]
    if boss:
        elite_recipe = [m for m in recipe_rare if fl.cls(m) == 'elite']
        elite_home = [m for m in home_rare if fl.cls(m) == 'elite']
        tier_a = elite_recipe or elite_home
        tier_b = [m for m in elite_home if m not in tier_a]
        tier_c = []
        if not tier_a:
            raise SystemExit(f'{i}: 보스 장비인데 레시피에도 나오는 곳(보스 드롭)에도 정예 재료가 없다 — {home_rare}')
    else:
        # 윗 등급 정수(그 층보다 한 단계 위, 1회 0.6개 안팎)는 원칙 R 이 아니다 — 겹칠 때 B 에서만 (환산하면 가장 비싼 R 이라
        # 낮은 장비가 보스 장비보다 비싸지지 않게)
        own = [m for m in home_rare if fl.cls(m) != 'next']
        tier_a = recipe_rare or own
        tier_b = [m for m in home_rare if m not in tier_a]
        # 정제는 한 등급 위까지만 (그 층 정수 → 윗 등급 정수). 이미 윗 등급인 정수는 더 올리지 않는다.
        tier_c = []
        for m in tier_a + tier_b:
            nxt = next((e for e, base in refine.items() if base == m), None)
            if nxt and fl.cls(m) == 'ess' and nxt not in tier_a + tier_b + tier_c and fl.supply.get(m, 0) > 0:
                tier_c.append(nxt)
        if not (tier_a or tier_b or tier_c):
            tier_a = [fl.ess]
    # 겹칠 때 바꿔 쓸 R 은 1회 공급량으로 환산해 싼 것부터 (정수 < 정예 재료 < 윗 등급 정수) — 원칙 R(A 의 첫째)은 그대로
    r_cost = lambda m: sum((R_BOSS if boss else R_COUNT).get(fl.cls(m), R_COUNT['ess'])) / max(1e-9, eff_supply(fl, refine, m))
    tier_a = tier_a[:1] + sorted(tier_a[1:], key=r_cost)
    tier_b, tier_c = sorted(tier_b, key=r_cost), sorted(tier_c, key=r_cost)
    return {'bulk': bulk, 'ps': ps, 'RA': tier_a, 'RB': tier_b, 'RC': tier_c, 'R_recipe': recipe_rare, 'R_home': home_rare,
            'K': core, 'boss': boss, 'how': how, 'label': label, 'kind': kind, 'cat': category(v), 'home_sup': home_sup}


def recipe_of(cand, fl, P, S, R, dp=0, ds=0):
    cat, boss = cand['cat'], cand['boss']
    sc = lambda m: p_scale(fl.supply.get(m, REF_SUPPLY))
    pc = band_counts(cat, 'P', 'common', sc(P), dp, boss)
    sc_s = band_counts(cat, 'S', fl.cls(S), sc(S), ds, boss)
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


def build(c, cfg):
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
    collisions, unfair = [], []

    def order_key(i):
        v = items[i]
        cand = cands[i]
        # 일반 장비 먼저(모든 층), 보스 장비는 그 뒤 — 보스 장비는 핵이 들어 보스 장비끼리만 겹칠 수 있고, 같은 층·같은 분류 일반 장비가
        # 정해진 뒤에야 그보다 싸지 않은 개수를 고를 수 있다. 일반 장비는 낮은 레벨·등급부터 — 겹침을 피하는 변형은 높은 장비가 받는다.
        # 같으면 레시피 장비 먼저(원칙 그대로 받을 차례), 종류에 맞는 재료가 주 재료인 장비 먼저.
        affinity = fls[gear_floor(v)].hard if KIND_HARD.get(cand['kind'], True) else fls[gear_floor(v)].soft
        return (1 if cand['boss'] else 0, gear_floor(v), v.get('level_req', 1),
                RARITY_ORDER.index(v.get('rarity')) if v.get('rarity') in RARITY_ORDER else 0,
                0 if cand['how'] == 'recipe' else 1, 0 if cand['bulk'][0] == affinity else 1,
                KIND_ORDER.index(cand['kind']) if cand['kind'] in KIND_ORDER else 99, i)

    cands = {}
    for i in gear:
        fl = fls.get(gear_floor(items[i])) or fls[min(fls, key=lambda x: abs(x - gear_floor(items[i])))]
        cands[i] = candidates(i, items[i], fl, tables, by_result.get(i), refine)
    steps = range(1, cfg['max'] + 1)
    norm_max = {}  # (층, 분류) → 단계 → 일반 장비 중 가장 비싼 1회 공급량 환산값

    def stages_of(cand, bump_lists):
        """겹침을 피하는 변형을 단계별로: 원칙 R(A) → 레시피 밖 나오는 곳 드롭(B) → 정제 정수(C), 각 단계 안에서 R 바꿈 → P·S 순서 →
        개수 +1 (bump_lists 차례로 — 첫 목록을 A·B·C 에 다 써 본 뒤에야 다음 목록)."""
        stages = []
        for bumps in bump_lists:
            for tier in ('RA', 'RB', 'RC'):
                stage = [(P, S, R, tag, dp, ds, tier) for (dp, ds) in bumps for (P, S, tag) in cand['ps'] for R in cand[tier]
                         # S 정수를 정제한 윗 정수는 R 로 쓰지 않는다 (같은 정수를 두 번 걷어 가서 +10 이 너무 길어짐)
                         if R not in (P, S) and refine.get(R) != S]
                if stage:
                    stages.append(stage)
        return stages

    def pick(cand, fl, f, stages, ok):
        for stage in stages:
            for var in stage:
                r = recipe_of(cand, fl, var[0], var[1], var[2], var[4], var[5])
                if signature(r) not in used[f] and ok(r):
                    return var, r
        return None

    for i in sorted(gear, key=order_key):
        v = items[i]
        f = gear_floor(v)
        fl = fls.get(f) or fls[min(fls, key=lambda x: abs(x - f))]
        cand = cands[i]
        need = None
        if cand['boss']:
            key = (f, cand['cat'])
            if key not in norm_max:
                group = [n for n, m in meta.items() if not m['boss'] and m['floor'] == f and m['cat'] == cand['cat']]
                norm_max[key] = {t: max(step_value(fl, refine, out[n], t) for n in group) for t in steps} if group else None
            need = norm_max[key]
            # 보스 장비: P·S 순서 바꿈도 개수 +1 하나만큼으로 친다 — 원칙(P = 가장 많이 드는 재료)을 먼저 지키고, 개수를 가장 적게
            stages = [sorted(st, key=lambda x: (x[4] + x[5] + (x[3] == 'swap'), x[4], x[3] == 'swap')) for st in stages_of(cand, [BOSS_BUMPS])]
        else:
            stages = stages_of(cand, [STAGE_BUMPS, MORE_BUMPS])
        if not stages:
            raise SystemExit(f'{i}: 고를 수 있는 귀한 재료(R)가 없다 — 후보 {cand}')
        first = stages[0][0]
        # 보스 장비: 겹치지 않으면서 모든 단계에서 같은 층·같은 분류 일반 장비 중 가장 비싼 것 이상인 첫 변형
        dominates = (lambda r: all(step_value(fl, refine, r, t) >= need[t] * (1 - 1e-9) for t in steps)) if need else (lambda r: True)
        chosen = pick(cand, fl, f, stages, dominates)
        if chosen is None and need:
            chosen = pick(cand, fl, f, stages, lambda r: True)
            unfair.append(i)
        if chosen is None:
            r = recipe_of(cand, fl, *first[:3], first[4], first[5])
            chosen = (first, r)
            collisions.append((i, used[f][signature(r)]))
        var, r = chosen
        P, S, R, tag, dp, ds, tier = var
        used[f].setdefault(signature(r), i)
        out[i] = r
        # 왜 원칙 그대로가 아닌가: 보스 장비는 '일반 장비 이상'(겹침을 빼고 봐도 원칙 그대로로는 싼 단계가 있음) · '겹침 피함'
        reasons = []
        if var != first:
            fair_first = next((x for st in stages for x in st if dominates(recipe_of(cand, fl, x[0], x[1], x[2], x[4], x[5]))), first)
            if fair_first != first:
                reasons.append('일반 장비 이상')
            if var != fair_first:
                reasons.append('겹침 피함')
        meta[i] = dict(cand, floor=f, P=P, S=S, Rm=R, swapped=(tag == 'swap'), dp=dp, ds=ds, bump=dp + ds, tier=tier,
                       canonical=(var == first), r_rot=(R != first[2]), reasons=reasons)
    return out, meta, fls, collisions, unfair


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


# ───────────────────────── 보스 장비 ≥ 일반 장비 검사 ─────────────────────────
def eff_supply(fl, refine, m):
    """1회 공급량 — 윗 등급 정수는 아래 정수 5:1 정제분까지."""
    s = fl.supply.get(m, 0)
    if refine.get(m):
        s += fl.supply.get(refine[m], 0) / 5
    return s


def step_value(fl, refine, recipe, t):
    """목표 단계 t 시도 1번의 장비 재료를 '클리어 몇 회분'으로 환산 (개수 ÷ 1회 공급량의 합)."""
    return sum(c / max(1e-9, eff_supply(fl, refine, m)) for m, c in costs_for(recipe, t).items())


def step_grade(fl, recipe, t):
    return max((GRADE[fl.cls(m)] for m in costs_for(recipe, t)), default=0)


def fairness(cfg, out, meta, fls, refine):
    """보스 장비(보스 고유·칭호 보상) 와 같은 층·같은 분류(무기 / 방패 / 흉갑·하의 / 투구·신발) 일반 장비 비교.

    grade_bad : 단계마다 보스 장비 재료의 최고 등급(일반 < 정수 < 정예 < 핵)이 일반 장비 최고 등급보다 낮은 경우 — 생성 실패
    r_bad     : +7·+8 귀한 재료가 정예 재료가 아닌 보스 장비 — 생성 실패
    cheaper   : 단계 → [(배율, 보스 장비, 그보다 비싼 일반 장비)] — 1회 공급량 환산값이 가장 비싼 일반 장비보다 싼 보스 장비 (참고)
    """
    groups = collections.defaultdict(lambda: {'boss': [], 'norm': []})
    for i, m in meta.items():
        groups[(m['floor'], m['cat'])]['boss' if m['boss'] else 'norm'].append(i)
    grade_bad, cheaper, compared = [], {t: [] for t in range(1, cfg['max'] + 1)}, 0
    r_bad = [i for i, m in meta.items() if m['boss'] and fls[m['floor']].cls(m['Rm']) != 'elite']
    for (f, cat), g in sorted(groups.items()):
        if not g['boss'] or not g['norm']:
            continue
        fl = fls[f]
        compared += len(g['boss'])
        for t in range(1, cfg['max'] + 1):
            ng = max(step_grade(fl, out[n], t) for n in g['norm'])
            nv, nmax = max((step_value(fl, refine, out[n], t), n) for n in sorted(g['norm']))
            for b in sorted(g['boss']):
                bg = step_grade(fl, out[b], t)
                if bg < ng:
                    grade_bad.append(f'{b} +{t}: 보스 장비 재료 등급 {GRADE_NAME[bg]} < 같은 층 {GROUP[cat]} 일반 장비 {GRADE_NAME[ng]}')
                bv = step_value(fl, refine, out[b], t)
                if bv < nv * (1 - 1e-9):
                    cheaper[t].append((nv / bv, b, nmax))
    return {'grade_bad': grade_bad, 'r_bad': r_bad, 'cheaper': cheaper, 'compared': compared}


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


def write_yaml(cfg, items, recipes_out, meta, fls, rows, collisions, fair, source_note):
    att10 = attempts(cfg, 10)
    att10p = attempts(cfg, 10, protect=True)
    att5 = attempts(cfg, 5)
    n_recipe = sum(1 for m in meta.values() if m['how'] == 'recipe')
    n_drop = len(meta) - n_recipe
    normal = [m for m in meta.values() if not m['boss']]
    boss = [m for m in meta.values() if m['boss']]
    n_canon = sum(1 for m in meta.values() if m['canonical'])
    n_rrot = sum(1 for m in meta.values() if m['r_rot'])
    n_swap = sum(1 for m in meta.values() if m['swapped'])
    n_sb = sum(1 for m in normal if m['ds'] and not m['dp'])
    n_pb = sum(1 for m in normal if m['dp'])
    n_out = sum(1 for m in meta.values() if m['tier'] != 'RA')
    n_boss_extra = sum(1 for m in boss if m['bump'])
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
    w('#      high (+7~+10): P + S + 귀한 재료 R = 레시피에서 가장 귀한 재료 (정예 재료 > 정수)')
    w('#      레시피가 일반 재료 2종뿐이면 R 은 그 장비가 나오는 곳(정예·몬스터·상자)의 귀한 드롭 (정예 재료 > 정수).')
    w('#   ② 제작법이 없는 장비 → 그 장비를 떨어뜨리는 곳의 드롭 재료로 강화한다.')
    w('#      low = 그 층 일반 재료 중 장비 종류에 맞는 쪽 (검방·대검·단검·흉갑·신발 = 단단한 재료, 활·지팡이·홀·투구·하의 = 부드러운 재료)')
    w('#      mid = + 나오는 곳이 같이 떨어뜨리는 다른 일반 재료 (몬스터·상자·정예·보스 모두 그 층 일반 재료 2종을 준다)')
    w('#      high = + 나오는 곳의 귀한 드롭 (정예 재료 > 정수)')
    w('#      집: 층 공용 무기 = 그 층 몬스터·상자 · 보스 고유 = 그 보스 ·')
    w('#          시작 지급(수련생) = 1층 몬스터·상자 · 칭호 보상(악몽의 왕관) = 그 칭호를 주는 10층 보스 (핵 포함)')
    w('#   → 어느 장비든 mid 까지는 일반 재료 2종, 정수·정예 재료는 high 의 R 에만 — 낮은 장비의 mid 가 보스 장비보다 귀해지지 않는다.')
    w('#   ③ 보스 장비 (보스 고유 · 보스가 주는 칭호 보상) — 제작법이 있으면 ①, 없으면 ② 에 더해:')
    w('#      +7·+8 의 R 은 정예 재료만 — 레시피의 정예 재료, 없으면 그 보스 드롭의 정예 재료 (보스 드롭마다 1회 0.5개). 정수로 내려가지 않는다.')
    w('#      +9·+10 은 R 대신 그 보스의 핵.')
    w('#      그리고 단계마다 같은 층·같은 분류(무기 / 방패 / 흉갑·하의 / 투구·신발) 일반 장비 중 가장 비싼 것보다 싸지 않게')
    w('#      (재료 개수 ÷ 그 재료 1회 공급량으로 환산) P·S 개수를 가장 적게 더한다 — 아래 "검사" 참고.')
    w('#   ④ 같은 층에 재료 구성(개수까지)이 똑같은 장비가 생기면, 원칙에서 덜 벗어나는 것부터 차례로:')
    w('#      1단계 (원칙 재료 그대로) R 을 같은 원칙 안의 다른 귀한 재료로(환산해 싼 쪽부터) → P·S 순서 바꿈 → S +1 → S +2 → P +1 …')
    w('#      2단계 (원칙 밖, 1단계로 안 될 때만) 나오는 곳의 다른 귀한 드롭·윗 등급 정수 → 3단계 그 정수를 대장간에서 정제한 윗 등급 정수')
    w('#      일반 장비는 낮은 레벨·등급부터 원칙 그대로 받고 변형은 높은 장비가 받는다. S 를 먼저 늘리는 것은 S 가 mid·high 에만 들어 싸서.')
    w(f'#   결과: 장비 {len(meta)}종 (제작 재료 {n_recipe} · 드롭 재료 {n_drop}) — 원칙 그대로 {n_canon}종 · R 바꿈 {n_rrot}종 ·'
      f' P·S 순서 바꿈 {n_swap}종 · 일반 장비 S +n {n_sb}종 · P +n {n_pb}종 · 원칙 밖 R {n_out}종 (겹칠 수 있음)')
    w(f'#         보스 장비 {len(boss)}종 중 개수를 더한 장비 {n_boss_extra}종. 같은 층에서 구성이 똑같은 장비 {len(collisions)}쌍.')
    w('#   강화석(하급·상급·최상급)은 그대로 모든 장비에 공용으로 든다 — 장비 재료는 그 위에 더하는 몫.')
    w('#')
    w('# ── 개수 (시도 1번당) ─────────────────────────────────────────────────────────')
    fb = lambda cat, bands=BANDS: ' · '.join(fmt_counts(P_BASE[cat][b]) for b in bands)
    fs = lambda cat: fmt_counts(S_BASE[cat]['mid']) + ' · ' + fmt_counts(S_BASE[cat]['high'])
    w('#   P (일반 재료, low · mid · high)  무기 ' + fb('weapon') + ' | 방패 ' + fb('shield'))
    w('#                                    흉갑·하의 ' + fb('armor_body') + ' | 투구·신발 ' + fb('armor'))
    w('#   S (mid · high)  일반 재료: 무기·방패 ' + fs('weapon') + ' | 흉갑·하의 ' + fs('armor_body') + ' | 투구·신발 ' + fs('armor'))
    w('#                   일반 재료 P·S 는 그 재료 1회 공급량 ÷ 40 (0.25 단위, ×1.0 ~ ×2.0) 을 곱하고 .5 는 올린다 — 깊은 층일수록 많이 떨어지고 많이 든다.')
    w('#   R (+7~+10)      정예 재료 ' + fmt_counts(R_COUNT['elite']) + ' · 정수 ' + fmt_counts(R_COUNT['ess'])
      + ' · 윗 등급 정수 ' + fmt_counts(R_COUNT['next']) + '   (보스 장비는 +7·+8 만: 정예 재료 ' + fmt_counts(R_BOSS['elite']) + ')')
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
      f' +9·+10 시도에만 넣는다 (+10 까지 핵 {k10:.0f}개). 대신 +7·+8 에는 그 층 정예 재료.')
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
    one5 = [r['one5'] for r in rows]
    kit5 = [r['kit5'][0] for r in rows]
    ten_n = [x for r in rows for k, v in r['ten'].items() if k != 'boss' for x, _ in v]
    ten_b = [x for r in rows for x, _ in r['ten'].get('boss', [])]
    span = lambda xs, d: f'{min(xs):.{d}f}' if f'{min(xs):.{d}f}' == f'{max(xs):.{d}f}' else f'{min(xs):.{d}f}~{max(xs):.{d}f}'
    w(f'#   → +5 는 장비 하나가 {span(one5, 1)}회, 대표 한 벌이 {span(kit5, 1)}회 (강화석이 병목 — mid 까지는 일반 재료 2종이라 제작과 같이 모인다).')
    w(f'#   → +10 은 장기 목표: 일반 장비 {span(ten_n, 0)}회, 보스 장비는 핵 때문에 그 보스 {span(ten_b, 0)}회 (보호 주문서를 쓰면 크게 준다).')
    w('#   1~3층 하급 강화석은 떠돌이 상인 핀에게서 살 수 있어 병목이 아니다.')
    w('#')
    w('# ── 검사: 보스 장비 vs 같은 층·같은 분류(무기 / 방패 / 흉갑·하의 / 투구·신발) 일반 장비 ─────────')
    n_boss = sum(1 for m in meta.values() if m['boss'])
    n_elite = sum(1 for m in meta.values() if m['boss'] and fls[m['floor']].cls(m['Rm']) == 'elite')
    w(f"#   +7·+8 귀한 재료가 정예 재료인 보스 장비 {n_elite}/{n_boss}종 · 단계마다 재료 등급(일반 < 정수 < 정예 < 핵)이"
      f" 같은 분류 일반 장비 최고 등급보다 낮은 경우 {len(fair['grade_bad'])}건")
    w('#   1회 공급량 환산(개수 ÷ 그 재료 1회 공급량, 윗 등급 정수는 정제분 포함)이 같은 분류 일반 장비 중 가장 비싼 것보다 싼 보스 장비 수'
      f" (비교 {fair['compared']}종 — 그 층에 일반 방패가 없는 방패는 빠짐):")
    w('#     ' + ' · '.join(f"+{t} {len(v)}" + (f"(최대 ×{max(v)[0]:.2f})" if v else '') for t, v in fair['cheaper'].items()))
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
        if m['tier'] == 'RC':
            why += ' + 정제 정수'
        elif m['how'] == 'recipe' and m['Rm'] not in m['R_recipe']:
            why += ' + 나오는 곳 드롭'
        notes = []
        if m['r_rot']:
            notes.append('R 바꿈')
        if m['swapped']:
            notes.append('P·S 바꿈')
        if m['dp']:
            notes.append(f"P +{m['dp']}")
        if m['ds']:
            notes.append(f"S +{m['ds']}")
        w(f"  {i}:  # {v.get('name', i)} · {KIND_NAME.get(m['kind'], m['kind'])} · {home_text(v, m['label'])} → {why}"
          + (f" ({', '.join(notes)} — {' · '.join(m['reasons'])})" if notes else ''))
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
    recipes_out, meta, fls, collisions, unfair = build(c, cfg)
    refine = refined_from(c['recipes'])
    rows = report_rows(cfg, items, recipes_out, meta, fls, refine)
    problems = obtainable_problems(items, recipes_out, meta, fls, refine)
    note = a.note or (f'content/ — 장비 {len(recipes_out)}종 · 레시피 {len(c["recipes"])}개 · 루팅 테이블 {len(c["tables"])}개'
                      + (' + 루팅 명세 ' + Path(a.spec).name if a.spec else ''))
    fair = fairness(cfg, recipes_out, meta, fls, refine)
    problems += [f'{i}: 보스 장비 +7·+8 귀한 재료가 정예 재료가 아님 ({meta[i]["Rm"]})' for i in fair['r_bad']] + fair['grade_bad']
    text = write_yaml(cfg, items, recipes_out, meta, fls, rows, collisions, fair, note)
    summary = (f'장비 {len(recipes_out)}개 · 같은 층 똑같은 구성 {len(collisions)}쌍 {collisions[:5]}'
               f" · 원칙 그대로 {sum(1 for m in meta.values() if m['canonical'])} · P·S 바꿈 {sum(1 for m in meta.values() if m['swapped'])}"
               f" · 개수 더함 {sum(1 for m in meta.values() if m['bump'])} · 원칙 밖 R {sum(1 for m in meta.values() if m['tier'] != 'RA')}"
               f" · 보스 장비가 일반 장비보다 싼 단계 {sum(len(v) for v in fair['cheaper'].values())}"
               f" (일반 장비 이상을 못 맞춘 보스 장비 {unfair}) · 재료 문제 {len(problems)}")
    if problems:
        print('재료 문제:', *problems, sep='\n  ', file=sys.stderr)
    if a.report:
        print('\n'.join(l for l in text.splitlines() if l.startswith('#')))
        for t, v in fair['cheaper'].items():
            for ratio, b, n in sorted(v, reverse=True)[:3]:
                print(f'  +{t} {b} < {n} ×{ratio:.2f}')
        print(summary)
        return 1 if problems else 0
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
