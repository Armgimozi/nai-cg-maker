# -*- coding: utf-8 -*-
"""TASK C (2판, gear-c2) 공통 — repo yml(읽기 전용) · 전투 명세(combat_spec.json) · 효과 명세(unique_spec.json) ·
옛 장비 명세(_bak/gear_spec_c1.json: 새 무기 106개의 이름·모양·효과·이야기·모델, 새 방어구 6세트, 새 실루엣)를 읽는다.

이 판에서 새로 정하는 것: 요구 능력치(AND 만, 2~3 능력치 나눔), 층 이름표 없는 획득처(띠 풀), 띠별 다양성, 특별 시련 표, 테스트.
숫자(간격·한 방 피해·스킬 위력)는 combat_spec.json 을 그대로 쓴다.
"""
import collections
import json
import math
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.dirname(HERE)
REPO = '/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/'
C = REPO + 'content/'


def _y(p):
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f)


def _j(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


_IT = _y(C + 'items.yml')
ITEMS = _IT['items']
SETS = _IT['sets']
LOOT_ALL = _y(C + 'loot.yml')
LOOT = LOOT_ALL['tables']
LOOT_SETTINGS = LOOT_ALL['settings']
RECIPES = _y(C + 'recipes.yml')['recipes']
MOBS = _y(C + 'mobs.yml')['mobs']
BOSSES = _y(C + 'bosses.yml')['bosses']
FLOORS = _y(C + 'floors.yml')['floors']
CLASSES = _y(C + 'classes.yml')['classes']
TITLES = _y(C + 'titles.yml')['achievements']
NPCS = _y(C + 'npcs.yml')['npcs']
CONFIG = _y(REPO + 'config.yml')

COMBAT = _j(D2 + '/combat_spec.json')
CW = COMBAT['weapons']                       # 237 무기: interval · per_hit · style · kind · skill_power …
USPEC = _j(D2 + '/unique_spec.json')
DIRS = _j(D2 + '/directions.json')['tags']
OLD = _j(HERE + '/_bak/gear_spec_c1.json')   # 옛 판 (새 무기 106개 정의 · 방어구 · 실루엣 · 특별 시련)
OLDW = OLD['weapons']

STATS6 = ['STR', 'DEX', 'INT', 'VIT', 'WIS', 'LUK']
STAT_KO = {'STR': '힘', 'DEX': '민첩', 'INT': '지능', 'WIS': '정신', 'VIT': '체력', 'LUK': '행운'}
RAR = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic']
RAR_KO = {'common': '일반', 'uncommon': '고급', 'rare': '희귀', 'epic': '영웅', 'legendary': '전설', 'mythic': '신화'}
STYLE_KO = {'melee': '근접', 'ranged': '원거리', 'caster': '시전'}
KIND_KO = {'physical': '물리', 'magic': '마법', 'hybrid': '혼합'}
CLS = ['guardian', 'berserker', 'hunter', 'arcanist', 'priest', 'shadow']
CLS_KO = {'guardian': '수호기사', 'berserker': '광전사', 'hunter': '사냥꾼', 'arcanist': '비전술사', 'priest': '사제', 'shadow': '그림자'}

# 획득처 종류 (source kind) — 툴팁·도감 글자는 층 번호 없이
SK = ['B', 'F', 'M', 'T', 'S', 'V', 'E', 'P']
SK_KO = {'B': '보스', 'F': '대장간', 'M': '몬스터·상자', 'T': '시련방', 'S': '특별 시련', 'V': '금고·미믹', 'E': '정예', 'P': '상인',
         'R': '칭호 보상', 'ST': '시작 지급'}
SK_SRC = {'B': ['boss'], 'F': ['craft'], 'M': ['drop', 'chest'], 'T': ['trial'], 'S': ['special'], 'V': ['hoard'],
          'E': ['elite'], 'P': ['shop'], 'R': ['reward'], 'ST': ['starter']}
SRC_SK = {'boss': 'B', 'craft': 'F', 'drop': 'M', 'chest': 'M', 'trial': 'T', 'special': 'S', 'hoard': 'V', 'elite': 'E',
          'shop': 'P', 'reward': 'R', 'starter': 'ST'}
POOL_KIND = {'M': 'drop', 'T': 'trial', 'S': 'special', 'V': 'hoard', 'E': 'elite'}   # 띠 풀을 쓰는 종류

BANDS = list(range(1, 11))


def band(L):
    return (int(L) - 1) // 5 + 1


def blabel(b):
    return f"{b * 5 - 4}–{b * 5}"


def mid(r):
    return (r[0] + r[1]) / 2 if isinstance(r, (list, tuple)) else float(r)


FLOOR_RANGE = {int(k): tuple(v['level_range']) for k, v in FLOORS.items()}
FLOOR_ELITE = {int(k): v['elite'] for k, v in FLOORS.items()}
FLOOR_GIMMICK = {int(k): v['gimmick'] for k, v in FLOORS.items()}
FLOOR_NAME = {int(k): v['name'] for k, v in FLOORS.items()}
FLOOR_BOSS = {int(k): v['boss'] for k, v in FLOORS.items()}
BOSS_TABLE = {f: BOSSES[b]['drops'] for f, b in FLOOR_BOSS.items()}


def look_of_item(iid):
    """방어구 겉모습 heavy|light|cloth|shield|any (세트는 흉갑 모양, 단품 투구는 투구 모양) — GearRequirementsDataTest.LOOK 와 같음."""
    d = ITEMS[iid]
    if d.get('armor_slot') == 'offhand':
        return 'shield'
    LOOK = {'chestplate': 'heavy', 'leather_vest': 'light', 'robe_top': 'cloth', 'helm_knight': 'heavy', 'helm_horned': 'heavy',
            'helm_winged': 'heavy', 'hood': 'light', 'half_mask': 'light', 'circlet': 'cloth', 'crown': 'cloth', 'wizard_hat': 'cloth'}
    s = d.get('armor_set')
    if s:
        for k, o in ITEMS.items():
            if o.get('armor_set') == s and o.get('armor_slot') == 'chest':
                return LOOK.get(o['model']['shape'], 'any')
    if not d.get('classes'):
        return 'any'
    return LOOK.get(d['model']['shape'], 'any')


def weapons_all():
    """237 무기 한 줄 정보 (이 판 계산의 기준). 숫자는 combat_spec, 효과·방향은 unique_spec(기존)·옛 판(새)."""
    out = {}
    for wid, c in CW.items():
        new = c['src'] != 'existing'
        if new:
            o = OLDW[wid]
            unique = dict(o['unique'])
            direction = o['direction']
            name = o['name']
            lore = o['lore']
            stats = dict(o['stats'])
            old_kind = o['source']['kind']
            skills = o.get('weapon_skills') or []
            strength = o.get('unique_strength')
            tooltip = o.get('unique_tooltip')
        else:
            v = ITEMS[wid]
            a = USPEC['assignments'][wid]
            unique = dict(a, id=a['effect'])
            direction = a['direction']
            name = v['name']
            lore = v['lore']
            stats = dict(v['stats'])
            s = v.get('sources') or []
            old_kind = 'B' if 'boss' in s else 'F' if s == ['craft'] else ('M+F' if 'craft' in s else 'M')
            skills = v.get('weapon_skills') or []
            strength = a.get('strength')
            tooltip = a.get('tooltip')
        stats['damage'] = list(c['per_hit'])
        L = c['level']
        out[wid] = dict(id=wid, name=name, new=new, L=L, band=band(L), rar=c['rarity'], style=c['style'], kind=c['kind'],
                        interval=c['interval'], per_hit=list(c['per_hit']), sp=c['skill_power'], dps=c['dps_equiv'],
                        shape=c['shape'], direction=direction, unique=unique, lore=lore, stats=stats, old_kind=old_kind,
                        skills=skills, strength=strength, tooltip=tooltip,
                        floor_old=(OLDW[wid]['floor'] if new else ITEMS[wid]['floor']))
    return out


def armor_all():
    """기존 방어구·방패 95개 + 옛 판 새 방어구 6세트(24)."""
    out = {}
    for k, v in ITEMS.items():
        if v.get('type') == 'armor':
            out[k] = dict(id=k, new=False, name=v['name'], L=v['level_req'], band=band(v['level_req']), rar=v['rarity'],
                          slot=v['armor_slot'], set=v.get('armor_set'), set_bonus=v.get('set_bonus'), look=look_of_item(k),
                          sources=v.get('sources') or [], floor_old=v.get('floor'), classes=v.get('classes') or [],
                          stats=v.get('stats') or {})
    for sid, s in OLD['armor_sets'].items():
        for pid, p in s['pieces_items'].items():
            out[pid] = dict(id=pid, new=True, name=p['name'], L=p['level_req'], band=band(p['level_req']), rar=p['rarity'],
                            slot=p['armor_slot'], set=sid, set_bonus=sid, look=s['look'], sources=p.get('sources') or [],
                            floor_old=p.get('floor'), classes=p.get('classes') or [], stats=p.get('stats') or {})
    return out


def class_base(c):
    return dict(CLASSES[c]['base_stats'])


def points_at(L):
    lv = CONFIG['level']
    return lv['start_points'] + (max(1, L) - 1) * lv['points_per_level']


if __name__ == '__main__':
    W = weapons_all()
    A = armor_all()
    print(len(W), len(A))
    print(collections.Counter(w['old_kind'] for w in W.values()))
    print(collections.Counter((w['band']) for w in W.values()))
