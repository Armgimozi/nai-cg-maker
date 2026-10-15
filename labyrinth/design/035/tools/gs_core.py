# -*- coding: utf-8 -*-
"""TASK C 계산 핵심 — 공식(피해·스탯·티어 위력·스킬 위력), 기존 무기 표, 새 무기 생성, 고유 효과·무기 스킬."""
import json, math, sys, collections
import yaml

D = '/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad/design2/'
C = '/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
sys.path.insert(0, D + 'tools')
from gs_data import (N, EXR, SPEED, OLD_TYPE_SPEED, OLD_TYPE_STYLE, PAL, NEW_SHAPES, ELITE, ARMOR, style_of)  # noqa
from ue_catalog import E as UE, params_for  # noqa  (효과 설계자의 카탈로그 그대로)

ITEMS = yaml.safe_load(open(C + 'items.yml'))['items']
SETS = yaml.safe_load(open(C + 'items.yml'))['sets']
LOOT = yaml.safe_load(open(C + 'loot.yml'))['tables']
RECIPES = yaml.safe_load(open(C + 'recipes.yml'))['recipes']
MOBS = yaml.safe_load(open(C + 'mobs.yml'))['mobs']
BOSSES = yaml.safe_load(open(C + 'bosses.yml'))['bosses']
NPCS = yaml.safe_load(open(C + 'npcs.yml'))['npcs']
USPEC = json.load(open(D + 'unique_spec.json'))
DIRS = json.load(open(D + 'directions.json'))['tags']

STATS6 = ['STR', 'DEX', 'INT', 'WIS', 'VIT', 'LUK']
RAR = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic']
RAR_KO = {'common': '일반', 'uncommon': '고급', 'rare': '희귀', 'epic': '영웅', 'legendary': '전설', 'mythic': '신화'}
STYLE_KO = {'melee': '근접', 'ranged': '원거리', 'caster': '시전'}
STAT_KO = {'STR': '힘', 'DEX': '민첩', 'INT': '지능', 'WIS': '지혜', 'VIT': '체력', 'LUK': '운'}
KIND_KO = {'B': '보스', 'F': '대장간', 'M': '몬스터·상자', 'T': '시련', 'S': '특별 시련', 'V': '금고·미믹', 'E': '정예', 'P': '상인'}
KIND_SRC = {'B': ['boss'], 'F': ['craft'], 'M': ['drop', 'chest'], 'T': ['trial'], 'S': ['special'], 'V': ['hoard'],
            'E': ['elite'], 'P': ['shop']}
SEC_KO = {'crit_chance': '치명 확률', 'crit_damage': '치명 피해', 'attack_speed': '공격 속도', 'move_speed': '이동 속도',
          'lifesteal': '흡혈', 'hp': '체력', 'hp_regen': '체력 재생', 'damage_reduction': '피해 감소', 'defense': '방어',
          'skill_damage': '스킬 피해', 'cooldown_reduction': '재사용 감소', 'mp': 'MP', 'mana_regen': 'MP 재생',
          'heal_power': '치유력', 'evasion': '회피', 'STR': '힘', 'DEX': '민첩', 'INT': '지능', 'WIS': '지혜', 'VIT': '체력(능력치)', 'LUK': '운'}

# ── 공식 (items.yml 에서 맞춤 — gs_fit.py: 피해 비 평균 1.002 sd 0.015, 부가 스탯 비 1.00) ──
def P(L):                     # 무기 힘 (GDD §16.4)
    return 7 + 0.25 * (L - 1) + 0.0195 * (L - 1) ** 2
