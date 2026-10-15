import json,sys,collections,math
D='/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad/design2/'
sys.path.insert(0,D+'tools')
from ue_catalog import E, params_for, pc
from ue_assign import A
W=json.load(open(D+'tools/ue_weapons.json'))
DIR=json.load(open(D+'directions.json'))['tags']
PRIM={'greatsword':'STR','sword_shield':'STR','bow':'DEX','dagger':'DEX','staff':'INT','scepter':'WIS'}
WT_KO={'greatsword':'대검','sword_shield':'한손검·방패','bow':'활','dagger':'단검','staff':'지팡이','scepter':'홀'}
RAR_KO={'common':'일반','uncommon':'고급','rare':'희귀','epic':'영웅','legendary':'전설','mythic':'신화'}
SRC_KO={'drop':'몹','chest':'상자','craft':'대장간','boss':'보스','elite':'정예'}
WGT={'crit_chance':0.5,'crit_damage':0.2,'attack_speed':0.7,'lifesteal':0.4,'skill_damage':0.35,'cooldown_reduction':0.45,
     'damage_reduction':0.8,'evasion':0.6,'move_speed':0.15}
def mid(r): return (r[0]+r[1])/2
def power(w):
    L=w['L']; Sp=8+2.5*(L-1); v=0
    for k,r in w['sec'].items():
        m=mid(r)
        if k==PRIM[w['wt']]: v+=0.02*m/(1+0.02*Sp)
        elif k in WGT: v+=WGT[k]*m
        elif k=='heal_power': v+=0.4*m/(1.5*Sp)   # 치유력 = WIS×1.5 + 장비 (고정값)
        elif k=='mana_regen': v+=0.2*m/(1+0.05*Sp)  # 초당 MP (고정값)
        elif k=='hp': v+=m/(100+9*L)*0.4
        elif k=='defense': v+=m*0.004
        elif k=='hp_regen': v+=m*0.01
        elif k=='mp': v+=m/(80+3*L)*0.15
        elif k=='VIT': v+=m*0.004
        elif k=='LUK': v+=m*0.002
        else: v+=m*0.002
    v+=0.10*len(w['skills'])
    return mid(w['dmg'])*(1+v)
def band(L): return (L-1)//5
def blabel(b): return f"{b*5+1}–{b*5+5}"
for w in W: w['P']=power(w); w['band']=band(w['L'])
top=collections.defaultdict(float)
for w in W: top[(w['wt'],w['band'])]=max(top[(w['wt'],w['band'])],w['P'])
def width(t):
    n=0
    for ch in t:
        if ch==' ': n+=4
        elif '가'<=ch<='힣': n+=9
        elif ord(ch)<128: n+=6
        else: n+=8
    return n
ICD_TXT=lambda e: (e['icd'].get('global') or e['icd'].get('per_attacker') or e['icd'].get('per_target') or 0)
assign={}; problems=[]
for w in W:
    eid,el,title=A[w['id']]; e=E[eid]
    gap=top[(w['wt'],w['band'])]/w['P']-1
    B=min(0.28,max(0.04,0.08+0.6*gap))
    if w['rar']=='common' and w['L']<=1: B=0.04
    elif w['rar']=='common' and w['L']<=3: B=min(B,0.06)
    s=round(B/0.10,2)
    p=params_for(eid,w['L'],s,el)
    desc=e['desc'](p); short=e['short'](p)
    icd=ICD_TXT(e)
    head=f"✧ 고유 {title}"+(f" (재발동 {icd:g}초)" if icd>=1 else "")
    for t,lim in ((desc,34),):
        if len(t)>lim: problems.append((w['id'],'desc>34',len(t),t))
    if width('  '+desc)>330: problems.append((w['id'],'desc px',width('  '+desc),desc))
    if width(head)>330: problems.append((w['id'],'head px',width(head)))
    if width('✧ '+title+' '+short)>330: problems.append((w['id'],'short px'))
    if e['ranged_only'] and w['wt'] not in ('bow','staff'): problems.append((w['id'],'ranged_only'))
    w.update(eid=eid,title=title,gap=gap,B=B,s=s,params=p,desc=desc,short=short,dir=e['direction'])
    assign[w['id']]=dict(effect=eid,name=title,direction=e['direction'],params=p,strength=s,budget=round(B,3),
        tooltip=[head,"  "+desc],tooltip_folded="✧ "+title+" "+short)
print('problems',len(problems)); [print(x) for x in problems[:30]]
# 다양성: (종류, 구간) 안 방향 중복 / 인접 구간 포함 방향 수
div=[];lines=[]
types=['greatsword','sword_shield','bow','dagger','staff','scepter']
CORE={'greatsword':['blast','sustain','sunder','execute','frenzy','bleed_crit'],
      'sword_shield':['bulwark','sunder','sustain','support','tempo','execute'],
      'bow':['ambush','tempo','affliction','blast','bleed_crit','execute'],
      'dagger':['ambush','bleed_crit','affliction','tempo','frenzy','execute'],
      'staff':['mana_flow','affliction','blast','execute'],
      'scepter':['support','mana_flow','bulwark','affliction','sunder']}
gaps={}
for t in types:
    for b in range(10):
        ws=[w for w in W if w['wt']==t and w['band']==b]
        ds=[w['dir'] for w in ws]
        dup=[d for d,c in collections.Counter(ds).items() if c>1]
        near=set(w['dir'] for w in W if w['wt']==t and abs(w['band']-b)<=1)
        miss=[d for d in CORE[t] if d not in ds]
        gaps[(t,b)]=miss
        div.append((t,b,len(ws),len(set(ds)),dup,len(near)))
bad=[d for d in div if d[4]]
print('dup bands',bad)
print('near<3', [(d[0],d[1],d[5]) for d in div if d[5]<3 and d[2]>0])
# 희귀도별 평균 강도
by=collections.defaultdict(list)
for w in W: by[w['rar']].append(w['s'])
print({k:round(sum(v)/len(v),2) for k,v in by.items()})
json.dump(dict(W=W,assign=assign,gaps={f"{t}|{b}":m for (t,b),m in gaps.items()},div=div),open(D+'tools/ue_state.json','w'),ensure_ascii=False)
