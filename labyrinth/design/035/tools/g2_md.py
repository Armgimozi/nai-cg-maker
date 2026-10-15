# -*- coding: utf-8 -*-
"""gear_spec.md 만들기 (g2_spec.py 다음에). python3 tools/g2_md.py"""
import collections
import json
import os

import g2_core as G
import g2_req as Q
import g2_loot as L

ST = json.load(open(os.path.join(G.HERE, 'g2_state.json'), encoding='utf-8'))
SP = json.load(open(os.path.join(G.D2, 'gear_spec.json'), encoding='utf-8'))
W, WR, AR, A, SRC = ST['W'], ST['WR'], ST['AR'], ST['A'], ST['src']
BANDS = {int(k): v for k, v in ST['bands'].items()}
RATES = {int(k): v for k, v in ST['rates'].items()}
FORGE = {int(k): v for k, v in ST['forge'].items()}
CHK = ST['check']
OUT = []


def p(s=''):
    OUT.append(s)


def req_txt(r):
    if not r:
        return '없음'
    return ' · '.join(f'{G.STAT_KO[k]} {v}' for k, v in sorted(r.items(), key=lambda kv: -kv[1]))


def req_short(r):
    if not r:
        return '-'
    return ' '.join(f'{k}{v}' for k, v in sorted(r.items(), key=lambda kv: -kv[1]))


def kinds_txt(ks):
    return ' + '.join(G.SK_KO[k] for k in ks)


def wname(wid):
    return f"{W[wid]['name']} `{wid}`"


def utext(wid):
    w = W[wid]
    tt = w.get('tooltip') or []
    nm = w['unique'].get('name', '')
    body = tt[1].strip() if len(tt) > 1 else ''
    return f'{nm}: {body}' if body else nm


def pct(x):
    return f'{x * 100:+.0f}%'


SK_ORDER = ['B', 'F', 'M', 'T', 'S', 'V', 'E', 'P']
DIR_KO = {k: v['name'] for k, v in G.DIRS.items()}


def head():
    s = SP['summary']
    p('# 미궁 라비린스 — 장비 늘리기 · 획득처 다시 짜기 (TASK C 2판, 0.3.5 안)')
    p()
    p('주인 결정을 모두 따른다. 이 판에서 새로 반영한 것은 아래 셋이다.')
    p()
    p('1. **무기 종류가 없다.** 분류 이름(대검·한손검·활·지팡이·홀·단검)·직업 추천 무기·종류별 요구 능력치가 사라진다. 무기마다 모양·공격 방식·간격·요구 능력치·고유 효과가 따로 있다.')
    p('2. **요구 능력치는 "그리고"만.** `requires_any`(… 중 하나)를 없앤다. 요구는 능력치 2~3개에 나눈다(60/40 또는 50/30/20). 무기·방어구 **전부(기존 226 + 새 130)** 를 다시 정했다.')
    p('3. **장비에 층 이름표가 없다.** 툴팁·도감·대장간에 "N층"이 안 나온다. 보스가 아닌 장비는 레벨 창이 겹치는 이웃 층 셋에서 나온다. 보스 고유 장비만 그 보스에게서 나온다. 영웅 이상 무기는 **획득처 종류 하나**.')
    p()
    p('공격 간격·한 방 피해·스탯 역할·스킬 위력은 전투 명세(`combat_spec.json`·`combat_spec.md`)를 그대로 쓴다. 고유 효과 이름·수치는 효과 명세(`unique_spec.json`)와 방향 12개(`directions.json`)를 그대로 쓴다.')
    p()
    p('- 데이터: `gear_spec.json` — 새 무기 106개(items.yml 형식) · 기존 무기 131개 바뀜 · 기존 방어구·방패 95개 바뀜 · 새 방어구 6세트 · 루팅 표 · 특별 시련 · 새 실루엣 15종 · 테스트')
    p('- 스크립트(`tools/`): `g2_core.py`(읽기) · `g2_req.py`(요구 능력치 규칙·틀) · `g2_assign.py`(무기 요구 고르기) · `g2_check.py`(직업 검사) · `g2_loot.py`(단계 풀·확률·회차) · `g2_spec.py`(JSON) · `g2_md.py`(이 문서). `python3 tools/g2_spec.py && python3 tools/g2_md.py` 로 다시 만든다.')
    p('- 옛 판(층 이름표·`requires_any`·`attack.speed` 를 쓰던 판)은 `tools/_bak/gear_spec_c1.*` 에 있다. 새 무기 106개의 이름·모양·효과·이야기·모델은 옛 판에서 그대로 가져왔다(전투 명세가 그 106개로 숫자를 정했기 때문).')
    p()
    p('## 0. 한눈에')
    p()
    p('| 항목 | 지금 (0.3.4) | 바꾼 뒤 |')
    p('|---|---|---|')
    p(f"| 무기 | 131 (종류 6 × 구간 10, 칸마다 1~4개) | **{s['weapons_after']}** (+{s['weapons_new']}, 종류 없음) |")
    p(f"| 5레벨 띠마다 무기 (신화 제외) | 9~21 | **{min(b['non_mythic'] for b in BANDS.values())}~{max(b['non_mythic'] for b in BANDS.values())}** |")
    p(f"| 띠마다 획득처 종류 | 2~3 | **{min(b['n_source_kinds'] for b in BANDS.values())}~{max(b['n_source_kinds'] for b in BANDS.values())}** |")
    p('| 방어구 세트 | 20 (+단품 투구 5 · 방패 10) | 26 (+6: 판금 2 · 가죽 2 · 천 2, 24부위) |')
    p('| 무기 모양 | 30 | 45 (+15 새 실루엣) |')
    p('| 요구 능력치 | 무기 종류·방어구 겉모습으로 한 능력치 R = ceil(2.5(L−1)), 천·모든 직업용은 "또는" | 장비마다 2~3 능력치 "그리고", 합 T = ceil(2.75(L−1)) |')
    p('| 장비의 층 | items.yml `floor` — 그 층 표에서만 나오고 툴팁에 "지하 N층" | `tier`(숨은 단계) — 이웃 층 셋이 나눠 주고, 화면에 층 없음 |')
    p('| 영웅 이상 무기 집 | 보스 32 · 대장간 36 · 몬스터·상자 6 | 보스 32 · 대장간 36 · 몬스터·상자 21 · 금고·미믹 16 · 특별 시련 15 · 시련방 11 · 정예 10 (모두 종류 하나) |')
    p('| 6·8·9·10층 몹·상자 무기 | 없음 (r1 에서 대장간만) | 다시 있음 (단계 풀 + 새 몬스터·상자·시련·금고·특별 시련·정예 무기) |')
    p(f"| 직업 검사 (띠마다 알맞은 무기 3개 미만인 직업·띠) | - | **{len(s['short_class_bands'])}건** |")
    p()
    p('핵심 규칙 네 줄:')
    p('1. 같은 띠의 시련방·특별 시련·금고·미믹·정예·새 몬스터·상자 무기는 **대장간 무기와 기본 성능 ±5% 안**이다. 다른 것은 고유 효과의 방향과 세기다.')
    p('2. 보스 전설 무기는 기본 성능이 5~30% 높지만 고유 효과가 약하다(강도 0.8). 상자·시련 무기는 효과가 세다(강도 2.2~2.8). 자기 상황에서는 상자 무기가 이긴다.')
    p('3. 대장간은 1회 안팎이면 만드는 **확정 바닥값**(무기 레시피 골드 ×1.5 로 올림). 몬스터·상자 2.5~3.5회, 시련방·금고·정예 5회, 특별 시련 3~7회, 보스 고유 1.4~9회. 가운데값으로 보면 대장간 말고는 2회 미만인 것이 없고, 10회를 넘는 것도 없다.')
    p('4. 요구 능력치는 그 무기의 정체성을 따른다. 생김새가 비슷해도 요구가 다르다(예: 처형자 도끼 셋 = 힘+민첩 · 민첩+힘+체력 · 힘+행운). 어느 직업도 한 띠를 통째로 잃지 않는다.')
    p()


def sec1():
    p('## 1. 종류가 없어진 뒤 장비가 무엇으로 갈리나')
    p()
    p('### 1.1 없어지는 것 (장비 쪽)')
    p()
    p('| 없어짐 | 대신 |')
    p('|---|---|')
    p('| items.yml `weapon_type` | `attack: {style, interval, kind}` — 전투 명세 §2·§5 그대로. 플레이어에게 분류 이름으로 보이지 않는다 |')
    p('| 툴팁 머리 "영웅 대검 · 지하 4층" | "영웅 무기" (층 없음) + "⚔ 공격력 23 (21–24) · 물리" + "공격 속도 초당 1.5회" |')
    p('| 요구 능력치 "지능 또는 정신 30" | "요구 지능 18 · 정신 12" (요구치 큰 순, 모두 채워야 함) |')
    p('| 장비 `classes` (드롭 직업 편향·"내 직업 장비만") | 삭제. 드롭 편향은 요구 능력치로 (`own_build_bias`, §4.1). 도감·대장간 필터는 "지금 낄 수 있는 것만" |')
    p('| 장비 `floor` | `tier` (숨은 단계, 표시 안 함). 보스 장비는 tier 로 그 층 보스를 찾는다 |')
    p('| 획득처 "보스 테오라(9층)" · "지하 3층 몬스터·상자" · "정예 …(9층)" | "보스 테오라" · "몬스터·상자" · "정예 대시계 집행관" · "시련방" · "특별 시련" · "금고·미믹" · "대장간" · "상인 핀" |')
    p('| 도감 "지하 N층 무기 (몬스터·상자 공용)" 묶음 | "몬스터·상자" 한 줄 |')
    p()
    p('몬스터 도감·보스 도감의 "지하 N층"은 그대로 둔다(장비가 아니다).')
    p()
    p('### 1.2 공격 방식과 피해 종류')
    p()
    p('- 방식(style)은 모양에서 나온다: 활 모양 7종 → 원거리(당겨 쏘기), 시전 모양 14종 → 시전(휘두르기, 마법), 그 밖 → 근접. 전투 명세 §2.')
    p('- 피해 종류(kind): 근접·원거리 = 물리(STR), 시전 = 마법(INT). 전투 명세 §6.4·§5.7 이 허용한 대로 **지능을 요구하는 근접·활 8개를 마법으로** 둔다 — "지능 활", "지능 근접":')
    p()
    p('| 무기 | 띠 | 모양 | 방식 | 요구 | 이유 |')
    p('|---|---|---|---|---|---|')
    for wid in Q.KIND_MAGIC:
        w = W[wid]
        p(f"| {wname(wid)} | {G.blabel(w['band'])} | `{w['shape']}` | {G.STYLE_KO[w['style']]} → 마법 | {req_txt(WR[wid]['requires'])} | {WR[wid]['why']} |")
    p()
    p('간격·한 방 피해는 종류와 상관없이 같다(전투 명세 c(L) 가 물리·마법 같음). 혼합(hybrid) 공격은 쓰지 않는다 — 전투 명세 검사기가 `kind ∈ physical|magic` 이다.')
    p()
    p('### 1.3 전투 명세에서 그대로 가져오는 것 (이 명세는 바꾸지 않는다)')
    p()
    p('- 공격 게이지 없음 · 무기마다 `attack.interval` · 이른 클릭 0.35초 기억 · 활은 당김 (전투 명세 §2).')
    p('- 툴팁 "⚔ 공격력 = 한 방 피해" + "공격 속도 초당 N회(민첩 전)" (§7.1).')
    p('- STR = 물리, INT = 마법 공격력 1%/점, DEX = 공속 0.5%·치명 0.25%p·회피 0.1%p (§3).')
    p('- 직업 스킬·무기 스킬은 **스킬 위력** SP = (한 방 가운데값 ÷ 간격) ÷ K(방식, 간격) × (시전 1.05) × (1 + 0.5 × 공속) 에 곱한다. 같은 단계면 무거운 무기와 가벼운 무기의 SP 가 같다(§3.3·§5.6). 직업마다 `skill_scale`(§6.3).')
    p('- 그래서 이 명세의 "같은 단계" 비교값도 SP 와 같은 식이다(§5).')
    p()


