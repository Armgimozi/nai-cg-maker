import json,sys,collections
D='/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad/design2/'
sys.path.insert(0,D+'tools')
import ue_catalog as C
from ue_gen import W,assign,top,blabel,WT_KO,RAR_KO,SRC_KO,DIR,CORE,gaps,div
class Ph(str):
    def __format__(self,spec): return "{"+str(self)+"}"
def template(e,variant=None):
    old=(C.pc,C.sec)
    C.pc=lambda v: "{"+str(v)+"}%" ; C.sec=lambda v: "{"+str(v)+"}초"
    p={k:Ph(k) for k in e['params']}
    if variant: p['element']=variant
    try: return e['desc'](p)
    finally: C.pc,C.sec=old
HOOK_KO={'on_hit':'적중','on_crit':'치명타','on_kill':'처치','on_hurt':'들고 맞음','hp_below':'HP 낮음','hp_above':'HP 높음',
 'nth_hit':'N번째 공격','first_hit':'첫 타','vs_state':'대상 상태','on_dodge':'회피','on_skill':'스킬 사용','aura':'주기 기운'}
UNIT={'pct':'공격력·피해 비율','cc':'치명 확률','cd':'치명 피해','cap':'최대 HP 비율','heal':'최대 HP 비율','ls':'흡혈','duration':'초',
 'max_stacks':'중첩','stun':'초','n':'번째','vuln':'받는 피해','thr':'HP 비율','dr':'받는 피해 감소','radius':'칸','targets':'명',
 'chance':'확률','as':'공격 속도','decay':'초','window':'초','ms':'이동 속도','mp':'최대 MP 비율','cdr':'초','period':'초','dist':'칸','pierce':'명','element':'burn|poison|frost'}
effects={}
for eid,e in C.E.items():
    schema={}
    for k,(ref,kind,mx) in e['params'].items():
        schema[k]={'unit':UNIT.get(k,''),'ref':ref,'kind':{'s':'강도 비례','f':'고정','L':'레벨 단계'}[kind],'max':mx}
    if eid=='imbue': schema['element']={'unit':UNIT['element'],'kind':'무기마다 지정'}
    tmpl=template(e,'burn') if eid=='imbue' else template(e)
    if eid=='imbue': tmpl={v:template(e,v) for v in ('burn','poison','frost')}
    effects[eid]=dict(name=e['name'],direction=e['direction'],hook=e['hook'],desc_template=tmpl,params_schema=schema,
        scaling="강도 s = B/0.10 (B = clamp(0.08 + 0.6×gap, 0.04, 0.28)); '강도 비례' 값 = ref × s (max 로 자름)",
        icd=e['icd'],pvp_rule=e['pvp_rule'],note=e['note'],ranged_only=e['ranged_only'])
dirs=json.load(open(D+'directions.json'))['tags']
spec=dict(version=1,directions=dirs,effects=effects,
    rules=dict(budget="B = clamp(0.08 + 0.6 × gap, 0.04, 0.28). gap = (같은 무기 종류·같은 5레벨 구간 최고 기본 성능 ÷ 이 무기 기본 성능) − 1. Lv1 일반 = 0.04, Lv3 일반 ≤ 0.06",
               strength="s = B / 0.10",
               base_power="P = 무기 피해 중앙값 × (1 + Σ 부가 스탯 가치 + 0.10 × 무기 스킬 수) — tools/ue_gen.py power()",
               template="desc_template 의 {키}% 는 저장값(0~1) × 100 으로, {키}초 는 그대로 표시. imbue 는 element 별 템플릿",
               procs="기본 공격(스킬·패턴·지속 피해·고유 효과 피해가 아닌 것)만 적중 훅을 켠다. rend·hemorrhage·execute·exploit·backstab·first_strike·berserk·armor_break·imbue 는 스킬 적중에도 (재발동 그대로). 고유 효과가 낸 피해(source unique:*)는 어떤 훅도 다시 켜지 않는다."),
    assignments=assign)
json.dump(spec,open(D+'unique_spec.json','w'),ensure_ascii=False,indent=1)

