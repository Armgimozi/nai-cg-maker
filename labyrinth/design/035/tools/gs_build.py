# -*- coding: utf-8 -*-
"""TASK C 명세 생성 → design2/gear_spec.json · gear_spec.md"""
import json, math, collections, statistics as S
from gs_core import *          # noqa
from gs_loot import *          # noqa
from gs_data import (ARMOR, NEW_SHAPES, EXR, SHOP_PRICE, SHOP_UNLOCK, ELITE, BOSS, FLOOR_NAME, GIMMICK, PAL)

old, new, allw, best = all_weapons()

# ───────────── 방어구 6세트 ─────────────
WEIGHT = {'heavy': 1.0, 'light': 0.62, 'cloth': 0.42}
ARAR = {'uncommon': 1.0, 'rare': 1.05, 'epic': 1.1, 'legendary': 1.18}
SHARE = {'head': 0.20, 'chest': 0.35, 'legs': 0.27, 'feet': 0.18}
SLOT_SUF = {'head': 'helm', 'chest': 'chest', 'legs': 'legs', 'feet': 'boots'}
LOOK_CLS = {'heavy': ['guardian', 'berserker'], 'light': ['hunter', 'shadow'], 'cloth': ['arcanist', 'priest']}
armor_items, armor_sets, armor_recipes = {}, {}, {}
REC_PAT = {  # 그 층 같은 희귀도 세트 레시피를 본뜸
    'mycel_carapace': {'head': ({'hypha_thread': 6, 'spore_cap': 8, 'dim_essence': 1}, 490),
                       'chest': ({'hypha_thread': 8, 'spore_cap': 12, 'dim_essence': 1, 'brood_core': 1}, 700),
                       'legs': ({'hypha_thread': 7, 'spore_cap': 10, 'dim_essence': 1, 'brood_core': 1}, 600),
                       'feet': ({'hypha_thread': 5, 'spore_cap': 7, 'dim_essence': 1}, 420)},
    'sluice_diver': {'head': ({'eel_scale': 8, 'brine_pearl': 6, 'labyrinth_essence': 1}, 490),
                     'chest': ({'eel_scale': 12, 'brine_pearl': 8, 'labyrinth_essence': 1, 'verdigris_plate': 1}, 700),
                     'legs': ({'eel_scale': 10, 'brine_pearl': 7, 'labyrinth_essence': 1, 'verdigris_plate': 1}, 600),
                     'feet': ({'eel_scale': 7, 'brine_pearl': 5, 'labyrinth_essence': 1}, 420)},
    'index_bulwark': {'head': ({'old_page': 14, 'ink_essence': 9, 'radiant_essence': 1}, 4800),
                      'chest': ({'old_page': 20, 'ink_essence': 13, 'radiant_essence': 1, 'forbidden_seal': 1}, 6900),
                      'legs': ({'old_page': 17, 'ink_essence': 11, 'radiant_essence': 1, 'forbidden_seal': 1}, 5900),
                      'feet': ({'old_page': 12, 'ink_essence': 8, 'radiant_essence': 1}, 4100)},
}
for a in ARMOR:
    L, rar, look = a['L'], a['rarity'], a['look']
    R = req_value(L)
    dsum = (3 + 0.95 * L) * WEIGHT[look] * ARAR[rar]
    pm = PRIM(L) * RC[rar]
    pieces = []
    srcs = sorted(set(sum((KIND_SRC[k] for k in a['kind']), [])))
    for slot in ('head', 'chest', 'legs', 'feet'):
        iid = f"{a['id']}_{SLOT_SUF[slot]}"
        pieces.append(iid)
        dm = dsum * SHARE[slot]
        st = {'defense': [max(1, int(round(dm * 0.9))), max(int(round(dm * 0.9)) + 1, int(round(dm * 1.05)))]}
        mains = a['main'].split('|')
        for ms in mains:
            st[ms] = rng(ms, pm * SHARE[slot] * 1.7 * (0.7 if len(mains) > 1 else 1.0))
        for k in a['subs'][slot]:
            if k == 'move_speed' and slot == 'feet':
                st[k] = rng(k, BASE[k](L) * RC[rar])
            elif k in STATS6:
                st[k] = rng(k, pm * 0.6 * SHARE[slot] * 2.0)
            else:
                st[k] = rng(k, BASE[k](L) * RC[rar] * SHARE[slot] * 2.0)
        it = {'name': a['names'][slot], 'type': 'armor', 'armor_slot': slot, 'armor_set': a['id'], 'rarity': rar,
              'level_req': L}
        if look == 'cloth':
            it['requires_any'] = {'INT': R, 'WIS': R}
        else:
            it['requires'] = {('VIT' if look == 'heavy' else 'DEX'): R}
        it.update({'floor': a['floor'], 'classes': LOOK_CLS[look], 'stats': st, 'set_bonus': a['id'], 'pool': False,
                   'sources': srcs, 'model': {'shape': a['shapes'][slot], 'length': 1.0},
                   'texture': {'style': a['style'], 'palette': a['palette']}, 'lore': a['lore']})
        it['_kind'] = a['kind'][0]
        it['_id'] = iid
        armor_items[iid] = it
        if 'F' in a['kind']:
            mats, gold = REC_PAT[a['id']][slot]
            armor_recipes[iid] = {'result': iid, 'category': 'armor', 'station': 'blacksmith', 'materials': mats,
                                  'gold': gold, 'level_req': L}
    armor_sets[a['id']] = {'name': a['name'], 'look': look, 'back': a['back'], 'pieces': pieces, 'bonuses': a['bonuses']}

