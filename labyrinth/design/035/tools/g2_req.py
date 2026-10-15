# -*- coding: utf-8 -*-
"""요구 능력치 다시 짜기 (주인 결정: '또는' 없음 · 2~3 능력치에 나눔 · 정체성/고유 효과 방향을 따름).

  예산  T(L) = ceil(2.75 × (L − 1)),  L ≤ 2 이면 요구 없음        (지금 한 능력치 R = ceil(2.5 × (L − 1)) 보다 10% 많다)
  나눔  두 능력치 60 / 40   ·   세 능력치 50 / 30 / 20 (L ≥ 12 부터)   — 반올림해도 합은 T
  고르기 무기: 방향(directions.json pairs_stats) + 피해 능력치(물리 STR · 마법 INT) 로 만든 후보 틀에서, 같은 띠 안
        직업마다 '세금 적게 낄 수 있는 무기' 수가 고르게, 주 능력치가 겹치지 않게, 같은 모양끼리 다르게 고른다.
        방어구: 세트마다 손으로 (겉모습 + 세트 정체성).
"""
import collections
import math

import g2_core as G

STATS = G.STATS6


def budget(L):
    if L <= 2:
        return 0
    return math.ceil(2.75 * (L - 1))


def split(L, order):
    """order = (주, 둘째[, 셋째]) → {stat: n}. L < 12 이면 셋째를 버린다."""
    T = budget(L)
    if T == 0:
        return {}
    order = list(order)
    if len(order) == 3 and L < 12:
        order = order[:2]
    if len(order) == 1:
        return {order[0]: T}
    if len(order) == 2:
        a = round(0.6 * T)
        return {order[0]: a, order[1]: T - a}
    a, b = round(0.5 * T), round(0.3 * T)
    return {order[0]: a, order[1]: b, order[2]: T - a - b}


# ── 무기 후보 틀 (방향, 피해 종류) → [순서 튜플 …]  앞이 정체성에 가깝다 ──
TPL = {
    ('bleed_crit', 'physical'): [('DEX', 'STR', 'LUK'), ('STR', 'DEX', 'LUK'), ('DEX', 'LUK', 'STR'), ('STR', 'LUK', 'VIT')],
    ('sustain', 'physical'): [('STR', 'VIT'), ('VIT', 'STR'), ('STR', 'VIT', 'WIS'), ('DEX', 'VIT', 'STR')],
    ('bulwark', 'physical'): [('VIT', 'STR'), ('VIT', 'STR', 'WIS'), ('STR', 'VIT'), ('VIT', 'DEX', 'STR')],
    ('blast', 'physical'): [('STR', 'VIT'), ('STR', 'INT'), ('STR', 'VIT', 'INT'), ('DEX', 'STR', 'INT')],
    ('execute', 'physical'): [('STR', 'DEX'), ('DEX', 'STR'), ('STR', 'DEX', 'LUK'), ('DEX', 'STR', 'VIT')],
    ('tempo', 'physical'): [('DEX', 'STR'), ('DEX', 'STR', 'LUK'), ('STR', 'DEX', 'VIT'), ('DEX', 'VIT', 'STR')],
    ('mana_flow', 'physical'): [('STR', 'INT', 'WIS'), ('STR', 'WIS'), ('DEX', 'INT', 'STR'), ('VIT', 'STR', 'INT')],
    ('support', 'physical'): [('STR', 'WIS', 'VIT'), ('WIS', 'STR'), ('VIT', 'WIS', 'STR'), ('STR', 'VIT', 'WIS')],
    ('affliction', 'physical'): [('DEX', 'STR', 'INT'), ('DEX', 'STR'), ('STR', 'DEX', 'INT'), ('DEX', 'VIT', 'INT')],
    ('ambush', 'physical'): [('DEX', 'STR', 'LUK'), ('DEX', 'LUK', 'STR'), ('DEX', 'STR'), ('DEX', 'VIT', 'LUK')],
    ('frenzy', 'physical'): [('STR', 'LUK'), ('STR', 'VIT', 'LUK'), ('STR', 'DEX', 'LUK'), ('VIT', 'STR', 'LUK')],
    ('sunder', 'physical'): [('STR', 'VIT'), ('STR', 'VIT', 'DEX'), ('VIT', 'STR'), ('STR', 'DEX')],
    ('bleed_crit', 'magic'): [('INT', 'LUK', 'DEX'), ('INT', 'DEX'), ('LUK', 'INT')],
    ('sustain', 'magic'): [('INT', 'VIT'), ('WIS', 'VIT', 'INT'), ('VIT', 'INT')],
    ('bulwark', 'magic'): [('VIT', 'WIS', 'INT'), ('WIS', 'VIT'), ('VIT', 'INT'), ('INT', 'VIT')],
    ('blast', 'magic'): [('INT', 'VIT'), ('INT', 'STR'), ('INT', 'WIS', 'VIT'), ('INT', 'VIT', 'STR')],
    ('execute', 'magic'): [('INT', 'DEX'), ('INT', 'VIT', 'DEX'), ('WIS', 'INT', 'DEX'), ('INT', 'LUK')],
    ('tempo', 'magic'): [('INT', 'DEX', 'LUK'), ('WIS', 'DEX', 'INT'), ('INT', 'VIT', 'DEX'), ('WIS', 'VIT', 'DEX')],
    ('mana_flow', 'magic'): [('INT', 'WIS'), ('WIS', 'INT'), ('INT', 'WIS', 'VIT'), ('WIS', 'INT', 'VIT')],
    ('support', 'magic'): [('WIS', 'INT'), ('WIS', 'VIT', 'INT'), ('WIS', 'VIT'), ('VIT', 'WIS', 'INT')],
    ('affliction', 'magic'): [('INT', 'DEX'), ('INT', 'VIT', 'DEX'), ('INT', 'WIS', 'DEX'), ('WIS', 'INT', 'DEX')],
    ('ambush', 'magic'): [('INT', 'DEX', 'LUK'), ('DEX', 'INT'), ('INT', 'LUK')],
    ('frenzy', 'magic'): [('INT', 'LUK'), ('INT', 'LUK', 'VIT')],
    ('sunder', 'magic'): [('INT', 'VIT'), ('WIS', 'INT', 'VIT'), ('VIT', 'INT'), ('WIS', 'VIT', 'INT')],
}

