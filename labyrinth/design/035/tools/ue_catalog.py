# 무기 고유 효과 카탈로그 (26종). 수치 = 기준값(강도 s=1) × s, 상한 max. kind: s=강도 비례, f=고정, L=레벨 단계
# s = B/0.10, B(효과 예산) = clamp(0.08 + 0.6*gap, 0.04, 0.28)  — gap = 같은 무기 종류·같은 5레벨 구간 최고 무기 대비 기본 성능 부족분
def pc(v): return f"{round(v*100,1):g}%"
def sec(v): return f"{v:g}초"
E = {}
def eff(id, name, direction, hook, params, desc, short, icd, pvp, note="", melee_only=False, ranged_only=False):
    E[id] = dict(id=id, name=name, direction=direction, hook=hook, params=params, desc=desc, short=short,
                 icd=icd, pvp_rule=pvp, note=note, melee_only=melee_only, ranged_only=ranged_only)

# ── 출혈치명 ──
eff("rend","찢는 치명","bleed_crit","on_crit",
    {"pct":(0.06,"s",0.15),"duration":(4,"f",None),"max_stacks":(5,"f",None)},
    lambda p: f"치명타 시 출혈 (중첩당 초당 공격력 {pc(p['pct'])}, 최대 {p['max_stacks']})",
    lambda p: f"치명타 → 출혈 {pc(p['pct'])}",
    {"per_target":0.4}, "출혈 피해 ×0.5, 플레이어에게는 최대 3중첩",
    "출혈 중첩은 StatusEffectService bleed 에 stacks 를 더한다(venom 과 같은 방식). 기본 공격·스킬 치명타 모두.")
eff("hemorrhage","피 냄새","bleed_crit","vs_state",
    {"cc":(0.10,"s",0.22),"cd":(0.20,"s",0.45)},
    lambda p: f"출혈 중인 적에게 치명 확률 +{pc(p['cc'])}, 치명 피해 +{pc(p['cd'])}",
    lambda p: f"출혈 적에게 치명 +{pc(p['cc'])}",
    {}, "그대로 (치명 피해는 PvP 상한이 막는다)", "출혈을 거는 다른 수단(직업 스킬·무기 스킬·rend)과 짝. 혼자서는 아무것도 안 한다.")
# ── 유지흡혈 ──
eff("leech","생명 흡수","sustain","on_hit",
    {"pct":(0.06,"s",0.14),"cap":(0.03,"f",None)},
    lambda p: f"기본 공격 피해의 {pc(p['pct'])} 회복 (초당 최대 HP {pc(p['cap'])}까지)",
    lambda p: f"적중 회복 {pc(p['pct'])}",
    {"per_second_cap":"max_hp*cap"}, "회복량 ×0.5", "흡혈 스탯과 별도 합산. 회복 상한이 있어 보스전 무한 유지는 안 된다.")
eff("feast","포식","sustain","on_kill",
    {"heal":(0.04,"s",0.10),"ls":(0.04,"s",0.10),"duration":(4,"f",None)},
    lambda p: f"처치 시 최대 HP {pc(p['heal'])} 회복, {sec(p['duration'])}간 흡혈 +{pc(p['ls'])}",
    lambda p: f"처치 → HP {pc(p['heal'])}",
    {"global":1.0}, "플레이어 처치에도 발동 (재발동 1초 그대로)", "보스 소환체도 처치로 친다. 몹이 적은 보스전에서는 약하다(장단점).")
# ── 방벽제어 ──
eff("thorns","가시 반격","bulwark","on_hurt",
    {"pct":(0.30,"s",0.70)},
    lambda p: f"맞으면 줄기 전 피해의 {pc(p['pct'])}를 되돌린다 (근접만)",
    lambda p: f"반사 {pc(p['pct'])}",
    {"per_attacker":0.5}, "되돌리는 피해 ×0.5, PvP 상한 적용", "줄기 전 피해 기준이라 피해 감소·방어를 쌓아도 반사가 줄지 않는다 → 판금 탱커의 공격 수단.")
eff("shield_bash","방패 강타","bulwark","nth_hit",
    {"n":(5,"L",None),"stun":(0.8,"s",1.5),"pct":(0.40,"s",0.9),"vuln":(0.06,"s",0.14)},
    lambda p: f"{p['n']}번째 공격마다 기절 {sec(p['stun'])} + 공격력 {pc(p['pct'])}",
    lambda p: f"{p['n']}타 기절 {sec(p['stun'])}",
    {"per_target_stun_immunity":6.0}, "기절 대신 느려짐 40% 1초", "같은 적은 6초 동안 다시 기절하지 않는다(기절 잠금 방지). 보스는 기절 면역 → 받는 피해 증가 3초.")
