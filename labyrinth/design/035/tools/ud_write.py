# -*- coding: utf-8 -*-
"""TASK D — 결과 쓰기.

  python3 tools/ud_assign.py && python3 tools/ud_write.py
  → design2/unique_assign_all.json (237) · design2/unique_assign_new.json (106) · design2/unique_spec.md 끝에 9장 덧붙임
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ud_core as U
import ud_assign as A
import ud_value as V

D2 = U.D2
MARK = '## 9. 새 무기 배정'

PVP_RULE = {
    'shield_bash': '기절 그대로 — PvP 상태이상 규칙(시간 ×0.8 · 최대 1초 · 줄어듦 · 끝나면 2초 면역). 같은 적 6초 면역도 그대로',
    'imbue': '지속 피해는 PvP 피해 공식을 거침. 서리 5중첩 빙결 그대로(PvP 상한 1.5초 · 줄어듦 · 면역)',
    'leech': '전역 pvp.lifesteal 0.5 (따로 ×0.5 하지 않음)',
    'sanctify': '혼자면 자신에게 절반 + 고정량 회복 규칙(× HP÷PvP 체력) + healing 0.6',
    'feast': '플레이어 처치에도 발동, 회복 × healing 0.6',
    'ward_aura': '같은 파티만, 보호막 × shield 0.8 · 긴 싸움 규칙',
    'thorns': '되돌리는 피해 ×0.5, 그 피해도 PvP 피해 공식을 거침(한 방 상한 없음)',
    'hemorrhage': '치명 추가 피해는 crit_damage_scale 0.6',
    'rend': '플레이어에게 최대 3중첩, 출혈 피해는 PvP 피해 공식',
    'armor_break': '플레이어에게 최대 3중첩',
    'steadfast': '그대로', 'momentum': '그대로', 'siphon': '그대로 (플레이어 처치에도)',
}
for e in ('execute', 'bloodrush', 'first_strike', 'backstab', 'longshot', 'berserk', 'exploit', 'counterstep'):
    PVP_RULE[e] = '+피해 ×0.5'
for e in ('flurry', 'cleave', 'chain_spark', 'overcharge'):
    PVP_RULE[e] = '덧 피해 ×0.5, PvP 피해 공식·완충을 거침'
PVP_RULE['death_burst'] = '플레이어를 처치하면 터지지 않음, 몹 폭발이 플레이어를 맞히면 ×0.5'


def dmg_kind(w):
    e = w['effect']
    if e in ('cleave', 'flurry', 'death_burst', 'shield_bash'):
        return w['kind']
    if e in ('chain_spark', 'overcharge'):
        return 'magic'
    if e == 'rend':
        return 'physical'
    if e == 'thorns':
        return 'fixed'
    if e == 'imbue':
        return {'burn': 'magic', 'poison': 'physical', 'frost': 'none'}[w['element']]
    return 'none'


KIND_KO = {'physical': '물리', 'magic': '마법', 'fixed': '고정', 'none': '-'}


def pct_s(x):
    return f"{x * 100:+.0f}%"


def main():
    st = A.main()
    W = st['W']
    bands = V.evaluate(W)
    fair = json.load(open(os.path.join(HERE, 'ud_fair.json')))
    fix_ids = {c['id'] for c in st['changes']}
    # ── JSON ──
    allj = {}
    newj = {}
    for wid in sorted(W, key=lambda k: (W[k]['band'], W[k]['L'], k)):
        w = W[wid]
        e = A.CAT[w['effect']]
        icd = A.ICD[w['effect']]
        ent = dict(effect=w['effect'], name=w['uname'], direction=w['direction'], params=w['params'],
                   strength=w['s'], budget=round(w['B'], 3), source_factor=(A.FORGE_F if w['sk'] == ['F'] else 1.0),
                   basis=w['basis'], interval_factor_g=round(w['g'], 3), damage_kind=dmg_kind(w), icd=icd,
                   hook=e['hook'], tooltip=[w['head'], '  ' + w['desc']], tooltip_folded='✧ ' + w['uname'] + ' ' + w['short'],
                   pvp_rule=PVP_RULE[w['effect']],
                   weapon=dict(new=w['new'], band=U.blabel(w['band']), level=w['L'], rarity=w['rar'], style=w['style'],
                               attack_kind=w['kind'], interval=w['interval'], per_hit=w['per_hit'], source_kinds=w['sk']),
                   power=dict(Q=round(w['Q'], 3), gap=round(w['gap'], 3), compare_value=round(w['cv'], 2),
                              secondary_value=round(w['sv'], 3), weapon_skills=w['n_skills']),
                   situational_gain={s: round(w['gain'][s], 3) for s in V.SITS},
                   before=dict(effect=(w.get('_before_effect') or w['effect']), params=w['old_params'], strength=w['old_s'],
                               source='unique_spec.json (A)' if not w['new'] else 'gear_spec.json (C)'))
        if wid in fix_ids:
            c = [c for c in st['changes'] if c['id'] == wid][0]
            ent['before']['effect'] = c['before']
            ent['before']['name'] = c['before_name']
            ent['changed_why'] = c['why']
        allj[wid] = ent
        if w['new']:
            newj[wid] = dict(effect=w['effect'], name=w['uname'], direction=w['direction'], params=w['params'])
    json.dump(allj, open(os.path.join(D2, 'unique_assign_all.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(newj, open(os.path.join(D2, 'unique_assign_new.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('json', len(allj), len(newj))

    # ── 문서 ──
    L = []
    P = L.append
    P('')
    P('---')
    P('')
    P(MARK + ' (TASK D, 0.3.5 — 종류 없는 띠 · 새 전투 모델에 맞춰 다시 계산)')
    P('')
    P('1~8장은 1판(무기 종류가 있던 때) 설계다. 효과 26개와 방향 12개는 그대로 쓴다. 수치를 정하는 기준과 일부 배정만 바뀐다. **수치가 다른 곳은 이 장이 이긴다.**')
    P('')
    P('- 결과: `unique_assign_all.json` (무기 237개 전부: 효과·이름·수치·강도·툴팁·PvP 규칙·상황별 이득·전 값), `unique_assign_new.json` (새 무기 106개: `{effect, name, direction, params}`).')
    P('- 계산: `tools/ud_core.py`(읽기) · `ud_assign.py`(강도·수치) · `ud_value.py`(상황별 가치) · `ud_fair.py`(간격 공정성 시뮬레이션) · `ud_write.py`(이 장). `python3 tools/ud_write.py` 로 다시 만든다.')
    P('- 저장소는 건드리지 않았다. gear_spec.json 새 무기의 `unique` 블록은 이 파일 값으로 바꿔 넣는다.')
    P('')
    # 9.1
    P('### 9.1 강도 — 무기 종류 대신 띠 전체와 비교')
    P('')
    P('1판은 "같은 무기 종류·같은 5레벨 구간 최고"와 비교했다. 종류가 없어졌으니 **같은 5레벨 띠 전체(신화 제외)**와 비교한다.')
    P('')
    P('```')
    P('비교값 CV = (한 방 가운데값 ÷ 간격) ÷ K(방식, 간격)          ← gear_spec §5 와 같음 (= 스킬 위력 ÷ 시전 배율)')
    P('무기 힘 P′ = CV × (1 + 부가 스탯 가치 + 0.1 × 무기 스킬 수)      ← 부가 스탯 가치 = gear_spec sec_value (STR·INT 1%/점)')
    P('Q        = P′ ÷ TP′(L)                                       ← 레벨 차이를 뺀다. TP′ = 전투 명세 §5.7 일반 티어 위력 P(L)×c(L)')
    P('gap      = 띠 최고 Q ÷ Q − 1')
    P('B        = clamp(0.08 + 0.6 × gap, 0.04, 0.28)   s = B ÷ 0.10      (1판 식 그대로)')
    P('  Lv1 일반 0.04 · Lv3 일반 ≤ 0.06 · 신화 0.05~0.08')
    P('대장간만으로 얻는 무기: 강도 비례 수치 × 0.8 (상한에서 자른 뒤)')
    P('```')
    P('')
    P('- 왜 Q 로 나누나: 띠 안에서 Lv11 무기와 Lv15 무기를 그대로 비교하면 레벨이 낮은 무기가 늘 진다. 같은 레벨에 놓고 희귀도·부가 스탯·무기 스킬만 비교한다.')
    P('- 왜 대장간 × 0.8: 대장간 무기는 0.4~1.1회 돌면 만든다(gear_spec §7.3). 같은 힘의 상자·시련·금고 무기보다 효과가 조금 약해야 "대장간이 언제나 정답"이 아니다. 상한에 닿은 무기도 줄어들도록 상한에서 자른 뒤 곱한다.')
    P('- 띠 최고는 늘 보스 무기다(2~3 스킬 전설·영웅). 그래서 보스가 아닌 무기는 대부분 상한(B 0.28)에 닿는다: 237개 중 '
      + str(sum(1 for w in W.values() if w['B'] >= 0.28 - 1e-9)) + '개.')
    by = collections.defaultdict(list)
    for w in W.values():
        by[w['rar']].append(w['s'])
    old_a = collections.defaultdict(list)
    old_c = collections.defaultdict(list)
    for w in W.values():
        if w['old_s'] is not None:
            (old_c if w['new'] else old_a)[w['rar']].append(w['old_s'])
    def avg(v):
        return f"{sum(v) / len(v):.2f}" if v else '-'
    P('')
    P('| 희귀도 | 무기 수 (기존 + 새) | 1판 s 평균 (기존, A) | 옛 장비 명세 s 평균 (새, C) | 이번 s 평균 (237) |')
    P('|---|---|---|---|---|')
    for r in U.RAR:
        if by[r]:
            P(f"| {U.RAR_KO[r]} | {len(by[r])} ({len(old_a[r])} + {len(by[r]) - len(old_a[r])}) | {avg(old_a[r])} | {avg(old_c[r])} | {avg(by[r])} |")
    src = collections.defaultdict(list)
    for w in W.values():
        src['+'.join(w['sk'])].append(w['s'])
    P('')
    P('획득처별 강도 s 평균: ' + ' · '.join(f"{'+'.join(U.SK_KO[x] for x in k.split('+'))} {sum(v) / len(v):.2f}" for k, v in sorted(src.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))) + ' (대장간은 표의 s 에 × 0.8 이 더 걸린다).')
    P('')
    P('- 기존 131개 중 수치가 바뀐 무기 ' + str(sum(1 for w in W.values() if not w['new'] and w['params'] != w['old_params'])) + '개, 새 106개 중 '
      + str(sum(1 for w in W.values() if w['new'] and w['params'] != w['old_params'])) + '개 (새 무기는 옛 판에서 이미 상한이던 것이 많다).')
    P('- 전체 힘이 조금 오른다: 비보스 무기 효과가 1판보다 세다(희귀 평균 s 1.91 → 2.57). 고유 효과는 combat_spec 난이도 시뮬레이션에 들어 있지 않다. 테스트 서버에서 보통·솔로 클리어율을 한 번 본다.')
    P('')
    # 9.2
    P('### 9.2 수치 기준 — 빠른 무기·느린 무기가 같은 값을 받게')
    P('')
    P('공격 간격이 무기마다 다르다(0.42~1.30초). 한 방 피해는 간격에 비례한다. 효과마다 "무엇에 곱하나"를 정해, 간격과 상관없이 같은 값이 나오게 한다.')
    P('')
    P('| 기준 | 효과 | 이유 |')
    P('|---|---|---|')
    P('| 한 방 공격력 (W) | `cleave` · `flurry` · `chain_spark` · `sanctify` · `leech` · `rend` · `shield_bash` | 기본 공격 한 대마다 켜진다. 초당 횟수 × 한 방 = 같은 값. `rend` 는 치명타마다 중첩이 쌓여 빠른 무기가 중첩을 더 쌓으므로 한 방 기준이 맞다(전투 명세 §3.5 의 "스킬 위력"에서 바꿈, 아래 표) |')
    P('| 스킬 위력 (SP) | `death_burst` · `overcharge` · `imbue`(불태움·독 지속 피해) | 처치·스킬 사용·지속 시간처럼 타격 수와 상관없이 켜진다 (전투 명세 §3.5 그대로). 툴팁 글도 "스킬 위력 N%" |')
    P('| 한 방 × 간격 보정 g | `first_strike` · `bloodrush` · `counterstep` | "다음 한 대 +N%" 는 한 대 크기에 비례해 느린 무기가 2배 이득. pct 에 g 를 곱해 저장한다. g = 그 무기의 (스킬 위력 ÷ 한 방) ÷ 장검 0.67초의 값. 단검 0.45초 g 1.60 · 대검 1.0초 0.67 · 장궁 1.25초 0.56. 툴팁 숫자는 무기마다 다르다(가벼운 무기 크고 무거운 무기 작음) |')
    P('| 곱하기 그대로 | `execute` · `hemorrhage` · `exploit` · `backstab` · `longshot` · `berserk` · `momentum` | 모든 타격에 같은 비율로 붙는다 |')
    P('| 무기와 무관 | `thorns` · `steadfast` · `feast` · `siphon` · `ward_aura` · `armor_break` | 받는 피해·최대 HP·MP·방어 비율 |')
    P('')
    P('그 밖에 바뀐 것:')
    P('')
    P('- `imbue` 확률 = 0.25 × min(1.5, 간격 ÷ 0.67) 을 **무기마다 저장**한다(전투 명세 §3.5 의 확률 보정). 툴팁 숫자가 실제 확률이다. 서비스는 다시 곱하지 않는다. 단검 0.47초 18% · 장검 25% · 대검 37% · 활 38%. 서리(frost)는 `pct` 를 쓰지 않는다(값은 남겨 둠).')
    P('- `shield_bash` N번째 = clamp(round(N기준 × 0.67 ÷ 간격), 2, 8), N기준 = 4(s ≥ 1.4) 또는 5. 공격력 % = pct(s) × N ÷ N기준. 몇 초마다 한 번 터지는지가 무기마다 같다(약 2.7~3.4초). 피해 몫도 같다.')
    P('- 재발동: `chain_spark` 1.0 → **0.3초**, `sanctify` 0.5 → **0.25초**. 1초·0.5초면 빠른 무기가 재발동에 막혀 15~50% 손해를 본다(아래 표).')
    P('- `chain_spark` 확률 0.20 → **0.30** (고정). 재발동을 줄이며 맞춘 값이다. 무리 사냥 값이 같은 강도 `cleave` 의 40% 쯤 된다(튀는 거리 6칸이 더 넓은 대신).')
    P('- 피해 종류: `cleave`·`flurry`·`death_burst`·`shield_bash` 는 무기 `attack.kind` 를 따른다(지능 활·시전 무기면 마법). 전투 명세 §4.4 는 `shield_bash` 를 물리로 적었다 — 종을 휘두르는 시전 무기(경보종 홀·수정 종 홀)가 힘을 타지 않게 무기 종류를 따르도록 바꿨다.')
    P('')
    P('**간격 공정성** (`ud_fair.py`, 600초 몬테카를로, 같은 단계 무기, 장검 0.67초 = 1.00, 1 에 가까울수록 공정. 같은 단계 무기 힘(K 로 나눈 값) 기준):')
    P('')
    rows = fair['rows']
    ref = fair['ref']
    def kfac(r):
        return U.K_style(r['style'], r['iv']) / U.K_style('melee', 0.67)
    cols = [('rend_SP', 'rend 스킬 위력'), ('rend_W', 'rend 한 방 ✔'), ('chain_W_icd1', 'chain 재발동 1초'), ('chain_W_icd0.3', 'chain 0.3초 ✔'),
            ('imbue_SP_flat', 'imbue 확률 고정'), ('imbue_SP_scaled', 'imbue 확률 보정 ✔'), ('first_W', 'first_strike 그대로'), ('first_g', 'first_strike × g ✔'),
            ('burst_W', 'death_burst 한 방'), ('burst_SP', 'death_burst 스킬 위력 ✔'), ('sanct_W_icd0.5', 'sanctify 0.5초'), ('sanct_W_icd0.25', 'sanctify 0.25초 ✔')]
    P('| 무기 (방식·간격) | ' + ' | '.join(c[1] for c in cols) + ' |')
    P('|---|' + '---|' * len(cols))
    for r in rows:
        if r['style'] == 'caster':
            continue
        P(f"| {U.STYLE_KO[r['style']]} {r['iv']:.2f}초 | " + ' | '.join(f"{r[c[0]] / ref[c[0]] * kfac(r):.2f}" for c in cols) + ' |')
    P('')
    P('- ✔ 가 고른 방식이다. 남은 차이는 ±16% 안이다. 시전 무기는 기본 공격이 설계상 17% 약해(K 1.22) 한 방 기준 효과가 그만큼 약하다 — 1판과 같은 성질이다.')
    P('')
    # 9.3 changes
    P('### 9.3 바꾼 배정 (효과만, 방향 태그는 그대로)')
    P('')
    P('방향 태그(`direction`)가 효과와 안 맞는 무기는 없었다(새 무기 106개 모두 효과의 방향 = 무기 방향). 아래는 "그 무기에서 효과가 거의 안 켜지는 것"과 "같은 띠·같은 방식에 같은 효과가 몰린 것"만 고쳤다. 방향을 안 바꿨으니 gear_spec 의 요구 능력치(방향 틀)는 그대로다.')
    P('')
    P('| 무기 | 새/기존 | 전 | 이번 | 이유 |')
    P('|---|---|---|---|---|')
    for c in st['changes']:
        P(f"| {c['name']} `{c['id']}` | {'새' if c['new'] else '기존'} | {c['before_name']} / `{c['before']}` | **{c['after_name']}** / `{c['after']}` | {c['why']} |")
    P('')
    P('- `exploit`(상태이상 걸린 적에게 +)은 무기가 스스로 상태이상을 못 걸어도 둔다(프리즘 쌍현 활). 직업 스킬 대부분이 무언가를 건다(표식·서리·불태움·독·출혈·느려짐). `hemorrhage` 는 출혈만 세서 광전사 말고는 거의 안 켜지므로 바꿨다. 남은 `hemorrhage` 4개는 모두 무기 스킬이 출혈을 건다.')
    P('')
    # 9.4 new weapons table
    P('### 9.4 새 무기 106개 배정')
    P('')
    P('열: 숨은 Lv · 희귀도 · 방식(간격 초) · 획득처 · 방향 · 고유 효과(이름 / id) · 툴팁 설명 · 강도 s · 기준. 대장간 무기는 설명 숫자에 × 0.8 이 이미 들어 있다.')
    P('')
    for b in range(1, 11):
        ws = sorted([w for w in W.values() if w['band'] == b and w['new']], key=lambda w: (w['L'], w['style'], w['id']))
        if not ws:
            continue
        P(f"#### {U.blabel(b)} ({len(ws)}개)")
        P('')
        P('| 무기 | Lv | 희귀도 | 방식 | 획득처 | 방향 | 고유 효과 | 설명 | s | 기준 |')
        P('|---|---|---|---|---|---|---|---|---|---|')
        for w in ws:
            P(f"| {w['name']} `{w['id']}` | {w['L']} | {U.RAR_KO[w['rar']]} | {U.STYLE_KO[w['style']]} {w['interval']:.2f} | {'·'.join(U.SK_KO[k] for k in w['sk'])} | {U.DIR_KO[w['direction']]} | **{w['uname']}** / `{w['effect']}` | {w['desc']} | {w['s']:.2f} | {A.BASIS_KO[w['basis']]} |")
        P('')
    # 9.5 diversity
    P('### 9.5 띠별 다양성 (기존 + 새, 237개)')
    P('')
    P('목표: 띠마다 방식(근접·원거리·시전)마다 방향 3개 이상 · 획득처 3종 이상 · "대장간이나 보스가 모든 상황에서 최고"인 띠가 없을 것.')
    P('')
    P('| 띠 | 무기 (근접/원거리/시전) | 방향 수 근접 · 원거리 · 시전 | 같은 방식 안 같은 효과 | 획득처 종류 |')
    P('|---|---|---|---|---|')
    ok_dir = True
    for b in range(1, 11):
        ws = [w for w in W.values() if w['band'] == b]
        cnt = collections.Counter(w['style'] for w in ws)
        dcount = []
        dups = []
        for stl in ('melee', 'ranged', 'caster'):
            s2 = [w for w in ws if w['style'] == stl]
            d = set(w['direction'] for w in s2)
            dcount.append(str(len(d)))
            if len(d) < 3:
                ok_dir = False
            ec = collections.Counter(w['effect'] for w in s2)
            dups += [f"{U.STYLE_KO[stl]} `{e}`×{c}" for e, c in ec.items() if c > 1]
        sks = sorted(set(k for w in ws for k in w['sk']))
        P(f"| {U.blabel(b)} | {len(ws)} ({cnt['melee']}/{cnt['ranged']}/{cnt['caster']}) | {' · '.join(dcount)} | {', '.join(dups) or '-'} | {len(sks)} ({'·'.join(U.SK_KO[k] for k in sks)}) |")
    P('')
    P('- 방식마다 방향 3개 이상: ' + ('모든 띠 통과.' if ok_dir else '실패 있음.') + ' 같은 효과가 두 번 나오는 곳은 대부분 획득처나 간격이 다르다(보스 하나 + 보스 아닌 하나 → "같은 효과를 보스 말고도 얻는다"). 가장 몰린 곳은 31–35 근접 `rend` 3개(몹·상자 Lv32 대도·단검, 대장간 Lv34 팔시온, 간격 0.90·0.45·0.62초) — 방향을 바꾸면 gear_spec 요구 능력치가 같이 바뀌므로 그대로 두었다.')
    P('')
    P('**상황별 가치** (`ud_value.py`). 가치 = Q × (1 + 그 상황의 효과 이득). 1판의 "자기 상황 = P×(1+2B)" 대신 효과마다 상황 4개의 이득을 따로 셈한다. 가정은 파일 맨 위 상수(기본 공격 비중 근접·원거리 0.7 · 시전 0.5, 치명 25%·×1.5, 무리 = 붙어 오는 4마리·한 마리 3초, 보스 혼자 90초, 3인 파티 보스, 버팀은 gear 가치표 무게로 피해 값으로 바꿈). 숫자는 순위를 보려는 어림이다.')
    P('')
    P('| 띠 | 무리 사냥 최고 | 정예전 최고 | 보스 혼자 최고 | 보스 파티 최고 | 보스·대장간 아닌 무기 중 최고 ÷ 전체 최고 (P·E·B·T) | 판정 |')
    P('|---|---|---|---|---|---|---|')
    verdict_fail = []
    for b, res in bands.items():
        cells = []
        for s in V.SITS:
            r = res[s]
            w = W[r['top']]
            cells.append(f"{w['name']} ({'·'.join(U.SK_KO[k] for k in r['top_sk'])})")
        ratios = ' · '.join(f"{(res[s]['bestO_V'] / res[s]['top_V']):.2f}" for s in V.SITS)
        winners = [frozenset(res[s]['top_sk']) for s in V.SITS]
        kinds_won = set()
        for s in V.SITS:
            t = res[s]['top_sk']
            kinds_won.add('B' if 'B' in t else ('F' if 'F' in t else 'O'))
        strict = len(kinds_won) == 1 and kinds_won != {'O'}
        other_ok = any(res[s]['bestO_V'] / res[s]['top_V'] >= 0.95 for s in V.SITS)
        v = ('✔' if (not strict and other_ok) else ('△' if not strict else '✘'))
        if v != '✔':
            verdict_fail.append((b, v))
        P(f"| {U.blabel(b)} | " + ' | '.join(cells) + f" | {ratios} | {v} |")
    P('')
    P('- ✔ = 한 획득처가 네 상황을 다 갖지 않고, 보스·대장간이 아닌 무기가 적어도 한 상황에서 최고의 95% 이상.')
    P('- 결과: ' + ('모든 띠 ✔.' if not verdict_fail else '✔ 아닌 띠: ' + ', '.join(f"{U.blabel(b)} {v}" for b, v in verdict_fail) + '.'))
    P('- 무리 사냥은 보스 아닌 무기(몹·상자·특별 시련·금고·정예)나 대장간 무기가 이긴다. 휩쓸기·과부하·시체 폭발이 무리에서 크다.')
    P('- 정예전·보스전은 대부분 보스 전설·영웅(무기 스킬 2~3개)이 이긴다. 다만 보스·대장간이 아닌 최고 무기가 보통 85~99% 까지 따라온다. 보스 무기는 그 보스에게서만 나오고 1.4~9회 걸린다(gear_spec §7.3).')
    P('')
    # per-style
    P('**방식별로 보면** (근접만·원거리만·시전만 놓고 같은 판정). 네 상황 모두 보스 또는 대장간이 이기는 칸(괄호 = 보스·대장간 아닌 최고 ÷ 그 방식 최고, 가장 좋은 상황):')
    P('')
    P('| 띠 | 근접 | 원거리 | 시전 |')
    P('|---|---|---|---|')
    style_fail = []
    for b, res in bands.items():
        row = []
        for stl in ('melee', 'ranged', 'caster'):
            tops = []
            best_ratio = 0
            for s in V.SITS:
                ps = res[s]['per_style'].get(stl)
                if not ps:
                    continue
                k = 'B' if 'B' in ps['top_sk'] else ('F' if 'F' in ps['top_sk'] else 'O')
                tops.append(k)
                if ps['other_V']:
                    best_ratio = max(best_ratio, ps['other_V'] / ps['V'])
            if 'O' in tops:
                row.append('✔')
            else:
                row.append(f"✘ {'·'.join(sorted(set(U.SK_KO[k] for k in tops)))} ({best_ratio:.2f})")
                style_fail.append((b, stl, best_ratio))
        P(f"| {U.blabel(b)} | " + ' | '.join(row) + ' |')
    P('')
    P(f'- 30칸 중 {30 - len(style_fail)}칸 ✔. ✘ 칸은 효과만으로는 못 메운다. 보스·대장간 쪽이 희귀도가 높고 무기 스킬이 1~2개 더 많아 Q 가 20~60% 높다. 비보스 무기는 이미 효과 상한이다. 주인이 기본 스탯 조정은 고르지 않았으므로 9.7 결정으로 넘긴다.')
    P('')
    # full table per band
    P('### 9.6 띠별 전체 표 (237개)')
    P('')
    P('굵게 = 새 무기. 열: Lv · 희귀도 · 방식 · 획득처 · 방향 · 효과 · 설명(툴팁 숫자) · s · Q(레벨 뺀 무기 힘) · 상황 이득 무리/정예/보스/파티.')
    P('')
    for b in range(1, 11):
        ws = sorted([w for w in W.values() if w['band'] == b], key=lambda w: (w['style'], w['L'], w['id']))
        P(f"#### {U.blabel(b)}")
        P('')
        P('| 무기 | Lv | 희귀도 | 방식 | 획득처 | 방향 | 효과 | 설명 | s | Q | 무리·정예·보스·파티 |')
        P('|---|---|---|---|---|---|---|---|---|---|---|')
        for w in ws:
            nm = f"**{w['name']}**" if w['new'] else w['name']
            g4 = ' · '.join(f"{w['gain'][s] * 100:.0f}" for s in V.SITS)
            P(f"| {nm} `{w['id']}` | {w['L']} | {U.RAR_KO[w['rar']]} | {U.STYLE_KO[w['style']]} | {'·'.join(U.SK_KO[k] for k in w['sk'])} | {U.DIR_KO[w['direction']]} | {w['uname']} `{w['effect']}` | {w['desc']} | {w['s']:.2f} | {w['Q']:.2f} | {g4} |")
        P('')
    # 9.7 decisions
    P('### 9.7 남은 문제 · 결정할 것')
    P('')
    worst = sorted(style_fail, key=lambda x: x[2])[:6]
    P('- **보스 전설이 단일전에서 앞선다.** 띠 최고 Q 는 늘 보스 무기다(무기 스킬 2~3개, 부가 스탯 많음). 효과는 상한이라 더 못 메운다. 1판의 결정 (가)/(나)는 그대로 남는다. 이번 계산으로 범위가 정해졌다:')
    P('  - (가) 보스·대장간이 아닌 무기 몇 개에 무기 스킬 1개 (또는 새 무기를 한 단계 높은 희귀도로). 가장 급한 칸: ' + ', '.join(f"{U.blabel(b)} {U.STYLE_KO[s]} ({r:.2f})" for b, s, r in worst) + '.')
    P('  - 특히 **31–35** 는 보스 아닌 무기가 모두 희귀·스킬 0개이고 보스 셋은 전설·스킬 2~3개다. 이 띠의 새 무기 8개(시련방·특별 시련·금고·정예)를 다른 띠의 새 무기처럼 영웅 + 무기 스킬 1개로 올리는 것이 가장 작은 고침이다(gear_spec 작업).')
    P('  - (나) 보스 무기 강도를 더 낮춤 — 이미 0.5~2.0 이라 차이가 작다(권하지 않음).')
    P('- **pvp_spec 표 숫자**: `cc_table` 의 고유 효과 기절 시간(1.5초 등)은 옛 수치다. 이번 `shield_bash` 기절은 0.6~1.5초, N 은 3~5. 규칙(×0.8·최대 1초·줄어듦·면역)은 그대로라 결론은 같지만 표는 `unique_assign_all.json` 으로 다시 만든다.')
    P('- **전투 명세와 다른 점** (combat_spec §3.5 · §4.4 에 알릴 것): `rend` 는 스킬 위력이 아니라 한 방 기준 · `first_strike`·`bloodrush`·`counterstep` 은 g 보정 · `imbue` 확률 보정은 데이터에 넣었으니 서비스에서 다시 곱하지 않음 · `shield_bash` 피해 종류는 무기를 따름 · 재발동 2개 · `chain_spark` 확률.')
    P('- **gear_spec 과 맞출 것**: 새 무기 `unique` 블록과 `_spec.unique_strength`·`unique_tooltip` 을 이 파일 값으로. gear_spec §5 의 "자기 상황" 열은 이 장 9.5 의 상황별 표로 바꾼다.')
    P('- **전체 힘**: 비보스 무기 효과가 1판보다 세다. 테스트 서버에서 보통 난이도 클리어율, 무리 사냥 속도(휩쓸기·과부하)를 본다. 너무 세면 상한 B 0.28 → 0.24 한 줄로 줄인다.')
    P('- **보스 장비 툴팁 접기 순서**(1판 6장)는 그대로 필요하다. 설명 줄 길이는 237개 모두 34자·330px 안이다(`ud_assign.py` problems 0).')
    P('')
    P('### 9.8 테스트 바뀜')
    P('')
    P('- `UniqueEffectCatalogTest`: 무기 237개 모두 `unique`. id 닫힌 목록. `imbue.chance` = round(0.25 × min(1.5, interval ÷ 0.67), 2). `shield_bash.n` = clamp(round(N기준 × 0.67 ÷ interval), 2, 8). `longshot` 은 `attack.style: ranged` 만. 수치 ≤ 카탈로그 상한 × g(한 방 보너스 셋만).')
    P('- `UniqueDiversityTest`: 종류 대신 (5레벨 띠, attack.style) 마다 direction 3개 이상. 같은 (띠, style, 획득처 종류, Lv) 안에 같은 효과 없음.')
    P('- `UniqueFairnessTest`(새, 순수): g 식(장검 0.67초 = 1, 단검 0.45초 ≈ 1.60, 장궁 1.25초 ≈ 0.56) · 대장간 × 0.8 · 신화 강도 0.5~0.8.')
    P('- `UniqueProcTest`: 재발동 `chain_spark` 0.3초 · `sanctify` 0.25초. `imbue` 확률을 서비스가 다시 곱하지 않는지.')
    P('- `TooltipFitTest`: 그대로(줄 수 안 바뀜). 설명 34자 검사를 237개에.')
    P('')
    md = os.path.join(D2, 'unique_spec.md')
    cur = open(md, encoding='utf-8').read()
    if MARK in cur:
        cur = cur[:cur.index(MARK)].rstrip()
        if cur.endswith('---'):
            cur = cur[:-3].rstrip()
        cur += '\n'
    open(md, 'w', encoding='utf-8').write(cur + '\n'.join(L) + '\n')
    print('md appended', len(L), 'lines; verdict_fail', verdict_fail, 'style_fail', len(style_fail))


if __name__ == '__main__':
    main()
