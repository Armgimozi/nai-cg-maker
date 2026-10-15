# -*- coding: utf-8 -*-
"""gear_spec.md 쓰기 (gs_build 를 실행해 값을 받는다)."""
import io
from gs_build import *          # noqa  (빌드 실행)
from gs_data import NEW_SHAPES, EXR, ARMOR, SHOP_PRICE, SHOP_UNLOCK, BOSS, FLOOR_NAME, GIMMICK

out = io.StringIO()
def w(s=''):
    out.write(s + '\n')

def pct(x, d=0):
    return f"{x * 100:.{d}f}%"

def kinds(wp):
    return KINDS_OF(wp)

def src_label(wp):
    k = wp['kind']
    if k == 'M+F':
        return '몬스터·상자+대장간'
    if k == 'B':
        return '보스' + (' (어려움+)' if wp['mythic'] else '')
    return KIND_KO[k]

def main_sec(wp):
    ks = [k for k in wp['stats'] if k != 'damage' and k not in wp['req'].split('|') and k != wp.get('req_old')]
    return SEC_KO.get(ks[0], ks[0]) if ks else '-'

def B_of(wp):
    return wp.get('B', wp['strength'] / 10)

# 자기 상황 (효과 설계자 규칙): P'(1+2B) ≥ 구간 최고 P'(1+B_최고)
best_w = {}
for b in range(1, 11):
    cand = [x for x in allw.values() if x['band'] == b and not x['mythic']]
    best_w[b] = max(cand, key=lambda x: x['P'])
def own_win(wp):
    bw = best_w[wp['band']]
    if wp['id'] == bw['id']:
        return '최고'
    return '✔' if wp['P'] * (1 + 2 * B_of(wp)) >= bw['P'] * (1 + B_of(bw)) else '-'

n_old, n_new = len(old), len(new)
w('# 미궁 라비린스 — 장비 늘리기 · 획득처 다시 짜기 (TASK C, 0.3.5 안)')
w()
w('주인 결정을 따른다. **무기 종류(대검·한손검·활·지팡이·홀·단검)를 게임에서 없앤다.** 무기마다 모양·공격 방식·요구 능력치·고유 효과가 따로 있다.')
w('그 위에서 무기를 늘리고, 상자·시련·특별 시련에서도 좋은 무기가 나오게 한다. 대장간과 보스가 늘 정답이 아니게 한다.')
w()
w('- 데이터: `gear_spec.json` (새 무기 106개 items.yml 형식 · 기존 무기 바꿈 · 방어구 6세트 · loot 바꿈 · 특별 시련 · 새 실루엣 · 테스트)')
w('- 계산 스크립트: `tools/gs_data.py`(설계 데이터) · `gs_core.py`(공식) · `gs_loot.py`(루팅·회차) · `gs_build.py`(검사·JSON) · `gs_md.py`(이 문서). `python3 tools/gs_md.py` 로 다시 만든다.')
w('- 고유 효과 이름·수치는 효과 설계자의 `unique_spec.json` 카탈로그(26개)와 `directions.json` 방향(12개)을 그대로 쓴다. 기존 131개 무기의 효과는 그대로 둔다.')
w()
w('## 0. 한눈에')
w()
w(f'| 항목 | 지금 (0.3.4) | 바꾼 뒤 |')
w('|---|---|---|')
w(f'| 무기 | {n_old} | **{n_old + n_new}** (+{n_new}) |')
w(f'| 방어구 세트 | 20 | 26 (+6: 판금 2 · 가죽 2 · 천 2, 24부위) |')
w(f'| 무기 모양 | 30 (근접·시전 25 + 활 5) | 45 (+15 새 실루엣) |')
w(f'| 5레벨 구간마다 무기 (신화 제외) | 9~21 | 22~25 |')
w(f'| 구간마다 획득처 종류 | 2~3 | 6~8 |')
top = spec['summary']['top_weapon_homes']
w(f"| 영웅 이상 무기 집 1곳 | 보스 32 · 대장간 36 · 몬스터·상자 6 | 보스 {top['B']} · 대장간 {top['F']} · 몬스터·상자 {top['M']} · 특별 시련 {top['S']} · 금고·미믹 {top['V']} · 시련 {top['T']} · 정예 {top['E']} |")
w(f'| 6·8·9·10층 몹·상자 무기 | 없음 (대장간만) | 다시 있음 (몬스터·상자 4·4·4·3개 + 시련·특별 시련·금고·정예) |')
w(f'| 검사 문제 | - | {len(problems)}건 |')
w()
w('핵심 규칙 세 줄:')
w('1. 같은 구간의 상자·시련·특별 시련·금고·정예 무기는 **대장간 무기와 기본 성능이 ±5% 안**이다. 다른 것은 고유 효과의 방향과 세기다.')
w('2. 보스 전설 무기는 기본 성능이 10~25% 높지만 고유 효과가 약하다(강도 0.8). 상자·시련 무기는 효과가 세다(강도 2.2~2.8). 자기 상황에서는 상자 무기가 이긴다.')
w('3. 대장간은 1회 안팎이면 만드는 **확정 바닥값**이다. 다른 곳은 4~7회 걸리지만 그 빌드의 핵심 효과가 붙는다.')
w()

# ───────── 1. 무기 종류 없애기 ─────────
w('## 1. 무기 종류 없애기')
w()
w('### 1.1 없어지는 것 · 남는 것')
w()
w('| 없어짐 | 대신 |')
w('|---|---|')
w('| items.yml `weapon_type` | `attack: {style, speed}` — 공격 방식(근접·원거리·시전)과 기본 공격 속도. 플레이어에게 분류 이름으로 보이지 않는다 |')
w('| 툴팁 분류 글자 "대검/한손검/활/지팡이/홀/단검" | 무기는 분류 줄 없이 "공격 속도 초당 1.5회 · 스킬 위력 31" 한 줄 |')
w('| 도감·대장간의 종류 필터, "내 직업 추천 장비만 보기" | "지금 낄 수 있는 것만 보기"(요구 능력치 충족) |')
w('| classes.yml `weapon_types`(추천 무기), 추천 무기 직업 스킬 재사용 −10% | 없음. 대신 직업 스킬 기본 재사용 대기를 0.9배로 (추천 무기를 들던 사람은 그대로) |')
w('| 직업 스킬 피해의 무기 종류 환산 (`WeaponTypes.classSkillScale`) | 무기마다 **스킬 위력**(1.4) |')
w('| 요구 능력치를 종류로 정함 (대검 STR …) | 무기마다 요구 능력치 (1.5). 값 공식 ceil(2.5×(L−1)) 은 그대로 |')
w('| config `weapon_attack_speed` 종류별 표 | 무기마다 `attack.speed` (`none` 맨손 1.6 만 남김) |')
w('| 시작 무기 = 추천 무기 중 최저 | classes.yml `starter_weapon: <id>` 로 직접 |')
w('| 드롭 직업 편향 (`classes`) | 능력치 편향 (1.6) |')
w()
w('남는 것: 무기마다의 모양(실루엣)과 실제 공격 방식. 활 모양은 활(BOW 아이템, 당겨 쏘기)이고, 시전 무기는 기본 공격이 근접 휘두르기다(지금도 기본 투사체는 없다).')
w()
w('### 1.2 공격 방식은 모양에서')
w()
w('| 방식 | 모양 | 기본 공격 | 무기 스킬 기본 피해 유형 | 무기 하나의 기본 공격 속도 |')
w('|---|---|---|---|---|')
w('| 원거리 `ranged` | longbow · recurve_bow · composite_bow · horn_bow · blade_bow · **bone_bow · twin_bow** | 바닐라 활 당기기 → 화살 | ranged | 1.2 (당김 1초 그대로) |')
w('| 시전 `caster` | staff_orb/crystal/ring/spiral/fork · scepter · sun_scepter · bell_scepter · chalice_scepter · censer_staff · **antler_staff · lamp_crook · thurible_rod · chime_rod** | 근접 휘두르기 (약함) | magic | 1.1~1.4 |')
w('| 근접 `melee` | 그 밖 전부 | 근접 휘두르기 | melee | 0.85~2.2 |')
w()
w('모양별 기본 공격 속도 (새 무기). 기존 131개는 지금 종류 속도 그대로라 숫자가 바뀌지 않는다 (검방 1.5 · 대검 0.95 · 단검 2.2 · 활 1.2 · 지팡이 1.1 · 홀 1.3).')
w()
sp = collections.defaultdict(list)
for k, v in SPEED.items():
    sp[v].append(k)