eff("steadfast","굳건함","bulwark","hp_above",
    {"thr":(0.70,"f",None),"dr":(0.08,"s",0.18)},
    lambda p: f"HP {pc(p['thr'])} 이상이면 받는 피해 -{pc(p['dr'])}, 밀려나지 않음",
    lambda p: f"HP 높으면 피해 -{pc(p['dr'])}",
    {}, "그대로", "체력 재생·회복을 받는 판금 빌드용. 한 번 무너지면 효과가 꺼진다(장단점).")
# ── 폭발범위 ──
eff("cleave","휩쓸기","blast","on_hit",
    {"pct":(0.30,"s",0.70),"radius":(2.5,"f",None),"targets":(2,"L",None)},
    lambda p: f"기본 공격이 주변 {p['radius']:g}칸 적 {p['targets']}명에게 공격력 {pc(p['pct'])}",
    lambda p: f"주변 {p['targets']}명 {pc(p['pct'])}",
    {}, "휩쓸린 플레이어는 ×0.5", "주 대상 1명뿐이면 아무 효과 없음 → 사냥 빌드. 활·지팡이는 맞은 자리 기준.", melee_only=False)
eff("chain_spark","연쇄 번개","blast","on_hit",
    {"chance":(0.20,"f",None),"pct":(0.45,"s",1.0),"targets":(2,"L",None)},
    lambda p: f"{pc(p['chance'])} 확률로 번개가 {p['targets']}명에게 튐 (공격력 {pc(p['pct'])})",
    lambda p: f"번개 {p['targets']}명 {pc(p['pct'])}",
    {"global":1.0}, "번개 피해 ×0.5, 아군·안전지대 플레이어는 건너뜀", "마법 피해. 튀는 대상은 주 대상 6칸 안의 적만(TargetFilter).")
eff("death_burst","시체 폭발","blast","on_kill",
    {"pct":(0.80,"s",1.8),"radius":(3.0,"f",None)},
    lambda p: f"처치한 적이 터져 {p['radius']:g}칸 안 적에게 공격력 {pc(p['pct'])}",
    lambda p: f"처치 폭발 {pc(p['pct'])}",
    {"global":0.5}, "플레이어를 처치하면 터지지 않음", "폭발로 죽은 적은 다시 터지지 않는다(연쇄 없음). 보스·정예 단일전에서는 거의 쓸모없다.")
# ── 처형 ──
eff("execute","마무리","execute","vs_state",
    {"thr":(0.30,"f",None),"pct":(0.25,"s",0.60)},
    lambda p: f"HP {pc(p['thr'])} 이하 적에게 피해 +{pc(p['pct'])} (보스는 60%만)",
    lambda p: f"빈사 적 +{pc(p['pct'])}",
    {}, "+피해 ×0.5", "정예·보스의 마지막 구간을 줄인다. 앞 70%에서는 아무것도 안 한다.")
eff("bloodrush","추격","execute","on_kill",
    {"pct":(0.60,"s",1.4),"ms":(0.10,"f",None),"duration":(3,"f",None)},
    lambda p: f"처치하면 다음 공격 피해 +{pc(p['pct'])}, {sec(p['duration'])}간 이동 +{pc(p['ms'])}",
    lambda p: f"처치 → 다음 +{pc(p['pct'])}",
    {"global":1.0}, "+피해 ×0.5", "몹 무리를 하나씩 끊어 가는 빌드. 다음 공격은 스킬도 된다.")
# ── 속공 ──
eff("momentum","가속","tempo","on_hit",
    {"as":(0.03,"s",0.06),"max_stacks":(5,"f",None),"decay":(3,"f",None)},
    lambda p: f"적중마다 공격 속도 +{pc(p['as'])} ({p['max_stacks']}중첩), {sec(p['decay'])} 쉬면 사라짐",
    lambda p: f"적중 공속 +{pc(p['as'])}×{p['max_stacks']}",
    {}, "그대로", "멈추면 잃는다. 이동하며 치는 가죽 빌드. 공격 속도 상한(+60%)은 StatCalculator 가 지킨다.")
