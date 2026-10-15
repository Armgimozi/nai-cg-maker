"""기존 무기 131개 → 구간별 공격 방식·요구 능력치·방향·획득처 종류 (새 무기 설계용 빈칸 찾기)."""
import yaml,json,collections
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
D='/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad/design2/'
it=yaml.safe_load(open(C+'items.yml'))['items']
loot=yaml.safe_load(open(C+'loot.yml'))['tables']
U=json.load(open(D+'unique_spec.json'))['assignments']
STYLE={'greatsword':'melee','sword_shield':'melee','dagger':'melee','bow':'ranged','staff':'caster','scepter':'caster'}
SPEED={'sword_shield':1.5,'greatsword':0.95,'dagger':2.2,'bow':1.2,'staff':1.1,'scepter':1.3}
REQ={'greatsword':'STR','sword_shield':'STR','bow':'DEX','dagger':'DEX','staff':'INT','scepter':'WIS'}
def kind(v):
    s=v.get('sources',[])
    if 'boss' in s: return 'boss'
    if s==['craft']: return 'forge'
    if 'drop' in s: return 'chest'   # gear_fNN_common (몬스터·상자)
    return '?'
band=lambda L:(L-1)//5+1
rows=[]
for k,v in it.items():
    if v.get('type')!='weapon': continue
    wt=v['weapon_type']
    rows.append(dict(id=k,band=band(v['level_req']),L=v['level_req'],F=v['floor'],rar=v['rarity'],style=STYLE[wt],speed=SPEED[wt],
        req=REQ[wt],dir=U[k]['direction'],eff=U[k]['effect'],kind=kind(v),src=v.get('sources'),shape=v['model']['shape'],wt=wt,name=v['name']))
if __name__=='__main__':
    for b in range(1,11):
        rs=[r for r in rows if r['band']==b]
        print(f"band {b}: n={len(rs)} style={dict(collections.Counter(r['style'] for r in rs))} req={dict(collections.Counter(r['req'] for r in rs))} kind={dict(collections.Counter(r['kind'] for r in rs))}")
        print('   dirs', dict(collections.Counter(r['dir'] for r in rs)))
        allD=set(json.load(open(D+'directions.json'))['tags'])
        print('   missing dirs', sorted(allD-set(r['dir'] for r in rs)))