ARM_IN = {k: dict(v, floor=v['floor']) for k, v in armor_items.items()}
tables, changes = build_tables(new, ARM_IN)
homes = homes_of(tables, allw)
# M 배율 맞추기: 그 층 몬스터·상자 무기(내 능력치) 기대 회차 가운데값 → 목표 (몇 번 되풀이해 맞춘다)
MF = {f: 1.0 for f in range(1, 11)}
for _ in range(8):
    tables, changes = build_tables(new, ARM_IN, MF)
    homes = homes_of(tables, allw)
    for f in range(1, 11):
        ids = (tables.get(tid_common(f)) or {}).get('entries', [{}])[0].get('one_of', [])
        rs = [runs_for(wid, allw, tables, homes) for wid in ids]
        rs = [r for r in rs if r]
        if rs:
            med = S.median(rs)
            MF[f] = round(min(1.0, MF[f] * med / M_TARGET[f]), 4)
tables, changes = build_tables(new, ARM_IN, MF)
homes = homes_of(tables, allw)

# 새 무기 획득처 (테이블, chance)
def source_of(w):
    f = w['F']
    k = w['kind']
    if k == 'P':
        return {'kind': 'P', 'table': 'npcs.yml merchant.shop', 'price': SHOP_PRICE[w['id']],
                'unlock_floor': SHOP_UNLOCK[w['id']], 'note': f"{SHOP_UNLOCK[w['id']]}층 보스를 한 번 잡은 뒤 진열"}
    tid = {'M': tid_common(f), 'T': tid_trial(f), 'S': tid_special(f), 'V': tid_hoard(f), 'E': floor_tables(f)[1]}[k]
    t = tables[tid]
    for e in (t.get('entries') or []) + (t.get('guaranteed') or []):
        if w['id'] in (e.get('one_of') or []):
            return {'kind': k, 'table': tid, 'chance': e.get('chance', 1.0), 'pool': len(e['one_of']),
                    'guaranteed': e in (t.get('guaranteed') or [])}
    raise KeyError(w['id'])

for w in new.values():
    w['source'] = source_of(w)
    w['runs'] = runs_for(w['id'], allw, tables, homes) if w['kind'] != 'P' else None
for w in old.values():
    w['runs'] = runs_for(w['id'], allw, tables, homes)

GOLD = {f: run_gold(f) for f in range(1, 11)}

# 대장간 회차 (구간 기준 레시피)
FORGE = {}
for b in range(1, 11):
    ref, top = craft_ref(allw, b)
    cands = [w for w in old.values() if w['band'] == b and 'craft' in (w['src'] or []) and (RAR.index(w['rar']), w['L']) == top]
    rid = cands[0]['id']
    r = RECIPES[rid]
    runs, gruns, det, g = forge_cost(cands[0]['F'], tables, r)
    FORGE[b] = dict(recipe=rid, ref_tp=ref, mat_runs=runs, gold=r['gold'], gold_runs=gruns, detail=det, gold_per_run=g,
                    level=top[1], rarity=RAR[top[0]])