# ── markdown ──
o=[]
P=o.append
P("# 무기 고유 효과 설계 (0.3.5 안)\n")
P("모든 무기에 **고유 효과** 하나를 붙인다. 같은 레벨대라도 무기마다 싸우는 방법이 달라진다.")
P("희귀(상자) 무기는 효과가 세고, 보스 전설·신화 무기는 기본 성능이 높은 대신 효과가 약하다. 그래서 '보스 무기 = 정답'이 아니다.\n")
P("- 효과 종류 26개, 빌드 방향 12개 (`directions.json`, id 고정)")
P("- 기존 무기 131개 전부 배정 (`unique_spec.json` assignments)")
P("- 같은 무기 종류·같은 5레벨 구간 안에서는 방향이 겹치지 않는다 (검사 통과)")
P("- 인접 구간(±5레벨)까지 보면 모든 종류·구간에서 방향 3개 이상\n")
P("## 1. 빌드 방향 12개\n")
P("| id | 이름 | 뜻 | 어울리는 스탯 · 방어구 |")
P("|---|---|---|---|")
AR={'light':'가죽','heavy':'판금','cloth':'천','any':'아무거나'}
for k,v in dirs.items():
    P(f"| `{k}` | {v['name']} | {v['meaning']} | {'·'.join(v.get('pairs_stats',[]))} · {AR.get(v.get('pairs_armor'),'')} |")
P("\n## 2. 고유 효과 26개\n")
P("수치는 강도 s = 1 기준. 실제 무기 수치는 3장 규칙으로 정한다. '재발동'은 같은 효과가 다시 켜지기까지의 최소 시간.\n")
P("| id | 이름 | 방향 | 훅 | 설명 (s = 1) | 재발동 | PvP |")
P("|---|---|---|---|---|---|---|")
def icdtxt(i):
    if not i: return "-"
    m={'per_target':'대상별','global':'전체','per_attacker':'공격자별','per_second_cap':'초당 상한','per_target_stun_immunity':'같은 적 기절 면역','boss':'보스','period':'주기'}
    return ", ".join(f"{m.get(k,k)} {v if isinstance(v,str) else f'{v:g}초'}" for k,v in i.items())
for eid,e in C.E.items():
    ref=C.params_for(eid,25,1.0,'burn' if eid=='imbue' else None)
    P(f"| `{eid}` | {e['name']} | {dirs[e['direction']]['name']} | {HOOK_KO[e['hook']]} | {e['desc'](ref)} | {icdtxt(e['icd'])} | {e['pvp_rule']} |")
P("\n효과별 메모\n")
for eid,e in C.E.items():
    P(f"- `{eid}` {e['name']}: {e['note']}")
P("\n## 3. 수치 규칙 — 희귀 무기와 보스 무기가 경쟁하게\n")
P("1. 무기마다 기본 성능 P 를 잰다. P = 무기 피해 × (1 + 부가 스탯 가치 + 무기 스킬 수 × 0.10).")
P("2. 같은 무기 종류·같은 5레벨 구간에서 P 가 가장 높은 무기와의 차이 gap 을 구한다.")
P("3. 효과 예산 B = 0.08 + 0.6 × gap (0.04 ~ 0.28). 강도 s = B ÷ 0.10. '강도 비례' 수치 = 기준 × s (상한에서 자름).")
P("4. 레벨은 대상 수·관통 수 같은 정수만 단계로 올린다 (휩쓸기 Lv20·40, 연쇄 번개 Lv15·35, 관통 Lv30). 피해 비율은 공격력에 곱하므로 레벨로 따로 올리지 않는다.")
P("5. Lv1 일반(시작 무기)은 B = 0.04 로 맛보기만. Lv3 일반은 0.06 까지.\n")
P("결과: 평소(효과가 안 맞는 상황)에는 상위 무기가 조금 낫다. 자기 상황(무리 사냥·빈사 마무리·출혈 빌드 등)에서는 하위 무기가 이긴다.")
P("아래 표의 '자기 상황'은 P × (1 + 2B) ≥ 구간 최고 P × (1 + 최고 B) 이면 ✔ (효과가 맞는 상황에서 효과 가치가 두 배가 된다고 본다).\n")
by=collections.defaultdict(list)
for w in W: by[w['rar']].append(w['s'])
P("희귀도별 평균 강도 s: " + " · ".join(f"{RAR_KO[k]} {sum(v)/len(v):.2f}" for k,v in sorted(by.items(),key=lambda kv:['common','uncommon','rare','epic','legendary','mythic'].index(kv[0]))) + "\n")
miss=[]
for w in W:
    tp=top[(w['wt'],w['band'])]; tb=max((x for x in W if x['wt']==w['wt'] and x['band']==w['band']), key=lambda x:x['P'])
    if w is not tb and w['P']*(1+2*w['B']) < tp*(1+tb['B'])-1e-9: miss.append((w,tb))