eff("flurry","연타","tempo","nth_hit",
    {"n":(4,"f",None),"pct":(0.70,"s",1.6)},
    lambda p: f"{p['n']}번째 공격마다 공격력 {pc(p['pct'])}의 추가 타격",
    lambda p: f"{p['n']}타 추가 {pc(p['pct'])}",
    {}, "추가 타격 ×0.5", "추가 타격은 치명타가 날 수 있고 흡혈은 없다. 공격 속도와 곱으로 좋아진다.")
eff("counterstep","흘려치기","tempo","on_dodge",
    {"pct":(0.30,"s",0.70),"window":(3,"f",None),"ms":(0.15,"f",None)},
    lambda p: f"회피하면 {sec(p['window'])} 안 다음 공격 치명타 확정, 피해 +{pc(p['pct'])}",
    lambda p: f"회피 → 확정 치명",
    {"global":2.0}, "+피해 ×0.5", "회피 스탯(가죽·DEX)이 있어야 굴러간다. 2초 이동 +15%.")
# ── 마나순환 ──
eff("siphon","마력 흡수","mana_flow","on_kill",
    {"mp":(0.05,"s",0.12),"cdr":(0.5,"s",1.2)},
    lambda p: f"처치 시 MP {pc(p['mp'])} 회복, 무기 스킬 대기 -{sec(p['cdr'])}",
    lambda p: f"처치 → MP {pc(p['mp'])}",
    {"global":0.5}, "플레이어 처치 시 그대로", "몹이 많은 층에서 스킬을 계속 돌린다. 보스 단일전에서는 약하다.")
eff("overcharge","과부하","mana_flow","on_skill",
    {"pct":(1.20,"s",2.6),"window":(5,"f",None),"radius":(2.5,"f",None)},
    lambda p: f"스킬을 쓰면 다음 기본 공격이 공격력 {pc(p['pct'])} 폭발",
    lambda p: f"스킬 후 폭발 {pc(p['pct'])}",
    {"global":3.0}, "폭발 피해 ×0.5", "무기 스킬·직업 스킬 모두. 반경 2.5칸 적 최대 4명, 마법 피해. 5초 안에 쳐야 한다.")
# ── 지원 ──
eff("sanctify","축성","support","on_hit",
    {"pct":(0.12,"s",0.28),"radius":(8,"f",None)},
    lambda p: f"적중 시 {p['radius']:g}칸 안 가장 다친 아군을 공격력 {pc(p['pct'])} 치유",
    lambda p: f"적중 → 아군 치유",
    {"global":0.5}, "아군 = 나 + 같은 파티. 혼자면 자신에게 절반", "치유량 = 공격력 × pct + 치유력(heal_power) × 0.3. 때리는 사제·성기사 빌드.")
eff("ward_aura","수호 기운","support","aura",
    {"pct":(0.04,"s",0.09),"period":(8,"f",None),"radius":(8,"f",None),"duration":(6,"f",None)},
    lambda p: f"{sec(p['period'])}마다 {p['radius']:g}칸 아군에게 최대 HP {pc(p['pct'])} 보호막",
    lambda p: f"보호막 {pc(p['pct'])}/{sec(p['period'])}",
    {"period":8}, "같은 파티만, 마을 안전지대 안에서는 멈춤", "전투 중(최근 5초 안에 피해를 주거나 받음)일 때만. 최대 5명, 자신 포함.")
# ── 상태이상 ──
eff("imbue","원소 부여","affliction","on_hit",
    {"chance":(0.25,"f",None),"pct":(0.10,"s",0.22),"duration":(3,"f",None)},
    lambda p: {"burn":f"{pc(p['chance'])} 확률로 {sec(p['duration'])} 불태움 (초당 공격력 {pc(p['pct'])})",
               "poison":f"{pc(p['chance'])} 확률로 독 1중첩 (초당 공격력 {pc(p['pct'])}, 최대 5)",
               "frost":f"{pc(p['chance'])} 확률로 서리 1중첩, 5중첩이면 빙결 1초"}[p['element']],
    lambda p: {"burn":"적중 → 불태움","poison":"적중 → 독 중첩","frost":"적중 → 서리"}[p['element']],
    {"per_target":1.0}, "지속 피해 ×0.5, 빙결 대신 느려짐", "element = burn | poison | frost. 서리는 중첩당 느려짐 8%, 보스는 빙결 대신 받는 피해 +5%(3초).")