# ───────────── 검사 (테스트로 옮길 것) ─────────────
problems = []
def check(cond, msg):
    if not cond:
        problems.append(msg)

KINDS_OF = lambda w: {'M+F': ['M', 'F']}.get(w['kind'], [w['kind']])
band_rows = collections.defaultdict(list)
for w in allw.values():
    band_rows[w['band']].append(w)
DIR_ALL = list(DIRS.keys())
for b in range(1, 11):
    ws = band_rows[b]
    normal = [w for w in ws if not w['mythic']]
    st = collections.Counter(w['style'] for w in normal)
    check(len(normal) >= 22, f'{blabel(b)} 무기 {len(normal)} < 22')
    check(st['melee'] >= 5 and st['ranged'] >= 3 and st['caster'] >= 3, f'{blabel(b)} 방식 {dict(st)}')
    rq = collections.Counter()
    for w in normal:
        for r in w['req'].split('|'):
            rq[r] += 1
    for s6 in STATS6:
        check(rq[s6] >= (1 if b == 1 else 2), f'{blabel(b)} 요구 {s6} {rq[s6]}')
    dirs = set(w['dir'] for w in normal)
    check(set(DIR_ALL) <= dirs, f'{blabel(b)} 방향 빠짐 {set(DIR_ALL) - dirs}')
    kinds = set(k for w in normal for k in KINDS_OF(w))
    check(len(kinds) >= 5, f'{blabel(b)} 획득처 종류 {kinds}')
    ref = FORGE[b]['ref_tp']
    for w in ws:
        if w['new'] and w['kind'] in 'MTSVE':
            check(abs(w['tp'] / ref - 1) <= 0.05 + 1e-9, f"{w['id']} 티어 위력 {w['tp'] / ref - 1:+.1%}")
for w in new.values():
    check(len(w['udesc']) <= 34, f"{w['id']} 고유 설명 {len(w['udesc'])}자")
    if w['eff'] == 'longshot':
        check(w['style'] in ('ranged', 'caster'), f"{w['id']} longshot 은 원거리·시전만")
# 영웅 이상 무기 획득처 1곳
top_home = collections.Counter()
for w in allw.values():
    if RAR.index(w['rar']) >= 3:
        kinds = KINDS_OF(w)
        check(len(kinds) == 1, f"{w['id']} 영웅+ 획득처 {kinds}")
        top_home[kinds[0]] += 1
# 같은 아이템이 두 테이블에
seen = collections.defaultdict(set)
for tid, t in tables.items():
    for e in (t.get('entries') or []) + (t.get('guaranteed') or []):
        for x in (e.get('one_of') or ([e['item']] if 'item' in e else [])):
            if x in new or x in armor_items:
                seen[x].add(tid)
for x, ts in seen.items():
    check(len(ts) == 1, f'{x} 테이블 {ts}')
# 무기 스킬 이름 중복
names = collections.Counter(w['skill']['name'] for w in new.values() if w.get('skill'))
check(all(n == 1 for n in names.values()), f'스킬 이름 중복 {[k for k, n in names.items() if n > 1]}')
# 획득처별 기대 회차 범위
WINDOW = {'M': (1.0, 6.0), 'T': (3.0, 7.0), 'V': (3.0, 7.0), 'S': (5.0, 10.0), 'E': (3.0, 7.0)}
for w in new.values():
    if w['kind'] in WINDOW and w['runs']:
        lo, hi = WINDOW[w['kind']]
        check(lo <= w['runs'] <= hi, f"{w['id']} ({w['kind']}) 기대 {w['runs']:.1f}회")