w('| 공속 | 모양 |')
w('|---|---|')
for v in sorted(sp):
    w(f"| {v} | {' · '.join(sorted(sp[v]))} |")
w()
w('### 1.3 피해 공식 (종류 없이)')
w()
w('items.yml 131개에서 맞춘 공식 (`tools/gs_fit.py`, 피해 비율 평균 1.002 · 표준편차 0.015):')
w()
w('```')
w('무기 힘      P(L)  = 7 + 0.25×(L−1) + 0.0195×(L−1)²')
w('희귀도 배율  R     = 일반 1.00 · 고급 1.06 · 희귀 1.13 · 영웅 1.21 · 전설 1.31 · 신화 1.45')
w('DPS 상수     K     = 근접 1.47 − 0.143×max(0, 공속 − 1.5) · 원거리 1.56 · 시전 1.22')
w('피해 가운데값      = P(L) × R × K ÷ 공속           (정수 [lo, hi], 반폭 3~12% — 지금 평균 6.8%)')
w('티어 위력  TP      = 피해 가운데값 × 공속 ÷ K       (= P(L) × R)')
w('주 스탯 줄         = (1 + 0.22L) × 희귀도 계수(일반 0.6 · 고급 0.8 · 희귀 1.0 · 영웅 1.2 · 전설 1.45 · 신화 1.75), 굴림 ×0.85~1.15')
w('부가 스탯          = 기준값(L) × 희귀도 계수 × 0.85~1.15 (능력치형 부가 ×0.6) — 개수: 일반·고급 1 · 희귀 2 · 영웅 3 · 전설 4 · 신화 5')
w('                     기준값: hp 3+3.2L · mp 2+1.6L · defense 1+0.35L · crit_chance 0.01+0.0009L · crit_damage 0.03+0.003L ·')
w('                     attack_speed 0.02+0.0009L · move_speed 0.01+0.0005L · cooldown_reduction 0.01+0.0009L · skill_damage 0.02+0.0015L ·')
w('                     mana_regen 0.1+0.015L · hp_regen 0.2+0.05L · heal_power 1+0.8L · lifesteal·damage_reduction·evasion 0.01+0.0006L')
w('요구 능력치        = ceil(2.5×(L−1)), 2 이하면 없음')
w('```')
w()
w('K 로 옛 종류 배율을 다시 만든다 (그래서 기존 무기를 안 고쳐도 된다):')
w()
w('| 옛 종류 | 옛 피해 배율 | 공속 | K÷공속 | 차이 |')
w('|---|---|---|---|---|')
for t, sc in OLD_SCALE.items():
    st, spd = OLD_TYPE_STYLE[t], OLD_TYPE_SPEED[t]
    hs = hit_scale(st, spd)
    w(f'| {t} | {sc:.2f} | {spd} | {hs:.3f} | {hs / sc - 1:+.1%} |')
w()
w('빠른 근접 무기(공속 1.5 초과)는 K 가 조금 낮다. 적중 훅(고유 효과·흡혈)을 더 자주 켜서다.')
w()
w('### 1.4 직업 스킬 위력 — 무기마다 `skill_power`')
w()
w('지금은 직업 스킬 피해 = 공격력 × 스킬 배율 × (추천 무기 배율 ÷ 든 무기 배율)이다. 종류가 없어지면 이 환산을 못 한다.')
w('그냥 공격력(무기 피해)을 쓰면 느리고 한 방이 큰 무기가 직업 스킬을 독차지한다(대검 1.55 vs 단검 0.62 = 2.5배).')
w('초당 피해(피해 × 공속)를 쓰면 시전 무기가 손해다(시전 0.81 vs 원거리 1.04).')
w()
w('**제안: 스킬 위력 = 티어 위력 TP × skill_power_mult.**')
w()
w('```')
w('skill_power      = 굴린 피해 가운데값 × 공속 ÷ K(방식, 공속) × skill_power_mult    (무기 없음 = 맨손 3)')
w('skill_power_mult = 1.0 (기본) · 1.05 (시전 무기 — 기본 공격이 17% 약한 대신)')
w('직업 스킬 피해   = skill_power × (1 + 0.02 × 직업 주스탯 혼합) × 스킬 배율 × classes.yml skill_scale')
w('skill_scale      = 수호기사 1.00 · 광전사 1.55 · 사냥꾼 1.30 · 비전술사 1.05 · 사제 0.90 · 그림자 0.62')
w('```')
w()
w('skill_scale 은 옛 "추천 무기 배율"을 직업 쪽으로 한 번 옮긴 것이다 (시전 직업은 ÷1.05). 그래서 0.3.4 에서 추천 무기를 든 사람은 직업 스킬이 그대로다(±2%).')
w('이제 무엇을 들든 같은 단계면 직업 스킬 위력이 거의 같고, 차이는 무기의 고유 효과·부가 스탯에서 난다.')
w()
for b in (5, 10):
    ws = sorted([x for x in allw.values() if x['band'] == b and not x['mythic']], key=lambda x: (-x['skill_power']))
    raw = [mid(x['stats']['damage']) for x in ws]
    dps = [mid(x['stats']['damage']) * x['speed'] for x in ws]
    spw = [x['skill_power'] for x in ws]
    w(f'{blabel(b)} 구간 무기 {len(ws)}개 (신화 제외) — 직업 스킬 기준값 비교:')
    w()
    w('| 기준 | 가장 낮음 | 가장 높음 | 최고 ÷ 최저 |')
    w('|---|---|---|---|')
    w(f'| 무기 피해 그대로 (환산 없음) | {min(raw):.1f} | {max(raw):.1f} | {max(raw) / min(raw):.2f}배 |')
    w(f'| 초당 피해 (피해 × 공속) | {min(dps):.1f} | {max(dps):.1f} | {max(dps) / min(dps):.2f}배 |')
    w(f'| **스킬 위력 (제안)** | {min(spw):.1f} | {max(spw):.1f} | **{max(spw) / min(spw):.2f}배** (희귀도·레벨 차이만) |')
    w()
