import yaml,json,sys
C='/home/user/nai-cg-maker/labyrinth/plugin/src/main/resources/content/'
it=yaml.safe_load(open(C+'items.yml'))['items']
ws=[(k,v) for k,v in it.items() if v.get('type')=='weapon']
print(len(ws))
ws.sort(key=lambda kv:(kv[1]['weapon_type'],kv[1]['level_req']))
for k,v in ws:
    sk=[s['id'] for s in (v.get('weapon_skills') or [])]
    st={a:b for a,b in v['stats'].items()}
    print(f"{v['weapon_type'][:6]:6} L{v['level_req']:<3} F{v.get('floor')} {v['rarity'][:4]:4} {k:30} {v['name']} | {json.dumps(st,ensure_ascii=False)} | sk={sk} | src={v.get('sources')} req={v.get('requires')}{v.get('requires_any') or ''} m={v.get('model')} aura={v.get('aura')} set={v.get('set_bonus')}")