# ───────────── 직업 스킬 위력 (무기 종류 없이) ─────────────
OLD_SCALE = {'sword_shield': 1.00, 'greatsword': 1.55, 'bow': 1.30, 'staff': 1.10, 'scepter': 0.95, 'dagger': 0.62}
CLASS_SCALE = {'guardian': 1.00, 'berserker': 1.55, 'hunter': 1.30, 'arcanist': 1.05, 'priest': 0.90, 'shadow': 0.62}
def spm(w):
    """skill_power_mult — 시전 무기 1.05 (기본 공격이 약한 대신 스킬 위력), 나머지 1.0."""
    return 1.05 if w['style'] == 'caster' else 1.0
for w in allw.values():
    w['spm'] = spm(w)
    w['skill_power'] = w['tp'] * w['spm']

# ───────────── JSON ─────────────
def items_yml(w):
    st = dict(w['stats'])
    it = {'name': w['name'], 'type': 'weapon', 'attack': {'style': w['style'], 'speed': w['speed']}, 'rarity': w['rar'],
          'level_req': w['L']}
    R = req_value(w['L'])
    if R:
        rs = w['req'].split('|')
        if len(rs) == 1:
            it['requires'] = {rs[0]: R}
        else:
            it['requires_any'] = {r: R for r in rs}
    it.update({'floor': w['F'], 'classes': classes_for(w['req']), 'stats': st, 'pool': False,
               'sources': KIND_SRC[w['kind']]})
    if w.get('skill'):
        it['weapon_skills'] = [w['skill']]
    u = {'id': w['eff'], 'name': w['uname']}
    u.update({k: v for k, v in w['params'].items()})
    it['unique'] = u
    if w['spm'] != 1.0:
        it['skill_power_mult'] = w['spm']
    it['model'] = {'shape': w['shape'], 'length': 1.0}
    it['texture'] = {'style': w['tex_style'], 'palette': w['palette']}
    it['lore'] = w['lore']
    return it

weapons_json = {}
for w in sorted(new.values(), key=lambda w: (w['band'], 'MTSVEP'.index(w['kind']), w['id'])):
    shp = NEW_SHAPES.get(w['shape'])
    weapons_json[w['id']] = {
        **items_yml(w),
        'direction': w['dir'],
        'model_recipe': {'shape': w['shape'], 'new_silhouette': bool(shp), 'palette': w['palette'], 'style': w['tex_style'],
                         'notes': (f"새 실루엣 {shp['name']} — new_shapes.{w['shape']} 참고, 테마는 id 로 ({w['id'].split('_')[0]})"
                                   if shp else f"기존 템플릿 {w['shape']} 재사용 — 층 테마 장식(dress_blade/dress_shaft/dress_bow)·새 색")},
        'source': w['source'],
        'band': blabel(w['band']),
        'tier_power': round(w['tp'], 2),
        'vs_forge': round(w['tp'] / FORGE[w['band']]['ref_tp'] - 1, 3),
        'unique_strength': w['strength'],
        'unique_tooltip': w['utip'],
        'expected_runs_fit': None if w['runs'] is None else round(w['runs'], 1),
    }

existing_changes = {}
for w in sorted(old.values(), key=lambda w: (w['band'], w['id'])):
    ch = {'attack': {'style': w['style'], 'speed': w['speed']}, 'remove': ['weapon_type']}
    if w['id'] in EXR:
        R = req_value(w['L'])
        rs = EXR[w['id']][0].split('|')
        if len(rs) == 1:
            ch['requires'] = {rs[0]: R}
            if rs[0] != w['req_old']:
                ch['stats_rename'] = {w['req_old']: rs[0]}
        else:
            ch['requires'] = None
            ch['requires_any'] = {r: R for r in rs}
        ch['classes'] = classes_for(EXR[w['id']][0])
        ch['why'] = EXR[w['id']][1]
    if w['spm'] != 1.0:
        ch['skill_power_mult'] = w['spm']
    existing_changes[w['id']] = ch

loot_json = {}
for tid, c in sorted(changes.items()):
    loot_json[tid] = {'op': c['op'], 'note': c['note'], **{k: v for k, v in c['table'].items()}}

shop_json = [{'item': w['id'], 'price': SHOP_PRICE[w['id']], 'unlock_floor': SHOP_UNLOCK[w['id']]}
             for w in new.values() if w['kind'] == 'P']