near=[(w,tb) for w,tb in miss if abs(tb['L']-w['L'])<=1]
P(f"'-' (자기 상황에서도 못 이김) {len(miss)}개. 대부분 구간 최고 무기보다 2~5레벨 낮아 같은 시점의 경쟁 상대가 아니다 (레벨 차 평균 {sum(tb['L']-w['L'] for w,tb in miss)/max(1,len(miss)):.1f}).")
P(f"진짜 문제는 레벨 차 1 이하인 {len(near)}개: " + ", ".join(f"{w['name']}(gap {w['gap']*100:.0f}%)" for w,tb in near) + ".")
P("이들은 무기 스킬 0개 vs 보스 전설 2~3개라 기본 격차가 40%를 넘는다. 효과 예산 상한(B 0.28)으로는 못 메운다. 상한을 올리면 출혈·휩쓸기 수치가 지나치게 커진다.")
P("제안: (가) 이 무기들에 무기 스킬 1개씩 추가 (새 무기 설계와 같은 작업) 또는 (나) 구간 최고 무기의 s 를 0.8 → 0.6 으로. 기본 스탯은 건드리지 않는다(주인 선택).")
P("")
P(", ".join(f"{w['name']}(Lv{w['L']}↔{tb['name']} Lv{tb['L']})" for w,tb in miss) + "\n")
P("## 4. 무기 종류별 구간 표\n")
P("열: 레벨 · 희귀도 · 무기 · 획득처 · 고유 효과(이름 / 종류) · 방향 · gap · s · 자기 상황")
for t in ['greatsword','sword_shield','bow','dagger','staff','scepter']:
    P(f"\n### {WT_KO[t]} (`{t}`)\n")
    P("| 구간 | Lv | 희귀도 | 무기 | 획득처 | 고유 효과 | 방향 | gap | s | 자기 상황 |")
    P("|---|---|---|---|---|---|---|---|---|---|")
    for b in range(10):
        ws=sorted([w for w in W if w['wt']==t and w['band']==b],key=lambda w:w['L'])
        tp=top[(t,b)]; tb=max((w for w in ws), key=lambda w:w['P'])
        for w in ws:
            ok = w['P']*(1+2*w['B']) >= tp*(1+tb['B'])-1e-9
            src='·'.join(SRC_KO.get(s,s) for s in w['src'])
            P(f"| {blabel(b)} | {w['L']} | {RAR_KO[w['rar']]} | {w['name']} `{w['id']}` | {src} | **{w['title']}** / `{w['eid']}`{(' '+w['params'].get('element','')) if w['eid']=='imbue' else ''} | {DIR[w['dir']]['name']} | {w['gap']*100:.0f}% | {w['s']:.2f} | {'최고' if w is tb else ('✔' if ok else '-')} |")
P("\n## 5. 구간마다 비어 있는 방향 (새 무기 설계 참고)\n")
P("종류별 핵심 방향 가운데 그 구간에 아직 없는 것. 새 무기는 여기부터 채우면 선택지가 가장 많이 늘어난다.\n")
P("| 종류 | " + " | ".join(blabel(b) for b in range(10)) + " |")
P("|---|" + "---|"*10)
for t in ['greatsword','sword_shield','bow','dagger','staff','scepter']:
    P(f"| {WT_KO[t]} | " + " | ".join(", ".join(DIR[d]['name'] for d in gaps[(t,b)]) or "-" for b in range(10)) + " |")
