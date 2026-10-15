# -*- coding: utf-8 -*-
"""TASK D — 고유 효과 다시 배정 (기존 131 + 새 106 = 237, 종류 없는 띠 · 새 전투 모델).

  python3 tools/ud_assign.py      → tools/ud_state.json (문서·JSON 쓰기용 중간값) + 검사 출력

바뀌는 것 (unique_spec 1판 대비)
 1) 강도 s 의 기준: '같은 무기 종류·같은 5레벨 구간 최고' → '같은 5레벨 띠 전체(종류 없음, 신화 제외) 최고'.
    무기 힘 P′ = 비교값 × (1 + 부가 스탯 가치 + 0.1 × 무기 스킬 수), 비교값 = (한 방 가운데값 ÷ 간격) ÷ K(방식, 간격)
    (= gear_spec §5 의 P′). 레벨 차이를 빼려고 Q = P′ ÷ TP′(L)  (TP′ = 전투 명세 §5.7 일반 티어 위력) 로 비교한다.
    gap = 띠 최고 Q ÷ Q − 1,  B = clamp(0.08 + 0.6 × gap, 0.04, 0.28),  s = B ÷ 0.10  (식은 1판 그대로).
 2) 수치의 기준 (전투 명세 §3.5 + 이 작업에서 고친 점):
    W  (한 방 공격력)      cleave · flurry · chain_spark · sanctify · leech · rend · shield_bash
    SP (스킬 위력)         death_burst · overcharge · imbue 지속 피해          ← 툴팁 글도 '스킬 위력'
    W×g (한 방 보너스)     first_strike · bloodrush · counterstep              ← pct 에 간격 보정 g 를 곱해 저장
    그대로                 execute · hemorrhage · exploit · backstab · longshot · berserk · momentum ·
                           thorns · steadfast · feast · siphon · ward_aura · armor_break
    g = (1 ÷ (간격 × K(방식, 간격)) × 시전 1.05) ÷ (1 ÷ (0.67 × 1.47))   — 그 무기의 스킬 위력 ÷ 한 방, 장검 0.67초 = 1
    imbue 확률 = 0.25 × min(1.5, 간격 ÷ 0.67) 을 무기마다 저장 (툴팁 숫자 = 실제 확률, 서비스는 다시 곱하지 않는다)
    shield_bash N = clamp(round(N기준 × 0.67 ÷ 간격), 2, 8), pct = pct(s) × N ÷ N기준  (몇 초마다 한 번은 같게)
    재발동: chain_spark 1.0 → 0.3초, sanctify 0.5 → 0.25초 (빠른 무기가 재발동에 막혀 손해 보지 않게)
    chain_spark 확률 0.20 → 0.30 (고정)
 3) 획득처 보정: 대장간만으로 얻는 무기는 '강도 비례' 수치 × 0.8 (상한에서 자른 뒤). 신화 B = 0.05~0.08.
 4) 배정 바꿈 8개 (FIX, 방향은 그대로 → gear_spec 요구 능력치 영향 없음).
"""
import collections
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ud_core as U
from ue_catalog import E as CAT, nice  # 1판 카탈로그 (기준값·상한·종류) — 읽기만

# ── 상수 ──────────────────────────────────────────────────────────────────────
REF_IV = 0.67
REF_SPW = 1 / (REF_IV * 1.47)          # 장검 0.67초: 스킬 위력 ÷ 한 방 = 1.015
WGT = {'crit_chance': 0.5, 'crit_damage': 0.2, 'attack_speed': 0.7, 'lifesteal': 0.4, 'skill_damage': 0.35,
       'cooldown_reduction': 0.45, 'damage_reduction': 0.8, 'evasion': 0.6, 'move_speed': 0.15}
RAR_MULT = {'common': 1.00, 'uncommon': 1.06, 'rare': 1.13, 'epic': 1.21, 'legendary': 1.31, 'mythic': 1.45}