SPECIAL = {
    'config': {
        'file': 'plugin/src/main/resources/dungeon.yml',
        'block': {'special_trial': {
            'enabled': True, 'chance': SPECIAL_Q, 'pity_visits': 4, 'xp_bonus': 0.5,
            'conditions': {
                'swift': {'time_factor': 0.7, 'min_seconds': 40, 'default_seconds': 75},
                'unscathed': {'hits': 2, 'per_member': 1, 'min_damage': 0.03},
                'abstain': {'potions': True, 'scrolls': True},
                'flawless': {}}}},
        'floors_override': 'floors.yml 층마다 special_trial: {conditions: [...], seconds: N} (없으면 아래 기본표)'},
    'per_floor': {},
    'tables': {f: tid_special(f) for f in range(1, 11)},
    'texts': {
        'board': '<gold><b>✦ 특별 시련: {title} ✦</b></gold>\\n{rules}\\n<yellow>{condition}</yellow>',
        'title': '<gold><b>특별 시련</b></gold>', 'subtitle': '<gray>{condition_short}',
        'chat': '<gold>✦ 특별 시련</gold> <gray>— 오늘의 방은 무언가 다르다. <yellow>{condition}</yellow>',
        'broken': '<gray>특별 조건이 깨졌다 — 이번 상자는 평소와 같다.',
        'kept': '<gold><b>특별 시련 성공!</b></gold> <gray>상자 하나가 더 놓였다.',
        'conditions': {'swift': '모래시계가 뒤집혔다. {seconds}초 안에 끝내라.',
                       'unscathed': '이 방은 상처를 세고 있다. {hits}번 넘게 다치지 마라.',
                       'abstain': '물약 냄새를 싫어하는 방이다. 아무것도 마시지 마라.',
                       'flawless': '한 번의 실수도 기억된다. 틀리지 마라.'},
        'bar': '<gold>특별 조건</gold> <gray>· {status}'},
}
COND = {1: ['flawless', 'swift'], 2: ['unscathed', 'abstain'], 3: ['abstain', 'swift'], 4: ['swift', 'unscathed'],
        5: ['swift', 'abstain'], 6: ['swift', 'unscathed'], 7: ['flawless', 'unscathed'], 8: ['flawless', 'swift'],
        9: ['flawless', 'unscathed'], 10: ['unscathed', 'abstain']}
SECONDS = {1: 60, 3: 90, 4: 42, 5: 70, 6: 84, 8: 126}     # swift: 그 기믹의 보통 걸리는 시간 × 0.7 (제한이 있으면 그 0.7)
for f in range(1, 11):
    SPECIAL['per_floor'][f] = {'gimmick': GIMMICK[f], 'conditions': COND[f], 'swift_seconds': SECONDS.get(f),
                               'table': tid_special(f),
                               'weapons': [w['id'] for w in new.values() if w['F'] == f and w['kind'] == 'S'],
                               'armor': [k for k, v in armor_items.items() if v['floor'] == f and v['_kind'] == 'S']}