RM = {'common': 1.00, 'uncommon': 1.06, 'rare': 1.13, 'epic': 1.21, 'legendary': 1.31, 'mythic': 1.45}   # 피해 희귀도
RC = {'common': 0.6, 'uncommon': 0.8, 'rare': 1.0, 'epic': 1.2, 'legendary': 1.45, 'mythic': 1.75}       # 스탯 희귀도
BASE = {'hp': lambda L: 3 + 3.2 * L, 'mp': lambda L: 2 + 1.6 * L, 'defense': lambda L: 1 + 0.35 * L,
        'crit_chance': lambda L: 0.01 + 0.0009 * L, 'crit_damage': lambda L: 0.03 + 0.003 * L,
        'attack_speed': lambda L: 0.02 + 0.0009 * L, 'move_speed': lambda L: 0.01 + 0.0005 * L,
        'cooldown_reduction': lambda L: 0.01 + 0.0009 * L, 'skill_damage': lambda L: 0.02 + 0.0015 * L,
        'mana_regen': lambda L: 0.1 + 0.015 * L, 'hp_regen': lambda L: 0.2 + 0.05 * L, 'heal_power': lambda L: 1 + 0.8 * L,
        'lifesteal': lambda L: 0.01 + 0.0006 * L, 'damage_reduction': lambda L: 0.01 + 0.0006 * L,
        'evasion': lambda L: 0.01 + 0.0006 * L}
PRIM = lambda L: 1 + 0.22 * L
N_SEC = {'common': 1, 'uncommon': 1, 'rare': 2, 'epic': 3, 'legendary': 4, 'mythic': 5}


def K(style, speed):
    """DPS 상수 — 초당 피해 = 티어 위력 × K. 근접 1.47 (1.5회 넘으면 회당 −0.143), 원거리 1.56, 시전 1.22."""
    if style == 'ranged':
        return 1.56
    if style == 'caster':
        return 1.22
    return 1.47 - 0.143 * max(0.0, speed - 1.5)


def hit_scale(style, speed):
    return K(style, speed) / speed


def req_value(L):
    r = math.ceil(2.5 * (L - 1))
    return r if r > 2 else 0


def band(L):
    return (L - 1) // 5 + 1


def blabel(b):
    return f"{b * 5 - 4}–{b * 5}"


def mid(r):
    return (r[0] + r[1]) / 2


def rnd(key, v):
    if key in ('hp', 'mp', 'heal_power', 'defense') or key in STATS6:
        return int(round(v))
    if key in ('mana_regen', 'hp_regen'):
        return round(v, 1)
    return round(v, 3)


def rng(key, m, lo=0.85, hi=1.15):
    a, b = rnd(key, m * lo), rnd(key, m * hi)
    if key in STATS6 or key in ('hp', 'mp', 'heal_power', 'defense'):
        a = max(1, a)
        if b <= a:
            b = a + 1
    elif b <= a:
        b = a + (0.1 if key in ('mana_regen', 'hp_regen') else 0.001)
    return [a, b]


# ── 부가 스탯 가치 (효과 설계자 ue_gen.power 와 같은 가중치) ──
WGT = {'crit_chance': 0.5, 'crit_damage': 0.2, 'attack_speed': 0.7, 'lifesteal': 0.4, 'skill_damage': 0.35,
       'cooldown_reduction': 0.45, 'damage_reduction': 0.8, 'evasion': 0.6, 'move_speed': 0.15}


def sec_value(L, stats, prim_keys):
    Sp = 8 + 2.5 * (L - 1)
    v = 0
    for k, r in stats.items():
        if k == 'damage':
            continue
        m = mid(r)
        if k in prim_keys:
            v += 0.02 * m / (1 + 0.02 * Sp)
        elif k in WGT:
            v += WGT[k] * m
        elif k == 'heal_power':
            v += 0.4 * m / (1.5 * Sp)
        elif k == 'mana_regen':
            v += 0.2 * m / (1 + 0.05 * Sp)
        elif k == 'hp':
            v += m / (100 + 9 * L) * 0.4
        elif k == 'defense':
            v += m * 0.004
        elif k == 'hp_regen':
            v += m * 0.01
        elif k == 'mp':
            v += m / (80 + 3 * L) * 0.15
        elif k == 'VIT':
            v += m * 0.004
        else:
            v += m * 0.002
    return v