P("\n## 6. 툴팁 형식 (≤20줄, ≤330px)\n")
P("스탯 줄 다음, 무기 스킬 앞에 2줄. 무기 스킬과 같은 묶음(빈 줄 없음).\n")
P("```\n<#9fe3ff>✧ 고유</#9fe3ff> <white>{이름}</white> <dark_gray>(재발동 N초)   ← 재발동 1초 이상만\n  <gray>{설명 한 줄, 34자 이하}\n```\n")
P("줄이 넘치면 접는 순서 (ItemTooltip.lines tier):")
P("- 일반 장비: 0 전부 → 1 이야기 뺌 → 2 획득처 뺌 → 3 빈 줄 뺌 → 4 스킬 설명 첫 줄만 + 고유 효과를 1줄로 접기 (`✧ {이름} <gray>{짧은 설명}`)")
P("- 보스 고유 장비: 0 전부 → 1 이야기 뺌 → 2 빈 줄 뺌 → **3 스킬 설명 첫 줄만 + 고유 1줄 (획득처는 남김)** → 4 획득처 뺌")
P("  (지금은 보스 장비가 3단계에서 획득처를 먼저 뺀다. 순서를 바꿔야 신화 4스킬 무기 3개가 TooltipFitTest '보스 이름' 검사를 통과한다.)")
P("- 시뮬레이션(`tools/ue_tooltip2.py`): 131개 전부 +0·+8·+10 에서 20줄 이하, 보스 장비는 획득처 유지. 가장 긴 것 voidheart_staff 20줄.")
P("- 설명 줄은 전부 34자 이하·330px 이하로 검사함 (`tools/ue_gen.py` problems 0). 새 효과·새 무기도 같은 검사를 돌린다.\n")
P("## 7. 구현 스케치\n")
P("### items.yml\n")
P("```yaml\n  spore_kris:\n    ...\n    unique: {id: rend, name: \"아물지 않는 상처\", pct: 0.12, duration: 4, max_stacks: 5}\n  frostbone_longbow:\n    unique: {id: imbue, name: \"얼음뼈 화살\", element: frost, chance: 0.25, pct: 0.17, duration: 3}\n```\n")
P("- `unique` 는 무기만. `id` = 닫힌 목록(26개), `name` = 툴팁 이름(8자 이하 권장), 나머지 = 수치 (빠진 수치는 카탈로그 기준값 × 1).")
P("- 수치는 굴리지 않는다(고정). 강화는 고유 효과를 바꾸지 않는다 — 강화로 '정답'이 다시 생기지 않게.")
P("- 착용 요구 능력치를 못 채우면 무기 스킬처럼 고유 효과도 꺼진다 (`EquipRules.usable`).\n")
P("### 코드 위치\n")
P("| 할 일 | 파일 | 내용 |")
P("|---|---|---|")
rows=[
("정의 읽기","content/ItemDef.java, ContentLoader","`record UniqueDef(String id, String name, Params params)` 를 ItemDef 에 추가, items.yml `unique` 파싱"),
("검사","ContentValidator + 새 UniqueEffectCatalogTest","id 가 닫힌 목록인지, 무기에만 있는지, 필수 수치·범위(max), ranged_only 효과가 활·지팡이에만 있는지, 모든 무기에 하나씩 있는지"),
("서비스","새 items/unique/UniqueEffectService (DamageService.Hook + Listener)","플레이어별 상태(중첩·N번째 카운터·첫 타 기록·재발동 시각). ItemsModule 에서 `services.damage().addHook(..)`"),
("들고 있는 무기","EquipmentListener (손 바꿈 때 이미 스탯 재계산)","주손 무기의 UniqueDef 를 캐시 → UniqueEffectService.current(player). 요구 능력치 미달이면 null"),
("적중·치명타·대상 상태 (공격자)","Hook.before(ctx)","vs_state(hemorrhage critBonus·execute·exploit·backstab·first_strike·berserk) = ctx.amount()/critBonus 조정. counterstep·bloodrush 의 '다음 공격' 소모도 여기"),
("적중 후 효과","Hook.after(ctx)","on_hit/on_crit/nth_hit: `!ctx.evaded() && ctx.dealt()>0`. rend·imbue·armor_break·cleave·chain_spark·flurry·leech·sanctify·shield_bash·momentum·longshot(관통은 아래)"),
("처치","Hook.after(ctx), ctx.killed()","feast·death_burst·bloodrush·siphon. 공격자 = ctx.attackerPlayer(), 대상이 플레이어면 pvp_rule"),
("들고 맞음","Hook.after(ctx) (대상이 플레이어)","thorns: ctx.amount()(방어 전 피해) × pct 를 공격자에게 `DamageContext.raw(..).source(\"unique:thorns\").noCrit().noLifesteal()`"),
("HP 높음 (받는 피해)","Hook.absorb(ctx, dmg) (대상이 플레이어)","steadfast: HP ≥ thr 이면 dmg × (1−dr). 넉백 면역은 StatusEffectService.isKnockbackImmune 확장"),
("회피","DamageService.deal — `if (out.evaded())` 분기","지금은 회피 시 훅을 안 부른다 → `Hook.evaded(ctx)` 기본 메서드를 추가하고 그 분기에서 호출. counterstep 이 사용"),
("방어 깎기","DamageService.deal — 방어 요소 계산 직후","`defense *= 1 − services.unique().defenseShred(target)` (armor_break 중첩 × pct, 상한 40%). PvP 대상은 3중첩까지"),
("스킬 사용","LabWeaponSkillService.handle (impl.cast 직후, 약 202행) · LabyrinthClassService (useMana 직후, 약 367행)","`services.unique().onSkill(player)` → overcharge 충전. 무기 스킬과 직업 스킬 모두"),
("관통","CombatListener.onShoot (EntityShootBowEvent)","longshot: 화살 `setPierceLevel(pierce)`, 맞을 때 거리 ≥ dist 면 before 에서 +pct. 지팡이 기본 공격(투사체)도 같은 경로"),
("주기 기운","UniqueEffectService 1초 타이머","ward_aura: period 마다 TargetFilter 아군(같은 파티) 반경 안 최대 5명에게 StatusEffectService.addShield(.., \"unique:ward\"). 최근 5초 전투일 때만, 안전지대 제외"),
("상태이상","LabyrinthStatusEffectService","bleed 에 중첩 추가(venom 방식), frost 5중첩 → frozen 1초(보스 면역 → vulnerable 0.05 3초)"),
("툴팁","ItemTooltip.lines","스탯 다음 고유 2줄. 접기 단계(6장) + 보스 장비 순서 변경. 도감(CodexMenu)도 같은 lines 사용"),
("PvP","pvp/PvpModule.PvpHook","고유 효과 피해(source `unique:*`)는 PvpConfig.adjust 를 그대로 거친다 + 효과별 ×0.5 는 UniqueEffectService 가 대상이 플레이어일 때 먼저 곱한다"),
]
for r in rows: P("| "+" | ".join(r)+" |")
P("\n### 폭주 방지 (모든 효과 공통)\n")
P("1. 적중 훅은 기본 공격만 켠다. 스킬·보스 패턴·지속 피해·고유 효과 피해는 켜지 않는다. 예외(스킬에도 켜짐): rend·hemorrhage·execute·exploit·backstab·first_strike·berserk·armor_break·imbue — 그래도 재발동 시간은 그대로.")
P("2. 고유 효과가 낸 피해는 `source(\"unique:<id>\")` 로 표시하고 어떤 고유 효과 훅도 다시 켜지 않는다 (재귀 없음).")
P("3. 범위 효과는 대상 수 상한: 휩쓸기 2~4명, 연쇄 번개 2~4명, 과부하 4명, 시체 폭발은 연쇄 없음.")
P("4. 중첩 상한: 출혈 5 · 독 5 · 서리 5 · 갑옷 부수기 5 · 가속 5. 플레이어 대상은 3.")
P("5. 기절은 같은 적 6초 면역. 보스는 기절·빙결 면역 → 짧은 받는 피해 증가로 바꿈.")
P("6. 회복형(흡수·포식·축성)은 초당 상한이 있다. 보스전에서 무한 유지가 안 된다.\n")
P("### PvP 공통\n")
P("- 대상 고르기는 전부 TargetFilter (같은 파티 = 절대 적 아님, 마을 안전지대 제외). 치유·보호막은 나 + 같은 파티만.")
P("- 고유 효과 피해도 PvpConfig.adjust (×0.7, 한 방 최대 HP 35%) 를 거친다. 그 위에 효과별 ×0.5 (2장 표).")
P("- 기절·빙결은 플레이어에게 느려짐으로 바뀐다. 중첩 효과는 플레이어 대상 3중첩까지.\n")
P("## 8. 테스트 추가\n")
P("- UniqueEffectCatalogTest: 무기 131개 + 새 무기 전부 unique 있음, id 닫힌 목록, 수치 범위, ranged_only.")
P("- UniqueDiversityTest: 같은 weapon_type·같은 5레벨 구간에서 direction 중복 없음 (구간에 무기 5개 이상이면 2개까지 허용).")
P("- TooltipFitTest: 그대로 통과해야 함 (접기 순서 변경 포함). 설명 34자 이하 검사 추가.")
P("- UniqueProcTest (순수 로직): N번째 카운터, 첫 타 창(10초), 재발동, 중첩 상한, PvP 배율.")
open(D+'unique_spec.md','w').write("\n".join(o)+"\n")
print('written', len(o))