BASIS = {}
for e in ('cleave', 'flurry', 'chain_spark', 'sanctify', 'leech', 'rend', 'shield_bash'):
    BASIS[e] = 'W'
for e in ('death_burst', 'overcharge', 'imbue'):
    BASIS[e] = 'SP'
for e in ('first_strike', 'bloodrush', 'counterstep'):
    BASIS[e] = 'Wg'
for e in ('execute', 'hemorrhage', 'exploit', 'backstab', 'longshot', 'berserk', 'momentum'):
    BASIS[e] = 'mult'
for e in ('thorns', 'steadfast', 'feast', 'siphon', 'ward_aura', 'armor_break'):
    BASIS[e] = 'none'
BASIS_KO = {'W': '한 방 공격력', 'SP': '스킬 위력', 'Wg': '한 방 × 간격 보정 g', 'mult': '곱하기(그대로)', 'none': '무기와 무관'}

ICD = {k: dict(v['icd']) for k, v in CAT.items()}
ICD['chain_spark'] = {'global': 0.3}
ICD['sanctify'] = {'global': 0.25}

# ── 바꾼 배정 (효과만, 방향은 그대로 → gear_spec 요구 능력치 영향 없음) ────────────────
FIX = {
    # 출혈을 스스로 못 거는 무기의 hemorrhage(출혈 적에게만 켜짐) → rend. 대부분 직업에서 아무것도 안 하는 효과라서.
    'soulflame_kris': ('rend', None, '혼불 상처', '무기 스킬이 불태움만 걸어 hemorrhage 가 거의 안 켜짐 → rend (방향 출혈치명 그대로)'),
    'mycel_dirk': ('rend', None, '균사 상처', '무기 스킬 없음 → hemorrhage 가 스스로 안 켜짐 → rend'),
    'brine_katar': ('rend', None, '소금 상처', '무기 스킬 없음 → hemorrhage 가 스스로 안 켜짐 → rend'),
    # 41–45 대장간 Lv41 근접 셋이 모두 momentum → 둘을 같은 방향(속공) 다른 효과로
    'regulator_greatsword': ('flurry', None, '조율 박자', '같은 띠·같은 방식·같은 대장간 Lv41 에 momentum 3개 → flurry'),
    'mainspring_dagger': ('counterstep', None, '태엽 반동', '같은 띠·같은 방식·같은 대장간 Lv41 에 momentum 3개 → counterstep'),
    # 11–15 근접에 death_burst 2개(몹·상자 Lv11, 대장간 Lv14), 휩쓸기 없음 → 몹·상자 쪽을 cleave 로 (무리 사냥에서 보스 무기를 이기는 몹·상자 무기가 생김)
    'capsplitter_cleaver': ('cleave', None, '갓 휩쓸기', '같은 띠 근접 death_burst 2개 · 무리 사냥 최고가 보스 무기였음 → cleave (방향 폭발범위 그대로)'),
    # 31–35 무리 사냥 최고가 보스 무기(질풍 날개 활) → 몹·상자 원거리 하나를 cleave 로 (화살이 맞은 자리 주변)
    'prismstring_longbow': ('cleave', None, '빛 파편', '31–35 는 네 상황 모두 보스 무기가 최고였음 → 몹·상자 활 하나를 chain_spark → cleave (방향 폭발범위 그대로)'),
    # 21–25 시전에 몹·상자 Lv22 imbue(불태움) 2개 → 스스로 불태우는 무기 스킬이 있는 쪽을 exploit 로
    'crucible_chalice': ('exploit', None, '도가니 열기', '같은 띠·같은 획득처 시전 imbue(불태움) 2개 → exploit (무기 스킬이 불태움을 건다, 방향 상태이상 그대로)'),
}