TESTS = [
    dict(name='WeaponTypeGoneTest', file='plugin/src/test/java/kr/labyrinth/WeaponTypeGoneTest.java',
         checks=['items.yml 무기에 weapon_type 키가 없다 · 모든 무기에 attack{style: melee|ranged|caster, speed 0.6~2.5}',
                 'attack.style 이 모양과 맞다: BOWS(longbow…twin_bow) ⇔ ranged, 시전 모양(staff_*·scepter*·censer_staff·antler_staff·lamp_crook·thurible_rod·chime_rod) ⇔ caster',
                 'classes.yml 에 weapon_types 없음 · 툴팁(ItemTooltip.lines)·도감·대장간 필터에 "대검/한손검/활/지팡이/홀/단검" 분류 글자가 안 나온다',
                 'WeaponTypes 클래스 삭제 (또는 사용처 0) · 추천 무기 재사용 대기 −10% 없음']),
    dict(name='WeaponRequirementRuleTest (GearRequirementsDataTest 교체)', file='plugin/src/test/java/kr/labyrinth/GearRequirementsDataTest.java',
         checks=['무기: requires 1개 또는 requires_any 2개, 값은 모두 ceil(2.5×(L−1)) (2 이하면 없음) — 능력치는 무기마다 자유',
                 '방어구·방패: 겉모습 규칙 그대로 (판금 VIT · 가죽 DEX · 천 INT|WIS)',
                 'ownFloorKitFitsTheStatPointsAtItsLevel: "추천 무기" 대신 "그 층에서 요구 능력치가 직업 주 능력치(primary_stat)인 무기 중 가장 높은 것"']),
    dict(name='BandDiversityTest', file='plugin/src/test/java/kr/labyrinth/BandDiversityTest.java',
         checks=['5레벨 구간마다 (신화 제외) 무기 ≥ 22', '근접 ≥ 5 · 원거리 ≥ 3 · 시전 ≥ 3',
                 '요구 능력치 STR·DEX·INT·WIS·VIT·LUK 각각 ≥ 2 (1~5 구간은 ≥ 1, Lv1 무기는 요구 없음)',
                 '방향 12개 전부 (directions.json)', '획득처 종류 ≥ 5 (보스·대장간·몬스터·상자·시련·특별 시련·금고·미믹·정예·상인 중)']),
    dict(name='SidegradeBandTest', file='plugin/src/test/java/kr/labyrinth/SidegradeBandTest.java',
         checks=['티어 위력 TP = 피해 가운데값 × 공속 ÷ K(방식, 공속) (K: 근접 1.47 − 0.143×max(0, 공속 − 1.5) · 원거리 1.56 · 시전 1.22)',
                 '구간 대장간 기준 = 그 구간 대장간 무기(보스+대장간 포함) 중 가장 높은 단계 TP 가운데값',
                 '몬스터·상자/시련/특별 시련/금고·미믹/정예 무기의 새 무기는 기준 ±5% 안 (상인은 기준 이하)',
                 '같은 구간 같은 방향·같은 요구 능력치·같은 획득처가 겹치는 무기 쌍 없음']),
    dict(name='TopWeaponsOneHomeTest (GearRequirementsDataTest.topWeaponsHaveExactlyOneHome 갱신)',
         file='plugin/src/test/java/kr/labyrinth/GearRequirementsDataTest.java',
         checks=[f'영웅 이상 무기는 집 1곳 — 집별 수 {dict(sorted(top_home.items()))} (B 보스 · F 대장간 · M 몬스터·상자 · T 시련 · S 특별 시련 · V 금고·미믹 · E 정예)',
                 '보스 무기는 그 층 보스 테이블만, 대장간 무기는 드롭 없음, T/S/V 무기는 그 표 하나에만']),
    dict(name='LootHomesTest 갱신', file='plugin/src/test/java/kr/labyrinth/LootHomesTest.java',
         checks=['labeledTables 에 trial_gear_fNN(집 trial) · special_trial_fNN(special) · hoard_gear_fNN(hoard) 추가, gimmick_floor_N 은 장비가 trial 표로만',
                 'TAGS 에 trial→[trial] · special→[special] · hoard→[hoard] · shop→[shop] 추가 — items.yml sources 와 실제 획득처 일치',
                 '6·8·9·10층 gear_fNN_common 이 다시 있다 (영웅 몬스터·상자 무기) · 다른 층 장비 금지 그대로',
                 'gear >= 250 → gear >= 370 (무기 234 + 방어구·방패·장신구)']),
    dict(name='DropRateWindowTest', file='plugin/src/test/java/kr/labyrinth/DropRateWindowTest.java',
         checks=['순수 계산(LootRoller 규칙 + 이 명세의 1회 상수: 몹 수 GDD §16.1, 미로 상자 1~3층 8.7·4~10층 12.4, 금고 2.25, 시련 성공 0.8, 특별 0.3×0.65)',
                 '내 주 능력치 무기 하나 기대 회차: 몬스터·상자 1~6 · 시련 3~7 · 금고·미믹 3~7 · 정예 3~7 · 특별 시련 5~10 · 보스 고유(지금 테스트 유지)',
                 '대장간 기준 레시피 재료 회차 1.5~5']),
    dict(name='SpecialTrialTest (순수)', file='plugin/src/test/java/kr/labyrinth/dungeon/SpecialTrialTest.java',
         checks=['SpecialTrial.pick(seed, floor, config): 같은 시드 → 같은 결과, 1만 번에 chance ±2%, pity_visits 만큼 못 보면 다음은 확정',
                 '층마다 conditions 가 그 기믹이 지원하는 것만 (flawless 는 attempts 가 있는 lever_sequence·resonance_tune·book_cipher·gear_timing)',
                 '조건 판정: swift(경과 ≤ 초), unscathed(min_damage 이상 맞은 횟수 ≤ hits + per_member×(인원−1)), abstain(물약·주문서 사용 0), flawless(noteMistake 0)',
                 '조건이 깨져도 기믹 성공이면 gimmick_floor_N 은 그대로, special_trial_fNN 만 안 굴린다']),
    dict(name='SkillPowerTest (WeaponFreedomTest 교체)', file='plugin/src/test/java/kr/labyrinth/WeaponFreedomTest.java',
         checks=['DerivedStats.skillPower = 무기 피해 × 공속 ÷ K × skill_power_mult (무기 없음 = 맨손 3)',
                 '같은 구간 무기끼리 skill_power 최대/최소 ≤ 1.25 (지금 무기 종류 배율 1.55/0.62 = 2.5배였던 것)',
                 '공속 1.0 미만 무기의 skill_power ≤ 같은 구간 공속 1.5 무기 × 1.05 — 느린 대검이 직업 스킬을 독차지하지 않는다',
                 '직업 스킬 피해 = skill_power × (1 + 0.02×주스탯 혼합) × 스킬 배율 × classes.yml skill_scale (수호 1.00·광전 1.55·사냥 1.30·비전 1.05·사제 0.90·그림자 0.62) — 0.3.4 와 같은 단계 무기에서 ±5%']),
    dict(name='UniqueDiversityTest 갱신', file='plugin/src/test/java/kr/labyrinth/items/UniqueEffectCatalogTest.java',
         checks=['무기 234개 전부 unique 있음, id 닫힌 목록 26개, 수치 범위(max), longshot 은 원거리·시전만',
                 '같은 5레벨 구간에서 같은 방향은 최대 4개 (종류별 검사 → 구간 전체 검사로)']),
    dict(name='TooltipFitTest 그대로', file='plugin/src/test/java/kr/labyrinth/items/TooltipFitTest.java',
         checks=['새 무기 103·방어구 24 포함 전부 +0·+8·+10 에서 20줄·330px 이하', '획득처 줄: 시련(N층) · 특별 시련(N층) · 금고·미믹(N층) · 상인 핀 이름이 맞게']),
    dict(name='validate.py 새 실루엣 (리소스팩)', file='resourcepack/src/validate.py · tools/hold_preview.py',
         checks=['새 모양 15개가 voxel/weapons._TEMPLATES 또는 BOWS 에 있음, HOLD/TWO_HANDED/HEAD_SHAPES 표가 new_shapes 명세와 같음',
                 'hold_preview metrics: 1인칭 화면 덮는 비율(idle·max_central)이 같은 무게 기존 모양 ±25% 안, 손잡이(8,1,8)/(4.5,6,8) 고정',
                 'THEME_KEYS 로 새 id 가 모두 층 테마로 잡힘 (pit_* 는 style rusted_iron → forge)']),
]