eff("exploit","약점 파고들기","affliction","vs_state",
    {"pct":(0.15,"s",0.35)},
    lambda p: f"상태이상 걸린 적에게 피해 +{pc(p['pct'])} (2개면 1.6배)",
    lambda p: f"상태이상 적 +{pc(p['pct'])}",
    {}, "+피해 ×0.5", "불태움·독·출혈·서리·느려짐·약화·실명·표식 중 하나라도. 거는 수단은 직업·무기 스킬·imbue.")
# ── 기습 ──
eff("first_strike","선제","ambush","first_hit",
    {"pct":(0.80,"s",1.8),"cc":(0.20,"f",None),"window":(10,"f",None)},
    lambda p: f"처음 때리는 적에게 피해 +{pc(p['pct'])}, 치명 확률 +{pc(p['cc'])}",
    lambda p: f"첫 타 +{pc(p['pct'])}",
    {"boss":30.0}, "+피해 ×0.5", "'처음' = 이 적을 최근 10초 동안 안 때림. 보스는 30초에 한 번. 치고 빠지는 빌드.")
eff("backstab","등 찌르기","ambush","vs_state",
    {"pct":(0.25,"s",0.60)},
    lambda p: f"적의 등 뒤에서 때리면 피해 +{pc(p['pct'])}",
    lambda p: f"등 뒤 +{pc(p['pct'])}",
    {}, "+피해 ×0.5", "등 뒤 = 대상이 보는 방향 뒤쪽 120°. 그림자 급소 찌르기(치명 +20%)와 겹친다. 탱커가 있는 파티에서 강하다.")
eff("longshot","관통 사격","ambush","on_hit",
    {"dist":(12,"f",None),"pct":(0.20,"s",0.45),"pierce":(1,"L",None)},
    lambda p: f"{p['dist']:g}칸 밖 적에게 피해 +{pc(p['pct'])}, 화살·탄이 {p['pierce']}명 더 꿰뚫음",
    lambda p: f"원거리 +{pc(p['pct'])}",
    {}, "+피해 ×0.5", "활·지팡이 전용. 꿰뚫을 때마다 피해 -20%. 가까이 붙으면 약해진다(장단점).", ranged_only=True)
# ── 광기 ──
eff("berserk","광기","frenzy","hp_below",
    {"pct":(0.025,"s",0.055),"ls":(0.05,"s",0.12),"thr":(0.30,"f",None)},
    lambda p: f"잃은 HP 10%마다 피해 +{pc(p['pct'])}, 빈사 흡혈 +{pc(p['ls'])}",
    lambda p: f"다칠수록 +{pc(p['pct'])}/10%",
    {}, "+피해 ×0.5", "광전사 피의 분노와 합쳐 최대 +50%. 판금·회복 없이 아슬아슬하게 버티는 빌드.")
# ── 파쇄 ──
eff("armor_break","갑옷 부수기","sunder","on_hit",
    {"pct":(0.04,"s",0.08),"max_stacks":(5,"f",None),"duration":(5,"f",None)},
    lambda p: f"적중마다 대상 방어 -{pc(p['pct'])} ({p['max_stacks']}중첩, {sec(p['duration'])})",
    lambda p: f"방어 -{pc(p['pct'])}×{p['max_stacks']}",
    {"per_target":0.3}, "플레이어에게는 최대 3중첩", "깎인 방어는 파티 전원의 공격에 적용 → 긴 싸움(정예·보스)에서 빛난다. 일반 몹은 금방 죽어 손해.")

SECS={'stun','cdr','duration','window','period','decay'}
def nice(k,v):
    if k in SECS: return round(v,1)
    if v>=0.1: return round(v,2)
    return round(round(v*200)/200,3)  # 0.5% 단위
def level_int(eid, key, L, s):
    if eid=="shield_bash" and key=="n": return 4 if s>=1.4 else 5
    if eid=="cleave" and key=="targets": return 2 + (L>=20) + (L>=40)
    if eid=="chain_spark" and key=="targets": return 2 + (L>=15) + (L>=35)
    if eid=="longshot" and key=="pierce": return 1 + (L>=30)
    raise KeyError((eid,key))
def params_for(eid, L, s, element=None):
    e=E[eid]; out={}
    for k,(ref,kind,mx) in e['params'].items():
        if kind=="f": v=ref
        elif kind=="L": v=level_int(eid,k,L,s)
        else:
            v=ref*s
            if mx is not None: v=min(v,mx)
            v=nice(k,v)
        out[k]=v
    if element: out['element']=element
    return out