# ── 방향별 부가 스탯 (주 → 둘째 → 셋째) ──
SEC = {
    'bleed_crit': ['crit_chance', 'crit_damage', 'attack_speed'], 'sustain': ['lifesteal', 'hp', 'hp_regen'],
    'bulwark': ['damage_reduction', 'hp', 'defense'], 'blast': ['crit_damage', 'skill_damage', 'hp'],
    'execute': ['crit_damage', 'crit_chance', 'move_speed'], 'tempo': ['attack_speed', 'move_speed', 'crit_chance'],
    'mana_flow': ['cooldown_reduction', 'mp', 'mana_regen'], 'support': ['heal_power', 'mana_regen', 'hp'],
    'affliction': ['skill_damage', 'crit_chance', 'cooldown_reduction'], 'ambush': ['crit_chance', 'move_speed', 'evasion'],
    'frenzy': ['lifesteal', 'crit_damage', 'attack_speed'], 'sunder': ['crit_damage', 'hp', 'defense'],
}


def sec_keys(direction, style, n):
    ks = list(SEC[direction])
    if style == 'caster':
        ks = ['cooldown_reduction' if k == 'attack_speed' else k for k in ks]
        if direction == 'blast':
            ks = ['skill_damage', 'mp', 'crit_damage']
    out = []
    for k in ks:
        if k not in out:
            out.append(k)
    return out[:n]


# ── 기존 무기 131개 ──
TYPE_REQ = {'greatsword': 'STR', 'sword_shield': 'STR', 'bow': 'DEX', 'dagger': 'DEX', 'staff': 'INT', 'scepter': 'WIS'}


def old_kind(v):
    s = v.get('sources', [])
    if 'boss' in s:
        return 'B'
    if s == ['craft']:
        return 'F'
    if 'craft' in s:
        return 'M+F'
    return 'M'


def existing():
    out = {}
    for k, v in ITEMS.items():
        if v.get('type') != 'weapon':
            continue
        wt = v['weapon_type']
        style, speed = OLD_TYPE_STYLE[wt], OLD_TYPE_SPEED[wt]
        req = EXR[k][0] if k in EXR else TYPE_REQ[wt]
        L = v['level_req']
        prim_old = TYPE_REQ[wt]
        stats = dict(v['stats'])
        if k in EXR and '|' not in req and req != prim_old and prim_old in stats:
            stats = {(req if kk == prim_old else kk): vv for kk, vv in stats.items()}   # 주 스탯 줄도 같은 능력치로
        a = USPEC['assignments'][k]
        tp = mid(stats['damage']) * speed / K(style, speed)
        out[k] = dict(id=k, name=v['name'], new=False, L=L, F=v['floor'], band=band(L), rar=v['rarity'], style=style,
                      speed=speed, shape=v['model']['shape'], req=req, req_old=prim_old, stats=stats,
                      skills=len(v.get('weapon_skills') or []), dir=a['direction'], eff=a['effect'], uname=a['name'],
                      params=a['params'], strength=a['strength'], kind=old_kind(v), src=v.get('sources'), tp=tp,
                      mythic=v['rarity'] == 'mythic', wt=wt)
    return out


# ── 새 무기 ──
def dmg_range(m):
    """정수 피해 [lo, hi] — 가운데값이 목표 m 에 가장 가깝고 반폭이 3~12% (items.yml 평균 6.8%)."""
    best = None
    for lo in range(max(1, int(m * 0.8)), int(m * 1.1) + 2):
        for hi in range(lo + 1, int(m * 1.25) + 3):
            c = (lo + hi) / 2
            w = (hi - lo) / 2 / c
            if not 0.03 <= w <= 0.12:
                continue
            key = (abs(c - m), abs(w - 0.068))
            if best is None or key < best[0]:
                best = (key, [lo, hi])
    return best[1]


