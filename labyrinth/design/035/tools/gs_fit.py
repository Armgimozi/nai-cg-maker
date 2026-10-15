"""items.yml 무기 수치 → 공식 맞추기 (피해 · 주 스탯 · 부가 스탯)."""
import yaml,collections,statistics as S
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
it=yaml.safe_load(open(C+'items.yml'))['items']
W={k:v for k,v in it.items() if v.get('type')=='weapon'}
TS={'sword_shield':1.00,'greatsword':1.55,'bow':1.30,'staff':1.10,'scepter':0.95,'dagger':0.62}
RM={'common':1.00,'uncommon':1.06,'rare':1.13,'epic':1.21,'legendary':1.31,'mythic':1.45}
RC={'common':0.6,'uncommon':0.8,'rare':1.0,'epic':1.2,'legendary':1.45,'mythic':1.75}
P=lambda L:7+0.25*(L-1)+0.0195*(L-1)**2
BASE={'hp':lambda L:3+3.2*L,'mp':lambda L:2+1.6*L,'defense':lambda L:1+0.35*L,'crit_chance':lambda L:0.01+0.0009*L,
 'crit_damage':lambda L:0.03+0.003*L,'attack_speed':lambda L:0.02+0.0009*L,'move_speed':lambda L:0.01+0.0005*L,
 'cooldown_reduction':lambda L:0.01+0.0009*L,'skill_damage':lambda L:0.02+0.0015*L,'mana_regen':lambda L:0.1+0.015*L,
 'hp_regen':lambda L:0.2+0.05*L,'heal_power':lambda L:1+0.8*L,'lifesteal':lambda L:0.01+0.0006*L,
 'damage_reduction':lambda L:0.01+0.0006*L,'evasion':lambda L:0.01+0.0006*L}
PRIM={'greatsword':'STR','sword_shield':'STR','bow':'DEX','dagger':'DEX','staff':'INT','scepter':'WIS'}
dm=[];pr=collections.defaultdict(list);sec=collections.defaultdict(list);wid=[]
for k,v in W.items():
    L=v['level_req'];r=v['rarity'];wt=v['weapon_type'];st=v['stats']
    d=st['damage'];m=(d[0]+d[1])/2
    dm.append(m/(P(L)*RM[r]*TS[wt])); wid.append((d[1]-d[0])/2/m)
    p=st.get(PRIM[wt]); 
    if p: pr[r].append(((p[0]+p[1])/2)/((1+0.22*L)*RC[r]))
    for key,val in st.items():
        if key in BASE:
            sec[(key,r)].append(((val[0]+val[1])/2)/(BASE[key](L)*RC[r]))
print('damage ratio mean %.3f sd %.3f min %.3f max %.3f'%(S.mean(dm),S.pstdev(dm),min(dm),max(dm)))
print('damage half-width mean %.3f min %.3f max %.3f'%(S.mean(wid),min(wid),max(wid)))
for r,v in pr.items(): print('primary',r,'%.2f'%S.mean(v),len(v))
agg=collections.defaultdict(list)
for (key,r),v in sorted(sec.items()): agg[r]+=v; print('sec',key,r,'%.2f'%S.mean(v),len(v))
for r,v in agg.items(): print('SEC ALL',r,'%.3f sd %.3f'%(S.mean(v),S.pstdev(v)))
# number of secondaries by rarity
cnt=collections.defaultdict(list); sk=collections.defaultdict(list)
for k,v in W.items():
    n=len([x for x in v['stats'] if x not in ('damage',PRIM[v['weapon_type']])]); cnt[v['rarity']].append(n); sk[v['rarity']].append(len(v.get('weapon_skills') or []))
for r in RM: print(r,'secondaries',collections.Counter(cnt[r]),'skills',collections.Counter(sk[r]))