# 대장간(언제든 만들 수 있는 것)만으로 얻는 무기는 고유 효과 수치 × 0.8 — '대장간이 언제나 정답'이 아니게.
FORGE_F = 0.8
# chain_spark 확률 0.20 → 0.30 (재발동 1.0 → 0.3초와 함께; 무리 사냥 값이 휩쓸기의 40% 쯤이 되게)
CHAIN_CHANCE = 0.30


def pc(v):
    return f"{round(v * 100, 1):g}%"


def sec(v):
    return f"{v:g}초"


# 설명 글 (34자 이하). 1판과 같은 것은 그대로, 기준이 바뀐 셋(death_burst·overcharge·imbue)만 '스킬 위력'.
def desc(eid, p):
    if eid == 'rend':
        return f"치명타 시 출혈 (중첩당 초당 공격력 {pc(p['pct'])}, 최대 {p['max_stacks']})"
    if eid == 'hemorrhage':
        return f"출혈 중인 적에게 치명 확률 +{pc(p['cc'])}, 치명 피해 +{pc(p['cd'])}"
    if eid == 'leech':
        return f"기본 공격 피해의 {pc(p['pct'])} 회복 (초당 최대 HP {pc(p['cap'])}까지)"
    if eid == 'feast':
        return f"처치 시 최대 HP {pc(p['heal'])} 회복, {sec(p['duration'])}간 흡혈 +{pc(p['ls'])}"
    if eid == 'thorns':
        return f"맞으면 줄기 전 피해의 {pc(p['pct'])}를 되돌린다 (근접만)"
    if eid == 'shield_bash':
        return f"{p['n']}번째 공격마다 기절 {sec(p['stun'])} + 공격력 {pc(p['pct'])}"
    if eid == 'steadfast':
        return f"HP {pc(p['thr'])} 이상이면 받는 피해 -{pc(p['dr'])}, 밀려나지 않음"
    if eid == 'cleave':
        return f"기본 공격이 주변 {p['radius']:g}칸 적 {p['targets']}명에게 공격력 {pc(p['pct'])}"
    if eid == 'chain_spark':
        return f"{pc(p['chance'])} 확률로 번개가 {p['targets']}명에게 튐 (공격력 {pc(p['pct'])})"
    if eid == 'death_burst':
        return f"처치한 적이 터져 {p['radius']:g}칸 안 적에게 스킬 위력 {pc(p['pct'])}"
    if eid == 'execute':
        return f"HP {pc(p['thr'])} 이하 적에게 피해 +{pc(p['pct'])} (보스는 60%만)"
    if eid == 'bloodrush':
        return f"처치하면 다음 공격 피해 +{pc(p['pct'])}, {sec(p['duration'])}간 이동 +{pc(p['ms'])}"
    if eid == 'momentum':
        return f"적중마다 공격 속도 +{pc(p['as'])} ({p['max_stacks']}중첩), {sec(p['decay'])} 쉬면 사라짐"
    if eid == 'flurry':
        return f"{p['n']}번째 공격마다 공격력 {pc(p['pct'])}의 추가 타격"
    if eid == 'counterstep':
        return f"회피하면 {sec(p['window'])} 안 다음 공격 치명타 확정, 피해 +{pc(p['pct'])}"
    if eid == 'siphon':
        return f"처치 시 MP {pc(p['mp'])} 회복, 무기 스킬 대기 -{sec(p['cdr'])}"
    if eid == 'overcharge':
        return f"스킬을 쓰면 다음 기본 공격이 스킬 위력 {pc(p['pct'])} 폭발"
    if eid == 'sanctify':
        return f"적중 시 {p['radius']:g}칸 안 가장 다친 아군을 공격력 {pc(p['pct'])} 치유"
    if eid == 'ward_aura':
        return f"{sec(p['period'])}마다 {p['radius']:g}칸 아군에게 최대 HP {pc(p['pct'])} 보호막"
    if eid == 'imbue':
        el = p['element']
        if el == 'burn':
            return f"{pc(p['chance'])} 확률로 {sec(p['duration'])} 불태움 (초당 스킬 위력 {pc(p['pct'])})"
        if el == 'poison':
            return f"{pc(p['chance'])} 확률로 독 중첩 (초당 스킬 위력 {pc(p['pct'])}, 최대 5)"
        return f"{pc(p['chance'])} 확률로 서리 1중첩, 5중첩이면 빙결 1초"
    if eid == 'exploit':
        return f"상태이상 걸린 적에게 피해 +{pc(p['pct'])} (2개면 1.6배)"
    if eid == 'first_strike':
        return f"처음 때리는 적에게 피해 +{pc(p['pct'])}, 치명 확률 +{pc(p['cc'])}"
    if eid == 'backstab':
        return f"적의 등 뒤에서 때리면 피해 +{pc(p['pct'])}"
    if eid == 'longshot':
        return f"{p['dist']:g}칸 밖 적에게 피해 +{pc(p['pct'])}, 화살·탄이 {p['pierce']}명 더 꿰뚫음"
    if eid == 'berserk':
        return f"잃은 HP 10%마다 피해 +{pc(p['pct'])}, 빈사 흡혈 +{pc(p['ls'])}"
    if eid == 'armor_break':
        return f"적중마다 대상 방어 -{pc(p['pct'])} ({p['max_stacks']}중첩, {sec(p['duration'])})"
    raise KeyError(eid)