eg = [allw[k] for k in ('ember_greatsword', 'dawnbringer', 'cinder_fang', 'bellows_composite_bow', 'cinder_crystal_staff', 'anvil_executioner_axe', 'cinder_dagger', 'forge_chime_rod')]
w('예 (21~25 구간):')
w()
w('| 무기 | 방식 | 공속 | 피해 | 스킬 위력 | 광전사 직업 스킬 기준(×1.55) | 0.3.4 광전사 기준 |')
w('|---|---|---|---|---|---|---|')
for x in eg:
    oldv = P(x['L']) * RM[x['rar']] * 1.55
    w(f"| {x['name']} `{x['id']}` | {STYLE_KO[x['style']]} | {x['speed']} | {x['stats']['damage'][0]}~{x['stats']['damage'][1]} | {x['skill_power']:.1f} | {x['skill_power'] * 1.55:.1f} | {oldv:.1f} |")
w()
w('대검(공속 0.95)과 단검(2.2)의 스킬 위력 차이는 희귀도·레벨 차이뿐이다. 느린 무기가 직업 스킬을 독차지하지 않는다.')
w()
w('### 1.5 요구 능력치 — 무기마다')
w()
w('값은 지금 공식 그대로다. 능력치만 무기마다 고른다. `requires_any` 두 능력치(혼합 빌드용)도 쓴다.')
w('새 무기는 방향에 맞춰 고르고, 같은 모양이라도 능력치가 다르다 (예: 뼈 활 = 힘·운·지능·민첩, 처형 도끼 = 힘·운).')
w(f'기존 무기 {len(EXR)}개도 바꾼다 (무기의 주 스탯 줄도 같은 능력치로, 숫자는 그대로):')
w()
w('| 무기 | 구간 | 지금 | 바꿈 | 이유 |')
w('|---|---|---|---|---|')
for k, (r, why) in EXR.items():
    x = old[k]
    w(f"| {x['name']} `{k}` | {blabel(x['band'])} | {x['req_old']} | {r.replace('|', ' 또는 ')} | {why} |")
w()
w('### 1.6 드롭 편향: 직업 → 능력치')
w()
w('loot.yml `own_class_bias: 0.65` 는 "내 직업에 어울리는 장비"(items.yml `classes`)만 고르던 편향이다. 종류가 없어지면 직업과 무기의 짝이 흐려진다.')
w('바꿈: 무기 one_of 를 고를 때 65% 확률로 **요구 능력치가 내 능력치(직업 기본 + 분배) 상위 2개 안에 드는 무기**만 후보로 (없으면 전체). 방어구는 지금처럼 겉모습·classes.')
w('이 명세의 모든 회차 계산은 이 규칙으로 했다. `classes` 필드는 새 무기에도 요구 능력치에서 뽑아 채워 둔다(옛 코드 호환).')
w()
w('### 1.7 코드 바꿀 곳')
w()
w('| 파일 · 메서드 | 바꿀 것 |')
w('|---|---|')
for a, b_ in [
    ('content/ItemDef · ContentParser.item', '`weaponType` 대신 `AttackStyle attackStyle()`(MELEE/RANGED/CASTER) · `double attackSpeed()` · `double skillPowerMult()`. items.yml `attack:{style,speed}`·`skill_power_mult` 파싱. `weapon_type` 이 있으면 경고(옮기는 동안)'),
    ('content/WeaponTypes', '삭제. 아래 사용처를 attackStyle 로'),
    ('combat/CombatListener.firedFromLabyrinthBow · items/GearItemService.isBow · items/crafting/BlacksmithMenu(아이콘 Material)', '`"bow".equals(weaponType())` → `attackStyle() == RANGED`'),
    ('items/weaponskills/LabWeaponSkillService.handle · defaultType · ProjectileSkills · AreaSkills', '활 입력 규칙·기본 피해 유형을 방식으로 (ranged → RANGED, caster → MAGIC, melee → MELEE)'),
    ('stats/StatService.applyAttributes', '`settings.weaponAttackSpeed(type)` → `weapon.attackSpeed()` (없으면 `none`)'),
    ('stats/StatCalculator.compute · DerivedStats', '`skillPower` 추가 = 굴린 damage × attackSpeed ÷ K(style, speed) × skillPowerMult (무기 없음 = UNARMED_DAMAGE). K 는 순수 함수 `CombatMath.dpsConstant(style, speed)`'),
    ('classes/skills/SkillContext.weaponScale', '`WeaponTypes.classSkillScale` → `cls.skillScale() × stats.skillPower() ÷ stats.weaponDamage()` (요구 미달 무기 = 맨손). dotRatio 도 같은 배율'),
    ('classes/LabyrinthClassService (쿨다운 371행 · 시작 무기 237~248행 · weaponName 444행) · ClassesModule 229행 · ui/menus/ClassMenu 43~48행', '추천 무기 −10% 와 "추천 무기" 문구 삭제, 시작 무기 = `cls.starterWeapon()`'),
    ('content/ClassDef · classes.yml', '`weapon_types`·`recommendsWeapon` 삭제, `skill_scale`·`starter_weapon` 추가, 직업 스킬 cooldown ×0.9'),
    ('items/ItemTooltip.category · inputName · lines', '무기 분류 글자 삭제, "공격 속도·스킬 위력" 한 줄, 활 입력 이름은 ranged 로. SOURCES 에 trial "시련" · special "특별 시련" · hoard "금고·미믹"'),
    ('ui/menus/CodexMenu (SOURCE_GROUPS · buildSources) · items/crafting/BlacksmithMenu 130행', '종류 필터 삭제, 획득처 그룹 3개 추가, "낄 수 있는 것만" 버튼'),
    ('items/loot/LootRoller (one_of 고르기)', '직업 편향 → 능력치 편향 (1.6)'),
    ('core/ContentValidator 130~170행', 'weapon_type 검사 → attack.style 과 모양이 맞는지(활 모양 ⇔ ranged), 속도 범위 0.6~2.5, longshot 고유 효과는 ranged·caster 만'),
    ('config.yml weapon_attack_speed', '`none: 1.6` 만'),
]:
    w(f'| {a} | {b_} |')
w()

# ───────── 2. 무기 수 ─────────
w('## 2. 무기 수 — 전과 후')
w()
w('### 2.1 지금 (0.3.4, 옛 종류 × 5레벨 구간)')
w()
types = ['greatsword', 'sword_shield', 'bow', 'dagger', 'staff', 'scepter']
TKO = {'greatsword': '대검', 'sword_shield': '한손검·방패', 'bow': '활', 'dagger': '단검', 'staff': '지팡이', 'scepter': '홀'}
w('| 종류 | ' + ' | '.join(blabel(b) for b in range(1, 11)) + ' | 합 |')
w('|---|' + '---|' * 11)
for t in types:
    row = [sum(1 for x in old.values() if x['wt'] == t and x['band'] == b) for b in range(1, 11)]
    w(f'| {TKO[t]} | ' + ' | '.join(str(v) for v in row) + f' | {sum(row)} |')