# 손으로 정한 무기 (정체성이 분명한 것 · '민첩 대형 도끼' · '지능 활' 같은 본보기). (순서, 이유)
WEAPON_FIX = {
    # 시작 무기 (Lv1, 요구 없음) 는 자동
    'grove_warden_maul': (('VIT', 'STR'), '이끼바위 — 버티는 망치'),
    'minewarden_mace': (('WIS', 'STR'), '축성 철퇴 — 때리는 사제'),
    'silkstring_recurve': (('LUK', 'DEX'), '선제 활 — 행운 사수'),
    'ore_splitter_axe': (('STR', 'VIT'), '광맥 쪼개개'),
    'skitter_fang': (('DEX', 'INT'), '독 송곳니 — 지능 섞인 독'),
    'rootgnaw_tanto': (('LUK', 'STR'), '갉아먹는 뿌리 — 광기'),
    'moss_bone_bow': (('STR', 'DEX'), '뼈 활 — 힘으로 당기는 활'),
    'corridor_executioner_axe': (('STR', 'DEX'), '처형 도끼'),
    'silkqueen_reaper': (('DEX', 'STR', 'LUK'), '여왕의 낫 — 출혈치명'),
    'silkqueen_spindle_censer': (('WIS', 'VIT'), '물레 향로 — 지원'),
    'silkqueen_fang': (('DEX', 'INT'), '여왕의 송곳니 — 독'),
    'pit_war_spear': (('VIT', 'STR'), '입구 막기'),
    'miners_bell_scepter': (('VIT', 'WIS'), '경보종 — 맞아 주는 시전자'),
    'silk_sickle': (('DEX', 'VIT'), '흡혈 낫 — 민첩 유지'),
    'skitter_longbow': (('LUK', 'DEX'), '소리 없는 줄'),
    'glowcap_bone_bow': (('INT', 'DEX'), '지능 활 (마법 화살)'),
    'mycelking_scepter': (('WIS', 'INT', 'VIT'), '균사왕 홀 — 파쇄'),
    'mycelking_guard_blade': (('VIT', 'STR', 'WIS'), '근위의 방패'),
    'hypha_glaive': (('DEX', 'STR', 'LUK'), '민첩 언월도'),
    'eelbone_recurve': (('INT', 'DEX', 'WIS'), '장어뼈 — 연쇄 번개 (마법 화살)'),
    'drowned_executioner_axe': (('DEX', 'STR', 'VIT'), '민첩 처형 도끼'),
    'verdigris_great_axe': (('STR', 'VIT', 'DEX'), '녹청 큰도끼'),
    'slagedge_bladebow': (('INT', 'WIS', 'DEX'), '슬래그 날활 — 과부하 (마법 화살)'),
    'slag_katar': (('STR', 'LUK'), '힘 주먹칼 — 광기'),
    'dawnbringer': (('STR', 'WIS', 'VIT'), '여명 — 축성 검'),
    'ember_greatsword': (('STR', 'VIT', 'INT'), '잿불 대검'),
    'rime_great_axe': (('DEX', 'LUK', 'STR'), '민첩 대형 도끼 — 광기'),
    'frost_war_spear': (('INT', 'STR', 'VIT'), '서리 창 — 지능 근접 (마법)'),
    'rime_chime_rod': (('VIT', 'WIS', 'INT'), '서리 풍경 — 방벽'),
    'soulflame_kris': (('LUK', 'DEX', 'STR'), '혼불 — 행운 출혈'),
    'prism_twin_bow': (('INT', 'DEX', 'LUK'), '프리즘 쌍현 — 지능 활 (마법)'),
    'geode_great_maul': (('VIT', 'STR', 'WIS'), '정동 망치 — 유지'),
    'twin_light_scepter': (('INT', 'WIS', 'VIT'), '쌍광 홀 — 폭발'),
    'lorekeeper_katar': (('INT', 'DEX', 'WIS'), '금서지기 주먹칼 — 지능 근접 (마법)'),
    'ink_recurve': (('INT', 'STR', 'DEX'), '먹물 만곡궁 — 지능 활 (마법)'),
    'inkseal_warhammer': (('STR', 'WIS', 'INT'), '봉인 망치 — 마력 흡수'),
    'lore_glaive': (('STR', 'INT', 'WIS'), '금서 언월도'),
    'index_cleaver': (('STR', 'LUK', 'VIT'), '색인 참마도 — 광기'),
    'regulator_greatsword': (('DEX', 'STR', 'VIT'), '조율기 — 민첩 대검'),
    'pendulum_censer': (('WIS', 'DEX', 'INT'), '진자 향로 — 민첩 시전'),
    'quicksilver_longbow': (('DEX', 'INT', 'STR'), '수은 장궁'),
    'clock_glaive': (('LUK', 'STR', 'DEX'), '자정 언월도 — 행운 광기'),
    'abyss_bone_bow': (('INT', 'DEX', 'LUK'), '심연 뼈 활 — 지능 활 (마법)'),
    'abyss_sentinel_longsword': (('VIT', 'STR', 'WIS'), '심연 파수검'),
    'celestial_oathkeeper': (('STR', 'WIS', 'VIT'), '천궁 — 수호 기운'),
    'eclipse_blade': (('DEX', 'LUK', 'STR'), '일식 — 등 찌르기'),
    'bloodmoon_reaver': (('STR', 'LUK', 'VIT'), '혈월'),
    'seraph_scepter': (('WIS', 'VIT', 'INT'), '치천사'),
    'aurora_scepter': (('INT', 'WIS', 'VIT'), '오로라 — 마나순환'),
}