def short(eid, p):
    S = {
        'rend': lambda: f"치명타 → 출혈 {pc(p['pct'])}",
        'hemorrhage': lambda: f"출혈 적에게 치명 +{pc(p['cc'])}",
        'leech': lambda: f"적중 회복 {pc(p['pct'])}",
        'feast': lambda: f"처치 → HP {pc(p['heal'])}",
        'thorns': lambda: f"반사 {pc(p['pct'])}",
        'shield_bash': lambda: f"{p['n']}타 기절 {sec(p['stun'])}",
        'steadfast': lambda: f"HP 높으면 피해 -{pc(p['dr'])}",
        'cleave': lambda: f"주변 {p['targets']}명 {pc(p['pct'])}",
        'chain_spark': lambda: f"번개 {p['targets']}명 {pc(p['pct'])}",
        'death_burst': lambda: f"처치 폭발 위력 {pc(p['pct'])}",
        'execute': lambda: f"빈사 적 +{pc(p['pct'])}",
        'bloodrush': lambda: f"처치 → 다음 +{pc(p['pct'])}",
        'momentum': lambda: f"적중 공속 +{pc(p['as'])}×{p['max_stacks']}",
        'flurry': lambda: f"{p['n']}타 추가 {pc(p['pct'])}",
        'counterstep': lambda: "회피 → 확정 치명",
        'siphon': lambda: f"처치 → MP {pc(p['mp'])}",
        'overcharge': lambda: f"스킬 후 폭발 위력 {pc(p['pct'])}",
        'sanctify': lambda: "적중 → 아군 치유",
        'ward_aura': lambda: f"보호막 {pc(p['pct'])}/{sec(p['period'])}",
        'imbue': lambda: {'burn': '적중 → 불태움', 'poison': '적중 → 독 중첩', 'frost': '적중 → 서리'}[p['element']],
        'exploit': lambda: f"상태이상 적 +{pc(p['pct'])}",
        'first_strike': lambda: f"첫 타 +{pc(p['pct'])}",
        'backstab': lambda: f"등 뒤 +{pc(p['pct'])}",
        'longshot': lambda: f"원거리 +{pc(p['pct'])}",
        'berserk': lambda: f"다칠수록 +{pc(p['pct'])}/10%",
        'armor_break': lambda: f"방어 -{pc(p['pct'])}×{p['max_stacks']}",
    }
    return S[eid]()