def sec2():
    p('## 2. 무기 수 — 전과 후')
    p()
    p('### 2.1 지금 (0.3.4, 옛 종류 × 5레벨 띠)')
    p()
    TYPES = [('greatsword', '대검'), ('sword_shield', '한손검·방패'), ('bow', '활'), ('dagger', '단검'), ('staff', '지팡이'), ('scepter', '홀')]
    c = collections.Counter()
    for k, v in G.ITEMS.items():
        if v.get('type') == 'weapon':
            c[(v['weapon_type'], G.band(v['level_req']))] += 1
    p('| 종류 | ' + ' | '.join(G.blabel(b) for b in G.BANDS) + ' | 합 |')
    p('|---|' + '---|' * 11)
    for t, ko in TYPES:
        p(f'| {ko} | ' + ' | '.join(str(c[(t, b)]) for b in G.BANDS) + f' | {sum(c[(t, b)] for b in G.BANDS)} |')
    p('| **합** | ' + ' | '.join(f'**{sum(c[(t, b)] for t, _ in TYPES)}**' for b in G.BANDS) + ' | **131** |')
    p()
    ones = sum(1 for t, _ in TYPES for b in G.BANDS if c[(t, b)] == 1)
    p(f'칸마다 1~4개, 1개뿐인 칸이 {ones}개다. 6~10·26~30·36~40·41~45 띠는 9개뿐이고, 26~30·36~40·41~45 는 대장간·보스 두 곳에서만 나온다.')
    p()
    p('### 2.2 바꾼 뒤 (띠 전체, 종류 없음)')
    p()
    p('| 띠 | 무기 (신화 제외) | 새 | 근접 | 원거리 | 시전 | 마법 피해 | 요구 STR | DEX | INT | WIS | VIT | LUK | 방향 수 | 획득처 종류 |')
    p('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for b in G.BANDS:
        x = BANDS[b]
        st = x['req_stats']
        extra = f" (+신화 {x['total'] - x['non_mythic']})" if x['total'] > x['non_mythic'] else ''
        p(f"| {G.blabel(b)} | {x['non_mythic']}{extra} | {x['new']} | {x['styles'].get('melee', 0)} | {x['styles'].get('ranged', 0)} | {x['styles'].get('caster', 0)} | "
          f"{x['kinds'].get('magic', 0)} | {st.get('STR', 0)} | {st.get('DEX', 0)} | {st.get('INT', 0)} | {st.get('WIS', 0)} | {st.get('VIT', 0)} | {st.get('LUK', 0)} | "
          f"{x['directions']}/12 | {x['n_source_kinds']} |")
    p()
    p('요구 능력치 칸 = 그 능력치를 요구에 넣은 무기 수(한 무기가 2~3칸에 센다). 1–5 띠의 Lv1 무기 6개는 요구가 없어 빠진다.')
    p()
    p('### 2.3 왜 237개인가')
    p()
    p('- 주인 목표: 띠마다 무기 **10~14개 이상**, 근접 ≥5 · 원거리 ≥3 · 시전 ≥3, 요구 능력치·방향·획득처 종류가 고루. 전체 목표 220~240, 늘림 상한 +110.')
    p('- 이 판의 계산 기준은 **직업마다 "알맞게 낄 수 있는 무기"** 다(§3.4). 직업 6개가 띠마다 각자 3~5개의 알맞은 선택지를 가지려면, 같은 무기를 여러 직업이 나눠도 띠마다 20개 이상이 필요하다. 요구가 2~3 능력치라 한 무기를 2~4직업이 나눠 쓴다.')
    p('- 여기에 보스 고유 2~3개, 상인·몬스터·상자 하위 무기를 더하면 띠마다 22~23개. 10띠 × 23 = 230. 1–5 띠는 1층·2층 Lv5 무기가 겹쳐 25개, 46–50 띠는 신화 6개(어려움 이상)를 빼고 22개다.')
    p('- 그래서 131 + 106 = **237** (+106, 상한 +110 안). 전투 명세가 이미 이 237개로 간격·한 방 피해를 정했다 — 숫자를 다시 만들지 않으려고 수를 바꾸지 않았다.')
    p('- 더 늘리지 않는 이유: 같은 띠에서 같은 방향 + 같은 요구 짝 + 같은 획득처가 겹치기 시작하면 선택지가 아니라 중복이다. 지금 그런 쌍은 0개다.')
    p()


def sec3():
    p('## 3. 요구 능력치 — "그리고"만, 2~3 능력치에 나눔')
    p()
    p('### 3.1 식')
    p()
    p('```')
    p('예산   T(L) = ceil(2.75 × (L − 1))      L ≤ 2 이면 요구 없음          (지금 한 능력치 R = ceil(2.5 × (L − 1)) 의 1.1배)')
    p('두 개   주 = round(0.6 T) · 둘째 = T − 주                            (60/40)')
    p('세 개   주 = round(0.5 T) · 둘째 = round(0.3 T) · 셋째 = 나머지       (50/30/20, L ≥ 12 부터)')
    p('판정   내 능력치 = 직업 기본 + 분배 + 장착 칭호 (장비 스탯 제외) — 모든 요구를 채워야 낀다 (지금과 같음)')
    p('```')
    p()
    p('| 숨은 Lv | 지금 R (하나) | 새 합 T | 두 개 60/40 | 세 개 50/30/20 |')
    p('|---|---|---|---|---|')
    for Lv in (3, 5, 8, 14, 19, 24, 27, 34, 38, 41, 44, 46, 48):
        R = Q.math.ceil(2.5 * (Lv - 1)) if Lv > 1 else 0
        T = Q.budget(Lv)
        two = Q.split(Lv, ('A', 'B'))
        thr = Q.split(Lv, ('A', 'B', 'C'))
        p(f"| {Lv} | {R if R > 2 else '-'} | {T or '-'} | {two.get('A', '-')} / {two.get('B', '-')} | {'-' if len(thr) < 3 else ' / '.join(str(thr[k]) for k in 'ABC')} |")
    p()
    p('- 한 벌(무기 + 방어구 + 방패)의 요구는 **능력치마다 가장 큰 값**이다(합이 아니다). 지금은 무기 STR 108 + 방어구 VIT 108 처럼 두 능력치에 나뉘어 포인트가 거의 다 찼다(수호기사 Lv44: 220 중 204). 새 규칙에서 태엽 거신 판금(체력 71 · 힘 48) + 태엽 성벽 방패(같음) + 방벽 무기 태엽 넓은검(체력 66 · 힘 44)은 체력 71 · 힘 48 로 겹쳐 107 포인트다. **같은 방향끼리 맞추면 싸고, 섞으면 비싸다** — 이것이 빌드 선택이다.')
    p('- 세 번째 능력치 20% 는 "조금 섞인 맛"이다. 지능 20% 가 붙은 판금(색인 방벽)은 마검사에게 열리고, 힘·체력 빌드에게는 몇 포인트의 세금이다.')
    p()
    p('### 3.2 무기 — 정체성 틀')
    p()
    p('무기마다 (고유 효과 방향, 피해 종류)로 후보 틀을 만든다. 방향의 `pairs_stats` 와 피해 능력치(물리 STR · 마법 INT)를 섞었다. 앞 틀이 정체성에 가깝다.')
    p()
    p('| 방향 | 물리 무기 후보 (앞이 먼저) | 마법 무기 후보 |')
    p('|---|---|---|')
    for d in G.DIRS:
        ph = ' · '.join('+'.join(o) for o in Q.TPL[(d, 'physical')])
        mg = ' · '.join('+'.join(o) for o in Q.TPL[(d, 'magic')])
        p(f'| {DIR_KO[d]} `{d}` | {ph} | {mg} |')
    p()
    p('고르는 순서 (`g2_assign.py`):')
    p('1. 손으로 정한 무기 50개(`WEAPON_FIX` — 이름·이야기가 능력치를 말하는 것, "민첩 처형 도끼"·"지능 활" 같은 본보기)는 그대로.')
    p('2. 나머지는 앞 틀부터 보되, 같은 띠 안에서 같은 짝(예: 민첩+힘)·같은 주 능력치가 겹치면 다음 틀로.')
    p('3. 같은 띠·같은 모양 두 무기는 다른 틀.')
    p('4. 고치기: 띠마다 직업별 "알맞은 무기"(§3.4)가 목표(수호·광전·사냥·그림자 5, 비전·사제 4)보다 적으면, 정체성을 덜 잃는 무기부터 다른 후보 틀로 바꾼다. 다른 직업이 목표 밑으로 떨어지는 바꿈은 하지 않는다.')
    p()
    nos = [k for k, w in W.items() if w['kind'] == 'physical' and WR[k]['order'] and 'STR' not in WR[k]['order']]
    noi = [k for k, w in W.items() if w['kind'] == 'magic' and WR[k]['order'] and 'INT' not in WR[k]['order']]
    p(f'- 피해 능력치를 요구하지 않는 무기: 물리 {len(nos)}개(민첩·행운 치명/기습, 민첩·지능 독 — 정체성), 마법 {len(noi)}개(정신·체력 지원). 끼는 사람이 힘·지능을 따로 찍는다. 띠 3~10 에서는 띠마다 1~3개, 요구가 작은 1·2 띠에는 5·8개(민첩·행운 두 능력치 무기가 많아서).')
    p(f"- 손으로 정하지 않은 무기 중 직업 몫을 채우려 바꾼 것: {sum(1 for r in WR.values() if '몫을 채우려' in (r.get('why') or ''))}개. 고치기로도 못 채운 칸: {', '.join(ST['assign_log']) or '없음'} (3개는 있다).")
    p()
    p('### 3.3 방어구 · 방패 — 세트마다')
    p()
    p('겉모습의 정체성은 그대로 둔다: 판금 = 체력·힘, 가죽 = 민첩(+힘·행운·체력), 천 = 지능·정신(+체력). 세트마다 짝이 조금씩 달라 같은 겉모습 안에서도 빌드가 갈린다. 세트 네 부위는 같은 요구.')
    p()
    p('| 세트·단품 | 겉모습 | 단계 | Lv | 지금 | 새 요구 | 알맞게 입는 직업 | 이유 |')
    p('|---|---|---|---|---|---|---|---|')
    seen = set()
    rows = []
    for aid, a in A.items():
        key = a['set'] or aid
        if key in seen:
            continue
        seen.add(key)
        old = G.ITEMS.get(aid, {})
        oldr = old.get('requires') or ({'또는': old['requires_any']} if old.get('requires_any') else {})
        if a['new']:
            oldr_t = '(새)'
        elif old.get('requires_any'):
            vals = list(old['requires_any'].values())
            oldr_t = '·'.join(G.STAT_KO[k] for k in old['requires_any']) + f' 중 하나 {vals[0]}'
        else:
            oldr_t = req_txt(old.get('requires') or {})
        cl = CHK['per_set'].get(key, [])
        look = {'heavy': '판금', 'light': '가죽', 'cloth': '천', 'shield': '방패', 'any': '모두'}[a['look']]
        rows.append((a['L'], f"{a['name'] if not a['set'] else G.SETS.get(a['set'], {}).get('name', a['set']) if a['set'] in G.SETS else SP['armor_sets'].get(a['set'], {}).get('name', a['set'])} `{key}`",
                     look, a['floor_old'], a['L'], oldr_t, req_txt(AR[aid]['requires']), ' '.join(G.CLS_KO[c] for c in cl) if cl else '-', AR[aid]['why']))
    for r in sorted(rows, key=lambda x: (x[0], x[1])):
        p('| ' + ' | '.join(str(v) for v in r[1:]) + ' |')
    p()
    p('"알맞게 입는 직업" = 그 세트 레벨+2 에서 직업 기본 분배(전투 명세 §6.1)로 세금 ≤ 15%. 방패는 수호기사 검사(§3.4)에 들어간다.')
    p()


def sec3b():
    p('### 3.4 직업 검사 — 띠마다 알맞은 한 벌이 있는가')
    p()
    p('`tools/g2_check.py`. 가장 나쁜 경우로 잰다: 칭호 없음(칭호 12개는 서버에 한 명씩), 스탯 초기화 뒤, 포인트 = 시작 5 + 레벨당 5.')
    p()
    p('```')
    p('한 벌     = 그 띠 무기 1 + 방어구 세트 1 (그 레벨까지 나온 것, 15레벨 안, 겉모습 무엇이든) (+ 수호기사는 방패 1)')
    p('필요      = 능력치마다 max(요구) − 직업 기본 → 합 ≤ 받은 포인트 이면 낄 수 있다')
    p('세금      = 직업 "알맞은 분배"(combat_spec sensible_spread new: 수호 VIT3:STR2 · 광전 STR3:VIT2 · 사냥 DEX2:STR1.3:VIT1.7 ·')
    p('            비전 INT3:VIT2 · 사제 WIS2.5:INT0.55:VIT1.95 · 그림자 DEX2:STR1.4:VIT1.6) 밖으로 더 찍어야 하는 포인트 ÷ 받은 포인트')
    p('알맞음    = 낄 수 있고 세금 ≤ 15%, 그리고 무기 피해 종류가 직업과 맞음 (비전·사제 = 마법, 나머지 = 물리)')
    p('레벨      = 띠 끝 레벨 (5, 10, … 50)')
    p('```')
    p()
    p('| 직업 | ' + ' | '.join(G.blabel(b) for b in G.BANDS) + ' |')
    p('|---|' + '---|' * 10)
    for c in G.CLS:
        cells = []
        for b in G.BANDS:
            v = CHK['by_class_band'][f'{c}|{b}']
            cells.append(f"**{v['good_kind']}** / {v['wearable']}")
        p(f'| {G.CLS_KO[c]} | ' + ' | '.join(cells) + ' |')
    p()
    p('칸 = **알맞은 무기 수** / 그 직업이 그 띠에서 포인트 안에 낄 수 있는 무기 수(세금 무관). 모든 칸이 3 이상 — 어느 직업도 한 띠를 통째로 잃지 않는다. 낄 수 있는 무기는 띠마다 22~25개 중 대부분이다(세금을 내면 다른 빌드도 된다).')
    p()
    p('직업 겉모습(수호·광전 = 판금, 사냥·그림자 = 가죽, 비전·사제 = 천)으로만 입어도 알맞은 무기 수:')
    p()
    p('| 직업 | ' + ' | '.join(G.blabel(b) for b in G.BANDS) + ' |')
    p('|---|' + '---|' * 10)
    for c in G.CLS:
        p(f'| {G.CLS_KO[c]} | ' + ' | '.join(str(CHK['by_class_band'][f'{c}|{b}']['good_natural_look']) for b in G.BANDS) + ' |')
    p()
    p('1–5 띠는 0 이다: 그 띠 방어구가 수련생·길잡이(모든 직업용, 가죽 모양) 뿐이라 모든 직업이 공용 세트를 입는다(지금과 같음). 판금·천은 2단계(Lv8)부터.')
    p()
    p('보기 (직업 겉모습 한 벌, 띠 끝 레벨, 그 띠에서 세금이 가장 적은 무기):')
    p()
    p('| 직업 | 띠 | 무기 | 방어구 | 방패 | 합친 요구 | 필요 포인트 / 받은 | 세금 |')
    p('|---|---|---|---|---|---|---|---|')
    SETNAME = {sid: v['name'] for sid, v in G.SETS.items() if isinstance(v, dict) and v.get('name')}
    SETNAME.update({sid: v['name'] for sid, v in SP['armor_sets'].items()})
    for c in G.CLS:
        for b in (2, 5, 9):
            v = CHK['by_class_band'][f'{c}|{b}']
            ex = v.get('natural')
            if not ex:
                continue
            wid = ex['weapon']
            sh = A[ex['shield']]['name'] if ex.get('shield') else '-'
            p(f"| {G.CLS_KO[c]} | {G.blabel(b)} | {W[wid]['name']} | {SETNAME.get(ex['set'], ex['set'])} | {sh} | {req_txt(ex['req'])} | {ex['need']} / {G.points_at(5 * b)} | {ex['tax'] * 100:.0f}% |")
    p()
    oth = CHK['per_weapon_arch']
    if oth:
        p('직업 기본 분배로는 세금이 15% 를 넘지만 **다른 빌드로는 알맞은 무기** (요구가 "쓸모없는 무기"를 만들지 않는지):')
        p()
        p('| 무기 | 요구 | 맞는 빌드 |')
        p('|---|---|---|')
        for wid, arch in oth.items():
            p(f"| {wname(wid)} | {req_txt(WR[wid]['requires'])} | {' · '.join(Q.ARCH_KO[a] for a in arch)} |")
        p()
        p('다른 빌드 5종(`g2_req.ARCH`): 치명(행운) DEX1.6:LUK1.2:STR1:VIT1.2 · 마검사 STR1.4:INT1.4:VIT1.6:DEX0.4 · 전투 사제 WIS1.8:STR1.2:VIT1.8 · 민첩 시전 INT2.2:DEX1.2:VIT1.6 · 방벽 시전 VIT2.2:WIS1.4:INT1.4. 어떤 빌드로도 안 맞는 무기: 0개.')
        p()
    p('전투 명세와의 관계: 전투 명세 §6 은 0.3.4 요구치(한 능력치)로 직업 ±10% 를 맞췄다. 새 요구는 같은 방향 한 벌일 때 **더 싸다**(판금+방벽 108 vs 216). 알맞은 분배 안에서 요구가 묶이지 않으므로 그 결과가 그대로 선다. 세금을 내는 빌드는 그만큼 약해진다 — 전투 명세 §6.4 표의 세금(1점당 피해 1%)과 같은 크기다.')
    p()


def sec3c():
    p('### 3.5 기존 무기 131개 — 요구 능력치 바뀜')
    p()
    p('모두 바뀐다(한 능력치 → 2~3 능력치, 합 2.75 기준). 전투 명세의 간격·한 방 피해·무기 스킬 계수는 `gear_spec.json existing_changes` 에 함께 적었다.')
    p()
    p('| 무기 | 띠 | 모양 | 피해 | 지금 | 새 요구 | 이유 |')
    p('|---|---|---|---|---|---|---|')
    for wid, w in sorted(W.items(), key=lambda kv: (kv[1]['L'], kv[0])):
        if w['new']:
            continue
        old = G.ITEMS[wid].get('requires') or {}
        p(f"| {wname(wid)} | {G.blabel(w['band'])} | `{w['shape']}` | {G.KIND_KO[w['kind']]} | {req_short(old)} | {req_short(WR[wid]['requires'])} | {WR[wid]['why']} |")
    p()
    p('### 3.6 코드 (요구 능력치)')
    p()
    p('| 파일 · 메서드 | 할 일 |')
    p('|---|---|')
    p('| content/StatRequirement | `any` 필드·`anyMet`·"또는" 문구 삭제. `of(Map<Stat,Integer>)` 하나. `text()` = "요구 민첩 24 · 힘 16" (요구치 큰 순) |')
    p('| content/ContentParser.item (190행) | `requires_any` 를 읽지 않는다. 있으면 problem("requires_any 는 0.3.5 에서 없어짐 — requires 로") |')
    p('| items/EquipRules · ItemTooltip.requirementLine | any 분기 삭제. 줄은 능력치마다 충족/미달 색 (지금 all 과 같음) |')
    p('| core/ContentValidator.requirements (206행) | 시작 무기 = classes.yml `starter_weapon` (WeaponTypes 삭제). 장비 요구 합·나눔 규칙 경고 (§12 GearRequirementsDataTest 와 같은 규칙) |')
    p('| items/loot/LootRoller (one_of 고르기) | `own_class_bias` → `own_build_bias`: 후보 중 "요구치 가장 큰 능력치 ∈ 줍는 사람 능력치(기본+분배+칭호) 상위 2개" 인 것만 65% (없으면 전체). items.yml `classes` 를 안 본다 |')
    p('| ui/menus/StatsMenu | 초기화 안내에 "장비 요구는 이제 2~3 능력치" 한 줄 (0.3.5 무료 초기화와 같은 안내, 전투 명세 §10.3) |')
    p()


def sec4():
    p('## 4. 층 이름표 없애기 — 단계 풀')
    p()
    p('### 4.1 규칙')
    p()
    p('```')
    p('단계(tier) N      = 그 장비를 만든 레벨 구간 = N층 레벨 구간 Lv 5N−5 ~ 5N        (지금 items.yml floor 값을 이름만 바꿈)')
    p('레벨 창           = 단계 구간 앞뒤 5레벨 = Lv 5N−10 ~ 5N+5')
    p('주는 층           = 레벨 구간이 창과 겹치는 층 = N−1 · N · N+1')
    p('층 f 의 몫         = 단계 f−1 : f : f+1 = 2 : 7 : 1   (특별 시련만 1 : 8 : 1, 없는 단계는 빼고 다시 나눔)')
    p('보스 고유 장비     = 그 보스 표에만 (단계 = 보스 층, 이웃 층 없음)')
    p('대장간            = 레시피 그대로 (재료가 층 재료라 사실상 그 층에서 모은다)')
    p('```')
    p()
    p('- 그래서 같은 층을 돌아도 **조금 낮은 장비·조금 높은 장비가 섞여** 나온다. 높은 단계 장비는 요구 능력치가 높아 바로 못 끼는 경우가 많다(미리 얻는 맛).')
    p('- 상자·시련방·특별 시련·금고·미믹 전용 장비는 **그 획득처 종류에만** 있지만 층 셋에서 나온다. 영웅 이상 "획득처 하나" 규칙은 "획득처 종류 하나"가 된다.')
    p('- 단계와 5레벨 띠는 거의 같다. 다른 것은 경계 레벨뿐이다(예: Lv24 서리 송곳니 가죽은 단계 6, 띠 21–25). 다양성 표(§2·§5)는 띠로, 루팅 표는 단계로 센다.')
    p()
    p('### 4.2 새 루팅 항목 PICK (가장 작은 코드)')
    p()
    p('```yaml')
    p('# loot.yml — 하위 표를 무게로 하나 골라 굴린다. guaranteed 에도 둘 수 있다.')
    p('- {pick: [{table: band_t04_drop, weight: 2}, {table: band_t05_drop, weight: 7}, {table: band_t06_drop, weight: 1}], chance: 1.0}')
    p('```')
    p()
    p('지금 항목은 저마다 따로 판정한다. 그래서 "셋 중 하나"를 표 단위로 고를 방법이 없다(one_of 는 아이템만). PICK 하나를 더한다.')
    p()
    p('| 파일 | 할 일 |')
    p('|---|---|')
    p('| content/LootTable | `Kind.PICK` + `record Pick(String table, int weight)` · `List<Pick> pick()` |')
    p('| content/ContentParser (loot) | `pick:` 목록 읽기 (table 필수, weight 기본 1) |')
    p('| items/loot/LootRoller | PICK: chance(난이도·파티·행운 배율, 장비 항목 아님 → rarity_weight 없음) 통과 → 무게 합 안에서 하나 → 그 표를 굴림(깊이 제한 그대로) |')
    p('| core/ContentValidator | 하위 표 존재·무게 > 0·순환 금지 (table: 항목과 같은 검사) |')
    p('| LootHomesTest·GearRequirementsDataTest.expand · ItemTooltip.items · CodexMenu.items | 펼칠 때 PICK 하위 표 전부를 따라간다 |')
    p()
    p('### 4.3 표 구조')
    p()
    p('| 표 | 수 | 내용 | 누가 굴리나 |')
    p('|---|---|---|---|')
    pools = ST['pools']
    n = collections.Counter()
    for tid in SP['loot_changes']:
        if tid.startswith('band_'):
            n[tid.split('_')[-1]] += 1
    p(f"| `band_tNN_drop` | {n['drop']} | 그 단계 몬스터·상자 무기 one_of | `mix_fNN_drop` (PICK) |")
    p(f"| `mix_fNN_drop` | 10 | PICK 2:7:1 | 그 층 일반 몹 6종 · 보물방 · 미로 나무/철/금 상자 (지금 `gear_fNN_common` 자리, 확률은 §7.2) |")
    p(f"| `band_tNN_trial` | {n['trial']} | 시련방 무기 one_of (+ 시련 방어구 50%) | `gimmick_floor_N` 의 PICK 항목 (몬스터·상자 무기는 뺀다) |")
    p(f"| `band_tNN_special` | {n['special']} | 특별 시련 무기 확정 1 + 50% 로 하나 더 (+ 방어구 50%) | `special_trial_fNN` (새, 코드가 굴림 — §6) |")
    p(f"| `band_tNN_hoard` | {n['hoard']} | 금고·미믹 무기 (+ 방어구) | `hoard_fNN` (새, 금고 금 상자·길들인 미믹 상자를 열 때 한 번 더) |")
    p(f"| `band_tNN_elite` | {n['elite']} | 그 단계 정예 방어구 세트 · 방패 · 장신구 · 정예 무기 | 그 층 정예 표의 PICK 항목 (지금 층 장비 항목 자리) |")
    p('| `gear_fNN_common` | -6 | 삭제 | - |')
    p()
    p(f"바뀌는 표 합계: {len(SP['loot_changes'])}개 (새 {sum(1 for v in SP['loot_changes'].values() if v['op'] == 'new')} · 다시 씀 {sum(1 for v in SP['loot_changes'].values() if v['op'] == 'replace_entries')} · 삭제 {sum(1 for v in SP['loot_changes'].values() if v['op'] == 'delete')}). 모두 `gear_spec.json loot_changes` 에 전체 항목으로 있다.")
    p()
    p('코드가 새로 굴리는 표 두 종류:')
    p('- `special_trial_fNN` — GimmickRoom.succeed() 가 특별 시련 조건까지 지켰을 때 (§6.6).')
    p('- `hoard_fNN` — dungeon/treasure/Treasures.open() 에서 연 상자가 금고 안 상자(`plan.vault().contains(x, z)`)이거나 길들인 미믹(`tamed[i]`)이면 층별 표를 굴린 뒤 `fs.loot("hoard_f%02d", …)` 한 번 더. 칭호 카운터는 그대로.')
    p()
    p('### 4.4 획득처 종류 행렬')
    p()
    p('띠마다 그 종류에서 나오는 무기 수 (신화 제외, 대장간+보스·몬스터·상자+대장간인 하위 무기는 두 칸에 센다).')
    p()
    p('| 띠 | ' + ' | '.join(G.SK_KO[k] for k in SK_ORDER) + ' | 종류 수 |')
    p('|---|' + '---|' * (len(SK_ORDER) + 1))
    for b in G.BANDS:
        sk = BANDS[b]['source_kinds']
        p(f'| {G.blabel(b)} | ' + ' | '.join(str(sk.get(k, '·')) for k in SK_ORDER) + f" | {BANDS[b]['n_source_kinds']} |")
    p()
    p('영웅 이상 무기는 모두 한 칸뿐이다(테스트: §12 GearRequirementsDataTest.topWeaponsHaveExactlyOneSourceKind).')
    p()
    p('### 4.5 툴팁 · 도감 글')
    p()
    p('| 자리 | 지금 | 바꾼 뒤 |')
    p('|---|---|---|')
    p('| 툴팁 첫 줄 | 영웅 대검 · 지하 4층 · ✦ 아우라 | 영웅 무기 · ✦ 아우라 |')
    p('| 요구 줄 | 요구 지능 또는 정신 58 | 요구 지능 29 · 체력 17 · 민첩 12 |')
    p('| 획득처 (보스) | 획득처: 보스 테오라(9층) · 대장간 | 획득처: 보스 테오라 · 대장간 |')
    p('| 획득처 (공용) | 획득처: 지하 3층 몬스터·상자 | 획득처: 몬스터·상자 |')
    p('| 획득처 (정예) | 획득처: 정예 대시계 집행관(9층) · 대장간 | 획득처: 정예 · 대장간 (정예가 셋이라 이름 대신 종류) |')
    p('| 획득처 (새) | - | 획득처: 시련방 / 특별 시련 / 금고·미믹 / 상인 핀 |')
    p('| 도감 획득처 | 지하 9·10층 무기 (몬스터·상자 공용) · 보물 상자 지하 9·10층 | 몬스터·상자 · 시련방 (층 없이 종류만) |')
    p()
    p('코드: items/ItemTooltip.lines 170행(층 붙이기 삭제) · sourceLine 297행("지하 N층" 삭제) · names() 320·325행(라벨에서 "(N층)" 삭제 — 정예 라벨은 그 장비를 주는 정예가 하나일 때만이므로 단계 풀에서는 거의 "정예") · SOURCES 에 trial "시련방" · special "특별 시련" · hoard "금고·미믹" · shop "상인 핀". ui/menus/CodexMenu 131행 정렬(floor → tier) · 201행 공용 묶음 줄 삭제 · 251행 commonFloor 삭제 · 290행 SOURCE_GROUPS 에 "시련방"·"특별 시련"·"금고·미믹" · 305~400행 장비 획득처에서 "(N층)"·"지하 N층" 삭제(몬스터·보스 도감 쪽은 그대로).')
    p()
    p('### 4.6 데이터 이름 바꿈')
    p()
    p('- items.yml 장비: `floor` → `tier` (값 같음). 파서는 `floor` 도 tier 로 읽고 경고(옮기는 동안). `ItemDef.tier()`; `floor()` 는 재료(층 재료 검사) 에만 남긴다.')
    p('- 보스 장비 → 보스: `content.bossOfFloor(def.tier())` (LootHomesTest.bossGearComesOnlyFromItsOwnFloorBoss 와 같은 짝).')
    p('- items.yml `sources` 값 추가: `trial` · `special` · `hoard` (`shop` 은 있음). 머리 주석의 "장비 하나 = 한 층" 줄을 "장비 = 단계 하나, 레벨 창 ±5, 이웃 층 셋" 으로.')
    p('- loot.yml 머리 주석: "6·8·9·10층은 없음" 줄 삭제, 단계 풀·PICK 설명 추가. settings.own_class_bias → own_build_bias.')
    p()


def sec5():
    p('## 5. 띠마다 "정답이 하나가 아니다" — 증명 표')
    p()
    p('열: 희귀도·숨은 Lv · 방식·피해 · 공격 속도(초당, 민첩 전) · 한 방 피해 · 초당 피해(한 방 가운데값 ÷ 간격) · 스킬 위력(전투 명세 식) · 대장간 기준 대비 · 주 부가 스탯 · 방향 · 요구 · 획득처 · 고유 강도 s · 자기 상황.')
    p()
    p('- **대장간 기준 대비** = 비교값 ÷ 그 띠 대장간 기준 − 1. 비교값 = (한 방 가운데값 ÷ 간격) ÷ K(방식, 간격) = 스킬 위력 ÷ 시전 배율. 한 방 피해는 무기 무게에 따라 3배까지 벌어지지만 비교값은 무게와 상관없다(전투 명세 §5.6).')
    p('- **자기 상황** = 효과 설계자 규칙 P′×(1+2B) ≥ 띠 최고 P′×(1+B최고). P′ = 비교값 × (1 + 부가 스탯 가치 + 0.1 × 무기 스킬 수), B = s × 0.10. 효과가 맞는 상황(무리·빈사·출혈 빌드 등)에서 효과 값이 두 배라고 볼 때 띠 최고 무기를 이기면 ✔.')
    p('- 굵게 = 새 무기. † = 한 방 피해를 전투 명세 값에서 1점 안팎 다시 반올림 (±5% 규칙, §13).')
    p()
    for b in G.BANDS:
        x = BANDS[b]
        fr = x['forge_ref']
        rows = x['rows']
        side = [r for r in rows if r['new'] and r['kinds'][0] in 'MTSVE']
        devmax = max((abs(r['vs_forge']) for r in side), default=0)
        win = sum(1 for r in rows if r['situational'] is True)
        bestn = W[x['best']]['name']
        p(f"### {G.blabel(b)} — 대장간 기준 {fr['ref']:.1f} ({G.RAR_KO[fr['rarity']]} Lv{fr['level']}: {', '.join(W[i]['name'] for i in fr['ids'])})")
        p()
        p(f"새 옆길 무기 {len(side)}개 모두 기준 ±5% 안 (가장 먼 것 {devmax * 100:.1f}%). 띠 최고 P′ = {bestn}. 자기 상황에서 최고를 이기는 무기 {win}개.")
        p()
        p('| 무기 | 희귀도·Lv | 방식·피해 | 초당 | 한 방 | 초당 피해 | 스킬 위력 | 기준 대비 | 주 부가 | 방향 | 요구 | 획득처 | s | 자기 상황 |')
        p('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for r in sorted(rows, key=lambda r: (r['kinds'][0] != 'F', r['kinds'][0] != 'B', SK_ORDER.index(r['kinds'][0]) if r['kinds'][0] in SK_ORDER else 9, r['L'])):
            nm = f"**{r['name']}** `{r['id']}`" if r['new'] else f"{r['name']} `{r['id']}`"
            if r['id'] in ST['per_hit_fix']:
                nm += ' †'
            sit = '최고' if r['situational'] == 'best' else ('✔' if r['situational'] else '-')
            sec = SEC_KO.get(r['secondary'], r['secondary'] or '-')
            p(f"| {nm} | {G.RAR_KO[r['rar']]} {r['L']} | {G.STYLE_KO[r['style']]}·{G.KIND_KO[r['kind']]} | {r['rate']} | {r['per_hit'][0]}~{r['per_hit'][1]} | {r['dps']} | {r['sp']} | {pct(r['vs_forge'])} | {sec} | {DIR_KO[r['direction']]} | {req_short(r['req'])} | {kinds_txt(r['kinds'])} | {r['strength']:.2f} | {sit} |")
        p()


SEC_KO = {'crit_chance': '치명 확률', 'crit_damage': '치명 피해', 'attack_speed': '공격 속도', 'move_speed': '이동 속도',
          'lifesteal': '흡혈', 'hp': '최대 HP', 'hp_regen': 'HP 재생', 'damage_reduction': '피해 감소', 'defense': '방어',
          'skill_damage': '스킬 피해', 'cooldown_reduction': '재사용 감소', 'mp': '최대 MP', 'mana_regen': 'MP 재생',
          'heal_power': '치유력', 'evasion': '회피'}


def sec6():
    stc = SP['special_trial']
    p('## 6. 특별 시련 (가장 적은 공사로)')
    p()
    p('### 6.1 무엇인가')
    p()
    p(f"- 층마다 하나 있는 시련방(기믹방)이 **{int(L.SPECIAL_Q * 100)}% 확률로 \"특별 시련\"** 이 된다. 기믹은 같다. **조건 하나**가 붙고, 들어가면 바로 알려 준다.")
    p('- 기믹 성공 + 조건 지킴 → 평소 상자(`gimmick_floor_N`) **에 더해** 특별 상자(`special_trial_fNN`, 개인 루팅)가 하나 더 놓인다. 경험치 ×1.5.')
    p('- 기믹 성공 + 조건 깨짐 → 평소 상자만. 실패가 아니다. 기믹 실패 → 지금과 같다.')
    p(f"- 같은 층을 {L.SPECIAL_PITY}번 연속 특별 시련 없이 돌면 다음 방문은 반드시 특별 시련 (`pity_visits: {L.SPECIAL_PITY}`, 파티원 중 가장 큰 값). 그래서 실제로는 방문의 {L.SPECIAL_Q_EFF * 100:.0f}% 가 특별 시련이다.")
    p('- 특별 상자 = 특별 시련 무기 1개 확정 + 50% 로 하나 더 (+ 단계 6·9 는 특별 시련 방어구 50%) + 그 층 정수 1 + 골드. 무기는 단계 풀 `band_tNN_special` 에서 층 몫 1:8:1 로.')
    p()
    p('### 6.2 조건 4종 (공통 구현)')
    p()
    p('| id | 이름 | 판정 | 그 기믹이 지원해야 하는 것 |')
    p('|---|---|---|---|')
    p('| `swift` | 서두름 | 기믹 시작부터 성공까지 `seconds` 초 이하. 보스바에 남은 초 | 없음 (GimmickRoom.elapsed) |')
    p('| `unscathed` | 무상 | 방 안에서 최대 HP 3% 이상 맞은 횟수 ≤ 2 + 파티원 1명당 1 | 없음 (피해 훅) |')
    p('| `abstain` | 절제 | 방 안에서 물약·주문서를 하나도 안 씀 | 없음 (소모품 훅) |')
    p('| `flawless` | 무결 | 기믹의 "실수"(기회 하나 잃음) 0번 | 실수 자리에서 `noteMistake()` — lever_sequence · resonance_tune · book_cipher · gear_timing 만 |')
    p()
    p('### 6.3 층별')
    p()
    p('| 층 | 기믹 | 조건 후보 (둘 중 하나, 시드로) | swift 초 | 특별 상자가 고르는 단계 (무게) | 그 단계 특별 시련 무기 | 방어구 |')
    p('|---|---|---|---|---|---|---|')
    COND = {'swift': '서두름', 'unscathed': '무상', 'abstain': '절제', 'flawless': '무결'}
    for f in range(1, 11):
        v = stc['per_floor'][str(f)]
        tw = ' · '.join(f"{t}단 {w}" for t, w in v['tiers'].items())
        wl = []
        for t, ids in v['tier_pool_weapons'].items():
            if ids:
                wl.append(f"{t}단: " + ', '.join(W[i]['name'] for i in ids))
        arm = '; '.join(f"{t}단: {SP['armor_sets'][A[ids[0]]['set']]['name']}" for t, ids in v['tier_pool_armor'].items()) or '-'
        p(f"| {f} {G.FLOOR_NAME[f]} | `{v['gimmick']}` | {' · '.join(COND[c] for c in v['conditions'])} | {v['swift_seconds'] or '-'} | {tw} | {' / '.join(wl)} | {arm} |")
    p()
    p('swift 초 = 그 기믹이 보통 걸리는 시간의 0.7배 (제한 시간이 있는 lights_out 120초 → 84, book_cipher 180 → 126). 조건 후보는 그 기믹과 겹치지 않게 골랐다(spore_purge 는 감염 피해가 있어 무상을 빼고, void_trial 은 버티기라 서두름을 뺐다).')
    p()
    p('### 6.4 문구 (공략 없이, 분위기만)')
    p()
    t = stc['texts']
    p('| 자리 | 문구 |')
    p('|---|---|')
    p(f"| 방 안 글자판 | `{t['board']}` |")
    p(f"| 들어갈 때 가운데 글자 | `{t['title']}` / `{t['subtitle']}` |")
    p(f"| 채팅 | `{t['chat']}` |")
    for k, v in t['conditions'].items():
        p(f'| 조건 `{k}` | {v} |')
    p(f"| 보스바 | `{t['bar']}` |")
    p(f"| 조건 깨짐 | `{t['broken']}` |")
    p(f"| 조건 지킴 (성공 때) | `{t['kept']}` |")
    p()
    p('기믹을 푸는 방법은 적지 않는다. 조건은 "무엇을 하지 마라 / 언제까지"만 말한다. 힌트(core/Hints)는 기믹 실패만 센다 — 조건이 깨진 것은 실패가 아니다.')
    p()
    p('### 6.5 설정 키')
    p()
    p('```yaml')
    p('# dungeon.yml')
    p('special_trial:')
    p('  enabled: true')
    p(f'  chance: {L.SPECIAL_Q}          # 층 방문마다 시련방이 특별 시련일 확률 (시드 고정)')
    p(f'  pity_visits: {L.SPECIAL_PITY}         # 이만큼 연속으로 못 보면 다음은 확정 (0 = 끔)')
    p('  xp_bonus: 0.5          # 조건까지 지키면 시련 경험치 ×1.5')
    p('  conditions:')
    p('    swift:     {time_factor: 0.7, min_seconds: 40, default_seconds: 75}')
    p('    unscathed: {hits: 2, per_member: 1, min_damage: 0.03}')
    p('    abstain:   {potions: true, scrolls: true}')
    p('    flawless:  {}')
    p('# floors.yml (층마다, 생략하면 6.3 기본표)')
    p('#  special_trial: {conditions: [flawless, swift], seconds: 60}')
    p('# loot.yml')
    p('#  special_trial_f01 … special_trial_f10  (PICK → band_tNN_special)')
    p('```')
    p()
    p('### 6.6 코드')
    p()
    for c in stc['code']:
        p(f'- {c}')
    p()


def sec7():
    p('## 7. 확률과 기대 회차')
    p()
    p('### 7.1 1회 돌기 가정 (보통 · 솔로 · LUK 0 · 층 끝까지)')
    p()
    p('| 층 | 일반 몹 | 보물방 상자 | 미로 나무/철/금(비밀방·금고 포함) | 금고 금 상자 + 미믹 | 시련 성공 | 특별 시련 성공 | 정예 | 1회 골드 |')
    p('|---|---|---|---|---|---|---|---|---|')
    for f in range(1, 11):
        c = L.maze(f)
        p(f"| {f} | {L.MOBS_RUN[f]} | {L.treasure_rooms(f) * L.TREASURE_CHESTS:.1f} | {c['wood']}/{c['iron']}/{c['gold'] + c['secret'] + c['vault']:.2f} | {c['vault'] + c['mimic']:.2f} | {L.GIMMICK_OK} | {L.SPECIAL_Q_EFF * L.SPECIAL_C:.2f} | {L.ELITES[f]} | {L.run_gold(f):,.0f} |")
    p()
    p('미로 상자 수는 0.3.4 자가 진단(10층: chests 113 · vaults 10 · secret_rooms 17 · mimics 14)에서 잡았다. 시련 성공 0.8 · 특별 조건 지킴 0.65 는 추정이다.')
    p('"기대 회차" = **그 무기의 요구에 맞춘 빌드**가 그 무기 단계의 층을 돌 때 그 무기 하나를 얻기까지 평균 몇 번 (기하분포 1/p, 빌드 편향 0.65 포함).')
    p()
    p('### 7.2 항목 확률')
    p()
    fac = ST['fac']
    p('| 층 | 몬스터·상자 배율 (몹 기본 × 배율) | 몹 1마리 | 보물방 | 나무 | 철 | 금 | 시련방 PICK | 금고·미믹 PICK | 정예 무기 (그 단계 풀 안) |')
    p('|---|---|---|---|---|---|---|---|---|---|')
    for f in range(1, 11):
        m = fac['M'][str(f)] if isinstance(list(fac['M'].keys())[0], str) else fac['M'][f]
        g = lambda d, k: d[str(k)] if str(k) in d else d[k]
        p(f"| {f} | {m:.3f} | {L.M_BASE_MOB[f] * m:.4f} | {L.M_BASE['treasure'] * m:.4f} | {L.M_BASE['wood'] * m:.4f} | {L.M_BASE['iron'] * m:.4f} | {L.M_BASE['gold'] * m:.4f} | {g(fac['T'], f):.3f} (상자 2번) | {g(fac['V'], f):.3f} | {g(fac['E'], f):.3f} |")
    p()
    p('몬스터·상자 배율은 "그 층 단계 무기 가운데값 회차"가 목표(1층 2.0 · 2~4층 3.0 · 5·6·8~10층 3.5 · 7층 3.0)가 되게 풀었다. 떼 몹은 ×0.7(지금과 같음).')
    p()
    p('### 7.3 띠 × 획득처 기대 회차 (가운데값, 범위)')
    p()
    p('| 띠 | 보스 | 대장간 (재료 · 골드 → ×1.5) | 몬스터·상자 | 시련방 | 특별 시련 | 금고·미믹 | 정예 | 상인 (값 · 골드 회차) |')
    p('|---|---|---|---|---|---|---|---|---|')

    def cell(r, k):
        x = r.get(k)
        if not x:
            return '·'
        return f"{x['median']}" + (f" ({x['lo']}~{x['hi']})" if x['lo'] != x['hi'] else '')
    for b in G.BANDS:
        r = RATES[b]
        fo = FORGE[b]
        shop = [w for w in W.values() if w['band'] == b and 'P' in L.weapon_kinds(w)]
        sh = '·'
        if shop:
            h = next(h for h in SRC[shop[0]['id']]['homes'] if h['kind'] == 'P')
            sh = f"{shop[0]['name']} {h['price']:,}G (Lv{h['level_req']}) · {h['gold_runs']}"
        p(f"| {G.blabel(b)} | {cell(r, 'B')} | {fo['mat_runs']} · {fo['gold_runs']} → {fo['gold_runs_new']} ({fo['gold']:,} → {fo['gold_new']:,}G) | {cell(r, 'M')} | {cell(r, 'T')} | {cell(r, 'S')} | {cell(r, 'V')} | {cell(r, 'E')} | {sh} |")
    p()
    p('이웃 층에서도 나온다: 단계 N 무기는 N+1 층에서 2/10, N−1 층에서 1/10 몫. 예를 들어 몬스터·상자 무기는 다음 층을 돌 때 자기 층의 약 3~4배 회차, 앞 층에서는 7~10배 회차로 나온다(`gear_spec.json weapons.*._spec.source.runs_next_floor / runs_prev_floor`).')
    p()
    p('읽는 법:')
    p('- **대장간**은 재료가 1회에 넉넉히 모여(층 몹 재료 1회 40~80개, 정예 재료 3.6~5.5개) 재료로는 0.2~0.5회다. 골드가 묶는다. 무기 레시피 골드를 **×1.5** 로 올려(단계 2~10) 대장간 = 0.4~1.1회 → "거의 공짜"가 아니라 "한 번 돌면 확정"이 된다. 방어구 레시피는 그대로.')
    p('- **몬스터·상자** 2.5~3.5회. 1층 첫 장비만 2회 안팎. 지금은 5층 영웅 무기가 거의 매번 나왔다(1회 이하) — 이번에 내렸다. 묶음 안에서 요구 1위 능력치가 혼자인 무기(예: 4단계 소금물 종 홀, 체력·정신)는 그 빌드에게 1회 안팎으로 빨리 나온다 — 빌드 편향(own_build_bias)이 원래 그렇게 돕는다.')
    p('- **시련방·금고·미믹·정예** 5회 안팎, **특별 시련** 3~7회 (단계 4·5·9 는 같은 주 능력치 무기가 둘이라 6.5~7.4회). 대장간보다 5배쯤 오래 걸리는 대신 같은 단계에서 효과가 세다(s 2.2~2.8, 대장간 무기는 0.8~2.8, 보스 전설 0.8).')
    p('- **보스 고유**는 지금 그대로(1.4~9회). 신화는 어려움 이상 10층 보스만.')
    p('- **상인**은 1~3단계 3개. 그 층 1회 골드의 1.7~1.9배. 상인의 `level_req`(이미 있는 키)로 그 레벨이 돼야 진열된다.')
    p('- 대장간은 일부러 싼 바닥값(0.4~1.1회)이다. 나머지는 가운데값이 2회 미만(공짜)인 종류가 없고, 10회를 넘는 무기(노가다)도 없다(가장 긴 것 보스 전설 9.1회 · 금고·미믹 묶음 끝 8.7회). 파티면 각자 굴린다(개인 루팅), 파티 보너스 +5%/명.')
    p()
    p('### 7.4 1회 돌기 장비 수 (무기 · 방어구, 보통·솔로) — 전과 후')
    p()
    p('| 층 | 무기 (전 → 후) | 방어구·방패·장신구 (전 → 후) |')
    p('|---|---|---|')
    for f in range(1, 11):
        v = ST['per_run'][str(f)]
        p(f"| {f} | {v['before'].get('weapon', 0)} → {v['after'].get('weapon', 0)} | {v['before'].get('armor', 0)} → {v['after'].get('armor', 0)} |")
    p()
    p('6·8·9·10층은 보스 무기뿐이던 것(0.25)이 2.5~3개로 돌아온다. 2층이 가장 많이 는다(×1.6, 단계 2 무기가 23개로 늘어서). 나머지는 ±25% 안 — "아무 데서나 쏟아지는" 정도가 아니다.')
    p()


def sec8():
    p('## 8. 새 무기 106개 (띠별)')
    p()
    p('수치·무기 스킬 조합·모델 색은 `gear_spec.json weapons` 에 items.yml 형식으로 있다(`_spec`·`direction`·`source`, `model` 의 palette·notes·hold·new_silhouette 는 명세용 — 넣을 때 뺀다). 한 방 피해 = 전투 명세 §5.4 († 는 §13). 무기 스킬 피해 숫자는 이미 계수(K ÷ 옛 초당 횟수)를 곱했다.')
    p()
    p('수치 공식 (items.yml 131개에서 맞춘 것 — 옛 판 `gs_fit.py` 피해 비 평균 1.002 · 표준편차 0.015, 전투 명세 §5.7 로 옮김):')
    p()
    p('```')
    p('한 방 가운데값 = P(L) × 희귀도 × c(L) × K(방식, 간격) × 간격                 (전투 명세 §5.7)')
    p('  P(L) = 7 + 0.25(L−1) + 0.0195(L−1)²      희귀도: 일반 1.00 · 고급 1.06 · 희귀 1.13 · 영웅 1.21 · 전설 1.31 · 신화 1.45')
    p('  c(L) = (1 + 0.02 S) ÷ (1 + 0.01 S),  S = 8 + 3.6 × (L + 3)')
    p('  K    = 근접 1.47 − 0.143 × max(0, 1/간격 − 1.5) · 원거리 1.413 · 시전 1.22')
    p('  범위 = 가운데값 ± 3~12% (평균 6.8%), 정수')
    p('간격           = 모양 기본값 (전투 명세 §5.1) — 새 무기는 옛 판 공속의 역수를 모양 ±15% 안으로')
    p('주 스탯 줄      = (1 + 0.22 L) × 희귀도 계수(일반 0.6 · 고급 0.8 · 희귀 1.0 · 영웅 1.2 · 전설 1.45 · 신화 1.75), 굴림 ×0.85~1.15')
    p('                 줄 이름 = 요구 1위 능력치 (기존 무기는 그대로)')
    p('부가 스탯       = 기준값(L) × 희귀도 계수 × 0.85~1.15 (능력치형 ×0.6) — 개수 일반·고급 1 · 희귀 2 · 영웅 3 · 전설 4 · 신화 5')
    p('  기준값: hp 3+3.2L · mp 2+1.6L · defense 1+0.35L · crit_chance 0.01+0.0009L · crit_damage 0.03+0.003L · attack_speed 0.02+0.0009L')
    p('          move_speed 0.01+0.0005L · cooldown_reduction 0.01+0.0009L · skill_damage 0.02+0.0015L · mana_regen 0.1+0.015L')
    p('          hp_regen 0.2+0.05L · heal_power 1+0.8L · lifesteal·damage_reduction·evasion 0.01+0.0006L')
    p('  고르는 순서(방향): 출혈치명 치명확률→치명피해→공속 · 유지흡혈 흡혈→HP→재생 · 방벽 피해감소→HP→방어 · 폭발 치명피해→스킬피해→HP ·')
    p('          처형 치명피해→치명확률→이동 · 속공 공속→이동→치명확률 · 마나순환 재사용→MP→MP재생 · 지원 치유력→MP재생→HP ·')
    p('          상태이상 스킬피해→치명확률→재사용 · 기습 치명확률→이동→회피 · 광기 흡혈→치명피해→공속 · 파쇄 치명피해→HP→방어 (시전 무기는 공속 → 재사용)')
    p('요구 능력치     = §3.1 (합 ceil(2.75(L−1)), 60/40 · 50/30/20)')
    p('고유 효과 강도  = 효과 명세 규칙 B = clamp(0.08 + 0.6 × gap, 0.04, 0.28), s = B/0.10, gap = 띠 최고 기본 성능 ÷ 이 무기 − 1 (띠 전체)')
    p('```')
    p()
    for b in G.BANDS:
        ids = sorted([wid for wid, w in W.items() if w['new'] and w['band'] == b], key=lambda i: (W[i]['L'], i))
        if not ids:
            continue
        p(f'### {G.blabel(b)} ({len(ids)})')
        p()
        p('| 무기 | Lv·희귀도·단계 | 모양 (방식·간격) | 피해 | 한 방 | 요구 | 고유 효과 (강도) | 방향 | 획득처 (표 · 확률) | 이야기 |')
        p('|---|---|---|---|---|---|---|---|---|---|')
        for wid in ids:
            w = W[wid]
            e = SP['weapons'][wid]
            shape = e['model']['shape']
            newsh = '**' + SP['new_shapes'][shape]['name'] + '** ' if shape in SP['new_shapes'] else ''
            hs = []
            for h in SRC[wid]['homes']:
                if h['kind'] == 'P':
                    hs.append(f"상인 핀 {h['price']:,}G (Lv{h['level_req']})")
                else:
                    ch = h.get('chance')
                    chs = '확정' if ch == 'guaranteed' else (f"{ch}" if ch is not None else '')
                    hs.append(f"{G.SK_KO[h['kind']]} `{h['table']}` {chs} (묶음 {h.get('pool_size')}) · {h.get('runs')}회")
            fix = ' †' if wid in ST['per_hit_fix'] else ''
            p(f"| {w['name']} `{wid}` | Lv{w['L']} {G.RAR_KO[w['rar']]} · {SRC[wid]['tier']}단 | {newsh}`{shape}` ({G.STYLE_KO[w['style']]} {w['interval']}초) | {G.KIND_KO[w['kind']]} | {w['per_hit'][0]}~{w['per_hit'][1]}{fix} | {req_txt(WR[wid]['requires'])} | {utext(wid)} ({w['strength']:.2f}) | {DIR_KO[w['direction']]} | {' / '.join(hs)} | {w['lore']} |")
        p()


def sec9():
    p('## 9. 모델')
    p()
    p('### 9.1 규칙')
    p()
    newsil = sum(1 for wid, w in W.items() if w['new'] and w['shape'] in SP['new_shapes'])
    p(f'- 새 무기 106개 중 {newsil}개가 새 실루엣 15종, {106 - newsil}개가 기존 템플릿(longsword·kris·dagger·katar·great_axe·cleaver·glaive·greatsword·falchion·broadsword·mace·sickle·fang_blade·longbow·recurve_bow·composite_bow·blade_bow·staff_orb·staff_ring·sun_scepter·chalice_scepter·censer_staff·bell_scepter)을 새 색으로.')
    p('- 테마 장식(dress_blade·dress_shaft·dress_bow, `voxel/weapons.THEME_KEYS`)은 id 로 잡힌다. 새 id 는 모두 기존 키(moss/corridor/root · skitter/silk · miners/ore_ · spore/mycel/glowcap/hypha · brine/tide/eel/drowned/sluice/verdigris · ember/cinder/slag/anvil/bellows/forge · rime/frost · prism/geode/amethyst/shardglass/crystal/resonan · ink/lore/index · clock · abyss/void)를 품는다. `pit_*` 두 개는 style rusted_iron → forge.')
    p('- 희귀도 장식 단계(P.lv 0~5)는 그대로. 새 무기에 전설·신화는 없다(아우라·애니메이션 없음).')
    p('- 마법 피해로 바꾼 근접·활 8개(§1.2)는 모델을 바꾸지 않는다. 손잡이 쪽 보석(gem)을 glow 로 한 단계 밝혀(lv≥2 규칙 그대로) "마법이 깃든" 표시만.')
    p('- **손에 드는 각도**: 0.3.4 의 모양별 방식 그대로 — `voxel/weapons.HOLD[shape]`(fp_yaw), `TWO_HANDED`, 활은 `BOWS`(displays.voxel_bow), `tools/hold_preview.HEAD_SHAPES`(옆 머리 — 바닐라 도끼 행과 비교). `displays._fp_scale` 넓이 규칙은 그대로 걸린다. 새 모양마다 아래 표의 값을 넣고 `python tools/hold_preview.py --shapes <새 모양들>` 시트와 metrics 를 같은 무게 기존 모양과 비교한다.')
    p('- 간격은 전투 명세 §5.1 모양 기본값(새 실루엣도 포함).')
    p()
    p('### 9.2 새 실루엣 15종')
    p()
    p('| 모양 | 이름 | 계열 | 방식 · 기본 간격 | 양손 | 옆 머리 | HOLD | 쓰는 무기 |')
    p('|---|---|---|---|---|---|---|---|')
    for k, v in SP['new_shapes'].items():
        p(f"| `{k}` | {v['name']} | {v['family']} | {G.STYLE_KO[v['style']]} {v['interval']}초 (초당 {v['rate_per_s']}) | {'예' if v['two_handed'] else '-'} | {'예' if v['head_sideways'] else '-'} | {v['hold'] or '기본'} | {len(v['weapons'])} |")
    p()
    p('```python')
    p("# resourcepack/src/voxel/weapons.py")
    p("_TEMPLATES.update({'executioner_axe': executioner_axe, 'flamberge': flamberge, 'great_maul': great_maul, 'sabre': sabre,")
    p("                   'morning_star': morning_star, 'rapier': rapier, 'stiletto': stiletto, 'tanto': tanto, 'war_spear': war_spear,")
    p("                   'antler_staff': antler_staff, 'lamp_crook': lamp_crook, 'thurible_rod': thurible_rod, 'chime_rod': chime_rod})")
    p("BOWS = (..., 'bone_bow', 'twin_bow')            # bow(g, p, kind) 의 curv 표에 bone_bow 3.4 · twin_bow 3.2")
    p("TWO_HANDED |= {'executioner_axe', 'flamberge', 'great_maul', 'war_spear'}")
    p("HOLD.update({'sabre': {'fp_yaw': 100}})          # 나머지는 기본 90")
    p("# resourcepack/tools/hold_preview.py")
    p("HEAD_SHAPES += ('executioner_axe', 'great_maul', 'morning_star', 'lamp_crook', 'thurible_rod')")
    p("# resourcepack/src/shapes_weapons.py TWO_HANDED (2D 아이콘 쪽) 에도 같은 양손 모양을 더한다")
    p('```')
    p()
    p('### 9.3 모양별 만들기 (voxel/weapons.py, 단위 = 복셀, L = model.length)')
    p()
    for k, v in SP['new_shapes'].items():
        p(f"**{v['name']}** `{k}` — {v['family']}, {G.STYLE_KO[v['style']]} {v['interval']}초")
        p(f"- 만들기: {v['build']}")
        p(f"- 부품: {v['parts']}")
        p(f"- 색 역할: {v['palette_roles']}")
        p(f"- 손: {v['hold_note']}")
        p()


def sec10():
    p('## 10. 새 방어구 6세트')
    p()
    p('수치는 GDD §16.4 방어구 공식(세트 방어 합 = (3+0.95L) × 무게 × 희귀도, 부위 비중 20/35/27/18%, 주 스탯 ×1.7, 부가 ×2.0, 신발 이동 속도는 기준값). 요구는 §3.3(세트 네 부위 같음).')
    p('겉모습별 장단점(판금·가죽·천의 이동·회피·마나 등)은 다른 설계 작업(겉모습 명세)이다. 새 6세트는 `sets.<id>.look` 과 흉갑 모양만 맞으면 그 규칙을 그대로 받는다.')
    p('장비 텍스처는 `equipment.py` paint_set(look) + style 로, 투구는 `voxel/armor.py` 의 투구 모양(helm_horned·helm_knight·half_mask·hood·wizard_hat)으로. 3D 어깨·등 장식(`armor_pieces.py`·`items/ArmorPieceLayout`)은 0.3.4.2 에서 런타임 서비스가 빠졌지만 모델 생성기는 남아 있다 — 다시 켤 때를 위해 look·back·테마·흉갑 색만 적어 둔다(생성기가 자동으로 만든다).')
    p()
    for sid, s in SP['armor_sets'].items():
        pi = list(s['pieces_items'].values())
        Lv = pi[0]['level_req']
        look = {'heavy': '판금', 'light': '가죽', 'cloth': '천'}[s['look']]
        p(f"### {s['name']} `{sid}` — 단계 {s['tier']} · Lv{Lv} · {G.RAR_KO[pi[0]['rarity']]} · {look} · 획득처 {' + '.join(G.SK_KO[G.SRC_SK[x]] for x in s['sources'])}")
        p()
        dz = s.get('design', {})
        p(f"- 요구 (네 부위 같음): {req_txt(pi[0]['requires'])} — {s['requires_why']}")
        p(f"- 세트 효과: 2부위 {s['bonuses']['2']} · 4부위 {s['bonuses']['4']}")
        if dz:
            p(f"- 색: style `{dz.get('style')}` · {' '.join(dz.get('palette', []))} · 등 `{s.get('back')}`")
            p(f"- 장비 텍스처 무늬 (equipment.py): {dz.get('motif')}")
            p(f"- 투구 (voxel/armor.py): `{dz.get('shapes', {}).get('head')}` 모양 + 같은 색 · 3D 장식 (armor_pieces.py): {dz.get('pieces3d')}")
            p(f"- 이야기: {dz.get('lore')}")
        p()
        p('| 부위 | 이름 | 모양 | 스탯 |')
        p('|---|---|---|---|')
        for pid, pp in s['pieces_items'].items():
            st = {k: ([round(x, 3) for x in v] if isinstance(v, list) else v) for k, v in pp['stats'].items()}
            p(f"| {pp['armor_slot']} | {pp['name']} `{pid}` | {pp['model']['shape']} | {st} |")
        p()
    p('세트를 고른 이유: 겉모습별로 비어 있던 곳을 메운다.')
    p('- 판금: Lv8 → Lv19 사이 (균사 갑각 Lv14, 정신 20% — 재생·지원형), Lv34 → Lv44 사이 (색인 방벽 Lv38, 지능 30% — 마검사).')
    p('- 가죽: Lv14 → Lv24 사이 (수로 잠수부 Lv19, 체력 30%), Lv24 → Lv34 사이 (서리 추적자 Lv28, 힘 30% · 행운 20%).')
    p('- 천: Lv14 → Lv24 사이 (잿불 성가자 Lv23, 지능 쪽), Lv34 → Lv44 사이 (태엽 점성술사 Lv42, 정신 쪽).')
    p('- 획득처도 새 종류로: 정예+대장간 2세트(판금), 시련방+대장간 1, 금고·미믹 1, 특별 시련 2. 대장간 레시피 12개(`recipes_new`).')
    p()


def sec11():
    p('## 11. 데이터 파일 바꿈 요약')
    p()
    p('- **items.yml**: 새 무기 106 (`gear_spec.json weapons`) · 새 방어구 24 + sets 6 · 기존 무기 131 `existing_changes`(weapon_type·floor·classes 삭제 → tier · attack{style, interval, kind} · stats.damage 새 범위 · requires 새 값 · 무기 스킬 피해 × weapon_skill_factor) · 기존 방어구·방패 95 `armor_changes`(floor·classes·requires_any 삭제 → tier · requires 새 값) · sources 값 trial / special / hoard 추가 · 머리 주석.')
    p(f"- **loot.yml**: 표 {len(SP['loot_changes'])}개 — 단계 풀 band_tNN_* 50 · 층 섞음 mix_fNN_drop 10 · special_trial_fNN 10 · hoard_fNN 10 · 몹·보물방·미로 상자·시련방·정예 다시 씀 · gear_fNN_common 6 삭제. settings own_class_bias → own_build_bias.")
    p('- **recipes.yml**: 방어구 12개 새로 (균사 갑각·수로 잠수부·색인 방벽). 무기 레시피 54개(단계 2~10) 골드 ×1.5 (`recipes_changes`). 새 무기 레시피는 없다 — 대장간 무기는 지금 그대로가 기준이다.')
    p('- **npcs.yml**: merchant shop 에 3줄 (길손의 사브르 1,500G Lv3 · 은실 감긴 사슴뿔 지팡이 2,000G Lv8 · 빛갓 레이피어 2,500G Lv11 — `level_req` 는 이미 있는 키).')
    p('- **classes.yml**: 전투 명세 §6.3 (weapon_types 삭제 · skill_scale · starter_weapon · 쿨다운 ×0.9). 이 명세는 더하지 않는다.')
    p('- **dungeon.yml**: special_trial 블록. **floors.yml**: (선택) special_trial 덮어쓰기.')
    p('- **titles.yml**: 바꾸지 않는다 (칭호 12개 그대로).')
    p('- **GDD.md**: §11 장비(요구 능력치 규칙·단계·레벨 창·획득처 종류·특별 시련) · §5 기믹방(특별 시련) · §11.10 루팅(PICK·own_build_bias). **ARCHITECTURE.md §6**: items.yml tier·requires(AND)·attack, loot.yml pick, dungeon.yml special_trial.')
    p()


def sec12():
    p('## 12. 테스트')
    p()
    for t in SP['tests']:
        p(f"**{t['name']}** — `{t['file']}`")
        for c in t['checks']:
            p(f'- {c}')
        p()
    p('이 명세는 위 검사 중 데이터로 할 수 있는 것을 스크립트로 이미 돌렸다: 직업 검사(`g2_check.py`, 부족 0건 · 어떤 빌드로도 안 맞는 무기 0개) · 띠 다양성(§2.2) · 옆길 ±5%(§5) · 영웅 이상 획득처 종류 1개(237개 중 위반 0) · 회차 창(§7.3).')
    p()


def sec13():
    p('## 13. 다른 설계자와 맞출 것')
    p()
    p('**전투 명세(combat_spec)**')
    p('- 숫자는 그대로 썼다. 예외: 새 옆길 무기 6개의 한 방 피해를 ±5% 규칙에 맞게 1점 안팎 다시 반올림했다 (초당 피해 오차는 전투 명세의 반올림 오차 4.4% 안):')
    p()
    p('| 무기 | 전투 명세 | 이 명세 | 대장간 기준 대비 (전 → 후) |')
    p('|---|---|---|---|')
    for wid, v in ST['per_hit_fix'].items():
        p(f"| {wname(wid)} | {v['old'][0]}~{v['old'][1]} | {v['new'][0]}~{v['new'][1]} | {pct(v['dev_old'])} → {pct(v['dev_new'])} |")
    p()
    p(f"- `attack.kind: magic` 으로 바꾼 근접·활 {len(Q.KIND_MAGIC)}개(§1.2): `{'`, `'.join(Q.KIND_MAGIC)}`. 한 방 피해는 같다(c(L) 물리·마법 같음). 기본 공격·`flurry`·`cleave` 피해 종류가 마법이 된다. 이 무기들의 무기 스킬 꼬리표는 전투 명세 그대로.")
    p('- 전투 명세 §6.4 의 "DEX·LUK·WIS·VIT 단독 요구 60/40 나누기" 권고는 이 명세의 일반 규칙(모든 장비 2~3 능력치)으로 넘어갔다. 직업 맞추기에 쓴 0.3.4 요구치보다 같은 방향 한 벌이 싸다(§3.4 보기).')
    p('- 전투 명세 스크립트(`tools/ce_core.py`)는 옛 형식(attack.speed)의 장비 명세를 입력으로 읽는다. 이 명세가 `gear_spec.json` 을 새 형식으로 덮어썼으므로, 같은 결과가 다시 나오게 `ce_core.py` 의 입력 경로만 `tools/_bak/gear_spec_c1.json`(옛 판 사본)으로 바꿨다(없으면 예전처럼 gear_spec.json). 전투 숫자는 바뀌지 않는다.')
    p()
    p('**효과 명세(unique_spec)**: 효과 id·수치 그대로. 기존 131개의 강도(s)는 종류별 구간으로 계산된 값이다 — 종류가 없어졌으니 띠 전체로 다시 계산하는 편이 맞다(대장간·몬스터·상자 무기 일부의 s 가 오른다). 새 106개는 띠 전체 규칙으로 계산되어 있다.')
    p()
    p('**겉모습 명세(판금·가죽·천 장단점)**: 이 명세는 방어구 요구 능력치(§3.3)를 정했다. 겉모습 명세가 요구치를 따로 정하면 같은 예산 T(L)·같은 나눔을 쓰고, 세트마다의 짝(§3.3 표)은 하나로 합친다. 새 6세트는 look 만 맞춰 두었다.')
    p()


def sec14():
    p('## 14. 주의 · 남은 위험')
    p()
    p('- 요구 능력치가 같은 방향끼리는 싸져서 "알맞은 빌드"의 남는 포인트가 는다(수호기사 Lv44: 요구에 묶이는 포인트 204 → 107). 피해·체력이 늘지는 않는다(분배 비율이 같으면 스탯은 그대로) — 요구가 분배를 덜 강제할 뿐이다. 전투 명세의 직업 ±10% 는 그대로 선다.')
    p('- 반대로 섞은 빌드(판금 + 행운 무기 등)는 세금을 낸다. 1포인트 세금 ≈ 피해 1%(전투 명세 §6.4). 툴팁의 요구 줄이 색으로 충족/미달을 보여 주므로 혼란은 적다.')
    p('- 특별 시련 성공률 0.65 · 시련 성공 0.8 은 추정이다. 테스트 서버에서 층마다 10번씩 재 보고 chance·조건 수치를 맞춘다.')
    p('- 정예 단계 풀: 3층 정예가 2단계 방어구를 20% 로 준다. 테마가 섞이는 것은 주인이 원한 "섞인 루팅"이지만, 그 정예 재료(레시피)와 다른 세트가 나올 수 있다는 점을 도감 글에 적지 않는다(획득처는 "정예"뿐).')
    p('- 단계 1·10 은 이웃이 하나라 몫이 7:1 · 2:7 이다. 10단계 장비는 9층에서 1/10 로 미리 나온다(요구가 높아 대부분 못 낀다).')
    p('- 새 영웅 무기 63개의 무기 스킬은 방향별 조합형 틀 12종을 층 연출로 바꿔 쓴 것이다. 이름은 모두 다르다. 무기마다 완전히 다른 조합을 원하면 따로 다듬는다.')
    p('- 기존 플레이어: 이미 가진 장비의 요구가 바뀌어 갑자기 못 끼게 될 수 있다. 0.3.5 의 무료 스탯 초기화(전투 명세 §10.3, `stats.role_reset_035`)와 같은 접속 안내에 "장비 요구 능력치가 바뀌었다"를 붙인다. 이미 낀 장비는 벗기지 않는다(지금 규칙: 못 채우면 효과만 꺼짐 — EquipRules).')
    p()


def main():
    head()
    sec1()
    sec2()
    sec3()
    sec3b()
    sec3c()
    sec4()
    sec5()
    sec6()
    sec7()
    sec8()
    sec9()
    sec10()
    sec11()
    sec12()
    sec13()
    sec14()
    with open(os.path.join(G.D2, 'gear_spec.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(OUT) + '\n')
    print('md lines', len(OUT))


if __name__ == '__main__':
    main()