# 마법 피해로 바꾸는 근접·활 (지능 활 · 지능 근접). combat_spec §6.4·§5.7 이 허용한 'INT 요구 근접·활은 attack.kind: magic'.
KIND_MAGIC = ['glowcap_bone_bow', 'eelbone_recurve', 'slagedge_bladebow', 'frost_war_spear', 'prism_twin_bow',
              'lorekeeper_katar', 'ink_recurve', 'abyss_bone_bow']

# 직업이 '자연스럽게' 찍는 능력치 (combat_spec sensible_spread new) — 세금 계산용
RATIO = G.COMBAT['formulas']['sensible_spread']['new']
NATURAL_LOOK = {'guardian': 'heavy', 'berserker': 'heavy', 'hunter': 'light', 'shadow': 'light', 'arcanist': 'cloth', 'priest': 'cloth'}
DMG_STAT = {'guardian': 'STR', 'berserker': 'STR', 'hunter': 'STR', 'shadow': 'STR', 'arcanist': 'INT', 'priest': 'INT'}
CLASS_SET = {c: set(RATIO[c]) for c in G.CLS}
CLASS_SET['shadow'] = CLASS_SET['shadow'] | {'LUK'}       # 그림자 기본 LUK 4 · 치명 빌드

# ── 방어구 (세트마다 하나 — 네 부위 같은 요구) ──
ARMOR_FIX = {
    # 세트
    'novice': (None, '시작 지급 — 요구 없음'),
    'wayfarer': (('VIT', 'DEX'), '모든 직업용 — 누구나 1포인트 안'),
    'pit_foreman': (('VIT', 'STR'), '판금'),
    'webrunner': (('DEX', 'STR'), '가죽 — 사수·암살자 공통'),
    'silkweaver': (('INT', 'WIS'), '천 — 낮은 레벨이라 두 직업 모두 가볍다'),
    'hypha_stalker': (('DEX', 'STR', 'VIT'), '가죽'),
    'spore_sage': (('INT', 'VIT', 'WIS'), '천 — 지능 쪽'),
    'mycel_carapace': (('VIT', 'STR', 'WIS'), '새 판금 — 재생·지원형'),
    'verdigris_guard': (('VIT', 'STR'), '판금'),
    'sluice_diver': (('DEX', 'VIT', 'STR'), '새 가죽 — 이동·회피'),
    'emberforged': (('STR', 'VIT', 'INT'), '판금 — 힘 쪽, 불의 룬'),
    'rimefang': (('DEX', 'LUK', 'STR'), '가죽 — 행운 쪽'),
    'crypt_mourner': (('WIS', 'VIT', 'INT'), '천 — 정신 쪽'),
    'cinder_cantor': (('INT', 'VIT', 'WIS'), '새 천 — 지능 쪽'),
    'forge_warden': (('VIT', 'STR'), '보스 판금'),
    'frost_regalia': (('INT', 'WIS', 'VIT'), '보스 천 — 마나'),
    'rime_stalker': (('DEX', 'STR', 'LUK'), '새 가죽 — 치명'),
    'geode_bastion': (('VIT', 'STR', 'DEX'), '판금'),
    'shard_dancer': (('DEX', 'LUK', 'VIT'), '가죽 — 행운 쪽'),
    'lorekeeper': (('INT', 'WIS', 'VIT'), '천'),
    'index_bulwark': (('VIT', 'INT', 'STR'), '새 판금 — 마검사(지능)'),
    'inkveil': (('DEX', 'STR', 'LUK'), '보스 가죽'),
    'clock_astrologer': (('WIS', 'INT', 'VIT'), '새 천 — 정신 쪽'),
    'clockwork_juggernaut': (('VIT', 'STR'), '판금'),
    'abyss_walker': (('DEX', 'STR', 'VIT'), '가죽'),
    'starless_choir': (('INT', 'VIT', 'WIS'), '천 — 지능 쪽'),
    # 단품 투구 · 방패
    'grove_mossguard_helm': (('VIT', 'STR'), '모든 직업용 보스 투구'),
    'silkqueen_veil': (('DEX', 'LUK'), '보스 가죽 두건'),
    'mycelking_spore_crown': (('WIS', 'VIT', 'INT'), '보스 천 관'),
    'osric_sluice_helm': (('VIT', 'STR'), '보스 판금 투구'),
    'nightmare_crown': (('VIT', 'LUK'), '모든 직업용 신화 관 — 체력·행운, 어느 직업이든 같은 세금'),
    'oak_round_shield': (None, 'Lv1'),
    'ironbound_kite_shield': (('VIT', 'STR'), '방패'),
    'sporecap_round_shield': (('VIT', 'STR', 'WIS'), '방패 — 재생'),
    'verdigris_tower_shield': (('VIT', 'STR'), '방패'),
    'anvil_face_shield': (('VIT', 'STR'), '방패'),
    'frostgrave_tower_shield': (('VIT', 'STR', 'INT'), '방패'),
    'prism_aegis': (('VIT', 'WIS', 'STR'), '보스 방패 — 성기사'),
    'inkbound_kite_shield': (('VIT', 'INT', 'STR'), '방패 — 재사용 감소'),
    'clockwork_bastion': (('VIT', 'STR'), '보스 방패'),
    'void_bulwark_shield': (('VIT', 'STR', 'DEX'), '방패'),
}