def width(t):  # 1판 ue_gen.width 와 같은 근사 (px)
    n = 0
    for ch in t:
        if ch == ' ':
            n += 4
        elif '가' <= ch <= '힣':
            n += 9
        elif ord(ch) < 128:
            n += 6
        else:
            n += 8
    return n


def icd_head(eid):
    i = ICD[eid]
    v = i.get('global') or i.get('per_attacker') or i.get('per_target') or 0
    return v


# ── 무기 힘 ───────────────────────────────────────────────────────────────────
def P_L(L):
    return 7 + 0.25 * (L - 1) + 0.0195 * (L - 1) ** 2


def c_L(L):
    S = 8 + 3.6 * (L + 3)
    return (1 + 0.02 * S) / (1 + 0.01 * S)


def TP(L):
    return P_L(L) * c_L(L)


def sec_value(L_, stats):  # gear_spec g2_spec.sec_value 와 같음 (STR·INT 1%/점)
    Sp = 8 + 2.5 * (L_ - 1)
    v = 0
    for k, r in stats.items():
        m = U.mid(r)
        if k in ('STR', 'DEX', 'INT', 'VIT', 'WIS', 'LUK'):
            v += (0.01 * m / (1 + 0.01 * Sp)) if k in ('STR', 'INT') else m * 0.002
        elif k in WGT:
            v += WGT[k] * m
        elif k == 'heal_power':
            v += 0.4 * m / (1.5 * Sp)
        elif k == 'mana_regen':
            v += 0.2 * m / (1 + 0.05 * Sp)
        elif k == 'hp':
            v += m / (100 + 9 * L_) * 0.4
        elif k == 'defense':
            v += m * 0.004
        elif k == 'hp_regen':
            v += m * 0.01
        elif k == 'mp':
            v += m / (80 + 3 * L_) * 0.15
    return v


def compare_value(w):
    return (U.mid(w['per_hit']) / w['interval']) / U.K_style(w['style'], w['interval'])


def g_factor(w):
    spw = 1 / (w['interval'] * U.K_style(w['style'], w['interval'])) * U.spm(w['style'])
    return spw / REF_SPW


# ── 수치 ──────────────────────────────────────────────────────────────────────
def level_int(eid, key, L):
    if eid == 'cleave' and key == 'targets':
        return 2 + (L >= 20) + (L >= 40)
    if eid == 'chain_spark' and key == 'targets':
        return 2 + (L >= 15) + (L >= 35)
    if eid == 'longshot' and key == 'pierce':
        return 1 + (L >= 30)
    if eid == 'shield_bash' and key == 'n':
        return None   # 아래에서 간격으로
    raise KeyError((eid, key))


def params_for(w, eid, s, element):
    e = CAT[eid]
    L = w['L']
    out = {}
    f_src = FORGE_F if w['sk'] == ['F'] else 1.0
    for k, (ref, kind, mx) in e['params'].items():
        if kind == 'f':
            v = ref
        elif kind == 'L':
            v = level_int(eid, k, L)
        else:
            v = ref * s
            if mx is not None:
                v = min(v, mx)
            v *= f_src
        out[k] = v
    if eid == 'chain_spark':
        out['chance'] = CHAIN_CHANCE
    g = g_factor(w)
    if BASIS[eid] == 'Wg':
        out['pct'] = out['pct'] * g
    if eid == 'shield_bash':
        n_ref = 4 if s >= 1.4 else 5
        n = max(2, min(8, round(n_ref * REF_IV / w['interval'])))
        out['n'] = n
        out['pct'] = out['pct'] * n / n_ref
    if eid == 'imbue':
        out['chance'] = round(0.25 * min(1.5, w['interval'] / REF_IV), 2)
        out['element'] = element
    for k in list(out):
        if k in ('element', 'n', 'targets', 'pierce', 'max_stacks', 'chance') or CAT[eid]['params'].get(k, (0, 'f'))[1] == 'f':
            continue
        out[k] = nice(k, out[k])
    return out, g


