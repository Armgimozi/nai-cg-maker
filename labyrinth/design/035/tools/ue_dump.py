import yaml,json,collections,sys
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
it=yaml.safe_load(open(C+'items.yml'))['items']
loot=yaml.safe_load(open(C+'loot.yml'))
tables=loot.get('tables',loot)
rec=yaml.safe_load(open(C+'recipes.yml'))
W={k:v for k,v in it.items() if v.get('type')=='weapon'}
home=collections.defaultdict(set)
def walk(tid,t):
    if not isinstance(t,dict): return
    for sec,val in t.items():
        if isinstance(val,list):
            for e in val:
                if isinstance(e,dict):
                    if e.get('item') in W: home[e['item']].add(tid)
                    for x in e.get('one_of') or []:
                        if x in W: home[x].add(tid)
for tid,t in tables.items(): walk(tid,t)
rs=rec.get('recipes',rec)
if isinstance(rs,dict):
  for rid,r in rs.items():
    if not isinstance(r,dict): continue
    out=r.get('result') or r.get('output') or {}
    oid=out.get('item') if isinstance(out,dict) else out
    if oid in W: home[oid].add('craft')
out=[]
for k,v in sorted(W.items(), key=lambda kv:(kv[1]['weapon_type'],kv[1]['level_req'])):
    st=v['stats']
    sec={a:b for a,b in st.items() if a!='damage'}
    sk=[s['name'] for s in (v.get('weapon_skills') or [])]
    out.append(dict(id=k,wt=v['weapon_type'],L=v['level_req'],F=v.get('floor'),rar=v['rarity'],name=v['name'],dmg=st.get('damage'),sec=sec,skills=sk,src=v.get('sources'),homes=sorted(home[k]),cls=v.get('classes'),lore=v.get('lore','')))
json.dump(out,open(sys.argv[1],'w'),ensure_ascii=False,indent=0)
for o in out:
    print(f"{o['wt'][:6]:6} L{o['L']:<2} F{o['F']} {o['rar'][:4]:4} {o['id']:26} {o['name']} dmg={o['dmg']} {list(o['sec'].keys())} sk={len(o['skills'])} src={o['src']} h={o['homes']}")
print(len(out))