def armor_key(a):
    return a['set'] if a['set'] else a['id']


def armor_requires(A):
    out = {}
    for aid, a in A.items():
        k = armor_key(a)
        order, why = ARMOR_FIX[k]
        out[aid] = dict(requires=split(a['L'], order) if order else {}, order=order, why=why)
    return out


# 직업 기본 분배 말고도 고를 수 있는 빌드 (요구 능력치가 '쓸모없는 무기'를 만들지 않는지 볼 때)
ARCH = {
    'crit': {'DEX': 1.6, 'LUK': 1.2, 'STR': 1.0, 'VIT': 1.2},          # 치명 빌드 (행운)
    'spellblade': {'STR': 1.4, 'INT': 1.4, 'VIT': 1.6, 'DEX': 0.4},    # 마검사 (힘 + 지능)
    'battle_priest': {'WIS': 1.8, 'STR': 1.2, 'VIT': 1.8},             # 때리는 사제
    'dex_caster': {'INT': 2.2, 'DEX': 1.2, 'VIT': 1.6},                # 민첩 시전 (상태이상)
    'tank_caster': {'VIT': 2.2, 'WIS': 1.4, 'INT': 1.4},               # 맞아 주는 시전자
}
ARCH_KO = {'crit': '치명(행운)', 'spellblade': '마검사', 'battle_priest': '전투 사제', 'dex_caster': '민첩 시전', 'tank_caster': '방벽 시전'}


