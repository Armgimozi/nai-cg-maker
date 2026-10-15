import yaml,json,collections
C='/home/user/w-r1/labyrinth/plugin/src/main/resources/content/'
it=yaml.safe_load(open(C+'items.yml'))['items']
loot=yaml.safe_load(open(C+'loot.yml'))['tables']
rec=yaml.safe_load(open(C+'recipes.yml'))
W={k:v for k,v in it.items() if v.get('type')=='weapon'}
home=collections.defaultdict(set)
def walk(tid,t):
    for sec in ('entries','guaranteed'):
        for e in (t.get(sec) or []):
            if 'item' in e and e['item'] in W: home[e['item']].add(tid)
            for x in e.get('one_of') or []:
                if x in W: home[x].add(tid)
for tid,t in loot.items(): walk(tid,t)
# recipes
rs=rec.get('recipes',rec)
for rid,r in (rs.items() if isinstance(rs,dict) else []):
    out=r.get('result') or r.get('output') or {}
    oid=out.get('item') if isinstance(out,dict) else out
    if oid in W: home[oid].add('recipe:'+rid)
res={}
for k,v in sorted(W.items(), key=lambda kv:(kv[1]['weapon_type'],kv[1]['level_req'])):
    res[k]=sorted(home[k])
    print(v['weapon_type'][:6],v['level_req'],v['rarity'][:4],k,sorted(home[k]))
json.dump(res,open('/tmp/claude-0/-home-user-nai-cg-maker/f3f3d909-a465-5457-ae4c-97c24013e339/scratchpad/design2/tools/homes.json','w'),ensure_ascii=False,indent=1)
