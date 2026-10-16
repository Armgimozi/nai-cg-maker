#!/usr/bin/env python3
"""0.3.6 계약 검사 — mine.json · materials.json · visual.json · district.json 을 서로, 그리고 주인 결정·지금 content·Java 뼈대와 맞대어 본다.

  python3 -B tools/data/036/check_contract.py        # 오류가 있으면 1
params.py 를 읽지 않는다 (JSON 만 본다) — 다만 마지막에 build_contract.py --check 로 JSON 이 params 와 같은지 본다.
"""
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
CONTENT = LAB / 'plugin/src/main/resources/content'
JAVA = LAB / 'plugin/src/main/java/kr/labyrinth'
errors, notes = [], []

METALS = ['copper', 'iron', 'silver', 'gold', 'mithril', 'orichalcum']
GEMS = ['quartz', 'garnet', 'moonstone', 'topaz', 'sapphire', 'dragonblood_stone']
REACH_ABOVE = 1               # 0.3.6.1 주인 결정 1: 곡괭이 tier t 는 tier ≤ t + 1 을 캔다 (한 단계 위는 느림)
GOLD_WITH_SALE_MAX = 0.20     # 광산 G/분 ÷ 던전 G/분 (판매 포함, 그 단계 금속을 캘 수 있는 가장 낮은 곡괭이) — 0.3.6 과 같음
GOLD_DROP_MAX = 0.25          # 드롭 골드만 — 0.3.6 과 같음 (곡괭이를 일찍 올린 사람은 표 E 참고 칸)
MONSTER = ['ember_soul', 'resonant_sinew', 'clock_oil']          # §0 결정 4: 5층은 불씨 혼 (잿불 가죽 없음)
DROP_PARTS = ['moss_scale', 'tunnel_fang', 'cinder_scale', 'rime_talon', 'chrono_dust', 'abyss_scale']   # §0 결정 4: 몹 몸에 맞는 새 부위
PRE_RELEASE = {'cinder_hide': 'cinder_scale'}                  # 배포 전 시험 서버에만 있던 id
RETIRED = ['rusted_iron', 'slag_ingot', 'ember_shard', 'rime_crystal', 'amethyst_shard', 'prism_dust', 'brass_gear', 'mainspring']
BANNED_WORDS = ['starmetal', 'obsidian', '별철', '흑요석']
LABEL_RE = re.compile(r'(Lv\s*\d|레벨|\d+\s*층|층\s*\d|단계|구간|티어|tier\s*\d)', re.I)
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
BIOMES = {'badlands', 'bamboo_jungle', 'basalt_deltas', 'beach', 'birch_forest', 'cherry_grove', 'cold_ocean', 'crimson_forest', 'dark_forest',
          'deep_dark', 'desert', 'dripstone_caves', 'end_barrens', 'eroded_badlands', 'flower_forest', 'forest', 'frozen_peaks', 'grove',
          'jungle', 'lush_caves', 'mangrove_swamp', 'meadow', 'mushroom_fields', 'nether_wastes', 'ocean', 'pale_garden', 'plains',
          'savanna', 'snowy_plains', 'soul_sand_valley', 'sulfur_caves', 'swamp', 'taiga', 'the_end', 'the_void', 'warped_forest', 'wooded_badlands'}
PARTICLES = {'WAX_ON', 'WAX_OFF', 'ELECTRIC_SPARK', 'GLOW', 'END_ROD', 'CRIT', 'SCRAPE', 'FLAME', 'SMALL_FLAME', 'DUST', 'WHITE_ASH', 'ASH'}


def err(m):
    errors.append(m)


def need(cond, m):
    if not cond:
        err(m)
    return cond


def load(n):
    p = HERE / n
    if not need(p.exists(), f'{n} 없음'):
        return {}
    return json.loads(p.read_text(encoding='utf-8'))


def hangul(s):
    return any('가' <= ch <= '힣' for ch in s)


def boxes_overlap(a, b, slack=0):
    return not (a[2] + slack < b[0] or b[2] + slack < a[0] or a[3] + slack < b[1] or b[3] + slack < a[1])


def paper_api_names():
    """paper-api 26.3 jar 의 상수 이름 (javap) → {클래스: set(이름)}. jar·javap 가 없으면 None (검사 건너뜀)."""
    jars = sorted(glob.glob(os.path.expanduser('~/.gradle/caches/modules-2/files-2.1/io.papermc.paper/paper-api/26.3*/*/paper-api-*.jar')))
    javap = shutil.which('javap') or next((j for j in (os.path.join(os.environ.get('JAVA_HOME', ''), 'bin/javap'), '/opt/jdk25/bin/javap')
                                           if j and os.path.exists(j)), None)
    if not jars or not javap:
        return None
    out = {}
    for cls in ('org.bukkit.block.BlockType', 'org.bukkit.block.Biome', 'org.bukkit.Particle', 'org.bukkit.Sound',
                'org.bukkit.entity.EntityType', 'org.bukkit.potion.PotionEffectType'):
        r = subprocess.run([javap, '-cp', jars[-1], cls], capture_output=True, text=True)
        if r.returncode:
            return None
        out[cls.rsplit('.', 1)[1]] = set(re.findall(r'static final \S+ ([A-Z0-9_]+);', r.stdout))
    out['_jar'] = os.path.basename(jars[-1])
    return out