def tax_points(cls, L, req, ratio=None):
    """요구치(req)를 채우려 '알맞은 분배'(직업 기본, 또는 ratio) 밖으로 더 찍어야 하는 포인트 (0 = 세금 없음), 다 낄 수 있는가, 필요 포인트."""
    base = G.class_base(cls)
    N = G.points_at(L)
    need = sum(max(0, v - base.get(s, 0)) for s, v in req.items())
    feasible = need <= N
    r = ratio or RATIO[cls]
    tot = sum(r.values())
    pool = N + sum(base.get(s, 0) for s in r)
    plan = {s: max(base.get(s, 0), pool * r[s] / tot) for s in r}
    extra = 0.0
    for s, v in req.items():
        have = plan.get(s, base.get(s, 0))
        extra += max(0.0, v - have)
    return extra, feasible, need


def kit_req(items_req):
    out = {}
    for r in items_req:
        for s, v in r.items():
            out[s] = max(out.get(s, 0), v)
    return out


def assign_weapons(W, verbose=False):
    """무기마다 요구 능력치 순서 고르기. 반환 {wid: dict(order, requires, why, kind)}."""
    out = {}
    for wid in KIND_MAGIC:
        W[wid]['kind'] = 'magic'
    for b in G.BANDS:
        ws = sorted([w for w in W.values() if w['band'] == b], key=lambda w: (w['L'], w['id']))
        cover = collections.Counter()
        prim = collections.Counter()
        shape_tpl = collections.defaultdict(set)
        pair_used = collections.Counter()
        for w in ws:
            L = w['L']
            if budget(L) == 0:
                out[w['id']] = dict(order=None, requires={}, why='Lv1 — 요구 없음')
                continue
            if w['id'] in WEAPON_FIX:
                order, why = WEAPON_FIX[w['id']]
            else:
                cands = TPL[(w['direction'], w['kind'])]
                best = None
                for i, o in enumerate(cands):
                    o2 = tuple(o[:2]) if (len(o) == 3 and L < 12) else tuple(o)
                    s = 0.35 * i
                    for c in G.CLS:
                        if set(o2[:2]) <= CLASS_SET[c]:
                            s -= 1.0 / (1 + cover[c])
                    s += 0.45 * prim[o2[0]]
                    s += 0.6 * pair_used[frozenset(o2[:2])]
                    if o2 in shape_tpl[w['shape']]:
                        s += 1.5
                    if best is None or s < best[0]:
                        best = (s, o2)
                order = best[1]
                why = '자동 (방향 ' + G.DIRS[w['direction']]['name'] + ')'
            order = tuple(order[:2]) if (len(order) == 3 and L < 12) else tuple(order)
            for c in G.CLS:
                if set(order[:2]) <= CLASS_SET[c]:
                    cover[c] += 1
            prim[order[0]] += 1
            pair_used[frozenset(order[:2])] += 1
            shape_tpl[w['shape']].add(order)
            out[w['id']] = dict(order=order, requires=split(L, order), why=why)
    return out


if __name__ == '__main__':
    W = G.weapons_all()
    R = assign_weapons(W)
    for b in G.BANDS:
        print('== band', b)
        for wid, w in sorted(W.items(), key=lambda kv: kv[1]['L']):
            if w['band'] != b:
                continue
            print(f"  {wid:28s} L{w['L']:2d} {w['kind'][:4]} {w['direction']:10s} {R[wid]['requires']}")