def craft_ref(allw, b):
    """구간의 대장간 기준 = 대장간에서 만드는 무기(보스+대장간 포함) 중 가장 높은 단계의 티어 위력 가운데값."""
    cr = [w for w in allw.values() if not w['new'] and w['band'] == b and 'craft' in (w['src'] or [])]
    top = max((RAR.index(w['rar']), w['L']) for w in cr)
    tps = sorted(w['tp'] for w in cr if (RAR.index(w['rar']), w['L']) == top)
    n = len(tps)
    return (tps[n // 2] if n % 2 else (tps[n // 2 - 1] + tps[n // 2]) / 2), top


def classes_for(req):
    m = {'STR': ['guardian', 'berserker'], 'DEX': ['hunter', 'shadow'], 'INT': ['arcanist', 'priest'], 'WIS': ['priest'],
         'VIT': ['guardian'], 'LUK': ['shadow']}
    out = []
    for r in req.split('|'):
        for c in m[r]:
            if c not in out:
                out.append(c)
    return out


def build_new():
    out = {}
    for (iid, name, F, L, rar, shape, req, eff, el, kind, pal, lore) in N:
        style = style_of(shape)
        speed = SPEED[shape]
        m = P(L) * RM[rar] * hit_scale(style, speed)
        d = dmg_range(m)
        stats = {'damage': d}
        pm = PRIM(L) * RC[rar]
        for r in req.split('|')[:1]:
            stats[r] = rng(r, pm)
        direction = UE[eff]['direction']
        for kk in sec_keys(direction, style, N_SEC[rar]):
            if kk in STATS6:
                stats[kk] = rng(kk, pm * 0.6)
            else:
                stats[kk] = rng(kk, BASE[kk](L) * RC[rar])
        tp = mid(d) * speed / K(style, speed)
        tex_style, palette = PAL[F][pal]
        out[iid] = dict(id=iid, name=name, new=True, L=L, F=F, band=band(L), rar=rar, style=style, speed=speed,
                        shape=shape, req=req, stats=stats, skills=1 if rar in ('epic', 'legendary', 'mythic') else 0,
                        dir=direction, eff=eff, element=el, kind=kind, tp=tp, mythic=False, lore=lore,
                        tex_style=tex_style, palette=palette)
    return out


# ── 고유 효과 강도 (type-free: 같은 5레벨 구간 전체, 신화는 어려움 전용이라 비교에서 뺀다) ──
def power(w):
    prim = set(w['req'].split('|')) | {w.get('req_old', '')}
    return w['tp'] * (1 + sec_value(w['L'], w['stats'], prim) + 0.10 * w['skills'])


def assign_unique(allw, names):
    best = collections.defaultdict(float)
    for w in allw.values():
        w['P'] = power(w)
        if not w['mythic']:
            best[w['band']] = max(best[w['band']], w['P'])
    for w in allw.values():
        w['band_best'] = best[w['band']]
        w['gap'] = best[w['band']] / w['P'] - 1
        if not w['new']:
            continue
        B = min(0.28, max(0.04, 0.08 + 0.6 * w['gap']))
        if w['rar'] == 'common' and w['L'] <= 3:
            B = min(B, 0.06)
        s = round(B / 0.10, 2)
        p = params_for(w['eff'], w['L'], s, w['element'])
        e = UE[w['eff']]
        w.update(B=round(B, 3), strength=s, params=p, uname=names[w['id']], udesc=e['desc'](p), ushort=e['short'](p))
        icd = e['icd'].get('global') or e['icd'].get('per_attacker') or e['icd'].get('per_target') or 0
        w['utip'] = ["✧ 고유 " + names[w['id']] + (f" (재발동 {icd:g}초)" if icd >= 1 else ""), "  " + w['udesc']]
    return best


# 새 무기 고유 효과 이름 (툴팁 8자 이하 권장)
UNAME = {
    'corridor_executioner_axe': '마지막 판결', 'rootgnaw_tanto': '갉아먹는 뿌리', 'moss_bone_bow': '마디 사냥',
    'wayfarer_sabre': '길손의 발놀림', 'skitter_stiletto': '틈 찌르기', 'miners_great_maul': '갱도 붕괴',
    'silk_twin_bow': '겹시위', 'miners_lamp_crook': '등롱 기름', 'ore_morning_star': '광석 쪼개기',
    'silk_sabre': '엉킨 분노', 'skitter_longbow': '소리 없는 줄', 'silkcut_flamberge': '거미줄 끊기',
    'silk_chime_rod': '은실 울림', 'ore_kris': '광맥 찢기', 'ore_thurible_rod': '광석 연기', 'pit_war_spear': '입구 막기',
    'pit_rapier': '다그치기', 'silk_antler_staff': '은실 축복', 'spore_stiletto': '포자 첫 침', 'mycel_warhammer': '포자 광란',
    'glowcap_bone_bow': '빛갓 독', 'spore_flamberge': '포자 추격', 'mycel_dirk': '실 냄새', 'spore_thurible_rod': '공생 연기',
    'hypha_glaive': '낭창한 날', 'glowcap_rapier': '어둠 찌르기', 'brine_sabre': '소금 톱날', 'tide_lamp_crook': '수문 불빛',
    'drowned_executioner_axe': '수문 형장', 'eel_twin_bow': '곧은 물길', 'sluice_morning_star': '수문 삼킴',
    'brine_katar': '소금 상처', 'verdigris_great_axe': '집게 부수기', 'verdigris_chime_rod': '잔잔한 물살',
    'cinder_dagger': '첫 불씨', 'slag_flamberge': '쇳물 상처', 'anvil_executioner_axe': '실패작 처분', 'bellows_bone_bow': '뜨거운 숨',
    'ember_tanto': '잿속 칼끝', 'forge_chime_rod': '망치 소리', 'slag_war_spear': '슬래그 가시', 'forge_cleaver': '쇠판 쓸기',
    'cinder_rapier': '불씨 회전', 'rime_great_maul': '묘비 깨기', 'frost_twin_bow': '팽팽한 얼음줄', 'rime_thurible_rod': '장례 향',
    'frost_longsword': '묘지기의 피', 'rime_morning_star': '고드름 강타', 'frost_stiletto': '얼음 송곳', 'rime_great_axe': '금 간 분노',
    'frost_antler_staff': '눈사슴 울음', 'rime_composite_bow': '얼음 꿰뚫기', 'frost_tanto': '서리 소매', 'rime_flamberge': '얼음 포식',
    'rime_chalice': '얼지 않는 물', 'rime_chime_rod': '종지기의 꾸중', 'frost_war_spear': '얼음 파편', 'prism_lamp_crook': '뜨거운 갈래',
    'geode_great_maul': '결정 이빨', 'amethyst_executioner_axe': '짙어지는 보석', 'prism_twin_bow': '무지개 틈',
    'shardglass_tanto': '늦은 그림자', 'crystal_censer': '수정 막', 'resonance_chime_rod': '어긋난 음', 'resonance_rapier': '네 번째 음',
    'ink_sabre': '흐르는 획', 'ink_great_maul': '거꾸로 도장', 'ink_recurve': '먹줄 번개', 'lore_lamp_crook': '되살린 글자',
    'ink_morning_star': '차분한 먹', 'lore_sickle': '붉은 잉크', 'index_cleaver': '끝없는 번호', 'ink_bone_bow': '먹물 방울',
    'lore_antler_staff': '책갈피 독', 'ink_flamberge': '먹물 삼킴', 'ink_stiletto': '이름 지우기', 'lore_sun_scepter': '빛살 글귀',
    'index_war_spear': '대출 금지', 'ink_rapier': '피하는 획', 'clock_kris': '도는 상처', 'clock_mace': '무거운 태엽',
    'clock_blade_bow': '빠른 첫 바늘', 'clock_bell_scepter': '정시 종', 'clock_falchion': '한 번 더 물기', 'clock_staff_orb': '기름 구슬',
    'clock_glaive': '열두 시', 'clock_greatsword': '맞물린 이', 'clock_thurible_rod': '진자 박자', 'clock_katar': '소리 없는 톱니',
    'clock_broadsword': '경비병 방패', 'clock_antler_staff': '도는 가지', 'clock_morning_star': '추의 박자', 'clock_longsword': '빨라지는 초침',
    'void_stiletto': '빛 먹는 끝', 'abyss_great_maul': '늦은 메아리', 'void_twin_bow': '틈 사이로', 'abyss_sabre': '뻗는 촉수',
    'void_lamp_crook': '어둠 등불', 'abyss_executioner_axe': '떨리는 날', 'abyss_bone_bow': '가까운 과녁', 'void_tanto': '보이는 순간',
    'abyss_antler_staff': '감긴 눈', 'abyss_war_spear': '문 앞의 창', 'abyss_broadsword': '휘는 물길',
    'void_fang_blade': '먼저 움직임', 'abyss_ring_staff': '이어진 고리',
}


# ── 새 영웅 무기의 무기 스킬 (조합형 mechanics 1개, 층 연출 모델) ──
PROJ = {4: 'proj_brine', 5: 'proj_ember', 6: 'proj_frost_shard', 7: 'proj_crystal', 8: 'proj_ink', 9: 'proj_gear', 10: 'proj_void_orb'}
BURST = {4: 'tide_burst', 5: 'ember_burst', 6: 'rime_burst', 7: 'prism_burst', 8: 'inkblot_burst', 9: 'chrono_burst', 10: 'void_burst'}
SLASH = {4: 'tide_slash', 5: 'ember_slash', 6: 'rime_slash', 7: 'prism_slash', 8: 'inkblot_slash', 9: 'chrono_slash', 10: 'void_slash'}
WORD = {4: '물살', 5: '불티', 6: '서리', 7: '수정', 8: '먹물', 9: '톱니', 10: '공허'}
ELEM_FX = {'burn': {'ignite': 3}, 'poison': {'poison': 4}, 'frost': {'freeze': {'seconds': 3, 'stacks': 1}}}
FLOOR_ELEM = {4: 'frost', 5: 'burn', 6: 'frost', 7: 'burn', 8: 'poison', 9: 'burn', 10: 'poison'}
ACT = {  # (근접·시전, 원거리) 이름 후보
    'bleed_crit': (['가르기', '난도질'], ['가시 화살', '찢는 화살']), 'sustain': (['피 마시기', '삼키기'], ['흡혈 화살', '목마른 화살']),
    'bulwark': (['버티기', '방벽'], ['방벽 화살', '버팀 화살']), 'blast': (['폭쇄', '내려찍기'], ['폭발 화살', '터지는 화살']),
    'execute': (['목 치기', '끝맺음'], ['끝맺는 화살', '마지막 화살']), 'tempo': (['칼바람', '회전 칼날'], ['연사', '쏟아붓기']),
    'mana_flow': (['연쇄 섬광', '흐름'], ['연쇄 화살', '흐르는 화살']), 'support': (['축복의 원', '돌봄'], ['축복 화살', '돌봄 화살']),
    'affliction': (['비', '장막'], ['비', '화살비']), 'ambush': (['그림자 걸음', '등 뒤 일격'], ['기습 화살', '숨은 화살']),
    'frenzy': (['광란', '피 끓음'], ['광란 화살', '끓는 화살']), 'sunder': (['짓찧기', '부수기'], ['꿰뚫는 화살', '깨는 화살']),
}
KO_DESC = {
    'bleed_crit': ('앞쪽 부채꼴을 베어 4초 출혈을 건다.', '화살 세 대를 부채꼴로 쏘아 출혈을 건다.'),
    'sustain': ('주위를 휩쓸고 준 피해 일부를 체력으로 되찾는다.', '꿰뚫는 화살을 쏘고 준 피해 일부를 체력으로 되찾는다.'),
    'bulwark': ('보호막을 두르고 주위 적을 3초 도발한다.', '보호막을 두르고 주위 적을 3초 도발한다.'),
    'blast': ('뛰어올라 내려찍어 주위를 터뜨린다.', '맞은 자리에서 터지는 탄을 쏜다.'),
    'execute': ('앞으로 돌진해 벤다. 체력이 낮은 적에게 더 아프다.', '곧게 나는 화살. 체력이 낮은 적에게 더 아프다.'),
    'tempo': ('칼날 셋이 4초 동안 주위를 돈다.', '화살 다섯 대를 빠르게 이어 쏜다.'),
    'mana_flow': ('적 사이를 튀는 섬광을 쏘고 MP 를 조금 되찾는다.', '적 사이를 튀는 화살을 쏘고 MP 를 조금 되찾는다.'),
    'support': ('주위 아군을 치유하고 5초간 받는 피해를 줄인다.', '주위 아군을 치유하고 5초간 받는 피해를 줄인다.'),
    'affliction': ('바라보는 곳에 여섯 번 쏟아져 상태이상을 건다.', '바라보는 곳에 화살비를 내려 상태이상을 건다.'),
    'ambush': ('적의 등 뒤로 순간 이동해 찌르고 표식을 남긴다.', '아주 빠른 화살로 표식을 남긴다.'),
    'frenzy': ('6초간 공격 속도와 흡혈이 오르고 주위를 친다.', '6초간 공격 속도와 흡혈이 오른다.'),
    'sunder': ('뛰어올라 내려찍어 4초간 받는 피해를 늘린다.', '꿰뚫는 화살로 4초간 받는 피해를 늘린다.'),
}


def mechanics_for(w):
    f, d, rngd = w['F'], w['dir'], w['style'] == 'ranged'
    pj, bu, sl = PROJ[f], BURST[f], SLASH[f]
    el = ELEM_FX[w.get('element') or FLOOR_ELEM[f]]
    if d == 'bleed_crit':
        m = ([{"type": "projectile", "count": 3, "spread": 18, "speed": 1.6, "range": 18, "display": pj, "effects": [{"damage": 0.7}, {"bleed": 3}]}]
             if rngd else [{"type": "cone", "range": 4.5, "angle": 100, "display": sl, "effects": [{"damage": 1.5}, {"bleed": 4}]}])
        cd, mp = 11, 16
    elif d == 'sustain':
        m = ([{"type": "projectile", "speed": 1.8, "range": 20, "pierce": 2, "display": pj, "effects": [{"damage": 1.2}, {"lifesteal": 0.25}]}]
             if rngd else [{"type": "nova", "radius": 3.5, "display": bu, "effects": [{"damage": 1.3}, {"lifesteal": 0.3}]}])
        cd, mp = 12, 16
    elif d == 'bulwark':
        m = [{"type": "self", "effects": [{"absorption": {"amount": 0.12, "seconds": 5}}]},
             {"type": "nova", "radius": 4, "display": bu, "effects": [{"damage": 0.8}, {"taunt": 3}]}]
        cd, mp = 16, 18
    elif d == 'blast':
        m = ([{"type": "projectile", "speed": 1.3, "range": 16, "display": pj, "explode": {"radius": 3, "display": bu, "effects": [{"damage": 1.6}]}}]
             if (rngd or w['style'] == 'caster') else
             [{"type": "leap", "forward": 0.6, "upward": 0.7, "land": [{"type": "nova", "radius": 4, "display": bu, "effects": [{"damage": 1.6}]}]}])
        cd, mp = 12, 18
    elif d == 'execute':
        m = ([{"type": "projectile", "speed": 2.0, "range": 24, "display": pj, "effects": [{"damage": 1.3}, {"execute": {"amount": 0.8, "threshold": 0.3}}]}]
             if rngd else [{"type": "dash", "distance": 6, "width": 1.5, "effects": [{"damage": 1.2}, {"execute": {"amount": 1.0, "threshold": 0.3}}]}])
        cd, mp = 12, 16
    elif d == 'tempo':
        m = ([{"type": "projectile", "count": 5, "interval": 3, "speed": 1.8, "range": 18, "display": pj, "effects": [{"damage": 0.45}]}]
             if rngd else [{"type": "orbit", "count": 3, "radius": 2.2, "duration": 4, "speed": 12, "hit_cooldown": 10, "display": pj, "effects": [{"damage": 0.35}]}])
        cd, mp = 12, 15
    elif d == 'mana_flow':
        m = [{"type": "chain", "jumps": 3, "range": 10, "falloff": 0.8, "effects": [{"damage": 1.3}]}, {"type": "self", "effects": [{"mana": 8}]}]
        cd, mp = 10, 14
    elif d == 'support':
        m = [{"type": "party", "radius": 8, "effects": [{"heal": 0.08}, {"buff": {"stats": {"damage_reduction": 0.1}, "seconds": 5}}]},
             {"type": "nova", "radius": 3, "display": bu, "effects": [{"damage": 0.8}]}]
        cd, mp = 14, 20
    elif d == 'affliction':
        m = [{"type": "rain", "at": "aim", "range": 14, "count": 6, "radius": 3, "interval": 4, "display": pj, "effects": [{"damage": 0.5}, el]}]
        cd, mp = 13, 18
    elif d == 'ambush':
        m = ([{"type": "projectile", "speed": 2.2, "range": 26, "display": pj, "effects": [{"damage": 1.6}, {"glow": 4}]}]
             if rngd else [{"type": "blink", "distance": 8, "behind": True}, {"type": "cone", "range": 3, "angle": 70, "display": sl, "effects": [{"damage": 1.7}, {"glow": 4}]}])
        cd, mp = 12, 16
    elif d == 'frenzy':
        m = [{"type": "self", "effects": [{"buff": {"stats": {"attack_speed": 0.2, "lifesteal": 0.06}, "seconds": 6}}]}]
        if not rngd:
            m.append({"type": "nova", "radius": 3, "display": bu, "effects": [{"damage": 0.9}]})
        cd, mp = 18, 15
    else:  # sunder
        vul = {"effect": {"id": "vulnerable", "seconds": 4, "potency": 0.1}}
        m = ([{"type": "projectile", "speed": 1.6, "range": 20, "pierce": True, "display": pj, "effects": [{"damage": 1.2}, vul]}]
             if rngd else [{"type": "leap", "forward": 0.5, "upward": 0.8, "land": [{"type": "nova", "radius": 3.5, "display": bu, "effects": [{"damage": 1.4}, vul]}]}])
        cd, mp = 14, 18
    return m, cd, mp


def skill_for(w, used_names):
    acts = ACT[w['dir']][1 if w['style'] == 'ranged' else 0]
    word = WORD[w['F']]
    name = None
    for a in acts + [a + ' ' + s for a in acts for s in ('Ⅱ', 'Ⅲ')]:
        cand = f"{word} {a}" if w['dir'] != 'affliction' else f"{word} {a}"
        if cand not in used_names:
            name = cand
            break
    used_names.add(name)
    mech, cd, mp = mechanics_for(w)
    dtype = {'melee': 'melee', 'ranged': 'ranged', 'caster': 'magic'}[w['style']]
    desc = KO_DESC[w['dir']][1 if w['style'] == 'ranged' else 0]
    return {'id': 'mechanics', 'name': name, 'input': 'SNEAK_RIGHT' if w['style'] == 'ranged' else 'RIGHT',
            'cooldown': float(cd), 'mana': mp, 'description': desc, 'params': {'damage_type': dtype}, 'mechanics': mech}


def existing_skill_names():
    s = set()
    for v in ITEMS.values():
        for sk in v.get('weapon_skills') or []:
            s.add(sk['name'])
    return s


def all_weapons():
    old = existing()
    new = build_new()
    allw = {**old, **new}
    best = assign_unique(allw, UNAME)
    used = existing_skill_names()
    for w in new.values():
        if w['skills']:
            w['skill'] = skill_for(w, used)
    return old, new, allw, best