spec = {
    'version': 'gear-c1 (labyrinth 0.3.4 기준, 무기 종류 없앰)',
    'summary': {
        'weapons_before': len(old), 'weapons_new': len(new), 'weapons_after': len(old) + len(new),
        'armor_sets_new': len(armor_sets), 'armor_pieces_new': len(armor_items),
        'new_silhouettes': len(NEW_SHAPES), 'existing_requires_changed': len(EXR),
        'top_weapon_homes': dict(sorted(top_home.items())), 'problems': problems,
    },
    'formulas': {
        'weapon_power': 'P(L) = 7 + 0.25×(L−1) + 0.0195×(L−1)² (GDD §16.4)',
        'rarity_damage': RM, 'rarity_stat': RC,
        'attack_K': 'K = 근접 1.47 − 0.143×max(0, 공속−1.5) · 원거리 1.56 · 시전 1.22',
        'damage_mean': '피해 가운데값 = P(L) × 희귀도 × K ÷ 공속 (정수 [lo,hi], 반폭 3~12%) — 기존 6종 배율(1.00·1.55·1.30·1.10·0.95·0.62)을 ±2% 로 다시 만든다',
        'tier_power': 'TP = 피해 가운데값 × 공속 ÷ K  (= P(L) × 희귀도)',
        'primary_stat': '요구 능력치 줄 = (1 + 0.22L) × 희귀도 계수, 굴림 ×0.85~1.15',
        'secondary': '부가 스탯 = 기준값(L) × 희귀도 계수 × 0.85~1.15 (능력치형 부가는 ×0.6). 개수: 일반·고급 1 · 희귀 2 · 영웅 3 · 전설 4 · 신화 5',
        'requires': 'ceil(2.5×(L−1)), 2 이하면 없음 — 능력치는 무기마다',
        'skill_power': 'skill_power = TP(굴린 피해로) × skill_power_mult (기본 1.0 · 시전 1.05) — 직업 스킬 = skill_power × (1+0.02×주스탯 혼합) × 스킬 배율 × classes.yml skill_scale',
        'unique_budget': 'B = clamp(0.08 + 0.6×gap, 0.04, 0.28), gap = 구간(신화 제외) 최고 P\' ÷ 이 무기 P\' − 1, P\' = TP × (1 + 부가 가치 + 0.1×스킬 수), s = B÷0.1 (효과 설계자 규칙, 종류 대신 구간 전체)',
    },
    'weapons': weapons_json,
    'existing_changes': existing_changes,
    'armor_sets': {k: {**v, 'pieces_items': {p: {kk: vv for kk, vv in armor_items[p].items() if not kk.startswith('_')} for p in v['pieces']},
                       'design': next(a for a in ARMOR if a['id'] == k)} for k, v in armor_sets.items()},
    'recipes_new': armor_recipes,
    'loot_changes': loot_json,
    'shop': {'npc': 'merchant', 'entries': shop_json, 'code': 'NpcDef.ShopEntry 에 unlock_floor (PlayerData 최고 처치 층) — 못 채우면 진열 안 함'},
    'special_trial': SPECIAL,
    'new_shapes': NEW_SHAPES,
    'theme_keys_add': {'note': '새 id 는 모두 기존 THEME_KEYS 로 잡힌다 (pit_* = style rusted_iron → forge). 추가 없음'},
    'rates': {},
    'forge': FORGE,
    'gold_per_run': GOLD,
    'm_factor': MF,
    'tests': TESTS,
}