def strength_budget(w, gap):
    B = min(0.28, max(0.04, 0.08 + 0.6 * gap))
    if w['rar'] == 'mythic':
        B = min(0.08, max(0.05, 0.08 + 0.6 * gap))
    if w['rar'] == 'common' and w['L'] <= 1:
        B = 0.04
    elif w['rar'] == 'common' and w['L'] <= 3:
        B = min(B, 0.06)
    return B


def main():
    W = U.load()
    # 바꾼 배정 적용
    changes = []
    for wid, (eid, el, name, why) in FIX.items():
        w = W[wid]
        changes.append(dict(id=wid, name=w['name'], before=w['effect'], before_name=w['uname'], after=eid, after_name=name,
                            direction=w['direction'], why=why, new=w['new']))
        assert CAT[eid]['direction'] == w['direction'], wid
        w['effect'], w['element'], w['uname'] = eid, el, name
    # 힘
    for w in W.values():
        w['cv'] = compare_value(w)
        w['sv'] = sec_value(w['L'], w['stats'])
        w['Pp'] = w['cv'] * (1 + w['sv'] + 0.1 * w['n_skills'])
        w['Q'] = w['Pp'] / TP(w['L'])
    ref = {}
    for b in range(1, 11):
        cand = [w for w in W.values() if w['band'] == b and w['rar'] != 'mythic']
        top = max(cand, key=lambda w: w['Q'])
        ref[b] = dict(id=top['id'], Q=top['Q'])
    problems = []
    for w in W.values():
        gap = ref[w['band']]['Q'] / w['Q'] - 1
        B = strength_budget(w, gap)
        s = round(B / 0.10, 2)
        p, g = params_for(w, w['effect'], s, w['element'])
        d = desc(w['effect'], p)
        sh = short(w['effect'], p)
        icd = icd_head(w['effect'])
        head = f"✧ 고유 {w['uname']}" + (f" (재발동 {icd:g}초)" if icd >= 1 else "")
        if len(d) > 34:
            problems.append((w['id'], 'desc>34', len(d), d))
        if width('  ' + d) > 330:
            problems.append((w['id'], 'desc px', width('  ' + d), d))
        if width(head) > 330:
            problems.append((w['id'], 'head px'))
        if width('✧ ' + w['uname'] + ' ' + sh) > 330:
            problems.append((w['id'], 'short px'))
        if CAT[w['effect']]['ranged_only'] and w['style'] != 'ranged':
            problems.append((w['id'], 'ranged_only', w['style']))
        if CAT[w['effect']]['direction'] != w['direction']:
            problems.append((w['id'], 'direction'))
        w.update(gap=gap, B=B, s=s, params=p, g=g, desc=d, short=sh, head=head, basis=BASIS[w['effect']])
    print('problems', len(problems))
    for x in problems:
        print('  ', x)
    # 희귀도별 강도
    by = collections.defaultdict(list)
    for w in W.values():
        by[w['rar']].append(w['s'])
    print('s by rarity', {k: round(sum(v) / len(v), 2) for k, v in by.items()})
    byo = collections.defaultdict(list)
    for w in W.values():
        byo['new' if w['new'] else 'old'].append(w['s'])
    print('s new/old', {k: round(sum(v) / len(v), 2) for k, v in byo.items()})
    capped = sum(1 for w in W.values() if w['B'] >= 0.28 - 1e-9)
    print('capped', capped, 'of', len(W))
    by_src = collections.defaultdict(list)
    for w in W.values():
        by_src['+'.join(w['sk'])].append(w['s'])
    print('s by source', {k: round(sum(v) / len(v), 2) for k, v in sorted(by_src.items())})
    st = dict(W=W, ref=ref, changes=changes, problems=problems)
    json.dump(st, open(os.path.join(HERE, 'ud_state.json'), 'w'), ensure_ascii=False, indent=0)
    return st


if __name__ == '__main__':
    main()