def collateral_uses(blocks):
    """블록 이름(minecraft:…)이 content/*.yml (mine.yml 빼고 — 미궁 층·경기장·보스 무대 …)·마을/구역 조각(resources/village/**)·
    광산 청사진 팔레트(@vein/@gem 빼고)에 나오는 곳."""
    names = {b.split(':', 1)[1] for b in blocks}
    pat = re.compile(r'(?<![a-z0-9_])(' + '|'.join(sorted(map(re.escape, names))) + r')(?![a-z0-9_])', re.I)
    hits = []
    res = LAB / 'plugin/src/main/resources'
    files = [f for f in sorted((res / 'content').glob('*.yml')) if f.name != 'mine.yml'] + sorted((res / 'village').rglob('*'))
    for f in files:
        if f.is_file():
            for m in pat.finditer(f.read_text(encoding='utf-8', errors='replace')):
                hits.append(f"{f.relative_to(res)}:{m.group(1)}")
    for f in sorted((res / 'mine/levels').glob('L*.json')):
        pal = json.loads(f.read_text(encoding='utf-8')).get('palette') or {}
        for v in (pal.values() if isinstance(pal, dict) else pal):
            if isinstance(v, str) and not v.startswith('@') and pat.search(v):
                hits.append(f"{f.relative_to(res)}:{v}")
    return hits


def gdd_closed_lists():
    text = (LAB / 'GDD.md').read_text(encoding='utf-8')
    sec = text.split('### 14.5', 1)[1].split('### 14.6', 1)[0]
    out = {}
    for key in ('outfit', 'hair', 'accessories'):
        m = re.search(r'- `' + key + r'`:(.*?)(?=\n- `|\Z)', sec, re.S)
        out[key] = set(re.findall(r'`([a-z_]+)`', m.group(1))) if m else set()
    return out