# ── 회차 표 ──
def runs_stats(lst):
    lst = [x for x in lst if x]
    if not lst:
        return None
    return (round(min(lst), 1), round(S.median(lst), 1), round(max(lst), 1))
RATES = {}
for b in range(1, 11):
    ws = [w for w in allw.values() if w['band'] == b and not w['mythic']]
    row = {}
    for k in 'BMTSVE':
        row[k] = runs_stats([w['runs'] for w in ws if k in KINDS_OF(w)])
    fz = FORGE[b]
    row['F'] = {'recipe': fz['recipe'], 'mat_runs': round(fz['mat_runs'], 1), 'gold': fz['gold'], 'gold_runs': round(fz['gold_runs'], 2)}
    pw = [w for w in ws if w['kind'] == 'P']
    row['P'] = [{'item': w['id'], 'price': SHOP_PRICE[w['id']], 'gold_runs': round(SHOP_PRICE[w['id']] / GOLD[w['F']], 1)} for w in pw]
    RATES[b] = row
spec['rates'] = {blabel(b): v for b, v in RATES.items()}

json.dump(spec, open(D + 'gear_spec.json', 'w'), ensure_ascii=False, indent=1)
json.dump({'allw': {k: {kk: vv for kk, vv in w.items() if kk not in ('skill',)} for k, w in allw.items()}},
          open(D + 'tools/gs_state.json', 'w'), ensure_ascii=False, indent=0, default=str)
print('problems', len(problems))
for p in problems:
    print('  ', p)
print('top homes', dict(top_home))
for b, r in RATES.items():
    print(blabel(b), {k: v for k, v in r.items()})
