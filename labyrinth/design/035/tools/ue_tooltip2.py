# 제안 툴팁 규칙: 고유 효과 2줄(머리+설명 1줄). 줄이 넘치면 단계적으로 접는다.
# 일반: 0 전부 · 1 설명(이야기) 뺌 · 2 획득처 뺌 · 3 빈 줄 뺌 · 4 스킬 설명 첫 줄만 + 고유 효과 1줄로 접기
# 보스 고유: 0 전부 · 1 이야기 뺌 · 2 빈 줄 뺌 · 3 스킬 설명 첫 줄만 + 고유 1줄 (획득처 유지) · 4 획득처 뺌
import yaml,math,sys
sys.path.insert(0,'/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad/design2/tools')
from ue_tooltip import wrap,it,MAX
def count(v,U=2,E=2):
    head=1+(1 if v.get('requires') or v.get('requires_any') else 0)
    n=len(v['stats']); stats=1+math.ceil((n-1)/2)
    sk=v.get('weapon_skills') or []
    descs=[len(wrap(s.get('description',''))) for s in sk]
    flavor=len(wrap(v.get('lore',''))) if v.get('lore') else 0
    boss='boss' in (v.get('sources') or [])
    for tier in range(5):
        if boss: keep=tier<=3; blanks=tier<=1; short=tier>=3
        else: keep=tier<=1; blanks=tier<=2; short=tier>=4
        o=head+(1 if blanks else 0)+stats+E
        o+=(1 if blanks else 0)+len(sk)+sum((1 if short and d>1 else d) for d in descs)+(1 if short else U)
        if tier==0 and flavor: o+=1+flavor
        if keep: o+=1
        if o<=MAX: return o,tier,keep
    return o,tier,keep
ws=[(k,v) for k,v in it.items() if v.get('type')=='weapon']
bad=[];worst=(0,'')
for k,v in ws:
    for E in (2,1,0):
        o,t,keep=count(v,2,E)
        if o>MAX or ('boss' in v['sources'] and not keep): bad.append((k,E,o,t))
        worst=max(worst,(o,k))
print('bad',bad,'worst',worst)
for k,v in ws:
    o,t,keep=count(v,2,2)
    if t>=3: print(' tier>=3:',k,o,t,keep)