def main():
    mine, mat, vis, dist = load('mine.json'), load('materials.json'), load('visual.json'), load('district.json')
    if errors:
        return
    for n, d in (('mine', mine), ('materials', mat), ('visual', vis), ('district', dist)):
        need(d.get('contract') == '0.3.6' and d.get('schema') == 1, f'{n}.json contract/schema')
    items_now = (yaml.safe_load(open(CONTENT / 'items.yml', encoding='utf-8')) or {})['items']
    recipes_now = (yaml.safe_load(open(CONTENT / 'recipes.yml', encoding='utf-8')) or {})['recipes']

    # ── 1. id ──
    ores = [f'{m}_ore' for m in METALS]
    ingots = [f'{m}_ingot' for m in METALS]
    picks = [f'{m}_pickaxe' for m in METALS]
    expect_ids = ores + ingots + GEMS + MONSTER + DROP_PARTS + picks
    need(sorted(mat['new_ids']) == sorted(expect_ids), f"새 id 목록이 주인 결정과 다름: {sorted(set(mat['new_ids']) ^ set(expect_ids))}")
    need(len(set(mat['new_ids'])) == len(mat['new_ids']) == 33, '새 id 33개 (광산 27 − 잿불 가죽 + 불씨 혼 + 몹 주제 부위 6), 겹침 없음')
    # content 는 바꾸기 전(0.3.5.1 — 새 id 0 · 옛 id 8) 이거나 Q3 생성기가 바꾼 뒤(새 id 모두 · 옛 id 0) 둘 중 하나여야 한다
    have_new = [i for i in mat['new_ids'] if i in items_now]
    migrated = len(have_new) == len(mat['new_ids'])
    need(migrated or not have_new, f'content 가 반쯤 바뀜 — 새 id {len(have_new)}/{len(mat["new_ids"])} (python3 tools/gen_035_content.py)')
    if migrated:
        notes.append('content 는 0.3.6 (Q3 생성기가 바꾼 뒤) — 새 id 모두 있음 · 옛 id 0 을 본다')
    for i in mat['new_ids']:
        if migrated:
            v = items_now[i]
            need(v.get('name') == mat['items'][i]['name'] and v.get('type') == mat['items'][i]['type'], f'{i}: items.yml 이름·종류 ≠ 계약')
            need(v.get('rarity') == mat['items'][i]['rarity'], f'{i}: items.yml 희귀도 ≠ 계약')
            if mat['items'][i]['kind'] in ('ore', 'ingot', 'gem'):
                need(v.get('mine_kind') == mat['items'][i]['kind'] and v.get('mine_level') == mat['items'][i]['mine_level'], f'{i}: mine_kind·mine_level ≠ 계약')
        need(i not in RETIRED and i not in PRE_RELEASE, f'새 id 가 옛 id: {i}')
        need(re.fullmatch(r'[a-z][a-z0-9_]*', i) is not None and ':' not in i, f'플러그인 id 꼴이 아님: {i}')
    need(list(mine['ores']) == ores, f"mine.ores 순서·id: {list(mine['ores'])}")
    need(list(mine['gems']) == GEMS, f"mine.gems 순서·id: {list(mine['gems'])}")
    need(list(mine['pickaxes']) == picks, f"mine.pickaxes 순서·id: {list(mine['pickaxes'])}")
    blob = json.dumps([mine, mat, vis, dist], ensure_ascii=False)
    for w in BANNED_WORDS:
        need(w not in blob, f'버린 이름이 남음: {w}')
    for r in RETIRED:
        if migrated:
            need(r not in items_now, f'옛 id 가 바뀐 content 에 남음: {r}')
        else:
            need(r in items_now, f'옛 id 가 지금 items.yml 에 없음 (바꿈 표 확인): {r}')
    for r in PRE_RELEASE:
        need(r not in items_now, f'배포 전 id 가 items.yml 에 있음: {r}')
    need(mat['conversion'].get('pre_release') == PRE_RELEASE, '배포 전 id 바꿈 표 (cinder_hide → cinder_scale)')

    # ── 2. 등급 ──
    for k, o in enumerate(ores, 1):
        need(mine['ores'][o]['tier'] == k == mat['items'][o]['mine_level'], f'{o} 등급')
        need(mat['items'][f'{METALS[k - 1]}_ingot']['mine_level'] == k, f'{METALS[k - 1]}_ingot 등급')
        need(mine['ores'][o]['gem'] == GEMS[k - 1], f'{o} 덤 보석')
    for k, g in enumerate(GEMS, 1):
        need(mine['gems'][g]['tier'] == k == mat['items'][g]['mine_level'], f'{g} 등급')
    for k, p in enumerate(picks, 1):
        d = mine['pickaxes'][p]
        need(d['tier'] == k == mat['items'][p]['tier'] == mat['items'][p]['tool']['tier'], f'{p} 등급')
        need(d['level_req'] is None and mat['items'][p].get('level_req') is None, f'{p} 레벨 조건이 있음 (주인 결정 2)')
        need(mat['items'][p]['sellable'] is False, f'{p} 팔 수 있음')
        top = min(6, k + REACH_ABOVE)   # 0.3.6.1 주인 결정: 한 단계 위까지 캔다 (느리게)
        want = [o for o in ores if mine['ores'][o]['tier'] <= top] + [g for g in GEMS if mine['gems'][g]['tier'] <= top]
        need(sorted(d['mines']) == sorted(want), f'{p} mines = tier ≤ {top} 가 아님')
        need(sorted(d.get('slow') or []) == sorted(x for x in want if (mine['ores'].get(x) or mine['gems'].get(x))['tier'] > k), f'{p} slow = 한 단계 위')
        need(set(d['speed']) == {str(o) for o in range(1, top + 1)}, f'{p} speed 키 = 1..{top}')
        for o in range(1, k + 1):
            need(abs(d['speed'][str(o)] - d['speed']['1']) < 1e-9, f'{p} 제 등급 이하 속도가 같지 않음')
        if top > k:
            own = mine['pickaxes'][picks[top - 1]]['speed'][str(top)]
            slow = d['speed'][str(top)]
            need(0.5 <= slow / own <= 0.75, f'{p} 한 단계 위 속도 {slow} 가 제 곡괭이 {own} 의 0.5~0.75 배가 아님 (느리지만 캘 만해야)')
            need(abs(slow / own - mine['rules']['stretch_factor']) < 0.01, f'{p} 한 단계 위 속도 ≠ rules.stretch_factor')
        need(d['speed'] == mat['items'][p]['tool']['speed'], f'{p} speed mine ↔ materials')
        need(abs(d['bonus'] - mat['items'][p]['tool']['bonus']) < 1e-9, f'{p} bonus mine ↔ materials')
    for o in range(1, 7):   # 좋은 곡괭이일수록 모든 광석에서 빠름 (한 단계 아래 곡괭이 = 느림 → 제 곡괭이 → 위 곡괭이)
        prev = None
        for k, p in enumerate(picks, 1):
            if k + REACH_ABOVE < o:
                continue
            s = mine['ores'][ores[o - 1]]['base_seconds'] / mine['pickaxes'][p]['speed'][str(o)]
            need(abs(s - mine['pickaxes'][p]['seconds'][ores[o - 1]]) < 0.011, f'{p} {ores[o - 1]} 초 표')
            need(s >= mine['rules']['min_seconds'] - 1e-9, f'{p} {ores[o - 1]} {s:.2f}초 < 최소')
            if prev is not None:
                need(s < prev - 1e-9, f'{p} 가 {ores[o - 1]} 에서 앞 곡괭이보다 빠르지 않음')
            prev = s
    bonus = [mine['pickaxes'][p]['bonus'] for p in picks]
    need(bonus == sorted(bonus), '곡괭이 덤이 등급 순이 아님')
    base = [mine['ores'][o]['base_seconds'] for o in ores]
    need(base == sorted(base), '광석 base_seconds 가 단단함 순이 아님')

    # ── 3. 층 ──
    lv = mine['levels']
    need(len(lv) == 6 and [x['n'] for x in lv] == list(range(1, 7)), '층 6개 (1..6)')
    need(len({x['id'] for x in lv}) == 6 and len({x['name'] for x in lv}) == 6, '층 id·이름 겹침')
    ys = [x['floor_y'] for x in lv]
    need(ys == sorted(ys, reverse=True), '층 바닥 y 가 깊이 순이 아님')
    depth = [x['depth_m'] for x in lv]
    need(depth == sorted(depth), '층 깊이(m) 순')
    for a, b in zip(lv, lv[1:]):
        need(a['box'][1] > b['box'][4], f"층 상자 겹침 {a['n']}·{b['n']}")
    for x in lv:
        need(not re.search(r'\d', x['name']) and hangul(x['name']), f"층 이름에 숫자/한글 아님: {x['name']}")
        need(x['biome'].startswith('minecraft:') and x['biome'].split(':')[1] in BIOMES, f"바이옴 이름: {x['biome']}")
        y0, y1 = x['biome_y']
        need(y0 % 4 == 0 and (y1 + 1) % 4 == 0, f"{x['n']} 바이옴 경계가 4칸 단위 아님 {x['biome_y']}")
        need(y0 <= x['box'][1] and x['box'][4] <= y1, f"{x['n']} 층 상자가 바이옴 띠 밖 {x['box']} {x['biome_y']}")
        need(x['regen_fx'] in PARTICLES, f"{x['n']} 재생 입자 {x['regen_fx']}")
        need(HEX.match(x['title_color']) is not None, f"{x['n']} 층 색")
        w = x['ore_weights']
        need(abs(sum(w.values()) - 100) < 1e-9, f"{x['n']} 광석 무게 합 {sum(w.values())}")
        need(len(w) >= 3, f"{x['n']} 광석이 섞이지 않음 (주인 결정 3)")
        need(set(w) <= set(ores), f"{x['n']} 모르는 광석")
        need(abs(sum(x['gem_weights'].values()) - 100) < 1e-9 and set(x['gem_weights']) <= set(GEMS), f"{x['n']} 보석 무게")
        need(len(x['gem_weights']) >= 2, f"{x['n']} 보석이 섞이지 않음")
        need(sum(x['vein_blocks'].values()) == x['veins_total'], f"{x['n']} 광맥 블록 수 합")
        need(set(x['vein_blocks']) == set(w), f"{x['n']} 청사진 광석 종류 ≠ 무게")
        need(all(g in GEMS for g in x['gem_nodes']) and len(x['gem_nodes']) >= 2, f"{x['n']} 보석 노드")
        need(x['prototype']['reach_max'] <= mine['rules']['veins']['reach_max'], f"{x['n']} 손 닿는 광맥 {x['prototype']['reach_max']}")
        need(x['prototype'].get('reach_max_server', 99) <= mine['rules']['veins']['reach_max'],
             f"{x['n']} 서버 한도 {mine['rules']['veins'].get('reach_server')} 에서 손 닿는 광맥 {x['prototype'].get('reach_max_server')}")
        need(x['office'] == (x['n'] == 1), f"{x['n']} 관리소 자리")
    share = lambda x, o: x['ore_weights'].get(o, 0)
    need(share(lv[0], 'copper_ore') + share(lv[0], 'iron_ore') >= 80 and 0 < share(lv[0], 'silver_ore') <= 15, '맨 위층: 구리·철 많고 은 조금')
    need(share(lv[1], 'copper_ore') + share(lv[1], 'iron_ore') >= 70, '둘째 층: 구리·철 많음')
    need(set(lv[-1]['ore_weights']) == set(ores), '가장 깊은 층에 모든 광석')
    need(max(lv, key=lambda x: share(x, 'orichalcum_ore'))['n'] == 6, '오리하르콘 몫이 가장 큰 층 = 가장 깊은 층')
    need(max(lv[-1]['ore_weights'], key=lv[-1]['ore_weights'].get) == 'orichalcum_ore', '가장 깊은 층의 가장 큰 몫 = 오리하르콘')
    ori = [share(x, 'orichalcum_ore') for x in lv]
    need(ori == sorted(ori), '오리하르콘 몫이 깊을수록 늘지 않음')
    deep = [share(x, 'gold_ore') + share(x, 'mithril_ore') + share(x, 'orichalcum_ore') for x in lv]
    need(deep == sorted(deep), '금·미스릴·오리하르콘 몫이 깊을수록 늘지 않음')
    need(mine['rules']['lift']['gate'] is None and mine['owner_decisions']['all_levels_open'] is True, '승강기 잠김 (주인 결정 2)')
    need(mine['owner_decisions']['level_binding'] is False, 'level_binding')
    need(mine['rules']['too_weak_actionbar'] == '곡괭이가 약해 캘 수 없습니다', '못 캘 때 액션바 글')
    need('stamina' not in mine['rules'] and 'stamina' not in mine['config_defaults']['mine'], '기력이 남음 (계약 §0-1)')
    need(not any('stamina' in k for k in mine['names']['ext']), 'ext mine.stamina* 가 남음 (계약 §0-1)')
    need('anti_afk' not in mine['rules'] and 'alert_per_hour' not in mine['config_defaults']['mine'], '매크로 막기가 남음 (계약 §0-2)')
    need('mine.prev_mode' not in mine['names']['ext'], 'ext mine.prev_mode 가 남음 (R §2-3)')
    need(set(mine['names']['interact']) == {'mine_lift', 'mine_office', 'smelter', 'mine_info'}, 'interact 이름')
    need(set(mine['names']['npc_roles']) == {'miner', 'smelter'}, 'NPC 역할 이름')
    need(len(mine['config_defaults']['mine']['regen_minutes']) == 6, 'config regen_minutes 6개')
    need(mine['config_defaults']['mine']['fx']['pop'] is True, '광석 날아오기 켬 (주인 결정 5)')

    # ── 4. 블록 ──
    ob = {o: v['block'] for o, v in vis['blocks']['ores'].items()}
    gb = {g: v['block'] for g, v in vis['blocks']['gems'].items()}
    need(set(ob) == set(ores) and set(gb) == set(GEMS), '블록 표 = 광석 6 + 보석 6')
    allb = list(ob.values()) + list(gb.values())
    need(len(set(allb)) == 12, f'광석·보석 블록 12개가 서로 다르지 않음: {allb}')
    for o in ores:
        need(mine['ores'][o]['block'] == ob[o], f'{o} 블록 mine ↔ visual')
    for g in GEMS:
        need(mine['gems'][g]['block'] == gb[g], f'{g} 블록 mine ↔ visual')
    forb = set(vis['blocks']['forbidden'])
    for b in allb:
        need(b.startswith('minecraft:') and b not in forb and 'redstone' not in b, f'쓰면 안 되는 블록: {b}')
    # 0.3.6.1: 팩이 모습을 바꾸는 보석 블록 6개는 이 팩의 다른 세계 어디에도 없어야 한다 (미궁 층·마을·구역 조각·광산 장식)
    gem_blocks = set(gb.values())
    elsewhere = collateral_uses(gem_blocks)
    need(not elsewhere, f'보석 블록이 다른 곳에도 쓰임 (팩이 그 모습까지 바꿈): {elsewhere[:6]}')
    notes.append('보석 블록 6개 (팩이 모습을 바꿈): ' + ' · '.join(f"{g}={gb[g].split(':')[1]}" for g in GEMS) + ' — 미궁·마을·구역·광산 장식에 0칸')
    for x in lv:
        dep = x['depleted_block']
        need(dep == vis['blocks']['depleted'][str(x['n'])], f"{x['n']} 빈 광맥 mine ↔ visual")
        need(dep not in allb and dep not in forb, f"{x['n']} 빈 광맥 블록이 광석·보석 블록")
        pal = x['palette']
        used = set(pal['wall']) | set(pal['floor']) | {pal['post'], pal['beam']} | set(pal['decor']) | set(x['lighting']['sources'])
        used = {'minecraft:' + u.split('@')[0] for u in used}
        need(not (used & set(allb)), f"{x['n']} 장식·벽에 광석·보석 블록: {used & set(allb)}")
        need(dep not in used, f"{x['n']} 빈 광맥 블록이 그 층 벽·바닥·장식과 같음")

    # ── 5. 레시피 ──
    sm = mat['smelting']
    need(len(sm) == 6 and [r['result'] for r in sm] == ingots, '제련 6 (금속마다 1)')
    for k, r in enumerate(sm):
        need(r['materials'] == {ores[k]: 2} and r['station'] == 'smelter' and r['amount'] == 1, f"제련 {r['id']}")
    golds = [r['gold'] for r in sm]
    need(golds == sorted(golds), '제련 골드 순')
    cv = mat['carving']
    need(len(cv) == 6 and sorted(next(m for m in r['materials'] if m in GEMS) for r in cv) == sorted(GEMS), '새기기 6 (보석마다 1)')
    for r in cv:
        need(r['result'] in ('lesser_enhance_stone', 'greater_enhance_stone', 'supreme_enhance_stone') and r['amount'] == 2, f"새기기 {r['id']}")
        need(r['id'] not in recipes_now or (migrated and recipes_now[r['id']].get('station') == 'smelter'), f"새기기 id 가 지금 recipes.yml 과 겹침: {r['id']}")
        for m in r['materials']:
            need(m in items_now or m in mat['items'], f"새기기 재료 없음: {m}")
    pr = mat['pickaxe_recipes']
    need([r['result'] for r in pr] == picks[1:], '곡괭이 레시피 5 (구리는 레시피 없음)')
    for k, r in enumerate(pr, 2):
        mats = r['materials']
        need(mats.get(picks[k - 2]) == 1, f"{r['id']} 앞 곡괭이")
        # 0.3.6.1 주인 결정: "철 곡괭이로 업글하려면 철 주괴가 필요한게 정상" — 제 금속 주괴 + 같은 등급 보석 (앞 곡괭이로 느리게 캠)
        need(ingots[k - 1] in mats and GEMS[k - 1] in mats, f"{r['id']} 제 금속 주괴·같은 등급 보석")
        need(not any(m in mats for m in ingots[:k - 1] + GEMS[:k - 1]), f"{r['id']} 앞 금속·앞 보석을 씀 (주인 결정과 다름)")
        need(not any(m in mats for m in ingots[k:] + GEMS[k:]), f"{r['id']} 윗 금속을 씀 (앞 곡괭이로 못 캠)")
        prev_mines = set(mine['pickaxes'][picks[k - 2]]['mines'])
        need(ores[k - 1] in prev_mines and GEMS[k - 1] in prev_mines, f"{r['id']} 재료를 앞 곡괭이로 캘 수 없음 (순환)")
        need(r['station'] == 'smelter' and r['category'] == 'tool' and 'level_req' not in r, f"{r['id']} station/category/레벨 조건")
        for m in mats:
            need(m in items_now or m in mat['items'], f"{r['id']} 재료 없음: {m}")
        need(mine['pickaxes'][r['result']]['recipe']['materials'] == mats, f"{r['id']} mine ↔ materials 레시피")
    for r in sm + cv + pr:
        if migrated:
            now = recipes_now.get(r['id']) or {}
            need(now.get('station') == 'smelter' and now.get('materials') == r['materials'] and now.get('gold') == r['gold'],
                 f"recipes.yml {r['id']} ≠ 계약 (station·재료·골드)")
        else:
            need(r['id'] not in recipes_now or r['id'] in ingots, f"레시피 id 겹침: {r['id']}")

    # ── 6. 바꿈 ──
    conv = mat['conversion']['map']
    need(sorted(conv) == sorted(RETIRED), '바꿈 표 = 옛 8개')
    for o, n in conv.items():
        slot = mat['retired'][o]['slot']
        need((slot == 'monster') == (n in MONSTER), f'{o} → {n} 칸 종류')
        need(slot == 'monster' or n in ores, f'{o} → {n} 이 광석이 아님')
        need(mat['retired'][o]['ratio'] == '1:1', f'{o} 1:1')
    need({conv[o] for o in conv if mat['retired'][o]['slot'] == 'monster'} == set(MONSTER), '몬스터 칸 → 새 몬스터 재료 3')
    for k in MONSTER:
        need(mat['items'][k]['floor'] in (5, 7, 9), f'{k} 층 5·7·9')

    # ── 7. 생성기 규칙 ──
    g = mat['generator_rules']
    need(abs(g['ing_share'] - 0.20) < 1e-9, 'ING_SHARE = 0.20 (주인 결정 4)')
    mc = g['metal_choice']
    need(mc['not_a_band_table'] is True, '금속 = 띠 표가 아님')
    prev_pos = 0
    for key, e in mc['examples_n10'].items():
        split = e['split_of_10']
        ranks = [METALS.index(m) + 1 for m, _ in split]
        need(sum(n for _, n in split) == 10 and len(split) in (1, 2), f'금속 예 {key} 개수')
        need(len(split) == 1 or (ranks[1] == ranks[0] + 1 and all(n >= 1 for _, n in split)), f'금속 예 {key} 이웃 두 금속만')
        need(1 <= e['pos'] <= 6 and abs(e['pos'] * 8 - round(e['pos'] * 8)) < 1e-9, f'금속 예 {key} pos')
    dor = g['dungeon_ore']
    need(sorted(int(k) for k in dor['per_run']) == list(range(1, 11)), '던전 광석 모든 층 (R §3-10)')
    for f, ms in dor['metals'].items():
        need(abs(sum(ms.values()) - 1) < 0.01 and set(ms) <= set(METALS) and len(ms) <= 2, f'던전 광석 {f}층 금속 비율')
        need(dor['per_run'][f] > 0, f'던전 광석 {f}층 0')
    need(abs(sum(dor['split'].values()) - 1) < 1e-9, '던전 광석 집 비율 합')
    need('drops_reserved' in mat and mat['drops_reserved']['owner'] == 'Q3', '몹 주제 드롭 자리 (Q3)')
    keep = ' '.join(mat['drops_reserved'].get('must_keep', []))
    need(all(k in keep for k in MONSTER) and 'conversion.map' in keep, '드롭 단계가 지킬 것에 새 몬스터 재료 3·바꿈 표 (주인 결정 5)')

    # ── 8. 판매 ──
    t = mat['sell']['table']
    for kind in ('ore', 'ingot', 'gem'):
        vals = [t[str(k)][kind] for k in range(1, 7)]
        need(vals == sorted(vals), f'판매가 {kind} 순')
    for k in range(1, 7):
        need(t[str(k)]['ingot'] < 2 * t[str(k)]['ore'] + t[str(k)]['smelt_gold'], f'{k} 녹여 팔면 이득')
        need(t[str(k)]['smelt_gold'] == sm[k - 1]['gold'], f'{k} 제련 골드 ↔ 판매표')

    # ── 9. 글 (주인 결정 4: 층·Lv·단계 글자 없음) ──
    for i, v in mat['items'].items():
        for fld in ('name', 'lore', 'sources_text'):
            s = v.get(fld) or ''
            if v['kind'] in ('ore', 'ingot', 'gem', 'pickaxe'):
                need(not LABEL_RE.search(s), f'{i}.{fld} 에 층·Lv·단계 글자: {s}')
            need(hangul(v['name']), f'{i} 이름이 한글이 아님')
    for x in lv:
        need(not LABEL_RE.search(x['atmosphere']), f"{x['n']} 분위기 글에 층·Lv 글자")
    need(not LABEL_RE.search(mat['codex']['mine_line'].split('—')[0]), '도감 광산 줄')

    # ── 10. 그림 ──
    icon_ids = ores + ingots + GEMS + MONSTER + DROP_PARTS
    need(sorted(vis['icons']) == sorted(icon_ids), '아이콘 27개 = 광석·주괴·보석·새 몬스터 재료·몹 주제 부위')
    seen = set()
    for i, v in vis['icons'].items():
        need(all(HEX.match(c) for c in v['palette']) and 4 <= len(v['palette']) <= 6, f'{i} 팔레트')
        key = (v['style'], tuple(v['palette']))
        need(key not in seen, f'{i} 아이콘이 다른 것과 같음')
        seen.add(key)
    need(sorted(vis['pickaxes']) == sorted(picks), '곡괭이 3D 6개')
    budgets = [vis['pickaxes'][p]['element_budget'] for p in picks]
    need(budgets == sorted(budgets) and budgets[-1] <= 720, '곡괭이 요소 예산')
    need(len({vis['pickaxes'][p]['style'] for p in picks}) == 6, '곡괭이 모양 6개가 다르지 않음')
    # 0.3.6.1 주인 결정 ("삐쭉 튀어나온 부분이 별로"): 보석 결정 ItemDisplay 없음 — 보석 블록 6개를 팩이 새 광석 그림으로
    need('gem_nodes' not in vis and all('node_model' not in mine['gems'][g] for g in GEMS), '보석 결정 모델이 남음 (0.3.6.1: 네모난 광석 블록만)')
    for gid in GEMS:
        gv = vis['blocks']['gems'][gid]
        need(gv.get('model') == gv.get('texture') == f'labyrinth:block/mine/gem_{gid}', f'{gid} 보석 블록 모델·그림 이름')
        lk = gv.get('look') or {}
        need(lk.get('base') in vis['gem_blocks']['texture']['bases'] and len(lk.get('palette') or []) == 4 and all(HEX.match(c) for c in lk['palette']),
             f'{gid} 보석 블록 그림 (바탕·4색)')
        need(bool(gv.get('natural')), f'{gid} 자연 생성 메모 없음')
    looks = [(vis['blocks']['gems'][g]['look']['base'], vis['blocks']['gems'][g]['look']['palette'][2]) for g in GEMS]
    need(len(set(looks)) == 6, '보석 블록 그림 6개가 서로 다르지 않음')
    closed = gdd_closed_lists()
    for role in ('miner', 'smelter'):
        n = vis['npcs'][role]
        ss = n['skin_style']
        need(ss['outfit'] in closed['outfit'] and ss['hair'] in closed['hair'] and set(ss['accessories']) <= closed['accessories'],
             f'{role} 스킨이 GDD §14.5 닫힌 목록 밖 (같은 그림 수준 — 주인 결정 6)')
        need(len(ss['palette']) == 6 and all(HEX.match(c) for c in ss['palette']), f'{role} 스킨 팔레트')
        need(hangul(n['name']) and n['name'] == dist['npcs'][role]['name'], f'{role} 이름 (visual ↔ district)')
    need(vis['npcs']['smelter']['name'].startswith('제련공 ') and len(vis['npcs']['smelter']['name']) > 4, '제련공 이름 (주인 결정 6)')
    names_now = {(v.get('name') or '') for v in (yaml.safe_load(open(CONTENT / 'npcs.yml', encoding='utf-8')) or {})['npcs'].values()}
    npcs_now = (yaml.safe_load(open(CONTENT / 'npcs.yml', encoding='utf-8')) or {})['npcs']
    for role in ('miner', 'smelter'):
        same = [k for k, v in npcs_now.items() if (v.get('name') or '') == vis['npcs'][role]['name']]
        need(not same or (migrated and all(npcs_now[k].get('role') == role for k in same)), f'{role} 이름이 지금 NPC 와 겹침')

    # ── 11. 광산 마을 ──
    pcs = dist['pieces']
    for i, a in enumerate(pcs):
        for b in pcs[i + 1:]:
            need(not boxes_overlap(a['box'], b['box'], 1), f"조각 겹침 (+1칸) {a['piece']} · {b['piece']}")
        need(min(a['box'][0], a['box'][2]) >= dist['world_shipped']['village_protect_max_x'] + 1, f"{a['piece']} 이 마을 다듬은 칸과 겹침")
    sm_p = next(p for p in pcs if p['piece'] == 'smelter')
    need(sm_p['size'] == [13, 18, 12], '제련소 크기 13×18×12 (V · R §3-20)')
    w = sm_p['box'][2] - sm_p['box'][0] + 1
    d = sm_p['box'][3] - sm_p['box'][1] + 1
    need((w, d) == (13, 12), f'제련소 상자 {w}×{d}')
    for k, v in dist['npcs'].items():
        x, z = v['spot_east']
        own = next(p for p in pcs if p['piece'] == v['piece'])
        need(not (own['box'][0] <= x <= own['box'][2] and own['box'][1] <= z <= own['box'][3]), f'{k} NPC 가 건물 안')
        need(abs(x - (own['box'][0] + own['box'][2]) / 2) + abs(z - (own['box'][1] + own['box'][3]) / 2) <= 12, f'{k} NPC 가 건물에서 멂')
    need(set(dist['interact']) <= set(mine['names']['interact']), '구역 interact 이름')
    need([s['id'] for s in dist['sites']][:2] == ['east', 'south_east'], '자리 후보 east → south_east (주인 결정 5)')
    need('fingerprint' in dist and 'human_if' in dist['fingerprint'], '지문 규칙 (R §2-5)')
    need('wild_border' in dist['zones'] and 'pvp_safe' in dist['zones'], '야생 경계·안전지대에 구역 상자')

    # ── 12. Java 뼈대 이름 ──
    jn = JAVA / 'mine/MineNames.java'
    if need(jn.exists(), 'Java MineNames.java 없음'):
        src = jn.read_text(encoding='utf-8')
        for s in list(mine['names']['interact']) + list(mine['names']['npc_roles']) + list(mine['names']['ext']) + ['labyrinth_mine', 'smelter', 'tool', 'mine', 'smelt']:
            need(f'"{s}"' in src, f'MineNames.java 에 "{s}" 없음')
    cv_ = (JAVA / 'core/ContentValidator.java').read_text(encoding='utf-8')
    need(('"miner"' in cv_ or 'MineNames.ROLE_MINER' in cv_) and ('"smelter"' in cv_ or 'MineNames.ROLE_SMELTER' in cv_),
         'ContentValidator.NPC_ROLES 에 miner·smelter')
    need('MineNames.CATEGORY_TOOL' in cv_ or '"tool"' in cv_, 'ContentValidator.RECIPE_CATEGORIES 에 tool')
    need('TOOL' in (JAVA / 'content/ItemType.java').read_text(encoding='utf-8'), 'ItemType.TOOL')

    # ── 13. 경제 ──
    ep = HERE / 'model/out/economy.json'
    if need(ep.exists(), 'model/out/economy.json 없음 (run_all.py)'):
        eco = json.loads(ep.read_text(encoding='utf-8'))
        for r in eco['rows']:
            c = r['craft']
            need(c['delta_solo'] <= 0.30, f"{r['tier']} 솔로 제작 시간 +{c['delta_solo'] * 100:.0f}% > 30%")
            need(c['delta_4p'] <= 0.45, f"{r['tier']} 4인 제작 시간 +{c['delta_4p'] * 100:.0f}% > 45%")
            # 0.3.6.1: '그 단계 곡괭이' = 그 단계 금속을 캘 수 있는 가장 낮은 곡괭이 (한 단계 위까지 캠) — 한도는 0.3.6 그대로 20/25%
            need(r['gold']['band_pickaxe'] == picks[max(0, max(METALS.index(k) for k in r['craft']['new_solo']['ingots']) - REACH_ABOVE)]
                 if r['craft']['new_solo']['ingots'] else True, f"{r['tier']} 표 E 곡괭이가 그 단계 금속을 캘 수 있는 가장 낮은 곡괭이가 아님")
            need(r['gold']['ratio_with_sale'] <= GOLD_WITH_SALE_MAX, f"{r['tier']} 광산 골드 {r['gold']['ratio_with_sale'] * 100:.0f}% (판매 포함) > {GOLD_WITH_SALE_MAX:.0%}")
            need(r['gold']['ratio'] <= GOLD_DROP_MAX, f"{r['tier']} 광산 골드 {r['gold']['ratio'] * 100:.0f}% (드롭만) > {GOLD_DROP_MAX:.0%}")
        st = eco.get('stretch') or {}
        need(st.get('reach_above') == REACH_ABOVE and abs(st.get('factor', 0) - mine['rules']['stretch_factor']) < 1e-9, 'economy.json 한 단계 위 표 (표 G)')
        for k, v in (st.get('by_metal') or {}).items():
            need(v['own_seconds'] < v['slow_seconds'] and v['own_per_min'] >= v['slow_per_min'], f'{k}: 제 곡괭이가 한 단계 아래 곡괭이보다 빠르지 않음')
        need('stamina' not in eco, 'economy.json 에 기력이 남음 (계약 §0-1)')
        pj = json.loads((HERE / 'model/out/proto036.json').read_text(encoding='utf-8'))
        for f, tgt in pj['dungeon_ore_target'].items():
            got = sum(pj['dungeon_ore_check'][f].values())
            need(abs(got - tgt) <= max(1.0, 0.1 * tgt), f'{f}층 던전 광석 {got} ≠ 목표 {tgt}')
        need(pj['enhance']['collisions'] == 0 and not pj['enhance']['problems'] and not pj['enhance']['no_ingot_mid_high'], '강화 시제품 문제')
        need(all(v == 0 for v in pj['enhance']['cheaper'].values()), '보스 장비가 더 싼 단계')

    # ── 13b. 이름이 Paper 26.3 API 에 있는가 (javap — jar 가 없으면 건너뜀) ──
    api = paper_api_names()
    if api is None:
        notes.append('Paper API 이름 검사 건너뜀 (paper-api 26.3 jar 또는 javap 없음)')
    else:
        blocks_used = set(allb) | set(forb) | {x['depleted_block'] for x in lv}
        for x in lv:
            pal = x['palette']
            blocks_used |= {'minecraft:' + u.split('@')[0] for u in
                            set(pal['wall']) | set(pal['floor']) | {pal['post'], pal['beam']} | set(pal['decor']) | set(x['lighting']['sources'])}
        for b in sorted(blocks_used):
            need(b.split(':', 1)[1].upper() in api['BlockType'], f'블록이 26.3 에 없음: {b}')
        for x in lv:
            need(x['biome'].split(':', 1)[1].upper() in api['Biome'], f"바이옴이 26.3 에 없음: {x['biome']}")
            need(x['regen_fx'] in api['Particle'], f"입자가 26.3 에 없음: {x['regen_fx']}")
        fb = vis['feedback']
        sounds = {fb['harvest']['sound'][0]} | {sd[0] for sd in fb['lift']['sounds']} | {v['regen_fx']['sound'] for v in vis['levels'].values()}
        for sd in sorted(sounds):
            need(sd in api['Sound'], f'소리가 26.3 에 없음: {sd}')
        for e in ('MANNEQUIN', 'ITEM_DISPLAY', 'BLOCK_DISPLAY', 'TEXT_DISPLAY', 'INTERACTION', 'ITEM'):
            need(e in api['EntityType'] and e in ' '.join(mine['world']['safety']), f'스폰 화이트리스트 {e}')
        for ef in ('HASTE', 'CONDUIT_POWER', 'BLINDNESS'):
            need(ef in api['PotionEffectType'], f'효과가 26.3 에 없음: {ef}')
        notes.append(f"Paper API 이름 검사: 블록 {len(blocks_used)} · 바이옴 6 · 입자 · 소리 {len(sounds)} ({api['_jar']})")
    # 미궁 층이 같은 블록을 쓰는 곳 (오류 아님 — outside_mine 안내가 덮음, CONTRACT §2.3)
    floors = (yaml.safe_load(open(CONTENT / 'floors.yml', encoding='utf-8')) or {}).get('floors') or {}
    hits = []
    for fno, f in floors.items():
        palette = (f or {}).get('palette') or {}
        used = {('minecraft:' + str(b).lower()) for v in palette.values() if isinstance(v, list) for b in v}
        both = sorted(b.split(':')[1] for b in used & set(allb))
        if both:
            hits.append(f"{fno}층 {'·'.join(both)}")
    if hits:
        notes.append('미궁 층이 쓰는 광산 블록 (광산 밖 안내로 덮음): ' + ' / '.join(hits))
        need('미궁' in mine['rules']['outside_mine'], '미궁 층이 광산 블록을 쓰는데 outside_mine 규칙이 미궁을 말하지 않음')

    # ── 14. JSON 이 params 와 같은가 ──
    r = subprocess.run([sys.executable, '-B', str(HERE / 'model/build_contract.py'), '--check'], capture_output=True, text=True)
    need(r.returncode == 0, 'JSON 이 params.py 와 다름 — run_all.py 를 돌릴 것:\n' + r.stdout + r.stderr)
    notes.append(f"새 id {len(mat['new_ids'])} · 층 {len(lv)} · 블록 {len(set(allb))} · 레시피 +{len(sm) + len(cv) + len(pr)} · 조각 {len(pcs)}")


if __name__ == '__main__':
    main()
    for n in notes:
        print('[계약]', n)
    if errors:
        print(f'[계약 검사] 오류 {len(errors)}')
        for e in errors:
            print('  ✗', e)
        sys.exit(1)
    print('[계약 검사] 오류 0')
