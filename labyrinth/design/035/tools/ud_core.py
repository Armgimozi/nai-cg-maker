# -*- coding: utf-8 -*-
"""TASK D (고유 효과 합치기) 공통 로더 — 읽기 전용.
237 무기 = 기존 131 (items.yml + unique_spec 배정 + gear_spec existing_changes + combat_spec)
        + 새 106 (gear_spec weapons + combat_spec).
"""
import json, os, collections
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.dirname(HERE)
REPO = '/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'

def _j(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

ITEMS = yaml.safe_load(open(REPO + 'items.yml', encoding='utf-8'))['items']
COMBAT = _j(D2 + '/combat_spec.json')
GEAR = _j(D2 + '/gear_spec.json')
USPEC = _j(D2 + '/unique_spec.json')
PVP = _j(D2 + '/pvp_spec.json')
DIRS = _j(D2 + '/directions.json')['tags']
EFF = USPEC['effects']

RAR = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic']
RAR_KO = {'common': '일반', 'uncommon': '고급', 'rare': '희귀', 'epic': '영웅', 'legendary': '전설', 'mythic': '신화'}
STYLE_KO = {'melee': '근접', 'ranged': '원거리', 'caster': '시전'}
SRC_SK = {'boss': 'B', 'craft': 'F', 'drop': 'M', 'chest': 'M', 'trial': 'T', 'special': 'S', 'hoard': 'V', 'elite': 'E',
          'shop': 'P', 'reward': 'R', 'starter': 'ST'}
SK_KO = {'B': '보스', 'F': '대장간', 'M': '몹·상자', 'T': '시련방', 'S': '특별 시련', 'V': '금고·미믹', 'E': '정예', 'P': '상인',
         'R': '칭호 보상', 'ST': '시작 지급'}
DIR_KO = {k: v['name'] for k, v in DIRS.items()}

def band(L):
    return (int(L) - 1) // 5 + 1

def blabel(b):
    return f"{b*5-4}–{b*5}"

def mid(r):
    return (r[0] + r[1]) / 2 if isinstance(r, (list, tuple)) else float(r)

def K_style(style, interval):
    if style == 'ranged':
        return 1.413
    if style == 'caster':
        return 1.22
    return 1.47 - 0.143 * max(0.0, 1.0 / interval - 1.5)

def spm(style):
    return 1.05 if style == 'caster' else 1.0

def load():
    W = {}
    CW = COMBAT['weapons']
    for wid, ch in GEAR['existing_changes'].items():
        it = ITEMS[wid]; c = CW[wid]; a = USPEC['assignments'][wid]
        W[wid] = dict(id=wid, new=False, name=it['name'], lore=it.get('lore', ''), L=c['level'], rar=c['rarity'],
                      style=ch['attack']['style'], kind=ch['attack']['kind'], interval=ch['attack']['interval'],
                      per_hit=list(ch['stats_damage']), shape=c['shape'], stats={k: v for k, v in (it.get('stats') or {}).items() if k != 'damage'},
                      n_skills=len(it.get('weapon_skills') or []), skills=it.get('weapon_skills') or [],
                      sources=list(ch['sources']), direction=ch['direction'],
                      effect=a['effect'], uname=a['name'], element=a['params'].get('element'),
                      old_params=a['params'], old_s=a['strength'], requires=ch['requires'], old_type=c.get('old_type'))
    for wid, v in GEAR['weapons'].items():
        c = CW[wid]; u = v['unique']
        W[wid] = dict(id=wid, new=True, name=v['name'], lore=v.get('lore', ''), L=v['level_req'], rar=v['rarity'],
                      style=v['attack']['style'], kind=v['attack']['kind'], interval=v['attack']['interval'],
                      per_hit=list(v['stats']['damage']), shape=v['model']['shape'],
                      stats={k: x for k, x in v['stats'].items() if k != 'damage'},
                      n_skills=len(v.get('weapon_skills') or []), skills=v.get('weapon_skills') or [],
                      sources=list(v['sources']), direction=v['direction'],
                      effect=u['id'], uname=u['name'], element=u.get('element'),
                      old_params={k: x for k, x in u.items() if k not in ('id', 'name')},
                      old_s=v['_spec'].get('unique_strength'), requires=v['requires'], old_type=None)
    for w in W.values():
        w['band'] = band(w['L'])
        w['sk'] = sorted(set(SRC_SK[s] for s in w['sources']))
    return W

if __name__ == '__main__':
    W = load()
    print(len(W))
    print(collections.Counter(w['band'] for w in W.values()))
    print(collections.Counter(tuple(w['sk']) for w in W.values()))