row = [sum(1 for x in old.values() if x['band'] == b) for b in range(1, 11)]
w('| **합** | ' + ' | '.join(f'**{v}**' for v in row) + f' | **{sum(row)}** |')
w()
w('구간에 종류마다 1~4개, 1개뿐인 칸이 많다. 6·8·9구간(26~30·36~40·41~45)은 9개뿐이고 대장간·보스 두 곳에서만 나온다.')
w()
w('### 2.2 바꾼 뒤 (구간 전체 — 종류 없음)')
w()
w('| 구간 | 무기 (신화 제외) | 새 | 근접 | 원거리 | 시전 | STR | DEX | INT | WIS | VIT | LUK | 방향 수 | 획득처 종류 |')
w('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for b in range(1, 11):
    ws = [x for x in allw.values() if x['band'] == b and not x['mythic']]
    st = collections.Counter(x['style'] for x in ws)
    rq = collections.Counter(r for x in ws for r in x['req'].split('|') if req_value(x['L']))
    ks = set(k for x in ws for k in kinds(x))
    myth = sum(1 for x in allw.values() if x['band'] == b and x['mythic'])
    w(f"| {blabel(b)} | {len(ws)}{f' (+신화 {myth})' if myth else ''} | {sum(1 for x in ws if x['new'])} | {st['melee']} | {st['ranged']} | {st['caster']} | "
      + ' | '.join(str(rq[s]) for s in STATS6) + f" | {len(set(x['dir'] for x in ws))}/12 | {len(ks)} |")
w()
w('요구 능력치 수에 `requires_any` 무기는 두 능력치에 다 센다. 1~5 구간의 Lv1 무기 6개는 요구가 없어 빠진다.')
w()
w('### 2.3 왜 237개인가')
w()
w('- 한 캐릭터가 한 구간에서 고를 수 있어야 하는 것 = **내 주 능력치로 낄 수 있는 무기 3개 이상, 방향이 서로 다르고 획득처가 2곳 이상**.')
w('  능력치 6개 × 3 = 18개가 바닥이다. 여기에 보스 고유 무기 2~3개, 두 능력치 무기(requires_any) 1~2개를 더하면 구간마다 22~23개.')
w('- 10구간 × 23 = 230. 1~5 구간은 1층·2층 Lv5 무기가 겹쳐 25개, 46~50 구간은 신화 6개가 어려움 이상 전용이라 보통에서 고를 수 있게 22개를 맞췄다(전체 25).')
w(f'- 그래서 {n_old} + {n_new} = **{n_old + n_new}** (+{n_new}, 상한 +110 안). 새 무기를 구간마다 지금 모자란 만큼만 넣었다: 4·14·8·8·9·14·8·14·14·10.')
w('- 더 늘리지 않는 이유: 같은 구간 같은 방향·같은 능력치가 겹치기 시작하면 "선택지"가 아니라 "중복"이 된다. 지금 수에서 겹치는 쌍은 0개다.')
w()

# ───────── 3. 획득처 행렬 ─────────
w('## 3. 획득처 종류 행렬')
w()
w('구간마다 무기 수 (신화 제외). 몬스터·상자 = 그 층 `gear_fNN_common`(일반 몹·보물방·미로 상자) · 시련 = 시련방(기믹방) 성공 상자 · 특별 시련 = 5장 · 금고·미믹 = 열쇠 금고 금 상자와 길들인 미믹 상자 · 정예 = 그 층 정예 · 상인 = 떠돌이 상인 핀.')
w()
KORD = ['B', 'F', 'M', 'T', 'S', 'V', 'E', 'P']
w('| 구간 | ' + ' | '.join(KIND_KO[k] for k in KORD) + ' | 종류 수 |')
w('|---|' + '---|' * 9)
for b in range(1, 11):
    ws = [x for x in allw.values() if x['band'] == b and not x['mythic']]
    c = collections.Counter(k for x in ws for k in kinds(x))
    w(f'| {blabel(b)} | ' + ' | '.join(str(c[k]) if c[k] else '·' for k in KORD) + f' | {sum(1 for k in KORD if c[k])} |')
w()
w('1~5 구간의 "몬스터·상자+대장간"(1층 Lv3 일반 6개)은 두 칸에 다 셌다. 영웅 이상은 모두 한 칸뿐이다.')
w()

# ───────── 4. 구간별 증명 ─────────
w('## 4. 구간마다 "정답이 하나가 아니다" — 증명 표')
w()
w('열: 희귀도·숨은 Lv · 방식 · 공속 · 피해 · DPS(피해 가운데값 × 공속) · 티어 위력 TP(대장간 기준 대비) · 주 부가 스탯 · 방향 · 요구 · 획득처 · 고유 강도 s · 자기 상황.')
w('"자기 상황" = 효과 설계자 규칙 P′×(1+2B) ≥ 구간 최고 P′×(1+B최고) — 효과가 맞는 상황(무리·빈사·출혈 빌드 등)에서 효과 가치가 두 배라고 볼 때 구간 최고 무기를 이기면 ✔.')
w('P′ = TP × (1 + 부가 스탯 가치 + 0.1 × 무기 스킬 수). 굵게 = 새 무기.')
w()
for b in range(1, 11):
    ref = FORGE[b]['ref_tp']
    ws = sorted([x for x in allw.values() if x['band'] == b],
                key=lambda x: (KORD.index(kinds(x)[0]) if kinds(x)[0] in KORD else 9, -x['tp']))
    side = [x for x in ws if x['new'] and x['kind'] in 'MTSVE']
    mx = max(abs(x['tp'] / ref - 1) for x in side)
    wins = sum(1 for x in ws if not x['mythic'] and own_win(x) in ('✔', '최고'))
    bw = best_w[b]
    w(f"### {blabel(b)} 구간 — 대장간 기준 TP {ref:.1f} (`{FORGE[b]['recipe']}`, {RAR_KO[FORGE[b]['rarity']]} Lv{FORGE[b]['level']})")
    w()
    w(f"새 옆길 무기 {len(side)}개 모두 기준 ±5% 안 (가장 먼 것 {mx:+.1%}). 구간 최고 P′ = {bw['name']}({src_label(bw)}). 자기 상황에서 최고를 이기는 무기 {wins}개.")
    w()
    w('| 무기 | 희귀도·Lv | 방식 | 공속 | 피해 | DPS | TP (기준 대비) | 주 부가 | 방향 | 요구 | 획득처 | s | 자기 상황 |')
    w('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for x in ws:
        nm = f"**{x['name']}** `{x['id']}`" if x['new'] else f"{x['name']} `{x['id']}`"
        d = x['stats']['damage']
        rq = x['req'].replace('|', '/') if req_value(x['L']) else '-'
        w(f"| {nm} | {RAR_KO[x['rar']]} {x['L']} | {STYLE_KO[x['style']]} | {x['speed']} | {d[0]}~{d[1]} | {mid(d) * x['speed']:.1f} | "
          f"{x['tp']:.1f} ({x['tp'] / ref - 1:+.0%}) | {main_sec(x)} | {DIRS[x['dir']]['name']} | {rq} | {src_label(x)} | {x['strength']:.2f} | {own_win(x) if not x['mythic'] else '(어려움+)'} |")
    w()

# ───────── 5. 특별 시련 ─────────
w('## 5. 특별 시련 (가장 적은 공사로)')
w()
w('### 5.1 무엇인가')
w()
w(f'- 층마다 있는 시련방(기믹방) 하나가 **{pct(SPECIAL_Q)} 확률로 "특별 시련"**이 된다. 기믹은 같고 **조건 하나**가 붙는다. 들어가면 바로 알려 준다.')
w('- 기믹 성공 + 조건 지킴 → 평소 상자(gimmick_floor_N) **에 더해** 특별 상자(`special_trial_fNN`, 개인 루팅)가 하나 더 놓인다. 경험치 +50%.')
w('- 기믹 성공 + 조건 깨짐 → 평소 상자만 (실패가 아니다). 기믹 실패 → 지금과 같다.')
w('- 같은 층을 4번 연속 특별 시련 없이 돌면 다음 방문은 반드시 특별 시련 (`pity_visits: 4`, 파티원 중 가장 큰 값 — 선택 기능, PlayerData 층별 카운터).')
w('- 특별 상자는 그 층 특별 시련 전용 무기 1개 확정 (+ 6·9층은 특별 시련 방어구 50%) + 그 층 정수 1.')
w()
w('### 5.2 조건 4종 (공통 구현)')
w()
w('| id | 이름 | 판정 | 그 기믹이 지원해야 하는 것 |')
w('|---|---|---|---|')
w('| `swift` | 서두름 | 기믹 시작부터 성공까지 `seconds` 초 이하. 보스바에 남은 초 | 없음 (GimmickRoom.elapsed) |')
w('| `unscathed` | 무상 | 방 안에서 최대 HP 3% 이상 맞은 횟수 ≤ 2 + 파티원 1명당 1 | 없음 (피해 훅) |')
w('| `abstain` | 절제 | 방 안에서 물약·주문서를 하나도 안 씀 | 없음 (소모품 훅) |')
w('| `flawless` | 무결 | 기믹의 "실수"(기회 하나 잃음) 0번 | 실수할 때 `noteMistake()` 를 부른다 — lever_sequence · resonance_tune · book_cipher · gear_timing 만 |')
w()
w('### 5.3 층별')
w()
w('| 층 | 기믹 | 조건 후보 (둘 중 하나, 시드로) | swift 초 | 특별 상자 무기 | 특별 상자 방어구 |')
w('|---|---|---|---|---|---|')
for f in range(1, 11):
    pf = SPECIAL['per_floor'][f]
    arm = ', '.join(sorted(set(armor_items[a]['armor_set'] for a in pf['armor']))) or '-'
    w(f"| {f} {FLOOR_NAME[f]} | `{pf['gimmick']}` | {' · '.join(pf['conditions'])} | {pf['swift_seconds'] or '-'} | "
      f"{', '.join(new[i]['name'] for i in pf['weapons'])} | {arm} |")
w()
w('swift 초 = 그 기믹이 보통 걸리는 시간의 0.7배 (제한 시간이 있는 lights_out 120초 → 84, book_cipher 180 → 126). 조건 후보는 그 기믹과 겹치지 않게 골랐다 (spore_purge 는 감염 피해가 있어 unscathed 를 빼고, void_trial 은 60초 버티기라 swift 를 뺐다).')
w()
w('### 5.4 문구 (공략 없이, 분위기만)')
w()
t = SPECIAL['texts']
w('| 자리 | 문구 |')
w('|---|---|')
w(f"| 방 안 글자판 | `<gold><b>✦ 특별 시련: {{기믹 이름}} ✦</b></gold>` + 기믹 안내 + `<yellow>{{조건}}</yellow>` |")
w(f"| 들어갈 때 가운데 글자 | {t['title']} / {t['subtitle']} |")
w(f"| 채팅 | {t['chat']} |")
for k, v in t['conditions'].items():
    w(f'| 조건 `{k}` | {v} |')
w(f"| 조건 깨짐 | {t['broken']} |")
w(f"| 조건 지킴 (성공 때) | {t['kept']} |")
w()
w('기믹을 푸는 방법은 적지 않는다. 조건은 "무엇을 하지 마라 / 언제까지"만 말한다.')
w()
w('### 5.5 설정 키')
w()
w('```yaml')
w('# dungeon.yml')
w('special_trial:')
w(f'  enabled: true')
w(f'  chance: {SPECIAL_Q}          # 층 방문마다 시련방이 특별 시련일 확률 (시드 고정)')
w(f'  pity_visits: 4         # 이만큼 연속 못 보면 다음은 확정 (0 = 끔)')
w(f'  xp_bonus: 0.5          # 조건까지 지키면 시련 경험치 ×1.5')
w('  conditions:')
w('    swift:     {time_factor: 0.7, min_seconds: 40, default_seconds: 75}')
w('    unscathed: {hits: 2, per_member: 1, min_damage: 0.03}')
w('    abstain:   {potions: true, scrolls: true}')
w('    flawless:  {}')
w('# floors.yml (층마다, 생략하면 위 기본표)')
w('#  special_trial: {conditions: [flawless, swift], seconds: 60}')
w('# loot.yml')
w('#  special_trial_f01 … special_trial_f10   (6.3)')
w('```')
w()
w('### 5.6 코드')
w()
w('| 파일 · 메서드 | 할 일 |')
w('|---|---|')
for a, b_ in [
    ('새 `dungeon/rooms/SpecialTrial` (순수)', '`record SpecialTrial(Condition cond, int seconds, int hits)` · `static SpecialTrial pick(long seed, FloorDef def, DungeonConfig.Special cfg, int pityCount)` · `enum Condition {SWIFT, UNSCATHED, ABSTAIN, FLAWLESS}` · `boolean kept(Stats s)` (경과 초·맞은 횟수·소모품 수·실수 수) — 단위 테스트 대상'),
    ('dungeon/DungeonConfig · dungeon.yml', '`special_trial:` 블록 읽기 (`Special` record)'),
    ('content/FloorDef · ContentParser', 'floors.yml `special_trial:` 덮어쓰기 (선택)'),
    ('dungeon/FloorState.createRoom (115행)', 'GIMMICK 방을 만들 때 `SpecialTrial.pick(seed ^ 방 번호, def, cfg, pity)` 를 GimmickRoom 에 넘긴다'),
    ('dungeon/rooms/GimmickRoom', '필드 `special`(null 가능) · `brokenReason` · 카운터(hits, consumes, mistakes). `onReady`: 글자판을 특별판으로. `onEnter`: 제목·채팅 안내. `tick`: swift 남은 초를 보스바 status 에 붙이고 넘으면 `breakCondition("시간")`. `succeed()`: `special != null && broken == null` 이면 `fs.loot("special_trial_f%02d", winners, …)` + xp ×1.5 + 성공 문구, 아니면 지금 그대로. 새 `protected void noteMistake()` · `public void onPlayerHurt(Player, double pct)` · `public void onConsume(Player, ItemDef)`'),
    ('gimmicks/LeverSequence 151행 · ResonanceTune 157행 · BookCipher 183행 · GearTiming 192행', '기회를 잃는 자리에서 `noteMistake()` 한 줄'),
    ('combat/DamageService (훅) 또는 DungeonManager 피해 리스너', '피해를 받은 플레이어가 인스턴스의 진행 중 GimmickRoom 안이면 `room.onPlayerHurt(p, 피해 ÷ 최대 HP)`'),
    ('items/ConsumableListener.onConsume (103행) · 주문서 사용', '사용 후 `services.dungeon().onConsume(p, def)` → 그 방으로'),
    ('core/Hints', '특별 시련도 같은 힌트 키 (기믹 실패만 센다, 조건 깨짐은 안 센다)'),
    ('dungeon/SelfTest', '층마다 특별 시련 하나 강제 → 조건 4종 판정·특별 상자 지급 확인 (`special_trials=10`)'),
    ('items/ItemTooltip · ui/menus/CodexMenu', '획득처 "특별 시련 (N층)"'),
]:
    w(f'| {a} | {b_} |')
w()

# ───────── 6. 확률 ─────────
w('## 6. 확률과 기대 회차')
w()
w('### 6.1 1회 돌기 가정 (보통 · 솔로 · LUK 0 · 층 끝까지)')
w()
w('| 층 | 일반 몹 | 보물방 상자 | 미로 상자 나무/철/금(금고 포함) | 금고 금 상자 | 미믹 | 시련 성공 | 특별 시련 성공 | 정예 | 1회 골드 |')
w('|---|---|---|---|---|---|---|---|---|---|')
for f in range(1, 11):
    c = maze(f)
    w(f"| {f} | {MOBS_RUN[f]} | {TREASURE_ROOMS[f] * TREASURE_CHESTS:.1f} | {c['wood']}/{c['iron']}/{c['gold'] + c['secret'] + c['vault']:.2f} | {c['vault']:.2f} | {c['mimic']:.2f} | {GIMMICK_OK} | {SPECIAL_Q * SPECIAL_C:.3f} | {ELITES[f]} | {GOLD[f]:,.0f} |")
w()
w('미로 상자 수는 0.3.4 자가 진단 10층(chests=113 · vaults=10 · secret_rooms=17 · mimics=14)에서 잡았다. 시련 성공 0.8 · 특별 조건 지킴 0.65 는 추정값이다.')
w('"기대 회차" = 내 주 능력치에 맞는 그 무기 하나를 얻기까지 평균 몇 번 돌아야 하나 (능력치 편향 0.65 포함, 기하분포 1/p).')
w()
w('### 6.2 항목 확률')
w()
w('| 획득처 | 테이블 · 항목 | 확률 |')
w('|---|---|---|')
w(f'| 몬스터·상자 | 몹 · 보물방 · 미로 상자의 `{{table: gear_fNN_common}}` | 기준(몹 층별 0.03→0.012 · 보물방 0.07 · 나무 0.03 · 철 0.06 · 금 0.10) × 층 배율 (6.4) |')
w(f'| 시련 | `gimmick_floor_N` 의 `{{table: trial_gear_fNN, chance: {T_RATE}}}` (상자 2번 굴림, 4층은 방어구 포함 0.25) | 몬스터·상자 무기 항목은 시련 상자에서 뺀다 |')
w(f'| 금고·미믹 | 금고 금 상자·길들인 미믹 상자를 열 때 `hoard_gear_fNN` 를 한 번 더 | 무기 항목 ' + ' · '.join(f'{f}층 {H_RATE(f)}' for f in (1, 4, 7, 10)) + ' (금고+미믹 상자 수에 맞춤) |')
w(f'| 특별 시련 | `special_trial_fNN` guaranteed one_of | 확정 1개 (특별 시련이 나와 조건까지 지켰을 때) |')
w(f'| 정예 | 그 층 정예 테이블 `{{one_of: [...], chance}}` | 1~8층 {E_RATE[1]} · 9~10층(정예 2마리) {E_RATE[9]} |')
w('| 상인 | npcs.yml merchant shop + `unlock_floor` | 골드 (6.3) |')
w()
w('### 6.3 구간 × 획득처 기대 회차 (가운데값, 범위)')
w()
w('| 구간 | 보스 | 대장간 (재료 회차 · 골드 회차) | 몬스터·상자 | 시련 | 특별 시련 | 금고·미믹 | 정예 | 상인 (값 · 골드 회차) |')
w('|---|---|---|---|---|---|---|---|---|')
def fmt(t):
    if not t:
        return '·'
    lo, md, hi = t
    return f'{md}' if lo == hi else f'{md} ({lo}~{hi})'
for b in range(1, 11):
    r = RATES[b]
    fz = r['F']
    sh = ', '.join(f"{new[p['item']]['name']} {p['price']:,}G · {p['gold_runs']}" for p in r['P']) or '·'
    w(f"| {blabel(b)} | {fmt(r['B'])} | {fz['mat_runs']} · {fz['gold_runs']} ({fz['gold']:,}G) | {fmt(r['M'])} | {fmt(r['T'])} | {fmt(r['S'])} | {fmt(r['V'])} | {fmt(r['E'])} | {sh} |")
w()
w('읽는 법:')
w('- **대장간**은 재료가 1회에 넉넉히 모여(층 몹 재료 1회 40~80개, 정예 재료 3.6~5.5개) 1회 안팎이면 만든다. 확정이고 빠르다 → 바닥값.')
w('- **몬스터·상자**는 1~3층 2회 안팎, 영웅 층(5·6·8·9·10) 4.5회. 지금은 5층 영웅 무기가 거의 매번 나왔다(1회 이하) — 이번에 내렸다.')
w('- **시련·금고·정예** 4~5회, **특별 시련** 5~7회. 대장간보다 4~6배 오래 걸리는 대신 같은 단계에서 효과가 세다(s 2.2~2.8, 대장간 무기는 0.8~2.8, 보스 전설 0.8).')
w('- **보스 고유**는 지금 그대로(1~9회). 신화는 어려움 이상 10층 보스만.')
w('- **상인**은 1~3층만. 그 층 1회 골드의 1.7~1.9배 — 재료 없이 바로 사는 대신 강화 골드를 미룬다. 그 층 보스를 한 번 잡아야 진열된다.')
w('- 어느 것도 1회 미만(공짜)이 아니고 10회 넘는(노가다) 것도 없다. 파티면 각자 굴린다(개인 루팅), 파티 보너스 +5%/명.')
w()
w('### 6.4 몬스터·상자 층 배율 (지금 → 바꿈)')
w()
w('| 층 | 목표 회차 | 배율 | 일반 몹 | 보물방 | 나무 | 철 | 금 | 표 크기 |')
w('|---|---|---|---|---|---|---|---|---|')
for f in range(1, 11):
    fac = MF.get(f, 1.0)
    n = len((tables.get(tid_common(f)) or {}).get('entries', [{}])[0].get('one_of', []))
    oldm = [e['chance'] for t in floor_tables(f)[0] for e in (LOOT[t].get('entries') or []) if e.get('table') == tid_common(f)]
    oldv = f"{max(oldm):g}" if oldm else '없음'
    w(f"| {f} | {M_TARGET[f]} | {fac:.3f} | {oldv} → {M_BASE_MOB[f] * fac:.4f} | {0.07 * fac:.4f} | {0.03 * fac:.4f} | {0.06 * fac:.4f} | {0.10 * fac:.4f} | {n} |")
w()
w('1층은 첫 장비라 거의 그대로다. 6·8·9·10층은 표가 다시 생긴다(r1 에서 없앤 몹·상자 무기를 새 영웅 무기로 되살림).')
w()

# ───────── 7. 새 무기 목록 ─────────
w('## 7. 새 무기 106개 (구간별)')
w()
w('수치·무기 스킬 조합·모델 색은 `gear_spec.json` weapons 에 items.yml 형식으로 있다. 여기는 이름·모양·요구·고유 효과·획득처·이야기.')
w()
for b in range(1, 11):
    ws = sorted([x for x in new.values() if x['band'] == b], key=lambda x: ('MTSVEP'.index(x['kind']), x['id']))
    w(f'### {blabel(b)} ({len(ws)})')
    w()
    w('| 무기 | 층·Lv·희귀도 | 모양 (방식·공속) | 요구 | 고유 효과 (강도) | 무기 스킬 | 획득처 | 이야기 |')
    w('|---|---|---|---|---|---|---|---|')
    for x in ws:
        so = x['source']
        if so['kind'] == 'P':
            src = f"상인 핀 {so['price']:,}G ({so['unlock_floor']}층 보스 후)"
        else:
            src = f"{KIND_KO[so['kind']]} `{so['table']}` {'확정' if so.get('guaranteed') else so['chance']}" + (f" (묶음 {so['pool']})" if so['pool'] > 1 else '')
        shp = NEW_SHAPES.get(x['shape'])
        shape = f"**{shp['name']}** `{x['shape']}`" if shp else f"`{x['shape']}`"
        sk = x['skill']['name'] if x.get('skill') else '-'
        R = req_value(x['L'])
        w(f"| {x['name']} `{x['id']}` | {x['F']}층 Lv{x['L']} {RAR_KO[x['rar']]} | {shape} ({STYLE_KO[x['style']]} {x['speed']}) | "
          f"{(x['req'].replace('|', '/') + ' ' + str(R)) if R else '-'} | {x['uname']}: {x['udesc']} ({x['strength']:.2f}) | {sk} | {src} | {x['lore']} |")
    w()

# ───────── 8. 모델 ─────────
w('## 8. 모델')
w()
w('### 8.1 규칙')
w()
w('- 새 무기 106개 중 74개가 새 실루엣 15종, 32개가 기존 템플릿(longsword·kris·dagger·katar·great_axe·cleaver·glaive·greatsword·falchion·broadsword·mace·sickle·fang_blade·longbow·recurve_bow·composite_bow·blade_bow·staff_orb·staff_ring·sun_scepter·chalice_scepter·censer_staff·bell_scepter)을 새 색으로.')
w('- 테마 장식(dress_blade·dress_shaft·dress_bow·층 테마 THEME_KEYS)은 id 로 잡힌다. 새 id 는 모두 기존 키(moss/corridor/root · skitter/silk · miners/ore_ · spore/mycel/glowcap/hypha · brine/tide/eel/drowned/sluice/verdigris · ember/cinder/slag/anvil/bellows/forge · rime/frost · prism/geode/amethyst/shardglass/crystal/resonan · ink/lore/index · clock · abyss/void)를 품는다. `pit_*` 두 개는 style rusted_iron → forge.')
w('- 희귀도 장식 단계(P.lv 0~5)는 그대로: 일반 깨끗 → 희귀 테두리·보석 → 영웅 테마 모티프. 새 무기에 전설·신화는 없다(아우라·애니메이션 없음).')
w('- **손에 드는 각도**: 0.3.4 의 모양별 방식 그대로 — `voxel/weapons.HOLD[shape]`(fp_yaw), `TWO_HANDED`, 활은 `BOWS`(displays.voxel_bow), `tools/hold_preview.HEAD_SHAPES`(옆으로 머리가 있는 모양, 바닐라 도끼 행과 비교). 새 모양마다 아래 표의 값을 넣고 `python tools/hold_preview.py --shapes <새 모양들>` 로 시트를 보고 metrics 를 같은 무게 기존 모양과 비교한다.')
w()
w('### 8.2 새 실루엣 15종')
w()
w('| 모양 | 이름 | 계열 | 방식·공속 | 양손 | 옆 머리 | HOLD | 쓰는 무기 수 |')
w('|---|---|---|---|---|---|---|---|')
use = collections.Counter(x['shape'] for x in new.values())
for k, v in NEW_SHAPES.items():
    w(f"| `{k}` | {v['name']} | {v['family']} | {STYLE_KO[v['style']]} {v['speed']} | {'예' if v['two_handed'] else '-'} | {'예' if v['head_sideways'] else '-'} | {v['hold'] or '활 기본'} | {use[k]} |")
w()
for k, v in NEW_SHAPES.items():
    w(f"**`{k}` {v['name']}**")
    w(f"- 만들기: {v['build']}")
    w(f"- 부품: {v['parts']}")
    w(f"- 색 역할: {v['palette_roles']}")
    w(f"- 손에 들기: {v['hold_note']}")
    w()
w('표에 넣을 것 (voxel/weapons.py):')
w()
w('```python')
w("_TEMPLATES.update({'executioner_axe': executioner_axe, 'flamberge': flamberge, 'great_maul': great_maul, 'sabre': sabre,")
w("                   'morning_star': morning_star, 'rapier': rapier, 'stiletto': stiletto, 'tanto': tanto, 'war_spear': war_spear,")
w("                   'antler_staff': antler_staff, 'lamp_crook': lamp_crook, 'thurible_rod': thurible_rod, 'chime_rod': chime_rod})")
w("BOWS = (..., 'bone_bow', 'twin_bow')            # bow(g, p, kind) 의 curv 표에 bone_bow 3.4 · twin_bow 3.2")
w("TWO_HANDED |= {'executioner_axe', 'flamberge', 'great_maul', 'war_spear'}")
w("HOLD.update({'sabre': {'fp_yaw': 100}})          # 나머지는 기본 90")
w("# tools/hold_preview.py")
w("HEAD_SHAPES += ('executioner_axe', 'great_maul', 'morning_star', 'lamp_crook', 'thurible_rod')")
w('```')
w()

# ───────── 9. 방어구 ─────────
w('## 9. 새 방어구 6세트')
w()
w('겉모습 요구 능력치 규칙은 그대로다(판금 VIT · 가죽 DEX · 천 INT|WIS). 수치는 GDD §16.4 방어구 공식(세트 방어 합 = (3+0.95L) × 무게 × 희귀도, 부위 비중 20/35/27/18%, 주 스탯 ×1.7, 부가 ×2.0, 신발 이동 속도는 기준값).')
w('겉모습별 장단점(판금·가죽·천) 규칙이 따로 정해지면 이 세트들도 같은 규칙을 받는다 — 세트는 `sets.<id>.look` 만 맞으면 된다.')
w('3D 어깨·등 장식은 `armor_pieces.py` 가 look·back·테마·흉갑 색으로 자동으로 만든다. 장비 텍스처는 `equipment.py` paint_set(look) + style 로.')
w()
for a in ARMOR:
    sd = armor_sets[a['id']]
    srcs = ' + '.join(KIND_KO[k] for k in a['kind'])
    w(f"### {a['name']} `{a['id']}` — {a['floor']}층 · Lv{a['L']} · {RAR_KO[a['rarity']]} · {dict(heavy='판금', light='가죽', cloth='천')[a['look']]} · 획득처 {srcs}")
    w()
    w(f"- 세트 효과: 2부위 {a['bonuses'][2]} · 4부위 {a['bonuses'][4]}")
    w(f"- 색: style `{a['style']}` · {' '.join(a['palette'])} · 등 `{a['back']}`")
    w(f"- 장비 텍스처 무늬: {a['motif']}")
    w(f"- 3D 장식: {a['pieces3d']}")
    w(f"- 이야기: {a['lore']}")
    w()
    w('| 부위 | 이름 | 모양 | 요구 | 스탯 |')
    w('|---|---|---|---|---|')
    for p in sd['pieces']:
        it = armor_items[p]
        rq = it.get('requires') or it.get('requires_any')
        w(f"| {it['armor_slot']} | {it['name']} `{p}` | {it['model']['shape']} | {rq} | {it['stats']} |")
    w()
w('세트를 고른 이유: 겉모습별로 구간이 비어 있던 곳을 메운다.')
w('- 판금: 2층 Lv8 → 4층 Lv19 사이 (3층 균사 갑각 Lv14), 7층 Lv34 → 9층 Lv44 사이 (8층 색인 방벽 Lv38)')
w('- 가죽: 3층 Lv14 → 6층 Lv24 사이 (4층 수로 잠수부 Lv19), 6층 Lv24 → 7층 Lv34 사이 (6층 서리 추적자 Lv28)')
w('- 천: 3층 Lv14 → 6층 Lv24 사이 (5층 잿불 성가자 Lv23), 8층 Lv34 → 10층 Lv44 사이 (9층 태엽 점성술사 Lv42)')
w('- 획득처도 새 종류로: 정예+대장간 2세트(판금), 시련+대장간 1, 금고·미믹 1, 특별 시련 2.')
w()

# ───────── 10. 파일 바꿈 요약 ─────────
w('## 10. 데이터 파일 바꿈 요약')
w()
ops = collections.Counter(v['op'] for v in loot_json.values())
w(f"- **items.yml**: 새 무기 {n_new} (gear_spec.json weapons — `direction`·`model_recipe`·`source`·`band`·`tier_power`·`vs_forge`·`unique_strength`·`unique_tooltip`·`expected_runs_fit` 는 명세용, 넣을 때 뺀다) · 새 방어구 24 + sets 6 · 기존 무기 131개 `weapon_type` → `attack` (existing_changes), 그중 {len(EXR)}개 요구 능력치·주 스탯 줄 이름 바꿈, 시전 무기 `skill_power_mult: 1.05` · sources 값에 trial / special / hoard 추가.")
w(f"- **loot.yml**: 테이블 {len(loot_json)}개 (새 {ops['new']} · 다시 씀 {ops['replace'] + ops['replace_entries']}) — gear_fNN_common 5개(2층 늘림, 6·8·9·10층 새로), trial_gear_fNN 10, special_trial_fNN 10, hoard_gear_fNN 10, 시련 상자 10(몬스터·상자 항목 빼고 시련 표), 정예 9, 몹·보물방·미로 상자의 몬스터·상자 확률. 머리 주석의 '6·8·9·10층은 없음' 줄을 고친다.")
w(f"- **npcs.yml**: merchant shop 에 3줄 ({', '.join(f'{new[e['item']]['name']} {e['price']:,}G·{e['unlock_floor']}층' for e in shop_json)}).")
w(f"- **recipes.yml**: 방어구 12개 (균사 갑각·수로 잠수부·색인 방벽). 새 무기 레시피는 없다 — 대장간 무기는 지금 36개(영웅+)가 그대로 기준이다.")
w('- **classes.yml**: weapon_types 삭제, skill_scale·starter_weapon 추가, 직업 스킬 cooldown ×0.9.')
w('- **config.yml**: weapon_attack_speed 는 none 만. **dungeon.yml**: special_trial 블록. **floors.yml**: (선택) special_trial 덮어쓰기.')
w('- **titles.yml**: 바꾸지 않는다 (칭호 12개 그대로). 특별 시련 카운터 `titles.trial.special` 만 기록해 두면 다음에 쓸 수 있다.')
w()

# ───────── 11. 테스트 ─────────
w('## 11. 테스트로 만들 것')
w()
for t in TESTS:
    w(f"**{t['name']}** — `{t['file']}`")
    for c in t['checks']:
        w(f'- {c}')
    w()
w(f'이 명세는 위 검사를 스크립트로 이미 돌렸다 (`gs_build.py` problems = {len(problems)}).')
w()

# ───────── 12. 남은 일 ─────────
w('## 12. 주의 · 남은 일')
w()
w('- 대장간이 싸다. 재료가 1회에 넉넉해 대장간 무기는 1회 안팎이면 나온다. 이 명세는 대장간을 "확정 바닥값"으로 두고 다른 곳을 효과로 차별했다. 대장간을 더 어렵게 하려면 레시피의 정예 재료를 2~3개로 올리는 것이 가장 덜 건드리는 방법이다(1회 3.6~5.5개 → 1회 안팎 그대로라 효과는 작다). 강화 골드가 더 큰 골드 소비처다.')
w('- 보스 고유 무기 회차(1~9회)는 그대로 뒀다. 능력치 편향으로 바꾸면 "내 직업 무기" 대신 "내 능력치 무기" 확률이라 bossUniqueWeaponsDropOftenEnough 테스트의 숫자를 다시 맞춰야 한다 (보스 묶음 대부분이 능력치가 서로 달라 크게 변하지 않는다).')
w('- 효과 설계자의 기존 131개 강도(s)는 종류별 구간으로 계산된 값이다. 종류가 없어지면 구간 전체로 다시 계산하는 편이 맞다 — 이 명세는 새 무기만 구간 전체 규칙으로 계산했다. 다시 계산하면 대장간·몬스터·상자 무기 일부의 s 가 올라간다(구간 최고가 보스 전설이라).')
w('- 새 영웅 무기 63개의 무기 스킬은 방향별 조합형 틀 12종을 층 연출(proj_*·*_burst·*_slash)로 바꿔 쓴 것이다. 이름은 모두 다르다. 보스·대장간 상위 무기처럼 무기마다 완전히 다른 조합을 원하면 따로 다듬는다.')
w('- 특별 시련 성공률 0.65 는 추정이다. 테스트 서버에서 층마다 10번씩 재 보고 chance·조건 수치를 맞춘다.')
w('- 겉모습별 방어구 장단점(판금·가죽·천)은 다른 설계 작업이다. 새 6세트는 look 만 맞춰 두었다.')

open(D + 'gear_spec.md', 'w').write(out.getvalue())
print('md', len(out.getvalue()))
